# The Machines catalogue: the molecular machines of each species

Status: **written for the viewer, 17 November 2026**, for the Machines tab. The tab and its
catalogue were asked for on 17 November 2026: a catalogue of molecular machines by species,
gathered as the proteins were, in a design of its own. Decided 17 November 2026 (D209, main
`7538b0cd`): the tab is the first milestone (M0) of the engine's path for machines, a catalogue
with drawing levels labelled illustration; no machine is in the engine, and the drawing levels are
the viewer's, not simulation detail.

The catalogue says, for each machine a species' record names: what it is and does, which group it
stands in (what it does), what names it, how many a cell has and how big it is where a source says,
the proteins its species' own data marks with it, where it sits in the cell, and what Cells models
of it, as the record says. It never says that Cells models a machine unless the record does.

`schema/MACHINES.md` is the contract of one machine drawn closer (the flagellar motor). A machine
of the catalogue with such a file is the same machine: it keeps its file's id, so its page id is the
same in both views (`machine:<id>`).

## Files

| File | Made by | Holds |
| --- | --- | --- |
| `data/catalogue/overlay.json` | Hand | The groups; the units of the law inventory left out, with why; the kinds of machine (id, label, group, a plain line, the record lines of what Cells models of it); for each species, the kinds its records name and where each is named, counted and sized |
| `data/catalogue/catalogue.json` | `tools/build_catalogue.py` (generated: do not edit) | The groups, the kinds and one entry for each machine of each species, with what its records give and their sources |

```bash
python3 tools/build_catalogue.py            # writes data/catalogue/catalogue.json
python3 tools/build_catalogue.py --check    # fails if the file is not what the tool writes
```

One catalogue for all species, with species' entries: a kind (the ribosome, the ATP synthase)
recurs across species, and what it is and does, its group and what the record says Cells models of
it are the kind's, said once; what names it, its count, its size and its proteins are the species',
each entry with its own sources. The page carries the catalogue in its scene as `catalogue` (as the
Laws library's list), so the view, its List and the text page read one file. The membrane units of
the law inventory are not in the file: the page reads them from the scene's protein units, as
the Protein atlas does ("Cells' N units"), and lists a unit for a species where that species' atlas
found its family there or found it built from another (for the inventory's own species, a unit that
names gene products). A unit that is no protein assembly (a leak, a permeability, a lumped
conductance, or a law that names no protein) is no machine: the overlay's `units_left_out` names
each with its reason, and the catalogue never holds it. The atlas keeps all its units, and the
catalogue never says their count.

## Rules

- **A kind** has an `id` (lower case, hyphens), a `label`, a `group` of the overlay's groups, a
  `plain` line in its own words (a machine file's own, where the kind has one) and `records`: the
  lines of the project's record that say what Cells models of it. A kind with `machine_file` has a
  file `data/machines/<species>.<id>.json` whose `id` is the kind's: the tool stops otherwise.
- **A record line** names a record of `records` (a file of the engine with `path`, `where` with its
  line, and the full `revision` it is read at, or a file of the viewer). It says only what that
  record states: FR-13's status, and that it names the machine among those with no model, or that
  it does not name it ("not on the engine's plan"); the map's own status of a part of the Cell view
  (the ribosomes: `cap.ribosomes`, read from the scene at run time). A line of a kind's own gives
  its `status` and `says`, written as "Decided <date> (<decision>): ..." in plain past tense. Today
  one kind has one: the ATP synthase, "Planned, first", on D209. No line says modelled, designed,
  qualified or judged.
- **What names it** is a capability's note in the species' file, of which the entry keeps the one
  sentence that names it, with that capability's sources; or a file of the viewer
  (`docs/CELL_STRUCTURES.md`: every cell has ribosomes).
- **A count** is a fact of the species' file, whole, with its sources, and what it counts where
  that is not the machine itself ("one at the foot of each flagellum").
- **A size** is read, never written here: a fact of the species' file that gives it (the attachment
  organelle's length), or the size the species' file states for a part of its cell
  (`cell.parts.ribosome`: the viewer's own measure from a structure, with its definition, its tool
  and its entries). The catalogue holds no second number of a size. Where neither is there, the
  machine has no size in hand and is drawn as a card. A width that no source gives and that a shape
  needs (the attachment organelle's) is the picture's choice, and the panel says so.
- **Its proteins** are those of the species' own data that carry a mark with the machine's name
  (`complex` for E. coli, by the Gene Ontology; `complex` for Syn3A, by the genome record's product
  names; `where` for M. pneumoniae's attachment organelle, by UniProt), with the mark's own words on
  how it is given. They are not called subunits unless a source says so. No protein is matched by
  its name here.
- **Sources** are copied from the species' files with their terms (`text`, `doi`, `licence`,
  `class`, `accessed`). Whatever names, counts or sizes a machine rests on a permissive source
  (`tests/licence_classes.test.mjs`).
- **The file holds no clock time**, so the same inputs give the same bytes, and
  `tests/machine_catalogue.test.mjs` holds the file to what the tool writes.

## In the page

`src/lenses/machines.js`, the second tab, "Machines" (`lens=machines`).

- **The bench.** The machines of the species shown lie on a bench in trays, one for each group,
  the law inventory's membrane units in one wide tray behind the others. A machine with a size is a
  simple shape at that size, every one at one scale (one unit of the scene is ten nanometres),
  with a scale bar of 100 nm on the bench; a machine with no size in hand is a card with its name,
  the same size for all. The legend names each mark that is drawn and each group's colour.
- **Drawing levels.** Among the others a machine is an outline. A machine with a file of its own
  (`schema/MACHINES.md`) is drawn from it: its outline (level 1) on the bench, its parts (level 2)
  when it is chosen, its subunits (level 3) by the card's Detail, as its closer view draws them.
  Every level is an illustration.
- **Its panel** gives what it is, what names it, how many and how big with their sources, its
  proteins, what Cells models of it (each record line), and its doors: the Protein atlas on its
  proteins where the species' own data can show the set, the place it sits in the Cell view (the
  ribosomes), or its closer view there ("Look closer in the cell"). A unit of the law inventory has the Protein
  atlas's own panel of it, for the species shown, and a door into the atlas.
- **Addresses.** `lens=machines`, `select=machine:<id>` (the kind's id; with no lens it opens the
  catalogue). Under the Cell view the same id stays the closer view's: the view shown keeps an id
  it holds itself. A unit keeps its own id (`unit.U01`). A machine the species shown lacks says which
  species have it.
- **Elsewhere.** The Cell view's ribosomes, a machine's closer view and a unit of the atlas that the
  species has each offer "Show it in the Machines catalogue".
- **The list, the search and the text page.** The List gives the groups with their machines; the
  card's search finds a machine by its name, a gene or an identifier of its proteins; with no 3D the
  List and the panels stand alone.
- **Checks.** `tests/machine_catalogue.test.mjs` (the file, the words, the layout, the draw
  ceiling) and `tools/check_catalogue.mjs` (`catalogue-*` in `tools/check_all.mjs`).
