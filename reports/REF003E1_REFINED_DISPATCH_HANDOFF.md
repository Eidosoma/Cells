# REF-003e1: finer dispatch prelaunch handoff

2026-09-13, D083. **Software preflight passed; actual native execution is a
separate detached job.** This document precedes launch and is not a result.

The [contract](../docs/BETSE_REFINED_DISPATCH_PREFLIGHT.md) extends only the
input-application preflight after the [D082 failure closeout](../runs/ref-003e1-response-audit-2026-09-13/audit-01/completion.json)
was reviewed. That audit completed in 50.390 s and verified, rather than erased,
the original 150 failed response comparisons. All previous evidence stays frozen.

## Implemented and checked

Eight fresh native SIM preparations cover baseline, zero amplitude, static block
and suppression/recovery at 12.5 and 6.25 µs. Record and check all **960 direct
event dispatches / 345,600 diffusion values**, without transport or integration.
The prescribed clock mapping, input tables and original 2e-14 control criterion
are fixed before execution. There is no new event at the elapsed endpoint.

Reuse the native event observer, preparation fence, metadata reader and durable
per-event writer unchanged. New mapping/checking code is in
`validation/betse/response_refinement/`, outside the installed simulator and the
historical flat adapter inventory. Original equations, Cells runner and both
runtime environments are untouched.

All **109 focused software tests pass in 36.21 s**, with warnings as errors and
no failures/errors/skips in [checks-01](ref-003e1-refined-dispatch-checks-01.xml).
All **368 Python files** pass whole-tree lint and formatting checks.
These use saved initial preparations and explicitly fabricated event/receipt
data, not native execution. Coverage includes old-map equality, both finer
clocks, targets/modifiers, physical-state invariance, endpoint hold, malformed
and rehashed evidence, source/runtime links, forbidden function entry, partial
events, timeouts and detached launch without polling. No old full regression
matrix or simulation is rerun for these software checks.

## Preservation and prospective resources

The [preservation record](ref-003e1-refined-dispatch-preservation.json) pins 979
existing files, the 150-file rejected response and the 16-file completed audit.
All 352 accepted files / 51 production modules remain unchanged. The source
capsule has 98 inputs: old 88 adapter inputs, four frozen audit modules and six
new refinement inputs (five Python modules plus the plan). Preserve the exact
recorded `.gitignore` amendment and all historical XML receipts. Only seven
existing status documents are updated; no prior captured source/report changes.

The [prelaunch receipt](ref-003e1-refined-dispatch-prelaunch.json) freezes sources,
tests, new documentation, preservation hashes, whole-tree quality checks and
the prospective budget. D080's measured 24.463 s / 25,283,869-byte preparation
attempt and 3,466,668-byte largest aggregate dispatch file supply the sizing
basis. Explicit allowances estimate 251 worker seconds, 206,406,234 artifact
bytes and 17,333,340 bytes for the largest worker file.

Hard caps: **300-second native worker, 360-second attempt, CPUs 0–3, 256 MiB
artifacts and 32 MiB per worker file**. Numeric libraries use one thread; file
limits are OS-enforced, total bytes checked between rows/at completion. This
does not measure peak RAM or predict a future response/GPU workload.

## Launch boundary and interpretation

Intended fresh attempt:
`runs/ref-003e1-refined-dispatch-2026-09-13/preflight-01`.

Registration and the source capsule precede launch. `launch.json` records the
actual PID/time; `worker.log` and the native row files retain work as it happens.
The final receipt is either `completion.json` with
`refined_dispatch_checks_pass_not_response_qualification`, or a durable failure
with partial artifacts. No failed attempt is overwritten or retried automatically.

Return control immediately after detached launch; status is user-polled. A pass
would establish actual finer-grid input application at the initial state only.
It would not establish integrated response, native/forcing convergence or
observer noninterference during transport. The next response implementation,
capture and any independent audit remain separate user-approved steps. No
biological, organ, restart or GPU qualification is added.
