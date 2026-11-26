<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Ion charge sets permeation reversal and bounds the current–voltage slope

For a passive ion of either sign, the analytic flux reverses at its Nernst voltage and dissipates nonnegative heat. At fixed concentrations the electrical slope conductance stays between the lower and higher concentrations multiplied by the same positive factor. Equal concentrations give a linear current–voltage relation.

## Assumptions

- Temperature, concentrations and compartment volumes are positive. The reversal requires nonzero ion charge and positive permeability, area and opening. The conductance bound also includes a closed route.
- Conductance holds at fixed concentrations, permeability and opening. In the engine’s real-arithmetic evaluator the slope bounds exclude the two switches at |zFV/(RT)| = 0.0001. The secant bound assumes the whole voltage interval stays within one branch. The material response holds at fixed volumes and voltage.
- The biological current predictions assume the same effective permeability at both voltages within each preparation. A red-cell current is inferred from net solute transfer, and a planar-bilayer current is measured under voltage clamp.

## Lean proof

**Proved**

- [CellsProofs.Transport.ChargedPermeation.reversal_iff](../CellsProofs/Transport/ChargedPermeation.lean#L20)
- [CellsProofs.Transport.ChargedPermeation.heat_nonneg](../CellsProofs/Transport/ChargedPermeation.lean#L30)
- [CellsProofs.Transport.ChargedPermeation.bernoulli_reflection](../CellsProofs/Transport/ChargedPermeation.lean#L41)
- [CellsProofs.Transport.ChargedPermeation.material_response](../CellsProofs/Transport/ChargedPermeation.lean#L57)
- [CellsProofs.Transport.ChargedPermeation.current_formula](../CellsProofs/Transport/ChargedPermeation.lean#L69)
- [CellsProofs.Transport.ChargedPermeation.symmetric_current](../CellsProofs/Transport/ChargedPermeation.lean#L76)
- [CellsProofs.Transport.ChargedPermeation.bernoulli_slope](../CellsProofs/Transport/ChargedPermeation.lean#L93)
- [CellsProofs.Transport.ChargedPermeation.conductance_bounds](../CellsProofs/Transport/ChargedPermeation.lean#L127)
- [CellsProofs.Transport.ChargedPermeation.chord_bounds](../CellsProofs/Transport/ChargedPermeation.lean#L150)

Direct proof subject `cells.route.passive_constant_field_permeation@1`

Uses [Voltage and free proton concentrations set the leak reversal](proton-leak.md)

## Numerical comparison

**Checked.** 360 CPU float64 component cases matched high-precision flux, heat and slope references. In two finite tissue pairs, halving the step from 64 to 128 steps reduced errors in signed transfer, heat and final voltage by factors of 4.03–4.05. Both amount ledgers matched the transferred material.

**Engine** `resolved_pump_tissue@3`, `passive_constant_field_permeation@1`

[Charged inward flux](https://github.com/Eidosoma/Cells/blob/239ab8cd23ecd41048fb89404bd5ba17e89c35c4/src/cells/laws/routes/constant_field_permeation.py#L56) · [Heat and conductance](https://github.com/Eidosoma/Cells/blob/239ab8cd23ecd41048fb89404bd5ba17e89c35c4/src/cells/laws/routes/constant_field_permeation.py#L83) · [Material slopes](https://github.com/Eidosoma/Cells/blob/239ab8cd23ecd41048fb89404bd5ba17e89c35c4/src/cells/laws/routes/constant_field_permeation.py#L116) · [Integration with the passive route](https://github.com/Eidosoma/Cells/blob/239ab8cd23ecd41048fb89404bd5ba17e89c35c4/src/cells/kinds/passive_routes.py#L566) · [Host charge and material bounds](https://github.com/Eidosoma/Cells/blob/239ab8cd23ecd41048fb89404bd5ba17e89c35c4/src/cells/kinds/passive_routes.py#L780) · [Finite-pair fixture](https://github.com/Eidosoma/Cells/blob/239ab8cd23ecd41048fb89404bd5ba17e89c35c4/tests/unit/test_passive_routes_kind.py#L294) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/5f6437c5fead7445109dcd24aaf3b0d458d379d6/lean/checks/charged_permeation.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/5f6437c5fead7445109dcd24aaf3b0d458d379d6/lean/PROGRESS.md#20-november-2026--charged-constant-field-permeation)

[Tested engine 239ab8cd23ec](https://github.com/Eidosoma/Cells/commit/239ab8cd23ecd41048fb89404bd5ba17e89c35c4) · [Evidence checkpoint 5f6437c5fead](https://github.com/Eidosoma/Cells/commit/5f6437c5fead7445109dcd24aaf3b0d458d379d6)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `clleak_always_open@1`, `passive_constant_field_permeation@1`

**Operators** `cells.species_regulated_availability@1`, `cells.species_regulated_availability@2`

[Held-input state update](https://github.com/Eidosoma/Cells/blob/afc28d1d200d3f926c831e6216eee8209a763f38/src/cells/operators/species_regulated_availability.py#L1363) · [Chloride-selective flux kernel](https://github.com/Eidosoma/Cells/blob/afc28d1d200d3f926c831e6216eee8209a763f38/src/cells/laws/junctions/selective.py#L19) · [Charged route flux kernel](https://github.com/Eidosoma/Cells/blob/afc28d1d200d3f926c831e6216eee8209a763f38/src/cells/laws/routes/constant_field_permeation.py#L59) · [Composite world fixture](https://github.com/Eidosoma/Cells/blob/afc28d1d200d3f926c831e6216eee8209a763f38/validation/tissue/secreted_species_fixtures.py#L92) · [Regulatory state fixture](https://github.com/Eidosoma/Cells/blob/afc28d1d200d3f926c831e6216eee8209a763f38/validation/tissue/regulated_availability_fixtures.py#L130) · [Independent chloride and SK2 measurements](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/data/paired_transport_responses.json) · [SK2 calibration measurements](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/data/hirschberg1998_sk2.json) · [Red-cell chloride readings](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/data/freedman1997_chloride.json) · [Bilayer potassium readings](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/data/pfeffermann2026_potassium.json) · [SK2 calcium clamp](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/regulated_availability.py#L337) · [Original chloride protocol](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/chloride_channel.py#L23) · [One-voltage calibrations](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/charged_permeation.py#L152) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/checks/paired_transport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9/lean/PROGRESS.md#paired-transport-and-membrane-measurements)

[Tested engine afc28d1d200d](https://github.com/Eidosoma/Cells/commit/afc28d1d200d3f926c831e6216eee8209a763f38) · [Evidence checkpoint bb2a42672ba8](https://github.com/Eidosoma/Cells/commit/bb2a42672ba8e3acd6fdb7055e68b4c3f5c5b8d9)

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `cells.kv1p5_mh@1`, `cells.passive_constant_field_permeation@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.population_unit_turnover@1`, `cells.membrane_entity_state@1`

[Kv1.5 activation and inactivation](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/channels/kv1p5_mh.py#L25) · [Clamped population current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Gate advance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/numerics/exponential_gates.py#L44) · [Constant-field ion flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/constant_field_permeation.py#L59) · [Inward rectifier slope](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Native cohort removal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/population_unit_turnover.py#L958) · [Surface population counts](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/membrane_state.py#L152) · [Two-population fixture](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/validation/fr7/unit_turnover_fixtures.py#L68) · [Paired measurements and protocols](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_replay_measurements.json) · [Kv1.5 dose and rectifier data](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Activation curve and step current](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/trapani2003_kv15_ph.json) · [Published receptor component fits](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/membrane_physiology_pairs.json) · [Red-cell chloride measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/freedman1997_chloride.json) · [Planar-bilayer potassium currents](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pfeffermann2026_potassium.json) · [Prepared clamp and pH rows](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/kv15_ph.py) · [Permeability calibration](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/charged_permeation.py) · [Population declaration and binding](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/population_units.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_law_replays.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

**Engine** `resolved_pump_tissue@3`, `cells.passive_constant_field_permeation@1`

[Constant-field material flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/constant_field_permeation.py#L59) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/electrochemistry.py#L10) · [Red-cell concentrations and voltages](https://github.com/Eidosoma/Cells/blob/369431f74ae5108c8be47f3a0afc80623de7f028/lean/checks/data/freedman1997_chloride.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/369431f74ae5108c8be47f3a0afc80623de7f028/lean/checks/red_cell_chloride_ratio.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/369431f74ae5108c8be47f3a0afc80623de7f028/lean/PROGRESS.md#red-cell-chloride-ratio)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 369431f74ae5](https://github.com/Eidosoma/Cells/commit/369431f74ae5108c8be47f3a0afc80623de7f028)

## Biological evidence

**Mixed.** Electrical current at a second voltage and reversal at a known ion gradient. These experiments leave microscopic route heat unmeasured.

- [At fixed concentrations in each preparation, one permeability fitted at one voltage suffices to predict current at a second voltage.](../WET_LAB_EVIDENCE.md#pair-single-permeability-current-voltage) · Challenged by both studies
- [One constant permeability reproduces the wide-voltage I–V shape of valinomycin-mediated potassium transport in two independent planar bilayers.](../WET_LAB_EVIDENCE.md#pair-valinomycin-wide-voltage-shape) · Comparison unresolved

**Unit** mA per g Hb (red cells), nA (bilayer) and mV (reversal)

### freedman1997_chloride@1

DIDS-treated human red cells, five donor series at 23 °C and pH 7.5. Optical shrinkage estimates net chloride transfer. A parallel pH assay estimates membrane voltage. The lower Fig. 6A points give chloride currents. Fig. 6C gives measured voltages at the two external potassium concentrations. Fig. 5 gives conductances. [Freedman and Novak, Figs. 5–6 and Table I](https://doi.org/10.1085/jgp.109.2.201)

- **Evidence role** held out from fitting
- **Fit** 1 mM external potassium, −103 mV
- **Evaluation** 10 mM external potassium, −59 mV

Means and SD were digitized. Estimated figure-reading precision is ±1.5 mV and ±0.05 mA/g Hb. The within-donor covariance is unavailable.

At −59 mV, the one-voltage fit predicted −1.97 mA/g Hb against −1.17 ± 0.13 measured. The ratio of reported mean slope conductances was 3.67. At the inferred fixed chloride concentrations the model permits a local slope ratio up to 1.49. Inverting both Fig. 6 means requires a shared intracellular/extracellular chloride ratio of 0.187 against an initial 0.67 ± 0.02. Fig. 5A/C and Fig. 6 reuse the same five series. [Dataset manifest](../checks/data/freedman1997_chloride.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--charged-constant-field-permeation)

### pfeffermann2026_potassium@1

Planar bilayer under voltage clamp with a 150/15 mM potassium gradient and valinomycin. The comparison assumes 25 °C. Open magenta squares for asymmetric KCl at matched light state. The text reports the interpolated reversal. [Pfeffermann et al., Fig. 2c](https://doi.org/10.1039/D5NR04234H)

- **Evidence role** held out from fitting
- **Fit** +110 mV potassium current
- **Evaluation** −110 mV potassium current, cis-state reversal

The plotted currents are readable to about ±1 nA. The panel gives no pointwise uncertainties or measurement temperature. The reversal is interpolated from the same curve.

The predicted reversal was −59.16 mV against −59.8 mV measured. At −110 mV the same fitted permeability gave −3.84 nA against approximately −13.5 nA measured. [Dataset manifest](../checks/data/pfeffermann2026_potassium.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--charged-constant-field-permeation)

### piasta2011_valinomycin_local@1

Valinomycin added to a single-channel planar bilayer in a 200/10 mM K gradient. Appendix B, Fig. B1, diamond markers after valinomycin addition. Example bilayer and blocked-channel baseline. [Piasta et al. (2011), Appendix B, Fig. B1](https://doi.org/10.1085/jgp.201110684)

- **Evidence role** descriptive

The ±1.3 mV belongs to the channel-minus-carrier reversal difference over four comparisons. Pointwise current uncertainty and ion activities for the plotted curve are unavailable. Use only the narrow window actually covered by the carrier points.

Carrier points straddle the blocked-channel baseline around −71 mV. The paired channel-minus-carrier reversal difference is −0.8 ± 1.3 mV. These data constrain the local crossing. [Dataset manifest](../checks/data/paired_replay_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-law-replays)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
