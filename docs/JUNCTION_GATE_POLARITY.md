# Junction gate polarity: FR-16's check for FR-30's next benchmark

**Status: design note, 24 November 2026. Nothing here is built.**
- It answers D320's decision: "a polarity-aware gate within FR-16, with a fresh blind benchmark on
  Ek-Vitorín 2016, extractor first. ... The law's form changes only if independent sources support
  it."
- The user decided on it in D334 (§8).
- It is committed beside its companion, the registration in section 13.7 of
  [JUNCTION_TWO_RELAXATION_DESIGN.md](JUNCTION_TWO_RELAXATION_DESIGN.md). That benchmark's fitter
  does not open this note.

**Marks.**
- **S** marks this note's own arithmetic or derivation, done by hand or in a standard-library script
  (`tools/derived.py` in `/mnt/workspaces/Cells/fr30-next-20261124/`). Nothing was run in the
  engine.
- Each source says what of it was read, the **abstract** or the **full text**.
- Every figure from a single study is an indication (the user's rule, D320).

**Kept closed.**
- Ek-Vitorín, Pontifex and Burt (2016) was not opened, searched for, or read through anyone's notes.
- Revilla, Castro and Barrio (1999) is used only through its spent extraction files, and is never
  counted as independent.
- The unopened §13.4 fallbacks 5 to 9 were kept closed so that they stay blind. A search summary
  exposed one sentence of fallback 7's abstract, and probably one clause of fallback 9 (§10).
- Burt-laboratory papers were not consulted, so the design does not lean on the benchmark's own
  laboratory.

§10 lists what was read and what reached this note by accident.

## 0. Summary

| Question | Answer | Weight of the evidence |
| --- | --- | --- |
| **Is homotypic Cx43 gating polarity-dependent** (G_ss or τ different at +V_j and −V_j)? | **Not as a property of the junction.** With one cell stepped, independent preparations disagree: one is asymmetric, and two are near-symmetric with small differences of mixed sign. The one study that also stepped both cells symmetrically found that the asymmetry vanished. | Four labs besides Revilla's. Each figure is one study's indication. Only one study tested the protocol directly |
| **And heterotypic junctions?** | **Yes, in every pairing read:** Cx26/Cx32, Cx43/Cx45, Cx40/Cx43, Cx37/Cx43 and Cx43/Cx46. In G_ss always, and in τ where reported | Many labs; the textbook case |
| **Is the Revilla preparation homotypic?** | **By construction, yes:** both oocytes received rat Cx43 cRNA with an antisense against the endogenous Cx38. But one oocyte was stepped from a common holding potential, so V_j's sign is confounded with that oocyte's V_m. The benchmark's own laboratory reports that rat Cx43 junctions in oocytes depend on V_m. Its ± difference is therefore not evidence of a polarity-dependent V_j gate | Protocol from the spent extraction; the V_m dependence is from Revilla's laboratory, not independent |
| **Each hemichannel's gate polarity?** | Cx43's fast gate closes in the hemichannel on the relatively negative side. Cx43's and Cx45's fast and slow V_j gates both close on relative negativity of their own cytoplasm. The amino terminus sets the polarity, and Cx26 and Cx32 have opposite polarities | Bukauskas lab (two papers), consistent with Elenes 2001; the N-terminus from the Bargiello and Verselis labs |
| **Standard forms?** | A per-polarity two-state Boltzmann; two gates of opposite orientation in series with contingent gating; one switch per hemichannel governed by its own share of V_j (four states); opposing gates fitted across both polarities; stochastic four- and sixteen-state models | §5 |

**Recommendation.**
- **Do not change the form fitted to homotypic Cx43 data.** The Ek-Vitorín 2016 benchmark fits
  `junction_series_gates@1` as declared, with one parameter block for both polarities (§6).
- **The polarity-aware form is supported for heterotypic junctions.** It is FR-16 F3's next version,
  `junction_series_gates@2`, which places each gate on a hemichannel with its own polarity (§7).
- **@2 reduces to today's law.** With every gate declared symmetric it is @1 bitwise. With
  homotypic placed pairs it is polarity-symmetric exactly, and equal to @1 in G/G_0 within a stated
  bound.
- **A heterotypic benchmark qualifies @2.** A homotypic benchmark cannot, by the symmetry in §1.

## 1. The symmetry argument (S)

- **The argument.** Take a junction whose two hemichannels are identical, and whose gates read only
  the transjunctional voltage.
  - Exchanging the two cells maps V_j to −V_j and leaves the junction unchanged.
  - So G_ss(V_j) = G_ss(−V_j) and τ(V_j) = τ(−V_j), whatever polarity each hemichannel's gate has.
- **What follows for a polarity-aware gate.** Per-hemichannel polarity cannot change a homotypic
  prediction. It changes only junctions whose two sides differ.
- **What can make a homotypic junction look asymmetric.** Only something that tells the two cells
  apart:
  - **a V_m (inside–outside) dependence** under a protocol that steps one cell only, so that +V_j
    depolarizes the stepped cell and −V_j hyperpolarizes it;
  - **unequal hemichannels:** heteromeric or heterotypic channels from another connexin present in
    the cells, or differences of phosphorylation between the cells;
  - **a technical asymmetry** between the two clamps.
- **Chen-Izu, Moreno and Spangler (2001)** state the same principle: "the channel voltage-gating
  profile is symmetrical for homotypic channels made of two identical connexons (hemichannels) and
  asymmetric for the heterotypic channels" (abstract).

## 2. Homotypic Cx43: what independent sources show

| Study | Lab, preparation | Protocol | What it reports, by polarity | Read |
| --- | --- | --- | --- | --- |
| Banach and Weingart 1996 | Weingart (Bern). RIN cells stably transfected with rat Cx43; dual whole-cell clamp of preformed pairs | **Both protocols.** "Asymmetrical": cell 1 held, cell 2 stepped. "Symmetrical": both cells stepped by equal amounts of opposite sign | The abstract orders each pair negative then positive. **Asymmetrical:** V_j,0 "−73.7 mV and 65.1 mV for negative and positive Vj"; g_j,min 0.34 and 0.29; τ at 100 mV 350 and 80 ms; "more sensitive to positive Vj values". **Symmetrical:** "the Vj-dependent asymmetries were absent": −60.5 and 59.5 mV, 0.27 and 0.29, 64 and 47 ms. The authors' putative explanation: "the number of channels alters with the polarity of Vj" | Abstract. It gives no n or errors, and does not say which cell is relatively positive at positive V_j |
| Sahu and Bera 2013 | Bera (IIT Madras). N2a cells transfected with Cx43; dual whole-cell clamp; n = 7 | **One cell stepped:** both cells at 0 mV, cell 1 stepped from −120 to +120 mV for 20 s; V_j = V1 − V2 | Positive then negative (Table 2): G_min 0.35 ± 0.01 and 0.33 ± 0.01; V0 +57 ± 0.5 and −56 ± 0.5 mV; A 7.9 ± 0.7 and 8.4 ± 1.2. **S:** the + minus − differences have z = +1.4, +1.4 and −0.4, slightly less closure at +V_j | Full text (PMC3607587, CC BY) |
| Hoang, Qian and Ripps 2010 | Ripps (University of Illinois at Chicago). Xenopus oocytes, mouse Cx43 with the Cx38 antisense; dual two-electrode clamp; n = 5 | **One cell stepped:** ±120 mV in 20 mV steps, the other cell at −40 mV; 10-s steps; G_ss normalized to its value at ±20 mV | Positive then negative (Table 2): A 0.08 and 0.07 per mV; V0 69 and 63 mV; G_jmin 0.21 and 0.24; "general symmetry of the voltage gating behavior for minus and plus Vjs". **S**, its Boltzmann at 60, 80 and 100 mV: 0.741 against 0.660, 0.442 against 0.417, 0.271 against 0.293. The sign is mixed, and no errors are printed. **Caveat:** each polarity is normalized to its own ±20 mV value, so a polarity offset already present at 20 mV divides out | Full text (PMC2905638). The lines read do not say which cell is relatively positive at +V_j |
| Desplantez et al. 2004 | Weingart. HeLa cells, rat Cx43 | Dual voltage clamp; the protocol is not in the abstract | "Homotypic Cx43-Cx43 and Cx45-Cx45 cell pairs yielded distinct symmetrical functions gj,inst=f(Vj) and gj,ss=f(Vj)" | Abstract. A spent FR-30 candidate; its full text was not reachable |
| Schulte et al. 2008 | Dhein. HeLa cells stably transfected with Cx40, Cx43 or Cx45; neonatal rat cardiomyocytes | Dual voltage clamp with switching clamps | Transfected HeLa: "quasisymmetrical ... indicating homotypic gap junction channels". Cardiomyocyte pairs: "an asymmetrical inactivation pattern", attributed to heterotypic and heteromeric channels | Abstract |
| *Revilla, Castro and Barrio 1999, as already seen; not independent* | Barrio. Oocytes, rat Cx43 with the Cx38 antisense; mean ± SEM of six pairs | **One cell stepped:** both oocytes at a common holding level, "e.g., −40 mV"; oocyte 1 stepped; V_j = V1 − V2 | **S**, from the spent files: G_ss is lower at +V_j at 60, 80 and 100 mV, with z = −4.1, −2.6 and −3.1 (SEMs combined as independent, although the six pairs are the same). The times show no consistent sign: τ_slow z −0.9, +1.1 and +1.0; τ_fast +0.4, +0.3 and +1.1 | Spent extraction files only |

**Two foundations, not Cx43.**
- Spray, Harris and Bennett (1981), amphibian blastomeres: "Equal transjunctional voltages of
  opposite polarities produce equal conductance changes", and "The junctional conductance is
  insensitive to the potential between the inside and outside of the cells" (abstract).
- Chen-Izu et al. (2001) state the principle quoted in §1 (abstract).

**What the homotypic evidence shows.**
- **Counted by lab:** Weingart, Bera, Ripps and Dhein, four labs besides Revilla's.
  - **Symmetric or near-symmetric:** Desplantez (HeLa), Schulte (HeLa), Sahu and Bera (N2a), Hoang
    (oocytes), and Banach and Weingart under the symmetric protocol.
  - **Asymmetric:** Banach and Weingart under the one-cell protocol only.
  - Revilla's oocyte asymmetry, which prompted this check, is not reproduced by the independent
    oocyte laboratory. That laboratory used the same holding level (−40 mV), with mouse rather than
    rat Cx43 and 10-s rather than 30-s steps (§2.1).
  - **That comparison is weaker than it looks.** Hoang normalizes each polarity to its own ±20 mV
    value, so it cannot show an offset already present at 20 mV.
    - Revilla's ±20 mV points differ by about 5%: 1.025 at −20 against 0.970 at +20, the latter
      without an SEM.
    - Hoang shows no consistent polarity difference in the voltage dependence beyond 20 mV. It is
      silent on any offset.
- **The direction is not consistent across sources (S).**
  - Revilla: more closure at +V_j, the stepped oocyte relatively positive.
  - Sahu and Bera: slightly less closure at +V_j, the stepped cell relatively positive.
  - Hoang: mixed by magnitude.
  - Banach and Weingart: "more sensitive to positive Vj", in a convention the abstract leaves open.
- **Time constants by polarity are scarce.**
  - Banach and Weingart's one pair at 100 mV is the only independent one read. Negative against
    positive, it is 350 against 80 ms with one cell stepped, and 64 against 47 ms with both stepped.
  - Sahu and Bera, and Hoang, give the two times at one voltage only.
- **Conclusion.** No independent source supports an intrinsic polarity dependence of homotypic Cx43
  V_j gating. Where an asymmetry appears, it appears under one-cell protocols and is not
  reproducible across preparations. In the one direct test, it went away when the cells' mean
  potential was held fixed. That points to something that tells the cells apart (§1), not to the
  V_j gate.

### 2.1 Is the Revilla preparation homotypic?

- **By construction, yes** (`protocol.json`, as already seen).
  - Both oocytes of a pair received wild-type rat Cx43 cRNA, co-injected with an antisense
    oligonucleotide against Xenopus Cx38 mRNA (10 ng per oocyte) "to block endogenous expression".
  - The extraction kept the homotypic wild-type pairs only. It excluded Cx32, the tailless mutant,
    and the hybrid wild-type/tailless pairs.
- **The antisense method,** from outside Revilla's laboratory.
  - Ebihara (1996): "Antisense depletion of Cx38 caused a marked reduction in Ic and blocked
    endogenous gap-junctional coupling in oocyte pairs" (abstract).
  - Barrio et al. (1991), Revilla's laboratory, used the same block.
  - Nothing read measures how much Cx38 remains, or whether any of it co-assembles with Cx43. A
    residual mixed fraction would break §1's premise (**S**), but no source read shows one.
  - Hoang et al. (2010) used the same kind of antisense with mouse Cx43 and found "general symmetry"
    (one study).
- **The protocol does break the argument's premise.**
  - Both oocytes were held at one level ("e.g., −40 mV"), and oocyte 1 alone was stepped. So +V_j
    depolarizes oocyte 1 and −V_j hyperpolarizes it.
  - With a V_m dependence like the one Revilla, Bennett and Barrio (2000) report for rat Cx43 in
    oocytes (§4), the two polarities differ in the stepped oocyte's V_m. §1's argument then no longer
    applies.
- **Other technical candidates** were not assessed from anything read, such as the clamp of large
  oocytes or series resistance. Revilla kept pairs with G_j below 5 µS (`protocol.json`).
- **Answer.** The preparation is homotypic. It is not evidence of a polarity-dependent V_j gate: its
  ± difference is what a V_m dependence under one-cell steps would give (**S**, §4), and it is one
  study's indication.

## 3. Heterotypic junctions: polarity dependence is the rule

- **Barrio et al. 1991,** Cx26/Cx32 in oocytes (Revilla's laboratory, other connexins; abstract).
  - Heterotypic junctions "were electrically asymmetric", with a large slow decrease "for relative
    positivity on the Cx26 side but not for Vj of the opposite sign".
  - Homotypic Cx26 junctions depend on V_i-o; homotypic Cx32 junctions do not.
- **Verselis, Ginter and Bargiello 1994** (abstract): "aspects of the rectification of Cx32/Cx26
  junctions are explained by opposite gating polarities of the component hemichannels", set by the
  charge at the amino terminus's second position.
- **Elenes et al. 2001,** Cx43/Cx45 in N2A or HeLa cells (abstract; a spent FR-30 candidate):
  - "Cx45 connexons inactivated rapidly upon hyperpolarizing voltage pulses applied to the
    Cx45-expressing cell";
  - "During depolarizing pulses to the Cx45-expressing cell, Cx43 connexons inactivated with
    substantially reduced kinetics as compared with homotypic Cx43 channels".
- **Bukauskas, Angele, Verselis and Bennett 2002,** Cx45/Cx43-EGFP (abstract):
  - "very asymmetrical V(j) gating with the maximum junctional conductance shifted to V(j) positive
    on the Cx45 side";
  - the asymmetry "can be strongly modulated by small changes in difference of holding potentials".
- **Desplantez et al. 2004,** Cx43–Cx45 (abstract): "asymmetric functions ... suggesting that
  connexons Cx43 and Cx45 gate with positive and negative Vj, respectively".
- **Valiunas, Weingart and Brink 2000,** Cx40/Cx43 (abstract):
  - "a nonsymmetrical behavior" at steady state;
  - a unitary conductance of 61 pS "when the Cx43 cell was stepped positively or the Cx40 cell
    negatively (V(j)=70 mV); the reverse polarities yielded a conductance of 100 pS".
- **Brink et al. 1997,** rat Cx43/human Cx37 (abstract): "The heterotypic cell pairs displayed
  asymmetric voltage dependence."
- **Hoang et al. 2010,** Cx43/Cx46 in oocytes (full text).
  - V0 is 92 and 46 mV, and G_jmin 0.40 and 0.23, at +V_j and −V_j.
  - The two times are 0.29 ± 0.03 and 3.6 ± 0.3 s at −V_j, and 0.81 ± 0.08 and 5.1 ± 0.9 s at +V_j
    (n = 6, "with respect to the Cx46 cell").
  - This is one study's indication that both relaxation times can depend on polarity in a
    heterotypic junction.
- **Palacios-Prado and Bukauskas 2009,** Cx43/Cx45 (abstract): "small differences in resting
  (holding) potentials of communicating cells can fully block (at relative negativity on Cx45 side)
  or enhance (at relative positivity on Cx45 side) dye transfer".

## 4. Each hemichannel's gate polarity

**Cx43.**
- **Bukauskas, Bukauskiene and Verselis 2002** (abstract): "Each hemichannel in Cx43 cell-cell
  channel possesses two gates: a fast gate that closes channels to the residual state and a slow gate
  that fully closes channels; the transjunctional voltage (V(j)) closes the fast gate in the
  hemichannel that is on the relatively negative side."
  - Its residual state rectifies.
  - "The V(j)-gated channel is not permeable to monovalent positively and negatively charged dyes",
    which supports §7 of the FR-30 design note: a route's own residual, 0 for a large tracer.
- **Bukauskas, Angele, Verselis and Bennett 2002** (abstract): "Fast and slow V(j) gates of both
  Cx45 and Cx43 hemichannels close for relative negativity at their cytoplasmic end."
- **Elenes et al. 2001 agree (S).**
  - Cx45 closes when its cell is hyperpolarized, that is, when its own cytoplasm is relatively
    negative.
  - Cx43 closes when the Cx45 cell is depolarized, that is, when the Cx43 cytoplasm is relatively
    negative.
- **Desplantez et al. 2004 imply the same intrinsic polarity (S).**
  - In a heterotypic pair the two hemichannels face opposite ways. Closing at opposite signs of one
    V_j therefore means the same polarity relative to each hemichannel's own cytoplasm.
  - It agrees with Bukauskas if its V_j is referenced to the Cx45 cell, and its convention was not
    read.

**What sets polarity.**
- Verselis et al. 1994: the charge at the amino terminus's second residue. Cx26 and Cx32 are
  opposite.
- Purnick et al. 2000 (abstract):
  - "In Cx32 hemichannels, V(j)-gating occurs at negative V(j)";
  - negative charges at positions 2, 5, 8, 9 or 10 reverse it;
  - the amino terminus lies in the transjunctional field and is "largely insensitive to changes in
    absolute membrane potential (V(m))".
- Bukauskas and Verselis 2004 (review, abstract): the amino terminus "is most essential and ...
  determines gating polarity".

**Two gates per hemichannel.**
- Trexler et al. 1996, Cx46 hemichannels: a gate to a substate on depolarization, and a slow loop
  gate to closed on hyperpolarization.
- Valiunas, Bukauskas and Weingart 1997, native neonatal rat Cx43 channels: transitions to the
  residual state are fast (< 2 ms), and those involving the closed state slow (15 to 65 ms).
- Banach and Weingart 2000, RIN Cx43: fast transitions under 2 ms, and slow ones of 3.5 to 145 ms.
- Bukauskas and Verselis 2004: the fast gate is "solely sensitive to V(j)". The slow gate is also V_j
  sensitive, and "may mediate gating by transmembrane voltage (V(m))". (All abstracts.)

**V_m (inside–outside) dependence, a separate mechanism.**
- Spray et al. 1981, amphibian junctions: insensitive.
- Barrio et al. 1991: Cx26 sensitive, Cx32 not.
- Revilla, Bennett and Barrio 2000, rat Cx43 in oocytes (the benchmark's laboratory, not
  independent; abstract):
  - "equal depolarization of both cells decreases g(j)";
  - the dependence is abolished by truncation at residue 242 but not 257, and R243Q and D245Q change
    it without changing V_j dependence;
  - "V(j) gating was somewhat modulated by V(m), and V(m) gating was reduced when the V(j) gate was
    closed".

**Revilla 1999 under this reading (S; a hypothesis, not a demonstration).**
- A +V_j step depolarizes the stepped oocyte, and with the 2000 paper's sign it should close more
  junction than an equal −V_j step.
- That is the direction of Revilla 1999's G_ss at 60, 80 and 100 mV (§2).
- The independent oocyte study (Hoang) shows no such consistent direction from the same holding
  level.

## 5. Standard law forms

| Form | Source (all abstracts unless marked) | Steady state, kinetics and polarity | Homotypic case |
| --- | --- | --- | --- |
| **1. Per-polarity two-state Boltzmann** | Spray et al. 1981: "for voltages of each polarity ... a reversible two-state system". Harris et al. 1981: rate constants exponential in V. The form Sahu and Bera, and Hoang, fit (full texts) | G_min + (1 − G_min)/(1 + exp(A(V_j − V0))), with each polarity's own parameters; one exponential per polarity (Harris 1981) | Equal parameters at both polarities |
| **2. Two gates of opposite orientation in series, contingent** | Harris, Spray and Bennett 1981: "two gates, each with opposite voltage sensitivity, and in which an open gate may close only if the gate in series with it is open"; "each gate senses only the local voltage drop within the channel" | At most one gate closed. A transient recovery on polarity reversal | Symmetric |
| **3. One switch per hemichannel, four states** | Vogel and Weingart 1998: two hemichannel submodels in series, each switch "governed by the voltage drop across the respective hemichannel"; the switches "work independently, thus giving rise to four conformational states"; LL is "rare and of short duration"; contingent-like time courses emerge; the high and low conductances vary exponentially with the hemichannel voltage | Polarity per hemichannel; heterotypic predicted from homotypic | Symmetric |
| **4. Opposing gates, fitted across both polarities** | Chen-Izu et al. 2001: "integrating, rather than separating, the contributions of the voltage gates of the two member connexons"; fitted "over the entire voltage range"; "assignment of gating polarity to a connexon" | One formula through V_j = 0. FR-16's preprint uses it (GAP_JUNCTION_CANCER_REPLICATION.md quotes the preprint's version) | Symmetric |
| **5. Stochastic four-state contingent model** | Paulauskas et al. 2009: two fast gates, "one per hemichannel", oriented oppositely; gating set by "the fraction of V(j) that falls across the hemichannel"; open and residual conductances rectify; gates "can exhibit the same or different gating polarities" | Holding-potential differences modulate heterotypic signalling | Symmetric |
| **6. Sixteen-state model, fast and slow gates per hemichannel** | Paulauskas et al. 2012: "two fast and two slow gates in series"; each gate's voltage "varies depending on the states of three other gates"; each gate has a slope, a midpoint, a gating polarity and its unitary conductances | The full form of what FR-30's law approximates | Symmetric |

**Where `junction_series_gates@1` sits (S).** Its fast and slow gates both read |V_j|. It is form 6
for a homotypic junction with three simplifications:
- **(a)** the hemichannel on the relatively positive side is taken as fully open;
- **(b)** each gate reads the whole V_j, with no voltage division and no contingency;
- **(c)** neither conductance rectifies.

(b) and (c) are approximations the law already makes. (a) costs at most 1/h(0) − 1 in G/G_0, about
1e-3 at Revilla's fitted parameters and about 1e-2 for a gate half closed at 60 mV with slope
80 V⁻¹ (§7).

## 6. Recommendation: the form fitted to a homotypic benchmark does not change

**The evidence.**
- **The mechanism is symmetric for homotypic junctions (§1).** Per-hemichannel polarity is real and
  well supported (§4), but it leaves a homotypic prediction unchanged.
- **The data agree.** Independent homotypic Cx43 studies are symmetric or near-symmetric, and their
  residual differences are inconsistent in sign (§2).
- **The asymmetry depends on the protocol.** The one direct test removed it by stepping both cells
  symmetrically (Banach and Weingart 1996, one study).
- **Revilla's ± difference has a candidate cause outside the V_j gate:** one-cell steps combined with
  a V_m dependence reported by its own laboratory. It is one study's indication either way.

**So the benchmark fits @1 as declared.** The Ek-Vitorín 2016 benchmark fits `junction_series_gates@1`
with one block of kinds and parameters for both polarities.
- D317 ruled one block for Revilla. It did so after reading, with every number masked, the Lean
  lane's line on polarity-symmetric gates.
- §13.7 registers the same choice before this paper is opened.

**What would change this:**
- an independent study with a symmetric (bipolar) protocol showing a homotypic Cx43 ± difference
  beyond its errors; or
- independent mammalian evidence of a Cx43 V_m dependence large enough to matter under the benchmark's
  protocol.

The registration's unjudged diagnostics record the protocol type, the holding levels and the ±
differences, so that the benchmark's paper becomes a further indication either way
(section 13.7, part 7).

**The polarity-aware form belongs to heterotypic junctions (§3, §4).** It is FR-16 F3's next version
(§7), qualified by its own heterotypic benchmark.

**No V_m term now.**
- **The evidence for Cx43 is thin and mixed:**
  - one laboratory, in oocytes, and it is the benchmark's (Revilla 2000);
  - one protocol-dependent asymmetry whose authors proposed a different cause (Banach and Weingart
    1996);
  - two one-cell studies that are near-symmetric (Sahu and Bera, held at 0 mV; Hoang, held at
    −40 mV).
- **A V_m gate also needs each cell's V_m.** `cells.junction_law@1` gives a law only the junction
  voltage (`kinetics(voltage, parameters)`), so this is an interface change: a later FR-16 item.

## 7. The next version, for FR-16 (not built; not this benchmark's law)

**`junction_series_gates@2`.** It is @1 with one declaration added per gate.
- **Its scope (D334):** a design note under FR-16 F3, for heterotypic junctions only.
- **The replication does not need it.** What the gap-junction replication needs is F3's two-state
  Cx45 gate in Chen-Izu's manner, and no heterotypic junction is documented in it (D334's
  correction).

**Per gate:**
- `kind`: `threshold_relaxation` or `boltzmann_eyring`, as in @1;
- `placement`:
  - `symmetric`: reads |V_j|, exactly @1's gate;
  - `sender` or `receiver`: a gate in that cell's hemichannel;
- `polarity`, for placed gates only: `closes_on_own_negative` or `closes_on_own_positive`, the
  connexin's intrinsic polarity relative to its own cytoplasm. Cx43 and Cx45 are
  `closes_on_own_negative` (Bukauskas 2002, §4).
- Its parameters, as in @1: λ, A, V0, δ and r for `boltzmann_eyring`.
- `threshold_relaxation` stays symmetric only, since its cited rates are defined on |V| minus a
  threshold.

**The polarity convention.**
- @3's junction voltage is V_j = V_sender − V_receiver (`_JUNCTION_VOLTAGE` in
  `surface_pump_v3.py`: "positive when the sender is at the higher potential").
- A placed gate's drive is d = s·ε·V_j, where:
  - s = +1 on the receiver's side and −1 on the sender's (the receiver's cytoplasm is relatively
    negative when V_j > 0);
  - ε = +1 for `closes_on_own_negative` and −1 for `closes_on_own_positive`.
- A `boltzmann_eyring` gate then uses u = A·(d − V0) in place of A·(|V_j| − V0).
- **Check:**
  - a receiver-side Cx43 gate has d = V_j, and closes when the sender is relatively positive;
  - a sender-side Cx43 gate has d = −V_j, and closes when the sender is relatively negative.
- **For a benchmark's paper,** the sender is the stepped cell, or cell 1 under a symmetric protocol,
  so the paper's V_j maps to sender minus receiver (section 13.7, E3).

**The junction.**
- g = Π_i c_i over all gates, two to four of them, each independent.
- Each gate keeps detailed balance, and the product chain passes Kolmogorov's test, as in @1.
- The exact constant-voltage step is the product of the gates' exact steps, as in @1.

**How it reduces to today's law (S).**
- **R1, exact.** With every gate `symmetric`, @2 calls @1's functions on |V_j|: it is @1 bitwise.
  - *Test rows:* the law's gate factors and conductance under @2 equal @1's bitwise on a voltage
    and time grid.
  - Revilla's registered block, run through `predict` and `readout` under @2, reproduces
    `fit/predictions.json` (20ca2a4a...) within `verify`'s relative 1e-6.
- **R2, exact symmetry.** Give a homotypic junction the same gate list on both sides: the same kinds,
  parameters and polarity.
  - Then g(V_j) = h(V_j)·h(−V_j), with h the product of one side's gate factors at drive d.
  - So g(V_j) = g(−V_j), equal up to floating-point reordering of the product.
  - *Test row:* ± pairs on a grid agree within 4 ulp.
- **R3, bounded.** Compare that homotypic pair with @1 using the same per-gate parameters.
  - G/G_0 under @2 equals G/G_0 under @1 times h(−|V_j|)/h(0).
  - For monotone gates (A ≥ 0) that factor lies in [1, 1/h(0)], where h(0) is one side's product at
    V_j = 0.
  - In kinetics the opening side adds a rising component of total amplitude at most 1/h(0) − 1.
  - **S:** 1/h(0) − 1 is 8.1e-4 at Revilla's fitted block (fit/LOG.md), and 1.2e-2 for two gates
    with A = 80 V⁻¹, V0 = 60 mV and r = 0.3.
  - *Test row:* the bound holds on a grid.
- **R4, heterotypic.** Different gate lists on the two sides give g(V_j) ≠ g(−V_j) in general: the
  new capability.

**Not in @2, and each would be its own later version:**
- **contingency and voltage division** (Harris 1981; Vogel and Weingart 1998; Paulauskas 2009,
  2012). Each gate reads the whole V_j, as in @1;
- **V_m dependence** (§6);
- **instantaneous rectification** of the open and residual conductances (Vogel and Weingart 1998;
  Bukauskas 2002 JGP; Valiunas 2000).

**Interface and ownership.**
- The gate block's parse gains placement and polarity.
- @3 already orients every edge.
- A heterotypic edge needs each side's connexin from FR-16's catalogue: that is F3's work, with the
  @3 owner.
- @1 is development-only (D262). Under the pre-alpha rule, @1 would be retired once @2 lands, since
  R1 makes @1 a special case of @2.

## 8. Decisions (D334) and what stays open

The user decided on this note on 24 November 2026 (D334), with the advisor's provisos.
- **The form:** the Ek-Vitorín 2016 benchmark fits `junction_series_gates@1` as declared, with one
  parameter block (§6).
- **@2** (§7) is logged as a design note under FR-16 F3, for heterotypic junctions only.
- **The one-cell protocol.** Under any protocol type but a symmetric one, disjoint ± windows are
  reported per observable as confounded by V_m, neither pass nor fail.
  - Overlapping observables are still judged, and a minimum judged set is stated.
  - The justification is non-identifiability (§1, §2.1), not a claim that V_m gating is real.
- **No fallback is opened,** and nothing is downloaded for this decision.

**Still open.**
1. **Revilla, Bennett and Barrio 2000** is used only as mechanism evidence, since it comes from the
   benchmark's laboratory.
2. **The cost of keeping the fallbacks closed.** Three unread sources are probably the most on
   point:
   - Bukauskas 2001, on Cx43 and Cx43-EGFP gating (its subject from training data);
   - Rackauskas 2007, on heterotypic Cx40/43/45 (by its title in a PubMed listing);
   - Wang 1992, on V_j gating in native myocytes (by its title).

   Reading any of them would end its use as a blind benchmark. Rackauskas 2007 would be a natural
   heterotypic benchmark for @2.
3. **Full texts.** The pivotal homotypic evidence was read as abstracts only, without n, errors or
   sign conventions: Banach and Weingart 1996, and the polarity statements of Desplantez 2004 and
   Elenes 2001. Section 2's weights stand as abstract-level indications.
4. **V_m dependence** stays a later FR-16 item, needing each cell's V_m (§6).

## 9. Sources

**Each source at its strength.**
- **Read in full:** two, Sahu and Bera 2013 and Hoang et al. 2010.
- **Read as abstracts only:** the other 24. Harris et al. 1981's came from its publisher's page.
- **Revilla et al. 1999:** used only through its spent extraction files.

| Source | DOI or ID | Lab | Preparation, n | Read at |
| --- | --- | --- | --- | --- |
| Banach K, Weingart R (1996) Pflügers Arch 431:775 | 10.1007/BF02253843 | Weingart | RIN + rat Cx43, pairs | abstract only |
| Banach K, Weingart R (2000) Pflügers Arch 439:248 | 10.1007/s004249900182 | Weingart | RIN + mouse Cx43, single channels | abstract only |
| Barrio LC et al. (1991) PNAS 88:8410 | 10.1073/pnas.88.19.8410 | Barrio, Bennett, Nicholson | oocytes, Cx26 and Cx32 | abstract only |
| Brink PR et al. (1997) Am J Physiol 273:C1386 | 10.1152/ajpcell.1997.273.4.C1386 | Brink | rat Cx43, human Cx37 | abstract only |
| Bukauskas FF, Bukauskiene A, Verselis VK (2002) J Gen Physiol 119:171 | 10.1085/jgp.119.2.171 | Bukauskas, Verselis | Cx43, Cx43-EGFP lines | abstract only |
| Bukauskas FF, Angele AB, Verselis VK, Bennett MVL (2002) PNAS 99:7113 | 10.1073/pnas.032062099 | Bukauskas, Bennett | Cx45, Cx43-EGFP lines | abstract only |
| Bukauskas FF, Verselis VK (2004) Biochim Biophys Acta 1662:42 | 10.1016/j.bbamem.2004.01.008 | review | — | abstract only |
| Chen-Izu Y, Moreno AP, Spangler RA (2001) Am J Physiol Cell 281:C1604 | 10.1152/ajpcell.2001.281.5.C1604 | model | — | abstract only |
| Desplantez T et al. (2004) Pflügers Arch 448:363 | 10.1007/s00424-004-1250-0 | Weingart | HeLa, rat Cx43, mouse Cx45 | abstract only (spent FR-30 candidate) |
| Ebihara L (1996) Biophys J 71:742 | 10.1016/S0006-3495(96)79273-1 | Ebihara | oocytes, Cx38 | abstract only |
| Elenes S et al. (2001) Biophys J 81:1406 | 10.1016/S0006-3495(01)75796-7 | Moreno | N2A or HeLa, Cx43 and Cx45 | abstract only (spent FR-30 candidate) |
| Harris AL, Spray DC, Bennett MVL (1981) J Gen Physiol 77:95 | 10.1085/jgp.77.1.95 | Bennett | amphibian blastomeres | abstract only, from the publisher's page |
| Hoang QV, Qian H, Ripps H (2010) Mol Vis 16:1343 | PMC2905638 (no DOI listed) | Ripps | oocytes, mouse Cx43 and Cx46; n = 5 (Cx43), 6 (Cx43/Cx46) | full text |
| Palacios-Prado N, Bukauskas FF (2009) PNAS 106:14855 | 10.1073/pnas.0901923106 | Bukauskas | Cx43/Cx45 | abstract only |
| Paulauskas N et al. (2009) Biophys J 96:3936 | 10.1016/j.bpj.2009.01.059 | Bukauskas | model | abstract only |
| Paulauskas N et al. (2012) Biophys J 102:2471 | 10.1016/j.bpj.2012.04.038 | Bukauskas | model | abstract only |
| Purnick PEM et al. (2000) Biophys J 79:2403 | 10.1016/S0006-3495(00)76485-X | Bargiello, Verselis | Cx32 mutants | abstract only |
| Revilla A, Bennett MVL, Barrio LC (2000) PNAS 97:14760 | 10.1073/pnas.97.26.14760 | Barrio (the benchmark's laboratory) | oocytes, rat Cx43 | abstract only |
| Sahu G, Bera AK (2013) PLoS ONE 8:e60506 | 10.1371/journal.pone.0060506 | Bera | N2a, Cx43, n = 7 | full text (Table 2, Methods) |
| Schulte JS et al. (2008) Cell Commun Adhes 15:13 | 10.1080/15419060802014404 | Dhein | HeLa Cx40, Cx43 and Cx45; neonatal rat cardiomyocytes | abstract only |
| Spray DC, Harris AL, Bennett MVL (1981) J Gen Physiol 77:77 | 10.1085/jgp.77.1.77 | Bennett | amphibian blastomeres | abstract only |
| Trexler EB et al. (1996) PNAS 93:5836 | 10.1073/pnas.93.12.5836 | Verselis, Bargiello | oocytes, Cx46 hemichannels | abstract only |
| Valiunas V, Bukauskas FF, Weingart R (1997) Circ Res 80:708 | 10.1161/01.RES.80.5.708 | Weingart | neonatal rat heart cells | abstract only |
| Valiunas V, Weingart R, Brink PR (2000) Circ Res 86:e42 | 10.1161/01.RES.86.2.e42 | Brink, Weingart | Cx43-RIN, Cx40-HeLa, Cx43-HeLa | abstract only |
| Verselis VK, Ginter CS, Bargiello TA (1994) Nature 368:348 | 10.1038/368348a0 | Verselis, Bargiello | oocytes, Cx26 and Cx32 | abstract only |
| Vogel R, Weingart R (1998) J Physiol 510:177 | 10.1111/j.1469-7793.1998.177bz.x | Weingart | model | abstract only |
| *Revilla A, Castro C, Barrio LC (1999) Biophys J 77:1374* | *10.1016/S0006-3495(99)76986-9* | *Barrio* | *oocytes, rat Cx43, six pairs* | *spent extraction files only* |

Also read and not used: the abstract of Fishman et al. (1991), PNAS 88:3525, doi:10.1073/pnas.88.9.3525,
whose abstract has no polarity data.

**Access.**
- Full texts outside the open-access subset could not be fetched. PMC's browser check, Europe PMC
  (403), Cell Press (403), Springer's sign-in and the Bern repository all refused.
- So most sources here are abstracts, with their quotations exact.
- The abstracts, the two full texts and the lookup scripts are in
  `/mnt/workspaces/Cells/fr30-next-20261124/`, under `sources/` and `tools/`. Nothing was downloaded
  into the repository.

## 10. What I read, and what I did not

**Read in the checkout.**
- D262, D308, D311, D317 and D320; FR-16's and FR-30's sections.
- The whole of `docs/JUNCTION_TWO_RELAXATION_DESIGN.md`.
- The law's code:
  - `junction_series_gates.py`, `junction_voltage_relaxation.py` and `junction_gate.py`;
  - its declaration's entry in `visualizer/data/laws/pieces.json`. It has no page under
    `docs/library/`.
- The Revilla harness, `revilla1999.py` and `revilla1999_score.py`.
- `GAP_JUNCTION_CANCER_REPLICATION.md`'s F3 lines, and the junction-voltage definition in
  `surface_pump_v3.py`.

**Revilla's spent materials.**
- **Read:**
  - in `fr30-benchmark-20261123/`: `RULING_DRAFT.md`, `fit/LOG.md`, `fit/kinds.json` and
    `verdict/checker_verdict.json`;
  - in `fr30-candidates4-extraction/revilla1999/extraction/`: `protocol.json`, `fit.json`,
    `held_out.json` and `SHA256SUMS`, values included. Each was first checked by count only for the
    sealed paper's names, and none matched.
- **Not opened:**
  - Revilla's `extraction_notes.md` and its sealed digitizers;
  - `fr30-candidates4-extraction/README.md` and `LOG.txt`, which may describe the sealed paper's
    status;
  - the Shibayama and Elenes extraction folders, and every earlier FR-30 extraction folder,
    Ek-Vitorín 2018's included.

**Kept closed.**
- **The sealed paper:** its folder, its record, its DOI's landing pages, and any search for it.
- **`lean/`:** a grep that lists file names only, for the paper's names, found no hit. Nothing was
  opened.
- **The §13.4 fallbacks 5 to 9.** A PubMed title listing showed the titles, journals and pages of
  Rackauskas 2007 and Wang 1992. Their abstracts were not fetched.
- **Burt-laboratory papers,** and Ek-Vitorín 2018, which is the same laboratory's and later.
- **A 1994 paper with the sealed paper's first author** (pH gating of Cx43) appeared in the same
  title listing. Not fetched.

**Reached me by accident.**
- **Fallbacks 7 and 9 are exposed.** My first web search returned a model-written summary.
  - It quoted one sentence of the abstract of fallback 7, Wang et al. 1992.
  - It also carried one clause from a Veenstra-laboratory paper on Cx43-dominated junctions during
    action potentials. That paper is probably fallback 9 (Lin, Xu and Veenstra 2014), or Lin et al.
    2005.
  - Neither carries a step-decay value. Neither is quoted here.
- After that, every topic search went through PubMed with a publication-date ceiling of 2014, so no
  source that could quote the 2016 paper was listed.
- The exposure sweep for the sealed paper, which lists file names only, is recorded in section
  13.7's disclosure.

**From training data.** I recall the sealed paper's approximate title, "Determinants of Cx43 channel
gating and permeation: the amino terminus", and so its subject. I recall no figure, protocol, voltage
or value from it.
