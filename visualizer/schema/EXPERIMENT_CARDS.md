# The Experiments landing's cards

Status: **written for the viewer, 18 November 2026**, for the landing page of the Experiments tab. On
18 November 2026 the user decided that the tab gets a landing page of cards that shows everything Cells
has run, in bands, each card with its standing in the record's words; what the page has today is marked
as the examples to start with, and everything else is in. This note is the contract between the cards'
data (`data/replays/cards.json`) and the landing that draws them: the landing reads it, and no word of a
standing is written anywhere else.

A card says what an experiment asks, where it stands in the record, and, where the record has them, its
answer, its verdicts (how many of their checks passed, on which day, from which run), its scope line and
its runs. **Nothing on a card is typed from memory.** A card's title, what it asks, its band and kind,
and which map part, catalogue entry, verdict file and PROGRESS.md entry it reads are typed; everything
else is read, and each reading names the file and the field it came from.

## Files

| File | Made by | Holds |
| --- | --- | --- |
| `data/replays/cards.source.json` (`cells.visualizer.experiment_cards_source@1`) | Hand | The bands' typed words; each card's id, band, kind, title, `asks` (or `shows`), and its locators: `map` (a map part), `standing` (a catalogue outcome, a catalogue stop or a model-system entry, where the card reads no map part), `answer`, `record` (PROGRESS.md entries and verdict files), `switch`, `cite`, `rows`, `replay`; `none` (why a card has no level, where the map states none); `left_out` (each experiment part of the map that is on no card, with why) |
| `data/replays/cards.readings.json` (`cells.visualizer.experiment_cards_readings@1`) | `tools/build_cards.py --gather` (generated: do not edit) | What was read from the record, card by card, each reading with the locator it answers (`read`), its file and field; the revisions found on main (`on_main`); the sources whose place was not found word for word (`unplaced`) |
| `data/replays/cards.json` (`cells.visualizer.experiment_cards@1`) | `tools/build_cards.py` (generated: do not edit) | The cards, below |

```bash
python3 tools/build_cards.py                                   # the cards, from tracked files only
python3 tools/build_cards.py --check                           # fails if cards.json is stale (npm test runs it)
python3 tools/build_cards.py --gather --evidence DIR --repo DIR  # reads the record, then writes both files
python3 tools/build_cards.py --check --evidence DIR --repo DIR   # also fails if the readings are stale
python3 tools/build_cards.py --gather --evidence DIR --repo DIR --revision HEAD
                                                               # moves the record to that checkout's head first
```

`--evidence` is the folder of saved run folders, read only; `--repo` a checkout of the engine's
repository, read with git only (`show`, `cat-file`, `rev-parse`, `merge-base`). The record's revision
is the source file's `record.revision`, a revision of main named in full; `--revision` (with `--gather`)
moves it, writing the new revision there, the one line of that file the tool changes. The cards are built from
tracked files and the readings alone (`--check` in `npm test` reads nothing else). The gathering is run
again, with the record at hand, when any of these moves:
- **the record**: a new revision of main in the source file's `record.revision`;
- **a locator** in the source file (the build refuses readings that answer another one, and says so);
- **the map's revision**, the one the scene states: the cards then rebuild from tracked files, but the
  test "every source names its revision, each one the gathering found on main" fails until the
  gathering has confirmed the new one (`on_main`). So a merge of the map forward is followed by a
  gathering.
- **a new judged entry** in PROGRESS.md (with a new record revision): the test "every entry of
  PROGRESS.md's runs that reports a judged run or a registered qualification is on a card or left out
  with a reason" fails until the entry is placed in the source file, on a card's `record` or in
  `entries_left_out` with its reason.

A change of the map's words alone (same revision) needs only `python3 tools/build_cards.py`.

## Where each word comes from

- **A map part's standing** (`standing.from: "map"`): its `status`, `as_of`, `plain` (as `says`),
  `label` and `sources`, from `data/architecture/overlay.json` (a component by its id, an operator as
  `op.<key>`, as the scene names it). Its level's words are the map's `statuses`. Its sources carry the
  map's revision, the one the scene's `meta.source_base_url` ends in, unless a source names its own.
  The map and the landing cannot say two things: `tests/experiment_cards.test.mjs` holds each field
  equal to the part's.
- **A map part with no status** (the gap-junction work): `status` and `level` are null, `none` is the
  card's typed reason, and `first` is the first sentence of the map's words, "Development work, not
  judged (D138).", which the landing shows first, beside every picture of that work.
- **A level** is the map's, exactly as the map gives it, on every card that reads a map part: "Failed
  qualification" on the card that failed, "Implemented and guarded" where the map says so.
  `standing.tests` lists the tests the map's part names among its sources (none where it names none).
  (`level_withheld`, an optional field of the first round, is no longer written.)
- **A catalogue standing** (`from: "catalogue"`): the experiment's `outcome.status` (as `says`) and
  `outcome.text` (as `text`), with its sources; or, for a catalogue stop (`none`), the stop's label.
- **An entry's standing** (`from: "entry"`, the assembly): the model-system entry's `modelled.text`
  and `state` (`data/models/<id>.json`), its scoped words unchanged.
- **An answer** (`answer`): the catalogue's `outcome` of a judged experiment (`judged`, `answer`,
  `label`, `text`), kept apart from the standing so that two dates never show; its status string is
  not copied.
- **The record** (`record`, a list): each entry is a PROGRESS.md entry at the record's revision, found
  by the start of its bold lead: `says` is that lead, `item` the words of one bullet under it where the
  source names one, and `scope` the entry's scope line (a bullet such as "Scope:" with its list), each
  in the record's words with markdown left out. A clock time in a heading is left out of every string
  here (the date stays), and words that would carry a path of a machine are refused.
- **A verdict** (`record[].verdict`): read from the run's own file in the saved run folders, named by
  its folder (`run.evidence`) and its folders one by one (`run.within`), never by a path.
  - `count`: `passed` of `of`, in the record's own unit (`judged criteria`, `criteria`, `judged items`,
    `items`, `rows`, `cases`, `protocols`, `judged runs`, `judged quantities` …), with `from` (the file and
    the field it was counted from; `from.files`, optional, where one verdict is read from several files,
    `from.file` then naming the first). The readers, one for each layout of verdict file: `criteria`
    (the entries whose `judged` is true), `items` (a mapping, the judged ones where any says), `list` (a
    list of items), `named` (names each with a verdict), `rows` (with its tally), `tally` (the file's own
    passed, failed and not-evaluable numbers; `count.not_evaluable`, optional, holds the last), `one` (a
    single verdict), and several files of one verdict each. The gathering confirms the count against
    the run's `reading.json` or its registered protocol's entries where the source names one, and
    against any count the PROGRESS.md entry words in the same noun (`confirmed_by`).
    - Where the entry words a different count and nothing confirms the file's, `count` is null and
      `count_withheld` says why: the card says less.
    - Where the entry words a different count and the run's protocol confirms the file's (MG0a: 13
      judged entries, PROGRESS "All 12 criteria"), the count stands, `count.differs_from` (optional)
      keeps the entry's words with their place, and `count.note` (optional) says in the tool's own
      words which numbered criterion is judged in parts, from the entries' own names.
  - `also_on` (optional): where one judged run (one run folder) stands behind several cards, each of its
    verdicts names the other cards, so that each card says so once, with the run's folder (`run`).
  - `passed`: the verdict's own; a failed run that is kept stands as plainly as a pass.
  - `day`: the date of a timestamp inside a named file of the run (`judged.done`, a log's line), or a
    date written out there ("Run once, 11 November 2026"); never a file's time and never the protocol's
    registration day.
  - `snapshot`: the revision the run was made from, where it is on main; otherwise `revision` is null
    and `says` why.
  - `protocol`: the verdict's `protocol_id` (or its `protocol.id`), where it has one.
- **Runs** (`replay.runs`): counted from the catalogue's selection (`data/replays/selection.json`), from
  a run folder's own index where the selection reads one (as the adapter does), from the entry's
  `runs`, or from a tracked fixture folder (the test sheet); `runs_from` says which, part by part.
- **Every revision** a card names is in full and was found on main by the gathering (`on_main`).
- **Every judged entry of the record** is placed: the gathering lists, in `judged_entries`, each entry of
  PROGRESS.md's runs whose bold lead holds one of the words judged, judge, qualified, qualification,
  pass, passes, passed, fail, fails, failed, verdict or acceptance, whatever its outcome; each is on a
  card's `record` or in the source file's `entries_left_out`, with a reason.

## The format (`cells.visualizer.experiment_cards@1`)

Top level: `format`, `note`, `built_from` (`map.revision` and `as_of`; `record.revision`), `bands`,
`not_run`, `listing`, `cards`.

- **`bands`**, in this order, each `{id, label, says, cards}` (the card ids, in their order):
  1. `examples`, "Examples to start with": the tumour tissue and the assembly. "Example" names these two
     and nothing else.
  2. `judged`, "Judged under a registered protocol": everything the record has judged or put to a
     registered qualification, passed or failed, side by side. Its `says`: "Each card here was judged
     under a registered protocol, experiment or qualification. Passes and failures stand side by side,
     and each card shows its own level from the Engine map." `status` is null (no single level), and
     `levels` (optional) lists the map's levels its cards show, each `{id, label, says}` in the map's
     words: `qualified` ("Qualified or judged"), `failed` ("Failed qualification") and `landed`
     ("Implemented and guarded", the composite on the L4, whose judged run's Q7 failed and stands). A
     card stands here only where its map part's level is one of them, and, at a level that is neither
     qualified nor failed, where it reads a judged run's verdict file. A failure is not set apart:
     projective stepping (Failed qualification), MG1's and parity rung 1's failed judged runs, the L4's
     run C and the first origin-of-life harness run's kept failure stand among the passes.
  3. `development`, "Development runs".
  4. `invented`, "Invented numbers": the test sheet, alone. It is no run of the engine. (In the
     catalogue's code `example: true` means invented numbers; no string a visitor reads puts "example"
     and "invented numbers" on one card.)
- **`not_run`**: `{says, lens}`: the one line that says what was designed or planned and never ran is
  on the Engine map, and the lens to link to. Nothing designed or planned and never run has a card.
- **`listing`**: `experiments`, every catalogue experiment a card opens, in the cards' order;
  `entries`, every model-system entry a card opens. This is the landing's own list; the catalogue's
  `listed` keeps today's tab as it is until the landing exists.
- **A card**: `id`, `band`, `kind`, `title`, `asks` (a question, or null where it shows rather than
  asks, with `shows`), `standing` (above), `record` (possibly empty), and by kind:

| Kind | What it is | Fields |
| --- | --- | --- |
| `replay` | Its runs are packaged for the viewer; it opens the view that exists today | `replay`: `opens` (`{experiment}` or `{entry}`, what a press opens), `experiments`, `runs`, `runs_from`, `parts` (where it plays several experiments as one: each `{experiment, label, status, runs}`), `run_labels` (an entry's), `still` |
| `standing` | A standing with no replay | `record` with its verdicts and scope lines; `rerun` |
| `rows` | A family verified row by row against references | `rows`: each `{id, claim, passed, reference, modules}`, from the run of record (`record[0]`), and `rows_from`; `rerun` |

  Optional on any card: `answer`; `cite` (`{says, from}`, the catalogue's own citation of a paper,
  word for word); `switch` (`{heading, items, source}`, a note's paragraph, read at its own revision
  and found the same at the record's).
- **`still`** is the landing's, typed in the source file (`replay.still`): `{light, dark, width, height}`, the stills of
  the card's opening view for each theme, as paths beside the page (`stills/<card>.<theme>.jpg`), and their size in
  pixels; null where a card has none. The stills are made by `tools/make_stills.mjs` into `data/replays/stills/`, with
  their record (`stills.json`: each still's card, address, size and checksum, the page's revision and the renderer);
  the export publishes them beside the page, and the landing fetches each only when it comes near the screen.
- **`rerun`** is room for a replay made again later, through the engine's run-view writer, of a run
  that has a standing (two judged feature-request worlds are expected). It is null today. When filled
  it is `{revision, says, replay}`: a rerun at a named revision of main, saying so in its own words.
  It is never called the judged run, which stays the verdict beside it.

A source anywhere is `{path, where?, revision}`: a path inside the engine's repository (the viewer's
own files under `visualizer/`), a place in its words, and a revision of main in full.

## Rules the tests hold (`tests/experiment_cards.test.mjs`)

- The cards are what the tool writes from tracked files and the readings (`--check`).
- Four bands in order; every card in one band, of one kind, with a standing (`says`) or the stated
  reason for none (`none`).
- Every source carries a full revision the gathering found on main; no file names a path of a
  machine or a clock time.
- Every count names its run, file and field; every verdict its day; a count left off says why.
- A map part's standing is the part's, field by field, its level as the map gives it; a card in the
  `judged` band has a map part at one of the band's levels, and one that is neither qualified nor failed
  reads a judged run's verdict; nothing typed (titles, questions, reasons, and the band words outside the judged band's own) says judged or qualified; an
  answer and a catalogue or entry standing are their source's words.
- The gap-junction work: `first` is "Development work, not judged (D138).", no level of its own, its
  citation is the catalogue's, the note's paragraph on the switch is carried from `a4b2db3d`, and no
  string a visitor reads says replicated, reproduces, agrees or matches (nor "replication", which
  stands only in a source's path and place).
- "Example" and "invented numbers" never on one card; the test sheet never says "example".
- Every judged entry of PROGRESS.md's runs is on a card or left out with a reason, never both.
- A judged run behind several cards names the others on each (`also_on`).
- The listing holds every replay the page packages; the catalogue's `listed` is today's; every
  experiment part of the map is on a card or left out with a reason.
- Each card's map part says the same in the scene the page draws as in the map's overlay.
- A planted card of each fault is caught: "agrees" in the note's paragraph, "replicated" in a part's
  label, "example" beside invented numbers, "qualified" or "judged" typed by hand; "replication" in a
  source's place is not.
- A rerun, when one is filled in, says it is a rerun and never calls itself the judged run.
- One command moves the record forward (`--revision`), writing the new revision into the source file.
- The gathering, on small fixtures (`tests/cards-fixtures/`): judged rows only are counted; the layouts `tally`, `named`
  and several files are read; a count worded otherwise is left off, and stands where the protocol's
  entries confirm it, with the record's words beside it and the tool's note on a criterion judged in
  parts; the judged entries are listed; a snapshot off main names no revision; a day is the named line's; a
  clock time leaves a heading; the paragraph is read at its revision; the full check fails when a run's
  file changes; words naming a path of a machine, a paragraph changed since its revision and a folder
  named as a path are refused.

## A card of each kind (shortened: "…" marks words left out here)

The judged band, as built:

```json
{
 "id": "judged", "label": "Judged under a registered protocol",
 "says": "Each card here was judged under a registered protocol, experiment or qualification. Passes and failures stand side by side, and each card shows its own level from the Engine map.",
 "status": null,
 "levels": [
  { "id": "qualified", "label": "Qualified or judged", "says": "Numerically qualified (a registered protocol passed) or judged (used in a registered experiment), in its declared scope." },
  { "id": "failed", "label": "Failed qualification", "says": "Built, then failed its registered qualification. Kept as evidence and not relied on." },
  { "id": "landed", "label": "Implemented and guarded", "says": "On main with its tests and guards: …" }
 ],
 "cards": ["e07-v1", "fr1", "…", "water", "replacement", "l4-agreement", "fixed-points", "projective"]
}
```

A standing that failed (its verdict's tally, with what was not evaluable):

```json
{
 "id": "projective", "band": "judged", "kind": "standing", "title": "Projective stepping",
 "standing": { "from": "map", "part": "num.projective", "status": "failed", "level": { "label": "Failed qualification", "…": "…" }, "as_of": "2026-11-10", "says": "A long-time mode that takes bursts of fine steps and then jumps ahead. It failed its qualification on the absolute error caps.", "…": "…" },
 "record": [{
  "says": "Projective (C) qualification qual-01: FAIL (9–10 November).",
  "verdict": { "run": { "evidence": "projective-c-20261109-01", "within": ["qual-01"] }, "protocol": "projective-c-qualification-v1", "passed": false,
               "count": { "passed": 2, "of": 7, "not_evaluable": 1, "unit": "cases", "from": { "…": "…", "file": ["judgement.json"], "field": "passed, failed and not_evaluable_or_incomplete: the file's own numbers" }, "confirmed_by": [] },
               "day": { "date": "2026-11-10", "…": "…" }, "snapshot": { "revision": "ca70d4a68456559e37e4c86218203d4c2fe62839", "…": "…" } }
 }],
 "rerun": null
}
```

A replay:

```json
{
 "id": "e07-v1", "band": "judged", "kind": "replay",
 "title": "E07-v1: renewal",
 "asks": "Can a voltage pattern written into a tissue survive while its cells are replaced?",
 "standing": {
  "from": "map", "part": "exp.e07v1", "label": "E07-v1: renewal", "status": "qualified",
  "level": { "label": "Qualified or judged", "says": "Numerically qualified (a registered protocol passed) or judged …" },
  "as_of": "2026-11-14",
  "says": "Can a voltage pattern written into a tissue survive while its cells are replaced? Judged: under donor-copy turnover it did not renew, and 8 of 15 predictions held. …",
  "sources": [{ "path": "PROGRESS.md", "where": "E07-v1 judged (13–14 November)", "revision": "b5d3faf064444db7dbc9321ec0f7e77c9ccc9ee2" }, "…"],
  "tests": []
 },
 "answer": { "from": "catalogue", "experiment": "e07-v1", "judged": true, "answer": "no", "label": "The disc did not renew", "text": "Under donor-copy turnover the written disc did not renew, …", "sources": ["…"] },
 "record": [{ "says": "E07-v1 judged (13–14 November): under donor-copy turnover the written disc did not renew. …", "source": { "path": "PROGRESS.md", "where": "…", "revision": "718405b287d0d5623d522d4e7ca0523a7d151722" } }],
 "replay": { "opens": { "experiment": "e07-v1" }, "experiments": ["e07-v1"], "runs": 38, "runs_from": [{ "experiment": "e07-v1", "runs": 38, "from": { "file": "data/replays/selection.json", "field": "e07-v1.runs" } }], "still": null }
}
```

A standing with no replay (one of its verdicts):

```json
{
 "id": "fr1", "band": "judged", "kind": "standing",
 "title": "FR-1: a closed compartment",
 "asks": "Can a cell hold a closed compartment of its own, with its own volume and amounts, that exchanges species with the cell?",
 "standing": { "from": "map", "part": "fr.internal_compartment", "status": "qualified", "as_of": "2026-11-18", "says": "A closed compartment inside a cell: … Numerically qualified, on CPU only, within its scope line: …", "…": "…" },
 "record": [{
  "says": "FR-1 judged: passed (18 November 2026).",
  "source": { "path": "PROGRESS.md", "where": "FR-1 judged: passed (18 November 2026)", "revision": "718405b287d0d5623d522d4e7ca0523a7d151722" },
  "scope": { "says": "Scope: cell_owned_compartments@1 with exchange@1, turnover@1 and local_species_reactions@1 as built at 05a8d193: …", "source": { "…": "…" } },
  "verdict": {
   "run": { "evidence": "closed-compartment-fr1-20261117", "within": ["judged", "run-05a8d193"] },
   "protocol": "fr1-closed-compartment-v1", "passed": true,
   "count": { "passed": 44, "of": 44, "unit": "judged criteria",
              "from": { "evidence": "closed-compartment-fr1-20261117", "within": ["judged", "run-05a8d193"], "file": ["verdict", "verdict.json"], "field": "criteria: the entries whose judged is true, and those of them whose passed is true" },
              "confirmed_by": [{ "…": "reading.json" }, { "path": "PROGRESS.md", "…": "…", "says": "44 of 44 judged criteria" }] },
   "day": { "date": "2026-11-18", "from": { "…": "…", "file": ["judged.done"], "field": "the date of its first timestamp" } },
   "snapshot": { "revision": "05a8d1934e785ea9a575fbe5673569f589bdbc42", "from": { "…": "…", "field": "source.git_revision" } }
  }
 }],
 "rerun": null
}
```

Rows:

```json
{
 "id": "origin-laws", "band": "development", "kind": "rows",
 "title": "Origin-of-life laws (OL1)",
 "asks": "Do the origin-of-life engine's first laws hold against references written without the engine's code?",
 "standing": { "from": "map", "part": "laws.origin_laws", "status": "landed", "level": { "label": "Implemented and guarded", "…": "…" }, "says": "Landed for development, not judged (18 November 2026). …", "tests": ["tests/unit/test_assembly_lineages_v2_registration.py", "tests/unit/test_assembly_lineages_v2_kernel.py"], "…": "…" },
 "record": [
  { "says": "OL1 landed: the origin-of-life laws, cells.assembly_lineages@2 (18 November 2026).", "item": "Verified against code-blind references. …", "verdict": { "passed": true, "count": { "passed": 6, "of": 6, "unit": "rows", "…": "…" }, "snapshot": { "revision": "3e39bcc55206832d8dbd75aae7079883bf6a21a1", "…": "…" }, "…": "…" }, "…": "…" },
  { "says": "…", "item": "The first harness run failed one row on a record rule. … Both verdicts are kept.", "verdict": { "passed": false, "count": { "passed": 5, "of": 6, "unit": "rows", "…": "…" }, "…": "…" } }
 ],
 "rows": [
  { "id": "OL1-1", "claim": "Every channel keeps local detailed balance", "passed": true,
    "reference": { "path": "validation/ool/references/README.md", "where": "The rows (OL1): row OL1-1", "revision": "a9f4013094be5b8769845827e6c2e5cd764216da" },
    "modules": [{ "path": "validation/ool/references/detailed_balance.py", "revision": "a9f4013094be5b8769845827e6c2e5cd764216da" }, "…"] },
  "…"
 ],
 "rerun": null
}
```

## For the landing

- Show a card's `standing.first` before anything else where it has one; a null `level` shows no
  level.
- `none` is the card's reason for having no level, in its own words or the catalogue's.
  `level_withheld`, `count_withheld` and `snapshot.says` are the tool's own words for what a card
  leaves off: for a card's detail at most, never in place of a standing, and never as the record's.
- `record[].says` is the record's sentence with its place (`source`); `scope.says` is the scope line,
  shown with the verdict it belongs to, so that a pass is not read as more than it is.
- A null `count` shows no number.
- A replay card's press opens `replay.opens` as the Experiments tab opens it today (an experiment's
  opening run, or the entry's own view).
