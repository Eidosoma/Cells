# CORE-007 production acceptance

2026-09-10, D051, Cells 0.12.0. **Complete — bounded CPU/JAX engineering acceptance.**

The [state-bearing channel implementation](../docs/VOLTAGE_GATED_MEMBRANE.md)
uses the frozen [SPEC-006 law](../docs/VOLTAGE_GATED_CHANNEL_SPEC.md) and
[NUM-007 numerical qualification](NUM007_REFERENCE.md). Existing ionic model
equations, the common integrator, runner and I/O remain unchanged.

## Accepted result

The [third registered session](../runs/core-007-2026-09-10/acceptance-03/verification.json)
passes, including the independent [read-only saved-output audit](core-007-audit.json).
Verification SHA-256:
`b6c35e258fff90da5a05b232b1da774d7e2082fe7e357aec1cbc5ce80438e6cf`.

| Check | Accepted evidence |
| --- | --- |
| Frozen NUM-007 panel | All 14 cases in both eager and JIT modes, at the selected 0.5 ms step |
| Complete scalar outputs | 43: 14 JIT, 14 eager, 14 resumed, one future-input branch |
| Independent comparisons | 40,938 accepted-state rows and 356,281 observation rows; all six state fields, 26 derived readouts, control intervals and complete cubic extrema |
| Restart and branch | 14 exact fresh-process suffixes; the pulse-omission branch preserves original gates, charge anchors and ledgers |
| Bounded execution | Two scalar window runs; four original/resumed cohort runs covering 128 rounds and 332 world windows |
| Provenance | 1,580 authenticated payloads, a 204-file implementation capsule and 44 production modules |
| Complete checkpoint inventory | 488 current scalar and 54 current cohort checkpoints, including nested world records |
| Earlier-model regression | All 78 scalar trajectories, 1,777 scalar windows and ten batches/44 worlds exact; all 14 earlier multispecies trajectories / 700 arrays exact |

The largest gate discrepancy against the frozen refined implicit reference is
`7.771614e-5`, against the declared `1e-4` limit. The largest normalized trajectory
error is **0.777162**, below the passing boundary of 1, in the eager gate-only case.
The largest normalized accounting residual is 0.095572. Eager/JIT comparison also
passes the separate 0.001-times trajectory-limit check. These are numerical
checks on short synthetic fixtures, not biological error estimates or an accuracy
guarantee for arbitrary parameters and durations. Reference limits and coarse
failures remain unchanged; no new independent-reference ODE was solved.

The recorded verification work is **1436.144 s**, before its final read-only audit,
within the registered 2400 s wall allowance. The complete accepted directory is
**546,355,382 bytes (521.045 MiB)**, including the verification receipt, within the
prospectively revised 1 GiB evidence allowance. The two excluded interrupted
sessions remain intact; all three directories together occupy 1,039,626,644 bytes.
These are verification/evidence costs, not live simulator memory or performance
measurements. Scheduling corrections and reuse are detailed below.

One state-sufficiency check is useful for future multiscale design: initial gates
`(m,h)=(0.2,0.8)` and `(0.8,0.2)` have the same open fraction of 0.16, yet their
voltages differ by approximately **1.794 mV after 100 ms**. Saving only the open
fraction would lose predictive state. This does not validate biological memory
or plastic heredity by itself.

## Preserved predecessor

Accepted 0.11.0 and its strict reference environment were preserved before edits:
[preservation receipt](core-007-preservation.json). The archive contains 291 files,
including all 41 old production modules; both prior build and numerical-reference
audits pass. Archive SHA-256:
`59d4c371f57b5a758a1c6f03c77d3385b97eb079c2fc05cfaeb708e155acdda4`.

## Preflight and retained attempts

- [First production preflight](core-007-preflight-01.xml): 79 pass, 19 failures.
  All failures are the standalone JAX gate-law test using default float32 before
  the engine's CPU/float64 initialization. The test now establishes the production
  runtime explicitly; no equation, scientific tolerance or reference changed.
- [Corrected preflight](core-007-preflight-02.xml): all 98 tests pass in 71.31 s.
- [Initial saved-output audit tests](core-007-audit-preflight-01.xml): 14 pass,
  one failure from expecting 25 independently checked fields instead of the actual
  26. The inventory assertion is corrected; the valid physical audit already passed.
- [Combined targeted suite](core-007-targeted-01.xml): all 113 pass in 72.93 s.
  Includes all fourteen frozen compiled trajectories, real-stage/domain guards,
  checkpoint/branch/cohort tests, and rehashed-corruption refusal.

## Full regression

All **2883 tests pass**, with zero failures, errors or skips:

| Source context | Tests | Test time (s) |
| --- | --- | --- |
| Current production 0.12.0 | 1707 | 569.734 |
| Preserved NUM-005 / 0.10.0 | 971 | 154.505 |
| Preserved SPEC-006/NUM-007 / 0.11.0 | 205 | 18.160 |

[Machine-readable matrix](core-007-regression-01/verification.json), SHA-256
`0472c674dadbb7819d7879db701ada8093eec5442ba14754384d84a1b6d2459f`.
Summed test-context time is 742.399 s; this is not simulation performance.

## Acceptance scheduling correction

The first [registered session](../runs/core-007-2026-09-10/acceptance-01/registration.json)
used one CPU and a 2400 s wall / 512 MiB artifact cap. The first complete eager
case required **333.369 s for 1000 steps**, versus 0.0102 s compiled execution
plus 2.240 s compilation/cache preparation. This single workload timing explains
verification cost; it is not a cross-hardware or biological performance benchmark.
Extrapolating to the 16214-step full panel would exceed the serial cap.

The driver was explicitly interrupted at 542.853 s after three complete scalar
outputs (two JIT, one eager), with 14,107,599 bytes retained, including the
[interruption record](../runs/core-007-2026-09-10/acceptance-01/failure.json).
No failed numerical verdict was overridden. The incomplete eager depolarized run
has no completed output and is not counted. The original driver source is retained
in that session's 204-file capsule.

Revision 2 changes **only acceptance scheduling**: coordinator CPU 4 and four
independent eager lanes on CPUs 0–3, each single-threaded, after the regression
suite finished. The per-session wall/artifact caps, all fourteen cases in both
modes, equations, selected 0.5 ms method, error limits and all acceptance checks
are unchanged. Three completed runs are independently re-audited before exact
copy/reuse, and their old manifests/registration are recorded. No scientific
reference solver or completed eager trajectory is rerun to hide an outcome.

Revision 2 completed all fourteen JIT cases and their independent saved-output
checks, fourteen exact fresh-process replays, the independently checked pulse
omission branch, scalar windows, both original/resumed cohort groups, and exact
old-model regressions. At that point the recorded evidence plus the remaining
eager outputs projected to approximately **521 MiB**, above 512 MiB. Much of this
is the deliberately demanding checkpoint-every-window fixture repeating complete
resolved schedules, not the live integration state.

Revision 2 was interrupted before exceeding its cap; all outputs and the
[interruption record](../runs/core-007-2026-09-10/acceptance-02/failure.json) remain.
It retained 479,163,663 bytes, fourteen complete JIT records, two complete eager
records, and fourteen complete resumed records. Incomplete eager workers were
stopped and reaped; their partial computations are not counted as complete paths.

Revision 3 retains the same CPU scheduling and 2400 s wall bound, and prospectively
allocates **1 GiB** for evidence before continuing. Only the verification driver
changes; production and the independent checker remain byte-identical. All sixteen
complete original-mode scalar records are re-audited for reuse. Cohort/restart and
old-model checks remain required. This is a resource-planning correction, not a
changed physical model, acceptance tolerance or source validator.

The third session passes all unchanged criteria. Reuse was limited to fourteen
complete JIT and two complete eager records, independently re-audited before exact
copying; all other required output was completed in this session. All three source
capsules have identical production/runtime, with only the scheduling driver changed.

## Closeout and next boundary

The [release audit](../runs/core-007-2026-09-10/release-audit.json) and
[workspace/test closeout](core-007-closeout.json) bind the accepted sources,
checkpoint inventory, independent audit, test receipts and resource checks.
The 291 archived 0.11.0 members and all three regression-context XML/log receipts
are rehashed. Against the [402-file pre-edit workspace baseline](core-007-workspace-baseline.json),
383 files are unchanged, 19 have intended implementation/documentation changes,
and none is missing. Frozen scientific references, pilot data and prior results
remain unchanged. Ruff checks and formatting pass for 199 Python files; dependency,
whitespace and the twelve edited Markdown documents' local-link/structure checks pass.

CORE-007 adds one stateful channel on one physical cell through reusable engine
interfaces; it does not add a channel catalog or populate multiple cells/channels
merely by increasing capacity. Ionic/capacitor accounting explicitly omits gating
charge and protein conformational energy. No biological, BETSE-parity, GPU, organ,
multirate or deferred E02 acceptance is implied.

Next specify and independently check a **data-defined physical ionic graph**:
single/disconnected-cell reductions, reciprocal two-cell exchange, then a
three-cell star with explicit per-edge transfer ownership. This should precede
production graph assembly and retain the same complete state, conservation,
restart and numeric-axis contracts. Organ type remains data; communication
between cells is distinct from parallel independent worlds.
