# MT-1 component references: the mitochondrial laws

**Status: proposed on 20 November 2026, not registered.**
- Registration waits until the user rules on the forms and the engine's form design is ruled.
- If the engine's kernel signature differs from the appendix's "Reads", the rows mapped onto it
  are added before the tag, never after.
- Integration grants no scientific acceptance.

These are independent, high-precision references for each law in
`docs/MITOCHONDRIA_LAWS_APPENDIX.md` at tag `mito-laws-appendix-2026-11-20`. MT-1 judges the
engine's law kernels against them. No such kernel existed when they were written.

Beard's printed Eqs. 11, 16 and 24 fail the thermodynamic check. Each has rows in its printed
form, its balanced form and its alternative repairs (convention 6). The user's ruling selects
which form is judged; the chosen forms are registered.

## Independence

- **Read:**
  - the appendix at the tag, the only engineering source;
  - D193 to D196, D209 and D210, D227 and D228, and D234 in `docs/DECISIONS.md`, with the
    headings of D230 to D233 from a search;
  - `AGENTS.md`;
  - FR-7's layout, as a pattern only: `validation/fr7/__init__.py`,
    `validation/fr7/references/__init__.py`, the first 80 lines of its `REFERENCES_USAGE.md`, the
    head of its `rows.json` and its merge commit's message;
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
- **Questions to the lead:** the conventions below were put to the lead and approved. No other
  convention was needed.

## Conventions

1. **No evaluation domain.** The appendix declares none, and none belongs in the references;
   any limit on x is the engine's own business.
   - Each law's x range is reported.
   - Rows with x < −80 are kept, and J⁻/J⁺ = e^x is checked there.
   - Nothing is refused or clipped.
2. **The supply's work.** For section 6, W = J (ΔG°_DH + RT ln([NADH] h_N/[NAD])), with ΔG°_DH
   the world's input. There are rows for J and for the concentration part
   (`dG_conc_J_per_mol`) only.
3. **Parameters.** The "With Pi control" column applies throughout, Eq. 24 and its restored
   form included. The Eq. 7 rows use the "Without" column's X_C3 = 0.14483. Each law's column is
   in `inputs.json`.
4. **The input signature.**
   - Each law's "Reads" line, taken literally, lists its independent inputs.
   - The slopes of S are partial derivatives at fixed other inputs: d ln S/d ln c for each
     concentration and for h_N and h_P, and d ln S/du with u = FΔψ/RT.
     - Section 2's balanced S reads [MgADP⁻], total [Pi]_N, h_N, h_P and u, so
       d ln S/d ln h_N = −n_A.
     - Section 4's balanced S reads [H₂PO₄⁻]_P and h_N.
   - The slopes of x are with respect to the base-form species. They are exactly ν_s and q.
   - The J slopes are dJ/d ln c = J d ln S/d ln c − J⁻ ν_c, or A s_A − B s_B for a two-term form.
5. **The binding closure** (the lead's addition, so a kernel with another signature can be
   compared exactly). Each row of sections 2, 3 and 4 gives:
   - d ln[form]/d ln[total] = 1 at fixed free ligand;
   - each form's dependence on the free ligand at fixed total. Mg²⁺ binds ATP⁴⁻ and ADP³⁻, and
     H⁺ binds HPO₄²⁻.

   The chained slopes are checked against central differences of S and x recomputed from totals
   (`checks.json → binding_chain`).
6. **The alternative repairs** (the lead, 20 November). The tagged appendix states each failure's
   cause, not a list of repairs, so each form below is the repair its stated cause implies. The
   lead confirmed this set, and left out two others that fit the published curves poorly: Eq. 11
   with Pi read as H₂PO₄⁻, and Eq. 24 with the full affinity.

**The forms of the three failing laws.** A kappa form is J = A (1 − e^{κx}) and balances; a
two-term form is J = A − B as written.

| Law | Form | Kind | Forward term A | Backward term B |
| --- | --- | --- | --- | --- |
| Eq. 24 | `printed` | two-term | A₂₄ (printed) | X_C3 φ [c²⁺] (printed) |
| Eq. 24 | `balanced` | κ = 1/2 | A₂₄ (printed) | A₂₄ e^{x/2} = X_C3 φ [c²⁺] h_N/10⁻⁷ |
| Eq. 24 | `restored` | κ = 1/2 | φ_Pi × Eq. 7's term = A₂₄ · 10⁻⁷/h_N (the dropped +2RT ln(h_N/10⁻⁷) back) | X_C3 φ [c²⁺] (printed) |
| Eq. 11 | `printed` | two-term | A₁₁ (printed) | X_F1 [MgATP²⁻] (printed) |
| Eq. 11 | `balanced` | κ = 1 | A₁₁ (printed) | A₁₁ e^x |
| Eq. 11 | `proton_restored` | two-term | A₁₁ · h_N/10⁻⁷ (Eq. 10's consumed proton back) | X_F1 [MgATP²⁻] (printed) |
| Eq. 11 | `base_form_restored` | κ = 1 | X_F1 e^{−(ΔG°_ATP − n_A ΔG_H)/RT} (h_N/10⁻⁷)(K_MgADP/K_MgATP)[MgADP⁻][HPO₄²⁻](1 + 10⁻⁷/k_dH) | X_F1 [MgATP²⁻] (printed) |
| Eq. 16 | `printed` | two-term | X_PiHt [H₂PO₄⁻]_P h_N/([H₂PO₄⁻]_P + k) | X_PiHt [H₂PO₄⁻]_N h_P/(…) |
| Eq. 16 | `balanced` | κ = 1 | as printed | A₁₆ e^x |
| Eq. 16 | `subscripts_swapped` | κ = 1 | X_PiHt [H₂PO₄⁻]_P h_P/([H₂PO₄⁻]_P + k) | X_PiHt [H₂PO₄⁻]_N h_N/(…) |

**Notes on the forms:**
- **`proton_restored`** balances only in the source's own frame, where total Pi is one species.
  In the declared base forms it still fails, by d = −ln[(1 + h_N/k_dH)/(1 + 10⁻⁷/k_dH)].
- **`base_form_restored`** is its counterpart in the declared frame. It keeps the printed
  backward term, as `restored` does for Eq. 24.
- **Computation:** each form is computed from the printed terms times its stated factor, so a
  plant's change to the printed terms reaches every form. Its literal transcription, above, is
  checked against that to 10⁻⁵⁷.
- **`restored`** is also checked as φ_Pi times Eq. 7's own class at the With column's X_C3.
- **What each form reads** is in `inputs.json → laws.<key>.forms.<form>.reads`, beside Δψ.
  - `base_form_restored` reads [HPO₄²⁻]_N where the law's line has total [Pi]_N.
  - `subscripts_swapped` reads h_P where it has h_N.
  - The two-term forms list their backward term's reads too ([MgATP²⁻] for Eq. 11).

**Definitions and displays:**
- **Definitions:**
  - each ΔG° at 1 M is derived exactly from Table 2's pH-7 value, ΔG°(1 M) = ΔG°(pH 7) +
    ν_H RT ln 10⁷;
  - ΔG°_F comes from section 2's matched formula;
  - T = 310.15 K, with R = N_A k_B and F = N_A e exact.
- **Displays:** the appendix's rounded 1 M entries and its rounded RT and F/RT. Kernels built on
  the displays are planted below, with their sizes.
- **The transcription of the parameters** (`hp.py`) was compared with the tagged appendix's
  `<!-- parameters -->` table: 24 rows, no mismatch. θ_P, θ_N and the four ΔG° at pH 7 match its
  text.

**Arithmetic:** `decimal` at 60 digits, re-run at 80 digits. Every Decimal operation runs in a
local context.

## The laws

| Key | Law (section) | q | ΔG° at 1 M, J/mol (RT) | κ | Forms | States |
| --- | --- | --- | --- | --- | --- | --- |
| `complex_I` | redox_driven_proton_cycle@1 (1.1) | +4 | −110934.226 (−43.01893) | 1 | declared | 61 |
| `complex_III_eq7` | redox_driven_proton_cycle@1 (1.2, Eq. 7) | +2 | +50598.452 (+19.62146) | 1/2 | declared | 61 |
| `complex_III_eq24` | redox_driven_proton_cycle@1 (1.2, Eq. 24) | +2 | +50598.452 (+19.62146) | 1/2 | balanced, printed, restored | 97 |
| `complex_IV` | redox_driven_proton_cycle@1 (1.3), per O₂ | +8 | −412136.905 (−159.82162) | 1/4 | declared | 61 |
| `lumped_QO` | redox_driven_proton_cycle@1 (1.4), x only | +12 | −310940 (−120.57871) | — | declared | 61 |
| `atp_synthase` | proton_coupled_atp_synthesis_cycle@1 (2) | −3 | −6684.808 (−2.59229) | 1 | balanced, printed, proton_restored, base_form_restored | 99 |
| `nucleotide_exchange` | electrogenic_nucleotide_exchange@1 (3) | −1 | 0 | 1 | declared | 61 |
| `phosphate_carrier` | phosphate_proton_symport@1 (4) | 0 | 0 | 1 | balanced, printed, subscripts_swapped | 49 |
| `k_h_exchange` | potassium_proton_exchange@1 (5) | 0 | 0 | 1 | declared | 45 |
| `nadh_supply` | driven_redox_supply@1 (6), not a cycle | 0 | — | — | declared | 15 |

That is 610 states, and 1199 rows over all forms.

## Files

| Path | What it is |
| --- | --- |
| `interface/inputs.json` | Constants, parameters, the band rule, and each law's legs (species, side, ν, z), q, ΔG°, Reads and forms. Also every state as float64 inputs. A kernel under test reads only this file |
| `interface/rows.json` | Per law and form, per state: the reference values at 20 significant digits, their bands, flags and binding sensitivities |
| `interface/plants.json` | Per plant and form: its rows caught, its power on J alone, its minimum and maximum margins, per-quantity power and zero-power rows |
| `interface/checks.json` | The physics checks per form, the appendix's numbers, the failing forms' measured violations, the float64 calibration and the references' own precision |
| `hp.py` | Backends (decimal and float64), constants, the cited parameters |
| `laws.py` | The laws and their forms, computed along separate paths that the checks compare |
| `states.py` | The section 8 grid, interior points and the binding closure |
| `checks.py` | The checks of the physics |
| `plants.py` | The plants: subclasses of the laws, one parameter or constant changed, or another form |
| `design.py` | Writes `interface/` in about 80 s on one core. `--check` regenerates and compares |

**The paths in `laws.py`, compared by the checks:**
1. x from the turnover's table alone;
2. each form's terms, transcribed literally;
3. ΔG as each section writes it;
4. the stated closed forms of S and of the balanced backward term;
5. hand-derived slopes, checked against central differences.

**Test:** `tests/unit/test_mito_component_references.py`, about 1.1 s, with 5 test IDs. It checks
that the files parse. It regenerates three rows of every law and form, values and bands, exactly.
At the base state it checks every form: the balanced forms' equilibrium, reversal and slopes, and
the failing forms' closed-form mismatch. It also reruns the two planted controls, checks the
recorded verdicts, and checks independence.

## Rows

**States.** Each law has:
- its center (the base state);
- the 2^k corners of section 8's ranges over the inputs it reads;
- six interior points (a Halton sequence), with the pool totals varied, so that, for example,
  [c²⁺] + [c³⁺] ≠ cytC_tot;
- 22 states next to equilibrium: x = 0, ±10⁻⁶, ±10⁻³, ±0.1, ±1 and ±3 at two bases.
  - Base A: pH_N 7.4, pH_P 7.1.
  - Base B: an acid matrix, pH_N 6.8, pH_P 7.0.
  - A charged law reaches its target x by Δψ. A neutral law splits the move between its two
    sides.

**Each failing two-term form** (printed, and Eq. 11's `proton_restored`) also has two **stall**
rows, where its J = 0 (x = −d). Each failing law has two **coincidence** rows, where every form
agrees in value: pH_N = 7.0 for Eqs. 11 and 24, h_N = h_P for Eq. 16.

**Inputs** are float64 values. Each reference is evaluated at the exact value of those doubles,
so input rounding never enters a comparison.
- **Forms and totals:** each form in a row is rounded separately, so the forms agree with their
  totals and their binding relations to about one ulp. The references use the forms as given,
  which are the Reads. A kernel that recomputes forms from totals differs by that ulp, well
  inside the bands.
- **Section 8's box:** the states next to equilibrium may leave it. Δψ reaches 271 mV
  (complex IV), K⁺ 0.85 M and Pi 26 mM.

**Quantities.**

| Quantity | Meaning |
| --- | --- |
| `x`, `dG_J_per_mol`, `affinity_J_per_mol` | x = ΔG/RT, ΔG and −ΔG |
| `S`, `J_minus`, `J` | The one-way fluxes J⁺ = S and J⁻ = S e^x, and J = S (1 − e^x), in mol s⁻¹ (L mito)⁻¹ |
| `A_term`, `B_term` | J = A − B. B = A e^{κx} in a kappa form |
| `I_A_per_L` | q F J |
| `dI_ddpsi_A_per_L_per_mV` | q F ∂J/∂Δψ |
| `dissipation_W_per_L` | −J ΔG, ≥ 0 in every balanced form |
| `static_head_mV` | The Δψ where ΔG = 0 at fixed concentrations, q ≠ 0 |
| `slopes_lnS`, `slopes_J` | As in convention 4; the key `u` is ∂/∂u |
| two-term rows: `slopes_lnA`, `slopes_lnB`, `lnB_over_A` | The terms' slopes and log ratio |
| `nadh_supply` | `J`, `J_plus` = X φ r [NAD], `J_minus` = X φ [NADH], `dG_conc_J_per_mol` and `slopes_J` |

- **Two-term rows:** `S` and `J_minus` are the form's own two terms. For Eq. 24's printed form
  (κ = 1/2) these are not the declared one-way fluxes, which a failing law does not define.
- **Flags:**
  - `sign_not_judged`: |J| is within its band, so the sign of J cannot be judged in float64. The
    band comparison still applies.
  - `x_below_minus_80`: x < −80.

## Bands

band = 16 · eps64 · scale + 10⁻¹⁹ · |value|, with eps64 = 2⁻⁵². The second term bounds the
references' own error: the 20-digit storage, and a computation error measured at about 10⁻⁴⁵ of
the band (60 against 80 digits).

**The scales, per row:**
- **x:** scale_x = Σ|terms of x| + Σ|ν| + |q| + 1 + M, with dx = 16 eps64 scale_x.
  - The terms are ΔG°/RT, each ν ln a and q u.
  - M = 0 here (see below).
- **ln A:** scale_lnA = |ln K| + Σ|s_v ln v| + |s_u u| + Σ|s| + 1, where ln K = ln A − Σ s_v ln v
  − s_u u and the s are the forward term's log-slopes. In a two-term form, B takes the same with
  its own slopes.

**The bands that follow, in a kappa form:**
- d ln S = 16 eps64 scale_lnA + w dx, with w = d ln Σ_j e^{jκx}/dx;
- S: S · d ln S;
- J⁻: J⁻ (d ln S + dx);
- J: |J| d ln S + J⁻ dx;
- the slopes of ln S: 16 eps64 (1 + |s_A| + w|ν|) + |ν| (dw/dx) dx;
- the slopes of J: |s| band_J + |J| band_s + |ν| band_J⁻;
- dissipation: RT (|x| band_J + |J| dx + band_J dx). The last term is second order, since
  −J ΔG is quadratic next to x = 0.

**In a two-term form,** A and B take their own log scales, and J's band is band_A + band_B.

**Calibration.** Correct float64 kernels were run in three operation orders:
- the reference's own formulas in float64;
- the closed forms (the declared and balanced forms) or each form's literal transcription;
- the two-term arrangement, J = A − A e^{κx}, with x summed in reverse.

Their worst error over all rows and quantities is 0.045 of the band (`checks.json →
float64_calibration`).

**M: a kernel that builds ΔG° by summing species potentials.**
- Such a kernel carries an extra rounding of order eps64 · Σ|ν μ°|.
- For potentials of order 10⁶ J/mol, that rounding approaches the band.
- Such a kernel passes M = Σ|ν_s μ°_s|/RT (`design.bands_cycle(..., extra_scale_x=M)`). That is
  decided with the engine's form, before registration.

**The power margin** is 3: a plant is caught at a row when some quantity misses by 3 bands or
more.

## Plants

Each plant is a candidate kernel with one deliberate error. Section 8 names two of them; the rest
are proposed here.
- **Columns:**
  - *forms*: the reference forms measured against (in brackets);
  - *caught*: rows where some quantity misses by 3 bands or more, over those forms;
  - *by J alone*: rows where the flux J by itself misses by 3 bands or more;
  - *min margin*: the smallest top margin among the rows that catch;
  - *zero power*: rows where no quantity misses by one band.
- **The `*_as_<form>` plants** run one form of a failing law as the kernel under test against
  each of the law's other forms. Whichever form the user's ruling selects, the others are then its
  plants.
- **More in `plants.json`, per form:** the zero-power rows, the rows without power on J
  (`no_power_on_J`), the rows caught only by slopes (`zero_power_values_only`), and the power on
  each quantity.

| Plant | Law | Kind | Caught | By J alone | Min margin | Zero power |
| --- | --- | --- | --- | --- | --- | --- |
| `C1_q_reversed` (section 8) | complex_I | thermodynamic | 61/61 | 45 | 4.5e14 | 0 |
| `C1_scalar_proton_dropped` | complex_I | thermodynamic | 61/61 | 56 | 1.1e11 | 0 |
| `C1_dG0_display` (−110.934) | complex_I | free-energy entry | 61/61 | 49 | 8.3e7 | 0 |
| `C3_eq7_dG0_display` (+50.599) | complex_III_eq7 | free-energy entry | 61/61 | 61 | 2.8e8 | 0 |
| `C3_eq24_as_balanced` [printed, restored] | complex_III_eq24 | form | 194/194 | 188 | 9.8e11 | 0 |
| `C3_eq24_as_printed` [balanced, restored] | complex_III_eq24 | form | 194/194 | 190 | 3.4e11 | 0 |
| `C3_eq24_as_restored` [balanced, printed] | complex_III_eq24 | form | 194/194 | 188 | 9.0e11 | 0 |
| `C3_eq24_dG0_display` [all three] | complex_III_eq24 | free-energy entry | 291/291 | 194 | 2.8e8 | 0 |
| `C3_eq24_restored_with_eq7_X_C3` (0.14483) [restored] | complex_III_eq24 | parameter | 97/97 | 95 | 1.6e12 | 0 |
| `C3_eq24_kappa_one` [balanced, restored] | complex_III_eq24 | kinetic | 194/194 | 190 | 1.3e12 | 0 |
| `C3_eq24_phi_inverted` [all three] | complex_III_eq24 | kinetic | 291/291 | 285 | 1.4e14 | 0 |
| `C4_dG0_display` (−412.137) | complex_IV | free-energy entry | 61/61 | 49 | 1.8e7 | 0 |
| `C4_per_half_O2` | complex_IV | stoichiometry | 61/61 | 59 | 1.8e12 | 0 |
| `C4_kappa_half` | complex_IV | kinetic | 61/61 | 58 | 7.8e11 | 0 |
| `C4_ctot_parameter` | complex_IV | kinetic | 61/61 | 6 | 1.6e12 | 0 |
| `F1_as_balanced` [the other three] | atp_synthase | form | 297/297 | 287 | 3.6e12 | 0 |
| `F1_as_printed` [the other three] | atp_synthase | form | 297/297 | 282 | 2.7e11 | 0 |
| `F1_as_proton_restored` [the other three] | atp_synthase | form | 297/297 | 281 | 7.0e13 | 0 |
| `F1_as_base_form_restored` [the other three] | atp_synthase | form | 297/297 | 283 | 2.6e13 | 0 |
| `F1_dG0_display` (−6.685) [all four] | atp_synthase | free-energy entry | 396/396 | 182 | 1.3e8 | 0 |
| `F1_dG0_ATP_text_sign` (−36.03) [all four] | atp_synthase | free-energy entry | 396/396 | 396 | 2.3e24 | 0 |
| `F1_q_reversed` [all four] | atp_synthase | thermodynamic | 396/396 | 268 | 4.2e14 | 0 |
| `F1_totals_in_dG` [all four] | atp_synthase | binding | 396/396 | 198 | 2.4e12 | 0 |
| `F1_total_Pi_in_dG` [all four] | atp_synthase | binding | 396/396 | 193 | 5.9e10 | 0 |
| `ANT_shares_0.35_0.60` (section 8) | nucleotide_exchange | thermodynamic | 61/61 | 45 | 5.6e10 | 0 |
| `ANT_shares_swapped` (0.65, 0.35) | nucleotide_exchange | kinetic | 61/61 | 43 | 4.0e10 | 0 |
| `ANT_totals` | nucleotide_exchange | binding | 61/61 | 56 | 1.3e11 | 0 |
| `PiHt_as_balanced` [printed, subscripts_swapped] | phosphate_carrier | form | 98/98 | 92 | 4.6e12 | 0 |
| `PiHt_as_printed` [balanced, subscripts_swapped] | phosphate_carrier | form | 98/98 | 94 | 2.0e12 | 0 |
| `PiHt_as_subscripts_swapped` [balanced, printed] | phosphate_carrier | form | 98/98 | 92 | 3.7e13 | 0 |
| `PiHt_k_in_M` [all three] | phosphate_carrier | unit | 147/147 | 141 | 5.3e12 | 0 |
| `PiHt_one_proton` [all three] | phosphate_carrier | stoichiometry | 145/147 | 94 | 1.1e11 | 2 |
| `KH_proton_sides_swapped` | k_h_exchange | stoichiometry | 45/45 | 45 | 2.8e14 | 0 |
| `DH_phi_inverted` | nadh_supply | kinetic | 15/15 | 15 | 2.0e13 | 0 |
| `DH_r_on_NADH` | nadh_supply | kinetic | 15/15 | 15 | 1.3e14 | 0 |
| `FRT_display/*` (0.0374158 per mV), the 7 charged laws | all forms | constant | 992/992 | 625/931 | 3.9e5 | 0 |
| `RT_display/*` (2578.7306), 9 laws | all forms | constant | 1160/1184 | 784/1123 | 24 | 24 |
| `T_298/*` (298.15 K), 9 laws | all forms | constant | 1176/1184 | 893/1123 | 1.3e5 | 8 |
| `activity_mM/*` (c/1 mM), the 6 laws whose Σν ≠ 0 | all forms | unit | 931/931 | 565/870 | 2.6e12 | 0 |

**Read "caught" with the J column.** The slopes, the charge current and its Δψ slope carry
much of the catch.

**Where J alone has no power:**
- **Section 8's two controls:** none at the 16 corners with Δψ = 0, where a reversed q or a wrong
  share leaves J unchanged. Only the u-slopes catch them there.
- **On two-term rows:** none for any plant that changes only ΔG (the free-energy entries, the
  binding of ΔG's forms, the activity unit, the one-proton slip). A two-term J never reads x; its
  x, ΔG and dissipation catch those plants.
- **The c_tot plant:** none except at the 6 interior rows, where [c²⁺] + [c³⁺] differs from
  Table 1's 2.70 mM. Elsewhere it changes only S's slope in c³⁺.
- **At the coincidence rows,** a law's forms agree in value: J, x and the backward terms to
  10⁻⁴ of a band. Their h-slopes still differ there.
- **Far from equilibrium,** J separates two forms only while their backward terms matter; the
  backward term itself (`J_minus`, `B_term`) separates them at any x.

**Zero power:**
- The RT and T plants have none at the neutral laws' rows within 10⁻⁶ of equilibrium. Their x
  has no RT in it, and ΔG = RT x ≈ 0 there.
- The one-proton plant has none on the printed Eq. 16 at h_N = h_P, where the slip vanishes.

**Choices behind the plants:**
- **Complex III across the two kinds:** S, J⁻ and the slopes of ln S are not compared between a
  two-term and a kappa form (`excluded_quantities`). With κ = 1/2, the printed S and J⁻ are
  Eq. 24's own terms, and a kappa form's S and J⁻ are the declared one-way fluxes: different
  quantities, not the failure. `B_term` and J carry that comparison.
- **The two stoichiometry plants** on the neutral laws keep the declared q = 0.
- **Activities in mM:** the exchange, the phosphate carrier and the K⁺/H⁺ exchange (Σν = 0) are
  invariant to the activity unit, so that plant is not listed for them.

## Checks and measured violations (`checks.json`)

**Every cycle law passes in every form,** at 45 to 99 exact states each (`laws.<key>.forms.<form>`):
- x from the table agrees with each section's ΔG to 2·10⁻⁵⁷;
- the static head returns x = 0 to 5·10⁻⁵⁸;
- each form's terms equal their literal transcription to 5·10⁻⁵⁸ of the terms;
- each balanced form has d = 0 to 2·10⁻⁵⁷; each failing form's mismatch equals its closed form
  to 3·10⁻⁵⁸;
- the closed forms of S agree to 2·10⁻⁵⁸;
- the slopes of S, and of the two-term forms' A and B, agree with central differences to
  3·10⁻³⁸;
- the slopes of J agree with central differences, over every input and u, to 10⁻³⁸ of A + B;
- q F ∂J/∂Δψ agrees with a finite difference to 7·10⁻³⁷;
- the charge balance holds: Σ ν z = 0 and q_N = −q;
- in every balanced form, S > 0 and −J ΔG ≥ 0 (in W per L) at every state, J = 0 at x = 0
  (|J/S| below 10⁻⁴⁵), and J reverses past it;
- the lumped cycle's x = 2 x_III + x_IV to 3·10⁻⁵⁷;
- Eq. 24's `restored` equals φ_Pi times Eq. 7, and the balanced J times 10⁻⁷/h_N, to 10⁻⁵⁷.

**The supply (section 6) passes** (`checks.json → supply`):
- q = 0 and Σ ν z = 0;
- J⁺ − J⁻ = J;
- its slopes agree with central differences to 5·10⁻⁴⁰;
- J = 0 at [NADH] = r [NAD], with the sign changing across it.

**The section 8 planted controls are refused:**
- complex I with q = −4 runs forward at x = 0 and uphill at x = +1 (J/S = 1.0);
- the exchange with shares 0.35 and 0.60 has J/S = −0.12 at x = 0.

**x ranges** over the grid, with each law's rows below −80:

| Law | x range | Rows below −80 |
| --- | --- | --- |
| complex I | −43.9 to +38.1 | 0 |
| complex III | −32.8 to +30.0 | 0 |
| complex IV | −114.8 to +40.7 | 6; J⁻/J⁺ = e^x there to 3·10⁻⁵⁸ |
| lumped QO | −143.8 to +63.9 | 12 |
| ATP synthase | −29.1 to +34.0 | 0 |
| nucleotide exchange | −24.4 to +15.0 | 0 |
| phosphate carrier | −12.1 to +8.5 | 0 |
| K⁺/H⁺ exchange | −4.8 to +6.9 | 0 |

**The failing forms' violations,** measured with d = κ⁻¹ ln(B/A) − x (`laws.<key>.violation`).
The appendix's own values are reproduced: −1.84, +0.68, +0.92, −1.38 and 0.82.
- **Eq. 24 printed:** d = −2 ln(h_N/10⁻⁷).
  - Range: −0.92 to +5.53 over section 8's pH_N.
  - At base A (pH_N 7.4), the printed J at equilibrium is −1.51 J⁺, and its dissipation reaches
    −2.45 W (L mito)⁻¹ at x = −0.92.
  - Its backward term is 2.51 times the balanced one.
- **Eq. 11 printed:** d = ln(h_N/10⁻⁷) − ln[(1 + h_N/k_dH)/(1 + 10⁻⁷/k_dH)].
  - Range: −2.35 to +0.27 over pH_N 8.2 to 6.8.
  - At pH_N 7.4, the printed J at equilibrium is +0.49 J⁺, still making ATP.
  - Its dissipation reaches −389 W (L mito)⁻¹ at x = 0.34, because X_F1 is large.
- **Eq. 11 `proton_restored`:** d = −ln[(1 + h_N/k_dH)/(1 + 10⁻⁷/k_dH)].
  - Range: −0.19 to +0.41 over pH_N 6.8 to 8.2.
  - At pH_N 7.4, its J at equilibrium is −0.28 J⁺, hydrolysing, with its dissipation down to
    −40 W (L mito)⁻¹ at x = −0.12.
  - No grid state falls in its narrow uphill band.
- **Eq. 16 printed:** d = 2 ln(h_P/h_N).
  - Range: −3.68 to +7.83 over section 8's pH ranges.
  - 12 of its 23 grid states run uphill, the worst at −568 W (L mito)⁻¹ (pH_N 8.2, pH_P 6.5).
  - At base A, the printed J at equilibrium is −2.98 J⁺.

## Findings for the lead

1. **Section 7's 1 M entry for complex III reads +50.599 kJ/mol; the exact value is +50.598452.**
   - It is −32.53 + 2 RT ln 10⁷.
   - The table's own "In RT" value, +19.6215, matches 50.598.
   - Every other entry and constant agrees with its display (`appendix_numbers`).
2. **A kernel built on any rounded display is refused by margins of 10⁴ or more,** except the RT
   display on the neutral laws (24 at least).
   - The rounded displays are the 1 M entries, RT = 2578.7306 and F/RT = 0.0374158.
   - So the registry must carry ΔG° and the constants at full double precision, from their
     definitions. Alternatively, the user rules that the displays are the definitions, and these
     rows are regenerated from them.
3. **The bands assume ΔG° carried as one value,** or as species potentials whose Σ|ν μ°| is small
   beside the terms of x. If the engine's registry sums large formation potentials, the band takes
   the M term above. This is decided with the form design, before registration.
4. **Eq. 11's `proton_restored` still fails in the declared frame.** Restoring the proton balances
   it only with total Pi as one species. In base forms, the balanced repairs that keep a printed
   term are `balanced` (forward) and `base_form_restored` (backward).
5. **The exchange, the phosphate carrier and the K⁺/H⁺ exchange are invariant to the activity
   unit.** Their concentration unit cannot be tested from these laws alone.

## Regenerate and test

```
python -m validation.mitochondria.references.components.design          # writes interface/
python -m validation.mitochondria.references.components.design --check  # regenerates, compares
pytest tests/unit/test_mito_component_references.py                     # about 1.1 s
```

- Run from the repository root.
- `--check` compares `inputs.json`, `rows.json` and `plants.json` byte for byte, and
  `checks.json` apart from its float64 calibration, whose verdict must still pass.
