# Roadmap

Historical snapshot retained before the 2026-10-11 documentation refresh.
Status statements below describe their original stages. Read the
[maintained document](../ROADMAP.md) and [current progress](../../PROGRESS.md)
for present scope and run status.

Baseline: 2026-09-07. This document defines milestones and completion evidence;
[Progress](../../PROGRESS.md) is the source of current status. Dates and performance
targets will be set from measured workloads rather than assumed here.

Direction update: start with one cell; progress toward a simple whole-organ
preset and eventually multiple coupled organ presets. Modularity, data-defined
composition, and computational-multiscale extension points begin with the first
cell. Their full implementations arrive only when a milestone exercises them.

## Milestones

| Milestone | Deliverable | Completion evidence |
| --- | --- | --- |
| M0: project foundation | Scientific basis, architecture, experiment plan, decisions, and tracker | Documents are consistent, linked, and explicit about implemented versus planned work |
| M1: executable CPU foundation | M1a one-cell engine; M1b source-backed regulation; M1c two-cell contact | Analytic fixture and replay tests first; E01/E02 source checks subsequently; pinned numerical settings |
| M2: memory and relay assays | Checkpoints, branching, cue schedules, observers, stable identities | Restart comparison; selected E03-E06 positive/negative references; full-state and endpoint agreement |
| M3: fixed 2D tissue | Graph geometry, selective boundaries, E07, and separate viewer | Reproducible cue/removal/boundary/replacement demonstration; viewer does not affect dynamics |
| M4: GPU execution | Qualified one-GPU execution, then multi-GPU ensembles and coupled spatial partitions; multi-host operation later | Accuracy/precision and partition-interface checks, collective-safe failure/restart, strong/weak scaling and complete memory/communication/output measurements |
| M5: growth and turnover | Cell-centre mechanics, resource/volume accounting, division, death, changing contacts | Accounting and ancestry checks; capacity/event handling; E08 comparison with scripted renewal |
| M6: multiscale tissue unit | Detailed regions coupled to fields/compartments or validated reduced models | Interface accounting, multirate/refinement tests, E12 held-out challenge agreement, cost/accuracy profile |
| M7: first whole-organ preset | Simplest useful organ/function selected and expressed as a data definition | Declared extent and omitted physiology; organ-level validation within scope; repeatable configuration-driven run |
| M8: coupled organ presets | Two or more organ instances linked through explicit transport/signalling models | Disconnected controls, exchange/delay/accounting tests, coupled functional validation, reproducible world checkpoint |

## Sequence and dependencies

The main scientific path is M0 -> M1 -> M2 -> M3 -> M5 -> M6 -> M7 -> M8.
A small CPU/GPU feasibility comparison should begin during M1/M2 when hardware is available; M4
records a usable, verified acceleration path after representative workloads exist.
Later mechanics and lifecycle kernels need their own GPU checks.

GPU availability is not a prerequisite for the CPU milestones. JAX-compatible
state and control flow are design requirements from M1, including capacity and
mask semantics. Results from the continuing exploration can update reference
cases at any milestone through the research-update record.

Priority update, 2026-09-09, D044/D045: [BIO-001 through BIO-003 are closed as
a descriptive pilot](../../reports/BIO003_PILOT_CLOSEOUT.md), not biological
validation or a production extension. The active track returns to
[BETSE-level capability planning](../BETSE_CAPABILITY_ROADMAP.md) through the
[multiscale and parallel execution architecture](../MULTISCALE_EXECUTION_ARCHITECTURE.md).
D046 now completes SPEC-005's [one-cell multispecies contract](../MULTISPECIES_MEMBRANE_SPEC.md)
and [instantaneous reference](../../reports/SPEC005_DESIGN_CHECK.md). D047 now
completes [bounded trajectory qualification](../../reports/NUM006_REFERENCE.md)
(NUM-006). D048 implements the [versioned CPU/JAX assembly](../MULTISPECIES_MEMBRANE.md)
(CORE-006), with [production acceptance complete](../../reports/CORE006_ACCEPTANCE.md).
D049 now delivers [SPEC-006's first state-bearing channel contract](../VOLTAGE_GATED_CHANNEL_SPEC.md)
and [independent gate/instantaneous reference](../../reports/SPEC006_DESIGN_CHECK.md).
D050 now completes [NUM-007 coupled-cell qualification](../../reports/NUM007_REFERENCE.md),
selecting 0.5 ms RK4/cubic with passing 0.25 ms refinement and retained coarse
failures. D051 / CORE-007 now implements the [production channel](../VOLTAGE_GATED_MEMBRANE.md)
under a new identity; [bounded acceptance is complete](../../reports/CORE007_ACCEPTANCE.md).
D052 / [SPEC-007](../PHYSICAL_IONIC_GRAPH_SPEC.md) now supplies the physical ionic
graph contract and [passing instantaneous reference](../../reports/SPEC007_DESIGN_CHECK.md),
including one/disconnected/pair/star reductions and per-edge transfer ownership.
D053 / [NUM-008](../../reports/NUM008_REFERENCE.md) now qualifies twelve short graph
cases: independent Radau/BDF/refinement, five component reductions, complete
histories and intervention/domain checks. The selected 2 ms RK4/cubic has passing
1 ms refinement **only on this panel**. CORE-008 now implements a new
[CPU/JAX physical graph family](../PHYSICAL_IONIC_GRAPH.md), after preserving
0.12.0 and its strict source-context evidence. Its [acceptance status](../../reports/CORE008_ACCEPTANCE.md)
is separate from reference qualification. No old timestep changes.
D055 / [SPEC-008](../FINITE_EXTRACELLULAR_SPEC.md) now supplies the explicit finite
extracellular-compartment contract and [independent closed-system/reduction checks](../../reports/SPEC008_DESIGN_CHECK.md).
NUM-009's [v2 amendment](../FINITE_EXTRACELLULAR_NUMERICS_V2.md) retains the frozen
fourteen cases and all original depletion/concentration, countercharge, history,
control and whole-cubic gates. All inventories are explicitly integrated;
only implicit derivative directions use conservation-tangent linearization.
The [new numerical result](../../reports/NUM009_REFERENCE_V2.md) passes all reference
gates, selecting 1 ms RK4/cubic with passing 0.5 ms refinement. The previously
unrun block/release, pulse and depletion stresses now have complete evidence.
The [first stopped attempt](../../reports/NUM009_REFERENCE.md) and its original
sources remain unchanged. No CORE-008 timestep is inherited. Full maintained
regressions close the reference gate. D058 / CORE-009 now implements the
[finite-outside CPU/JAX family](../FINITE_EXTRACELLULAR.md), with fourteen-case
[formal restart/branch/window/cohort acceptance](../../reports/CORE009_ACCEPTANCE.md)
passing; all 150 new targeted and 3616 maintained/historical regression tests
pass, with release closeout recorded in [Progress](../../PROGRESS.md).
D059 / [SPEC-009](../SPATIAL_EXTRACELLULAR_SPEC.md) now completes the minimal spatial
outside transport/electrical-closure design and [instantaneous reference](../../reports/SPEC009_DESIGN_CHECK.md).
One cell and two outside volumes exercise diffusion potentials without invented
bulk capacitance or independent grounding. Eight definitions / 44 evaluations
pass 1,016 independent high-precision comparisons and 85 new unit tests.
[NUM-010](../../reports/NUM010_REFERENCE.md) now separately qualifies fourteen short
spatial cases / 140 attempts, selecting 0.125 ms with passing 0.0625 ms refinement.
Analytic salt relaxation, a sealed-line grid-refinement path, complete-state
restart and the independent read-only audit pass. Coarse-step failures remain
evidence, not exceptions to the limits. All 3806 five-context regression tests
and preservation closeout pass. D061 / [CORE-010](../SPATIAL_EXTRACELLULAR.md) now
implements the development CPU/JAX family in 0.15.0.dev0 after preserving 0.14.0.
Explicit inventory/interface axes and a separate same-stage field block use the
shared checkpoint/window/cohort machinery. All 156 preflight and 3962 six-context
regression tests pass. The frozen full production artifact/replay/audit gate must
still finish before release acceptance; implementation alone does not close
CORE-010. This bounded spatial
step does not apply to arbitrary future meshes.
Broader channels, fields, compartments, mechanics and
fine/coarse organ models follow as staged capability work.

GPU architecture is active design work; GPU implementation and optimization
remain future work, not part of this slice. GPU-001/002/003 separate one-GPU
qualification, multi-GPU ensembles/coupled partitions and later multi-host
execution. Full BETSE parity is not required before a representative GPU test.
This track does not complete M1 or bypass unfinished source E02 qualification;
NUM-005c2 remains deferred until its resource gates are separately resolved.

## M1 implementation slices

M1a, M1b, and M1c-a were completed on 2026-09-08; see
[M1a acceptance](../../reports/M1A_ACCEPTANCE.md) and
[M1b acceptance](../../reports/M1B_ACCEPTANCE.md), followed by the
[passive-contact acceptance](../../reports/M1C_A_ACCEPTANCE.md). CORE-003's engineering
composition gate is also complete in 0.4.0; see
[composition acceptance](../../reports/CORE003_ACCEPTANCE.md). MODEL-003's physical
cell is complete in 0.5.0; see [acceptance](../../reports/MODEL003_ACCEPTANCE.md).
MODEL-004's gated physical pair follows in 0.6.0; see its
[guide](../BIOELECTRIC_PAIR.md) and [acceptance](../../reports/MODEL004_ACCEPTANCE.md).
MODEL-005's nominal source-compatible pair follows in 0.7.0; see its
[guide](../SOURCE_EMT_PAIR.md) and [acceptance](../../reports/MODEL005_ACCEPTANCE.md).
CORE-004 now supplies independently clocked world batches and a bounded CPU
profile in 0.8.0; see [acceptance](../../reports/CORE004_ACCEPTANCE.md). CORE-005a
adds [single-world bounded windows and recording](../WINDOWED_EXECUTION.md) in
0.9.0; CORE-005b extends the contract to [independently clocked cohorts](../WINDOWED_WORLDS.md)
in 0.10.0, with prepared execution reuse and complete round checkpoints.
Selected longer E02 switching remains, so M1 is still in progress. Larger workloads
and vectorized/GPU execution have additional engineering gates.
SPEC-004 now freezes [E02-SW1](../E02_SWITCHING_PROTOCOL.md): qualify independent
graph composition and fresh preparation first (NUM-005), then implement a
general fixed-graph source profile (MODEL-006/VERIFY-011), then audit the
14-condition assay (ASSAY-002). The minimum selected positive-hypothesis topology
has three cells; one- and two-cell controls preserve the one-cell-first build
sequence. No larger model or long-time method is implemented by this design gate.
NUM-005a now implements and checks the [independent graph reference](../SOURCE_EMT_GRAPH_REFERENCE.md)
against native instantaneous witnesses and the old pair oracle.
NUM-005b now passes [bounded full preparation](../SOURCE_PREPARATION_REFERENCE.md),
with exact 500-unit endpoints, independent references and complete qualified
packets. NUM-005 remains open: long trajectories and candidate selection
(NUM-005c) precede production. Neither instantaneous agreement nor preparation
alone selects a production timestep or qualifies connected switching.
NUM-005c is now split into [c1 long implicit references/readouts](../SOURCE_GRAPH_PATHS_REFERENCE.md)
and c2 RK4 selection, selected/half-step qualification and four candidate-owned
preparation continuations. The frozen 14-case panel and all resource/error budgets
are unchanged; a stopped session remains incomplete and does not trigger an
automatic budget extension.
The [explicit c1 continuation](../../reports/NUM005C1_CONTINUATION.md) now leaves ten
conditions qualified and a reverse miRNA-only reference disagreement to resolve
before c1 can close. A named amendment must precede any new numerical settings.
The later [c2 preflight](../E02_CANDIDATE_PREFLIGHT.md) must assess complete checked
runtime and evidence volume before launching its fine-step study.
The approved [A1 BDF refinement diagnostic](../../reports/NUM005C1_A1_BDF_REFINEMENT.md)
meets the unchanged agreement target and passes independent auditing. Adopting
an amended reference policy, generating that case's reference observers and
completing the three remaining controls require a separate decision, not an
automatic outcome of the diagnostic. D036 now authorizes that
[A2 reference-policy/remaining-panel step](../E02_REFERENCE_POLICY_A2.md). All 14
amended-policy cases and their observers now pass independent auditing;
[A2 evidence](../../reports/NUM005C1_A2_REFERENCE_PANEL.md) preserves the original
failed campaign. All 1362 regression tests pass; NUM-005c1 is complete under A2.
The [c2a bounded-candidate engineering/preflight](../../reports/NUM005C2A_CANDIDATE_ENGINEERING.md)
now passes twelve short profiles, independent auditing and all 1415 regression
tests, including 53 new checks. Exact width/restart
evidence and short accuracy are established, but complete checked runtime and
full evidence volume do not establish a long-study fit under the existing caps.
D038's [c2b diagnostic optimization](../../reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md)
now passes twelve matched short profiles and expanded readout auditing. Across
the six cases, complete checked time is 1.84× lower and all saved readouts are
bitwise exact against the frozen scalar evaluator. All 1540 regression tests and
335 targeted tests pass, including 125 new checks. The improved
planning estimate is still 7.09 hours and 11.505 GB, not an established fit.

D039's [c2c lossless-recording prototype](../../reports/NUM005C2C_LOSSLESS_EVIDENCE.md)
now passes twelve short profiles, exact reconstruction/restart and independent
audit/failure checks. All 1707 regression tests and 384 targeted tests pass,
including 167 new checks. Compressed trajectory payloads fall 57.8%, but total
profile evidence falls only 16.7%; checked and audited runtime is essentially
unchanged. No compact long-study policy is adopted.

D040's [c2d reference-backed comparison prototype](../../reports/NUM005C2D_COMPARISON_RECORDING.md)
now passes twelve short profiles and independent dependency/reconstruction
auditing. All 1903 regression tests and 541 targeted tests pass, including
196 new checks. Exact logical samples are retained with 98.5% smaller
comparison payloads and 80.6% less total profile evidence. Checked time rises
4.2% in the single matched observations; long-study fit remains unestablished.

D041's [c2e immutable scalar evaluator](../../reports/NUM005C2E_INTEGRATION_EVALUATION.md)
now passes twelve short profiles and independent recomputation of all 30,720
recorded complete stage derivatives. All logical evidence remains exact against
D040, with no stage/domain/accounting/cubic-check change. RHS time falls 13.9%,
checked runtime 2.9%, and checked-plus-audited runtime 0.9% in these single
matched observations. All 2178 regression tests and 816 targeted tests pass,
including 275 new checks. The short-only slice is complete; production is unchanged.

D041 recommended further unchanged-validation/audit profiling. D042 pauses that
optimization track. Preserve all checks and independent coverage; trajectory
storage and runtime remain unresolved. No compact long-study policy is adopted
and no long candidate study has started. Production graph/assay work still
depends on completing the numerical gates, not on success of BIO-001/002.

1. M1a: pin a CPU environment and package/test entry points. Implement one
   source-and-decay cell from a validated data definition, a pulse schedule,
   independent numerical stepping and observations, complete snapshots, and
   isolated checkpoint branches. Compare against the analytic solution and check
   eager/JIT agreement. The detailed build order and acceptance suite live in
   [First build](../FIRST_BUILD.md).
2. M1b: resolve the pinned reference source, reuse terms, and smallest useful
   fixtures. Add the source-backed intracellular model, its units, algebraic
   refresh, parameters, and endpoint semantics. Validate isolated regulation
   against CPU reference calculations and source behaviour.
3. M1c-a, complete: add two cells with an explicit active/blocked contact. Check
   passive reciprocal transport against analytic references, including unequal
   volumes, cell/edge capacities, source-free accounting, release, and replay.
4. M1c-b, with the user's engineering-first refinements (D016 and D018):
   CORE-003's local-reaction/graph-transport [engineering gate](../ENGINEERING_GATE.md)
   is complete (D017). The [one-cell physical specification](../BIOELECTRIC_CELL_SPEC.md)
   now defines membrane/bath interfaces, charge closure, leaks, and an energized
   reference pump. [NUM-002](../BIOELECTRIC_NUMERICS.md) now qualifies independent
   CPU trajectories and a bounded RK4/5 ms plus cubic-observation candidate;
   the subsequent small physical cell (MODEL-003) is now implemented and regressed,
   including independent controls, identified observations, and full replay.
   D021/SPEC-002 now specifies the [stateful physical pair](../SELECTIVE_CONTACT_SPEC.md)
   and verifies instantaneous [source correspondence](../SOURCE_COUPLING_MAP.md).
   [NUM-003](../SELECTIVE_CONTACT_NUMERICS.md) now freezes and qualifies all 20
   independent coupled cases, selecting RK4/1 ms and cubic observations after
   coarser gate errors. MODEL-004 implements the pair through the shared engine,
   with JAX/reference, identity/padding, replay/branch and regression checks.
   SPEC-003/D024 pins the [complete source-compatible pair](../SOURCE_EMT_PAIR_SPEC.md),
   prepared full packets, 14 cases and 17 native instantaneous settings.
   [NUM-004](../SOURCE_EMT_PAIR_NUMERICS.md) qualifies all 14 independent coupled
   cases at RK4/0.01 nominal units with cubic observations. Native trajectories
   pass the corresponding gates with a separately recorded S12 event refinement;
   the original timing failure remains evidence. [MODEL-005](../SOURCE_EMT_PAIR.md)
   now implements that distinct profile through the shared engine, with complete
   replay/branch and six-model regressions. Physical calibration and selected
   source-assay protocols remain separate gates; no nominal/physical mapping is assumed.
   CORE-004/PERF-001 now measures independent-world batches, including a 32-cell
   reaction graph and nominal pairs at 1/4/16 worlds, separating compilation,
   kernel, host, output and memory costs. These bounded CPU profiles are distinct
   from ordinary acceptance timings; they do not qualify GPU or tissue-scale work.
   Source-assay support must use reusable engine capabilities, not special cases
   for expected outcomes.

The [BETSE/software review](../BETSE_DESIGN_REVIEW.md) informs these interface and
physics decisions, not a backend replacement or automatic source parity.
Preparation must be explicit, external support accounted for, and model fidelity
separate from solver/device choices. A pinned corresponding BETSE reference is
a later bounded task; no full upstream experiment campaign is required now.

The pinned source checkout is now available locally. M1b implements the isolated
regulatory equations independently; upstream implementation redistribution terms
remain unresolved. M1c-b must separately establish its source-unit mapping and
coupled numerical contract. The analytic fixture remains engineering verification,
not a replacement for source comparison or a demonstration of heredity.

Package versions, array ordering, and solver choice are resolved by this slice.
They are not reasons to revisit the accepted Python/JAX decision unless evidence
shows a material obstacle.

## M2 and M3 implementation slice

Extend the M1a restart and branching machinery to all coupled state, intervention
schedules, and phenotype/retention/transmission observers. Specify biological
transfer boundaries independently of numerical snapshots. Reproduce a bounded
reference subset before introducing the first tissue extension. Carry the actual resulting
states and identities forward through failures.

Extend E04 with matched-visible-state, different-history challenge assays and
component substitutions. Fix observer coordinates, sampling, nulls, and positive
controls before interpreting a difference. Biological readers/writers use only
declared inputs; offline decoders are separate analysis.

Add fixed 2D geometry and a viewer reading recorded state. E07 then combines cue
writing, release, altered communication, and scripted replacement. Extracellular
fields enter when a selected experiment needs them, with explicit boundary
conditions and cell-field exchange tests.

## M4 and M5 implementation slice

Benchmark GPU relay ensembles and coupled graphs with the same accuracy contract
as CPU. Record where acceleration helps and where overhead or solver behaviour
limits it. Avoid expanding benchmark coverage without a corresponding decision
or unresolved concern.

For M5, specify the extended growth/turnover model before interpreting its results.
Add moving cell centres, neighbour discovery, resource dynamics, division and
partition, death, and stable ancestry. Check numerical coupling, volume/amount
accounting, simultaneous events, and capacity overflow. Evaluate autonomous
renewal as a new experiment, informed by the continuing exploration's H5 work.

## M6 to M8: tissue units, organs, and coupled organs

First make one explicit fine/coarse interface work. Add spatial fields, 3D
geometry, and process-specific rates as required by the chosen tissue question;
test each addition against a smaller detailed/reference case. A reduced state
must preserve relevant history and future responses, not only a current label.

Select the first organ using simplicity, available evidence, external dependency
count, and one measurable function. Its definition specifies species, geometry,
cell/process families, resolution, parameters, ports, and omitted physiology.
Implement any missing reusable mechanism as a model module; keep organ selection
and assembly in data. Do not relabel a tissue patch as a whole organ.

Add a second independently initialised organ instance and explicit couplers only
after generic multi-compartment exchange tests pass. A coupled world checkpoint
includes transport compartments, pending exchanges, delays, and each component's
numerical state. Independent ensemble batching is not organ-to-organ coupling.

Computational multiscale and large-GPU execution are future requirements recorded
in [Multiscale design](../MULTISCALE_DESIGN.md). Profile memory, numerical work,
coupling, output, and transfers before selecting spatial partitioning, different
regional fidelity, or multiple devices. GPU capacity alone does not establish
whole-organ feasibility. These are not M1a implementation tasks.

## Other research options

Cell shape models, population evolution, inherited regulatory structure,
information-dynamic observers, differentiable inference, and validated coarse
models can be selected when they answer a concrete research question. E09-E11
memory-location, ecology, and embedded-control experiments can branch from the
appropriate milestones; all are not mandatory gates to an organ demonstration.
The strict-eight, ingressing/Ruliad, and AI design review is recorded as R002.
Unreviewed parts of the broader preprints collection remain later ideas sources.

## Updating this roadmap

Track daily execution and evidence in [Progress](../../PROGRESS.md). Change a milestone
here when its scope or acceptance evidence changes. Record architectural changes
in [Decisions](../DECISIONS.md), preserving the reasons for earlier choices. A valid
negative scientific result may complete a milestone; implementation success does
not require a favourable biological hypothesis.
