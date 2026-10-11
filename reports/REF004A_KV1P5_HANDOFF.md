# REF-004a isolated-channel handoff

D087, 2026-09-13. **Implementation/preflight, before actual native capture.**
The user approved the isolated channel-first next step. This handoff is frozen
at launch; subsequent run receipts, not edits to this report, establish results.

## Completed work

- Recorded D086's user-reviewed joint closeout in the seven mutable status
  documents. The unchanged completion SHA-256 is
  `c4352798787638b1b8749672cf18376d01b404debbde0938304733792f0c75f6`.
  All 2,298,936 required checks and 336 tests pass; all 4173 diagnostics remain.
- Read the pinned native channel, base initialization/run and updater directly.
  Units, explicit-versus-equilibrium initial state, separate numerical methods,
  temperature restriction and non-clamp scope are specified in the
  [design](../docs/BETSE_VOLTAGE_GATE_CONTACT.md).
- Added one nested, offline adapter: data protocol, model-free reference/checker,
  isolated native/Cells workers, detached job and short tests. Existing flat
  adapter inventories, source chains and production modules are untouched.
- First preflight: **41 passed in 0.94 s**, preserved in
  [checks-01](ref-004a-kv1p5-checks-01.xml). Expanded preflight:
  **62 passed in 0.96 s**, no failures/errors/skips, in
  [checks-02](ref-004a-kv1p5-checks-02.xml). Final source review removes a
  redundant zero-time update after fixture-state installation and explicitly
  labels initial open fraction as derived m*h. **63 tests pass in 1.11 s** in
  [checks-03](ref-004a-kv1p5-checks-03.xml), with no failures/errors/skips.
  These use synthetic records and read-only byte checks; no native numerical
  evidence is claimed. Earlier receipts are not overwritten.
- All **389 Python files**, including four new modules, pass lint and formatting. Prior 352-file accepted
  implementation, source-review hashes and D086 completion/payloads verify
  unchanged. No new dependency, version promotion or production regression job.

## Authorized bounded capture

Six piecewise-held voltage protocols; activation, deactivation/recovery, slow
inactivation, a short pulse and two different hidden histories. Eighteen native
and eighteen compiled-Cells trajectories at 1/0.5/0.25 ms steps, 49,980 updates
per engine. Full gates/P at every registered observation, all native updates and
all Cells RK4 stages checked. Thirteen static voltages and one-step production
probes additionally exercise NumPy/eager/JIT. No production world runner,
geometry, ionic transport, current, membrane feedback or electrode model.

The 70-digit oracle separately checks the continuous solution and each
discretization. Limits precede capture, with native first-order/RK4 fourth-order
refinement and explicit roundoff-limited reports. Temperature is the existing
298.15 K engineering regime; neither gate formula implements a temperature law.
No availability/blocker semantics or native tissue-target path is tested here.

One fresh destination: `runs/ref-004a-kv1p5-2026-09-13/capture-01`.
The registration binds 11 source/design/config inputs, upstream tracked-file
inventory/license, all 332 installed Python files via worker provenance, the
existing dependency lock, accepted runtime and exact passing preflight receipt.
CPU 0–3, float64, single-thread libraries; worker limits 60/90 s, total 180 s,
64 MiB new artifacts, 16 MiB individual worker files. These are not peak-RAM
or GPU performance measurements. Failure artifacts and full comparisons remain.

```bash
.venv/bin/python -B validation/betse/voltage_gate_contact/gate_job.py launch runs/ref-004a-kv1p5-2026-09-13/capture-01 --preflight reports/ref-004a-kv1p5-checks-03.xml
```

Return after launch, without polling, retry or subsequent jobs. A successful
capture is explicitly `capture_pass_pending_audit`. After user review, request
a separate saved-data closeout before the channel-plus-membrane/finite-bath
comparison. Biological validation and general BETSE/GPU/multiscale qualification
remain distinct; prior passive input-sampling limitations are not resolved here.
