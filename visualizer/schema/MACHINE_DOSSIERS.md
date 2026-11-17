# The Machines catalogue's dossiers: the evidence gathered for each machine of each species

Status: **written for the viewer, 17 November 2026**, beside the Machines catalogue
(`schema/MACHINE_CATALOGUE.md`). The gathering was asked for on 17 November 2026: which molecular
machines each species of the page has, their parts as the species' own proteins in the Protein
atlas, how many a cell holds where an open paper gives a number, and which Protein Data Bank entries
a size can be measured from. Nothing here says that Cells models a machine: no machine is in the
engine (D209).

## Files

| File | Made by | Holds |
| --- | --- | --- |
| `data/catalogue/gather.json` | Hand | The kinds looked for (id, label, group, a plain line), the groups proposed beside the catalogue's, and for each species: its UniProt proteome, the Gene Ontology terms (and keywords) that name each machine's proteins, an entry chosen by hand with why, the RNA chains of an entry that are parts, the entries other agents chose (to compare), and the numbers per cell with the paper and the place in it |
| `data/catalogue/dossiers/<species>.json` | `tools/gather_machines.py` (generated: do not edit) | One dossier per machine, and `by_protein`: for each protein of the atlas, the machines it is a part of |

```bash
python3 -I tools/gather_machines.py fetch <species>        # asks RCSB, UniProt and Europe PMC for what is not saved
python3 -I tools/gather_machines.py fetch-files <species>  # the chosen entries' files, where no folder holds them
python3 -I tools/gather_machines.py build                  # writes the dossiers from the saved answers alone
python3 -I tools/gather_machines.py check                  # fails if a dossier is not what build writes
```

Downloads go under the datasets folder (default `/mnt/datasets/Cells`), each source in a folder of the
tool's own with a MANIFEST (address, time, SHA-256, and the body of a POST beside its answer):
`<species>/rcsb-machines-g/`, `<species>/wwpdb-<kind>-g/`, `<species>/europepmc-machine-counts-g/`,
and `human/uniprot-human-keywords-g/`. A folder another agent made is read, never written.

## Rules

- **Proteins, by tier.** A protein is named with the machine where the species' reviewed UniProt
  entry carries the machine's Gene Ontology term or a narrower one (by is_a and part_of). `part`:
  named with it (and carrying one of the machine's UniProt keywords, where gather.json gives them)
  and held by the chosen entry as an entity of the species; or, for a machine named by a seed
  entry, a protein of the species in that entry. `part by keyword`: named with it and carrying the
  keyword, and not held by the entry. `named`: named with it by the term alone. A protein of the
  species that the entry holds and the term does not name is not in the list: it is counted under
  the structure (`in_entry_only`) and left out of the measure. No protein is matched by a name.
- **The join.** Each protein carries the atlas's own `id` (for E. coli and the human, the UniProt
  accession) and `in_atlas`; `join` counts the parts and all, and lists what the atlas lacks.
  `by_protein` maps each part (of either part tier) to its machines, with the tier: it is what the
  atlas reads to say "part of" on a protein.
- **The structure.** Candidates are the experimental entries in which a polymer entity from the
  species (by the entity's source organism and its lineage) is, by RCSB's mapping, one of the
  machine's proteins. They are ranked by a stated rule (each dossier's `rules.structure`); gather.json
  may name another and says why. The entry's own file is checked: its entities, and the reference
  each gives (`file_reference`, beside RCSB's mapping, which the join uses). `measurable` speaks only
  of the proteins the entry holds: their residues with coordinates add up to at least 70 per cent of
  them; how much of the machine the entry holds is `whole.present` of `whole.proteins_wanted`.
  `compared` gives the rank of entries other agents chose. The file is read from the folder
  gather.json pins (`held`), else from the tool's own folder, else from any folder that lists it.
- **The measure call.** `measure` is one call of `tools/measure_particle.py --machine`:
  the file, `--exclude` for every entity that is not the machine (nucleic acids that are not its
  parts, other organisms' proteins, partners of the species), `--part NAME=ENTITY,...` for the rest,
  by sub-term or keyword where gather.json gives them, else by gene, and a frame where two parts
  name one. Where the first biological assembly holds other chains than the deposited model, the
  assembly's file is the one named. A size so measured is the viewer's own; the database states none.
- **Per cell.** A number of an open paper's running text, with what it counts, in what cell, the
  paper (`source`, its licence as Europe PMC's record states it) and the section and paragraph
  (`where`); the tool finds each number there in the saved full text. No text, figure or data file
  of a paper is kept. A fact of the species' file is pointed to, not copied.
- **Sources** carry `licence` and `class` as `tests/licence_classes.test.mjs` defines them; whatever
  a value rests on is permissive. The file holds no clock time and no path of this machine.

## What the catalogue would read (the proposal to `schema/MACHINE_CATALOGUE.md`)

The smallest addition, for `tools/build_catalogue.py`:

1. **Admit a machine from a dossier.** A kind of a species with a dossier is named by the dossier's
   `named.text` and its sources (the Gene Ontology and UniProt), in place of a capability's note,
   where the species' file names none. The kinds, labels and plain lines of gather.json join the
   overlay's; the groups `dna`, `folding` and `traffic` are proposals for the overlay.
2. **Its proteins** from the dossier's `proteins` (tiers `part` and `named`, each said as such), in
   place of a shelves mark, where the species' shelves give none.
3. **Its count** from the dossier's `per_cell`, where the species' file gives none, each number with
   what it counts and its source.
4. **Its size** stays the measure's (the overlay's `measures`): the dossier gives only the call.
5. **The atlas** reads `by_protein` to say on a protein: "part of <machine>".
