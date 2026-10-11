# NUM-005c2e: immutable integration-side evaluation

D041, 2026-09-09. Short engineering prototype; not long-time candidate
qualification or a production change.

## Scope and acceptance

The [frozen plan](../configs/reference/e02_evaluation_profiles_v1.json) and
[evaluation contract](../docs/E02_INTEGRATION_EVALUATION.md) compare an explicit
frozen scalar evaluator with an immutable scalar cache. All prior equations,
RK4 updates, stage/domain/accounting and whole-cubic checks, logical comparison
evidence and checkpoint-publication rules remain unchanged.

The cache stores fixed diffusion/geometry factors, pump eligibility, bath
values and Snail-only regulatory factors. Complete derivatives retain all six
coordinate blocks. No state-dependent constitutive value is cached. Changed
controls require a new instance, and evaluator identity is part of the
numerical restart contract. Same-evaluator restarts can change lossless
recording representation and window width; cross-evaluator restarts fail closed.

Pre-registration probes cover all 45 frozen graph fixtures, eight perturbed
primary states and both absolute/increment coordinate modes. The 1,440 prepared
complete derivatives and 720 decomposed evaluations are bitwise identical to
the frozen graph equations. These finite probes are not a proof for every
admissible state, parameter panel or runtime.

An initial exploratory timing check found no benefit from reusing D038's
batched readout cache with a batch of one. Scalar profiling instead motivated
hoisting fixed subexpressions and replacing generic indexing-based derivative
assembly with direct concatenation. No algebraic reassociation or edge-order
change was introduced.

## Registered measurements

The root is
[runs/num-005c2e-2026-09-09/evaluation-01](../runs/num-005c2e-2026-09-09/evaluation-01).
It retains an exclusive 74-source archive: all 68 D040 sources plus six new
files. Twelve profiles cover prepare E/M and both directions of active and
one-neighbor switching, with both scalar policies. Each uses duration 5.12,
step 0.01, 512 steps, and recording width 256.

Both policies use the same `rk4_basis` trajectory, `trajectory_backed`
comparison and `batched_cached` readout policies. Complete checked timing
includes model/cache preparation, stage and whole-curve checks, reference
comparisons and checkpoint publication. Separate 256-call cProfile diagnostics
are initial-state RHS-only measurements; their cost remains in worker/session
totals, not the checked trajectory timer. The scalar baseline uses the same
prepared interface and timing instrumentation around the original evaluator.

One ordered profile per case/policy is not a statistical benchmark. Timing
differences are observations in this pinned environment, not a general
performance guarantee.

All twelve profiles completed. Totals across the six cases per policy:

| Measurement | Frozen scalar | Cached scalar |
| --- | --- | --- |
| Complete checked time | 23.1644 s | 22.4919 s |
| Per-profile independent audit time | 52.7946 s | 52.7806 s |
| Checked plus per-profile audit time | 75.9590 s | 75.2725 s |
| RHS call time, included above | 5.8103 s | 5.0026 s |
| Integration plus stage checks, included above | 8.7917 s | 8.0251 s |
| Whole-cubic checks, included above | 10.2340 s | 10.2870 s |
| Comparison and sample recording, included above | 2.9473 s | 2.9822 s |
| Window recording, included above | 0.3466 s | 0.3536 s |
| Measured model preparation, included above | 0.0073 s | 0.0077 s |
| Profile artifacts before timing receipts | 1,600,103 bytes | 1,600,201 bytes |
| Compressed trajectory payloads | 1,166,247 bytes | 1,166,247 bytes |
| Comparison artifacts, including metadata | 243,208 bytes | 243,211 bytes |
| Separate complete checkpoints | 13,078 bytes | 13,078 bytes |
| Separate cProfile artifacts | 29,576 bytes | 29,672 bytes |
| Process high-water RSS range | 89,313,280–99,504,128 bytes | 89,460,736–99,225,600 bytes |

The cache reduces RHS time by **13.9%**, integration-plus-stage-check time by
**8.7%**, and complete checked time by **2.9%** in these measurements. Individual
checked reductions range from 1.7% to 4.8%. Whole-cubic checks still consume
45.7% of cached checked time; this result does not make the long study feasible.
RHS timing is nested inside integration timing, and preparation/sections are
subsets of checked time, not additional costs to sum again. Both profiles use
the same conservative evaluator-array allowance. RSS includes imports, input
checking and the separate microprofile, not only integration.

The session took 109.1762 seconds; the longest complete worker took 9.8856
seconds. All 24 paired candidate/checkpoint files are byte-identical across
the two policies. There are also 48 exact candidate/checkpoint comparisons
and 118 exact comparison-payload comparisons against D040. Small metadata-byte
differences above reflect identities/timings, not reduced numerical evidence.
The independent scientific audit passes in 115.3430 seconds, including shared
source/session integrity checks. Per-profile audit times above exclude those
shared checks and include the new every-stage RHS verification. Checked plus
per-profile audited time falls only **0.9%**; cached execution does not accelerate
the independent frozen evaluator. Relative to D040, the new audit also checks
more than the earlier readout/curve audit, so historical audit durations do not
measure a like-for-like optimization.

Across both policies, the audit checks 6,144 accepted steps, all 30,720 complete
stage/endpoint derivatives, 24 trajectory windows, 26,864 comparison samples
in 118 chunks, 108 observer samples and 107,456 readout evaluations. Ordered
trajectory/sample fingerprints exactly match D040, and all six readout fields
are bitwise scalar-equivalent. Maximum candidate score is 0.003536686 against
the unchanged limit 1; maximum independently audited accounting residual is
1.4210854715202004e-14 against 2e-9.

See the [registration](../runs/num-005c2e-2026-09-09/evaluation-01/registration.json),
[profile receipt](../runs/num-005c2e-2026-09-09/evaluation-01/verification.json),
[instantaneous probes](../runs/num-005c2e-2026-09-09/evaluation-01/instantaneous-probes.json)
and [independent audit](num-005c2e-audit.json).

## Verification and limits

All **2178 regression tests pass** in 749.16 seconds; all 816 targeted tests
pass in 115.20 seconds, including 275 new checks. Both suites report zero
failures, errors and skips, with warnings treated as errors. JUnit durations
are 749.133 and 115.186 seconds respectively.
They cover complete derivative/field identity, immutable snapshots and
nonaliasing, explicit control changes, strict inputs and domain/exponent
refusals, aggregate preflight, exact short trajectories, restarts in both
recording directions, evaluator identity refusal, live accounting failures,
every-stage audit independence and slope corruption, profiler receipt checks,
exclusive source registration and no-retry failure handling.

The independent audit adds frozen-equation recomputation of every recorded
RK4 stage and endpoint slope to the existing D040 evidence audit. RHS
evaluation checks stored slopes; it does not regenerate recorded evidence.
Whole-curve extrema are floating-point polynomial checks, not interval-certified
enclosures of the true ODE solution.

The post-regression integrity check passes: all 304 new payloads, all 74 current/archive source
hashes, all 153 payloads pinned by nine prior closeouts, and all 39 production
source hashes match. Production remains version 0.10.0.
Ruff check and formatting pass across all 156 project Python source files;
dependency and diff checks pass. The [closeout receipt](num-005c2e-closeout.json)
pins 17 payloads, including both test receipts and this report. Mutable project
progress/architecture documents are intentionally outside that immutable payload set.

Original caps remain: one CPU float64 worker, affinity 0–3, library thread
counts one, 900 seconds per worker, 3600 seconds per session/audit,
one million steps per trajectory, 256 MiB estimated arrays and 1 GiB of
aggregate retained research artifacts. Before this slice, retained roots use
831,126,114 bytes; none is removed or reset. The new root adds 3,748,280 bytes
across 305 files (304 payloads plus verification), making 834,874,394 aggregate
bytes and leaving 238,867,430 bytes of the original cap.
This accounting covers the registered E02 preparation/reference/engineering
roots, not the entire workspace or temporary pytest fixtures.

The additional evaluator-array estimate is combined with D040's aggregate
recording/readout estimate before output creation. It is not a hard RSS bound.
Filesystem inventories, dependency/index scans and quota checks remain growing
costs despite bounded numerical windows.

## Planning consequence and next recommendation

The original 18-trial, 3.5-million-step study is still not resource-qualified.
Scaling these short measurements for cached evaluation gives about 7.54 hours
checked plus 17.60 hours of per-profile audit, or 25.15 hours combined; the
largest checked trial estimate is 3,820.7 seconds. The crude short-rate evidence
estimate is 1.903 GB, versus only 238.9 MB remaining. The uncompressed trajectory
array count is 4.732 GB, not a lower bound on compressed storage.

These are planning extrapolations, not long measurements or feasibility
certification. Small-run metadata, retained microprofile diagnostics, compression
and later dynamics need not scale at these rates. Audit costs include the
additional stage verification. Neither the 900-second worker cap, 3600-second
session/audit caps nor aggregate storage cap is thereby satisfied.

Recommend profiling the unchanged stage/whole-curve checks and independent-audit
path next, then specifying reusable bounded validation caches where measured
costs justify them. Preserve every domain/accounting/extrema check and independent
verification; do not infer permission to reduce coverage. Further trajectory
storage work remains a separate decision. Do not launch the long study yet.

No long candidate study, timestep choice, candidate-owned phase continuation,
compact long-policy adoption, tolerance change, budget relaxation, GPU/fluid
work or production graph change is made in this slice.

## Reproduction and provenance

The executed profile and audit commands were:

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/profile_graph_evaluation.py --run --output runs/num-005c2e-2026-09-09/evaluation-01
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/audit_graph_evaluation.py runs/num-005c2e-2026-09-09/evaluation-01 --output reports/num-005c2e-audit.json
```

These paths are already closed, immutable outputs; do not rerun over them or
silently create another capped session. Re-auditing is read-only with respect
to the root and requires a fresh audit receipt path. Numerical reproduction
requires a separately registered output and resource decision.

| Payload | SHA-256 |
| --- | --- |
| Plan | 73e24fcde771fdcb3fe43f155fe1ec7b4c2323f35af5f28de33fd6016acc308e |
| Registration | ef39ff402f3048ab8296051130fb5476822ac5c92007a30197f13623b96c64b6 |
| 74-source archive | 60dc7f5393e912f2e3e6856b1dab5dfdb9f68d49fa58295f734050e0cb112512 |
| Profile verification | 0e5dc17f06fe743cb8bfae39c02021096a0b59e6b717dd66aa1fe79f08916fb1 |
| Independent audit | ac830143f3ee578af7c6be56b87508b5bb3e6b584cd87bb5f0c62462cf4d4754 |
| Full regression XML | 13c809c63a20722129acda3fe51ea96a7e36d677199d3fbbbdecb1bd9bcce011 |
| Targeted test XML | af9f839204922f43b65858d664cc0adfe0c01fd35965b5a38426eb6e2aa1febf |
