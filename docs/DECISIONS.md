# Decision record

Initial agreement: 2026-09-07. The user selected Python and JAX and accepted the
proposed overall direction. These decisions describe the baseline; concrete
implementation details remain adjustable through recorded evidence.

Use stable decision IDs. A later change should supersede an entry with a new
dated rationale rather than erase the earlier choice.

This is a historical decision record, not a current feature list. Statements
about pending work apply to the date of their entry. Consult [Architecture](ARCHITECTURE.md),
[Roadmap](ROADMAP.md) and [Progress](../PROGRESS.md) for present scope and priorities.

## D001: Python with JAX, CPU first

Status: accepted, 2026-09-07.

Use Python for the simulation API, experiment orchestration, and analysis, and
JAX for numerical execution on CPU and subsequently GPU. Keep small, readable
NumPy/SciPy reference calculations for numerical verification.

This fits the existing Python research and makes array batching and explicit
state useful immediately. JAX's shape, compilation, and control-flow constraints
will be addressed in the initial implementation. The GPU path is verified through
benchmarks and scientific comparisons, not assumed from library selection.

R remains available for analysis of shared artifacts. PyTorch may be useful for
future learned controllers but is not a second simulation backend in the initial
plan. Taichi, Julia/SciML, and a C++ core remain alternatives if a concrete later
requirement justifies reconsideration. Supporting all these runtimes is not a
project objective.

## D002: explicit state and separate model responsibilities

Status: accepted, 2026-09-07.

Represent intracellular state, communication, environment, lifecycle, and execution
state explicitly. Calculate phenotype and other measurements through observers.
Model equations, solver settings, interventions, and measurements have identifiable
versions. This supports full-state memory experiments and reproducible branching.

Writable carriers are model mechanisms with stated dynamics. Shared fixed rules
and externally supplied cues retain their own identities and accounting.

## D003: fixed contact graphs followed by moving cell centres

Status: accepted direction, 2026-09-07.

Start with small graphs and fixed 2D layouts. Extend to cell-centre mechanics,
changing contacts, growth, and division. Cell shapes represented by Cellular Potts
or vertex models remain possible if morphology becomes central.

PhysiCell and CompuCell3D are reference alternatives for mature tissue mechanics.
They are not current dependencies; adopting one would require comparing its
mechanics, intracellular coupling, and execution model against Cells requirements.

## D004: arrays, ensembles, and declared numerical accuracy

Status: accepted, 2026-09-07.

Use array-oriented numerical state, explicit capacities and active masks, and
stable biological identities independent of slots. Support compatible batches of
independent worlds as well as one coupled tissue.

Use float64 CPU reference calculations and meaningful convergence checks. Validate
GPU execution against specified numerical and scientific tolerances. Record
cross-device statistical agreement where exact trajectories are not an appropriate
comparison. Preserve identifiable precision and random-stream policies.

## D005: experiments and reproducibility are core capabilities

Status: accepted, 2026-09-07.

Provide complete checkpoints, restoration, alternative futures, intervention
schedules, lineage records, and machine-readable manifests. Separate scientific
failure from execution failure. Include positive, negative, ordinary-state, and
mechanism-specific controls appropriate to each question.

The first tissue demonstration is a small 2D cue/communication/retention/replacement
experiment. Scripted relay renewal and later autonomous division are separately
specified model versions and claims.
The later one-cell-first refinement is recorded in D011.

## D006: headless engine and separate viewer

Status: accepted, 2026-09-07.

Simulation execution works without a GUI. A viewer displays saved or streamed
state; its refresh rate does not set the scientific clock. Interactive actions
use the recorded intervention interface. Python and optional R analysis consume
the same portable result artifacts.

## D007: evolving research with identifiable snapshots

Status: accepted, 2026-09-07.

Use Plastic Heredity v2.3 and the continuing Levin-derived exploration as the
initial ideas base. Bring reviewed findings, source versions, checkpoints, and
controls into Cells through recorded updates. Completed Cells runs retain their
original contracts as upstream research changes.

The initial wider-review deferral was superseded for the strict-eight,
ingressing/Ruliad, and AI branches by the user's subsequent request; R002 records
that targeted review. Other branches remain deferred. The existing
exploration continues in its own workspace; this documentation task does not
launch or modify its experiments.

## D008: explicit biological boundaries and mechanism access

Status: accepted direction, 2026-09-07, following the broader review.

Numerical snapshots preserve complete continuation state. Biological transfer,
division, and replacement each declare surviving, partitioned, reconstructed,
erased, and external state. Include environmental and contact channels where
relevant. Track expression, transport, reading, and writing as distinguishable
operations, with declared sensing/actuation access and costs.

Protected memory, restricted writing windows, and learned translators are optional
mechanisms to test, not laws assumed by the engine. Global observer information
must not silently become local biological input.

## D009: observer contracts and future-response assays

Status: accepted direction, 2026-09-07, following the broader review.

Version observer coordinates, scales, sampling, thresholds, and calibration.
Retain continuous and challenge-response measurements alongside phenotype labels.
Equal current expression does not prove equal responsiveness or inherited state.
Permit explicitly modelled changes to regulatory/plasticity dynamics; do not add
unexplained memory variables to the source model.

Separate parent continuity, ancestor retention, renewal, rewriting, and useful
adaptation. Correct/wrong carrier, reader/writer ablations, passive persistence,
recipient compatibility, and matched-cost controls are selected by the claim.
The ingressing/Ruliad audit supersedes treating its early law summaries as
established universal constraints.

## D010: data-defined multiscale composition and multiple organs

Status: accepted direction, 2026-09-07, from the user's expanded goal.

Support a whole-organ model and eventually interacting organs. Organ instances
are configurations of reusable processes, geometry, populations, parameters,
fields, and exchange ports. Implement new physics in tested modules, not organ
name branches in the core. Separate model, experiment, and execution settings.
An ownership hierarchy and an exchange graph are different structures.

Use explicit dimensional, spatial, temporal, and fine/coarse coupling contracts.
One coupled world may contain several organ instances; independent worlds remain
replicates. Select the simplest useful first organ/function later. No organ name,
species, complete physiology, or all-cell/full-detail representation is selected.
See [Multiscale design](MULTISCALE_DESIGN.md).

## D011: one-cell-first implementation

Status: accepted direction, 2026-09-07. Concrete fixture details are the proposed
implementation plan and may be refined during M1a.

Start with one well-mixed cell and a timed input. A source-and-decay fixture with
an analytic solution verifies state, units, scheduling, integration, observation,
save/restore, and independent branches. M1b introduces the source-backed regulatory
model; M1c adds contact. The fixture establishes engineering correctness only.

Use small modular functions and explicit array state from the start. Do not build
an unused universal plugin, organ, or distributed runtime framework. Early NPZ/JSON
snapshots do not settle the production storage format. See
[First build](FIRST_BUILD.md).

## D012: future computational multiscale and large-GPU execution

Status: accepted future requirement, 2026-09-07; implementation deferred.

Preserve independent choices of spatial resolution, process time step, model
fidelity, and hardware placement. Start with static choices; dynamic resolution
changes later need validated state transfer, conservation, and retention of
history-dependent behaviour. Select GPU tiling, capacity/model batching,
device-resident stepping, and multi-device decomposition by measured workloads.

Budget memory, scratch space, communication, and outputs as well as arithmetic.
Do not equate more cells or larger GPUs with a valid multiscale model. M1a creates
the state/interface prerequisites only; no distributed backend, large-GPU target,
or mixed-precision policy is selected now.

## D013: implemented M1a baseline

Status: implemented and verified, 2026-09-08; resolves the first-build choices
without selecting the later source-backed model's numerics.

Cells 0.1.0 uses Python 3.13.5, JAX/jaxlib 0.11.1, NumPy 2.5.3, an isolated .venv,
and the pinned CPU development dependency set. Package metadata currently supports
Python 3.13 only. The CLI exposes validate, run, resume, and branch. JSON schema 1
separates model, experiment, and execution; only source_decay@1 is supported.

RK4 evolves a one-cell amount plus input/decay ledgers on a zero-anchored,
event-split grid. Units are explicitly fmol, pL, and seconds. The conservative
supported step domain is k times the largest actual step <= 1. Observations are
read-only linear interpolation and do not set the integration grid. Complete
numeric NPZ/JSON snapshots include state/layout/clock, resolved definitions,
checksums, source hashes, and runtime identity. Output never silently overwrites.

M1a explicitly selects CPU and float64 for its process. Strict resume refuses
source/runtime mismatch; migration and cross-device restoration are not yet
supported. Branching changes future inputs/horizon/observations, not the past,
model, or numerical settings. Tissue, organ, and accelerator mechanisms remain
future work. See the [acceptance report](../reports/M1A_ACCEPTANCE.md).

## D014: source-backed isolated regulation through a model registry

Status: implemented and verified in 0.2.0, 2026-09-08.

Add emt_mirna@1 alongside source_decay@1 through a small explicit module registry.
Each model owns its state/layout types, pure RHS, parameters, numerical checks,
read-only observations, and summaries; shared code owns integration and artifacts.
Retain distinct biological meanings rather than assigning all state amount/volume
semantics. This is a two-model interface, not a plugin system or organ hierarchy.

The isolated regulatory subsystem needs only total miR200, total Zeb mRNA, and
ZEB protein, with fixed declared Snail. Retain the source's simple total-miRNA
binding approximation; derived complexes and E/M labels are not primary state.
Use explicit source-scaled coordinates and nominal source-time units while the
physical-unit correspondence is unresolved. Source checkout is pinned and clean;
upstream code is not vendored and redistribution terms remain open.

CPU float64 RK4 at step 0.1 is validated for the shipped E/M cases by source
derivative comparisons, Radau/BDF references, and fourth-order refinement. The
supported largest-step cap is 0.25, not an arbitrary-state error guarantee or
a solver decision for coupled ionic dynamics. See [Reference contract](EMT_REFERENCE.md).

Strict checkpoint identity is retained. The verified 0.1.0 source was archived
before edits; old runs remain intact and require that source to restore. No
cross-version migration or relaxed compatibility check is introduced. Python API
specifications are normalized before checkpoint writing and fingerprinting.

## D015: passive contact with distinct cell and edge state

Status: implemented and verified in 0.3.0, 2026-09-08; M1c-a only.

Add passive_pair@1 as a third explicit model. A separate pure coupling module
calculates each contact's amount flux once and applies equal-and-opposite endpoint
contributions. The runnable fixture has exactly two fixed-volume cells and one
physical contact. Cell and edge capacities, masks, stable IDs, layout, and
checkpoint dimensions remain distinct. General graphs and full-world batching
are later extensions, although shared-endpoint and flux-batching primitives are tested.

Prescribed contact opening is a named experimental control, separate from external
amount input. Blocking a contact does not remove its physical topology. The signed
transfer ledger supports accounting but is not additional stored material or a
biological memory variable. Source/EMT controls cannot silently be substituted.

Retain CPU float64 RK4 with per-event-interval h*g*u*(1/VA + 1/VB) <= 1, exact
control boundaries, read-only observations, and full restart/branch provenance.
Independent scalar and matrix references, fourth-order refinement, conservation,
and exact replay validate this engineering model. The previous 0.2.0 source and
runs are preserved; strict compatibility is not weakened.

This does not validate voltage-selective coupling or calibrate source-scaled EMT
coordinates to physical contact units. M1c-b must establish that separate model
and solver contract. Representative batch profiling is also still required before
M1 closeout. See [Passive contact](PASSIVE_CONTACT.md) and
[acceptance](../reports/M1C_A_ACCEPTANCE.md).

## D016: engineering-led composition before source-assay parity

Status: accepted direction, 2026-09-08, following the user's clarification.
The design-only decision below preceded implementation; D017 records its delivery.

Cells must support the Levin assays through reusable mechanisms, topology,
numerical execution, and explicit experiment operations. Source-specific equations
remain in a versioned model; assay names, expected E/M labels, and historical
outcomes must not select engine behaviour. Reference parity is scientific
acceptance evidence, not a reason to bypass engineering or numerical checks.

Refine the next M1c-b sequence: first exercise local-reaction plus graph-transport
composition on a tiny independent amount model, then implement source-specific
bioelectric mechanisms through those boundaries. Verify independent limits,
conservation where declared, stage-consistent accumulation, configuration-driven
topology, and complete state before testing source switching and relay behaviour.
Do not force the source's scaled coordinates into physical units without a mapping.

Keep the existing verified foundation and extend only interfaces exercised by
the new fixture. No general plugin framework, organ implementation, or GPU
runtime is added at this design gate. Current 0.3.0 functionality and all
historical acceptance scopes remain unchanged. See
[Engineering gate](ENGINEERING_GATE.md) for responsibilities, the bounded fixture,
and separate engineering, numerical, and scientific acceptance criteria.

## D017: local reaction and graph transport composition

Status: implemented and verified in 0.4.0, 2026-09-08; CORE-003 only.

Add reaction_transport@1 as a fourth explicit model, composing one reversible
two-species conversion with species-specific passive contacts. Host validation
resolves names, cell/edge IDs, endpoint slots, dimensions, and control ordering.
The fixed population and topology are data, with independent cell/edge capacities
and neutral padding; zero-edge, disconnected, and shared/parallel-contact cases
are supported. This is not a general reaction language or arbitrary model assembly.

The reaction module and graph coupler return contributions from the same RK
stage state. The model explicitly sums them; no sequential mutation introduces
an accidental split method. Amounts use species-by-cell arrays; contact-transfer
ledgers use species-by-edge arrays; conversion ledgers use cell arrays. Ledgers
are signed accounting, not stored material or biological memory. Event controls
specify a complete opening vector by contact ID and never silently replace an
external source or a reaction law.

For this closed synthetic amount model, validate global A+B and per-cell/species
reaction/transport accounting. Retain CPU float64 RK4 with h*alpha <= 0.5, where
alpha combines local loss and all incident outgoing transport rates. The bound
supports positivity but does not guarantee trajectory accuracy: independent
piecewise matrix references and refinement establish the latter. Faster test
variants use a finer step to meet the unchanged accuracy target, not relaxed
tolerances or altered mechanisms.

All 270 tests, eight saved composition examples, and 12 earlier-model regression
runs pass. The verified 0.3.0 source was archived before edits and its historical
pair runs reverified. Strict checkpoint identity remains; no silent migration.
See [contract](REACTION_TRANSPORT.md) and [acceptance](../reports/CORE003_ACCEPTANCE.md).

This completes D016's engineering/numerical composition gate, not source-selective
bioelectric validation. Source-scaled EMT coordinates are not wired to physical
amounts without a separately specified model/mapping. Next specify that source
contract and independent reference before implementation. Full-world batching,
representative profiling, multirate/fine-coarse execution, organ hierarchy, and
GPU execution remain future work.

## D018: bioelectric interfaces and a one-cell physical contract

Status: accepted design and independently checked instantaneous equations,
2026-09-08; not a new simulator release. The user approved the recommendations
from the [BETSE/software review](BETSE_DESIGN_REVIEW.md), recorded as R004.

Retain Python/JAX, pure composed mechanisms, host-resolved arrays, and strict
restart identity. Introduce explicit membrane identity/area/capacitance and a
typed external bath in the next physical model. Cell volume, membrane interface,
contact adjacency, experimental inhibition, and endogenous gate state are
separate concepts. Evolving gates, finite reservoirs, and fields acquire their
own checkpointed state when implemented, not hidden mutable state now.

Physical approximation, numerical method, and hardware placement are independent
choices. A reduced circuit-only model is not just a faster solver for an ionic
model; unsupported quantities and interventions must be rejected explicitly.
Preparation is an identified protocol/checkpoint, never an automatic reset on
resume or branch. Couplers remain open to directed transport as well as passive
exchange, with each law owning its physics and shared accumulation owning its
declared accounting. Future tissue/GPU work must budget solver and output memory.

The next bounded physical fixture is one Na/K/Cl cell, one lumped membrane, a
maintained bath, constant-field leaks, and an explicitly energized reversible
reference pump. Primary ion amounts determine voltage through an immutable
charge/capacitance anchor; voltage is not independently integrated. Separate
leak and pump controls, exchange/cycle ledgers, and external chemical work make
its assumptions inspectable. The pump law is our phenomenological engineering
fixture, not calibrated Na/K-ATPase kinetics or a copied BETSE/Calculion mechanism.

The [one-cell specification](BIOELECTRIC_CELL_SPEC.md) fixes the equations, units,
state ownership, and acceptance targets. Its independent calculator passes
74 instantaneous design checks; it is not a trajectory solver or production
model. NUM-002 must establish independent CPU trajectories, a solver, and a
bounded numerical domain before MODEL-003 production acceptance. No existing
RK4 step bound is presumed valid for nonlinear ionic dynamics.

This extends D017's next-step sequence with physical one-cell engineering before
source-selective contact. The unresolved source-scaled EMT unit/clock mapping
remains separate; a physical toy must not be substituted for a source comparison.
BETSE and the other reviewed tools are reference/adaptor candidates, not added
dependencies. Cells remains 0.4.0 with four runnable models. Organs, multirate
execution, spatial fields, large GPUs, and source-assay parity remain future work.

## D019: independent bioelectric numerics and interval-correct observations

Status: NUM-002 reference/method qualification, 2026-09-08; not a production
release. The user approved proceeding from D018's physical-cell specification.
See [numerical contract](BIOELECTRIC_NUMERICS.md) and
[qualification report](../reports/NUM002_REFERENCE.md).

Use a separate NumPy/SciPy oracle with no Cells mechanism imports. It evolves
ion-amount increments and uses an equivalent hyperbolic flux expression; the
independent RK4 probe evolves absolute amounts. Compare Radau/BDF, tolerance
refinement, analytic limits, material/charge balance, and an independent
bath-relative energy identity. Preserve reference code, case definitions,
trajectories, runtime, and hashes before JAX implementation.

Select float64 RK4 with maximum step 0.005 s and interval-held-control cubic
Hermite observations for the initial 18-case panel. Accurate accepted endpoints
did not make linear observations accurate enough; this is an observation-method
decision with its own tests and metadata, not altered physics or looser targets.
At an intervention, the two adjacent intervals need their own endpoint slopes.
Sampling stays read-only and must preserve exactly constant intervals/endpoints.
Do not change the previous four models' observation contracts implicitly.

The method is qualified on the stated panel, not the full Cartesian product of
its parameter ranges or arbitrary physical cells. Check all stages/endpoints
for finite positive amounts and the specified voltage domain, keep resource
limits explicit, and revalidate new regimes. No linear-model stability bound
or global nonlinear accuracy guarantee is claimed.

Local fast/slow modes and a long passive reference motivate future stiff or
validated multirate methods; a GPU alone does not resolve numerical stiffness.
The passive endpoint still has a measurable equilibrium residual after the
requested horizon. Preparation therefore remains a recorded protocol with
measured criteria, not an automatic warm-up or a duration-based success label.

MODEL-003 must now implement the physical-cell state/layout, mechanisms, independent
controls, and identified observation policy, then pass eager/JIT, reference,
event, full-checkpoint, and regression acceptance. Preserve 0.4.0 source before
production changes. This reference adds no registered model, biological/source
parity, GPU execution, or organ functionality.

## D020: physical JAX cell through reusable engineering boundaries

Status: implemented and verified as MODEL-003 / Cells 0.5.0, 2026-09-08.
The user approved proceeding from D019's qualified reference. See the
[run guide](BIOELECTRIC_CELL.md) and [acceptance](../reports/MODEL003_ACCEPTANCE.md).
D018/D019 above retain their historical design/reference-stage status.

Implement one fixed-volume Na/K/Cl cell with distinct membrane and clamped-bath
identities. Keep the Bernoulli/GHK and reference pump laws pure, and compose them
from the same stage state. Amounts own charge; immutable anchors own the voltage
closure. Signed leak/cycle ledgers record external exchange, not duplicate matter.
Independent control groups are host-resolved on their event union. No general
plugin framework or source-assay branch is introduced.

The engine gains an optional pure stage-domain predicate and checked RK4 path,
plus interval-controlled cubic sampling. Invalid trials are guarded before
nonlinear evaluation and refused before result publication, not repaired or
classified as biological death. The new observer is identified in metadata;
the four earlier models keep their linear policy. Full layout, electrical
anchors, bath, controls and exchange history survive exact restart and branching.

The fixed physical targets pass all 18 pinned cases and a future-control branch;
447 tests and all four earlier acceptance suites pass. Archive 0.4.0 before edits
and keep strict source/runtime snapshot checks. No dependency, GPU execution,
calibration or source-assay parity follows from this release.

Next specify stateful gates and selective contact, with a new electrical closure
where needed and a separately justified source unit/clock mapping. Numerical
stiffness, per-world batching/failure policy, multiscale reduction and GPU placement
remain distinct decisions, to be made from verified representative workloads.

## D021: separate physical gate memory from source-compatible contact

Status at this decision: design and instantaneous verification complete as SPEC-002,
2026-09-08; NUM-003 and production MODEL-004 were unimplemented (since completed
in D022/D023). The user approved the
next gate after MODEL-003. See the [pair specification](SELECTIVE_CONTACT_SPEC.md),
[source map](SOURCE_COUPLING_MAP.md), and [evidence](../reports/SPEC002_DESIGN_CHECK.md).

The next physical fixture is two membrane/bath cells with one selective junction
and an explicit evolving gate. Use diagonal charge/capacitance closure relative
to a shared clamped bath; omit mutual junction capacitance explicitly. Gate
probability, per-species open/residual permeability, and prescribed inhibition
are separate. Store one signed edge-transfer ledger and scatter its flux once.
Reuse the one-cell leak/pump physics and stage-composition boundaries.

Do not silently replace the source's algebraic gate with a dynamic state or its
upwind drift law with constant-field transport. Native probes establish these
distinctions, the executable voltage orientation, species-specific amplitudes
that can exceed one, and miRNA's effective drift charge excluded from voltage
accounting. Source-compatible models must preserve identified approximations
and nominal units. A physically calibrated EMT/ionic model needs an additional
mapping; parameter conversion alone cannot remove an equation mismatch.

This design adds one junction gate first; membrane-channel gates, heterotypic
physical kinetics, finite reservoirs and fields remain separate extensions.
Explicit gate state supports later multirate/reduced-model comparisons, but
neither a fast-gate approximation nor a GPU removes the numerical qualification
requirement. Freeze the 20-case NUM-003 panel and targets before integrating it;
do not assume the one-cell 5 ms limit carries over. Preserve 0.5.0 source before
any production change, then implement MODEL-004 only against a qualified oracle.

R005's completed H3/H4 document check-in strengthens existing full-state,
matched-control and external-support requirements; it adds no engine-specific
PH mechanism. The source memory harness and voltage-gated cancer cases use
different switches. CONTACT-003 remains in progress until corresponding coupled
trajectories are validated; source-table, biological and organ claims remain open.

## D022: qualified physical-pair reference before production

Status: NUM-003 complete, 2026-09-08; no production package change. The user
approved proceeding from SPEC-002. See the [numerical contract](SELECTIVE_CONTACT_NUMERICS.md)
and [qualification evidence](../reports/NUM003_REFERENCE.md).

Freeze the 20-case data panel and targets before integration. Compose the
independently qualified one-cell reference with an independently expressed
hyperbolic junction law and one primary relaxation gate. Radau/BDF evolve amount
increments; the RK4 candidate evolves absolute amounts. Reference-only leak,
pump and junction dissipation quadratures remain separate from biological state.

Use boundary-aware Jacobian probes so an initial gate at one does not require
invalid forward perturbations or clipping. Keep all gate and ledger state across
exact control boundaries. Check complete-state errors, per-cell accounting,
separate-cell/analytic/symmetry/orientation limits, cubic interior extrema, and
native accepted states in addition to RHS trials and requested samples.

The predeclared study rejects inherited RK4/5 ms: Q09's gate error is about 84
times the fixed target, and Q11 also fails. Q09 still fails at 2.5 ms. Select
CPU float64 RK4 with nominal maximum step **1 ms** and interval-controlled cubic
Hermite observations for the bounded 20-case panel. All 20 cases pass; all 20
linear-observation alternatives miss at least one target even at 1 ms. Preserve
these failures, not a relaxed tolerance or altered gate law. Local spectra and
short-horizon qualification do not justify an arbitrary long-time or multiscale
step size, or substituting GPU throughput for numerical accuracy.

MODEL-004 is now ready: preserve verified 0.5.0 source, then implement the pair
through existing state/mechanism/schedule/observation boundaries and validate JAX,
padding/identity, complete restart/branch behaviour and all five earlier models.
No physical EMT calibration, source-compatible contact, organ result or GPU
performance follows from this independent reference.

## D023: compose the qualified physical gated pair through the shared engine

Status: implemented as MODEL-004 / Cells 0.6.0, 2026-09-08, following the user's
approval to proceed. See the [run guide](BIOELECTRIC_PAIR.md) and
[acceptance](../reports/MODEL004_ACCEPTANCE.md). D021/D022 retain their historical
design/reference-stage accounts; their equations, panel and targets are unchanged.

Reuse the membrane laws and graph scatter with two fixed-volume cells, separate
membrane and edge capacities, one maintained bath and diagonal charge/capacitance
closure. Gate state and a single signed junction-transfer ledger are explicit.
Three dissipation integrals are checkpointed diagnostic history, not biological
inventory or feedback. Gate conformational energy/current/cost remains excluded.

Keep membrane leak/pump groups and prescribed junction inhibition independent.
Host resolution produces separate membrane/contact arrays in a control PyTree;
the generic checked engine supports these without an assay-specific branch.
The gate continues evolving while the junction is blocked. Capacities are storage
settings; topology and identity are biological definitions, and inactive padding
is neither inhibition nor deletion.

Use the independently qualified 1 ms RK4 bound and interval-held cubic sampling.
Require valid gates, amounts, both electrical domains and finite state at every
trial and accepted endpoint. Check whole-interpolant amount/gate/voltage extrema
and refuse nonfinite coefficients, even without interior requested observations.
No clipping or repair is allowed. Same-layout replay and observations are exact;
cross-capacity/orientation diagnostics may differ by floating reduction roundoff.

Preserve verified 0.5.0 before production edits and retain strict source/runtime
snapshot compatibility. Compare with frozen NUM-003 arrays, check a future-control
branch independently, and regress all five earlier models. No new runtime
dependency, physical EMT calibration, upstream code vendoring, source-assay
parity, organ implementation, multirate solver or GPU claim follows.

Next pin the complete source-compatible model and smallest coupled positive/
negative trajectory panel. Reuse these engine interfaces, but retain the source
algebraic gate, upwind approximation and explicitly nominal coordinate/time
contract. Representative graph/world profiling remains a separate M1 gate.

## D024: complete source-compatible state before source-assay implementation

Status: specified and instantaneously checked as SPEC-003, 2026-09-08, following
the user's approval to proceed. No production change: Cells remains 0.6.0.
See the [complete contract](SOURCE_EMT_PAIR_SPEC.md) and
[evidence](../reports/SPEC003_DESIGN_CHECK.md).

Pin a two-cell nominal-clock profile with three ionic and three regulatory
primary coordinates per cell, fixed P/Snail/inert ST context, pure reconstructed
binding caches, charge-derived voltage, source leakage/pumping and upwind contact
transport. Algebraic junction scales are parameters/readouts, not extra gate
memory. Keep source miRNA drift valence distinct from its excluded voltage charge.
Keep the source's base-permeability pump eligibility distinct from IC inhibition.
Reversing an asymmetric junction must also swap its hemichannel parameters if it
is intended as the same physical junction under another orientation.

Reuse complete previously captured E/M packets, not just endpoint labels or
regulatory triples. Preserve actual accepted preparation clocks and raw plotting
caches; explicitly import into a new phase with reconstructed diagnostics and
new accounting anchors. This is not a fresh equilibrium proof, source integrator
restart, or the continuing memory harness's prepared-state identity.

Freeze a small 14-case panel, full-state/route/control negative checks, and future
numerical targets before integration. Independent equations match 17 native
instantaneous control settings. NUM-004 must still qualify coupled paths, source
clock/refinement correspondence, observations and accounting before MODEL-005.
The cancer pilot's endogenous K expression, neighbor information access, and
contact expression strategies need their own additional profile checks.

Future production composes through generic stage, scatter, schedule, state,
checkpoint and observer boundaries; source quirks stay inside the named model.
Keep typed ionic/regulatory histories, no invented physical RNA charge or clock
mapping, no assay-specific runner branch and no automatically reused step bound.
Source, numerical, engineering and biological validation remain separate.

## D025: qualify nominal coupled paths without copying source timing artifacts

Status: independently qualified as NUM-004, 2026-09-08, following the user's
approval to proceed. Production remains Cells 0.6.0. See the
[numerical contract](SOURCE_EMT_PAIR_NUMERICS.md) and
[evidence](../reports/NUM004_REFERENCE.md).

Use RK4 with a maximum 0.01 source nominal-time step and extrema-checked cubic
observations for the frozen first profile. Radau, BDF and refined Radau agree;
all 14 cases pass at the selected step and its half. Integrate typed diagnostic
histories at the same stages, with no feedback; retain complete event carryover,
independent routes, reconstructed caches and explicit fixed context.

Native adaptive Euler has its own error budget and realized clock. Record the
exact integer-step updates and lagged caches. Compare every accepted primary
state against independent equations at the actual times, and separately measure
the state effect of delayed interventions. S12's original fine release at 0.1439,
requested at 0.137, fails the intended-schedule RNA tolerance. Preserve this
failure. Two predeclared further refinements pass without changing the tolerance;
the finest native release is 0.13755. Do not reproduce native overshoot in the
shared production scheduler merely to match a legacy requested-time endpoint.

MODEL-005 is now ready: preserve 0.6.0, implement the source-specific laws on
shared state/stage/scatter/control/observation boundaries, verify JAX and complete
replay/branches against frozen arrays, and regress all six earlier models.
The qualified short-horizon nominal step is not a physical calibration or a
multiscale timestep policy. Large-GPU, multirate and reduced-model choices still
require representative workloads and independent accuracy/accounting checks.

## D026: implement the nominal pair without source-specific engine branches

Status: implemented as MODEL-005 / Cells 0.7.0, 2026-09-08, following the user's
approval to proceed. See the [run guide](SOURCE_EMT_PAIR.md) and
[acceptance](../reports/MODEL005_ACCEPTANCE.md). D024/D025 retain their historical
design/reference-stage records; their equations, panel and targets are unchanged.

Keep ionic and regulatory primary coordinates separately typed. Checkpoint all
exchange and local-reaction histories without feedback, with fixed P/Snail/ST
context and accounting anchors. Reconstruct voltage, algebraic gate scales and
binding diagnostics purely; do not add voltage or gate memory. Source miRNA
transport valence does not become physical voltage charge.

Compose independently expressed source membrane/contact laws, the existing pure
EMT component and graph scatter at the same RK stages. Extend the shared host
control resolver with a named route axis so ionic and miRNA inhibition remain
independent. Preserve existing physical laws and control shapes. Runner, fixed
stepper, observation machinery and snapshot format need no assay-specific branch.
The strict configuration names a source parameter set, not a test-case identity;
biological IDs and independently padded capacities remain separate.

Use the qualified nominal maximum step 0.01, exact event splitting and checked
cubic observations. Validate trial states, endpoints, whole-polynomial primary
and voltage extrema, finite histories and typed accounting; never clip a failed
trajectory. Preserve native requested/realized clock evidence separately instead
of reproducing the legacy overshoot. New parameters or long horizons require
their own numerical qualification.

Preserve accepted 0.6.0 before editing production. Compare all 14 frozen paths,
complete restart and an independently solved future-control branch; verify all
six previous models, strict snapshot source refusal and archived replay. The
852-test suite passes and all 62 prior trajectories are exactly unchanged.
This accepts the bounded nominal model, not longer E02 switching, the cancer
expression strategies, memory/relay results, physical EMT calibration or organs.

Next exercise an explicit independent-world execution axis and bounded CPU
profiling before choosing GPU, multirate or coarse-grained optimizations. Keep
world-local state, IDs, schedules and histories separate, and require scalar
parity, resource limits and complete replay. Independent worlds are experiments,
not interacting organs; organ coupling still requires explicit exchange ports.

## D027: independent clocks and measured batching before vectorization

Status: implemented as CORE-004 / PERF-001 / Cells 0.8.0, 2026-09-08, following
the user's approval to proceed. See the [batch guide](INDEPENDENT_WORLDS.md) and
[acceptance/profile](../reports/CORE004_ACCEPTANCE.md). This adds an execution
capability, not an eighth biological model or an organ interface.

Make world identity explicit and namespace every cell, membrane, contact and
bath within its world. Stack compatible state/layout shapes and parameters,
but retain each world's own zero-anchored event grid, dt and clock. Taking the
union of unrelated intervention times would change otherwise independent RK4
paths. Mask terminal step storage without evaluating extra RHS calls; strip
padding before ordinary model observers and checks.

Use conservative compiled `lax.map` for this first policy, not unqualified
vectorization of guarded branches. The shared RK4 functions and all seven model
laws remain unchanged. Require scalar parity, world-order/ID independence,
no cross-world parameter/control effects, exact same-policy replay, and refusal
of invalid trials even when another world is already finished. Aggregate work
and array-storage estimates precede timeline/capacity allocation. They are not
hard process-RSS or compiler-memory limits.

Batch ownership wraps ordinary complete scalar snapshots, including diagnostic
history and per-world schedule positions. Reorder by stable world ID, not by
array-slot guesses. Resume uses saved definitions; future branches must pass
the existing per-world branch checks. No ordinary branch can add/remove worlds,
change models or rewrite past interventions. Scalar snapshot formats and
strict source/runtime compatibility are retained; preserve 0.7.0 before editing.

Acceptance passes 896 tests, 10 batch runs/44 worlds, all 14 frozen source cases,
complete replay and independently solved future branches. All 78 preceding scalar
trajectories and 3511 arrays are exactly unchanged. CPU profiles use 12 separate
workers, fixed 1/4/16-world graph/pair workloads and three warm measurements.
At 16 worlds, graph kernel/full-call ratios are about 2.19/1.22 in favor of the
batch; the source pair has about 1.16 kernel ratio but no overall gain. Smaller
batches are slower overall. These bounded shared-host measurements establish no
GPU, tissue-scale or universal batch speedup.

Next specify bounded-window execution and selectable recording, preserving
event-clock, observation and full-checkpoint semantics. Full traces grow with
worlds and steps, while host preparation/observers and output remain substantial
measured costs. Do not bypass checks to improve a benchmark. Vectorized guards,
GPU placement, distributed execution and fine/coarse biological coupling remain
separate qualifications; longer E02 and memory/relay assays remain science work.

## D028: bounded storage must preserve the complete numerical contract

Status: CORE-005a / VERIFY-009 / PERF-002 / Cells 0.9.0 implemented and verified,
2026-09-08, following approval to proceed. See the [window contract](WINDOWED_EXECUTION.md)
and [acceptance/profile](../reports/CORE005A_ACCEPTANCE.md).
Prove one-world windows first, then add independently clocked windowed cohorts
as CORE-005b. This is an execution/storage capability, not a new biological model.

Separate run recording policy from physics and restart state. Use the ordinary
RK4/observer path on bounded pieces of the existing event grid. Generate that
grid lazily, using exact float products and event positions; never restart a
local `t += dt` clock or silently introduce new solver boundaries. Keep every
diagnostic ledger and fixed reference in complete snapshots regardless of output
selection. Snapshot validity is distinct from a full-horizon recording budget.
Ordinary full-trace execution retains its own resource guard.

Support full, observation-only and checkpoint-only recording. Every interval and
configured observation is still checked. Preserve cross-window diagnostic/sample
continuity and reduce explicitly supported maximum diagnostics over the whole
run. Checkpoint requests must be accepted times, not dense-output samples.
Window size and recording may change on resume; biological changes use the
ordinary future-branch checks. Source/runtime compatibility remains strict.

Write bounded numeric chunks and an incremental hashed index; publish completion
last. Do not grow an in-memory trace or payload inventory with the horizon.
Metadata schedules remain resident, and array estimates are not hard RSS limits.
Preserve accepted 0.8.0 before edits; require old-source replay, exact saved
scalar/cohort regressions, failure tests and separate CPU memory/cost profiles.
No numerical law, observer formula, dependency or backend changes in this slice.

Acceptance passes 982 tests. All 78 prior scalar trajectories/3511 arrays and
10 prior batches/44 worlds/2042 arrays are exactly unchanged; 1777 serialized
windows preserve every baseline state and observation. All 434 accepted 0.8.0
snapshots load through the preserved archive, with exact old-source replay.

Twelve separate CPU profile workers show the intended memory/overhead trade-off.
The long 32-cell graph's 256-step history buffer is about 39× smaller but the
whole call is about 1.5× slower. The source pair has no throughput or general RSS
improvement. The first long full-trace profile's 64 MiB budget refusal is retained;
the completed comparison gives all modes the same explicit 128 MiB array budget,
without changing physics or production guards. Keep full execution useful for
small jobs; amortize preparation and prove windowed cohorts before GPU work.

## D029: bounded cohorts keep independent clocks and reuse prepared execution

Status: CORE-005b / VERIFY-010 / PERF-003 / Cells 0.10.0 implemented and verified,
2026-09-08. See [windowed worlds](WINDOWED_WORLDS.md) and
[acceptance/profile](../reports/CORE005B_ACCEPTANCE.md). Follows the user's approval
to continue.

Extend the existing guarded `lax_map` kernel across bounded execution rounds.
Each world advances through its own original intervals, retaining complete state,
typed diagnostic ledgers, layouts and global local-clock indices. Finished worlds
are masked without RHS evaluation. Do not union event times, synchronize biology,
or add model-specific execution branches. Prepare parameters and active masks
once per run, carry state on the device, and cache compiled full/tail widths within
the run. Ordinary host observers and numerical preflight still perform their work.

Share scalar-window analysis and numeric chunk writing; check every participating
world before exposing any of the round. Copy checkpoint endpoints so they do not
retain views of old history buffers. Aggregate array estimates include common-width
padding, overlapping rounds and observation continuity. Per-world and global work
limits still apply to the declared horizon on restart. Snapshot validity must not
require reserving a full trajectory; ordinary full-run guards stay in place.

One incremental cohort index identifies world and round. Save complete initial and
final cohorts and optionally every N completed rounds, with actual independent
clocks. Do not offer arbitrary common-time checkpoint queues in this bounded first
writer. Preserve strict scalar/cohort snapshot schemas and source/runtime checks;
archive accepted 0.9.0 before changes. Future branches use existing per-world
restrictions, with stable ID reordering but no implicit add/remove/couple operation.

No equation, observer formula, dependency, precision or backend change. Require
exact full-state/readout regressions, serialized round replay, whole-round failure
tests, archived replay and separately measured CPU costs. GPU mapping, distributed
execution, multirate/fine-coarse interfaces and organs remain additional gates.

Acceptance passes 1057 tests. All 78 scalar trajectories and 10 full batches are
exactly unchanged; 20 windowed cohort runs / 88 worlds pass serialized full-state
and observation comparisons plus complete round restart. Preserved 0.9.0 loads
342 accepted scalar snapshots and its ten cohort wrappers, with exact window
replay. An acceptance-fixture event-cursor mismatch was correctly refused and
retained; correction changed only the test fixture, not production guards.

Sixteen isolated CPU workers show roughly 3.9× smaller history buffers at width
256 and 30.4× at width 32, compared with full batches on the tested ten-unit
horizons. Width-256 cohorts finish faster than sequential scalar windows, but
slower than full batches; source-pair RSS does not improve. Keep both policies.
Next qualify a selected longer E02 protocol, preserving independent source
evidence and preparation criteria; a wider engine or GPU is not automatically
the next scientific requirement.

## D030: freeze the longer assay before generalizing the source graph

Status: SPEC-004 design and R006 source review complete, 2026-09-08. No production
change; Cells remains 0.10.0. See [E02-SW1](E02_SWITCHING_PROTOCOL.md),
[prospective numerics](E02_SWITCHING_NUMERICS.md) and
[design evidence](../reports/SPEC004_PROTOCOL_CHECK.md).

Select the smallest topology demonstrated in the completed source neighbour
pilot: one recipient, two freely evolving donors. Use fresh isolated full-model
500-unit preparation, then 1000-unit contact at fixed per-edge miRNA diffusion
`2e-15`, both directions and six controls each. Freeze phenotype and full-state
preparation checks, continuous readouts, finite-window labels, source-clock
differences and numerical uncertainty before any assay integration. No label
or preparation extension may be tuned to manufacture switching.

The native historical helper's preparation, inherited ionic context, plotting
endpoints and distance predicate differ. Treat this as an independent
source-equation protocol, not exact threshold reproduction or post-removal
memory. No generated full prepared packets or long-time candidate exist yet.

The current pair cannot emulate the star by padding or independent batching.
NUM-005 must first qualify independent fixed-graph assembly, source instantaneous
witnesses, full preparation and long trajectories. Then MODEL-006/VERIFY-011 can
extend the named source profile using per-cell processes once, reciprocal edge
scatter, typed ledgers and existing execution/checkpoint infrastructure. Preserve
pair@1 and all earlier-family behavior; keep assay predicates outside the engine.
ASSAY-002 follows those gates and records negative/unresolved outcomes honestly.
Organ presets, interacting organs, physical EMT mapping and GPU remain later.

## D031: independently check source graph composition before long integration

Status: NUM-005a implemented and checked, 2026-09-08; production remains 0.10.0.
See [reference contract](SOURCE_EMT_GRAPH_REFERENCE.md) and
[acceptance](../reports/NUM005A_REFERENCE.md). NUM-005 itself remains in progress.

Generalize the independent reference, not the production runner: one local
regulatory/membrane evaluation per cell, then an explicit loop accumulating
reciprocal per-edge transport. Preserve all source constitutive laws and the
30-coordinate one-edge reduction; use `13*N + 4*E` typed reference coordinates
for general fixed graphs. Do not sum full pair RHSs, rescale coupling by degree,
invent donor clamps or read phenotype labels in the dynamics.

Pin complete inputs and native source identity before capture. Check one-cell,
pair, star, chain, permutations, reversed hemichannels, disconnected components,
independent controls, diagnostic ledgers and invalid state/evidence. Label E02
construction seeds explicitly, without claiming prepared packets. The 45 native
derivative cases and 17 pair reductions pass; the initial diagnostic collector
indexing error remains a separate failed attempt, corrected without a physics,
input or tolerance change. No upstream implementation is redistributed.

Split the remaining qualification into bounded preparation (NUM-005b) and long
E02 trajectories/candidate selection (NUM-005c). Neither static derivative
agreement nor tangent bookkeeping selects a solver or qualifies long-time
behavior. Keep the frozen SPEC-004 protocol and numerical documents unchanged;
new evidence lives in separate reports. MODEL-006/VERIFY-011 and ASSAY-002 stay
behind the full numerical gate. Organ/fluid/multiscale physics and GPU remain
additional model and numerical decisions, not implied by the graph extension.

## D032: bounded independent preparation and explicit qualified-state transfer

Status: NUM-005b complete, 2026-09-08; numerical/packet gate, independent artifact
audit and all 1243 tests pass. Production remains 0.10.0.
See [reference guide](SOURCE_PREPARATION_REFERENCE.md) and
[measured preparation evidence](../reports/NUM005B_PREPARATION.md).

Keep the graph equations, implicit integration, observer criteria and artifact
audit separate. A live Radau/BDF solver crosses 256-step recording boundaries
without resetting adaptive history or reanchoring physical state. Retain complete
increment/history snapshots and actual dense-polynomial coefficients in hashed
chunks, with constant-size streaming comparison buffers. These snapshots do not
claim exact restart of private adaptive-solver state.

Check primary, affine electrical and accounting-residual extrema over every
polynomial interval, and independently check the Jacobian stencil and dense
coefficient adapter. Compare all reference grids, midpoints and observer times,
including passive histories and reconstructed binding caches. Keep the frozen
scientific budgets and preparation duration unchanged; no label enters the RHS.

Qualify and hash full 500-unit E/M endpoints only after all methods and observer
criteria pass. Preserve preparation histories and source/clock/solver provenance;
a later assay imports exact primary/context arrays into a new world with zero
assay ledgers. This is an explicit phase transfer, not an ordinary restart or an
equilibrium/replication claim. Observed ionic drift remains visible even where
regulatory labels are stable. Incomplete, numerically refused and biologically
negative outcomes remain different statuses.

NUM-005c still owns connected long-path references, RK4 candidate selection,
selected/half-step qualification and candidate-owned preparation continuations.
No production graph, new integrator dependency, fluid module, multirate physics
or GPU implementation follows implicitly from passing this preparation gate.

## D033: lossless long-reference evidence before candidate qualification

Status: NUM-005c1 infrastructure implemented; first scientific session capped,
2026-09-08, with eight qualified conditions and six still incomplete. Production
remains 0.10.0. See the [long-reference guide](SOURCE_GRAPH_PATHS_REFERENCE.md)
and [session evidence](../reports/NUM005C1_LONG_REFERENCE.md). Independent subset
auditing and all 1287 tests pass, including 44 new checks.

Split NUM-005c into long implicit references/readouts (c1) and the registered RK4
study, selected/half-step qualification and candidate-owned continuations (c2).
This is a work boundary, not a change to E02-SW1, its error budgets, stopping
rules or production prerequisites. A stopped session is never extended silently.

Copy exact qualified preparation primary/context arrays into each new graph,
with zero new assay ledgers and full parent history/provenance retained. Use the
same graph equations, independently checked stencils and dense-curve checks for
all 14 conditions. Keep old numerical sources and evidence immutable.

Separate a new bounded recorder from the numerical method. Lossless compressed
chunks preserve dtypes, accepted states, full coefficients and exact carries;
short tests require identical numerical paths with the earlier recorder. Budget
the uncompressed next batch conservatively against the unchanged 1 GiB limit,
with reserved metadata space. Do not replace full evidence with endpoint-only
data to make a long run fit.

Cross-compare all three implicit settings over complete union grids before
interpreting reference readouts. Preserve uncertain labels, sampled-time
brackets/censoring, donor changes and complete-state drift. Desired switching
does not enter the integrator or numerical pass condition. A separate read-only
audit checks complete evidence and independent graph accounting; failed campaigns
receive integrity-only audits. No GPU, fluid or production graph change is implied.

## D034 — Continue a capped reference campaign with immutable imports

2026-09-08. The user approved continuing NUM-005c1 after the first session reached
its registered cap. Add an explicit, separately registered continuation for the
six remaining conditions. Reuse only the eight trios covered by the hash-pinned
complete-subset audit, after rechecking all old payloads and identities. Preserve
the old root and all 25 original source dependencies unchanged.

The interrupted M-to-E blocked/Radau trajectory is a new attempt from time zero,
not an adaptive checkpoint resume. Derive order from the original attempt list.
Keep the 3600-second session and all per-trajectory limits. The 1 GiB artifact
quota covers both sessions, including the old partial attempt; give unchanged
new-root writers only the explicitly registered remaining allowance. New source
capsules include the continuation, audit and short tests before any integration.

A composite receipt maps all 14 conditions to their original evidence locations.
Independent auditing reuses the pinned old full-subset audit and checks every
new complete dense path, comparison grid and observer record. An incomplete
continuation cannot close c1, and c1 cannot close the later RK4 gate. Production
0.10.0, equations, tolerances and scientific protocol remain unchanged. See the
[continuation guide](SOURCE_GRAPH_CONTINUATION.md).

2026-09-09 outcome: the continuation stops at the unchanged reference-agreement
gate after nine new complete paths. Blocked and ionic-only qualify; miRNA-only
has a regulatory disagreement of 0.2263 versus the 0.1 limit, involving BDF
against both Radau references. Same-state, one-neighbour and isolated were not
started. All nine new dense paths pass the independent domain/accounting audit,
and a read-only saved-sample check reproduces the regulatory maxima. That audit
does not overturn the failed accuracy gate. Any refinement trial requires a
named amendment; no automatic retry or threshold relaxation is made.
All 1314 tests pass, including 24 continuation and three diagnostic tests;
production 0.10.0 and all prior registered sources remain unchanged.
See the [retained continuation report](../reports/NUM005C1_CONTINUATION.md).

## D035 — One preregistered BDF refinement diagnostic

2026-09-09. The user approved the proposed tighter BDF reference check after
D034's retained regulatory disagreement. [E02 A1](E02_BDF_REFINEMENT_A1.md)
authorizes one new 1000-unit miRNA-only BDF trajectory with both tolerances
multiplied by 0.1. Equations, exact initial state, maximum step, Jacobian strategy,
reference error thresholds and resource limits are unchanged. The original
unqualified BDF and both audited Radau paths remain immutable inputs.

Compare all four paths on their complete union grid; retain all six pairwise
comparisons. The required sensitivity comparisons are each Radau against tighter
BDF and the two Radau settings against each other. A pass is diagnostic agreement,
not automatic reclassification of the original trial, an increased original
panel qualification count, a biological result or permission to run remaining
controls. A failure stops without further refinement.

Use an explicit multi-root reader mapping and close reader streams on all exit
paths. Budget old and new artifacts together under 1 GiB. The new directory is
outside the closed campaign's sibling inventory but receives only the aggregate
remaining bytes. Archive inputs and implementation before running. Independently
audit the new dense path, union grid, source-sampled states and primary/history
scores. No production, RK4, GPU or fluid implementation is included.

The single trial meets its registered agreement target: 0.005334691340757373
against 0.1. The original BDF discrepancy remains at about 0.226 on the expanded
grid. Independent auditing passes without changing the original qualification
count. The next reference-policy/remaining-control decision stays separate;
see the [A1 report](../reports/NUM005C1_A1_BDF_REFINEMENT.md).
All 1337 tests pass, including 23 A1 checks. The registered 35-file source capsule and
all earlier evidence remain intact; production stays at 0.10.0.

## D036 — Adopt A2 reference policy and complete the remaining panel

2026-09-09. The user approved the next recommended step. [E02 A2](E02_REFERENCE_POLICY_A2.md)
explicitly accepts the audited tighter-BDF path with the two original Radau paths
for reverse miRNA-only, using the pinned A1 required-pair comparison and new
reference-only observers. The original failed trio and A1 diagnostic receipts
remain unchanged. Ten original qualified cases keep their original settings.

Register same-state, one-neighbour and isolated controls in that order, each with
Radau, refined Radau and tighter BDF, before observing their outcomes. All three
pairs must meet unchanged numerical targets; a nonswitch is not failure. This is
an explicitly mixed-setting, accuracy-qualified panel, not a uniform-settings
study or retrospective success claim for the original campaign.

Use explicit per-case trajectory/comparison/observer manifests and reader
lifetimes. Keep the original one-worker CPU, one-hour session and aggregate 1 GiB
limits, including all old partial/failed evidence. Nine new paths only; stop at
any failure without retry or threshold change. Independently audit new dense
curves, saved-state identity, comparison scores and observers, preserving earlier
source capsules. Only a complete audited 14-case A2 panel closes NUM-005c1;
RK4 selection, production graph/assay work and biological validation stay separate.

Outcome: all nine new paths and the three new comparisons pass, with maximum
scores 0.00257, 0.00483 and 0.00510 against 0.1. The adopted case's observers
complete the 14-case panel. Its independent audit checks every new dense path,
comparison sample/state and all four new observer sets; maximum new dense
accounting residual is 3.41e-12 against 2e-9. The scientific session takes
1087.264 seconds and aggregate retained artifacts occupy 715,966,189 bytes,
including original partial/failed attempts. NUM-005c1 qualifies under A2, without
reclassifying the original campaign. All 1362 tests pass, including 25 new A2
checks; all 39 production source hashes and prior evidence remain unchanged;
see [A2 evidence](../reports/NUM005C1_A2_REFERENCE_PANEL.md).

## D037 — Bounded checked RK4 engineering before the long candidate study

2026-09-09. The user approved the recommended short-fixture engineering step.
[NUM-005c2a](E02_CANDIDATE_ENGINEERING.md) implements the fixed-control graph
candidate with lazy global clocks, complete accepted checkpoints and exact
restart identity. Every stage and whole cubic curve retains the existing domain
and accounting checks. Use explicit selected-reference trios and bounded union-grid
comparison batches; close all readers on success and failure.

Register six existing study inputs, each for 5.12 units at 0.01, at recording
widths 16 and 256. Retain full short-path states, five slopes, cubics and all
comparison samples, then audit numerical identity across widths independently.
Measure the complete checked path, array estimates, process RSS and stored bytes.
Include accepted preparations as well as all old reference/failed artifacts in
the unchanged 1 GiB aggregate quota. No automatic retry or refinement.

This is an engineering and resource-preflight result, not long-time accuracy,
a timestep selection or production acceptance. If full evidence and checked
execution do not fit the long-study caps, record that result and propose a
separate optimization/evidence-policy decision. Preserve all accepted capsules;
no production, GPU, native long driver or biological validation change.

Outcome: all twelve short profiles and the independent audit pass. Widths 16
and 256 have identical ordered binary64 numerical evidence, maximum normalized
disagreement 0.00354 against 1, and maximum independently checked accounting
residual 1.42e-14. The session takes 137.557 seconds and combined retained
artifacts occupy 783,644,175 bytes. All 1415 regression tests pass in 612.40
seconds, including 53 new tests; all 169 targeted checks pass.

The preflight does not establish a long-study resource fit: the width-256
short-rate estimate is 12.70 hours and 11.47 GB, with no guarantee that initial
transient costs or compression persist. Next optimize repeated diagnostics and
specify a compact auditable evidence policy, then reprofile before a long-study
decision. No cap, tolerance, equation or source capsule was relaxed.
See [D037 evidence](../reports/NUM005C2A_CANDIDATE_ENGINEERING.md).

## D038 — Optimize diagnostics with a frozen numerical baseline

2026-09-09. The user approved the next recommendation after D037. Implement
[cached, bounded batched readouts](E02_DIAGNOSTIC_OPTIMIZATION.md) for the
independent fixed graph, using the frozen scalar evaluator as the differential
oracle. Batch only observation samples and cache only static graph/control
data. Preserve equation expressions, edge accumulation order, input domains,
all eight scientific comparison targets and the complete RK4 path.

Register one scalar and one batched profile for each of D037's six short inputs,
all at width 256. Both retain full state/stage/cubic/sample evidence and new
readout fingerprints; numerical path and sample arrays must match D037 exactly.
Independently recompute the saved readouts and eight comparison scores. Use
existing NUM-005a instantaneous tolerances for readout equivalence and report
bitwise identity separately. No silent fallback, retry or threshold change.

Keep the original one-worker, wall/array and shared-artifact limits, counting
D037 and all earlier accepted/failed artifacts. Measure complete checked calls
as well as readout/cache sections. Faster diagnostics do not by themselves
qualify the long study or change the retained-evidence policy.

Record [compact-evidence options](E02_COMPACT_EVIDENCE_DESIGN.md) as an
unimplemented proposal. Complete restart state is mandatory under every future
policy; hashes alone cannot independently verify omitted calculations. A later
storage implementation needs separate reconstruction/failure tests, audit and
resource preflight. No production, dependency, GPU, fluid or organ change.

Outcome: all twelve profiles and the expanded 266-payload/55-source audit pass.
All saved integration/sample arrays match D037 exactly; all six readout fields
are bitwise exact against scalar evaluation. Complete checked time totals
38.719 seconds scalar versus 21.057 batched (1.84×); readout time is 17.902
versus 0.209 seconds. One measurement per combination is not a statistical
benchmark. All 335 targeted tests and the full 1540-test suite pass, including
125 new checks; full-suite time is 619.79 seconds with warnings treated as errors.
Prior sources and all 39 production hashes remain unchanged.

Aggregate artifacts are 803,085,279 bytes. Short-rate batched planning estimates
of 7.09 hours and 11.505 GB do not establish a long-study fit. Recommend a bounded
lossless-redundancy prototype with exact reconstructed-evidence auditing next;
the proposal remains unimplemented, with no automatic evidence-policy adoption,
resource extension or long run. See [D038 evidence](../reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md).

## D039 — Prototype lossless evidence with explicit checkpoint publication

2026-09-09. The user approved D038's next recommendation. Implement the
[short lossless-recording contract](E02_LOSSLESS_EVIDENCE.md): full trace versus
an RK4 basis retaining all stage slopes, complete window endpoints and clocks.
Reconstruct redundant state/cubic arrays in pinned arithmetic, requiring exact
logical bytes before publication. Keep every D038 comparison sample/readout
fingerprint and all numerical thresholds; do not edit the frozen kernel.

Use a separate reference runner with explicit evidence policy and a hash-linked
commit boundary after payload synchronization and completed comparison. Apply
the existing score/accounting limit at each boundary; this changes failure
publication timing, not successful integration or acceptance thresholds.
Closed committed prefixes are restartable across policy/width changes under the
same numerical identity. Failed/unclosed/partial evidence is never implicitly
promoted; preservation attempts are independent and do not retry a failed write.

Register twelve matched short CPU profiles under the unchanged aggregate caps,
including every prior root. Independently decode/audit reconstructed curves,
samples and readouts, and compare ordered evidence exactly to D038. Measure
full checked and offline audit costs as well as size. This is a prototype, not
adoption of a compact long-study policy, timestep selection or production change.

Outcome: all twelve profiles and the independent 266-payload/62-source audit
pass. Decoded ordered trajectories/samples exactly match D038; every saved
readout is bitwise scalar-equivalent. The basis saves 57.8% of compressed
trajectory payloads and 16.7% of complete profile evidence, with essentially
unchanged checked/audited runtime. All 1707 regression tests and 384 targeted
tests pass, including 167 new checks. Aggregate retained artifacts are
821,019,434 bytes; prior sources, production and budgets remain unchanged.

Comparison artifacts now occupy 83.4% of basis-profile evidence. Recommend a
separate lossless reference-backed comparison-record prototype with exact
reconstruction and dependency auditing next; it is not yet implemented or
adopted. Long-study resource fit is still unestablished, and runtime needs
separate work. See [D039 evidence](../reports/NUM005C2C_LOSSLESS_EVIDENCE.md).

## D040 — Lossless reference-backed comparison records

2026-09-09. The user approved D039's next recommendation. Implement the
[bounded comparison-recording contract](E02_COMPARISON_RECORDING.md): full versus
trajectory-backed sample arrays with every clock, flag, state/readout digest
and score retained. Bind immutable reference dependencies and the already-written
candidate window before the unchanged D039 commit boundary. Numerical carries
stay complete and independent of output representation.

Add explicit dependency-aware closed-prefix reading/restart, exact online and
independent offline reconstruction, corruption/allocation/failure tests and
twelve matched short profiles. Keep all prior evidence, equations, production
and original caps unchanged. Report complete checked/audited cost and remaining
resource gates; this is not adoption of a compact long-study policy or authority
to launch the long candidate study.

Outcome: all twelve short profiles and the independent 290-payload,
68-source audit pass. Logical trajectories/samples exactly match D039, and
all saved readouts remain bitwise scalar-equivalent. Comparison payloads shrink
98.5%, total profile evidence 80.6%, with 4.2% more checked time in these single
matched observations. All 1903 regression tests and 541 targeted tests pass,
including 196 new checks. Aggregate retained artifacts are
831,126,114 bytes, with all prior sources and production unchanged.

Recommend profiling/caching integration-side graph evaluation next, beginning
with exact complete-RHS probes and preserving all stage/domain/accounting and
whole-curve checks. This is not yet implemented or adopted. Trajectory storage
remains a separate resource gate; no evidence reduction, replay-only policy,
budget extension or long launch follows automatically. See
[D040 evidence](../reports/NUM005C2D_COMPARISON_RECORDING.md).

## D041 — Immutable scalar evaluation with independent stage checks

2026-09-09. The user approved D040's recommendation. Profile the complete scalar
RHS and test an immutable per-model cache through the unchanged checked runner.
The [evaluation contract](E02_INTEGRATION_EVALUATION.md) keeps all state and
controls explicit, preserves all stage/domain/accounting and whole-cubic checks,
and retains the complete lossless D039/D040 evidence and publication rules.

Require exact instantaneous complete derivatives and decomposed fields before
twelve matched short profiles. Bind the evaluator revision/policy and model
digest into numerical identity; do not infer cross-evaluator restart authority
from finite probes. Add independent frozen-equation recomputation of every
recorded RK4 stage/endpoint slope. Measure cache preparation, complete checked
execution, extra audit cost, storage and RSS separately from microprofiles.

Outcome: all twelve profiles and the 304-payload/74-source independent
audit pass. All 1,440 complete-RHS probes, 720 decomposed evaluations and 30,720
recorded complete stage derivatives are bitwise exact against the frozen
equations. RHS time falls 13.9%, checked runtime 2.9% and checked-plus-audited
runtime 0.9% in these single matched observations. All 2178 regression tests and
816 targeted tests pass, including 275 new checks. Aggregate retained artifacts
are 834,874,394 bytes. The short-only implementation and closeout are complete.

All prior sources, production and caps remain unchanged. Recommend profiling
unchanged validation and independent-audit costs next, then specifying bounded
static validation reuse where measurements justify it. No check reduction,
long candidate study or compact long-policy adoption is authorized. Trajectory
storage remains a separate resource gate. See [D041 evidence](../reports/NUM005C2E_INTEGRATION_EVALUATION.md).

## D042 — Begin an experimental benchmark and pause optimization

2026-09-09. After reviewing current functionality, CPU performance and the future
GPU path, the user approved beginning a first biological benchmark. Pause further
optimization/GPU work and defer the unfinished long NUM-005c2 campaign. Retain
all existing evidence, numerical checks and resource gates; no study is declared
complete or implicitly authorized by this priority change.

[BIO-001](BIOLOGICAL_BENCHMARK_001.md) selects a provisional RPTEC/TERT1 endpoint
pilot from Bonzanni et al. 2020. Preserve both conflicting C4/C5 input columns
and quarantine those conditions. Retain original licensed figures, three coarse
voltage estimates, unknown numerical SEM, cell/experiment counts and a
retrospective C1/C2 fit / C3 evaluation split. It is not a blinded experiment,
raw dataset, time course, fitted model or biological acceptance result.

The current physical-cell model is not an automatic match: the experimental
bath contains divalent ions and whole-cell recording introduces an intracellular
boundary uncertainty. A pipette recipe is not a free-ion measurement. Changing
chloride to satisfy the old three-ion schema, tuning initial voltage to the
evaluation result, or silently adding an active chloride route is prohibited.
The Costa/BETSE lead remains useful but has a separate chloride-homeostasis gap.

Next BIO-002 should specify a reusable conditioned-response reference and a
small descriptive comparator, followed by new-regime numerical qualification
if a production extension is justified. Unknown measurement uncertainty prevents
a quantitative biological pass/fail criterion at this stage. Source/data
integrity tests do not substitute for that evidence. See the
[curation report](../reports/BIO001_DATASET_REVIEW.md).

## D043 — Keep the first endpoint fit separate from production cell dynamics

2026-09-09. Following the user's approval, complete BIO-002 as a small
conditioned electrical-response reference beside the production simulator.
The [protocol](../configs/reference/bio002_conditioned_voltage_v1.json) and
[equation/boundary specification](CONDITIONED_VOLTAGE_REFERENCE.md) precede
calculation. Preserve BIO-001's exact data and retrospective split: fit only
C1/C2, predict C3 without its observed voltage, and retain C4/C5 quarantine.

Fixed unknown internal ions, fixed relative permeabilities and the constant
external Na+K/Cl series reduce the passive monovalent GHK relation to
`exp(V/V_T) = a + b K_external`. Fit two effective coefficients only; do not
claim unique permeabilities, ion concentrations or a physically identified
cell. Divalent bath charge is explicit while divalent, pump and intercellular
currents are omitted in this approximation. No pipette free-ion values,
dynamic reservoir, voltage anchor or assay-specific production branch is added.

Propagate all four C1/C2 reading-box corners, using the same C1 value for each
fit and voltage-change baseline. Reject an invalid log-domain corner; do not
clip it or narrow the box. Compare with the approximate C3 reading and an
unchanged-C1 baseline. Reading bounds are not SEMs, confidence intervals or a
biological threshold. All results remain descriptive.

The [completed calculation](../reports/BIO002_CONDITIONED_VOLTAGE.md) predicts
-14.59 mV versus approximately -18 mV, with a reading-bound prediction range
of [-18.32, -11.20] mV. All 63 targeted tests and 12 independent Decimal
arithmetic comparisons pass; the previous full 2,178-test suite was not rerun.
Production remains 0.10.0 with the same 39 source files and seven models;
the original dataset and curation metadata are unchanged. No retuning follows
the C3 result. BIO-003 reviews measurement uncertainty and boundary support
before a biological criterion or separately qualified production extension.
D042's optimization/GPU pause and unfinished long E02 gates remain in force.

## D044 — Close the endpoint pilot without promoting biological acceptance

2026-09-09. The user requests a bounded closeout before returning to
architecture. BIO-003 completes that review: the original one-page supplement
contains temperature and dye-stability plots, not C1-C3 numerical summaries or
experiment-level records. Article methods confirm whole-cell zero-applied-current
recording, but do not establish the fixed internal composition/current omissions
used by our comparator or absence of intercellular coupling.

[Close BIO-001 through BIO-003 as descriptive](../reports/BIO003_PILOT_CLOSEOUT.md).
Retain `biological_acceptance: not_assessable`; do not tune to C3, digitize new
targets into the old dataset, choose an after-the-fact acceptance threshold or
keep an open-ended search running. The original result, inputs, exclusions,
code and artifacts remain unchanged. The 63 targeted tests pass again; no
dynamic-cell validation or current full-suite result is claimed. Reopening needs
new evidence or a separately scoped benchmark.

## D045 — Target BETSE scientific coverage through modular multiscale execution

2026-09-09. The user confirms the long-term ambition to reach/exceed BETSE-level
capabilities using Cells' multiscale design, with parallel GPUs later. Adopt
the [v1.5.0 capability roadmap](BETSE_CAPABILITY_ROADMAP.md) and
[execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md). They specify
scientific capability families, not achieved parity, legacy GUI/file-format
compatibility or permission to reinterpret prior acceptance results.

Retain Python/JAX and pure array state. Separate species/compartment/membrane/field
ownership, physical laws, resolution, numerical coupling and device placement.
Treat fixed Na/K/Cl, one membrane, constant geometry and RK4 as current bounded
model choices, not universal assumptions. New physical closures, kinetic laws,
field/implicit solvers and stochastic processes each require independent cases
and versioned contracts. A generic array mapping is not scientific compatibility.

Support selectable detailed/reduced representations with typed conserved ports
and declared hidden-state mappings. Qualify static fine/coarse coupling and
multirate interfaces before adaptive resolution. Preserve the material, charge,
energy and relevant history required by the chosen mechanisms; matching mean
voltage alone is insufficient. Region or organ identity is not device ownership.

Plan separately for independent-world GPU ensembles, one spatially partitioned
interacting world, and coupled organs. Partitioned execution needs single-owned
fluxes, stage/iteration-correct halo exchange, global field/constraint work,
coordinated failure and a common committed checkpoint. Later multi-host work
must preserve collective ordering. JAX sharding is a candidate implementation
mechanism, not automatic domain decomposition or a distributed solver.

The next task is [SPEC-005](MULTISPECIES_MEMBRANE_NEXT.md): a one-cell
multispecies membrane specification and independent instantaneous reference,
then NUM-006 trajectory qualification and CORE-006 production assembly with
new identities. Old model versions remain unchanged. Add channels/graphs,
fields, compartments, water/mechanics and multiscale organ presets in stages.

This decision changes the active priority to architecture and restores explicit
future GPU planning. It does not start GPU implementation, performance work,
a BETSE execution, a full feature port or the deferred long E02 campaign.
GPU-001/002/003 own later device qualification; no hardware/speedup is selected.
Existing source E02 numerical/resource gates and M1/M1c requirements remain
unfinished and visible, independent of the new physical-model work.

## D046 — Generalize charge and membrane bindings before production dynamics

2026-09-09. Following the user's approval, complete SPEC-005 as a bounded
[physical/data contract](MULTISPECIES_MEMBRANE_SPEC.md), frozen synthetic panel
and [independent instantaneous reference](../reports/SPEC005_DESIGN_CHECK.md).
Keep one fixed-volume cell, one fixed membrane and one maintained bath. The
reference schema is separate from existing model/configuration identities.

Species records declare valence; transport mechanisms bind by stable ID, not
storage position. Explicit signed fixed charge and initial voltage must agree
with the amount anchor; inconsistent definitions fail instead of rebalancing
chloride or changing fixed charge. Maintained bath background charge is explicit
support, not a finite inventory or inferred chemistry. An inactive transport
route retains its species' amount, electrochemical domain and charge.

Resolve ownership and named constant-field/Na-K pump laws into immutable aligned
tuples before scalar evaluation. Do not introduce arbitrary expression/plugin
dispatch, a general membrane-surface closure, calcium signaling or a GPU layout.
The Na/K/Cl reduction and deliberately specified divalent case pass all 1546
instantaneous checks; all 352 targeted tests pass, including 113 new tests.
Cases, physical specification and tolerances retain their pre-evaluation hashes.
A receipt metadata path error was corrected and recorded; no physical target
was changed. All 39 production sources remain unchanged, as do the closed pilot
and historical evidence.

NUM-006 now owns a predeclared small trajectory/resource panel, independent
CPU methods and refinement, positive internal-stage states, event/observation
semantics and material/charge/energy histories. The new valence/kinetic regime
does not inherit the old RK4 timestep. Only after qualification may CORE-006
implement a newly identified CPU/JAX assembly and complete restart acceptance.
Parallel-GPU/multiscale design remains active, implementation stays later,
and the unfinished E02/long-campaign gates are not bypassed.

## D047 — Qualify a bounded multispecies method before the JAX assembly

2026-09-09. Continue from completed SPEC-005 to NUM-006, retaining the exact
physical inputs and existing production identities. The
[prospective numerical protocol](MULTISPECIES_NUMERICS.md) freezes fourteen
short cases, solver/timestep ladders, species-specific errors, accounting limits
and one-worker/time/output caps before evaluation.

The [completed session](../reports/NUM006_REFERENCE.md) passes all 84 attempts:
Radau/BDF/refined Radau in independently implemented hyperbolic increment
coordinates and three absolute-amount RK4 probes using the independent Bernoulli
reference. The declared rule selects 0.01 s with interval-held-control cubic
observations, backed by 0.005 and 0.0025 s refinement. Worst observed voltage
error is 5.243e-8 V against 1e-6 V; material, charge, energy, positive stage states,
candidate cubic-domain bounds and off-grid/sub-step controls pass.

This is narrow reference qualification, not an inherited or global timestep
guarantee. The old model's numerical limits do not change. Actual source code,
cases, native/dense data, comparisons and receipts are retained; no candidate
failure or scientific retry was needed. The session takes 69.882 s and 38264835
bytes within its declared caps, neither a throughput nor GPU benchmark.

The read-only audit reproduces 547572 sampled rows across 84 arrays and checks
186 payloads/13 archived sources. Its revision 2 additionally binds the session
protocol and solver settings to frozen sources. Preserve the initial audit and
archived original auditor; report the independently strengthened auditor's new
identity rather than changing that capsule. Only auditor-source drift is allowed;
numerical code, original tests, physical/numerical inputs and dependencies retain
their identities. Four corruption tests cover the added provenance checks.
No trajectory was rerun or changed for that audit improvement.

All 446 targeted tests pass, including 94 new tests. The 284 captured pre-existing
files, including all 39 production sources, stay unchanged. CORE-006 is now the
next implementation: a new CPU/JAX multispecies model identity through the shared
engine, pure array parameters, complete controls/observations/checkpoints and
acceptance against the frozen reference. Production remains 0.10.0 until then.
No biological acceptance, dynamic calcium mechanism, organ hierarchy, GPU
implementation, optimization or deferred E02 campaign is implied by this result.

## D048 — Add a new multispecies production identity and preserve old contexts

2026-09-09. The user's approval advances CORE-006 from the completed SPEC-005
and NUM-006 references to `multispecies_membrane@1` in Cells 0.11.0. Reuse the
existing pure dimensioned laws and the shared guarded RK4, sampling, recording,
scalar/cohort and restart paths. The [production guide](MULTISPECIES_MEMBRANE.md)
defines species/valence arrays, role-bound pump stoichiometry, explicit fixed
and maintained background charge, diagnostic energy history and complete anchors.

Host definitions retain stable string labels. Numeric device layouts carry
explicit local label codes and aligned parameter arrays; the complete definition
and summary dictionary preserve their meaning. Species count participates in
control shapes, conservative working-memory estimates and batch compatibility.
No arbitrary expressions, per-cell Python dispatch or organ-name branch is added.

Material accounting tolerances are explicit per-species execution data, not
species-name conditionals in physics. NUM-006's frozen limits independently
govern acceptance. The 0.01 s actual-step ceiling applies to the new family;
qualification remains limited to its two fixtures/fourteen schedules, not all
legal configurations. The old physical cell/pair keep 0.005/0.001 s limits.

Archive accepted 0.10.0 **before** production edits. Its 39 modules and original
NUM-006 audit environment are authenticated by the
[preservation receipt](../reports/core-006-preservation.json). Old checkpoint
replay uses old source; current readers refuse implicit migration. Historical
reference tests must also use their original source/packaging and CPU/thread
context. Isolate their workspace with real temporary file copies; do not relax
source identity, confinement or no-links guards. Current production tests run
separately against 0.11.0. [Retained engineering attempts](../reports/CORE006_ACCEPTANCE_ATTEMPTS.md)
record the initially incorrect single-context test run and linked-workspace
attempt, plus the interrupted first acceptance session.

[Production acceptance passes](../reports/CORE006_ACCEPTANCE.md): 43 scalar
original/restart/branch outputs and four cohort outputs, both eager and JIT
across the frozen panel, independently checked readouts/accounting, exact
fresh-process restarts and a future branch reducing to the frozen passive case.
All 78 older scalar trajectories/1777 windows and ten batches/44 worlds remain
exact. The read-only audit authenticates 773 payloads and 60 captured source/input
files; all 2565 tests pass (1594 current, 971 preserved-reference, no skips).

The proposed SPEC-006 slice is one state-bearing physical membrane channel
with an independent voltage-step/relaxation reference. This does not authorize
a general physical graph, finite bath, calcium network, GPU implementation,
optimization or the deferred long E02 campaign. The first biological pilot
remains closed/descriptive, with no refit or change in biological acceptance.

## D049 — Specify one two-gate membrane channel before coupled implementation

2026-09-09. The user's approval advances SPEC-006, not a channel catalog or a
production change. Select the `Kv1p5` continuous m/h parameterization at the
already pinned BETSE v1.5.0 commit. [R010](SCIENTIFIC_BASIS.md#r010-first-membrane-channel-source-review)
records source units/update semantics and the primary abstract's evidence limits.
The [contract](VOLTAGE_GATED_CHANNEL_SPEC.md) adopts no fixed reversal-voltage
transport law, native semi-implicit update, automatic gate equilibrium or
unqualified temperature correction. Production remains Cells 0.11.0.

Keep both gates as primary dimensionless state and their product as a readout.
Bind permeation to an explicitly named +1 species; keep the channel's transfer
ledger separate from baseline leak and pump histories. Abundance, permeability,
area and external availability do not substitute for kinetic state. Inhibition
zeros only that route's permeation; real disabled gates remain present and obey
the same domain checks. No clipping or silent reconstruction from current V/m h.

Prescribed voltage is solely an isolated-gate reference input. Future coupled
stages derive voltage from owned ionic charge. A whole-cell clamp requires an
explicit electrode closure. Ionic/capacitor energy accounting excludes unmodeled
gating charge, conformational energy and protein turnover; it is not complete
channel thermodynamics. Numeric gate/channel axes and complete histories support
later execution work, without adding a plugin framework or GPU implementation.

The frozen reference [passes 7528 checks and 105 new tests](../reports/SPEC006_DESIGN_CHECK.md):
source-unit/Decimal arithmetic, seven analytic gate protocols, instantaneous
flux/accounting, permutations, independent controls and equal-open/different-future
states. All **2670 regression tests pass** (1699 current-production, 971
preserved-reference), with no failures or skips. All 41 production modules,
packaging, old references and prior numerical/biological evidence remain unchanged.

The declared activation timescale reaches 1.352 ms; an algebraic held-gate check
rejects inheritance of the old 10 ms RK4 choice. **NUM-007** must register and
qualify bounded coupled references and a candidate method before **CORE-007**
production acceptance. This slice does not start physical graphs, finite baths,
GPU/optimization work, organ models, a biological refit or the deferred E02 campaign.

## D050 — Qualify coupled gates and ionic history before extending production

2026-09-09. The user's approval advances NUM-007 under its
[prospective protocol](VOLTAGE_GATED_NUMERICS.md). Fourteen fixed cases cover
the two SPEC-006 assemblies, explicit nonequilibrium preparations, independent
controls, a substep channel pulse, channel-off reduction and charge-held analytic
gates. Altered initial voltage always has an explicitly declared consistent
charge anchor; there is no runtime reanchoring, fit or implicit electrode.

The increment-coordinate Radau/BDF reference uses independent hyperbolic
permeation and native-unit gate laws. The absolute-amount RK4 candidate uses
the frozen scalar Bernoulli/gate evaluator. Both carry m/h and separate channel
transfer alongside all ionic ledgers. Reuse unchanged grid/dense infrastructure,
but check gate states at every actual trial and the extrema of every candidate
cubic interval. Record failed coarse trials without clipping or replacing them.

Freeze the 2/1/0.5/0.25 ms ladder, absolute error/accounting limits, refinement
rule, 900-second session cap and 128 MiB output cap before scientific evaluation.
All 198 preflight tests pass. The [frozen scientific session](../reports/NUM007_REFERENCE.md)
now qualifies 0.5 ms coupled RK4/cubic, with a passing 0.25 ms refinement on all
fourteen cases. Six coarse accuracy failures and one out-of-domain trial are
retained; 97 complete arrays / 947939 sampled rows pass read-only replay and
verdict auditing. All 205 targeted tests and **2770 regression tests pass**,
including 100 new tests, with no failures or skips. Production Cells 0.11.0 and prior evidence remain
unchanged. CORE-007 implementation/replay/cohort acceptance is a separate next
gate; no optimization, GPU execution, biological promotion or E02 restart.

## D051 — Compose complete channel state into the shared production engine

2026-09-10. The user's approval advances CORE-007 following NUM-007's frozen
0.5 ms qualification. Preserve accepted 0.11.0 before any production edit and
add `voltage_gated_membrane@1` in 0.12.0, without extending the old model identity
or inheriting its 10 ms bound. [Implementation guide](VOLTAGE_GATED_MEMBRANE.md);
[production acceptance](../reports/CORE007_ACCEPTANCE.md).

Retain flat numeric m/h and channel-transfer arrays with a separate channel
capacity, alongside the existing amount/leak/pump/energy state. Resolve channel
species/membrane IDs on the host; keep names and assay logic out of the kernels.
Reuse ionic transport/charge laws and the shared checked integrator, observers'
cubic infrastructure, snapshots, scalar windows and independent cohorts. Add only
model-owned working-array size and compatible-capacity hooks to the common engine.
Experimental availability is an independent right-continuous control, not intrinsic
gate state. Real disabled channels remain subject to chemistry/voltage/gate guards.

Keep the original electrical anchor and all cumulative ledgers through restart
and future-input branches. Compute gate and amount derivatives from the same
stage state; check unsampled cubic extrema too. An accounting-only projection
adds channel transfer to the ionic material balance without merging the stored
baseline and channel ledgers. Ionic/capacitor energy neglects gating charge,
protein conformational energy and turnover explicitly.

The 113 targeted and 2883 regression tests pass. Complete production acceptance
passes all fourteen cases in eager/JIT, exact fresh-process restarts, future-input
branching and bounded scalar/cohort execution. Two interrupted scheduling/budget
attempts remain recorded; only the verification driver changed between sessions,
with all scientific criteria and production sources unchanged. No biological, GPU,
organ, multirate or long E02 result is promoted. Old reference tests retain their source
guards in authenticated 0.10.0 and 0.11.0 contexts. The recommended next design
slice is a fixed physical ionic graph, tested first by single/disconnected and
two-cell reductions, then a three-cell star with explicit per-edge ownership.

## D052 — Own physical graph transfers once, with explicit local reduction

2026-09-10. The user approves the next bounded physical graph design step after
CORE-007. [SPEC-007](PHYSICAL_IONIC_GRAPH_SPEC.md) composes the unchanged SPEC-005/006
local references and SPEC-002 reciprocal constant-field/synthetic gate law;
production stays 0.12.0. The [instantaneous checks](../reports/SPEC007_DESIGN_CHECK.md)
pass 14116 comparisons on eight frozen definitions; all 114 new tests pass.
All 2997 regression tests pass across three source contexts, with no failures or
skips. The previous 1580-payload production audit passes again. All 44 production
modules, packaging and earlier scientific/pilot files remain byte-identical;
eleven pre-existing files have documentation-only updates.

Use one common maintained bath and one fixed diagonal cell-to-bath capacitance
per cell. Junction area is a transport coefficient, not an implicit capacitance
or geometry update. Local membrane/channel and edge operators read the same
stage state. Evaluate each cell's local membrane once and each oriented edge
once; apply opposite species transfers at the two endpoints. A shared recipient
is one cell, not two independently simulated pairs.

Retain independent cell/membrane/channel/edge axes, optional local channels,
heterogeneous geometry and explicit valence/role bindings. Each edge owns its
gate, signed species history and dissipation; neither inhibition nor a checkpoint
may erase them. Unequal capacitances require weighted charge accounting, while
cycle histories expose information not recoverable from net node amounts.
These are arithmetic witnesses, not biological memory or trajectory results.

No graph timestep is inherited from the one-cell or old pair limits. NUM-008
must qualify short coupled paths, refinements, stage/interior domains, events,
complete ledgers and resource budgets before CORE-008 production. Future GPU
partitions need solver-stage halo values and single-owned boundary transfers;
the scalar reference demonstrates neither device execution nor bitwise GPU
reproducibility. Do not start the deferred source E02 campaign or reopen the pilot.

## D053 — Qualify coupled physical graphs before production assembly

2026-09-10. The user approves the next bounded step after SPEC-007. The
[NUM-008 protocol](PHYSICAL_IONIC_GRAPH_NUMERICS.md) and twelve-case panel were
fixed before any trajectory evaluation. Preserve all prior sources, equations,
anchors and evidence; production stays 0.12.0. These are short synthetic
engineering cases, not BETSE parity or biological validation.

Independent Radau/BDF/refined trajectories use the earlier hyperbolic local
equations and a separately expressed oriented edge flux and gate target. The
candidate evolves absolute amounts using the frozen Bernoulli reference.
Both retain all nine state fields, evaluate complete common stages, and split
at every independent control event. No junction may duplicate its recipient's
membrane contribution or clear its history during inhibition.

[All twelve cases qualify](../reports/NUM008_REFERENCE.md), on 84 graph attempts
and five separately integrated edge-free components. The predeclared rule
selects **2 ms RK4/cubic with passing 1 ms refinement**. Complete material,
capacitance-weighted charge and chemical/electrical energy accounting pass,
as do stage/cubic-interior domains, analytic all-off gates, independent releases
and a 0.1 ms junction pulse. No candidate failed or was rejected in this short
scientific panel; the preflight separately tests retained rejection evidence.
The read-only audit authenticates 194 payloads/26 sources and exactly replays
256283 sampled rows without solving the ODE again. The one-worker session
used 321.805 s and 109.393 MiB within its prospective 1800 s / 256 MiB caps.
These are qualification costs, not production performance benchmarks.

All 99 new tests and **3096 regression tests** pass across current 0.12.0,
preserved 0.10.0 and preserved 0.11.0 contexts, without failures or skips.
The prior 1580-payload production audit passes again. All 44 production modules,
packaging, frozen SPEC-007 work and earlier scientific/pilot evidence are unchanged;
433 of 444 pre-existing files are byte-identical and eleven have documentation-only
updates. A preflight tuple/list receipt mismatch was fixed before scientific
execution; its failed test receipt is retained, with no relaxed numerical limits.

This selected step is a property of the declared preparations, graph weights,
event schedules and short horizons. It neither relaxes the previous one-cell
0.5 ms limit nor guarantees arbitrary topology, stronger coupling or organ-scale
stability. It does not qualify multirate, GPU or partition-interface approximations.

CORE-008 is next: preserve the accepted 0.12.0 source/runtime context, add a new
versioned CPU/JAX graph family with explicit reference-to-production axis mapping,
reuse the shared engine, and accept complete snapshots, branches, windows and
independent cohorts against these saved references. Defer universal plugin,
organ hierarchy and distributed-runtime scaffolding until an actual assembly
needs them. Do not reopen the pilot or restart the deferred E02 source campaign.

## D054 — Compose a production physical graph through the shared engine

2026-09-10. CORE-008 adds `physical_ionic_graph@1` in 0.13.0, following the
unchanged SPEC-007/NUM-008 contract and saved numerical references. Accepted
0.12.0 was authenticated and archived before production edits; historical
provenance tests retain their original sources in a fourth test context.
The [production guide](PHYSICAL_IONIC_GRAPH.md) fixes scope, ownership and
prospective acceptance budgets; [acceptance status](../reports/CORE008_ACCEPTANCE.md)
is separate from specification and reference qualification.

Use the existing local membrane/channel laws and a single owned sparse junction
flux at the same complete RK stage. State remains numeric and species-major,
with independent cell/membrane/channel/edge capacities and stable label maps.
Retain nine state fields, including distinct baseline leak, channel and internal
junction transfer histories and local/edge dissipation. Amounts are the only
mobile-charge inventory. Internal exchange never masquerades as bath exchange.
Gates evolve while blocked; a cycle history cannot be reconstructed from amounts.

Keep the shared runner, integration method, checkpoint I/O and window/cohort
machinery unchanged. Only model/schema/control dispatch grows. Different fixed
topologies and cell counts can share capacity-compatible independent-world
batches; they are not multiple interacting organs. Real-state and full cubic
guards plus local/global material, weighted charge and energy checks remain
mandatory. The 2 ms graph bound does not change old model limits or qualify
arbitrary topology, parameters or duration.

All 114 new targeted tests and **3210 regression tests pass** across current
0.13.0 and preserved 0.10.0/0.11.0/0.12.0 source contexts, without failures,
errors or skips. Formal acceptance passes on the first attempt: twelve frozen
cases in eager/JIT, independently reconstructed readouts/dense output, exact
fresh-process restart, a future-only branch, two window runs and four original/
resumed mixed-topology cohorts. The read-only audit authenticates 600 payloads
and 223 captured files; all 162 scalar/16 cohort checkpoints load, and earlier-model
replay is exact. The [closeout](../reports/core-008-closeout.json) records source
preservation, retained preflight failures and the bounded 453.536 s/441.253 MiB
acceptance cost. No universal plugin framework, organ hierarchy, solver rewrite,
GPU job or optimization is required for this extension.

Next prefer SPEC-008, a minimal finite extracellular-compartment specification:
outside inventories, geometry and charge ownership, maintained-bath reduction
and closed-system accounting. Qualify its reference/numerics before production,
and add spatial fields or organ presets later. Keep the pilot closed/descriptive
and the long E02 source campaign deferred.

## D055 — Give a finite outside real inventory, countercharge and energy

2026-09-10, SPEC-008. Specify one finite well-mixed extracellular compartment
shared by one or more cells, starting from the existing local membrane/channel
and junction laws. The [contract](FINITE_EXTRACELLULAR_SPEC.md) and
[independent reference checks](../reports/SPEC008_DESIGN_CHECK.md) are separate
from accepted 0.13.0 production; all 46 production modules remain unchanged.

Do not implement this by adding a volume to the old maintained-bath record.
The outside owns actual species amounts and fixed charge. Each membrane's
inward transfer is debited once from the outside; junction transfers cancel
within intracellular nodes and never reach that debit. Preserve ten complete
state fields, including all existing channel/junction histories and one outside
amount vector. A shared outside couples even junction-disconnected cells.

Use the explicitly derived floating capacitor-star closure: each membrane owns
one capacitor, extracellular charge opposes their summed charge, and setting
the sole outside potential to zero fixes a gauge, not an electrode clamp.
Initial fixed charges and anchors must be declared and consistent. Do not impose
separate exact-zero compartment charge, add a ground capacitor, infer a repair
ion, or reset anchors. Inside plus outside chemical free energy and each membrane
capacitor once replace the fixed-bath grand potential. ATP drive remains an
explicit external power term; ionically closed does not mean thermally isolated.

Nine frozen cases exercise single-cell volume changes, mono/divalent species,
disconnected cells, pairs and shared-outside stars. All 10,671 instantaneous
checks and 88 targeted tests pass. A checker-label issue initially skipped extra
all-off assertions; numeric predicates and assertion-count tests correct it.
The original passing narrower receipt, exact old sources and interrupted first
regression attempt remain recorded. No reference equation, frozen input or
scientific tolerance was changed by that correction. The complete four-context
regression passes all 3298 tests, with no failures, errors or skips. The
[closeout](../reports/spec-008-closeout.json) binds that evidence, exact saved-result
replay and the unchanged production audit; no finite-outside trajectory is claimed.

For later GPUs, all membranes read the same stage-specific outside state and
contribute one conservative shared reduction. Independent worlds own separate
outsides; partitions of one interacting world must not integrate private copies.
A spatial extracellular partition is a different mixing/electrical resolution
with its own interfaces and validation, not a transparent speed flag.

Next, NUM-009 must freeze short trajectories, reference methods/refinement,
depletion and all ten state fields, events, full cubic domains and resources.
The explicit countercharge constraint also matters for implicit Jacobian probes:
choose and document conservation-consistent reference coordinates, retaining
all complete physical fields for audit. An explicitly equivalent reduced
coordinate system is permissible; silent projection/repair of an invalid trial
state is not. Do not inherit the 2 ms graph step or weaken a charge constraint
merely to fit a solver's unconstrained perturbations. CORE-009 production follows
that gate. Meshes, organs, osmotic/mechanical work, GPU execution, the closed pilot
and deferred long E02 campaign remain outside this slice.

## D056 — Qualify finite-outside dynamics with explicit conserved coordinates

2026-09-10, NUM-009. The [frozen protocol](FINITE_EXTRACELLULAR_NUMERICS.md)
and [result record](../reports/NUM009_REFERENCE.md) separate numerical qualification
from CORE-009 production. Fourteen short cases include one-cell volume variants,
shared-outside graphs, independent blocking/release, a sub-step junction pulse
and two tiny-outside stress cases. Outside concentration errors and depletion
are explicit gates, not inferred from small absolute amount errors.

Use amount increments from fixed original anchors for both numerical paths.
This preserves small transfers into large inventories without resetting anchors.
The implicit reference eliminates only redundant species totals: reconstruct
outside increments as minus the summed inside increments at every actual trial,
Jacobian perturbation and dense coefficient. The independent RK4 candidate
evolves its own outside increment using owned membrane fluxes. All ten physical
fields and separate transfer histories remain available in saved evidence.
Do not project a supplied full state or substitute histories for material.

The first preflight exposed a near-quadratic stationary-root failure in a generic
cubic-extrema calculation. The NUM-009 checker uses a scaled stable quadratic
formula; its old source and failed test receipt are retained. All 101 corrected
preflight tests pass, including fifteen scale/sign cases. No frozen equation,
input, solver setting or tolerance changed. Earlier accepted sources stay intact;
a separate read-only review examines their actual saved candidate polynomials.

The first frozen session stopped after 80 attempts / ten case ladders. Nine cases
pass the independent references; in the junction-only star, reconstructed outside
increments fluctuate by up to 7.593e-19 fmol even though the physical outside
amounts round to constants. All reference accuracy/accounting and all five RK4
trials pass that case, but the predeclared exact blocking invariant does not.
The stopped-attempt audit authenticates 174 payloads / 31 sources and replays
184240 rows. Four cases remain unrun, and no timestep is selected. All 109
targeted tests pass; complete-session and full-regression gates are not promoted.

The next revision must handle invariants generally. Prefer investigating explicit
full inventories with conservation-consistent Jacobian linearization/probes;
compare this against a justified constrained-coordinate formulation before
freezing it. This is a recommendation, not an implemented method. Do not solve
only this fixture by picking a convenient dependent cell, zeroing the outside
after steps, reanchoring or weakening exact-blocking/charge checks. Preserve the
failed session and declare any reference change before fresh qualification.

The formal session, saved-evidence audit and regression gate determine acceptance;
preflight success alone does not select a timestep. CORE-009 must explicitly map
the anchored numerical coordinates to physical readouts and complete checkpoints,
then qualify eager/JIT, restart, branch, window and cohort execution. A larger
outside or a disconnected graph does not justify independent cell integration.
Future GPU partitions still share one same-stage outside reduction per world.
No biological, spatial-field, organ, optimization or deferred E02 gate is promoted.

## D057 — Keep every inventory explicit; linearize only along conserved directions

2026-09-10, NUM-009 v2. The [prospective amendment](FINITE_EXTRACELLULAR_NUMERICS_V2.md)
retains all v1 physics, cases, horizons, solver tolerances, candidate steps,
invariants and resource limits. Full inside/outside inventory increments are
now integrated explicitly by Radau and BDF as well as RK4. No compartment
absorbs the rounding of other compartments' internal exchange. Initial anchors,
full histories and exact disabled-inventory checks are unchanged.

For each species, implicit derivative probes use the equal-owner tangent
projector I - 11^T/(N+1). This gives a constrained Newton linearization Df P,
not a claim about an ambient unconstrained Jacobian. It agrees with the physical
directional derivative on conserved-total corrections. Gate directions are
ordinary coordinate directions; histories are not consumed by the RHS and have
zero Jacobian columns. Bounded central/one-sided probes remain in the physical
domain and count against the same RHS allowance. Actual solver states, fluxes,
residuals and dense output are never projected.

This choice avoids switching the dependent inventory to a convenient cell,
history-derived amounts, reanchoring or fixture-specific repair. It is a dense
CPU reference technique, not the future GPU algorithm. Production must still
own each membrane transfer once and share one outside update across partitions.
The physical representation is compatible with later array/sparse/matrix-free
implementations, but those require separate numerical and performance evidence.

All 153 preflight tests pass before registration, including every original
preflight/stopped-attempt test and 44 new tangent/test-routing checks. New
synthetic controls freeze the outside, all transport, or each possible cell
owner after nonzero transfers. Every blocked inventory remains exactly constant.
All fourteen initial definitions receive conservation-tangent probes without
extra full-panel trajectory runs.

Every v1 source and artifact remains unchanged and executable. Its stopped-run
audit still authenticates 174 payloads and replays 184240 rows. The original
13-test prospective complete-session suite has no complete v1 run; it remains
explicitly unexecuted, not passing coverage. A maintained v2 suite reproduces
those checks and adds complete-session/Jacobian-work audits. The
[new test-context wrapper](../scripts/test_finite_extracellular_build.py) records
this routing without changing the accepted production driver or any provenance
validator. The frozen numerical run, evidence audit and full maintained matrix
determine qualification; current outcome is tracked in [Progress](../PROGRESS.md).
The registered v2 run completes all fourteen cases / 112 attempts in 297.692 s,
selecting 1 ms RK4/cubic with passing 0.5 ms refinement. Exact outside blocking
now passes; the synthetic outside-K depletion is 80.8057%. Nine coarse accuracy
failures remain failures. The [result and closeout](../reports/NUM009_REFERENCE_V2.md)
authenticate 242 payloads / 43 sources and replay 251400 rows; all 168 targeted
and 3466 full-matrix tests pass. No earlier source or scientific artifact changes.
CORE-009 is next as a separate production/restart/cohort gate; no GPU, biological
or organ acceptance follows from this numerical result.

## D058: Explicit finite outside through the shared CPU/JAX engine

2026-09-10. CORE-009 implements `finite_extracellular@1` in 0.14.0 using
the [production contract](FINITE_EXTRACELLULAR.md) and unchanged NUM-009 v2
reference. Accepted 0.13.0 is authenticated and archived before edits.
The [formal acceptance](../reports/CORE009_ACCEPTANCE.md) passes fourteen cases,
complete restart/branch/window/cohort paths and exact earlier-model regression;
the full five-context release matrix passes all 3616 tests, with no failures,
errors or skips in that final matrix. Release/source closeout passes.

Inside and outside amount increments are explicit state, with immutable initial
inventories, fixed charge and geometry in the layout. Derive voltage directly
from increments, without subtracting nearly equal large inventories. A membrane
updates both of its owners from one flux; cell-cell junctions cannot alter the
outside. This is a general ownership rule, not a correction for the original
reference's failed exact-blocking test. The energy check includes both finite
chemical inventories and each capacitor once, not a maintained-bath grand potential.

Keep independently padded cell, membrane, channel, junction and outside axes.
The first closure has one active outside per world; disconnected cells sharing
it are still coupled. Independent worlds each own their outside state.
The common runner, RK4, scheduling and scalar/cohort I/O remain unchanged.
Current CPU/float64 and 1 ms step restrictions are explicit; GPU placement,
spatial resolution and numerical method are separate future choices.

All 150 new targeted tests pass, including labels/species permutation,
one-/five-cell scaling, invalid-state and cubic-interior refusal, conserved
outside feedback, hidden cycle history and 33 rehashed corruption cases.
No frozen physical input or tolerance is changed. Original reference scripts
and evidence retain their identities, with packaging-dependent guards running
unchanged in preserved 0.13.0. The thirteen prospective v1 complete-session
tests remain explicitly unexecuted, not passing coverage.

The first full matrix's two historical subprocess import checks fail because
the copied workspace lacks its expected interpreter path. The
[launcher correction](../reports/core-009-regression-correction.json) links only
the environment, not sources/evidence; all 256 historical checks then pass.
New final acceptance captures that correction and reproduces all 25,654 saved
numerical arrays exactly. The old matrix remains failed and the original
successful numerical session remains retained, not silently relabeled.

The next proposed design slice is SPEC-009: minimal spatial outside transport
and electrical closure. Do not duplicate the zero-potential gauge independently
at every new compartment. Define field/compartment ownership, potential
constraints, conservative interface transfers and limiting-case references
before choosing a mesh or parallel communication implementation.

## D059: Spatial outside potentials require a coupled electrical constraint

2026-09-11, SPEC-009 / R011. The [new contract](SPATIAL_EXTRACELLULAR_SPEC.md)
and [independent instantaneous reference](../reports/SPEC009_DESIGN_CHECK.md)
are complete; production stays 0.14.0. One cell with two finite outside volumes
is the smallest coupled witness. Add a membrane-free bulk volume, not an
artificial capacitor or independently grounded bath for every outside region.

Select bulk-electroneutral transport with explicit membrane capacitance as the
first coarse spatial direction. Amount increments remain explicit for every
owner. The capacitance graph requires charge compatibility in each of its
components; bulk current continuity determines their relative potential offsets.
Only the final common potential reference is an arbitrary gauge. A positive
log-mean mobility gives Fickian zero-field transfer, diffusion potentials and
instantaneous passive energy dissipation in one owned interface law. These
algebraic properties do not establish time-integration positivity or stability.

The first passive reference deliberately excludes cross-region junction return
currents, multiple membrane patches, electrodes, changing geometry and disconnected
conducting domains. They need explicit extensions, not fixes hidden in a gauge
or grounding regularizer. This does not remove existing production mechanisms.
Pumps/channels and broader coupling must be qualified in separately frozen
spatial panels before any production feature claim.

Keep a field-solver block separate from biological ownership, resolution and
device placement. Its gauge, physical residuals, same-stage dependencies and
restart/cache policy must be explicit. Small dense reference matrices do not
choose production storage; future GPU work needs a sparse coupled solve and
communication, not merely independent-cell batching. R011 records the primary
literature motivation without upstream execution or a hardware speed claim.

All eight definitions / 44 evaluations pass 1016 separate 70-digit comparisons;
85 new unit and 229 targeted tests pass. Arithmetic evidence replays exactly,
and the old production audit authenticates its 830 payloads / 256 captured files.
All 48 production modules and previous evidence are unchanged; ten existing
documents have expected updates. The full historical matrix is not rerun for
this isolated design/reference slice; the previous 3616-test result remains
CORE-009 evidence. NUM-010 must next qualify short spatial trajectories and
temporal/spatial refinement before CORE-010; the old 1 ms bound is not inherited.

## D060: Qualify spatial time evolution before mapping it to production devices

2026-09-11, NUM-010. The [prospective protocol](SPATIAL_EXTRACELLULAR_NUMERICS.md)
freezes fourteen short cases, three implicit reference settings, seven RK4
candidate steps and separate temporal, spatial, charge/current, material and
energy gates. The [registration](../runs/num-010-2026-09-11/reference-01/registration.json)
captures the complete numerical source set before panel integration. Production
remains 0.14.0; the formal result is still pending at registration.

Both equation paths integrate every inventory increment and every owned membrane/
face transfer and dissipation history. The implicit path independently assembles
outside-node current continuity and hyperbolic GHK. Its derivative probes use a
general orthogonal tangent space preserving both species totals and each
capacitance-component charge. No accepted state, physical RHS or dense output is
projected. The RK4 path uses the frozen capacitance-component reference and
independent incidence scattering. Dense CPU reference linear algebra does not
choose future sparse production storage or a GPU algorithm.

Reference agreement alone is insufficient: pure-bulk/blocked-cell analytic
relaxation and 8/16/32-volume finite-volume convergence must pass too. Keep the
case definitions, tolerances, explicit step ladder and resource caps unchanged
after results arrive; retain unstable/incorrect coarse attempts. Exact blocking
includes nonzero histories, and restart must reproduce native/dense/observation
suffixes from all five fields, original anchors and the absolute event clock.
No exact BDF restart, biological validation, BETSE parity or device speedup is
claimed by this CPU reference gate.

The [registered result](../reports/NUM010_REFERENCE.md) passes fourteen cases /
140 attempts and selects 0.125 ms RK4/cubic with passing 0.0625 ms refinement.
All fourteen complete-state restarts and the 339-payload/21-source read-only audit
pass. Seven actual coarse trials are rejected and two completed candidates fail
accuracy; none is relabeled. The 8/16/32-volume continuum errors decrease by
factors 0.254674 and 0.251153, with finest error 0.0059 mM. This supports the
bounded numerical design, not a universal spatial timestep. All 190 preflight
and 3806 five-context regression tests pass. The [closeout](../reports/num-010-closeout.json)
preserves 628 existing files and records ten documentation-only updates; all
48 production modules stay unchanged. CORE-010 remains a separate production gate.

## D061: Integrate the passive spatial family before extending its physiology

2026-09-11, CORE-010 development implementation. Preserve and audit accepted
0.14.0 and the unchanged NUM-010 reference context before edits. Use
`spatial_extracellular@1` in **0.15.0.dev0** so implementation/preflight work is
not mistaken for formal release acceptance. The [integration contract](SPATIAL_EXTRACELLULAR.md)
keeps the frozen passive scope and separate checkpoint/observation meanings.

Cells, outside volumes, membranes and faces have independent padded axes; zero
cells is valid for pure-bulk transport. All inventory increments and owned
transfer/dissipation histories evolve explicitly. No hidden dependent ion,
charge projection, independently grounded outside or bulk capacitor is introduced.
The existing GHK process kernel is reused with an explicit outward sign convention.
The shared RK4, runner, checkpoint and window/cohort algorithms are unchanged.

Keep the field calculation in its own module and identify the initial algorithm
as `gauged_dense_kirchhoff@1`. Persist edge lists and the gauge, not dense field
matrices. Dense temporary CPU workspace is deliberately bounded and included in
pre-allocation memory accounting; it is not the future large-mesh backend.
A sparse/matrix-free GPU field solver must later qualify its own residuals,
reduction behavior, precision, resource limits and restart semantics.

Implementation tests and old-context regression precede a separately frozen full
production capture and independent saved-data/corruption audit. CORE-010 stays
open until that release gate passes. Do not extend this family with the existing
pump/channel/junction mechanisms merely because those modules already exist;
their coupled spatial qualification is separate. Organ, GPU, biological and
BETSE-parity claims remain out of scope.

## D062: Audit recorded spatial execution before stable-version promotion

2026-09-11, CORE-010 recorded development acceptance. Freeze the completed
0.15.0.dev0 production bytes; this slice changes no physical law, shared engine,
artifact format or version. The [prospective protocol](SPATIAL_EXTRACELLULAR_ACCEPTANCE.md)
requires complete saved eager/compiled/refined trajectories, fresh-process scalar
and cohort restarts, future-only control branching and bounded windows. Earlier
accepted families still require exact replay under the current engine, with old
checkpoints restored only under preserved sources.

The scientific audit recomputes all state-coordinate comparisons, 26 physical
readouts and incoming-control Hermite polynomials independently of production's
RHS/observer. Complete-checkpoint compatibility checks retain the normal loader's
domain preflight. Rehashed corruptions must fail even when their file checksums
are internally consistent. Map reference capacitance components explicitly to
public outside-owner order. For cancellation-dominated current, propagate the
checked species-flux error and separately verify recorded flux/current/residual/
normalization dependencies; do not change the inherited continuity tolerance.

All 122 new preflight tests pass. The [recorded acceptance report](../reports/CORE010_ACCEPTANCE.md)
tracks the bounded full capture, separate read-only audit and six-context
regression gate. Those results must not be inferred from preflight. Keep 0.14.0
as the accepted stable version until an explicit source-preserving promotion
closeout; no organ, new physiology, GPU or biological validation is implied.

The registered v1 attempt stopped at the one-hour budget with ten of fourteen
eager cases complete. All 53 completed scalar runs and 12 window/cohort runs
independently audit, including all 166 scalar/24 cohort checkpoints and strict
byte replay of scalar restarts and the future branch. Three eager cases were
interrupted and one unstarted; none is counted as a full pass. Preserve the
880-file stopped capture and frozen v1 protocol. The next attempt needs an
explicit revised resource plan, not looser science or implicit acceptance of
partial coverage. The separate regression gate passes all 4084 tests across six
source contexts, with no failures, errors or skips and all 345 implementation
files unchanged. The [tooling/preservation closeout](../reports/core-010-audit-tooling-closeout.json)
records 703 of 707 pre-existing files unchanged and four intended status-document
edits; its passing scope does not accept the stopped full panel or promote a release.

## D063: Separate acceptance resource profiles from the unchanged scientific panel

2026-09-11, CORE-010 runtime amendment. The prior one-hour attempt remains stopped
and immutable. Use a [new named v2 resource profile](SPATIAL_EXTRACELLULAR_ACCEPTANCE_V2.md)
with 7200 seconds, unchanged 2 GiB, CPU 0–3, four eager lanes and case order.
The measured worst eager step cost plus a 900-second allowance projects 87.3
minutes; this is a planning estimate, not a performance guarantee or optimization.

Keep production, the v1 scientific plan, definitions, references, physical oracle
and numerical tolerances byte-identical. Pass validated resources explicitly
through acceptance orchestration and resolve worker/auditor profiles from saved
registration. Capture both protocols, the resource definition, projection and
pre-edit baseline. Do not patch global plan constants or offer arbitrary CLI limits.

Enforce the already-required byte-exact scalar restart/branch comparison literally,
including dtype, shape and signed zero, without changing tolerant path comparisons.
All 106 new resource/replay preflight checks pass; the complete capture, separate
read-only audit and unchanged-source regression result are tracked in the
[v2 report](../reports/CORE010_ACCEPTANCE_V2.md), not inferred from short tests.
Development acceptance and stable-version promotion remain separate gates.

## D064: Close the current gate, then establish narrow executable BETSE contact

2026-09-11. The user approved careful, stepwise external comparison with early
contact. The complete CORE-010 v2 capture passes; finish its existing independent
audit, unchanged-source regression and development closeout before adding new
comparator code. Run that follow-through detached with durable stage receipts,
bounded resources and fail-fast behavior. Do not rerun the completed capture,
poll repeatedly, automatically retry or implicitly promote a stable release.

The [REF-003 plan](BETSE_REFERENCE_PLAN.md) starts with an isolated, authenticated
BETSE v1.5.0 environment calling its unmodified passive-flux module. Explicitly
map units, constants, orientation, area and removable-singularity behavior;
retain independent analytic checks. Then establish whether its one-cell charge
closure and initialization can match the existing maintained-bath family before
comparing trajectories. Component correspondence is not a full BETSE run, and
cross-simulator agreement is not experimental biological validation.

Keep the adapter offline and out of the production kernel. Neither organ/GPU
work nor broad BETSE feature coverage is a prerequisite. Preserve our own
engineering and physical contracts; mismatches must be explained rather than
removed by tuning established equations or tolerances to a reference curve.

## D065: Establish passive-law source contact without changing accepted physics

2026-09-12, REF-003a. Inspect and authenticate the passing CORE-010 development
closeout before starting external work. Retain stable 0.14.0, development
0.15.0.dev0, all 352 captured implementation/protocol files and the existing
912-payload accepted evidence. The [preservation receipt](../reports/ref-003a-preservation.json)
binds the existing source capsule, prior audits and 4190-test matrix.

Place this optional adapter in `validation/betse`, outside the installed runtime
and its frozen test/source set. Install pinned BETSE v1.5.0 in a separate
environment and authenticate all 332 installed Python files. Call the complete
upstream module, not an extracted or rewritten function. Use an explicit F/R
parameter carrier; do not imply that a full simulator configuration was loaded.

Keep source-declared rounded constants separate from matched-constant probes.
The [executed comparison](../reports/REF003A_PASSIVE_CONTACT.md) passes 54 probes,
1047 tolerance comparisons and 15 exact-blocking checks in 4.681 seconds. The
matched compiled-Cells difference is at most 2.22e-16 fmol/s; independent
70-digit arithmetic explains native-constant differences within floating-point
residuals. Fresh arrays isolate the upstream input nonce. Source semantics are
recorded, not copied into or imposed on production.

The separate saved-data audit and 52 adapter/artifact tests pass, including nine
rehashed corruptions. No pre-existing production/test/solver/fixture/dependency
file changed; the prior 4190-test matrix is preserved, not reported as newly
rerun. Full-model electrical closure and preparation alignment precede REF-003b
trajectories. No whole-cell, biological, GPU or throughput claim follows from
this instantaneous component result.

## D066: Check actual native preparation, not just configuration labels

2026-09-12, REF-003b1. Extend the isolated adapter to load actual BETSE
configuration and native seeded geometry before comparing electrical closure
or a trajectory. Preserve the earlier component result and all accepted Cells
sources. The [design](BETSE_INITIALIZATION_ALIGNMENT.md) selects the existing
finite-compartment family as the candidate: nonspatial BETSE does not hold its
outside composition constant. Record the source-derived face-count bath
normalization, charge-balanced initialization and time-label convention for
subsequent executable qualification. Do not copy these implementation conventions
into production physics.

The [actual seed](../reports/REF003B1_PREPARATION.md) contains seven cell
compartments / 30 faces despite the single-cell flag. The one-cell guard rejects
the fixture before charge/RHS/update probes or integration. Explicitly disabling
the native default general network in protocol revision 2 does not fix geometry.
Retain the first three configuration-serialization/path failures, both seeded
geometry rejections, all source capsules and unchanged numerical criteria.

The read-only diagnostic confirms the mismatch; 103 short adapter tests pass,
including synthetic checker tests and negative tests on actual preparation
evidence. This is not a passing scientific alignment, and no full production
matrix was rerun. All 352 accepted implementation files / 51 production modules
and prior external evidence remain unchanged. No stable, biology or GPU promotion.

Next investigate a genuine one-cell native geometry route with explicit mechanism
flags. If unavailable, prospectively register a clearly named seven-cell
comparison using existing Cells composition. Do not relabel one selected trace
as an entire single-cell world, patch upstream, or silently relax this protocol's
shape guard. No long follow-on job is launched automatically.

## D067: Use explicit seven-cell composition for the native reference

2026-09-12, REF-003c. The user approved the next bounded step after D066.
The native one-centre SVG route loads but fails Delaunay triangulation; preserve
that diagnostic alongside the five earlier rejected preparation attempts.
This is evidence about the tested pinned routes, not every possible single-cell
BETSE configuration. Keep the one-cell guard and its unqualified status intact.

Prospectively register an explicitly seven-cell comparison using the existing
`finite_extracellular@1` family. Export and represent all seven cells / 30 faces,
with owned membrane areas, capacitances and one shared finite outside inventory.
Do not patch upstream geometry, select one trace as the entire world, or add
production physics solely to accommodate the reference. The source-specific
face-mean bath normalization belongs in the adapter, not Cells' volume definition.

The [capture](../reports/REF003C_CLUSTER_ALIGNMENT.md) passes 19,691 scalar
comparisons in 18.666 seconds. Actual native initialization, zero-polarizability
charge closure, passive fluxes and prescribed updates agree with unchanged Cells
voltage/RHS paths on NumPy, eager JAX and compiled JAX. Nine independent
preparations, four flux footprints and separate native/matched F/R profiles
retain explicit coverage. Both workers report no warnings. This is not full
time integration, equilibrium, field correspondence or biological validation.

Prepared probe states are new initial conditions, not invented trajectory
histories. The existing production domain check rejected a preflight attempt
to encode doubled permeability as availability 2. Correct the adapter to double
the maximum-permeability parameter with availability 1; keep the [0,1] fraction
contract unchanged. All 25 new preflight checks then pass. Preserve the first
failed test receipt and unchanged scientific tolerances.

All 352 accepted implementation files / 51 production modules stay unchanged;
no version or dependency change, stable promotion, GPU test or throughput claim.
The previous 103 adapter tests and 4190-test production matrix are not rerun
totals. Next, on user instruction, finish the separate saved-data audit,
actual-packet corruption tests and short closeout. Only then register REF-003d's
short actual native FULL transient against Cells RK4, with independent timestep
refinement and explicit native-label versus elapsed-update-time mapping. Keep
the original one-cell REF-003b deferred; do not silently mark it complete.
No automatic follow-up audit, regression or trajectory job is started.

## D068: Close the seven-cell evidence before beginning full trajectories

2026-09-12. The user authorized the separate REF-003c audit and short adapter
closeout. The [result](../reports/REF003C_CLOSEOUT.md) replays all 19,691 saved
comparisons without either simulator. All 171 short adapter tests pass, including
43 new actual-evidence checks and a fresh-process model-import fence. The native
one-centre SVG failure is explicitly checked as a rejection, not an acceptance.

Preserve the frozen nine-file capture source set. Add a separate evidence layer
for three metadata gaps demonstrated on rehashed copies: jointly altered
geometry, jointly altered runtime and a false trajectory claim in the capture
receipt. Anchor geometry to retained native preparation and runtime to accepted
Cells metadata; require the receipt's limited scope. Do not change scientific
tolerances or rerun a simulator to fix an evidence-checking problem.

All 352 accepted implementation files / 51 production modules and both reference
environments remain unchanged. The previous 4190-test production matrix is not
rerun; no production, biology, stable or GPU promotion. The closeout records eight
intended document edits and 807 unchanged files from its 815-file baseline.

The [first trajectory design](BETSE_PASSIVE_TRAJECTORY_PLAN.md) proposes a short
1 ms baseline and blocked control, with independent timestep refinement and
native/matched constants separate. Actual FULL-loop observation must come first:
native labels differ from elapsed update times, its ordinary storage omits the
first update, and complete per-ion transfer history is not retained there.
Prefer a read-only native observer with non-interference checks, not a substitute
solver or fabricated history. Next implement/test the adapter, then freeze the
numerical protocol before capture. This design is not preregistration, accepted
timestep selection or authorization for an automatic long campaign.

## D069: Observe the actual native loop and register short trajectory criteria

2026-09-12, REF-003d. The user authorized continuing after the seven-cell closeout.
Implement a separate read-only native observer, full-engine adapter, independent
saved-array checker and [prospective protocol](../validation/betse/trajectory_protocol.json).
All **228 short adapter tests pass in 24.234 seconds**, including 57 new observer,
schema, timing, static readout and corruption preflights. No full simulator
trajectory is executed by those preflights. See the
[engineering/launch report](../reports/REF003D_TRAJECTORY_LAUNCH.md).

Use `sys.setprofile` at actual FULL-loop concentration/voltage/storage boundaries,
without patching upstream methods. Preserve the unsampled first update, original
native labels, explicitly derived elapsed times and the native voltage nonce.
Every native condition/constant/step combination has a fresh unobserved partner;
require byte-identical declared ordinary/final arrays. Keep the ordinary final
current's preceding-step meaning distinct from a post-update instantaneous rate.

Amend D068's proposed backend list before numerical capture: Cells' unchanged
checked RK4 runner implements eager and compiled JAX, not a third NumPy integrator.
Use both actual paths, ordinary NumPy readouts and separate arithmetic checks.
Do not add a solver or production special case to satisfy the proposed panel.

Freeze a 1 ms baseline/blocked panel, native 0.1/0.05/0.025 ms refinement, Cells
0.1/0.05 ms refinement, independent native/matched constant profiles and eleven
common state times. The twelve observed native runs, twelve unobserved partners
and eight Cells runs have explicit charge/material/transfer checks and exact
inactive-route requirements. Instantaneous criteria stay frozen; cumulative and
trajectory budgets are separately declared before any outcome. Native refinement
must contract above the roundoff floor; compare fine matched-constant runs only.

Retain exclusive registration/source capsules, durable logs and success/failure
receipts. Bound workers to 90 seconds, the panel to 180 seconds and artifacts to
64 MiB on CPUs 0–3. Launch detached and return control without polling or scheduling
a follow-up audit. Failures remain failures; no automatic retries or tolerance
changes. The later independent actual-packet audit waits for user instruction.

All accepted implementation files, production equations, historical adapter
sources and previous evidence stay unchanged. Stable 0.14.0 and accepted
development 0.15.0.dev0 remain distinct. This slice adds reference engineering,
not biological, GPU, organ or family-wide BETSE acceptance.

## D070: Refine native timesteps while retaining the original numerical rejection

2026-09-12, REF-003d v2. The user approved finer native steps after v1 failed
shared-bath Na/K amount criteria. Preserve all 119 original packet files /
23,075,224 bytes, its source capsule and failure verdict. The
[saved-data audit](../reports/ref-003d-failure-audit.json) reproduces all 129,384
comparisons and all 36 failures without importing either model or NumPy/JAX.
Independent endpoint arithmetic finds approximately first-order native convergence,
coherent summed cell/bath discrepancies and much smaller material residuals.
Extrapolated agreement supports the explanation but is not a native simulation
or qualification. See the [report](../reports/REF003D_TRAJECTORY_REFINEMENT.md).

Register a fresh native **25/12.5/6.25 µs** ladder, replacing 100/50/25 µs. Keep the
1 ms horizon, preparations, mechanisms, eight Cells runs, constants, common times,
all instantaneous/cumulative/trajectory tolerances and refinement requirements
identical. A new versioned harness reuses the frozen actual-model workers and
saved-state arithmetic without changing their globals or patching either model.
Repeated native 25 µs records and all eight Cells numerical records must reproduce
v1 exactly; timings are excluded.

The denser native trace has 1120 observed steps versus 280. Increase only the
artifact allowance from 64 to 128 MiB; the first packet is 23.1 MB and fourfold
recording growth leaves inadequate headroom at 64 MiB. CPU lanes 0–3, 90-second
worker limits and the 180-second panel bound remain unchanged. Complete recording
is retained, without selective intervals or weakened criteria.

All **276 short adapter tests pass**, including 48 new checks of protocol changes,
native mappings, 80/160-step synthetic observers, original-packet integrity,
import-fenced replay, rehashed overlap corruptions and detached failure handling.
Lint/format checks pass for 313 Python files. All 352 accepted files / 51 production
modules and the original 29 captured source files remain unchanged; the 4190-test
production matrix is not rerun. Stable 0.14.0 and accepted development 0.15.0.dev0
stay unchanged. Launch detached; no polling, automatic retry, new biology/GPU
claim or automatic post-capture audit follows.

## D071: Close bounded passive trajectory correspondence with separate evidence guards

2026-09-12, REF-003d v2. The user authorized independent audit, corruption tests
and closeout after the refined capture passed. Reproduce all **435,144 numerical
comparisons**, maximum normalized error 0.559745, without importing Cells, BETSE,
NumPy or JAX or rerunning a simulation. The 104.031-second capture completes all
24 native / eight Cells runs without recorded warnings. Native 12.5 → 6.25 µs
refinement now satisfies the unchanged bounds and contraction test; physics,
Cells definitions, criteria and the original rejection remain unchanged.

Qualify only the **1 ms neutral-prepared seven-cell passive/blocked finite-bath
case**. Select native 6.25 µs versus Cells 50 µs for the matched finest comparison,
not as a universal timestep policy. Preserve raw clocks and begin-/end-step
measurement semantics; no final-time RHS is invented from the last saved flux.
Repeated native 25 µs records and all eight Cells numerical records reproduce
v1 exactly, excluding timings. The original one-cell fixture stays rejected.

Add a separate read-only evidence layer that binds independent capture/source
anchors, all 115 payloads, complete paths and runtime/geometry/budget metadata.
Cross-link auxiliary native arrays to observed fluxes, boundary state, owner
mapping and constant/disabled mechanisms. Existing captured arithmetic is reused
unchanged; a test demonstrates the narrower old final-flux field boundary and
rejection by the added guard. Native open junction gates are not confused with
transport: `gj_surface=0` keeps the junction flux zero in this fixture.

All **325 adapter tests pass**, including 49 new actual-packet/import-fence/
corruption tests. The new group took 91.26 s; future full suites run detached.
Test setup failures from cross-filesystem hardlinks and an incorrect pytest
launcher are retained and corrected only in scratch setup and invocation. All
352 accepted files / 51 production modules, both complete 119-file packets and
35 captured v2 sources stay unchanged; the prior 4190-test production matrix
is not rerun. See the [closeout](../reports/REF003D_CLOSEOUT.md).

Keep source-specific mappings out of production. Multiscale validation must
include shared-pool inventory and interface errors, where coherent cell-wise
errors can accumulate. Next design a passive block/release experiment with
explicit event timing and independent refinement; no new panel is registered
or launched. Stable 0.14.0 and accepted development 0.15.0.dev0 are unchanged.
No biological, organ, family-level parity or GPU qualification is implied.

## D072: Qualify phase and input semantics before a permeability response comparison

2026-09-12, REF-003e design. The user approved the next controlled-intervention
design after the bounded passive trajectory closeout. Source review finds that
native scheduled events fire only in SIM, before flux evaluation; the qualified
REF-003d run used INIT. Native permeability changes are additive logistic pulses
relative to tissue-default diffusion, not exact on/off multipliers. Keep this
distinction explicit instead of assuming the proposed hard-block test maps directly.

First implement/preflight a separate REF-003e0 SIM-from-neutral bridge, retaining
the original seven-cell preparation, disabled mechanisms and bounded criteria.
Compare no-event/blocked paths and enabled zero-amplitude events, and add a
read-only observer for tissue-handler dispatch and effective diffusion. A fresh
SIM-from-neutral phase is not the high-level `SimRunner.sim()` lifecycle, which
loads an initialized state; both the route and its initial condition need an
explicit protocol. No model integration or bridge capture occurs in D072.

For subsequent REF-003e1, propose source-native smooth suppression/recovery at
elapsed centres 0.3/0.7 ms, transition parameter 0.1 ms and additive multiplier -1.
The ideal midpoint availability is about 4.1223e-9, not zero; exact zero transport
belongs to a separate static blocked control. Do not clip tails or demand an
unchanged pre-centre trajectory. In the homogeneous fixture the additive law
reduces to a multiplier; heterogeneous defaults require their own mapping.

Native raw labels equal `k*N*dt/(N-1)`, not elapsed `k*dt`. Explicitly scale start,
finish and transition parameters by `N/(N-1)` to prescribe a common elapsed-time
pulse; never patch native labels. The actual pinned control function agrees with
independent 70-digit arithmetic at 280 points within 2.665e-15 after conversion.
Existing Cells right-continuous controls and off-grid event splitting also pass
control-only probes. Separate input discretization, state-integration refinement
and observation-side conventions; use distinct actual grids, not nominal step
labels that collapse after event splitting. Generate any held input from declared
parameters before integration, not from native voltage/state outputs.

All **38 focused checks pass in 3.67 s**. The initial startup-log/JSON setup error
is retained; diagnostics are now captured inside the structured result. Both
stepping-entry imports are fenced. All 352 accepted files / 51 production modules,
35 captured v2 sources, prior closeout and both trajectory packets stay unchanged.
The previous 325 adapter tests / 4190 production tests are not rerun. No new
production control law, simulation qualification, biological claim or GPU work.
See the [design](BETSE_INTERVENTION_PLAN.md) and
[source/control review](../reports/REF003E_INTERVENTION_DESIGN.md). Future long
jobs and subsequent audits retain detached, durable, user-polled execution.

## D073: Preserve the failed SIM preflight and expose tissue-profile prerequisites

2026-09-12, REF-003e0. Implement a separate SIM-from-neutral preparation adapter
and one read-only event/step profiling dispatcher. Synthetic tests verify
source/object/phase routing, exactly one event before membrane fluxes and updates,
unchanged legacy trace copies, exception/hook restoration and preparation-mode
entry guards. No production model, upstream method or accepted evidence changes.

The first registered preparation attempt fails after 9.491 s on the first
disabled-event row: adapter metadata assumes `dyna.tissue_default`, but native
`_init_tissues` returns early when `is_tissue_profiles` is false. The accepted
baseline disables profiles. Its target map is empty, so merely making metadata
nullable cannot supply the targeted event infrastructure. Zero-amplitude runtime
was not reached; no completed preparation result or new trajectory is qualified.
See [failure report](../reports/REF003E0_PHASE_PREFLIGHT.md).

Keep the original six-file attempt and capsule immutable. Add a fail-fast guard
that prevents the unchanged candidate from launching again; do not silently
enable tissue profiles or patch native code. All 73 software/negative-evidence
tests pass, not a native scientific pass. Retain the missing partial-state export
as an observability gap to correct before the next preparation attempt.

Next explicitly version three controls: profiles-off SIM matching the INIT
baseline, homogeneous default-profile-on SIM without events, and the same
profile with enabled zero-amplitude Na/K/Cl events. Verify configuration and
physical state at each transition, including effective cutting/voltage events,
geometry, baseline diffusion, charges, finite bath and disabled transport paths.
Only after preparation succeeds register a bounded trajectory panel with exact
phase/profile/no-op correspondence and observed/unobserved partners.

The [bridge note](BETSE_SIM_PHASE_BRIDGE.md) records this prerequisite separately
from the frozen D072 design. General lesson: optional capability dependencies
need explicit configuration validation; unavailable structures are not equivalent
to available-but-inactive physics. No GPU, biology, stable promotion, full-suite
rerun, automatic retry or follow-up capture is authorized by this handoff.

## D074: Accept explicit profile/no-op preparation, not trajectory correspondence

2026-09-12, REF-003e0 v2. On user instruction, add a separate versioned native
preparation adapter. Keep profiles-off SIM as the baseline, then compare
default-only profiles-on SIM, then the same profile with enabled zero-amplitude
Na/K/Cl events. The profile-enabled flag is the only new configuration change
relative to the previous SIM/event mapping. Retain the rejected D073 launcher,
packet, source and report rather than making that first attempt appear successful.

All six independently seeded passive/blocked preparations and 30 direct event
dispatches pass in 17.360 s. Initial values match retained INIT; native diffusion
bytes and between-configuration physical state/control records match exactly.
Profiles-off metadata has no resolved default or targets; enabled metadata
resolves `Base` to all seven cells / 30 faces. Extra tissue/cut profiles remain
absent. Record the inherited configured cutting request separately from its
absent effective event. No transport or integration occurs in this preflight.

Save successive core, dynamics, ready, metadata, dispatch and final records with
exclusive writes. In particular, persist ready-state evidence before optional
metadata access. A failure-injection test verifies that a metadata exception
cannot discard it. Keep the source's existing preparation fence and event observer
unchanged; never use observation to apply controls or replace native methods.

All 87 focused tests pass in 2.10 s, including actual saved preparation evidence;
the 59-file packet and 51-file source capsule are bound in the
[report/handoff](../reports/REF003E0_PROFILE_BRIDGE.md). All 352 accepted files /
51 production modules and prior evidence remain unchanged. No old full suite,
production matrix, retry, GPU or biological qualification is added.

Next specify and implement the full-loop phase/profile/no-op bridge, then
prospectively register its coverage and resource limits. Preparation equality
does not prove trajectory equality, full-loop observer noninterference, native
serialization/restart or a response to nonzero intervention. Retain original
material/charge/source-law/refinement criteria and observed/unobserved partners.
Use fresh phases; long captures and subsequent audits remain detached and
user-polled. See the [preparation contract](BETSE_PROFILE_BRIDGE_PREFLIGHT.md).

## D075: Pilot the full SIM loop at the accepted preparation inputs first

2026-09-12, REF-003e0. On user continuation, implement a separate full-loop
adapter and prospective [12-run pilot contract](BETSE_FULL_LOOP_BRIDGE.md).
Keep passive/blocked cases, matched constants, 25 µs and 1 ms from the passing
D074 preparation. For each, separately test profiles off, the default profile
on, and enabled zero-amplitude Na/K/Cl events, with independently seeded
observer-off partners. Broader two-constant-set / three-step SIM coverage stays
a later 72-run expanded bridge, not an automatic consequence of this pilot.

Use the fresh seed/SIM/init_core helper, then normal native run_sim_core once.
The native method owns dynamics setup, closure, integration and SIM saving.
Never reuse a preparation-probed phase or replace model methods. Extend the
frozen observer through one read-only profiling dispatcher; retain exact file,
object, event/flux/update-order and lifecycle gates. Save core/dynamics and
loop-entry physical copies before optional metadata; retain partial copies on
catchable failure and already-written evidence on timeout.

Require exact numerical correspondence to the retained INIT record, exact
observer-off partners and exact between-configuration physical trajectories.
Compare pre-event and post-flux boundaries correctly: the native loop resets
fluxes before events, and electroflux has an in-place voltage nonce. Record
native SIM-pickle presence separately from INIT; do not infer pickle byte
identity, restart or nonzero response qualification. Existing independent
material/charge/source-law/refinement criteria remain unchanged and are not
automatically rerun as part of the capture.

All 100 focused tests pass in 7.45 s. Fabricated lifecycle/event extensions of
retained data test the checker but are not native execution evidence. All 333
Python files pass lint/format checks. The 891-file preservation baseline allows
only seven existing status-document edits; all 352 accepted implementation
files / 51 production modules and earlier packets/adapters remain unchanged.
No Cells run, old full suite, production matrix or release promotion is added.

Register before a detached capture under 120-second worker / 150-second overall
elapsed gates, CPUs 0–3, 256 MiB panel storage and 32 MiB per-worker-file limits.
The prospective storage allowance is 136.30 MiB, not a measured runtime. Keep
enforcement boundaries explicit. Return control after launch, without polling,
automatic retry, independent audit or expanded campaign. A successful capture
remains pending a user-requested independent saved-data audit. See the
[prelaunch handoff](../reports/REF003E0_FULL_LOOP_PILOT.md).

## D076: Independently audit the saved narrow pilot before expanding it

2026-09-12, REF-003e0. On user continuation after the completed pilot's status
check, add a separate offline audit and detached focused-regression closeout.
D075's twelve native runs / 240 observed steps passed capture controls in
26.139 s. Preserve its 142-file packet, 58-file capsule, historical pending-audit
receipt and all earlier accepted/rejected evidence. No simulator is rerun.

The new audit reads JSON and pinned source text, not native pickles, and refuses
BETSE/Cells/NumPy/JAX imports. It independently checks metadata, physical and
event/step links, source/runtime provenance, observer/variant comparisons and
resource evidence, without calling the capture checker. Reuse the frozen
independent arithmetic functions for 88,956 flux/charge/current/concentration/
cell-and-bath-transfer comparisons over all six observed trajectories, retaining
the original tolerances. Validate native post-flux nonce semantics explicitly,
separately from exact zero-amplitude event noninterference.

All 65 new evidence preflight tests pass in 16.47 s, including rehashed
corruptions. The four new audit/test files bring tree quality checks to 337
Python files. The 903-file preservation baseline allows only seven existing
status-document edits; all 352 accepted files / 51 production modules stay
unchanged. Full numerical-audit success is not inferred from these preflight
tests. The independent numerical worker and 165-test combined focused suite
run detached under 90-second stage / 210-second overall and 64 MiB retained
artifact gates, on CPUs 0–3. No old full suite or production matrix rerun.

Only their successful closeout qualifies the narrow matched-constant 25 µs,
1 ms, seven-cell passive/blocked SIM pilot. Expanded constants/timesteps,
nonzero intervention, restart, biology, GPU and stable release remain separate.
Return control after launch without polling, automatic retry or new capture.
See the [audit contract](BETSE_FULL_LOOP_AUDIT.md) and
[prelaunch handoff](../reports/REF003E0_PILOT_AUDIT_HANDOFF.md).

## D077: Expand the audited SIM bridge without changing its native runner or criteria

2026-09-12, REF-003e0. The user approved continuation after D076's polled
closeout passed 88,956 independent comparisons and 165 tests in 32.682 s.
That completion qualifies the narrow matched-constant 25 µs, 1 ms, seven-cell
SIM pilot only. Preserve its historical capture/audit receipts, 142 capture
files, 11 audit-job files, 62 audited adapter sources and all earlier evidence.

Add a separate [expanded contract](BETSE_EXPANDED_BRIDGE.md), plan, context,
checker and detached supervisor. Run 72 fresh native SIM paths: passive/blocked,
source/matched F/R, 25/12.5/6.25 µs, profiles-off/default-on/zero-amplitude
controls and independent observed/unobserved partners. Require 3360 observed
steps, 1120 enabled-target dispatches, 36 observer pairs, 24 variant comparisons
and 12 exact numerical/physical original-pilot overlaps. Link the 24 retained
INIT mode references without rerunning Cells or modifying numerical tolerances.

Reuse D075's native row runner and full-loop observer unchanged. Static
metadata expectations vary only explicitly registered inputs; do not label
those expectations as actual preparations. Capture the real native loop-entry
state before metadata checks, and compare charge/voltage to the appropriate
retained INIT at that F/R and timestep. Preserve normal native lifecycle,
raw/elapsed clocks, post-flux nonce semantics, fixed control bytes and all
state/ownership/trace links. Serialization presence does not qualify restart.

All 125 focused tests pass in 17.67 s: actual overlap, all input mappings,
synthetic finer-step extensions, corruptions, coverage, resource refusal,
timeout preservation and detachment. Four Python files bring quality coverage
to 341 Python files. The 912-file preservation baseline permits only seven
existing status-document edits; all 352 accepted files / 51 production modules
remain unchanged. No expanded native result is inferred from synthetic tests.

Use actual pilot output sizes and runtime for prospective enlargement:
1,388,179,444 estimated bytes, 42,565,368 largest-file bytes and 549 seconds
including runtime allowance fit 2 GiB panel / 64 MiB worker-file / 600-second
worker / 660-second total limits, on CPUs 0–3 with single-threaded libraries.
The panel limit is checked between rows and at completion; only the per-file
worker limit is OS-enforced. No peak-RAM, optimization or GPU claim is made.
Keep only one group's baseline/current pair in memory, not the whole panel.

Freeze prelaunch tests/source/preservation, register and launch detached into
a fresh directory, then return without polling. Preserve partial evidence on
failure; no automatic retry, audit, regression or nonzero-response experiment.
A capture pass remains pending a separately requested independent arithmetic
audit/regression closeout. Biological, general-feature, organ, GPU and stable
release qualification remain outside scope. See the
[prelaunch handoff](../reports/REF003E0_EXPANDED_BRIDGE.md).

## D078: Independently close the expanded no-op bridge without rerunning either model

2026-09-12, REF-003e0. The user approved continuation after reviewing D077's
completed 72-run / 3360-step capture: 203.562 s, no Python warnings, 36 observer
pairs, 24 variant comparisons and 12 exact original-pilot overlaps. Preserve
the 802-file packet / 798 manifested payloads, 67 captured adapter sources,
all previous evidence and the unchanged 352 accepted files / 51 production
modules. Do not relabel the capture's historical pending-audit receipt.

Add a separate [offline audit](BETSE_EXPANDED_AUDIT.md), context, detached job
and evidence tests. Independently reconstruct metadata/coverage and physical
state/event/lifecycle links from saved arrays and pinned inputs. Read actual
entry charge at each row's F/R and timestep; recompute event-time conversion
without calling the capture checker. Preserve nonce semantics and all exact
observer, variant, INIT and original-pilot controls. Reuse only generic frozen
independent-audit primitives and the original arithmetic/tolerances, not the
narrow audit's hardcoded row counts or the capture's pass summaries.

The complete numerical audit has 1,232,616 comparisons: 36 observed rows × 266
initial/final checks plus 3360 steps × 364 checks. Keep variant-qualified labels
and process one control group at a time. The independent process forbids
BETSE/Cells/NumPy/JAX imports and never loads native pickles or integrates a
model. Capture data is not duplicated into the new audit packet.

Preflight tests cover actual saved rows across the full grid, controls,
metadata and rehashed-array corruptions, file/capsule integrity, import fences,
qualification gates, timeout preservation and detachment. All 143 pass in
48.73 s. The first preflight's 141 passes / two cross-filesystem fixture errors
are retained; only the test's temporary hard-link location changed. The final
receipt is frozen before registration. The detached closeout then runs
independent arithmetic and a five-module **433-test** focused regression.
Do not rerun the older full suite or production matrix.

The 922-file preservation baseline permits only the seven existing status
documents to change. Four new Python files extend the source capsule from 67
to 71; final quality and hashes are bound in prelaunch. Prospective resources
use measured pilot audit/regression timings, the 14× observed-step multiplier
and measured preflight duration with explicit allowances, not inherited narrow
pilot limits. Estimated 147-second stages and 11,628,348 new bytes fit
180-second stage / 420-second total and 64 MiB limits. Retain CPUs 0–3 and
single-threaded libraries. All 345 Python files pass quality checks.

Only the joint arithmetic/regression completion qualifies this registered
1 ms, seven-cell, both-F/R, three-timestep zero-amplitude bridge. A standalone
audit result remains pending regression. Return after detached launch without
polling, retry or automatic nonzero-response experiment. Biology, restart,
organ, GPU, feature-family parity and stable promotion remain separate.
See the [handoff](../reports/REF003E0_EXPANDED_AUDIT_HANDOFF.md).

## D079: Compile prescribed held interventions before testing their physical response

2026-09-12, REF-003e1. The user approved continuation after D078's expanded
no-op bridge was independently closed and user-reviewed. Its joint completion
passes 1,232,616 comparisons and 433 tests in 167.679 s, maximum normalized
error 0.185990. It qualifies only the registered 1 ms, seven-cell, both-F/R,
three-timestep zero-amplitude SIM bridge. Preserve the 802-file native packet,
11-file expanded audit packet, 71 captured adapter sources, all earlier
evidence and 352 accepted files / 51 production modules. Historical prelaunch,
capture and standalone pending-regression receipts are not rewritten.

Extend the frozen D072 plan in a [new held-input contract](BETSE_HELD_INTERVENTION.md)
and data-defined design, with a compiler into existing Cells controls. Propose
four conditions: default-profile baseline, enabled zero-amplitude event,
permanently blocked transport and smooth suppression/recovery. The first
response pilot will use matched constants and a fixed 25 µs hold over 1 ms:
eight native observed/unobserved runs and 24 Cells eager/JIT runs at h, h/2,
h/4. This is not yet a capture registration or native convergence qualification.

Control-only probes call the actual pinned native pulse, reproduce source-order
additive diffusion arithmetic and compare it with independently compiled
multiplicative inputs. Scale error by positive unsuppressed diffusion, never
the near-zero residual; retain the 2e-14 control tolerance and all original
physical criteria. Require exact immobile/static-blocked zeros. The probe is
not execution of the event handler, target selection or a physical response.

Generate times as integer products of one declared binary64 hold step; use
the same numeric schedule for all solver subdivisions. Actual production
parser/control/EventGrid probes check 36 condition/hold/subdivision configurations,
with distinct N/2N/4N grids within each fixed-input family and no sliver steps.
Check left/right boundary controls, active targets, padded/disabled fields and
retention of the final interval's control at T. No new endpoint event or pulse
evaluation at T is inserted. State, fresh right-side rates, preceding-update
native stored current and interval transfers remain separately labeled;
matching a timestamp alone is insufficient.

All 80 focused tests pass in 14.14 s; 348 Python files pass lint/format checks.
The first 79-pass / one-failure receipt is retained: its negative source-mutation
fixture assumed a single-line expression, while the real source uses line
breaks. Only the fixture's replacement target changed. Both actual control
probes and the source checker already passed. Preserve 932 pre-existing files,
allowing only the seven status documents to change. No production or old
frozen adapter changes, full-suite rerun, integration or long job is added.

Next preflight actual nonzero SIM preparation/dispatch against prescribed
effective diffusion and unchanged physical state, then implement control-aware
capture/checking and register the pilot with prospectively measured resources.
Do not relax old no-op assertions or constant-permeability checkers to handle
a new experiment. Broader h/F/R coverage, fixed-input solver versus forcing
refinement and a separate independent audit follow only on instruction. The
host-side input compiler imposes no BETSE dependency or per-step Python
callback inside future compiled GPU kernels; it does not establish GPU speed,
memory, accuracy or portability. Biology, restart, organs and stable promotion
remain outside this control-only slice. See the [report](../reports/REF003E1_CONTROL_DESIGN.md).

## D080: Verify real nonzero event application before integrating its response

2026-09-12, REF-003e1. Following the user's approval after D079's control-design
review, implement a separate [native dispatch preflight](BETSE_NONZERO_DISPATCH_PREFLIGHT.md),
not a response trajectory. Preserve D079's compiler/plan/review and all accepted
no-op/constant-permeability adapters unchanged. Use a new mapping, control-aware
checker and native preparation entry point. No production mechanism or solver
change is required to apply the declared intervention.

Use four fresh matched-constant, 25 µs / declared 1 ms SIM preparations:
default-profile baseline, enabled zero amplitude, static block and suppression/
recovery. Call the actual native event handler at all 40 raw `linspace(0,T,N)`
labels per condition, preserving the explicit N/(N−1) input-clock conversion.
The final raw label T represents elapsed T−h, not a new endpoint control. A
read-only native preparation fence rejects transport/integration; the existing
event observer records actual call/return states without replacing the handler.

Persist prepared physical state before metadata; validate initial state/topology
against qualified retained preparation and INIT before dispatch. Read actual
targets, profile/default/base diffusion, scalar/dynamic modifiers, function
names, multipliers and resolved pulse times. Preserve every completed event
immediately plus an aggregate trace; keep partial/open-event evidence on error.
The control-aware checker permits changes only to scheduled/effective diffusion.
All other recorded physical/control state and final metadata/topology must stay
unchanged. Compare diffusion to independently compiled declared controls at the
original 2e-14 baseline-scaled control tolerance, with exact additive composition,
immobile/static zeros and positive smooth-pulse residuals. Never normalize by
the nearly suppressed residual or relax physical trajectory criteria.

All 75 focused tests pass in 8.48 s and 352 Python files pass quality checks.
The first 74-test pass is retained; before freeze, initial-state checking was
moved ahead of dispatch and interrupted-dispatch persistence gained a test.
Freeze the 80-file adapter source inventory and prelaunch/protocol/test hashes
before actual native execution. The 942-file preservation baseline permits
only seven existing status documents to change.

Prospective resources use D074's 17.360-second six-preparation result and its
largest 29,538-byte state, with explicit allowances: estimate 33 worker seconds
and 46,197,248 bytes. Bind 45-second worker / 60-second attempt, 64 MiB panel /
16 MiB worker-file limits, CPUs 0–3 and single-thread numeric libraries. The
file bound is OS-enforced, panel size checked between rows and at completion;
neither is a peak-RAM measurement or response-simulation budget.

The actual native attempt passes **four preparations / 160 dispatches in
24.463 s**, including 80 enabled targeted / 40 nonzero-amplitude calls and
57,600 diffusion-value checks. Maximum baseline-scaled control error is
2.670623e-15; Python warnings are absent. Fresh physical setup and baseline/
zero-amplitude exact controls pass. Retain all 201 attempt files, including
200 manifested payloads, the 80-source capsule and 332 installed native Python
hashes. All 352 accepted files / 51 production modules and previous evidence
remain unchanged; neither transport nor integration ran.

Next implement/register the eight-native / 24-Cells control-aware response
pilot with observed/unobserved native partners, separate fixed-h Cells solver
subdivisions, correct rate/ledger observation sides and prospective resources.
Do not infer a response, nonzero full-loop noninterference, forcing/native
refinement, biological recovery, restart, GPU or organ qualification from
initial-state dispatch. No automatic trajectory, retry, long regression, audit
or stable promotion. See the [result](../reports/REF003E1_DISPATCH_PREFLIGHT.md).

## D081: Compare actual held-input responses without fitting production to BETSE

2026-09-13, REF-003e1. After D080's actual nonzero dispatch passed and the user
approved continuation, implement the [first response pilot](BETSE_HELD_RESPONSE_PILOT.md).
Use eight fresh native SIM runs and 24 unchanged Cells runs, four conditions,
matched F/R, seven cells / finite bath, 1 ms and a fixed 25 µs input hold. The
three Cells solver subdivisions at each backend share one prescribed input
table. Retain the D079 compiler, D080 preparation helpers, generic full-loop
observer, production runner and all old acceptance/evidence unchanged.

Add separate control-aware native lifecycle/state gates and saved-data
arithmetic. Check actual scheduled/effective diffusion at every interval
against independent prescribed values; permit only those controls to change
at dispatch. Preserve no-op retained overlaps, exact observer partners and
baseline/zero-amplitude response controls. Verify all stored field shapes,
precision/hashes, disabled routes, material positivity, owner/bath ledgers,
charge, GHK flux and current signs. Native arithmetic uses each interval's
actual effective Dm, not the final Dm for the whole response.

Compare state/amount/cumulative transfer at 41 boundaries and fresh rates at
40 interval starts; separately compare the 40 interval transfers. The native
post-update stored current belongs to the preceding update, not a fresh RHS
at that state. Preserve source-order voltage nonce effects and validate the
real final Cells RHS against the last held input, while leaving the unmatched
native endpoint rate absent. Do not reinterpret permeability recovery as
recovery of the physical state or organism.

Retain all earlier physical criteria and explicitly retain any coarse-native
baseline failure: 25 µs previously missed shared-bath comparison tolerances.
This first response pilot is not native or forcing convergence qualification;
one native timestep/hold cannot establish either. No finer solution may be
silently substituted or threshold relaxed. Future native fixed-input and input-
sampling refinement need their own explicit experiment and independent audit.

Freeze seven new Python files / one input plan with the existing 80 adapter
inputs, focused test receipts, original runtime and prospective resources.
The 954-file preservation baseline allows only the seven status documents to
change; 352 accepted files / 51 production modules and D080's 201-file packet
stay unchanged. Keep earlier failing software receipts as evidence; synthetic
fixtures test rejection/arithmetic, not new biological or response validity.
All 122 final focused tests pass in 21.41 s, with 359 Python files passing
quality checks. Earlier test count and shared-mutable-fixture failures are
retained in their receipts; neither amended physical tolerances or equations.

Resource estimates include the slowest retained eager step cost and explicit
allowances: native/Cells/comparison 134/1894/120 s, approximately 136 MB files.
Bind stage caps 180/2100/180 s, total 2520 s, CPUs 0–3, single-thread numeric
libraries, 512 MiB artifacts and OS-enforced 64 MiB worker files. Neither total
file budget nor elapsed estimates measure peak RAM or GPU performance. Keep
native, Cells and model-free comparison in separate processes/environments.

Launch only the approved capture detached, persist completed results/logs and
failure evidence, then return control without polling. A failed numerical
comparison is retained and makes the job fail, without retry/expansion. A pass
is still pending a separately requested independent audit/regression and does
not qualify biology, GPU, restart, organs or general BETSE parity. Production
still consumes ordinary numeric controls: this introduces no native dependency
or Python event callback into future pure JAX GPU kernels.

## D082: Audit a rejection without rewriting physics, reports or user metadata

2026-09-13, REF-003e1. Following user review of D081's completed numerical
rejection, implement the [saved-data failure audit](BETSE_HELD_RESPONSE_AUDIT.md)
and [future refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md). All eight
native / 24 Cells trajectories completed in 715.769 s without warnings; 150
of 345,576 comparisons failed. Preserve all 150 capture files, original 88
adapter inputs, numerical criteria and 352 accepted files / 51 production
modules. Neither simulator is rerun or edited.

The internal-law report's count says zero failures, but its mutable list aliases
later cross-engine failures. Reproduce the original checker exactly, retain it
unchanged, and add a separate deep-snapshot reporter and versioned corrected
review. Change only `internal_laws.first_failures`; the 150-failure physical
verdict stays rejected. Do not overwrite a captured source or report to repair
its display. Rebuild all 147,312 comparison-surface checks with separately
implemented owner/amount/rate/transfer arithmetic and normalization, retaining
the complete 150-failure ledger. Label frozen-law helper reuse honestly as
reproducibility, not an independently derived second physical oracle.

The user committed an exact `.gitignore` addition during preparation:
`reports/ref-*.xml`, commit `fa5ec7127cfb0062e1151904b90f25a38b3e9bd5`.
Leave that operational change intact, authenticate its old/new bytes and pin
now-ignored receipts using the union with historical inventories. The new
baseline contains 969 files; only the seven existing status documents may
change in this work. Run all original 122 tests unchanged, recording the
expected 121-pass / one-failed metadata preservation guard explicitly as a
non-green legacy suite. Permit exactly that known guard outcome in audit
orchestration; any different/additional failure, error or skip blocks closeout.
Do not patch the test, relabel it as passing or weaken physical criteria.

All 70 new focused software tests pass in 12.01 s. Place four audit modules
in a nested directory to preserve the historical flat source inventory; freeze
a separate 92-source capsule and prospective prelaunch evidence. Bind audit,
legacy regression and new regression to 90/90/120 s stages, 360 s total,
CPUs 0–3, 16 MiB artifacts and OS-enforced 8 MiB worker files. Aggregate file
checks are not a filesystem quota or peak-RAM claim. Launch once detached,
return without polling and preserve failures without automatic retry. A
successful joint receipt is `failure_audit_closed_response_rejected`, not a
qualified response or all-green legacy test result.

Use saved constant-input 25/12.5/6.25 µs native baselines for a diagnostic
timestep ladder against the new finest Cells baseline; focused checks find
roughly halving amount error and the finest case meets unchanged criteria.
Do not extrapolate this to the pulse: native event sampling occurs at each
integration step, so native pulse refinement changes solver and forcing
together. A fixed held-table native substep mechanism is not established.
The next proposed bounded extension needs actual finer-h dispatch preflight,
fixed-h Cells subdivisions and separate forcing-sensitivity reports. It is
design only, not a new capture registration or automatic campaign. Keep
numeric input tables, solver steps and observation/accounting contracts separate
for future multirate/GPU work. No production change, physiology, biology,
restart, organ or GPU qualification follows from the audit.

## D083: Preflight finer pulse inputs before refining response trajectories

2026-09-13, REF-003e1. After the user-reviewed D082 joint closeout completed
in 50.390 s and the user approved continuation, implement the first bounded
step of the [refinement design](BETSE_HELD_RESPONSE_REFINEMENT.md):
[finer native preparation/dispatch](BETSE_REFINED_DISPATCH_PREFLIGHT.md), not a
new response trajectory. D082 reproduced the 345,576 original comparisons and
independently rebuilt all 147,312 surface checks. Its 150 shared-bath Na/K
failures, separate reporting correction, 70 passing new tests and explicit
121-pass / one-failed legacy metadata-guard outcome remain frozen.

Use eight fresh preparations at 12.5/6.25 µs, matched constants, the same
seven-cell finite bath and all four controls. Check all 960 direct event calls,
including 480 enabled targeted and 240 nonzero-amplitude calls. No transport,
concentration update, integrator or Cells run may execute. Reuse the frozen
preparation fence, event observer, metadata reader and per-event durable writer;
add a separately versioned clock mapping and variable-length control checker.
The old 25 µs declared mapping/metadata must remain an exact software overlap.
Retained initial states are correspondence references, never loaded restarts.

Freeze prescribed controls and YAML/clock mappings before execution. Preserve
the N/(N−1) conversion and T−h final held input; do not introduce a new elapsed-
endpoint pulse. Check actual targets/modifiers, initial state, event chaining,
physical-state invariance and exact baseline/zero controls. All 345,600 diffusion
values use the original 2e-14 positive-baseline-scaled criterion; no physical
threshold is relaxed. Persist ready state before metadata and each completed
event immediately, retaining partial/open events on exceptions. The controller's
source/runtime/result/aggregate linkage checks are not an independent numerical
audit of a response.

All 109 focused software tests pass in 36.21 s, using saved initial states and
fabricated event/receipt data only. Preserve 979 baseline files, all 150 response
files / 16 audit files and 352 accepted files / 51 production modules. Five new
Python modules and one plan in a nested adapter directory make a 98-input
capsule, leaving the old flat 88 inputs and four audit modules unchanged. Only
seven existing status documents change. Retain the exact recorded user ignore-
rule amendment and now-ignored historical XML receipts, without altering or
rerunning old regression assertions.

Use D080's measured 24.463 s, 25,283,869-byte attempt and largest 3,466,668-byte
aggregate as the prospective basis. Sixfold call scaling plus explicit
allowances estimate 251 worker seconds, 206,406,234 total bytes and 17,333,340
bytes for the largest worker file. Bind 300-second native worker / 360-second
attempt, CPUs 0–3, single-thread numeric libraries, 256 MiB artifacts and
OS-enforced 32 MiB worker files. Aggregate checking is not a filesystem quota
or a peak-RAM measurement. Launch once detached and return for user status;
preserve failures with no automatic retry, response or follow-up audit.

A passing initial-state dispatch gate still does not qualify native integration,
forcing convergence or observer noninterference during transport. A later
response panel needs actual fixed-h Cells subdivisions and explicitly labelled
joint native/forcing refinement. Native pulse resampling is not isolated
solver refinement under an unchanged input table. Keep that distinction in the
generic simulator's future multirate/organ coupling contracts; no production
callback, model change or biological/GPU claim is introduced here.

## D084: Separate fixed-input response gates from forcing sensitivity

2026-09-13, REF-003e1. The user-reviewed D083 actual preflight passes in
116.002 s (eight preparations, 960 dispatches, 345,600 diffusion checks,
maximum baseline-scaled error 2.671e-15, no integration). Proceed with a
[separately versioned finer response adapter](BETSE_REFINED_RESPONSE_PANEL.md).
Reuse D081's frozen 25 µs response, not a new coarse rerun; authenticate all
150 original / 16 audit / 1042 dispatch files. Preserve the 990-file baseline,
original criteria, accepted production and the exact recorded ignore-rule change.

New work is 16 native observer-paired runs and 48 Cells eager/JIT runs at
12.5/6.25 µs. At each hold, retain all four controls and 1/2/4 Cells subdivisions
under identical input tables. The unchanged compiler/exporter/runner and native
observer remain outside the seven new Python modules plus one plan. A nested
106-input capsule preserves the old flat 88 inputs and all audit/dispatch source.

Require internal laws, capture controls, fixed-input Cells solver refinement and
CPU backend agreement at every hold. Require cross-engine agreement at the
finest 6.25 µs hold under original trajectory limits. Keep all coarse/intermediate
failures as explicit rejections in all-comparison totals, separate from required
gate totals. Across successive holds, report 41-boundary diagnostics only:
native pulse changes combine integration and input resampling; finest-subdivision
Cells changes assess input-hold sensitivity. No native/forcing/trajectory,
biology or GPU qualification is set by the capture alone.

Inspect all N+1 state/ledger observations, N fresh interval-start native rates
and N interval transfers. Validate Cells' terminal RHS against its final hold,
without inventing a native terminal RHS. Original-report replay and new immutable
summaries are separate: the old mutable-list reporting defect stays archived.

The first 100-test software attempt reports 96 passes / four failures in
60.79 s. Correct the new native checker's reused step-count variable, the
full-grid comparison-count expectation and the test's wrong fence exception
expectation. Keep that receipt; add late-grid corruption coverage and durable
launch-failure/software-only-launch tests. All 24 targeted checks pass in
31.84 s, reproducing the complete original coarse arithmetic/surfaces exactly.
The complete comparison has 2,494,936 checks, including 2,298,936 required;
failure counts and bounded detailed examples remain separate by scope.
The final 114-test regression ran detached under a 180-second worker /
300-second total budget and now passes without failures/errors/skips in
64.15 s pytest / 95.688 s total. All 375 Python files pass whole-tree lint/format
checks. Its source capsule, registration, JUnit and manifested payloads verify.
After user review and renewed approval, freeze response prelaunch against this
exact software completion and launch only the 16-native / 48-Cells capture.
The software job itself launched no transport. Preserve the historical handoff
and source bytes; update only the seven mutable status documents. Actual
execution receipts establish capture state; return without polling or an audit.

The prospective response estimate is 239/10,004/125 s and 520,964,299 bytes,
based on D081 measured costs with explicit allowances. Bind 300/10,800/300-second
native/Cells/comparison stages, 11,700-second total, CPUs 0–3, CPU float64,
1 GiB artifacts and OS-enforced 64 MiB worker files. No polling, automatic
retry, refinement expansion or follow-up audit. Peak RAM and GPU speed are
unmeasured. Keep sampling, integration, readout sides and conserved interface
transfers separate when later adding multirate tissue/organ coupling.

## D085: Raise the trace cap without changing science or rerunning completed rows

2026-09-13, REF-003e1. The user authorizes a sensible resource amendment after
D084 stopped at the configured trace-storage guard. All 16 native / 26 Cells
runs completed in the 1830.727 s attempt; its 27th Cells row never integrated.
The largest registered reservation is 25,838,496 bytes (24.6415 MiB), beyond
16 MiB. This is not a measured out-of-memory event. 32 MiB would fit; select
64 MiB for headroom in only the eight previously unexecuted 640-step definitions.
Keep all other definitions byte-equivalent, including their old trace caps.

The [versioned continuation](BETSE_TRACE_BUDGET_CONTINUATION.md) changes no
physics, timestep, input, observation, solver/backend, tolerance, production or
old adapter source. Read completed results directly from their original paths,
with exact registration, capsule and payload hashes. Preserve all 241 original
files and their failed status. Do not invent an aggregate Cells worker receipt
that never existed. The read-only reuse gate passes 666,108 internal checks,
zero failures, with maximum normalized error 0.18106284912210208; that is not
an independent audit or cross-engine response qualification.

Preflight the actual production parser/timeline/trace guard over all 48
definitions before launch and again before the first new rollout. All 48 pass;
the old limits reproduce precisely eight guard rejections, without integration.
All 47 focused tests pass in 22.88 s; all 380 Python files pass quality checks.
Preserve D084's prior 114-test completion rather than rerunning it. Five new
modules and one plan extend the frozen 106-input capsule to 112, leaving the
original flat 88 inputs unchanged. The 1013-file baseline permits only seven
established status-document edits; accepted 352 files / 51 production modules
and all earlier evidence stay unchanged.

New execution is 22 Cells rows / 8480 steps (4000 eager / 4480 JIT), no native
rerun. Run the unchanged full comparison over reused and new records, retaining
2,494,936 checks, 2,298,936 required checks and all original 150 coarse failures.
Use CPU 0–3, float64 and single-thread libraries, 6600/300-second stage limits
and a two-hour total. Retained-plus-new artifacts share a 1 GiB cap; individual
worker files retain OS-enforced 64 MiB. D084 measurements plus allowances
estimate 5295 Cells seconds, 502,363,957 combined bytes and a 16,791,168-byte
largest worker file. Trace reservation, serialized storage and total peak RAM
remain distinct; no peak-RAM or GPU performance measurement is claimed.

Freeze the [handoff](../reports/REF003E1_TRACE_RESUME_HANDOFF.md) and prelaunch,
launch once into a fresh continuation directory and return without polling.
Durable actual receipts alone determine execution state. No automatic retry,
refinement expansion or subsequent audit/regression. Keep fixed-input solver
refinement, native integration/resampling and input-hold sensitivity separate;
no new trajectory, native/forcing convergence, biological or GPU qualification.
Future multiscale workload preflight should examine the entire declared grid,
not just a representative row; this does not require a new production solver
or streaming subsystem for the present small correction.

## D086: Audit finest-held agreement without hiding input-refinement failures

2026-09-13, REF-003e1. The user reviewed D085's completed continuation and asked
to proceed with independent audit. The capture completed in 2239.322 s and
reports 2,298,936 required checks passing, maximum normalized error
0.5592883878208624. Its 4173 diagnostic failures remain: 150 coarse, 40
intermediate and 3983 across-input-hold comparisons. Do not reclassify or discard
them when reviewing the finest-held result.

The [new saved-data closeout](BETSE_REFINED_RESPONSE_AUDIT.md) authenticates the
56-file continuation and 241-file resource failure, preserving split provenance
without copying old results or inventing an aggregate old Cells worker receipt.
The 1027-file baseline permits only seven established status-document edits.
All older source/receipt chains, the exact ignore-rule amendment, 352 accepted
files / 51 production modules, definitions and scientific criteria stay unchanged.

Replay all 2,494,936 frozen comparisons exactly. Separately rebuild 1,121,904
surface checks over 132 scopes, using D082's independent saved-array/`fsum`
construction, new variable-grid loops and independent scope assembly. This is
separate from the 1,373,032 replayed internal law/accounting checks. Preserve full
41/81/161 boundary coverage, all interval transfers and fresh rates, and exact
41-boundary across-hold projections. Do not invent a native terminal RHS.
Apply the original physical thresholds throughout; retain the earlier allowance
for diagnostic reconstruction roundoff only. Save every failure and verify
ledger/summary linkage, not merely a truncated first-100 list.

The first preflight retains 94 passes / one test failure in 25.53 s: a new test
expected the wrong import-fence exception. The existing guard correctly raises
`RuntimeError`. Correct only that test and add full-loader/output-linkage checks.
All 105 new tests now pass in 28.38 s; all 385 Python files pass quality checks.
Five new modules plus one plan make a 118-input capsule, leaving the frozen 112
inputs and original flat 88 unchanged. Run the 231 prior D082/D084/D085 tests
unchanged alongside the 105 new tests, requiring all 336 exact identities and
zero failures/errors/skips. The historical 121-pass / one expected metadata-guard
failure remains separately preserved, not relabelled green.

Bound the detached audit/regression at 300/300-second stages, 900-second total,
CPU 0–3 and single-thread libraries. New audit artifacts have a 64 MiB aggregate
cap and OS-enforced 16 MiB file cap; these are not trace-memory or peak-RAM limits.
Measured costs plus allowances estimate 217/252 stage seconds and 11,222,792
output bytes. Read simulations in place; no integration, packet copies, new
dependencies, production changes or whole-simulator acceptance rerun.

Only a passing joint closeout can set the narrowly named
`finest_held_response_qualified` flag, bound to seven cells, 1 ms, matched
constants, four conditions, 6.25 µs held input and the declared CPU backends/
subdivisions. Native convergence, forcing convergence, biology and GPU remain
unqualified. Actual receipts establish execution state; return after one detached
launch without polling, retry, simulation or a subsequent job. For future
multiscale coupling, distinguish integration accuracy under a fixed interface
input from sensitivity to interface exchange/input-sampling intervals.

### D086 actual closeout

The user-reviewed joint completion at
`runs/ref-003e1-refined-response-audit-2026-09-13/audit-01/completion.json` now
passes in 249.644 s: 336 tests, zero failures/errors/skips; all 2,298,936 required
checks and 1,121,904 independently rebuilt surface comparisons. The scoped
`finest_held_response_qualified` flag is true; native/forcing convergence,
biology and GPU remain false. All 4173 diagnostic failures remain. No simulator
rerun or automatic follow-up. Earlier handoff, stage audit, source and receipt
bytes are not rewritten to incorporate this later result.

## D087: Validate active channel kinetics before coupled native feedback

2026-09-13, REF-004a. The user approved the channel-first next step after the
passive audit. [Isolated Kv1.5 contact](BETSE_VOLTAGE_GATE_CONTACT.md) reuses
the existing continuous gate kernel and shared RK4; production remains unchanged.
Keep the adapter outside the installed simulator and native dependencies in
their existing separate environment. No generic registry or GPU optimization.

Compare the actual pinned native `Kv1p5.init/run` with the 70-digit continuous
solution and each method's own discrete propagator. Temperature is the existing
298.15 K engineering regime, not the passive fixture's 310.15 K. Native equilibrium
initialization is checked separately from explicit non-equilibrium fixture states.
No membrane/current/reversal mapping is inferred from this kinetic-only contact.
Prescribed gate voltage is not a whole-cell electrode clamp.

Six protocols span fast opening, closing, seconds-long inactivation/recovery,
exact pulse events and equal-open-fraction states with distinct m/h history.
Eighteen native/eighteen compiled-Cells runs use fixed 1/0.5/0.25 ms steps;
kinetics and one RK4 step also cover NumPy/eager/JIT. Check all real Cells stages
and native updates without clipping. Observations do not redefine either solver.
Limits and clocks are fixed before actual capture; retain all errors and label
roundoff-limited order estimates rather than claiming observed convergence there.

All 63 short preflight tests pass in 1.11 s (earlier 41/62-pass receipts retained),
before one detached 180-second / 64 MiB attempt,
CPU 0–3 and single-thread libraries. Preserve completion/failure/logs, return
without polling, and require a later user instruction for actual-packet audit or
coupled-cell expansion. A raw pass is `capture_pass_pending_audit`, not biological
validation, general BETSE parity, full world-runner acceptance or GPU qualification.
The prior passive across-input-hold limitations remain open. Later multiscale
approximations must retain or explicitly approximate both gate histories and
separately validate their fast/slow coupling error.

## D088: Close isolated gating; verify transport ownership before coupled feedback

2026-09-13, REF-004a closeout / REF-004b design. The user reviewed the passing
11.971-second isolated capture and requested independent audit and the next
coupled plan. [Actual closeout](../reports/REF004A_KV1P5_CLOSEOUT.md) now passes
in 0.979 s. Replay and independently rebuild every one of the 11,266 numerical
rows using 80-digit SI expressions and affine-map powers of explicit native/RK4
steps. Retain 36 measured and 12 roundoff-limited refinements, plus six explicit
hidden-history checks. All 102 focused tests pass in 2.58 s; all 392 Python
files pass quality checks. No simulator import/rerun, changed criterion, new
dependency, production edit or evidence rewrite. Only isolated gating is qualified.

The [source-reviewed coupled plan](BETSE_COUPLED_CHANNEL_PLAN.md) uses existing
finite-bath composition. Native `apply to: all` still supplies a face-target
array; per-cell reduction needs demonstrated within-cell gate/voltage uniformity.
The native channel runner updates ion concentrations directly and records
channel flux/current separately from ordinary membrane fluxes. It advances
gates before that transfer, whereas Cells uses shared RK4 stages. Preserve
those numerical distinctions, the current sign and one-transfer ownership;
do not patch the engine to imitate native loop ordering or hide double counting.

Next implement only a 298.15 K preparation/transport preflight: network-off,
empty-network, zero-permeability channel and active channel controls; real
target/core objects; same-state constitutive checks; one conservative update
and charge/voltage bookkeeping. Register limits/resources before native work.
No default auxiliary network, synthetic pump, voltage clamp, full coupled loop,
channel catalog or GPU job is introduced here. Physiological calibration and
the old passive input-sampling limitations remain separate. No further job
was automatically launched after the short closeout.

## D089: Isolate native channel ownership before closing the feedback loop

2026-09-14, REF-004b. Implement the [setup/single-transfer preflight](BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md)
approved after D088. Use four minimal native configurations and three fresh
states each; preserve real target arrays, initial absent P, independent m/h,
native gate-before-transfer ordering and explicit current export. Background
leak, pumps, junction transport and auxiliary chemistry are off. The empty
network's charge-balancing hook must not change ion inventories.

Keep 298.15 K, matched constants, fixed seven-cell / thirty-face geometry and
one finite well-mixed bath. Preserve actual fixed-ion charge and residuals, not
silent neutrality. Compare native channel flux to unchanged Cells RHS at the
same post-gate/pre-transfer state. A prescribed 25 microsecond ledger increment
checks ownership and voltage; it is not a replacement solver, RK4 step or
coupled-trajectory qualification. No production or dependency change.

All 76 software checks pass in 2.03 s, with earlier receipts preserved. Freeze
63 capsule inputs, 393 earlier sources, accepted implementation and original
isolated-channel evidence before one detached native/Cells attempt. Maximum
120 seconds per worker, 300 seconds total, 128 MiB artifacts and 32 MiB per file,
CPU 0–3 and float64. File quotas are not memory ceilings. Keep all failures and
partial artifacts; no polling, automatic retry, audit or dynamic expansion.
Actual receipts are separate from the [prelaunch handoff](../reports/REF004B_TRANSPORT_PREFLIGHT_HANDOFF.md).
A later user-requested audit must precede a refined coupled pilot. Organ-scale,
physiological, broad BETSE parity and GPU claims remain outside this stage.

## D090: Correct the native input representation without changing the experiment

2026-09-14, REF-004b. The user reviewed D089's 4.672-second setup failure and
approved correction plus a fresh bounded attempt. Our null biomolecule value
violated BETSE's runtime sequence annotation at `tissue_init`. Three network-off
cases completed, but no channel or Cells comparison ran. Preserve the original
failure and all 22 packet files; do not recast a setup failure as a physics result.

The [configuration-only successor](BETSE_CHANNEL_SETUP_FIX.md) changes null to
an empty biomolecule list. Keep all other network presence semantics, numerical
cases, equations, constants, temperature, timestep, tolerances and resources.
The versioned native worker differs only in its configuration-provider call;
enforce that with AST comparison. Import the frozen Cells worker and numerical
checker directly. No production modification or runtime monkeypatch.

All 107 focused tests pass in 7.00 s, including the original 76 and 31 new tests.
Real native YAML loading plus its annotation/type-checking contract rejects the
old null and accepts the corrected sequence in all four controls (4.143 s).
This is explicitly not full native initialization or transport evidence. Freeze
the 11-file contract packet, passing XML, 70-input capsule and prior-preservation
receipt before the new numerical capture.

Re-execute all twelve registered cases fresh, including the three previous
network-off cases, under the unchanged 300-second / 128 MiB bounds. This is the
user-approved new attempt, not an automatic retry. No polling, automatic audit,
regression campaign or full dynamic pilot follows. Any pass remains pending
independent closeout; biological, broad parity and GPU claims do not advance.

## D091: Reproduce the registered environment; preserve the runtime guard

2026-09-14, REF-004b. The user reviewed D090's 7.084-second failure and resumed
this correction after the infographic task. All twelve native cases executed,
but Cells stopped before transfer: the launcher set `JAX_DISABLE_JIT=false`
while the registered accepted runtime records null/absence. Preserve the 51-file
packet and all seventy old source inputs, alongside D089's earlier failure.

The [environment-only successor](BETSE_CHANNEL_RUNTIME_FIX.md) constructs child
flags from the exact registered values before importing JAX. Remove registered-
null variables rather than inheriting them or substituting equivalent-looking
strings. Keep the existing strict runtime equality, CPU/float64/enabled-JIT
guard, production implementation and every numerical criterion unchanged.
The native worker, Cells worker and comparator remain frozen imports.

All 152 focused tests pass in 13.25 s (107 original / 45 new). Five fresh-process
probes enter the actual Cells worker in 4.589 s total: corrected startup reaches
the deliberately absent native-input file; explicit-false, empty-XLA,
disabled-JIT and wrong-package controls fail at their expected guards. These
are startup-only probes, not model integration or transport evidence. Actual
loaded production hashes, runtime, precision, CPU affinity and exceptions are
retained. No monkeypatch or relaxed identity comparison.

Freeze 76 source inputs, both amendments/preservations, original native contract,
passing focused XML and the 11-file startup packet before the fresh twelve-case
capture. Re-execute native cases rather than relabelling old output. Same CPUs,
120 seconds per worker, 300 seconds total, 128 MiB aggregate and 32 MiB per file.
Launch once detached, return control, and retain any failure. No polling,
automatic retry, audit or full dynamic expansion. A pass still needs separately
requested independent closeout; broad parity, biology and GPU remain unqualified.

## D092: Independently reconstruct the single-transfer evidence before dynamics

2026-09-14, REF-004b. The user reviewed D091's 21.272-second / 37,068-comparison
pass and requested independent audit and the next small step. Preserve every
captured byte and both earlier failures. The [new audit](BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md)
first exactly replays the old comparator, then independently reconstructs all
numerical rows from raw fields with 80-digit Decimal arithmetic. No original
formula/compiler/comparator helper is imported by the independent module.
Use unchanged absolute-plus-relative-to-expected tolerances; audit actual and
expected values, mapping units, hidden m/h, finite-bath conservation, current
signs and voltage/charge. Reconcile partial native/definition records as well.

All 220 focused tests pass in 33.27 s (152 original / 68 new). Preserve the
59-pass/seven-error first receipt and 67-pass/one-failure second receipt:
corrected an audit-only null-channel representation assumption and a test's
exception boundary for a correctly rejected hidden-state corruption. No model,
physical equation, original comparison or tolerance changed.

Bind 54 capture files, 76 unchanged capture inputs, 83 combined audit/capture
source inputs, passing XML and original receipt/source identities before one
detached audit. The actual audit forbids model imports, reruns neither simulator
nor any prior audit, and has a 120-second / 64 MiB ceiling. Return without
polling, automatic retry or follow-up. Only an actual successful completion
qualifies the prescribed single-transfer scope; original pending-audit receipts
remain unmodified.

The [next coupled-pilot outline](BETSE_CHANNEL_DYNAMIC_PILOT.md) is conditional:
close the voltage–gate feedback loop using each engine's own evolving state,
check real full-loop preparation and observer neutrality, then independently
refine constant-control dynamics. A 2 ms horizon is merely a candidate pending
signal, numerical and resource checks. No trajectory, organ, physiological or
GPU result is implied, and no dynamic simulation is launched by this decision.

## D093: Verify real full-loop initialization and prepare independent feedback dynamics

2026-09-14, REF-004b. The user requested both next steps. D092's actual independent
audit now closes the single-transfer contact in **3.215 s**: 37,068 comparisons,
zero failures, twelve definition mappings and two hidden-state controls. Preserve
that nine-file audit packet, the 54-file original capture, both prior failures and
all accepted production. Do not rewrite original pending-audit receipts.

Add [bounded full-loop preparation](BETSE_CHANNEL_LOOP_PREPARATION.md) and a
[feedback-pilot implementation design](BETSE_CHANNEL_FEEDBACK_DESIGN.md). Native
`run_sim_core` owns real INIT dynamics initialization, storage reset, voltage
closure, stepping, sampling and serialization. Test four controls with observed/
unobserved counterparts, eight updates each at 25 µs. Arbitrary m/h is not a
native configuration option: apply the explicit 0.2/0.6 fixture once at successful
`init_dynamics` return in both modes. This is declared mutating initial setup,
separate from the optional read-only observer. No replaced model method or copied
native time loop. Do not run a fixture on exception unwinding.

Observe each gate/transfer/current/ordinary/voltage boundary. Retain absent initial
P, actual scalar-to-face constant modulation and minute native input mutation.
Map native labels separately from elapsed update time. Reconstruct exported
float64 bytes; check paired state/history equality and native-method gate/flux/
conservation/current/charge accounting. Retain both native full-object restart
artifacts without claiming restart replay or equality of path-dependent pickles.

Prepare a model-free 80-digit continuous coupled vector field and twelve candidate
Cells definitions using the existing parser, initial-state/RHS checks, timeline
and resource estimator. Software checks include nonuniform per-cell states,
shared-bath cross-cell feedback and distinct hidden gates at equal initial P.
Keep 2 ms and distinct native/Cells refinement grids as candidates, not an accuracy
qualification. The preparation runs **zero Cells integration steps**. A later
version must select and converge an independent numerical reference and register
dynamic tolerances/resources before capture. Each engine will evolve its own
complete state through its own method; no injection of native post-gates.

Bind all source/receipt/runtime identities before one detached preparation,
CPU 0–3 float64, 240 s overall, 128 MiB aggregate / 32 MiB per-file artifacts.
All 96 focused tests pass in 18.70 s; the earlier 83- and 95-pass receipts remain.
Repository lint/format/diff checks pass. The 94-input source capsule and passing
XML bind the implementation; software uses labeled synthetic lifecycle/trajectory
packets and existing production initial-state/RHS/resource checks, not a native
trajectory claim. The actual registered native capture remains separate.
Preserve partial failures and stop without polling, retry or automatic audit/
dynamic follow-up. This strengthens existing coupling interfaces, not production
feature scope; biological, general BETSE, GPU and multiscale accuracy claims do
not change.

## D094: Audit preparation and full-state readiness before the dynamic pilot

2026-09-14, REF-004b. The user reviewed D093's successful capture and requested
the next step. Its actual receipt reports **18.031 s**, eight native runs /
64 updates (32 observed), **73,744 native boundary comparisons + 348 Cells
initial-rate comparisons**, zero failures, no warnings and twelve candidate
definitions. Preserve its 74-file packet and 94 source inputs, including the
original pending-audit completion. No Cells integration occurred.

Implement a new nested [independent saved-data audit](BETSE_CHANNEL_LOOP_CLOSEOUT.md),
with exact frozen native replay, frozen initial-rate packet replay and separate
80-digit mathematical reconstruction of every numerical identity. Check complete
float64 arrays and bytes, partial records, observer-on/off equality, elapsed/native
clock mapping, full initial states/RHS and inactive padding. Independently rebuild
candidate definitions from actual mobile and auxiliary-ion inventories, including
fixed charge, owner maps and capacitor anchors. Expand the unchanged trace
reservation formula independently. Do not call either production RHS or parser,
advance either engine, unpickle native restart files, reanchor voltage or relax
tolerances. The model-free continuous vector field is still not a numerical
reference solution.

Authenticate the entire source/runtime/provenance chain and prior failures,
including unchanged 352 accepted implementation files / 51 production modules.
Keep all 96 D093 software tests and add saved-data reconstruction, arithmetic,
corruption and import-boundary controls. Bind the passing XML and a 101-input
capsule before one detached saved-data audit: 120 seconds, 64 MiB aggregate /
32 MiB per file, CPUs 0–3, no polling, retries or automatic follow-up. Preserve
failed software receipts and actual numerical failures separately.

All **176 focused tests pass in 25.21 s** (96 original / 80 new), including
reconstruction of every saved comparison and fresh-process model-free
authentication. The first receipt retains 162 passes / eight failures caused by
new tests expecting the wrong exception type from correctly rejecting guards.
Correct only those expectations; no physics or tolerance changes. Repository
lint, format and whitespace checks pass. The [handoff](../reports/REF004B_LOOP_AUDIT_HANDOFF.md)
records the source/test bindings before the single detached audit; software
preflight is not the registered numerical closeout receipt.

A pass qualifies only preparation/readiness. Independently converging a continuous
reference integrator, selecting dynamic error criteria and registering the
coupled panel remain later steps on user instruction. Each future engine must
advance its own complete state. No broader BETSE, biology, GPU, restart replay or
multiscale accuracy claim is implied.

## D095: Gate the coupled pilot on independent continuous-reference convergence

2026-09-15, REF-004b. The user requested both next stages after D094's actual
audit passed in 5.541 s: all 74,092 comparisons, zero failures. Preserve that
nine-file audit, D093's preparation, every older failure/capture, 101 existing
source inputs and accepted 352 implementation files / 51 production modules.

Implement the [reference-gated feedback pilot](BETSE_CHANNEL_FEEDBACK_PILOT.md)
outside production. Use the independently checked 80-digit vector field with
explicit q, separate present-channel m/h and dissipated-energy coordinates;
integrate float64 values with base/tight DOP853 and an independent-algorithm
Radau check. Save accepted states, method-native dense polynomials and reference
samples. Validate dense replay, analytic blocked kinetics, exact-zero controls,
thermodynamics and convergence. Do not describe float64 integration as 80-digit
integration or two algorithms in SciPy as independent library implementations.

Select a 2 ms constant-control panel, with the previously proposed native and
Cells refinement grids. Run 12 native observed/unobserved pairs, 12 compiled /
four eager production JAX trajectories and four complete 1 ms checkpoint resumes.
The production runner has eager/compiled JAX paths; do not invent a NumPy
trajectory wrapper merely to reproduce an earlier sizing proposal. Both engines
evolve their own full states through their own methods. Use lossless bounded
compressed native records; retain every observed boundary and byte identity.
Evaluate fresh native constitutive flux on copies after simulation, preserving
the distinction from gate-first interval current.

Freeze finest-grid, reference-convergence, own-refinement, backend, restart and
invariant criteria before new scientific integration. Coarse approximation
failures are explicit retained diagnostics, not omitted cases. A priori native
roundoff allowance grows only for accumulated/conserved amounts with update count
and initial inventory; instantaneous laws and all older criteria remain fixed.
Keep every ordinary production domain, interpolant, charge and resource guard.

The user approved both stages: one registered detached capture may proceed from
reference checks to native/Cells workers only after its explicit reference gate
passes. This is not an automatic follow-up job or audit campaign. Overall cap
900 s, worker caps 180 / 240 / 360 s, aggregate artifacts 512 MiB, per-file and
decompressed-record caps 128 MiB, CPUs 0–3. No polling, retries or automatic
independent audit. Source/test/runtime identities are bound before launch.

All 157 focused software tests pass in 50.23 s (96 original / 61 new), including
saved-reference gate success/corruption and refusal to start simulators after a
failed gate. Production full-state/restart and strict own-state readouts pass
on the separately declared synthetic fixture. Earlier fixture-failure receipts
remain; no production or scientific criteria were changed for them. The
[handoff](../reports/REF004B_FEEDBACK_PILOT_HANDOFF.md) records the software
receipts and 112-input source binding before the one detached capture.

A successful capture remains pending independent saved-data closeout. No
production release, biological validation, broad BETSE parity, native restart,
GPU, organ or multiscale-accuracy qualification follows. The reference and pilot
exercise state/ownership/time interfaces useful to later multiscale execution;
shared-bath cells remain coupled, while independent worlds can later be batched.

## D096: Independently close the saved 2 ms coupled pilot without rerunning engines

2026-09-15, REF-004b. The user reviewed D095's successful 338.424-second capture
and requested the next audit. Implement the [saved-data closeout](BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md)
in a new validation directory. Preserve all 284 capture files, 112 source inputs,
earlier evidence, 352 accepted implementation files and 51 production modules.
Keep all fourteen coarse diagnostic failures and the original pending-audit receipt.

Replay frozen comparisons through redirected output sinks and independently
reconstruct their measured/expected columns, clocks, charge, full states and
checkpoints. Reuse D094's independently audited math primitives; do not import
the D095 oracle or comparator into independent modules. Stream native checks one
step at a time. Standard-library NPZ decoding avoids a NumPy/model dependency.
Check reference dense polynomials and convergence without rerunning integration.

Keep all original tolerances and separate coarse diagnostic misses from required
finest-grid accuracy. Check the refinement decisions independently, including
reference/roundoff floors. Bind software tests, runtime/source identities and
immutable capture hashes before one detached audit under 900 s / 256 MiB aggregate
/ 128 MiB per file, CPUs 0–3, with model/numerical-library imports forbidden.
No polling, retries, new simulator runs, production changes or automatic follow-up.
A pass closes only the fixed numerical pilot, not biology or broader BETSE parity.

All 122 audit-only tests pass in 11.18 s, including bounded saved-data numerical
reconstruction, checkpoint corruption, output-write protection, independent
refinement decisions and import rejection. Original 157 pilot tests remain
hash-bound, not rerun. Repository quality checks pass. The
[handoff](../reports/REF004B_FEEDBACK_AUDIT_HANDOFF.md) binds 122 source inputs and
the passing XML before the single detached audit; software tests are not its
numerical closeout receipt.

## D097: Test response-relevant hidden state before broadening channel physiology

2026-09-15, REF-004c. The user reviewed D096's actual successful independent
closeout and asked to continue. Record its [closed scope](../reports/REF004B_FEEDBACK_CLOSEOUT.md):
172.504 s, 5,806,006 independent identities with zero mismatches, all 24 complete
checkpoints and fourteen preserved coarse diagnostic misses. The old pending-
audit capture receipt, original contracts and all source evidence remain frozen.

Implement the [paired-history preparation](BETSE_CHANNEL_HISTORY_PREFLIGHT.md)
as new validation tooling, not a production model or integrator change. The
minimal next question is state sufficiency: equal initial voltage, inventories,
open fraction and current do not in general determine subsequent m/h kinetics.
Use explicit swapped gate settings in separately defined worlds, not a claim
that biological preparation produced these states. Retain zero-permeability
controls with continuing gate dynamics.

Use the actual Cells parser, full initial-state/RHS and conservative grid/resource
checks on NumPy/eager/JIT. Compare against independent audited mathematics and
test exact inactive zeros, shared-bath conservation and one-owned transfer.
In a separate pinned environment, test unmodified native Kv1p5 initialization
and one fresh gate step at each original step size; no native tissue/transport,
SIM event or new Cells integration occurs. Derivative-based curvature differences
are local mathematical witnesses, not simulated trajectories or horizon proofs.

Bind prior evidence, software receipt and source capsule before one detached
240-second / 64 MiB preparation, CPUs 0–3. No polling, automatic retry, audit,
production release, GPU work or dynamic follow-up. A pass still precedes the
separately reviewed paired continuous-reference and own-state coupled comparison.
Preserving explicit local history and stage-consistent shared-bath transfers
supports the planned multiscale/GPU boundaries without building a new framework.

All 49 focused software tests pass in 7.50 s, including actual eager/JIT initial
rates and corruption/scope guards; the earlier 44-test receipt is retained.
Repository quality checks pass. Read-only prerequisite authentication confirms
the unchanged nine-file audit / 284-file original capture. The
[handoff](../reports/REF004C_HISTORY_PREFLIGHT_HANDOFF.md) binds a 130-input
source capsule and final software receipt before one detached preparation;
software success alone does not qualify the new experiment.

## D098: Close saved initial-history evidence before paired integration

2026-09-15, REF-004c. The user requested preparation closeout, paired references
and detached coupled capture. D097's actual preparation passes all 2,442
comparisons in 14.036 s, with no warnings. Preserve its original pending-review
receipt and close it in a separate, model-free evidence layer.

The [completed review](../reports/REF004C_HISTORY_PREPARATION_CLOSEOUT.md) takes
3.062 s: all 2,442 comparisons replay exactly, 1,404 alternate rate comparisons
pass against separately audited 80-digit mathematics, and 528 complete layout
hashes match numeric arrays from already audited full checkpoints. No simulator
or reference integration is rerun. All twelve review tests pass in 0.38 s; the
four-file review and 132-input capsule authenticate unchanged.

This closes initial state, rates, layout and candidate-resource readiness only.
The derivative witness does not select a coupled time horizon or establish
biological history. Existing production and every original input, failure and
receipt remain unchanged. D099 is the separately authorized trajectory question.

## D099: Gate a paired coupled capture on integrated reference evidence

2026-09-15, REF-004c. Implement the requested steps 2 then 3 as
[one detached workflow](BETSE_CHANNEL_HISTORY_PILOT.md), with a mandatory
reference gate before either simulator. Active/blocked × initial a=(0.2, 0.6)
and b=(0.6, 0.2) preserve equal initial voltage, inventory, opening and current.
Gate settings are explicit data, not simulated biological preparation histories.

Evaluate the proposed 2 ms window using twelve fresh reference solves: base/tight
DOP853 and Radau, with the original precision, numerical budgets and domain
checks. Separately reconstruct saved dense/readout/thermodynamic evidence. Both
algorithms share the pinned SciPy library; float64 integration with an 80-digit
RHS is not arbitrary-precision integration. At the final time, require active
voltage separation of at least 100 microvolts and opening separation of 0.005
in every cell. Blocked voltage stays equal. Failure stops; no horizon expansion,
fitted setting, criterion relaxation or automatic retry.

Only a hash-bound passing gate releases 24 native runs / 4,480 updates and 16
complete Cells trajectories, with four full-state resumes. Both engines use
their existing own-state dynamics. Preserve full native boundaries, observer
partners, complete checkpoint arrays, conservation, original refinement and
single-trajectory budgets. Signed a-minus-b contrasts use twice the base budget;
cross-engine contrasts use four times it, propagating the contributing errors
prospectively. Retain every coarse diagnostic failure and reference-limited label.

Keep source-bound old implementations unchanged. New explicit per-history views
and validators must not depend on the old implicit a gate state. Derived native
fixture expectations are declared normative views, never fabricated observations.
Local gates, conservative transfer ownership and stage-consistent shared-bath
reductions use the existing modular architecture; no benchmark-only production
branch or new execution framework is introduced.

All 56 software tests pass in 22.96 s, including short real eager/JIT/restart
checks and reference-gate corruption/sequence tests; the 46-test first receipt
remains. The [handoff](../reports/REF004C_PAIRED_HISTORY_HANDOFF.md) binds a 143-input
capsule, passing XML and exact views before one new output directory. CPUs 0–3,
1,200 s total, 512 MiB aggregate / 128 MiB per file. No polling or automatic
post-capture audit/regression. A raw pass remains pending independent closeout;
no biology, GPU, organ, channel-family or native-restart qualification follows.

## D100: Independently close the saved paired-history experiment

2026-09-15, REF-004c. The user reviewed D099's [successful paired capture](../reports/REF004C_PAIRED_HISTORY_CAPTURE.md)
and requested the separate saved-data audit. The capture took 391.917 s, passed
all required reference/accounting/refinement/restart/contrast checks and retained
21 coarse misses. Its original pending-audit receipt, 291 files, 143 source inputs
and every earlier failure remain immutable; no simulator or reference integration
is rerun by this step.

Implement [D100](BETSE_CHANNEL_HISTORY_CLOSEOUT.md) as an independent evidence
layer with explicit a/b history settings, not a patch to the old implicit-a
auditor or a production change. Stream every native identity with no omitted or
duplicate comparisons. Independently reconstruct initial physical preparation,
full states, six signed contrast groups, integrated signal and eight refinement
decisions. Preserve every rejected coarse row and original numerical budget.

D099's reference checker already uses D096/D094 mathematics. Cross-check it
with the separately audited D093 vector field and D095 alternative dense/work
formulations, explicitly acknowledging that these also underlie the saved
generator. This is not a third independent integrator. Since D099 also uses
D096's checkpoint decoder, add a distinct bounded raw-byte route, linking full
state to saved histories and layouts to D098-authenticated preparation. Check
canonical checkpoint definition hashes, not pre-canonical input serialization.
Never load native pickles or imply native restart equivalence.

All **137 audit-only software checks pass in 16.56 s**. Retain the first
29-pass / 99-setup-error receipt: one canonical-versus-input checksum bug in
the new auditor, corrected without changing evidence or criteria. The 128-pass
second receipt remains. An expanded full-reference software replay reached its
55 s foreground cap; retain the timeout record and keep full reference replay
in the detached audit. Quick pipeline tests use explicit three-observation
saved-reference slices; the actual audit remains complete.

The [handoff](../reports/REF004C_PAIRED_HISTORY_AUDIT_HANDOFF.md) binds all software
attempts and a 152-input capsule before one detached audit, CPUs 0–3, 900 s /
256 MiB aggregate / 128 MiB per file. No polling, automatic retry, follow-up
regression, production release or GPU work. Actual completion, not software
success or launch, supplies any fixed 2 ms paired-history numerical qualification.
Biological preparation/memory, broad BETSE parity, multiscale reduction and organ
accuracy remain separate questions.

## D101: Test channel release through numeric inputs, not a new model

2026-09-15, REF-004d. D100's actual [paired closeout](../reports/REF004C_PAIRED_HISTORY_CLOSEOUT.md)
passes in 240.629 s, with 8,036,300 independently reconstructed comparisons,
zero mismatches and all 21 coarse failures preserved. Record the completed
scope without rewriting the pending-audit capture or its registered sources.

The user's continuation takes the next bounded [input design](BETSE_CHANNEL_RELEASE_DESIGN.md).
Existing availability schedules already separate transport from intrinsic m/h.
Use baseline/no-op/static block/suppression-release settings across both histories,
keeping original parameters, full state, other mechanisms and production unchanged.

The pinned native FULL channel path multiplies `maxDm` into transport after the
gate update. Propose absolute `baseline_maxDm * availability` as an externally
imposed adapter input. Do not confuse it with the previously qualified passive
tissue event, change arbitrary native eval expressions, reset m/h, or infer a
drug model. Actual native application must be checked before coupled execution.
Keep elapsed step-boundary input separate from the native loop's labels, hold
controls through each integration interval, and distinguish one-sided fresh
readouts from accumulated transfer. Future piecewise references must split at
input discontinuities with complete continuous state.

All **107 focused tests pass in 11.88 s**: 24 candidate grids and 54 actual
NumPy/eager/JIT instantaneous probes at six saved active states, independent
full RHS, exact blocked transport, unchanged intrinsic gate rates and preserved
nonzero history. Those saved states are not a release trajectory. Sources and
evidence authenticate unchanged; [software report](../reports/REF004D_RELEASE_DESIGN_CHECK.md).
No native dispatch, new trajectory, reference solve, checkpoint qualification,
detached job, automatic follow-up, production release or GPU work here.

Next: actual native input-application/single-update preflight, then separate
piecewise reference and response qualification. No new production abstraction
is justified by a validation-specific input bridge. Future independent worlds
may batch, while each world's shared bath still needs stage-consistent reductions.

## D102: Apply native channel inputs without resetting scientific state

2026-09-15, REF-004d. The user approved continuing from the D101 design. Implement
the [actual native preflight](BETSE_CHANNEL_RELEASE_PREFLIGHT.md) in a distinct
validation namespace; do not modify production or any registered earlier code.

Each fresh native phase is initialized from the audited a/b fixture, given one
active priming update and then the requested input prefix, without integration
between queries. Absolute `maxDm = baseline * availability` changes transport
only. Retain gates, ion inventories, cached currents and numeric layout, then
check fresh copied-state flux and one real subsequent update independently.
Thus block/release application is tested on nonzero history without claiming
that the phase has simulated to 0.5 or 1 ms. A full-loop timed input hook and the
2 ms response remain later work.

Use explicit identical per-phase initialization seeds: native code draws an
unused noise vector even with noise disabled. Keep this vector in the exact
observer comparison. Account explicitly for native unit-modulator materialization
and the electroflux `1e-25` voltage/valence additions, rather than ignoring
bookkeeping fields or weakening physical budgets. Persist partial boundaries on
failure; never replace native methods or confuse the input setter with an observer.

All **71 software tests pass in 14.01 s**, including four actual native phases /
eight updates, independent equations, observer pairs, artifact linkage,
corruptions and exception paths. Five earlier failing XML attempts and the
69-pass intermediate receipt remain. The [handoff](../reports/REF004D_RELEASE_PREFLIGHT_HANDOFF.md)
documents setup/checker corrections without altering prior evidence or criteria.

Freeze 165 inputs and launch one detached six-seed / 144-phase / 288-update /
288-application / 72-pair preflight, CPUs 0–3, 480 s total / 360 s native worker /
256 MiB aggregate / 64 MiB per file. No polling, automatic retry, audit, reference
solve or Cells trajectory follows. Actual full-panel completion and saved-data
review precede any dynamic response qualification. Biology, broad BETSE parity,
native restart, multiscale reduction and GPU remain separate gates.

## D103: Check zero-flux bath remixing as an operation, not identity

2026-09-15, REF-004d. D102's actual native worker completed all 144 phases /
288 updates / 72 observer pairs in 36.066 s without warnings. The controller
failed at 52.782 s on an exact-identity assertion. The user requested investigation
and continued work; retain the [failure](../reports/REF004D_RELEASE_PREFLIGHT_FAILURE.md).

Pinned BETSE calls the bath updater at zero ordinary or blocked-channel flux,
and that updater averages the represented bath entries. The source-defined
NumPy reduction may move a uniform vector by one ULP, including on successive
calls. Zero physical transport does not imply bitwise identity after remixing.

Implement a separate [saved-data review](BETSE_CHANNEL_RELEASE_REVIEW.md).
Replace only the incorrect outside-value identity expectations with **exact
source-order mean checks**, not an observed-error-based tolerance. Keep all
original physical budgets, full-state/input preservation and independent
gate/transport/current/charge checks. Explicitly record the signed rounding
material residual and require it to fit the original conservation allowance.
Never normalize, compensate or rewrite the captured values.

Bind the matching NumPy revision's source and license, installed implementation
and binary identities, and compare the standard-library reconstruction with the
actual binary on 198 vectors. Actual review imports no numerical library or
simulator. This is a pinned validation operation, not a new production law or
GPU reduction requirement. Other execution backends must qualify their own
reductions and physical budgets.

All **66 focused tests pass in 10.66 s**, including eight actual saved rows,
strict one-ULP corruption rejection, original-failure reproduction, source-diff
restriction, failure receipts and no-poll launch. Preserve the first 63-pass /
two-failure XML: two synthetic changes rounded away and were corrected using
`nextafter`, without changing the checker. [Handoff](../reports/REF004D_RELEASE_REVIEW_HANDOFF.md).

Authenticate all 605 original files / 165 frozen inputs, then freeze a new
175-input capsule and launch one detached full saved-data review, CPUs 0–3,
180 seconds / 64 MiB aggregate / 32 MiB per file. Keep the original failure and
each old exact-guard rejection. No simulator rerun, polling, automatic retry,
piecewise reference solve, release trajectory or GPU work follows. Actual
review completion alone may close the fixed input/single-update scope.

Outcome: the [actual D103 closeout](../reports/REF004D_RELEASE_INPUT_CLOSEOUT.md)
passes **916,176 comparisons in 24.469 s**, all 1,776 source-order means and
72 observer pairs, with zero failures. Preserve all 104 original exact-guard
rejections, all 605 capture files and unchanged physical budgets. This closes
the native input/two-single-update scope only. No simulator rerun occurred.

## D104: Establish a piecewise reference before timed simulator response

2026-09-15, REF-004d. Proceed after the user-reviewed D103 input closeout with a
[reference-only experiment](BETSE_CHANNEL_RELEASE_REFERENCE.md). Keep D101's
seven-cell shared bath, two gate histories, four conditions and fixed candidate
2 ms window. Intrinsic permeability stays positive even in the availability-zero
control. No production/API change or full-loop native/Cells trajectory is needed
for this gate.

Hold input across each integrator stage; split exactly at 0.5 and 1 ms, carry
all 28 continuous coordinates, and save left/right fresh rates. Gates evolve
through block; amounts, capacitor voltage and accumulated energy do not reset.
Use an unsplit baseline versus explicitly split no-op so numerical splitting is
itself controlled. No dense polynomial crosses an input switch.

Use the unchanged D099/D095 DOP853 base/tight and Radau settings, unit-specific
convergence budgets, independent Decimal algebra and float64 integration.
Twenty-four paths require 48 solver segments. Check analytic blocked kinetics,
exact zero transport, full carry, dense replay, thermodynamics, domains at RHS /
accepted / sampled / interior-probed states, and all solver agreements. This is
not a proof about the entire dense polynomial or arbitrary model regimes.

Freeze resolution thresholds before the seven-cell experiment: block and
post-release voltage changes ≥ 40 µV, immediate release flux ≥ 2e-4 fmol/s,
blocked gate change ≥ 4e-4, each plus reference uncertainty. These are four times
the already declared simulator budgets. Require each history and solver to pass;
record signed history contrasts without selecting a positive memory outcome.
Do not extend the window or tune tolerances after a failure.

All **102 focused tests pass in 4.35 s**, including deliberately microscopic
one-cell / 2 µs paths that fail the full signal gate as intended, independent
readouts, boundary corruption, analytic controls and detached failure/timeout
receipts. Retain the earlier 79-pass / 4.53 s receipt. The
[handoff](../reports/REF004D_RELEASE_REFERENCE_HANDOFF.md) binds software and
immutable prerequisites before one detached 900 s / 256 MiB job on CPUs 0–3.
No polling, automatic retry, post-run audit or regression. A reference pass is
pending saved review, not biological or simulator response qualification; later
native/Cells dispatch registration needs a new user instruction. GPU remains
future work, with the production stage-consistent shared-bath design unchanged.

Outcome: the [actual reference capture](../reports/REF004D_RELEASE_REFERENCE_CAPTURE.md)
passes **1,485,380 comparisons in 160.675 s**, with zero failures and all eight
signal decisions resolved. The original pending-review receipt stays unchanged.

## D105: Gate timed simulator comparison on independent saved-reference review

2026-09-16, REF-004d. The user requested both next steps. Implement one explicit
[gated job](BETSE_CHANNEL_TIMED_RELEASE.md): reconstruct every D104 numerical
comparison independently, then permit native and Cells workers only on a
hash-linked review pass. No new reference solve, horizon selection, tolerance
change or production implementation is needed.

Keep experiment inputs separate from intrinsic state and read-only observation.
Native input sets maximum diffusivity from an immutable baseline at actual
elapsed intervals, not inclusive printed loop labels. Record unchanged complete
numeric state around every input application. Fresh left/right current probes
use copied completed state; interval current retains its distinct meaning.

Preserve D103's exact source-order bath averaging. Also reconstruct the six
ordinary-flux voltage-nonce additions that precede the FULL channel boundary:
the blocked completed voltage equals the previous completed voltage, not that
intermediate nonce-shifted value. Retain direct-charge and physical budgets;
these source-specific checks do not become production/GPU requirements.

Two histories and four conditions give 48 observed/unobserved native phases,
8,960 updates, 96 input applications and 24 observer pairs. Existing data-defined
Cells schedules produce 32 eager/compiled trajectories and eight restarts at
the release boundary. Check 48 complete checkpoints / 2,592 arrays, full state
and ledgers, no-op neutrality, finest-grid contact, two-step refinement and
12 signed history-contrast groups. A positive biological memory effect is not
required; coarse misses remain explicit failures in diagnostic rows.

The [handoff](../reports/REF004D_TIMED_RELEASE_HANDOFF.md) retains bounded smoke,
corruption and controller tests, earlier software failures and the foreground
timeout. Freeze validation sources and receipts before one detached CPU job:
1,800 s total, 480 s native, 600 s Cells, 128 MiB/file and 512 MiB artifacts.
Return without polling, retry, full regression or automatic post-capture audit.
A successful capture still remains pending independent audit. Stable 0.14.0 /
accepted development 0.15.0.dev0 and future modular/GPU contracts are unchanged.

## D106: Independently audit saved timed response before closing its numerical scope

Date: 2026-09-16.

D105 completed the fixed seven-cell/two-history/four-condition experiment in
1,004.27 s: zero required failures, all refinement groups pass, 49 coarse misses
retained. Its prerequisite reference review also closed. User authorization now
covers a separate [saved-capture audit](BETSE_CHANNEL_RELEASE_CLOSEOUT.md), not
another simulation or an automatic regression campaign.

Reconstruct the 15,042,946 numeric identities using alternate mathematical
columns, validate all complete checkpoint bytes and right-continuous event clocks,
and retain both sides of each switch. Independently reconstruct exact native
source-order means, six ordinary-flux voltage nonce additions, and original
identity diagnostics. Keep the old capture, sources, budgets and status receipts
unchanged. Authenticate the closed reference review rather than repeating it;
reconstruct only the reference readouts and error floors needed for this audit.

Software checks exercise saved slices, corruption rejection, full restart/backend
and side-RHS ledgers, and detached success/failure/timeout controls. Freeze the
new capsule and reports, then launch one model-free CPU audit with durable logs
and terminal receipts: CPUs 0–3, 1,800 s, 128 MiB/file and 256 MiB aggregate disk
artifacts. Return immediately without polling, automatic retry or follow-up.

An audit pass closes only the registered fixed finest-grid/refinement numerical
scope. It does not validate biology, broad BETSE parity, native restart, large
organs, GPU performance or a multirate scheme. Production and the modular/GPU
architecture remain unchanged; select the next increment after user review.

## D107: Make BETSE-level realism explicit; separate kinetic contact from production parity

2026-09-16. The user approved the pump, junction and biological-data next tracks
and clarified that Cells should be at least as realistic as BETSE. Adopt the
[detailed-model baseline and staged plan](BETSE_REALISM_AND_NEXT_STEPS.md).
Reduced modes remain first-class configurations but cannot cap detailed fidelity.
The full B01–B17 inventory remains open until its individual evidence gates close.

D106's [timed channel audit](../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md) is
complete: 15,042,946 independent comparisons / 182 groups, zero mismatches in
387.772 s, all 49 coarse misses retained. Preserve original receipts and sources;
do not run another channel campaign merely to advance the roadmap.

Cells' synthetic reversible pump and BETSE's substrate-dependent Na/K kinetics
are distinct models. Start a separate [positive-domain source contact](BETSE_PUMP_CONTACT.md)
against the unmodified native function and an independent thermodynamic
reference. The new batched NumPy/JAX law is validation-only. A future separately
named production mechanism must connect material, charge and metabolic-energy
ports, then qualify coupled pump–leak dynamics. Do not fit the synthetic law or
reuse the distinct BITSEY nominal pump under a BETSE label.

For [junctions](BETSE_GAP_JUNCTION_PLAN.md), compare held-open conservative
transport first. Dynamic source initialization, stored-state blocking and the
possible per-moving-ion update count need an actual native lifecycle preflight;
they are not universal production/GPU semantics.

Begin [biological benchmark preparation](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) now.
Keep original versus BETSE-reported Xenopus values separate, including the
permeability discrepancy and unresolved chloride transport. Original abstract
uncertainties are not yet typed; do not invent error bars, tune held-out targets
or call a secondary-table match experimental validation.

Keep accepted production and dependencies unchanged in this slice. Freeze new
sources before a bounded detached contact capture; no automatic polling, retry,
audit, regression or follow-up. GPU/multiscale design remains a constraint on
mechanism ownership and array interfaces, not a new performance claim.

## D108: Independently close the kinetic source contact without model reruns

2026-09-16. The user approved review, integration and coupled validation.
The [independent pump audit](../reports/REF005A_PUMP_CONTACT_CLOSEOUT.md) rebuilds
all 1,240 comparison rows with a new 90-digit quotient/equilibrium expression,
checks 248 raw flux triplets, and closes in 0.163 s with zero mismatches.
An import fence excludes both simulators, numerical libraries and the old
oracle/worker/controller. All 17 software checks pass; the original 15-file
capture and its 11 source inputs remain unchanged. No broad biological,
production or whole-cell source claim follows from component closeout.

## D109: Qualify kinetic pump coupling before changing the accepted model

2026-09-16. Specify [explicit metabolic support and conservative integration](KINETIC_PUMP_INTEGRATION.md).
ATP/ADP/Pi are initially maintained reservoirs; derive their chemical drive rather
than fit the synthetic pump. Keep stoichiometry, cycle history, local/outside
amount ownership and energy accounting separate. Plan a distinct named process
and versioned finite-bath configuration; preserve the old family and checkpoints.

Implement the numerical prerequisite outside production: six short pump-only,
leak-only, combined, blocked/released and heterogeneous shared-bath cases.
Reuse the existing production GHK function and checked JAX RK4 integrator,
with an independently written scalar RHS / separate DOP853 and Radau reference
process. Candidate 100/50 µs steps must qualify on their own; no inherited 1 ms
claim. Retain complete endpoint state, input boundaries, chemical-work balance,
all owner ledgers, refinement and exact-value complete restart suffixes.

The [handoff](../reports/NUM011_KINETIC_PUMP_HANDOFF.md) records 37 passing focused
checks and earlier failed/intermediate receipts. Only invalid-state rejection
arithmetic and smoke process isolation were repaired; no physical law or
tolerance changed. One bounded detached numerical candidate is authorized;
return without polling, retry, automatic saved-data audit or regression.
Production integration/acceptance remains pending this numerical gate and review.

## D110: Close the coupled numerical prerequisite with independent saved-state accounting

2026-09-16. User-requested continuation finds D109's six-case capture passing in
21.908 s. [Independent review](../reports/NUM011_COUPLED_CLOSEOUT.md) reconstructs
all 4,070 comparisons / 30 summaries, 12 refinement records and 12 restart links,
and checks 3,756 physical records using separate 60-digit extensive-energy
arithmetic. It passes in 4.535 s without importing simulators or ODE solvers.
All 20 audit tests pass; old files, fixtures and budgets remain unchanged.

All refinement groups are roundoff-limited under the registered criterion.
Do not claim measured convergence order, a universal timestep or long-term
equilibrium from this 10 ms scope. Preserve the complete accepted 352-file /
51-module source/runtime context before any production extension.

## D111: Add the reusable kinetic process before versioned model assembly

2026-09-16. Implement `nak_atp_mass_action_positive@1` as a
[pure named process](KINETIC_PUMP_PROCESS.md), not a solver branch or a
replacement for the existing synthetic pump. Numeric parameter/result pytrees
broadcast over worlds/membranes. Explicit ATP/ADP/Pi reservoirs determine chemical
drive; signed cycles determine ionic transfer and energetic ledgers. The
composing model remains the only owner of amounts, charge-derived voltage and
history. No native code or assay-specific case table enters the process.

Separate the per-route numerical predicate from full physical stage/interior
validity. Log saturation and combined exponents improve representation without
floors/clipping. Exact blocking cannot excuse invalid metabolic pools. The first
declared numerical temperature range is 200–400 K, not biological calibration;
positive-interior gradients do not imply boundary-parameter gradient guarantees.

Thirty-two process tests and ten gate tests pass. Bind the process to all 31
saved matched-constant probes on three backends, with unchanged budgets, then
run a targeted existing-model regression in one bounded detached job. No
automatic polling/retry/review or full release campaign. A process pass is not
new-family runner acceptance.

Adding one production module changes the whole-package identity from 51 to 52
modules despite leaving every old accepted file unchanged. Preserve strict old
checkpoint source checks; do not relabel this working tree as accepted 0.15.0.dev0
or promote stable 0.14.0. Versioned schema/host/layout composition, complete
runner acceptance and appropriate regression remain the next engineering slice.

## D112: Prepare versioned integration without changing a running qualification

2026-09-16. The user approved all next integration work. The user-requested
inspection finds all 930 process-contact comparisons passing without warnings,
while the targeted 348-test regression remains active. Preserve its frozen
source set and no-poll policy; do not change production underneath that job.

Prepare a separate [kinetic finite-bath integration design](KINETIC_FINITE_BATH_MODEL.md).
Use `finite_extracellular@2` with distinct immutable host specifications and
numeric layout, preserving v1's schema/fingerprints and synthetic pump. Canonical
capacity is extensive fmol cycles/s; explicit maintained ATP/ADP/Pi support
determines the chemical drive. No duplicated authority for density/area or drive.

Reuse the existing physical/history state ownership and introduce only the
required parameter layout. The composing model selects the process, not RK4;
no monkeypatch or subtraction of an already evaluated synthetic pump. Add
conservative whole-Hermite-interval bounds for log-concentration/voltage-dependent
pump affinity, distinguishing failed certification from proven domain violation.

Ordinary runner, restart/branch, events, padding, batch/window and resource tests
remain required beyond the six-case numerical candidate. This decision records
the implementation route, not implemented v2 support or a completed regression.

## D113: Versioned kinetic finite-bath composition on the ordinary engine

2026-09-16. On user-requested continuation, D111's terminal qualification is
reviewed: 930 process comparisons and 348 targeted regression tests pass. All
361 registered sources/payloads authenticate. Archive and byte-verify 1,273
working-context files before production changes; retain strict historical source
guards rather than relaxing them to fit the new tree.

Implement D112 as `finite_extracellular@2` in **0.16.0.dev0**. Distinct immutable
host types and a flat layout hold explicit kinetic/metabolic parameters; the
existing ten evolving fields retain amount/history ownership. Resolve +1 Na/K
roles once, keep extensive capacity canonical, and derive maintained chemical
drive from pools. No implicit v1 migration or dynamic metabolic-pool schedule.

Share only narrow geometry, passive, ownership, accounting and observation
helpers. Each composing model explicitly supplies its own readouts/RHS/domain;
the integrator is unchanged. v1 keeps its schema, identity and synthetic law.
A separate process using the preserved pre-edit source verifies exact old
fingerprints, layouts, initial states and complete derivatives for fourteen cases.

Use the kinetic process's stage predicate and conservative cubic-interior
enclosures. In addition to existing floating extrema checks, outward-rounded
Bernstein hulls enclose amount polynomials without uncertain derivative roots.
Log and expression-rounding allowances are explicit CPU/libm assumptions, not
a formal transcendental proof. A too-wide bound means unable to certify, not
proof of an unsafe trajectory. Test both distinctions with high-precision
arithmetic. Keep the initial 100 µs ceiling separate from general accuracy.

Sixty focused software checks and eight controller checks pass. Freeze and
launch one **74 new-family + 348 regression** detached attempt, preserving full
10 ms trajectories, comparisons against both already-saved independent solvers,
twelve restart suffixes and ordinary lifecycle evidence. No new native/reference
solver, no polling, no automatic follow-up. Full acceptance, release promotion,
experimental plausibility, GPU, resolved spatial pump composition and interacting
organs remain unclaimed until their own evidence exists.

## D114: Close the bounded kinetic family using independent saved-number accounting

2026-09-16. Review the completed D113 attempt on user-requested continuation.
All 74 family and 348 targeted regression tests pass in 418.438 s. Authenticate
601 captured inputs, 55 production modules and all 292 result files before
adding review files; leave those captured bytes unchanged.

Use a new stdlib-only numeric artifact decoder and 60-digit Decimal physical
accounting, with explicit simulator/reference-import fencing. In 3.601 s it
reconstructs 3,256 reference comparisons, 1,944 physical records, twelve exact
restart suffixes and 36 complete checkpoint links. Twenty-four audit checks
pass. See the [closeout](../reports/SPEC010_FAMILY_CLOSEOUT.md) for identities,
budgets and exact evidence scope. No tolerance change or solver rerun.

Close only this bounded development-family scope. Do not equate 422 targeted
tests with the historical 4,190-test multi-context release matrix; keep stable
0.14.0 and accepted 0.15.0.dev0 preserved. Future broad regression planning
must explicitly route current functional tests and archived identity suites.
New audit files may extend the directory without rewriting historical
source inventories or weakening original guards.

## D115: Observe native pump–leak ownership before comparing coupled trajectories

2026-09-16. Prepare one [bounded native lifecycle capture](BETSE_PUMP_LOOP_PREFLIGHT.md)
on the pinned BETSE FULL INIT driver, separate from production and from later
Cells/BETSE trajectory qualification. Reuse established read-only lifecycle
observation; add direct-loop pump/passive argument/return copies. The declared
once-only setup intervention is separate and identical in both observation modes.

BETSE's third pump return is outward sodium density before driver density and
boundary-mask changes, not ATP consumption. Derive signed cycles from applied
-3/+2 transfers. Preserve native face geometry, actual chemistry, immutable-ion
charge, effective finite-bath ownership, raw sample labels and actual elapsed
updates. Do not adopt source quirks as production biology or integrator rules.

Six controls × observed/unobserved = twelve native runs, eight 25 µs updates
each, with 48 recorded steps. Twenty-nine software checks pass, including real
native configuration loading, before launch. Use CPU 0–3, one BLAS thread,
240 s worker / 300 s total, 64 MiB/file / 256 MiB artifact bounds. Detach and
return without polling, retry or automatic audit/regression. A producer pass
still needs user-requested independent review; no native coupled parity,
equilibration, biology, spatial-pump or GPU claim follows from this preparation.

## D116: Independently close native pump lifecycle from saved live-call evidence

2026-09-16. On user-requested continuation, authenticate the completed twelve-run
D115 capture and reconstruct its evidence using a new stdlib-only, 70-digit
Decimal reviewer. All 613 prior sources, 55 production modules and 73 result
files remain unchanged. Twenty-six reviewer checks pass before the bounded audit.

The independent reconstruction closes 73,188 numerical comparisons, 150 physical
records, 48 observed updates and six exact observer pairs in 1.877 s. It covers
raw pump/passive laws, applied density/masks, concentration ownership, shared
bath, charge/voltage, whole-cell current and stored elapsed-time history links.
Separate source nonce behavior and the sodium-rate diagnostic from actual
physical transfers. Account explicitly for 24 known disabled-cut notices.

Native pickles are hashed, not executed; unexported face-smoothing weights are
not independently reproduced. No trajectory, energy-convergence, biology,
restart or GPU qualification follows from this lifecycle result. Preserve the
original producer capsule and add a [separate closeout](../reports/REF005B_PUMP_LOOP_CLOSEOUT.md).

## D117: Match measured pump preparation through public configuration before refinement

2026-09-16. The user authorizes continuing the reviewed next work. Prepare one
[gated matched pilot](BETSE_MATCHED_PUMP_PILOT.md), with no production/upstream
changes. Translate actual per-cell geometry, immutable-ion charge, finite-bath
ownership and maintained metabolic parameters into `finite_extracellular@2`.
Do not idealize tiny initial voltage or repair chemistry for neutrality.

Closed-boundary masks reduce effective transport area, not membrane capacitance.
Reject within-cell membrane heterogeneity rather than hiding it in an average.
First compare all 48 saved interval-start states on three array backends and
prescribed single transfers; that mapping is not an alternative integrator or
trajectory assimilation. Retain the native raw clock and actual elapsed clock.

Then qualify an independent float64 DOP853 base/tight and Radau reference, before
one 1 ms six-control campaign: 36 native runs / 18 observer pairs, 24 ordinary
Cells trajectories and six complete exact restart suffixes. Register separate
native/Cells timestep ladders, numerical budgets, conservation/energy checks,
and floor-aware error contraction before any campaign output. Save coarse
results and failed gates; never fit or loosen criteria to obtain agreement.

Thirty-seven short software checks pass, including a real compiled two-step
runner/checkpoint smoke. Freeze 629 inputs and the receipt, then launch detached:
CPUs 0–3, one BLAS thread, 1,080 s total, 64 MiB/file / 512 MiB disk artifacts.
Return without polling, automatic audit, retry or follow-up regression. Producer
success remains pending independent review; longer relaxation/experimental
perturbations, junctions, spatial composition, release and GPU gates stay separate.

## D118: Diagnose native finite-step energy error without repairing away rejection

2026-09-16. On user-requested continuation, independently diagnose the failed
D117 pilot from saved records. Its simulations completed, but the final
fail-fast comparator stopped after 385.829 s at native finest-step energy.
Preserve all 629 source inputs, the original protocol/failure and all 431 result
files. Seal the failed payload at review time; do not invent an original
successful completion manifest.

A new stdlib-only diagnosis reconstructs native energy with 70-digit arithmetic
from total applied ion transfer and potassium-derived pump cycles. It evaluates
all registered trajectory/reference/accounting summary limits rather than stopping
at the first miss. Exactly six of 203,274 comparisons fail: two finest native
dissipation coordinates and four total energy-balance limits. All 376,320
additional flux/transfer comparisons and 36 refinement groups pass. Decode
actual Cells NPZ records and verify all six complete full-state restart suffixes
and midpoint checkpoint links; no simulator/reference solver imports or reruns.
Thirty-three diagnosis software checks pass. [Report and limits](../reports/REF005C_PILOT_FAILURE_DIAGNOSIS.md).

The native energy error halves with timestep. Independently computed convex
chemical/capacitive Taylor remainders explain the dominant balance defect.
Do not subtract those terms to relabel the original dissipation as accepted,
loosen scientific budgets, fit parameters or modify production for this miss.
The matching quantities and energy accounting remain visible separately from
the native integrator's first-order error.

Recommend a separately registered 6.25 / 3.125 / 1.5625 µs native ladder, with
an exact overlap control and reuse of source-bound Cells/reference evidence.
Revisit artifact/time limits explicitly before execution; the finer raw trace
will exceed the old per-file cap. Extrapolated success is not qualification.
This diagnosis launches no replacement capture, regression or automatic review.
Longer relaxation, biology, multiscale and GPU gates remain separate.

## D119: Refine the comparator run without teaching Cells a discretization error

2026-09-16. The user authorizes the next capture and explicitly emphasizes not
replicating errors in Cells. Keep Cells' checked RK4, stage/interpolation domains,
conservative composition and energy accounting unchanged. The diagnosed native
first-order remainder is a finite-step limitation, not by itself evidence of a
biological-law or implementation bug. It is not a new target for Cells to fit.

Register a separate [native refinement amendment](BETSE_PUMP_REFINEMENT.md):
6.25 / 3.125 / 1.5625 µs, all six controls and 1 ms duration, with exactly the
original scientific criteria. Require all twelve repeated 6.25 µs records to
match the old capture, including signed zero. Reuse the 213 byte-verified saved
Cells/reference/mapping files; no new production or adaptive-reference solver
runs, physical-parameter changes, energy correction or tolerance relaxation.

Call the frozen native producer with the new registered timetable/resources;
do not replace its physics or modify its source. Preserve the original failed
attempt and its independent diagnosis. Numerical reporting now retains all miss
counts/groups, up to 64 concrete examples and per-row traces/accounting, rather
than stopping at the first numerical miss. Structural/domain failures still
stop. A saved-data replay reproduces all six original failures, not a new pass.

Forty-six software checks pass in 36.82 s, including all eighteen actual refined
native configuration loads and exact single-dispatch worker checks. Freeze 641
source/configuration/contract inputs and the receipt. Raise recording limits
explicitly to 256 MiB/file and 2 GiB checked artifacts, requiring 3 GiB free at
launch. Retain raw traces; no unverified chunking/reduction is introduced.

One detached campaign: CPUs 0–3, one BLAS thread, 90 s reuse / 900 s native /
180 s comparison / 1,260 s total. Return without polling, retry, regression or
automatic follow-up audit. A producer pass remains pending independent review.
Persistent discrepancies require investigation, not fitting away; biological,
organ, GPU and general BETSE-parity claims remain separate.

## D120: Review the refined pump pilot independently, without replaying a solver

2026-09-16. On user-requested status, D119 has finished in 501.812 s and reports
616,806 comparisons with zero failures, all eighteen observer pairs and twelve
exact overlap records. Its main energy-balance defect is about 7.351e-8 pJ,
below the unchanged 1e-7 pJ criterion. Keep the original six-miss attempt rejected;
the new producer pass is not itself independent acceptance.

On the user's continuation, prepare a [separate saved-data review](../reports/REF005C_AUDIT_HANDOFF.md).
Authenticate all 641 captured inputs, 55 production modules, 444 sealed payloads,
the original failure and prior independent receipts. Preserve source identities
and all 213 reused file hashes; decode the original Cells/checkpoint artifacts
and require their copied counterparts to remain identical.

Use stdlib-only readers and independently tested 70-digit arithmetic, with
Cells, BETSE, numerical runtimes, reference integration and producer checkers
excluded by an import fence. Reconstruct live flux laws, every native transfer,
conservation, electrical state, energy and clocks across 6,720 updates; check
the reconstructed coordinates against the saved producer output. Re-evaluate
trajectory/reference/backend/refinement gates and exact observation/restart
links. Convex energy remainders remain diagnostic, never acceptance corrections.
The step-count-dependent material allowance remains exactly the original policy,
not a new rate or trajectory tolerance. This review reconstructs native energy;
Cells diagnostics retain their separate D114 accounting provenance.

Forty-seven preflight checks pass in 30.06 s, including a full real 640-step
record, all six short controls, corrupt-evidence refusals and complete saved
Cells restart/checkpoint links. Register the review code and its dependencies,
test receipt, handoff and exact capture inventory. Run once detached on CPUs
0–3, bounded to 900 s, 32 MiB/file and 128 MiB review artifacts. Preserve partial
rows/logs and terminal completion or failure; no polling, simulator reruns,
production change, automatic retry, regression or follow-up campaign.

Only a passing independent terminal receipt may close the registered six-control
1 ms CPU pilot. Longer relaxation, full pump/transporter support, biological
plausibility, release promotion and GPU qualification remain separate gates.

## D121: Close the bounded refined pump–leak pilot and preserve its rejection history

2026-09-17. The user-requested status check finds D120's independent review
completed on 2026-09-16 in 337.048 s, with **203,274 acceptance comparisons /
zero failures** and **10,610,676 additional law, transfer, conservation and
evidence-link checks**. All 6,720 observed updates, 20,178 physical records,
36 refinement groups, eighteen observer pairs, twelve exact overlap records,
and six complete Cells restart/checkpoint links pass. Twenty-three refinement
groups are floor-limited; no convergence order is claimed for those groups.

The [formal closeout](../reports/REF005C_PUMP_PILOT_CLOSEOUT.md) records immutable
capture/audit identities, precise numerical scope and limitations. All 641
capture inputs, 55 production modules, 444 capture payloads, eleven audit inputs
and 22 audit payloads authenticate. The original failed 431-file packet and
six energy misses stay rejected. The independent finest pump+leak energy defect
is 7.351e-8 pJ against the unchanged 1e-7 pJ limit. Neither a convex-remainder
correction nor a change to Cells is needed to pass the refined pilot.

This closes only the registered six-control, seven-cell, matched-constant
**1 ms CPU** correspondence scope. Native energy reconstruction, saved Cells
diagnostics and their separate D114 accounting review retain distinct provenance.
Native restart, full BETSE feature parity, biology, release promotion and GPU
remain unqualified. Document closure by adding a new report; never rewrite old
producer receipts or launch handoffs. This closeout reruns no simulator or audit.

## D122: Qualify recording before longer relaxation and recovery

2026-09-17. The [longer-duration design](BETSE_PUMP_RELAXATION_PLAN.md) separates
numerical extension, physical steady-state/recovery and experimental validation.
Its machine-readable proposal is non-runnable and has no unmeasured runtime or
aggregate artifact budget. **35 design/evidence checks pass / 7.25 s**. A saved-
data planning receipt binds the closed evidence, matrix counts, exact inherited
scientific criteria and explicitly labeled resource extrapolations.

The present 1 ms packet uses 1.47 GiB and a 136.55 MiB largest record. A naive
10 ms extrapolation reaches 14.74 GiB and a 1.33 GiB file, exceeding the old
caps. These are legacy observation/audit workloads, not future Cells or GPU
benchmarks. Chunking bounds files/buffers, not aggregate storage. Require
lossless numeric recording, static metadata deduplication, measured buffers/RSS,
failure-safe hashes/indexes and independent decoder checks. Preserve every raw
call, physical boundary and clock needed by the scientific review.

First qualify an offline codec against all preserved records, then a separately
registered same-1 ms live observed/unobserved replay. Do not modify frozen
producers or silently disable native storage. Match Cells' existing windowed
execution and complete restart behavior on the actual seven-cell fixture;
recording changes must not reset physical/history state or skip interval checks.

Next propose a distinct 10 ms six-control extension: 36 native / 24 Cells /
18 reference trajectories, six midpoint restarts and 41 shared observations.
The candidate steps and all scientific limits are explicit, not prequalified
at the longer horizon. Preserve the physical first-millisecond prefix while
recognizing that changing BETSE's horizon changes its raw sample labels.
Failure calls for diagnosis and explicit registration, never tolerance inflation
or automatic timestep retries.

Only after reference/domain qualification select residuals and stable windows
for longer relaxation, then separately specify pump suppression/release and
its native input lifecycle. A flat voltage or the both-blocked control is not
physiological equilibrium; sustained pump/leak flux and dissipation need not
vanish at a driven steady state. Reservoir changes require explicit accounting.
Original-data preparation can proceed alongside this engineering, without
turning initialized concentrations or simulator outputs into held-out targets.

No production edit, new solver, long simulation, audit rerun, biological fit or
GPU job is launched. Model fidelity, solver, recording policy, window size and
device remain independent choices; windowing is not multirate integration.

## D123: Separate lossless recording from native physics and qualify saved data first

2026-09-17. Implement [a new adapter-side record stream](../validation/betse/native_recording/README.md)
without editing production or any frozen producer. Use explicit little-endian
float64/int64 types, bounded compressed chunks, a streaming hash-linked index
and manifest-last publication. Preserve all nested fields, numeric types and
signed zero. Unknown schema fields, incomplete calls, wrong order/clocks,
corruption and missing terminal evidence are errors, not data to discard.

Initial/static metadata comes first; final arrays, hook closure and history
hashes come last. A future live observer must not need the endpoint to start
writing. The current adapter is an offline partition/verification path; it does
not yet replace the native accumulating observer or BETSE's own histories.

**132 checks pass in 3.51 s**, including every saved short control/mode and
allocation checks with cyclic GC disabled. The final source-bound resource
probe reconstructs the largest 143,185,735-byte row exactly from 1,549,225 bytes
(92.424× smaller), with a 1,087,999-byte largest encoded chunk. Full load/write/
decode/canonical comparison takes 38.519 s and peaks at 504.82 MiB process RSS.
The offline importer and whole-row compatibility decoder intentionally retain
complete trees. Never describe an 8 MiB encoded-chunk cap as 8 MiB process RAM,
or evidence compression as simulator/GPU acceleration.

Register one detached conversion of all 36 saved D119 rows / 6,720 observed
updates / 20,196 stream records. Freeze inputs, source capsule, passing tests,
probe and recording contract. Require whole-row canonical equality, all array
byte checksums, structural completeness and unchanged prior source/evidence
identities. CPUs 0–3; 900 s; 4 GiB address space; 16 MiB/file; 32 MiB/stream;
512 MiB total; 1 GiB free-space reserve. Reserve the next stream's full allowance
before starting it and enforce quotas before payload writes. No polling,
automatic retry, follow-up audit/regression or native simulation.

Offline success is pending separate review, not R0 closure. Live same-1 ms
observer parity and actual matched Cells window/restart checks precede a new
10 ms reference/resource scope. No tolerance change, loss of cumulative
accounting, upstream-error mimicry, biological fit or GPU claim is permitted.

## D124: Independently decode and compare every preserved native value

2026-09-17. The full D123 offline conversion finishes in 215.987 s with all
36 rows reconstructed exactly: 1,509,951,698 bytes of native JSON become
18,070,684 bytes of streams, an 83.558× reduction. All 778 sealed payloads,
fourteen captured inputs and prior numerical evidence authenticate. Source-
bound converter metrics are not independent closure or live-memory evidence.

Add a [separately implemented read-only decoder and reviewer](../validation/betse/native_recording_audit/README.md).
Forbid imports of the producer's codec, partitioner, compatibility reconstruction
and job, alongside simulator/array frameworks. Use a cursor parser and standard-
library vectors; compare values directly to the original JSON with exact type
and float64-bit equality, including negative zero. Recompute every history and
endpoint array byte digest, all stream integrity/extent/sequence metrics, and
coverage of every original primitive. A saved producer digest is provenance,
not a substitute for independent decoding and comparison.

**133 preflight checks pass in 52.34 s**, including handwritten wire fixtures,
corruption after outer-hash resealing, omitted/extra fields, signed-zero/type
changes, cyclic-GC-disabled reader release, all twelve actual coarse controls
and the complete finest 640-update pump+leak row. Array-digest and terminal
matrix/controller failures are separately exercised. The original legacy row
is materialized one at a time; do not claim the whole review uses only a chunk
of RAM. No model, reference solver or physical-law evaluator is rerun.

Register one detached full review, source-bound to the exact completed codec
packet, software receipt and new code/contract capsule. CPUs 0–3, 600 s, 4 GiB
address space, 4 MiB per output file, 32 MiB total and 1 GiB free-space reserve.
Pass the registration digest to the worker. Preserve partial results and
failure evidence; never poll, retry or launch another job automatically.

A passing review may close only the offline codec sub-gate. Preserve every old
source/receipt and the original failed numerical attempt. Live observer
neutrality and storage ownership, matched Cells window/restart behavior, longer
reference/domain scoping, biological validation, release and GPU/organ scaling
retain their separate gates. No old threshold or physical model changes here.

## D125: Stream live native evidence and qualify public Cells windows without changing physics

2026-09-17. D124 independently passes all 36 offline rows, with **54,685,116
exact scalar comparisons / zero failures in 191.565 s**. Record the
[offline closeout](../reports/REF005D_CODEC_CLOSEOUT.md), retaining frozen
producers, reviewers, original failure and accepted numerical evidence unchanged.

Add a [separate live adapter](../validation/betse/live_recording/README.md),
retaining one pending physical update/raw-call group and emitting lossless
records at actual update/storage boundaries. Match exact source/instance
boundaries through upstream type-check wrappers; count only direct toolbox
pump/passive calls. Copy native scalar subclasses using legacy JSON semantics,
without rounding or weakening the strict codec. Failure must not publish a
completed stream. Recompute complete history hashes from native retained samples
without making a second full JSON trajectory.

Do not modify native history retention, the native time schedule or pickle
creation under the name of read-only observation. Measure those retained numeric
payloads and current/high-water process RSS separately from encoded chunks.
The schema's quiet mode now has a storage-only hook; explicitly compare it to
the accepted truly quiet baseline and to all common fields of the full-observer
partner. Do not describe it as a new hook-free native run.

Qualify the same **1 ms / six controls / three native grids / both modes**,
with exact all-record overlap. On Cells, reuse the **public ordinary checked
RK4 full/window/disk/checkpoint APIs**, not a special test integrator. Compare
24 accepted baselines, 72 window runs at widths 1/7/64, eighteen full/observations/
checkpoints disk outputs, six complete loaded full/window restart suffixes,
six zero-length continuations and two sparse observation schedules. Diagnostic
maxima and all cumulative state/layout/clock fields remain checked independent
of what is recorded.

The [new registration](../reports/REF005D_LIVE_HANDOFF.md) binds sources,
receipts and prior packets, with CPUs 0–3, 1,800 s total, 900/750 s native/Cells,
32 MiB per file, 512 MiB aggregate, 1 GiB disk reserve and 8/16 GiB worker
address-space caps. These are safety caps, not RSS targets or an ETA. Detach
once, preserve failures, never poll/retry/launch follow-up automatically.

Producer success remains pending separate independent live review. No longer
horizon, biological acceptance, release, GPU result, tolerance change or
production edit is implied. BETSE's internal memory ownership remains explicit
future work, not silently solved by streaming observer output.

## D126: Close preflight and execute the unchanged full live/window matrix

2026-09-17. The detached D125 preflight passes **79 tests / 54.27 s**, with
**77.511 s** overall including source/evidence authentication. Verify all 235
sealed payloads, 239 regular files, 26 internal pytest aliases, 668 frozen inputs,
the capsule and the exact passing receipt. Record the result and the user's
separate execution authorization in the [launch/closeout report](../reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md).
Preserve the earlier smoke timeout and other preflight failures unchanged.

Run the already captured `live_job.py` with that passing receipt and fresh
output. Do not alter its implementation, source manifest, D125 registration
schema, physics, timestep, duration, scientific thresholds or resource bounds
to move from preflight to the full matrix. The same 1 ms fixture now targets
36 native runs/eighteen observer pairs plus 24 Cells baselines, 72 window paths,
eighteen disk-policy outputs and complete restart/zero-length/sparse controls.

Retain the existing 1,800 s overall, 900/750 s phase, 32 MiB/file, 512 MiB
aggregate and 8/16 GiB address-space limits, CPUs 0–3 and 1 GiB disk reserve.
Launch detached once, return control, and leave polling to the user. A successful
producer result remains pending separately authorized independent review; no
automatic audit, broader regression, 10 ms run or GPU execution follows it.
Native retained histories are still not constant-memory. This is execution of
the prepared gate, not a new feature or numerical acceptance claim at launch.

## D127: Correct invocation-aware notice classification and reuse authenticated native work

2026-09-17. D126 stops after 577.531 s at a controller-only logging check,
after all 36 native exact overlaps and eighteen pairs report success. BETSE's
terminal prefix is derived from the invocation: the smoke used `python -c`
(`[betse]`), the actual worker used a file (`[live_job.py]`). All 72 messages
are otherwise exact. Cells has not run. Preserve the original failure and the
entire tested/frozen implementation; do not change physics or tolerances.

Use a [separate continuation](../reports/REF005D_LIVE_CONTINUATION_HANDOFF.md),
not an edit to executed code or an in-place retry. Match only the registered
script prefix and the exact notice body/count. Authenticate fixed original
registration/failure/result/log identities, 668 old sources/capsule, passing
software and prerequisites, all 964 saved files and every comparison/capture/
manifest/index/chunk link. Bind that complete inventory in the new registration
and recheck before/after execution. Carry forward producer comparisons without
rerunning native simulations or claiming a new independent review.

Fifty-four regression checks pass, including actual script-launched upstream
formatting, saved notice regression, corruption/coverage/source refusals,
Cells-only dispatch, terminal failure and worker-group cleanup. The source-bound
receipt covers 674 inputs. Invoke only the unchanged D125 Cells worker through
ordinary public APIs: 24 baselines, 72 windows, eighteen disk outputs, six full
and six windowed loaded restart suffixes, six zero-length and two sparse controls.
Require empty Cells stderr. No special solver or adjusted numerical threshold.

Keep original CPU, Cells deadline, address-space, per-file/disk and overall
limits. Detach once; no polling, automatic retry, audit or longer run. The
original attempt stays failed. The new packet may establish producer completion,
but independent live review, duration extension, biology, GPU and whole-native
memory remain separate gates. See the [launch record](../reports/REF005D_LIVE_CONTINUATION_LAUNCH.md).

## D128: Separate output ownership and qualify the actual campaign worker before its matrix

2026-09-17. D127 stops after 79.799 s: native reuse passes and one Cells case
completes, then the harness assigns both ordinary baseline and full recording
to `full/`. Production correctly refuses to overwrite it. The earlier smoke
used individual APIs in a different layout and missed the combined-worker
collision. Preserve both failed attempts and their tested/frozen source contexts.

Use a [separate output-layout adapter](../reports/REF005D_OUTPUT_LAYOUT_HANDOFF.md),
with distinct `baseline/`, `recordings/<policy>/` and `resumed/` leaves. Validate
all case destinations before computing, keep non-overwrite/link/path checks,
and recheck baseline hashes after recording. Import frozen numerical checkers;
retain all prior specification, integration, state/readout, diagnostic, disk,
checkpoint/restart, zero-length and sparse-observation comparisons. A source
regression compares numerical branches with only output expressions normalized.
No production code, native source, physics or scientific thresholds change.

Fifty-one fast harness tests pass. They explicitly stub physics while exercising
the actual worker's filesystem sequence, original collision, mutation/coverage
refusals, source binding and probe gates. Do not present these as numerical
validation. Preserve the first test-fixture failure; isolating its phase directory
does not justify weakening the job-wide symlink guard.

Preregister one detached job with an actual one-case probe followed by the
original matrix. Both use precisely the same worker. The pump+leak 25 µs/1 ms
probe must write baseline and all disk policies and pass full/windowed loaded
restart and zero-length checks. Seal its complete packet; controller and matrix
worker both authenticate it before matrix execution. A failed/tampered probe
stops the job. This is an internal gate, not an automatic follow-up campaign.
Probe cases do not replace any of the 24 matrix cases. Do not reuse/promote the
partial Cells packet; carry forward only the hash-authenticated native evidence.

Keep 750 s matrix / 1,800 s overall and existing CPU/memory/disk bounds. Add a
120 s probe sub-bound within that overall cap and apply the artifact quota to
both phases together. Detach once, no polling/retry/later audit or regression.
Actual probe and producer completion remain pending at launch, followed by a
separately authorized independent review. Longer duration, biology, GPU and
whole-native-memory qualification retain separate gates.
[Launch record](../reports/REF005D_OUTPUT_LAYOUT_LAUNCH.md).

## D129: Independently review saved live output and distinguish receipt-only evidence

2026-09-17. D128 completes its actual shared-worker probe and full matrix in
553.910 s; producer acceptance is not independent closure. The user authorizes
the next review. Preserve all D128 inputs and both earlier failed attempts;
do not rerun either simulator or change production, physics or tolerances.

Use a [separate standard-library reviewer](../reports/REF005D_LIVE_AUDIT_HANDOFF.md).
Reuse the qualified independent D124 native decoder against every original JSON
value in all 36 live streams, then all eighteen observed/quiet pairs. Independently
decode and bit-compare Cells baselines, saved restart suffixes, recording chunks
and complete checkpoints against accepted D119 arrays. Check clock/cursor,
file/field coverage, chunk ownership, observation boundaries and diagnostic
reductions, not only successful producer status or outer hashes.

D128 did not save every in-memory window trajectory. Reconstruct their expected
rolling array-receipt hashes from accepted baselines, including state/layout and
boundary readouts. Explicitly label these as receipt checks; do not imply direct
inspection of unsaved trajectories. Zero-length diagnostic maxima receive bound/
schema checks, not fresh physical-law evaluation. Reported memory reservations
and native observer counters are not independent peak-process measurements.

The source-bound software gate includes saved real cases and corruption/resealing
tests. Test a uniquely named controller to avoid older audit modules on helper
import paths. Preserve failed preflight packets. Known internal software-test
aliases may resolve to registered regular files or directories; exact alias
membership remains mandatory, and normal evidence paths never permit links.

After that gate, launch one detached 900 s / 4 GiB / 8 MiB-per-file / 64 MiB
review, CPUs 0–3 with 1 GiB disk reserve. Authenticate source/capture identities
before and after; produce durable completion/failure evidence. No polling,
automatic retry or next campaign. **97 source-bound preflight checks pass**;
the [launch record](../reports/REF005D_LIVE_AUDIT_LAUNCH.md) records acknowledgment,
not a full independent verdict. Longer integration, native memory, biological
validation and GPU execution remain distinct future gates.

## D130: Close recording and scope the longer reference before native execution

2026-09-17. D129's independent review passes in 128.769 s with zero failures.
Record a [separate R0 closeout](../reports/REF005D_LIVE_CLOSEOUT.md) and authenticate
all 66 review payloads, 21 source inputs and the accepted/failure-preserving
prerequisite chain. Preserve the distinction between directly decoded saved
arrays and independently reconstructed receipts for unsaved windows. Neither
old status fields nor frozen sources are rewritten.

The user authorizes proceeding toward longer physiology, junction communication
and biological readiness. The next numerical execution is a bounded
[R1-S0 reference/domain study](../reports/REF005E_REFERENCE_SCOPE_HANDOFF.md):
six original seven-cell finite-bath cases, 10 ms, DOP853 base/tight and Radau,
unchanged equations and settings. Retain the 30,000 RHS-call/4,096-step per-solve
caps and all scientific tolerances. Check complete saved-sample/accepted-endpoint
domains, accounting, three-solver agreement and 161-sample overlap with the old
reference. Report terminal net ion and voltage rates without equilibrium criteria.
Do not claim continuous domain enclosure between sampled states.

Source-bound software tests precede a detached 300 s worker / 600 s controller /
4 GiB / 8 MiB per file / 128 MiB total / CPUs 0–3 run. Only the reference equations
integrate: no native BETSE, Cells or JAX execution, no native ladder promotion,
and no full 10 ms campaign. Success still needs separate review and measured
native timestep/resource scoping. The native finest energy limit remains 1e-7 pJ.

The final source-bound gate passes **73 checks / 17.83 s**, including two real
10 ms reference smokes. Formal R0 closeout completes at **18:25:18 UTC**;
the reference-only study [launches detached at 18:25:49 UTC](../reports/REF005E_REFERENCE_SCOPE_LAUNCH.md).
This is a launch acknowledgment, not a full-study verdict. Preserve the first
60-pass/two-failure software packet and subsequent 63-pass packet; the fix was
JSON-boundary scalar normalization in the new wrapper, not changed equations or
numerical limits. No worker polling or automatic follow-up.

The [readiness snapshot](BETSE_NEXT_GATES.md) does not infer active junction
evidence from a seven-cell pump preparation: the saved reciprocal-neighbour map
is missing. J0 must record native topology before selecting edges or dynamic
gate semantics. The existing biological candidate remains non-runnable until
original methods, uncertainty and input/held-out roles are resolved; no new
literature review or fitted parameters are claimed here. No automatic polling,
retry or follow-up campaign; GPU/multiscale organs remain separate gates.

## D131: BETSE is an external reference; test parity with Cells' own physics

2026-11-08. From 30 October the work re-hosted and transcribed BETSE inside
`src/cells`, and its end-to-end demonstration compared BETSE with BETSE. That
track is frozen (tag `native-betse-frozen-2026-11-08`) and is being removed from
the engine. BETSE now runs unmodified and out of process, and Cells is compared
against its saved outputs (`AGENTS.md`, "BETSE's role"). The user also directed
that no BETSE-specific code remains in the engine.

For BETSE's default world (225 cells, 600 extracellular nodes, 1,291 membrane
patches), the user chose the physical route. Cells' resolved-tissue family is
scaled beyond its 256-node bound with a prefactorized field, and a new identity
adds the Na/K pump and a physical-time junction gate (estimated 4.5–5.5 days).
The alternative, renaming the BETSE-order kernel (3.5–4 days), would have kept
BETSE's numerics under a Cells name. That kernel moves to `validation/betse` as
an emulator that attributes differences. Deliberate differences measured on a
probe seed: CODATA constants 1.2 µV in Vmem; converged time stepping versus
BETSE's 10 ms Euler about 52 µV transiently in INIT; the others below 1 µV
([coverage map](/mnt/workspaces/Cells/cells-betse-default-coverage-20261108-01/coverage.json)).

## D132: Stage B — neutral engine names; BETSE-loop tooling leaves the engine

2026-11-09. Follows D131 and the user's direction that no BETSE-specific code
remains in `src/cells`. From the reviewed plan in
`/mnt/workspaces/Cells/stage-b-plan-20261108-01/plan.json`:

- **Physiology stack:** 64 modules (19K lines) that arrange Cells components in
  BETSE's loop order, with BETSE phase labels and random-number replay. It
  moves to `validation/betse/` with its tests, at the user's choice. Its two
  tissue-profile importers are decoupled.
- **Renames:** generic physics keeps its equations under neutral names and
  cites its source (e.g. the channel catalog's BETSE v1.5.0 library
  parameters). This covers 7 modules and 72 IDs. Variant suffixes such as
  `source_sign` or `source_tau` are renamed to say what the variant does.
- **Mixed modules:** the 4 mixed modules (environment transport, geometry,
  perturbations, tissue profiles) are split, and their BETSE-convention parts
  move to `validation/betse/`.
- **RNG replay:** BETSE random-number stream replay is dropped. BETSE
  comparisons with noise inject prescribed draws from the validation adapter.
- **Hash-pinned manifests:** the hash-pinned source manifests and
  `_verify_sources` guards are retired in favour of git provenance; stage A
  left them stale.
- **Junction law:** `betse_rate_junction_relaxation@1` merges into the identical
  `junction_voltage_relaxation@1`.
- **Schema fields:** `native_BETSE_*` schema fields are renamed.

Old configs and checkpoints with old IDs are refused afterwards; frozen evidence
keeps its own source snapshots. Each batch is gated by test tier 1, and by tier
2 for engine changes.

## D133: First heredity experiment choices (E07-v1)

2026-11-09, user decisions on the [design](HEREDITY_FIRST_EXPERIMENT.md):

- **Carrier:** electrical first, a NaV1.2 window current plus Kir2.1
  bistability. The expression carrier follows as Stage D.
- **Volume:** fixed volume for tier 1. D residence is capped near 70 min, runs
  above 10% osmotic excess are flagged and those above 15% are censored. Water
  and volume come later.
- **Renewal:** pattern-level is primary (Jaccard ≥ 0.8 through full founder
  turnover); carrier-level conversion is reported as secondary.
- **Parameters:** BETSE defaults plus the bistable channel set, as a
  sufficiency demonstration; calibration comes later.
- **Lead defaults:**
  - each newcomer draws its own parameters, so no state is inherited through
    them;
  - a BITSEY cross-check of the experiment driver is optional and runs in
    parallel.

## D134: Morphogenesis track choices

2026-11-09, user decisions on the [morphogenesis plan](MORPHOGENESIS_PLAN.md):
- **MG0 starts now**, in parallel with the heredity work: MG0a, a morphogen
  gradient on fixed tissue, then MG0b, a bistable voltage domain wall cut and
  restored on the channel model.
- **Mechanics** from MG1 onward is a 2-D vertex model: Farhadifar energy,
  differentiable in JAX, GPU-batched with padded topology. tyssue, run out of
  process, is the first reference.
- **Long-term targets:** the Drosophila wing disc, for its quantitative
  morphogen and topology data, with planarian anterior–posterior polarity on
  fixed geometry in parallel for the bioelectric link.

## D135: Optional long-horizon time modes

2026-11-09, user decision. The fine engine needs about 1 ms steps, while
heredity and morphogenesis questions run over hours to months. Coarser time
modes are added, all **optional and configurable**. The qualified fine engine
stays the default and is unchanged when a mode is off.
- **Now, E:** stationary-state, stability and one-parameter continuation
  analysis of a configured world, with no time stepping.
- **Now, C:** coarse projective integration (Gear and Kevrekidis 2003). Bursts
  of the unchanged fine engine are followed by extrapolated jumps, inside
  configured windows and never across a scheduled input.
- **Later, B:** a quasi-steady electrical model in which Vm, the field and fast
  gates become algebraic, with a fine/coarse handoff at checkpoints.

Each mode has a neutral ID, a declared validity domain, automatic fallback to
fine stepping and its own pre-registered qualification against the fine mode.
For days to months, the slow physics must also grow (water and volume,
metabolism, expression, turnover); a coarse mode alone does not make a
fixed-volume world realistic.

## D136: Experiments drive biologically valid engine features

2026-11-10, user decision, after the heredity pre-screens showed written D cells
loading K⁺ and anions in a fixed volume: "lets use this test as others to add
missing features to the current engine, biologically valid ones".
- **Rule:** when an experiment exposes a missing mechanism, add it to `src/cells`
  as a Cells model, not as a driver reset or a tuned rule.
  - Each model has a biological basis with cited parameter sources.
  - It gets a neutral name, an opt-in versioned ID, conserved accounting, tests,
    the tier gate and its own qualification against an independent reference.
  - The default engine is unchanged when it is off.
- **Water and volume:** D133 deferred these ("water and volume come later"). Work
  on them now starts as an opt-in water-and-volume model for the pump-channel
  tissue family. Whether E07-v1 uses it is decided when the experiment is
  redesigned.
- **Hypotheses stay hypotheses:** mechanisms proposed from model behaviour, such
  as per-hemichannel junction gating or a rule for newcomer junctions, are
  sourced from the literature before any design.

## D137: Test Cortés-Poza (2026) in Cells

2026-11-10, user decision on the [test plan](CORTES_POZA_2026_TEST_PLAN.md) for
"A hybrid mathematical framework for morphogenesis and regeneration" (J. Math.
Biol. 93, 43): "Sounds good on phase 0, and authors code can be outside refrence
and you rank this, we are in no rush".
- **Phase 0 approved as tooling.** The author's code is an external reference:
  run out of process, never copied or imported, with its licence checked first.
- **The lead ranks the work:**
  1. Phase 0 on the next free agent slot;
  2. cell replacement (G2) next;
  3. Phase 1 after the junction-heat fix and the frozen-composition comparison;
  4. Phases 2–3 through the engine-feature queue (D136).
- **The abstract regulatory modules stay out of the engine.** Only claims with a
  physical mapping are tested.

## D138: MG1 start and the paper backlog

2026-11-11, user decisions:
- **MG1.** "start is when the machine is fully free and according to your plan and
  priorities". MG1 (2-D vertex mechanics) starts once the machine has no outside
  jobs. Its pre-registered acceptance includes the additions from the
  [Deb et al. review plan](DEB_2026_MORPHOGENESIS_REVIEW_PLAN.md): junction recoil
  after ablation, and synthetic tension inference.
- **Backlog.** The user is building a backlog of papers to model ("I'm also
  creating a bit of a backlog for us"). Each paper gets a review, a mapping to
  Cells and a plan, indexed in [PAPER_BACKLOG.md](PAPER_BACKLOG.md); the lead
  orders it against the engine-feature queue (D136). Reproducing a paper's own
  model or code is tooling and needs the user's approval per paper (D137 covers
  only Cortés-Poza Phase 0).

## D139: Cell replacement (G2) rules

2026-11-11, user decisions on the [G2 design note](/mnt/workspaces/Cells/cell-replacement-g2-20261111-01/design-note-G2.md):
- **"Inherit" is excluded.** The literature (abstracts) says whole gap-junction
  plaques leave with a departing cell, and a newcomer forms new channels after a lag
  (about 2–20 min) over tens of minutes. No junction gate state carries across a
  replacement. The engine offers only the parameterised formation law (initial
  abundance, lag, time constant and gate at arrival, all declared). Pre-screen 9's
  inherit results, including the 91-cell full renewal, stay as driver evidence
  labelled biologically unsupported.
- **Newcomer templates: both kinds now.** These are isolated cells at their own
  steady state (D133) and a donor copy (division: the newcomer takes a declared
  neighbour's contents). The donor copy is a different heredity claim, an inheritance
  route for the written state, and its arms are labelled as such.

## D140: Molecular scope: assembly, not folding

2026-11-11, user clarification: "our ambition is assembly of structures like the
proteasome and up but not protein folding itself, while we'll still simulate both
beneath (GRNs) and above how the proteins are used".
- **Skipped:** protein folding itself, the one level not simulated.
- **Beneath it:** gene regulation, which sets how much of each protein is made.
- **Above it:** the assembly of proteins into complexes and molecular machines,
  from protein cages (the first case) toward structures such as the proteasome and
  larger, and how those machines are used in cells and tissues.
- **Lead note, not part of the user's decision:** folded structures and interfaces
  would come from structural data or prediction. The current cage model uses a
  prescribed contact graph.

## D141: Cell division, high priority

2026-11-11, user decisions on the [cell-division plan](CELL_DIVISION_PLAN.md):
- **Priority.** Simulating cell division in a simple subject with a lot of wet-lab
  data is high priority. It is the first slice of morphogenesis rung MG3, brought
  forward.
- **Subjects.** "Either Xenopus or C. elegans": either is acceptable as the first
  subject. The lead's order is Xenopus cleavage first, for its bioelectric fit,
  then C. elegans. The order swaps if verification finds the Xenopus data too
  thin.
- **Rule.** "As with all our tests we should add to our simulation or models as we
  need those, we want the simulation/modeling to be as realistic as possible."
  Whatever physiology a subject needs (for example cortical polarity and spindle
  positioning for C. elegans) is added to the engine as cited, opt-in models
  (D136). It is not prescribed.

## D142: Architect new features cleanly

2026-11-11, user direction: "make sure to architecture new features well not
ad-hoc, object oriented multiscale and clean".
- **Design first.** Every new engine feature starts with a design note, reviewed
  by the lead and the advisor before code.
- **What the note sets out:**
  - the entities it touches and the state each owns;
  - the operations it adds and their interfaces;
  - how it composes with the other features across scales.
- **Object-oriented at the level of entities, specs, models and operators.** The
  hot loops stay functional JAX array kernels.
- **Composition over combination families.** Features compose through shared
  interfaces rather than a new model family for each combination.
- **First application:** cell division (D141).

## D143: One composite tissue model, adopted now

2026-11-11, user decision on the [cell-division design note](CELL_DIVISION_DESIGN.md):
"Re-express everything now".
- **The composite.** One composite pump-tissue model runs `resolved_pump_tissue@3`'s own
  step plus declared operators. Water, cell replacement, division, and later growth and
  mechanics are operators, and new combinations are definitions rather than model
  families (D142).
- **Now, not later.** The composer stage rebuilds the qualified `resolved_pump_water@1`,
  `resolved_pump_water@2` and `resolved_pump_replacement@1` through the composite at
  once.
  - Each must be bitwise equal to its frozen model on its own test and qualification
    worlds before its module becomes a thin composition.
  - If a guard fails, that model stays frozen and the failure is reported. Integration
    grants no new acceptance.
- **Lead defaults stated with this decision (the user may object):**
  - J1 is the first judged run;
  - the first slice's stated limits are accepted;
  - unqualified operator combinations may run only as labelled development runs, with
    judged status only from registered protocols.

## D144: Qualify the simulator for many uses, not one experiment

2026-11-11, user direction: "we never want to build something in the simulator or
models just for one experiment, but rather work on slowly qualifying the simulator
for different work".
- **General features only.** An experiment can reveal a missing mechanism (D136),
  but the engine gains a general, reusable model or operator, not an
  experiment-specific one. Experiment-specific choices stay in validation drivers
  and protocols.
- **Qualification grows step by step.** Each feature is qualified against
  independent references and judged runs, so the qualified scope widens over time.
- **Current examples:**
  - Division is built as general operators: membrane insertion, a restricted
    compartment, partition and bridge closure. Xenopus is the first validation case.
  - Current injection is planned as a general control.
  - The definition-check bound is to scale with any cell size.
  - The protein catalogue is shared by every model.
- Builds on D136, D142 and D143.

## D145: The current plan is adopted, with the L4 now and GH200 next week

2026-11-12, user direction: "so we get GH200 access by end of next week so let's wait with
that and use the L4 we have that one just for us rest you you guys suggest - as much as we
can in parallel".
- **Adopted:** [CURRENT_PLAN.md](CURRENT_PLAN.md), the gates and their completion evidence.
  It was built from two architecture reviews and the advisor's review.
- **GH200 (JUPITER) work waits for access, expected by the end of next week.**
  - The L4 is used fully meanwhile, for us only.
  - The only GH200 preparation now: make the L4 step-profile harness rerunnable on GH200
    on day one.
- **The open choices, taken as suggested by the lead and the advisor:**

  | Choice | Taken as |
  | --- | --- |
  | Check C1 | Stays held |
  | Single-world size | Set later from the L4 profile and the GH200 measurements |
  | Molecular-loop unit | Provisionally the junction-channel population, which both renewal and division consume; confirmed at that gate |
  | Heredity or division | Both in parallel: division work takes the agent slots; heredity takes the cores and the L4 |
  | E07-v1 redesign | Stays open until the turnover results exist |

- **Parallelism stays within AGENTS.md:** one lead, at most four subagents on disjoint files,
  memory-capped units, and one GPU process at a time.
  - Parallel work comes from inside the gates.
  - Cortés-Poza Phase 1, the GRN track and catalogue stage 3 stay held.
- **Not approved by this entry:** the two tooling items, a public validation package and a
  versioned checkpoint migration. They need the user's explicit approval when they become
  due.
- **Resource note:** more RAM on the VM is the cheapest gain in parallelism. Memory, not CPU
  or GPU, is the limit.

## D146: Neutral names for BITSEY-derived identifiers

2026-11-12, user direction. BITSEY (Grodstein and Pietak,
https://gitlab.com/grodstein/bitsey, pinned at `b2cb370`) is an external reference
like BETSE (D131). It runs out of process, Cells compares against its saved
outputs, and `src/cells` carries no BITSEY-named identifiers. This is a pure
rename with no numerical change:

| Kind | Old | New |
| --- | --- | --- |
| Model ID | `bitsey_emt_pair@1` | `emt_mirna_pair@1` |
| Observer ID | `bitsey_nominal_pair_pure_readouts@1` | `emt_mirna_pair_pure_readouts@1` |
| Parameter set of the pair | `bitsey-b2cb370-emt-pair-simple` | `emt-mirna-pair-scaled-simple` |
| Parameter set of `emt_mirna@1` | `bitsey-b2cb370-mirna-simple` | `emt-mirna-scaled-simple` |
| Time unit | `bitsey_time_unit` | `nominal_time_unit` |
| Regulatory coordinate unit | `bitsey_scaled_coordinate` | `scaled_coordinate` |
| Junction diffusion unit | `m2/bitsey_time_unit` | `m2/nominal_time_unit` |

- **Citation:** the source stays cited in docstrings and in the
  `upstream_revision` summary field. As with BETSE, docstring citations and
  disclaimers that name BITSEY remain.
- **No aliases:** old configs and checkpoints are refused. Runs recorded before
  the rename are reproduced from their frozen snapshots and from the tag
  `bitsey-names-frozen-2026-11-12`.
- **Frozen inputs keep their labels:** the reference panel
  (`bitsey_emt_pair@1-design`), the E02 protocol (`bitsey_emt_graph@1-design`),
  the probe fixtures and `docs/E02_SWITCHING_PROTOCOL.md` record what was
  registered.
- **Audit:**
  - Nothing in the engine imports BITSEY. `emt_mirna.py` and `source_pair.py`
    are independent implementations that use the source's parameter values.
  - Classification of `processes/source_electrochemistry.py` lines 17–56 is
    pending. It writes published laws, but it reproduces the source's
    implementation choices for parity; the user decides.
  - Left for a later decision: BITSEY's species names (`miR200_total`,
    `Zeb_mRNA_total`, `ZEB_prot`, `snail`, `ST`), which are schema keys, and the
    `source_*` module, class and stage-domain names.
  - BITSEY declares no licence. Its files say "See LICENSE", but no licence
    file exists anywhere in its history, so its code may not be copied.
  - The five `scripts/capture_*` tools that import BITSEY in a worker process
    belong in `validation/bitsey/`.
- **Evidence:**
  - `/mnt/workspaces/Cells/bitsey-rename-20261112-01/`: the audit and licence
    findings, the bitwise identity of ten runs, and the tests before and after.
  - `/mnt/workspaces/Cells/bitsey-rename-20261112-02/`: the tests after the
    rebase onto `5fdbeb3`.

## D147: Definitions with free field offsets declare field solver version 3

2026-11-13, lead decision, reviewed by the advisor (draft for landing with
[FIELD_FLOOR_ACCEPTANCE_DESIGN.md](FIELD_FLOOR_ACCEPTANCE_DESIGN.md)).
- **The trigger is mechanical.** It applies to the resolved pump family, whose field
  solve is `numerics/surface_field.py`'s capacitive reduction and which accepts both
  versions: `resolved_pump_tissue@1`–`@3`, `resolved_pump_water@1`–`@2` and
  `resolved_pump_replacement@1` (shown by `test_field_floor.py` and the note's guard 1).
  A new definition of the family with at least one free field offset declares
  `capacitive_reduction_gauged_damped_newton@3`. The count needs only the definition:
  the `field_offset_free` leaf of `initialise(spec).layout`, set by finite extracellular
  space with floating components. Definitions with no free offset keep version 2,
  because the floor never decides their acceptance.
- **In the drivers:** `validation/tissue/field_solver_choice.py` applies the trigger
  (choice `auto`); `heredity_pilot.py`'s `--field-solver` defaults to it for its start,
  prepare and run parts, and `--field-solver 2` reproduces the definitions made before
  this decision. Builders keep their earlier default, version 2, so guard worlds and
  studies built through them are unchanged.
- **Drivers that must call `field_solver_choice.declare()`:** `heredity_pilot.py` (it
  does), and every new run driver that builds a free-offset world, E07-v1's among them.
  `tests/unit/test_d147_drivers.py` fails for a run driver under `validation/` that
  uses a builder of such a world (the modules `resolved_scale_world`,
  `surface_pump_v3_study` and `heredity_pilot`, or the fixture function
  `pump_water_fixtures.scale_world`) without the choice, unless it is exempted there with
  its reason. The check is static and sees only those builders: a driver that builds a
  free-offset world any other way must call `declare()` by this rule alone.
- **The exemptions are narrow.** The studies recorded before this decision
  (`batched_worlds_study`, `cell_replacement_cost`, `ledger_rounding_study`,
  `resolved_scale_study`, `surface_pump_v3_study`) are exempt only for reproducing their
  recorded runs. Any new run they make of a free-offset world declares its field solver
  by this decision. The cross-revision guards, the judges and the floor tools are exempt
  because they run definitions as declared, or both versions on purpose.
- **Why.** Version 2 accepts a field solve only below `NEWTON_TARGET`. On the W1 hold's
  825-node tissue (172 free offsets), a converged root sits at 0.8–1.1 of that target,
  at the rounding floor of the current balance. Whether it is accepted then depends on
  the compiled program: the CPU's vectorized and scalar programs refuse at different
  steps, and the L4 has not refused these worlds. Version 3 also accepts a residual
  within `CURRENT_FLOOR_ULPS` (1e3) ulps of the attainable floor. It iterates exactly as
  version 2. On that tissue the cap lies about 8–2,200 times above `NEWTON_TARGET`,
  depending on the component.
- **Unchanged:** version 2's semantics and every solver and model ID. Every qualified
  world (W1, W2, G2-Q1), the hold's segment 1 and every saved snapshot keep version 2.
  There is no migration.
- **A switch is a new definition.** It cannot resume or start from a version-2
  checkpoint (`validate_checkpoint` refuses its layout), so a run is rerun from its
  start under version 3.
- **A change to a solver's iterations or acceptance is a new solver ID**, never an edit
  to an existing one. For example, fixed-count masked loops would be a new ID.
- **Evidence** (`/mnt/workspaces/Cells/window-timing-20261112-01/`,
  `/mnt/workspaces/Cells/field-floor-guards-20261113-01/`):
  - Margins: W1's trajectories, W2's arms, G2-Q1's cases and the turnover pre-screen's
    discs have no free offsets, and their residual is exactly 0. The hold's
    preparation worlds sit at 0.92–0.995 of the target from t = 0.
  - Version 3 on the hold's edge states (CPU): it accepts every state version 2
    refused, in the vectorized and scalar programs. Its states are bitwise version 2's
    before each refusal. Every refused residual is within 2 ulps of its floor.
  - Guard 1, on 41 worlds before and after main's S2: the floor's magnitude reaches two
    multiplications and one comparison per field solve. Every output depends on it only
    through that comparison's boolean, and the device row checks never read it.
  - Guard 2: W1, W2, G2-Q1, Q5, Q6, W37 and the 825-node world run equal under both
    versions (bitwise, with device row checks, where the part records them).
  - Guard 6: the @3 tests pass. A solve held just under the cap, 866–2,166 times
    `NEWTON_TARGET` on the hold's states, passes every row check and ledger. Its state
    change over 20 steps (at most 5e-13) cannot be told from rounding. The checks cannot
    see the residual even under caps 1e9 times wider; there the change reaches 4e-11 at
    1e12 ulps, which scales to about 4e-20 at 1e3. That bound, not the checks, is what
    makes the cap safe.

## D148: An in-place fix to shared qualified code

2026-11-13, lead decision, reviewed with the advisor (drafted in
[the v2 design note](PUMP_COMPOSITE_V2_DESIGN.md) §3, S3 prerequisite (c)).
- **D147 makes an ID promise its semantics.** A change to a solver's iterations or
  acceptance takes a new ID. A fix to code that qualified models share may instead be made
  in place, but only if all four criteria below hold, fix against no fix.
- **The criteria:**
  1. Physical fields are bitwise identical in every qualified world and in every program:
     scalar, windowed, vector-window and batch runs, and the derivative programs the judges
     use. That covers every state field, observation column and diagnostic, except the
     ledger accumulators and their residual diagnostics.
  2. Verdicts, and every registered number other than those ledger diagnostics, are
     unchanged.
  3. Ledger accumulators and their residual diagnostics change only at rounding level, and
     every case is listed.
  4. The crossrev baseline is renewed at the landing commit. 8416a72 stays as the earlier
     record.
- **Otherwise** the change takes a new ID (D147), or an allowance where the residual is
  representable precision. That choice is the user's.
- **The ledger diagnostics.** The residual diagnostics of the electrode, global-charge and
  energy ledgers are functions of the ledger accumulators, so a fix to an accumulator
  changes them. That is the fix working, not a moved number: electrode errors go to 0, and
  global-charge ratios move within rounding. For example, Rm1's bound ratio went from
  0.0236 to 0.0241, well inside its bound.
- **The first case, `surface_tissue.capacitor_change` (S3 prerequisite (c)).**
  - Explicit species-order adds make every evaluation of a state's plate charges one
    computation. Before, XLA summed them in two orders, and the Xenopus egg's electrode
    ledger drifted by 7e-22 C per step.
  - **With an optimization barrier added, it was not admissible.** The forward runs were
    identical, but the barrier changed the step-map Jacobian that the stationary judges take
    by automatic differentiation. W1 and W2 moved 49 consistency numbers (by 1e-14 to 1e-13
    relative), with their verdicts unchanged, so the stop rule triggered.
  - **Without the barrier (option 3, registered before its runs at c540fdb), it was
    admissible.**
    - The judges were unchanged apart from the ledger diagnostics.
    - The forward subset was identical.
    - The egg's electrode ledger stays within one ulp of its plate charge on every row.
  - Evidence: `/mnt/workspaces/Cells/composite-v2-20261112-01/s3-fix/`, listing every
    ledger change.
- **What crossrev compares** (`validation/tissue/composite_crossrev.py`): for each world of its base,
  qualification and injection sets, traced at t = 0, the jaxpr text of the checked step, right-hand side and
  device row checks, in which scalar constants such as `NEWTON_TARGET` appear as full-precision literals; the
  dtype, shape and SHA-256 of every array those programs close over; and the initial state, layout, controls
  at every schedule time and device-check constants. It does not compare the execution paths' rollout
  programs or host-side checks (`check_values` and its tolerances). Constants are compared from 13 November
  2026; the retro-check found them unchanged since `8416a72`, so earlier verdicts stand. The floor guard of
  D147 compares primitive counts, not constants: rerun it with constants before version 3 serves a run of
  record.

## D149: The EMT-miRNA pair's source profile keeps the reference's numerical conventions

2026-11-13, user decision, reviewed by the advisor. This settles D146's pending
classification of `processes/source_electrochemistry.py`. The user's words were "Lets go
on your suggestions, but get adviser view as well". They accepted the lead's suggestion:
keep the module as a cited, independent profile rather than move it to a validation
emulator.
- **What the module holds.** It writes published laws: a constant-field leak, a pump
  cycle and a gated junction flux. In lines 17–56 it also reproduces four implementation
  choices of the reference (BITSEY, Grodstein and Pietak, pinned at `b2cb370`):
  - the 1e-25 offset added to the constant-field argument;
  - the pump switched off on membranes with no channels;
  - the upwind donor of the junction flux;
  - the miRNA scaling of the junction gate.
- **This is an exception to AGENTS.md as written.** AGENTS.md says `src/cells` carries
  no simulator-specific conventions, and the rule covers BITSEY. These four are such
  conventions. They stay because they keep the recorded *How Patterns Return*
  replication runs bitwise reproducible; moving them to a validation emulator would
  break that continuity.
- **They are confined to one model.** Only `cells.models.source_pair`
  (`emt_mirna_pair@1`) imports the module, and its spec admits only the parameter set
  `emt-mirna-pair-scaled-simple`. `tests/unit/test_source_profile_boundary.py` fails if
  any other module imports it.
- **Nothing is renamed; this is documentation.** The module name carries no BITSEY
  identifier. BITSEY's species names and the `source_*` names stay as D146 left them,
  open for a later decision. The module docstring cites the source and this decision.
  No code is copied, since BITSEY declares no licence.
- **Not a precedent.** New physics in `src/cells` follows AGENTS.md. A further exception
  needs its own user decision.


## D150: Secreted-species transport is promoted now

2026-11-13, user decision after the granzyme K review
([PAPER_REVIEW_GZMK_AGEING.md](PAPER_REVIEW_GZMK_AGEING.md)): "we do have plans to be able to
run special modes of Cells at differnt timescales, so down the road nothing right now but for
sure the secreted-species transport now".
- **Promoted now:** general secreted-species transport. A protein-scale species is secreted by
  cells, moves in extracellular space, and is taken up or cleared, with conserved accounting and
  a catalogue identity. It is a general, reusable engine feature (D136, D144), never specific to
  granzyme K, and it also serves the roadmap's morphogen-source goal (ROADMAP item 9).
- **Design first (D142),** then code behind the usual guards. Calibration comes from a measured
  protein or morphogen gradient in the literature.
- **Deferred:** organ-scale ageing timescales (months) wait for Cells' planned long-time modes.
  Nothing is built for them now.
- The checkpoint-continuity decision drafted as "D150" in its design note takes the next free
  number when the user approves it.

## D151: Every reviewed candidate is deferred, not closed

2026-11-13, user decision on the paper reviews, with the advisor's help: "Have advisier help but
we want to test all of this in the end".
- **What it means.** Every ranked candidate in the paper reviews stays on the list as deferred,
  with its prerequisite and gate named. Covered: partial reprogramming, granzyme K and tissue
  ageing, kinetochore counts, and the earlier reviews. Wording such as "not recommended", "park"
  or "not a Cells target" in the backlog becomes "deferred".
- **Partial reprogramming, taken now:**
  - **E07-v2** adopts the write–clear–challenge rules, translated to Cells, drafted after
    E07-v1's analysis. It is in the coupled-renewal gate of CURRENT_PLAN.
  - **Functional challenges,** in order: a second cue, injected current, then an osmotic step,
    which needs replacement over water.
  - **The cross-lineage perturbation test** is logged as a second-tier benchmark for the future
    gene-regulation layer, as a direction-of-response test only.
  - **Watch** for the peer-reviewed version, its GEO accession and its code deposit when E07-v2
    is drafted and when the gene-regulation track opens.
- **What it does not authorise:**
  - any change to the registered E07-v1, whose protocol, frozen scorer and judged items stay as
    they are;
  - lifting D145's holds (Cortés-Poza Phase 1, the gene-regulation track, catalogue stage 3);
  - reproducing a paper's own pipeline, model or code, or writing a reference solution for it,
    which stays tooling needing the user's approval per paper (D138);
  - building a feature for one paper (D144).

## D152: Reactions on the shared inventory are designed as a general feature

2026-11-13, user decision on the pattern-recovery path (E15,
[note](EXPERIMENT_PATH_PATTERN_RECOVERY.md)): "Yes on the question and lets go as you see fit
otherwise". The question was whether reactions acting on the same molecules that transport moves
should be designed as a general engine feature.
- **What it means.** Driven, open, nonlinear reactions that write @3's species rows become a
  general composite operator. These are the one inventory that membranes, faces and D150's
  operators move. The operator is the engine's route to Turing-type self-organisation.
- **Consumers named so far:**
  - MG0c, Turing patterning at the predicted wavelength, which is its qualification case;
  - the GZMK review's catalysis on a substrate (item 2);
  - E15's self-organisation layer.
- **Design first (D142).** The note is written against D150 v1's accepted design. It settles
  the GZMK review's shared-state question: `network_reactions@1` keeps its own species state
  beside the physical inventory. The design must give:
  - one owner per species row (the ownership contract);
  - conserved material and charge;
  - energy booked in the composite's ledgers;
  - bitwise idleness at zero rate (D136);
  - cited kinetics.
- **Order.** The design note starts when a subagent slot is free. Code follows D150 v1's code
  (after S5a) and the note's acceptance.
- **What it does not authorise:**
  - code before the note is accepted;
  - any change to `network_reactions@1` or the calcium-energy family;
  - lifting D145's holds;
  - a law or species named for one experiment (D144);
  - reproducing a paper's model (D138).
- **The note, accepted 14 November 2026** by the lead with the advisor
  ([SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md); its rulings are
  recorded in §9).
  - **The operator.** `local_species_reactions@1` holds one network per composition. It runs as a
    split part around @3's step and writes @3's neutral species rows at cells and finite outside
    nodes.
  - **Shared state.** `network_reactions@1` stays separate, neither migrated nor wrapped. Only the
    neutral detailed-balance kernel `mass_action.reversible_flux` is reused, unchanged.
  - **Energy.**
    - Exact ΔG bookings, with a standard-potential term the operator owns, since @3's chemical
      term has none.
    - At nodes with both passive and driven routes, a per-route hybrid books the heat.
    - One known limit: a driven route that carries a trace species across a passive equilibrium
      within one half-step overbooks that step's heat.
  - **Numerics.** SSPRK(3,3) half-steps under a stage condition at θ = 1/2. dt·L > 1 is refused.
  - **Refused in version 1:** RK4, the stationary analysis, volume providers, closers, charged or
    permeant reacting species, turnover on reacting rows, and cell routes on replaced slots.
  - **First acceptance.** MG0c's numerical qualification, against textbook references written by
    an agent that never reads the operator code.
  - **D138.** The lead's reading is that MG0c is within it; work proceeds unless the user objects.
    The note's questions 10 and 11 stay open for the user.
  - **The D148 round it queues.** @3's explicit bound and its membrane-rate rule have no material
    term for neutral species on junctions and membranes (probe C4).
    - A sweep found no world that declares such a species, and both version 1s refuse them.
    - The round comes after D150 v1 lands, statically gated. It fixes stability, not accuracy.

## D153: Checkpoints resume across a source or runtime change only through a recorded admission

2026-11-13, user approval of the tooling, with the lead's design reviewed by the advisor
([CHECKPOINT_CONTINUITY_DESIGN.md](CHECKPOINT_CONTINUITY_DESIGN.md)). Landed with the first implementation on
14 November 2026; see PROGRESS for its evidence.
- **The approval.** The user's words were "yes fix checkpoint continuty also". This
  approves the versioned checkpoint migration that D145 listed as unapproved tooling. The
  public validation package stays unapproved.
- **The attestation question.** The user delegated it ("lets go as you see fit otherwise").
  After the lead told the user that it had taken the delegation to cover the question (the
  case-1 probe is within AGENTS.md's rule, AGENTS.md unchanged), the user confirmed it on
  13 November: "sounds good".
- **Refusal stays the default.** `load_snapshot` and `load_batch_snapshot` refuse any
  change of source or runtime unless given a continuity record
  (`cells.checkpoint_continuity@1`).
  - A record binds one checkpoint manifest and one pair of identities.
  - It names both sources and runtimes, the evidence and who admitted the resume.
  - It lives in the new run's folder, and the run's provenance names it.
- **Four cases:**
  1. **Source changed, programs unchanged:** admitted when the continuity probe finds
     four things identical:
     - the programs the path compiles: jaxpr, constants, lowered StableHLO and compile
       arguments;
     - the bindings over the remaining horizon;
     - host acceptance and observation on the run's saved states;
     - a bitwise overlap: the first rounds of the resume, run on CPU under both trees,
       past the next event and observation, with each round's bound arguments and
       outputs compared.

     The probe runs on CPU, on the checkpoint's own definitions. No file is exempted by
     argument. The record states the overlap's length. A driving-loop change that first
     moves an output after it is the stated residual.
  2. **Programs or bindings changed, physical fields unchanged:** only with a D148 record
     covering those definitions, admitted by the lead. Never automatic.
  3. **Definition, layout, solver or model ID changed:** refused. No record relaxes these
     checks. D146 and D147 stand: no aliases, no migration.
  4. **Runtime changed:** every differing field is named in the record, and the first
     landing refuses them all. The rules are parked until a run needs them:
     - host-side fields, decided at trace level on CPU;
     - compiler and device fields, decided by tolerance with the backend-variant method,
       at least three repeats, and terms taken over all pairs.
- **The first landing:** the vector-windows path, CPU definitions with `jit: true`. Other
  paths answer "cannot decide" until the consolidation.
- **GPU definitions** have been admitted since 14 November 2026, through the CPU-host probe
  with `execution_device` patched (design §13.4: every question was identical on the L4), and
  the record notes the patch. An admitted L4 checkpoint resumed on the L4, where the loader
  checked the runtime and `jaxlib` exactly.
- **Who admits:** the probe decides case 1 and the lead records it; the lead admits
  case 2; any registered run is the user's.
- **Unchanged:** registered runs. The W1 hold stays on `source-09`, E07-v1 on its
  snapshot, and judges on clean snapshots. The first consumer is a CPU development run.
- **Bypasses.** Execution from saved state either loads through the loaders or declares
  itself a new run started from imported state, recorded and judged on its own. A static
  test lists the exempt tools with their reasons.
- **Evidence:** `/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/`. The probes
  show that:
  - cohort programs traced from a batch snapshot, and captured from all five paths'
    entry points, repeat identically;
  - jaxpr text omits constant values, so constants and the lowered StableHLO are
    compared;
  - host-only and comment edits leave programs, bindings and host replay identical;
  - a program edit changes every path's program;
  - an observer-only edit changes only the host replay.

## D154: Every experiment must eventually be visualizable, through one run-view output

2026-11-14. This is the user's request, relayed by the visualizer session that the user
started the same day: "ask the lead to add this to the architecture in a general way, all
experiments eventually must be visualizable".
- **What it means.** Every run writes a view record beside `definition.json`, through one
  shared output path, never one per driver. A viewer then needs nothing else. The record
  holds:
  - **geometry:** where each entity is, in physical units. That means cell centres or polygons
    and their vertices, and contact endpoints, static or per record;
  - **identity:** stable ids saying which column of each recorded array is which cell,
    membrane, junction or channel;
  - **record metadata:** for each recorded array, its name, unit, axes and time base;
  - **events:** time, kind and entity ids, such as replacement, division, cue and injection;
  - **representation per layer:** simulated, modelled in aggregate, or prescribed. Mixed runs
    are expected; for example, an aggregate assembly model drawn with illustrative machines;
  - **scale:** molecule, cell, tissue, organ or organism. One cell comes first; the larger
    scales are placeholders.
- **The engine side.** A separate view file is written by the shared run-output path.
  - It is not fields in the definition, so definitions, bindings and crossrev stay unchanged.
  - The exact file and field names come from a short design note (D142), aligned with the
    consumer schema the visualizer drafts (`visualizer/schema/RUN_VIEW.md`).
- **The viewer is a read-only consumer.** Rendering never sets simulation time or random draws
  (ARCHITECTURE, "Analysis and viewing").
- **Order.** The design note comes when an agent slot is free. Meanwhile the visualizer adapts
  existing runs on its own side, so nothing waits.
- **What it does not authorise:**
  - any change to definitions or qualified models;
  - view writers per driver;
  - the visualizer committing outside `visualizer/`.

## D155: The Myc–cyclin T1 heart paper is modelled in two tracks; excitable tissue and coupling out of the inventory are designed now

2026-11-14, user decisions on the [review](PAPER_REVIEW_MYC_CYCLINT1_HEART.md) (Boikova et al.
2026). They follow the lead's recommendations, reviewed by the advisor. The user asked for
ambition ("we want to be ambitous"), then answered "Yes lets raise it and I agree, lets go".
- **Two tracks.**
  - **Track E, excitable tissue.** Do weakly coupled cells with low sodium conductance slow or
    block conduction, and does clustering matter? It needs excitable tissue and a prescribed
    perturbation, not the pulse, the gate or division.
  - **Track R, regulation:** the pulse, a gate on cycle entry, then division triggered by state.
  - The tracks join at newborn-cell integration.
  - There are two clocks: the slow world runs coarsely, and short conduction assays run from its
    frozen snapshots.
- **1. D145 is narrowed, not lifted.** One general feature is authorised for design (D142):
  *coupling out of the inventory*.
  - A species amount sets another operator's control, through the contract's
    `CONTROL_FACTORS`.
  - Later, it triggers an event such as division.
  - The rest of the gene-regulation track stays held.
- **2. Comparisons with this paper's data** are approved at every stage, each with its
  predictions registered before its runs. The paper deposits no model, so nothing is
  reproduced. The user is asked for Supplementary Tables 1–2 and the source data.
- **3. The first target is conduction.**
  - A probe on the engine as it is comes first: can the channel laws the composite admits
    propagate an action potential along a chain, at a feasible step?
  - The passive sheet, with junction availability perturbed on a schedule, becomes Track E's
    control arm.
- **4. Excitable tissue enters the engine-feature queue now** as general excitable-tissue
  physics, not a cardiac mode.
  - A design note comes first.
  - It is qualified against cable theory, with independent references.
  - Its wavelength is checked against the 127-cell sheet. Re-entry is expected to need the
    sparse solver and GH200.
- **5. Species** is decided in that design note: a generic cell for qualification, mouse for the
  first comparison, human second.
- **6. The protein catalogue's scope** is deferred; it blocks nothing.
- **The agent cap.** At most six subagents from 14 November 2026, raised from four, on disjoint
  files. AGENTS.md is updated.
- **What it does not authorise:**
  - the full gene-regulation track, or D145's other holds;
  - a feature built for this paper (D144).
- **The review's own findings** (its §6) are the starting point.
  - The composite carries five channel laws today.
  - There are three composition walls on Track R. Turnover and reactions refuse closers. The
    partition refuses replacement, so a cell born by division has no junction-formation law.
    The partition refuses water and pumps on the dividing cell.

## D156: The external architecture follow-up of 14 November is adopted into the D145–D155 plan

2026-11-14. The user supplied an external review of `62ca548` and asked: "check this also with
your adviser then go as you see fit". The lead and the advisor checked it against the code and
adopted it.
- **A four-level status scale** is used in the entry documents: *implemented*, *guarded*,
  *numerically qualified*, and *judged in an experiment*.
- **Conduction is the next integrated milestone.** D155's probe on the engine as it is comes
  first, with its success criteria defined before running:
  - excitation that continues beyond the stimulated cells;
  - passive, subthreshold and sodium-disabled controls;
  - activation time, velocity, capture, recovery and block, each measured;
  - stability under timestep refinement, with chain-length and boundary-distance checks;
  - ledgers that keep passing.

  Its verdict decides between proceeding with the existing mechanisms and naming the one
  mechanism the excitable-tissue feature must add. The staged move of old families (lead's
  option (b)) waits for that verdict.
- **D155 item 1, corrected.** `CONTROL_FACTORS` multiplies the inner model's control fields
  only.
  - Version 1 of coupling out of the inventory is therefore a species setting @3's channel or
    junction availability.
  - Routing to another operator's control (a reaction multiplier, a turnover rate, an event
    threshold) is a separate, named door, which the division trigger needs.
  - The design note must settle target routing, source semantics (amount or concentration,
    current volumes and masks, axis mapping, refusal of unsupported compositions) and
    evaluation time (held through the inner step, or evaluated at its stages).
  - The first integrated case is inventory → effective control → a measurable electrical
    response, qualified against an independent coupled-ODE reference.
- **The qualifications in flight finish as planned:** D150's registration and judged run, and
  D152's MG0c with a compiled composition (several sites, a permitted second writer, supply
  counted once, a rejected step restoring the whole state). Local accuracy at the consumer's
  concentrations belongs to the coupling milestone's protocol.
- **D147 for composite definitions** is a prospective gap, not a defect in any judged result.
  `field_solver_choice` auto-selects only for the tissue, water and replacement IDs.
  - Its explicit policy, with four tests, is the first freed slot's task: a free-offset composite
    selects the intended solver; a held-bath composite is unchanged; the legacy solver is
    reproduced explicitly; a checkpoint is refused after a solver change.
  - Before registration, D150's judged definitions are checked for free offsets, and so are
    MG0c's and Track E's.
- **Newborn integration** comes as a reusable contact-maturation process that replacement or
  division can initialise. Then four named steps follow: reaction state across partition;
  contact formation after birth; newborn integration in a qualified conduction model; and
  volume, pump and lifecycle interactions when a consumer needs them. The current refusals stay
  until each step is qualified.
- **Performance.** The field-solver measurement plan gains conduction workloads compared at
  equal accuracy, and static-world capacity is kept apart from dynamic-field capacity (the
  64-node limit). Invalidation and reuse rules at geometry and activity events are qualified
  before lifecycle worlds are scaled.
- **Two execution interfaces** go with the first freed slot, inside the existing paths:
  - host-only start and failure records for the phase markers;
  - D154's one shared run-view writer, exercised on a static conduction case and a
    birth/partition event.
- **The working order:** the conduction probe, the D150 and D152 qualifications and the
  coupling design run in parallel now, with the documents reconciled alongside. Next comes the
  minimal inventory → control → electrical-response case, then newborn integration and
  state-triggered division. The full gene-regulation track stays held.

## D157: A closed internal compartment on the shared inventory (FR-1) is logged as high priority

2026-11-14, user request: "here is a new feature request please log as high prioriity". The user
supplied the request (FR-1), and it is logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-1--a-closed-internal-compartment-on-the-shared-inventory).
- **The feature:** a cell-owned finite node, with no bath and no faces, bounded by one patch of
  its owning cell, carrying its own volume and inventory rows, with transfer routes to the
  owner's cytosol.
- **Its uses:** vesicles and granules (roadmap item 9), lysosomes, phagosomes and autophagosomes,
  and the ER and mitochondrial matrix as species compartments.
- **The order:** fixed topology first, with retained and cytosolic material kept distinct and
  transfers reconciled on both sides. Dynamic internalisation (FR-2) later.
- **Design first (D142),** as a general feature (D144). The lead's mapping (exchange as a possible
  transfer law, fixed volume first, the electrical treatment as the hard question) is for the
  design note to test.
- **What it does not authorise:** code before the design note is accepted.

## D158: Internalisation of membrane and its populations (FR-2) is logged as priority 2

2026-11-14, user request ("first log this one"), the requester's priority 2. Logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-2--internalisation-of-membrane-and-its-populations).
- **The feature:** the retrieval direction of membrane insertion. Area, capacitance and their
  populations move inward at a scheduled rate, carrying the FR-1 compartment they form.
- **Its open question:** retrieval's energy source. The capacitor's free energy rises, so a
  declared work source is needed. One design of energy-pool coupling should serve FR-2 and the
  pool doors deferred by D150 and D152.
- **The order:** after FR-1, design first (D142), as a general feature (D144).

## D159: The site-occupancy primitive (FR-3) is logged as priority 2

2026-11-14, user request ("then next one"), the requester's priority 2. Logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-3--the-site-occupancy-primitive).
- **The feature:** binding sites as state with one owner. Bound and free share one material
  ledger, and accessibility is a factor separate from stoichiometry. Partition and reset rules
  at division and replacement are declared. It is D150 §2.5's door, with its analytic
  saturable-sink guard.
- **The order:** its design may precede FR-1's code, since its first version needs only membrane
  state and @3's free inventory. Its internalisation step follows FR-2. Design first (D142), as
  a general feature (D144).

## D160: Compartment pH (FR-4) is logged at the requester's priority 1, sequenced after FR-1

2026-11-14. The user supplied the request (FR-4), logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-4--compartment-ph-a-proton-species-an-acidifying-pump-buffering).
- **The feature:** protons as a species, an acidifying pump drawing on fuel, and buffering
  through the reaction operator.
- **The doors it meets:**
  - a proton row is already legal in @3;
  - D152's charged closed reactions (buffering);
  - the energy-pool coupling, shared with FR-2;
  - FR-1's electrical treatment. A proton-carrying compartment cannot be electrically silent,
    and the counterion pathway is explicit.
- **The order:** after FR-1, as the request sequences it. Design first (D142), as a general
  feature (D144).

## D161: State-conditioned transfer across an internal membrane, with leak and reseal (FR-5), is logged

2026-11-14. The user supplied the request (FR-5), at the requester's priority 1, logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-5--state-conditioned-transfer-across-an-internal-membrane-with-leak-and-reseal).
- **The feature:** `resolved_repair@1`'s damage and resealing, applied to a compartment's bounding
  patch, plus a transfer rate conditioned on the compartment's state (its pH). It needs the
  accounting, not a fitted mechanism.
- **It depends on:**
  - FR-1's compartment and FR-4's pH;
  - the coupling operator's routing door (D156);
  - re-expressing the injury law in the composite, a case of the old-family decision (D156).
- **Design first (D142),** as a general feature (D144).

## D162: Species-driven control factors (FR-6) are logged as addressed by the accepted coupling design

2026-11-14. The user supplied the request (FR-6), at the requester's priority 2, logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-6--species-driven-control-factors).
- **The general request is addressed by the accepted inventory-coupling design** (D155, D156), with
  no code yet.
- **Three narrower items are recorded as consumer registrations:**
  - the channel target, in the coupling operator's milestone 1;
  - the routing door to other operators' controls, with a second consumer (FR-5, FR-7);
  - the regulatory state as a cell's prior condition, through its declared initial value and
    writes.

## D163: Abundance-to-function in the composite (FR-7) is logged at priority 3

2026-11-14. The user supplied the request (FR-7), at the requester's priority 3 ("ordering, not
scope"), logged in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-7--abundance-to-function-exposed-in-the-composite).
- **The request:** when the closed loop's unit is chosen (the user's choice), the loop admits a
  species-driven production rate (the coupling operator's routing door), and a factor whose source
  is a population abundance (a source-semantics door of the same operator).
- **Most of its part (b)** is the coupling operator's channel target, in milestone 1.

## D164: A qualified long-duration mode (FR-8) is logged at priority 2

2026-11-14. The user supplied the request (FR-8), at the requester's priority 2, logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-8--a-qualified-long-duration-mode).
- **The request:** keep the quasi-steady or multirate mode on the path. Its acceptance case is to
  include an intervention applied during the slow phase. This is added to the compute-limits
  gate's long-time deliverable.
- **The gap recorded with it:** no composite operator has a long-time path (the coarse modes cover
  @1 to @3). A design note is needed, for which the requester's benchmark specification is an
  input.

## D165: The 7-species cap rises to 16 (FR-9), as a D148 change

2026-11-14. The user supplied the request (FR-9), logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-9--raise-the-7-species-cap). The cap counts every
species, ions included, so it binds on the requester's first world. The W4 probe measured 16 safe in
every composition D150 and D152 admit.
- **The lead's decision:** raise `MAX_SPECIES` to 16 now, as a D148 in-place change to
  `species_common`, with the four criteria and the stop rule first, a tier-1 guard world of 8 or
  more species, and the refusal tests and documents updated.
- **What stays the same:**
  - D150's claim 3 stays reported.
  - Worlds above 7 species are outside D150's judged scope until a protocol covers them.
  - Above 16 needs another probe.

**Amended 2026-11-15, the user:** "so we should increase that limit as we need!"
- The cap is raised whenever a consumer needs more species. Each raise:
  - is a D148 change;
  - comes with a guard world at the new size;
  - measures the memory and step cost.
- D172's restructure makes every species sum one explicit order, on host and device, in the same
  round that consolidates species identity. A raise then needs only that guard and the cost
  measurement, not a new summation-order probe (the lead's implementation).

## D166: A scheduled bath composition in the composite (FR-10) is logged at priority 2

2026-11-14. The user supplied the request (FR-10), the last of the block, at the requester's
priority 2 ("small"). It is logged in
[FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-10--a-dose-schedule-scheduled-bath-composition-in-the-pump-family).
- **The feature:** a held bath's composition changes on the dt grid in the composite. The older
  family's explicit ideal-reservoir law, with dose, compensating charge and external work, exists
  and is re-expressed as a composite operator.
- **Its consumers:** this study's doses, E07-v2's osmotic step and FR-4's pH step.
- **Design first (D142),** as a general feature (D144).

## D167: The feature-request order and the staged move of old-family physics are adopted

2026-11-14, user decision: "lets continue and use all the agents and priorities the new feature
request in the order you suggtest". This answers the lead's proposed order for FR-1 to FR-10 and its
parity plan (option (b) of the architecture report).
- **The feature-request order:**
  1. FR-9, the species cap to 16, now;
  2. FR-1's design note, then FR-10's;
  3. FR-3's design alongside;
  4. FR-4, with the shared energy-pool design, which also serves FR-2;
  5. then FR-5;
  6. FR-8's long-time design note after the GH200 numbers.
  - FR-6 and FR-7 are registered consumers of the coupling operator's doors.
- **The staged move of old-family physics** (option (b)): move each capability into the composite
  when a consumer needs it, and freeze the old family as a reference once it is covered.
  - The order: the channel library (through Track E, its start set by the conduction probe's
    verdict); bath doses (FR-10); energy pools (FR-2, FR-4); calcium handling, with excitable
    tissue; repair (FR-5); tissue removal (E15); mitochondria, when needed.
  - It is not a wholesale migration, and the registry covers the composite only.
- **Agents.** All six slots are used, on disjoint files.

## D168: G2-Q1's Q7 on the L4: a deterministic setting first, then a tolerance item if needed

2026-11-14, user decision ("lets go") on the lead's recommendation, after the advisor's review.
Q7, replacement with no events bitwise equal to `@3` on the 825-node tissue, failed in the L4 judged
run C. Development runs show that `@3` against itself already differs on the L4 at 825 nodes, up to
1.6e-11 relative, and the replacement's scatter matches it.
- **First,** in the next L4 gap after hold segment 3 (about 5 min), test whether this jaxlib has a
  deterministic GPU execution setting under which `@3` repeats bitwise at 825 nodes across separate
  processes.
  - If it does, Q7 is judged as registered under that setting, and the setting carries to GH200.
  - It is never applied to the hold, whose snapshots check the XLA flags.
- **If not,** a tolerance-based Q7 as a new item, labelled weaker evidence, registered after
  attribution, with a judge change. It needs:
  - repeats in separate processes, with all pairs;
  - per-field scales;
  - residual diagnostics judged against their own bounds;
  - a planted wrapper effect of registered size as a judged control that must fail.

  The user allows this allowance in place of bitwise equality (D148's last clause, by analogy).
- **The record:** Q7 stays a failed item of C until one of these settles it. The composition gate's
  GPU condition is met for W1, W2 and G2's Q1–Q6, and open for Q7.

## D169: The FR-1, FR-10 and FR-3 design notes are accepted

2026-11-14. The lead reviewed all three with the advisor, in rounds that each ended in a probe or a
code check. The notes are [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md),
[BATH_SCHEDULE_DESIGN.md](BATH_SCHEDULE_DESIGN.md) and
[SITE_OCCUPANCY_DESIGN.md](SITE_OCCUPANCY_DESIGN.md).
- **FR-1, the closed compartment.**
  - The compartment is a declared @3 outside node owned by a cell, a free node of the capacitor
    solve. Transfer is D150's exchange, unchanged.
  - Version 1 is neutral and silent, with criteria S1–S5 fixed before milestone 1. S5: the
    declaration changes no program.
  - The declaration's home is a host-only admission in the contract: "today's clause, or every
    owned field is an accepted write". It is a strict superset, an addition under D148.
  - Its protocol is exchange's first judged acceptance.
  - Probe P2 belongs to milestone 1. P1, the charged bounding patch, goes with the D148 bound round
    that also covers finding 3. P3 waits for the door for topologies without a held bath.
- **FR-10, the bath schedule.**
  - The dose and its work are the operator's own records, and the reconciliation term is the
    operator's own ledger term (confirmed in code).
  - Net-charged steps are refused.
  - A dose from nothing is a known limit, extending D150's resolved-start ruling. It is refused in
    species-only worlds and unseen in mixed ones (probe 1). A staircase probe is requested.
  - Door S (slot-scoped provision) comes early, as a general contract feature. D152's conflict with
    the schedule is nominal. *Amended by D174:* door S also covers the runtime merge onto the
    accumulated view, so it is not host-only, and it joins D172's round.
- **FR-3, the site occupancy.**
  - It is a new operator, `site_occupancy@1`, owning its populations and providing no field input.
  - It uses D152's unsplit SSPRK(3,3) with the per-route hybrid. The palindrome was measured and
    rejected: it biases steady uptake, the guard's own quantity.
  - α is static in version 1.
  - The day-one guard is judged against an independent integration of the full binding kinetics,
    with the saturable sink as convergence in ε on the reference side.
  - The trace refusal is a declared `trace_mM` per ligand, checked against 10⁻⁶ K_d. The rates are
    a labelled bracket until sourced.
- **The first admissible delivery world** is recorded under FR-1 in FEATURE_REQUESTS.md.
- **The code order** (D167): FR-10, then FR-1, then FR-3, each behind its milestones and the
  independent references.

## D170: Track E's design note accepted narrowly, for M1 and M2 on @3

2026-11-14. The lead reviewed [EXCITABLE_TISSUE_DESIGN.md](EXCITABLE_TISSUE_DESIGN.md) together
with the probe records in [the evidence folder](/mnt/workspaces/Cells/excitable-tissue-20261114-01/HANDOFF.md).

**Correction (the same evening).** The ruling was written and landed before the advisor saw it,
though this record first said it was reviewed with the advisor. The advisor then reviewed it,
confirmed it, and corrected one other statement here: which comparisons were blind (below).

**What failed.** The note's acceptance was conditional on one cheap probe. Probe 2 at 0.05 F/m²
failed S1 as registered: every perturbed segment blocked before cell 24. Its registered rule
says the verdict does not stand on that probe.

**What the acceptance rests on: amendment 4.** It is a second, post-hoc probe, written before its
runs, at candidate A: c_m 0.01 F/m² (1 µF/cm²), with NaV1.2 1e-6, Kir2.1 1e-8 and Kv1.5 3e-7 m/s.
- **S1–S4 were met:**
  - segment delays of 1.08–2.02 times the control, and block at combined 0.02 and 0.01;
  - outcomes identical at 5 and 2.5 µs;
  - energy residual at most 2.1e-4, against a limit of 2e-3.
- **The lead checked the records.**
  - A's conduction velocity comes from cells 13–26, all activated after the stimulus ended. The
    delay per cell is steady at about 0.121 ms, and interior peaks stay near +40 mV.
  - A's +56.65 mV is the chain's end cell, which has one neighbour. The isolated cell peaks at
    +56.0 mV.
- **The independent reference agrees.** Its junction voltages were blind: they were recorded
  before it read the engine's. Its peak was not blind, since the lead had given it the engine's
  +56.65 mV (Radau, rtol 1e-10, 40 cells, s = 1000;
  [comparison](/mnt/workspaces/Cells/independent-references-20261114-01/block-site-A/COMPARISON.md)).
  - At the entry junction it gives 106.012 mV at r = 0.02 and 118.079 mV at r = 0.01, against
    the engine's 106 and 118.1.
  - The largest V is +56.655 mV, at the end cell.
  - Below s·r_gj = 10 the combined arm crosses 120 mV between 10 and 7.
  - In the coupling-only arm (full sodium) the wave crosses the segment and fails at its exit
    junction. The largest segment junction voltage there is 113.4 mV at s·r_gj = 20 and 120.6 mV
    at 10, which is over the 120 mV domain.
  - So 10 is not safe. At 20 the margins are 6.6 mV (coupling-only) and 14 mV (combined).

**Rulings.**
1. **The generic cell is A,** by the registered rule ("A, or B if A fails") applied to amendment
   3's text.
   - The driver's domain record names B, through C1's after-the-stimulus clause, which that text
     lacks.
   - A dated addendum beside the record says so. The record is not regenerated.
2. **The scope is M1 and M2 on @3.** M3's grid is registered only after M1's first development
   runs:
   - the junction voltage at block sites on the sheet, at the s M3 will use;
   - the block threshold between r = 0.5 and 0.02, coupling-only included;
   - the peaks at lightly loaded cells (sheet edges and corners, the last cell before a block,
     collision sites) against +60 mV.
3. **The floor s·r_gj ≥ 20 is provisional.** It comes from chains at s = 1000 only. The
   independent reference supports it there, and shows 10 is unsafe in the coupling-only arm. If
   the sheet's block sites need values below it, `junction_ungated@1` becomes an M3
   prerequisite, not an M4 one.
4. **The fallback is pre-registered:** B if A is refused on the sheet in M1. B's segment run is
   done in M1, so the fallback has evidence.
5. **The importer** (open item 2):
   - it carries the effective availability frozen at import time, with the factor's source
     recorded;
   - it refuses water's volumes until the assay's identity takes water;
   - it refuses at definition time any junction below the floor, closed ones and those set by
     Track R's factor included. @3 checks the junction domain whatever the availability.
6. **The qualification's tolerances** come in M1's PROPOSED protocol, from development runs, with
   D150's and MG0c's lessons.
   - The probe driver may become the development driver once its step ladder includes its own
     cap and probe 1's C4 and C5 measurement fixes are made.
   - The judge is separate code that reads records.
7. **GH200 time** comes when re-entry becomes a target (M5).
8. **`junction_ungated@1`** joins the list for the inner-model (@4) design note, which the lead
   commissions ([CURRENT_PLAN](CURRENT_PLAN.md)).

**Track E's independent references** (`validation/excitable/`) are being written by the
references agent from the appendix at 99fddc35. It computes block-site junction voltages
independently, including below s·r_gj = 10, where the engine's junction law refuses.

## D171: The subagent cap rises to seven

2026-11-14, the user: "lets have the cap to 7". At most seven subagents work on disjoint files
under the lead (AGENTS.md); D155 had set six. The seventh slot came from the user's request for
a Syn3A minimal-cell agent (docs/SOTA_SYN3A.md, the user's brief) while all six were in use. The
inner-model (@4) design note's agent, paused to keep within six, resumes. Memory per detached
unit, `--oom-first`, and one GPU process at a time are unchanged.

## D172: One inner model, made modular in place (the user)

2026-11-14, the user, after the lead set out three routes for the requests to change @3
(a fork per feature; @3 changed in place; a new @4 beside a frozen @3, which the lead
recommended): "lets just have one model for now, we don't need backwards compatbility at this
early stage", then "but lets keep the core design we do modular".

**The route.**
- There is one inner model. It is restructured in place into a modular design: laws, junction
  laws, transporters, fuel and implicit solvers become declarations, traced only where a definition
  declares them.
- No second inner ID is kept beside @3.
- Old compiled programs and old checkpoints need not be reproduced by new code. Old evidence stays
  reproducible from its frozen snapshots and tags.
- This amends D143's single named inner model and D147's new-ID rule, for the inner model only.

**The lead's implementation, reviewed with the advisor on 14 November.** This is not the user's
wording.
- **A results gate replaces program identity for the restructure.** "No backwards compatibility"
  drops old programs, not qualified results.
  - Existing worlds' CPU outputs stay unchanged, bitwise or at a stated rounding.
  - Registered protocols are re-run from a new snapshot.
  - A planted change must fail the gate.
- **The design note decides, by a probe,** whether @3's five laws stay one group (probably bitwise)
  or become per-law modules (cleaner, perhaps at rounding). It also decides the label (keep
  `resolved_pump_tissue@3` or rename once), and whether the L4 variants' terms need re-measuring.
- **Order.**
  - The restructure lands as one batched round at a quiet point, with main tagged just before.
  - It lands after MG0c and Track R's qualification are judged.
  - Track E's M2 is judged wholly before or wholly after it.
  - In-flight `src/` branches re-gate after it.
- **Still open:** the fuel design, which may come to the user. Syn3A's metabolism needs reactions
  that can make and spend fuel.

## D173: Syn3A becomes the minimal-cell track; no contact with authors

2026-11-14, the user, after the advisor reviewed the options from the Syn3A audit
([SYN3A_MINIMAL_CELL_TRACK.md](SYN3A_MINIMAL_CELL_TRACK.md)): "go on as you suggest but no
contacting the authors and we will search for the missing data also help if needed lets go".

- **Adopted as a track,** and run beside the current work. It does not displace FR-4 and FR-5,
  which the requester labels blocking. Its engine features join D172's single restructure round.
- **The first milestone is fixed after:**
  - probe P0, a capability probe: a vesicle without channels or pumps under water@1, started from
    the stepped state, with a scale check of the ledger floors and step bounds;
  - the Frallicciardi 2022 audit (CC BY): numeric traces, size distributions, the signal model, and
    other conditions on the same membrane;
  - a check whether D150's exchange already acts as gradient-driven permeation, which may leave
    only water seeing neutral molecules as missing.
- **Recorded caution** (the advisor): the proposed first milestone uses protein-free synthetic
  vesicles, so it tests membrane physics, not Syn3A. The living-cell lipid-diet data come from a
  tagged strain, and their authors attribute the effects to lipid–protein interactions.
- **Never contact authors.** The missing Pelletier 2021 division data are searched for in public
  sources only, by the user's side and the agent.
- **Agreed:** values from non-commercial papers are cited, but their tables are never copied into
  the repository. The 4D model's outputs come at the metabolism stage (D138).
- **Licences of the data (the user, 15 November 2026):** "lets use them for analysis but ours is
  a commerical project bvut open source".
  - Datasets under non-commercial licences are used for analysis only. These are Maier 2011,
    Wodke 2013, Chen 2016 and the Presutti 2026 article.
  - Nothing from them, whether tables, traces or plots, is committed or redistributed.
  - Any judged or published result rests on permissively licensed data where possible, and the
    note flags every dependence on non-commercial data.
- ***M. pneumoniae* is audited soon,** amended the same evening by the user: "But also M. pneumoniae
  soon for validation if we have more real public data there". The Syn3A agent audits it next,
  for real measured public data to validate against, and says whether it should lead any stage.

## D174: The external architecture review adopted into D172; the architecture document first

2026-11-15. The user forwarded an external review of the D172 direction and asked: "from
external reviewers, you review then get adviser then act on this", then "update the arhtecture doc
before changing any code" and "afte3r review".

**What the lead did.**
- Reviewed it and checked three of its claims in the code:
  - the adapter's view replaces whole fields per provider;
  - exchange books signed work with no heat;
  - the tier gate compares exit codes and failed and error counts only.
- Adopted it after reviewing it with the advisor.
- Wrote its requirements into [ARCHITECTURE.md](ARCHITECTURE.md), section "The modular core". Each
  requirement there is marked holds today, target for D172, or open.

**The rule:** no review-driven code, and no `src/` or `scripts/` landing, until that section is on
main. Approved branch work continues.

**Consequences, recorded there:**
- Per-law dispatch replaces the option of keeping @3's five laws as one group.
- A new passive permeation law is expected, since exchange is a driven route.
- Door S includes the runtime merge onto the accumulated view and joins D172's round. This amends
  D169.
- The fuel requirement is fixed. Its representation is open.
- The reviewers' text is kept outside the public repository.

**Amended 2026-11-15.** The user forwarded a second review, of 6f76b8d: "from adviser on the latest
plan, get also your adviser on it and make changes as needed". With the advisor, five
clarifications were adopted into the section:
- The GPU guarantees are targets with an implementation audit pending, not open. Per-law dispatch
  means build-time selection.
- The status legend now separates D172's landing scope from later consumer milestones.
- Evolution roles are kept apart from conservation relationships, and counters declare what they
  count.
- The passive test runs on a closed two-compartment system, with reservoir work counted in
  held-bath worlds.
- Two present-tense examples were corrected.

## D175: Levels of detail as declared representations

2026-11-15. The user forwarded guidance approving a concise "Levels of detail" section, with six
refinements, and asked: "review and also get a review from your adviser then update the arch docs".
The lead adopted it after reviewing it with the advisor. It is now in
[ARCHITECTURE.md](ARCHITECTURE.md#levels-of-detail), linked from both multiscale documents.

**What it sets.**
- Representations of a mechanism are declared per mechanism and per question; there is no global
  detail level.
- Compatibility is defined at the physical interface. Each representation closes its own ledgers,
  and the transient difference between them belongs to the declared error budget.
- One representation of a pathway per scope, enforced by a declared key.
- Four optional fields, only on laws that stand in for something. They are a reserved interface in
  D172's law design.
- The representation is kept separate from the numerical method.
- Assignments are fixed first.
- The reduction is real in the kernels, not a runtime flag.
- Numerical, reduction and biological validation are kept separate. The envelope is declared
  before the comparison, and one case outside it must fail.

**Its first consumer** follows D174's fuel case and waits for the fuel representation. The
guidance's text is kept outside the public repository.

## D176: The modular rework proceeds, with FR-4 and FR-5 as its priority consumers

2026-11-15. The user forwarded their external adviser's decisions on the inner-model note, and asked
to review them with the advisor and proceed with six agents "in the most efficent way". The lead
adopted them after reviewing them with the advisor. The note is
[INNER_MODEL_V4_DESIGN.md](INNER_MODEL_V4_DESIGN.md).

**The decisions.**
1. **Fuel is F2.**
   - ATP, ADP and Pi are shared inventory species, used by reactions and pumps.
   - One authority for amounts and standard chemical potentials.
   - The "moved by the step" admission fix is included.
2. **FR-4's first case uses maintained fuel,** with its scope labelled. The finite-fuel acceptance
   stays separate: reaction → shared ATP/ADP/Pi → pump, with depletion and recovery against an
   independent reference.
3. **Summation keeps a controlled deterministic policy.** Before it is frozen, one bounded
   comparison is made between serial left folds and an explicitly ordered hierarchical
   alternative at representative species counts. It reports compilation, checked-window runtime,
   memory, accuracy and ledger residuals. Sensitive charge and energy quantities are evaluated
   consistently.
4. **Qualification:** the full affected registered protocols are re-run on the integrated
   candidate, E07 included. Targeted development checks come first, and the expensive final gate is
   not run repeatedly.
5. **The name stays `resolved_pump_tissue@3`,** with the snapshot, tag and results-gate provenance.
6. **Track E:** bounded slowing and arrangement work follows the required qualification, without
   delaying FR-4 and FR-5. `junction_ungated@1` is follow-on physics: it removes a domain
   restriction, and does not by itself produce block. Before a judged M3, loss of activation inside
   the cluster is separated from failure of propagation beyond it.
7. **Syn3A:** the licence policy stands. Numerical vesicle, pH and fuel qualification can proceed.
   The Wodke-based Stage 4a stays a separate decision.
8. **Lifecycle M2:** its first milestone is state-triggered timing on a predeclared daughter tree,
   with fixed fractions and anchors. It is queued behind the core and the priority features unless
   it can proceed independently.

**Corrections to the design, now in force.**
- **The dependency table** is refreshed against main.
- **Bath → uptake → owned compartment → reaction** is a real scoped-composition acceptance case,
  reusing the compartment identity map.
- **Charged buffering** is an FR-4 dependency with an owner and an acceptance criterion, since
  today's reactions parser refuses charged species.
- **The charged-patch feasibility test runs early.**
- **Scoped-composition order independence** is narrowed: disjoint provider writes are invariant
  under reordering, while overlapping contributions have a fixed evaluation order, and the
  numerical split order is preserved.
- **Reference reads** of immutable anchors are told apart from assumptions that a physical field is
  unchanged.
- **G1 and G3 are aligned:** exact contract tests, plus scientific negative controls whose effects
  exceed the declared budget.
- **A7's gate manifest** is built from the import closure of the changed files, not from the new
  identifiers.

**The lead's implementation, with the advisor.**
- **Branching:** main is tagged `d172-base-2026-11-15`. Until the single landing, `src/` lands only
  on the local integration branch `integration-d172`, while main takes docs, validation and tests.
- **Owners split by file.** One integration owner holds the contract, the composite, the adapter,
  door S, every merge and the tier gates.
- **Commit order:** declarations, dispatch, operator adaptation and door S are checked bitwise
  against outputs saved at the tag. The summation change lands last, alone, at a declared
  tolerance.
- **Privacy:** acceptance worlds stay generic.

## D177: A downstream user's requests: a matched-arm export, retained states as species, the dose world's controls after the round, FR-7 registered

2026-11-15. A downstream user of Cells sent four requests. A review covered them (read-only, its
report kept in the lead's private workspace), and the user decided:
- **The coupling operator's matched-arm export is approved as a planned follow-up.**
  - A dedicated agent writes a neutrally named validation driver on main. It runs the four
    matched arms, 16 definitions, from a clean snapshot of main: the definitions, traces, the
    independent references' traces, restarts and windows, and duration probes at 0.125 ms.
  - It runs `resolved_pump_composite@1`, `resolved_pump_tissue@3`,
    `scheduled_species_turnover@1` and `species_regulated_availability@1`.
  - **What it is not:** an engine change, or a registered or judged protocol. Its provenance is
    the Git revision and the frozen snapshot, with no attestation layer.
- **A retained processing state is modelled as distinct species, with D152 reactions at the
  retained node.** No new engine state is added. A per-compartment content state (a declared
  multi-state cargo) waits for a second consumer (D144).
- **The dose world's release route, production stage and zero-rate controls come after D172's
  integrated landing,** not in the round.
- **FR-7 is registered as a consumer of the coupling operator's routing and abundance-source
  doors,** with removal and surface insertion under FR-2. Its design note follows the round, and the
  choice of the closed loop's unit stays the user's.

## D178: Membrane-placement predictions read from UniProt and WormBase ParaSite may stay

2026-11-15. The visualizer's protein records include membrane-placement predictions (which side of
the membrane each protein sits on) for about 17,500 planarian proteins and some *M. pneumoniae*
ones. They were read from UniProt and WormBase ParaSite. Those databases computed them with programs
licensed for academic use: TMHMM, SignalP and Phobius, plus PROSITE's rules for about 200
placements. The visualizer classed these values as non-commercial under D173.
- **The user's ruling, asked before the visualizer's second merge into main:** these values may
  stay. The databases' published terms are treated as governing.
- **The visualizer reclassifies them,** keeps its notes on where each value came from, and its
  licence test still lists every dependence by species.
- **Scope, widened the same day by the user:**
  - **Every species:** human, planarian, Syn3A, *M. pneumoniae* and *E. coli*.
  - **The terms:** a placement value stands on the terms of the database it was read from, and the
    record names and counts the tool behind it.
  - **Where the user said so:** to the visualizer, as one rule for every species with the numbers
    for each; and to the lead, for *E. coli* ("Yes, extend D178").
  - Anything else, a source with no stated terms included, stays under D173's rule: nothing from
    non-commercially licensed or unlicensed data is committed or redistributed.

## D179: The FEP track's decisions: on hold, E. coli as data only, approvals delegated for this track

2026-11-15. The user answered the decisions listed in [the FEP proposal](FEP_TRACK_PROPOSAL.md).
Items 3 and 4 the user left to the lead and the advisor ("You and adviser decide").
- **The track stays on hold until more of the inner model exists.** D145's gene-regulation hold also
  stays.
- **E. coli is added as a data-only organism,** for the track's Stage 1a (chemotaxis in a
  well-mixed cell). There is no engine organism definition and no run.
  - The visualizer adds it as a species.
  - Whether D178's ruling extends to its tool-derived placements is the user's to decide. Those
    values are held until then.
- **Published reference models (D138), for this track only:** the per-paper approvals are delegated
  to the lead with the advisor.
  - None is approved now.
  - Each paper is approved when Stage 1a opens, after a full-text read and a licence check, and its
    model runs out of process.
  - Other D138 approvals stay the user's.
- **The comparison harness is approved in principle as tooling.** It is built only with Stage 1a's
  first engine arm, and its planted tests and its pair with identical dynamics come first.
- **The temporal comparison over about 4 s is accepted as analysis only,** because no permissively
  licensed data covers it.

## D180: External modules are a first-class architectural requirement; Cells stays MIT

2026-11-15. The user directed that Cells stays MIT, aiming at broad adoption. People should be able
to use, extend and compose Cells from independently maintained packages, and the project extends
itself through the same interfaces. An external component meets the same validation, composition,
execution and accounting contracts as a built-in one.
- **The design is proposed** in [MODULE_SYSTEM_DESIGN.md](MODULE_SYSTEM_DESIGN.md), with a
  proposed ARCHITECTURE section, "External modules". It was reviewed with the advisor.
  - **The path:** components are registered explicitly into a registry scoped to one model build,
    then resolved, validated, assembled, compiled and run.
  - **Stages, staged by real consumers:**
    1. one external law in a separately installed package;
    2. a stateful mechanism and a reusable composition, each used twice;
    3. a reduced and detailed pair.
- **D172's round takes only four seam constraints,** which the core owner confirmed cost nothing
  extra:
  - kinds reach core through a build-scoped lookup;
  - new IDs are namespaced;
  - the canonical order is the sorted namespaced ID;
  - a registered but undeclared kind changes nothing.
- **Stage 1 starts after the integrated landing.**
- **The design's §6 decisions are the user's:** provenance for modules, D144 with modules,
  qualifying outside modules, where the example lives, and what a module PR is.

## D181: The round's end game: E07-v1's re-run held, and the L4 block run under the deterministic flag

2026-11-15. Both decisions concern D172's end game, after the summation change (A7) lands.
- **The user put E07-v1's re-run on hold.** E07-v1 is judged, and its successor E07-v2 is still a
  proposal.
  - Its worlds are covered by the results gate instead: the baseline's protocol-e07 set, compared
    bitwise at the integrated candidate and at A7's declared tolerance after it.
  - It is re-run only if that comparison shows physical state moving beyond the tolerance, or if a
    later experiment needs the runs.
  - This changes D176's rule that A7 re-runs every affected registered protocol, for E07-v1 only.
- **The lead ruled, with the advisor, that the 13-run L4 block runs under the deterministic flag**
  (`--xla_gpu_deterministic_ops=true`), as a declared measurement mode.
  - The backend term is remeasured under the flag, and the run-to-run term is exactly 0.
  - One confirming repeat per structure must be bitwise; a repeat that is not stops the block.
  - Tolerances are unchanged.
  - Q7's plain-against-flagged difference, about 1.8e-11 relative, bridges to the registered
    unflagged mode.
  - The amendment is registered before the block's first run.

## D182: A7's summation order: a serial left fold in declared species order, with barriers at every listed site

2026-11-16. This settles D176's A7 for D172's round. It is the round's last program change, c0 → c1
in the end game.
- **The order.** Every species summation site the operators listed
  (`operators/summation/SITES.md`) uses the shared helper's serial left fold in declared species
  order, with an optimisation barrier at each site. That is the configuration rehearsed on all
  113 worlds.
  - **The rehearsed list** is the 37 single species-sum sites and the 13 calls on 10 split lines,
    where the species are folded first and the rest reduced as before.
  - **The 7 row-sum folds** of the turnover operator keep their existing fold arithmetic, without
    the barrier. The rehearsal never touched them, and their ledgers have no tolerance pattern.
  - **The 122 sums over entities** go through a named helper that is the same reduction as before.
    It exists for the static test, which refuses any summation that bypasses the helpers.
  - **As built** (a7-summation 32d6b56f, 16 November):
    - crossrev against its parent keeps constants and bindings identical in all eight sets, while
      every program text differs;
    - the results gate under the frozen tolerance file holds 113 of 113 worlds, with physical
      fields bitwise;
    - its saves are bitwise identical to the rehearsal's in all 113 worlds
      (`core/c10/a7/g1-32d6b56f/`).
- **Why barriers everywhere.** The L4 column (`operators/summation/out/gpu/NOTE.md`, 16 November)
  found:
  - the barrier costs nothing at 16 species on the 825-node world, within noise in window time
    and compile;
  - at 150 species the barrier is cheaper than the plain fold, at about +4% step time against
    today's code where the plain fold costs +10%. The tree would cost +34% step time.
  - Host and GPU agree bitwise for the fold, with or without the barrier, at 8 to 150 species,
    the inexact products included. Today's reduction does not.
- **What it changes.** The CPU rehearsal on all 113 worlds kept physical fields bitwise. Only
  ledger and diagnostic arrays moved, at rounding.
  - The final tolerance file (`a7-g1-tolerance.json`, 862 patterns, three post-data floors named
    in it) holds all 113 worlds. It is the results gate's file at c1, frozen in the end game.
  - At c1, constants and bindings must be identical to c0 while program texts may differ. The
    results gate at this tolerance is A7's semantic check.
- **Open, not blocking.** Whole 825-node runs on the L4 differ between every pair of arms at
  2–5e-16 of each field's scale, without the deterministic flag. With one run per arm this cannot
  be separated from run-to-run variation, most likely the order of atomic scatter-adds. G1 runs
  on the CPU, and D148 excludes GPUs from bitwise claims. Two repeats of today's code (about
  3 min of L4 time) settle it in a later gap.
- **The tree** stays the option if species counts go well past 150.

## D183: The human cardiac law set is brought forward

2026-11-16. The user was asked whether FR-11's human loop should start as a paced generic excitable
cell, labelled "not a human cardiomyocyte model", while Track E's human cardiac laws waited for its
milestones M4 and M5. The user decided: "let's bring the human cardiac laws forward", noting that the
machine now has more CPUs.
- **What moves.** Track E's human ventricular law set ([excitable tissue design](EXCITABLE_TISSUE_DESIGN.md)
  §3.3, §7, and M4 and M5 in §11) starts now as its own lane on the inner model that D172 lands,
  instead of waiting for M1–M3. M1–M3 on the generic cell are unchanged.
- **FR-11's human loop** becomes a paced human ventricular cell built on that law set, with no
  generic stand-in, and it waits for those laws. *Correction (D184):* "no generic stand-in" was the
  lead's reading of the user's answer; D184 keeps it under the user's delegation. The planarian loop stays first. This replaces the
  generic paced cell in the FR-11 design that the lead ruled earlier the same day.
- **Design first (D142).** The lane's first deliverable is a design note with options for the
  user. It covers:
  - the source of equations and parameters: O'Hara–Rudy 2011, its ToR-ORd successor, or ten
    Tusscher–Panfilov 2006;
  - the cell types, the form of the sodium current, and the temperature;
  - the verification.

  No engine code is written until the user chooses. The prerequisites stay as Track E lists them:
  calcium handling moved under D167, the ungated junction law, and the step condition of §4.2.
- **Unchanged:**
  - each law is general and named by its mechanism, not by a protein or for one experiment (D144);
  - a whole-cell action-potential comparison against a published model needs the user's approval
    (D138, D151), and the note asks for it;
  - external simulators run only out of process against saved outputs, and every parameter is
    cited.

## D184: The human cardiac law set's choices, and the whole-cell comparison approved for O'Hara–Rudy 2011

2026-11-16. The lane's design note put its choices to the user. It is
`docs/HUMAN_CARDIAC_LAWS_DESIGN.md`, proposed, on branch `cardiac-laws`, and reaches main after D172's
landing. The user answered: "on the other decisions get adviser with you then its go from me".
So the user approved the lead's recommendations as presented, after the advisor's review:
1. **The source:** O'Hara–Rudy 2011's endocardial cell (ORd).
   - Its equations and tables are open (CC BY), with a published correction and documented errors,
     and its steady state is published.
   - It has no Markov form.
   - Its known weakness, slow conduction in tissue, matters only for the tissue milestone.
2. **Cell types:** the endocardial cell first; epicardial and M cells later as parameter sets.
3. **The sodium current:** Hodgkin–Huxley gates, with a Markov form later as a general kind.
4. **Temperature:** 310 K.
5. **D138 and D151's approval, for O'Hara–Rudy 2011 only.** H4's conduction remedies, which come from
   other papers, are not covered.
   - **(A) An independent whole-cell reference,** written from the paper, Text S1 and PLOS's
     correction by an agent who reads neither the engine nor the authors' code. It has two arms: as
     published, and with the note's listed departures. Any later departure is reported to the user
     before the judged run.
   - **(B) The published model, run unmodified and out of process,** keeping only saved outputs.
     - One plain attempt is made at the authors' own code (BSD-style notice).
     - If that meets any wall (an account, JavaScript, a guard), the lane stops trying and uses
       Myokit (BSD 3-Clause) in its own environment, with the model repository's CellML encoding,
       used by reference and never committed. No workaround.
   - **(C) The comparison over one beat at 1 Hz:**
     - the engine against the declared arm, judged at tolerances registered before the run;
     - the two references against each other, judged;
     - the engine against the published model, reported and not judged, with each difference
       attributed to a declared change.
6. **D167's expectation, for the human set only.** No catalogue channel law can carry ORd's gating, so
   the human set's channel laws are new. The catalogue's laws stay as D167's parity references, and
   the mouse's expectation is unchanged.
7. **FR-11's human loop stays as D183 records it:** no generic stand-in. The viewer has no human loop
   until the human cell is ready, about 20–30 working days after the landing by the note's estimate.
   - A labelled interim generic cell remains a one-line amendment.
   - This corrects D183's record: "no generic stand-in" was the lead's reading of the user's answer,
     and this delegation keeps it.

**The 2004 model code.**
- **What happened:** a research subagent of the lane downloaded the authors' 2004 (TNNP04) C++ code
  after the worktree guard had refused the command. Their page offers the code publicly, with no
  licence stated. The permission classifier separately blocked a copy of the
  paywalled 2004 paper, which was never obtained. The user was told.
- **Under this delegation:** every statement in the note that can be traced to that code is
  removed, then the files are deleted, and the note's sources record that the code was fetched and
  discarded.
- **From now on,** every brief says that when a guard, classifier or permission check refuses an
  action, the agent stops and reports. It never rephrases or reroutes the action, and the same
  applies to the subagents it starts.

**Not covered by this delegation:**
- the note's questions for the lead and the core owner (§9.2), ruled after the landing. Opening
  subspace calcium, closed in version 1 by the inner-model note, goes to the user if it changes an
  approved closure;
- the landing itself, which keeps its own heads-up.

## D185: The module system's five decisions, and contributions by pull request

2026-11-16. The user's direction: "yes modular and easy for others to add PRs with new modules / laws".
The lead listed the five defaults of the [module design](MODULE_SYSTEM_DESIGN.md)'s §6, with two
additions, and asked the user to confirm them. The user replied: "sounds good".
1. **A module PR (§6.5): in-tree contributed modules first.**
   - Each module has its own folder and namespace, an MIT licence and a named owner, and is gated
     by the conformance kit and the tiers.
   - Core physics PRs continue under D142, D144 and the full tier gate.
   - Out-of-tree modules, listed by a docs PR with their conformance record, may follow.
2. **Qualifying outside modules (§6.3): a conformance kit shipped in Cells.**
   - The contributor runs it before opening the PR. It runs the declaration and error checks, I1–I4,
     ledger closure with planted controls, executable reuse, a fresh-process restart, CPU/GPU
     agreement and the matrix report, and it scans for reference-simulator imports.
   - It records both identities and each claim separately.
   - *The lead's reading:* a pass means the kit's checks passed. It does not qualify the science,
     which still needs a registered protocol.
   - Still open from §6.3: whether the project lists the modules that pass.
3. **D144 with modules (§6.2): new physics goes into `src/cells`, as modules.**
   - The default confirmed first was (b), "modules incubate". The user then said: "So yes new
     physics go into src/cells but we have a modular architecture there right?"
   - So AGENTS.md's rule stands. Physics enters `src/cells` as modules of its structure (laws, kinds
     and operators, each declared and registered), under D144.
   - A contributed module is a PR that adds its pieces inside `src/cells`, in their own namespace.
   - Packages outside the repository can still extend Cells through the same registry. The
     project's own experiments run on physics in `src/cells`.
   - `validation/` still holds no physics.
4. **The example (§6.4): in this repository.**
   - It is a separately installable folder (for example `examples/modules/cells-example-law/`),
     installed as a wheel in tier 2, with a test that it imports only Cells' public interface.
   - It doubles as the template contributors copy.
5. **Provenance (§6.1): identity for development runs, frozen files for registered and judged runs.**
   - Development runs record each outside module's identity (§2.5), computed at run time.
   - Registered and judged runs also freeze the module's files beside Cells' snapshot, so the freeze
     tool takes a root outside the checkout.
   - There is no attestation layer.
   - AGENTS.md's provenance rule is amended to say so. Provenance for in-tree contributed modules,
     which are installed as packages, is settled in stage 1's design.

**The two additions:**
- **A declarations manifest.** The engine writes a JSON list of every registered law, operator and kind,
  with its ID, what it reads and writes, what it conserves, and its units and signs. Contributed modules
  then appear in the docs and in the viewer's laws library without hand edits.
- **A contributor guide and a pull-request template.** They say how to add a law or a module: name it by
  mechanism, cite its source, test it, and run it through the kit.

**Asked separately later:** automatic checks on GitHub for outside pull requests, because that changes the
public repository's setup.

**When:** stage 1 (one external law, registered explicitly) starts after D172's landing. The manifest and
the guide follow with it.

## D186: Numbers from open papers may be used with a citation, even when no licence is stated

2026-11-16. The user told the visualizer session: "you can use any numbers from open papers even if no
licence is decrlared". The user then confirmed it to the lead: "yes on the licence ruling". The lead
adopts the visualizer session's reading for the whole project:
- **What it covers:** numbers taken from an open paper and entered with a citation, such as parameter
  values and measured quantities, in the engine, in `validation/` and in the visualizer.
- **What it does not cover:** copying a paper's text, figures or data files into the repository.
- **Unchanged:** data under a non-commercial licence is used for analysis only and never committed
  (D173's rule for datasets).
- **It widens D178 in kind.** D178 lets membrane-placement predictions read from UniProt and WormBase
  ParaSite stay. D186 lets cited numbers from open papers stay when no licence is stated.

## D187: Testing as little as possible but enough for the science; old regression tests not kept indefinitely

2026-11-16. The user said: "we like to design for as little testing as possible but still enough no
compromizes on quality of science". The user then approved the lead's plan, which was reviewed with
the advisor: "sounds good lets go on those test plans and not keep endless old regression tests
also".

**The rules** (the lead's proposal, approved):
1. **Prove each claim once, at the cheapest level that can prove it,** such as a law against its
   reference at the kernel. Add one composed-world check per claim about composition, because the
   raw-sum bound and the cycle refusals of 16 November showed up only in composed worlds.
2. **Crossrev and the results gate carry regression only for what their worlds exercise.** Each
   landed feature adds one world to the baseline and crossrev sets, starting with the kinds set.
3. **New tests need teeth:** a planted error they must catch. The 90 s split rule applies to them,
   and a test that cannot fail is removed.
4. **Gate once per merge,** on main plus the branch. While building, run targeted files.
5. **Make long checks faster rather than skip them,** for example with device checks and faster
   harnesses.
6. **The science is never thinned.** Each claim keeps its independent reference, its planted
   control, its conservation checks and one registered judged run. No tolerance is loosened to save
   time.

**Tier 3:** each landing's final table is frozen, per test ID with its normalized error. The next run
is compared against it, instead of re-running old code to learn what was already failing.

**The audit,** after D172's landing (about 1–2 agent-days for the triage). D172's tier-3 table is the
inventory, sorted into three classes:
- **Harness limits:** fix the harness, or retire the test.
- **Stale tests:** fix with the reason the file changed, or retire. A stale pin is never fixed by
  updating the hash alone.
- **Possibly real defects in older code:** these are open findings, each with its own plan item.
  Examples are the missing `[anchor]` refusal (corrected the same evening: the 73 µs observation-time
  case, `[off_grid]`, passes; the audit traced the `[anchor]` loss to 88866b60 of 9 November, a change
  to the shared `numerics/surface_field`, so it reaches @3), the cotransport energy failure, the
  excision charge failure and the fixed-step tracing errors.

**Old regression tests that do not earn their cost are retired, not kept indefinitely.**
- This includes tests of frozen older families.
- The tree is tagged before any removal, so every retired test stays recoverable, and the frozen
  evidence is kept.
- The retire list goes to the user in one batch before the removal commit lands.
- AGENTS.md is unchanged.

## D188: The engine's source tree takes the modular layout by two scripted moves; older families go to src/cells/legacy/

2026-11-16. The user asked whether `src/cells` should be cleaned up "according to our framing so maybe
laws folder with sub folders". The user then chose: "I'm leaning towards 3. but if we can go as quick
as possible to 2. and just move files to src/legacy then that is good". The user confirmed the plan,
reviewed with the advisor: "sounds good and yes src/cells/legacy".

**The target layout** (option 2):
- `laws/`, one module per law, grouped by mechanism: `channels/`, `junctions/`, `pumps/`, `routes/`,
  `reactions/`, `transport/`;
- `kinds/`, `operators/`, `models/`, `numerics/`, `execution/`, `registry/`, `definitions/` and
  `records/`;
- `legacy/`, for the older model families.

**How it is reached:** a design note and probe (step 0), then two scripted moves.
- **Step 0.**
  - Derive the legacy list from the import graph of the active entry points, and from each
    family's consumers in the record. The list goes to the user, and it is built together with
    D187's audit inventory.
  - Run a probe in a scratch copy: move one family and one shared kernel, then check crossrev, the
    kinds pair, a continuity resume and test collection.
- **Move 1:** the older families go to `src/cells/legacy/`. Nothing outside `legacy/` imports from
  it, and the model registry's dispatch chain is refactored to keep it that way.
- **Move 2:** the modular parts go into the target folders.

**Each move** is one move map plus one import rewriter.
- A verifier checks that every changed pin equals the rewriter applied to its old content.
- **Gates per commit:**
  - the same collected test IDs;
  - crossrev and the kinds pair identical;
  - G1 at 113 of 113;
  - tiers 1+2 with 0 changed.
- Tier 3 runs once, on the final tree, against the frozen table (D187).
- Test file paths do not move.
- Open branches apply the same script to their heads before merging.

**Refactors are separate.** These belong to the core-seams pass:
- putting each law's declaration, math and citation in one module, and the law template;
- the stable import surface for contributed modules (D185);
- how a moved law names its frozen original.

**It starts** after core-next lands on main.

**Step 0 done, 17 November** (`docs/SOURCE_LAYOUT_MOVES_DESIGN.md` §13, §16 and §17):
- **The probe passed every check,** and so did a full dry run of move 1. The only red tests were
  16 sites R2 fixes and 2 AST-hash cases.
- **Before move 1:** four refactor commits.
  - R1: the legacy registration entry point.
  - R2: computed module paths.
  - R3: seven extractions.
  - R4: one pinned law's root.
- **The lead's rulings** on the note's eight items are in §17. Whether any checkpoint must cross
  move 2 is the user's.
- **Size:** move 1 is about 3.5–4.5 agent-days and move 2 about 2–3, plus about 6 hours of gates.

## D189: The four undecided families stay active, and the firm retire list is approved

2026-11-16. D187's audit and D188's step 0 left two calls for the user, put with the advisor's
review. The user: "1. agreed all four" and "2. as you suggest".

**The families (D188 step 0's legacy list).**
- Four families stay active. The modular path does not use them, but registered protocols name
  them:
  - `apical_vertex_mechanics@1`: MG1's vertex mechanics;
  - `reaction_transport@1`: MG0a's morphogen gradient;
  - `resolved_pump_tissue@1` and `@2`: the stationary analysis and the L4 physical protocols.
- The shared code of the four moves into the modular core in D188, not into `legacy/`.
- With the five families already active, 9 are active and 102 are legacy. The list is
  `scripts/legacy_inventory.py`'s at a83d8f15 (its output is in
  `/mnt/workspaces/Cells/test-audit-20261116-01/a83d8f15/inventory/`). This settles step 0's list;
  its probe follows.

**The retire list** (`docs/TEST_AUDIT_RETIRE_LIST.md`, regenerated at a83d8f15).
- **The firm list retires by its Unit column:**
  - tier 3: 15 whole files, and the listed cases of 4 more;
  - tiers 1 and 2: 43 whole files, and the listed cases of 39 more.
- **Two checks run before anything is deleted.** A row that fails either moves to the held list,
  with its reason:
  - a whole file that tests a module on the list of 42 couplings from the modular path into older
    modules;
  - a skipped case that the L4 block runs.
- **The tree is tagged first.** The tier record and tier 3's frozen record are then updated to match
  the collected tests.
- **Kept for now:** the held list and the 91 passing tier-3 files of frozen families. They are
  reviewed again once D188 has cut the 42 couplings.
- **The saving:** about 7.5 of tier 3's 29.8 core-hours per run, and 2.1 minutes per tier 1+2 gate.

**Amended on 17 November (D188's dry run):** the couplings that matter under this ruling are the 7
reached modules that import a moved one (R3 of `docs/SOURCE_LAYOUT_MOVES_DESIGN.md`), not the 42.
The 102 families' registrations become legacy, but the shared modules that the four kept families
build on stay in the core: `surface_tissue`, `surface_kinetic`, their specs, and the reached kernel
of `kinetic_finite_extracellular`. R3's keep rule also keeps `calcium_gates`, `kinetic_finite_bounds`
and `rate_junction_spec` in the core (the moves note §18). The held tier-3 files are reviewed again
after R3.

**Done on 17 November** (test-audit a676930b):
- **Retired:** 11 tier-3 and 40 tier-1/2 files, plus 23 and 788 cases. Collection fell by exactly the
  2,322 retired IDs.
- **8 firm rows moved to held,** each with its reason:
  - four tier-3 files that run a coupling target (check a);
  - three files whose code the remaining tests need;
  - three cases that pass in a checkout with Git history.
- **The saving as done:** 5.5 core-hours per tier-3 run, and 2.0 minutes per tier 1+2 gate.

## D190: BLAS is pinned to one thread, in a lean form

2026-11-16. The core found that a CPU run's bits follow its CPU allocation through OpenBLAS's thread
count (ARCHITECTURE.md, "Allocation-independent linear algebra"). Asked to approve a pin, the user
answered: "lets not go overboard here but take your adviser". The form below was chosen with the
advisor.

**What is built:** the proposal as committed in ARCHITECTURE.md.
- One small module, `core/blas_threads.py`, pins every BLAS to 1 thread. It runs at the first
  import of `cells.core`, which every computing path passes through, and again at each of the eight
  run entry points.
  - At import it sets `OPENBLAS_NUM_THREADS=1`. If numpy is already loaded, it also force-loads
    scipy's LAPACK and sets every loaded BLAS through threadpoolctl (BSD).
  - **Amended at the landing (17 November):** "at `import cells`" became "at the first import of
    `cells.core`". `src/cells/__init__.py` stays unchanged, because a held legacy law
    (`processes/charged_surface_work`) pins that file's content, and D187 forbids updating a pin
    by hand.
- **The run is refused** if, at run entry, a read-back finds any loaded BLAS not at 1 thread.
- **The run manifest records** each library's version, kernel architecture and thread count, and
  so does the results baseline's environment. The runtime identity that checkpoints compare is
  unchanged, so checkpoints written before the pin still restore.
- **Two tests,** each with a planted error.

**What is dropped:**
- a scoped pin that restores the caller's setting, with its reference count and lock. A pin that is
  never released needs no count;
- a re-check at every window. One read-back when the manifest is written covers the run, and
  AGENTS.md rules out per-call attestation.

**The cost:**
- A process that imports cells runs BLAS single-threaded throughout, including the caller's own
  numpy work.
- Multi-core CPU runs of large worlds lose the threaded per-step factorization: 21 ms of the
  825-node world's 91 ms one-core step.
- One-core runs and GPU runs are unchanged.

**The baselines:**
- G1 is unchanged.
- crossrev's two S825 bindings are renewed once.
- If a tier test with stored bit-exact values moves, it is attributed before anything is renewed.

**When:** the pin lands before D188's move 1, so the moves' gates no longer depend on the CPU
allocation. It landed on 17 November (core-pin 52dd5816). crossrev's renewed record is
`record-cda5dc82`, and with the pin the 825-node world gives the same bits on 1, 2 and 4 CPUs.

## D191: Operator composition takes one general rule (option A)

2026-11-16. The composition design (`docs/OPERATOR_COMPOSITION_DESIGN.md`) put the D147 question:
does reading a field's current value, instead of its declared value, change a law's semantics? The
user: "4. as you and adviser suggest".

**The ruling: A.** A current read keeps the law's ID, under D148's four conditions.
- Each operator declares, per field, whether it reads the current or the declared value.
- The composite resolves each read when the model is built: current if some operator of the
  composition changes the field, otherwise the declared value.
- Worlds that do not compose keep their programs bit for bit.

**What it implies:**
- **D150's registered protocol.** Q5's test asserts two version-1 refusals that A lifts: turnover
  beside water, and turnover beside insertion@1.
  - Q5's file keeps those refusals for the static-tissue scope its verdict covers.
  - A's admissions are tested in a file outside Q5's list.
  - The verdict judged at f7f0592 stands.
- **Gaps 2 and 5 land together.**
- **It is qualified numerically only,** since no judged experiment needs it yet.
- **The cost:** about 9.5–12.5 agent-days, plus 3–4 for the references. That excludes pumps on
  dividing cells (about 3 more), the furrow world, and how ions join growth.

**When:** step 3 of D194's order.

## D192: GARD: the design choices, and the comparison approved

2026-11-16. The GARD design (`docs/GARD_DESIGN.md`) proposes the engine's first origin-of-life model
family. The user: "5. as you and adviser suggest". On the comparison (D138): "6. yes to all three".

**The choices** (the note's §4):
- **Kinetics:** the exact stochastic simulation (direct method), one molecule per event. τ-leaping
  comes later, only as a qualified fast mode.
- **Assemblies:** abstract ones first, over a generic ideal-mixing phase.
- **Matrix:** dense lognormal, β = exp(−4 + 4Z), with about 100 types, as per-world data.
- **Kernel form:** both.
  - The preprint's single-event form, for the reference comparison.
  - The pair-consistent form, as the engine's passive law.
  - The first experiment measures the difference.
- **Reference experiment:** the preprint's reconstructed GARD, contract T2-02.
- **Architecture:** a stochastic family, registered as modules (D185).
- **Cost:** about 20–29 agent-days, CPU only.

**When:** step 4 of D194's order.

**The reversibility finding, as checked** (the note's §2.5; evidence in
`/mnt/workspaces/Cells/verify-gard-beard-20261116/`). An independent check by exact enumeration
found:
- **In a closed two-type world, the preprint's single-event kernel generically fails Kolmogorov's
  cycle criterion.** That kernel is the event split of the original rate law (Eq. 4 of Segrè,
  Ben-Eli and Lancet 2000).
  - A rank-one catalysis matrix is the exception: it stays reversible, with a shifted
    equilibrium.
- **The original authors' kernel is not established either way.** Their papers state the rate law
  but no event rates. Their 2000 scheme, Poisson draws on the net rate, is a different kernel.
- **Not tested:** the preprint's vector-Poisson contracts.
- **The preprint's driven runs are not affected,** because detailed balance is not expected there.
- **The pair-consistent form is exactly reversible.** In it, the leaving molecule does not catalyse
  its own leave.

**The comparison (D138), approved:**
- **(A)** an independent reference, written from the preprint's Appendix F by an agent who has read
  neither the engine nor the programme's code;
- **(B)** the programme's clean-room test code (MIT), run unmodified and out of process;
- **(C)** a distributional comparison on 40 fresh matrices, at tolerances registered in advance,
  with planted controls that must be caught.

## D193: Mitochondria: the direction, and the comparison approved

2026-11-16. The mitochondria design (`docs/MITOCHONDRIA_DESIGN.md`). The user: "7. agreed" and
"8. agreed".

**The direction:**
- **One law set** for mitochondria and bacteria (*E. coli*, JCVI-syn3A), with one thermodynamic
  cycle form.
- **One effective mitochondrion per cell first.**
- **Isolated cardiac mitochondria first,** then mitochondria in a cardiac cell (D183).
- **The source:** Beard 2005 (PLoS Comput Biol 1(4):e36), with its 2006 correction (2(1):e8). An
  independent check found both legible in PLOS's open XML:
  - the display equations' MathML sits in XML comments;
  - Table 1's 35 parameters are text. The correction changes 9 of them;
  - the comment text was not checked against the typeset images.
  - *Corrected the next day:* the PDF is the version of record. The web XML's Eq. 22 is stale, and
    the independent check of the cycle laws (`docs/CORE_SEAMS_STEP0.md` §7) found it.
- **Probe P1 comes first,** because the membrane-potential mode is stiff.
- **Not put separately:** the note's questions 3 and 4 (the respiration drive and the
  intermembrane space). Its recommendations stand as working defaults. Host P or C remains the
  lead's call (§3.6).
- **The cost:** about 23–46 agent-days.

**When:** step 4 of D194's order.

**The comparison (D138), approved:**
- **(A)** an independent whole-organelle reference, by an agent who has read neither the engine
  nor any model file. It runs in two arms: as published, and with the note's listed departures;
- **(B)** the published model, run unmodified and out of process, from the public CellML in
  libOpenCOR. Whether that file carries the 2006 correction is checked first;
- **(C)** a comparison over the source's steady-state and low-oxygen protocols, judged against the
  declared arm, with the differences from the published model reported.

## D194: The order after 16 November

2026-11-16. The user: "9. lets go".
1. **D188's moves, now.**
   - The full verification of main's head comes first.
   - The retire (D189) and the pin (D190) land before move 1, which starts from a head that holds
     both.
2. **One core-seams pass:** the shared transporter and cycle kind, populations, binding, and heat
   booking. It serves the cardiac laws, mitochondria, composition's pumps and finite fuel. It also
   takes:
   - D188's separate refactors;
   - the fuel-potential check and the material-slope seam, from the compartment-pH design's §17.7;
   - the visualizer's three run-view format items.
3. **Then in parallel:** the human cardiac laws (D183, D184), composition (D191), and finite fuel.
4. **Mitochondria (D193) and GARD (D192),** after their prerequisites.
- **G3 and G4,** owed since D172's landing, run once with tier 3 on D188's final tree.
- **No dates** until the core-seams pass is scoped.

## D195: The core-seams pass approved at its scope, within seven agents; `cells.modules` provisional; no checkpoint crosses move 2

2026-11-17. On the four items of the core-seams design (`docs/CORE_SEAMS_DESIGN.md`, §14), the
user: "Get adviser on those options but sounds good from my perspective, we want to focus on the
core but in parallel". With the advisor, every default stands, with the conditions below.

**1. The pass, at its scope.**
- **The estimate is the design lane's own, not yet re-derived:** 20–31.5 agent-days plus 2–3 on
  branch X, and about 9–13 working days elapsed.
- **The code starts after D188's move 2.** *Amended the same day:* seam F's foundation started
  earlier, on the user's "can we add one more agent on building core?". It landed before move 2
  and before the owner table (75e925ea), gated identical on a tree that differed from main only in
  docs. The rest of the pass still follows move 2.
- **The cycle kind (A) and the binding closure (C) wait for step 0's cycle-law screen.** The
  screen asks whether O'Hara–Rudy's and Beard's cycles factor in A's form. A's contract rests on
  that, and the note lists it as unverified.

**2. Staffing within seven.**
- **Each file has one owner for the whole pass.** §13's table is redone so that no file has two
  owners, and the elapsed estimate is re-derived from it.
- **One operators owner** does composition's M1–M5 first, then B1. *Amended the same day:* B1's
  operator part comes first, and composition after. This follows D194's order (the core first), and
  it keeps composition's 12–15 days off the pass's critical path.
- **An FR owner** runs FR-4 and FR-5 in parallel.
- **The cap stays at seven** (the user, 17 November: "lets keep the 7 agent cap"). The pass's
  owners count together with every other agent, GARD's included. The pass starts with the owners
  that fit, and the rest join as other lanes finish.

**3. `cells.modules` is built as provisional.** The word "provisional" stands where contributors
read it: the module's docstring and its docs. There is no public stability promise until a first
outside module arrives; then the promise comes back to the user.

**4. No checkpoint crosses move 2.** A checkpoint written before move 2 is refused cleanly, and the
refusal names the tag of the tree before the move, where it restores.
- *Amended 18 November (the lead; confirmed by the user the same day, "Yes, accept", before move 2 landed):*
  - **The layout identity** is the checkpoint's recorded source map, the paths in `source_hashes`,
    and not a new field. That covers checkpoints already on disk and the frozen @1 writer.
    `cells.source_layout` declares each made move: its name, the folders it dissolved, and the tag
    where the earlier layout restores.
  - **Both engine routes refuse and name the tag:** `io.load_snapshot` and `load_batch_snapshot`,
    the continuity route included.
  - **One exception, the frozen comparison model:** GARD's @1 lineage reader
    (`models/assembly_lineages/checkpoints.read`) is frozen by D215. Its refusal is clean (it refuses
    any changed engine source), but it doesn't name the tag. GARD's documentation names the tag
    instead.

**In parallel now ("focus on the core but in parallel"):**
- D188's move 2, starting with a full dry run;
- an FR owner, for FR-4's and FR-5's tools, rehearsals and registration;
- step 0's desk work: the cycle-law screen, the pins against F's extractions, the search for
  worlds that refusal 4 per move would newly refuse, and one owner per file;
- P1 and the booking probe, in scratch, once their criteria are committed.

## D196: Older code is a reference until the modular engine has learned from it, then it is dropped

2026-11-17. The user said to the visualizer session: "no legacy code, it will be removed - we're
still building Cells so not really any legacy data". The user said to the lead: "when we have
learned use the old code then we can drop it".

- **`src/cells/legacy/` (D188's move 1) is a reference, not a supported surface.** No new work goes
  into it, and it is kept only as far as the gates need.
- **A capability's legacy code and its tests are dropped once the modular engine covers that
  capability,** having learned from the old code. The capabilities that live only in `legacy/`
  today:
  - calcium handling, to be rebuilt with the human cardiac laws (D183, D184);
  - energy and mitochondria, to be rebuilt with D193;
  - the older families' injury law. FR-5's `patch_damage` kind already covers it.
- **Dropping comes as one batch the user approves,** as D187 and D189 did. The tree is tagged first,
  and a coverage check lists what each removal would lose.
- **The viewer's map already leaves out `legacy/`.**
- **Before any batch drops a legacy test that is a live law's only reference check, the check moves
  beside the law and becomes its declared test.** The first known case is Kv1.5's 19
  kernel-against-reference cases in `tests/unit/test_voltage_gated_membrane.py`, a tier-3 file that
  imports `cells.legacy` (the documentation design's gap 10). It is not in D198's batch.

## D197: Cells builds its own first-principles origin-of-life engine; GARD is for comparison only

2026-11-17. The user, on starting GARD: "and we will also do our own first principle engine, GARD is
only for comparison".

- **The origin-of-life track's engine is Cells' own,** with laws derived from physical chemistry
  rather than an abstract catalysis matrix:
  - thermodynamically consistent catalysis;
  - physical assemblies;
  - explicit sources of free energy.
- **It runs on the general machinery built in GARD's G1 (D192),** under neutral names, not GARD's:
  - the exact SSA kernel with keyed streams;
  - assemblies exchanging with a held phase;
  - fission, continuation and lineage;
  - the stochastic thermodynamic ledger;
  - the run records.
- **GARD is one declared law set on that machinery, used only for comparison.** It has the preprint's
  single-event form and the pair-consistent form, and D192's comparison (D138) stands as approved.
- **The first-principles engine starts with a design note that gives the user options (D142)**,
  before any of its laws are built.

## D198: `processes/` is dissolved: its pinning legacy laws retire, and what the engine uses moves

2026-11-17. Move 2 found that keeping the bytes of the files that legacy laws pin would need a
leftover `src/cells/processes/` folder: option (L). Option (R) was to retire the tests and laws
behind those pins. The user: "So let's retire any old files but transform them into the new engine
if neccasary so (R)".

- **D196's first removal batch, scoped to the `processes/` cluster and its own leftovers.** That is
  the pinning legacy laws, `charged_surface_work` and the stable-seed and conservative-polygon
  geometry cluster, together with the tests that run only them.
  - The 91 held tier-3 files and the rest of `legacy/` wait for a later batch.
- **One fact per file decides "transform if necessary":** does an active entry point reach it?
  - A reached file moves like any other, and its law kernels become law modules in seam F's
    extraction step.
  - An unreached file retires.
- **The batch, in the manner of D187 and D189:**
  - the tree is tagged first;
  - the exact list is taken from the dissolved tree, with one line on each capability that goes;
  - collection falls by exactly the retired IDs, and the tier records follow.
  - If a registered protocol's guard tests or a kept family's tests are on the list, the batch
    stops and asks the user.
- **Superseded:** the moves note's byte-keeping rulings (§17 item 2, §18 and §19 on the six files),
  and step 0's extraction exclusion rule, once the batch lands.
- **The BLAS pin.** If `src/cells/__init__.py` is no longer pinned, the pin may return to one
  home, as D190 first said. Move 2's owner measures it as R6 was measured: on 2 CPUs, with a
  planted control, and with continuity still importing no numpy.

## D199: The origin-of-life engine's first decisions, and relationship tracking

2026-11-17. On the design note (`docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md`), the user said: "Then I go
with your recommendations on the origin of life", adding "but look at docs/SOTA_ORIGIN_OF_LIFE.md
also", "first with your adviser also" and "also to see if we are missing some engine features for
tracking relationships in the most effective way".

**Decided, as recommended:**
- **U1:** amphiphile assemblies, with their geometry derived from the counts, first; oligomers
  after.
- **U4,** which follows U1: selection by a finite shared pool and serial transfer. Moran
  replacement is used only for comparisons.
- **U5:** templating after oligomers.
- **U6(b), the experimental anchors:**
  - A1 (tension competition) and A4 (shape and shear division) are judged anchors (D138);
  - A2 is reported until its question is settled;
  - A3 comes later;
  - A5–A8 are reported only.

**The lead's calls:**
- **U2: one free-energy function for every law.** Driven laws without a declared source are
  refused. D192's single-event GARD law is admitted as the labelled exception.
- **U3:** ideal and regular mixing in OL1.
- **U7:** the deterministic limit of the same laws, declared as a representation for
  vesicle-scale anchors and qualified against exact events where both run.
- **U6(a): the GARD limit is a consistency check by construction, not a D138 comparison.** G1's
  pair-consistent rule is the note's "kinetic factor on the common state", so it carries a planted
  control.

**U8, the scope: the whole programme.** The user, the same day: "whole program". OL0–OL9 is built
as one programme, in order with its gates, starting once G1 and seam F land. The estimate, about
33–51 agent-days, is the design lane's own.

**Relationship tracking: four checks.** Descent, whose material is whose, who depends on whom,
and what history a state carries.
- **Descent:** G1's fission table records both daughters, but its single-lineage mode follows one.
  Check that carrier keys are unique across a world, that each row carries its parent and end
  reason, and that tissue division and replacement write the same shape.
- **Material provenance, the likely real gap.** Nothing in the active engine labels material by
  origin; a search finds no tracer or label machinery.
  - The general form is a declared label on a species' amount, which every law moves without
    seeing.
  - Without labels, programs are identical. With them, events are unchanged, and any label draw is
    on its own stream.
  - It is one mechanism with step 0's moiety ledgers, in the core, with the species rows.
  - A design section comes first. It is put to the user as a finding to confirm.
- **Dependence:** FR-12's manifest (reads, writes and provides) answers the static question. "Who
  fed whom" is provenance again, and supplied material names its source, as work names a payer.
- **History:** a carrier swap needs branching plus a transplant. Check whether E07's donor-copy
  machinery is general or tissue-only.

**The state-of-the-art note (`docs/SOTA_ORIGIN_OF_LIFE.md`).** It asks for resemblance, function
and renewal kept apart, every descendant tracked, founder material traced, and external help
visible.
- SpudCell and Otto-type replicators are candidate benchmarks. Each is a D138 question, raised only
  after its primary sources have been read.
- **Two cheap fit tests:**
  - Does the note's assembly admit a fibre that grows and breaks under shear?
  - Is SpudCell's plasmid-set inheritance reachable on G1's partition machinery in population mode?

## D200: Relationships are tracked in general, so that graphs come easily from the raw data

2026-11-17. Asked whether the lead had read "tracking relationships" right (descent, whose material
is whose, who depends on whom, and what history a state carries), the user answered: "yes, let's
have a good way to track things in general so we can create graphs from the raw data easily, for
example so plug the gaps".

- **A general engine feature, not one per experiment (D144).** A design note with options comes
  first (D142); building follows the user's ruling on it.
- **The gaps D199 found:**
  - **Material provenance:** declared labels on species amounts, which every law moves without
    seeing.
  - **Every descendant:** a population of lineages with one record shape across tissue division,
    replacement and assembly fission.
  - **Supplied material names its source,** as work names a payer.
  - **History:** branching, and transplants between lineages.
- **Graphs from the raw data.** The records give relationships as plain node and edge tables with
  stable identifiers, so a lineage tree, a material-flow graph, a dependency graph or a history of
  branches is a join, not a reconstruction.
- **The standing rules hold:**
  - a world that declares no tracking gets identical programs;
  - with tracking, events and results are unchanged, and any label draw is on its own stream;
  - totals are conserved per label;
  - each claim is tested with a planted error (D187).

## D201: Numbers from free-to-read papers may be used with a citation (extends D186)

2026-11-17. The visualizer session put a question to the user in a dialog, and relayed the ruling to
the lead.
- **The case:** E. coli drawn to scale uses five envelope widths measured in two papers, Matias et
  al. 2003 (J Bacteriol 185:6112) and Berry et al. 2010 (Protein Sci 19:1967). Both are free to read
  at PubMed Central but not open access: publisher copyright, no licence stated, and no limit on use
  in their text.
- **The user:** "Yes, use them".
- **The rule:** for free-to-read papers in general, numbers may be used, each with its citation.
  Never their text, figures or data files.
- **Still asked case by case:** a paper whose own text limits use to academic or non-commercial
  purposes. Non-commercial material otherwise stays analysis-only.
- **No full-text copy is saved.** The records are under `/mnt/datasets/Cells/ecoli/`.

## D202: Relationship tracking: GARD first, then everywhere, as one general engine feature

2026-11-17. On the relationships design (`docs/RELATIONSHIPS_DESIGN.md`), the user said: "sounds good
and agree on 1. as you suggest then we make it work everywhere but we want it to be a general
feature of the engine - also get adviser in on those choces then lets go".

**The order:**
- **First, GARD's runs.** GARD's G1 part 2 writes the relationship tables for GARD's lineages. The
  first graphs show descent and supply. Who fed whom, founder material against rebuilt material,
  needs the material labels, which belong in the core.
- **Then everywhere,** after the core-seams pass: descent across tissue division and replacement,
  named sources, material labels, and branches and transplants.

**One general feature from the start.**
- The tables' writer and its row interface live in their own engine module, outside the GARD
  family, with their own owner. GARD only calls it.
- **Before anyone binds to it,** a second consumer must use the same function with no edit to the
  writer: an existing division world's and an existing replacement world's lineage. No operator
  file is touched.
- `cells.relations@1` is provisional until that passes.

**The lead's choices, reviewed with the advisor:**
- **Labels follow one-way flows.**
  - Net-flow mode is declared per law.
  - Any founder-fraction or renewal readout refuses a label that used it.
  - A factored cycle law exposes both one-way fluxes (CORE_SEAMS_DESIGN §16).
- **The format is NPZ plus a JSON descriptor, settled by a test.**
  - The arrays load with `allow_pickle=False`, so string ids are fixed-width columns.
  - A lineage tree and a supply graph are drawn from a GARD bundle by a short script that imports
    no engine code.
- **Written by default for GARD.** For existing worlds this is decided at RT1, from the results
  gate's file comparison.
- **Frozen before any bundle is shared:** the `s:c` key rule, end reasons (an unfollowed daughter
  differs from an extinct one), the final row, and a reserved `label` stream domain. The run
  qualifier appears only in ids, never in a stream fold.

## D203: A library of human-readable pages for laws, kinds, operators and models (approved tooling)

2026-11-17. On the documentation design (`docs/LAW_DOCUMENTATION_DESIGN.md`), the user said: "sounds good
lets go". This approves the build, which AGENTS.md counts as tooling, and the design's recommended
answers.

- **The first landing comes first** (about 3.5–5.5 agent-days):
  - `cells.declarations@2`: page links (`doc`), module paths and lines, structured citations, a
    `models` section, an explicit `not_extracted` list, units and read modes;
  - its format page, `docs/library/DECLARATIONS_FORMAT.md`;
  - the page tool (`scripts/library_pages.py`) and its drift check (`tests/unit/test_library_pages.py`);
  - the template, glossary and index;
  - three pilot pages.
- **Then the other pages,** in batches. The whole build is about 8.5–14.5 agent-days.
- **One page per piece,** at `docs/library/<namespace>/<section>/<name>@<major>.md`, keyed by ID, not
  by code location.
- **The one plain sentence lives on the page, not in the code.** Wording fixes then change no source
  fingerprint and strand no checkpoint.
- **Links into the viewer wait for its public address.** Until then, pages name `select=laws:<ID>`.
- **Status on a page** reads "Not stated" until a per-piece record exists, and is never invented.

## Implementation choices and remaining work

| ID | Choice | When to resolve | Evidence needed |
| --- | --- | --- | --- |
| O001 | Python/JAX versions and environment tooling | Resolved for M1a in D013 | Pinned CPU environment installed and checked; deliberate revalidation for other versions/platforms |
| O002 | Integrators and coupling schedule | Eleven accepted bounded CPU/JAX families, including CORE-009 finite outside | NUM-009 v2 selects 1 ms RK4/cubic with 0.5 ms refinement only on fourteen short finite-outside cases; production/replay/accounting and release checks pass. Shared-stage local/edge/outside rates and complete histories; old 0.5 ms one-cell, 10 ms multispecies and 2 ms graph bounds are unchanged; no multirate, GPU or arbitrary-regime guarantee |
| O003 | Array ordering and capacity buckets | CORE-003 species/cell/edge semantics; CORE-004 worlds and CORE-005 scalar/cohort windows verified | Larger buckets, vectorized policies and GPU placement need separate accuracy/resource measurements |
| O004 | GPU hardware/vendor and performance target | Early feasibility work / M4 | Available device, float64 capability, supported software, and measured workload |
| O005 | Production storage and schema evolution | Scalar/cohort complete checkpoints and bounded incremental NPZ/JSONL recording verified | Complete restart independent of selected output; HDF5/Zarr, output quotas and migrations remain future choices |
| O006 | Viewer technology | M3 | Required 2D views, interaction needs, and clean headless operation |
| O007 | Physical growth, resource, and partition laws | Before M5 experiments | Explicit model specification and accounting; relevant exploration updates |
| O008 | First ecological benefit and cost model | Before E10 | Independently defined ecology, fair controls, and held-out schedules |
| O009 | First organ, species, and validation function | Before M7, without blocking M1 | Simplest useful model with adequate evidence, explicit extent, and external dependencies |
| O010 | First cross-resolution and organ-port models | M6, then M8 | Dimensional/accounting checks, coupling convergence, response validation, and explicit delays |
| O011 | Computational decomposition and large-GPU strategy | After representative tissue workloads | Memory/work/communication profiles, fine/coarse accuracy, and available hardware |

These are normal design tasks. They do not require a new language-selection
discussion or prevent the next independent implementation work.

## D204: Molecular machines go on the engine's backlog (FR-13)

2026-11-17. The visualizer session relayed the user's request:
- a "Machines" tab in the viewer, cataloguing molecular machines per species as the proteins were;
- modelling the machines put on the engine's backlog.

The user confirmed it to the lead, "yes new feature request from me", and added:
> "only thing with the machines, if there is something missing in our core archtecture or if they can
> be naturally modeled there"

> "and we'd to be able to model them both individuall and in aggregate in a cell or whatever, LODs
> based on what is being looked at"

- **[FR-13](FEATURE_REQUESTS.md#fr-13--molecular-machines-individually-and-in-aggregate) records the
  request.** Its scope stands on D140: assembly, not folding.
- **The first step is a read-only design note.** It answers the user's question: can the core
  architecture model machines naturally, individually and in aggregate, with the level of detail set
  by what is looked at, or what is missing?
  - It presents options.
  - Nothing is built before the user has discussed them.
- **The tab and its catalogue are the viewer's own data,** under D173, D178, D186 and D201. Its
  fields follow what a declared model carries, once one exists.

## D205: Declared extension goes on the backlog (FR-14)

2026-11-17. The user asked: "one question is it possible to extend a model or an operator, like object
oriently?" The lead answered from the code: subclasses register under new IDs, but the engine does not
record or check an extension. The user then said: "cool get also adviser in on this so put the oo
extension on the backlog".

- **[FR-14](FEATURE_REQUESTS.md#fr-14--declared-extension-of-laws-operators-and-models) records it.** It
  holds what was verified at seam F's registry head and the three missing pieces: a declared extends
  link, inherited checks, and version rules.
- **FR-13's design note covers it,** since machines are its likely first use. No separate note is
  written.

## D206: The laws in D198's retire batch are transformed into the new engine, even unused

2026-11-17. The lead listed the eight capabilities that D198's batch drops, none of them transformed.
The user answered within the window the lead gave: "so those old models, we should transform those laws
even if we don't use them yet", then "if that makes sense". This amends D198, whose rule was "transform
them into the new engine if necessary".

- **The retire batch is held out of landing.** Branch `retire-processes`, at 81a96128, stays as gated
  until the split below is agreed.
- **Scope: the eight capabilities of D198's batch.** Whether the same applies to `legacy/`'s laws is the
  user's call; D196 stands until then.
- **The lead's proposal, made with the advisor, is put to the user.** Nothing is built before the user
  agrees.
  - **Physical laws** in the batch go onto seam F's law template now. Each one gets:
    - one reference check, against saved outputs of the old code run from a frozen snapshot, not
      against the old test files;
    - its old status carried over: charged-surface work, for example, was "held, never released";
    - a visible "not qualified" status in the manifest and the library.
  - **Numerical methods and geometry machinery** (meshes, polygons, control volumes, partitions) wait
    for the engine's own geometry design, instead of being ported as they are.
  - **Kernels that carry BETSE's conventions** enter `src/cells` only under neutral names, with a
    citation.
- **A classification table of the batch's 33 source modules is being made, read-only.** For each
  module it gives the class (law, method or machinery) and what the modular engine already covers.
- **Landed (17 November, evening):** merge 742132db, once the two laws' reference outputs were saved.
  The table's result: 2 laws, 16 methods and 15 machinery modules.
- **The user agreed the split** the same day: "yes, the levin work has highest priority as we want to
  use that as an example in the viz, machinery can wait for sure".
  - The batch's laws go onto seam F's template, after the classification table, at a lower priority
    than the gap-junction replication (D207).
  - The machinery waits for the engine's geometry design.
  - `legacy/` stays under D196 unless the user extends this.

## D207: The gap-junction replication has the highest priority

2026-11-17. The user: "the levin work has highest priority as we want to use that as an example in the
viz". The work replicates, with the Cells engine, the experiment of the public bioRxiv preprint
10.64898/2026.09.02.748840, which was made with BITSEY. It is on branch `gap-junction-replication`.

- **Its jobs have first claim on CPUs 6, 7, 22 and 23,** at nice 0 while other light work stays at
  nice 10. It takes lane A when it needs dedicated cores.
- **Its runs are designed to be shown in the viewer as an example.** The format is agreed with the
  visualizer session. Anything shown is published from a stated run with its revision, and a
  development run is labelled not judged.
- **Lead's note, not part of the user's decision:** FR-4's and FR-5's judged run, already queued on lane
  B, is not interrupted.
- **Amended the same day.** The user: "so GARD and Levin highest priority". GARD's work (D192, D197)
  shares the highest priority with the replication.
  - On lane A, GARD's short gate runs first and the replication's tissue search follows.
  - On the light CPUs, both run at nice 0.
- **Amended again, the same evening.** The user said: "lets get GARD and Levin finished as soon as
  possibl even if we have to slow down other work, I want to replace the Experiments in viz with those
  two for the next demo, which will be soon".
  - The viewer's Experiments view shows GARD and the gap-junction replication in the next demo.
  - Other work slows for them (D211).

## D208: Numbers from BITSEY's code and logs may be used, cited

2026-11-17. The gap-junction replication found that BITSEY's repository carries no licence. It asked
whether numbers from BITSEY's code and logs may be used: the Cx45 gate constants and Table 3's
provenance. The user: "its fine on BITSEY code we are MIT here".

- **Numbers from BITSEY's code and logs may be used,** each cited to the repository and the commit
  read.
- **AGENTS.md stands.** BITSEY's code is never copied or imported into Cells. It may be run out of
  process, in its own environment, as a reference; that is proposed to the lead first.
- **Lead's note:** downloaded copies of BITSEY stay under /mnt/workspaces and are never committed.

## D209: Molecular machines: M0 now, then M1 (FR-13)

2026-11-17. On the machines design (`docs/MOLECULAR_MACHINES_DESIGN.md`), the user said: "lets go with M0
then m1 - but get adviser in on the final decision then go". The lead reviewed the choice with the
advisor.

- **M0, now.** The viewer's Machines tab is a catalogue with drawing levels, labelled illustration.
  - No machine is in the engine; the drawing levels are the viewer's, not simulation detail.
  - ATP synthase reads "planned, first".
- **M1, next: ATP synthase as the first machine, built as general pieces.** "Go" means its build plan
  (§10), not code.
  - **One law, one owner.** M1's law is D193's `proton_coupled_atp_synthesis_cycle@1`, built by the
    mitochondria lane after the core-seams pass; FR-13 writes no synthesis law. Beard's printed F1F0
    law (Eq. 11) fails the step-0 screen, so the user rules on a departure.
  - **The order:** the core-seams pass, D193's synthesis law, M1a, a minimal form of D175's
    representation fields, then M1b.
  - **Seam A.** The note's per-edge detailed-balance check implies §16's Wegscheider condition when
    every state declares one free energy (§10.2). Seven requirements go to seam A's design.
  - **Cost:** 17–26.5 agent-days. The second consumer, named before any code, is the proteasome core
    (M2).
  - **Sources:** the numbers were read through a page-reading tool. A direct read is owed before any
    number is registered.
- **The note's questions:**
  - **U1, U3 and U5 are answered by this choice:** a level fixed per run first, ATP synthase first,
    and tagged one-way individuals first.
  - **U2:** the user's words of the same day, "different researdh would need different levels of
    detail so you could choose the setup" (D210). The lead reads them as follows: the level is declared
    per run, undeclared worlds are unchanged, and the finer representation is the reference.
  - **Open:** U4 (the ribosome and D145) and U6 (a declared extends link, FR-14).
  - **Put to the user:** U7, which judges ATP synthase's intercept and reports its coupling ratio as a
    finding. The approved check stands until the user rules.
- **The lead's rulings:**
  - **L1 and L3:** the relations vocabulary and the manifest's machine piece wait for later
    versions. `cells.relations@2` collects its requirements from three sources: machines,
    mitochondrial fusion (D210), and GARD's need for an order between same-time events.
  - **L4:** D175's four fields are designed once, against fuel (D174), machines and mitochondria.
    D174's fuel case stays their first consumer.
  - **L5:** the zero-rate run belongs to the mitochondria lane, which owns the synthesis law.
- **Amended by D214 (user, 17 November):** the static level-of-detail contract (D175's four fields,
  with finite fuel as the first executable consumer) comes before M1a.

## D210: Mitochondria: the level of detail is chosen per research question; individuals sooner

2026-11-17. The lead explained that mitochondria use one set of laws, and that the host sets the level.
The first level is one lumped mitochondrion of N identical members per cell (D193), which is exact for
identical members; then classes; then individuals. The user: "sounds great. So yes, the idea is that
different researdh would need different levels of detail so you could choose the setup. get adviser also
in on this". On individual mitochondria with fission and fusion, the user added: "yes sooner rather than
later".

- **This confirms D175.** Levels of detail are declared representations, chosen per mechanism and per
  question. Two independent laws for one mechanism are not written: a simpler level is declared as a
  representation of the detailed one.
- **Individual mitochondria move up in D193.** D193's first step is unchanged: the lumped node stays the
  reference that N identical individuals must reduce to.
  - **"Sooner" means the design now, and its dependencies pulled forward.** No mitochondrion runs in
    the modular engine yet, and the synthesis law still needs the user's ruling on a departure (D209).
  - **Static individuals** (N mitochondria per cell, with no events) may need no new door. An addendum
    to `docs/MITOCHONDRIA_DESIGN.md` checks the code.
  - **Dynamic individuals need more:**
    - splitting and merging a compartment's patch at fission and fusion;
    - retiring one compartment in a living cell;
    - stochastic partition at division;
    - two-parent relations (`cells.relations@2`).
- **Choosing between levels that are not exact** needs D175's four fields, designed once for fuel,
  machines and mitochondria (D209, L4).
- **The addendum is read-only and gives options.** It names the first research question that needs
  individuals, and the free-to-read data for it. Inheritance may belong to another target, since
  cardiac cells rarely divide.

## D211: Tested legacy laws are ported to the active engine, below GARD and the replication

2026-11-17, evening. The visualizer session found that 38 of the Protein atlas's 48 units rest on laws
that no active model declares. It relayed the user's reply: "the lead so prioritize reimplementing
those". The user then told the lead directly: "so yes for legacy laws that maybe have been tested we
should port those with priority". The user added: "but not the highest priorty, lets get GARD and Levin
finished as soon as possibl even if we have to slow down other work" (D207).

- **Scope:** the 54 law IDs behind those 38 units, tested laws first.
  - This amends D196: legacy laws are ported, not only rebuilt when a capability needs them.
  - It amends D206: the retire batch's two laws join this program.
  - The count of other legacy laws is reported to the user after the inventory.
- **The method:**
  1. A read-only inventory first. For each law it records where the kernel lives, whether the law is
     tested, what it needs beyond voltage, and who owns the mechanism.
  2. One pilot family, a voltage-only family that is tested and whose kernel is already live, ported
     end to end.
  3. Batches on disjoint files.
- **Each ported law** declares its test and its source. Its reference check moves beside it, as D196's
  safeguard requires, and no citation is written from memory. Adding channel codes to @3 must leave
  existing worlds' programs and fingerprints unchanged.
- **Mechanisms already owned are not ported as they stand:**
  - calcium handling and NCX fold into the cardiac lane's planned laws (D183, D184);
  - mitochondria fold into D193;
  - the gap-junction flux belongs to FR-16.

  D210 rules out a second law for one mechanism.
- **A law that becomes declared is not thereby qualified.** Each unit keeps the status its record
  states.
- **Priority:** below GARD and the gap-junction replication.

## D212: The origin-of-life programme starts now, aimed at lipids with chemicals in and out, and fission

2026-11-17, evening. With GARD and the gap-junction replication's first stages on main, the user said
"Lets go on 4" (the origin-of-life engine, D199's whole programme). They added: "where we test break and
renew in a real lipid simulation", and then "so the first principle physics simulation of lipids and
chemcials going in and out fission".

- **OL1 and OL5 start now, under D199.** No new design round is needed, since D199 settled the design.
  - **OL1 (the laws)** first delivers a design check: how its laws fit G1's kernel, frozen the same day,
    without changing any `cells.assembly_lineages@1` world.
  - **OL5 (independent references)** writes its designs in files before any engine output exists.
- **The programme's first target is the user's:** a first-principles physical simulation of lipid
  assemblies, with lipids and chemicals going in and out, and fission ("break and renew").
  - OL2 delivers the in-and-out: phase exchange, geometry and tension from the counts, the lumen, and
    the finite pool.
  - OL3 delivers the fission: physical division, partition and serial transfer.
  - OL1's laws are the foundation.
- **Priority** follows D207 and D211: this programme, beside the port pilot and the core-seams pass.

## D213: The tissue search reruns now; the core pass restarts through retire, then move 2

2026-11-17, evening. The lead asked two questions:
- rerun the gap-junction tissue threshold search from main, now that FR-19's fix is there;
- restart the core-seams pass through the chain retire, then move 2, then the pass with about four
  owners, folding the Kv1 port pilot into it.

The user: "yes on both as y9u suggest".

- **The "neither" threshold search reruns** exactly as section 7 of the replication's note registered
  it, from a clean snapshot of main, on lane A. It is labelled a comparison with BITSEY's log at
  b2cb370, written by an earlier revision of its code. Its arms reach the viewer only from main, and
  the page only if the user says so (D207).
- **The chain:**
  1. D198's retire batch lands once its merged-head gate passes. Its two laws' reference outputs are
     saved, so they can be rebuilt under D211.
  2. D188's move 2 follows.
  3. The core-seams pass (D195) resumes at steps 1–3, with about four owners within the cap of seven.
- **The Kv1 port pilot (D211) folds into the pass,** as seam F's step-2 per-law extractions, which own
  the same files.

## D214: An external adviser's architecture follow-up: two fixes now, the rest to the core backlog

2026-11-17, evening. The user forwarded an external adviser's architecture follow-up, reviewing main
b661cd1a. It found the modular direction sound and listed seven items for a bounded core-completion
lane. The user's instructions: "two fixes then backlog", "external adviser", and "also get your
adviser in on this". The lead reviewed it with the advisor.

- **Now, item 1's two extension-boundary fixes,** on branch `core-boundary-checks`:
  - kinds write only their own resolved, declared fields (initial values, derivatives and control
    outputs);
  - more than 31 model checks are refused at admission.

  They land before move 2's map is regenerated, as an exception to D195's "code follows move 2".
- **Items 2–7 are the core backlog,** mapped to their seams and records in CURRENT_PLAN's
  17 November section. They are not new decisions.
- **Two order questions were flagged for the user, not decided:**
  - item 4 pulls D175's fields ahead of M1a in D209's order;
  - item 3's first outside module brings back D195's question of a public stability promise.

  **The user answered the same evening:** "1. sure, 2. but low priority".
  - Item 4 comes before M1a: the static level-of-detail contract, with finite fuel as its first
    consumer, precedes machines' M1a. This amends D209's order.
  - Item 3 (the installed external module and the stability-promise question) is low priority.
- **Item 7 was applied the same day:**
  - CURRENT_PLAN was refreshed;
  - the README's status was brought to 17 November;
  - the README's levels-of-detail paragraph was reworded as an aim;
  - the gate wording was made precise: "0 changed against the baseline".

## D215: The core may change while the first experiments run; gates do not

2026-11-17, evening. On the lead's rulings for OL1's design check, the user said: "Sounds good on the
rulings, get adviser also on it - and as we are just doing the first experiments, find to change the
core and even so we have to keep on upgfading". The lead reviewed it with the advisor.

- **The lead's reading:** this is permission to change the core where that helps, not an instruction to
  reverse the rulings.
  - It relaxes source freezes kept for their own sake, and the bias toward duplicating code to avoid
    touching a frozen file.
  - It does not relax gates, registered results, D148, or guards such as FR-18.
- **Applied to the origin-of-life engine:**
  - **OL1 keeps Option A** (a separate `cells.assembly_lineages@2` package) for now.
  - **At OL3, the default is one shared run loop** for `@1` and `@2` behind `@1`'s invariance gate,
    not a copy. The probe-set comparison's exemptions are widened deliberately then, after the demo.
  - **Ruling 3 is revisited:** `@1` gets the driven-law guard under its invariance gate, if a second
    unsourced driven law is not already refused there.
- **D199's U6(a) is amended.** The GARD limit is exact only under the declared measure that matches
  G1: `condensed_measure: multinomial_less_one` with `last_molecule: extinct`. The physical measure,
  `multinomial` with `kept`, reaches GARD to O(1/N).
  - OL6 reports both.
  - In OL9's ladder, the switch of measure is its own rung.

## D216: An FR completion lane for FR-1 to FR-10, beside origin of life and the core pass

2026-11-17, evening. The user said: "the start of origin of life is good but we also have other
priorities like finishing fr-1 to fr10, status on that". The lead gave the status (FR-4, FR-5 and
FR-9 done; FR-1, FR-3, FR-6 and FR-10 partly done; FR-2, FR-7 and FR-8 logged) and proposed a lane.
The user: "sounds good yes".

- **An FR lane,** owned by the agent that qualified FR-4 and FR-5, starts when a slot frees within the
  cap of seven. It takes the fast judged acceptances first:
  1. FR-10's protocol and judged run;
  2. FR-1's judged acceptance, exchange's first;
  3. FR-3's independent references, then its protocol;
  4. FR-6's channel target qualified with the coupling operator (A5).
- **Design notes for FR-2, FR-7 and FR-8 follow.** FR-7 needs the user's choice of the closed loop's
  unit, framed by its note.
- **Overlaps go to the core pass,** so no file has two owners: FR-3's binding with seam C, FR-6's
  routing door with seam B1, and FR-1's later doors (creation, division, fission and fusion,
  retirement) with seam B and the mitochondria work (D210).
- **Amended 18 November (the lead).** FR-7's design note found that B1 as written covers the kinds'
  routing door into @3 (CORE_SEAMS §4.3), not the coupling note's operator *rate route* (§2.1).
  The rate route edits the operators owner's files, so it becomes step B1′, after B1, with that
  owner (CORE_SEAMS §13's table). It goes ahead only if the user's answer on D145's hold admits a
  species → control → production loop. That is FR-7's note, question 2.


## D217: FR-7, FR-8 and FR-2: the first loop's unit, stage 0, and retrieval's version 1

2026-11-18, evening. The lead put the three design notes' questions as options, reviewed with the
advisor. The user relayed the answers of the project's external reviewers ("Please take the
following as my answers"), then gave the go ("Yes—go ahead with the previously recommended
choices and qualifications"; "and go from me"), with two clarifications.

- **FR-7, abundance to function** (ABUNDANCE_TO_FUNCTION_DESIGN):
  - **The unit.** A membrane channel population is the first loop (U2). The junction channel (U1)
    follows, with its contact and maturation requirements. The first loop establishes reusable
    production, finite precursor consumption, delays, removal and material accounting. D145's
    provisional unit is changed.
  - **The estimate stays explicit:** 10–16 agent-days, excluding FR-2 and composition. The
    abundance source can be prepared early. Its live integration needs composition's M1, the
    interface for reading other operators' current state.
  - **The first acceptance is numerical**, on synthetic minute-scale lifetimes labelled as
    synthetic. It covers finite unit turnover, several declared lifetimes, and template clearance
    measured from the run's trajectory:
    - the clearance criterion is declared before the run;
    - its threshold is meaningful for the template's remaining ability to drive the response;
    - a declared rule covers falling back below it;
    - every compartment that can still release template is included;
    - literal zero is not required, and "not cleared" is a valid outcome.

    Sourced lifetimes belong to the later biological comparison, and are distinct from a run's
    recorded clearance time.
  - **The closed loop.** The closed-loop capability is not called qualified until a genuinely closed
    feedback case passes, with a control in which the feedback is cut. Persistence is measured, not
    required. The linear chain from template to conductance is a first check only.
- **FR-8, long-duration mode** (LONG_DURATION_MODE_DESIGN):
  - **What is approved: stage 0 only.** That is FR-8's measurements M1–M5, plus a small numerical
    harness: an existing single-cell or two-cell case on today's fine engine, benchmarked under M3,
    with its trajectory and reference outputs kept.
  - **Every measurement's criteria and tolerance budget are declared before its comparison.** They
    cover cumulative trajectory error, intervention response, threshold timing, histories,
    conservation and measured cost. The old parity caps stay as benchmarks where useful.
  - **What waits.** The method, a new solver or a reduction, is chosen after stage 0's results and
    the core's FR-18 energy-check probe. Neither the full solver build nor an exact charged booking
    is approved in advance.
  - **The first scientific consumer** is FR-7's loop at measured lifetimes. Stage 0 does not wait
    for the full FR-7 loop.
- **FR-2, membrane retrieval** (MEMBRANE_RETRIEVAL_DESIGN). Version 1 is membrane and channel
  retrieval and recycling.
  - **Energy.** Retrieval follows the membrane's charge (R2), and the split and merge share one
    accounting. Version 1's scope reads "no new explicit machinery fuel draw in v1".
    - Recorded still: carrier-ion chemical work, reservoir and electrode work, and merge heat.
    - The machinery's omitted cost is a declared limit, so version 1 claims neither total
      trafficking energy demand nor ATP-limited uptake.
    - A later held or finite fuel coupling is designed once, in the common energy interface.
  - **The receiving pool.** There is one lumped pool per cell, well mixed, and stated as such, since
    pooling chemically or electrically different vesicles is not exact.
    - It is indexed by compartment, owner and route, so one pool is a first configuration, not an
      engine-wide restriction.
    - Cohorts or discrete vesicles follow when a specified observable needs within-cell variation.
  - **Staging.** Fluid-phase uptake comes in version 1.1. Internalised channel units start silent.
  - **Remaining uptake work, kept visible:** FR-3's receptor and bound-cargo movement, exchange with
    a changing area, and FR-4 and FR-5 on a growing compartment.
  - **The lead's rulings on the note's questions 5–11:**
    5. R2 is the charge rule, and R1 is refused as an artefact.
    6. The split-and-merge kernel belongs to the operators owner, inside B1's operator part
       (CORE_SEAMS §18). FR-2 starts when that lands.
    7. P0's record lives in the new operator's own state.
    8. Areas and capacitances are `reference` reads.
    9. The name is `scheduled_membrane_trafficking@1`.
    10. Pumps stay held on the plasma patch with their aggregate capacity.
    11. Refusal 5 gains version 1.2, which admits a retrieval-charged lumen's anchor at import,
        with a planted case.

## D218: D145's hold, narrowed again: physical production feedback through the one routing door

2026-11-18, evening, on the same go (D217). The coupling note's question 2 is answered: a species →
control → production loop is within the narrowed hold.
- **Admitted:** physical, state-mediated production feedback, only through the one coupling and
  rate-routing mechanism (B1′, the operators owner's, after B1). The rest of the gene-regulation
  hold stays in place.
- **Conditions.** Each loop:
  - declares its evaluation timing and its operating range;
  - is verified whole, against a reference, under timestep refinement, and with a control in which
    the feedback is cut.

  The regulatory state's rate bound alone does not establish that an arbitrary production feedback
  is stable.
- **Refusals kept:**
  - unsupported instantaneous algebraic cycles. Today's operator refuses instantaneous reads of
    charged species;
  - a population's availability multiplied by its own abundance where that abundance already sets
    its conductance. This is planned in FR-7's abundance source and built with it.

## D219: The gap-junction replication's next bundle and two judged comparisons

2026-11-18, evening, on the same go (D217). The note's §8 and §6 questions are answered.
- **The bundle,** next for a free seat:
  - the correctly specified 25×25 threshold case;
  - Figure 5a through the windowed execution and record path;
  - BITSEY run unmodified, out of process, for pinned reference outputs, after its licence and
    revision are checked.

  Before the 2D search, its registration states the geometry, the row-spread success criterion, the
  horizon, the bracket, the refinement rule and the compute budget. A representative point's cost is
  measured first, at a point that cannot show the threshold, and what it showed is disclosed.
- **Judged comparisons approved (D138),** each under a registered protocol with code-blind
  references:
  - **The linear model's numerical qualification.** Figure 8 is judged against independently derived
    physical balances, and the printed recursion's discrepancy is kept as a finding.
  - **The "neither" threshold comparison.** Successful refinement and a predeclared convergence
    condition are part of the verdict, and the threshold-to-log ratio alone is not the judge.
    - The 1D line's value was already seen (neither-02), so its registration says its conditions
      came after. Only the 2D field is a true pre-registration.
    - The historical log is named, with the uncertainty about which revision produced it. Fresh
      outputs from a pinned BITSEY revision are an additional reference.
  - **Table 3.** Its logged inputs and the interventions as actually executed govern the
    code-reproduction target. The printed table stays unchanged as a separate publication target,
    with the mapping discrepancies reported. Interventions are named by what they do, with the
    original labels kept as provenance.
- **FR-15, FR-16 and FR-17** stay with the core owners whose files they touch, scheduled after those
  owners' current work and not yet started:
  - FR-15 with the kinds and @3 owners;
  - FR-16 with the F owner, after its per-law extractions, and the @3 owner;
  - FR-17 with numerics, its owner named when a seat frees. FR-1's condensation door is the
    preferred route.

## D220: Seats, the gate tooling and the self-replicator replication

2026-11-18. Within the cap of seven (D171):
- **The seat order.** Free seats go, in order, to:
  1. the gap-junction bundle (D219), released or reassigned once its runs proceed unattended;
  2. the binding owner;
  3. the kinds owner, whose start is protected the moment the registry and the host table land;
  4. the code-blind references for D219's two judged comparisons;
  5. the gate tooling;
  6. FR-8's stage 0, when capacity allows, without displacing a core owner whose prerequisites are
     ready.

  Blocked work stays tied to specific owner hand-offs and interfaces.
- **The gate tooling** moves into the repository under `scripts/gates/`, with tests: the
  cross-revision runner, FR's bitwise landing set, the tier record's three-way fold, the
  definition-fingerprint check through a move map, and GARD's @1 invariance gate. The user approved
  this the same afternoon: "yes lets have them in".
- **The self-replicator replication.** The user asked for Liu et al. (Nature Catalysis 8, 1000–1009,
  2025) to be replicated. The pasted text stays out of the repository: it is paraphrased, cited, and
  its numbers are given as read. The authors' kinetic model runs out of process as a reference only
  if its licence allows. A replication owner writes the docs-only replication note first.

## D221: The self-replicator replication: development first, R0 and R1, the authors' model in Octave, recovery kept apart

2026-11-18, evening. The user answered the replication note's four questions
(SELF_REPLICATOR_SELECTION_REPLICATION §7.3): "1. A", "2. Agreed first two to start with", "3. Yes
fine with the install you have sudo on this vm", "4. yes agreed keep seperate as you suggest".
- **D138.** Development runs first. Once both chemical systems (1+4 and 2+3) run in Cells, there is a
  judged comparison against the paper's orderings, with the authors' model as a reported reference
  only.
- **Scope.** The first two stages start the work: R0, three hexamer types in stacks under flow in the
  dark; then R1, with light and the bound cofactor. That is about 16–25 agent-days, after OL3
  (D212). The rest of the replication is decided after them.
- **The authors' model** (Zenodo, CC BY 4.0) is to run unmodified in GNU Octave, out of process, as a
  reference.
  - Octave 9.4.0 is installed system-wide from the distribution's packages, with the user's leave.
  - **Debian's build could not run it** (18 November 2026, evening). That build has no SUNDIALS, so
    its `ode15s` cannot run at all. Octave's `ode15s` also does not forward the six extra parameters the
    authors' MATLAB call passes. The attempt is recorded in the replication note's §5.4, and the
    route (U5, L11) is put to the user.
  - **U5 and L11 answered** (the same evening). The user: "1. yes, install it 2. Yes, fine".
    - **The install:** conda-forge's GNU Octave 9.4.0, which is built with SUNDIALS, through
      micromamba 2.0.5 into its own folder under /mnt/workspaces, with no system change. The
      release's published checksum is verified.
    - **The adapter:** a run through a separate calling-convention adapter counts as unmodified.
      The adapter passes the six extra parameters the MATLAB way, and the authors' file stays byte
      for byte as downloaded.
      - It is disclosed and qualified by two checks: it passes a test equation through bit for
        bit, and the run's concentrations stay real and non-negative.
      - The second check is needed because Octave ignores the code's `NonNegative` option.
    - **It ran** at 20:04–20:05 UTC, all 250 cases, with both adapter checks passing. M0–M6 all
      pass as registered (the replication note's §5.4).
      - One difference is unexplained: Supplementary Fig. 124's top row.
      - The values are good to about three significant figures.
  - Its outputs are numbers, cited.
  - Its code is never copied into Cells.
- **The perturbation-and-recovery experiment** suggested in the user's reading summary is registered
  separately, after the basic replication works, so that the match with the paper stays
  unambiguous.

## D222: Core and FRs first

2026-11-18, evening. The user: "we should now be priortizing core and FRs".
- **Seats and CPU lanes go first** to two lines of work:
  - **the core-seams pass:** the F, @3, operators, binding and kinds owners, the verification
    owner, and the references for seams A and C;
  - **the feature requests:**
    - the external review's fixes;
    - FR-8's stage 0 (D217);
    - FR-2's retrieval version 1, on B1's split-and-merge kernel;
    - FR-7's loop;
    - FR-15 to FR-17 as scheduled;
    - FR-18's criterion, from the @3 owner's probe.
- **The gate tooling counts as core.** On 18 November three of its faults stood in front of core
  landings:
  - FR's lane-B holder refused a landing because another unit was merely waiting for the lock;
  - a tier list without a tier-2 key failed the measuring script;
  - a fold made against an older record conflicted at landing.

  The tooling moves into `scripts/gates/` as D220 and the user approved.
- **The new seat order, replacing D220's:**
  1. the kinds owner, the moment the registry and the host table land;
  2. the operators owner's next step after F's step terms land: refusal 4 version 1.3, then B1;
  3. the gate tooling;
  4. FR-8's stage 0;
  5. then FR-2's retrieval version 1, FR-7, and FR-15 to FR-17.
- **Waits until the core and FR seats are filled and lanes are free:**
  - the gap-junction bundle's steps 2–5 and the references for D219's two judged comparisons;
  - the self-replicator's R0 and R1, which come after OL3 anyway (D212);
  - OL3.
- **Work already built still lands:**
  - the gap-junction replication's crossrev set, which guards every core landing;
  - OL2, when its gate passes;
  - the self-replicator's reference run (landed, 9f9ffd7f).

## D223: Gates use both lanes, and are sized to what a landing changes

2026-11-18, late evening. The user approved two standing rules: "yes on 1. and 2.". Quality is
unchanged: every check that could see a change still runs.
1. **Both lanes host full gates.**
   - Lane A (CPUs 0–3, 16–19) and lane B (8–11, 24–27) are the same hardware. A full gate runs on
     whichever is free.
   - Until the gate tooling's lane check lands (`scripts/gates/lane_busy.py`, which ignores units that
     are only waiting for the lock), lane B takes at most one full gate at a time, launched only when
     it is free. Otherwise a pinned gate waiting there would make FR's holder refuse.
2. **A gate is sized to the landing's changed files:**
   - **src/ changed:** the full gate, as before:
     - tiers 1+2, G1's 113 worlds, crossrev's eleven sets and IDs;
     - FR's bitwise set for a landing under operators/, kinds/ or @3;
     - the lead's merged check at landing.
   - **No src/ change:**
     - tiers 1+2 and IDs always;
     - crossrev only if a changed file is in the import closure of the crossrev set modules, whose
       worlds come from validation generators;
     - G1 only if a changed file is in the import closure of its harness
       (`validation/results_baseline.py`).

     A check that can't see the change is not run.
   - **Docs only** (docs/ outside docs/library/, and the root's Markdown): the private-term scan.
     docs/library/'s generated pages also run their page tests.
   - The import closures are computed at the landing's head, never guessed. The gate tooling gains a
     scope tool for it.
   - When in doubt, the larger gate runs.

## D224: The user's answers on FR-2's floors, X2, FR-8's ladder and the test suite's cost

2026-11-19, about 11:20 UTC. The user answered the four open questions: "1. agreed"; on X2, "get
adviser on it and then go as you guys think"; on FR-8, "sounds good on the ladder and get adviser on
it"; and on gates and tests, "yes plese stop and also remove tests no longer needed and lets make sure
we are not filling our tests with a lot of regression tests for small bugs along the way, be safe but
testing is already one of teh slowest part of our process". The advisor reviewed 2, 3 and 4 before
these rulings.

1. **FR-2's floors: (b).** The references agent exports the floors and plant rows that the
   engine-side comparison needs into a named interface file, generated from its design file. The
   builder reads only the interface.
2. **FR-18's criterion X2 is adopted as an opt-in energy check that registered and judged runs must
   select.** Development runs keep today's check. Before any code:
   - **An accuracy cap per registration.** X2 subtracts the integration error rather than capping it,
     and today's 2e-3 · F bound was the only cap on it. So each registration that selects X2
     declares its own cap on Σ|a|/F. There is no default, and a run without a cap is refused.
   - **The run-level conditions.** The order condition's median and the held-step cap are whole-run
     quantities. Either implement them as registered, decided over the whole run, or amend them to a
     running form and re-evaluate the saved records before any code.
   - **With X2 off,** today's check and device programs stay bit-identical, so crossrev stays
     identical and adoption needs no renewal.
   - **Scope, fail-closed:** ARS(2,2,2) only, refused elsewhere. The evidence on FR-8's worlds stops
     at 5 ms.
   - **Evidence on main:** the registration, the harness and the results land with the
     implementation.
   - **Qualification:** one run on the boundary worlds against the saved verdicts, not a tier file:
     - the refused arms;
     - the four mixed worlds X1 failed;
     - W1_P4;
     - division_quartered_values;
     - FR-3's plant;
     - cleft_egg.
   - **Corrections to what the user was told on 19 November:**
     - X2's misses are plants below κΣ|a|, so its sensitivity falls as steps grow. They are not
       plants below rounding.
     - The 14 GB and 26 GB figures were the replay harness's raised admission limits, not the check's
       cost. The cost is two extra half steps per checked step.
   - **Owner:** the @3 owner, who also takes `surface_pump_checks.py`.
3. **FR-8's ladder:**
   - **Rung 0, first:** explain the fine engine's order drop through a switch, on a restart window
     near 1800 s, before any later rung is registered. Every later accuracy study is judged against
     that reference. Check whether the drop follows the gate updates or the cue's discontinuity.
   - **Rung 1:** N2 with (a), the exponential junction-gate update, as one new opt-in ID, with G1 and
     crossrev identical when it is off.
     - (b), the review of the inherited 0.125, is a side study if it changes admission only.
     - Rung 1 declares its own accuracy budget and names its energy check. Nothing past 5 ms has been
       measured, so X2 lands first.
   - **Rung 2:** (c), the slow integrator, designed inside the existing long-horizon family. C's
     qual-01 failed on absolute caps on this world.
   - **825 nodes:** whether FR-8's targets include 825-node tissue is settled from the request. If
     they do, face diffusion, which none of (a), (b) or (c) touches, is a rung.
4. **Gates and tests:**
   - **Superseded gates may be stopped.** A running gate whose head has been replaced by a newer
     head of the same change is stopped as a whole unit. Science runs, and any run whose result is
     still needed, are never interrupted. A guard refusal is still held and put to the user.
   - **The cost was measured** on the record:
     - tiers 1+2 hold 589 files, 172 CPU-minutes in all;
     - the 329 files under 10 s take 11%, and the 103 files over 40 s take 57%;
     - files named for fixes or regressions take 0.4 CPU-minutes.

     The time goes on per-file world building and compiling, not on small tests.
   - **The policy aims at cost:**
     - a fix adds a row to an existing parametrized test, or nothing;
     - no new test file for a small bug;
     - a new test that compiles or runs a world states its seconds and its reason at landing.
   - **Tests no longer needed are removed in batches:**
     - each batch has a removal list for the IDs gate;
     - their tier rows are dropped in the same commit, since fold refuses a row whose file is gone;
     - each batch lands after the queued heads that touch those files;
     - legacy tests go with the approved legacy batch.
   - **The larger saving is slimming the heaviest files while keeping their claims,** with shared
     compiled fixtures and smaller worlds, measured before and after. One agent does it once the
     queue drains.

**Amended the same day, about 11:50 UTC (the lead's rulings on X2, after the @3 owner's checks of the
records):**
- **Amendment 2 is not adopted.** It was registered at 11:36:41 UTC. Re-evaluating the saved
  records reproduced the registered verdicts, but the running form refused 47 worlds that the
  whole-run form admits. So the order condition and the held-step cap are decided over the whole run,
  as registered.
- **The cap is per row:** Σ|a|_k ≤ cap·F_k + floor_k at every row, like today's bound.
  - A cap decided at the run's end would weaken as a run grows and would say nothing about the
    early rows.
  - For FR-18's three refused arms, Σ|a|/F peaks at row 1, at 2.3e-2, 5.7e-3 and 2.6e-3, so a
    registration declares at least those values.
  - There is no default. A missing, non-finite or non-positive cap is refused at parse.
- **The switch and the cap's constants:**
  - The switch lives in the execution spec, beside row_checks.
  - The cap's constants have their own type, used only when X2 is on. When X2 is off, crossrev is
    identical, and R1's parse row differs only by a defaulted field's text.
- **The half steps** are taken at the model's step function, so a composite's operators are
  included. The run-level sums travel in the checkpoint, not in the model state. Recorded
  exceptions cover the execution layer's runner, windows, row checks, checkpoint IO and the
  execution spec.
- **The corrections, worded exactly:**
  - X2 missed 15 of 378 plant cases. In each, the plant sat inside the allowance, and κΣ|a|
    dominates that allowance.
  - 14 GB was H2's raised admission limit, and 26 GB was cleft_egg's own trace estimate.
  - The replay runs peaked at 2.2–6.5 GB, including the harness's per-row arrays.
  - The check's work is two extra half steps per checked step. Its overhead inside the engine is to
    be measured.

## D225: The Xenopus bioelectric cancer replication is one of the top three priorities

2026-11-19, about 12:40 UTC. The user checked in an external review,
[docs/lanes/LEVIN_CANCER_XENOPUS.md](lanes/LEVIN_CANCER_XENOPUS.md). It proposes a lane for Levin
and colleagues' Xenopus tumour experiments, starting with Chernet and Levin (2013): local
hyperpolarisation suppressing oncogene-induced tumour-like structures, through a proposed
SLC5A8–butyrate–HDAC route. The user's words: "get an agent to look into this at first to see if we
are missing something in the engine or architecture to make this work, but then we want to have
this as one of our top 3 priorities to replicate with our physics laws and to visualize on multiple
scales in the main engine visualization tool".
- **Priority:** the lane joins the core pass and the FRs (D222) as the third of the top three.
- **First step:** one agent checks the review's claims about Cells and analyses, per experiment,
  what the engine and its architecture already provide and what is missing. Missing pieces are
  named as general, reusable engine models (D136, D144), not built for one experiment.
- **Discussion before building:** the gap analysis and the build options go to the user before any
  code.
- **Replication:** it uses Cells' own physics laws, under a protocol registered before each judged
  run.
- **Visualization:** on multiple scales (embryo, tissue and cell) in the main viewer. The
  visualizer session gets the layers the analysis names.

## D226: The Xenopus lane goes ahead as option B, with a first experiment that can fail

2026-11-19, about 13:10 UTC. The user chose option B of the gap analysis ("1. B"). On whether a
transport reconstruction with conditional tumour-incidence projections counts as XC1's success:
"Yes but get adviser also in on this but lets go". The advisor reviewed it.
- **Option B:** the review's first bundle (XC0, and XC1's local transport: one-cell and two-cell
  preparations, a small mosaic, the matched three-arm replay) runs beside general features that
  other users also need:
  - charged species in the species operators (FR-15, its F2 part, whose first step is the
    `check_impermeant` diagnosis);
  - anatomy as data.

  A decision point follows the matched replay. Cell migration and light-driven pumps stay as design
  notes until then. XC4's regression claim and XC5 wait for a second decision.
- **The regulation-to-behaviour path** (a regulatory state driving cell-kind rates) is logged with a
  design note and not started. It belongs to FR-7's family, and the first bundle does not need it.
- **XC1's success is defined so that it can fail.** Its registration lists every published
  transport-level number it is scored against, and the outcomes that count as failure, taken from
  the review's §6. Examples: justified ionic conditions cannot reproduce the electrical response;
  voltage matches but uptake does not; a mechanism-disruption result is missed. If those numbers are
  few, the first result is reported as "qualified physics plus conditional projections", not as a
  replication. The user is told that before the mosaic is built.
- **Order:** the evidence ledger first. It confirms the matched arms, KRAS in one assay, and the
  effect sizes, including the 1.3-fold figure, which so far rests on one reading. A parse-only
  engine probe of the carrier comes before any protocol is registered or law is coded.
- **Agents and models:** after a safeguard stop on Opus 5.5 in the first gap analysis, the user
  chose Sonnet. Lane-specific agents run on Sonnet. General laws and operators go to their file
  owners, briefed as general features (D136). The lane's code-blind references agent is fresh and
  briefed from the physics alone. Any further safeguard stop is held and put to the user.

## D227: Bare published numbers may be committed with their citation; one rule for commits in the shared checkout

2026-11-19, about 13:30 UTC. The user answered two questions: "1. a as you recommend 2. yes please add
this to agents and give me copy paste for Codex to make this smooth". On the Xenopus lane's first
result, the user wrote "fine with \"not a replication\" we do our best".
1. **Licences:** a paper under a non-commercial licence, such as Chernet and Levin 2013 (CC BY-NC-SA
   3.0), may be cited in the repository with its bare published numbers. An example is "1.32-fold,
   P = 0.01 (Chernet and Levin 2013, Table 2)". Numbers are facts, not the licensed text.
   - Figures, tables reproduced as tables, article text, images, supplements and datasets under such
     licences stay out of the repository. They are analysis-only, as before.
   - Source extracts stay in the workspace.
2. **Commits:** AGENTS.md now asks every agent to commit only its own named paths
   (`git commit -- <paths>`), to check what is staged first, never to commit, reset or stash over a
   merge in progress, and never to rebase, amend a pushed commit or force-push main. The rule exists
   because another agent, the Lean proofs project in `lean/`, now commits to main from this same
   checkout. The lead's landings already assert the staged tree against the checked trial.
3. **The Xenopus lane's first result** is reported as "qualified physics plus conditional
   projections", not as a replication. The ledger found three scorable transport-level numbers, none
   with uncertainties, and incidence ratios without counts (D226).

## D228: Gaps found by real use cases are prioritised as general engine features

2026-11-19, about 13:45 UTC. The user: "that is the good thing looking at real upcoming use cases
find gaps, so lets prioritze those gaps". The Xenopus lane's XC0 design, the kinds owner's probe and
the @3 owner's answers (all of 19 November) found these gaps. Each is a general, reusable feature
(D136, D144), qualified with its own references and tier gate. They are scheduled into the core
pass as its current heads land, in this order:
1. **An electrogenic Na⁺-coupled anion symporter cycle law,** SLC5-type (the kinds owner). Version 1
   is the fuel-free factored form with an integer coupling count. Version 2 is an eight-state diagram
   with voltage-dependent edges. The kinds owner's probe showed it parses, binds and closes every
   ledger on main today.
2. **An instantaneous inward-rectifier route law** on the passive-routes kind (the kinds owner): a
   driving force of V − E_K, conductance scaling with √K_o, and data coefficients in the route's
   declaration. It serves Kir4.1 and other inward rectifiers. Today's channel-law seam sees only the
   voltage.
3. **Cl⁻ as a permeant ion in channel populations** (the H1 seam). The @3 owner's part is small: the
   valence table and its tests. A registered Cl⁻ channel law is the F owner's. Until it lands, a
   Cl⁻-only membrane patch carries a constitutive Cl⁻ conductance.
4. **Charged species in the species operators** (FR-15 F2, the operators owner). It starts with the
   `check_impermeant` diagnosis. Butyrate and serotonin chemistry need it, as does the gap-junction
   replication's microRNA.
5. **Availability schedules** for the cycle kind's general layout (the kinds owner). Today a
   population's availability there is fixed at 1.
6. **A check in the kind contract that each state field's array matches its declared axes** (the F
   owner), with planted kinds corrected. The review's trace-estimate work exposed this.
7. **Later, as design notes until the lane's first decision point (D226):**
   - field-input providers beyond 64 field nodes;
   - a regulatory state that drives cell behaviour (FR-7's family);
   - light as an energy input;
   - cell migration and topology changes.

Each lands through its owner's gate. The lane uses each one only after its qualification.

## D229: The testing plan's three decisions: the compile measurement, stacked gates, and selection for non-src landings

2026-11-19, about 15:35 UTC. The user answered the testing plan's three questions
(/mnt/workspaces/Cells/testing-plan-20261119/PLAN.md, after the advisor's review): "1. yes you can run
any tests that you need 2.yes 3. yes".
1. **The held measurement runs:** the compile, execute and host-check split on a sample of the
   heaviest tier-2 files and G1 worlds. A guard had refused writing its driver.
   - More broadly, the lead and its agents may run whatever tests and measurements the work needs,
     within the CPU, memory and lane rules.
   - A guard refusal is still held and put to the user.
   - The persistent compilation cache stays conditional. It is adopted only if compiling is 40% or
     more of tier and G1 time, and only after its bitwise and memory qualification. It has two
     recorded failures, and its writes are not atomic.
2. **Queued heads may be gated together as a stack** of two or three, after the fail-fast steps
   (the plan's A) are in.
   - The stacked tree is the one that lands, so cross-head clashes are seen before landing. Today's
     three landing-check refusals were all such clashes.
   - On a failure, the stack is bisected with only the failing check.
   - Evidence is recorded per stack, and each head's merge message names its stack's gate.
3. **Landings with no src/ change run a selection of tiers 1+2.** This amends D223 rule 2. They run:
   - the tier-1/2 files that the change can reach, found from recorded runtime imports and file
     reads, not guessed;
   - an always-run guard set: the tree-scanning guards, test_species_sum_sites.py, and any test that
     reads the repository's files;
   - IDs, as before.

   Tiers 1+2 then run in full once a night, and a nightly failure stops selection until it is
   explained. A landing with a src/ change keeps the full gate.
- **The plan's A and B need no decision.** They are built first and qualified by replay before any
  owner uses them:
  - A: pre-lock checks, including a removal list declared before the gate, then the checks under
    the lock in fail-fast order;
  - B: base-side runs reused per main revision, and G1's shards re-planned.

  Crossrev keeps comparing head against base, never against the record. G1 keeps its 113 worlds.

## D230: OL2 and OL3 resume, behind core and FR-1 to FR-10

2026-11-19, about 15:45 UTC. Asked how close the GARD experiment is with real chemistry, the user
answered "lets on OL3", then "and continue OL2" and "but still fr1-10 and core highest priority".
This lifts D222's hold on OL2 and OL3, at low priority.
- **The order is unchanged at the top.** Core and FR-1 to FR-10 keep the first claim on seats and
  lanes, with the Xenopus lane beside them (D225). OL work comes after.
- **Lanes.** An OL gate starts only when the lead sees the core and FR queues on its lane empty. A
  test of free locks alone is not enough, because some core units wait on files before they take a
  lock.
- **Seats.** At the agent cap, the OL builder stops at a clean commit rather than an FR or core
  agent waiting.
- **What lands, in order** ([ORIGIN_OF_LIFE_ENGINE_DESIGN §0.2e](ORIGIN_OF_LIFE_ENGINE_DESIGN.md#02e-the-leads-rulings-for-ol2s-remaining-milestones-and-ol3-19-november-2026)):
  OL2 milestone 1 as built (ol2-engine 9190ae78); then, on one branch, OL2 milestone 2 (the osmotic
  lumen and lysis), OL3 milestone 1 (single-lineage division), OL2 milestone 3 (the shared pool and
  serial transfer, labels and the diagnostic record), and OL5's probe roles.

## D231: FR-7's first closed loop and FR-8 rung 1's three choices

2026-11-19, about 20:50 UTC. The user, on the two open questions: "Get adviser on the two questions
then I go with what yuo guyes think". The lead took the advisor's review, and records these rulings
under that delegation, which covers these two questions only.

1. **FR-7's closed loop (the lane's Q10): (b), the Na/K pump with Na-leak units**
   (`naleak_always_open@1` populations), with a declared synthetic time scale.
   - **Gated on one engine probe before R-loop is briefed.** The probe runs in the world to be
     registered: real population units through membrane state, the pump, and the whole F4
     composition admitted at definition, including the regulator sourced on Na. It measures the
     loop's gain. The stand-in's 0.37 scaled a patch's Na leak rather than population units, and
     the engine's K-unit result was below 0.01.
   - **The synthetic time scale** is one declared geometric number, volume per area, labelled
     synthetic (D217). The probe also checks that the gain is unchanged, that 1 ms is admitted,
     and what a run costs. The real-time-scale world, FR-8's consumer, is the same world.
   - **Fallback, declared now:** if the closed and cut arms cannot differ by more than the
     comparison band, the question returns to the user. The lane does not move to (c), the held
     injection, whose only evidence is NumPy.
   - **Power:** F4's registration has the code-blind references show, blind, that |closed − cut|
     exceeds the comparison band by a stated margin.
   - **Reference inputs** declare the pump's fuel pools and standard state from the start.
   - **F3 does not wait:** its readings are units and conductance. R-chain's and R-clear's
     references are briefed now; only R-loop waits for the probe.
2. **FR-8 rung 1** (validation/long_duration/RUNG1_20261119.md, registered at a28616ba):
   - **The accuracy bar:** the parity caps (|ΔVm| ≤ 20 µV, |Δc|/c ≤ 2 × 10⁻⁴) judge the method,
     and stage 0's adequacy budgets (2 µV, 2 × 10⁻⁵, 10⁻⁵) judge the reference. Stage 0's
     registration defined 2 µV as a tenth of the voltage cap, so these roles were on record before
     rung 0's numbers. Both are reported. Before any new-ID run, the owner checks that the
     intervention reading carries stage 0's peak-response and crossing-time criteria (D217), and
     adds them as a dated §10 entry if it does not.
   - **The threshold:** a step gain of 10, as registered. The cost per simulated second of both
     IDs at dt* is added as a reported reading (D217 lists measured cost).
   - **The energy check:** X2 (`step_doubled_energy@1`) at the registered cap of 2 × 10⁻³, never
     raised. Rung 1 builds no exact booking.
     - **Trigger, recorded now:** if an X2 cap refusal is what binds dt* in Stage A or on either
       reading, seam D's branch X (the exact booking, 2–3 agent-days, the @3 owner's) is built
       before rung 2.
     - It is deferred because on the intervention reading the predicted limit is NaV resolution,
       which an exact booking would not lift.
     - I3 runs X2's plant at the largest step claimed, not only at 1 ms.

## D232: FR-7's scoped exception to D177, and FR-8 measures before it builds

2026-11-19, about 21:25 UTC. The user, choosing among the lead's options (after the advisor's
review):

1. **FR-7: option 2.** The first test proceeds as built.
   - **A scoped exception to D177** covers both surface insertion and irreversible removal: FR-7's
     unit producer (`population_unit_turnover@1`, landed at 7fb27a92) inserts its units and removes
     them itself.
   - **The declared lifetime applies to every unit in a routed population,** including units present
     initially.
   - **The producer's refusal stays simulation-wide.** It excludes recycling (FR-2's trafficking),
     membrane insertion and division even on other populations, and this is documented.
   - **References:** the independent chain and clearance references proceed now. The closed-loop
     reference stays behind the agreed gain probe (D231).
   - **For the later FR-2 design:** specify who owns insertion, and give each population one owner
     for terminal removal, so that a retrieved unit can either return or be destroyed and its loss
     is counted once.
   - Whether recycling prolongs the response remains an open question.
2. **FR-8: option B first.** Run rung 1's registered control, today's time integrator with X2
   enabled, before building anything.
   - **Report:** the largest passing step, what stops the next rung, and wall time per simulated
     second. The roughly 71 ms figure is a predicted charge-stability ceiling.
   - **In parallel,** check whether fine steps around events can run on today's integrator.
   - **Then, by these rules:**
     - if charge stability limits the calm stretch and the proposed method (N2) addresses that
       limit, proceed to A (build N2, then rung 1 as registered);
     - if today's integrator already gives adequate calm-stretch performance and event windows can
       use it, prioritise C (the fine-window executor);
     - if X2's cap binds today's integrator, report the evidence and keep the exact-accounting build
       on hold. The registered build trigger (D231) applies to Stage A or the new integrator's
       limiting rung; a refusal on today's integrator alone does not trigger it.
   - **Rung 0's official verdict stays inconclusive.** The follow-up supports a transient in this
     case. The 3.3 µV figure is the difference from the finest saved trace through one switch.
   - **The 1 ms rule** governs the spacing of the samples bracketing the threshold crossing.
   - **For later downstream use,** the per-arm errors and the reference refinement are retained, so
     that 6.25 µV per arm and 25 µV across four arms can be checked separately from FR-8's 20 µV
     per-trace criterion.

## D233: FR-7's closed-loop world scales its template five-fold

2026-11-19, about 23:02 UTC. The user, choosing among the lead's options after the advisor's review
and the references' measurement: "lets do option 2".

- **F4, R-loop's world (D231), scales the template's half-saturation K and its dose together, ×5:**
  K 0.05 mM and dose 0.5 mM. n 2, the 20 s half-life, basal b_T 0.2 and ε 2 × 10⁻⁶ are unchanged.
  Only c/K drives the cell, so F_T(t), t_clear (260 s) and every non-template row are unchanged. The
  references show that identity before they register.
- **Why:** in F4's 7.5 fL cell, R-chain's template falls under D150 §1.3's mean-field floor (about
  10² molecules per cell) at 243 s, before the cut at t_d = 260 s. Clearance (D ≤ ε) then comes at
  about 64 molecules. The references measured how far replacing that sub-floor tail (set to zero, or
  held at 10² molecules) moves the judged effect, the closed arm minus the cut arm:
  - up to 9.5% at ×1 (R, 10 s after the cut);
  - at most 6 × 10⁻⁵ at ×5. There the floor comes at 289 s, after the cut, clearance comes at about
    320 molecules, and the cut's applied factor F* no longer depends on the tail.
- **The tail is registered as a bounded term.** Both sides run the same mean-field tail, and neither
  applies a floor. The comparison would detect a different treatment: even at ×5, up to about 10
  bands on s at late rows. R-loop registers the ×5 floor table with its rows.
- **The lead's earlier rule is withdrawn.** "1% of the tightest band" was the wrong yardstick: the
  bands measure numerical agreement between two codes running the same equations. The judged effect
  is the yardstick.

## D234: Option 2 of the core-laws roadmap, and gene regulation's design begins

2026-11-19, about 23:29 UTC. The user, choosing among the lead's options after the advisor's review
of the core-laws roadmap (branch core-laws-roadmap): "option 2 as you suggest, lets start gene
regulation as well".

1. **Option 2.** The energy groundwork and mitochondria go to the kinds and binding owners and a new
   mitochondria lane. The operators, F and @3 owners keep D222's order for FR-1 to FR-10 and the
   Xenopus lane (D225).
   - **Kinds owner:** land symporter version 2 and the schedules, and the net-flow step-bound
     follow-up. Then: moved fuel at closure nodes, the cycle kind's trapezoid booking, the Δp readout
     and, for host P's per-complex respiration, chemistry at P.
   - **Binding owner:** registry entries for the nucleotides and the respiratory carriers, then the
     registry moieties.
   - **A new mitochondria lane** writes the mitochondrial laws (new files under `laws/cycles/`, D209)
     and `validation/mitochondria/`. Its first milestone, MT-1, is one isolated cardiac mitochondrion,
     lumped, on @3.
   - **References:** the code-blind Beard 2005 reference, already running, serves MT-2. Fresh
     code-blind agents write the component references, from the laws' appendix of declared
     equations.
   - **Agents stay within the cap of seven.** New origin-of-life work waits for a free seat (D230).
2. **Gene regulation begins with a design note.** D145's hold is lifted for the design: transcription
   and translation as physics, regulatory networks as declared laws, and how they are verified. Its
   options come to the user before any engine code is written. D218's door is unchanged until then.

## D235: FR-8 builds N2 then C; mitochondria on host P; gene regulation's option A

2026-11-20, about 10:53 UTC. The user, on the lead's morning brief: "1. decide with adviser but
probably both in the end", "2. Same get adviser and you choose but we're not in a hurry per se",
"3. yes, get adviser also on this". The lead's choices, after the advisor's review:

1. **FR-8: N2 first, then C, both built.** D232's rule 1 holds: charge stability limits H2's calm
   stretch above 20 ms, also from the calm state at 1000 s (§10.8's probe), and the @3 owner confirmed
   that N2 removes that refusal.
   - **N2 is rung 1 as registered.** The @3 owner builds it. H2's ceiling under N2 is the explicit-rate
     bound on what stays explicit, 292 ms, against 200 ms for the registered gain of 10.
   - **C is required, not optional.** N2 alone is predicted to gain about 1 on FR-8's acceptance
     reading through the cue, which the location rule caps at 1 ms. C, the fine-window executor,
     starts once three things are settled: its files' owner, disjoint from @3's step; X2 across a
     step change, measured; and a dated registration entry.
2. **Mitochondria: host P for MT-1 and MT-2,** as MITOCHONDRIA_DESIGN §3.6, §5.2 and §7 recommend.
   P1′ found no accuracy reason to leave it.
   - **MT-1** runs on today's solver at declared activities.
   - **MT-2 at Beard's synthase activity** adds the cycles and faces to N2's operator later.
   - **The outer membrane and the IMS kinase stay in host P's world.** The code-blind reference
     found a 577 µM outer-membrane ADP gradient and the IMS kinase at 44 times respiration.
   - **K3**, chemistry at P, starts now. Host C, with the three complexes, stays the in-cell host
     (M6).
   - **Still the user's:** the Beard repairs (D209), put as one question with one combined arm's
     numbers.
3. **Gene regulation: option A,** one gene, open loop, deterministic, expression as templated
   polymerisation with its ATP cost. It is judged against exact references only, and starts when seats
   free.
   - **First,** the design note is refreshed against main: the charged ATP set, moieties and moved fuel
     at closure nodes.
   - **The operator's moiety hook** lands with it.
   - **The mitochondria pattern applies:** an equation sheet, a tag, code-blind references, and
     registration before any engine output. A also registers what it does not claim, and includes a
     machine-limited arm with its own plant.
   - **The note's other questions remain open.**
- **Erratum (lead, 20 November 2026, about 11:12 UTC), from the @3 owner's measurement on the N2
  development head.** Item 1's "H2's ceiling under N2 ... 292 ms" is wrong.
  - **292 ms is M1's M term:** the passive patches' membrane charge relaxation at definition,
    3.42 per s. That is a slope conductance, which N2 moves into the operator; M1's ladder says "N2
    alone removes J, M and Mc".
  - **Measured under `imex_ars222_implicit_conductances_n2_alone@0`:** the explicit rate is 2.3e-4
    per s, which admits about 4,384 s. It is set by each species' material relaxation through patches
    and junctions, which N2 adds to its bound.
  - **What binds H2 under N2:** X2's cap and order condition, the accuracy budgets and the step's
    domain checks. None is a definition-time ceiling.
  - **The stage rule:** under N2 it counts the kinds' terms. Today's rule never counted the pumps'
    electrogenic currents, and N2 keeps that.
  - **The choice to build N2 stands.**

## D236: Beard's repairs (frame B, Eq. 24 as run, the balanced supply); FR-7's development chains stopped

2026-11-20, about 12:13 UTC. The user, on the lead's two questions: "1. yes as you suggtest", "2. yes as
you suggst".

1. **FR-7's three development chains are stopped** (cells-fr7-chain-a, -b and -c). Their first worlds
   have maturation stages (m = 3), which compiled and stepped 6–10 times slower than they should
   before the FR-7 lane's fix (fr7-perf 395b80a4). The three queued judged units had already been
   stopped before they started. F3's judged comparison runs from main once the fix lands: about 2–3
   hours on CPUs 6, 22 and 23. The chains' partial outputs are kept.
2. **Beard 2005's repairs (D209's departure), the consistent set in frame B:**
   - **Phosphate:** the appendix's balanced Eqs. 11 and 16, with Eq. 22's proton row counting the
     protons on phosphate.
   - **Eq. 24 restored,** φ_Pi × Eq. 7: the model as the paper ran it.
   - **Eq. 1:** the balanced NADH supply with a held neutral reductant pair, at reference matrix pH
     7.10.
   - **Conditions:** 298.15 K and matrix Mg²⁺ total 5 mM, as already ruled.
   - **The lead's ruling on adenylate kinase,** reported for MT-2: Eq. 18 is written in base forms and
     matched at 3.81 mM free Mg²⁺ (K_base 0.389). That is derived from the paper's active-state
     buffer, 5 mM Mg and 1.3 mM ADP; the paper never states the IMS's free Mg²⁺.
   - **Its cost,** MR1's `host_p_question_arm_ak_base`:
     - rms z 3.72 against the published curves, against 1.40 for the published arm;
     - largest departures at the 12 reported states: ΔΨ 1.31 mV, matrix pH 0.014, NADH's reduced
       fraction 0.020, cytochrome c's 0.004, O₂ flux 2.1%;
     - dissipation non-negative for every process, at the reported states and at 2,000 random states
       with binding at equilibrium;
     - steady states exist and are unique.

     The base-form kinase changes nothing at the reported states.
   - **Next:**
     - the lane retags the appendix with the chosen forms;
     - the component references and MR1 register against that tag;
     - the binding owner adds AMP in beard2005@2;
     - the kinds owner writes the law modules after K3 and K3b.

## D237: FR-20 to FR-22 join the high-priority feature requests

2026-11-20, about 12:52 UTC. The user pasted three requests and said: "then add this to the high
priority list of feature requests". They are logged in docs/FEATURE_REQUESTS.md at **high priority**,
beside core and FR-1 to FR-10 (D222):
- **FR-20, a pulse and washout:** an assembly population's exterior replaced at a declared time, with
  a finite wash bath and the material and energy exchanged recorded;
- **FR-21, a prescribed shell** that owns a lumen and an exchange conductance, independent of the
  membrane's inventory and its binding-site count;
- **FR-22, checkpoint and resume** for the version-2 stochastic assembly runner, qualified around a
  wash.

Each becomes a design note before code (D142), and a general feature (D144). They are listed, not yet
assigned: the agent seats are at the cap.

FR-20 builds on the vesicle-population accounting of the ol3-engine branch, which D230 lands last, so
the order of that landing is put to the user.

## D238: N2's registered target kept; FR-7 lifts the producer's refusal for division; the origin-of-life stack lands now

2026-11-20, about 15:13 UTC. The user, on the lead's and the advisor's five recommendations:
"1. agreed 2. agreed 3. agreed 4. agreed. 5. agreed — sounds good".

1. **FR-8, N2's step: the registered target stays a gain of 10** (200 ms against 20 ms). §6 reads
   N2 alone against it and records the miss if N2 alone reaches 5 (100 ms).
   - **The development evidence:**
     - X2 passes N2 at 20, 100 and 125 ms (§10.14). At 200 ms its order band refuses late in the
       calm stretch, a second-order method leaving its asymptotic range (4 − q ∝ dt).
     - The integration error stays at least 25 times inside the cap.
   - **N2 with C** is registered as a new dated arm before it runs.
   - **125 ms is not offered as a rung:** it was seen passing, so it would be tuned.
   - **The two priced remedies** (stage-wise slopes, a gate-change bound) address start-up, not the
     band, and are not built now.
   - **The "95 times fewer steps" for N2 with C** is a desk count: against C alone, N2 adds about
     4.8 times in steps, at a per-step cost not yet measured.
2. **The gap-junction cancer replication:** a desk note prices FR-15's remainder (junction
   hosting of the charged route), FR-16 and FR-17 when a seat frees, saying which table each
   unlocks:
   - Table 2 (2D, 626 nodes) needs FR-15's remainder and FR-16;
   - Table 1 (3D) also needs FR-17;
   - Table 3 needs a mechanism the preprint does not give.
   Seats are decided on those prices. FR-15 to FR-17 stay scheduled after FR-2's retrieval and FR-7
   (D222).
3. **FR-7: D232's simulation-wide refusal of the unit producer is lifted for division only.** It
   takes effect only with three things:
   - a design note fixing how the producer's pools and history accounts split at division;
   - a code-blind division reference, registered first;
   - worlds without division bitwise unchanged.

   Insertion and recycling stay refused until FR-2's ownership design. The cost is 5–8 agent-days
   across the FR-7 lane, the operators owner and a references agent.
4. **FR-7's measured response (D151):** one channel's abundance against membrane voltage. It is
   conditional on a desk scan finding an open dataset with sourced lifetimes and a usable licence.
   Coupling against conduction waits for U1. The judged run likely needs FR-8's real time scales.
5. **The origin-of-life stack (ol3-engine at 09f4cb58, landing-ready) lands at the next free lane,
   ahead of D230's order.** FR-20 and FR-22 (D237) build on it. Further origin-of-life building
   stays behind core and FR work (D230).

**The order for seats as they free:**
1. the stack's landing;
2. the mitochondria law modules (the kinds owner, after K3b);
3. FR-7's division step;
4. FR-20's design note and FR-22's short controls;
5. gene regulation's G2 references;
6. the gap-junction pricing note;
7. FR-21's design note;
8. further origin-of-life building.

## D239: FR-23 to FR-26 join the high-priority feature requests; the bath recipe's six-order regression

2026-11-20, about 17:24 UTC. The user pasted a verified bug report and four feature requests, and
said "high priority feature request".

**The bug:** `scheduled_bath_composition@1`'s per-species running sum loses a small dose between
large opposite contributions, so its result depends on order. In a 1 pL bath, "+24, −24, +2⁻⁴⁹ mM"
records 2⁻⁴⁹ fmol, but "+24, +2⁻⁴⁹, −24" records 0.
- **The fix**, already in hand (`math.fsum` per species, D148 in place; no registered world
  changes), gains the user's regression test: all six orders give the exact expected target and
  dose.

**The requests** are logged in docs/FEATURE_REQUESTS.md at high priority, beside FR-20 to FR-22
(D237):
- **FR-23:** timed bath changes beside binding sites on distinct finite nodes;
- **FR-24:** binding-site occupancy as an input to reaction rates;
- **FR-25:** a reusable one-gene expression unit, folded into gene regulation's option A (D235);
- **FR-26:** owned state when a cell is replaced.

Each becomes a design note before code (D142) and a general feature (D144).

## D240: FR-20's design approved; the user runs FR-7's data search

2026-11-20, about 17:37 UTC. The user, on the lead's two questions: "1. Small new operator as you
suggest", "2. I'm doing the search myself".

1. **FR-20, the pulse and washout: the design note's recommendation is approved**
   (docs/ASSEMBLY_WASHOUT_DESIGN.md). A new operator, `cells.pool_replacement@1`: a host stop that
   draws nothing, keeps every assembly as it stands, and replaces the pool from a declared source. It
   records the old pool to the sink and the fresh pool from its source, with their free energies,
   and gives relations a pool node. The note's five answers:
   - **Q1:** the wash bath has the pool's own volume.
   - **Q2:** a pulse is a replacement with tracer-containing solution, not an addition.
   - **Q3:** a held tracer concentration is refused.
   - **Q4:** the transfer's osmotic refusal is kept as it is.
   - **Q5:** the name is `cells.pool_replacement@1`.

   The cost is about 2–2.5 agent-days. The origin-of-life builder builds it now, ahead of its own
   repairs (D237's priority). An exposed site that binds in one step is FR-21's ground.
2. **FR-7's measured response (D238 item 4): the user does the search for an openly licensed
   dataset of measured channel lifetimes.** The agents' search was stopped by a safeguard and is
   not retried by any route. FR-7's item 4 waits for the user's source.

## D241: FR-7's measured response gets a public source: Kir2.1 in U251MG cells, for a retrospective comparison

2026-11-20, about 17:59 UTC. The user, after doing the search themselves (D240): "Use option (a)
for the data handoff", with the results.
- **The source:** Ambrosini et al. (2014, doi:10.1093/hmg/ddu201, CC BY 4.0) measured Kir2.1
  membrane-fraction abundance, resting voltage and total-protein decay in the same human U251MG
  model, for wild type and K346T. The variant has more channel protein in the membrane fraction and
  a resting voltage about 6 mV more negative.
- **The second study:** Qile et al. (2019, CC BY 4.0) give a 2.6 h half-life for wild-type human
  Kir2.1 protein in HEK293T cells.
- **The readings:** 12 group means with their plotted SEMs and a sanitized manifest, in
  validation/fr7/data/ (bare cited numbers with attribution; no figure images).

**The scope, in the user's terms:**
- **A retrospective group comparison only.**
  - Record which protein pool each model state represents.
  - Fix the abundance-to-conductance conversion independently of the two voltage means.
  - Compare the predicted K346T-minus-wild-type voltage contrast with the published one.
- **The judged run stays pending** until the mapping from measured protein to functional surface
  units and FR-8's timing are decided.
- **No claim about persistence after a trigger.** It would need voltage through recovery and a
  measured trigger-clearance time.

This gives FR-7's channel target a public-data path ahead of its junction stage (U1).

## D242: Origin of life takes the lipid route, through fuel; the Lean repairs land now

2026-11-20, about 18:25 UTC. Asked how close a break-and-renew run is, the lead gave two routes:
1. GARD on `cells.assembly_lineages@1`, whose G3 and G4 have never run;
2. the lipid simulation D212 asked for. Four pieces are missing:
   - a world that combines catalysis with vesicles, division and the pool;
   - F12's restored futures on @2;
   - an F12 reader for @2's records;
   - the paused Lean repairs.

The lead added a caveat. @2's catalysis keeps detailed balance, so without a drive the vesicles may
relax to one composition and the result could be null; fuel may be needed.

The user: "2. and yes lets get everything working inclduing Fuel", then "and lets get lean repears
done".

- **The route:** the lipid simulation. GARD's G3 and G4 stay unscheduled.
- **The scope, as the lead reads it:**
  - the four missing pieces;
  - then the parts of the official version the lead named in the message the user answered: OL4
    (energy, with fuel), OL6 (the GARD limit and the deterministic representation), OL8
    (oligomers) and OL9 (the first experiment, registered before any judged run).
  - This answers D199's U8 (OL0–OL9 as one programme) as far as these parts go. OL8 cannot start
    before OL4 lands.
- **Fuel starts as a desk note.**
  - It says what of ORIGIN_OF_LIFE_ENGINE_DESIGN §3 already exists in the version-2 family.
  - It gives options for which step fuel pays for. Fuel answers the caveat only if fuel-driven
    steps make or unmake membrane species, as in anchor A5, with member catalysis acting on those
    steps. The options go to the user.
  - It says how its files sit beside the origin-of-life builder's.
  - No fueled world runs before OL5's references for it are registered.
- **The Lean repairs land now:**
  - the three on `ol-lean-repairs`: GARD's pair-consistent leave, the transition-state factor, and
    the lumen's tension formed from the physical area;
  - the declared-lumen crash (`ol-pool-declared-lumen`);
  - the @1 ledger docstring's sink sign. It reached the lead the same evening, and the docstring
    should read ΔΦ = −W + S;
  - `species_exchange`'s depletion remainder, in the robustness batch.

  The origin-of-life repairs gate as one stack, and D230's lane rule is lifted for that stack only.
  A repair is done when the Lean project's own reproducers pass at the landed head.
- **Priority:** D230 stands until the user answers one question: whether origin of life now queues
  on equal terms with the core and feature-request work.

## D243: Origin of life gets one more agent; the rest is the lead's call

2026-11-20, about 18:29 UTC. The lead asked whether origin of life should now compete for agents
and test lanes on equal terms with the core and feature-request work. The user: "just add one more
agent", "then as you see fit".

- **One more agent works on origin of life:** a second builder, beside the first builder and the
  fuel desk agent (D242).
- **The second builder's work** is the break-and-renew development pieces in files that no open
  origin-of-life head touches:
  - the F12 reader for @2's records;
  - the world that combines catalysis with vesicles, division and the pool;
  - F12's restored futures, through a single-lineage checkpoint (rung S) and a branch rule.

  It starts with the plan and price the lead had asked of the first builder. After the fuel note is
  ruled, it builds OL4.
- **The first builder keeps** FR-20 and the Lean repairs, then slice 5, the population runs and
  OL5's probe roles, then OL6.
- **Everything else is the lead's call,** within D230 and D242. Core and feature requests keep
  their claim on seats and lanes, and origin of life may get more as seats free.

## D244: FR-21, FR-23, FR-24 and FR-26 decided by the lead with the advisor; two corrections

2026-11-20, about 19:07 UTC. The operators owner's design notes were merged the same evening:
[OPERATOR_FEATURES_FR23_24_26_DESIGN.md](OPERATOR_FEATURES_FR23_24_26_DESIGN.md) and
[ASSEMBLY_SHELL_DESIGN.md](ASSEMBLY_SHELL_DESIGN.md). The lead put five questions to the user. The
user: "lets go and all the FR question as you and adviser see fit check in with them again". So
the lead decided all five with the advisor, under that delegation.

The advisor saw the options, prices and questions, FR-21's §4.1 and rule 3, but not the notes'
bitwise, test or acceptance sections. The operators owner's own advisor reviewed the notes up to
1952f141. Nobody reviewed the W-or-L comparison.

1. **FR-23: option A.**
   - The site operator's reads are scoped to the outside nodes its populations face, and a
     scheduled dose may not set a ligand below its trace.
   - "Distinct finite nodes" is the lead's reading: a held bath is dosed, and the sites face other,
     finite nodes. The bath schedule can dose held baths only.
   - **Not covered:** a dose into a finite compartment, such as a wash of a well. An outside review
     request is that case, and its gap is being named.
   - The evidence is development evidence, with no judged protocol.
2. **FR-24: the occupied fraction, and amounts as concentrations in the cell (mM),** read through
   quantities the site operator declares in the contract (the note's R3).
   - Coupling @2's programs gain empty site-route arrays.
   - So FR-24 lands after FR-7's judged verdicts are tagged, with a D148 statement and a short A/B of
     FR-7's C2 and C5 worlds on main showing their values bitwise.
3. **FR-26: W, a replacement writer for site populations, unless L is ruled first.**
   - L is one lifecycle for cell replacement and cell division. It is compared in FR-7's division
     note, which D238 already owes, and as a new system it goes to the user.
   - If L is ruled before FR-26's turn, it replaces W. FR-26 waits behind FR-23 and FR-24 on
     `site_occupancy.py`.
   - **Included:** part C′, a linked reaction in a replaced cell.
   - **Not in version 1:**
     - part C, the coupling's states;
     - contact populations, which stay refused;
     - donor copies, which come in version 1.1;
     - templates that change capacity or constants.
4. **Multipliers follow the occupant** (D150). This is a version-1 limit: a newcomer's multipliers
   are constant, so a timed intervention does not reach replaced cells.
5. **FR-21: all of it, sites first.**
   - **Rule 3 is amended** to admit exactly the binding shape (one pool molecule and one declared site
     forming one complex in the wall) under the existing `cells.stochastic_mass_action@1` with
     `count_on_m`. A named law with the same rates would be a second law for one mechanism (D175,
     D210). A named encounter law comes only with a diffusion-limited form.
   - **The shell starts only after the site step lands,** since that step has never run with a
     geometry or in a population.
   - **The shell's own design:**
     - its own entry law, `cells.shell_permeation@1`, with P_s times the declared area;
     - a prescribed wall;
     - one shell type per world;
     - a gated shell gets the gate factor over the gate's own forms, or is refused in version 1.
   - **Sites on bilayer vesicles take area.**
   - **Who builds it:** the first origin-of-life builder, after FR-20.

**Corrections:**
- **D242:** GARD's pair-consistent leave did not land. The in-place repair moved registered @1 bits:
  part 1's `binomial_second.0` and the kernel probe's leave arrays. It was reverted (3dc3b7aa), and
  the revert's message corrects the original commit's claim.
  - The accurate leave becomes `cells.gard_catalysis_pair_consistent@2`, with @1 untouched. Its
    design is a double-double cache, O(C) per event, priced at 1.5–2 agent-days.
  - It is the one Lean finding still open. The first builder builds it after FR-20, while FR-20's
    gates run, and before FR-21.
- **D243:** on the first builder, FR-21 (and GARD's version 2) come before slice 5, the population
  runs, OL5's probe roles and OL6.

## D245: Fuel option (d), a second inheritance reading beside F12, and the review's two gaps; the break-and-renew rulings

2026-11-20, about 19:42 UTC. The user: "Then get adviser with you to decide on the options three
decisions based on the requirements". The lead decided all three with the advisor, under that
delegation. The advisor saw the hand-backs and the fuel note's §2.3, §2.4, §9, §10 and option
(d); the note's desk probe had not reported.

1. **Fuel: option (d), conditional on the desk probe confirming §2.3's condition.**
   - **The chemistry:**
     - fuel recharges a spent building block in the pool (F + S → B + W);
     - the block joins membranes;
     - in the membrane B + L_i → 2 L_i, catalysed by L_i through the transition-state factor;
     - L_i decays to S, uncatalysed.
   - **It runs on today's laws** in worlds declared `condensed_measure: multinomial`, the physical
     worlds' measure (D215). The autocatalytic step is refused under `multinomial_less_one` outside
     probe worlds.
   - **It is registered with its own nulls,** zero drive and β = 0, in the same world. If the probe
     refutes the condition, the choice returns to the user.
   - **Order:**
     1. the fuel agent's fixes and probe;
     2. the note merged and tagged;
     3. OL5's references written from the tag alone;
     4. then the build.
   - Fuel reacting at the membrane (b1) waits for later. Two papers, A9 and A10, join §7.4 as
     reported comparisons once their numbers are checked against the papers.
2. **The measure: (ii).**
   - F12 is kept as the preprint defines it. A second reading, each parent against the next parent
     on the same path, gets its own name and registration and is never called F12. GARD_DESIGN §8's
     readout 4 already asks for it.
   - The species set for H is declared per experiment: the amphiphiles only, without the block or
     the spent form.
   - **Why:** a split breaks only near four or fewer molecules per species, so F12 cannot see a
     vesicle of real size switch composition between fissions.
   - The probe adds how the switching time scales with the molecule count. "No spontaneous break at
     real size" is a possible result, and is recorded as one.
3. **The review's two gaps** (an outside user's tracer-wash request, D244):
   - **FR-27, a timed partial wash of a finite compartment: high.** It is the finite case D244 set
     aside from FR-23. It starts as a short design note by the operators owner, its semantics
     stated against FR-20's pool replacement (D175, D210).
   - **FR-28, binding sites owned by a compartment's surface: normal.** A stand-in gives the same
     numbers today. It queues after FR-26 on `site_occupancy.py`.

**The lead's rulings the same evening, on the second builder's plan:**
- **D243 corrected: restored futures are fresh runs founded from post-fission landmarks.**
  - Single lineages first, with a check of the kernel's rate table at the landmark.
  - The single-lineage checkpoint (rung S) stays for long runs that must survive a stop.
- **D242's fuel line: a step that consumes a held species to make something that enters the
  membrane is fuel.**
  - A held amphiphile exchanging with its own membrane place is OL2's physics, and stays allowed.
  - Development probes of fuel-driven worlds ran before the line was drawn. They count as prior
    exposure for OL9's registration, which uses fresh matrices and seeds, and their results are not
    used.

## D246: FR-27's design, GARD's version 2 and FR-21's admission key (the lead's rulings)

2026-11-20, about 19:50 UTC. These are the lead's rulings. FR-27's design questions fall under
the user's delegation for FR questions (D244), as the lead reads it, and were decided with the
advisor. The others are the lead's own calls on the builders' questions. None is the user's
approval.

1. **FR-27, the wash of a finite compartment** ([note](COMPARTMENT_WASH_DESIGN.md) on its branch):
   - **One mechanism, two executions.** A liquid exchange at constant volume:
     - a fraction f of the well-mixed liquid leaves as a recorded sample;
     - the same volume of a declared buffer enters;
     - everything not dissolved stays.

     FR-20's pool replacement is its whole-exchange execution in exact counts, if FR-20's builder
     confirms the f = 1 booking against `replacement.py` as built.
   - **Ions are declared, never silently left:** version 1 requires `same_as_compartment` ions. The
     sample and supply records list every species.
   - **The mixing heat is computed** in the cleft fix's small-ratio form, not taken as the ledger's
     remainder. A host check holds it non-negative at every event.
   - **The buffer sits at the species' trace.** Faces at an exchanged node stay refused until they
     are measured.
   - **The name is `scheduled_compartment_wash@1`.**
2. **GARD's version 2,** `cells.gard_catalysis_pair_consistent@2` (D244's correction):
   - **The cache:** a double-word cache of βn, exact within a proven 106-bit budget.
   - **Refused at parse** when a world's fission size needs more, through an optional `domain`
     field on rate-factor laws. @1's bits stay unchanged.
   - **Experiments that draw matrices** record each refused draw, and never fall back silently to
     @1.
   - **The Lean project's own driver stays on @1** until that project points it at @2.
3. **FR-21's site binding** is admitted only for a declared site species and a declared complex
   species, never by stoichiometry alone. OL5's registered refusal worlds therefore stay refused.
   OL5's reference parser needs its own amendment before an FR-21 world is registered.

## D247: Breaks both induced and spontaneous; the blocked timing measurement may run; the fuel note is merged

2026-11-20, about 19:58 UTC. The lead asked two questions. The user: "both - yes the agent can run
the timing measurments".

1. **How OL9 tests break and renew: both ways.**
   - The fuel note's desk probe found that a vesicle of real size never switches composition on its
     own. The mean switching time grows exponentially with the amphiphile count.
   - **So at realistic sizes, breaks are induced,** for example by a pulse of the other amphiphile
     through FR-20's pool replacement, and the lineage is then followed for renewal.
   - **In small vesicles of a few tens of amphiphiles, breaks are spontaneous,** as a comparison
     with GARD's regime.
2. **The blocked timing measurement may run.** It is the second origin-of-life builder's tier
   measurement on the timed lane, which a guard refused as "[Unauthorized Access]". If the guard
   refuses it again, the agent stops and reports. It never routes around a refusal.
3. **The fuel note** ([ORIGIN_OF_LIFE_FUEL_DESIGN.md](ORIGIN_OF_LIFE_FUEL_DESIGN.md)) is merged with
   the lead's rulings written into it:
   - (d)'s dividing null;
   - D245's fuel line covering (d0) and held-block worlds;
   - the generational reading's name;
   - this U5 answer.

   OL5's fuel references are written from the note at tag `ol4-fuel-note-2026-11-20` alone.

## D248: Missed wet-lab comparisons are investigated, not tuned away; FR-29 to FR-33

2026-11-20, about 21:10 UTC. The lead checked the Lean project's biological review: its four
drivers, run at main, reproduce its numbers. The user: "all go on the list but you decide with
adviser on the priority". Then, with three requests, the user gave a rule for every comparison with
wet-lab data, and added "add this to your lists".

**The rule, in the user's words:**
- "Use every missed wet-lab comparison to investigate the simulator, the biological model and the
  measurement. Preserve the original prediction, comparator, units, threshold and score. Record
  what the investigation established, who owns the open question and which observation could
  resolve it."
- "One experimental source is enough to propose and prototype a missing mechanism. State what the
  mechanism predicts, give a competing explanation, and identify a fresh measurement on which they
  would differ."
- "Call an observation corroborated when at least two independently collected datasets agree on
  the same quantity under comparable conditions. A paper, its supplement and a later paper reusing
  its samples count as one source. Even independent studies can share an assay bias."

**The list.** The priorities were set by the lead with the advisor. Each item starts as a design
note by an existing owner, with no new agent.
- **FR-29, an optional proton-return mode for ATP-driven proton pumps: normal, started first.**
  - It has the strongest evidence: −13.0 mV measured against −112.40 mV predicted.
  - A held-out test exists in the same table.
  - It goes to the kinds owner after the mitochondria laws' second head.
- **FR-30, Cx43 junctions with two relaxation times: normal, after N2.**
  - The gap-junction replication's gate models Cx45, not Cx43, so it is not raised under D225.
  - A prediction needs a voltage series.
- **FR-31, vesicle rupture during a steady tension hold: low (D230).**
  - Its note comes before OL9 registers, since a rupture is extinction in both readings.
  - It is blocked on rupture rates against tension, and on OL6.
- **FR-32, a DOPC swelling validation record for the water operator: low.** It is folded into the
  next water-operator landing.
- **FR-33, regional labelled-protein readouts: high (D228).** A study is waiting on it. Its first
  step is identifying any missing export field.
- **Not listed:** two signals the review itself called easy to overfit.

**The other two requests:**
- **The turnover defect** is repaired and landed (b4273772). The Lean project's reproducer and its
  six controls at biological rates are being run at main.
- **The protein export for A1** joins FR-25's backlog, beside the RNA readout, with how to recover
  protein made in a chosen window that survives to sampling. The references record that protein
  completed in minutes 60–90 was 7.46 times the net increase.

## D249: The lead finds the Kir2.1 data with the advisor; the turnover request closed; FR-30 raised

2026-11-20, about 21:15 UTC. The lead asked the user for Kir2.1 inputs for FR-7 item 4. The user:
"you have to find data with advsier I dont have it". This lifts D240's hold on the search, for the
lead with the advisor.

1. **What the source already given holds** (Ambrosini et al. 2014, read verbatim; the article and its
   supplement count as one source, D248):
   - **Recording solutions,** for HEK293 and U251MG together:
     - bath 4.8 mM KCl (NaCl 135, CaCl2 1.8, MgCl2 1, glucose 10, HEPES 5);
     - pipette about 149 mM K+ (KAsp 130, KCl 15, K2-ATP 2, MgCl2 1, HEPES 5);
     - at room temperature.
   - **Barium-sensitive currents** (1 mM BaCl2), with a 15 mV junction-potential adjustment.
   - **Fig. 3G,** the current density at −100 mV, n = 6, as bars only.
   - **Fig. S2B,** a representative current density against voltage, one cell per variant.
   - **Not stated:** the configuration, the temperature as a number, capacitance, and any non-Kir
     conductance.
2. **The plan:**
   - **First, the test that needs no voltage.** Fig. 3E's membrane-fraction ratio against Fig. 3G's
     current ratio separates abundance from channel activity. It uses ratios, since the driving force
     at −100 mV (about 13 mV) is below the junction adjustment.
   - **The voltage contrast still needs the Kir share of resting conductance,** which a
     barium-sensitive current excludes. It is either a registered band over the share, or a background
     calibrated on wild type's voltage. That second route spends one of the two means, departs from
     D241, and is the user's call.
3. **The turnover defect is closed.** At main b4273772 the Lean project's reproducer exits 0: 2.0 fmol
   stored and 0.9956673077917628 pJ booked, exactly as expected, with its controls passing.
4. **FR-30 is raised to high.** FR-16's connexin catalogue (F3 of the gap-junction cancer replication)
   names per-connexin constants, homotypic and heterotypic, and the preprint turns on heterotypic
   Cx43/Cx45, so FR-30 inherits D225 as part of FR-16. D248 is corrected accordingly.

## D250: FR-7's Kir2.1 comparison registers a band over the Kir share

2026-11-20, about 21:34 UTC. The Kir2.1 source gives the abundance-to-current link (Fig. 3E
against Fig. 3G), but not the Kir share of the resting conductance. The lead offered two options:
(a) register a band over that share, or (b) calibrate the background on wild type's voltage. The
user: "lets go with your and adivsor recommendatoin for the Kir".

- **The choice is (a).** The registration fixes a band [s_lo, s_hi] over the Kir share and the
  background's reversal E_b before any computation. The prediction is then a band on the
  K346T-minus-wild-type voltage contrast. It fails only if the published contrast (about −5.5 mV,
  combined SEM about 1.0 mV) falls outside the band.
- **This keeps D241's terms:** the abundance-to-conductance conversion uses neither voltage mean.
  It is fixed from Fig. 3G's current ratio (2.03) against Fig. 3E's abundance ratio (1.64), with
  both arms given the same rectification.
- **Registered first:** the test of abundance against current, which needs no voltage. It is
  disclosed as retrospective, since both ratios were computed while planning, and it can fail only
  for a discrepancy above about 2.9-fold.
- **The judged run stays pending** on the protein-to-surface-unit mapping and FR-8's timing (D241).
  A steady-state start, with the engine run as a drift check, avoids the latter.

## D251: A reviewer's protein and channel readout requests join the high-priority list

2026-11-20, about 21:37 UTC. The user relayed a reviewer's checks with "please review and add to
the high priority list (with all the other high priority items)".

- **What the reviewer reproduced:**
  - **The turnover repair** at b4273772: 2 fmol and +0.9956673 pJ, with its six ordinary-rate controls
    unchanged. The lead's own run agrees, and the request is closed (D249).
  - **The development A1 export** (f96a9606): protein-balance errors below 1e-18 fmol over 360
    intervals.
  - **The window survivors** for one well-mixed pool.
- **High priority, under the requests they extend:**
  - **FR-25:** a restart example with a rate change at the join, showing which interval owns the
    event and whether the joined counters reproduce the uninterrupted run. Also, a field identifying
    the population that lost material under age- or region-selective loss. Today none exists.
  - **FR-33:** a maintained compartment-transfer example exporting the donor, the receiver and the
    cumulative loss together. Its control gives the same fading donor signal under transfer and under
    local destruction, with only transfer increasing the receiver.
  - **FR-34 (new):** channel population readouts, meaning surface count, availability and signed
    current at a declared voltage, with sign convention and units. Its control halves availability at
    fixed count and driving force, which must halve the current.

## D252: Correction to D250: the Kir2.1 band cannot fail on today's data

2026-11-20, about 21:44 UTC. D250 said the registered band "fails only if the published contrast
falls outside the band". The FR-7 lane's registration draft shows that, with the Kir share left as a
declared ignorance range [0.1, 0.9], the band spans about −15.6 to −1.2 mV. The published contrast
(about −5.5 mV, 2-SEM interval −7.5 to −3.4 mV) cannot fall outside it. So the band is a consistency
check, not a test. Nothing is tagged.

- **What the source establishes:** a consistent chain.
  - The wild-type-to-K346T decay-rate ratio is about 1.7, 1.5 and 2.3 at 3, 6 and 12 h (Fig. 4B).
  - The membrane-fraction ratio is 1.64 (Fig. 3E), and the current ratio 2.03 (Fig. 3G).
  - Fig. S2B, read by the lead, shows mean barium-sensitive current density against voltage. It
    reverses near −85 to −90 mV, consistent with E_K from the solutions, and K346T's current is about
    twice wild type's at negative voltages and in the small outward hump above E_K.
  - So slower decay, more surface channels and more current agree. But none of these links tests an
    engine prediction sharply, and the decay ratios assume equal synthesis.
- **What remains open:** the Kir share of the resting conductance. A measurement that would resolve
  it is the background conductance, or resting potential, of mock-infected or untransfected U251MG
  cells in comparable solutions.
- **No world is built and no factor source is commissioned** until one link can fail. The mapping
  questions wait too.
- **FR-34's engine items, found by the same desk check,** are on the list: current at a declared
  voltage, an effective-availability record, and per-route flux records for the kinds' routes.

## D253: FR-7's Kir2.1 comparison: a search for the background conductance, then a labelled calibration on wild type's voltage

2026-11-20, about 21:45 UTC. D252 offered three ways on. The user: "2. then 3. and note it well".

1. **First, the lead searches for one measurement:** the background, non-Kir conductance or the
   resting potential of mock-infected or untransfected U251MG cells, in solutions comparable to the
   Kir2.1 paper's. The lead does this itself, with targeted reads and no agent. If a guard refuses, it
   stops and reports. Any value found is quoted with its source, conditions and units, and checked
   for comparability before it narrows the Kir share.
2. **Then option (b):** the background is calibrated so that wild type rests at its measured −70.1
   mV, and K346T's voltage is predicted from the abundance-to-current chain.
   - **This departs from D241,** whose conversion was to use neither voltage mean. Wild type's mean
     is spent on calibration, so only K346T's voltage, and the K346T-minus-wild-type contrast, remain
     as the comparison.
   - **The result is retrospective:** both means were known before the calibration was chosen.
   - **Every record of this result carries that statement,** its source and its limits: the
     unstated recording configuration, the room temperature, and the equal-synthesis assumption.

## D254: FR-7's Kir2.1 comparison stays a consistency check; what would make it a test

2026-11-20, about 21:53 UTC. This carries out D253: "2. then 3. and note it well".

1. **The search (2) found one independent U251 background source.** Ratto et al., Cell Mol Neurobiol
   2019/2020, doi:10.1007/s10571-019-00776-3, PMC11448950, read verbatim. It is © Springer with no CC
   licence, so bare cited numbers only (D227).
   - **Recording:** nystatin-perforated patch; bath 5 mM K+, pipette 140 mM KCl; temperature not
     stated.
   - **Cells outside a wound:** Vm −34.7 ± 1.7 mV (n = 33), 26 of 33 without rectifying currents.
   - **Cells with constitutive currents:** Rm 0.72 GΩ and Cm 29.9 pF (n = 46).
   - It is a different lab and preparation, so it is not corroboration under D248.
2. **It does not make the comparison able to fail.** The FR-7 lane's desk analysis:
   - Nystatin pores pass Cl⁻, so Ratto's cytosol has about 144 mM Cl⁻ against about 17 mM in
     Ambrosini's dialysed cells. The OUT cells' −34.7 mV is the background's reversal in Ratto's
     conditions only.
   - Carried across by a Goldman–Hodgkin–Katz estimate, the background reverses near −37 mV if its
     non-K part is Na⁺, or near −76 mV if it is Cl⁻.
   - The resting conductance gives only an upper bound on the background.
   - With these, option (a)'s band on the K346T-minus-wild-type contrast runs from about −16.6 to 0.0
     mV. It overlaps the published 2-SEM interval [−7.5, −3.4] mV whatever the data.
3. **Option (b), the calibration (3).** It spends wild type's −70.1 mV, departs from D241, is
   retrospective, and carries the configuration (pump taken as 0), temperature and equal-synthesis
   caveats.
   - Over the background reversal's honest range (−69 to −37 mV), it predicts a contrast of −0.6 to
     −7.0 mV. That cannot fail.
   - Only with a Na-type background assumed (about −35 mV) does it narrow: to −6.4 to −7.9 mV at
     Fig. 3G's current ratio 2.03, or −4.8 to −5.5 mV at Fig. 3E's abundance ratio 1.64.
4. **So FR-7 item 4 stays a consistency check.** The chain agrees: slower decay (Fig. 4B), more
   membrane channel (Fig. 3E, 1.64), more current (Fig. 3G, 2.03; Fig. S2B the same at every
   voltage), and a more negative rest. No link yet tests an engine prediction. No world is built and
   no factor source is commissioned (D252).
   - **What would make it a test:** the U251 background's ionic composition (Na⁺ against Cl⁻), or a
     background measured in Ambrosini's own solutions; Fig. S2B's outward hump read as numbers; and
     the configuration of Fig. 3F's recordings.
   - **If it becomes a test,** the route is the passive rectifier with the kinds owner's factor
     source, whose hump relative to E_K matches Fig. S2B; `kir2p1_mh2@1`'s outward plateau does not.
   - Ratto's values join `validation/fr7/data/` as bare cited numbers, with their comparability
     caveats.

## D255: Origin of life and gene regulation pause until tomorrow; their agents turn to core and FR work

2026-11-20, about 22:07 UTC. The user: "I would like to deprioritze origin of life until tomorrow
and also gene regulation - do not stop any tests or such - then use the agents for core / FR work
from all the user/reviewer reqeuest today".

- **No test, gate or run is stopped.** Heads whose gates pass still land. The paused lanes' work
  resumes tomorrow:
  - origin of life: break-and-renew, the fuel references, GARD's version 2;
  - gene regulation: G4 and FR-25's reviewer follow-ups.
- **FR-20 and FR-21 count as FR work** (D237, with the requester's acceptance given today). The first
  origin-of-life builder continues them: FR-20's landing, FR-21's site step, then its shell.
- **The freed agents take today's core and FR requests:**
  - **the second origin-of-life builder:** FR-30's design note (Cx43's two relaxation times, within
    FR-16's catalogue), built after N2 lands; then one of FR-34's engine items;
  - **the gene-regulation agent:** FR-33 (the regional labelled-protein readouts: which export fields
    exist and which are missing, and the transfer-against-destruction example), taken over from the
    FR-7 lane;
  - **the fuel references agent** stops at a clean point and keeps its code-blindness for tomorrow.
- **Unchanged:**
  - N2 for FR-8, first;
  - FR-24, then FR-26 and FR-28, by the operators owner;
  - FR-29's design note, by the kinds owner after its second mitochondria head;
  - FR-34, Kir2.1 and the Ratto data, by the FR-7 lane;
  - the robustness fixes.

## D256: Mitochondria pause too; Fig. S2B read, and FR-7 item 4's options for the user

2026-11-20, about 22:08 UTC. The user: "same with mitochondria, keep tests going and suh but lets
focus on core and fr tonight while I sleep".

1. **Mitochondria pause until tomorrow, beside origin of life and gene regulation (D255).** Running
   gates and runs continue, and heads that pass still land. The kinds owner turns to FR-29's design
   note.
2. **Fig. S2B, read as numbers** by the FR-7 lane as a second reader (from the supplement's embedded
   image, its SHA-256 checked; rows merged at c97f1ab1). This completes D254's record.
   - **These are the six-cell means:** the values at −100 mV equal Fig. 3G's (wild type −7.25 against
     −7.3; K346T −14.70 against −14.8 pA/pF), although the legend says "representative".
   - **The points sit on the command steps** (−140 to −30 mV) within 0.2 mV, so the axis is most likely
     the command voltage, with no 15 mV adjustment.
   - **So it most likely shows barium-subtracted Kir current,** whose true zero crossings (about −88
     and −92 mV) lie near E_K. This doesn't revive item 4: it checks E_K and gives Kir's shape, not its
     share of the resting conductance.
   - **The K346T-to-wild-type ratio** is flat near 1.9 on the inward limb. A fit scaling wild type's
     shape could fail only for an outward ratio above about 5–6 or below 0.5, so the test has little
     power.
3. **D254's chloride point** (nystatin pores letting Cl⁻ into Ratto's cells) is the FR-7 lane's
   inference, made without reading Ratto's paper, and is labelled so.
4. **FR-7 item 4's options, for the user's decision tomorrow.**
   - **Close it:** D238's item 4 is then recorded as unmet, not passed, with a PROGRESS entry and the
     open question's owner.
   - **Change the endpoint** to current at imposed voltages. This is retrospective, has low power,
     and is the user's call, since D241 set voltage.
   - **Get the missing measurement:** each line's barium-induced voltage shift, or mock-cell voltage
     and resistance in Ambrosini's solutions, with Fig. 3F's configuration.

## D257: The Kir2.1 variant panel cannot test abundance against current; item 4 still waits for the user

2026-11-20, about 22:43 UTC. The user found a Kir2.1 variant study (Ross et al., J Biol Chem 2025,
doi:10.1016/j.jbc.2025.110985, CC BY 4.0) and downloaded its supplementary tables. It was offered
with the advice to keep surface abundance and channel activity as separate measurements. The FR-7
lane extracted Tables S1, S2 and S6, which are merged as bare cited values in validation/fr7/data/.

- **What the panel holds:**
  - surface expression with the variant co-expressed with wild type, for 70 variants;
  - surface with the variant alone, for 10;
  - yeast growth for 20;
  - barium-subtracted current density at −50 and −100 mV in HEK293 cells expressing one variant
    each, for 13.
- **Why it can't test current against abundance:**
  - Only one variant (D71Y) has its surface level and its current measured in the same channel
    make-up.
  - Ten of the 13 current lines are null.
  - Every value has been seen, so any test would be retrospective.
  - "Abundance alone" has one parameter, fixed by wild type, so a held-out split has nothing to fit.
  - The two-voltage scale check has no detectable power.
  - The panel holds no K346T and no membrane voltage.
- **What it does show** is why abundance and per-channel activity must stay separate quantities,
  which the FR-7 design keeps.
- **What would make a test:** surface abundance measured in the same single-variant lines that were
  patch-clamped (Table S4's totals, if from single-variant lines, measure total protein only).
- **Item 4's options are unchanged** (D256): close it as unmet, change the endpoint, or get the
  measurement. The user decides.

## D258: FR-29 reads Kettner's full current-voltage curves before any build

2026-11-20, about 22:50 UTC. The lead explained FR-29's issue with the advisor. The user: "1.".
- **Established:** a tightly coupled pump is ruled out. A lumen-pH change from 4.1 to 6.0 moved the
  ATP-dependent reversal by −13.0 mV, where any fixed ratio predicts −112.4 mV.
- **Weak so far:**
  - The return mode's first prediction missed two rows. It is preserved as made (D248).
  - Those rows then shaped the revised form.
  - The remaining held-out row lies between the two fitted rows, so almost any smooth model passes
    it, and the zero-gradient bounds only cap the return's strength.
- **Structural:** the lumen-pH-3.1 bound fails for one saturable return site in every variant. The
  response is nearly flat from pH 6.0 to 4.1, then rises more than 65 mV from 4.1 to 3.1.
- **The competing explanation** is variable coupling. ATP use at the reversal separates them, and
  Kettner does not report it.
- **The choice:** first read Kettner's Fig. 3, the full ATP-dependent current-voltage curves, after
  confirming which conditions it shows. It gives many points across voltages at each pH without
  spending a held-out row. Then decide whether a return mode can work.
- **Kept:** the build stays held; the pH 3.1 row is not dropped from the mode's domain; variable
  coupling stays on the backlog.

## D259: A review's eight findings in FR-33's tracer, G4's readers and the Kir table: fixed before any of their outputs is scored

2026-11-21, about 11:14 UTC. A reviewer, relayed by the user ("review this also with adviser then
deal with as a matter of priority"), reported eight findings. The lead and the advisor found all
eight real, and assigned them that day.
- **Held:** no output of FR-33's tracer, G4's cohort reader or G4's comparison tool is used to score a
  wet-lab discrepancy until its fixes land. G4's dt 1.0 and dt 0.5 results stay unread until the
  comparison is fixed and rerun.
- **FR-33's tracer** (on main; the operators owner):
  1. (P1) the trapezoid cohort update goes negative when a node's step outflow exceeds the sum of its
     endpoint amounts, while the balance check passes. Fix: refuse on a stated resolution bound,
     and check each cohort's bounds.
  2. (P2) the mover check is a deny-list keyed on a species field, so FR-27's wash, which declares
     nodes, was admitted and its removal of label unseen. Fix: fail closed.
  3. (P2) a caller's cohort named `unlabelled` is overwritten on export. Fix: reserved names
     refused, and the serialized cohorts checked at every row.
- **G4's readers** (on gene-regulation-lane, not on main; the GR agent):
  1. (P1) `--product R` selected protein completions by default, overstating new RNA by 66.4×.
  2. (P1) `compare_run` reported zero error for a comparison it skipped. Fix: match by required
     times, with matched and expected counts.
  3. (P2) the known-rate control fails at zero and near-zero clearance.
  4. (P2) a run receipt omitted an untracked script, against the provenance rule. The original
     receipt is kept, with an addendum citing the reviewer's bit-for-bit replay.
- **The Kir table** (on main; the FR-7 agent): (P2) the S2B rows' n = 6 is inferred from Fig. 3G
  and moves to its own field. Any number behind D250, D254 or D256 that used it away from −100 mV
  is corrected by a dated entry.
- **Provenance sweep:** two validation drivers on main record no untracked sources; they are fixed
  in the same class as finding 8.
- **Independent check:** an agent that wrote none of the code reruns the reviewer's reproducers at
  the base and on each fixed head before anything lands.
- **The reviewer confirmed** that the extreme-turnover repair and the restart at a rate change held
  up on replay.

## D260: Until 20:00 UTC on 21 November, core and feature requests only

2026-11-21, about 11:49 UTC. The user: "so lets pause the gene regualatoin work after that check,
lets until 8pm this evening focus on core and FRs nothing else".
- **Gene regulation** pauses after the independent checker's rerun of finding 8 on its branch
  (D259). A gap that rerun finds is recorded for when the lane resumes, not fixed now. Its dt 1.0
  and dt 0.5 results stay unread.
- **Origin of life and mitochondria** stay paused, except their feature-request work (FR-35's
  partial withdrawal, by the assembly owner).
- **Until 20:00 UTC:** the core and the feature requests. That covers FR-33's tracer fixes
  (D259), FR-35, regulated turnover's second-order step, FR-34's declared-voltage evaluation for
  @3's channel populations, FR-30's integration into @3 now that N2 has landed, and the gates'
  own upkeep (the scope map and the crossrev information record).
- **Decisions open for the user** stay open (FR-7 item 4, FR-26's L, FR-28, FR-29, the FR-30
  downloads).

## D261: FR-35's design, decided by the lead with the advisor under the user's delegation (D244)

2026-11-21, about 12:02 UTC, on docs/ASSEMBLY_WITHDRAWAL_DESIGN.md (merged).
1. **The law:** a new operator, `cells.pool_withdrawal@1`, schedule kind `withdrawal` with
   `fraction` in (0, 1) and a `buffer`. `cells.pool_replacement@1` stays as registered (it draws
   nothing and books no heat); `fraction` on a replacement is refused, naming the withdrawal kind.
2. **The draw:** each molecule independently with probability f, so k ~ Binomial(n, f), in
   per-place blocks on the schedule's own stream at draw number w·P_f + j. The counter w and
   FR-22's applied-stops record are one number, or asserted equal on restore. The addresses are
   shown disjoint from the transfer's and the Poisson shear's draws.
3. **The buffer:** integer counts in the withdrawn volume fV; tracer-free means zero.
4. **The booking:** A, FR-27's booking with the discrete free energy. The sink takes F(before) −
   F(kept at (1 − f)V), the work F(buffer at fV), and the mixing heat goes to the heat ledger.
   - That sink is not the sample's own F: it differs by σ = −ln[C(n,k) f^k (1 − f)^(n−k)], the
     outcome's binomial surprisal. The record names the sink field for what it is and records σ
     separately, so the energy exchanged is stated plainly.
   - Shown: heat ≥ 0 per realization, also when the buffer carries the species. Tested: the f → 1
     limit gives @1's bookings with zero heat, and the mean over k matches FR-27's continuum heat.
   - The free energies at fV and (1 − f)V go through the guarded table read.
5. **Capacity (changed from the note):** decided before the draw. The wash is refused when a
   place's pre-wash count plus its buffer count exceeds the capacity (the k = 0 worst case), so no
   refusal depends on k and the binomial is never truncated. The guard stays as a backstop.
6. **The statistics:**
   - The tier test draws on the host at real run addresses, with bands and a χ² test.
   - One engine run's cost is measured after the compile. If a few thousand runs are cheap, that
     ensemble runs once as development evidence across independent streams.
   - The invariant is collected plus remaining equals the pre-wash count, recorded per run.
   - The quarter case gets a variance band (1.5) and checks the collected count.
   - An independence row covers two places with equal counts and consecutive washes.
7. **c_ext:** the buffer's concentration is checked at parse, and the realized pool's drift is
   reported.
8. **The legend and the checkpoint key** are written only when a world declares a withdrawal, so
   existing worlds stay bitwise.
- **Process:** the reproducer's two behaviours are rerun at the base first; the independent checker
  writes the acceptance from the requester's words against the built head.
- **Price:** 1.5 to 2 agent-days, gates excluded. For the requester: the sink term above, and how
  "independent streams" was run.

## D262: FR-30's integration into @3, decided by the lead with the advisor (D244's delegation)

2026-11-21, about 13:31 UTC, on the @3 owner's plan for `junction_series_gates`.
- **State S2:** `junction_gate` [edge] keeps its meaning, the junction's relative conductance; a
  series-law world adds `junction_series_gates` [gate, edge]; `junction_gate` is set to the
  product of the gates wherever they change (computed, never integrated, and checked).
- **Readers:**
  - The junction's own transport applies one factor to every species it carries. So a series-law
    edge refuses any valence-0 species with nonzero junction permeability: its factor would be
    the ionic conductance, and a neutral species needs its own route factor, not built in
    version 1.
  - A kind's passive route on a series-law edge is refused.
  - Partition, cell replacement, the composite adapter's closers, the projective mode and the
    stationary analysis each refuse the law.
- **Scope, version 1:** @3 alone and @3 with kinds. Every composite is refused, at
  `pump_composite_adapter.for_structure` (a recorded exception in the operators owner's file,
  reviewed by them).
- **Grants:** @1's check in `definitions/surface_pump_spec.py`, narrowly (@1 and @2 still refuse
  the law; no existing definition's `to_dict` moves); `models/inner_laws.py` and
  `registry/model_table.py`, as recorded exceptions naming the F owner.
- **Development only:** the law refuses unless its junction declaration carries
  `development: true`. A registered or judged result whose definition carries the flag is not
  admissible. The registry's reserved `qualified` field (D175) is left for a general consumer.
- **Order:** the scaffold first (fields, types, parse, registration, refusals, no physics), shown
  bitwise (crossrev 11 of 11, the guard set, `test_inner_laws`, the IDs check); then the step.
- **Tests added:** a convergence-order row with a planted stale product at one stage; m = 2 with
  the second gate pinned open, reproducing the one-gate trajectory.

## D263: A second review's four findings in the assembly washes, the compartment wash and the shell; FR-35 held until fixed

2026-11-21, about 14:36 UTC. A reviewer's report, relayed by the user ("report"):
1. **A wash with an unlimited tracer source still active.** A full wash (`cells.pool_replacement@1`, on
   main) reported successful accounting while such a source remained active: three molecules bound
   to exposed sites before any bound molecule was released. FR-35's partial withdrawal accepts the
   same configuration. The review asks that the tracer-source check be fixed before FR-35 merges,
   and that the same fix be applied to full washes on main.
2. **Crossing a surface:** a bulk wash refuses tracer crossing a surface through its built-in
   permeability, but accepts the same crossing through a registered route.
3. **A vacuous shell check:** a low-count shell fired a reaction and reported zero detailed-balance
   error after checking zero reaction pairs.
4. **Shared state between runs:** editing one exported check changed the result saved for a later,
   independent run.
- **Held:** FR-35 does not land until finding 1 is fixed on its branch and on main.
- **Fixers:** findings 1, 3 and 4 go to the assembly owner, finding 2 to the operators owner.
- **Independent check:** as in D259, an agent that wrote none of the code reproduces each finding at
  its base and reruns the reproducers on each fixed head before anything lands.

## D264: A tester's six readout findings (FR-24, FR-26, FR-25); their readouts held from scoring until fixed

2026-11-21, about 14:57 UTC. A tester's report, relayed by the user, tested at main 5dcf276a and
gene-regulation-lane 43afa534; FR-24 and the two FR-25 RNA counter issues first.
1. **FR-24 (main):** a receptor-controlled reaction's exported rate ignores the receptor factor. It
   reads 0.000200 fmol/s in all three controls, where the accumulated product shows 0 (empty
   receptors), 0.000080 (40% occupancy) and 0.000200 (coupling disabled).
2. **FR-26 (main):** at a replacement's event time (0.020 s), the observation combines the
   departing cell's substrate with the incoming cell's multiplier, giving 0.00048009 fmol/s. The
   departing rate is 0.00192035 and the incoming rate 0.00050000.
3. **FR-25 (gene regulation's branch):** reversing only the cell declaration order of a two-cell A1
   run changes exported RNA from 1.00e-12 to 1.403e-8 fmol, because the export is keyed by
   position, not by cell and gene ID.
4. **FR-25:** two degradation routes for one RNA give ten loss readings for five sampling times,
   overstating surviving labelled RNA by 64%.
5. **FR-25:** the survivor reader reports 3.32347 fmol labelled where only 1.03321 fmol total
   remains (exact 0.99966), with zero reported grid error.
6. **FR-25:** a NaN or decreasing loss counter returns 100% survival and zero grid error, and a
   reversed labelling window returns negative completions.
- **Held:** FR-24's exported reaction rates at routed reactions, FR-26's event-row observations,
  and FR-25's readers (already held by D259) are not used for scoring until fixed.
- **Fixers:** 1 and 2 go to the operators owner; 3 to 6 to the gene-regulation agent. These are FR
  fixes, inside D260's core-and-FR window.
- **Independent check:** as in D259 and D263, an agent that wrote none of the code reproduces each
  finding at its base and reruns the reproducers on each fixed head before anything lands.

## D265: A fourth review's nine findings; FR-34 reopened for composite worlds

2026-11-21, about 15:30 UTC. A reviewer's report, relayed by the user ("review this with adviser and then
get into high priority"); the lead and the advisor found all nine real.
- **FR-34 is reopened.** The lead had reported it complete, and 121aca27's landing text says composite
  worlds are covered. Finding 1 shows they are not:
  - in a composite with `species_regulated_availability@1` holding one population's factor at 0.5,
    the inner helper given the composite's stored state, controls and layout returns 11.10328 pA at
    −50 mV, where the composite's effective controls give 5.55164 pA (and reproduce the recorded
    0.95264 pA at the cell's own voltage);
  - the composite exposes no clamp method, and the example README tells a reader to multiply an
    observed availability that already holds the factor by the factor again.
  - The fix exposes the calculation through the composite, with its ordinary readout's views, and
    corrects the README. The lead's scope ruling for the effective-availability note (operator
    writes enter through the held value) is to be checked against the stored control and the
    observed field.
- **FR-33 (main):**
  - (2) equivalent pulse times assign different material and can drop a requested sample, because
    the tracer admits a time within tolerance but applies it, and the exporter samples it, by exact
    comparison;
  - (4) a nearly depleted pool still returns negative old material with both checks at zero, because
    the cumulative balance tolerance also decides the resolution test;
  - (5) a repeated region member creates negative outside material.
- **FR-25 (gene regulation's branch):**
  - (3) conflicting rows at one required time can earn a zero error, and six-decimal time keys collide;
  - (7) a valid zero-loss product raises in the cohort reader;
  - (8) the reader resolves a producing chain across all cells, not the exported one;
  - (9) a receipt is called clean while archiving an ignored source; main's fix (c180c1bc) is to be
    merged and checked through G4's entry point. D260 parked finding 9's class for the lane's
    resume; the user's instruction here overrides that.
- **(6) The Lean lane's pulse replay** samples the start of each half-step, so it fails against the
  midpoint rule (a6235d7b). It is the Lean lane's file; it is relayed, and it confirms the midpoint
  record (sampling the midpoints reproduces it to 3.9e-16).
- **Held from scoring until fixed:** FR-34's composite currents and the README's instruction,
  FR-33's tracer and region export, and FR-25's readers (already held).
- **Process:**
  - The independent checker reproduces each finding at main 62ec1cc0 and gene-regulation-lane
    c06a0612 first, and reruns D264's cases on the gene-regulation head.
  - Follow-ups to a held tool now get the checker's rerun as well: finding 4 may have come with the
    tolerance follow-up (1b8017d1), which landed without one.

## D266: FR-27's wash books unchanged ions inexactly at non-dyadic fractions

2026-11-21, about 15:34 UTC. A user's finding, relayed: on main c4570309, in compiled float64 on
CPU, `validation.tissue.wash_schedule_fixtures.well(sites=False, volume=1e6, dt=0.01, end=0.08)`,
replacing 3/7 of the well at 0.02, 0.04 and 0.06 s and refilling with only the tracer at its trace
level, keeps chloride's inventory fixed, but its cumulative collected and supplied amounts differ by
2.98e-8 fmol. Three half-volume exchanges give exact equality.
- **The fix:** an unchanged ion's collected and supplied amounts come from one expression, so they
  are equal exactly at any fraction. Both fractions (3/7 and 1/2) become regression rows at the
  existing balance tolerances.
- **Assigned:** the robustness agent, with the operators owner's review, stacked on the wash's
  surface-path fix (0e8194e0). FR-27's wash counters are held from scoring until it lands.

## D267: Origin of life, gene regulation and mitochondria resume

2026-11-21, about 20:35 UTC. The user, after D260's window ended: "yes lets start all three paused
ones".
- **Origin of life:** GARD @2's gate first (merging main), then the builder's held queue: slice 5
  (labels), the population runs, OL5's probe roles and OL6. A fuelled pulse through a wash needs a
  declared-source option first (D263's version-1 limit).
- **Gene regulation:** G4 lands with the D259, D264 and D265 fixes, after a main merge and its gate.
  The dt 1.0 and 0.5 development runs are then compared again with the fixed comparison, and only
  then read. FR-25's follow-ups come after.
- **Mitochondria:** the lane resumes from its own plan after FR-33's tracer fixes land. Any open
  science choice comes to the user.
- **Unchanged:** the review holds (D259, D263 to D266) stay until each fix lands. The floating-
  junction fix (A) still needs the user's decision.
- **Priority (the user, the same evening: "but still prioritize FR fixes", then "and Frs"):** FR
  fixes and FR work, with their landings, come before the resumed lanes' new work, in agents' time
  and in the test lanes. A resumed lane's gate queues behind any waiting FR gate.

## D268: Lanes paused again for FR work; four FR choices decided with the advisor

2026-11-21, about 20:41 UTC. The user: "so lets pause those three again, get adviser on the items to
choose - then go on the FRs instead of the three paused ones". Origin of life, gene regulation and
mitochondria pause their own work again; FR work takes the agents. Running tests are not stopped.
Decided by the lead with the advisor, under the user's delegation for FR choices (D244):
1. **FR-7 item 4: closed as unmet.** No public data gives a falsifiable test of abundance against
   function: the Ross et al. 2025 panel cannot (D257), and the Kir chain's consistency check (D256)
   is not support. It reopens on surface abundance and current measured in the same single-variant
   cells.
2. **FR-29: recorded as investigated, no build.** The return mode failed its registered test, and no
   form tested fits Fig. 3's curves and the pH 3.1 bound together (D258). It reopens on a difference
   current at vacuolar pH 3.1 to 3.5 under Fig. 3's protocol.
3. **FR-28: option A** (a node owner, counts as for every population; about half a day), built by
   the operators owner after the composite clamp lands.
4. **FR-26's L: not now.** W meets FR-26's acceptance. L, one lifecycle shared with division, is a
   7 to 10 day build to be designed with its first division consumer.
- **Still the user's:** the FR-30 downloads (a Cx43 voltage series); the Kv1.5 density data (D218);
  and the floating-junction fix (A), since one G1 world would move.
- **FR-25:** the fixed comparison over the dt runs is FR-25's own acceptance (induction and decay
  against independent references), so it runs now as FR work, with the follow-ups after.
- **Checking:** the origin-of-life builder, now free, becomes a second independent checker, for
  code it did not write. Each new FR landing needs its acceptance written from the request's own
  words, as for FR-35.

## D269: The Lean lane's biological-disagreement review, routed

2026-11-21, about 20:49 UTC. The Lean lane and its literature search reviewed where Cells' models
disagree with measurements (relayed by the user: "from lean get that to the right places"). Routed:
- **FR-35, FR-30, FR-31, FR-32 and FR-29:** each finding is recorded in its FR section in
  docs/FEATURE_REQUESTS.md as a validation target or a restatement. No build changes now.
- **Shear fission (the assembly owner, origin of life):** summed daughter fluorescence was 0.87 ±
  0.01 of the parent expectation (PMC5876618). Bath tracer and optical recovery are to be measured
  before a 13% molecular loss is assigned; a validation target for the division model, not a defect.
- **Channel currents (the @3 owner and the kinds owner):** matching reversal still left large
  amplitude errors. Red-cell chloride at −59 mV gave −1.17 ± 0.13 against −1.97 mA/g Hb predicted
  (doi:10.1085/jgp.109.2.201); Kir4.1 at 15 mM external potassium gave about −0.59 against −0.385 pA
  (doi:10.2170/jjphysiol.48.71). Both are targets for testing full current-voltage curves, with
  FR-34's clamped evaluation as the instrument.
- **Kv1.5 pH (FR-7's lane):** retention at pH 6.8 was 74.5 ± 1.9% (SEM); voltage alone gives 100%,
  the measured pH shift on the default gate 40.5%, and both measured midpoints 69.5%. The control
  midpoint and pulse protocol are to be matched before the residual is read.
- **Mitochondrial ATP synthase stalls (the mitochondria lane, paused):** the three-proton endpoint
  shift was 0.745 pH unit against 0.74 observed, but four intermediate values sat 0.068 to 0.078 pH
  unit below prediction. Free activities and interpolation errors are to be checked before any
  change of stoichiometry; the measured coupling was 2.9 ± 0.2 H⁺/ATP.
- The full handoff is the Lean lane's PROGRESS.md, in its FR-35 withdrawal checkpoint folder. The
  paused lanes take their items when they resume.

## D270: FR-25's tolerance registration, FR-8's row rule, and the branch triage

2026-11-21, about 21:07 UTC. Decided by the lead with the advisor, under D268's FR delegation.
- **FR-25's registration (the GR agent's plan, approved with five changes).** Each readout's
  tolerance is F x a Richardson estimate of the engine's own step error at dt 0.5, from fresh runs
  at dt 2.0, 1.0 and 0.5 at G4's landed head, with a floor of 1e-9 of scale (the references'
  resolution). It is set per readout and world, never from the gaps to G2. F = 3, after Roache's
  grid-convergence-index convention for an assumed order (to be checked against the source before
  it is cited). The changes:
  1. A readout at the floor is judged against the floor without an order check. Elsewhere an
     observed order outside p +/- 0.5 makes the world inconclusive, and FR-25 does not pass with
     any inconclusive world.
  2. p is declared per world kind and readout class, each with its scheme's reason; heat's order
     is checked first.
  3. One retry, declared now: an inconclusive world gets one finer triple (1.0, 0.5, 0.25) under
     the same rule.
  4. Two tags: the rule before the fresh runs launch, then the table before anything compares to
     G2.
  5. It is not blind. The development gaps were read, and the landed head differs from those runs
     only at rounding; the rule's soundness is that it comes from step error alone.
  - The OL builder judges, recomputing the table with its own code.
  - A pass covers G2's trajectories at dt 0.5, within 3x the engine's own step error. dG and u are
    not exported, and corners and interior points stay with G6.
  - About one agent-day and three CPU-hours; the runs wait for G4's landing.
- **FR-8's section 10.20 reading: its rows are matched to the clock by integer millisecond**, each at
  the clock's own point (section 10.4's Times rule): 2,711 rows. Exact float membership would drop 60
  rows on representation artefacts, including the stretch after 1802.0 that section 10.20 calls
  uncertain. The judge reports the verdict on both sets, the 2,711 (registered) and the 2,651.
  - The dated entry before launch records both counts, the desk figure's correction and the judge's
    ordering fix, and C's near-coincident-event finding with a proposed rule. The fix to
    fine_windows comes after the reading.
  - The run is from a frozen snapshot of 03fe5119 plus the driver commit, as section 10.20 names.
    The second builder re-judges from the frozen outputs.
- **Merges into main.** The visualizer's Versions 52 and 53 (beb6ff1b). The Lean lane's latest line,
  unedited (c6ad8cc4); its catalog cites 3d31a606, which is local until GARD @2 lands.
- **Branch triage.** A read-only triage of the older unmerged branches.
  - Landed: the floating-junction interim note (26059683), FR-7's division note, proposed
    (8e2268a0), P1's section 9 committed before its runs (faf64005), and the tier-3 refreeze
    (2a3166be).
  - Pending with owners: crossrev-renewal (needs a gate; a tier-row conflict); three code-blind
    reference branches (OL5 amendment 7, the XC0 references, G2's published interior sample),
    which wait for their lanes; the 11 November Phase 0 reference runner, which needs a review for
    copied code before landing; and packed-gpu-planner, held for the GPU decision.
  - Ten branches hold nothing not on main. Their deletion waits for the user.

## D271: FR-25's registration amended: heat's order, the order window, and the claim's wording

2026-11-21, about 21:14 UTC, before the rule is tagged. Decided by the lead with the advisor
(amends D270).
- **Heat in the A1-M worlds is declared second order.** Each route's heat is its share of the exact
  total, split by divided-difference potentials, a second-order discrete gradient. Recharging,
  running near equilibrium, shows it (2.47e-7 at dt 1.0 against 6.26e-8 at dt 0.5, order 1.98, in
  pol T=100). The other A1-M classes stay third order (SSPRK(3,3)); A1 stays second order (the
  Strang split of its coupling and the X turnover). No order is set per route.
- **The order window is p − 0.5 ≤ q ≤ 3.5 for every judged readout**, replacing p ± 0.5.
  - Under p ± 0.5, benign superconvergence would have made every world inconclusive.
  - Removing the upper bound would leave the tolerance unboundedly loose. With p declared, it is
    (2^q − 1)/(2^p − 1) times larger than the actual step error, 7× at q = 3 for p = 2.
  - The bound 3.5 is the integrator's order plus the declared margin, so it comes from the scheme.
    It caps the tolerance near 10× the actual step error. Above it, the declared finer-triple
    retry applies.
  - Disclosure: the development orders (a maximum of about 3.2) were seen before this change.
- **The claim is worded "within 3× the step-error estimate at the scheme's formal order"**, not "3×
  the engine's step error". The judge reports, per readout, the observed order and the effective
  factor against the actual step error; these are reported, not judged.
- **The sequence**, so that no tag publishes ungated code: G4 lands; the follow-ups and the
  registration tools land (validation only); the rule is tagged on main; the fresh runs launch from
  that snapshot; the table is tagged; the OL builder judges.
- F = 3 cites Roache's grid-convergence-index convention through secondary sources (NASA's NPARC
  tutorial; Phillips and Roy 2014, J. Fluids Eng.). The 1994 paper itself was not reached.

## D272: Holds lifted as their fixes land; a clock finding recorded

2026-11-21, about 21:21 UTC.
- **FR-34's reopening for composites (D265) is closed.** The composite clamp landed at 07022ddf: the
  composition's own clamped_channel_flux and clamped_kind, at the step's control and layout views.
  The second builder confirmed it independently.
- **D266's wash ion counters are fixed** at 52831912. The lead reran the Lean lane's acceptance
  (ion-counters) before landing: exit 1 at main, exit 0 at the head. Wash runs with ions at any
  fraction need no special handling now.
- **FR-8's section 10.20 reading passed.** The second builder's re-judge confirmed it from the frozen
  outputs and found that judge.json came from the launch snapshot, not the one named. An erratum
  (section 10.24) names each verdict's snapshot before the branch lands.
- **A finding for its own decision:** a clock without fine windows has the same near-coincident
  exposure that C's fix closes for windowed clocks. A decimal event one ulp from i x dt adds a step
  of about 2e-13 s. Extending the refusal would touch every world's clock, so it is not done now.
- **Housekeeping, at the user's word:** ten branches holding nothing not on main were deleted, then
  145 branches merged into main along with 94 idle, clean worktrees. Their tips are recorded beside
  the lead notes. Kept: lean-*, visualizer, branches or worktrees used in the last six hours, one
  worktree with uncommitted changes (core-pass-at3-fr34), worktrees in evidence folders, and two
  whose removal git refused.

## D273: The user's delegation of three decisions, and the hold on the paused lanes

2026-11-21, about 22:14 UTC. The user: "You and adviser decide on 1. - 3. I can help with
downloading papers etc add to this vm - 4. all on hold for now until we have less FR and core
work". Decided by the lead with the advisor.
1. **The floating-junction order fix (A) will be built,** as the next engine item, landing alone.
   It is a defect in the default integrator and in N2, not a missing feature, and it will never be
   cheaper than now: one registered world moves, by 2.6e-11 in a gate, with transfer and heat
   bitwise.
   - It is recorded as a D148 exception under the user's delegation.
   - Three facts gate the go:
     - the fixture tier differences, which may move values only where a junction crosses a
       floating component;
     - whether "never conducts" is static in replacement_padded;
     - the topology scan of FR-30's development host worlds and FR-15's planned junction hosting.
       If either has a conducting crossing junction, (A) lands before that FR is judged.
   - The @3 owner prices it. Above about two days, the fallback is a parse-time refusal of
     conducting crossing junctions.
   - Its landing stops unless all of these hold:
     - crossrev differs only for replacement_padded;
     - G1 moves only that world, with transfer and heat bitwise;
     - H2-N2C's arm reruns bitwise against its frozen rows;
     - the new baseline matches the old by digest for every other world.
   - The second builder reproduces the orders at base and head.
2. **FR-25's follow-up 3, age- and region-selective loss, is not now.** It lies outside FR-25's
   request, and the cohort design builds it when a study needs it. It is FR-36, which reopens on a
   requester's readout needing age-dependent loss.
   - **FR-33's two-way tracing is approved: D1, label families in the species registry, with the
     label-row route** (the kinds owner, 1.5 to 2 agent-days, after the binding guard). FR-33's
     request is labelled protein moving between synapses, which is two-way transport. No
     host-side patch can trace that through diffusion, while the engine's own linear laws trace it
     exactly on checked label rows. Every world stays bitwise. No more host-side tracer patching.
3. **Papers.** The user downloads them into /mnt/datasets/Cells/papers/incoming/<paper>/, outside
   the checkout. They are never committed; non-CC sources give bare cited numbers only (D227).
   - First: Lin, Crye and Veenstra 2003 (Circ Res, doi:10.1161/01.RES.0000093379.61888.35), for
     FR-30's voltage series; and Maverick and Tamkun 2022 (Biophys J 121:755,
     doi:10.1016/j.bpj.2022.01.021, PMC8943702), with its Supporting Material, for FR-7.
   - Fallbacks: Desplantez et al. 2004 (Pflugers Arch, doi:10.1007/s00424-004-1250-0), Snipas et
     al. 2020 (Biophys J, PMC7642245, with Supporting Material) and Moreno et al. 2002 (Circ Res,
     doi:10.1161/hh0402.105667).
   - Each benchmark is registered before anyone opens its paper, as FR-29's was: a held-out split
     within the one paper (labs cannot be pooled), the judged observables and the pass rule, tagged.
     One agent extracts, another fits without the held-out file, and a checker scores. Anything
     already read is disclosed.
   - **A correction to D268:** FR-7 item 4 is not closed. D268 named its reopening condition,
     surface abundance and current measured in the same single-variant cells, and Maverick and
     Tamkun 2022 meets it (TIRF channel counts, gating charge and conductance in the same HEK
     cells), as the 14:27 search had logged. Item 4 waits on that paper; its test is registered
     first, disclosing that the headline result was already read.
4. **On hold:** origin of life, gene regulation's own lane work and mitochondria stay paused until
   FR and core work lessen (the user). PROGRESS carries a count of the open FR and core items, so
   that "less" is visible.
- Also landed this evening: C's near-event refusal for windowed clocks (c65dbfa5).

## D274: FR-37, sampling an unevenly mixed liquid, added at high priority

2026-11-21, about 22:34 UTC. A user's feature request, relayed by the user ("add to our high priority
feature list"): a draw from chosen parts of an unevenly mixed liquid, with a synthetic two-region
test (8 and 2 fmol in two 100 pL regions; three collection cases) and the question of which inputs a
user must declare and which Cells can calculate from the collection port, flow and timing.
- It is FR-37, High.
- The operators owner, who built FR-27's wash, takes the first step: whether existing operators
  represent the draw, shown as a runnable example over the three cases with the request's
  accounting, plus the inputs analysis. If something is missing, it names the smallest addition.
- An independent checker writes the acceptance from the request's words before anything lands.
- FR-28's landing after G4 comes first.

## D275: FR-7 item 4's registered test scored inconclusive; no build now

2026-11-21, about 23:07 UTC. The test was registered before the paper was read
(fr7-item4-registered-2026-11-21), extracted and sealed (fr7-item4-extraction-sealed-2026-11-21),
predicted blind (fr7-item4-predictions-2026-11-21) and scored by the second builder.
- **Result:** d = −0.381, Welch's 95% interval [−0.656, −0.105], against ±ln 1.25. That is
  inconclusive. Its direction agrees with the paper's finding that conductance per channel falls with
  density.
- **Information only:** a declared conducting-fraction form predicted the held-out cells better (rms
  ln error 0.272 against the chain's 0.441).
- **Decisions:**
  - FR-7's chain is unchanged, and D218's refusal stands with its restated reason.
  - Item 4 stays open.
  - A conducting-fraction law is a candidate general model. It would need its own registered test on
    data not used here: other cells, another paper, or the same paper's Kv1.4 family if it is
    independent. Under D273's hold it waits.

## D276: FR-30's benchmark on Lin 2003 is undetermined by its registered rule; the fallbacks are registered before they are read; fix (A) goes ahead

2026-11-21, about 23:13 UTC, with the advisor.
- **Lin, Crye and Veenstra 2003 reports single-exponential decays only.** That meets the
  registration's "undetermined" condition: fewer than two held-out voltages carry both relaxation
  times. The checker confirms it. Lin's held-out file stays sealed, and nothing is reinterpreted
  after the fact.
- **The fallbacks:** the @3 owner amends section 13 before anyone opens them. The same split, judged
  observables and pass rule apply in a fixed order: Desplantez et al. 2004, then Moreno et al. 2002,
  then Snipas et al. 2020. Each is extracted only if the one before is undetermined. The amendment is
  tagged before any extraction.
- **Fix (A) goes ahead** (amends D273). Its price is about 2.5 agent-days with charged kind routes
  refused on crossing junctions in version 1; including them adds about a day, when FR-15 needs it.
  - D273's two-day threshold is withdrawn. It assumed the parse-time refusal was a cheap route to the
    same guarantee. Facts 2 and 3 show it is not: it would refuse the @3 conducting fixtures and
    FR-30's development host, and it would have to evaluate replacement_padded's formation lag at
    parse.
  - **The three gating facts:**
    - no tier verdict depends on the moved values; the one changed test counted the prototype's extra
      solves;
    - "never conducts" is declared;
    - FR-30's development host is affected, and FR-15's planned hosts are not.
  - **Added stop checks:** every frozen bitwise baseline (gate.sh, FR's landing set, the OL
    invariance gate) is shown unmoved or renewed; the kinds refusal's reach is scanned first;
    test_field_floor_held passes unedited, and existing test bodies stay as they are.
  - The second builder reproduces the orders at base and head.

## D277: Overnight delegation, and the order in which paused lanes resume

2026-11-21, about 23:24 UTC. The user, going to bed: "good luck with the FRs, lean and core over night.
you decide with adviser this question and the ones overnight except something significant", and
"if there are free agents, I guess the FR list will take a while then start, mitochondria and gene
regulation and origin of life last".
- **The held junction study runs as option (a),** three plain commands. That removes the ambiguity
  the safety check flagged, without overriding it. If one is refused again, it waits for the morning.
- **Decided overnight with the advisor:** what is already decided runs without asking.
  - FR-25's rule tag, fresh runs, table tag and judgement, including the declared retry.
  - FR-30's next paper in the registered order, after the checker confirms the one before is
    undetermined.
  - Landings whose gates pass with no undeclared movement.
- **Held for the user (significant):**
  - a gate where crossrev or G1 moves an undeclared world;
  - what to build after a failed or inconclusive verdict (the verdict itself is recorded as scored);
  - any engine build not already decided: FR-37's advection, a conducting-fraction law, D2, kinds on
    crossing junctions, the unwindowed-clock refusal;
  - deletions, a content refusal, and a privacy-scan hit.
- **Lane order:** FR and core work first. G4 takes the first free test lane after FR-28.
- **Paused lanes resume only with free agents, in this order:** mitochondria, gene regulation's own
  work, then origin of life last. Desk work first; nothing of theirs takes a test lane ahead of the
  FR and core landings.
- **The Lean lane** publishes its own work. The lead scans its commits after they land and does not
  merge its branches tonight.

## D278: FR-25's registered acceptance scored inconclusive; the next step is the user's

2026-11-22, about 01:53 UTC. The registered sequence ran as D270 and D271 set it:
- the rule was tagged before any run;
- the fresh runs came from the tagged snapshot;
- the table was tagged before any comparison;
- the declared retry's table was tagged before its comparison;
- the OL builder judged independently.

**Result:** 28 of 32 worlds-by-set pass, every judged readout within 0.40 of its tolerance. 4 are
inconclusive after the one declared retry: A1 at both test instances (order 3.69, above the cap) and pol
T=100 at both (order 2.40, below p - 0.5). No world failed. Under the registered rule FR-25 is
inconclusive, recorded as scored.

**Coverage:** G2's per-move ΔG and A1's u(t) are published but not exported by the engine, so a pass
would not cover them. The lane README's claim that engine_run exports every readout of the sheet's
section 6 is corrected to match.

**Held for the user (D277):** record FR-25 as inconclusive, or register a revised rule before any new
runs, or bring ΔG and u into scope with a later registration.

## D279: OL5's probe roles scored: 6 of 10 registered rows pass, 4 fail at the registered 1e-12 precision; the next step is the user's

2026-11-22, about 06:42 UTC.

**How it was judged.** The judged driver run came from a clean frozen snapshot of main 67bb0bfe
(manifest c0a5ee55...). The second builder wrote the adapter from FORMAT_OL2.md alone, without opening
the engine side's code, and ran OL5's code-blind harness2.

**Result.**
- Pass: OL2-2, OL2-5 (all 22 declarations refused), OL3-1, OL3-3, OL3-4 and OL3-5.
- Fail at the registered tolerance of 1e-12:
  - OL2-1: forward_form's log residual is 5.07e-12;
  - OL2-3, OL2-4 and OL3-2: event times differ by up to 3.8e-12 relative.
- Every law-level check passes. Channels, counts, slots, keys, draws and bookings replay exactly, and
  the time differences follow from the rate differences through tau = -ln(u)/a0.
- A planted partition-count error failed, as it should.

**The adapter's readings** where FORMAT did not fix the mapping (R1 to R8) are listed in its docstring.
Two of them changed closure verdicts:
- R7: a non-splitting drawing attempt books zero terms;
- R8: a lysing step's heat includes the release.
FORMAT is to state these.

**Held for the user (D277):**
- whether the engine's rate arithmetic should match the references' forms to 1e-12, which is an engine
  change;
- or whether a revised tolerance is registered, which would be after the fact and must be disclosed.

Recorded as scored. Evidence: the second builder's review folder, ol5/ (ol5_verdict.json and the
adapter, with sha256s).

## D280: The user's decisions on the overnight holds

2026-11-22, about 10:22 UTC. The user: "OK on the disc cleanup. 1. Agreed 2. Lets search for other
sources to get FR-30 working, I don't have time in this process to contact authors... 3. agreed 4.
Agreed 5. Agreed 6. Agreed 7. as you and adviser suggest", answering the lead's and the advisor's
recommendations.
1. **FR-25:** one more registered finer triple (0.5, 0.25, 0.125 s) for the four inconclusive
   worlds-by-set (A1 and pol T=100 at both instances), under the same window and F, registered and
   tagged before the runs. After it, the verdict is final. The cap is not loosened. dG and u stay out
   of scope.
2. **FR-30:** search for other sources: a paper or dataset with two-exponential step decays of
   homotypic Cx43 at four or more junction voltages. The search is metadata only and reads no values;
   any candidate is registered and sealed before it is read. No contact with authors. FR-30 stays
   development-only until a benchmark passes.
3. **The face-heat booking: F2.** An opt-in exact booking under heat_bookings, with no registered world
   moving; its note says what heat a label family's rows book. F1 comes only after an MG0c rerun.
4. **FR-33 in-cell:** a short priced note on the cheapest of the three blocks, and a question to the
   requester, through the user, whether two regions joined by a face meet their need. No build yet.
5. **MT-1b:** R2, a fresh code-blind integration, is the judged reference. Two facts come before the
   other choices: whether any judged readout depends on the IMS binding equilibria, and the CPU cost
   at the proposed activity range. The lane's owner reviews the draft.
6. **OL5:** the three checks run first: exact forward forms, event times from the references' rates,
   and R7 and R8 confirmed from the engine's code. No fix and no tolerance change until they report.
7. **Small items wait.** The one exception is extending C's near-event refusal to clocks without
   windows: scan the registered worlds first, and add the refusal only if none is hit.
- **Disk cleanup approved:** the listed scratch copies and idle worktrees are removed. Old run folders
  are archived to /mnt/datasets with a link left at each old path, so cited paths still resolve.

## D281: OL5's precision fix, (a) plus (b), approved; FR-25's final triple from one snapshot

2026-11-22, about 10:29 UTC.
- **OL5's precision fix.** The user, "lets go as you suggest a + b", on the lead's recommendation after the
  checks. The four OL5 failures are the engine's arithmetic, not conditioning: the references are exact,
  the activities come from log-factorial table differences, and the osmotic ΔF from a difference of large
  energies.
  - (a) computes ln ff(n, k) as a direct sum of logs (k <= 3) in mass_action and exchange.
  - (b) computes lumen.delta's ΔF_osm incrementally with log1p/expm1.
  - (a) moves OL1's probe bits, so OL1's probe set is renewed in the same landing as a declared
    renewal, and OL1's registered rows are rerun on it. Invariance steps 1 to 4 stay bitwise.
  - OL5's judged run is then repeated and judged by the unchanged adapter at the registered 1e-12, with
    nothing loosened.
  - R7 and R8 are confirmed from the engine's code, and FORMAT now states them (1dcdda1b), so D279's 6
    passes stand.
- **FR-25's final triple** (registered at 97c6359c) runs all three steps from one frozen snapshot of the
  tagged main, rather than mixing in earlier runs (the lead's call on the GR agent's question).

## D282: FR-25's final verdict: inconclusive under the registered rule, 30 of 32 pass, none failed

2026-11-22, about 11:26 UTC. The registered sequence (D270, D271, D280) is complete.
- The rule, the table, the first retry and the final retry were each tagged before their comparison.
- The final retry made pol T=100 ready, and it passes at both instances.
- A1 stays inconclusive at both instances. C_tx_3's observed order moved 3.94, then 3.69, then 1.49.
- 30 of 32 worlds-by-set pass, and none failed. Under the rule FR-25 is inconclusive, and the rule
  makes this final.
- A1 carries the request's induction and decay under the regulator switch, so the request's central
  claim is not judged. The passing worlds cover the chains' amounts, extents and heats against G2.
- Any further test of A1 would be a new registration after these results, and is the user's decision.

## D283: Near-event times snap to the clock's instant on clocks without windows

2026-11-22, about 12:35 UTC. The user: "get adviser in on both those question but we want to be ambitous".
Decided with the advisor: option 2 of the three the @3 owner priced after the extension's gate failed,
reversing the lead's recommendation to drop it.
- **The rule:** on clocks without windows, an event within the clock's same-instant tolerance (4 ulps) of
  a coarse point is that point.
  - One predicate serves every on-the-grid check: events, control schedules, label switches, and wash and
    intervention times.
  - An event just outside the tolerance that would still make a degenerate step is refused as an author
    error, in a band the owner states.
- **Windowed clocks:** the owner either states why they refuse rather than snap, or adopts the same rule.
- **Not silent:** the record carries both the declared and the applied time, and the fingerprint stays on
  the declared definition.
- **Checkpoints:** a checkpoint written on the old grid is refused or handled on resume.
- **First, a scan** of the worlds that validation drivers build behind judged results (FR-25, FR-8, MG0c
  and others). A hit goes back to the user.
- **What moves:**
  - no registered world is affected (the extension's own scan);
  - the seven test files' worlds lose their one-ulp step and move at rounding.
- **No opt-in strict mode** (option 3).
- **Order:** it lands before FR-38's engine piece, which adds grid consumers.

## D284: FR-38 at full scope, finishing with a registered comparison

2026-11-22. The same words, decided with the advisor; the scope is the gene regulation lane's full path
plus two pieces.
- **The engine piece** goes in `templated_polymerisation@1`, in place under D148, with a sheet amendment
  tagged before code:
  - a terminal hold per chain, split by p into two fate rows, with exact energy and no driven work;
  - the machine held or released, as a declared per-chain option;
  - p from a constant, a schedule or a state factor, its source recorded;
  - declarable initial hold occupancy;
  - counters and a per-producer ledger;
  - producer identity across restart.
- **The cohort, two ways:**
  - release into label rows by schedule (D1);
  - recovery from the counters, on the host.

  The two must agree. The hold's occupancy carries a class axis (size one by default), so a label switch
  can sit at completion or at release.
- **The observation reader** goes in `src/cells/assays`:
  - per-copy detection thresholds, with the copy distribution a named input;
  - roster denominators that keep IDs;
  - named two-colour statistics.
- **Law form:** the sheet states it, including any affinity factor, and the acceptance world states its
  distance from the requester's far-from-equilibrium limit. Amounts and potentials are not chosen to hit
  a tolerance.
- **The finish:** a registered comparison against code-blind references.
  - Its rule is tagged before the runs, and disclosed as written after FR-25's outcome.
  - Until then, the routes are development status.
- **Waiting on the requester:**
  - (c) what "replacement" means, and (e) whether the cohort is marked at completion or at release; these
    block only their own pieces;
  - (a) is covered by the option;
  - (b) keeps the default, no binding energy;
  - (d) defaults to one gene per producer.

## D285: OL5's second judging, after D281's precision fix: 9 of 10 rows pass

2026-11-22, about 13:14 UTC. The second builder re-judged OL5's probe roles with its unchanged adapter, at
the registered 1e-12 precision. The run was frozen from main e6571f88, which carries D281's fix (a)+(b);
its manifest sha256 is 5cc8f280….
- **The verdict file says this is a second judging,** after an engine fix prompted by the first. D279's
  6 of 10 stands as the first result. Verdicts: verdicts-e6571f88.json, sha256
  2598e017131773d741e462a027fc912f71fe44acf338e56f01c54c592fda1db9.
- **Three of the four earlier failures now pass:**
  - OL2-1's forward log residual is 4.4e-15 and 1.0e-14 (it was 5.07e-12);
  - OL2-4's and OL3-2's event times replay exactly.
- **OL2-3 fails, on a convention, not a residual.** Its event times now match exactly. That uncovers a
  difference that the first judging's list, which stopped at five time differences, had hidden: the
  lysing event's pool.
  - The engine records the step's own pool, [30, 0], and the released molecules separately: 1,470 of L1
    and 61,178 of S.
  - The references expect the pool after the whole event, [1500, 61178], which is the same total.
  - FORMAT_OL2 states R7 and R8 but is silent on this pool. A reading R9 (the lysing step's pool includes
    the returned molecules) makes OL2-3 pass. That check is information only and is not scored.
- **The result stands at 9 of 10.**
  - FORMAT_OL2 states R9 next, so that any later judging reads it.
  - A third judging would be a new registration after these results, and is the user's call.
- A planted failure (the partition probe's eq_N5_k3 + 1) fails, as it must.

## D286: The Lean lane's biological findings go into the high-priority list

2026-11-22, about 13:32 UTC. The user relayed the Lean lane's findings with "from lean get into high
priority". The evidence branch was merged unedited at 81916b5d.
- **FR-31 goes from Low to High.** Karal and Yamazaki's tension series is the data it was waiting for.
  The next step is a design note shared with FR-39, then a registered test of a declared rupture law,
  fitted on the end tensions and predicting the middle. The middle values were read before registration,
  and that is disclosed. OL6 remains a dependency.
- **FR-39 (new, High):** a vesicle that survives transient pores, with partial cargo loss.
- **FR-40 (new, High):** a single-ribosome translation timing benchmark. The 406 s observation is kept,
  and the speed comparison stays unscored until reconciled.
- **FR-41 (new, High):** vesicle shrinkage validation records. One agreement is unfitted (24.56% against
  about 25%). Small-osmole retention stays open.
- **Owners:**
  - the FR-31 and FR-39 design note goes to the OL builder, at the desk;
  - the FR-40 desk note goes to the gene regulation references' author, from the sheet's laws;
  - FR-41's search waits for a free agent.

## D287: Vesicle pores (FR-31, FR-39): the user's four decisions, and the lead's rulings

2026-11-22, about 14:25 UTC. The design note is docs/VESICLE_PORES_DESIGN.md (64e9f8e7).

**The user chose:**
1. **Phase A (FR-31, rupture under a held tension): go, with code-blind references.**
   - A laws sheet, tagged before code, written from primary papers read directly.
   - The engine build, and references in parallel.
2. **A blind test, plus a search.**
   - The six points already read (Karal and Yamazaki, 25 °C and 32 °C at 7.0, 7.5 and 8.0 mN/m) are fit
     rows, reported as a disclosed comparison with no pass or fail. Both classical forms fitted on the end
     tensions over-predict the read middle, by 14% to 28%.
   - The held-out set is the figure's other temperature columns. The sheet states how the prefactor and
     line tension depend on temperature, with sources, before extraction. The tolerance (the stated
     standard errors at their small n, plus a declared digitising error) is fixed before a sealed
     extractor reads them.
   - The Lean lane has already viewed the figure, and that is disclosed. No Cells agent opens the
     Karal PDF before then.
   - A metadata-only search for another tension series runs alongside.
   - Given the in-sample misfit, a blind failure is likely. It would be recorded, and the law would ship
     as development status.
3. **A held tension becomes a general, declared boundary** (cells.tension_hold@1). It is a work source,
   with a named payer and a work column, as shear has (U2, D199).
4. **OL6 comes right after Phase A,** with the same owner, then FR-39's pore episodes.

**The lead's rulings, with the advisor (the user may overrule):**
- **The law:** line-tension nucleation only. Opening forms an event pair under it, so there is no second
  exemption, and the exponential form is not built into the engine.
- **The hazard is per membrane area.** A per-vesicle rate belongs to a preparation.
- **One line tension per composition,** shared by opening and the open pore's dynamics.
- **Exact-event worlds** get rupture only. Transient pores need OL6.
- **sigma_max stays** as registered in every world. In worlds with pores it carries its own cause label
  and count.

## D288: The user's decisions on FR-38's labels, FR-41, MT-1b and the optional re-tests

2026-11-22, about 14:43 UTC.
1. **FR-38's labels are rebuilt under FR-42.**
   - FR-38's engine core lands as development once its gate passes, with its class rows (K > 1) marked
     not neutral.
   - FR-42's share-based labels replace those rows, and FR-38's registered comparison waits for that.
   - Erratum B (81fc3ebb) retracts erratum A's "physical" for a neutral label's departure and marks
     route 1 provisional. Route 2, the counters through cohort.py, stands: it reads the run's own
     per-molecule loss.
2. **FR-41: Akui et al. 2021, with Ahumada et al. 2015 downloaded by the user.**
   - Akui is a sealed extraction and a disclosed, weak test. Its licence (CC BY-NC-ND) allows analysis
     only, so only bare cited numbers are used, never committed material. Its volumes come from other
     experiments.
   - Ahumada is evaluated when it arrives.
3. **MT-1b: the outer-membrane face that reads the IMS closure is built, and the judged run keeps 180 mV**
   with a larger CPU budget rather than scaled activities. The mitochondria lane resumes with a free
   agent (D277).
4. **No optional re-tests now.** FR-25's A1 stays inconclusive (D282) and OL5 stays at 9 of 10 (D285).

## D289: FR-42 is built as option A, labels as share vectors on the physical row

2026-11-22, about 14:54 UTC. The user chose option A of docs/NEUTRAL_LABELS_DESIGN.md (fa4b9d9e).
- **The design:** one physical population per row; labels are shares of it.
  - Every law, the energy terms and the heat bookings read the physical population.
  - Each one-way flux is split by its source's shares.
  - A new cohort starts at exactly zero as a share.
  - Windows resolve to step indices.
- **The stages, 7–10 agent-days in all:**
  1. pools: registry labels, @3's share state, and one-way reports from turnover and templated
     polymerisation;
  2. transport: faces and routes report one-way flows, and FR-33's first test is rebuilt on shares;
  3. exchange, reactions and kinds, each by its own owner.
- **Owners:** the kinds owner leads. The gene regulation lane adds templated polymerisation's one-way
  reports, then replaces FR-38's class rows with shares before FR-38's registered comparison (D288).
- **Bitwise and records:**
  - worlds without labels keep their programs, and no registered world moves;
  - labelled worlds get a new checkpoint field;
  - D1's and FR-33's examples keep their material and transfer records, while their booked face heat
    moves to the physical value.
- **Scoring:** an independent checker writes FR-42's acceptance from the requester's words, including
  its reference case dN/dt = −N², built with the engine's own second-order mass action.

## D290: MT-1b keeps 180 mV and the source's activities, through an implicit cycle block

2026-11-22, about 15:10 UTC. The robustness agent priced D288's choice.
- **Explicit cycles cannot run it.** At 180 mV with the source's activities, the cycle kind's explicit
  bound is 27 ns. 300 s of protocol is then about 1.1e10 steps: about 19,400 CPU-hours on the device
  step alone, which is years of wall time, since one trajectory runs on one core.
- **The user chose to build the implicit cycle block** (D235's branch I, which MT-2 needs anyway): the
  cycles' slope conductances in N2's implicit operator, with a design note first. The outer-membrane face
  (18 µs bound) then limits the step: about 1–4 days per world on a lane, provided the runner path's
  per-step overhead comes down from 168 ms towards the device step's 6.3 ms. That overhead is being
  examined.
- **The order:**
  1. the face's design note, then the cycle block's;
  2. the face build and gate, then the cycle block's;
  3. MT-1b's worlds and the pre-registration checks;
  4. registration, then the judged run.
  R2's code-blind references start once the face note fixes the declared equations.

## D291: FR-30's section 13.3 candidates are all undetermined

2026-11-22, about 15:10 UTC. The lead's rulings, made blind to every value.
- **Lin et al. 2010** (J Mol Cell Cardiol 48:238) is undetermined on two separate grounds.
  - The Xu 2013 ruling (the strict reading) extends to it. It reports closing rates
    k_on = (1 − P_open)/tau from fitted exponentials, without P_open per voltage, so the law's relaxation
    times cannot be mapped without inference.
  - Its only kinetic data are neonatal atrial myocytes, with similar Cx40 and Cx43. That is neither
    ventricular nor Cx43-dominated, so it falls outside section 13.3's native admission.
- **Ek-Vitorín et al. 2018** (IJMS 19:1659) is undetermined under rule 1. Its decays come from ±80 mV
  pulses only, which is one magnitude, and wild-type Cx43 has a steady state only.
- With Xu 2013 also undetermined, section 13.3's registered candidates are exhausted. The extractor's
  files are under /mnt/workspaces/Cells/fr30-lin2010-benchmark/ and fr30-ekvitorin2018-benchmark/, with
  the held-out files sealed empty.
- **What follows is the user's decision.** FR-30 can stay development-only, with its gating law built and
  unjudged, or another metadata-only search round can look for two-exponential step decays at four or
  more voltages.

## D292: FR-30 gets one more metadata-only search; FR-41 gets a data-only retention check

2026-11-22, about 15:11 UTC. The user's choices.
- **FR-30:** one more metadata-only search, with values unread, broadened to any Cx43 preparation with
  two-exponential voltage-step decays at four or more voltages. A registration (a section 13.4 entry)
  comes before any extraction. If nothing qualifies, FR-30 stays development-only.
- **FR-41: a data-only check of whether calcein is retained during shrinkage,** in Akui 2021 and Ahumada
  2015/2017.
  - The analysis was fixed by the lead, blind to every value, before any reading:
    /mnt/workspaces/Cells/fr41-retention-20261122/rule.md, sha256
    9ae86b4028451d91663a40cdae1c8821a64b8dfcf4f121f1cc7922e3a6292d0f.
  - It is evidence for Cells' retention assumption, not a validation of Cells: no Cells prediction is
    scored.
  - The Sonnet extractor reads the values, since the Opus extractor was stopped by a safeguard false
    positive on Akui's methods; the user moved that task to Sonnet.

## D293: The rupture blind test's stage-1 rulings, made before any prediction or held-out value

2026-11-22, about 15:36 UTC. The sealed extractor's stage 1 (conditions only; stage1_conditions.json sha256
9c02be36…) found:
- set 1: six held-out points in five new temperature columns of Karal and Yamazaki's Fig. 2a, at about
  38, 35, 30, 18, 18 and 12 °C;
- set 2: Shibly et al. 2016's tables hold six osmotic rows and no control rows, and give no standard
  errors.
The lead's rulings, which are made blind to every held-out value and extend VESICLE_PORES_LAWS §8:
1. **Temperatures.**
   - Set 1 uses each column's plotted position, T = 10⁶/x, exactly as the six fit points did.
   - Set 2 uses T = 298.15 K with δT = 1 K (the paper's 25 ± 1 °C).
2. **Set 1's S1-6 (12 °C, 8.0 mN/m) is reported, not scored.** FR-31's entry, which the builders have read,
   already quotes 12 °C survival under a held tension from the same paper.
3. **Set 2's controls: a stage-1b pass.**
   - The extractor reads the control points' tensions from Fig. 1C, x only, with n where stated, and these
     become control conditions.
   - Their rates are read at stage 2, with the digitising error s_dig = 0.03 in ln k declared now.
   - The controls are scored two-sided, and the osmotic rows one-sided (§8).
4. **The vesicle area across preparations.**
   - In stage 1b the extractor reads Karal's method reference (Levadny et al. 2013) for the GUV radii,
     conditions only.
   - Set 2's per-vesicle predictions scale by (r_Shibly/r_Karal)², with r_Karal the midpoint of the stated
     range.
   - A declared term s_area, half the width of ln r² over that range, enters set 2's tolerance only. Set 1
     is unaffected, since its area cancels.
5. **Set 2's standard errors** are read from Fig. 1C's error bars at stage 2, with the declared s_dig. A
   point with no readable bar is reported, not scored.
6. **The quoted survival count.** At stage 2 the extractor matches it against Fig. 1B's curves among the
   2.8 mM cohorts. The matched point is reported, not scored. If the match is ambiguous, every candidate
   is unscored.
7. **Stage 2's reading of set 1:**
   - vector coordinates, with the centre at the midpoint of the bar caps;
   - the six fit points re-read as a check against the data file;
   - s_dig stays 0.03.
8. **Minor:**
   - the 1.9 mM series takes the stated 3 × 18–22 as its n;
   - Shibly's ± on r₀ is used as stated, for s_area;
   - the PMC HTML page is set 2's source of record.
   - The reader scripts stay with the run's evidence.
- **The exposures are disclosed:** lean/PROGRESS.md's intact fractions for Karal's Fig. 1(a) were seen by
  the extractor, and they concern S1-6, which is unscored. The extractor's other exposures carry no held-out
  value.

## D294: The rupture blind test's stage-1b rulings

2026-11-22, about 15:53 UTC. The extractor's stage 1b (stage1b_conditions.json sha256 0feca192…) found:
- set 2's three control points (Shibly's Fig. 1C, open squares) at 7.0, 7.5 and 8.0 mN/m, reprinted from
  Levadny et al. 2013, with n, temperature and solutions not stated;
- that Levadny et al. 2013 could not be obtained.
The lead's rulings, made blind to every held-out value:
1. **The controls are reported, not scored.** They sit at the fit points' tensions and come from the
   method paper of the fit data's laboratory, so they may overlap the fit data. Without a copy, their
   independence cannot be shown. This replaces D293's two-sided scoring of the controls. A prediction at
   6.5 mN/m with ΔC₀ = 0 is also recorded, reported only, in case stage 2 finds a control there.
2. **Set 2's scored content is the osmotic rows, one-sided** (D287, D293), less the point the quoted
   count matches.
3. **Karal's vesicle radius,** for the osmotic rows' area ratio (D293 item 4). In a stage 1c, the
   extractor reads only the methods of Karal et al. 2015 (Phys Rev E 92:012708, the Shizuoka repository's
   free copy), a paper from the same laboratory using the same micropipette method, for the GUV radius
   range. Karal, Levadnyy and Yamazaki 2016 stays unopened, since it may reanalyse the temperature series.
4. **The controls' temperature** is reported at 298.15 K with δT = 1 K, as for Shibly's own rows.
5. **Fig. 1C's digitising error.**
   - It is s_dig = max(0.03, the ln k span of 2 pixels on the panel's y-axis).
   - The pixel scale comes from the axis calibration at stage 2. That is axis metadata, read before any
     data mark.
   - It applies to the error bars read there.

## D295: The vesicle area for set 2's osmotic rows: a declared premise

2026-11-22, about 15:55 UTC. Stage 1c (stage1c_conditions.json sha256 7f99f680…): Karal et al. 2015 PRE's methods
state no GUV size, and Levadny et al. 2013 is unobtainable. The lead's ruling, made blind to every held-out
value:
- **The area ratio for set 2's osmotic rows is 1,** under a declared premise. Shibly et al.'s vesicles
  and the fit data's come from one laboratory, by one micropipette method in the same period, so their
  size distributions are taken as equal.
- **s_area** is the propagation of Shibly's stated ±0.2 µm on its mean r0 of about 13.5 µm:
  2 × 0.2/13.5, about 0.03 in ln k.
- **The premise is stated beside each set-2 verdict,** as the identity "first rupture is first opening"
  is. A set-2 failure may come from a size difference between preparations rather than from the law.
- **Set 1 is unaffected,** since its area cancels.

## D296: FR-42's label state lives in the label owner (option b); FR-38's replacement accounting in the operator

2026-11-22, about 16:09 UTC. The user: "lets go as you suggest regarding the label".
- **Label state lives in the label owner** (`neutral_arrival_labels@1`), through a contract addition:
  - reporters declare the pools they own, such as the release hold;
  - the owner holds those pools' label shares;
  - moves carry a pools part;
  - arrivals can be keyed by source, so that a chain's products join its producer label (cell, generation,
    chain).

  So every unlabelled program stays unchanged (D289). The kinds owner designs it and prices it beside
  stage 2. If it proves too costly, the fallback is operator-held shares as a D148 case 2, which goes back
  to the user.
- **FR-38's replacement accounting** (per-producer removal counters, per-generation counter starts, the
  operator's EVENT part) is the gene unit's own physical bookkeeping, not label state. It may add
  zero-size fields when no replacement is declared, as a D148 case 2 like FR-38's release fields. The proof
  is the programs check and optin_check before and after, with every physical field bitwise.

## D297: The rupture blind test's stage 2 is sealed; set 2 reads from Shibly et al.'s corrected Fig. 1C

2026-11-22, about 16:27 UTC. Recorded before any scoring; the lead has seen no held-out value.
- **The sealed file:** /mnt/workspaces/Cells/pores-extraction-20261122/held_out.json, sha256
  20a0c4a534a28ab2748d96f0c5de0cf81d38e2a47283c4f2aea94b0c9647468b. Stage 2 began at 16:04:16 UTC, after
  the predictions' tag (6d718ae2, 16:03:26). The extractor did not open the predictions.
- **Set 2 uses the corrected Fig. 1C.** Its SEs and control readings come from the figure in the
  journal's correction (Biophys J 112:1290, 2017, doi:10.1016/j.bpj.2017.03.001, PMC5376104), which
  replaced the original panel.
  - The corrected figure reproduces all six tabulated osmotic rates within 0.005 in ln k.
  - Its control tensions match stage 1b's, so the registered conditions and predictions are unaffected.
  - Disclosed: the extractor first read the original panel and found it inconsistent with the tables. Those
    readings are sealed separately (superseded_original_fig1c.json, sha256 d27cb33b…) and are not for
    scoring.
- **The quoted count matches S2-6** (4.3 mN/m, ΔC₀ = 2.8 mM) unambiguously. S2-6 is reported, not scored
  (D293 item 6).
- **Set 2's controls:** three, reported only. None lies at 6.5 mN/m.
- **The tables print two significant figures,** a rounding of up to about 0.05 in ln k. The registered
  s_dig = 0 for tabulated rates stands unchanged, since the corrected figure agrees with the printed values
  within 0.005.
- **Set 1:** read from the vector coordinates, with centres at the cap midpoints. The six fit points
  re-read within 0.0005 of the data file. S1-6 is reported only.

## D298: The vesicle-rupture blind test passes: set 1 five of five, set 2 five of five (one-sided, weak)

2026-11-22, about 16:39 UTC. The independent checker scored the registered predictions
(pores-predictions-registered-2026-11-22, sha256 8f72193b…) against the sealed held-out values
(held_out.json 20a0c4a5…) under VESICLE_PORES_LAWS §8, D293–D295 and D297. The score file is
/mnt/workspaces/Cells/review-check-20261121/pores/score.json, sha256 a4b452d6…. A planted failure fails.

**Set 1, Karal and Yamazaki's other temperature columns, two-sided: 5 of 5 pass.**
- **In range:** S1-1 (38 °C, 7.5 mN/m) has residual −0.200 against τ 0.252, the closest at 0.79 τ. S1-2
  (35 °C, 7.0) is −0.009 against 0.263, and S1-3 (30 °C, 7.0) is +0.032 against 0.257.
- **Extrapolated below the viscosity data:** S1-4 (18 °C, 7.5) is −0.035 against 0.231, and S1-5
  (18 °C, 8.0) is +0.173 against 0.241.
- **Reported only:** S1-6 (12 °C, 8.0) is +0.287 against 0.264. It would fail by 0.023. It was
  unscored because FR-31's entry had quoted that condition.

**Set 2, Shibly et al.'s osmotic rows, one-sided: 5 of 5 pass.** These are weak tests: the read rates lie
5.6 to 15.4 in ln k above the law at the external tension, as any added osmotic tension allows. The law
implies total tensions of 7.1 to 8.2 mN/m, an osmotic tension of about 2.6 to 3.9 mN/m (reported, not
scored). S2-6 (the quoted count) and the three controls are reported only. The controls would pass
two-sided.

**What this does and does not show.**
- The line-tension law, with the membrane viscosity's temperature dependence (E_A = 27 kJ/mol) and a
  constant line tension, fitted on the six read points, predicts first-rupture rates at three other
  temperatures within the registered tolerance, including two below the viscosity data's range.
- The tolerance is wide: t(0.975, 2) = 4.303 on three experiments per setting, so τ is about 0.25 in
  ln k, or about 28% in rate.
- The in-sample misfit stands as disclosed: the law over-predicts the 7.5 mN/m points by 14% to 28%,
  with χ² = 98.6 on 4 degrees of freedom.
- **Both declared premises go with every verdict:**
  - a pipette-held vesicle's first rupture is its first opening, though pores under suction can reclose;
  - for set 2, equal vesicle sizes across the two papers.
- The Lean lane had viewed the figure before the test (D287).

## D299: An external review's four architecture items, adopted into the queue

2026-11-22, about 16:57 UTC. An external reviewer, relayed by the user, asked the next architecture work
to focus on four items. The user: "lets go on 2. as you suggest put it on our backlog / 3. as you guys
suggest / 4. lets go on this as you see fit in the queue".
1. **Finish FR-42's neutral-label separation** (in progress, D289 and D296):
   - one physical population, with labels as passive shares;
   - FR-38's and FR-33's consumers moved onto it;
   - verified across label count, nonlinear loss, transport and restart.

   What remains is one independent acceptance on the stacked head: transport with face heat (F2 on),
   restart mid-transfer and with pools, replacement, and a reused label. D1's own-potential family rows
   stay as they are until the user decides their future.
2. **One small evolving-cell integration case, on the backlog.**
   - A read-only inventory ranks the composition matrix's refused volume and lifecycle combinations by
     the approved items they block, preferring a missing declared read or accounting term over a new law.
   - The lead chooses from it.
   - It uses the declared-read and ownership contracts, and unsupported combinations stay explicitly
     refused. It may extend to a lifecycle event, such as FR-38's replace-and-restart.
3. **Affordable realistic-duration runs,** judged by end-to-end cost per simulated biological duration at
   a stated accuracy, fixed before timing with the registered step-error estimate. Ensemble throughput,
   interacting-tissue size and biological duration are reported separately.
   - The dt ladder names the limit that binds the step, and whether the implicit cycle block relaxes it.
     The block's go returns to the user with those numbers (D290's premise was about 115 times too stiff).
   - Also in this item: the runner overhead (the bit-identical closure reuse), the step-cost growth with
     run length, and device row checks proven against the host checks.
   - Ensemble throughput is measured first on the existing batch and vector CPU paths. The GPU planner
     stays held until those numbers are in.
4. **One executable static level-of-detail pair, queued by the lead.**
   - The first pair is chosen from the read-only inventory: both versions through one physical interface,
     a validity measure, declared conserved quantities, supported readouts, a validity range and error
     limits.
   - The reduced version is opt-in, the choice is made at definition and never at run time, out-of-range
     use is refused, and the one-writer rule prevents double counting.
   - The general level-of-detail contract follows from it.

## D300: D1's own-potential label families are retired; no backwards compatibility before alpha

2026-11-22, about 16:59 UTC. The user: "retire them as soon as possible, we don't want old backwards
compatibility - we're still in heavy dev not even at alpha".
- **D1's families are removed,** with their checks, sums and D1-only paths, in the kinds owner's stacked
  FR-42 landing.
  - Their consumers (FR-33's first test and tracer, and FR-38's labelled cohort) are on FR-42's neutral
    shares.
  - D1-only tests are removed in one batch, with a removal list (D224).
  - Crossrev and G1 must stay identical, since no registered world uses D1 families.
- **The general rule before alpha:** a superseded mechanism is retired as soon as its replacement lands,
  with no compatibility path or opt-in for the old behaviour. Registered and judged results stay
  reproducible through their tags, frozen snapshots and records (D148), not by keeping old code.
- **Also recorded:** the Lean lane found FR-38's release_check accepting a survival ratio of 1.00 where 0.25
  is predicted, on a 0, 1 and 2 h grid. A grid error that could not be estimated became an infinite
  tolerance, and an empty cohort raised ZeroDivisionError. The fix fails closed, with "insufficient
  resolution" and "empty cohort". All eight saved R1/R2 survival comparisons passed with finite bounds,
  so no saved result moves.

## D301: The architecture items' first cases: FR-38's replace-and-restart, then M3; the site/sink level-of-detail pair

2026-11-22, about 17:22 UTC. The lead chooses under D299 ("as you suggest", "as you see fit in the queue"),
from the checker's read-only inventories (/mnt/workspaces/Cells/arch-inventories-20261122/INVENTORIES.md).
- **The evolving-cell case:**
  - **First:** FR-38's producer across replacement and restart, the gene unit beside
    scheduled_cell_replacement@1 with labels. It needs an accounting term and a definition-time occupant
    rule, priced at 1–2 agent-days once the label branches land (FR-38 step 4).
  - **A finding:** main admits the gene unit beside replacement but defines nothing for a replaced slot's
    chains, hold, machines or counters. A temporary refusal closes that now, until step 4 defines it.
  - **Next on the backlog:** composition M3, turnover beside water and beside partition or insertion,
    reading the current volume and masks. It is the cheapest case with a changing volume: declared reads
    only, 2–2.5 agent-days plus references.
- **The first static level-of-detail pair: site binding against exchange's saturable sink.**
  - The pair shares a ligand and the same node-to-cell ends, both run in the engine, and each is judged
    (FR-3, FR-1). Its validity measure is ε, with an error of order ε.
  - With it comes the general contract: one representation per scope, chosen at definition, refused when
    both are declared; out-of-range use and unsupported readouts refused; an automated comparison. The
    detailed form is the default and the reduced form is opt-in.
  - About 4.5–6.5 agent-days in all. Queued after FR-42 and FR-38 land.
  - **D214's finite fuel** remains named as a level-of-detail consumer, to follow on the same contract.
  - **R2 against A1** is the in-lane alternative after FR-38's comparison, with its default reversed so the
    detailed form leads.

## D302: The implicit cycle block is dropped; the half-step energy check is now the cost driver

2026-11-22, about 19:37 UTC. The user chose "Drop the block", on the robustness agent's measurements.
- **The measurements** (MT-1b's state-4 world, explicit cycles, today's solver, windowed runner, device
  row checks):
  - 16 µs passes every check through the protocol's inhibitor event, at more than 100 times inside the
    declared bands by FR-25's step-error form;
  - X2's order condition binds between 16 and 18.25 µs;
  - the block would buy at most about 1.14 times, or 1.3–1.5 times with the face present.
  D290's premise of 5e6 /s was about 115 times too stiff; the cycles' ΣG/C is 4.35e4 /s, about 98%
  of it from the synthase. MT-2 has the same stiffness. MT-1b runs explicitly at about 16 µs.
- **The cost now:**
  - X2, the half-step energy check, costs about 57 ms per step against 7.3 ms for the device step alone.
    At 16 µs that is about 300 CPU-h per 300 s world, against 38 without X2.
  - X2's per-step cost also grows with run length (39.6 to 53.7 ms per step from 512 to 2,560 steps).
    One candidate is the record's per-window concatenation.
  - The next item-3 target (D299) is a cheaper X2 with the same guarantee, profiled at length and designed
    before code.
- **Findings recorded for the backlog:**
  - **At a replacement swap,** neither replacement@1 nor templated_polymerisation@1 books the rows'
    standard term Σμ°Δn, and D152's reactions share the gap. The energy ledger still closes, because the
    owned terms are accumulators, but replacement_free_energy_pJ understates what leaves and arrives. This
    is a desk reading.
  - **FR-38's extracellular retention** of the producer ID is not admitted in version 1. The one-writer rule
    refuses any other mover of a gene-unit row, so no fate row can leave its cell. It needs a designed
    door.

## D303: Corrections to D302, FR-38's extracellular retention restored, the face plan re-priced, and the evening's repairs

2026-11-22, about 20:22 UTC.
1. **D302's basis, qualified.** The 16 µs result, and the question put to the user, covered state 4
   over at most 2,560 steps, not every MT-1b world.
   - State 3 was refused at 16 µs (dissipation) and at 8 µs (X2's cap at its first step). The cause is not
     established; the inference is the faceless IMS not being at steady state.
   - A long run at the source's activities was refused under head 2's per-species ledger floors, and was
     rerun with development floors.
   - X2's cost at length measured about 19 ms per step, not 57. The CPU-h figure in D302 is corrected
     when the timing table is in.
   - The block stays dropped unless state 3 or the floors reopen it. Both tests are raised in priority. A
     300 s world that fits under no admissible floor goes to the user, since floors are a tolerance.
2. **FR-38's extracellular retention is restored to FR-38's scope.** D302 filed it for the backlog, and
   amendment S marked it not admitted in version 1. That was wrong: the requester's clarification asks
   that RNA retained in an extracellular compartment keeps its original producer ID, and D284 is full
   scope. The one-writer rule refuses any other mover of a gene-unit row, so the door is designed as a
   sheet amendment, tagged before code, with options and a recommendation. Amendment S's sentence is
   superseded when that amendment is tagged.
3. **MT-1b's face build plan** (bafe39ef) is re-priced from the 2–4 agent-days quoted at D288 to about
   6.5–9, for four items:
   - the forms law and face, 3–5 days, by a separate face builder under the @3 owner's leave;
   - the held buffer, about 1 day;
   - the leak @2, 1.5–2 days for the kinds owner plus about half a day in the binding owner's admission;
   - the forms-aware lag drive, about 1.5 days.
   The capacitor/held-bath parse change is not needed. Dropping the implicit block (D302) saved 4.5–5.5
   days. The user has been told. The engine's builders stay blind to R2's code and outputs, and every
   exposure is recorded for the comparison's registration.
4. **FR-3's Q6 classifier repaired** (1adbb39e). replaced_slot's phrase is matched to today's message.
   view_conflict_bath_schedule is retired: FR-23 (D244) admitted that pair through door S's scoped
   reads. The repair is disclosed beside CHECKS, and the judged run stays reproducible at its tag.
5. **FR-42's stacked acceptance** at core-pass-kinds-26 3f760925 passed every check buildable from the
   public declarations, and all three planted failures were caught:
   - transport by a face with F2 on, by contact patches and by junctions, order 2.00;
   - exchange and reversible reactions; restart mid-transfer; replacement's rows; a reused label;
   - D1's families refused.
   Templated polymerisation's pools and sources come with the gene-regulation branch, so a second
   acceptance runs on that head. Kinds' routes are refused until the kinds hook.
6. **FR-42's kinds hook.** This is a separate optional kind hook, traced only with labels: it computes
   the trapezoid and the gap at the step's start and end states, with per-kind `label_refusals` in place
   of the blanket refusal. Passive routes and the transporter's flux-force forms report one-way moves;
   the rectifier and net-flow modes are refused. The kinds owner takes 1–1.5 days and @3 half a day,
   once the signature is agreed.
7. **The kinds owner's queue** follows D277's order, FRs first: FR-42's kinds hook, then the replacement
   event report FR-38's step 5 needs, then the leak @2, which is still ready before the face's item 1.
8. **OL6 has a new owner,** from the Phase A builder's handover. Its design note comes before code.

## D304: OL6 at full scope, and the GARD limit judged pathwise to rounding (the user)

2026-11-22, about 21:32 UTC. The user answered two questions on OL6's design note
(docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md, tag ol6-design-note-2026-11-22).
1. **"Full scope", priced at 7.25–10 agent-days.** It covers:
   - the deterministic representation, chosen in execution.representation over the same world id;
   - Kurtz's limit for the continuous counts;
   - each law's limit as a hook on its own declaration;
   - a Rosenbrock integrator with dense output and a strict envelope;
   - Protocol D against exact events;
   - the hazard clock in both representations, with Phase A's count-change refusal lifted in exact
     events as its own slice;
   - a size-threshold division for version 2;
   - Protocol G, the GARD limit.
   OL6's original 3–5 days predate OL2's third milestone and OL3, whose populations, divisions and lysis
   crossings the representation must carry. Version 1 still refuses: area-changing steps under a held
   tension, checkpoints in the deterministic representation, and `free_energy_form: continuum`, which
   OL1's registered conventions refuse.
2. **"Pathwise to rounding"** replaces section 7.3's "bitwise" tier. Probe P1 shows that the two GARD
   kernels' rates agree within 3.1e-15 but only about 13% are bitwise equal. The tier asks for identical
   channel sequences, with coincidences near a decision boundary counted and reported. Distributional
   agreement at registered tolerances stays the second tier, and a planted change to one β entry must
   fail.
- The lead's rulings on the note's other recommendations: accepted as written. The names
  `cells.rate_equations@1`, `cells.assembly_representation@1`, `rosenbrock_rodas4_dense@1` and
  `cells.size_threshold_division@1` are accepted. Each protocol is run at its tag by an independent
  checker, not the builder. The representation's contract is written so that it can serve as the
  first instance of the general level-of-detail contract (D299 item 4).

## D305: D302's cost corrected, and MT-1b's long runs refused by a fixed global-charge bound (an engine gap)

2026-11-22, about 22:19 UTC. The robustness agent's successor reconciled D302 and D303 on Step 0's
world: state 4, a steady start, faceless and event-free, at 16 µs. Evidence:
`/mnt/workspaces/Cells/mito-step0-20261122/RECONCILE.md` and `reconcile/`.
1. **X2 costs about 20 ms per step at length, not 57.**
   - Today's check alone costs 7.3–8.0 ms per step, so X2 costs about 2.6 times as much, not 8.
   - A 300 s world at 16 µs (1.875e7 steps) takes about 100–110 core-hours with X2, against 38–42
     without. D302's 300 is withdrawn, and so is the lead's later statement that the timing table
     confirmed it.
   - **The cause:** D302's 57 ms and the table's 59 and 68 ms each included a one-time recompile of
     78–100 s. `energy_check.doubled_step` caches the doubled step under the whole definition's
     digest, which includes the end time and max_steps, so each new run length recompiles X2's rollout.
     Keying that cache on what the step reads is a small engine fix, on the backlog.
   - **Four measurements agree:**
     - 19.7 ms per step, the median over 251 windows of a 64,756-step replay;
     - 20.2 ms, the marginal between warm runs;
     - 19.4 ms over the long run's fast windows;
     - 19.6 ms from growth_x2's 1,280→2,560 marginal.
   - **Two side findings:**
     - D302's "growth with length" was the same artefact.
     - A window with any ledger above half its bound is re-checked on the host, at about 180 ms per
       step.
   - **Caveats:**
     - No run has passed 64,756 steps, 0.35% of a 300 s world.
     - x2/breakdown.json's 52 ms for the doubled step is unexplained, so a cheaper X2 is not designed
       from it until it is.
2. **The long run was refused by the global charge ledger at step 64,756 (1.04 s)**, with every material
   floor at the parse cap.
   - **The mechanism:** MT-1b's bath is a held reservoir behind host P's closed plasma patch, so no
     charge crosses the boundary. The global charge residual is then the bath electrode's charge, which
     carries the zero-mean rounding fluctuation of the matrix and IMS net ionic charge, up to 2.8e-25 C.
   - **The bound:** 3e-25 C plus an allowance on the charge moved through the boundary. That charge is
     the residual itself, so the bound never rises.
   - **It refuses whatever X2 or the floors do.** Today's check takes the bit-identical trajectory. Long
     runs of any world with a held bath behind a closed patch meet the same fixed bound.
   - **This is an engine gap:** surface_field's component rule of 9 November gives a floating component
     a rounding allowance, under which this residual stays at most 0.1% of it. A component grounded
     through a held bath was never given the same allowance.
   - The bound is a tolerance, so the fix is the user's decision (asked now).
3. **The material floors fit a 300 s world at the parse cap of 1e-10 fmol.**
   - The per-row residual maxima grow as n^0.67–n^0.83, reaching 7.2e-15 fmol at 6.4e4 steps. They
     extrapolate to about 1e-12 fmol at 300 s, at most 1% of the cap; the cap fails only for growth of
     n^1.68 or faster.
   - Head 2's floors (1e-16 fmol for H) refuse at step 28,438, very probably H where its magnitude
     dips. That was very probably the first long run's refusal.
   - A 1e6-step check under today's check (about 2 h) follows once item 2 is fixed.
4. **D303's item 1 is settled:**
   - "about 19 ms" is confirmed;
   - the floors do not reopen the implicit block, since they fit at the cap;
   - the global charge refuses whichever block runs (an inference).

## D306: FR-42's kinds, pools and sources and FR-38's steps 4 and 5 accepted; FR-38's cohort follows the requester's words

2026-11-23, about 02:13 UTC. An independent checker, blind to the builders' tests and drivers, ran an
acceptance written from the requesters' words, on main 529a8bd9. Its evidence is in
`/mnt/workspaces/Cells/review-check-20261123/`. Its criteria were set after the results, from order
arguments (a dt-halving ratio near 4, and exact zeros and bit patterns where the design says exact),
never from the builders' numbers. That is disclosed.
1. **Passed:**
   - **FR-42 through kinds:** routes and the transporter, each labelled against unlabelled bit for
     bit. The one-way splits match closed forms at second order, where a net-only split would be 0.03
     off in share. Shares are a partition to 3.3e-16, and the rectifier is refused.
   - **FR-42's pools and sources:** R1's 80 chains, survival 0.7071 and 0.2500, and a restart mid-hold
     bit for bit.
   - **FR-38's replacement (step 4):** removal by label exactly the pre-event row times its shares, the
     counters at birth and death bit for bit, and per-producer identities closing to 1e-15.
   - **FR-38's replace-then-restart (step 5):** restarts through snapshots bit for bit.
   - **Planted failures:** all six were caught (shifted one-way amounts on a route and on the
     transporter, an ulp per step, a skipped relabel, a skipped removal record, completion marks at
     the base).
2. **Unmet, in the requester's words:** RNA retained in an extracellular compartment keeping its
   producer ID. Amendment T's export is tagged and not built. It is next.
3. **The lead's ruling on a split the checker found.** Near the degradation's domain edge (e^y_f about
   0.34), RNA re-synthesised from monomers takes the label in force, and a cohort decays at the gross
   one-way rate.
   - **The finding:** a cohort windowed on the species' own arrivals then counts re-synthesised
     molecules, 18% more at 240 s. A cohort windowed on the chain's source schedule, which marks at
     release from the template, matches the requester's words: "detaches from its template" and "the
     same molecules".
   - **The ruling:** FR-38's cohort is defined on the chain's source schedule, and re-synthesised
     molecules are not members.
   - **An erratum F to the sheet's section 9.8** is tagged before FR-38's rule. It states:
     - the definition;
     - that route 2 uses the gross one-way loss, not the net;
     - that the species-window and source-schedule readings agree only where e^y_f << 1.

     At the sheet's own state the two differ by 4e-9.
   - The rule (fr38-rule, untagged) is not yet registered, so no registered result moves.
4. **A risk, to be closed by design: producer identity is a declared name.**
   - A producer label schedule that does not switch at the replacement event is admitted, and so is
     one that switches early. The newcomer's copies then sit under the founder's label.
   - The requester defines a producer as cell, occupant generation and expression chain, preserved
     across restart and cell reordering.
   - So the producer label is to be derived by the engine from the replacement events, or an
     inconsistent schedule refused. This is a sheet amendment first, with options.
5. **Stated, not changed:** under release-marking, a hold emptied at a replacement is recorded at the
   base label (erratum E), and is booked to the departing generation through the counters only. Under
   completion-marking it carries its labels.

## D307: The global charge's grounded allowance takes the larger of the two terms; producer labels are derived (amendment G, option a)

2026-11-23, about 02:22 UTC. The lead's rulings within the user's decisions. The user can overrule either.
1. **The global charge (D305, the user's "extend the rule"): option (M).**
   - The bound is 3e-25 + 256 eps × moved + max(2.5 eps n × moved, 2.5 eps n × the grounded
     component's summed |z F dn|).
   - It solves the gap: MT-1b's Step 0 world runs to 131,072 steps (2.1 s) under today's check, its
     global charge at most 9.2e-5 of the bound after 1 s.
   - It is bit for bit unchanged wherever the moved charge's term dominates. It is within twice the
     strict sum (S), and stays the tighter of the two; a planted supply leak at twice the bound is still
     refused. (Z), the allowance only where nothing has crossed, would bring the refusal back with any
     tiny leak.
   - It moves only the diagnostic `max_global_charge_bound_ratio`, always lower: in 26 of G1's 113
     worlds, and in FR's set. Both frozen baselines are renewed in the same landing, each with a
     renewal record, as fix (A) renewed G1's (D273). Frozen evidence that stores the ratio stays as
     recorded, and MG0b's ≤ 1 still holds.
2. **FR-38's producer identity (D306 item 4): amendment G's option (a).** The label owner derives each
   producer label, <cell>-g<k>-<chain>, and its source's schedule from replacement@1's occupants.
   - A hand-written schedule for a producer source is refused.
   - The derived schedules equal a correct hand-written one, so programs stay bitwise.
   - Restart and cell reordering leave the labels unchanged.
   - Option (b), refusing an inconsistent schedule, is cheaper but leaves the burden on every
     definition.
   - Price: the kinds owner 0.75–1 day, the gene-regulation lane 0.25–0.5.
3. **Erratum F** (tag gr1-sheet-fr38-erratum-f-2026-11-23, main f802d0ea) settles D306 item 3. FR-38's
   cohort is the molecules released from their template, marked on the chain's own label schedule.
   Route 2 runs at the gross one-way rate. The rule follows it before its tag.

## D308: FR-38's rule was tagged without its reader; a rule erratum supplies it before any judged run

2026-11-23, about 06:03 UTC. The independent judge of FR-38's registered comparison (tag
fr38-rule-registered-2026-11-23) stopped before any run.
- **The gap:** the rule names "the comparison's reader" and a name mapping "that the comparison's reader
  states at the tag", and none exists. G4/FR-25's compare.py reads only G2's files, and FR-25's
  registration.py cannot judge this rule's quantities (route 1's labels, the hold's class, survivors,
  route 2). The lead tagged the rule without checking that its reader existed.
- **The fix:** rule erratum 1, tagged before any judged run.
  - The judge writes the reader from the interface files' keys and array shapes only, never their
    values, and states the name mapping per world.
  - The erratum also states:
    - the route agreement's bound, section 9.8's (route 2's grid error plus route 1's split), reported
      with the verdicts and changing no verdict;
    - route 2's error and scale per sample time;
    - the retry's support runs (the matched blanks at the retry steps, and R1L's unlabelled twin),
      not judged themselves;
    - FR-25's precedence. Within a run, an out-of-window order makes it inconclusive. Overall, any
      failed run makes the comparison failed, else any inconclusive makes it inconclusive.
- **Disclosed:** the judge saw reference figures printed in the references' tag messages (679fe885,
  05725b23) before any run. No tolerance is the judge's, so the exposure cannot move one, and it is
  recorded in the verdict's not_blind.
- **For later rules:** a registration names a reader that exists at its tag, or the rule is not
  tagged.

## D309: OL6's pore clock takes a relative error bound (the user)

2026-11-23, about 10:41 UTC. The user chose "Accept the relative bound", on Protocol D's section 7.3
proposal (tag ol6-protocol-d-registered-2026-11-23).
- **The bound:** a deterministic-representation step is accepted when the pore clock's embedded error
  estimate satisfies |U^H| <= 1e-10 + 2e-3 |dH|, where dH is the step's own clock increment. This replaces
  the absolute 1e-10 per step (the lead's ruling (a), D304).
- **Why:**
  - the absolute bound refuses D7, vesicles opening a pore at 50 and 100 nm, even at rtol 1e-13,
    because H takes no part in step selection;
  - the order-3 estimate overstates H's error about 200-fold;
  - over the registered seeds the largest (estimate - 1e-10)/dH is 5.3e-4, a 3.8-fold margin;
  - t* moves at most 1.1e-8 relative between rtol 1e-12 and 1e-13.
  All of this was found from runs of the deterministic representation alone, with no comparison read.
- **The guarantee it changes:** the crossing time's error is bounded by 2e-3 relative by the estimate.
  That is inside the envelope's 2/n_min for n_min up to 1000.
- **Next, both before D7 runs:** an engine follow-up to S3, which implements the bound with its rows,
  gated, and Protocol D's erratum 1, which makes D7 runnable under it. Protocol D's other worlds (D0-D6)
  and Protocol G's scope 1 can run now.


## D310: FR-15 F2, charged trace species on junctions: option A, with the lead's rulings

2026-11-23, about 11:45 UTC. The lead rules on docs/CHARGED_TRACE_SPECIES_DESIGN.md (7f3f6ccd, tag
fr15-f2-design-landed-2026-11-23), under the user's go on the cancer lanes and the FRs (23 November).
- **C1: option A.** `passive_constant_field_permeation@1` is hosted on junctions. This keeps the 19
  November ruling and needs no per-stage material bound inside @3.
- **C2: refused in version 1.** A junction that crosses a floating capacitor component is refused
  explicitly. The refusal lands in the same change that lifts today's junction refusal, because fix (A)
  (b8e786d4) relied on that refusal. No consumer has such a junction, so A2 waits for one.
- **C3: the two-end sum** for a junction route's material term. It is the neutral law's form, and its
  limit at zero voltage.
- **C4: widen @1 in place.** The precedents are S1 and FR-19:
  - no world declares the law;
  - P2's header reserved junction hosting under @1;
  - unchanged worlds stay bitwise (D148 case 2), and pre-alpha needs no second ID.
- **C5 goes to the gap-junction replication's owner.** The microRNA's decay can be written now as the
  closed conversion miR- -> D-. turnover@2 is needed only for exact exponential clearance.
- **The @3 owner's two questions,** ruled by the lead as the note proposes:
  1. a kind's cell-to-cell current enters the floating-component residual only on junctions that cross
     a floating component; version 1 refuses those, so the residual is unchanged;
  2. KindRates gets no `junction_flux` in version 1.
- **The 19 November note is corrected:** the kind's charge term on a junction takes 2G at each cell.
- **Sanctioned test change:** the junction-host refusal row in `tests/unit/test_passive_routes_kind.py`
  becomes the crossing-junction refusal.
- **P2's patch material term becomes the two-end sum where a patch faces a finite node,** in the same
  build. The term is each end's own slope, so it can admit up to twice the stable step there. No
  registered world declares the law, so nothing registered changes.
- **Recorded for other lanes:**
  - **FR-16:** F4's per-species floor must reach a kind's junction route, as a per-route floor.
  - **The kinds lane:**
    - the transporter's material term skips charged rows that cross, so a trace charged row moved by a
      carrier (butyrate on the symporter) has no material bound;
    - `site_occupancy@1` refuses a charged ligand (HDAC binding);
    - from the Xenopus lane: `cells.na2_anion_symport_diagram@1` fixes zeta at 0 on four of its edges,
      where XC0's version-2 design moves charge.
- **The build** is A1, about 2.25 to 2.75 agent-days with its gates. It starts at the next free agent
  slot.

## D311: FR-30's benchmark is Revilla, Castro and Barrio (1999), held out at -80 and +80 mV; the trace criterion is a dated amendment (the user)

2026-11-23, about 12:08 UTC. The user chose (a), "Sounds good", on the lead's description and blind to every
value, after the advisor endorsed it with a precedent check, which came back clean. The section 13.4
extraction is in /mnt/workspaces/Cells/fr30-candidates4-extraction/ (README.md, LOG.txt).

**The verdicts in the registered order.**
1. **Shibayama et al. 2006:** undetermined. Both times are given at +100 mV only.
2. **Elenes et al. 2001:** undetermined. The times are on an unsigned axis at three magnitudes, which
   leaves one held-out voltage.
3. **Revilla, Castro and Barrio 1999** (homotypic wild-type rat Cx43, Xenopus oocyte pairs): qualifies.
   - Fig. 3B gives tau1 and tau2 at -100, -80, -60, +60, +80 and +100 mV, each the mean +- SEM of six pairs.
   - Rule 1 holds out 80 mV at both polarities.
   - The judged observables are tau_fast, tau_slow and G_ss/G_0, each at -80 and +80 mV. Amplitudes are not
     reported per voltage, so they are not judged (section 13.2).
4. **Ek-Vitorin et al. 2016:** not opened.

The held-out file is revilla1999/extraction/held_out.json, sha256
e83680830219a58ab6b47d268518543b90e63c52d6b7d7694ee8a8e45c7a7285. All 12 entries of its SHA256SUMS verify.

**The lead's ruling: -80 and +80 mV are two held-out voltages.**
- Rule 1's data unit is a signed step, and rule 2 judges "each held-out V_j". Section 13.1 point 2 keeps
  section 13's rule where each polarity is reported.
- This agrees with D291, which ranked by magnitude (Ek-Vitorin 2018 had one magnitude), and with Elenes,
  whose unsigned axis gives one unit.
- With two voltages, "more than half" means both, so every judged time and both G_ss must pass.
- The claim is one interpolated magnitude, 80 between 60 and 100 mV, at both polarities. It is not two
  independent tests.
- D292's search asked for "four or more voltages". Revilla has three magnitudes per polarity, six signed
  voltages in all.

**The amendment: superimposed or single sample records are not refitted.**
- **The change.**
  - Rule 1 admits traces "digitized, then fitted by the extractor", while rule 5 says the extractor "does
    not fit".
  - The amendment resolves that tension toward rule 5: only decays the paper itself analysed count.
  - It applies to the paper that prompted it and binds every later candidate, fallbacks 5 to 9 included.
- **What had been seen when it was written.**
  - The extractor had read all of Shibayama and nothing of Elenes or Revilla.
  - It fixed and hashed the criterion (4d5b1df8...) before Elenes was opened and before any value was
    digitized.
- **Precedent.** No earlier FR-30 extraction refitted a sample record:
  - Desplantez 2004's extractor declined its Fig. 2B traces on 21 November: "a tau from a trace needs
    fitting, which is barred";
  - Lin 2003's extractor did not fit its Fig. 5A traces.
- **Under the unamended text** the outcome is unknown: Shibayama's ten superimposed 30-s records (Fig. 1A)
  would have been tried first, then Elenes's Fig. 3A records.
  - The extractor states that refitting was the only way Shibayama could qualify.
  - Shibayama's wild-type arm is the same preparation from the same laboratory (Barrio is an author of
    both), and its printed per-polarity Boltzmann parameters match Revilla's Table 1. So its records are
    probably the same experiments, read more noisily.
  - Elenes's Fig. 3A records are partly in HeLa cells, which carry another connexin.

**Exposures, disclosed. The fitter never opens lean/.**
- `lean/checks/data/revilla1999_cx43.json` holds Revilla's Table 1, each polarity's Boltzmann fit. It has
  been on main since 21 November (0ec0ac28, 760d9f0c).
- Its comparison voltage is 80 mV. lean/PROGRESS.md and lean/claims/junction-gate.md print the fitted
  conductance at -80 and +80 mV, so the held-out steady state is printed in the repo, not merely
  derivable.
- lean/claims/junction-series-amplitudes.md and lean/COVERAGE.md print the -100 mV times and the amplitude
  ratio, which are training values.
- **Section 13.4's line is corrected.** It said "Nobody on this project has read these papers' results",
  which was wrong for Revilla. The Lean lane, an independent agent, had read it and put its Table 1 on main
  the day before.
- **The law's design predates the exposure.** The FR-30 design note read lean/claims/junction-gate.md on
  20 November (d0245ebc, 22:14 UTC), before Revilla's section landed there (21 November, 14:12 UTC). Any
  later reading by the law's developer is not recorded.
- **The lead stayed blind.** The lead read those files only as lines with every non-voltage number masked, plus
  the data file's keys and its comparison voltage. He did not open the held-out file, Revilla's
  extraction notes or Shibayama's record.

**Next, before the tag.**
- Section 13.5 pins the prediction and readout conventions: the 30-s step; G_0 at the +10 mV prepulse;
  G_ss as the end-of-step value; the fit window, form and start values; degenerate fits; and the tolerance
  combining ln 1.25 with 2 SEM.
- The scoring code must exist at the tag (D308).
- Then the fitter starts, working from fit.json and protocol.json only. Its exclusions are all of lean/,
  the four papers, and everything else under fr30-candidates4-extraction/.
- The lead's draft is /mnt/workspaces/Cells/fr30-benchmark-20261123/RULING_DRAFT.md.

## D312: XC0's comparison rule is registered; the lead's answers to its three questions

2026-11-23, about 12:15 UTC. The Xenopus lane's XC0 rule is tagged on its branch head,
xc0-rule-registered-2026-11-23 (98351456), and merged at 1030280a. It names its reader,
validation/xenopus_bioelectric/xc0_compare.py, as D308 requires. Nothing has been compared.
1. **The manifest: option B, without the text.**
   - The tagged reader's keys stage runs first. It prints family names, kinds, units and row keys only.
   - The claim and quantity strings are not printed, because they can carry numbers. The families'
     meaning comes from the confirmer (answer 2).
   - The erratum that maps the undocumented families is then written once and tagged before the table is
     built, and the table is built once.
2. **The semantics come from a confirmer who is code-blind and value-silent.**
   - An agent that may read the references' values and notes, but never Cells' engine code or outputs,
     writes one file. It covers the nine readings to confirm (each "matches" or "differs"), the families
     REFERENCES_USAGE.md does not map, and C3's worlds S2 to S8.
   - It states no value, band, floor or tolerance, and no word that gives away an outcome. A mechanical
     check confirms that every number in it is a key token, a unit, a declared input or a number already
     in REFERENCES_USAGE.md.
   - The builder reads only that file.
3. **T1 and T2 stay unscored calibrations in XC0.**
   - DESIGN gives no plausibility range for P_GlyR or the m_kleak availability, and a range set now would
     be the lead's guess.
   - The calibrated values are reported with the verdict, which states that they are unconstrained.
- **Disclosed in the rule's not_blind:**
  - the builder's refused listing of the designs files, of which nothing was read;
  - the reference figures printed in DESIGN's erratum, declared_inputs.json and the references' README;
  - one engine value at a registered state, pump_dG_atp at the declared pump conditions, printed by a
    first invented input set and then replaced.
- **The engine gap stays queued for the kinds lane** (D310's list): a declared zeta on every edge of
  `cells.na2_anion_symport_diagram@1`. Until it lands, version 2's charge-placement rows are "not run on
  main".

## D313: FR-38's registered comparison failed: R1 failed, R2 inconclusive

2026-11-23, about 13:32 UTC. The independent judge's verdict under the rule (tag fr38-rule-registered-2026-11-23)
and its erratum 1 (tag fr38-rule-erratum-1-registered-2026-11-23, 57ff66b0).
- **Provenance:**
  - the runs came fresh from a clean frozen snapshot of 3f485ee9;
  - the table and the verdict came from a clean frozen snapshot of the erratum's tag;
  - the record is /mnt/workspaces/Cells/fr38-judged-20261123/verdict.json, sha256
    f4e868de1c72520cee5d88b8d2db33027bd0990237059ea098d5ba4beeb3da3a, with verdict_notes.json beside it.
- **Per run:**
  - passed: R1 at p = 0.25 and p = 0.75, for both machine options;
  - failed:
    - R1 at p = 0 (survivors_R) and at p = 1 (survivors_R_s);
    - R1's blank (G_minus_G0);
    - R1L at p = 0.75 (label_R_cohort and label_R_s_cohort);
  - inconclusive: R2, on C_tx_3's observed order. The first triple gave 3.94. The one retry, at 1, 0.5 and
    0.25 s, gave 3.69 and 3.67, still above the 3.5 cap, although all 69 readouts of each run were within
    tolerance at 0.25 s.
- **The failures, by clause:**
  - **Zero-rate survivors, four runs.** The engine's |n_F - blank| is at most 5.3e-24 fmol, against a floor
    of 1e-21. They fail only on the lead's sixth ruling, which required the reference to be exactly 0. It is
    not 0: it matches the engine's value to within 5e-27 fmol. **That ruling was wrong.** Without it these
    four runs fail on nothing else, but R1 still fails.
  - **The blank's G_minus_G0, two runs.** The gap is 1.51e-16 pJ, against a floor of 9.98e-17 pJ (1e-9 of
    the row's own 1e-7 pJ scale). The absolute gap is 1.1 to 1.8e-16 pJ in all twelve R1 runs; the others
    pass because their scales are 4 to 7e-3 pJ.
  - **Route 1, two runs (R1L).** The gaps are 3.56e-9 and 5.78e-9 of their scales, against the 1e-9 floor.
- **The judge's hypotheses about the causes. None is verified.**
  - **Route 1:** erratum F's gross-versus-net difference. The engine's cohort leaves at the gross loss rate,
    while the references' route1_blank (row minus blank) loses at the net rate. Its closed form reproduces
    the short-lived gap (5.78e-9), but predicts 1.72e-9 for the durable readout against 3.56e-9 observed.
    So route 1 is not explained.
  - **The blank's G:** rounding of G's large terms, about one ulp of M times its potential.
  - **The zero-rate survivors:** both sides compute the same coupling through M.
- **The verdict stands as registered.**
  - FR-38's functional acceptance (D306) is unchanged; the judged comparison failed.
  - Re-scoring this table under any corrected rule would be a labelled, non-blind diagnostic beside the
    failed verdict, never a replacement. R2's retry is spent.
- **What follows is the user's decision.** The options, put to the user on 23 November:
  1. record and stop: FR-38 stays development-only, with no validation claim;
  2. record, diagnose route 1, then decide. The diagnosis covers the engine-side gap per time, and the
     references' author stating in words what route1_blank is defined to be;
  3. a new registered comparison on fresh worlds, with the rule fixed before new references exist. This is
     the only route to a pass.

## D314: The user's three decisions of 23 November afternoon, and BITSEY's role

2026-11-23, about 13:39 UTC. The user chose the lead's recommendation on each.
1. **FR-38 (D313): diagnose route 1 before deciding.**
   - The diagnosis gives the engine-side gap per sample time for R1L's two readouts, each tested against
     erratum F's gross-versus-net closed form.
   - The references' definition of route1_blank is stated in words.
   - It is a non-blind diagnosis and replaces no verdict.
2. **OL6 Protocol D: erratum 2 for P-D1, using its registered closed form.**
   - P-D1's planted (d) run is refused by its own books (residual 7.26e-8 k_BT against 1.00e-8) before
     criterion B can read it. Under section 8, a plant not caught makes the protocol fail.
   - The erratum has B read P-D1's (d) side from the registered `pd1_closed_form` (`d0_stationary`), so no
     new number is introduced. P-D1 gets one attempt under it.
   - It also records the lead's ruling on P-D2(ii): its process computes the engine's generic verdict
     before entering its scope. That plant then reproduces the registered effect bit for bit
     (0.20764924410295305).
   - It is tagged after every plant has been attempted, which is now done, and before any honest
     comparison is computed or opened. None has been.
3. **GJ-N1's 2D field takes the faster path first.**
   - GJ-N1 is registered as written (gj-neither-registered-2026-11-23), and the 1D line, about 8 CPU-hours,
     runs now.
   - The field would cost about 350 to 410 CPU-hours at 0.16 to 0.19 s per step. Before it runs, the
     engine's per-cell cost is profiled and the GPU tried, as development timings only, with no outcome
     read.
- **BITSEY's role, the lead's ruling on D219's "an additional reference":** the pinned run is reported
  beside the verdicts and never judged.
  - BITSEY integrates by explicit adaptive Euler, which has no a priori error bound, so no band could be
    set honestly.
  - The judged reference is the code-blind integration with its stated accuracy (GJ-N1's check A).

## D315: FR-43's design decided: part 3 in the composite (B); the cap to 1,024; two writers with one potential (the user)

2026-11-23, about 14:13 UTC. The user reviewed docs/FR43_SHARED_INVENTORIES_DESIGN.md (branch fr43-design, 398a6e64)
and gave the five rulings it asks of the lead, with part 3's host.
1. **Part 1, networks above 16 species:**
   - the cap rises to 1,024 species;
   - the existing sum is kept through 16 terms and the scan fold is used above 16, so every world at 16 or
     fewer keeps its program text;
   - the trace budget's over-estimate is fixed now;
   - the per-entry sparse layout is staged afterwards.
2. **Part 1, the step:** the accuracy-limited timestep is reported, and the stiff integrator is deferred
   (D152's door, a separate law).
3. **Part 2, fixed volume:** two writers are allowed on one shared row, with one registry potential and
   separate material and energy accounts for each writer.
4. **Part 2, changing volume:**
   - the reaction law keeps its ID;
   - current-volume reads are delivered for both writers, the reactions and the gene unit, within FR-43;
   - a test must run both writers active while the volume changes.
5. **Part 3:** the host is option B, an integer-population operator in the composite. B requires no OL6
   exemptions, so OL6's refusals 9 and 11 stay.
   - The split is the new token independent_segregation (each unit to the first recipient with
     probability f), and exact_fraction is preserved, with Protocol G's contract untouched.
   - Event timing is verified under step halving, the partition at division is verified, and a same-seed
     restart is verified.
- **Next:**
  - the build, on the extra cores that are the priority item's;
  - the code-blind references for part 2's coupled calculation and part 3's same-draws integration, by a
    separate agent;
  - the GPU column folded into the note.

## D316: FR-38's route 1 diagnosis: every failure is definitional, with no engine or reference defect found

2026-11-23, about 14:26 UTC. The judge's non-blind diagnosis (D314, the user's option 2). The judge read the references'
code and values for it, so it is no longer a blind judge for FR-38. The D313 verdict stands as scored. Files:
/mnt/workspaces/Cells/fr38-judged-20261123/diagnosis/ (diagnosis.json and the three scripts with their records).
- **Route 1 is definitional.**
  - The engine's label cohort leaves at the gross rate, which is erratum F's definition and what the rule
    asks: the forward loss k n leaves at the row's shares, and the re-synthesis k n e^y enters at the base
    label.
  - The references' route1_blank (row minus blank) loses at the net rate, k(1 - e^y). The references were
    built on 22 November, the day before erratum F.
  - The per-time gaps equal the gross-minus-net closed form, to the engine's own split-step error. The
    durable readout's 3.56e-9 is that form at 7200 s, normalised by the 3600-s scale.
  - The engine meets the references' own gross closed form, first_order_limit, to 2e-14.
  - The mapping that failed was the lead's: erratum 1's reading that "the blank-free label row is the same
    quantity".
  - Route 2 has the same mismatch, hidden by its known-rate grid error.
- **The blank's G_minus_G0** is mu_M times the engine's float rounding of n_M (0.85 ulp at 7200 s). With
  the exact M, the engine meets the reference to 7.7e-22 pJ.
- **The zero-rate survivors.** The reference's n_F_minus_blank carries the row's real coupling through M,
  and the closed form gives the same value. The engine departs from it by 4 to 5e-27 fmol, within its own
  step noise. The sixth ruling's premise, that this quantity is exactly 0, was wrong.
- **A side finding:** the short-lived split error is 1.10 times erratum C's stated bound, so that bound is
  not strict. A sheet correction is on the backlog.
- **The judge's recommendation:** a corrected rule for a new comparison, with these parts:
  - routes 1 and 2 mapped to the gross reading, either through first_order_limit or through a new code-blind
    gross tracker;
  - the survivors compared with the reference at a floor of 1e-9 times the row's magnitude;
  - G's floor set as a reasoned multiple of |mu_M| ulp(n_M);
  - R2's order window argued from the split scheme before any run;
  - fresh runs and a new judge, with the non-blindness disclosed.

  Such a comparison on these worlds is weaker evidence than the first. The decision is the user's.

## D317: Three choices of 23 November afternoon, and a disclosure for FR-30

2026-11-23, about 15:20 UTC.
1. **FR-38 (D316): a new registered comparison, after FR-43** (the user). The corrected rule is fixed first. Then come
   fresh worlds, new code-blind references for the gross reading, and a new judge. It waits until FR-43's build
   has its agents.
2. **OL6 Protocol D: erratum 3 before D0, D3 and D5 are judged** (the user).
   - D6 fails criterion M as registered through an arithmetic artifact. At three pre-shear times all 128 exact
     replicas equal (d) bitwise, yet the registered mean_error's rounding gives z of about sqrt(128), against a
     threshold of 6.
   - The erratum excludes from M a pair that is exact at the top rung. D6's registered fail stands, and it is
     rescored under the erratum only as a labelled diagnostic.
   - **The registered verdict stands:** Protocol D fails as registered through D6, and the full repair of M
     belongs to a re-registration.
   - **Zero-SE check:** the checker found no (observable, time) pair with a zero combined SE and a nonzero
     error in D1, D2, D4 or D6.
3. **GJ-N1's 2D field** (the user, on the owner's profiling). The registered cost was overstated: it is about
   0.11 to 0.14 CPU-s per step, about 300 CPU-hours for the field search. The plan:
   - first, two bitwise-identical engine fixes: the Hill evaluation's padded double branch, and the window
     path's per-step overhead;
   - then a sparse solve for the arrowhead-shaped field matrix, as part of FR-17, qualified against the dense
     solve and named in a tagged GJ-N1 amendment before any field point runs;
   - then the field runs on a gate lane.
- **A disclosure for FR-30 (D311, section 13.5).** The lead ruled one parameter set for both polarities after
  reading, with every number masked, the Lean lane's line that a polarity-symmetric gate misses one fitted curve
  at 80 mV. The ruling follows the law as declared, junction_series_gates@1 being symmetric in |V_j|. It does not
  tune toward a pass.

## D318: OL6 Protocol D fails as registered, on D6's M alone; everything else passes

2026-11-23, about 17:05 UTC. The independent checker's verdict on D0–D7 under errata 1–3. The record is
/mnt/workspaces/Cells/ol6-checker-20261123/ol6-protocol-d-3e50d48d/verdict_protocol_d_D0_D7.json, with 30 disclosures.
- **The protocol fails as registered on D6's criterion M alone** (10.47, against the fail threshold of 6). It is
  the arithmetic artifact of D317: all 128 exact replicas equal (d) bitwise at three pre-shear times.
  - Under erratum 3's rule, D6's labelled, non-blind diagnostic is 2.293, and D6's other criteria pass.
  - D5 passes under erratum 3 (M 1.66, with 16 exact pairs excluded). Over every pair, the registered value
    would be 10.98, the same artifact.
- **Every other world passes:**
  - D0 is refused at parse at min_count 10, as registered;
  - D1, D2 and D3 pass, with P slopes of -0.498, -0.500 and -0.496, M at 2.9 or below, and B's c_r at 2.08 or
    below;
  - D4 passes, with E's mean_z at 0.49;
  - D7 passes under D309's bound: E's mean_z is 1.01, and all 384 of 384 are paired by the pore.
- **Every plant is caught.** P-D1, under erratum 2, needs c_r 15.94 against 5. P-D2 through P-D7 are caught as
  registered.
- **Other results:**
  - n_min: none, since M fails at the ladder.
  - Zero-SE pairs with a nonzero error: none.
  - N: passes.
- **Protocol G scope 1 still passes.** The checker corrected its physical-measure note: paired on the same seeds,
  the measure is -1.80% against section 7's predicted -1.75%.
- **Scope 2 is running.**
- **The user's decision (23 November): re-register Protocol D after FR-43.** M is repaired, the seeds are fresh,
  and the fail and its diagnosis stay on record meanwhile.

## D319: FR-43 part 3's registered comparison passes

2026-11-23, about 17:26 UTC. The builder ran the integer-unit population operator, option B (D315), at 52935908 from a
clean frozen snapshot. It was judged under the criteria tagged fr43-part3-criteria-2026-11-23, which were fixed before the
references returned, against the code-blind references tagged fr43-part3-references-2026-11-23. The verdict is in
/mnt/workspaces/Cells/fr43-part3-20261123/evidence-52935908/compare/verdict.json (sha256 548b7928b04c6a4d...).
- **W1, W2 and W4 agree with the references at rounding,** at 20 and 5 ms: event times within 1.8e-14 s and amounts within
  6.4e-15 fmol, against bounds of 1e-9. The events, channels and counts are the same. W4 is the first use of the
  node-side read.
- **W3, the two-way coupling, converges at order 1.96** under step halving from 20 to 1.25 ms, inside [1.7, 2.3]. Its
  RMS/dt^2 varies by a factor of 1.82, against a bound of 4. The RMS at 1.25 ms is 1.47e-7 s, against a bound of 1e-6.
- **C3.3:** at 16,384 sites with feedback off, the fraction with no active unit falls inside its band at all ten times
  (z = 3.89). The k_a +10% plant misses at all ten.
- **C3.5:** at f = 1/2 exactly (64 seeds x 128 sites), exactly one recipient receives each draw. The frequency is 0.4954,
  inside 0.5 +- 0.0182. The f = 0.55 plant falls outside.
- **The plants are data per world,** so the cached-rollout hazard cannot reach them.
- **Disclosed:** the builder chose W3's window and phase band after its own engine and development runs. That is
  recorded in the registration's section 5.
- **It lands after FR-43 part 1,** gated against main.

## D320: FR-30's registered benchmark on Revilla 1999 fails: 4 of 6 comparisons, both misses at -80 mV

2026-11-23, about 17:44 UTC. The independent checker's score, under section 13's rule 4 and D311.
- **Provenance:**
  - the registration is tag fr30-revilla1999-registered-2026-11-23, and the reader erratum is tag
    fr30-revilla1999-reader-erratum-1-2026-11-23, which changes resolve's container step only;
  - the score ran from a clean snapshot of 00bc183e;
  - the inputs are predictions.json 20ca2a4a... and held_out.json e8368083..., both unchanged;
  - the verdict is /mnt/workspaces/Cells/fr30-benchmark-20261123/verdict/checker_verdict.json (af9f402d...), with
    the scorer's own verdict.json (c28010d5...);
  - the checker recomputed all six comparisons without the scorer, and they agree.
- **The six comparisons:**
  - **-80 mV:** tau_fast passes (1.51 against 1.75 s, within 2 SEM). tau_slow fails (19.40 against 13.39 s, ln ratio
    0.370, outside 2 SEM). G_ss/G_0 fails (0.397 against 0.478, off by 0.081, beyond 2 SEM's 0.053).
  - **+80 mV:** tau_fast passes, through 2 SEM only (1.51 against 2.17 s). tau_slow passes (19.40 against 16.45 s).
    G_ss/G_0 passes (0.397 against 0.384).
- **Rule 4 as written also fails,** so the verdict does not rest on D311's "both" reading:
  - G_ss fails at one voltage of two;
  - tau_slow passes at one of two, not more than half;
  - the 75% clause holds, at 3 of 4.
- **What the fail does and does not show** (corrected 23 November; the first reading here overstated it):
  - **The +-80 mV acceptance windows overlap for every observable:** tau_fast 0.47-3.77 s, tau_slow 12.1-16.8 s and
    G_ss/G_0 0.4245-0.4339. So one |V_j|-symmetric prediction could have passed all six.
  - **The fail shows that this fit missed, not that symmetry fails.** Its tau_slow (19.40 s) lies above both
    polarities' observations.
  - **The polarity difference is one study's indication:** G_ss/G_0 differs between -80 and +80 mV by about 2.6
    combined SEM, tau_slow by 1.1 and tau_fast by 0.3. The in-sample fit's G_ss residuals at +-60 and +-100 mV
    point the same way, from the same paper. One wet-lab experiment is never fully trusted (the user, 23 November).
- **Disclosed:**
  - the checker wrote the reader erratum from value-free structure logs before reading any held-out value;
  - the lead ruled one parameter set after reading, masked, the Lean lane's line on polarity-symmetric gates
    (D317).
- **FR-30's law stays development-only** (D262).
- **The user's decision (23 November): a polarity-aware gate within FR-16, with a fresh blind benchmark on
  Ek-Vitorin 2016, extractor first.**
  - The FR-16 design starts by checking polarity dependence in independent sources, including whether the
    benchmark's junction is homotypic. It does not open Ek-Vitorin 2016, which stays sealed for the benchmark.
  - The law's form changes only if independent sources support it.

## D321: speeding up current runs: the shared compile cache, cold where seconds are measured, and a first L4 timing for the gap-junction field

2026-11-23, about 18:19 UTC. The user's two decisions on the speed-up note,
/mnt/workspaces/Cells/speedup-20261123/NOTE.md. The note measured from a clean snapshot of main f721e1d8.
- **The shared JAX compilation cache is adopted in two steps.**
  - **Background:** it passed qualification on this machine's CPU on 20 November
    (/mnt/workspaces/Cells/cache-qualify-20261119/run-1), with every output bitwise, and was never adopted.
    - Warm, it cut G1 from 541 to 177 s and tiers 1+2 from 1,496 to 1,027 s.
    - Today's sample of 12 G1 worlds, from all five families, is bitwise cold and warm.
  - **Step 1, now, scripts only:**
    - **Tier seconds are always measured with the cache disabled.** test_tiers.py enforces this, and fold refuses
      a measurement without the cold marker. Measured warm, 77 tier-2 files would refile as tier 1, and even an
      empty shared cache moves 27.
    - **Gates are cold by default.** gate.sh, stack.sh, nightly_tiers.sh and the fr_landing scripts disable the
      cache, log it and check that no entry appeared.
    - run_detached.sh disables the cache in every unit that is not run with --jax-cache, so judged and
      registered runs stay cold.
    - **Development runs may opt in** with run_detached.sh --jax-cache. That uses one CPU-only folder per jaxlib
      version and CPU model under /mnt/workspaces/Cells/jax-cache/, in JAX's default mode as qualified. A nightly
      sweep caps it at 8 GB. JAX's own eviction under filelock is not adopted: it is unqualified and scans every
      entry on each write.
  - **Step 2, after a replay of about one lane-hour:**
    - Gates read and write the cache. That saves about 15-20 minutes per full gate.
    - The replay must cover two lanes writing from two trees at once, a case the qualification did not cover.
    - The nightly full tier run stays cold, as the control.
- **The gap-junction field on the L4: a measured timing first.**
  - One windowed timing goes through the vector path, which is already admitted on a GPU, with no src change.
  - It runs in a short block announced to the visualizer, after FR-43's GPU needs.
  - The projected gain is 2-5x per point, not measured. The full qualification of the device row checks on the
    GPU (about 1-1.5 agent-days and 1.5-2 L4-hours), and the tagged GJ-N1 amendment it would need, are decided
    on the measured number.
- **The lead's rulings:**
  - **A routine fix:** configure_caches() stops turning a cache on implicitly for cells ensemble workers, and is
    off on the GPU. That removes the path of the 8 November L4 bitwise failure.
  - **Deferred:** resolved_pump_composite@1 in cells ensemble, since no current run uses cells ensemble, and the
    assembly_lineages@2 ensemble adapter, which would gain no speed.

## D322: OL6 Protocol G passes in both scopes

2026-11-23, about 19:06 UTC. The independent checker's verdict under the tag ol6-protocol-g-registered-2026-11-23 is
/mnt/workspaces/Cells/ol6-checker-20261123/verdict_protocol_g_both_scopes.json.
- **The runs:**
  - scope 1 ran at 3e50d48d;
  - scope 2 (50 fissions) ran at 2263d11c, the first main head holding S7;
  - both ran from clean frozen snapshots whose registered files are byte-identical to the tag.
- **Tier 1 passes in both scopes:** 1,280 of 1,280 seeds.
  - Scope 2 runs through the 50th trigger, 2,030-2,398 events.
  - Every uniform, first daughter, trigger index and partition's uniforms are bitwise equal.
  - There are no coincidences, and the largest time ratio is 0.167 against a threshold of 1.
- **Tier 2 passes:** 180 statistics in scope 1 and 360 in scope 2. The largest |z| is 3.81 against a pass bound of
  4.5. None is in the band, and none is censored.
- **The plants are caught:**
  - G-P1 in 64 of 64 seeds in every world, with counts equal to the registered power table;
  - G-P2 in every world, with the smallest per-world largest |z| at 29.0 (scope 1) and 41.8 (scope 2). Its z
    equals the registered power to 1e-15 and 5e-14.
- **Independent checks:** the checker re-derived tier 1, tier 2 and the worlds with its own code, and spot-checked
  the raw arrays outside the judge.
- **Reported only (section 7):** paired on the same seeds, the physical measure moves the passage time by -1.80%
  on average, negative in 20 of 20 worlds, against the predicted -1.75%.
- **Not run:**
  - @1 under pair_consistent@2, since "reported beside" has no procedure;
  - a scope-2 physical arm.
- **Disclosed:**
  - the checker's event limit (8,192 events, 2.34 s), which the lead kept;
  - a claim-and-skip change to the run driver;
  - an I/O-only change to the judge after its first freeze, with its self-test identical;
  - timing smokes on unregistered seeds 900001+.
- **Protocol D's fail stands as D318.** It is to be re-registered after FR-43.

## D323: FR-46, FR-47 and FR-48: the user's rulings with a reviewer's additions; FR-48 is built first, then FR-46, and FR-47 is registered before its build

2026-11-23, about 19:10 UTC. These rule on the design note /mnt/workspaces/Cells/fr46-48-design-20261123/DESIGN.md, with its
section 9. The user agreed with the recommendations and relayed a reviewer's comments, which are adopted.
- **FR-48, a lumen standard potential (R1-R3):**
  - The species owns an absolute `lumen` standard potential. Records report Delta = mu0_lumen - mu0_solution.
  - The shell law keeps all of Delta on the exit.
  - **What the qualification claims:** the equilibrium ratio, Binomial(N, 1/(1 + e^Delta)) at equal volumes, and
    detailed balance. The relaxation time follows the law's rate convention and is not claimed.
  - **Rows:** a nonzero solution potential, with a plant that reads the lumen value as an offset; and the undeclared
    default.
  - **Version 1** covers prescribed shells only, with the rest refused by name. The key is statically absent unless
    declared (D148).
- **FR-46, binding from a shell's inner face (R4-R6):**
  - One face per complex, and shells only in version 1.
  - **The face rule propagates faces by ligand moiety over every wall state,** from the stoichiometry, not from
    declared pairs. A reviewer reproduced a carrier that passed the proposed check: the ligand went through a
    ligand-bearing wall state that had no binding pair of its own.
  - **Rows:**
    - the reviewer's counterexample first, as a failing row;
    - carriers with zero, one and two intermediates refused;
    - a same-face isomerization admitted;
    - a run-level row: a shell closed to the ligand keeps the lumen at zero.
  - **Rule 3's recorded message** is revised in FR-46's own landing, with the one recorded string declared in probes2's
    compare. All 22 historical refusal inputs still refuse.
- **FR-47, shell exchange and washes in the deterministic representation (R7-R9, R11):**
  - **Gates:** autonomous switching gates, meaning forms interconverting by a wall step. Gates driven by bound states
    are refused in (d).
  - **Zeros (E2):** true zeros for first-order tracer places, through the difference form.
  - **Site binding** in (d) shell worlds is refused by name in version 1.
  - **min_count 10** is recorded as the run setting only, not as a qualified n_min.
  - **E2's derivative.** At an empty place, the flux's one-sided derivative must be the first-order law's, not the
    zero that exp(safe_log(n)) gives, because the Rosenbrock stages use it.
    - Rows test the flux and its one-sided derivative at an empty reactant and at an empty product.
    - A row tests the step-halving order across a step that starts at zero, with the old factored form as its plant.
    - A stated rule for stage or step results below zero at E2 places replaces the envelope's guard there.
- **FR-47's qualification (R10, R12),** tagged before the build, with C9 and P9 (the heat against the reference's
  closed form):
  - **Zero uncertainty is classified from the reference, before the run.**
    - Where the reference predicts a constant, every replica must match it, and one wrong replica fails.
    - Where it predicts spread, identical replicas still face the spread test.
    - A tolerance exists only where it is derived, for two routes to one constant by different arithmetic, as
      release_check's bound is. The lead's earlier proposal of a declared rounding floor is withdrawn.
    - **The same rule serves Protocol D's re-registration,** which must justify any excluded pair from the model, not
      from the replicas.
  - **C6's spread test** takes its fourth moment from the reference, or another justified spread test is chosen.
  - **C8's slope** is claimed as measured only where 128 replicas resolve it by the reference's own estimate.
    Elsewhere it is reported.
  - **Seeds:** fresh seeds, disjoint from every probe and smoke seed, are named in the tag.
  - **The judge** is first run on a file written by the references' own writer, on invented inputs.
  - **FR-43 part 2's lessons apply:**
    - the reference spec states the unit of every declared count;
    - the references agent shows bitwise regeneration under other hash seeds;
    - there is one tag, at the final head.
- **Order:**
  - FR-48, then FR-46, in one gate if both are ready together.
  - FR-47's protocol and reference spec come next, and its build follows FR-48.
  - Gates wait for FR-43's lanes.
  - FR-47's exact ensemble, about 3 CPU-hours, runs after Protocol D's re-registration or on other CPUs.

## D324: FR-43 part 2's registered comparisons pass: C2.3, C2.6/C2.7 and C2.8

2026-11-23, about 19:24 UTC.
- **The judgements:** the builder's, run against the code-blind references tagged fr43-part2-references-2026-11-23
  (0172e1b9, under the spec's amendments 1 and 2) by CRITERIA.md, with a floor of 1e-8 and a band of [3.6, 4.4].
  Each ran once, from a clean frozen snapshot.
- **The records:** /mnt/workspaces/Cells/fr43-20261123/part2/registered-20261123/.
- **C2.3, two writers on one shared stock at fixed volume (2A at 205dbaa5): passes in the sink and in the source.**
  - The gene unit's books are judged, at ratios 4.004 (sink) and 4.009 (source).
  - The other quantities fall below the floor at both steps. In the source, the network's books and route rate
    agree at rounding, since X -> N does not read N.
  - The planted 1%-fast network fails in n_N and in the network's books, at ratio 1.000.
- **C2.6 and C2.7, the swelling cell (2B at ea813fae): pass, with every ratio judged.**
  - amounts 3.930 and V 3.999;
  - the engine's endpoint energy identity 4.006;
  - F against the reference 4.017;
  - water's heat 4.000, the bath's water work 3.999 and the network's heat 3.986.
  - The plant that reads V0 is refused by the energy ledger.
- **C2.8, the swelling pair (2B): passes.**
  - n_W, the network's books and the network's rate are judged, at 4.000, 4.000 and 3.999.
  - The rest fall below the floor.
  - The two plants that read V0 (the gene unit and the network) fail in amounts by factors of 1.7e5 to 1.3e8,
    at ratio 1.000.
- **On record:**
  - c23-judge-a8444119, as failed evidence. Its stage-1 reference read machines = 100 as fmol, the spec's
    unstated unit, which amendment 2 fixed.
  - c26-judge-3455afd2, as development evidence.
  - The superseded reference tags fr43-part2-references-c23-2026-11-23 and fr43-part2-references-c26-c27-2026-11-23.
- **2A and 2B land after their gates.**

## D325: the gap-junction replication's GJ-L1 comparison passes

2026-11-23, about 19:24 UTC. The GJ owner's registered engine run and judgement are in
/mnt/workspaces/Cells/gap-junction-20261123/judged/.
- **The verdict:** 57 of 57 real entries pass, 45 arms and 12 chains.
  - The two plants, each scaling every junction permeability by 1.01 in the definition, are caught, with margins
    of 2.0e9 and 1.0e3. They are the only failures, as required.
  - No entry is inconclusive, so no retry is owed.
  - The largest real margin, gap against tolerance, is 0.333 on the as-written arms. That is the registration's
    expectation: the dt/4 error is about a third of its estimate, since the tolerance is three times the
    estimate.
- **The engine run:**
  - one registered invocation (figure3, figure5, figure8, control and aswritten, at the 600 s horizon);
  - from the clean snapshot of main 23593267, equal to the tag in src/ and validation/ except unrelated files;
  - on CPU 8, under lane B's lock, paused by the holder's yields and never stopped;
  - the table was built from the engine alone before any reference was read. Its sha256 is
    672373c7a747c6c4791d14fe70ee9853bd7a30a2682de00185c19ed335c601df.
- **The judgement:**
  - from a clean snapshot of main 9eb9890a, with the judge unchanged since its tag;
  - the interface is byte-identical to gj-linear-references-2026-11-23's;
  - the verdict's sha256 is b3e9c1cc4185462341b81f72c38777a00004791153b660c13690969723f1a94f.
- **The plants' isolation:** each plant's definition fingerprint differs from its reference arm's at every step taken
  (plants-isolation.json), so a program cached per model computed the planted values.
- **Next:** GJ-N1's 1D line runs now, about 8 CPU-hours. The 2D field waits for the sparse solver (FR-17's stage 1)
  and a GJ-N1 amendment that names it.

## D326: the gap-junction field on the L4 is measured; the user's decision is to place GJ-N1's field after the sparse solver lands

2026-11-23, about 22:30 UTC. This follows D321's first item.
- **The timing.** It is development only, with no outcome read, in /mnt/workspaces/Cells/speedup-20261123/l4-timing/.
  - It ran from a clean snapshot of main 31fde682, which includes the field-path change d6d42b46.
  - It ran GJ-N1's field at D = 1e-13 (dt 1/128 s): one world, 9 windows of 32 steps, through run_vector_windowed,
    with no src change.
  - The L4 took 21.2 ms per world-step after the first window, and 19.7 ms in steady windows. The same driver,
    snapshot and arm on one CPU took 65.5 ms. That is 3.1x, inside the projected 2-5x.
  - Compiling took 73.4 s on the L4 against 40.2 s on the CPU. Device memory peaked at 388 MB. An L4 run also keeps
    one host CPU busy.
  - **Agreement after 288 steps:** 31 of 39 state arrays are bitwise equal, and the other 8 differ by at most
    4.3e-16 of their own array's scale.
  - The block followed the GPU protocol (the gpu.reserved flag and the exclusive gpu.lock), with the visualizer on
    hold. The lock was held for about 1.5 of the 10 allowed minutes.
- **What it means for GJ-N1, as estimates:**
  - the upper end of the search (2.56 million steps) would take about 47 h on one CPU, or about 15 h on the L4;
  - with the sparse solve on a CPU, it would take about 30 h (amendment 1);
  - the whole search would occupy the L4 for 40-55 hours one point at a time, and the visualizer uses the same
    GPU.
- **The user's decision:** time the sparse solver on both the CPU and the L4 once it lands, then choose the field's
  placement on those numbers. The GPU qualification of the device row checks waits until then.
  - Any GPU placement needs a further tagged GJ-N1 amendment before field points run.
- **Disclosures for GJ-N1's record, made before any field point runs:**
  - this timing ran the field for 288 steps (2.25 s simulated) and compared CPU and L4 state arrays for agreement
    only;
  - the GJ owner's development timings ran the 25 x 25 field for up to 36 s at D = 0 and 2.25 s at 1e-13. They
    were window timing, host and trace checks, the bit check and the D148 guard dumps;
  - no criterion was computed and no state was printed in either. The short field states saved in
    probes/field-profile-01 and gj-fieldpath-20261123/d148 were never read.

## D327: FR-44, FR-45, FR-49, FR-50 and FR-51: the user's approval of the designs, with two reviewers' qualification details; build order and file ownership

2026-11-23, about 22:36 UTC. These rule on the design notes /mnt/workspaces/Cells/fr44-45-design-20261123/DESIGN.md and
/mnt/workspaces/Cells/fr49-51-design-20261123/DESIGN.md. The user approved the designers' recommendations, with two
reviewers' additions. Names follow the notes.
- **The fail-open fix comes first** (FR-44 note section 5.2).
  - Today a wash is admitted at a node that templated_polymerisation@1 exports into, or degrades outside at.
  - The fix refuses both by name, each with its own row, plus a passing control where the wash is at a different
    node.
  - Before it lands, it lists every existing and registered world the refusal would catch, and discloses any judged
    run that used one.
  - It lands after FR-43 part 3, before anything widens wash admission.
- **FR-44, labels across a wash:**
  - **The core ships first.** The wash reports a typed LiquidExchange, read from each wash event's own
    wash_last_sample_fmol and wash_last_supply_fmol, not from cumulative deltas.
  - The incoming buffer carries the base label, even during an active label window.
  - Labelled ions at a washed node are admitted: their amount is kept and their shares are diluted.
  - label_outside_removed_fmol joins same_physics's exact extra-field set.
  - The regression for a full wash that follows an earlier wash is kept.
  - **Admission by species** (the written_species hook, about 0.5 agent-day) comes as step 3, after FR-44 and FR-45
    land. Sites as label reporters, and crossings at a washed node, stay priced follow-ups.
- **FR-45, competing ligands:**
  - Shared site_sets inside site_occupancy@1, widened in place under D148 with crossrev renewed.
  - Internalisation and the occupant-replacement operator are refused beside site_sets in version 1.
  - The coupling operator @2 is admitted, reading a shared set's theta_b.
  - **Before renewing the baseline:**
    - show D148 compatibility on FR-3's existing worlds, their derivative programs included, and check whether FR-3's
      judges take derivative programs;
    - write the full new crossrev record first, so the renewal is against one clean baseline.
  - **A registered protocol** (R-eq, R-ode and R-dG, with code-blind references) covers the finite-volume
    equilibrium, the per-ligand balances and the shared-site heat.
  - **Bound-site retention** is tested on the wash operator alone: bound arrays bitwise before and after. Saved rows
    are not used, because binding resumes within the same step.
- **FR-49, compartment compositions:**
  - Its rulings 1-9 are as recommended, with the registered protocol fr49-compartment-compositions-v1 over World L
    and World B.
  - **Checks for combinations two changes create.** Whichever change lands second carries a check, or a refusal by
    name, in that same landing for:
    - a compartment with labels and a wash at a separate node;
    - competing ligands sharing sites at a compartment;
    - the inherited composition (cell_owned_compartments@1, neutral_arrival_labels@1, scheduled_compartment_wash@1 at
      an external node), and its four-way form with unlabelled site_occupancy@1 once Admission by species lands.
  - Each combination is enabled only once its check passes. The second builder lists what newly parses at its merged
    head.
- **FR-50, one-way records:**
  - Its rulings 1-8 are as recommended. Phase 1, then phase 2 after FR-51, with the registered protocol
    fr50-one-way-records-v1 and one_way_gap_relative.
  - The gap is measured before any correction.
  - The channel split is built from channel_rates' own factors, so opening, availability and block are shared by
    construction.
  - **The planted fault** leaves FR-51's block out of both directions. At zero net current that doubles both records
    while the net, ratio and gap all pass.
  - Each direction is checked against an independent absolute value from the reference. Transporters get the same
    absolute equilibrium check, and the gap is defined when both directions are zero.
- **FR-51, two blocking modes:**
  - Its rulings 1-6 and 8-9 are as recommended. These are Option A, a constant blocker in version 1, s = +1 from
    outside and -1 from inside, N2 refused beside a blocked population, blocked_channels and block_modes, the readout
    channel_unblocked_fraction, and the registered protocol fr51-channel-block-v1.
  - **Ruling 7:** each mode declares exactly one of electrical_distance (delta in [0, 1], giving s z_B delta) or
    effective_valence (> 0, signed by s sgn(z_B), with blocker.valence nonzero kept for the charge's sign). A check
    and a plant row cover that branch.
    - The slope-bound probe is rerun at the steepest admitted value.
    - The step bound must see u's dependence on E under V - E.
  - **The unblocked fraction u and the slope term's (1 - theta) must be right at both ends:** exactly 1 at zero
    blocker, and relatively accurate at strong block. A single mode with c/K = 1e18 must give about 1e-18, not 0,
    which the literal 1 - sum(w theta) cannot do in binary64. Both ends are proved on the compiled program.
  - At reversal the fraction is checked directly. The current ratio is used only away from reversal.
  - The coupled-ion steepness case (polyamine block of an inward rectifier) rests on one study, recalled from memory.
    Its source is checked before it enters the repo, and it is worded as an indication.
- **Order and file ownership** (one owner per file at a time; each builder merges main just before hand-off,
  regenerates the composition table with --write, and lands serially):
  - **the wash files:** FR-43 part 3, then the fail-open fix, then FR-44, then FR-49's wash narrowing;
  - **site_occupancy.py:** FR-45, then FR-49's site-occupancy pairing;
  - **surface_pump_v3.py:** FR-17's call-site refactor (about 30-60 lines: readouts, imex_step, layout types), then
    FR-51, then FR-50. Amended the same evening, after the FR-17 builder's report; FR-17 is on GJ-N1's critical path;
  - **FR-49's other pieces** proceed in parallel.
  - Each registered protocol and its spec are tagged before its engine build. Gates wait for FR-43 2B's landing.

## D328: FR-43's three planned parts are on main; a correction to 2B's merge message

2026-11-24, about 11:37 UTC.
- **The landings:**
  - part 1, the 1,024-species capacity (bbc99163);
  - part 2A, two writers of one shared pool at fixed volume (c9687d68);
  - part 3, the integer-unit population with its division hook (7fb0ad87);
  - part 2B, both writers reading the current volume (2ca07dcb).
- **Every registered comparison passed:** part 2's C2.3, C2.6/C2.7 and C2.8 (D324), and part 3's (D319).
- **A correction.** 2B's merge message says "FR-43's build is complete". That overstates it, and the commit is
  pushed, so the correction is recorded here.
  - Part 3 stays open until D152 reactions and the gene unit can co-write a moved row.
  - The version-1 refusals stand: integer_unit_population@1 beside scheduled_compartment_wash@1, and in the region
    readouts.
  - Each lifts only as its own qualified extension.
- **The follow-up queued for after FR-43:** fixed_working_size gains a factor-width term. It is pre-existing, and
  covered far above any declared network.

## D329: the Xenopus lane's XC0 registered comparison fails; diagnostics before any next step

2026-11-24, about 11:37 UTC.
- **The run:** an independent runner, who built none of XC0, ran the procedure of erratum 1
  (xc0-rule-erratum-1-2026-11-23) exactly.
  - the snapshot of 260d7c7f;
  - the manifest, equal to coverage.counts;
  - the six P1LB segments on lane A;
  - the table;
  - the tagged retry, once, under the lead's ruling: the first judge refused, reading no value, on 46 refused table rows,
    none of them C8b;
  - the judge.
- **The record:** /mnt/workspaces/Cells/xenopus-lane-20261119/xc0-judged/, with verdict.json
  79bd2b243b0552a1a0b342d8d6e274edb4968e1ebf315c822a11c1400fc53669 and VERDICT.md.
- **The registered verdict: fail.**
  - C0-C5 pass. C6 is not testable. C7 and C8 fail.
  - Rows: 7,382 pass, 4 fail, 44 engine-refused, 242 not run, 272 not mappable, 736 info.
- **The four failures:**
  - C7.pump_cell_charge_per_fmol: a relative gap of 3.43e-11 against a band of 1e-12;
  - C8.b_final_c for Cl, K and Na: the bare run's 64 s node concentrations miss their 1e-6 bands by 6.4e-6, 5.0e-4
    and 1.1e-5 relative. The engine's h and h/2 values agree to about 1e-13.
- **C6:** 44 rows are refused by the engine's scan, with no sign change found at 24 or at 48 points. The retry
  recovered 2 rows, which pass.
- **No cause is attributed yet.** The runner flagged candidates without settling them:
  - for C7, a rounded Faraday constant on one side;
  - for C8, whether the reference's "final" is its own 64 s value or an end state;
  - for C6, a root that the coarse scan misses.
- **Three labelled diagnostics come first,** run by someone who built none of XC0:
  - C7: the declared constant, and whether the rule has the engine read it;
  - C8: each ion's miss at 32 s against 64 s, and the rule's and DESIGN's own text for "final";
  - C6: where the reference's roots sit in the scan domain, and how many there are.
- **Any v2 cannot be blind on these rows.**
- **T1 and T2** are reported as unconstrained calibrations. Where they rest on one wet-lab source, they are
  indications only.

## D330: GJ-N1: the 1D line's engine table is hashed; the user's decision, qualify the device checks on the GPU and run the field's longest points on the L4

2026-11-24, about 11:37 UTC.
- **The line search finished** (search_exit 0, cells_exit 0) from main 23593267 under amendment 1's record. The hashes
  are in /mnt/workspaces/Cells/gap-junction-20261123/judged/line-01/SHA256SUMS:
  - cells-line.json 92fad3a4f938288fe500a12e5f2006f7b8a373fe00d66cb3fd6d1f1af8b1bf7b
  - run/search.json 0ee59228bdc9b0f25c0e72fa4faba969319611f32dba0234e456ba23175d8d37
  - run/points.jsonl 798afd4bd7f7222c56364dff6ae72d0ac0c291d491dd575bc84d59499afea24b
  - run/half_step.jsonl ea8d6567d1bf1fea1f5c016bf407863589766f7a6b6e3975de6379ff266a3613
  - run/uncoupled.json 870025e978ece6685b24d5c8842fc5ed665ef87ad0f8d0843a2e0be686285e98
- **The references stay sealed** until the field's table is hashed too.
- **The four placement numbers** (FR-17), in ms per world-step for the field at D = 1e-13:
  - on one CPU: @2 53.3, the sparse solver 29.2;
  - on the L4: @2 13.1, the sparse solver 10.1.
  - On the production path on a CPU, the sparse solver is bitwise equal to @2.
- **The user's decision: qualify the device row checks on the GPU, then run the field's longest points on the L4.**
  - The qualification uses the sparse solver on the production path: the host-against-device spread, the bitwise
    and band tests, and memory.
  - A tagged amendment 2 comes before any field point. It fixes in advance which points run where, and keeps every
    pair the judge compares (h against h/2, the bracket's ends) on one device, since the CPU and the L4 differ at
    rounding.
  - The visualizer is on hold (the user), so the L4 blocks need no notice for now.

## D331: FR-49's first landing: World L's registered judgement passes

2026-11-24, about 12:23 UTC.
- **What landed:** parts H and L of fr49-compartment-compositions-v1 (with amendment 1 and the judge tag), at the
  merge 7d021548.
  - The gene unit and neutral arrival labels are admitted beside cell-owned compartments.
  - Each has its own check: outside degradations and exports at a compartment's node are refused, and labels
    beside membrane state are refused by name.
- **World L's judgement:** run once from a clean snapshot of the tagged judge's head (0cfdffaa) against the code-blind
  references fr49-references-2026-11-24 (35c91d25), at the registered 3600 s horizon with dt 2 s and 1 s. **It passes.**
  - L1, L2, L3, L6 and L7 pass. L7 is a bitwise restart at 900 s.
  - L4's order ratios are 4.0037, 4.0034, 4.0043 and 4.0011, in the band 3.6-4.4. L5's sizes are 1.0e-7 to 6.6e-7,
    against 1e-3.
  - Plants (a)-(c) fail L4 at a ratio of about 1, and plant (d) fails L7, as registered.
  - The record is /mnt/workspaces/Cells/fr49-expression-labels-20261123/judged-0cfdffaa/ (verdict.json sha256 begins
    509118c73f3fde72).
- **Still to come:**
  - World B and the combination checks C1 and C2, after FR-49's site pairing (following FR-45) and its wash
    narrowing (following FR-44);
  - C4's four-way form, by amendment, once admission by species lands.

## D332: XC0's failures diagnosed (labelled, post-verdict): rule-side definitions and an engine parse tolerance, not physics

2026-11-24, about 12:26 UTC. These are labelled diagnostics by an agent who built none of XC0, run after D329's verdict and
re-judging nothing. They are in /mnt/workspaces/Cells/xenopus-lane-20261119/xc0-diagnostics/DIAGNOSTICS.md. **D329's
fail stands.**
- **C7 (pump_cell_charge_per_fmol): two Faraday constants.**
  - The rule declares F = 96485.33212, to 10 digits, 3.43e-11 below the exact SI value N_A*e. The reference uses the
    declared value.
  - The engine uses its SI constant. No XC0 code has the engine read the declared F, and the rule's
    declared_deviations doesn't mention it.
  - The gap equals the ratio of the two constants, 34 times the 1e-12 band.
- **C8 (b_final_c): "final" means two things.**
  - The reference, its README, SEMANTICS.md and DESIGN's erratum mean the analytic Donnan end state. Erratum 1 maps
    "final" to the bare run's value at 64 s.
  - The engine's bare run matches the reference's own RK4 bare values to 1.1e-10 at every time. The reference's own
    64 s values miss its b_final_c by the same amounts.
  - The miss decays at the run's slow mode, tau 9.35 s, a charge-neutral exchange of K for Na. That accounts for K's
    47-78 times larger relative miss.
  - 64 s was set from Na's single-ion time, which is too short for the slowest mode.
- **C6 (v1_eq_ratio and v1_eq_x, 44 rows): the reader's settings meet a parse check.**
  - Each key has exactly one root. At the reader's B_out of 10 mM, the cell holds 1e6-1e10 fmol of B at the roots.
  - There the parse check |q - initial_charge_C| > 1e-20 C is finer than float64 can resolve, so the worlds are
    refused, and the scans see no sign change.
  - Four roots also lie beyond the reading's domain of 1e6.
- **What a v2 would change (it cannot be blind on these rows):**
  - **C7:** declare the SI constants, or the deviation, with no band tighter than the constants agree.
  - **C8b:** define "final" once, and settle whether the bare node is compared.
  - **C6:** state B_out and the domain, and keep B_in within float64's charge resolution.
  - **The engine, separately:** the parse check's absolute 1e-20 C tolerance could scale with float64 resolution.
- **What follows is the user's decision.**

## D333: the user's decision on XC0: a v2 for the diagnosed rows, and a separate engine fix

2026-11-24, about 12:36 UTC, following D332.
- **D329's fail stays on record.**
- **XC0 v2 is registered as rule erratum 2,** disclosed as not blind on these rows. It changes only what D332 found:
  - **C7:** declare the SI constants the engine uses, or the deviation, with no band tighter than the two sides'
    constants agree.
  - **C8b:** define "final" once, and settle whether the bare node is compared.
  - **C6:** state B_out and the reading's domain, keep every B_in within float64's charge resolution, and count the
    points a parse drops in a scan's refusal.
  - Only those families are rerun, on the same frozen engine (260d7c7f), by an independent runner, with code-blind
    references regenerated where a declared constant changes.
- **The engine fix, separately:** surface_tissue.check_definition's absolute 1e-20 C tolerance on the charge anchor
  scales with float64's resolution of the terms.
  - It is a definition-time check, so no program changes.
  - It is a gated src change, after FR-17 lands, since FR-17 also edits that file.

## D334: FR-30's next benchmark keeps the symmetric law; FR-38's second comparison is registered with arms A and B deciding

2026-11-24, about 12:45 UTC. The user's decisions on the two drafts, with the advisor's review applied:
/mnt/workspaces/Cells/fr30-next-20261124/ (POLARITY.md, REGISTRATION_DRAFT_13_7.md) and
/mnt/workspaces/Cells/fr38-next-20261124/REGISTRATION_DRAFT.md.
- **FR-30, superseding D320's "polarity-aware gate" line:**
  - **The law.** The Ek-Vitorin 2016 benchmark fits junction_series_gates@1 as declared, with one parameter block.
    - Identical hemichannels whose gates read only V_j are symmetric by construction, so a polarity-aware gate cannot
      change a homotypic prediction.
    - Independent sources indicate near-symmetry for homotypic Cx43, each one study's indication. Revilla's one-cell
      protocol ties the sign of V_j to one cell's V_m.
  - **@2** (placement and polarity per gate) is logged as a design note under FR-16 F3, for heterotypic junctions
    only. A correction: what the gap-junction replication needs is F3's two-state Cx45 gate in Chen-Izu's manner. No
    heterotypic junction is documented in it.
  - **The one-cell protocol** (the user's ruling, made mechanical before Tag A):
    - the extractor records the protocol type as an enumerated, value-free field, including what "not stated" maps
      to;
    - under a one-cell protocol, disjoint +-V_j windows are reported per observable as confounded by V_m, neither
      pass nor fail. Overlapping observables are still judged;
    - a minimum judged set is stated, below which the result is undetermined;
    - the justification is non-identifiability, not a claim that V_m gating is real.
  - **The rest, as recommended, with provisos:**
    - a separate predictor;
    - a fresh fitter, barred from D311, D320, POLARITY.md and Revilla's extraction;
    - Part S only as a separately named steady-state result, with FR-30's own verdict staying undetermined;
    - SD converted only where the paper states what n counts;
    - generic modules, with the harness authored by the polarity check's author, who never fits, predicts or checks;
    - withheld cross-voltage summaries;
    - POLARITY.md committed without its two accidental quotes, naming fallbacks 7 and 9 as exposed and each source
      at its strength.
  - **What a pass licenses** is stated in section 13.7: one study's agreement. D262's status changes only by the
    user's decision.
  - **No fallback is opened** and nothing is downloaded for this decision.
  - **BITSEY's GJ_lib.py** names Jose Ek Vitorin as an expert colleague, a person, not the sealed paper. There is no
    exposure (the lead checked, by name only).
  - **Before Tag A:**
    - finish the exposure sweep;
    - rehearse Tag A's whole chain on Revilla's spent files in the new layout, reproducing section 13.5's
      conventions and D320's six lines.
- **FR-38's second registered comparison:**
  - **Scope:** arms A and B decide FR-38's verdict, and arms C and D (FR-43's shared pools and swelling cells) carry
    separate verdicts reported beside it.
  - **Changes to the draft's recommendations:**
    - in arm A, the stage complexes are reported, not judged, the designer's fallback. The first comparison went
      inconclusive on a stage complex's order;
    - the references are written afresh, since the net-rate blank lived in the old ones;
    - the near world's synthetic potentials are accepted, as a numerical-discrimination world with no biology
      claimed (D306's precedent). The registration states in advance what a miss there means, since its potentials
      lie outside section 3.3's range.
  - **The rest, as recommended:**
    - D271's order window, with the larger-pair estimate;
    - fresh worlds only;
    - a new judge, blind to the first comparison;
    - a pass recorded beside D313's failure, never in place of it;
    - the sheet's erratum I tagged before the rule;
    - export, producer identity, routed p and the observation layer left to later registrations;
    - no optional engine counters now;
    - A1's swelling-cell gap logged, not built.
  - **A correction to D316's reading:** R2's inconclusive verdict came from C_tx_3's observed order (3.94, then 3.69
    and 3.67 against the 3.5 cap), as D313's verdict records. It did not come from gross against net, which explains
    R1's failure.
  - Its judge uses FR-47's agreement.py, which reaches main with FR-47. Its 8-12 CPU-hours queue behind Protocol D's
    re-registration and FR-47's ensemble.

## D335: FR-17's GPU qualification (D330): block 2's findings, and the lead's rulings before block 3′

2026-11-24, about 13:35 UTC.
- **Block 2** ran on the L4 from snapshot 04032172, with the host thread on CPU 4 and its sibling 20 idle under
  the timed lock. CPUs 6 and 22 were never quiet for 30 s. The autotune was unpinned and no determinism flag was
  set.
  - **G1 fails at both D.**
    - Host and device modes differ by bytes from window 1 on: 16 arrays at D = 1e-13 (28 by window 8), and 12 at
      D = 0. They are amount increments, passive-route transfers and heats, and reaction ledgers.
    - The field arrays, which come from the sparse solver with no scatter, agree.
    - The builder's diagnosis, inferred and not yet shown by a repeat: the rollout's 94 scatter-adds run as atomic
      adds on the GPU, in an order that varies from run to run.
    - On the CPU, G1 passes, and a second process repeats bit for bit (G6's baseline: 8 of 8 window digests, 37 of
      37 arrays).
  - **G2 has not passed.**
    - Every window the device decided is within the amended bound: at D = 1e-13, "total" 0.0165 against 0.291; at
      D = 0, energy 1e-17.
    - Window 1 at D = 1e-13 was handed back to the host (device ratio 0.727, against the CPU device's 0.088). Its
      host ratio was not recorded, so it is unassessed.
  - **G5:** the device peak is 199 MB; the check's temporaries are 539 KB (D = 1e-13) and 459 KB (D = 0).
  - **G7, ms per step on the production path, whole core:**

    | | D = 1e-13 | D = 0 |
    | --- | ---: | ---: |
    | L4, device mode | 16.9 | 13.7 |
    | L4, host mode | 29.6 | 22.8 |
    | CPU timed lane, device mode | 32.0 | 28.3 |

    That is about 2×, before any determinism cost. D326 and D330's decision rested on about 3×.
  - **CPU against L4, final states:**
    - D = 1e-13 (2 s): 29 of 37 arrays identical, the rest within 5.5e-16 of scale.
    - D = 0 (32 s): reaction ledgers and amounts differ by up to 8.6e-8 of scale. That is well above rounding, and
      its cause is unknown.
- **The lead's rulings,** all made before any further L4 number:
  1. **G2's bound, amended** (amendment 1 of GPU_CRITERIA.txt, recorded before any L4 G2 value): on each ledger,
     the L4's largest spread ≤ min(0.4, max(0.1, 1.5 × the CPU's on the same definition)).
     - The reason: at steps 0 and 1 the bound is the bare atol, 1e-20 fmol, and a 625-cell global sum's rounding is
       a large fraction of it. The CPU's device mode, already in production, shows 0.194 there.
     - **G4's sampled spread takes the same bound.**
  2. **Handed-back windows count in G2 and G4.** Both read "every window", and the amendment changed the bound, not
     the windows. Handback counts are reported beside G2.
  3. **Registered and qualified GPU device mode requires XLA's deterministic-ops setting,** beside the pinned
     autotune file.
     - Before block 3′, the builder verifies the flag's effect in the installed jaxlib, including on autotuning, and
       records which flag is used and what it implies.
     - `admit` refuses GPU device mode without it. That check is a tripwire reading `XLA_FLAGS`, not enforcement;
       the bitwise G1 and G6 evidence is the guard.
     - It is an engine change, so tiers 1 and 2 and the admission gate run on its head.
  4. **The stop rule.** If G1 or G6 fails with the flag, the fail is recorded and the qualification stops, with no
     further amendment to G1, G2, G4 or G6. GPU device mode then stays unqualified, and the field's longest points
     run on the CPU.
  5. **Block 3′** adds:
     - one unflagged device-mode repeat, labelled diagnostic, to show the run-to-run variation directly;
     - the D = 0 CPU-against-L4 comparison, rerun, with Newton iteration counts per step on both devices.
  6. **Amendment 2 does not let R be compared across devices** until the D = 0 spread is explained and shown to lie
     below R's resolution.
  7. **The user's D330 decision goes back to them** once G7′, which includes the determinism cost, is measured,
     since its speed premise was about 3×.
- Block 2's unpinned, nondeterministic results stay on record as found.

## D336: the user's decisions: XC0's t_e stays out of v2, and FR-17's GPU qualification closes as failed, with the field's longest points on CPUs

2026-11-24, about 13:54 UTC. The user agreed with the lead's and the advisor's recommendation on both.

**XC0 rule erratum 2 (D333): `C8.bc_t_e` stays out of v2.**
- **Why it was raised.** The row passed in D329 under erratum 1's "final", the bare run's value at 64 s. SEMANTICS.md
  measures t_e "not from a late value of the run", so that pass rests on a definition that conflicts with the
  references.
- **Why it stays out.** D332 diagnosed b_final_c only, and D333 limits v2 to D332's findings. The erratum's author has
  seen the verdict, so adding a passed row would widen the user's decision.
- **What v2 reruns:** 349 rows. D329's pass on t_e is carried, and the mismatch is recorded in the erratum as a
  labelled post-verdict observation.
- **The lead's other rulings before the tag:**
  - **C7's tolerance:** |F_declared − F_SI|/F_SI plus the row's float64 allowance, evaluated and stated, so the
    tolerance is exactly as loose as the two constants' disagreement.
  - **C6:**
    - the erratum names the law that makes v1_eq_ratio and v1_eq_x independent of B_out: DESIGN.md's equilibrium
      ratio (B_in/B_out)_eq = (Na_out/Na_in)^n exp(−(n−1)FV/RT);
    - it derives B_out = 1e-5 mM from the 2^19 fmol bound over the declared scan domain, not from where the roots
      lie;
    - a rerun row whose key carries a B_out token would need its references regenerated before the tag.
  - **An independent cross-check of the C6 bound.** An exact-rational check of the frozen parser (17 controls)
    finds every refused balanced input at or above 2^20 fmol. Below 2^19 fmol the worst-case budget, 5.6e-21 C, is
    under the native 1e-20 C.
  - **The judge's source check** compares at run time with D329's recorded snapshot manifest, with no source hash as
    a literal. The six digests in the erratum are of D329's evidence files.
- **Disclosure:** the lead has seen D329's numbers on these rows (D332).
- **The tag** waits on the revised head and on the base rerun's CPU-hours. A new independent agent runs it.

**FR-17's GPU qualification (D330, D335) closes as failed.**
- **Block 3′a** ran from snapshot bc438c6c on the L4, with the host thread on CPU 4 and its sibling 20 idle under
  the timed lock, and `--xla_gpu_deterministic_ops=true` set.
  - **G1 passes.** Host and device modes are identical by bytes in all 8 windows, so the flag removes block 2's
    scatter nondeterminism.
  - **G2 fails as declared.**
    - In window 1 (steps 0–32) the device read "total" at 0.715 and handed the window back; the host read 0.202.
    - The spread, 0.514, is above the amended bound (0.291) and the cap (0.4). In windows 2–8 it is at most 0.016.
    - The device erred high, so the window went to the host and safety held. The criterion still fails, and D335
      bars amending it after the data.
  - **G7 with the flag,** ms per step: device mode 21.8 (16.9 unflagged), host mode 34.0 (29.6). That is about 1.5×
    the CPU's device mode (32.0), against the about 3× that D326 and D330 assumed.
  - **G6** is recorded when it lands. G4 was not run, and blocks 3′b, 4′ and 5′ are cancelled.
- **Consequences:**
  - **GPU device mode is not qualified.** The field's longest points run on CPUs, as amendment 1 places them. A
    tagged amendment 2 says so before any field point.
  - **The admission code.** If main admits GPU device mode, a plain refusal lands, with no XLA_FLAGS check, which
    nothing qualified could reach. If main already refuses it, only the driver and the criteria record land.
  - **A new GPU attempt would be a fresh registration** and the user's decision: for example, compensated summation
    in the device check, or the GH200.
- **Corrections to D335:**
  - **The D = 0 line.** The 8.6e-8 was measured against the increments' and gross ledgers' own scale. Against the
    amounts, the CPU and the L4 differ by at most 2.1e-16, one ulp. A one-ulp change of the start on the CPU alone
    gives the same picture, with no growth over 32 s.
  - **The pinned autotune file plays no part under the flag.** The flag disables timing-based autotuning: the
    flagged dumps hold no results.
  - **Two items D335 ordered did not run:**
    - the unflagged repeat, because the admit tripwire refused device mode;
    - the Newton iteration counts, because the hypothesis is excluded by construction: the reaction operator is
      explicit (SSPRK(3,3)), and the field arrays were identical between the devices.

    The scatter diagnosis rests on one shared executable, together with the flag contrast.
- **A finding for any device.** At steps 0–1 the bound is the bare atol, and the host itself reads 0.20–0.28 of it
  on 625 cells. Whether that fraction grows with cell count is being estimated. If it does, a larger tissue could
  refuse window 1 on rounding alone.

**FR-47's judged run and its checker's driver use the landed engine,** main at ec7e8c7d (the merge of 43763a36),
from a frozen snapshot. The registration was tagged before the build, so it names no engine revision. The fix for
inert wall places, in progress, is not in the judged engine.

## D337: XC0's erratum 2 and FR-30's Tag A are tagged before reading; the user's decisions on a core, FR-53 and a refused removal; SK2's one closing rate is flagged provisional

2026-11-24, about 14:22 UTC.

**XC0 rule erratum 2 is tagged `xc0-erratum-2-2026-11-24` at b477f433** (branch xc0-erratum-2). Its src/ tree equals
260d7c7f's, D329's engine.
- **What reruns:** 349 rows (C6 eq_ratio 172, C6 eq_x 172, C7 1, b_final_c 3, b_final_psi 1). C8.bc_t_e is
  carried (D336).
- **No reference changes.** No rerun row's key carries a B_out token, so no reference is regenerated.
- **C7's tolerance:** |F_declared − N_A·e|/(N_A·e) + 16·2⁻⁵³, evaluated exactly as 3.4307699621628870747e-11.
- **C6's B_out** is 1e-5 mM: the largest power of ten below 2¹⁹ fmol / (1e8 × 65.45 pL) = 8.0e-5 mM. The largest
  charge-anchor term over the scan domain is then 81,100 fmol.
- **Cost:** about 3.5 core-hours, or 2.5 h of wall time in three gate-lane batches of under 45 minutes plus the
  table. A C8b retry would add about 4.4 core-hours, and the procedure asks the lead first.
- **The runner** is a new independent agent, working from a frozen snapshot of the tag.

**FR-30's Tag A is tagged `fr30-ekvitorin2016-tag-a-2026-11-24` at 9c53fd76** (branch fr30-next).
- **The exposure sweep finished** (pass 5). It searched text files only, and never the sealed folder.
- **The lead's two files are confirmed.** They name the 2016 paper only by name, identifier and status:
  - LEAD-NOTES.md: its filing, the user's decision, and the registration's progress;
  - MORNING-BRIEF-20261123.md: its name and PMC identifier.

  Both stay barred for the fitter.
- **The fourth choice is confirmed.** Part S judges every held-out G_ss, those at decay-list magnitudes included,
  and starts from at least two held-out G_ss entries. Part S is reported only; FR-30's verdict does not depend on
  it.
- **Not exercised by any test, as the record states:**
  - of_G0 amplitude scoring;
  - reference_step predictions;
  - a G_ss sampling time other than T;
  - the symmetric protocol's holding difference.
- **Next:**
  - the branch lands later, with its tier measurement folded onto main's record (D222);
  - the sealed extractor is a new agent, started when a slot frees.

**The user's decisions:**
- **GJ-N1's upper end runs on CPU 13, with its sibling 29 idle.** That is about 23 h, and another 45–73 h if its
  h/2 is needed. The user lends this one visualizer core while the viewer is on hold. The rest of the search stays on
  a gate lane under its lock; amendment 2 is tagged with its driver change.
- **FR-53 is logged, high:** a rounding allowance for global ledgers at every row, from D336's finding.
- **A refused removal.**
  - The safety check refused the FR-38 references agent's `rm -f out/*`, a glob after a `cd`. No one retried it.
  - The user gave permission to remove the four untracked smoke-test files by their explicit paths, and the lead did.
  - The regeneration then runs from a clean tree.

**SK2's timing is flagged provisional** (the Lean lane, 24 November).
- **Half-activation.** Two independent labs place rat SK2's half-activation near 0.7 µM Ca²⁺. That is close to the
  fit of 0.728 µM with `cells.species_regulated_availability`.
- **The bound.** Lean proves that, with a fixed closing rate, the 20–80% rise time is at most ln 4 times the washout
  time constant. Both compiled versions of the operator passed that check.
- **One study indicates otherwise.** Oliver et al. (Neuron, doi:10.1016/S0896-6273(00)81197-6) report a mean
  high-dose washout that implies a 48.1 ms ceiling, and about 80 ms at low calcium.
- **So reusing one closing rate across doses is provisional.** A rise and a washout measured on the same low-dose
  patch would settle it. One study is an indication, and no law's form changes on it.
- **The operator's docstring gains this scope line** at its next src landing, batched with other docstring-only
  updates.

## D338: corrections and additions to D336 and D337: the vector path refuses the composite only; D330's G6 and CPU cost; SK2's evidence stated exactly; FR-30's earlier extractor never opened the 2016 paper

2026-11-24, about 14:26 UTC.

**The vector path refuses the composite only** (amends D336's admission line).
- **Where things stood:**
  - main's scalar row checks already refused a GPU (D187), so that path needed no src change;
  - `run_vector_windowed` decides on the device alone and had no refusal.
- **What changes:** the vector path refuses `resolved_pump_composite@1`, under every field solver, on a GPU. That
  is the family D330 measured and failed.
- **Why not a blanket refusal.** A blanket refusal would break GPU uses that have evidence:
  - the calcium ensemble's ionic families;
  - `resolved_pump_tissue@1` and @3's batched GPU runs (9 and 10 November);
  - their GPU tests.
- **A logged follow-up, not started:** re-check those families' GPU evidence under D330's criteria, run-to-run
  determinism included.

**D330's closing evidence:**
- **G6 passes under the flag.** A fresh process and one loading the saved autotune file each reproduce the pair's 8
  windows by bytes. The flagged autotune dumps hold no results.
- **What D330 closes on:** G1 and G6 pass under the flag; G2 fails. G3–G5 and G7′ were not run; the flag's cost
  was measured in block 3′a.

**The CPU cost of GJ-N1's field search:**
- about 70–115 thread-hours in all;
- the upper end at h: 2.56 M steps, about 23 h on a whole core;
- its h/2, if it ends as a final bracket end: another 45–73 h;
- a base-step point: 1.3–2.3 h, or 2.8–4.6 h at h/2.

**Correction to D337: amendment 2 is not yet tagged.**
- It will be tagged with its driver change (`--upper-cpu`, `--lane-lock`, `--lane-after`).
- The upper end starts at launch on CPU 13. The lane part takes its lock from 20:00 UTC, so the bisection runs
  overnight rather than holding a lane for about 10 h of daytime gates.

**SK2's evidence, stated exactly** (refines D337, from the Lean lane's record at lean-paired-transport-mechanics,
41f3de69).
- **The steady response.**
  - Hirschberg et al. (1998, doi:10.1085/jgp.111.4.565) measured absolute open probability at four calcium doses in
    one inside-out patch from a Xenopus oocyte expressing rat SK2.
  - The Cells curve calibrated on those data gives half-activation at 0.728 µM.
  - Syme's independent, untreated rat SK2 dose response gives 0.700 µM.
- **The proved identity.** For a held input, the 20–80% rise time equals ln 4/(a + b). It is at most ln 4 times the
  zero-input washout time constant when the closing rate b is positive and shared.
- **The replay.** In a compiled held-dose world (a = b = 16/s), both versions of
  `cells.species_regulated_availability` bracket the exact 43.32 ms within 42.97–43.95 ms, on a 0.488 ms grid.
- **Two tests of carrying one closing rate across recordings disagree with it:**
  - Hirschberg's single-channel plateau and macropatch washout predict a 10.63 ms activation time constant, against
    4.1 ± 0.6 ms measured;
  - Oliver et al. (2000, doi:10.1016/S0896-6273(00)81197-6), with separate recombinant SK2, measured a 6.18 ±
    1.91 ms 20–80% rise and a 34.7 ± 6.5 ms washout at 10 µM Ca²⁺. Reusing that mean closing rate at 0.5 µM gives
    a ceiling of ln 4 × 34.7 = 48.1 ms, against a reported rise of about 80 ms.
- **Limits of the evidence.** The low-dose record has no reported uncertainty, no sample count and no paired washout,
  and the two groups' data come from separate preparations.
- **So reusing one closing rate across doses stays provisional,** as an indication, with no change of law. A rise and
  a washout measured on the same low-dose patch would settle it.

**FR-30: the earlier sealed extractor never opened the 2016 paper.**
- It ran on 23 November and filed four candidates. Its README lists Ek-Vitorín 2016 as candidate 4, "not opened",
  because the procedure stops at the first paper that qualifies: Revilla 1999.
- Its folder holds extractions for Shibayama 2006, Elenes 2001 and Revilla 1999 only.
- So Tag A's message ("tagged before the sealed extraction") and section 13.7's "no record shows anyone opening the
  paper" stand.
- At landing, the branch gains a dated pointer to D337 for the lead's two files and the fourth choice, with no
  criteria change.

**FR-47's inert-wall fix ran FR-47's registered worlds before their verdict,** for its before-and-after comparison.
- It printed statuses and booleans only, never a value.
- The folder (`/mnt/workspaces/Cells/fr47-inert-wall-20261124/`) is barred to FR-47's checker. Its brief will say
  so.

## D339: a reviewer's four points (FR-47's scorer gets a registered schedule supplement and a tightened acceptance; FR-52's premise is corrected; the GPU guard; the feature index); GJ-N1 amendment 2 and FR-38 v2's references are tagged

2026-11-24, about 14:46 UTC. The advisor reviewed the four points with the lead.

**FR-47's frozen scorer does not check the washes against the registered schedule.**
- **Confirmed by reading `fr47_judge.py` at the registration tag:**
  - `judge_d` takes each stop's kind from the run, and never compares stop times or the heat intervals' ends;
  - `judge_exact` indexes each replica's stops by the references' count, and ignores time, kind and any extra
    stop.

  The reviewer's three invented cases pass it: a relabelled withdrawal with its heat removed, both washes 10 s late,
  and an extra trailing wash in every replica.
- **The frozen scorer stays the official verdict, unchanged.** There is no erratum.
- **A schedule supplement is registered before any judged run.** It is
  `validation/assembly_lineages_v2/FR47_SCHEDULE_SUPPLEMENT.md`, tagged `fr47-schedule-supplement-2026-11-24`.
  It checks, exactly:
  - count, order, time and kind, for the references and for every saved run;
  - a heat at every scheduled withdrawal;
  - the heat intervals' ends.

  Before any saved run is read, its controls must behave: the three cases fail and an honest record passes.
- **The lead tightens D323:** FR-47 leaves development-only only if both the frozen verdict and the supplement pass.
  D323 named the verdict alone. The user is told.
- **FR-47's independent checker implements the supplement.** Its brief also bars the inert-wall fix's
  before-and-after folder (D338).

**FR-52: one event can move several units.**
- A channel carries integer stoichiometry over the unit states, and `integer_change` is products minus reactants.
  So the reader uses each event's declared change, E <- E·(n − d)/n. Restricting version 1 to single-unit events,
  by name, is the fallback.
- **An acceptance row:** two original units and one new; one event removes two, chosen uniformly. The expected
  survivors are 2/3 original and 1/3 new.
- **A mutant:** a reader assuming one unit per event gives a total of 2 against the engine's 1, and must fail the
  integrity check.
- **For the design note:** whether a channel may list the active state on both sides. If so, the stored change is
  net there.

**The GPU guard.**
- 478664a0 refuses the composite on a GPU in the vector path. It waits for lane B, with FR's set and the D148
  proofs.
- After it lands, its refusal row is rerun at main's head and recorded.
- Judged runs of the composite run on CPUs (D338, GJ-N1 amendment 2).

**The feature index is brought up to date:**
- FR-43: all three parts on main (D328);
- FR-46 and FR-48: landed at d702f13a;
- FR-49: parts H and L at 7d021548, with World L passing (D331); World B, C1, C2 and C4 are still to come.

**Tags:**
- **`gj-n1-amendment-2-2026-11-24` at 750076a7.**
  - The field runs on CPUs. The upper end runs on CPU 13 from launch; the base-step points, bisection and half steps
    run on lane A from 20:00 UTC.
  - One engine revision serves both geometries: the line's stage 1 and one line point are checked by bytes at the
    field's snapshot before launch.
- **`fr38-v2-references-2026-11-24` at 8bd81c7e** (generated at 55c52c4b from a clean tree).
  - Six files, 19,957,976 bytes in `out/`, byte-identical across PYTHONHASHSEED 0, 1 and 4242. The hashes are in
    `out/SHA256SUMS` at the tag.
  - The worst judged accuracy is 1.3e-16 of scale, against 1e-11. Every must-catch plant is at least 72 times its
    honest tolerance.
  - **The user's limit:** about 20 MB is the ceiling for any committed data set. This one is at it.

**The ledger limit, recorded here** because the builder's note sits in a scratch folder. Small E2 worlds at a loose
`atol_count` can fail their own ledger: its tolerance is 100·rtol·max(1, |Q| + |W| + events), with no atol term. The
fix is an atol term derived from the integrator's declared `atol_count`. It is a follow-up after Protocol D's
re-registration.

## D340: two parameter-transfer flags from the Lean lane (a bilayer footprint across temperature; Kir4.1's square-root potassium scaling across preparations)

2026-11-24, about 15:01 UTC. These come from the Lean lane's paired wet-lab records (candidate 8634e566, in its gate).
They concern carrying a parameter across conditions. No law's form changes.

**A bilayer's molecular footprint is declared for one temperature.**
- `cells.bilayer_geometry@1` takes each membrane species' area per molecule as a declaration, and the engine does
  not vary it with temperature.
- Two independent methods find fluid POPC expanding on warming:
  - scattering (Kučerka's group): 64.3 ± 1.3 to 67.3 ± 1.3 Å² over 30 to 50 °C, +4.7%;
  - solid-state NMR (Leftin's group): 60.4 ± 3.6 to 70.5 ± 4.2 Å² over 28 to 48 °C, +16.7%.
- The Lean lane's compiled replay shows that a fixed footprint hides that expansion completely.
- **So a world compared across temperatures declares the footprint measured at each temperature.** A common
  expansion coefficient is still open: the two methods disagree on its size.

**Kir4.1's square-root potassium scaling stays scoped to its preparation.**
- `inward_rectifier_linear_driving_force@1` scales as (c_o/K_ref)^(1/2), and its coefficients are the route's
  declaration (its docstring already says they must be sourced before a claim rests on them).
- **One preparation supports the exponent.** Tada's group (rat Kir4.1 in HEK293T, three patches per level) fitted
  0.51 over 15–153 mM.
- **Another departs from it.** Edvinsson's series (human Kir4.1) reaches about 19 pS at 40 mM, against 13.9 pS
  from a square root anchored at their 110 mM value of 23 pS.
- Figure precision, species and solutions limit what the difference shows. One dataset is an indication, so the law's
  form stays, and a calibration carries only within its preparation.

**Both scope lines** go into the laws' docstrings (`geometry.py`, `inward_rectifier_linear_driving_force.py`) in
the next docstring-only landing, with the regulated-availability one closing rate (D337, D338) and the charge-anchor
fix's citation of the Lean claim, merged at 29d69f1d.

## D341: FR-30's Ek-Vitorín 2016 benchmark is undetermined by structure for the filed PDF; the user files its Supporting Material, added by a tagged amendment; FR-54 is high priority

2026-11-24, about 15:16 UTC.

**The extraction of the filed PDF** (the sealed extractor, under Tag A):
- **The kinetic part is undetermined under any expression of the data.**
  - Fig. 2B shows one illustrative record pair, labelled jointly ±100 mV.
  - It carries the paper's own second-order exponential fits, with no amplitudes, dispersion or n.
  - No other wild-type time constant appears in the text or the seven figures.
  - So the decay list has at most one magnitude (S2, P6.1).
- **The steady part cannot be expressed in the layout as tagged (E9).**
  - Fig. 2C plots wild-type points individually: n = 3, with what n counts unstated, in 9 clusters per polarity
    against the Methods' 10-step grid.
  - Some markers share one abscissa (K3), or are hidden. Pairing them across polarities depends on digitizing
    resolution.
- **The lead's ruling (advisor concurring):**
  - §13.7 applies as tagged;
  - no rule for summarizing plotted points is written after the paper was opened. If the user wants one for Part S,
    it is a separately tagged amendment, drafted by someone other than the extractor.
- **The seal.** No `fit.json`, `held_out.json` or `protocol.json` was written, so there is no held-out digest.
  - The folder `/mnt/workspaces/Cells/fr30-ekvitorin2016-extraction/` is read-only, and its SHA256SUMS digest
    begins 066b20d2.
  - It holds a value-free structure record, the LOG, and the unfinished digitizer scripts, with their working state
    kept private.
- **Disclosed by the extractor:** it read D334, which summarizes the polarity check's conclusions, and D337 at the
  lead's direction, before sealing. The lead's brief had erred on that point, and on the training file's name.
  `docs/JUNCTION_GATE_POLARITY.md` stays unopened (E11).

**The user's decision: file the paper's Supporting Material.**
- Two files, identified by their PDF metadata only and unopened, are filed read-only at
  `ek-vitorin-2016/supporting-material/`:
  - `mmc1.pdf`: 6 pages, the Supporting Material, sha256 d36e5964…;
  - `mmc2.pdf`: 20 pages, the article with its Supporting Material, sha256 3ace545d….
- **§13.7 amendment 1 adds them as a source before anyone opens them.** It is Part 12, tagged
  `fr30-ekvitorin2016-amendment-1-2026-11-24` at b725c702.
  - The same extractor reads them under the unchanged rules.
  - If they give per-voltage τ_fast and τ_slow at two or more magnitudes, the extraction proceeds; otherwise the
    benchmark is undetermined for the paper with its Supporting Material.
- **The fitter, the predictor and the checker start only after a seal under amendment 1.**
- A third file the user added, Tanis et al. (2017) on CALHM channels, is not part of this benchmark. Its use waits
  for the user.

**FR-54** (passive neutral diffusion against the exact two-well solution, then a wash at a diffusion-connected node)
is **high priority, the user's decision.** It takes the next free builder after FR-50.

## D342: FR-30 stays undetermined with the Supporting Material, and stays development-only; FR-38 v2's roles are restored; a branch pushed by mistake is deleted after its landing

2026-11-24, about 15:23 UTC.

**FR-30: the Supporting Material doesn't decide it.** The extractor read it under §13.7 amendment 1.
- **mmc1** (6 pages) is almost all single-channel work. Its only wild-type macroscopic decay record (Fig. S1 C's
  inset) is under halothane, a treated arm (E1), and is not fitted (E2).
- **mmc2** (20 pages) is the article followed by mmc1. Its pages and images are identical to theirs.
- **So Part 12's condition is not met.** The benchmark is undetermined by structure, now for the paper with its
  Supporting Material.
- **The seal:** no data file was written, and no held-out digest exists. The new folder
  `/mnt/workspaces/Cells/fr30-ekvitorin2016-extraction-a1/` is read-only, and its SHA256SUMS digest begins 5f410db7.
  It stays barred like the first, since its scratch holds the paper's text and figures.
- **FR-30 stays development-only (D262).** As the user's choice of 24 November provides, the next step is a
  metadata-only search for another source. It is registered before anything is opened, and every paper the record
  names as exposed is excluded. It queues behind FR-50's builder for an agent slot.

**FR-38 v2's roles are restored.**
- The lead's brief gave one agent both the builder's and the judge's role. The protocol
  (`docs/FR38_SECOND_COMPARISON_PROTOCOL.md` §5) requires a different agent for each.
- **The builder's reader is retired unused and never tagged.** It was 9dc73d57, and history keeps it.
- **The builder continues as builder:** the worlds, and `engine_run.py`'s exports for families C and D.
- **A new judge, blind to the first comparison and to the builder's retired reader, writes its own reader and
  mapping.** It starts when a slot frees.

**A branch was pushed by mistake.**
- The OL6 builder pushed `fr47-inert-wall` to origin at 14:37 UTC. Its own delete was refused by the safety
  check, and nobody retried it.
- The branch holds only the inert-wall fix's commits, which passed the privacy scan.
- **The user's decision:** the lead deletes it once the fix has landed on main. If the deletion is refused, the user
  is told.

**FR-50's phase-1 builder has started.** Its judge comes first (D308), on the branch from FR-51's head.

## D343: the user's decision: FR-30 is parked, development-only, with one labelled diagnostic on Revilla's data; D342's metadata search is withdrawn

2026-11-24, about 15:30 UTC. The advisor reviewed FR-30's record with the lead; the decision is the user's.

**The record since FR-30's benchmark began: twelve papers, one qualified, and it failed.**
- **Undetermined by their data's structure:**
  - Lin 2003, Desplantez 2004, Moreno 2002 and Snipas 2020;
  - Sahu and Bera 2013;
  - Xu 2013, Lin 2010 and Ek-Vitorín 2018 (D291);
  - Shibayama 2006 and Elenes 2001;
  - Ek-Vitorín 2016, with its Supporting Material (D341, D342).
- **Revilla 1999 qualified, and failed** (D320: 4 of 6). Its ±80 mV windows overlap, so the fit missed (§13.7 W2), which
  says nothing against symmetry.
- **§13.7 W5:** "undetermined" means no test, and triggers nothing.

**Nothing depends on FR-30's law.** `junction_series_gates@1` is used only by the Revilla benchmark's scripts. GJ-N1
runs the single gate, pinned open. Under the single-study rule, a second paper passing would leave one pass and one
fail, and D262 would stand either way.

**The decision: FR-30 is parked.**
- **It stays development-only (D262).**
- **Its scope line:** two relaxation times at the cited voltages; the voltage dependence is unvalidated.
- **It reopens:**
  - when an experiment or a registered world needs the series-gate law beyond development; or
  - when a source with per-voltage τ_fast and τ_slow at two or more magnitudes, at both polarities, is in hand.

  The three papers still registered unopened in §13.4's order (Bukauskas 2001, Rackauskas 2007 and Moreno 1994) come
  first then. Wang 1992 and Lin, Xu and Veenstra 2014 are exposed.
- **Not done:** pooling across papers. Parameters fail to carry across preparations, as D338 and D340 record today
  for SK2, Kir4.1 and POPC, so a miss would say nothing about the law.

**One diagnostic, labelled and non-blind.**
- **What:** a joint fit of `junction_series_gates@1`, with one symmetric block, to all six of Revilla's voltages.
- **Who:** an agent that never fits FR-30 again.
- **What it reports:** whether one parameter set can sit inside every registered window, with each residual in
  window units. It decides nothing (W6), and changes no verdict and no law.
- **When:** it takes the next free small slot.

**Correction to D342.** D342 called a metadata-only search "the user's choice of 24 November". The user's answer then
only filed the Supporting Material. That search is withdrawn.

## D344: the user's rule for confirmed findings; four Lean wet-lab rows sorted by it; FR-30 reopened narrowly; FR-55 and FR-56 logged; FR-50's judge tagged

2026-11-24, about 15:48 UTC. The advisor reviewed this with the lead. The decisions are the user's.

**The user's rule.** "For Cells, if we have something confirmed that doesn't work the same in Cells, we should find
out why and fix." Confirmed means two or more independent wet-lab studies agree. One study stays an indication.
- Each confirmed row is read at the Lean lane's record (`lean/WET_LAB_EVIDENCE.md`), not from a handoff.
- **The test:** does Cells reproduce the confirmed part when run with that preparation's own inputs?
  - **Yes:** a comparison rule or a scope line.
  - **No, because the law cannot produce it:** a law-form gap, diagnosed and then fixed by a general FR.
  - **Not run:** running it is the first step.

**Four rows, read at the Lean tip d5a2c138:**
1. **Cx43, the decay at −100 mV.**
   - **What is confirmed:** two phases. Revilla's paired oocytes gave 417 ± 175 ms and 7.06 ± 1.28 s; Sahu and
     Bera's N2a pairs gave 70 ± 5 and 931 ± 54 ms. Both data sets are already in D343's table.
   - **What is not:** a shared magnitude. The time scales differ six- to eightfold across preparations.
   - **The rule fires.** The shipped single gate, `junction_voltage_relaxation@1`, has one relaxation by design.
2. **Mixed-ion reversal** (Hodgkin and Katz's intact squid axons; Ohki and Aono's six perfused axons).
   - **What is confirmed:** the direction. Raising K depolarizes.
   - **Cells reproduces the direction.** Its +12.63 mV against the measured +2.0 mV carried intact-axon permeability
     ratios to perfused axons, whose own ratios were never measured.
   - **A comparison rule:** quantitative comparisons use preparation-specific ratios.
3. **Receptor turnover** (Strack, ten muscles: 1.1 and 13.1 day half-lives; Stanley and Drachman: 18.7 h and 12.4
   days).
   - **What is confirmed:** a mixture of lifetimes, with a fast fraction of 13–20%.
   - **Cells can represent it.** `population_unit_turnover@1` declares one removal rate per population, so the fast
     and slow cohorts are two declared populations.
   - **Guidance, no engine change.**
4. **Proton reversal** (Kapus's macrophages and Morihata's microglia; Bertholet's mitoplasts and Cherny's alveolar
   cells).
   - **What is confirmed:** the Nernst direction.
   - **Cells reproduces it.** At large gradients the nominal pipette and bath pH overstate the magnitude.
   - **A comparison rule:** quantitative comparisons use the intracellular pH at the time of the current measurement.

**Earlier flags, re-sorted by the rule:**
- **SK2 (D338) fires.** Two separate groups' recordings each contradict carrying one closing rate across conditions,
  and the operator's closing rate cannot depend on the dose.
- **POPC (D340) partly fires.** Two methods confirm expansion on warming, and Cells shows it only through a footprint
  declared per temperature.
- **Kir4.1 (D340) does not fire.** It rests on one series.

**The user's decisions:**
- **FR-30 reopens narrowly** (amends D343).
  - `junction_series_gates@1` becomes usable for two phases at a declared voltage, calibrated per preparation.
  - The voltage dependence stays marked unvalidated, and the law's predicted third amplitude stays flagged as
    unmeasured.
  - The Revilla joint fit, labelled and non-blind, moves up as the first diagnosis step.
  - D262's development flag is narrowed to that scope by a design note and a gated landing, never by this entry alone.
- **FR-55, high:** an input-dependent closing rate for regulated availability (dose-dependent deactivation).
- **FR-56, normal:** a temperature-dependent molecular footprint with a declared, sourced expansion coefficient per
  lipid.
- **Lean is asked, through the user,** for every row of its 46 where two studies agree and the Cells replay does not.

**The comparison rules and guidance** go into the docstring-only batch, with D337's and D340's scope lines.

**FR-50's judge is tagged** `fr50-judge-2026-11-24` (3cec272b). Its builder reads the references' spec folder only
after that tag, by the user's permission. The read was refused once earlier, before the judge existed, and was not
retried.

**The Lean tip d5a2c138** contains 8634e566, 41f3de69, 0bb50d8b, cb961e34 and 73e7e9d7. One merge covers them once
its gate passes.

## D345: the user's decision: law IDs become hierarchical, keyed by interface, starting on 25 November in the morning

2026-11-24, about 16:18 UTC.

**Today's IDs.** Law IDs are `namespace.name@major`, and 185 of 187 registered IDs are bare, in `cells`. The
families exist as folders and as interfaces, but not in the key.

**The decision: Option 1.** The key carries the law's family, read as its interface:
`cells.<interface>.<name>@major`, for example `cells.channel.inward_rectifier_linear_driving_force@1`. Folders mirror
interfaces. Outside modules take the same shape in their own namespace.

**Rejected:**
- family as metadata only, which leaves the key flat;
- a family prefix inside a flat name.

**The conditions:**
- **Timing:** it starts on the morning of 25 November, after tonight's runs and this round of landings, so it never
  collides with the branches in flight.
- **One mechanical, scripted move,** as D188's source moves were, with a committed old→new mapping table. Past
  decision entries and Lean's claims stay readable through the table, and old tags and snapshots keep their names.
- **No aliases.** An old ID is refused at parse, and the refusal names its new ID.
- **Codes and majors are unchanged.**

**Open until the morning:**
- the scope: laws only, or models, operators and kinds too;
- the advisor's review of identity stability across the module system and the Lean lane.

## D346: the user's decisions on the ID rename's scope and on legacy (amends D345)

2026-11-24, about 16:35 UTC. The advisor reviewed the plan with the lead. The decisions are the user's.

**The scope is everything live.** Laws, models, operators, kinds, solvers, the heat choice and execution mappings all
take `cells.<family>.<name>@major`, from a short closed list of families:
- model, operator, kind, solver, heat and execution;
- one family per law interface: channel, route, reaction, cycle, junction, exchange, rate_factor and free_energy.

Interface IDs (`cells.route_law@1` and the like) and schema IDs (`cells.declarations@2`) keep their names.

**No compatibility beyond this repository.** The user's private experiments run no legacy model, and the user renames
them.

**Legacy (`src/cells/legacy`, 321 files and about 75,600 lines; 195 of 888 test files import it):**
- **The parts used by neither BETSE nor the calcium ensemble are deleted,** together with the tests and drivers that
  depend only on them. The exact removal list is prepared read-only tonight, for the user's OK tomorrow.
- **The legacy-based BETSE comparisons (39 drivers) and the calcium ensemble families, with their GPU tests, are
  ported to the modern models first.** Their legacy remainder goes after the ports.
- **The one live law that imports legacy, `kinetic_pump_binding.py`, is ported.**
- **Main is tagged before any deletion,** as the BETSE-native removal was.
- **Until legacy is gone,** its remaining IDs stay bare and frozen, and old live IDs are refused by a table that names
  their new keys.

**The scale priorities:**
- **Catalogue size:** the rename.
- **Gate throughput:** about an hour locked per gate on two lanes. The time the deletion saves is measured.

**The order, from 25 November:**
1. Land what is gated.
2. Tag main.
3. Delete legacy's unused part, with its own gate, a removal list (D224) and re-measured tiers.
4. Run the rename's three read-only checks: IDs feeding numbers, the registry-built list, and the parse sites. Then
   generate the mapping from the registries, with a collision report.
5. The rename, with its own gate.
6. Re-merge the branches in flight.

The BETSE and ensemble ports are a separate, multi-day work item.

**Never rewritten by the rename script:**
- tagged specs, references, judges and their errata still in the tree (FR-50's `judge.py`, `REGISTRATION.md`,
  `JUDGE_ERRATUM_1.md` and `references/` among them);
- the crossrev replication record;
- `lean/`;
- past decision entries.

The Lean lane gets the mapping table, through the user, before the landing.

## D347: FR-43 checked item by item against its request: what is judged, what only tested, and four gaps

2026-11-24, about 16:58 UTC. This is the lead's read-only check, with the advisor. Evidence counts only as a test body
or a verdict file at main.
- **The two texts.** The user's paste of 24 November differs from the request saved on 23 November only in part 1's
  first lines, which now note that part 1 raised the limit to 1,024. Every acceptance clause is unchanged.
- **Judged by a registered criterion:**
  - C2.3, C2.6, C2.7 and C2.8 (D324). C2.7, the work of changing volume, was judged by convergence order (ratios
    near 4), consistent with water's second-order bookings.
  - C3.3, C3.4 and C3.5 (D319).
- **Covered by the builder's tests only:**
  - C1.1 at 32 and 1,024 rows, with C1.2 and C1.3 (`test_species_cap_runs.py`, `test_species_cap_large.py`);
  - part 2's two baseline refusals, now admitted;
  - C2.2, C2.4 and C2.5;
  - C3.1 and C3.2;
  - C3.6, the same-seed restart (`test_integer_unit_population.py`), which settles FR-52's restart premise.
- **No FR-43 evidence test imports `legacy/`.**
- **The gaps:**
  1. **Part 1's 16-row control and 256-row case** have no test at main: they ran only in the design phase.
  2. **Part 1's performance report** (compile time, time per simulated second, peak memory, device and precision,
     C1.4) lives only in the design note. Its L4 numbers were taken on a path D336 now refuses: the composite on a
     GPU.
  3. **Part 1 has no registered criterion at all,** only the builder's tests.
  4. **Turnover in a swelling cell** (D301's queue, A1) is still refused at parse ("reads volume as declared"), as
     D334 logged.
- **Any fix waits for the user:** a row in an existing test, or an FR. Nothing is built from this check.

## D348: the user's decision: port legacy's used families first, then delete legacy whole (amends D346)

2026-11-24, about 17:03 UTC.

**The removal list** (read-only; `/mnt/workspaces/Cells/legacy-removal-20261124/`) traced imports and legacy model
IDs together.
- **What is used:**
  - BETSE's legacy-based comparisons use 5 legacy model IDs.
  - The calcium ensemble's tests and drivers exercise 6: `assembly_regulated_cell@1`, `assembly_regulated_cluster@1`
    and `spatial_calcium@1` to `@4`. Its adapter table, `ensemble/ionic.py`, lists 98.
- **What keeping those 11 would mean:**
  - 133 of legacy's 321 modules stay;
  - 187 modules could go now, but 180 files outside legacy use both the kept and the deletable parts. 101 of them
    are unit tests, mostly through shared fixtures and legacy's core.

**The decision: no partial deletion.**
- A builder ports the 11 legacy families that BETSE and the calcium ensemble use to the modern models.
- Then legacy is deleted whole, with one gate. The 195 test files go with it.
- The ID rename of live code goes ahead from the morning of 25 November, with legacy's IDs bare and frozen until the
  deletion.
- **The parity rule holds throughout:** BETSE stays an outside reference, and nothing named BETSE enters `src/`.

**A correction to D346:** `kinetic_pump_binding.py` does not import legacy. It only names its origin in a docstring,
so there is nothing to port there.

## D349: an umbrella request on shared finite pools, checked: covered, apart from one restart row and a per-solver view

2026-11-24, about 17:05 UTC. The user's request on operators that share a finite pool maps onto existing work, checked
read-only at main:
- FR-43 part 2 (judged, D324);
- the gene unit beside the unit producer (`test_shared_inventory_unit_writers.py`);
- FR-38, FR-42, FR-33, FR-34 and FR-44 for tracking;
- regulated availability and FR-51 for availability;
- the wash against the bath schedule (FR-27, FR-10);
- the generated composition table.

Its acceptance check (stock identity, the sink off, the source off) is C2.2 and C2.4. Three points were checked
separately:
1. **Material already in production at the start is covered, as a bound.**
   - The gene unit's production bound caps release at κ times the pool's machines, whatever is already in
     production, since occupied chains never exceed the machines.
   - The unit producer takes it times the horizon once, and counts its own units in transit at the start
     separately.
   - No exact "total available over an interval" readout exists. None is built until a target needs one.
2. **A restart exactly at a production source's switch-off is a gap.**
   - Restarts at a change are tested for cell-owned compartments, in process and through a snapshot, and for the
     surface-repair pulse's end. FR-44's resume through a wash plants a redo and a skip.
   - **Queued:** one row in the existing shared-inventory test, cut exactly at the switch, compared bitwise with the
     uninterrupted run, with a planted redo and a planted skip of the switch caught.
3. **Support per solver is partly listed.**
   - The generated composition table lists each solver refusal as its own row, with source and test.
   - There is no operator × solver view, and the species cap (1,024) is global.
   - **Queued:** a per-solver view, generated from the existing refusal rows, with no engine change. It belongs to the
     catalogue work of 25 November.

## D350: FR-30's symmetric law stands; no FR-51 registration against V − E_K yet; an external review's findings (an FR-47 supplement erratum, the rename's design inputs, follow-ups)

2026-11-24, about 17:21 UTC. These are the lead's decisions with the advisor, under the user's delegation ("decide on the
two questions with adviser").

**1. FR-30: D334 stands, and `junction_series_gates@1` keeps one symmetric block.**
- **The diagnostic's first deliverable** (non-blind, deciding nothing) found G_ss/G_0's ±60 mV windows disjoint in
  Revilla's data: a gap of 0.052, which is robust. At ±100 the gap is 0.0016, which is marginal. The +V windows sit on
  the registered 0.05 floor, since 2·SEM is smaller there (n = 6 pairs).
- **It is confounded.** Revilla steps one cell from a common holding level (`protocol.json`; `JUNCTION_GATE_POLARITY.md`),
  so under §13.7 W3's reading the difference is confounded by that cell's V_m, neither a pass nor a fail. It is one
  study.
- **D334 was made with it in view:** the polarity note at Tag A already weighed Revilla's oocyte asymmetry, which
  prompted that check.
- **Corrections:**
  - D320 had 4 of 6 comparisons passing and 2 missing, both at −80 mV (τ_slow and G_ss). It failed on the 75% rule.
  - D343's "says nothing against symmetry" holds for those two judged ±80 lines only.
  - D344's narrow scope names a signed V_j and the stepped cell, since −100 and +100 differ.
- **The second deliverable is running.** It asks whether parameter sets compatible with the training data can reach
  the −80 τ_slow window.

**2. FR-51 against V − E_K: no registration now.**
- Two independent fits put Kir2.1's steep spermine valence above 4. "About 5" is less firm: 5.33–5.37 derives from one
  fit's e-fold, which has no stated uncertainty.
- FR-51's law admits a declared effective valence above |z_B| (ruling 7), and its test rows use values up to 9, so it
  is representable by declaration.
- The testable content is block against V − E_K at a second K level in one preparation, and no such source is in hand.
- **Next:** FR-51's entry gets a dated status line once it lands, and Lean is asked, through the user, for a two-K,
  same-preparation row.
- Cells' Kir2.1 law is a parity law with its own rectifying gates. A block on top could double-count, which is a later
  design question.

**3. An external code review, read-only over main and the active branches, checked and triaged:**
- **FR-47's schedule supplement has two defects, both confirmed in the code:**
  - `d.stops` carries no `kind`;
  - check 4 would confirm itself.

  Erratum 1 is registered before any judged run: `validation/assembly_lineages_v2/FR47_SCHEDULE_SUPPLEMENT_ERRATUM_1.md`,
  tagged `fr47-schedule-supplement-erratum-1-2026-11-24`.
- **The rename's design inputs, settled in the design note on 25 November before any script runs:**
  - **Five live interfaces are missing from D346's family list:** `cells.binding_law@1`, `cells.assembly_geometry@1`,
    `cells.population_structure@1`, `cells.assembly_hazard@1` and `cells.assembly_representation@1`. Whether
    `cells.lineage_operator@1` and `cells.assembly_operator@1` share `cells.operator.*` is also open.
  - **A folder does not always match its interface.** `rapid_binding@1` sits under `laws/reactions` but implements
    `cells.binding_law@1`.
  - **FR-51's `open_channel_block_weighted_modes@1` has no Law record or model-table home.** A mapping built from the
    registries would miss it. It gets registered on the slot-refusal follow-up branch, never on e4bbf0ec.
  - **The ID grammar.** `laws._ID` admits one dot, and `kind_registry.qualified()` would read `<family>.<name>@major`
    as an outside namespace. `registry/declarations.py` splits on the first dot.
  - **A name collision.** The declarations manifest already uses a field named `family` for the host model family,
    and the viewer reads it, so the ID segment's word and that field must not collide.
  - **Judged runs and Lean.** A judged run not finished before the rename runs from a pre-rename snapshot. Lean's
    check drivers need the mapping table before their next gate merge.
- **Follow-ups:**
  - **Before gating FR-50,** it merges the slot refusal (fr51-slot-refusal) or main after that lands, so
    `block_slot_errors` is not dropped.
  - **FR-44's two new wash records** join every washed world's state. Any frozen checkpoint of a washed world needs
    renewing, which goes in FR-44's landing text.
  - **The charge-anchor budget** is exact for valences 0, ±1, ±2, ±4 and ±8. Builders summing ±3, ±5, ±6 or ±7 terms
    rationally may add half a spacing per term. That check is queued.
  - **Two untracked files** in the main checkout's `lean/claims/incoming/` belong to the Lean lane. The lead leaves
    them, and the user asks that lane to file them.

## D351: the wet-lab gap diagnosis: three rows confirmed, none wrong inside its claimed domain; FR-55 goes to normal (the user)

2026-11-24, about 17:29 UTC.

**What was done.** A read-only diagnosis of the Lean register's eight "law misses" rows at af4a8000, plus the vacuolar
pump. It used one definition: confirmed means two independent labs measuring the same quantity on the same molecular
system under like conditions. The records are in `/mnt/workspaces/Cells/wetlab-gap-diagnosis-20261124/`. Every engine
revision Lean tested is on main.

**Confirmed:**
- **Kv1.5's acid shift**, in direction. Three labs agree in sign: +11.7, +17.3 and +7.8 mV, so the size differs.
  `kv1p5_mh@1` is a parity law with no pH input. A scope line, kept off the parity law's code; no target needs
  acidified worlds.
- **POPC's expansion on warming**, in the direction of the central estimates. Covered by D340 and FR-56.
- **Cx43's two decay phases**, in form. Covered by FR-30's narrowed reopening (D344, D350).

**Indications, not confirmed:**
- **Kv1.5's K–pH interaction:** different readouts. The same scope line.
- **DOPC rupture timing:** hold against ramp, different observables. FR-31's pore model covers it.
  - The registered worlds' fixed lysis thresholds are illustrative and claim nothing about DOPC: Protocol D's D4, D5, D6
    and D7, and OL5's references.
  - Recorded only.
- **SK2's closing rate.** The two labs contradict one fixed closing rate in opposite directions:
  - Hirschberg's rise is faster than one rate allows;
  - Oliver's low-dose rise is slower;
  - the one shared quantity agrees: the high-dose rise, 4.1 against 4.46 ms.

  A monotone input-dependent closing rate fits both only if the macropatch plateau is at least 0.93.
- **One permeability across voltage:** red-cell chloride and a valinomycin bilayer miss in opposite directions. A
  scope line on the constant-field law.
- **Kir in Na-poor solutions:** the same direction in two preparations, but the with-Na arm comes close to the square
  root (exponent about 0.40). So `inward_rectifier_linear_driving_force@1` is silent on external Na. A scope line, kept
  separate from D340's Kir4.1. No world runs it Na-free; XC0 uses it as Kir4.1, with sodium.
- **The vacuolar pump:** yeast and Arabidopsis, two organisms. FR-29 stays parked (D268).

**The verdict: no law is wrong inside its own claimed domain.** The confirmed gaps are a missing input (pH,
temperature) or a known one-gate design.

**The user's decision: FR-55 goes from high to normal.** D344 had read SK2 as firing. The plateau ≥ 0.93 condition, and
a same-patch rise and washout, go to FR-55's design note.

**FR-51 for the spermine target.** FR-51's law admits an effective valence up to 8, so the steep spermine component
(5.0–5.37) can be declared on an @3 population once FR-51 lands. Its qualification ran only the leak laws, so that use
is untested.

**The docstring batch gains three scope lines:**
- external Na on the Kir route law;
- one permeability across voltage on the constant-field law;
- pH on Kv1.5, on its library page rather than its parity code.

## D352: corrections and checks after D350 and D351; Lean's two-potassium rows for FR-51; FR-57's growing collector

2026-11-24, about 17:36 UTC. The lead's checks, with the advisor.

- **A correction to D350.** FR-51's test row with an effective valence of 9.0 is a refusal: "steepness above 8",
  refused as "exceeds 8". So no test exercises an admitted effective valence above |z_B|. One admitted row (spermine,
  z_B = +4, z_eff = 5) is queued on the slot-refusal follow-up branch, never on e4bbf0ec.
- **FR-44's resume** cuts exactly at the wash row: the checkpoint holds the state the wash acts on, and the resumed run's
  first step applies it, with planted redo and skip. That meets the request's "a checkpoint immediately before the
  event".
- **FR-50's pre-gate run:** one failure in 1,284, `test_library_pages.py`, because the generated library pages are
  stale after FR-50's new records. FR-51's snapshot passes the same test. FR-50 regenerates them with
  `scripts/library_pages.py --write` after each merge, as with the composition table.
- **FR-38 v2's smoke-3** passed, with nothing failed.
- **Lean's two-potassium rows for FR-51** (the user's relay):
  - **External K.** Panama and Lopatin measured Kir2.1 at four external K levels in one preparation. The steep block's
    midpoint moved 0.98 ± 0.01 mV per mV of measured reversal, over two patches. Ishihara and Yan give fixed-dose
    conductance curves at 150, 50 and 20 mM external K.
  - **Internal K.** Lopatin and Nichols report a slope of −0.15 when internal K changes, from one study.
  - **What this means for FR-51's law.** A block referenced to V − E moves exactly 1 mV per mV of E for both changes,
    and one referenced to V moves 0. So:
    - the external arm gives FR-51's reference real teeth;
    - the internal arm is an indication against V − E for internal changes, so the reference is supported for
      external changes only. That scope line also touches `inward_rectifier_linear_driving_force@1`, which reads
      u = V − E and runs in XC0.
  - **Main's Kir2.1** (`kir2p1_mh2@1`, a parity law) gates on absolute V, so it has no external-K shift. Once a second
    external slope is extracted (Ishihara and Yan's curves), the user's rule fires there, and the fix is a new law or
    major.
  - **Non-blind:** the lead has seen 0.98, so any comparison now is not blind.
  - **Registration is the user's call** after FR-51 lands. It needs both an external and an internal arm.
- **FR-57's growing collector** is appended to FR-57 and settles that open point: a tube at zero volume holds no trace,
  so the collector starts as a record. The case's numbers check: 1 fmol·ln(1/2) + 3 fmol·ln(3/2) = 0.523248 RT·fmol. The
  reversed order gives the same total with different per-portion losses.

## D353: the user's decisions: FR-63 (a pH-dependent Kv1.5 activation, normal) and FR-51's two-potassium registration after its landing

2026-11-24, about 17:40 UTC.
- **FR-63 is logged, normal.** D351 found Kv1.5's acid shift confirmed in direction by three labs, and `kv1p5_mh@1` is a
  parity law with no pH input. The fix is a new law: the parity law stays unchanged, for BETSE parity. The size of the
  shift is a declaration, since the labs differ.
- **FR-51's reference voltage gets a registration after FR-51 lands.** It has two arms:
  - **external:** Panama and Lopatin's slope of 0.98 ± 0.01 mV per mV of measured reversal; Ishihara and Yan's
    fixed-dose curves at 150, 50 and 20 mM;
  - **internal:** Lopatin and Nichols' −0.15.

  It is recorded as non-blind, since the lead has seen 0.98. The data come through Lean's rows, read at their commit
  before the registration is written.

## D354: FR-38 v2's amendment 3 is tagged; the user's decision: three uncovered readout controls go to a later registration; FR-47's wall-marker fix landed

2026-11-24, about 17:49 UTC.
- **FR-38 v2's amendment 3** is tagged `fr38-v2-amendment-3-2026-11-24` at 5859006b (branch fr38-registration). The
  protocol author wrote it:
  - **Family D's energy identity** is now a stepped entry with p = 2, passing if max|r_h| ≤ 3 est + e_round in C3's
    order window. Holding it to rounding was an error carried over from the fixed-volume worlds, and the amendment
    discloses it. The builder's invented-cell figures (order 2.003) were seen before the ruling. D is reported only,
    and no registered world has run.
  - **`release_check`'s narrowed scope** is as the spec intended. It is not a registered criterion: the gross against
    net discrimination rests on C2 with plants P1, P1′ and P1″.
  - **The four readout controls,** from a user's note:
    - (b), survival by detachment, is covered and judged in arms A and B;
    - (a), producers reordered and replaced, is not covered (D334). D306's checker holds development evidence;
    - (c): the degradation is covered, but the same molecule leaving and returning through export is not;
    - (d): zero loss, two loss routes on one row, and a constant-stock control are not covered. The resolution limit is
      covered in host form.
- **The user's decision:** the three uncovered controls, (a), (c) and (d), go to a later registration (FR-38 v3) with
  its own verdict. v2 stays as registered, so its judge and judged run are not delayed.
- **FR-47's wall-marker fix landed** at 9d8c42be (tag `fr47-inert-wall-landed-2026-11-24`): gate G1 113 of 113, and
  the D148 proofs identical but for provenance. The origin branch `fr47-inert-wall`, pushed by mistake, is deleted, as
  the user approved in D342.

## D355: Lean's two-potassium evidence for FR-51: the external arm meets D351 in direction and rough size; FR-51's reversal reference answers it; the internal arm and chloride are indications

2026-11-24, about 18:07 UTC. The lead, with the advisor, on Lean's results relayed by the user.

**What arrived.** Lean's results are at Lean commit fccbb5e5 (branch lean-paired-replay-audit-20261124), with its
readings and drivers at 59fe4896. They are non-blind exploratory results for the registration after FR-51's landing
(D353).
- **The engine:** FR-51's follow-up at 7ca7c9c1 (branch fr51-slot-refusal), not e4bbf0ec, with
  `resolved_pump_tissue@3`, `kir2p1_mh2@1` and `open_channel_block_weighted_modes@1`.
- **What ran is FR-51's block factor, not Kir2.1.** Lean divides a blocked population's current by a matched free
  population's, with their Kir gates held equal. "Absolute voltage" below is FR-51's block on the membrane-voltage
  reference.

**The external arm.** The half-conductance shift against the measured reversal shift, with each preparation's
two-mode block fitted to its first K level and then held fixed:

| Series, external K (mM) | Half-conductance shift (mV) | Measured reversal shift (mV) | Cells, from concentrations (mV) | RMS: reversal reference | RMS: membrane voltage | RMS: measured shift (diagnostic) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Panama, 5.4 → 60 | +51.6 | +53.2 | +62.3 | 0.226 | 0.397 | 0.044 |
| Ishihara, 150 → 50 | −26.1 | −26.9 | −28.2 | 0.026 | 0.479 | 0.010 |
| Ishihara, 150 → 20 | −48.1 | −48.9 | −51.7 | 0.043 | 0.533 | 0.015 |

- **The definition is met in direction and rough size only.** The independent pair is Panama against Ishihara.
  Ishihara's two rows share one 150 mM calibration. On Lean's half-conductance reading the slopes are 0.97 (Panama),
  and 0.97 and 0.98 (Ishihara). The exact slope stays open, since readings are good to about 1 mV and some half
  crossings sit in 10 mV brackets.
- **A correction to D352 and D353:** Panama's 0.98 ± 0.01, which they quote, is a fitted steep component, a different
  observable. The pair is on the half-conductance reading.
- **The user's rule (D344) is answered by FR-51's `{"reversal_of": ion}` reference,** which is in flight. D352's "a
  new law or major" for main's Kir2.1 is withdrawn: FR-51's block law is that new law. `kir2p1_mh2@1` stays unchanged,
  as a parity law, with a scope line on its library page:
  - its own gates read absolute voltage, so they do not shift with external K;
  - a world in which external K changes declares FR-51's block with a reversal reference.
- **Concentration-based against measured reversal: no cause is assigned.**
  - Cells' shift is larger in all three series, by 9.1, 1.3 and 2.8 mV, and only Panama's difference is large.
  - Panama's zero crossings and curves come from different panels, with unspecified specimen linkage.
  - The measured-shift arm is a clamp offset in Lean's driver: one lab's indication, and no request.

**The internal arm is an indication.** It comes from one lab (Lopatin and Nichols), with one to three patches per K
level.
- Raising internal K from 150 to 625 mM moved the half-block voltage about +5 mV, from about −20 to −15.
- FR-51 predicts −36.3 mV with the reversal reference and 0 with the membrane-voltage reference.
- The full series' slope is −0.15.

D352's scope line stands, now with numbers: the reversal reference is supported for external-K changes only. One study
adds no reference option.

**Red-cell chloride is recorded only.** One permeability fits both of Freedman and Novak's mean currents only with an
intracellular to extracellular chloride ratio of 0.187, against a measured initial 0.67 ± 0.02. Intracellular chloride
was not measured at each test voltage, so D351's scope finding stands.

**Where the scope lines go:**
- FR-51's landing message, which the lead writes;
- the block law's docstring on `fr51-slot-refusal`, never on e4bbf0ec, which is in its gate.

They cite Lean by commit (fccbb5e5), since Lean's files are not on main.

**Lean's tip fccbb5e5 merges only when both hold:**
- the slot-refusal branch has landed by merge with 7ca7c9c1 in its history (its builder adds commits, and never
  rebases or squashes);
- a gate has run on fccbb5e5 itself, since the branch has moved past 59fe4896.

**For the registration (after FR-51 lands, D353), before any run:**
- **Judged quantities.** Fix which slope and which reversal are judged. The lead's proposal: judge the
  concentration-based reversal, and report the measured one.
- **Panama's other K levels.** Panama recorded four K levels, and Lean scored one pair. The lead asks Lean, through
  the user, whether the other levels are unscored. Until then `kir_spermine_potassium.json` stays unopened, since those
  levels could be the one arm still blind.

## D356: Kir2.1 is a composition, not a law; the user's decision: one declared voltage shift on the channel population (FR-64), with FR-63 re-formed; Panama's 10 and 20 mM become holdouts

2026-11-24, about 18:19 UTC.

**Kir2.1 (the lead with the advisor, at the user's request for the cleanest form).** There is no Kir2.1 law. Kir2.1
is an always-open K population (`kleak_always_open@1`) carrying FR-51's block on a K reversal reference.
- **Why no law.** The two labs confirm the block's shift (D355), each with its own fitted modes. A Kir2.1 law would
  freeze one lab's fit. The confirmed part is the form, and FR-51's reference gives it to any channel population.
- **The block stays off `kir2p1_mh2@1`.**
  - Its m target falls with depolarisation at absolute voltage, so stacking the block on it would rectify twice, and
    the gate half could not shift.
  - Lean's ratio cancelled the gates, and no gates on V − E have evidence here.
- **FR-51's registration already runs this pairing:** `validation/fr51/REGISTRATION.md` names the always-open hosts,
  and its references' cases use them. D353's registration judges the composition itself. Until it passes, both
  library pages (`kir2p1_mh2@1`'s and the block law's) call the composition development-only.
- **What the pages say is not claimed:**
  - the unblocked current's shape and size against external K, which Lean leaves open;
  - internal K, an indication (D355);
  - the block's own limits in version 1: the blocker is held at a declared constant concentration rather than a
    species row; the block has no kinetics; and binding is trace, with no count.
- **No values tonight.** The fitted modes stay in Lean's driver and JSON, unopened.

**The user's decision: one general mechanism, logged as FR-64.** FR-51's reversal reference and FR-63's pH shift have
one shape: the voltage a factor reads, shifted by a declared function of a local activity. It becomes one mechanism,
declared on the channel population:
- **The shifts are a small closed set:** an ion's reversal, V − E from its compartment concentrations, and a sourced
  shift per pH unit.
- **Who reads it:** the factors that declare it, the gates and the block.
- **Parity laws are untouched.** A population that declares no shift runs bit for bit as now.
- **FR-63** becomes a declared pH shift on Kv1.5's population, instead of a new law.
- **FR-51** lands as is. Its block's `reference` key then moves into the mechanism, with no aliases (pre-alpha).
- **A design note comes first,** before FR-51's block law is registered and before the rename's design note
  (25 November).
- **Where it sits today** (the lead's read of `fr51-slot-refusal`):
  - `channel_block` in `surface_pump_v3.py` computes V − E per population, for the block only;
  - `channel_kinetics` hands the gating laws the plain membrane voltage;
  - the block law, `open_channel_block.py`, already takes any reference voltage.

  So the change is in the model's plumbing, not in any law.

**Lean's answer on Panama's other levels** (relayed by the user):
- **What Lean scored.** Its frozen replay fitted Panama at 5.4 mM and scored only 60 mM. Panama's 10 and 20 mM
  normalized-current curves and half-conductance shifts are unscored; the 20 mM row in D355's table is Ishihara's. Lean
  verified this from the saved run output and left the input data file unopened.
- **The registration** (after FR-51 lands, D353) reserves both levels as within-study holdouts. The 5.4 mM fit, the
  readout and the scoring rule are frozen before the two levels are extracted.
- **Prior exposure, disclosed.** Lean's search saw the full figure, including the intermediate traces, and had read
  their reversal voltages and the published four-level fit. By its recall it extracted normalized currents only at the
  endpoints. So the registration can claim a prospective test of the two intermediate responses, with that exposure
  disclosed.
- **The lead** keeps `kir_spermine_potassium.json` unopened.

## D357: OL6 Protocol D v2 is registered; the judged revision is pinned at eced4ef8

2026-11-24, about 18:29 UTC. The lead, with the advisor.

**The tag.** `ol6-protocol-d-v2-registered-2026-11-24` is at eced4ef8 (branch `ol6-protocol-d-v2`).
- **The judged revision is eced4ef8.** Its src is main 9d8c42be's, FR-47's inert-wall landing. The branch merged main
  once, at 0087818d, and never again: main now carries FR-44's src.
- **The authority** is `docs/OL6_PROTOCOL_D_V2.md`, with `protocol_d_v2.py` and `protocol_d_v2.json`. The files it
  judges with are unchanged since their own tags.
- **Checks at eced4ef8:**
  - `protocol_d_v2 check`: 29 of 29;
  - the JSON regenerates byte for byte;
  - the guard set: 87 passed;
  - the privacy scan of the branch's diff: clean.

**Rulings on the builder's four calls:**
- **The pin** goes in this entry, as the document says. 0087818d predates the last text commits.
- **`moments` stays.** Without it, identical replicas would miss the zero-SE rule in 14 of the 54 constants. A pair
  wrongly classed as spread would then read the same artifact that failed the first registration (D318).
  - A check row shows that `moments` equals the registered `mean_error` bit for bit on columns whose replicas are not
    all identical.
- **A missing row keeps failing (§6).** An exact run that loses a vesicle that (d) keeps floppy is a real
  disagreement. Counting it as tense would make it unfailable.
- **Erratum 2's frozen module stays as it is.** One docstring line ("P-D1's (d) side, in place of the refused (d) run")
  names a plant outcome of the first check. §7 already states that P-D1's (d) side is computed from the closed form and
  never run. The tag message discloses the line, and the checker lists it.

**Seeds:**
- **First:** 670001 to 670000 + M.
- **Retry:** 690001 to 690000 + M, once, and for inconclusive worlds only.
- **D7's clock convergence** reads the first six seeds of the set it checks.
- **Withdrawn:**
  - 640001 onwards: its first 128 were consumed by a (d)-only clock-room probe; the retry range was never run;
  - 740001 onwards: never run.

**P-D8, the one-ulp plant,** moves a read value; it is not an engine run. This records its limit: moving N_L by 1 to
16 ulps leaves V's bits unchanged, so these constant pairs cannot see a small lumen-count error.

**Two routes to inconclusive** (a correction to the lead's "about 1 in 10²⁰" to the user, which covered the first
only):
- **A tense replica:** about 1.8e-20 at the worst rung M reads, from the linear-noise variance, which was checked
  against 128 exact replicas of an unregistered 12.5 nm D5.
- **A D7 clock refusal on the new seeds,** which are unscreened by design. It has no number. On the withdrawn seeds
  the worst case used 0.39 of the bound.

**Cost:** about 13.5 process-hours for the first seed set, with D5 at 6 hours and its 100 nm rung at 4.5 hours in one
chain. With a retry, at most about 27.

**The checker** is fresh and independent: neither the builder nor the first checker. It is briefed with the tag, the
document and §10, and with its CPUs. It reports before any retry.

## D358: the user's decision on gate speed: refresh the scope map after engine landings, record the 37 unmapped files, and narrow D229's readers rule after a file-open check

2026-11-24, about 18:32 UTC. The user: "think practically about testing as much as we can try to be optimized without
sacrificing quality". The lead measured, with the advisor.

**What a gate with no src change runs today.** The gate for the Lean calibration tip, whose diff is 52 files, all under
`lean/`, selected 561 of 666 tier files: 12,633 of 13,307 test-seconds, and 2,354 s of wall time on lane A. Two terms
dominate:
- **Drift: 442 files.** `scope.py select` compares each test's recorded paths with the nightly map's snapshot (03:09),
  so every test that touches src changed by the day's landings is re-run by every later gate, whatever the gate's own
  change.
- **D229's always-run readers: 469 files.** Every test that reads repository files always runs.

The same estimate for two other diffs, with the drift term removed:

| Always-run rule | Lean tip (52 files) | D356 (two docs files) | Protocol D v2 (three files) |
| --- | --- | --- | --- |
| Recorded reads only | 49 files, 735 s | 50 files, 794 s | 51 files, 815 s |
| Folder scanners | 295 files, 7,824 s | 296 files, 7,930 s | 296 files, 7,930 s |
| Readers (D229) | 479 files, 10,496 s | 480 files, 10,602 s | 480 files, 10,602 s |

- **The floor.** In every variant, 37 files run because their child processes are not recorded, and a few because they
  are missing from the map.
- **No tier test reads `lean/`.**
- **Tracing is nearly free.** The traced nightly ran 662 files in 2,301 s of wall time.

**Why not simply select from the landing's own diff.** That would change what a gate certifies. Main also changes
without a gate:
- the lead's decision commits, which pass only the privacy scan;
- the merged state after each `land.sh`, whose trial runs only the named test files.

FR-50's stale library pages are that class of failure. So main's drift stays tested, once rather than in every gate.

**The user's decision: build all three tomorrow.** Each is qualified before use, and the full nightly run stays the
backstop: a nightly failure still stops selection until it is explained.
1. **Refresh the map after each engine landing,** with one traced full run on main. Later gates then select against a
   map of the current main. No rule changes, and no coverage is lost.
2. **Record the 37 files whose children are unmapped,** so they run only when their inputs change.
3. **Narrow D229's always-run readers rule,** amending D229 rule 3. Tests that read repository files then run when the
   recorded files they read, or the folders they list, change.
   - The evidence comes first: a file-open trace (`strace -f -e trace=openat`) of a sample of reader files, compared
     with the map's paths. A repository path the map lacks is a hole, and it blocks the change.
   - The guard set still always runs.

**Tonight nothing changes** in `scripts/gates` or `gate-cache/scope-map.json`, because gates are queued.
- The queued Lean gates are Lean's, and the lead does not stop them.
- The user passes Lean the advice: one gate per merge point. 647b4c15 covers d5a2c138, 3a5f40d7 and af4a8000.
  fccbb5e5 is superseded by c1924c89, which cannot merge before FR-51's follow-up lands.

## D359: XC0 v2 (rule erratum 2) passes on its independent run; D329's fail stays on record

2026-11-24, about 19:57 UTC. The independent runner's report, under the tag `xc0-erratum-2-2026-11-24` (b477f433) and
D333's terms: only the diagnosed families rerun, on the same frozen engine, disclosed as not blind on those rows.

**The verdict: pass.** The judge (step 7, exit 0) gives every claim, C0 to C8, a pass. Its counts:

| Pass | Not mappable | Not run | Information |
| ---: | ---: | ---: | ---: |
| 7,430 | 272 | 242 | 736 |

- **The five changed families pass:** C6.v1_eq_ratio, C6.v1_eq_x, C7.pump_cell_charge_per_fmol, C8.b_final_c and
  C8.b_final_psi.
- **The rows:** all 349 rerun rows pass, and 8,331 are carried from D329.
- **Of 129 families,** 98 pass, 19 are information, 7 not mappable and 5 not run. None fails, none is not testable,
  and none lacks power.
- **The record** is `/mnt/workspaces/Cells/xenopus-lane-20261119/xc0-erratum2-run/`: `step7/judge.json`,
  `verdict/verdict.json` and `RUN.json`.

**The engine's identity:**
- **The tree:** the tag's src tree equals 260d7c7f's (tree 2c5a51cb).
- **The snapshot** is clean: 5,345 files at b477f433, with an empty patch, frozen with `--scope full --require-clean`.
- **The imports:** all 109 loaded cells and validation modules came from the snapshot.
- **The judge's checks** pass: the same engine as D329's snapshot, the base record's digest, and the carried judge
  record's digest.

**The runner's procedure:**
- **Coverage.** The key check and the carry check pass, and the changed manifest equals the builder's.
- **The charge anchor** bounds all 344 rows below 524,288 fmol.
- **The segments.** All six bare segments, at factors 1 and 0.5, end cleanly and pass the segment check.
- **The table** has 349 numeric rows, and every C8b step check converged. No retry was needed.
- **Refusals and errors:** none.
- **Cost:** about 3.78 core-hours, over the estimate of about 3.5. The wall time was about 5.5 h, of which about 2.5 h
  was spent waiting for lane locks.

**The runner's disclosures, recorded here; the sealed record is unchanged:**
- **Batches.** Two of three lane batches ran slightly over 45 minutes (45:55 and 45:16). The lane flock is not first
  in, first out, so a batch may have gone ahead of a waiting gate.
- **The launcher.** It used main's `scripts/run_detached.sh`, which is newer than the tag's and turns JAX's
  compilation cache off, adding `python -B`, `/usr/bin/time -v` and CPU pinning.
- **One small scratch file** went to `/tmp` against the brief, and was removed.
- **The sealed not_blind file is slightly inaccurate:**
  - it says lines 1530 to 2193 of `xc0_engine.py` were read, but lines 1930 to 1948 were not;
  - it omits that a grep of DECISIONS.md printed D332's title line.

**What it means.** XC0's registered comparison failed in v1 (D329). The diagnosed rows were rule-side definitions and
an engine parse tolerance, not physics (D332). They now pass in v2, on the same frozen engine. The engine fix of
D333, the charge anchor, landed separately (82c26ddd).

## D360: a correction to D352: admitted effective valences above |z_B| were already tested; FR-51's follow-up is gating

2026-11-24, about 20:06 UTC.

**The correction.** D352 said that no FR-51 test exercises an admitted effective valence above |z_B|. That was wrong:
the lead read only the refusal row at 9.0 ("exceeds 8").
- **B5** is D352's spermine case itself: z_B = +4, inside, z_eff = 5, on a K reversal reference. It is a host row
  compared with the 60-digit closed forms at 40 voltages.
- **B4** (1.5 on |z_B| = 1) and **G1, G3 and G5** (8 on |z_B| = 1) are admitted rows too.
- **The judged run covered them:** REGISTRATION.md's B-u cases include B4, B5 and G1 to G5.

**What the follow-up adds instead** (branch `fr51-slot-refusal`, head e79cbade, with 7ca7c9c1 kept in its history):
- **A plant** that caps each effective valence at |z_B|. It is a row in the existing plants test, and it must fail B5's
  B-u. It does: planted, the relative error is about 2.4e2 at +60 mV, while unplanted B5 sits at 0.4% of the 1e-12
  band.
- **B5's round trip:** it parses with steepness exactly −5.0, and round-trips through `to_dict`. That is the
  effective-valence form's first round trip.
- **The slot refusal:** a blocked population beside cell replacement @1 or @2, partition@1, or membrane insertion @1
  or @2 is refused by name at `Composition.check_definition`.
- **The block law's scope lines (D355, D356),** in its module docstring only. The law is not registered (D356).

**State.**
- **The gate** is on lane B and the FR set follows it (`/mnt/workspaces/Cells/fr51-slot-refusal-20261124/`).
- **Fifteen related files** matched their rows at the head, in 171 s.
- **The populations file's tier row** is 23.65 s, 61 passed, measured cold.

**Two notes for later:**
- The slot refusal has no entry yet in `composition_matrix.RULES`.
- `kir2p1_mh2@1` has no library page, so D355's and D356's page line waits for the docstring batch. A docstring edit
  would change a parity law's source.

## D361: FR-64's design note: the user's decisions (all four pairings admitted, two claimed; priority normal) and the lead's rulings

2026-11-24, about 20:22 UTC. The note is `docs/VOLTAGE_SHIFT_DESIGN.md` on branch `fr64-design` (6fb3b7bb). It contains
no engine code.

**The mechanism.**
- **The schema:** one optional key on the channel population, `voltage_shift: {"gates": {"m": shift}, "block":
  shift}`.
- **The rule:** each reader reads V_ref = V − ΔV. ΔV is an ion's reversal E, or σ(pH − pH_ref) at a declared side.
- **ΔV never depends on V.** So dV_ref/dV = 1, and the block's charge term keeps its form. Permeation, its heat and its
  charge still read V.
- **Where it is computed:** one function in @3, for every reader, at every stage and on every path. No law changes,
  and the declaration adds no new ID.

**The user's decisions:**
- **All four reader and kind pairings are admitted in version 1, and two are claimed:**
  - the claimed two are the block on an ion's reversal (D355) and the gates on pH (D351);
  - the qualification proves all four as engine arithmetic, including the block on pH's new material term through h
    and its bound;
  - the gates on reversal, and the block on pH, carry no wet-lab claim.
- **FR-64's priority is normal.**

**The lead's rulings, as the note recommends:**
- **Readers:** each gate and the block separately. A gate shift moves its target and τ together. τ's shift is
  unmeasured, since D351's records give the activation midpoint only.
- **The pH sign:** σ = dΔV/dpH in V per pH unit, negative for Kv1.5.
- **Sources:** carried by the world's registration.
- **The build** comes after FR-51's follow-up and the rename land.

**Moved to the rename's design note (25 November):** the block law's family (its ID is live but in no registry),
together with how tagged files that are never rewritten keep being read after a spelling changes. That covers FR-51's
engine translator and FR-50's exclusions. The pre-alpha rule argues against a shim.

**Before the pH window is ruled:** the note's example puts the reference pH on the window's edge, so a world resting at
its reference would be refused through drift or rounding. The note must state the rule at the edges.

**Coverage the note adds:**
- the slot writers' stale-slot hazard for any declared shift, not only a block;
- plants for the two gaps it found: an IMEX stage gate reading unshifted V, and a stored total read in place of free h
  at a buffered node;
- §9: the linear pH form interpolates each lab's two points, and only the direction is confirmed.

**Order:** D353's two-arm registration must not straddle the key move. It is written after the migration, or pinned
to FR-51's landed revision (955765ef). The note lands with the rename note as one stack with no src change.

## D362: FR-54 and FR-57's design note: one liquid router that takes over the wash; the user's decisions; a correction to D352's reversed-order line

2026-11-24, about 20:35 UTC. The note is `docs/LIQUID_ROUTING_DESIGN.md` on branch `fr54-57-design` (df9361a4). It
contains no engine code.

**The recommendation.** One new operator, `liquid_routing@1`, moves well-mixed liquid between inlets, finite nodes and
records, as portions at declared times (a wash is one case) or as prescribed flows.
- **A flow is stepped exactly,** by the matrix exponential of the declared network. It is computed once per schedule
  segment on the host, so the trajectory, the volume and every solute are exact to rounding.
- **Heat is booked per portion,** in the wash's ideal-mixing form, never as a remainder. Its split among holders is
  first order in the step.
- **The collector** starts from zero volume, and its first portion loses exactly 0.
- **The estimate** is 7.25 to 9 agent-days, plus 1 to 1.5 to retire the wash.

**The user's decisions:**
- **The router takes over the wash.** `scheduled_compartment_wash@1` is retired after a bitwise check, under the
  pre-alpha rule.
  - The retirement waits for FR-49's registered World B and C1 runs, or pins them to an earlier snapshot.
  - FR-45's worlds W2 and W7 also wash. Its protocol, not yet tagged, is written against the router or pinned the same
    way.
- **The collector is a record that can later open as a node** whose liquid keeps reacting. That adds 1 to 1.5
  agent-days now.

**The lead's rulings,** as the note recommends:
- **One operator for events and flows,** with flows by the exact network step.
- **Networks:** any balanced network of up to 64 nodes, qualified on a chain, a split and merge, and a loop.
- **Heat:** records outside the energy check's flow bound, like the wash's.
- **The default face heat** at a face-connected exchanged node is admitted for events within the resolved domain, and
  a flow's face-connected nodes take the exact heat only. The domain edge is the author's desk arithmetic, so it is
  measured before any tag, with the 8 and 2 fmol world confirmed inside.
- **Flow beside diffusion** comes in the same build, once FR-54's two arms pass.
- **One registered protocol,** with a verdict per request.
- **FR-54's item 3** is read plainly: the wash's events at a connected finite node, on the dt grid.

**Cautions for the build:**
- **The exponential's bits.** The host routine is pinned or its version recorded, since its bits set restart identity
  and crossrev.
- **Three readout classes:**
  - flow alone is exact, judged with a rounding bound, never an order window;
  - flow beside diffusion carries Strang's second order;
  - the heat's split is first order.
- **The references** need the repeated-eigenvalue closed form for a chain of identical wells. FR-57's 26.42% is that
  case.
- **The label owner's new field,** `label_collected_fmol`, is absent where there is no collector, or else FR-49's
  judge needs an erratum first, as today's erratum 1 did for one field.
- **The build comes after the rename,** so the operator's ID is minted once. The note lands in that no-src stack. Its
  author has read the engine, so a separate code-blind agent writes the references.

**A correction to D352 and FR-57's addition.** "The reversed order gives the same total, with different per-portion
losses" was wrong for two deliveries.
- **The first delivery** into the empty tube loses 0 in either order, so the second carries the whole 0.523248
  RT·fmol. Only the second delivery's split between resident and arriving liquid differs: 0.306853 and 0.216395
  forward, reversed in the other order.
- **A third delivery** makes the per-delivery losses differ, with the same total:
  - 1, 3 and 3 mM gives (0, 0.523248, 0.137341);
  - 3, 3 and 1 mM gives (0, 0, 0.660589).
- **The case's control** is that three-delivery form, with the two-delivery split recorded too. The line was the
  lead's, on the advisor's suggestion. The author's figures check by hand.

## D363: FR-50 phase 1's registered comparison passes (fr50-one-way-records-v1)

2026-11-24, about 20:35 UTC.

**The run.** At 4872266d, once, from a clean snapshot frozen before the run, on the timed lane (CPUs 4 and 5 under
its lock, siblings idle). It took 2 min 31 s of wall time.
- **The order:** the tagged reader's pre-flight read the results first, and all ten cases parsed, none invented. The
  judge ran after it.
- **The sources:** the tagged judge (3cec272b) with erratum 1 (a6e48ce9), and the code-blind references (5a59b3c5),
  taken with `git archive`.

**Every criterion passes:**

| Criterion | Measured | Band |
| --- | --- | --- |
| K1-1 | 8.4e-15 relative | 1e-11 |
| K1-2 | gap 0 | 1e-12 |
| K1-3 | closure 0 | rounding bound |
| K2-1 | order ratios 4.0021 and 4.0019 | 3.6–4.4 |
| K2-2 | gap 9.98e-7 at 0.1 s; ratio 4.000 | ≤ 1e-5; ratio 3–5 |
| K2-3 | closure 0.040 of its bound | ≤ 1 |
| K2-4 | restart at 100 s, bit for bit | bitwise |
| K3 | 2.3e-16 | 1e-12 |
| K4-1 | 5.7e-15 | 1e-11 |
| K4-2 | gap 0 | 1e-12 |
| K4-3 | closure 0.026 of its bound | ≤ 1 |
| K4h | 1.8e-16 | 1e-12 |
| K5 | the four refusal rows | all pass |

- **All five plants** are caught as registered.
- **The record** is `/mnt/workspaces/Cells/fr50-build-20261124/judged-4872266d/`.

**The landing head** will be 4872266d plus the ruling's docstring and comment (452db412), plus a merge of main after
FR-51's follow-up lands. The merge message states that FR-50's src differs from the judged head in docstrings and
comments only. The gate follows, on lane B, with the FR set.

## D364: corrections to D362 (FR-45 is registered; the label field); FR-54 and FR-57's note is final; no gap in the standalone replacement model

2026-11-24, about 20:54 UTC.

**FR-45's registration is tagged.** D362 said FR-45's protocol was not yet tagged and would be written against the
router. That was wrong.
- **The tags:** `fr45-site-competition-v1-registered-2026-11-24` (6e92d0ec) names `scheduled_compartment_wash@1` for
  W2, and its amendment 1 is tagged. Only amendment 2 (ff99fead on `fr45-protocol`, which adds W7) is untagged.
- **So:** FR-45's judged runs (W2 and W7) stay on the wash, or are pinned to an earlier snapshot. The wash's
  retirement waits for them, as it does for FR-49's B and C1 runs.

**The label field.** The router's label owner gains `label_collected_fmol` [labelled species, label, collector],
attributed to each portion's node of origin. That is exact for a chain, where reusing FR-44's field is not.
- **Without collectors** the field is zero-size, as FR-44's field is.
- **FR-49's judge erratum 2** (the name added to `LABELS_ONLY`) lands with the router, before any FR-49 judged run on
  an engine that has the router. A run pinned to an earlier snapshot needs none.
- **The absent-field form,** with per-declaration field sets in the contract (0.75 to 1 day of central code), is not
  taken now. It stays a candidate if owner fields keep growing.

**The note is final:** `docs/LIQUID_ROUTING_DESIGN.md` at f66a4828 on `fr54-57-design`.
- **The exponential** is `scipy.linalg.expm`, with scipy pinned and recorded in each run's identity, and BLAS at one
  thread (D190). Each source node's kept part absorbs the column-sum remainder.
  - The author probed it against a 40-digit exponential on equal-rate and unequal chains, and on looped networks of 8
    and 64 nodes. It was within 1.0 eps per entry.
  - The note's 4 and 8 eps checks are re-measured before the tag.
- **The three readout classes** are judged as D362 set out.
- **The default face heat's domain** and the energy check's stop are desk arithmetic, measured on today's engine
  before the protocol is tagged. By that arithmetic the 8 and 2 fmol world lies inside the domain at kh ≤ 0.2, and it
  completes under the default heat only at kh ≤ 0.05.
- **The price** is 8.25 to 10.5 agent-days with the wash's takeover, plus 1 to 1.5 for the collector's later opening
  as a node.

**No gap in the standalone replacement model.** The lead suspected that `resolved_pump_replacement@1` admits FR-51's
block, and it does not.
- **On `fr51-slot-refusal`:** its `check_definition` calls the composite's, so a block there is refused at parse by
  the slot refusal.
- **On main:** @3's `BLOCK_STRUCTURE_REFUSAL` already refused it.
- **Only the composite form** carries the stale-slot hazard, and the follow-up covers it. The probes are in
  `/mnt/workspaces/Cells/fr51-replacement-refusal-20261124/probe/`.
- **Two small follow-ups** go to the next no-src stack: a `composition_matrix.RULES` entry for the slot refusal, and
  the replacement row moved to the composite form, where that refusal is the only wall.

## D365: the user's decisions on FR-43's gaps (two closed next, turnover at changing volume logged as FR-65) and FR-58 to FR-62's priority

2026-11-24, about 21:10 UTC.

**FR-43's four gaps (D347).** The user chose three to close next:
- **Part 1's 16-row control and 256-row case,** as rows in the existing species-cap tests (D224).
- **Part 1's performance report, measured on CPU:** compile time, time per simulated second and peak memory. Its L4
  figures were taken on a path D336 now refuses, the composite on a GPU. FR-43 is the user's top priority, so its
  timing takes the timed cores under their lock.
- **Turnover in a swelling cell,** logged as FR-65 (high, as part of FR-43's request). This is D301's composition M3:
  turnover beside water, partition or insertion, reading the current volume and masks.

**Not now:** a registered criterion for part 1.

**FR-58 to FR-62 are normal priority.** Their design notes follow the high items.

**Tonight's slots** (the user: "use tonight well even if we have to pause something in the morning for the big delete
/ rename"). Four agents write without CPU:
- the rename's design note, with a read-only candidate mapping;
- the legacy families' port plan;
- FR-52's design note;
- FR-53's design note.

FR-43's builder takes the next free slot.

## D366: FR-30's Revilla diagnostic, second deliverable: the registered split had little power to test the law; D320 stands; Ek-Vitorín's fit waits for a power check

2026-11-24, about 21:21 UTC. The lead, with the advisor.

**The terms.** The diagnostic is labelled and non-blind (D343, D344). It decides nothing (W6), and changes no verdict
and no law. D320 stands. Every result is one study's indication, and D334's caveat applies to the steady-state
polarity difference, since Revilla's one-cell protocol ties V_j's sign to one oocyte's V_m.

**Identity, checked before the search, with no refit:**
- the tagged `predict` stage reproduced `predictions.json` byte for byte, apart from its time stamp;
- the objective at the judged parameters is bit-equal to the record;
- one shared slope and midpoint per gate set both the rates and the steady target.

**The declared reading, on the law's full box (free split).** This box has ten parameters on nine distinct targets,
so it is saturated (D1), and "could not test" was nearly forced there by counting.
- **The compatible sets:** 383, 397 and 411 at margins 0.5, 1.0 and 2.0 of excess over the polarity floor.
- **Their predictions at 80 mV,** all inner bounds:
  - τ_slow(80) spans 4.15 to 135 s;
  - τ_fast(80) spans 1.10 to 3.77 s;
  - G_ss/G_0(80) spans 0.332 to 0.473 (the lead, from `exact.jsonl`).

  Each covers both polarities' windows.
- **A witness on the floor,** S804 (excess 0.0000), predicts τ_slow(80) = 15.81 s, passing both ±80 lines.

**The judged family (split ½, eight parameters).** This is beside and post hoc, since the declaration gave the slice
no meaning on a premise the run refuted. Three sets fit the training data comparably and score differently on the six
judged lines:
- S59, at excess 0.0125: 3 of 6;
- S444, at 0.1456: 5 of 6;
- the judged fit, at 1.1242: 4 of 6.

What follows from that:
- **The local minimum cost no pass.** The registered fit stopped in one, but the family's better minimum scores fewer
  lines. D1's reading of the 1.124 excess, as the cost of eight parameters on nine targets, is superseded; no entry
  had quoted it.
- **In this family G_ss/G_0(80) is pinned,** at 0.434 to 0.450 (margins 0.5 and 1.0, 116 sets), just above +80's
  window top of 0.4339.

**Narrowed:**
- **"Could not test" holds for the two time constants.** The −80 steady-state line is failed by 79 of the 91 sets
  scoring 5 of 6. That is the polarity difference again, confounded as D350 left it.
- **The one set passing all six lines** (S247, post hoc) is recorded only:
  - it is 1 of 383, and one split sits on the box edge;
  - its G_ss(80) lies in a band 0.0094 wide, against a 0.007 digitising error;
  - it was checked with uncommitted code.
- **"Kinetics alone, feasible"** fits six distinct numbers with eight or more parameters, and supports nothing.

**The named witnesses** are scored through the tagged predict, readout and scorer (`d2/verify_key_sets.txt`): S804, S444
and S913 score 5 of 6, and S59 3 of 6.

**What it means.**
- **D344's "voltage dependence unvalidated"** now has its reason: two training magnitudes do not pin the law's
  interpolation to the held-out magnitude.
- **FR-30's next fit, Ek-Vitorín's** (tag A and amendment 1), fits `junction_series_gates@1` to `train.json` and
  predicts the held-out voltages. It has no power check and no stated starts. Before any fit, an amendment adds two
  rules:
  1. **A power check, judged first from the training data alone.** Over the parameter sets compatible with the
     training fit within a declared margin, compare each held-out prediction's span with its pass band. A comparison
     whose span covers both a pass and a fail is "not tested by the split", reported and not judged. The benchmark
     counts only tested comparisons, and is undetermined if too few remain.
  2. **Multistart,** with declared starts and a reported check of the global minimum.

  The fitter starts only after that amendment's tag. The extraction is not yet tagged (no tag B).
- **The diagnostic lands by merge** in the next stack with no src change, keeping its declaration (7c9f6ea0) ahead of
  its driver (64fbd84a). Branch `fr30-revilla-diagnostic`.

**Cost:** 3 h 33 min of wall time and 10.8 CPU-hours, on CPUs 6, 7, 22 and 23. The record is
`/mnt/workspaces/Cells/fr30-revilla-diagnostic-20261124/d2/`, with its SHA256SUMS.

## D367: FR-38 v2's judge is built from the spec alone; amendment 4 rules its questions and registers the export contract

2026-11-24, about 21:27 UTC.

**The judge.** A separate agent built it from the spec folder alone, at amendment 3's tag. It is on branch
`fr38-v2-judge` (4c98bd7a), untagged, and has read no engine output.
- **C0:** its reader accepted all six reference files, the invented one first.
- **Sizing:** every C2 must-catch unit clears the 10× rule. The smallest margins are P6 in AF at 72×, P1′ in AN at 159×
  and P3a at 786×.
- **Tests:** 23 host-only tests on invented inputs, taking 19 to 39 s.
- **Disclosed:**
  - It opened the six real reference files with ad hoc scripts, the invented file first, before its reader existed. It
    took their key names and entry shapes from them, and set its 1-ulp echo tolerances with them in view. No accept or
    refuse rule changed after the reader's first run on them.
  - It read no engine code and no engine output, and none of the references' code or README.

**Amendment 4,** tagged `fr38-v2-amendment-4-2026-11-24` (b4af13df). It is written by the protocol author, without
the judge's code, and value-silent:
- **Arm B's G scale** is the sheet's §3.4 reading, covering every chain's residues in transit. It is reported only, so
  no verdict depends on it. C0 checks a stated scale only where a judged entry's accuracy rests on it.
- **C4 runs at every rung,** each with its own step count, retry rungs included. Family D's energy identity is the
  exception, being stepped since amendment 3.
- **Blanks are judged runs,** and AF's two engine blanks must be bitwise equal.
- **P8's negative control** follows the literal text: a failure leaves family C inconclusive, never FR-38.
- **The judge forms P1, P1′, P1″ and P6 itself.** Builder entries for them are excluded from scoring and recorded.
- **A missing index** is recorded and flagged to the checker. A missing run, or a run without provenance, is still
  refused.
- **The judge's readings are confirmed,** with two corrections:
  - route 2's "every second output" counts even indices from the grid's start, which is the same in every registered
    world;
  - the restart comparison includes the labels and `released_present_gross`.

  An unscorable core plant leaves FR-38 at best inconclusive.
- **The export contract is registered (§8):** the builder's hashed per-family engine tables, hashed before any
  reference value is read. The judge's reader conforms to §8 before its tag, and the builder adds P9's V₀ patch to
  P9's record.

**Next:**
1. The judge adapts on its branch, then the lead tags it.
2. The builder's table follows §8.
3. The judged run waits for both, and for the lead's go.

## D368: OL6 Protocol D v2 passes its independent check on the first seed set; D318's failure stays on record

2026-11-24, about 21:38 UTC. The checker is fresh, neither the builder nor the first checker, working under the tag
`ol6-protocol-d-v2-registered-2026-11-24` (D357).
- **The snapshot** is at eced4ef8 (`snap-eced4ef8`), clean. Its src is exactly main 9d8c42be's, and the four files it
  judges with are byte-identical to their own tags.
- **The check:** `protocol_d_v2 check` passes 29 of 29.
- **The verdict** is `/mnt/workspaces/Cells/ol6-protocol-d-v2-checker-20261124/verdict/verdict.json`, with its
  disclosures and choices in `record.json`.

**The verdict: pass.** All seven worlds pass on the first seed set (670001 to 670000 + M), so no retry is needed.

| World | M (z) | B | Other |
| --- | --- | --- | --- |
| D1 | 1.38 | passes at all 4 rungs | P slope −0.504 |
| D2 | 2.52 | passes at all 4 rungs | P −0.512 |
| D3 | 2.23 | passes at all 4 rungs | P −0.500 |
| D4 | 1.57 | passes at all 3 rungs | E: mean z 0.38, SD ratio 0.19 |
| D5 | 1.94, on 56 spread pairs | passes at all 3 rungs | 16 constant pairs exact at both rungs |
| D6 | 1.97, on 29 spread pairs | passes at all 3 rungs | 11 constant pairs exact at both rungs |
| D7 | — | — | E on the paired Δ: mean z −0.15, RMS ratio 0.2385 |

- **The constant pairs:** all 27 hold, 128 replicas each, with (d)'s bits matching.
- **The precondition:** no exact replica and no (d) run was tense, and no pair was left unjudged.
- **The plants,** P-D1 to P-D8, are all caught. P-D8, the one-ulp plant, is caught 22 of 22.
- **The bounds:**
  - L: all 423 honest (d) runs close, with the largest moiety drift 1.5e-14 against 1e-12;
  - n_min is 98;
  - no clock refusal in 384 paired runs, the largest fraction of the bound used being 0.389.
- **Cost:** 7.79 CPU-hours against the estimated 13.5. Lane B was held for 59 minutes in batches between gates.

**The checker's disclosures:**
- **Erratum 2's module:** it read it in full to use `pd1_b`, including the disclosed docstring line.
- **Erratum 3's module:** three of its searches spanned that module's text, and none printed a line.
- **Commit subjects:** a `git log` printed one merge subject (9dac867b), which states no result. The session context
  showed main's recent commit subjects, D357's included.
- **A probe of other locks:** a non-blocking shared-lock probe briefly took, and at once released, the timed-cores,
  GPU and gap-junction locks. A checker should not probe locks it does not use, so this goes into future briefs.
- **PROGRESS:** following the brief, it wrote only to its own folder, so the PROGRESS line §10 asks for is the lead's.

**What it means.** OL6's deterministic representation (d) agrees with the exact stochastic chemistry on D1 to D7,
under the shared agreement rule.
- **D318's failure stays on record:** the first registration failed on D6's M alone, the zero-spread artifact. Version 2
  passes on fresh seeds after M's repair.
- **FR-47's** schedule supplement and independent check are next in this lane.

## D369: the user's direction on legacy: everything actually used leaves legacy, in Cells' canonical formats

2026-11-24, about 22:18 UTC. The user, on reading the port plan's summary: "the legacy work is clearly important cleanup we
need to make sure to get everything we're actually using out of there in our canonical formats".

**What it settles:**
- **The end state is canonical.** Everything Cells uses from legacy is re-expressed in the engine's canonical forms:
  its laws, models, operators and definitions, under the rename's IDs. Relocation alone, a legacy island moved into
  `src/cells`, is ruled out as an end state. That is the port plan's Q2 (c).
- **The scope is a test of use, not a list of IDs.** The port plan's "the 11 families" (D348) gives way to everything
  actually used. This restates the user's 17 November rule: legacy is removed in one batch after a check that covers
  every capability.

**Not settled: the sequence.** Whether a bitwise relocation comes first, as an interim step, is still the user's call;
D348 never defined "port". The morning's review prices both routes.

**The port plan is reworked** (plan only, by its author) around:
1. **A coverage table by capability and consumer,** not by ID or import closure. Each row gets one class: canonical
   already, expressible today, needs an engine feature, or dropped.
2. **A definition of "used," fixed before counting.** A test whose only subject is a legacy model is not a use. The
   plan's dry-run deletion, with a tiers run, measures it.
3. **The 18 BETSE drivers on other legacy IDs:** whether their evidence is still claimed anywhere. That decides the
   plan's Q1 and the rename's Q3.
4. **The "blocked today" list,** checked by reading each refusal site: calcium-permeant channels on @3, finite fuel,
   an ER store, and assembly coupling. Each confirmed gap is a candidate request for the user, not a logged FR.
5. **The BETSE rule (AGENTS.md, 8 November):** nothing in `src/cells` re-hosts or copies BETSE code or carries its
   conventions or names. A relocated family must meet that, which may rule relocation out for some families.
6. **Qualifying a re-expression** needs science-length runs, with a tolerance derived, never tuned. Five-step captures
   prove only a bitwise move.

**Order:**
- **The rename's Q3,** the 18 live pieces also spelled inside legacy, waits until the sequence is chosen.
- **In the morning,** before the rename's move lands, main is tagged and the pre-rename snapshot frozen. Every capture
  can run from it later.

## D370: a correction to FR-53's premise (the global ledgers' row-1 bound), from its design note

2026-11-24, about 22:19 UTC. The note is `docs/LEDGER_ROUNDING_DESIGN.md` on branch `fr53-design` (774fdcd5). Its
probe ran four worlds on CPU 4 under the timed lock: GJ-N1's line and 9×9 sheet, and synthetic sheets of 15×15 and
27×27 cells. The evidence is in `/mnt/workspaces/Cells/fr53-design-20261124/`.

**The correction.** In the `ledger_limits` family (`resolved_pump_tissue@1` to `@3`, the water models, the replacement
model and the composite), the bound at row 1 is not the bare material atol.
- **Row 0** has every residual exactly zero.
- **From row 1** the running allowance (2.5 ε k M) is already 97.6% to 99.9% of the total ledger's bound.

So FR-53's "zero at steps 0 and 1", and the "bare material atol" in D335 and the GPU criteria, do not hold for these
models. They do hold for `resolved_tissue@1` to `@10`, reached through legacy.

**What grows is the check's own summation, not the stored state:**
- **The row's exact residual** stays at or below 0.12 of the bound, and does not grow with the cell count.
- **The check's sum** reaches 0.12 of the bound on the host at 225 and 729 cells, and up to 0.19 on the CPU device. It
  is also the part that differs between host and device: D336 recorded the L4's two sums 0.51 apart.
- **No clean √N law fits.** The host's first-window shares are 0.044, 0.122, 0.169 and 0.115 at 25, 81, 225 and 729
  cells.

**The note recommends:**
- **One compensated sum** (fixed-order TwoSum), with the same code on host and device.
- **One bound form for every ledger,** with three declared classes: exact, rounding, and truncation. The truncation
  class carries its own term, as FR-38's amendment 3 taught, and FR-47's `atol_count` term belongs there.

Its five questions go to the user in the morning batch with the advisor.

**A note on the probe:** it held the timed lock for about four minutes while an FR-43 profile, the user's top priority,
was waiting. Briefs now say to release the lock between probes.

## D371: the user's decisions on the rename's family words, FR-52's form and scope, and FR-53's priority; the lead's rulings on the notes' other questions

2026-11-24, about 22:29 UTC. The lead brought the three notes' questions to the advisor, as the user asked; four went to
the user.

**The user's decisions:**
- **The rename's family words:** short where unambiguous, prefixed where a collision could come. For the five missing
  interfaces and the block law:

| Old ID | New ID |
| --- | --- |
| `rapid_binding@1` | `cells.binding.rapid_binding@1` |
| `shared_pool@1` | `cells.population.shared_pool@1` |
| `bilayer_geometry@1` | `cells.assembly_geometry.bilayer_geometry@1` |
| `pore_nucleation@1` | `cells.assembly_hazard.pore_nucleation@1` |
| `rate_equations@1` | `cells.assembly_representation.rate_equations@1` |
| `open_channel_block_weighted_modes@1` | `cells.channel_block.open_channel_block_weighted_modes@1` |

  The note's `block` is not used, since "block" already names a definition section throughout the code.
- **FR-52's form:** an engine record kept at each event, with the trace reader kept in `validation/` as the
  independent check.
- **FR-52's scope:** chains are needed now. Version 1 covers dimer-to-tetramer chains and single-subunit activation,
  through a declared identity map across states, rather than the note's two-state limit.
- **FR-53 goes to normal.** Its premise was corrected (D370), and on CPU nothing fails. FR-47's small ledger fix, an
  atol term for counts, lands on its own now that Protocol D has passed.

**The lead's rulings, as the notes recommend, with the advisor's cautions:**
- **FR-52:**
  - **Q3:** an observed state on both sides of a channel is refused in version 1; the page states how returns are
    counted.
  - **Q4:** the new tier-2 file, with one integer-unit world added to G1 and crossrev at landing, rather than a routine
    twin.
  - **Q5:** an optional `cohorts` key on `@1`; omission is the only spelling, and an empty list is refused.
  - **Independence:** the author's enumerated fractions are frozen in the note before the build, and the note states
    the float record's rounding bound.
- **FR-53:**
  - **Q3:** X2's registered floor is unchanged.
  - **Q4:** the fixed multipliers stay until evidence retires each one.
  - **Q1, Q2 and Q5** wait for the build, now normal priority, after reads of what the new sum changes in G1's and
    crossrev's saved fields, its compiled cost, and evidence on the L4.
- **The rename:**
  - **Q2:** the block law gets its own family, `channel_block`, with its law and interface registered in the hand
    refactors, so the mapping holds no seeded law row. The interface's name follows the family word.
  - **Q3:** the 18 live pieces also spelled inside legacy are re-spelled in legacy's files too, after a check for
    pinned legacy config digests. Every route left after D369 has legacy outliving the rename.
  - **Q4:** the ten sub-laws and the field closure law are in scope, since D346 names laws; the 35 recorded labels are
    not. Any that needs a new family word comes back to the user.
  - **Q5:** folders move separately, after the rename.
  - **Q6:** the manifest keeps `@2`'s keys, with its ID rule amended. The note checks the library pages' paths, and
    the viewer session is told.
  - **Q7:** tagged files are pinned or translated at live drivers, with an erratum only where a judge must change. The
    note lists every tagged registration with a run still to come (FR-38, FR-45, FR-49, Ek-Vitorín), each marked
    pinned or translated.
  - **Q8:** test plants take the three-part shape. The note states the grammar for outside modules, and the user is
    told that private IDs change shape.
- **The move's order:**
  - FR-38's build runs its judged run before it merges main after the rename.
  - The scripted move stays pure, with the long-line rewrap as a separate commit.
  - The scope map is refreshed right after the landing.

**FR-45, a coordinator's ruling.** P5's sizing on W7 covers both C6 and C4a, as for W2. CRITERIA's plant row, as
amendment 2 amended it, names both, and it governs the narrower per-world table in amendment 2 §3.

## D372: FR-50 phase 1 lands; FR-43 part 1's two gaps are closed on their branch, with the report committed by the lead on the user's approval; FR-66 is logged

2026-11-24, about 22:41 UTC.

**FR-50 phase 1 landed** at 1939563e (tag `fr50-phase1-landed-2026-11-24`). The landing trial passed 261 tests in 376 s.
- **The judged comparison passed** (D363).
- **The gate:** crossrev 11 of 11 identical; tiers 1+2, 671 files, none changed; G1 113 of 113 equal.
- **FR's set** passed.
- **The landing engine is the judged engine,** apart from docstrings and comments, by an AST comparison.

**FR-43 part 1's two gaps (D365)** are closed on branch `fr43-part1-gaps` (10338924). Its selection gate follows.
- **The missing cases are rows (D224), each with a plant:**
  - the 16-row control in tier 2 (24.35 s);
  - the 256-row case in tier 3 (35.5 s), which would push the tier-2 file past its 90 s cap.

  The planted fast link is caught at 9.3× to 10.1× the accuracy.
- **The CPU performance report (C1.4)** is `validation/fr43_part1/PERFORMANCE.md`, with `performance.json`. It ran on CPU
  4 under the timed lock, three fresh-process repeats per size, at 4f4c4812's frozen snapshot. Every repeat met the
  declared accuracy.

| Rows | Compile s | ms per step | s per simulated s | Peak RSS MiB |
| --- | --- | --- | --- | --- |
| 16 | 18.4 | 0.23 | 0.046 | 833 |
| 32 | 21.0 | 0.48 | 0.095 | 866 |
| 256 | 24.3 | 16.5 | 3.3 | 939 |
| 1,024 | 47.0 | 455 | 91 | 1,746 |

- **Against the design note:**
  - its comparable arms agree;
  - its headline 1,024-row figures (214 s, 3.9 GiB) are its unrolled arm, which the landed engine never runs above 16
    terms;
  - its L4 column is kept, labelled as taken on the path D336 found unqualified.
- **The refusal, and the user's decision.**
  - The harness refused the builder's write of a report draft ("Subagents should return findings as text, not write
    report files"). The builder held and did not retry.
  - The user approved the lead committing the report: the builder's text, and its measured JSON byte-identical.
- **For the morning:**
  - **Verify a finding:** the builder reports that the plain `runner.run` still admits the composite on a GPU, where
    only the vector windows refuse it (D336, D338). Check this against D187.
  - **Stale texts** go to the docstring batch: the large file's 1,024-row bullet, and the runs file's docstring (66 s
    against the record's 70.48 s).

**FR-66 is logged** (medium, the user): a passive fluorescence reader over FR-33's regional amount exports, with several
masks over one accepted trajectory.

## D373: FR-47's independent check passes, and its schedule supplement passes separately; FR-47's development-only status is lifted

2026-11-24, about 22:50 UTC. The checker is fresh: not FR-47's builder, its protocol's author or its references agent. It
ran under the tag `fr47-shell-exchange-registered-2026-11-24`, with the supplement and its erratum 1 at their tags.

**The frozen scorer's verdict: pass.**
- **The worlds:** all six pass (W1, W1Δ, and W2 at N_g 64, 256, 1,024 and 4,096). None was inconclusive, so no retry
  ran. No pair fell in the band; the largest |z| was 3.67.
- **The plants:** all nine are caught. Each predicted size the references gave is matched: for example P3 at 2.90e4
  bounds, P8 at 191.6 fail bands and P9 at 428.7.
- **The first read and regeneration:** the judge's first read of both invented files passed before any engine run.
  The references regenerate bitwise under two other hash seeds.
- **The books:** every ledger closes in 768 exact replicas and 6 (d) runs.
- **The snapshot:** f8c6c326, clean. Every tagged FR-47 file in it is byte-identical to its tag.
- **The record:** `/mnt/workspaces/Cells/fr47-checker-20261124/judgement/verdict.json`.

**The schedule supplement passes,** a separate result, never merged into the verdict.
- **The controls,** run before any saved run was read: the honest invented record passes, and cases A, B and C fail
  as designed.
- **The schedule:** every exact replica and (d) run records exactly the scheduled stops, in count, order, kind and
  time, with a clock bound of 0 s derived from the code beforehand.
- **The heats:** every scheduled withdrawal carries a finite heat. Every (d) run's intervals have the scheduled
  edges.

**So FR-47's development-only status is lifted** (D339: both must pass).

**The checker's disclosures:**
- **The plants** are scoped patches in its own driver, with its readings of P1, P3, P5, P6 and P7 stated.
- **Supplementary variants:** for P1 and P7, CRITERIA names only C1 and C2. Variants with the refusing check made a
  no-op exercised those criteria, and were kept out of the plant verdicts.
- **Two driver faults** (v1) were fixed and rerun (v2), with the v1 folders kept as evidence.
- **Cost:** about 1.06 CPU-hours, against the estimate of about 3.
- **Cleanup:** its two worktrees are pruned.

## D374: the user's decisions on legacy: keep and re-express the calcium ensemble; retire the physiology stack

2026-11-24, about 22:53 UTC. The port plan reworked for D369 is on branch `legacy-port-plan` (3b7c729f). Its finding:
measured by use, most of D348's eleven IDs are not used. Only the calcium ensemble is substantial, together with
`spatial_extracellular@2` for the JUPITER readiness check, `resolved_tissue@8` as @3's reference world, and
`source_decay@1` as the test conftest's world. The advisor sent two questions to the user, because both revisit the
user's answer of earlier the same day, "keep BETSE and ensemble".

**The calcium ensemble is kept, and re-expressed in canonical form.**
- **What it is:** the assembly-regulated cell and cluster on `spatial_calcium@1` to `@4`, run by the GPU ensemble
  runner and the JUPITER readiness check.
- **What it needs:** five engine features, the plan's G-1, G-4, G-5, G-7 and G-8: calcium-permeant channels on @3,
  an ER store, IP3-gated release, assembly coupling, and the composite on a GPU. The author's rough guess is 16 to 28
  agent-days. These are candidate requests, sized by their own design notes, not FRs yet.
- **The route** comes back to the user with prices:
  - relocate first, then re-express (route A);
  - re-express directly (route B);
  - prune legacy in place to the used cores, then re-express.

**The physiology stack is retired.**
- **What goes:** the 17 drivers on legacy's five BETSE IDs and the 18 REF-era drivers. No current document claims a
  result from them, and their helpers are BETSE glue throughout.
- **What stays:** the BETSE parity that PROGRESS claims, which runs on the live `resolved_pump_tissue@1` to `@3`
  ladder, and BETSE itself as an outside reference. The ladder's one legacy import, a re-export of a live helper,
  becomes a direct import.
- **How:** the drivers and their tests retire in the approved deletion batch, with their records kept. That batch
  needs the dry-run deletion, a tag, and a removal list the user approves.

**The lead's rulings,** with the advisor:
- **No retirement before the rename's move.** It would save about a dozen files, but a deletion needs the measured
  dry run and the user's approved batch.
- **Inside that batch:**
  - the plan's Q5: @3's checks against `resolved_tissue@8` stay for now, and move to an independent validation
    reference at the end;
  - the plan's Q6: `source_decay@1`, `emt_mirna@1` and `passive_pair@1` are deleted, and the conftest's users point at
    a live world.
- **Waiting for the route:** which engine gaps to request, and the plan's three lead rulings. Tolerances are derived
  in each re-expression's registration, never ruled.
- **For the plan:** check that its coverage table has the protein inventory's law records that point into legacy
  (13 of 81 on 17 November).

**Tonight:** a dry-run deletion of legacy in a scratch copy of a frozen snapshot measures what depends on it, on lane B
after FR-43's gate. It changes nothing on main.

## D375: the user's decisions on FR-52's splits and FR-65's scope; FR-45's amendment 3 is tagged

2026-11-24, about 23:10 UTC.

**FR-52: a split makes a new unit.** When a tetramer formed from two original dimers splits back into two dimers inside
the window, one dimer keeps the original identity, and the other counts as newly assembled.
- **What follows:** "initial" stays a true survival count, and every split adds one to "newly assembled". The round
  trip ends at 1 initial and 1 new.
- **This refines D371's sentence:** a partial-assembly step does not count a unit as new, but a split does create one.
- **The note** (`fr52-design`, ed0bd135) froze both readings' values in advance, so this needs no erratum. It now keeps
  reading (a).
- **The lead's rulings, as recommended:**
  - P1: a channel step with one tracked unit on each side keeps its identity with no declaration;
  - P3: the G1 and crossrev world is added with its cohort declared.
- **The price** is 4.25 to 5 agent-days, after the rename.

**FR-65: the first build also admits a lumen,** at nodes turnover does not read. That adds about 1 to 1.5 agent-days to
the note's pairwise, lumen-free core, for about 3.25 to 4.5 in all.
- **The note** is `fr65-design` (3dd81578).
- **The lead's rulings,** as the note recommends:
  - Q1 (b): turnover first, then the coupling's reads of the current volume, so that A1 in a swelling cell is admitted.
    It adds about 2 to 2.5 agent-days, and the coupling's contract extension is designed in that step.
  - Q2 (a): the builder's tests, with no new registered criterion. The Q5 assertion of D150 flips, amended in place with
    disclosure as on 20 November.
- **Not now:** partition beside water (M4) and water's current area and masks (M2).

**FR-45's amendment 3 is tagged** `fr45-site-competition-v1-amendment-3-2026-11-24` (98cd33db).
- **W7s's horizon** is 2.0 s (47 time constants), so every interval's heat stays resolved. The sizing rule gains an
  upper side.
- **dt · max L ≤ 0.03** holds, as §4 registers. W7 and W7s now step at 0.0025 s, and amendment 2's sentence confusing
  h with dt is withdrawn.
- **Plant entries are keyed** (plant, criterion, world, time_s). P5 under C6 on W7 keeps two entries.
- **Next:** the references agent regenerates W7 and W7s before the references' tag.

## D376: FR-43 part 1's gaps land; FR-45's references v2 are tagged; a privacy slip on a Lean merge, the user's decision on the Lean tips, and the merge check that now runs

2026-11-24, about 23:35 UTC.

**FR-43 part 1's two gaps landed** at 14f19f9f (tag `fr43-part1-gaps-landed-2026-11-25`), with the selection gate at
a4e638c2 done 0: 572 of 671 files, none changed. The landing trial passed 219 tests in 164 s.
- **The tag's name is a day ahead:** the landing was at 23:34 UTC on 24 November. The pushed tag stays as named.
- **The gate certifies the test rows and the report.** Two docs-and-record changes followed it: the report's text, and
  the tier-3 record entry for the 256-row case (0 blocking and 0 reported against the run).
- **The report's text was corrected.** The builder rechecked it against its twelve records after the gate and found
  errors, among them a claim that the step cost follows the sibling thread's load, which it withdraws. The lead checked
  each corrected figure from the records. The measured figures did not change. The landing message's own step-cost
  sentence was wrong at 16 rows and was corrected before the commit: within 6% of the design note at 32, 256 and 1,024
  rows, and 12% below it at 16.

**FR-45's references v2 are tagged** `fr45-references-v2-2026-11-24` (b62ce23c). W7 and W7s conform to amendment 3:
the methods agree to about 1e-68, every W7s interval's heat is resolved, and the files regenerate byte for byte
(774,060 bytes). Its judge comes after the rename.

**A privacy slip, and the user's decision.**
- **The slip.** The lead merged a Lean branch (1b3bde45) without running the privacy scan on it, because the Lean check
  looked at paths, citations and gates only. Five of its lines match the list kept for a private review. The matched
  word is one main already carried in 37 files of published citations and viewer data. No project name appears in it,
  in any Lean merge of the day or in any waiting Lean tip, and the lead's own commits and landings that day are clean
  on both lists. A push cannot be undone, so it stays.
- **What the user decided.** The waiting Lean tips add published-paper evidence that uses another word on that list,
  as well as that one. The user asked Lean to reword first, and Lean is doing so. The tips are held until then. Since a
  merge publishes every commit in its history, Lean rebuilds the unpublished commits instead of rewording on top. The
  commit numbers the records cite will change, and Lean sends a map.
- **The check now runs before every Lean merge,** as a tool in the lead's folder (`lean-ready.sh`, not in the
  repository). It requires: the gate done 0 on exactly the tip; a clean trial merge that touches only `lean/`; every
  cited commit on main, lean-only on the tip's history, or a tagged commit; and both lists at 0 in the merged lines, in
  every unpublished commit and in every commit message. It held the waiting tip and passed an earlier clean one when
  tested.

**FR-52's note:** the lead accepted its rule that a merge or split declares exactly min(R, P) pairs, and ruled that a
channel with only one legal pairing resolves by rule, with a declaration of it refused.

**Also noted.**
- **A correction to the lead's own summary:** the lead told the user on the evening of 24 November that the FR-51
  holdout registration was waiting for Lean's answer on re-reading the 5.4 mM anchor. The request had not been sent. It
  is now with Lean, through the user. Extraction waits for the registration's tag.

## D377: FR-51's judged pass is recorded; PROGRESS and the feature index are brought up to date; three design notes are final; corrections to the legacy plan's figures

2026-11-24, about 23:57 UTC.

**FR-51's judged comparison (fr51-channel-block-v1) passes.** It ran once, at the clean snapshot d3b3cf0b, whose code
equals the landed head's, with the tagged judge (`fr51-channel-block-v1-judge-2026-11-24`, 5b9b4c90), against the
code-blind references (`fr51-references-2026-11-24`, 1360c925). Every registered criterion passes and none is
inconclusive: P (4 cases), B-u (18), B-ratio (7), R (8), S (2), G (12) and E (8). All eleven reference-judged plants
are caught, and RUN, Z and C hold in the tests. The record is
`/mnt/workspaces/Cells/fr51-build-20261124/judged-d3b3cf0b/` (`verdict.json`, sha256 bb04eeba…). The landing message
(955765ef) and the FR's index row stated it, but no decision entry did until now.

**PROGRESS.md** is refreshed from the decision log and the tags, after 22 November. An agent drafted it
(`progress-refresh`, 619cfa47, not merged); the lead reviewed it, replaced 33 tag-object hashes with the commits they
point at, and corrected the stale lines it flagged. **The feature index** had five rows behind the decisions (FR-17,
FR-38, FR-44, FR-45, FR-47), which are now current. FR-45 has no engine code on main.

**Three design notes are final,** each on its own branch, landing in the next no-src stack:
- **FR-52** (`fr52-design`, c43f9a4a): the declared pairings need exactly min(R, P) pairs; a channel with one legal
  pairing resolves by rule, and declaring it is refused (D376). The reviewer's gap is closed: a host test of the update
  against enumeration on small random tables, whose plant applies one pair per channel, and a row G in the same compile
  (a channel carrying two identities). The compiled qualification world also gains the declared pairing's two
  channels; if the file passes tier 2's cap it falls back to the host row, and the landing text says which.
- **FR-65** (`fr65-design`, df473a02): the lumen by the host-only hook, which changes no lumen program; parse rows and
  one tier-3 run each for the two pairings that newly parse; first build 3.1 to 4.45 agent-days, the coupling step 2 to
  2.5 more. Turnover's readouts (solute amount and volume at every accepted row) already exist in the run files, as
  read from the code; the build checks them against a saved file. The note cites its commit 3dd81578, whose message
  claimed a review that had not happened: the author disclosed it, and the history is kept because D375 cites it.
- **FR-64** (`fr64-design`, 377a1b34).

**Corrections to the legacy plan's figures** (plan at `legacy-port-plan`, ef344334):
- Route C's first batch removes at least 58% of legacy's lines, not the 63% the lead had called firm. Higher figures are
  estimates.
- "About 15 hand edits" is 15 direct edits, with another 50 fixture files open.
- `resolved_tissue@1` and `@2` are used by live-subject tests, and their code is live; only their dispatch sits in
  legacy. The kept set now includes them, with `@8`, and route C's first batch moves their dispatch to the live
  registry, using exact-type checks, since legacy classes that stay derive from the two spec classes.
- The choice for the user is whether a CPU re-expression of the calcium ensemble counts as leaving legacy, with its GPU
  path parked, or whether legacy's core waits for the GPU. The plan recommends the first.

## D378: Lean's rebuilt tip is merged with its commit map; FR-51's two-potassium registration and FR-38's amendment 5 are tagged; the legacy dry run, the gate-speed evidence, and a correction to D339 and D371

2026-11-25, about 01:18 UTC.

**Lean's tip dfe2a723 is merged unedited at 18198688** (71 files, all under `lean/`). Lean reworded published-paper
evidence at the user's request and rebuilt its 17 unpublished commits, so their numbers changed. The gate passed on
exactly that tip, run by the lead on lane B from Lean's own frozen snapshots, because lane A holds the GJ-N1 run
(`/mnt/workspaces/Cells/lean-dfe2a723-laneb-20261125`). The check of D376 was GO. **Earlier entries name commits by
their old numbers.** They map as:

| Cited as | Now |
| --- | --- |
| 59fe4896 (D355, D356) | 369431f7 |
| fccbb5e5 (D355, D356, D360 and FR-51's follow-up; the block law's docstring) | 48fb7e0f |
| c1924c89 (D376) | 2473ba85 |
| 647b4c15 (D351) | d8c90f12 |
| 27d641a6, e28a6046, 0cd4bab4 (D376) | e43b2757, 7d74bbcc, 8aba3211 |

The docstring is updated in the next docstring batch. The old entries stay as written.

**FR-51's two-potassium registration is tagged** `fr51-two-potassium-registered-2026-11-25` (28e8e734,
`validation/fr51_two_potassium/REGISTRATION.md`), before either held-out curve is read.
- **The scope.** Panama and Lopatin's 10 and 20 mM levels, on the 5.4 mM calibration that Lean re-read on the 5 mV grid
  (half crossing −74.05 mV, bracket [−75, −70]), with FR-51's landing 955765ef as the engine and the frozen scorer and
  calibration at 18198688.
- **The rule was written knowing this study's 60 mM result (ratio 0.83), and says so.** The 20 mM level decides and
  10 mM supports. A pass rejects a shift under about seven tenths of the concentration-based one at 20 mM. It cannot tell
  a Nernst shift from one that tracks the measured reversal, D355's open gap. The label a pass would lift says
  direction, and that size is not judged.
- **Safeguards.** Two fresh readers with a blind control on the 5.4 mM trace, a sheet of the panel's labels written by
  another agent, no re-read and no third reader, and no other extraction scored. The engine check uses Lean's K(0) rule
  and catches a wrong external K, a wrong internal K, the membrane-voltage reference and a flipped sign.
- **The advisor's review** found the first draft's faults: a planted error that could not fail, readers with choices,
  and a rule written knowing a result without saying so.

**FR-38's second comparison: amendment 5 is tagged** `fr38-v2-amendment-5-2026-11-25` (fcbcb8e7). The builder's tables'
shapes are pinned by a registered format sample (`/mnt/workspaces/Cells/fr38-v2-format-sample-20261124/`, read-only) that
holds invented worlds only: 0 of its numbers match 99,441 numbers of the run records, the registered definitions and the
spec's literals. It shows every key, name and type; a judge may not take values, lengths, identities or orders from it.
The judge conforms next, and must parse the sample before its tag. The sample took three attempts: the first let one
number survive the scrub, and the second had the wrong number of transcription stages in four families, which the
builder's own check missed and later caught.

**Legacy: the dry run** (tool `validation/legacy_port/dry_delete.py` on `legacy-dry-run`, 144e0ef9; records in
`/mnt/workspaces/Cells/legacy-dry-run-20261124/`). With `src/cells/legacy/` deleted from a scratch copy:
- **Tiers 1 and 2:** 508 of 671 files pass, 147 fail, 16 failures unchanged from the control. Classes: 105 test only
  legacy models (30 physiology, 8 in route C's kept core, 67 not checked row by row), 27 test live code with a legacy
  vehicle, 4 fail through one validation tool, and 11 are helpers and lists.
- **Tier 3:** all 11 files run failed. 211 were not run, among them the calcium ensemble's own tests.
- **A gap:** two refusals of a wrong execution or experiment type live in legacy's `to_dict`, and no test covers them.
  After deletion a live model with a wrong type raises an `AttributeError`. They move to live code with the first batch,
  with a test.
- **The lead's rulings:** the eight planning tests and test_recovery_response_grid are live code with a legacy vehicle;
  test_spatial_extracellular_acceptance_resources is in the kept core. The plan (`legacy-port-plan`) is being corrected.

**Gate speed (D358): the evidence for the third change.** Of 469 reader files, 243 were traced, and for regular files
the map is complete in all 216 the change would release. One bug blocks it: `sitecustomize.py:148` keys a folder listing by
the folder alone, so a test's own listing is dropped when a library lists that folder first. It is fixed, the map is
re-recorded from a passing nightly, and a standing trace check is added, before the change is built. The 37 files with
unmapped children are explained: 31 can be mapped by small rules. On a lean-only change, today's readers rule selects 475
files (10,271 test-seconds), the change 66 (1,452), and both changes 37 (1,052). Evidence:
`/mnt/workspaces/Cells/d358-evidence-20261125/`.

**FR-47's ledger limit: a correction to D339 and D371.** They tie the limit to E2 places and a zero start. A builder
measured otherwise: it comes from Q's absolute tolerance in any world whose energy bookings are small. Plain one-molecule E1
worlds are refused too, and W1, W1Δ and W2 have zero starts. A term gated on a zero start would loosen W1's closing test up
to 24 times and still refuse those worlds. The form that follows the cause adds a term at every controlled step of every (d)
world, in its own ledger column (D370's truncation class). That is larger than the small fix D371 recorded, so it waits for
the user: build it as its own gated change, or keep the documented limit until FR-53. FR-47's `FORMAT_RATE_EQUATIONS.md`
wording is corrected on its branch. A tiny world is refused, never wrong.

**FR-55's design note** (`fr55-design`, 6109cfad) recommends no build: the two published records do not support a
dose-dependent closing rate, and a same-patch low-dose rise and washout would reopen it. The user's decision is pending.

## D379: FR-51's two-potassium engine check passes, and its readers wait; FR-47's ledger limit, measured; six design notes filed; corrections to D366, D372, D377 and D378

2026-11-25, about 02:05 UTC. The lead.

**FR-51's two-potassium registration** (`fr51-two-potassium-registered-2026-11-25`):
- **The engine check of section 2 passes.** It ran once, from a clean snapshot of 955765ef, with the script committed
  first (`fr51-two-k-engine-check`, 09b718d3). The reversal arm's half crossings are −74.159891523, −58.230247578 and
  −40.311006814 mV at 5.4, 10 and 20 mM. Its shifts, +15.929643945 and +33.848884709 mV, equal the predictions to
  5.3e-15 mV, against the registered 1e-6. The absolute-voltage arm moves by 0, and all four plants are caught by the
  criteria the registration names for them. The record is
  `/mnt/workspaces/Cells/fr51-two-k-engine-check-20261125/run-01/result.json` (sha256 7a40b3dc…).
- **A wording fault it found.** Section 1 reads as if the composition's own 5.4 mM crossing were the reading's, −74.05 mV.
  It is −74.160, inside the bracket, and no shift depends on it. It becomes erratum 1, with the blocker's side and
  valence, tagged before any curve is read.
- **The readers' sheet is not filed, and no reader has started.** Its writer found that the panel labels its traces by
  circled 5, 10, 20 and 60, and that two lines leave the circled 10. Section 3 stops the registration if the sheet cannot
  say which trace is which, so the question is with Lean through the user. If Lean cannot say from the caption, a
  dated erratum comes before any reading: both lines are read, and 10 mM is unresolved if they differ. The 20 mM level
  decides in any case, and 10 mM supports.

**FR-47's ledger limit, measured** (branch `fr47-ledger-atol`, 2c5b84ef; records
`/mnt/workspaces/Cells/fr47-ledger-atol-20261124/`). D378 left the form that follows the cause, (c), to the user. Built
as a candidate and not landed, it costs more than it gives:
- **It loosens closings that registered worlds meet:** W1 24 times on its first row and 2.2 times at its end, W2 42
  times, D1 up to 594, D3 108 and D5 65. A heat leak of half the bound now passes, and P-D1, a registered plant,
  would be admitted on a rerun. No code reads its old refusal.
- **The remedy exists today:** a tighter `atol_count`. In the case measured, 1e-7 closes it, at 149 steps against 83
  (about 0.5 s).
- **The lead's recommendation is changed:** keep the documented limit and do not build (c); FR-53 takes the class. The two
  commits that correct `FORMAT_RATE_EQUATIONS.md` (9efe77b0, 2c5b84ef) land in the next no-src stack. A small gated
  change that makes the refusal name the remedy is optional. D371's line, that the fix lands on its own, waits for the
  user's decision.

**Legacy, corrections to D377** (plan `legacy-port-plan`, 4781e141, frozen until the user chooses a route). "At least
58%" stands.
- **"15 direct edits, with another 50 fixture files open" is replaced.** With the dry run and the reading after it, about
  49 surviving files change by hand at route C's first deletion. Most of them change on every route, because they drop a
  world that goes. None of the 50 fixture files needs a hand edit. The pruned tree's own run fixes the number.
- **The saving in tiers 1 and 2 at that deletion** is 99 files and 2,398 test-seconds, about 7.5 minutes of a full gate.
- **Every route costs 2 to 3 agent-days more** than the prices the lead gave: A 20 to 30, B 15 to 22, C 16 to 25, beyond
  the engine features.
- **The kept core's own tests are weak.** Five of its ten test files in tiers 1 and 2 already fail in the record, and
  `spatial_extracellular@2` has none, so the bitwise windows taken before the prune carry its proof.
- **D211's cotransport kernel leaves with the first deletion,** and no route ports it. It goes to the user with the route.

**Six design notes are filed, each on its own branch; none is built,** and each lands in the next no-src stack with the
user's answers:
- **FR-55** (`fr55-design`, 6109cfad): recommends no build (D378).
- **FR-58** (`fr58-design`, 0d54e2e9): a label on an exchangeable group. The reactions already compute both one-way
  extents; the pairing of donor and product is lost before the label owner sees them. An optional `groups` key,
  4 to 4.75 agent-days. It found a latent fault: the gene unit's label report doubles what its hold carries when a species
  row is given twice.
- **FR-59** (`fr59-design`, 8e12ce53): the flux is finite at an empty pool; every logarithm of the row is not. It needs an
  exact charged heat booking, which D217 left unapproved, so it is the user's. 4.8 to 6.1 agent-days.
- **FR-60** (`fr60-design`, 179ec8fa): an external potential on a declared place, with the work formed from integers and
  declared values. 2.5 to 3 agent-days. FR-60's own acceptance example cannot see the change act on the wrong state.
- **FR-61 and FR-62** (`fr61-62-design`, 6fd4dd85): one rotor, with its own angle, on the cycle kind. A kind may already
  own a ledger, so rule (a) of MODULE_SYSTEM §7 no longer bars it. 5 to 7 agent-days.
- **FR-66** (`fr66-design`, 1ba73040): a host-only reader in `src/cells/assays`. 1.05 to 1.2 agent-days.

**Corrections:**
- **D366 calls Ek-Vitorín 2016 "FR-30's next fit".** It is not. D341 and D342 found that benchmark undetermined by its
  data's structure, so no data file exists and nothing can be fitted, and D343 parked FR-30. D366's two rules, a power
  check and multistart with declared starts, bind any later registered fit. No amendment is owed now.
- **D372's question, whether a plain run admits the composite on a GPU, is answered by reading main.** It does. A plain run
  checks every row on the host. What D330 measured and D336 closed is the device's own checks:
  `row_checks="device"` is refused on a GPU (`execution/row_checks.py:71`), and the vector windows refuse the composite.
  D338's "main's scalar row checks already refused a GPU" means the device row checks. No refusal is missing. Two texts
  still say the GPU is unmeasured (`row_checks.py:65`, ARCHITECTURE.md:112), and are corrected in the docs steps of the
  next stack.
- **FR-58's note found a live law missing from the rename's table** (`ideal_detailed_balance_mass_action@1`). The
  author is checking every live ID.

**Started overnight, on branches, none landing yet:** the rename's hand refactors, staged so that each passes today's
tests before any ID moves (`id-rename-hand`, with the strict grammar last on `id-rename-strict`); the capture tools for
the calcium ensemble's science set, which every legacy route needs (`legacy-captures`), with a pilot before any lane is
taken; D358's gate-speed changes; FR-38's judge; FR-56's note. The advisor was asked about the first two and did not
answer (it timed out twice), so starting them is the lead's own choice.

**The docstring batch is done on its branch** (`docstring-batch`, a182e5da, 14 commits; not landed): the scope lines of
D337, D338, D340, D344, D351 and D355, the block law's Lean commit, D364's two follow-ups (the `RULES` entry and the
replacement row's composite form), and two species-cap texts. For items that touch `src`, only docstrings differ, by two AST
tools; the two species-cap test files also differ in docstrings only. The wording is the lead's to review before it lands.
Two lines have no page to go on yet (`kir2p1_mh2@1`, and the block law's page, which the rename's hand refactors add).

## D380: a correction to D379 on the composite on a GPU; FR-38's amendment 6; the rename's table gains 52 missing IDs; FR-51's erratum drafted; notes on FR-56 and FR-43's co-writers

2026-11-25, about 03:07 UTC. The lead, with the advisor.

**A correction to D379 (the advisor's finding).** D379 answered D372's GPU question with "no refusal is missing", and
PROGRESS called it settled. That was the lead's ruling, written as if it were read from the code. What the records show:
- **The plain path on a GPU has judged evidence, for some worlds.** The composite's L4 agreement run of 14 November passed
  W1, W2 and G2-Q1's Q1 to Q6 unflagged. It failed Q7, which asks for bitwise equality with @3 on the 825-node tissue; Q7
  passed on 16 November, judged alone under XLA's deterministic flag (D168, D181).
- **An unflagged run varies from one repeat to the next,** by up to 1.9e-11 relative on that tissue. D335's block 2 found
  the host and device modes differing in amount increments, passive-route transfers and heats, and reaction ledgers.
  Those are the rollout's own arrays, and the builder's cause, the order of its scatter-adds, is inferred. So the
  variation would reach any composite run on a GPU, host-checked or not (D182 left it open). Under the flag, 15 of 15
  pairs repeat bitwise.
- **What D336 closed is the device's own row checks.** D347 and FR-43's `PERFORMANCE.md` call the whole of "the composite
  on a GPU" a path D336 found unqualified, which is wider than D336's words. Their labels are corrected with the next
  docs landing, as is PROGRESS.
- **What to do about a plain, unflagged run is the user's,** since D336 was: admit it with the caveat stated, require the
  flag, or refuse it. The lead leans to the first, since D181's judged runs use the plain path. `row_checks.py`'s raised
  message still says "until a GPU measurement exists"; it changes with the next `src` landing, with its test.

**FR-51's two-potassium erratum 1 is drafted, not tagged** (branch `fr51-two-k-erratum-1`, bdfc9e3e). It fixes what the
registration left open, before any curve is read: how the two files are scored (a script, `score_readers.py`, that calls
the frozen scorer unedited and applies sections 3 and 5; its self-test plants nine kinds of faulty file), the reading
of the control (the half crossing lies in [−75, −70] mV, ends included), the form of a file, and the fallback if the
circled 10 stays ambiguous (the 10 mM level is not read and is unresolved). Readers get a bare folder with the image,
the sheet and a form check that prints no value. The figure's legend, read in part by the sheet's writer, does not say
what the two lines are.

**FR-56's design note is filed** (`fr56-design`, 172fce4c): a preparation's own (temperature, area) rows beside the species'
sourced area, read at parse to the integer quanta the engine already uses. One agent-day, host rows only, no compiled
world, no registered comparison. A change of temperature inside a run stays refused, because worlds declare no
enthalpies. The direction of POPC's expansion is confirmed, the size is not (2.33e-3 against 8.36e-3 per K, about 1.3
combined errors apart). Five questions go to the user.

**The rename's table was incomplete: 52 live IDs were missing** (`rename-design`, 2dd54f72). FR-58's note found one of them
(D379), and the author then checked every quoted ID, 2,062 in all. Each of the 1,869 that are not in the table has a
recorded reason.
- **Now:** 193 rows and 386 old spellings, with no collisions. 127 rows are settled, 17 wait for the user's words, and 49
  for the lead.
- **Why they were missed:** an ID held by any legacy module had been classed as legacy's; every `kind` key as a schema key;
  mixed-case IDs, and IDs built at run time, were not seen.
- **45 sites need a hand change, and five of them fail silently,** so the script alone is not complete. Among them, a
  test fixture's `startswith("nav1p2")` would set no channel change. The hand refactors take the list.
- **The lead's rulings, to be confirmed with the user's words:** the three `resolved_tissue` models and 45 catalogue laws
  stay bare until C-1, as a stated exception; `ionic_worlds@1` is minted; of the 36 hash-pinned files, the Python ones
  are re-spelled and the 18 data files left; the 8 example artifacts' outcomes are declared and their tests leave with
  legacy, unless regenerating them proves easy.
- **The tool is being built** by another agent (`id-rename-tool`). Its generated table must equal the author's, row by row.

**FR-38's second comparison: amendment 6 is tagged** `fr38-v2-amendment-6-2026-11-25` (f555dcec), before any engine run of a
registered world. The judge had conformed to amendment 5 and reported five readings that could change a verdict. The
lead ruled on them from the registered text, and the protocol's author wrote them down, with three corrections:
- **A refusal never hides a fail.** The judge scored a run "refused" when its twin, blank or restart was refused, even
  where an entry of its own failed, which could read a fail as inconclusive. An entry that can be formed and fails now
  fails its run. One exception is kept and stated: an entry that C0 refuses for a malformed leaf.
- **A refused P9 is caught;** a refused blank leaves P1″ unscorable; AN's missing restart refuses the restart alone; the
  equalities run over named things, a narrowing disclosed before any run.
- **A dry C0 by the lead:** the judge's own definition check on the builder's registered definitions, with made-up
  readouts: 76 entries with no fault and no flag, ten plants that differ only by their registered change, and 15 of 15
  planted wrong inputs named (`/mnt/workspaces/Cells/fr38-v2-dry-c0-20261125/`).
- **The registered engine is main's at the merge** of main with the three branches, so the checks the amendment names are
  re-run there before the registration tag: the builder's own, the judge's, the dry C0, the author's arm-A probe and the
  regenerated format sample, on made-up values only.

**Legacy: the science captures are queued on lane B** (`legacy-captures`, 1dc62bdf; about 70 MB under a 1 GiB cap). They
are the calcium ensemble's present results, from a frozen snapshot of 76a498ae, at h, h/2 and h/4, and every legacy route
needs them. The pilot corrects the plan's section 8: about 1.8 CPU-hours, not 6 to 8; JUPITER's configuration is at
100 µs, not 50; the whole run in one window is refused at h/2 and h/4, so it is saved in 256-step windows. A short
bitwise check, run again at the pre-rename tag, will show that the stack's earlier commits do not reach the captured
worlds.

**FR-43 part 3's open item has a design note** (`fr43-part3-cowriters`, c82d8d42; docs only): local reactions and the gene unit
may share a row that the integer-unit population moves, as turnover and exchange do, by one general rule on shared
rows. It is refused today only by definition checks; with those lifted in process, both pairs ran compiled with every
host check passing and restarted bit for bit. Event times and amounts are second order in the step, and exact where rates
are constant. 3.75 to 5.25 agent-days with one judged comparison. Four questions go to the user. It also found that
`site_occupancy@1` writes moved rows with no check, and that the hazard bound ignores what co-writers make.

**FR-54 and FR-57:** the registered protocol's author and the recorded dt study have started, as the note's order has it
(the protocol is tagged before the build). The study measures the default face heat's domain on today's engine; the
protocol's spec is value-silent, and its references come from a code-blind agent.

## D381: FR-38's second registered comparison passes, and its independent checker agrees; the pre-rename stack lands; FR-54 and FR-57's protocol is tagged

2026-11-25, about 06:31 UTC. The lead, with the advisor.

**FR-38's second comparison passes as registered** (`fr38-v2-registered-2026-11-25`, b0974a06: main at acc080c5 with the spec,
amendments 1 to 6, the references, the builder and the judge; the engine is main's). It is recorded beside D313's failed
verdict, never in its place.
- **The campaign:** 86 jobs from the tag's clean frozen snapshot, on lane B in 30 minutes; every job exited 0 and the
  engine refused none. The tables were hashed and written down before any reference value was read. The record is
  `/mnt/workspaces/Cells/fr38-v2-campaign-20261125/`.
- **The judge** (`judge/verdict.json`, sha256 15b5a104…): AF, AN, B, C and D pass, and so do arms A and B. All 12 plants are
  caught and P8's negative control passes. No run is inconclusive or refused and no retry is owed. The largest gap over
  tolerance among 605 judged readouts is 0.542 (`E_tx` at 30 s, AF and AN `p=0 returned`). No difference was flagged.
- **An independent checker** recomputed C0, every criterion and every plant with its own code from the registered text and
  the hashed tables. Its verdict was written and frozen before it opened the judge's (`fr38-v2-checker-20261125/out/`,
  90ce0afb…): it passes, and 6,959 flags and 7,791 numbers of the two agree with no flag differing. The references
  regenerate byte for byte under two other hash seeds. Of its 130 perturbation probes, 127 are flagged, the honest
  control passes, and two are missed (below).
- **What the pass cannot show,** by the checker:
  - **An error at the finest step alone.** A label changed by 1e-6 at h alone, with the membership sum kept, passes in two
    of seven such probes. At p = 2 the tolerance is at least the step difference itself, so C2 cannot fail it, and C3 sees
    it only where the orders are resolved (243 judged p = 2 series are not). It is a property of the registered rule. No
    readout here has that pattern.
  - **Order coverage is thin:** resolved orders are 21 of 224 (AF), 15 of 149 (AN), 22 of 50 (B), 7 of 56 (C) and 34 of
    58 (D); no label order in AF or AN is resolved.
  - **Four judged readouts** (AN and C `E_tx`, B `H_tx_release` and `n_R_s`) have a tolerance above ten times the
    registered expectation and are failed by no registered plant of their family.
  - AF's excess at the four idle fates has a tolerance above the readout's own size.
- **Two disagreements in bookkeeping, none deciding a verdict:** the judge counts P1″ as caught at AF's eight active-fate
  entries, where no reference distance exists (amendment 4, item 7); and the references' inputs omit three structural
  declarations that SPEC.md §7's "every input" names.
- **What it claims and does not** is the protocol's §2. It is a second registration after a definitional failure, whose
  author had read the diagnosis (D316), so it is weaker evidence than a first-time pass would have been. Nothing about
  biology. FR-38's functional acceptance (D306) stands. FR-38 v3 (the three uncovered readout controls, D354) is open.
- **Disclosed:** the checker went round a harness refusal of `sleep 120` with other waits, until the advisor pointed it out,
  and says no result depends on it. The judge amended two unpushed commit messages earlier in the night. Neither is to be
  repeated.

**The legacy science captures finished clean:** 90 of 90 jobs and 12 of 12 check jobs, 67 MB, in 19 minutes on lane B
(`/mnt/workspaces/Cells/legacy-captures-20261125/`, read-only).

**The pre-rename stack is landed** at 260a9138 (tag `pre-rename-stack-landed-2026-11-25`): docstrings only in ten `src` files,
one fix of an exception's order (a sparse-field refusal), D349's restart row and per-solver view, the legacy capture
tools, FR-51's engine-check script and FR-30's diagnostic. Its gate at 7f54a32c: crossrev 11 of 11, tiers 1 and 2 (671
files, none changed), G1 113 of 113, FR's bitwise set passed; the landing's trial, 182 passed. The per-solver view found
the defect the fix repairs: four live operators were refused with an `AttributeError`, not the intended error.

**FR-54 and FR-57: the registered protocol is tagged** (`liquid-routing-criteria-2026-11-25`, e2b19380; amendment 1 at
915ac820). It was reviewed by the lead and by the advisor (eleven items). The recorded dt study corrected three statements
of the design note: the domain of the default face heat is the lower well's relative change per step, not kh times the
concentration ratio; the 0.08 energy stop is a table by ratio; and the propagator's 4 and 8 eps bounds do not hold at
the note's "up to 10" throughput.
- **The lead's ruling:** version 1 of the router admits a flow only where a node's throughput per half-step is at most 1
  (two residence times per step), refused by name above, and the registered worlds stay at or under 0.625. Below it 657
  networks hold both bounds, and the first sampled failure is at 2. A sub-stepped propagator is the later widening.
- **The order is two snapshots:** arm 6 (a flow beside a face) runs from the landing that lifts its refusal, after FR-54
  passes. The engine gains no declared key for it.
- **The references** are being computed by a code-blind agent from the spec folder alone.

**D358's build is at its gate** (`d358-gate-speed`, 5bb7cdcb). The advisor's first check found that a change to the test
runner itself would have been selected around, and ten runner files now refuse a selection. On a Lean-only change the
selection falls from 484 files and 10,915 test-seconds to 42 and 1,153.

**The rename's hand refactors are built** (`id-rename-hand`, aa2bd2b7; `id-rename-strict`, 9000d5d7). They cover the 45 sites
of D380 and three more that nobody had listed, two of them in the engine: each tests the start of an ID and would have
matched nothing after the move, letting a refused operator order through.
- **The lead's rulings:** 91 further files are declared frozen; `configs/resolved_hcn_extra_ionic.json` is re-spelled
  although a log line pins it; the gate scripts' table option and the fingerprints' go to the tool's builder after D358.

## D382: FR-38's second comparison is landed; D358's map is live; the rename's tool is built, for two landings; the routing spec's amendments 2 to 4; a correction on FR-51's fallback

2026-11-25, about 08:26 UTC. The lead, with the advisor.

**FR-38's second comparison is landed** at 4039dcba (tag `fr38-v2-landed-2026-11-25`): the spec with its six amendments, the
references, the engine side and the judge, with no `src` change. The registered files are byte-identical to the
registration's tag. D381 has the results and what they cannot show.

**D358 is landed** (2c82a048, tag `d358-landed-2026-11-25`) and its map is live. The nightly run on demand at 2c82a048 passed:
671 files, none changed, all 671 traced. The trace found only the two gate-tool files it was expected to find, and
five files have children that are not mapped.
- **The first gate under it** (FR-38's, 955a9dcc): 48 of 672 files and 1,352 of 13,775 test-seconds, 8 minutes in all. The
  readers rule it replaces would have taken 482 files and 10,890.
- **Open for the user:** the 28 readers of `SNAPSHOT.json`, and the wording of D229's rule 3 in AGENTS.md.

**The rename's tool is built, not landed** (`id-rename-tool`, a43beab9: main at 2c82a048, the hand refactors, and
`scripts/id_moves.py` with its choices file; the gate scripts and the fingerprints gain a table option). On rehearsal trees
the move changes 888 files and 7,382 tokens; the verifier finds 0 problems; a second move changes nothing; 21,918 test IDs
are collected on both sides, 194 of them renamed. No hazard stands and no live ID is unplaced. The rehearsal did not
yet include FR-38's folder and is being repeated with it.
- **Two landings (the lead's ruling, after the advisor):** first the hand refactors and the tool with an empty table,
  which changes no value; then, after the user's words, the move, the strict grammar, the rewrap and the docs, each its own commit.
- **The first landing has one addition that is content:** FR-51's block law is registered, with its library page (D371, Q2).
- **The lead's rulings, waiting for the user's words:** the plants' declarations are in the move; the 25 live pages under
  `validation/` are in its docs commit; 932 long lines are left as they are. The choices file marks the family words as
  pending, and the tool refuses to write its table while one is.
- **Order:** the pre-rename tag, snapshot and the legacy captures' bitwise check come after the first landing and before
  the move, so that the captures also check the hand refactors independently. A nightly on demand follows the first landing,
  since it changes two of D358's ten runner files.
- **One ruling is being checked before it goes to the user:** whether the eight example artifacts can be regenerated by
  their own tools. The earlier ruling (declare their outcomes until legacy goes) would carry declared failures on
  main to a date that is not set, and presupposes a legacy route the user has not chosen.

**FR-54 and FR-57: amendments 2 to 4 of the spec are tagged together** (`liquid-routing-amendment-4-2026-11-25`, 49691515). They are
value-silent and change no band. They correct two errors of the spec's author (arm 2's sums, and the scale of an event's own
amount) and state what a judge could not have built from the text: which holders have a mixing heat, where arm 2's
interval starts, what a miss on any stop does, arm 7's registered runs (nothing passes empty), the retry, no-router and restart
runs, the ID echoes and the rehearsal's table.
- **The references are built** by a code-blind agent (`liquid-routing-references`, 35a7d69d): 867 check rows, 605 of 605
  self-check rows, 45 of 45 mutations flagged, and byte-identical under two other hash seeds. They are not tagged.
- **An independent auditor** reads the spec folder alone before the references are tagged and before any judge is built.

**FR-51's external-K fallback: a correction (the advisor's finding).** D380 records, as part of the drafted erratum, that if
the circled 10 stays ambiguous the 10 mM level is not read and is unresolved. Two things were not said. The registration
itself stops if the sheet cannot say which traces are which. And the 10 mM level can only block a pass, so dropping
it makes a pass easier, in a registration that is not blind. The draft stays untagged. The choice is the user's: wait for
Lean's answer, stop, or an erratum that discloses this.

**Disclosed:** the hand-refactor builder asked to remove its 18 scratch trees (3.2 GB), and the harness refused. Nobody has run it,
and it waits for the user. `/mnt/workspaces` is at 93%.

## D383: the user's decisions on legacy, the rename's words and FR-43 part 3: one cleanup branch with one test at its end; the routing spec's audit and amendment 5

2026-11-25, about 10:20 UTC. The user's answers this morning, then the lead's plan for them, with the advisor.

**The user's decisions.**
- **Legacy's route,** verbatim: "Re-express and put everything else on hold and test just once after the re-expression, fine to
  prune in place but we want to get this cleanup done and not run any tests until it's more or less done (so save test time
  by testing many coding things at the same time) - we're still in pre-alpha dev, I'm the only user of Cells so we can
  move as we like". The lead read it back as: one branch, nothing lands, no gate, tier or suite runs until the cleanup is coded, then
  one full test of it all. The user confirmed ("Yes, go").
- **A CPU re-expression of the calcium ensemble counts** as leaving legacy. Its GPU path, which works today at about 1.5 times the
  speed, is parked until a GPU qualification passes. No date is set for one.
- **Four design notes are written now:** calcium-permeant channels, an ER store, IP3-gated release, and assembly topology
  setting channel availability. Each build comes back to the user with a price.
- **While coding, a builder may run the rows it writes or changes,** and nothing else.
- **The rename's words: all 12,** for 16 IDs. `exponential_mean_rate_linear_target_gates@1` is left out of the move, since
  nothing in `src` reads it.

| Family word | Pieces |
| --- | --- |
| `species_reaction` | `ideal_detailed_balance_mass_action@1` |
| `transfer_factor` | `ph_conditioned_factor@1`, `exponential_volume_activation@1` |
| `junction_formation` | `delayed_first_order_junction_formation@1` |
| `damage` | `bounding_patch_damage@1` |
| `regulation` | `hill_regulated_two_state@1` |
| `site_binding` | `langmuir_site_binding@1` |
| `site_internalisation` | `site_conserving_internalisation@1` |
| `fuel_kind` | `maintained_held_rows@1`, `finite_fuel_rows@1`, `maintained_chemical_reservoirs@1` |
| `field_closure` | `resolved_capacitor_components_current_continuity@1` |
| `potential_set` | `beard2005@1`, `beard2005@2` |
| `topology` | `dodecahedron_g10_2@1` |
| `analysis` | `stationary_continuation_analysis@1` |

- **FR-43 part 3's four questions** are accepted as the note recommends (`fr43-part3-cowriters`, c82d8d42): split writers, one judged run with
  code-blind references, part 3 closes at that landing, and the declared general rule. Its spec and references start
  now. Its build waits for the cleanup.
- **The scratch trees** of two finished agents are deleted: 17 under `id-rename-hand-20261125/` and 39 under
  `id-rename-tool-20261125/rehearsal/` (219 to 230 GB free). Logs, scripts and outputs stay.

**How it is run (the lead, with the advisor).**
- **Integration branch `legacy-cleanup`,** from the rename's first landing (43b22d40, at its gate). The order on it: the live side
  without legacy; the deletion, whole; the four features; the re-expressed ensemble; and the ID move last.
- **The move comes last** so that it runs once on a smaller tree, over code that is already final. Two rulings fall away
  with that. The example artifacts leave with the commands they serve, so none is regenerated or declared. And the 48 IDs that were to stay
  bare until legacy's first deletion are in the move, since their dispatch is live by then. D348's single deletion stands;
  the plan's two-deletion route is not taken.
- **"Once" is an order.** The re-expression's criteria are tagged before any re-expressed run. Then come the registered
  qualification against the captures, the user's approval of the removal list, and one full gate with tier 3 and FR's set. Nothing lands
  ungated.
- **What goes on meanwhile:** the first landing's gate, which was already running and gives the final test the table option it
  needs; GJ-N1's field run; FR-43 part 3's spec and references; and closing the routing amendments, after which routing
  holds. Everything else waits, every other queued build included. The cleanup is roughly 30 to 45 agent-days, spread over at
  most seven agents. Main moves by docs and Lean's merges only. No nightly on demand follows the first landing.

**FR-54 and FR-57: the spec was audited before any judge was built.** An independent agent read the spec folder alone, wrote a reader and
honest tables for every registered run, and perturbed them. The numeric core holds: every honest entry passes and every plant is
caught. The text did not: 9 findings that change a verdict, 10 refusals or passes with nothing judged, and 18 places with two
readings. Read literally, an honest engine could not have passed FR-57, and some wrong tables could have passed.
- **Amendment 5** (`liquid-routing-amendment-5-2026-11-25`, 3c71ab61) settles all of them after two re-runs of the audit on the
  amended text. It moves no constant, window, scale or existing count, and states what it changes in classes and in what is judged. The audit's own
  numbers are used for nothing.
- **Two rulings to know:** arm 6 (a flow beside a face) is rehearsed from an unlanded branch before the registration, so that no bound
  moves after a registered run; and a retry can still forgive one wrong coarse run, which the protocol says.
- **Two of the lead's rulings were wrong and are reversed.** An order outside its window with an error above the tolerance was to be a fail.
  FR-25's and FR-38's precedent makes it inconclusive with a retry, and that stands. And "any fault" on an expected stop
  was narrowed by the author, since the stop is itself a refused entry.
- **The references agent,** conforming to amendment 5, found one clause it cannot meet (R8 for a remainder bound at a trace start) and three
  wordings. Amendment 6 follows. Then the references are tagged, and the line holds: no judge is started.
- **Disclosed:** the lead read the references' README layout section and printed key names, no value, to answer the author.
  Eight subagents ran for some minutes, one over the cap.

**Lean's message of last night** (its rebuilt tip, the citation map, the 5.4 mM anchor) was relayed by the user this morning. All of it was done
overnight (D378 to D381): the tip is merged at 18198688, its map is in D378, the docstring cites the new commit, and FR-51's
external-K registration is tagged. The 15 files outside `lean/` that its audit lists hold one published cell line's name in
ordinary citations, and are left as they are unless the user says otherwise.

## D384: the rename's first landing; the cleanup's baseline is tagged and checked; the routing references are tagged and that line holds; what the re-expression map found

2026-11-25, about 10:42 UTC. The lead.

**The rename's first landing** is at 49529e71 (tag `id-rename-landing-1-2026-11-25`). No ID changes. Its gate at 43b22d40: IDs
additions only (26), crossrev 11 of 11 identical, tiers 1 and 2 (672 files, 0 changed), G1 113 of 113, FR's bitwise set passed; the landing's
trial 479 passed.

**The baseline of the cleanup's one test:** tag `pre-cleanup-2026-11-25` at 49529e71, its frozen snapshot under
`/mnt/workspaces/Cells/pre-cleanup-20261125/`. The first steps of every captured legacy world were run again from that snapshot and
compared with the captures of 76a498ae: 12 of 12 jobs identical, bit for bit. So the captures stand at the baseline, and the hand refactors
moved none of these worlds.

**FR-54 and FR-57:** amendment 6 is tagged (`liquid-routing-amendment-6-2026-11-25`, dd21509b) and the code-blind references conform to all six
(`liquid-routing-references-2026-11-25`, fa3eccbd): 867 check rows, 626 of 626 self-check rows, 54 of 54 mutations flagged, byte-identical
under two other hash seeds; every `accuracy` is within its bound (the largest at 0.102 of it); the smallest plant margin is 13.2 on the
registered worlds. The line holds here (D383).

**The re-expression map** (`legacy-port-plan`, a1db6ab9, section 14) corrects the plan and shrinks the work.
- **The sodium-calcium exchanger needs no engine feature.** The plan said the transporter kind refuses a mode that moves charge. It refuses one
  that creates charge. The exchanger is one law module, and the plasma calcium pump is a re-parameterisation of the live one.
- **The calcium-gated opening of the store blocks all four calcium clusters,** not the IP3 one alone. It and the IP3 factor are one per-stage
  factor source on one route, so one note owns the source and the other the route.
- **A calcium row with a channel route on the pump tissue cannot be buffered today.** Either a per-stage bound for channels is added, or
  the channel's gates become a factor source on a passive route. The note weighs both.
- **Four consumers need no new piece:** the JUPITER world, the assembly cluster's base, the assembly cell and the integrated ensemble's world.
  The last has no capture yet and is captured from the baseline.
- **The assembly half is one-way and live already.** An assembly world can be written today as a live pool run whose event path becomes a channel
  schedule. The note weighs that against an operator.
- **The calcium worlds keep their equations and change their integrator** (fourth-order RK4 to a second-order split), so no bitwise
  comparison with legacy is possible for them. The criteria are written and tagged before any candidate run (D383).

**Rulings (the lead):** the live side owns the ensemble families' file, the command line and the ionic list until its merge, with a refusal by
name for the two assembly commands and the two kinds; the manifest's `legacy` key leaves under a new major (`cells.declarations@3`), which also
covers the ID rule the move amends (D371, Q6); and the shared test worlds move to `reaction_transport@1`.

## D385: a review the user relayed, checked: the rename's seam with the cleanup, FR-58's pump question and FR-61 and FR-62; rulings on the calcium store note

2026-11-25, about 11:18 UTC. The lead, with the advisor; the two open points of the review were delegated by the user.

**A review of the cleanup branch and five design notes** was relayed by the user and checked against the branches.
- **The rename's seam with the cleanup: its four points hold,** none a fault of the cleanup branch, all of them due before the move, which runs
  last. Two were known: the tool calls a manifest function that has left, and `cells.declarations@3` is in no kept list. Two are new: three seeds
  of the choices file name constants that have left, and the models' rows now silently override the choice "bare" of the group
  `three_models`, while `catalogue` still says bare. Minting is what D383 decides, so both groups are set to mint explicitly.
- **What follows for the tool:** its whole legacy side leaves, the 11 kept constants whose reason is "read by legacy" are decided again, it refuses a seed,
  path or ID in the choices that is gone or shadowed, and the rehearsal's counts are taken again on the final tree.
- **The manifest's readers,** the viewer's two tools and Lean's `generate_claims.py`, refuse the new major. They are told before the landing. The
  final test does not read the viewer's copy of the manifest.
- **The five notes:** prices and recommendations agree with the notes. A "latent bug" that FR-58's note is said to have found is not one: a species
  listed twice is refused at parse today.

**FR-58's question 2, pump cycles, is ruled by the lead with the advisor:** option (b), a flux-force law carries the label in complete cycles, forward
and reverse, about 1.5 to 2 agent-days more, with a limited claim. The label is a lower bound wherever partial steps of the cycle exchange it, and
any comparison with a measurement of incorporation is one-sided. The note refused these laws "until a study needs it". Two labs' papers on the Na/K pump
running in reverse in red cells are that study: one reports ouabain-sensitive incorporation of labelled phosphate in high-sodium,
potassium-free media (doi:10.1113/jphysiol.1967.sp008298), the other ouabain-sensitive, sodium-dependent potassium efflux
(doi:10.1113/jphysiol.1970.sp009062). Both were read as abstracts and search records only. Incorporation through partial steps at zero net
flux is not what (b) carries. The state-resolved form (the note's (c)) is for diagram laws, and the live Na/K law is
a mass-action cycle, so it would be a new law with sourced step rates: a separate request.
- **What (b) does not reach on its own:** the live pump takes its fuel from maintained reservoirs, not species rows, so the label on ATP needs row fuel
  for the Na/K pump. That is a candidate request, the user's to log, in the order FR-59, row fuel, then FR-58 with (b).

**FR-61 and FR-62 leave the round of "accept the note's recommendations".** The note defers two requested items, the finite-reservoir version
with the capacitor charge at each event (its Q4) and the calibration-range readout (its Q6). Both go to the user singly when those builds come
off hold. The rest of the two requests is in the note. The part of the review that claims scope gaps was not in what the user relayed.

**The calcium store note** (`calcium-store-design`, c5006ff6) measures that a one-cell store world already parses and steps on the composite with two
planted law modules, and prices the missing pieces at 6 to 7.5 agent-days, against the plan's 7.5 to 13. No piece changes the ensemble's
equations. **Rulings, as recommended:** a calcium channel stays a channel population on the pump tissue, its law the one authority for
its ions' valences (L1); one ATP-driven transport law on the transporter kind serves both calcium pumps (L2); the bound on the feedback of a factor
read by what it opens is built (L3); a compartment is admitted where its node is not its component's representative (L4); the door for
buffered calcium rows is for `local_species_reactions@1` alone (L5); conservation is judged by the engine's own ledger rule (L6); no schedules for passive
routes and no non-negative booking for them now (L7, L9); the independent calcium reference is kept (L8). One question goes to the user, the
exchanger's two kinetic forms. The note has had no second reader yet; one is given before its build.

## D386: the user's answers on the cleanup's open questions; the legacy list is corrected against D211; a live stage-bound gap found by the second reader; a correction to D383

2026-11-25, about 13:20 UTC. The user's answers, then the lead's, with the advisor.

**The user's decisions,** "agreed" on each and on the rest as below.
- **The exchanger (A2):** the ensemble's form is registered now, labelled synthetic (only its reversal is supported). Whether it stays beside the cardiac
  plan's law or retires is decided when that law lands.
- **The assembly coupling (A3):** a driver that writes a live pool's switch path into a channel schedule, in `src/cells/assembly_pool`. It is one-way, and no
  claim is made above a few hundred cells. An operator waits for a need.
- **The release factor (A4):** a general source any route or channel can name, after one check that it does not duplicate the live pH source.
- **The assembly observable (A5):** a registered law with an ID and a page, family word `assembly_observable`.
- **The builds (A6)** start in stages: the driver and the exchanger first, then the source, then the calcium core edits. The notes' prices are their authors' own: 7 to 9 days for
  the calcium pieces after the second reader (6 to 7.5 before), 1 to 1.75 for the source, 1 to 1.5 for the driver.
- **What the deletion loses (A1):** the list below, with the cell-zone transporter left at the tag ("leave it") and "yes" to the rest. Final counts are shown before
  the deletion is merged.

**A1 was wrong against D211, and is corrected.** The user asked why the modules on the "lost" list are not ported. Crossed with the cleanup tree, D211's 54
laws stand as: 5 registered; 36 of the 47 "port as is" with their kernels kept in live `laws/`, without a host on the pump tissue; 3 built by name; and 3 that lose their source, the
NKCC and generic symport laws and the cell-zone transporter. The last is BETSE's transporter network, which AGENTS.md bars from `src`. The page had listed
the first two as lost, and had not named D211.
- **NKCC and the generic symport are ported in the cleanup,** as law modules on the transporter kind, after a check of their tanh form against the cycle forms.
- **The other D211 ports follow the cleanup:** the voltage-only sodium and potassium laws need one module each and no engine feature; calcium and HCN
  laws need calcium through channels, which is being built; the instantaneous ones need G-2; the calcium-activated one needs channels that read a
  species, which the cardiac plan holds.
- **Kept for that:** the kernels, their references and a kernel-level test for each, so that no one sweeps them.
- **The rest of the list is lost or not carried over:** the refinement clock (`execution.fine_windows` gives declared finer steps on live models); ceilings on an ion's total (a check, not
  physics); lateral redistribution and mobile proteins; cutting cells out (the composite's operator is new work, named by the pattern-recovery plan); the finite-fuel pools (row fuel for the
  Na/K pump is a request the user may make); the four commands that prepare meshes in BETSE's order; the assembly GPU path, parked.

**A correction to D383 (the advisor's finding).** D383 says the criteria for the re-expression are tagged before any re-expressed run exists. One consumer breaks it: a design author ran
two of the sixteen worlds of the cluster base in composed form against legacy at three steps before the criteria's tag. The protocol names the two worlds, the verdict
reports them apart, and no band rests on them. The lead is not blind either: the lead has read both notes' numbers.

**The calcium and release notes had a second reader** (`/mnt/workspaces/Cells/d172-restructure-20261115-01/second-reader/`): no equation, unit or sign is wrong and no ledger is booked
twice or missed. Sixteen findings are ruled; the notes are being revised.
- **A live-engine gap (row 1).** A stage bound divides a cell's slopes by the capacitance of all its patches, a cell-owned store's included, though a plasma current charges
  the plasma patches alone while the store floats along (`surface_pump_v3.py:3674`, `surface_pump.py:487`, `transporter.py:2330`). A probe at 3.3 times the store's share admits a step
  the membrane cannot take, and the run stops at the domain or the energy ledger. It is not silent, and no JSON world of today exceeds 0.67. The fix is one D148 round,
  first, with a scan of the Python-built compartment worlds behind FR-1, FR-4 and FR-5; a hit is a recorded erratum.
- **The driver is legacy's model:** pool end states bit for bit over four worlds, with step boundaries at the switch times (legacy also splits where nothing switches).
- **The rule for which worlds declare the other field solver is D147's** and not "every world": the lead's first ruling was too broad.

**Two parsers scaled a shared junction schedule in place** (`surface_pump_spec` and `surface_kinetic_spec`): a Python-built definition that used one schedule object for several controls had the others scaled too. Fixed on
the cleanup branch with a row that fails on the old code. A static scan of 92 files found no built definition that shares one, so no judged run is known to be affected.

**The removal list** (stream A) was read past its first hop: 246 files reach a going file by import, bare-name import or path, and ten live parity tests use part of the REF-era chain, one of them
(`test_betse_tissue_contact.py`) in every gate. Those files stay. The rule is to keep whatever something in use runs; the final list and counts follow.

**Streams merged into `legacy-cleanup`:** the live engine without legacy (the deletion itself is held), the live tests on live worlds (window and batch-window tests at 75 and 171 CPU seconds, from 162 and 411), the two
fixes. The rename's tool is fitted to the cleanup tree, and minting the catalogue leaves no ID bare. FR-43 part 3's registration is written and an independent auditor reads it before its tag.
Eight agents ran for some minutes, one over the cap.
