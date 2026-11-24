# FR-38's second registered comparison: the references' spec folder

This folder is for the code-blind references agent of FR-38's second registered comparison (D334).
That agent writes the references **afresh**, from this folder and the sheet sections that `LAWS.md`
names. The registration itself is `docs/FR38_SECOND_COMPARISON_PROTOCOL.md`, which the references
agent does not read.

## Rules for the references agent

**Code-blind.**
- Do not read `src/`, `tests/`, any engine module, or any Python file under `validation/` outside
  your own folder.
- Do not read the first comparison's references (`validation/gene_regulation/references/`: code,
  README or interface files), its rule and erratum, its records under `/mnt/workspaces/Cells/`, or
  its diagnosis.
- Do not read the protocol document, the design draft, or any decision text beyond what this folder
  quotes.
- Read only this folder and the sheet sections `LAWS.md` names.

**Value-silent.** This folder states every input and no result. Compute every result yourself.

**Never:**
- run the engine;
- read an engine output;
- fit anything;
- round a reported value;
- report a value this folder does not ask for.

**Deterministic regeneration** (FR-43 part 2's lesson):
- Your writer's files are bitwise the same under at least two `PYTHONHASHSEED` values besides your
  own, with every BLAS pinned to one thread (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`).
- Show this before you report a head, and record the seeds and each file's sha256 in the files'
  provenance and in your report.

**Invented inputs first.**
- Your writer's own test writes a file of the same format for invented inputs: other τ, pools,
  rates, windows and times, none of them this folder's.
- The comparison's judge reads that file, its first read, before any engine run.

**Questions.** Ask the lead in writing, and keep the answers with your references. An answer that
changes an input or a definition becomes a dated amendment to this folder, never a silent change.

## Files

| File | What it holds |
| --- | --- |
| `SPEC.md` | The units of every declared count, every world's inputs, what to compute, the accuracy required, the classes, and the writer's file with a format sample |
| `LAWS.md` | The sheet sections to read, and the laws quoted here: the membership classes, the D152 passive law, water's law, G's definition |
| `READOUTS.md` | Every published quantity: its name, unit and definition, and which arm judges or reports it |
| `CRITERIA.md` | The criteria, bands and plants, fixed before any reference exists. The plants' predicted effects are yours to compute (SPEC.md §6) |
| `AMENDMENT-2026-11-24.md` | Amendment 1: the answers to your four questions and your five readings. It governs where it differs from the files above |
| `AMENDMENT-2-2026-11-24.md` | Amendment 2: the lead's layout rulings on provenance, extra keys and precision. It governs where it differs from the files above |
| `AMENDMENT-3-2026-11-24.md` | Amendment 3: family D's energy identity judged at second order (a disclosed correction), release_check's scope, and four readout controls. It changes nothing the references compute |
| `AMENDMENT-4-2026-11-24.md` | Amendment 4: the judge's questions ruled, and the engine export contract (the table's layout, run names and definition vocabulary) that the builder and the judge both read. It changes no band |

## Where your work goes

- `validation/gene_regulation/fr38_v2/references/`: your code, a README stating your method and
  readings, your self-check, and `out/` with the writer's files.
- Nothing of yours imports, runs or reads the engine.
