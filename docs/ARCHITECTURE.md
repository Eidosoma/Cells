# Architecture

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

## System shape

Build one headless Python library. JAX executes numerical kernels on CPU first
and GPU later. Experiments, analysis, and a viewer use the same simulation
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
padding, and shape-aware checkpoint/resource checks; passive_pair@1 still accepts
exactly two active cells and one contact. CORE-003 adds species-by-cell amounts,
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
evolving during prescribed transport block. This is implemented as
[bioelectric_pair@1](BIOELECTRIC_PAIR.md) in D023. The
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

The bounded CPU profile now separates compilation, warmed execution, host work
and storage. It shows no universal batch speedup: graph batches help at the
largest tested count, while nominal pairs have no overall gain there. Full
histories, host work and output remain visible costs. CORE-005a/D028 adds
[single-world windows](WINDOWED_EXECUTION.md), with a lazy exact grid, every
ordinary interval/observer check, complete ledger/state continuity, and
incremental selected recording. It bounds retained arrays, not biological work
or whole-process RSS. CORE-005b/D029 applies the contract to
[independent cohorts](WINDOWED_WORLDS.md): each execution round consumes each
world's own existing intervals, with prepared parameters, active masks and
compiled widths reused. A complete cohort checkpoint maps independent local
clocks; it is not a simultaneous organ state. Per-world observers still check
ordinary host results before any round is exposed. Vectorized failure guards,
multi-device semantics and biological exchange still require qualification.

JAX is the shared execution framework. GPU readiness requires checking compiled
control flow, allocation, reductions, random semantics, and device-resident state;
changing the device alone is not a performance guarantee. Keep state on the device
across many steps and transfer selected observations or checkpoints in batches.

Measure compilation separately from warmed execution, synchronise device work
before recording elapsed time, and report both end-to-end experiment throughput
and kernel timings. Early comparisons cover small relay ensembles, a coupled 2D
graph, and later changing-population events. No GPU model or speedup is assumed.

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

## Technical references

- [JAX compilation and functional constraints](https://docs.jax.dev/en/latest/notebooks/Common_Gotchas_in_JAX.html)
- [JAX JIT compilation and changing shapes](https://docs.jax.dev/en/latest/201/jit.html)
- [JAX float64 configuration](https://docs.jax.dev/en/latest/default_dtypes.html)
- [JAX explicit state](https://docs.jax.dev/en/latest/stateful-computations.html)
- [JAX structured array state](https://docs.jax.dev/en/latest/101/pytrees.html)
- [SciPy integration reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)

These references informed the initial design review. Exact supported versions
and target-device compatibility will be checked when the environment is pinned.
