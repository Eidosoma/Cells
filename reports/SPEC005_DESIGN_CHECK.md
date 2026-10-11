# SPEC-005: multispecies membrane design/reference

2026-09-09, D046. **Complete as an instantaneous engineering reference.**
The [frozen panel receipt](spec-005-design-check.json) passes all **1,546 checks**.
All **352 targeted pytest cases pass**, including **113 new reference tests**.
This does not add an eighth production model, qualify new trajectories, reopen
the biological pilot or establish BETSE parity.

## What was delivered

- [Physical/data contract](../docs/MULTISPECIES_MEMBRANE_SPEC.md): one fixed-volume
  cell, one membrane and one maintained bath; explicit species valence, signed
  fixed/background charge, amount anchors, units, ownership and support.
- [Frozen synthetic panel](../configs/reference/multispecies_membrane_v1.json):
  the previous Na/K/Cl reduction and a deliberately specified divalent-ion case.
  Inputs and tolerances preceded evaluation and did not change afterward.
- [Independent scalar reference](../tests/reference_multispecies.py): strict
  schema/role resolution into immutable aligned tuples; passive transport,
  the named reversible Na/K pump, charge closure and material/energy accounting.
  It imports only the standard library, not Cells/JAX or production kernels.
- [Reproducible checker](../scripts/check_multispecies_contract.py) and
  [tests](../tests/unit/test_multispecies_reference.py): an independent 70-digit
  Decimal exponential calculation, comparison with the existing independent
  hyperbolic reference, failure guards, permutations and immutable receipts.

The reference is deliberately outside `src/cells`. Its schema is an experimental
reference identity, not a runnable Cells configuration, final device layout or
checkpoint schema. No arbitrary plugin/expression framework was introduced.

## Results and meaning

| Check | Result | What it establishes |
| --- | --- | --- |
| 210 passive-law probes, valences -3 through +3 excluding zero | Flux and potential agree with Decimal; maximum normalized errors 0.0000902 and 0.000199 | Bounded arithmetic agreement, not arbitrary-parameter support |
| 30 Nernst probes | Largest zero-flux residual approximately 7.11e-19 fmol/s | Correct passive electrochemical equilibrium limit |
| Diffusion, orientation, area, route-off and dissipation | Pass across the frozen grid | Signs, units and limiting behavior of the selected passive law |
| Na/K/Cl reduction at seven voltages | Pass against the existing independent reference | Old equations and parameter meanings retained, without production imports |
| Named pump roles, stoichiometry, stall/reversal, off/absent pump | Pass | Species order does not define the pump; signed drive/cycle accounting is explicit |
| Initial species permutations | All 6 + 24 orderings agree exactly on this CPU | Storage order independence on these small scalar fixtures, not universal GPU bitwise equivalence |
| Algebraic material and charge ledgers | Largest material residual 9.33e-15 fmol; charge residual 7.51e-14 V | Material/charge interfaces agree without integrating a timestep |
| Open-system energy rate | All eight checked assembled states pass | Chemical plus capacitor rate equals supplied power minus dissipation |
| Inactive divalent route | Zero flux, unchanged anchor, correct voltage response to its amount | Turning off transport does not remove charge |

Normalized error is `abs(actual - expected) / (atol + rtol * abs(expected))`;
the pass limit is one. The largest normalized arithmetic residual across all
comparison groups is approximately 0.00933, in algebraically constructed amount
ledgers. These are arithmetic limits, not biological thresholds.

The initial Na/K/Cl passive fluxes are approximately
`[0.03959637, -0.01691466, 0.000536006]` fmol/s, with pump rate
`0.01882748` fmol cycles/s. In the divalent case its added inward passive flux
is approximately `0.000101843` fmol/s. These are synthetic instantaneous values,
not a calcium transient, equilibrium, relaxation time or measured-cell result.

Both fixtures explicitly supply fixed charge and assert an initial -65 mV
anchor. The direct initial-charge voltage residuals are approximately
-8.30e-14 and -1.76e-13 V, below the predeclared 1e-10 V consistency limit.
Neither fixed charge nor chloride was silently recalculated to obtain a pass.
The bath background represents maintained charge support, not identified
chemistry, osmolarity or a finite reservoir inventory.

## Verification and retained development issue

Commands from the Cells directory, using the existing CPU environment:

```bash
.venv/bin/python scripts/check_multispecies_contract.py --output reports/spec-005-design-check.json
.venv/bin/pytest -q tests/unit/test_multispecies_reference.py tests/unit/test_biological_benchmark.py tests/unit/test_conditioned_voltage.py tests/unit/test_bioelectric_reference.py tests/unit/test_bioelectric_cell.py
.venv/bin/ruff check tests/reference_multispecies.py scripts/check_multispecies_contract.py tests/unit/test_multispecies_reference.py
```

The receipt path is exclusive: rerun without `--output` or choose a new path.
The receipt records Python 3.13.5, NumPy 2.5.3 and SciPy 1.18.1, source hashes,
the input hash, tolerances, check groups and initial resolved states. NumPy/SciPy
are used by the old independent reference; the new scalar reference is stdlib-only.
The combined targeted regression passed **352 tests in 54.89 seconds**. This
time measures tests, not simulator throughput. Lint and formatting pass. The
historical full 2,178-test suite was **not** rerun; no new full-suite result is claimed.

The first unit-test run had 104 passes and three failures because receipt
metadata incorrectly named a nonexistent `uv.lock`. The project actually uses
`requirements-lock.txt` and `requirements-reference.txt`. Correcting that
source list restored all 107 then-existing tests; six additional domain tests
bring the new total to 113. No fixture, tolerance or physical law changed to
address those failures. Fault-injection tests separately demonstrate that an
incorrect flux sign produces retained failed checks, not a success receipt.

The frozen input SHA-256 is
`a5b267af9f88f218673e585ba1e3e575a9a85cb567ae24d3542721e13cfe6f34`.
The physical specification retains its pre-evaluation SHA-256
`f3729c43c2a03d833400c70435b50826821f72af7de5726169dcc5d74a1f5bc6`.
All **219 pre-existing files captured at the start** retain their hashes,
including all **39 production sources**, prior tests/reference scripts,
configuration/data files, old electrical specifications and original BIO-002
result files. Dependency files and package version remain unchanged.

## Next gate: NUM-006

Freeze a small multispecies trajectory panel and numerical/resource policy
before running it. Begin with the two specified assemblies and elementary
passive-only, pump-only, all-off and block/release controls. Compare independent
CPU integration methods and refinement; check internal stages, positive amounts,
off-grid events, material/charge/energy histories and observation error. Qualify
the new divalent regime explicitly: even its dimensionless voltage domain
differs from the old monovalent domain. Do not inherit the old RK4 timestep.

Only afterward should CORE-006 add a newly identified production assembly,
pure-array execution and complete restart acceptance. Finite environments,
channel/calcium signaling, fields, spatial partitions, multirate solvers and GPU
runtime remain separate stages in the
[capability roadmap](../docs/BETSE_CAPABILITY_ROADMAP.md). The descriptive pilot,
unfinished source E02 gates and the pause on optimization/long campaigns remain
unchanged. No biological parameters became identifiable through these tests.
