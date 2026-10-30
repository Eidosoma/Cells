# Bounded windows and recording

CORE-005a / D028: Cells 0.9.0 contract, 2026-09-08. This first slice is
single-world CPU execution. [Windowed independent-world cohorts](WINDOWED_WORLDS.md)
follow in CORE-005b / Cells 0.10.0;
neither capability is interacting organs, multirate physics or GPU execution.
See [acceptance and CPU measurements](../reports/CORE005A_ACCEPTANCE.md): 982 tests,
all prior accepted scalar/cohort arrays unchanged, and exact archived replay.

## Using windows

```bash
taskset -c 0-3 .venv/bin/python -m cells windowed validate configs/source_pair_baseline.json --window-steps 256
taskset -c 0-3 .venv/bin/python -m cells windowed run configs/source_pair_baseline.json --window-steps 256 --recording observations --checkpoint-at 5 --output runs/my-windowed-pair
taskset -c 0-3 .venv/bin/python -m cells windowed resume runs/my-windowed-pair/snapshots/step-0000000500 --window-steps 128 --recording checkpoints --output runs/my-windowed-replay
taskset -c 0-3 .venv/bin/python -m cells windowed branch runs/my-windowed-pair/snapshots/step-0000000500 configs/source_pair_branch.json --window-steps 256 --recording full --output runs/my-windowed-branch
```

All output directories must be new. The default is 256 accepted intervals and
`observations` recording. Windows do not reduce the number of integration steps.
`cells run` and `cells batch run` keep their existing full-trace behavior.
Snapshot filenames in the window writer use ten-digit **global step indices**;
the index records their times. A snapshot is not an interpolated observation.

Python callers can use `run_windowed(spec, WindowPolicy(256, "observations"))`
for a final checkpoint, diagnostics, timings and measured buffer sizes without
output files. `iter_windows(...)` or the synchronous `sink=` callback expose
fully checked read-only windows. Retaining these windows defeats bounded storage.
`write_windowed_run(...)` performs incremental disk recording. The run policy
is saved in its manifest, independently of the resolved biological definition.

The disk format has `resolved_config.json`, `summary.json`, complete
`checkpoint_initial` / `checkpoint_final` directories, and `windows.jsonl`.
Each index line is either a checked-window record or an optional snapshot record.
For `full` recording, accepted rows have no duplicate window boundary; all
state fields use the same names as ordinary trajectories. Observation fields
use `observation_times` / `observed_*`. A chunk without observations omits those
fields. Fixed layout arrays live in the complete snapshots, not every chunk.
There is deliberately no monolithic `trajectory.npz` or automatic history loader.

## Execution is independent of recording

Keep the same zero-anchored `i * dt` mesh, exact event splits, RK4 kernels,
model laws and model observers as the full-trace runner. A window contains a
bounded number of **existing accepted intervals**, not a new time discretization.
Its final complete state becomes the next window's initial state. No ledger,
gate, reference quantity or event position is reset. Tail windows may be shorter.

Compiled scalar execution prepares one fixed-width integration executable per
iterator. Its width is the smaller of the requested window and the number of
remaining real intervals. A shorter final window masks its unused slots before
any model step, domain check or clock advance. Only real rows reach observations,
diagnostics and checkpoints. This keeps a short tail from compiling another
large integration executable; it adds no physical integration steps. Eager
execution and the ordinary full-trace path retain their existing behavior.
The working-array estimate already reserves that maximum window width. Compiler
memory and total process RSS still need their separate guards.

The grid is a lazy indexed union of nominal times, declared events and any
supported explicit numerical refinement, including the exact end time. It never
materializes a horizon-length array. Checkpoints
retain global accepted-step indices. Off-grid observations do not become steps,
and requested checkpoints must already be exact accepted boundaries.

Each window runs the ordinary step, state/accounting, stage-domain and observer
checks supported by its model. The two pair models' whole-cubic-interval checks
still run when a window has no requested observations. The physical single-cell
observer retains its existing sampled-domain checks; this change does not add a
new interpolation qualification. Cross-window sampled-state continuity is checked
explicitly, including diagnostic dissipation ordering. Diagnostic maxima reduce
over all accepted windows, not just saved output. Other reducer semantics require
an explicit future contract.

An observation on a shared window boundary is emitted once, by the preceding
window (except the run's initial boundary). Its state is the exact endpoint;
derived controls remain right-continuous. All configured observations are
evaluated and validated even when their output is not retained.

## Explicit local numerical refinement

`resolved_cotransport_water@1` additionally accepts an optional list under
`execution`, for example:

```json
"refinement_times": [6.25e-7, 1.875e-6]
```

Times must be finite, strictly increasing and strictly inside the simulation
horizon. They add exact accepted boundaries to the nominal/event grid. A point
already on that grid is included once; adjacent representable floats remain
distinct. The complete RK4 state advances through each interval, using the same
physical controls, equations, domain checks and conservation tolerances.
Resolution is declared in advance; this is not an adaptive error controller.

Refinement changes the numerical step index but does not change biological event
indices, component-call calendars or random streams. It is stored with the
resolved definition and cannot be changed by checkpoint branching. An omitted
or empty list preserves the previous serialized definition and fingerprint;
source-pinned snapshots still obey their existing installation checks.
Step, trace-storage and padded batch-work limits include the extra boundaries.
Other model definitions, including native BETSE discrete clocks, refuse this
option. See [current qualification and limitations](../PROGRESS.md) before using
it to support a scientific claim; CPU execution tests do not establish GPU
support or resolve the separate depleted-fuel recovery failure.

## Recording policies

| Policy | Saved window payload | Restart state |
| --- | --- | --- |
| `full` | All accepted states and configured observations, in bounded NPZ chunks | Complete initial/final snapshots and explicitly requested snapshots |
| `observations` | Only configured observations, in bounded NPZ chunks | Same complete snapshots |
| `checkpoints` | No trajectory/observation arrays | Same complete snapshots |

Do not masquerade a selected trace as an ordinary full-history `RunResult`.
The existing full-trace API and artifact schema remain available. The new writer
consumes checked windows incrementally. A streamed result returns final state,
aggregate diagnostics, timings and resource measurements, not an accumulated
history. A caller that deliberately retains iterator outputs owns that memory.

## Memory and artifact boundaries

Working arrays scale with window length, model capacity, and the maximum number
of requested observations in a window—not total accepted steps. Definitions and
their event/observation schedules are still resident metadata. A conservative
array estimate includes overlapping windows and observation continuity storage;
it is not a process-RSS, compiler-memory or operating-system allocation limit.
Work remains bounded by the existing global `max_steps` independently of memory.
Dense observation schedules can exceed the array budget and are refused before
execution. This first slice does not subdivide observation batches within a window.

Chunk and optional checkpoint records go to an append-only JSONL index with
individual payload hashes. The final manifest hashes that index and fixed
metadata; it does not accumulate a horizon-length in-memory list of payloads.
Hash files incrementally. Publish the complete manifest last. A failure may
leave partial files and earlier valid complete snapshots, but must not publish
a completed run. Never overwrite or silently repair an output directory.

Recording and window length are run policies, outside the biological definition
and checkpoint state. Changing them on resume is permitted; changing physics or
past controls is not. Existing source/runtime identity checks remain strict.
The accepted 0.8.0 source archive is preserved before production edits; there is
no implicit old-checkpoint migration.

## Acceptance gate

Require all seven model families, irregular event boundaries, differing window
sizes, eager/JIT paths, zero-length continuations, complete replay and future
branches. Compare every saved state/readout against the ordinary full run.
Require identical results across recording policies, refusal of unrecorded
invalid intervals, bounded allocation/resource refusal, failure-safe output and
hash checks. Re-run the prior suite and accepted scalar/cohort regressions.

Measure memory buffers and whole-call costs separately. Windowing may trade
throughput and output overhead for memory; do not claim a speedup without evidence.
CORE-005b separately extends this to independent cohorts. Larger workloads,
GPU placement and fine/coarse exchange remain additional steps.

The first profile confirms constant retained history size as the horizon grows
at fixed window length. For the 100 s, 32-cell graph, 256-step windows reduce
that buffer about 39-fold but increase warm whole-call time about 1.5-fold.
Smaller windows add more overhead. Worker RSS does not fall for every workload.
Retain both full-trace and windowed policies; see the report for exact scopes,
the preserved initial budget refusal and reproducible profile commands.
