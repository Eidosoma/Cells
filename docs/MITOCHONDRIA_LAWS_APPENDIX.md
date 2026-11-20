# Mitochondrial laws: the declared equations

*Status: ruled, 20 November 2026 (D236), by the mitochondria lane. The appendix of declared
equations that MT-1's component references and MT-2's reference are registered against. It states
each law's physics only. The user chose Beard's repairs in frame B (D236):
- the balanced Eqs. 11 and 16 (§2, §4);
- Eq. 24 restored as φ_Pi × Eq. 7 (§1.2);
- the balanced NADH supply on a held reductant pair (§6);
- the IMS adenylate kinase in base forms (§7).

Each printed form is kept beside its declared form. Nothing here is registered.*

**Sources.** D. A. Beard, "A biophysical model of the mitochondrial respiratory system and
oxidative phosphorylation", PLoS Comput Biol 1(4):e36 (2005), doi:10.1371/journal.pcbi.0010036, and
its correction, PLoS Comput Biol 2(1):e8 (2006), doi:10.1371/journal.pcbi.0020008. Both are CC BY.
- "Eq. n" and "Table n" refer to the 2005 PDF, the version of record.
- Every Table 1 value is the 2006 correction's.
- Each was read at the typeset image.
- The mitochondria were isolated from rat heart.

**Words used.**
- **Printed:** an equation exactly as the source prints it, in this note's symbols.
- **Declared:** the form the laws use. Where it differs from the printed form, the user ruled on it
  (D236).
- **Declared, uncited:** a value the source does not print. It is ours, or a ruling's.

**Changes from the first tag** (mito-laws-appendix-2026-11-20):
- **Temperature:** 298.15 K, the lead's ruling, replaces 310.15 K. Every constant, 1 M value and
  entry changes; the laws, mismatches and stall points do not.
- **Ruled forms (D236):**
  - Eq. 24 is restored as φ_Pi × Eq. 7. It replaces the first tag's balanced form.
  - Eq. 1 is the balanced supply on a held reductant pair at reference matrix pH 7.10. The law is
    renamed `held_reductant_supply@1`, from `driven_redox_supply@1`, since it is no longer
    driven.
  - Eq. 18 is in base forms.
- **New sections:**
  - frame B (§0);
  - adenylate kinase (§7);
  - the outer membrane per form (§8);
  - the potential convention, with the species' potentials (§9) and the band term M (§10).
- **Fixed:** the first tag's complex III entry at 1 M was misprinted as +50.599 kJ mol⁻¹. At
  310.15 K it is +50.598; at 298.15 K it is +47.382 (§9).
- **§1.4** is not used under host P (D235).

## 0. Conventions

**Sides.** Each membrane law runs across one membrane with two ends.
- **N** is the matrix, the side that is negative at the operating point.
- **P** is the intermembrane space (IMS).
- The source's subscripts are x (matrix), i (IMS) and e (external buffer). Its inner-membrane laws
  use the external H⁺ and K⁺ for the IMS, since it takes these cations to equilibrate across the
  outer membrane. Here every P-side quantity is the IMS's own: [·]_P.
- §6 runs at N only and §7 at P only; neither has a membrane leg.

**Potential.** Δψ = φ_P − φ_N, the source's ΔΨ ("outer minus inner"), in mV. It is positive at the
operating point. u = FΔψ/RT.

**Concentrations and activities.**
- Concentrations are in M, moles per litre of that compartment's water.
- Every activity is a = c/(1 M), H⁺ included.
- Water's activity is 1, and water is never a row.
- h_N = [H⁺]_N and h_P = [H⁺]_P are free protons.
- ΔG_H = FΔψ + RT ln(h_P/h_N) is the free energy of moving one proton from N to P (Eq. 4).

**Frame B (D236).**
- Every law is written in base forms, with every proton counted. A phosphate's protons count with
  the protons: H₂PO₄⁻ is HPO₄²⁻ + H⁺.
- So the matrix's proton row is a total: the free protons plus those bound to phosphate and to the
  buffer. Its free part, h_N, follows from that total by the binding equilibria.
- In this frame, Eq. 22's proton row counts the protons on phosphate. Its coefficients per
  turnover are the laws' own H⁺_N counts: −5 (complex I), −2 (III), −8 per O₂ (IV), +(n_A − 1)
  (synthesis), +2 (phosphate carrier), −1 (K⁺/H⁺ exchange), +1 (the supply) and +1 (the leak).

**Turnover, stoichiometry and charge.**
- A law's turnover is one forward pass of its reaction as written here, with integer counts.
- ν_s is the change of species s at its end per turnover, products positive.
- q is the positive charge moved from N to P per turnover, q = Σ_{s at P} ν_s z_s. Every turnover
  conserves charge, so the N side changes by −q.

**Free energy.**
- ΔG = ΔG° + RT Σ ν_s ln a_s + q F Δψ, and x = ΔG/RT.
- ΔG° is the reaction's standard free energy, with every species at 1 M: the transport legs
  cancel, and water is at activity 1.
- The source states its values "at pH 7": every species at 1 M except H⁺, at 10⁻⁷ M. Each law
  below writes its free energy on that basis, as the source does, so each scalar proton appears as
  RT ln(h_N/10⁻⁷ M). §9 gives every value on the 1 M basis.
- A pure transport law has ΔG° = 0.

**Flux.**
- J is in mol s⁻¹ per litre of total mitochondrial volume, the source's unit. J > 0 runs the
  turnover forward.
- **The declared form:** J = S (1 − e^x), with S > 0 at every finite positive state. So J·ΔG ≤ 0
  everywhere, and J = 0 exactly where ΔG = 0.
- Some of the source's laws write their exponent per electron pair: J = A (1 − e^{κx}), with κ = ½
  or ¼ and A > 0. These have the same declared form with S = A (1 − e^{κx})/(1 − e^x), which is
  positive for 0 < κ ≤ 1. In particular:
  - κ = ½: S = A/(1 + e^{x/2});
  - κ = ¼: S = A/(1 + e^{x/4} + e^{x/2} + e^{3x/4}).
- The one-way fluxes are J⁺ = S and J⁻ = S e^x.

**Constants (declared, uncited: the source prints none).**
- **T = 298.15 K,** the lead's ruling (D236). The code-blind whole-organelle reference reproduces
  the source's published curves there: rms z 1.98, against 25.9 at 310.15 K.
- R and F are exact SI: R = N_A k_B and F = N_A e.
- So RT = 2478.9570 J mol⁻¹, F/RT = 0.0389217 mV⁻¹, and RT ln 10⁷ = 39.9561 kJ mol⁻¹.

**Forms: what binds what.** The source's own binding set is used. Binding is at equilibrium; the
source sets its Mg²⁺ binding rate large for that purpose (Table 1, X_MgA, class C).

| Symbol | Species and form | z | Where | Notes |
| --- | --- | --- | --- | --- |
| h | H⁺, free | +1 | N, P | |
| [K⁺] | K⁺ | +1 | N, P | |
| [Mg²⁺] | Mg²⁺, free | +2 | N, P | |
| [ATP⁴⁻] | ATP, Mg-free (the source's fATP) | −4 | N, P | No proton binds ATP in the source |
| [MgATP²⁻] | ATP, Mg-bound (mATP) | −2 | N, P | [MgATP²⁻] = [ATP⁴⁻][Mg²⁺]/K_MgATP |
| [ADP³⁻] | ADP, Mg-free (fADP) | −3 | N, P | No proton binds ADP in the source |
| [MgADP⁻] | ADP, Mg-bound (mADP) | −1 | N, P | [MgADP⁻] = [ADP³⁻][Mg²⁺]/K_MgADP |
| [AMP²⁻] | AMP | −2 | P | Nothing binds AMP in the source |
| [HPO₄²⁻] | Phosphate, base form | −2 | N, P | |
| [H₂PO₄⁻] | Phosphate, protonated | −1 | N, P | [H₂PO₄⁻] = h [HPO₄²⁻]/k_dH (Eq. 15) |
| [Pi] | Phosphate, total: [HPO₄²⁻] + [H₂PO₄⁻] | — | N, P | No Mg²⁺ binds phosphate in the source |
| [NAD] | NAD⁺, oxidized | −1 | N | The net charge with the phosphates |
| [NADH] | NADH, reduced | −2 | N | z(NAD) − z(NADH) = +1 is what enters |
| [Q], [QH₂] | Ubiquinone, ubiquinol | 0 | N | In the membrane, counted in matrix volume (Eq. 22) |
| [c³⁺], [c²⁺] | Cytochrome c, oxidized and reduced | +3, +2 | P | The source's labels; only their difference enters |
| [O₂] | Dioxygen | 0 | N | Held at 2.6×10⁻⁵ M in the source's simulations |
| [S_red], [S_ox] | The supply's reductant pair, reduced and oxidized | 0 | N | Held (read, never moved); declared (§6) |

## 1. `redox_driven_proton_cycle@1`: respiration

One law for the respiratory complexes. Each complex is a population of it, with its own
stoichiometry, S and parameters. Eqs. 3, 7 and 9 pass the check as printed, and §1.1–§1.3 declare
them unchanged, written as J = S (1 − e^x). Eq. 24 fails as printed; §1.2 declares it as φ_Pi ×
Eq. 7.

### 1.1 Complex I (Eqs. 2–5)

**Turnover: one NADH oxidized** (two electrons).

  NADH(N) + Q(N) + 5 H⁺(N) → NAD(N) + QH₂(N) + 4 H⁺(P)

- ν: NADH −1, Q −1, NAD +1, QH₂ +1, H⁺_N −5, H⁺_P +4.
  - Four protons are pumped and one is consumed by the chemistry (Eq. 2).
- Charge moved: q = +4.
- **Free energy:**
  ΔG = ΔG°_C1 + RT ln([NAD][QH₂]/([NADH][Q])) − RT ln(h_N/10⁻⁷ M) + 4ΔG_H,
  with ΔG°_C1 = −69.37 kJ mol⁻¹ at pH 7 (Table 2).
- **Printed (Eq. 3):**
  J = X_C1 { exp[−(ΔG°_C1 + 4ΔG_H − RT ln(h_N/10⁻⁷ M) − RT ln([Q]/[QH₂]))/RT] [NADH] − [NAD] }.
- **Declared:** J = S (1 − e^x), with S the printed forward term:
  S = X_C1 exp[−(ΔG°_C1 + 4ΔG_H − RT ln(h_N/10⁻⁷ M) − RT ln([Q]/[QH₂]))/RT] [NADH].
  - As a monomial: S = X_C1 e^{−ΔG°_C1/RT} 10⁷ [NADH] [Q] [QH₂]⁻¹ h_N⁵ h_P⁻⁴ e^{−4u}, with every
    concentration in M.
  - It equals the printed flux exactly, and S = X_C1 [NAD] e^{−x}.
- **Reads:** NADH, NAD, Q and QH₂ at N; free h_N and h_P; Δψ.

### 1.2 Complex III (Eqs. 6, 7 and 24)

**Turnover: one QH₂ oxidized** (two electrons, to two cytochrome c on the P side).

  QH₂(N) + 2 c³⁺(P) + 2 H⁺(N) → Q(N) + 2 c²⁺(P) + 4 H⁺(P)

- ν: QH₂ −1, Q +1, c³⁺ −2, c²⁺ +2, H⁺_N −2, H⁺_P +4.
  - Four protons are pumped, and the chemistry releases two in the matrix (Eq. 6 and its text).
  - So the matrix loses two net.
- Charge moved: q = +2.
- **Free energy:**
  ΔG = ΔG°_C3 + RT ln([Q][c²⁺]²/([QH₂][c³⁺]²)) + 2RT ln(h_N/10⁻⁷ M) + 4ΔG_H − 2FΔψ,
  with ΔG°_C3 = −32.53 kJ mol⁻¹ at pH 7 (Table 2).
  - The −2FΔψ is the two electrons crossing from N to P, so the electrical part is
    4FΔψ − 2FΔψ = qFΔψ.

**Without phosphate control (Eq. 7).**
- **Printed:**
  J = X_C3 { exp[−(ΔG°_C3 + 4ΔG_H + 2RT ln(h_N/10⁻⁷ M) − 2FΔψ + RT ln([Q]/[QH₂]))/2RT] [c³⁺] − [c²⁺] }.
- Call the first term A₇. Then [c²⁺] X_C3/A₇ = e^{x/2}, so J = A₇ (1 − e^{x/2}): the printed law
  passes with κ = ½.
- **Declared:** J = A₇ (1 − e^{x/2}), identical to the printed flux; S = A₇/(1 + e^{x/2}).

**With phosphate control (Eq. 24), the source's final model.**
- **Printed:**
  J = X_C3 φ_Pi { exp[−(ΔG°_C3 + 4ΔG_H − 2FΔψ + RT ln([Q]/[QH₂]))/2RT] [c³⁺] − [c²⁺] },
  with φ_Pi = (1 + [Pi]_N/k_Pi,3)/(1 + [Pi]_N/k_Pi,4) and [Pi]_N the total matrix phosphate.
- **It fails the check.**
  - Its exponent drops Eq. 7's term +2RT ln(h_N/10⁻⁷ M), the two protons the chemistry releases in
    the matrix.
  - With A₂₄ its first term and B₂₄ = X_C3 φ_Pi [c²⁺] its second, the mismatch is
    d = 2 ln(B₂₄/A₂₄) − x = −2 ln(h_N/10⁻⁷ M), which varies with the matrix pH.
  - The printed flux is zero at x = 2 ln(h_N/10⁻⁷ M), not at x = 0. At pH_N 7.4 it stalls with
    ΔG = −1.84 RT still downhill. Below pH_N 7 it runs uphill between that point and
    equilibrium.
- **Declared (ruled, D236): Eq. 24 restored as φ_Pi × Eq. 7.** This is the model as the source ran
  it.
  - J = φ_Pi A₇ (1 − e^{x/2}), with A₇ as above.
  - It is Eq. 24 with Eq. 7's +2RT ln(h_N/10⁻⁷ M) restored in its exponent. Its backward term is
    Eq. 24's, and its forward term is Eq. 24's times 10⁻⁷ M/h_N.
  - It passes, as Eq. 7 does. S = φ_Pi A₇/(1 + e^{x/2}).
- **Reads:** QH₂ and Q at N; c³⁺ and c²⁺ at P; free h_N and h_P; Δψ; and total [Pi]_N under Eq. 24.

### 1.3 Complex IV (Eqs. 8 and 9)

**Turnover: one O₂ reduced** (four electrons). The source writes its reaction per ½ O₂ (two
electrons); integer counts need the whole O₂.

  O₂(N) + 4 c²⁺(P) + 8 H⁺(N) → 2 H₂O + 4 c³⁺(P) + 4 H⁺(P)

- ν: O₂ −1, c²⁺ −4, c³⁺ +4, H⁺_N −8, H⁺_P +4.
  - Four protons are pumped, and the chemistry consumes four matrix protons (Eq. 8, doubled).
- Charge moved: q = +8.
- **Free energy:**
  ΔG = 2ΔG°_C4 + RT ln([c³⁺]⁴/([c²⁺]⁴[O₂])) − 4RT ln(h_N/10⁻⁷ M) + 4ΔG_H + 4FΔψ,
  with ΔG°_C4 = −122.94 kJ mol⁻¹ per ½ O₂ at pH 7 (Table 2).
  - The 4FΔψ is the four electrons crossing from P to N.
- **Printed (Eq. 9, per two electrons):**
  J_C4 = X_C4 · [1/(1 + k_O₂/[O₂])] · ([c²⁺]/c_tot) ·
  { exp[−(ΔG°_C4 + 2ΔG_H − 2RT ln(h_N/10⁻⁷ M) − ½ RT ln[O₂])/2RT] [c²⁺] − e^{u} [c³⁺] },
  with c_tot = [c³⁺] + [c²⁺].
- Each printed turnover reduces ½ O₂, so this law's flux is J = J_C4/2.
- With A₉ the printed first term, including its prefactors: J = (A₉/2)(1 − e^{x/4}), with x per O₂
  as above. The printed law passes: κ = ¼ per O₂, which is ½ per electron pair.
- **Declared:** J = (A₉/2)(1 − e^{x/4}), identical to half the printed flux;
  S = (A₉/2)/(1 + e^{x/4} + e^{x/2} + e^{3x/4}).
- **The domain:** per O₂, |x| doubles. At low Δψ it reaches about −94 RT on the grid of §10.
- **Reads:** O₂ at N; c²⁺ and c³⁺ at P (and their sum); free h_N and h_P; Δψ.

### 1.4 The lumped quinol-to-oxygen cycle (not used in MT-1 or MT-2)

Complexes III and IV taken together, with cytochrome c eliminated. It is needed only where the
IMS is merged with the medium. MT-1 and MT-2 keep the IMS (host P, D235), so they do not use it.
The source prints no kinetics for it, so only its stoichiometry and free energy are declared.

  2 QH₂(N) + O₂(N) + 12 H⁺(N) → 2 Q(N) + 2 H₂O + 12 H⁺(P)

- ν: QH₂ −2, Q +2, O₂ −1, H⁺_N −12, H⁺_P +12.
- Charge moved: q = +12.
- **Free energy:**
  ΔG = ΔG°_QO + RT ln([Q]²/([QH₂]²[O₂])) + 12ΔG_H, with ΔG°_QO = 2(ΔG°_C3 + ΔG°_C4) =
  −310.94 kJ mol⁻¹.
  - The scalar protons of III and IV cancel, so the pH-7 and 1 M values agree.

## 2. `proton_coupled_atp_synthesis_cycle@1`: ATP synthesis (Eqs. 10 and 11)

**Turnover: one ATP made**, with n_A protons entering from P (n_A = 3 in the source).

  ADP³⁻(N) + HPO₄²⁻(N) + n_A H⁺(P) → ATP⁴⁻(N) + H₂O + (n_A − 1) H⁺(N)

- ν: ADP³⁻ −1, HPO₄²⁻ −1, ATP⁴⁻ +1, H⁺_N +(n_A − 1), H⁺_P −n_A.
  - Eq. 10's chemistry consumes one matrix proton, and n_A protons cross from P to N.
  - n_A is an integer per ATP. A rotor's c protons per three ATP is the same law per rotation:
    ν multiplied by 3 with c in place of 3n_A.
- Charge moved: q = −n_A.
- **Free energy, in base forms:**
  ΔG = ΔG°_F + RT ln([ATP⁴⁻]/([ADP³⁻][HPO₄²⁻] h_N)) − n_A ΔG_H, every concentration in M at N.
  - ATP⁴⁻ and ADP³⁻ are the Mg-free forms, which are the source's fATP and fADP.
  - [HPO₄²⁻] = [Pi] k_dH/(k_dH + h_N).

**The free-energy entry, derived (declared, uncited).** ΔG°_F = −5.032 kJ mol⁻¹, every species at
1 M (−2.0299 RT).
- The source gives ΔG°_ATP = +36.03 kJ mol⁻¹ for H⁺ + ADP + Pi → ATP at pH 7 (Table 2), with
  [Pi] the total phosphate.
- It is matched to the base form at pH 7 with the source's own k_dH:
  ΔG°_F = ΔG°_ATP + RT ln(10⁻⁷) − RT ln(1 + 10⁻⁷ M/k_dH).
- **The sign:** the text under Eq. 11 prints ΔG°_ATP = −36.03 kJ mol⁻¹. Eq. 11 uses it for
  synthesis, which needs Table 2's +36.03, a standard state that favours hydrolysis. The text's
  sign is the slip.

**Printed (Eq. 11):**
  J = X_F1 { exp[−(ΔG°_ATP − n_A ΔG_H)/RT] (K_MgADP/K_MgATP) [MgADP⁻][Pi] − (1 M)[MgATP²⁻] },
with ΔG°_ATP = +36.03 kJ mol⁻¹, every concentration at N, [Pi] total, and the Mg-bound forms.

**It fails the check.**
- With Mg²⁺ binding at equilibrium, its two terms give
  ln(B/A) − x = ln(h_N/10⁻⁷ M) − ln[(1 + h_N/k_dH)/(1 + 10⁻⁷ M/k_dH)].
  - This varies with h_N; its slope in ln h_N is k_dH/(k_dH + h_N), 0.82 at pH_N 7.4.
- **In the source's own frame** (total Pi as one species, Eq. 10's scalar proton written out), the
  mismatch is exactly ln(h_N/10⁻⁷ M): the matrix proton that Eq. 10 consumes is missing from
  Eq. 11's exponent.
- Either way, the printed flux runs against its free energy next to its own zero. At pH_N 7.4 it
  keeps making ATP until ΔG = +0.68 RT (+0.92 RT in the source's own frame). That is where the
  source holds it, since X_F1 is chosen large enough to keep the reaction near equilibrium.

**Declared (balanced in frame B; ruled, D236):** J = A₁₁ (1 − e^x), keeping the printed forward
term A₁₁ = X_F1 exp[−(ΔG°_ATP − n_A ΔG_H)/RT] (K_MgADP/K_MgATP) [MgADP⁻][Pi].
- ΔG°_ATP stays inside A₁₁ as part of the rate constant. The thermodynamics is ΔG's.
- Its backward term is X_F1 (1 M)[MgATP²⁻] (10⁻⁷ M/h_N)(1 + h_N/k_dH)/(1 + 10⁻⁷ M/k_dH).
- S = A₁₁ = X_F1 e^{−ΔG°_ATP/RT} (K_MgADP/K_MgATP) [MgADP⁻][Pi] h_P^{n_A} h_N^{−n_A} e^{n_A u},
  with every concentration in M.

**Reads:** [MgADP⁻] and total [Pi] at N (in S); ATP⁴⁻, ADP³⁻, HPO₄²⁻ and h_N at N (in ΔG); h_P; Δψ.

## 3. `electrogenic_nucleotide_exchange@1`: the adenine nucleotide exchange (Eq. 14)

**Turnover: one ATP out of N for one ADP in.**

  ATP⁴⁻(N) + ADP³⁻(P) → ATP⁴⁻(P) + ADP³⁻(N)

- ν: ATP⁴⁻_N −1, ATP⁴⁻_P +1, ADP³⁻_P −1, ADP³⁻_N +1. Both are the Mg-free forms.
- Charge moved: q = −1, one negative charge from N to P.
- **Free energy:** ΔG = RT ln([ATP⁴⁻]_P [ADP³⁻]_N/([ATP⁴⁻]_N [ADP³⁻]_P)) − FΔψ. ΔG° = 0.
- **Printed (Eq. 14):**
  J = X_ANT { [ADP³⁻]_P/([ADP³⁻]_P + [ATP⁴⁻]_P e^{−θ_P u}) − [ADP³⁻]_N/([ADP³⁻]_N + [ATP⁴⁻]_N e^{θ_N u}) }
  · 1/(1 + k_mADP/[ADP³⁻]_P),
  with the voltage shares θ_P = 0.35 and θ_N = 0.65.
- **It passes, because θ_P + θ_N = 1.**
  - The difference of the two fractions is (ad − bc)/((a + b)(c + d)), with:
    - a = [ADP³⁻]_P, b = [ATP⁴⁻]_P e^{−θ_P u};
    - c = [ADP³⁻]_N, d = [ATP⁴⁻]_N e^{θ_N u}.
  - bc/(ad) = e^{x} exactly when θ_P + θ_N = 1.
- **Declared:** identical to the printed flux, J = S (1 − e^x), with
  S = X_ANT · [ADP³⁻]_P [ATP⁴⁻]_N e^{θ_N u} / {([ADP³⁻]_P + [ATP⁴⁻]_P e^{−θ_P u})([ADP³⁻]_N + [ATP⁴⁻]_N e^{θ_N u})}
  · 1/(1 + k_mADP/[ADP³⁻]_P).
  - The shares are the law's parameters, with θ_P + θ_N = 1 a condition of the law.
  - A pair that does not sum to one fails the check: the planted control.
- **Reads:** the Mg-free ATP⁴⁻ and ADP³⁻ at both ends; Δψ.

## 4. `phosphate_proton_symport@1`: the phosphate carrier (Eqs. 15 and 16)

**Turnover: one phosphate into N with one proton.**
- The source's text states an electroneutral 1:1 co-transport of H⁺ and H₂PO₄⁻ into the matrix.
- In base forms that is one HPO₄²⁻ and two H⁺:

  HPO₄²⁻(P) + 2 H⁺(P) → HPO₄²⁻(N) + 2 H⁺(N)

- ν: HPO₄²⁻_P −1, HPO₄²⁻_N +1, H⁺_P −2, H⁺_N +2.
  - Eq. 22 gives the matrix +1 Pi and +2 proton equivalents per turnover.
- Charge moved: q = 0.
- **Free energy:**
  ΔG = RT ln([HPO₄²⁻]_N h_N²/([HPO₄²⁻]_P h_P²)) = RT ln([H₂PO₄⁻]_N h_N/([H₂PO₄⁻]_P h_P)). ΔG° = 0.
  - The two forms agree because k_dH is the same on both sides.

**Printed (Eq. 16):**
  J = X_PiHt ([H₂PO₄⁻]_P h_N − [H₂PO₄⁻]_N h_P)/([H₂PO₄⁻]_P + k_PiHt).

**It fails the check.**
- Its proton subscripts are the reverse of the stated co-transport: the forward term carries the
  matrix proton, the backward term the IMS proton.
- The mismatch is d = ln(B/A) − x = 2 ln(h_P/h_N), and no stoichiometry, neutral or charged, makes
  it constant.
- The printed flux is zero at x = 2 ln 10 (pH_P − pH_N). At the source's pH_P 7.1 and a matrix at
  7.4 it stalls with ΔG = −1.38 RT still downhill. With a matrix more acid than the IMS it runs
  uphill.

**Declared (balanced in frame B; ruled, D236):** J = A₁₆ (1 − e^x), keeping the printed forward
term A₁₆ = X_PiHt [H₂PO₄⁻]_P h_N/([H₂PO₄⁻]_P + k_PiHt).
- Its backward term is X_PiHt [H₂PO₄⁻]_N h_N²/(h_P ([H₂PO₄⁻]_P + k_PiHt)).
- k_PiHt is printed in mM; with concentrations in M it enters as 10⁻³ k_PiHt.

**Reads:** H₂PO₄⁻ at P (in S) and h_N; HPO₄²⁻ (or H₂PO₄⁻) at both ends and h_P (in ΔG).

## 5. `potassium_proton_exchange@1`: the K⁺/H⁺ exchange (Eq. 21)

**Turnover: one K⁺ into N for one H⁺ out.**

  K⁺(P) + H⁺(N) → K⁺(N) + H⁺(P)

- ν: K⁺_P −1, K⁺_N +1, H⁺_N −1, H⁺_P +1.
- Charge moved: q = 0.
- **Free energy:** ΔG = RT ln([K⁺]_N h_P/([K⁺]_P h_N)). ΔG° = 0.
- **Printed (Eq. 21):** J = X_KH ([K⁺]_P h_N − [K⁺]_N h_P). It passes.
- **Declared:** identical, J = S (1 − e^x), with S = X_KH [K⁺]_P h_N.
- **Reads:** K⁺ at both ends; free h_N and h_P.

## 6. `held_reductant_supply@1`: the NADH supply (Eq. 1)

The source's substrate oxidation, which it calls an arbitrary four-parameter function outside its
thermodynamic framework. It is declared as a balanced supply: a held neutral reductant pair reduces
NAD in the matrix (D236). There is no membrane leg.

**Turnover:**

  S_red(N) + NAD(N) → S_ox(N) + NADH(N) + H⁺(N)

- ν: S_red −1, NAD −1, S_ox +1, NADH +1, H⁺_N +1.
- S_red and S_ox are a declared pair, both neutral and both held: read, never moved.
- Charge moved: q = 0. z(NAD) = z(NADH) + z(H⁺).

**Free energy:**
  ΔG = ΔG°_S + RT ln([S_ox][NADH]/([S_red][NAD])) + RT ln(h_N/10⁻⁷ M).
- **The anchor (the lead's ruling, option A):** ΔG°_S = 0 at pH 7 (+16.1181 RT at 1 M, §9). This
  is the named set's own anchor (declared, uncited).
- **The held pair's ratio (declared, D236),** in both directions:
  - S_red/S_ox = 10^{−0.10} r = 0.794328 r. That is 3.63858 with Table 1's r = 4.5807 (with Pi
    control), or 3.37828 with r = 4.2530 (without).
  - S_ox/S_red = 10^{0.10}/r: 0.274833 or 0.296009.
- With this anchor and ratio, the supply's equilibrium is the source's [NADH]/[NAD] = r at the
  reference matrix pH 7.10. So ΔG/RT = ln([NADH]/(r [NAD])) + ln(h_N/10^{−7.10} M).
- **A planted control:** a world that holds S_red/S_ox = r, without the factor 10^{−0.10}, puts
  that equilibrium at pH_N 7.00 instead. Its x is smaller by 0.10 ln 10 = 0.2303 at every state.

**Printed (Eq. 1):**
  J = X_DH φ_DH (r [NAD] − [NADH]), with φ_DH = (1 + [Pi]_N/k_Pi,1)/(1 + [Pi]_N/k_Pi,2).
- [Pi]_N is the total matrix phosphate. k_Pi,1 and k_Pi,2 are printed in mM.
- It relaxes [NADH]/[NAD] toward r at every matrix pH, so it is not balanced. In frame B its
  mismatch is d = ln(B/A) − x = −ln(h_N/10^{−7.10} M).

**Declared (balanced; ruled, D236):** J = A₁ (1 − e^x), keeping the printed forward term
A₁ = X_DH φ_DH r [NAD]:
  J = X_DH φ_DH (r [NAD] − [NADH] h_N/10^{−7.10} M).
- It equals Eq. 1 at pH_N 7.10.
- S = A₁, and S = X_DH φ_DH [NADH] (h_N/10^{−7.10} M) e^{−x}.

**Energy.** As with any held fuel, the pair's upkeep supplies work at the rate
−J (μ̃_{S_ox} − μ̃_{S_red}). The supply's heat is −J ΔG ≥ 0.

**Reads:** NAD and NADH at N; total [Pi]_N; h_N; the held pair (only their ratio enters).

## 7. Adenylate kinase in the IMS (Eqs. 17 and 18)

**Turnover, in base forms:**

  2 ADP³⁻(P) → ATP⁴⁻(P) + AMP²⁻(P)

- ν: ADP³⁻ −2, ATP⁴⁻ +1, AMP²⁻ +1, all at P.
- No proton enters, and the charge balances (−6 = −4 − 2). q = 0.
- The source writes the same direction: Eq. 17 is 2 ADP ⇌ ATP + AMP. Eq. 22 moves ATP_i +1,
  ADP_i −2 and AMP_i +1 per J_AKi.

**Free energy:** ΔG = −RT ln K_base + RT ln([ATP⁴⁻][AMP²⁻]/[ADP³⁻]²). It is dimensionless, so no
standard-state term enters.

**The constant (declared; the lead's ruling, D236).**
- K_base = K_AK (1 + m/K_MgADP)²/(1 + m/K_MgATP) = **0.388964538**, with Table 1's K_AK = 0.4331.
  It is derived from the match below at full precision; a rounded value (0.38896 or 0.389) is not
  the declared constant.
- m = 3.808553529 mM is the free Mg²⁺ of the source's state-3 buffer: 5.0 mM total Mg²⁺ and
  1.3 mM ADP, with no ATP or AMP (p. 0258; Figs. 2–5).
  - It is the positive root of m² + (K_MgADP + 1.3 − 5.0) m − 5.0 K_MgADP = 0, in mM. In that
    buffer only ADP binds Mg²⁺.
- The source states no IMS free Mg²⁺, so the match is declared.

**Printed (Eq. 18):** J = X_AK (K_AK [ADP]_P² − [AMP]_P [ATP]_P).
- It acts on totals: the source's unprefixed [ATP]_i and [ADP]_i include their Mg-bound forms.
- K_AK = 0.4331 is the equilibrium constant of the direction written. Table 1, footnote c, says
  it was computed from Alberty 2003's tables, at conditions the source does not print.
- **In frame B** its equilibrium moves with the free Mg²⁺. The mismatch is
  d = ln[(1 + m/K_MgATP)/(1 + m/K_MgADP)²] + ln(K_base/K_AK), zero at the matched m.

**Declared (in base forms; ruled, D236):**
  J = X_AK (K_base [ADP³⁻]² − [AMP²⁻][ATP⁴⁻]) = S (1 − e^x), with S = X_AK K_base [ADP³⁻]².
- X_AK is set large (class C), so the reaction stays near equilibrium.
- D236 reports no change at the source's reported states.

**Reads:** the Mg-free ATP⁴⁻ and ADP³⁻, and AMP²⁻, at P.

## 8. The outer membrane (Eq. 13)

**Printed (Eq. 13):** J_ATPt = γ p_A ([ATP]_e − [ATP]_i).
- ADP and AMP take the same form with p_A, and phosphate takes it with p_Pi.
- Each is on totals, and flows from the external buffer into the IMS.

**Declared (the lead's design for MT-1 and MT-2): a Fick flux for each form.**
- Each form f of a class moves J_f = γ p_class ([f]_e − [f]_P). There is one permeability per
  class:
  - p_A for ATP⁴⁻, MgATP²⁻, ADP³⁻, MgADP⁻ and AMP²⁻;
  - p_Pi for HPO₄²⁻ and H₂PO₄⁻.
- Summed over a class's forms, it equals Eq. 13's total flux exactly.
- A bound form carries its ligand (Mg²⁺ or H⁺) with it.
- Units: γ p is in s⁻¹ (μm⁻¹ times μm s⁻¹), so J is in mol s⁻¹ per litre of mitochondria.
- The free H⁺, K⁺ and Mg²⁺ are declared with the world. The source takes H⁺ and K⁺ to equilibrate
  rapidly across the outer membrane.

## 9. Parameters, potentials and free-energy entries

**Table 1 values** (the 2006 correction; units as printed). "With Pi control" is the source's
final model, under Eq. 24. "Without" is Eq. 7's.

<!-- parameters -->
| Name | Law | With Pi control | Without | Unit | Source |
| --- | --- | --- | --- | --- | --- |
| `X_C1` | §1.1 | 0.36923 | 0.54088 | mol s⁻¹ M⁻¹ (L mito)⁻¹ | Table 1 (2006) |
| `X_C3` | §1.2 | 0.091737 | 0.14483 | mol s⁻¹ M⁻¹ (L mito)⁻¹ | Table 1 (2006) |
| `k_Pi3` | §1.2 | 0.19172 | — | mM | Table 1 (2006) |
| `k_Pi4` | §1.2 | 25.310 | — | mM | Table 1 (2006) |
| `X_C4` | §1.3 | 3.2562e-5 | 2.2669e-5 | mol s⁻¹ M⁻¹ (L mito)⁻¹ | Table 1 (2006) |
| `k_O2` | §1.3 | 1.20e-4 | 1.20e-4 | M | Table 1 (2006) |
| `X_F1` | §2 | 150.93 | 154.82 | mol s⁻¹ M⁻² (L mito)⁻¹ | Table 1 (2006) |
| `n_A` | §2 | 3 | 3 | 1 | Table 1 (2006) |
| `K_MgATP` | §2, §7 | 24.0e-6 | 24.0e-6 | M | Table 1 (2006) |
| `K_MgADP` | §2, §7 | 347.0e-6 | 347.0e-6 | M | Table 1 (2006) |
| `k_dH` | §2, §4 | 1.7783e-7 | 1.7783e-7 | M | Table 1 (2006) |
| `X_ANT` | §3 | 0.0079204 | 0.010723 | mol s⁻¹ (L mito)⁻¹ | Table 1 (2006) |
| `k_mADP` | §3 | 3.5e-6 | 3.5e-6 | M | Table 1 (2006) |
| `X_PiHt` | §4 | 3.3943e5 | 3.7442e5 | mol s⁻¹ M⁻¹ (L mito)⁻¹ | Table 1 (2006) |
| `k_PiHt` | §4 | 0.45082 | 0.72911 | mM | Table 1 (2006) |
| `X_KH` | §5 | 2.9802e7 | 3.1775e7 | mol s⁻¹ M⁻² (L mito)⁻¹ | Table 1 (2006) |
| `X_DH` | §6 | 0.09183 | 0.10990 | mol s⁻¹ M⁻¹ (L mito)⁻¹ | Table 1 (2006) |
| `r` | §6 | 4.5807 | 4.2530 | 1 | Table 1 (2006) |
| `k_Pi1` | §6 | 0.13413 | 0.13890 | mM | Table 1 (2006) |
| `k_Pi2` | §6 | 0.67668 | 0.62396 | mM | Table 1 (2006) |
| `K_AK` | §7 | 0.4331 | 0.4331 | 1 | Table 1 (2006) |
| `X_AK` | §7 | 1.0e6 | 1.0e6 | mol s⁻¹ M⁻² (L mito)⁻¹ | Table 1 (2006) |
| `p_A` | §8 | 85.0 | 85.0 | μm s⁻¹ | Table 1 (2006) |
| `p_Pi` | §8 | 327 | 327 | μm s⁻¹ | Table 1 (2006) |
| `gamma` | §8 | 5.99 | 5.99 | μm⁻¹ | Table 1 (2006) |
| `NAD_tot` | §1.1, §6 | 2.97 | 2.97 | mM | Table 1 (2006) |
| `Q_tot` | §1.1, §1.2 | 1.35 | 1.35 | mM | Table 1 (2006) |
| `cytC_tot` | §1.2, §1.3 | 2.70 | 2.70 | mM | Table 1 (2006) |
| `A_tot` | §2, §3 | 10 | 10 | mM | Table 1 (2006) |
<!-- /parameters -->

- **Also printed:**
  - θ_P = 0.35 and θ_N = 0.65 (Eq. 14);
  - four protons pumped by complexes I and III, two by IV per ½ O₂ (Eqs. 2, 6 and 8).
- **Declared (D236):**
  - T = 298.15 K;
  - the supply's reference matrix pH 7.10 and ΔG°_S = 0 at pH 7;
  - adenylate kinase matched at the state-3 buffer (5.0 mM total Mg²⁺, 1.3 mM ADP), whose free
    Mg²⁺ m = 3.808553529 mM gives K_base = 0.388964538 (§7);
  - matrix Mg²⁺ total 5 mM.
- **Units in ratios:** a ratio such as [Pi]_N/k_Pi,3 or [H₂PO₄⁻]_P + k_PiHt needs both terms in
  one unit; the k's printed in mM enter as 10⁻³ k in M.
- **Where the correction changed a value these laws use:** K_MgATP, K_MgADP, k_dH, k_mADP, k_O₂ and
  X_AK.
  - The 2005 PDF prints 1.0×10⁻⁶ for each.
  - The correction also changes X_KH with phosphate control (2.9802×10⁻⁶ in 2005), C_IM and X_MgA.

**The potential convention** (the binding owner's, for its named set; the species registry's one
authority):
- **Basis:** potentials are μ°/RT at 1 M. A world that declares another standard concentration
  c0 shifts every potential, forms included, by ln(c0/1 M).
- **Zero references** (μ°/RT = 0 at 1 M): H⁺, K⁺, Mg²⁺, O₂, NAD, Q, cytochrome c³⁺, ADP³⁻, HPO₄²⁻
  and S_ox.
  - Water is never a row: μ = 0 at unit activity, omitted from every stoichiometry.
  - A declared proton buffer's base form is also a reference at 0, outside the set.
- **Each reaction fixes one species, in this order,** from x° = 1000 ΔG°(pH 7)/(RT) + ν_H ln 10⁷.
  For a total, add ν ln P at 10⁻⁷ M, with P its binding polynomial.
  1. Complex IV, per O₂ → cytochrome c²⁺.
  2. Complex III → QH₂.
  3. Complex I → NADH.
  4. Synthesis → ATP⁴⁻, including the total phosphate's term −ln(1 + 10⁻⁷ M/k_dH).
  5. The supply's declared reaction (ΔG°_S = 0 at pH 7, ν_H = +1) → S_red.
  6. Adenylate kinase (ΔG°/RT = −ln K_base) → AMP²⁻.
- **Forms:** μ°_f = μ°_base + Σ n μ°_L + ln K_d, with K_d in M.
  - ln K_d carries no temperature.
  - At another T only the reaction terms change.
- **Arithmetic:** evaluate at 50 digits and round once.
- **With concentrations in mM,** x = Σ ν (μ°/RT − ln 1000) + Σ ν ln(c/1 mM) + q u. This is the same
  as Σ ν μ°/RT + Σ ν ln(c/1 M) + q u.

The species' potentials at 298.15 K (μ°/RT at 1 M):

<!-- potentials -->
| Species | μ°/RT | How it is set |
| --- | --- | --- |
| `H` | 0 | Zero reference |
| `K` | 0 | Zero reference |
| `Mg` | 0 | Zero reference |
| `O2` | 0 | Zero reference |
| `NAD` | 0 | Zero reference |
| `Q` | 0 | Zero reference |
| `cytc_ox` | 0 | Zero reference |
| `ADP` | 0 | Zero reference |
| `HPO4` | 0 | Zero reference |
| `S_ox` | 0 | Zero reference |
| `cytc_red` | 40.914814298 | Complex IV per O₂ |
| `QH2` | 62.715891459 | Complex III |
| `NADH` | 106.817529855 | Complex I |
| `ATP` | −2.029938769 | Synthesis, with total Pi's term |
| `S_red` | 90.699434204 | The supply's declared reaction |
| `AMP` | 2.974205870 | Adenylate kinase's K_base |
| `MgATP` | −12.667395497 | ATP⁴⁻ + Mg²⁺, K_d 24.0×10⁻⁶ M |
| `MgADP` | −7.966185778 | ADP³⁻ + Mg²⁺, K_d 347.0×10⁻⁶ M |
| `H2PO4` | −15.542437799 | HPO₄²⁻ + H⁺, K_d 1.7783×10⁻⁷ M |
<!-- /potentials -->

**Free-energy entries** (the standard free energy each law's chemistry carries, at 298.15 K, every
species at 1 M; each equals Σ ν μ°/RT over the potentials above):

| Law | Reaction (base forms, water at activity 1) | Source value | kJ mol⁻¹ at 1 M | In RT |
| --- | --- | --- | --- | --- |
| §1.1, per NADH | NADH + Q + H⁺ → NAD + QH₂ | −69.37 kJ mol⁻¹ at pH 7 (Table 2) | −109.326 | −44.1016 |
| §1.2, per QH₂ | QH₂ + 2 c³⁺ → Q + 2 c²⁺ + 2 H⁺ | −32.53 at pH 7 (Table 2) | +47.382 | +19.1137 |
| §1.3, per O₂ | O₂ + 4 c²⁺ + 4 H⁺ → 4 c³⁺ + 2 H₂O | 2 × (−122.94) at pH 7 (Table 2) | −405.704 | −163.6593 |
| §1.4, per O₂ | 2 QH₂ + O₂ → 2 Q + 2 H₂O | −310.94 (Table 2, summed) | −310.940 | −125.4318 |
| §2, per ATP | ADP³⁻ + HPO₄²⁻ + H⁺ → ATP⁴⁻ + H₂O | +36.03 at pH 7, total Pi (Table 2) | −5.032 (matched, §2) | −2.0299 |
| §6, per NADH | S_red + NAD → S_ox + NADH + H⁺ | 0 at pH 7 (declared) | +39.956 | +16.1181 |
| §7, per 2 ADP | 2 ADP³⁻ → ATP⁴⁻ + AMP²⁻ | K_AK 0.4331 on totals (Table 1) | +2.341 (matched, §7) | +0.9443 |
| §3, §4, §5, §8 | Transport only | — | 0 | 0 |

- **The conversion:** the source writes each scalar proton as RT ln(h/10⁻⁷ M). So a reaction that
  produces ν_H scalar protons has ΔG°(1 M) = ΔG°(pH 7) + ν_H RT ln 10⁷.
  - This is exact for §1 and §6, whose species bind no proton in the source.
  - §2's and §7's values are the matched ones given there.
- **The first tag's complex III value** at 310.15 K was misprinted as +50.599 kJ mol⁻¹. It is
  +50.598452.
- A law's ΔG° holds only where its reaction's species have these potentials. A different standard
  potential for any of them is a departure from the source.

## 10. What the component references check

On a grid of states, and on states placed next to each turnover's equilibrium (|x| from 0 to 3):
- **Grid:**
  - Δψ 0–250 mV; pH_N 6.8–8.2; pH_P 6.5–7.6;
  - the reduced fractions of NAD, Q and cytochrome c 0.01–0.99;
  - ATP/ADP 10⁻³–10³ at each end; phosphate 0.1–20 mM; O₂ 10⁻⁴–0.3 mM;
  - free Mg²⁺ 0.1–5 mM at each end; K⁺ 10–200 mM; AMP 10⁻³–1 mM.
- **For each declared law:**
  - J, ΔG and their signs: J·ΔG ≤ 0, J = 0 at ΔG = 0, and reversal past it;
  - the static head, the Δψ where ΔG = 0 at fixed concentrations;
  - the charge current's slope q F ∂J/∂Δψ against a finite difference;
  - the one-way flux J⁺ = S at the source's parameters.
- **For each printed law:**
  - its agreement with the declared form where it passes (§1.1, Eq. 7 of §1.2, §1.3, §3, §5);
  - its mismatch d where it does not (Eq. 24, §2, §4, §6 and §7), in the closed forms above.
- **Planted controls**, each of which the check must refuse:
  - a reversed sign in a stoichiometry or in q (complex I with −4u in place of +4u);
  - exchange shares that do not sum to one (θ_P = 0.35, θ_N = 0.60).
- **Arithmetic:** high precision, 50 digits or more. The lane's own check of this appendix runs at
  50 digits and is not independent of it.

**The band term M.** It is the scale of each turnover's x in rounding, from the potentials above.
- M = Σ_s |ν_s| (|μ°_s|/RT + ln 1000), over the turnover's rows. Each row is counted at each end,
  so a proton pumped from N to P counts at both.
- Two evaluations of x are compared within a small multiple of ε·M, with ε the double-precision
  unit (2⁻⁵²).

<!-- bands -->
| Turnover | M (298.15 K) | Law |
| --- | --- | --- |
| C1 | 259.334 | §1.1, per NADH |
| C3 | 227.439 | §1.2, per QH₂ |
| C4 | 308.722 | §1.3, per O₂ |
| QO | 325.757 | §1.4, per O₂ |
| F1 | 57.292 | §2, per ATP (n_A = 3) |
| ANT | 31.691 | §3 |
| PiHt | 41.447 | §4 |
| KH | 27.631 | §5 |
| Supply | 232.056 | §6, per NADH |
| AK | 32.635 | §7, per 2 ADP |
<!-- /bands -->

## 11. Reading notes on the source

Each was checked at the typeset image of the PDF, not a text layer.
- **Table 1 in the 2005 PDF is the uncorrected table.**
  - Nine values differ from the 2006 correction (§9). So the correction must be read from its
    own article.
  - Table 1 describes V_i as "per total cell volume". With its footnote f (matrix 90%, IMS 10% of
    the water) it reads as per total mitochondrial volume.
- **ΔG°_ATP's sign:** −36.03 in the text under Eq. 11, +36.03 in Table 2 (§2).
- **Eq. 22's matrix proton balance** in the PDF has −(4 + 1) J_C1, −(4 − 2) J_C3, −(2 + 2) J_C4,
  +(n_A − 1) J_F1, +2 J_PiHt, +J_Hle, −J_KH and +J_DH. These agree with Eqs. 2, 6, 8 and 10, and
  with frame B (§0).
  - The sentence after it says complex III consumes "three" matrix protons and describes complex
    I's reaction. That is a leftover: the printed coefficients are the ones that agree.
  - PLOS's web XML version of Eq. 22 differs from the PDF's; the PDF is the version of record.
- **K_AK** is on totals, in the direction 2 ADP → ATP + AMP (§7).
  - Eq. 18's unprefixed symbols are totals; the prefixes f and m mark the Mg-free and Mg-bound
    parts.
  - Its source is Alberty 2003 (Table 1, footnote c), at conditions not printed.
- **The IMS free Mg²⁺ is not stated:** [Mg²⁺]_i has no equation in Eq. 22.
- **No temperature, R or F is printed** (§0).

## 12. Not covered here

These are the source's other equations, declared with MT-1's world:
- the proton leak (Eq. 19) and the passive K⁺ flux (Eq. 20, zero in the source's fits);
- Mg²⁺ binding (Eq. 12), taken at equilibrium here;
- the matrix buffer (Eq. 22's r_buff), whose protons count in the proton row (§0, frame B);
- the membrane capacitance (Eq. 22).
