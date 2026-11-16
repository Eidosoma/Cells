# A looping run written by the engine's run-view writer (branch run-view-d154, d7a11d5b)

The interim planarian loop of FR-11: a development run with no verdict, an illustration, not
registered. Its writer is on the branch `run-view-d154`, not on main; it reaches main only after its
own landing and gates. Nothing of it is published. It is kept here as a development fixture for the
viewer's reader of a run view, until the engine's lead says it has landed.

- **What it is:** seven heredity cells on a hexagonal patch, an electrode in the centre cell
  (`cell_3`) driven by a charge-balanced square wave of period 2 s; four settling periods, then one
  observed period of 101 rows, from 8 s to 10 s, written through `window_io.write_windowed_run`
  (recording "observations") with its view and loop. Engine models: `resolved_pump_composite@1` over
  `resolved_pump_tissue@3`, and `electrode_current_injection@1`.
- **Its source, as its own view states it** (`run.source`): `{"revision":
  "d7a11d5b0e20f3133c081386e487fe21b8b8f893", "dirty": false, "from": "the execution snapshot's
  record (SNAPSHOT.json)"}`. The run was made from the execution snapshot `snapshot-d7a11d5b` of
  that revision. Nothing here is planted.
- **What its view states that the reader must take:** a recording subset of 17 fields (no elements,
  every observed row); the loop block (species planarian, cell `cell_3`, period 2 s, closing within
  2.76e-5 against a tolerance of 1e-4, seven running totals not measured, none identically zero);
  a builder's geometry (the cells' hexagons, prescribed); a junction voltage on data.
- **How it was obtained:** copied unchanged from the engine's lead's folder
  (`replay-20261116/planarian-d7a11d5b/` in the Cells workspace, 16 November 2026): `view.json`,
  `windows.jsonl`, `summary.json`, `resolved_config.json` and the five chunks the view names. The
  manifest and the two checkpoints are left out. It was not made by
  `tools/make_engine_view_fixture.sh`, and that script could not make it: it runs the writer from a
  `git archive` export, which is no execution snapshot, so the writer states no source and refuses
  a loop (a looping package must name its engine's source).
- **Checked before keeping:** no machine path, host name or user name in any text file, and none in
  the strings of the five chunks.

Do not edit by hand.
