# A run with invented numbers

Written by `tools/make_run_fixture.py`. Every number is invented by the formulas in that tool: no engine
ran, and nothing here is evidence. Do not edit by hand; change the tool and run it again.

`invented-numbers/` is laid out as the engine's shared output path lays out a run, and names its readouts as the
engine does. Its `example.json` says that its numbers are invented; the adapter carries that into the run's
view, and the page then shows it as a test sheet of invented numbers, never among the experiments, with
"Invented numbers · no run of Cells' engine" on the picture and in the legend (`schema/QUANTITY_LAYERS.md`, rule 6).

- 19 cells with one membrane, one pump, two channel populations and one held bath each; 42 junctions; 4 species.
- 25 observation times, half a second apart.
- Totals carried (channel populations, pump cycles, the membranes' own passive routes, junctions) and energy
  dissipated at each, each ledger apart as the engine keeps them.
