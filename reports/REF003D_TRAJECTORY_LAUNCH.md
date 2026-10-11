# REF-003d: short native trajectory engineering and launch

2026-09-12, D069. **Adapter preflights pass; numerical capture launched detached,
result not yet reviewed.** This report records engineering and launch, not a numerical
result review or the later independent actual-packet closeout.

## What is built

The [observer](../validation/betse/native_observer.py) copies native FULL-loop
initial, concentration-update, voltage-update and storage boundaries using a
scoped Python profiling hook. No native method is replaced; existing profilers
are refused and the hook is cleared on exit. The [driver](../validation/betse/trajectory.py)
executes real BETSE seed/INIT and the unchanged Cells checked RK4 runner in
separate environments. The [saved-array checker](../validation/betse/trajectory_check.py)
uses independent arithmetic without importing either simulator, NumPy or JAX.

The mapping reuses the [independently closed REF-003c fixture](REF003C_CLOSEOUT.md):
seven cells, 30 native membrane faces and one effective 6.75 pL finite bath.
Passive Na/K/Cl transport is active in the baseline; the matched control blocks
all membrane transport from the same neutral preparation. Auxiliary ions are
immobile. Active channels, pumps, junction exchange, regulation, mechanics and
dynamic extracellular fields remain disabled. INIT here is a physical transient,
not proof of equilibration or a resting cell.

The original one-cell rejection and failed one-centre geometry probe remain
unchanged. This is explicitly a seven-cell comparison, not a relabelled one-cell
success or a change to the production model.

## Frozen-before-execution panel

The [protocol](../validation/betse/trajectory_protocol.json) and
[design](../docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md) specify:

| Dimension | Prospective setting |
| --- | --- |
| Conditions | Passive baseline and all-blocked control, 1 ms each |
| Native steps | 0.1, 0.05, 0.025 ms; 10, 20, 40 actual updates |
| Native constants | Rounded source constants and explicitly matched constants, reported separately |
| Native runs | 12 observed combinations, each with a fresh unobserved partner |
| Cells runs | Eight actual checked-RK4 runs: two conditions × two steps × eager/JIT JAX CPU float64 |
| Common times | Eleven state samples from 0 to 1 ms, every 0.1 ms |
| Rate samples | Native beginning-of-step rates at 0 through 0.9 ms; no invented final rate |
| Resources | CPUs 0–3, single-threaded numerical libraries, 90 s per worker, 180 s panel, 64 MiB artifacts |

D068 proposed three full backends. Code inspection establishes only two actual
production runner paths: eager and compiled JAX. NumPy supplies ordinary readouts
and independent arithmetic, not a third full integrator. D069 amends that proposal
before numerical execution; it adds no substitute solver or production exception.

Raw native labels differ from physical update time. The observer retains the
unsampled first update; each step has its raw label, index, derived before/after
elapsed times, raw per-ion fluxes and pre/post state. The native voltage nonce is
preserved. Post-update stored current is checked against its preceding step's
flux, not falsely treated as a new instantaneous rate. All nine declared ordinary
array fields and ten final fields must match dtype, shape and bytes between
observed and unobserved partners. This is a scoped exported-output check, not a
claim about every internal variable or BETSE mode.

Instantaneous limits are unchanged from REF-003c. Cumulative amount accounting has
a predeclared 1e-10 fmol absolute allowance. Trajectory absolute limits are 5e-6 V,
1e-7 fmol for amount increments/transfers, 1e-5 fmol/s and 1e-15 A, with relative
tolerance 1e-5. Independent charge/material checks and exact blocked/inactive
routes remain mandatory. Native finest-step differences must pass and contract
by at least the declared 0.75 factor above the instantaneous roundoff floor.
Cells refinement and eager/JIT comparisons use tighter instantaneous criteria.
Cross-program comparisons use finest matched-constant runs and amount increments,
not large absolute inventories. These are numerical budgets, not biological
measurement uncertainties or an already measured fit.

## Preflight evidence and preservation

- [Initial preflight](ref-003d-preflight-01.xml): 44 passed, 1.68 s.
- [Expanded preflight](ref-003d-preflight-02.xml): 52 passed, 3.20 s.
- [First combined adapter suite](ref-003d-checks-01.xml): 223 passed, 21.84 s.
- [Second combined adapter suite](ref-003d-checks-02.xml): 227 passed, 22.014 s.
- [Final combined adapter suite](ref-003d-checks-03.xml): **228 passed, 24.234 s**;
  57 new tests plus the earlier 171, no failures, errors or skips.

Tests cover observer lifecycle/isolation/exceptions, first-update and clock
semantics, independent synthetic accounting, saved precision/byte/field coverage,
native YAML overrides, all eight production definitions, static production
readouts and rehashed corruptions. A registration-only test verifies source
capture without launching model workers. A mocked-launch test also verifies
detachment, durable logs and CPU affinity for the coordinator and its descendants.
Synthetic native records are test
fixtures, not external evidence. No full BETSE or Cells trajectory runs in these
new preflights.

The [pre-edit preservation](ref-003d-preservation.json) anchors 819 existing files,
the prior closeout and all 352 accepted implementation files. The
[prelaunch check](ref-003d-prelaunch.json) confirms 812 unchanged existing files,
exactly seven intended documentation edits and no missing files. Lint and format
checks pass for all 308 Python files. All 51 production
modules and historical captured adapters remain unchanged. The earlier
4190-test production matrix is preserved, not rerun. Stable 0.14.0 and accepted
development 0.15.0.dev0 are not promoted. The reference dependency environments
and unrelated ongoing research are not edited.

## Detached handoff

Launched at **17:00:05 UTC**, PID **1881932**, into the exclusive target
`runs/ref-003d-2026-09-12/trajectory-01`.
The [start receipt](../runs/ref-003d-2026-09-12/trajectory-01/launch.json) records
`launched_detached`; registration SHA-256 is
`9f41747f0f59eda41782368adfcf58b734f89ee7c51e2729c9ca9425a754927c`.
The launcher wrote registration and the 29-member `sources.zip` before starting
the detached coordinator and returned immediately. The start receipt is not a
numerical pass. Captured adapter/protocol files are now frozen. No capture status
or result was polled for this handoff.

The folder retains native configuration/seed/phase artifacts, raw exports and
observations, complete Cells histories/readouts and worker logs. A completed
passing capture writes `comparison.json` and `verification.json`; an error writes
`failure.json` with retained partial evidence. No numerical warning, missing
coverage, budget stop or failed criterion is converted into acceptance. No
automatic retry or post-result tolerance change is authorized.

Under the [no-poll policy](../AGENTS.md), return control immediately after launch.
On the user's next request, inspect the retained result. If complete, the next
separate gate is a source-bound actual-packet audit, rehashed-corruption tests
and short closeout, not another simulation by default. A capture pass alone is
not that independent closeout, biological validation, broad BETSE parity or GPU
qualification. Longer relaxation and active physiological cases remain later work.
