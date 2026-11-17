# Molecular machines: individually and in aggregate, at the detail set by what is looked at (design)

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
anticipate (§7):
- the states of a machine's cycle;
- assembly from subunits;
- individual machines with their own identity, coupled both ways to the cell;
- a level of detail that follows what is looked at.

| Layer | What the core hosts | What is missing |
| --- | --- | --- |
| **Aggregate:** copy numbers, rates, ledgers | [main] Channel populations with an abundance and mean gate fractions (`core/surface_kinetic_spec.py`:84–92); @3's two pumps; the transporter kind, one population per patch, n of 1–4 (`models/inner_kinds/transporter.py`:41, :164); abundance as state, with its own ledger (`models/operators/membrane_state.py`:1–30); D152's reactions, with a Michaelis–Menten law that reads a catalyst row (`models/operators/species_reactions.py`:21–24). [designed] Seam A: any integer stoichiometry, many populations per host, finite fuel. Seam B: capacity as extensive state | Copies made from, and returned to, subunit rows: units appear today from an operator's booked supply. A host for soluble machines, which have one end, not two |
| **Cycle:** the states of the working cycle | [designed] Seam A's §16: Hill cycles, Wegscheider's condition at parse, Σ J·ΔG ≤ 0, one-way fluxes. These are lumped steady-state fluxes, and a law holds no cycle state | A law that declares the cycle's states and edges. The individual chain, the occupancies and the lumped flux all follow from it |
| **Assembly:** subunits, stoichiometry, order | [main] `capsid_graph@1`: one prescribed 20-site cage of one subunit type in a held bath (`assembly/graph.py`:7–9; `assembly/spec.py`:18–23). `finite_bond_assembly@1`: the same graph with a finite pool. The lineages family: a bag of label-only types (`models/assembly_lineages/family.py`:1–17). D152's passive mass action, which holds a small pathway with subunits as moieties (`species_reactions.py`:26–28, :37) | A general assembly map: typed subunits, declared intermediates and steps, in three representations |

**Recommended (§8):** the viewer's catalogue now, labelled as illustration; ATP synthase as the
first machine, built as general pieces after the core-seams pass, with the level of detail fixed
per run; the ribosome after a user ruling on D145's hold.

## 1. One machine, three layers

### 1.1 Aggregate

- **What exists [main].** The engine's membrane laws act on functional units, not on gene products
  (PROTEIN_CATALOGUE_PLAN, stage 2).
  - A channel population has a patch, a law, an abundance and mean gate fractions
    (`core/surface_kinetic_spec.py`:84–92).
  - Kinds book what they move into the ledgers by role: material per node, a `produced` record for
    chemistry, heat, work and stored energy (`core/kind_registry.py`:264, the `ledger_terms` hook).
- **Copy number as state [main].** `membrane_entity_state@1` holds each population's abundance in
  units, under an entity ledger (`membrane_state.py`:1–30).
  - Each population also carries a functional-unit ID and a catalogue reference (:62–67).
  - Its writers book where the units come from, as a supply.
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
- **It hosts machines that are not transporters,** where the machine's job is a stoichiometric
  cycle: ATP synthase, a proteasome's ATP per substrate, a translocon's ATP and protons per residue.
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
  - It implies Wegscheider's condition for every cycle (§16). It is also the stochastic kernel check
    of GARD_DESIGN §2.4.
- **Run-time guards follow the level:**
  - lumped: Σ J·ΔG ≤ 0 per population (§16);
  - occupancy: heat booked from the edges' affinities, closing against the free-energy state
    function;
  - individual: event heat, declared non-monotone, closing the same way (GARD_DESIGN §2.4).

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
- **Combinatorics.** n distinct subunits allow up to 2ⁿ intermediates. The declared map, not the
  code, keeps them few.
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
  §4.6). The only machinery for discrete entities is in the event-driven families, with one
  assembly per lane.
- **Two ways to coexist (S):**

| | I1: tagged individuals (one-way) | I2: promoted individuals (two-way) |
| --- | --- | --- |
| What | k of the N machines are followed one by one. Each moves on the rates of the occupancy aggregate, at the environment the step computed. The aggregate still holds all N | m machines leave the aggregate (N → N − m) and run as individuals. Their events move material on the shared inventory |
| Exact? | In distribution, for independent identical machines (§3.1): each tag follows the law of any one machine | In principle, if the hybrid clock is right |
| Effect on the run | None: every other array is bitwise the same with tags on or off, as D200 asks of labels | Individuals feed back on the cell |
| Needs | A keyed stream per tag (a `tag` domain); each tag's hazard integrated over the step by a declared quadrature | F11's stochastic regime: events inside a fixed step, hazards integrated and rescheduled when rates change (MULTISCALE_EXECUTION_ARCHITECTURE, "Coupled numerical execution"); random state in checkpoints |
| Gives | Dwell times, step statistics, one machine to show | Effects of fluctuations at low copy numbers |

- **The precedent is one-way.** The assembly-cell families coupled one stochastic assembly to an
  ionic cell in one direction only (CAPSID_ASSEMBLY.md, "One-way assembly regulation"). They now sit
  in `legacy/`, a holding area to be removed (D196).
- **Identity and streams [main].** In the lineages family, "an assembly's draws depend on its
  identity alone" (`models/assembly_lineages/streams.py`:22–23), folded from the seed, the world,
  the carrier key, a domain and a counter. An individual machine would take the same fold.
- **Relations [branch].** `cells.relations@1` is built on `relations-writer` (35a5bbb9), not merged.
  Its vocabulary is closed (`records/relations.py`:98–107 on that branch). Machines need four
  additions (S):
  - a birth by assembly, `assembled`, and the ends `disassembled` and `degraded`;
  - many parents: `lives.parent` is one entity, but a complex is made of many subunits. An
    `assembled_from` edge, weighted by stoichiometry, would run from pools or from subunit lives;
  - `member_of`, from a tagged or promoted individual to its population node. The `population` node
    kind already exists;
  - a key case: under RELATIONSHIPS_DESIGN §1.3 a parentless newcomer opens a new sub-lineage, so
    10⁴ assembled ribosomes would open 10⁴. Keys from a counter per machine population avoid that.
- **At a cell division** an individual keeps its life and changes its `occupies` edge (S).
- **Timing.** The lead's rulings on that branch lift the format's provisional label. So these
  additions are a new version, unless they enter before a bundle is shared (§9, L1).

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
| **(e) Zoom by branching (S):** looking closer starts a new run from a stored checkpoint, with a declared focus | One prolongation at the branch, booked as in (c); then as (b) | As (b) | The parent run is unchanged. The new run's inputs are its focus and its branch time (D153's new run from imported state; the relations' `branched_into`) | Declared by the new run | (b), one prolongation, `cells branch` |

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
  (`core/projective_spec.py`:1–3).
- **It does not carry over directly.** No machine model exists, and today's membrane machines are
  deterministic aggregates. Individuals by default would be unworkable at a cell's copy numbers and
  would change every existing world.
- **Two readings, for the user (§9, U2):**
  - **(A)** each machine declares a reference representation, which a world gets unless it opts
    for another;
  - **(B), recommended:** a world that declares nothing is unchanged, and every representation is
    declared and opt-in. The finer representation is always the reference when a coarser one is
    qualified, with the envelope declared first and one case outside it failing (D175).

## 4. First machines, chosen by constraint

- **Targets** are JCVI-syn3A, mouse, planarian and human. Presence in bacteria is read from the
  viewer's species files (`visualizer/data/species/*.json`, `cap.machines`). They record no machines
  for the eukaryotes, so that column is general biology (**S**).
- **The data column** was checked for access by web search on 17 November 2026, at the level of
  abstracts and PMC records, not full texts.

| Machine | Substrates in the modular engine | Free-to-read data for a judged check | Targets that need it | Verdict |
| --- | --- | --- | --- | --- |
| **ATP synthase** | **Yes:** ATP, ADP and Pi rows (D176's F2; `core/species_registry.py`:5–6), H⁺ with buffering (FR-4), patch voltage [main]. Moving them through a synthesis cycle needs seam A [designed]: `proton_coupled_atp_synthesis_cycle@1` (MITOCHONDRIA_DESIGN §1.2, §4). FR-4's proton law already reverses past its static head, on held fuel | Thermodynamic H⁺/ATP of about 4.0 for the *E. coli* and chloroplast enzymes (Steigmiller et al. 2008, PNAS, PMC2268821). Yeast mitochondria 2.9 ± 0.2, against 3.3 from its 10-subunit ring (Petersen et al. 2012, PNAS, PMC3396544). The bovine ring has 8 c subunits (Watt et al. 2010, PNAS, PMC2947889) | 4 of 4: Syn3A, where its reconstruction runs it in the hydrolysis direction (viewer `syn3a.json`); mitochondria in the three animals | **First** |
| **Ribosome** | **No:** no amino-acid, tRNA, GTP or mRNA rows, no polymers (F10), 16 species | In-cell structures: 101,696 ribosomes from 356 tomograms of *M. pneumoniae*, sorted into 13 classes of translating ribosomes (Xue et al. 2022, *Nature*, PMC9534751, open access). About 500 per Syn3A cell, from cryo-electron tomograms (viewer `syn3a.json`; PAPER_REVIEW_WHOLE_CELL §2.6) | 4 of 4 | The flagship. Blocked by F8, F10 and F11; crosses D145's hold |
| **RNA polymerase** | **No:** NTPs, the DNA template and transcripts are absent | Not searched | 4 of 4 | With the ribosome |
| **Proteasome** | **Partly:** ATP yes; protein substrates and peptides as rows, no | Degradation tracks ATP hydrolysis: tens of ATP per substrate, 50–80 for a stabilised one (Peth, Nathan and Goldberg 2013, *JBC*, PMC3790020; abstract level). Assembly kinetics not searched | 3 of 4: not Syn3A, whose annotation lists the proteases FtsH and Lon (viewer `syn3a.json`) | **Second:** D140's named case, a node machine and an assembly case |
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
  - Against the thermodynamic measurements it may fail. Petersen et al. report their ratios outside
    the rotational models' values.
  - A failure would be informative, and is a reason to choose the first acceptance with care.

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

- **A `machine` piece is a new key set,** so it is a new major of the manifest
  (LAW_DOCUMENTATION_DESIGN §7). Its @2 is designed and not built.
- **The viewer's Machines tab** binds to that piece once one exists, as D204 says.

## 6. Extension: one general machine law, specialised per machine?

**The lead's findings, checked:**
- **Correct:** laws are frozen declarations on one `Law` base (`registry/laws.py`:128; `ChannelLaw`
  :202; `CycleLaw` :269). A subclass passes registration's `isinstance` check (:399) and is found by
  its inherited interface (:453).
- **Correct:** operators are checked by `check_declarations` at registration
  (`registry/operators.py`:42–45). A `cells` ID names one object, for operators (:53–61) and for
  laws (`register`). So an extension takes a new ID (D147, D148).
- **Partly correct:** "models extend by composition under D191's one rule". Composition over model
  families is D142's and D143's rule: new combinations are definitions. D191 rules how a composition
  reads a field. And inheritance is used today:
  - `scheduled_cell_replacement@2` subclasses @1's operator class, extends its writes and calls @1's
    parser (`models/operators/cell_replacement_v2.py`:346–380);
  - `membrane_insertion_v2.py`:202 subclasses @1's step checks;
  - specifications inherit version over version (`core/surface_kinetic_spec.py`:50;
    `core/surface_pump_v3_spec.py`:101);
  - kinds are frozen records of hooks, varied by `dataclasses.replace`, as `bound` does
    (`core/kind_registry.py`:383–392).
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
  state what the child promises (D147), and an overridden kernel can hide a change of meaning.

## 7. Gaps

**New to FR-13** (agent-days are rough, **S**):

| Gap | Why it is general | Consumers | Days |
| --- | --- | --- | --- |
| **N1.** A cycle-diagram law: states, three derived levels and per-level guards (§1.2) | Any enzyme, carrier or channel with explicit states | ATP synthase's steps; channel gating as jump processes (GARD_DESIGN §7.2) | 4–6 |
| **N2.** A node host for seam A (§1.1) | Any soluble machine or enzyme with a cycle | Proteasome; soluble ATP-coupled enzymes for Syn3A's stage 4 (F9) | 0.5–1 |
| **N3.** Copies made from, and returned to, subunit rows; capacity from the count | The closed molecular-to-physiology loop | FR-7; the junction-channel unit (D145); protein turnover (SYN3A_MINIMAL_CELL_TRACK §9.3) | 2–4 |
| **N4.** An assembly map in three representations (§1.3) | Any complex | Proteasome (D140); ribosome subunits; ATP synthase modules; typed capsids | 8–12 |
| **N5.** Tagged individuals, I1 (§2) | Single-entity statistics with no change to a run | Rotary steps; dwell times of any cycle | 2–3 |
| **N6.** Zoom by branching (e), then switching (c) (§3) | Any pair of a reduced and a detailed representation | FR-13; ARCHITECTURE's first level-of-detail consumer (D174's fuel case) | (e) 2–3; (c) 5–8 |
| **N7.** Relations vocabulary and a key case for machines (§2) | Any entity made from many parts | FR-13; material provenance of complexes (D200) | 0.5–1, before sharing |
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
| **M1** | ATP synthase as the first machine, built as general pieces: N1, N2, N3, N5 and N8, its law and data, and meaning (a). Less if D193's synthesis law lands first | 13–20 | After the core-seams pass (A, B, E) |
| **M2** | The proteasome core second: a node machine, then the first stoichiometric assembly (N4) | 10–15 | After M1 |
| **M3** | Zoom by branching (e), then switching (c), on request | 2–3; then 5–8 | After M1 |
| **M4** | Ribosome and RNA polymerase, with promoted individuals (I2) | Large; F8, F10 and F11 first | After the user's ruling on D145 |

**Recommended: M0 now, then M1, and N7 now,** before `cells.relations@1` bundles are shared.
- **Why ATP synthase:** its substrates are on the inventory once the pass lands; free-to-read
  numbers give it a sharp check; all four targets need it.
- **Why general pieces:** the proteasome is the second consumer of N1–N3, which keeps D144: no
  machine-specific code.
- **Why (a) with tagged individuals first:** it answers "individually and in aggregate" cheaply,
  with no change to any run.

**Risks:**
- **Seam A's contract is not on main.** FR-13 builds on it, so changes there reach FR-13.
- **The first judged check may fail on stoichiometry** (§4). That is science, but it can stall an
  acceptance.
- **The most-wanted machine, the ribosome, waits** on F8, F10, F11 and D145.
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
- **L1. Time-sensitive:** add N7's vocabulary and key case to `cells.relations@1` before its first
  bundle is shared?
- **L2.** Reserve the node host and a cycle-diagram interface in seam A's template now, while
  `cells.cycle_law@1` is provisional (CORE_SEAMS §15)?
- **L3.** The manifest's `machine` piece: in @2, before the viewer binds, or in a later major?

## Sources

- **Engine documents read:** AGENTS.md; DECISIONS.md (D135, D136, D140, D142–D145, D148, D152,
  D173, D175, D176, D185, D186, D191–D204); FEATURE_REQUESTS.md (FR-6, FR-7, FR-13); ARCHITECTURE.md
  ("Levels of detail"); MULTISCALE_EXECUTION_ARCHITECTURE.md ("Fidelity and resolution", "Coupled
  numerical execution", "Precision, randomness"); CORE_SEAMS_DESIGN.md (§0–§17);
  MODULE_SYSTEM_DESIGN.md; RELATIONSHIPS_DESIGN.md (§0, §1, §5–§8); LAW_DOCUMENTATION_DESIGN.md (§7,
  §8); CAPSID_ASSEMBLY.md; GARD_DESIGN.md (§1, §2.4, §4.6, §7); PROTEIN_CATALOGUE_PLAN.md;
  PROTEIN_ASSEMBLY_IDEAS.md (§6, §7); SYN3A_MINIMAL_CELL_TRACK.md (§4.3, §4.4, §9–§11);
  SOTA_SYN3A.md; PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL.md (§2, §4, §5); MITOCHONDRIA_DESIGN.md (§1.2,
  §1.4, §3.2, §4); `visualizer/docs/CELL_STRUCTURES.md`.
- **Code read at e5edba97:** the files cited above, under `src/cells/` (`registry/`, `core/`,
  `models/inner_kinds/`, `models/operators/`, `models/assembly_lineages/`, `assembly/`, `io.py`).
- **Branches read:** `relations-writer` at 35a5bbb9 (`src/cells/records/relations.py`, and the
  lead's rulings in its RELATIONSHIPS_DESIGN.md); the `visualizer` branch's species list.
- **Viewer data read on main:** `visualizer/data/machines/ecoli.flagellar-motor.json`;
  `visualizer/data/species/{syn3a,mpneumoniae,ecoli,human,planarian}.json`.
- **External sources, checked for access by web search on 17 November 2026** (abstracts, PMC records
  and search summaries, not full texts; numbers only, each cited, D186 and D201; no text, figure or
  data file copied): Steigmiller, Turina and Gräber 2008, PNAS 105:3745 (PMC2268821); Petersen,
  Förster, Turina and Gräber 2012, PNAS 109:11150 (PMC3396544, its PMC page's ratios and ring
  sizes); Watt et al. 2010, PNAS 107:16823 (PMC2947889); Xue et al. 2022, *Nature* 610:205
  (PMC9534751); Peth, Nathan and Goldberg 2013, *J. Biol. Chem.* 288:29215 (PMC3790020).
- **Cited from memory, not read for this note:**
  - Hill's diagram method and King and Altman's, for steady-state cycle fluxes;
  - linearity of expectation for independent Markov chains, and van Kampen's system-size expansion,
    for the mean-field error;
  - Gillespie's direct method, and next-reaction methods with integrated hazards, for I2;
  - the Berg group's torque–speed measurements on the flagellar motor.
