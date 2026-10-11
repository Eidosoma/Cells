# Multiscale composition and organ definitions

Scope reviewed: **2026-10-11**. This document defines composition, ownership and
future organ interfaces. Current cell, spatial-tissue, calcium and assembly
families exercise parts of these contracts; they are not a general organ or
adaptive multiscale implementation. [Progress](../PROGRESS.md) records their
verification, and the [model index](README.md#models-and-execution) locates the
versioned guides.

Selected families run on CPU and L4. Independent-world GPU scheduling and offline
Jupiter planning are described in [GPU execution](GPU_ENSEMBLES.md). Splitting one
interacting tissue across devices, conservative fine/coarse reduction, coupled
multirate stepping and organ validation need additional implementation and evidence.
The [parallel architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md) describes those
requirements. Earlier build notes are preserved at the end of this document.

## What is data and what is code?

An organ is a versioned model definition: geometry, cell populations, process
choices, parameters, initial conditions, internal connections, external exchange
interfaces, and requested measurements. It is not a special branch in the engine.
An experiment places one or more such definitions in a world and supplies a
schedule, external conditions, numerical settings, and output policy.

Configuration selects and connects implemented, versioned mechanisms. A genuinely
new reaction law, mechanical model, or transport mechanism still requires code,
tests, and a model revision. A name or parameter file cannot supply missing physics.
Do not embed executable expressions or arbitrary imports in configuration.

Keep three concerns separate:

| Concern | Contains | Example |
| --- | --- | --- |
| Model definition | Components, processes, parameters, units, coupling, geometry | A cell model or reusable tissue/organ preset |
| Experiment definition | Initialisation, challenges, external support, observers, horizon | A pulse-and-release assay on the selected model |
| Execution settings | Backend, precision, solver, capacities, output paths | The same model/assay run on CPU or GPU |

Save the fully resolved definitions, schema versions, and model-code identifiers
with each run. Units and dimensions are validated before numerical execution.
Changing backend must not silently change biological parameters or resolution.
The [BETSE review](BETSE_DESIGN_REVIEW.md) reinforces a further distinction:
physical approximation belongs to the model, not the solver or device. A
circuit-only approximation must declare that it lacks ionic/field state and
reject incompatible requests; it is not an undisclosed acceleration option.

## Composition and connectivity

An illustrative future world has the following ownership structure:

```text
World
  organ instance A
    tissue regions -> cell populations + local fields
  organ instance B
    tissue regions -> cell populations + local fields
  shared transport compartments and explicit connections
```

This hierarchy organises configuration, geometry, and reporting. Physical and
functional connections form a separate graph and may cross ownership boundaries.
Membership alone never creates signalling or material exchange. A first-build
world contains just a cell population of size one and a prescribed external input;
it needs no empty organ objects or artificial intermediate hierarchy.
The passive pair adds one explicit exchange route in that same world; CORE-003
extends this to data-defined fixed graphs with two reactive species. Neither
requires an organ wrapper or treats connected cells as independent replicates.

Distinguish two meanings of multiple:

- Independent worlds are experimental replicates, with no physical exchange.
- Multiple organs in one world interact through declared couplers and share a
  coordinated physical timeline. They are not independent batch entries.

Biological IDs, component-instance IDs, ancestry, and numerical storage slots have
separate meanings. Reusing a template creates independent instance state. Changing
a reporting group must not move a cell or alter its dynamics.

## Minimal contracts, implemented when first exercised

These names describe responsibilities, not a required class hierarchy or plugin
framework. Use small Python definitions and pure numerical functions initially.

| Contract | What it declares | First use |
| --- | --- | --- |
| Model/component specification | State fields, units, initialisation, parameters, model version | M1a, one cell |
| Process specification | Allowed inputs, owned outputs or tendencies, domain, update rule | M1a, source and decay |
| Port/coupler specification | Quantity, units, direction, endpoints, exchange law, accounting | Named external input in M1a; passive contact in M1c-a; species-specific graph exchange composed with local reactions in CORE-003 |
| Biological boundary specification | What is retained, partitioned, reconstructed, erased, or external | Defined now; implemented with transfer/division assays |
| Observer specification | Read access, coordinates, scale, sampling, definition and calibration | M1a, amount/concentration trajectory |
| Resolution mapping | Fine/coarse state relationship, closure, invariants, validity range | M6, after a detailed tissue reference exists |

Processes receive only their declared state and inputs. They return tendencies,
fluxes, or proposed events; a documented scheduler combines these without hidden
module-order dependence. Multiple contributions to one state field require an
explicit accumulation rule. Topology changes and material partition are events,
not silent side effects of measurement.

CORE-003 exercises this rule: a local conversion and graph flux return separate
amount contributions evaluated at the same RK stage. The composition model sums
them and keeps separate signed ledgers for local and exchanged amounts. Host-side
field/identity mappings and independent contact controls are explicit. This is
a small tested composition path, not a process plugin system or organ-port API.

D018's [physical cell](BIOELECTRIC_CELL.md), now implemented as MODEL-003, exercises a second kind
of interface: a membrane with its own area/capacitance, owner-cell mapping,
and facing bath. It starts with prescribed bath conditions and explicit external
exchange/chemical support. Later finite reservoirs and spatial extracellular
fields must own their state and charge closure; the bath must not become an
unrestricted global variable. Multiple surfaces can eventually face different
compartments, but that extension needs new physical and numerical validation.
Endogenous gate state is distinct from physical adjacency and imposed controls.

Fast activity, slow regulatory state, and changes in responsiveness can have
different process rules and update rates. The initial model need not contain all
of them. Model family and initial cell-type configuration are distinct from a
phenotype label inferred by an observer.

## Spatial and temporal scales

Support different representations through explicit adapters rather than pretending
that every level is the same kind of object:

- A well-mixed cell uses lumped intracellular variables first. Subcellular spatial
  compartments are a later option if the question requires them.
- Contacts couple cells through a graph; extracellular fields occupy their own
  grid or mesh, which need not align one-to-one with cells.
- Tissue and organ regions can use detailed cells, continuum fields, lumped
  compartments, or validated reduced models.

Geometry records its dimension and coordinate frame. The first cell has no shape
solver; a later 2D fixture must not make 2D an engine-wide assumption. Add 3D
geometry only with an actual 3D fixture and numerical checks.

Use one physical time coordinate per coupled world, with named process rates and
synchronisation points. Couplers specify sample/hold or interpolation semantics,
exchange intervals, and any delays. Pending transfers, delay buffers, and solver
history belong in checkpoints when they affect future evolution. Physiological
time, cell age, lineage count, and observation time are distinct coordinates.

Coarse-to-fine and fine-to-coarse exchange must conserve the declared quantities
and avoid counting the same material twice. A reduced representation needs a
closure model and tests of future response, including relevant history effects.
Matching an average phenotype or steady state alone is not adequate validation.
Automatic adaptive resolution is not an initial implementation requirement.

## Organ-to-organ exchange

Later organ definitions expose typed boundary ports. Depending on the selected
physics, these may exchange amount per time, fluid flow with concentration,
electrical signals, or mechanical loads. A concentration is not itself an amount
flux. Non-material signals need explicit semantics rather than a fictitious mass
conservation check.

A shared circulating or transport compartment is an explicit model with its own
volume, state, dynamics, and source/sink accounting. It is not a free global
variable readable by every cell. External reservoirs and imposed signals remain
labelled external support. No circulation, endocrine, neural, or fluid model is
selected merely by reserving these interfaces.

Before biological multi-organ claims, test two small generic compartments:
disconnecting their link must remove exchange, closed-system amount accounting
must balance, and changing a port must affect only the declared routes. These are
coupling tests, not evidence that a real organ has been reproduced.

## Research safeguards across scales

A numerical checkpoint restores the complete world. A biological boundary passes
only the state allowed by its model. Division, transplantation, fragmentation,
and replacement have different boundary specifications; the AI experiments'
hard-reset convention is not a default cell-division law.

Observers may inspect more than a biological mechanism can sense. Observer
outputs do not feed back into the model unless an explicit controller declares
that access, actuation, and cost. Likewise, communication access and permission
to modify slow memory state need not be identical.

Track expression, transport, reading, and successor writing separately where a
model contains those mechanisms. A useful measurement decoder does not establish
that cells can use or renew the information. Preserve correct/wrong-recipient,
reader-off, writer-off, passive-copy, and reconstruction controls when relevant.

## Execution boundary

Resolve configuration and component wiring on the Python host. Numerical state
uses array blocks grouped by compatible model and capacity; avoid invoking a
Python object method for each cell at every numerical step. Keep static structure
separate from changing state, and specialise numerical kernels for the selected
configuration. This follows JAX's documented treatment of
[explicit state](https://docs.jax.dev/en/latest/stateful-computations.html) and
[structured array containers](https://docs.jax.dev/en/latest/101/pytrees.html).

Changing model structure, array shape, or static arguments can require new JAX
compilation. Configurability does not imply arbitrary structural changes inside
one compiled loop. Handle those changes at declared host boundaries, preserving
state and provenance. See the
[JIT compilation contract](https://docs.jax.dev/en/latest/201/jit.html).

CPU/GPU agreement is tested at each new scale. Independent ensembles already
have a GPU scheduling path; Jupiter execution remains to be qualified. Domain
decomposition of one interacting world requires additional state ownership,
communication and numerical checks. Device count does not establish organ capacity.

## Future note: computational multiscale and large GPUs

Added at the user's request on 2026-09-07. This is a future architectural
requirement, not an instruction to build an accelerator framework during M1a.
Biological scale labels alone do not reduce computational work. Plan for three
independent numerical choices, recorded in each run:

| Choice | Future approach | Required scientific check |
| --- | --- | --- |
| Spatial resolution | Detailed regions coupled to coarser fields/compartments | Mesh/region refinement, interface flux balance, boundary artifacts |
| Temporal resolution | Fast local dynamics subcycled within slower process updates | Coupling-error refinement, event timing, delay and stability checks |
| Model fidelity | Detailed intracellular dynamics in selected regions; validated reduced state elsewhere | Held-out responses, memory/commitment retention, valid range of reduction |

These choices are separate from hardware placement. A GPU can run several
resolution levels; an organ need not be assigned one device, and one large
organ may later span devices. Begin with static region/resolution assignments.
Adaptive promotion or demotion needs conservative state-transfer rules, retention
of relevant hidden history, and accounting for any reconstruction cost before it
becomes a scientific mode.

Candidate implementation techniques, to select by profiling, are spatial
tiles/partitions with local contacts and halo exchange; model-family/capacity
batches; device-resident integration over many steps; bounded observation buffers;
and explicit communication phases for coupled regions. Spatial decomposition of
one interacting world is different from distributing independent replicates.
Long-range fields, global solves, and inter-organ transport can still impose
global work; they need their own solver and communication measurements.

Before choosing a large-GPU or multi-GPU path, budget state and scratch bytes
per active cell, edge, field site, and retained checkpoint. Measure active versus
padded work, compilation, compute, device transfers, inter-partition exchange,
output, and end-to-end throughput. Precision can be selected per numerical block
only after validation; float64 remains the reference. Raw GPU capacity or cell
count does not establish organ-scale feasibility or biological accuracy.

The implementation preserves explicit array state, separate numerical and
biological contracts, dimensioned inputs, stable identities and bounded recording.
Spatial and resolved-tissue models add field and membrane ownership; assembly
coupling adds complete stochastic event state. These are useful prerequisites,
not a validated fine/coarse biological interface. Memory plans must also include
compiler caches, process overhead and communication buffers.

Adaptive meshes, coupled multirate stepping and distributed interacting state
remain further work. The current Jupiter target is up to sixteen GPUs, beginning
with qualification on one four-GPU node. Mixed precision requires separate
numerical checks; it is not implied by that hardware target.

NUM-002 supplies the first physical-cell [time-scale evidence](BIOELECTRIC_NUMERICS.md):
fast electrical and much slower ionic modes in its synthetic reference. Its
interpolation checks also distinguish output accuracy from accepted-step
accuracy. These support separate solver/output budgets and later validated
multirate or stiff methods, not an immediate GPU or distributed implementation.

## Selecting the first organ later

The user's preference is the simplest useful organ target, eventually selectable
as data. No named organ is selected yet. Prefer a target with a small necessary
set of cell/process families, simple geometry, available validation evidence,
explicit external dependencies, and one measurable organ-level function.

Record species, developmental stage, represented extent, omitted physiology,
resolution, and validation task. A small tissue patch, organoid, or arbitrary
cell cluster is not automatically a whole-organ model. Success means reproducing
the selected organ function within a stated scope, not simulating every molecule
or all physiology. The same definition mechanism must allow more than one organ
instance without a fork of the engine.

## Historical implementation notes

These baseline notes preserve the scope of their original September versions.
Their future-work statements are historical; current evidence lives in Progress.

Design direction: 2026-09-07. Start with one cell; support tissues, a whole organ,
and eventually interacting organs through the same modular architecture. This
document specifies extension contracts. Version 0.14.0 retains the one-cell
fixture, isolated regulation, passive two-cell contact, and local-reaction/transport
composition on data-defined fixed graphs, plus a [physical membrane/bath cell](BIOELECTRIC_CELL.md)
and a [gated physical pair](BIOELECTRIC_PAIR.md), plus a separately typed
[nominal source-compatible EMT pair](SOURCE_EMT_PAIR.md), and adds a
[multispecies membrane family](MULTISPECIES_MEMBRANE.md) and
[state-bearing membrane channel](VOLTAGE_GATED_MEMBRANE.md), with a separate
[physical ionic graph family](PHYSICAL_IONIC_GRAPH.md) for communicating cells.
It adds a distinct [finite extracellular family](FINITE_EXTRACELLULAR.md):
one shared outside inventory with explicit membrane ownership, not a private
bath copied into each cell.
It retains [independent-world execution](INDEPENDENT_WORLDS.md) and adds
[bounded single-world windows](WINDOWED_EXECUTION.md) and
[independently clocked windowed cohorts](WINDOWED_WORLDS.md). Tissue, organ, and
computational-multiscale execution remain future work. See [First build](FIRST_BUILD.md),
[Isolated regulation](EMT_REFERENCE.md), [Passive contact](PASSIVE_CONTACT.md), and
[Reaction and transport](REACTION_TRANSPORT.md)
for the deliberately small delivered scopes.

D055 / [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md) now independently checks a small
finite extracellular compartment at the design/reference level. It owns outside
amounts, volume and fixed charge; membrane transfers have equal/opposite endpoint
ownership, and total ionic chemical/capacitor energy is accounted for. A common
well-mixed outside is a declared physical approximation, not one duplicated
environment per cell or a generic organ wrapper. Distinct future organs sharing
a transport compartment will likewise belong to one coupled world. Numerical
qualification and production remain separate gates before spatial refinement.

[NUM-009 v2](FINITE_EXTRACELLULAR_NUMERICS_V2.md) now tests the time-dependent numerical
boundary with outside amount and concentration budgets, complete conserved
state and small-reservoir depletion. Anchored numerical increments preserve
small exchanges without changing the physical amount/charge ownership. Every
inventory remains explicit, including disconnected compartments; a disabled
owner must not become a sink for other owners' numerical cancellation. This is
one resolution of a finite environment, not a validated organ or spatial model.

D058 / CORE-009 now implements these anchored coordinates on separate numeric
cell/membrane/channel/junction/outside axes. Its
[formal CPU/JAX acceptance](../reports/CORE009_ACCEPTANCE.md) passes complete
restart, branch and cohort paths; the shared execution machinery is unchanged.
Outside volume and population size are data, with one-/five-cell scaling tests.
One active outside is the current physical approximation, not a permanent
engine-wide restriction. Spatial refinement needs a new electrical closure,
convergence evidence and eventually a deliberate device communication plan.

D059 / [SPEC-009](SPATIAL_EXTRACELLULAR_SPEC.md) supplies the next spatial
design and instantaneous reference, not production spatial refinement. Outside
volumes may have no membrane; membrane capacitance and extracellular current
constraints are separate graph structures. The one-cell/two-outside fixture,
two-cell chain and loop use data-defined ownership. No one-field-node-per-cell,
one-organ-per-GPU or implicit independent-bath convention is introduced.
Fine/coarse transfer will need charge/capacitance and energy constraints in
addition to material aggregation; this reference does not yet supply it.

D060 / [NUM-010](../reports/NUM010_REFERENCE.md) now supplies bounded short
spatial trajectories and temporal/spatial checks without adding production
multiscale execution. All five inventory/history fields survive reference
restart; potentials are derived from current inventories. The 8/16/32-volume
line panel separates continuum discretization error from analytic discrete-mode
time error. Its finest grid rejects the old well-mixed 1 ms step and qualifies
0.125 ms with 0.0625 ms refinement. Resolution-dependent stiffness remains a
numerical design concern regardless of CPU/GPU placement; adaptive coarsening,
fine/coarse transfers and multirate coupling are still separate gates.

D061 / [CORE-010](SPATIAL_EXTRACELLULAR.md) now maps this passive subset into the
shared CPU/JAX engine as a development family. Six array leaves retain the five
reference coordinate fields by splitting amount increments across independent
cell and outside axes. Pure-bulk worlds need no fake cell; membrane and face
histories are independently sized. Potentials are recomputed from state at every
stage and observation. The bounded dense field scratch is a numerical backend
choice, not dense saved geometry or a GPU partition map. Formal release
acceptance is still open; this adds no organ preset or cross-resolution coupling.

D045, 2026-09-09, now makes [BETSE-level capability](BETSE_CAPABILITY_ROADMAP.md)
and future parallel GPUs explicit targets. The companion
[execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md) refines ownership,
multirate/fine-coarse interface transfers, distributed field solves, independent
versus interacting GPU workloads, and collective/checkpoint semantics. It is
design-only. D046 now completes [SPEC-005's one-cell reference](MULTISPECIES_MEMBRANE_SPEC.md);
D047 adds [NUM-006's bounded trajectory qualification](../reports/NUM006_REFERENCE.md).
CORE-006 now implements a new numeric CPU/JAX assembly, with
[bounded acceptance complete](../reports/CORE006_ACCEPTANCE.md).
Species/role bindings, independent capacity axes and complete histories are
exercised through existing scalar/cohort paths. No organ wrapper, adaptive reduction
or distributed runtime is needed for that first production extension.
SPEC-006 now [checks two retained gates in one channel](../reports/SPEC006_DESIGN_CHECK.md)
without changing production. Fast activation and slower inactivation must remain
distinct from abundance and controls; equal open fraction is not complete state.
Its [contract](VOLTAGE_GATED_CHANNEL_SPEC.md) proposes gate/channel axes and
complete histories, with coupled NUM-007 qualification before production or
multirate reduction. An analytic fixed-voltage gate step is not an exact
feedback-coupled update or whole-cell voltage clamp.
NUM-007 now [qualifies a coupled 0.5 ms RK4/cubic candidate](../reports/NUM007_REFERENCE.md)
with independent refinement. The equal-open preparations evolve differently,
so a reduction must preserve or explicitly approximate both gate histories.
CORE-007 now implements those gate/channel axes through the common CPU/JAX
engine, with [bounded acceptance complete](../reports/CORE007_ACCEPTANCE.md).
Channel capacity is independent of cell
and membrane capacity and enters memory/batch preflight. This is not a multirate
or GPU result.

[SPEC-007's physical graph](PHYSICAL_IONIC_GRAPH_SPEC.md) now has passing
[instantaneous composition checks](../reports/SPEC007_DESIGN_CHECK.md). Its shared
bath/diagonal-capacitance closure, one local membrane per cell and one owned
transfer per edge are explicit. Amounts alone cannot reconstruct a graph's
cycle transfer histories. Single/disconnected reductions and unequal pair/star
checks now have separate [NUM-008 short trajectory qualification](../reports/NUM008_REFERENCE.md).
The 2 ms candidate and 1 ms refinement cover only the frozen low-degree graphs;
they do not justify skipping shared stages, averaging away gate/history state,
or changing fine/coarse clocks. CORE-008 now implements the new production
family through the shared CPU/JAX engine; [acceptance status](../reports/CORE008_ACCEPTANCE.md)
is tracked separately. Independent worlds can have different physical cell and
edge counts while sharing capacity buckets. This does not make worlds interact
or establish coarse-grained physics, an organ preset, a larger-graph timestep or
a GPU result.

The first independent-world batch and bounded CPU profiles are now verified,
without selecting GPU or multirate optimizations. A batch is a collection
of independent experiments, not an organ hierarchy or an exchange model between
organs. The source pair's nominal clock supplies no physical multiscale timestep.
Complete batch histories still grow with world count and step count; conservative
compiled mapping is not a large-organ memory policy. Single-world windows now
separate bounded working traces from optional retained output, with exact
continuation, observations and accounting preserved. Windowed cohorts extend
this contract while retaining each world's own clock and complete restart state.
Windowing is storage partitioning, not multirate stepping,
coarse-grained physics or permission to bypass numerical checks.

SPEC-004's [first longer switching design](E02_SWITCHING_PROTOCOL.md) needs
three communicating cells, which the nominal pair cannot currently represent.
Its next graph extension must compose one local process per cell and explicit
edge contributions in a single world. Two independent pairs cannot stand in
for one shared recipient. This is a fixed-graph model gate, not new multiscale
physics; independently qualify it before production, then retain the same
bounded execution and complete state interfaces for later larger graphs.
