# REF-004b / D092 independent single-transfer audit handoff

2026-09-14. **Audit implementation and focused regression complete; detached
audit completion is separate.** See the [audit contract](../docs/BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md)
and [conditional dynamic-pilot outline](../docs/BETSE_CHANNEL_DYNAMIC_PILOT.md).

## User-reviewed capture

D091's runtime-corrected capture passed in **21.272 seconds**, without warnings:
four native preparations, twelve native single updates, and twelve matched
Cells transfers on each of NumPy, eager JAX and compiled JAX. All **37,068
comparisons passed**. Its original status remains `capture_pass_pending_audit`.

Capture: `runs/ref-004b-runtime-fix-2026-09-14/capture-01`.

| Anchor | SHA-256 |
| --- | --- |
| Completion | `e2bbd1e45f0b04845603f29f6fb932f239a22045650128989f2aa93dc0f57f09` |
| Registration | `90dc854e2a8b32a350127325d8a49a9c8a7159deb9c08e71fdd85c02b285a322` |
| Comparison | `4d5d491dacca611da7d3d44a89a8de63795046705790c5aaee05b8ab4772918d` |

All **54 capture files**, **76 capture-source inputs**, accepted **352 files /
51 production modules**, installed **332 native Python files** and both earlier
failure packets authenticate unchanged. Native world archives are hashed, never
unpickled. Preparation/before/after/definition files agree with aggregate output.

## Independent check and regression evidence

The audit first replays the original comparator exactly, then independently
reconstructs every one of its 37,068 numerical rows using **80-digit Decimal**
arithmetic from raw saved fields. The independent module imports only `math`
and `decimal`, not either simulator or any original comparator/formula helper.
Exponential-odds kinetics, rational gate stepping, direct-exponential GHK,
face-to-cell sums, six-species inventories, current signs, finite-bath exchange
and charge/voltage accounting are rebuilt separately. Both stored actuals and
stored expectations are reconciled under the original tolerances. Twelve data
definitions and two hidden-state controls receive additional independent checks.

First software attempt: **59 passes / seven setup errors in 3.33 s**. The new
auditor wrongly expected an absent channel key; canonical Cells definitions
use explicit `channel: null`. Corrected that representation check without
changing the saved definitions or their physics. Added missing-key/empty-map
negative controls and required a passing baseline before corruption tests.

Second attempt: **67 passes / one test failure in 21.03 s**. All 37,068 numerical
rows reconstructed successfully. A deliberate P corruption was correctly
rejected by the hidden-state reconciliation guard, but its test only expected
the earlier reconstruction guard. Corrected the test's exception boundary;
no numerical expression or acceptance criterion changed.

Final combined regression: **220 tests pass in 33.27 s**, no failures/errors/
skips: all 152 original tests plus 68 new audit checks. Repository lint/format
and whitespace checks pass. Exact replay, full independent reconstruction,
corruptions, endpoint/charge mapping, import fences and failure receipts pass.
The original synthetic-model, parameter-loader and real-worker-startup tests
also rerun as software tests; the numerical capture itself is not rerun.

Retained XML receipts:

| Receipt | SHA-256 |
| --- | --- |
| `ref-004b-transport-audit-checks-01.xml` | `ee6ba0c7208520260a11faf8007e89db5a66d5b86f6a40a73b9a30f15aadfebf` |
| `ref-004b-transport-audit-checks-02.xml` | `f6352aa62d7a6c9b258e2ed8fec59e1f04acd7ee5ea0f56da50da5cb2d72baf8` |
| `ref-004b-transport-audit-checks-03.xml` | `605dda973a2565b1487423ac6d17f212725cf95cf434dd2affaa388c8e8a1c08` |

Legacy test subprocess artifacts are retained separately under
`reports/ref-004b-native-config-contract-03` and
`reports/ref-004b-worker-startup-contract-02`. Their original D090/D091 packets
remain unchanged.

## Registered detached audit

Bind **83 source-capsule inputs**, all 54 unchanged capture-file hashes, the
three capture anchors, historical handoffs, fixed audit plan and the passing
220-test XML before launch. Actual output:
`runs/ref-004b-transport-audit-2026-09-14/audit-01`.

The fresh audit process forbids Cells, BETSE, NumPy, JAX and SciPy imports.
Replay and rebuild saved arithmetic; do not run a simulator, an old audit or a
new regression campaign. Preserve full independent comparisons and any rejection.
Limits: **120 seconds / 64 MiB aggregate / 32 MiB per file**, CPUs 0–3. File
budgets are not RAM ceilings. Launch once detached and return without polling,
automatic retry, audit chaining or dynamic expansion.

Only an actual `single_transfer_audit_closed` completion qualifies this seven-
cell, one-bath, 298.15 K, matched-constant, 25-microsecond, channel-only prescribed
transfer panel. No full native/Cells trajectory, production-integrator comparison,
biological calibration, general BETSE parity or GPU claim is made here.

The next outline proposes a small constant-control channel–voltage feedback
study with independently refined methods. A 2 ms horizon is only a candidate
for assessment, not a registered numerical choice. Native full-loop preparation,
observer neutrality and resource/numerical checks come first. No pilot launches
automatically after this audit.
