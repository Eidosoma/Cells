# A junction gate with two relaxation times (FR-30): design note

**Status: proposed, 20 November 2026, for the lead.** Desk work only (D142): options, a
recommendation, the interface, the data a prediction needs, files and owners, what stays bitwise,
tests and a price. Nothing is built. Branch `fr30-design` from main 8839a175. **S** marks this
note's own derivation, done by hand and not run. "From memory" marks standard theory cited without
being read for this note.

**The request** (FR-30 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md); D248, D249). The generic
`junction_voltage_relaxation@1` relaxes once: in 50.0 ms at −100 mV. Homotypic Cx43 junctions show
two phases in one decay. FR-30 belongs to FR-16's connexin catalogue
([GAP_JUNCTION_CANCER_REPLICATION.md](GAP_JUNCTION_CANCER_REPLICATION.md) F3: per-connexin
constants, homotypic and heterotypic) and to the Cx43 plan in
[PROTEIN_CATALOGUE_PLAN.md](PROTEIN_CATALOGUE_PLAN.md).

**Engine models it would run:** `cells.resolved_pump_tissue@3` with a new junction law (§4), beside
an unchanged `junction_voltage_relaxation@1`.

**Names are mechanisms' (D144).** The law is two voltage gates in series. Cx43 is one parameter set
in FR-16's catalogue, never the law's name.

## 0. Summary

| | |
| --- | --- |
| **What exists** | One junction law with one gate state per edge: a two-state relaxation with a residual floor, BETSE's rates. Its interface is `kinetics(voltage, parameters) → Rates(alpha, beta, target, relaxation)` |
| **The data** | Sahu and Bera (2013), read: 70 ± 5 and 931 ± 54 ms in one decay at −100 mV, with a Boltzmann for the steady state at each polarity. Moreno et al. (2002): not read, since the fetch was refused; 0.25 and 3.18 s at 60 mV, as the review reports them |
| **Recommended** | (A) **two gates in series**, fast and slow. Each is today's two-state gate, with today's `Rates` and `rhs`, and a Boltzmann–Eyring kind for cited constants. The conductance is the product of the gates' factors. Each gate keeps detailed balance by itself, so the pair does |
| **The interface** | Each gate keeps today's `kinetics(voltage, parameters) → Rates`. The law adds a gate count, the product, and the per-gate open fractions that routes read. Today's law is the one-gate case |
| **A prediction needs** | A voltage series from one preparation: both components' time constants and amplitudes at several voltages of both polarities, the steady conductance, and the recovery at 0 mV. One voltage from each of two labs is not a series |
| **Tracer transfer** | Kept apart. Ions pass the residual state and large tracers may not, so each route declares its own residual per gate. The electrical and tracer comparisons are separate registrations with separate data |
| **Bitwise** | Every existing world: the law's module, its one-gate state layout, its programs, records, crossrev and G1 |
| **Price** | 3.75–5.5 agent-days, gates excluded; @3's part after N2. The search for a voltage series is not priced |

## 1. What exists

- **The law** (`src/cells/laws/junctions/junction_voltage_relaxation.py`):
  - One state per junction edge, g in [minimum, 1].
  - dg/dt = α(1 − g) − β(g − minimum), with α = 1.3·exp(−77·s) and β = 20·b/(1 + b), where
    b = 0.065·exp(140·s) and s = |V| − threshold (V, s; BETSE v1.5.0's rates, cited).
  - `kinetics(voltage, parameters)` returns `Rates(alpha, beta, target, relaxation)`, with
    target = (α + β·minimum)/(α + β) and relaxation = α + β.
  - `advance_clamped` is the exact constant-voltage update.
  - `Parameters` are the threshold and the minimum.
- **Its one time constant (S, from the code).** At −100 mV, with a threshold well below 100 mV, β
  saturates near 20 s⁻¹ and α is negligible. So 1/(α + β) is about 50 ms. With the reference
  parameters the review used, it is the 50.0 ms FR-30 states; a threshold near 100 mV gives a
  longer time.
- **Today's state is the gate's conductance factor.** With x the open fraction of a two-state gate,
  g = minimum + (1 − minimum)·x. Then dg/dt above is exactly the two-state equation for x (**S**).
  So today's law is one two-state gate whose closed state keeps a residual conductance.
- **The integration** (the @3 owner's, `src/cells/models/surface_pump_v3.py` and
  `surface_kinetic.py`):
  - `state.junction_gate` is [edge], intensive, 0 on a closed contact.
  - The junction's conductance is `control.junction × state.junction_gate`.
  - `junction_gate_rhs` calls the law's `rhs`; the domain check calls `domain_valid`.
  - The parameters are laid out per edge (`junction_threshold_voltage`, `junction_minimum`).
- **The interface** (`src/cells/registry/laws.py`, `JunctionLaw`): `gated`, `kinetics`, `rhs`,
  `domain_valid` and `max_abs_voltage_V`.
- **What it proves.** The Lean project's claim (`lean/claims/junction-gate.md`) proves
  one-exponential relaxation, bounds, polarity symmetry and the clamp, for this law only.
- **FR-16 (F3, F4).** F3 asks for a two-state connexin gate in the manner of Chen-Izu et al. (2001),
  with per-connexin constants. F4 asks for a residual floor per species, since a closed gate passes
  small ions but not miRNA. Neither is built.

## 2. The data

### 2.1 Sahu and Bera (2013), read for this note

PLoS ONE, doi:10.1371/journal.pone.0060506, read at PMC3607587 under its Creative Commons
Attribution licence.

**The preparation.**
- Neuro-2a (N2a) cell pairs, transfected with connexin cDNA and recorded 24–36 h later.
- Dual whole-cell voltage clamp. Both cells were held at 0 mV, and cell 1 was stepped from −120 to
  +120 mV in 20 mV increments, for 20 s each, with 30 s at 0 mV between sweeps.
- A 100 ms, 10 mV prepulse normalised Gj.
- The pipette solution held, in mM, 10 NaCl, 140 KCl, 1 MgCl₂, 0.2 CaCl₂, 3 Mg-ATP, 5 HEPES
  (pH 7.2) and 2 EGTA. The bath was a bicarbonate external solution at pH 7.4.
- The patch-clamp Methods state no recording temperature.

**The kinetics.**
- "Ij traces (recorded at −100 mV, Vj) were fitted with standard single or double exponential
  equation".
- "All wild type GJs in our experiment showed double exponential decay of Ij."
- **The sign of the voltage is inconsistent in the source.** Table 2's footnote and Figure S2's
  caption say a "100 mV" step; the Methods and Results say −100 mV.

**Table 2, wild-type Cx43, n = 7, means ± SEM:**

| Polarity | Gmin | V0 (mV) | A | τ column, headed "τ1 and τ2, (ms)" |
| --- | --- | --- | --- | --- |
| + | 0.35 ± 0.01 | +57 ± 0.5 | 7.9 ± 0.7 | 70 ± 5 |
| − | 0.33 ± 0.01 | −56 ± 0.5 | 8.4 ± 1.2 | 931 ± 54 |

- **The steady state.** The table's Boltzmann is Gj(ss) = (Gjmax − Gjmin)/(1 + exp[A(Vj − V0)]) +
  Gjmin, with Gjmax = 1. The steps last 20 s, about 21 times the slow time constant, so the end
  value is steady (**S**).
- **The slope A is printed without a unit.** The text defines it as zq/kT. A gating charge needs its
  unit, which this note does not guess.
- **The two time constants are one decay's.**
  - The τ column holds one value per row under one header, "τ1 and τ2".
  - The variants follow the same layout: Cx43-C40 has 99 ± 7 and 1046 ± 68 ms. Cx43-eGFP and
    Cx43-Δ257 have only the second value (1804 ± 193 and 2234 ± 176 ms), as single exponentials.
  - So the two wild-type values are read, as the review read them, as the fast and slow components
    of one decay.
- **What the paper does not give:** the two components' amplitudes, and any tracer or dye-transfer
  measurement (its dyes image calcium and pH only).
- **Its own reading:** "Fast time constant and slow time constant of voltage relaxation reflect
  closure of fast gate and slow gate respectively."

### 2.2 Moreno et al. (2002), not read

Circ Res, doi:10.1161/hh0402.105667.
- The publisher's page returned HTTP 403 to this note's fetch. As instructed, no other host was
  tried.
- **The numbers here are the review's,** not read for this note (FR-30;
  `lean/claims/junction-gate.md`): fast and slow times of 0.25 ± 0.04 and 3.18 ± 0.12 s at 60 mV, in
  wild-type Cx43 N2a pairs (its Fig. 5A and Table 2).
- They are used for nothing but the argument of §6.

### 2.3 What the two studies fix, and what they leave free (S)

- **One preparation, one voltage.** The steady state at both polarities and two time constants at a
  single voltage fit a two-gate law's constants at that voltage only. Each gate's rates vary with
  voltage, and one voltage cannot show how.
- **The components' amplitudes are missing.** They are what split the steady reduction between the
  two gates. Without them, the gates' residual floors are fixed only as a product.
- **Two labs, two voltages** (−100 mV against 60 mV) mix voltage with preparation: cells, construct,
  temperature and junction size. They are two sources, not a series (D248's rule for
  corroboration).

## 3. Options for the law's form

All four keep the existing law. They differ in mechanism, in the decay's shape, and in their
interface.

| Option | Form | Decay at a fixed voltage | Consistency | Interface |
| --- | --- | --- | --- | --- |
| **(A) Two gates in series** | g = c_f·c_s, with each c_i = r_i + (1 − r_i)·x_i a two-state gate | Three exponentials: k_f, k_s and k_f + k_s. With k_f ≫ k_s the third is about k_f, so a two-exponential fit sees τ_f and τ_s (**S**) | Each two-state gate keeps detailed balance, and independent gates form a product chain that satisfies Kolmogorov's test exactly (**S**) | Each gate is today's `kinetics → Rates` and `rhs`. Today's law is the one-gate case |
| (B) A sequential chain, O ⇌ R ⇌ C | A fast step to a residual state R, then a slow step to closed. g = P_O + γ_R·P_R | Exactly two exponentials: the eigenvalues of a 2 × 2 generator | No cycle, so detailed balance holds (**S**) | A generator per edge. Today's `Rates` does not describe it, and the exact step needs the eigen-decomposition |
| (C) Two parallel populations | g = w·g₁ + (1 − w)·g₂ | Exactly two exponentials | Each population is consistent | A weight w with no mechanism: a curve fit. Refused as a mechanism |
| (D) Four-state contingent gating | One fast gate per hemichannel (Paulauskas et al. 2009, from memory) | Several | Detailed balance by construction | The mechanism for heterotypic junctions: FR-16, later |

**Why (A).**
- It is the paper's own reading: a fast gate and a slow gate (§2.1). Two gates in series in each
  channel is the textbook picture of Cx43 (Bukauskas and Verselis 2004, from memory).
- It changes no existing function: each gate is today's gate.
- Its exact constant-voltage step is two of today's exact steps.
- (B) is the alternative if the slow gate is shown to close only from the fast gate's residual
  state, the contingent case. The data read here cannot tell (A) from (B): that needs amplitudes
  against time and voltage.

## 4. The law (recommended)

### 4.1 Form (S)

**One gate**, i in {fast, slow}:
- open fraction x_i in [0, 1], and conductance factor c_i = r_i + (1 − r_i)·x_i in [r_i, 1];
- dc_i/dt = α_i(1 − c_i) − β_i(c_i − r_i): today's `rhs`, with r_i in place of the minimum.

**Two kinds of gate**, chosen per gate and fixed at parse:
- **`threshold_relaxation`:** today's α and β, with a threshold. This is today's law exactly.
- **`boltzmann_eyring`:** a two-state gate in |V|, for cited constants.
  - With u_i = A_i·(|V| − V0_i): α_i = λ_i·exp(−δ_i·u_i) opens, and β_i = λ_i·exp((1 − δ_i)·u_i)
    closes.
  - So α_i/β_i = exp(−u_i): detailed balance, with a Boltzmann steady state
    x_i∞ = 1/(1 + exp(u_i)) whose midpoint is V0_i and slope A_i.
  - The relaxation rate k_i = α_i + β_i is smallest near V0_i, the bell-shaped τ(V) of voltage
    gates.
  - δ_i in [0, 1] splits the voltage dependence between the two directions. It is a kinetic choice,
    declared per gate, and it never moves the steady state.

**The junction:**
- g = c_f·c_s, in [r_f·r_s, 1];
- at a steady state, g∞(V) = Π_i (r_i + (1 − r_i)·x_i∞(V));
- at a fixed V, each c_i(t) = c_i∞ + (c_i(0) − c_i∞)·exp(−k_i t) exactly. So the junction's exact
  constant-voltage step is the product of two of today's `advance_clamped`.

**Polarity.** Homotypic, so every rate is a function of |V|, as today. Per-hemichannel polarity,
which heterotypic junctions need, is (D)'s.

**Domain:** |V| ≤ max_abs_voltage_V (0.120 V, today's); c_i in [r_i, 1]; λ_i > 0; A_i ≥ 0;
δ_i in [0, 1]; r_i in [0, 1]. A_i·max|V| is bounded so that every exponential stays finite, and a
law whose rates could overflow on the domain is refused at parse.

### 4.2 What a fit to Sahu and Bera can and cannot be (S)

- **What can be set at −100 mV:** k_f = 1/0.070 s and k_s = 1/0.931 s. The steady Boltzmann at each
  polarity constrains the product of the two gates' steady factors.
- **That fixes the constants at one voltage.** The two gates' midpoints, slopes and splits, and the
  split of the residual between them, stay free. So a development fit reproduces its own inputs and
  predicts nothing.
- **It may be run as a development record.** It shows that the law's decay has the source's
  two-phase shape, and makes no claim.

## 5. The interface against today's

- **Per gate, unchanged.** Each gate keeps today's signatures exactly:
  - `kinetics(voltage, parameters, *, xp) → Rates(alpha_per_s, beta_per_s, target, relaxation_per_s)`,
    where target is the steady c_i and relaxation is α_i + β_i;
  - `rhs`, `advance_clamped` and `domain_valid`.
  - A gate kind adds only its own `Parameters` NamedTuple: the threshold and minimum for
    `threshold_relaxation`; λ, A, V0, δ and r for `boltzmann_eyring`.
- **The law adds:**
  - `gate_count`: m, static, so it selects the program. m is 1 for every existing law;
  - `conductance(gates) → g`: the product, the identity when m = 1;
  - `open_fractions(gates, parameters) → x_i` for routes (§7).
- **`JunctionLaw` gains** `gate_count`, defaulting to 1, and `conductance`, defaulting to the
  identity. Every existing declaration stays valid unchanged.
- **@3's step after N2:**
  - `state.junction_gate` stays [edge] when m = 1, and becomes [edge, m] only for a law with m > 1,
    branched on the structure at trace time;
  - the step multiplies `control.junction` by `conductance(...)`;
  - `junction_gate_rhs` returns each gate's derivative, and the domain check runs per gate;
  - records keep `junction_gate` [row, edge] when m = 1. An m > 1 law writes `junction_gates`
    [row, edge, gate] and `junction_conductance` [row, edge], declared only when present.

## 6. A voltage series: what a prediction needs

**Everything in one preparation:** cells, an untagged homotypic wild-type construct, the temperature
stated, the solutions, the prepulse and its normalisation, junction sizes with any series-resistance
correction stated (a large Gj distorts its own kinetics), and n with its errors. For each of several
junctional voltages, at both polarities, spanning the steady Boltzmann's drop (for example ±20 to
±120 mV in steps of 20 mV or less):

1. **The full decay** of normalised Gj during the step, or both components' time constants and
   amplitudes with their errors. Amplitudes are what split the steady reduction between the gates
   (§2.3).
2. **The end-of-step conductance,** long enough to be steady.
3. **The recovery at 0 mV after the step:** its time constants. They fix the reopening rates
   independently of the closing ones.

**A split declared before any fit.** For example, calibrate on the steady Boltzmann and the kinetics
at two voltages, and predict the kinetics at the others, with a band registered before the
comparison (D248).

**What the two studies give:**
- Sahu and Bera meet the one-preparation rule. But they give the kinetics at one voltage, without
  amplitudes or recovery.
- Moreno et al. give one other voltage from another preparation, and were not read.
- Neither, nor both together, is a series. Until one is found, FR-30's law is development only at
  −100 mV.

## 7. Tracer transfer kept apart from electrical coupling

- **The physics** (from memory). A connexin's fast gate closes to a residual state that still
  passes small ions but excludes larger tracers. So electrical coupling and dye transfer can differ.
  FR-16's F4 is the same finding for miRNA.
- **In the law.**
  - The ionic conductance is g = Π_i (r_i + (1 − r_i)·x_i).
  - A route declares its own residual ρ_i per gate. Its factor is Π_i (ρ_i + (1 − ρ_i)·x_i), with
    ρ_i = r_i for small ions and possibly 0 for a large tracer.
  - The law exposes the open fractions x_i (§5). It never offers g as a tracer's factor.
  - With one gate this is F4's per-route floor, so FR-30 and FR-16 meet at one interface.
- **In tests and comparisons:**
  - The electrical comparison uses Gj data only.
  - A tracer comparison needs its own dye-transfer data. Sahu and Bera report none.
  - Neither is calibrated on the other, and each is registered separately.

## 8. Files and owners

**Free now** (interface-preserving, the lead's ruling):
- `src/cells/laws/junctions/junction_series_gates.py` (new): the gate kinds, the series law, its
  exact step, its domain and its registration;
- `src/cells/laws/junctions/junction_gate.py`: its re-exports, if any new name needs them.

**The F owner's:** `src/cells/registry/laws.py` (`JunctionLaw`'s two defaulted fields), and the law's
registration (`src/cells/models/inner_laws.py`, `src/cells/registry/model_table.py`).

**The @3 owner's, after N2 lands** (about 01:00 UTC):
- `src/cells/models/surface_pump_v3.py`: the state [edge, m], the step, the derivative, the domain
  and the records;
- `src/cells/models/surface_kinetic.py`: the per-gate parameter layout;
- `src/cells/definitions/surface_pump_spec.py` and `partition_spec.py`: the parse of the law and its
  per-gate parameters, and today's check that names `junction_voltage_relaxation@1`.

**FR-16's:** the catalogue's Cx43 homotypic parameter set, with each cited value and its source.

**Validation:** a comparison driver, once a voltage series exists.

**Not edited:** `lean/`. The Lean project's claims follow from its own generator.

## 9. What stays bitwise

- **Every existing world** with `junction_voltage_relaxation@1`:
  - the law's module is unchanged;
  - m = 1 keeps the [edge] state, the programs (branched at trace time), the records and the
    refusal messages.
- **crossrev's sets, G1's 113 worlds and FR's landing set:** none of their worlds declares the new
  law.
- **The Lean project's junction-gate claim:** its subject law is unchanged.
- **No new key is written** unless a world declares the new law.

## 10. Tests (D224)

**`tests/unit/test_junction_series_gates.py`** (new, host only, about 1–2 s). Each claim has its
planted error:
- **Each gate keeps detailed balance:** α/β = exp(−u), and x∞ is the Boltzmann. Planted: δ applied
  to one direction only.
- **The exact step:** two gates' exact step against a fine numerical integration. Planted: the
  product's cross term dropped.
- **The one-gate reduction:** m = 1 with `threshold_relaxation` equals today's `rhs` and
  `advance_clamped` bitwise. Planted: the residual applied twice.
- **Two relaxation times:** a decay from open, with k_f ≫ k_s, fitted by two exponentials, recovers
  k_f and k_s within a stated tolerance.
- **Polarity symmetry** and the domain's refusals.

**After N2:** one row in an existing @3 junction test, a two-cell world with m = 2, with its seconds
stated. Its tier row is measured on the timed lane.

## 11. Price (agent-days, gates excluded)

| Item | Days |
| --- | --- |
| The law module: gate kinds, the series, the exact step, the domain, the registration; and its host tests | 1–1.5 |
| `JunctionLaw`'s two defaulted fields, and the one-gate reduction's tests | 0.5 |
| @3's integration after N2: the state [edge, m], the step, the derivative, the records and the parse | 1.5–2 |
| The development record at −100 mV (§4.2) | 0.25–0.5 |
| A voltage-series comparison driver, once data exist | 0.5–1 |
| **Total** | **3.75–5.5** |

The search for an open-access voltage series is not priced.

## 12. Questions for the lead

1. **Approve (A),** two gates in series, each a two-state gate (the threshold kind or the Boltzmann–Eyring
   kind), with today's law as the one-gate case? Or (B), the sequential chain?
2. **Moreno et al.:** the fetch was refused (HTTP 403). Keep its numbers as the review's report and
   use them for nothing, or obtain the paper another way, for example as a copy the user downloads?
3. **The voltage series:** who searches for an open-access homotypic Cx43 series in one
   preparation (§6)? Until one exists, the law is development only.
4. **The interface:** two defaulted fields on `JunctionLaw` (the F owner), or a new interface
   version for gate-vector junction laws?
5. **The units of A** in Sahu and Bera's Table 2 are not printed. Is a source needed before any
   gating charge is quoted?

## 13. Registered benchmark: Lin, Crye and Veenstra (2003), before the paper is opened

**Entry of 22:16 UTC on 21 November 2026.** Written by the @3 owner, FR-30's integrator, at the
lead's direction under the user's delegation (D273). Nobody on this project has yet opened the
paper (Circ Res, doi:10.1161/01.RES.0000093379.61888.35); the user is downloading it. The rules
below are fixed before it is read, and the commit carrying them is tagged
`fr30-lin2003-registered-2026-11-21`. Any change after the paper is opened is a dated amendment
that says what had been seen.

**What has been read about it (disclosure).**
- Nothing of its content. The project's files only name it: docs/DECISIONS.md, where the lead
  chooses it as the first benchmark, and FR-30's row in docs/FEATURE_REQUESTS.md. I read only the
  citation in each.
- lean/claims/incoming/biological-evidence.md cites a different paper from the same laboratory
  (Lin and Veenstra 2007). I have not read that entry.
- **Notes that name it, which I have not opened.** A search of /mnt/workspaces/Cells's notes
  (.md, .txt) for the second author's name and the DOI found three files. They may describe its
  content:
  - the FR-7 agent's notes, `fr7-loop-20261119/u2-compartment/NOTES.md`;
  - a full text that agent fetched in its FR-30 search, of a 2005 paper from the same laboratory:
    `fr7-loop-20261119/u2-compartment/fr30-search/lin2005_PMC2752676.txt`;
  - the lead's notes, `d172-restructure-20261115-01/LEAD-NOTES.md`.

  I saw only their names. The fitter does not open them (rule 5). The other matches were
  simulation output (visualizer JSON), where the letters occur by chance in encoded data.
- From training data I recall the paper's title, approximately "Regulation of connexin43 gap
  junctional conductance by ventricular action potentials". I also recall that it concerns Cx43
  junctional conductance and its transjunctional-voltage dependence in cell pairs. I recall no
  figure, protocol, voltage, time constant, amplitude or conductance value from it.

**One paper.** Labs cannot be pooled, so the fit and the held-out test both come from this paper's
own data.

**The host: the law clamped, not an @3 world.**
- The prediction is the law's clamped evaluation, `junction_series_gates.advance_clamped`, at each
  held transjunctional voltage V_j. The junction voltage is imposed, as Lin's dual whole-cell
  clamp imposes each cell's voltage, and each gate relaxes exactly at that voltage.
- This mirrors the experiment and does not depend on fix (A).
- @3 cannot impose V_j. Its reservoirs hold outside nodes only, and no operator holds a cell's
  voltage.
- `series_world()`, FR-30's development host, is the @3 closed fixture. Its junction crosses two
  floating capacitor components and conducts from t = 0, and there the junction converges at
  first order (about 1.2 under N2). Judging on it would require (A) to land first.
- An @3 world whose cells each face their own reservoir has no floating component, and it may
  carry the fitted law as a numerics check against the clamped evaluation. It is not the
  benchmark.

**1. The split rule.**
- **The data unit:** a V_j step (signed, mV) at which the paper reports the junctional
  conductance's decay. Its values may be its relaxation times and their amplitudes, and its
  steady-state conductance. They may come as values in the text or tables, as plotted points
  (digitized), or as traces (digitized, then fitted by the extractor with the paper's own form).
- **The order:** the extractor lists, for each polarity, the distinct |V_j| magnitudes at which
  the paper reports relaxation data, sorted ascending.
- **Held out:** the interior magnitudes at even rank (the 2nd, 4th, 6th, ...).
  - The smallest and the largest magnitudes always stay in training, so every held-out voltage is
    an interpolation.
  - With exactly three magnitudes, the 2nd is held out.
  - With two or fewer, the benchmark is undetermined and is reported so.
- **Polarities:** where the paper reports both, the same magnitudes are held out at both.
- **Every observable at a held-out voltage is held out:** its relaxation times, amplitudes and
  steady-state conductance. Steady-state points at magnitudes without relaxation data follow the
  same rank rule on their own sorted list.
- **The files:** the extractor applies the rule mechanically and writes `train.json` and
  `held_out.json`. A dated entry records the held-out file's SHA-256 before the fitter starts.

**2. The judged observables, as the series gates predict them.** At each held-out V_j:
- the two relaxation times, τ_fast and τ_slow;
- their amplitudes, A_fast and A_slow, as fractions of the initial conductance;
- the steady-state conductance, G_ss/G_0, normalized as the paper normalizes it.

The prediction is read the way the paper reads its data.
- The law's conductance trace is computed for the paper's step protocol: its holding level, step
  duration and sampling, which the extractor records from the methods. Each gate starts at its
  steady state at the holding voltage.
- That trace is fitted with the paper's two-exponential form, window and offset rule.
- The product of two relaxing gates carries a third rate, λ₁ + λ₂. So the fitted times of the
  predicted trace are compared, not the gates' own rates.

**3. The fit.** The fitter fits junction_series_gates@1 to `train.json` only. It chooses each
gate's kind (threshold_relaxation or boltzmann_eyring) and its parameters, residuals included,
and states the kinds before scoring.

**4. The pass rule.**
- **Each comparison at a held-out voltage:**
  - a relaxation time passes if |ln(predicted/observed)| ≤ ln 1.25;
  - an amplitude passes if |predicted − observed| ≤ 0.10 of G_0;
  - G_ss/G_0 passes if |predicted − observed| ≤ 0.05.
  - In each case, twice the paper's reported SEM at that voltage replaces the tolerance where it
    is wider.
- **The benchmark passes** if all three hold:
  - every G_ss comparison passes;
  - each of τ_fast, τ_slow, A_fast and A_slow passes at more than half of the held-out voltages;
  - at least 75% of all relaxation comparisons pass.
- **Undetermined** if fewer than two held-out voltages carry both relaxation times.
- **Cannot predict** if the fitted law leaves its domain at a held-out voltage.
- The in-sample fit is reported, not judged.

**5. Roles.**
- **The extractor** (one agent) reads the paper, records the protocol, digitizes, applies the
  split and records the hash. It does not fit.
- **The fitter** (another agent) does not open the paper, `held_out.json` or the three notes
  named above. It works from `train.json`, which carries the protocol and the held-out voltages but
  none of their values, and writes `predictions.json`.
- **The checker** (a third agent) scores `predictions.json` against `held_out.json` by rule 4 and
  writes the verdict. Disagreements go to the lead.

**6. What it decides.**
- A pass is evidence for the law's voltage dependence under this paper's conditions only.
- It does not lift D262's development flag. That stays until the lead and the user decide.

### 13.1 Amendment of 23:16 UTC on 21 November 2026: Lin undetermined; three fallbacks, in order, before any is opened

Written by the @3 owner, FR-30's fitter, at the lead's direction (D276). Nobody has opened the three
papers below. They sit in `/mnt/datasets/Cells/papers/incoming/<name>/`, and the commit carrying
this amendment is tagged `fr30-fallbacks-registered-2026-11-21`.

**Lin, Crye and Veenstra (2003) is undetermined.**
- The paper fits each step's decay with a single exponential, and it reports one τ per |V_j|.
  It gives no τ_slow, no amplitudes and no step-end conductance.
- So no held-out voltage carries both relaxation times, and rule 4 makes the result
  undetermined.
- Its held-out file is sealed, with its digest on main (36ccc20d, D276).
- Nothing from Lin is reinterpreted, re-split or re-scored under the rules below. I have seen no
  value from it.

**The fallbacks, in this order.** Each is extracted only if the one before it is undetermined.
1. Desplantez et al. (2004), Pflügers Arch 448:363 (`desplantez-2004`).
2. Moreno et al. (2002), Circ Res 90:450 (`moreno-2002`).
3. Snipas et al. (2020), Biophys J 119:1640 (`snipas-2020`).

§13's split rule, judged observables, pass rule and roles apply to each, completed by the points
below. If all three are undetermined, the benchmark is undetermined, and the lead decides what
follows.

**What has been read about them (disclosure).**
- **Moreno et al. (2002).** This record already carries two of its values: 0.25 and 3.18 s at
  60 mV, as a review reports them (§2.2 and this note's summary table). I have read those lines,
  so 60 mV is not a blind voltage for me (point 8 below).
- **Desplantez et al. (2004) and Snipas et al. (2020).** I have seen no content from either.
  From training data I recall only their approximate subjects: Cx43 and Cx45 junctional gating
  for Desplantez, and a kinetic model of Cx43 gating for Snipas. I recall no values.
- **Files that name these papers, which I have not opened:**
  - docs/DECISIONS.md, the lead's entries;
  - the FR-7 agent's `fr7-loop-20261119/u2-compartment/NOTES.md`;
  - a full text that agent fetched, `fr7-loop-20261119/u2-compartment/fr30-search/maciunas2023_PMC10491658.txt`.

**Points the Lin extraction showed §13 leaves open, fixed now without any value.**
1. **Only decays are ranked.** The ranked data units are the inactivation decays at steps away
   from the holding level.
   - Recovery steps, for example a return to 0 mV after a step, are not ranked and never held
     out.
   - Recovery data may enter training only, through the law's own prediction of the recovery
     protocol as recorded.
2. **Polarity.** Where decays are reported by |V_j|, as pooled or polarity-averaged values, each
   |V_j| is one data unit, and the law is predicted at that magnitude. Where the paper reports each
   polarity, §13's rule holds: the same magnitudes are held out at both polarities.
3. **Ramp-derived steady state.** Conductance derived from a voltage ramp does not stand in for a
   step-end G_ss, and it is not judged. It may enter training only, through the law's own
   prediction of the recorded ramp.
4. **SD or SEM.** The widening rule uses twice the SEM. Where the paper reports an SD with n, the
   SEM is SD/√n. An SD without n, or a range, does not widen a tolerance.
5. **One time constant at a voltage.** A held-out voltage that carries one reported τ gives no
   relaxation comparison. Its G_ss, if reported, is still judged. Rule 4's "both relaxation
   times" condition stands.
6. **Homotypic Cx43 only.** Only homotypic Cx43–Cx43 data are extracted. Heterotypic and other
   connexins' data, which Desplantez et al. also report, are excluded from the files.
7. **The holding level and protocol** are recorded by the extractor. The fitter predicts each
   step from the law's steady state at the holding level, as §13 says.
8. **A voltage already seen is not held out.**
   - A magnitude whose values the fitter has already seen stays in training: for Moreno et al.,
     60 mV.
   - The rank rule then runs over the remaining interior magnitudes.
   - If this leaves fewer magnitudes than §13 needs, the paper is undetermined.

**The fitter's exclusions, added to §13's.** The fitter does not open:
- the scratch folder `cx43-search/` in the shared session scratchpad;
- each paper's sealed digitizer scripts;
- the three files named above;
- the papers themselves.

The fitter works from `train.json` alone.

### 13.2 Entry of 00:34 UTC on 22 November 2026: Sahu and Bera (2013) under §13 and §13.1, and a rule for missing amplitudes

Written by the @3 owner, FR-30's fitter, at the lead's direction under the user's overnight
delegation (D277). All four registered papers are undetermined, each confirmed by the checker:
- Lin: single-exponential decays only;
- Desplantez: the second exponential is "data not shown";
- Moreno: both times at only three magnitudes;
- Snipas: ramps only, no step decays.

The lead proposed Sahu and Bera (2013), PLoS ONE, doi:10.1371/journal.pone.0060506 (PMC3607587,
CC BY). The Lean lane pointed to it. This commit is tagged `fr30-sahu2013-registered-2026-11-22`.

**Disclosure: this paper is not unread.**
- It was read for this note on 20 November 2026. §2.1 records its protocol, its Table 2 and its
  own statements, and §4.2 says what a fit to it can be. FR-30's law cites it
  (`junction_series_gates.LAW`, with its departures).
- I have read §2.1, §4.2 and the law's citation, in this note and in that module. So I have seen:
  - the protocol: N2a cell pairs, dual whole-cell clamp, steps from −120 to +120 mV in 20 mV
    increments of 20 s each;
  - Table 2's wild-type Cx43 row: per polarity, Gmin, V0 and A of a steady-state Boltzmann, with
    the two decay times 70 ± 5 and 931 ± 54 ms;
  - the paper's statement that the decays were fitted at −100 mV.
- I have not opened the paper itself. The lead's message relayed the Lean lane's pointer.

**§13 with §13.1's fixes, unchanged, decides it before extraction: undetermined.**
- **Relaxation data:** both times are reported at one voltage only, −100 mV.
  - §13's rank rule therefore has one magnitude, and with two or fewer the paper is undetermined.
  - That magnitude has also been seen, so by §13.1's point 8 it stays in training. No relaxation
    voltage is left to hold out.
- **The steady state:** the record already carries the steady-state Boltzmann's parameters for
  each polarity. Those determine G_ss at every step voltage, so no G_ss magnitude is unseen either
  (§13.1's point 8).
- So the paper cannot be a held-out test of the law. It stays what §4.2 calls it: a development
  record that reproduces its own inputs. No extraction under §13 is needed for this paper, and none
  would change this.

**A rule for missing amplitudes, decided now for any later paper and without its values.** It
applies when a paper reports both relaxation times at held-out voltages but no amplitudes.
- **Judged:** the two times, and G_ss where the paper reports it.
- **Recorded as not reported:** the amplitude observables. No amplitude is inferred, for example
  from a figure's trace shape, and none is counted as passing or failing.
- **The pass rule** then counts the reported observables only:
  - every reported G_ss comparison passes;
  - τ_fast and τ_slow each pass at more than half of the held-out voltages;
  - at least 75% of the τ comparisons pass.
- **The principle:** the pass rule judges what the source reports. Dropping an unreported
  observable neither raises nor lowers the bar on the reported ones.
- **Unchanged:** a paper with one time per voltage stays undetermined (§13.1's point 5).

**What follows** is the user's and the lead's decision: another paper with step decays at several
magnitudes, registered and sealed the same way, or FR-30 staying development only.

### 13.3 Entry of 10:40 UTC on 22 November 2026: three candidates in order, and native myocyte pairs, before any is read

Written by the @3 owner, FR-30's fitter, at the lead's direction (D280, the source search). Nobody
on this project has read these papers. The lead will fetch the open-access ones into their folders
for the extractor after this commit, which is tagged `fr30-candidates3-registered-2026-11-22`.

**The order.** Each paper is extracted only if the one before it is undetermined.
1. **Xu et al. (2013)**, Front Pharmacol 4:44, doi:10.3389/fphar.2013.00044, PMC3625725, CC BY.
   Neonatal mouse ventricular myocyte pairs, dual whole-cell clamp, the control arm only. It comes
   from the same laboratory as Lin (2003), with different data.
2. **Lin et al. (2010)**, J Mol Cell Cardiol 48:238, doi:10.1016/j.yjmcc.2009.05.014,
   PMC2813328, a free author manuscript. Ventricular myocytes.
3. **Ek-Vitorín et al. (2018)**, Int J Mol Sci 19:1659, doi:10.3390/ijms19061659, PMC6032060,
   CC BY. Wild-type Cx43 in Rin43 cell pairs.

§13's split rule, judged observables and pass rule apply unchanged to each, with §13.1's fixes and
§13.2's missing-amplitude rule. If all three are undetermined, the lead and the user decide what
follows.

**What has been read about them (disclosure).** Only the source search's caption-level reading,
which the lead relayed. It locates each paper's data and gives no value:
- Xu et al.: fast and slow time constants, said to be in Fig 7D–F. The number of |V_j| magnitudes
  is unknown.
- Lin et al. (2010): fast and slow inactivation, said to be in Fig 5A–D.
- Ek-Vitorín et al.: second-order decay fits, probably at a single ±80 mV. If so, it is
  undetermined under §13's rank rule.

Lin et al. (2005) (PMC2752676) is excluded as seen. The FR-7 agent's search fetched its full text
(§13), and I have not opened it. The fitter also does not open the source search's notes on these
papers.

**Native myocyte pairs: admitted, under a separate and narrower claim.**
- **The question.** Do native ventricular myocyte pairs count as "homotypic Cx43" under §13.1's
  point 6? Their junctions are Cx43-dominated, but the composition of a native junction is not
  controlled. Other connexins may be present, Cx45 above all in neonatal ventricle. They could
  form heteromeric or heterotypic channels, whose transjunctional gating differs.
- **Point 6 stays as written.** It was fixed so that a benchmark judges one channel type, and an
  expression system with wild-type Cx43 alone (such as Ek-Vitorín's Rin43 pairs) meets it. A
  native pair does not, since nothing in it shows that one channel type carries the current.
- **The decision.** Native pairs are admitted, and their verdict is labelled "Cx43-dominated native
  ventricular junctions", never "homotypic Cx43":
  - **Pass:** evidence that the law, with fitted effective parameters, describes those native
    junctions' voltage-dependent relaxation.
  - **Not claimed:** that it describes homotypic Cx43 channels.
  - **The parameters** fitted to native pairs are the native mixture's, and are not entered as
    Cx43's.
  - **Within a native paper:** only the control arm is extracted. No knockout, knockdown,
    pharmacological or mutant arm is used, and no arm with another connexin's expression changed.
- **Why admit rather than exclude.** FR-30's law serves tissue models (FR-16), whose junctions are
  native, Cx43-dominated ones, so a native benchmark tests the law where it will be used. Stating
  the narrower claim keeps the benchmark honest. Excluding native pairs would leave one candidate
  that is probably undetermined, so the search would most likely end with no test at all.

## Sources

- **Read:**
  - FR-30 and FR-16 in FEATURE_REQUESTS.md;
  - D248, D249 and D255;
  - GAP_JUNCTION_CANCER_REPLICATION.md (F3, F4) and PROTEIN_CATALOGUE_PLAN.md (the Cx43 case);
  - the Lean project's `lean/claims/junction-gate.md` and its evidence note.
- **Code read:**
  - `src/cells/laws/junctions/junction_voltage_relaxation.py` and `junction_gate.py`;
  - `JunctionLaw` in `src/cells/registry/laws.py`;
  - the gate's call sites in `src/cells/models/surface_pump_v3.py` and `surface_kinetic.py`.
- **Paper read:** Sahu and Bera (2013), PLoS ONE, doi:10.1371/journal.pone.0060506 (PMC3607587,
  CC BY): Methods, Results, Table 2 and its footnote, and Figure S2's caption.
- **Not read** (the fetch was refused, HTTP 403): Moreno et al. (2002), Circ Res,
  doi:10.1161/hh0402.105667. Its numbers are quoted as FR-30 and the review state them.
- **From memory, not read for this note:**
  - Chen-Izu, Moreno and Spangler (2001) on two-state connexin gating;
  - Bukauskas and Verselis (2004) on fast and slow gates and the residual state's selectivity;
  - Paulauskas et al. (2009) on four-state contingent gating.
