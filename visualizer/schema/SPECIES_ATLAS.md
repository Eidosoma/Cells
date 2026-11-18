# Species atlas: one species' side of the protein atlas

Status: **fixed for the viewer, 14 November 2026**, so that the planarian catalogue and
the species switch can be built side by side. Revised the same day when the two were put
together: the fourth finding was `not a protein`, which was false for a default current,
a configured slot and a designed protein. The user asked for "a full catalogue of
Planerian proteins" and to "switch between Human and Planerian (later others) atlases".

**Revised 16 November 2026 (format `@2`):** each product gives two facts apart, how it was
found (`found_by`) and what its record is (`entry`). The one word of `@1`, `evidence`, mixed
the two: a product with a reviewed entry was called `reviewed entry` however it was found, so
a page counted 3 of the mouse's 158 products as found by signature when all 158 were. How a
product was found decides what it is a candidate for; how its entry was written never does.

The protein atlas draws the functional units of Cells' law inventory. A unit is a machine
a law acts on; it has no species. What changes with the species is which gene products
would make that machine. A species atlas answers that for one species, for every unit.

This is the viewer's reference data. It is not the engine's protein catalogue, whose
design (`docs/PROTEIN_CATALOGUE_PLAN.md`, stage 3) has not begun and belongs to the lead.

## File

`data/proteins/atlases/<species id>.json`

```json
{
  "format": "cells.visualizer.species_atlas@2",
  "species": {
    "id": "planarian",
    "label": "Planarian",
    "organism": "Schmidtea mediterranea",
    "taxon": 79327,
    "plain": "One sentence on the animal and why it is here."
  },
  "made": "2026-11-14",
  "method": ["One line per step of how the entries were found."],
  "sources": [
    {"name": "UniProt", "url": "https://www.uniprot.org/", "release": "2026_04",
     "accessed": "2026-11-14", "licence": "CC BY 4.0", "class": "permissive", "cite": "…", "holds": "what was taken"}
  ],
  "not_copied": "What was read but not copied, and why.",
  "units": {
    "U36": {
      "finding": "different family",
      "note": "A plain sentence a reader outside the field can follow.",
      "products": [
        {
          "name": "Innexin",
          "gene": null,
          "role": null,
          "ids": [{"db": "uniprot", "id": "A0A000000"}],
          "length": 412,
          "found_by": "family signature",
          "entry": "unreviewed",
          "evidence_note": "Which signature, search or paper, in a few words.",
          "citation": null
        }
      ]
    }
  },
  "extra": []
}
```

## Rules

- **Complete.** `units` has one entry for every unit of the inventory snapshot
  (`data/proteins/inventory.snapshot.json`), keyed by the inventory's unit id. A unit with
  nothing found still has an entry that says so.
- **`finding`** is one of:
  - `found`: gene products of the same family as the unit's candidates were found. It asks for a
    family that makes the machine itself: a protein that carries only the signature of an
    accessory family (a regulator, a subunit that forms no channel or pump by itself)
    does not make a unit found, and the note names it;
  - `different family`: the species builds this machine from another protein family
    (the note names both);
  - `none found`: the search found nothing; the note says what was searched;
  - `nothing to look for`: the inventory names no natural gene product for the unit, so
    nothing was searched. The unit is a lumped property, a default form of a current, a
    slot that each configuration fills, or a designed protein.
- **`found_by`** on each product says how it was found, and nothing else:
  - `family signature`: its own record (a UniProtKB entry, an archived sequence, a gene
    model) carries the InterPro signature of a family that makes the machine itself;
  - `accessory signature`: its own record carries only the signature of a family that goes
    with the machine (a regulator, or a subunit that makes no channel or pump by itself).
    It is listed with the machine and is no candidate for the machine's own work;
  - `named in a publication`: a paper names this gene or protein in this species;
    `citation` is then required;
  - `similarity search`: found by sequence similarity to a named protein of another
    species.
  A product found by `family signature` or `similarity search` is a candidate, never an
  established counterpart, and the atlas says so. One found by `accessory signature` is a
  candidate for no machine's own work. A product listed in several units is found the same
  way in each; a build stops where it would not be. A signature broader than the family it
  is asked for (a table's `broader`: IPR000920, InterPro's "Myelin P0 protein-related",
  beside the sodium channels' beta subunits, since 16 November 2026) finds no product: the
  unit's note names what carries it and says why none is listed. Under `extra`, which matches no unit,
  `family signature` means the signature of the family the product is listed for, and it is
  a candidate for no unit.
- **`entry`** on each product says what its record is, read from the record the build read:
  - `reviewed`: a UniProtKB entry that a curator reviewed;
  - `unreviewed`: a UniProtKB entry annotated automatically, by rule systems and prediction
    programs;
  - `genome annotation`: a gene model, or a protein of a genome record, with no UniProtKB
    entry of its own.
  A reviewed entry says how the entry was written. It makes no product more of a
  candidate, and no count of reviewed entries may be read as one of products more sure to
  do a unit's work. `found_by` is never set from `entry`.
- **Which species uses which** (16 November 2026):

  | Species | `found_by` | `entry` |
  | --- | --- | --- |
  | Fruit fly, mouse, thale cress (`tools/lib/proteome_shelves.py`, `find_units`) | `family signature`, `accessory signature` | `reviewed`, `unreviewed` |
  | Planarian (`tools/build_planarian_atlas.py`) | `named in a publication`, `family signature`, `accessory signature` | `unreviewed`, `genome annotation` (gene models of WormBase ParaSite) |
  | E. coli (`tools/build_ecoli_atlas.py`), under `extra` only | `family signature`, `accessory signature` | `reviewed` |
  | M. pneumoniae (`tools/build_mpneumoniae_atlas.py`), under `extra` only | `family signature` | `reviewed` |
  | Syn3A (`tools/build_syn3a_atlas.py`), under `extra` only | `named in a publication`, `family signature` | `genome annotation` (its genome record's proteins) |

  No species uses `similarity search` today; no similarity search was run for any.
- **`ids`** name database entries; `db` is `uniprot`, `pdb`, or a species database named
  in `sources`. The viewer builds links from them; the file holds no URLs per product.
- **`citation`** is `{"text", "doi", "pmid"}` with at least `text`.
- **`extra`** (optional) lists proteins of the species that bear on what the atlas draws
  but match no unit, each a product with a `why` sentence. It is not a proteome.
- **Licences.** Nothing is copied from a source whose terms forbid redistribution or
  commercial use; such a source may be named and linked. `sources` states each licence,
  and the file passes the same checks as the snapshot: no machine paths, no host names.
- **Classes.** Every entry of `sources` and every `citation` carries a `class`:
  `permissive` (CC BY, CC0, or a plain statement that no restriction is placed on use),
  `non-commercial` (a CC BY-NC licence of any kind) or `no stated terms` (the project's
  rule, D173, 15 November 2026). The atlas holds no value and no statement from a source
  that is not permissive: every entry of `sources` is permissive. A paper of another
  class may be cited for a name only. The product then carries `name_record`, the
  permissive record in which the name stands too (`source`, the name of an entry in
  `sources`, and `id`), and none of the paper's findings is repeated.
  `tests/licence_classes.test.mjs` holds every atlas to it.
- **No claim about the engine.** The engine's laws are the same for every species. A
  species atlas never says the engine models a species' protein.

## Reading an older file

A file of format `cells.visualizer.species_atlas@1` gives each product one word,
`evidence`. The builder reads it as the two facts, and the side the word does not cover is
`not stated`, never guessed:

| `evidence` (`@1`) | `found_by` | `entry` |
| --- | --- | --- |
| `reviewed entry` | `not stated` | `reviewed` |
| `named in a publication` | `named in a publication` | `not stated` |
| `family signature` | `family signature` | `not stated` (it covered gene models and genome records as well as unreviewed entries) |
| `similarity search` | `similarity search` | `not stated` |

`not stated` is a word of the reader only: a file of format `@2` may not give it, and gives
no `evidence`. The repository's files are all `@2` since 16 November 2026.

## In the scene

The builder puts each species atlas into the scene's `proteins.atlases`, the human one
made from the inventory snapshot's own products, and gives every unit its products per
species. The view switches between them; the units drawn do not change.

- **Each atlas counts its products once** (a product listed in several units counts once):
  `counts.products`; `counts.candidates`, those found by `family signature` or
  `similarity search`; `counts.reviewed`, those whose entry is `reviewed`; and the lists
  `found_by` and `entries`, a count for each word. The words are the overlay's
  (`data/proteins/overlay.json`, `species.found_by` and `species.entry_kinds`) and the scene
  carries them as `proteins.product_found_by` and `proteins.product_entries`.
- **The page says the two apart:** how the products were found, then what their records
  are, and that a reviewed entry says how the entry was written, not that the protein does
  a unit's work. Each product's panel gives its `found_by` as its tag, then a line on what
  it is a candidate for, then a line on its record.

## A unit left out of the picture

A unit of the inventory may be left out of the picture for now, by a flag on it in the
atlas's overlay (`data/proteins/overlay.json`, `units.<id>.left_out`). Decided by the user
on 15 November 2026 for the engineered protein cage (U48): the atlas is a picture of a
cell's machines, and a designed protein is not one of them.

```json
"left_out": {
  "since": "2026-11-15",
  "says": "an engineered protein cage",
  "reason": "it is a designed protein, not a part of a cell",
  "why": "the fuller record, for whoever maintains the overlay; never shown",
  "empties": {"district": "assembly", "site": "cytoplasm", "evidence": "designed protein"},
  "rewords": [{"in": "species.findings", "id": "nothing to look for", "field": "description", "to": "…"}]
}
```

- **The inventory keeps the unit, and so does every species' file.** `units` still has
  one entry for each unit of the inventory, the one left out included; the builder reads
  and checks it like any other. Nothing is deleted anywhere.
- **The scene does not draw it.** The unit is no part of the scene and no link points at
  it. A district, a site and a kind of evidence that only it holds go with it; `empties`
  says which, for the reader, and the builder warns if that is not what happened.
- **Counts on the page are of what is drawn.** `proteins.counts.units` and every atlas's
  `counts.units`, `with_products` and `findings` leave the unit out;
  `proteins.counts.inventory_units` still gives the inventory's number. The stamp's check
  of the law records is the inventory's and covers them all.
- **The page says so, once in each place a count stands.** The atlas's `summary` ends
  with a sentence made from the flag ("The inventory has 49 units. One of them, an
  engineered protein cage, is left out of the picture for now: it is a designed protein,
  not a part of a cell."), and each atlas's `method` ends with the same, adding how many
  are shown and counted. `says` is how the page names the thing and `reason` its short
  reason; both are needed, with `since`, a date.
- **Wordings.** `rewords` gives the text that stands in, while the flag is there, for a
  text of the overlay that names the thing (`to` null takes the text away). The overlay's
  own text is not edited, so nothing has to be put back by hand.
- **The scene names what is left out in one list,** `left_out` at its top: `id`, `kind`,
  `label`, `since`, `says` and `reason`, for units and for capabilities of the cell map
  alike (`schema/SPECIES.md`).
- **Removing the flag brings everything back** as it was: the unit, its links, its
  district, the counts and the texts. A test builds the scene both ways.
