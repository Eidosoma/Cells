<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Mixing two solutions of unequal positive concentration releases heat in the cleft

For each species in an ideal isothermal fill, mixing heat is the bath’s chemical and pressure work minus the cleft’s free-energy increase. Heat vanishes at equal concentration and is strictly positive for a positive addition of a different concentration. Both concentration ratios in the entropy formula remain positive.

## Assumptions

- Initial volume, both concentrations and temperature are positive. The added bath volume is nonnegative. Strictly positive heat also requires positive added volume and unequal concentrations.
- The comparison uses an isolated neutral tracer and a bath at 310 K. The energy reference evaluates the endpoint ideal-solution expression to 75 decimal digits.

## Lean proof

**Proved**

- [CellsProofs.Tissue.RestrictedLumen.phi_nonneg](../CellsProofs/Tissue/RestrictedLumen.lean#L63)
- [CellsProofs.Tissue.RestrictedLumen.residual_ratios](../CellsProofs/Tissue/RestrictedLumen.lean#L78)
- [CellsProofs.Tissue.RestrictedLumen.heat_nonneg](../CellsProofs/Tissue/RestrictedLumen.lean#L90)
- [CellsProofs.Tissue.RestrictedLumen.heat_pos](../CellsProofs/Tissue/RestrictedLumen.lean#L96)
- [CellsProofs.Tissue.RestrictedLumen.heat_same](../CellsProofs/Tissue/RestrictedLumen.lean#L108)
- [CellsProofs.Tissue.RestrictedLumen.heat_entropy](../CellsProofs/Tissue/RestrictedLumen.lean#L120)
- [CellsProofs.Tissue.RestrictedLumen.energy_booking](../CellsProofs/Tissue/RestrictedLumen.lean#L133)

Direct proof subject `cells.restricted_cleft_lumen@1`, `cells.restricted_cleft_lumen@2`

Uses [Fluid from a held bath dilutes a growing cleft in proportion to its added volume](cleft-bath-fill.md) · [A held bath can return to its original composition after supplying solute and work to tissue](scheduled-bath-exchange.md)

## Numerical comparison

**Failed.** At 1 and 2⁻⁶⁰ mM, in either orientation, the heat evaluator rounds one fractional deviation to −1 and produces NaN. Both versions refuse the first fill. The reference gives +0.00245660 or +0.00618054 pJ. Replacing only nonfinite heat with the direct positive-ratio form in memory lets all four complete, within 2.09 × 10⁻¹⁷ pJ of cumulative reference heat.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.membrane_entity_state@1`, `cells.scheduled_membrane_insertion@1`, `cells.scheduled_membrane_insertion@2`, `cells.restricted_cleft_lumen@1`, `cells.restricted_cleft_lumen@2`

[Entropy term at a fractional concentration change](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen.py#L242) · [Mixing heat and pressure work](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen.py#L251) · [Version 1 finite-heat guard](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen.py#L329) · [Version 2 call to the shared heat calculation](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen_v2.py#L236) · [Version 2 finite-heat guard](https://github.com/Eidosoma/Cells/blob/d16976560e255eba8ff600068a326a0946e22f62/src/cells/operators/restricted_lumen_v2.py#L261) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/e106a3da24cbd8443c3b3cb60091e4820b8a1375/lean/checks/restricted_lumen.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/e106a3da24cbd8443c3b3cb60091e4820b8a1375/lean/PROGRESS.md#cleft-mixing-heat)

[Tested engine d16976560e25](https://github.com/Eidosoma/Cells/commit/d16976560e255eba8ff600068a326a0946e22f62) · [Evidence checkpoint e106a3da24cb](https://github.com/Eidosoma/Cells/commit/e106a3da24cbd8443c3b3cb60091e4820b8a1375)

## Biological evidence

**Open.** Heat released on mixing, with independently measured cleft and added volumes, solute concentrations and temperature. A local calorimetric measurement is still needed.

**Unit** pJ

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
