#!/usr/bin/env python3
"""Build the public operating record from the supplied fixtures only."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
LOG = ROOT / "log"


def load_fixture(name: str) -> Any:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing fixture: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require_keys(mapping: dict[str, Any], *keys: str) -> None:
    for key in keys:
        if key not in mapping:
            raise KeyError(f"Missing fixture key: {key}")


def days_in_window(window: dict[str, str]) -> list[str]:
    require_keys(window, "start", "end")
    start = date.fromisoformat(window["start"])
    end = date.fromisoformat(window["end"])
    if end < start:
        raise ValueError("Fixture window ends before it starts")
    result: list[str] = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def validate(
    meta: dict[str, Any],
    heartbeats: dict[str, Any],
    receipts: dict[str, Any],
    failures: dict[str, Any],
    days: list[str],
) -> None:
    require_keys(
        meta,
        "cost_note",
        "live_day_1",
        "notes",
        "reconstructed",
        "reconstructed_note",
        "redaction_policy",
        "window",
    )
    if not isinstance(meta["window"], dict):
        raise TypeError("Fixture key window must be an object")
    require_keys(meta["window"], "start", "end")
    if meta["live_day_1"] not in days:
        raise ValueError("live_day_1 is outside the fixture window")

    for day in days:
        if day not in receipts:
            raise KeyError(f"Missing value_receipts day: {day}")
        receipt = receipts[day]
        if not isinstance(receipt, dict):
            raise TypeError(f"value_receipts {day} must be an object")
        require_keys(
            receipt,
            "attention_gate_emits",
            "capture_ingest_runs",
            "compute_minutes",
            "delegated_runs",
            "failed_fires",
            "job_fires",
            "partial_day",
        )
        if not isinstance(receipt["delegated_runs"], dict):
            raise TypeError(f"delegated_runs for {day} must be an object")
        for engine, delegated in receipt["delegated_runs"].items():
            if not isinstance(delegated, dict):
                raise TypeError(f"delegated run for {engine} on {day} must be an object")
            require_keys(delegated, "qa_pass", "runs")

        if day not in failures:
            raise KeyError(f"Missing failures_7d day: {day}")
        if not isinstance(failures[day], list) or not failures[day]:
            raise ValueError(f"failures_7d {day} must be a non-empty list")
        for story in failures[day]:
            if not isinstance(story, dict):
                raise TypeError(f"failure story for {day} must be an object")
            require_keys(story, "lesson", "status", "system", "what")

    if not heartbeats:
        raise ValueError("heartbeats_7d must contain at least one system")
    for system, record in heartbeats.items():
        if not isinstance(record, dict):
            raise TypeError(f"heartbeat record for {system} must be an object")
        require_keys(record, "days", "desc")
        if not isinstance(record["days"], dict):
            raise TypeError(f"heartbeat days for {system} must be an object")
        for day, row in record["days"].items():
            if day not in days:
                raise ValueError(f"heartbeat day outside window: {system} {day}")
            if not isinstance(row, dict):
                raise TypeError(f"heartbeat row for {system} on {day} must be an object")
            require_keys(row, "compute_min", "failures", "runs")


def display_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def delegated_summary(delegated_runs: dict[str, dict[str, Any]]) -> str:
    if not delegated_runs:
        return "no delegated runs"
    parts = []
    for engine in sorted(delegated_runs):
        row = delegated_runs[engine]
        qa_pass = row["qa_pass"]
        # No QA claim is made unless a pass is recorded; a zero here means
        # "not yet QA'd in the ledger", which is not the same as "failed QA".
        if qa_pass:
            parts.append(
                f"{engine}: {display_number(row['runs'])} runs "
                f"({display_number(qa_pass)} passed cross-family QA)"
            )
        else:
            parts.append(f"{engine}: {display_number(row['runs'])} runs")
    return "; ".join(parts)


def choose_failure(stories: list[dict[str, str]]) -> dict[str, str]:
    """Prefer the ledger's explicitly OPEN recurring failure, then any open story."""
    explicit_open = [story for story in stories if story["status"].startswith("OPEN")]
    if explicit_open:
        return explicit_open[0]
    open_stories = [story for story in stories if story["status"].casefold().startswith("open")]
    if open_stories:
        return open_stories[0]
    return stories[0]


def daily_page(
    day: str,
    meta: dict[str, Any],
    heartbeats: dict[str, Any],
    receipt: dict[str, Any],
    stories: list[dict[str, str]],
) -> str:
    is_live = day == meta["live_day_1"]
    label = "day 1 (live) — partial" if is_live else "backfill"
    attention = (
        "Attention cost was not tracked for this reconstructed backfill; tracking starts with live day 1."
        if not is_live
        else "Attention cost was not tracked; tracking starts with this live day 1."
    )
    emits = display_number(receipt["attention_gate_emits"])
    emit_note = (
        "the gate suppressed everything below threshold"
        if receipt["attention_gate_emits"] == 0
        else "emits recorded"
    )
    failure = choose_failure(stories)
    lesson_clause = f" Lesson: {failure['lesson']}." if failure["lesson"] else ""

    lines = [
        f"# {day} — {label}",
        "",
        "[Back to the operating record](../README.md)",
        "",
        (
            "**Value.** "
            f"{display_number(receipt['job_fires'])} job fires; "
            f"{display_number(receipt['failed_fires'])} failed fires; "
            f"{display_number(receipt['compute_minutes'])} compute-minutes; "
            f"{display_number(receipt['capture_ingest_runs'])} capture-ingest runs; "
            f"{emits} attention-gate emits ({emit_note}); "
            f"delegated runs: {delegated_summary(receipt['delegated_runs'])}."
        ),
        "",
        (
            "**Failure of the day.** "
            f"**{failure['system']}** — {failure['what']} "
            f"Status: {failure['status']}.{lesson_clause}"
        ),
        "",
        f"**Attention cost.** {attention}",
        "",
        (
            "**Evidence.** "
            "[value receipts](../fixtures/value_receipts.json) "
            "(value and attention lines); "
            "[failure ledger](../fixtures/failures_7d.json) (failure line); "
            "[heartbeats](../fixtures/heartbeats_7d.json) (table)."
        ),
        "",
        "## Per-system heartbeat",
        "",
        "| System | Runs | Failures | Compute-min |",
        "| --- | ---: | ---: | ---: |",
    ]
    for system in sorted(heartbeats):
        row = heartbeats[system]["days"].get(day)
        if row is None:
            lines.append(f"| {system} | absent | absent | absent |")
        else:
            lines.append(
                f"| {system} | {display_number(row['runs'])} | "
                f"{display_number(row['failures'])} | {display_number(row['compute_min'])} |"
            )
    return "\n".join(lines) + "\n"


def readme(meta: dict[str, Any], days: list[str]) -> str:
    links = []
    for day in days:
        label = "day 1 (live) — partial" if day == meta["live_day_1"] else "backfill"
        links.append(f"- [{day} — {label}](log/{day}.md)")
    return "\n".join(
        [
            "# Public operating record",
            "",
            "This is a real fleet's public daily record.",
            "",
            "It says what worked, what failed, and what still needs fixing.",
            "",
            (
                f"**Where this record starts.** This log went live on {meta['live_day_1']} — that is day 1. "
                "To show what a normal week looks like, the seven days before launch were rebuilt from the "
                "fleet's own internal records (every scheduled run already writes a row when it fires). "
                'Those rebuilt days are marked "backfill" so nothing pretends to be older than it is.'
            ),
            "",
            (
                "**This week, plainly.** The best story is a failure: one system, the equity research desk, refused "
                "to run for five straight days — on purpose. Its pre-run check found its own code out of date and "
                "stopped, every time, rather than run stale logic. One fix on 2026-08-08, and on 2026-08-09 it ran "
                "16 times without a failure."
            ),
            "",
            (
                "Two things are still broken, and they stay on this page until fixed: the daily health check is "
                "failing on purpose because 4 of the agents it audits are unhealthy, and one dashboard-refresh job "
                "failed all 7 of its runs this week — it is top of next week's fix list. "
                "Attention cost (human minutes spent) was not tracked for the rebuilt days; tracking starts with day 1. "
                "[Failure ledger](fixtures/failures_7d.json) · "
                "[Heartbeats](fixtures/heartbeats_7d.json)"
            ),
            "",
            "## What it costs to run",
            "",
            meta["cost_note"],
            "",
            "## What is and is not shown",
            "",
            (
                "The public record is allowlisted: only systems named in the companion fixtures can appear. "
                "No dollar amounts, holdings, employer or client names, personal names, or machine names appear. "
                "[Redaction policy](fixtures/META.json)"
            ),
            "",
            "## How to read this",
            "",
            "Each daily page has one line for what happened, one failure story, an attention-cost note, evidence links, and a small heartbeat table. A missing heartbeat is written as absent, not zero.",
            "",
            *links,
            "",
            "## Cadence",
            "",
            "Updates are manual each day first. Automation begins only after 3 clean manual days.",
            "",
            "## Source record",
            "",
            f"{meta['reconstructed_note']} [Metadata](fixtures/META.json)",
            "",
        ]
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    meta = load_fixture("META.json")
    heartbeats = load_fixture("heartbeats_7d.json")
    receipts = load_fixture("value_receipts.json")
    failures = load_fixture("failures_7d.json")
    if not all(isinstance(item, dict) for item in (meta, heartbeats, receipts, failures)):
        raise TypeError("Every fixture root must be an object")
    if not isinstance(meta.get("window"), dict):
        raise TypeError("Fixture key window must be an object")
    days = days_in_window(meta["window"])
    validate(meta, heartbeats, receipts, failures, days)

    write(ROOT / "README.md", readme(meta, days))
    for day in days:
        write(
            LOG / f"{day}.md",
            daily_page(day, meta, heartbeats, receipts[day], failures[day]),
        )


if __name__ == "__main__":
    main()
