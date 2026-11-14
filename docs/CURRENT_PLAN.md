# Current plan (adopted 12 November 2026)

Status: **adopted 12 November 2026 ([D145](DECISIONS.md#d145-the-current-plan-is-adopted-with-the-l4-now-and-gh200-next-week)).**
GH200 access is expected by the end of next week, and the L4 is used fully meanwhile. The
open choices were taken as the lead and the advisor suggested (D145). Of the two tooling items,
checkpoint continuity was approved and landed (D153). The public validation package still
needs the user's explicit approval. The status and working order at 14 November are in the
next section (D156).

**What this file holds.** It is an ordering document: what comes next, in what order, and
the evidence that closes each gate.
- Current status and run results stay in [PROGRESS.md](../PROGRESS.md).
- Mechanisms and the longer milestones stay in [ROADMAP.md](ROADMAP.md).
- Gates are named, not numbered, because "stage" already has three meanings: division
  S0b–S5, the catalogue stages and the E07 tiers.

**Sources.**
- the [architecture review notes](ARCHITECTURE_REVIEW_NOTES.md) and their corrections;
- a second review of public `main` at `541ac11`, supplied by the user;
- the advisor's review of both.

**What it supersedes.**
- The ordering of the 8 November plan in PROGRESS ("BETSE parity on CPU and L4, then
  JUPITER"). Its status table stays as the record.
- The order of the ROADMAP's current priorities 7–9: division, the protein catalogue and
  Golgi/trafficking. Their content stays.

## Status on 14 November 2026, and the working order (D156)

Levels: *implemented* (on main), *guarded* (tests, crossrev and frozen-model guards),
*numerically qualified* (a registered protocol passed), *judged* (used in a registered
experiment).

| Item | Level today |
| --- | --- |
| The composite: @3 plus operators, the ownership and energy-role contract, bound step checks | Guarded. Numerically qualified on CPU through frozen-model guards; GPU agreement by tolerance in progress on the L4 (14 November). Judged in E07-v1 (`resolved_pump_replacement@1`) |
| Water plus replacement@2 with the entity volume ledger | Implemented and guarded; not qualified on the heredity sheet |
| Lifecycle operators: S2 membrane state, S3 insertion and lumen, Rm1 injection, S5a partition and bridge closure | Numerically qualified, against independent references for S5a. Division is prescribed; nothing yet judges endogenous proliferation |
| Secreted-species transport (D150 v1) | Implemented and guarded; its protocol is being registered and judged |
| Reactions on the shared inventory (D152 v1) | Implemented and guarded (milestones 1–2); MG0c, the qualification, is in progress |
| Checkpoint continuity (D153) | Implemented and guarded for CPU vector windows. The GPU probe passed (14 November) and the GPU extension is being built |
| Phase markers | Completion records implemented; start and failure records pending |
| Run-view output (D154) | Requirement recorded; design pending |
| Coupling out of the inventory (D155, scoped by D156) and excitable tissue (D155) | Design and the conduction probe in progress |
| Field-solver interface | Designed; code waits for the GH200 numbers |
| One production execution path, compile policy, registry, D147 policy for composite definitions | Not started. The D147 policy and the two execution interfaces take the first freed agent slot |

**The working order** (D156; six agents from 14 November, D155):
1. **Now, in parallel:** the conduction probe on the engine as it is (Track E); D150's judged
   qualification; D152's MG0c with a compiled composition; the coupling design (Track R).
2. **Next:** one minimal inventory → effective control → measurable electrical-response case,
   qualified against an independent coupled-ODE reference.
3. **Then:** newborn integration in four named steps, and state-triggered division (the
   lifecycle gate's milestone 2).
4. **The first freed slot:** D147's composite policy with its four tests, then a table of which
   operators admit and refuse which, the phase start and failure records, and D154's writer.
   Nothing under `src/` lands between D150's final dry run and its judged snapshot.
5. **After GH200:** the sparse field solver, the parked D148 rounds, and the conduction
   workloads in the measurement plan.
6. **Held:** the full gene-regulation track and catalogue stage 3 (D145). E07-v2 is proposed,
   with three questions waiting for the user.

## The aim, restated

The next major success for Cells should be **several different biological behaviours,
explained through the same shared physical machinery, at a measured computational cost.**

Fidelity is measured per declared cell type and environment: how many independently
measured responses one coherent model predicts, with quantified uncertainty. Candidate
responses are voltage, ion composition, calcium response, volume regulation, energy demand,
division and recovery.

The rules that stay in force:
- design new features first (D142);
- one composite tissue model (D143);
- build only general, reusable, qualified models, never for one experiment (D144);
- molecular scope: assembly, not folding (D140);
- the J1 rules: J1 is a selection datum; curves for unmeasured unknowns; no value is picked
  from Em; C1 and J2 are held.

## The central abstraction: shared physical state

When two mechanisms affect the same physical thing, they must change the same state.
Examples:
- a channel assembled by the molecular machinery joins the population that membrane
  transport uses;
- water movement changes the concentrations that transport and reactions see;
- division partitions those same inventories.

The ownership contract to make explicit, consolidating the division design's entities:

| Entity | Primary state it owns | What other mechanisms contribute |
| --- | --- | --- |
| Compartment | Material amounts, volume, fixed-charge background | Reactions, transport, synthesis, removal, water movement |
| Membrane domain | Area, capacitance, location and orientation | Insertion, retrieval, deformation, partition |
| Functional-unit population | Identity (catalogue reference), abundance, internal state | Assembly, trafficking, turnover, regulation, inheritance |
| Contact | Endpoints, geometry, junction abundance, gate state | Formation, closure, remodelling, topology changes |
| Cell and lineage | Stable identity, membership, ancestry | Birth, division, replacement, death |
| Extracellular environment | Its own material, geometry and boundary conditions | Secretion, uptake, diffusion, external supply |

**How contributions combine** is checked when a model is built:
- fluxes add;
- availability factors multiply;
- an event may replace a value, but books what it removed and supplied;
- every derived observation has exactly one declared owner.

## Three separate scaling problems

| Objective | What it enables | Main work |
| --- | --- | --- |
| More independent worlds | Parameter uncertainty, controls, intervention search, replication | Batching, scheduling, less host overhead (well advanced) |
| A larger interacting world | Larger tissues and organ structures | A solver interface; sparse or matrix-free field methods; partitioning only if measurements justify it |
| Longer biological duration | Turnover, slow regulation, reconstruction, persistent memory | Qualified multirate or reduced-time methods |

**Duration may be the earlier constraint.**
- At 1 ms, one simulated hour is 3.6 million steps.
- E07 tier 1 is estimated at 4,100–7,200 L4 GPU-hours (PROGRESS), about 6–10 months on
  one L4.
- Two numbers should be reported:
  - validated biological world-hours per allocated GPU-hour;
  - elapsed time to one meaningful trajectory.

## Gates, in order

Numerical work and biological model discrimination can proceed in parallel. Shared-state
interfaces have one owner, the lead.

### Gate: today's commitments (unchanged)

- **Landing order:**
  1. the composite (water@1, water@2 and replacement@1 re-expressed under frozen guards);
  2. the plan-validation fix;
  3. the BITSEY rename, with a tag first;
  4. the J1 diagnostic's R-full extensions.

  Each is rebased and gated through the wrapper with about 5 GB, with `oom_kill` checked
  afterwards. The composite's long proof tests are run deliberately at the merged head.
- **No new tracks** until these have landed: Cortés-Poza Phase 1, the GRN track and
  catalogue stage 3 wait.
- **The J1 diagnostic** runs under its registered rules
  ([arms](../validation/division/j1_diagnostic_arms.json)). Check C1 and J2 stay held.
- **Running jobs continue:** the W1 water sheet arms and the turnover pre-screen
  (`resolved_pump_replacement@1` over `@3`, without water).
- **Test tiers are re-measured** only on idle cores. Last night's timings were taken
  under contention.

### Gate: execution

| Deliverable | Completion evidence |
| --- | --- |
| The plan-validation fix | For the long-clock 825-node case: expensive binds counted and scaling with distinct definitions; trajectories and accepted or refused steps unchanged; **the cost probe records windows** |
| Live phase markers (a follow-on, not added to the fix in flight) | Binding, plan validation, compile and first window reported as they happen; preparation, execution, observation and output timed separately |
| A bound-definition object, if the fix shows the need | Definition-invariant quantities bound once. State-dependent views (volumes under water, capacitance and masks under division) keep explicit update rules |
| One production execution path | Vector windows for families with qualified device checks; the other paths declared as reference paths; shared admission and checkpoint validation |
| A run-view output (D154: every experiment must eventually be visualizable) | One shared path writes, beside `definition.json`, each run's geometry, entity identity, record metadata, events, representation per layer and scale; a short design note first (D142), aligned with the visualizer's consumer schema |
| A compile policy | A rule for traced inputs and built-in constants, plus a resource budget around the existing executable cache |

**Note:** batch snapshots check every source file's hash. The W1 hold's prepared state
must therefore be regenerated (start and prepare, about 20 min) once the fix lands, before
the GPU segment runs.

### Gate: composition

| Deliverable | Completion evidence |
| --- | --- |
| The composite landed | Frozen-model guards (done on CPU); GPU agreement by **tolerance**, using the backend-variant method, because L4 repeats are not bitwise |
| An explicit ownership and conflict contract | The entity table above; the combination rules checked when a model is built; heat and work fields declared, not recognised by suffix; observation ownership explicit |
| An entity volume ledger | Newcomers declare volume and contents; volume changes from events are booked in water's ledgers; dilution and elastic free energy booked |
| **Water plus replacement**, the first composition with real interaction. Replacement@2 over water with the entity volume ledger is implemented and guarded (13 November) | Material, charge and free energy reconcile across replacement of a cell whose volume and composition have changed; later transport sees the newcomer's actual volume; a refused event leaves the full prior state |

The consumer of water plus replacement is the renewal assay (D144). Its qualification on the
heredity sheet comes with the assay that needs it.

**Secreted-species transport (D150).**
- **Design landed** ([note](SECRETED_SPECIES_TRANSPORT_DESIGN.md)): one inventory in @3 (neutral
  species rows), and split operators for turnover and for secretion and uptake.
- **Version 1 code landed (14 November 2026): milestones 1 and 2.**
  - `scheduled_species_turnover@1` and `scheduled_species_exchange@1`, with their guards.
  - Crossrev was identical in all five sets, and the tier 1 and 2 gates showed no changed outcome.
  - Integration grants no acceptance.
  - Milestone 3 is next: the comparison with the continuum closed forms, then the PROPOSED
    protocol. The lead reviews it with the advisor before registering.
  - The pre-code checks are in [note §11](SECRETED_SPECIES_TRANSPORT_DESIGN.md), and the rulings
    at milestone 1 in §12.
- **Deferred under D151:** a transport-only drift valence, and drawing on finite energy pools.
  Secreted proteins in the catalogue belong to stage 3.

**Reactions on the shared inventory (D152).** Driven nonlinear reactions that write @3's species
rows, as a general composite operator. Its consumers are MG0c's Turing case, GZMK item 2 and E15.
- **The design note was accepted on 14 November 2026** ([note](SHARED_INVENTORY_REACTIONS_DESIGN.md),
  rulings in §9). Code follows D150 v1's landing.
  - Its first milestone is the contract fit (C1), then the operator, its guards and MG0c.
  - Estimate: about 6 agent-days and an hour of CPU.
- **The first acceptance** is MG0c's numerical qualification against independent references.
- **Queued after D150 v1: a D148 round for @3** (probe C4).
  - It adds the material term for neutral species on junctions and membranes to @3's explicit
    bound and membrane-rate rule, statically gated.
  - It fixes stability, not accuracy, and opens D150 v1.1's bridge.
  - No world declares such a species, and both version 1s refuse them.

### Gate: lifecycle operators

These are the cell-division stages S2–S5 and current injection.

**Status (14 November 2026).** Membrane state (S2), insertion and the restricted lumen (S3, judged
against R-full), current injection (Rm1) and S5a's partition, bridge closure, insertion@2 and
lumen@2 are qualified. S5a passed its registered protocol against the independent references R-ops and
R-tissue. Q7(b), S3's egg on the @2 operators, is deferred. S5b and the endogenous lifecycle
come later. J2 and C1 stay held.

| Deliverable | Completion evidence |
| --- | --- |
| Membrane state as entity state; insertion; a restricted compartment; **current-injection control**; partition; bridge closure | Conservation and event tests; restart across events; the engine agrees with R-full |
| **Prescribed division** (milestone 1) | The physiology and accounting of a declared division sequence |
| A fresh prediction after model selection | **C1** soon, on R-full, once candidate cleft models are frozen and its rule is registered; **J2** after the partition |
| **Endogenous lifecycle** (milestone 2, later) | Division triggered by growth or regulation; daughters with conserved inventories and identities; repeated births and deaths. Needs decisions on reference anchors at birth, slot reuse and capacity, lineage across storage changes, conservation through topology changes, and checkpoints at events |

Current injection, membrane domains and restricted compartments did not depend on the J1
cleft answer, and all three are now qualified (above).

### Gate: compute limits

| Deliverable | Completion evidence |
| --- | --- |
| A full profile of a representative step | Only 41.5 of the 154 ms batch step at 64 worlds is accounted for today |
| GH200 measurements (needs access) | End-to-end cost, host and device memory, numerical agreement with CPU and L4 |
| A field-solver interface | It keeps the field law and residual checks. Sparse or matrix-free alternatives are compared on one device, covering the IMEX, capacitor and offset solves and the 2,048-node limit |
| A verdict on long-time methods | Multirate or quasi-steady methods qualified, or bounded, on histories and intervention responses (projective failed its qualification) |

Partitioning one world across devices is introduced only when single-device measurements
justify it. Thousands of cells do not by themselves need several GPUs.

### Gate: coupled renewal

This is the heredity question: can a written state repeatedly renew?

**Status (14 November 2026).** E07-v1 is judged ([PROGRESS](../PROGRESS.md)).
- Under donor-copy turnover the written disc did not renew. B1 was false in every fast k1 run,
  and J was 0.25–0.65, as neutral copying gives.
- The coupling's effect was far smaller than predicted. 8 of 15 scored predictions held.
- The s 1.0 control's collective falls await a 1 ms development check, and a readout of where
  the lost D copies sat is pending.
- E07-v2 is drafted as PROPOSED ([note](E07_V2_DESIGN.md)), for the lead's review with the
  advisor, with three questions for the user.

| Deliverable | Completion evidence |
| --- | --- |
| The revised cue, release and turnover assay (the E07-v1 redesign is the user's decision) | Cue-written starting states; water and volume regulation; the delayed junction-formation law; replacement schedules set relative to junction maturation; several complete founder turnovers |
| Separate outcome measures | Retention, newcomer conversion, spatial fidelity, continued transmissibility, physiological cost |
| E07-v2, drafted after E07-v1's analysis (user, 13 November: "we want to test all of this in the end"; D151) | The write–clear–challenge rules from the partial-reprogramming review, translated to Cells: classify by the state measured at the cue's end; clearance as a measured criterion on what the cue drove, where v1 used a fixed 2 min; the retained mark and a post-release functional challenge scored separately. Challenges, in order: a second cue, injected current, then an osmotic step (needs replacement over water). Each registers a no-turnover control, a fit inside the fixed-volume window and a check that it is not the mark again (a fresh D cell against a long-held one), named per world definition. The plan's own measures come first: continued transmissibility and physiological cost. |
| Causal carriers | Interventions on slow variables (ion loading, channel state, junction abundance, regulatory state) to find which ones explain the different futures |
| Robustness | Does the conclusion survive plausible uncertainty in the slow laws? The KCC law has no activation lag and no pH, Mg or phosphorylation state; the junction-formation shape is a modelling choice, not a fit |

**Scale is named, not assumed.**
- First the 127-cell sheet on CPU.
- The 825-node full tissue needs GH200 access or a qualified long-time method.

### Gate: a closed molecular-to-physiology loop

| Deliverable | Completion evidence |
| --- | --- |
| One regulated functional-unit population | A regulated production rate; a finite precursor inventory; assembly and trafficking delays; insertion and removal; a quantitative abundance-to-function relation; partition at division |
| One material account | All of these reconcile in one account and predict a measured physiological response |

The choice of unit is the user's. Candidates where abundance is already state:
- the redistribution pumps (`resolved_redistribution@1/@2`);
- junction formation.

The [protein catalogue](PROTEIN_CATALOGUE_PLAN.md) supplies identity, stoichiometry and
evidence.

### Gate: an integrated tissue unit

Mechanics, transport and lifecycle together on changing geometry.

Completion evidence:
- coupled refinement;
- accounting through topology events;
- held-out functional responses.

## A declarative registry, placed after execution and composition

The goal is one place that declares how a model takes part in parsing, serialisation,
controls, execution and checkpoints. Replacing only `get_model()` would leave the
duplicated dispatch elsewhere. Today's subclass ordering is meaningful, so dispatch parity
needs protecting with tests.

## How the work is organised

The lead coordinates three streams. The streams meet at small executable cases: a proposed
interface proves itself on an actual Cells model.

| Stream | Owns |
| --- | --- |
| Architecture and integration | Entities, composition, binding, registration, lifecycle interfaces |
| Numerics and execution | Profiling, field solvers, long-time methods, CPU and GPU qualification |
| Biological models and evidence | The heredity and division cases, parameter provenance, model discrimination, held-out predictions |

Agent limits and the memory rules from AGENTS.md apply. Every long job runs as its own
capped unit (`scripts/run_detached.sh`).

## 90-day objectives (working targets)

| Objective | Gate | Cost or feasibility |
| --- | --- | --- |
| A landed, reusable composite physiology model | Composition | Guards done on CPU; GPU agreement pending |
| A dependable execution path with measured GH200 costs | Execution, compute limits | GH200 access needed |
| General division operations, with a clear line between prescribed and state-triggered division | Lifecycle | S2–S5, about 10–11 agent-days by the division plan's own estimate |
| A repeated-turnover experiment with a defensible positive or negative result | Coupled renewal | The 127-cell sheet on CPU; the full tissue only with GH200 or a long-time method (E07 tier 1 is 4,100–7,200 L4 GPU-hours) |
| At least one fresh biological prediction after model selection | Lifecycle | C1 on R-full first; J2 after the partition |
| A compact public validation package: representative inputs, machine-readable outcomes, failure records, short reproduction commands | All | Tooling: needs the user's approval |

## The longer progression

1. A coherent cell model: multiple processes sharing inventories and predicting several
   responses in one preparation.
2. A functional tissue unit.
3. Larger, more heterogeneous tissues.
4. An organ model.
5. Interacting organs and intervention discovery.

Each step uses the same qualified mechanisms. For Plastic Heredity and How Patterns Return,
any reduced model must keep the slow variables that carry history. Matching present
voltage or shape is not enough: fresh and fully loaded depolarised cells already show
that.

## Decisions taken (D145) and still open

**Taken:**
- The plan is adopted.
- GH200 (JUPITER) work waits for access, expected by the end of next week. The L4 is used
  fully meanwhile.
- The suggested choices, as listed in D145:
  - C1 stays held.
  - The single-world size is set from the L4 profile and the GH200 numbers.
  - The molecular-loop unit is provisionally the junction-channel population.
  - Heredity and division run in parallel: division takes the agent slots; heredity takes
    the cores and the L4.
  - The E07-v1 redesign stays open until the turnover results exist.

**Still open:**
- The public validation package (tooling; the user's approval). Checkpoint continuity was
  approved (D153).
- More RAM on the VM.
- Linger: run `loginctl enable-linger robert` yourself. The agent's attempt was blocked as a
  persistence change.
