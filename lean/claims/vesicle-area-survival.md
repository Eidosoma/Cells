<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Vesicle area variation bounds survival during a tension hold

Under a common hazard per unit area, survival evaluated at the initial mean area bounds the cohort’s survival from below. The linear interpolation of the two endpoint survivals at that mean bounds it from above. An endpoint mixture attains the upper bound.

## Assumptions

- Every vesicle has fixed area during observation, the same integrated hazard per unit area and single-vesicle survival exp(−qA). The initial finite cohort weights are nonnegative and sum to one.
- For the upper bound, L and U are actual limits on the same initial cohort’s areas and L < U. If L = U the common single-area result is exact. Positive exposure and unequal areas with positive weights give a strict lower bound.
- For spherical vesicles the required mean area is 4π times the mean of squared radii. Inferring area from a mean radius alone requires further information. D293’s set-2 allowance addresses area differences across preparations. The bound here concerns the survival curve within one cohort.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleArea.at_mean_le](../CellsProofs/Chemistry/VesicleArea.lean#L18)
- [CellsProofs.Chemistry.VesicleArea.at_mean_lt](../CellsProofs/Chemistry/VesicleArea.lean#L26)
- [CellsProofs.Chemistry.VesicleArea.endpoint_mixture](../CellsProofs/Chemistry/VesicleArea.lean#L42)
- [CellsProofs.Chemistry.VesicleArea.le_chord](../CellsProofs/Chemistry/VesicleArea.lean#L54)
- [CellsProofs.Chemistry.VesicleArea.population_le_chord](../CellsProofs/Chemistry/VesicleArea.lean#L68)
- [CellsProofs.Chemistry.VesicleArea.one_area](../CellsProofs/Chemistry/VesicleArea.lean#L80)

Proof sources [Mathlib exponential convexity and strict convexity, imported for survival](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/SpecificFunctions/Basic.lean#L37-L60) · [Mathlib finite Jensen inequality and its strict form, specialized to initial cohort weights](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/Jensen.lean#L63-L100) · [D293 records a separate area allowance across preparations for the registered blind test](https://github.com/Eidosoma/Cells/blob/562cc9b4ec5225089feee26cab3ad2ef42405e02/docs/DECISIONS.md#d293-the-rupture-blind-tests-stage-1-rulings-made-before-any-prediction-or-held-out-value) · [Cells tagged FR-31 law sheet, area scaling and survival](https://github.com/Eidosoma/Cells/blob/57cf9a4ed0b68454232a3c531c14e1b725853955/docs/VESICLE_PORES_LAWS.md#5-the-area-and-the-clock)

## Numerical comparison

**Open.** Four synthetic calculations passed. With mean area 2 and range 1 to 3, the lower and upper bounds are 1/4 and 5/16 at the selected exposure. Two cohorts give 5/16 and 9/32. Equal areas and zero exposure give equality. An FR-31 engine comparison is pending.

**Reference calculation**

[Declared area scaling and fixed-tension survival](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/docs/VESICLE_PORES_LAWS.md#5-the-area-and-the-clock) · [Finite-cohort survival bound and endpoint construction](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/CellsProofs/Chemistry/VesicleArea.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/checks/vesicle_area.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2/lean/PROGRESS.md#fr31-area-bounds)

[Evidence checkpoint e4b729acf7e7](https://github.com/Eidosoma/Cells/commit/e4b729acf7e784cd088a3a9f05da4de42d5e8dd2)

**Reference calculation**

[Area scaling and survival at a fixed tension](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/docs/VESICLE_PORES_LAWS.md#5-the-area-and-the-clock) · [Published verdict of the separate registered blind test](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/docs/DECISIONS.md#d298-the-vesicle-rupture-blind-test-passes-set-1-five-of-five-set-2-five-of-five-one-sided-weak) · [Neutral DOPC plateau and linked ruptures](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/data/shibly2016_swelling.json) · [Charged vesicle rupture and independent swelling groups](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/data/saha2020_osmotic_rupture.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/checks/vesicle_area.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78/lean/PROGRESS.md#fr31-osmotic-rupture)

[Evidence checkpoint cecbe3627a7a](https://github.com/Eidosoma/Cells/commit/cecbe3627a7a9a0bc37ae7a4b3d2b5f29f828c78)

## Biological evidence

**Open.** Initial vesicle areas from the same at-risk population, held tension, and time to first rupture or censoring per vesicle. Linked observations would quantify the mean-area approximation.

Shibly et al. link relative swelling and rupture in selected neutral-DOPC traces. Saha et al. compare charged-vesicle rupture and swelling in separate cohorts. Neither supplies absolute starting areas with outcomes across the full at-risk cohort.

**Unit** Surviving fraction at a stated exposure

### shibly2016_dopc_rupture_traces@1

Neutral DOPC vesicles at 25 ± 1 °C, held at 4 mN/m aspiration after a 3 mM osmotic difference. Figure 4A, with Figure 4B as the pre-equilibrium comparison [Shibly et al. (2016), Biophysical Journal](https://doi.org/10.1016/j.bpj.2016.09.043)

- **Evidence role** descriptive

The paper gives 0.0086 ± 0.0002 for fractional plateau radius change (17 vesicles), without identifying the statistic here. The mean area modulus is 218 ± 26 mN/m (SD).

Relative radius and rupture are paired on displayed traces. Individual absolute areas and complete event or censor times are still missing. [Dataset manifest](../checks/data/shibly2016_swelling.json) · [Comparison verdict](../PROGRESS.md#fr31-osmotic-rupture)

### saha2020_charged_vesicle_rupture@1

DOPG/DOPC 40:60 vesicles in 150 mM NaCl at 25 ± 1 °C. The rupture group used 12 mOsm/L and the closest swelling group used 13 ± 5 mOsm/L. Figure 1B and Table 1 for rupture, Figure 2 and Table 3 for swelling [Saha, Shibly and Yamazaki (2020), Journal of Physical Chemistry B](https://doi.org/10.1021/acs.jpcb.0c03681)

- **Evidence role** descriptive

Rates are means and SDs of 4–5 repeats, each with 20–25 vesicles. Geometry-based osmotic tension at 13 mOsm/L was 3.0 ± 0.1 mN/m. The ±5 mOsm/L is estimated osmolarity error.

Rupture rate rose 6.52-fold over the applied 3.5–4.5 mN/m range. The independent swelling estimate comes from a different cohort. Rate-matched tension uses the rupture data themselves. [Dataset manifest](../checks/data/saha2020_osmotic_rupture.json) · [Comparison verdict](../PROGRESS.md#fr31-osmotic-rupture)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
