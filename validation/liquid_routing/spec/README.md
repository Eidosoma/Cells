# FR-54 and FR-57, liquid routing: the references' spec folder

**Read the amendments with this folder: they govern over it, the latest first** (below, Files).

This folder is for the code-blind references agent of the registered comparison
`liquid-routing-v1`. That agent writes the references **from this folder alone**. The registration is
`docs/LIQUID_ROUTING_PROTOCOL.md`, which the references agent does not read. The judge, the builder and
the checker read this folder too (the protocol's roles).

**The two requests, as the references need them:**
- **FR-54:** passive neutral diffusion between two finite liquid regions, against the exact two-well
  solution, then a partial exchange of one well's liquid beside it. The heat dissipated is part of the
  comparison.
- **FR-57:** a passive tracer carried by a prescribed liquid flow between finite regions into a growing
  collector, with the flow's mixing heat.

## Rules for the references agent

- **Code-blind.** Do not read engine code, tests, any Python file under `validation/` outside your own
  folder, the protocol, any design note, or any decision text. Read this folder only.
- **Value-silent.** This folder states every input and no result. Compute every result yourself.
- **Never** run the engine, read an engine output, fit anything, or report a value this folder does not
  ask for.
- **Decimal.** Compute in the standard library's `decimal` at 60 digits or more (no other library is
  needed). Publish each value as a decimal string of 40 significant digits.
- **Deterministic regeneration.** Your writer's files are byte-identical under at least two
  `PYTHONHASHSEED` values besides your own. Show this before you report a head. Record the seeds, the
  platform and the library versions in `out/provenance.json`, and each file's sha256 in
  `out/SHA256SUMS`. Run times go in a separate file.
- **Invented inputs first.** Write `reference_invented.json` (SPEC.md §8) in the same layout before the
  real files. The judge reads it first.
- **Questions** go to the lead in writing. An answer that changes an input or a definition becomes a
  dated change to this folder, never a silent one.

## Files

| File | What it holds |
| --- | --- |
| `inputs.json` | Every world's inputs and the list of registered runs, as numbers. It governs. If SPEC.md and it differ, stop and ask |
| `SPEC.md` | The worlds and why each value was chosen, what to compute, the placements from the dt study, the file layout, the invented file, the checks to pass before the tag |
| `LAWS.md` | The closed forms, the published scheme, the rounding counts, the planted series |
| `READOUTS.md` | Every compared series: its name, unit, definition, scale and class |
| `CRITERIA.md` | Bands, classes, tolerances, plants, verdicts, refusals and the retry |
| `TABLE.md` | The engine table's contract, for the builder and the judge |
| `AMENDMENT-1-2026-11-25.md` | The references agent's first six readings, and the layout they settle |
| `AMENDMENT-2-2026-11-25.md` | Two errors of the author's text, the retry's cases in arm 1, the references' readings |
| `AMENDMENT-3-2026-11-25.md` | Which holders have a mixing heat, the exchange's interval, an M1 miss, the invented set's near-tight start |
| `AMENDMENT-4-2026-11-25.md` | Arm 7's runs, retry runs, the restart and no-router runs, the spec auditor |
| `AMENDMENT-5-2026-11-25.md` | The spec audit's findings as ruled, the layouts they give, what the references must do |
| `AMENDMENT-6-2026-11-25.md` | The scale of `B_def`'s accuracy, `J0`'s `n_U_K`, P16's `heat`, which run a plant reads |

**Files outside this folder that the registration uses:** in `validation/liquid_routing/`, `takeover_map.json`,
`takeover_map_rehearsal.json` and `takeover_pairs.json` (the builder's), and `registered_strings.json` with its phase-2 and
rehearsal counterparts (the lead's); in `table-retry/` and `table-arm6-retry/`, `retry_owed.json` (the judge's). Layouts:
amendment 5.

**What this folder does not test.** A bound species at a node that a link touches is not tested here. `F7` has its
sites at a node no link touches, and a builder's own row must test a linked one.

Your work goes in `validation/liquid_routing/references/`: code, a README with your method and readings,
your self-check, and `out/`.
