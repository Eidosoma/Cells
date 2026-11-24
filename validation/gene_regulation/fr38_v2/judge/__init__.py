"""The judge of FR-38's second registered comparison, built from the spec folder alone.

The spec is `validation/gene_regulation/fr38_v2/spec/` at tag `fr38-v2-amendment-3-2026-11-24`
(README, SPEC, LAWS, READOUTS, CRITERIA and amendments 1 to 3), with the shared pair rule
`validation/assembly_lineages_v2/agreement.py`. The references are read only as CRITERIA's C0
directs: `reference_invented.json` first, then each reference file.

- `spec.py`: the judge's transcription of SPEC.md's inputs, runs, classes, orders and plants.
- `mapping.json`: READOUTS.md's published names, engine series against reference series.
- `records.py`: the reader (C0) of the reference files and of the engine's export folder; the
  engine export's layout is stated in its docstring.
- `rules.py`: the scales (READOUTS.md §3), C1 to C4, and route 2's host forms (LAWS.md §6).
- `judge.py`: the verdicts per run, family, arm and comparison, the retry and the plants.
- `__main__.py`: the CLI.

Nothing here imports, runs or reads the engine.
"""
