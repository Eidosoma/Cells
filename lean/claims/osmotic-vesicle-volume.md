<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Membrane area caps the volume that minimizes a vesicle’s osmotic free energy

At fixed solute count, area and bath osmolarity, the equilibrium volume is the smaller of the ideal osmotic volume and the spherical volume allowed by the membrane. Tension vanishes below the cap. Once the cap is reached, further bath dilution raises tension while volume stays fixed.

## Assumptions

- The bath is held, internal osmoles are conserved during equilibration, temperature is fixed, and water equilibrates rapidly. The minimum over positive volumes requires positive solute count, bath density, molecular standard and spherical capacity. The empty lumen is assigned zero volume and zero osmotic energy.
- The membrane has fixed area within a bath comparison. Reduced volume divides by the spherical volume at that area. The ideal osmotic term uses particle density.
- For the POPC transfer test, the first observation fixes the effective trapped solute per spherical volume. For the DOPC swelling transfer, the first group fixes a common volume reserve. The separate tension estimate uses an initially spherical inextensible membrane at the reported radius.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.energy_strict_min](../CellsProofs/Chemistry/Vesicle.lean#L101)
- [CellsProofs.Chemistry.Vesicle.empty_lumen](../CellsProofs/Chemistry/Vesicle.lean#L122)
- [CellsProofs.Chemistry.Vesicle.slack_stall](../CellsProofs/Chemistry/Vesicle.lean#L126)
- [CellsProofs.Chemistry.Vesicle.slack_tension](../CellsProofs/Chemistry/Vesicle.lean#L135)
- [CellsProofs.Chemistry.Vesicle.laplace](../CellsProofs/Chemistry/Vesicle.lean#L142)
- [CellsProofs.Chemistry.Vesicle.reduced_volume](../CellsProofs/Chemistry/Vesicle.lean#L151)
- [CellsProofs.Chemistry.Vesicle.tension_at_density](../CellsProofs/Chemistry/Vesicle.lean#L157)
- [CellsProofs.Chemistry.Vesicle.capped_bath_change](../CellsProofs/Chemistry/Vesicle.lean#L162)

Direct proof subject `cells.free_energy.osmotic_lumen@1`

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Water potential sets flow, heat and osmometric equilibrium](osmotic-water.md)

## Numerical comparison

**Checked.** Two compiled trajectories each crossed between 34 slack and 64 tense records. Across both runs the relative volume error stayed below 1.07 × 10⁻¹⁴, tension error below 2.24 × 10⁻¹⁷ N/m, and osmotic energy error below 2.54 × 10⁻¹⁴ k_BT against a 70-digit reference. Separate 64-osmole worlds reproduce the macroscopic reduced-volume and tension-per-radius predictions at matched density.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Repaired tension at the cap](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py) · [Tension test at each event](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [Volume and tension in the run record](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/runner.py) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [test assembly lineages v2 lumen](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_lumen.py) · [kucerka2011 popc](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/kucerka2011_popc.json) · [wolfisberg2025 vesicle](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/wolfisberg2025_vesicle.json) · [shibly2016 swelling](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/shibly2016_swelling.json) · [vesicle rupture holds](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/vesicle_rupture_holds.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Spherical and osmotic volume constants](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L86) · [Equilibrium volume and free energy](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L114) · [Tension from the pressure difference](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L164) · [Volume and tension in the run record](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L649) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#osmotic-vesicle-volume)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

**Engine** `cells.assembly_lineages@2`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`

[Osmotic equilibrium volume](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/lumen.py) · [Physical membrane area](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/geometry.py) · [Compiled single-lineage runner](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/src/cells/models/assembly_lineages_v2/runner.py) · [Fixed-osmole world fixture](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/tests/unit/test_assembly_lineages_v2_lumen.py) · [World and execution definition](https://github.com/Eidosoma/Cells/blob/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25/tests/assembly_lineage_v2_fixtures.py) · [Two-bath 64-osmole comparison](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/checks/vesicle.py) · [Study inputs and tracer measurements](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/checks/data/fujiwara2014_vesicle.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/checks/vesicle_events.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7e126375842ef23f0eb29734847cfe1dffd5ac4c/lean/PROGRESS.md#intact-vesicle-deflation)

[Tested engine 87e81f56366b](https://github.com/Eidosoma/Cells/commit/87e81f56366b5d06bd2abd45ebd2bb45a70f8b25) · [Evidence checkpoint 7e126375842e](https://github.com/Eidosoma/Cells/commit/7e126375842ef23f0eb29734847cfe1dffd5ac4c)

**Engine** `cells.assembly_lineages@2`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`

[Osmotic equilibrium volume](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py) · [Membrane geometry](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/geometry.py) · [Compiled lineage runner](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/runner.py) · [Pinned vesicle fixture, geometry, concentrations](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_lumen.py) · [World and execution definition](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [Bhatia single-vesicle geometry and bath](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/bhatia2020_vesicle_deflation.json) · [64-osmole compiled comparison at a specified cap density](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle.py) · [Geometric outer-volume bound](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/CellsProofs/Chemistry/Vesicle.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle_events.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#bhatia-vesicle-deflation)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.pool_withdrawal@1`, `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`, `cells.scheduled_species_exchange@1`

[Bilayer area](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/geometry.py#L249) · [Lumen tension and volume](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/lumen.py#L265) · [Deterministic rupture decision](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/kernel.py#L350) · [Bead-equivalent count withdrawal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/withdrawal.py#L150) · [Full wash at a bound wall](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/wash_schedule.py#L472) · [Saturable uptake](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/species_exchange.py#L335) · [Potassium reversal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L55) · [Paired measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_wet_lab_measurements.json) · [Potassium changes in Müller cells](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Kir4.1 temperature and concentrations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/tada1998_kir41.json) · [POPC molecular areas](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/leaflet_packing.json) · [First independent deflation study](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fujiwara2014_vesicle.json) · [Survival during a tension hold](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/vesicle_rupture_holds.json) · [First bead-count groups](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fornell2017_partition.json) · [Remaining bead counts and volume observations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pool_withdrawal_measurements.json) · [Bilayer area harness](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/leaflet_packing.py) · [Vesicle world](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle.py) · [Retained-osmole comparison](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle_events.py) · [Whole draw and site stocks](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/wall_wash.py) · [Pool event and count reconstruction](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_response_endpoints.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Mixed.** Equilibrium volume after a bath osmolarity change, measured relative to the same vesicle’s spherical capacity or its initial volume, as specified for each study.

- [Increasing external osmolarity reduces the enclosed volume of intact, solute-loaded vesicles.](../WET_LAB_EVIDENCE.md#pair-vesicle-deflation-direction) · Supported by both studies
- [The optically measured relaxed radius is a hard cap on spherical vesicle size during hypotonic swelling before rupture.](../WET_LAB_EVIDENCE.md#pair-vesicle-resting-radius-cap) · Challenged by both studies
- [The retained-osmole volume ratio transfers quantitatively from freely suspended to adhered deflating vesicles.](../WET_LAB_EVIDENCE.md#pair-vesicle-ideal-volume-transfer) · Comparison unresolved

**Unit** volume ratio

### viallat2004_sucrose_deflation@1

One electroformed DOPC vesicle remained spherical during slow external glucose titration. The experiment also continued with separate gel-filled vesicles. Fig. 2, slow sucrose-vesicle results and accompanying text. [Viallat et al. (2004), Fig. 2](https://doi.org/10.1016/S0006-3495(04)74277-0)

- **Evidence role** descriptive

Rounded radii for one vesicle. No pointwise errors. The plotted internal pressure assumes retained sucrose.

The ratio (17/25)³ = 0.314 is close to the nominal 50/162 = 0.309. The spherical surface area declined during this observation. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### chabanon2017_closed_swelling@1

Giant POPC vesicles with 1 mol% fluorescent lipid, under a 200 mM hypotonic differential. Experimental Fig. 1c–d and Movie S2. [Chabanon et al. (2017), Fig. 1c–d](https://doi.org/10.1016/j.bpj.2017.03.018)

- **Evidence role** descriptive

Representative optical trace. The estimate of relaxed radius and unmeasured membrane slack limit inference of molecular area.

Radius increased above the relaxed reference during closed swelling phases before pore opening. This observation limits use of the relaxed radius as a fixed size cap. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### fujiwara2014_vesicle_deflation@1

The five tracked liposomes started at 70 mOsm/L internally and shrank in a 285 mOsm/L bath. Final over initial volume is the reciprocal of the approximately fourfold inverse-volume plateau. A separate paired series follows GFP concentration and volume within the same liposome. Figures 2–3 and supplementary Figures S2–S3. [Fujiwara and Yanagisawa (2014), ACS Synthetic Biology](https://doi.org/10.1021/sb4001917)

- **Evidence role** held out from fitting
- **Evaluation** Plateau volume ratio using the prepared osmolarities, with no fitted parameter
- **Excluded** The time taken to shrink, An independent inventory of smaller osmoles
- **Observed** 0.25 volume ratio
- **Predicted** 0.2456 volume ratio

The plateau is approximate and has no stated standard error. Volumes were estimated from diameters. Individual ten-minute inverse volume ratios in Figure S2 span about 3.3–4.9.

The intact-liposome plateau agrees at the reported precision. The paired GFP measurement supports retention of the protein during shrinkage. [Dataset manifest](../checks/data/fujiwara2014_vesicle.json) · [Comparison verdict](../PROGRESS.md#intact-vesicle-deflation)

### bhatia2020_single_vesicle_deflation@1

The same trapped vesicle was imaged across a 66 to 72 mM bath change. Bath-origin liquid in an inward tube contributes to the outer contour volume. The ratio here divides final lumen by the measured starting volume. Figure 2 and the Movie S1 caption in the supplement. [Bhatia, Robinson and Dimova (2020), Soft Matter](https://doi.org/10.1039/D0SM00155D)

- **Evidence role** held out from fitting
- **Evaluation** Outer-contour upper bound and a straight-cylinder estimate for the inward tube
- **Excluded** The separate Figure 4 bath change, A direct measure of small-solute retention

The final outer volume alone carries a stated uncertainty of about 1,000 µm³. The tube dimensions have no pointwise uncertainty.

Inconclusive. The central outer-contour bound is 0.756. A cylindrical tube gives 0.705, versus a retained-osmole prediction of 0.917. The reported volume uncertainty spans the difference. [Dataset manifest](../checks/data/bhatia2020_vesicle_deflation.json) · [Comparison verdict](../PROGRESS.md#bhatia-vesicle-deflation)

### wolfisberg2025_deflation@1

One POPC vesicle weakly adhered by 0.4% PEG was tracked through sequential hypertonic bath changes. The prepared lumen contained 25 mM sucrose. Five paired osmolarity and reduced-volume labels printed below the confocal reconstructions. [Wolfisberg et al. (2025), Fig. 2B](https://doi.org/10.1021/jacs.5c13925)

- **Evidence role** held out from fitting
- **Fit** 26 mOsm/L, measured reduced volume 0.98
- **Evaluation** 32, 46, 58 and 83 mOsm/L on the same vesicle
- **Observed** 0.3 volume ratio
- **Predicted** 0.4393 volume ratio

At 58 mOsm/L the label reads 0.30. Label rounding is ±0.005 and reported bath precision is ±2 mOsm/L. The paper gives no point-specific geometry uncertainty for Figure 2B.

The displayed pair is the 58 mOsm/L step after calibration at the first observation. All four later volumes were lower than predicted. Using prepared sucrose with no fit gave 0.431 at this step. [Dataset manifest](../checks/data/wolfisberg2025_vesicle.json) · [Comparison verdict](../PROGRESS.md#osmotic-vesicle-volume)

### shibly2016_dopc_swelling@1

Micropipette-held giant DOPC vesicles were transferred from an isotonic 98 mM bath to 96 or 95 mM glucose. Volumes here are relative to each group’s initial volume. The volume-increase measurements accompany Fig. 2B. [Shibly et al. (2016), Fig. 2B](https://doi.org/10.1016/j.bpj.2016.09.043)

- **Evidence role** held out from fitting
- **Fit** 96 mM group, 1.7% swelling
- **Evaluation** 95 mM group, 2.6% swelling
- **Observed** 1.026 volume ratio
- **Predicted** 1.017 volume ratio

Reported swelling was 1.7 ± 0.1% (14 vesicles) and 2.6 ± 0.1% (17 vesicles). The statistic for ±0.1 was unspecified. Transferring one area reserve across groups is an additional assumption.

The fixed-area model reaches its fitted limit at the first dilution and underestimates swelling at the second. An initially full sphere predicts zero swelling in both baths. [Dataset manifest](../checks/data/shibly2016_swelling.json) · [Comparison verdict](../PROGRESS.md#osmotic-vesicle-volume)

### shibly2016_osmotic_tension@1

A separate DOPC experiment at an initial osmotic difference of 1.9 mM and radius of 13.4 µm. Table 1 estimates the osmotic tension by matching rupture rates to isotonic aspiration controls. [Shibly et al. (2016), Table 1](https://doi.org/10.1016/j.bpj.2016.09.043)

- **Evidence role** descriptive

The reported osmotic tension was 2.6 ± 0.1 mN/m and initial radius 13.4 ± 0.2 µm. Tension was inferred from the rate measurements.

The initially spherical fixed-area model predicts 31.56 mN/m at that radius. Swelling and aspirated geometry limit this application of the spherical cap. [Dataset manifest](../checks/data/shibly2016_swelling.json) · [Comparison verdict](../PROGRESS.md#osmotic-vesicle-volume)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
