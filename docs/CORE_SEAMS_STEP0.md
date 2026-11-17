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

## 5. The probes (criteria follow, before they run)

The cardiac booking probe and mitochondria's P1 (CORE_SEAMS_DESIGN §6.4), in scratch only, after
items 1–4.
