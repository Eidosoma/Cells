# REF-003e0 expanded bridge: prelaunch handoff

2026-09-12, D077. This is the preparation/launch-boundary record, not a native
capture verdict. The user approved proceeding after D076's polled closeout.

## Qualified predecessor

[D076 completion](../runs/ref-003e0-loop-audit-2026-09-12/audit-01/completion.json)
passed in **32.682 s**: **88,956** independent arithmetic comparisons, maximum
normalized error **0.146996**, and **165** focused tests with no failures,
errors or skips. Numerical auditing took 6.278 s, regression 24.571 s.
No native or Cells model was integrated for that audit.

This qualifies the narrow matched-constant 25 µs, 1 ms, seven-cell
passive/blocked SIM pilot only. Its historical capture and audit preflight
receipts are not rewritten. The completion SHA-256 is
`3167c314451fb4447d805d587b1bd7433544527c432d23b59c0c1f84113544a3`.

## New preparation

The [contract](../docs/BETSE_EXPANDED_BRIDGE.md) and
[plan](../validation/betse/expanded_bridge_plan.json) specify 72 native runs:
both passive/blocked cases, both F/R profiles, three timesteps, three
profile/event controls and observer-on/off partners. Duration stays 1 ms.
Expected coverage is 3360 observed steps, 1120 enabled-target dispatches,
36 observer pairs, 24 variant comparisons and 12 exact original-pilot overlaps.
There are no nonzero interventions, new Cells runs or production changes.

Four new Python files and one plan add a separate expanded context, checker,
detached orchestration and focused tests. The native runner/observer and all
older captured sources are reused unchanged. Explicit static input expectations
do not stand in for captured preparation; actual entry charge/voltage is checked
against the appropriate retained INIT constants and timestep.

[Focused tests](ref-003e0-expanded-checks-01.xml): **125 passed in 17.67 s**.
Actual saved overlap checks and synthetic expanded fixture checks are labeled
separately. No expanded native model was run by these tests. The new
[preservation baseline](ref-003e0-expanded-preservation.json) covers 912 files,
all 142 pilot files, 11 audit-job files and the unchanged 352 accepted Cells
files / 51 production modules. Only seven pre-existing status documents may
change. The [prelaunch receipt](ref-003e0-expanded-prelaunch.json) binds final
source hashes, tests, quality and preservation before registration.

## Resources and next handoff

Conservative sizing from actual pilot files estimates **1,388,179,444 bytes**;
the largest estimated worker file is **42,565,368 bytes**. Step-scaled runtime
is 365.943 s, or 549 s with 50% allowance. Limits are prospectively enlarged to
600 s worker / 660 s total, 2 GiB panel, 64 MiB per worker file, CPUs 0–3 and
single-threaded numeric libraries. This is not measured expanded runtime.

The fresh destination is
`runs/ref-003e0-expanded-2026-09-12/capture-01`. Its
[launch receipt](../runs/ref-003e0-expanded-2026-09-12/capture-01/launch.json)
records actual launch/PID; this handoff does not infer process or completion
status. The user requests status. Do not poll, rerun, edit frozen sources or
launch an audit/regression automatically. Preserve all partial data on failure.

A passing capture is only a control/correspondence result pending a separately
approved independent arithmetic/evidence audit and focused regression.
No expanded qualification, nonzero-response, biology, organ, restart, GPU or
stable-release claim follows from this prelaunch handoff.
