# Long fixed-graph reference paths

NUM-005c1 / D033. This is independent reference infrastructure, not production
graph support, a selected RK4 step, or a validated biological switching assay.
The [frozen numerical plan](E02_SWITCHING_NUMERICS.md) is unchanged.

## Scope and immutable inputs

Load the exact [NUM-005b](SOURCE_PREPARATION_REFERENCE.md) refined prepared E/M
packets, with pinned packet, qualification, verification and independent audit
hashes. Preserve their full preparation histories in provenance. Each new assay
copies primary state and fixed context exactly; its own ledgers start at zero.
This is an explicit state import, not a restart of the preparation solver.

Register all 14 E02-SW1 conditions and their three implicit settings before any
1000-unit run. Follow frozen direction/condition order, running Radau, BDF and
refined Radau sequentially for each condition; compare that complete trio before
proceeding. All donors evolve freely, local terms occur once per cell, and the
same runner handles zero, one and two edges. No phenotype feeds back into it.

The previous numerical sources remain unchanged and archived. A new recording
layer reuses their graph equations, bounded Jacobian stencils, dense coefficient
adapter and full-curve domain/accounting checks. Short tests require bit-exact
accepted clocks, complete increments and dense coefficients against the previous
runner for all three methods. Chunk boundaries do not restart the live solver.

## Bounded storage and stopping

Retain every accepted state and dense polynomial in 256-step chunks, including
the fixed anchor/context and bit-exact carries. Use lossless NumPy compressed ZIP
arrays with unchanged dtypes and no quantization or dropped evidence. Preflight
each batch conservatively using its uncompressed size plus ZIP overhead against
the original 1 GiB campaign budget; reserve 4 MiB for indexes and receipts.

This version changes recording, not scientific inputs, methods or tolerances.
It keeps the original 256 MiB working-array estimate, one CPU worker, float64,
affinity 0–3 and single-thread numerical libraries. Keep the original 900-second
trajectory, accepted-step and RHS-call caps and 3600-second scientific session
cap, including comparisons and observations. A resource refusal or timeout is
incomplete. Numerical refusal is unqualified. Both retain logs, available valid
chunks, failing evaluation when possible, source capsule and hashes. Never
automatically extend a budget, retry a failed case, or overwrite an output root.

Implementation/unit-test time and a separately bounded, read-only artifact audit
are not continuation of a stopped numerical session. No partial adaptive solver
resume is supported. If the session cannot finish the registered panel, stop and
report the exact unfinished inventory; a later continuation needs explicit work.

## Comparisons and reference-only observations

Compare all three method pairs on the union of every accepted endpoint,
midpoint, fixed observer time and phase boundary, streamed in batches of at most
256. Preserve sampled complete states and compare typed histories, primary
coordinates, voltage, gates, fluxes and reconstructed binding caches. Maximum
normalized scores must be at most 0.1 of the frozen candidate budgets; primary
reconstruction must remain within 2e-9 and blocked histories exactly zero.

Observers record all 1007 registered times, including 102 times in 900–1000.
Keep full states/RHS, packet/cache/voltage/flux readouts, regulatory distances
scaled by E/M prepared-anchor separation, and the native-style goal diagnostic.
Codes are E=1, M=-1, X=0, unresolved=2. Label intervals include both coordinate
budgets and measured reference disagreement; any touched threshold or method
label disagreement is unresolved. Candidate errors are explicitly absent until
the later RK4 qualification; these are empirical allowances, not rigorous bounds.

Record each cell's terminal labels, unresolved samples, first sampled target
time and preceding bracket, right censoring, later returns and label changes.
The entire small fixed observer label/time table is bounded by 1007*N entries;
trajectory windows are never accumulated. Complete-state terminal drift, range
and RHS remain visible. Neither a positive switch nor equilibrium is required
for numerical acceptance. An unresolved label cannot count as a target hit.

The separate read-only auditor checks archived/live identities, complete payload
inventory, settings/budgets, exact chunk carries, polynomial endpoints, every
dense-curve extremum and independent graph ledger reconstruction. It independently
rebuilds the union comparison grid, observer labels/allowances and binding caches,
and checks observer coverage and drift summaries. Flux comparison
scores are checked as recorded online results, not independently re-integrated
or recomputed by that auditor. Failure campaigns receive integrity-only audits,
never numerical promotion.

## Remaining gate and use

NUM-005c remains open after c1. The later c2 slice must retain all registered RK4
study trials, select only after all six study cases, qualify every preparation
and condition at selected/half steps, and carry the candidate's own preparation
states into all four prescribed end-to-end continuations. Production MODEL-006
and ASSAY-002 still wait for that gate. No GPU or fluid implementation is added.

```bash
taskset -c 0-3 .venv/bin/python -m pytest tests/unit/test_source_graph_paths.py -q -W error
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/qualify_source_graph_paths.py --output runs/my-new-long-reference-attempt
taskset -c 0-3 .venv/bin/python scripts/audit_source_graph_paths.py runs/my-new-long-reference-attempt
```

The first command uses short engineering fixtures only; it does not execute or
qualify the long panel. The second deliberately requires a new output directory.
