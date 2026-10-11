# Before the long-time RK4 candidate study

Planning note for NUM-005c2, 2026-09-08. This does not select a timestep, amend
the [frozen numerical plan](E02_SWITCHING_NUMERICS.md), or authorize another
scientific session. Finish and audit the 14 implicit reference trios first.

## Work and evidence scale

The registered study includes six cases: two 500-unit isolated preparations,
two 1000-unit active stars and two 1000-unit one-neighbour conditions. Ignoring
roundoff and any additional boundary subdivision, its nominal work is:

| Maximum step | Steps per preparation | Steps per 1000-unit condition | Steps across six study cases |
| --- | ---: | ---: | ---: |
| 0.01 | 50,000 | 100,000 | 500,000 |
| 0.005 | 100,000 | 200,000 | 1,000,000 |
| 0.0025 | 200,000 | 400,000 | 2,000,000 |

That is 3.5 million steps in the study alone. The later half of 0.0025 is
0.00125, requiring 800,000 nominal steps per 1000-unit condition: below the
one-million-step cap, but not yet shown to fit the 900-second worker cap.
It would need at least about 889 checked steps per second, including recording
and all required comparisons. Do not extrapolate that speed from an implicit
solver, a short unconstrained kernel, or a GPU claim.

For scale only, storing one float64 time, one complete state and four complete
cubic coefficients per step takes approximately `8 + 40*D` bytes, before chunk
carries, indexes, diagnostics or comparison records. The source coordinate
counts are D=13 for an isolated preparation, 30 for a pair and 47 for a star.
Across all 18 study attempts this illustrative uncompressed layout alone is
4,704,000,000 bytes (about 4.38 GiB). Compression is data-dependent. The implicit
reference compression ratio is not a candidate storage guarantee.

The frozen plan requires full checks and complete checkpoints, not a Python
list of every window. It explicitly retains reference dense coefficients and
accepted states, plus observer samples, initial/final states and streamed error
summaries. Before launching c2, state exactly which candidate evidence is
retained versus checked online and which checks an independent audit can repeat.
Do not silently omit an obligation, promise full post-run trajectory auditing
without the corresponding evidence, or reset an aggregate quota per directory.

## Small engineering step first

Build a separate bounded reference candidate runner, leaving the accepted
production kernels and earlier numerical sources unchanged. The existing
short-pair `integrate_rk4` helper builds whole-history lists and cannot simply be
used as the long fixed-graph implementation.

Use a short engineering fixture to verify exact global clocks, window carries,
stage/domain checks, cubic extrema, typed ledger reconstruction and streamed
comparisons with the accepted implicit reference readers. Measure the complete
checked path, not just its RHS. Independently audit the chosen evidence format.
These fixtures are not replacements for any registered long study case.

Then pre-register the candidate implementation, source/runtime capsule, complete
trial inventory, evidence policy, aggregate retained-byte accounting and bounded
session schedule. Keep all three study steps, all six cases and rejected trials;
select only after the complete study. Reuse previous attempts or preparation
prefixes only through explicit, exact-input provenance, never by resetting a
candidate to the qualified reference anchor.

Every preparation and condition still needs selected/half-step qualification,
and both active directions need the candidate's own prepared states at both
steps. If the measured implementation or required evidence cannot fit the frozen
limits, stop and propose a named amendment with prior evidence retained. No
GPU, production graph, timestep selection or budget increase follows from this note.
