# REF-003c closeout: audited seven-cell correspondence

2026-09-12, D068. **The independent evidence audit and all 171 short adapter
tests pass.** The [original seven-cell capture](REF003C_CLUSTER_ALIGNMENT.md)
is preserved, not rerun. This closes initialization, instantaneous voltage/RHS
and prescribed-update correspondence only. No full trajectory, one-cell native
alignment, biological validation, GPU qualification or stable promotion follows.

## What was verified

The [frozen-checker audit](ref-003c-audit-01.json) exactly reproduces all **19,691
scalar comparisons**, authenticating 14 payloads and the original source capsule.
The [extended evidence audit](ref-003c-evidence-audit.json) adds independent
metadata checks against the retained native geometry and accepted Cells runtime.
It calls neither simulator and performs no ODE execution. A fresh-process test
actively refuses imports of Cells, BETSE, NumPy, JAX and SciPy while that audit
runs successfully; the zero-model-call claim is not merely an output flag.

The [geometry diagnostic audit](ref-003c-geometry-audit.json) separately verifies
one actual SVG centre, native `QhullError` at the Delaunay call, the retained
failure warning, and all 332 installed BETSE source identities. It returns
`native_one_centre_rejection_confirmed` with `alignment_qualified: false`.
A failed one-point seed cannot be relabelled as a successful one-cell comparison.

The original numerical results remain unchanged: maximum matched voltage
difference 5.90e-13 V, per-cell ionic rate difference 1.15e-12 fmol/s, and maximum
normalized tolerance score 0.282. No scientific criterion or captured source
file was changed to obtain this closeout.

## Audit improvements, without rewriting the captured checker

Tests on copied, rehashed evidence exposed three metadata gaps in the original
audit: agreeing altered copies of cell-centre coordinates, agreeing altered
runtime claims, and an unchecked `trajectory_run` claim in the capture receipt.
These did not invalidate the actual packet's numerical result, but the original
audit alone did not reject those altered claims. The new
[evidence layer](../validation/betse/cluster_evidence.py) independently checks
the preserved geometry/runtime and enforces the receipt's no-trajectory scope.
The frozen driver, arithmetic checker, protocol and nine-file source capsule
remain unchanged; both the older boundary and the stronger rejection are tested.

The negative geometry audit now checks the meaning of the failure as well as
file identities. It rejects an invented success, another exception or traceback,
missing warning, changed dependency/source inventory, altered SVG and wrong
requested centre count. It does not claim every possible native one-cell route
is impossible. The original one-cell protocol and five preparation attempts
remain preserved and unqualified.

## Test scope and preservation

The [final 171-test result](ref-003c-checks-02.xml) passes in **20.98 seconds**,
with no failures, errors or skips and warnings treated as errors:

- 103 preserved passive-law / one-cell preparation adapter tests.
- 25 seven-cell synthetic-checker and actual Cells preparation/domain tests.
- 43 new actual-packet tests: positive audits, model-import isolation and
  40 rejection cases covering numerical corruption, metadata forgery, false
  geometry claims and linked evidence.

Rehashed corruption tests update payload digests deliberately, so stale file
hashes alone cannot explain their rejection. Only pytest-owned copies are altered.
The first passing 171-test run is [also retained](ref-003c-checks-01.xml); the final
run makes the joint runtime forgery target the existing `cells_version` field.
The earlier doubled-availability preflight failure remains part of D067's history.

The [pre-closeout preservation record](ref-003c-preservation.json) binds 815
existing files and the earlier 800-file pre-probe baseline. The
[closeout receipt](ref-003c-closeout.json) records eight intended status/design
document edits, 807 unchanged closeout-baseline files, and 793 unchanged files
from the pre-probe baseline. All **352 accepted implementation files / 51
production modules** remain unchanged. Lint and formatting checks pass across
`src`, `tests`, `scripts` and `validation`.

The previous **4190-test production matrix was not rerun**: this slice adds only
offline evidence tooling, tests and documentation. Stable 0.14.0 and accepted
development 0.15.0.dev0 are unchanged. Neither reference environment nor any
continuing research agent's workspace was modified.

## Next step

The [first trajectory design](../docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md) proposes
a 1 ms baseline and blocked control, with independent native/Cells timestep
refinement. Its immediate engineering task is a read-only native observer and
explicit mapping between raw native labels and elapsed update times. Native
ordinary output skips the first update and lacks complete per-ion transfer
history; comparing curves without resolving those details would be premature.

Next implement and test that adapter, then freeze the numerical protocol before
capture. The design is not yet trajectory preregistration or a passing timestep.
No trajectory or automatic long follow-up job was launched. No job remains
running or scheduled; retain the [detached/no-poll policy](../AGENTS.md).
