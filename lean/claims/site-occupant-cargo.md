<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Replacing occupied sites accounts for departing and arriving bound ligand

For each due population the newcomer carries its template occupancy times its capacity. Site-bound ligand after the event plus departures equals site-bound ligand before the event plus arrivals. Free ligand common to the two sides cancels.

## Assumptions

- The identity isolates the site operator at the event. The host accounts separately for changes to free pools, reactions and binding between rows.
- Each due population has an admitted template and a fixed site capacity. Other populations retain their bound amount.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CellReplacement.occupant_ligand_balance](../CellsProofs/Tissue/CellReplacement.lean#L114)

Direct proof subject `cells.operator.site_occupant_replacement@1`

## Numerical comparison

**Checked.** In the compiled world with occupied sites and ongoing conversion, maximum ligand and product balance residuals were at most 10⁻¹⁵ fmol. Dropping departing ligand from the balance produced the expected deficit. The site-readout regression also read the newcomer’s occupancy after reset. These cargo and occupancy controls passed on 68ab12e7. At the replacement time the exported reaction rate mixed the departing substrate and incoming multiplier. D264 holds that row from scoring.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.site_occupant_replacement@1`, `cells.site_occupancy@1`, `cells.species_regulated_availability@2`

[Site reset and cargo](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/site_occupancy.py#L1820) · [Reaction and replacement fixture](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_site_replacement_runs.py#L101) · [Site-sourced controls and post-reset reads](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_species_regulated_availability.py#L1511) · [Composite observed rows](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/models/pump_composite.py#L2183) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/tests/unit/test_site_replacement_runs.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

**Engine** `resolved_pump_tissue@3`

**Operators** `cells.site_occupant_replacement@1`, `cells.site_occupancy@1`

[Template selection and arrival bounds](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/operators/site_occupancy.py#L1676) · [Departure and arrival bookings](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/operators/site_occupancy.py#L1820) · [Whole-world ligand balance](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/tests/unit/test_site_replacement_runs.py#L64) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/tests/unit/test_site_replacement_runs.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-features)

[Tested engine a6235d7b02c0](https://github.com/Eidosoma/Cells/commit/a6235d7b02c04e147991342c2891eb0c1cd3deb6) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_tissue@3`

**Operators** `cells.site_occupant_replacement@1`, `cells.site_occupancy@1`, `cells.species_regulated_availability@2`

[Readable site quantities](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/operators/species_regulated_availability.py#L1462) · [Template and channel readouts](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/tests/unit/test_species_regulated_availability.py#L1511) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/tests/unit/test_species_regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-features)

[Tested engine a6235d7b02c0](https://github.com/Eidosoma/Cells/commit/a6235d7b02c04e147991342c2891eb0c1cd3deb6) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

## Biological evidence

**Open.** Cross-event inventories of free and occupant-bound ligand with independently measured departing and arriving cargo.

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
