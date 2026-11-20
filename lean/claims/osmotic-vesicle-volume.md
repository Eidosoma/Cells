<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Membrane area caps the volume that minimizes a vesicle’s osmotic free energy

At fixed solute count, area and bath osmolarity, the equilibrium volume is the smaller of the ideal osmotic volume and the spherical volume allowed by the membrane. Tension vanishes below the cap. Once the cap is reached, further bath dilution raises tension while volume stays fixed.

## Assumptions

- The bath is held, internal osmoles are conserved during equilibration, temperature is fixed, and water equilibrates rapidly. The minimum over positive volumes requires positive solute count, bath density, molecular standard and spherical capacity. The empty lumen is assigned zero volume and zero osmotic energy.
- The membrane has fixed area within a bath comparison. Reduced volume divides by the spherical volume at that area. The ideal osmotic term uses particle density.
- For the POPC transfer test, the first observation fixes the effective trapped solute per spherical volume. For the DOPC swelling transfer, the first group fixes a common volume reserve. The separate tension estimate uses an initially spherical inextensible membrane at the reported radius.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.energy_strict_min](../CellsProofs/Chemistry/Vesicle.lean#L95)
- [CellsProofs.Chemistry.Vesicle.empty_lumen](../CellsProofs/Chemistry/Vesicle.lean#L116)
- [CellsProofs.Chemistry.Vesicle.slack_stall](../CellsProofs/Chemistry/Vesicle.lean#L120)
- [CellsProofs.Chemistry.Vesicle.slack_tension](../CellsProofs/Chemistry/Vesicle.lean#L129)
- [CellsProofs.Chemistry.Vesicle.laplace](../CellsProofs/Chemistry/Vesicle.lean#L136)
- [CellsProofs.Chemistry.Vesicle.reduced_volume](../CellsProofs/Chemistry/Vesicle.lean#L145)
- [CellsProofs.Chemistry.Vesicle.tension_at_density](../CellsProofs/Chemistry/Vesicle.lean#L151)
- [CellsProofs.Chemistry.Vesicle.capped_bath_change](../CellsProofs/Chemistry/Vesicle.lean#L156)

Direct proof subject `cells.osmotic_lumen@1`

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Water potential sets flow, heat and osmometric equilibrium](osmotic-water.md)

## Numerical comparison

**Checked.** Two compiled trajectories each crossed between 34 slack and 64 tense records. Across both runs the relative volume error stayed below 1.07 × 10⁻¹⁴, tension error below 2.24 × 10⁻¹⁷ N/m, and osmotic energy error below 2.54 × 10⁻¹⁴ k_BT against a 70-digit reference. Separate 64-osmole worlds reproduce the macroscopic reduced-volume and tension-per-radius predictions at matched density.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Spherical and osmotic volume constants](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L86) · [Equilibrium volume and free energy](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L114) · [Tension from the pressure difference](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/lumen.py#L164) · [Volume and tension in the run record](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L649) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#osmotic-vesicle-volume)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

## Biological evidence

**Disagrees.** Equilibrium volume after a bath osmolarity change, measured relative to the same vesicle’s spherical capacity or its initial volume, as specified for each study.

**Unit** volume ratio

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
