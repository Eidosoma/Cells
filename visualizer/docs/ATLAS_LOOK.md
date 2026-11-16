# The species' own proteins: colour and ways around (options)

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
