# REF-003d v2: preserved rejection and finer native steps

2026-09-12, D070. **The original numerical rejection is confirmed; the refined
panel is launched detached, with its result not yet reviewed.** No v2 model
trajectory has been run during the engineering preflights.

## Original failure, retained without relabelling

The first panel completed 24 native and eight Cells runs without warnings in
79.69498 seconds. Its [comparison](../runs/ref-003d-2026-09-12/trajectory-01/comparison.json)
failed 36 of 129,384 checks: 18 native-refinement and 18 cross-program comparisons,
all on shared-bath Na/K amount increments. The largest normalized discrepancy is
2.24680697. The [failure receipt](../runs/ref-003d-2026-09-12/trajectory-01/failure.json)
remains `failed_not_qualified`; there is no passing verification receipt.

The new [preservation](ref-003d-v2-preservation.json) hashes every one of the
119 existing packet files / 23,075,224 bytes, its registration/source capsule,
and an 834-file workspace baseline. The [read-only audit](ref-003d-failure-audit.json)
exactly reproduces the original comparison and all failures without importing
Cells, BETSE, NumPy or JAX. Independent endpoint arithmetic confirms that small
same-direction per-cell discrepancies sum in the shared bath, while material
residuals are much smaller. Native endpoint convergence orders are approximately
1.006; extrapolation reduces the largest bath endpoint difference to about
7.4e-10 fmol. This supports the timestep explanation, but is diagnostic rather
than a qualifying native trajectory or biological result.

## Prospective amendment, not a tolerance change

The [v2 protocol](../validation/betse/trajectory_refinement_protocol.json) differs
from [v1](../validation/betse/trajectory_protocol.json) in exactly four top-level
fields: revision, scope text, native step ladder and maximum artifact bytes.

| Setting | v1, retained failure | v2, prospective |
| --- | --- | --- |
| Native steps | 100 / 50 / 25 µs | 25 / 12.5 / 6.25 µs |
| Updates per native run | 10 / 20 / 40 | 40 / 80 / 160 |
| Total observed native updates | 280 | 1120 |
| Artifact allowance | 64 MiB | 128 MiB |

The 1 ms passive/blocked conditions, seven cells / 30 native faces, effective
6.75 pL finite bath, separate constant profiles, auxiliary fixed charges,
disabled mechanisms, common times and every instantaneous/cumulative/trajectory
criterion stay unchanged. Cells retains all eight identical eager/JIT runs with
0.1/0.05 ms steps. The cumulative amount allowance remains 1e-10 fmol, now applied
over up to 160 updates without widening. Native convergence and matched-constant
cross-comparisons remain mandatory. No final native instantaneous rate is invented.

The denser histories require more storage: the old packet is 23.1 MB, including
14.55 MB of native JSON records; fourfold recording growth leaves inadequate
headroom at 64 MiB. Raise storage explicitly to 128 MiB and keep complete records.
CPUs 0–3, single-threaded numerical libraries, 90 seconds per worker and the
180-second total bound remain unchanged. These are limits, not promised runtime.

## Engineering and preflight evidence

The new [harness](../validation/betse/trajectory_refinement.py) calls the frozen
v1 native/Cells worker functions; it does not edit their globals or either model.
The [new panel comparator](../validation/betse/trajectory_refinement_check.py)
reuses unchanged saved-state arithmetic. Additional gates require all ordinary,
final and trace fields of repeated 25 µs native runs to reproduce v1, plus all
eight Cells state/readout arrays and diagnostics. Numerical array equality
includes dtype, shape and bytes; elapsed run timings are excluded.

- [New preflight](ref-003d-v2-preflight-01.xml): all 48 tests pass, 8.85 s.
- [Combined adapter suite](ref-003d-v2-checks-01.xml): all **276 tests pass**,
  32.48 s reported by pytest, no failures, errors or skips.
- Lint and formatting checks pass for all 313 Python files.

New tests exercise allowed/forbidden amendments, all finer native input mappings,
80/160-step synthetic observers, source-bound registration, retained original
failure integrity, a fresh-process model/array-library import fence, independent
endpoint diagnostics, rehashed overlap corruption, and detached launch/worker
failures without automatic retry. These tests do not run full model trajectories.

All 352 accepted implementation files / 51 production modules and all 29 v1
captured adapter files remain unchanged. The original launch report remains a
historical record. The old 4190-test production matrix is preserved, not rerun;
stable 0.14.0 and accepted development 0.15.0.dev0 are not promoted. Unrelated
ongoing research and the reference dependency environments are untouched.

## Detached handoff

Launched at **17:56:14 UTC**, PID **1897018**, into the exclusive target
`runs/ref-003d-v2-2026-09-12/trajectory-01`.
The [launch receipt](../runs/ref-003d-v2-2026-09-12/trajectory-01/launch.json) records
`launched_detached`; registration SHA-256 is
`b3a26038fec113443f6a57ca1b4ac3b6c905d7be2f9d629d2d839c9cdb12c883`.
No capture status or numerical result was polled for this handoff.
The [prelaunch check](ref-003d-v2-prelaunch.json) binds the passing test receipt,
allowed documentation changes, preserved packet and current source identities:
827 of 834 existing files are unchanged, with exactly seven documentation edits.
Registration and a 35-member source capsule precede worker execution. All v2
source/protocol files become frozen at that point; do not edit captured files.

The new folder retains registration, ordinary/observed records, complete Cells
histories, phase/seed artifacts and durable worker/coordinator logs. A passing
capture writes `comparison.json` and `verification.json`; failure writes
`failure.json` and retains partial evidence. No automatic retry or criterion
change follows. Under the [no-poll policy](../AGENTS.md), return control after
launch. The user requests the next status check; even a fresh numerical pass
requires a separate actual-packet audit and closeout. No GPU, organ, active
physiology or biological-validation claim is made by this refinement.
