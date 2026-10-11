# Multiphysics, multiscale and parallel execution architecture

2026-09-09, D045 / ARCH-003. Target design for the
[BETSE capability roadmap](BETSE_CAPABILITY_ROADMAP.md). This refines the
[existing multiscale design](MULTISCALE_DESIGN.md); it does not implement a new
solver, spatial model, GPU backend or distributed runtime.

## Five separate decisions

```text
Biological definition: mechanisms, compartments, geometry, organ ports
    -> Operator/boundary graph: who owns state and exchanges what
    -> Resolution plan: detailed cells, coarse regions, declared closures
    -> Numerical plan: coupled methods, clocks, tolerances, exchange stages
    -> Placement plan: CPU/GPU devices, partitions and communication
```

All five identities belong in a run manifest. The organ is data selecting
implemented mechanisms and wiring ports, not a solver branch. Organ membership,
physical connectivity, numerical resolution and device ownership are distinct
maps. One organ can span GPUs; one GPU can hold several organs or resolutions.
Changing a device must not silently change physics, precision or resolution.

Keep Python for assembly, validation, experiments and orchestration, and JAX
array kernels for the primary CPU/GPU path. Do not promise that one JAX function
or one explicit timestep will efficiently solve every future mechanism. A
specialized field/linear solver may be an independently qualified backend block
with explicit array residency and transfer costs; adopting one needs a concrete
fixture, not a new mandatory framework now.

## State ownership and geometry

| Entity | Owns | Must not be conflated with |
| --- | --- | --- |
| Species definition | Stable identity, valence, units, compartment eligibility | Hard-coded Na/K/Cl indices or an implicit charge-repair ion |
| Compartment | Amounts, declared volume and any dynamic resource/buffer state | A cell name, observer phenotype or maintained reservoir |
| Membrane surface | Endpoints, geometry, capacitance, channel/transport state | Cell volume, contact adjacency or experiment-imposed inhibition |
| Contact/transport edge | Endpoint mapping, route law and owned transfer history | A duplicated pair simulator for each neighbour |
| Field mesh | Cell volumes/faces, geometry, boundary conditions and field-owned inventory | One mandatory field node per biological cell |
| Mechanics/lifecycle | Position/shape/volume laws, topology events and partition rules | Moving array slots or arbitrary duplication of concentrations |
| Solver/execution | Required method state, coupled clock, events, random streams and pending exchanges | Biological inheritance or an observation-only snapshot |

Use structured arrays/PyTrees grouped by compatible model family and capacity.
Compartments, species, surfaces, edges and field sites have independent axes and
stable IDs. No dense all-cell connectivity matrix is required. Padding is finite
and mask-safe, and overflow is a checked checkpoint/reallocation boundary.
The current explicit model registry and CPU-only schemas are not already a general
assembly API; add exercised contracts incrementally and preserve their old versions.

Amounts are primary where the model represents material. Derive concentrations
from amounts/volumes; changing volume requires the correct dilution and transport
terms. A chemical species, a fixed charge background and a maintained external
countercharge have different ownership and costs. State-changing reactions must
declare their stoichiometry and any externally supplied matter/energy.

Electrical closure belongs to a named physical model. The existing one-cell
affine voltage anchor is valid for its fixed-capacitance, fixed-potential bath.
Multiple facing potentials, electrode currents or evolving membrane capacitance
require a newly derived constraint/charge law. Do not copy that anchor to each
surface or evolve both voltage and charge independently without a constraint.
Geometry changes must account for any modeled capacitive/mechanical work.

D055 / [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md) adds a design/reference for one
shared finite outside, not a production field solver. One outside inventory
collects equal/opposite transfers from all membranes. With no junctions, cells
sharing that outside are still coupled through chemistry; they cannot be put
into independent-world slots. Each true independent world owns a separate outside.
For a later partitioned world, exchange the current solver-stage outside state
and reduce owned membrane transfers exactly once. Do not integrate private
outside replicas per GPU or count junction transfers in that reduction.
This reduction is an explicit communication dependency, not a measured scaling
result. Spatial compartment refinement may localize it later, but changes the
mixing/electrical approximation and needs separate convergence evidence.

D057 / [NUM-009 v2](FINITE_EXTRACELLULAR_NUMERICS_V2.md) separates physical inventory
from its anchored numerical representation. Initial amounts are immutable;
inside and outside increments are complete checkpoint-relevant state, not
transfer histories or a reason to reanchor partitions independently. The
implicit references and candidate all evolve every inventory explicitly.
Conservation-tangent Jacobian probes are a CPU reference linearization, not
state projection or a distributed algorithm. The original dependent-outside
reference remains a retained failed attempt. Future device placement must
preserve the candidate's same-stage conservative outside reduction and exact
inactive-inventory behavior, not absorb roundoff into a designated compartment.

D058 / CORE-009 now supplies the [CPU/JAX finite-outside implementation](FINITE_EXTRACELLULAR.md)
and [formal execution evidence](../reports/CORE009_ACCEPTANCE.md). Outside state,
anchors, volume and owner indices are independently padded numeric arrays, and
each independent cohort world retains its own complete outside state. Existing
scalar/cohort clocks and restart semantics are reused. No distributed runtime
or CPU-to-GPU speedup follows from this: splitting one coupled world still
requires same-stage reductions and synchronized outside state. The next spatial
contract must define extracellular potential constraints as well as transport;
several independent zero-potential baths would change the physics.

D059 / [SPEC-009](SPATIAL_EXTRACELLULAR_SPEC.md) now defines that first spatial
closure at the design/instantaneous-reference level. A membrane-capacitance graph
sets charge differences within its components; extracellular current continuity
sets their relative potential offsets. A membrane-free bulk node needs no fake
capacitance. The field block therefore has its own graph, gauge, residual budget
and solver/cache contract, distinct from the compartment inventory and transfer
ledgers. The passive first subset gives a sparse gauge-fixed linear problem at
each admissible state; more general cross-component transport can make it nonlinear.

Future distributed execution must exchange same-stage concentrations and
potentials, accumulate each interface flux once and qualify the coupled solve's
reductions/preconditioner. Independent-world batching cannot partition this one
interacting environment. Coarser geometry and faster hardware must not silently
change its electrical closure. Dense reference matrices, a passing arithmetic
panel and the existing 1 ms finite-outside step are not a spatial/GPU solver
qualification. [NUM-010](../reports/NUM010_REFERENCE.md) now provides the separate
bounded CPU numerical result: 0.125 ms with 0.0625 ms refinement on its panel,
not a GPU or arbitrary-resolution bound.

The [NUM-010 protocol](SPATIAL_EXTRACELLULAR_NUMERICS.md) treats temporal resolution,
spatial resolution and device placement as separate choices. Its 8/16/32-volume
line panel tests one finite-volume refinement path; it does not qualify all meshes.
Finer diffusion grids can require smaller explicit steps, even on a faster GPU.
Do not encode the selected reference step as a universal physical timescale.

Future GPU work should preserve independently sized inventory, membrane and
outside-face axes, once-owned flux accumulation and same-stage field residuals.
The small dense field solve and dense conservation-tangent implicit Jacobian are
reference techniques, not scalable kernels. A sparse or matrix-free field solver,
and any later implicit/IMEX or multirate evolution, must qualify their own coupling,
conservation, observation and restart behavior against this baseline. Device
placement alone cannot remove stiffness or a coupled field-solve dependency.

D061 / [CORE-010 development integration](SPATIAL_EXTRACELLULAR.md) now makes
that separation executable for the passive subset. Checkpoints store independent
cell/outside/membrane/face axes and sparse edge ownership; the explicitly named
`gauged_dense_kirchhoff@1` block uses quadratic temporary CPU workspace included
in pre-allocation scalar/cohort/window guards. No dense matrix, solver warm start
or additional hidden state is persisted. Existing JAX cohorts batch independent
worlds, not pieces of the same tissue. This bounded implementation is a baseline
for later sparse/matrix-free backend qualification, not a large-GPU scaling result.
Full captured production acceptance remains open.

## Small operator contracts, not a universal plugin runtime

A process declares the state it reads, the outputs or fluxes it owns, units and
signs, validity limits, required physical capabilities, and numerical needs.
Local reaction rates, membrane transfer, graph exchange, field transport and
algebraic constraints are different operator kinds. They can contribute to one
coupled state without all becoming arbitrary Python callbacks inside a hot loop.

Each physical transfer is calculated once and accumulated with opposite signs
at its endpoints. Convert amounts to concentration changes only with the
appropriate compartment volume. Charge current follows the declared species
fluxes and valences, plus separately modeled electrode/displacement/gating
currents where applicable. A ledger records transfer history, not extra matter.

Source-scaled EMT coordinates do not become physical ion amounts through a
generic field mapping. Adapters need explicit units, clock meanings and tested
approximations. Observers can inspect global state for analysis but cannot
silently provide nonlocal information to a biological process.

## Fidelity and resolution are explicit capabilities

Support named model families rather than an undocumented global "fast" flag:

- Conditioned endpoint relations can answer only their declared static queries.
- Dynamic lumped ionic compartments own amounts, voltage closure and fluxes.
- Spatial membrane/field models add polarization and environmental gradients.
- Reduced tissue/organ regions own their explicit coarse state and closure.

BIO-002, for example, cannot supply ionic flux or hidden gate history merely
because it predicts voltage. A reduced region can connect to a material port
only if its closure defines that port and accounts for the exchanged inventory.
Refuse unsupported observations, controls and couplings rather than inventing
the missing state.

Start fine/coarse coupling with **static region assignments**. Restriction maps
aggregate amounts, volume and relevant slow/history state; prolongation specifies
what can be reconstructed and its uncertainty. Coarse concentrations alone do
not uniquely recover hidden channel, regulatory or inheritance state. Adaptive
refinement/derefinement requires its own state-transfer and hysteresis/error
policy. Memory preservation is tested by future interventions, not just by
matching the current mean phenotype.

## Coupled numerical execution

Retain a common-step detailed reference before introducing multirate updates.
Candidate methods include explicit local stepping, implicit stiff blocks,
implicit-explicit splitting and field/pressure solves; no package or universal
method is selected in this design. Each block specifies its domain checks,
error target, dense-output/event semantics, constraint residuals and restart
requirements. Fast electrical dynamics cannot be assigned a larger timestep
just because the calculation moves to a GPU.

One interacting world has a coordinated physical timeline. Independent worlds
may retain their separate clocks. A coupled macrostep must:

1. Resolve the next intervention/topology event and the participating blocks.
2. Exchange the endpoint/stage data required by the selected method.
3. Evaluate local and interface operators, including any necessary global solve.
4. Reconcile integrated interface transfers and validate the candidate state.
5. Commit a common valid boundary, then publish requested observations/checkpoints.

For explicit RK coupling, halo exchange must match the required RK stages, not
just the output or recording window. For an implicit solve, communication and
constraint checks may occur during each iteration. Freezing neighbouring state
over several substeps is a numerical approximation to qualify, not a free
parallelization trick.

For multirate/fine-coarse interfaces, declare interpolation/extrapolation, flux
quadrature and synchronization intervals. An owned flux register can retain the
same integrated transfer for both sides; corrections must not conceal negative
inventories or failed intermediate states. Conservation is necessary but does
not establish temporal accuracy or stability. Refine both local timesteps and
coupling intervals against the common-step reference.

## Parallel GPU execution: three different workloads

| Workload | Partitioning | Required communication |
| --- | --- | --- |
| Independent experiments | Whole worlds across devices; compatible worlds batched within each device | Dispatch/results, no biological exchange between worlds |
| One interacting tissue/organ | Spatial cell/edge/mesh partitions within one world | Halo/stage values, single-owned boundary transfers, constraint reductions and field solves |
| Coupled organs | Organ ports plus whichever spatial partitions each organ needs | Conserved port transfers and shared transport/field dynamics on the coupled clock |

Independent-world mapping in Cells 0.10.0 is not evidence for spatial multi-GPU
execution. Nor should an interacting organ be forced onto exactly one GPU.
Use a partition ownership map with read-only ghost entries, deterministic edge
ownership and no double-counted flux at cross-device contacts. Model-family
buckets allow heterogeneous kinetics without one Python call per cell.

Candidate JAX mechanisms are device meshes and explicit array sharding for
placement, with `shard_map` where explicit per-partition collectives are useful.
These are implementation candidates, not a promise that JAX automatically finds
our tissue decomposition or supplies a distributed PDE solver.
[Distributed arrays](https://docs.jax.dev/en/latest/sharded-computation.html),
[manual parallelism](https://docs.jax.dev/en/latest/notebooks/shard_map.html).

Multi-host operation comes after a single-host multi-GPU fixture. Participating
processes must execute compatible collective operations in the same order;
failure/rejection decisions cannot leave peers waiting in a different branch.
Distributed initialization, rank/device discovery and shutdown are execution
concerns, not biological state. Exact APIs and hardware support must be checked
against the eventual pinned deployment environment.
[JAX multi-controller guidance](https://docs.jax.dev/en/latest/multi_process.html).

Fields and incompressible flow may require nonlocal linear solves and global
reductions even when cellular interactions are local. Prefer sparse/matrix-free
operators and evaluate suitable preconditioning; do not assume a dense inverse
or all-gathering the entire world will scale. Communication, imbalance and
solver iterations belong in the cost model.

Keep state device-resident across bounded stepping windows where practical.
Host interaction handles scheduled structural changes, bounded data transfers
and output. Dynamic growth/repartitioning happens at declared safe boundaries
with identity-preserving migration and possible recompilation, not arbitrary
shape changes inside one compiled kernel. No asynchronous stale-halo mode is
enabled by default.

## Precision, randomness, failure and restart

CPU float64 remains the reference. GPU precision and each operator's tolerance
must be qualified; reductions may change rounding order across devices. Require
bounded scientific/numerical agreement, not universal bitwise cross-device
trajectories. Current exact-replay guarantees keep their original scope.

When stochastic models are introduced, derive streams from stable world/entity
IDs, process identity and declared logical sample/event counters, not device
rank or reusable slots. Repartitioning must not create a new biological noise
history. Adaptive stochastic timesteps require their own consistent path scheme;
ID-based keys alone do not solve that problem.

A complete checkpoint includes primary biological state, slow/history state,
geometry/topology, control clocks, pending transfers and required solver state.
Parallel publication needs a common committed epoch across all partitions;
uncommitted shards are not a resumable world. Retrying, resharding and changing
resolution have explicit policies and identities. Conservative redistribution
cannot be relabeled bitwise replay. Restart portability and distributed fault
tolerance remain future deliverables.

## Qualification before scale claims

- Recover existing small-model limits without changing their saved versions.
- Compare local operators and coupled CPU trajectories with independent references.
- Check disconnect, block/release, boundaries, conservation and required energy laws.
- Vary timestep, mesh and coupling interval separately; test fine/coarse responses.
- Compare unpartitioned and partitioned one/pair/star/field fixtures, including
  an edge crossing a partition and a field source on an interface.
- Test topology/ID permutation, complete restart and all-partition failure handling.
- Measure one GPU, multiple GPUs and then multiple hosts at equivalent accuracy;
  report strong scaling (fixed total problem) and weak scaling (fixed work/device).

Budget active and padded state, solver scratch, field/preconditioner storage,
halos, compilation, transfers, diagnostics, output and checkpoints. Report
end-to-end time alongside kernel time. No speedup, whole-organ capacity or
hardware purchase is inferred from this design.

## What happens now

The [SPEC-005 contract](MULTISPECIES_MEMBRANE_SPEC.md) and
[instantaneous reference](../reports/SPEC005_DESIGN_CHECK.md) are now complete.
[NUM-006 now qualifies short trajectories](../reports/NUM006_REFERENCE.md) with
independent methods, explicit event/observation checks and retained dense data.
CORE-006 now implements the [first production assembly](MULTISPECIES_MEMBRANE.md),
with [bounded acceptance complete](../reports/CORE006_ACCEPTANCE.md). The existing
model identities and regression results are preserved while the new assembly
exercises the smallest species/compartment/membrane interfaces. SPEC-006's
[two-gate channel reference](VOLTAGE_GATED_CHANNEL_SPEC.md) now passes separate
analytic and instantaneous checks; that reference alone adds no production channel. NUM-007 now
[qualifies coupled gate/amount dynamics](../reports/NUM007_REFERENCE.md) at
0.5 ms RK4/cubic with passing refinement, full state/history and domain checks.
CORE-007 now implements a [state-bearing channel family](VOLTAGE_GATED_MEMBRANE.md),
with [complete replay/cohort acceptance](../reports/CORE007_ACCEPTANCE.md). The additional numeric channel
extent enters model-owned memory estimates and cohort compatibility before
allocation. Subsequent solver, field,
reduction and GPU stages each need an actual fixture. Design for those stages
now; do not implement placeholder organ hierarchies or a distributed framework
to run the first cell.

SPEC-007 now provides a [physical ionic graph contract](PHYSICAL_IONIC_GRAPH_SPEC.md)
and [passing scalar composition checks](../reports/SPEC007_DESIGN_CHECK.md).
Shared-recipient stars exercise the distinction between one local cell operator
and several edge contributions. The edge map stays sparse, with separate gate,
transfer and dissipation arrays. Future partitions must exchange matching solver
stage values and reconcile single-owned interface transfers; numeric reduction
order and restart policy need their own GPU qualification.
[NUM-008 now qualifies short coupled graph paths](../reports/NUM008_REFERENCE.md):
2 ms RK4/cubic with passing 1 ms refinement on twelve fixed cases, explicit
control splits and complete interface history. This is a shared-stage numerical
baseline for the [CORE-008 production graph](PHYSICAL_IONIC_GRAPH.md), not a
multirate or distributed solver. The new family composes existing physical
operators with sparse endpoint gather/scatter and independently padded channel/
junction histories; CPU acceptance uses the ordinary scalar and cohort paths.
No device placement or solver infrastructure is introduced solely for this graph.
Larger degree,
stronger coupling, smaller capacitance and coarser region boundaries require
their own stability/accuracy qualification before device placement or speedup claims.
