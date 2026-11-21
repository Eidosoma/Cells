<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Stall voltages and net charge of the sodium–potassium and calcium pumps

The Na⁺/K⁺ pump stalls at ψ = g_NaK − 3r_Na + 2r_K and the calcium pump at ψ = (g_Ca − r_Ca)/2. An enabled pump runs forward above its own stall voltage. Their outward charge flux in elementary-charge equivalents is J_NaK + 2J_Ca. The same sum determines their voltage-dependent free-energy change. The two currents cancel exactly when J_NaK = −2J_Ca.

## Assumptions

- For each ion, r is ln(inside activity / outside activity), ψ = F(V_inside − V_outside)/(RT), and each g is its pump’s ATP hydrolysis free energy divided by RT. Temperature and all activities are positive. The direction and stall results assume positive capacity, availability and saturation.
- J denotes signed cycles per unit time. Each forward cycle consumes one ATP. The Na⁺/K⁺ pump exports three Na⁺ and imports two K⁺. The Cells calcium pump transports one Ca²⁺ outward and counts only that ion. The formula sums the currents of these two pumps.

## Lean proof

**Proved**

- [CellsProofs.Transport.ElectrogenicPumps.nak_stall_iff](../CellsProofs/Transport/ElectrogenicPumps.lean#L23)
- [CellsProofs.Transport.ElectrogenicPumps.calcium_stall_iff](../CellsProofs/Transport/ElectrogenicPumps.lean#L29)
- [CellsProofs.Transport.ElectrogenicPumps.nak_forward_iff](../CellsProofs/Transport/ElectrogenicPumps.lean#L35)
- [CellsProofs.Transport.ElectrogenicPumps.calcium_forward_iff](../CellsProofs/Transport/ElectrogenicPumps.lean#L41)
- [CellsProofs.Transport.ElectrogenicPumps.charge_per_cycle](../CellsProofs/Transport/ElectrogenicPumps.lean#L51)
- [CellsProofs.Transport.ElectrogenicPumps.voltage_work](../CellsProofs/Transport/ElectrogenicPumps.lean#L54)
- [CellsProofs.Transport.ElectrogenicPumps.zero_current_iff](../CellsProofs/Transport/ElectrogenicPumps.lean#L61)

Direct proof subject `cells.nak_atp_mass_action_positive@1`, `cells.ca_atp_mass_action_positive@1`

Uses [Free energy sets ATP-driven transport direction and stall](atp-cycle.md)

## Numerical comparison

**Checked.** The compiled tissue matched two 80-digit references at five initial voltages, including both stalls (−99.365 and −104.104 mV). The largest cycle-rate error was 3.50 × 10⁻¹⁶ fmol/s. At the midpoint the pumps ran in opposite directions, each contributing 0.349 pA in magnitude. The net electrode current was 2.04 × 10⁻²⁶ A. The 1 ms trajectory accounted for all three ions and both midpoint pumps dissipated energy.

**Engine** `resolved_pump_tissue@3`, `nak_atp_mass_action_positive@1`, `ca_atp_mass_action_positive@1`

[Na⁺/K⁺ drive and rate](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/pumps/nak_atp_mass_action_positive.py#L55) · [Calcium standard state and rate](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/pumps/ca_atp_mass_action_positive.py#L66) · [Plasma-membrane voltage convention](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/reactions/plasma_calcium.py#L29) · [Calcium rate formula](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/laws/reactions/er_calcium.py#L36) · [Tissue pump dispatch](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L451) · [Outward ion transfers](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L898) · [Charge and electrode current](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/src/cells/models/surface_pump_v3.py#L938) · [Na⁺/K⁺ scalar reference](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/betse/pump_contact/pump_reference.py#L83) · [Calcium scalar reference](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/validation/chemistry/finite_calcium_pump_reference.py#L19) · [Na⁺/K⁺ rate tests](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_kinetic_pump.py#L46) · [Calcium standard-state and stall tests](https://github.com/Eidosoma/Cells/blob/d0104950c40b92860a211c9e2555709d0fd61aed/tests/unit/test_surface_pump_v2.py#L86) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/checks/electrogenic_pumps.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c1e2b733bc4c54a4fd005b9dedb4697d801855d1/lean/PROGRESS.md#channel-source-replays-nov21)

[Tested engine d0104950c40b](https://github.com/Eidosoma/Cells/commit/d0104950c40b92860a211c9e2555709d0fd61aed) · [Evidence checkpoint c1e2b733bc4c](https://github.com/Eidosoma/Cells/commit/c1e2b733bc4c54a4fd005b9dedb4697d801855d1)

## Biological evidence

**Open.** Ion transfer per ATP, paired ion flux and outward current, and stall voltage under known fuel and ion activities.

Squid axons gave 3.05 ± 0.13 Na⁺ per net charge from −60 to −90 mV in Na-free seawater and 2.72 ± 0.09 at 0 mV with 390 mM external Na⁺ (SEM). Cells predicts 3. Red-cell ghosts lost about 3 Na⁺ per ATP. In pig-brain calcium pumps, separate rate measurements imply 1.02 Ca²⁺ per ATP and about +1.4 net charges per ATP after inward H⁺ is included. Cells counts +2 from Ca²⁺ alone. The simulated stall voltages still lack a matched measurement. [Rakowski et al., Table I](https://doi.org/10.1085/jgp.93.5.903) · [Garrahan and Glynn](https://doi.org/10.1113/jphysiol.1967.sp008297) · [Salvador et al., Table I](https://doi.org/10.1074/jbc.273.29.18230)

**Unit** ions per net elementary charge, ions and net elementary charges per ATP, mV for stall

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
