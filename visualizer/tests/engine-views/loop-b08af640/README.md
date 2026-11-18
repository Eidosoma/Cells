# The looping run again, written by the run-view writer at b08af640 (branch run-view-d154)

The interim planarian loop of FR-11, re-run by the engine's lead after the writer adopted the
engine's own view declarations: a development run with no verdict, an illustration, not registered.
It was written at b08af640, a revision of the development branch `run-view-d154` that main holds
through its merge: its writer is on main since 050aa741 (16 November 2026), and main's writer is the
same file as b08af640's. The run is still what it was, a development run with no verdict. It is the
run the page carries, packaged as the experiment `planarian-loop` (`data/replays`). Kept beside
`loop-d7a11d5b/`, the same package written by the writer at d7a11d5b.

- **What it is:** the same world, drive and period as `loop-d7a11d5b/` (see its note): seven
  heredity cells, a square-wave current into the centre cell `cell_3`, period 2 s, 101 observed rows
  from 8 s to 10 s.
- **Its source, as its own view states it** (`run.source`): `{"revision":
  "b08af640c3db83e891e29ade36c300d6f8e5a553", "dirty": false, "from": "the execution snapshot's
  record (SNAPSHOT.json)"}`. The run was made from the execution snapshot `snapshot-b08af640` of that
  revision (6303 files, a clean status). Nothing here is planted.
- **What differs from `loop-d7a11d5b/`:** only the view. Its five chunks, `windows.jsonl`,
  `summary.json` and `resolved_config.json` are byte for byte the same as that run's. In the view,
  ten records' orientations are now @3's own declarations: the voltages' differences are
  `confirmed` by the core's owner from the code, no longer `source`; the totals' signs carry the new
  word; four flux rates gain signs. There is one more constant, `amount_reference`, the fixed
  reference of `amount_increment`. `run.source` names b08af640. The loop block, its closure, its
  `not_measured` and its `zero` are unchanged.
- **How it was obtained:** copied unchanged from the engine's lead's folder
  (`replay-20261116/planarian-b08af640/` in the Cells workspace, 16 November 2026): `view.json`,
  `windows.jsonl`, `summary.json`, `resolved_config.json` and the five chunks. The manifest and the
  two checkpoints are left out. `tools/make_engine_view_fixture.sh` could not make it: it runs the
  writer from a `git archive` export, which is no execution snapshot, so the writer states no source
  and refuses a loop.
- **Checked before keeping:** no machine path, host name or user name in any text file, and none in
  the strings of the five chunks.

Do not edit by hand.
