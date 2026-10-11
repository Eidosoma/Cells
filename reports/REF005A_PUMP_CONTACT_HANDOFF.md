# REF-005a Na/K kinetic contact: D107 handoff

2026-09-16. The user approved all next tracks and clarified that Cells should
ultimately be at least as realistic as BETSE. The
[active plan](../docs/BETSE_REALISM_AND_NEXT_STEPS.md) makes that a detailed-model
requirement; this first component panel does not fulfill it by itself.

## Completed in this slice

- Recorded the successful [D106 timed-channel closeout](REF004D_TIMED_RELEASE_CLOSEOUT.md).
  Read-only authentication checks all ten audit files / 203 source inputs /
  37 historical reports and all 555 original capture files. No numerical audit
  or simulator was rerun. Accepted implementation remains 352 files / 51 modules.
- Specified [substrate-dependent Na/K kinetics](../docs/BETSE_PUMP_CONTACT.md)
  separately from the existing synthetic pump and distinct BITSEY nominal law.
  Added an 80-digit thermodynamic reference, pure NumPy/JAX validation prototype,
  actual native-function worker, strict comparison and detached controller.
- Reviewed [junction source/lifecycle differences](../docs/BETSE_GAP_JUNCTION_PLAN.md)
  and scoped held-open transport before dynamic gating. No junction capture yet.
- Prepared a [biological benchmark candidate](../docs/BETSE_BIOLOGICAL_BENCHMARK_PLAN.md)
  with source-labelled data. Original abstract versus BETSE table permeability
  values differ; uncertainty definitions and chloride handling need further
  investigation. No biological run, calibration or claimed acceptance.

## Software verification

Final focused suite: **70 passed in 16.19 s**, no failures/errors/skips,
[receipt 04](ref-005a-pump-contact-checks-04.xml), SHA-256
`e18e842cd76cba665d7a1d4b116c56daa871449b40f49a3b2ba8c50382cc0338`.
This includes real native and prototype smoke on three prescribed states
(baseline, exact block, mathematical reverse): twelve backend/fixture probes
across native, NumPy, eager JAX and JIT JAX. No cell-world setup or integration.

Other checks cover positive-input/domain rejection, material/current units,
stoichiometry and third-return interpretation, dissipation, stall/reversal,
area/capacity/block scaling, synthetic-law nonequivalence, corrupted comparison
columns/coverage, metadata guards, no-poll launch, durable failure/timeout,
synthetic controller success, attempted-run preservation and distinct biological
data sources. Synthetic fixtures are not executed native-panel evidence.

Earlier receipts remain unchanged:

| Receipt | Outcome | Meaning |
| --- | --- | --- |
| [01](ref-005a-pump-contact-checks-01.xml) | 57 passed / 7.99 s | Initial mathematical/controller checks |
| [02](ref-005a-pump-contact-checks-02.xml) | 66 passed / 8.11 s | Added metadata, replay and biological-data checks |
| [03](ref-005a-pump-contact-checks-03.xml) | 69 passed / one failed / 15.26 s | Native smoke completed, but its test parsed startup logging as JSON |
| [04](ref-005a-pump-contact-checks-04.xml) | 70 passed / 16.19 s | Smoke uses a separate payload file; native logging and mathematical budgets unchanged |

The detached controller already separates worker JSON payloads and logs; only
the smoke harness needed that correction. No source law, comparison tolerance
or native implementation changed to repair the test. Repository lint, formatting
(722 Python files at final inspection) and whitespace checks pass. Full production regression is
not rerun: production and dependencies remain unchanged.

## Registered panel and handoff boundary

Candidate: **31 states × two constant profiles × four engines × five numeric
columns = 1,240 comparisons**. Record raw native/prototype densities and every
comparison row. Independently derive rates from 80-digit thermodynamics. Keep
exact zero-block/zero-capacity checks and the declared near-stall absolute error
floor. Capture is prescribed-state contact, not a pump–leak trajectory.

Freeze the five new Python files, pump contract, candidate-data fixture and bound
reports/helpers in the source capsule before either worker. Bind the final XML,
full pinned upstream source, installed 332-file native Python tree and accepted
Cells preservation. The broader next-step/junction/biological planning documents
are living indexes, not numerical inputs to the pump capture.

One detached job: CPUs 0–3, **45 s per worker / 150 s total**, **8 MiB/file /
32 MiB aggregate disk artifacts**. This is not a RAM restriction. Logs and
terminal result/failure receipts persist. A capture pass is
`contact_pass_pending_audit`; it neither installs a production pump nor completes
independent saved-data review. Registration/launch records establish actual
execution state; this handoff does not claim the full panel has run.

No polling, automatic retry, post-run audit, regression, coupled trajectory or
GPU job. The next user-directed step is to inspect the saved contact result;
then review it before production kinetic integration and coupled acceptance.
The biological and junction plans remain active routes toward the larger realism
target, not features silently removed from scope.
