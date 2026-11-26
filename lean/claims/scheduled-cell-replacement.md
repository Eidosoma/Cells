<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Simultaneous replacement books the old and arriving species, charge and electrical work

At each due site the previous occupant leaves and a template or a copy of a pre-event donor enters. Gross supply minus gross removal equals the tissue change for each species. Valence weights give the signed charge. The equal shares of field energy less electrode work sum to one field adjustment.

## Assumptions

- A finite set of tissue sites is replaced simultaneously. Sites outside that set retain their amounts. Copying a donor uses its pre-event amounts, including when that donor is also due.
- Field-energy sharing requires at least one due site. Capacitor energy and held-electrode work enter the formal result as signed inputs. The numerical comparison computes each independently for a sheet with one membrane and one held bath per cell.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CellReplacement.simultaneous_copy](../CellsProofs/Tissue/CellReplacement.lean#L29)
- [CellsProofs.Tissue.CellReplacement.gross_balance](../CellsProofs/Tissue/CellReplacement.lean#L37)
- [CellsProofs.Tissue.CellReplacement.booked_charge](../CellsProofs/Tissue/CellReplacement.lean#L48)
- [CellsProofs.Tissue.CellReplacement.shared_field_energy](../CellsProofs/Tissue/CellReplacement.lean#L54)

Direct proof subject `cells.operator.scheduled_cell_replacement@1`

## Numerical comparison

**Checked.** One cell copied a donor that simultaneously received a template. Gross species transfers, image charge, electrode work and generation replay matched the expected state. The largest per-site free-energy residual was 2.21 × 10⁻¹³ pJ against 2 × 10⁻¹¹ pJ. A three-step checked sheet recorded exactly one exchange at each of the two due sites. D264 separately holds the exported reaction rate at the replacement time.

**Engine** `resolved_pump_composite@1`

**Operators** `cells.scheduled_cell_replacement@1`

[Simultaneous donor and template state](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement.py#L245) · [Charge, field and electrode work](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement.py#L301) · [Once-per-generation schedule](https://github.com/Eidosoma/Cells/blob/4638694ac13bedae5f93aa56d77cf8820e687ec1/src/cells/operators/cell_replacement.py#L327) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/checks/cell_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddb723080dee6544576464afaf5314a3b95e2b06/lean/PROGRESS.md#scheduled-cell-replacement)

[Tested engine 4638694ac13b](https://github.com/Eidosoma/Cells/commit/4638694ac13bedae5f93aa56d77cf8820e687ec1) · [Evidence checkpoint ddb723080dee](https://github.com/Eidosoma/Cells/commit/ddb723080dee6544576464afaf5314a3b95e2b06)

## Biological evidence

**Open.** Time between basal-layer exit and compensating local division, and the species amounts in the departing and arriving cells at one site.

**Unit** days and fmol per cell

### mesa2018_epidermal_neighbor_fates@1

Intravital recordings covered two 90 × 90 µm fields of adult mouse epidermis and counted 524 divisions and 529 differentiations. Figure 3C follows neighboring fates after a basal cell differentiates. [Mesa et al. (2018), Fig. 3C](https://doi.org/10.1016/j.stem.2018.09.005)

- **Evidence role** descriptive

The main panel shows one mouse. The 1.8-day estimate is a fitted coordination time scale.

Neighboring division followed differentiation on a 1.8-day time scale. Cells takes its schedule as an input. The assay leaves the identity and ion inventory of an immediate same-site arrival open. [Dataset manifest](../checks/data/cell_replacement_measurements.json) · [Comparison verdict](../PROGRESS.md#scheduled-cell-replacement)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
