<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Vesicle pore rates scale with area and increase on warming

At fixed temperature and tension, the rate of first pore opening is area times a common per-area rate. At fixed area and tension, the logarithmic sensitivity to temperature exceeds 5/2 everywhere the Phase A hold is admitted. Warming between two admitted temperatures therefore increases the rate.

## Assumptions

- The area, tension σ, absolute temperature T, line tension Γ, prefactor and activation energy E_A are positive. The material parameters are fixed as temperature changes. The SI rate uses E_A/R and the tension scale πΓ²/k_B.
- The guard is σ ≤ πΓ²/(4k_BT). Testing it at the hotter endpoint suffices over the interval. Single-vesicle survival assumes a constant hazard up to the observation time.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePore.rate_eq_area_mul](../CellsProofs/Chemistry/VesiclePore.lean#L24)
- [CellsProofs.Chemistry.VesiclePore.hold_survival](../CellsProofs/Chemistry/VesiclePore.lean#L29)
- [CellsProofs.Chemistry.VesiclePore.logRate_hasDerivAt](../CellsProofs/Chemistry/VesiclePore.lean#L36)
- [CellsProofs.Chemistry.VesiclePore.temperature_slope_gt](../CellsProofs/Chemistry/VesiclePore.lean#L51)
- [CellsProofs.Chemistry.VesiclePore.warming_increases_rate](../CellsProofs/Chemistry/VesiclePore.lean#L67)

Direct proof subject `cells.pore_nucleation@1`

Proof sources [Mathlib exp_log, imported for area scaling](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L54) · [Mathlib hasDerivAt_log, imported for the implemented temperature derivative](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Deriv.lean#L47) · [Mathlib strictMonoOn_of_deriv_pos, specialized to the admitted temperatures](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L370) · [Cells pore law and its physical assumptions](https://github.com/Eidosoma/Cells/blob/f51a3b07d302fb177b166b1568155084ffb8e1c1/docs/VESICLE_PORES_LAWS.md#2-the-rupture-law)

Uses [Vesicle area variation bounds survival during a tension hold](vesicle-area-survival.md)

## Numerical comparison

**Checked.** At 300 K, three held tensions including the domain limit gave a doubling ratio of 2.0000000000000036. The scaled slopes ranged from 13.3245 to 33.7982 and agreed with one-sided finite differences. The single founder and both shared-pool founders had the same rate per area within 10⁻¹³ relative tolerance.

**Engine** `cells.assembly_lineages@2`, `cells.pore_nucleation@1`

**Operators** `cells.tension_hold@1`

[Pore rate and temperature slope](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/pore_nucleation.py#L58) · [Tension domain and hold payer](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/tension_hold.py#L88) · [Clock, opening and release](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/pore_clock.py#L82) · [Single-lineage pore event](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/runner.py#L363) · [Population pore event](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/population.py#L665) · [Per-founder random stream and threshold inputs](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/streams.py) · [Geometry and area in both runners](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/src/cells/models/assembly_lineages_v2/geometry.py) · [Closed-form work oracle, founder worlds and both public run modes](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/unit/test_assembly_lineages_v2_pores.py) · [Base assembly run definition](https://github.com/Eidosoma/Cells/blob/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe/tests/assembly_lineage_v2_fixtures.py) · [Exact rate, heat and recorded cutoff proof](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/CellsProofs/Chemistry/VesiclePore.lean) · [Common-exposure survival bounds](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Measured pore observables](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/checks/data/dopc_pore_observables.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/checks/vesicle_pore.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87/lean/PROGRESS.md#fr31-pore-endpoint-repair)

[Tested engine 0a1c1b0dc814](https://github.com/Eidosoma/Cells/commit/0a1c1b0dc8145c9c313c02a4ed57cfe5433b2efe) · [Evidence checkpoint 1c3c422d32a6](https://github.com/Eidosoma/Cells/commit/1c3c422d32a6723d650b2f6d2bc5b531d4a3ff87)

## Biological evidence

**Open.** First-rupture rate at known temperature, tension and initial vesicle area. Separately resolving an opening that reseals would test the assumed equivalence of first opening and terminal rupture.

- [Lysis tension during pressurization gives an independent temperature-resolved first-rupture rate at fixed DOPC tension and area.](../WET_LAB_EVIDENCE.md#pair-rupture-rate-transfer-hold-ramp) · Comparison unresolved

**Unit** first ruptures per intact vesicle per second

### karal2015_dopc_rate_temperatures

The endpoint was complete aspiration. The linked six-row measurement table contains the fit inputs. The independent Cells checker recorded the held-out score in D298. Figure 2a, pure DOPC giant vesicles under constant aspiration tension. [Karal and Yamazaki (2015), Figure 2a](https://doi.org/10.1063/1.4930108)

- **Evidence role** held out from fitting
- **Fit** Six read rates near 25 and 32 °C at 7.0, 7.5 and 8.0 mN/m
- **Evaluation** D298 S1-1 through S1-5, two-sided
- **Excluded** S1-6, a previously quoted condition at 12 °C

Three repeat experiments per setting. The registered typical tolerance was about 0.25 in log rate. The six fit rows had χ² = 98.6 on four degrees of freedom.

Five of five held-out rates passed. Two were below the viscosity calibration range. Individual areas and reversible openings were unresolved. [Dataset manifest](../../validation/vesicle_pores/predictions_registered.json) · [Measurements](../checks/data/karal2015_rupture_rates.json) · [Comparison verdict](../../docs/DECISIONS.md#d298-the-vesicle-rupture-blind-test-passes-set-1-five-of-five-set-2-five-of-five-one-sided-weak)

### olbrich2000_tension_ramp

Giant fluid phosphatidylcholine vesicles were driven to lysis by increasing tension. Micropipette pressurization and composition series at 21 °C. [Olbrich et al. (2000)](https://doi.org/10.1016/S0006-3495(00)76294-1)

- **Evidence role** descriptive

This measurement is lysis tension on a ramp at one temperature. The ramp cohort provides no independent temperature series of constant-tension waiting times.

Mono- and dimono-unsaturated phospholipids lysed around 9–10 mN/m. The data do not determine a DOPC area-normalized first-rupture rate on a hold. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
