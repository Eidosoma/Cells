<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Free energy sets ATP-driven transport direction and stall

With positive forward rate J⁺, an enabled cycle has net rate J⁺(1 − exp(ΔG/RT)). It runs forward for negative ΔG, reverses for positive ΔG and stalls at zero. A disabled cycle has zero rate. Instantaneous heat is nonnegative in every case. For n protons per ATP, the stall voltage is (RT/F) ln(a_P/a_N) + ΔG_fuel/(nF). Neutral cargo flux is independent of voltage at fixed activities and forward rate.

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
- [CellsProofs.Transport.ATPCycle.neutral_voltage_independent](../CellsProofs/Transport/ATPCycle.lean#L64)

Direct proof subject `cells.proton_atp_mass_action_positive@1`, `cells.atp_driven_transporter_mass_action_positive@1`

## Numerical comparison

**Checked.** Across 92 compiled tissue states, 72 ran forward, 16 reversed and four were within the stall tolerance. Cycle flux agreed with frozen references to 7.50 × 10⁻¹⁶ fmol/s and heat was nonnegative in all cases. Offsetting the voltage by ±10 mV about proton stall reversed the rate. The same voltage perturbations preserved all three flowing neutral controls. Eight capacity and availability controls gave exactly zero flux, heat and work.

**Engine** `resolved_pump_tissue@3`, `proton_atp_mass_action_positive@1`, `atp_driven_transporter_mass_action_positive@1`

[Proton stoichiometry and saturation](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/laws/pumps/proton_pump.py#L223) · [Neutral cargo stoichiometry and saturation](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/laws/pumps/atp_transporter.py#L135) · [Free energy and availability](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/kinds/transporter.py#L1404) · [Signed rate](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/laws/cycles/forms.py#L893) · [Cycle heat and work](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/src/cells/kinds/transporter.py#L1544) · [Independent Decimal rates](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/validation/core_seams/references/cycles.py#L66) · [Frozen inputs](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/validation/core_seams/references/reference_inputs.json) · [Frozen reference values](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/validation/core_seams/references/designs/core_seams_reference_values.json) · [Host comparison and tolerances](https://github.com/Eidosoma/Cells/blob/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3/tests/unit/test_cycle_kind_references.py#L296) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/5f39e089a5f84fa4c2414d72536de844d0bd2503/lean/checks/atp_cycle.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/5f39e089a5f84fa4c2414d72536de844d0bd2503/lean/PROGRESS.md#19-november-2026--atp-driven-transport)

[Tested engine a6f4c7d9b8e8](https://github.com/Eidosoma/Cells/commit/a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3) · [Evidence checkpoint 5f39e089a5f8](https://github.com/Eidosoma/Cells/commit/5f39e089a5f84fa4c2414d72536de844d0bd2503)

## Biological evidence

**Open.** Reversal voltage of ATP-dependent proton transport at known fuel and proton activities, and neutral-cargo flux at fixed activities under varied voltage.

In yeast vacuoles at cytosolic pH 8.5 and vacuolar pH 5.0, measured reversal was −17.5 ± 5 mV (SE, six trials). The tightly coupled two-proton prediction was −86.5 mV. The authors proposed a proton shunt. Vesicles showed ATP-dependent riboflavin uptake. Neutral-cargo reversal and voltage independence remain open. [Kettner et al., Table 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC1303676/) · [Van Herwaarden et al., Fig. 3E](https://pmc.ncbi.nlm.nih.gov/articles/PMC1800714/)

**Unit** mV for reversal, fmol/s for signed cargo flux

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
