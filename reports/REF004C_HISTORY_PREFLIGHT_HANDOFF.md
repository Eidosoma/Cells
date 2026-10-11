# REF-004c / D097 history preparation: prelaunch handoff

2026-09-15. Software checks and source authentication pass before one detached
preparation. This handoff is **not its numerical completion receipt**.

## Scope

Four data definitions: active/blocked × m/h=0.2/0.6 or 0.6/0.2, with identical
non-gate inputs within each pair. Twelve actual production initial-RHS probes
(NumPy/eager/JIT), twelve candidate grid/resource checks, and six fresh isolated
native gate-vector updates (42 scalar-channel updates). No new coupled native/
Cells trajectory, native tissue preparation, continuous integration, checkpoint,
production change, release promotion, GPU or biological qualification.

The [contract](../docs/BETSE_CHANNEL_HISTORY_PREFLIGHT.md) and
[plan](../validation/betse/channel_history_preflight/plan.json) fix the acceptance
criteria. The local opening/curvature witness is not a 2 ms trajectory prediction.
Future reduced-state/GPU work must retain or explicitly approximate relevant
history, while connected cells retain one shared-bath reduction.

## Software evidence

- Attempt 01: **44 passed in 1.87 s**; NumPy full-state/RHS and synthetic native
  comparator fixtures. SHA-256
  `f57728b00b8967b317bd19f5c27a3370ce52341406d7fd9a12cce00e8459a559`.
- Attempt 02: **49 passed in 7.50 s**; adds actual eager/JIT initial-rate checks,
  forbidden runner calls, extra array-axis and false-count rejection. Explicit
  time-constant units, exact padding and complete voltage/readout axes are
  checked. SHA-256
  `0b2ac9550a187a1190dfd26dc1d89e6a1ced9c3ba33732bd83277617b9515827`.
- Native rows used by software comparator tests are labelled synthetic. Actual
  native execution belongs to the separate registered worker, not these tests.
- Repository lint, formatting (631 Python files) and whitespace checks pass.
  No full production regression or original numerical integration was rerun.

## Frozen inputs and resources

Read-only authentication confirms D096's nine-file closeout, all 284 original
D095 capture files, original test/source/runtime identities and unchanged
accepted production. D096 completion SHA-256:
`61e700cbddda5141f92443ba684bf344d14d09e1b3c9db12110d1a0a923a28b9`.
All fourteen original coarse misses remain. The [closeout report](REF004B_FEEDBACK_CLOSEOUT.md)
records that completed milestone without rewriting old receipts.

The new source capsule has **130 inputs** (122 previously frozen + eight new).
Registration additionally binds the passing 49-test receipt and exact generated
definitions. After registration, do not edit these source inputs; any correction
requires a new explicitly versioned attempt.

One detached preparation, CPUs 0–3: **240 seconds total, 90 seconds per worker,
64 MiB aggregate artifacts, 32 MiB per file**. Candidate 64 MiB trace reservations
are separate from these artifact caps; neither is a RAM measurement. Separate
native/Cells subprocesses use the pinned runtime and exact numerical environment.
The controller performs model-free comparisons and final provenance checks.

Launch once, from the Cells root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  validation/betse/channel_history_preflight/history_job.py launch \
  runs/ref-004c-history-preflight-2026-09-15/capture-01 \
  --tests reports/ref-004c-history-preflight-checks-02.xml
```

`launch.json`, durable logs, and `completion.json` or `failure.json` establish
actual execution state. A successful result remains
`history_preflight_pass_pending_review`, not coupled-history qualification.
Return after launch without polling, retry or automatic audit/trajectory work.
The user requests status and subsequent steps.
