# The Laws library: the engine's declared pieces, as its declarations manifest gives them

Status: **format 2 (`cells.visualizer.laws@2`), 17 November 2026.** The Laws library reads what
the engine declares from the engine's declarations manifest alone. Format 1 read the engine's
code at fa19d80c and is replaced whole. The lead ruled on 17 November 2026 that the declarations
file is the whole truth of what the engine declares, and that what no active registry declares
comes off the wall.

## Navigating the library

The opening star atlas gives each family a pod. Each piece has a fixed position within its family, derived from its ID. A solid star marks a declared piece and an open ring marks a design note. Highlight a model to light its members in place. A family label then gives its highlighted and total counts. Selecting a family brings its stars and names into view. Its connection map aggregates explicit cross-family relationships and lists the declarations behind each arc. Following a listed relationship opens its piece trace. Search and the family selector reach every piece, including those whose labels overlap.

Select a piece and choose a relationship to draw its recorded neighbours. Following a link moves the camera along its arc and adds a stop to the breadcrumb. Travelled links stay amber. Selecting an earlier stop restores its neighbours. For example, Site occupant replacement requires Scheduled cell replacement, which reads membrane area. Fields and model references appear at the end of the declaring piece’s links. A read that names a current piece lands at that piece, and its reverse appears under Read by. The field inspector can lead to another operator when the Engine map explicitly lists the edge and its field at the same revision. An empty or unextracted declaration retains the explanation in its inspector. The positions, arc lengths and navigation pulse have display meaning only.

Compare models opens a matrix with one row per piece in the two models. It distinguishes direct declarations and membership through an inner model or host kind. Filter to shared or exclusive pieces, or select a row to trace its connections. The address preserves the model pair, family, traced piece and mapped Scope or Engine entrance. A shared flight includes its selected relationship in `lawRelation` and up to its most recent 40 links in `lawTrail`. The viewer checks each link against the loaded declarations before restoring it. The earlier model-and-family bridge layout is available at `?lens=laws&lawLayout=atlas` and the shelf layout at `?lens=laws&lawLayout=shelves`.

Scope entrances use an explicit `shown_as` edge from an inventory unit to the selected capability, followed by an exact declared law named by that unit. The atlas identifies the contributing unit in the piece inspector. The inventory mapping describes a catalogue relationship.

The original shelf and rack drawing is available with `?lens=laws&lawLayout=shelves`. Its rack slots, free codes and other marks are described below.

## Files

| File | Made by | Holds |
| --- | --- | --- |
| `data/engine/declarations.json` | The engine's own command, copied unchanged (`data/engine/README.md`) | The manifest, `cells.declarations@3`: the input, and the tests' oracle |
| `data/laws/pieces.json` | `tools/extract_laws.py` (generated: do not edit) | The manifest's pieces and models, each carried unchanged, with the viewer's layer |
| `data/laws/overlay.json` | Hand (`cells.visualizer.laws_overlay@2`) | The viewer's words: the families and shelves, the models' short names and Engine view boxes, the laws design notes name |
| `data/laws/law_port.json` | `tools/extract_law_port.py` (generated: do not edit) | The law-port inventory's table (`cells.visualizer.law_port@1`, below): what a unit of the Protein atlas says of a law no active model declares |

```bash
python3 tools/extract_laws.py              # data/engine/declarations.json -> data/laws/pieces.json
python3 tools/extract_laws.py --out -      # to standard output
```

The manifest's format is the engine's page `docs/library/DECLARATIONS_FORMAT.md`: that page and
the manifest's `kind` are the contract. The tool reads nothing of the engine's source, imports
nothing of it and runs nothing of it. Making the list again from the same manifest and overlay
gives the same bytes (a test holds it).

**The reader refuses** (exit status 2, nothing written):
- a manifest whose `kind` is not `cells.declarations@3` (another major, or not a declarations
  manifest);
- a manifest whose tree was not clean (`dirty` not false);
- a manifest whose `revision` is not a full Git revision.

The view's `Library` (`src/lenses/laws_data.js`) refuses a list read from another major or from
a tree that was not clean as well.

## The stamp

```json
"stamp": {
  "generator": "visualizer/tools/extract_laws.py",
  "read": "Read from the engine's declarations at main 93fc8c2c",
  "manifest": { "path": "data/engine/declarations.json", "kind": "cells.declarations@3", "revision": "<40 hex digits>", "short": "93fc8c2c", "dirty": false, "origin": "git checkout" },
  "overlay_as_of": "2026-11-18",
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
  its `status_source`. At main 93fc8c2c none does.

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
`loop_term`, `material_term`, `charge_bound`, `material_bound` and `step_method` null are "none"
("Each names the kernel that supplies it, or is null where the law has none"); `forms` null is
"none" too, since the page says of it only "or null", and a value of `forms` is said in the page's
words ("base", "registry"). The step terms and bounds are named as the page names them: "Stage term",
"Material term", "Bound on a charged row", "Bound on a neutral row", "Forms". `declared_host` null says the host is not stated
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
- the rest under `fields`, by the format page's section for its interface, a cycle law's general
  form in words (below);
- its status ("not stated" today) and its page (`doc`: "none given yet" today).

### A cycle law's general form

A cycle law's `fields.cycle` is said under the format page's name for it, "Its general form"
("Cycle laws": "`cycle`: its general form (seam A's cycle form), or null"), never as the raw key
or its JSON. Each key's meaning is the engine's own: the format page and the docstrings of the
cycle forms' module (`laws/cycles/forms.py`, "What a cycle form is").
- **The row** says its kinetics and how many modes, roles and parameters it has. A null form
  says "none".
- **The section "Its general form"** says, key by key:
  - `kinetics`: which of the four kinetic forms, in the module's words (factored, diagram, net
    flow, monomial);
  - `modes`: each mode by its ID, and each row's change per forward cycle, signed: an integer,
    or a parameter's name, which a leading "-" negates;
  - `roles`: each role with the valence it requires of the species it binds, or any valence;
  - `rows`: each a role at the N or P end of its host;
  - the kinetics' own data (`saturation`, `diagram`, `flux_terms` or `monomial`): what it is,
    never the data: a factored form's Hill factors per mode and their rows, a diagram's states,
    steps and Hill cycles, a net-flow form's terms, a monomial form's rates and read roles;
  - `ph_bands`: the row whose pH stays within a band, and the band's two parameters;
  - `temperature_K`: the domain, low to high, in K.
- **The section "Its general form: its parameters"** says each parameter with its unit and its
  declared range: inclusive bounds, above zero where it is positive, a whole number where it is
  an integer.
- **A key that is null says nothing,** and another kinetics' empty data says nothing.
- **A key the engine's documents do not explain** is shown under its own name with a plain
  value: `fuel_roles` today.
- **A form the card does not know** (a kinetics added later, or a key added to the form) still
  shows: the kinetics under its own name, as one these words do not know yet, and its data and
  any other key under their own names, a list or an object counted by its size, never poured.
- **Where the form carries the law** (the format page: "`moves` may be empty and the kernels
  null"), its empty moves say "none of its own: its general form carries them", and its null
  `kinetics` and `domain_valid` fields say nothing.

## Sources and links

Every source is the engine's own record or the viewer's own data; no third-party source is read.

- **The manifest's revision.** A file the manifest names (a piece's `module_path`, a kernel's, a
  model's, a page in `doc`, a design note's) links at `stamp.manifest.revision`, in the
  repository of the scene's `source_base_url`: the file is there by construction. Where the
  map's revision is another, the words beside the link say so ("line 47, as declared at main
  93fc8c2c"). The link names the file; the line is said in words.
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
a long family name is written smaller so that it fits its column. A shelf of one family is named
by its family alone. Today all six shelves stand on one band: the laws of the inner model, a model
family's own laws, the kinds, the composite's operators by their part of the step (split, event
and split, event, process, no part), a model family's own operators, and, apart, the laws named
in design notes. A model family's own laws and operators stand on shelves of their own because
they are not the inner model's laws nor the composite's operators, and a shelf's name stands
over every column on it (a test holds this).

## What the wall does not show

- **Historical model bookmarks** come from the v58 catalogue in `data/engine/viewer-ids.json`.
  A bookmark that resolves through the published ID moves to a current model opens that model.
  The other bookmarks open a historical entry with its catalogue revision.
- **Currently unlisted IDs** open a notice pointing back to the current registry.
- **A row with no piece of its own** (the fuel kind) is drawn as its socket; its address opens
  what the model says of it and the cycle laws that run on it.

## On the map's page

The page carries this file in its scene as `laws` (`tools/lib/build_page.mjs`), and the viewer
offers the Laws library only when it does. It carries the law-port table (below) as `law_port`.

- **The address.** `lens=laws` (or `#laws`) opens it. `select=laws:<id>` opens it on a piece, a
  model or a notice, from any view.
- **The doors.**
  - An Engine view box that holds the files of declared pieces: "Show its N declared pieces in
    the Laws library", which picks them out; the card says so, and its Close lets them go.
  - An Engine view operator (`op.<id>`) the manifest declares: "Open <id> on the Laws library's wall".
  - A unit of the Protein atlas: for each law its panel names, "Open <id> on the Laws library's
    wall" where the manifest declares it. For those it does not, lines that open nothing: one for
    each mark the law-port table gives them, "<laws>: <the mark's words>" (below), and one for the
    laws the table has no row for: "No active model declares these laws of this unit: <ids>. The
    engine's declarations do not list them, and the Laws library does not show them." (in the
    singular for one).
- **The way back.** A piece's panel links its box, or an operator's own part, and a model's
  panel its boxes, where the page draws them.
- **The card** has the search field, the Family control and "Where it stands". `]` and Page Down
  step to the next piece in the wall's order, `[` and Page Up to the one before.
- **The room** is kept clear of the cards on the left on a wide window, and the names written on
  it come back with a lost context or a lost graphics process.

## The law-port table

On 17 November 2026 the project decided to port tested older laws to the active engine (D211).
Its first step was a read-only inventory of the law IDs behind the Protein atlas's units that no
active model declares (`cells.law_port_inventory@1`, a working record of the engine's lead, kept
at `/mnt/workspaces/Cells/law-port-20261117/inventory.json`). The page reads it through a table
of its own, made by a tool and never by hand:

```bash
python3 -I tools/extract_law_port.py --inventory PATH/inventory.json   # -> data/laws/law_port.json
```

```json
{
  "format": "cells.visualizer.law_port@1",
  "note": "…how it is made…",
  "inventory": { "kind": "cells.law_port_inventory@1 (working record, D211)", "made": "2026-11-17", "head": "<40 hex digits>" },
  "counts": { "rows": 54, "units": 38, "marks": { "port as is": 47, "fold into an owner's planned law": 5, "not a port": 2 }, "test_class": { "a": 52, "b": 2 } },
  "rows": [ { "law": "kv1p1_mh2@1", "has_id": true, "units": ["U05"], "mark": "port as is", "test_class": "a" }, … ]
}
```

- **A row** is the inventory's row: `law` its `law_id` (for the one row without an ID, what the
  inventory calls it, and `has_id` false), `units` its `atlas_units`, `mark` its `owner.mark`,
  `test_class` its `tests.test_class` (a: a passing test of the kernel against a reference; b:
  passing tests of the family only). Nothing else of the inventory is copied, and no path.
- **The tool refuses** (exit status 2, nothing written) an inventory whose `kind` is not
  `cells.law_port_inventory@1` (with or without words in brackets), and one whose rows do not
  hold 47, 5 and 2 laws of the three marks on 38 units, whose own counts of its marks differ from
  its rows, that lists a law twice, that gives a law to port as is a tests' class that does not
  pass ("tested" is said of it), or a law to fold to another than the cardiac lane.
- **The words** for each mark are in `src/lenses/law_port.js` (`PORT_PHRASES`) and nowhere else:
  one for "port as is", one for "fold into an owner's planned law", and for "not a port" one for
  each of its two laws (the mitochondrial passive permeability, the gap-junction flux). They are
  the lead's, given to the viewer on 17 November 2026, and a test holds them letter for letter.
  "Tested" in them is the inventory's word for a passing test of the old kernel, not a judgement
  of the engine; "declared" is not a level.
- **A row is matched** to a law a unit's panel names by the law ID as written, on a unit the row
  names. The row without an ID is matched, on each unit it names, to that unit's one law that is
  not an ID and begins with the same word (the function's name, `junction_flux()`). A law of a
  mark the source has no words for, or with no row, keeps the line for laws the declarations do
  not list: no mark is guessed. A law the manifest declares is a door, whatever the table says.
