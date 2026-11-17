# The Laws library: the list of the engine's declared pieces

Status: **fixed for the viewer, 16 November 2026**, for phase 1 of the Laws library. The user
chose the racks from the ideas page (`docs/LAWS_LIBRARY.md`, `docs/ideas/laws-library.html`),
and asked for it to be built "now", and then "use the engines manifest when those are ready".

The library is a view of its own. It shows every declared piece of the engine on a wall,
shelved by family: channel laws, junction laws, pumps, operators, kinds, solvers. In front
of the wall stand the frames, one for each model and what it declares. This file fixes the
list both are drawn from, and what may be said of each piece.

It is read from the engine's code, without running it. When the engine writes its
declarations manifest (D185), the list is made from that manifest instead. The tool then
changes; this contract keeps its fields.

## Files

| File | Made by | Holds |
| --- | --- | --- |
| `data/laws/pieces.json` | `tools/extract_laws.py` (generated: do not edit) | The pieces, the frames, the families and the stamp |
| `data/laws/overlay.json` | Hand (curated) | The viewer's words: families and shelves, the family of an identifier no rule places, the pieces design notes name, the frames' words |

```bash
python3 tools/extract_laws.py --ref origin/main                      # main as pushed (since the landing of 16 November 2026)
python3 tools/extract_laws.py --ref origin/main --candidate BRANCH   # and a working branch's pieces that main lacks
python3 tools/extract_laws.py --ref origin/main --out -              # to standard output
```

The tool reads through git (`git show`, `git ls-tree`, `git grep`) at a revision, so it
changes no checkout and writes nothing but its output. It parses Python with the viewer's
own static reader (`tools/lib/static_eval.py`) and imports nothing of `cells`.

## The stamp

```json
"stamp": {
  "generator": "visualizer/tools/extract_laws.py",
  "main": { "ref": "origin/main", "revision": "ab267c39", "date": "2026-11-16", "on_remote": true },
  "candidate": null,
  "landed": null,
  "records": { "scene_revision": "…", "inventory": "2026-11-12 (engine fec863f)" },
  "warnings": []
}
```

- **The main revision must be one others can find.** This is the map's extractor's rule, since
  06684552. Where the checkout read has a remote, the revision must be on a remote branch as
  last fetched. Otherwise the tool warns, and `--strict` fails. A checkout with no remote (a
  test's copy) is taken as it is.
- **A candidate is a working branch.** Working branches are not in the public repository until
  they land, so the candidate's revision is stated and never linked. Once the candidate is an
  ancestor of the main revision, it adds nothing: `landed` names it, and every piece is read
  from main.
- **Nothing in a piece changes between two readings of the same revisions.** The file holds no
  clock time.

## A piece

```json
{
  "id": "kv1p5_mh@1",
  "kind": "channel law",
  "where": "main",
  "family": "potassium",
  "read": {
    "ref": "origin/main", "revision": "ab267c39", "path": "src/cells/processes/voltage_gates.py",
    "found_by": "LAW_CODES table",
    "fields": { "code": 0, "permeant": [["K", 1.0]], "doc": "Pure continuous m/h kinetics in volts/seconds; no implicit preparation." },
    "also": ["src/cells/processes/cav_channels.py"]
  },
  "curated": { "family": "potassium", "family_by": "unit kind", "unit": "Kv1.5 channel", "unit_by": "the protein inventory of 2026-11-12 (engine fec863f)" },
  "declared_by": [{ "frame": "resolved_pump_tissue@3", "how": "direct" }, { "frame": "resolved_pump_composite@1", "how": "inner", "via": "resolved_pump_tissue@3" }],
  "status": null,
  "box": { "id": "laws.channels", "label": "Channel catalogue", "level": "established", "source": { "path": "docs/README.md", "where": "Models and execution" } }
}
```

- **`id`** is the engine's own `name@version`, or a namespaced `namespace.name@version`.
  Ids are unique in the file.
- **`kind`** is one of: `channel law`, `route law`, `route kind`, `junction law`, `pump law`,
  `release law`, `factor`, `read`, `fuel kind`, `kind`, `operator`, `solver`, `law`.
- **`where`** is `main`, `candidate` (on the landing candidate, not on main yet) or `design`
  (named in a design note; no code). A piece found on both main and the candidate is `main`.
- **`read`** is what the code says, with where it was read: the ref, the revision, the file,
  and which rule found it. Its `fields` are read from the code:
  - `code`, `permeant`, `gate_powers` and `gate_states` from the catalogue tables;
  - an operator's contract (`parts`, `provides`, `reads_declared`, `reads_current`, `writes`,
    `requires`, `heat`, `work`, `ledgers`, `step_method`, `schedule`);
  - a kind's own `pieces`;
  - `doc`, the first paragraph of the module's docstring, quoted as the module's own words.

  `read` is `null` for a `design` piece.
- **`curated`** is the viewer's: the family and how it was given (`family_by`: `family_of`,
  `unit kind`, `permeant ions`, `kind`, `rule` or `designed`), the unit the protein inventory
  says the law acts on, an operator's label from the Engine view, and the design notes that name
  a `design` piece (`named_in`, each with its path, its place and its ref: `main` or a
  development branch).
- **`declared_by`** lists the frames that declare the piece (below). Every entry names a frame
  of the file.
- **`registry`** and **`registered_in`** say where it stands registered (above). `read.fields`
  may add `provenance` (inner_laws' tag) and `unversioned` (an id with no version).
- **`status`** is a level only where a record states one for this piece, with that record. Today
  that means the operators, whose levels the Engine view's overlay records with their sources.
  It is `null` everywhere else, and the view says "No level recorded for this piece".
  - `level` is one of the Engine view's status ids, `label` its words, and `as_of` its date.
  - `source` is the record the level rests on (`path`, `where`), and `record` the line of the
    map that carries it.
  - No status is inferred, and none comes without a source.
- **`box`** is the Engine view's box that holds the piece's file, with that box's level and
  source. It is a status of the box, never of the piece, and the view says so. It is given only
  for pieces on main, and only where the box has a level and a source.

## What counts as a piece: the lead's provisional answers of 16 November 2026

The engine's lead answered the page's questions provisionally on 16 November 2026, through the
coordinator. The formal answers come with a later pass of the core. The file carries these
answers (`stamp.what_counts`), and the tool follows them:

- **A piece is what is registered:**
  - a law in `inner_laws`' tables;
  - a kind in the kind registry;
  - an operator in `OPERATORS`;
  - a model by its `MODEL_ID` (the frames).

  Each piece says where it stands registered (`registry`, below).
- **The older families' laws count.** They stand on their own part of each shelf, marked as in
  an older family. The user chose this on 16 November 2026. A law named only by a constant
  (`no registry`) stands on that upper part too, with its own words.
- **Solvers and step methods count**, an operator's `STEP_ID` among them. `rk4` has no version. It is shown as it is (`unversioned`),
  and the manifest's design is to close that gap. No version is given to it.
- **A kernel in the code that no kind imports is not a piece yet.** It becomes one when
  registered. The overlay names such kernels (`not_registered`), and the file keeps them in
  `unregistered`, apart from the pieces. They are never counted, never drawn on the wall, and
  each carries the words "In the code, not registered: not a piece yet".
- **`provenance` in `inner_laws`** (today always `"parity"`) is a source tag and not a level. It
  is read as `read.fields.provenance` and said as that. How a moved piece names the frozen
  original it came from is the core's to specify.

`registry` is one of:

| Value | Means |
| --- | --- |
| `inner_laws.py` | Named by a table or constant of `src/cells/models/inner_laws.py` (`registered_in` gives which) |
| `the kind registry` | A built-in kind, registered as an outside package would be |
| `a registered kind` | One of a registered kind's own pieces (`registered_in.kind`); the page's reading of "what is registered" |
| `OPERATORS` | An operator of the composite's registry |
| `a registered operator` | A law named in a registered operator's own module (`registered_in.operator`); the page's reading |
| `the inner model's structure` | Named by the inner model's own declarations outside `inner_laws` (its heat booking) |
| `a solver or step method` | A solver or step method |
| `an older family` | A law of the older families' channel catalogue: a `LAW_CODES` table inside its own module, until a use moves it (D167) |
| `no registry` | A constant named for a law that no registry the tool reads holds: shelved by the page's reading until the manifest says what it is |

A `design` piece has `registry: null`.

## How a piece is found

Each rule reads the code at a revision. A rule's name is the piece's `read.found_by`.

1. **Catalogue tables.** Every `LAW_CODES` dictionary of a module in `src/cells/processes/`
   gives channel laws, each with its registry code and, where the module has them, its
   `LAW_PERMEABILITIES`, `GATE_POWERS` and `STATE_COUNTS` entries. A code used by two
   identifiers is a warning.
2. **The operator registry.** `OPERATORS` in `src/cells/models/operators/__init__.py`, each
   operator's `LAW_ID` and its contract declarations.
3. **Kinds.** Each module of `src/cells/models/inner_kinds/` with a `KIND_ID`. A kind's own
   pieces are the `LAW_ID` and `READ_ID` of the processes modules it imports, and its
   module-level constants whose value is an identifier.
4. **Named constants.** The module-level constants of `src/cells/processes/`, `numerics/`,
   `coupling/`, `core/` and `models/` (but not `models/operators/`) whose value is an
   identifier and whose name says what it names:
   - a name with `SOLVER` or `METHOD` in it, or `ARS222_ID` or `EULER_ID`, is a solver;
   - a name with `LAW` in it is a law;
   - `READ_ID` is a read;
   - `KIND_ID` in `processes/` is a route kind.

   Other identifiers (random streams, stage domains, schema ids) are not pieces. The form
   `name@version` alone does not say what a thing is.
5. **The inner model's declarations.** The pieces @3 declares (below) that no rule above
   found.
6. **The protein inventory.** A law of the inventory's snapshot that no rule found, where its
   identifier stands as a string in `src/cells` at the revision.
7. **Designed.** The overlay's `designed` pieces, each named in a design note. None of them may
   stand in the code: if one does, the tool warns, and the code's reading wins.

A piece whose identifier names a reference simulator is never listed. A reference simulator is
no piece of Cells. Quoted docstrings may name one as the source of a law's coefficients.

## A frame

```json
{
  "id": "resolved_pump_tissue@3",
  "kind": "inner model",
  "read": { "ref": "origin/main", "revision": "ab267c39", "path": "src/cells/core/surface_pump_v3_spec.py", "found_by": "MODEL_ID" },
  "rows": [
    { "label": "Channel laws", "pieces": ["kv1p5_mh@1", "…"], "next_code": 5,
      "read": { "path": "src/cells/models/inner_laws.py", "name": "CHANNEL_LAWS", "ref": "origin/main", "revision": "ab267c39" },
      "codes": { "kv1p5_mh@1": 0, "…": 4 }, "codes_read": { "path": "src/cells/core/surface_pump_v3_spec.py", "name": "LAW_CODES" } }
  ],
  "boxes": [{ "id": "models.pump_tissue", "level": "qualified", "label": "…", "as_of": "2026-11-10", "source": { "path": "PROGRESS.md", "where": "…" } }]
}
```

- **`kind`** is `inner model`, `composite`, `composition` or `older family`.
- **The inner model's rows** are read from `models/inner_laws.py` where the revision has it:
  - its channel, junction and pump registries;
  - its route ids and its fuel kind;
  - its heat booking (`TRAPEZOID_JUNCTION_HEAT`);
  - its built-in kinds, and its family's `SOLVERS`.

  Each row says the ref it was read at. Where main has no `inner_laws.py` (before the landing of
  16 November 2026), the rows come from the candidate, and main's closed table stands beside
  them (`closed_on_main`). `codes` are the inner model's own registry codes (`LAW_CODES` of
  `core/surface_pump_v3_spec.py`), a registry apart from the older families' catalogue codes.
  `next_code` is the next free one: a new channel law takes it, and no code is reused.
- **The composite's row** is the operator registry: any ordered subset of it is a definition
  (`any_order`).
- **A composition's row** is curated: the operators of the blocks that `frozen_definition`
  moves into the operator list, with that source.
- **An older family** has no rows. Its laws are a table inside its own module, and they become
  declared pieces as each moves into the one model, when a use needs it (D167).
- **`boxes`** are the Engine view's boxes for the model, with their levels and sources. A
  frame's status never comes from its parts: "integration grants no acceptance"
  (`development_status`, read from `core/pump_composite_spec.py`).

## What declares a piece

`declared_by` has one entry for each frame, with `how`:

- **`direct`**: a row of the frame names the piece;
- **`kind`**: the piece is one of a kind's own pieces, and a row names the kind (`via`);
- **`inner`**: the frame holds the inner model (`via`), and the inner model declares the piece
  directly or through a kind.

The view lights exactly these when a piece is chosen: its slots in each frame, and for `kind` and
`inner` the slot of the kind or the block of the inner model it comes through.

## Sources and links

Every source here is the engine's own record (its code and documents, under the project's MIT
licence) or the viewer's own data. No third-party source is read.

A file on main may be linked at the map's source address. A file read on a candidate or a
development branch, and a design note on a branch, is named in words and never linked: those
branches are not in the public repository until they land.

## What the view may say

- What a piece computes is its module's docstring, quoted. The view writes no physics of its own.
- What it declares is `read.fields`. What it acts on is `curated.unit`, as the inventory's.
- Its status is `status`, or "No level recorded for this piece". A `box` is said as the box's.
- Every count the view shows is counted from this file.
- The revision the list was read at is written on the picture itself, on the wall's foot, with
  the date it was committed.

## What the view's marks may stand for

Each visual difference in the room stands for one thing the list says, and the legend names
each one that is drawn (`MARKS` in `src/lenses/laws.js`, with a swatch for each in
`src/lenses/laws_styles.js`):

- solid slate: on main; a dark band: on the landing candidate; a glass outline: named in a design
  note, with no code;
- a narrower bar higher on its shelf: an older family's law, or a named law in no registry;
- a column's height: the family's count; a rack: a model; a card in it: a piece it declares; a
  block across its head: the inner model it holds; an empty socket marked "free": a row's next
  free registry code, with no piece;
- a small box on the plinth: an older model family;
- forward and faint: what a search or a filter finds and does not; a faint bar: an empty place,
  in a test of size only;
- blue light: what is chosen, the slots that declare it and the routes between. Only these are
  marked to glow, and bloom is on only while something is chosen. In the light theme a lit card
  keeps a face that reads as a card, drawn toward the accent, and its edges and its rack's rails
  shine; in the dark theme the card shines whole. Both mean the same thing.

Nothing else differs. The glass, rails, planks, dividers, sockets and plinth are the room. No
mark is dashed (on the page's other views a dashed outline is how the planned status looks). The
colours are the page's own tokens: its neutral (`--ghost`) for the pieces, its plate and edge
for the room, and its accent for what is chosen. No status token (`--st-*`) is used. The accent
is near the blue of the landed status, and the neutral near the grey of the established status;
the legend names both, and a status is said only in the panel, with its source.

## On the map's page

The page carries this file in its scene as `laws` (`tools/lib/build_page.mjs`), and the viewer
offers the Laws library as its fifth view only when it does.

- **The address.** `lens=laws` (or `#laws`) opens it. `select=laws:<id>` opens it on a piece or
  a frame, from any view.
- **The door from the Engine view.** An Engine view box that holds the files of pieces of this
  list (a piece's `box`) has a door, "Show its N pieces in the Laws library", with N counted
  from this file. It opens the library with those pieces picked out; the card says so, and its
  Close lets them go.
- **The way back.** A piece's panel links its box, and a frame's panel its boxes, under "On the
  Engine view". The link opens the Engine view on the box.
- **The card** has the search field, the Family control and "Where it stands" (only where a
  piece stands today). The keys `]` and Page Down step to the next piece, `[` and Page Up to the
  one before; the arrow keys turn the camera, as on every view.
- **The room** is kept clear of the cards on the left on a wide window (a left inset), and the
  names written on it come back with a lost context or a lost graphics process.
