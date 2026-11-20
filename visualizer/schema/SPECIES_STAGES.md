# Species stages: a species' life stages, and the spans between them

Status: **proposed for the viewer, 19 November 2026.** On that day the user chose that a species
may carry life stages, shown as a strip in the Scope view, and asked that the design carry a
later use in which development is played along the strip, from one cell to the whole animal.
The reader is `src/scene/life_stages.js`, held by `tests/life_stages.test.mjs`; the species reader
(`tools/lib/species.py`) asks it, through node, and the Scope view shows the strip. The check is
`tools/check_stages.mjs`, on a check-only scene with a made-up species
(`tests/fixtures/stages/species/dewkin.json`). **No species file of the page carries the block yet.**

This is a note of its own, beside `SPECIES.md`, because the block is optional and every rule of
`SPECIES.md` holds unchanged for a species without it.

A stage is the viewer's data, as the species file is. Nothing in it says that Cells models an
organism, an embryo or development: what the project's record says of a stage is its `modelled`,
held to the same ladder as a species' (`ENTRIES.md`).

## The block

An optional top-level `stages` in `data/species/<species id>.json`. Every name, number and source
below is made up.

```json
"stages": {
  "system": {"id": "ds", "label": "Dewkin stage", "short": "DS", "sources": ["made"]},
  "times_after": "fertilisation",
  "opens_on": "egg",
  "list": [
    {
      "id": "egg", "order": 1, "index": "1", "label": "Egg",
      "plain": "The made-up egg, before its first division.",
      "ends_at": "cell",
      "no_further_levels": "An egg is one cell: it has no tissue, organ or body yet.",
      "levels": [
        {"id": "cell", "label": "The egg", "shape": {"kind": "sphere", "across_um": 900},
         "note": "A made-up egg, 900 µm across.", "sources": ["made"]}
      ],
      "cell": {
        "facts": [{"label": "Diameter", "value": "900 µm (made up)", "sources": ["made"]}],
        "capabilities": {"cap.junctions": {"place": "absent", "why": "One cell has no neighbour."}}
      }
    },
    {
      "id": "two-cell", "order": 2, "index": "2", "label": "Two cells",
      "time": {"value": 80, "unit": "min", "about": true, "temperature_c": 20,
               "sources": ["made"], "where": "a made-up table, row 2"},
      "missing": "No size of the two-cell form is in hand under usable terms."
    },
    {"id": "adult", "order": 3, "label": "Adult", "own": true}
  ],
  "spans": [
    {"from": "egg", "to": "two-cell", "fill": {"kind": "prescribed", "run": "made-up-division"}}
  ]
}
```

## Rules

- **A species without the block is read exactly as before**, by every reader and on every view: no
  strip, no `stage=`, nothing else changed. A block that breaks a rule below is refused as a whole
  (each breach with its own code: `order-gap`, `number-unsourced`, `span-not-neighbours`, …); the
  species is then read as if it had none, and a strict build fails on the warning.
- **`list`** holds two stages or more. Each has:
  - `id`, a plain id of lower-case letters, digits and hyphens, once in the list;
  - `order`, a whole number: the stages stand at 1, 2, 3 … with no gap and none twice;
  - `label`, its name, and `short` (optional, at most 18 letters) for a narrow screen;
  - `index` (optional), the species' own index for it, as text, as its staging system writes it
    (`"2"`, `"35-36"`). It needs `system`. Where two stages' indices begin with a number, the
    number rises with the order;
  - `time` (optional): `{value, unit, about, temperature_c, sources, where}`, after the event that
    `times_after` names (one for the whole strip). `value` is a number above nought or a rising
    range of two; `unit` is `s`, `min`, `h` or `d`; `temperature_c` the temperature the source
    states it at; `where` the place in the source. A time is kept only as its source states it,
    after that event: a time a source gives from another event (twenty minutes after the first
    division) is not summed into one; it goes into the stage's `note` in the source's words;
  - `plain` and `note` (optional), sentences; `sources` (optional), the keys of the species'
    sources that give its name and its index, where the system's do not;
  - `modelled` (optional, not on the file's own stage): what the project's record says of the
    species at this stage, held to the ladder and its record as a species' `modelled` is (the
    entries reader, `tools/lib/entries.py`, checks its citations as it checks the species'). Left
    out, the species' own word stands, and the page says that it is the species'.
- **Exactly one stage is the file's own** (`"own": true`): the form the species file describes.
  It states nothing over the file (no level, no cell, no cell type, no `modelled`).
- **`opens_on`** (optional) names the stage the species opens on, which must be one that is drawn
  (`opens-on-unknown`, `opens-on-named`). Left out, the species opens on its file's own stage, so
  that adding a block changes nothing a visitor sees until another stage is chosen. A species may
  so open on its egg while its file describes the adult.
- **A stage named and not drawn** gives `missing`: in a sentence, what is not in hand (a size under
  usable terms, say). It may give its name, index, time, notes and `modelled`, and nothing to
  draw. It stands on the strip, says what is missing, and cannot be entered. **Nothing is invented
  to fill a stage.**
- **A drawn stage states only what differs from the file**, and at least one level, an end or a
  cell of its own:
  - `levels`: levels in the species file's own shape (`SPECIES.md`, `SPECIES_SHAPES.md`), each
    replacing the file's level of the same id whole. A level it does not give is the file's own.
  - `ends_at` (optional): the stage has no level above this one (`cell` for an egg). It gives no
    level above it. Where the stage then lacks a tissue, organ or body, `no_further_levels` (its
    own, or the file's) says so; a stage with every level carries no such sentence.
  - `cell`: `facts`, `parts` and `capabilities`, as the file's `cell` block. `facts` and `parts`
    each replace the file's whole; `capabilities` are taken place by place over the file's, and
    `capability_sources` likewise. **A stage that draws a cell of its own gives its own `facts`**
    (an empty list where it states none): the file's facts are of another form. One that gives no
    `parts` is drawn with the file's cell's parts, and the page says so.
  - `cell_type`, `cell_types`, `default_cell_type`: as at the top of a species file. **A stage
    that leaves the cell alone** (it gives no cell or tissue level, no `cell`, no end and no cell
    type) keeps the species' cell types whole, with their looping run. **One that changes the
    cell has a cell type of its own** (named by its `cell_type`, or "Its cell"), and of the
    species' other types only those it names in `cell_types`, each one the species names in its
    own; a looping run is its own type's `loop` alone.
- **Every number a stage states has its source and is no invention:**
  - a level's shape names its sources (keys of the species' `sources`); the level's `note` says
    which of its sizes are the picture's choice, as a species' does;
  - a time names its sources and the place in them;
  - a fact names its sources;
  - the parts' sized blocks (`organelle_sizes`, `envelope`, `proteins`, `ribosome`, `appendages`)
    carry theirs as `SPECIES_SHAPES.md` asks;
  - framing numbers (`view`, `fade_in_um`, `fade_out_um`, `centre_um`, `label_um`, `sheet_mark`,
    a note's `at_um`) are the picture's and need none.
  Every source a stage cites is among the species' `sources` and of the class `permissive`
  (`SPECIES.md`, D173): nothing is taken from another.
- **`system`** (needed for an index): `{id, label, short, sources}`, the staging system the
  species' stages are counted in, with the sources that give it. `short` is written before an
  index on the strip ("DS 2").
- **`spans`** (optional): `{from, to, fill, note}`. A span lies between two stages that follow each
  other in the order (`to` stands at `from`'s order plus one), once for each pair. Its `fill` is
  `{kind, run, note}`, `kind` one of:
  - `illustrative`: the viewer's own drawing, never a run. It names no run. This is also what
    fills, without being written, every span between one drawn stage and the next drawn one that
    no run fills: one plain change from the one stage's picture to the next, passing any named
    stage between. A span written `illustrative` adds only its `note`; it must lie between two
    drawn stages, with only named ones between them.
  - `simulated`, `modelled` or `prescribed`: the frames of a saved run, named by `run`, its id in
    the page's catalogue of runs. The word is the run's own word for the layer that gives the
    span its geometry (`RUN_VIEW.md`, `layers[].representation`). Until a run's view says which of its
    layers gives the geometry, the page holds the word to those its layers give (one of them must
    be it, or nothing is drawn and the reason is given), and says the run's word. The Scope view
    does not draw a run's frames yet: while its span plays, the picture gives way and says what
    plays. A run fills a span between the times the run itself states for the
    span's two stages (a preparation card in the run's view: proposed to the engine's side, not
    yet in `RUN_VIEW.md`); the viewer never reads a stage from a run's state. Where the run is not at hand,
    nothing is drawn and the reason is given: illustration does not stand in for it.
  A stretch with no drawn stage on one side, and no run, is empty, and says so.
- **Not yet in this contract:** keyframes from a declared source (a `prescribed` fill without a
  run, each keyframe a picture stated as a stage states one, with its sources, played as a run's
  records are), named regions on an outline and intervention sites. They are proposed, and a block
  that gives them is refused until this note takes them in.

## The strip

- The strip is **the stages' order, evenly**: each stage one step, whatever time lies between, so
  that no place on it is invented. A stated time is written on its mark ("about 80 min after
  fertilisation, at 20 °C"), never used to place it. Between two stages whose times are stated at
  one temperature the page may say how long lies between them, worked out by the viewer from the
  two stated times, and says so.
- A drawn stage can be entered; a named one cannot. The page opens on the stage `opens_on` names, else on the file's own.
- A visitor goes from one drawn stage to another by pressing its mark on the strip, or by the
  keyboard; the press makes the viewer's plain change (four seconds, the picture's choice). The
  strip is one clock (`journeyOf`), and **its play control shows only where a saved run fills a
  span**: play then plays that run's span at the speed its replay opens at, and stops where it
  ends. Playing the viewer's own change along the strip is built and held by the tests, and is
  switched off in the Scope view (`PLAIN_CHANGE_PLAYS` in `src/lenses/cell.js`) until the user has
  seen it. Its words never say "true speed". Every stretch and every layer
  in it says its kind: "Illustration: not a run", "Simulated by a run of the engine", "Modelled in
  aggregate by a run of the engine", "Prescribed by the run's caller: not grown in the run", or
  "Nothing is drawn here" with the reason. Nothing is shown as growth that emerged.

## The address

`stage=<id>`, kept with the species (`entry=<species>&stage=<id>`). It is written only for a drawn
stage that is not the one the species opens on. A named stage in an address opens that stage's card
at the stage the species opens on; a stage the species does not have is passed over, and the next address written
leaves it out. Choosing another species leaves the stage behind.

## What reads it

- `src/scene/life_stages.js`: the block held to the rules of the stages themselves (ids, the
  order, the own stage, named and drawn stages, levels, ends, facts, times, the sources cited and
  their class, the spans and their fills); the species read through a stage, as a file gives it
  and as the scene carries it; the strip; the spans' players; the address.
- `tools/lib/species.py`: carries the block into the scene where it is sound. It asks the reader
  above, through node (one call for each species with stages), so the block's rules and the
  read-through exist once; and it holds the species read through each drawn stage to `SPECIES.md`
  and `SPECIES_SHAPES.md` like any species file, so the shapes, the parts and their sized blocks
  are checked there and not twice. A refused block, a stage whose species breaks the contract, a
  missing node or a reader that throws each give a warning naming the species (and the stage), and
  the species is carried without its stages. The outlines a stage's levels name are carried with
  the species' own.
