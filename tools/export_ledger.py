#!/usr/bin/env python3
"""Export the private delegation ledger into this public record, sanitized.

The ledger is the operating evidence behind the fleet: every delegated agent run,
which model family took it, and whether it worked. It is written continuously by
the delegation wrappers and is never edited by hand.

This exporter is the only path from the private file to the public one, and it is
built to fail closed. A missing or empty denylist is a broken gate, not a pass. A
banned term that survives into the output aborts the write. The point is that the
public file can be trusted precisely because the export refuses to guess.

Usage:
    python3 tools/export_ledger.py --ledger ~/.local/state/delegation-ledger.jsonl \
        --denylist path/to/denylist.txt
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

REDACTED = "[redacted: allowlist policy]"
REQUIRED_KEYS = ("engine", "outcome", "qa", "task", "ts")


class GateBroken(RuntimeError):
    """The export gate could not be established. Never treat this as a pass."""


def load_denylist(path: Path | None) -> list[str]:
    """Load banned terms. Absent, unreadable, or empty is a broken gate."""
    if path is None:
        raise GateBroken("no denylist supplied - refusing to export unscreened rows")
    if not path.is_file():
        raise GateBroken(f"denylist not found at {path} - gate is broken, not passing")
    terms = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not terms:
        raise GateBroken(f"denylist at {path} is empty - gate is broken, not passing")
    return terms


def _pattern(term: str) -> re.Pattern[str]:
    """Short alphanumeric terms match whole-word only, so 'ate' misses 'operate'."""
    escaped = re.escape(term)
    if len(term) <= 4 and term.isalnum():
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def find_banned(text: str, terms: Iterable[str]) -> list[str]:
    return [term for term in terms if _pattern(term).search(text)]


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise GateBroken(f"ledger not found at {path}")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GateBroken(f"ledger line {number} is not valid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise GateBroken(f"ledger line {number} is not an object")
        missing = [key for key in REQUIRED_KEYS if key not in row]
        if missing:
            raise GateBroken(f"ledger line {number} is missing {missing}")
        rows.append(row)
    if not rows:
        raise GateBroken("ledger is empty - refusing to publish an empty record")
    return rows


def sanitize(rows: list[dict[str, Any]], terms: list[str]) -> tuple[list[dict], int]:
    """Redact task text that trips the denylist. Redactions are counted, not hidden."""
    clean: list[dict[str, Any]] = []
    redacted = 0
    for row in rows:
        task = str(row.get("task", ""))
        if find_banned(task, terms):
            task = REDACTED
            redacted += 1
        clean.append(
            {
                "ts": row["ts"],
                "engine": row["engine"],
                "outcome": row["outcome"],
                "qa": row["qa"],
                "task": task,
            }
        )
    return clean, redacted


def summarize(rows: list[dict[str, Any]], redacted: int) -> dict[str, Any]:
    days = collections.Counter(str(r["ts"])[:10] for r in rows)
    outcomes = collections.Counter(str(r["outcome"]) for r in rows)
    engines = collections.Counter(str(r["engine"]) for r in rows)
    reviewed = sum(
        1 for r in rows if str(r.get("qa", "")).strip() not in ("", "unreviewed")
    )
    stamps = sorted(str(r["ts"]) for r in rows)
    return {
        "rows": len(rows),
        "window": {
            "first_run": stamps[0],
            "last_run": stamps[-1],
            "days_covered": len(days),
        },
        "engines": dict(engines.most_common()),
        "outcomes": dict(outcomes.most_common()),
        "failure_rate_pct": round(100 * outcomes.get("fail", 0) / len(rows), 2),
        "qa": {
            "annotated": reviewed,
            "unannotated": len(rows) - reviewed,
            "coverage_pct": round(100 * reviewed / len(rows), 1),
            "note": (
                "Most rows carry no per-run QA annotation. High-stakes work is reviewed by a "
                "different model family through held branches, which this field did not record "
                "until annotation began. The gap is published rather than backfilled."
            ),
        },
        "redacted_tasks": redacted,
        "runs_per_day": dict(sorted(days.items())),
    }


def verify_clean(rows: list[dict[str, Any]], terms: list[str]) -> None:
    """Last gate: nothing banned may survive into the output."""
    for index, row in enumerate(rows):
        for value in row.values():
            hits = find_banned(str(value), terms)
            if hits:
                raise GateBroken(
                    f"banned term survived sanitization in row {index} - aborting write"
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the delegation ledger, sanitized"
    )
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--denylist", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("fixtures"))
    args = parser.parse_args(argv)

    try:
        terms = load_denylist(args.denylist)
        rows = read_ledger(args.ledger.expanduser())
        clean, redacted = sanitize(rows, terms)
        verify_clean(clean, terms)
    except GateBroken as exc:
        print(f"EXPORT REFUSED: {exc}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.out_dir / "delegation_ledger.jsonl"
    summary_path = args.out_dir / "delegation_summary.json"
    ledger_path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in clean) + "\n", encoding="utf-8"
    )
    summary = summarize(clean, redacted)
    summary_path.write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"exported {summary['rows']} rows spanning {summary['window']['days_covered']} days"
    )
    print(f"redacted {redacted} task string(s) under the allowlist policy")
    print(
        f"failure rate {summary['failure_rate_pct']}% | QA coverage {summary['qa']['coverage_pct']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
