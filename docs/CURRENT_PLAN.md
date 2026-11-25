# Current plan (adopted 12 November 2026)

Status: **adopted 12 November 2026 ([D145](DECISIONS.md#d145-the-current-plan-is-adopted-with-the-l4-now-and-gh200-next-week)).**
GH200 access was expected, at adoption, by the end of the week of 16 November, and the L4 is used
fully meanwhile. The
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

## Status on 17 November 2026, and the core-completion lane (D214)

**Landed on main, 17 November:**
- **The law and operator registries,** the static model table and family operators (seam F).
- **The declarations manifest `cells.declarations@2`** with its format page, and the first
  plain-language library pages (D203).
- **The run-view writer's reach,** with `local_species_reactions@1` declaring its view, and the
  relationship tables `cells.relations@1` (D200, D202).
- **FR-4's and FR-5's registered protocols,** judged and passed: 21 of 21 and 51 of 51 criteria,
  tags fr4/fr5-v1-qualified-2026-11-17, qualified within their scope.
- **GARD's G1** (D192, D197) and the gap-junction replication's first stage (D207): development work,
  not judged.
- **FR-19's fix:** the passive routes' heat-share floor.

**Still incomplete, kept visible until their acceptance cases pass:**
- **The module system's stage 1** (D185): one separately installed module that registers, builds,
  runs, contributes checks and observations, and checkpoints and resumes, with Cells' source
  unchanged.
- **Executable levels of detail:** D175's four fields are refused at registration.

**Gate wording.** A gate passes when it shows **0 changed against the recorded baseline**. That is
not the same as all tests passing. In the baseline, 35 of tier 1's 353 rows and 5 of tier 2's 161
rows have failing or erroring tests, and there are 5 collection errors.

**The core-completion lane (D214).** An external adviser's architecture follow-up, reviewing main
b661cd1a, was forwarded by the user. Their instruction: "two fixes then backlog".
1. **Two extension-boundary fixes, now** (branch `core-boundary-checks`). They are an exception to
   D195's "code follows move 2".
   - **A kind writes only its own resolved, declared fields.** This applies to its initial values,
     derivatives and control outputs, with planted foreign-write refusals at construction and
     tracing boundaries.
   - **More than 31 model checks are refused at admission.** The vector failure mask packs them into
     an int32 from bit 1. The last supported and the first unsupported configurations are tested.
2. **The shared physical interfaces through their consumers.** These are seams A (cycles), B
   (populations), C (binding), D (heat booking) and E (finite fuel's core part; moieties), each
   with one mechanism owner (`docs/CORE_SEAMS_DESIGN.md`).
   - Seam C takes the buffered-state predictor correction (§17), with P1's convergence and ledger
     checks rerun.
   - **New acceptance case, unestimated:** the first finite-fuel acceptance shows depletion,
     regeneration and recovery through shared ATP, ADP and Pi, with a consuming pump.
3. **The module system's stage 1, with one installed external module** (D185,
   `docs/MODULE_SYSTEM_DESIGN.md`). New to the lane, unestimated.
   - The built model freezes the component resolution it used, as the AGENTS.md provenance rules
     allow: no per-call or bytecode attestation, and no hash literals.
   - Unused-module invariance extends to a world that uses a real kind.
   - **Low priority** (the user, D214), and with it D195's question of a public stability promise.
4. **The minimal static level-of-detail contract.** D175's four fields are designed together for
   fuel, machines and mitochondrial hosts. Requirements are in ARCHITECTURE.md, "Levels of detail".
   - Finite fuel is the first executable consumer: a reduced regeneration closure against a small
     detailed network, with the envelope and error budgets declared first, and an out-of-envelope
     refusal.
   - Selection is fixed before a run.
   - The executable comparison is new and unestimated.
   - **The user agreed** that it comes before machines' M1a (D214).
5. **General composition through D191's declared-read rule:** current volume, area, activity masks
   and population capacity, proved with an independent additional operator. Explicit refusals stay.
6. **The packed GPU qualification on the merged core** (§ "Status on 14 November", item 4;
   `docs/PACKED_GPU_EXECUTION_DESIGN.md`).
   - It reports packed repeatability, packed against lone agreement, and throughput, each
     separately, with scales and limits frozen before held-out judgment.
   - Ensemble throughput, coupled-world size and biological duration stay separate milestones.
   - It needs the L4, so it is announced to the visualizer and kept off demo hours. New to the lane,
     unestimated.
7. **Precise reporting.** This section is the refresh. Owed at the final-tree checkpoint: the D172
   restructure's G3 negative controls and G4 measurements (compile time, memory, end-to-end time),
   as recorded above and in PROGRESS.

**The order:**
1. The two fixes.
2. The retire (D198) and move 2.
3. The pass, with about four owners (D213). Item 4 runs ahead of machines' M1a.
4. Item 6, as the L4 allows.
5. Item 3 last, at low priority.

## Status on 14 November 2026, and the working order (D156)

Levels: *implemented* (on main), *guarded* (tests, crossrev and frozen-model guards),
*numerically qualified* (a registered protocol passed), *judged* (used in a registered
experiment).

| Item | Level today |
| --- | --- |
| The composite: @3 plus operators, the ownership and energy-role contract, bound step checks | Guarded. Numerically qualified on CPU through frozen-model guards. GPU agreement by tolerance on the L4 (14 November): W1 and W2 pass, and G2-Q1 passes Q1–Q6; Q7, which is bitwise, failed there because of the L4's own run-to-run nondeterminism at 825 nodes. Judged again alone under the deterministic flag (16 November), Q7 passed, in that declared mode only (D181), and the landing's L4 block passed under the flag (PROGRESS). Judged in E07-v1 (`resolved_pump_replacement@1`) |
| Water plus replacement@2 with the entity volume ledger | Implemented and guarded; not qualified on the heredity sheet |
| Lifecycle operators: S2 membrane state, S3 insertion and lumen, Rm1 injection, S5a partition and bridge closure | Numerically qualified, against independent references for S5a. Division is prescribed; nothing yet judges endogenous proliferation |
| Secreted-species transport (D150 v1) | **Numerically qualified** (14 November): the held sphere with decay, the faces with exact radial conductances and turnover's clearance. Exchange is qualified within FR-1's scope line since FR-1's judged acceptance (18 November, `fr1-v1-qualified-2026-11-18`). Production and the occupant rule are guarded only, through the Q5 tests |
| Reactions on the shared inventory (D152 v1) | **Numerically qualified** within MG0c's scope (15 November): the judged run of `mg0c-turing-v1` passed 55 of 55, with the guards and every kept control. CPU only |
| Checkpoint continuity (D153) | Implemented and guarded for CPU vector windows and on the GPU (the extension landed on 14 November) |
| Phase markers | Start, completion and failure records implemented (`execution/phases.py`'s `Recorder`, 15 November) |
| Run-view output (D154) | Design note proposed (15 November, [RUN_VIEW_DESIGN](RUN_VIEW_DESIGN.md)). The operator contract's view interface landed with D172's round (16 November); the operators' declarations and the writer (`cells.run_view@1`) merged into main the same evening, with FR-11's first looping development run (PROGRESS) |
| Coupling out of the inventory (D155, scoped by D156) | **Numerically qualified** (15 November): the judged protocol passed, with second order against independent references for reciprocal feedback (A4) and a species setting a channel (A5). CPU only, within its scope line |
| Excitable tissue (D155) | Design accepted narrowly, for M1 and M2 on @3 (D170). The generic cell is 0.01 F/m² (candidate A), on post-hoc probe evidence; the junction floor is provisional until M1's sheet runs. The human law set is brought forward as its own lane (D183, 16 November). Its [design note](HUMAN_CARDIAC_LAWS_DESIGN.md) is proposed and on main since 16 November, and its choices are recorded in D184: O'Hara–Rudy 2011's endocardial cell, with the whole-cell comparison approved. Engine work starts after the landing |
| Feature requests (D157–D167) | FR-9's cap of 16 landed. FR-1, FR-3 and FR-10 designs accepted (D169). FR-10's milestones 1 and 2, FR-1's milestone 1 and FR-3's milestone 1 landed (15 November). FR-4 and FR-5's design note is proposed. FR-4's kinds (the transporter with its proton pump, the rapid proton buffer and the passive routes with the proton leak) landed with D172's round (16 November), and FR-5's source kinds, refusal 4 version 1.2 and refusal 5 version 1.1 merged with fr45-next the same evening, all for development, not judged. Their protocols, `fr4-acidification-v1` and `fr5-transfer-v1`, are registered and judged (17 November 2026): both passed, 21 of 21 and 51 of 51 judged criteria. FR-10's protocol, `fr10-dose-schedule-v1`, is registered and judged the same night: passed, 31 of 31. FR-1's, `fr1-closed-compartment-v1` (exchange's first judged acceptance), is registered and judged on 18 November: passed, 44 of 44. FR-3's, `fr3-site-occupancy-v1` (`site_occupancy@1`'s first judged acceptance), is registered and judged the same day: passed, 51 of 51. FR-6's A5″, `fr6-a5pp-v1` (the channel driven through the regulatory state from a per-cell prior), follows the same day: passed, 18 of 18 |
| The D172 restructure (one modular inner model, `resolved_pump_tissue@3`) | **Landed on 16 November** (tag `d172-landed-2026-11-16`, merge ab267c39 of candidate 3c10b833). It passed the results gate, crossrev, tiers 1–3 (every non-passing tier-3 file classified, none the round's), G2 and the L4 block; the records are in PROGRESS. The lanes built on it merged the same evening, each after its own gate: core-next, windows (the packed planner's seams and opt-in device row checks; the planner itself merges after its own gate), fr45-next, the run view and core-fixes. G1 has since run at core-next, at core-fixes and on main a83d8f15, 113 of 113 each. G2, the affected registered protocols, ran at the landing and is not repeated per lane: a lane whose G1 is bitwise moves no registered result. G3's negative controls and G4's measurements are owed, and run with tier 3 on D188's final tree (D194) |
| Field-solver interface | Designed; code waits for the GH200 numbers |
| One production execution path, compile policy, registry | The kind and species registries landed with D172 (16 November). The model-level declarative registry and the one production path are not started. D147's policy for composite definitions landed on 14 November |

**The working order** (updated 16 November 2026; seven agents, D171):
1. **Done, 16 November: D172's round, landed** (merge ab267c39, tag `d172-landed-2026-11-16`;
   PROGRESS).
   - **Its critical path was:** schema A with the kind seams (the core), then FR-4's transporter
     kind (the FR-4/FR-5 owner), then A7's summation order (the left fold, D176), then the end game:
     the results gate, crossrev, tiers, the affected protocols and the flagged L4 block (D181).
   - **In parallel it carried:** B4's stage read and the passive law's insertion point (the core);
     the adapter and the families' refusals (the integration owner); O3's run-view declarations
     (the operators).
2. **Now, after the landing, in order** (from 16 November evening, D194's order supersedes the rest
   of this list where they differ):
   - **Done, 16 November:** the lanes built on the round merged, each after its gate: core-next,
     windows, fr45-next, run-view-d154, core-fixes and the test audit. The full verification of
     main a83d8f15 passed (tiers 1+2 517 files 0 changed, G1 113 of 113, crossrev's new record).
   - **D194's order:**
     1. D188's moves. The retire (D189) and the BLAS pin (D190) land first.
     2. One core-seams pass, with the core's built but unlanded items on `core-fixes` (the
        fuel-potential check, the material-slope seam, the passive-route view set).
     3. Then in parallel: the human cardiac laws, composition A (D191) and finite fuel.
     4. Mitochondria (D193) and GARD (D192), after their prerequisites.
   - **D195 (17 November):** the core-seams pass is approved at its scope, staffed within seven
     agents. In parallel now: D188's move 2, an FR owner, and step 0's desk work. Move 1 landed
     on 17 November.
   - **Origin of life (D197, D199):** the whole programme, OL0–OL9, after G1 and seam F land.
     **Relationship tracking (D200):** a general engine feature, design note first.
   - **Also started on 17 November, at the user's request:** seam F, the law template and registry
     (one more agent on the core), and GARD (D192) "as soon as possible". GARD's G1, the engine
     family registered through today's chain, and G2, the independent component references,
     run in parallel, as GARD_DESIGN §7.3 plans.
   0. **Merging the lanes built on the round** (done, above). Then D188's source-tree restructure
      (step 0's legacy list, settled in D189, and its probe, then two scripted moves). Owed from
      the landing's acceptance plan, and run with tier 3 on D188's final tree (D194):
      - G3's negative controls on landed main (planted changes that must fail the results
        gate; about 1–2 CPU-hours);
      - G4's measurements (compile time, memory and end-to-end time) on a quiet machine.

      Neither was run as a separate end-game step. The per-commit contract tests ran in the
      tiers, and the results gate's own planted-difference self-test exists.
   1. FR-4 and FR-5: registration, rehearsal and judged runs on the landed core.
   2. The finite-fuel case (D176 item 2) against its independent reference.
   3. The run-view writer (D154). **Merged into main on 16 November** (050aa741; built on branch
      `run-view-d154` from integration-d172 at 0ae1943a), with a worked example on the secreted-species development run
      (`/mnt/workspaces/Cells/run-view-20261115-01/`). It merges with its tier records and a tier
      gate. Its seam requests follow:
      - the operator contract's view declarations, and the default `view_events` entity form fixed
        to `{"cell": id}`;
      - @3's own units, readout axes and layers, which replace the writer's interim table;
      - door S's merged view of each changed field at observation. It is built by route B on
        run-view-d154 (61a2f4e7): with `view=` only, the writer re-forms the view with the
        composite's own view function, bitwise the observer's. After the landing the composite
        declares its changed set in one method of pump_composite.py, and the writer reads that
        instead of the adapter's tables (MASK_FIELDS, PADDED_FIELDS), a stopgap named in the code
        until then;
      - the visualizer's reading of the worked example: its eleven items, in
        [`visualizer/docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md`](../visualizer/docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md),
        written on the visualizer branch at d818cb34 and on main since the visualizer's merges.
        Items 1 and 10 are answered from the engine's code. `exchange_moved_fmol` is cumulative and
        positive outward. The saved `membrane_transferred` holds the passive routes only.
      FR-11's interim planarian loop comes after these. Its design is
      `docs/LOOPING_REPLAY_DESIGN.md`, on main with the writer since 16 November (ruled the same
      day):
      - a loop block whose closure the writer measures;
      - the planarian patch driven by a subthreshold current train;
      - the human loop: a paced human ventricular cell on Track E's human law set, brought
        forward by D183 (16 November) in place of a generic stand-in. It waits for those laws;
      - the minimal cells' cycle after an admission probe. Its run must carry what the viewer's loop
      reader requires: the visualizer's "What a species' looping run must carry", written on its
      branch at cf11924a and on main since its merges
      ([note](../visualizer/docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md#what-a-species-looping-run-must-carry-16-november-2026)).
      - a `loop` block in the view: the species, the cell, and the run's own closure statement
        (`within`, `says`);
      - the engine's models and its revision, since the reader refuses a loop run that names no
        revision;
      - a real run, not an example;
      - the totals that feed the rates, each with its kind and sign.
   4. The packed GPU planner. It is built on branch `packed-gpu-planner` (cf919da3) and passes its
      CPU evidence, including a rehearsal of the staged L4 plan on the 825-node tissue.
      - Its one-time GPU qualification runs on the merged head, under the lead's rulings. Packed
        against lone is judged on every field, and the field solver is set to `auto`.
      - The core seams it asked for follow: a public window-arguments constructor, mask-and-continue
        on the device, a world ID on every vectorized refusal, and a typed memory refusal.
      - **A development GPU run** (16 November, the planner's pre-D172 head 69a14cb5, under the
        flag; `packed-gpu-20261115-01/dev-gpu-69a14cb5/`):
        - packed repeats are bitwise, and the refusing world is refused on both paths;
        - but packing alone, against the same world run alone on the GPU, moves 78 field-world
          pairs beyond 1e-12, up to 1.6e-8 relative. They are the small extracellular, junction
          and reservoir flux observables and running ledgers, the fields where the vector path
          already differs from scalar on the CPU. The CPU showed packing at 3.4e-16 or less.
        - So the ruled criterion, packed against lone within 1e-12 on every field, does not hold on
          the GPU. It needs a basis in the field solve's conditioning before the qualification.
        - The throughput steps also overran the 3600 s GPU budget: throughput-128 was stopped, and
          256 was skipped.
        - **The diagnosis** (16 November): it is rounding amplified by conditioning. Lone equals
          scalar bitwise on the GPU, and observables are host maps of the state. The moved fields
          are small differences of potentials, with outside potentials near 0.5 µV against cells
          at 21 mV.
        - **The direction ruled:**
          - a class table, each field judged at 1e-12 of the scale it is computed from (the
            minimal table);
          - an empirical 1e-10 cap for the outside network's ledgers;
          - an exact host-map check;
          - `LOCKED_LIMIT_S = 4800`.
          Not frozen until a held-out development pass at a batch of 128 on the merged head, and a
          long packed-against-lone pair that settles the horizon.
   5. The module system's stage 1, one external law (D180), with §6 decided by D185: in-tree contributed modules, a conformance kit, a declarations manifest, and a contributor guide.
3. **Queued follow-ups** (each its own gated change):
   - **The test-suite audit (D187),** after the landing, starting from D172's tier-3 table:
     - freeze the table as tier 3's record;
     - triage it in three classes (harness limits, stale tests, possibly real defects);
     - retire old regression tests that don't earn their cost, sending the user the retire list in
       one batch first.
   - **Operator composition: operators reading each other's current state.** FR-11's cycle probe
     (16 November, `/mnt/workspaces/Cells/replay-20261116/cycle-probe-0407c088.md`) found four
     general gaps, each refused by the engine today. These are general composition features
     (D144). The user, 16 November: "queuing the gaps with high priority after the landing", and
     to start the design now. The design ([OPERATOR_COMPOSITION_DESIGN](OPERATOR_COMPOSITION_DESIGN.md))
     is decided: option A, one general rule (D191), built in step 3 of D194's order. The cell cycle of the minimal
     cells needs all four, and division with water needs the first. "Four" is a lower bound until
     the full-cycle definition's complete admission errors are collected.
     1. Production that reads the current volume (door V, D150 §5.1's fallback), and the
        partition's daughter volumes taken from the current volume beside water.
     2. Water that reads the current membrane area beside an area provider (membrane state or
        insertion).
     3. Turnover that reads the current masks beside the operators that close them (partition,
        insertion).
     4. Pumps on a dividing cell (pump capacity as state).
   - insertion@2's gate fix, before `check_onsets` is lifted (§7.4 (j));
   - the BETSE physiology validation's dangling reference, found by tier 3 at c1 and pre-existing at
     the tag: `validation/betse/physiology/core/physiology_protein_block_calendar.py:106` reads
     `scoped.PINS`, which its scope module doesn't define, so those tests never reach their
     assertions;
   - A7's allow-list note (`tests/species_sum_entity_sums.json`) wrongly says no entry includes the
     species axis. Three entries, partition's host-only end-of-run summary, sum mixed
     [species, slot] and [slot] fields. Either fix the wording, or fold those fields per field;
     G1 compares neither;
   - a kind hook so that rows written by operators join the passive law's exact-scope fixpoint,
     moving those routes to tableau booking. Design it with the core under D180. Until then the
     composite refuses an operator that writes an exact-booked route's row (fail-closed, version 1);
   - ledger lists read from the implementation object;
   - moving the host-side window checks, 91% of long-run time, into device windows. The first part
     merged with windows on 16 November: opt-in device row checks for scalar windows on the CPU
     (`WindowPolicy(row_checks="device")`). The vector path and the GPU follow, the GPU after its
     own measurement;
   - the summation tree, if species counts go well past 150 (D182).
4. **After GH200:** the sparse field solver, the parked D148 rounds, and the conduction workloads
   in the measurement plan.
5. **Held:**
   - the full gene-regulation track and catalogue stage 3 (D145);
   - the FEP track (D179);
   - E07-v1's re-run (D181). E07-v2 is proposed, with three questions waiting for the user.

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

### Gate: the commitments of 12 November (unchanged)

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
- **Test tiers are re-measured** only on idle cores. The timings of the night of 11 November
  were taken under contention.

### Gate: execution

| Deliverable | Completion evidence |
| --- | --- |
| The plan-validation fix | For the long-clock 825-node case: expensive binds counted and scaling with distinct definitions; trajectories and accepted or refused steps unchanged; **the cost probe records windows** |
| Live phase markers (a follow-on, not added to the fix in flight) | Binding, plan validation, compile and first window reported as they happen; preparation, execution, observation and output timed separately |
| A bound-definition object, if the fix shows the need | Definition-invariant quantities bound once. State-dependent views (volumes under water, capacitance and masks under division) keep explicit update rules |
| One production execution path | Vector windows for families with qualified device checks; the other paths declared as reference paths; shared admission and checkpoint validation |
| **A closed internal compartment on the shared inventory (FR-1, high priority; D157)** | A cell-owned finite node with its own volume and inventory rows, bounded by one patch of its owning cell, with transfer to the cytosol that reconciles on both sides. Fixed topology and volume first. Dynamic internalisation (FR-2, priority 2, D158) follows, with retrieval's energy source designed together with the energy-pool doors. The site-occupancy primitive (FR-3, priority 2, D159) is designed alongside. Compartment pH (FR-4, the requester's priority 1, D160) follows FR-1, with the energy-pool and charged-reaction doors. State-conditioned transfer with leak and reseal (FR-5, the requester's priority 1, D161) follows FR-1 and FR-4. Design notes first ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md)) |
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
| A verdict on long-time methods | Multirate or quasi-steady methods qualified, or bounded, on histories and intervention responses (projective failed its qualification). The acceptance case includes an intervention applied during the slow phase (FR-8, D164). The coarse modes cover @1–@3 only, so a long-time path for composite operators needs a design note |

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

The choice of unit is the user's. FR-7 (D163) asks that the chosen loop admit a species-driven production rate and an abundance-sourced factor in the composite. Candidates where abundance is already state:
- the redistribution pumps (`resolved_redistribution@1/@2`, which left with the legacy cleanup, D386);
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
| A landed, reusable composite physiology model | Composition | Guards done on CPU; L4 agreement by tolerance passed (W1, W2 and G2-Q1, Q7 in the flagged mode); GH200 pending |
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
- GH200 (JUPITER) work waits for access, expected at adoption by the end of the week of 16
  November. The L4 is used fully meanwhile.
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
