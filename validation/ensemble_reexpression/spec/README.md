# The ensemble's re-expression: the spec folder

**Registration:** `docs/ENSEMBLE_REEXPRESSION_PROTOCOL.md`. Protocol name: `ensemble-reexpression-v1`.

**What this folder is.** The registered criteria for one comparison. The calcium ensemble and its neighbours leave legacy
and are written in the engine's canonical forms. Each re-expressed consumer is judged against captures of the legacy
runs, taken on 25 November 2026 from frozen snapshots of the engine. It holds docs and data only: no engine code, no candidate, no judge.

**Two parts, with their own tags.**
- **Part 1:** the four consumers that need no new ionic piece. `SPEC.md`, `READOUTS.md`, `CRITERIA.md`, `TABLE.md`, `PLANTS.md`, `inputs.json`,
  `legacy_part1.json`, `reference_paths.json`, `margins.json`, `plants_manifest.json`.
- **Part 2:** the four calcium clusters and the four assembly-regulated calcium clusters. `PART2.md`, `inputs_part2.json`,
  `legacy_part2.json`, `margins_part2.json`, `plants_manifest_part2.json`. It waits for two design notes, which `PART2.md` §0 names.
- Completing Part 2 changes none of Part 1's files. What Part 2 needs beyond them is in its own files.

## Files

| File | What it holds | Governs |
| --- | --- | --- |
| `inputs.json` | Part 1: every world's content by name and value, the pools, the seeds, the scales, the list of registered runs | Numbers. If a text differs from it, stop and ask |
| `SPEC.md` | What a canonical definition must hold, what the candidate declares, the runs, the steps, the scale rule, the references, the rehearsal set | The worlds and the runs |
| `READOUTS.md` | Every compared quantity: its name, unit, sign, its canonical source, its captured array and index, where it is judged | Names, signs and lumps |
| `CRITERIA.md` | Classes, bands, the order rule, power, faults, plants, the retry, verdicts, what a miss means | The judgement |
| `TABLE.md` | The contract of the engine table, one entry shape for every run | The exporter and the judge's reader |
| `PLANTS.md` | The plants, their homes, and their margins from the legacy side alone | The plants |
| `legacy_part1.json` | The captures' identity and the legacy side's own classes, entry by entry | The reference side |
| `reference_paths.json` | Every committed event of the captured assembly pools | Class E on the event path |
| `plants_manifest.json` | Every planted legacy run of Part 1: command, patch text, output folder, sha256 | The plants' provenance |
| `margins.json` | Part 1: the plants' distances, ratios and margins, the mechanisms and their home entries, from the legacy side alone | Power |
| `PART2.md`, `inputs_part2.json`, `legacy_part2.json`, `margins_part2.json`, `plants_manifest_part2.json` | Part 2, the same files by part | Part 2 |
| `AMENDMENT-<n>-<date>.md` | Dated changes, the latest first. None exists at the criteria tag | Over every file above |

**Files outside this folder that the registration uses,** all in `validation/ensemble_reexpression/`: the lead's
`registered_strings.json` (the strings note, §"No registered ID here"), and the rehearsal's `inputs_rehearsal.json` and
`registered_strings_rehearsal.json`. In `table-retry/`, the judge's `retry_owed.json`. In the judge's record, `power.json`.

## Rules for every reader

- **Who may read what** is the protocol's §3. Two lines matter most here.
  - The builders' exporter is written from `TABLE.md` and `READOUTS.md` alone. The judge's reader is written from this folder alone.
    Neither reads the other's code.
  - The judge reads the captures, the planted legacy arrays and this folder. It reads no engine source and no builder's code.
- **Value-silent about the candidate.** This folder holds legacy numbers (scales from the inputs, the legacy runs' own refinement,
  planted distances). It holds no number from any re-expressed run, and its author had seen none. Others had, and the protocol's §11 says who and what. `CRITERIA.md` §8 reports the two worlds of `base` that a prototype ran apart from the rest.
- **Nothing is fitted.** No band, class, window, count or scale comes from a run of either side. The legacy side's refinement and the
  plants' distances are reported beside the bands. A margin never changes a band.
- **Questions** go to the lead in writing. An answer that changes an input, a class or a definition becomes a dated amendment here,
  with the sentence it replaces, and never a silent change.

## No registered ID here

- **Every model, law, operator, solver and kind is named by a label** (for example `kv15_mh`, `junction_relaxation`). No file of this
  folder holds a registered ID. The ID move comes last on the cleanup branch, and these files are hashed before it.
- **The strings note** maps every label to the exact string that a run declares. The lead writes it after the move, with its own tag
  (`TABLE.md` §5). It is the one file through which a string enters the judgement.
- **This folder is frozen for the ID move,** because it holds nothing for the move to rewrite. A match in it is a fault of the move.

## What this folder does not test

Say these before anyone reads a pass as more than it is. The full list is the protocol's §9.
- Bitwise identity with legacy, anything on a GPU, and legacy's own proofs that a step stays inside its domain.
- The assembly consumers' trajectories. Their captures hold one end state, and a few summaries for the clusters.
- Any form of the assembly coupling but the decided one (`SPEC.md` §3.3).
- How a lumped heat divides among its parts.
- A difference below a band.
