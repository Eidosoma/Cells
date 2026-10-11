# NUM-005c2b — cached bounded diagnostic readouts

2026-09-09, D038. All twelve registered short profiles and the expanded
independent artifact audit pass. Across the six matched inputs, complete checked
time falls from **38.719 to 21.057 seconds (1.84×)**; readout computation falls
from **17.902 to 0.209 seconds (85.45×)**. Every saved readout is bit-for-bit
identical to frozen scalar evaluation on these inputs. Integration and sampled
states are exactly unchanged. These are single short measurements, not a
statistical benchmark or a general CPU/GPU speed guarantee.

The full long-study resource fit remains unestablished. No long candidate study,
timestep selection or production change occurred; Cells remains 0.10.0.
The [compact-evidence design](../docs/E02_COMPACT_EVIDENCE_DESIGN.md) is a
separate, unimplemented proposal.

## Implementation and verification boundary

The [readout contract](../docs/E02_DIAGNOSTIC_OPTIMIZATION.md) and
[profile inventory](../configs/reference/e02_diagnostic_profiles_v1.json) were
fixed before the session. Its [registration](../runs/num-005c2b-2026-09-09/diagnostics-01/registration.json)
archives 55 source files, including all 48 unchanged D037 sources. No frozen
module was patched or replaced.

The independent NumPy adapter snapshots static graph, geometry and control
data, preflights its array estimate and batches only the observation-sample axis.
It preserves equation expressions, edge accumulation order, source domains,
float64 semantic axes and input immutability. Cache reuse does not silently
follow later edits to model dictionaries. Invalid inputs or readout failures
are refused without scalar fallback.

An explicit per-instance policy selects the frozen scalar or cached batched
readouts. RK4 stages, accepted states, complete passive histories, global clocks,
cubic checks, checkpoint semantics and reference sampling remain in D037's
unchanged integrator. All eight scientific targets and the 2e-9 accounting
bound stay unchanged. Both policies retain full short state/stage/cubic/sample
evidence and additionally fingerprint all six readout fields per comparison
batch. This comparison does not obtain speed by discarding checks or output.

All **335 targeted tests pass in 23.34 seconds**, including **125 new tests**.
The new tests cover all 45 existing instantaneous graph fixtures, varied batch
widths and non-contiguous arrays, cache isolation, invalid domains and inputs,
preallocation refusals, full comparison compatibility, reader cleanup, retained
readout failure, fingerprint corruption and orchestration stops without retry.
Instantaneous equivalence uses the unchanged NUM-005a tolerances; exact bits are
reported separately. These fixtures are not long-time candidate qualification.
The full suite passes **1540 tests in 619.79 seconds**, with warnings treated
as errors and no failures, errors or skips. Lint and formatting pass for all
143 Python files; dependency and whitespace checks pass. The
[machine-readable closeout](num-005c2b-closeout.json) retains these results with
source and evidence hashes.

## Matched short measurements

Each input runs once per policy from 0 to 5.12 nominal model units, at step 0.01
and width 256: 512 accepted steps. A scalar worker precedes its batched worker;
workers are sequential CPU float64 processes with affinity 0–3 and single-thread
numerical libraries. The scalar baseline is measured anew with the same added
fingerprinting work, not inferred from old timings.

| Input | Scalar checked seconds | Batched checked seconds | Checked-time ratio | Readout-time ratio | Maximum normalized candidate error |
| --- | --- | --- | --- | --- | --- |
| Fresh E preparation | 4.949 | 2.357 | 2.10× | 103.81× | 0.003537 |
| Fresh M preparation | 5.085 | 2.405 | 2.11× | 99.48× | 0.002979 |
| E → M active star | 8.028 | 4.666 | 1.72× | 78.62× | 0.0003241 |
| M → E active star | 8.164 | 4.587 | 1.78× | 83.03× | 0.001377 |
| E → M one neighbour | 6.212 | 3.494 | 1.78× | 78.76× | 0.0003265 |
| M → E one neighbour | 6.281 | 3.548 | 1.77× | 79.64× | 0.00006121 |

Ratios are scalar time divided by batched time. The unchanged candidate limit
is 1. Complete checked time includes cache creation, integration/stage checks,
cubic checks, reference sampling, comparisons, fingerprints, full recording,
trajectory receipts and reader cleanup. Immutable-input validation, process
startup and final profile receipts are measured separately. Isolated readout
time excludes cache creation, fingerprinting and the rest of the checked call.

The session takes **113.854 seconds**; its twelve complete checked calls total
59.775 seconds. The longest whole worker is 12.393 seconds, below 900; the
session limit remains 3600 seconds. All twelve profiles complete without retry.
They retain 6,144 accepted steps, 30,720 integration RHS calls, 24 trajectory
chunks, 26,864 comparison samples in 118 chunks, 107,456 readout evaluations
and all 108 short observer flags.

Across the six batched profiles, section totals are 8.552 seconds for
integration/stage checks, 10.241 for complete cubic checks, 1.862 for comparison
and sample recording, and 0.267 for trajectory-window recording. Cache creation
totals 0.00631 seconds; fingerprinting totals 0.11785 seconds. Integration/stage
and cubic checking now account for about 89% of complete checked time. This
identifies the next runtime concern; it does not authorize weakening guards.

Candidate-array estimates are 6,608,960–22,762,816 bytes; the separate batched
readout estimates are 329,472–1,252,096 bytes. Even their conservative sum is at
most 24,014,912 bytes, below the 256 MiB estimated-array cap. Measured process
high-water RSS spans 86,544,384–94,752,768 bytes. This includes runtime/imports,
input checks and Python objects; the array cap is not a hard process RSS limit.
Receipt inventories and filesystem scanning still grow with retained files.

## Independent audit and preserved evidence

The [read-only audit](num-005c2b-audit.json) passes in **94.246 seconds**. It
checks 266 payloads and the 55-file source capsule, plus the unchanged prior
evidence chains and production identity. D037's independent components recheck
stage/update/cubic algebra, whole-curve domains and accounting, exact comparison
grids/samples and the four primary/history score formulas. The largest
independently audited accounting residual is **1.4211e-14**, against 2e-9.

All twelve ordered step-array and comparison-sample fingerprints equal the
corresponding frozen D037 width-256 result. Additionally, the new auditor
evaluates every saved candidate/reference input with the frozen scalar readout
implementation, checks batched results against it, reconstructs every recorded
readout fingerprint and recomputes all eight candidate/reference scores. Every
one of the six fields is bitwise exact here; the maximum scalar differential
score is zero. This extends D037's audit beyond its four independently evaluated
primary/history scores.

Scalar readout evaluation includes a primary-RHS readout, but no new integration.
It shares the frozen constitutive implementation, so it is an independent check
of the optimization, not a second derivation of the source laws. Stored stage
slopes are checked algebraically, not all recomputed as constitutive derivatives.
Floating-point polynomial extrema are not rigorous interval-certified ODE bounds.
None of these checks constitutes biological or native long-assay validation.

Full per-profile evidence before timing receipts totals 9,543,308 bytes for
scalar and 9,543,741 for batched execution; all 83 paired NPZ files are byte-identical.
The 433-byte difference is metadata, not a storage optimization. The new root
contains 267 files and **19,441,104
bytes**, including its verification receipt. Adding every prior accepted,
failed and partial preparation/reference/D037 artifact gives **803,085,279
bytes** of the original 1,073,741,824-byte quota; **270,656,545 bytes remain**.
No earlier evidence was removed or reclassified. All 39 production sources
remain unchanged; no dependency, native long, GPU, fluid or continuing-agent
experiment was added.

## Long-study preflight and next slice

Scaling complete checked short cost per step over the original six cases and
three timesteps gives the following planning estimates for its 18 trials:

| Readout policy | Estimated complete study | Largest estimated trial | Short-rate compressed evidence estimate |
| --- | --- | --- | --- |
| Current frozen scalar | 46,076.74 s / 12.80 h | 6,378.39 s | 11.504 GB |
| Cached batched | 25,533.15 s / 7.09 h | 3,644.94 s | 11.505 GB |

These are not long measurements or feasibility certifications. Transient
comparison density, compression, growing metadata/scanning costs and late-time
numerics can change. The unchanged raw trajectory-layout floor remains
9,408,000,000 uncompressed bytes before comparison samples and metadata; this
is not a lower bound on compressed output. Neither the runtime nor the retained
evidence policy establishes a safe fit under the original limits.

Recommended next slice: prototype **lossless evidence redundancy removal** on
the same short cases, with exact reconstruction, complete restart checkpoints,
corruption/interruption/quota tests and an independent reconstructed-evidence
audit. Measure the complete checked and audited path, including metadata costs.
This will not necessarily solve the remaining storage or runtime gap. A later
checkpoint/replay policy needs an explicit change of audit contract and replay
budget; hashes alone cannot validate omitted calculations. Runtime optimization
of the remaining stage/cubic checks also needs its own unchanged-semantics tests.

NUM-005c2b's diagnostic implementation, short profiles, audit and design note
are complete. Do not launch the long study, enlarge limits, select a timestep
or promote this NumPy adapter into production as an automatic consequence of
these profiles.
NUM-005c2's long candidate study, selected/half-step trials and candidate-owned
continuations remain unfinished, before production graph/assay acceptance.
Computational multiscale, organ composition and GPU execution remain later work.
