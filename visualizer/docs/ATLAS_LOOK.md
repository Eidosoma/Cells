# The species' own proteins: colour and ways around

The user, 16 November 2026: "review the look and feel of the All protein pages, the navigation is a bit
ackward and the look and feel a bit boring, cant we classify more with color, inside outside".

The answer is a page of options for the user to choose from, published as an artifact ("Protein Shelves in
Colour", recorded in `artifacts.json`). **Nothing in it is built into the viewer.** Its pictures are of working
prototypes made in a scratch copy of the viewer's code, taken in headless Chrome with software 3D on 16
November 2026.

**The page is not in git.** It holds 38 pictures and is 2.0 MB, which is more than an options page should add
to the repository. It is kept, with the copy of the code it was pictured from and the tools that build it, in
`/mnt/workspaces/Cells/visualizer-atlas-look-20261116-01/` (`atlas-look.html`, and a `README.md` that says what
each folder is). This note carries its findings, its recommendation and its questions.

## Decided (16 November 2026), and built

The user, the same evening: "lets go with your and adviser recomendartion on the nav questions". So all eight, as
recommended, and built as the page's own (not the prototypes):

1. **Inside and outside are the side of each protein's own membrane**, as the files state. The legend uses each
   shelf's own words when one shelf is shown or in focus ("In the mitochondrial matrix"), and words that hold on
   every shelf for the whole stack ("Beyond its membrane", "In its membrane", "Enclosed by its membrane").
2. **Look A.** Every marker, family and member takes the colour of its side: a family's line the side where most
   of its members sit (as the file states it; right for 96% of the human's proteins, 81% of the planarian's); a
   gathering its side's own colour too (paler, it fell under 3 : 1 as drawn), told by its dashed ring and its
   name; what has no known side stays hollow and grey. What makes a machine Cells has a law for keeps
   its machine's shape and its blue base. Light theme: plum `#57295d` beyond, violet `#4a4cd0` in, burnt orange
   `#a04600` enclosed; dark theme: rose `#efb9e4`, violet `#7c6cf2`, orange `#ef6c1a` (`src/page.css`, `--own-*`).
3. **"Colour" in the legend** offers the side (the default), how the side is known, essentiality where a species
   states it (Syn3A, M. pneumoniae), Cells' laws (one hue, as before), and a small catalogue's other marks: the
   card's "Show by" is folded into it there, and stays for a large catalogue's sets (E. coli's chemotaxis
   proteins and assemblies). A family's line states no basis and no mark, so under those it stays grey and the
   legend says to open it.
4. **The trail, the search in view and the map of the stack** (`src/ui/atlas_nav.js`). The trail says species,
   shelf, side shown alone, the open family ("Opening …" while its proteins are fetched) and the protein; each
   step goes back to it, and its arrow one level. The search, in the trail, finds a protein by gene, name or
   identifier inside a family not yet opened, the families' lines and the shelves; on a phone it opens from
   "Find". The map, a column of bars at the right edge that opens to the shelves' names, stands in for the
   legend's list of shelves.
5. **A names file** beside each large catalogue's members' files (`names.json`, one more published file for each
   of the six large catalogues), written by the page builder from the members' files. With each protein's side
   in it they are larger than the review's estimate: 1.32 MB for the human (1.1 estimated) and 1.81 MB for thale
   cress (1.5), 0.28 to 1.40 MB for the others.
6. **Escape steps back one level of the trail**, in the atlas only: protein, family, side, shelf, the whole stack.
   With one shelf (Syn3A), it also brings the shelf back into view after a protein was flown to.
7. **The light theme's orange and violet were deepened until, as drawn and lit on the graphics card, every side
   stands at least 3 : 1 against the page** (the human's families: violet 3.35, orange 3.36, its gatherings 3.53
   and 3.54; Syn3A's markers 3.61 and 3.72). The light theme's two ramps of "Colour" (how the side is known,
   essentiality) were deepened the same way: as drawn on Syn3A their lightest steps stand 3.39 and 3.38 against
   the page, and their steps are at least 15 apart for every kind of sight (dark theme: 6.19 and 6.20, at least
   17). `tests/palette.test.mjs` holds the tokens to the palette check; `tools/check_shelves.mjs colours` holds
   the sides, the gatherings and the ramps as drawn.
8. **The ring of the other side's colour** on a mixed family: not built, as decided.

With it: a side shown alone is that side of the shelf in focus only (it used to light that side on every shelf);
and the human's 27 entries that the law inventory names only as going with a machine (auxiliary subunits, the
sodium pump's beta subunits, the uniplex's regulators, the pump's FXYD regulators) are drawn plain and say so,
in the inventory's own words (`inventory_roles`, `schema/SPECIES_PROTEINS.md`).

## What the page holds

- **A walk through today's page** as a visitor would take it, for the human, thale cress and Syn3A, on a wide
  window and a phone: each step's presses, camera flights, what lay under the pointer and what the page then
  said, with pictures of the awkward moments. The worst: a protein cannot be found by its gene until its family
  is open ("KCNJ2" finds nothing; "AHA1" finds another protein's family); a family opens with one 900 ms flight
  18 times nearer; going back takes three Escapes and lands on the shelf, not where the visitor began; a side
  pressed for one shelf lights that side on every shelf; on a whole stack a marker is 1 to 5 pixels across and
  every side is drawn in the same grey.
- **What colour can truthfully carry**, from what each species' file states: the side of a protein's own
  membrane for every protein and every family; how the side is known and a measured mark (essentiality) only
  for each protein of a small catalogue and for the members of an open family; Cells' laws as today.
- **Three looks**: A, colour by side on today's shelves; B, the same with the inside's glass tinted; C, a calm
  stack with only the shelf in focus in colour and a small map of the stack.
- **Ways around**: a trail that always says species, shelf, side, family and protein and steps back one level
  (Escape too); one search that stays in view and finds a protein by its gene inside a family not yet opened; a
  small map of the stack in place of the legend's list of shelves. On a phone these are crowded, and the page
  says so.
- **The palettes with their numbers**, checked by a script, not by eye: CIE Lab distances between every pair for
  normal sight and for protan, deutan and tritan (Machado and others 2009, full severity), against the surfaces
  the markers stand on, the law hue and the map's status colours, and WCAG contrast to both page backgrounds.
  Every proposed palette passes as tokens. As drawn and lit, the light theme's orange and violet fall under
  3 : 1 against the page (today's grey markers do too), so the build should settle the light orange by a check
  of drawn colours; a deeper orange is proposed.

## The recommendation

Look A, colour by the side of each protein's own membrane, with "Colour" in the legend offering how the side is
known, essentiality where a species states it, and Cells' laws; then the trail with Escape one level back; the
search in view, with a small file of every protein's name beside a large catalogue's members' files; and the
map of the stack in place of the legend's list of shelves. B's tinted glass can follow as a later choice; C would
take colour from the first view a visitor has. The page ends with eight questions for the user, the first being
whether "inside" means inside a protein's own membrane, as the files state, or inside the cell.

## Where the work is

The review's working files (the scratch copy behind address flags, the palette checker and its numbers, the
pictures and logs, and the hand-over for the coordinator) are in the folder named above, copied from
`out/scratch-atlas/` and `out/handover/atlas-look.md`, which git ignores. The prototypes are not code awaiting
review: building the chosen option is a separate step, with its own tests and click checks, after the user
has chosen.

## The questions put to the user

1. Should "inside" and "outside" mean the side of each protein's own membrane, as the files state, or inside
   and outside the cell? Recommended: its own membrane, with each shelf's words in the legend. For the human the
   two nearly agree (1,890 of the 2,074 proteins outside their membrane are outside the cell), but on the shelf
   "A membrane, not told which" the files cannot say.
2. Which look: A, B or C? Recommended: A.
3. Should colour show the side by default, with "Colour" offering how the side is known, essentiality where a
   species states it, and Cells' laws? Recommended: yes, folding a small catalogue's "Show by" into it.
4. Which ways around? Recommended: the trail, then the search in view, then the map of the stack.
5. May each large catalogue carry a file of its proteins' names beside its members' files (about 1.1 MB for the
   human and 1.5 MB for thale cress before compression), so that the search finds a protein in a family not yet
   opened? Recommended: yes.
6. Should Escape in the atlas step back one level at a time? Recommended: yes, in the atlas only.
7. Drawn and lit, the light theme's orange and violet fall under 3 : 1 against the page. May both be deepened?
   Recommended: yes, settled by a check of the colours as drawn.
8. Should a family whose members sit on more than one side carry a thin ring of the other side's colour?
   Recommended: later.

## What was checked before the page was published

The coordinator read the page's text, looked at each of its 38 pictures, and loaded it in headless Chrome at
1,280, 400 and 360 pixels wide in both themes: no sideways scrolling, no picture missing, both fonts arrived.
Not checked: the prototypes' own controls were drawn, not pressed (the page says so), and the page was not seen
inside the artifact's frame on a phone.
