# FR-47's schedule supplement, erratum 1 (24 November 2026)

**Status.** Registered by the lead (D350) before any judged run of fr47-shell-exchange exists, and tagged
`fr47-schedule-supplement-erratum-1-2026-11-24`. It corrects two checks of `FR47_SCHEDULE_SUPPLEMENT.md`. An external
code review found both, and the frozen scorer's code confirms them. The frozen scorer stays official and unchanged.

## 1. `d.stops` carries no kind (corrects check 1)

The references' (d) stops are `{time_s, removed, mixing_heat}` (SPEC.md §5; `fr47_judge.py`'s made-up reference), with
no `kind` key. Only `stops`, the exact side, carries `kind`. So check 1 reads:
- for `stops`: count, order, time and kind against the schedule, as before;
- for `d.stops`: count, order and time against the schedule. A stop's `mixing_heat` must be non-null exactly where
  the schedule says withdrawal, and null where it says replacement.

## 2. The heat intervals' ends come from the records (corrects check 4)

`d_intervals(run, stop_times, horizon)` builds its edges from the stop times it is given. Given the schedule's own
times, check 4 would confirm itself. So check 4 reads:
- **The run's intervals** are built from the run's own recorded stop times (`[t for t, *_ in d_stops(run)]`), never
  from the schedule. Every interval's heat must be finite: a NaN means a missing row at an edge, and fails.
- **Those edges,** `[0, *run stop times, horizon]`, must equal `[0, *scheduled stop times, horizon]`, exactly.
- **The references' intervals,** `[(start_s, end_s) for iv in d.intervals]`, must equal the same scheduled edges,
  pair by pair. `judge_d` does not read them.

Everything else in the supplement stands, including what a split result means.
