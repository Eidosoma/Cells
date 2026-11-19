# Runs written by the engine's run-view writer (89bd2ffb)

Written by `tools/make_engine_view_fixture.sh 89bd2ffb` at revision `89bd2ffba7a0732a1dc20a6c2e61f86786c9b535`, that is main at `89bd2ffb`: the writer is on main since 050aa741 (16 November 2026).
Exported with `git archive` (src, tests, validation) and run with the engine's own Python as a
memory-capped unit (`scripts/run_detached.sh`). Every
file here is the writer's own output, kept as written: `view.json` (`cells.run_view@1`), the
arrays it names, `resolved_config.json` and `summary.json` (the manifest and the final checkpoint
are left out). Do not edit by hand; run the script again.

- `secretion`: the worked example's short world (one cell makes S and secretes it into a finite
  node that leaks to a held bath; 10 steps, 6 observed rows) through `io.write_run`. No declaration
  is planted.
- `subset`: the same world through `io.write_run` with a recording subset, as the engine's own
  test records one: four fields, of the species only S, every second observed row. Nothing is
  planted.
- `increments` (where written): the same world with a recording subset that keeps the two
  increments in place of the amounts, of the species only S. Nothing is planted.
- `kinds` (where written): FR-4's development world without its transporter, as the engine's own
  test of the inner model's kinds builds it, run for 10 steps: @3 alone with its passive routes
  and its proton buffer. Nothing is planted. The writer reads the kinds' declarations only from
  b08af640 on; written.json in the export says why where it was skipped.
- `division`: S5's compact partition world (a cell divides into two daughters) through
  `window_io.write_windowed_run` with two windows. The membrane state's and the partition's
  run-view declarations are planted for the run only, as the engine's own test does
  (`declare_division`): the layer "division" and its label are the test's words, not the
  operators' files'.
- `factors` (where written): heredity cell D, as the engine's own test of the routing door into @3
  builds it: its first channel population declares two factors of the test's **planted** factor
  source (`tests.factor@1`, registered for the run only). Observed at each of its 4 steps, with a
  recording subset of five fields. It shows the membrane's Na/K pump (`per_cycle`), the channel
  set's `factors` and the note on `channel_availability`.
- `condition` (where written): FR-5's development world, arm R, as the engine's own test of the pH
  condition's set builds it, run for 10 steps (its damage schedule's points after that end left out,
  as `fr5_world` does for a shortened horizon), with a recording subset of five fields. It shows
  the pH condition's kind as a word and its law under `laws`. Nothing is planted.
- `dose` (where written): the bath schedule's dose world (8 steps, a dose of cargo S at 4 ms),
  written through `io.write_run` without a view and given its view afterwards by
  `run_view.write_view`, as a run already on disk: a record stored over a field the run did not
  save (`{"field": X}`) with X's `unstated` entry. The bath schedule's layer is **planted** for the
  run only, as the engine's own test does: the layer "bath" and its label are the test's words.

Its writer holds the core seams pass's three format items (docs/CORE_SEAMS_DESIGN.md §9, on main from `d64fb664`, 18 November 2026): kinds are words with a law's ID under `laws`; each species a route carries moves with its own flux, coupled stoichiometry being `per_cycle`; a reference constant only where a record names it, and a `{"field": X}` reference only with X's `unstated` entry. And where a channel population declares factors, the channel set gives each population's `factors`.

**The engine's source is not stated.** An export has no execution snapshot's record
(`SNAPSHOT.json`), from which alone the writer learns its source, so no view here has
`run.source`: each lists the engine source as unstated, with the writer's reason. The
`run.revision` of the secretion view, `89bd2ffb`, is a caller's label **planted** by the script;
it is not the engine's own word for its source, and nothing may read it as that. The other views
name no revision. The division run's helper (`declare_division`) also patches
the writer's source lookup to give none, as the engine's tests do; from an export the lookup gives
none anyway, as the unpatched runs show. The exported code is that of `89bd2ffba7a0732a1dc20a6c2e61f86786c9b535`.

These are development runs of unit-test worlds: no result and no evidence.
