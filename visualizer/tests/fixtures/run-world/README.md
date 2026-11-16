# Synthetic runs of one small world

Written by `tools/make_run_fixture.py` for the viewer's tests. Every number is invented: no engine ran,
and nothing here is evidence. Do not edit by hand; change the tool and run it again.

- One cell, a finite space outside it (`ecs_0`) and a held bath; a membrane from the cell to each; a face
  from the space to the bath; a species S that is made in the cell, carried across the contact membrane
  by two exchange routes, and cleared in the space.
- 5 observation times, one second apart, in `trajectory.npz`, with a manifest that names each
  readout's owner as the engine's does.
- `secreting`: the amounts add up. `unbalanced`: the cell's amount of S does not follow.
- `viewed` and `retiring`: the same numbers with a `view.json` beside them, in the shape of the engine's
  run-view writer (two time bases, signs by role, a padding slot); in `retiring` the cell is retired at
  2.5 s and its membranes' heat ledger restarts there.
