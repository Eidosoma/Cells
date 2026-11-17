# The Laws library: the engine's declared pieces, as its declarations manifest gives them

Status: **format 2 (`cells.visualizer.laws@2`), 17 November 2026.** The Laws library reads what
the engine declares from the engine's declarations manifest alone. Format 1 read the engine's
code at fa19d80c and is replaced whole. The lead ruled on 17 November 2026 that the declarations
file is the whole truth of what the engine declares, and that what no active registry declares
comes off the wall.

The library is a view of its own. It shows every piece the engine declares on a wall, shelved
by interface: channel, cycle, route and junction laws; kinds; the composite's operators by their
part of the step. In front of the wall stand the racks, one for each active model with rows,
each piece in its slot; a model family with no rows stands as a closed case on the plinth. This
file fixes the list they are drawn from, and what may be said of each piece.

## Files

| File | Made by | Holds |
| --- | --- | --- |
| `data/engine/declarations.json` | The engine's own command, copied unchanged (`data/engine/README.md`) | The manifest, `cells.declarations@2`: the input, and the tests' oracle |
| `data/laws/pieces.json` | `tools/extract_laws.py` (generated: do not edit) | The manifest's pieces and models, each carried unchanged, with the viewer's layer |
| `data/laws/overlay.json` | Hand (`cells.visualizer.laws_overlay@2`) | The viewer's words: the families and shelves, the models' short names and Engine view boxes, the laws design notes name |

```bash
python3 tools/extract_laws.py              # data/engine/declarations.json -> data/laws/pieces.json
python3 tools/extract_laws.py --out -      # to standard output
```

The manifest's format is the engine's page `docs/library/DECLARATIONS_FORMAT.md`: that page and
the manifest's `kind` are the contract. The tool reads nothing of the engine's source, imports
nothing of it and runs nothing of it. Making the list again from the same manifest and overlay
gives the same bytes (a test holds it).

**The reader refuses** (exit status 2, nothing written):
- a manifest whose `kind` is not `cells.declarations@2` (another major, or not a declarations
  manifest);
- a manifest whose tree was not clean (`dirty` not false);
- a manifest whose `revision` is not a full Git revision.

The view's `Library` (`src/lenses/laws_data.js`) refuses a list read from another major or from
a tree that was not clean as well.

## The stamp

```json
"stamp": {
  "generator": "visualizer/tools/extract_laws.py",
  "read": "Read from the engine's declarations at main 7538b0cd",
  "manifest": { "path": "data/engine/declarations.json", "kind": "cells.declarations@2", "revision": "<40 hex digits>", "short": "7538b0cd", "dirty": false, "origin": "git checkout" },
  "overlay_as_of": "2026-11-17",
  "boxes": "data/architecture/overlay.json: the Engine view's components, matched to each piece's module_path"
}
```

The manifest states no date, and the view writes none.

## A piece

```json
{ "id": "kv1p5_mh@1", "family": "channel", "where": "declared", "box": { "id": "laws.declarations", "label": "Laws as declared pieces" }, "declared": { "...": "the manifest's piece, unchanged" } }
```

- **`id`** is the piece's `declared_id`, the spelling its declaration uses. The page's id is
  `laws:<id>`. Either spelling names the piece (the format page's ID rule, D185): an address
  `laws:cells.kv1p5_mh@1` opens `kv1p5_mh@1`, and
  `laws:atp_driven_transporter_mass_action_positive@1` opens
  `cells.atp_driven_transporter_mass_action_positive@1`.
- **`family`** is the viewer's shelving: the first overlay family whose `match` the piece meets
  (its `piece`, its `interface`, an operator's `fields.parts`). A piece no family takes is
  refused.
- **`where`** is `declared` for every piece of the manifest, `design` for a law a design note
  names (below).
- **`box`** is the Engine view's box whose path globs match the piece's `module_path` (the map's
  own record, `data/architecture/overlay.json`), or null. It names the box and carries no level.
- **`declared`** is the manifest's piece, unchanged. Nothing else of the list says what a piece
  is.
- **No `status`** is added. A level is shown only where the manifest's `status` gives one, with
  its `status_source`. At main 7538b0cd none does.

### A law a design note names

```json
{ "id": "fast_sodium_m3hj@1", "family": "design-channel", "where": "design", "box": null, "declared": null, "kind": "channel law",
  "named_in": [{ "path": "docs/HUMAN_CARDIAC_LAWS_DESIGN.md", "section": "2. The law set for a human ventricular myocyte", "line": 168 }] }
```

It is not declared, and it stands on a shelf apart, in glass. It is kept only while its note
still names it on that line at the manifest's revision (a test asks the main checkout where it
is there). A design note's law that the manifest declares is refused: it is a declared piece.

## A model

```json
{ "id": "resolved_pump_tissue@3", "short": "@3", "boxes": [{ "id": "models.pump_tissue", "label": "…" }], "declared": { "...": "the manifest's model, unchanged" } }
```

The view draws a model with rows as a rack, its rows grouped by role in the manifest's order:
- **the inner model:** channel laws by code, with its `next_code` as the empty socket marked
  "free"; its junction law; its cycle laws; its route laws; a fuel kind (a row whose `piece` is
  null, drawn as an empty socket with its ID and "no piece"); its kinds by definition key;
- **the composite:** its operators, in ID order, and the inner model whose pieces the manifest
  lets it declare, as a block;
- **a composition:** its inner model, as a block, then each operator by position.

A family with no rows is a closed case on the plinth. `short` and `boxes` are the viewer's.

### What declares a piece

From the models' rows alone: a row of its own (`direct`); the kind that hosts it, where that
kind is a row (`kind`); or the inner model a model holds, where the piece is of that inner
model's family (`inner`). Every model the piece's `models` names declares it in one of these
ways.

## The three meanings of null, and what the panel says

The panel says what the manifest states of a piece, in plain words, and no more. A piece key
that is null is said by its meaning (the format page, "The three meanings of null"):
- **not applicable** (the key does not apply to that kind of piece): nothing is said;
- **not extracted** (the pair (its `interface`, the key) is in `not_extracted`): "not yet
  extracted in the engine's declarations";
- **not stated** (otherwise): "not stated".

An empty list or object says "the declaration lists none". A nested null keeps the meaning the
format page gives its field: `rk4_step_s` null is "none: a law with no gate"; `stage_term`,
`loop_term` and `step_method` null are "none". `declared_host` null says the host is not stated
as a registered model, kind or operator; a null `module_path` says the module is outside the
`cells` package, and nothing is linked.

The panel says, of a declared piece:
- its ID (and the spelling it is declared with), interface, host, family and models;
- where it is declared: `module_path` and `line`;
- its kernels, each with its file;
- its provenance: the tag in the format page's words ("moved from an older family (moving is
  not calibrating)", "cited", "calibrated"), what it rests on, and a citation's source, place,
  licence and departures, with its works (each a link to its DOI or URL, opening outside the
  page);
- its test; its reads with mode and stage; what it changes, owns, writes, provides and controls;
  its ledgers and energy; its units and signs; an operator's requirements; a kind's laws;
- the rest under `fields`, by the format page's section for its interface;
- its status ("not stated" today) and its page (`doc`: "none given yet" today).

## Sources and links

Every source is the engine's own record or the viewer's own data; no third-party source is read.

- **The manifest's revision.** A file the manifest names (a piece's `module_path`, a kernel's, a
  model's, a page in `doc`, a design note's) links at `stamp.manifest.revision`, in the
  repository of the scene's `source_base_url`: the file is there by construction. Where the
  map's revision is another, the words beside the link say so ("line 93, as declared at main
  7538b0cd"). The link names the file; the line is said in words.
- **Not linked.** No page is linked while the manifest gives none, and no file outside the
  package is linked.
- **The Engine view's boxes** are linked only where the page draws them, and no level of a box
  is said.

## What the view's marks may stand for

Each visual difference in the room stands for one thing the list says, and the legend names
each one that is drawn (`MARKS` in `src/lenses/laws.js`, a swatch for each in
`src/lenses/laws_styles.js`). Its counts are the manifest's.

- solid slate: declared by the engine; a glass outline, on a shelf apart: named in a design note,
  not declared;
- a column's height: the family's count; a rack: a model with rows; a card in it: a piece that is
  a row of the model, with its code, key or position written under it; a block across its head:
  the inner model it holds; an empty socket marked "free": the inner model's next free channel
  code; an empty socket with a name: a row with no piece of its own;
- a closed case on the plinth: a model family with no rows;
- forward and faint: what a search or a filter finds and does not; a faint bar: an empty place,
  in a test of size only;
- blue light: what is chosen, the slots that declare it and the routes between.

Nothing else differs. The glass, rails, planks, dividers, sockets and plinth are the room. No
mark is dashed, and no status token (`--st-*`) is used.

## The wall's layout

The overlay's shelves name a `band`; on a wide screen each band is a row of columns, and a shelf
marked `apart` stands a gap away from the shelves before it. On a tall screen the shelves break
into bands of at most six families, a shelf never split. A family with no piece is not drawn, and
a long family name is written smaller so that it fits its column. Today all four shelves stand
on one band: the laws of the inner model, the kinds, the composite's operators by their part of
the step (split, event and split, event, process, no part), and, apart, the laws named in design
notes.

## What the wall does not show

- **The older model families** of the manifest's `legacy` list are not drawn. The List names them
  by ID, as the manifest gives them, under "Not shown: the older model families (legacy code, to
  be dropped)". An address naming one opens the notice: "The engine's declarations list <id>
  among the older model families: legacy code, to be dropped, with no page of its own. The map
  does not show it."
- **Any other ID** an address names, a piece of an older list included, opens: "The engine's
  declarations do not list <id>: no active registry declares it, so the map does not show it."
  It is never called legacy unless the manifest's `legacy` names it.
- **A row with no piece of its own** (the fuel kind) is drawn as its socket; its address opens
  what the model says of it and the cycle laws that run on it.

## On the map's page

The page carries this file in its scene as `laws` (`tools/lib/build_page.mjs`), and the viewer
offers the Laws library only when it does.

- **The address.** `lens=laws` (or `#laws`) opens it. `select=laws:<id>` opens it on a piece, a
  model or a notice, from any view.
- **The doors.**
  - An Engine view box that holds the files of declared pieces: "Show its N declared pieces in
    the Laws library", which picks them out; the card says so, and its Close lets them go.
  - An Engine view operator (`op.<id>`) the manifest declares: "Open <id> on the Laws library's wall".
  - A unit of the Protein atlas: for each law its panel names, "Open <id> on the Laws library's
    wall" where the manifest declares it, and one line, which opens nothing, for those it does not:
    "No active model declares these laws of this unit: <ids>. The engine's declarations do not
    list them, and the Laws library does not show them." (in the singular for one).
- **The way back.** A piece's panel links its box, or an operator's own part, and a model's
  panel its boxes, where the page draws them.
- **The card** has the search field, the Family control and "Where it stands". `]` and Page Down
  step to the next piece in the wall's order, `[` and Page Up to the one before.
- **The room** is kept clear of the cards on the left on a wide window, and the names written on
  it come back with a lost context or a lost graphics process.
