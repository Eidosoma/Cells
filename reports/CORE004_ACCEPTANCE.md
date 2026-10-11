# CORE-004 acceptance and first CPU profiles: Cells 0.8.0

Date: 2026-09-08 UTC. Independent-world execution is implemented and verified
across all seven model families. This adds an execution capability, not an eighth
biological model, coupled organs, multiscale reduction or GPU execution. See the
[run guide](../docs/INDEPENDENT_WORLDS.md) and [progress](../PROGRESS.md).

## Delivered engineering and tests

Each world owns its state, parameters, layout, IDs, controls and original
event-split clock. Compatible shapes are stacked for conservative compiled
mapping; unequal timesteps, events, horizons and restart clocks do not cause
cross-world integration changes. Masked terminal storage never advances biology
or calls a completed world's RHS. All model equations and shared RK4 functions
are unchanged. Scalar resource estimation was extracted into a shared helper
without changing its arithmetic or scalar results.

The first policy is `lax_map`, deliberately not unqualified vectorization of
conditional numerical guards. Existing stage, endpoint, history, accounting and
observation checks still apply to each world. A failing world refuses the batch;
no partial cohort is published as complete. Aggregate work and conservative
array-storage guards precede timeline/capacity allocation. They do not impose
a hard process-RSS/compiler bound or solve full-history memory scaling.

Batch definitions wrap complete ordinary simulation definitions. Batch snapshots
wrap ordinary per-world snapshots with checksummed world ownership and definition
identity. Saved definitions govern resume; future branches must pass the original
per-world branch restrictions. World reordering uses IDs rather than slot guesses.
Individual scalar artifacts remain usable, and no snapshot migration is implicit.

All **896 tests passed in 388.65 seconds**, with warnings treated as errors:
the previous 852, 43 new batch unit tests and one fresh-process CLI case.
The [JUnit record](core-004-tests.xml) has SHA-256
`4ebe4cc5af93712ff24fe08af83114571aeae979eaf8a9f6aa9cf5d4498edf47`.

New checks cover all seven families against scalar execution, complete histories
and observations, independent event clocks and parameters, world renaming/order,
unchanged neighbors after one-world intervention, unequal horizons, eager/JIT,
cell/edge/membrane padding, ragged and final-only replay, ordinary future branches,
resource refusals, corruption and non-overwriting output. A guarded log-domain
test under JAX's NaN checks confirms that rejected trials and an already finished
world do not evaluate invalid RHS expressions. Three-repeat timing diagnostics
are verified to return the same single biological trajectory.

## Batch numerical acceptance

The [acceptance driver](../scripts/verify_world_build.py) writes 10 batches with
**44 saved world runs**. Six earlier model families are compared with ordinary
scalar runs; a single independently clocked source batch contains all 14 frozen
NUM-004 cases. It compares directly with the unchanged refined Radau arrays,
not newly fitted endpoints or labels. A separate two-world future branch is
checked against fresh independent refined Radau solves under its full protocol;
the definitions, comparison arrays, solver states and statistics are retained.

The largest frozen-source normalized error is **0.0271018**, against a limit
of one. The largest independent branch score is **0.000234721**. Independent
typed source accounting remains below **6.61617e-13**, against 2e-9 in each
coordinate's units. These are bounded sampled checks, not long-time, arbitrary-
parameter or continuous-error guarantees. Nominal source time is not seconds.

All 14 source-world histories and requested readouts replay exactly from saved
cohort checkpoints. The acceptance verifies 377 enclosing-batch payload hashes
and 90 complete scalar snapshots; a separate replay cohort contains another 14
snapshots. It preserves 50 implementation/reference/configuration files,
including all 34 production source files. No equation, reference input or
numerical target was relaxed.

The [acceptance receipt](../runs/core-004-2026-09-08/acceptance-01/verification.json)
has SHA-256 `589f9379dada33cbc7240b7e198f492637054872311f5077ad6c55f4de690187`.
The [implementation capsule](../runs/core-004-2026-09-08/acceptance-01/implementation_sources.zip)
has SHA-256 `356f85ca14355e38189fc8b3466ce14af7a1b21fa2ee605dd72793eb5f802108`.

## Previous models and preserved source

All six preceding scalar suites and the nominal source-pair suite were regenerated
under 0.8.0. Their independent reference/refinement/replay checks pass. A separate
direct [regression audit](../runs/core-004-2026-09-08/scalar-regression-audit.json)
compares every saved numeric array with accepted 0.7.0: **78 trajectories and
3511 arrays are exactly unchanged**, including inventory, shape and dtype.
It verifies 642 payload hashes and 204 snapshots. Its SHA-256 is
`b5b0f15590e9c9e1f9a10c5e8270f2b9a2d90a20d738a2843317e81c929dab8d`.

Before production edits, accepted 0.7.0 was preserved in
[cells-0.7.0-source.tar.gz](cells-0.7.0-source.tar.gz), SHA-256
`06a8336a2555452c8e9caea5c426a904b03f35ffaabeabf23f6faa480b945b29`.
All 31 archived source hashes match the accepted release. In a temporary source
tree using the compatible existing runtime, all 204 old snapshots load and the
source-pair five-to-ten-unit replay reproduces state and readouts exactly.
Current 0.8.0 refuses those old source identities. The
[archive audit](../runs/core-004-2026-09-08/archived-07-audit.json) has SHA-256
`2c1289168bb74cc625eb7b81e8d472dbd66b33a5ddc0c11b6c87c2d9e86ff03e`.

To inspect old snapshots, use the archive's `src` via `PYTHONPATH` in a separate
temporary extraction, with the matching runtime. Do not overwrite current source
or edit checkpoint hashes/version fields. The previous-suite driver also rechecks
the older 0.6.0 archive and its exact physical-pair replay. No historical run was
deleted or relabeled as current-source output.

## Bounded CPU profile

The [profile driver](../scripts/profile_worlds.py) ran **12 sequential fresh
worker processes**, separately from our verification jobs, on CPU cores 0–3.
Each workload uses 1, 4 or 16 worlds, comparing scalar calls in sequence with
one compiled map. Each worker records a cold call, an untimed warm-up and three
warm whole-call measurements, always from the same original state. Device work
is synchronized by the public runners before timing ends. Repeated trajectories
are exact; every scalar/batch saved array in this panel is also exactly equal.

The workloads are a 32-cell two-species reaction/transport chain with independently
controlled contacts, and the frozen S13 nominal source pair. Each uses 102
accepted steps and four observation times. This is deliberately a small CPU
baseline, not a tissue, large-GPU, long-horizon or realistic relay workload.
The host is shared; three samples establish no statistical/general speedup claim.

All entries below are warm medians in milliseconds. A full call includes host
preparation, cache lookup, synchronized kernel execution, transfer and model
checks/observations; it excludes artifact writing. Scalar entries include all
world calls in sequence. Kernel entries exclude host setup and observations.

| Workload | Worlds | Scalar kernel | Batch kernel | Scalar full call | Batch full call |
| --- | ---: | ---: | ---: | ---: | ---: |
| 32-cell graph | 1 | 1.766 | 2.389 | 8.536 | 15.734 |
| 32-cell graph | 4 | 6.976 | 5.444 | 32.088 | 35.947 |
| 32-cell graph | 16 | 27.604 | 12.603 | 129.116 | 106.097 |
| Source pair | 1 | 2.311 | 12.511 | 18.371 | 56.876 |
| Source pair | 4 | 9.209 | 16.830 | 72.909 | 105.218 |
| Source pair | 16 | 36.191 | 31.174 | 281.132 | 289.568 |

At 16 worlds the graph's kernel/full-call ratios favor the batch by about
**2.19× / 1.22×**. The source pair's kernel ratio is about **1.16×**, but its full
call is slightly slower (**0.97×** scalar-to-batch ratio). Smaller batches are
slower overall. Conservative mapping is not parallel execution across worlds;
these measurements do not justify automatically batching every small job.

Cold batch compilation is about 0.64–0.82 seconds for the graph and 1.79–1.93
seconds for the source pair in these fresh workers. Cold observation/check work
can also include lazy backend setup; it is not a pure NumPy-only cost. The
separate warm samples avoid attributing those cold costs to steady execution.

At 16 worlds, graph host histories occupy 2083072 bytes (about 1.99 MiB), compared
with 395520 bytes (about 0.38 MiB) for source pairs. Whole-worker peak RSS is about
270 and 330 MiB respectively, including imports, compiler, repeated results and
output work. The compiler's argument/output/temporary estimates are saved
separately; they are not live RSS. Source compiler argument bytes can be smaller
than supplied input arrays because unused fields can be eliminated.

Writing the 16-world batch artifacts takes about 0.89 seconds for the graph and
1.04 seconds for the pair, with about 4.39 MB and 1.69 MB of output. These are
prototype NPZ/JSON writes including complete individual and cohort checkpoints;
they are not like-for-like storage optimization comparisons or filesystem
benchmarks. Host preparation/observers and output are substantial costs even
when the numerical kernel improves. Full histories still grow with worlds and
steps; the current profile does not demonstrate large-organ memory feasibility.

All worker measurements, configurations, actual array/output bytes, peak RSS,
source/runtime identity, affinity and payload checksums are retained. The
[profile receipt](../runs/core-004-2026-09-08/profile-01/verification.json) has
SHA-256 `8738b9076fa54274ba2b8f0fd09e95ee67476a8afc47cd2b63901e80d356d36f`.
Its driver SHA-256 is
`251da80e96bc48a54ed6f19c3ed2e424a51bcaeb74e85a08482a248a7d2f2467`.
No performance threshold was imposed or weak result removed.

## Final audit, environment and reproduction

The final [release audit](../runs/core-004-2026-09-08/release-audit.json), SHA-256
`6a166ea315a33fbb24e85b93b4f548b08c1dabf7ac13766a0f4a82ce74201b96`, checks
**206 saved current-version world-run records and 434 scalar snapshots** across
batch acceptance, scalar regressions and profiles. The separate historical
archive replays are not included in that count. All 34 current source hashes,
50 capsule files and retained evidence identities match. The profile audit
checks all 618 worker payload hashes, including complete cohort snapshots.

Environment: Linux x86_64, Python 3.13.5, JAX/JAXlib 0.11.1, NumPy 2.5.3,
SciPy 1.18.1, CPU float64 and no RNG. The dependency lock is unchanged; only
editable package metadata was refreshed to 0.8.0. All 93 Python files pass lint
and formatting checks; dependency and scoped whitespace checks pass. Numerical
tests and acceptance overlapped, so the full-suite elapsed time is not a profile.
Documentation checks pass for 39 Markdown files, 71 tables and 587 local link
occurrences, including heading anchors, with no unresolved targets.
No new dependency, GPU job, native BITSEY capture or continuing-agent experiment
was introduced. The pinned source tree was not modified.

From Cells, use new output directories. Reference acceptance requires the retained
MODEL-005/NUM-004 artifacts, whose hashes are checked before use. The profile
needs no upstream checkout or network and bounds each worker to 120 seconds.
Run it separately from other verification workloads on the selected cores.

```bash
taskset -c 0-3 .venv/bin/python -W error -m pytest -q --junitxml=reports/core-004-tests-rerun.xml
taskset -c 0-3 .venv/bin/python -W error scripts/verify_world_build.py --output runs/my-world-acceptance
taskset -c 0-3 .venv/bin/python -W error scripts/verify_previous_models.py --output runs/my-world-previous
taskset -c 0-3 .venv/bin/python -W error scripts/verify_source_pair_build.py --output runs/my-world-scalar-source
taskset -c 0-3 .venv/bin/python -W error scripts/profile_worlds.py --output runs/my-world-profile
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

## Next engineering step

CORE-005 should first specify bounded windows and selectable recording, retaining
full restart state, every interval's domain checks, exact event clocks, read-only
observations and typed history accounting. Measure plan reuse, observation work
and output separately; do not bypass checks for benchmark gains. Later vectorized
mapping needs explicit guard/refusal qualification, and GPU/distributed/fine-coarse
interfaces require their own workloads and accuracy checks.

M1 remains open for longer selected E02 switching. Memory/relay protocols,
donor-removal operations and cancer-expression strategies remain separately
pinned science gates. No biological memory, organ functionality or full Levin-
assay claim follows from independent-world execution.
