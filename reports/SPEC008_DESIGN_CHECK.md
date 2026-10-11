# SPEC-008: finite extracellular-compartment design checks

2026-09-10, D055. **Complete — design and instantaneous reference only.**
Production remains Cells 0.13.0, with no changed production module, package
version, shared solver, test-context driver or checkpoint schema.

The [contract](../docs/FINITE_EXTRACELLULAR_SPEC.md) gives one finite well-mixed
outside its own species inventory, fixed charge and chemical energy. It may
serve one or several cells; each membrane transfers equal/opposite amounts
between its endpoints, while junction transfers stay inside the cell graph.
This is a scalar instantaneous reference, not a time-integrated or production
finite environment, selected timestep, biological validation or organ model.

## Frozen inputs and corrected result

All **10,671 instantaneous checks pass** on nine synthetic cases, with zero
failed checks. The [revision-2 receipt](spec-008-design-check-v2.json) records
resolved definitions/rates, manufactured accounting probes, volume-limit
results, 17 source/evidence identities and all 46 unchanged production modules.
Its SHA-256 is
`ebb0e660dd5c1f980968d631f6539441fed94e4e9ec995aba26401510cf4e44b`.

The [panel](../configs/reference/finite_extracellular_v1.json) and contract were
declared before scientific evaluation. Their SHA-256 values are
`5169c84abd14fe9d9963bd55bd6bb5b2614c8541031d1378367eba81b37b1e2a` and
`f8e3a4798c0d9fa7ba7c82478aaede0c15a3bc8abadccceca3ae9d369ce34af1`.
The current-versus-charge tolerance key was separated into its explicit ampere
unit before the first evaluation; there was no post-result tolerance revision.
Cell/channel/junction inputs are inherited unchanged from SPEC-007. New outside
volumes, amounts and countercharges are explicit, not calibrated to experiments.

| Check | Evidence |
| --- | --- |
| Independent rates | 6852 complete-coordinate comparisons with direct 70-digit Decimal exponential transport, pump/channel kinetics and energy arithmetic, plus 319 comparisons at nonzero supplied histories |
| Maintained-bath reduction | 202 initial intracellular/gate/history derivative comparisons are exact when inside/outside concentrations match the old reference |
| Material and charge | 591 species-rate balances, 591 checks that outside exchange contains only membrane transfer, and 183 opposite capacitor-current checks |
| Energy | 183 full inside/outside chemical-plus-capacitor power balances, 183 nonnegative interface-dissipation checks, and nine independent energy directional-derivative probes |
| Hidden state and blocking | 60 explicit all-off gate-relaxation assertions and 69 exact zero-outside-rate assertions; old histories are not reset |
| Storage choices | Cell, species and edge ordering plus edge orientation: 319 comparisons each, all exact on these scalar fixtures |
| Nonzero histories | Separate inside/outside/global material, capacitor countercharge, stable finite energy difference and signed pump-work/history formula checks |

Maximum normalized arithmetic/accounting error is **0.0701681**, below the
passing boundary of 1, in a nonzero-history countercharge check. The largest
material normalized residual is 0.0626035. These reflect bounded floating-point
accounting, not biological uncertainty or a trajectory error allowance.
The pJ dissipation derivative coordinates are converted to W before comparison;
charge is measured in C and charge rate in A.

## What the design establishes

The extracellular potential is a gauge reference for a floating capacitor star,
not an electrode clamp. Initial outside charge opposes the summed membrane
capacitor charge. Exact zero net charge in every individual compartment would
contradict the nonzero membrane voltages; only the complete ionic system has
zero total charge. Amounts drive charge, while histories record transfers.

The finite-system energy contains both intracellular and extracellular chemical
energy and counts each physical membrane capacitor once. Substituting a changing
outside concentration into the old fixed-bath grand potential would not supply
this energy identity. External pump drive and isothermal dissipation remain
explicit; ionic closure is not complete thermodynamic isolation.

A unit test transfers neutral salt from one cell to the outside without changing
another cell's state or voltage. The other cell's membrane rates change even
with no junctions. This is an instantaneous shared-environment feedback witness,
not a simulated signal, adaptation or memory experiment. A separate supplied
cycle-history witness leaves node amounts and outside amounts unchanged.

For the same algebraically prescribed 0.001 fmol inward sodium transfer:

| Outside volume, pL | Outside sodium change, mM | Largest intracellular rate difference from maintained bath, fmol/s |
| --- | --- | --- |
| 0.1 | approximately -0.01 | 2.931158e-6 |
| 1 | approximately -0.001 | 2.931186e-7 |
| 10 | approximately -0.0001 | 2.931189e-8 |
| 1000 | approximately -0.000001 | 2.931190e-10 |

Concentration changes follow the specified inverse-volume relation, and these
instantaneous rates approach the maintained-bath result. No uniform long-time
limit or coupled trajectory is claimed. Manufactured histories and symmetric
energy directional probes are algebraic calculations, not solver steps.

## Retained correction and test attempts

The [first receipt](spec-008-design-check.json) passes its 10,569 checks, but
text labels `str(0)` versus `"0.0"` skipped extra all-off assertions. Complete
Decimal comparisons already included zero availability. Revision 2 replaces
those special-case labels with numeric control predicates and tests their
execution counts, adding 102 assertions. The physical reference, frozen inputs,
tolerances and all earlier verdicts are unchanged. The
[correction record](spec-008-checker-correction.json) retains exact pre-correction
checker/reference/test sources, each verified against the first receipt's hashes.

The [initial 83-test preflight](spec-008-preflight-01.xml),
[expanded 88-test preflight](spec-008-targeted-01.xml) and
[corrected 88-test targeted run](spec-008-targeted-02.xml) all pass. The expansion
adds resolved-world/derived-coefficient guards and species-name independence;
the final targeted run takes 1.65 s. No failed scientific comparison is reclassified.

The [saved-receipt replay](spec-008-reference-replay.json) reproduces all 10,671
checks and every serialized field except the timestamp exactly. Its first
[comparison-harness attempt](spec-008-reference-replay-01.json) compared in-memory
tuples with JSON-loaded lists and failed object equality. Applying the same JSON
serialization roundtrip as the writer fixes that comparison; no reference code,
saved result, source hash or numerical tolerance changed. Replay takes 1.125 s,
checks all 17 source identities and verifies the three retained old source bodies.

The first full regression was deliberately stopped before editing the checker.
Its [interruption record](spec-008-regression-01/interruption.json) preserves
the partial log: 81 progress markers include one failure marker, without a
completed failure traceback, JUnit file or matrix receipt. It is **not accepted
or classified as passing**. The corrected complete run uses a new directory;
its [final matrix](spec-008-regression-02/verification.json) passes all **3298
tests**, with zero failures, errors or skips in all four source contexts.

| Source context | Tests | JUnit duration, s |
| --- | --- | --- |
| Current production 0.13.0 | 1909 | 694.858 |
| Preserved reference 0.10.0 | 971 | 156.682 |
| Preserved channel reference 0.11.0 | 205 | 18.687 |
| Preserved physical-graph reference 0.12.0 | 213 | 15.201 |

The summed context duration is 885.428 s, not a simulation performance benchmark.
The matrix SHA-256 is
`339823d18d225fadfef5a7f0d1dba7bff54767835a3dd8af0b9789ec3181f3d0`.
All eight log/JUnit payload hashes, all three preserved source archives and the
unchanged test-context driver were verified again before closeout.

## Production preservation and next gate

The [unchanged production saved-output audit](spec-008-core008-audit.json) passes
again: 600 payloads, 223 captured implementation files, 46 production modules,
twelve reference cases, 37 scalar outputs, two window runs and four cohorts.
It rereads saved evidence without rerunning an ODE solver. The
[493-file pre-edit baseline](spec-008-workspace-baseline.json) includes existing
uncommitted work. Of those, 484 remain byte-identical and nine have documentation-
only updates; none is missing. All production modules, packaging, test-context
driver, old reference code and earlier scientific/pilot data remain unchanged.
All 221 Python files pass Ruff lint/format checks; dependency and whitespace
checks pass. The [closeout](spec-008-closeout.json) binds the final documentation,
regression matrix, reference/correction/replay receipts and preservation hashes.

Next is **NUM-009**, a separately frozen short-trajectory qualification. Small
outside volumes can introduce fast feedback/depletion; no old timestep carries
over. Independent solvers must use explicitly justified, conservation-consistent
coordinates for their Jacobian probes while retaining all ten physical fields
for audit. Outside amounts, countercharge, full histories, events and cubic
interiors need qualification before **CORE-009** production.

For future GPUs, the shared outside is a same-stage reduction dependency, not
one independently evolving copy per device. Spatial outside compartments and
organ definitions come later with their own closure/convergence evidence. No
GPU work, optimization, field mesh, organ preset, biological refit or deferred
long E02 campaign is started here.

To repeat these checks with new output paths:

```bash
taskset -c 4 .venv/bin/python scripts/check_finite_extracellular.py --output reports/my-spec008-check.json
taskset -c 4 .venv/bin/python -m pytest tests/unit/test_finite_extracellular_reference.py -q
.venv/bin/python scripts/test_cells_build.py --output reports/my-spec008-tests
```
