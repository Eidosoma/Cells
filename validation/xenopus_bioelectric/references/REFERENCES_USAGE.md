# Using XC0's references: interface only

This note says how a comparison reads the registered values and bands, without reading their source.

**Files** (all under `designs/`, plus the inputs beside this note):
- `reference_inputs.json`: a byte copy of the frozen `declared_inputs.json` (19 November 2026, 13:35 UTC).
  The engine builds its worlds from the declared inputs, never from the values.
- `designs/xc0_reference_values.json`: every reference as a 50-digit decimal string.
- `designs/xc0_interface_bands.json`: the band rule, the floor model, every row's floor and band, the plants with
  their margins, and the zero-power list.

**Environment:** `/mnt/workspaces/Cells/venv-cpu/bin/python` with `PYTHONPATH` at the checkout. The values are
strings: read them with `decimal.Decimal`, or `float` for a float64 comparison.

## Rows

A **row** is one compared quantity at one registered state. Rows are grouped in **families**; a family is a claim's
observable, for example `C2.V_ghk_area`. In the values file:

    families[<family>]["values"][<key>]   the reference (string)
    families[<family>]["aux"][<key>]      for sign rows only: the underlying quantity

In the bands file `families[<family>]` holds `claim`, `quantity`, `unit`, `kind`, `tol_abs`, `tol_rel`,
`tol_source` (which DESIGN.md section the tolerance comes from, or `proposed`/`borrowed` where DESIGN.md gives none),
`note` and `rows[<key>] = {"floor", "band"}`.

**Kinds:**

| Kind | Comparison |
| --- | --- |
| `abs` | pass iff `abs(engine - reference) <= band` |
| `sign` | the engine's value has the sign of the reference (1, 0 or -1); compared only when `abs(aux) > band`, otherwise the row has no power |
| `exact_zero` | the engine's value is exactly 0 (availability 0) |
| `flag` | `"true"`/`"false"` equality |
| `info` | not compared (a context value) |

**The band rule (one rule, every row):**

    band = max( tol_abs + tol_rel * |reference| , 10 * floor )

`floor` is the float64 rounding floor of the row (floor model below). The tolerance is DESIGN.md's; where DESIGN.md
gives none the family says `proposed` or `borrowed`. These choices are mine and open to the lead's ruling by a dated note.

## Keys (registered states)

- **State key** `ionset|exterior|T<K>`: ion sets `primary`, `bracket_Cl_high`, `bracket_second_hand_table`; exteriors
  `bath` (0.1x MMR), `local` (the local node), `bath70_Na` (70 mM Cl-, sodium salt), `bath70_inert` (70 mM Cl-, inert
  cation, Na_out stays 9.9 mM), `bath_Cl10` and `bath_Cl11p1` (bath Cl 10.0 and 11.1 mM, others as 0.1x MMR); temperatures
  `291.15` and `287.15`. C0, C1, C2, C4 and C8a run all 36 states; C3, C5, C6, C7 and C8b run the scenarios below.
- **C3 scenario** keys: `S1_leaks_bath` to `S9_leaks_bath_T287` (see the family notes); `|d<delta>` is the step
  V_0 - V_inf in volts; `|k<n>` is the observation at t = n tau_lin/4.
- **C4 keys:** `<state>|P<P_GlyR>|a<availability>` and `<state>|g<g_ref>|a<availability>`.
- **C5 keys:** scenarios `sym`, `kir_g<g_ref>` (cell 2 has the Kir route), `x_gly<P_GlyR>` (supplementary, outside DESIGN:
  cell 2 has the Cl- patch open); `|x<m>` multiplies the declared junction permeability by m.
- **C6 keys:** `n<n>|Nain<Na_in>|Naout<Na_out>|BP<B_out>|rB<B_in/B_out>|T<K>` (stall states), `|off<V offset>` (a voltage
  offset from the stall), `|V<V>` (a fixed voltage), `NaP..|BP..|BN..|V..` (version 2).

## Units and signs

SI for geometry, permeability, potentials and currents; mM for concentrations; fmol for amounts; s; energies in J/mol
(per mole of cycles) and heat power in fW (fmol/s x J/mol). Constants are the declared doubles (F, R) and
CHARGE_PER_FMOL. V = inside - outside. Currents are outward positive: an anion entering the cell is a positive current.
The Cl- Nernst potential uses z = -1.

**Symporter sign.** The references use only J-/J+ = exp(dG_cyc/RT), dG_cyc = n RT ln(Na_N/Na_P) + RT ln(B_N/B_P) +
(n - 1) F V; J > 0 is a net import (a forward cycle). Rows `C6.v1_x_offset` are dG_cyc/RT. Compare in terms of
this relation, not of the engine's affinity sign.

## How each claim compares

- **C0:** `C0.E_*`, `C0.V_ghk_area` (primary) and `C0.V_ghk_unit` (the alternative reading, see README), the K and Cl- effect
  sign rows (`C0.k_effect_sign_*`, `C0.cl_effect_sign_*`; +1 depolarises) with the Cl- bound `C0.cl_bound_*`, the Cl_i threshold, and the feasibility flag of the
  published 19.4 mV.
- **C1:** `C1.zero_K`, `C1.zero_Cl` (the zero within the band), `C1.sign_I_*` (flux sign at E +/- 1 and 10 mV), the Kir
  route's zero, shape, slope and sqrt(K_o) ratio.
- **C2:** `C2.V_ghk_area` and the sign of dV/dt either side of the crossing.
- **C3:** `C3.tau_lin` (C/g), `C3.tau_fit` (the nonlinear fixed-amount step ODE at t = tau_lin: the centre of the 2 % band for
  an engine fit), `C3.ratio_t` (the decay curve); `C3.drift_amounts` says how far letting the amounts evolve moves the decay.
- **C4:** `C4.V_zero_glycine` (closed form), `C4.V_zero_kir` and `C4.V_zero_both` (roots), the shift and its sign, the monotone
  flags and the exact zero at availability 0. **Most Kir shifts are below the 1e-5 V band**: those rows have no power.
- **C5:** `C5.tau_common`, `C5.tau_diff` (closed forms for `sym` at |x1; the 2x2 eigenvalues otherwise), `C5.tau_fit_*`
  (nonlinear ODE), steady voltages, the large-g_J limit and the linear weighted average.
- **C6:** see the families `C6.*`: version 1 (Hill product, stall, offsets, equilibrium ratio, n = 1, capacity ratio) and
  version 2 (King-Altman J, J-/J+, stall, early-uptake ratio, a second consistent constant set).
- **C7:** `C7.relax_*` (a relaxation from V_0 = -0.04 V with the amounts evolving, pump off: the charge identities are
  compared; the decay and the amounts are `info`, since DESIGN gives no tolerance), the symporter's per-cycle energy partition and counts, and the pump's counts and energy partition. The
  pump's heat in J/mol is `info` (DESIGN.md does not say the standard state of delta_g0).
- **C8:** (a) paired differences local - bath; (b) the node's relaxation: `C8.b_*` (bare node and face) and `C8.bc_*` (the cell
  coupled through its passive membrane) are two labelled readings, the lead rules which the engine run is compared with;
  the end state is Donnan (`C8.b_final_*`), not the bath; the single-species and ambipolar times are `info`.

## Floors

`floor = G u (|q| + sum_j |q(x_j (1+u)) - q(x_j)|)`, G = 16, u = 2**-53, summed over every real input x_j of the row's
function; roots use the implicit-function form (README). ODE rows use G u |q|. The floor models a float64 evaluation of the same
formula; the tolerance covers time stepping.

## Plants

`plants` in the bands file: each plant's description, size, number of rows, `rows_ge_10_bands`, `smallest_margin_*`,
the `weak_rows` (margin between 1 and 10) and the `zero_power_rows` (margin below 1) with the reason. A margin is
|plant - reference| / band.

## After the erratum of 19 November 2026 (15:46 UTC)

- `*_unit` families and `C2.V_ghk_unit`, `C8.a_dV_ghk_unit` are `info`: the area-weighted `*_area` rows are compared.
- P1LB is compared on `C8.bc_*`; `C8.b_t_e`, `C8.b_c_t`, `C8.b_psi_t` are `info`.
- Charge identities (`C3.Q_over_CV_error`, `C7.relax_dQ`, `C7.relax_charge_identity`) have the band 1e-14 C.
- The pump uses the 1 M standard state: `C7.pump_dG_atp`, `C7.pump_heat`, `C7.pump_heat_nonneg` are compared.
- New rows: C6 equilibrium ratios at `Vrest_<exterior>` and `C6.v2_early_ratio_rest`.
- Per-row tolerance overrides are stored as `tol_abs` in the row's entry of the bands file.
