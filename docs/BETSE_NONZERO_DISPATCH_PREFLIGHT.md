# REF-003e1: actual nonzero event-dispatch preflight

2026-09-12, D080. This follows the checked [D079 held-input design](BETSE_HELD_INTERVENTION.md).
Implement and execute native preparation and direct event dispatch only; do not
enter a transport function, concentration update, time integrator or Cells run.

## Fixed scope

Four fresh seven-cell / 30-face SIM preparations at matched F/R constants and
25 µs nominal step over a declared 1 ms horizon: default-profile baseline,
enabled zero amplitude, static block, and suppression/recovery. Actual physical
state stays at its freshly prepared value throughout this preflight. Dispatch
times do not represent an integrated trajectory or equilibration.

Use the [new plan](../validation/betse/dispatch_preflight_plan.json) and
[mapping](../validation/betse/dispatch_preflight_context.py). They extend the
retained initialization inputs only with the explicit SIM clock, enabled default
profile and declared Na/K/Cl event settings. Keep the D072 pulse and its
N/(N−1) conversion of all three time parameters. Nonzero multiplier is −1;
no modulator, extra tissue, global event, active transport or geometry change.

For each condition, call the actual native `fire_events` at all **40** raw labels
from `linspace(0, T, N)`: **160 dispatches**, of which 80 have enabled targeted
events and 40 have nonzero amplitude. The corresponding elapsed input times
are `k * 25 µs`; the last raw label is 1 ms but its elapsed input time is
**0.975 ms**, not a newly evaluated endpoint pulse. This is the proposed
pilot's first hold grid, not all three refinement grids.

## Checks and preserved evidence

The [runner](../validation/betse/dispatch_preflight.py) uses the ordinary pinned
native YAML loader, seed, fresh SIM `init_core`, `init_dynamics`, storage reset
and initial voltage closure. The unchanged preparation fence refuses entry to
integration/transport. The existing read-only native event observer records the
real handler call and return; it is not a replacement handler or solver.

Before dispatch, persist core, dynamics and ready physical snapshots, then read
metadata. A metadata failure cannot erase already prepared state. Check:

- Actual Base profile, all 30 membrane / seven cell targets, all enabled ion
  target lists, default and actual base diffusion, zero extra profiles and the
  unchanged physical configuration.
- Actual scalar modifiers, dynamic modifier values at every raw label, function
  names, multipliers and all three resolved pulse-time settings. `None` must
  resolve to scalar/dynamic values of one, not an assumed implicit multiplier.
- Exact fresh-state/topology correspondence to qualified D074 no-event
  preparation and initial values to the corresponding retained REF-003d INIT.
  Neither retained state is loaded into the new native phase.

Persist **each completed dispatch** immediately in a separate exclusive JSON
file. Also retain the aggregate observer trace for full event-chain checks;
on error save completed records and any open-event snapshot. No existing
attempt, source capsule, state, log or failure is overwritten.

The [control-aware checker](../validation/betse/dispatch_preflight_check.py)
does not import BETSE or call its pulse. It compares actual effective and
scheduled diffusion against independently compiled declared inputs. Across
160 dispatches it checks **57,600 diffusion values** (two arrays, six species,
30 faces). Use the existing 2e-14 absolute error scaled by positive unsuppressed
diffusion, not relative error against the near-zero pulse residual. Exact
source-order `effective == scheduled + base` and nonnegative/baseline-bounded
diffusion remain separate gates. Static-blocked and immobile diffusion must
be exactly zero; the smooth suppressed mobile values remain positive.

Only `Dm_scheduled` and `Dm_cells` may change. Concentrations, voltage, charge,
current, stored fluxes, base diffusion, temperature, pressure and pump/GJ blocks
must preserve their initial values, shapes, dtypes and bytes. Geometry/topology
and resolved configuration remain unchanged. This checks native stored state;
it does not invent native transfer ledgers or qualify future Cells accounting.
Adjacent event snapshots must link exactly, including the final state.

Baseline/zero-amplitude dispatch records must agree exactly across separately
prepared phases. Baseline, zero-amplitude and pulse preparations must have
the same initial physical setup. Permanently blocked preparation uses the
retained blocked reference. No flux evaluation is allowed during any dispatch.
The observer's full-loop noninterference under a nonzero trajectory is still
a later gate, requiring observed/unobserved run partners.

## Tests, resources and execution boundary

Focused prelaunch tests use retained initial preparations with **fabricated**
event records. They test mapping, correspondence gates, rehashed corruptions,
target/modulator errors, physical-state changes, malformed/partial evidence,
provenance and timeout/nonzero-exit preservation. Synthetic passes are not
native event-dispatch results. Freeze passing tests, all adapter sources,
plan and preservation hashes before the native attempt.

All **75 focused tests pass in 8.48 s**, and all **352 Python files** pass
lint/format checks. The earlier 74-test pass is retained; before native
registration the prepared-state gate was moved ahead of dispatch and an
additional interrupted-dispatch persistence test was added. The
[prelaunch receipt](../reports/ref-003e1-dispatch-prelaunch.json) freezes the
final tests, 80-file adapter capsule inventory, criteria and resource estimate.

Prospective sizing uses D074's measured six preparations in 17.360 s and its
largest 29,538-byte state snapshot. Explicit dispatch/format/storage allowances
estimate **33 worker seconds and 46,197,248 bytes**. The registered caps are
**45 seconds for the worker, 60 seconds for the attempt, 64 MiB overall and
16 MiB per worker-written file**, CPUs 0–3, single-thread numeric libraries.
The panel budget is checked between rows and at completion; the file cap is
OS-enforced. These are not a peak-RAM measurement or trajectory-run budget.

This short preparation preflight may be collected once while doing other local
work. There is no polling loop or automatic response launch. Any later long
capture/audit follows the [detached/user-polled policy](../AGENTS.md).

After passing prelaunch, register once into a fresh output directory:

```bash
.venv/bin/python -B validation/betse/dispatch_preflight.py preflight runs/ref-003e1-dispatch-2026-09-12/preflight-01
```

The result is separate from software prelaunch. Preserve failures without
automatic retry. Passing preparation qualifies only this prescribed event
dispatch at the initial physical state, not a nonzero response, the 8+24
trajectory pilot, native/forcing refinement, biology, restart, GPU execution,
organs or stable promotion. The [result report](../reports/REF003E1_DISPATCH_PREFLIGHT.md)
records the actual outcome and the next boundary.
