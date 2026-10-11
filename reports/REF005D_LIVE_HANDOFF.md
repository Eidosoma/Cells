# REF-005d R0 live recording / matched-window handoff

2026-09-17, D125. Implement the next recording gate after
[independent offline closeout](REF005D_CODEC_CLOSEOUT.md). The complete contract
is in the [adapter README](../validation/betse/live_recording/README.md).

This is the same **1 ms seven-cell pump–leak preparation**, not an extension in
duration. Keep all physics, geometry, steps and scientific thresholds unchanged.
Preserve all frozen sources and prior accepted/rejected evidence. No Cells
production or upstream source edit is needed for this step.

The native worker streams one update at a time and retains unchanged native
histories/pickles. It compares all 36 output streams exactly against the closed
offline packet and checks eighteen new full-observer/storage-only pairs. The
Cells worker compares 24 ordinary full trajectories to the accepted files,
72 windowed paths, eighteen disk-policy outputs, six loaded full/window restart
suffixes, six zero-length continuations and two sparse-observation controls.
No new reference solver or energy-accounting formula is introduced.

Sources, receipts, budgets and all prior packet hashes are frozen in a new
registration; both workers receive its SHA from the detached launcher. One
worker failure ends the attempt with durable partial evidence. Successful
completion stays pending a separately authorized independent review.

## Verification and execution

**Current action: detached software/smoke preflight only. The full 36-row
campaign is implemented but NOT launched.** Its next execution requires the
passing preflight result and another user instruction.

Preflight development receipts are retained under `reports/ref-005d-live-*.xml`.
An early unit receipt has twelve test-harness key-access failures after the
underlying exact comparisons had passed; the assertion was corrected to use
the reviewer's actual scalar-coverage fields. Real-native smoke failures caught
two adapter-boundary issues: native float subclasses versus the plain JSON
schema, and source-owned concentration updates behind native type-check
wrappers. Fixes are confined to the new adapter, with explicit regression tests.
Neither failure was a scientific disagreement or grounds to change a threshold.
The first full-suite receipt also preserves a missing-parent temporary-directory
setup error (26 passing tests / 50 setup errors, no simulator run). Its successor
uses a new durable preflight directory; no prior receipt or output is overwritten.

The expanded second full suite reports **75 passed / one timeout in 78.34 s**:
the actual Cells smoke exceeded its original 45-second subprocess cap. No
numerical mismatch was reported; this is incomplete evidence, not a pass. Both
new real native modes already match their accepted 160-update rows exactly,
under the proposed native address-space limit. An earlier narrower Cells smoke
passed full/window/checkpoint/restart comparison in 27.23 s. Adding all disk
policies, zero-length and sparse-schedule coverage requires more preflight time.

Increase **only the new software-smoke runtime cap** to 120 seconds, add durable
Cells substage receipts, and run the entire **79-test** suite detached. Preserve
the stopped receipt and all partial artifacts at
`runs/ref-005d-live-preflight-2026-09-17/checks-02`. The final fast subset passes
**76 checks / 5.55 s**, with three real simulator smokes explicitly deselected:
[`ref-005d-live-unit-checks-03.xml`](ref-005d-live-unit-checks-03.xml).
No physics, scientific tolerance or simulation duration changes.

The new preflight controller has **300 s overall / 240 s pytest / 256 MiB total /
32 MiB per file / CPUs 0–3**, with a 1 GiB free-disk reserve. Individual native
smokes retain 35 s; the expanded Cells smoke gets 120 s. Worker address-space
limits remain 8 / 16 GiB. The controller owns a fresh test-worker process group
so a registered timeout cannot orphan a native/JAX grandchild. Pytest's internal
aliases are recorded explicitly without traversal; escaping links are refused.
Registration binds all source/helper/contract inputs and prerequisite hashes.

Current launch command (both output and receipt must be absent):

```bash
.venv/bin/python -B validation/betse/live_recording/preflight_job.py launch \
  runs/ref-005d-live-preflight-2026-09-17/detached-01 \
  --receipt reports/ref-005d-live-checks-03.xml
```

No automatic full campaign follows a software pass. Check `completion.json`
or `failure.json` on the next user-requested status turn. The produced XML is
source-bound in the preflight completion; it is not a full live matrix result.

Prepared full-campaign command, **not executed by this handoff** (output must
be absent and the new 79-test receipt must pass):

```bash
.venv/bin/python -B validation/betse/live_recording/live_job.py launch \
  runs/ref-005d-live-recording-2026-09-17/qualification-01 \
  --tests reports/ref-005d-live-checks-03.xml
```

Controller bounds: **1,800 s / CPUs 0–3 / 32 MiB per file / 512 MiB aggregate /
1 GiB free-disk reserve**. Native/Cells phase limits: **900 / 750 s**, address
space **8 / 16 GiB**. Output contains per-row native streams, retained native
pickles, comparison receipts, Cells full/window/checkpoint artifacts, logs and
exactly one terminal completion/failure. A source-bound current/high-water RSS
measurement is not a promise of constant-memory BETSE.

No automatic completion polling, retry, independent audit, broader regression,
10 ms integration or GPU job. After a user-requested result check, review the
saved evidence independently; only then revisit longer-horizon reference/domain
scoping and native-history ownership.
