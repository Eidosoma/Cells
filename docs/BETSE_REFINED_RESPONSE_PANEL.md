# REF-003e1: two finer held-response panels

2026-09-13, D084. Prospective capture contract, not response qualification.
The [handoff](../reports/REF003E1_REFINED_RESPONSE_HANDOFF.md) records software
checks; actual launch and completion/failure receipts belong to a separate run.

## Prerequisites and fixed scope

D083's [actual dispatch result](../runs/ref-003e1-refined-dispatch-2026-09-13/preflight-01/completion.json)
passes eight fresh preparations / 960 dispatches in 116.002 s, with 345,600
diffusion checks and maximum baseline-scaled error 2.671e-15 under the unchanged
2e-14 bound. It performed no transport or integration. Authenticate all 1042
files, its 98-input capsule and its runtime before starting response work.
This is a reviewed input-application gate, not an independent response audit.

Retain D081's original 25 µs capture and D082's independent rejection audit:
150 shared-bath Na/K failures remain failures. Replay the frozen original
checker exactly, including its documented mutable-list reporting defect, then
use separate value-snapshot summaries for new reporting. Do not overwrite
the old source, packet, criteria, handoff or regression evidence.

Use the same neutral seven-cell finite bath, matched constants, 1 ms duration
and four conditions: baseline, zero amplitude, static block, suppression/recovery.
The [plan](../validation/betse/response_panel/refined_response_plan.json) fixes:

| Input hold | Native observed / unobserved | Cells eager / JIT | State/ledger boundaries |
| --- | --- | --- | --- |
| 25 µs | Reuse 4 / 4 from D081 | Reuse 12 / 12 from D081 | 41 |
| 12.5 µs | New 4 / 4 | New 12 / 12 | 81 |
| 6.25 µs | New 4 / 4 | New 12 / 12 | 161 |

New work is **16 native + 48 Cells runs**, 960 observed native steps and
13,440 accepted Cells steps (6720 per backend). At each hold, Cells uses
subdivisions 1/2/4 with the exact same prescribed control table. Reused runs
are identified separately and are neither copied nor counted as new evidence.

Native phases are freshly seeded/prepared, not loaded from retained states.
Reuse D083's clock-only YAML mapping and fresh preparation, D081's unchanged
full-loop observer, and the existing Cells definition compiler/exporter/runner.
New static adapter derivatives generalize the old 40-step checks to N steps;
old code is not patched or dynamically rewritten. Production remains unchanged.

## What constitutes a gate

| Comparison | Required for this capture's candidate verdict? | Interpretation |
| --- | --- | --- |
| Internal laws, inventories, charge, controls, pair and zero checks at all holds | Yes | Physical/accounting and capture integrity |
| Cells 1→2 and 2→4 subdivisions at each fixed hold | Yes, original instantaneous limits | Solver sensitivity under unchanged input |
| Eager/JIT agreement for each subdivision and hold | Yes, original instantaneous limits | CPU backend correspondence |
| Native versus finest Cells at 6.25 µs | Yes, original trajectory limits | Bounded finest-held-input correspondence, pending audit |
| Native versus finest Cells at 25 and 12.5 µs | Diagnostic, failures retained as rejections | Show coarse/intermediate disagreement without relaxed limits |
| Changes across successive holds on 41 common boundaries | Diagnostic, same trajectory limits | Native joint integration/resampling or finely integrated Cells input sensitivity |

There are 36 full-grid scopes per hold and 24 across-hold diagnostic scopes.
Each full-grid scope has 101N+52 comparisons (52 state/ledger scalars at N+1
boundaries, 28 fresh-rate scalars at N starts and 21 interval transfers at N
intervals). The complete report has 1,373,032 internal checks and 1,121,904
surface/diagnostic checks: **2,494,936 total**, including **2,298,936 required**.
Reports include every failure count, per-scope counts and up to 100 detailed
examples per scope, as well as a separate required-gates summary. Raw records
retain the evidence needed for a later complete failure ledger.
A failed required gate stops the capture without retry. A passing candidate may
still contain coarse/intermediate/diagnostic rejections; its status explicitly
says so. It is never reported as an all-green comparison.

At each hold, inspect all N+1 registered state/ledger boundaries and all N fresh
native RHS values at interval starts. Check Cells' terminal fresh RHS against
the retained last input; exclude it from cross-engine rates because the native
loop supplies no fresh terminal RHS. Check cumulative transfers and N interval
differences separately. Across holds use exact common 25 µs boundaries, without
interpolation; interval differences then span the common 25 µs windows.

The prescribed native raw clock uses N/(N−1) scaling. The final held sample is
at elapsed T−h, not a newly evaluated pulse at T. Native pulse refinement changes
both integration step and forcing samples. A passing finest comparison does
not establish forcing or native convergence. Both qualification flags, overall
trajectory qualification, biological validation and GPU validation stay false;
a separately requested audit must assess the actual evidence.

## Resources and handoff

D081 measured 19.821 s native, 687.130 s Cells and 6.774 s comparison.
Use its slowest accepted-step cost separately for eager (0.893958 s) and JIT
(0.086577 s), not an optimistic average extrapolation. The prospective estimate
with explicit allowances is 239 / 10,004 / 125 s for native / Cells / comparison,
520,964,299 bytes of artifacts and a 34,058,544-byte largest worker file.
These are conservative estimates, not measured D084 runtime or peak RAM.

Bind stage limits of 300 / 10,800 / 300 s, total 11,700 s (3 h 15 min), CPUs 0–3,
single-thread numeric libraries, CPU float64, 1 GiB aggregate artifacts and an
OS-enforced 64 MiB worker-file cap. Aggregate checks occur between rows/stages;
they are not a filesystem quota. Native, Cells and arithmetic run in separate
source-bound worker processes with durable logs, started-row receipts and
partial/failure artifacts. Runtime errors and Python warnings reject the run.

Only the new capture may be launched after prelaunch review. Return control immediately; no
assistant polling, automatic retry, refinement expansion or follow-up audit.
User status requests inspect the durable results. Audit/regression execution
and its resource budget require a later instruction and separate registration.

Current implementation gate: the first software attempt reports 96 passes /
four failures in 60.79 s. Corrected checker/count/fence-test issues pass all
24 targeted checks in 31.84 s; all 375 Python files pass lint/format checks.
The complete 114-test software suite runs separately, detached, with a
180-second pytest worker / 300-second total cap, CPUs 0–3, 16 MiB artifacts
and 8 MiB worker files. Its conservative allowance accommodates the measured
60.79-second first suite plus the new corruption/launcher tests and source
authentication. This job saves logs, JUnit, source capsule and completion/failure;
it cannot freeze response prelaunch or launch a trajectory. Review its actual
completion on user instruction first. This software preflight is distinct from
the later independent scientific audit/regression.

Preserve the 990-file baseline, all 150 original response / 16 audit / 1042
dispatch files, and 352 accepted implementation files / 51 production modules.
Only seven existing status documents change. Seven new Python modules plus one
plan in a nested directory extend the capsule to 106 inputs without enlarging
the frozen flat 88-source inventory. Keep the user's exact recorded ignore-rule
amendment and now-ignored JUnit evidence. Do not reinterpret the legacy
121-pass / one-metadata-guard-failure result as a passing suite.

## Multiscale design consequence

Input sampling, solver steps, observation sides and conserved interface
transfers remain separate contracts. This is directly relevant when a tissue
region or organ communicates less frequently than its local solver updates.
Keep source-specific native clock conversions in this optional adapter; Cells
continues to use numeric control arrays and pure JAX kernels, with no BETSE
dependency or native callback inside a compiled step. This preserves the GPU
architecture without claiming GPU speed, memory scaling or feature parity.
