<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Uncharged membrane insertion dissipates nonnegative capacitor heat

The exact network heat in pJ is (10¹²/2) times the sum of C(ΔV)² + ΔC(V + ΔV)² over patches and every allocated patch share is nonnegative. For a single patch against a held bath, the heat is (10¹²/2) C V² ΔC/(C + ΔC) and the bath supplies zero image charge during insertion.

## Assumptions

- Inserted membrane arrives uncharged. Each free node keeps its charge and each held node keeps its potential. The network is finite and the voltage changes obey its capacitor equations.
- C and ΔC are nonnegative, expressed in F, with positive starting C in the one-patch formula. V and ΔV are in volts. The proof uses real arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Tissue.MembraneInsertion.node_patch_work](../CellsProofs/Tissue/MembraneInsertion.lean#L24)
- [CellsProofs.Tissue.MembraneInsertion.fixed_node_balance](../CellsProofs/Tissue/MembraneInsertion.lean#L33)
- [CellsProofs.Tissue.MembraneInsertion.heat_eq_squares](../CellsProofs/Tissue/MembraneInsertion.lean#L46)
- [CellsProofs.Tissue.MembraneInsertion.heat_nonneg](../CellsProofs/Tissue/MembraneInsertion.lean#L55)
- [CellsProofs.Tissue.MembraneInsertion.share_nonneg](../CellsProofs/Tissue/MembraneInsertion.lean#L68)
- [CellsProofs.Tissue.MembraneInsertion.one_patch_heat](../CellsProofs/Tissue/MembraneInsertion.lean#L75)
- [CellsProofs.Tissue.MembraneInsertion.one_patch_image_zero](../CellsProofs/Tissue/MembraneInsertion.lean#L82)

Direct proof subject `cells.operator.scheduled_membrane_insertion@1`, `cells.operator.scheduled_membrane_insertion@2`

## Numerical comparison

**Checked.** Both versions passed all seven half-step cases and completed the original extreme one-patch rollout. At ΔC/C = 1.7 × 10¹⁶ both booked +0.051603097344170144 pJ, against +0.05160309734417014 pJ from the 80-digit calculation. The earlier refusal and diagnostic substitutions are retained below.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `scheduled_membrane_insertion@1`, `scheduled_membrane_insertion@2`, `membrane_entity_state@1`

[Selection of the stable insertion calculation](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/membrane_insertion.py#L416) · [Heat and image calculation in the extreme branch](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/membrane_insertion.py#L471) · [Second-version half-step](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/membrane_insertion_v2.py#L369) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/membrane_insertion.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-engine-review)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `scheduled_membrane_insertion@1`, `scheduled_membrane_insertion@2`, `membrane_entity_state@1`

[Fixed-charge energy and plate charge](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/models/pump_composite_adapter.py#L966) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/membrane_insertion.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#six-numerical-retests)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `scheduled_membrane_insertion@1`, `scheduled_membrane_insertion@2`, `membrane_entity_state@1`

[Fixed-charge field, heat and image charge](https://github.com/Eidosoma/Cells/blob/06e25525a39f3a2995bd5aa26a7e38bd67b211c3/src/cells/models/pump_composite_adapter.py#L959) · [Version 1 heat sign check](https://github.com/Eidosoma/Cells/blob/06e25525a39f3a2995bd5aa26a7e38bd67b211c3/src/cells/operators/membrane_insertion.py#L424) · [Version 2 heat sign check](https://github.com/Eidosoma/Cells/blob/06e25525a39f3a2995bd5aa26a7e38bd67b211c3/src/cells/operators/membrane_insertion_v2.py#L244) · [One-patch fixture](https://github.com/Eidosoma/Cells/blob/06e25525a39f3a2995bd5aa26a7e38bd67b211c3/tests/membrane_insertion_fixtures.py#L28) · [One-patch reference and tolerance](https://github.com/Eidosoma/Cells/blob/06e25525a39f3a2995bd5aa26a7e38bd67b211c3/tests/unit/test_membrane_insertion.py#L144) · [Two-version comparison](https://github.com/Eidosoma/Cells/blob/06e25525a39f3a2995bd5aa26a7e38bd67b211c3/tests/unit/test_membrane_insertion_v2.py#L203) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/6c495445518af429c1c163a374a3a25abef4c062/lean/checks/membrane_insertion.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/6c495445518af429c1c163a374a3a25abef4c062/lean/PROGRESS.md#19-november-2026--membrane-insertion-heat)

[Tested engine 06e25525a39f](https://github.com/Eidosoma/Cells/commit/06e25525a39f3a2995bd5aa26a7e38bd67b211c3) · [Evidence checkpoint 6c495445518a](https://github.com/Eidosoma/Cells/commit/6c495445518af429c1c163a374a3a25abef4c062)

## Biological evidence

**Open.** Membrane capacitance, patch voltage and clamp charge during a characterized insertion event, with the incoming membrane’s initial charge accounted for.

Capacitance steps were measured during secretion in chromaffin cells. Testing insertion heat also needs the initial charge of the added membrane and independent electrical work and energy measurements. [Neher and Marty](https://doi.org/10.1073/pnas.79.21.6712)

**Unit** pJ for heat, C for image charge

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
