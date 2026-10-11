# CORE-010 recorded production acceptance, v1

Prospective plan, 2026-09-11. This is an engineering gate for the passive
`spatial_extracellular@1` family, not biological validation or a stable-release
claim. The existing 0.15.0.dev0 equations, shared engine and artifact formats
remain unchanged. The pre-work [baseline](../reports/core-010-acceptance-workspace-baseline.json)
authenticates the completed development build and all 707 existing worktree files.

## Frozen scientific scope

Use all fourteen NUM-010 v1 definitions, controls, horizons, observations and
accounting/trajectory tolerances unchanged. Read the authenticated refined Radau
records; do not rerun, fit or alter the reference. Run CPU float64 RK4 at
0.000125 s, with a compiled refinement at 0.0000625 s for every case. Domain
failures, incomplete paths and budget stops fail the session; retain outputs
and require a separately documented correction before a new attempt.

Capture each complete compiled, eager and refined trajectory, and resume all
fourteen compiled runs from their saved midpoint in a fresh process. Scalar
restarts must reproduce all native/observed arrays and geometry byte-for-byte.
Eager/compiled and scalar/cohort comparisons use the inherited trajectory limits
multiplied by 0.001 for every physical coordinate and potential; both paths must
also separately pass the full independent checks.

Future-control branches use `membrane_block_release` at its 0.0713 s boundary.
One parent stops at that time with the terminal availability changed to one;
branching back to the frozen target must reproduce the normal blocked/released
suffix, preserving nonzero transfer and dissipated-energy history. The terminal
control has no arrival-state impulse. Past-control edits remain forbidden.

Record scalar windows (width 128) and windowed cohort runs (width 128, or 32 for
the short mesh group) for these
groups; resume their first saved cohort boundary in a fresh process using width
73. Save every fourth cohort boundary to bound checkpoint overhead, including
complete initial and final snapshots. Independent worlds have their original,
different horizons and event clocks, not one shared event schedule.

| Group | Cases | Shared padded capacities: cells / membranes / outside / faces |
| --- | --- | --- |
| membrane | single_outside, two_cells_chain, membrane_block_release, membrane_short_pulse, pure_bulk | 3 / 4 / 4 / 4 |
| mesh | line_8, line_16, line_32 | 1 / 2 / 33 / 32 |
| ternary | ternary_loop | 2 / 3 / 4 / 4 |
| divalent | divalent | 2 / 3 / 3 / 2 |

The ordinary scalar panel uses these same capacities for grouped cases, and
the fixture's existing default padding for remaining cases. Four scalar window
runs use `membrane_block_release`, `line_32`, `ternary_loop` and `divalent`.
Different batching/window boundaries may change floating-point reduction order;
never relabel tolerance comparisons as bitwise replay. Every chunk and saved
checkpoint must match its own recorded world trajectory exactly.

## Independent saved-data gate

Authenticate exact manifest/payload/source sets, schema, dtypes, shapes, owner
padding, resolved configuration and complete checkpoint clocks/state/layout.
Reject duplicate archive members, nonfinite arrays, unexpected files, escaping
paths, symbolic links and multiply-linked evidence. Numerical corruption tests
update file checksums deliberately: a checksum alone is not a scientific check.

At all native and observation rows compare every state coordinate and physical
potential to the saved refined reference. Independently recompute all 26 physical
readouts from inventory, geometry and held controls, including membrane/face
fluxes, current, material, component charge and once-owned energy. Also recompute
the residual/normalization dependency from the recorded face currents, so harmless
roundoff in two independent field solves is not confused with corrupted diagnostics.
Independent current comparisons propagate the per-species flux comparison error
through the charge-weighted sum and owner incidence; a relative error on an almost
zero sum would be inappropriate. The saved current/flux/residual dependency is
checked separately at 1e-30 A absolute plus 3e-12 relative tolerance, and its
normalized value at 1e-12 absolute plus 3e-12 relative. The inherited physical
current-continuity limit is unchanged. Public charge/current readouts use outside
owner order, not the reference evaluator's capacitance-component column order.

Reconstruct each incoming-control Hermite polynomial from saved endpoints and
independent instantaneous equations. Check sampled state and whole-polynomial
inventory, voltage and component-charge bounds, including exact blocked histories.
This is data replay and instantaneous equation evaluation: no ODE trajectory solve
and no production RHS/observer as an oracle. It does not prove the nonlinear
current constraint throughout an unsampled cubic interior or reconstruct hidden
RK4 trial evidence that the current artifact format does not save.
The normal complete-checkpoint loader still executes its production-domain
preflight; that compatibility check is separate from the independent oracle.

Re-audit preserved NUM-010 under its original 0.14.0 context. Authenticate all
accepted CORE-009 payloads and load every accepted old scalar/cohort checkpoint
under the preserved source capsule, with one exact archived spatial-predecessor
replay. Current sources must refuse implicit migration. Replay earlier accepted
families against their frozen arrays under the current engine as explicit test
fixtures, not checkpoint migrations.

## Resource and release boundaries

The formal session registers the entire implementation/protocol/definition
capsule before work, with a 3600 s wall limit and 2 GiB artifact limit. Use CPU
affinity 0–3, four single-CPU eager lanes and single-thread BLAS/OpenMP; compiled
work may share those CPUs. Child failures terminate this session's children only.
No automatic retry, parameter tuning, reference integration or GPU benchmarking.

Preflight fixtures are explicitly shorter engineering checks, not full-panel
acceptance. After the formal capture, a separate read-only audit and the complete
current plus five historical regression contexts must pass with the same source
identity. Until that closeout, CORE-010 and stable-version promotion remain open;
0.14.0 remains the accepted stable production baseline.
