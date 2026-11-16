# Entries: what the species switch offers, in three kinds

Status: **proposed for the viewer, 16 November 2026** (`docs/ENTRIES_DESIGN.md`). The reader is
`tools/lib/entries.py`. The scene and the page do not read these files yet: the hook-up is set
out step by step in the design note, section 6, and applied when the files it touches are free.

The switch offers one kind of thing today, a species. It will offer three kinds of entry:

| Kind | Its file | Its contract | Example |
| --- | --- | --- | --- |
| A species | `data/species/<id>.json` | `SPECIES.md`, with the four keys below | Human, E. coli |
| A cell type of a species | `data/cells/<species>.<id>.json`, or the species' own `cell` block | `CELL_TYPES.md` | the human's generic cell; later its ventricular cell |
| A model system | `data/models/<id>.json` | `MODEL_SYSTEMS.md` | a GARD assembly, under "Origin of life" |

A model system is a model, not an organism: it has no taxon, no cell and no organs, and its
levels are its own. A cell type belongs to a species and is a cell.

## Ids

- **An id is a plain word:** lower-case letters, digits and hyphens.
- **Species and model systems share one set of ids.** A model system may not take a species' id.
- **A cell type is named within its species:** its full id is `<species>.<type>`, as in
  `human.generic`.

## The keys a species file gains

All four are optional, and they stand at the top level of the file. `tools/lib/species.py`
passes top-level keys it does not know without a word, and it refuses any key inside `cell` that
it does not know. So no existing file changes, and the present reader keeps reading every file
exactly as before.

| Key | Meaning |
| --- | --- |
| `cell_type` | `{"id", "label", "loop"}`: the name of the cell type the species' own `cell` block describes, and the id of its looping run. Left out, the id is `cell`, and the label is "Generic cell" for a `generic` species and "Its cell" for another |
| `cell_types` | The ids of the species' other cell types, each a file `data/cells/<species>.<id>.json` |
| `default_cell_type` | The cell type the page opens on. Left out, it is the species' own `cell` block |
| `modelled.record` | The citations behind the species' word (see below). For a species it is optional until the hook-up, since today's files state their record in `modelled.text` |

## What Cells models of an entry: `modelled`

```json
"modelled": {
  "state": "proposed",
  "text": "One or two plain sentences, in the record's own words.",
  "record": [{"path": "visualizer/docs/ORIGIN_OF_LIFE.md", "where": "Decided"}],
  "design": null,
  "model": null
}
```

**One ladder of words, for every kind.** Each word requires everything the word before it
requires, and more. A word is met by what tracked files hold:
- tracked files of the engine's main;
- the viewer's own tracked notes, where a user's decision or request is recorded with its words.

| Word | What the record must hold | The page says | Kinds that may use it |
| --- | --- | --- | --- |
| `generic` | Nothing of the entry itself is modelled. Cells models a generic cell and tissue, and the entry lends it names or outlines; the text says which | "Generic cell" | species, and a species' own default cell type |
| `proposed` | A tracked record proposes modelling it, or asks for it to be looked into. Nothing of it is in the engine | "Proposed, not modelled" | every kind |
| `planned` | A tracked record decides that it will be modelled: a decision of main, the plan or the roadmap, or the user's decision quoted in the viewer's own note. It is not started, and no design of it is a tracked file of main | "Planned, not modelled" | every kind |
| `designed` | Its design note is a tracked file of main (`design`: its path). Its code is not on main | "Designed, not modelled" | every kind |
| `modelled` | The record of main says a registered model of it exists (`model`: its id) | "Modelled", beside the map's status of that model | every kind |

- **A file may state a lower word than its record allows,** never a higher one.
- **A file that exists only on a development branch moves no word.** It is not cited and it is
  not a reason.
- **What the reader holds:**
  - the word is one of the five and allowed for the kind;
  - `generic`'s text says "generic";
  - every word above `generic` has at least one citation in `record` (for a species, once the
    hook-up has made `record` required);
  - `designed` gives `design`, a tracked file of main;
  - `modelled` gives `model`;
  - every citation is one the rule below allows.
- **The words the page writes** follow the third column. The first word of each says what the
  record holds; the words "not modelled" say that nothing of it is in the engine.

## Citing the project's record: `{"path", "where"}`

- **`path`** is one of two kinds of file:
  - a tracked file of the engine's main, such as `docs/DECISIONS.md`;
  - one of the viewer's own tracked files, prefixed `visualizer/`, such as
    `visualizer/docs/ORIGIN_OF_LIFE.md`.

  The extractor holds the first against main's `git ls-files` and the second against the viewer's
  folder, as it already does for the map's sources (`own_file` in
  `tools/extract_architecture.py`).
- **`where`** is a heading or a decision's id, in words.
- **No other keys.** A citation never carries `ref`, `branch` or `commit`. A file that exists only
  on a development branch is not a tracked file and is never cited as a path. Where an entry must
  speak of such a file, the viewer's own tracked note names it in words, with its branch and
  commit as read, and the entry cites that note. The engine's GARD design note is cited this way.

## Sources and licence classes

As `SPECIES.md` sets them out:
- **Sources are keyed.** Each has `text`, a `doi` or a `url`, `licence`, `class` and `accessed`.
- **The classes are** `permissive`, `non-commercial` and `no stated terms`. The class must
  follow from the licence text, as `tests/licence_classes.test.mjs` reads it.
- **Only a permissive source stands behind a value:** a number, a fact, a level's words or a
  capability's words. A source of another class is a pointer in `see`, and nothing is taken from
  it.

The one widening is D186 (main, 16 November 2026): a number from an open paper that states no
licence may stand with its citation. Such a source has the class `no stated terms` and
`"standing": "open paper, numbers only"`, as `MACHINES.md` sets out, and it stands behind a
number alone, never behind words.

Until the licence test walks `data/cells/` and `data/models/` (a step of the hook-up),
`tools/lib/entries.py` holds these files to the rule.

## The switch

- **Headings.** There is a heading for each `group`, in the order of its first entry. Within a
  heading, entries stand in `order`.
  - The species keep theirs: Animals, Bacteria and Plants.
  - A model system brings its own, such as "Origin of life".
- **A species' row:** its label, its organism in italics, and its word.
- **A model system's row:** its label, its `is` line where a species has its organism ("A model,
  not an organism"), and its word.
- **A cell type** is a row under its species only where the species has more than one. That
  control lands with the first second cell type, and how it is shown is designed after the
  phone-layout pass. It adds nothing to a phone's top bar (`docs/CELL_TYPES_DESIGN.md`,
  "Decided").
- **`default` is true on exactly one species.** A model system is never the default.

## The address

- **`entry=<id>`** chooses a species or a model system.
- **`species=<id>` and `atlas=<id>`** still choose a species, as today, so every link that works
  now still works. They also choose a model system: one parameter names any entry.
- **`cell=<type>`** chooses a cell type of the species shown. A model system ignores it.
- **The page writes** `entry=`, and `cell=` only where the cell type shown is not the species'
  default.

## What a view gets from an entry

The view of an entry is the Cell view for a species and a cell type, and the model system's own
view (`MODEL_SYSTEMS.md`). Each gets the same block, which the scene will carry:

```json
{"kind": "model system", "id": "gard", "label": "GARD assembly", "group": "Origin of life",
 "levels": [{"id": "molecules", "label": "Molecules", "shows": "...", "status": null}],
 "view": {"kind": "assembly"}, "clock": {"base": "fission", "says": "..."},
 "runs": [{"file": "data/origin/example-run.json", "label": "...", "kind": "example"}],
 "modelled": {"state": "proposed", "...": "..."}, "facts": [], "sources": {}}
```

For a species and a cell type, `kind` is `species` or `cell type`; `levels` are those of
`SPECIES.md` (molecules, cell, tissue, organ, organism); `view.kind` is `cell`; and a cell type's
`runs` hold its looping run.

## The clock

- **One authority: the run.** A run states its own clock:
  - a species' replay in `view.time`, in seconds (`RUN_VIEW.md`);
  - an assembly run in `time`, with `base: "fission"` and the words it is counted in
    (`ASSEMBLY_RUN.md`).
- **An entry's `clock`** (model systems only) is a label: `{"base", "says"}`, where `base` is the
  word its runs state. It is shown before any run is loaded. It is never a rate and never a
  speed.
- **Where a run's clock differs from its entry's label,** the run's clock is shown, the page's
  reader of the run warns, and the entry's label is not used for that run.
- **The page keeps one time control,** the Experiments timeline, with a second ladder of speeds
  for a clock that is not seconds. That ladder and its words are the view builder's seam, not
  this contract's.

## What the other views say

| When the switch shows | Cell and scales | Protein atlas | Experiments | Engine |
| --- | --- | --- | --- | --- |
| A species | As today | As today | As today | As today: it depends on no entry |
| A cell type | That cell, and the levels of its type | The species' own proteins. A cell type's own set only where its file names one (`CELL_TYPES.md`, `proteins`); else the panel says that no source gives it | As today. A looping run of the type shows in the Cell view | As today |
| A model system | Gives way to the model system's own view. Choosing a species from there returns to the Cell view | The engine's machines, with no species' side: "A model system has no proteins of a species: its molecules are the model's own types" | Lists the runs the model system names. Each opens in the model system's own view | As today |
