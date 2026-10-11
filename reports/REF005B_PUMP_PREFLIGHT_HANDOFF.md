# REF-005b native pump–leak lifecycle handoff

2026-09-16, D115. **Prepared for one detached capture; no native pass claimed.**
See [scope and next gates](../docs/BETSE_PUMP_LOOP_PREFLIGHT.md) and the
[independently closed family prerequisite](SPEC010_FAMILY_CLOSEOUT.md).

The new adapter in `validation/betse/pump_loop_preflight` uses the unchanged
BETSE FULL INIT loop, an explicit once-only setup hook and the existing
source-scoped observer extended for raw pump/passive calls. Producer-side checks
reconstruct applied density and concentration updates, distinguish sodium
diagnostics from actual pump cycles, and compare observed/unobserved outputs.
The six controls include density scaling and boundary masking, not only a
single favorable pump+leak preparation. Production and upstream are unchanged.

Software evidence is **29 passing checks / 2.70 s** in
`reports/ref-005b-preflight-checks-02.xml`: synthetic
transfer/corruption tests, source-scoped read-only observation, strict priors,
protocol/resource/receipt checks, and actual loading of all six configurations
in the pinned native Python environment. Loading configurations is **not**
running native trajectories. Receipt 01 is retained as the earlier 28-check
scope before the real native configuration-loading check was added.

```text
.venv/bin/python -B validation/betse/pump_loop_preflight/pump_job.py launch runs/ref-005b-pump-loop-2026-09-16/capture-01 --tests reports/ref-005b-preflight-checks-02.xml
```

The launcher returns the PID, UTC time and registration digest and saves them
in `launch.json`. Its capsule freezes **613 source/configuration/contract inputs**;
the software receipt and both prerequisite closeouts are bound separately.
Twelve native runs, 48 observed steps, CPU 0–3, one BLAS
thread, 240 s worker / 300 s total, 64 MiB/file / 256 MiB disk artifacts.
Keep frozen inputs unchanged until the user asks for status/review. Logs and
terminal failures are durable; do not relaunch over an existing attempt.

Success is only `native_lifecycle_checks_pass_pending_review`. No Cells
trajectory, independent saved-data follow-up, full historical regression,
relaxation, biological validation, production modification or GPU run is
part of this attempt. The next user-requested review determines readiness
for matched initial-state/transfer mapping and a later coupled panel.
