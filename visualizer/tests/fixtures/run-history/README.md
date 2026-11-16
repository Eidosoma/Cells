# Synthetic runs in the layout of the engine's shared output paths

Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. Every number is invented: no engine
ran, and nothing here is evidence. Do not edit by hand; change the tool and run it again.

- 19 cells with one membrane and one held bath each, 42 junctions, 19 channel populations, 4 species.
- 5 observation times. `whole/run` holds them in `trajectory.npz`; `windowed/run` in two window chunks.
- Arrays are made for 2 more places than the run uses, as the engine makes them for its capacity.
