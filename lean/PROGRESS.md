# Cells proof comparisons

## 19 November 2026 · Chloride leak

The newly registered `clleak_always_open@1` adds a monovalent anion to the channel populations of `resolved_pump_tissue@3`. Lean proves that outward Cl⁻ movement gives negative outward current. For positive permeability, availability and concentrations, the reversal voltage on the regular branch is `(RT/F) × (ln inside − ln outside)`. The identity also holds at zero voltage. The finite near-zero polynomial keeps its own Bernoulli ratio. The proof reuses the existing constant-field reversal theorem with the concentrations exchanged. [Channel and reversal proofs](CellsProofs/Transport/IonChannels.lean) · [Registered chloride declaration](../src/cells/laws/channels/clleak_always_open.py#L20) · [Current in the tissue host](../src/cells/models/surface_pump_v3.py#L872)

Two one-cell runs started at −21.52 mV with 62.56 mM internal Cl⁻. With 147 mM in the held bath, chloride moved into the cell and the initial electrode current was **+0.573 pA**. With 70 mM outside, chloride left the cell and the current was **−5.733 pA**. The independent calculation integrated signed material transfer with a 70-digit constant-field rate and updated the capacitor voltage at each evaluation. The driver checked the cell and reservoir inventories, signed electrode charge, voltage, all other ions and a padding slot. It took 13.95 s on four CPU cores. [Two tissue worlds and comparison](checks/chloride_channel.py) · [Independent scalar flux](../validation/betse/junction_transport/check.py#L10)

```json
{
  "engine_revision": "d4f1eaf723ee1bdd1e54d9be086cb81d67356bfa",
  "model": "resolved_pump_tissue@3", "law": "clleak_always_open@1", "backend": "cpu", "dtype": "float64",
  "solver": "imex_ars222_face_electromigration@1", "independent_solver": "DOP853",
  "dt_s": 0.000030517578125, "end_s": 0.00048828125, "temperature_K": 310.0,
  "bath_mM": [147, 70], "initial_voltage_V": -0.02151770525721294,
  "initial_outward_flux_fmol_s": [-0.005942329617988368, 0.05942329617988358],
  "initial_electrode_current_A": [5.733476467777896e-13, -5.733476467777887e-12],
  "final_outward_transfer_fmol": [-2.8824350858087033e-6, 2.88820012833921e-5],
  "max_transfer_error_fmol": 1.5791679555264733e-12, "material_atol_fmol": 1e-10,
  "max_electrode_current_error_A": 2.875735404806082e-21, "current_rtol": 2e-6,
  "paper_conditions": {"outside_mM": [145, 15], "temperature_K": 310.15, "model_reversal_shift_mV": 60.63433164318693}
}
```

At 37 °C in rabbit collecting-tubule principal cells, lowering nominal pipette chloride from 145 to 15 mM shifted the single-channel reversal about **+45 mV**. For those concentrations the Cells chloride-only pathway gives **+60.6 mV** at fixed intracellular chloride. The cell-attached voltage is relative to rest, and the paper gives no uncertainty on the shift. The result supports the direction of the response. Absolute permeability and intrinsic opening remain open. [Ling et al., Fig. 1B](https://doi.org/10.1172/JCI117037) · [Preparation and selectivity](claims/incoming/channel-gating-evidence.md#chloride-leak)

## 19 November 2026 · Ten ion-channel laws

For the eight voltage-dependent channel laws in `resolved_pump_tissue@3`, Lean proves that both gate targets lie in [0, 1] and both time constants are positive over the declared −120 to +60 mV domain. The exponential stage keeps the opening in [0, 1] for any nonnegative duration and any pair of admissible endpoint voltages. The proof covers the polynomial branch at small steps and the regularized NaV1.2 rates. The two gate-free leak laws have intrinsic opening one. On the permeant ion, opening times external availability scales the signed constant-field flux. The channel debits the cell and credits its exterior by that same flux. All other species receive zero. These theorems use the Cells constant-field and transfer proofs and Mathlib’s exponential inequalities. The 14 new theorems use only the standard Lean axioms. [Stage proof](CellsProofs/Transport/ChannelStep.lean) · [Channel laws and booking](CellsProofs/Transport/IonChannels.lean) · [Tissue stage](../src/cells/models/surface_pump_v3.py#L1257)

The CPU driver checks each law’s declared ion and opening powers against Lean and the compiled tissue dispatcher. For the five Kv1 laws with coefficient tables it also checks the Lean targets and time constants against the engine’s table entries symbolically. Scalar references in mV and ms cover all eight gated laws at 25 voltages, including NaV1.2’s removable singularities. In 72 additional stage cases the driver checked every combination of gate and endpoint targets at zero or one, including the floats immediately below and above the series switch. [Driver and synthetic world](checks/ion_channels.py) · [Kv1 reference](../validation/tissue/kv1_reference.py) · [Kir2.1 reference](../validation/tissue/kir_reference.py) · [NaV1.2 reference](../validation/tissue/sodium_reference.py)

One cell with a held bath carried all ten channels on one membrane. An external block lasted 0.24414 ms. All eight gate pairs moved during the block while every transfer stayed zero. After release the potassium routes carried outward flux and both sodium routes carried inward flux. Each channel’s flux and cumulative transfer, the cell and reservoir inventories, and the membrane voltage were checked against a separate adaptive integration of the capacitor and material balances with Decimal rates. Every off-ion and padding transfer was zero. The test used the ARS(2,2,2) integrator in float64. The driver took 29.62 s on four CPU cores. [Outward flux in the host](../src/cells/models/surface_pump_v3.py#L358) · [Independent constant-field calculation](../validation/betse/junction_transport/check.py#L10)

```json
{
  "engine_revision": "ec46f7a4e940b86c6fc110230b2bd851081dee50",
  "model": "resolved_pump_tissue@3", "backend": "cpu", "dtype": "float64",
  "solver": "imex_ars222_face_electromigration@1", "independent_solver": "DOP853",
  "dt_s": 0.0000019073486328125, "release_s": 0.000244140625, "end_s": 0.0009765625,
  "voltages": 25, "gate_pairs": 6, "stage_cases": 72, "max_stage_error": 2.220446049250313e-16,
  "max_target_error": 2.220446049250313e-16, "max_tau_error_s": 1.7763568394002505e-15,
  "max_opening_error": 2.7755575615628914e-17, "max_tissue_gate_error": 4.3100384372607436e-11,
  "max_flux_error_over_channel_peak": 3.8995113287681594e-10, "max_transfer_error_fmol": 2.3651329705171267e-13,
  "final_voltage_V": -0.039793205071044134, "gate_atol": 2e-6, "flux_atol_over_channel_peak": 2e-6, "material_atol_fmol": 1e-10
}
```

**Biological comparison.** Rat Kv1.1 whole-cell currents in CHO cells at 25 °C had a fitted decay time of 313 ± 82 ms (SD) at −20 mV. Under an assumed equilibrated −80 mV hold the same fit on the Cells current gave about 8.0 s, beyond the 1.5 s pulse. The model retained 88.3% of its peak current at pulse end. For adult human NaV1.2 at room temperature, the model current's 10–90% rise was 0.296 ms versus 0.38 ± 0.05 ms measured (SEM). Its inactivation midpoint was −54.9 mV versus −63.53 ± 0.79 mV. These are descriptive whole-current comparisons for the specified preparations. The evidence note also records the limitations for the other isoforms and the generic leak laws. [Search agent’s evidence and protocols](claims/incoming/channel-gating-evidence.md) · [Reproduce both model traces](checks/channel_clamp_evidence.py) · [Ranjan et al., Fig. 2C](https://doi.org/10.3389/fncel.2019.00358) · [Begemann et al., Table 2](https://doi.org/10.1186/s10020-019-0073-6)

For rat Kv1.4 a 3.2 s depolarization from −80 to 0 mV left **less than 2%** of peak oocyte patch current. Cells retained **0.57%**. Four published voltage-dependence parameters coincide with the engine’s, which limits the independence of this comparison. In a separate 30 °C HEK293 preparation, a +40 mV pulse elicited two fitted decay components. The Cells law has a single inactivation gate and retained 21.0% of its peak at 200 ms under that pulse. [Stühmer et al., Table I and Fig. 6](https://doi.org/10.1002/j.1460-2075.1989.tb08483.x) · [Roeper et al., Fig. 1](https://doi.org/10.1523/JNEUROSCI.17-10-03379.1997) · [Pulse calculations and definitions](checks/channel_clamp_evidence.py)

## 19 November 2026 · Hill activation and inhibition

The optional `grn-lean` check recompiled the original scalar monotonicity proofs and both Cells specializations on Lean 4.19.0. The axiom reports contain only `propext`, `Classical.choice` and `Quot.sound`. On the engine's 6 × 5 × 9 grid of half-saturations, exponents and concentrations, the compiled CPU factors were compared with the upstream formula evaluated at 65-digit precision using the exact binary inputs. All three engine Hill tests also passed, including the reaction-rate comparison in `resolved_pump_composite@1`. [Proof and upstream pin](checks/hill/check.sh) · [Numerical driver](checks/hill/compare.py) · [Reaction operator comparison](../tests/unit/test_hill_factors.py) · [Chemistry library assessment](ENGINE_LAW_VERIFICATION.md#chemistry-libraries-tested-against-cells)

```json
{
  "engine_revision": "6d74998581eab13d45327bc4801b463d0fb7a6f7",
  "grn_revision": "070ba8da6a09bdc4b0550396c61611668768bc0b",
  "backend": "cpu", "dtype": "float64", "cases": 540, "atol": 8.881784197001252e-16,
  "max_abs_error": {"hill_activation": 4.440892098500626e-16, "hill_inhibition": 4.718447854656915e-16}
}
```

## 19 November 2026 · Voltage-gated junction conductance

At a fixed junction voltage the law has one equilibrium conductance and one relaxation time. Lean proves that increasing voltage magnitude lowers the equilibrium when the residual fraction is below one. Starting anywhere in the allowed interval preserves its bounds. Reversing voltage polarity preserves the clamped trajectory, and splitting a constant-voltage interval preserves its final conductance. For three equally spaced samples of the deviation from equilibrium, the middle sample squared equals the product of its neighbors. Two exponential decays with positive amplitudes and distinct rates give a strict inequality instead. [Proof](CellsProofs/Transport/JunctionGate.lean) · [Rate equation and clamp update](../src/cells/laws/junctions/junction_voltage_relaxation.py#L41)

The compiled clamp update matched the reference at 45 voltage–time combinations. In a separate 62.5 ms run of `resolved_pump_tissue@3`, three cell pairs carried only a neutral tracer so their voltage differences stayed fixed at −80, 0 and +80 mV. External availability was zero for 31.25 ms. Tracer flux remained zero during the block while the intrinsic gates moved from 0.9 to **0.528734, 0.908373 and 0.528734**. On release the flux immediately reflected those three values. Both cell inventories and the junction transfers matched the integrated neutral-tracer solution. The reference evaluates the two voltage rates with 65-digit decimal arithmetic. The driver took 23.99 s on four CPU cores. Nineteen existing rate, clamp and host tests passed. [Driver and input world](checks/junction_gate.py) · [Scalar reference](../validation/betse/junction_gate/reference.py#L9) · [Clamp protocol](../validation/betse/junction_gate/protocol.json) · [Transport availability](../src/cells/models/surface_pump_v3.py#L733) · [Intrinsic gate derivative](../src/cells/models/surface_pump_v3.py#L779)

In seven wild-type Cx43 cell pairs, voltage-clamp fits gave residual normalized conductances of **0.35 ± 0.01** on the positive branch and **0.33 ± 0.01** on the negative branch (SEM). At −100 mV the same preparation showed a fast **70 ± 5 ms** decay and a slow **931 ± 54 ms** decay. The Cells reference parameters give **one 50.001 ms** time constant at that voltage. The two measured components limit the model's use for the full Cx43 trace. The voltage series leaves exact transient polarity symmetry and the external availability factor open. [Evidence note and normalization](claims/incoming/junction-gate-evidence.md) · [Sahu and Bera, Table 2 and Figure S2](https://pmc.ncbi.nlm.nih.gov/articles/PMC3607587/)

```json
{
  "engine_revision": "6d74998581eab13d45327bc4801b463d0fb7a6f7",
  "model": "resolved_pump_tissue@3", "law": "junction_voltage_relaxation@1",
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1", "jaxlib": "0.11.1",
  "threshold_V": 0.015, "residual_fraction": 0.1, "initial_gate": 0.9,
  "clamp_samples": 45, "max_clamp_error": 1.1102230246251565e-16,
  "max_three_sample_residual": 5.551115123125783e-17, "tau_at_minus_100_mV_ms": 50.000551675513144,
  "solver": "rk4", "dt_s": 0.00006103515625, "release_s": 0.03125, "duration_s": 0.0625,
  "junction_voltages_V": [-0.08, 0, 0.08], "gate_at_release": [0.5287339724666028, 0.908373067432633, 0.5287339724666028],
  "release_flux_fmol_s": [0.10574679449332056, 0.18167461348652658, 0.10574679449332056],
  "final_transfer_fmol": [0.002614271383999489, 0.0056791335747008315, 0.002614271383999489],
  "max_tissue_gate_error": 5.9396931817445875e-15, "max_transfer_error_fmol": 8.673617379884035e-18,
  "gate_atol": 5e-12, "flux_atol_fmol_s": 3e-12, "material_atol_fmol": 1e-10
}
```

## 19 November 2026 · Sodium-potassium and calcium pump charge

A forward Na⁺/K⁺-ATPase cycle exports three Na⁺ and imports two K⁺. The Cells plasma-membrane calcium pump exports one Ca²⁺ per forward cycle. Their outward charge flux in elementary-charge equivalents is therefore `J_NaK + 2 J_Ca`. Lean connects that count to the voltage term in the free energy of both pumps and proves each pump’s stall voltage and forward direction. Each pump runs forward above its own stall voltage when voltage is measured inside relative to outside. The seven theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ElectrogenicPumps.lean) · [Na⁺/K⁺ rate](../src/cells/laws/pumps/nak_atp_mass_action_positive.py#L63) · [Calcium rate](../src/cells/laws/pumps/ca_atp_mass_action_positive.py#L88) · [Ion flux and electrode current](../src/cells/models/surface_pump_v3.py#L783)

We initialized five independent cells in `resolved_pump_tissue@3` at each predicted stall, at the midpoint and 10 mV beyond each end of the interval. Each cell had its own held bath, the same maintained fuel concentrations and only the two pumps carrying current. Two independent 80-digit scalar calculations supplied the initial reference rates. The compiled tissue rates and energies matched at all five voltages, with stalls at **−99.365 mV for Na⁺/K⁺** and **−104.104 mV for Ca²⁺**. At the midpoint, we chose the calcium capacity so the two initial currents would cancel. Each contributed about 0.349 pA in opposite directions. The compiled electrode current was 2.04 × 10⁻²⁶ A. The 1 ms run accounted for Na⁺, K⁺ and Ca²⁺ in both the cells and the reservoirs and booked positive heat for each midpoint pump. The cancellation is an initial condition. The driver took 29.32 s on four CPU cores. Nine existing pump and declaration tests passed. [Driver and inputs](checks/electrogenic_pumps.py) · [Na⁺/K⁺ reference](../validation/betse/pump_contact/pump_reference.py#L83) · [Calcium reference](../validation/chemistry/finite_calcium_pump_reference.py#L19) · [Calcium tolerances](../validation/chemistry/finite_calcium_pump_protocol.json)

The experimental comparisons constrain the ion counts. Squid axon measurements pair sodium flux with electrical current, while red-cell ghosts pair sodium loss with ATP hydrolysis. In purified pig-brain calcium pumps, the measured Ca²⁺ and ATP rates give 1.02 Ca²⁺ per ATP. Including the measured inward H⁺ flux gives about +1.4 net charges per ATP in that preparation. The Cells law books +2 because calcium is its only transported ion. Applying its current to this preparation would require accounting for the protons. Experimental validation of the two calculated stall voltages remains open. [Measurements, conditions and uncertainties](claims/incoming/pump-charge-evidence.md) · [Squid axons, Table I](https://doi.org/10.1085/jgp.93.5.903) · [Red-cell ghosts](https://doi.org/10.1113/jphysiol.1967.sp008297) · [Calcium and proton flux, Table I](https://doi.org/10.1074/jbc.273.29.18230)

```json
{
  "engine_revision": "a06ee308a8348a5392e4645ccc368ccf8a086604",
  "model": "resolved_pump_tissue@3",
  "laws": ["nak_atp_mass_action_positive@1", "ca_atp_mass_action_positive@1"],
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1", "jaxlib": "0.11.1",
  "solver": "rk4", "dt_s": 0.00005, "duration_s": 0.001, "temperature_K": 298.15,
  "concentrations_mM": {"inside": {"Na": 12, "K": 140, "Ca": 0.0001}, "bath": {"Na": 145, "K": 5, "Ca": 2}, "maintained": {"ATP": 1.5, "ADP": 1, "Pi": 5}},
  "delta_g0_1M_J_mol": -30500, "nak_capacity_fmol_s": 0.1, "calcium_capacity_fmol_s": 0.1574830840232326,
  "initial_voltages_V": [-0.11410448475867015, -0.10410448475867015, -0.10173467077150977, -0.09936485678434939, -0.0893648567843494],
  "nak_stall_V": -0.09936485678434939, "calcium_stall_V": -0.10410448475867015,
  "max_cycle_error_fmol_s": 3.5041414214731503e-16, "max_current_error_A": 3.7966297646476856e-26,
  "midpoint_cycles_fmol_s": [-0.00361764979679795, 0.001808824898399081],
  "midpoint_electrode_current_A": 2.0419795228050456e-26,
  "midpoint_heat_pJ": [8.268047906450134e-7, 7.244105791341412e-7],
  "cycle_atol_fmol_s": 2e-12, "current_atol_A": 2e-22, "integrated_inventory_atol_fmol": 1e-15
}
```

## 19 November 2026 · ATP-driven transport

An enabled ATP cycle runs forward when its total free-energy change is negative, reverses when it is positive, and stalls at zero. Positive flux moves cargo from N to P and consumes ATP on side N. Lean proves these statements for the two branches of the engine’s rate formula and proves nonnegative heat in either direction. For a proton pump moving `n` protons per ATP, the stall voltage is `V_N − V_P = (RT/F) ln(a_P/a_N) + ΔG_fuel/(nF)`. For a neutral cargo, voltage drops out of the rate at fixed activities and capacity. All eight theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ATPCycle.lean) · [Proton cycle](../src/cells/laws/pumps/proton_pump.py#L223) · [Neutral cycle](../src/cells/laws/pumps/atp_transporter.py#L135) · [Shared rate formula](../src/cells/laws/cycles/forms.py#L893)

The compiled `resolved_pump_tissue@3` transporter matched the independent reference values at 92 states. Each of the four panels had 18 forward cases, four reverse cases and one nominal stall within the reference roundoff band. Heat was nonnegative at all 92 states. Disabling availability or setting capacity to zero gave exactly zero cycles, heat and work in all eight controls. At fixed chemistry, shifting the proton pump’s voltage by −10 or +10 mV about stall gave **−0.023228** and **+0.010986 fmol/s** respectively. The same offsets left all three flowing neutral controls unchanged. The driver took 4.52 s on four CPU cores. Six existing tests passed in 49.20 s, including two 4 ms tissue trajectories checking the material, charge and energy accounts. [Compiled comparison](checks/atp_cycle.py) · [Reference inputs](../validation/core_seams/references/reference_inputs.json) · [Frozen values](../validation/core_seams/references/designs/core_seams_reference_values.json) · [Reference tolerances](../tests/unit/test_cycle_kind_references.py#L296) · [Neutral run](../tests/unit/test_transporter_kind.py#L197) · [Proton run](../tests/unit/test_transporter_kind.py#L329)

```json
{
  "engine_revision": "a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3",
  "model": "resolved_pump_tissue@3", "kind": "cells.transporter@1",
  "laws": ["proton_atp_mass_action_positive@1", "atp_driven_transporter_mass_action_positive@1"],
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1",
  "states_by_panel": {"v1_proton_n2": 23, "v1_neutral_n1": 23, "v1_neutral_n2": 23, "ff_neutral_n1": 23},
  "forward": 72, "reverse": 16, "within_stall_band": 4, "off_controls": 8,
  "max_abs_error": {"dG_RT": 6.466044960882567e-15, "cycles_fmol_s": 7.494005416219807e-16,
                    "heat_pJ_s": 3.9968028886505635e-15, "work_pJ_s": 3.907985046680551e-14},
  "max_error_in_reference_floors": 0.441238400426874, "allowed_floors": 16
}
```

**Biological comparison.** Kettner et al. measured ATP-dependent current in isolated yeast vacuoles. At cytosolic pH 8.5 and vacuolar pH 5.0, Table 2 gives a mean reversal of **−17.5 ± 5 mV** (standard error, six trials). Using the paper’s estimated hydrolysis voltage and proton gradient, the proved stall relation gives `−587.5/2 + 207.2 = −86.55 mV` for two tightly coupled protons per ATP. The paper tabulates −86.5 mV, **69.0 mV below the observed mean**. Both use cytosol-minus-vacuole voltage. This comparison uses the authors’ fuel estimate and assumed coupling. They attribute the shifted current reversal to a parallel proton shunt. The neutral case has a separate experimental lead. Van Herwaarden et al. measured ATP-dependent riboflavin uptake into inside-out vesicles in Fig. 3E. A test of voltage independence needs matched gradients and multiple imposed voltages. [Kettner et al., Table 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC1303676/) · [Van Herwaarden et al., Fig. 3E](https://pmc.ncbi.nlm.nih.gov/articles/PMC1800714/)

## 19 November 2026 · Membrane insertion heat

Both versions of `scheduled_membrane_insertion` add uncharged membrane at fixed free-node charges and held bath potentials. They call `fixed_charge_change` and require every booked patch heat to be finite and at least zero. Lean shows that the exact field equations give the network heat in pJ as `(10¹²/2) Σ [C(ΔV)² + ΔC(V + ΔV)²]`. Here `V` is the old patch voltage and `ΔV` its change. Each term is nonnegative for nonnegative capacitances and additions. In one patch against a held bath, the heat is `(10¹²/2) C V² ΔC/(C + ΔC)` and the bath’s image charge change is exactly zero. All seven public theorems use the standard Lean axioms. [Proof](CellsProofs/Tissue/MembraneInsertion.lean) · [Shared field calculation](../src/cells/models/pump_composite_adapter.py#L959) · [Version 1 guard](../src/cells/operators/membrane_insertion.py#L424) · [Version 2 guard](../src/cells/operators/membrane_insertion_v2.py#L244)

**Engine finding, confirmed by the Cells lead.** Both operators refuse a 1 ms step on an admitted one-patch input with `ΔC/C = 1.7 × 10¹⁶` per initial half-step. The compiled CPU half-step computes **−0.043037 pJ**. An 80-digit calculation at the same initial charge gives **+0.051603 pJ**. The first energy term alone is about 8.77 × 10¹⁴ pJ, with float64 spacing of 0.125 pJ. The implementation adds a nearly equal correction of opposite sign. This stress input doubles the area on the first half-step using an extreme inserted specific capacitance of 8.5 × 10¹⁴ F/m². All 12 ordinary control half-steps passed at the existing relative tolerance of 10⁻⁹, and both 1 ms control runs completed. Four existing tests also passed, including two clamps and a finite cleft. [Reproducer](checks/membrane_insertion.py) · [One-patch fixture and tolerance](../tests/unit/test_membrane_insertion.py#L145) · [Two-version comparison](../tests/unit/test_membrane_insertion_v2.py#L203)

The same field solve gives **+0.051603 pJ** with the sum of squares. Substituting that heat alone in a separate diagnostic run exposed an electrode accounting failure. The unmodified field calculation gives **−3.638 × 10⁻¹² C** of bath image charge for this single patch. With the sum-of-squares heat and the known single-patch image charge of zero substituted, both runs completed. Multi-patch worlds can have real image charge at individual baths. The single-patch control isolates the two calculations involved in this refusal. [Image charge and heat](../src/cells/models/pump_composite_adapter.py#L985) · [Diagnostic controls](checks/membrane_insertion.py)

The lead assigned the robustness fix to the operators owner. The proposed change uses sum-of-squares heat and a cancellation-free image charge exact for one patch. A bitwise comparison of recorded worlds determines whether it lands with the declared numerical freeze batch. The failed comparison above records the original engine behavior. [Existing heat calculation for charge-following transfer](../src/cells/models/pump_composite_adapter.py#L1095)

```json
{
  "engine_revision": "06e25525a39f3a2995bd5aa26a7e38bd67b211c3",
  "model": "resolved_pump_composite@1", "inner": "resolved_pump_tissue@3",
  "operators": ["scheduled_membrane_insertion@1", "scheduled_membrane_insertion@2"],
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1", "jaxlib": "0.11.1",
  "half_step_s": 0.0005, "end_s": 0.001,
  "control_ratios": [0, 0.000001, 0.5, 1, 5, 1000], "control_cases_passed": 12,
  "max_control_relative_heat_error": 1.857494947841975e-14, "heat_rtol": 1e-9,
  "stress_ratio": 1.7e16, "stress_specific_capacitance_F_per_m2": 8.5e14,
  "initial_capacitance_F": 1.6306360828084532e-11, "initial_charge_C": -1.2972730823853619e-12,
  "computed_heat_pJ": -0.04303697682917118, "reference_heat_pJ": 0.05160309734417014,
  "sum_of_squares_pJ": 0.05160309734417019,
  "computed_image_C": -3.637978807091713e-12, "reference_image_C": 0,
  "stress_runs": {"original": "both refused the first step", "heat_only": "both failed electrode accounting",
                  "heat_and_single_patch_image": "both completed"}
}
```

## 19 November 2026 · Passive proton leak

For `proton_constant_field_leak@1`, an open route carries free H⁺ inward when the outside concentration exceeds the reversal concentration. With `x = F V/(RT)`, inside-minus-outside voltage and evaluator `B`, Lean gives that concentration as `hIn × B(−x)/B(x)` on both engine branches. The analytic constant-field law reverses at `V = (RT/F) × (ln hOut − ln hIn)` and releases nonnegative instantaneous heat. Those results also apply to the engine’s real-arithmetic formula at zero and for `|x| ≥ 10⁻⁴`. All seven public theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ProtonLeak.lean) · [Engine flux and heat](../src/cells/laws/transport/proton_leak.py#L28) · [Bernoulli evaluator](../src/cells/laws/electrochemistry.py#L17) · [Goldman’s constant-field model](https://doi.org/10.1085/jgp.27.1.37)

Inside the small-voltage branch the polynomial shifts the reversal ratio. At `x = 0.00009`, an 80-digit calculation found `B(−x)/B(x) − exp(x) ≈ 1.582 × 10⁻³³`, below float64 spacing near 1. Halfway between the thresholds the polynomial gives outward flux with a positive inward electrochemical drive. This limits the engine docstring’s unconditional instantaneous-heat sign claim. [Reversal calculation](checks/proton_leak.py) · [Engine heat contract](../src/cells/laws/transport/proton_leak.py#L35)

**Lead decision.** A numerical tolerance is sufficient. The instantaneous proton heat feeds the step booking. The charged leak uses the solver’s tableau, and the 16 ε negative-share floor applies to routes eligible for exact booking. The lead will clarify the heat docstring. Exact nonnegativity applies to the analytic law, with the polynomial and float64 covered to numerical tolerance. [Route selection](../src/cells/kinds/passive_routes.py#L246) · [Step booking](../src/cells/kinds/passive_routes.py#L500) · [Exact-share floor](../src/cells/kinds/passive_routes.py#L458)

Twelve compiled CPU float64 cases covered opposing drives, the Nernst crossing, blocking, partial opening and both sides of the two branch boundaries. The flux reference uses 70-digit Decimal arithmetic. In a 4 ms `resolved_pump_tissue@3` run, the buffered cell initially took up **3.310 × 10⁻⁶ fmol/s**. Using total intracellular proton equivalents in the reference gave **−3.183 fmol/s**. Two four-core runs took 13–16 s, and three existing law and tissue tests passed. [Driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10) · [Independent buffer closure](../validation/compartment_ph/ph_reference.py#L167) · [Tissue fixture](../tests/unit/test_proton_buffer_kind.py#L258)

```json
{
  "engine_revision": "1dee280f681af373071079c5f9b5921725dc7ed3",
  "model": "resolved_pump_tissue@3", "law": "proton_constant_field_leak@1",
  "backend": "cpu", "dtype": "float64", "component_cases": 12,
  "max_flux_error_fmol_s": 1.543812817544248e-20, "flux_atol_fmol_s": 4.7124e-17,
  "max_heat_error_pJ_s": 2.0328790734103208e-19, "heat_atol_pJ_s": 1.214613282895345e-16,
  "opposed_flux_fmol_s": -1.9698929665489864e-5, "nernst_residual_fmol_s": 4.3159515760814405e-21,
  "small_voltage_x": 0.00009, "outside_inside_ratio_shift": 1.581812000278e-33,
  "end_s": 0.004, "initial_voltage_V": -0.02151770525721294,
  "free_inside_mM": 6.309573444801929e-5, "total_inside_mM": 25.000063095734447,
  "free_outside_mM": 3.981071705534969e-5,
  "initial_inward_fmol_s": 3.3097843238305726e-6, "reference_inward_fmol_s": 3.309784324017176e-6,
  "using_total_inward_fmol_s": -3.183387556995154, "booked_heat_pJ": 1.1771717405987001e-8
}
```

**Biological evidence.** Schilling et al. measured reversal of an activated proton current in Jurkat T cells at 20–23 °C. Figure 2E gives a fitted slope of **−47 mV per unit of outside-minus-inside pH** across six gradients, alongside an ideal Nernst slope of **−58 mV per pH unit**. The observed shift has the predicted direction and is 11 mV per pH unit shallower. The figure reports group means and standard errors. Uncertainty in the fitted slope and the relation between pipette pH and intracellular pH matter for a quantitative comparison. The current amplitude also depends on channel opening. Biological validation of the Cells leak remains open. [Schilling et al., Fig. 2E and Methods](https://doi.org/10.1113/jphysiol.2002.028878)

## 19 November 2026 · Passive neutral permeation

For `passive_neutral_permeation@1`, the zero-valence specialization of the existing constant-field theorem gives inward flux `J = scale × (cOut − cIn)` at any voltage. In a closed pair of fixed positive volumes, the outside-minus-inside concentration difference changes at rate `−k × (cOut − cIn)`, with `k = scale × (1/vIn + 1/vOut)`. The three Lean theorems use the standard axioms `propext`, `Classical.choice` and `Quot.sound`. [Neutral proof](CellsProofs/Transport/NeutralPermeation.lean) · [Engine law](../src/cells/laws/routes/passive_permeation.py#L43) · [Tissue rate bound at full opening](../src/cells/kinds/passive_routes.py#L553)

Five compiled CPU float64 cases exercised both directions, equilibrium, a blocked route and partial opening. With 1 fmol inside 0.5 pL and 2 fmol outside in 2 pL, the solute flowed outward at 50 fmol/s. Following the amount difference would reverse that result. In a separate 20 ms `resolved_pump_tissue@3` run, both final compartment amounts agreed with the independent closed-form solution within the existing relative tolerance. The driver took 9.94 s on four cores and three existing tests passed in 12.21 s. Figure 3 of Lande et al. supplies urea-flux time courses for three liposome compositions. A quantitative comparison needs the gradients, area and permeability of a matched preparation. [Lande et al., Fig. 3](https://doi.org/10.1085/jgp.106.1.67) [Driver](checks/neutral_permeation.py) · [Analytic reference](../validation/passive/passive_reference.py#L66) · [Tissue fixture and tolerance](../tests/unit/test_passive_routes_kind.py#L64)

```json
{
  "engine_revision": "f130a109ad8861ce114f0f6fea3ece524465e80f",
  "model": "resolved_pump_tissue@3", "law": "passive_neutral_permeation@1",
  "backend": "cpu", "dtype": "float64", "component_cases": 5,
  "max_flux_error_fmol_s": 7.105427357601002e-15,
  "unequal_volume_inward_flux_fmol_s": -49.999999999999986,
  "end_s": 0.02, "reference_rate_per_s": 99.99999999999999,
  "inward_transfer_fmol": -0.0002160443856244789, "reference_transfer_fmol": -0.00021616617919084682,
  "max_final_amount_error_fmol": 1.2179356636795365e-7,
  "max_final_amount_relative_error": 0.0001700632756849268, "final_amount_rtol": 5e-4
}
```

## 19 November 2026 · Biological evidence review

The first literature handoff covered 11 of the 12 claims registered at review time. The reaction time courses below give a direct comparison of two measured pools. At this checkpoint, 11 biological claims were open and the retrospective RPTEC comparison was not assessable. [Claim index](README.md#proof-index) · [RPTEC closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

**Reaction inventory.** Eicher et al. measured glucose-6-phosphate and fructose-6-phosphate separately by ³¹P NMR. In their supplementary workbook `supp_data.ods`, the upper block of sheet `PGI` contains five time courses of peak integrals expressed in mM. For dataset 1, summing cells B4 and C4 gives 8.395747 mM at 1.33 min. B30 and C30 give 7.782390 mM at 35.91 min. The measured soluble pool changed by **−0.613357 mM (−7.31%)**. Three of the five courses decreased between their own first and last readings and two increased. Figure 4A reports a nominal starting condition and rounded endpoints with 60° pulses. Figure 5 uses 90° pulses. To interpret the drift, quantify the shared calibration uncertainty and any unobserved pools. Only the first listed acquisition has raw data in the supplement. Its metadata give 0.950 mL and 1.40 min per acquisition. The standard assay gives 1.00 mL and the workbook uses 1.33 min. Per-course volumes and timing remain unresolved. [Reaction claim](claims/reaction-inventory.md) · [Eicher et al., Figs. 4–5 and §3.3](https://www.mdpi.com/2218-1989/2/4/818) · [Publisher’s workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

| Claims | What the published evidence can test |
| --- | --- |
| Junction gradient, reversal, blocking and transfer orientation | Figure 2B of Palacios-Prado and Bukauskas tracks a charged tracer moving between two cells near zero junction voltage. The flux trace is normalized. Zonta et al. estimated **226 ± 75 calcein molecules/s per open Cx26 channel** at a 125 μM gradient. Only the donor was voltage-clamped during that transfer interval. Figure 1 of Wang and Veenstra shows paired electrical currents. The bovine block and washout traces are **Wang et al. (2010), Fig. 2E–F**. A species-specific rate needs ion or tracer calibration, and a quantitative blocking test needs a residual detection limit. [Tracer](https://pmc.ncbi.nlm.nih.gov/articles/PMC2736430/) · [Calibrated calcein flux, Fig. 1A–C](https://doi.org/10.1186/1478-811X-11-15) · [Paired currents](https://pubmed.ncbi.nlm.nih.gov/9101407/) · [Block study and byline](https://pubmed.ncbi.nlm.nih.gov/20089928/) |
| Extracellular face direction and dissipation | Weber et al. (Fig. 6) measured net current reversal across a claudin pore. Galvez et al. (Fig. 3 and Tables 1–2) measured sodium tracer fluxes in epithelia with active uptake. Passive-face power needs signed net flux, activities and voltage across the same passive path. [Claudin recordings](https://elifesciences.org/articles/09906) · [Sodium flux measurements](https://www.zoology.ubc.ca/~woodcm/Woodblog/wp-content/uploads/2016/07/Galvez-et-al.-2008-In-Vitro-Cell.pdf) |
| Regional transfer and reaction–transport inventories | Kuki et al. (Figs. 3–4) compared myocardial K⁺ depletion and coronary effluent loss in separate preparations. Fausto (Fig. 1) tracked carbon-6 label across tissue, perfusate, bile and CO₂. A closure residual needs amounts on a common boundary and time interval, with sampling and omitted pools accounted for. [Heart potassium](https://doi.org/10.1161/01.RES.67.2.401) · [Liver tracer](https://doi.org/10.1042/bj1290811) |
| Enzyme and substrate inventories | The isomerase NMR study resolves bound ligand states. The chymotrypsin mass spectra resolve an enzyme intermediate. Testing both inventories needs calibrated amounts of free enzyme, substrate, complex and product in the same preparation. [Bound states, Figs. 3–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC1794347/) · [Enzyme intermediate, Figs. 1–3](https://www.derekwilsonlab.ca/userfiles/files/TRMS_Applied_to_Enzymes.pdf) |
| RPTEC C3 voltage | Bonzanni et al. (Fig. 3C) reported 20 cells across three experiments. The ±2 mV in the Cells record is figure-reading uncertainty. Experiment-level uncertainty for the +3.41 mV prediction residual is unresolved. [Primary study](https://doi.org/10.1242/bio.048553) · [Existing comparison](claims/rptec-voltage-c3.md) |

**Single-site binding** was the missing claim. A primary lead is the human myoglobin oxygen-equilibrium study by Rossi-Fanelli and Antonini. Look for observed site occupancy across known free ligand values, record temperature and solution conditions, and identify which observations set the affinity and which test it. For oxygen pressure, report the solubility used to convert to dissolved concentration or compare the dimensionless pressure ratio at the same temperature. A myoglobin comparison would test the one-site curve in that preparation. [Cells binding claim](claims/single-site-binding.md) · [Human myoglobin study](https://pubmed.ncbi.nlm.nih.gov/13584010/)

**Research follow-up.** I reproduced the proposed within-figure comparison for human myoglobin at 10 °C. Of the first five published digitized points, fitting the first and fourth gave a half-saturation pressure of 0.3311 Torr. The other three had a root-mean-square occupancy residual of 0.0422. This retrospective split shares a preparation and a figure, with unknown pointwise uncertainty. The PGI workbook gave first-to-last changes in measured G6P + F6P of −0.613357, −1.534898, +0.099302, +0.391083 and −0.207509 mM for datasets 1–5 respectively. Both biological assessments remain open. [Myoglobin experiment](https://pubmed.ncbi.nlm.nih.gov/13584010/) · [Caltech’s Fig. 2 digitization](https://bi1.caltech.edu/2017/code/t05_nonlinear_regression.html) · [PGI workbook](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

## 19 November 2026 · Single-site binding and face-power units

For `rapid_binding@1`, Lean derives the bound fraction from equal forward and reverse rates and recovers the same fraction from the two form weights used by Cells. The local proof specializes the Langmuir argument to a free ligand concentration and a dissociation constant, both in mM. The comparison ran the compiled law on all thirteen manufactured S1 states and the stage read on the first state in `resolved_pump_tissue@3`. Reference tolerances are twice the recorded floor on the log of each concentration. A common binder total cancels when taking the ratio of two bound fractions. The driver took 5.79 s on four CPU cores. Three existing kernel and tissue checks passed in 6.59 s. Experimental binding data remain open. [Binding proof](CellsProofs/Chemistry/SingleSiteBinding.lean) · [Upstream theorem](https://github.com/ATOMSLab/LeanChemicalTheories/blob/00841fedb86c0af282f515eda7e83a525a42e048/src/adsorption/langmuir_kinetics.lean) · [Driver](checks/single_site_binding.py) · [Independent reference design](../validation/core_seams/references/README.md#L101) · [Tolerance calculation](../tests/unit/test_rapid_binding_kernel.py#L127)

```json
{
  "engine_revision": "9a5bc6b8211847888cbb83c41ad88941bac19213",
  "model": "resolved_pump_tissue@3", "law": "rapid_binding@1",
  "backend": "cpu", "dtype": "float64", "reference": "S1", "states": 13,
  "kd_mM": 9.999999999999994e-5, "fraction_range": [0.038286503882254776, 0.999000999000999],
  "max_fraction_error_vs_reference": 3.3306690738754696e-16,
  "max_fraction_error_vs_formula": 1.1102230246251565e-16,
  "total_ligand_control_failures": 13, "tissue_state_0_fraction": 0.5812579461704979
}
```

For `logmean_electrodiffusion@1`, the default proof checks the exact scale from fmol/s × J/mol to pJ/s. An optional import checks the physical dimensions using ATOMS Lab's amount, time and energy. A first build of upstream revision `de263eed` on Lean 4.19 failed on the newer Mathlib matrix-rank module name. Changing that one import in the build copy let both upstream modules compile. Omitting the molar denominator in a negative control left an uncancelled amount dimension and Lean rejected the equation. The dimension proof uses `propext` and `Quot.sound`. The two binding theorems and scalar conversion also use `Classical.choice`. With compiled Mathlib available, the optional check took 10.09 s including the first source download. Warm default builds measured 4.01 s before the additions and 3.75 s afterward on this checkout. [Units check](checks/units/FacePower.lean) · [Reproduction script](checks/units/check.sh) · [Engine multiplier](../src/cells/numerics/surface_transport.py#L312) · [Pinned package](https://github.com/ATOMSLab/LeanDimensionalAnalysis/tree/de263eed945693058ef2b8a1fa56c2ec5642ea7a) · [SI prefixes](https://www.bipm.org/en/measurement-units/si-prefixes)

## 19 November 2026 · Extracellular face electrodiffusion

Eight Lean theorems check the two log-ratio branches, positivity and symmetry of the implemented mean (including its small-gradient polynomial), flux reversal, equilibrium, direction and instantaneous dissipation per species and per face. They use the standard axioms `propext`, `Classical.choice` and `Quot.sound`. The force is sender minus receiver electrochemical potential. The direction equivalence requires a positive face coefficient. [Face proofs](CellsProofs/Transport/LogMeanFace.lean) · [Mean](../src/cells/numerics/extracellular_field.py#L48) · [Flux and power](../src/cells/numerics/surface_transport.py#L292)

The development comparison ran eleven CPU float64 cases and one closed `resolved_pump_tissue@3` world with `logmean_electrodiffusion@1`. For each active species and face at each observation time, the independent scalar mean and the declared geometry gave a reference flux. The driver took 17.46 s on four cores. Sixteen existing surface and scalar-reference tests passed in 8.91 s. [Inputs and JSON results driver](checks/logmean_face.py) · [Independent reference](../validation/tissue/surface_reference.py#L13) · [Tolerances](../validation/tissue/surface_protocol.json#L27)

At zero voltage, concentrations of 100.00000000000001 and 100 mM gave a positive reference flux and zero computed flux. The engine subtracts the two rounded logs in its driving force. The difference falls within the protocol's absolute flux tolerance. At a resolved gradient, deliberately reversing the flux and both endpoint bookings conserved total material but produced negative power and failed the direction check. These are development checks under supplied or simulated endpoint conditions. Biological face-flux measurements remain open.

```json
{
  "engine_revision": "c9549dfc553ce2e9cce5d05160c24b1879e3077b",
  "backend": "cpu", "dtype": "float64", "component_cases": 11,
  "flux_atol_fmol_s": 3e-12, "physical_rtol": 3e-10,
  "opposed_flux_fmol_s": -0.0004999999999999968,
  "reversed_flux_fmol_s": 0.0004999999999999968,
  "balanced_flux_fmol_s": 3.361730104660899e-18,
  "adjacent_float64": {"flux_fmol_s": 0, "reference_fmol_s": 1.4210854715202002e-18},
  "reversed_flux_control": {"total_rate_fmol_s": 0, "power_pJ_s": -4.522364735283246e-5},
  "tissue": {
    "model": "resolved_pump_tissue@3", "law": "logmean_electrodiffusion@1",
    "solver": "imex_ars222_face_electromigration@1", "samples_species_faces": [3, 4, 5],
    "max_flux_error_fmol_s": 1.496198998029996e-17, "max_abs_transferred_fmol": 9.758954574665261e-6
  }
}
```

## 19 November 2026 · Regional reaction and transport balance

Lean checked the regional balance for a reaction–transport–reaction step and its whole-graph corollary. The proof uses the earlier chemistry theorem separately on each reaction half-step. The transfer theorem cancels every internal edge. Only the reactions inside the chosen region need to balance its inventory. Both results use the standard Lean axioms `propext`, `Classical.choice` and `Quot.sound`. [Regional proof](CellsProofs/Tissue/ReactionTransport.lean) · [Engine split order](../src/cells/models/pump_composite.py#L1308)

The development comparison ran one 50 ms step of `resolved_pump_composite@1` with `local_species_reactions@1` and the `resolved_pump_tissue@3` face solver. Four of the twelve finite extracellular compartments formed the region. A and B interconverted there, while one boundary face brought material in and the other carried it out. Both the individual species balances and the A + B inventory passed. Reversing the larger boundary face in the recorded transfers failed the regional check and passed the whole-chain check. The driver took 17.99 s on four CPU cores. The existing 200-step passive-chain test against the independent reference passed in 19.76 s. [Inputs and driver](checks/regional_balance.py) · [Closed pair](../validation/morphogenesis/mg0c_turing.py#L180) · [Reference test](../tests/unit/test_species_reactions_composition.py#L84) · [Tolerance rule](../tests/unit/test_species_reactions_composition.py#L321)

```json
{
  "engine_revision": "030bd02a5f4bb74d15ef8bde4fdf1db03f69b801",
  "backend": "cpu", "dtype": "float64", "step_s": 0.05,
  "region": ["node_2", "node_3", "node_4", "node_5"],
  "region_balance": {
    "inventory_change_fmol": 1.2526038874940276e-6,
    "boundary_inflow_fmol": 1.2526038874941343e-6,
    "crossing_faces_fmol": {"face_1": 3.5748138477117313e-6, "face_5": -2.322209960217597e-6},
    "reaction_extent_fmol": 1.7563691429785305e-5,
    "max_species_residual_fmol": 9.147955830346444e-20,
    "residual_fmol": -1.0672615135404184e-19, "tolerance_fmol": 5.578917767468619e-17
  },
  "whole_chain": {"residual_fmol": -1.6263032587282567e-19, "tolerance_fmol": 1.7053025658242405e-16},
  "reversed_face": {
    "id": "face_1", "region_residual_fmol": 7.149627695423356e-6,
    "whole_chain_residual_fmol": -1.6263032587282567e-19
  }
}
```

## 19 November 2026 · Closed enzyme reactions

Lean 4.19.0 checked the general conservation theorem, the two enzyme-fixture inventories and the missing-enzyme counterexample. All four use only the standard Lean axioms `propext`, `Classical.choice` and `Quot.sound`. Four additional equalities matched the fixture’s integer columns and weights to the Lean definitions. Replacing the catalytic products with P alone made the column equality fail in Lean. [General theorem](CellsProofs/Chemistry/Stoichiometry.lean) · [Fixture proofs](CellsProofs/Chemistry/Enzyme.lean) · [Declaration](../validation/tissue/species_reactions_fixtures.py#L248)

The development comparison ran one JIT-compiled half-step of `local_species_reactions@1` on `resolved_pump_composite@1` from `enzyme_recipe(1e-12)`. At `cell_0`, X counts substrate (S + C + P) and Y counts enzyme (E + C). The driver took 11.51 s on four CPU cores, including Lean’s declaration check. The two existing tests for stored amounts and refusal of an unbalanced reaction passed in 3.05 s. [Driver and JSON output format](checks/closed_enzyme.py) · [Amount and inventory tolerances](../tests/unit/test_species_reactions_halfstep.py#L275) · [Refusal case](../tests/unit/test_species_reactions_refusals.py#L119)

```json
{
  "engine_revision": "a124c937041353d395732a936a3d2b1001c2b63a",
  "backend": "cpu",
  "dtype": "float64",
  "half_step_s": 0.0125,
  "extent_fmol": {"binding": 1.2338087167211897e-6, "catalysis": 7.711641577505311e-9},
  "max_species_residual_fmol": 1.122318655111948e-20,
  "inventory_residual_fmol": {"X": -1.1206642938868419e-20, "Y": 6.776263578034403e-21},
  "inventory_tolerance_fmol": 6.938893903907228e-18,
  "missing_enzyme": {"inventory_change_per_catalytic_event": {"X": 0, "Y": -1}, "engine_admission": "refused"}
}
```

The conservation theorem applies to any signed reaction extents in exact arithmetic. The CPU result measures the implementation on this fixture. Reaction-rate accuracy and tissue-level composition are separate claims.

## 19 November 2026 · Junction transport

Eight Lean theorems cover the constant-field flux and finite-graph transfer accounting. The development comparison used engine revision `109a7355ed85`, CPU float64 and four CPU cores. The driver took 18.79 s, including the integrated `resolved_pump_tissue@3` world. The 11 component tests passed in 9.46 s. The largest per-cell rate difference from the reference was 1.36 × 10⁻²⁰ fmol/s against a tolerance of 3 × 10⁻¹⁴ fmol/s. Swapping the owners gave a 2.40 × 10⁻⁴ fmol/s discrepancy. The tissue’s potassium transfer reached 2.18 × 10⁻⁶ fmol and its maximum global material residual was 3.25 × 10⁻¹⁹ fmol. The pilot source was checkpointed in `627c376c`. [Comparison](checks/constant_field.py) · [Flux proof](CellsProofs/Transport/ConstantField.lean) · [Accounting proof](CellsProofs/Accounting/Transfer.lean)
