<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Bilayer area is half the sum of the molecular footprints in its two leaflets

The integer footprint adds across lipid inventories. Refining the area unit preserves the physical area. A common per-lipid error bound gives a bilayer area bound of half the total lipid count times that error. The area-equivalent sphere gives the same volume from its radius and its area.

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

Direct proof subject `cells.bilayer_geometry@1`

## Numerical comparison

**Checked.** A 64-lipid control calibrated to fluid POPC at 30 °C gave 20.576 nm² and an empty lumen. In two compiled 96-event trajectories with different molecular weights for two lipids, every recorded integer footprint matched the independent count sum. A 32-fold refinement preserved the molecule counts across all 98 records.

**Engine** `cells.assembly_lineages@2`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

[Molecular areas in integer quanta](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/geometry.py#L123) · [Physical bilayer area](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/geometry.py#L245) · [Compiled count-weighted footprint](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/kernel.py#L322) · [Saved footprint at each row](https://github.com/Eidosoma/Cells/blob/9d03bd2bd907a3c48bb43679b8e05c392df9adac/src/cells/models/assembly_lineages_v2/runner.py#L635) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/checks/vesicle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c/lean/PROGRESS.md#bilayer-footprint)

[Tested engine 9d03bd2bd907](https://github.com/Eidosoma/Cells/commit/9d03bd2bd907a3c48bb43679b8e05c392df9adac) · [Evidence checkpoint b2dea374a2d2](https://github.com/Eidosoma/Cells/commit/b2dea374a2d2bcba5c6eb860dd7e42bd263e628c)

## Biological evidence

**Open.** Area per lipid at known composition and temperature, and total bilayer area in a vesicle with independently determined lipid counts.

**Unit** nm² per lipid

### kucerka2011_popc@1

Fluid phosphatidylcholine bilayers characterized by joint small-angle neutron and X-ray scattering. The POPC row at 30 °C supplies the per-lipid area. Equation 2 explains the uncertainty. [Kučerka, Nieh and Katsaras (2011), Table 1](https://doi.org/10.1016/j.bbamem.2011.07.022)

- **Evidence role** calibration
- **Fit** Fluid POPC molecular footprint at 30 °C
- **Observed** 0.643 nm² per lipid

The reported uncertainty is ±0.013 nm² per lipid.

This calibrates the area of each lipid. An independent whole-vesicle check would require both its total lipid count and its measured membrane area. [Dataset manifest](../checks/data/kucerka2011_popc.json) · [Comparison verdict](../PROGRESS.md#bilayer-footprint)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
