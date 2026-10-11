# NUM-005c2c — lossless numerical evidence

2026-09-09, D039. All twelve short profiles and the independent reconstruction
audit pass. The RK4 basis reduces compressed trajectory payloads by **57.8%**,
but total per-profile evidence by **16.7%** because comparison samples remain
fully retained. Decoded trajectories, sample arrays and readouts exactly match
D038. Complete checked and audited cost is essentially unchanged on these
single matched short measurements.

This is a working reference-recording prototype, not an adopted compact policy
for the long study. No long candidate trial, timestep selection, production
change or budget extension occurred. Cells remains 0.10.0.

## What changed and what stayed fixed

The [contract](../docs/E02_LOSSLESS_EVIDENCE.md) and
[profile inventory](../configs/reference/e02_evidence_profiles_v1.json) were
fixed before profiling. The [registration](../runs/num-005c2c-2026-09-09/evidence-01/registration.json)
archives 62 sources, including all 55 unchanged D038 sources. The numerical
kernel remains frozen; a separate runner selects an explicit recording policy.

`full_trace` retains every accepted state, five slopes and four cubic rows.
`rk4_basis` retains complete window endpoints, every slope, clocks and
anchor/context, then reconstructs intermediate accepted states and cubic rows
in the pinned arithmetic. The writer checks exact logical array digests before
writing, and the reader checks bounded archive/header inventories before loading.
No RHS replay, quantization, clipping, silent fallback or incomplete state.

Both policies retain every comparison sample, observer flag and readout hash.
All eight scientific targets, stage/whole-curve checks, source domains and the
2e-9 accounting limit remain unchanged. The commit record now follows payload
synchronization and successful window comparison. Applying the existing score
limit at each window can stop a failing run earlier than D038; it does not change
successful arithmetic or acceptance thresholds.

Committed closed prefixes are restartable across recording-policy and width
changes with complete state, original clocks and numerical/source identity.
Failed writes are not retried. Last-evaluation and uncommitted-window preservation
are attempted independently, and diagnostic dumps cannot become checkpoints.
Malformed tails and unclosed attempts are refused; automatic process-kill
recovery and distributed/power-loss durability are not established.

All **384 targeted tests pass in 33.67 seconds**, including **167 new checks**:
all 45 graph fixtures, exact codecs and independent decoding, short final steps,
window widths, cross-policy restart at each tested boundary, complete histories,
strided/Fortran arrays, corrupted and forged evidence, allocation/header guards,
partial or unacknowledged commit lines, independent preservation, closed-prefix
eligibility, unchanged comparison limits and one-worker stops without retry.
A negative fixture initially changed the first state and hit the endpoint guard;
it was corrected to target an interior row without altering any guard or tolerance.
All **1707 regression tests pass in 640.43 seconds**, including the 167 new
checks, with warnings treated as errors. The [full test receipt](num-005c2c-tests.xml)
and [targeted receipt](num-005c2c-targeted-tests.xml) retain the results.
Lint and formatting checks pass for 148 Python files, dependency checks pass,
and local Markdown targets, tables, headings, fences and whitespace pass.
The final integrity recheck verifies all 62 current/archived sources, 266 new
payloads, 118 payloads pinned by seven prior closeouts and 39 unchanged production
sources. The [machine closeout](num-005c2c-closeout.json) pins this report and the
implementation, test and audit receipts.

## Matched short measurements

Each case runs once per policy from 0 to 5.12 nominal units, at step 0.01 and
width 256: 512 accepted steps. Full precedes basis in separate sequential CPU
float64 workers, affinity 0–3 and single-thread numerical libraries. Both use
the new publication protocol and D038 cached readouts. This is not a repeated
statistical benchmark, and timing variation is not a demonstrated speedup.

| Input | Full checked seconds | Basis checked seconds | Full evidence MB | Basis evidence MB |
| --- | --- | --- | --- | --- |
| Fresh E preparation | 2.442 | 2.453 | 1.114 | 0.942 |
| Fresh M preparation | 2.550 | 2.492 | 1.148 | 0.975 |
| E → M active star | 4.732 | 4.688 | 1.933 | 1.609 |
| M → E active star | 4.711 | 4.568 | 1.955 | 1.632 |
| E → M one neighbour | 3.520 | 3.542 | 1.687 | 1.384 |
| M → E one neighbour | 3.613 | 3.590 | 1.719 | 1.416 |

MB is decimal. Per-profile evidence excludes its timing receipt and shared
session files. Checked time includes integration/guards, reference comparisons,
encoding and reconstruction verification, synchronized publication, final
trajectory receipts and reader cleanup. Startup/input verification and the
final profile receipt are measured separately.

Across all six cases, full versus basis results are:

| Measurement | Full trace | RK4 basis |
| --- | --- | --- |
| Complete checked seconds | 21.568 | 21.334 |
| Per-profile offline audit seconds | 44.276 | 44.461 |
| Checked plus per-profile audit seconds | 65.844 | 65.794 |
| Compressed trajectory payload bytes | 2,765,842 | 1,166,247 |
| Uncompressed encoded trajectory array bytes | 7,426,752 | 3,743,232 |
| Complete per-profile evidence bytes | 9,557,489 | 7,957,861 |
| Comparison artifact bytes | 6,640,318 | 6,640,315 |
| Separate initial/final checkpoint bytes | 13,078 | 13,078 |
| Online encoding/reconstruction-verification seconds | 0.0558 | 0.1358 |

The raw trajectory-array reduction is 49.6%; actual compressed trajectory savings
are 57.8%. Total evidence falls 16.7%. All 71 paired comparison/checkpoint NPZ
files are byte-identical; the three-byte comparison-directory difference is
timing metadata, not omitted samples. Comparison artifacts now occupy **83.4%**
of basis-profile evidence. Storage and checking cost are separate concerns.

Per-profile audit times include curve/sample/readout checks and exclude shared
session-integrity checks. The full independent audit takes 96.385 seconds.
The profile session takes **99.366 seconds**, with the longest whole worker
9.136 seconds, against unchanged 3600/900-second session/worker caps.
All twelve profiles complete without retry: 6,144 accepted steps, 30,720
integration RHS calls, 24 trajectory chunks, 26,864 comparison samples in 118
chunks, 107,456 readout evaluations and 108 short observer flags.

Conservative candidate-plus-codec array estimates span 7,892,416–27,402,688 bytes,
below 256 MiB. Process high-water RSS spans 86,810,624–94,875,648 bytes and includes
imports, runtime and metadata. This is not a hard RSS cap or a constant-total-
memory claim: existing quota scans, comparison-prefix checks and final inventories
still grow with retained files.

## Independent audit and retained provenance

The [read-only audit](num-005c2c-audit.json) verifies 266 payloads and the 62-file
source capsule. A separately implemented decoder reconstructs basis arrays;
tests explicitly prevent it from using the writer's decoder. Every decoded
window digest, encoded/logical byte count, complete checkpoint and hash-linked
comparison prefix is checked. Independent stage/update/cubic algebra,
domain/accounting and sample-grid checks then run on the reconstructed evidence.

All twelve ordered trajectory and comparison-sample fingerprints exactly equal
the corresponding D038 batched result. Scalar readout checks and recomputation
of all eight scores also pass: all six readout fields are bitwise exact on every
saved input. The maximum candidate error is **0.0035367**, below 1; the largest
independently audited accounting residual is **1.4211e-14**, below 2e-9.

Reconstruction and stored logical hashes do not independently establish every
constitutive stage slope. The audit retains the earlier algebra/reference-path
checks and recomputes primary-RHS readouts at saved comparison inputs, not all
integration stages. Floating-point polynomial extrema are not interval-certified
ODE bounds. No biological, native long-assay or production qualification follows
from lossless encoding.

The new root contains **17,934,155 bytes in 267 files**, including verification.
Together with all earlier accepted, failed and partial preparation/reference
and engineering roots, the total is **821,019,434 bytes** under the unchanged
1,073,741,824-byte cap. **252,722,390 bytes remain**. No root was removed,
overwritten or reclassified. Prior registered sources and all 39 production
sources remain unchanged. No new dependency, GPU/fluid job or continuing
exploration experiment was added.

## Long-study preflight and next recommendation

Short-rate estimates for the original eighteen-trial candidate study are:

| Policy | Checked study estimate | Additional audit estimate | Compressed-evidence estimate | Raw trajectory-array floor |
| --- | --- | --- | --- | --- |
| Current full trace | 7.24 h | 14.79 h | 11.520 GB | 9.408 GB |
| RK4 basis | 7.16 h | 14.85 h | 9.570 GB | 4.732 GB |

The largest estimated basis trial is 3,662.68 seconds, above the unchanged
900-second worker limit. Checked-plus-audited cost projects to about 22 hours;
neither stage establishes a fit under its current limits. Raw layout floors
exclude checkpoint/window overhead and comparisons, and are not lower bounds
on compressed output. These are planning estimates, not long measurements:
transients, sampling density, compression, metadata and late-time numerics can
change. The long candidate study remains unlaunched and unqualified.

Recommended next bounded slice: prototype **lossless reference-backed comparison
records**. Retain complete clocks/observer flags and input/readout digests, then
reconstruct comparison states from the retained candidate evidence and immutable
reference trajectories. Require bit-exact decoded arrays, explicit dependency
identity/availability checks and an independent audit on the same short cases.
This is a proposal, not permission to discard samples under the present policy.

That targets the now-dominant repeated comparison data without immediately
requiring RHS replay or reduced audit coverage. It still may not fit the quota.
Stage/cubic checking and offline audit runtime need separate unchanged-semantics
optimization; storage reduction alone does not solve those costs. Any later
checkpoint/replay-only policy, reduction in inspectable evidence or budget
change requires an explicit decision and cost preflight, not silent adoption.

NUM-005c2c's prototype/profile/audit/regression scope is complete.
Long RK4 selection, selected/half-step trials, candidate-owned
continuations and production graph/assay acceptance remain unfinished. Organ
and GPU work remain later stages.
