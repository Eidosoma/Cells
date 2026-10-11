# REF-004b / D094 preparation-readiness audit handoff

2026-09-14. **Implementation and focused software checks complete; actual
detached audit completion is separate.** See the
[audit contract](../docs/BETSE_CHANNEL_LOOP_CLOSEOUT.md).

## User-reviewed preparation

D093 passed in **18.031 seconds**, without warnings: eight real native INIT runs,
four observer-on/off pairs, 64 updates (32 observed). All **73,744 native boundary
and 348 Cells initial-rate comparisons pass**, with twelve candidate definitions
and zero Cells trajectories. The original status remains
`preparation_readiness_pass_pending_audit`.

Capture: `runs/ref-004b-loop-preparation-2026-09-14/capture-01`.

| Anchor | SHA-256 |
| --- | --- |
| Completion | `49db72ff95caa5e69c96e476233f0874bde6a046affea5130dc1e0ad640a6efd` |
| Registration | `e8ec5eb5e6274544bfced0dec64d77509c540d25e9222ed4703ace29e211cd27` |
| Native comparisons | `56e8ca0d237d635e347b77bbf1b35e237481325d6b503326189937d2aadc304f` |
| Cells readiness | `6f04de8cc3a1b0afb7812933faf1c2d3e9d12a1f3e4e3db28e2a1a30a83e9951` |

All **74 capture files / 94 preparation source inputs**, D092's nine-file audit,
D091's 54-file capture, both earlier failures and accepted **352 implementation
files / 51 production modules** authenticate unchanged. Match 332 installed
native Python files and the recorded package/runtime identities. Native YAML
and INIT/world pickles are hash-authenticated, never regenerated or unpickled.

## Independent implementation and software evidence

The original native comparator replays exactly. Saved initial-rate comparisons
replay with frozen parameter/definition/vector-field/tolerance code, using saved
full state and RHS—not executing a production RHS or integration step. Two new
math modules use only the standard library and each other; no original oracle,
model, parser or compiler is imported by them. They independently rebuild all
74,092 numerical identities under unchanged unit tolerances and 80-digit
exponential arithmetic. Extra checks cover:

- 204 exported float64 array records and exact observer-pair state/history equality.
- Native elapsed versus label/storage clocks, partial lifecycle and final state.
- 36 absolute six-species charge snapshots alongside incremental capacitor checks.
- Twelve data definitions, complete initial states/RHS, inactive padding,
  fixed/mobile charge and shared-bath mappings, timestep grids and resource estimates.

First software attempt: **162 passes / eight failures in 22.92 s**. Complete
numerical reconstruction already passed. Eight new rejection tests expected
`RuntimeError`; the existing provenance/plan guards correctly raised `ValueError`.
Corrected only those test expectations, retaining this receipt. Added five native
clock/order/observer-pair corruption checks and fresh-process model-free
authentication. No equations, tolerances or captured data changed.

Final focused software run: **176 tests pass in 25.21 s**, no failures/errors/
skips: 96 original tests and 80 new checks. Full saved-data reconstruction passes.
Original software-only lifecycle/readiness tests rerun; no native numerical
capture is rerun. Repository lint, formatting and diff checks pass.

| Software receipt | SHA-256 |
| --- | --- |
| `ref-004b-loop-audit-checks-01.xml` | `a1b42705260189b6e5bcb628d78920aabd206bc97964968802a499031f3e2893` |
| `ref-004b-loop-audit-checks-02.xml` | `b66d159a0898696dfe184a4315fbd84ed850ccb356d64de2d414470babdec302` |

## Single-use detached audit

Bind **101 source inputs** (94 previous + six new audit files + one new contract),
all capture hashes, explicit anchors, historical handoffs and the passing
176-test XML before launch. Output:
`runs/ref-004b-loop-audit-2026-09-14/audit-01`.

```sh
.venv/bin/python -B validation/betse/channel_loop_audit/loop_audit_job.py launch \
  runs/ref-004b-loop-audit-2026-09-14/audit-01 \
  --tests reports/ref-004b-loop-audit-checks-02.xml
```

Use this destination only once. The fresh process forbids Cells, BETSE, NumPy,
JAX/JAXlib and SciPy imports; independently reconstruct saved data without a
simulator or earlier numerical-audit rerun. Retain all numerical failures and
structural failure tracebacks. Limits: **120 seconds / 64 MiB aggregate / 32 MiB
per file**, CPUs 0–3. Artifact budgets are not RAM ceilings. Detach and return
without polling, retries or automatic follow-up. This handoff predates launch;
the launch receipt establishes PID/time/registration and later receipts establish
success or failure. Mutable [progress](../PROGRESS.md) records the launch.

Only an actual `loop_preparation_audit_closed` receipt qualifies this narrow
preparation/readiness. No coupled cross-engine trajectory, continuous numerical
reference solution, native restart replay, biology, broad BETSE parity, GPU or
multiscale accuracy is qualified. The next user-directed step after a passing
audit is independent-reference integration/convergence and dynamic registration;
the proposed 2 ms / 12-native / 36-Cells panel is still only a candidate.
