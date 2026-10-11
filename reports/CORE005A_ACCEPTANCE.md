# CORE-005a: bounded single-world execution

2026-09-08 UTC. Cells 0.9.0, D028 / CORE-005a / VERIFY-009 / PERF-002.
The [window contract](../docs/WINDOWED_EXECUTION.md) is implemented on the
ordinary numerical path. This is an execution/storage release, not an eighth
model, new Levin assay, organ, multirate scheme or GPU result.

## Delivered behavior

Single-world windows retain at most a bounded piece of the accepted trace.
The indexed event grid stores only off-nominal event metadata, preserving the
existing float `i * dt` clock, exact events and global checkpoint positions.
The original full-trace and independent-world batch APIs remain available.

Full, observation-only and checkpoint-only recording are separate run policies.
All model-supported interval and observation checks still run, including
cross-window sampled-state/accounting continuity. Typed diagnostic ledgers and
fixed anchors remain in every complete checkpoint. Observations never insert
solver steps. The disk writer uses bounded NPZ chunks and an incremental hashed
JSONL index; it publishes the completed manifest last and never overwrites output.

No model law, RK4 function, observer formula or dependency changed. The four
changed existing production modules are package version, CLI, runner and I/O;
three new modules implement the lazy grid, windows and incremental writer.
There are 37 production Python files. Snapshot validation no longer requires a
full-horizon trace reservation; the ordinary full-run budget remains enforced.

## Tests and accepted-trajectory regression

The full CPU suite passes **982 tests in 446.58 s**, warnings treated as errors:
[JUnit receipt](core-005a-tests.xml), SHA-256
`c463618705fb03e28ee1c39a8bcbd5fc418c3773ca215fa465c4b164b913ead7`.
There are 86 new tests covering all seven models, eager/JIT execution, widths
1/7/1000, irregular events, exact/off-grid observations, complete resume with
changed recording/window size, future branches, terminal continuations, strict
resource/type refusals, read-only arrays and incomplete-output failure behavior.

The suite also checks float-product collisions, subnormal and underflowing time
ratios, a billion-step indexed grid without allocating its times, and a small
window run/restart whose definition is refused by the full-trace memory guard.
Both pair observers still inspect every cubic interval when no output samples
are retained. Injected hidden interpolation and numerical-state failures prevent
publication of a complete run under every recording policy.

[Acceptance receipt](../runs/core-005a-2026-09-08/acceptance-01/verification.json),
SHA-256 `2e536f49bc16ca456482bbab288d404bede0168b792192a681d5fcebcd8fb502`:

- All 78 accepted 0.8.0 scalar trajectories and **3511 arrays** are exactly
  unchanged under ordinary 0.9.0 execution. The same runs, including continuations
  and already-qualified branches, are saved through 257-interval windows and
  compared element-for-element with their archived baseline arrays.
- Those windowed artifacts contain **1777 windows, 451325 accepted rows and
  558729 observation rows**. Every serialized state/readout, complete initial/
  middle/final snapshot, global index and diagnostic maximum is audited.
  There are 234 complete snapshots and 2479 payload-hash checks.
- All 10 accepted independent-world batches / **44 worlds / 2042 arrays** are
  exactly unchanged. Their 372 enclosing payload hashes and final cohort
  restoration pass. These batch runs still use full histories, not windows.

This includes the frozen physical-cell, physical-pair and all 14 nominal
source-pair cases inherited from accepted 0.8.0 evidence. No new native reference
solve was used, and no accuracy target was changed. The acceptance driver reads
old full traces for comparison; that verification-only memory use is not the
production window runner's memory profile.

The [43-file implementation capsule](../runs/core-005a-2026-09-08/acceptance-01/implementation_sources.zip)
has SHA-256 `6f546ed8c2eca6eefe79f8a6d2d88270bdecbba6175c2a100a8dd0fcd702951c`.
The receipt records every member hash, including all 37 production files.

The final [handoff audit](../runs/core-005a-2026-09-08/release-audit.json)
rechecks the capsule against the current tree, all 2969 accepted payload hashes
and all **342 current complete scalar snapshots** across 134 saved world-run
records (78 windowed, 44 batch-world and 12 profile records). The archived replay
and initial profile refusal are retained separately, not added to those counts.
Ruff lint/format pass on all 100 Python files; local documentation links, tables
and code fences were checked.

## Preserved source and checkpoints

Accepted 0.8.0 was archived **before production edits**, after matching its 34
production hashes to the prior release audit:
[source archive](cells-0.8.0-source.tar.gz), SHA-256
`5f49ac0fde1af95b47977d6310f9e4eeddc048456006d21a9ba7c30d4449bdad`.

[Archive audit](../runs/core-005a-2026-09-08/acceptance-01/archived-08-audit.json),
SHA-256 `afa4f0359b5d1a4c4b6077e93611f74b61b711cc180fb3ee3dde3f2d8321f4f5`:
all **434 accepted old scalar snapshots** load through the archived engine;
source S01 continuation from 5 to 10 nominal units exactly matches all state and
observation arrays. The current engine correctly refuses implicit old-source
restoration. The old-version replay is retained separately and not counted as
a current-version simulation. There is no automatic checkpoint migration.

The acceptance driver's explicit old-array-to-test-fixture conversion is solely
a regression test. It is not a production bypass of source/runtime identity.
Archive replay uses an isolated temporary extraction and the same pinned Python
environment; all preceding version archives remain preserved.

## Bounded CPU profile

The profile compares ordinary full traces with 32- and 256-interval windows in
separate sequential workers. Workloads are the existing 32-cell reaction/
transport chain (1 and 100 s) and nominal source pair (1 and 10 source units),
with the same dt, controls and four observations across recording policies.
Each worker has a cold call, untimed warm-up and three warm calls starting from
the original state. A separate untimed digest pass compares every accepted
state/observation value; timed-call peak RSS is captured before that pass and
artifact writing. CPU affinity is 0–3; no concurrent verification or GPU jobs.

The first attempt is retained as
[profile-01 refusal](../runs/core-005a-2026-09-08/profile-01/failure.json).
Three short graph workers completed, then the 100 s full run correctly exceeded
its inherited 64 MiB budget (event-split estimate 101494624 bytes). Its log and
pre-change driver capsule remain in place. The subsequent comparison declares
the same **128 MiB working-array budget for all policies**, with no equation,
dt, horizon, observation or production-guard change. A working-array estimate
is not a hard worker-RSS or compiler-memory limit.

[Completed profile](../runs/core-005a-2026-09-08/profile-02/verification.json),
SHA-256 `454ff262452f7e28cc0d690d374c65b109b1d72a723183c6ea031ccd43dbcbc2`:
all 12 workers pass, with **identical complete-trajectory digests** across
policies. All 118 worker payload hashes pass. The driver SHA-256 is
`480ba0ed0d4dd3e9b899666b8625663cb05656515b43ace2dd3bfdf52459b007`.

Warm whole-call times exclude recording; history bytes include accepted times,
not observations, temporary arrays, compiler/runtime storage or artifacts.

| Workload / horizon | Full call / history | 256-step call / peak history | 32-step call / peak history |
| --- | --- | --- | --- |
| 32-cell graph, 1 s | 7.65 ms / 131016 B | 8.16 ms / 131016 B | 18.98 ms / 41976 B |
| 32-cell graph, 100 s | 197.54 ms / 12723816 B | 301.19 ms / 326904 B | 1111.65 ms / 41976 B |
| Source pair, 1 nominal unit | 17.59 ms / 25544 B | 17.84 ms / 25544 B | 53.17 ms / 8184 B |
| Source pair, 10 nominal units | 37.68 ms / 248744 B | 72.50 ms / 63736 B | 352.67 ms / 8184 B |

The longer graph's 256-step buffer is **38.9× smaller**, while whole calls take
1.52× as long. Its 32-step buffer is 303× smaller but calls take 5.63× as long.
At fixed 32-step windows, increasing the graph horizon 100-fold or pair horizon
10-fold leaves the peak accepted-history buffer unchanged. This establishes
bounded retained arrays, not constant work or a throughput improvement.

Timed-worker peak RSS for the long graph is about 302.2 MiB (full), 240.4 MiB
(256) and 244.5 MiB (32). For the 10-unit pair it is 289.7, 315.7 and 318.2 MiB:
smaller trace buffers do **not** imply lower process RSS on every workload.
Imports, allocator/compiler caches and an extra compiled tail shape matter.
These are shared-host CPU measurements with three warm samples, not a hardware
capacity forecast or hard memory guarantee.

Host preflight, preparation, repeated compilation/cache calls, transfers and
model observers remain visible costs. On the long graph the 32-step preflight
takes about 108 ms and ordinary per-window analysis about 211 ms. On the long
pair they take about 51 and 163 ms. The synchronous observation-only recording
sink takes roughly 5.7/25.2 ms for the long graph at 256/32 steps and 3.6/7.3 ms
for the long pair. Those one-off sink timings exclude initial/final snapshot
publication, manifest finalization and some host bookkeeping; they are not a
standalone filesystem benchmark. Full-call timing also includes continuity
checks and iteration overhead beyond the named window components.

Use the ordinary full runner when memory is affordable and small-job throughput
matters. Use windows when bounded retained state or selective output is needed;
256 is a starting policy, not a universal optimum. Amortized preparation and
windowed cohorts should precede a GPU performance claim.

## Reproduce

Use the existing CPU environment: Python 3.13.5, JAX/JAXlib 0.11.1, NumPy 2.5.3,
SciPy 1.18.1, ml_dtypes 0.6.0, opt_einsum 3.4.0. The dependency lock is unchanged.
Only the editable Cells package metadata was refreshed to 0.9.0.

```bash
.venv/bin/python -m pip install --no-index --no-build-isolation --no-deps -e .
.venv/bin/python -m pip check
taskset -c 0-3 .venv/bin/python -m pytest -q -W error --junitxml=reports/core-005a-tests.xml
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
taskset -c 0-3 .venv/bin/python scripts/verify_windows_build.py --output runs/my-window-acceptance
taskset -c 0-3 .venv/bin/python scripts/profile_windows.py --output runs/my-window-profile
```

Use new output paths; do not overwrite the accepted evidence. Run the profile
separately from the suite/acceptance workload. Each profile/archive subprocess
has a 120-second limit. No research-lane environment, upstream checkout or
continuing-agent experiment is changed.

## Next engineering boundary

CORE-005b: windowed independent-world cohorts, preserving world-local clocks,
aggregate memory/work guards, complete cohort restart and failure semantics.
Keep the ordinary scalar path for small jobs. The first window implementation
repeats some host preparation/observer work and is not a throughput optimization.
Resident event/observation definitions, JAX compilation caches, Python overhead
and filesystem storage are outside the bounded trajectory-array guarantee.
Dense observations in one window may still exceed the declared budget.

Windowing does not reduce biological integration work or establish organ-scale
feasibility. GPU placement, vectorized guards, multirate integration, fine/coarse
exchange and interacting organ interfaces remain separate qualifications.
Longer selected E02 switching and memory/relay protocols remain science work;
no full Levin-assay, cancer-expression or plastic-heredity result is claimed.
