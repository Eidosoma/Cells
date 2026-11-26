<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Bilayer area is half the sum of the molecular footprints in its two leaflets

The integer footprint adds across lipid inventories. Refining the area unit preserves the physical area. A common per-lipid error bound gives a bilayer area bound of half the total lipid count times that error. The area-equivalent sphere gives the same volume from its radius and its area. For two spherical headgroup surfaces with measured positive radii and lipid counts, equal area per head holds exactly when the inner lipid fraction equals the inner surface-area fraction.

## Assumptions

- Each membrane species has a fixed footprint expressed in integer quanta. Both leaflets contribute to the counted lipid inventory.
- When the quantum is refined by a positive integer factor, every lipid’s integer weight and the integer floor scale by that factor. The physical quantum scales inversely.
- The geometric reference is the sphere at the given area. A deflated vesicle can have a different shape and a smaller enclosed volume.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.footprint_add](../CellsProofs/Chemistry/Vesicle.lean#L25)
- [CellsProofs.Chemistry.Vesicle.footprint_refine](../CellsProofs/Chemistry/Vesicle.lean#L30)
- [CellsProofs.Chemistry.Vesicle.area_refine](../CellsProofs/Chemistry/Vesicle.lean#L35)
- [CellsProofs.Chemistry.Vesicle.area_error_bound](../CellsProofs/Chemistry/Vesicle.lean#L40)
- [CellsProofs.Chemistry.Vesicle.radius_area](../CellsProofs/Chemistry/Vesicle.lean#L61)
- [CellsProofs.Chemistry.Vesicle.sphere_radius](../CellsProofs/Chemistry/Vesicle.lean#L66)
- [CellsProofs.Chemistry.Vesicle.sphere_area](../CellsProofs/Chemistry/Vesicle.lean#L72)
- [CellsProofs.Chemistry.Vesicle.equal_leaflet_footprint_iff](../CellsProofs/Chemistry/Vesicle.lean#L200)

Direct proof subject `cells.assembly_geometry.bilayer_geometry@1`

Proof sources [Mathlib cross-multiplication at nonzero denominators, imported for the leaflet area criterion](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L426-L427)

## Numerical comparison

**Checked.** A 64-lipid control calibrated to fluid POPC at 30 °C gave 20.576 nm² and an empty lumen. In two compiled 96-event trajectories with different molecular weights for two lipids, every recorded integer footprint matched the independent count sum. A 32-fold refinement preserved the molecule counts across all 98 records. At a fixed 30 °C POPC footprint, the same native 64-lipid system gave 20.576 nm² at 30 and 50 °C. Using the 50 °C footprint gave 21.536 nm².

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Molecular areas in integer quanta](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/geometry.py#L123) · [Physical bilayer area](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/geometry.py#L245) · [Compiled count-weighted footprint](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L322) · [Saved footprint at each row](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L635) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#bilayer-footprint)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`

[Input molecular footprints](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/models/assembly_lineages_v2/geometry.py#L113) · [Area from counted footprint](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/models/assembly_lineages_v2/geometry.py#L249) · [Compiled count-weighted footprint](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/models/assembly_lineages_v2/kernel.py#L326) · [Footprints from the host run](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/models/assembly_lineages_v2/runner.py#L1013) · [Empty lumen convention](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/src/cells/models/assembly_lineages_v2/lumen.py#L159) · [Closed world fixture](https://github.com/Eidosoma/Cells/blob/1e40fc16ade2244aa45a3f18f3055dd60819a2e7/tests/unit/test_assembly_lineages_v2_lumen.py#L59) · [Leaflet surface and lipid fractions](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/CellsProofs/Chemistry/Vesicle.lean) · [POPC temperature and egg-PC leaflet measurements](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/checks/data/leaflet_packing.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/checks/leaflet_packing.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/22587f8d5e38ae18d775b7a65c91fb10e9277991/lean/PROGRESS.md#paired-calibration-and-leaflet-packing)

[Tested engine 1e40fc16ade2](https://github.com/Eidosoma/Cells/commit/1e40fc16ade2244aa45a3f18f3055dd60819a2e7) · [Evidence checkpoint 22587f8d5e38](https://github.com/Eidosoma/Cells/commit/22587f8d5e38ae18d775b7a65c91fb10e9277991)

**Engine** `cells.assembly_lineages@2`, `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.pool_withdrawal@1`, `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`, `cells.scheduled_species_exchange@1`

[Bilayer area](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/geometry.py#L249) · [Lumen tension and volume](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/lumen.py#L265) · [Deterministic rupture decision](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/kernel.py#L350) · [Bead-equivalent count withdrawal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/withdrawal.py#L150) · [Full wash at a bound wall](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/wash_schedule.py#L472) · [Saturable uptake](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/species_exchange.py#L335) · [Potassium reversal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L55) · [Paired measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_wet_lab_measurements.json) · [Potassium changes in Müller cells](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Kir4.1 temperature and concentrations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/tada1998_kir41.json) · [POPC molecular areas](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/leaflet_packing.json) · [First independent deflation study](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fujiwara2014_vesicle.json) · [Survival during a tension hold](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/vesicle_rupture_holds.json) · [First bead-count groups](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fornell2017_partition.json) · [Remaining bead counts and volume observations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pool_withdrawal_measurements.json) · [Bilayer area harness](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/leaflet_packing.py) · [Vesicle world](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle.py) · [Retained-osmole comparison](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle_events.py) · [Whole draw and site stocks](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/wall_wash.py) · [Pool event and count reconstruction](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_response_endpoints.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Open.** Area per lipid at known composition and temperature, and total bilayer area in a vesicle with independently determined lipid counts.

- [One fixed molecular footprint describes fluid POPC across a roughly 20 °C temperature increase.](../WET_LAB_EVIDENCE.md#pair-popc-temperature-footprint) · Challenged by both studies
- [The inner and outer headgroup surfaces of a small spherical egg-PC vesicle have equal area per lipid.](../WET_LAB_EVIDENCE.md#pair-egg-pc-leaflet-packing) · Comparison unresolved

Fluid POPC footprints increased with temperature in two independent measurements. Two egg-PC studies constrain how curved leaflets pack, although the reported data leave equal inner and outer area per lipid unresolved.

**Unit** nm² per lipid

### kucerka2011_popc@1

Fluid phosphatidylcholine bilayers characterized by joint small-angle neutron and X-ray scattering. The POPC row at 30 °C supplies the per-lipid area. Equation 2 explains the uncertainty. [Kučerka, Nieh and Katsaras (2011), Table 1](https://doi.org/10.1016/j.bbamem.2011.07.022)

- **Evidence role** calibration
- **Fit** Fluid POPC molecular footprint at 30 °C
- **Observed** 0.643 nm² per lipid

The reported uncertainty is ±0.013 nm² per lipid.

This calibrates the area of each lipid. An independent whole-vesicle check would require both its total lipid count and its measured membrane area. [Dataset manifest](../checks/data/kucerka2011_popc.json) · [Comparison verdict](../PROGRESS.md#bilayer-footprint)

### kucerka2011_popc_temperature@1

Area inferred from joint neutron and X-ray scattering. The 30 °C entry is also the existing Cells calibration. Table 1, pure POPC at 30 and 50 °C, with Eq. 2 [Kučerka, Nieh and Katsaras (2011), Table 1 temperature series](https://doi.org/10.1016/j.bbamem.2011.07.022)

- **Evidence role** calibration
- **Fit** 30 °C and 50 °C molecular footprints used as inputs to their respective native replays

The authors give ±1.3 Å² at both temperatures. The 30 °C entry also appears in the pre-existing calibration record.

The mean area rises from 64.3 to 67.3 Å² per lipid between 30 and 50 °C. These measurements can supply temperature-specific input footprints. [Dataset manifest](../checks/data/leaflet_packing.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### leftin2014_popc_temperature@1

Molecular areas inferred from chain order using the mean-torque model. The SDs propagate repeated dipolar-coupling measurements. Table 1, pure POPC, carbon-13 NMR columns [Leftin et al. (2014), Table 1, ¹³C NMR](https://doi.org/10.1016/j.bpj.2014.07.044)

- **Evidence role** descriptive

Propagated SDs are 3.6 and 4.2 Å². The area inference uses the authors’ chain-order model.

The mean POPC footprint rises from 60.4 to 70.5 Å² over 28–48 °C. The different endpoints and methods limit comparison of thermal expansion coefficients. [Dataset manifest](../checks/data/leaflet_packing.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### finer1971_egg_pc@1

Fraction II of sonicated egg-yolk lecithin. External manganese broadened the solvent-accessible choline proton signal. p. 333, paragraph following Fig. 2 [Finer, Flook and Hauser (1971), p. 333](https://doi.org/10.1016/0014-5793(71)80479-9)

- **Evidence role** descriptive

No error reported on the protected fraction. The cited geometry is external to the NMR sample.

The protected headgroup fraction was 0.28. Using outer radius 115 Å and thickness 46 Å from Huang (1969) gives an equal-footprint fraction of 0.2647. The authors interpreted this as compatible with equal areas. [Dataset manifest](../checks/data/leaflet_packing.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

### huang1978_egg_pc@1

Homogeneous egg phosphatidylcholine vesicles. The group combined its earlier phosphorus NMR and hydrodynamic measurements. Methods and Tables 1–2, pp. 308–309 [Huang and Mason (1978), Tables 1–2](https://doi.org/10.1073/pnas.75.1.308)

- **Evidence role** descriptive

Table 1 input errors were at most 5% according to the authors. Table 2 gives rounded inferences without propagated intervals.

An outer:inner NMR ratio of 2.1 gives an inner fraction of 0.3226. Radii of 62 and 99 Å give 0.2817 at equal footprint. Their inferred outer and inner molecular areas were 74 and 61 Å². [Dataset manifest](../checks/data/leaflet_packing.json) · [Comparison verdict](../PROGRESS.md#paired-calibration-and-leaflet-packing)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
