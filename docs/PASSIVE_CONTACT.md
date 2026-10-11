# Passive contact: two cells, one exchange route

Implemented and verified as `passive_pair@1` in Cells 0.3.0 on 2026-09-08.
This completes M1c-a, the conservative transport prerequisite, not the full
M1c selective bioelectric model. See [acceptance](../reports/M1C_A_ACCEPTANCE.md)
and [current progress](../PROGRESS.md).

## Physical and numerical contract

Two well-mixed cells hold one synthetic transferable quantity. Volumes are fixed,
amounts are nonnegative, and there is no production, degradation, external source,
charge, membrane voltage, regulatory circuit, or internal gate dynamics. A single
physical contact has an aggregate permeability g in pL/s. Its prescribed opening
u(t) is dimensionless and lies between zero and one.

For the contact oriented from cell A to cell B:

```text
cA = nA / VA                       concentration: fmol/pL
cB = nB / VB
J  = g * u(t) * (cA - cB)          signed amount flux: fmol/s
dnA/dt = -J
dnB/dt = +J
dQ/dt  =  J                       signed net transferred amount: fmol
```

The orientation is an accounting convention: negative J reverses transport.
Q is a cumulative signed ledger, not material stored in the junction, an
additional reservoir, or a biological memory variable. It does not feed back
into dynamics. Total cell amount stays constant and each cell's change must
match its signed edge transfer. No clipping or renormalisation repairs a failed
trajectory.

Equal concentration is the equilibrium, not equal amount. With initial amounts
[8, 0] fmol and volumes [1, 3] pL, the equilibrium amounts are [2, 6] fmol.
The fixture is dimensional engineering mathematics, not a calibrated molecule or
an approximation validated against BITSEY's selective gap junctions.

## Data definitions and explicit state

The [active configuration](../configs/pair_exchange_active.json) declares two
distinct positive cell IDs, initial amounts/volumes, one contact ID, endpoint
cell IDs, permeability, the opening schedule, observations, and execution limits.
It shares schema version 1 with the isolated models, but its fields are specific
to this model. Unknown fields, undeclared endpoints, self-contacts, invalid units,
non-finite values, and unsupported controls are rejected.

| Block | Stored fields | Axis and meaning |
| --- | --- | --- |
| Dynamic cell state | amount | Cell capacity; first two slots active |
| Dynamic contact ledger | transferred | Edge capacity; first slot active |
| Cell layout | volume, active, cell IDs | Stable IDs are independent of array slots |
| Contact layout | contact IDs, sender/receiver slots, active, permeability | Physical adjacency, separate from opening |
| Experiment control | time and open_fraction | Explicit external intervention, not intracellular sensing |
| Execution clock | time, step index, event index | Full definition and clock identify the next control |

Host validation resolves endpoint IDs to in-bounds slots before JAX execution.
Cell capacity must be at least two and edge capacity at least one. Padding has
finite neutral values: zero amounts/transfer/permeability, unit volumes, false
masks, sentinel IDs, and safe endpoint indices. Inactive edges and edges incident
to inactive cells contribute nothing. Cell and edge dimensions are checked
separately in checkpoints and estimated trace-storage budgets.

The [coupling module](../src/cells/coupling/passive.py) calculates each flux once
and scatters equal-and-opposite amount changes into the cell vector. Repeated
endpoints accumulate all their contributions. JAX documents this accumulation
behaviour, but not a universal order for conflicting updates; cross-device
bitwise equality is therefore not assumed. See
[JAX indexed updates](https://docs.jax.dev/en/latest/_autosummary/jax.Array.at.html).

Shared-endpoint and independent-world flux tests exercise this primitive. The
end-to-end model/configuration remains exactly two cells and one physical edge;
those kernel tests do not themselves deliver a graph/ensemble or organ API.
Cells 0.4.0 separately adds [reaction/transport composition](REACTION_TRANSPORT.md)
on data-defined fixed graphs using the same coupling primitive; passive_pair@1's
original contract remains unchanged.

## Events, integration, and observation

Opening is piecewise constant and right-continuous. An entry at time t applies
from t onward; the segment ending at t uses the preceding value at all RK4 stages.
The zero-anchored integration grid is split at every contact event and the exact
final time. Observation times do not add integration steps. A final-time opening
change affects the reported instantaneous flux but transfers no extra amount.

CPU float64 RK4 is validated in the conservative supported domain:

```text
h * g * u * (1/VA + 1/VB) <= 1
```

This bound is checked on each actual event-split interval, not just the nominal
step or the maximum permeability. A blocked interval has zero exchange rate;
an extremely short opening is still represented. Finite initial concentrations,
declared instantaneous flux bounds, derived state, and accounting are checked.
The step bound is not an arbitrary-parameter accuracy guarantee. Refinement and
independent references establish accuracy for the shipped cases.

Accepted arrays are retained in full within explicit resource limits. Read-only
observations linearly interpolate primary amounts and the transfer ledger, then
derive concentration and flux using the opening at the observation time. The
flux is reconstructed from sampled state; it is not interpolated across a control
discontinuity. Snapshots use accepted states, never interpolated observations.

## Controls, restart, and branching

Four shipped definitions share the same physical contact and initial cells:

| Configuration | Opening schedule | Check |
| --- | --- | --- |
| [Active](../configs/pair_exchange_active.json) | Open throughout 0-12 s | Conservative equilibration with unequal volumes |
| [Blocked](../configs/pair_exchange_blocked.json) | Closed throughout | Contact remains present; zero transfer |
| [Release](../configs/pair_exchange_release.json) | Open until 6 s, then closed | Compatible future branch freezes further exchange |
| [Pulse](../configs/pair_exchange_pulse.json) | Open from 2.03 to 5.07 s only | Off-grid control events and exact restart boundaries |

Complete snapshots retain cell and edge state/layout, definitions, clock, source
identity, runtime, and hashes. Unchanged continuation reproduces the accepted
trajectory suffix exactly under the pinned CPU runtime. A branch may change
future opening, horizon, and observations while preserving the past, the accepted
checkpoint boundary, model, topology, and execution settings. Numerical restart
is not biological transfer or inheritance.

## Next boundary

CORE-003's [engineering gate](ENGINEERING_GATE.md) is now complete: local reactions
and species-specific transport share a numerical stage, with independent controls
and accounting. This does not validate the source's gap-junction mechanism.

D018's next [one-cell physical contract](BIOELECTRIC_CELL_SPEC.md) introduces
membrane/bath interfaces, charge closure, leaks, and an energized reference pump.
Its instantaneous checks and [NUM-002 trajectory qualification](BIOELECTRIC_NUMERICS.md)
pass. Production JAX implementation is next; this is not source parity.

M1c-b must separately specify the source's ions, voltage, molecule selectivity,
regulatory coupling, unit correspondence, primary/derived refresh, and stiffness.
The isolated EMT model uses nominal source-time units; it cannot simply be wired
to a contact measured in seconds without a declared mapping. Source reuse and
paper correspondence also remain open as recorded in the
[isolated reference contract](EMT_REFERENCE.md).

Before full M1 closeout, measure a representative small independent-world batch
and coupled workload. Current per-run timings and kernel batching tests do not
constitute a performance study. Large-graph scaling, multirate stepping, fine/coarse
state transfer, bounded streaming, GPU execution, and multiple organs remain
later work under the [multiscale design](MULTISCALE_DESIGN.md).
