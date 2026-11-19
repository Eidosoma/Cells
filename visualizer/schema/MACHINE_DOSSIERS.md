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
| `data/catalogue/gather.json` | Hand | The kinds looked for (id, label, group, a plain line), the groups proposed beside the catalogue's, and for each species: its UniProt proteome, the Gene Ontology terms (and keywords) that name each machine's proteins, an entry chosen by hand with why, the RNA chains of an entry that are parts, the entries the catalogue measures (to compare), and the numbers per cell with the paper and the place in it. A species with no curated record of its machines (`route: family`) names its reference species and its atlas table instead |
| `data/catalogue/dossiers/<species>.json` | `tools/gather_machines.py` (generated: do not edit) | One dossier per machine, and `by_protein`: for each protein of the atlas, the machines it is a part of |
| `data/proteins/planarian/interproscan.json`, `interproscan_added.tsv` | `tools/read_planarian_scan.py` (generated: do not edit) | The planarian's own scan, read by a dossier by family where gather.json's `atlas.scan` names it: its record, and the entries it added to each line, each with its databases (`docs/PLANARIAN_ATLAS.md`) |

```bash
python3 -I tools/gather_machines.py fetch <species>        # asks RCSB, UniProt and Europe PMC for what is not saved
python3 -I tools/gather_machines.py fetch-files <species>  # the chosen entries' files, where no folder holds them
python3 -I tools/gather_machines.py build                  # writes the dossiers from the saved answers alone
python3 -I tools/gather_machines.py check                  # fails if a dossier is not what build writes
```

Downloads go under the datasets folder (default `/mnt/datasets/Cells`), each source in a folder of the
tool's own with a MANIFEST (address, time, SHA-256, and the body of a POST beside its answer):
`<species>/rcsb-machines-g/`, `<species>/wwpdb-<kind>-g/`, `<species>/europepmc-machine-counts-g/`,
`human/uniprot-human-keywords-g/`, `<species>/uniprot-<species>-subunit-g/`, `<species>/complex-portal-g/` and
`<species>/paxdb-g/` (the files gather.json lists under `downloads`). A folder another agent
made is read, never written. An answer of no content (RCSB's 204, no entry) is written down by the
tool and its MANIFEST line says so.

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
- **Which entries may stand for the machine.** An entry is taken only where it holds at least two
  of the proteins sought (or the one, where one is sought), and at least one of them that no other
  machine of the species seeks: an entry of one protein of a larger machine, or one that holds only
  subunits two machines share (the three RNA polymerases' common subunits), is named in
  `no_structure` and not taken.
- **An entry of another machine is never a pick.** gather.json's `entries_left_out` lists, for a
  species and a machine, the entries left out of its ranking, each with a dated line and the entry's
  own title, which the tool checks against the saved answer; a dossier says what was left out
  (`left_out`). Every pick, and every entry named elsewhere, carries the entry's own `title`. An entry
  kept for a machine that holds it among other complexes (a supercomplex, a ribosome with the
  polymerase on it) is listed in `entries_noted`, and its pick carries `holds_more` ("the machine
  among other complexes", with how many entities the measure leaves out), so that nobody measures the
  whole entry as the machine.
- **A species whose saved UniProt copy holds every entry** (`uniprot.scope: all`: the mouse, the
  fruit fly, thale cress) is read through the entries its atlas keeps, one for each gene, reviewed
  or not. Where none of its own entries stands for a machine, `structure_elsewhere` names the
  entry of the species gather.json gives as `elsewhere` (the human), with its organism.
- **The measure call.** `measure` is one call of `tools/measure_particle.py --machine`:
  the file, `--exclude` for every entity that is not the machine (nucleic acids that are not its
  parts, other organisms' proteins, partners of the species), `--part NAME=ENTITY,...` for the rest,
  by sub-term or keyword where gather.json gives them, else by gene, and a frame where two parts
  name one. Where the first biological assembly holds other chains than the deposited model, the
  assembly's file is the one named. A size so measured is the viewer's own; the database states none.
- **Copies, in UniProt's words.** `uniprot_subunit` gives, for each part, the sentences of its UniProt
  SUBUNIT comment that say how many copies go together (a word for a homo-oligomer, a ring named by
  its number, a number of subunits), as UniProt writes them, its evidence tags left out (CC BY 4.0).
- **Named sub-assemblies** (`sub_assemblies`): the narrower Gene Ontology terms the parts carry,
  each with its parts, and the Complex Portal's complexes whose members are all parts of the machine
  and fewer than all, each with its members and stoichiometry. `uniprot_fractions` gives the
  fragment or fraction of the machine that a part's own UniProt SUBUNIT comment places it in (the
  human's complex I: its FP and IP fragments and its hydrophobic fraction), in UniProt's words; a
  sentence that lists other proteins by name is not read.
- **The Complex Portal** (`complex_portal`, CC0 1.0 as its 2022 paper states): its curated complexes
  of the species that hold parts of the machine, matched by UniProt accession (the most parts
  first), each with its stoichiometry for those parts (0 where it gives none).
- **A held source.** gather.json's `sources_held.<name>` has `use` and a dated line saying why. While
  `use` is false, no step reads the source: `fetch` skips its downloads, and `build` writes no field
  that rests on it (for the Complex Portal: no `complex_portal`, no `sub_assemblies.complex_portal`,
  no source entry); what rests on other sources stays (the Gene Ontology's sub-assemblies). Its saved
  folders are kept. Switching it on is one edit and a rebuild. The Complex Portal was held on
  17 November 2026, because its licence is stated in its team's paper and not on its site; the user
  decides.
- **PaxDb** (`paxdb`, CC BY 4.0 as its home page declares): each part's abundance in one PaxDb
  dataset (its id and name kept), in parts per million of the dataset's protein molecules, joined by
  an identifier (E. coli's locus; the human's UniProt entry name, by PaxDb's own links). It is said
  as that database's value, never as copies in a cell.
- **Per cell.** A number of an open paper's running text, with what it counts, in what cell, the
  paper (`source`, its licence as Europe PMC's record states it) and the section and paragraph
  (`where`); the tool finds each number there in the saved full text. A number written with a power
  of ten keeps `written` and `scale` (`value` is `as_written` times `scale`); one a paper cites from
  another says whom (`cites`). No text, figure or data file of a paper is kept. A fact of the
  species' file is pointed to, not copied.
- **A species by family** (`route: family`: the planarian by the human, Syn3A and M. pneumoniae by
  E. coli). Each part of the reference's machine has its narrowest InterPro families (entries of the
  type Family under which no other Family entry of the same protein lies); a protein of the species'
  atlas table whose signatures include one is a candidate for that part (`proteins`, the one tier
  `candidate by family`, with `families`, `stands_for` and `how`); `looked_for` lists every part of
  the reference (with its tier there) and, for each of its narrowest families, how it was matched:
  `narrowest` (some line carries it); `broader` (the family is numbered above the highest entry that
  some group of the table's lines carries, so it is taken to be newer than that group's scan, and the
  nearest broader Family that some line carries is used); `not in the table` (no line carries it,
  though a scan that could show it was run: this says what the table holds, never that the species
  lacks the protein); `cannot tell` (newer than a scan, and no broader Family is carried). A candidate
  is never called the part or a counterpart.
- **A species' own scan** (the planarian since 18 November 2026: `atlas.scan` in gather.json names
  the scan's record and its table of added entries, both written by `tools/read_planarian_scan.py`;
  `docs/PLANARIAN_ATLAS.md` says what was run). The entries the scan found on a protein and its line
  lacks count as carried by that line, so a protein is a candidate by them too, and its row's `how`
  says so in words ("which only the entries the species' own scan added to its line carry", with the
  databases). Two rules then stand side by side:

  | | The number rule | The database rule |
  | --- | --- | --- |
  | Reads | the table's own column alone: `scans_newest`, the highest entry each group of lines carries | the scan's record: each database's proteins run on, and the Family entries it has a signature in (the tool's own entry list) |
  | `not in the table` where | no line carries the family, and it is numbered at or below what every group carries | no line carries it (own column or added entry), the number rule cannot place it, a database the scan ran has a signature in it, and that database's pass ran on every protein of the table |
  | Otherwise | up the tree: `broader` or `cannot tell` | the same |

  The scan's entries are never folded into `scans_newest`: they would carry it past the families that
  only a database the scan did not run could show, and those would be called `not in the table`
  falsely. The order is: `narrowest`, the number rule, the database rule, the tree; so a family that
  was `broader` and that the scan shows absent on every protein becomes `not in the table`, and its
  broader family's candidates are no longer taken for that part. `looked_for.scan` gives the scan's
  part: `rests_on_it` (each family whose level rests on the scan, with its level and the databases),
  `family_rows_changed` and `changed` (each row whose level differs from the table's own column's),
  `candidates_only_by_it`, `no_longer_candidates` and `candidates_lost_by_part`, and
  `on_every_protein` (the databases the database rule may use). Each database a value of the machine
  rests on is a source (`scan_<key>`, with the scan record's terms and class, and `scan_interpro`),
  named in `named.sources`. The family rows keep their five columns. A species with no scan named is
  written as before, byte for byte. The species' own entries are found by a search of the Protein
  Data Bank by its taxon; one is the machine's structure where it holds candidates for at least half
  of the parts that have candidates, and for at least two parts where the reference's machine has
  two or more (its parts grouped and framed as the reference groups them, such as a ribosome's two
  subunits).
  Otherwise `structure` is null, `no_structure` begins "None in hand", and `structure_elsewhere`
  names the reference's entry with its organism, and the entries the reference compares. Where the species' own data marks a machine's
  proteins (Syn3A's `complex`), `own_mark` sets the two sets side by side.
- **Sources** carry `licence` and `class` as `tests/licence_classes.test.mjs` defines them; whatever
  a value rests on is permissive, except a source of a species' own scan that the scan's record
  carries with the same terms and that the licence test's register `DECIDED` names (CDD for the
  planarian, by the decision of 18 November 2026; `tests/machine_gather.test.mjs` defers to the
  record). The file holds no clock time and no path of this machine.

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
4. **Its size** stays the measure's (the overlay's `measures`): the dossier gives only the call. For a species by family, a
   size is its own entry's where `structure` names one, and otherwise the reference's machine, said
   as of that organism (`structure_elsewhere`).
5. **The atlas** reads `by_protein` to say on a protein: "part of <machine>".
