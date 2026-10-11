# REF-004d: reference-gated timed-release handoff

2026-09-16, D105. The user authorized independent review of the successful
D104 reference and the subsequent timed native/Cells comparison. Implement both
as one gated, detached job: **no simulator worker may start before reference
review passes**. Production remains stable 0.14.0 / accepted development
0.15.0.dev0, with all 352 implementation files / 51 modules unchanged.

## Completed software verification

All **121 focused tests pass**, in two disjoint bounded suites: **107 in 36.15 s**
and **14 in 29.33 s**, without failures, errors or skips. No full 2 ms reference
review or response experiment is included in these software results.

The real native smoke runs four 25-microsecond intervals for all four conditions,
with observed/unobserved partners: eight phases / 32 updates. The real Cells
smoke uses suppression/release over those four intervals on eager and compiled
JAX, plus a release-boundary resume: two trajectories / one resumed segment,
four complete checkpoints / 216 arrays. It checks full state carry, intrinsic
gates under block, copied-state one-sided RHS, observer timing, full numeric
input non-mutation, restart and backend agreement. The full detached panel—not
these small fixtures—must establish all-condition, two-history trajectory results.

Saved-reference callback tests cover DOP853 and Radau records, segment/dense
state identities, one-sided rates, agreement, analytic gates, thermodynamics,
controls and interval transfer. Negative tests reject corrupted evidence and
wrong state/input clocks. Synthetic comparison-assembly tests distinguish retained
coarse diagnostic misses from rejected finest-grid comparisons. Controller tests
cover reference-before-simulator ordering, changed gate digests, subprocess
failures/timeouts, durable receipts, exclusive output and detached no-poll launch.
Checkpoint tests reconstruct right-continuous event position from all control
timelines and reject even correctly rehashed wrong-clock manifests.

Every earlier software result is retained:

| Attempt | Actual result | Disposition |
| --- | --- | --- |
| 01 | Foreground 55 s cap, exit 124; no finalized XML | [Timeout record](REF004D_TIMED_RELEASE_SOFTWARE_TIMEOUT.md); fixtures split/bounded |
| 02 | 60 passed / one failure, 24.12 s | New native checker supplied an elapsed-time scalar to a snapshot-only helper; explicit snapshot mapping fixes it |
| 03 | Eight passed, 28.66 s | Initial Cells state/restart/backend/side checks |
| 04 | One failure, 19.52 s | Static-block voltage compared against an intermediate nonce-shifted boundary |
| 05 | One passed, 19.67 s | Full native smoke after exact source-operation/boundary checks |
| 06 | 85 passed, 7.96 s | Expanded reference, comparison and controller checks |
| 07 | 91 passed, 30.68 s | Expanded non-Cells suite |
| 08 | Ten passed / one failure, 29.80 s | Old constant-input checkpoint checker assumed event zero; actual timed checkpoint correctly held event two |
| 09 | 107 passed, 36.15 s | Final non-Cells suite |
| 10 | 14 passed, 29.33 s | Final Cells and complementary controller/receipt checks |

All corrections are in new validation tooling. No native/Cells model, captured
old value, original checker or physical tolerance was changed. The FULL loop's
six 1e-25 V nonce additions are checked in source order, and completed blocked
voltage must still equal the previous completed voltage exactly. The new
checkpoint decoder retains the existing full state/layout checks while replacing
the constant-input clock assumption with the registered right-continuous schedule.

Final receipt hashes:

- `ref-004d-timed-release-checks-09.xml`: `f4264b756dc5589442f034e921d65fc5450253288ca490b96866ebbcce1e7d81`.
- `ref-004d-timed-release-checks-10.xml`: `623b58a86fecf20e1d6e2c95d6f5a461e8f0f84739c6ab384191da08f912abb5`.

Registration requires their disjoint union, including both real engine tests;
it cannot accept the non-Cells suite alone. Earlier XML files and the timeout
record are also hash-bound. Repository lint, formatting and
whitespace checks pass. No full production regression or GPU job was run.

## Prospective experiment and evidence boundary

The [contract](../docs/BETSE_CHANNEL_TIMED_RELEASE.md) retains D101/D104's seven
cells, one finite bath, positive intrinsic Kv1p5 permeability, two initial gate
histories and baseline/no-op/static-block/suppression-release conditions. The
window is fixed at 2 ms; block/release are at 0.5/1 ms. All prior physical,
refinement and contrast budgets remain unchanged.

First authenticate the 34-file D104 packet and reconstruct all **1,485,380
numerical comparisons** with alternate audited algebra and dense evaluation.
Independently reconstruct signal thresholds and signed final history diagnostics.
This is not a reference reintegration or third ODE solution. A hash-linked
review pass, independently checked by each worker, is required for simulation.

Then capture **48 native phases / 8,960 updates / 96 input applications / 24
observer pairs**, **32 Cells trajectories / eight release-boundary restarts**,
and **48 checkpoints / 2,592 arrays**. Separate elapsed boundaries from native
printed labels and one-sided fresh currents from integrated interval currents.
Check complete states, conservation, thermodynamics, no-op neutrality, native
source-order operations, own-state constitutive laws, reference contact,
refinement, eager/JIT and restart agreement, and 12 signed history contrasts.
Save coarse diagnostic failures without promoting them to passes.

The new capsule binds **194 validation source inputs / 30 historical reports**,
the two final software XML receipts and the unchanged prerequisite/production
chain. Mutable progress indexes are outside the frozen capsule. Never alter
registered code or artifacts after launch.

One fresh detached run at `runs/ref-004d-timed-release-2026-09-16/capture-01`:
CPUs 0–3, **1,800 s total / 480 s native worker / 600 s Cells worker / 128 MiB
per file / 512 MiB aggregate artifacts**. These are artifact limits, not a RAM
allocation. Logs and failure/partial evidence are durable; no polling, retry,
automatic post-capture audit, full regression or GPU work follows.

Actual launch/completion/failure receipts establish status. A successful result
is `timed_release_capture_pass_pending_audit`, not a qualified biological release
response, broad BETSE parity, native restart or GPU validation. The next user
status request can inspect the result and decide the separate capture audit.
