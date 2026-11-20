<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# An empty surface population has zero abundance and channel flow

Removing the full declared number of functional units sets both the normalized abundance and the channel's contribution to zero for any positive patch area. The two-term float64 readout can retain a signed residue.

## Assumptions

- The two initial channel counts are exactly representable, and the state subtracts those counts exactly. The engine accepts the controlled state at each tested area.
- The area changes isolate membrane abundance at fixed capacitance and drive. The comparison measures the rate readout of the prepared state. Reachability and accumulation in a complete trajectory remain open.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PopulationUnits.empty_surface](../CellsProofs/Chemistry/PopulationUnits.lean#L143)
- [CellsProofs.Chemistry.PopulationUnits.whole_patch_flow](../CellsProofs/Chemistry/PopulationUnits.lean#L135)

Direct proof subject `cells.membrane_entity_state@1`

Uses [At fixed channel drive, whole-patch flow tracks the surface unit count](membrane-population-flow.md)

## Numerical comparison

**Failed.** At 1.4 times declared area, zero units still produced abundance −1.11022 × 10⁻¹⁶ and potassium flux −2.19124 × 10⁻¹⁸ fmol/s. At 1.8 times the area the same zero-unit state produced +2.81730 × 10⁻¹⁸ fmol/s. NumPy and compiled CPU showed both signs. At the reference area both outputs were exactly zero.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.membrane_entity_state@1`

[Unit count](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/membrane_state.py#L151) · [Two-term abundance and entity domain](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/membrane_state.py#L158) · [Composite rate readout](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/models/pump_composite.py#L1564) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/population_units.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#empty-surface-flow)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

## Biological evidence

**Open.** The zero-unit case is a numerical identity. Resolving a physiological consequence would require a measurable residual current.

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
