<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# An empty surface population has zero abundance and channel flow

Removing the full declared number of functional units sets both the normalized abundance and the channel's contribution to zero for any positive patch area. The two-term float64 readout can retain a signed residue.

## Assumptions

- The two initial channel counts are exactly representable, and the state subtracts those counts exactly. The engine accepts the controlled state at each tested area.
- The controlled states isolate abundance at fixed capacitance and drive. A second comparison follows a scheduled four-step retrieval from the declared initial state of 3,072 Kir units, with synthetic enrichment 1,024 and a total area decrease of 30%.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PopulationUnits.empty_surface](../CellsProofs/Chemistry/PopulationUnits.lean#L143)
- [CellsProofs.Chemistry.PopulationUnits.whole_patch_flow](../CellsProofs/Chemistry/PopulationUnits.lean#L135)

Direct proof subject `cells.membrane_entity_state@1`

Uses [At fixed channel drive, whole-patch flow tracks the surface unit count](membrane-population-flow.md)

## Numerical comparison

**Failed.** Prepared zero-unit states gave potassium flux of −2.19124 × 10⁻¹⁸ and +2.81730 × 10⁻¹⁸ fmol/s at 1.4 and 1.8 times declared area. Scheduled retrieval reached a zero Kir count at 70% of the starting area. At 4 ms its abundance was −2.22045 × 10⁻¹⁶, its potassium flux was −5.58157 × 10⁻¹⁹ fmol/s and the engine refused the observation. The ordinary enrichment and the diagnostic that set abundance to zero at zero count both completed.

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
