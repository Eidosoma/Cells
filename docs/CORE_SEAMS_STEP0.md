# Core seams, step 0: the desk work and the two probes (D195)

*Status: in progress, 17 November 2026, for the lead. Step 0 of the core-seams pass
([CORE_SEAMS_DESIGN.md](CORE_SEAMS_DESIGN.md), approved by D195 with conditions). Branch
`core-seams-step0` from main ef9fc1a8. Docs only in the repository; scratch code, fetched sources
and outputs are in `/mnt/workspaces/Cells/core-seams-step0-20261117/` (cited as `$W`). Each item's
criterion is committed before the item runs; results follow in later commits under each item.
Tags as in the design note: **S** is this note's own derivation, arithmetic or proposal.*

**Engine models** (AGENTS.md): items 1–4 run none. They are D195's desk work for step 0: the
cycle-law screen, the pins against F's extractions, the search for worlds that refusal 4 per move
would newly refuse, and one owner per file. The probes of item 5 name their models in their own
criteria, written before they run.

**What was seen before this commit,** so the criteria can be read against it:
- The sources were fetched and read for orientation: Beard 2005's article XML and its 2006
  correction (PLOS), and O'Hara et al. 2011's article XML and Text S1 (PLOS). Text S1's pages
  12–15 were read as extracted text, and pages 12 and 14 as images. While reading, the exponent
  sums of the printed voltage factors were noticed (2·q_Na + q_Ca for the exchanger; the K_Nai and
  K_Nao exponents for the Na⁺/K⁺ cycle). The criteria below test them; they were not tuned to
  them.
- The planner's pin inventory ran once at ef9fc1a8 without a report (40 live pins on 19 files,
  in 14 pinning modules): the inventory only, no intersection.
- Code read: refusal 4 (`models/operators/compartments.py`), the transporter kind's header, and
  `models/inner_laws.py`.

## 1. The cycle-law screen (D195's condition on seams A and C)

### 1.1 Criterion

**The form under test** (CORE_SEAMS_DESIGN §3.2). For each mode m of a law, an integer
stoichiometric cycle with rows at its two ends:
- the kind computes ΔG_m = Σ ν μ̃ from the registry;
- **A's form:** the law supplies kinetics S_m ≥ 0, and J_m = k·a·S_m·(1 − e^{ΔG_m/RT});
- **the fallback:** the law supplies J_m, and the kind enforces its sign: J_m has the sign of −ΔG_m
  at every state.

**The laws, as printed:**
- O'Hara et al. 2011 (Text S1, with PLOS's correction of 14 September 2011): the Na⁺/Ca²⁺
  exchanger (INaCa, both Y ∈ {i, ss}), the Na⁺/K⁺ cycle (INaK) and the sarcolemmal Ca²⁺ pump
  (IpCa);
- Beard 2005 (PLoS Comput Biol 1:e36), with Table 1 as its 2006 correction (2:e8) gives it:
  complexes I, III and IV, F1F0, the nucleotide exchanger (ANT) and the phosphate carrier (PiHt).

**Reading.**
- Each equation used is read from the source and checked against its typeset image wherever the
  text form is malformed, truncated or doubtful: Text S1's page images; PLOS's equation images for
  Beard.
- A law whose equation cannot be read is stopped there, and the note says so.
- Notation here is ours, with the source's equation or page cited. No source text is copied.

**Modes.** Each law's modes come from its own reaction scheme.
- For a kinetic diagram (INaCa, INaK), every cycle of the diagram (Hill's cycles) is a candidate
  mode, and the independent bases are checked too.
- For a mass-action flux X·(A − B), the one reaction it writes.

**Three tests per mode,** with ΔG_m split into ΔG_m = ΔG°_m + ΔG_stoich,m. ΔG_stoich,m is RT Σ ν ln
c plus F Σ ν z φ, in the source's own concentrations, units, sign conventions and constants.
- **(a) Form.** d_m = ln(Π⁻_m/Π⁺_m) − ΔG_stoich,m/RT over the grid. Π⁺_m and Π⁻_m are the law's
  forward and backward cycle products, or the two mass-action terms.
  - **Factors:** d_m is constant over the grid, shown algebraically and numerically, with a spread
    within 1e-9 in float64. The constant is the law's implied ΔG°_m/RT, reported for seam E's
    check (cardiac C3, mitochondria C2).
  - **Does not factor:** d_m varies. The variable it varies with is reported, with its slope. A
    standard potential cannot absorb a d_m that varies with V or with a concentration.
  - This verdict does not depend on any stand-in for the registry's ATP potential.
- **(b) S ≥ 0,** from the algebraic S (Π⁺_m Σ_m/Σ for a Hill cycle, the forward term for mass
  action), shown non-negative for positive inputs. It is not taken from J/(1 − e^{ΔG/RT}) near
  ΔG = 0.
- **(c) The fallback:** J_m·ΔG_m ≤ 0 at every state of the declared domain grid (§1.2).
  - A violation is J_m·ΔG_m > 0 with |ΔG_m/RT| > 1e-9 and |J_m| above 1e-12 of the mode's
    one-way flux.
  - Reported as **holds identically** (true at every state, as for a law that factors), **holds
    on the domain** (with the wrong-sign window outside it and its margin), or **fails** (with the
    window).

**For INaCa's diagram:** the tests run per Hill cycle, per edge flux (the two parallel branches
between its states 2 and 3), and per two-mode basis. The population's total dissipation, the sum
over cycles of −J·ΔG, is reported beside them. If only the total is sign-definite, A's per-mode
contract needs a change, and the lead hears of it.

**Printed and declared, apart.** Each law is screened as printed, and separately with its notes'
declared departures:
- IpCa with D3's completion by (1 − e^{ΔG/RT}) (cardiac §3.9);
- INaCa with D2's own-flux booking;
- Beard's laws under rapid Mg²⁺ binding (mitochondria D1).

A completion never stands in for the printed verdict.

**Verdicts per law:**
- **FACTORS:** A's contract holds. Any implied ΔG° goes to E's check.
- **FALLBACK:** A's fallback, with the domain the screen used.
- **FAILS:** refused as printed (§3.2: refused, never repaired). The consumer note's conditional
  departure fires, and any change goes to the user through the lead.

### 1.2 The grids (the declared domains)

**O'Hara et al. 2011:** 310 K, with Text S1's own R and F, and again with the engine's exact SI
constants.
- V from −120 to +60 mV, the cardiac note's channel domain.
- **Concentrations, log-uniform (mM):** Na_i 4–20, K_i 120–155, Ca_i (bulk) 2e-5–5e-3, Ca_ss
  2e-5–5e-2. Na_o 140, K_o 5.4 and Ca_o 1.8 are the source's bath.
- **A wider sweep for test (a) only:** Na_o 100–160, K_o 2–10, Ca_o 0.5–3, Na_i 1–40, and the
  INaK cycle's held rows (MgATP 1–10, MgADP 0.01–1, ΣP 0.5–10, H⁺ 1e-5–1e-3).
- **Size:** 20,000 random states per law. For each concentration set, the V where ΔG_m = 0 is also
  added when it lies in the domain, with offsets of ±0.01, ±0.1 and ±1 mV.

**Beard 2005:** the source's temperature and constants as printed.
- ΔΨ 0–250 mV; matrix pH 6.8–8.2 and external pH 6.5–7.6.
- The NADH, QH₂ and reduced cytochrome c fractions 0.01–0.99.
- ATP/ADP 1e-3–1e3 on each side; Pi 0.1–20 mM; O₂ 1e-4–0.3 mM; free Mg²⁺ 0.1–5 mM.
- Each mode's equilibrium neighbourhood, as above.

**The registry stand-in, for test (c) only.** The fallback's sign needs a ΔG for the fuel of
INaK's and IpCa's cycles, and no human cardiac registry exists yet.
- We take FR-4's generic Δ_rG'° = −30.5 kJ/mol (`validation/compartment_ph_engine/parameters.py`)
  at the source's held MgATP, MgADP and ΣP.
- We report the margin: the least negative ΔG_ATP at which the fallback still holds on the domain.
  The verdict is then a condition on the registry's value.

**Numerics:** float64, and mpmath at 50 digits near each equilibrium and for d_m's constancy.

### 1.3 Amendment, committed before the numerical run

Reading Beard's typeset equations showed three things the criterion must say exactly. Nothing was
run between the criterion's commit and this amendment.

- **Laws written per half reaction.** Beard's complexes III and IV (Eqs. 7, 24 and 9) write their
  exponent over 2RT, so ln(Π⁻/Π⁺) = κ·ΔG/RT with a printed κ = ½. Test (a) then reads
  d_m = ln(Π⁻_m/Π⁺_m)/κ_m − ΔG_stoich,m/RT, with κ_m = 1 for every other law. Where d_m is constant,
  A's form holds with S = X·A·(1 − e^{κΔG/RT})/(1 − e^{ΔG/RT}). That S is positive for any κ > 0,
  with the limit κ·X·A at ΔG = 0. The question the test answers is unchanged: does J factor as
  S·(1 − e^{ΔG/RT}) with S ≥ 0?
- **Laws that are not a difference of two products** (Beard's nucleotide exchange, Eq. 14).
  Π⁺ and Π⁻ are the two terms of the flux's numerator over its common denominator.
- **Beard's modes and their ΔG_stoich** come from the printed reactions (Eqs. 2, 6, 8 and 10), with
  ΔH⁺ as the text defines it (a proton moved from the matrix to the cytosol side) and ΔG_H as Eq. 4.
  - The scalar protons sit where the reactions and the text put them: complex III's two in the
    matrix, by the text.
  - The phosphate carrier's mode is the electroneutral H⁺/H₂PO₄⁻ co-transport into the matrix,
    as the text, Table 1 and the matrix proton balance (Eq. 22, +2·J_PiHt) describe it.
- **Complex III's two printed fluxes** are screened separately: Eq. 7, without phosphate control,
  and Eq. 24, with it, which the paper's final fits use.
- **Beard's temperature** is not printed in the text read. T = 310.15 K is used. The verdicts are
  identities in FΔΨ/RT and ln c, so they do not depend on T.

### 1.4 Results

**The verdicts:**

| Law (source) | A's form (test a) | The fallback on the domain (test c) | Verdict |
| --- | --- | --- | --- |
| INaCa (Text S1 pp. 12–14) | Cycle B only. Cycles A and C: d = const − 0.2118·FV/RT | Fails for A and C. The population's total dissipation is also negative at some domain states | **FAILS** |
| INaK (pp. 14–15) | No: d = const − 0.31·FV/RT | Holds against the stand-in, with 0.7 RT of margin | **FALLBACK**, conditional; C3 fires |
| IpCa (p. 16), as printed | No: no back reaction | Holds against the stand-in, with 2.2 RT of margin | **FALLBACK**, conditional |
| IpCa with D3's completion | Yes, S = the printed rate | Holds identically | **FACTORS** |
| Beard complex I (Eq. 3) | Yes, d = ΔG°_C1/RT | Holds identically | **FACTORS** |
| Beard complex III (Eq. 7) | Yes, κ = ½ | Holds identically | **FACTORS** |
| Beard complex III with phosphate control (Eq. 24) | No: d = const − 2 ln([H⁺]_x/10⁻⁷) | Fails | **FAILS** |
| Beard complex IV (Eq. 9) | Yes, κ = ½ | Holds identically | **FACTORS** |
| Beard F1F0 (Eq. 11) | No: d = const + ln([H⁺]_x/10⁻⁷) | Fails near its own zero, where the source holds it | **FAILS** |
| Beard ANT (Eq. 14) | Yes, d = 0 | Holds identically | **FACTORS** |
| Beard PiHt (Eq. 16) | No: d = 2 ln([H⁺]_e/[H⁺]_x) | Fails | **FAILS** |

Each slope in the table was fitted over the grid and matches the algebra to rounding: the residuals
after the fit are 1e-14 to 4e-14. The evidence is `$W/screen/screen.json` and
`$W/screen/screen-extra.json`, from `$W/scripts/cycle_screen.py` and `cycle_screen_extra.py`. Our
own code was written from the printed equations; no model file or author code was read.

**Departures from the criterion as committed.** mpmath is not installed in any project environment.
The 50-digit checks use Python's `decimal` module instead (`$W/scripts/hp.py`); no package was
installed.

**INaCa.** Text S1's exchanger is a four-state diagram. Between states 2 and 3 it has two parallel
branches, (k₃′, k₄′) and (k₃″, k₄″), so it has three cycles:
- **A:** through ′. One Ca²⁺ in, 3 Na⁺ out.
- **B:** through ″. One Ca²⁺ in, 2 Na⁺ out, since the ″ branch carries one Na⁺ in with the Ca²⁺.
- **C:** out by ′ and back by ″. One Na⁺ out: the leak mode.

The printed occupancies are King and Altman's. The edge fluxes rebuilt from them match Hill's
three cycle fluxes to 3e-14, and the printed J_Na and J_Ca equal 3J_A + 2J_B + J_C and −(J_A + J_B).

**The cycle products (S).** In each cycle's product ratio the binding polynomials h₁, h₄, h₇ and h₁₀
cancel:
- Π⁺_A/Π⁻_A = ([Ca]_o[Na]_i³/([Ca]_i[Na]_o³))·h_Na²·h_Ca = e^{−ΔG_A/RT}·e^{(2q_Na + q_Ca − 1)FV/RT};
- Π⁺_B/Π⁻_B = [Ca]_o[Na]_i²/([Ca]_i[Na]_o²) = e^{−ΔG_B/RT}, with no voltage factor, as an
  electroneutral cycle needs;
- Π⁺_C/Π⁻_C = ([Na]_i/[Na]_o)·h_Na²·h_Ca = e^{−ΔG_C/RT}·e^{(2q_Na + q_Ca − 1)FV/RT}.

With the printed q_Na = 0.5224 and q_Ca = 0.1670, 2q_Na + q_Ca = 1.2118, against the net charge of
1 that cycles A and C move. So d_A = d_C = −0.2118·FV/RT (fitted slope −0.21180), and d_B = 0. No
standard potential can absorb that.

**Where the signs go wrong.**
- J_A has the sign of 1.2118·V − E_NCX, but −ΔG_A has the sign of V − E_NCX. So cycle A runs
  against its free energy between E_NCX/1.2118 and E_NCX. At the published diastolic
  E_NCX ≈ −28.5 mV that window is about 5 mV wide, inside the domain.
- Cycle C's window lies between E_Na/1.2118 and E_Na, about 43–52 mV at Na_i 20 mM, also inside.
- 50,449 of 204,407 bulk grid states are wrong-signed for cycle A, with |ΔG_A| up to 0.8 RT.
- At 50 digits, at ±0.01 mV around cycle A's own zero (200 concentration sets), exactly half the
  states run against ΔG_A, as the algebra predicts.
- **The population's total dissipation,** −Σ J_κΔG_κ, is negative at:
  - 5,158 of 240,552 subspace grid states, at V from 42 to 60 mV, worst −0.049 of the one-way
    flux;
  - 1 bulk grid state, at 59.5 mV.
- **ORd's own booking.** Its concentration equations book 3·I_NaCa to Na⁺ and I_NaCa to Ca²⁺, so its
  3:1 mode carries J = I = J_A + J_C. That J is wrong-signed at 20–27% of grid states, across the
  whole domain, with |ΔG_A| up to 5.4 RT.

**Verdict: FAILS as printed.** For cycles A and C neither A's form nor the fallback holds, and not
even the population's total is sign-definite on the domain.
- D2, booking the cycle's own fluxes, does not cure it: the fault is in the cycle's voltage factors.
  The cardiac note's C2 fires.
- **Two changes would make it admissible.** They are listed for the user, through the lead; nothing
  is decided here.
  - **A's form on the three cycles,** S_κ = Π⁺_κΣ_κ/Σ, with the kind's (1 − e^{ΔG_κ/RT}). At the
    published diastolic state (−87.84 mV, Na_i 7.23 mM, Ca_i 8.54e-5 mM) it multiplies cycle A's
    flux by 0.47 and C's by 0.50, and leaves B's unchanged.
  - **Charges that sum to one,** 2q_Na + q_Ca = 1. This changes the law's voltage dependence.

  Either changes the exchanger's current by a large factor, so it is beyond D2's scope.

**A finding about A's contract, not about ORd.** We tested a consistent variant of the same diagram
(q_Ca = 1 − 2q_Na; hypothetical, not a proposal) at 200,000 states:
- Hill's three cycles each factor and keep their signs, and the total dissipation is never
  negative.
- **But every two-mode basis has per-mode sign violations:**
  - {A, B}: 17% and 25% of states;
  - {A, C}: 2.3% and 0.2%;
  - {B, C}: 44% and 12%;
  - the 3:1 booking: 17%.

So in a diagram with more cycles than independent stoichiometries, the per-mode contract of §3.2
holds only if the law's modes are all of Hill's cycles, dependent ones included, each with its own
flux. The exchanger needs three modes, not two. §3.1's line "the Na⁺-leak mode is a second mode"
needs that wording, or the kind's sign check has to be per population. The lead hears of it here.

**INaK.** Text S1's pump is one four-state cycle: E1 →α₃ E2 →α₄ E3 →α₁ E4 →α₂ E1. The printed
J_Na = 3(E1α₃ − E2β₃) and J_K = 2(E4β₁ − E3α₁) fix those edges. One forward turn moves 3 Na⁺ out
and 2 K⁺ in, and turns MgATP into MgADP + P + H⁺.

**The cycle product.**
- Π⁺/Π⁻ carries (K_Nao/K_Nai)³. With K_Nao's printed exponent (1 − Δ)·VF/3RT and Δ = −0.155, that
  makes a voltage factor e^{(1 − 2Δ)FV/RT} = e^{1.31·FV/RT}, against a net charge of 1.
- So d = const − 0.31·FV/RT (fitted slope −0.3100, residual 4e-14). It does not factor at any
  registry.

**C3 fires.**
- The law's own constant (d at V = 0) is −23.16 RT, with concentrations in mM.
- At its held fuel (MgATP 9.8, MgADP 0.05, free P ≈ 2.0, H⁺ 10⁻⁷ mM), the law's own hydrolysis drive
  is −43.9 RT (−113 kJ/mol), against −22.6 RT (−58.2 kJ/mol) for the stand-in.
- E's check would refuse it. C3's remedy, ATP's potentials declared from the cycle, would put an
  unphysical value into the registry that every ATP consumer shares. That is for the user.
- Two observations for the cardiac lane's references:
  - the printed H⁺ of 10⁻⁷ mM (pH 10, as the reader comment notes) and the printed
    K_MgATP = 1.698·10⁻⁷ mM, the same number as K_H,P, make β₃ vanish;
  - the reverse flux is therefore negligible on the whole domain: J/S ≥ 1 − 1e-9.

**The fallback against the stand-in** has no violation on the domain grid.
- The grid's largest ΔG_reg is −0.86 RT (−0.79 RT with the engine's SI constants). At the domain's
  corner itself (V = −120 mV, Na_i 4 mM, K_i 155 mM) it is −0.71 RT, in closed form.
- So it holds with a margin of 0.7 RT, 1.8 kJ/mol, on the registry's ATP potential at the held fuel.
- **The printed x₁** has β₂·β₄·β₃ where King and Altman's spanning tree gives β₁·β₃·β₄. It moves the
  printed fluxes by at most 1.4e-9, since β₃ is negligible. The tree's four edge fluxes agree to
  3e-11.
- A's form, with S = Π⁺/Σ, would change the flux by −2.1% at the published diastolic state.

**Verdict:** FALLBACK on the domain, conditional on the registry's ATP potential. It does not factor,
and C3 fires.

**IpCa.** The printed flux is G_pCa·[Ca]_i/(0.0005 + [Ca]_i), one-way. It does not factor: J ≠ 0 at
ΔG = 0.
- **The fallback** holds on the domain against the stand-in, with one Ca²⁺ out per ATP. The largest ΔG
  is −2.2 RT, at the corner of −120 mV and Ca_i 20 nM (−2.24 RT on the grid, −2.19 RT in closed
  form).
- **With D3's completion** it factors by construction, with S the printed rate. That changes the flux
  by −0.24% at the published diastolic state.

**Beard:**
- **Complex I (Eq. 3).** Mass action, X·(K′[NADH] − [NAD]). Its exponent holds Eq. 2's own terms, so
  ln(Π⁻/Π⁺) = ΔG_C1/RT and d = ΔG°_C1/RT = −26.90. It factors, with S = X·K′·[NADH].
- **Complex III (Eq. 7).** X·(e^{−(…)/2RT}[cyt c³⁺] − [cyt c²⁺]), so ln(Π⁻/Π⁺) = ΔG_C3/2RT
  (κ = ½), and d = ΔG°_C3/RT = −12.62. It factors, with
  S = X·e^{−(…)/2RT}[cyt c³⁺]/(1 + e^{ΔG/2RT}).
- **Complex III with phosphate control (Eq. 24),** the form the paper's final fits use.
  - Its exponent lacks Eq. 7's 2RT ln([H⁺]_x/10⁻⁷): the two matrix protons that the text and Eq. 6
    give each turnover. So d = const − 2 ln([H⁺]_x/10⁻⁷).
  - The law stops where ΔG/RT = 2 ln 10·(7 − pH_x): −5.5 RT at pH 8.2 and +0.9 RT at pH 6.8. So it
    runs uphill, or stalls downhill, next to its own zero.
  - 2,444 of 20,000 grid states are wrong-signed. It fails.
- **Complex IV (Eq. 9):** κ = ½, with a positive prefactor (O₂ saturation and the reduced fraction).
  d = ΔG°_C4/RT = −47.68. It factors.
- **F1F0 (Eq. 11).**
  - Mass action in the Mg-bound forms. With Mg²⁺ binding at equilibrium (D1),
    ln(Π⁻/Π⁺) = (ΔG°_ATP − n_A·ΔG_H)/RT + ln(fATP/(fADP·Pi)).
  - Eq. 10's own reaction consumes one matrix proton, and Eq. 11's exponent omits it. So
    d = ΔG°_ATP/RT + ln([H⁺]_x/10⁻⁷). Kinetic Mg²⁺ binding, as printed, misses the same term.
  - The law's zero sits at ΔG/RT = ln 10·(pH_x − 7): +0.92 RT at pH 7.4.
  - The source holds F1F0 at that zero ("X_F1 large enough"). So at any matrix pH but 7 it runs
    against ΔG next to its operating point. Only 7 random grid states land in that window, but it is
    where the source runs. It fails.
- **ANT (Eq. 14).**
  - J > 0 exactly when ([fADP]_i[fATP]_x/([fADP]_x[fATP]_i))·e^{(0.35 + 0.65)FΔΨ/RT} > 1, which is
    ΔG_ANT < 0, because the shares sum to 1.
  - With Π⁺ = [fADP]_i[fATP]_x·e^{0.65ψ} and Π⁻ = [fADP]_x[fATP]_i·e^{−0.35ψ}, d = 0 exactly. It
    factors.
  - Mitochondria's C1 does not fire.
- **PiHt (Eq. 16),** checked against its typeset image.
  - The numerator is [H₂PO₄⁻]_i[H⁺]_x − [H₂PO₄⁻]_x[H⁺]_e. For the electroneutral co-transport into
    the matrix that the text, Table 1 and Eq. 22 describe,
    ΔG/RT = ln([H₂PO₄⁻]_x[H⁺]_x/([H₂PO₄⁻]_i[H⁺]_e)). So d = 2 ln([H⁺]_e/[H⁺]_x): the proton
    subscripts are the reverse of the co-transport's.
  - No mode, electroneutral or charged, makes d constant.
  - Its zero sits at ΔG/RT = 2 ln 10·(pH_e − pH_x), and 6,968 of 20,000 grid states are
    wrong-signed. It fails.

**What follows for Beard's three failures.** For each, the consistent form is the one A's form
produces with S as the printed forward term, since the kind's ΔG supplies the missing or reversed
proton terms. Each is a departure from the printed equation. It goes on the mitochondria note's list
(§5.4), and to the user before the judged run.

**A reading note for the mitochondria lane's references** (the screen reads the flux laws only).
- Eq. 22's matrix H⁺ balance has −(4 − 1)·J_C1, −(2 + 2)·J_C3 and −(4 − 2)·J_C4.
- Eqs. 2, 6 and 8, with the text, give −5, −2 and −4 matrix protons per turnover.
- F1F0's +(n_A − 1) agrees with Eq. 10.
- The references must settle which is meant, since it fixes the modes' ν.

**What changes for seams A and C:**
- **A's form holds** for complexes I, III (Eq. 7) and IV, the ANT, IpCa with D3's completion, and
  INaCa's cycle B alone. INaK and the printed IpCa need the fallback.
- **Every law that fails** does so through a voltage or proton coefficient that no standard potential
  can absorb. Under A's contract each one is refused as printed. Admitting it takes a departure the
  user rules on:
  - the cardiac C2 for the exchanger, and C3 for the Na⁺/K⁺ pump's implied ΔG°;
  - for Beard, new entries beside mitochondria's C1 and C2, for Eqs. 24, 11 and 16.
- **Seam C's design is unchanged by the screen.** The screened laws read free or bound forms: F1F0
  Mg-bound, the ANT Mg-free, PiHt H₂PO₄⁻. Under the closure's rapid binding (D1), their zeros are
  those of the free-form modes, as shown for F1F0 above. What C must carry is the ligand forms these
  laws read.
- **The contract change, for the lead:** a law's modes are all the cycles of its diagram (above).

## 2. The pin check for F

### 2.1 Criterion

**The run.** `scripts/source_moves_plan.py pins --out DIR --report R`, from this branch's worktree
at ef9fc1a8 with `PYTHONPATH=src:.`, once per set. Each set is written as a synthetic scan report,
`{"report": {"moved": [], "files": [...]}}`, in today's paths.

**Set F, F's extraction list (§8.2), by a rule:**
1. every module that defines a kernel function or class that a declaration in `models/inner_laws.py`'s
   tables, or a kind's law tuple, calls or names. These are found from the declaring modules'
   imports and their call sites;
2. the defining modules of the passive route laws' kernels, as named in `ROUTE_LAWS`' basis;
3. `models/inner_laws.py`, whose central tables leave, and `models/operators/__init__.py`, the
   operators' registration.

**Set G, the files the `cells.modules` guard (§8.5) would rewrite:** every module that move 2's
draft maps into `cells.kinds.*` or `cells.laws.*` and that imports a `cells` module. The draft is
the moves note's, `plan-fa19d80c/move2-draft.json`; where it differs from the move-2 owner's
regeneration at ef9fc1a8, read without editing, the difference is flagged.

**Findings:**
1. a live pin whose pinned file is in the set (`pins_whose_file_is_touched`);
2. a pinning module in the set (`pinning_modules_touched`);
3. one of the six files that must keep their bytes in the set (SOURCE_LAYOUT_MOVES_DESIGN §17
   item 2): `processes/electrochemistry.py`, `numerics/fixed_step.py`,
   `numerics/extracellular_field.py`, `cells/__init__.py`, `numerics/__init__.py` and
   `processes/__init__.py`;
4. a law kernel defined in a file that must keep its bytes, since an extraction that re-imports
   would edit that file;
5. a live pinning or pinned module among move 2's unplaced modules, since placing one under
   `laws/` would make it a guard target;
6. the inventory's drift from the moves note's 43 pins on 22 files, recorded.

**Pass:** none of findings 1–5.

### 2.2 Results

The evidence is in `$W/pins/`: the sets and their rule's output (`sets-ef9fc1a8/`), the planner's
four runs (`run-set-F/`, `run-set-Fplus/`, `run-set-G/`, `run-planted/`), and the script
`$W/scripts/pin_sets.py`.

**The inventory at ef9fc1a8:** 40 live pins on 19 files, held by 14 pinning modules, 23 of them
keyed by path.
- The moves note counted 43 on 22 at fa19d80c.
- The 3 files that dropped out are those move 1 rewrote, whose pins went stale as its §16.3
  predicted: `stable_seed_{partition_physiology_bridge,explicit_ecm_partition,control_volume_physical_bridge}.py`.
- None was added.

**The two sets:**
- **Set F, by the rule:** 17 files. These are the kernel modules the declarations name:
  - `processes/{voltage_gates,potassium_channels,sodium_channels,junction_gate,kinetic_pump,calcium_atpase,atp_transporter,proton_pump,proton_leak,passive_permeation,rapid_proton_buffer,ph_condition,patch_damage}.py`;
  - `coupling/selective.py`;
  - `numerics/surface_transport.py`;

  with `models/inner_laws.py` and `models/operators/__init__.py`. Adding the calcium pump's
  delegated kernels, `er_calcium.py` and `plasma_calcium.py`, makes 19 (set F+).
- **Set G:** 32 files. The two move-2 drafts map the same modules into `kinds/` and `laws/`, except
  R3's `kinetic_pump_binding`, which exists only from ef9fc1a8 on.

**The findings:**
1. **Pins in set F: 3,** all on `numerics/surface_transport.py`. That module holds `transport`, the
   face route law's flux.
   - They are held by `legacy/core/conservative_polygon_tissue_preparation.py` and
     `legacy/processes/stable_seed_partition_{advance,physiology_bridge}.py`.
   - No green test is behind them: the moves note's §16.3 lists those tests as red or retired.
   - Move 2's draft already rewrites `surface_transport.py`, since it imports `coupling.selective`,
     which move 2 moves. So the pins are stale after move 2 whatever F does.
   - The consequence for F: nothing is extracted from `surface_transport.py`. The face law's
     declaration names its kernel there.
2. **Pinning modules in either set:** none.
3. **The six byte-kept files:** none in either set.
4. **Law kernels in byte-kept files,** reached from the declarations:
   - `numerics/extracellular_field.logmean`, the face law's mean;
   - `processes/electrochemistry`'s `ghk_leak` (the proton leak's flux), `bernoulli` and
     `electrochemical_potential`, with R, F, `CHARGE_PER_FMOL` and `MOL_PER_FMOL`.

   A P2-style extraction of any of these would edit a byte-kept file and turn
   `test_charged_surface_repository.py` red, since no hash is updated (D187). So they stay where
   they are: the law modules, and the surface, import them.
5. **Move 2's unplaced modules hold the geometry cluster.**
   - **Pinned files (5):** `conservative_polygon_geometry`, `stable_geometry_primitives` and
     `stable_mesh_{metric_reconstruction,operator_reconstruction_algebra,physical_reconstruction}`.
   - **Pinning modules (4):** `conservative_polygon_geometry`, `fixed_polygon_removal` and
     `stable_mesh_{metric,operator}_reconstruction`.
   - **The pins are module pins, checked at call time.** `fixed_polygon_removal` compares the hashes
     of the modules it imports.
   - **Green tier-1 tests sit behind them:** `test_fixed_polygon_removal.py` (2 passed),
     `test_stable_geometry_primitives.py` (84), `test_stable_mesh_metric_saved_domains.py` (22) and
     `test_stable_mesh_physical_reconstruction.py` (33).
   - **Any placement makes the pins stale.** The modules import each other by `cells.processes`
     paths, so any placement that moves them rewrites those imports. Placed under `laws/`, the guard
     would rewrite them too.
   - **For move 2's owner and the lead:** the cluster stays in `processes/`, outside the guard's
     scope, as the regenerated draft leaves it.
6. **The planted control has teeth.** Adding `electrochemistry.py` and `extracellular_field.py` to
   set F+ makes the planner report 10 touched pins, `charged_surface_work`'s two among them.

**A finding about the guard's scope (§8.5).** Set G's 32 files hold 40 imports between kinds/ and
laws/ modules:
- catalogues importing gate kernels;
- the calcium pump importing `er_calcium` and `plasma_calcium`;
- each kind importing its laws.

They also import core modules the surface does not list: `species_registry` in the transporter and
the proton buffer, and `calcium_gates` in `cav_channels`.

Read literally, "built-ins import only the surface" would put every shared law kernel into the
stable surface. **Proposed for the F owner:**
- the guard admits imports within `laws/`, and from a kind to `laws/`, and refuses every other
  import that is not from `cells.modules`;
- the surface lists what kinds need from the core, such as the registry's potential readers.

**Verdict:**
- **Set G passes.**
- **Set F passes with one exclusion rule:** nothing is extracted from `surface_transport.py`,
  `electrochemistry.py` or `extracellular_field.py`, and declarations name those kernels where they
  are. With it, F's per-law extractions and the guard touch no live pin that has a green test behind
  it.
- **On move 2:** the geometry cluster's placement is a condition.

## 3. The refusal-4 search

### 3.1 Criterion

**Scope:** main ef9fc1a8's `validation/`, `configs/` and `examples/`.

**Candidates:**
- files naming `cell_owned_compartments@1`;
- files using the operator's `LAW_ID`;
- files declaring a kind's model key (`transporters`, the passive routes', the proton buffer's, the
  factor kinds');

in JSON or Python.

**Per candidate world:**
- Build the definition host-side, calling a Python builder or loading the JSON, and parse it with
  the engine. Nothing is stepped.
- Read each declared kind's `moved_rows` (species, node, law), each compartment's node and
  bounding patch, and each row's valence.

**The rule (version 1.3, CORE_SEAMS_DESIGN §4.4).** Every move at a compartment's node or across its
bounding patch needs a term from its law:
- a charged row, a `stage_term` contribution;
- a neutral row, a `material_term` or a `bound_rate`.

A stage read declares its rows. A source kind, with no moves, is admitted.

**Each law's terms** are read from the kinds' hooks on main, cited by file and line.

**Evaluated twice:**
- (i) with the terms as on main;
- (ii) with D4's material term (core-fixes 0a00ba6e) declared for the transporter's neutral law.

**Finding:** any world newly refused under (i) or (ii), named with its law and row. Tests that
assert a version-1.2 admission that version 1.3 changes are out of scope, and are reported
separately.

### 3.2 Results

The evidence is `$W/refusal4/search-ef9fc1a8.json`, from `$W/scripts/refusal4_search.py`.

**The candidates.** Six files name the compartments operator; `examples/` has none:
- `validation/compartment_ph_engine/definitions.py`;
- the two protocols `validation/compartment_ph/protocols/fr{4_acidification,5_transfer}_v1.json`,
  whose worlds are that file's builders;
- `validation/tissue/{composition_matrix,compartment_fixtures,compartment_ph_protocol}.py`.

Of these, only FR-4's and FR-5's builders declare kinds beside a compartment. The fixtures' planted
route is @3's own constant-field permeability, which version 1.3 leaves under version 1.2's rule.
The composition matrix pairs operators, and the protocol module derives criteria.

**The worlds parsed:** 27 definitions.
- FR-4's raw definition, its development world and its declared world.
- FR-5's arms T and R, each under its three controls, in each of its four forms.

**Parsed as the composite:** the 7 declared worlds that hold a compartment. In each, the parsed
`moved_rows` equal the rows read statically from the definition.

**Not parsed with a compartment:**
- the raw definitions, whose `operators` key @3 alone refuses;
- `today_only` of a declared world, which drops the operators.

**The moves at the compartment** (FR-5's arm R, the fullest world):

| Mover | Law | Row | Charged | Its terms on main |
| --- | --- | --- | --- | --- |
| The pump | `proton_atp_mass_action_positive@1` | H, both ends | yes | `stage_term` (`transporter.py`:592), `bound_rate` (:413) |
| The leak and the damage pore | `proton_constant_field_leak@1` | H | yes | `stage_term` (`passive_routes.py`:480) |
| The cargo route and the cargo pore | `passive_neutral_permeation@1` | X | no | `bound_rate` (`passive_routes.py`:499) |

**Result: no world is newly refused,** with the terms as on main and with D4's term added. No saved
or registered world puts the transporter's neutral law, the one law with no term, beside a
compartment.

**Out of scope, reported:** `tests/unit/test_cell_owned_compartments.py` asserts version 1.2's lists
at lines 463, 494–496, 525, 603 and 613–632, the last of these the test of the lists' premise.
Version 1.3 removes the lists, so those tests change with B1. They are in the operators owner's
row of §4.

## 4. One owner per file

### 4.1 Criterion

**The files.** Every file the pass edits or creates is enumerated, from §2–§9's text and §13's
table, at its post-move-2 path (§2's draft, with differences flagged).

**The owners.** Each file gets exactly one owner for the whole pass.
- A script checks uniqueness and coverage: every enumerated file has one owner, and no file has
  two.
- **At most seven agents** (D171, D195), counting:
  - the FR owner;
  - the references agent;
  - the operators owner, who does composition's M1–M5 first, then B1 (D195);
  - the F owner the lead started on `core-seams-f`. Its files are given: the law template's
    types, `registry/laws.py`, the operators' registration section, `src/cells/modules/`,
    `KindRates`' move, and F's edits to `models/inner_laws.py` and to the kinds' registry.
- **F's per-law extractions and the built-ins' import guard** stay unassigned until item 2
  reports.
- **The note says who lands core-fixes across move 2,** since that merge touches several owners'
  files.

**The estimate.** The elapsed time is re-derived from the table:
- the dependencies of §13, with composition's M1–M5 estimate read from its design note (§14 there);
- the critical path named;
- labelled as this note's (**S**).

### 4.2 Results: the owner table (a proposal for the lead)

The evidence is `$W/owners/owners.json`, from `$W/scripts/owner_check.py`.
- **The check:** 78 rows, files or named groups. No file has two owners, and no row repeats. There
  are 7 agents, and every file the design note names is in the table. A planted duplicate fails it.
- **Paths:** the moves note's draft (fa19d80c) and the move-2 owner's regeneration (ef9fc1a8) agree
  on every path in the table.
  - The drafts differ only elsewhere. The older one still moves five specs that move 1 has since
    put in `legacy/`; the newer adds `blas_threads`, `kinetic_pump_spec`, `rate_junction_spec` and
    `kinetic_pump_binding`.
  - **Not decided by the regeneration as read:** the newer one counts `legacy/` among its unplaced
    modules (367).

**The seven agents and their files** (post-move-2 paths under `src/cells/`; tests go with the
module they test):

| Agent | Files for the whole pass | Its work in the pass |
| --- | --- | --- |
| **F owner** (`core-seams-f`, given) | `registry/laws.py` (new), `registry/kind_registry.py`, `modules/__init__.py` (new), `models/inner_laws.py`, `operators/__init__.py`. In `laws/`: `channels/{voltage_gates,potassium_channels,sodium_channels}`, the 12 catalogues (the guard's import rewrite only), `junctions/{junction_gate,selective}`, `pumps/{kinetic_pump,kinetic_pump_binding,calcium_atpase}`, `reactions/{er_calcium,plasma_calcium,ph_condition}`, `routes/{passive_permeation,k_anion_symport}`, `transport/{proton_leak,patch_damage}`, and the new per-law and route-law modules. The guard test; `docs/MODULE_SYSTEM_DESIGN.md` | F whole: the template, the law registry, the surface, `KindRates`, the operators' section, the per-law extractions and the guard (item 2 clears them under its exclusion rule). The kind contract's hooks that B, D and E add, on their owners' requests |
| **@3 owner** (core owner 2 in §13's terms) | `models/surface_pump_v3.py`, `definitions/surface_pump_v3_spec.py`, `definitions/surface_kinetic_spec.py`, `records/run_view.py`, `docs/RUN_VIEW_DESIGN.md`, `docs/INNER_MODEL_V4_DESIGN.md` | The host table (A's prerequisite); D; B1's @3 part (the door into @3, gating by host activity, which composition's M5 needs as its Q1, and @3's field roles); E's moiety `ledger_lists`; `KindRates`' re-import line; G and D's run-view part; branch X |
| **Kinds owner** | `kinds/{transporter,passive_routes,ph_condition,patch_damage,__init__}.py`, `laws/pumps/{proton_pump,atp_transporter}.py` and any new cycle-law module | A (A3's two layouts and its first two laws); B1's kind-side roles; B2; G's kind-side fix; E's moved-row terms; the guard's imports in its files |
| **Binding owner** (new; C was core owner 2's in §13) | `kinds/proton_buffer.py`, `laws/reactions/rapid_proton_buffer.py`, the new multi-ligand closure module, `registry/species_registry.py` | C; E's reaction-level potentials check; E's moieties in the registry |
| **Operators owner** | `operators/{contract,partition,compartments,species_reactions,osmotic_water,species_turnover,membrane_insertion_v2,membrane_state}.py`, `models/pump_composite{,_adapter}.py`, `tests/unit/test_cell_owned_compartments.py`, `docs/OPERATOR_COMPOSITION_DESIGN.md`, `docs/CLOSED_COMPARTMENT_DESIGN.md` | Composition's M1–M5 first, then B1's operator part (lifecycle by roles, refusal 4 per move, the composite's refusal lifted for kinds with roles), D's declared energy roles and E's hook in `contract.py` |
| **References agent** | `validation/core_seams/` (new), composition's references | A's and C's independent references, then composition's |
| **FR owner** | `validation/compartment_ph_engine/` and the FR protocols: no file of the pass | FR-4 and FR-5. A3 keeps their programs |

**How the four known overlaps resolve:**
1. **`models/surface_pump_v3.py`:** the @3 owner alone, for D, B1's @3 part, E's moiety ledgers and
   the host table. `KindRates`' move is a hand-off:
   - the F owner puts the class in the kind contract;
   - the @3 owner replaces its definition with the import, in the same merge window.
2. **`registry/`, by file:**
   - `laws.py` and `kind_registry.py` go to the F owner. The B (roles API), D (mover classes'
     bookings) and E (`standard_free_energies`) hooks in `kind_registry.py` are F's work, on their
     owners' requests.
   - `species_registry.py` goes to the binding owner, for C's forms, E's check and the moieties.
3. **`laws/`, by file:** the F owner extracts and declares @3's laws and the passive laws. The kinds
   owner holds the transporter's two laws, and the binding owner the closure's. Each owner rewrites
   the guard's imports in its own files.
4. **`operators/contract.py`:** the operators owner, for composition's C1–C6, B's `CLOSES`, D's
   declared energy roles and E's operator hook.

**Further hand-offs:**
- **New operator modules.** Composition's new operator versions (such as turnover@2) join through
  the F owner's `operators/__init__.py`, or F's section is built so that a new operator module needs
  no edit there.
- **The lead lands core-fixes across move 2** before the owners branch: one integration merge, not
  authoring, so no owner's file is touched twice. It brings D3 and D4 (ff5ca5ff, 0a00ba6e) and G's
  item 1 (9b0d8baa).
- **The lead also owns** `validation/tissue/composite_crossrev.py` (one world per landed seam),
  `tests/test_tiers.json` and the design note's amendments.

**The estimate (S), re-derived from the table.** In agent-days, from §13's figures and composition's
§14. My splits are marked.
- **F owner:**
  - F's registry, template, surface and operators' section: 1.5–2.5;
  - the kind contract's hooks for B, D and E: 0.5–1 (my split from those seams);
  - the extractions and the guard: 1.5–2;
  - done by day 3.5–5.5.
- **@3 owner:**
  - the host table: 0.5–1 (my split from A);
  - D: 1–2;
  - B1's @3 part: 1–2 (my split of B1's 2–4);
  - G with D's run-view part: 0.75–1.25;
  - moiety ledgers: 0.25, after A;
  - done by day 3.5–6.5, or 5.5–9.5 with branch X.
- **Kinds owner:**
  - waits for F's registry and the host table: day 1.5–2.5;
  - A: 4–5.5;
  - B1's kind-side roles: 0.5–1;
  - A is done by day 5.5–8.
- **Binding owner:**
  - registry forms: 0.5–1;
  - the closure: 2.5–4;
  - E's check: 0.5–0.75;
  - moieties: 0.25–0.5;
  - done by day 3.75–6.25.
- **Operators owner:**
  - composition's M1–M5 in series: 2.5–3.5, 2–2.5, 2–2.5, 3–4 and 2.5–3, so 12–15.5. M5 needs the
    @3 owner's gating by host activity, ready by day 2.5–5;
  - then B1's operator part and the hooks: 1.25–2.5;
  - done by day 13.25–18.
- **Kinds owner's B2**, after B1's operator part: 1–1.5, done by day 14.25–19.5.
- **The final gates:** 1.
- **The references agent:** 2–3 for A's and C's references from about day 3, then composition's 4–5
  in parallel with M2–M5. It fits inside the window.

**The totals:**
- **Elapsed: about 15–21 working days after move 2,** plus 0.25–0.5 for the carry-over, against the
  design's 9–13.
- **The critical path** is the operators owner's composition M1–M5, then B1's operator part, then
  B2, then the gates. It follows from D195's ordering: one operators owner, M1–M5 first.
- **Everything except B2 and B1's operator part** lands by day 6–9.5.
- **Effort:** about 20.5–33 agent-days for the pass, plus 2–3 on branch X. That is §13's 20–31.5,
  plus 0.5–1 for the hand-offs to the kind contract. Composition's own 12–15.5 and its references
  are composition's, as before.

**When each consumer is unblocked** (day after move 2):

| Consumer | Needs | Day |
| --- | --- | --- |
| GARD's G1 | F's registry and surface | about 2–2.5 |
| Cardiac H1 | D, and F's template and registry | about 3–5.5 |
| Finite fuel | A, E | about 6–8 |
| Cardiac H2 | A, the door (B1's @3 part), C, F | about 6–8 |
| Mitochondria's M1 | A, C, D, B's refusal 4, F | about 14–18; about 6–8 under option (a) |
| Composition's M6 | B2 | about 14–19.5 |

**Options for the lead** (S):
- **(a) Refusal 4 per move first.** `operators/compartments.py` and its test are not among composition's
  M1–M5 files. The operators owner can land refusal 4 per move, about half a day, before composition's
  M1. That unblocks mitochondria's M1 about eight days earlier, and moves composition by half a day.
- **(b) Accept B last.** Only composition's M6 needs B2.
- **(c) A second operators owner** does not fit within seven. One could take composition's M2 only
  if its files are disjoint from the operators owner's other files, which this note did not check
  file by file.

## 5. The probes (criteria follow, before they run)

The cardiac booking probe and mitochondria's P1 (CORE_SEAMS_DESIGN §6.4), in scratch only, after
items 1–4.
