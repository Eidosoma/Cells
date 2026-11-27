# FR-45's addenda (TABLE.md §14.1), drafted 27 November 2026

The builder drafted each file. A reviewer who is not the builder confirmed them against `src/` on 27 November 2026:
the patches (N1); the checks, floors, multipliers, execution record and host values (N2), with no bound depending
on W1eq's start; and the mapping (B4). The review's corrections are made in these files and in the driver:
- a failure is named by the engine's exact message;
- the checks list is the engine's own, from the passes;
- the ions' reason in the floor addendum is corrected.

The lead then hashes them, before any registered run.

| File | Addendum | The judge reads it as |
| --- | --- | --- |
| `refusal-mapping-2026-11-27.md` | 1. The refusal mapping, from the engine's exceptions and check names to `kind` and `book`, with the stage identification [B4] | its own `mapped` (a literal, which must match) |
| `checks-list-2026-11-27.json`, `checks-list-2026-11-27.md` | 2. The ledgers and host checks by world, each one's cadence and where `definition` records it [B3, S-b] | `--checks-list` |
| `execution-record-2026-11-27.json` | 3. The execution record: each honest run's execution block from its parse-only pass; W1eq takes W1's, a plant run its honest run's; the excluded paths (R5-4: none) [N3, N4] | `--execution-record` |
| `plants-2026-11-27.md` | 4. The plants' changed inputs (P2's two `k_off`, and where they sit in `definition`), and the patch files for the hashes [B6, N1] | its `B6_DEFINITION` (a literal, which must match) |
| `host-entities-2026-11-27.json` | 5. The host-entity values: each honest run's host volumes and `host_values`, from its parse-only pass; W1eq takes W1's [§9.6] | `--addendum` |
| `species-floor-2026-11-27.md` | 6. The one floor the driver passes to the species helper for every ligand (1e-20 fmol), and the ions' (1e-10 fmol) [W6-1] | the execution record's `material_balance_atol_fmol` |

## The parse-only passes

- **What was run:** `python -B -m validation.fr45.registered passes` at bc201ec8, from a clean frozen snapshot of
  `src/cells`, `validation/fr45` (the references' folder left out), `validation/tissue` and `agreement.py`. It ran
  twelve passes on CPUs 6 and 7, each in its own process (`driver.py parse`): every registered honest run but
  W1eq.
- **What a pass does:** parse, the model's initial values with their binding checks, and `runner.timeline`'s grid,
  with no step.
- **Result:**
  - every pass parsed, with none refused;
  - each grid ran from 0 to its horizon in exactly its registered steps;
  - every run's echo equals its expected-inputs entry under the judge's own comparison, with these host values,
    with no departure;
  - the execution blocks hold the literal fields, and no `energy_check`;
  - no field of any definition names a run, a world or a record.
- **The host values** are the bath form's own:
  - each held bath and host cell is 1.0 pL;
  - a wall on the bath is 1e-10 m2 and 1e-12 F;
  - every other patch (the contacts, and `specimen_face` in W3, W3p and W6) is 1e-11 m2 and 1e-13 F;
  - every compartment holds the bath's ions: Na 145, K 5 and Cl 150 mM, times its volume.

  They change no registered quantity: no ligand or ion crosses a host patch. The host compartments' ligand
  traces are 1e-12 times these volumes.
