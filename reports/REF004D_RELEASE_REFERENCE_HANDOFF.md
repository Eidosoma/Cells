# REF-004d: independent piecewise reference handoff

2026-09-15, D104. The user authorized the next step after the successful D103
input review. Production remains stable 0.14.0 / accepted development
0.15.0.dev0, with no implementation changes. The
[input closeout](REF004D_RELEASE_INPUT_CLOSEOUT.md) records 916,176 passing saved
comparisons in 24.469 s; the original D102 failed capture remains untouched.

## Software verification

The new [reference contract](../docs/BETSE_CHANNEL_RELEASE_REFERENCE.md) is
implemented in `validation/betse/channel_release_reference/`. All **102 focused
tests pass in 4.35 s**. The earlier **79-pass / 4.53 s** result is retained.
No failed software test attempt or new simulator run occurred in this stage.

| Receipt | Result | SHA-256 |
| --- | --- | --- |
| `ref-004d-release-reference-checks-01.xml` | 79 passed | `475d95cadc060bf03f1c201c3d66674acc1b2eef475c99fab2fccda52591e2f8` |
| `ref-004d-release-reference-checks-02.xml` | 102 passed | `90dbe3fd720a1816281ac623785453a20ffdcc9f8cebc53f501bcc66a73aebbe` |

Tests use all three real solver settings on deliberately tiny **one-cell, 2 µs**
fixtures. Those paths pass readout/convergence/analytic checks and intentionally
fail the registered response-resolution gate. Separate seven-cell instantaneous
checks cover full state axes, availability scaling and unchanged gate rates.
Corruptions cover carry, gates, bath amounts, switch side, dense coefficients,
clocks, resource counts and one-ULP boundary samples. Other checks cover domains,
every signal requirement, reference-only import guards, source authentication,
exclusive outputs, detached no-poll launch, durable failures/timeouts, and a
controller that stops after the reference even on success. These tests do not
constitute the real seven-cell / 2 ms reference result.

The controller and checker use only the standard library and previously audited
algebra. The reference worker uses pinned NumPy/SciPy, not either simulator.
RHS arithmetic is 80-digit Decimal; ODE integration and saved states are float64.
Repository lint, formatting (686 Python files) and whitespace checks pass.
Final model-free authentication confirms 182 new-capsule inputs, 19 bound reports,
the ten-file prerequisite packet, 102 software tests, and all **352 accepted
implementation files / 51 production modules** unchanged. No full production
regression was rerun.

## Frozen prospective execution

Two histories × baseline/no-op/static-blocked/suppression-release × three solver
settings = **24 paths / 48 segment integrations**. The 2 ms candidate and
0.5/1 ms switches were fixed before this run. Baseline is unsplit; no-op is split.
Carry all 28 coordinates exactly at input boundaries and save one-sided rates.
Positive intrinsic permeability and evolving gates remain distinct from input
availability. Reference tolerances and solver settings are inherited unchanged;
resolution thresholds are four times prior simulator budgets, plus two-readout
reference uncertainty. Signed history diagnostics do not select a positive
biological memory effect.

The registration binds the 182-input source capsule, 19 historical reports,
the final software receipt, the pinned reference runtime, D103's ten-file packet
and the unchanged earlier source/capture chain. Mutable progress indexes are
outside the frozen evidence capsule. Never modify registered code or artifacts
after launch.

One fresh detached job: CPUs 0–3, **900 s total / 480 s worker / 128 MiB per file /
256 MiB aggregate artifacts**. No explicit small RAM restriction is added.
Save every accepted reference path and all rejections; a failure retains partial
evidence. No retry, polling, simulator execution, automatic audit, regression or
GPU work follows. The job's actual launch/completion/failure receipts—not this
handoff—establish execution status. A pass is
`piecewise_reference_pass_pending_review`, not a qualified simulator response.

Next, on user instruction: inspect saved reference evidence, then plan/qualify
full-loop timed native dispatch and a corresponding Cells comparison. Do not
infer that two-single-update preflight already validates that timed full loop.
