# REF-003e1 control-design review

2026-09-12, D079. **Control design checked; no trajectory registered or run.**

## Qualified starting point

The user-polled D078 [joint completion](../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json)
passes **1,232,616 numerical comparisons and 433 focused tests in 167.679 s**,
maximum normalized error **0.185990**. The independent arithmetic took
68.069 s and regression 90.483 s; neither simulator was rerun. This qualifies
the 1 ms, seven-cell, both-F/R, three-timestep **zero-amplitude SIM bridge**.
Its completion SHA-256 is
`65a7b798bdbf81a1f1b380165154b5803580f119bbfbb29133f1a4003a063558`.

All 802 capture files, 11 expanded-audit files and 71 captured adapter sources
are authenticated alongside the previous evidence chain. The standalone
`audit.json` retains its historical pending-regression scope; only the separate
joint `completion.json` qualifies the expanded bridge.

## What changed

The [design](../docs/BETSE_HELD_INTERVENTION.md) extends D072, without editing
its frozen plan, source or evidence. The new
[data-defined plan](../validation/betse/held_intervention_plan.json) proposes
four conditions: baseline, enabled zero amplitude, permanent block and smooth
suppression/recovery. A first response pilot would have **eight native runs
and 24 Cells runs**, at matched constants and fixed 25 µs input hold over 1 ms.
This proposal is not a registered capture and has no simulation launcher.

The [compiler/probes](../validation/betse/held_intervention.py) add:

- Cells schedules derived only from declared inputs, with independent 70-digit
  pulse arithmetic and unchanged geometry/initial conditions/production physics.
- Actual pinned BETSE pulse evaluation plus source-order additive diffusion
  arithmetic: **12 condition/hold rows, 1120 sampled time points** across the
  conditions (280 pulse samples across the three hold grids before condition reuse).
  All mobile differences meet the existing **2e-14 baseline-scaled control
  tolerance**; permanently blocked and immobile diffusion are exactly zero.
  This is not actual event dispatch or target preparation.
- **36 actual Cells schedule/grid configurations**, covering all four conditions,
  three hold steps and three solver subdivisions. At each fixed hold, the
  production EventGrid has exactly N/2N/4N steps, without extra tiny intervals.
  These are not 36 globally unique numerical grids: conditions reuse grids.
- Left/right boundary controls, retained terminal hold, active membrane fields
  and disabled/padded control zeros. Fresh endpoint rates are explicitly
  distinguished from native stored preceding-update flux/current.
- Import fences against both simulator entry paths and the Cells RK4 module;
  no RHS/integration or native event-handler calls are performed by the probes.

The proposed physical comparison must independently check actual controls,
state/ledger continuity at dispatch, correct rate evaluation states, cell/bath
inventory and charge accounting, backend agreement and fixed-input solver
refinement. Subsequent finer hold steps assess sampling sensitivity separately;
the one-h pilot alone cannot qualify the full response/refinement gate.

## Checks and preservation

All **80 focused tests pass in 14.14 s**, with failures/errors/skipped all zero
in the [second JUnit receipt](ref-003e1-control-design-checks-02.xml).
All **348 Python files** pass lint/format checks; tracked diffs pass whitespace
checks. No older full adapter suite or production matrix was rerun.

The [first receipt](ref-003e1-control-design-checks-01.xml) retains **79 passes
and one failed source-mutation fixture** in 9.75 s. It searched for a single-line
addition while the native source splits that expression across lines. The
fixture's replacement target was corrected; the source checker, numerical
inputs, tolerance and actual control/grid probes were unchanged.

The [preservation baseline](ref-003e1-control-design-preservation.json) covers
**932 pre-existing files**, with only the seven existing status documents
allowed to change. All **352 accepted files / 51 production modules**, previous
adapter sources, native capture/audit files and earlier evidence stay unchanged.
The [machine-readable review](ref-003e1-control-design-review.json) binds final
plan/source/test/preservation hashes, quality results and complete control-probe
outputs. No output, failure or historical receipt is overwritten.

## Next boundary

First implement a bounded **actual nonzero SIM preparation/dispatch preflight**,
checking real target indices, tissue/base diffusion equality, additive effective
diffusion, modulator values and unchanged physical state. Then implement the
control-aware pilot capture/checker and prospectively register source/input/
observation/criteria/resource contracts. Preserve accepted no-op and constant-
permeability checkers unchanged. Long captures and follow-up audits run detached,
with durable artifacts and user-requested status checks; no automatic campaign.

This slice establishes input/scheduling correspondence only. Nonzero trajectory,
biological recovery, continuous forcing, longer horizons, restart, organ models,
GPU execution and stable release promotion remain unqualified. Stable stays
0.14.0; accepted development stays 0.15.0.dev0.
