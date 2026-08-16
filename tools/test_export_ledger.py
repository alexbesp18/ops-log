"""The export gate must fail closed. These tests try to make it fail open."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import export_ledger as E


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


ROW = '{"ts":"2026-08-01T10:00:00Z","engine":"codex","outcome":"ok","qa":"unreviewed","task":"%s"}'


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.deny = write(self.dir / "deny.txt", "acmecorp\n# comment\nWidgetCo\n")
        self.ledger = write(
            self.dir / "l.jsonl",
            "\n".join(
                [
                    ROW % "routine sweep",
                    ROW % "acmecorp lane fill",
                    ROW % "build exporter",
                ]
            ),
        )

    # --- the gate itself ---

    def test_missing_denylist_is_broken_not_a_pass(self) -> None:
        with self.assertRaises(E.GateBroken):
            E.load_denylist(None)
        with self.assertRaises(E.GateBroken):
            E.load_denylist(self.dir / "nope.txt")

    def test_empty_denylist_is_broken_not_a_pass(self) -> None:
        empty = write(self.dir / "empty.txt", "# only comments\n\n")
        with self.assertRaises(E.GateBroken):
            E.load_denylist(empty)

    def test_cli_returns_nonzero_when_gate_is_broken(self) -> None:
        code = E.main(["--ledger", str(self.ledger), "--out-dir", str(self.dir / "o")])
        self.assertEqual(code, 2)
        self.assertFalse((self.dir / "o" / "delegation_ledger.jsonl").exists())

    # --- sanitization ---

    def test_banned_task_is_redacted_and_counted(self) -> None:
        rows = E.read_ledger(self.ledger)
        clean, redacted = E.sanitize(rows, E.load_denylist(self.deny))
        self.assertEqual(redacted, 1)
        self.assertEqual(sum(1 for r in clean if r["task"] == E.REDACTED), 1)
        self.assertNotIn("acmecorp", json.dumps(clean).lower())

    def test_redaction_is_case_insensitive(self) -> None:
        led = write(self.dir / "c.jsonl", ROW % "AcMeCorp migration")
        clean, redacted = E.sanitize(E.read_ledger(led), E.load_denylist(self.deny))
        self.assertEqual(redacted, 1)

    def test_short_terms_match_whole_words_only(self) -> None:
        deny = write(self.dir / "short.txt", "ate\n")
        # "operate" must not trip a 3-letter term, or every export is all-redacted noise
        self.assertEqual(E.find_banned("operate the fleet", E.load_denylist(deny)), [])
        self.assertEqual(E.find_banned("ate lunch", E.load_denylist(deny)), ["ate"])

    def test_verify_clean_aborts_if_a_term_survives(self) -> None:
        with self.assertRaises(E.GateBroken):
            E.verify_clean(
                [{"task": "acmecorp still here"}], E.load_denylist(self.deny)
            )

    # --- input integrity ---

    def test_malformed_json_line_stops_the_export(self) -> None:
        bad = write(self.dir / "bad.jsonl", (ROW % "fine") + "\n{not json}")
        with self.assertRaises(E.GateBroken):
            E.read_ledger(bad)

    def test_row_missing_a_required_key_stops_the_export(self) -> None:
        bad = write(
            self.dir / "miss.jsonl", '{"ts":"2026-08-01T10:00:00Z","engine":"codex"}'
        )
        with self.assertRaises(E.GateBroken):
            E.read_ledger(bad)

    def test_empty_ledger_is_refused(self) -> None:
        with self.assertRaises(E.GateBroken):
            E.read_ledger(write(self.dir / "e.jsonl", "\n\n"))

    # --- summary honesty ---

    def test_summary_reports_the_qa_gap_rather_than_hiding_it(self) -> None:
        rows = [
            {
                "month": "2026-08",
                "engine": "grok",
                "outcome": "ok",
                "qa": "unreviewed",
                "task": "a",
            },
            {
                "month": "2026-09",
                "engine": "codex",
                "outcome": "fail",
                "qa": "behavior-reviewed",
                "task": "b",
            },
        ]
        s = E.summarize(rows, redacted=0)
        self.assertEqual(s["qa"]["annotated"], 1)
        self.assertEqual(s["qa"]["unannotated"], 1)
        self.assertEqual(s["qa"]["coverage_pct"], 50.0)
        self.assertEqual(s["failure_rate_pct"], 50.0)
        self.assertEqual(s["window"]["months_covered"], 2)

    def test_redaction_count_appears_in_the_summary(self) -> None:
        rows = E.read_ledger(self.ledger)
        clean, redacted = E.sanitize(rows, E.load_denylist(self.deny))
        self.assertEqual(E.summarize(clean, redacted)["redacted_tasks"], 1)

    def test_end_to_end_export_writes_both_files(self) -> None:
        out = self.dir / "out"
        code = E.main(
            [
                "--ledger",
                str(self.ledger),
                "--denylist",
                str(self.deny),
                "--out-dir",
                str(out),
            ]
        )
        self.assertEqual(code, 0)
        lines = (out / "delegation_ledger.jsonl").read_text().strip().splitlines()
        self.assertEqual(len(lines), 3)
        summary = json.loads((out / "delegation_summary.json").read_text())
        self.assertEqual(summary["rows"], 3)
        self.assertNotIn(
            "acmecorp", (out / "delegation_ledger.jsonl").read_text().lower()
        )


class TimestampWithholdingTests(unittest.TestCase):
    """The public file must never carry a per-run timestamp."""

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.deny = write(self.dir / "d.txt", "acmecorp\n")

    def test_row_timestamps_are_replaced_by_month(self) -> None:
        led = write(self.dir / "l.jsonl", ROW % "routine sweep")
        clean, _ = E.sanitize(E.read_ledger(led), E.load_denylist(self.deny))
        self.assertNotIn("ts", clean[0])
        self.assertEqual(clean[0]["month"], "2026-08")

    def test_a_leaked_timestamp_aborts_the_write(self) -> None:
        with self.assertRaises(E.GateBroken):
            E.verify_no_timestamps([{"month": "2026-08", "task": "ran at 2026-08-01T10:00:00Z"}])
        with self.assertRaises(E.GateBroken):
            E.verify_no_timestamps([{"month": "2026-08", "ts": "2026-08-01T10:00:00Z"}])

    def test_clock_times_are_caught_too(self) -> None:
        with self.assertRaises(E.GateBroken):
            E.verify_no_timestamps([{"month": "2026-08", "task": "kicked off 15:26"}])

    def test_month_itself_is_allowed(self) -> None:
        E.verify_no_timestamps([{"month": "2026-08", "engine": "codex", "task": "sweep"}])

    # --- home-directory fragments never reach the public file ---

    def test_home_dir_fragments_are_scrubbed_from_task_and_qa(self) -> None:
        rows = [
            {"ts": "2026-08-01T10:00:00Z", "engine": "grok", "outcome": "fail",
             "qa": "read /Users/somebody/notes", "task": "22650w:--cwd-Userssomebody"},
        ]
        clean, _ = E.sanitize(rows, ["acmecorp"])
        self.assertNotIn("somebody", clean[0]["task"])
        self.assertNotIn("somebody", clean[0]["qa"])
        self.assertIn("~", clean[0]["task"])

    def test_a_surviving_home_dir_fragment_aborts_the_write(self) -> None:
        with self.assertRaises(E.GateBroken):
            E.verify_no_home_paths([{"month": "2026-08", "engine": "grok", "outcome": "ok",
                                     "qa": "unreviewed", "task": "cwd-Userssomebody"}])
        E.verify_no_home_paths([{"month": "2026-08", "engine": "grok", "outcome": "ok",
                                 "qa": "unreviewed", "task": "workspace-users-table"}])


if __name__ == "__main__":
    unittest.main()
