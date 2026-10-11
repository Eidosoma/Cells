# REF-003e0 expanded bridge: independent closeout

2026-09-12, D078. The user approved the separate saved-data audit/regression
after reviewing the completed D077 capture. Do not rerun either simulator.

## Evidence and scope

D077's [capture receipt](../runs/ref-003e0-expanded-2026-09-12/capture-01/capture.json)
reports 72 completed native runs / 3360 observed steps in **203.562 s**, no
Python warnings, 36 observer pairs, 24 profile/no-op comparisons and 12 exact
original-pilot overlaps. Its 802 files include 798 manifested payloads and a
67-file adapter capsule. Output before the receipt is **644,923,963 bytes**.
All earlier accepted/rejected evidence and the unchanged Cells implementation
remain in scope for preservation. The capture remains unqualified pending
this separate closeout; its historical receipt must not be relabeled.

Audit only the registered seven-cell / 30-face finite-bath, 1 ms passive/blocked
SIM panel: both F/R profiles, 25/12.5/6.25 µs, profiles-off/default-profile-on/
zero-amplitude controls and independent observer-on/off partners. This is
neither equilibrium preparation nor a nonzero intervention experiment.

## Independent checks

The [audit](../validation/betse/expanded_audit.py) reads saved JSON and pinned
source text. It does not call the capture checker, native runner or Cells
integrator. An import fence rejects BETSE, Cells, NumPy and JAX in the audit
process. Source ZIP members are hashed; native pickle presence and file digests
are checked, but their objects are never deserialized.

The audit derives the row grid from the retained trajectory protocol, checks
it against the expanded registration, and independently checks:

- Complete file layout, digests, source capsule, registration/prelaunch links,
  timestamps, serialization presence, installed-native provenance and resources.
- Real core/entry/final states, shapes, dtypes, bytes, membrane ownership and
  unchanged disabled controls. Entry charge/voltage must match INIT at the
  actual constant set and timestep, not a matched-constant substitute.
- Explicit profile and event metadata, with a separately computed N/(N−1)
  conversion of all three pulse-time parameters. Raw labels and elapsed
  update times are checked separately.
- Full native lifecycle and every event/flux/update boundary, including the
  pinned `electroflux` voltage nonce. A no-op event does not imply that later
  flux evaluation leaves voltage bytes unchanged.
- All ordinary/final INIT correspondences, 36 observer controls, 24 variant
  controls, and 12 physical/numerical overlaps with the qualified pilot.

The frozen independent arithmetic evaluates **1,232,616 comparisons**:
36 observed rows × 266 initial/final checks plus 3360 steps × 364 checks.
These cover membrane flux, charge, concentration, current and cell/bath
transfers with the original tolerances. Auxiliary histories and final-to-step
links are also verified. Labels include the variant so duplicated parameter
settings do not make failures ambiguous. Comparison count is coverage, not
the number of independent biological observations.

Retain only one group's baseline and current pair in memory. Do not load the
whole panel as one Python object or copy 645 MB into a new audit packet.
Existing capture data is read-only; audit output contains results, logs,
registration, source capsule and regression evidence.

## Tests, resources and launch boundary

All **143 focused preflight tests pass in 48.73 s**. They inspect actual saved
rows across the complete grid, controls,
rehashed-array corruptions, false metadata/coverage, missing or linked files,
changed capsule members, import exclusions, qualification gates, timeouts and
detachment. They do not execute the complete independent arithmetic panel.
The [prelaunch receipt](../reports/ref-003e0-expanded-audit-prelaunch.json)
records actual test count/time, whole-tree quality and final source hashes.

The detached job then runs the independent arithmetic audit and a focused
regression containing D075's 100, D076's 65, D077's 125 and D078's 143 tests:
**433 total**.
Do not rerun the older full adapter suite or 4190-test production matrix.

Resources are estimated prospectively from D076's 6.278-second audit /
24.571-second regression, the expanded 14× observed-step count and the measured
new preflight duration. With explicit allowances the estimate is **147 seconds
per stage** and **11,628,348 new artifact bytes**. The
[job plan](../validation/betse/expanded_audit_context.py) binds **180 seconds
per stage / 420 seconds total**, CPUs 0–3, single-threaded numeric libraries
and **64 MiB** of new retained artifacts. All **345 Python files** pass quality
checks; the new source capsule has 71 files. The artifact limit is checked
between stages and at closeout, not a filesystem quota or peak-RAM bound.

After prelaunch succeeds, register once into a fresh directory:

```bash
.venv/bin/python -B validation/betse/expanded_audit_job.py launch runs/ref-003e0-expanded-audit-2026-09-12/audit-01
```

Return immediately after detached launch under [AGENTS.md](../AGENTS.md).
The user requests status; no repeated polling, automatic retry or subsequent
experiment. Preserve failure receipts, logs and partial audit evidence.

Only a passing numerical audit **and** complete focused regression closeout
qualify this expanded zero-amplitude bridge. A standalone `audit.json` remains
pending regression; `completion.json` is the joint verdict. Nonzero held-drive
responses, biological plausibility, longer runs, restart, organ models, GPU
execution and stable release promotion remain separate work.
