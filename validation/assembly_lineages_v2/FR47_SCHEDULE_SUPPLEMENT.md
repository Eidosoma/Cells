# FR-47: the schedule supplement (24 November 2026)

**Status.** Registered by the lead (D339) before any judged run of fr47-shell-exchange exists, and tagged
`fr47-schedule-supplement-2026-11-24`. It is structural and quotes no value. The frozen scorer,
`fr47_judge.py` at `fr47-shell-exchange-registered-2026-11-24`, stays the official verdict, unchanged. This
supplement is a separate result, recorded beside that verdict and never merged into it.

## Why

A reviewer showed, on invented records, that the frozen scorer does not verify the washes against the registered
schedule. Reading the scorer confirms each case.

| Case | Scorer | Why it passes |
| --- | --- | --- |
| A (d) withdrawal relabelled as a replacement, with its heat entry removed | `judge_d` | The stop's kind comes from the run, so the heat is never asked for. |
| Both washes moved 10 s later | `judge_d` | Stop times and the heat intervals' ends are never compared. |
| An extra trailing wash in every exact replica | `judge_exact` | It indexes each replica's stops by the references' count, and ignores time, kind and any extra stop. |

## The checks

Every comparison is exact. There is no tolerance unless the checker derives one, as item 2 says.

1. **The schedule.** For each registered world, the expected washes come from the world definitions at the
   registration tag (`fr47_worlds.py`): an ordered list of (time, kind), with kind one of withdrawal or
   replacement. The references' stops, both `stops` and `d.stops`, must equal that list in count, order, time
   and kind.
2. **Every saved run.** Each exact replica's stops and each (d) run's stops, as the frozen scorer extracts them
   (`exact_stops`, `d_stops`), must equal the schedule's list in count, order, time and kind.
   - The engine records a wash at its declared time. If a recorded time differs from the declared time by
     rounding, the checker derives the bound from the engine's clock arithmetic and states it in writing before
     reading any saved run. Any other difference fails.
3. **Heat where the schedule says withdrawal.** At every stop the schedule calls a withdrawal, each saved run must
   carry a finite mixing heat. A missing or non-finite heat fails, whatever kind the run itself records.
4. **The heat intervals' ends.** Each (d) run's heat intervals must start and end exactly at the schedule's
   boundaries, in order: the start, each wash time, and the horizon.
5. **Controls, run before any saved run is read:**
   - the three cases above, as invented records, each fail the supplement;
   - an honest invented record passes it.

## What a result means

- **Both pass:** FR-47's development-only status can be lifted.
- **The frozen verdict passes and the supplement fails:** FR-47 stays development-only. This tightens D323, which
  named the verdict alone. The frozen verdict is still recorded exactly as computed.
- **The frozen verdict fails:** the supplement is still run and reported.

## Who

FR-47's independent checker implements these checks in its own driver, from this note and the frozen scorer's
extractors only, before any judged run. It reports the result separately from the official verdict.
