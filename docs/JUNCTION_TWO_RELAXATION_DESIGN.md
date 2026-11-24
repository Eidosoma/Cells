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

### 13.4 Entry of 15:30 UTC on 22 November 2026: a fourth candidate list, in order, before any is read

Written by the lead, after section 13.3's candidates all came out undetermined (D291) and the user chose one
more metadata-only search (D292). Nobody on this project has read these papers' results. The search
read titles, abstracts, query matches and stated conditions only, and its full-text checks were
blocked by PMC's browser check. This entry is tagged `fr30-candidates4-registered-2026-11-22` before
any extraction.

**The order.** Each paper is extracted only if the one before it is undetermined. Section 13's split
rule, judged observables and pass rule apply unchanged, with section 13.1's fixes, section 13.2's
missing-amplitude rule, the Xu ruling (D291: on-rates without P_open are undetermined) and section
13.3's native admission. The search's own suggested reading of the held-out voltage count is not part
of the rule.
1. **Shibayama et al. (2006)**, Biophys J 91:4054, doi:10.1529/biophysj.106.085787, PMC1635665. The
   wild-type Cx43 arm only; the His-142 mutants are not used.
2. **Elenes et al. (2001)**, Biophys J 81:1406, doi:10.1016/S0006-3495(01)75796-7, PMC1301620. The
   homotypic Cx43 arm only.
3. **Revilla, Castro and Barrio (1999)**, Biophys J 77:1374, doi:10.1016/S0006-3495(99)76986-9,
   PMC1300426. Xenopus oocyte pairs.
4. **Ek-Vitorín, Pontifex and Burt (2016)**, Biophys J 110:127, doi:10.1016/j.bpj.2015.10.054,
   PMC4805864. Wild-type Cx43 only.
5. **Bukauskas et al. (2001)**, Biophys J 81:137, doi:10.1016/S0006-3495(01)75687-1, PMC1301499.
6. **Rackauskas et al. (2007)**, Biophys J 92:1952, doi:10.1529/biophysj.106.099358, PMC1861779.
7. **Wang et al. (1992)**, Biophys J 63:139, doi:10.1016/S0006-3495(92)81573-4, PMC1262131. Native
   neonatal myocyte pairs, under section 13.3's native admission and its narrower claim, and only if
   they are ventricular.
8. **Moreno et al. (1994)**, Biophys J 67:113, doi:10.1016/S0006-3495(94)80460-6, PMC1225340.
9. **Lin, Xu and Veenstra (2014)**, Channels 8:433, doi:10.4161/19336950.2014.949188, PMC4594514.

Papers 1 to 4 matched a full-text query for two-exponential wording with Cx43 and transjunctional
voltage. A match is not a reading: it may come from another connexin or from a hemichannel passage.

**Excluded, from the search's reading of text and conditions:**
- Lin et al. 2008: on-rates without P_open per voltage (the Xu ruling).
- Hoang, Qian and Ripps 2010: two exponentials at one voltage only.
- Desplantez et al. 2011: the fast constant only. Its untagged wild-type Cx43 panels are also replotted
  from the excluded Desplantez 2004, and must not be read by the extractor or the fitter.
- Lübkemeier et al. 2013: a mutant, measured with ramps.
- Banach and Weingart 1996 and 2000; Valiunas et al. 2000; Xu et al. 2012; Vogel and Weingart 1998;
  Desplantez 2017.
- Maciunas 2023, which the FR-7 agent has already fetched.

**What has been read (disclosure).** Only the search's metadata. It recorded no time constant, rate,
amplitude, P_open or conductance value for any candidate. The search's file is
/mnt/workspaces/Cells/fr30-search-20261122/candidates.md, and the fitter does not open it.

### 13.5 Entry of 13:55 UTC on 23 November 2026: Revilla, Castro and Barrio (1999), the prediction, readout and scoring conventions and their code, before any fit

Written by FR-30's harness author, who becomes its fitter after the tag, at the lead's direction
(D311). It pins the conventions of the lead's draft (call 3 of
/mnt/workspaces/Cells/fr30-benchmark-20261123/RULING_DRAFT.md) and section 13's rule 4 with D311's
consequences. It also names the code that applies them, which exists at this entry's tag (D308).
The commit carrying it is to be tagged `fr30-revilla1999-registered-2026-11-23` before any fit. No
fit has been made, and the code has met no held-out value. Its tests and its end-to-end smoke use
invented inputs. Its reader ran twice on the training file fit.json (point 6): it parsed and
validated the training values in memory, and printed and compared none.

**What I have read (disclosure).**
- **Read:**
  - this note's sections 13 to 13.4 and its source list;
  - D276, D291, D292, D308 and D311, and the lead's draft;
  - the training files `revilla1999/extraction/fit.json` and `protocol.json`, values included;
  - the law's code (`junction_series_gates.py`, `junction_voltage_relaxation.py`,
    `junction_gate.py`) and the header of its unit test.
- **Other papers' values, seen through this note:** sections 13.1 and 13.2 print Moreno et al.
  (2002)'s two times at 60 mV, and Sahu and Bera (2013)'s protocol and Table 2's two decay times at
  -100 mV. Neither is this paper's.
- **Seen by name only:** a search for this section's heading printed four headings of sections 2 to
  4 (2.1, 3, 4 and 4.1). I read none of their text and nothing else of sections 1 to 12.
- **Not opened:**
  - anything under lean/, and the four papers;
  - `held_out.json` and every other file under `fr30-candidates4-extraction/`;
  - the earlier FR-30 extraction folders;
  - the source search's `candidates.md`, and the notes named in sections 13 and 13.1.
- **From training data** I recall this paper's title and subject: transjunctional voltage dependence
  of Cx32 and Cx43 junctions in oocyte pairs. I recall no value from its figures or tables. What I
  know of Cx43 gating in general comes from other work, not from this paper.

**The trace criterion (D311, the user's choice).** Superimposed or single sample records are not
refitted: only decays the paper itself analysed count.
- It resolves rule 1's "digitized, then fitted by the extractor" toward rule 5.
- It applies to this paper and binds every later candidate, fallbacks 5 to 9 included.
- It was fixed and hashed (4d5b1df8...) after Shibayama had been read, and before Elenes was opened
  or any value digitized.

**1. The prediction** (`predict(params, vj_mV, protocol)`).
- **The protocol:** each gate at its steady state at V_j = 0 (the target of the law's `kinetics` at
  0 V), then a 30-s step to V_j. Both oocytes are held at one level, so V_j = 0 before each step
  (protocol.json).
- **G_0:** the law's conductance at +10 mV immediately after the step from the 0-mV steady state,
  that is `advance_clamped` with dt = 0. This is the paper's brief 10-mV prepulse, with no
  relaxation. The law has no instantaneous voltage dependence, so G_0 equals the 0-mV steady
  conductance. It is computed, never assumed to be 1.
- **The trace:** one call of `advance_clamped` from that state at V_j, with dt the grid's times, so
  each sample is exact and none is chained. The grid is t_k = k ms, k = 0 to 30,000, from the
  step's onset.
- **G_ss/G_0:** the conductance at t = 30 s over G_0. It is the end-of-step value, never the fitted
  offset or an asymptote, and it is judged whatever the fit.
- **Cannot predict** (rule 4): `domain_valid` fails at the holding level, the prepulse, the step
  (dt = 30 s) or the end state; or the trace is not finite; or G_0 is not positive.
- **One parameter set at both polarities.**
  - Both gate kinds read |V_j|. The law declares this departure: one Boltzmann in |V|, symmetric in
    polarity, where the paper fits each polarity.
  - So one block of kinds and parameters, as the law is declared, gives the predictions at -80 and
    +80 mV, and the two are equal.
  - predictions.json carries that one block, and `verify` recomputes every prediction from it. A
    separate fit per polarity would be another law, and this entry does not admit it.

**2. The readout** (`readout(trace)`), on y = G/G_0 over 5 ms <= t <= 30 s, both ends included
(29,996 samples).
- **The form:** y = C + A_f exp(-t/tau_f) + A_s exp(-t/tau_s), with C free, by unweighted least
  squares. "Fast" means tau_f < tau_s, and the amplitudes are fractions of G_0.
- **Variable projection:** C, A_f and A_s by linear least squares at each (tau_f, tau_s).
- **The start:** the fixed log grid, tau_f in {0.05, 0.1, 0.2, 0.5, 1, 2} s and tau_s in {1, 2, 5,
  10, 20, 50} s with tau_f < tau_s (33 pairs). The pair with the smallest residual sum of squares
  starts the refinement; on a tie, the first in grid order (tau_f ascending, then tau_s).
- **The refinement, fixed beyond the draft:**
  - the projected residual over (ln tau_f, ln tau_s), unbounded;
  - Levenberg-Marquardt (SciPy's `least_squares`, method `lm`) with Kaufman's Jacobian;
  - xtol, ftol and gtol 1e-12, and at most 1,000 evaluations;
  - then C, A_f and A_s at the final pair, with the two terms sorted so that tau_f < tau_s.
- **Reported:** tau_f, tau_s, A_f, A_s, C, the residual's RMS, the grid start and the refinement's
  status, with each gate's rates at V_j.

**3. Degenerate fits.** A fit is degenerate if tau_s/tau_f < 1.5, if A_f or A_s is below 1e-3, or
if tau_s is above 300 s.
- **Fixed beyond the draft:**
  - "below 1e-3" is signed, so a negative amplitude (a rising term) is degenerate;
  - a refinement that does not converge, or that ends with a value that is not finite or a time
    that is not positive, is degenerate too.
- At a degenerate voltage both time comparisons fail, with the reasons recorded. Its G_ss/G_0 is
  still judged.

**4. The comparisons** (`score(predictions, held_out)`).
- **A time** passes if |ln(pred/obs)| <= ln 1.25 or |pred - obs| <= 2 SEM.
  - Both outcomes are recorded, with the tolerance that applied: the band edge farther from the
    observed value, on the prediction's side.
  - The ln band is asymmetric: -20% and +25%.
- **G_ss/G_0** passes if |pred - obs| <= max(0.05, 2 SEM), and the one that applied is recorded.
- **The SEM** is the held-out entry's own dispersion, where its type begins "SEM" (each point is the
  mean +- SEM of six pairs).
  - A null dispersion leaves the base tolerance alone (section 13.1, point 4).
  - Any other type, such as an SD or a range, is refused for the lead to rule.
- **Not judged:** A_fast and A_slow, which are not reported per voltage (section 13.2). The
  prediction's amplitudes are reported only. The digitising error, the extractor's own, is reported
  with each comparison and widens nothing, since section 13 fixes none.

**5. The pass rule** (section 13's rule 4, with D311's consequences).
- **The held-out voltages** are -80 and +80 mV, two voltages (D311). The claim is one interpolated
  magnitude, 80 mV between 60 and 100 mV, at both polarities. It is not two independent tests.
- **With two voltages, "more than half" means both.** The benchmark passes only if all four time
  comparisons and both G_ss comparisons pass. Rule 4's 75% condition then holds too.
- **The verdict:** cannot predict if the law leaves its domain at either held-out voltage; otherwise
  fail if any comparison fails; otherwise pass.
- The in-sample fit is reported, not judged.

**6. The reader, and how the checker runs it.**
- **Written from fit.json,** which the extractor built the same way as held_out.json.
  - It reads every list under "observables" and matches each entry by its (vj_mV,
    maps_to_registered_observable) pair.
  - An entry without that mapping is skipped (fit.json's amplitude ratio).
  - It needs exactly one entry per held-out voltage and judged observable.
  - The units are seconds (or milliseconds, converted) for times, and fit.json's "G/G(10-mV
    prepulse)" for G_ss.
- **It fails closed.**
  - It refuses a missing or duplicated entry, a missing key, a value that is not a finite number, a
    sign against its polarity, unknown units, and a dispersion that is not an SEM.
  - A refusal names key paths only, never a value, and the command line withholds any other error's
    text.
- **The checker's order:**
  1. `python -m validation.junction_gate_benchmark.revilla1999 verify predictions.json` recomputes
     every prediction from the file's one block with the tagged code, within a relative 1e-6.
  2. `python -m validation.junction_gate_benchmark.revilla1999_score score predictions.json
     held_out.json verdict.json --expect-sha256
     e83680830219a58ab6b47d268518543b90e63c52d6b7d7694ee8a8e45c7a7285` (D311's digest). The
     verdict file records both files' digests, every value and the tolerance used; stdout carries
     verdicts only.
- **Checked before the tag:**
  - `resolve` on fit.json at -100, -60, +60 and +100 mV resolves all 12 entries from their keys.
    At the default -80 and +80 mV it refuses, since fit.json holds neither. Neither run printed a
    value.
  - An end-to-end smoke of the stages used an invented parameter block and synthetic held-out files
    in fit.json's structure (/mnt/workspaces/Cells/fr30-benchmark-20261123/harness/smoke-c58714f8/).
    `predict` ran at -80 and +80 mV with the invented parameters, which is not a fit. `verify`
    passed, and `score` with each file's digest gave pass and fail where it should. A wrong digest
    and a tampered prediction were refused (exit 2), and stdout carried no value.

**7. Exposures and exclusions** (D311).
- **The Lean lane's files:**
  - `lean/checks/data/revilla1999_cx43.json` holds Table 1's per-polarity Boltzmann fits, which
    encode the held-out steady state. It has been on main since 21 November (0ec0ac28, 760d9f0c).
  - lean/PROGRESS.md and lean/claims/junction-gate.md print the fitted conductance at -80 and +80
    mV, so the held-out steady state is printed in the repository, not merely derivable.
  - lean/claims/junction-series-amplitudes.md and lean/COVERAGE.md print the -100 mV times and the
    amplitude ratio, which are training values.
- **Section 13.4's line** "Nobody on this project has read these papers' results" was wrong for
  Revilla. The Lean lane, an independent agent, had read it and put its Table 1 on main the day
  before (D311).
- **The law's design predates the exposure** (D311).
- **The fitter's exclusions,** beyond sections 13 and 13.1:
  - all of lean/;
  - the four papers in /mnt/datasets/Cells/papers/incoming/;
  - every file under fr30-candidates4-extraction/ except revilla1999/extraction/fit.json and
    protocol.json;
  - the earlier FR-30 extraction folders;
  - sections 1 to 12 of this note.

  The fitter works from fit.json and protocol.json alone.

**8. The code at the tag** (D308).
- `validation/junction_gate_benchmark/revilla1999.py`: `PROTOCOL`, `READOUT`, `LawParameters`,
  `predict`, `readout`, `predictions_document` and `verify`, with the stages `predict` and `verify`.
- `validation/junction_gate_benchmark/revilla1999_score.py`: `resolve`, `read_predictions` and
  `score`, with the stages `resolve` and `score`. It imports the standard library only, so no
  verdict depends on the engine's code.
- `tests/unit/test_junction_gate_benchmark.py`: synthetic inputs only. Its plants are a 30% time
  error, a G_ss off by 0.06 and a degenerate predicted trace, with the reader's refusals.

**9. What follows.**
- The fitter fits junction_series_gates@1 to fit.json only and states the gates' kinds before any
  prediction.
- It writes predictions.json at -80 and +80 mV with the tagged `predict` and `readout`, and the
  in-sample fit report.
- A separate checker runs the tagged scorer against held_out.json. Disagreements go to the lead.

### 13.6 Entry of 16:02 UTC on 23 November 2026: reader erratum 1, the held-out file's container, before any comparison

Written by FR-30's checker at the lead's direction, on D308's precedent: a registered reader that
cannot read its registered file is corrected by an erratum tagged before any judged run. Until now
the checker had built nothing in FR-30. This erratum is its only part in the harness, and its
verdict will say so. The lead tags the commit carrying it before the judged score.

**The obstacle.**
- The checker ran section 13.5 point 6's order from a clean full snapshot of main at ddcf32c1.
  `verify` passed. `resolve` on held_out.json refused it (exit 2) at its first check. `score`, which
  calls the same reader, was not run. The record is
  /mnt/workspaces/Cells/fr30-benchmark-20261123/verdict/checker_record.json.
- The tagged reader takes "observables" only as an object of named lists of entries, which is
  fit.json's shape. In held_out.json, "observables" is one flat list of six entries, one per judged
  pair.
- So point 6's "built the same way as held_out.json" holds for the entries, not for their
  container. Each entry carries the keys, labels and JSON types that the reader's entry checks
  expect.
- The refusal's text misled as well. It said there was "no 'observables' object" while listing
  `observables` among the top-level keys. The key exists, and its value is a list.

**The change** (`revilla1999_score.py`'s `resolve` only).
- "observables" may be fit.json's object of named lists, with paths `observables.NAME[i]` as before,
  or held_out.json's one flat list, with paths `observables[i]`.
- Every entry goes through the same checks as before, by the unchanged `_entry`: its (vj_mV,
  maps_to_registered_observable) pair, its polarity, its units, its dispersion's type and units, and
  its value.
- The refusals now say whether the key is absent, or present with neither shape.
- Nothing else changes: no tolerance, rule, pass logic or mapping of quantities.
  - `RULE`, which predictions.json carries as its conventions, is unchanged, so `verify` reads the
    registered predictions as before.
  - The scorer's output therefore still names section 13.5, and the checker's verdict names this
    entry's tag.

**How it was written.**
- From the two files' keys and shapes only, through the checker's structure logs:
  /mnt/workspaces/Cells/fr30-benchmark-20261123/verdict/logs/06-structure-held_out.txt and
  07-structure-fit.txt.
  - They print key names, JSON types, list lengths and step voltages, with the reader's labels
    (the mapping, units and polarity, and whether a dispersion is an SEM).
  - They print no value.
- Its tests use invented values. The new reader has not been run on held_out.json, and it meets the
  file only after the tag.

**No comparison has been computed.** No predicted value has been compared with a held-out value, and
the checker has seen no held-out value. The inputs are unchanged:
- predictions.json, sha256 20ca2a4a4e53fe04fe3a335a824f1148df1df436676e69d07064ec75f2252401, which
  `verify` passed;
- held_out.json, sha256 e83680830219a58ab6b47d268518543b90e63c52d6b7d7694ee8a8e45c7a7285 (D311).

**Tests** (`tests/unit/test_junction_gate_benchmark.py`, H8).
- **The passing path:** a synthetic document in held_out.json's flat list resolves to the same
  entries as in fit.json's structure, at paths `observables[i]`, and scores to the same comparisons.
  The tagged reader refused it, and that refusal is the plant.
- **Two refusal rows:** an SD at the flat list's first entry, refused by its path; and an
  "observables" of neither shape, refused with a message saying that the key is present.
- **Cost:** three test IDs, and well under a second.

**What follows.** After the tag, the checker freezes a clean snapshot that holds the erratum. It then
runs `verify`, `resolve` and `score` as section 13.5 point 6 states, with the same `--expect-sha256`.

### 13.7 Entry of 13:05 UTC on 24 November 2026: Ek-Vitorín, Pontifex and Burt (2016), registered before the paper is opened

**Who wrote it.** The author of FR-16's polarity check, who is FR-30's harness author under D334 and
never fits, predicts or checks.
- It registers the fresh blind benchmark of D320, with the user's decisions of D334.
- **No record shows anyone on this project opening the paper** (D311; the exposure sweep below).
- The commit carrying this entry, its code and its tests is tagged (Tag A, part 10) before the paper
  is opened.
- The polarity check is [JUNCTION_GATE_POLARITY.md](JUNCTION_GATE_POLARITY.md), committed beside
  this note. This benchmark's fitter does not open it.

**The paper.** Ek-Vitorín JF, Pontifex TK, Burt JM (2016), Biophys J 110:127,
doi:10.1016/j.bpj.2015.10.054, PMC4805864.
- It is filed read-only at `/mnt/datasets/Cells/papers/incoming/ek-vitorin-2016/`, for the extractor
  only.
- One paper: the fit and the held-out test both come from its own data (§13).

**What has been read about it (disclosure).**
- **This note:** section 13.4's entry, which gives its citation, DOI and PMC ID, "Wild-type Cx43
  only", and that candidates 1 to 4 "matched a full-text query for two-exponential wording with Cx43
  and transjunctional voltage".
- **D311** ("not opened"), **D320**, **D334** and **FR-30's row.**
- **Section 13.3's caption-level line on Ek-Vitorín et al. 2018,** a different paper from the same
  laboratory: "second-order decay fits, probably at a single ±80 mV". Nothing here is fixed from it.
- **From training data:** the approximate title, "Determinants of Cx43 channel gating and
  permeation: the amino terminus", and so its subject. No figure, protocol, voltage or value.
- **The exposure sweep (file names only; no matching file opened):**
  - **In the checkout,** before this entry, an Ek-Vitorín paper was named only in
    `docs/DECISIONS.md`, `docs/FEATURE_REQUESTS.md` and this note, and in their copies in worktrees.
    - Those mentions are of the 2016 paper and the 2018 one.
    - The 2016 DOI or PMC ID appears only in section 13.4.
    - This entry adds a fourth file, `docs/JUNCTION_GATE_POLARITY.md`.
    - `lean/` has no hit.
  - **Git's full history,** 5,207 commits on every branch, has no other path that ever carried these
    names. So the snapshot copies of tracked files in run folders can hold nothing else.
  - **In `/mnt/workspaces/Cells` and `/mnt/datasets/Cells`** (pass 5, 13:18 to 14:07 UTC on 24
    November; `/mnt/workspaces/Cells/fr30-next-20261124/sweep/pass5/`). File names only, with
    these skips:
    - snapshot trees were left to Git's history;
    - virtual environments and the sweep's own folder were skipped;
    - the sealed folder was left out of the datasets pass's search roots.

    Earlier passes timed out or were stopped before their datasets stage, so none searched the
    sealed folder. Pass 5 found:
    - **519 copies of the four docs above,** in worktrees and run folders.
    - **Files naming this paper specifically,** by its DOI, PMC ID or year, counted without
      reading:
      - the lead's notes in `d172-restructure-20261115-01/` (`LEAD-NOTES.md` and
        `MORNING-BRIEF-20261123.md`);
      - the source search's `candidates.md`;
      - `fr30-candidates4-extraction/`'s `README.md` and `LOG.txt`.

      `candidates.md` and the two candidates4 files are candidate lists and status notes
      (section 13.4; D311). The lead's two files were counted, not read, and the lead confirms them
      before Tag A. All of them are barred to the fitter (part 9).
    - **Pass 4** also searched every snapshot's `checkout.patch` (the snapshots' uncommitted
      changes), with no hit.
    - ripgrep skips binary and compressed files, so "nothing else" below means text files.
    - **Files naming the 2018 paper by the same authors:** its extraction's four files, its
      datasets folder's `MANIFEST.txt`, Revilla's `RULING_DRAFT.md`, Shibayama's `held_out.json`,
      and a file listing in `wash-export-refusal-20261123/`.
    - **The surname only:** BITSEY's `GJ_lib.py` (three copies; a person, D334), Elenes's
      extraction notes, and two text renderings of Moreno et al. (2002) under
      `review-check-20261121/`.
    - **Nothing else** in either tree names it.
  - **The 2018 extraction's two lines.**
    - A count, with no file opened, found one line matching this paper's second author in each of
      `fr30-ekvitorin2018-benchmark/extraction/`'s `protocol.json` and `extraction_notes.md`.
    - The lead read both by name only (24 November). They read "Ek-Vitorin, Pontifex and Burt
      (2018)": the 2018 candidate, by the same authors, not this paper.
    - The folder stays excluded for the fitter, the predictor and the checker (part 9).
  - **BITSEY's `GJ_lib.py`** names Jose Ek Vitorin as an expert colleague: a person, not this paper.
    The lead checked it by name only, and there is no exposure (D334).

#### Part 1. The law to be fitted (D334)

- **`junction_series_gates@1` as declared, with one parameter block** for both polarities. Both gate
  kinds read |V_j|.
- **Why the form does not change** (D334; [JUNCTION_GATE_POLARITY.md](JUNCTION_GATE_POLARITY.md)):
  - Identical hemichannels whose gates read only V_j are symmetric by construction, so no
    polarity-aware gate can change a homotypic prediction.
  - Independent sources indicate near-symmetry for homotypic Cx43, each one study's indication.
- **Not admitted:**
  - **per-polarity blocks:** they would be another law;
  - **`junction_series_gates@2`:** a design note under FR-16 F3, for heterotypic junctions only.
- **The kinds are stated first.** The fitter states each gate's kind before any fit, in `kinds.json`,
  and then the parameters in `params.json`. Each is hashed in a dated log line.
- **The host is the law clamped,** as section 13 hosts it: `advance_clamped` at each imposed V_j.

#### Part 2. The extraction protocol

- **E1, scope.** Only the homotypic, untagged, wild-type Cx43 control arm (§13.1 point 6; §6's
  untagged construct).
  - **Excluded:** mutants of any domain, tagged constructs, other connexins, heterotypic or mixed
    pairs, treated arms (drugs, phosphorylation manipulations, uncouplers), and hemichannel and
    single-channel data.
  - **Native cells** fall under section 13.3's admission and its label.
  - If the paper states that its cells express another connexin, the extractor records that
    statement, and the verdict carries it in its label.
- **E2, data units.** A data unit is a signed V_j step from the holding level at which the paper
  reports decays it analysed itself.
  - **D311's trace criterion:** superimposed or single sample records are not refitted.
  - Recovery steps enter training only (§13.1 point 1).
- **E3, the convention block (required, value-free and enumerated).**
  - **`paper_vj_definition`:** the paper's V_j definition as printed, or "not stated".
  - **`protocol_type`,** exactly one of:
    - `one_sided`: one cell stepped, the other held;
    - `symmetric`: both cells stepped by equal amounts of opposite sign;
    - `other`: any other stated protocol;
    - `not_stated`.
  - **`stepped_cell`:** `cell_1` or `cell_2` in the paper's labels, or null. It is required for
    `one_sided`, and null for `symmetric`.
  - **`holding_mV`:** each cell's holding level, a number or null.
  - **`sign_map`:** `as_printed`, `negated` or `not_stated`.

  **The canonical sign** is vj_mV = V(stepped cell) − V(other cell). Under a symmetric protocol it is
  V(cell 1) − V(cell 2), by the paper's labels. The law's sender is the stepped cell (or cell 1), so
  vj_mV is @3's V_sender − V_receiver. Where the sign is `not_stated`, part 7's polarity diagnostics
  are marked unoriented.

  **What each type maps to (D334).** Only `symmetric` holds the pair's mean membrane potential the
  same at both polarities. `one_sided`, `other` and `not_stated` all fall under the one-cell rule
  (P4).
- **E4, the observables,** as the paper reports them, each with its dispersion:
  - **τ_fast and τ_slow.** The smaller is the fast one, whatever the paper calls them.
  - **A_fast and A_slow,** if reported per voltage, with the paper's definition: a fraction of G_0
    (`of_G0`) or of the decaying part (`of_decaying_part`).
  - **G_ss/G_0:** the step-end conductance in the paper's normalization: `prepulse`,
    `instantaneous`, `reference_step`, `fitted_gmax`, or `not_stated`.
  - **How values are taken.** Text and table values are taken as printed. Plotted points are
    digitized, each with the extractor's declared digitizing error.
  - **Special cases:**
    - one τ at a voltage is recorded and gives no relaxation comparison (§13.1 point 5);
    - on-rates without P_open make the kinetic part undetermined (D291);
    - ramp-derived conductance enters training only, and is never judged (§13.1 point 3).
- **E5, polarity.**
  - Values reported per polarity are entered per signed voltage.
  - Values pooled by |V_j| are entered once, with polarity `pooled` (§13.1 point 2).
- **E6, withheld summaries.**
  - A quantity fitted across voltages that include a held-out voltage encodes held-out values. Such
    quantities include a Boltzmann's parameters, a τ(V) fit, a drawn curve and a mean over voltages.
  - It is listed in `held_out.json`'s `withheld`, never written into `fit.json`, and no value
    derived from it enters training.
  - D311's lesson: a copy of Revilla's Table 1 encoded the held-out steady state.
- **E7, the protocol file.** `protocol.json` carries E3's convention block, identical to the data
  files'. It also carries these fields:
  - `step_duration_s`, the analysed decays' step, and `step_durations_s`, every duration in the
    decay protocol;
  - `gss_time_s`, `prepulse_mV`, `prepulse_s`, `normalization`, `reference_mV` and `fit_window_s`;
  - `fit_form`, `fit_offset` and `amplitude_definition`;
  - `sampling_Hz`, `filter_Hz`, `temperature_C`, `cells`, `construct` and `n`.

  Each field has a status: `stated`, with its quotation and place; `read`, the extractor's reading,
  saying how it was made; or `not_stated`, with a null value.
- **E8, the layout.** Both data files follow part 8's layout: one flat list of entries, with
  identical `split` and `convention` blocks.
- **E9, the structure check before sealing.**
  - The extractor runs the tagged `check` stage on `fit.json`, `held_out.json` and `protocol.json`
    together. It prints key paths, counts, signed voltages and labels, never a value, and exit 0 is
    required.
  - **A refusal is fixed in the files,** since the layout binds, never in the reader.
  - **If the data cannot be expressed in the layout,** the extractor stops and reports to the lead,
    without values. Any layout erratum is the harness author's, written from that report and tagged
    before sealing.
- **E10, the seal.**
  - `SHA256SUMS` covers `fit.json`, `held_out.json`, `protocol.json`, `extraction_notes.md` and the
    sealed digitizers, and the files are made read-only.
  - The extractor hands back the digests and the `check` log.
  - The lead records `held_out.json`'s digest in a dated decision entry before any fitter starts.
- **E11, the extractor's limits.** The extractor does not fit, predict or score, wrote none of the
  harness, and does not open the polarity check before sealing.
- **E12, no qualifying arm.** If no homotypic wild-type arm qualifies, the benchmark is undetermined.
  The extractor reports that alone, with no substitute arm.

#### Part 3. The split rule

- **S0, the classes.** Every |V_j| magnitude m falls in exactly one class. "Decays" means mapped
  time or amplitude entries; "G_ss" means mapped steady-state entries.
  - **The decay list:** decays at both polarities, or pooled decays.
  - **Training only:** decays at one polarity only. Every value at m stays in training, and m is not
    ranked.
  - **The steady list:** no decays, and G_ss at both polarities or pooled.
  - **Training:** everything else, for example G_ss at one polarity only.
  - **Precedence.** Where m carries both per-polarity and pooled values of one observable, the
    per-polarity values are the data units, and the pooled ones are listed under `not_used`.
- **S1, the list.** Sort the decay list's magnitudes ascending, and drop any magnitude already seen
  (§13.1 point 8).
  - Point 8 concerns the fitter. A fresh fitter barred from the 2018 extraction (part 9) has seen
    none of this paper's values.
- **S2, what is held out.** The interior magnitudes at even rank (the 2nd, 4th, ...) are held out;
  the smallest and the largest stay in training. With three magnitudes, the 2nd is held out. With two
  or fewer, the kinetic part is undetermined.
- **S3, both polarities.** A held-out magnitude is held out at both of its signed voltages, or as
  its pooled unit.
- **S4, no ranking outside the two lists.** S0's two training classes are never ranked or held out.
- **S5, the steady list** follows S1 to S3 on its own magnitudes.
- **S6, everything at a held-out voltage.** Every entry at a held-out magnitude is held out, with
  any per-voltage value derived from it, and E6's summaries are withheld.
- **S7, mechanical application.** The extractor applies S0 to S6 and records the classes and the
  held-out magnitudes in the `split` block. The reader recomputes both from the two files' entries
  and refuses any mismatch (K4).

#### Part 4. The prediction and readout conventions

**How they are pinned.**
- At Tag B, the tagged `conventions` stage applies this table to `protocol.json` mechanically.
- A field that is absent or `not_stated` takes its default, and every value records the field and
  status it came from.
- Nothing is left to judgment after the extraction.

| # | Convention | Rule, from `protocol.json` | Default | Against section 13.5 |
| --- | --- | --- | --- | --- |
| 1 | Holding V_j | holding_mV(stepped) − holding_mV(other) | 0 mV | same |
| 2 | Initial state | each gate at its steady state at the holding V_j | — | same |
| 3 | G_0 | by `normalization`. **prepulse:** the conductance after `prepulse_s` at `prepulse_mV` from the holding state, with dt = 0 where `prepulse_s` is not stated. **reference_step:** the law's G_ss at `reference_mV`, at the step's polarity. **Otherwise** the holding conductance, since the law has no instantaneous voltage dependence | the holding conductance | generalized |
| 4 | Step duration T | `step_duration_s`. Else the protocol's only duration, or its longest (`step_durations_s`). Neither: the kinetic part cannot be predicted | — | generalized |
| 5 | G_ss sampling time | `gss_time_s` | the step's end, T | generalized |
| 6 | Sampling | t_k = k ms from the step's onset | — | same |
| 7 | Fit window | `fit_window_s`, within the step | 5 ms to T | generalized |
| 8 | Fit form | y = C + A_f e^(−t/τ_f) + A_s e^(−t/τ_s), **C free in every case**. A fixed offset is recorded as a statement only. An offset taken from data is withheld (E6) | C free | same |
| 9 | Start grid | T in integer ms, rounded half up; the 1-2-5 ladder from 1 ms to 1,000 s. τ_f has 600·τ_f ≥ T and 15·τ_f ≤ T; τ_s has 30·τ_s ≥ T and 3·τ_s ≤ 5·T; every bound inclusive; pairs with τ_f < τ_s; ties go to the first in grid order | — | scaled with T |
| 10 | Refinement | Levenberg–Marquardt with Kaufman's Jacobian, tolerances 1e-12, at most 1,000 evaluations | — | same |
| 11 | Degenerate fit | τ_s/τ_f < 1.5; A_f or A_s below 1e-3, signed; τ_s > 10 T; no convergence; a value not finite or a time not positive | — | the cutoff scaled with T |
| 12 | Predicted amplitudes | `of_G0`: A_f and A_s over G_0, each judged. `of_decaying_part`: A_f/(A_f + A_s) only, since A_s's share is 1 minus A_f's | — | new |
| 13 | Cannot predict | the domain fails at the hold, prepulse, step or end; the trace is not finite; or G_0 ≤ 0 | — | same |
| 14 | One block | every prediction comes from one block, and `verify` recomputes each within a relative 1e-6 | — | same |

**At 30 s the rules give section 13.5 exactly.**
- With Revilla's fields at T = 30 s, the rules give section 13.5's constants: τ_f {50, ..., 2,000}
  ms, τ_s {1,000, ..., 50,000} ms (its 33 pairs), the 300-s cutoff and the 5 ms to 30 s window.
- At T = 10 s the grid is τ_f {20, 50, 100, 200, 500} ms and τ_s {500, 1,000, 2,000, 5,000,
  10,000} ms.

#### Part 5. The comparisons, the one-cell rule and the verdict

- **P1, the comparisons** (section 13.5's, with amplitudes added):
  - **a time** passes if |ln(pred/obs)| ≤ ln 1.25 or |pred − obs| ≤ 2 SEM;
  - **an amplitude** passes if |pred − obs| ≤ max(0.10, 2 SEM), in the paper's definition;
  - **G_ss/G_0** passes if |pred − obs| ≤ max(0.05, 2 SEM).

  Each comparison records the tolerance that applied.
- **P2, the SEM.**
  - An entry's SEM is taken as given.
  - **An SD becomes SD/√n only where the paper states n and what n counts** (the dispersion's `n`
    and `n_counts`; D334).
  - An SD without both, a range, or no dispersion widens nothing, and this is recorded.
  - The digitizing error is reported and widens nothing.
- **P3, degenerate fits.** A degenerate predicted fit fails the time and amplitude comparisons at its
  voltage, with its reasons. Its G_ss is still judged.
- **P4, the one-cell rule (D334).**
  - **The windows.** At each held-out magnitude, each observable's + and − acceptance windows are
    computed from the observations alone (P1's tolerances), never from a prediction:
    - a time's window is the union of its ln 1.25 band and its 2-SEM band;
    - a band's window is the observation ± its tolerance.
  - **The rule.** Under `one_sided`, `other` or `not_stated` (E3), an observable whose two windows
    are disjoint is reported at both voltages as **confounded by V_m**, neither passed nor failed.
    Overlapping observables are judged.
  - **The justification is non-identifiability,** not a claim that V_m gating is real. Unless a
    protocol is symmetric:
    - the two polarities differ in the stepped cell's membrane potential as well as in V_j's sign;
    - a law of V_j alone cannot separate them;
    - so disjoint windows are equally consistent with an asymmetry in V_j and with an effect of V_m.
  - **Under `symmetric`,** every comparison is judged.
- **P5, the minimum judged set.** Two conditions:
  - at least two held-out voltages each carry both judged times;
  - wherever the paper reports G_ss at a held-out voltage, at least one G_ss comparison is judged.

  Below this set the verdict is undetermined.
- **P6, the kinetic verdict (FR-30's), decided in this order:**
  1. **undetermined**, if fewer than two held-out voltages carry both times. This is decided from
     the sealed split's structure, before any fit;
  2. **cannot predict**, if the law leaves its domain at any held-out voltage;
  3. **undetermined**, if the judged comparisons fall below P5's set;
  4. **pass**, if (a) every judged G_ss passes, (b) each judged time and amplitude passes at no
     fewer than ⌊k/2⌋ + 1 of its k judged voltages, and (c) at least 75% of the judged relaxation
     comparisons pass. Rule (b) means both of two (D311), two of three, and three of four;
  5. otherwise **fail**.

  The in-sample fit is reported, not judged.
- **P7, Part S: a separately named steady-state result (D334).**
  - It is scored only when FR-30's verdict is undetermined. It judges every held-out G_ss under P4,
    with at least two judged comparisons.
  - It reads **pass**, **fail**, **cannot predict** or **undetermined**.
  - FR-30's own verdict stays undetermined whatever Part S reads.
- **P8, one magnitude held out.** The claim is one interpolated magnitude at both polarities, not
  two independent tests (D311).

#### Part 6. What a verdict decides, stated before the paper is opened

- **W1, what a pass licenses.** One study's agreement with `junction_series_gates@1`, with one
  symmetric block, at the held-out magnitudes under this paper's conditions.
  - D262's development status changes only by the user's decision.
- **W2, a fail where the failed observables' ± windows overlap.** One symmetric prediction could
  have passed, so the fit missed (D320's reading). It says nothing against symmetry.
- **W3, disjoint windows.**
  - Under a one-cell protocol, P4 reports them as confounded, never as a fail.
  - Under a symmetric protocol, a fail there is the first independent indication of an intrinsic
    homotypic asymmetry, and it reopens the polarity check.
- **W4, Part S.** It says only whether one symmetric steady state predicts the held-out G_ss. It is
  FR-16's question, and it never qualifies FR-30's law.
- **W5, undetermined or cannot predict.** No test.
- **W6, the diagnostics decide nothing.**

#### Part 7. Diagnostics, reported and never judged

- **D1, the windows.** At each held-out magnitude and observable: the + and − windows, whether they
  are disjoint, and whether P4 applied.
- **D2, polarity differences.** At every magnitude with both polarities, in both files: obs(+) minus
  obs(−), the combined SEM, and z.
  - The SEMs are combined as independent. That is an approximation, since the same pairs usually
    give both polarities.
- **D3, the polarity mean.** The prediction against each held-out magnitude's polarity mean.
- **D4, protocol and V_m.** The protocol type, the stepped cell, the holding levels and the sign
  map.
  - The observed sign of G_ss(+) − G_ss(−) is reported at each magnitude, against the V_m
    hypothesis. Revilla, Bennett and Barrio (2000), doi:10.1073/pnas.97.26.14760, report that
    "equal depolarization of both cells decreases g(j)". Under a one-cell protocol that predicts
    G_ss(+) ≤ G_ss(−), + meaning the stepped cell relatively positive.
  - Unoriented when the sign is `not_stated`.
- **D5, the in-sample fit.** The fitter's in-sample residuals, as fitted.

#### Part 8. The code at the tag (D308; section 13.6's lesson)

**The modules** (`validation/junction_gate_benchmark/`):
- **`score.py`,** standard library only: the reader, `check`, `resolve` and `score`. No verdict
  depends on the engine's code.
- **`harness.py`:** `conventions`, `predict` and `verify`, with `readout`.
- **`revilla1999_layout.py`:** the rehearsal's converter of Revilla's spent extraction into this
  layout.
- They are generic (D334): a later benchmark of the law reuses them with its own files.

**The layout, binding on the extractor.** Both data files have the same container (section 13.6's
lesson), and every entry carries every key below. Angle brackets show a type or a placeholder, never
a value expected from the paper.

```json
{
  "schema": "fr30-junction-observations@1",
  "role": "train | held_out",
  "registration": {},
  "paper": {"citation": "<string>", "doi": "10.1016/j.bpj.2015.10.054", "pdf_sha256": "<hex>"},
  "arm": "<string>",
  "convention": {
    "paper_vj_definition": "<as printed, or not stated>",
    "protocol_type": "one_sided | symmetric | other | not_stated",
    "stepped_cell": "cell_1 | cell_2 | null",
    "holding_mV": {"cell_1": "<number or null>", "cell_2": "<number or null>"},
    "sign_map": "as_printed | negated | not_stated"
  },
  "split": {
    "rule": "section 13.7 S0-S7",
    "classes_mV": {"decay_list": [], "training_only": [], "steady_list": [], "training": []},
    "seen_mV": [],
    "held_out": {"decay_mV": [], "steady_mV": []}
  },
  "observables": [
    {
      "id": "<string>",
      "vj_mV": "<number: the canonical signed mV; |V_j| if pooled>",
      "polarity": "+ | - | pooled",
      "observable": "<the paper's name>",
      "maps_to": "tau_fast | tau_slow | A_fast | A_slow | G_ss/G_0 | null",
      "value": "<number>",
      "units": "s | ms | G/G_0 | fraction",
      "normalization": "prepulse | instantaneous | reference_step | fitted_gmax | not_stated | null",
      "amplitude_definition": "of_G0 | of_decaying_part | null",
      "dispersion": {"type": "SEM | SD | range", "value": "<number, or [low, high]>",
                     "units": "<the entry's units>", "n": "<integer or null>",
                     "n_counts": "<what n counts, as the paper states, or null>"},
      "n": "<integer or null>",
      "source": "<figure or table, page>",
      "method": "printed | digitized",
      "digitizing_error": "<number in the entry's units, or null>"
    }
  ],
  "withheld": [{"name": "<string>", "why": "<string>"}],
  "not_used": []
}
```

**Notes on the layout.**
- **Normalization.** G_ss and amplitude entries carry the protocol's normalization (`not_stated`
  where its field is not stated). Times carry null.
- **Amplitude definition.** Only amplitudes carry one.
- **The dispersion** is null or an object. A range's value is `[low, high]`, and `n` and `n_counts`
  matter only for an SD (P2).
- **`withheld`** is empty in `fit.json`.
- **An unmapped entry** (`maps_to` null) still carries every key. Only its voltage, polarity, `n`
  and digitizing error are checked.
- **Extra keys** are ignored.

`protocol.json` carries the data files' convention block, identical, and E7's 17 fields. Each field
has every key below.

```json
{
  "schema": "fr30-junction-protocol@1",
  "role": "protocol",
  "paper": {},
  "convention": "<the data files' block>",
  "fields": {
    "<field>": {"value": "<as below, or null>", "status": "stated | read | not_stated",
                "quote": "<string where stated>", "place": "<string where stated>",
                "how": "<string where read>"}
  }
}
```

**Field values,** with null where the status is `not_stated`:
- **A positive number:** `step_duration_s`, `gss_time_s`, `sampling_Hz` and `filter_Hz`.
- **A nonnegative number:** `prepulse_s`.
- **A number:** `prepulse_mV`, `reference_mV` and `temperature_C`.
- **Lists:**
  - `step_durations_s`: a non-empty list of positive numbers;
  - `fit_window_s`: `[start, end]` with 0 ≤ start < end.
- **One of a fixed set:**
  - `normalization`: `prepulse`, `instantaneous`, `reference_step` or `fitted_gmax`;
  - `fit_offset`: `free`, `fixed_constant` or `fixed_from_data`;
  - `amplitude_definition`: `of_G0` or `of_decaying_part`.
- **A string:** `fit_form`, `cells` and `construct`.
- **A positive integer:** `n`.

**The reader's checks.** The reader fails closed, and every refusal names key paths only, never a
value.
- **K1, the top level:** the schema and role; `observables` as one list, so an object of named
  lists is refused; and the convention and split blocks.
- **K2, each entry:** its keys, allowed values and finite numbers; its polarity against its sign;
  positive times; units suited to the mapping; the normalization and definition where needed; and
  the dispersion's units.
- **K3, duplicates:** one entry per (vj_mV, polarity, maps_to), and S0's precedence.
- **K4, the split:** S0's classes and S1 to S5's held-out magnitudes, recomputed from the union of
  both files' entries, must equal the declared ones. The two files' blocks must be identical, and
  `protocol.json`'s convention block equal to theirs.
- **K5, where entries sit:** no `fit.json` entry at a held-out magnitude, and every `held_out.json`
  entry at one, with each held-out unit present.
- **K6, dispersion,** as P2.
- **K7, errors:** an unexpected error's text is withheld (exit 3).

Every G_ss and amplitude entry must carry the protocol's normalization.

**Stages,** run from a clean snapshot of the tag:
- `python -m validation.junction_gate_benchmark.score check FIT HELD_OUT PROTOCOL`;
- `... score resolve FILE --role train|held_out`;
- `... score score PREDICTIONS HELD_OUT FIT OUT --expect-sha256 HEX`;
- `python -m validation.junction_gate_benchmark.harness conventions PROTOCOL OUT`;
- `... harness predict PARAMS CONVENTIONS FIT OUT`. It predicts at both polarities of every
  held-out magnitude named by `fit.json`'s split, and never opens `held_out.json`;
- `... harness verify PREDICTIONS CONVENTIONS FIT`.

Every stage prints verdicts, statuses, labels and key paths only. Values go to the output files.

**The tests** (`tests/unit/test_junction_benchmark_harness.py`) use invented files only. They run
in 2.17 s, measured cold on the timed lane (tier 1, `tests/test_tiers.json`), and compile no
world. Each claim has its planted error:
- **G1:** the passing path, a G_ss off by 0.06, and tau_slow off by 30% at two voltages;
- **G2:** section 13.6's container;
- **G3:** SD conversion, which needs both n and n_counts;
- **G4:** leakage of a held-out magnitude into training;
- **G5:** the recomputed split, and differing blocks;
- **G6:** entry checks, with a planted value never printed;
- **G7:** "more than half";
- **G8:** the one-cell rule. Disjoint G_ss windows are confounded under `one_sided` and fail under
  `symmetric`; disjoint τ_slow windows leave the verdict below the minimum judged set; and the
  confound does not depend on a prediction;
- **G9:** Part S;
- **G10:** the conventions, including section 13.5's constants at 30 s and three refusals;
- **G11:** `verify` against a tampered time;
- **G12:** no value printed, and `score.py`'s imports from the standard library only;
- **G13:** pooled units, scored at +|V_j|, and per-polarity and pooled entries of one observable
  refused.

**The rehearsal on Revilla's spent files** (D334) runs Tag A's whole chain in this layout:
convert, `check`, `resolve` for both roles, `conventions`, `predict` with Revilla's registered
parameter block, `verify`, and `score`.
- **What it must reproduce:**
  - section 13.5's conventions;
  - the registered `predictions.json` (20ca2a4a...) within `verify`'s tolerance;
  - D320's six comparison lines, and their verdict.
- **What it shows of the new rule:** with Revilla's one-cell protocol, P4 confounds nothing, since
  every ±80 mV window overlaps (D320).
**Rehearsed at 13:07 UTC on 24 November 2026,** from a clean full snapshot of a1fd52d0, the commit
that first carried this entry and its code (record:
`/mnt/workspaces/Cells/fr30-next-20261124/rehearsal-a1fd52d0/`, with `logs/exits.txt`).
- **Every stage exited 0:** convert, `check`, `conventions`, `predict`, `verify`, `score` (with
  `--expect-sha256`) and the comparison.
- **The conventions are section 13.5's:** the hold, the +10-mV prepulse at dt = 0, the 30-s step,
  the 5 ms to 30 s window, the 33-pair grid and the 300-s cutoff.
- **The predictions equal the registered `predictions.json` bitwise** at −80 and +80 mV, in G_0,
  both times, both amplitudes, C and G_ss/G_0.
- **The six comparison lines are byte-identical to D320's,** with the verdict fail, 4 of 6 judged
  pass.
- **Nothing is confounded,** since every ±80 mV window overlaps.
- **The inputs were unchanged** after the run (`logs/08-compare.txt`: 43 of 43 checks).

**Rehearsed again at 13:20 UTC on 24 November 2026,** from a clean full snapshot of d643a1e9, the
commit that holds the final code. This run adds `resolve` for both roles (record:
`/mnt/workspaces/Cells/fr30-next-20261124/rehearsal-d643a1e9/`).
- **Every stage exited 0,** and `resolve` printed key paths only. On the held-out file they are the
  six of D320's own `resolve`, one for one.
- **All 43 checks passed again,** and the six comparison lines are byte-identical to D320's.
- **Later commits change no module under `validation/`:** they change this note, the tier
  record and the test file (G13, pooled units).

#### Part 9. Roles and exclusions

- **The extractor (E)** reads the paper and follows E1 to E12. It is a fresh agent.
- **The harness author (H)** is the polarity check's author (D334), who never fits, predicts or
  checks.
  - H wrote part 8's code and tests from this entry, with section 13.5's modules and Revilla's
    spent files (already seen) for the rehearsal.
  - After the seal, H runs `conventions` on `protocol.json` and commits `conventions.json` for
    Tag B.
  - H reads `protocol.json` and `fit.json`'s structure, never `held_out.json`'s values or
    `extraction_notes.md`.
  - H writes any erratum, from value-free structure logs.
- **The fitter (F), fresh (D334).**
  - F works from `fit.json`, `protocol.json` and `conventions.json` alone, and states the kinds
    before fitting.
  - F fits @1 to `fit.json` only, and writes `params.json`, hashed in a dated log line.
  - F evaluates the law at no held-out voltage, and writes no prediction.
- **The predictor (P), separate (D334).**
  - From a clean snapshot of Tag B, P runs `predict` and then `verify`, and writes
    `predictions.json`.
  - P never opens `held_out.json`, and is neither E, H, F nor C.
- **The checker (C).**
  - C wrote no code, erratum or extraction.
  - From a clean snapshot of Tag B, C runs `verify`, `check`, `resolve` and `score` with
    `--expect-sha256`, then recomputes every comparison with its own code, and writes the verdict
    with its disclosures.
  - **On a refusal, C stops and reports.** The erratum is H's, tagged before any judged score.
- **The lead** rules and tags, and stays blind to every value until the verdict.

**Exclusions.** They bind F, P and C until C scores. E is held only from the polarity check, until
sealing.
- **The fitter is barred** (D334) from:
  - D311 and D320;
  - the polarity check ([JUNCTION_GATE_POLARITY.md](JUNCTION_GATE_POLARITY.md));
  - all of `/mnt/workspaces/Cells/fr30-next-20261124/`, whose rehearsal holds Revilla's held-out
    values in this layout;
  - Revilla's extraction;
  - sections 1 to 12 of this note, which print other preparations' values, as section 13.5 barred
    them.
- **The paper:** the paper itself and `/mnt/datasets/Cells/papers/incoming/`.
- **The sealed files:** `held_out.json` (for F and P), `extraction_notes.md` and the sealed
  digitizers.
- **Other extractions:** every FR-30 extraction folder.
  - That includes `fr30-candidates4-extraction/` (Revilla's among them) and
    `fr30-ekvitorin2018-benchmark/`, the same authors' later paper.
- **Revilla's benchmark:** `fr30-benchmark-20261123/`.
- **Priors and notes:** `lean/`, the source search's `candidates.md`, the lead's notes and briefs
  in `d172-restructure-20261115-01/`, and the notes named in section 13 and 13.1.

#### Part 10. Order of work and tags

1. **Before Tag A:**
   - the exposure sweep is completed;
   - the rehearsal passes;
   - the lead gates the landing (D223, D229).
2. **Tag A, before the paper is opened.** The lead tags this entry with its code:
   `fr30-ekvitorin2016-tag-a-2026-11-24`.
3. **The extraction.**
   - E extracts, recording the PDF's sha256, runs `check` (exit 0) and seals.
   - The lead records `held_out.json`'s digest in a dated decision entry.
   - **The branch,** read from the sealed split's structure without values:
     - two or more held-out voltages carry both times: steps 4 to 7 run for FR-30's verdict;
     - otherwise, if the held-out file carries at least two G_ss entries (counted from `check`'s
       output): steps 4 to 7 run for Part S alone, and FR-30's verdict is undetermined;
     - otherwise: undetermined, and nothing further runs.
4. **Tag B, before any fit.** H runs `conventions`, and the lead tags `conventions.json` as
   `fr30-ekvitorin2016-tag-b-<date>`.
5. **The fit.** F states the kinds, fits, and writes `params.json`.
6. **The prediction.** P predicts and verifies.
7. **The score.** C scores, and the lead's decision entry follows.

Each step expected to run for 10 minutes or more runs detached, with durable logs (AGENTS.md).

#### Part 11. Settled before Tag A (the lead, 24 November 2026)

- **The tags:** `fr30-ekvitorin2016-tag-a-2026-11-24` and later `fr30-ekvitorin2016-tag-b-<date>`
  (part 10).
- **The 2018 extraction's two lines** name the 2018 paper by the same authors, not this one
  (disclosure). S1's "none seen" stands, and the folder stays barred (part 9).
- **The three choices D334 left to this entry stand:**
  - `other` and `not_stated` count as confounding (E3, P4);
  - the minimum judged set is as P5 defines it;
  - cannot predict is decided before the confounded undetermined (P6).
- **A fourth choice, for the lead to confirm before the tag.** Part S judges every held-out G_ss
  (P7), including those at decay-list magnitudes, and part 10 starts it from at least two held-out
  G_ss entries. D334's draft named the steady list only. The case this decides: three magnitudes
  with pooled decays give one held-out unit, so FR-30's verdict is undetermined, while a held-out
  G_ss exists.
- **Section 13.5's modules stay on main for now** (`revilla1999.py`, `revilla1999_score.py` and
  their tests). Their tags keep them, and the generic modules reproduce them (part 8). Retiring them
  is a later cleanup.

#### Part 12. Amendment 1 (24 November 2026, the lead, D341): the paper's Supporting Material is added as a source, before anyone opens it

**Why.** E's extraction of the filed PDF found the benchmark undetermined by structure, for that PDF alone. E
reported it without values.
- Fig. 2B shows one illustrative record pair, at a single magnitude, with the paper's own fits.
- Fig. 2C's points cannot be expressed in the layout (E9, K3).

The lead ruled no new rule for summarizing points. E sealed its folder and released no value.

**The new source.** The user filed the paper's Supporting Material on 24 November 2026, at
`/mnt/datasets/Cells/papers/incoming/ek-vitorin-2016/supporting-material/`, read-only, with a MANIFEST:

| File | sha256 | What its PDF metadata says |
| --- | --- | --- |
| `mmc1.pdf` | d36e596474bebf59ce8ea7e0800576fad8c4349bdf27c2e80cfee40097616757 | 6 pages, the Supporting Material |
| `mmc2.pdf` | 3ace545d130705f05fe68fbd0e28bea778cb0729fa6c26aacd842e591e9ad6ad | 20 pages, the article with its Supporting Material |

Nobody has opened either file. The lead identified them by their PDF metadata alone.

**What changes:**
- The same extractor, E, opens these two files under this section's rules, unchanged: E1–E12, the split rule, the
  layout, the check and the seal.
- E reads them for the Cx43WT arm's macroscopic decays and steady state at per-voltage resolution.
- **If they give what §13.7 needs,** E extracts from the paper and its Supporting Material together, as one source:
  per-voltage τ_fast and τ_slow at two or more magnitudes, at both polarities or pooled. Anything they repeat from the
  article is taken once, from the Supporting Material's per-voltage form where both give it.
- **If not,** the benchmark stays undetermined by structure, now for the paper with its Supporting Material.

**What does not change:** every criterion; Part S; the layout; who may read what; and the bar on any rule for
summarizing plotted points. The fitter, the predictor and the checker start only after a seal under this amendment.

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
