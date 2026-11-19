<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Regional inventory changes by net boundary transfer across a split step

A reaction–transport–reaction step changes a region’s weighted inventory by exactly its signed boundary inflow. The total over a closed graph is conserved.

## Assumptions

- Node identities and the region stay fixed. Every local reaction inside the region balances the inventory. Each transport edge debits and credits its endpoints.

## Lean proof

**Proved**

- [CellsProofs.Tissue.region_inventory_balance](../CellsProofs/Tissue/ReactionTransport.lean#L40)
- [CellsProofs.Tissue.whole_inventory_conserved](../CellsProofs/Tissue/ReactionTransport.lean#L69)

Uses [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md) · [Balanced reactions preserve a weighted inventory](reaction-inventory.md)

## Numerical comparison

**Checked.** In a 50 ms CPU step, the change in A + B across four compartments agreed with boundary inflow within 1.07 × 10⁻¹⁹ fmol. Reversing a crossing face failed the regional check while the whole chain still balanced.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `logmean_electrodiffusion@1`

**Operators** `local_species_reactions@1`

[Split-step order](https://github.com/Eidosoma/Cells/blob/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801/src/cells/models/pump_composite.py#L1308) · [Closed pair](https://github.com/Eidosoma/Cells/blob/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801/validation/morphogenesis/mg0c_turing.py#L180) · [Independent trajectory comparison](https://github.com/Eidosoma/Cells/blob/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801/tests/unit/test_species_reactions_composition.py#L84) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9252236d3f6339d4dfdd18fd79fc1d73246faf7e/lean/checks/regional_balance.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9252236d3f6339d4dfdd18fd79fc1d73246faf7e/lean/PROGRESS.md#19-november-2026--regional-reaction-and-transport-balance)

[Tested engine 030bd02a5f4b](https://github.com/Eidosoma/Cells/commit/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801) · [Evidence checkpoint 9252236d3f63](https://github.com/Eidosoma/Cells/commit/9252236d3f6339d4dfdd18fd79fc1d73246faf7e)

## Biological evidence

**Open.** Change in the amount of a named chemical group inside a defined tissue region and its net passage across that boundary over the same interval.

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
