# NUM-005c2a — bounded checked RK4 engineering

2026-09-09, D037. All twelve registered short profiles and the independent
artifact audit pass. The engine is window-bounded and exactly restartable on
these fixed-control fixtures. **The current checked implementation and full
evidence policy are not ready for the long study under the existing caps.**
No long-time timestep is selected; production remains 0.10.0.

The [engineering contract](../docs/E02_CANDIDATE_ENGINEERING.md) and
[registered inventory](../configs/reference/e02_candidate_engineering_v1.json)
were frozen before profiling. The new
[run root](../runs/num-005c2a-2026-09-09/engineering-01/registration.json)
archives 48 sources, including all 41 unchanged A2 sources. It reuses the
audited preparations and explicit A2 per-case reference trios; no new long
implicit integration or original-result reclassification occurred.

## What was built and checked

The independent NumPy graph candidate advances the complete `13*N + 4*E`
anchored-increment state with classical RK4. Lazy integer-tick clocks preserve
the original grid across windows, including a shortened exact final interval.
Every stage and complete cubic observation curve is checked for domain,
electrical limits, typed accounting and blocked histories. Diagnostic histories
remain passive. There is no clipping or early phenotype stop.

Complete hash-checked accepted checkpoints include all state/history coordinates,
anchor, context, case identity, global tick and numerical source/runtime identity.
Short fixtures establish exact restart with a different recording width. This
does not yet implement changing controls/topology or candidate-owned preparation
transfer into a new assay phase.

Online comparison samples the union of accepted candidate/reference endpoints,
midpoints, original observers and the short end boundary. Three immutable
reference readers retain their original 500/1000-unit identities. All eight
existing error scores are evaluated and full short sample states retained.

All **169 targeted tests pass**, including **53 new tests**, in 47.80 seconds.
They cover analytic fourth order and stage clocks, original-RK4 arithmetic,
cubic samples, graph edges, exact restart, awkward final clocks, window widths,
budget refusals, bad-stage preservation, failed comparisons, reader cleanup,
source/payload tampering, independently detected rehashed numerical corruption,
and orchestration failure/timeout without retry. A negative-test fixture initially
hit the voltage guard before its intended blocked-history guard; charge-balancing
that fixture fixed the test without changing a guard, equation or tolerance.
The full suite passes **1415 tests in 612.40 seconds**, with warnings treated as
errors and no failures, errors or skips. Lint, formatting, dependency and
whitespace checks pass. All prior closeout payloads and production hashes are
rechecked unchanged. [Machine-readable closeout](num-005c2a-closeout.json).

## Measured short profiles

Each case runs from 0 to 5.12 nominal model units with maximum step 0.01:
512 steps, first at width
16, then 256. Each combination is measured once, with one CPU float64 worker,
affinity 0–3 and single-thread numerical libraries. These are short engineering
profiles, not a repeated statistical benchmark or late-time accuracy study.

| Case | Checked seconds, width 16 | Checked seconds, width 256 | Evidence MiB, width 16 | Evidence MiB, width 256 | Maximum normalized error |
| --- | --- | --- | --- | --- | --- |
| Fresh E preparation | 5.754 | 4.909 | 1.353 | 1.056 | 0.003537 |
| Fresh M preparation | 6.462 | 5.131 | 1.393 | 1.087 | 0.002979 |
| E → M active star | 9.592 | 7.947 | 2.104 | 1.838 | 0.0003241 |
| M → E active star | 9.873 | 8.041 | 2.132 | 1.859 | 0.001377 |
| E → M one neighbour | 8.275 | 6.101 | 1.862 | 1.602 | 0.0003265 |
| M → E one neighbour | 8.760 | 6.328 | 1.899 | 1.633 | 0.00006121 |

Checked time includes integration/stage checks, cubic checks, reference sampling,
derived comparisons, compressed recording, the trajectory receipt and reader
cleanup. It excludes earlier immutable-input validation/process startup; those
are measured separately, with whole-worker timing also including final profile
receipts. Table evidence sizes exclude only each profile's timing receipt and
shared session files. Errors are normalized by the unchanged quantity-specific
budgets; the candidate limit is **1**, not 0.1 and not a percentage of cell state.

The session takes **137.557 seconds**; complete checked calls total 87.175 seconds.
The longest whole worker takes 13.796 seconds against its 900-second cap.
There are 6,144 accepted steps, 30,720 integration RHS evaluations, 204 trajectory
chunks, 26,864 comparison samples in 997 chunks, and 107,456 derived-readout
evaluations. Each profile retains all nine registered short observers.

At width 256, section totals across the six cases are 8.417 seconds for RK4/stage
checks, 10.120 for cubic checks, 19.394 for comparison/sample recording and 0.336
for trajectory-window recording. Comparison/sample recording takes about half
the complete checked time. Reducing only integration cost would miss much of
the workload. These costs include repeated reference readouts, not just candidate
RHS evaluations.

Working-array estimates range from 1,878,080 to 22,762,816 bytes, including cached
reference windows independently of candidate window width; the cap is 256 MiB.
Measured process high-water RSS is 85,172,224–94,535,680 bytes and includes imports,
input checks, Python/runtime memory and comparison. RSS is not the array estimate.
The array cap is not a hard process-memory limit: receipt inventories and
directory scans also grow with the number of recorded files. The bounded claim
concerns numerical windows, not constant total process memory for arbitrary runs.
Larger windows increased memory but reduced runtime and stored bytes in every
measured pair; these measurements do not establish a universal speedup.

## Independent audit and preserved evidence

The [read-only audit](num-005c2a-audit.json) passes in 60.079 seconds. It checks
1,313 payloads and the 48-file source capsule, all global clocks and exact carries,
stage/update and cubic algebra, independently calculated stage/whole-curve domains
and typed accounting, every comparison grid/sample identity, and all four
primary/history score formulas. The maximum independently checked accounting
residual is **1.4211e-14**, against 2e-9.

All six width pairs have identical ordered binary64 clocks, states, slopes,
cubics and comparison-sample evidence. This establishes that these recording
windows do not alter the numerical path, not that all future execution policies
are interchangeable.

Stored slopes and derived voltage/gate/flux/binding scores are online evidence,
not independent recomputations of the RHS or derived laws. The algebraic audit
does not prove a stored slope is a correct derivative; analytic tests and
comparison with frozen reference paths provide separate checks. Polynomial
extrema use floating-point roots, not rigorous interval-certified ODE bounds.

The new root contains 1,314 files and **21,201,053 bytes**, including verification.
Accepted preparations plus all old complete/failed/partial long-reference roots
occupy 762,443,122 bytes. The combined total is **783,644,175 bytes**, below
1,073,741,824; **290,097,649 bytes remain**. The quota was not reset by opening a
new directory. Old reference sources, failed receipts and all 39 production
source hashes are unchanged. No new dependency, native long trajectory, GPU,
fluid or continuing-exploration-agent run was added.

## Long-study preflight: do not launch this implementation yet

The original six-case, three-timestep study contains 18 trials and 3.5 million
accepted steps. Scaling the measured complete checked cost per step gives:

| Recording width | Estimated whole study | Largest estimated trial | Short-rate compressed-evidence estimate |
| --- | --- | --- | --- |
| 16 | 58,254.96 s / 16.18 h | 7,713.61 s | 13.43 GB |
| 256 | 45,715.09 s / 12.70 h | 6,281.93 s | 11.47 GB |

The unchanged limits are 3,600 seconds per session, 900 seconds per trial and
the remaining shared artifact quota. Even the trajectory arrays alone—one
accepted state, five slopes, four cubic rows and time/tick per step—would require
at least **9,408,000,000 uncompressed bytes**, before comparison samples, window
carries and metadata. This is a raw-layout floor, **not** a lower bound on
compressed bytes.

These are planning estimates, not executed long-run results or guaranteed costs.
The initial reference transient produces many comparison times; its cost per
candidate step need not persist at later times or finer timesteps. Compression,
root-directory scanning overhead and numerical behaviour can also change. The
estimates neither certify long feasibility nor prove exact future consumption.
They do show that this baseline does not establish a safe fit under the limits.

Recommended next slice: optimize repeated diagnostics using cached static graph
data and bounded batched readouts, verifying them against this frozen scalar
baseline. Separately specify a compact, auditable evidence policy with complete
restart state and explicit retained-versus-online-only checks. Reprofile the
same short workloads before any long study. Do not enlarge budgets, silently
drop evidence, change equations/error limits or select a timestep to force a fit.

NUM-005c2a's bounded engineering/profile task is complete. NUM-005c2's long
candidate study, selected/half-step qualification
and candidate-owned continuations remain unfinished, followed by production
graph and assay acceptance. Organ and GPU work remain later stages.
