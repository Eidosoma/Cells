# Synthetic cue folder

Written by `tools/make_run_fixture.py` for `tests/adapt_run.test.mjs`. It has the layout of a W1
pilot evidence folder (`<study>/run`), but every number is invented: no engine ran, and nothing
here is evidence. Do not edit by hand; change the tool and run it again.

- Every cell has 2 membrane patches and a cue channel on each; the schedule switches it on
  from 3 s to 4 s in the disc's 7 cells only.
- `study-a` runs to its end: the disc is written within two records and stays written.
- `study-b` records a failure at the cue's first step, with a traceback that holds a machine
  path, and keeps its records up to the cue.
- `runs.jsonl` names the source snapshot each study ran from, by a path the adapter must not copy.
