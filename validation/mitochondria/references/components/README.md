# MT-1 component references: the mitochondrial laws

**Status: prepared for registration; the lead's tag registers it.**
- **Source:** written against `docs/MITOCHONDRIA_LAWS_APPENDIX.md` at tag
  `mito-laws-appendix-2026-11-20b` (commit c9c5be1f), the appendix the user ruled on (D236).
- **Registration:** the lead tags this branch's head as the registration.
- **Signature:** if the engine's kernel signature differs from the appendix's "Reads", the rows
  mapped onto it are added before the tag, never after.
- Integration grants no scientific acceptance.

These are independent, high-precision references for each law of the appendix. MT-1 judges the
engine's law kernels against them. No such kernel existed when they were written.

## Independence

- **Read:**
  - the appendix at `mito-laws-appendix-2026-11-20b`. The proposal before it was written from the
    first tag, `mito-laws-appendix-2026-11-20`;
  - D193 to D196, D209 and D210, D227 and D228, and D234 in `docs/DECISIONS.md`, with the
    headings of D230 to D233 from a search;
  - `AGENTS.md`;
  - FR-7's layout, as a pattern only: `validation/fr7/__init__.py`,
    `validation/fr7/references/__init__.py`, the first 80 lines of its `REFERENCES_USAGE.md`, the
    head of its `rows.json` and its merge commit's message;
  - `scripts/test_tiers.py`'s `measure` command, to time the test;
  - file names under `validation/` and `tests/`, as listings only.
- **Not read:**
  - `src/` or `lean/`;
  - any test except this folder's own;
  - any file on the `mito-lane` branch (`appendix_check.py` and `beard2005_cardiac.py`
    included);
  - MR1's whole-organelle reference (`validation/mitochondria/references/*.py` and its JSON, on
    any branch);
  - the Beard papers, which no question needed.
- **Imports:** the standard library only (`decimal`, `json`, `math`, `itertools`). Nothing
  imports `cells`; the fast test checks this in a fresh process.

## Conventions

**Approved by the lead (20 November):**
1. **No evaluation domain.** The appendix declares none.
   - Each law's x range is reported.
   - Rows with x < −80 are kept, and J⁻/J⁺ = e^x is checked there.
   - Nothing is refused or clipped.
2. **Parameters:** the "With Pi control" column applies throughout. The Eq. 7 rows use the
   "Without" column's X_C3 = 0.14483. Each law's column is in `inputs.json`.
3. **The input signature:**
   - Each law's "Reads" line, taken literally, lists its independent inputs.
   - The slopes of S are partial derivatives at fixed other inputs: d ln S/d ln c, d ln S/d ln h
     and d ln S/du, with u = FΔψ/RT.
   - The slopes of x are with respect to the base-form species: exactly ν_s and q.
   - The J slopes are dJ/d ln c = J d ln S/d ln c − J⁻ ν_c, or A s_A − B s_B for a two-term form.
4. **The binding closure:**
   - d ln[form]/d ln[total] = 1 at fixed free ligand.
   - Each form's dependence on the free ligand (Mg²⁺ or H⁺) at fixed total.
   - Given at every row that reads a bound form, so a kernel that reads totals can be compared
     exactly. Checked against central differences (`checks.json → binding_chain`).

The first proposal's convention for the supply's work, W = J (ΔG°_DH + …), is superseded. The
supply is now balanced on its held pair (§6).

**Readings of the tag** (the lead accepted each as a reading, not a declaration):
- **No potential across the outer membrane:** ΔG_f = RT ln([f]_P/[f]_e), matching §8's Fick flux
  and Beard's Eq. 13.
- **The external side uses pH_P's range, 6.5–7.6.** Mg²⁺ and the adenylates vary at each end, so
  the total-in-place-of-forms plant has power.
- **The held pair:** S_ox = 1 mM and S_red = 10^−0.10 r · S_ox, both listed as inputs. Only their
  ratio enters the flux.
- **The kinase's approach to equilibrium:** its near-equilibrium states move AMP²⁻ and ATP⁴⁻
  together, with binding kept.
- **The outer membrane's corners:** they vary Mg²⁺, pH and ATP/ADP at both ends, with AMP and Pi
  held at base. The interior points vary those too.
- **The labels:** "adenylate_kinase (section 7)" and "outer_membrane (section 8)", since the tag
  names neither law.
- **Complex IV's range:** §10's ranges reach x = −118.7 RT, against §1.3's "about −94 RT". The
  corner is: cytochrome c 99% reduced, O₂ 0.3 mM, pH_N 6.8, pH_P 7.6 and Δψ 0. The grid is
  unchanged; the lead passes §1.3's note to the lane.

**Definitions and displays:**
- **Definitions:**
  - T = 298.15 K, with R = N_A k_B and F = N_A e exact;
  - each ΔG° at 1 M derived exactly from Table 2's pH-7 value, or from §2's and §7's matched
    formulas;
  - K_base from §7's match at full precision: m = 3.80855352888 mM, the root of the quadratic.
- **Displays:** the appendix's rounded entries, constants and K_base. Kernels built on them are
  planted below, with their sizes.
- **§9's potentials and §10's M** are computed exactly from the convention's order. All nine
  potentials, at 9 decimals, and all ten M values, at 3 decimals, reproduce the tag's tables
  (`appendix_numbers`).

**The parameter transcription** (`hp.py`) was compared with tag b's `<!-- parameters -->` table:
29 rows, both columns, no mismatch. θ_P, θ_N, T, the kinase's buffer and the supply's
reference pH match its text.

## The registered forms (D236, frame B)

| Law | Registered form | Unregistered forms (stall rows kept, labelled; plants) |
| --- | --- | --- |
| §1.2 Eq. 24 | `restored`, φ_Pi × Eq. 7 | printed; the first tag's `balanced` |
| §2 Eq. 11 | `balanced` (keeps the printed forward term) | printed; `proton_restored`; `base_form_restored` |
| §4 Eq. 16 | `balanced` (keeps the printed forward term) | printed; `subscripts_swapped` |
| §6 Eq. 1 | `balanced` on the held pair | printed |
| §7 Eq. 18 | `balanced` in base forms, with the source's rate | printed (on totals) |

- `design.REGISTERED_FORMS` holds the choice.
- Each unchosen form keeps its stall rows as states, labelled `"registered": false`. It runs as a
  plant against the registered form: `*_as_<form>`.
- §1.4's lumped cycle is not used in MT-1 or MT-2 (host P, D235). Its x-only rows stay, marked
  `"used_in_MT1_MT2": false`.

## The laws

| Key | Law (section) | q | ΔG° at 1 M, J/mol (RT) | κ | M (§10) | States |
| --- | --- | --- | --- | --- | --- | --- |
| `complex_I` | redox_driven_proton_cycle@1 (1.1) | +4 | −109326.067 (−44.10163) | 1 | 259.334 | 61 |
| `complex_III_eq7` | redox_driven_proton_cycle@1 (1.2, Eq. 7) | +2 | +47382.133 (+19.11374) | 1/2 | 227.439 | 61 |
| `complex_III_eq24` | redox_driven_proton_cycle@1 (1.2, restored) | +2 | +47382.133 (+19.11374) | 1/2 | 227.439 | 97 |
| `complex_IV` | redox_driven_proton_cycle@1 (1.3), per O₂ | +8 | −405704.266 (−163.65922) | 1/4 | 308.722 | 61 |
| `lumped_QO` | redox_driven_proton_cycle@1 (1.4), x only, unused | +12 | −310940 (−125.43175) | — | 325.757 | 61 |
| `atp_synthase` | proton_coupled_atp_synthesis_cycle@1 (2) | −3 | −5032.131 (−2.02994) | 1 | 57.292 | 99 |
| `nucleotide_exchange` | electrogenic_nucleotide_exchange@1 (3) | −1 | 0 | 1 | 31.691 | 61 |
| `phosphate_carrier` | phosphate_proton_symport@1 (4) | 0 | 0 | 1 | 41.447 | 49 |
| `k_h_exchange` | potassium_proton_exchange@1 (5) | 0 | 0 | 1 | 27.631 | 45 |
| `nadh_supply` | held_reductant_supply@1 (6) | 0 | +39956.067 (+16.11810) | 1 | 232.056 | 41 |
| `adenylate_kinase` | adenylate kinase (7), per 2 ADP | 0 | +2340.798 (+0.94427) | 1 | 32.635 | 41 |
| `outer_membrane` | outer_membrane (8), per form | — | 0 | 1 | per form, 13.8 to 44.9 | 93 |

That is 770 states, with one row each, in the registered form.

**The new components:**
- **The supply (§6):**
  - S_red(N) + NAD(N) → S_ox(N) + NADH(N) + H⁺(N), with ΔG°_S = 0 at pH 7.
  - The held ratio S_red/S_ox = 10^−0.10 r puts its equilibrium at [NADH]/[NAD] = r at pH_N 7.10.
  - Balanced: J = X_DH φ_DH (r [NAD] − [NADH] h_N/10^−7.10), with S = X_DH φ_DH r [NAD].
  - Its energy (the lead's request) is the upkeep row `upkeep_work_W_per_L`,
    −J (μ̃_S_ox − μ̃_S_red), from §9's potentials. It is checked to equal the heat −J ΔG plus the
    work delivered to the NAD pool, J (μ̃_NADH + μ̃_H − μ̃_NAD).
- **The kinase (§7):**
  - 2 ADP³⁻ → ATP⁴⁻ + AMP²⁻, at P.
  - J = X_AK (1 + [Mg²⁺]_P/K_MgATP)(K_base [ADP³⁻]² − [AMP²⁻][ATP⁴⁻]). It equals the source's
    form on totals with K_tot, and K_tot = K_AK at the matched m.
- **The outer membrane (§8):**
  - For each of ATP⁴⁻, MgATP²⁻, ADP³⁻, MgADP⁻, AMP²⁻ (p_A) and HPO₄²⁻, H₂PO₄⁻ (p_Pi):
    J_f = γ p ([f]_e − [f]_P), with γ p_A = 509.15 s⁻¹ and γ p_Pi = 1958.73 s⁻¹.
  - Rows give each form's J, S, J⁻, x, ΔG, dissipation and slopes.
  - They also give each class's sum, Eq. 13 on totals (equal to the sum), and the Mg²⁺ and H⁺
    carried by the bound forms.

## Files

| Path | What it is |
| --- | --- |
| `interface/inputs.json` | Constants at 298.15 K, parameters, potentials, the kinase's match, readings, registered forms, the band rule, each law's legs, q, ΔG°, M, Reads and forms, and every state as float64 inputs. A kernel under test reads only this file |
| `interface/rows.json` | Per law, per state, in the registered form: the reference values at 20 significant digits, their bands, flags and binding sensitivities |
| `interface/plants.json` | Per plant: its rows caught, its power on J alone, margins, per-quantity power and zero-power rows |
| `interface/checks.json` | The physics checks of every form (registered or not), the tag's numbers, the failing forms' violations, the float64 calibration and the references' own precision |
| `hp.py` | Backends, constants, parameters, the kinase's match, §9's potentials and §10's M |
| `laws.py` | The laws and their forms, computed along separate paths that the checks compare |
| `states.py` | The §10 grid, interior points, the external side and the binding closure |
| `checks.py` | The checks of the physics |
| `plants.py` | The plants |
| `design.py` | Writes `interface/` in about 85 s on one core. `--check` regenerates and compares |

**The paths in `laws.py`, compared by the checks:**
1. x from the turnover's table;
2. each form's terms, transcribed literally;
3. ΔG as each section writes it;
4. the stated closed forms of S and of the balanced backward term;
5. hand-derived slopes, against central differences.

## Rows

**States.** Each law has:
- its center (the base state);
- the 2^k corners of §10's ranges over the inputs it reads;
- six interior points (a Halton sequence), with pool totals varied;
- 22 states next to equilibrium: x = 0, ±10⁻⁶, ±10⁻³, ±0.1, ±1 and ±3 at two bases.
  - Base A: pH_N 7.4, pH_P 7.1.
  - Base B: pH_N 6.8, pH_P 7.0.
  - A charged law moves by Δψ.
  - A neutral law splits the move between its two sides.
  - The supply moves [NADH]/[NAD] at a fixed pool.
  - The kinase moves AMP and ATP⁴⁻.
  - The outer membrane sets the IMS side to the external side times e^x, with the same Mg²⁺ and
    pH, so every form has that x.
- **The failing laws also have:**
  - stall rows, at each two-term form's zero (x = −d);
  - two coincidence rows, where every form agrees in value: pH_N 7.0 for Eqs. 11 and 24, h_N = h_P
    for Eq. 16, pH_N 7.10 for the supply, and the matched m for the kinase.

**Inputs** are float64 values. Each reference is evaluated at those doubles' exact values.
- **Forms and totals:** each form in a row is rounded separately, so the forms agree with their
  totals to about one ulp.
- **§10's box:** the states next to equilibrium may leave it. Δψ reaches about 270 mV for
  complex IV.

**Quantities:**
- **For the cycle laws:**
  - x, ΔG and affinity;
  - S (= J⁺), J⁻ and J;
  - `A_term` and `B_term`;
  - q F J and its Δψ slope;
  - −J ΔG;
  - the static head (q ≠ 0);
  - the slopes of ln S and of J.
- **For the supply:** also `upkeep_work_W_per_L`.
- **For the outer membrane, per form:** J, S, J⁻, x, ΔG, −J ΔG and the slopes, plus `class_J`,
  `eq13_J`, `ligand_J` (Mg²⁺ and H⁺ carried) and `dissipation_total`.

**Flags:**
- `sign_not_judged`, per form for the outer membrane: |J| within its band;
- `x_below_minus_80`.

## Bands

band = 16 · eps64 · scale + 10⁻¹⁹ · |value|, with eps64 = 2⁻⁵². The second term bounds the
references' own error: 20-digit storage, and computation at about 10⁻⁴⁵ of the band.

**The scales:**
- **x:** scale_x = Σ|terms of x| + Σ|ν| + |q| + 1 + M, with M §10's term for the turnover.
  - M = Σ |ν_s| (|μ°_s|/RT + ln 1000), each row counted at each end, computed from §9's
    potentials.
  - For an outer-membrane form, M = 2(|μ°_f|/RT + ln 1000).
- **ln A:** scale_lnA = |ln K| + Σ|s_v ln v| + |s_u u| + Σ|s| + 1.
- **S, J⁻ and J:** d ln S = 16 eps64 scale_lnA + w dx; J's band is |J| d ln S + J⁻ dx.
- **Slopes:** 16 eps64 (1 + |s_A| + w|ν|) + |ν| (dw/dx) dx.
- **Dissipation:** RT (|x| band_J + |J| dx + band_J dx).
- **Two-term forms:** band_A + band_B.
- **The outer membrane:** both arrangements of J (two terms, or S (1 − e^x)) are covered.

**Calibration:** correct float64 kernels were run in four operation orders (`float64_calibration`).
- **The first three:** the reference's formulas, the closed forms or literal transcriptions, and
  the two-term arrangement with x summed in reverse.
- **The fourth, §9's route for a kernel:** x = Σν(μ°/RT − ln 1000) + Σν ln(c/1 mM) + q u, with
  each potential rounded once to a double.
- **Worst over all rows and quantities:** 0.036 of the band. The fourth order alone reaches
  0.018 of x's band, so the M term holds for that route.

**The power margin is 3:** a plant is caught at a row when some quantity misses by 3 bands or
more.

## Plants

There are 84 plants, every one caught on the registered rows.
- **Named in the tag:**
  - §10's two controls (`C1_q_reversed`, `ANT_shares_0.35_0.60`);
  - §6's held ratio r (`supply_held_ratio_r`);
  - §7's missing prefactor (`AK_no_prefactor`);
  - §8's total crossing in place of the forms (`OM_total_as_base_form`), the lead's request.
- **Columns:**
  - *caught*: rows where some quantity misses by 3 bands or more;
  - *by J*: rows where J alone does (any form's J, for the outer membrane);
  - *zero power*: rows where nothing misses by one band.

| Plant | Law | Caught | By J | Min margin | Zero power |
| --- | --- | --- | --- | --- | --- |
| `C1_q_reversed` (§10) | complex_I | 61/61 | 45 | 4.5e14 | 0 |
| `C1_scalar_proton_dropped` | complex_I | 61/61 | 56 | 1.1e11 | 0 |
| `C1_dG0_display` (−109.326) | complex_I | 61/61 | 49 | 8e7 | 0 |
| `C3_eq7_dG0_display` (+47.382) | complex_III_eq7 | 61/61 | 61 | 3e8 | 0 |
| `C3_eq24_as_printed` | complex_III_eq24 | 97/97 | 95 | 1.9e11 | 0 |
| `C3_eq24_as_balanced` (the first tag's) | complex_III_eq24 | 97/97 | 93 | 5.2e12 | 0 |
| `C3_eq24_restored_with_eq7_X_C3` (0.14483) | complex_III_eq24 | 97/97 | 95 | 1.6e12 | 0 |
| `C3_eq24_kappa_one`, `C3_eq24_phi_inverted`, `C3_eq24_dG0_display` | complex_III_eq24 | 97/97 each | 95, 95, 97 | 3.4e7 and up | 0 |
| `C4_dG0_display`, `C4_per_half_O2`, `C4_kappa_half`, `C4_ctot_parameter` | complex_IV | 61/61 each | 49, 59, 57, 6 | 3.4e7 and up | 0 |
| `F1_as_printed`, `F1_as_proton_restored`, `F1_as_base_form_restored` | atp_synthase | 99/99 each | 95, 97, 95 | 2.3e11 and up | 0 |
| `F1_dG0_display` (−5.032), `F1_dG0_ATP_text_sign`, `F1_q_reversed`, `F1_totals_in_dG`, `F1_total_Pi_in_dG` | atp_synthase | 99/99 each | 90, 99, 67, 97, 96 | 4.4e10 and up | 0 |
| `ANT_shares_0.35_0.60` (§10), `ANT_shares_swapped`, `ANT_totals` | nucleotide_exchange | 61/61 each | 45, 43, 56 | 4e10 and up | 0 |
| `PiHt_as_printed`, `PiHt_as_subscripts_swapped`, `PiHt_k_in_M`, `PiHt_one_proton` | phosphate_carrier | 49/49 each | 47, 45, 47, 47 | 8.6e11 and up | 0 |
| `KH_proton_sides_swapped` | k_h_exchange | 45/45 | 45 | 2.8e14 | 0 |
| `supply_held_ratio_r` (§6) | nadh_supply | 41/41 | 41 | 2.2e11 | 0 |
| `supply_as_printed` (Eq. 1) | nadh_supply | 41/41 | 39 | 5.2e11 | 0 |
| `supply_dG0_display` (+39.956), `supply_phi_inverted`, `supply_X_DH_without` | nadh_supply | 41/41 each | 41, 39, 39 | 2.5e7 and up | 0 |
| `supply_upkeep_ratio_only` (the work without §9's potentials) | nadh_supply | 39/41 | 0 (J is unchanged) | 9.3e5 | 2 |
| `AK_no_prefactor` (§7) | adenylate_kinase | 41/41 | 39 | 1.3e14 | 0 |
| `AK_as_printed` (Eq. 18 on totals) | adenylate_kinase | 41/41 | 39 | 1.9e14 | 0 |
| `AK_K_base_rounded` (0.38896), `AK_K_AK_on_base_forms`, `AK_prefactor_MgADP` | adenylate_kinase | 41/41 each | 41, 41, 39 | 5.4e7 and up | 0 |
| `OM_total_as_base_form` (no ligand carried) | outer_membrane | 93/93 | 91 | 5.2e13 | 0 |
| `OM_total_split_upstream` | outer_membrane | 55/93 | 55 | 4.2e10 | 38 |
| `OM_AMP_with_p_Pi`, `OM_gamma_missing` | outer_membrane | 93/93 each | 91 | 1.5e13 and up | 0 |
| `OM_MgADP_dropped` | outer_membrane | 75/93 | 75 | 3.5e6 | 18 |
| `FRT_display/*` (0.0389217), the 7 charged laws | all | 501/501 | 300/440 | 3.4e5 and up | 0 |
| `RT_display/*` (2478.9570), 12 laws | all | 740/770 | 373/709 (none on the neutral laws) | 11 and up | 30 |
| `T_310/*` (the first tag's 310.15 K), 12 laws | all | 760/770 | 413/709 | 3.8e4 and up | 10 |
| `activity_mM/*`, the 7 laws whose Σν ≠ 0 | all | 481/481 | 411/420 | 1.8e12 and up | 0 |

**Zero power, where it is expected:**
- **`OM_total_split_upstream`:** none at the 38 rows where both sides share Mg²⁺ and pH. There the
  split is exact, so these rows are expected to be powerless: 16 corners, and the 22 rows next to
  equilibrium.
- **`OM_MgADP_dropped`:** none at the 18 rows where MgADP⁻ is equal on both sides and carries
  nothing.
- **`supply_upkeep_ratio_only`:** none at the 2 rows at x = 0, where J = 0 and both works vanish.
- **The RT and T plants:** none at the neutral laws' rows within 10⁻⁶ of equilibrium. Those laws'
  x has no RT, and ΔG ≈ 0 there.
- **Activities in mM:** the exchange, the phosphate carrier, the K⁺/H⁺ exchange and the kinase
  (Σν = 0) are invariant to the activity unit, so that plant is not listed for them.

## Checks and measured violations (`checks.json`)

**Every law passes in every form,** registered or not, at 41 to 99 exact states each:
- x from the table agrees with each section's ΔG to 1.4·10⁻⁵⁷;
- each form's terms equal their literal transcription to 7·10⁻⁵⁸;
- each balanced form has d = 0, and each failing form's mismatch equals its closed form, to
  1.5·10⁻⁵⁷;
- the slopes of S, A, B and J agree with central differences to 5·10⁻³⁸;
- q F ∂J/∂Δψ agrees with a finite difference to 7·10⁻³⁷;
- the charge balance holds: Σνz = 0 and q_N = −q;
- in every balanced form, S > 0, −J ΔG ≥ 0, J = 0 at x = 0 and J reverses past it.

**The specific checks:**
- **Supply:**
  - the balanced J equals X_DH φ (r[NAD] − [NADH] h_N/10^−7.10) to 6·10⁻⁵⁹;
  - the upkeep's work equals the heat plus the work delivered to the NAD pool, to 10⁻⁶⁰;
  - x = 0 at [NADH] = r[NAD] and pH_N 7.10;
  - the balanced J equals Eq. 1 at pH_N 7.10.
- **Kinase:**
  - the balanced law equals the totals form with K_tot to 1.5·10⁻⁵⁸;
  - its forward term is the no-prefactor form's times total/free ATP;
  - Eq. 18's mismatch vanishes at the matched m.
- **Outer membrane:**
  - each class sum equals Eq. 13 on totals to 10⁻⁵⁹;
  - every form has −J ΔG ≥ 0 and J = 0 at equal sides, and reverses past it;
  - the slopes agree with central differences to 3·10⁻⁴⁰;
  - x ranges over ±10.6.
- **The tag's own numbers all reproduce:**
  - RT, F/RT, RT ln 10⁷;
  - the seven 1 M entries in kJ and in RT;
  - the first tag's complex III value corrected to +50.598452;
  - the stalls (−1.84, +0.68, +0.92, −1.38) and the slope 0.82;
  - the supply's ratios (0.794328, 3.63858, 3.37828, 0.274833, 0.296009) and its 0.2303 shift;
  - m, K_base, the prefactor 159.69 and K_tot = 0.4331;
  - all potentials and all M values;
  - Σν μ° = each entry.
- **Planted controls:**
  - §10's two are refused by the equilibrium check;
  - the held ratio r shifts x by exactly −0.10 ln 10;
  - the kinase without its prefactor keeps the equilibrium, and its rate is smaller by exactly
    1 + [Mg²⁺]_P/K_MgATP.

**x ranges over the grid:**
- complex I: −45.0 to +38.5;
- complex III: −33.4 to +30.3;
- complex IV: −118.7 to +39.9, with 8 rows below −80 (J⁻/J⁺ = e^x there to 2·10⁻⁵⁸);
- the lumped cycle: −148.6 to +63.6, with 13 rows below −80;
- ATP synthase: −29.7 to +34.5;
- the exchange: −24.8 to +15.0;
- the phosphate carrier: −12.1 to +8.5;
- the K⁺/H⁺ exchange: −4.8 to +6.9;
- the supply: −8.6 to +3.8;
- the kinase: −16.3 to +12.6.

**The unregistered forms' violations** (`laws.<key>.violation`):

| Form | Mismatch d | d over the grid | Uphill grid states | Worst −J ΔG, W (L mito)⁻¹ |
| --- | --- | --- | --- | --- |
| Eq. 24 printed | −2 ln(h_N/10⁻⁷) | −0.92 to +5.53 | 1/71 | −1.43 |
| Eq. 11 printed | ln(h_N/10⁻⁷) − ln[(1 + h_N/k_dH)/(1 + 10⁻⁷/k_dH)] | −2.35 to +0.27 | 1/71 | −9.0 |
| Eq. 11 `proton_restored` | −ln[(1 + h_N/k_dH)/(1 + 10⁻⁷/k_dH)] | −0.19 to +0.41 | 1/71 | −16 |
| Eq. 16 printed | 2 ln(h_P/h_N) | −3.68 to +7.83 | 12/23 | −546 |
| Eq. 1 printed | −ln(h_N/10^−7.10) | −0.69 to +2.53 | 1/15 | −0.22 |
| Eq. 18 printed | ln[(1 + m/K_MgATP)/(1 + m/K_MgADP)²] + ln(K_base/K_AK) | −0.23 to +1.24 | 2/15 | −615 |

## Findings for the lead

**The displays are planted:** the 1 M entries, RT, F/RT and K_base at 0.38896.
- Each is refused by margins of 10⁷ or more on the charged laws, and of 11 or more on the neutral
  laws.
- So a registry must carry the exact definitions, as §7 and §9 say.

## Regenerate and test

```
python -m validation.mitochondria.references.components.design          # writes interface/
python -m validation.mitochondria.references.components.design --check  # regenerates, compares
pytest tests/unit/test_mito_component_references.py
```

- `--check` compares `inputs.json`, `rows.json` and `plants.json` byte for byte, and
  `checks.json` apart from its float64 calibration, whose verdict must still pass.
- **The test:** `tests/unit/test_mito_component_references.py`, 5 test IDs, compiles no world.
  Its tier row was measured on the timed lane; the number is in the hand-back.
