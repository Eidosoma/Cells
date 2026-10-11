# NUM-010: short spatial extracellular trajectories

2026-09-11, D060. **NUM-010 is qualified.** The frozen reference run, independent
saved-data audit, all 3806 regression tests and preservation closeout pass.
Production remains Cells 0.14.0: this is a CPU numerical reference, not new
production physics, biological validation or a GPU implementation.

The [prospective protocol](../docs/SPATIAL_EXTRACELLULAR_NUMERICS.md) and
[fourteen-case panel](../configs/reference/spatial_extracellular_trajectories_v1.json)
extend SPEC-009's independently checked instantaneous physics into time.
Cells and membrane-free outside volumes have explicit inventories; membranes
and outside faces each own their transfer and dissipation histories. Relative
outside potentials satisfy current continuity at the current solver stage,
with only one arbitrary common gauge. No bulk capacitor, independent ground,
concentration floor or accepted-state projection is introduced.

## Frozen run

The [registration](../runs/num-010-2026-09-11/reference-01/registration.json)
captured 21 numerical/configuration/source files before any panel integration,
at 13:57:46 UTC. The [verification receipt](../runs/num-010-2026-09-11/reference-01/verification.json)
has SHA-256 `abf25d88ebd64bf2c922f189bdf0669ae100c46eef3101d0d8eda98f15a66046`.
No definition, tolerance, step ladder or resource cap changed after registration.

| Check | Observed result |
| --- | --- |
| Frozen cases / main attempts | 14 / 140: 42 implicit references and 98 RK4 candidates |
| Independent reference and analytic gates | All fourteen pass |
| Selected RK4/cubic step | **0.125 ms**, with passing **0.0625 ms** refinement |
| Retained failures | Seven rejected coarse trials and two completed accuracy failures |
| Complete-state restarts | All fourteen native/dense/observation suffixes are bitwise equal |
| Main work | 454,155 RHS calls, including all Jacobian probes; 88,411 accepted steps |
| Reference session / evidence size | 523.138 s on one CPU / 42,701,619 bytes |

The three reference settings use Radau, BDF and refined Radau. They independently
assemble outside-node current equations and use hyperbolic GHK; the RK4 path
uses SPEC-009's capacitance-component solve, Bernoulli GHK and separate incidence
scattering. Both integrate the same complete five-field state. The implicit
linearization probes a general tangent space preserving species totals and
capacitance-component charge; it does not repair actual states or derivatives.

The [trajectory review](num-010-trajectory-review.json) records all measured
errors, failures and work counters. Largest selected native/observation errors,
normalized by their acceptance budgets, are about `1.7373e-6` / `1.7364e-6`.
The selected observed concentration discrepancy is at most `1.80e-11 mM` on
this smooth, short synthetic panel. Such small discrepancies do not quantify
biological uncertainty or provide rigorous continuous-time error bounds.

The 94 implicit Jacobian evaluations account for 2,162 RHS calls, including
1,034 central-probe columns. One-sided probes and zero tangent columns are
exercised in preflights, not in this formal panel. The largest attempt uses
24,010 RHS calls and 4,802 accepted steps, below the unchanged 100,000 limits.
The maximum normalized current residual over admissible calls is 0.220461;
the maximum charge residual is `4.56e-24 C`, below `1e-20 C`. Rejected offending
states are saved separately and are not described as admissible trial states.

This session timing includes reference methods, dense output, analysis and
restart evidence. It is **not a production throughput or GPU speed benchmark**.

## Spatial resolution and the failures that matter

The closed binary-salt example matches exact ambipolar relaxation and the
derived diffusion potential. Its concentration contrast falls by **22.1199%**
in 0.3 s, exceeding the predeclared 10% witness. With the membrane blocked, the
same outside relaxation continues while the cell inventory and its membrane
histories stay exactly constant. Nonzero-history block/release and the 0.1 ms
membrane pulse also pass.

For the same sealed 20 micrometre line and initial finite-volume-average cosine
profile, concentration errors against the continuum reference are:

| Outside volumes | Maximum concentration error | Error / preceding grid's error |
| --- | --- | --- |
| 8 | 0.0922417 mM | — |
| 16 | 0.0234916 mM | 0.254674 |
| 32 | 0.00589999 mM | 0.251153 |

Both ratios pass the 0.3 limit and the finest error is below 0.02 mM. Separate
comparisons with the discrete analytic eigenmode give errors at most
`1.65e-12 mM`, distinguishing temporal integration error from spatial error.
This is one smooth mode on one-dimensional orthogonal grids, not validation
of arbitrary meshes, tissue geometry or all diffusion scales.

The 16-volume case rejects 4 and 2 ms steps; the 32-volume case rejects all
steps from 4 down to 0.25 ms. Their actual nonpositive stage states, held controls
and accepted prefixes remain recorded. The 8-volume case at 4 ms and the
16-volume case at 1 ms finish but fail accuracy: their largest observation
errors are 1.23359 and 6.75341 times budget. They remain failed results.

The fine-grid stability requirement, rather than the smooth low-frequency
observable's accuracy alone, determines the common selected step. The old
1 ms well-mixed step is not transferable, and 0.125 ms is not a universal bound
for arbitrary future spatial models. Faster GPUs cannot remove that numerical
constraint; other resolutions and implicit/multirate solvers need new gates.

## Evidence, tests and preservation

All **190 prospective preflight tests pass** with warnings treated as errors:
105 new NUM-010 tests and 85 unchanged SPEC-009 tests. The
[last preflight](num-010-preflight-04.xml) follows three retained passing
preflight receipts. It covers independent complete derivatives, general tangent
projectors, admissible probes, short synthetic integrations, whole-cubic domain
failures, exact blocking, complete restart, actual rejected stages, resource
stopping and rehashed artifact corruption. The full panel is not hidden inside
these preflights.

The [read-only auditor](../scripts/audit_spatial_extracellular_reference.py)
authenticates exact payload/source membership and dependency identities,
reconstructs native/dense observations, recomputes conservation, energy, controls,
analytic/refinement/selection verdicts and restart suffixes, and checks saved
offending stages without calling an ODE solver. The [complete-session audit](num-010-artifact-audit.json)
passes all **339 payloads / 21 sources**, numerical verdicts and fourteen bitwise
restart suffixes.

The [unchanged full-matrix driver](../scripts/test_finite_extracellular_production_build.py)
passes all **3806 tests** in the [new regression matrix](num-010-regression-01/verification.json):
2161 current 0.14.0, 971 preserved 0.10.0, 205 preserved 0.11.0, 213 preserved
0.12.0 and 256 preserved 0.13.0. There are no failures, errors or skips in the
executed matrix. Its original NUM-009 v1 complete-session suite still has no
completed v1 evidence: those thirteen prospective tests remain explicitly
unexecuted, not passing coverage. The maintained v2 replacement and original
stopped-evidence tests continue to execute in their preserved source context.

The [previous production audit](num-010-core009-audit.json) passes again:
830 payloads, 256 captured files and all 48 production modules retain their
accepted identities, without a solver rerun. The initial
[638-file workspace baseline](num-010-workspace-baseline.json) is the actual
pre-edit tree, not Git HEAD. The [closeout](num-010-closeout.json) records **628
existing files byte-identical**, ten expected documentation-only updates and
none missing. All 48 production modules, earlier sources and the original
stopped NUM-009 v1 status remain unchanged. Ruff lint/format checks pass for all
263 Python files; dependency and whitespace checks pass.

To audit the saved session in its unchanged 0.14.0 source/runtime context:

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 4 .venv/bin/python scripts/audit_spatial_extracellular_reference.py runs/num-010-2026-09-11/reference-01
```

The corresponding [qualification driver](../scripts/qualify_spatial_extracellular_reference.py)
requires the same pinned single-CPU environment and a fresh destination; it
refuses overwrites. Preserve this reference context alongside accepted production
before CORE-010 changes the version. Later code must not silently reinterpret
this run using a different electrical closure or source identity.

## Next implementation boundary

Next is **CORE-010**, a separately versioned passive spatial CPU/JAX family
through the existing engine. Map explicit inventory, membrane and outside-face
axes; expose the field solve and its residuals as a distinct same-stage block;
then qualify eager/JIT execution, complete checkpoints, branches, windows and
independent-world cohorts. Preserve accepted 0.14.0 before any production edit.

The reference's small dense linear algebra is not a large-GPU architecture.
Future sparse/matrix-free field solves, multirate/implicit evolution and partition
communication must preserve the same physical ownership and invariants. Broader
pumps/channels, cross-region gap junctions, multiple membrane patches, barriers,
electrodes, changing geometry, empirical calibration and organ models remain
separate work. No BETSE parity, physiological plausibility or GPU speedup follows
from this numerical gate alone.
