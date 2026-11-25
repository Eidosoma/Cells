# The legacy cleanup: what goes, and what you approved

25 November 2026. Nine minutes to read. Basis of each number: **(m)** measured, **(r)** read in the code, **(e)** estimated.
The list behind this page is `validation/legacy_port/removal_list.tsv` on branch `legacy-removal-list`: one row per file, with its
owner, reason, basis and state.

**In one sentence.** All of `src/cells/legacy` goes in one deletion, with everything that only served it. What you use comes back in
the engine's own forms. The old code, its runs and its captures stay at the tag `pre-cleanup-2026-11-25` and in
`/mnt/workspaces/Cells/legacy-captures-20261125`.

**Status.** You approved the losses on 25 November (D386): yes to the table in section 3, the cell-zone transporter left at the tag,
NKCC and the generic symport ported in the cleanup, and D211's other ports as the next step after it. The same day you agreed that two things which your earlier
decisions held go too, kept at the tag: the network laws and the EMT-miRNA two-cell model (section 3). A second reader has read the list, the script and the optional
batch: safe, with corrections, which are in. **The counts below are at e24daab6, but for what the builders still add. The deletion (branch `legacy-deletion`, in
place of 9b0debe6) is merged only after you have seen them. One answer is left: the optional batch, yes or no.**

## 1. Counts, by area

| Area | Goes | Lines | Basis |
|---|---|---|---|
| `src/cells/legacy`, and its entry | 322 files | 75,581 | (m) |
| Four law tables in `laws/channels` (of the tissues `@9` to `@12`) | 4 files | 286 | (m); they hold no law, only which code is which (r) |
| Tests | 265 of 894 files | 93,356 | (m); which ones, by the dry run and by reading |
| Test helpers | 37 files | 3,792 | (m), import graph |
| Validation drivers and references | 738 of 1,720 files | 207,021 | (m); 433 of them read one by one, the rest by import graph and names |
| Scripts | 30 of 123, two of them already deleted | 10,520 | (m) |
| Configurations | 116 of 157 | JSON | (m) |
| Examples | all 15 (ten inputs, five guides) | JSON | (m) |
| Test data | 7 files | 1,200 | (m) |
| Test IDs | **9,284 of 21,927**: 9,023 in files that go, 261 rows in files that stay | | (m), collection of the staged deletion; 593 are new |
| Test IDs of the files being rewritten | 314, in 10 files: 138 in the two that moved onto the new laws (60 rewritten, 70 dropped, 8 left to the calcium worlds), 176 in 8 files still to be rewritten | | (m); those 8 files do not import until then |
| Written or rewritten by an owner | 212 files edited (83 of them documents), 17 tests retargeted | | (r); 195 of the 212 edits are done, and one of the 17 tests |
| **Optional, your yes or no:** what the oldest families were checked with, a graph study that never ran, and the last REF-era folders | 165 files: 40 helpers, 37 tests, 68 scripts, 20 REF-era files | 49,055 | (m); 1,933 more test IDs, 192 more test-seconds in tiers 1 and 2, about 36 s of wall per full gate |

On the tree without all of this, **12,922 tests collect and only the 8 files above fail to** (m). 58 of them are in seven more of the files being
rewritten: 24 use what goes and are expected to fail until then, 6 run on a GPU only and use it too, and 28 do not use it (r). Apart from the retargeted tests and
the three validation scripts that are being rewritten, no remaining file imports or loads anything that goes, `lean/` and `visualizer/` included, by any way of importing (m). The nightly's record of the files that tests open
(main, tiers 1 and 2) showed one test more, which is now on the list, and no other that still does (m, r); tier 3 is known by its imports only. The rename's tool, one
guard, the words of three parity files and six of the viewer's files still name some of it (m), and so do records (155 reports, 56 validation protocols and source maps) and
documents. The deletion saves 2,574 of 13,784 test-seconds in tiers 1 and 2 (m), about 8 minutes of wall per full gate (e: 0.186 s of
wall per test-second, measured 24 November). 142 of 222 tier-3 files go (m). The gate's fingerprints lose 129
definitions in 125 files, of the 194 in the three folders (m, the tool's own enumeration). The tag has 173: the live engine's two batch configurations brought four, and
the re-expression's format sample 17, which are placeholders that no parser accepts. G1's 113 worlds are unaffected (r). The fingerprint tool's comparison
takes both lists now: `removed_definitions.txt` (129), and the additions, of which 4 are written and 21 are found; the lead makes that list again for the final head. The tier
record loses 265 rows in the deletion's own commit, since the gate refuses a row without a file.
**Measured where:** files and lines at 49529e71, the tag's commit; seconds in the tier record; IDs and imports at 5429a49b, and the last dry runs at e24daab6, which is `legacy-cleanup` 8d82e435 with the documents (only documents changed between the two);
the parity runs at 63c181fc, on a tree without 1,472 of the files (the other 63 are outside their import chain).

**The optional batch** has four parts: 50 files of E02-SW1's graph study, a frozen protocol that never ran, for a model never built
(`docs/E02_SWITCHING_PROTOCOL.md`); 94 of the oldest families' own references, trajectories, audits and tests (11 of them NUM-008's); 20 of the last REF-era
contacts; and one old test context. The deletion does not need it, because it imports nothing that goes. Nothing that stays uses it: no test, no re-expression
reference, no registered criteria, no kept law, no capture (m, import graph; the second reader agrees). With it, 27 documents name files that are gone and 43
relative links break; notes for 21 of them are prepared, and the other six are records. Many of the 21 are pinned by hash in old reports or frozen panels; nothing
that stays checks those pins. Its frozen panels stay as records. **The lead recommends that it goes.**

## 2. What comes back

| You use | It becomes | Needs |
|---|---|---|
| The JUPITER world, the cluster base, the assembly cell, the integrated ensemble's world | closed `resolved_pump_tissue@3` worlds, same equations | their registered runs and the judge; the definitions (Part 1), the run driver and the assembly coupling are in |
| The four calcium clusters | a composite over @3, one store per cell | their definitions and criteria (Part 2); the calcium work is in |
| The assembly command lines and ensemble kinds | CPU batch runs; the GPU path is **parked** | the same as their worlds |
| NKCC and the generic symport | `na_k_2anion_symport_reversible_tanh@1` and `electroneutral_symport_reversible_tanh@1`, on the transporter kind | nothing: in |

**In the engine now (r, at e24daab6):** the Na/Ca exchanger; one pump law for an ion of any valence, `atp_driven_transporter_mass_action_positive@2`, for
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
and all 44 are collected after the deletion (m). Three had lost their only direct check: Kv1.5 (the 19 cases that D196 names), the one-gate junction law and the
passive reaction kernel. Each has a row beside it now, with planted errors, and the first two are the laws' declared tests. **A fourth came out when the table was
rebuilt under one standard:** `edge_flux`, the junction flux of `reaction_transport@1`, loses its two direct rows of hand values; whole worlds against matrix
exponentials still check it. The lead decides whether it gets a small row first, and the script makes no branch until then. One helper, `bernoulli`, loses its
one row of hand values; two rows that stay hold its slope, and every law that calls it is checked in decimals. With the optional batch gone as well, no row of the
table changes (m); which rows check a kernel was read (r).

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
| `assembly-cell`, `assembly-cluster`, and their two ensemble kinds | Refused by name, saying they are parked and where they are re-expressed. |
| Ten example inputs and five guides | Removed; they serve those commands. |
| 28 build and audit scripts, and two records of old moves | Removed with the builds they checked. |
| GPU coverage of `test_gpu_execution`, `test_batch_identity` and two GPU integration files | Moves to @3 if that is cheap, and is lost until the GPU path returns if it is not. |

## 5. Tests

265 files with 9,023 IDs test families that are canonical elsewhere, dropped or retired. **17 tests of used capabilities are rewritten, not
deleted:** the store, the four calcium worlds, the assembly cell and cluster, the integrated ensemble, the JUPITER and the catalogue planning, and the cotransport
laws, which are done. Of the 261 IDs that leave files that stay, 187 were rows on worlds that went (107 replace them), 70 are the parity rows, 3 followed the old
registry, and one is a refusal that the calcium work replaced. `removed_rows.tsv` names each, with the 314.

## 6. Records, and what is open

- **Records stay:** 59 protocol, data and record files, the other results, the design notes and the decisions.
- **Open:** the builders' 16 tests and three validation scripts; the rename's tool, table and note; the list of added definitions, made again for the final head; tier 3's record.
- **The deletion is one commit,** made from the list by a script, in place of 9b0debe6. Its dry runs at f38f6789, c368c9f2, 34d173d7, 9c30104e, 36165b70, 1fec66a6, 5429a49b and e24daab6 found every path;
  the last removed 1,528 files (six are gone already), and broke no import but the retargeted tests', 8 of them (m). With the optional batch it removed 1,693, with the same 8 (m).
  The same commit takes one guard's list, the tier record's rows, the old exchanger's kernel and nine names that only legacy uses (`plasma_calcium.py`,
  `er_calcium.py`, `calcium_gates.py`), and the words of three library pages. On that tree the 15 library pages pass their check (m). One old function, the store's `release_open`,
  stays unless the lead says that it goes: only a test that is being rewritten names it, and the roadmap calls it the older kernel of D211's store release, while the calcium note says that it goes. Both answers are prepared and were run.
- **Documents:** 57 say what left, with seven folders of old drivers, and the run guides name live worlds. 420 relative links into removed files break, in 52 Markdown files
  (m), most of them under such a note.
- **14 reference files stay** whose last test goes: each is imported by an old native probe or reference that stays and that no test runs at the tag either (m).
- **On commit 63c181fc:** its message's numbers are wrong. Measured: the drivers load six Python files (and two JSON protocols) where they loaded 24.
- **Five names** in live laws and numerics that nothing calls any more are listed for their files' owners, after the core edits.
- **Not run:** no gate and no suite. The full test of the cleanup branch is the test of it.
