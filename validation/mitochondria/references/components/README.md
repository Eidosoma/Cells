# MT-1 component references: the mitochondrial laws

**Status: proposed on 20 November 2026, not registered.**
- Registration waits until the engine's form design is ruled (the lead, 20 November).
- If the engine's kernel signature differs from the appendix's "Reads", the rows mapped onto it
  are added before the tag, never after.
- Integration grants no scientific acceptance.

These are independent, high-precision references for each law in
`docs/MITOCHONDRIA_LAWS_APPENDIX.md` at tag `mito-laws-appendix-2026-11-20`. MT-1 judges the
engine's law kernels against them. No such kernel existed when they were written.

For Beard's three printed equations that fail the thermodynamic check (Eqs. 11, 16 and 24), both
the printed and the balanced forms have rows. The user's ruling selects which is judged.

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
3. **Parameters.** The "With Pi control" column applies throughout, Eq. 24 included. The Eq. 7
   rows use the "Without" column's X_C3 = 0.14483. Each law's column is in `inputs.json`.
4. **The input signature.**
   - Each law's "Reads" line, taken literally, lists its independent inputs.
   - The slopes of S are partial derivatives at fixed other inputs: d ln S/d ln c for each
     concentration and for h_N and h_P, and d ln S/du with u = FΔψ/RT.
     - Section 2's S reads [MgADP⁻], total [Pi]_N, h_N, h_P and u, so d ln S/d ln h_N = −n_A.
     - Section 4's S reads [H₂PO₄⁻]_P and h_N.
   - The slopes of x are with respect to the base-form species. They are exactly ν_s and q.
   - The J slopes are dJ/d ln c = J d ln S/d ln c − J⁻ ν_c.
5. **The binding closure** (the lead's addition, so a kernel with another signature can be
   compared exactly). Each row of sections 2, 3 and 4 gives:
   - d ln[form]/d ln[total] = 1 at fixed free ligand;
   - each form's dependence on the free ligand at fixed total. Mg²⁺ binds ATP⁴⁻ and ADP³⁻, and
     H⁺ binds HPO₄²⁻.

   The chained slopes are checked against central differences of S and x recomputed from totals
   (`checks.json → binding_chain`).

**Definitions and displays:**
- **Definitions:**
  - each ΔG° at 1 M is derived exactly from Table 2's pH-7 value, ΔG°(1 M) = ΔG°(pH 7) +
    ν_H RT ln 10⁷;
  - ΔG°_F comes from section 2's matched formula;
  - T = 310.15 K, with R = N_A k_B and F = N_A e exact.
- **Displays:** the appendix's rounded 1 M entries and its rounded RT and F/RT. Kernels built on
  the displays are planted below, with their sizes.

**Arithmetic:** `decimal` at 60 digits, re-run at 80 digits. Every Decimal operation runs in a
local context.

## The laws

| Key | Law (section) | q | ΔG° at 1 M, J/mol (RT) | κ | Forms | Rows |
| --- | --- | --- | --- | --- | --- | --- |
| `complex_I` | redox_driven_proton_cycle@1 (1.1) | +4 | −110934.226 (−43.01893) | 1 | declared | 61 |
| `complex_III_eq7` | redox_driven_proton_cycle@1 (1.2, Eq. 7) | +2 | +50598.452 (+19.62146) | 1/2 | declared | 61 |
| `complex_III_eq24` | redox_driven_proton_cycle@1 (1.2, Eq. 24) | +2 | +50598.452 (+19.62146) | 1/2 | balanced, printed | 97 |
| `complex_IV` | redox_driven_proton_cycle@1 (1.3), per O₂ | +8 | −412136.905 (−159.82162) | 1/4 | declared | 61 |
| `lumped_QO` | redox_driven_proton_cycle@1 (1.4), x only | +12 | −310940 (−120.57871) | — | declared | 61 |
| `atp_synthase` | proton_coupled_atp_synthesis_cycle@1 (2) | −3 | −6684.808 (−2.59229) | 1 | balanced, printed | 97 |
| `nucleotide_exchange` | electrogenic_nucleotide_exchange@1 (3) | −1 | 0 | 1 | declared | 61 |
| `phosphate_carrier` | phosphate_proton_symport@1 (4) | 0 | 0 | 1 | balanced, printed | 49 |
| `k_h_exchange` | potassium_proton_exchange@1 (5) | 0 | 0 | 1 | declared | 45 |
| `nadh_supply` | driven_redox_supply@1 (6), not a cycle | 0 | — | — | declared | 15 |

That is 608 states and 851 rows. A law's flux is J = A (1 − e^{κx}), so S = A/Σ_{j<1/κ} e^{jκx}.

## Files

| Path | What it is |
| --- | --- |
| `interface/inputs.json` | Constants, parameters, the band rule, each law's legs (species, side, ν, z), q, ΔG° and Reads, and every state as float64 inputs. A kernel under test reads only this file |
| `interface/rows.json` | Per law and form, per state: the reference values at 25 significant digits, their bands, flags and binding sensitivities |
| `interface/plants.json` | Per plant: its rows caught, minimum and maximum margins, per-quantity power and zero-power rows |
| `interface/checks.json` | The physics checks, the appendix's numbers, the printed forms' measured violations, the float64 calibration and the references' own precision |
| `hp.py` | Backends (decimal and float64), constants, the cited parameters |
| `laws.py` | The laws, computed along separate paths that the checks compare |
| `states.py` | The section 8 grid, interior points and the binding closure |
| `checks.py` | The checks of the physics |
| `plants.py` | The plants: subclasses of the laws, or one parameter or constant changed |
| `design.py` | Writes `interface/` in about 40 s on one core. `--check` regenerates and compares |

**The paths in `laws.py`, compared by the checks:**
1. x from the turnover's table alone;
2. the printed equation, transcribed term by term in its pH-7 form;
3. ΔG as each section writes it;
4. the stated closed forms of S and of the balanced backward term;
5. hand-derived slopes, checked against central differences.

**Test:** `tests/unit/test_mito_component_references.py`, about 1.5 s. It checks that the files
parse. It regenerates three rows of every law and form, values and bands, exactly. It reruns the
physics checks at the base state and the two planted controls, checks the recorded verdicts, and
checks independence.

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

Each failing printed form also has two **stall** rows, where the printed J = 0 (x = −d), and two
**coincidence** rows, where its mismatch d vanishes: pH_N = 7.0 for Eqs. 11 and 24, h_N = h_P for
Eq. 16.

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
| `A_term`, `B_term` | J = A − B in the printed arrangement. B = A e^{κx} in the declared form |
| `I_A_per_L` | q F J |
| `dI_ddpsi_A_per_L_per_mV` | q F ∂J/∂Δψ |
| `dissipation_W_per_L` | −J ΔG ≥ 0 |
| `static_head_mV` | The Δψ where ΔG = 0 at fixed concentrations, q ≠ 0 |
| `slopes_lnS`, `slopes_J` | As in convention 4; the key `u` is ∂/∂u |
| printed rows: `slopes_lnA`, `slopes_lnB`, `lnB_over_A` | The printed terms' slopes and log ratio |
| `nadh_supply` | `J`, `J_plus` = X φ r [NAD], `J_minus` = X φ [NADH], `dG_conc_J_per_mol` and `slopes_J` |

- **Printed rows:** `S` and `J_minus` are the printed equation's own two terms. For Eq. 24
  (κ = 1/2) these are not the declared one-way fluxes, which a failing printed law does not
  define.
- **Flags:**
  - `sign_not_judged`: |J| is within its band, so the sign of J cannot be judged in float64. The
    band comparison still applies.
  - `x_below_minus_80`: x < −80.

## Bands

band = 16 · eps64 · scale + 10⁻²⁴ · |value|, with eps64 = 2⁻⁵². The second term bounds the
references' own error: the 25-digit storage, and a computation error measured at about 10⁻⁴⁵ of
the band (60 against 80 digits).

**The scales, per row:**
- **x:** scale_x = Σ|terms of x| + Σ|ν| + |q| + 1 + M, with dx = 16 eps64 scale_x.
  - The terms are ΔG°/RT, each ν ln a and q u.
  - M = 0 here (see below).
- **ln A:** scale_lnA = |ln K| + Σ|s_v ln v| + |s_u u| + Σ|s| + 1, where ln K = ln A − Σ s_v ln v
  − s_u u and the s are the forward term's log-slopes. For the printed B, the same with B's
  slopes.

**The bands that follow, in the declared and balanced forms:**
- d ln S = 16 eps64 scale_lnA + w dx, with w = d ln Σ_j e^{jκx}/dx;
- S: S · d ln S;
- J⁻: J⁻ (d ln S + dx);
- J: |J| d ln S + J⁻ dx;
- the slopes of ln S: 16 eps64 (1 + |s_A| + w|ν|) + |ν| (dw/dx) dx;
- the slopes of J: |s| band_J + |J| band_s + |ν| band_J⁻;
- dissipation: RT (|x| band_J + |J| dx + band_J dx). The last term is second order, since
  −J ΔG is quadratic next to x = 0.

**In the printed forms,** A and B take their own log scales, and J's band is band_A + band_B.

**Calibration.** Correct float64 kernels were run in three operation orders:
- the reference's own formulas in float64;
- the appendix's closed forms, with J = S (1 − e^x);
- the printed arrangement, J = A − A e^{κx}, with x summed in reverse.

Their worst error over all rows and quantities is 0.045 of the band (`checks.json →
float64_calibration`). The worst cases are complex IV's x and J.

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
  - *caught*: rows where some quantity misses by 3 bands or more, out of the rows;
  - *by J alone*: rows where the flux J by itself misses by 3 bands or more;
  - *min margin*: the smallest top margin among the rows that catch;
  - *zero power*: rows where no quantity misses by one band.
- **Two forms:** a plant on a law with two forms has one entry for its balanced rows and one for
  its printed rows.
- **The "other form" plants** run each failing law's printed form against its balanced rows, and
  the reverse.
- **More in `plants.json`:** the zero-power rows, the rows without power on J
  (`no_power_on_J`), the rows caught only by slopes (`zero_power_values_only`), and the power on
  each quantity.

| Plant | Law | Kind | Caught | By J alone | Min margin | Zero power |
| --- | --- | --- | --- | --- | --- | --- |
| `C1_q_reversed` (section 8) | complex_I | thermodynamic | 61/61 | 45 | 4.5e14 | 0 |
| `C1_scalar_proton_dropped` | complex_I | thermodynamic | 61/61 | 56 | 1.1e11 | 0 |
| `C1_dG0_display` (−110.934) | complex_I | free-energy entry | 61/61 | 49 | 8.3e7 | 0 |
| `C3_eq7_dG0_display` (+50.599) | complex_III_eq7 | free-energy entry | 61/61 | 61 | 2.8e8 | 0 |
| `C3_eq24_other_form` (balanced, printed) | complex_III_eq24 | printed vs balanced | 97/97 and 97/97 | 95 and 95 | 3.4e11 | 0 and 0 |
| `C3_eq24_dG0_display` (balanced, printed) | complex_III_eq24 | free-energy entry | 97/97 and 97/97 | 97 and 0 | 2.8e8 | 0 and 0 |
| `C3_eq24_kappa_one` (balanced) | complex_III_eq24 | kinetic | 97/97 | 95 | 1.3e12 | 0 |
| `C3_eq24_phi_inverted` (balanced, printed) | complex_III_eq24 | kinetic | 97/97 and 97/97 | 95 and 95 | 1.4e14 | 0 and 0 |
| `C4_dG0_display` (−412.137) | complex_IV | free-energy entry | 61/61 | 49 | 1.8e7 | 0 |
| `C4_per_half_O2` | complex_IV | stoichiometry | 61/61 | 59 | 1.8e12 | 0 |
| `C4_kappa_half` | complex_IV | kinetic | 61/61 | 58 | 7.8e11 | 0 |
| `C4_ctot_parameter` | complex_IV | kinetic | 61/61 | 6 | 1.6e12 | 0 |
| `F1_other_form` (balanced, printed) | atp_synthase | printed vs balanced | 97/97 and 97/97 | 93 and 93 | 2.7e11 | 0 and 0 |
| `F1_dG0_display` (−6.685; balanced, printed) | atp_synthase | free-energy entry | 97/97 and 97/97 | 89 and 0 | 1.3e8 | 0 and 0 |
| `F1_dG0_ATP_text_sign` (−36.03; balanced, printed) | atp_synthase | free-energy entry | 97/97 and 97/97 | 97 and 97 | 2.3e24 | 0 and 0 |
| `F1_q_reversed` (balanced, printed) | atp_synthase | thermodynamic | 97/97 and 97/97 | 65 and 65 | 4.2e14 | 0 and 0 |
| `F1_totals_in_dG` (balanced, printed) | atp_synthase | binding | 97/97 and 97/97 | 97 and 0 | 2.4e12 | 0 and 0 |
| `F1_total_Pi_in_dG` (balanced, printed) | atp_synthase | binding | 97/97 and 97/97 | 94 and 0 | 5.9e10 | 0 and 0 |
| `ANT_shares_0.35_0.60` (section 8) | nucleotide_exchange | thermodynamic | 61/61 | 45 | 5.6e10 | 0 |
| `ANT_shares_swapped` (0.65, 0.35) | nucleotide_exchange | kinetic | 61/61 | 43 | 4.0e10 | 0 |
| `ANT_totals` | nucleotide_exchange | binding | 61/61 | 56 | 1.3e11 | 0 |
| `PiHt_other_form` (balanced, printed) | phosphate_carrier | printed vs balanced | 49/49 and 49/49 | 47 and 47 | 2.0e12 | 0 and 0 |
| `PiHt_k_in_M` (balanced, printed) | phosphate_carrier | unit | 49/49 and 49/49 | 47 and 47 | 5.3e12 | 0 and 0 |
| `PiHt_one_proton` (balanced, printed) | phosphate_carrier | stoichiometry | 49/49 and 47/49 | 47 and 0 | 1.1e11 | 0 and 2 |
| `KH_proton_sides_swapped` | k_h_exchange | stoichiometry | 45/45 | 45 | 2.8e14 | 0 |
| `DH_phi_inverted` | nadh_supply | kinetic | 15/15 | 15 | 2.0e13 | 0 |
| `DH_r_on_NADH` | nadh_supply | kinetic | 15/15 | 15 | 1.3e14 | 0 |
| `FRT_display/*` (0.0374158 per mV), the 7 charged laws | all | constant | 693/693 | 426/632 | 3.9e5 | 0 |
| `RT_display/*` (2578.7306) | 9 laws | constant | 818/836 | 540/775 | 24 | 18 |
| `T_298/*` (298.15 K) | 9 laws | constant | 830/836 | 602/775 | 1.3e5 | 6 |
| `activity_mM/*` (c/1 mM) | the 6 laws whose Σν ≠ 0 | unit | 632/632 | 369/571 | 2.6e12 | 0 |

**Read "caught" with the J column.** The slopes, the charge current and its Δψ slope carry
much of the catch.

**Where J alone has no power:**
- **Section 8's two controls:** none at the 16 corners with Δψ = 0, where a reversed q or a wrong
  share leaves J unchanged. Only the u-slopes catch them there.
- **On the printed rows:** none for any plant that changes only ΔG (the free-energy entries, the
  binding of ΔG's forms, the activity unit, the one-proton slip). The printed J never reads x;
  its x, ΔG and dissipation catch those plants.
- **The c_tot plant:** none except at the 6 interior rows, where [c²⁺] + [c³⁺] differs from
  Table 1's 2.70 mM. Elsewhere it changes only S's slope in c³⁺.
- **At the coincidence rows,** the printed and balanced J, x and backward terms agree to 10⁻⁴ of
  a band. Their h-slopes differ, because d's derivative is not zero there.
- **Far from equilibrium,** J separates the forms only while J⁻ is not negligible. For Eq. 11 and
  Eq. 16 (κ = 1), the backward term J⁻ (and `B_term`) separates them at any x.

**Zero power:**
- The RT and T plants have none at the neutral laws' rows within 10⁻⁶ of equilibrium. Their x
  has no RT in it, and ΔG = RT x ≈ 0 there.
- The one-proton plant has none on the printed Eq. 16 at h_N = h_P, where the slip vanishes.

**Choices behind the plants:**
- **Complex III across the forms:** S, J⁻ and the slopes of ln S are not compared
  (`excluded_quantities`). With κ = 1/2, the printed S and J⁻ are Eq. 24's own terms, and the
  balanced S and J⁻ are the declared one-way fluxes: different quantities, not the failure.
  `B_term` and J carry that comparison.
- **The two stoichiometry plants** on the neutral laws keep the declared q = 0.
- **Activities in mM:** the exchange, the phosphate carrier and the K⁺/H⁺ exchange (Σν = 0) are
  invariant to the activity unit, so that plant is not listed for them.

## Checks and measured violations (`checks.json`)

**Every cycle law passes,** at 45 to 97 exact states each (`laws.<key>.worst`):
- x from the table agrees with each section's ΔG to 2·10⁻⁵⁷;
- the closed forms of S agree to 2·10⁻⁵⁸;
- each passing printed equation equals its declared form to 4·10⁻⁵⁸ of A + B, with |d| below
  2·10⁻⁵⁷;
- each failing one's mismatch equals its closed form to 2·10⁻⁵⁸;
- the slopes of S, and of the printed terms A and B, agree with central differences to
  3·10⁻³⁸;
- the slopes of J agree with central differences, over every input and u, to 10⁻³⁸ of A + B;
- q F ∂J/∂Δψ agrees with a finite difference to 4·10⁻³⁷;
- the charge balance holds: Σ ν z = 0 and q_N = −q;
- J = 0 at x = 0 (|J/S| below 10⁻⁴⁵), and J reverses past it;
- S > 0 and the dissipation −J ΔG ≥ 0 (in W per L) at every state;
- the lumped cycle's x = 2 x_III + x_IV to 3·10⁻⁵⁷;
- the balanced backward terms equal their stated closed forms to 2·10⁻⁵⁸.

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

**The printed forms' violations,** measured with d = κ⁻¹ ln(B/A) − x. The appendix's own values
are reproduced: −1.84, +0.68, +0.92, −1.38 and 0.82.
- **Eq. 24:** d = −2 ln(h_N/10⁻⁷).
  - Range: −0.92 to +5.53 over section 8's pH_N.
  - At base A (pH_N 7.4), the printed J at equilibrium is −1.51 J⁺, and its dissipation reaches
    −2.45 W (L mito)⁻¹ at x = −0.92.
  - Its backward term is 2.51 times the balanced one.
- **Eq. 11:** d = ln(h_N/10⁻⁷) − ln[(1 + h_N/k_dH)/(1 + 10⁻⁷/k_dH)].
  - Range: −2.35 to +0.27 over pH_N 8.2 to 6.8.
  - At pH_N 7.4, the printed J at equilibrium is +0.49 J⁺, still making ATP.
  - Its dissipation reaches −389 W (L mito)⁻¹ at x = 0.34, because X_F1 is large.
- **Eq. 16:** d = 2 ln(h_P/h_N).
  - Range: −3.68 to +7.83 over section 8's pH ranges.
  - 12 of its 23 grid states run uphill, the worst at −568 W (L mito)⁻¹ (pH_N 8.2, pH_P 6.5).
  - At base A, the printed J at equilibrium is −2.98 J⁺.

The full tables are in `laws.<key>.printed_violation`.

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
4. **The exchange, the phosphate carrier and the K⁺/H⁺ exchange are invariant to the activity
   unit.** Their concentration unit cannot be tested from these laws alone.

## Regenerate and test

```
python -m validation.mitochondria.references.components.design          # writes interface/
python -m validation.mitochondria.references.components.design --check  # regenerates, compares
pytest tests/unit/test_mito_component_references.py                     # about 1.5 s
```

- Run from the repository root.
- `--check` compares `inputs.json`, `rows.json` and `plants.json` byte for byte, and
  `checks.json` apart from its float64 calibration, whose verdict must still pass.
