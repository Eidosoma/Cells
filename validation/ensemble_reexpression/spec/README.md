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
`registered_strings.json` (the strings note, §"No registered ID here"), and the rehearsal's files, which `SPEC.md` §8 lists with their makers and readers. In `table-retry/`, the judge's `retry_owed.json`. In the judge's record, `power.json`.

## Rules for every reader

- **Who may read what** is the protocol's §3. Two lines matter most here.
  - **The exporter's builder receives `TABLE.md`, `READOUTS.md`, `SPEC.md` and `inputs.json`.** The judge's reader is written from this folder alone.
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
  folder holds a registered ID.
- **The strings note** maps every label to the exact string that a run declares. The lead writes it after the registration tag, with its own tag
  (`TABLE.md` §5), and it holds **today's IDs**. It is the one file through which a string enters the judgement.
- **The runs are made before the deletion and the ID move** (the protocol's §5). So the registered strings are today's IDs, and after the move one run per consumer on the final head must equal its registered table bit for bit: values by value, the IDs through the move's table. **This folder is frozen for the move,** because it holds nothing for the move to rewrite. A match in it is a fault of the move.

**The order of work** is the protocol's §5. In short: the spec auditor, Part 1's criteria tag, the judge and its plants, the rehearsal, the registration tag, the strings tag, the floor guard with constants on the registered head's frozen snapshot, the campaign, the checker and the record, then what the user sees, then the deletion, the ID move and the full gate. Part 2's tag does not hold Part 1's.

## For the independent auditor: what to look at first

The auditor reads this folder alone, and the captured arrays listed below. It comes before Part 1's criteria tag, and it asks its questions through the lead. It does not read the protocol, the engine or any other code.

1. **`CRITERIA.md` §4.3 (the order table) and §4.5 (power).** Part 2's rule for a home with several plants and its two replaced homes (`PART2.md` §7.1 and §7.4) came after the planted runs had been read. That document says so, and so does the protocol's §11, which is not in this folder and which the auditor does not need.
2. **`SPEC.md` §4 to §6:** the grid rule and its tolerance, the scales and `amount_refs` from the inputs alone, the rounding count 8 ε (S + 1) s, the term e_store that admits a state that stores amounts, and the closure term, which is on the potentials (a floor solver's cap is not small as a current residual) and has its own number for `phi_out`.
3. **`READOUTS.md` §5 and `CRITERIA.md` §4.2 to §4.4:** the judged balances and energy identity of Part 1, restored from an uncommitted draft. Check the signs against the arrays.
4. **`CRITERIA.md` §5 (where a partial run is judged, the copy guard, the owners, the counts), and §8 (the two sets of `base` and their members).**
5. **The signs of `READOUTS.md` §2 and `PART2.md` §6:** the leak's and the channel's flip, `store_voltage` = −V_b, the sorted chemical axis, the lumped heats, the calcium channel's minus.
6. **`TABLE.md` §3 `inputs.assembly`, and what is echo and what is class E** (`SPEC.md` §2.4).
7. **`inputs.json` and the literal blocks (`SPEC.md` §2.5) against the captured definitions:** amounts, charges, volumes, controls, the event path (`reference_paths.json`), the seeds, the defaults.
8. **The plants:** `margins.json` `mechanisms` against `PLANTS.md` §2, the structural plants' named entries, and the retry rule (`CRITERIA.md` §7).

**Try to find:** an entry that an honest run would miss; a pass with nothing judged; a refusal, a stop or a missing run that hides a fail; a support run that owns a failing entry; a literal a rehearsal cannot meet; a number here that differs between two files.

**The captured arrays it may open, as references** (read-only, under `/mnt/workspaces/Cells/legacy-captures-20261125/`; `legacy_part1.json` and `legacy_part2.json` pin the manifests by sha256):

| World | Path, with `{h,h2,h4}` the captured steps | Arrays |
| --- | --- | --- |
| `jupiter` arms | `science-76a498ae/runs/{jupiter_baseline,jupiter_pump_release}-{h,h2,h4}/window-*.npz` | `times`, `history.{amount_increment, extracellular_amount_increment, leak_transferred, channel_transferred, junction_transferred, face_transferred, pump_cycles, gate, junction_gate, dissipated_energy_pJ, junction_dissipated_energy_pJ, face_dissipated_energy_pJ}`, `observations.{times, voltage_V, extracellular_potential_V}` |
| `integrated` | `extra-49529e71/runs/finite_junction_cluster-{h,h2,h4}/window-*.npz` | The same names, without the faces and without `observations.extracellular_potential_V`. Its pump, leak, channel and gate arrays are padding (zero), since the world has none |
| `cell` | `science-76a498ae/runs/cell-{h,h2,h4}-s{0,1,2,3}/` `checkpoint/state.npz`, `result.json` | `pool_{the 19 names of READOUTS §4}`, `ionic_{the names above}`, `segments`, `availability_exposure_s`. `result.json`: `final_voltage_V` |
| `base` | `science-76a498ae/runs/cluster_base-{h,h2,h4}-s{0,1,2,3}/` `checkpoint/state.npz`, `observations/tick-*.json` | As `cell`, and the summaries `final_voltage_V`, `channel_transferred_fmol` |
| Definitions | `origin-76a498ae/science/ionic/<world>/{h,h2,h4}.json`, `origin-76a498ae/science/assembly/{cell,cluster_base}/{h,h2,h4}-s<k>.json`, `origin-extra-49529e71/extra/ionic/` | The captured definitions (a `definition` key where there is one) |
| Part 2 | `science-76a498ae/runs/{spatial,plasma,gated,ip3}_calcium-{h,h2,h4}` and `cluster_{spatial,plasma,gated,ip3}_calcium-{h,h2,h4}-s{0,1,2,3}` | `history.{chemical_amount_increment, reaction_extent, reaction_dissipated_energy_pJ, er_passive_transferred, er_pump_transferred, er_release_transferred, er_transport_dissipated_energy_pJ, plasma_pump_cycles, plasma_exchange_cycles, plasma_dissipated_energy_pJ, calcium_channel_transferred, calcium_channel_dissipated_energy_pJ, calcium_gate, ...}`, `observations.{er_voltage_V, plasma_voltage_V}` |
| The planted runs | `/mnt/workspaces/Cells/ensemble-reexpression-criteria-20261125/plants` (the manifests name each) | As the captures of their world |

## What this folder does not test

Say these before anyone reads a pass as more than it is. The full list is the protocol's §9.
- Bitwise identity with legacy, anything on a GPU, and legacy's own proofs that a step stays inside its domain.
- The assembly consumers' trajectories. Their captures hold one end state, and a few summaries for the clusters.
- Any form of the assembly coupling but the decided one (`SPEC.md` §3.3).
- How a lumped heat divides among its parts.
- A difference below a band.
- **The time order and the step.** Part 1 does not show them: its S and identity entries sit at rounding, so the steps and the solver string are declared, and the order is the engine's own tests' claim (`CRITERIA.md` §1).
- **The floor guard of the field solver.** It is made on the registered head's frozen snapshot before the first registered run, and this folder assumes nothing of its result.
