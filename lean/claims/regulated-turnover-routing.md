<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Midpoint sampling restores second-order reporter gain on the self-regulated ramp

A product of route factors in [0, 1] keeps the applied rate between zero and its scheduled maximum. When turnover produces its own regulator, taking a fresh Hill factor at the start of each target half-step can give first-order error in accumulated product. For the same ramp, using its midpoint gives a one-panel refinement difference proportional to the cube of the target stage width, with the exact denominator in the theorem.

## Assumptions

- The scheduled rate is nonnegative. Every applied route factor lies in its declared range. The midpoint comparison uses the half-stage predictor for a source changed by its own turnover target.
- In the counterexample a fixed 1 pL cell starts at 1 mM regulator. The same turnover operator produces the regulator at 1 fmol/s and the reporter at a scheduled 1 fmol/s. Its reporter factor has zero basal activity, Hill exponent 1 and half-saturation 1 mM. Both routes are pure production.
- Time is in seconds on [0, 1]. The target half-steps have uniform width h = dt/2 and an integer number spans the interval. The refinement bound compares accumulated gain on grids of width h and h/2 in exact arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Transport.RegulatedAvailability.routed_rate_bounds](../CellsProofs/Transport/RegulatedAvailability.lean#L119)
- [CellsProofs.Transport.RegulatedAvailability.reread_production](../CellsProofs/Transport/RegulatedAvailability.lean#L132)
- [CellsProofs.Transport.RegulatedAvailability.ramp_reference](../CellsProofs/Transport/RegulatedAvailability.lean#L140)
- [CellsProofs.Transport.RegulatedAvailability.ramp_panel_difference](../CellsProofs/Transport/RegulatedAvailability.lean#L148)
- [CellsProofs.Transport.RegulatedAvailability.ramp_refinement_lower](../CellsProofs/Transport/RegulatedAvailability.lean#L160)
- [CellsProofs.Transport.RegulatedAvailability.ramp_midpoint_difference](../CellsProofs/Transport/RegulatedAvailability.lean#L182)

Direct proof subject `cells.operator.species_regulated_availability@2`

Proof sources [Midpoint evaluation for a self-moved source](../../src/cells/models/pump_composite.py#L1641)

Uses [A regulated channel approaches its held-dose plateau without overshoot](regulated-state-response.md) · [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md)

## Numerical comparison

**Checked.** The left-endpoint engine reproduced first-order convergence on 21 November. On the midpoint revision the compiled gains agreed with independent midpoint sums within 2.23 × 10⁻¹⁶ fmol. Orders on 8, 16, 32 and 64 steps were 1.99973, 1.99993 and 1.99998. The continuous one-second gain is 0.5945348919 fmol. The pulse and the four-grid ramp both passed on main at 68ab12e7.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.species_regulated_availability@1`, `cells.species_regulated_availability@2`, `cells.scheduled_species_turnover@1`

[Target half-step predictor and applied factors](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/models/pump_composite.py#L1642) · [Regulatory reads and recorded factors](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/species_regulated_availability.py) · [Analytic ligand trajectory and continuous gate](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/coupling/state_reference.py) · [Pulse fixture definitions](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/regulated_availability_fixtures.py) · [Turnover world and controls](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/secreted_species_fixtures.py) · [Midpoint regression](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_species_regulated_availability.py#L1300) · [Fixed-calcium SK2 inputs](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/data/hirschberg1998_sk2.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.species_regulated_availability@2`, `cells.scheduled_species_turnover@1`

[Self-moved target selection](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/models/pump_composite.py#L168) · [Half-step midpoint predictor and applied factor](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/models/pump_composite.py#L1641) · [Turnover production booking](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/operators/species_turnover.py) · [Routed operator regression](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/tests/unit/test_species_regulated_availability.py#L1300) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-engine-review)

[Tested engine a6235d7b02c0](https://github.com/Eidosoma/Cells/commit/a6235d7b02c04e147991342c2891eb0c1cd3deb6) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.species_regulated_availability@2`, `cells.scheduled_species_turnover@1`

[State supplied to each target half-step](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/models/pump_composite.py#L1499) · [Rate multiplier and applied factor record](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_regulated_availability.py#L1843) · [Target production and clearance booking](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_turnover.py#L246) · [Second-order claim for rate routes](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/docs/INVENTORY_COUPLING_DESIGN.md#L690) · [Second-order claim for scheduled turnover](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/docs/ABUNDANCE_TO_FUNCTION_DESIGN.md#L254) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1/lean/checks/regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1/lean/PROGRESS.md#regulated-turnover-routing)

[Tested engine e297e05feab7](https://github.com/Eidosoma/Cells/commit/e297e05feab76f1ef8295c83996b70de2ea09fa1) · [Evidence checkpoint 6a8bb7ede08a](https://github.com/Eidosoma/Cells/commit/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1)

## Biological evidence

**Open.** An independently measured regulator concentration and absolute product appearance over time in the same well-mixed volume, with an independent calibration of the regulated production rate.

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
