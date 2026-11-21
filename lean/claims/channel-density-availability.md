<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Independent channel counts determine relative availability from fixed-gate currents

When two populations share their single-channel drive and stored gates, the ratio of their currents per counted surface channel equals the ratio of their availabilities. Their patch areas and channel densities may differ.

## Assumptions

- Compare the same permeant ion, voltage, charge conversion, temperature, concentrations, gate state, permeability and reference channel density. Counting uses all voltage-sensing channels, including channels that are silent.
- Each patch has positive area and density. The reference preparation has positive availability and a nonzero single-channel response. The test uses the same area units for current density and channel density.
- The descriptive density curve fixes the Hill exponent at one and basal fraction at zero. Its maximum and half-saturation come from the two Kv1.5 endpoints. The composite exercises a distinct reporter. D218 excludes using a population’s own density to route its own availability.

## Lean proof

**Proved**

- [CellsProofs.Transport.IonChannels.clamped_current_per_channel](../CellsProofs/Transport/IonChannels.lean#L266)
- [CellsProofs.Transport.IonChannels.relative_availability_from_counts](../CellsProofs/Transport/IonChannels.lean#L279)

Proof sources [Mathlib cancellation of common nonzero factors, used in the standard proof](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/GroupWithZero/Units/Basic.lean#L317-L325) · [grn-lean Hill response at the pinned revision, specialized in the optional check](https://github.com/marpaia/grn-lean/blob/070ba8da6a09bdc4b0550396c61611668768bc0b/GRN/Dynamics/VectorField.lean#L34-L37) · [Cells reciprocal-availability specialization at exponent one](../checks/hill/Response.lean#L60)

Uses [A fixed-gate current curve identifies the product of channel abundance and availability](clamped-channel-current.md) · [A regulated channel approaches its held-dose plateau without overshoot](regulated-state-response.md)

## Numerical comparison

**Checked.** On three Kv1.5 patches of 100, 160 and 240 µm², the count-normalized currents relative to the low-density patch were 1, 1 and 1 at fixed availability. With the measured fractions supplied, they were 1, 0.6765 and 0.5294 at both clamp voltages on NumPy and compiled JAX CPU. The separate reporter returned 0.22215 at 300 channels/µm², matching the reciprocal interpolation.

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `cells.kv1p5_mh@1`, `cells.kleak_always_open@1`

**Operators** `cells.membrane_entity_state@1`, `cells.species_regulated_availability@2`

[Instantaneous current at a declared voltage](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/models/surface_pump_v3.py#L415) · [Channel abundance and schedule in the constant-field flux](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/models/surface_pump_v3.py#L370) · [Kv1.5 gate specification](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/laws/channels/kv1p5_mh.py#L47) · [Reference density and membrane area](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/operators/membrane_state.py#L158) · [Population-density read and inhibition factor](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/operators/species_regulated_availability.py#L1513) · [Own-population refusal (D218)](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/operators/species_regulated_availability.py#L602) · [Log-domain Hill factor](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/laws/reactions/hill_factors.py#L39) · [Composite control view](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/models/pump_composite.py#L1510) · [Distinct source and reporter fixture](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/tests/unit/test_regulated_availability_population.py#L54) · [Membrane units declaration](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/validation/fr7/unit_turnover_fixtures.py#L68) · [Scheduled target availability](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/validation/tissue/regulated_availability_fixtures.py#L164) · [Clamp tissue specimen](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/tests/unit/test_chloride_leak_law.py#L37) · [Channel population parameters](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/validation/tissue/surface_pump_v3_fixtures.py#L61) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/71807e24c375bbc354501e046ea3e61961a4d550/lean/checks/channel_density.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/71807e24c375bbc354501e046ea3e61961a4d550/lean/PROGRESS.md#kv15-channel-density)

[Tested engine 1b8017d13755](https://github.com/Eidosoma/Cells/commit/1b8017d13755bed2ee9be09375c998e364a4ca62) · [Evidence checkpoint 71807e24c375](https://github.com/Eidosoma/Cells/commit/71807e24c375bbc354501e046ea3e61961a4d550)

## Biological evidence

**Not assessable.** Kv1.5 conducting fraction at a middle density excluded from fitting, and whether changes in the channel’s own density cause those changes in availability.

**Unit** conducting fraction

### maverick2022_kv_density

Tagged Kv1.5 in HEK293 cells at room temperature. Conducting-channel estimates use ionic conductance, and voltage-sensing channel counts use calibrated gating charge. The density series compares different cells. Fig. 8C, journal p. 766. The orange triangle nearest 300 channels/µm² is the evaluation point. [Maverick and Tamkun (2022), Fig. 8C](https://doi.org/10.1016/j.bpj.2022.01.021)

- **Evidence role** held out from fitting
- **Fit** Kv1.5 near 115 channels/µm², Kv1.5 near 425 channels/µm²
- **Evaluation** Kv1.5 near 300 channels/µm²
- **Observed** 0.23 conducting fraction
- **Predicted** 0.22215 conducting fraction

Graph readings of three-cell moving averages from one study. There are no pointwise errors. The estimated gating count occurs in the density numerator and the conducting-fraction denominator, so error in that count can induce anticorrelation.

The middle estimate is about 0.23. The two-endpoint inhibition curve gives about 0.22 there and a constant fraction calibrated at the low density gives 0.34. The comparison cannot establish the Kv1.5 silencing mechanism. Nearby Kv1.4 fractions were about 0.64 and 0.73. [Dataset manifest](../checks/data/maverick2022_kv_density.json) · [Comparison verdict](../PROGRESS.md#kv15-channel-density)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
