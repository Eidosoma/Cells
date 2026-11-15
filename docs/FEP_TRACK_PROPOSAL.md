# A free-energy-principle track: specification and engine gap analysis

Status: **PROPOSED, future; not scheduled.** Written on 15 November 2026 against main `bd8f1e9f`, at
the user's request: "spec out a future, not now, FEP track, but let's see if there are some relevant
engine issues". FEP is the free-energy principle; AIF is active inference.
- **Scope:** a specification and a gap analysis. Nothing was built, run or downloaded. Every stage is
  deferred (D151), with its prerequisite and gate in §6.
- **Not authorised:** any engine change or run; a new organism; reproducing a paper's model (D138);
  lifting D145's hold on gene regulation.
- **Engine models the stages would run** (AGENTS.md's milestone rule):
  - **Stage 1a:** `resolved_pump_composite@1` over `resolved_pump_tissue@3` with
    `scheduled_bath_composition@1`, `site_occupancy@1`, `local_species_reactions@1` and
    `species_regulated_availability@1`, plus §3.7's general items.
  - **Stage 3:** the same composite with `scheduled_cell_replacement@1`,
    `delayed_first_order_junction_formation@1`, `scheduled_species_exchange@1` and Track E's channel
    laws.
  - **Stage 2:** the gene-regulation layer, which is held.
  - A harness arm that runs none of these is tooling (§3.8).
- **Sources.** The user pasted two syntheses that read as another assistant's output: one on single
  cells, and one adding a tissue layer. Their claims are leads, checked at the primary source (§1.3).
  - Every source, with its licence class and read level, is in
    [the source log](/mnt/workspaces/Cells/fep-track-20261115-01/sources.json).
  - The licence classes are the visualizer audit's: permissive, non-commercial, no stated terms.
  - Numbers from the last two classes appear only in sentences, never in tables (D173).
- **S** marks our own inference or arithmetic.

## 0. Verdict

- **The essays' empirical anchors hold, with corrections** (§1.3). "CheA compares" is loose, and not
  every planarian change persists.
- **No result here would prove the FEP.** A standard chemotaxis model has been shown mathematically
  equivalent to an optimal filter, and PID control derived as AIF under linear generative models. So
  the harness must be able to fail, and must report "indistinguishable" when accounts coincide (§1,
  §3.8).
- **Stage 1a needs no motility, spatial gradient or stochastic kernel.** The classic data come from
  tethered or immobilised cells under flow-delivered stimuli. It needs:
  - an allosteric (MWC) factor;
  - receptor occupancy as a coupling source, a door FR-3's design already drew;
  - adaptation with an output-dependent rate;
  - an organism instance with observation models.

  A permissive single-cell dataset with a knockout exists (Keegstra et al. 2017, CC BY). It can judge
  step responses, recovery, dose response and the knockout. The ~4 s comparison, ramps and sine waves
  have no permissive source found, so they are analysis only.
- **The "active" loop needs two large general features wanted elsewhere:** motile cells sampling a
  field (E15's migration) and a stochastic regime (Syn3A's F11).
- **Stage 2 is blocked by D145's hold and FR-8.** Stage 3's islet maps mostly onto planned general
  work; its planarian strand reuses E07 and MG0b.
- **Recommended:** stay deferred; when started, a bounded Stage 1a after D172's landing and FR-4 and
  FR-5, about 20–28 agent-days (**S**, §6).

## 1. Scope and claims discipline

### 1.1 Four kinds of claim, kept apart

| Kind | It asserts | A Cells result can show | It cannot show |
| --- | --- | --- | --- |
| Mechanistic reproduction | Cited laws and parameters reproduce measured responses | Adequacy within scope, including held-out perturbations and knockouts | That the cell infers or believes anything |
| Control-theoretic description | A controller class, such as integral feedback (Yi et al. 2000) | Functional organisation: precise adaptation is robust while timing is not (Alon et al. 1999); robust adaptation needs an internal model of the disturbances (Sontag 2003) | Bayesian beliefs. That "internal model" models disturbances, not the world |
| Active-inference account | A generative model, variational belief updates, actions minimising expected free energy | Better held-out prediction than declared alternatives under a registered score, only where it commits to more (for example, gains as precisions retuned to the environment's statistics) | That the FEP holds |
| FEP interpretation | Anything with a Markov blanket at a non-equilibrium steady state can be read as minimising variational free energy | At most, whether its preconditions hold on a stochastic Cells model: conditional independence across a declared blanket | The principle, which our runs cannot test |

### 1.2 Rules for the track

- **No result proves the FEP.** Level 3 success means only that an AIF model wins on held-out
  perturbations under a score registered in advance.
- **Equivalences come first.**
  - A standard chemotaxis model is "mathematically equivalent to an information-theoretically
    optimal filtering dynamics" (Nakamura & Kobayashi 2021, arXiv abstract). Summaries of the full
    text add that the filter infers up- or down-gradient swimming, that methylation is its
    prediction term, that noise is neglected, and that one tumbling parameter disagrees with
    measurement.
  - PID control follows from variational free-energy minimisation under approximate linear
    generative models (Baltieri & Buckley 2019). The pathway's cutoff is also an optimal-filtering
    solution (Andrews, Yi & Iglesias 2006).
  - Where accounts coincide, no data separate them, so each comparison carries an identical-dynamics
    pair that must come out "indistinguishable".
- **Variational free energy is not thermodynamic free energy.** Cells' ledgers book heat and work in
  joules. The energy–speed–accuracy trade-off of adaptation (Lan et al. 2012; Sartori et al. 2014)
  is a thermodynamic claim our ledgers can test, not FEP evidence.
- **Decoded beliefs are not the cell's.** A decoder is an observer. A cell uses only declared local
  inputs (ARCHITECTURE, "Information access and memory mechanisms").
- **The membrane as a Markov blanket is contested.**
  - "Pearl blankets" (statistics) are not "Friston blankets" (agent boundaries) (Bruineberg et al.
    2022).
  - The blanket conditions hold only in a narrow parameter space, and the step to inference fails
    even for linear stochastic systems (Aguilera et al. 2022).
  - The original free-energy lemma is wrong at face value (Biehl, Pollock & Kanai 2021).
  - See also Raja et al. 2021, Colombo & Wright 2021, and the proponents' Friston et al. 2023.
- **Collectives start from attractors.** E07-v1 is judged: under donor-copy turnover the written disc
  did not renew (CURRENT_PLAN). A group-level memory claim must first survive such a test.

### 1.3 The essays' claims, checked

Each claim rests only on what was read; read levels are marked in the [References](#references).
- **"A comparison over about 4 s": confirmed** (Segall, Block & Berg 1986). Tethered *E. coli* got
  impulses, steps, exponential ramps and exponentiated sine waves. They weight the last second
  positively and the 3 s before it negatively.
- **"Lost without CheR/CheB": confirmed, with a nuance** (same paper).
  - cheRcheB mutants weight the last second like wild type but make no short-term comparison.
  - They fail to adapt within 12 s to small steps, and adapt partly, with a decay time over 30 s, to
    larger ones. cheZ mutants weight at least 40 s.
  - So the knockout predicts a response lobe without the adaptation lobe, plus a slow partial
    adaptation a methylation-only model lacks (**S**): a discriminating test.
- **"CheA compares": loose.** The receptor–CheW–CheA complex's activity reflects ligand occupancy
  against the methylation level (Tu, Shimizu & Berg 2008; Shimizu, Tu & Berg 2010). CheA carries
  the result.
- **"A feedback controller, not by itself a generative model": agreed.** Established readings:
  - adaptation as a consequence of network connectivity, with no fine-tuning (Barkai & Leibler 1997);
  - the same read as integral feedback (Yi et al. 2000);
  - the filter equivalence.
- **Anticipation: confirmed at abstract level.**
  - Mitchell et al. (2009) report asymmetric anticipation (early stimuli pre-induce later genes, not
    the reverse), a fitness gain from pre-exposure, and loss of the response in *E. coli* evolved
    without the second stimulus. The pair (lactose, then maltose), the ~500 generations and the
    yeast's wine-fermentation sequence come from the MeSH record and press coverage.
  - Tagkopoulos, Liu & Tavazoie (2008) report temperature and oxygen responses correlated as in
    entering the gut, plus in silico evolution. A partial decoupling after a few hundred generations
    in a flipped environment, with no *E. coli* fitness measured, comes from press coverage only.
- **Planarian persistence: confirmed for polarity, not for every change.**
  - Ectopic heads set permanent axes through later unperturbed regeneration (Oviedo et al. 2010).
  - The double-headed fraction stays constant, normal-looking animals carry a cryptic state, and
    recutting in water gives the same ratio (Durant et al. 2017; values in
    [MORPHOGENESIS_PLAN.md](MORPHOGENESIS_PLAN.md)).
  - Octanol-induced head shapes of other species are **not permanent**; they remodel back within
    weeks (Emmons-Bell et al. 2015, CC BY).
  - "Bioelectric networks store patterning information" is the authors' interpretation.
- **FEP morphogenesis papers are simulations,** with no new wet-lab comparison (Friston et al. 2015,
  CC BY; Kuchling et al. 2020).
- **"As One and Many": verified** (Waade et al. 2025, *Entropy* 27:143, CC BY; Friston is a
  co-author). Agents that maintain a group-level blanket can form a group-level agent, whose model
  relates "non-trivially" to theirs. The agents are software in a multi-armed bandit
  (ActiveInference.jl), with no biological data.
- **The islet: confirmed.**
  - Cx36-deficient islets lose synchronised Ca²⁺ oscillations and pulsatile insulin, with normal
    total output and raised basal release (Ravier et al. 2005).
  - Reduced coupling slows and disrupts Ca²⁺ waves, which a heterogeneously coupled model reproduces
    (Benninger et al. 2008).
  - Metabolism → electrical activity → Ca²⁺ → exocytosis is consensus (review: Rorsman & Ashcroft
    2018). Its abstract does not name K_ATP, so the essay's K_ATP step was not checked at source here.
  - PMC8915749 is a review of β-cell heterogeneity (Benninger & Kravets 2022).
  - Hub-cell leadership (Johnston et al. 2016) is doubted: no obvious electrophysiological mechanism
    lets one hyperpolarised hub silence an islet (Satin, Zhang & Rorsman 2020).

## 2. The staged track

Levels follow the essay: 1, feedback; 2, prediction (cue A anticipates B); 3, an AIF account beating
feedback on held-out perturbations.

### 2.1 Stage 1a: chemotaxis signalling in a well-mixed cell (Level 1)

| Item | Content |
| --- | --- |
| Observables | Kinase activity by FRET (populations and single cells) after steps, impulses, ramps and sine waves; tethered rotation bias; adaptation time and precision |
| Judged data (permissive) | Keegstra et al. 2017 (*eLife*, CC BY): single-cell FRET with and without CheR/CheB, steps and dose responses, figure source data as `.mat` files. Its single-cell traces are smoothed over a 14 s moving average in the part read |
| Analysis-only data | Shimizu et al. 2010 (CC BY-NC-SA: ramps, sine waves, temperature); Segall et al. 1986 and Block et al. 1982 (tethered impulse responses, the mutants); Sourjik & Berg 2002; Cluzel et al. 2000. The last four have no stated terms |
| Calibration, held out | Calibrate on wild-type steps. Hold out ramps and sine waves, the knockout, protein-level changes (Alon et al. 1999's design), temperature (analysis only) |
| Controls | A methylation-free arm that must fail to adapt; planted parameter errors; the harness's identical-dynamics pair |
| References | From equations, by an agent that never reads the engine code (as for D152); simulators second (§5) |
| Claim | Level 1, judged on the permissive set: step responses, recovery, dose response, and lost adaptation without CheR/CheB. Analysis only, since no permissive source was found: the impulse response's temporal comparison, ramps and sine waves, and temperature. Single-cell temporal fluctuations need the stochastic regime (§3.7, rank 4). The control reading is a separate claim; there is no inference claim |

### 2.2 Stage 1b: run and tumble in a gradient (the action loop)

- **Observables:** drift velocity; run and tumble statistics; behavioural noise in single cells,
  which the signalling network generates (Korobkova et al. 2004); performance against an
  information limit (Mattingly et al. 2021).
- **Data and references:** mostly no stated terms, so analysis only. RapidCell and MicrobeAgents.jl
  are the references (§5).
- **The claim:** an AIF account first predicts actions here, and can be compared with a fixed
  controller on how gains retune when the environment's statistics change. It says nothing about
  the FEP.

### 2.3 Stage 2: anticipatory regulation (Level 2)

- **Observables:** pre-induction of B's genes by A; growth after A → B against B → A; loss of the
  response under evolution without B.
- **Data:** Mitchell et al. 2009 and Tagkopoulos et al. 2008, both with no stated terms. Their
  deposits were not checked.
- **Controls:** A alone, B alone, the swapped order, uncorrelated sequences. **Held out:** the A–B
  interval.
- **Entry point:** lactose → maltose needs only chemical cues. The temperature arms need a control
  the engine lacks (§3.4).
- **References:** a cross-regulation model written from equations by an independent agent. No
  published simulator was checked.
- **The claim:** a cross-regulatory wiring reproduces the asymmetry. That the network "learned a
  correlation" is a further, evolutionary claim.

### 2.4 Stage 3: collective regulation (Levels 1–3, group level)

**3a** is the islet (human target, mouse data). **3b** is bioelectric pattern maintenance:
planarian polarity on fixed geometry (D134), E07's written discs, MG0b's walls, E15's recovery path.

| Configuration | Cells form | Islet arm | Pattern arm |
| --- | --- | --- | --- |
| Independent cells | Junction availability 0 | The Cx36-knockout analogue | Isolated templates at their own steady state (D133) |
| Coupled cells | Nominal junctions | Wild type | E07's cue-written sheet; MG0b's walls |
| Coupled, changing connectivity | Scheduled availability (D155's control arm); species-regulated availability; replacement with a formation lag | Partial coupling; junction blockers | E07's turnover; a transient (octanol-like) block; cut and restore |

- **Held-out perturbations:** glucose steps (FR-10), K_ATP openers and blockers as availability
  changes, partial coupling; turnover schedules, recut readouts, block timing.
- **Track E is the same question.** D155 asks whether weakly coupled cells slow or block
  conduction, and whether clustering matters. That is the islet's Cx36 wave question, on the same
  sheets and with the same channel laws. Its independent references (`validation/excitable/`) and
  M3's grid carry over.
- **The central question as a test:** do per-cell variables (ATP, volume, Ca²⁺) stay in their bands
  while a collective variable (synchrony, a wave pattern, a written domain) is kept or restored?
  Uncoupled cells are the control.
- **The group-level boundary:** declare the candidate blanket (boundary cells and the outside nodes
  they face) before the runs. Test interior–exterior conditional independence given it, which needs
  noise (§3.6). Compare the group model with reduced descriptions, as E12 asks.
- **Islet data:**
  - The Cx36 perturbations found so far are analysis only: Ravier et al. 2005 (no stated terms) and
    Benninger et al. 2008 (Elsevier's non-commercial user licence).
  - Stožer et al. 2013 and Johnston et al. 2016 are CC BY papers; their raw data were not checked.
  - Huber & Phelps 2025 (Zenodo 10.5281/zenodo.14605547, CC BY) holds calcium-imaging videos of
    human pancreas slices, about 33 GB, with no perturbation in its record.
- **Pattern data:** Durant 2017 (non-commercial) and Oviedo 2010 (no stated terms) are analysis
  only; Emmons-Bell 2015 is CC BY. The visualizer's audit lists the rest.
- **References:**
  - 3a: Track E's references, and a heterogeneously coupled islet model written from equations.
    Benninger et al. 2008's own model would need D138 approval.
  - 3b: the existing heredity and MG0b references, with BETSE and BITSEY as before.
- **The claim:** collective attractors and controllers first. Any organ-level predictive account must
  beat the conventional coupled model on held-out perturbations, and in Cells that model is the
  engine model itself.

## 3. Engine issues

### 3.1 Method

One minimal published model per stage was mapped term by term onto the engine's law tables. Nothing
was run. Levels follow D156 (implemented, guarded, numerically qualified, judged).
- **The "D172 round" column holds only list (a)** ([INNER_MODEL_V4_DESIGN.md](INNER_MODEL_V4_DESIGN.md)
  §15.1): A1 declarations with build-time selection, A5 the passive law, A6 door S's runtime merge,
  A7 species identity with one sum order. CURRENT_PLAN also puts the run-view writer (D154) in the
  round.
- List (b), B1–B8, holds reserved interfaces, not code.

### 3.2 Stage 1a, term by term

The minimal model is the MWC-plus-mean-methylation class (Tu et al. 2008; Shimizu et al. 2010). The
detailed alternative writes methylation levels and activity states as species.

| Term | Main today | D172 round | Missing | General? |
| --- | --- | --- | --- | --- |
| Stimulus program | `scheduled_bath_composition@1` (implemented): steps on the dt grid inside measured regions ([BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) §7–§8); D150's faces carry it (numerically qualified) | A6 | Ramps and sine waves as admitted staircases; D169's staircase probe | Yes: FR-10's next step |
| Ligand at the receptor | A finite node faced to the dosed bath, since sites and exchange refuse held-bath patches ([SITE_OCCUPANCY_DESIGN.md](SITE_OCCUPANCY_DESIGN.md) §0, item 9) | — | Nothing, for a lumped cell | — |
| Receptor binding | `site_occupancy@1` (implemented): Langmuir sites, one K_d per population | — | Activity-dependent affinity; **occupancy as a coupling source** (a door, SITE_OCCUPANCY §2.6) | Yes: receptor signalling, quorum and morphogen sensing |
| Activity a = MWC(m, L) | Hill factors, which multiply ([SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) §2.2). MWC is a logistic of a sum of energies, not such a product (**S**) | B8 reserves a reduced law's declaration (D175) | **An allosteric two-state factor**, or explicit activity-state species | Yes: PFK (3a), gated channels |
| Methylation, the memory | `hill_regulated_two_state@1` is first order with an input-dependent steady state, so it cannot adapt perfectly; its zero-order regime is excluded ([INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md) §1.5). D152's Michaelis–Menten law with a catalyst (guarded) is admitted; zeroth-order consumption is refused | A7: a cap raise needs only a guard world and a cost | (i) Methylation × activity species with Michaelis–Menten enzymes, above 16 rows (**S**); or (ii) **the two-state law's zero-order regime**, with an output-dependent rate | (i) Yes, now (D177). (ii) Yes: modification cycles |
| Kinase, phosphotransfer, CheZ | D152's operator, numerically qualified within MG0c's scope | — | The allosteric factor on autophosphorylation | — |
| Fast and slow rates together | D152 v1 refuses dt·L > 1 | B5 reserves implicit routes | The stiff door (D152 §7.3), or a small dt | Yes |
| Femtolitre cell, low copy numbers (**S**) | Syn3A's P0: floors marginal at small scale; neutral trace rows need species-scaled floors ([SYN3A_MINIMAL_CELL_TRACK.md](SYN3A_MINIMAL_CELL_TRACK.md) §5.1) | A7's trace policy | Species-scaled floors | Yes |
| FRET and rotation readouts | Hill factors; observers | The run-view writer | Observation models in an organism definition (ARCHITECTURE; Syn3A §10) | Organism data |

Stage 1a is a one-cell world over minutes of biological time: CPU minutes, with no FR-8 (**S**).

### 3.3 Stage 1b, term by term

| Term | Main today | Missing | General? |
| --- | --- | --- | --- |
| Motor switching | None. Gillespie kernels exist only in the assembly family (`assembly/kernel.py`; ARCHITECTURE, "Levels of detail") | **A stochastic regime** on the shared inventory and regulatory states, with keyed streams | Yes: Syn3A's F11 and F14; E15's noise operator (E07 tier 2) |
| Position and swimming | None. `apical_vertex_mechanics@1` moves vertices of a fixed, standalone tissue | **A motile cell:** position state and a velocity law driven by internal state | Yes: ARCHITECTURE's next spatial extension ("Communication and space"); E15 §1.6's migration |
| A spatial gradient | D150's faces between outside nodes, held baths as sources and sinks; static | **Field sampling at a moving position** | Yes (same section) |
| Many swimmers | Independent-world ensembles | Non-interacting swimmers sharing one field | Yes |

**What the D172 round adds here: nothing.** List (a) holds no stochastic, motility or
field-sampling item.

### 3.4 Stage 2, term by term

| Term | Main today | Missing | General? |
| --- | --- | --- | --- |
| Cues A then B | FR-10's bath schedule | — | — |
| Uptake | D150 exchange; the passive law (A5) in the round | A regulated rate: the routing door (FR-6 item 2) | Yes (FR-5, FR-7) |
| Regulated synthesis | D152 source reactions with Hill factors (**S**) | **The gene-regulation layer** (held, D145); transcription and translation (F10, held) | Yes, held |
| Delays | Chains of species (**S**). D152 v1 refuses delays; only the junction-formation law has a lag | A delay law or a declared chain | Yes |
| Temperature cue | `temperature_K` is fixed (`core/surface_tissue_spec.py`); no Q10 or Arrhenius law in `src/cells` (grep) | **Scheduled temperature with temperature-dependent rates** | Yes: channel Q10s, MG5–6's clock |
| Fitness | Prescribed division only | Growth and state-triggered division (lifecycle milestone 2) | Yes, planned |
| Evolution | None (ROADMAP, "Other research options"; E11's rules) | Variation, selection, reproduction | Defer; analyse evolved strains as data |
| Hours | Fixed steps | FR-8 | Yes |

**What the D172 round adds here:**
- A5's passive law, for uptake.
- A1's declarations: a delay or temperature-dependent law becomes a declaration, traced only where
  declared.
- B1 only reserves FR-8's step context; it is not code.

### 3.5 Stage 3, term by term

| Term | Main today | Missing | General? |
| --- | --- | --- | --- |
| Cx36 junctions | @3's `junction_voltage_relaxation@1`; `junction_ungated@1` follows the round (D176) | — | — |
| Excitable membrane | @3's NaV1.2, Kir2.1, Kv1.5 (Track E M1–M2) | L-type Ca²⁺ and Ca²⁺-activated K⁺ in the composite: older calcium/ER family only, awaiting Track E M5 and D167's move | Yes, planned |
| K_ATP | The coupling operator's channel target through a regulatory state (numerically qualified, CPU) | ATP and ADP rows (F2) from the finite-fuel case; perhaps a weakly rectifying K⁺ law (**S**) | Yes: a composition |
| Glucose → ATP | D152 reactions; maintained fuel today | The finite-fuel case (D176 item 2); the allosteric factor for glycolytic oscillations | Yes |
| Insulin secretion | D150 export at scheduled rates; FR-1 compartments as granules | A Ca²⁺-set rate: **the routing door** | Yes (FR-5, FR-7) |
| Changing connectivity | Scheduled and species-regulated availability; formation after replacement | Activity-dependent junction abundance (E15 §1.1; D145's molecular-loop unit); new contacts | Yes, planned |
| 100–1,000 cells over hours | The 127-cell sheet on CPU; the 825-node tissue needs GH200 or a long-time method | FR-8; the field-solver interface | Yes |
| Group blanket test | None | The stochastic regime, plus an analysis in `validation/` | Yes |

**What the D172 round adds here:**
- A1: a new K⁺ law, or the moved Ca²⁺ laws, become declarations traced only where declared.
- A5: glucose uptake.
- A6: bath → uptake → compartment → reaction chains, for dosing and granules.
- A7: cheap cap raises for metabolite rows.

The fuel rows come with the finite-fuel case after the round, and `junction_ungated@1` after it too.

### 3.6 The candidate gaps, confirmed or refuted

| Candidate | Verdict |
| --- | --- |
| "Deterministic and continuum" | **Refuted as a blanket statement; confirmed for the shared inventory.** Assembly runs Gillespie kernels; `physiological_noise_perturbations@1` is arithmetic only validation uses. Needed for motor switching, single-cell variability and every blanket test |
| Motile cells in a gradient | **Confirmed missing** (E15 §1.6) |
| Spatially varying bath or fields | **Refuted in part.** Static variation exists (D150's faces, held-bath boundaries, MG0a). Missing: sampling at a moving position; sparse field IDs for large sheets (E15 row 10) |
| Multi-state receptors, methylation | **Partly expressible** by D177's pattern. Missing: activity-dependent affinity, the occupancy door, rows above 16 (raised as needed, D165). A multi-state population waits for a second consumer (D177); this track would be one |
| Gene expression and delays | **Confirmed missing, and held** (D145; F10; D152 §7.2) |
| Long durations (FR-8) | **Confirmed open.** Stage 1a does not need it; Stages 2 and 3 do |
| Learning or evolution | **Confirmed missing.** Within-life learning fits a slow state with its own law (ARCHITECTURE, "Simulation state"); evolution needs E11's rules |
| Observation model, calibration | **Confirmed missing, planned:** it lands with its first consumer, expected to be Syn3A's S2-M1 |
| The comparison harness | **Belongs in `validation/`.** Control and AIF arms are fitted descriptions, not physics. A claim that chemistry implements AIF must be engine chemistry, with the AIF reading as analysis |
| *Found here* | The MWC factor, zero-order adaptation, a temperature control, Ca²⁺-set secretion |

### 3.7 Ranking, by what each gap unblocks

| Rank | Item | Unblocks | Other consumers (D144) | Agent-days (**S**) |
| --- | --- | --- | --- | --- |
| 1 | MWC factor, plus occupancy as a coupling source | Stage 1a; 3a's glycolysis | PFK, gated channels; quorum and morphogen sensing | 5–8 |
| 2 | Adaptation with an output-dependent rate | Stage 1a's adaptation and knockout | Modification switches; FR-6's states | 3–5 |
| 3 | An *E. coli* organism instance with observation models | Any judged Stage 1 result | The organism structure (Syn3A §10) | 2–3 |
| 4 | A stochastic regime (F11) | Stage 1b; single-cell data; all blanket tests | Syn3A Stage 4; E07 tier 2; F14 | 12–18, shared |
| 5 | Motile cells with field sampling | Stage 1b's action loop | E15's migration; field-directed migration | 12–15 |
| 6 | FR-8 | Stages 2 and 3 at hours | Priority 2 already | Its own milestone |
| 7 | Fuel case, Track E's calcium, routing door | Stage 3a | FR-4, FR-5, FR-7; Track E | Planned; 5–8 more for the islet |
| 8 | Gene regulation with delays | Stage 2 | Heredity Stage D; the GRN track | 15–25, held |
| 9 | Scheduled temperature | Stage 2's temperature arms | Channel Q10s; MG5–6 | 2–3 |
| 10 | Activity-dependent junctions | Stage 3's plastic connectivity | The molecular loop; Cortés-Poza group 2 | Planned |
| 11 | Evolution across generations | Stage 2's evolution arm | E10, E11 | Not recommended |

**One-experiment physics to avoid (D144):**
- a chemotaxis-pathway operator, or a run-and-tumble mode for *E. coli*;
- an islet module coupling glucose, ATP and K_ATP in one law;
- an "anticipation" operator;
- "belief", "prediction error" or "blanket" fields in engine state, or an AIF controller in
  `src/cells`;
- a planarian regeneration operator, which E15 already rules out.

### 3.8 The comparison harness, in `validation/`

- **Classes registered before held-out data are opened:** M, the Cells model; C, a controller
  (integral feedback, PID or a filter); A, an AIF model with its generative model, precisions and
  action rule declared; N, a static-gain null.
- **Splits by perturbation class,** as in §2. Non-commercial data stay in the workspace; judged
  verdicts rest on permissive data.
- **Score:** held-out log predictive density under a declared observation model, penalised for
  complexity, per class, with a registered margin.
- **Planted tests:**
  - data from a planted controller and a planted AIF agent are each traced to their generator above
    a registered rate;
  - an identical-dynamics pair comes out "indistinguishable";
  - a planted misspecification loses.
- **Verdicts per class:** M, C or A preferred; indistinguishable; or all fail.
- **Status:** analysis code. Alone it runs no engine model, so it is tooling needing the user's
  approval (AGENTS.md). A published model as an arm needs per-paper approval (D138).

## 4. Organisms

- ***E. coli* is not a target.** Adding it would be an organism instance in Syn3A §10's structure,
  data only, declaring no laws:
  - strains, with the CheR/CheB and CheZ mutants;
  - media, and temperature as a declared condition;
  - parameters bound to evidence records;
  - FRET and rotation observation models;
  - an evidence inventory with licences;
  - registered benchmarks.

  It is about 2–3 agent-days (**S**). The viewer's bacterium is *M. pneumoniae* (FR-11).
- ***M. pneumoniae* offers no Stage 1 counterpart.** Genome analyses find no two-component homologs,
  and its gliding shows no obvious chemotaxis, though that is not excluded experimentally (Miyata &
  Hamaguchi 2016, read through a summary). Its rebuffering case (Syn3A §9.3) could be a Level 1
  homeostasis test without a new organism. It has no knockout-like arm and rests on non-commercial
  data.
- **Syn3A offers none.** No motility or taxis was found reported; its gene list was not searched
  here.
- **Human and mouse** carry Stage 3a. Neutrophil chemotaxis (spatial sensing, polarity, migration)
  would be far heavier and was not checked. **The planarian** carries 3b on fixed geometry (D134).

## 5. External references

They run out of process only, are compared against saved outputs, and are never copied (AGENTS.md).
- From-equations references by an independent agent come first. A published model reproduced as a
  reference needs per-paper approval (D138).
- Licences were read from each repository's licence file (GitHub API, 15 November 2026).

| Reference | Use | Licence |
| --- | --- | --- |
| RapidCell; MicrobeAgents.jl | Pathway with swimming; agent-based run and tumble (Stage 1b) | MIT; MIT |
| NFsim; BioNetGen | Rule-based methylation states: Stage 1a's detailed reference | MIT; MIT |
| Smoldyn | Spatial stochastic signalling | GPL-3.0 |
| Tellurium; libRoadRunner; COPASI; VCell | ODE and SSA runs of SBML models | Apache-2.0; Apache-2.0; Artistic-2.0; MIT (its own code) |
| AgentCell; StochSim | Single-cell chemotaxis; stochastic receptor complexes | Not found or not checked |
| pymdp; ActiveInference.jl; RxInfer.jl | The harness's AIF arm | MIT; MIT; MIT |
| SPM (DEM toolbox) | Continuous-state AIF | GPL-2.0 |
| BETSE; BITSEY | Stage 3b's bioelectric references, already in use | As recorded in their notes |

BioModels' terms were not verified: the page refused automated access.

## 6. Dependencies, order and options

**Fixed points:**
- nothing lands before D172's single landing;
- the track never delays FR-4 or FR-5;
- the stochastic regime is built once, for Syn3A and this track.

| Option | Content | Prerequisite and gate | Agent-days (**S**) |
| --- | --- | --- | --- |
| 0. Deferred | This note | — | 0 |
| **1. Stage 1a** | Ranks 1–3, independent references, harness version 0, a registered protocol | The round landed; FR-4 and FR-5 merged; FR-3 judged. Gate: a judged Stage 1a protocol | 20–28 |
| 2. Stages 1a and 1b | Option 1 plus ranks 4–5 and a swimming protocol | Option 1; the stochastic regime scheduled with Syn3A | 45–60 |
| 3. Stage 3a, the islet | The islet world on the fuel case, Track E's calcium and the routing door | The fuel case; Track E M5; FR-8 or GH200 | 25–35, plus compute |
| 4. Stage 2 | Gene regulation, temperature, a protocol | D145's hold lifted; FR-8 | 30–45 |
| 5. Harness alone | Tooling on published data; no engine model | The user's explicit approval | 5–8 |

**Recommended: option 0 now, then option 1** once the round, FR-4 and FR-5 are through. Its engine
items are general doors with registered consumers, its judged data are permissive with a knockout
arm, and its claims stop at Level 1. Stage 3a follows Track E and the fuel case. Stage 2 comes only
if the user lifts D145's hold.

## 7. Open questions for the user

1. **Start:** keep the track deferred, or adopt option 1 for after the round?
2. ***E. coli*:** may it enter as an organism instance (data only)? If not, Stage 1 has no
   counterpart, and *M. pneumoniae*'s rebuffering stands in as a homeostasis test.
3. **D138:** may published models (a chemotaxis model, an AIF chemotaxis agent, an islet model) be
   out-of-process references, or only references written from equations?
4. **The harness:** approve it as tooling, or only alongside Stage 1a's engine run?
5. **Licences:** judged Stage 1 results would rest on Keegstra et al. 2017 (CC BY). That set covers
   step responses, recovery, dose response and the knockout.
   - One of the three observables you named, the ~4 s comparison, has no permissive judge. The
     impulse responses have no stated terms, and the ramps and sine waves (Shimizu et al. 2010) are
     non-commercial.
   - Accept it as analysis only, or should we look further for permissive data?
6. **Stage 2:** lift D145's hold for it, or keep it deferred?
7. **Islets:** accept them for Stage 3a? Their Cx36 data found so far are analysis only. The human
   slice deposit would be downloaded only when the stage starts.
8. **The group-level blanket test:** in scope? It needs the stochastic regime.

## Provenance

- **In the repository:** the documents and code cited above, read at `bd8f1e9f`.
- **Outside it:**
  - abstracts through Europe PMC's REST API;
  - records through Crossref;
  - one full text, Keegstra et al. 2017;
  - one Zenodo record;
  - licence files through the GitHub API.
- **Not read:** the full texts of the anticipation, impulse-response, filtering, information and islet
  papers.
- **Privacy:** every request used a generic client name. No author was contacted (D173), and nothing
  was downloaded.

## References

Read levels:
- **[A]**, the abstract;
- **[F]**, the open full text, searched;
- **[S]**, press or search summaries only;
- **[T]**, the title and record only.

**Licence classes** are in the [source log](/mnt/workspaces/Cells/fep-track-20261115-01/sources.json).

- Aguilera M, Millidge B, Tschantz A, Buckley CL (2022) *Phys Life Rev* 40:24–50. doi:10.1016/j.plrev.2021.11.001 [A]
- Alon U, Surette MG, Barkai N, Leibler S (1999) *Nature* 397:168–171. doi:10.1038/16483 [A]
- Andrews BW, Yi TM, Iglesias PA (2006) *PLoS Comput Biol* 2:e154. doi:10.1371/journal.pcbi.0020154 [A]
- Baltieri M, Buckley CL (2019) *Entropy* 21:257. doi:10.3390/e21030257 [A]
- Barkai N, Leibler S (1997) *Nature* 387:913–917. doi:10.1038/43199 [A]
- Benninger RKP, Kravets V (2022) *Nat Rev Endocrinol* 18:9–22. doi:10.1038/s41574-021-00568-0 [A]
- Benninger RK, Zhang M, Head WS, Satin LS, Piston DW (2008) *Biophys J* 95:5048–5061. doi:10.1529/biophysj.108.140863 [A]
- Biehl M, Pollock FA, Kanai R (2021) *Entropy* 23:293. doi:10.3390/e23030293 [A]
- Block SM, Segall JE, Berg HC (1982) *Cell* 31:215–226. doi:10.1016/0092-8674(82)90421-4 [A]
- Bruineberg J, Dołęga K, Dewhurst J, Baltieri M (2022) *Behav Brain Sci* 45:e183. doi:10.1017/S0140525X21002351 [A]
- Cluzel P, Surette M, Leibler S (2000) *Science* 287:1652–1655. doi:10.1126/science.287.5458.1652 [T]
- Colombo M, Wright C (2021) *Synthese* 198:3463–3488. doi:10.1007/s11229-018-01932-w [A]
- Durant F, Morokuma J, Fields C, Williams K, Adams DS, Levin M (2017) *Biophys J* 112:2231–2243. doi:10.1016/j.bpj.2017.04.011 [A]
- Emmons-Bell M, Durant F, Hammelman J, et al. (2015) *Int J Mol Sci* 16:27865–27896. doi:10.3390/ijms161126065 [A]
- Friston K, Levin M, Sengupta B, Pezzulo G (2015) *J R Soc Interface* 12:20141383. doi:10.1098/rsif.2014.1383 [A]
- Friston K, Da Costa L, Sajid N, et al. (2023) *Phys Rep* 1024:1–29. doi:10.1016/j.physrep.2023.07.001 [T]
- Huber MK, Phelps EA (2025) Calcium imaging videos from human pancreas slices. Zenodo. doi:10.5281/zenodo.14605547 [the deposit record]
- Johnston NR, Mitchell RK, Haythorne E, et al. (2016) *Cell Metab* 24:389–401. doi:10.1016/j.cmet.2016.06.020 [T]
- Keegstra JM, Kamino K, Anquez F, Lazova MD, Emonet T, Shimizu TS (2017) *eLife* 6:e27455. doi:10.7554/eLife.27455 [F]
- Korobkova E, Emonet T, Vilar JMG, Shimizu TS, Cluzel P (2004) *Nature* 428:574–578. doi:10.1038/nature02404 [A]
- Kuchling F, Friston K, Georgiev G, Levin M (2020) *Phys Life Rev* 33:88–108. doi:10.1016/j.plrev.2019.06.001 [A]
- Lan G, Sartori P, Neumann S, Sourjik V, Tu Y (2012) *Nat Phys* 8:422–428. doi:10.1038/nphys2276 [A]
- Mattingly HH, Kamino K, Machta BB, Emonet T (2021) *Nat Phys* 17:1426–1431. doi:10.1038/s41567-021-01380-3 [S]
- Mitchell A, Romano GH, Groisman B, et al. (2009) *Nature* 460:220–224. doi:10.1038/nature08112 [A; details S]
- Miyata M, Hamaguchi T (2016) *Front Microbiol* 7:960. doi:10.3389/fmicb.2016.00960 [S]
- Nakamura K, Kobayashi TJ (2021) *Phys Rev Lett* 126:128102. doi:10.1103/PhysRevLett.126.128102; arXiv:2005.13208 [A of the arXiv version; details S]
- Oviedo NJ, Morokuma J, Walentek P, et al. (2010) *Dev Biol* 339:188–199. doi:10.1016/j.ydbio.2009.12.012 [A]
- Raja V, Valluri D, Baggs E, Chemero A, Anderson ML (2021) *Phys Life Rev* 39:49–72. doi:10.1016/j.plrev.2021.09.001 [T]
- Ravier MA, Güldenagel M, Charollais A, et al. (2005) *Diabetes* 54:1798–1807. doi:10.2337/diabetes.54.6.1798 [A]
- Rorsman P, Ashcroft FM (2018) *Physiol Rev* 98:117–214. doi:10.1152/physrev.00008.2017 [A]
- Sartori P, Granger L, Lee CF, Horowitz JM (2014) *PLoS Comput Biol* 10:e1003974. doi:10.1371/journal.pcbi.1003974 [T]
- Satin LS, Zhang Q, Rorsman P (2020) *Diabetes* 69:830–836. doi:10.2337/dbi19-0012 [A]
- Segall JE, Block SM, Berg HC (1986) *PNAS* 83:8987–8991. doi:10.1073/pnas.83.23.8987 [A]
- Shimizu TS, Tu Y, Berg HC (2010) *Mol Syst Biol* 6:382. doi:10.1038/msb.2010.37 [A]
- Sontag ED (2003) *Syst Control Lett* 50:119–126. doi:10.1016/S0167-6911(03)00136-1 [T]
- Sourjik V, Berg HC (2002) *PNAS* 99:123–127. doi:10.1073/pnas.011589998 [A]
- Stožer A, Gosak M, Dolenšek J, et al. (2013) *PLoS Comput Biol* 9:e1002923. doi:10.1371/journal.pcbi.1002923 [T]
- Tagkopoulos I, Liu YC, Tavazoie S (2008) *Science* 320:1313–1317. doi:10.1126/science.1154456 [A; details S]
- Tu Y, Shimizu TS, Berg HC (2008) *PNAS* 105:14855–14860. doi:10.1073/pnas.0807569105 [A]
- Waade PT, Olesen CL, Laursen JE, Nehrer SW, Heins C, Friston K, Mathys C (2025) *Entropy* 27:143. doi:10.3390/e27020143 [A]
- Yi TM, Huang Y, Simon MI, Doyle J (2000) *PNAS* 97:4649–4653. doi:10.1073/pnas.97.9.4649 [T]

**Software (§5)**, with licences read from the repositories:
- RapidCell: Vladimirov et al. 2008, doi:10.1371/journal.pcbi.1000242.
- NFsim: Sneddon, Faeder & Emonet 2011, doi:10.1038/nmeth.1546.
- Smoldyn: Andrews & Bray 2004, doi:10.1088/1478-3967/1/3/001.
- pymdp: Heins et al. 2022, doi:10.21105/joss.04098.
