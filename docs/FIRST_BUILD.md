# First build: one cell, end to end

Initial implementation plan: 2026-09-07. M1a is implemented as version 0.1.0 and
verified on 2026-09-08. This document preserves its scope and numerical contract.
See the [acceptance report](../reports/M1A_ACCEPTANCE.md),
[run instructions](../README.md), and [Progress](../PROGRESS.md).
M1b has since been completed in 0.2.0; its separate
[reference contract](EMT_REFERENCE.md) and [acceptance report](../reports/M1B_ACCEPTANCE.md)
extend, rather than change, the historical 0.1.0 scope below.
M1c-a adds a verified [passive two-cell contact](PASSIVE_CONTACT.md) in 0.3.0;
later source-selective work is described in the [source-compatible pair guide](SOURCE_EMT_PAIR.md).
The version 0.1.0 boundaries below remain historical, not current engine-wide limits.

## Deliverable

Run one well-mixed cell on CPU from a data definition. Apply a timed input,
record its trajectory, save and restore the complete state, and branch it into
two independent continuations. Compare numerical output with a known solution.

The biological cell model, numerical method, experiment schedule, and observations
are separate modules. This is a small instance of the
[multiscale design](MULTISCALE_DESIGN.md), not a separate disposable simulator.
It establishes the execution contract before importing a more complex regulatory
model. It does not demonstrate memory, heredity, organ function, or complete
cell biology.

## First model and experiment

Use an explicitly synthetic source-and-decay fixture with one primary amount n,
fixed positive cell volume V, and derived concentration c = n / V:

```text
dn/dt = q(t) - k*n
```

Here q is a declared external input in amount/time, k is a nonnegative decay
rate in 1/time, and n is an amount. The source is externally supplied and the
decay product is outside this reduced model; record their contributions rather
than claiming the cell alone is a closed system. No molecular calibration or
membrane mechanism is implied. No stochastic process is added initially.

For constant q and k > 0, the exact reference over an interval of length h is:

```text
n(t+h) = q/k + (n(t) - q/k)*exp(-k*h)
```

At k = 0, use n(t+h) = n(t) + q*h. Piecewise-constant input gives an independent
reference for a pulse. Test no input, constant input, and pulse/release. A pulse
is a simple way to exercise event timing, not an assumed learning mechanism.

The numerical implementation is fixed-step RK4 for this non-stiff
fixture, splitting steps at scheduled input changes and the requested final
time. Input is constant on each integration segment, including its RK stages;
the new input applies to the next segment at a discontinuity. The analytic
solution remains separate test code. Pin tolerances and a stable test step range
before recording a pass; test refinement instead of relying on a plausible plot.

The implemented schema fixes units to fmol, pL, and seconds without implicit
conversion. It supports one active cell plus neutral padded slots, CPU float64,
and the conservative domain k times the largest actual step <= 1. The timestep
grid is anchored at zero and split at exact source events and the final time.
Step count and estimated trace-working-storage limits are explicit settings.

RK4 here is not the solver decision for the Levin-derived model. Its stiffness,
coupling, and source settings require an independent check in M1b/M1c against
CPU references such as SciPy's
[ODE solvers](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).

## Small module layout

Implemented layout (package initialisers and individual tests omitted):

```text
pyproject.toml
src/cells/
  __main__.py          command entry point
  core/
    specs.py          validated model/experiment/execution definitions
    state.py          explicit numerical state and stable identities
    runner.py         schedule, numerical stepping, observation boundaries
  models/
    source_decay.py   first registered model and its state/units contract
  numerics/
    fixed_step.py     numerical method independent of biology
  observers.py        read-only amount/concentration measurements
  io.py               resolved manifest, trajectories, restart snapshots
configs/
  single_cell_pulse.json
  single_cell_rechallenge.json
scripts/
  verify_first_build.py
tests/
  unit/
  integration/
```

Keep the model registry small and explicit. No plugin discovery, universal
equation language, deep inheritance hierarchy, organ classes, or distributed
scheduler is needed for this slice. Add communication, fields, lifecycle, and
reduction modules when their first executable fixtures arrive.

Use the same batched-array conventions with one active cell that will later
support larger populations. A larger padded capacity must not change the active
cell's result. The first process has a named external input; full physical
couplers are deferred to the two-cell/field fixtures.

## Configuration and outputs

Start with validated JSON to avoid an additional configuration dependency.
Define separate model, experiment, and execution sections, recording:

- Schema and model identifiers, amount/volume/time units, initial state, and k.
- The one-cell population and prescribed q(t) schedule, including its external
  support status and exact event times.
- Backend, float64 precision, step size, horizon, observation times, and output
  policy. The output directory is selected separately with the CLI's --output
  argument. Seed/random-state fields are explicitly unused for this model.

Reject unknown model identifiers, unsupported fields/schema versions, incompatible
units, negative rates or amounts, invalid volume, and ambiguous schedules before
execution. Do not silently supply scientifically consequential defaults.

For this tiny build, numeric NPZ arrays plus a readable JSON manifest are a
provisional snapshot/trajectory format; avoid pickle-dependent object arrays.
The longer-run HDF5/Zarr decision remains open. A snapshot includes state,
physical time, event position, continuation-relevant numerical state, cumulative
accounting needed for reporting, and identifiers for the resolved definitions.
Incompatible model/schema restoration must fail clearly. Save outputs to a new
run directory and refuse accidental overwrite.

The implemented command is:

```text
.venv/bin/python -m cells run configs/single_cell_pulse.json --output runs/single-cell-001
```

The primary artifact is machine-readable data plus a compact report. A plot of
the trace is useful but optional; no interactive viewer is required.

## Build order and acceptance evidence

All six M1a steps are complete; the report links their tests and saved artifacts.

| Step | Build | Check before moving on |
| --- | --- | --- |
| 1 | Local CPU environment, package, test entry point | Reproducible pinned dependencies; imports and float64 setting checked |
| 2 | Definitions, explicit state, initialisation, model RHS | Units/domain validation; derivative spot checks; no hidden mutable state |
| 3 | Integration, pulse scheduler, read-only observations | Exact-solution comparison, step refinement, off-grid event times, exact final-time handling |
| 4 | Run artifacts and snapshot/restore | Resolved manifest; uninterrupted versus restored equality under the pinned backend |
| 5 | Independent checkpoint branches and padded execution | No state aliasing; changed input affects only its branch; masked slots are neutral |
| 6 | End-to-end example and concise test report | Clean CLI run; eager/JIT agreement; reproducible output and honest timing |

The build uses an isolated CPU-only .venv and its pinned dependency set. No GPU
packages or research-lane environment were used.

The acceptance suite must also verify:

- Nonnegative, finite trajectories in the declared supported regime, without
  silent clipping of failed numerical states.
- Amount/concentration consistency and source-minus-decay accounting residuals
  within numerical tolerance.
- Changing observation frequency does not change model evolution or consume
  model randomness. Output sampling is separate from the integration schedule.
  Sample accepted states or use a declared read-only interpolation; do not force
  extra integration steps merely to reach a requested observation time.
- An input pulse shorter than the nominal integration step is still represented
  by its event boundaries.
- Invalid input, unsupported backend, and incompatible snapshots produce explicit
  failures rather than altered models.
- CPU compilation, warmed execution, and output time are recorded separately.
  No GPU speed claim follows from a one-cell benchmark.

## Version 0.1.0 boundaries

The 88-test suite checks the acceptance contract, including eager/JIT agreement
and exact unchanged restart under the pinned software/backend. Off-grid
observations use explicitly labelled linear interpolation; all accepted numerical
states are saved separately. Snapshots require exact accepted boundaries, not an
interpolated observation. Observation frequency does not alter the numerical grid.

Resume requires matching engine/model source hashes, runtime versions, CPU
architecture, selected numerical environment, and a complete valid snapshot.
Cross-version/device migration is deliberately not implemented. Bitwise agreement
has been tested on this host, not promised across different hardware or runtimes.

A branch can change future input, the future horizon, and observation times while
retaining the past schedule, numerical grid through the checkpoint, model, and
execution settings. Preserve a source entry at an off-grid checkpoint time if
otherwise removing it would remove that integration boundary. Biological
inheritance/partition events are not yet implemented and are not snapshot copies.

The runner saves full bounded traces and uses a small host-built schedule with a
JAX scan. It does not implement streaming long runs, chunked restart, multiple
active cells, physical contacts, spatial fields, organ presets, or GPU execution.
Runtime or derived-state failure is explicit; invalid/failed simulations do not
produce a completed run manifest. No clipping, automatic rescue, or overwrite is
used. The 0.1.0 registry supported only source_decay@1.

## Following slices

M1b is now complete for isolated regulatory equations. It resolves the pinned
checkout and E/M fixtures, independently implements the source's simple binding
variant, and verifies derivative/trajectory/refinement/restart comparisons. Reuse
terms for upstream code redistribution and physical-time calibration remain open;
no upstream code is vendored. See [Isolated regulatory reference](EMT_REFERENCE.md).

M1c-a is complete: two cells and one explicit active/blocked passive contact,
with reciprocal amount accounting, analytic references, control events, and exact
restart. CORE-003 also completes [local reaction/transport composition](REACTION_TRANSPORT.md)
on data-defined fixed graphs. D018 now specifies a
[one-cell physical model](BIOELECTRIC_CELL_SPEC.md); its independent CPU
[numerical qualification](BIOELECTRIC_NUMERICS.md) and subsequent
[production JAX implementation](BIOELECTRIC_CELL.md) now pass. Source-selective
coupling follows with its own units, approximation, and solver contract.
Two contacting cells in one world are
distinct from two independent one-cell worlds.

The subsequent sequence is checkpoint-based memory/challenge assays, a small
fixed tissue, moving/growing tissue, validated multiscale tissue units, a simple
organ preset, and eventually coupled organ presets. GPU checks begin once a
representative CPU workload exists. No organ choice is needed to start M1a.
