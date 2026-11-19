# Made-up plants on the engine's views (not the engine's output)

**Made up.** `plants.json` is the viewer's own, written by hand for its tests on 19 November 2026.
No engine writer wrote any of it, and nothing here is a run's output or evidence.

Each plant names a world of `tests/engine-views/run-view-89bd2ffb/` (views written by main's
run-view writer at 89bd2ffb). A test copies that world, changes its `view.json` as the plant says
(`sets`: keys of a set replaced; `add_sets`: sets added), and packages the copy; the arrays are the
writer's own. They hold what no small world of the engine shows at that revision:

- **A route that carries more than one species.** Each passive route and each exchange route
  carries one species at 89bd2ffb. A list of several means, in the engine's words, that each
  species moves with its own flux, not as a coupled set (docs/RUN_VIEW_DESIGN.md §9).
- **A cycle kind's coupled stoichiometry on a set of its own** (`per_cycle`, by mode and
  population). No cycle kind gives a set at 89bd2ffb; the shape planted here is the viewer's
  guess from the engine's one sentence on it, and the adapter reads none of its inside: it names
  the key and leaves it out. Its shape is a question for the engine's lead.

`tests/adapt_run_formats.test.mjs` applies them.
