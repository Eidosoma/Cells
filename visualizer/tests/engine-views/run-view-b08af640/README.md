# Runs written by the engine's run-view writer (branch run-view-d154, b08af640)

Written by `tools/make_engine_view_fixture.sh b08af640` on the branch `run-view-d154` at revision
`b08af640c3db83e891e29ade36c300d6f8e5a553`, exported with `git archive` (src, tests, validation) and run with the engine's own
Python as a memory-capped unit (`scripts/run_detached.sh`). The writer is on a development
branch, not on main. Every
file here is the writer's own output, kept as written: `view.json` (`cells.run_view@1`), the
arrays it names, `resolved_config.json` and `summary.json` (the manifest and the final checkpoint
are left out). Do not edit by hand; run the script again.

- `secretion`: the worked example's short world (one cell makes S and secretes it into a finite
  node that leaks to a held bath; 10 steps, 6 observed rows) through `io.write_run`. No declaration
  is planted.
- `subset`: the same world through `io.write_run` with a recording subset, as the branch's own
  test records one: four fields, of the species only S, every second observed row. Nothing is
  planted.
- `increments` (where written): the same world with a recording subset that keeps the two
  increments in place of the amounts, of the species only S. Nothing is planted.
- `kinds` (where written): FR-4's development world without its transporter, as the branch's own
  test of the inner model's kinds builds it, run for 10 steps: @3 alone with its passive routes
  and its proton buffer. Nothing is planted. The writer reads the kinds' declarations only from
  b08af640 on; written.json in the export says why where it was skipped.
- `division`: S5's compact partition world (a cell divides into two daughters) through
  `window_io.write_windowed_run` with two windows. The membrane state's and the partition's
  run-view declarations are planted for the run only, as the branch's own test does
  (`declare_division`): the layer "division" and its label are the test's words, not the
  operators' files'.

**The engine's source is not stated.** An export has no execution snapshot's record
(`SNAPSHOT.json`), from which alone the writer learns its source, so no view here has
`run.source`: each lists the engine source as unstated, with the writer's reason. The
`run.revision` of the secretion view, `b08af640`, is a caller's label **planted** by the script;
it is not the engine's own word for its source, and nothing may read it as that. The other views
name no revision. The division run's helper (`declare_division`) also patches
the writer's source lookup to give none, as the branch's tests do; from an export the lookup gives
none anyway, as the unpatched runs show. The exported code is that of
`b08af640c3db83e891e29ade36c300d6f8e5a553`, the branch's tip when it was exported.

These are development runs of unit-test worlds: no result and no evidence.
