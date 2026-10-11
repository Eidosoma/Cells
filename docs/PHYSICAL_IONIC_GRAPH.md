# Physical ionic graph production engineering

CORE-008 implements `physical_ionic_graph@1` in Cells 0.13.0. Acceptance requires
the separately recorded production verification; [Progress](../PROGRESS.md)
tracks its current status. The
[physical contract](PHYSICAL_IONIC_GRAPH_SPEC.md) and
[short numerical qualification](PHYSICAL_IONIC_GRAPH_NUMERICS.md) remain frozen.

## Assembly and ownership

One common maintained bath, a named species/valence table, one bath-facing
membrane per cell, zero or one existing m/h channel per membrane, and a fixed
sparse junction list. Cells may have different amounts, volumes, capacitances,
transport coefficients and gate preparations. The production schema composes
the existing strict local definitions; no production code imports references.
All physical entity IDs are unique; species use a separate namespace.

The retained state has nine fields: amounts, baseline leak transfer, pump
cycles, membrane dissipation, membrane m/h gates, channel transfer, junction
gate, junction transfer and junction dissipation. Species are the penultimate
axis; cells, membranes, channels and edges have independent padded capacities.
Only amounts own ionic charge. Internal transfer never enters the bath ledger.
Disconnected components and absent channels/edges require no alternative solver.

The [runnable three-cell example](../configs/physical_ionic_star.json) binds the
frozen monovalent star and its independent block/release schedule to production
JSON. It includes unequal cell volumes, two membrane channels, two junctions
and extra inactive slots on each capacity axis. It is a synthetic engineering
fixture, not an organ configuration or a fitted cell preparation.

Use a new output directory for each run:

```bash
.venv/bin/python -m cells validate configs/physical_ionic_star.json
.venv/bin/python -m cells run configs/physical_ionic_star.json --output runs/my-ionic-star --checkpoint-at 0.0679
.venv/bin/python -m cells windowed run configs/physical_ionic_star.json --window-steps 37 --output runs/my-ionic-star-windows
```

The ordinary complete-snapshot resume, future-input branch and independent-world
cohort APIs apply. A branch cannot rewrite chemistry, geometry, past inputs or
the numerical method; new physical preparations are new model definitions.

Local transport and every owned junction are evaluated once from the same
complete RK stage. Sparse endpoint gather and signed scatter avoid a dense
cell-by-cell matrix. The shared CPU float64 checked RK4, zero-anchored event
grid, old-interval-control cubic interpolation and right-continuous observations
are unchanged. Gates continue relaxing when their external availability is zero.
Trial states and entire cubic interiors must remain in the declared physical
domains; no clipping or hidden reset is permitted.

## Prospective acceptance contract

Freeze this plan before the first production acceptance session. Authenticate
the 0.12.0 source archive and accepted NUM-008 source/evidence. Use the unchanged
twelve reference cases, preparations, controls, horizons and numerical/error
budgets. Run CPU/JAX JIT and eager at 2 ms, compare every retained field at
native endpoints and the frozen comparison mesh against saved refined Radau
dense output, and inspect readouts and cubic output with independent equations.
This is not a new implicit solve or a largest-stable-step claim.

Require complete scalar serialization, fresh-process restart of all twelve
cases, a future-only branch preserving all state, full scalar windows and
independent-clock original/resumed cohorts. Compare replayed arrays exactly
where the shared-engine contract promises exactness; use 0.001 times the frozen
trajectory budgets for eager/JIT comparison. Include changed topology/counts
within equal-capacity cohorts, edge orientation/order, inactive padding, hidden
ledger witnesses, absent mechanisms, malformed definitions, numerical rejection,
resource refusal and corrupted-artifact tests. Preserve old snapshot loading
under authenticated 0.12.0 sources, refuse implicit migration, and regress old
production model families without altering their meanings or timestep bounds.

Each attempted acceptance uses a new exclusive output directory. Its prospective
limits are 2400 s wall time and 1 GiB serialized artifacts, including complete
per-window/checkpoint evidence. CPU workers may use only CPUs 0–3 (one eager lane
per core); BLAS/OpenMP thread counts are one. Do not run CPU-heavy full regression
at the same time. Independent audits use CPU 4. Array reservations are conservative
working-storage estimates, not operating-system RSS or compiler-memory guarantees.
Retain failures and interrupted evidence; no automatic budget extension, scientific
retuning or tolerance relaxation. The full regression matrix runs afterward in
current, preserved 0.10.0, 0.11.0 and 0.12.0 source contexts, with source guards intact.

## Limits and the next architecture boundary

The 2 ms bound is qualified only for NUM-008's short single/disconnected/pair/star
fixtures. Accepting a general fixed graph schema does not qualify arbitrary
topologies, stiffness, durations or parameters. Runtime accounting/domain checks
are necessary but not an error guarantee. The cycle is a ledger witness, not a
qualified trajectory. Old model identities retain their previous bounds.

There is no finite extracellular inventory, mesh PDE, mechanics, growth,
division, multi-organ physiology, multirate stepping, distributed execution or
GPU acceptance here. Future accelerator work must preserve one edge owner,
solver-stage endpoint exchange and complete restart state; cross-device bitwise
identity is not promised. This is a multiscale-compatible transport foundation,
not BETSE parity or biological validation. The closed first-cell pilot and the
deferred E02 campaign are not reopened.
