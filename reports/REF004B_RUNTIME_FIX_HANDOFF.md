# REF-004b / D091 worker-environment correction handoff

2026-09-14. **Correction and focused checks complete; fresh numerical capture
is separate.** See the [contract](../docs/BETSE_CHANNEL_RUNTIME_FIX.md).

## Preserved execution boundary

D090 completed all twelve native single-transfer cases, without Python warnings,
then stopped after **7.084 seconds**. Cells rejected the launcher's explicit
`JAX_DISABLE_JIT=false` against the registered absent value. Its CPU/float64/
enabled-JIT guard passed; no Cells transfer or numerical comparison ran.
The native execution is not independently qualified by this handoff.

The [preservation receipt](ref-004b-runtime-fix-preservation.json) binds all
**51 D090 packet files**, all **70 D090 source inputs**, historical handoff/XML
and D089's earlier 22-file failure preservation. Both failures, every old
numerical criterion and the accepted 352 files / 51 production modules remain
unchanged. Receipt SHA-256:
`6035044c548c5149050b3fbf34bd0c7005d33e8203db9e0f533479da47a36f1a`.

## Correction and actual startup evidence

Construct the child environment from its registered numerical identity before
importing JAX. Remove registered-null variables; preserve registered strings
exactly. In this run both `XLA_FLAGS` and `JAX_DISABLE_JIT` must be absent, rather
than inherited or rewritten to an equivalent-looking string. Keep the existing
strict identity check and enabled-JIT / CPU / float64 guard unchanged.

The new runner directly imports the frozen native worker, Cells worker and
comparator. Its execution-body delta is AST-checked: environment construction
and D091 provenance only. No production, native-source, dependency, physics,
protocol, tolerance or resource change.

All **152 focused tests pass in 13.25 seconds**: 76 original transport, 31
configuration-correction and 45 new runtime-correction tests, no failures/errors/
skips. Repository lint/format and diff-whitespace checks pass. XML:
`reports/ref-004b-runtime-fix-checks-01.xml`, SHA-256
`dc90dcde798fb81e3ce197dfa55e27915a69e3ede90330f51b7ea89b9692a50a`.

The **five real-worker subprocess probes pass in 4.589 seconds** total:

| Probe | Observed boundary |
| --- | --- |
| Registered absent flags, after removing injected inherited values | Actual worker passes its guards and reaches the intentionally absent native-input file |
| Explicit `JAX_DISABLE_JIT=false` | Reproduces the original exact-runtime rejection |
| Unregistered empty `XLA_FLAGS` string | Exact-runtime rejection |
| Genuinely disabled JIT | CPU/float64/enabled-JIT guard rejection |
| Deliberately mismatched registered NumPy version | Exact-runtime rejection |

Every probe authenticates the actual loaded 51 production modules, interpreter,
CPU affinity, actual package/runtime values and exception boundary. The empty
input directory remains empty. No transport, integration, GPU execution or
native simulation runs in these startup probes. Their successful startup is
not evidence that the later numerical capture will pass.

The 11-file packet with durable per-probe logs/results is
`reports/ref-004b-worker-startup-contract-01`. Aggregate result SHA-256:
`2c6ea2565689b8c084b0fccddbecaeb6ea5526e9c49875a8471160ed8fbce131`.
The unchanged legacy configuration tests also reran BETSE's parameter-loader/
type check, without world/network initialization, in
`reports/ref-004b-native-config-contract-02`; the original registered D090
configuration-contract packet remains unchanged and continues to authenticate.

## Fresh bounded capture

Freeze **76 source-capsule inputs**, unchanged scientific registration fields,
both correction amendments, both failure preservations, original native
configuration contract, passing focused XML and the real-worker startup packet.
Output: `runs/ref-004b-runtime-fix-2026-09-14/capture-01`.
Actual launch/completion/failure receipts, not this prelaunch handoff, establish
execution status.

Re-execute all twelve native cases fresh; do not reuse D090 native output as
new execution. Run the same twelve matched Cells transfers on each of NumPy,
eager JAX and compiled JAX. Native gate-before-transfer and Cells prescribed
ledger update remain explicit; this is not a new RK4 method or coupled trajectory.

Same seven cells / thirty faces, four network controls, three state fixtures,
298.15 K, 25 microseconds, matched constants and all numerical criteria. Same
CPUs 0–3, float64, **120 seconds per worker / 300 seconds total**, **128 MiB
aggregate / 32 MiB per file**. File ceilings are not RAM limits.

Launch once detached and return. No polling, automatic retry, audit, regression
campaign or dynamic expansion. Any pass is `capture_pass_pending_audit`; a later
user-requested review and independent closeout must precede a coupled pilot.
No biological, broad BETSE-parity, organ-scale or GPU qualification advances.
