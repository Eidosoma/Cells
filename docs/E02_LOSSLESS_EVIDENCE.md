# E02 lossless evidence prototype

D039 / NUM-005c2c, 2026-09-09. The user approved the next slice after
[D038](../reports/NUM005C2B_DIAGNOSTIC_OPTIMIZATION.md): prototype lossless
redundancy removal, verify reconstruction/restart/failure semantics, and measure
complete checked and audited cost on the same short cases. This implements one
option from the [design proposal](E02_COMPACT_EVIDENCE_DESIGN.md), not an adopted
long-study policy. Production, equations and scientific thresholds stay fixed.

## Data policy, not biological model

Choose `full_trace` or `rk4_basis` explicitly per recording instance. Both use
the same immutable classical RK4 kernel, stage and whole-cubic guards, complete
anchored-increment state, exact integer-tick grid and D038 cached readouts.
Do not patch frozen modules or route behavior by assay/cell identity.

| Policy | Stored per window | Reconstructed for readers |
| --- | --- | --- |
| `full_trace` | All accepted states, five slopes and four cubic rows, clocks, anchor/context | Nothing omitted |
| `rk4_basis` | Complete initial/final state, all five slopes per step, clocks, anchor/context | Interior accepted states and all cubic rows |

The basis preserves every passive history coordinate. Reconstruct sequential
accepted updates with the exact pinned expression
`left + h * (k1 + 2*k2 + 2*k3 + k4) / 6`; reconstruct Hermite rows with the
original operation order and stored endpoint slope. No RHS replay, changed
precision, quantization, clipping, sparse observation or omitted stage slope.
Retain complete final window state separately and compare it exactly.

Before writing, decode the proposed payload and match a digest of every logical
array's name, shape, dtype and ordered bytes against the live full window.
Reject any mismatch; there is no fallback to a different policy. Retain that
logical digest alongside the encoded payload hash. Readers verify field/shape
inventories and allocation bounds before loading arrays. Codecs and numerical
acceptance remain distinct: a self-consistent encoding is not proof of a valid
trajectory, and hashes alone do not independently verify a calculation.

All comparison sample arrays, observer flags and D038 readout fingerprints stay
fully retained. Therefore total evidence savings can be much smaller than the
roughly one-half reduction of large trajectory arrays. The prototype does not
promise that lossless compression can fit the original long-study quota.

## Publication, restart and failure boundary

Write an exclusive payload, flush it and synchronize the file and containing
directory on the pinned local Linux filesystem. Complete the window's online
comparison and check the existing score/accounting limits. Only then append
and synchronize a hash-linked commit record binding payload, decoded arrays,
global clocks, prior record and comparison-index prefix. A new numerical carry
must not silently advance the durable committed cursor before this boundary.
The same publication protocol applies to both profile policies.

The maximum comparison score and residual are checked at each window boundary
using the unchanged final acceptance limits. This can stop a failing run earlier
than D038's end-only score decision; it is an explicit failure/publication change,
not a new threshold or modified successful numerical path.

Complete initial/final snapshots remain separate from selected output. Restart
requires a hash-checked committed prefix of a closed successful or failed
attempt, with the same numerical source/runtime identity, case, anchor/context
and original global grid. Recording policy and width may change without changing
that numerical identity. There is no implicit import/migration from older
recorder schemas or candidate-owned phase/preparation transfer in this slice.

On failure, do not retry a failed chunk or overwrite prior evidence. Independently
attempt to retain the last evaluated input/current numerically accepted carry
and any uncommitted validated window, then write a failure receipt identifying
the eligible committed prefix and each preservation error. An uncommitted dump
is diagnostic evidence, not a restart checkpoint. Retain partial files. A
missing closure after process kill or malformed/extra tail is refused for
automatic restart; audited unclean recovery requires a later explicit design.

File/directory synchronization is not a general distributed-filesystem or
power-loss guarantee. This prototype assumes one writer and an unmodified local
filesystem; test interruption and corruption without claiming fault-tolerant
distributed transactions. Per-window records are streamed, but existing quota
tree scans and final inventories remain: numerical windows do not imply constant
total process RSS or metadata cost.

## Tests and registered short measurements

Cover exact full/basis reconstruction, short final steps, one-step windows,
width changes, both cross-policy restart directions at each accepted boundary,
complete passive histories and graph/context identity. Refuse malformed dtype,
shape, allocation, archive members, nonfinite values, forged/reordered/missing
records, wrong source/parent identity, incomplete closure, quota exhaustion and
interrupted payload/index/comparison operations. Independent preservation
attempts must not mask the original error or promote an uncommitted window.

Freeze all new implementation/tests and the [profile inventory](../configs/reference/e02_evidence_profiles_v1.json)
before twelve new sequential CPU float64 workers: full then basis for each of
the six exact D038 cases, 0–5.12 nominal units, step 0.01, width 256. No retry,
refinement, new long implicit integration or long candidate trial. Compare
ordered numerical/sample hashes to D038 and decoded window identities across
both policies. One profile per combination is not a statistical benchmark.

Keep affinity 0–3 and four numerical-library thread counts at 1. Original limits
remain 900 seconds per worker, 3600 per session, one million global steps,
256 MiB estimated arrays and 1 GiB aggregate artifacts. All prior roots occupy
803,085,279 bytes, leaving 270,656,545 for one new root under
`runs/num-005c2c-2026-09-09/`. Account for decode/encode buffers before allocating
them. Emergency records may use the existing 4 MiB tail reserve without raising
the total byte cap; preservation may still fail and must be reported honestly.

## Independent audit and interpretation

Use a separately implemented basis decoder in the read-only auditor, not the
writer's decoder or RK4 stepping function. Recheck decoded digests, stored final
checkpoint identity, stage/update/cubic algebra, domains/accounting, full
comparison grids/samples, scalar readout equivalence and all eight scores.
Verify every commit's comparison prefix and exact D038 ordered evidence.
Algebraic reconstruction is not an independent constitutive evaluation of every
stored stage slope; retain D038's stated scientific limits.

Measure full checked calls, recording/reconstruction sections, raw and actual
compressed trajectory bytes, unchanged comparison bytes, checkpoint/metadata
costs, estimated arrays and process RSS. Report per-policy offline audit time
and checked-plus-audited cost, not just compressed size or writer throughput.
Planning extrapolations are not long measurements or feasibility certificates.

No output reduction, speed result or successful unit test automatically adopts
a long-study policy, selects a timestep, relaxes a cap, removes old evidence or
promotes production graph/GPU/organ work. If this slice still cannot establish
a resource fit, report the remaining runtime/storage gaps explicitly.

## Registered commands

Use the pinned `.venv`, CPU affinity 0–3 and `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` all set to `1`.
Outputs are exclusive: do not rerun or reopen a closed attempt. The first
command archives sources before starting the registered short workers.

```bash
taskset -c 0-3 .venv/bin/python scripts/profile_graph_evidence.py --run --output runs/num-005c2c-2026-09-09/evidence-01
taskset -c 0-3 .venv/bin/python scripts/audit_graph_evidence.py runs/num-005c2c-2026-09-09/evidence-01 --output reports/num-005c2c-audit.json
```
