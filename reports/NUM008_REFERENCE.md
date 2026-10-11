# NUM-008: short physical ionic graph qualification

2026-09-10, D053. **Complete — independent CPU numerical qualification.**
Saved-data audit and all 3096 regression tests pass. Production remains Cells 0.12.0.

The [frozen protocol](../docs/PHYSICAL_IONIC_GRAPH_NUMERICS.md) tests the unchanged
[SPEC-007 equations](../docs/PHYSICAL_IONIC_GRAPH_SPEC.md) over time. This adds
an independent CPU numerical reference, not a production graph or biological result.

## Result and bounded scope

All twelve cases qualify on **84 graph attempts and five independent component
solves**. Radau, BDF and refined Radau agree; all four candidate steps pass.
The predeclared rule selects the coarsest declared **2 ms coupled RK4/cubic**
candidate, with a passing **1 ms refinement**. The 0.5 and 0.25 ms trials also
pass. No scientific candidate was rejected or failed an accuracy check in this
short panel; larger steps were not tested.

This is deliberately a different preparation/horizon panel from NUM-007.
It **does not relax production's one-cell 0.5 ms limit**, change the old pair
or multispecies bounds, or establish a safe step for arbitrary cell counts,
high-degree graphs, stronger junctions, small capacitances or organs.
It does not qualify multirate, coarse-grained or GPU execution.

| Case | Horizon (s) | Maximum observed voltage error (V), 2 ms | Largest normalized observed error |
| --- | --- | --- | --- |
| single_mono | 0.10 | 9.007e-9 | 0.009007 |
| single_divalent | 0.10 | 9.003e-9 | 0.009003 |
| disconnected_mono | 0.10 | 4.529e-8 | 0.090907 |
| pair_mono | 0.20 | 4.586e-8 | 0.092018 |
| pair_divalent | 0.20 | 4.594e-8 | 0.092123 |
| star_mono | 0.20 | 4.464e-8 | 0.089481 |
| star_divalent | 0.20 | 4.471e-8 | 0.089582 |
| pair_mono_internal | 0.20 | 1.583e-12 | 0.013035 |
| star_mono_internal | 0.20 | 2.513e-12 | 0.013134 |
| star_mono_block_release | 0.30 | 4.464e-8 | 0.089481 |
| star_divalent_block_release | 0.30 | 4.471e-8 | 0.089582 |
| star_mono_short_pulse | 0.05 | 4.466e-8 | 0.089515 |

Normalized error must be <= 1. The largest selected error fraction is
**0.0921231**: K amount error `9.21231e-9` fmol in the divalent pair,
against the predeclared `1e-7` fmol budget. The largest observed voltage error
is approximately `4.59382e-8` V; membrane-gate error is `1.66176e-6` and junction-gate
error `2.37452e-8`. The largest implicit-reference comparison is
`0.000158850` of its tighter error allowance.

These are maxima on the declared native/comparison meshes, not rigorous
continuous-time error bounds or experimental uncertainty. Native candidate
endpoint errors and cubic observations are checked separately. Whole-cubic
extrema checks establish only the polynomial's domain within floating arithmetic.

## What is checked over time

- Single mono/divalent and disconnected heterogeneous cells agree with five
  separately integrated components using the unchanged earlier local references.
  The receiving star cell has no membrane channel; channel count is not cell count.
- Each edge transfers ions once, with equal/opposite endpoint contributions.
  Each cell's membrane is evaluated once even when two junctions share it.
  Independent hyperbolic edge/local equations and Bernoulli candidate equations
  read the complete state at each shared solver stage.
- Local leak, pump, membrane-channel and junction transfer histories remain
  separate. Signed edge histories do not become bath exchange or replace the
  amount-owned charge anchor. Both membrane and junction dissipation are retained.
- Closed pair/star cases keep bath histories exactly zero while conserving
  global species inventories and capacitance-weighted charge. The unweighted
  sum of unequal-capacitance cell voltages is not the conserved quantity.
- Independent blocking/release, the all-off interval [0.0679, 0.113] s,
  staggered edge release and the [0.0203, 0.0204] s edge pulse pass.
  Disabled histories remain exactly constant. Gates continue evolving and
  match analytic fixed-voltage relaxation when all transport is off.
- Events split the native mesh; every stage and endpoint slope uses the old
  interval's control. Final-time settings affect right-continuous readouts,
  not the incoming state. Observation requests do not select integration steps.
- Every actual RHS call, including implicit Jacobian probes, accepted state
  and common observation stays in the physical/gate domain. Candidate cubic
  interiors check every amount, cell voltage, edge voltage difference and gate.
  A blocked real edge or species is not exempt from its domain restrictions.

Across native and observed states of the selected candidate, the largest
material residual is approximately `3.98459e-13` fmol (K), and the Ca residual is
`1.44843e-18` fmol. Local charge residual is `1.79381e-12` V,
global weighted charge residual is `3.77725e-23` C, and total chemical/capacitor
energy residual is `3.22345e-8` pJ. Each dissipation history is nondecreasing
at inspected points. All are within the prospective limits. Energy-history
limits here genuinely use **pJ**, distinct from SPEC-007's derivative-coordinate
comparison key.

The maintained bath, diagonal capacitance, fixed topology and synthetic gate
laws are unchanged assumptions. No finite extracellular field, metabolism,
geometry evolution, cycle-memory trajectory, whole-cell clamp, native BETSE
execution or biological/source parity is claimed.

## Evidence, resources and reproducibility

The accepted [session receipt](../runs/num-008-2026-09-10/reference-01/verification.json)
has SHA-256
`bd9ee2599899dd3b34fa2072b308c2dd435485bb538a7775f24396baf664c8a7`.
The [numerical panel](../configs/reference/physical_ionic_graph_trajectories_v1.json)
is pinned at
`d09e21f945525769aea541e668625b168586f4c29d2cd852767b301ef2d8e00f`;
the prospective protocol is pinned at
`bb439a278e55c17b83fcbd8a0debf128455c78ad1a1451fabb772232871d790f`.

The [read-only audit](num-008-reference-audit.json) authenticates **194 payloads
and 26 captured source/dependency files**, replays **89 recorded arrays and
256283 sampled rows** exactly, and recomputes accounting, controls, reductions,
error and candidate selection without an ODE rerun. It rechecks declared/current/
archived source identity, complete file inventories, initial preparations,
settings, event meshes, dense bases and final summaries. Trial-domain summaries
are instrumentation, not a saved transcript of every adaptive stage.

The single CPU-4, one-thread session used **321.805 s** and **114706916 bytes
(109.393 MiB)**, within its prospective 1800 s / 256 MiB caps. Graph attempts
used 304958 RHS calls and 50816 accepted steps in aggregate;
per-attempt limits remain 100000, not a pooled allowance. These are reference
qualification costs, not production throughput or GPU speedup measurements.

All scientific code/tests and input identities were captured before this run.
No solver setting, initial condition, tolerance, budget or candidate ladder
was changed after observing its trajectories.

## Tests and preservation

All **99 new tests pass**, with no failures, errors or skips, in the
[targeted run](num-008-targeted-01.xml), 29.958 s of JUnit time.
They cover strict controls/layout, zero-length axes, independent equation paths,
cell order and edge orientation, frozen histories, hidden charge-anchor repair,
event/readout ownership, full cubic domains, rejected-stage evidence, work/output
caps, exact dense replay and rehashed corruption/provenance refusals.

Preflight used a shorter 0.012 s synthetic preparation. Its
[first run](num-008-preflight-01.xml) had 83 passing tests and one failing
rejection-receipt test: an in-memory tuple control was compared with its
JSON-list representation. Normalizing the retained control receipt fixed that
serialization mismatch **before scientific execution**. The
[second preflight](num-008-preflight-02.xml) passed 84 tests; after four additional
order/edge-domain/history checks, the [final preflight](num-008-preflight-03.xml)
passed 88. The earlier failed preflight remains recorded; no numerical criterion
was weakened.

All **3096 regression tests pass**, with no failures, errors or skips:

| Source context | Tests | JUnit time (s) |
| --- | --- | --- |
| Current production 0.12.0 | 1920 | 637.400 |
| Preserved NUM-005 / 0.10.0 | 971 | 158.247 |
| Preserved channel references / 0.11.0 | 205 | 18.479 |

The [regression receipt](num-008-regression-01/verification.json) has SHA-256
`ab72c57bdd1c1866abafa9bc2b3ff8b099c3db819d46c30513d2d96c7876f267`.
Summed JUnit time is 814.126 s, not a simulation performance measurement.
All six XML/log hashes and counts are rechecked; both historical source archives
retain their accepted identities. No historical source guard or regression driver
was changed to accommodate this new reference.

The [earlier production audit](num-008-core007-audit.json) passes again:
1580 payloads, 44 production modules, fourteen reference cases, 43 scalar runs,
two windows and four cohorts; no ODE rerun. Before documentation updates, all
444 files in the [pre-edit baseline](num-008-workspace-baseline.json) remained
byte-identical. At final [closeout](num-008-closeout.json), **433 remain unchanged
and eleven have documentation-only updates**, with none missing. All earlier
scientific/pilot artifacts, including uncommitted SPEC-007 work, are preserved.
All 209 Python files pass Ruff checks and formatting; dependencies and Git
whitespace checks pass. The thirteen affected Markdown files pass local-link,
anchor, table, heading and fence checks.

To inspect the accepted evidence without rerunning the scientific session:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  taskset -c 4 .venv/bin/python scripts/audit_physical_ionic_graph_reference.py \
  runs/num-008-2026-09-10/reference-01
```

To repeat qualification, the same one-CPU/thread environment and
`scripts/qualify_physical_ionic_graph_reference.py --output NEW_DIRECTORY`
are required. Existing destinations are refused; do not modify or replace the
accepted session. A reference failure or resource cap stops a new session.

## Next gate: CORE-008

Preserve accepted 0.12.0 and its strict source/runtime contexts before changing
production. Add a separately versioned physical ionic graph family through the
existing CPU/JAX engine, with explicit species/cell/membrane/channel/edge axes
and reference-to-production layout adapters. Verify shared-stage sparse
exchange, padding/control bindings, all nine state fields, full checkpoint
roundtrips, fresh-process restart, branching, window and independent-cohort
isolation against these saved references.

Use prospective production verification runtime/output limits before launching
that acceptance. Numerical reference qualification does not establish eager/JIT
agreement, production checkpoint compatibility or memory/cost bounds.
Larger-graph and GPU execution need their own measured qualification later.
Do not reopen the descriptive pilot or the deferred E02 source campaign here.
