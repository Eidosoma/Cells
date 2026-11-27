# Haloferax volcanii

The **Archaea** menu entry introduces the planned Haloferax model with an illustrated rod, plate and envelope cutaway. The picture uses schematic dimensions. Raised six-lobed motifs follow the S-layer around the cell. The oblique cut exposes the membrane and a cytoplasmic section with selectable paired ribosomal subunits. The packing, layer gaps, particle sizes and particle positions are illustrative.

The **Proteins** tab includes the 3,922 entries of UniProtKB DS2 reference proteome `UP000008243` in release `2026_04`. Of these, 204 are manually reviewed and 3,718 are automatically annotated. Each entry carries its curation status. The catalogue generator takes a UniProtKB TSV export with accession, review status, protein and gene names, ordered locus, length and subcellular location.

```bash
python3 tools/build_haloferax_shelves.py DS2.tsv --release 2026_04 --date 2026-11-27 --out data/proteins/haloferax/shelves.json
```

The **Machines** tab links the 32 distinct PDB deposits returned on 27 November 2026 by the experimental polymer-entity search for NCBI taxon 2246 and descendants. The [search record](../data/catalogue/structures/haloferax.json) groups them around 18 representative biological assemblies. The S-layer, pilus and 70S ribosome come from Haloferax. The mixed 30S experiment uses a Haloferax tRNA fragment bound to a *Sulfolobus acidocaldarius* subunit. Chain labels preserve the recorded sources.

The **Cell structures shelf** in Machines includes the cell–cell bridge, S-layer and membrane section, extracellular vesicle, archaellum and a possible storage granule. The bridge, envelope spacing and vesicle use measurements from *H. volcanii*. The bridge illustrates the midpoints of separately reported width and length ranges. The granule retains the tentative identification from the original tomogram. [Cell bridge cryotomography](https://doi.org/10.3389/fmicb.2020.612239) · [Extracellular vesicles](https://doi.org/10.1073/pnas.2311321121)

- [NCBI taxonomy, strain DS2](https://www.ncbi.nlm.nih.gov/taxonomy/309800)
- [UniProtKB reference proteome](https://www.uniprot.org/proteomes/UP000008243)
- [Cell shape study](https://doi.org/10.1038/s41467-024-45196-0)
- [S-layer primary study](https://pubmed.ncbi.nlm.nih.gov/34818541/)
- [PDB 8FJ5, type IV pilus](https://www.rcsb.org/structure/8FJ5)
- [PDB 12DM, 70S ribosome](https://www.rcsb.org/structure/12DM)
