# The assembly view's run files

The replay files use the contracts in `schema/ASSEMBLY_RUN.md`.

- **`vesicle-<id>.json`** holds one recorded life of a Cells vesicle. The two OL5 development runs show growth with shear division and osmotic swelling with threshold lysis. The adapter preserves seconds, place counts, geometry samples and release causes. Their model entry is `data/models/origin-vesicles.json`.
- **`reference-popc.json`** supplies the 52 heavy atoms and bonds of an ideal POPC conformer for the molecular close-up. The replay carries the run's own membrane species labels independently. [wwPDB Chemical Component Dictionary, LBN](https://www.rcsb.org/ligand/LBN)

- **`gard-pair-consistent-<id>.json` and `gard-single-event-<id>.json`: the engine's own pair of GARD
  runs,** written by `tools/adapt_assembly_run.py` from the engine's final set
  (`/mnt/workspaces/Cells/gard-g1-part2-20261117/probes-c6dd5956/probes/`, its roles `lineage` and
  `lineage_single_event`; final at GARD's merge into main, `1f9863ce`). Development runs of the engine,
  not judged: each file says so and says where that standing is recorded. Do not edit them by hand;
  run the adapter again on a new set. GARD's entry (`data/models/gard.json`) names them, so the page
  plays them.
- **`example-run.json`: the example of invented numbers** (below), which the page played before the
  engine had a run and which the checks still play on scenes of their own.

## The example run

`example-run.json` holds invented numbers in the form of `schema/ASSEMBLY_RUN.md`, so that the
assembly view (heading "Origin of life", a GARD assembly as its first model system) can be built and
shown before Cells' engine has a run of an assembly lineage. **It is not a run of Cells' engine, not
any published study's run, and nothing in it is a finding.**

- Written by `tools/make_assembly_example.mjs`; do not edit by hand. Run twice, the tool writes the
  same bytes, and a test holds this file to it.
- Two lineages of 120 fissions in one environment of 100 molecule types, by the rules the tool's
  opening comment states (the Plastic Heredity preprint, doi:10.5281/zenodo.22143269, Appendix F; the
  open papers in the file's `sources`, each CC BY 4.0).
- Its own analysis (the marks of inheritance at the preprint's strict 0.9) is worked out by the tool,
  as invented as the numbers; it names no composome.
- The file says it is an example (`example.says`), and the view keeps those words on the picture and
  in the legend while it is shown. It names no engine model and no revision.
