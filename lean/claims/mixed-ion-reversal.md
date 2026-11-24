<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Three passive ions set one zero-current membrane voltage

For monovalent Na⁺, K⁺ and Cl⁻ the analytic sum of the outward constant-field currents vanishes exactly at the Goldman–Hodgkin–Katz voltage. The chloride concentrations enter in the opposite order to sodium and potassium.

## Assumptions

- The concentrations, effective permeabilities and temperature are fixed during the voltage comparison, the thermal voltage RT/F is positive and both permeability-weighted concentration sums are positive.
- The membrane carries only these three passive ions. The analytic identity agrees with the engine’s real-arithmetic evaluator at zero and outside its near-zero series interval. We also compare float64 at one nonzero reversal inside that interval.

## Lean proof

**Proved**

- [CellsProofs.Transport.MixedMembrane.current_factorization](../CellsProofs/Transport/MixedMembrane.lean#L33)
- [CellsProofs.Transport.MixedMembrane.reversal_iff](../CellsProofs/Transport/MixedMembrane.lean#L42)
- [CellsProofs.Transport.MixedMembrane.engine_current_eq](../CellsProofs/Transport/MixedMembrane.lean#L58)

Direct proof subject `cells.passive_constant_field_permeation@1`

Uses [Ion charge sets permeation reversal and bounds the current–voltage slope](charged-permeation.md)

## Numerical comparison

**Checked.** Four roots of the Cells membrane current matched the analytic voltage within 2 × 10⁻¹⁵ V. At −47.168248 mV, outward Na, K and Cl currents were −0.557437, +0.491856 and +0.065581 pA. All three also matched on both sides of reversal and in a two-step run. Seven native roots with the 1949 permeability ratios reproduced the analytical changes to within 10⁻¹⁰ mV. Transferring that ratio to the 1979 perfusate gave +12.63 mV for 10→30 mM external K against +2.0 mV measured.

**Engine** `resolved_pump_tissue@3`, `cells.passive_constant_field_permeation@1`

[Signed ion flux](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/laws/routes/constant_field_permeation.py#L56) · [Area, opening and orientation of each passive route](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/kinds/passive_routes.py#L550) · [Sum of the outward membrane currents](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/models/surface_pump_v3.py#L874) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/mixed_membrane.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#mixed-membrane-reversal)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `cells.passive_constant_field_permeation@1`, `cells.proton_constant_field_leak@1`

[Three-ion constant-field flux](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/routes/constant_field_permeation.py#L59) · [Open-route proton flux](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/transport/proton_leak.py#L31) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/electrochemistry.py#L10) · [Flux evaluation](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/electrochemistry.py#L32) · [1949 squid permeability ratios](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/checks/data/hodgkin_katz1949_rest.json) · [1979 substitutions and measured proton reversals](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/checks/data/membrane_physiology_pairs.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/checks/paired_membrane_physiology.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/PROGRESS.md#paired-membrane-physiology)

[Tested engine 0455ce787fd8](https://github.com/Eidosoma/Cells/commit/0455ce787fd8c36ec2eb51389e4f5a5a5012f253) · [Evidence checkpoint 34e1f9dfc162](https://github.com/Eidosoma/Cells/commit/34e1f9dfc1628af1f81e66cf8166d5c6f4207407)

## Biological evidence

**Open.** Resting voltage shifts under known ion substitutions and separate currents for each ion at the same reversal.

- [Replacing external sodium with potassium at fixed total external monovalent cation concentration depolarizes the resting squid axon.](../WET_LAB_EVIDENCE.md#pair-squid-potassium-substitution) · Supported by both studies

Independent squid recordings agree on depolarization when external K replaces Na. The same fitted 1949 permeability ratio overpredicts the voltage changes in the 1979 perfused preparation.

**Unit** mV

### hodgkin_katz1949_rest@1

Resting squid giant axon in two potassium-enriched artificial seawater solutions and one diluted seawater solution. Shifts use inside-minus-outside voltage. Resting rows B, C and E in the original printed table. [Hodgkin and Katz (1949), Table 7](https://doi.org/10.1113/jphysiol.1949.sp004310)

- **Evidence role** descriptive
- **Fit** Published resting permeability ratios chosen using the experimental series
- **Evaluation** Three resting shifts against the appropriate baseline bath
- **Excluded** Action potential, afterpotential and individual ionic currents
- **Observed** 4 mV
- **Predicted** 4.03 mV

Table 7 gives means rounded to mV without row-specific uncertainties. The calculation adopts 21 °C from Table 3.

For B, C and E, observed shifts were +2, +4 and −2 mV. The reconstructed Cells shifts were +2.10, +4.03 and −1.58 mV. The displayed pair is solution C. The three ionic currents were unmeasured. [Dataset manifest](../checks/data/hodgkin_katz1949_rest.json) · [Comparison verdict](../PROGRESS.md#mixed-membrane-reversal)

### ohki1979_squid_perfusion@1

Six Loligo pealii giant axons. Electrodes measured steady resting voltage during successive K-for-Na substitutions in a perfused axon at about 20 °C. The authors checked that the voltage returned near its initial level. Table 1a, p. 378, internal solution Id-1, seven artificial external solutions [Ohki and Aono (1979), Table 1a](https://doi.org/10.2170/jjphysiol.29.373)

- **Evidence role** descriptive

Reported ± for the six successful axons. Table 1 gives no definition of these errors or covariance between solution means. Electrode-tip corrections were applied, up to about 3 mV.

Raising external K from 10 to 30 mM gave +2.0 mV. With the 1949 ratios and the nominal chloride-free internal solution, the native three-ion flux projection gives +12.63 mV. At 100 mM the measured change was +19.8 mV against +34.50 mV. A separate interpolation anchored within the perfused preparation is recorded with the comparison. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
