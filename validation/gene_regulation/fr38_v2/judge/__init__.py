"""The judge of FR-38's second registered comparison, built from the spec folder alone.

The spec is `validation/gene_regulation/fr38_v2/spec/` at tag `fr38-v2-amendment-6-2026-11-25`
(README, SPEC, LAWS, READOUTS, CRITERIA and amendments 1 to 6), with the shared pair rule
`validation/assembly_lineages_v2/agreement.py`. The references are read only as CRITERIA's C0
directs: `reference_invented.json` first, then each reference file.

- `spec.py`: the judge's transcription of SPEC.md's inputs, runs, classes, orders and plants.
- `mapping.json`: READOUTS.md's published names, engine series against reference series.
- `records.py`: the reader (C0) of the reference files and of the engine's tables, its value pass.
- `shapes.py` and `table_shapes.json`: the tables' registered shapes (amendment 5) and the structure
  pass, which the judgement and the sample check both run.
- `definitions.py`: C0's echo of SPEC.md's inputs in the engine's declaration, and the plants'
  registered declaration changes.
- `sample.py`: the reader's check on the registered format sample (amendment 5, §5).
- `rules.py`: the scales (READOUTS.md §3), C1 to C4, and route 2's host forms (LAWS.md §6).
- `judge.py`: the verdicts per run, family, arm and comparison, the retry and the plants.
- `__main__.py`: the CLI.

Nothing here imports, runs or reads the engine.
"""
