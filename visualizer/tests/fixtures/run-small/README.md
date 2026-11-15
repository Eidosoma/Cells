# Synthetic run folder

Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. It has the layout of an
E07-v1 evidence folder, but every number is invented: no engine ran, and nothing here is
evidence. Do not edit by hand; change the tool and run it again.

- 19 cells on a hexagonal lattice, numbered in a scrambled order, and 42 junctions.
- 9 records: 7 on the 10 s grid and 2 at event times; one is marked not valid.
- 3 replacements of disc cells; one copy falls back to the resting voltage.
- `result.json` and `snapshot/SNAPSHOT.json` carry a made-up host name and machine paths, which
  the adapter must leave out.
