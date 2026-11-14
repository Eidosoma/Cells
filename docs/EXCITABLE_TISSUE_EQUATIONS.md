# Excitable-tissue probe: the active equations, for an independent reference (draft)

**Status.** Draft of 14 November 2026, by Track E (D155). It is the equations appendix for the
independent reference that the coordinator commissions if the probe's single cell
regenerates. It states the equations the conduction probe
(`validation/tissue/excitable_probe.py`) runs, completely enough to implement them without
reading the engine.

**Rules for whoever writes the reference:**
- Do not read `src/cells`, the probe driver or the probe's records until the reference's own
  results are saved.
- This appendix is self-contained. The documents cited below are provenance and are not
  needed to implement it.
- §7.2 gives the two cells to compute: the heredity cell (the plan's) and point 2 (the
  chain's).

**Sources.** The gate laws are BETSE v1.5.0's Kv1p5, Kir2p1 and Nav1p2 channel classes
(BETSE commit `5269a714`), as restated in Cells' docs
([sodium catalogue](SODIUM_CHANNEL_CATALOG.md), [tissue channels](TISSUE_RETURN_CURRENT.md)).
The flux law is the Goldman–Hodgkin–Katz constant-field flux. The pump law is
`nak_atp_mass_action_positive@1` ([kinetic pump process](KINETIC_PUMP_PROCESS.md)). These are
parity laws with no biological calibration. The reference checks that the engine integrates
them; it does not check that they are right for any cell type.

## 1. Constants, species and units

- N_A = 6.02214076e23 /mol, e = 1.602176634e-19 C, k_B = 1.380649e-23 J/K.
- F = N_A·e = 96485.33212331001 C/mol, and R = N_A·k_B = 8.31446261815324 J/(mol K).
- T = 310 K. A catalogue cross-check also runs at 298.15 K.
- Species s and valence z_s: Na (+1), K (+1), M (−1, a permeant anion), P (−1, impermeant).
- Units:
  - Concentrations c in mM, which equals mol/m³. Amounts N in mol (the engine's records use
    fmol, 1e-15 mol).
  - Volume in m³, area in m², permeability in m/s, potential in V, time in s.

## 2. The cell, its bath and its voltage

- **Each cell i** is one well-mixed compartment.
  - Volume V_c = 0.7505222518670602 pL, that is 7.505222518670602e-16 m³.
  - One membrane patch of area A = 3.261272165616906e-10 m².
  - Capacitance C = c_m·A, with c_m the specific capacitance (§7).
- **Each cell faces its own bath.**
  - The bath is held: its concentrations are fixed (Na 145, K 5, M 140, P 10 mM).
  - Its potential is held at 0 V.
  - Baths are not coupled to each other.
- **Membrane voltage.** V_i = φ_cell,i − φ_bath,i = q_i / C. The net charge is
  q_i(t) = C·V_i(0) + F Σ_s z_s (N_s,i(t) − N_s,i(0)).
- **P is impermeant**: N_P is constant at 135 mM × V_c.

## 3. The constant-field flux

For a route of area a and effective permeability p between side 1 (concentration c₁,
potential φ₁) and side 2 (c₂, φ₂), the flux from 1 to 2 of species s, in mol/s, is

    J = a · p · [ c₁ · B(−x) − c₂ · B(x) ],    x = z_s F (φ₁ − φ₂) / (R T),
    B(x) = x / (e^x − 1),   B(0) = 1   (removable singularity; use a series near 0).

**Membrane routes.** Side 1 is the cell and side 2 the bath, so φ₁ − φ₂ = V_i. A positive J
is outward.

**Effective membrane permeability of species s** is the sum of three terms:
- the leak P_leak,s: Na 5.3333333333333356e-11, K 1.333333333333334e-10,
  M 1.333333333333334e-10 and P 0 m/s, always open;
- each channel population of that ion, P_max × abundance × opening(gates) × availability,
  where abundance is 1 and availability is 1 unless a protocol sets it;
- the stimulus populations (§6) when they are on.

## 4. Gate laws

Each gated population has gates m and h with dg/dt = (g∞(V) − g) / τ(V). Every gate starts
at its steady state g∞(V_rest).
- V is in volts.
- σ(u) = 1/(1 + e^(−u)) is the logistic function.
- Every law is defined only for −0.120 ≤ V ≤ 0.060 V. The engine refuses a step outside that
  range, so report any excursion beyond it.

**Kv1.5** (K; opening m·h):

    m∞ = σ((V + 0.0060)/0.0064)       τm = 0.008330 − 0.1163 V
    h∞ = σ(−(V + 0.0253)/0.0035)      τh = 1.620000 − 15.500 V

**Kir2.1** (K; opening m·h²):

    m∞ = σ(−(V + 0.09648)/0.02326)    τm = 0.0037 − 0.00337 σ(−(V + 0.0329)/0.02793)
    h∞ = σ((V + 0.16828)/0.04413)     τh = 0.00085 + 0.3063 σ((V + 0.11829)/0.02723)

**NaV1.2** (Na; opening m³·h). Rates are per millisecond, and u = (V + 0.025)/0.009:

    αm = 0.182 · 9 · B(−u)            βm = 0.124 · 9 · B(u)
    αh = 0.024 · 5 · B(−(V + 0.040)/0.005)
    βh = 0.0091 · 5 · B((V + 0.065000123)/0.005)
    m∞ = αm / (αm + βm)               τm = 0.001 / (αm + βm)   (s)
    h∞ = 1 / (1 + exp((V + 0.055)/0.0062))
                                      τh = 0.001 / (αh + βh)   (s)

Note that h∞ is **not** αh/(αh + βh); it is the separate logistic above.

**Leaks** (K and Na leak populations) have opening 1 and no gate.

## 5. The Na/K pump (`nak_atp_mass_action_positive@1`)

Per cell, the pump turns over at a rate ν (mol cycles/s). Each cycle moves 3 Na out and 2 K
in.

- **Inward potentials.** For each ion, Δμ_s = R T ln(c_s,i / c_s,o) + z_s F V_i, the free
  energy of moving one mole from the bath into the cell.
- **Drive.** G_drive = ΔG₀ + R T ln(ADP · Pi / (ATP · 1000 mM)), with ΔG₀ = −37000 J/mol,
  ATP 1.5 mM, ADP 0.1 mM and Pi 0.1 mM held.
- **Cycle free energy.** G = G_drive − 3 Δμ_Na + 2 Δμ_K, and a = G/(R T).
- **Saturation.**

      sat = 1/(1 + (K_Na/c_Na,i)³) · 1/(1 + (K_K/c_K,o)²) · 1/(1 + K_ATP/ATP)

  with K_Na = 12 mM, K_K = 0.2 mM and K_ATP = 0.5 mM.
- **Rate.** ν = ν_max · sat · (1 − e^a). Compute it as e^max(a,0) · (e^(−a) − 1) when a ≥ 0,
  for range, which is algebraically the same. ν_max = 1e-7 mol/(m² s) × A =
  3.261272165616906e-17 mol/s.
- **Transfers.** dN_Na,i += −3ν and dN_K,i += +2ν.

## 6. Junctions, stimuli and kicks

**Gap junctions.** A chain joins cell i to i + 1 by one junction.
- Area a_j = 9.25e-6/√3 × 1.0e-5 = 5.340489990004038e-11 m².
- Permeabilities: s_c × D_s × 5.0e-8 / 26.0e-9, with D = Na 1.33e-9, K 1.96e-9, M 1.0e-9 and
  P 0 m²/s. At s_c = 1 that gives Na 2.5576923076923074e-9, K 3.7692307692307685e-9 and
  M 1.923076923076923e-9 m/s. Here s_c is the coupling factor of §7.
- Flux: §3 with side 1 = cell i, side 2 = cell i + 1 (both cytoplasmic concentrations) and
  φ₁ − φ₂ = V_i − V_{i+1}. The junction gate is pinned open at 1.
- The engine refuses a step where any |V_i − V_{i+1}| exceeds 0.120 V, so report the largest
  transjunctional voltage.

**Stimulus.** A stimulated cell carries one K leak and one Na leak population, each of
permeability P_stim. They are on (availability 1) for t in [t_on, t_off) and off otherwise.
Their reversal is near 0 mV.

**Kick.** A kick of ΔV raises the initial Na amount by C·ΔV/F, so that V(0) = V_rest + ΔV.
The gates stay at their V_rest steady state.

## 7. Parameters

### 7.1 Fixed for every point

The cell geometry, the leaks, the pump, the bath and the junction law are as above.
- **Initial composition** (the heredity pre-screen's H state): Na 5.934560723484736,
  K 136.17199964403224, M 7.124496086230464 and P 135 mM.
- **Heredity rest:** V_H = −0.07955626004246525 V.

### 7.2 The points

The probe's chain runs at **point 2** of its density scan: amendment 2 of the probe's plan
(`/mnt/workspaces/Cells/excitable-tissue-20261114-01/PLAN.md`). The reference computes both
columns. The heredity column is the plan's own single cell; the point-2 column is the cell
of the chain.

| Symbol | Meaning | Heredity cell | Point 2 |
| --- | --- | --- | --- |
| c_m | specific capacitance (F/m²) | 0.05 | 0.05 |
| P_NaV | NaV1.2 maximum permeability (m/s) | 2.5e-7 | 1e-6 |
| P_Kir | Kir2.1 maximum permeability (m/s) | 1e-8 | 1e-8 |
| P_Kv | Kv1.5 maximum permeability (m/s) | 0 | 3e-7 |
| V_rest | the rest the cells start from (V) | V_H itself | after the 2 s relaxation of §8.1 |

**Notes on the rows:**
- Every other value is §7.1's.
- Kv1.5 = 0 means the heredity cell carries no Kv1.5 population at all.
- The reference computes V_rest itself, following §8.1; it should not take the value from
  the engine.

## 8. Protocols and what to report

Everything below is per cell unless stated.

### 8.1 Rest
- **Heredity point:** start at H.
- **Any other point:** integrate 2 s unstimulated from H's composition, with V(0) = V_H and
  gates at V_H's steady state. Take V_rest = V(2 s). Then start every protocol from H's
  composition with V(0) = V_rest and gates at V_rest's steady state. The composition is
  deliberately reset to H's; the charge follows from V(0).

### 8.2 Single cell
- **Kick threshold:** the smallest kick in [0, 60] mV whose peak exceeds 0 mV.
- **At twice that kick, capped at 60 mV:**
  - with NaV unavailable (availability 0);
  - with NaV, Kv and Kir all unavailable;
  - at threshold ± 0.5 mV and at threshold − 5 mV.
- **For each run, report:**
  - peak V and the time to peak;
  - the largest dV/dt;
  - APD50 and APD90 from the time of the largest dV/dt;
  - whether V returns within 5 mV of rest within 60 ms;
  - V at 80 ms.

### 8.3 Stimulus and recovery
- **Stimulus threshold:** the smallest P_stim on [1e-9, 1e-6] × (c_m / 0.05) m/s for a 1 ms
  stimulus at t = 2 ms that gives an overshoot.
- **S1–S2 at twice that P_stim:** S1 at 2 ms, S2 at 2 ms + Δ, with
  Δ ∈ {5, 8, 10, 12, 15, 20, 25, 30, 40, 60} ms.
- **S2 responds** if, after S2's onset, V newly crosses −30 mV upward and then exceeds 0 mV.

### 8.4 Chain
- **Set-up:** N = 20 cells (and 40 for the length check), with cells 0–2 stimulated at
  P_stim = 1e-6 × (c_m / 0.05) m/s for t in [2, 3) ms. Stimuli scale with c_m so that their rate
  (G/C) is the same at every point.
- **Activation time** of each cell: its first upward crossing of −30 mV, interpolated
  linearly.
- **CV** = 1 / (the least-squares slope of activation time against cell index) over cells
  N/3 to 2N/3, in cells/s.
- **Report:**
  - activation times and peaks for s_c ∈ {10, 30, 100, 300, 1000, 3000};
  - at s_c = 1000, the NaV-disabled and passive controls;
  - the coupling bracket between block and propagation;
  - the capture threshold in P_stim;
  - the S1–S2 interval for a second wave at the far end.

## 9. What the reference must provide

- **The integrator.** An implementation of §2–§6 with its own stiff integrator at tight
  tolerances, for example an implicit Runge–Kutta method with relative tolerance 1e-10.
  Include its own convergence check: the results do not move when the tolerance is tightened.
- **Results.** The numbers of §8, with the integrator and tolerances that produced them.
- **Independence.** No engine code may be read or imported. The comparison with the engine's
  records, and its tolerances, belong to a protocol the lead registers. The reference does
  not set them.
