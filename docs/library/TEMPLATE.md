# How to write a page of the library

Each registered law, kind and operator, and each model with declared structure, has one page in
plain words, at `docs/library/<namespace>/<section>/<name>@<major>.md`
([the design](../LAW_DOCUMENTATION_DESIGN.md); D203). A page opens so that a biologist, a chemist,
a physicist and a computer scientist can each follow it, then gives the declared facts, the
mathematics, the sources, the checks, the status and the links, under fixed headings.

## Writing one

1. **Make it.** `python scripts/library_pages.py --new law cells.<name>@1` (or `kind`, `operator`,
   `model`) writes the skeleton below, with the generated blocks filled in from the declarations
   manifest.
2. **Write the plain layers first,** for a reader outside your field: the plain name, the one
   sentence, "In plain words" and, if the fields name the thing differently, "Seen from each
   field". Then the mathematics, the sources with their marks, and the checks in words.
3. **Render and check.** `python scripts/library_pages.py --write` renders every generated block
   again, the [index](README.md) and the [glossary](GLOSSARY.md)'s "Used by" lines.
   `python scripts/library_pages.py --check` runs the library's five checks, as tier 1 does.

Never edit a generated block by hand: change the declaration, and run `--write`.

## The skeleton

The generated blocks are those between `<!-- generated: NAME -->` and `<!-- /generated -->`.
Everything else is written by hand.

````markdown
# <Plain name> (`<namespaced ID>`)

**In one sentence:** <one sentence that biology, chemistry, physics and computing can each follow>

## In plain words

<what it does, why it matters in a cell, and what it leaves out>

## Seen from each field

- **Biology:** <optional: one line each, where the fields name the same thing differently>
- **Chemistry:** <...>
- **Physics:** <...>
- **Computing:** <...>

## At a glance

<!-- generated: at-a-glance -->

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

<!-- /generated -->

<the equations, each symbol with its unit; the assumptions; the domain and why; what it leaves out>

## Sources

<!-- generated: provenance -->

<!-- /generated -->

<each work with its mark; what was taken from it, the form or the numbers; each departure in words>

## How it is checked

<!-- generated: tests -->

<!-- /generated -->

<in words: the independent reference, the planted error it must catch, and any recorded evidence with its scope; never a level>

## Status

<!-- generated: status -->

<!-- /generated -->

## Links

<!-- generated: links -->

<!-- /generated -->
````

"Seen from each field" may be left out. Further reading, to design notes only, may follow the
last block.

## The rules for writing it

- **The one sentence:** at most 30 words, with no symbols or equations, and units named in words.
  The index and the viewer's Laws library quote it.
- **"In plain words":** at most 150 words. A term that a reader outside your field may not know
  links to the glossary at its first use, such as `[gate](../../GLOSSARY.md#gate)`.
- **Nothing in the plain layers claims more than the Status says.** A page never states a level;
  the Status block copies one from a record, or says "Not stated".
- **Name the mechanism.** Name a protein only to say where a form came from.
- **IDs, field names and file names are always in backticks,** so that GitHub does not turn
  `name@1.md` into an e-mail link.
- **Code and test paths appear only in generated blocks,** so that a file move needs one `--write`
  and no hand edit.
- **Link only to pages that exist.** The generated blocks link another page once the manifest's
  `doc` names it; until then they give its ID in backticks, and so should the hand-written parts.
- **The mathematics uses GitHub math** (`$...$` and `$$...$$`), with each symbol's unit. A piece
  whose mathematics is elsewhere says so in a line that starts `No equations:`, with the reason.
- **Each work in Sources carries a mark:**
  - FT: the full text was read;
  - FT-img: an equation was read from an image of it;
  - ABS: the abstract only;
  - Der: derived here;
  - relayed: taken from a named Cells document that read the work;
  - unread: named, not read.

## How kinds, operators and models differ from laws

| | Law | Kind | Operator | Model |
| --- | --- | --- | --- | --- |
| What it is | Mathematics with no state of its own. Its host keeps its gates | Machinery inside the inner model: it hosts laws and keeps their state and books | A part of the composite's step, with its own state and books, carrying its own law | What a definition names, and what it declares |
| "What it reads and changes" | What it reads; the rows it changes; its gates | Owned state, with axes; readouts; controls; records; the laws it hosts | What it reads, with each read's mode; owned state; its writes into others' fields; view fields and readouts; controls; ledgers; heat and work | Its rows: the pieces it declares or requires, by slot |
| "The mathematics" | Its equations | What the kind computes itself, such as bookings and closures. The rates are its laws' | Its law, and where it acts in the step | None: `No equations:`, and its guide as further reading |
