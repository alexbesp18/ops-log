# Public operating record

This is a real fleet's public daily record.

It says what worked, what failed, and what still needs fixing.

**Where this record starts.** This log went live on 2026-08-09 — that is day 1. To show what a normal week looks like, the seven days before launch were rebuilt from the fleet's own internal records (every scheduled run already writes a row when it fires). Those rebuilt days are marked "backfill" so nothing pretends to be older than it is.

**This week, plainly.** The best story is a failure: one system, the equity research desk, refused to run for five straight days — on purpose. Its pre-run check found its own code out of date and stopped, every time, rather than run stale logic. One fix on 2026-08-08, and on 2026-08-09 it ran 16 times without a failure.

Two things are still broken, and they stay on this page until fixed: the daily health check is failing on purpose because 4 of the agents it audits are unhealthy, and one dashboard-refresh job failed all 7 of its runs this week — it is top of next week's fix list. Attention cost (human minutes spent) was not tracked for the rebuilt days; tracking starts with day 1. [Failure ledger](fixtures/failures_7d.json) · [Heartbeats](fixtures/heartbeats_7d.json)

## What it costs to run

The fleet runs on fixed-price subscriptions for agent labor plus two always-on Macs; per-run marginal cost is ~zero. Exact per-day dollar metering is not yet wired to this log - it lands with the automation decision. Until then this log reports compute-minutes and delegated-run counts, which are measured, never estimated.

## What is and is not shown

The public record is allowlisted: only systems named in the companion fixtures can appear. No dollar amounts, holdings, employer or client names, personal names, or machine names appear. [Redaction policy](fixtures/META.json)

## The delegation ledger

The delegation wrappers write a row for each task they run: which engine took it, what happened,
and roughly when. Nothing edits it by hand and it is still being written to today. It records what
went through the wrappers, which is not the same as proving every delegated task everywhere was
captured.

| | |
|---|---|
| **Runs** | **717** |
| **Window** | 2026-07 → 2026-08 |
| **By month** | 2026-07 — 454 runs · 2026-08 — 263 runs |
| **Engines** | codex 258 · grok 455 · kimi 2 · sol+kimi 1 · workflow-fable 1 |
| **Families behind those labels** | OpenAI/Codex (codex, sol) · xAI/Grok (grok) · Moonshot/Kimi (kimi) · Anthropic/Claude (workflow-fable) |
| **Outcomes** | fail 38 · hung-retaken 1 · noop 1 · ok 677 |
| **Failure rate** | **5.3%** |

### What this file deliberately does not contain

Per-run timestamps are withheld. Rows carry a month, never a date or a clock time.

A run-level time series says more about when one person happens to work than about the work
itself, and that is not what this record is for. The exporter enforces it rather than trusting
anyone to remember: any date or clock time surviving into the output aborts the write, and four
tests pin that behaviour. Dates that appeared inside task labels are stripped from the label too.

The month is kept so the window stays checkable and so the record visibly accrues from here.

### Review annotations, stated plainly

**24 of 710 rows carry a per-run review annotation — 3.4% annotation coverage.**

Read that as what it is. It measures how often this field was filled in, not how often a review
happened. A blank field cannot prove a review took place and cannot prove one did not. High-stakes
work goes to a different model family on held branches, but until annotation began this ledger did
not record it, so **historical review coverage is not provable from this file.**

The number is published rather than backfilled. Per-run annotation starts now, so the figure above
moves on its own from here. Watch it move rather than take the claim.

### What is redacted, and what that costs

1 task string was replaced with a redaction marker under the allowlist policy.
The row itself stays — the count, the engine, the outcome, and the timestamp are all still there.
Nothing is deleted to make the record look better.

### Reproduce it

The exporter is the only path from the private ledger to this file, and it fails closed. A missing
or empty denylist aborts the run. A banned term that survives sanitization aborts the write.

```bash
python3 tools/export_ledger.py --ledger <private-ledger> --denylist <denylist>
python3 -m unittest discover -s tools -p 'test_*.py'
```

[Ledger rows](fixtures/delegation_ledger.jsonl) · [Computed summary](fixtures/delegation_summary.json)

## How to read this

Each daily page has one line for what happened, one failure story, an attention-cost note, evidence links, and a small heartbeat table. A missing heartbeat is written as absent, not zero.

- [2026-08-03 — backfill](log/2026-08-03.md)
- [2026-08-04 — backfill](log/2026-08-04.md)
- [2026-08-05 — backfill](log/2026-08-05.md)
- [2026-08-06 — backfill](log/2026-08-06.md)
- [2026-08-07 — backfill](log/2026-08-07.md)
- [2026-08-08 — backfill](log/2026-08-08.md)
- [2026-08-09 — day 1 (live) — partial](log/2026-08-09.md)

## Cadence

Updates are manual each day first. Automation begins only after 3 clean manual days.

## Source record

This 7-day sample is reconstructed from the fleet's own ledgers (heartbeat rows, delegation ledger, attention-gate ledger). It was assembled on 2026-08-09 - the log's first live day. Backfill is labeled as backfill. [Metadata](fixtures/META.json)
