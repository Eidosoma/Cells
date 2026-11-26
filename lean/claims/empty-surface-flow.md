<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# An empty surface population has zero abundance and channel flow

Removing the full declared number of functional units sets both the normalized abundance and the channel's contribution to zero for any positive patch area. The original two-term float64 readout retained a signed residue at certain areas.

## Assumptions

- The two initial channel counts are exactly representable, and the state subtracts those counts exactly. The engine accepts the controlled state at each tested area.
- The controlled states isolate abundance at fixed capacitance and drive. A second comparison follows a scheduled four-step retrieval from the declared initial state of 3,072 Kir units, with synthetic enrichment 1,024 and a total area decrease of 30%.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PopulationUnits.empty_surface](../CellsProofs/Chemistry/PopulationUnits.lean#L143)
- [CellsProofs.Chemistry.PopulationUnits.whole_patch_flow](../CellsProofs/Chemistry/PopulationUnits.lean#L135)

Direct proof subject `cells.operator.membrane_entity_state@1`

Uses [At fixed channel drive, whole-patch flow tracks the surface unit count](membrane-population-flow.md)

## Numerical comparison

**Checked.** Six prepared states at three area ratios on NumPy and JAX CPU gave exact zeros for abundance and potassium flux. The retrieval rollout completed and every zero-count observation through 4 ms had exactly zero abundance and flux.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.membrane_entity_state@1`

[Exact zero-count abundance](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/operators/membrane_state.py#L159) · [Composite readout](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/models/pump_composite.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9dad3f26380e6ac11f25016eb1a33ae62aff1dbb/lean/checks/population_units.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9dad3f26380e6ac11f25016eb1a33ae62aff1dbb/lean/PROGRESS.md#nov21-engine-review)

[Tested engine a6235d7b02c0](https://github.com/Eidosoma/Cells/commit/a6235d7b02c04e147991342c2891eb0c1cd3deb6) · [Evidence checkpoint 9dad3f26380e](https://github.com/Eidosoma/Cells/commit/9dad3f26380e6ac11f25016eb1a33ae62aff1dbb)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kir2p1_mh2@1`, `cells.nav1p2_m3h_regularized@1`

**Operators** `cells.scheduled_membrane_trafficking@1`, `cells.cell_owned_compartments@1`, `cells.membrane_entity_state@1`

[Redistribution and retrieval](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/membrane_trafficking.py) · [Zero-count abundance](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/membrane_state.py#L159) · [Tissue host observations](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/models/surface_pump_v3.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/compartment_trafficking.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-engine-review)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.membrane_entity_state@1`

[Unit count](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/membrane_state.py#L151) · [Two-term abundance and entity domain](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/membrane_state.py#L158) · [Composite rate readout](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/models/pump_composite.py#L1564) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/population_units.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#empty-surface-flow)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kir2p1_mh2@1`, `cells.nav1p2_m3h_regularized@1`

**Operators** `cells.scheduled_membrane_trafficking@1`, `cells.cell_owned_compartments@1`, `cells.membrane_entity_state@1`

[Fraction withdrawn during retrieval](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/membrane_trafficking.py#L646) · [Unit count and two-term abundance](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/operators/membrane_state.py#L151) · [Host observation refusal](https://github.com/Eidosoma/Cells/blob/b30e3298523e49bd6c33bba01aa11561f8fba449/src/cells/models/surface_pump_v3.py#L2870) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/checks/compartment_trafficking.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5/lean/PROGRESS.md#trafficking-empty-surface)

[Tested engine b30e3298523e](https://github.com/Eidosoma/Cells/commit/b30e3298523e49bd6c33bba01aa11561f8fba449) · [Evidence checkpoint bad3c2a2f8b6](https://github.com/Eidosoma/Cells/commit/bad3c2a2f8b69d739c8f60a2f6e334e0bd187bd5)

## Biological evidence

**Open.** The zero-unit case is a numerical identity. Resolving a physiological consequence would require a measurable residual current.

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
