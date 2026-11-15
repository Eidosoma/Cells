# Species atlas: one species' side of the protein atlas

Status: **fixed for the viewer, 14 November 2026**, so that the planarian catalogue and
the species switch can be built side by side. Revised the same day when the two were put
together: the fourth finding was `not a protein`, which was false for a default current,
a configured slot and a designed protein. The user asked for "a full catalogue of
Planerian proteins" and to "switch between Human and Planerian (later others) atlases".

The protein atlas draws the functional units of Cells' law inventory. A unit is a machine
a law acts on; it has no species. What changes with the species is which gene products
would make that machine. A species atlas answers that for one species, for every unit.

This is the viewer's reference data. It is not the engine's protein catalogue, whose
design (`docs/PROTEIN_CATALOGUE_PLAN.md`, stage 3) has not begun and belongs to the lead.

## File

`data/proteins/atlases/<species id>.json`

```json
{
  "format": "cells.visualizer.species_atlas@1",
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
          "evidence": "family signature",
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
  - `found`: gene products of the same family as the unit's candidates were found;
  - `different family`: the species builds this machine from another protein family
    (the note names both);
  - `none found`: the search found nothing; the note says what was searched;
  - `nothing to look for`: the inventory names no natural gene product for the unit, so
    nothing was searched. The unit is a lumped property, a default form of a current, a
    slot that each configuration fills, or a designed protein.
- **`evidence`** on each product is one of:
  - `reviewed entry`: a curated database entry for this species;
  - `named in a publication`: a paper names this gene or protein in this species;
    `citation` is then required;
  - `family signature`: an unreviewed entry carrying the family's sequence signature;
  - `similarity search`: found by sequence similarity to a named protein of another
    species.
  A product found by signature or similarity is a candidate, never an established
  counterpart, and the atlas says so.
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

## In the scene

The builder puts each species atlas into the scene's `proteins.atlases`, the human one
made from the inventory snapshot's own products, and gives every unit its products per
species. The view switches between them; the units drawn do not change.

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
