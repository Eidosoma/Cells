# The legacy cleanup: what goes, what you approved, and one question

25 November 2026. Twelve minutes to read, and three for section 7, the question. Basis of each number: **(m)** measured, **(r)** read in the code, **(e)** estimated.
The list behind this page is `validation/legacy_port/removal_list.tsv` on branch `legacy-removal-list`: one row per file, with its
owner, reason, basis and state.

**In one sentence.** All of `src/cells/legacy` goes in one deletion, with everything that only served it. What you use comes back in
the engine's own forms. The old code, its runs and its captures stay at the tag `pre-cleanup-2026-11-25` and in
`/mnt/workspaces/Cells/legacy-captures-20261125`.

**Status.** You approved the losses on 25 November (D386): yes to the table in section 3, the cell-zone transporter left at the tag,
NKCC and the generic symport ported in the cleanup, and D211's other ports as the next step after it. The same day you agreed that two things which your earlier
decisions held go too, kept at the tag (the network laws and the EMT-miRNA two-cell model, section 3), and that the optional batch goes. **The counts below are with
the batch, at a6432f98, but for what the builders still add. One question is left for you: the rows in section 7. The deletion (branch
`legacy-deletion`, in place of 9b0debe6) is made and merged only after you have seen them, and after the campaign's verdicts.**

## 1. Counts, by area

| Area | Goes | Lines | Basis |
|---|---|---|---|
| `src/cells/legacy`, and its entry | 322 files | 75,581 | (m) |
| Four law tables in `laws/channels` (of the tissues `@9` to `@12`) | 4 files | 286 | (m); they hold no law, only which code is which (r) |
| Tests | 302 of 894 files | 101,495 | (m); which ones, by the dry run and by reading |
| Test helpers | 77 files | 18,717 | (m), import graph |
| Validation drivers and references | 758 of 1,720 files | 212,182 | (m); 433 of them read one by one, the rest by import graph and names |
| Scripts | 98 of 123, two of them already deleted | 31,350 | (m) |
| Configurations | 116 of 157 | JSON | (m) |
| Examples | all 15 (ten inputs, five guides) | JSON | (m) |
| Test data | 7 files | 1,200 | (m) |
| Test IDs | **11,217 of 21,927**: 10,956 in files that go, 261 rows in files that stay | | (m), collection of the staged deletion; 612 are new |
| Test IDs of the 17 files that used what goes | 372: 77 rewritten (done), 28 that use nothing that goes, 70 that left with the pump and symports work, **197 that would retire (section 7)** | | (m, r), one line per test function in `open_rows.tsv` |
| Written or rewritten by an owner | 246 files edited (112 of them documents), 17 tests retargeted or proposed to retire | | (r); 201 of the edits are done |

The optional batch is in these counts: 165 files and 49,055 lines (50 files of E02-SW1's graph study, a frozen protocol that never ran; 94 of the oldest families'
own references, trajectories, audits and tests; 20 of the last REF-era contacts; one old test context), 1,933 test IDs, and 192 test-seconds in tiers 1 and 2 (about
36 s of wall per full gate, e). Nothing that stays uses it (m, import graph; the second reader agrees). 27 documents name files of it: 21 get a note in the deletion's
commit, and six are records. Its frozen panels stay as records.

On the tree without all of this, **11,008 tests collect, and only 8 files fail to** (m): they are among those of section 7. With section 7's rows gone as well,
**10,995 tests collect with no error, and no file imports or loads anything that goes**, `lean/` and `visualizer/` included, by any way of importing (m), but for
one script of the re-expression's rehearsal, which runs the frozen legacy snapshot. The nightly's record of the files that tests open (main, tiers 1 and 2) showed one
test more, which is now on the list (m, r); tier 3 is known by its imports only. The rename's tool, one guard, the words of three parity files and six of the viewer's
files still name some of it (m), and so do records (155 reports, 56 validation protocols and source maps) and documents. The deletion saves 2,766 of 13,784 test-seconds in
tiers 1 and 2 (m), about 8.6 minutes of wall per full gate (e: 0.186 s of wall per test-second, measured 24 November). 142 of 222 tier-3 files go (m); 148 with
section 7's. The gate's fingerprints lose 129 definitions in 125 files, of the 194 in the three folders (m, the tool's own enumeration); the batch holds none of them. The tag has
173: the live engine's two batch configurations brought four, and the re-expression's format sample 17, which are placeholders that no parser accepts. G1's 113 worlds are unaffected (r).
The fingerprint tool's comparison takes both lists now: `removed_definitions.txt` (129), and the additions, which the lead makes again for the final head. The tier
record loses 302 rows in the deletion's own commit, since the gate refuses a row without a file.
**Measured where:** files and lines at 49529e71, the tag's commit; seconds in the tier record; the parity runs at 63c181fc, on a tree without 1,472 of the files; everything else at a6432f98, a merge for the measurement, not pushed: `legacy-cleanup` 94805c08 with `legacy-cleanup-docs` ebf1bba1 and `legacy-open-rows` eff7d103 (that branch's later commits change no test ID). Section 7's numbers are at 407bc106, the same with `legacy-open-retirements` b0e568d9.

## 2. What comes back

| You use | It becomes | Needs |
|---|---|---|
| The JUPITER world, the cluster base, the assembly cell, the integrated ensemble's world | closed `resolved_pump_tissue@3` worlds, same equations | their registered runs and the judge; the definitions (Part 1), the run driver and the assembly coupling are in |
| The four calcium clusters | a composite over @3, one store per cell | their definitions and criteria (Part 2); the calcium work is in |
| The assembly command lines and ensemble kinds | **CPU runs, one process per world** (`cells assembly-pool resolve`, then `cells run`; the campaign runs them so). A file of several worlds also resolves to a batch that the planner admits, and no row or registered run executes a batch of driven worlds, or of store worlds. The GPU path is **parked** | the same as their worlds |
| The JUPITER platform check (`validation/ensemble/jupiter_check.py`) | its device part (inventory, affinity, float64, benchmark) as it is; **its model part rebuilt** on the re-expressed JUPITER world | after the registration tag; about half a day (e), host parse only until someone runs it on a GPU |
| NKCC and the generic symport | `na_k_2anion_symport_reversible_tanh@1` and `electroneutral_symport_reversible_tanh@1`, on the transporter kind | nothing: in |

**In the engine now (r):** the Na/Ca exchanger; one pump law for an ion of any valence, `atp_driven_transporter_mass_action_positive@2`, for
the plasma's calcium pump and the store's, with the step terms that a store's node needs; the two symports; the release's factor and its source; the assembly
coupling; calcium through a channel, with its step bound, and the CaV1.2 law; and the loop's bound. **Not yet:** a registered run of any of them. Part 1's 214 definitions
parse, and none has been run; Part 2's criteria are being completed (D387).

## 3. What is lost, what stays, and what waits

**The laws stay (D211)** in live `laws/`, with their references and a test of each kernel. Only the old tissue that hosted them goes.

| Group | Laws | Waits for |
|---|---|---|
| Kv1.1 to Kv1.4, Kv1.6 | 5 | nothing: registered on @3 |
| Voltage-only Na and K: Kv2, Kv3, K_fast, Nav1.3, the rat Navs, Nav1.6, three dynamic Morris-Lecar | 15 | one module each on @3; no engine feature |
| CaV1.2 | 1 | nothing: registered on @3, with its step bound |
| Calcium and HCN: nine more CaV laws, six HCN laws | 15 | one module each |
| Instantaneous Morris-Lecar | 7 | G-2, a law without a gate |
| Calcium-activated K | 1 | G-3, which the cardiac plan's H1 already holds |

D211's programme is recorded as open, after the cleanup, in `docs/CORE_LAWS_ROADMAP.md`. `test_channel_law_kernels.py` tests three HCN laws that would have
had no test, and keeps the kernel rows of three tissue tests that go.

**D196's condition:** before a batch drops a test that is a live law's only reference check, the check moves beside the law. `law_reference_checks.tsv` holds one
row for each of 134 laws and kernels: the 71 registered laws, the catalogues' 44 and 19 kernels that live models import. 44 of the 71 registered laws declare a test,
and all 44 are collected after the deletion (m). Four had lost their only direct check: Kv1.5 (the 19 cases that D196 names), the one-gate junction law, the
passive reaction kernel and `edge_flux`, the junction flux of `reaction_transport@1`. Each has a row beside it now, with planted errors that fail it, and the first two are the laws'
declared tests. The helper `bernoulli` loses its one row of hand values; a decimal row of the sodium laws that stays evaluates it at and near zero (m: 16 arguments at zero, 64 below 1e-4, and two
planted errors fail it). With the optional batch gone as well, no row of the table changes (m); which rows check a kernel was read (r). The table was read again for every file of section 7: two of their
kernels are live (the pump rates and the drive of `er_calcium.py`), and both are held elsewhere (r).

| Lost, or not carried over | In one sentence |
|---|---|
| Cell-zone transporter (I10) | Left at the tag, as you decided; it is BETSE's network. |
| Finite ATP, ADP and phosphate pools, and the finite-fuel pumps (C2, C3, I4, I5) | Not in the engine after the cleanup, not lost for good; row fuel for the Na/K pump is a candidate request you may make, and none is made yet. |
| Ceilings on an ion's total (D2) | Lost; a check on the @3 line can be asked for. |
| Lateral redistribution and mobile proteins (D5) | Lost; the nearest pieces are `membrane_entity_state@1` and trafficking. |
| Cutting cells out (D9) | Lost until you ask for an operator. |
| BETSE-facing preparation (P1), and its four commands | Gone; it may not live in the engine anyway. |
| The refinement clock | Gone with its two tests; no remaining model uses it. |
| GPU ensembles of assembly clusters | Parked. |
| **The ionic ensemble on a GPU queue** | Its rows (`test_integrated_ensemble_gpu.py`) run on GPUs only, and no gate runs a GPU (r). They go with section 7, and **the ionic GPU queue has no row after that**. The GPU queue's rows on the two other families stay, and are run by hand only. |
| Physiology stack and REF-era BETSE drivers (D374) | You retired them: 559 files; their protocols and reports stay. |
| **Live BETSE runs in four parity files** | Three files lose an optional live run that has not started since 11 October 2026 (the source it is bound to changed), and one that is skipped loses its call. Their closed-form rows stay: 55 pass, 70 that could only error leave. The tag keeps the driver; it does not run it either. |
| **`network_reactions@1` and `network_control_factors@1` (C3)** | Gone, as you agreed on 25 November; kept at the tag. They were an enzyme-network law library that no model integrated, and the factors by which it regulated the calcium-energy family's pumps, channels and junctions. What does this work on the live engine: `local_species_reactions@1` (qualified with MG0c), `species_regulated_availability@1` and `@2`, and, not judged yet, the new pump, the symports and the species condition. The finite-fuel forms and their regulated kinetics have no live replacement. |
| **The EMT-miRNA two-cell model, `emt_mirna_pair@1` (D149)** | Gone, as you agreed on 25 November, which ends D149's exception; kept at the tag, with its guard `test_source_profile_boundary.py` and its configurations (`source_pair_baseline.json` among them). The EMT switch itself runs on the live engine, in the gap-junction replication (`local_species_reactions@1`). What is not live is the pair written the source's way, and the full lineage replication. The pair is captured (`/mnt/workspaces/Cells/legacy-captures-20261125/extra-pair-49529e71`: the baseline twice and the controls; the repeats are bit for bit). There is nothing to compare it with: the earlier recorded runs were not found. |
| `source_decay@1`, `emt_mirna@1`, `passive_pair@1` (G1, G2), neutral mobile leak, mitochondrial passive (I1, I11) | Gone; the tests that used them run live worlds. |
| `scripts/verify_batch_windows_build.py` | Gone: it accepted a live feature, windowed batches, against an archived release. `test_batch_windows.py` covers the feature. |
| Law records in the viewer's inventory | 13 units lose one or two: U34, and U36 to U47. U34, U36 and U39 keep others; for U40 to U46 a live law holds the physics; U37, U38 and U47 have none left. The viewer's agent updates its files. |

**Nothing in use is lost** in the oldest families (A11, but for the pair), the baths and clusters (A10), mitochondria (C4), water, injury, bath schedules, barriers and
membrane profiles (D3, D4, D6 to D8): @3's line does the same physics. The ensemble rebuilds the parts of the owned-calcium tissues (B6, B7). **The three
parity files whose live BETSE run works keep it:** 16, 38 and 25 rows pass without what goes, and the 64 native captures equal the saved ones bit for
bit (m).

## 4. Commands, examples, scripts, the GPU

| What | In one sentence |
|---|---|
| `tissue-phase`, `tissue-geometry`, `tissue-profiles`, `excise` | Removed. |
| `assembly-cell`, `assembly-cluster`, and their two ensemble kinds | Refused by name, saying they are parked and where they are re-expressed (both have a row). |
| Ten example inputs and five guides | Removed; they serve those commands. |
| 96 build, audit and reference scripts, and two records of old moves | Removed with the builds and the references they checked. |
| GPU coverage | `test_batch_identity.py` keeps its GPU option and `test_gpu_execution.py` its definition rows, on the live pump tissue (done). The GPU-only rows of `test_gpu_execution.py` (2), `test_integrated_ensemble_gpu.py` (4) and `test_assembly_cluster_gpu.py` (1) are in section 7. |

## 5. Tests

302 files with 10,956 IDs test families that are canonical elsewhere, dropped or retired. Of the 261 IDs that leave files that stay, 187 were rows on worlds that went
(107 replace them), 70 are the parity rows, 3 followed the old registry, and one is a refusal that the calcium work replaced; `removed_rows.tsv` names each. The 17 files that tested used capabilities on worlds that go
were listed as "rewritten, not deleted". What came of them, by test ID, is the table's last line but one: **77 of 372 are rewritten and run** (60 on the new laws; 17 planning, batch
and GPU-definition rows on the live pump tissue), and section 7 says why most of the others would retire.

**New rows, since rows that retire held claims that no other row did** (branch `legacy-open-rows`): a neighbour's answer through a junction; a store world at equilibrium; thirteen refusals of @3's parser;
the device kind of a saved ionic ensemble; and the two parked commands. Two rows of the pool let a planted error pass and are strengthened: its exposure left out the last interval unseen, and its rechunked run was one chunk.

## 6. Records, and what is open

- **Records stay:** 59 protocol, data and record files, the other results, the design notes and the decisions.
- **Open:** your word on section 7; the campaign and its verdicts; the JUPITER check's model part; the rename's tool, table and note (four pins and four reviewed lines of its choices name files of the batch, m); the list of added definitions, made again for the final head; tier 3's record.
- **The deletion is one commit,** made from the list by a script (both in `validation/legacy_port/`, branch `legacy-removal-list`), in place of 9b0debe6; its message names the head and the list's revision. The script takes the batch by default, and
  makes no branch while a row waits for you. Its last dry run (a6432f98) found every path, removed 1,693 files (six are gone already), and broke no import but those of 8 files of section 7, and of the rehearsal's driver, which runs the frozen snapshot (m).
  The same commit takes one guard's list, the tier record's rows, the old exchanger's kernel and the names that only legacy uses (`plasma_calcium.py`,
  `er_calcium.py`, `calcium_gates.py`; `release_open` among them), and the words of three library pages. On that tree the 15 library pages pass their check (m), and the guard whose list the script edits passes all 17 of its rows (m).
- **Documents:** 57 say what left, with seven folders of old drivers, and the run guides name live worlds; 31 more get their note in the deletion's commit. Pages that old reports pin by hash say that the pinned bytes are the tag's. 420 relative links into removed
  files break without the batch and 43 more with it, most of them under such a note (m, at 5429a49b).
- **14 reference files stay** whose last test goes: old native probes and references that stay import them, or they are BETSE-side references of kinetics with no live version (the four of the network among them).
- **On commit 63c181fc:** its message's numbers are wrong. Measured: the drivers load six Python files (and two JSON protocols) where they loaded 24.
- **Five names** in live laws and numerics that nothing calls any more are listed for their files' owners, after the core edits.
- **Not run:** no gate and no suite. The full test of the cleanup branch is the test of it.

## 7. For your word: the rows that would retire instead of being rewritten

You decided that everything actually used leaves legacy in canonical forms, and that holds: the worlds are rebuilt and judged by the registered campaign. What is below is about the **test rows** on the old forms of those
worlds. The list said "rewritten" for 17 test files. Each of their test functions was then read (`open_rows.tsv`: its claim, what carries it, the plant that shows it, what is not carried). 197 of their 372 IDs would retire:

| Class | IDs | What it is, and the condition |
|---|---|---|
| The older definitions' own refusals | 68 | Each refuses a field or a rule of a form that goes. The new forms' counterparts are refused by rows that stay; thirteen were missing and are written |
| General rows | 38 | Saving, loading, the command line, schedules, changed files: held for every model by rows that belong to no family |
| Carried | 40 | A row that stays holds the same claim, **and a planted fault of that claim makes that row fail** (recorded by its builder, or made for this in a scratch copy: `carrier_plants.tsv`). What is not carried is named below |
| The campaign's own worlds | 13 | Conditional. They retire with the deletion and only after the verdicts. If their consumer fails or stays inconclusive, they come to you with it |
| Parked with the assembly ensembles | 27 | Commands, planning of a parked kind, sums over an ensemble, GPU agreement: parked by your earlier decision. Ten of these hold planning that other rows carry, or sums that nothing replaces |
| GPU only | 4 | No gate runs a GPU, and their tolerances are the older model's. The ionic GPU queue has no row after this |
| Others | 7 | A tool's own row (the tool goes), one on the older kernel's two code paths, a reduction between two families that both go, three cubic proofs of the older observers, a reference's own sampling |

With them go 13 files: `test_assembly_cell.py`, `test_assembly_cluster.py`, `test_assembly_controls.py`, the four calcium tests (`er`, `gated`, `ip3`, `spatial`), `test_surface_catalog_planning.py`, two GPU test files, and
three drivers (`integrated_matrix.py`, `spatial_matrix.py`, `cluster_reference.py`). No module of `src/cells` is reached by the retiring tests alone (m, import graph), and no data file loses its last reader (m). Two of the five calcium references lose their last reader and
stay for the campaign (`reference_gated_calcium.py`, `reference_ip3_calcium.py`).

**Three claims that nothing carried, and what holds them now:**

1. **What one cell's assembly does reaches its neighbour through the junction, and only so.** Now in the compiled row of the composed world: the neighbour's voltage moves by the junction's charge (0.98 of it, m; between 0.10 and 1 by the world's own conductance), and with the junction closed by its control it carries exactly nothing and the neighbour answers by 4e-8 of that (m).
2. **A store world at equilibrium does not move at all.** Now a host row: with every mover on and the pumps at their stall, two steps leave every field but the channel's gates as it was; 1e-15 V, one rounding of the store's calcium or 1e-15 of the fuel's drive each moves it.
3. **A batch of store worlds.** Still no row, and section 2 says so. Measured once in a probe: two store worlds in one batch are bit for bit their own windows, and the batch's restart repeats (m). A row would compile a second program (about 50 s of CPU under load, m).

**Not carried, by name** (no live row holds them): the pinned store pump's and the pinned release gate's own functions, and that gate's six network branches, run out of process (the pinned plasma pump's still is); the slope of CaV1.2's kinetics by automatic differentiation; IP3's binding in the cytosol, as a
reaction of the store world (calcium's is there); the older kernel's count of its own pieces; a stop asked for off the grid; a composed file whose order of pools does not matter; two driven worlds with different schedules in one batch; the sums over an assembly
ensemble's worlds (the parked kind's); CPU and GPU agreement of assembly-driven and store worlds; the older observers' cubic proofs.

**If you say yes,** the 13 files go by the list, and the rows of three staying files by the prepared branch `legacy-open-retirements`, right after the deletion's commit. 10,995 tests are then left, of which 615 are new since the tag (three of them renamed). **If you say no to a class,** its rows are rewritten first, and their cost is estimated then.
