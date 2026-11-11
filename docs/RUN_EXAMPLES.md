# Running the model families

Command examples moved from the project README on 11 November 2026, unchanged except
for link paths. They use a local `.venv` created as in the [README](../README.md#get-started)
install steps. On the project host, the shared environment is
`/mnt/workspaces/Cells/venv-cpu/bin/python` with `PYTHONPATH=src`. The synthetic pulse
fixture was rerun that way on 11 November 2026; the other examples were not rerun, and
every config they name still exists. Model guides in this folder give each family's
units, controls and limits.

## Run with bounded recording memory

```bash
taskset -c 0-3 .venv/bin/python -m cells windowed run configs/source_pair_baseline.json --window-steps 256 --recording observations --checkpoint-at 5 --output runs/my-windowed-pair
taskset -c 0-3 .venv/bin/python -m cells windowed resume runs/my-windowed-pair/snapshots/step-0000000500 --window-steps 128 --recording checkpoints --output runs/my-windowed-replay
```

Choose `full`, `observations` (default), or `checkpoints`; every configured
numerical and observation check still runs. Checkpoints always contain complete
state, including diagnostic history. Change window size/recording on resume
without changing physics. Each output must be new. See the
[window guide](WINDOWED_EXECUTION.md) for the Python API, chunk format,
resource bounds and branch commands. Ordinary scalar and batch commands remain
available with their full-trace behavior.

For independent cohorts, checkpoint cadence counts execution rounds, not a shared
biological time:

```bash
taskset -c 0-3 .venv/bin/python -m cells batch windowed run configs/batch_source_pair.json --window-steps 16 --recording observations --checkpoint-every-windows 2 --output runs/my-windowed-worlds
taskset -c 0-3 .venv/bin/python -m cells batch windowed resume runs/my-windowed-worlds/snapshots/round-0000000002 --window-steps 32 --recording checkpoints --output runs/my-windowed-worlds-replay
```

Initial/final checkpoints always contain the complete cohort, including finished
worlds. See the [cohort window guide](WINDOWED_WORLDS.md) for branch commands,
independent clocks, memory guards and incremental output.

## Run independent worlds

```bash
taskset -c 0-3 .venv/bin/python -m cells batch run configs/batch_source_pair.json --output runs/my-worlds --checkpoint-at 0.5
taskset -c 0-3 .venv/bin/python -m cells batch resume runs/my-worlds/snapshots/checkpoint-000000 --output runs/my-worlds-replayed
taskset -c 0-3 .venv/bin/python -m cells batch branch runs/my-worlds/snapshots/checkpoint-000000 configs/batch_source_pair_branch.json --output runs/my-worlds-branched
```

These are two independent source-pair experiments, not four communicating cells
or two interacting organs. Each world retains its own clock and complete state.
The branch changes only world 101's future miRNA control. Every output must be
new; see the [batch guide](INDEPENDENT_WORLDS.md) for schema, numerical and
resource restrictions, individual-world access and profiling commands.

## Run a source-compatible pair

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/source_pair_baseline.json --output runs/my-source-pair --checkpoint-at 5
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-source-pair/snapshots/step-000500 --output runs/my-source-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-source-pair/snapshots/step-000500 configs/source_pair_branch.json --output runs/my-source-branch
```

The branch independently inhibits/restores miRNA transfer and one cell's pump;
ionic contact remains active. Full primary state, fixed context, anchors and
exchange histories survive restart. Each output must be new. See the
[guide](SOURCE_EMT_PAIR.md) for units, supported controls and remaining scope.

## Run a physical gated pair

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_pair_baseline.json --output runs/my-physical-pair --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-pair/snapshots/step-006000 --output runs/my-pair-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-physical-pair/snapshots/step-006000 configs/bioelectric_pair_branch.json --output runs/my-pair-branch
```

The gate keeps evolving during a transport block; restart retains it and all
exchange history. This model uses the independently qualified 1 ms step, not
the single-cell 5 ms bound. See the [guide](BIOELECTRIC_PAIR.md) for data,
controls, accounting, numerical limits and remaining scope. Every output must be new.

## Run one physical cell

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_baseline.json --output runs/my-physical-cell --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-cell/snapshots/step-001200 --output runs/my-physical-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-physical-cell/snapshots/step-001200 configs/bioelectric_branch.json --output runs/my-physical-branch
```

This runs 10 seconds, not automatic equilibration. The branch independently
blocks/releases Na leakage and pumping. Every destination must be new; accounting
and electrical anchors survive restart. See the [guide](BIOELECTRIC_CELL.md)
for units, controls, outputs, numerical limits, and remaining scope.

## Run reactions and transport

Start with one reactive cell, then a three-cell chain using the same model:

```bash
.venv/bin/python -m cells run configs/reaction_transport_single.json --output runs/my-reaction-cell
.venv/bin/python -m cells run configs/reaction_transport_chain.json --output runs/my-reaction-chain --checkpoint-at 6
.venv/bin/python -m cells branch runs/my-reaction-chain/snapshots/step-000122 configs/reaction_transport_release.json --output runs/my-reaction-release
```

Two synthetic species interconvert locally and exchange through declared contacts.
Cell count, volumes, rates, species names, topology, and contact openings are data.
The release branch closes both contacts at six seconds: transport stops while
local reactions continue. Total A+B is conserved; each species total need not be.
The [composition contract](REACTION_TRANSPORT.md) defines the equations,
axes, units, numerical limits, and model boundaries. It is not a general reaction
network language or a connection to the source-scaled EMT model.
Every output directory must be new. For bounded CPU use on this host, prefix
commands with `taskset -c 0-3`.

## Run two contacting cells

From this directory, using the installed CPU environment:

```bash
.venv/bin/python -m cells run configs/pair_exchange_active.json --output runs/my-pair --checkpoint-at 6
.venv/bin/python -m cells resume runs/my-pair/snapshots/step-000120 --output runs/my-pair-replay
.venv/bin/python -m cells branch runs/my-pair/snapshots/step-000120 configs/pair_exchange_release.json --output runs/my-pair-release
```

The cells start with [8, 0] fmol in unequal volumes [1, 3] pL. Passive transport
moves them toward equal concentration while preserving total amount. The release
branch closes the contact at six seconds; the physical connection remains present
but further exchange stops. The [contact contract](PASSIVE_CONTACT.md) describes
units, controls, edge state, numerical limits, and the separate source-coupling gate.
Every output directory must be new. For bounded CPU use on this host, prefix
commands with `taskset -c 0-3`.

## Run a regulatory cell

From this directory, using the installed CPU environment:

```bash
.venv/bin/python -m cells run configs/emt_isolated_e.json --output runs/my-emt-e --checkpoint-at 5000
.venv/bin/python -m cells run configs/emt_isolated_m.json --output runs/my-emt-m
.venv/bin/python -m cells resume runs/my-emt-e/snapshots/step-050000 --output runs/my-emt-replay
```

The two configurations differ only in initial regulatory state. Each runs to
10000 source-time units with fixed Snail 72; the coordinates are source-scaled,
not calibrated physical concentrations or seconds. Outputs include the three
primary trajectories, derived binding complexes, observer labels, and provenance.
Read the [reference contract](EMT_REFERENCE.md) for the model's limits.

## Run the synthetic pulse fixture

From this directory, using the already installed local environment:

```bash
.venv/bin/python -m cells run configs/single_cell_pulse.json --output runs/my-first-cell --checkpoint-at 6
```

This simulates 12 seconds with an input pulse from 2.03 to 5.07 seconds. It writes
the resolved configuration, accepted/observed trajectories, a summary, hashes,
timings, and complete checkpoints. The output directory must not already exist.

Continue unchanged, or change only future inputs from the same six-second state:

```bash
.venv/bin/python -m cells resume runs/my-first-cell/snapshots/step-000122 --output runs/my-replay
.venv/bin/python -m cells branch runs/my-first-cell/snapshots/step-000122 configs/single_cell_rechallenge.json --output runs/my-rechallenge
```

The snapshot name above is for the shipped configuration; other grids list their
snapshot paths in the run manifest. Rechallenge adds a 0.5 fmol/s source at six
seconds. It changes the future without modifying the parent or its prior inputs.

For a fresh checkout, use Python 3.13 (tested with 3.13.5):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements-lock.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
```

The lock is CPU-only. Supported model families can also select GPU execution;
see the [GPU and ensemble guide](GPU_ENSEMBLES.md) for the separate CUDA
environment and model-specific requirements.

