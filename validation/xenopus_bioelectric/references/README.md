# XC0's code-blind references (the Xenopus lane's first physical preparations)

Independent reference values for claims C0 to C8 of XC0 (`DESIGN.md` version 2 and `declared_inputs.json` of
19 November 2026, 13:35 UTC, in the workspace's `xenopus-lane-20261119/xc0/`), with bands, plants and a floor
model. Nothing here imports `cells`, any reference simulator or any third-party numerical library.

## Registration

**When.** Registered on 2026-11-19 at 15:44 UTC (`date -u` at this commit; a first commit of the same files, 16727134 at
15:16 UTC, lacked this line and the K-patch sign family), before any engine result exists. The branch is
`xenopus-xc0-references`, from main 9252236d. The generator was written and run under `/mnt/workspaces/Cells/venv-cpu/bin/python`;
`design --check` printed "regenerates identically" and `tests/unit/test_xenopus_xc0_references.py` passed (6 tests), both on this
commit's files.


**What was read:**
- `DESIGN.md` and `declared_inputs.json` (frozen 13:35 UTC), all of both.
- As structural examples only: the README and REFERENCES_USAGE of the membrane-trafficking package (FR-2's
  references; the same package), and the first 40 lines of its `design.py` (module docstring, imports, constants).
  For the core-seams package I listed its directory and read nothing.
- AGENTS.md and D225 to D228.

**What was never read:**
- Engine code (`src/cells/`), any test (the one test file here is my own), anything in `validation/` outside the
  reference packages.
- In the workspace: `expected_values_for_review.json`, `OWNER_ANSWERS.md`, `GAP_ANALYSIS.md`, `gaps.json`, `ledger/`,
  `lit/`, `commit/`.

One slip is on record: before the lead's ruling I issued a `cat` of an existing test file to copy its structure.
The permission check refused the whole command, so nothing was read; I stopped, reported it, and the lead
continued the task and said not to look at any existing test. I did not.

**Substitution.** The brief asks for mpmath; no venv has it (checked: venv-cpu, venv-gpu, venv-betse and the system
Python), and the one test file must pass under venv-cpu. Every reference uses the standard library's `decimal` at
60 digits, reported to 50, as FR-2's references did. No installation was made.

**Rulings by the lead** (19 November 2026, in the hand-off messages): continue, read nothing under `tests/`;
branch from main's head (9252236d); the stall formula is computed arithmetically and any mismatch is reported, not
corrected (DESIGN.md is frozen; the lead routes corrections as a dated erratum).

**Amendments** are made only by dated amendment, and each states whether it came before or after any engine output.
There is one, below (19 November 2026, after the design erratum, before any engine output).

## What is in this directory

| File | What it is |
| --- | --- |
| `reference_inputs.json` | byte copy of the frozen `declared_inputs.json` (the `--check` cannot read the workspace) |
| `exact.py`, `model.py`, `claims_membrane.py`, `claims_c5.py`, `symporter.py`, `local_node.py`, `rows.py`, `plants.py`, `design.py` | the generator |
| `designs/xc0_reference_values.json` | every reference, 50-digit strings, by family and key |
| `designs/xc0_interface_bands.json` | band rule, floors, bands, plants, zero-power list |
| `REFERENCES_USAGE.md` | the interface the engine side may read |

**Published numbers** appear only as bare numbers with their citation, as DESIGN.md gives them (D227): the Xrel3 shift of
about -11 mV, the GlyR F99A hyperpolarisation of 19.4 mV and the butyrate ratio 253 against 175 micrograms per 60 embryos
(1.45) are from Chernet and Levin 2013 (Dis Model Mech 6(3), PMC3634644); n = 2 for the symporter rests on the abstract of
Coady et al. 2007 (PMC1965447); the cytosolic ion set on the abstract of Gillespie 1983 (J Physiol 344); the leak
permeabilities on the original abstract of Costa et al. 1989. No figure, table, text or supplement is reproduced.

## Method

Inputs are read as the exact values of their doubles (F, R, areas, capacitances, permeabilities), except the
diagram's rate constants and electric distances, read as decimal values (0.2, not the nearest double) so that the
declared detailed-balance product (2.16e25) and the charge sum (1.0) are exact. Concentrations are the declared mM
values. V = inside - outside; currents are outward positive.

**Closed forms** (50 digits): Nernst with an explicit valence (z = -1 for Cl); the GHK zero-current voltage; the GHK
current and its analytic slope; the Kir route's current and slope (DESIGN 3.2); the symporter's saturation, stall,
equilibrium ratio, n = 1 limit, capacity factor and energy partition; the face's time constants; the Donnan end state.
**Roots** (Kir zero, steady voltages): a sign scan, bisection, then Newton checked to stay in its bracket, with the
float64 floor through the implicit function. The two-cell steady state is solved by Newton in 2D and
cross-checked by a nested one-dimensional root.
**ODEs** (C3 step, C5 two-cell, C7 relaxation, C8b): classical RK4 at N and 2N fixed steps; the reported value is the
Richardson extrapolation and its error estimate |y_2N - y_N|/15 is recorded (`internal_checks`; at most about 1.3e-9
of the step, far below every band). **King-Altman** (version 2): the spanning-tree sums of the eight-state ring,
cross-checked at every state against a Gaussian solve of the master equation (agreement 1e-45).

**The symporter uses only J-/J+ = exp(dG_cyc/RT)**, dG_cyc = n RT ln(a_Na,N/a_Na,P) + RT ln(a_B,N/a_B,P) +
(n - 1) F V. A forward cycle is favourable when dG_cyc < 0. The stall -(RT/((n-1)F)) [n ln(Na_in/Na_out) + ln(B_in/B_out)]
is the zero of that dG_cyc; I verified it at 50 digits by dG_cyc = 0 at every stall state, and the version-2 King-Altman
root agrees with it to 1e-30.

## Registered states

- **State key** `ionset|exterior|T<K>`: three ion sets (primary, `bracket_Cl_high`, `bracket_second_hand_table`) times six
  exteriors (0.1x MMR bath; the local node; the 70 mM Cl- bath as a sodium salt; the same with an inert cation, where
  Na_out stays 9.9 mM; the bath with Cl 10.0 and 11.1 mM) times two temperatures (291.15 K and the bracket's 287.15 K):
  36 states for C0, C1, C2, C4 and C8a.
- C3 (nine scenarios, listed in the family notes), C5 (seven scenarios times four junction multiples), C6, C7 and C8b run
  explicit scenario keys at 291.15 K, with the 287.15 K bracket in C3 (S9) and in C6's stall table for n = 2.
- Grids: P_GlyR 1e-9, 3e-9, 1e-8, 3e-8 m/s; g_ref 0.1, 0.3, 1, 3 S/m2; availability 0, 0.25, 0.5, 0.75, 1 (rows at
  0.25, 0.5 and 1; the five levels feed the monotone flags).

## The band rule and the floor models (registered once, applied to every row)

**Band rule**

    band = max( tol_abs + tol_rel * |reference| , FLOOR_FACTOR * floor ),   FLOOR_FACTOR = 10

- `tol_abs`, `tol_rel` come from DESIGN.md's tolerance for the claim (1e-6 V on E and V_GHK in C1 and C2; 1e-5 V in C4;
  2 % on tau in C3; 3 % on tau and 0.1 mV on voltages in C5; 0.01 mV on the stall and 1e-6 relative on ratios in C6;
  5 % on the time constant in C8b).
- Where DESIGN.md gives none, the family's `tol_source` says `borrowed` (the same quantity's tolerance elsewhere) or
  `proposed` (mine, open to the lead's ruling). Examples: C0 has none (borrowed from C1's 1e-6 V), C7's energy
  partition and C3's currents (proposed 1e-6 relative), the node's concentrations (5 %).
- `sign` rows are compared only when |aux| exceeds the band: a sign decided by less than the band has no power.

**Floor model `input_perturbation_float64`** (before any comparison): a float64 engine holds every real input to a
relative rounding u = 2^-53 and rounds each of at most about 16 operations. For a row q = q(x_1, ..., x_m):

    floor = G u ( |q| + sum_j | q(x_j (1+u)) - q(x_j) | ),    G = 16

summed over every real input (T, R, F, concentrations, permeabilities, areas, ...). For a root V* of I(V; x) = 0:

    floor = G u ( |V*| + sum_j | I(V*; x_j (1+u)) - I(V*) | / |dI/dV| )

Rows without a sensitivity analysis (ODE outputs, one-rounding closed forms) take G u |q| by default; C5's steady voltages and the large-g_J limit take the larger of the two cells' root floors. Rows that are zero by an identity
(J at the stall, I at E_K) take the floor of the argument's rounding (G u times the sum of the terms that cancel). The
floor is a statement about float64 evaluation of the same formula; it is not an estimate of the engine's time-stepping
error, which the tolerance covers.

## Findings the lead should see first (none changes DESIGN.md; they are reported)

**1. The zero-current voltage depends on a reading that DESIGN.md states two ways.** DESIGN C2 weights the
permeabilities "by the patches' area fractions", and the declared patches put K on 20 %, and Na and Cl on 60 %, of the
area. That gives V_GHK = -47.09 mV in 0.1x MMR and -6.33 mV in the
local node (primary ion set). DESIGN's quoted -70.5 mV and -26.7 mV (in C0, C8a and the sign-problem text) are
reproduced only when each leak permeability is used as a whole-membrane value without area weights
(-70.52 and -26.74 mV). I registered the **area-weighted value as primary**
(`*_area`: what the declared patches give, and what an engine reading the declared inputs will compute) and the
**unweighted value as a labelled alternative reading** (`*_unit`), not a plant. The lead ruled (erratum item 1): **area-weighted is primary**; the unweighted rows are `info`, not compared.
Everything in DESIGN.md that leans on -70.5 mV is recomputed under both readings below.

**2. C0's sign conclusion changes with the reading, and in one bath it reverses.**

| Exterior (primary ion set, 291.15 K) | E_Cl (mV) | V_rest area-weighted (mV) | open Cl- patch | V_rest unweighted (mV) | open Cl- patch |
| --- | --- | --- | --- | --- | --- |
| 0.1x MMR bath | 27.31 | -47.09 | depolarises | -70.52 | depolarises |
| local node | -16.97 | -6.33 | hyperpolarises (bound 10.64 mV) | -26.74 | depolarises |
| 70 mM Cl-, sodium salt | -21.26 | -13.91 | hyperpolarises (bound 7.35 mV) | -35.84 | depolarises |
| 70 mM Cl-, inert cation | -21.26 | -50.32 | depolarises | -71.81 | depolarises |
| 70 mM Cl-, sodium salt, Cl_i 60 mM | -3.87 | -11.40 | depolarises | -33.35 | depolarises |

- An open K patch hyperpolarises in all 36 states under both readings (E_K is -78 mV or lower; `C0.k_effect_sign_*` are all -1).
- In 0.1x MMR E_Cl is +27.3 mV, above V_rest under both readings: an open Cl- patch depolarises.
- In the 70 mM Cl- bath as a sodium salt, **the area-weighted reading gives hyperpolarisation**: E_Cl -21.3 mV is below
  V_rest -13.9 mV (Na_out 69.8 mM raises V_rest). DESIGN's "an open Cl- patch therefore depolarises this cell" compares
  E_Cl at 70 mM with the 0.1x MMR rest voltage. With the inert cation (Na_out 9.9 mM) V_rest is -50.3 mV and the patch
  depolarises. So T2's sign is available only in the sodium-salt option, and only under the area-weighted reading.
- **The published 19.4 mV is infeasible in all 36 states under both readings** (`C0.feasible_19p4_*` all false). The largest
  bound where the sign is hyperpolarising is 15.77 mV (area-weighted, bracket_second_hand_table|local|T291.15; 8 states) and 0.34 mV (unweighted, bracket_second_hand_table|local|T291.15; 2 states).
- The stall sentence holds: the cell at V_rest (-47.09 mV, or -70.5 mV) is more negative than V_stall, so the
  cycle imports under both readings.

**3. The stall voltage is -37.73 mV by the formula,** as DESIGN says (n = 2, Na_in 21, Na_out 9.9 mM, B_in/B_out = 1:
`n2|Nain21|Naout9.9|BP0.1|rB1|T291.15`, -37.7338 mV); the version-2 King-Altman zero agrees to 1e-30 V.

**4. The Kir route is nearly shut at every registered state.** At the bath's V_rest the cell sits about 106 mV above E_K
(-153 mV), where q(u) with V_h = +10 mV and s = 10 mV is about e^-9.6. The largest shift of V_zero anywhere on the declared grid
(g_ref 3 S/m2, availability 1) is 0.73 mV (in the local node). **T1's -11 mV is unreachable in 36 of 36 states** (`C4.T1_reachable`).
Only 69 of 432 Kir shift rows exceed the 1e-5 V band, and cell-to-cell Kir asymmetry in C5 is about 0.3 microvolt against its
0.1 mV band. That is a result about the declared V_h, s and ion sets, not a defect of the references. The supplementary C5x
scenarios (Cl- patch open in cell 2) are registered so that C5's steady-state rows have power.

**5. Time constants.** tau = C_total/g = 0.196106 s (C_total 78.54 pF, g 0.4005 nS) for the leak-only cell. The
nonlinear step ODE gives 0.194651 s for +2 mV and 0.197575 s for -2 mV, 0.74 % from C/g: both are registered (`C3.tau_lin`, `C3.tau_fit`)
so that nonlinearity does not silently use the 2 % band. Letting the amounts evolve moves the decay by at most 2e-4 of the step over four tau. C5's
tau_diff for the declared junction (g_J 5.42 nS) is 6.98 ms, 28 times shorter than tau_common; the engine step is 0.1 ms.

**6. C8b.** The node's end state is a **Donnan state, not the bath**: A (36 mM, D_A = 0) is trapped, so Na 37.875, K 0.7651,
Cl 2.6400 mM and a node potential of -33.66 mV against the bath (`C8.b_final_is_bath` is false; the log-mean flux has the exact
Donnan zero). DESIGN's "about 8 s for Na" is Na alone without a field (7.52 s, `info`); the declared mixture's 1/e times are 4.94 s (Na), 4.55 s (K),
4.92 s (Cl) for the bare node and face, and 4.79 s for K with the cell coupled through its passive membrane (5.2 % from the bare value, beyond the 5 % band). P1LB has a cell, so both are
registered; **the lead ruled (erratum item 2) that P1LB is compared on the cell-coupled `C8.bc_*` rows**; the bare `C8.b_t_e`, `C8.b_c_t`, `C8.b_psi_t` are `info`. A constant-field flux in place of the log-mean one moves the times by up to 3 % (`info`).
The node's quasi-neutrality (zero net face current) is my assumption about the node's potential.

**7. Charge identities (resolved by erratum item 3):** C_total x 100 mV is 7.9e-12 C, so DESIGN's 1e-9 C had no power. The erratum sets 1e-14 C for C3's Q = C V and C7's ionic
charge against the integrated current; the registered bands now use it (`C3.Q_over_CV_error`, `C7.relax_dQ`, `C7.relax_charge_identity`) and the plant `charge_on_main_patch_capacitance_only` is seen at them.
C5's junction charge sum stays at 1e-9 C (the erratum does not name it) and is zero power.

**8. The pump's heat** (resolved by erratum item 4): 1 M standard state, dG_ATP = delta_g0 + RT[ln c_ADP + ln c_Pi - ln c_ATP - ln 1000 mM]; `C7.pump_dG_atp`, `C7.pump_heat` and `C7.pump_heat_nonneg` are compared rows. The mM reading is a plant (`pump_standard_state_mM`).

**9. T3 inverse check** (`info`): the voltage difference for a ratio 1.45 is 9.322 mV (n = 2, 291.15 K; 9.248 mV from 253/175), and 19.4 mV gives a ratio of
2.1668 (DESIGN: 2.17). Version 2's early-uptake ratio J(-0.0899 V)/J(-0.0705 V) at B_in = 0 lies between 1.466 and 1.885 across the nine states; version 1's is exactly 1.

**10. The supplementary scenario family `C5x`** is accepted (erratum). **Kir:** the erratum records that no Kir-dependent claim can be scored until V_h, s and the conductance are sourced.

## Plants

29 plants, 4671 plant rows. A margin is |plant - reference| / band. Three plants have weak rows (margin 1 to 10): `kir_route_inert` (smallest 1.06; the route is shut at these states), `temperature_298` (1.41; stall rows near zero) and `face_area_10pct_large` (1.82; a 9 % error against the 5 % band). Every other plant's smallest margin is 13.3 or more.

| Plant | What is wrong | Size | Rows | Rows >= 10 bands | Smallest margin (rows expected to show it) | Weak (1-10) | Zero power (<1) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `availability_ignored` | the Cl- patch and Kir route at availability 1 whenever they exist (a = 0 and 0.5 not applied) | a = 0 -> 1; a = 0.5 -> 1 | 252 | 252 | 28.9 | 0 | 0 |
| `bath_Cl_11p1_for_10p1` | bath Cl 11.1 mM in place of 10.1 mM (the 2016 table value) | E_Cl shifts by -2.4 mV; V_GHK by about -0.3 mV | 18 | 18 | 56.5 | 0 | 0 |
| `capacitance_full_on_each_patch` | every patch given the full capacitance (the split missing) | tau x 4 (+300 %) | 54 | 54 | 100 | 0 | 0 |
| `capacitance_main_patch_only` | tau from the main patch's 60 % of the capacitance only | tau x 0.6 (-40 %) | 54 | 54 | 13.3 | 0 | 0 |
| `charge_on_main_patch_capacitance_only` | Q = C_main V (60 % of the capacitance) in the charge identities | Q - C_total V = -0.4 C_total V (1e-13 to 1e-12 C) | 216 | 214 | 5.09 | 2 | 0 |
| `diagram_charge_sum_0p9` | electric distances summing to 0.9 (e8 q = -0.1) in place of 1.0 | J-/J+ x exp(-0.1 psi) | 162 | 135 | 1.47e+05 | 0 | 27 |
| `diagram_detailed_balance_broken` | one backward constant (e1) 10 % too large: the loop product no longer balances | J-/J+ x 1.1 | 162 | 162 | 1e+05 | 0 | 0 |
| `face_area_10pct_large` | face area 1.1e-10 m2 in place of 1e-10 m2 | every t_1/e x 0.909 (-9 %) | 3 | 0 | 1.82 | 3 | 0 |
| `face_length_doubled` | face length 2e-4 m in place of 1e-4 m | every t_1/e x 2 | 3 | 3 | 20 | 0 | 0 |
| `junction_absent` | no junction in the difference mode | tau_diff changes by a factor (g+2gJ)/(g+2 f gJ) | 7 | 7 | 133 | 0 | 0 |
| `junction_conductance_x0.5` | g_J halved | tau_diff changes by a factor (g+2gJ)/(g+2 f gJ) | 7 | 7 | 24.9 | 0 | 0 |
| `junction_conductance_x2` | g_J doubled (counted from both ends) | tau_diff changes by a factor (g+2gJ)/(g+2 f gJ) | 7 | 7 | 15.5 | 0 | 0 |
| `kir_current_sign_flipped` | Kir route current with the wrong sign (inward positive) | I -> -I (2|I|) | 180 | 180 | 2e+06 | 0 | 0 |
| `kir_rectifies_on_absolute_V` | u = V instead of V - E_K in the Kir law | I(E_K) no longer zero | 216 | 216 | 1.27e+06 | 0 | 0 |
| `kir_route_inert` | the Kir route acts as if its availability were 0 (route off) | shift of V_zero by the route (microvolts; the route is rectified shut at these states) | 468 | 22 | 1.06 | 53 | 393 |
| `kir_without_sqrt_Ko` | Kir current without the sqrt(K_o/K_ref) factor | current x sqrt(K_ref/K_o): x5.0 (bath), x1.1 (local) | 186 | 186 | 1.18e+05 | 0 | 0 |
| `local_final_state_is_bath` | the node's end state taken as the bath (the trapped A ignored) | Na 37.9 -> 9.9 mM and so on | 4 | 4 | 7.39e+05 | 0 | 0 |
| `local_values_replaced_by_bath` | the local compartment's membranes silently take the bath's values | E_K -78.1 -> -153.3 mV; V_GHK shifts by tens of mV | 24 | 24 | 3.29e+04 | 0 | 0 |
| `n3_for_n2` | n_Na = 3 where the declared value is 2 (stall, equilibrium ratio, J offsets) | stall shifts by about -37 to -190 mV | 923 | 923 | 66.6 | 0 | 0 |
| `nernst_sign_flipped` | E = -(RT/zF) ln(c_out/c_in) for K, Na and Cl | 2|E| for each ion (22-306 mV) | 108 | 108 | 832 | 0 | 0 |
| `pump_2Na_3K` | pump moves 2 Na out and 3 K in | counts differ by 1 | 4 | 2 | 1e+09 | 0 | 2 |
| `pump_3Na_3K_neutral` | pump moves 3 Na out and 3 K in (electroneutral) | counts differ by 1 | 4 | 3 | 1e+09 | 0 | 1 |
| `pump_standard_state_mM` | the pump's ATP hydrolysis free energy with the log argument in mM (no 1 M factor) | dG_ATP shifted by RT ln 1000 = 16.7 kJ/mol | 8 | 8 | 2.54e+05 | 0 | 0 |
| `symporter_charge_n_not_n_minus_1` | the electrical term n F V in dG_cyc where (n - 1) F V is declared | stall x (n-1)/n = x 0.5 (n = 2) | 203 | 195 | 123 | 0 | 8 |
| `symporter_heat_sign` | heat booked as +dG_cyc per cycle (negative for a favourable cycle) | sign of the heat reversed | 480 | 480 | 2e+06 | 0 | 0 |
| `symporter_voltage_sign_flipped` | V -> -V in dG_cyc (the wrong inside/outside convention) | stall -> -stall; equilibrium ratio exponent flips | 492 | 425 | 117 | 0 | 67 |
| `temperature_298` | T = 298.15 K in place of 291.15 K | RT/F x 1.024 | 312 | 292 | 1.41 | 20 | 0 |
| `valence_swap_Cl` | Cl- treated as a cation (z = +1) in the Nernst term and the GHK sum | E_Cl sign flips: 2|E_Cl| (about 40-120 mV) | 108 | 108 | 112 | 0 | 0 |
| `vito_c_factor_on_forward_rate_only` | capacity factor f multiplies J+ but not J- | J(f)/J(1) = (f - e^x)/(1 - e^x) in place of f | 6 | 3 | 2.33e+05 | 0 | 3 |

## Zero power (what these references cannot see)

- **Charge identity rows** (`C3.Q_over_CV_error`, `C7.relax_dQ`, `C7.relax_charge_identity`, `C5.junction_charge_sum`): zero power at DESIGN's 1e-9 C (finding 7).
- **Kir availability effects** on V_zero (`C4.V_zero_kir`, `C4.shift_kir`, C5's Kir asymmetry): below the band at most states (finding 4); the `kir_route_inert` plant clears 10 bands in 22 rows, is weak (1 to 10 bands) in 53 and is unseen in 393.
- **Sign rows with |aux| below the band** are not compared; the family says which quantity decides the sign.
- **C7 trajectories** (`C7.relax_ratio_t`, `C7.relax_dn`) are `info`: DESIGN gives no tolerance and C7 is identities over records. `C3.ratio_t` is banded: DESIGN's 2 % on tau carried to the decay (tol_abs = 0.02 (t/tau) ratio).
- **Pump rates and heat:** `nak_atp_mass_action_positive@1`'s rate is not given by DESIGN.md, so only the stoichiometry and the energy partition per cycle are referenced.
- **The plants below the full margin, by plant:**
- `charge_on_main_patch_capacitance_only` at `C7.relax_dQ` (2 rows) is weak: margin between 1 and 10 bands
- `diagram_charge_sum_0p9` at `C6.v2_ratio_Jm_Jp` (27 rows): V = 0: the charge-sum error multiplies exp(0 x psi)
- `face_area_10pct_large` at `C8.bc_t_e` (3 rows) is weak: margin between 1 and 10 bands
- `kir_route_inert` at `C4.V_zero_both` (30 rows): the Cl- patch dominates; the route adds microvolts; the route shifts V_zero by less than the 1e-5 V band at these states
- `kir_route_inert` at `C4.V_zero_kir` (363 rows): the Cl- patch dominates; the route adds microvolts; the route shifts V_zero by less than the 1e-5 V band at these states
- `kir_route_inert` at `C4.V_zero_both` (2 rows) is weak: margin between 1 and 10 bands
- `kir_route_inert` at `C4.V_zero_kir` (51 rows) is weak: margin between 1 and 10 bands
- `pump_2Na_3K` at `C7.pump_cell_charge_per_fmol` (1 rows): the same charge per cycle; this count is the same as the declared one
- `pump_2Na_3K` at `C7.pump_cycle_counts` (1 rows): the same charge per cycle; this count is the same as the declared one
- `pump_3Na_3K_neutral` at `C7.pump_cycle_counts` (1 rows): this count is the same as the declared one
- `symporter_charge_n_not_n_minus_1` at `C6.v1_eq_ratio` (8 rows): V = 0: the electrical term vanishes
- `symporter_voltage_sign_flipped` at `C6.v1_eq_ratio` (67 rows): V = 0 or n = 1: no electrical term
- `temperature_298` at `C6.v1_V_stall` (20 rows) is weak: margin between 1 and 10 bands
- `vito_c_factor_on_forward_rate_only` at `C6.v1_capacity_ratio` (3 rows): x << 0: J- is negligible against J+, so f on J+ only equals f on both

## Amendment, 19 November 2026 (after DESIGN's erratum of 15:46 UTC)

Applied before any engine result exists, as one dated commit on top of 676f9545. The lead's rulings: (1) area-weighted zero-current
voltage primary, unweighted rows `info` (`C0.*_unit`, `C2.V_ghk_unit`, `C8.a_dV_ghk_unit`); (2) P1LB compared on `C8.bc_*`, the bare
node and face `info`; (3) charge-identity tolerance 1e-14 C; (4) pump standard state 1 M, heat rows compared; (5) C5x accepted. Also added:
the C6 equilibrium ratios at the corrected rest voltage (`...|Vrest_<exterior>`; for n = 2, Na_out 9.9 mM it is 1.45) and
`C6.v2_early_ratio_rest`. No reference value changed; the changes are in kinds and bands (see the commit message for counts).

## Regenerating

    python -m validation.xenopus_bioelectric.references.design            # write
    python -m validation.xenopus_bioelectric.references.design --check    # regenerate, compare byte for byte

Environment: `/mnt/workspaces/Cells/venv-cpu/bin/python` with `PYTHONPATH` at the checkout. The write takes
about 5 minutes on one loaded core. Two test files (D224): `tests/unit/test_xenopus_xc0_references.py` is the fast integrity check (about 9 s: the files parse and agree,
the band rule is recomputed from the stored references and floors, the plant margins are recomputed from the stored rows, a small subset is regenerated);
`tests/unit/test_xenopus_xc0_references_regenerate.py` is the full regeneration (about 5 minutes, for tier 3).
