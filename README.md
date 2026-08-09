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
