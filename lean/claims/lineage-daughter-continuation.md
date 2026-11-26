<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Switching an empty daughter pick to its sibling changes the sampled lineage

For a positive parent, the fallback always retains a nonempty daughter. When one daughter is empty, a fair initial pick retains the whole parent under fallback and half the parent on average if the initial pick stands. For either choice, the followed daughter’s log-weight jump equals minus the split work plus its sibling’s outgoing free energy.

## Assumptions

- The initial choice and the partition are separate. The selection average gives each daughter label equal probability, then applies the declared empty-daughter policy.
- An empty assembly has zero total molecules. A tracer-free daughter can still contain other species. Counts are measured at birth, before further chemical events.
- A daughter at the size threshold divides again if its fission limit allows it. The signed work and sink use the assembly’s log weight with zero log weight for the empty state.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.LineageFission.nonempty_fallback](../CellsProofs/Chemistry/LineageFission.lean#L140)
- [CellsProofs.Chemistry.LineageFission.fallback_selection_bias](../CellsProofs/Chemistry/LineageFission.lean#L147)
- [CellsProofs.Chemistry.LineageFission.zero_quota_at_threshold](../CellsProofs/Chemistry/LineageFission.lean#L155)
- [CellsProofs.Chemistry.LineageFission.log_weight_jump](../CellsProofs/Chemistry/LineageFission.lean#L163)

Direct proof subject `cells.operator.daughter_continuation@1`

Uses [Size-triggered fission conserves each species under fixed-quota and independent partitions](size-threshold-fission.md)

## Numerical comparison

**Checked.** Across 32 equiprobable partition-and-pick outcomes for four molecules, fallback raised mean retained size from 2.00 to 2.25. At quota zero, selecting an empty daughter ended a lineage and following the full sibling gave five immediate re-splits before the limit. The every-descendant run recorded four empty and four full daughter births. The signed energy bookings matched the reference within 3.11 × 10⁻¹⁵ k_BT. The ledger docstring has a sign typo in its derivation.

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`

**Operators** `cells.size_threshold_fission@1`, `cells.daughter_continuation@1`

[Choose a daughter and apply the fallback](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/continuation.py#L98) · [Book work and the outgoing sibling, decide the birth status](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/kernel.py#L365) · [Record both branches of a split](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/runner.py#L682) · [Ledger closure implementation](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/ledger.py#L90) · [Sink sign in the derivation](https://github.com/Eidosoma/Cells/blob/ea073ff872ec64b34346fb01fdc40bb38c8f2861/src/cells/models/assembly_lineages/ledger.py#L38) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4231c96210f7d0f63206ca08b88affab48ac1717/lean/checks/lineage_fission.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4231c96210f7d0f63206ca08b88affab48ac1717/lean/PROGRESS.md#lineage-daughter-continuation)

[Tested engine ea073ff872ec](https://github.com/Eidosoma/Cells/commit/ea073ff872ec64b34346fb01fdc40bb38c8f2861) · [Evidence checkpoint 4231c96210f7](https://github.com/Eidosoma/Cells/commit/4231c96210f7d0f63206ca08b88affab48ac1717)

## Biological evidence

**Open.** Birth sizes and subsequent fates of both daughters, with the rule used to select the tracked daughter recorded for empty as well as occupied outcomes.

The bead experiment in the partition claim measures the cargo of a liquid droplet. Its center-versus-pooled-sides readout cannot identify an empty assembly or which sibling was followed. A direct measurement of this selection effect remains open.

**Unit** molecules in the retained assembly

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
