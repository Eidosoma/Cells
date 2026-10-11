# Engineering gate before coupled bioelectricity

Direction clarified by the user on 2026-09-08: support the Levin exploration's
assays through Cells' own reusable engineering, not through experiment-specific
engine behaviour. The bounded composition build described here is implemented
and verified as CORE-003 in Cells 0.4.0. Its engineering/numerical gate is complete;
the subsequent source-selective scientific comparison is not. See the implemented
[contract](REACTION_TRANSPORT.md) and [acceptance](../reports/CORE003_ACCEPTANCE.md).
See [D016](DECISIONS.md#d016-engineering-led-composition-before-source-assay-parity)
and [Progress](../PROGRESS.md).

## Starting point: the 0.3.0 code

Keep the shared CPU/JAX runner, pure model functions, read-only observers, stable
identities, explicit cell/edge arrays, numerical checks, and strict checkpoints.
They are useful independently of the source experiments.

The 0.3.0 registry selects one complete model per run. The regulatory cell and
passive pair are separate models; local reactions and contact transport do not
yet contribute to the same evolving state. The pair's configuration and checks
explicitly assume two cells and one edge, and each model has at most one declared
control channel. These are honest first-fixture limits, not a composed world API.

CORE-003 addresses this gap with a small independent composition model, retaining
the registry and previous model contracts. Its host-resolved species and graph
definitions feed separate local and exchange functions on shared stage state.
This is not a wholesale rewrite or a universal simulation framework; each run
still selects one explicit model family.

## Responsibility boundaries

| Layer | Owns | Must not own |
| --- | --- | --- |
| State and topology | Named fields, units, primary/derived distinction, capacities, IDs, endpoints | Desired phenotypes or experiment outcomes |
| Mechanisms | Local reaction laws, membrane laws, transport laws, declared state reads and contributions | Assay IDs, hidden preparation history, implicit state resets |
| Numerical execution | Stage evaluation, accumulation, event boundaries, solver state, resource policy | A special integrator branch to make a named assay pass |
| Model definitions | Selected mechanisms, parameter sets, coordinate mappings, initial conditions, wiring | Arbitrary executable expressions in configuration |
| Experiments | Cues, explicit interventions, reference preparation, permitted boundary operations | Silent modifications to equations or undeclared biological information access |
| Observers and reference adapters | Labels, recovery/renewal criteria, imported source coordinates, comparison reports | Unrecorded feedback into the dynamics |

A small explicit registry may still identify model families. Source-specific
equations and approximations belong in an identifiable model module, not in the
solver or graph infrastructure. The source is a scientific reference and one
model family, not the definition of what every Cells cell must contain.

## Completed bounded build: local reactions plus graph transport

Implemented fixture: fixed-volume cells with two synthetic amount
coordinates A and B. A reversible first-order reaction A <-> B operates locally;
species-specific passive contacts exchange declared amounts between cells.
Reaction-only, transport-only, and combined cases use the same composition path.
The shipped examples have one, two, or three cells; an additional five-cell test
checks data-driven generalization beyond those examples. Species names are configurable.

For cell i, the local contribution is:

```text
r_i = k_forward_i * n_A_i - k_reverse_i * n_B_i
local d(n_A_i)/dt = -r_i
local d(n_B_i)/dt = +r_i
```

Transport contributes reciprocal edge fluxes to those same amount fields. The
synthetic 1:1 reaction conserves total A+B across the closed world; individual
species need not be conserved when reactions are active. Per-species contact
ledgers distinguish redistribution from internal conversion. These are declared
fixture invariants, not a universal mass law for all future regulatory models.

The implemented contracts are deliberately limited to what this fixture exercises:

- Resolve species/field mappings, graph endpoints, units, and writable targets on
  the host. Use finite neutral padding and independent cell/edge capacities.
- Evaluate local and exchange contributions from the same stage state, then
  accumulate them explicitly. Sequential mutation must not accidentally become
  an undocumented operator-splitting method.
- Keep reaction parameters separate from prescribed contact controls. New
  independent control channels require explicit scheduling and restart semantics;
  do not extend the current source-or-contact selector by silently dropping one.
- Preserve derived-state refresh, complete snapshots, immutable parent branches,
  and observer independence. A later state perturbation or donor replacement is
  a declared event, not an observer side effect or a generic snapshot copy.

Topology is data for these small cases: isolated cell, pair, three-cell chain,
and a connected pair with an isolated third cell. No organ names or donor/recipient
roles enter the numerical kernels. These population sizes are initial validation
cases, not hard-coded sizes in the shared graph machinery; the two-species reaction
is a fixture model, not the engine's definition of all cellular state.
The [implemented contract](REACTION_TRANSPORT.md) specifies the schema, state axes,
accounting, control semantics, and combined outgoing-rate numerical bound.
The passive-pair step bound is not reused as if it covered local reaction losses.

## Acceptance has separate layers

1. Engineering correctness: units and shapes, field ownership, finite state,
   declared accounting, exact event handling, graph disconnection, permutation
   invariance, padding, complete restart, and observation independence.
2. Numerical correctness: compare the small linear reaction/transport system
   with an independently assembled matrix reference; compose interval solutions
   in time order for changing controls. Check refinement and failure behaviour.
   Exercise reaction-only, transport-only, and combined cases, unequal volumes,
   and parameter/topology cases beyond the demonstration configuration.
3. Scientific correspondence: after these gates, add a pinned source model and
   compare derivatives, fluxes, continuous trajectories, and positive/negative
   assay outcomes under predeclared tolerances. Passing generic engineering
   tests alone does not establish correspondence with the source.

Layers 1 and 2 pass for this bounded composition model: 270 total regression tests,
eight saved examples, independent matrix/refinement checks, and full regressions
of the previous three models. Three faster test variants needed a finer step to
meet the unchanged numerical tolerance; that finding is retained in the
[acceptance report](../reports/CORE003_ACCEPTANCE.md). Layer 3 remains the next
separately specified source-coupling task, not a claim of this release.

Source comparison must not be reduced to a final E/M label. If a mismatch appears,
identify whether it comes from coordinate mapping, model assumptions, numerical
error, a source discrepancy, or an implementation defect. Preserve the discrepancy
and version any deliberate scientific change. Do not tune thresholds or add
case-specific behaviour merely to recover an expected result.

## Next physical-cell build after the gate

The user accepted the [BETSE/software recommendations](BETSE_DESIGN_REVIEW.md)
after CORE-003. D018 places one explicitly physical cell before source-selective
contact: a named membrane/bath interface, Na/K/Cl amounts, charge-derived voltage,
passive leaks, and a maintained-energy reversible reference pump. Its
[specification](BIOELECTRIC_CELL_SPEC.md) and 74 independent instantaneous design
checks are complete. NUM-002 now adds [independent integrated trajectories](BIOELECTRIC_NUMERICS.md)
and a bounded RK4/cubic-observation candidate. MODEL-003 now passes separate
[production acceptance](../reports/MODEL003_ACCEPTANCE.md).

The implemented fixture uses reusable contributions, independent leak/pump
controls and interval-correct observations. Physical units, charge/material
balance, energy signs, exact events, padding, observations, checkpoint provenance
and complete replay are verified. This extends the engineering-first path without substituting a physical
toy for BITSEY's source equations. No additional generic framework is required.

## Selective contact after the physical-cell build

D021/SPEC-002 now defines a [stateful physical pair](SELECTIVE_CONTACT_SPEC.md)
with explicit electrical closure, gate/transfer state and independent inhibition.
Its instantaneous equation checks pass; [NUM-003](SELECTIVE_CONTACT_NUMERICS.md)
now qualifies all 20 coupled reference cases and selects RK4/1 ms with cubic
observations. [MODEL-004 production](BIOELECTRIC_PAIR.md) now implements this
bounded pair with separate JAX/reference, domain, control, replay and regression
acceptance. The five earlier models keep their established numerical policies.
No inherited one-cell timestep guarantee or source-equivalence claim follows.

The [source map](SOURCE_COUPLING_MAP.md) now captures instantaneous native gate,
transport, orientation and miRNA-role probes. Source-compatible algebraic gating,
upwind drift and nominal coordinates are distinct from the physical model.

## Source integration after physical engineering

Complete the source model's ionic and regulatory primary state, algebraic refresh,
membrane/voltage law, selective contact law, numerical domain, and unit mapping.
Keep unresolved physical calibration explicit: source-scaled coordinates are not
silently physical amounts, and nominal source time is not silently seconds.
An explicitly defined reference-coordinate model can be distinguished from a
physically calibrated model; neither gets to invent conversions to satisfy tests.

For source acceptance, first compare isolated mechanisms and a small
active/blocked coupled case. Then
implement write-disconnect-challenge and a minimal relay through explicit generic
intervention/boundary operations. Larger historical panels are subsequent
reference coverage, not special engine branches or an automatically launched
campaign. Existing source-reuse limitations remain in the
[regulatory contract](EMT_REFERENCE.md).

## Multiscale and GPU consequences

Keep biological equations separate from process timing, numerical resolution,
and device placement. Use array functions and bounded storage now; compare small
independent worlds with one interacting graph and record compilation, execution,
memory, and output cost before choosing a GPU layout. Compatible field meanings
and exchange accounting are prerequisites for later fine/coarse and organ ports,
not evidence that those interfaces already exist.

This gate adds no adaptive mesh, multirate solver, dynamic population, distributed
runtime, general plugin loader, organ hierarchy, or GPU job. The verified 0.3.0
source was archived before package evolution, and its old runs were reverified
without relaxing strict snapshot identity. The delivered result is a small
composed model useful beyond the Levin assays, with independently checked
behaviour and explicit boundaries for subsequent source mechanisms.
