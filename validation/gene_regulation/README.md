# Gene regulation's option A: the engine's worlds, runs and readouts (FR-25)

These are development tools for templated_polymerisation@1, FR-25's expression unit. The equations
are in `docs/TEMPLATED_POLYMERISATION_LAWS.md`. G2's code-blind references sit in `references/`,
which this folder's tools read as data only.

| Tool | What it does |
| --- | --- |
| `worlds.py` | The sheet's A1 and A1-M's fifteen worlds, at any potential set |
| `engine_run.py` | Runs worlds, exporting every readout of the sheet's §6 per cell by ID, with a receipt of the source |
| `compare.py` | An engine run against G2's interface at G2's required times |
| `cohort.py` | Window survivors from the counters: one well-mixed pool, loss independent of age |
| `rna_readouts.py` | Per-cell RNA readouts and FR-25's two controls |
| `restart_example.py` | A restart at a rate change |
| `kernel.py` | The operator's own half-steps in NumPy, used by the tests |
| `plants.py` | The sheet's plants |

## Per-cell RNA readouts (`rna_readouts.py`)

**The readout.** For each cell and gene, the cell found by its ID, at each sampling time:
- the total RNA;
- the transcripts started, completed and degraded (int_J_I, int_Q and int_D);
- for a chosen window, the transcripts completed in it that are still present at sampling, as a
  pulse label measures them.

Values are raw, per cell and in copies, so each assay applies its own detection rule. The record
names its revision, units and sampling times.

**The two controls** both hold, and `tests/unit/test_gene_regulation_compare.py` checks them:

| Control | Expected | The engine's readout |
| --- | --- | --- |
| Turnover: 100 copies, a one-hour half-life, production 100 ln 2 per hour, the first hour marked | the total stays at 100; 69.31 marked; 50 at the hour's end; 25 an hour later | 99.99998 to 99.999998; 69.31470; 49.99998; 24.99999 |
| Responding cells: [0, 0, 20, 20] against [10, 10, 10, 10] new copies | means 10 and 10; at one copy, 50% and 100% positive; positive means 20 and 10 | means 9.999995 and 9.999997; 50% and 100%; positive means 19.99999 and 9.999997 |

The residual, about 1e-6 of each value, is the polymerases' depletion: 10^6 per cell, of which
the transcripts in progress hold a few.

**What the calculation assumes.** The window survivors take one well-mixed pool whose loss does not
depend on a molecule's age. Under age- or region-selective loss no field names which molecules were
lost, and the calculation does not apply. That needs labelled cohorts or age classes:
`docs/COHORT_LABELS_DESIGN.md`, and FR-33.

## A restart at a rate change (`restart_example.py`)

**What it shows** (FR-25's follow-up, D251): whether a run stopped at a checkpoint and resumed
reproduces the uninterrupted run, when a scheduled rate changes at the join.
- **The world:** pol T=5, with transcription's initiation rate halved at 1,800 s.
- **The join:** the run stops there, its checkpoint is saved, and it resumes two ways: in process,
  and from the snapshot files (`records/io.py`).

**Which interval owns the event.** The interval that starts at the join.
- A route's rate is piecewise constant from each change's time, so the change's time is the first
  step of the resumed run.
- The run to the join ends with a step at the old rate. In the recorded run, the step ending at
  1,800 s initiated 1.149e-9 fmol, and the step starting there 5.759e-10 fmol, half as much.

**Whether the joined counters reproduce the uninterrupted run.** They do, bit for bit, both ways:
- every one of 7,201 recorded steps;
- the row at the join;
- the final state, including the operator's cumulative counters: initiations, stage exits,
  releases, degradations, transfers and heat.

The checkpoint is the composite's whole state, so it carries the operator's own fields (free
machines, complexes per stage, and every counter).

**The evidence.**
- **The original run** (20 November 2026) is in
  `/mnt/workspaces/Cells/gene-regulation-20261120/dev/restart-215348/`. Its receipt did not record
  the script, which was untracked then. An addendum beside it says so.
- **An independent replay** from a frozen snapshot of 9ad7123c matched every row, the join and the
  final state bit for bit. Its six final counter arrays matched the original receipt.
- **Receipts now record** every executed source that Git does not track
  (`engine_run.provenance`).

Run: `PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.restart_example --out
DIR`, with `--world`, `--route`, `--join`, `--factor` and `--window-steps` to vary it. The join
must fall on a window's end.
