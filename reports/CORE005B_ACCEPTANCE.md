# CORE-005b: bounded independent-world cohorts

Cells 0.10.0, 2026-09-08. CORE-005b / VERIFY-010 / PERF-003 / D029.
Implementation, numerical acceptance, isolated CPU profiling and the final
handoff audit pass. The existing seven CPU float64 models are
unchanged. This is execution/storage engineering, not a new biological model.

## Delivered contract

The [windowed cohort guide](../docs/WINDOWED_WORLDS.md) documents the CLI and
Python APIs. The implementation uses the existing guarded compiled independent
world kernel on bounded rounds, with each world's original accepted intervals.
There is no union of event times, shared biological clock or extra numerical step.
Finished worlds remain in complete cohort checkpoints without RHS evaluation.

Parameters and active masks are prepared once per run; final device state carries
between rounds. At most two compiled widths are retained within the run. All
ordinary model checks, observations, diagnostic ledgers and per-world observation
continuity remain. An endpoint is copied into its host checkpoint so it cannot
retain a view of an old history buffer. Whole-round numerical refusal precedes
output; I/O failures never publish a completed-run manifest.

The new writer shares numeric chunk formatting with scalar windows. It writes one
world/round index, selected full/observed payloads, complete initial/final cohorts,
and optional checkpoints every N completed rounds. Its inventory is O(worlds).
Arbitrary common-time checkpoint queues are deliberately not supported. Resume
can change recording and window width; biological changes use the ordinary
future-branch rules at each world's actual local checkpoint clock.

Aggregate estimates reserve common-width padding, overlapping rounds, complete
state and observation continuity before capacity/control allocation. Whole-horizon
work limits remain in force on restart. Cohort checkpoint validity is separate
from full-history recording budgets; ordinary full-trace APIs retain their guards.
Metadata, compiler caches, caller-retained results and process RSS have different
scopes and are not hard-bounded by the working-array estimate.

## Verification

The full suite passes **1057 tests in 548.34 s**, with no failures, errors or skips;
warnings are errors. [JUnit receipt](core-005b-tests.xml). The 75 new cases cover
all seven families, eager/JIT parity, different dt/events/horizons, inactive cell/
edge/membrane slots, stable IDs and isolation, terminal worlds, exact complete
restart with changed policies, branches, parameter/executable reuse, low-budget
refusal, every pair-model cubic interval, observation continuity, recording,
hashes, CLI paths and failure publication. All 106 Python files pass Ruff lint
and formatting checks; editable installation and dependency consistency pass.

The [acceptance receipt](../runs/core-005b-2026-09-08/acceptance-02/verification.json)
authenticates the implementation and independent serialized-output audit.

| Check | Result |
| --- | --- |
| Ordinary scalar regressions | All 78 accepted trajectories / 3511 state, layout and observation arrays exactly unchanged |
| Ordinary full-batch regressions | 10 batches / 44 worlds / 2042 arrays exactly unchanged |
| Scalar-window recording regression | 1777 chunks, 451325 accepted rows and 558729 observations exactly match their frozen baseline |
| New cohort recording and round restart | 20 runs / 88 world runs / 95 rounds / 254 per-world windows |
| New serialized state and observations | 21197 accepted rows, 38226 observations and 6001 payload-array comparisons exact |
| New complete restart audit | 69 cohort snapshots containing 306 complete scalar snapshots; layouts, anchors, state and clocks checked |
| New explicit file-hash checks | 735 fixed/indexed payload hashes, plus strict recursive snapshot authentication |

The ten original cohort fixtures include all seven families, the fourteen frozen
nominal source cases, the previously qualified source restart and future branch.
Each is also resumed from a newly serialized complete round with a different
window width. Accepted values and observations are compared field-by-field, not
just by final state. The original source branch passes the production branch API
and matches the [previously independently qualified branch](CORE004_ACCEPTANCE.md).
No new native/reference source integration or continuing-agent experiment was run.

Scalar/full-batch regressions use the existing verification driver unchanged.
Their [completed receipt](../runs/core-005b-2026-09-08/acceptance-01/regression/verification.json)
is hash-pinned, re-audited and reused by the final cohort acceptance, not counted
as a second numerical execution. Its scalar recording checks include 2479 file
hashes and 234 snapshots; full batches include 372 file hashes and 88 snapshots.

### Retained acceptance-fixture refusal

The first cohort audit completed the scalar/full-batch regressions and six
original/resumed cohort pairs, then supplied a branch-local event cursor to an
original-protocol checkpoint validator. A new intervention exactly at the branch
time makes those cursors different. Production correctly refused world 101's
inconsistent event position.

The correction constructs the original-protocol **test fixture** clock only after
exact complete-state comparison with the frozen parent, then invokes the unchanged
branch API. No production law, guard, tolerance or schema was changed. The
[failure receipt](../runs/core-005b-2026-09-08/acceptance-01/failure.json) and
[attempt source capsule](../runs/core-005b-2026-09-08/acceptance-01/attempt_sources.zip)
are retained. The twelve completed cohort runs from that attempt are excluded
from final accepted cohort totals; its independently completed regressions remain
accepted and are explicitly referenced. No failed run is labelled complete.

## Preserved source and checkpoints

Accepted 0.9.0 was archived before any production edits:
[source archive](cells-0.9.0-source.tar.gz), SHA-256
`08d9b5b2b3288055ca5d356d3b0cb2e3fa169b156a781677a43c09825e964874`.
All 37 archived production hashes equal the accepted 0.9.0 release identity.
All **342 accepted scalar snapshots and 10 enclosing cohort snapshots** load
under that source; old-source source-pair window replay is exact across every
accepted state and observation. Current source refuses both old scalar and cohort
checkpoints, with no implicit migration.
[Archive audit](../runs/core-005b-2026-09-08/acceptance-02/archived-09-audit.json).
The reused regression also reverified archived 0.8.0's 434 accepted snapshots and
exact replay. Old-source replay outputs are excluded from current-version totals.

Current production has 39 modules. Two are new: the cohort window executor and
writer. Seven existing modules changed: version, CLI, batch snapshot guards,
branch budget validation, shared segment analysis, shared window validation/
continuity, and shared chunk writing. Model, process, coupling, numerical-method
and observer module hashes are unchanged. The accepted
[49-file implementation capsule](../runs/core-005b-2026-09-08/acceptance-02/implementation_sources.zip)
includes all production code, verification/profile drivers, new tests, packaging
and the unchanged dependency lock.

| Evidence | SHA-256 |
| --- | --- |
| Final cohort acceptance | `57f93deca4cfde86976c3c10f004ca0c468a76e0d0d386697d49275a18028954` |
| Reused scalar/full-batch regression | `128e3950890063353fb13cf542b4c3b7c59018ec6377aea664903338ca5fa36b` |
| Implementation capsule | `2e96a7b65ebe35b06d714a5458a61d99fd06131a6915a67a53b5e6a8225f4083` |
| Archived 0.9.0 audit | `7811bb7709b659fe8e54aa8cca8261b0c3040889cf922bef679283ce25d5f126` |
| Full test receipt | `ec25013e9051c673aa8fc2ffb9f88c0e5dc17f1ddaf1d101251cdfcc1ae80821` |
| Retained fixture-failure receipt | `b959a19e027609f19f78e27f7c6dfbb78ab3664193292fbbf71ac6ba5ff28761` |

Python 3.13.5, JAX/JAXlib 0.11.1, NumPy 2.5.3, CPU float64. No dependency or
precision change. Archive replay uses the preserved source via `PYTHONPATH` and
the same compatible numerical environment, not a new editable installation.

## Bounded CPU profile

The profile ran after numerical verification completed. Sixteen sequential
fresh workers compare 4/16-world, 32-cell reaction/transport graphs over 10 seconds
and nominal source pairs over 10 source-time units. Modes are ordinary full batch,
sequential scalar 256-step windows, and cohort 32/256-step windows. Every mode uses
the same definitions, dt 0.01 and four observation times. Each world declares a
128 MiB working-array budget; cohorts declare 512 MiB. All combinations passed
preflight before timed workers started.

Each worker measures a cold call, performs a fresh-state untimed warm-up, and
measures three fresh-state warm calls. Timed peak RSS is captured before extra
untimed full-trajectory digests, artifact writing and snapshot loading. Full-field
trajectory digests and final states must match across modes. Timings distinguish
preparation, compilation/cache use, synchronized execution, host transfer/assembly,
analysis and whole calls. Output-plus-parity timing is not pure filesystem cost.
Sequential scalar history memory is a one-world peak, not a simultaneous cohort
allocation. Shared-host CPU timings establish no general speedup or GPU result.

All sixteen workers pass, with identical full-trajectory field digests and final
states across all modes. They retain 1316 payload-hash checks and 320 complete
scalar snapshots. [Profile receipt](../runs/core-005b-2026-09-08/profile-01/verification.json),
SHA-256 `706d8dbb83a3ae86c2fbc75a33bb7c4c4f5247e6b4e811a46fd5aad2450f5c8a`.

Median warm whole-call milliseconds; each entry is three samples in its own
fresh worker, using CPU affinity 0–3:

| Ten-unit workload | Full batch | Sequential scalar, width 256 | Cohort, width 256 | Cohort, width 32 |
| --- | --- | --- | --- | --- |
| 32-cell graph, 4 worlds | 78.391 | 129.317 | 89.787 | 217.243 |
| 32-cell graph, 16 worlds | 282.645 | 519.804 | 338.168 | 763.528 |
| Nominal pair, 4 worlds | 173.112 | 275.935 | 238.660 | 1014.414 |
| Nominal pair, 16 worlds | 560.907 | 1120.918 | 897.605 | 3767.318 |

Actual peak host history array bytes (accepted times plus typed state, excluding
observations, layout, runtime/compiler overhead and overlapping result lifetimes):

| Workload | Full batch | Cohort, width 256 | Cohort, width 32 |
| --- | --- | --- | --- |
| Graph, 4 worlds | 5103264 | 1307616 | 167904 |
| Graph, 16 worlds | 20413056 | 5230464 | 671616 |
| Nominal pair, 4 worlds | 994976 | 254944 | 32736 |
| Nominal pair, 16 worlds | 3979904 | 1019776 | 130944 |

On these horizons, width 256 reduces cohort history by **3.90×**, width 32 by
**30.39×**. The sequential scalar mode has a one-world peak of 326904 bytes for
the graph and 63736 for the pair; it never holds all world histories together.
Fixed-window storage scales with simultaneous world count. Unit tests and the
[preceding horizon profile](CORE005A_ACCEPTANCE.md#bounded-cpu-profile) establish
the separate horizon-scaling behavior; this profile varies world count and width.

Width-256 cohorts finish about 1.44–1.54× faster than sequential graph windows and
1.16–1.25× faster than sequential pair windows here. They remain **1.15–1.20×
slower than full graph batches** and **1.38–1.60× slower than full pair batches**.
Width 32 increases whole-call cost further despite smaller history buffers. These
are policy trade-offs, not a universal performance improvement.

Total process memory tells a different story from history arrays. At 16 worlds,
timed peak RSS is 322.9 MiB for the full graph, 301.4 MiB at width 256 and 281.4 MiB
at width 32. For source pairs it is 344.5, 362.9 and 352.5 MiB respectively: no
RSS reduction. The four-world graph also has slightly higher cohort RSS. Compiler
and runtime memory remain material; bounded arrays are not a hard process limit.

At 16 worlds/width 256, each run prepares 16 parameter sets and uses two compiled
widths over four rounds. Median graph preparation/execution/analysis is roughly
104/104/120 ms; the source pair is 213/181/493 ms. Those component medians need not
sum to the median whole call. Source analysis still dominates, so prepared device
carry is useful infrastructure but does not remove host observers or full-grid
preflight. Cold whole calls are about 1.88 s (graph) and 4.54 s (pair) in these two
workers. No GPU mapping or new numerical approximation is justified by this alone.

## Final handoff audit

The [cross-suite audit](../runs/core-005b-2026-09-08/release-audit.json) rechecks
source/runtime identities, all archived/current capsule contents, indexed and
fixed payload hashes, test evidence and every accepted current checkpoint.
It covers **370 saved world-run records**, **948 complete scalar snapshots** and
**99 enclosing cohort snapshots**. The acceptance/profile receipts account for
4902 explicit file-hash checks, with strict snapshot authentication in addition.
The 370 records comprise 122 scalar/full-batch regression worlds, 88 cohort
acceptance/restart worlds and 160 saved profile worlds; repeated timing calls are
not counted as additional saved runs. Exclusions and the reused regression root
are explicit in the audit.

Audit SHA-256: `94d8ee4500f91fb6fb5506085c515944ad235e7d42318430d11d85e41b74da4e`.
All 39 production hashes and the 49-file acceptance capsule remain unchanged
after verification. Documentation links, tables, fences and whitespace were
checked; no further production edits were needed after the passing suite.

## Reproduce and next step

Choose new output directories. Do not run the profile alongside verification:

```bash
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
taskset -c 0-3 .venv/bin/python -W error scripts/verify_batch_windows_build.py --output runs/my-cohort-window-acceptance
taskset -c 0-3 .venv/bin/python scripts/profile_batch_windows.py --preflight-only
taskset -c 0-3 .venv/bin/python -W error scripts/profile_batch_windows.py --output runs/my-cohort-window-profile
```

The verifier can reuse a completed regression only with both `--regression PATH`
and `--regression-sha256 EXPECTED_SHA256`. It checks source/runtime and capsule
identity, re-audits all scalar chunk values and the full-batch payloads, and records
the reused receipt. The default command independently regenerates everything.

Next return to the selected longer E02 switching **protocol/qualification gate**:
pin preparation, controls, observation criteria and an independent reference
before expanding biological claims. M1 and M1c stay open. These independent
worlds are not interacting organs; GPU/vectorized guards, fine/coarse exchange,
multirate integration, memory/relay boundary operations and endogenous cancer
mechanisms remain separate work. No physical EMT calibration, full Levin-assay
parity, paper-table reproduction, Plastic Heredity or organ result is claimed.
