# The switch's entries: species, cell types and model systems, designed as one change

Agent K's design for the coordinator, 16 November 2026. **Proposed.** The contracts are new
files: `schema/ENTRIES.md` (what the three kinds share), `schema/CELL_TYPES.md` and
`schema/MODEL_SYSTEMS.md`. The reader is `tools/lib/entries.py`, with its tests in
`tests/entries.test.mjs`. The first model system's file is `data/models/gard.json`. No existing
file was changed, and the page does not read any of this yet. The hook-up is section 6, as steps
to apply when their files are free.

**Why one change.** The user asked for "Origin of life" as a new kind of species, with GARD
first, and took every recommendation of `docs/ORIGIN_OF_LIFE.md`. Its "Decided" section reads:
"a GARD assembly is a model system, not a species: a new kind of entry, with four levels of its
own". The cell types of option B (`docs/CELL_TYPES_DESIGN.md`, which stays as it is) change the
same reader and the same switch. So the three kinds are designed together: what an entry is,
what a file of each kind holds, what the switch shows, what the address carries, and what each
view says when an entry is chosen.

**Refs read.**
- **The viewer:** branch `visualizer` at `a4ef7492`, then `e51ffeb4`, a merge of main that
  changed nothing read here. Other agents' uncommitted files were read around: `schema/SPECIES.md` (its working copy, which another agent is changing for the
  machines), `tools/lib/species.py`, `tools/extract_architecture.py` (`own_file` and the
  tracked-file check of cited sources), `src/lenses/cell.js` (`MODELLED` and the caveat),
  `src/ui/viewer.js` (the switch), and `docs/ORIGIN_OF_LIFE.md` at `a4ef7492` ("Decided",
  sections 1 and 3).
- **The engine's main:** `a243a42b`, read with `git show`: `docs/SCIENTIFIC_BASIS.md` (GARD's
  matrix and reservoir; the F12 definition) and `docs/ARCHITECTURE.md` ("GARD, Boolean
  regulation, and continuous biochemical equations need explicit contracts if supported; they
  do not share an assumed universal physical clock").
- **The engine's GARD design note:** `docs/GARD_DESIGN.md` on the development branch
  `gard-design` (`e75b4b1f`). It is not on main, and nothing here binds to it.

## 1. The decisions

### 1.1 The status word: one ladder for every kind

**The problem.** A species' `modelled.state` is `generic`, `proposed` or `modelled` today.
`SPECIES.md` defines `proposed` as "a proposal to model this organism exists; nothing of it is in
the engine", and the page writes "Proposed, not modelled", with the caveat "nothing of it is in
the engine". Every species marked `proposed` rests on a record of main:
- E. coli on D179: "The track stays on hold", and "E. coli is added as a data-only organism";
- Syn3A on D173: "Syn3A becomes the minimal-cell track", "Adopted as a track";
- *M. pneumoniae* on the Syn3A note's section 9, as its own file's text says.

The cell types' rule, decided today, is in the map's words: `planned` until the design note is a
tracked file of main, then `designed`. The origin-of-life note proposed `proposed` for GARD
"since the design note is now a tracked file on a development branch". That would give
`proposed` a second meaning, the engine has a draft design, and a file on a branch would move a
word that the same file cannot move for a cell type.

**The decision.** One ladder, and every word is met by tracked files alone:

| Word | What the record must hold | The page says |
| --- | --- | --- |
| `generic` | Nothing of the entry is modelled; a generic cell and tissue stand in, and the text says which | "Generic cell" |
| `proposed` | A tracked record proposes modelling it, or asks for it to be looked into. Nothing of it is in the engine | "Proposed, not modelled" |
| `planned` | A tracked record decides it will be modelled; not started; no design of it is a tracked file of main | "Planned, not modelled" |
| `designed` | Its design note is a tracked file of main (`modelled.design`); no code on main | "Designed, not modelled" |
| `modelled` | Main's record says a registered model of it exists (`modelled.model`) | "Modelled" |

- **A tracked record** is a tracked file of the engine's main, or the viewer's own tracked note
  where a user's decision or request is quoted. The map already rests the nucleus's `planned` on
  such a note (`docs/CELL_STRUCTURES.md`).
- **A file on a development branch moves no word.** It is not cited and it is not a reason.
- **A file may state a lower word than its record allows,** never a higher one. So every species
  file of today stays valid, with its word and its meaning.
- **Which kinds may use which words:**
  - species: all five;
  - a cell type: all five, `generic` only as a generic species' own default type;
  - a model system: every word but `generic`, since no generic model stands in for it.

**The reasons.**
- One word means one thing for every kind.
- `proposed` keeps the meaning `SPECIES.md` gives it.
- The cell types' rule (planned, then designed once the note is on main) becomes the ladder's
  rule for all.
- The page's words keep "not modelled" wherever nothing is in the engine.

**What it gives GARD: `proposed`.** Main's record names GARD twice, and neither mention proposes
modelling it. The scientific basis records that the preprint's GARD matrix and reservoir are
fixed environmental constraints; the architecture says GARD "need[s] explicit contracts if
supported". What meets a word is the user's request, quoted in the viewer's tracked note: "add
another agent to look into adding a new "species" type Origin of life and the first one GARD,
which is one theory we need for an origin of life simulation GARD, which our plastic heredity
paper was based on - we'll ask lead also do look into it".
- That sentence asks for GARD to be looked into, which is `proposed`.
- Read as a decision to model it, it would be `planned`. That reading is the user's to confirm
  (question 1).
- The engine's design note, on a branch, moves no word either way. When that note is a tracked
  file of main, GARD is `designed`.

**What it gives the cell types:** the human's ventricular cell meets `designed`.
- D183 and D184 on main decide it, which is `planned`.
- Its design note, `docs/HUMAN_CARDIAC_LAWS_DESIGN.md` (status "PROPOSED"), became a tracked file
  of main on 16 November 2026: main at `3b7f1cff` holds it, entered at `349f5483`.
- So by the rule as decided (planned until the note is a tracked file of main, then designed),
  its file, when made, says `designed`, with `design` naming that note. Its code is not on main.

**What it would let the existing species say** (not applied: no existing file changes in this
step):
- Syn3A's D173 is a decision ("Syn3A becomes the minimal-cell track"; "Adopted as a track"), so
  Syn3A could be `planned` (question 2).
- E. coli (on hold, data only) and *M. pneumoniae* (recommended for a later stage, not decided)
  stay `proposed`.

### 1.2 Sources: tracked files only, and a branch is named in words

**The decision.**
- **The citations behind an entry's word** are `{"path", "where"}`, in `modelled.record`.
- **A path is one of two kinds:**
  - a tracked file of the engine's main, checked against main's `git ls-files`;
  - one of the viewer's own tracked files, prefixed `visualizer/`, checked against the viewer's
    folder.

  The extractor already holds the map's sources to the same two kinds (`own_file` in
  `tools/extract_architecture.py`, and its warning "cited source ... is not a tracked file").
- **A citation takes no other key.** No `ref`, no `branch`, no `commit`.
- **A file that exists only on a development branch is never cited as a path.** Where an entry
  must speak of one, the viewer's own tracked note names it in words, with its branch and commit
  as read, and the entry cites the note.
- **The reader warns of each breach,** and the strict build will refuse it.

**For GARD:**
- `data/models/gard.json` cites `visualizer/docs/ORIGIN_OF_LIFE.md` (its opening, the user's
  request, and "Decided"), `docs/SCIENTIFIC_BASIS.md` and `docs/ARCHITECTURE.md`.
- Its text says "The engine's lead has proposed a design for it, on a development branch, not on
  main". The note it cites gives the file, the branch and the commit.
- The test holds the file to name no law, operator, record or file of that note, and to cite
  only tracked paths.

**Scientific sources** are as `SPECIES.md` sets them: keyed, each with its licence and its class,
and only permissive ones behind a value. D186's numbers from open papers may stand behind a
number alone. Until the licence test walks `data/cells/` and `data/models/` (hook-up step 2), the
new reader holds these files to the rule itself.

**This supersedes the review's draft.** `docs/CELL_TYPES_DESIGN.md` section 7.3 drafted
citations with `"ref": "cardiac-laws", "branch": true`. The contract no longer allows them: a cell
type's file cites the viewer's note on the cardiac cell, and the note names the branch.

### 1.3 The clock: the run states it; an entry only labels it

**The decision.**
- **One authority, the run.** A run states its own clock in its view (`view.time`): seconds for a
  species' run, as `RUN_VIEW.md` has it, and fissions for a GARD run. Main's architecture says
  that these models "do not share an assumed universal physical clock", and the run is where that
  is said.
- **A model system's file gives `clock`: `{"base": "fission", "says": "..."}`.** `base` is the word
  its runs state as their `time.base` (`schema/ASSEMBLY_RUN.md`). It is a label, shown before a run
  is loaded. It is never a rate and never a speed. A species and a cell type
  give none.
- **Where a run's clock differs from its entry's label,** the run's is shown, the page's reader of
  the run warns, and the label is not used for that run.
- **The page keeps one time control,** the Experiments timeline, with a second ladder of speeds
  for a clock that is not seconds. The ladder is the view builder's seam.

### 1.4 Decided already, and carried into the contracts

From `docs/CELL_TYPES_DESIGN.md` ("Decided") and `docs/ORIGIN_OF_LIFE.md` ("Decided"):

- **Cell types:**
  - The epicardial and M cells get no file and no row; `extends` is exercised by a test fixture.
  - The cell-type control lands with the first second cell type, after the phone pass, with
    nothing new in the phone's top bar.
  - The human opens on its generic cell.
  - The binding to the engine is optional, and no id is invented.
- **The model system:**
  - It stands under "Origin of life", with its own four levels.
  - Its runs play in its own view, and the Experiments view lists them.
  - The clock counts fissions.
  - The 0.9 line is drawn on the parent-to-daughter comparison only.
  - Composomes are named only where a run or its analysis names them.
  - There is no toy in the built viewer, and one lineage comes first.

## 2. What an entry is, kind by kind

| | A species | A cell type | A model system |
| --- | --- | --- | --- |
| File | `data/species/<id>.json` (`SPECIES.md`) | `data/cells/<species>.<id>.json`, or the species' own `cell` block (`CELL_TYPES.md`) | `data/models/<id>.json` (`MODEL_SYSTEMS.md`) |
| Levels | molecules, cell, tissue, organ, organism | its own cell and tissue; the organ and the body are its species' | its view's fixed list; for `assembly`: molecules, assembly, population, lineage |
| What Cells models of it | `modelled`, the ladder; `record` optional until the hook-up | `modelled`, the ladder, with its record; a capability may carry its own word in this cell | `modelled`, the ladder without `generic`, with its record |
| Its row in the switch | label, organism in italics, word, under its `group` | under its species, only where the species has more than one | label, its `is` line ("A model, not an organism"), word, under its `group` ("Origin of life") |
| The address | `entry=<id>`; `species=` and `atlas=` as before | `cell=<type>` beside the species | `entry=<id>` (`species=` also accepted) |
| Its view | the Cell view | the Cell view | its own view (`view.kind`) |
| Protein atlas | as today | the species' proteins; a type's own set only where a permissive source gives it | the engine's machines, with no species' side, and a line saying why |
| Experiments | as today | as today; a looping run shows in the Cell view | lists the runs it names, which open in its own view |
| Engine | as today | as today | as today |

Every kind shares the ids, the citations, the sources and their licence classes, and the block a
view gets (`ENTRIES.md`).

## 3. The contracts, in short

- **`schema/ENTRIES.md`** is what the kinds share:
  - ids, and the four top-level keys a species gains (`cell_type`, `cell_types`,
    `default_cell_type`, `modelled.record`);
  - the ladder;
  - citations, sources and classes;
  - the switch and the address;
  - what a view gets;
  - the clock;
  - what the other views say.
- **`schema/CELL_TYPES.md`:**
  - `cells.visualizer.cell_type@1`, with `extends` and `differs`;
  - a species' present `cell` block as its one default type, named by `cell_type` at the top
    level, since the present reader refuses keys inside `cell`;
  - the optional engine binding;
  - `loop`, which moves from `cell.loop`.

  **The lead's provisional answers, as the coordinator passed them on, written in and labelled
  provisional:**
  - a cell type is read as an engine definition: a declared structure plus a cited parameter set
    under `validation/`, with a stable id;
  - a `cell_type` label beside `species` in a looping run's block is passed to the run view's
    owner as an optional field.
- **`schema/MODEL_SYSTEMS.md`:**
  - `cells.visualizer.model_system@1`;
  - no organism keys;
  - `view.kind` with its fixed list of levels (`assembly`: molecules, assembly, population,
    lineage), `clock` as a label held to the runs' `time.base`, `runs` as files of the view's own
    format (`cells.visualizer.assembly_run@1`), and its heading.

  **The view builder's contract, `schema/ASSEMBLY_RUN.md`, came onto disk while this was written,**
  and this contract was matched to its "What the lens needs from an entry". It took that
  contract's runs (files in its own format, not packaged replays) and its clock word (`time.base`,
  `fission`). The one difference: this contract adds `view.kind`, where that one opens its lens on
  `kind: model system` alone. The table is in `schema/MODEL_SYSTEMS.md`.

## 4. The reader

`tools/lib/entries.py`, beside `tools/lib/species.py`, which it calls unchanged for the species
themselves.

- **Two entry points:** `read_entries(...)` reads the folders; `check(...)` takes what is already
  parsed, so a test writes no file.
- **What it does:**
  - each species gains its cell types: its own, then the files its `cell_types` names, with
    `extends` resolved and loops refused, and `default_cell_type`;
  - beside the species come the model systems, with their view's labels filled in;
  - every breach is one warning, and the entry is left out.
- **What it holds:**
  - the ladder and what each word asks of the record;
  - the citations against main's tracked files and the viewer's folder, where these are given;
  - the licence classes, read as the licence test reads them;
  - the cell types' shapes and framing, through the species reader's own methods;
  - the model systems' fixed levels, clock, runs and the keys an organism has and a model does
    not.

## 5. GARD's file

`data/models/gard.json`:
- **Its label and line:** "GARD assembly", "A model, not an organism", under "Origin of life".
- **Its view and levels:** `view.kind` `assembly`, and four levels, each with what it will show.
  The population level waits for a run of a population, since one lineage comes first. The
  lineage level says that the 0.9 line is drawn on the parent-to-daughter comparison only.
- **Its clock and its run:** its clock's base is `fission`. Its one run is
  `data/origin/example-run.json`, the view builder's example of invented numbers, with `kind`
  `example`. The reader holds it to the assembly run's format, to `model.id` `gard` and to the
  fission base. **That file was uncommitted when this was written,** so the two are committed
  together, or the example first.
- **What Cells models of it:** `proposed`, with "Nothing of GARD is in the engine", the user's
  request, and the record of main's two mentions.
- **Its facts:** three, each from the preprint as the viewer's note reads it (CC BY 4.0):
  - 100 molecule types;
  - in the preprint, growth to 80 molecules and then a split in two;
  - in the preprint, a fission inherited when H between the parent and the daughter that carries
    on is above 0.9, with 0.9 itself a break.

  The last two are labelled as the preprint's: the note's section 1.3 records that the original
  papers grow to 100 and give no threshold. The rule agrees with main's scientific basis.
- **Its words of main are quoted, not paraphrased:** "the preprint's GARD catalytic matrix and
  reservoir are fixed environmental constraints", and "GARD, Boolean regulation, and continuous
  biochemical equations need explicit contracts if supported".
- **What it does not hold:**
  - no name of the engine's proposed note;
  - nothing of the open finding that note holds. If it is ever mentioned, it is only as "the
    engine's note has an open finding on the published kernel, under review", and the viewer
    takes no view on it.

It is data only. No test asks the page to show it.

## 6. The hook-up, as steps

Apply each step when its files are free, in this order. Each leaves `npm test` green and the
cell-build numbers byte for byte.

1. **The species reader and its contract.**
   - **Do this once main has today's landing and the map has had its pass**, as the coordinator
     ruled; the step rebuilds the scene. These files are owned elsewhere: `tools/lib/species.py`
     (the mouse's agent was told not to change it without asking), `schema/SPECIES.md` (another
     agent's working copy is open) and `src/lenses/cell.js` (the motor's).
   - **`tools/lib/species.py`:**
     - `STATES` becomes the ladder: `generic`, `proposed`, `planned`, `designed`, `modelled`;
     - the table kept twice (its `NEEDS` and `ANIMAL_ORGANELLES`, and `cell_structures.js`'s
       `NEEDS` and `organelles()`) becomes one data file, `data/parts/structures.json`, read by
       both;
     - a small fault is mended: `where` is reused inside the appendage loop of
       `Reader.species()`, so a breach after the appendages is reported under
       `cell.parts.appendages[N]` instead of the file's name (seen in a scratch run).
   - **`src/lenses/cell.js`:** `MODELLED` gains "Planned, not modelled" and "Designed, not
     modelled", in the same step as `STATES`, because `tests/species_levels.test.mjs` holds the
     two equal.
   - **`schema/SPECIES.md`:**
     - the ladder replaces the three words, citing `ENTRIES.md`;
     - `cell.loop` gives way to the top-level `cell_type.loop`, since the reader refuses `loop`
       inside `cell`;
     - the four top-level keys are added.
   - **`modelled.record` becomes required for every species above `generic`.** The three species
     files that are `proposed` gain it, citing what their texts already cite:
     - `syn3a.json`: `docs/DECISIONS.md`, D173, and `docs/SYN3A_MINIMAL_CELL_TRACK.md`;
     - `mpneumoniae.json`: `docs/SYN3A_MINIMAL_CELL_TRACK.md`, section 9;
     - `ecoli.json`: `docs/DECISIONS.md`, D179.

     The generic species (human, mouse, planarian, fruit fly, thale cress) need none.
   - **Held by:** `tests/species_levels.test.mjs` (the contract names every word; `MODELLED` has
     a word for each), `tests/cell_structures.test.mjs`, `tests/cell_build.test.mjs` (numbers
     identical), `tests/entries.test.mjs`, and a new test that the structures table is the one
     both read.
2. **The extractor and the scene.**
   - `tools/extract_architecture.py` reads through `entries.read_entries(...)`, with new
     `--cells` and `--models` folders, `tracked=self.files` (main's `ls-files`) and
     `own=HERE.parent`.
   - The scene's species each gain `cell_types` and `default_cell_type`, and the scene gains
     `models`, beside `species`.
   - `species_held` may also hold a model system.
   - `tests/licence_classes.test.mjs` walks `data/cells/` and `data/models/`.
   - `npm run extract -- --strict`.
   - **Held by:** `tests/entries.test.mjs`, `tests/visualizer.test.mjs` (the scene's species and,
     new, its models), `tests/licence_classes.test.mjs`, and `tests/cell_build.test.mjs`. That
     test's first check compares the scene's species with the species files and stays as it is;
     its reading code changes in step 3.
3. **The lens takes a cell type** (`docs/CELL_TYPES_DESIGN.md`, step 6; after the motor's
   hook-up).
   - **`src/lenses/cell.js`:**
     - `setCellType(id)`;
     - `plan()` and `build()` read the cell type's levels, parts, capabilities and facts, and
       keep the species' organ and body;
     - a caveat for a planned or designed type, in the ladder's words;
     - `inType()` gives a capability's word in this cell beside its map status;
     - the species panel lists the species' cell types.
   - **`src/layers/cellflux.js`:** `loops` is keyed by `species.type`.
   - **The address** takes `cell=`.
   - **The tests' reading code moves to the default type** (`species.cell_types[0]` where they
     read `species.cell.parts` today): `tests/cell_build.test.mjs` (line 346 and `planned()`),
     `tests/flux.test.mjs` (`lensFor`), `tests/cell_scenery.test.mjs` and
     `tests/cell_structures.test.mjs`. **The numbers must not move.**
   - **Held by:** `tests/species_levels.test.mjs`'s "follow the species", extended to types;
     `tools/check_species.mjs`; the cell-build numbers.
4. **The switch learns a second kind of entry** (after the phone-layout pass, and once the model
   system's view exists to open).
   - **`src/ui/viewer.js`:**
     - `speciesChoices()` holds species and model systems;
     - `speciesRows()` gives a model system's row (its `is` line in place of an organism) under
       its `group`;
     - `setSpecies(id)` becomes `setEntry(id)`: a model system opens its own view, and choosing a
       species from there returns to the Cell view;
     - `state.entry` beside `state.species`;
     - the address reads `entry=`, `species=` and `atlas=`, and writes `entry=`.
   - **`MODELLED` moves to a shared module** for the switch's words.
   - **`tools/check_species.mjs`:** `WORDS` becomes the ladder's words; "a row for every species
     of the scene" covers its models.
   - **The Protein atlas** says "A model system has no proteins of a species".
   - **Held by:** `tests/species_switch.test.mjs`, `tools/check_species.mjs`, `input-species`,
     and a new test of a model system's row and its address.
5. **The cell-type control** (`docs/CELL_TYPES_DESIGN.md`, step 7), with the first second cell
   type.
   - Rows under a species that has more than one type. How they are shown is designed after the
     phone pass.
   - The guard "names no species in its code" extends to cell-type and model-system ids and
     labels.
   - **Held by:** `tests/species_switch.test.mjs`, `tools/check_species.mjs`, `flux-phone`.

**Every test that pins the list of species,** and what it needs:
- `tests/visualizer.test.mjs` (lines 263–264): unchanged for species; it gains its models.
- `tests/species_levels.test.mjs`: the reader's words, `MODELLED`, and the guard in step 5.
- `tests/species_switch.test.mjs`: rows.
- `tests/cell_build.test.mjs`: its first test is unchanged; its reading code changes in step 3.
- `tests/flux.test.mjs`: `lensFor`, in step 3.
- `tests/licence_classes.test.mjs`: its folders, in step 2.
- `tools/check_species.mjs`: `WORDS` and its rows, in step 4.

The rest read the scene's list as it is.

## 7. Uncertain, and for others to decide

- **The view builder's contract** (`schema/ASSEMBLY_RUN.md`) was read while it was still
  uncommitted. If it changes its entry section, `schema/MODEL_SYSTEMS.md`'s table follows it.
- **The lead's two provisional answers** reached me through the coordinator only; the record of
  main does not hold them.
- **`data/parts/structures.json`** is my proposed home for the one table of what a structure
  needs. `data/architecture/` is the map's, and `data/species/` and `data/cells/` are read as
  entries.
