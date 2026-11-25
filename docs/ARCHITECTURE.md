# Architecture

Implementation context reviewed: **2026-10-11**. The [modular core](#the-modular-core-d172-d174)
section, added on 15 November 2026 (D172, D174) and refreshed after D172's round landed on 16
November, takes precedence where older sections differ.
Cells uses Python for definitions,
orchestration and checks, and JAX array kernels for supported CPU/GPU execution.
[Progress](../PROGRESS.md) owns the current qualification record; this document
explains component responsibilities and target interfaces.

Implemented building blocks include versioned cell/graph models, finite and
spatial extracellular inventories, [resolved tissue fields](TISSUE_RETURN_CURRENT.md),
[compartment chemistry](COMPARTMENT_REACTIONS.md), [calcium/IP3](PLASMA_CALCIUM.md),
and [stochastic assembly with experimental cell coupling](CAPSID_ASSEMBLY.md).
Shared workflows provide complete checkpoints, windows and independent ensembles.
CPU/L4 results apply to their declared model families and test conditions.

[GPU ensembles](GPU_ENSEMBLES.md) distribute independent worlds. Jupiter
qualification, distributed interacting tissues, adaptive fine/coarse resolution,
biophysical mechanics and organ models remain additional work. A named component
can exist before ordinary configuration or full integrated qualification is ready;
implementation alone does not complete those steps.

The contracts below describe both exercised interfaces and future extensions.
[Historical implementation notes](#historical-implementation-notes) retain the
original version-specific milestones without acting as a current task board.

## The modular core (D172, D174)

Added 15 November 2026. D172 settled the direction: one active inner model, made modular in place.
An external architecture review then set the boundary and acceptance below, and the lead adopted
it after reviewing it with the advisor (D174). A second review of this section clarified it the
same day. D172's round landed on main on 16 November 2026 (merge ab267c39, tag
`d172-landed-2026-11-16`), and the statuses below are refreshed against it. Every statement carries
a status:
- **holds today**, meaning in code read or in a landed test;
- **target**, meaning decided but not yet met, in D172's restructure round or in a later accepted
  milestone, as marked;
- **open**, meaning not yet decided.

The implementation note names the minimum cases required to land D172, and the consumer cases
completed in subsequent accepted milestones. A target interface does not by itself bring its
consumer's full scientific qualification into the restructuring. The results gate keeps D172's
output and registered-protocol checks, and adds required-case execution and the planted-change test.

Where older sections of this document differ, this section applies.

### Responsibilities

| Part | Responsibility | Where it lives today |
| --- | --- | --- |
| Physical state and entities | The authoritative amounts, volumes, membrane properties, populations, contacts and identities | @3's state, plus fields owned by operators (`ENTITY_WRITES`) and by declared kinds |
| Mechanism declarations | Each law's inputs, the quantities it changes, its conservation and energy role, its domain of validity | The operator contract (`contract.py`). Since the landing, @3's laws are frozen declarations (`models/inner_laws.py`), with one implementation built per declared structure, and kinds register through the build-scoped kind registry (`registry/kind_registry.py`; the built-in kinds are in `kinds/`) |
| Numerical plan | Evaluation order, explicit or implicit treatment, splitting, event boundaries, error checks | @3's IMEX and RK4 steps, the operators' split parts, `StepChecks`, schedules |
| Biological definitions | Organism, strain, conditions, parameter values, evidence references | World builders and fixtures. No organism definition yet; the [Syn3A note](SYN3A_MINIMAL_CELL_TRACK.md) proposes one |
| Execution and outputs | Binding, device windows, checkpoints, observations, the shared run view | The runner, batch and window paths; D153's checkpoints; D154's run view, whose interface in the operator contract (`VIEW_LAYERS`, `view_events`) is on main, and so are the operators' declarations and the writer (`src/cells/records/run_view.py`), since 16 November |

- **Arrays in the loop.** The composite builder assembles these parts into one bound array program.
  Python objects and modular interfaces belong to definition, validation and binding, and the
  production time loop runs on arrays. **Holds today in the vector-window path:** the composite's
  checked step and its device checks run vmapped inside one compiled scan (`vector_windows.py`,
  `pump_composite.device_checks`). Host-side per-row checks in other paths belong to the audit
  below.
- **The test of reuse.** A second biological use case runs on the same laws and state through
  configuration. A new organism or experiment adds engine physics only for a mechanism the engine
  lacks (D144). **Target.**
- **What D172 drops.** It drops old programs and checkpoints, not qualified results. Old evidence
  stays reproducible from frozen snapshots. Qualified results are protected by the results gate
  below.

### GPU-native execution

- **Three kinds of data are declared apart. Target.**
  - Executable structure: law kinds, compatible topology and capacities, array schemas, the
    numerical plan.
  - Runtime device data: rates, abundances, controls, initial conditions, activity masks, evolving
    state.
  - Host work: parsing, admission checks, assembly, binding, window dispatch, requested output
    processing.
- **What the restructure must show:**
  - **Undeclared mechanisms are absent from the traced program. Holds today for @3's laws, since
    the landing.**
    - Before it, @3 traced all three gated channel laws for every population, and the law table's
      length was a literal in every program (the inner-model probe, 14 November).
    - So per-law dispatch was required: build-time selection of the declared kernels, since a
      runtime switch over the whole catalogue would still trace absent mechanisms. It landed with
      the round, as one implementation per declared structure, and a landed test shows that an
      undeclared law traces no kernel (`tests/unit/test_inner_laws.py`).
    - It moved no result: the integrated candidate before A7 was bitwise on all 113 worlds of the
      results gate. A7's summation order then moved ledger and diagnostic arrays at rounding, so
      the round re-ran the registered protocols (G2), with E07-v1's re-run held (D181).
  - **Executable reuse and device-resident checks. Reuse holds today, in a landed test.
    Device-resident checks hold in part: opt-in for scalar windows on the CPU since 16 November;
    the vector path and the GPU are targets.**
    - For a fixed law set, numerical plan, compatible array shapes, dtypes and device placement,
      parameter-only changes reuse the executable.
    - Production state advancement, step checks and refusal handling remain inside device windows.
    - Host boundary checks and requested output processing remain allowed. So do the host checks on
      every row that qualification and development runs use.
    - **Holds today in the vector-window path.** Steps and device checks run vmapped inside one
      compiled scan. Executables are reused by step and check function, rows, array structure,
      shapes, dtypes and placement (`vector_windows.compile_window`). So parameter values passed as
      arrays reuse the executable, but constants baked into a model's functions do not.
    - **Holds today, since the landing:** the key also carries the declared structure. A landed test
      shows a parameter-only change compiling nothing and matching a fresh compile bitwise, while a
      world of another structure compiles its own (`tests/unit/test_inner_executable_reuse.py`).
    - **The audit** lists the exceptions: constants baked into programs, and checks or refusals run
      on the host per row in production paths. Its two inventories are in the inner-model note
      (§5.1, §5.2). Moving the host-side window checks into device windows has begun:
      `WindowPolicy(row_checks="device")` checks scalar windows' rows on the device and hands a
      window back to the host checks on any failure or margin above 1/2
      ([design](WINDOW_DEVICE_CHECKS_DESIGN.md)). It is refused on a GPU: the one
      GPU measurement, on the composite, failed its qualification (D330, D336).
  - **Adding a mechanism adds no per-cell Python dispatch and no CPU solver to the production loop.
    Target.**
  - **Compile time, host and device memory, and end-to-end time are measured on representative
    compositions. Target.**
- **Methods may differ.** Mechanisms may use different qualified numerical methods. Stiff chemistry
  and fast electrical propagation need not share an update method.
- **Three capabilities are reported separately:** ensemble throughput, interacting-world size and
  biological duration. One does not establish another. The L4 evidence stays scoped: Q7 passed only
  in the declared deterministic mode (D181), and GH200 numbers come when available. **Holds
  today,** as a reporting rule.

### Scoped composition (door S)

- **Before the landing: one provider per field.**
  - The adapter's view (`pump_composite_adapter.view`) applied each provider by replacing the whole
    field.
  - A provider such as the bath schedule returned its own values on its slots and the bound values
    elsewhere.
  - So a nominal refusal in the composition matrix meant that the slots were disjoint. It did not
    mean the pair was safe to admit under that adapter.
- **Holds today, since the landing: what each mechanism declares** (`operators/contract.py`).
  - The fields and entity slots it reads, and whether it reads reference values, a fixed declared
    value or the current composed view (`SCOPED_READS`).
  - The slots it changes, and whether its contribution adds, multiplies or replaces; a closer's is
    `and` (`VIEW_CHANGES`).
  - The stage at which it is evaluated.

  The composite admits each pair per slot and merges each change onto the accumulated current view
  on its slots (`pump_composite_adapter.view`). In the round, closers change whole masks, and the
  one pair newly admitted is the bath schedule beside D152's reactions; the other pairs keep their
  refusals.
- **Acceptance, met in landed tests** (`tests/unit/test_door_s.py`):
  - two independent providers on disjoint slots compose to the same bits in either declaration
    order;
  - overlap is refused unless both changes commute (add, multiply, `and`);
  - readers see the merged values at their declared stage.

  The integration case, the bath → uptake → compartment → reaction chain, runs with every ledger
  closing (`tests/unit/test_delivery_world.py`). It is guarded, not numerically qualified.
- **Door S changes scope.** As accepted in D169 it covered admission only. It now includes the
  runtime merge, and it landed with D172's round (D174).

### Ownership, geometry and solver invalidation

- **Three things are kept separate. Target.**
  - Owning a membrane population.
  - Changing membrane geometry or capacitance.
  - Invalidating a numerical operator or factorization, such as the field refresh.

  An occupancy change has only the numerical effects its physics requires. FR-3's separate owner,
  which avoids the field refresh and its 64-node cap, stays as accepted.
- **Compartment identity is a host-side map. Partly holds today.**
  - The map holds the compartment ID, owner, role, storage slot and oriented membrane endpoints. It
    is independent of today's storage as an outside node.
  - Sensing and transfer laws address a species in a named compartment, so one law serves
    cytosolic, lysosomal and mitochondrial cases. **Target:** such laws come with FR-4 and FR-5.
  - The accepted FR-1 design names each compartment's node, bounding patch and owner. Its operator
    (`cell_owned_compartments@1`, milestone 1) is on main since 15 November, and it writes the map
    (`compartments.identity_map`).
- **Acceptance:**
  - an occupancy-only world with fixed field inputs avoids the field refresh;
  - a capacitance-changing world triggers it;
  - two compartments in one cell stay distinct;
  - ownership-changing operations update the declared resources or refuse.
- **Not now:** runtime entity objects, or a general nested-compartment framework.

### Material identity and fuel

- **One authoritative account per physical quantity. Target.** Free and bound ligand may live in
  different arrays, but they resolve to one species identity and one conserved total.
- **Species identity and the background and trace policy are consolidated at the definition
  boundary. Holds today, since the landing.** New laws then add no pairwise identity checks between
  operators. The species registry (`registry/species_registry.py`) is one authority for each species'
  identity, standard potential and background, and a landed test refuses any pairwise identity
  check left in `src` (`tests/unit/test_species_registry.py`). Before the landing, the coupling
  operator checked species identity against D150's and D152's declarations.
- **Fuel: the requirement is fixed, and the representation is decided (D176).**
  - **The requirement:** reactions can make and spend fuel; pumps draw from those same amounts;
    each standard chemical potential has one authority; water and division get explicit interfaces
    later.
  - **The representation is decided (D176): F2.** ATP, ADP and Pi are shared inventory species,
    used by reactions and pumps, with one authority for amounts and standard chemical potentials.
    Maintained fuel is held inventory rows, not pump parameters. The "moved by the step" admission
    keeps instantaneous regulation from reading pump-consumed fuel as unchanged.
  - **The first case. Target.** A fixed volume holds one stoichiometric regeneration reaction and
    one pump, sharing finite ATP, ADP and Pi. It shows depletion, reduced pump activity and
    recovery, with material and energy accounting checked independently. Water, division and full
    metabolism are not prerequisites.
- **Two boundaries to declare.**
  - **Transformed potentials against protons: declared for maintained fuel, open for finite fuel.**
    - **For maintained fuel** (FR-4 §5.2, `cells.transporter@1`, landed with D172): hydrolysis is
      transformed at the fuel node's `ph_ref`. The domain refuses any stage where
      |pH − `ph_ref`| > `ph_band`, and Δ_rG'° comes only from the species registry. pMg is implicit
      in the registry's transformed potentials.
    - **Still refused, and open:** finite fuel at a node with a dynamic proton row. This is the
      finite-fuel design in the FR-4/FR-5 lane's queue.
  - **Booked work is not fuel.** D152's booked external work is not a finite fuel-consumption law.
    Finite fuel needs a declared donor, stoichiometry and affinity.

### Transport laws by physical contract

- **Holds today: exchange is a driven route.** `scheduled_species_exchange@1` books the free-energy
  change of what it moves as signed supplied work, with no heat. A matching concentration trajectory
  through paired routes does not make it passive permeation.
- **What a passive permeation law must show. Target.**
  - In a closed, fixed-volume two-compartment test, it conserves material, has zero net flux at
    equal chemical potential, reverses with the driving force, and dissipates the free-energy
    decrease without externally supplied work.
  - In a held-bath system, the total balance includes the declared reservoir work.
  - Its composition with water is qualified separately, using the same amounts and current volumes.

  A new generic passive law was expected in D172's round, reusing the common inventory, geometry and
  numerical machinery. First it was checked which admissible topology is closed for the test species,
  since FR-1's compartments sit in worlds with a held bath.
- **The law landed with the round:** `passive_neutral_permeation@1`, a law of the passive-routes
  kind (`cells.passive_routes@1`, `kinds/passive_routes.py`). It is implemented and
  guarded. On a closed pair, FR-1's face-free world, it relaxes as the independent closed form
  says, conserves material, and books as heat the engine's own free-energy decrease, to rounding
  (`tests/unit/test_passive_routes_kind.py`). It is not numerically qualified, and its composition
  with water is still a target.
- **The reuse rule.** A law is reused only where its physical contract, its energy role included,
  matches.

### State roles and time

- **Each field declares its evolution role. Target.** The roles are continuous dynamical state,
  algebraic state, accumulated history, and discrete event state. Conservation laws are
  relationships over those fields; an evolving amount may take part in several invariants.
- **Exact counters declare whether they count numerical steps or physical events. Target.** Physical
  time and crossing-time interpretation come from the numerical plan. The coupling operator's
  crossing record counts numerical steps today, and its declaration will say so.
- **Numerical plans carry time explicitly. Target, interfaces only.**
  - They carry the interval and stage time and the next compulsory event boundary, so a future coarse
    step respects doses, regulatory writes and timed events.
  - Stiff chemistry may run as a qualified local implicit or substepped block, with explicit exchange
    stages and residual checks. The physical law stays one law while its numerical treatment
    evolves.
- **FR-8's eventual acceptance. Target, in FR-8's own milestone.**
  - An intervention during a slow interval.
  - Histories and integer state preserved.
  - Crossing-time accuracy.
  - Restart across the intervention.
  - Convergence under different admissible macrosteps.

  Fixed-step restrictions stay until then. The two-clock assay strategy stays within its scope.

### Levels of detail

**The principle.** One engine supports different declared representations of a mechanism, chosen
per mechanism and per question. A world can combine detailed electrical dynamics with reduced
metabolism, or the reverse, and no single global detail level implies accuracy everywhere.

**The existing basis.** This builds on
[fidelity and resolution](MULTISCALE_EXECUTION_ARCHITECTURE.md#fidelity-and-resolution-are-explicit-capabilities)
and [spatial and temporal scales](MULTISCALE_DESIGN.md#spatial-and-temporal-scales). They already
require:
- named model families;
- refusal of unsupported observations;
- static region assignments first;
- closures tested on future responses.

- **Compatibility is defined at the physical interface. Target.**
  - A detailed and a reduced representation may have different internal state.
  - At the interface they expose the same quantities, controls, observations and coupling timing.
  - Each closes its own ledgers. Both expose the same amounts and invariants at the interface.
  - Their transient difference, such as material or free energy in transit through intermediate
    pools, belongs to the reduction's declared error budget.
- **One representation of a pathway per scope. Target.** "What is represented" is a declared key
  that admission compares, so a lumped reaction and its detailed network cannot both produce the
  same flux on the same nodes. Nothing refuses that today.
- **A small declaration, only on laws that stand in for something. Target; its fields are reserved,
  unused, in the landed law declarations (`ChannelLaw` in `models/inner_laws.py`).** It has four
  optional fields:
  - **what it represents:** the key above, and the reference it was reduced from;
  - **what it preserves:** retained state and history;
  - **what can be asked of it:** supported interventions, controls and observations, with others
    refused;
  - **where it is qualified:** its validity envelope and error budget. Enforceable bounds, checked at
    run time like the channel laws' voltage domains (**holds today** for those), are kept apart from
    assumptions that need evidence.
- **Representation and numerical method stay separate.**
  - Deterministic and stochastic execution have explicit semantics.
  - Reaction declarations are reused where valid, but stochastic execution needs count-based
    propensities and its own qualification.
  - **Holds today only within its own family:** `capsid_graph@1` assembly runs an event solver
    ([CAPSID_ASSEMBLY.md](CAPSID_ASSEMBLY.md)).
  - **Target, later:** general stochastic metabolism on the shared inventory.
- **Fixed assignments come first.**
  - Detail is selected before a run.
  - Static mixed-detail regions come next. They need scoped writes (door S), compatible exchange
    interfaces and synchronised accounting.
  - Automatic promotion and demotion is a later milestone. It needs explicit state transfer,
    reconstruction, history and uncertainty rules.
- **Execution stays GPU-native.**
  - **Target:** each declared representation group gets its own specialised kernels, connected
    through array exchanges. A reduced representation must remove actual work and storage; a runtime
    flag that still traces and evaluates the detailed mechanisms does not count.
  - **Holds today** for runs through the shared output path: the selected representation is
    recorded with every run, because `io.write_run` records the resolved definition
    (`resolved_config.json`). The run view will carry it too (D154).
  - **Rule:** fidelity never changes silently because of a resource limit.
- **Three validations stay separate. Rule.** They are:
  - numerical verification of each representation;
  - reduction accuracy, where the detailed model is the reference, not biological ground truth;
  - biological validation.

  For reduction accuracy:
  - the envelope and the error budget are declared before the comparison runs;
  - at least one case outside the envelope must fail;
  - the detailed reference is itself numerically verified in that regime against an independent
    reference;
  - the declared comparisons are automated, and they report their scope.
- **The first consumer comes after D174's fuel case. Target, a consumer milestone, after that case.**
  The representation is decided (F2, D176).
  - D174's fuel case, one regeneration reaction and one pump, is the reduced closure.
  - The consumer milestone adds a small detailed regeneration network, sharing the same fuel amounts
    and pump interface.
  - It compares depletion, demand changes and recovery, including transients, accounting and
    measured cost.
  - A later two-region case tests exchange between detailed and reduced regions.

#### Requirements collected for the four fields (17 November 2026)

Collected for one design against three consumers (D209, L4). Nothing here designs the fields: the
law template reserves them, and registration refuses them (`registry/laws.py`).
- **Fuel (D174), the first consumer:** the reduced closure, one regeneration reaction and one pump,
  declared against a small detailed network that shares its fuel amounts and pump interface (above).
- **Machines (FR-13; MOLECULAR_MACHINES_DESIGN §10.1, §10.5):** a minimal form before M1b:
  `represents` with its admission, so that a diagram law and D193's synthesis law cannot both be one
  population's aggregate; `supports`, refusing an observation the representation cannot answer; the
  envelope of `qualified`; and their manifest keys.
- **Mitochondria (D210; MITOCHONDRIA_DESIGN, addendum C):** the fields must also sit on host
  declarations, since the compartments declaration and the event doors set a mitochondrion's level,
  not a law. `represents` names a population and its owner with each declaration's share, so a pool
  beside k individuals stays admissible when the shares are disjoint and cover the whole.
  `preserves`, `supports` and `qualified` are listed per level there.

### Reuse cases and the results gate

Which cases must land with D172 and which come with their consumers is listed in the implementation
note.

| Case | What it exercises | Status |
| --- | --- | --- |
| Inventory → regulation → electrical response | Shared amounts, control routing, temporal coupling | Numerically qualified (15 November): Track R's judged protocol passed, with A4 and A5 against independent references. CPU only |
| Bath dose → uptake → compartment retention or reaction | Scoped views, compartment identity, material accounting | Guarded since the landing: door S's integration world runs with every ledger closing (`tests/unit/test_delivery_world.py`). Not numerically qualified |
| Reaction → finite fuel → pump | Chemistry and electrics sharing one energy budget | Target. The representation is decided (F2, D176); this is D176's finite-fuel case. Its single regeneration reaction is also the reduced closure of the first [levels-of-detail](#levels-of-detail) case |
| Neutral solute and water in a vesicle | Reuse across biological settings, changing concentration and volume | Target. The passive law landed with the round; its composition with water does not exist yet. Syn3A's probe P0 checks capability |

- **Organism data stays apart from engine mechanisms. Target.** The organism and evidence structure
  lands with its first consuming milestone, with its observation model and calibrated nuisance
  parameters.
- **Biological claims keep their kinds apart. Rule.** A protein-free vesicle test, numerical
  verification, calibration and a held-out living-cell prediction are different claims.
  Continuum, lumped-population and individual-compartment interpretations are declared.
- **The results gate for D172.** It names the required scientific cases and checks that they
  actually execute, plus the agreed planted-change test. **What PROGRESS records as passed at the
  landing (16 November):** G1, with the candidate bitwise on 113 of 113 worlds before A7 and within
  A7's frozen tolerance file after it, every physical field bitwise; crossrev; tiers 1 and 2 with no
  changed outcome, and tier 3 with every non-passing file classified; G2's registered protocols; and
  the L4 block. PROGRESS records no run of the planted changes (G3) or of the measurements (G4);
  the comparison's own planted-difference self-test is a landed unit test
  (`tests/unit/test_results_baseline.py`).
  - **Holds today, since the round:** the tier gate counts a file as changed when its exit code or
    its failed or error count differs from its row, when its passed count falls below the row's, or
    when its skipped count rises above it. A passed count above the row's is listed for
    re-measurement (`scripts/test_tiers.py`).
  - Before that change, on 14 November, a read-only check of the landing gates found no lost tests
    at count level, and the tier record's counts stale for about a dozen files that had gained
    tests ([comparison](/mnt/workspaces/Cells/external-review-20261114/gate-count-comparison.json)).
- **Regression after the landing (D187). Rule.** Crossrev and the results gate carry regression
  only for what their worlds exercise, and each landed feature adds one world to their sets. A new
  test needs a planted error it must catch. Old regression tests that do not earn their cost are
  retired after D187's audit, with the retire list going to the user first; the science keeps its
  independent references, planted controls, conservation checks and one judged run per claim.
- **The shared run view. Target.** It exposes the same entity identities, units, events, model
  scope and representation, and the viewer consumes them without reconstructing meaning from driver
  conventions. D154's note is proposed; the operator contract's view interface is on main, and the
  operators' declarations and the writer are on main since 16 November.

### Order

- **The qualification boundaries stay as agreed** for MG0c, Track R and Track E. D172's interfaces
  above are finalized during that work.
- **Then the single restructure round.** It landed on 16 November (tag `d172-landed-2026-11-16`),
  with main tagged before it (`d172-base-2026-11-15`), frozen evidence and the results gate.
- **The source tree has the modular layout (D188).** Two scripted moves put the older families in
  `src/cells/legacy/` (move 1, 17 November) and the modular parts in their own folders (move 2,
  18 November, tag `d188-move2-landed-2026-11-18`): `laws/`, `kinds/`, `operators/`,
  `definitions/`, `execution/`, `registry/` and `records/`. The source paths named in this document
  are post-move. The older families left in the legacy cleanup (25 November 2026, D386); the tag
  `pre-cleanup-2026-11-25` keeps them.
- **The accepted feature work continues in its order:** compartments, occupancy and delivery. Their
  real interactions exercise these contracts. The minimal-cell track supplies consumers and
  measured-data tests without displacing FR-4 and FR-5.
- **The success criterion:** adding a biological capability is a bounded addition of declarations
  and physical laws, with shared state, predictable GPU execution and reusable validation.

## External modules (proposed)

*Proposed on 15 November 2026 in [MODULE_SYSTEM_DESIGN.md](MODULE_SYSTEM_DESIGN.md). The user made
its five open decisions on 16 November (D185), and its stage 1 starts after D172's landing. It uses
the modular core's status words: holds today, target and open.*

**The target.** Cells stays MIT and aims at broad adoption.
- Independently maintained packages use, extend and compose Cells, and the project extends
  itself through the same interfaces.
- An external component meets the same validation, composition, execution and accounting
  contracts as a built-in one.
- Every component follows one path. It is registered explicitly into a registry scoped to one
  model build, then resolved, validated, assembled, compiled and run.

**Ownership boundaries.**
- **Cells owns** shared physical state and its accounting, the seams where components attach,
  admission, the numerical plan, compilation and its caches, checkpoints and run records.
- **A module owns** its declarations, its pure kernels, its own accumulators and its evidence. The
  declarations cover:
  - the quantities it reads and changes, with their units;
  - its own state, transfers, controls and stages;
  - its domain of validity;
  - the methods, backends and precision it supports.
- **Shared state is reached only through declared interfaces.** A module never reads another
  component's layout. Cells books the ledgers from the transfers actually applied.
- **IDs are namespaced** (`example.law@1`), and bare IDs belong to `cells`.
- **Registration is explicit,** never at import or by discovery. Registering an unused module
  changes no other model's state layout, program or run record.
- **Reference simulators stay out of process,** inside modules too (AGENTS.md).
- **Interface validity is not scientific validity.** Interface, accounting, accuracy, validity
  and performance are qualified apart.

**Holds today.** Built-in contracts with closed lookup: the operator contract, the model registry
and the definition parser are module-level tables. Any package can already ship definitions and
builders that use built-in IDs.

**Holds today, since D172's round** ([INNER_MODEL_V4_DESIGN.md](INNER_MODEL_V4_DESIGN.md) §7.4
(j)–(k); `registry/kind_registry.py`, with the built-in kinds in `kinds/`).
- **The seams:**
  - kinds register through a build-scoped registry, and built-in kinds use the same call;
  - IDs are namespaced, and the canonical order is the sorted namespaced ID;
  - a registered but undeclared kind changes nothing (`tests/unit/test_kind_types.py`; a planted
    kind registered from outside `src/cells` runs every seam in `tests/unit/test_kind_seams.py`).
- **Version 1 for kinds:**
  - their ledger terms fold into today's ledgers by role;
  - their state is observed;
  - their material moves land in the shared inventory;
  - their controls are availabilities unless declared otherwise.

**Target, staged by consumers:**
1. A separately installed package adds one law to an unchanged Cells installation, through normal
   construction, execution, checkpoints and provenance.
2. A stateful mechanism and a reusable composition, each instantiated twice.
3. A reduced and detailed pair, on the first [levels-of-detail](#levels-of-detail) consumer.
4. Other levels on demand: geometry, numerical methods, backends.

**Each stage's acceptance.** Its components:
- use the normal pipeline;
- keep their accounting correct;
- meet their CPU and GPU criteria;
- reuse compilation across parameter changes;
- survive checkpoint and restart.

Duplicate, missing and incompatible components are refused clearly, and unused modules change
nothing.

**Decided by the user on 16 November 2026 (D185):**
- **A module PR:** in-tree contributed modules first, each in its own folder and namespace, with an
  MIT licence and a named owner, gated by the conformance kit and the tiers. Out-of-tree modules,
  listed by a docs PR with their conformance record, may follow.
- **Qualifying outside modules:** a conformance kit shipped in Cells, which the contributor runs
  before opening the PR. In the lead's reading, recorded in D185, a pass means the kit's checks
  passed; the science still needs a registered protocol.
- **D144 with modules:** new physics goes into `src/cells` as modules of its structure (laws, kinds
  and operators, each declared and registered), and `validation/` still holds no physics.
- **The example:** in this repository, as a separately installable folder installed as a wheel in
  tier 2. It doubles as the template contributors copy.
- **Provenance:** development runs record each outside module's identity, computed at run time;
  registered and judged runs also freeze its files beside the snapshot (AGENTS.md).

D185 adds a declarations manifest, a JSON list of every registered law, operator and kind, and a
contributor guide with a pull-request template. **Target:** none of stage 1 is built yet; the kit,
the example module, the manifest and the guide come with it.

**Open:**
- whether the project lists the modules that pass;
- provenance for in-tree contributed modules, settled in stage 1's design;
- automatic checks on GitHub for outside pull requests, to be asked separately.

**Not designed:** nested compositions beyond templates, external numerical methods and backends,
and switching levels of detail at run time.

## System shape

*Where this differs from [the modular core](#the-modular-core-d172-d174), that section applies.*

Build one headless Python library. JAX executes numerical kernels on CPU and,
for supported model families, GPU. Experiments, analysis, and a viewer use the same simulation
interface. Small NumPy/SciPy reference calculations support verification of
equations and numerical methods.

| Component | Responsibility | Main exchanges |
| --- | --- | --- |
| Intracellular models | Regulatory, ionic, and explicitly specified carrier dynamics | Cell state, membrane fluxes, environmental inputs |
| Communication | Molecule-selective and voltage-dependent exchange | Edge properties and endpoint states |
| Spatial environment | Positions, geometry, extracellular fields, later mechanics | Cell-field source terms and physical contacts |
| Lifecycle | Growth, division, death, partition, and ancestry | Cell volumes, amounts, identities, and topology |
| Scheduler | Physical time, process update times, and discrete events | Valid coupling order and reproducible event handling |
| Experiments | Initialisation, cues, interventions, checkpoint branches | Explicit external actions and their resource use |
| Observers and outputs | Measurements, trajectories, manifests, and visualisation | Read-only state and declared sampling times |

Resolve model, experiment, and execution definitions separately on the host.
Organ presets select implemented processes and wire their interfaces; new physics
requires a tested model module. The engine must not dispatch behaviour by an
organ name. Component ownership is distinct from the graph of physical exchange.

Each process declares its state schema, units, permitted reads, contributions to
state change, and timing contract. Static definitions and dynamic array state
remain separate. M1a/M1b/M1c-a, CORE-003 and MODEL-003/004/005 exercise these
boundaries with small functions and an explicit model registry, not a general plugin or
distributed-computing framework.
Each model owns its numerical state/layout, pure derivative, checks, and observers.
The reduced EMT model does not acquire a fictional physical volume or use the
synthetic model's amount/ledger fields. Its fixed Snail context lives in the model
definition; its derived complexes and E/M labels remain outside primary state.
The passive model owns cell amounts and an edge-transfer ledger; a separate
coupling module returns conservative amount fluxes. Its opening schedule is an
external contact control, not an amount source or an intracellular gate law.
The composition model maps two declared species into local conversion and the
same passive coupler. Their derivatives add to the same amount fields at each
RK stage; signed reaction and transport ledgers remain separate. This exercises
reusable contributions, not arbitrary model-family assembly or reaction networks.

Intracellular and intercellular networks are distinct structures. Different
intracellular models may represent different hypotheses or levels of resolution.
GARD, Boolean regulation, and continuous biochemical equations need explicit
contracts if supported; they do not share an assumed universal physical clock.

## Simulation state

Represent each world as an explicit collection of arrays suitable for a JAX
PyTree. Avoid hidden mutable global state in numerical kernels. A conceptual
advance operation takes state, model parameters, inputs, and random state, and
returns updated state plus diagnostics.

| State block | Initial contents or extension point |
| --- | --- |
| Cells | Primary biochemical variables, active mask, stable cell IDs, model/type identifiers, volume, positions |
| Membranes | Separate surface IDs/masks, owner-cell and facing-compartment mappings, area, capacitance and permeability implemented in MODEL-003/004; membrane-channel gates remain planned |
| Contacts | Endpoint slots, active mask, contact geometry, conductance/permeability parameters, any declared dynamic gate state |
| Environment | Reservoir conditions initially; field arrays, grid geometry, and boundary conditions when added |
| Lifecycle | Parent IDs, generation or lineage metadata, age, cycle/resource state when the model includes them |
| Execution | Physical time, scheduled update times, pending interventions, random state, and integrator state needed for restart |

Derived species, voltage, and phenotype may be computed from primary variables.
Each model declares which quantities are dynamic and which are algebraic, along
with its units and refresh rules. Avoid evolving redundant representations
independently. In the initial BITSEY comparison, preserve its documented primary
totals, derived-species approximations, fixed inputs, and endpoint semantics.

Parameters declare whether they are shared constraints, cell-specific constants,
or dynamically writable state. An experiment changing a fixed parameter and a
cell changing its own regulatory structure are separately identifiable actions.

Experience-dependent responsiveness, thresholds, or plasticity rates are optional
dynamic state when a model explicitly supplies their update laws. Do not infer
state equivalence from equal visible phenotype. Record model-family identifiers
separately from observer-derived cell-type labels.

## Arrays, capacities, and identity

Use array blocks for each model family, with a consistent species/cell ordering
chosen during the first numerical prototype. A friendly Python cell interface
may refer to an array slot; hot loops operate on the arrays.

JAX compilation favours stable shapes. Allocate explicit cell and edge capacities
and use active masks. Allocate new identities and slots through declared event
rules. Padded entries must have finite neutral values so masked operations do not
introduce invalid arithmetic. Capacity overflow is an explicit condition: stop
with a checkpoint or expand at a host-controlled boundary and recompile. It must
never silently discard cells, contacts, or scientific events.

M1c-a implements separate cell and edge axes, masks, stable IDs, safe neutral
padding, and shape-aware checkpoint/resource checks; passive_pair@1, since removed,
accepted exactly two active cells and one contact. CORE-003 adds species-by-cell amounts,
species-by-edge transfer, and per-cell conversion. Its population and fixed
topology are data, including zero contacts, disconnected cells, and parallel
contacts with distinct IDs. Tiny reference cases extend through five cells;
there is no hard-coded five-cell limit or performance claim. Independent-world
batching is tested only at the process/RHS level, not as a full-run ensemble API.

Stable biological IDs are independent of reusable storage slots. Ancestry records
survive slot reuse and cell death. Track both daughters when division is introduced;
an observer may additionally follow a selected daughter to compare with a source
contract. Group membership and connected components are measurable properties,
with persistent group identities added only when an experiment defines them.

## Communication and space

Begin with a fixed graph, including small stars, pairs, chains, and a regular 2D
layout. Store physical adjacency separately from functional permeability. A
contact can exist while molecular exchange is blocked.

The implemented passive pair exercises this distinction with prescribed opening,
unequal volumes, reciprocal transfer, and exact restart. CORE-003 extends it to
data-defined fixed graphs, independently controlled contacts, and species-specific
permeabilities alongside local reactions. The shipped three-cell chain has no
spatial geometry or neighbour discovery. 2D geometry and the source's
voltage-selective contact remain subsequent extensions.

The communication model computes flux from endpoint state, contact properties,
and molecule-specific rules. For a conservative exchange model, calculate each
edge flux once and accumulate equal and opposite amount changes at its endpoints;
convert these to concentration changes using volumes. Source/sink and charge
accounting must follow the declared model, including external reservoirs.

Preserve the source bioelectric coupling in reference comparisons. A simple
diffusion equation or threshold rule can be a separate reduced model, with its
own validation, rather than an undocumented replacement for voltage gating.

The next spatial extension represents moving cell centres, sizes, and mechanical
forces. Neighbour search supplies candidate physical contacts, then contact rules
determine communication. Extracellular fields use their own grid, with explicit
cell-to-field deposition and field-to-cell sampling. The field grid need not have
one element per cell.

Cellular Potts and vertex representations remain options if cell shape or junction
mechanics becomes central. Their adoption would change the mechanical model and
requires a new design decision.

## Bioelectric interfaces: one physical cell

D018 adds a membrane-to-bath interface before a coupled ionic tissue. A membrane
has its own identity and area; it is not the cell volume, a physical adjacency
edge, or a gate. Begin with one well-mixed cell facing one maintained bath through
one lumped membrane. Bath concentrations, potential, and chemical drive are
explicit external support. Finite extracellular compartments and fields will
own dynamic state and different closure rules when their models are introduced.

The implemented physical cell evolves ion amounts and signed exchange/cycle ledgers.
Its voltage follows an immutable amount/charge/capacitance anchor. Leak and pump
mechanisms read the same stage state and contribute to the same amounts; their
experimental control groups remain independent. Evolving endogenous gates have
primary state with their own kinetics and complete snapshots; algebraic gates
are identified derived mechanisms. Neither is a relabelled prescribed opening.
See [the contract](BIOELECTRIC_CELL_SPEC.md) for
equations, units and external energy assumptions, and the
[production guide](BIOELECTRIC_CELL.md) for its verified bounded implementation.

The existing source-scaled EMT model is not silently wired to physical ions.
Likewise, a new surface mapping alone does not validate a multicompartment
electrical model. Add only exercised interfaces now, with sparse/local mappings
compatible with later graph/field exchange and device-resident execution.

D021's [physical-pair specification](SELECTIVE_CONTACT_SPEC.md) defines the
bounded extension: two effective membrane capacitances to a common bath, one
oriented selective flux/ledger, and one relaxing gate state. The gate continues
evolving during prescribed transport block. It was implemented as
[bioelectric_pair@1](BIOELECTRIC_PAIR.md) in D023, which left with the legacy cleanup. The
[NUM-003 reference](SELECTIVE_CONTACT_NUMERICS.md) requires a new 1 ms/cubic
candidate for its bounded panel, rather than inheriting the single-cell timestep.
Boundary-aware implicit Jacobian probes keep the reference domain explicit.
Production reuses membrane laws, graph scatter and the checked engine, with
explicit gate/transfer state, separate control-array capacities, diagnostic
energy integrals and complete replay. Its read-only sampler checks every cubic's
amount/gate/affine-voltage extrema, not only requested samples. Numerical failures
are refused without clipping. Same-layout replay is exact; changing capacity or
orientation can alter floating reduction order in diagnostics.
The [source map](SOURCE_COUPLING_MAP.md) separately identifies BITSEY's algebraic
gate, upwind junction law and regulatory tracer/clock approximations. Those
choices belong in named models, not global runner exceptions. Future reductions
must test the effect of eliminating gate history as well as fast voltage modes.

## Time and numerical integration

The scheduler coordinates continuous dynamics and discrete events. Start with a
documented coupled update scheme whose numerical convergence can be checked.
Introduce separate process update rates when justified by the model and profiles.
Electrical dynamics, regulation, diffusion, mechanics, and lifecycle events may
require different rates; their ordering and coupling error are part of the solver
contract.

Interventions occur at specified physical times or explicitly named lineage
boundaries. Short cues must not disappear between integration steps. Distinguish
an accepted live endpoint from the last saved sample, and record both times.

M1a uses RK4 for its analytic source/decay fixture. M1b also validates RK4 at step
0.1 for the source's isolated regulatory E/M cases against Radau/BDF references
and the pinned native source. M1c-a validates RK4 for passive exchange with an
event-local bound h*g*u*(1/VA + 1/VB) <= 1 and independent analytic references.
CORE-003 uses h*alpha <= 0.5, where alpha includes reaction loss and every incident
contact's outgoing rate for each species/cell coordinate. Both contributions use
the same stage state. Its [contract](REACTION_TRANSPORT.md#numerical-domain-and-accuracy)
explains this conservative positivity domain and independent matrix/refinement checks.
This does not select the solver for coupled ionic/regulatory dynamics, whose
timescales may make stiffness relevant. Compare that coupled
candidate with trusted CPU references and the source's numerical settings.
SciPy's [ODE solver documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)
describes explicit and stiff-method options for reference work. Fixed-step,
adaptive, implicit, and split methods are candidates to assess, not interchangeable
assumptions. A solver change is an identified numerical variant.

Physical approximation is a separate model choice: an equivalent-circuit model
that omits concentration dynamics is not the same ionic model with a faster
integrator. Declare supported quantities and controls with each model and reject
unsupported requests. Backend selection must not change those capabilities.
NUM-002's [independent reference](BIOELECTRIC_NUMERICS.md) selects a bounded
float64 RK4/5 ms candidate for the physical cell, with interval-correct cubic
Hermite observations. This is not yet implemented in production; existing linear
bounds do not transfer automatically. Its measured local time-scale separation
also motivates later stiff/multirate methods, independently of device placement.

Use float64 as the CPU reference precision and enable it explicitly in JAX.
Reduced precision requires measured error bounds and agreement on scientific
outcomes, especially near commitment thresholds. See
[JAX's precision settings](https://docs.jax.dev/en/latest/default_dtypes.html).

## Growth and renewal

Scripted transfer to fresh prepared cells is the first relay assay. Autonomous
growth and division are a later, separately specified model version.

A biological boundary specification declares what each event retains,
partitions, reconstructs, erases, or leaves external, including contact and
environmental state. It is distinct from a complete numerical checkpoint.
Transplantation, replacement, division, and fragmentation need different rules.
Track original versus newly created material where a renewal claim needs that
distinction; a lineage label alone is not evidence of material replacement.

That extension defines resource uptake, synthesis/degradation, volume growth,
division conditions, state partition, death, and contact formation. Where amounts
are represented, partition parent amounts and volume consistently and derive
daughter concentrations. Account for declared generation, degradation, and external
exchange. Copying concentrations into two full-size cells is not a material
partition model.

A concentration-based source approximation may not conserve every molecular
species. Record that approximation in the reference model; a revised accounting
model needs its own equations and comparisons. Successor creation rules must be
specified independently of the desired inherited label.

## Information access and memory mechanisms

Transport, biological reading, expression, and successor writing are distinct
causal operations even when ordinary kinetics implement several together.
Mechanism contracts state permitted local inputs and output targets. Global
history labels, evaluator targets, and analysis decoders are not automatically
available to a cell or controller.

Communication and slow-state writing may have different access rules. Protected
compartments, limited writing windows, recipient-compatible readers, and
independent versus correlated disturbances are optional experimental mechanisms,
not universal requirements. Record proposals, accepted interventions, and actual
state/material changes separately when a controller can refuse a write.

## Ensembles and the GPU path

*Where this differs from [the modular core](#the-modular-core-d172-d174), that section applies.*

The shared-runner foundations below retain their original model scope. The
[GPU guide](GPU_ENSEMBLES.md) covers later persistent workers, stable random
streams, per-device telemetry and offline planning for up to sixteen GPUs.
Remote scaling and a distributed interacting tissue remain unqualified.

Support both one world with many interacting cells and many independent worlds.
Batch worlds with compatible model structures and capacity shapes; use host-level
orchestration for incompatible experiments. CPU parallelism can first distribute
independent batches with explicit worker and thread limits.

CORE-004/D027 implements the first [independent-world batch](INDEPENDENT_WORLDS.md)
as an explicit world axis and conservative compiled mapping. Each world keeps
its scalar event grid; terminal padding is masked without advancing state or
evaluating a completed world's RHS. The batch wraps ordinary complete scalar
snapshots and model observers, rather than creating a second biological schema.
World IDs namespace cell/contact/bath IDs. This is independent experimentation,
not tissue decomposition or communication between organs.

The original bounded CPU profile separated compilation, warmed execution, host work
and storage. It shows no universal batch speedup: graph batches help at the
largest tested count, while nominal pairs have no overall gain there. Full
histories, host work and output remain visible costs. CORE-005a/D028 adds
[single-world windows](WINDOWED_EXECUTION.md), with a lazy exact grid, every
ordinary interval/observer check, complete ledger/state continuity, and
incremental selected recording. It bounds retained arrays, not biological work
or whole-process RSS. CORE-005b/D029 applies the contract to
[independent cohorts](WINDOWED_WORLDS.md): each execution round consumes each
world's own existing intervals, with prepared parameters and active masks reused.
The full compiled width also handles masked tail slots when the declared work
budget permits, avoiding another executable; tight budgets retain a shorter tail.
A complete cohort checkpoint maps independent local
clocks; it is not a simultaneous organ state. Per-world observers still check
ordinary host results before any round is exposed. Vectorized failure guards,
multi-device semantics and biological exchange still require qualification.

JAX is the shared execution framework. GPU readiness requires checking compiled
control flow, allocation, reductions, random semantics, and device-resident state;
changing the device alone is not a performance guarantee. Keep state on the device
across many steps and transfer selected observations or checkpoints in batches.

Measure compilation separately from warmed execution, synchronise device work
before recording elapsed time, and report both end-to-end experiment throughput
and kernel timings. Local CPU/L4 comparisons cover selected ionic, tissue and assembly families;
see [GPU execution](GPU_ENSEMBLES.md) and Progress for their scope. Changing-population
physics and Jupiter measurements need separate qualification. A speedup on one
workload is not a general performance guarantee.

Differentiation is optional. Smooth intracellular or transport components may
support inference, while discrete division, topology changes, and classifications
need separate treatment. Gradients are not required to run the first experiments.

## Randomness, replay, and checkpoints

Make randomness explicit and separate initialisation, process noise, partition,
intervention, and analysis streams. Record how stream keys derive from run,
replicate, lineage, and event identity. Paired comparisons explicitly declare which
draws are shared and which are independent. Diagnostics must not consume the
simulation's random stream.

A checkpoint contains all state needed for continuation, including pending inputs,
identities, environment, numerical scheduler/integrator state, and random state.
Fixed parameters and model code are referenced by immutable versions or hashes.
Restart verification compares uninterrupted and restored execution under a pinned
backend. Cross-device verification uses specified numerical tolerances and, for
stochastic models, distributional and endpoint comparisons; bitwise equality is
not presumed.

### Allocation-independent linear algebra (D190, built 16 November 2026)

**The finding.** A CPU run's bits follow its CPU allocation through one channel: OpenBLAS's thread
count, which defaults to the CPUs in the process's affinity and cannot exceed them. Two OpenBLAS
builds are in play:
- numpy's, for host work: the binding-time Cholesky of `surface_field.bind`, host solves and the
  analysis tools;
- scipy's, which jaxlib's CPU LAPACK kernels call from inside compiled programs: @3's IMEX step
  factors the full node-space operator every step, plus the triangular and offset solves.

On the 825-node world (`item3/` in `/mnt/workspaces/Cells/core-fixes-20261116/`):
- The binding's factor has two bit classes, one at 1 thread and one shared by 2, 3, 4, 8 and 16.
  The jitted Cholesky gives the same two classes.
- A 20-step run is bitwise equal on 1 CPU and on 4 CPUs with both libraries at 1 thread, so XLA's
  own threading moves no bits there.
- Setting one library to 1 thread and the other to 4 gives a third and a fourth result. Both
  libraries matter.
- A 1-CPU allocation cannot reach the multi-thread class.

**As built (D190, the lean form the user ruled): the engine sets both libraries to 1 thread.**
- `execution/blas_threads.py` loads scipy's LAPACK first, since jaxlib loads it only at its first
  LAPACK call and a limit reaches only loaded libraries. It then sets every loaded BLAS to 1
  thread through threadpoolctl (BSD, `threadpoolctl==3.8.0`).
- The import pin is taken in `cells/__init__.py`, at `import cells` (D198, R6'). Since the retire
  batch, no held law pins that file's bytes. Every engine path imports the package before any of its
  modules, and so before any linear algebra: parse, the models, the runs and the analysis tools.
  A BLAS that loads later starts at 1 thread, because OpenBLAS
  reads `OPENBLAS_NUM_THREADS` when it loads and both builds honour it. One already loaded, when
  numpy came first, is set at once. So a light module such as `cells.execution.continuity`, imported
  fresh, still loads neither numpy nor scipy (its own rule).
- Each run entry point (run, run_windowed and iter_windows,
  run_batch, run_batch_windowed and iter_batch_windows, run_vector_windowed and
  iter_vector_windows) pins again, then reads the counts back. It refuses the run (ConfigError)
  if any loaded BLAS is not at 1, or if none is found.
- The run manifest (`io.write_run`) and the results baseline's environment record every loaded
  library's API, prefix, version, kernel architecture and thread count, with threadpoolctl's
  version.
- The runtime identity that restores compare is unchanged, so a checkpoint written before the pin
  is not refused for it.
- Bits stay machine-dependent: OpenBLAS picks kernels by CPU type.
- Not built, as ruled: a scoped pin that restores the caller's setting, its reference count and
  lock, and a check at every window boundary. A change made inside a run, between its entry and
  its end, is not seen.
- Measured with the pin, without OPENBLAS_NUM_THREADS: the 825-node world's binding, jitted
  factor and 20-step run are bitwise the same on 1, 2 and 4 CPUs, in the 1-thread class
  (`/mnt/workspaces/Cells/core-pin-20261116/`).

Alternatives (not taken):
- A ctypes shim on the two builds' exported setters avoids a dependency but supports only these
  builds.
- An `OPENBLAS_NUM_THREADS=1` launcher policy fails open when a launcher forgets it.
- An order-fixed factorization of our own would be slower and would move every factored world's
  bits.

**Effect on the recorded baselines.**
- G1 (c1's save, 1-CPU shards) is already in the 1-thread class: unchanged.
- crossrev's records were made on 2 CPUs. Only the bindings of S825_closed_water and
  S825_event_free change, as the 1- and 2-CPU runs showed; they are renewed once. The kinds pair
  is unchanged.
- Trajectories recorded with more than one thread are not reproduced bitwise afterwards. They
  were not reproduced across allocations before either, and their verdicts, judged at
  tolerances, stand.
- Pinning at 2 instead would keep crossrev's records but change G1's 825-node worlds, and a 1-CPU
  allocation cannot reach 2 threads.

**Cost.**
- One-core runs, the measured profile in [the field-solver note](FIELD_SOLVER_INTERFACE_DESIGN.md)
  §2 and GPU runs (device LAPACK) are unchanged.
- Multi-core CPU runs of large worlds give up the threaded speedup of the per-step factorization:
  21 ms of the 825-node world's 91 ms one-core step.
- Multi-process CPU work, such as the tier runner and batch shards, no longer oversubscribes
  cores.

## Experiment records and storage

Preparation is an explicit experiment phase or preceding run, with its full
initial conditions, controls, duration/stopping criteria, and resulting checkpoint.
There is no silent equilibration on resume or branch. Preserve the prepared
state, external support, electrical anchors, and earlier accounting history;
re-preparing a cell would otherwise erase precisely the history a memory assay
may intend to challenge. MODEL-003 preserves this physical state/history through
run/checkpoint protocols; a general preparation API is not implemented.

Each run records the model and observer versions, code revision and local source
hashes when needed, resolved configuration, units, seeds, software versions,
device, precision, solver settings, stopping rules, and source-checkpoint hashes.

Store dense state in an array format such as HDF5 or Zarr and event/summary tables
in Parquet, with a readable JSON manifest. The exact storage choice is open.
M1a uses small numeric NPZ arrays plus JSON for a complete prototype snapshot;
that does not fix the production storage backend.
Use configurable observation rates plus complete restart checkpoints to control
output volume. Preserve continuous state and identity alongside derived labels.

Observation interpolation has its own accuracy contract. D019's reference found
that linear samples could miss the voltage target despite accurate RK4 endpoints.
The physical model now uses an explicitly identified cubic Hermite policy,
with endpoint derivatives evaluated under each interval's held controls. At an
event, left and right derivatives can differ. The existing four models retain
their verified linear policy; sampling remains read-only in either case. A shared
checked-RK4 path accepts a pure model-domain predicate, checks trials/endpoints,
and refuses failed runs without publishing repaired trajectories. Membrane
capacity is budgeted independently of cell/contact storage.

Run status distinguishes numerical failure, capacity exhaustion, biological death,
scientific negative outcomes, and a completed finite horizon. A scientifically
negative result can be a correctly completed experiment.

## Analysis and viewing

The viewer consumes snapshots or a bounded stream; rendering does not determine
simulation time or random draws. Initial views should show cellular state,
voltage, functional contacts, environmental fields when present, and selected
lineage histories. Interactive interventions go through the experiment interface
and are recorded for replay.

Python notebooks and optional R analysis read the same saved artifacts. Observers
include retention, transmission, episode coherence, rewrite cost, recovery, and
resource use. Phi-r or other information measures can be added with their complete
sampling and estimation contracts.

An observer specification fixes read access, coordinate frame, spatial and
temporal scale, thresholds, null/positive calibration, and version. Observer
frequency must not change the dynamics. Preserve continuous readouts alongside
classes and allow trajectory/challenge signatures instead of assuming a finite
catalogue of cell or tissue identities. Any feedback use of an observation is an
explicit controller with declared access and cost.

Cost outputs distinguish simulated material/energy assumptions, sensing and
reconstruction requirements, shared machinery, and actual computation/storage.
An inherited payload size alone is not the cost of the mechanism. Restoration,
reprogramming, and environment-specific benefit have separate endpoints.

Reduced models for larger scales must be validated on held-out trajectories and
interventions. A reduction that preserves current E/M labels but loses commitment
is insufficient for memory experiments.

**Run-view output (D154, requirement).** Every experiment must eventually be visualizable.
- One shared run-output path writes a view record beside each run's `definition.json`. Drivers
  do not each write their own.
- The record holds:
  - geometry in physical units;
  - stable entity identity for every recorded array's columns;
  - each array's name, unit, axes and time base;
  - events with their entity ids;
  - each layer's representation: simulated, modelled in aggregate, or prescribed;
  - the scale.
- It is kept out of the definition, so definitions, bindings and crossrev are unaffected.
- Its exact form is in the design note, [RUN_VIEW_DESIGN.md](RUN_VIEW_DESIGN.md) (proposed). The
  writer is on main since 16 November (`src/cells/records/run_view.py`).

## Technical references

- [JAX compilation and functional constraints](https://docs.jax.dev/en/latest/notebooks/Common_Gotchas_in_JAX.html)
- [JAX JIT compilation and changing shapes](https://docs.jax.dev/en/latest/201/jit.html)
- [JAX float64 configuration](https://docs.jax.dev/en/latest/default_dtypes.html)
- [JAX explicit state](https://docs.jax.dev/en/latest/stateful-computations.html)
- [JAX structured array state](https://docs.jax.dev/en/latest/101/pytrees.html)
- [SciPy integration reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)

These references informed the initial design review. Exact supported versions
and target-device compatibility will be checked when the environment is pinned.

## Historical implementation notes

These September build notes retain their original statuses, versions and test
counts. Read the implementation context above and Progress for current coverage.

Design baseline: 2026-09-07. Python and JAX are selected. The structures below
describe the target architecture. The one-cell engine, isolated regulation,
passive two-cell contact, local-reaction/graph-transport composition, one
physical membrane/bath cell, a gated physical pair and a nominal source-compatible
EMT pair are implemented. Version 0.8.0 adds independently clocked homogeneous
world batches through those same models. Version 0.9.0 adds bounded single-world
windows and selectable recording on the shared numerical path. Version 0.10.0
extends bounded execution to independently clocked cohorts, with prepared
parameters and device carry reused across rounds. Version 0.11.0 adds a
[data-defined multispecies membrane](MULTISPECIES_MEMBRANE.md) through this same
execution path. Version 0.12.0 adds a [state-bearing membrane channel](VOLTAGE_GATED_MEMBRANE.md)
with independent numeric channel capacity, retained m/h state and a separate
transfer ledger; its [bounded production acceptance passes](../reports/CORE007_ACCEPTANCE.md).
Version 0.13.0 adds a separate [physical ionic graph family](PHYSICAL_IONIC_GRAPH.md),
composing those local laws on heterogeneous cells and sparse state-bearing
junctions. Its [production acceptance status](../reports/CORE008_ACCEPTANCE.md)
is tracked separately from the frozen reference qualification.
Version 0.14.0 adds a [finite shared extracellular family](FINITE_EXTRACELLULAR.md):
explicit inside/outside inventory increments, membrane-to-outside ownership and
closed ionic energy accounting. Its [formal acceptance](../reports/CORE009_ACCEPTANCE.md)
passes through the same runner, solver, windows and cohorts; all 3616 maintained/
historical regression tests and release checks pass.
Development version 0.15.0.dev0 adds the separate [passive spatial family](SPATIAL_EXTRACELLULAR.md).
It uses independent cell/outside/membrane/face axes and a same-stage field module
without changing the shared integration, window or checkpoint algorithms.
Formal CORE-010 release acceptance is still open; see Progress for actual tests.
Longer source switching/relay assays,
lifecycle, tissue, organ, and multiscale execution remain planned. Current delivery
status lives in [Progress](../PROGRESS.md); rationale lives in
[Decisions](DECISIONS.md).

Current architecture update, 2026-09-09, D045: the [first pilot is closed as
descriptive](../reports/BIO003_PILOT_CLOSEOUT.md). The accepted target is now
[BETSE-level scientific coverage](BETSE_CAPABILITY_ROADMAP.md) through Cells'
own [multiscale/parallel execution contracts](MULTISCALE_EXECUTION_ARCHITECTURE.md).
Those documents separate biological mechanisms, resolution, numerical coupling
and device placement, and map 17 feature families to staged work. D046 now
delivers SPEC-005's [one-cell multispecies contract](MULTISPECIES_MEMBRANE_SPEC.md)
and [independent instantaneous reference](../reports/SPEC005_DESIGN_CHECK.md).
Explicit charge, amount anchors and role-bound transport resolve into immutable
aligned tuples outside production. D047 / [NUM-006](../reports/NUM006_REFERENCE.md)
now qualifies short trajectories with independent methods and a bounded RK4/cubic
candidate. D048 / CORE-006 now implements those bindings as numeric JAX layouts
and a complete new checkpoint schema; [production acceptance passes](../reports/CORE006_ACCEPTANCE.md).
Per-species memory and control extents are explicit, while old model timestep
limits stay unchanged. Historical Na/K/Cl, single-membrane and CPU/RK4 restrictions remain versioned model
limits, not permanent engine requirements. New fields, solvers and GPU modes
are planned, not already supported; historical implementation notes below retain
their original scope.

D049 / [SPEC-006](VOLTAGE_GATED_CHANNEL_SPEC.md) now specifies one state-bearing
Kv1.5-style membrane channel with two retained gates and one separate transfer
ledger. Its [scalar gate and instantaneous coupling checks pass](../reports/SPEC006_DESIGN_CHECK.md);
that specification alone is not a production extension. Geometry, abundance,
gate kinetics and external availability remain separately owned. Gate and amount
derivatives must share the same solver-stage voltage; the existing timestep is not inherited.
D050 / [NUM-007](../reports/NUM007_REFERENCE.md) now qualifies the coupled reference
at 0.5 ms RK4 with checked cubic observations and a passing 0.25 ms refinement.
Separate ionic/channel histories, real-stage gates and unsampled cubic extrema
are checked. CORE-007 now implements the separate CPU/JAX identity and passes
complete replay/cohort acceptance. Shared runner/integrator/I/O and earlier
model equations remain unchanged; multirate/device claims still need their own evidence.

D052 / [SPEC-007](PHYSICAL_IONIC_GRAPH_SPEC.md) now composes those local references
on a data-defined physical ionic graph. [Instantaneous checks pass](../reports/SPEC007_DESIGN_CHECK.md)
for independent/disconnected cells, unequal pairs and shared-recipient stars.
The first closure uses one common maintained bath and diagonal capacitances;
each edge owns one reciprocal flux, gate and dissipation history, and each cell's
membrane is evaluated once. That design reference alone was not a tenth production family.
[NUM-008](../reports/NUM008_REFERENCE.md) now qualifies short coupled paths and
complete histories, selecting 2 ms RK4/cubic with passing 1 ms refinement only
on its twelve-case panel. CORE-008 now explicitly maps the cell-/edge-major
reference to species-major numeric state, with independently padded cell,
membrane, channel and junction extents. Accepted 0.12.0 is archived. The shared
runner/integrator/I/O are unchanged; its CPU/JAX, checkpoint, window and cohort
acceptance is separate. Current model timesteps remain versioned.

D055 / [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md) now specifies and independently
checks one finite shared extracellular compartment, without changing production.
The outside owns real species amounts and opposing membrane charge. Its zero
potential is a gauge, not an electrode or an infinite reservoir. Every membrane
transfers into/out of that one inventory; cell-cell junction transfers cancel
internally. The energy model includes inside and outside ideal chemical energy
and each membrane capacitor once. The old fixed-bath grand potential is not
silently reused with time-varying outside concentrations. A shared outside makes
even junction-disconnected cells one interacting world. NUM-009 supplies the
separate qualification of ten-field trajectories, charge constraints and
depletion; CORE-009 adds a new production identity through the existing engine.

D056 / [NUM-009 v1](FINITE_EXTRACELLULAR_NUMERICS.md) makes immutable initial
anchors and numerical amount increments explicit. Its dependent-outside reference
failed exact blocking under continuing internal exchange. D057 /
[v2](FINITE_EXTRACELLULAR_NUMERICS_V2.md) therefore integrates every inventory
explicitly in both reference and candidate. Only the implicit Jacobian probe
directions are conservation-tangent; no state is projected or reconstructed from
other compartments' rounding residuals. The dense reference Jacobian is not a
GPU execution design. Both paths expose the same ten physical fields and full
histories. D058 / CORE-009 maps those anchors and coordinates deliberately to
readouts/checkpoints in a separate CPU/JAX family, without changing older model
semantics or interpreting a shared outside as independent per-cell worlds.
Both inventories remain explicit
solver and checkpoint state; membrane transfers update their two owners, while
junctions never enter the outside reduction. Formal reference/restart/branch/
window/cohort acceptance and release checks pass; see [Progress](../PROGRESS.md).

D059 / [SPEC-009](SPATIAL_EXTRACELLULAR_SPEC.md) now specifies spatial outside
inventories and an independently checked instantaneous electrical closure.
The minimum fixture is one cell plus near/far outside volumes, including a bulk
volume with no membrane. Capacitance-component charge compatibility and bulk
current continuity determine relative potentials; only one world reference is
an arbitrary gauge. Owned log-mean electrodiffusive faces preserve reciprocal
amount transfer and instantaneous passive energy dissipation. The small dense
NumPy design reference is not production storage or a time integrator.
[NUM-010](../reports/NUM010_REFERENCE.md) now separately qualifies short coupled
trajectories, physical field residuals and one line-grid refinement path before
CORE-010; old production, timestep bounds and maintained baths are unchanged.

D060 / [NUM-010](SPATIAL_EXTRACELLULAR_NUMERICS.md) fixes the complete numerical
contract before that implementation: every compartment increment, each membrane/
bulk-face transfer history and each interface's dissipated energy are explicit.
The instantaneous field block consumes the current stage's inventories and
returns gauge-fixed potentials plus physical residuals. Potentials are derived
again for observations, not interpolated as independent state. Immutable amount
anchors, the absolute control clock and every history must survive restart.
D061 / [CORE-010](SPATIAL_EXTRACELLULAR.md) now implements this passive scope in
the shared engine, with separate explicit arrays for cells and outside owners.
Its versioned field solver assembles a small dense temporary Kirchhoff matrix
from the saved edge list. The quadratic workspace is budgeted before allocation;
this is a bounded CPU implementation, not a scalable sparse or GPU solver.
Existing pumps, channels and junctions need new coupled spatial qualification
before they can be composed into it. The full production artifact/audit gate is open.

The target now extends to a whole organ and later interacting organs, composed
from data-defined model instances. Current executable worlds contain an isolated
cell (synthetic, regulatory, or physical bioelectric), a passive pair, or a fixed
graph of two-species reactive cells, two physically gated bioelectric cells,
the separately defined nominal source-compatible EMT pair, or a heterogeneous
physical ionic graph in a maintained bath or one finite shared outside. The
development spatial family adds passive finite-volume extracellular fields, not
spatial tissue mechanics, a reduced region or an organ preset.
See [Multiscale design](MULTISCALE_DESIGN.md) for composition, scale coupling,
and the future large-GPU computational-multiscale note, and
[First build](FIRST_BUILD.md) for the bounded M1a implementation and
[Isolated regulatory reference](EMT_REFERENCE.md) for M1b, and
[Passive contact](PASSIVE_CONTACT.md) for M1c-a, followed by
[Reaction and transport](REACTION_TRANSPORT.md) for CORE-003, and
[Physical cell](BIOELECTRIC_CELL.md) for MODEL-003 and
[Physical gated pair](BIOELECTRIC_PAIR.md) for MODEL-004, and
[Source-compatible EMT pair](SOURCE_EMT_PAIR.md) for MODEL-005.

The user's 2026-09-08 clarification makes development engineering-led:
exercise local-reaction/transport composition before the source-specific coupled
model. That [engineering gate](ENGINEERING_GATE.md) is now implemented and verified.
Engineering, numerical, and scientific checks remain separate. The accepted
[BETSE review](BETSE_DESIGN_REVIEW.md) refines the next step to an explicit
[one-cell physical contract](BIOELECTRIC_CELL_SPEC.md), then source-selective
coupling with its own unit/clock correspondence. The physical cell and pair are
now implemented. D021 defines the physical-pair design and instantaneous source
map; D022 qualifies independent coupled numerics; D023 implements the physical
pair against that frozen reference.
D024/SPEC-003 pins a distinct [complete source-compatible profile](SOURCE_EMT_PAIR_SPEC.md)
with six evolving coordinates per cell, separately typed fixed context and
reconstructed source plotting caches. Its independent full RHS matches native
instantaneous probes. D025/NUM-004 now qualifies the bounded coupled trajectories
at 0.01 nominal units with checked cubic observations, including explicit native
clock refinement; see the [numerical contract](SOURCE_EMT_PAIR_NUMERICS.md).
MODEL-005/D026 now implements this [nominal pair](SOURCE_EMT_PAIR.md), with separate
ionic/regulatory state and histories, a reusable route-axis control family,
the existing pure EMT component and graph scatter. Runner, RK4, observations and
snapshot machinery need no source-assay branches. Exact event splitting remains:
source equation compatibility does not require copying legacy clock overshoot.
A source assay is a client of the engine, not a special execution branch.

D030/SPEC-004 now freezes [E02-SW1](E02_SWITCHING_PROTOCOL.md). Its selected
three-cell star exposes the next model limitation: source pair capacity is
padding, not a general communicating graph. Qualify a separate fixed-graph
reference first (NUM-005), then extend source composition with local rates once
per cell and independently controlled, reciprocal per-edge fluxes at shared
stages. No duplicated pair solvers, degree-dependent retuning, clamped donors
or assay predicates in the runner. The design adds no production mechanism;
cell/contact count and eventual organ definitions remain data choices.
NUM-005a/D031 now checks this [fixed-graph composition independently](SOURCE_EMT_GRAPH_REFERENCE.md):
explicit edge loops rather than production scatter, full source derivatives,
typed passive histories and pair reduction. It is reference-only; the shared
production engine and its seven model families are unchanged.
NUM-005b/D032 adds [bounded implicit reference integration](SOURCE_PREPARATION_REFERENCE.md)
outside production: one live solver across recording chunks, complete anchored
state/histories, full-interval polynomial checks and separately owned preparation
observers. The two 500-unit preparations now pass the numerical/packet gate.
Long connected-path and candidate qualification remain before a production graph
profile. Complete reference state snapshots do not promise exact adaptive-solver
restart or change production checkpoint semantics.

NUM-005c1/D033 adds a separately versioned [long-reference recording layer](SOURCE_GRAPH_PATHS_REFERENCE.md)
without changing the earlier accepted numerical sources: lossless compression,
exclusive outputs, exact prepared primary/context imports with new zero ledgers,
and bounded full-panel comparisons/readouts. Storage policy cannot alter solver
paths or decide biological outcomes. These reference gates still do not select
the long-time production method; the later RK4 and preparation-sensitivity gate
remains explicit.

D034 adds [registered continuation and immutable reference imports](SOURCE_GRAPH_CONTINUATION.md):
session-qualified attempt identities, shared artifact quotas, exact ordered
remaining inventories and composite provenance. A stopped adaptive path is
restarted from its exact phase anchor under a new identity, not resumed from a
physical snapshot. Reusing audited evidence cannot bypass a failed accuracy
gate. The [candidate preflight note](E02_CANDIDATE_PREFLIGHT.md) keeps bounded
recording and full checking explicit before long-time RK4 work.

D035's [single BDF refinement](E02_BDF_REFINEMENT_A1.md) introduces explicit
multi-root reference readers with bounded batches and deterministic cleanup.
Numerical evidence can be compared across immutable attempts without copying
their files or modifying old solver modules. Diagnostic agreement and original
case qualification remain distinct, with acceptance rules fixed before a trial.

D036's [A2 panel](E02_REFERENCE_POLICY_A2.md) separates the accuracy contract
from solver settings and evidence locations. A per-case manifest identifies the
selected trajectories, their settings, the comparison supporting acceptance and
their observer output. Imported evidence can remain in several immutable roots;
new readouts do not require copying trajectories or overriding global solver
configuration. The three-input observer adapter retains the original arithmetic
and is tested array-for-array against the old reader. The explicit mixed-setting
panel preserves failed attempts, shared quotas and independent numerical checks.

D037's [bounded RK4 candidate](E02_CANDIDATE_ENGINEERING.md) separates accepted
solver state from recording windows and reference-comparison batches. Its
fixed-control checkpoint carries complete increments, passive histories, anchor,
context, case identity and the original global grid/source/runtime identity.
Recording widths and exact accepted-boundary restarts cannot reset those clocks
or histories. Short profiles verify this separation without changing production.

The [complete-path measurements](../reports/NUM005C2A_CANDIDATE_ENGINEERING.md)
show why bounded memory alone is insufficient: derived comparisons, cubic guards
and evidence recording are substantial costs, and retained disk output still
grows with the number of steps. D038's [readout adapter](E02_DIAGNOSTIC_OPTIMIZATION.md)
now snapshots static graph/control data and batches the observation axis within
explicit array bounds. Readout policy is per instance; neither a global patch
nor an integration-kernel substitution is needed. Frozen scalar evaluation
checks the batch implementation, while ordered full-path hashes check that
the optimization cannot change the accepted or sampled state.

The [compact-evidence proposal](E02_COMPACT_EVIDENCE_DESIGN.md) keeps output
retention separate from complete restart state. Lossless redundancy removal is
the first proposed prototype; checkpoint/replay certificates would require a
separate audit-policy decision and measured replay costs. No compact policy is
implemented by D038. Bounded windows, batching, output retention and future
spatial coarsening remain distinct choices with separate evidence requirements.
These are execution-layer concerns, not reasons to alter the source equations
or assume that GPU porting alone makes the full workload feasible.

D039's [lossless evidence prototype](E02_LOSSLESS_EVIDENCE.md) separates the
numerical identity from recording policy. Its method-specific RK4 basis stores
all stage slopes and complete window endpoints, then reconstructs redundant
accepted states and cubic rows exactly. The codec is tied to a named RK4/schema
revision, not an assay branch; it must not be applied to a different solver by
assuming that its algebra is interchangeable. This remains a fixed-graph
reference implementation, not a production-wide storage migration.

D040's [reference-backed comparison records](E02_COMPARISON_RECORDING.md) extend
that separation without changing the numerical runner: retain every sample
clock/flag and digest, reconstruct complete sampled states from pinned trajectory
dependencies, and validate those dependencies at the explicit reader/restart
boundary. This is a storage dependency graph, not biological coarse-graining.
The candidate payload precedes comparison records; the checkpoint commit binds
their index afterwards, avoiding circular hashes. Complete carries remain
separate, and older low-level readers cannot certify the new dependency policy.

D041's [immutable scalar evaluator](E02_INTEGRATION_EVALUATION.md) keeps fixed
configuration preparation separate from explicit dynamic state and histories.
Only state-independent factors are cached; all numerical guards still run.
Unlike lossless recording policy, evaluator policy belongs to numerical identity:
finite exactness tests do not authorize cross-evaluator restart. Independent
auditing recomputes every recorded complete stage slope with the frozen equations.
The measured 13.9% RHS-time reduction becomes only 2.9% of checked runtime and
0.9% with per-profile auditing, illustrating why future GPU/multiscale work must
measure validation and evidence costs separately from arithmetic throughput.
These are short CPU reference measurements, not a production or GPU benchmark.

Checkpoint publication is also explicit: numerical validation, payload and
comparison completion precede the hash-linked commit record. Failed-window
dumps are diagnostic evidence, never implicit restart state. Closed committed
prefixes retain complete clocks/state/source lineage across policy or width
changes; unclosed-process recovery and distributed durability are separate work.
The short prototype retains all comparison samples and keeps existing metadata
scans visible in its resource measurements.

D042 / [BIO-001](BIOLOGICAL_BENCHMARK_001.md) adds a measurement-boundary design
requirement, not new production state: distinguish the cell's biological
environment from the recording apparatus, and explicit transported ions from
maintained background charge. A whole-cell pipette recipe is not an intracellular
free-ion measurement. The first experimental dataset includes divalent bath
charge that the Na/K/Cl-only closure cannot represent unchanged. Future support
requires a versioned boundary contract with accounting and numerical checks;
no hidden electrolyte correction or assay-specific solver branch is permitted.
Optimization and GPU work are now paused in favor of this experimental track.

D043 / [BIO-002](CONDITIONED_VOLTAGE_REFERENCE.md) implements a static conditioned
endpoint comparator outside production Cells. Pure two-point algebra is separate
from the source-data adapter, uncertainty propagation and report rendering.
The evaluation voltage enters only a post-prediction comparison. Effective
curve coefficients are not a full biological state or uniquely identified
membrane parameters. Bath background charge and omitted current paths are
explicit assumptions; no production schema or charge guard is weakened.
The result does not add an eighth model, a time integrator or a dynamic pipette
boundary. Those would require their own reusable, versioned contracts and
numerical qualification after experimental boundary/uncertainty review.
