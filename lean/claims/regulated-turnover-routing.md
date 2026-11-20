<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Regulated turnover rates stay bounded and a changing regulator can give first-order production

A product of route factors in [0, 1] keeps the applied rate between zero and its scheduled maximum. When turnover produces its own regulator, taking a fresh Hill factor at the start of each target half-step can give first-order error in accumulated product.

## Assumptions

- The scheduled rate is nonnegative. Each factor is evaluated in its declared range at the state received by the target half-step.
- In the counterexample a fixed 1 pL cell starts at 1 mM regulator. The same turnover operator produces the regulator at 1 fmol/s and the reporter at a scheduled 1 fmol/s. Its reporter factor has zero basal activity, Hill exponent 1 and half-saturation 1 mM. Both routes are pure production.
- Time is in seconds on [0, 1]. The target half-steps have uniform width h = dt/2 and an integer number spans the interval. The refinement bound compares accumulated gain on grids of width h and h/2 in exact arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Transport.RegulatedAvailability.routed_rate_bounds](../CellsProofs/Transport/RegulatedAvailability.lean#L119)
- [CellsProofs.Transport.RegulatedAvailability.reread_production](../CellsProofs/Transport/RegulatedAvailability.lean#L132)
- [CellsProofs.Transport.RegulatedAvailability.ramp_reference](../CellsProofs/Transport/RegulatedAvailability.lean#L140)
- [CellsProofs.Transport.RegulatedAvailability.ramp_panel_difference](../CellsProofs/Transport/RegulatedAvailability.lean#L148)
- [CellsProofs.Transport.RegulatedAvailability.ramp_refinement_lower](../CellsProofs/Transport/RegulatedAvailability.lean#L160)

Direct proof subject `cells.species_regulated_availability@2`

Uses [A regulated channel approaches its held-dose plateau without overshoot](regulated-state-response.md) · [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md)

## Numerical comparison

**Failed.** Version 2 reread the Hill factor in both target half-steps. All four ramp worlds accepted and booked their reporter gains. The exact one-second gain was 0.59453489 fmol. For 8, 16, 32 and 64 steps the measured convergence orders were 1.006, 1.003 and 1.002, failing the design’s second-order claim when turnover also changes the regulator. Lean proves that halving the target half-step increases this example’s gain by at least h/36.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.species_regulated_availability@2`, `cells.scheduled_species_turnover@1`

[State supplied to each target half-step](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/models/pump_composite.py#L1499) · [Rate multiplier and applied factor record](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_regulated_availability.py#L1843) · [Target production and clearance booking](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_turnover.py#L246) · [Second-order claim for rate routes](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/docs/INVENTORY_COUPLING_DESIGN.md#L690) · [Second-order claim for scheduled turnover](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/docs/ABUNDANCE_TO_FUNCTION_DESIGN.md#L254) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1/lean/checks/regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1/lean/PROGRESS.md#regulated-turnover-routing)

[Tested engine e297e05feab7](https://github.com/Eidosoma/Cells/commit/e297e05feab76f1ef8295c83996b70de2ea09fa1) · [Evidence checkpoint 6a8bb7ede08a](https://github.com/Eidosoma/Cells/commit/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1)

## Biological evidence

**Open.** An independently measured regulator concentration and absolute product appearance over time in the same well-mixed volume, with an independent calibration of the regulated production rate.

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
