# Machines: a closer view of one machine of a species' cell

Status: **written for the viewer, 16 November 2026**, for the flagellar motor of E. coli. The
user, the same day: "motor, yes it should turn at real life speeds at flux ... look closer
sounds good - wait with protons through and have protein data bank". The design and the
options it was chosen from are the motor agent's note to the coordinator (not in the tree).

A machine file describes one molecular machine at one place in a species' cell: its parts,
with sizes and counts, the layer of the envelope each sits in, the species' own proteins
that make each, and a source for every number. The Cell view draws a closer view of the
machine from the file alone; the viewer holds no drawing that belongs to one machine or one
species (`src/lenses/machine_parts.js`, `src/layers/machine_motion.js`).

**It never says that Cells models the machine.** `modelled.state` is `none` unless the
project's record names a registered model of it, and the page says "Cells has no model of
this motor" (or of the machine, in its own name) wherever the machine is drawn.

## File

`data/machines/<species id>.<machine id>.json`, format `cells.visualizer.machine@1`.
`data/machines/ecoli.flagellar-motor.json` is the first.

## Rules

- **`cell_type`** (optional) names the cell type of the species the machine belongs to, by
  its id (cell types become first-class: `docs/CELL_TYPES_DESIGN.md`, "Decided"). Absent,
  the machine belongs to the species' default cell type. No cell-type file exists yet, and
  no machine file uses the field.
- **`species` and `at`** name the species file and where in its cell the machine stands.
  `at` is one of two forms, and what it names must exist:
  - `{"appendage": <kind>, "base": <base id>}`: the machine at an appendage's foot
    (`schema/SPECIES.md`, `base`). It is entered from the foot's panel, "Look closer".
  - `{"part": <a part of the Cell view>, "place": <words>}`: the machine at a part of the
    cell. It is entered from that part's panel. No file uses this form yet.
- **`set`** is the mark and value under which the species' own proteins list the
  machine's (`schema/SPECIES_PROTEINS.md`, `highlights`). **Every protein of the set
  stands in the file once**: in a part's `proteins`, or in `not_drawn` with its reason and
  what it rests on. Proteins are named by the catalogue's own identifiers, with the gene.
- **`frame`**: sizes in nanometres along one axis. For a machine in a membrane the axis
  runs out of the cell, from zero at the middle of that membrane (for an appendage, the one
  it starts at). For a machine in no membrane, the axis is its own and zero is its middle.
- **`layers`** (optional) are the membranes and walls round the machine: each a `layer`
  with `z_nm` and `thick_nm`.
- **`parts`** each have an `id`, a `label`, a `role` (`rotor`, `stator`, `bearing`,
  `export`, or another word the page can name), a `kind`, a span along the axis (`z_nm`;
  for `units`, its `body`'s), a place, the sizes its kind takes, `levels` (drawn from 1, 2
  and 3), `turns`, a `does` sentence with what it rests on, its `proteins` and, for level 3,
  `subunits` (each protein with a `count`, or none and why).
  - **Kinds**, each with its height or length given by its span: `ring` (`across_nm`,
    optionally `bore_nm` and `step_nm`); `units` (`count`, `radius_nm` where a unit meets
    what it stands round, a `body` with its own span, optionally an `arm` to a layer); `rod`
    (`across_nm`, `from`, `to`); `tube` (`across_nm`, optionally `bore_nm`, and for a bent
    one `length_nm` along its own line and `bend`); `band` (`between` two parts). A kind the
    viewer does not draw is a breach.
  - **Places**: `in` a layer; `under`, `inside` or `within` another part; `from` and `to`
    along the axis; `between` two parts. A place agrees with the spans and the bores: a part
    *in* a layer overlaps it, one *under* another ends below it, one *inside* or *within*
    another fits its bore (and *within* lies inside its span), a rod runs from the top of
    what it starts at to the middle of what it ends in, and parts set end to end meet.
- **Every number has one basis**, and only one:
  - `says`: the keys of sentences in `sentences`, of permissive sources;
  - `read`: a number from an open paper with no licence declared (below): the source and
    `where` in the paper it stands, in the file's own words;
  - `pdb`: a value from an entry of the Protein Data Bank: the `entry`, and `what` was read
    there, in the file's own words: the copies the entry's record states for an entity, or
    a size from its coordinates, said to be the reader's own reading (not checked against
    the paper that describes the entry). The entry stands in `structures`;
  - `choice`: a sentence that says it is the picture's choice, and why; a choice within a
    range the sentences give names them in `within_says`;
  - `derived`: how it is worked out, naming in `from` or `from_says` what from.
- **`measured_in`** gives the organism as the sentence itself names it (`E. coli`,
  `Salmonella`, `E. coli and Salmonella`, `bacteria in general`), or `not stated`; for a
  `read` number, `other bacteria: ` and their names, as the paper states them; for a `pdb`
  value, the organism as the entry's record states it (`other bacteria: ` and its name where
  it is neither the species nor Salmonella). A name in
  `measured_in` stands in the sentence, or in the heading of the figure the sentence is the
  caption of (its `where`). It is never read from a paper's references. The page shows it
  beside the number.
- **`sentences`** are keyed. Each names its source and holds the words as the saved text
  has them. `tools/check_machine_sources.py` stops if a saved text no longer holds one.
- **`sources`** are as in a species file (`text`, `doi` or `url`, `licence`, `class`,
  `accessed`), with `saved`, the file under the datasets folder the check reads. A source
  has one of two standings:
  - **permissive** (CC BY, CC0): its sentences may be quoted in the file, and the check
    holds them against the saved copy and its record's licence;
  - **open paper, numbers only** (`standing`), by the user's ruling of 16 November 2026:
    "you can use any numbers from open papers even if no licence is decrlared". Its class
    is `no stated terms`. The file holds the number, the citation with its DOI and where in
    the paper the number stands, in the file's own words, and never the paper's text. A copy
    kept to check against lies under the datasets folder with a MANIFEST that says it is
    kept for analysis and not redistributed; the check finds the number's term (`find`)
    there. Each such source is named in the register of `tests/licence_classes.test.mjs`.
    The register is empty today: a paper whose own text states terms (for academic
    research, say) is not one with no licence declared, and waits for a ruling.
- **`disagreements`** lists every case where sources give different numbers for one thing:
  all of them, with what is drawn and why. Nothing is averaged without saying so.
- **`motion`** names what may move: which parts turn about the machine's axis and which
  about their own line, the way and where it is seen from, the rate it is drawn at with its
  basis, the top rate the picture names, what shows the turn at each level, where the marks
  give way to a blur, the arrowhead, and what is held still and why. A part not named there
  never moves. What may move and what the picture says of it is rule 13 of
  `schema/QUANTITY_LAYERS.md`.
- **Structures.** A value may be taken from an entry of the Protein Data Bank (its terms:
  CC0 1.0, saved under the datasets folder, `ecoli/wwpdb-terms/`) once the entry is saved
  with its record, and its organism is stated beside the value as the entry's own record
  gives it, as a size measured in Salmonella is flagged. `structures` lists each entry
  used with its `title`, `organisms` and `method` as its record states them, and the
  source `pdb` names the folder they are saved in; `tools/check_machine_sources.py` holds
  the list to that folder's MANIFEST. No shape is taken from a structure yet, and no value
  from EMDB.
- **The rate's words.** Where the rate drawn is the picture's choice, `drawn.words` and
  `rate.words` say it in the picture's statement as the sentences allow: the rate drawn,
  that it is the picture's choice within the range they give and in which organism, and the
  top rate.

## In the page

`src/lenses/machine_view.js` in the Cell view, since 16 November 2026.

- **Look closer.** The panel of the foot the machine stands at offers "Look closer", after
  its door into the Protein atlas; the scale rail has the machine's stop below one cell.
  The camera flies to the foot nearest the press (or, from the rail and the address, the
  one that faces the camera most), from the side that foot faces; as it comes close the cell
  fades out and the machine fades in, drawn at its true size, upright (outside up), so that
  the scale bar stays true and reads in nanometres. It is framed in the part of the picture
  a panel leaves, and framed again when a panel opens or closes while the camera stands
  where the frame put it.
  "Back to the cell" (in every panel of the machine), the rail, Escape with no panel open,
  or zooming out far enough brings the cell back. The address names it with
  `machine=<machine id>` and `detail=1|2|3`; opened so, it stands until the visitor
  chooses. The card offers the level of detail in place of the size mode.
- **Parts.** Each can be chosen as `machine:<machine id>:<part id>`. Its panel gives what it
  does, its proteins, each size with its basis and the organism, what is the picture's
  choice, where the sources disagree, and a door into the Protein atlas that names the
  part's proteins (`ids`): the atlas lights the machine's set and, of it, those proteins.
- **Its statement.** "Illustration: not a run · Cells has no model of this motor" while it
  turns, "Illustration: Cells has no model of this motor" while it stands (with the
  machine's own word for itself), then its way (and "shown still") and its speed (`schema/QUANTITY_LAYERS.md`,
  rule 13), stands on the picture in the flux statement's place, or in the panel or sheet
  in front of it where the picture has no room, for as long as the machine shows.
