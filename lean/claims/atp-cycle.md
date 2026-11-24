<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Free energy sets ATP-driven transport direction and stall

With positive forward rate J⁺, an enabled cycle has net rate J⁺(1 − exp(ΔG/RT)). It runs forward for negative ΔG, reverses for positive ΔG and stalls at zero. A disabled cycle has zero rate. Instantaneous heat is nonnegative in every case. For n protons per ATP, the stall voltage is (RT/F) ln(a_P/a_N) + ΔG_fuel/(nF). At fixed fuel, temperature and coupling, changing the pH gradient shifts stall by exactly the change in the proton equilibrium voltage. Neutral cargo flux is independent of voltage at fixed activities and forward rate.

## Assumptions

- One tightly coupled mode hydrolyses one ATP on side N and moves n cargo units from N to P. Cargo valence is +1 for free protons and zero for the neutral role. Voltage is V_N − V_P.
- Activities and absolute temperature are positive. In an enabled population, capacity, availability and the saturation factor are positive. Lean represents their product by its finite logarithm and uses real arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Transport.ATPCycle.flux_disabled](../CellsProofs/Transport/ATPCycle.lean#L21)
- [CellsProofs.Transport.ATPCycle.flux_eq_mass_action](../CellsProofs/Transport/ATPCycle.lean#L23)
- [CellsProofs.Transport.ATPCycle.forward_iff](../CellsProofs/Transport/ATPCycle.lean#L31)
- [CellsProofs.Transport.ATPCycle.reverse_iff](../CellsProofs/Transport/ATPCycle.lean#L34)
- [CellsProofs.Transport.ATPCycle.stall_iff](../CellsProofs/Transport/ATPCycle.lean#L37)
- [CellsProofs.Transport.ATPCycle.heat_nonneg](../CellsProofs/Transport/ATPCycle.lean#L42)
- [CellsProofs.Transport.ATPCycle.proton_stall_iff](../CellsProofs/Transport/ATPCycle.lean#L59)
- [CellsProofs.Transport.ATPCycle.proton_stall_shift](../CellsProofs/Transport/ATPCycle.lean#L71)
- [CellsProofs.Transport.ATPCycle.neutral_voltage_independent](../CellsProofs/Transport/ATPCycle.lean#L64)

Direct proof subject `cells.proton_atp_mass_action_positive@1`, `cells.atp_driven_transporter_mass_action_positive@1`

## Numerical comparison

**Checked.** Across 92 compiled tissue states, 72 ran forward, 16 reversed and four were within the stall tolerance. Cycle flux agreed with frozen references to 7.50 × 10⁻¹⁶ fmol/s and heat was nonnegative in all cases. Offsetting the voltage by ±10 mV about proton stall reversed the rate. The same voltage perturbations preserved all three flowing neutral controls. Eight capacity and availability controls gave exactly zero flux, heat and work. For the eight yeast assay conditions, the registered proton law also bracketed 32 stall voltages. At fixed fuel the pH-induced shift was −112.40 mV for every supported coupling.

**Engine** `resolved_pump_tissue@3`, `proton_atp_mass_action_positive@1`, `atp_driven_transporter_mass_action_positive@1`

[Proton stoichiometry and saturation](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/laws/pumps/proton_pump.py#L223) · [Neutral cargo stoichiometry and saturation](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/laws/pumps/atp_transporter.py#L135) · [Free energy and availability](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/kinds/transporter.py#L1404) · [Signed rate](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/laws/cycles/forms.py#L893) · [Cycle heat and work](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/kinds/transporter.py#L1544) · [Independent Decimal rates](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/validation/core_seams/references/cycles.py#L66) · [Frozen inputs](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/validation/core_seams/references/reference_inputs.json) · [Frozen reference values](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/validation/core_seams/references/designs/core_seams_reference_values.json) · [Host comparison and tolerances](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/tests/unit/test_cycle_kind_references.py#L296) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/5f39e089a5f84fa4c2414d72536de844d0bd2503/lean/checks/atp_cycle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/5f39e089a5f84fa4c2414d72536de844d0bd2503/lean/PROGRESS.md#19-november-2026--atp-driven-transport)

[Tested engine a6f4c7d9b8e8](https://github.com/Eidosoma/Cells/commit/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3) · [Evidence checkpoint 5f39e089a5f8](https://github.com/Eidosoma/Cells/commit/5f39e089a5f84fa4c2414d72536de844d0bd2503)

**Engine** `resolved_pump_tissue@3`, `cells.proton_atp_mass_action_positive@1`

[Free energy for pumping at fixed coupling](https://github.com/Eidosoma/Cells/blob/6318b7d4f8d33251760834b6079aa27d88a81831/src/cells/laws/pumps/proton_pump.py#L73) · [Signed proton pump flux](https://github.com/Eidosoma/Cells/blob/6318b7d4f8d33251760834b6079aa27d88a81831/src/cells/laws/pumps/proton_pump.py#L91) · [Stoichiometry and fuel in the tissue population](https://github.com/Eidosoma/Cells/blob/6318b7d4f8d33251760834b6079aa27d88a81831/src/cells/laws/pumps/proton_pump.py#L223) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/78acb6bccc69cabbd8639a22975d87b5eabb42a2/lean/checks/atp_cycle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/78acb6bccc69cabbd8639a22975d87b5eabb42a2/lean/PROGRESS.md#biological-model-review)

[Tested engine 6318b7d4f8d3](https://github.com/Eidosoma/Cells/commit/6318b7d4f8d33251760834b6079aa27d88a81831) · [Evidence checkpoint 78acb6bccc69](https://github.com/Eidosoma/Cells/commit/78acb6bccc69cabbd8639a22975d87b5eabb42a2)

**Engine** `resolved_pump_tissue@3`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_constant_field_leak@1`, `cells.inward_rectifier_linear_driving_force@1`, `cells.kir2p1_mh2@1`, `cells.rapid_binding@1`

[Tight-coupled proton pump](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/pumps/proton_pump.py#L91) · [Proton flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/transport/proton_leak.py#L31) · [Kir slope conductance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Two binding forms](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/reactions/rapid_binding.py#L340) · [Tissue channel current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/electrochemistry.py#L10) · [Preparation records](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_preparation_controls.json) · [Kir slopes and controls](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_replay_measurements.json) · [Fixed-drive Kir evaluation](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_law_replays.py) · [Native proton roots](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_membrane_physiology.py) · [Tissue clamp specimen](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/clamped_channel_current.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_preparation_controls.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/PROGRESS.md#preparation-evidence-review)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 01edbd968e18](https://github.com/Eidosoma/Cells/commit/01edbd968e182f91c0bd281fe776f5609a78e645)

## Biological evidence

**Open.** Reversal voltage of ATP-dependent proton transport at known fuel and proton activities, and neutral-cargo flux at fixed activities under varied voltage.

- [The yeast vacuolar pump reversal exceeds +40 mV at cytosolic pH 7.5 and lumen pH 3.1.](../WET_LAB_EVIDENCE.md#pair-vacuolar-pump-low-ph) · Independent replication unconfirmed
- [At fixed nominal cytosolic pH 7.5, acidifying the lumen shifts the ATP-dependent vacuolar current reversal toward positive voltages.](../WET_LAB_EVIDENCE.md#pair-vacuolar-pump-lumen-gradient) · Supported by both studies

Vesicles showed ATP-dependent riboflavin uptake. Neutral-cargo reversal and voltage independence remain open. [Van Herwaarden et al., Fig. 3E](https://pmc.ncbi.nlm.nih.gov/articles/PMC1800714/) Two red-cell ghost studies observed ouabain-sensitive phosphate incorporation into ATP. Exchange can contribute at zero net ATP production. [Garrahan and Glynn](https://doi.org/10.1113/jphysiol.1967.sp008298) · [Lant and Whittam](https://doi.org/10.1113/jphysiol.1968.sp008663) Davies measured reversal in red-beet vacuoles at the same pH difference with different absolute pH values. Kettner Fig. 4 replots those beet data. Independent replication of the yeast lumen-pH-3.1 bound remains open. [Davies et al., Table 1](https://doi.org/10.1073/pnas.91.18.8547)

**Unit** mV for reversal, fmol/s for signed cargo flux

### kettner2003_vacuolar_pump@1

Voltage-clamped yeast vacuoles with ATP, ADP and phosphate supplied to the cytosolic side. ATP-dependent difference currents in Fig. 3 and five resolved reversals plus three bounds in Table 2. [Kettner et al. (2003), Fig. 3 and Table 2](https://doi.org/10.1016/S0006-3495(03)74789-4)

- **Evidence role** descriptive

At cytosolic pH 7.5, the two measured reversal voltages were −25.6 ± 1 and −38.6 ± 9 mV (SE, four and three trials). The proton equilibrium and hydrolysis voltages are calculated quantities.

Changing vacuolar pH from 4.1 to 6.0 shifted the ATP-dependent current reversal by −13.0 mV. Any fixed tightly coupled pump at the same fuel drive predicts the full proton-equilibrium shift, −112.5 mV using the paper's values. At pH 8.5/5.0 the two-proton prediction was −86.5 mV versus −17.5 ± 5 mV measured. The suggested pump-associated proton shunt remains one candidate mechanism. [Dataset manifest](../checks/data/kettner2003_vacuole.json) · [Comparison verdict](../PROGRESS.md#biological-model-review)

### kettner_workshop_low_ph

The same research group reported the journal reversal bound above +40 mV. Workshop voltage ramps lasted 2.5 s and journal ramps lasted 5 s. Table 1 at cytosolic pH 7.5 and lumen pH 3.1. Figure 7B shows a low-pH trace at 0 mV. [Kettner, 2002 workshop proceedings (2003), Fig. 7B and Table 1](https://www.beilstein-institut.de/download/736/kettner_1.pdf#page=14)

- **Evidence role** descriptive

The table gives +50 ± 8 mV (SE) without a replicate count or a matched low-pH sweep resolving the crossing. Independence from the journal recordings is unknown.

The earlier estimate is compatible with the journal’s lower bound. The low-pH measurement required to reopen FR-29 remains outstanding. [Dataset manifest](../checks/data/kettner_low_ph_reversal.json) · [Comparison verdict](../PROGRESS.md#fr29-low-ph-current)

### rienmuller2012_vacuole

Arabidopsis mesophyll vacuoles, cytosolic pH 7.5 during the lumen titration. Fig. 2, ATP-dependent current. [Rienmüller et al. (2012)](https://doi.org/10.1074/jbc.M111.310367)

- **Evidence role** descriptive

Reported errors and sample counts are retained per voltage. A cytosolic ATP/ADP/Pi activity quotient during each ramp was unavailable.

Acidifying the lumen by two pH units shifted the mean reversal by +44.9 mV. A constant fuel driving force and tight coupling give a larger shift at every tested stoichiometry. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
