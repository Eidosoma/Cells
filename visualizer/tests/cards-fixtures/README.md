# Fixtures for tools/build_cards.py's gathering

Made up for the tests in `tests/experiment_cards.test.mjs`: a record of a few lines, in the layouts the
real record uses. Nothing here is a result.

- `engine/<revision>/`: the engine's repository at a revision, one folder each (the tool's `--repo-folders`).
  A revision with a folder counts as one on main; `4444…` is a snapshot on main, `5555…` (no folder) is not.
- `evidence/`: saved run folders, each named by its folder name, with a verdict file in three layouts
  (criteria at the top, criteria under `verdict`, rows with a tally).
- `source.json`: four cards, one in each band, that read them.

The files that hold a clock time in the real record (a run's `judged.done`, `run.log`, and a PROGRESS.md
lead with its times) are written by the test into a copy of this folder, so that no file of the tree holds one.
