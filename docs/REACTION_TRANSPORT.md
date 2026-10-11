# Reaction and transport composition

Implemented as `reaction_transport@1` in Cells 0.4.0, 2026-09-08. This completes
CORE-003's [engineering gate](ENGINEERING_GATE.md), not the source-selective
bioelectric part of M1c-b. See [acceptance](../reports/CORE003_ACCEPTANCE.md).

## Model and process boundaries

This synthetic model contains two named amount species in fixed-volume cells,
one reversible local conversion, and species-specific passive contacts. The
population and fixed graph are data; the shared numerical machinery has no
one-, two-, or three-cell limit. The model itself has exactly two species and
one conversion law, not an arbitrary reaction-network language.

The [local process](../src/cells/processes/reactions.py) reads two amount fields
and per-cell rate constants. The [coupler](../src/cells/coupling/passive.py) reads
amounts, volumes, endpoints, masks, permeability, and prescribed openings. Neither
knows phenotype, donor/recipient roles, assay identifiers, or desired outcomes.
The [model composition](../src/cells/models/reaction_transport.py) maps declared
species names to slots, combines both contributions, and supplies its state,
validation, and observations to the existing runner. No upstream code is used.

For the declared from-species A and to-species B in cell i:

```text
r_i = k_forward_i * n_A_i - k_reverse_i * n_B_i
reaction contribution: d(n_A_i)/dt = -r_i, d(n_B_i)/dt = +r_i

J_s,e = g_s,e * u_e(t) * (n_s,from / V_from - n_s,to / V_to)
transport contribution: -J_s,e at the from-cell, +J_s,e at the to-cell

total derivative = reaction contribution + transport contribution
```

Every RK stage evaluates both processes on the same stage state. There is no
sequential state mutation or implicit operator splitting. Disabling reaction
rates or contact openings does not choose a different implementation path.

Amounts are fmol, volumes pL, time seconds, reaction rates 1/s, and aggregate
contact permeabilities pL/s. The model has no calibrated molecule, membrane
voltage, charge or energy budget, growth, division, or biological memory claim.
The closed 1:1 conversion preserves total A+B, not necessarily each species total.
These invariants do not apply automatically to a different regulatory model.

## State, axes, and accounting

| Field | Shape in one checkpoint | Meaning |
| --- | --- | --- |
| amount | species, cell capacity | Actual material in the cells |
| transferred | species, edge capacity | Signed net amount along each oriented edge |
| converted | cell capacity | Signed net from-species to to-species conversion |
| volume, active, IDs | cell capacity | Fixed volume, occupancy, stable biological identity |
| contact IDs, endpoints, active | edge capacity | Physical graph, independent of opening |
| permeability | species, edge capacity | Species-specific transport coefficient |
| forward/reverse rates | cell capacity | Fixed local reaction parameters |

Accepted and observed histories add a leading time axis. Species ordering is
explicit in configuration and summary; cell/edge IDs are independent of slots.
Contact orientation only determines the sign of a ledger, not a one-way channel.
Conversion and transfer ledgers are signed: neither is an extra material store
or a feedback/memory mechanism.

For every cell and species, amount change must equal signed contact receipts
plus the signed conversion contribution. The runtime separately checks this
identity, global A+B balance, finite/nonnegative amounts, and neutral padding.
The balance tolerance is 512 float64 epsilons times max(1, initial total); local
accounting uses 1024 epsilons times
`max(1, initial amount + |net receipts| + |conversion|)`.
These are roundoff guards, not trajectory-error estimates.

Unused cells have zero state/rates, unit volume, false masks, and sentinel IDs.
Unused edges have zero state/permeability, false masks, and safe endpoint slots.
Zero physical contacts and zero edge capacity are valid. Distinct contact IDs may
connect the same endpoints; their contributions accumulate independently.
Self-contacts and unknown/duplicate identities are rejected.

## Configuration and events

Examples are [one cell](../configs/reaction_transport_single.json),
[two cells](../configs/reaction_transport_pair.json), a
[three-cell chain](../configs/reaction_transport_chain.json), and its
[release branch](../configs/reaction_transport_release.json).

The model declares population, species, amounts, volumes, reaction source/target
species, per-cell rates, and contacts. The experiment declares `source.kind=none`
and `prescribed_contact_open_fractions`. Every scheduled entry supplies a complete
opening vector, each value in [0,1]. Its explicit contact-ID order may differ
from the model's contact order; the host resolves and normalizes it before stepping.
Each contact can open or close independently. There is no implicit external
amount supply or time-varying reaction-parameter control in this version.

The grid is anchored at zero and split at control events and the exact end time.
Opening is right-continuous. A step ending at an event uses the preceding vector
at all RK stages; the next interval uses the new vector. Even a sub-step opening
is represented. A final-time event changes instantaneous observed flux, not the
already integrated state or ledger.

Observations interpolate primary state on the time axis without changing the
numerical grid, then reconstruct concentrations and process rates. Flux uses
the opening at the observation time, not an interpolation across a control jump.
Empty observation selections and empty edge axes are supported. Full accepted
traces are retained within explicit step and estimated-storage limits; streaming
is not implemented.

## Numerical domain and accuracy

Let alpha be the largest outgoing rate of any species/cell coordinate:
its reaction loss rate plus all incident contact conductances divided by that
cell's volume. The implemented conservative bound is `h * alpha <= 0.5` for
each actual event-split interval. All incident edges contribute to alpha;
a blocked edge contributes zero. Finite concentration, rate, weighted-stage,
and integrated-ledger bounds are also checked, including final-time declarations.

For this closed linear positive system, write its amount generator as
`L = alpha * (P - I)`, where P is nonnegative and column-stochastic. At
`h * alpha <= 0.5`, the RK4 stage and endpoint polynomials in P have nonnegative
coefficients summing to one. This motivates the conservative domain in exact
arithmetic; accepted-state and accounting checks still guard floating-point runs.
This argument concerns the amount block, not positivity of signed ledgers, and
does not select a solver for future nonlinear or stiff bioelectric models.

Stability is not sufficient accuracy. Shipped definitions meet a 4e-8 fmol
maximum accepted-state/ledger reference-error target at step 0.05. Faster
equal-volume, parallel-edge, and five-cell test variants require step 0.025 for
that same target; refinement is tested explicitly. No automatic timestep
selection, clipping, renormalization, or numerical rescue is used.

The tiny verification oracle assembles a separate dense matrix with amount and
ledger rows. Piecewise matrix exponentials are applied in time order: changing
reaction/transport generators generally do not commute. The production model
uses sparse endpoint gathers/scatters and local rates, never this dense oracle.

## Continuation and remaining boundaries

Full snapshots preserve array state/layout, species and identity mappings,
definitions, clock, source hashes, runtime, and provenance. Unchanged replay is
exact under the pinned CPU runtime. A compatible branch may change future contact
openings, horizon, and observations, but not past controls, model, topology, or
execution settings. Off-grid checkpoint boundaries must remain in the new grid.

Closing all contacts freezes the transfer ledger while local reactions continue.
Each disconnected cell then preserves its own A+B total. This is process isolation,
not retention of a biological memory. Cell replacement, state perturbation,
dynamic topology, and biological transfer boundaries require their own event
contracts; a restart is not an inheritance operation.

The same fixed graph machinery can support further mechanisms, but this release
does not yet compose arbitrary model families. Source-scaled EMT and physical
amount coordinates remain separate until an explicit source model/mapping is
specified. GPU execution, complete-world batching, multirate stepping, resolution
changes, and organ composition remain future work; batching is currently checked
only at the process/RHS kernel level. No performance scalability claim follows
from these small examples.
