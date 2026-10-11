# REF-004c / D099 paired history: prelaunch handoff

2026-09-15. [D098 preparation closeout](REF004C_HISTORY_PREPARATION_CLOSEOUT.md)
passes. The user requested steps 1 and 2, then step 3 detached. This implements
steps **2 → 3 as one reference-gated detached workflow**: either simulator starts
only after the actual paired references pass. This handoff is not their result.

## Registered scope

The [contract](../docs/BETSE_CHANNEL_HISTORY_PILOT.md) and
[protocol](../validation/betse/channel_history_pilot/protocol.json) fix two initial
settings, a=(0.2, 0.6), b=(0.6, 0.2), with active and blocked controls. Reuse the
seven-cell / thirty-face, finite-shared-bath Kv1p5 fixture at 298.15 K and matched
constants. No new physiology, intervention, geometry, production code or GPU work.

- **Reference gate:** twelve fresh solves, base/tight DOP853 and Radau for each
  condition. Retain original convergence/domain/thermodynamic budgets. The
  proposed 2 ms duration is selected only if active final voltage separation
  reaches 100 microvolts and open-fraction separation reaches 0.005 in every
  cell. Blocked voltage remains identical. A failed gate stops the workflow.
- **Conditional coupled capture:** 24 native runs / 4,480 updates, 16 complete
  Cells trajectories and four checkpoint-resumed segments. Preserve all twelve
  observer pairs and 24 complete checkpoints / 1,296 arrays. Both engines evolve
  their own state, at three separately refined timesteps.
- **Comparison:** complete accounting, reference agreement, refinement,
  eager/JIT and restart checks, plus signed a-minus-b contrasts. Original
  single-trajectory criteria remain unchanged; contrast budgets propagate the
  errors of two trajectories. Coarse diagnostic failures remain failures.

The independent reference uses float64 integration with an 80-digit RHS in the
existing pinned SciPy runtime; its two algorithms are not independent libraries.
Saved reference reconstruction uses separately audited mathematics. Hash-bound
gate receipts are verified before each simulator and at completion. New native
initial-state expectations are declared fixture views, not rewritten old data.

## Software evidence and preservation

- Attempt 01: **46 passed in 12.99 seconds**, SHA-256
  `e1b6993b9b22a4640af4fb8cdcd322774e62515b284cbf54e55f9e3220aa87e9`.
- Attempt 02: **56 passed in 22.96 seconds**, SHA-256
  `f75c511b6ada481f7a19a3ec19a59a1c5c02666601957c28bc4999e66e32e65f`.
  [Final XML](ref-004c-paired-pilot-checks-02.xml) includes explicit initial
  histories, reference method/dense/domain checks, numerical and metadata
  corruption, gate sequencing/hash tampering, both real eager/JIT histories
  and complete short checkpoint resumes.
- Software reference fixtures integrate only a synthetic two-cell, 100-microsecond
  problem. Actual production tests run two 50-microsecond steps. Neither is the
  prospective full 2 ms experiment or its reference qualification.
- Read-only authentication confirms D098's four-file review and 132 source
  inputs, D097's unchanged preparation, earlier audit/capture evidence and all
  **352 accepted implementation files / 51 production modules**.
- The new capsule has **143 inputs**: 132 preserved plus eleven new protocol,
  adapter, test and contract inputs. Register the passing XML and exact parameter
  views before execution. Freeze these inputs after registration; do not repair
  a completed/failed run in place.

No full production regression or prior numerical integration is rerun. Repository
quality checks are recorded in the current progress log before launch.

## Detached execution

CPUs 0–3, **1,200 seconds total**; worker caps **240 seconds reference / 360
seconds native / 480 seconds Cells**. Artifact limits are **512 MiB aggregate /
128 MiB per file**, not RAM caps. Existing per-definition step/trace limits remain.

Launch once from the Cells root into the absent output directory:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  validation/betse/channel_history_pilot/paired_job.py launch \
  runs/ref-004c-paired-history-2026-09-15/capture-01 \
  --tests reports/ref-004c-paired-pilot-checks-02.xml
```

`launch.json` records the PID and registration hash. Worker-start receipts,
`reference-gate.json`, durable logs, and `completion.json` or `failure.json`
establish actual execution state. The launcher returns without waiting for the
controller. No assistant polling, automatic retry or automatic post-capture
audit/regression follows. The user requests status and further work.

A successful capture still says `paired_capture_pass_pending_audit`. Independent
saved-data closeout is separate. No biological, long-time, channel-family,
native-restart, GPU or organ-scale qualification is implied.
