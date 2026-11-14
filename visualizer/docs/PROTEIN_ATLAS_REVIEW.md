# Protein atlas base data: a review against main

**Status: read-only review by the visualizer session, 14 November 2026, for the lead.** The
user asked: "are we only modeling 49 functional units has nothing been added?" The review
compares the law inventory behind the protein atlas with the engine on main. It changed
nothing in the engine or the inventory. What belongs in the inventory is the lead's to
decide; this note reports what was found and how sure each finding is.

| | |
| --- | --- |
| Inventory | `cells.protein_catalogue.law_inventory@2`, made 12 November 2026 at `fec863f` (evidence: `/mnt/workspaces/Cells/protein-catalogue-20261111-01/law_inventory_v2.json`) |
| Compared with | main at `ced45c87` (14 November 2026) |
| Method | The inventory's own census, repeated on main |

## Answer

**Within what the inventory counts, 49 is still everything.** No channel, pump,
transporter, junction-channel or assembly law has been added, removed or changed since
12 November. That finding is firm.

The engine itself has grown by 25 versioned identifiers, 12 of them operators. All fall
outside the inventory's scope by its own exclusion reasons, except one borderline case
(secretion and uptake) and one the lead may want to list (the bridge between daughters).

## How it was checked

- **The census reproduces.** The inventory's method gives 778 identifiers at `fec863f`,
  its stated total, and 801 on main.
- **All 79 law identifiers are still present,** each in the file the inventory names or,
  for two, elsewhere in the engine as before.
- **No law code changed.** Of the 31 law files only `processes/source_electrochemistry.py`
  differs, by 8 docstring lines.
- **No newer inventory exists.** The evidence folder holds v1 and v2 only. The plan still
  reads "stages 1 and 2 done, design not begun", and stage 3 is held under D145.
- **No module builds a new identifier.** The static evaluator finds the same 8 built
  channel identifiers at both revisions.

## What the engine gained since the inventory

| Identifier | What it does | Reading |
| --- | --- | --- |
| `scheduled_species_exchange@1` | Secretion and uptake of a neutral species across a membrane patch. Its route laws (`flux`, `first_order`, `saturable`) carry no versioned identifier | **Unclear: for the lead.** Closest to U46, the declared transporter. Its design says these laws "name no protein", so at most a 50th, generic unit |
| `cytoplasmic_bridge_closure@1` | A closing aperture between two daughter cells, run as a junction with free cytoplasmic diffusion | Probably outside, by the injury exclusion ("not a protein population"). It could be listed as a lumped unit with no protein, as U35 is |
| `membrane_entity_state@1`, `scheduled_membrane_insertion@1` and `@2`, `isopotential_partition@1` | Hold, add and split membrane area, capacitance and population numbers | Outside, by the redistribution exclusion: they act on units' abundance and are not units |
| `local_species_reactions@1` | Reactions on the shared inventory, including `michaelis_menten` with an optional catalyst species | Outside, as reaction networks are. A catalyst is an enzyme, which the scope's list of units does not cover |
| `scheduled_species_turnover@1` | Production and first-order clearance at a node | Outside: chemistry |
| `electrode_current_injection@1` | An electrode's scheduled current | Outside: a prescribed control |
| `restricted_cleft_lumen@1` and `@2` | A cleft compartment that fills as it grows | Outside: geometry |
| `scheduled_cell_replacement@2` | Replacement over water | Outside, as `@1` is |
| Seven step-method names | How each operator advances | Outside: numerics |
| `resolved_pump_composite@1`, its readout and domain names, `cells.checkpoint_continuity@1` | Model, readout, domain and checkpoint names | Outside |
| `emt_mirna_pair@1`, `emt_mirna_pair_pure_readouts@1` | Renames of the two `bitsey_*` identifiers | Already accounted for |

## For the lead

1. **Classify the two open items:** the exchange routes (a 50th generic unit, or outside)
   and the bridge between daughters (a lumped unit with no protein, or outside).
2. **Unversioned laws are invisible to an identifier census.** The exchange routes and the
   reaction laws have no `@n` identifier. A next inventory needs another way to find them.
3. **The catalogue hook exists and is unused.** Membrane-state populations declare a
   `functional_unit` and an optional catalogue reference; species carry a reference and a
   kind of evidence. Only unit tests set one, against a `test_catalogue`.
4. **Two evidence vocabularies.** The engine's species code names four kinds of evidence
   (`label_only`, `expressed_isoform`, `native_current`, `model`); the inventory uses seven.
5. **Scope is an open question for the user.** The secreted-species design says extending
   the catalogue to secreted proteins is "for the user". Enzyme catalysts in the reactions
   operator raise the same question.

## What the inventory now misstates

Only names. `bitsey_emt_pair@1` became `emt_mirna_pair@1` (`135020d7`). That touches two
function records, the notes of U37 and U38, one exclusion entry and finding 6. The atlas
applies the rename when it builds its page, and names it.

## What "49" counts

A functional unit is one assembled molecular machine that a law acts on, such as a Kv1.5
channel. A law is one rule for how that machine behaves. A gene makes one protein chain
of it.

- **80 laws make 49 units** because 20 units have two or more alternative laws; 13 of the
  laws are reduced (Morris-Lecar) forms.
- **By kind:** 32 channels, 5 leaks or lumped permeabilities, 4 transporters, 3 pumps,
  3 junction channels, 1 release channel and 1 protein cage.
- **By naming:** 29 name a protein, 4 are candidates and 16 are generic.

## Units in use

- **E07-v1** runs 5 of the 49: NaV1.2, Kir2.1, the sodium-potassium pump, the generic gap
  junction and the constant-field permeability.
- **The division worlds** use only the constant-field permeability from the inventory.
  Their membrane-state operator declares no populations.
- Every one of the 79 laws is named by at least one config, driver or test. That is not
  the same as having run in a registered experiment. The parity ladder and the other
  experiments were not traced.

## What the atlas now says

- Its card gives the count the inventory's way: 25 identifiers gained, not 35. The first
  count also took unquoted shorthand in comments (`insertion@1`, `lumen@2`, `water@1`).
- It says a review found no channel, pump, transporter or junction law among them, and
  that one case is the lead's to classify. If the engine gains more, the card says how
  many are unreviewed.
- A possible addition, not made: mark the units a judged experiment ran.

## Not determined

- How the lead would classify the two open items.
- Whether work newer than main adds unit laws. The folders `closed-compartment-*` and
  `inventory-coupling-*` exist, but the coupling operator is not in `src` on main.
- Whether further unversioned law-like functions exist beyond the operator modules read.

## Also noticed, outside the atlas

`docs/CURRENT_PLAN.md` lists the closed internal compartment (FR-1) in the execution
gate's table, while the commit that logged it (`b8d87849`) says the composition gate. The
architecture map follows the file.
