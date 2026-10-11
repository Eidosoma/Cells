# Windowed independent worlds

CORE-005b / D029, Cells 0.10.0 implementation contract, 2026-09-08. Extend the
[single-world window contract](WINDOWED_EXECUTION.md) to homogeneous
[independent-world batches](INDEPENDENT_WORLDS.md). This remains CPU float64;
worlds are independent experiments, not connected organs or tissue partitions.

## Running a cohort

```bash
taskset -c 0-3 .venv/bin/python -m cells batch windowed validate configs/batch_source_pair.json --window-steps 16
taskset -c 0-3 .venv/bin/python -m cells batch windowed run configs/batch_source_pair.json --window-steps 16 --recording observations --checkpoint-every-windows 2 --output runs/my-windowed-worlds
taskset -c 0-3 .venv/bin/python -m cells batch windowed resume runs/my-windowed-worlds/snapshots/round-0000000002 --window-steps 32 --recording checkpoints --output runs/my-windowed-worlds-replay
```

The default width is 256 intervals and recording is `observations`. Cadence zero
(default) saves only the complete initial/final cohorts. A positive cadence saves
every N completed execution rounds, excluding the final round, which is already
saved as `checkpoint_final`. Round directory names count **completed rounds**;
the index's `round` field is zero-based. Every output directory must be new.

`cells batch windowed branch SNAPSHOT CHANGED_BATCH --output NEW_DIRECTORY`
uses the same policy flags and ordinary per-world future-change restrictions.
Check actual local clocks in the snapshot before choosing future interventions;
a round is not a common-time snapshot. The two example worlds happen to share
early grid points, but this is not a general guarantee.

Python APIs live in `cells.core.batch_windows`:

- `plan_batch_windows(spec, policy, checkpoints=None)` validates before execution.
- `run_batch_windowed(spec, policy, checkpoints=None, sink=None)` returns final
  per-world `WindowedResult`s, shared timings and peak working-array counts.
- `iter_batch_windows(...)` yields `BatchWindow`s. `worlds` contains participating
  read-only numerical windows; `checkpoints` always contains the complete cohort.
  A terminal world participates once if already finished at the start, then is
  omitted from later `worlds` mappings while its checkpoint remains unchanged.
- `cells.batch_window_io.write_windowed_batch(...)` runs and records incrementally.
  `cells.batch_io.load_batch_snapshot(...)` restores both ordinary and windowed
  cohort checkpoints under the same strict source/runtime checks.

Retaining yielded rounds or accumulating them in a sink defeats bounded storage.
There is no automatic background writer, device selection, asynchronous queue or
general resume-from-run reader. Resume consumes a complete checkpoint directory.

## Clocks and execution rounds

In each round, every unfinished world advances through at most `window_steps`
of **its own existing accepted intervals**. Each retains its original dt, exact
event splits, observations, parameters, identity and complete typed state. Do
not union unrelated event times or create a common biological clock. The last
round may be shorter; finished worlds are masked without evaluating their RHS.

Reuse the existing guarded compiled batch kernel. Prepare stacked parameters,
active masks and device state once per run. Cache compiled executables for the
full and tail widths inside that run. Numerical laws, RK4 stages and observer
formulas remain unchanged. Host observers still perform their ordinary checks;
this is not permission to skip checks for a benchmark.

Check every active world's numerical and observation results before exposing a
round to an output sink. Preserve cross-window sampled-state checks and reduce
diagnostic maxima separately by world ID. A failure refuses the whole round and
run. Previously recorded rounds and complete earlier checkpoints may remain,
but no completed-run manifest may be published for the failed cohort.

## Memory and checkpoints

Bound arrays by world count, common window width, capacities, padding and peak
observations per window. Check aggregate storage and global padded-work bounds
before model-capacity allocation. The per-world `max_steps` and batch
`max_padded_steps` still bound the declared horizon, even on resume. Metadata
schedules remain resident; compiler caches and process RSS are not hard-bounded
by the working-array estimate. Do not accumulate a list of rounds or payloads.

A cohort checkpoint is a map of complete states with **different valid local
clocks**, including worlds already finished. Snapshot validity is independent of
a full-horizon trace reservation. Keep the existing strict scalar/cohort snapshot
format and source/runtime compatibility. Preserve accepted 0.9.0 before editing;
there is no implicit old-checkpoint migration.

Save complete initial/final cohorts and optionally every N completed execution
rounds. Recording policy and window size may change on resume. A future branch
uses the existing per-world past/future rules at each world's own checkpoint
time; world reordering is by stable ID. No implicit add/remove/couple operation.

This first cohort writer does not offer arbitrary common-time `--checkpoint-at`
requests. Capturing unrelated requested times can require a separate queue of
past states; it must not silently defeat bounded storage or synchronize physics.
Individual scalar checkpoints can still be assembled through the validated
cohort-snapshot API. Round checkpoints state their actual per-world clocks.

## Incremental recording

Use the same full / observations / checkpoints policy and numeric chunk helper
as scalar windows. A single cohort JSONL index names each world and round; chunk
paths are namespaced by world ID. Initial/final cohort snapshots own fixed
layout arrays. No duplicate child trajectory or full-horizon payload inventory.
The final manifest hashes fixed metadata and the incremental index; each index
record hashes its own payload or cohort snapshot. Final summaries are per-world.

Files are `resolved_batch.json`, `summary.json`, `windows.jsonl`, the initial/final
checkpoint directories, and `manifest.json` published last. Full/observed chunks
are under `worlds/world-ID/chunks/`; checkpoint-only runs create no chunk files.
Each `world_window` index record contains world ID, round, local window index,
global local-clock step indices, validated/saved row counts, diagnostics and a
payload hash. Full recording omits duplicated inter-window boundary rows;
requested observations appear once per world in the continuation. A
`cohort_checkpoint` record hashes its manifest, which authenticates complete child
snapshots and their state hashes. Inventory memory is O(worlds), not O(rounds).

Numerical failure exposes no part of the failing round. An I/O failure can leave
partial output from an otherwise checked round; the absence of a completed-run
manifest identifies the incomplete run. Previously completed checkpoint
directories remain usable, subject to their ordinary validation.

## Acceptance and next boundary

Require all seven model families, different horizons/dt/events, eager/JIT paths,
padding, world reordering/renaming, one/all finished worlds, complete round
restart with changed policies, future branches and failure isolation. Compare
all accepted states and observations with scalar, scalar-windowed and ordinary
batch execution. Check serialization, resource refusal before allocation, source
preservation and no horizon-sized arrays in the new path.

Profile bounded CPU workloads separately from verification, preserving complete
trajectory parity and reporting preparation, kernel, observation, output and
memory scopes. A speedup is not an acceptance requirement. GPU placement,
vectorized guards, multirate/fine-coarse exchange, organ interfaces and longer
source assays remain separate work.

Acceptance passes **1057 tests**, with exact old scalar/full-batch regressions and
20 serialized cohort original/restart runs across all seven families. Preserved
0.9.0 snapshot loading and old-source window replay pass. Sixteen isolated CPU
workers confirm smaller history buffers and width-256 gains over sequential
scalar windows, but full batches remain faster and RSS does not consistently fall.
See [acceptance and measured trade-offs](../reports/CORE005B_ACCEPTANCE.md), including
the retained acceptance-fixture cursor refusal and its guard-preserving correction.
