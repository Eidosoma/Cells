<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Replacement over water accounts for incoming volume and composition-dependent free energy

For a donor copy, transfer of the donor's volume increment preserves its physical volume when reference volumes agree. Adding the water term to the chemical energy at the declared volume evaluates all tracked species at the physical volume. A composition change can give nonzero water free energy even at zero net volume transfer.

## Assumptions

- All cell volumes and the reference volume are positive. The finite-species ideal chemical identity assumes positive amounts. Each site keeps its own elastic pressure law and fixed extra impermeant amount.
- The donor and receiver have the same declared water compartment and initial reference volume. Species amounts and physical volume are read at the two endpoints of the event.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CellReplacement.gross_balance](../CellsProofs/Tissue/CellReplacement.lean#L37)
- [CellsProofs.Tissue.CellReplacement.donor_volume](../CellsProofs/Tissue/CellReplacement.lean#L69)
- [CellsProofs.Tissue.CellReplacement.ideal_at_volume](../CellsProofs/Tissue/CellReplacement.lean#L75)
- [CellsProofs.Tissue.CellReplacement.physical_endpoint](../CellsProofs/Tissue/CellReplacement.lean#L88)
- [CellsProofs.Tissue.CellReplacement.water_jump](../CellsProofs/Tissue/CellReplacement.lean#L97)
- [CellsProofs.Tissue.CellReplacement.same_volume_water_jump](../CellsProofs/Tissue/CellReplacement.lean#L106)

Direct proof subject `cells.operator.scheduled_cell_replacement@2`

Uses [Simultaneous replacement books the old and arriving species, charge and electrical work](scheduled-cell-replacement.md) · [Water potential sets flow, heat and osmometric equilibrium](osmotic-water.md)

## Numerical comparison

**Checked.** The copy stayed at 0.788048 pL, gained 1.1003 fmol of tracked osmoles and booked −0.138369 pJ of water free energy. The template changed both amount and volume at the other site. The largest combined energy discrepancy was 4.32 × 10⁻¹³ pJ against 2 × 10⁻¹¹ pJ. A three-step checked run reproduced both gross volume bookings.

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_cell_replacement@2`, `cells.ideal_osmosis_linear_compliance_water@1`

[Gross volume, donor copy and water booking](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement_v2.py#L99) · [Per-node water free energy](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/osmotic_water.py#L299) · [Equal donor compartment admission](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement_v2.py#L186) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/checks/cell_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/PROGRESS.md#cell-replacement-water)

[Tested engine 4638694ac13b](https://github.com/Eidosoma/Cells/commit/4638694ac13bedae5f93aa56d77cf8820e687ec1) · [Evidence checkpoint ddb723080dee](https://github.com/Eidosoma/Cells/commit/ddb723080dee6544576464afaf5314a3b95e2b06)

## Biological evidence

**Open.** Paired volume before removal and after arrival at the same site, with intracellular osmoles and mechanical or osmotic work.

**Unit** pL per cell, µm³ per division, % of baseline volume and pJ per event

### xie2020_paired_epidermal_volumes@1

Mouse basal epidermal cells were followed in vivo at 12-hour intervals. The register stores the paired figure readings in µm³. Supplement page 4, panel marked S2L. Eleven line segments pair the mitotic parent with both daughters at the next frame. [Xie and Skotheim (2020), Fig. S2L](https://doi.org/10.1016/j.cub.2019.12.062)

- **Evidence role** descriptive

The paired changes had a sample SD of 100 µm³. The authors report 9.1 ± 8.6% repeat-segmentation error overall. Imaging spans a full frame interval.

Mean volume was 770 µm³ for each parent and 677 µm³ for the sum of its daughters, with nine of eleven pairs decreasing. The paired change averaged −94 µm³. This measures division and leaves the same-site replacement volume and work open. [Dataset manifest](../checks/data/cell_replacement_measurements.json) · [Comparison verdict](../PROGRESS.md#cell-replacement-water)

### mitchell2025_extruding_cell_volume@1

MDCKII epithelial monolayers experienced a 20% hypertonic shock. Cells were grouped by subsequent extrusion or retention. Figure 1l and the accompanying results give the change in GFP-derived cytoplasmic volume. [Mitchell et al. (2025), Fig. 1l](https://doi.org/10.1038/s41586-025-09514-w)

- **Evidence role** descriptive

Values are mean ± SEM. The caption reports n = 5.

Cells subsequently extruded lost 20 ± 3% of baseline volume and retained cells lost 11 ± 2.5%. The assay measures outgoing shrinkage. Incoming absolute volume, osmole counts and work remain open. [Dataset manifest](../checks/data/cell_replacement_measurements.json) · [Comparison verdict](../PROGRESS.md#cell-replacement-water)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
