# REF-003e1 / D085 trace-budget continuation handoff

2026-09-13 UTC. Prelaunch handoff; execution receipts are separate.
See the [contract](../docs/BETSE_TRACE_BUDGET_CONTINUATION.md),
[plan/context](../validation/betse/response_resume/trace_resume_context.py),
[resource probe](../validation/betse/response_resume/trace_resume_probe.py),
[read-only checker](../validation/betse/response_resume/trace_resume_check.py)
and [detached job](../validation/betse/response_resume/trace_resume_job.py).

The original D084 attempt stopped after 1830.727 s at the Cells trace-storage
guard, before integration of its 27th Cells row. All 16 native runs and 26 Cells
runs completed. Its 241 files, failed status, original registration, old source
capsule and payloads remain unchanged. No original aggregate Cells worker
completion exists or is invented by this continuation.

The registered change raises only eight unexecuted 640-step definitions from
16 MiB to 64 MiB `max_trace_bytes`. The maximum production reservation is
24.6415 MiB; this was not a measured RAM exhaustion. All physics, time grids,
controls, criteria, backends and earlier sources remain unchanged. Other trace
limits stay at 16 MiB so every reused definition matches literally.

Completed prelaunch evidence:

- [Preservation](ref-003e1-trace-resume-preservation.json): 1013-file baseline,
  241 original failed-attempt files, unchanged accepted implementation and
  production; only seven established status documents may change.
- [Actual production resource probe](ref-003e1-trace-resume-resource-probe.json):
  all 48 amended parser/timeline/storage checks pass, eight original-cap
  rejections reproduced, maximum estimate 25,838,496 bytes; zero integrations.
- [Saved-data reuse check](ref-003e1-trace-resume-reuse-check.json): 16 native /
  26 Cells rows, 666,108 internal comparisons, zero failures, maximum normalized
  error 0.18106284912210208; not an independent audit or response qualification.
- [Focused software receipt](ref-003e1-trace-resume-checks-01.xml): all 47 tests
  pass in 22.88 s, with warnings treated as errors. Routing mocks do not count
  as simulation evidence. All 380 Python files pass lint/format checks.
- D084's prior 114-test software completion and historical prelaunch/handoff
  stay frozen; their original source/receipt chain is authenticated, not rerun.

Freeze `ref-003e1-trace-resume-prelaunch.json` only after those gates pass. It
binds the 112-input capsule (the frozen 106 plus five new modules and one plan),
new documents, probe/reuse/test receipts and prospective resource estimates.
The original flat 88-source inventory, 352 accepted files and 51 production
modules stay unchanged. No preserved report, test receipt or ignore rule changes.

Launch only 22 new Cells rows, 8480 steps (4000 eager / 4480 JIT), then the
unchanged full saved-data comparison. Reuse 16 native / 26 Cells directly from
their original paths without copying or relabelling them. Additionally reuse
the frozen coarse eight-native / 24-Cells panel, preserving all 150 original
rejections and all 2,494,936 comparison checks (2,298,936 required).

The new worker repeats all 48 production resource checks before its first
rollout. CPU 0–3, float64, single-thread libraries; Cells/comparison stage
deadlines 6600/300 s and total 7200 s. Combined retained-plus-new artifact cap
is 1 GiB, with OS-enforced 64 MiB individual worker files. Retained size is
246,326,549 bytes; estimated combined size with allowances is 502,363,957 bytes,
largest worker file 16,791,168 bytes. Estimated Cells time with allowances is
5295 s, not a guaranteed ETA. Neither total peak RAM nor GPU use was measured.

Intended fresh destination:
`runs/ref-003e1-trace-resume-2026-09-13/capture-01`.
Only `launch.json` establishes launch; `capture.json` or `failure.json`
establishes completion. This document does not assert either. Launch once
detached and return control without polling. Later status inspection,
independent numerical audit and regression await user instruction. Failure
preserves partial outputs without automatic retry or expansion.

Even a passing required-gates capture remains pending independent audit.
Keep coarse/intermediate and across-hold diagnostic failures visible; do not
claim native/forcing convergence, full BETSE parity, biology, organs or GPU
qualification from this resource amendment.
