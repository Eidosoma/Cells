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

Direct proof subject `cells.bilayer_geometry@1`

Proof sources [Mathlib cross-multiplication at nonzero denominators, imported for the leaflet area criterion](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L426-L427)

## Numerical comparison

**Checked.** A 64-lipid control calibrated to fluid POPC at 30 °C gave 20.576 nm² and an empty lumen. In two compiled 96-event trajectories with different molecular weights for two lipids, every recorded integer footprint matched the independent count sum. A 32-fold refinement preserved the molecule counts across all 98 records.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Molecular areas in integer quanta](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/geometry.py#L123) · [Physical bilayer area](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/geometry.py#L245) · [Compiled count-weighted footprint](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L322) · [Saved footprint at each row](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L635) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#bilayer-footprint)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

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
