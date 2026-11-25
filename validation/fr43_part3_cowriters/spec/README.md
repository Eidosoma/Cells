# FR-43 part 3, the co-writers: the references' spec folder

This folder is for the code-blind references agent of FR-43 part 3's co-writer registration (the user's decision of
25 November 2026, question 2). That agent writes the references from this folder alone, with the law-sheet sections
that `LAWS.md` names. The registration itself is `docs/FR43_PART3_COWRITERS_PROTOCOL.md`, which the references agent
does not read.

## Rules for the references agent

**Code-blind.**
- Do not read `src/`, `tests/`, any engine module, or any Python file under `validation/` outside your own folder.
- Do not read FR-43 part 3's first references, its registration or records, the design notes, or any decision text
  beyond what this folder quotes. Do not read any engine output, log or table.
- Read only this folder and the sheet sections `LAWS.md` §3 names (`docs/TEMPLATED_POLYMERISATION_LAWS.md`).

**Value-silent.** This folder states every input and no result. Compute every result yourself.

**Never:** run the engine; fit anything to a result; round a reported value; report a value this folder does not ask
for; change an input (a question that would goes to the lead and becomes a dated amendment, never a silent change).

**Deterministic regeneration.** Your files are bitwise the same under at least two `PYTHONHASHSEED` values besides
your own, with every BLAS pinned to one thread, on one machine. Show it before you report a head, and record the
seeds, the platform and each file's sha256 in your report. Run times go in a sidecar, never in the files.

**Invented inputs first.** Your writer's own test writes the invented pair (SPEC.md §8) before the registered files.
The comparison's judge reads it, its first read.

**Questions.** Ask the lead in writing. An answer that changes an input or a definition becomes a dated amendment to
this folder. It governs where it differs.

## Files

| File | What it holds |
| --- | --- |
| `SPEC.md` | The worlds, the runs, what to compute, the accuracy, the sizing, the reference-file layout, the invented pair, the checks |
| `LAWS.md` | The laws in closed form, the draws' rule, the sizing model, the rounding counts, the planted changes |
| `READOUTS.md` | Every published and judged quantity: its name, unit, definition, scale and class |
| `CRITERIA.md` | The criteria, classes, tolerances, the fault table, the plants, the retry and the verdicts |
| `TABLE.md` | The engine table's contract, between the builder and the judge |
| `inputs.json` | Every input, machine-readable: worlds, families, runs, plants, the judged set, the counts |
| `draws.json`, `make_draws.py` | Every copy's draws (float-hex), and their standalone generator |

A registered run's numbers are `inputs.json`'s. Where the text and `inputs.json` differ, `inputs.json` governs
numbers and the text governs rules. Read in the order SPEC, LAWS, READOUTS, CRITERIA, TABLE.

## Where your work goes

`validation/fr43_part3_cowriters/references/`: your code, a README stating your method, readings and checks, the
self-check and `out/`. Nothing of yours imports, runs or reads the engine.
