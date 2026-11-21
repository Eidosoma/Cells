<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A regulated channel approaches its held-dose plateau without overshoot

At fixed input a two-state gate stays in [0, 1] and moves toward its steady open fraction. Splitting a constant dose preserves its endpoint. For positive closing rate the rise time constant equals the zero-input washout time constant multiplied by one minus the plateau.

## Assumptions

- The starting state lies in [0, 1]. During a half-step the opening rate a = k_on × input and the closing rate b are nonnegative and fixed. If both vanish, the state stays fixed. The time-constant relation requires b > 0 and complete removal of opening drive on washout.
- An enabled route maps a factor f to basal + (1 − basal)f with basal in [0, 1]. The switch-off value is one. The upstream Hill ordering applies at positive concentration, half-saturation and exponent.
- For the SK2 comparison the state is absolute open probability with zero basal opening. A single Hill input sets the opening rate, the closing rate is calcium-independent, and the single-channel and macropatch recordings share model parameters.

## Lean proof

**Proved**

- [CellsProofs.Transport.RegulatedAvailability.half_step_eq](../CellsProofs/Transport/RegulatedAvailability.lean#L25)
- [CellsProofs.Transport.RegulatedAvailability.state_derivative](../CellsProofs/Transport/RegulatedAvailability.lean#L39)
- [CellsProofs.Transport.RegulatedAvailability.no_overshoot](../CellsProofs/Transport/RegulatedAvailability.lean#L46)
- [CellsProofs.Transport.RegulatedAvailability.state_bounds](../CellsProofs/Transport/RegulatedAvailability.lean#L63)
- [CellsProofs.Transport.RegulatedAvailability.constant_input_split](../CellsProofs/Transport/RegulatedAvailability.lean#L73)
- [CellsProofs.Transport.RegulatedAvailability.washout](../CellsProofs/Transport/RegulatedAvailability.lean#L76)
- [CellsProofs.Transport.RegulatedAvailability.timing_identity](../CellsProofs/Transport/RegulatedAvailability.lean#L80)
- [CellsProofs.Transport.RegulatedAvailability.steady_hill](../CellsProofs/Transport/RegulatedAvailability.lean#L88)
- [CellsProofs.Transport.RegulatedAvailability.route_bounds](../CellsProofs/Transport/RegulatedAvailability.lean#L104)
- [CellsProofs.Transport.RegulatedAvailability.route_mono](../CellsProofs/Transport/RegulatedAvailability.lean#L112)

Direct proof subject `cells.species_regulated_availability@1`, `cells.species_regulated_availability@2`

Proof sources [grn-lean activation monotonicity](https://github.com/marpaia/grn-lean/blob/070ba8da6a09bdc4b0550396c61611668768bc0b/GRN/Dynamics/Sensor.lean#L30) · [grn-lean inhibition monotonicity](https://github.com/marpaia/grn-lean/blob/070ba8da6a09bdc4b0550396c61611668768bc0b/GRN/Dynamics/Sensor.lean#L51) · [Optional Cells proof for both monotone responses with basal availability](../checks/hill/Response.lean#L46)

Uses [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md)

## Numerical comparison

**Checked.** On six pulse-and-washout runs the gate agreed with the stage-by-stage solution within 4.45 × 10⁻¹⁶. For version 2 the analytic half-step midpoints recovered the recorded second reporter factor within 4.45 × 10⁻¹⁶ and cumulative gains within 6.08 × 10⁻¹⁸ fmol. Sampling the half-step starts missed the factor by up to 0.053925. The fixed-calcium SK2 comparison also replayed. D264 holds the separate exported instantaneous site-routed reaction rate.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.species_regulated_availability@1`, `cells.species_regulated_availability@2`, `cells.scheduled_species_turnover@1`

[Target half-step predictor and applied factors](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/models/pump_composite.py#L1642) · [Regulatory reads and recorded factors](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/operators/species_regulated_availability.py) · [Analytic ligand trajectory and continuous gate](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/coupling/state_reference.py) · [Pulse fixture definitions](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/regulated_availability_fixtures.py) · [Turnover world and controls](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/secreted_species_fixtures.py) · [Midpoint regression](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_species_regulated_availability.py#L1300) · [Fixed-calcium SK2 inputs](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/data/hirschberg1998_sk2.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

**Engine** `resolved_pump_tissue@3`

**Operators** `cells.site_occupant_replacement@1`, `cells.site_occupancy@1`, `cells.species_regulated_availability@2`

[Readable site quantities](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/src/cells/operators/species_regulated_availability.py#L1462) · [Template and channel readouts](https://github.com/Eidosoma/Cells/blob/a6235d7b02c04e147991342c2891eb0c1cd3deb6/tests/unit/test_species_regulated_availability.py#L1511) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/tests/unit/test_species_regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-features)

[Tested engine a6235d7b02c0](https://github.com/Eidosoma/Cells/commit/a6235d7b02c04e147991342c2891eb0c1cd3deb6) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.species_regulated_availability@1`, `cells.species_regulated_availability@2`, `cells.scheduled_species_turnover@1`

[Route factor, basal availability and switch](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_regulated_availability.py#L1075) · [Frozen-input regulatory state update](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_regulated_availability.py#L1121) · [Channel and operator factor records](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/src/cells/operators/species_regulated_availability.py#L1822) · [Independent continuous-time state and exposure integration](https://github.com/Eidosoma/Cells/blob/e297e05feab76f1ef8295c83996b70de2ea09fa1/validation/coupling/state_reference.py#L427) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1/lean/checks/regulated_availability.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1/lean/PROGRESS.md#regulated-state-response)

[Tested engine e297e05feab7](https://github.com/Eidosoma/Cells/commit/e297e05feab76f1ef8295c83996b70de2ea09fa1) · [Evidence checkpoint 6a8bb7ede08a](https://github.com/Eidosoma/Cells/commit/6a8bb7ede08abd6c9e60343371ce9a76f38e04a1)

## Biological evidence

**Open.** Absolute SK2 open probability at fixed free calcium and its relaxation time after calcium addition or removal.

**Unit** open probability

### hirschberg1998_sk2@1

Recombinant rat SK2 in excised Xenopus oocyte patches at nominal −80 mV. The four dose measurements came from one patch, and the jump kinetics from separate macropatches. Figure 1B gives four single-channel steady doses. Figure 13A and its accompanying text give measured rapid calcium-jump kinetics. [Hirschberg et al. (1998), Figs. 1B and 13A](https://doi.org/10.1085/jgp.111.4.565)

- **Evidence role** held out from fitting
- **Fit** Open probability at 0.6, 0.8 and 5 µM calcium, Mean washout time after 9.5 µM calcium
- **Evaluation** Open probability at 1 µM calcium, Mean rise time after the jump to 9.5 µM calcium
- **Excluded** Simulated current traces in Figure 13B
- **Observed** 0.526 open probability
- **Predicted** 0.566 open probability

Reading precision is about ±0.01 in absolute open probability. Shifting the three fitted points by that amount gave 0.543–0.589 at 1 µM and 9.76–11.34 ms for the rise across eight corner fits. The 5 µM solution shifted voltage by about 11 mV. Six jumps across two patches gave washout 57.3 ± 11.1 ms and rise 4.1 ± 0.6 ms (mean ± SD).

The held-out dose is from the same single-channel patch as the fitted doses. With its plateau and the independent macropatch washout mean, the one-state model predicts a 10.63 ms rise against 4.1 ± 0.6 ms measured. This tests whether one set of rates transfers between patches. [Dataset manifest](../checks/data/hirschberg1998_sk2.json) · [Comparison verdict](../PROGRESS.md#regulated-state-response)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
