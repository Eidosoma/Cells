# SPEC-010 production pump process qualification handoff

2026-09-16, D111. The user authorized continuation. The
[coupled numerical review](NUM011_COUPLED_CLOSEOUT.md) is closed. Implement the
[named production process](../docs/KINETIC_PUMP_PROCESS.md), keeping ordinary
model/configuration integration as the next explicit engineering slice.

## Implemented now

`src/cells/processes/kinetic_pump.py`: numeric parameter/result pytrees,
explicit maintained chemical drive, signed mass-action rate, stable saturation
arithmetic and a per-route domain predicate. No biological identity, Python
case table, solver, inventory update or reference code enters the kernel.
The old synthetic law remains unchanged. Host schema/layout integration,
ordinary-runner acceptance and stable promotion are not implemented here.

All **352 previously accepted implementation files** still authenticate; one
new module makes the package inventory **52 instead of 51**. The pre-change
archive and runtime were authenticated before the new module was added, in
D110's review registration. The complete package identity changes despite no
old-file edits: old snapshots remain tied to their preserved source context.

## Short software results

- [Process receipt 02](spec-010-pump-process-checks-02.xml): **32 pass / 3.17 s**.
- [Gate receipt 02](spec-010-process-gate-checks-02.xml): **10 pass / 1.76 s**,
  including actual six-state NumPy/eager/compiled source-contact smoke: 180
  comparisons to saved oracle/native values, not a new native simulation.
- [Process receipt 01](spec-010-pump-process-checks-01.xml) preserves 31 passes /
  one failed test in 3.15 s. The manufactured stall used cancellation of large
  float64 energies and therefore retained a 2.91e-11 J/mol roundoff affinity.
  The exact-zero test now uses an exactly cancelling arithmetic fixture. The
  law, original source probes and physical comparison budgets were not changed.
- [Gate receipt 01](spec-010-process-gate-checks-01.xml): **10 pass / 1.81 s**;
  the final check also binds the collected regression count and declared deadline.

Final process software SHA-256:
`7d52ae79eefe19ac5ba9220924c746e9030a97826a4dd5547ccd9e015f246e60`.
Final gate software SHA-256:
`d362e42dc921e23221c8618c78f10b0238a177a481c2f8719cc728dad930f93b`.
Prelaunch lint/formatting (743 files) and whitespace checks pass; all 1,458
checked local document links resolve. **361 source/contract/report inputs**
authenticate, including the 352 unchanged accepted files and nine additions.

The independent coupled audit has its own 20 passing checks and immutable
source capsule; it is not rerun by this job.

## One prospective detached attempt

Freeze the accepted implementation files plus new process, tests, validation
tools, contract and handoffs. Authenticate D110 and D108 receipts, all original
coupled/source-contact payloads, the unchanged old source bytes and pinned
runtime packages before work. Neither original capture nor historical test
driver is edited.

1. Evaluate the new production process on all 31 matched-constant source-contact
   states, NumPy/eager-JAX/compiled-JAX. Compare five readouts to both the saved
   independent oracle and saved native results: **930 comparisons**, with the
   original absolute/relative budgets and exact blocking. The third native
   return is outward sodium, not a separately owned ATP turnover rate.
2. Run a targeted five-file / **348-test** matrix: existing bioelectric-cell, multispecies,
   finite-extracellular production and finite-extracellular ownership tests,
   plus the new process unit tests. This is not the full historical/release
   matrix, and a pass does not qualify a new simulation family.
   Read-only collection succeeds in 1.19 s before registration; the controller
   requires exactly 348 tests with no failures/errors/skips, not just a zero exit code.

CPU 0–3, float64/JIT enabled, one BLAS thread; **60 s contact / 600 s regression /
900 s controller**, **32 MiB/file / 128 MiB disk artifacts**, not a RAM cap.
Write durable source capsule, registration, logs, numerical comparisons, JUnit
and terminal completion/failure. No polling, retry, automatic result review or
additional campaign. A success is `process_qualification_pass_pending_review`.

After user-requested inspection, proceed to the versioned configuration and
conservative finite-bath composition described in the process contract. Native
full-loop comparison, long equilibrium, experimental plausibility, GPU and
whole-organ scale remain separate validation work.
