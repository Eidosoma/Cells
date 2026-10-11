# BIO-002: first conditioned voltage prediction

2026-09-09, D043. **Descriptive endpoint calculation completed; biological
acceptance remains not assessable.** Production Cells remains version 0.10.0.

## Result

Fitting the fixed two-coefficient electrical-response equation to C1/C2 alone
predicts **-14.59 mV** for C3, versus its approximate figure reading of **-18 mV**.
The prediction is 3.41 mV too depolarized. The unchanged-C1 comparator predicts
-39 mV, an absolute discrepancy of 21 mV. This is one retrospective evaluation
condition, not a blinded or prospective experiment.

| Condition | Role | External K (mM) | Approximate measured voltage (mV) | Predicted voltage (mV) |
| --- | --- | --- | --- | --- |
| C1 | Fit | 5.4 | -39 | -39.00 |
| C2 | Fit | 35.4 | -24 | -24.00 |
| C3 | Evaluation only | 65.4 | -18 | -14.59 |

C1/C2 agreement is exact by construction: two points determine two effective
coefficients. It is not validation. C3's dose enters the prediction but its
measured voltage does not enter the fit. C4/C5 remain quarantined for the
published input conflict; no result depends on repairing or scoring them.

The [comparison plot](../runs/bio-002-2026-09-09/endpoint-01/comparison.svg)
shows the response curve, reading-bound sensitivity, approximate observations
and no-response baseline. Unrounded results are in the
[analysis JSON](../runs/bio-002-2026-09-09/endpoint-01/analysis.json) and
[condition CSV](../runs/bio-002-2026-09-09/endpoint-01/conditions.csv).

## Reading-bound sensitivity

Every source voltage has an assigned +/-2 mV figure-reading bound. All four
C1/C2 corner combinations were evaluated without clipping or rejecting a valid
corner. The shared C1 baseline uses the same value in fitting and subtraction.

| Quantity | Central value (mV) | Reading-bound range (mV) |
| --- | --- | --- |
| Predicted C3 voltage | -14.59 | [-18.32, -11.20] |
| Approximate C3 measurement | -18 | [-20, -16] |
| Predicted minus measured C3 | +3.41 | [-2.32, +8.80] |
| Predicted change from C1 | +24.41 | [+18.68, +29.80] |
| Approximate measured change from C1 | +21 | [+17, +25] |
| No-response predicted voltage | -39 | [-41, -37] |
| No-response minus measured C3 | -21 | [-25, -17] |

These are worst-case figure-reading ranges under the assigned bounds, **not
SEMs or confidence intervals**. The nominal prediction falls outside C3's own
reading box; allowing uncertainty in the two fit readings broadens the
prediction enough to overlap that box. Neither observation establishes a
biological pass or failure. Numerical experimental SEM, raw experiment-level
records and dependence between condition summaries remain unavailable in the
curated dataset. Beating the simple no-response baseline does not identify
the mechanism.

## What was built

The [reference specification](../docs/CONDITIONED_VOLTAGE_REFERENCE.md) and
[fixed protocol](../configs/reference/bio002_conditioned_voltage_v1.json) were
written before calculation. The method reduces the passive monovalent GHK
voltage relation, with fixed unknown internal ions and relative permeabilities,
to `exp(V/V_T) = a + b K_external` along this fixed Na+K/Cl series.
The fitted effective coefficients are:

```text
V_T = 25.69257912108585 mV at 298.15 K
a   = 0.18788260474303084
b   = 0.0057923207470123896 mM^-1
```

These coefficients do not uniquely identify permeabilities, internal ions or
a complete cell mechanism. Ca/Mg contribute the unchanged bath's 5.6 mM positive
charge equivalents, but their membrane currents are omitted in this comparator.
Pump and intercellular currents are omitted too. Whole-cell recording is
approximated by fixed internal composition, not modeled pipette dynamics or
intracellular free-ion measurements. Zero applied current is not voltage clamp
or zero current through every ion pathway.

The [pure reference algebra](../tests/reference_conditioned_voltage.py) is
separate from the [dataset adapter and report writer](../scripts/evaluate_conditioned_voltage.py).
It has no case-specific solver branches, target-voltage fitting input, time
integrator, production-model registration or new dependency. This is a static
comparison beside the simulator, not an eighth production cell model or a
prediction of whole-cell homeostasis/recovery dynamics.

## Verification actually run

```bash
.venv/bin/ruff check scripts/evaluate_conditioned_voltage.py tests/reference_conditioned_voltage.py tests/unit/test_conditioned_voltage.py
.venv/bin/ruff format --check scripts/evaluate_conditioned_voltage.py tests/reference_conditioned_voltage.py tests/unit/test_conditioned_voltage.py
.venv/bin/pytest -q -W error tests/unit/test_conditioned_voltage.py tests/unit/test_biological_benchmark.py
.venv/bin/python scripts/evaluate_conditioned_voltage.py --output runs/bio-002-2026-09-09/endpoint-01
```

All **63 targeted tests pass** (48 new reference/adapter checks and the 15
BIO-001 data checks; initial combined run 0.20 s). Coverage includes synthetic
coefficient recovery, decreasing/constant responses, units, invalid domains and
corners, shared-baseline sensitivity, interior-box checks, exclusion/fit
separation, source/protocol mutation rejection, output identities and overwrite
refusal. Test passage has no biological error threshold.
The final warning-strict rerun also passes all 63 tests (0.16 s); lint and
formatting pass. Documentation checks cover nine Markdown files, 561 local
links and 21 tables, with no missing targets, malformed tables, unclosed code
fences or trailing whitespace. Scoped tracked-file whitespace checks pass.

A separate 60-digit Decimal calculation uses the weighted-exponential equation,
not the fitted a/b implementation. The central and four corner voltage/change
comparisons plus two fit residuals all pass: **12 scalar checks**, maximum
absolute discrepancy **7.11e-15 mV**, against the fixed **1e-10 mV numerical**
target. This verifies arithmetic agreement, not experimental plausibility or
a formal interval-arithmetic certificate.

The [saved receipt](../runs/bio-002-2026-09-09/endpoint-01/manifest.json) was
checked against all four payload hashes, all four recorded calculation-source
hashes, all six original dataset files and the copied protocol identity.
The frozen protocol SHA-256 is
`d5f24b40d80083f2b2b4694aee67a1fe21089e578203235d12520ce2ee2982ba`.
The output directory is new; existing outputs are refused, not overwritten.
Running the script without `--output` recomputes and prints JSON without writing
artifacts. Generated run artifacts are local evidence under the ignored `runs/`
directory, not a separately published dataset.

All **39 production source hashes** are unchanged. The original BIO-001 dataset,
its historical no-fit curation metadata and its report/specification are
preserved; this new analysis separately records its C1/C2 fit. Package and
dependency files were not edited. The prior 2,178-test full regression was not
rerun and is not presented as a current full-suite result. No optimization,
GPU setup, long E02 trajectory, source-exploration mutation or external message
was performed.

## Next step

BIO-003 should recover/review experimental uncertainty and assess the
whole-cell recording approximation before any biological acceptance criterion
or production extension. Better source summaries or independent digitization
should get an explicit dataset revision, not overwrite this first result.
Keep C3 out of retuning; if it guides a revised model, label it development data
and obtain a new evaluation condition/dataset. Optimization/GPU work remains
paused and long E02 qualification remains unfinished, with its gates intact.
