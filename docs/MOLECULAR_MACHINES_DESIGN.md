# Molecular machines: individually and in aggregate, at the detail set by what is looked at (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

*Status: proposed, 17 November 2026, for the lead and then the user (FR-13, D204). Docs only:
nothing here is built, and nothing is built before the user has discussed the options (D142).
Branch `machines-design` from main e5edba97. Code is cited `file`:line at e5edba97, by today's paths
under `src/cells/` (D188's move 2 has not landed). Each claim about the engine carries a status:
**[main]** on main at e5edba97; **[designed]** an approved design, not on main; **[branch]** built
on a branch, not merged; **[none]** not designed. **S** marks this note's own reading or proposal.*

**Engine models (AGENTS.md):** none; this note runs none. Its options would extend
`resolved_pump_tissue@3` with `cells.transporter@1` (seam A), `local_species_reactions@1` (D152),
`membrane_entity_state@1`, `capsid_graph@1`, `finite_bond_assembly@1` and
`cells.assembly_lineages@1`.

**The request (D204).** The user, 17 November 2026: "yes new feature request from me"; "only thing
with the machines, if there is something missing in our core archtecture or if they can be naturally
modeled there"; "and we'd to be able to model them both individuall and in aggregate in a cell or
whatever, LODs based on what is being looked at". The user then asked, through the lead: "is it
possible to extend a model or an operator, like object oriently?" (§6). The scope is D140's:
assembly of folded subunits, not folding.

## 0. The answer in short

**Partly natural.** A machine's *use in aggregate* fits the core's existing pattern: a law over a
population on a host, with what it moves booked on the ledgers. That holds today for channels and
pumps on membrane patches, and seam A [designed] extends it to any membrane cycle. The core's design
rules also reach further: hosts, populations, declared laws, keyed random streams and declared
representations (D175). What is not built is a set of general features those rules already
anticipate (§7; the options and the recommendation are in §8):
- the states of a machine's cycle;
- assembly from subunits;
- individual machines with their own identity, coupled both ways to the cell;
- a level of detail that follows what is looked at.

| Layer | What the core hosts | What is missing |
| --- | --- | --- |
| **Aggregate:** copy numbers, rates, ledgers | [main] Channel populations with an abundance and mean gate fractions (`definitions/surface_kinetic_spec.py`:84–92); @3's junction law and two pumps (`models/inner_laws.py`:131, :146); no exchanger on @3; the transporter kind, one population per patch, n of 1–4 (`kinds/transporter.py`:41, :164); abundance as state, with its own ledger (`operators/membrane_state.py`:1–30); D152's reactions, with a Michaelis–Menten law that reads a catalyst row (`operators/species_reactions.py`:21–24). [designed] Seam A: any integer stoichiometry, many populations per host, finite fuel. Seam B: capacity as extensive state | Copies made from, and returned to, subunit rows: units appear today from an operator's booked supply. A host for soluble machines, which have one end, not two |
| **Cycle:** the states of the working cycle | [designed] Seam A's §16: Hill cycles, Wegscheider's condition at parse, Σ J·ΔG ≤ 0, one-way fluxes. These are lumped steady-state fluxes, and a law holds no cycle state | A law that declares the cycle's states and edges. The individual chain, the occupancies and the lumped flux all follow from it |
| **Assembly:** subunits, stoichiometry, order | [main] `capsid_graph@1`: one prescribed 20-site cage of one subunit type in a held bath (`assembly/graph.py`:7–9; `assembly/spec.py`:18–23). `finite_bond_assembly@1`: the same graph with a finite pool. The lineages family: a bag of label-only types (`models/assembly_lineages/family.py`:1–17). D152's passive mass action, which holds a small pathway with subunits as moieties (`species_reactions.py`:26–28, :37) | A general assembly map: typed subunits, declared intermediates and steps, in three representations |

## 1. One machine, three layers

### 1.1 Aggregate

- **What exists [main].** The engine's membrane laws act on functional units, not on gene products
  (PROTEIN_CATALOGUE_PLAN, stage 2).
  - A channel population has a patch, a law, an abundance and mean gate fractions
    (`definitions/surface_kinetic_spec.py`:84–92).
  - Kinds book what they move into the ledgers by role: material per node, a `produced` record for
    chemistry, heat, work and stored energy (`registry/kind_registry.py`:264, the `ledger_terms` hook).
  - @3 runs a junction law and two pumps on maintained fuel (`models/inner_laws.py`:131, :146). No
    exchanger runs on @3.
- **Only in `legacy/`** (D196): finite energy (`legacy/processes/finite_energy.py`), mitochondria
  (`legacy/processes/mitochondrial_passive.py`), pumps whose abundance is state
  (`legacy/models/surface_redistribution.py`), the Na⁺/Ca²⁺ exchanger (its law,
  `laws/reactions/plasma_calcium.py`:16, runs only in older families) and the assembly–cell coupling.
- **Copy number as state [main].** `membrane_entity_state@1` holds each population's abundance in
  units, under an entity ledger (`membrane_state.py`:1–30).
  - Each population also carries a functional-unit ID and a catalogue reference (:62–67).
  - Its writer, insertion, adds units and books them in its own `inserted_units`; no material is
    consumed (`operators/membrane_insertion.py`:428, :490).
- **What is missing (S).** Units are not made from subunit rows, so a cell cannot spend material on
  new pumps. Seam E's moieties [designed] can state what a complex is made of, but nothing ties a
  population's capacity to an amount on the inventory. FR-7 asks for the same link.
- **ATP use today is a supply record, not a moved row.** The transporter's held fuel records ATP in
  `transporter_fuel_supplied_fmol` (`transporter.py`:33, :169) and refuses finite fuel (:193).
  Seam A [designed] moves fuel rows.
- **Soluble machines have two partial routes:**
  - **D152's Michaelis–Menten law with a catalyst row [main].** It takes exactly one reactant, so it
    cannot spend ATP (:24). It is driven: it books work, with no J·ΔG guard. It takes neutral
    species only, at most 16 (`species_common.py`:47; `species_reactions.py`:80).
  - **Seam A's cycle kind on a host with one end (S).** Its hosts have two ends (CORE_SEAMS §2). A
    node host, both ends one node with voltage rule zero, makes ΔG_m = Σ ν μ̃ the reaction's free
    energy at that node, under the same contract. This is small and general.

### 1.2 Cycle

- **Seam A's contract [designed].** The kind computes each mode's ΔG from the registry. The law
  gives a pure kinetic factor S ≥ 0, and J = k a S (1 − e^{ΔG/RT}) (CORE_SEAMS §3.2). §16 admits a
  law only if each declared Hill cycle meets Wegscheider's condition. It guards Σ J·ΔG ≤ 0 at run
  time and exposes both one-way fluxes.
- **Its thermodynamic form carries over to any stoichiometric cycle,** transporter or not; its hosts
  and the inventory's rows do not yet. ATP synthase fits as designed. A proteasome needs a node host
  (N2) and protein rows, and a translocon needs rows for nascent chains.
- **It cannot host two kinds of output:**
  - mechanical output: there is no torque or momentum ledger (MODULE_SYSTEM §7, rule (a));
  - work along a template, such as a ribosome's place on an mRNA (F10).
- **It holds no cycle states.** Hill's diagram method gives a cycle's steady-state flux, and seam A
  keeps only that flux. Channels hold states as mean gate fractions [main]. Their gates are
  independent two-state variables that move no chemistry, so no cycle check applies to them.
- **The proposal (S): one diagram, three levels.** A law declares states and edges. Each edge has
  rate kernels k⁺ and k⁻ and names the species it binds or releases at an end. From that one
  declaration:
  - **individual:** a continuous-time Markov chain on the states, one machine;
  - **occupancy:** the master equation dn/dt = W(c, V) n over the population's counts per state;
  - **lumped:** the diagram's steady-state flux, which has seam A's form.
- **One check serves all three (S):** local detailed balance per edge.
  - Each edge's k⁺/k⁻ must equal e^{−ΔG_e/RT}, with ΔG_e from the registry's potentials and the
    declared state free energies.
  - It implies Wegscheider's condition for every cycle (§16), and the converse holds (§10.2). It is
    also the stochastic kernel check of GARD_DESIGN §2.4.
- **Run-time guards follow the level:** lumped, Σ J·ΔG ≤ 0 per population (§16); occupancy, heat
  booked from the edges' affinities and closing against the free-energy state function; individual,
  event heat declared non-monotone and closing the same way (GARD_DESIGN §2.4).

### 1.3 Assembly

- **What exists [main]:**
  - **`capsid_graph@1`:** a 20-bit occupancy on a fixed dodecahedral graph, with one subunit type
    at one held concentration. It runs one rooted assembly per world, by exact stochastic
    simulation with keyed streams (`assembly/graph.py`:7–9; `assembly/spec.py`:18–23).
  - **`finite_bond_assembly@1`:** a finite pool and breakable bonds, on the same graph.
  - **The lineages family:** counts of label-only types in an ideal-mixing assembly, with no
    positions or order. Its population mode is refused (`models/assembly_lineages/spec.py`:301–302).
- **Neither generalises to a stoichiometric complex as it stands.** A ribosome or proteasome has
  many subunit types, a fixed copy number of each and a partial joining order. The capsid code fixes
  the graph and the subunit type, and the lineages family has no structure.
- **D152 holds a small pathway in aggregate today [main].**
  - Each intermediate is a neutral species whose moieties are its subunits.
  - Each joining step is a passive mass-action reaction, checked for moiety closure in integers
    (`species_reactions.py`:26–28, :37).
  - Its limits: molecularity of at most 3 per side, 16 species, neutral species only.
- **The proposal (S): an assembly map.**
  - Typed subunits, with their stoichiometry.
  - Declared intermediates and steps: a directed graph, reduced from a measured map, as the
    whole-cell minimal-cell model reduced *E. coli*'s maps to linear pathways
    (PAPER_REVIEW_WHOLE_CELL §2.1).
  - Each step's binding free energy from the registry.
- **Three representations from one map:**
  - rate equations over the intermediates, deterministic;
  - counts of the intermediates, by exact stochastic simulation;
  - individual complexes, each with a typed site occupancy, as the capsid code holds a bitmask.

  n distinct subunits allow up to 2ⁿ intermediates; the declared map, not the code, keeps them few.
- **Rule (c) binds the deterministic form:** its intermediates must be inventory rows unless kinds
  may own pools (MODULE_SYSTEM §4, §7).

### 1.4 Where a machine sits, "in a cell or whatever"

- **Position is a host [main; seam A designed].** A membrane machine sits on a patch (of any
  membrane: plasma, organelle or vesicle) or a junction; a soluble one sits in a node (a cell, an
  FR-1 compartment or a finite outside node). So the same declaration runs in a cell, in a
  mitochondrion (FR-1's host C, MITOCHONDRIA_DESIGN §1.1), in a proteoliposome or across a tissue.
- **Finer positions are a spatial gap [none].** There is no position within a node and no spatial
  stochastic method. A machine's place in three dimensions is illustration only, in the viewer.

## 2. Individual and aggregate in one compartment

- **Storage fits D142 [main].** A kind's instance is a row on its own axis, with no object of its
  own (MODULE_SYSTEM §3).
  - An individual is then a row: a host index, a cycle state, an assembly state, an identity key and
    an active mask, as @3 masks its channel slots (`models/surface_pump_v3.py`:212).
  - Births and deaths reuse slots under seam B's open, split and retire [designed].
- **The dynamics do not fit yet.** The fixed-step path is deterministic: a checkpoint with random
  state is refused (`io.py`:158–159), and operator events fall on multiples of dt (GARD_DESIGN
  §4.6). Discrete entities live only in the event-driven families, one assembly per lane. The
  assembly–cell families coupled one assembly to an ionic cell one way only (CAPSID_ASSEMBLY.md),
  and now sit in `legacy/`, to be removed (D196).
- **Two ways to coexist (S):**

| | I1: tagged individuals (one-way) | I2: promoted individuals (two-way) |
| --- | --- | --- |
| What | k of the N machines are followed one by one. Each moves on the rates of the occupancy aggregate, at the environment the step computed. The aggregate still holds all N | m machines leave the aggregate (N → N − m) and run as individuals. Their events move material on the shared inventory |
| Exact? | In distribution, for independent identical machines (§3.1), up to the declared quadrature of its hazard: each tag follows the law of any one machine | In principle, if the hybrid clock is right |
| Effect on the run | None: every other array is bitwise the same with tags on or off, as D200 asks of labels | Individuals feed back on the cell |
| Needs | Tag states and per-tag counters as integer state fields. Draws are counter-based from the definition's seed and the tag's key (a `tag` domain), so no random-number state is checkpointed and `io.py`:158–159 stands. Each tag's hazard is integrated over the step by a declared quadrature | F11's stochastic regime: events inside a fixed step, hazards integrated and rescheduled when rates change (MULTISCALE_EXECUTION_ARCHITECTURE, "Coupled numerical execution"); random state in checkpoints |
| Gives | Dwell times, step statistics, one machine to show | Effects of fluctuations at low copy numbers |

- **Identity and streams [main].** In the lineages family, "an assembly's draws depend on its
  identity alone" (`models/assembly_lineages/streams.py`:22–23), folded from the seed, the world,
  the carrier key, a domain and a counter. An individual machine would take the same fold.
- **Relations [branch].** `cells.relations@1` is built on `relations-writer` (35a5bbb9), not merged.
  Its vocabulary is closed (`records/relations.py`:98–107 on that branch). Machines need three
  additions (S):
  - a birth by assembly, `assembled`, and the ends `disassembled` and `degraded`;
  - many parents: `lives.parent` is one entity, but a complex is made of many subunits. An
    `assembled_from` edge, weighted by stoichiometry, would run from pools or from subunit lives;
  - `member_of`, from a tagged or promoted individual to its population node. The `population` node
    kind already exists.
- **At a cell division** an individual keeps its life and changes its `occupies` edge (S).
- **Timing.** The lead's rulings on that branch lift the format's provisional label: "a change to
  the format is now a new version". So these additions are a new version, unless the lead amends
  @1 before it lands on main (§9, L1). Whether any bundle has been shared was not checked.

## 3. Level of detail "based on what is being looked at"

### 3.1 When the aggregate is exact

Take N machines of one type in one node. Each is a Markov chain on the declared diagram (§1.2), with
rates set by the free concentrations c and the voltage V it sees.
1. **Occupancy is exact in expectation** under three conditions: the machines are identical, no rate
   depends on another machine's state, and the path c(t), V(t) is given.
   - The expected counts then obey dn/dt = W(c, V) n exactly, by linearity.
   - The counts are multinomial, so relative fluctuations scale as 1/√(N p_s).
2. **The lumped flux is exact at the cycle's steady state:** when the cycle relaxes much faster than
   c and V change. Hill's diagram method then gives the flux exactly, in seam A's form.
3. **Feedback makes both approximate.** If the machines' own use changes c, the closure
   E[f(c)] ≈ f(E[c]) is exact only for linear f.
   - The error is small when the pools hold many molecules: millimolar ATP is safe.
   - One gene, a few mRNAs or a scarce subunit are not. In a 200 nm cell one molecule is about 50 nM
     (PAPER_REVIEW_WHOLE_CELL §5 item 3). Syn3A's median protein count is about 120 copies, and 10%
     of its proteins have fewer than 10 (SYN3A_MINIMAL_CELL_TRACK §4.3).
4. **Interactions break independence:** machines queueing on one mRNA, cooperative receptor arrays,
   and assembly, whose association steps are bimolecular. Rate equations are then approximate, with
   errors that grow as counts fall.
5. **Material in transit.** A state-resolved machine holds bound ligands, such as ATP on a catalytic
   site; the lumped form holds none. That difference belongs to the declared error budget
   (ARCHITECTURE.md, "Levels of detail").

### 3.2 The meanings, and what each needs

| Meaning | Accounting across a switch | Exact or approximate | Reproducibility | Opt-in | Needs |
| --- | --- | --- | --- | --- | --- |
| **(a) Fixed per run,** per machine type, from the run's declared observables: dwell times need individuals, an ATP budget the aggregate | No switch: each representation closes its own ledgers (D175) | §3.1's conditions | Aggregate: bitwise on CPU. Individuals: keyed by identity | Declared per mechanism; a world that declares none keeps its programs | B8's fields, refused today (`registry/laws.py`:177–185). Its `supports` field would refuse an observation the chosen representation cannot answer |
| **(b) Per region or compartment,** from a declared focus: individuals in one cell, the aggregate in its neighbours | Each region closes its own ledgers. Regions meet only on shared inventory rows, and no machine crosses a boundary | As (a), per region | The focus is in the definition, so in its fingerprint | Declared per scope | (a), plus a representation per scope and synchronised accounting (ARCHITECTURE: "static mixed-detail regions") |
| **(c) Adaptive switching** during a run, as the focus moves | Restriction (individuals to counts) is exact. Prolongation draws individuals from counts. Bound ligands are released or drawn (§3.3) | Prolongation is exact in distribution only from a count-level stochastic aggregate; from deterministic fractions it needs a declared rounding. Hidden history, such as a ribosome's place on its mRNA, cannot be rebuilt | Draws on a `lod` stream keyed by region and switch count. The focus must be a declared schedule, never the live camera, or results depend on who watched | Last: "automatic promotion and demotion is a later milestone" (ARCHITECTURE) | (b), maps both ways, §3.3's bookings, hysteresis |
| **(d) In the viewer only:** a stored run drawn at different detail | None: nothing runs | Counts drawn equal the run's. Individuals drawn from an aggregate are illustration | Drawing seeded by machine ID and time | No engine change | Partly exists: `cells.visualizer.machine@1` has three drawing levels and states "Cells has no model of this motor" (`visualizer/data/machines/ecoli.flagellar-motor.json`) |
| **(e) Zoom by branching (S):** looking closer starts a new run from a stored checkpoint, with a declared focus | One prolongation at the start, booked as in (c); then as (b) | As (b) | The parent run is unchanged. The new run is recorded and judged on its own (D153); its inputs are its focus and start time | Declared by the new run | (b), and a tool that imports the parent's state through a declared map. `cells branch` refuses a changed model (`execution/runner.py`:117–122), and a checkpoint's state type is checked (:80). D153 lets a new run start from imported state, with the tool listed as exempt (`tests/unit/test_continuity_bypass.py`:44) |

### 3.3 Bound material and free energy at a switch

- **Material.** A switch from a state-resolved to a lumped form releases bound ligands to their free
  rows; the reverse draws them.
  - Totals and moieties stay exact.
  - A switch that would take a free row below its floor is refused.
  - From a deterministic aggregate only whole machines are promoted; the fractional remainder stays
    in the aggregate, so totals stay exact (S).
- **Free energy (S).** Two parts change, and neither is heat or physical work:
  - the bound ligands' release, from the diagram's state free energies;
  - the configurational term: the deterministic form's mixing entropy over states, which one
    microstate lacks. It is about k_BT ln of the multinomial count.

  Both are booked to a declared representation term. The energy ledger then closes exactly, and the
  switch's cost is visible. GARD books a fission's change in −k_BT ln π the same way, as signed work
  from an unmodelled agent (GARD_DESIGN §2.4).
- **The J·ΔG guard.** No flux runs during a switch, so the deterministic heat stays monotone, and
  each level keeps its own guard (§1.2).

### 3.4 What "fine is the default" can mean here

- **The rule's origin.** D135 makes coarse time modes optional, with the qualified fine engine as
  the default. The projective mode is opt-in in code: absent, a definition and its run are unchanged
  (`definitions/projective_spec.py`:1–3).
- **It does not carry over directly.** No machine model exists, and today's membrane machines are
  deterministic aggregates. Individuals by default would be unworkable at a cell's copy numbers and
  would change every existing world.
- **Two readings, for the user (§9, U2).** **(A):** each machine declares a reference
  representation, which a world gets unless it opts for another. **(B), recommended:** a world that
  declares nothing is unchanged, and every representation is declared and opt-in. The finer one is
  always the reference when a coarser one is qualified, with the envelope declared first and one
  case outside it failing (D175).

## 4. First machines, chosen by constraint

- **Targets** are JCVI-syn3A, mouse, planarian and human. Presence in bacteria is read from the
  viewer's species files (`visualizer/data/species/*.json`, `cap.machines`). They record no machines
  for the eukaryotes, so that column is general biology (**S**).
- **The data column** was checked for access by web search on 17 November 2026, at the level of
  abstracts and PMC records. Three were then read in full through a page-reading tool (§10.3).

| Machine | Substrates in the modular engine | Free-to-read data for a judged check | Targets that need it | Verdict |
| --- | --- | --- | --- | --- |
| **ATP synthase** | **Yes:** ATP, ADP and Pi rows (D176's F2; `registry/species_registry.py`:5–6), H⁺ with buffering (FR-4), patch voltage [main]. Moving them through a synthesis cycle needs seam A [designed]: `proton_coupled_atp_synthesis_cycle@1` (MITOCHONDRIA_DESIGN §1.2, §4). FR-4's proton law already reverses past its static head, on held fuel | Thermodynamic H⁺/ATP of about 4.0 for the *E. coli* and chloroplast enzymes (Steigmiller et al. 2008, PNAS, PMC2268821). Yeast mitochondria 2.9 ± 0.2, against 3.3 from its 10-subunit ring (Petersen et al. 2012, PNAS, PMC3396544). The bovine ring has 8 c subunits (Watt et al. 2010, PNAS, PMC2947889) | 4 of 4: Syn3A, where its reconstruction runs it in the hydrolysis direction (viewer `syn3a.json`); mitochondria in the three animals | **First** |
| **Ribosome** | **No:** no amino-acid, tRNA, GTP or mRNA rows, no polymers (F10), 16 species | In-cell structures: 101,696 ribosomes from 356 tomograms of *M. pneumoniae*, sorted into 13 ribosome classes (Xue et al. 2022, *Nature*, PMC9534751, open access). About 500 per Syn3A cell, from cryo-electron tomograms (viewer `syn3a.json`; PAPER_REVIEW_WHOLE_CELL §2.6) | 4 of 4 | Needed everywhere, but blocked by F8, F10 and F11; crosses D145's hold |
| **RNA polymerase** | **No:** NTPs, the DNA template and transcripts are absent | Not searched | 4 of 4 | With the ribosome |
| **Proteasome** | **Partly:** ATP yes; protein substrates and peptides as rows, no | Mouse 26S proteasomes: 50–80 ATP per ubiquitinated DHFR, 90–140 when folate stabilises it, 100–160 per ubiquitinated Sic1 (Peth, Nathan and Goldberg 2013, *JBC*, PMC3790020, Table 1; read, §10.3). Assembly kinetics not searched | 3 of 4: not Syn3A, whose annotation lists the proteases FtsH and Lon (viewer `syn3a.json`) | **Second:** D140's named case, a node machine and an assembly case |
| **Translocon (Sec)** | **Partly:** ATP and the proton-motive force yes; nascent chains no | Not searched | 4 of 4: Syn3A's Sec translocon and YidC (viewer); Sec61 in the three animals | After the ribosome, whose products it moves |
| **Flagellar motor** | **Partly:** H⁺ and voltage yes; no torque or momentum ledger | Torque–speed data exist (Berg's group; from memory, access not checked) | 0 of 4 (*E. coli*) | Defer. The viewer already draws it, as illustration |
| **Chemoreceptor arrays** | **Partly:** ligands as neutral rows; no phosphorylation relay | Not searched | 0 of 4 (*E. coli*) | Defer |
| **Attachment organelle** (*M. pneumoniae*) | **No:** mechanics and adhesion are absent | Not searched; its mechanism is less settled | 0 of 4: *M. pneumoniae* only, a validation organism (D173) | Defer |

- **What FR-13 adds to ATP synthase,** beyond FR-4 and D193:
  - its cycle's states, for tagged individuals (the rotary steps);
  - copies made from subunits, lumped into modules while the species cap holds;
  - the machine's declaration (§5);
  - later, its assembly. PROTEIN_ASSEMBLY_IDEAS §6 cites a study of human ATP synthase's 28 subunits
    of 17 kinds.
- **A sharp judged check.** With integer roles per rotation, c H⁺ per 3 ATP, the declared c and the
  registry's potentials fix the zero-flux point, with no free parameter.
  - The measured ratios are for *E. coli*, chloroplast and yeast enzymes; this search found none for
    a target organism. So the first check would run in a reconstituted-vesicle world, with one of
    those enzymes' numbers (**S**).
  - It may fail: Petersen et al. report their ratios outside the rotational models' values. A
    failure would be informative, and is a reason to choose the first acceptance with care.

## 5. What a declared machine would carry

Law IDs name mechanisms, never proteins (`registry/laws.py`:8–9), and copy numbers are values (P5).
So a machine is a declared entity that binds laws; it is not a law itself (S).

| Field | Holds | Where it lives | In the manifest today |
| --- | --- | --- | --- |
| Identity | Functional-unit ID and catalogue reference | As `membrane_entity_state@1` holds them per population (`membrane_state.py`:62–67) | No: `cells.declarations@1` lists laws, kinds and operators (`registry/declarations.py`:75, :80) |
| Subunits and stoichiometry | A moiety vector over subunit species | The species registry, with seam E's moieties [designed] | No |
| Cycle steps | States, edges, rate kernels and Hill cycles | The cycle law (§1.2) | As the law's `fields` |
| Consumption and production | Rows moved per cycle, with signs | The law's moves (`CycleLaw.moves`, `registry/laws.py`:275), inward-positive per forward cycle | Yes, as `changes` and `signs` |
| Location | Host kind (patch, junction or node) and N orientation | The definition, as values | No |
| Representations | Which of individual, occupancy and lumped it admits, with B8's four fields per reduction | The law, once B8 lands | No: B8 is refused today |
| Assembly map | Intermediates and steps | An assembly law (§1.3) | As that law's `fields` |
| Copy numbers and rates | Values with evidence records | Organism definitions (SYN3A_MINIMAL_CELL_TRACK §10), never the manifest | No |

A `machine` piece is a new key set, so a new major of the manifest (LAW_DOCUMENTATION_DESIGN §7;
its @2 is designed, not built). The viewer's Machines tab binds to it once it exists (D204).

## 6. Extension: one general machine law, specialised per machine?

**The lead's findings, checked:**
- **Correct:** laws are frozen declarations on one `Law` base (`registry/laws.py`:128; `ChannelLaw`
  :202; `CycleLaw` :269). A subclass passes registration's `isinstance` check (:399) and is found by
  its inherited interface (:453).
- **Correct:** operators are checked by `check_declarations` at registration
  (`registry/operators.py`:42–45). A `cells` ID names one object, for operators (:53–61) and for
  laws (`register`). So an extension takes a new ID: an ID promises its semantics (D148's reading
  of D147).
- **Partly correct:** "models extend by composition under D191's one rule". Composition over model
  families is D142's and D143's rule: new combinations are definitions. D191 rules how a composition
  reads a field. And inheritance is used today:
  - `scheduled_cell_replacement@2` subclasses @1's operator class, extends its writes and calls @1's
    parser (`operators/cell_replacement_v2.py`:346–380);
  - `membrane_insertion_v2.py`:202 subclasses @1's step checks;
  - specifications inherit version over version (`definitions/surface_kinetic_spec.py`:50;
    `definitions/surface_pump_v3_spec.py`:101);
  - kinds are frozen records of hooks, varied by `dataclasses.replace`, as `bound` does
    (`registry/kind_registry.py`:383–392).
- **Agreed absent:** a declared "extends" link, inherited checks, and version rules between parent
  and child. Two more points:
  - `moved_from`, the nearest precedent, is designed (CORE_SEAMS §8.6) but appears only in a
    docstring (`registry/laws.py`:19);
  - every law's `test` is null (LAW_DOCUMENTATION_DESIGN §8, gap 1), so there is no test to inherit
    yet.

**Do machines need it? Mostly not.**
- **Specialising by parameters** is the main case: one diagram law, with a parameter set per machine
  and organism. That needs only values.
- **Specialising by structure** is rarer: a law that adds states or roles to another. The ATP
  synthesis cycle generalises FR-4's proton law, which keeps its programs (MITOCHONDRIA_DESIGN §4).

**Options:**
- **X0:** nothing new. A structural variant takes a new ID, with the relation in prose.
- **X1, recommended once a first pair exists:** an `extends` field on the law template and on
  operator and kind declarations. It gives the parent ID, what changed, and the special case where
  the child must equal the parent. The parent's kernel test runs on the child at that case, and the
  manifest records the link. About 1–2 agent-days (**S**).
- **X2:** Python subclassing as the declared mechanism. Not recommended: inherited code does not
  state what the child promises (D148), and an overridden kernel can hide a change of meaning.

## 7. Gaps

**New to FR-13** (agent-days are rough, **S**):

| Gap | Why it is general | Consumers | Days |
| --- | --- | --- | --- |
| **N1.** A cycle-diagram law: states, three derived levels and per-level guards (§1.2) | Any enzyme, carrier or channel with explicit states | ATP synthase's steps; channel gating as jump processes (GARD_DESIGN §7.2) | 4–6 |
| **N2.** A node host for seam A (§1.1) | Any soluble machine or enzyme with a cycle | Proteasome; soluble ATP-coupled enzymes for Syn3A's stage 4 (F9) | 0.5–1 |
| **N3.** Copies made from, and returned to, subunit rows; capacity from the count | The closed molecular-to-physiology loop | FR-7; the junction-channel unit (D145); protein turnover (SYN3A_MINIMAL_CELL_TRACK §9.3) | 2–4 |
| **N4.** An assembly map in three representations (§1.3) | Any complex | Proteasome (D140); ribosome subunits; ATP synthase modules; typed capsids | 8–12 |
| **N5.** Tagged individuals, I1 (§2) | Single-entity statistics with no change to a run | Rotary steps; dwell times of any cycle | 2–3 |
| **N6.** Zoom by branching (e), then switching (c) (§3) | Any pair of a reduced and a detailed representation | FR-13; ARCHITECTURE's first level-of-detail consumer (D174's fuel case) | (e) 2–3 and (c) 5–8, each after (b) |
| **N7.** Relations vocabulary for machines (§2) | Any entity made from many parts | FR-13; material provenance of complexes (D200) | 0.5–1 |
| **N8.** A `machine` piece in the manifest (§5) | Every functional unit | The Machines tab; the catalogue's 49 functional units (PROTEIN_CATALOGUE_PLAN) | 1–1.5 |
| **N9.** Declared extension, X1 (§6) | Any family of laws | ATP synthesis over FR-4's law; D167's moved laws | 1–2 |

**Owned elsewhere** (their owners' estimates, not re-counted here):
- **The core-seams pass [designed]:** seam A's general cycle kind, 4.5–6.5; seam B's lifecycle,
  3–5.5; seam E's moieties, 1–1.5 (CORE_SEAMS §13).
- **Species beyond 16:** F8, a D148 change per consumer (D165) [none].
- **Without estimates [none]:** polymerisation laws, F10, held under D145; a stochastic regime,
  F11 (SYN3A_MINIMAL_CELL_TRACK §4.3; deferred in PAPER_REVIEW_WHOLE_CELL §7, item 1).
- **B8's fields and the "represents" key (D175):** reserved in the law template and refused until a
  first consumer; MODULE_SYSTEM §4 outlines them as stage 3 [none].
- **Kinds that own pools:** MODULE_SYSTEM §7's rule (c), rated "moderate" [none].
- **A torque or momentum ledger,** for motors [none].

## 8. Options for the user, and the recommendation

| Option | What | Agent-days (S) | When |
| --- | --- | --- | --- |
| **M0** | The viewer's Machines tab as a catalogue with drawing levels, labelled illustration: meaning (d) | Viewer only | Now |
| **M1** | ATP synthase as the first machine, built as general pieces: N1, N3, N5 and N8; its law and data; independent references, a protocol and a judged run (D187); meaning (a). Less if D193's synthesis law lands first | 14–23, plus B8's fields (no estimate) | After the core-seams pass (A, B, E) |
| **M2** | The proteasome core second: a node machine (N2), then the first stoichiometric assembly (N4), with its references | 12–18 | After M1 |
| **M3** | Per-scope focus (b), then zoom by branching (e), then switching (c), on request | (b) not estimated; (e) 2–3; (c) 5–8 | After M1 |
| **M4** | Ribosome and RNA polymerase, with promoted individuals (I2) | Large; F8, F10 and F11 first | After the user's ruling on D145 |

**Recommended: M0 now, then M1,** with N7's vocabulary reserved by the lead (§9, L1).
- **Why ATP synthase:** its substrates are on the inventory once the pass lands; free-to-read
  numbers give it a sharp check, though §10.3 narrows what that check tests; all four targets need
  it.
- **Why general pieces:** the proteasome is the second consumer of N1 and N3, which keeps D144.
- **Why (a) with tagged individuals:** it answers "individually and in aggregate" with no change to
  any run.

**Risks:**
- **Seam A's contract is not on main.** FR-13 builds on it, so changes there reach FR-13.
- **The first judged check may fail on stoichiometry** (§4). That is science, but it can stall an
  acceptance.
- **The ribosome, which every target needs, waits** on F8, F10, F11 and D145.
- **Assembly kinetics are thin in free-to-read sources.** Maps give the order, not the rates.
- **Switching (c) can make results depend on viewing.** Only a declared focus prevents that.
- **A machine framework built before a second consumer** would break D144 and D187. M1 names its
  second consumer before any code.

## 9. Questions

**For the user:**
- **U1.** The meanings of "what is being looked at": (d) now, (a) first in the engine, (e) next and
  (c) only on request?
- **U2.** "Fine is the default" for machines: reading (B), with undeclared worlds unchanged, every
  representation opt-in and the finer one as reference (§3.4)?
- **U3.** ATP synthase first, with the zero-flux check (§4)?
- **U4.** The ribosome: lift D145's hold for polymerisation laws, or wait?
- **U5.** Individuals: tagged and one-way first (I1), and promoted and two-way (I2) after F11?
- **U6.** Extension: X1, once the first parent and child exist?

**For the lead:**
- **L1. Time-sensitive:** reserve N7's vocabulary (`assembled`, `disassembled`, `degraded`,
  `assembled_from`, `member_of`) in `cells.relations@1` before it lands on main, or leave it to a
  later version? Building waits for the user's discussion.
- **L2.** Reserve the node host and a cycle-diagram interface in seam A's template now, while
  `cells.cycle_law@1` is provisional (CORE_SEAMS §15)?
- **L3.** The manifest's `machine` piece: in @2, before the viewer binds, or in a later major?

## 10. Build plan for M1

*Added 17 November 2026, after the user chose M0 now and then M1 (U1, U3 and U5). U2 is recorded
as the standing opt-in default. U4 and U6 stay open. L1 and L3 wait for later versions of their
formats. Read-only: nothing here is built.*

### 10.1 One ATP synthesis law, one owner

- **M1's law is D193's law.** D193 sets one law set, with one cycle form, for mitochondria and
  bacteria, *E. coli* and JCVI-syn3A included. Its synthesis cycle is
  `proton_coupled_atp_synthesis_cycle@1` [designed] (MITOCHONDRIA_DESIGN §1.2, §4).
- **Its owner is the mitochondria lane,** in that note's M3, "the laws and their references",
  checked by a fresh agent's component references (MITOCHONDRIA_DESIGN §5.1, §8). The core-seams
  pass took that note's P1 and M1 (CORE_SEAMS §13).
- **FR-13 writes no synthesis law.** It consumes D193's law and adds the machine's pieces around
  it. The legacy energy and mitochondria code is D193's reference to learn from (D196); FR-13 reads
  none of it.
- **The law's kinetics need a ruling first.** Beard's printed F1F0 law (Eq. 11) fails the cycle
  screen: it omits the matrix proton that its own reaction consumes (CORE_SEAMS_STEP0 §1.4, §7).
  The consistent form is seam A's, with Beard's forward term as S. It is a departure, which the user
  rules on with the mitochondria lane (CORE_SEAMS §16).
- **A diagram law would be a second law for the same mechanism.** N1's diagram, with rotary
  substeps, has a steady-state flux of its own, which matches D193's only where fitted. Without
  B8's `represents` key, nothing refuses both as the aggregate on one population. So N1 waits for a
  minimal B8 (§10.5), and M1 starts with tags on D193's law (§10.4).
- **The order:** the core-seams pass (A, B, C, E); then D193's M3, the law and its references;
  then M1a; then a minimal B8; then M1b.
  - D193's M3 follows that note's M1 (now the pass) and, on its branch I, its M2.
  - P1's result (CORE_SEAMS_STEP0 §8) leaves branch X unbuilt. It names a seam C gap that caps
    explicit steps where a route draws protons from a buffered outside node.
  - Whether the mitochondria note's M2 must run first was not settled in what was read here.
    FR-13 can ask that lane to build the synthesis law first within its M3.
- **Engine models (AGENTS.md).**
  - M1a runs `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with the generalised
    `cells.transporter@1` hosting D193's law and `cells.rapid_proton_buffer@1` as seam C's closure;
  - `isopotential_partition@1` handles N3's division;
  - N3's assembly route is `local_species_reactions@1` or the kind itself, settled in N3's design;
  - M1b adds the diagram law.

### 10.2 Seam A: the per-edge check against CORE_SEAMS §16, and what M1 needs

**The claim, made precise (S).** A diagram law declares one free energy G_s per state s. For each
edge e from s to s′, it declares the free ligands the edge binds or releases, ν_{l,e}; on a patch
these are ν_{l,x,e}, at end x (N or P). Per-edge detailed balance is k⁺_e/k⁻_e = e^{−ΔG_e/RT}, with
ΔG_e = G_{s′} − G_s + Σ ν μ̃, each μ̃ the registry's potential at its end and stage.

**It implies §16.** Take any cycle C of the diagram, dependent cycles included:
ln(Π⁺/Π⁻) = Σ_e ln(k⁺_e/k⁻_e) = −[Σ_e (G_{s′} − G_s) + Σ_l ν_{l,C} μ̃_l]/RT.
- The first sum telescopes to zero around a closed path.
- ν_{l,C} = Σ_e ν_{l,e} is the cycle's net stoichiometry, so the second term is the mode's ΔG as
  the kind computes it.
- Hence ln(Π⁺/Π⁻) + ΔG_C/RT = 0, which is §16's condition.

**By host:**
- **On a node host,** every species and state sits at one potential φ. If each edge conserves
  charge (z_{s′} − z_s + Σ_l ν_{l,e} z_l = 0, checked at parse), the electrical terms cancel edge by
  edge, and the voltage drops out.
- **On a patch,** each ligand's μ̃ is taken at the end it binds from, and each G_s carries its
  state's displaced charge times F V. These terms telescope as well, so the proof holds with
  voltage-dependent edges.

**The converse holds only in part.** If every cycle meets §16 at every stage, free energies built
along a spanning tree are path-independent at that stage. Nothing makes them constant across
activities and voltages.
- So with one declared constant G_s per state, the per-edge check is stricter than §16. It also
  refuses a law in which an edge's ratio depends on a ligand that the edge does not bind, even when
  that dependence cancels around every cycle.
- Requirement 7 therefore adds a refusal beyond §16: the physical rule for elementary steps.
- In return, the per-edge check gives the state free energies that the occupancy and individual
  levels need for their heat.

**The claim fails without single-valued state free energies.** If a law declares only per-edge
constants K_e, a per-edge test is vacuous. Take a three-state hydrolysis cycle E → E·ATP →
E·ADP·Pi → E with every K_e = 1, activity factors aside. Their product is 1, but §16 needs
e^{−ΔG°/RT}, far from 1 for ATP hydrolysis. §16 refuses it; an edge test without G_s would not.

**What seam A must provide for M1** (requirements on its design):
1. A population on a patch, with a declared N end and integer roles per cycle beyond today's 1 to 4
   (`transporter.py`:164). That means c H⁺ per 3 ATP (c from 8 to 15) for a structural ratio, or n
   H⁺ per ATP for a measured one.
2. Fuel rows moved, not held, at the N end, which may be the patch's outside node. In Steigmiller's
   proteoliposomes ATP is measured in the medium, so N is outside (**S**). Today fuel is held and
   fixed to the inside cell (`transporter.py`:193, :243).
3. Several populations per patch: the synthase beside a K⁺ route and a proton leak.
4. Each mode's one-way cycles kept as cumulative state, beside the net cycles that §3.1 keeps
   (`docs/CORE_SEAMS_DESIGN.md`:180). They must be booked by a non-negative quadrature, such as
   seam D's trapezoid, or the step refused.
   - The step's applied rate uses the tableau's weights (`models/surface_pump_v3.py`:1157–1160).
     With ARS(2,2,2) one weight is negative (CORE_SEAMS §6.1), so a one-way flux that falls sharply
     within a step would give a negative increment.
   - `book` sees those increments (`registry/kind_registry.py`:253–255). They are each tag's hazard.
5. The capacity read from an extensive state that N3 writes and seam B splits at division, not
   only a layout value.
6. A test that plants a law with a shifted zero, which must be caught. The judged check (§10.3)
   rests on J = 0 exactly at ΔG = 0, whatever S is.
7. For M1b: S per Hill cycle supplied by a law from its diagram, with all its Hill cycles
   enumerated (CORE_SEAMS §16) and the per-edge check at parse.

A node host is M2's requirement, not M1's.

### 10.3 Sources read, and what the judged check can test

**Read on PMC through a page-reading tool,** a model's extraction of the full text, not read by eye.
Peth et al.'s Table 1 was checked by a second, table-only query, which agrees. Each number gets a
direct read before any registration. Numbers only (D186, D201):
- **Watt et al. 2010** (PNAS 107:16823): the bovine c-ring has 8 subunits, from X-ray
  crystallography at 3.5 Å, so 8/3 ≈ 2.7 H⁺ per ATP. Other vertebrates are inferred to share it
  from identical c-subunit sequences. Fungal, bacterial and chloroplast rings have 10 to 15.
- **Peth, Nathan and Goldberg 2013** (*J. Biol. Chem.* 288:29215, Table 1), mouse 26S
  proteasomes: 50–80 ATP per ubiquitinated DHFR in 13 s; 90–140 ATP in 23 s when folate stabilises
  it; 100–160 ATP per ubiquitinated Sic1 in 26 s. The times are 1/Vmax. Substrates raise ATP
  hydrolysis two- to threefold. **§4 is revised to match:** a search summary had given 50–80 for
  the stabilised substrate. The abstract states the unstabilised values, then says both doubled.
- **Steigmiller, Turina and Gräber 2008** (PNAS 105:3745): purified enzymes in phosphatidylcholine
  and phosphatidic-acid liposomes.
  - The conditions: ΔpH by an acid–base jump to pH 8.47 outside; Δφ = 0, with 50 mM K⁺ on both
    sides and valinomycin; 1.25 mM Pi; about 4.5 mM MgCl₂; 23 °C.
  - The zero-rate ΔpH at fixed Q = [ATP]/([ADP][Pi]) gives H⁺/ATP of 4.0 ± 0.2 for the chloroplast
    enzyme, with ΔG°p′ = 38 ± 3 kJ/mol, and 4.0 ± 0.3 for *E. coli*'s, using the chloroplast ΔG°p′.
    The authors report both ratios disagree with the rings' 14/3 and 10/3, for reasons unknown.

**Syn3A's direction.** Neither Syn3A note states it.
- The viewer's species file (the 2019 reconstruction) and MITOCHONDRIA_DESIGN §4 have the enzyme
  hydrolysing ATP to pump protons out. That is a model's reading, not a measurement.
- In Cells the direction follows from ΔG_cyc. Syn3A has no measured ratio, ATP potential or
  proton-motive force; only relatives' values exist (SYN3A_MINIMAL_CELL_TRACK §4.2).
- So Syn3A is not where M1 is judged.

**What a stoichiometry mismatch would mean.** The zero-rate line plots 2.3RT·lg Q against
2.3RT·ΔpH at the zero. Its slope is the enzyme's coupling ratio. Its intercept, −ΔG°p′, is the
chemistry of ATP synthesis at the conditions, the same for any enzyme. The engine's zero is exact
and needs no kinetic parameter, so a mismatch is never a numerical error.
- **A ratio declared from structure** (c/3) makes the slope a test of integer coupling. The
  measurements already disagree: 4.0 ± 0.3 against 3.3 for *E. coli*, 4.0 ± 0.2 against 4.7 for
  chloroplasts, 2.9 ± 0.2 against 3.3 for yeast (Petersen et al. 2012).
- **A ratio declared from these data** makes the slope circular.

**A proposed change for the user (U7, §10.6).** U3 was approved with the zero-flux check, and that
form stands until the user rules. The proposal, before any registration:
1. The ratio is an input, with its source named.
2. The intercept, at the paper's conditions, is judged. It tests the registry's ATP, ADP and Pi
   potentials and seam C's Mg²⁺ and H⁺ closure: chemistry shared with D193, not the machine. Its
   potentials and binding constants need a cited source, not yet chosen.
3. The structural ratio is a reported finding with both outcomes stated in advance, not an
   acceptance.
4. N3's and N5's claims are carried by their own registered judged run (D187, rule 6): a numerical
   qualification against independent references, with planted errors. The first machine-specific
   biological check is then M2's ATP per substrate, from a target organism (mouse).

**Who runs the zero-rate line (L5, §10.6).** It tests D193's law and seam C's closure, beside the
component references that already check each cycle's zero and static head (MITOCHONDRIA_DESIGN
§5.1). So it is proposed for the mitochondria lane. Until the lead rules, §10.5 books it to M1a.
Its world runs the cycle in both directions, so it meets P1's buffered-node cap (CORE_SEAMS_STEP0
§8) until seam C's fix lands.

This weakens the "sharp check" reason for ATP synthase first (§8). Its other reasons stand:
substrates on the inventory, and need in all four targets.

### 10.4 Integer state for tagged individuals

**Kinds do not accept integer state fields today** (found by reading; no run was made).
- Kinds use integer arrays only as layout (`transporter.py`:404–405); their state is float
  (:436–441). No test in `tests/unit/test_kind_rules.py` exercises an integer state field.
- The kind record declares no types (`registry/kind_registry.py`:281–317).
- @3 gives every kind field a derivative, zero where the kind gives none
  (`models/surface_pump_v3.py`:500–512).
- Every stage adds (w·dt)·d to every field (`models/surface_pump.py`:235–240), which makes an int64
  field float64 inside the stages. `book` writes at the step's end (`models/surface_pump_v3.py`:
  1197–1199), so the field's type at the end depends on what `book` returns.

**Operators do.** `STATE_DTYPES` names non-float fields (`operators/contract.py`:11–12,
:214). Replacement@2 uses it (`operators/cell_replacement_v2.py`:349). The composite
collects it (`models/pump_composite.py`:759) and refuses it only under coupled RK4 (:1146–1158).

**Options for N5:**
- **(i), recommended:** a kind declares integer fields, which the core keeps out of the stage
  combination and lets only `book` write. A small core change, with a planted test. Whether
  observations and checkpoints keep the type was not checked.
- **(ii):** tags as an operator, which may hold integer state today, if an operator can read the
  cycle kind's one-way cycles (not checked). A separate kind cannot: no kind reads another kind's
  fields (`registry/kind_registry.py`:182).
- **(iii):** whole-number float64 fields, exact below 2⁵³. A stopgap that hides the type.

**M1a's tags are whole-cycle tags,** inside the cycle kind (S).
- **Events:** each tag completes forward and backward cycles as Poisson events. Their means over a
  step are its share (1/N) of the step's one-way cycle increments, booked non-negative
  (requirement 4).
- **The mean** equals the aggregate's one-way cycles as that same booking integrates them. It is not
  the tableau's net cycles; the two differ by the quadrature's error.
- **Draws** are counter-based, keyed by the tag and its draw index, one per step. A key on the cycle
  count would reuse a draw after a step with no event. No random-number state is checkpointed, so
  `io.py`:158–159 stands.
- **Unchecked:** whether `book` draws identically on host and device.
- **Counting:** Poisson counting is the lumped law's own assumption, which N1 refines in M1b.

### 10.5 Cost and order

Agent-days are rough (**S**). "After" names what must be on main first.

| Piece | What | Days | After |
| --- | --- | --- | --- |
| The law | D193's synthesis law and its component references, by the mitochondria lane | 0 for FR-13 (its M3: laws 2–4, references 3–4) | The pass |
| Data | Two worlds: the proteoliposome (its parameter set, and cited potentials and binding constants at its conditions); and a cell whose synthase copies are made from subunit modules, with one division and tags | 1–1.5 | The pass |
| N3 | Copies from subunit rows (lumped modules while the cap holds); capacity from the count | 2–4 | Seams B and E |
| Integer state | Option (i) | 0.5–1 | The pass |
| N5 | Whole-cycle tags: keyed draws, the non-negative booking, a consistency check with a planted error | 2–3 | Integer state; the law |
| References | Independent, by a fresh agent: N3, N5 and the zero-rate prediction | 1.5–2 | — |
| Protocols | Two, registered and rehearsed, criteria first: the zero-rate line (as approved, pending U7 and L5), and N3's and N5's numerical qualification (D187, rule 6) | 1.5–2 | Data; references |
| Judged runs | The two protocols' runs, with their analyses | 1–1.5 | All of M1a; seam C's fix, for the zero-rate world |
| **M1a** | | **9.5–15** | |
| B8, minimal | `represents` with its admission, `supports`, the envelope of `qualified`; their manifest keys | 2–3 | The pass; L4 |
| N1 | The diagram law with rotary substeps; the per-edge check; its reduction to D193's law within a declared envelope | 4–6 | B8 |
| References | For N1's reduction | 0.5–1 | — |
| **M1b** | | **6.5–10** | |
| N8 | The `machine` piece, in the manifest's next major (L3) | 1–1.5 | That major |

**Total: 17–26.5 agent-days,** of which 9.5–15 come before B8.
- This replaces §8's 14–23 plus B8: the law is D193's, and B8's minimal part is now estimated.
- If L5 gives the zero-rate run to the mitochondria lane, M1a falls by about 1–1.5.

**When seam A lands, desk work starts:** the data search, both protocols' drafts with their
criteria, and N3's design against seams B and E. **Code starts after the pass lands:** integer
state, N3, N5 and B8's minimal part. The pass's files have one owner each (D195). The judged runs
wait for D193's law.

**The second consumer, named before any code:** the proteasome core (M2).
- It is the second consumer of N3 and N5: a 20S core is made of α and β subunits.
- Peth et al.'s 13–26 s per substrate is a per-machine time for whole-cycle tags, from mouse.
- It is also N2's first consumer, and N1's second once B8 exists.

### 10.6 Questions this plan adds

- **U7, for the user.** Change U3's zero-flux check as §10.3 proposes? That means the ratio as an
  input, the intercept judged, the structural ratio as a finding, and N3 and N5 carried by their
  own numerical protocol. Until the user rules, the approved form stands.
- **L4, for the lead.** ARCHITECTURE names D174's fuel case as the first consumer of B8's fields.
  Should M1b's minimal B8 come first instead?
- **L5, for the lead.** Does the zero-rate line belong to the mitochondria lane (proposed) or to
  FR-13's M1a?

## Sources

- **Engine documents read:** AGENTS.md; DECISIONS.md (D135, D136, D140, D142–D145, D147, D148,
  D152, D153, D173, D175, D176, D185, D186, D191–D204); FEATURE_REQUESTS.md (FR-6, FR-7, FR-13);
  ARCHITECTURE.md ("Levels of detail"); MULTISCALE_EXECUTION_ARCHITECTURE.md ("Fidelity and
  resolution", "Coupled numerical execution", "Precision, randomness"); CORE_SEAMS_DESIGN.md
  (§0–§17); MODULE_SYSTEM_DESIGN.md; RELATIONSHIPS_DESIGN.md (§0, §1, §4–§8);
  LAW_DOCUMENTATION_DESIGN.md (§7, §8); CAPSID_ASSEMBLY.md; GARD_DESIGN.md (§1, §2.4, §4.6, §7);
  PROTEIN_CATALOGUE_PLAN.md; PROTEIN_ASSEMBLY_IDEAS.md (§6, §7); SYN3A_MINIMAL_CELL_TRACK.md (§4.3,
  §4.4, §9–§11); SOTA_SYN3A.md; PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md (§2, §4, §5);
  MITOCHONDRIA_DESIGN.md (§1.1, §1.2, §1.4, §3.2, §4–§8); CORE_SEAMS_STEP0.md (§1.4, §7);
  `visualizer/docs/CELL_STRUCTURES.md`.
- **Code read at e5edba97:** the files cited above, under `src/cells/` (`registry/`, `core/`,
  `models/`, `assembly/`, `laws/reactions/plasma_calcium.py`, `io.py`), and
  `tests/unit/test_continuity_bypass.py`.
- **Branches read:** `relations-writer` at 35a5bbb9 (`src/cells/records/relations.py`, and the
  lead's rulings in its RELATIONSHIPS_DESIGN.md); the `visualizer` branch's species list.
- **Viewer data read on main:** `visualizer/data/machines/ecoli.flagellar-motor.json`;
  `visualizer/data/species/{syn3a,mpneumoniae,ecoli,human,planarian}.json`.
- **External sources, 17 November 2026,** by nine web lookups: four searches and five queries of
  PMC pages through a page-reading tool. Two direct downloads were refused: PMC served a reCAPTCHA
  page, and Europe PMC's full-text service returned an error. Numbers only, each cited (D186, D201);
  no text, figure or data file copied.
  - **Read through the tool, full text** (§10.3; a direct read is owed before registration): Watt
    et al. 2010, PNAS 107:16823 (PMC2947889); Peth, Nathan and Goldberg 2013, *J. Biol. Chem.*
    288:29215 (PMC3790020; Table 1 queried twice); Steigmiller, Turina and Gräber 2008, PNAS
    105:3745 (PMC2268821);
  - **read on its PMC page, its ratios and ring sizes:** Petersen, Förster, Turina and Gräber 2012,
    PNAS 109:11150 (PMC3396544);
  - **search summary only:** Xue et al. 2022, *Nature* 610:205 (PMC9534751).
- **Cited from memory, not read for this note:** Hill's diagram method and King and Altman's, for
  steady-state cycle fluxes; linearity of expectation for independent Markov chains, and van
  Kampen's system-size expansion, for the mean-field error; Gillespie's direct method, and
  next-reaction methods with integrated hazards, for I2; the Berg group's torque–speed measurements
  on the flagellar motor.
