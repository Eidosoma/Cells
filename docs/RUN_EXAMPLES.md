# Running the model families

Command examples moved from the project README on 11 November 2026. They use a local `.venv`
created as in the [README](../README.md#get-started) install steps. On the project host, the
shared environment is `/mnt/workspaces/Cells/venv-cpu/bin/python` with `PYTHONPATH=src`. Model
guides in this folder give each family's units, controls and limits.

> **Legacy cleanup (25 November 2026, D386).** The examples of the source-compatible pair, the gated
> pair, the older physical cell, the two contacting cells, the regulatory cell and the synthetic
> pulse left with their model families. The tag `pre-cleanup-2026-11-25` keeps them. Every command
> below was run once on 25 November 2026, on the cleanup branch.

## Run one physical cell

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/resolved_pump_tissue_channels_cell.json --output runs/my-physical-cell --checkpoint-at 0.5
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-cell/snapshots/step-000500 --output runs/my-physical-replay
```

This is one `resolved_pump_tissue@3` cell with a Na/K pump and three channel populations (Kir2.1,
Nav1.2 and a sodium leak). It runs one second, not automatic equilibration; the leak opens
from 0.05 to 0.35 seconds. Every destination must be new; accounting and electrical anchors survive
restart.

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
network language.
Every output directory must be new. For bounded CPU use on this host, prefix
commands with `taskset -c 0-3`.

## Run with bounded recording memory

```bash
taskset -c 0-3 .venv/bin/python -m cells windowed run configs/reaction_transport_chain.json --window-steps 64 --recording observations --checkpoint-at 6 --output runs/my-windowed-chain
taskset -c 0-3 .venv/bin/python -m cells windowed resume runs/my-windowed-chain/snapshots/step-0000000122 --window-steps 32 --recording checkpoints --output runs/my-windowed-replay
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
taskset -c 0-3 .venv/bin/python -m cells batch windowed run configs/batch_reaction_transport.json --window-steps 16 --recording observations --checkpoint-every-windows 2 --output runs/my-windowed-worlds
taskset -c 0-3 .venv/bin/python -m cells batch windowed resume runs/my-windowed-worlds/snapshots/round-0000000002 --window-steps 32 --recording checkpoints --output runs/my-windowed-worlds-replay
```

Initial/final checkpoints always contain the complete cohort, including finished
worlds. See the [cohort window guide](WINDOWED_WORLDS.md) for branch commands,
independent clocks, memory guards and incremental output.

## Run independent worlds

```bash
taskset -c 0-3 .venv/bin/python -m cells batch run configs/batch_reaction_transport.json --output runs/my-worlds --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells batch resume runs/my-worlds/snapshots/checkpoint-000000 --output runs/my-worlds-replayed
taskset -c 0-3 .venv/bin/python -m cells batch branch runs/my-worlds/snapshots/checkpoint-000000 configs/batch_reaction_transport_branch.json --output runs/my-worlds-branched
```

These are two independent chains, not six communicating cells or two interacting
organs. Each world retains its own clock and complete state. The branch closes world
101's two contacts at eight seconds. Every output must be
new; see the [batch guide](INDEPENDENT_WORLDS.md) for schema, numerical and
resource restrictions, individual-world access and profiling commands.

## A fresh checkout

Use Python 3.13 (tested with 3.13.5):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements-lock.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
```

The lock is CPU-only. Supported model families can also select GPU execution;
see the [GPU and ensemble guide](GPU_ENSEMBLES.md) for the separate CUDA
environment and model-specific requirements.
