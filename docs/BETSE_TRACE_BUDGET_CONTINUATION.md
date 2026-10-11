# REF-003e1 trace-budget continuation

2026-09-13, D085. Resource-only continuation of D084, not a new scientific
panel. The user authorized a sensible budget increase and continuation.
See the [handoff](../reports/REF003E1_TRACE_RESUME_HANDOFF.md) and
[registered scope](../validation/betse/response_resume/trace_resume_plan.json).
The original [response contract](BETSE_REFINED_RESPONSE_PANEL.md), sources,
criteria and failed attempt remain frozen.

## Why the attempt stopped

D084 completed all 16 native runs and 26 of 48 Cells runs, then stopped after
1830.727 s. The next row, 6.25 µs baseline / eager / subdivision 4, was rejected
by the production timeline's trace-storage guard before integration:
`Estimated trace working storage exceeds max_trace_bytes`.

This was a configured 16 MiB array-reservation limit, not a measured out-of-memory
event. The largest registered reservation is 25,838,496 bytes (24.6415 MiB).
32 MiB would fit; select 64 MiB for headroom. Change only the eight previously
unexecuted 640-step definitions: four conditions × eager/JIT at the 6.25 µs
hold and subdivision 4. Their only changed field is
`execution.max_trace_bytes`, from 16,777,216 to 67,108,864. All other definitions
retain 16 MiB, including every reused Cells result's exact original definition.

No equations, constants, input tables, timesteps, observations, solver/backend
choices, tolerances, production sources or prior adapters change. Trace
reservation, total process RAM and serialized artifact size are distinct
budgets. This amendment makes no peak-RAM or GPU-memory measurement.

## Reuse without rewriting evidence

Authenticate all 241 files in the failed attempt, including its 237 manifested
payloads, three operational files and final failure receipt. Keep the original
registration, 106-input source capsule, native worker receipt, row-start records,
26 completed Cells payloads and both failure records unchanged. Bind their hashes
in the [preservation receipt](../reports/ref-003e1-trace-resume-preservation.json).

The new comparison reads reused data directly from that original directory;
it neither copies nor relabels it as new execution. There is no original
aggregate `cells.json` because the worker failed. Do not invent one, a clean
aggregate warning record, or a completed old-worker runtime receipt. Provenance
instead comes from the original frozen registration, failure manifest, started
rows and complete per-row payloads.

All 16 native runs and 26 completed Cells runs pass 666,108 frozen internal
law/accounting checks, with zero failures and maximum normalized error
0.18106284912210208. Native observer pairs and six available Cells
baseline/zero-amplitude pairs also pass. This read-only reuse check is not a new
independent audit or cross-engine response qualification.

Execute only the remaining 22 Cells rows, in their original order. They contain
8480 accepted steps: 4000 eager and 4480 JIT. No native integration is rerun.
The separate frozen coarse panel still supplies its eight native / 24 Cells
runs to the unchanged full comparison.

## Preflight and execution boundaries

Before launch, call the actual production parser/timeline/resource guard on all
48 amended definitions, not just the first row or an arithmetic estimate.
Check nominal and event-split grids, observations and trace reservations. All
48 pass; precisely eight original definitions reproduce the expected storage
rejection. No integration runs in this probe. The Cells worker repeats this
all-row check before its first new rollout.

The continuation has five new Python modules and one plan under
`validation/betse/response_resume/`. Its 112-input capsule preserves D084's
106 inputs and the older flat 88-source inventory. The 1013-file pre-edit
baseline permits only the seven established mutable status documents to change;
all 352 accepted implementation files / 51 production modules remain unchanged.

All 47 focused tests pass in 22.88 s, including one-field scope limits,
corrupted resource/reuse receipts, exact old/new path routing, coverage,
preflight-before-rollout ordering, detached launch and timeout preservation.
Routing mocks are software checks, not new simulation evidence. All 380 Python
files pass whole-tree lint/format checks. D084's passing 114-test software
completion stays frozen and is authenticated, not rerun.

## Prospective resource limits

| Resource | Continuation limit or estimate |
| --- | --- |
| Trace reservation | 64 MiB for eight 640-step definitions; 16 MiB for the other 40 |
| Execution | CPU 0–3, float64, single-thread numerical libraries; 22 new Cells runs |
| Stage deadlines | Cells 6600 s; saved-data comparison 300 s |
| Total deadline | 7200 s (two hours), including validation and closeout |
| Combined artifacts | 1 GiB across retained failed attempt plus new continuation |
| Individual worker file | OS-enforced 64 MiB |
| Retained bytes | 246,326,549 |
| Estimated combined bytes, with allowances | 502,363,957 |
| Estimated largest worker file, with allowance | 16,791,168 bytes |
| Estimated Cells time, with allowances | 5295 s (88 min 15 s) |

The time estimate uses the slowest measured D084 eager/JIT per-step costs,
applied only to the remaining steps, with a 1.5 multiplier and 120 s allowance.
It is a planning estimate, not an ETA guarantee. Artifact estimates use retained
per-step export sizes, a 1.5 multiplier and 32 MiB aggregate allowance. Aggregate
checks between rows/stages are not a filesystem quota or total-RAM limit.

## Unchanged verdict and handoff

Use the frozen comparison arithmetic for all 2,494,936 checks, including
2,298,936 required checks and 132 surface scopes. Preserve the original 150
coarse failures exactly. Require internal, fixed-input solver and backend
checks at every hold and cross-engine checks at the finest hold. Continue to
report coarse/intermediate and across-hold discrepancies separately. Reusing
old results does not reduce the declared numerical comparison surface.

Native integration and input resampling remain coupled across hold refinements;
do not call that isolated solver convergence. Native terminal rates are still
not invented. Capture alone does not qualify trajectory correspondence, native
or forcing convergence, biology, organs, restart or GPU execution.

Fresh destination: `runs/ref-003e1-trace-resume-2026-09-13/capture-01`.
Only its actual launch/capture/failure receipts determine execution state.
Launch once detached with durable logs and per-row results, then return without
polling. No automatic retry, expansion, independent audit or regression follows.
Review actual results on the user's next instruction.

For future multiscale work, retain this engineering lesson: preflight resource
needs over the complete declared workload, including the finest integration
grid, while keeping memory policy separate from model physics. Streaming and
GPU memory measurements remain separate future work, not prerequisites for
this small resource correction.
