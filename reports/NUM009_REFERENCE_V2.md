# NUM-009 v2: explicit finite-outside inventories

2026-09-10, D057. **NUM-009 is qualified.** The frozen numerical run,
independent saved-data audit and all 3466 regression tests pass. This is not a
production extension or biological validation. Cells remains 0.13.0.

The [v2 amendment](../docs/FINITE_EXTRACELLULAR_NUMERICS_V2.md) corrects the
reference representation generally: every compartment's inventory increments
are explicitly integrated, including the outside. Only implicit Jacobian probe
directions conserve species totals by construction. No inventory, solver state,
flux or dense output is projected, reset or inferred from another compartment's
rounding residual. The [first failed attempt](NUM009_REFERENCE.md), its original
protocol, all 31 captured source files and its stopped receipt remain unchanged.

## What changed, and what did not

The original reference reconstructed the outside from the summed inside changes.
During junction-only exchange, cancellation left approximately 7.6e-19 fmol in
that outside increment. The physical amounts rounded to constants, but the
declared complete-state exact-blocking contract failed.

The v2 reference integrates all ten fields and uses the actual zero outside RHS
when membranes are disabled. A general conservation-tangent linearization keeps
implicit derivative probes physically admissible without selecting a dependent
owner. Its derivation and bounded finite-difference rule are in the amendment.
This dense CPU reference method is not a proposed GPU kernel.

All SPEC-008 equations, preparations, fourteen cases, horizons, controls, RK4
code/step ladder, implicit tolerances, acceptance limits and resource caps are
unchanged. The new preflights cover every possible isolated owner of a synthetic
star after nonzero transfers, outside-only blocking with active junctions, all-off
gates, boundary gates, admissible probes and independent directional derivatives.
The final [pre-run suite](num-009-v2-preflight-03.xml) passes 153 tests: the
109 original preflight/stopped-evidence tests and 44 new engineering/context tests.
Earlier passing preflight receipts are retained too.

## Frozen run and numerical result

The [registration](num-009-v2-registration.json), made before any formal v2
trajectory, binds 43 source files and panel SHA-256
`91d7e85deddcc98c4e0ea1a474192d4224bda86edbfce85d563c663d008bcaa8`.
The new session is [reference-02](../runs/num-009-2026-09-10/reference-02/verification.json).
No failed-run payload was overwritten or reclassified.

| Item | Result |
| --- | --- |
| Complete short cases / attempts | 14 / 112: 42 implicit references, 70 RK4 candidates |
| Reference gates | All 14 pass |
| Selected RK4/cubic step | 1 ms, with passing 0.5 ms refinement |
| Largest selected endpoint / observation error, normalized by its budget | 0.581537 / 0.593937 |
| Largest 0.5 ms observation error, normalized | 0.032248 |
| Retained candidate accuracy failures | 9 completed candidates; no rejected stages |
| CPU qualification time / saved artifacts | 297.692 s / 103,601,932 bytes |

This step selection applies only to the declared 0.05–0.3 s synthetic panel.
It is not an arbitrary-volume, arbitrary-graph, long-time or production timestep
guarantee, and this resource-bounded qualification is not a performance benchmark.

All three junction-only references now have **exactly zero outside increments**
in native states and observations, and exactly zero outside dense coefficients.
The general blocked-owner preflights also preserve nonzero frozen inventories
exactly; passing this star alone is not the engineering justification.
The [saved-trajectory review](num-009-v2-trajectory-review.json) records those
exact values: the largest trial countercharge over the full panel is
2.76645e-21 C (limit 1e-20), the largest attempt uses 13358 RHS calls and 1815
accepted steps (each limit 100000), and the smallest actual trial outside
inventory is 9.19330e-5 fmol. All 3740 RHS calls used in 120 Jacobian evaluations
are included in the work totals; boundary one-sided probes are exercised in
preflight, while the formal panel uses central probes only.

The previously unrun full block/release, 0.1 ms pulse and two tiny-reservoir
cases now have complete evidence. The pump-only outside potassium witness falls
by **80.8057%**, exceeding its predeclared 5% requirement while staying positive
(minimum fraction 0.191943). This is a synthetic depletion stress, not evidence
of physiological depletion, homeostasis, memory or organ behavior.

Eight 4 ms candidates and one 2 ms candidate fail accuracy and remain failures.
The 4 ms failures occur in disconnected cells, pair, mono/divalent stars,
block/release, short pulse and both tiny-reservoir cases. The pump-only depletion
case also fails at 2 ms. Its normalized observation errors are 369.107 and 12.3392
at 4 and 2 ms, respectively; the unchanged concentration/error gates therefore
matter. No cases, solver settings or checks were adjusted after observing them.

## Independent audit and test routing

The [read-only v2 audit](num-009-v2-artifact-audit.json) authenticates
**242 payloads / 43 sources** and exactly replays **112 arrays / 251,400 rows**.
It recomputes material, charge, full ionic energy, controls, error/refinement,
whole-cubic domain and depletion verdicts without running an ODE solver.
Actual implicit work includes all conservation-tangent probes and is checked
against solver/Jacobian counts. The verification receipt SHA-256 is
`a628ee5eb7cbecb438728012ffe2a2ba6fb28b7a9ab20a7c4f429318f5b0c45b`.

All **168 targeted tests pass** in the [post-run suite](num-009-v2-targeted-01.xml),
with no failures, errors or skips: the 153 preflight tests plus 15 v2 complete-
session/corruption checks. Corruption checks mutate temporary copies only.
The [full matrix](num-009-v2-regression-01/verification.json) passes all
**3466 tests**, with no failures, errors or skips across its four source contexts:
2077 current, 971 preserved 0.10.0, 205 preserved 0.11.0 and 213 preserved
0.12.0. Summed test-context time is 926.421 s; archive copying is additional
orchestration time. This revision adds 59 engineering tests; the targeted
168-test run includes the 109 earlier NUM-009 tests, not 168 newly added tests.

The original v1 complete-session suite contains 13 prospective tests but has no
complete v1 scientific evidence. It remains explicitly **unexecuted**, not
silently counted as passing. The maintained v2 suite covers the same checks and
adds Jacobian accounting and a full saved-session audit. The
[test-context wrapper](../scripts/test_finite_extracellular_build.py) records
that version routing; the accepted production driver remains byte-identical.
Both original v1 preflight and stopped-evidence suites still execute.

## Preservation and next boundary

The [old stopped-run audit](num-009-v2-prior-attempt-audit.json) passes again
against its 31 unchanged current source identities and 174 original payloads.
It still reports `stopped_not_qualified`, no selected step, and exactly replays
184240 rows. The [existing production audit](num-009-v2-core008-audit.json) also
passes: 600 payloads, 223 implementation dependencies, 46 production modules,
twelve reference cases and scalar/window/cohort evidence, without an ODE rerun.

The [pre-edit baseline](num-009-v2-workspace-baseline.json) captures 529 existing
files, including the user's uncommitted work. All 520 non-edited files remain
byte-identical; nine documents have status/design-only updates and no prior file
is missing. All 239 Python files under src/tests/scripts pass Ruff lint/format
checks; dependency and whitespace checks pass. The
[closeout](num-009-v2-closeout.json) binds final sources, artifacts, regressions
and documentation. There is no finite-outside production family yet.

Next is CORE-009: preserve accepted 0.13.0, map explicit inside/outside anchors
and increments to numeric CPU/JAX state, implement same-stage one-owned outside
flux accumulation, and qualify complete readouts, checkpoint/restart, branch,
window and independent-world cohort paths. Keep older maintained-bath families
unchanged. GPU execution, spatial extracellular fields, organ presets,
biological validation and the deferred long E02 campaign remain separate work.
