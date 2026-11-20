# The experiment package: one way in for every experiment the viewer plays

Status: **decided by the owner on 19 November 2026; round one is built (section 5, "What is built").** The owner asked whether
the Experiments tab has a standard package format, with future use in mind, then for a draft
with options, and accepted the recommendations of section 4 the same evening: both levels, the
words in the package, schema files with a validator and a conformance set, a required visibility
and licence, the arrays as they are, the three older experiments left as derived, and the
specification kept by the engine's lead. Sections 1 and 2 describe what exists, read from the
files. Section 3 is what was accepted; its names stay proposals until the engine's lead has read
them, since the source level is the engine's to write. Building is in two rounds on the viewer's
side (section 5): the manifest's contract and the validator, then the play package. The engine's
side of it (the run view and its writer) is the engine's lead's; this note changes nothing there.

## 1. What exists today

Most of a package exists already, in three layers that were never given one name.

**What an engine run writes.** A run folder for the viewer holds one folder for each arm, and
each arm's folder is what this note calls a package:

```
<run folder>/
  index.json             optional: the experiment's id, what it represents, and its packages
  summary.json           optional: cells.experiment_summary@1, the sweeps (parameter, readouts, arms)
  <arm>/
    view.json            cells.run_view@1: what the run saved and how to read it
    trajectory.npz       the arrays (a windowed run has windows.jsonl and chunks/ in its place)
    resolved_config.json the run's definition, as resolved
    manifest.json        the engine's run manifest: when it was made, its definition's and files'
                         digests, the runtime, its provenance and status
    run.json             the driver's own statement: status words, citation, revision, snapshot,
                         models and laws
    summary.json         the engine's summary of the run: steps, end time, the ledgers' largest errors
    checkpoint_final/    the state to restart from
    concentration.json   optional sidecar, cells.experiment_quantity@1: a quantity the driver states
                         for each cell at each time
    criterion.json       optional sidecar, cells.experiment_criterion@1: the same with thresholds
  <arm>/REFUSED.json     in place of all that, for a pick the engine's checks refused
```

`view.json` is the engine's one shared writer's (`src/cells/records/run_view.py`, on main since
16 November 2026, D154). It states the run's identity and models, the space and its sets, the
time bases with the files that hold them, every record with its unit, kind, sign, owner and
layer, the layers with their representation, the events, the constants, and what is left
unstated with the reason. Its design note on the engine's side (`docs/RUN_VIEW_DESIGN.md`) is
still marked proposed.

**What the viewer adds, in its own tracked files.**

| File | What it holds |
| --- | --- |
| `data/replays/selection.json` | Which evidence folder an experiment is read from (a folder's name and the folders inside it, never a path), and which runs |
| `data/replays/overlay.json` | The experiment's words: its label and plain sentences, its sources, the labels of its groups, classes, records, parameters and readouts, which sidecars to read, and the choices of its picture |
| `data/replays/cards.source.json` | Its card on the landing: title, what it asks, its band, and which part of the Engine map and which entry of the record it reads its standing from |

**What the page plays.** One tool (`tools/adapt_run.py`, `npm run adapt:runs`) reads the run
folders and writes the files the page fetches, which are never committed:

| Format | File | What it is |
| --- | --- | --- |
| `cells.visualizer.replay_index@1` | `runs/index.json`, carried in the page | The catalogue: every experiment with its words, every run with its file |
| `cells.visualizer.replay@1` | `runs/<run id>.json` | One run: its view and its arrays as one payload, under 1 MB |
| `cells.visualizer.replay_part@1` | `runs/<run id>.<part>.json` | Records of a run in a file of their own, fetched when a layer first needs them |

A run's id is `<experiment>--<arm>--seed<n>` (the seed where there is one), in lower-case
letters, digits, dots and hyphens. A run is fetched when it is first shown. The contract is
`schema/RUN_VIEW.md`, "Packaged for the viewer".

**Counted on the page of Version 50:** nine experiments (eight of the engine's and one test sheet
of invented numbers), 112 runs, 341 files.

## 2. Where it is not a standard yet

1. **The folder has no name and no version.** `view.json` has a format; the folder around it
   does not. `index.json` is written by one family of drivers, is optional, and carries the
   absolute place of each package on the machine that wrote it.
2. **Three of the eight experiments have no engine view.** E07-v1, the turnover pre-screen and
   the first secreted-species run were written before the writer existed. The adapter rebuilds
   their views from tables of its own and lists every derived piece. Five come through the
   engine's own view: the four gap-junction sets and the planarian loop.
3. **An experiment's words live in the viewer.** A new experiment whose runs carry a view needs
   no code, but it needs three edits in the viewer's files. A package cannot describe itself.
4. **One view kind has a format of its own.** The assembly is not a run view
   (`cells.visualizer.assembly_run@1`, made by `tools/adapt_assembly_run.py`): it has no
   geometry and no clock of that kind. A package says nothing of which kind it is.
5. **No schema file and no validator.** The contract is prose and the adapter's refusals. Nobody
   outside the adapter can check a package before it is read.
6. **Nothing says who may see a package, or under which licence.** Today that is known only
   from where a folder lies. Private data is to come, and is never to be public.
7. **Size.** The played arrays travel as base64 inside JSON, a third larger than the bytes. The
   artifact's link holds 468 of the 511 files a page may have; the site has no such limit.
8. **`run.json` is each driver's own** (`gap_junction_tissue.run@1` for one family), so the
   status words, the citation and the revision are not in one place for every run.

## 3. The proposal

Two levels, one tool between them, and one manifest.

**The source package** is the run folder of section 1, given a name and made portable. It is
what the engine side writes and what stays with the frozen evidence.

**The play package** is what is carried to a page, a site or another machine: one experiment's
catalogue entry with its words, its run files and their parts, and nothing of the evidence
(no checkpoints, no definitions). It is today's `runs/` folder cut to one experiment. A viewer
plays it with no engine files at hand.

**The manifest** (`experiment_package.json` in both levels, `cells.experiment_package@1`; shown with the
names the engine's lead settled on 20 November 2026, section 6):

```json
{
  "format": "cells.experiment_package@1",
  "level": "source",
  "experiment": {
    "id": "gap-junction-linear-network",
    "title": "…", "asks": "…", "plain": "…",
    "status": "development run of the engine, not judged",
    "sources": [{ "path": "docs/…", "where": "…" }],
    "citation": { "text": "…", "doi": "…" }
  },
  "engine": { "revision": "…", "snapshot": "…", "clean": true },
  "made": "2026-11-17",
  "visibility": "public",
  "licence": "CC-BY-4.0",
  "summary": "summary.json",
  "packages": [
    { "arm": "figure3-g0.5", "kind": "cells.run_view@1", "path": "figure3-g0.5",
      "sidecars": ["concentration.json"], "label": "…" }
  ],
  "refused": [{ "arm": "…", "file": "REFUSED.json" }]
}
```

Its rules:

- **Paths are relative to the manifest, never absolute,** and name files inside the folder only.
- **`kind` says how a package is read.** `cells.run_view@1` today; the assembly's kind,
  `cells.assembly_view@1`, beside it; a new kind of view is a new kind here, and a viewer that
  does not know a kind says so and plays the rest.
- **`experiment.status` is the owner's own words for the run's standing.** For an experiment
  of the public record the page goes on reading its standing from the Engine map and the
  record, as the cards do, and shows the package's words only where the record has none.
- **`visibility` and `licence` are required.** A tool that stages a page, a site or an API
  refuses a package that is private, and one that states no licence. Words and numbers read
  from a source keep that source's terms.
- **Identity:** a run's id is `<experiment id>--<arm>` with the seed where there is one, as
  today. Ids are what other files point at: a card, an address, and a life stage's span that a
  saved run fills (`schema/SPECIES_STAGES.md`). An experiment's id is one for each source
  package; the sweeps of one experiment are each a package, gathered by `experiment.group`.
- **Provenance stays the engine's:** the revision, the snapshot and whether its tree was clean,
  as each run's own files state them. The manifest copies them; it adds no digest of its own.
  The models a run ran are its view's own statement, and are not copied.
- **Sidecars are named in the order they are played,** and a reader follows that order.
- **Versions:** within a major, a reader ignores what it does not know. A change that an older
  reader would misread is a new major.

**The validator** (`tools/check_package.mjs`, a proposal) reads a package of either level and
says what is wrong, in sentences: a missing file, a path outside the folder, a view the manifest
names that is not `cells.run_view@1`, a sidecar whose cells or times do not match its view, a
record whose array is not in the files the view names, an absolute path anywhere, no licence.
The adapter runs it before packaging, and anyone who makes a package can run it first. The
small runs already kept as fixtures (`tests/engine-views/`) become its conformance set.

## 4. The decisions, with their options, as decided

The last column is what the owner accepted on 19 November 2026.

| | Decision | Options | Decided |
| --- | --- | --- | --- |
| 1 | What "the package" is | **A.** The engine's run folder, named and made portable. **B.** A portable play package only. **C.** Both levels, with one tool from the first to the second | **C.** The first is nearly there, and the second is today's `runs/` folder cut to one experiment |
| 2 | Where an experiment's words live | **A.** In the viewer's files, as today. **B.** In the package's manifest, with only the picture's choices left in the viewer | **B.** A package then describes itself, and a new experiment needs no edit in the viewer |
| 3 | How a package is checked | **A.** Prose and the adapter's refusals, as today. **B.** Schema files and a validator. **C.** B with a conformance set of small packages | **C.** The small packages exist already as test fixtures |
| 4 | Public and private | **A.** Known from where a folder lies, as today. **B.** `visibility` and `licence` required, and the staging tools refuse what is private or unlicensed | **B.** It is one field and one refusal, in place before the first private package exists |
| 5 | The arrays | **A.** As today: base64 in JSON, parts under 1 MB. **B.** Binary parts with a small index. **C.** A chunked store read by range, for large tissues and long runs | **A now.** B when a run outgrows it; C only on the site, when a run needs it |
| 6 | The three older experiments | **A.** Left as they are, marked derived. **B.** Views written for them beside the frozen evidence, by the engine's writer | **A.** Frozen evidence is not written into; B is the lead's call |
| 7 | Who keeps the specification | **A.** The viewer, in this folder. **B.** The engine's lead, beside the run view's note, with the viewer as its first reader | **B.** The source level is the engine's to write, so its contract belongs with the writer |

## 5. What it would take

- **The viewer's side** (this lane): the specification's final text, schema files for the
  manifest and the three played formats, the validator with its conformance set, the adapter
  reading a manifest where a folder has one (and going on reading folders that have none), and
  the staging tools' refusal of private or unlicensed packages. About two days of an agent's
  work, in two rounds: the manifest and validator first, the play package second.
- **The engine's side** (the lead's): one shared writer for the manifest, in place of each
  driver's `index.json` and `run.json`; the run view's note moved from proposed to accepted.
- **Not proposed here:** a database, an API for packages, a binary container, runs on request,
  or any change to a frozen evidence folder.

### What is built (round one)

- **The contract** of the source package and its manifest: `schema/EXPERIMENT_PACKAGE.md`, with the
  manifest's schema file `schema/experiment_package.schema.json`. The field names and rules are as
  the engine's lead settled them on 20 November 2026 (section 6); the contract's last section says what
  that changed from the proposal of section 3.
- **The validator**, `python3 -I tools/check_package.py FOLDER [--json]` (Python, standard library
  only, in place of the `tools/check_package.mjs` named above): it reads a folder with a manifest, or
  one without as the adapter reads it today, writes nothing, and exits 0 when the package can be read,
  1 with every problem found (a code and a sentence that names the file and the field), 2 for a wrong
  call. Beyond its own checks it reads each package by the adapter's own reading, so a package it passes
  is one `npm run adapt:runs` reads. It judges no science.
- **The conformance set**: small packages built by `tests/check_package.test.mjs` from the fixtures
  under `tests/engine-views/`; each breach gives its own code. The same test holds that the schema file
  is what the validator writes and that the contract names exactly its codes and fields.
- **The adapter reads a manifest** where a run folder has one (`experiment_package.json`): its arms, their sidecars
  and its refused picks, in place of `index.json`, the overlay's `sidecar` and the search of the folder.
  A folder with a manifest is packaged to the same bytes as without one. Nothing else moved: the
  experiment's words still come from the overlay, and no folder written so far has a manifest.
- **The adapter's own reading stays inside a run's folder**, with or without the check before it: a
  file name its files give that leaves the folder, a link in a run folder, and a JSON file or a
  manifest that is a link are each refused. It does not yet run the whole check itself.
- **How a package is checked:** run the validator on the run folder before the viewer reads it. On a
  folder with no manifest it says so in a note and gives the manifest the folder would need, with `null`
  where the folder does not say (its title, visibility and licence).
- **The manifest's copies are held to the runs' own records.** Where the manifest gives the engine's
  revision, its snapshot or whether its tree was clean, each view must agree, and so must each arm's
  `run.json` where it has one. Where a `run.json` lists its sidecars, the manifest names the same ones.
- **Tried on copies of real run folders** (20 November 2026). Copies of the linear networks' and the
  tissue line's run folders were each given a manifest under the settled names (section 6), the tissue
  line's sidecars in the order they are played. The validator found no problem in either, and the
  adapter packaged them to the same 154 run files, byte for byte, as it does from the folders
  themselves. The folders themselves were not written into.

## 6. What the engine's lead settled (20 November 2026)

This note left four points open for the engine's lead, who keeps the specification (decision 7). The
lead settled them, and the names of section 3, on 20 November 2026. `schema/EXPERIMENT_PACKAGE.md` is
written to that, and its last section lists what changed from the proposal.

**The four points:**

- **Who writes the manifest:** a tool beside the run view's writer, called by each driver at the end
  of its run. The experiment's words, its licence and its visibility are the driver's to give; the run
  view's writer stays one run's.
- **`run.json`:** it stays the run's own record, and is pointed at. The manifest copies its revision,
  its snapshot and whether the tree was clean, and the validator holds the copies to it. New drivers
  write `clean` for a clean tree; the linear networks' older `snapshot_clean` is read as the same.
- **The assembly family:** a second kind, `cells.assembly_view@1`, written by its model's own writer.
  The viewer's reader names such a package and leaves it aside until that writer exists.
- **A judged run's play package:** it carries the verdict's summary (its count, its day, its tag), as
  the cards read it, and no evidence files. This is the next round's.

**The ids.** An experiment's id is one for each source package, and it is the public id. Where the
engine's names differed from the viewer's, the viewer's ids stand, and the drivers take them up in
their manifests:

| Run folder | `experiment.id` | `experiment.group` |
| --- | --- | --- |
| The linear networks (`dev-06`) | `gap-junction-linear-network` | |
| The tissue line (`dense-01`) | `gap-junction-tissue-line` | `gap-junction-tissue` |
| The tissue line's ladder (`ladder-01`) | `gap-junction-tissue-ladder` | `gap-junction-tissue` |
| The tissue sheet (`sheet-01`) | `gap-junction-tissue-sheet` | `gap-junction-tissue` |
| The picks (`picks-01`: three runs, and two picks an engine check refused), which the viewer does not play | `gap-junction-tissue-picks` | `gap-junction-tissue` |
| The planarian loop | `planarian-loop` | |

These folders are frozen evidence and are given no manifest: the ids are what each driver writes from
its next run.

**What follows, and whose it is:**

- **The engine side's** (the lead's, after the viewer's second round): the tool that writes the
  manifest; the linear networks' `index.json` written with relative paths; the drivers taking up the
  manifest, one at a time.
- **The viewer's second round:** the play package and its manifest, with the experiment's words moving
  into it; schema files for the three played formats; the adapter running the whole check before it
  packages; the staging tools' refusal of a private or unlicensed package.
