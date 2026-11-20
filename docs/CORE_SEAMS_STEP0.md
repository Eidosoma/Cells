# Core seams, step 0: the desk work and the two probes (D195)

*Status: 17 November 2026, for the lead. Items 1–4 are done, and the booking probe is done
(§6.1). P1 is handed off un-run, with its criterion committed (§5.2 and its two amendments): see
§6.2. This is step 0 of the core-seams pass
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
- Code read: refusal 4 (`operators/compartments.py`), the transporter kind's header, and
  `models/inner_laws.py`.

## 1. The cycle-law screen (D195's condition on seams A and C)

**The scope of every verdict below.**
- Each verdict is about a law **as printed**, tested against **seam A's contract** (thermodynamics
  in the kind, kinetics in the law), in **our reading** of the printed equations.
- A verdict is not a claim about the authors' own simulations or code, which may differ from the
  print.
- The results that change the design are the exchanger's charge sum, with its negative total
  dissipation, and Beard's Eqs. 11, 16 and 24. An independent check of them is under way
  (17 November). Seam A's contract is amended only after it reports.

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

Reading Beard's typeset equations showed what the criterion must say exactly.

**Provenance:**
- No part of item 1's screen ran between the criterion's commit and this amendment. Items 2 and 3
  ran in between.
- Before this amendment fixed Beard's modes, his equation images had been read, and so had Text S1's
  pages 13 and 15.

**What the criterion now says:**
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

**Departures from the criterion as committed, and what was run late.**
- **mpmath** is not installed in any project environment. The 50-digit checks use Python's `decimal`
  module instead (`$W/scripts/hp.py`); no package was installed.
- **The wider sweep for test (a)** was left out of the first run, which fixed the bath and INaK's held
  rows. It ran afterwards (`$W/scripts/cycle_screen_wide.py`, `$W/screen/screen-wide.json`), with
  Na_o 100–160, K_o 2–10, Ca_o 0.5–3 and Na_i 1–40 mM, and INaK's held rows varied:
  - INaCa's cycles A and C keep the slope −0.2118 (residual 2e-14), and B still factors;
  - INaK keeps −0.31 (residual 3e-14), so its held rows enter as mass action and only V moves d.
- **The counts below come from a grid enriched around each mode's zero.** On the 20,000 uniform
  states alone, which are fractions of the domain:
  - cycle A is wrong-signed at 3.4% (bulk) and 2.9% (subspace) of the domain, and C at 1.9% and 1.8%;
  - ORd's 3:1 booking is wrong-signed at 21% and 15%;
  - the total dissipation is negative at 0 and 31 (0.16%) states.
- **IpCa's page (p. 16)** was rendered and read after the run. It matches the screened form.

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
- On the grid enriched around the zeros, 50,449 of 204,407 bulk states are wrong-signed for cycle
  A, with |ΔG_A| up to 0.8 RT. On the uniform domain, 3.4% are.
- At 50 digits, at ±0.01 mV around cycle A's own zero (200 concentration sets), exactly half the
  states run against ΔG_A, as the algebra predicts.
- **The population's total dissipation,** −Σ J_κΔG_κ, is negative at:
  - 5,158 of 240,552 enriched subspace states, at V from 42 to 60 mV, worst −0.049 of the one-way
    flux; 31 of the 20,000 uniform ones (0.16%);
  - 1 enriched bulk state, at 59.5 mV.
- **ORd's own booking.** Its concentration equations book 3·I_NaCa to Na⁺ and I_NaCa to Ca²⁺, so its
  3:1 mode carries J = I = J_A + J_C. That J is wrong-signed at 15–21% of the uniform domain, across
  all of V, with |ΔG_A| up to 5.4 RT.

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
  - **For the cardiac lane:** its note records the reader comment's slip as "a β₂ that should be
    β₃". This derivation finds β₂ in place of β₁. The references should settle which.
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
  - **This verdict assumes the registry carries the matrix proton explicitly,** as mitochondria §1.3
    proposes with its base-form rows. With FR-4's transformed rows at a reference pH, the missing
    term would become part of the fuel's pH band instead.
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
3. `models/inner_laws.py`, whose central tables leave, and `operators/__init__.py`, the
   operators' registration.

**Set G, the files the `cells.modules` guard (§8.5) would rewrite:** every module that move 2's
draft maps into `cells.kinds.*` or `cells.laws.*` and that imports a `cells` module. The draft is
the moves note's, `plan-fa19d80c/move2-draft.json`; where it differs from the move-2 owner's
regeneration at ef9fc1a8, read without editing, the difference is flagged.

**Findings:**
1. a live pin whose pinned file is in the set (`pins_whose_file_is_touched`);
2. a pinning module in the set (`pinning_modules_touched`);
3. one of the six files that must keep their bytes in the set (SOURCE_LAYOUT_MOVES_DESIGN §17
   item 2): `laws/electrochemistry.py`, `numerics/fixed_step.py`,
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
five runs (`run-set-F/`, `run-set-Fplus/`, `run-set-G/`, `run-planted/`, `run-set-Fexcl/`), and the script
`$W/scripts/pin_sets.py`.

**The inventory at ef9fc1a8:** 40 live pins on 19 files, held by 14 pinning modules. 23 of the
pins are keyed by path.
- The moves note counted 43 on 22 at fa19d80c.
- The 3 files that dropped out are those move 1 rewrote, whose pins went stale as its §16.3
  predicted: `stable_seed_{partition_physiology_bridge,explicit_ecm_partition,control_volume_physical_bridge}.py`.
- None was added.

**The two sets:**
- **Set F, by the rule:** 17 files. These are the kernel modules the declarations name:
  - `processes/{voltage_gates,potassium_channels,sodium_channels,junction_gate,kinetic_pump,calcium_atpase,atp_transporter,proton_pump,proton_leak,passive_permeation,rapid_proton_buffer,ph_condition,patch_damage}.py`;
  - `laws/junctions/selective.py`;
  - `numerics/surface_transport.py`;

  with `models/inner_laws.py` and `operators/__init__.py`. Adding the calcium pump's
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
   - **Green tier-1 tests may sit behind them:** `test_fixed_polygon_removal.py` (2 passed),
     `test_stable_geometry_primitives.py` (84), `test_stable_mesh_metric_saved_domains.py` (22) and
     `test_stable_mesh_physical_reconstruction.py` (33), all green in the tier record. That a stale
     pin would turn them red is inferred from one call site; it was not run.
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

**Verdict.**
- **By its own criterion, item 2 does not pass:** findings 1, 4 and 5 hold. Set G alone is clean.
- **Set F is clean under one exclusion rule:** nothing is extracted from `surface_transport.py`,
  `electrochemistry.py` or `extracellular_field.py`, and declarations name those kernels where they
  are.
  - The planner, rerun on set F+ without `surface_transport.py` (18 files, `run-set-Fexcl/`),
    reports 0 touched pins.
  - So under that rule, F's per-law extractions and the guard touch no live pin.
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

**The worlds the FR drivers derive.** These were judged afterwards (`$W/scripts/refusal4_derived.py`,
`$W/refusal4/derived-ef9fc1a8.json`): 34 definitions.
- `dt_study`'s FR-4 rungs, and its rungs of FR-4's P_K = 0 control.
- Its FR-5 rungs, for both arms under every control.
- The delivery world. It holds a compartment and D152's reactions, and no kind.

None is refused. Three other kinds of driver need no separate pass:
- the other drivers (`refusal_paths`, `world_agreement`, `compartment_ph_qualification`, the window
  probes) build from the same two builders with other steps, starts or controls;
- the window probes use development worlds, which hold no compartment;
- K2's planted control (`planted.py`) replaces the transporter's hooks under its own kind ID and
  law ID, so its moves and laws are the declared world's.

A grep of `validation/`, `configs/` and `examples/` for the transporter's law constants
(`atp_transporter`, `neutral.LAW_ID`, `NEUTRAL_LAW`, `PUMP_LAW`, the `transporters` key) finds no
other world: outside `definitions.py` the hits are the older families' `cotransporters` and BETSE's
own names.

**Result: no world is newly refused,** with the terms as on main and with D4's term added. That covers
61 definitions. No saved or registered world puts the transporter's neutral law, the one law with no
term, beside a compartment.
- **A note for B1's design.** Version 1.3 reads each law's terms from the law registry, by law ID. A
  planted variant such as K2's reuses a law ID, so it is admitted on the law's declaration, not on
  its own hooks. K2's variant does supply its `stage_term`. The check should still confirm that the
  kind has the hook the law declares.

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
- **Coverage against the design note itself.** The 62 paths named in its §1–§13 were mapped through
  move 2's draft and diffed against the table (`$W/scripts/owner_coverage.py`,
  `$W/owners/coverage.json`).
  - **49 are in the table.**
  - **One bare name, `ph_condition.py`,** matches both the kind and the law. The note's use (:217) is
    the kind's, which is in the table.
  - **The other 12 are named, not edited by the pass:**
    - the dispatch points that R1 changed in move 1: `__main__.py`, `execution/schedule.py`,
      `definitions/specs.py`, `registry/models.py` and `legacy/registration.py`. §8.4 designs the
      models table but does not build it;
    - the byte-kept files: `processes/{electrochemistry,__init__}.py` and
      `numerics/{extracellular_field,fixed_step}.py`. The surface imports from them;
    - `operators/species_regulated_availability.py`, whose factors stay held (§4.3).
- **Paths:** the moves note's draft (fa19d80c) and the move-2 owner's regeneration (ef9fc1a8) agree
  on 43 of the table's 44 module paths, checked by script. The 44th, `laws/pumps/kinetic_pump_binding.py`,
  is only in the newer draft, since R3 created the module after fa19d80c.
  - Elsewhere, the older draft still moves five specs that move 1 has since put in `legacy/`. The
    newer one adds `blas_threads`, `kinetic_pump_spec` and `rate_junction_spec`.
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

**Three readings of the lead's message are this note's own:**
- **The F owner is counted inside the seven.** If the user's "one more agent building the core" means
  an eighth, option (c) below reopens.
- **"F's edits to the kinds' registry"** is read as owning `registry/kind_registry.py` whole.
- **F's per-law extractions and the guard** are proposed for the F owner on item 2's result. They are
  not given.

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

## 5. The probes (CORE_SEAMS_DESIGN §6.4), in scratch

Both run on main ef9fc1a8's code, from this branch's worktree, with FR builders and fixtures imported
read-only. Scratch code goes in `$W/probes/`.
- **Where they run:** before 15:00 UTC only on CPUs 0–3 under `locks/gate-cores-0-3.lock`, and only if
  short with JIT included; after it, on CPUs 6, 7, 22 and 23.
- **Anything over a few minutes** goes through `scripts/run_detached.sh`.

### 5.1 The booking probe: criterion

**Engine models:** `resolved_pump_tissue@3` with `kleak_always_open@1` and `naleak_always_open@1`,
under ARS(2,2,2) (`imex_ars222_face_electromigration@1`).

**The world:** one heredity-sized cell facing its held bath, from
`surface_pump_v3_fixtures.heredity_cells`, with its pump and its gated populations removed. Two leak
populations sit on its one patch:
- a K⁺ leak;
- a Na⁺ leak.

Their permeabilities put the rest potential about 20 mV above E_K.

**The driving current is the Na⁺ leak's, not an injected one,** a declared departure from §6.4's
wording. It keeps the probe on @3 alone; the composite's electrode would add its own routes and
carriers. The mechanism tested is the same: a K⁺ population whose current crosses its reversal
within a step.

**Two arms:**
- **The crossing arm:** V starts 15 mV below E_K and relaxes through E_K to rest.
- **The control:** V starts between E_K and rest and relaxes to rest without crossing E_K, at the
  same steps. The K⁺ power then falls by less than 59% per step.

**The ladder:** dt·G/C of 0.003, 0.01, 0.03, 0.1, 0.3 and 0.6.
- G is the cell's slope conductance at rest, and C its membrane capacitance.
- Each run lasts five relaxation times, or until it is refused.

**Recorded per run:**
- admitted or refused;
- the refusing check, by its message;
- the step;
- V at the step's start and end;
- the K⁺ population's power at the step's start and end;
- its booked increment of `channel_dissipated_energy_pJ`.

A refusal of the step's validity flag (where the per-stage rule folds in, beside the domain and the
field) is attributed by recomputing dt·`membrane_rate` at that step's start.

**Confirmation needs all of these:**
- the crossing arm is refused by the dissipation check ("Resolved pump dissipation cannot be negative
  or decrease") at the step that crosses E_K, on at least one rung;
- the control is admitted on that rung;
- no other check refuses either arm on that rung.

A refusal by any other check is reported and confirms nothing. The smallest refused rung is reported
against the cardiac note's claim that the 1e-12 pJ tolerance refuses even a crossing a fraction of a
millivolt wide.

**What follows:**
- **Confirmed:** D's trapezoid is needed for channels, as H1 assumes.
- **Never refused by the dissipation check:** the trapezoid's need for channels is revisited before
  H1 (§6.4).

### 5.2 P1: criterion

**Engine models:**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with `cells.transporter@1`
  (`proton_atp_mass_action_positive@1` on held fuel), `cells.rapid_proton_buffer@1` and
  `cell_owned_compartments@1` (host C);
- @3 with the transporter on a cell's plasma patch facing a faced finite node (host P).

**Host C:** FR-4's world (`definitions.fr4_world`), changed in its parameters only:
- n = 4;
- capacity raised so that the ladder's steps stay above 1 µs;
- the proton leak and the K⁺ counterion route set to zero, so the pump's mode is alone;
- the lumen charged past the static head, at V_b* − 20 mV, so the pump runs in reverse back to the
  head. V_b* is where ΔG_cyc = 0 at the start's concentrations.

**ΣG/C** is taken at the static head: G = n²F²J₁/RT, with J₁ = k·S the one-way flux there, over
C_b.

**The ladder:** dt·ΣG/C of 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1 and 2. Each rung runs ten relaxation
times, or until it is refused.

**Recorded per rung:**
- admitted or refused, and the refusing check: the per-stage rule (attributed as in §5.1), the energy
  ledger ("Resolved pump accounting failed: energy"), or another, named;
- the error: the largest |V_b(engine) − V_b(reference)| over the observations, relative to the
  start's offset |V_b0 − V_b*|.

**The reference** is this note's own integration of the same world. The ODE in the lumen's charge and
the two nodes' proton equivalents is solved with Radau at rtol 1e-12, with the law's equations as
`laws/pumps/proton_pump.py` and the buffers' equilibria give them.
- Its author has read the engine, so it is not independent.
- It checks the integration, not the law.

**Host P:** the parse first.
- **If it is refused,** the arm waits for A, and the refusal is reported.
- **If it parses,** the same ladder runs, and records refusals only. Its error is not measured in
  step 0, since its reference would need the faced node's field.

**The decision rules,** stated before the run:
- L_stage, L_ledger and L_err are the largest admitted rungs below the first refusal by each, and the
  largest rung whose error is within 1e-3.
- **Branch X is built** if, on host C, the energy ledger refuses first: L_ledger < L_stage.
- **Mitochondria's branch E** holds if L_eff = min(L_stage, L_ledger, L_err) ≥ 0.05 on the host the
  lead picks for M4; **branch I** otherwise.
  - 0.05 is FR-4's measured booking limit, which mitochondria §2.3's cost for E assumes.
  - L_eff is reported both with L_ledger and without it, since branch X would lift the ledger's
    limit.

**Amendment to P1, committed before P1 runs.** Writing P1's world showed two things the criterion
must fix:
- **The pump's slope past its head carries e^{a},** with a = nF·offset/RT. So a 20 mV offset would
  start the run with a slope 22 times the head's, and the per-stage rule would bind near rung 0.045
  of a ladder scaled at the head.
- **The fix:** the offset is 5 mV (e^{a} = 2.2), and ΣG/C is taken at the start. That is
  G = n²F²J₁/RT with J₁ = k·S·e^{a}, the reverse one-way flux there, the per-stage rule's own
  quantity. The ladder's rungs then read against the stage rule's bound of 1.
- **Run length:** each rung runs ten relaxation times at the head.
- **Capacity:** raised a thousandfold, so the head's rate is about 8e3/s and the steps are 1.2 µs or
  more.

**A second amendment to P1, committed before P1 runs.** Host-side parses, made while writing P1,
showed two more things. Their outcomes were seen before this amendment.
- **Capacity.** A thousandfold capacity is refused at the initial domain ("Initial resolved
  channel/junction/pump domain invalid") at every dt tried, from 1e-3 to 1e-7 s; up to 500-fold is
  admitted. So the refusal does not come from a step rule.
  - P1 uses 500-fold. The head's rate is about 4e3/s, and the smallest step is 1.2 µs.
  - The thousandfold refusal is reported as found. The likeliest cause, the proton buffer's envelope,
    is not traced.
- **Host P's world** is FR-4's with the compartment operator removed and the lumen made a faced node:
  one face to the bath.
  - Version 1 refuses a face that moves two-form buffer rows. It also refuses a face that moves the
    proton row at a buffered node ("proton routes there read through the closure").
  - So the face moves Na⁺, K⁺, Cl⁻ and the trace rows, but neither buffer row nor H.
  - That world parses with the transporter on the cell's patch facing the faced node, so the existing
    kinds do parse on that topology.
  - Its start is charged so that the patch voltage is 5 mV past the head. Its ΣG/C is taken over the
    cell's capacitance (both its patches), the per-stage rule's quantity at a free node.
  - It records refusals only, as committed.

## 6. Results of the probes

### 6.1 The booking probe: confirmed

The evidence is `$W/probes/out/booking.json` and `booking.log`, from `$W/probes/booking_probe.py` and
`booking_world.py`. It ran on CPUs 0–3 under the gate lock.

**The world:**
- E_K = −88.28 mV and the rest is −68.28 mV, with P_K = 1e-9 m/s and P_Na = 3.85e-11 m/s.
- G/C = 2.12/s, so τ = 0.47 s.
- The crossing arm starts at −103.28 mV, and the control at −78.28 mV.

| dt·G/C | Crossing arm | The step that crosses E_K | Control |
| --- | --- | --- | --- |
| 0.003 | Refused by the dissipation check | Step 223, −88.302 → −88.249 mV (0.053 mV); K⁺ increment −8.1e-12 pJ | Admitted |
| 0.01 | **Admitted** | Step 67, −88.284 → −88.111 mV; increment +2.8e-10 pJ | Admitted |
| 0.03 | Refused by the dissipation check | Step 22, −88.460 → −87.939 mV; −6.4e-9 pJ | Admitted |
| 0.1 | Refused by the dissipation check | Step 6, −89.545 → −87.775 mV; −2.1e-7 pJ | Admitted |
| 0.3 and 0.6 | Refused by the step's validity flag, on step 0 | — | The same |

**Reading the table:**
- **At 0.3 and 0.6** the recomputed dt·`membrane_rate` is 1.45 and 2.90: the per-stage rule. Those
  rungs confirm nothing. The rule uses the max-side constant-field slope, about 4.8 times G/C at rest.
- **Wherever the dissipation check refused,** the refused step was the one that crosses E_K. Both
  powers at its ends were positive, so the negative increment came from the internal stage.
- **No other check refused** on the rungs that confirm.

**Verdict: confirmed,** on three rungs. D's trapezoid is needed for channels, as H1 assumes.

**Two findings beyond the criterion:**
- **The refusal depends on where the crossing falls within the step.** At 0.01 the crossing step
  started 0.009 mV below E_K, so its start power was already small. The fall from q(0) to q(γ·dt)
  stayed under the 59% that ARS(2,2,2)'s weights allow, and the increment was positive. So an
  excitable run under the tableau would be refused at some crossings and not at others, depending
  on the step's phase: a reason more for the trapezoid.
- **The cardiac note's claim holds where the phase allows it.** It says the 1e-12 pJ tolerance
  refuses "even a crossing a fraction of a millivolt wide". At 0.003 a 0.053 mV crossing was refused,
  by 8 times the tolerance. At 0.01 a 0.17 mV crossing was not.

### 6.2 P1: handed off, not run

At the lead's instruction, P1 goes to a fresh agent. Its criterion is §5.2 with its two amendments,
all committed before any run.

**What is ready:**
- `$W/probes/p1_probe.py`, written to that criterion: host C's ladder against the reference, and
  host P's ladder recording refusals only.
- Host-side checks already made (parses only, nothing stepped):
  - host C's declared world and host P's world parse at rungs 0.01, 0.1, 1 and 2;
  - the reference integrates (V_b relaxes from −138.2 mV to the head, −133.3 mV);
  - at the start, ΣG/C = 8.55e3/s, and 4.04e3/s at the head.

**What is not done:** no rung was stepped.
- The run was queued behind `locks/gate-cores-0-3.lock`, then held there by the F owner's gate.
- It was cancelled before it started: `$W/probes/out/p1.log` is empty.

**For the agent that runs it:**
- run `p1_probe.py` from a checkout at ef9fc1a8, with `PYTHONPATH=src:.:$W/probes`;
- on CPUs that the lead assigns, under its lock;
- unchanged, unless the note records an amendment before the run.

## 7. The independent check of the screen (17 November 2026)

**Who and how.** An agent that read neither this note nor its workspace, nor the cardiac and
mitochondria notes, rederived the design-changing results from the primary sources. Its scripts and
machine-readable outputs are in `/mnt/workspaces/Cells/screen-check-20261117/` (`scripts/`, `out/`). Its report file was refused by
the harness, and it did not reroute; the report itself went to the lead.

**What it confirms, as printed and in our reading:**
- **O'Hara–Rudy's Na⁺/Ca²⁺ exchanger (INaCa).**
  - The effective charge of each charge-carrying Hill cycle is 2q_Na + q_Ca = 1.2118 against a net
    charge of 1. So the law does not factor at the registry's potentials.
  - **In the print's own bookkeeping** (the ODEs book each unit of charge as 3 Na⁺ in and 1 Ca²⁺
    out), the population's J·ΔG is positive over a band between the true 3:1 reversal and the
    model's. That is free energy delivered with no source. The largest value over the myoplasmic
    box is 5.81 nW/µF.
  - **In the diagram's own species partition:** the myoplasm is never positive, because the leak
    masks it. Cycle A still runs against its own ΔG at 4.5% of states and cycle C at 2.5%.
  - **The paper's own Figure S1** anchors the reading. Its plotted charge flux is about 1.21 times
    the species charge flux.
- **Beard 2005's Eqs. 11, 16 and 24 do not factor:**
  - Eq. 11 lacks the scalar matrix proton;
  - Eq. 16 has [H⁺]x and [H⁺]e reversed relative to the stated 1:1 cotransport;
  - Eq. 24 drops Eq. 7's +2RT ln([H⁺]x/10⁻⁷).

  Repaired forms give a constant residual, and a planted sign flip is caught.
- **Beard's two versions.** The PDF is the version of record. PLOS's web XML and its MathML carry a
  stale Eq. 22, and the earlier extraction script read that version. The printed ΔG°_ATP has the
  sign of hydrolysis but is used as synthesis in Eq. 11.

**What it settles for seam A** (Hill's cycle-flux decomposition, with 200,000 random consistent rate
sets and planted controls):
- **A basis of modes cannot carry each mode's own sign at every state** when cycles share an edge.
  The (3:1, Na⁺-leak) basis fails at 3.7% of a consistent exchanger's states.
- **The full set of Hill cycles, dependent ones included, carries each mode's sign** exactly, and
  each takes §3.2's form.
- **The energy ledger needs only the population's total** Σ J·ΔG. That total is the same in every
  basis.
- **A parse-time Wegscheider check per Hill cycle** (ln(Π⁺/Π⁻) + ΔG/RT = 0) catches O'Hara–Rudy's
  charge error exactly. A population-total check misses it.

## 8. P1's result (17 November 2026)

P1 ran unchanged against §5.2 and its amendments, from a frozen snapshot of main 2bb3e0a4, which is
identical in code to ef9fc1a8. It ran on the gate lane under its lock, 13:57–14:01 UTC. Evidence:
`/mnt/workspaces/Cells/core-seams-step0-20261117/p1_result_note_20261117.md` and `probes/out/`.

- **Neither compared check ever refused,** not the per-stage rule and not the energy ledger. Other
  checks refuse first:
  - **Host C:** admitted at rungs 0.01 and 0.02, with second-order error (×4.03, 4.5e-6 and 1.8e-5
    of the offset). Refused at step 0 from 0.05, by the step's validity flag. Refused before
    stepping from 0.5, by the transporter's explicit-rate bound, which caps the ladder at 0.289.
  - **Host P:** admitted at 0.01. Refused at step 0 from 0.02. Refused before stepping from 0.2, by
    the face term's bound, which caps it at 0.108.
- **Branch X, the exact charged booking, is not built, by the committed rule.** This is a weak no:
  the ledger was observed only up to rung 0.02. Host C's ledger stayed under 0.2% of its tolerance
  there. The trapezoid stays the plan for channels and cycles. A rerun on the same ladder, after
  the gap below is fixed, can only return "ledger first" or "neither".
- **An engine gap, named after the run** (`surface_pump_v3.imex_step`, main lines 1098–1102).
  - At every active outside node, the face-weight predictor requires a positive value: the stage
    read's amount plus θ·dt times the stored amount's derivative.
  - At a buffered node the read is the *free* proton amount, while the derivative is that of the
    stored proton *equivalents*.
  - So the check fails once θ·dt of pumping exceeds the free pool, although the buffer holds about
    38,000 times more. Here that is dt > 3.37 µs.
  - This caps explicit steps wherever a route draws protons from a buffered outside node. It
    matters for mitochondria and for strong proton pumps.
  - It goes to seam C (the binding closure) and @3's owner. No fix is proposed yet.

## 9. P1′: P1's ladder under the general closure (D234)

### 9.1 Criterion (20 November 2026, written and committed before any run)

**Why.** MT-1's host waits for P1′ (D234; CORE_LAWS_ROADMAP §2.3, item A1; MITOCHONDRIA_DESIGN §2.3
and §3.6). An engine gap decided P1 (§8): the face weights' predictor at a buffered node, which
refused every rung above 3.37 µs. 9e181b08 fixed that gap for the general closure `rapid_binding@1`
only. P1′ reruns P1's ladder with the buffers declared that way and asks P1's question per host. Does
today's IMEX handle the ΔΨ mode at the steps MT-1 needs (branch E)? Or is branch I (an implicit cycle
block) or branch X (the exact charged booking) needed? It edits no file under `src/`.

**Engine models:**
- host C: `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with `cell_owned_compartments@1`;
- host P: `resolved_pump_tissue@3`;
- on both:
  - `cells.transporter@1`'s population axis, running the proton law's general form;
  - `cells.rapid_proton_buffer@1`, declaring the general closure `rapid_binding@1`;
  - IMEX ARS(2,2,2), `imex_ars222_face_electromigration@1`;
  - in reading (b), `step_doubled_energy@1` (X2).

**The worlds** are P1's (§5.2 and both amendments: n = 4, capacity × 500, leak and K⁺ route at 0,
the start 5 mV past the pump's static head), ported to today's module layout and otherwise
unchanged, except for three declared changes:
1. **The buffers as the general closure.**
   - Each binder, B_c at the cell and B_L at the lumen, is one form holding one more H, with its
     protonated potential.
   - The read is `rapid_binding@1` on H at both nodes, with the world's own k_on of 10⁷ /mM/s.
   - At equilibrium it gives version 1's free h (`test_rapid_binding_world.py`, within 10⁻¹²).
2. **The pump under a probe ID, on the population axis.**
   - **Why a probe ID.** The shipped `cells.proton_atp_mass_action_positive@1` reads version 1's
     buffer only, so binding refuses it at a closure node ("a mover at a closure node reads the
     closure"). Version 1's layout runs that law by name only.
   - **What the probe ID is.** The shipped law, with its reads set to `rapid_binding@1` and its
     forms to "base".
     - A scoped law registry in the probe holds it; it is never shipped.
     - Its kinetics, domain, general form and step terms are the shipped law's own objects.
   - **Its entry** is the kind's own one-to-one map of P1's entry: N is the cell, and the held fuel
     sits at N.
   - MT-1's laws will declare this read (the roadmap's L1).
3. **Host P's error is measured.** P1 recorded only its refusals. P1′ measures it against the
   engine's own finest arm (below).

**Seen before this criterion, at parse only, with nothing stepped:**
- both hosts' worlds parse, and the structure lists the buffer in `free_amount_reads`, so the
  predictor takes P1's form;
- ΣG/C at the start is 8.55 × 10³ /s on host C and 3.29 × 10³ /s on host P (over the cell's two
  patches), as at P1;
- the definition-time ceilings are as at P1:
  - the kind's bound at rung 0.289 on both hosts;
  - host P's face term at rung 0.108.

**Host P first, on two ladders:**
- **(P-a), P1's face:** area 10⁻¹⁰ m², length 10⁻⁸ m, D 10⁻¹⁰ m²/s for Na, K, Cl and the trace
  rows, and 0 for H and the binders. This is the comparison with P1. Its face term caps it at 0.108.
- **(P-b), the face's D at a hundredth (10⁻¹² m²/s).** Its face term moves to rung 10.8, so the ladder
  reaches the cycle's own limits.
  - The face is the outer membrane's mode, not the ΔΨ mode. Its ceiling for MT-1 is
    1/(2 max_s p_s A_OM/V_IMS), with p_s each row's permeability.
  - That ceiling is reported as a host-P term, to be evaluated with MT-1's permeabilities.

**Then host C's two-cycle arm, if it fits about half a day.** This is P1's host C world with two
populations of the probe law on the bounding patch:
- **A:** n = 4, at P1's capacity;
- **B:** n = 2, its capacity set so that the two charge currents cancel 10 mV past A's head.
  There, A runs in reverse and B forward: a non-equilibrium steady state, V_ss, as respiration
  against synthesis.
- **The start** is 5 mV past V_ss, on the side away from B's head.
- **ΣG/C** is the two slopes at the start, Σ n² F² J₁/RT over C_b, with J₁ each population's reverse
  one-way flux.
- **Each rung** runs ten relaxation times at V_ss.
- **The reference** is P1's Radau integration with the two laws summed. Its code reduces to P1's
  with B's capacity at 0, which is checked before any run.

**The ladder:** dt·ΣG/C at the start of 0.01, 0.02, 0.05, 0.1, 0.2, 0.28 (just below the kind's
bound), 0.5, 1 and 2.
- Host P adds 0.0025 and 0.005, its reference arms.
- Each rung runs ten relaxation times at the head (V_ss for the two-cycle arm), or until it is
  refused.
- Records are taken every steps//200 steps, and at the end.

**Two readings per rung, each its own run:**
- **(a) today's energy check,** P1's configuration;
- **(b) X2 at the cap 2 × 10⁻³,** MT-1's registered configuration (D224). The cap is today's energy
  rtol, as FR-8 rung 1's.

**Recorded per rung and reading:**
- admitted or refused, and the refusing check by its message;
- **for a validity-flag refusal ("domain failure"):** dt·`membrane_rate` at the failing step's
  start, recomputed at the last accepted row.
  - Above `EXPLICIT_STEP_BOUND`, the refusal is the per-stage rule.
  - Otherwise it is "the validity flag, unattributed", P1's verdict form.
- `max_energy_balance_relative` against ENERGY_RTOL;
- in (b), X2's summary;
- **the error:** the largest |V_b(engine) − V_b(reference)| over the records, relative to the start's
  offset.
  - **Host C:** against P1's Radau reference (the lumen's charge and both nodes' proton
    equivalents, the buffers at equilibrium).
  - **Host P:** against its own 0.0025 arm, at matched times. The bound holds where the observed
    order from the 0.0025, 0.005 and 0.01 arms is at least 1, and the reference's error bound is its
    difference from the 0.005 arm.

**The decision rules, stated before the run, per host:**
- **The limits.** L_stage, L_ledger, L_X2 and L_other are each the largest admitted rung below the
  first refusal by:
  - the per-stage rule;
  - today's energy ledger, in (a);
  - X2, any of its refusals named, in (b);
  - any other check, named.

  L_err is the largest rung whose error is within 10⁻³ of the offset, every finer rung included.
- **The effective limit.**
  - In (a), L_eff = min(L_stage, L_ledger, L_err, L_other), P1's rule.
  - In (b), L_eff(X2) = min(L_stage, L_X2, L_err, L_other).
- **Branch E** holds on the host if L_eff(X2) ≥ 0.05, MT-1's configuration. P1's reading (a) is
  reported beside it. 0.05 is the explicit limit that MITOCHONDRIA_DESIGN §2.3's cost for E assumes.
- **Branch I** holds if L_eff(X2) < 0.05 and what binds is the ΔΨ mode itself, a limit an implicit
  cycle block would lift:
  - the per-stage rule;
  - a validity refusal attributed to it;
  - the error.
- **"Not decided by the ΔΨ mode"** if, below 0.05, another check binds first. That includes the
  face term at a face of the probe's choosing, an engine gap, or a definition-time bound. It is
  named, with what lifting it would take.
- **Branch X** is indicated if the energy check binds first:
  - in (a), if the ledger refuses before every other check, P1's rule;
  - in (b), if X2's per-row cap ("exceeds the registration's cap") does, FR-8 rung 1's trigger form.
- **The kind's definition-time bound** (rung 0.289 here, below the stage rule's 1) is reported as a
  ceiling. Above 0.05 it caps E's range, and its conservatism belongs to each law's `bound_rate`.

**Steps for MT-1, reported as information.** Each host's L_eff(X2) is converted with
MITOCHONDRIA_DESIGN §2.3's table: dt = L_eff/(ΣG/C) for J₁ = 1, 10 and 100 mM/s (n = 10, lumped).
With it come the cost of 300 s of protocol, at that note's 3.6 ms per step.

**How it runs:**
- from a clean snapshot of this criterion's commit;
- on the light CPUs at nice 10, through `scripts/run_detached.sh` with a memory cap;
- with 900 s per rung;
- **a timeout is not a result:** the rung is re-run once, and a second timeout is reported as one.

The probe is scratch, as P1's was: `p1prime/` in the @3 owner's workspace, with its sha256 recorded
in the result.

**Amendment 1 to §9.1 (20 November 2026), committed before host C's two-cycle arm runs.**
- **What was found.** A development smoke at an off-ladder rung (0.03), not a rung of the ladder,
  found the two-cycle world as declared refused at definition: "Initial resolved
  channel/junction/pump domain invalid".
  - With the currents cancelling 10 mV past A's head, B's capacity is 13.8 fmol/s, 3.3 times A's.
    The two populations' draw then lies past what the initial domain admits, as P1's thousandfold
    capacity did (§5.2's second amendment).
  - Host-side parses with nothing stepped admit B up to 10.4 fmol/s.
- **The change.** V_ss moves to 5 mV past A's head, which needs B at 4.4 fmol/s.
  - The start stays 5 mV past V_ss toward A's head, which is A's head itself.
  - ΣG/C is then about 4.0 × 10³ /s at the start and about 8.6 × 10³ /s at V_ss, P1's start value.
  - Each rung still runs ten relaxation times at V_ss.
- **The same smoke, at host P (P-a) and rung 0.03 in reading (b),** was refused by X2 at accepted
  step 1: "a held step's change exceeds today's bound at its row". It is reported with the results
  and changes nothing here.
- **The windows' width is 16 steps,** an execution choice that changes no row. With JAX's persistent
  compilation cache, every rung of one arm and reading then reuses one compiled program. It is
  recorded with the run.

**Amendment 2 to §9.1 (20 November 2026), committed before host P's ladders run.**
- **What was found.** A second development smoke, on (P-b) at off-ladder rungs 0.03 and 0.04 in
  reading (a), was refused by the host's dissipation check: "Resolved pump dissipation cannot be
  negative or decrease". The first smoke's X2 refusal, on (P-a) at 0.03, saw flows of 40.5 pJ after
  one 9 µs step.
- **What dominates host P's world: the face's gradient, not the cycle.**
  - P1's host P lumen keeps FR-4's lumen composition (Na 10, K 140, Cl 10 mM), while the bath holds
    Na 145, K 5 and Cl 110 mM.
  - So its face carries a large initial gradient. The lumen exchanges with the bath at
    D·A/(L·V) = 1.5 × 10⁴ /s, with a diffusion potential behind it.
  - That transient is the outer membrane's own and has nothing to do with the ΔΨ mode. An IMS
    equilibrated with its buffer, MT-1's host P, has no such gradient.
- **The change, for (P-b) only.** Its lumen starts at the bath's Na, K and Cl, the rows its face
  moves. Its H and its binder keep the lumen's values, and the face moves neither.
  - (P-b) then isolates the ΔΨ mode on host P.
  - (P-a) stays P1's world exactly, the comparison with P1.

**Amendment 3 to §9.1 (20 November 2026), execution only, committed before any rung's result.**
Two first launches were stopped by the @3 owner before any rung finished. Their folders are kept as
stopped.
- **Why.** The light CPUs are oversubscribed tonight. The probe's process got about a tenth of its
  CPU. The 0.0025 reference arm (8,460 steps, every step recorded) could not finish within 900 s.
- **The changes:**
  - each rung's limit rises to 3,600 s, and a timeout is still not a result;
  - the reference arms are recorded every 4 steps, which holds every rung's record times;
  - the windows are 128 steps wide;
  - (P-b) runs before (P-a), since it isolates the ΔΨ mode.
- **What does not change:** the worlds, the ladder, the readings and the rules.

**Amendment 4 to §9.1 (20 November 2026), committed before its arm runs: the source's own
activity.** This is the lead's request, from the mitochondria lane's appendix (branch mito-lane,
1eaf2310, `docs/MITOCHONDRIA_LAWS_APPENDIX.md`).
- **Why.** The appendix estimates, at the source's X_F1, a desk estimate and not a measurement:
  - the synthase's one-way flux J⁺: 1.4–3.4 mol s⁻¹ (L mito)⁻¹ at 150 mV, and 39–98 at 180 mV;
  - q²F²J⁺/(RT·C_IM): 7 × 10⁴–1.7 × 10⁵ /s at 150 mV, and 2–5 × 10⁶ /s at 180 mV.

  MITOCHONDRIA_DESIGN §2.3's table stops at 0.1 mol s⁻¹ L⁻¹. The ladder's rungs are dimensionless,
  so this arm checks what changes with scale: the closure's envelope, the predictor, the absolute
  floors.
- **Arm S** is (P-b)'s world, with the pump's capacity raised by f so that ΣG/C at the start is
  1.7 × 10⁵ /s (S150) or 5 × 10⁶ /s (S180). Those are the upper ends of the two estimates, taken
  over the cell's capacitance as the rungs are.
  - **The offset falls** so that the start's net flux is (P-b)'s: e^a − 1 = (e^{a₀} − 1)/f. The
    closure's envelope reads the stage's net transport, so it sees what (P-b)'s sees. ΣG/C follows
    the one-way flux, so it takes the source's value.
  - **The values:** f = 108 with an offset of 68 µV (S150); f = 3,214 with an offset of 2.3 µV
    (S180).
  - **Its runs:** rungs 0.01, 0.05 and 0.28 in reading (b), MT-1's configuration, and the 0.0025
    reference arm in reading (a).
  - **Its reading:** by the same rules, each limit converted to an absolute step,
    dt = rung/(ΣG/C).
  - It runs beside the ladder, on another light CPU at nice 10, from the same snapshot. The probe is
    `p1p_scale.py`, which leaves the others unchanged.
- **Host P's outer membrane, the lead's second question.** This is a statement, not a change. P1′'s
  host-P arms assume a face that moves no row the IMS's closure holds.
  - The face moves Na, K, Cl and the trace rows; H and the binder stay.
  - `check_closure_rows` refuses a face at a row the closure holds. MT-1's host P needs ATP, ADP
    and Pi to cross the outer membrane, and in the IMS they are closure rows.
  - The options and their costs are reported with the results.

**Amendment 5 to §9.1 (20 November 2026), execution only, committed before any rung's result.**
The third launch was stopped by the @3 owner before any rung finished, and arm S's first launch
likewise. Their folders are kept as stopped.
- **Why.** A profile of one off-ladder rung, (P-b) at 0.1 in reading (a), found the host's per-row
  checks and records spending 200 of 225 s in the general closure's Newton solve.
  - That solve runs in Python per row on the host, about 0.13 s a call.
  - The device rollout is a small part of the time.
  - At the light CPUs' share tonight, about a fifth of a CPU, (P-b)'s ladder alone would take
    about six hours.
- **The changes:**
  - **The device row checks** (`row_checks="device"`). The arrays, records and verdicts are host
    mode's. The device decides each window's rows, and a window near a bound goes back to the
    host's check (WINDOW_DEVICE_CHECKS_DESIGN §9). All three worlds are admitted.
  - **Host P's records at common times:** every multiple of 1.4/(ΣG/C at the start), the least
    common multiple of the admitted rungs' steps.
    - Every rung and the reference arms record the same physical times, 16 over the run, plus the
      run's end.
    - Host P's error is read at those times. They replace amendment 3's record strides.
  - **Host C's two-cycle arm** records every steps//50 steps, since its Radau reference is read at
    any time.
- **What does not change:** the worlds, the ladder, the readings and the rules.

### 9.2 Results (20 November 2026)

**The runs.**
- **Source:** the clean snapshot of e8e1c973, the criterion's last amendment. Its `src/` is main
  0804a342's.
- **The ladder:** unit `cells-at3-p1prime-e8e1c973`, light CPU 22 at nice 10, 00:54–03:38 UTC.
  (P-b) ran first, then (P-a), then the two-cycle arm.
- **Arm S:** its own unit on light CPU 6, 00:54–01:43 UTC.
- Every rung finished at its first attempt, and none timed out. The launches stopped under
  amendments 3 and 5 are kept as stopped and hold no rung's result.
- **Evidence:** `/mnt/workspaces/Cells/core-pass-at3-20261118/p1prime/`.
  - `out-e8e1c973/` holds each rung's record and log, and each arm's reading (`read_*.json`).
  - `out-scale-e8e1c973/` holds arm S.
  - `diag-late/` holds the diagnosis below.
  - `SHA256SUMS` holds the probe's hashes (p1p_probe.py 99800d42…, p1p_worlds.py 162b0345…,
    p1p_law.py d3b4fb6b…, p1p_scale.py 9b433d7f…).

**Host P, (P-b): the ΔΨ mode alone.** ΣG/C is 3.29 × 10³ /s at the start, so rung 0.01 is 3.04 µs
and ten relaxation times are 2,115 steps.

| Rung | (a) | Error / offset | Ledger, relative | (b): X2 |
| --- | --- | --- | --- | --- |
| 0.0025, 0.005 | admitted (references) | — | 6.1 × 10⁻⁶, 1.3 × 10⁻⁵ | — |
| 0.01 | admitted | 7.9 × 10⁻⁶ | 2.3 × 10⁻⁵ | order condition: median q 0.93 over 2,092 counted |
| 0.02 | admitted | 3.0 × 10⁻⁵ | 3.5 × 10⁻⁵ | order condition: 0.88 over 1,043 |
| 0.05 | admitted | 1.6 × 10⁻⁴ | 6.6 × 10⁻⁵ | order condition: 1.16 over 416 |
| 0.1 | admitted | 5.8 × 10⁻⁴ | 1.4 × 10⁻⁴ | order condition: 1.82 over 208 |
| 0.2 | admitted | 2.3 × 10⁻³ | 4.3 × 10⁻⁴ | order condition: 3.34 over 106 |
| 0.28 | admitted | 4.7 × 10⁻³ | 8.0 × 10⁻⁴ | held cap: 36 out-of-band held, cap 8 (73 counted) |
| 0.5, 1, 2 | refused at definition: the kind's bound | | | the same |

- **Second order:** the error grows 3.7–4.0 times per doubling. The reference's bound is
  1.7 × 10⁻⁶ of the offset.
- **No other refusal:** no per-stage, validity or ledger refusal. Today's ledger stays under half
  its tolerance of 2 × 10⁻³.
- **(a):** L_err 0.1 and L_other 0.28 (the kind's bound); the stage rule and the ledger never
  refuse. L_eff = 0.1.
- **(b):** X2 refuses from the first rung, so L_eff(X2) < 0.01.

**Host P, (P-a): P1's world.** The same ΣG/C, steps and references.

| Rung | (a) | Error / offset | Ledger, relative | (b): X2 |
| --- | --- | --- | --- | --- |
| 0.0025, 0.005 | admitted (references) | — | 6.8 × 10⁻⁴, 1.3 × 10⁻³ | — |
| 0.01 | admitted | 2.2 × 10⁻³ | 1.5 × 10⁻³ | admitted: median q 4.05 over 211 counted, 1 held |
| 0.02 | admitted | 5.2 × 10⁻³ | 1.4 × 10⁻³ | admitted: 4.09 over 119, 1 held |
| 0.05 | ledger: "Resolved pump accounting failed: energy" | | | X2's cap at accepted step 1: Σ\|a\| 0.69 pJ, flows 62 pJ |
| 0.1 | ledger | | | the dissipation check: "cannot be negative or decrease" |
| 0.2 to 2 | refused at definition: the face term's bound (0.108) | | | the same |

- **First order.** At every arm the error is 0.30 × (rung − 0.0025) of the offset: 2.24 × 10⁻³ and
  5.23 × 10⁻³ measured at 0.01 and 0.02, and the reference's own bound is 7.5 × 10⁻⁴.
- **The face carries it.** (P-b) has the same ΔΨ mode, and its error is 280 times smaller at 0.01
  and second order. The arms differ only in the face and the lumen's start.
  - In (P-a), P1's face exchanges FR-4's lumen with the bath at 1.5 × 10⁴ /s.
  - In (P-b), the lumen starts at the bath's composition, and the face's D is a hundredth.
  - Whether the initial gradient's transient or the face weights frozen over a step make the error
    first order was not traced.
- **P1's gap is closed on host P.** (P-a) runs at 0.02 (6.1 µs) in both readings, past P1's
  3.37 µs.
- **(a):** L_err is below 0.01, since no rung lies within 10⁻³. L_ledger and L_other are both 0.02.
  So L_eff < 0.01.
- **(b):** L_err is below 0.01, and L_X2 and L_other are both 0.02. So L_eff(X2) < 0.01.
- Amendment 1's smoke, (P-a) at 0.03 in (b), was refused at step 1 as well: "a held step's change
  exceeds today's bound at its row". Both refusals fall at the first step, inside the face's
  transient.

**Host C, the two-cycle arm.**
- ΣG/C is 4.04 × 10³ /s at the start, so rung 0.01 is 2.47 µs. It is about 8.6 × 10³ /s at V_ss.
- The reference is Radau. With B's capacity at 0 it equals P1's, a difference of 0.0 V, checked
  before any run.

| Rung | (a) | Error / offset | Ledger, relative | (b): X2 |
| --- | --- | --- | --- | --- |
| 0.01 | admitted | 1.0 × 10⁻⁵ | 6.8 × 10⁻⁷ | order condition: median q 1.27 over 465 counted |
| 0.02 | admitted | 4.2 × 10⁻⁵ | 2.7 × 10⁻⁶ | order condition: 2.41 over 233 |
| 0.05 | admitted | 2.7 × 10⁻⁴ | 1.7 × 10⁻⁵ | held cap: 47 held, cap 8 (93 counted) |
| 0.1 | admitted | 1.1 × 10⁻³ | 6.5 × 10⁻⁵ | held cap: 19 held, cap 8 (47 counted) |
| 0.2 to 2 | refused at definition: the kind's bound | | | the same |

- **Second order:** 4.1 times per doubling, and 6.4 times for 2.5.
- **(a):** L_err 0.05 (1.13 × 10⁻³ at 0.1) and L_other 0.1. So L_eff = 0.05.
- **(b):** X2 refuses from the first rung, so L_eff(X2) < 0.01.

**Arm S: the source's stiffness** (amendment 4). Each cell gives the step, then the result.

| Rung | S150: ΣG/C 1.7 × 10⁵ /s, f = 108, offset 68 µV | S180: 5 × 10⁶ /s, f = 3,214, offset 2.3 µV |
| --- | --- | --- |
| 0.0025 (a), the reference | 14.7 ns: admitted | 0.50 ns: admitted |
| 0.01 (b) | 58.8 ns: order condition, median q 0.92 over 1,011 counted; error 1.3 × 10⁻⁵ | 2.0 ns: order condition, 1.00 over 1,001; error 7.8 × 10⁻⁶ |
| 0.05 (b) | 0.29 µs: order condition, 0.57 over 203; error 3.6 × 10⁻⁴ | 10 ns: order condition, 0.64 over 201; error 2.3 × 10⁻⁴ |
| 0.28 (b) | refused at definition: the kind's bound, about rung 0.14 in arm S's units | the same |

- **Accurate where it runs.** The errors are small and second order: 27.7 times for 5 on S150.
- **Its offset had to be small.** A development check during the arm's runs confirmed what
  amendment 4's design assumed. S150's capacity at (P-b)'s 5 mV offset is refused at definition by
  the closure's envelope ("Initial resolved channel/junction/pump domain invalid").
- **The reading:** L_eff(X2) < 0.01, decided by X2's order condition, with L_err ≥ 0.05. The kind's
  bound caps the step at 0.8 µs on S150 and 27 ns on S180.

**Every reading (b) but (P-a)'s is decided by a floor under X2's count rule.** This is a
development diagnosis after the ladder, information only (`diag_late.py`). It takes X2's own
doubled step over a whole rung-0.01 run and splits each step's change as d = s + e and
d'' = s/4 + e: s is the integration error, and e is the part the half steps carry whole.
- **s falls with the relaxation,** on (P-b) from 1.4 × 10⁻¹¹ to 4 × 10⁻¹⁴ pJ a step.
- **e does not.** It stays at about 10⁻¹² pJ a step through the run, random in sign: 0.6–1.2 ×
  10⁻¹² on (P-b) and on the two-cycle arm.
- **X2 counts a step where |d''| > 1000 eps M,** here 0.4–4 × 10⁻¹⁴ pJ. So once s falls below e,
  after the first tenth to third of a run at rung 0.01, every counted step has q ≈ 1, and the
  run's median falls below 3.5.
  - At coarser rungs, with fewer steps in all, the out-of-band steps exceed the held cap instead.
  - In arm S, e dominates from the first step (`diag_q.py`), since its offsets are 70 to 2,000 times
    smaller.
- **e does not accumulate.** Its sum over (P-b)'s run is 1.1 × 10⁻¹⁰ pJ, 7 × 10⁻⁹ of the flows,
  and every row's check passes to the end.
- **It is not the general closure.** (P-b)'s world under version 1's buffer and the shipped law
  shows the same, three times larger (3 × 10⁻¹² pJ).
- **It needs a moving state.** At the pump's static head it is absent (2 × 10⁻¹⁹ pJ,
  `diag_noise.py`).
- **Its source is not traced.** At about 10⁻¹¹ of M it lies far above rounding.
- **(P-a) passes X2 at 0.01 and 0.02,** counting only a tenth of its steps (211 of 2,115). Its
  face's flows, 62 pJ by the first step at 0.05, put the count threshold above 10⁻¹¹ pJ, over the
  floor.
- **Lifting it is X2's matter, not the IMEX's.** Either the floor is removed at its source once it
  is traced, or the count rule gets a floor that holds this part.
  - The second changes X2's registered rule, so it needs the lead's ruling.
  - Reading (b) is then run again: about an hour and a half of one light CPU.

**The reading per host, by the rules as written.**
- **Host P: not decided by the ΔΨ mode.**
  - (P-b): X2's order condition binds at every rung in (b). Reading (a) gives L_eff = 0.1, set by
    the error.
  - (P-a): the face's first-order error binds below 0.01 in both readings, before the ledger (0.05)
    and X2's cap (0.05).
- **Host C: not decided by the ΔΨ mode.** X2's order condition, then its held cap, binds at every
  rung in (b). Reading (a) gives L_eff = 0.05, set by the error.
- **Branch I is not indicated on either host.** No arm had a per-stage or validity refusal, and the
  ΔΨ mode's own error binds only at 0.1 (P-b) and at 0.05 (the two-cycle arm).
- **Branch X is not indicated.**
  - The ledger never refused on (P-b) or on the two-cycle arm. On (P-a) the error binds first.
  - X2's per-row cap refused only on (P-a), at 0.05, after the error.
- **The kind's bound** lies at rung 0.289 on (P-b), where 0.28 runs and 0.5 is refused; between 0.1
  and 0.2 on the two-cycle arm; and at about 0.14 in arm S's units.
- **If X2's floor is lifted** and reading (b) then follows (a), both hosts give branch E: 0.1 on host
  P and 0.05 on host C, the latter exactly at the threshold.

**Steps for MT-1, information.** MITOCHONDRIA_DESIGN §2.3's table, n = 10 lumped. Each cell gives
the step and the cost of 300 s of protocol at 3.6 ms a step, before X2's two extra half steps.

| J₁ (mM/s) | ΣG/C | (b) as it stands: L < 0.01 | (a), host C: 0.05 | (a), host P (P-b): 0.1 |
| --- | --- | --- | --- | --- |
| 1 | 555 /s | < 18 µs: > 17 h | 90 µs: 3.3 h | 180 µs: 1.7 h |
| 10 | 5.5 × 10³ /s | < 1.8 µs: > 170 h | 9 µs: 33 h | 18 µs: 17 h |
| 100 | 5.5 × 10⁴ /s | < 0.18 µs: > 1,700 h | 0.9 µs: 330 h | 1.8 µs: 170 h |

- **At the source's own activity (arm S), branch E is out of reach on either host.**
  - In arm S the kind's bound alone caps the step at 0.8 µs at 150 mV and 27 ns at 180 mV. 300 s
    then takes 3.7 × 10⁸ to 1.1 × 10¹⁰ steps, about 370 to 11,000 CPU-hours. At 0.05 the steps are
    0.29 µs and 10 ns.
  - Bringing E to hours or tens of hours needs J₁ declared at the table's 1–10 mM/s, 30 to 9,000
    times lower: a departure for the user. Otherwise MT-1 needs branch I.
- **Host P's outer membrane caps the step by itself.**
  - The face's explicit bound is 1/(2 max_s p_s A_OM/V_IMS), with A_OM/V_IMS = γ/V_i.
  - At the source's p_Pi = 327 µm/s, γ = 5.99 µm⁻¹ and V_i = 0.0715
    (`validation/mitochondria/beard2005_cardiac.py`, mito-lane 1eaf2310), it is
    1/(2 × 2.7 × 10⁴ /s) = 18 µs. For p_A = 85 µm/s it is 70 µs.
  - 18 µs means at least 16 h for 300 s. Host C has no outer membrane.

**Host P's outer membrane: the lead's question.**
- **What P1′ assumed.** Its host-P arms use a face that moves no closure row: Na, K, Cl and the
  traces cross; H and the binder have D = 0.
- **What MT-1 needs.** ATP, ADP and Pi must cross, and in the IMS they are closure rows, which
  `check_closure_rows` refuses at a face.
- **The options, with the @3 owner's estimates:**
  1. **A face that reads the closure.** It moves a closure row's total at its free amounts on both
     sides, and keeps H⁺ and Mg²⁺ binding in the IMS. @3's face path, the face law's read and their
     tests: 2–4 days.
  2. **Outer-membrane uniports.** They need a host for kinds between two outside nodes, which does
     not exist: 4–6 days.
  3. **No closure in the IMS.** No engine cost. It is a declared departure: the IMS's nucleotides
     and Pi stay unbound, and the laws read totals at the IMS end.
  4. **Host C, with the IMS merged into the owner.** There is no outer membrane at all. The
     departures are the outer membrane's permeation and cytochrome c in the IMS, which makes
     respiration two cycles.

**Recommendation for the host: host C for MT-1,** with MITOCHONDRIA_DESIGN §1.1's two-cycle
respiration.
1. **P1′ does not separate the hosts on the ΔΨ mode.**
   - On (P-b) and on the two-cycle arm, both are second order, with no stage, validity or ledger
     refusal.
   - Reading (a) clears 0.05 on both: 0.1 on host P and 0.05 on host C.
   - Reading (b) is blocked on both by the same floor under X2's count rule.
2. **At the source's activity, E is out of reach on both hosts.**
   - Arm S ran on host P's world. The limits it meets, the kind's bound and the step's scale, belong
     to the law and to ΣG/C, so they hold on host C as well.
   - So MT-1 needs branch I or a declared lower activity.
   - Branch I's implicit cycle block is local on host C. On host P it needs the global form, another
     solver ID, unbuilt (MITOCHONDRIA_DESIGN §2.3).
3. **Host P's outer membrane adds three costs that host C does not have:**
   - a face path for closure rows (option 1, 2–4 days) or a departure;
   - a step cap of about 18 µs at the source's permeabilities;
   - in P1's own face world, a first-order error that binds below rung 0.01.

Host P stays the topology of the isolated organelle and of bacteria, and it handles the ΔΨ mode as
well as host C. If the lead prefers it for MT-1, it needs option 1 or 3 for the outer membrane, the
face's step cap accepted or the permeabilities declared lower, and branch E only at a declared lower
activity.

**On either host,** X2's floor should be traced before MT-1b's registered runs, since registered
runs must select X2. Whether MT-1's worlds meet the floor depends on their M: X2's count threshold
grows with a run's flows. Tracing it needs a buffer-free control and a split of R by term: about
half a day, and minutes of one light CPU.
