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
| `data/catalogue/measures/*.json` | `tools/measure_particle.py`, run by the viewer | The tool's own output for an entry, as written |
| `data/catalogue/overlay.json` | Hand | The groups; the units of the law inventory left out, with why; the measures it reads and the entries they rest on; the kinds of machine (id, label, group, a plain line, the record lines of what Cells models of it); for each species, the kinds its records name and where each is named, counted and sized |
| `data/catalogue/gather.json`, `data/catalogue/dossiers/<species>.json` | Hand, and `tools/gather_machines.py` (`schema/MACHINE_DOSSIERS.md`) | The kinds looked for, and for each species with a dossier file its machines, their proteins by tier, counts per cell from open papers, the entry the gathering would measure each from, and `by_protein`; read here, never written |
| `data/catalogue/structures/<species>.json` | Curated RCSB PDB search results | An experimental structure bench linked through `overlay.structure_benches`, with the taxonomy search, related depositions, the reference assembly and source annotations for its polymer entities |
| `data/catalogue/catalogue.json` | `tools/build_catalogue.py` (generated: do not edit) | The catalogue's core, which the page carries: the groups, the kinds (each with the species that have it), the records, the sources, the units' sizes, and `benches`, an index of the species' benches |
| `data/catalogue/benches/<species>.json` | `tools/build_catalogue.py` (generated: do not edit) | One species' bench (`cells.visualizer.machine_bench@1`): an entry for each of its machines, with what its records give and their sources; `by_protein`, its proteins' machines; and `none_found`, the machines its dossier looked for by family and found no candidate for (each with its reference, its rows part by part, the dossier's sentence and its sources); published beside the page at `catalogue/<species>.json` |

```bash
python3 tools/build_catalogue.py            # writes data/catalogue/catalogue.json
python3 tools/build_catalogue.py --check    # fails if the file is not what the tool writes
```

One catalogue for all species, with species' entries: a kind (the ribosome, the ATP synthase)
recurs across species, and what it is and does, its group and what the record says Cells models of
it are the kind's, said once; what names it, its count, its size and its proteins are the species',
each entry with its own sources. The page carries the catalogue's core in its scene as `catalogue`
(as the Laws library's list); each species' bench is a file beside the page, read once when that
bench is first shown (by the view, its List, the text page, or the atlas's way back to a protein's
machines), through `loadBeside`, as the atlas reads its shelves. A page for the disk carries every
bench inside it. While a bench is read the card says so; one that cannot be read says why in plain
words, and the tab goes on with the units of the law inventory. While it is read the view is not
`ready`: the viewer waits on it before it chooses what an address or a door names, so that a
machine, a part, a chain or a unit is chosen at its level on the bench laid out, and flown to, as
on a bench in hand; a choice made meanwhile (a unit pressed, the List) is chosen again once the
bench is laid out, and the camera sent to it goes to its new place. Decided 18 November 2026: with
eight dossiers the whole catalogue was about 1.2 MB, too much for every page to carry. The membrane units of
the law inventory are not in the file: the page reads them from the scene's protein units, as
the Protein atlas does ("Cells' N units"), and lists a unit for a species where that species' atlas
found its family there or found it built from another (for the inventory's own species, a unit that
names gene products). A unit that is no protein assembly (a leak, a permeability, a lumped
conductance, or a law that names no protein) is no machine: the overlay's `units_left_out` names
each with its reason, and the catalogue never holds it. The atlas keeps all its units, and the
catalogue never says their count.

A model system can supply a `view.machine_bench` in place of the last selected species' bench.
Each structure bench card describes a representative biological assembly and links its related
PDB entries. The first record in `structures` provides the measured assembly and its selectable
surface. Its chains carry the deposited entity's source organism and UniProt accession where
the archive has them. The Protein atlas cross-links only species-matched accessions held on its shelf.

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
- **A measured size** (`shape: measured`) is the viewer's own measure from a Protein Data Bank
  entry's coordinates, made with `tools/measure_particle.py` by its definition:
  each body the ellipsoid of the same spread as its polymer atoms, the farthest atoms beside it.
  It gives the whole's widths and each part's widths, centre and axes in the measure's frame. It
  names its entry, its organism, the definition and the tool, and it never reads as the database's
  value. Where the structure is another organism's (a bacterium's ribosome drawn at E. coli's
  measure), the species' file's own words say so (`whose`, its part's `note`), and the panel gives
  them as written. It is read from the species' file where that file states the part (`cell.parts.ribosome`),
  and only otherwise from the tool's own output that the overlay's `measures` names (kept under
  `data/catalogue/measures/` as the tool wrote it; transitional where a species' file will state
  it). The overlay's own `sources` hold the entries, each CC0 1.0.
- **Its parts and chains.** The tool's machine mode (`--machine`) gives the whole, the named parts
  the overlay asks for (`--part NAME=ENTITY,ENTITY`, by the entry's entity ids) in a frame from
  one part's centre to another's, and each chain. A measure's spec in the overlay names its entry
  (and one beside it), its parts with their labels (and a hue of the page's palette for a part a
  visitor should tell apart), whether its chains are drawn, and its outline: its parts, or the
  whole where it has none. A measured machine's levels are Outline (its outline's bodies in its
  group's colour), Parts (each named part, `machine:<kind>:<part>`) and Subunits (each chain,
  `machine:<kind>:chain-<id>`, in its part's hue), each where it has them; chosen, it goes to its
  first level past the outline. Each part and chain has its own panel with "Back to the machine".
  A part may also be named by chains (`NAME=chains:A,B`, for an entry of one kind of chain: a
  connexon of a gap-junction channel); it then keeps its chains' ids, and its chains wear its
  shade. Where every chain of a machine is in a named part, a part is drawn as its chains, in the
  part's one colour, and chosen and named as the part (its outline too, in the group's colour): a
  part's own ellipsoid is its size, given in its panel, not its picture, since the ellipsoid of the
  same spread of chains that lie apart (the ATP synthase's peripheral stalk, b2 and δ) is a slab
  that hides the rest. The levels a machine offers come from its measure, and nothing assumes
  three is the most.
- **Whose structure.** A measure names the organism its entry is of (`of`). Where the species shown
  is of another, the words say so and that none of the species' own is in hand: "a structure of
  Homo sapiens (one of Schmidtea mediterranea: none in hand)"; where the species' file gives its
  own words on it (`whose`), those stand instead. Until a dated search of the Protein
  Data Bank by organism is written down for a machine, that is all they say of the species' own.
  A measure that leaves something of its entry out says what, in its `note` (the human 80S: RACK1,
  which the tool does not count among the subunits' chains). Where entries were compared, the
  measure's `chosen` says which was taken and why, as a dated decision (the overlay's alone; the
  page does not show it).
- **Where its membrane lies.** A measure's spec may name its part in the membrane (`membrane`:
  the ATP synthase's ring), where its frame runs along the machine's axis (from the ring to the
  head). Chosen at its parts, the machine then stands in a thin, see-through slab, labelled an
  illustration: centred on that part, as thick as that part's farthest atoms reach along the axis
  (`membraneOf` in `src/lenses/machines_layout.js`; the panel gives the number), and across, the
  room of its tray round it. No entry holds a membrane: the slab says where the ring stands, not a
  membrane's measured thickness.
- **The dossiers.** A machine a species' dossier names is on that species' bench, after the
  overlay's own entries (E. coli 21, the human 32 beside its units). Where the overlay lists the
  machine too, its entry stands as decided, and the dossier adds what the overlay does not say:
  - *What names it*: the overlay's (a capability of the species' file, a record of the viewer)
    is "Named by", the dossier's sentence on the Gene Ontology and UniProt "Also named by"; where
    the overlay names nothing, the dossier's is "Named by".
  - *Its proteins by tier*: the panel lists them in three lists, said as such: "Its parts, held by
    the structure" (`part`), "Its parts by UniProt's keyword, not held by the structure" (`part by
    keyword`) and "Named with it by the Gene Ontology alone" (`named`), each with its UniProt
    link; they feed the search. A set the species' own data marks stays its door into the atlas.
  - *Its count*: the species' file's fact where the overlay names one, else the dossier's: a fact
    of the species' file it points to, or an open paper's number with what it counts, in what
    cell, the paper and its section and paragraph.
  - *The gathering's pick*: where the dossier would measure it from another entry than its size
    is measured from, or where it has no size, the panel names that entry beside it.
  - *Its kind*: a kind only the dossiers name takes gather.json's label, group and plain line, and
    FR-13's line (it names the machine as absent where the overlay says so, `absent_as`; else it
    does not name it). The groups `dna`, `folding` and `traffic` are the overlay's since 17
    November 2026, each with a colour no other tray has.
  - *The way to and from the atlas*: a measured part names the genes the overlay groups in it
    (`genes`, from the dossier's rows), and carries their proteins; where the measured entry is the
    dossier's own, each chain carries the protein its entity is, by the dossier's reading of the
    entry. A chain's panel opens the Protein atlas on its protein (the door's `find`: the atlas's
    own search, then its own reveal). The catalogue carries `by_protein` per species, and a protein
    of the atlas offers the machines its dossier makes it a part of, or names it with.
  - *A machine that stays a card* says why in one line (`no_size`, a dated decision): the human's
    nuclear pore, whose entry is an integrative model holding about a third of its proteins.
- **The eight dossiers** (since 18 November 2026: E. coli, the human, the mouse, the fruit fly and the
  thale cress by their own reviewed entries; the planarian, Syn3A and M. pneumoniae by family).
  What the panel says of each, each said as what it is and with its source:
  - *A species by family.* Its proteins are candidates by their family (InterPro) for parts of the
    reference's machine, never the machine's parts: "Candidates by family, not its parts", and
    "What was looked for, part by part", with the answer for each part in the dossier schema's
    words (candidates; not in the table, which says what the table holds, not that the species
    lacks the protein; cannot tell; no family signature). Where the species' own data marks the
    machine's proteins, both sets side by side. The species' own records keep their place above
    the dossier's ("Named by", FR-13's line). Nothing of the species names the machine by its
    family route, so that line is "Looked for, by family", never "Named by": the panel writes it
    from the dossier's rows, part by part, with the dossier's own counts (the species' candidates,
    the parts they stand for, and the parts not in the table, that it cannot tell of, and with no
    family signature).
  - *Looked for, no candidate found.* A machine that only the family route names and for which it
    found no candidate is not on the bench: in no count, no tray and none of the List's groups. The
    bench's `none_found` lists it, and the card and the List give it under its own heading,
    "Looked for by family, no candidate found", with the dossier's caveat (this says what the
    species' table holds, not that the species lacks the machine), each with its reference
    machine; the card's search and the List's find it there, and its panel says what was looked
    for, part by part. A machine the species' own file or record names stays on the bench, whatever
    the family route found (Syn3A's ribosome, RNA polymerase, ATP synthase, translocon, FtsH and
    Lon; M. pneumoniae's attachment organelle). Since 18 November 2026: the planarian 30 machines
    and 1 apart, Syn3A 9 and 10, M. pneumoniae 11 and 9.
  - *A candidate by family on the bench* says so on its card's face, in words ("candidates for 22
    of 32 parts, by family"), and in the List beside its name; the card counts the machines the
    species' own records name and the candidates by family apart. No dash, outline or status
    colour marks it: those are the page's statuses.
  - *A protein's door from the atlas* says what its dossier makes it: "It is a part of the …", "It
    is a part, by UniProt's keyword, of the …", "It is named with the …", or "It is a candidate, by
    its family, for a part of Human's proteasome"; a tier these words do not know has no door.
  - *Plain words.* A dossier's sentence reaches a panel without a file's or a field's name: the
    tool rewrites the few that hold one (each rewrite exact) and stops on any other, and a source
    that is a file of the tree is named in words, the file standing in the panel's list of files.
  - *PaxDb's abundance*: parts per million of one whole-organism dataset, named, as that database
    gives them; no count of copies.
  - *UniProt's SUBUNIT sentences*, in quotation marks, as UniProt's: not a count of copies.
  - *Sub-assemblies* by the Gene Ontology's narrower terms, and UniProt's fractions (complex I).
  - *The pick*, with its entry's own title, and where it holds other complexes, that it does, and how
    many of its entities a measure would leave out; *a structure elsewhere*, named as another
    organism's, where the species has none of its own; *entries left out*, and why.
  - *A count per cell* as the paper writes it (its power of ten kept: "1064 × 10^4"), what it counts,
    in what cell, the paper and its place, and whom it cites; several conditions, each with its own,
    none picked. The viewer multiplies nothing.
  The group `light` ("Capturing light", from gather.json) has a tray of its own, in the chloroplast's
  green; copying and mending DNA took the Golgi's pink.
- **Forms the Complex Portal curates** (since 19 November 2026; rule and exceptions in `schema/MACHINE_DOSSIERS.md`, "Forms").
  The Complex Portal's entries that fit a kind stand beneath it as lines of its panel (`gathered.forms` of its entry), under the
  head "Forms the Complex Portal curates" with how many there are; the first four stand and the rest open by a press. Each line
  gives the entry's own name, its identifier (a link to its page at the Complex Portal), how many proteins it holds and how many of
  the machine's parts they are, its stoichiometry where it gives one, and its evidence in the portal's own term with one plain
  line (an inferred entry says "Inferred" first and names the species it is taken from). A form is never a machine: it makes no
  kind, no marker on a bench and no count of machines. Where its stoichiometry differs from a count the panel shows, both stand,
  each with its source; nothing is reconciled by the page. The portal stands among the sources (CC0 1.0, as its 2022 paper states;
  taken as enough by the decision of 18 November 2026), through the licence test as it stands. The human's, E. coli's, the mouse's and
  the fruit fly's benches carry forms; each bench's file grows by what the panel shows and no more.
- **The vault** (`vault`, the 54th kind, in the group `unknown`, "Particles whose job is not known", the tray colour the page's
  cytoplasm blue). It is a named exception to how a kind is identified (the Gene Ontology has no term for it and UniProt no
  keyword): its proteins stand on three footings, each said in its own words on the card and never mixed (by the record, named by
  a reviewed UniProt entry, by family alone; `schema/MACHINE_DOSSIERS.md`, "The vault"). It stands on the human's, the mouse's
  and the planarian's benches; where no signature is found in a species it is not on that bench, and the panel that names it
  there says what was looked for and that this is not an absence. Its size and shape are the viewer's own measure and surface of
  Protein Data Bank entry 9MXV, a human vault; the card gives the Complex Portal's, the preprint's and the viewer's sizes side by
  side. A bioRxiv preprint (not peer reviewed) on prokaryotic vaults is named in one passage of its card, each number with its
  place in the preprint; no prokaryotic vault stands on any bench, and nothing of the preprint's figures is drawn. Each protein
  of the vault leads to its line in the Protein atlas and back.
- **Organelles** (since 20 November 2026). A kind of a group that `stands: "shelf"` (the overlay's `organelles`, "Organelles") is an
  organelle and no machine: its species' entry goes to the bench's own list `organelles`, beside `entries`, never into a tray or a
  count of machines (the core's index gives `organelles: n` beside `machines`); its page id is `organelle:<kind>`.
  - *What names it*: `named: { part, words }`, a part its species' file's `cell.parts` holds (`nucleus`, or one of `organelles`);
    the tool stops otherwise.
  - *Its size*: a fact of the species' file, whole (`size: { fact, shape, ... }`), or the size the file states for that part of its
    cell (`size: { part, shape }`, `cell.parts.organelle_sizes`); the shape one of `sphere` and `lens` (`across_um`), `stack`
    (`across_um`, a cisterna), `capsule` (`across_um`, `long_um`) and `sheet` (`thick_nm`). Every number stands in the fact's words
    (the tool stops otherwise); a fact says the cell type and species the paper measured in its own words. A range is drawn at its
    middle and says so. `what` (words, no number) says what the number is where the model takes it as another measure (a sheet's
    bilayer separation drawn as its thickness). No size: `no_size`, a dated line of what was looked for, and a card on the shelf.
  - *A general figure* (since 20 November 2026): where no measurement in a named cell type is in hand, a general figure from an open
    reference (a review, an encyclopedia) may stand as a fact, said plainly as general (whose words, which reference, what it cites),
    never as a measurement of that species' cell. It stands on a species' shelf only as far as its reference's own qualifier reaches:
    "in mammalian cells" serves the human and the mouse; a figure that names no species stands on the human's shelf alone (the
    narrow reading); a figure for one cell type serves only that species. A card that no figure reaches says so.
  - *What Cells models of it*: a record `{ map: <the map's part> }`, read from the scene at run time (its status, the map's own words
    in quotation marks, the files it rests on); the kind's `map_part` names that part, its door into the Cell view and the Cell view's
    door back ("Show it on the Machines shelf"). An organelle the Cell view draws as scenery (the chloroplast, the vacuole) has no
    record, and its panel says so.
  - *How it is drawn*: the Cell view's own model of it where there is one, built by the Cell view's builders
    (`src/lenses/machines_shelf.js`, `MODELS`: the nucleus, the reticulum, the Golgi, a mitochondrion, the chloroplast, and a centriole,
    one barrel of the centrosome the Cell view draws as scenery) and scaled so that the one measure its size sets (a width, a sheet's
    thickness, a cisterna's width, a barrel's width and length) is the source's; every other proportion is the Cell view's, and the
    panel says so. An illustration.
  - *A held size* (the owner's ruling of 20 November 2026: numbers from papers under non-commercial licences may be cited in the
    project's files and may set how a thing is drawn, and are not shown in the page). `size: { held, shape, across_um, fact?, fact_why? }`
    names an entry of `data/catalogue/held_sizes.json` (`cells.visualizer.held_sizes@1`: the paper's number as read, by whom and
    where, its source of class `non-commercial`, and the working, said as ours, to `drawn_um`). The tool checks the drawn size against
    it and writes into the bench only the size drawn, the held file's words for its basis and its path; the panel says "Drawn about
    … across, <words>, on a published measurement that the project's files cite and this page does not show", links the held file at
    the viewer's revision, and gives a permissive source's own measure where the entry names a `fact`, with why the picture differs.
    No file the page carries holds the held paper's numbers, name or source (`tests/licence_classes.test.mjs`). A held capsule (a
    centriole) gives its length too (`long_um`, the held file's `drawn_long_um`).
  - *A simple model*: an organelle the Cell view has no model of is named by the species' file's `cell.parts.shelf`, a list the Cell
    view does not read, and stands as a simple model of its own (`SIMPLE`, asked for on 20 November 2026: no flat cards), at its
    size: a sphere of one or two membranes cut open over a darker lumen (a lysosome, a peroxisome, an autophagosome), a sphere with
    knobs for its coat (a COPI vesicle), a sphere with short tubules (an endocytic vesicle), a plain sphere (a lipid droplet). It
    claims no structure beyond its plain line and its source; the panel says which part is the source's size and which the
    picture's choice. A kind with none there stands as a plain sphere, or a capsule where its size gives a length.
  - *The small organelles' plank*: an organelle no longer than 1.5 µm at its longest (`SHELF.small`) stands on a plank of its own
    between the bench and the shelf, with a stop of its own; the loupe is offered beside the shelf's organelles only.
  - *Where machines sit in it*: not stated. The catalogue states no `where` for a machine, so no organelle lists machines.
- **Its shape** (`size.surface`, `schema/MACHINE_SHAPES.md`). Where a shape file is published for a
  measured size (`data/catalogue/shapes/<the measure's file name>`, the species' own, or for a size
  a species' file draws at another's measure, the shape of that same entry: Syn3A's and M.
  pneumoniae's ribosomes take E. coli's; a unit's size the same, by its measure), the size names it: its file as published
  (`shapes/<name>.json`), whose it is, its entry and assembly, its definition and setting (a chain
  at 1.0 nm; a ribosome's subunits as solids at 1.6 nm; where a file was made coarser to hold its
  budget, both widths) and its triangles. Every measured machine and unit has one since 18
  November 2026: E. coli's six, the human's nine (the vault's since 19 November 2026), and the animals' 80S and five units. The builder stops where
  the shape's entry is not the measured one, or a surface names a chain or part the size does not.
  The page asks for a shape file only where the size names one. On every bench, a chosen machine at
  Shape stays within the ceiling: the bench's cost plus its heaviest shape (the innexin channel's
  11,680 triangles) is held by the tests.
- **A label of the species' own.** Where a species' dossier names a machine by one term that adds a
  numeral to the kind's label, the species' entry takes it: the human's RNA polymerase is "RNA
  polymerase II" (the Gene Ontology's "RNA polymerase II, core complex"), beside I and III.
- **Parts are sub-assemblies, subunits are chains** (decided 17 November 2026). A measured
  machine's Parts are the handful of sub-assemblies a textbook names, each the set of genes the
  dossier's rows give it and in its own hue (the proteasome's core particle, base and lid, as the
  Gene Ontology's terms on the rows group them; the ATP synthase's head, stalks, ring and foot, as
  UniProt names its subunits); where the rows give none, the machine has no Parts: its whole, then
  its chains. The measure's `chosen` says what the grouping follows.
- **A unit of the law inventory with a size** (`unit_sizes`). Decided 17 November 2026 (step C):
  a unit takes a size only from a structure of its own kind, of any organism, or,
  where a species' atlas finds it built from another family, from a structure of that family; the
  page picks by the atlas's finding (the inventory's own species counts as "found"). The sizes
  stand on the animals' benches and the thale cress's (`unit_sizes.species`; the plant's since
  17 November 2026, its ER calcium pump alone); the units of the other species stay cards.
  A unit with none stays a card, and no unit takes another's size (Kv1.1 is not Kv1.2).
  Where the atlas names reference structures for a unit, the measure is of one of them or of the
  unit's own protein (`unit.U41`: human SERCA2, the unit's UniProt entry, where the atlas names
  rabbit SERCA1a). The builder resolves each into the same measured size as a kind's, under
  `unit_sizes.units.<unit>.<finding>`.
- **A machine named by its own protein.** Where the species' file does not name a machine, a
  protein of the species' own catalogue (`data/proteins/<species>/proteins.tsv`) whose entry names
  it may (`named.protein`), with the catalogue's UniProt source.
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

A structure bench can also declare a microscopy shelf in its source JSON under `shelf`. Its label describes the collection, for example *Organelles* or *Cell structures*. Each row gives an id, label, species-specific description and source keys from that shelf. A sized row names its illustration and its dimensions with units and an evidence statement. A row lacking a dimension records which one in `no_size` and appears as a card. Generated shelf items use the existing `organelle:<id>` selection and scale rail. Only the deposited assemblies count toward the bench’s PDB total.

## In the page

`src/lenses/machines.js`, the second tab, "Machines" (`lens=machines`).

- **The bench.** The machines of the species shown lie on a bench in trays, one for each group,
  the law inventory's membrane units in one wide tray behind the rows of the others. A group whose
  overlay entry says `stands: "behind"` (with `stands_why`, its dated reason) has its tray at the
  very back, behind the units' tray: the particles whose job is not known do, since 19 November
  2026, because the vault is the largest shape on a bench and, in the row before the units' tray,
  hid their small shapes at the opening view. A machine with a size is a
  simple shape at that size, every one at one scale (one unit of the scene is ten nanometres),
  with a scale bar of 100 nm on the bench; a machine with no size in hand is a card with its name,
  the same size for all. A tray is as wide as its shapes, its cards (three across) or its name (in
  one line or two) need; its cards lie at its back and its shapes stand in front of them. The
  opening view frames the shapes drawn to scale (the whole bench where there are none, or where
  the shapes spread over most of it, so that no tray is cut at the screen's edge). While a
  machine is chosen, every other machine, card and name on the bench is faint, and only its name
  is on the picture. The legend names each mark that is drawn and each group's colour.
- **Drawing levels.** Among the others a machine is an outline. A machine with a file of its own
  (`schema/MACHINES.md`) is drawn from it: its outline (level 1) on the bench, its parts (level 2)
  when it is chosen, its subunits (level 3) by the card's Detail, as its closer view draws them.
  A measured machine or unit is drawn from its measure the same way. Every level is an
  illustration.
- **The Shape level** (the fourth, after Subunits, on a machine whose size names a shape file).
  Chosen at it, the machine's file is read once (`machine_shape.js`, `loadShape`) and drawn as one
  mesh in the group that holds its ellipsoids, so that it sits where they sit; its ellipsoids stand
  until the file is read, and stay where it cannot be, the panel saying why. Each surface wears its
  part's hue (or the group's colour in two shades by part), its chains a little apart; a ribosome
  is its two subunits as solids (its RNA and protein in two tones read less well: patches of protein
  on the RNA). A press on a surface chooses its chain where the catalogue names the chains, else its
  part; the chain's panel gives its protein, its door into the atlas and a door to its part. The
  machine's panel says what the shape is: the viewer's own smooth surface of the entry's
  coordinates, by its definition, at its setting, an illustration, not the structure and not a
  measurement; the Protein Data Bank states no surface; the width a file was made at where it is
  coarser than the setting's; and, where the entry is of another organism than the species shown,
  that it is the shape of a structure of that organism, as its size is. A unit of the law
  inventory is drawn by its own page id (`unit.U39:chain-A`). The card's Detail stands in one row,
  and in two rows of two on a phone, where four whole words do not fit in one.
- **The ceiling at every level.** Every measured machine and unit, chosen at every level it has, stays
  within 40 draws and 40,000 triangles on its species' bench (held by the tests for each of them): a
  chosen machine's bodies are as smooth as before, and coarser where it has many (the mitochondrial
  ribosome's 89 chains), within about 12,000 triangles together, as the bench's outlines coarsen.
- **A chain named while a shape of parts is shown** (the ribosomes' shapes are their two subunits):
  the machine goes to its Subunits, and the card's Detail and the panel say so.
- **The choice told apart.** A part or a chain chosen in a machine is lit in the page's accent, as
  the chosen machine is: by its instance's colour at Parts and Subunits, by its surface's at Shape
  (`recolour`); choosing it does not rebuild the machine. The legend's line for the choice says so.
- **Light on a phone.** The outlines of every measured machine on the bench are one instanced
  mesh, the trays two, the cards two; a chosen measured machine's bodies are one more, picked by
  their instance, however many chains it has. The tests hold each bench to 40 draws and 40,000
  triangles.
- **Its panel** gives what it is, what names it, how many and how big with their sources, its
  proteins, what Cells models of it (each record line), and its doors: the Protein atlas on its
  proteins where the species' own data can show the set, the place it sits in the Cell view (the
  ribosomes), or its closer view there ("Look closer in the cell"). A unit of the law inventory has the Protein
  atlas's own panel of it, for the species shown, and a door into the atlas; a unit with a size adds
  how big it is, whose structure it is measured from, and how it is drawn. Its parts and chains are
  chosen under its own id (`unit.U39:alpha`).
- **Addresses.** `lens=machines`, `select=machine:<id>` (the kind's id; with no lens it opens the
  catalogue). Under the Cell view the same id stays the closer view's: the view shown keeps an id
  it holds itself. A unit keeps its own id (`unit.U01`). A machine the species shown lacks says which
  species have it.
- **Elsewhere.** The Cell view's ribosomes, a machine's closer view and a unit of the atlas that the
  species has each offer "Show it in the Machines catalogue".
- **The shelf and travel between scales.** Behind a bench whose species has organelles stands a shelf at the bench's one scale, the
  small organelles on a plank of their own between the two. The page's rail gives the stops, largest first: the shelf, the small
  organelles and the bench by name, each with what the page's scale bar reads there, the powers of ten from 10 µm to 10 nm, and a
  mark for what is chosen at its own size. A stop is travelled to in the same time for each power of ten (`PER_POWER`), the camera's
  target moving in step with its distance from one stop to the next; with less motion the view changes at once. Every organelle is
  named at each stop, and a press on its name travels to it (since 20 November 2026, step D1: on every laptop window, with twelve
  organelles as with seven). At the bench's stop the planks are not drawn and every organelle has a short name above the bench
  ("↑ Nucleus", its size in its tooltip), in level rows as many to a row as the picture's free width holds, the top row below the
  page's bar; at the small organelles' stop each is named on its plank, the shelf's above them, and the bench is a marked tray; at
  the shelf's stop its organelles are named, the small ones named before it (each a way down to it), and the bench is a marked tray.
  Each name is measured as the page draws it and set where its box meets no other name of the stop; the names are laid out again
  when the window or the room the cards leave changes. A phone shows one name at each stop and the List for the rest. On a wide window the rail
  folds behind the page's button while a panel is open. The page's own scale bar shows on such a bench. A sized machine's panel
  offers a loupe: the machine beside an organelle at its true size, and in a framed lens magnified by a round factor, written on
  the frame. `scale=` in the address names a stop (`scale=shelf`, `scale=small`). A species with no organelle has no shelf and no rail.
- **The list, the search and the text page.** The List gives the groups with their machines; the
  card's search finds a machine by its name, a gene or an identifier of its proteins; with no 3D the
  List and the panels stand alone.
- **Checks.** `tests/machine_catalogue.test.mjs` (the file, the words, the layout, the draw
  ceiling) and `tools/check_catalogue.mjs` (`catalogue-*` in `tools/check_all.mjs`).
