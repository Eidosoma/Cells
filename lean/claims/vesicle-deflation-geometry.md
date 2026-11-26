<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# An inward membrane tube reduces the lumen inside a vesicle’s outer contour

Subtracting a nonnegative volume of bath-origin liquid inside an inward tube puts the lumen volume fraction at or below the outer-contour fraction. Geometry measured on the same vesicle can bound a fixed-area osmotic comparison.

## Assumptions

- The initial vesicle has positive volume and no inward tube. At the endpoint the tube occupies a nonnegative volume within the outer contour. The upper bound is independent of its shape.
- The numerical osmometer assumes initial osmotic balance at 66 mM, conserved internal solute and fixed area across the 72 mM challenge. The optional straight-cylinder estimate uses approximate reported dimensions.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Vesicle.invagination_bounds](../CellsProofs/Chemistry/Vesicle.lean#L83)

Direct proof subject `cells.free_energy.osmotic_lumen@1`, `cells.assembly_geometry.bilayer_geometry@1`

Proof sources [Cells outer-volume bound and fixed-area equilibrium](../CellsProofs/Chemistry/Vesicle.lean) · [Figure 2 geometry and compartment definitions](https://doi.org/10.1039/D0SM00155D)

Uses [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](osmotic-vesicle-volume.md)

## Numerical comparison

**Checked.** A compiled 64-osmole world matched to the measured dimensionless loading predicts 4,125 µm³ at the specimen scale. The central outer-volume bound is 0.756 of the measured starting volume. A straight-cylinder estimate gives 0.705.

**Engine** `cells.assembly_lineages@2`, `cells.osmotic_lumen@1`, `cells.bilayer_geometry@1`

[Osmotic equilibrium volume](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/lumen.py) · [Membrane geometry](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/geometry.py) · [Compiled lineage runner](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/runner.py) · [Pinned vesicle fixture, geometry, concentrations](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_lumen.py) · [World and execution definition](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [Bhatia single-vesicle geometry and bath](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/bhatia2020_vesicle_deflation.json) · [64-osmole compiled comparison at a specified cap density](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle.py) · [Geometric outer-volume bound](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/CellsProofs/Chemistry/Vesicle.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle_events.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#bhatia-vesicle-deflation)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

## Biological evidence

**Not assessable.** Volume and total membrane area of the same vesicle before and after an identified osmotic bath change, including the liquid inside its inward tube.

**Unit** µm³ for volume and µm² for area

### bhatia2020_single_vesicle_deflation@1

The same vesicle initially enclosed about 4,500 µm³. Its final outer contour enclosed 3,400.9 ± 1,000 µm³ and contained an inward tube about 18 µm long and 4 µm across. Figure 2, p. 7363. The Movie S1 caption in the publisher supplement, pp. 2–3, identifies the 66 to 72 mM transfer. [Bhatia, Robinson and Dimova (2020), Soft Matter](https://doi.org/10.1039/D0SM00155D)

- **Evidence role** held out from fitting
- **Evaluation** Outer volume as an upper bound on the final lumen, Straight circular tube as a stated geometric approximation
- **Excluded** The separate Figure 4 transfer and its inferred internal concentration, Independent retention of internal osmoles

The reported errors are about 25% for reconstructed area and 33% for volume. No statistical interpretation for the printed ± or independent tube-dimension errors is given.

The central tube-corrected lumen is about 950 µm³ below the 4,125 µm³ prediction. The reported outer-volume uncertainty alone spans that difference. The internal solute inventory was inferred. [Dataset manifest](../checks/data/bhatia2020_vesicle_deflation.json) · [Comparison verdict](../PROGRESS.md#bhatia-vesicle-deflation)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
