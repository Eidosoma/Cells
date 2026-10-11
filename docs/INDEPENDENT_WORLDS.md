# Independent-world execution

CORE-004/D027, 2026-09-08. Implemented and verified in Cells 0.8.0 across all
seven model families, with 896 passing tests and bounded CPU profiles. See
[acceptance and measurements](../reports/CORE004_ACCEPTANCE.md) and
[Progress](../PROGRESS.md) for the current status.

A world is one independent experiment, not a cell, tissue region or organ.
World IDs namespace biological IDs: two worlds may both contain cell 101
without sharing state, bath, parameters, controls or history. Interacting organs
would instead inhabit one world with explicit exchange interfaces.

## Run and continue a batch

From Cells, choose new output directories:

```bash
taskset -c 0-3 .venv/bin/python -m cells batch validate configs/batch_source_pair.json
taskset -c 0-3 .venv/bin/python -m cells batch run configs/batch_source_pair.json --output runs/my-worlds --checkpoint-at 0.5
taskset -c 0-3 .venv/bin/python -m cells batch resume runs/my-worlds/snapshots/checkpoint-000000 --output runs/my-worlds-replayed
taskset -c 0-3 .venv/bin/python -m cells batch branch runs/my-worlds/snapshots/checkpoint-000000 configs/batch_source_pair_branch.json --output runs/my-worlds-branched
```

The example contains world 101 (frozen S12 release) and world 202 (frozen S13
independent route/membrane pulse), both on the nominal source clock. Their
cell/contact IDs may overlap because they belong to different worlds. The
branch inhibits world 101's miRNA route from 0.5 to 0.713, preserving its ionic
route and leaving world 202 unchanged. It does not reset either world's history.

The batch definition is a strict object with `schema_version: 1`,
`kind: independent_worlds`, `worlds: [{world_id, simulation}, ...]` and an
`execution` object. Each `simulation` is a complete ordinary Cells definition;
there are no hidden file references, executable expressions or parameter overrides.
Batch execution requires `mapping: lax_map`, `max_worlds`, `max_padded_steps`
and `max_working_bytes`. The world count is data, not an engine constant.

Python clients use `BatchSpec`, `WorldSpec`, `run_batch` and
`branch_batch_checkpoints` from `cells.core.batch`. Results are keyed by world
ID, with ordinary `RunResult` values. `result.checkpoint_at(0.5)` selects a common
accepted boundary; `result.checkpoint_at({101: 0.13, 202: 0.274})` selects separate
accepted clocks. `write_batch_snapshot` and `load_batch_snapshot` in
`cells.batch_io` save/restore the complete cohort. Ordinary scalar snapshot
readers can also load an individual child directory under that cohort.
Use `branch_batch_checkpoints` before changing a saved cohort's definition;
raw `Checkpoint` objects alone do not authenticate their originating protocol.

## First bounded execution contract

One batch contains an explicit nonempty list of identified, fully specified
worlds. It requires one model family, equal cell/membrane/edge storage capacities
and the same JIT policy. It does not require equal biological parameters,
topology, initial state, schedules, dt, horizons or observation times. Each
world must independently satisfy its model's existing numerical contract.
Mixed model families or capacity shapes require separate batches; no automatic
resizing, unit conversion or model selection is permitted.

The device input axes are world, local step, then model-owned axes. Each world
uses its original zero-anchored, event-split timeline. Do not take a cross-world
union of event times: that would change otherwise independent RK4 paths.
Shorter paths have masked terminal storage, never additional accepted steps.
Continuation may begin at a different accepted clock in each world. Results
strip terminal padding before invoking the ordinary model checks and observers.

The first mapping policy is explicit `lax_map`: one compiled, device-resident
mapping over complete independent rollouts. It preserves scalar conditional
failure guards; it is not a claim of parallel world execution or GPU speedup.
JAX documents that vectorizing a conditional over world predicates converts it
to selection, which can evaluate otherwise guarded expressions. A future
vectorized path must qualify invalid-trial, completed-world and finite-padding
semantics before replacing this policy.
[JAX conditional semantics](https://docs.jax.dev/en/latest/_autosummary/jax.lax.cond.html),
[compiled mapping](https://docs.jax.dev/en/latest/_autosummary/jax.lax.map.html).

Existing pure RHS functions and RK4 methods remain the numerical implementation.
No model acquires a world axis internally or an assay-specific execution branch.
If any world fails stage, accounting or observation checks, the batch is refused
without publishing a complete batch manifest. A failure names the world.

## Resource and replay contract

Before timeline construction or capacity-sized initialization, check world
count, a conservative padded-step work limit and an aggregate array-working
storage allowance. Retain every world's existing resource limits too. These
estimates include terminal padding, controls, histories and host observation
work; they are not a hard bound on process RSS, compiler memory or runtime.
Full accepted histories remain this API's output policy. For bounded incremental
execution use the separate [windowed cohort API](WINDOWED_WORLDS.md), introduced
in 0.10.0. Neither policy is a large-organ biological model.

Batch checkpoints contain an ordinary complete scalar snapshot per world plus
a strict, checksummed batch definition and world mapping. IDs, source/runtime,
state, layout, schedule position and diagnostic histories remain intact.
Worlds may be reordered by ID, but not added, removed or replaced on ordinary
resume. Branching permits only each world's already-supported future changes;
it cannot rewrite past controls or model/execution settings.

Fresh outputs never overwrite existing directories. Validate all requested
checkpoint boundaries before creating the destination. Publish the enclosing
manifest last, so incomplete writes are not mistaken for a complete batch.
Scalar snapshot/run formats remain usable independently of batch ownership.

## Acceptance and profiling gates

Require all seven model families to agree with scalar runs on the same local
grids, including complete histories and observations. Exercise independent
parameters/controls, world ordering and IDs, mixed horizons, cell/edge padding,
empty continuations, exact same-policy replay and valid future branches.
Retain negative tests for cross-world event contamination, numerical failure,
invalid configurations, corruption and aggregate resource exhaustion.
Batch/scalar comparisons use declared tight floating-point tolerances; exact
same-policy restart is separately required, not assumed from close endpoints.

Profile bounded CPU graph and nominal-pair batches at fixed world counts.
Separate host preparation, compilation/cache lookup, synchronized kernel work,
host transfer, model checks/observations and artifact writing. Report actual
array bytes, compiler memory estimates when available, output bytes and process
peak RSS with their different scopes. Repeated kernel timings must start from
identical state, with an untimed warm-up; never advance biology for a timing loop.
[JAX profiling guidance](https://docs.jax.dev/en/latest/201/profiling.html).

No speedup threshold is an acceptance criterion. Measurements guide subsequent
vectorization, output reduction and chunking decisions. GPU, distributed,
multirate and fine/coarse tissue execution remain separately validated work.

The first measured profile is complete: at 16 worlds graph full calls improve
by about 1.22×; nominal-pair full calls do not improve, and smaller batches are
slower. The largest batch histories here occupy only about 2.0 MiB (graph) and
0.38 MiB (source pair), while full worker peak RSS includes much more compiler/
runtime storage. These are small CPU diagnostics, not large-organ extrapolations.
CORE-005a now adds [single-world windows and recording choices](WINDOWED_EXECUTION.md)
with those numerical checks, clocks, observations and snapshots preserved.
CORE-005b now adds [windowed independent-world cohorts](WINDOWED_WORLDS.md);
this ordinary batch API still retains
full histories and enforces its existing aggregate trace limits.

Complete cohort snapshots and future-branch validation no longer require a
full-horizon recording reservation. They retain identity, state/domain and global
work limits; the chosen run policy separately validates its working-array needs.

To regenerate acceptance or the bounded profile with new outputs:

```bash
taskset -c 0-3 .venv/bin/python -W error scripts/verify_world_build.py --output runs/my-world-acceptance
taskset -c 0-3 .venv/bin/python -W error scripts/profile_worlds.py --output runs/my-world-profile
```

The profile launches 12 sequential workers (120 seconds maximum each), separately
from verification jobs, and retains all measurements. Cold compilation, warmed
full-call/kernel medians, actual array/output bytes and process RSS have distinct
scopes. `run_batch(..., timing_repeats=3)` additionally supports an explicit
same-input kernel diagnostic with an untimed warm-up; it returns one trajectory,
not three biological advances. The saved profile instead repeats whole calls to
measure host work as well as synchronized kernel execution.
