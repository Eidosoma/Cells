# Mitochondrial laws: the declared equations

*Status: proposed, 20 November 2026, by the mitochondria lane (D234). The appendix of declared
equations that MT-1's component references are written from. It states each law's physics only.
Three of the source's printed equations fail the thermodynamic check (§1.2, §2 and §4). For each,
the printed and the balanced forms are given, and the user rules on them. Nothing here is
registered.*

**Sources.** D. A. Beard, "A biophysical model of the mitochondrial respiratory system and
oxidative phosphorylation", PLoS Comput Biol 1(4):e36 (2005), doi:10.1371/journal.pcbi.0010036, and
its correction, PLoS Comput Biol 2(1):e8 (2006), doi:10.1371/journal.pcbi.0020008. Both are CC BY.
- "Eq. n" and "Table n" refer to the 2005 PDF, the version of record.
- Every Table 1 value is the 2006 correction's.
- Each was read at the typeset image.
- The mitochondria were isolated from rat heart.

**Words used.**
- **Printed:** an equation exactly as the source prints it, in this note's symbols.
- **Declared:** the form the laws use.
- **Balanced:** a declared form that replaces a printed one which fails the check. It keeps the
  printed forward term, and its backward term follows from the free energy.
- **Declared, uncited:** a value the source does not print. It is ours.

## 0. Conventions

**Sides.** Each law runs across one membrane with two ends.
- **N** is the matrix, the side that is negative at the operating point.
- **P** is the intermembrane space (IMS).
- The source's subscripts are x (matrix), i (IMS) and e (external buffer). Its inner-membrane laws
  use the external H⁺ and K⁺ for the IMS, since it takes these cations to equilibrate across the
  outer membrane. Here every P-side quantity is the IMS's own: [·]_P.

**Potential.** Δψ = φ_P − φ_N, the source's ΔΨ ("outer minus inner"), in mV. It is positive at the
operating point. u = FΔψ/RT.

**Concentrations and activities.**
- Concentrations are in M, moles per litre of that compartment's water.
- Every activity is a = c/(1 M), H⁺ included.
- Water's activity is 1.
- h_N = [H⁺]_N and h_P = [H⁺]_P are free protons.
- ΔG_H = FΔψ + RT ln(h_P/h_N) is the free energy of moving one proton from N to P (Eq. 4).

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
  RT ln(h_N/10⁻⁷ M). §7 converts every value to the 1 M basis.
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
- T = 310.15 K.
- R and F are exact SI: R = N_A k_B and F = N_A e.
- So RT = 2578.7306 J mol⁻¹, F/RT = 0.0374158 mV⁻¹, and RT ln 10⁷ = 41.5642 kJ mol⁻¹.

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
| [HPO₄²⁻] | Phosphate, base form | −2 | N, P | |
| [H₂PO₄⁻] | Phosphate, protonated | −1 | N, P | [H₂PO₄⁻] = h [HPO₄²⁻]/k_dH (Eq. 15) |
| [Pi] | Phosphate, total: [HPO₄²⁻] + [H₂PO₄⁻] | — | N, P | No Mg²⁺ binds phosphate in the source |
| [NAD] | NAD⁺, oxidized | −1 | N | The net charge with the phosphates |
| [NADH] | NADH, reduced | −2 | N | z(NAD) − z(NADH) = +1 is what enters |
| [Q], [QH₂] | Ubiquinone, ubiquinol | 0 | N | In the membrane, counted in matrix volume (Eq. 22) |
| [c³⁺], [c²⁺] | Cytochrome c, oxidized and reduced | +3, +2 | P | The source's labels; only their difference enters |
| [O₂] | Dioxygen | 0 | N | Held at 2.6×10⁻⁵ M in the source's simulations |

## 1. `redox_driven_proton_cycle@1`: respiration

One law for the respiratory complexes. Each complex is a population of it, with its own
stoichiometry, S and parameters. All three pass the check as printed: §1.1–§1.3 declare the
printed forms unchanged, written as J = S (1 − e^x). §1.2 also gives Eq. 24, which fails.

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
- **Balanced (declared):** J = A₂₄ (1 − e^{x/2}), keeping the printed forward term
  A₂₄ = X_C3 φ_Pi exp[−(ΔG°_C3 + 4ΔG_H − 2FΔψ + RT ln([Q]/[QH₂]))/2RT] [c³⁺].
  - It keeps Eq. 7's half affinity, which Eq. 24 replaces term for term.
  - Its backward term is X_C3 φ_Pi [c²⁺] h_N/(10⁻⁷ M).
  - S = A₂₄/(1 + e^{x/2}).
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
- **Reads:** O₂ at N; c²⁺ and c³⁺ at P (and their sum); free h_N and h_P; Δψ.

### 1.4 The lumped quinol-to-oxygen cycle (only for an organelle without its own IMS)

Complexes III and IV taken together, with cytochrome c eliminated. It is needed only if the IMS is
merged with the medium, where cytochrome c has no compartment of its own. The source prints no
kinetics for it, so only its stoichiometry and free energy are declared.

  2 QH₂(N) + O₂(N) + 12 H⁺(N) → 2 Q(N) + 2 H₂O + 12 H⁺(P)

- ν: QH₂ −2, Q +2, O₂ −1, H⁺_N −12, H⁺_P +12.
- Charge moved: q = +12.
- **Free energy:**
  ΔG = ΔG°_QO + RT ln([Q]²/([QH₂]²[O₂])) + 12ΔG_H, with ΔG°_QO = 2(ΔG°_C3 + ΔG°_C4) =
  −310.94 kJ mol⁻¹.
  - The scalar protons of III and IV cancel, so the pH-7 and 1 M values agree.
  - It is the sum of twice §1.2's ΔG and §1.3's: cytochrome c, the scalar protons and the
    electrons' 4FΔψ cancel.

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

**The free-energy entry, derived (declared, uncited).** ΔG°_F = −6.685 kJ mol⁻¹, every species at
1 M (−2.5923 RT).
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

**Balanced (declared):** J = A₁₁ (1 − e^x), keeping the printed forward term
  A₁₁ = X_F1 exp[−(ΔG°_ATP − n_A ΔG_H)/RT] (K_MgADP/K_MgATP) [MgADP⁻][Pi].
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

**Balanced (declared):** J = A₁₆ (1 − e^x), keeping the printed forward term
  A₁₆ = X_PiHt [H₂PO₄⁻]_P h_N/([H₂PO₄⁻]_P + k_PiHt).
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

## 6. `driven_redox_supply@1`: the NADH supply (Eq. 1)

The source's substrate oxidation, which it calls an arbitrary four-parameter function outside its
thermodynamic framework. It is declared as a driven supply, not a cycle.

**Turnover:** NAD(N) → NADH(N) + H⁺(N).
- ν: NAD −1, NADH +1, H⁺_N +1.
- The electrons come from a substrate outside the model.
- Charge: z(NAD) = z(NADH) + z(H⁺), so q = 0, with no membrane leg.

**Flux (Eq. 1, as printed and declared):**
  J = X_DH · [(1 + [Pi]_N/k_Pi,1)/(1 + [Pi]_N/k_Pi,2)] · (r [NAD] − [NADH]).
- [Pi]_N is the total matrix phosphate. k_Pi,1 and k_Pi,2 are printed in mM.
- It relaxes [NADH]/[NAD] toward r. Its sign is not tied to its free energy.

**Energy (declared, uncited).** The supply delivers work at the rate W = J ΔG_DH, with ΔG_DH =
μ̃_NADH + μ̃_H − μ̃_NAD at N from the declared standard potentials. It is signed: positive when it
drives NADH up its potential. It books no heat. The source gives reaction-level standard free
energies only, so the species' own potentials (and with them ΔG_DH's standard part) are declared
with the world.

**Reads:** NAD and NADH at N; total [Pi]_N.

## 7. Parameters and free-energy entries

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
| `K_MgATP` | §2 | 24.0e-6 | 24.0e-6 | M | Table 1 (2006) |
| `K_MgADP` | §2 | 347.0e-6 | 347.0e-6 | M | Table 1 (2006) |
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
| `NAD_tot` | §1.1, §6 | 2.97 | 2.97 | mM | Table 1 (2006) |
| `Q_tot` | §1.1, §1.2 | 1.35 | 1.35 | mM | Table 1 (2006) |
| `cytC_tot` | §1.2, §1.3 | 2.70 | 2.70 | mM | Table 1 (2006) |
| `A_tot` | §2, §3 | 10 | 10 | mM | Table 1 (2006) |
<!-- /parameters -->

- **Also printed:**
  - θ_P = 0.35 and θ_N = 0.65 (Eq. 14);
  - four protons pumped by complexes I and III, two by IV per ½ O₂ (Eqs. 2, 6 and 8).
- **Units in ratios:** a ratio such as [Pi]_N/k_Pi,3 or [H₂PO₄⁻]_P + k_PiHt needs both in one
  unit; the k's printed in mM enter as 10⁻³ k in M.
- **Where the correction changed a value the six laws use:** K_MgATP, K_MgADP, k_dH, k_mADP and
  k_O₂.
  - The 2005 PDF prints 1.0×10⁻⁶ M for each.
  - The correction also changes X_KH with phosphate control (2.9802×10⁻⁶ in 2005) and C_IM, X_AK
    and X_MgA, which no law here uses.

**Free-energy entries** (the standard free energy each law's chemistry must carry, at T =
310.15 K):

| Law | Reaction (base forms, water at activity 1) | Source value | Every species at 1 M | In RT |
| --- | --- | --- | --- | --- |
| §1.1, per NADH | NADH + Q + H⁺ → NAD + QH₂ | −69.37 kJ mol⁻¹ at pH 7 (Table 2) | −110.934 kJ mol⁻¹ | −43.0189 |
| §1.2, per QH₂ | QH₂ + 2 c³⁺ → Q + 2 c²⁺ + 2 H⁺ | −32.53 at pH 7 (Table 2) | +50.599 | +19.6215 |
| §1.3, per O₂ | O₂ + 4 c²⁺ + 4 H⁺ → 4 c³⁺ + 2 H₂O | 2 × (−122.94) at pH 7 (Table 2) | −412.137 | −159.8216 |
| §1.4, per O₂ | 2 QH₂ + O₂ → 2 Q + 2 H₂O | −310.94 (Table 2, summed) | −310.94 | −120.5787 |
| §2, per ATP | ADP³⁻ + HPO₄²⁻ + H⁺ → ATP⁴⁻ + H₂O | +36.03 at pH 7, total Pi (Table 2) | −6.685 (derived, §2) | −2.5923 |
| §3, §4, §5 | Transport only | — | 0 | 0 |
| §6 | Driven; no entry | — | — | — |

- The conversion: the source writes each scalar proton as RT ln(h/10⁻⁷ M), so a reaction that
  produces ν_H scalar protons has ΔG°(1 M) = ΔG°(pH 7) + ν_H RT ln 10⁷.
  - This is exact for §1, whose species bind no proton in the source.
  - §2's conversion is the matched one given there.
- A law's ΔG° holds only where its reaction's species have these potentials. A different
  standard potential for any of them is a departure from the source.

## 8. What the component references check

On a grid of states, and on states placed next to each turnover's equilibrium (|x| from 0 to 3):
- **Grid:** Δψ 0–250 mV; pH_N 6.8–8.2; pH_P 6.5–7.6; the reduced fractions of NAD, Q and
  cytochrome c 0.01–0.99; ATP/ADP 10⁻³–10³ at each end; phosphate 0.1–20 mM; O₂ 10⁻⁴–0.3 mM; free
  Mg²⁺ 0.1–5 mM; K⁺ 10–200 mM.
- **For each declared law:**
  - J, ΔG and their signs: J·ΔG ≤ 0, J = 0 at ΔG = 0, and reversal past it;
  - the static head, the Δψ where ΔG = 0 at fixed concentrations;
  - the charge current's slope q F ∂J/∂Δψ against a finite difference;
  - the one-way flux J⁺ = S at the source's parameters.
- **For each printed law:**
  - its agreement with the declared form where it passes (§1.1, Eq. 7 of §1.2, §1.3, §3, §5);
  - its mismatch d where it fails (Eq. 24, §2 and §4), in the closed forms above.
- **Planted controls**, each of which the check must refuse:
  - a reversed sign in a stoichiometry or in q (complex I with −4u in place of +4u);
  - exchange shares that do not sum to one (θ_P = 0.35, θ_N = 0.60).
- **Arithmetic:** high precision, 50 digits or more. The lane's own check of this appendix runs at
  50 digits and is not independent of it.

## 9. Reading notes on the source

Each was checked at the typeset image of the PDF, not a text layer.
- **Table 1 in the 2005 PDF is the uncorrected table.**
  - Nine values differ from the 2006 correction (§7). So the correction must be read from its
    own article.
  - Table 1 describes V_i as "per total cell volume". With its footnote f (matrix 90%, IMS 10% of
    the water) it reads as per total mitochondrial volume.
- **ΔG°_ATP's sign:** −36.03 in the text under Eq. 11, +36.03 in Table 2 (§2).
- **Eq. 22's matrix proton balance** in the PDF has −(4 + 1) J_C1, −(4 − 2) J_C3, −(2 + 2) J_C4,
  +(n_A − 1) J_F1, +2 J_PiHt, +J_Hle, −J_KH and +J_DH, consistent with Eqs. 2, 6, 8 and 10 and
  with §1–§6 here.
  - The sentence after it says complex III consumes "three" matrix protons and describes complex
    I's reaction. That is a leftover: the printed coefficients are the ones that agree.
  - PLOS's web XML version of Eq. 22 differs from the PDF's; the PDF is the version of record.
- **No temperature, R or F is printed** (§0).

## 10. Not covered here

These are the source's other equations, declared with MT-1's world once its host is ruled:
- the proton leak (Eq. 19) and the passive K⁺ flux (Eq. 20, zero in the source's fits);
- Mg²⁺ binding (Eq. 12), taken at equilibrium here;
- the matrix buffer (Eq. 22's r_buff);
- the outer membrane's permeation (Eq. 13);
- the IMS adenylate kinase (Eqs. 17 and 18);
- the membrane capacitance (Eq. 22).
