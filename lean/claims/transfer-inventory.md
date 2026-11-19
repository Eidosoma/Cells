<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Only boundary transfers change a region’s inventory during transport

Internal edges cancel when transfers are summed over a region. On the entire closed graph each species and any charge-weighted sum are conserved.

## Assumptions

- Each edge transfers equal amounts between its two endpoints. A held bath needs an external supply term when included in an inventory.

## Lean proof

**Proved**

- [CellsProofs.Accounting.region_balance](../CellsProofs/Accounting/Transfer.lean#L42)
- [CellsProofs.Accounting.total_balance](../CellsProofs/Accounting/Transfer.lean#L53)
- [CellsProofs.Accounting.charge_balance](../CellsProofs/Accounting/Transfer.lean#L59)

## Numerical comparison

**Checked.** The closed tissue run checked the potassium ledger, including membrane, pump and channel contributions. The chain comparison exercised both entering and leaving transfers on a four-compartment region.

**Engine** `resolved_pump_tissue@3`, `constant_field@1`

[Junction flux](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/junctions/selective.py#L19) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/laws/electrochemistry.py#L17) · [Flux booking](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/src/cells/numerics/surface_transport.py#L318) · [Surface comparisons](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_transport.py#L103) · [Per-cell tissue ledger](https://github.com/Eidosoma/Cells/blob/109a7355ed85ff2e1e5a9c884c32801c07a2fd72/tests/unit/test_surface_pump_v3_imex.py#L80) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/checks/constant_field.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd/lean/README.md#cpu-comparison)

[Tested engine 109a7355ed85](https://github.com/Eidosoma/Cells/commit/109a7355ed85ff2e1e5a9c884c32801c07a2fd72) · [Evidence checkpoint 627c376c463a](https://github.com/Eidosoma/Cells/commit/627c376c463ae66c0f9e53db6dbb1374ec8ac1fd)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `local_species_reactions@1`, `logmean_electrodiffusion@1`

[Split-step order](https://github.com/Eidosoma/Cells/blob/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801/src/cells/models/pump_composite.py#L1308) · [Closed pair](https://github.com/Eidosoma/Cells/blob/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801/validation/morphogenesis/mg0c_turing.py#L180) · [Independent trajectory comparison](https://github.com/Eidosoma/Cells/blob/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801/tests/unit/test_species_reactions_composition.py#L84) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9252236d3f6339d4dfdd18fd79fc1d73246faf7e/lean/checks/regional_balance.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9252236d3f6339d4dfdd18fd79fc1d73246faf7e/lean/PROGRESS.md#19-november-2026--regional-reaction-and-transport-balance)

[Tested engine 030bd02a5f4b](https://github.com/Eidosoma/Cells/commit/030bd02a5f4bb74d15ef8bde4fdf1db03f69b801) · [Evidence checkpoint 9252236d3f63](https://github.com/Eidosoma/Cells/commit/9252236d3f6339d4dfdd18fd79fc1d73246faf7e)

## Biological evidence

**Open.** Change in regional ion amount and net ion transfer across its boundary over the same interval.

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
