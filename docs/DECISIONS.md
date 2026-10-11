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
