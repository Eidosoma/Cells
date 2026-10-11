# E02 candidate engineering: bounded checked RK4

D037 / NUM-005c2a, 2026-09-09. The user approved building and benchmarking a
bounded RK4 candidate on short fixtures after the
[A2 reference panel](../reports/NUM005C1_A2_REFERENCE_PANEL.md). This step does
not authorize the 500/1000-unit candidate study, choose a production timestep,
change equations or modify any accepted source capsule.

## Numerical and state contract

Use the independent fixed-graph NumPy model, not Cells or native BITSEY kernels.
Integrate the full `13*N + 4*E` increment vector about the unchanged phase anchor.
Keep typed histories passive. Classical RK4 takes four stage RHS evaluations
and one endpoint RHS for its cubic Hermite observation curve; do not reuse an
endpoint slope in a way that changes the tested arithmetic.

Generate clocks lazily from the global integer tick and the original maximum
step, with one exact shortened final step if needed. Never restart the grid at
a recording-window boundary or accumulate the clock through repeated additions.
Validate finite values, every stage's primary/electrical domain and accounting,
all cubic extrema and blocked histories. No clipping, early phenotype stop or
tolerance relaxation. Keep all eight existing candidate/reference error targets
and the 2e-9 accounting bound.

A window boundary carries every primary increment and diagnostic history, the
fixed case/context/anchor identity, global tick, original end/step and numerical
source/runtime identity. Exact RK4 restart is allowed only at a stored accepted
boundary with matching identity. This is a fixed-control, single-phase contract,
not support for donor removal, changing topology, adaptive restart or an
end-to-end candidate preparation transfer. Those later transfers must retain
their own preparation provenance, not substitute the qualified reference anchor.

## Bounded evidence and comparison

Retain one candidate window in memory. Short engineering evidence stores every
accepted state, all five RHS slopes and all four cubic coefficients, with exact
window carries and hash-indexed exclusive chunks. Complete initial/final state
and each window checkpoint are retained. A failed stage never becomes accepted
state; preserve the last accepted carry and failing input when quota permits,
plus an explicit failure receipt. Existing output roots cannot be overwritten.

An explicitly mapped reference reader samples the accepted trios directly from
their immutable roots. Sample the union of candidate and reference endpoints,
midpoints, registered observers and the short phase boundaries. References keep
their original 500/1000-unit identities; only the engineering comparison horizon
is shorter. Process samples in bounded batches, preserve exact accepted endpoint
values, retain full candidate/reference sample states and observer flags, and
stream all eight maximum error scores. Close every reader/generator on all exits.

This full short-fixture format is deliberately auditable. It is **not** yet the
long-study evidence policy: storing five slopes in addition to states/cubics
costs more than the illustrative estimate in the
[earlier preflight](E02_CANDIDATE_PREFLIGHT.md). A later compact policy would need
explicit retained-versus-online-only checks and its own audit scope; do not
silently drop evidence or extrapolate compression ratios.

## Predeclared bounded profiles

The [profile inventory](../configs/reference/e02_candidate_engineering_v1.json)
uses both actual preparation seeds, both prepared active stars and both prepared
one-neighbour cases. Run each from 0 to 5.12 at maximum step 0.01 (512 steps),
first with width 16 and then 256: twelve profiles, not an 18-trial timestep study.
Compare the two recording policies' complete clocks, states, stage slopes,
cubics and comparison samples exactly. Unit fixtures additionally cover awkward
final clocks, several widths, saved-state restart, numerical/order checks and
failure/tamper handling. No test runs a 500/1000-unit candidate.

Time the complete checked path: integration/stages, cubic checking, reference
sampling and derived comparisons, compressed recording and final receipts.
Record section times, working-array estimates, actual bytes and process RSS
with their different meanings. No speed or memory claim may be based on an
unchecked RHS-only loop. Profile each case once per width; this is not a repeated
statistical performance study or a claim about late-time stiffness/accuracy.

One CPU float64 worker at a time, affinity 0–3 and single-thread libraries.
Keep the original 900-second trajectory/profile, 3600-second engineering-session,
one-million-candidate-step and 256 MiB estimated-array limits. The two-million
RHS cap is for implicit references; five candidate RHS calls per accepted step
are counted separately and bounded by the candidate step cap. Derived comparison
evaluations are also counted. No new implicit integration is needed.

Accepted preparation artifacts occupy 46,476,933 bytes and all four existing
long-reference roots 715,966,189 bytes. Include both in the same 1 GiB quota:
762,443,122 prior bytes leave 311,298,702 bytes for the new engineering root.
The separate `runs/num-005c2a-2026-09-09/` parent preserves old strict inventories;
it does not reset the budget. Register and archive all sources before profiling.
Failure stops the session without retries or a changed timestep.

## Audit and interpretation

A separate bounded read-only audit verifies sources, imports, hashes, exact
clocks/carries, the RK4 stage/update and cubic algebra, independently checked
stage/curve domain and typed accounting, sample-grid coverage and sample identity.
It independently normalizes primary/history comparison scores. Stored RHS values
and derived flux/gate/voltage scores are not independent RHS recomputations;
algebraic reconstruction alone does not prove those values are correct. Analytic
RK4 tests and comparison to the frozen independent references provide separate
checks. Floating-point extrema are not interval-certified ODE error bounds.

Report short-prefix agreement without choosing a timestep. Use measured complete
costs for explicitly labelled planning extrapolations across the six registered
study cases; assess runtime and bytes against the unchanged caps. These estimates
cannot certify the long run. If the implementation/evidence policy does not fit,
propose optimization or a named policy decision before any long candidate study.
Production remains 0.10.0; no GPU, organ, native long driver or continuing-agent
experiment is included.

## Reproducible commands

Run with the pinned `.venv`, CPU affinity 0–3 and `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` all set to `1`.
The profile command creates one exclusive root, registers all sources, then
launches only the twelve short profiles in order. It cannot reopen a closed run.

```bash
taskset -c 0-3 .venv/bin/python scripts/profile_graph_candidate.py --run --output runs/num-005c2a-2026-09-09/engineering-01
taskset -c 0-3 .venv/bin/python scripts/audit_graph_candidate.py runs/num-005c2a-2026-09-09/engineering-01 --output reports/num-005c2a-audit.json
```

Audit output is exclusive and outside the immutable run root. Unit fixtures may
use temporary roots and shorter horizons; no unit test is a long candidate trial.
