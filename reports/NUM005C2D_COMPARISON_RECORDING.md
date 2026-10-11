# NUM-005c2d — lossless reference-backed comparison records

2026-09-09, D040. Implementation, all 541 targeted tests and all twelve short
profiles pass. Backed recording saves **98.5% of comparison payload bytes** and
**80.6% of total per-profile evidence**. Complete checked runtime rises **4.2%**
in these single matched short observations. The independent artifact audit
passes with exact D039 numerical/sample evidence and scalar-equivalent readouts;
all **1903 regression tests pass**. No long candidate run, production change
or budget extension is authorized by this prototype.

## Implementation and scope

The [contract](../docs/E02_COMPARISON_RECORDING.md) and
[profile inventory](../configs/reference/e02_comparison_profiles_v1.json) select
`full_samples` versus `trajectory_backed`. Both reuse the frozen D039 runner,
`rk4_basis` trajectory recording and D038 cached readouts. Scientific equations,
all eight score targets, stage/whole-curve checks and the 2e-9 accounting limit
are unchanged. Production remains 0.10.0.

The compact payload retains every float64 sample clock and Boolean observer
flag. Complete candidate and three reference states are reconstructed from
the retained candidate window and immutable reference trajectories. Each record
retains the full logical-array hash, individual input hashes and six-field
readout fingerprints. The writer requires bit-exact reconstruction before
publication; no RHS replay, precision change, thinning or coordinate omission.

An exclusive manifest pins reference case/report/index identities and selected
case/method/numerical settings, candidate attempt, codec sources and runtime.
Reference payload availability and hashes are checked before reconstruction.
Each comparison index record binds the manifest and candidate-window payload;
the unchanged D039 commit then binds the completed comparison prefix. This
avoids circular hashes without moving the numerical publication boundary.

Complete restart carries remain independent of the comparison representation.
The new explicit reader/restart API checks dependencies and closed committed
prefixes. Older low-level D039 readers alone cannot certify this added policy.
Corrupt, linked, missing or mismatched dependencies are refused. Failed windows
remain diagnostic, and independent emergency preservation is unchanged.
Absolute local paths are not a relocation/migration facility. General unclean
process recovery and distributed/power-loss durability remain unestablished.

## Engineering verification

All **541 targeted tests pass in 77.71 seconds**, with warnings treated as errors.
The 196 new checks cover all 45 graph layouts, independently reconstructed
candidate interpolation, full/backed sample identity, short final steps,
window widths, both restart-policy directions and complete passive histories.
They also cover changed/missing/symlinked/hardlinked reference files, selected
dependency identity, rehashed payload/index forgeries, incomplete and extra
indexes, source/runtime mismatches, bounded headers/allocations and explicit
adapter ownership. Disabling writer decoders and interpolation does not prevent
the independent decoder from reproducing the same arrays.

Interrupted compact payload/index writes and reconstruction mismatch preserve
only the prior committed restart checkpoint, without retry. The same comparison
limit still stops a failed first window before any commit. Registration/output
exclusivity and one-worker failure/timeout stops also pass.

The first test iteration passed 141 checks and exposed one fixture error: it
passed a pre-registration specification lacking source hashes to an identity
helper requiring a registered object. The fixture now adds the actual source
hash inventory; no numerical guard, equation or tolerance was changed.

All **1903 regression tests pass in 686.87 seconds**, including the 196 new
checks, with warnings treated as errors. The [full receipt](num-005c2d-tests.xml)
and [targeted receipt](num-005c2d-targeted-tests.xml) retain the results.
Lint and formatting checks pass for 152 Python files, dependency checks pass,
and local documentation/whitespace checks pass. The
[machine closeout](num-005c2d-closeout.json) pins this report, implementation
and verification receipts. These checks do not qualify the long study or
production graph implementation.

## Matched short measurements

Each of six inputs runs once per policy, full before backed, from 0 to 5.12
nominal units at step 0.01 and width 256: 512 accepted steps. Sequential CPU
float64 workers retain affinity 0–3 and single-thread numerical libraries.
The [68-file registration](../runs/num-005c2d-2026-09-09/comparison-01/registration.json)
includes all 62 unchanged D039 sources and the six new source/contract files.
Both policies use the new dependency metadata and the unchanged D039 basis
trajectory representation; timings are not a repeated statistical benchmark.

| Input | Full checked seconds | Backed checked seconds | Full evidence MB | Backed evidence MB |
| --- | --- | --- | --- | --- |
| Prepare E | 2.593 | 2.794 | 0.959 | 0.201 |
| Prepare M | 2.597 | 2.738 | 0.993 | 0.204 |
| E to M, active | 4.857 | 5.028 | 1.626 | 0.301 |
| M to E, active | 4.904 | 5.015 | 1.649 | 0.302 |
| E to M, one neighbour | 3.751 | 3.891 | 1.400 | 0.278 |
| M to E, one neighbour | 3.750 | 3.932 | 1.433 | 0.279 |

MB here is decimal. Profile evidence is measured before each timing receipt,
including trajectory, comparison, checkpoint and local metadata files, but
excluding shared session/registration/source-capsule files. Across six cases:

| Measurement | Full samples | Trajectory-backed |
| --- | --- | --- |
| Complete checked seconds | 22.452 | 23.399 |
| Per-profile offline audit seconds | 46.271 | 47.926 |
| Checked plus per-profile audit seconds | 68.722 | 71.325 |
| Complete per-profile evidence bytes | 8,061,025 | 1,565,024 |
| Comparison artifact bytes including metadata | 6,739,201 | 243,211 |
| Compressed comparison payload bytes | 6,598,114 | 101,910 |
| Logical comparison array bytes | 12,462,904 | 12,462,904 |
| Encoded comparison array bytes before compression | 12,462,904 | 120,888 |
| Compressed trajectory payload bytes | 1,166,247 | 1,166,247 |
| Separate initial/final checkpoint bytes | 13,078 | 13,078 |
| Comparison-index bytes | 82,693 | 82,869 |
| Dependency-manifest bytes | 42,335 | 42,365 |
| Online codec/reconstruction-verification seconds | 0.0938 | 1.0216 |
| Dependency validation/setup seconds | 0.5711 | 0.6442 |

The raw comparison-array reduction is 99.03%; the compressed payload reduction
is 98.46%. Including comparison metadata, savings are 96.39%, and complete
profile savings are 80.59%. The checked-time increase is 0.947 seconds summed
across six cases, or 4.22%. This trades a measured checking cost for storage,
not a claimed speedup. Codec/setup timings are subcomponents, not additional
costs to add to complete checked time.

All 24 paired trajectory/checkpoint NPZ files are byte-identical between the
two new policies and to D039. All 59 full-sample comparison NPZ files are also
byte-identical to D039. Backed payloads have fewer stored fields; their logical
identity is checked through reconstruction rather than raw file equality.

The profile session completes in **110.829 seconds**, longest whole worker
**10.838 seconds**, below the unchanged 3600/900-second caps, with no retry.
Conservative aggregate candidate/readout/reconstruction array estimates span
10,216,160–35,319,648 bytes, below 256 MiB. Measured process high-water RSS spans
87,130,112–98,455,552 bytes. RSS is not the array estimate or a hard memory cap;
dependency inventories, quota scans and comparison-prefix checks still have
growing metadata/I/O costs.

After this reduction, retained RK4 trajectory payloads account for **74.5%**
of backed-profile evidence, and comparison artifacts for **15.5%**. Storage
reduction does not remove stage/whole-curve checking or offline audit cost.

## Independent audit and retained provenance

The [read-only audit](num-005c2d-audit.json) passes in **102.135 seconds**.
It checks 290 payloads and the 68-file source capsule, explicit reference
dependencies and the complete decoded comparison arrays. Its candidate sample
and basis reconstruction use separate arithmetic implementations, not the
writer's decoder or sampler. Per-profile audit timings include trajectory,
sample and readout checks and exclude shared session-integrity checks.

All twelve ordered trajectory/sample fingerprints exactly match the corresponding
D039 basis results. All six readout fields are bitwise equal to frozen scalar
evaluation on every saved input; all eight scores are recomputed. Maximum
candidate error is **0.0035367**, below 1; the largest independently audited
accounting residual is **1.4211e-14**, below 2e-9. The profiles retain 6,144
accepted steps, 30,720 integration RHS calls, 24 trajectory windows, 26,864
comparison samples in 118 chunks, 107,456 readout evaluations and 108 observer
flags. No sample or passive-history coordinate was discarded.

This retains earlier scientific limits: the audit checks stage/update/cubic
algebra and recomputes primary-RHS readouts at saved comparison inputs, not
every constitutive integration slope. Polynomial extrema are floating-point
checks, not interval-certified ODE bounds. Storage reconstruction is not new
biological evidence, native long-assay reproduction or production acceptance.

The new root retains **10,106,680 bytes in 291 files**, including verification.
Aggregate prior and new artifacts are **831,126,114 bytes** under the unchanged
1,073,741,824-byte cap; **242,615,710 bytes remain**. No accepted, failed or
partial root was deleted or overwritten. Integrity rechecking verifies all
68 current/archived sources, 290 new payloads, 136 files pinned by eight prior
closeouts, and 39 unchanged production sources. No new dependency or GPU/fluid
job was added, and the continuing exploration agent's work was not changed.

## Long-study preflight and next recommendation

The original eighteen-trial study still comprises 3.5 million candidate steps.
Short-rate planning estimates are:

| Comparison policy | Checked study estimate | Additional audit estimate | Compressed-evidence estimate | Raw trajectory-array floor |
| --- | --- | --- | --- | --- |
| Full samples | 7.54 h | 15.47 h | 9.686 GB | 4.732 GB |
| Trajectory-backed | 7.84 h | 16.01 h | 1.863 GB | 4.732 GB |

The backed estimate is much smaller, but still exceeds the remaining artifact
allocation; its largest trial projects to **3,928.46 seconds**, above the
900-second worker cap. Checked and audited stages remain above their respective
3600-second limits, with combined short-rate cost about 23.85 hours. The
uncompressed layout floor is not a lower bound on compressed output. Static
metadata amortization, sampling density, transient compression and late-time
numerics may differ; these estimates are not long measurements or feasibility
certificates. No long candidate study or selected timestep is claimed.

Recommended next bounded slice: **profile and cache integration-side graph
evaluation**, starting with exact instantaneous RHS probes before matched short
trajectories. Retain immutable per-model configuration, complete derivatives,
all stage/domain/accounting and whole-cubic checks, and the independent audit.
The backed profiles still spend 8.732 seconds in integration/stage checks and
10.405 seconds in cubic-domain checks across six inputs. Separate those costs
before claiming a speed benefit; a cache must not add hidden history or change
cell/edge ownership, controls, numerical identity rules or scientific thresholds.

That recommendation is not implemented or adopted here. Remaining trajectory
storage is a separate gate: further compression, checkpoint/RHS replay-only
evidence, or a resource extension each needs an explicit decision and measured
checked/audited cost. Do not silently reduce inspectable evidence or launch a
long run because the comparison payloads are smaller.

NUM-005c2d's implementation/profile/audit/regression scope is complete.
Long RK4 selection, selected/half-step trials,
candidate-owned continuations, production graphs/assays and organ/GPU stages
remain unfinished.
