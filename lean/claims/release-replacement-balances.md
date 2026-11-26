<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Residue and energy accounts at producer replacement

When a departing occupant takes its unfinished chains and attached RNA and a newcomer starts with both empty, recording those exports preserves the residue account. With row and chain standard energies included, the endpoint energy account closes with zero heat assigned to the event. Successive differences of a cumulative counter recover its total change.

## Assumptions

- A stage j complex holds j r residues, a completed product holds m r, and all extents update the same cumulative counters through the last step of the departing occupant.
- Reconstruct incoming and outgoing rows’ mixing and standard energies from the exchanged amounts. Unfinished and attached residues leave at the chain’s standard energy per residue. Reading an individual generation requires both its counter endpoints.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.TerminalRelease.replacement_residue_step](../CellsProofs/Chemistry/TerminalRelease.lean#L69)
- [CellsProofs.Chemistry.TerminalRelease.replacement_energy](../CellsProofs/Chemistry/TerminalRelease.lean#L80)
- [CellsProofs.Chemistry.TerminalRelease.generation_counter](../CellsProofs/Chemistry/TerminalRelease.lean#L91)

Direct proof subject `cells.operator.templated_polymerisation@1`, `cells.operator.scheduled_cell_replacement@1`

Proof sources [FR-38 amendment S, event inventory and energy](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1499) · [Mathlib finite telescoping sum, imported as Finset.sum_range_sub](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L862-L865)

Uses [Stage exits account for residues in unfinished, terminally held and detached chains](polymerisation-residues.md) · [Simultaneous replacement books the old and arriving species, charge and electrical work](scheduled-cell-replacement.md)

## Numerical comparison

**Open.** All 65 current state fields matched byte for byte at four times after a disk checkpoint with occupied stages and hold, for both machine-return policies. The historical replay checked 40 fields. The [producer-labelled replacement replay](producer-replacement-rna.md) checks the departing material and producer identity. The full replacement-event residue and energy reconstruction remains open.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Unlabelled release world](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/validation/gene_regulation/worlds.py#L519) · [Initial rates and copy scale](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/validation/gene_regulation/sheet_check.py) · [Checkpoint at an accepted step](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/execution/runner.py#L362) · [Snapshot writing and reading](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/records/io.py#L86) · [RNA and machine ledgers](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/src/cells/operators/templated_polymerisation.py#L1993) · [Tagged replacement identities](https://github.com/Eidosoma/Cells/blob/2263d11ce5099fca1e58b9285ff4d302bb829fdf/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1499) · [Short observation schedule](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/checks/terminal_release.py) · [Conditional event proofs](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/CellsProofs/Chemistry/TerminalRelease.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/checks/release_restart.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/PROGRESS.md#fr38-retention-window-repair)

[Tested engine 2263d11ce509](https://github.com/Eidosoma/Cells/commit/2263d11ce5099fca1e58b9285ff4d302bb829fdf) · [Evidence checkpoint 7c9feb549f00](https://github.com/Eidosoma/Cells/commit/7c9feb549f00f58432dfc0ac3e8567a289c61255)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Unlabelled release world](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/validation/gene_regulation/worlds.py#L519) · [Initial rates and copy scale](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/validation/gene_regulation/sheet_check.py) · [Checkpoint at an accepted step](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/execution/runner.py#L362) · [Snapshot writing and reading](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/records/io.py#L86) · [RNA and machine ledgers](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/operators/templated_polymerisation.py#L1993) · [Tagged replacement identities](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1499) · [Short observation schedule](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/terminal_release.py) · [Conditional event proofs](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/CellsProofs/Chemistry/TerminalRelease.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/release_restart.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/PROGRESS.md#fr38-replacement-restart)

[Tested engine 5ef761505f2d](https://github.com/Eidosoma/Cells/commit/5ef761505f2dbd48c35e36a2caee391e1f7d9394) · [Evidence checkpoint ddd2dbd0dc2b](https://github.com/Eidosoma/Cells/commit/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2)

**Reference calculation**

[Per-producer counters and replacement balance](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1483-L1515) · [Division of the event reports between the two owners](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/docs/TEMPLATED_POLYMERISATION_LAWS.md#L1773-L1787) · [Cells writes the numerical state and clock to its checkpoint](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/src/cells/records/io.py#L86) · [Reference copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/validation/gene_regulation/sheet_check.py#L96) · [Exact per-producer balance and label partition](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/CellsProofs/Chemistry/ProducerReplacement.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/checks/producer_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/36f778812782bc352a9fe3666c579b85bc87ca28/lean/PROGRESS.md#fr38-producer-replacement)

[Evidence checkpoint 36f778812782](https://github.com/Eidosoma/Cells/commit/36f778812782bc352a9fe3666c579b85bc87ca28)

## Biological evidence

**Open.** The template swap specifies which material leaves a simulated slot. Comparing it with biological inheritance would require a specified physical replacement process and measured outgoing and incoming material.

**Unit** fmol of residues and pJ

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
