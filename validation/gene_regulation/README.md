# Gene regulation's option A: the engine's worlds, runs and readouts (FR-25)

These are development tools for templated_polymerisation@1, FR-25's expression unit. The equations
are in `docs/TEMPLATED_POLYMERISATION_LAWS.md`. G2's code-blind references sit in `references/`,
which this folder's tools read as data only.

| Tool | What it does |
| --- | --- |
| `worlds.py` | The sheet's A1 and A1-M's fifteen worlds, at any potential set; FR-38's release worlds R1 (with R1L, its fate rows labelled by FR-42's shares), R2 (with the addendum's development check) and R1S |
| `engine_run.py` | Runs worlds, exporting the sheet's §6 readouts per cell by ID, except each move's ΔG and A1's u(t) (below), with a receipt of the source |
| `compare.py` | An engine run against G2's interface at G2's required times |
| `cohort.py` | Window survivors from the counters: one well-mixed pool, loss independent of age; a fate row's inflow is its release's (FR-38, §9.8's route 2); and the survival readout by both routes. A row its cell exports is refused by `read`; `series` reads the cohort through the export (amendment T, erratum H) |
| `release_check.py` | FR-38's checks of R1, R2 and R1S runs: the requester's limit, the identities, energy, both cohort routes (route 1 on shares) and the survival readout |
| `optin_check.py` | The release opt-in's before/after dump of every registered FR-25 definition, and its D148 verdict |
| `rna_readouts.py` | Per-cell RNA readouts and FR-25's two controls |
| `restart_example.py` | A restart at a rate change |
| `replace_restart.py` | FR-38's step 5: a producer replaced midway through a chase, then a restart |
| `kernel.py` | The operator's own half-steps in NumPy, used by the tests |
| `plants.py` | The sheet's plants |

## What `engine_run.py` exports

At each output, per cell by ID, under G2's interface names:
- **Amounts:** every row the operator lists, `n_<row>` (and `n_X` in A1), and each pool's free
  machines, `F_<pool>`.
- **Chains:** each stage's complexes `C_<chain>_<j>`, their sum `E_<chain>`, the residues in transit
  `W_<chain>`, and the cumulative initiations, stage exits and releases, `int_J_I_<chain>`,
  `int_S_<chain>` and `int_Q_<chain>`.
- **Losses and recharging:** `int_D_<polymer>`, the sum of the polymer's loss routes at the cell (a
  zero series for a product with no loss route there), each route's own `int_D_route_<route>`, and
  `int_J_C` (signed).
- **Energy:**
  - the five heat classes `H_tx`, `H_tl`, `H_deg_R`, `H_deg_P` and `H_rc`;
  - each route's heat `H_route_<route>`, their sum and the booked total;
  - `G_minus_G0`, from the state alone.
- **J_bar_<chain>** in A1-M's worlds, at their full horizon.
- **The release** (FR-38, the sheet's §9), only in a world that declares one, per release and fate
  (`durable`, `short_lived`): the hold `H_<release>` (and `H_<release>_<k>` per class where it has
  several), the releases `int_Q_<release>_<fate>` (`_<k>` per class), each fate's class total
  `n_<release>_<fate>`, and its heat class `H_rel_<release>_<fate>`. `E_<chain>` counts a held hold
  among the engaged machines; a fate row other than its chain's product has its own loss class,
  `H_deg_<row>` (§9.12); and `G_minus_G0` includes the hold's standard term.
- **FR-42's labels** (D289), only in a world that declares `neutral_arrival_labels@1`: each
  labelled row's amount carrying each of its labels, `label_<row>_<label>`, the row times the
  label's share, by the species' and label's IDs. The labels are the owner's derived list, so a
  producer's labels (amendment G, §9.20) are exported with the declared ones. A label changes no
  physical readout.
  - In R1L, `label_R_cohort` and `label_R_s_cohort` are §9.8's route 1 on shares (errata C and
    F): the releases of R1's window still present, with no blank, marked on transcription's own
    label schedule, so a molecule re-synthesised from monomers is not a member.
  - **Limits:** a labelled species carries at most the label owner's MAX_LABELS labels, so
    producer identity crossed with the window labels must fit within it. RNA that leaves its cell
    by the operator's export (amendment T, §9.17) keeps its label at the node: the export reports
    its two one-way parts as transfers carrying their sources' shares (erratum H).
- **The export** (amendment T, §9.17; erratum H, §9.21), only where the exported cell's own exports
  feed nodes, at each such node by its ID:
  - each row the operator writes there (the exported rows, and the outside degradations' polymers
    and monomers), `n_<row>_<node>`, and with FR-42's labels `label_<row>_<label>_<node>`;
  - each export's one-way parts, `int_E_<export>_forward` and `int_E_<export>_backward`;
  - each outside degradation's `int_D_route_<route>`, and their sum per polymer and node,
    `int_D_<polymer>_<node>`;
  - the heat classes `H_exp` (each export's whole heat, booked at its cell) and `H_odeg` (the
    outside degradations', booked at their node), with each route's `H_route_<route>`.

  `G_minus_G0`, `H_total` and the routes' sum then cover the cell and its nodes, the checks name
  the nodes (`exported_nodes`), and an exported row is no lossless product (D265). A node that
  another cell's export also feeds is refused, since G over one cell and the node would not close.
- **Beside a second writer or water** (FR-43 parts 2A and 2B; FR-38's second comparison, families C
  and D):
  - with local_species_reactions@1, its own rows (`n_Mx`) and its heat at the cell, `H_store`;
  - with ideal_osmosis_linear_compliance_water@1, the cell's volume `V`, water's heat `H_water`,
    the bath's water work `W_bath`, and `n_K` and `n_Y`.

  `G_minus_G0` then adds the network's rows, or under water every species row at the current V.
  G's identity becomes G − G(0) + H_total + H_store + H_water − W_bath. Water's bookings are second
  order (FR-43's C2.7), so with water that identity closes at second order, not at rounding.

`release_check.survival`'s agreement of route 2's counts with the net reading applies only where
k_f (ts − t1) max e^(y_f) is within its own allowance (`net_scope`); elsewhere it is reported out
of scope (FR-38's second comparison, whose AN family has e^(y_f) of about 0.13).

**Not exported**, though G2 publishes them:
- each move's ΔG, `dG_tx`, `dG_tl`, `dG_rel_R`, `dG_rel_P`, `dG_deg_R`, `dG_deg_P` and `dG_rc`;
- A1's coupling factor u(t).

`compare.py` declares those two as not exported (`not_exported`) and lists them in each result's
`not_compared`. FR-25's registered acceptance (D278) therefore covers neither.

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

## A producer replaced midway through a chase, then a restart (`replace_restart.py`)

**What it shows** (FR-38's step 5, the requester's acceptance; the sheet's §9.16 and §9.18): the
readout distinguishes the two generations' RNA, and a run restarted after the replacement
reproduces the uninterrupted run's cohort counts. Development, not judged.
- **The world:** R1 at p = 0.75 with A1's transcription. Its fate rows R and R_s are labelled by
  FR-42's shares and both declare transcription as their producer with the window [0, 1,200 s)
  (amendment G, §9.20, option (a)). The label owner derives the labels from replacement@1's
  events, the species' own first, then per generation `cell_0-g<k>-tx` and `cell_0-g<k>-tx-cohort`,
  and transcription's schedule: g0's cohort label for releases in [0, 1,200 s), g0's after it, and
  g1's from the replacement at 3,000 s. No schedule is written by hand. A newcomer from template T,
  the founder's state and values, takes the slot then. The cell exports R into a finite node,
  driven by NTP, where R decays at its outside degradation's rate (amendment T, §9.17). Restarted
  from snapshot files at 3,600 s; ends at 4,800 s.
- **What stays where:** the departing occupant's rows, chains in progress and hold leave with it,
  so g0's RNA in the cell at the replacement is read from the removal record (`label_removed_fmol`
  for its rows, `label_pool_removed_fmol` for its hold, by label). The node is not replaced, so
  **g0's exported RNA stays there with its label** (amendment T's retention). It is read by two
  routes: the node's row times g0's shares, and g0's net exports over its life carried at the
  outside degradation's gross rate k_o (erratum H, §9.21). g1's RNA is read from the rows by share.
- **The checks:**
  - labels change no physics;
  - the resume reproduces every step and readout bit for bit;
  - no g1 share before the event, and no g0 in the cell after it but what the export's
    backward part returns from the node;
  - the removal records equal replacement@1's removed rows and the operator's H_rem;
  - each generation's per-producer identity, its net exports included, holds at rounding;
  - g0's RNA is retained at the node, the node's label amounts sum to its row, and the two routes
    agree;
  - the producer labels are the owner's derivation.

Run: `PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.replace_restart --out
DIR`. It writes `replace_restart.json` with the verdicts and readouts.
