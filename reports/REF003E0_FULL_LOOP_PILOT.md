# D075 / REF-003e0: full-loop pilot handoff

2026-09-12. **Adapter/prelaunch checks pass; native execution results are recorded
separately.** This document does not claim a passed trajectory. The
[prospective contract](../docs/BETSE_FULL_LOOP_BRIDGE.md) adds the first bounded
integration test of the phase/profile/event path established by D074 preparation.

## Scope and checks completed before launch

The pilot has **12 native SIM runs**: passive/blocked cases, profiles off,
default profile on, and zero-amplitude Na/K/Cl events, each with a freshly seeded
observer-off partner. All use matched constants, native 25 µs and a 1 ms
horizon. Six observed runs give 240 step/dispatch records; only 80 of those
dispatches have the targeted event settings enabled. This is narrower than the
later two-constant-set, three-timestep, 72-run expanded bridge.

All **100 focused tests pass in 7.45 s**, with no failures/errors/skips, in
[the first focused receipt](ref-003e0-loop-checks-01.xml). They test synthetic
normal-lifecycle observation, partial-state persistence, hook restoration,
missing/repeated/misordered setup and steps, explicit pilot scope, corrupted
and rehashed event records, paired controls, detached launch and timeout
handling. Fabricated event/lifecycle records built around accepted INIT data
exercise the saved-data gates; **they are not new native results**.

The checker preserves native pre-event versus post-flux boundaries, including
the upstream voltage nonce and per-step flux reset. The normal native solver
owns all preparation, event calls, integration and SIM serialization. No
production/native method is replaced and no preparation-probed phase is reused.

The full tree passes lint/format checks across **333 Python files**. The
[preservation receipt](ref-003e0-loop-preservation.json) starts from 891 existing
workspace files; only seven existing status documents are edited. All 352
accepted implementation files / 51 production modules, D074's 59-file packet,
the failed D073 attempt and all earlier accepted/rejected evidence remain
unchanged. Seven new adapter/input files bring the prospective source capsule
to 58 files. The [prelaunch receipt](ref-003e0-loop-prelaunch.json) binds focused
tests, sources, preservation and resource sizing before registration.

## Execution boundary

Session: `runs/ref-003e0-loop-2026-09-12/pilot-01`. Its
[launch receipt](../runs/ref-003e0-loop-2026-09-12/pilot-01/launch.json) records
actual detached launch, PID and registration digest; this report is the
prelaunch handoff, not an assertion that the computation is still running.

The native worker has 120 seconds, the supervisor checks 150 seconds overall,
and CPUs are limited to 0–3. A conservative 136.30 MiB storage allowance fits
under the 256 MiB panel limit; the worker also has a 32 MiB per-file OS limit.
Limits, their enforcement boundaries and partial-evidence behavior are explicit
in the contract. Logs and capture/failure receipts are durable. Nothing retries
or launches a larger panel automatically.

A completed `capture.json` can report only capture-control success pending
independent audit. `failure.json` records a rejection/error instead, retaining
available stages and trace copies. The user requests the next status check;
saved-data audits and regression jobs are not started automatically.

No new Cells simulation, old full adapter suite or 4190-test production matrix
was run in this preparation. There is no new trajectory qualification,
expanded timestep/constants coverage, nonzero response, restart, biological,
stable-release or GPU promotion. Once the pilot's saved evidence is audited,
decide on the expanded bridge before the nonzero held-drive comparison.
