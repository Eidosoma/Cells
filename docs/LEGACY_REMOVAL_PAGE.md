# The legacy cleanup: what goes, and what you approved

25 November 2026. Seven minutes to read. Basis of each number: **(m)** measured, **(r)** read in the code, **(e)** estimated.
The list behind this page is `validation/legacy_port/removal_list.tsv` on branch `legacy-removal-list`: one row per file, with its
owner, reason, basis and state.

**In one sentence.** All of `src/cells/legacy` goes in one deletion, with everything that only served it. What you use comes back in
the engine's own forms. The old code, its runs and its captures stay at the tag `pre-cleanup-2026-11-25` and in
`/mnt/workspaces/Cells/legacy-captures-20261125`.

**Status.** You approved the losses on 25 November (D386): yes to the table in section 3, the cell-zone transporter left at the tag,
NKCC and the generic symport ported in the cleanup, and D211's other ports as the next step after it. **The counts below are the final
ones, but for what the builders still add. The deletion (branch `legacy-deletion`, in place of 9b0debe6) is merged only after you have seen them, and
you say yes or no to the optional batch.**

## 1. Counts, by area

| Area | Goes | Lines | Basis |
|---|---|---|---|
| `src/cells/legacy`, and its entry | 322 files | 75,581 | (m) |
| Four law tables in `laws/channels` (of the tissues `@9` to `@12`) | 4 files | 286 | (m); they hold no law, only which code is which (r) |
| Tests | 265 of 894 files | 93,356 | (m); which ones, by the dry run and by reading |
| Test helpers | 37 files | 3,792 | (m), import graph |
| Validation drivers and references | 739 of 1,720 files | 207,146 | (m); 433 of them read one by one, the rest by import graph and names |
| Scripts | 30 of 123, two of them already deleted | 10,520 | (m) |
| Configurations | 116 of 157 | JSON | (m) |
| Examples | all 15 (ten inputs, five guides) | JSON | (m) |
| Test data | 7 files | 1,200 | (m) |
| Test IDs | **9,284 of 21,927**: 9,023 in files that go, 261 rows in files that stay | | (m), collection of the staged deletion |
| Test IDs of the files being rewritten | 314, in 10 files: 138 in the two that moved onto the new laws (60 rewritten, 70 dropped, 8 left to the calcium worlds), 176 in 8 files still to be rewritten | | (m); those 8 files do not import until then |
| Written or rewritten by an owner | 193 files edited (67 of them documents), 16 tests retargeted | | (r); 178 of the 193 edits are done, and one of the 16 tests |
| **Optional, your yes or no:** the old families' own references and the last REF-era folders | 166 files: 40 helpers, 37 tests, 69 scripts, 20 REF-era files | 49,279 | (m); 1,933 more test IDs, 192 more test-seconds in tiers 1 and 2 |

On the tree without all of this, **12,753 tests collect and only the 8 files above fail to** (m). Apart from the retargeted tests, no
remaining file imports or loads anything that goes, by any way of importing (m); the rename's tool and one guard still name some of it. The
deletion saves 2,574 of 13,784 test-seconds in tiers 1 and 2 (m), about 8 minutes of wall per full
gate (e: 0.186 s of wall per test-second, measured 24 November). 142 of 222 tier-3 files go (m). The gate's fingerprints lose 127
definitions in 123 files, of 274 (m); G1's 113 worlds are unaffected (r).
**Measured where:** files and lines at 49529e71, the tag's commit; seconds in the tier record; IDs, imports and the dry runs at `legacy-cleanup` 34d173d7;
the parity runs at 63c181fc, on a tree without 1,472 of the files (the other 63 are outside their import chain).

**The optional batch** is what the oldest families were checked with: their independent references, trajectories, audits and tests, and the last REF-era
contacts. The deletion does not need it, because it imports nothing that goes. Nothing that stays uses it: no test, no re-expression reference, no kept
law, no capture (m, import graph; the re-expression's criteria, notes and branches do not name it). Its frozen panels stay as records either way. One
of its files is the reference of Kv1.5's 19 cases (the open condition in section 3). **The lead recommends that it goes.**

## 2. What comes back

| You use | It becomes | Needs |
|---|---|---|
| The JUPITER world, the cluster base, the assembly cell, the integrated ensemble's world | closed `resolved_pump_tissue@3` worlds, same equations | the assembly coupling, now in; the worlds themselves |
| The four calcium clusters | a composite over @3, one store per cell | the rest of the calcium work, below |
| The assembly command lines and ensemble kinds | CPU batch runs; the GPU path is **parked** | the same as their worlds |
| NKCC and the generic symport | `na_k_2anion_symport_reversible_tanh@1` and `electroneutral_symport_reversible_tanh@1`, on the transporter kind | nothing: in |

**In the engine now (r, at 34d173d7):** the Na/Ca exchanger; one pump law for an ion of any valence, `atp_driven_transporter_mass_action_positive@2`, for
the plasma's calcium pump and the store's; the two symports; the release's factor and its source; the assembly coupling; and the CaV1.2 law. **Not yet:** a
channel's step bound, so a CaV1.2 population is refused by name; the step terms that admit the pump at a store's node; and the loop's bound.

## 3. What is lost, what stays, and what waits

**The laws stay (D211)** in live `laws/`, with their references and a test of each kernel. Only the old tissue that hosted them goes.

| Group | Laws | Waits for |
|---|---|---|
| Kv1.1 to Kv1.4, Kv1.6 | 5 | nothing: registered on @3 |
| Voltage-only Na and K: Kv2, Kv3, K_fast, Nav1.3, the rat Navs, Nav1.6, three dynamic Morris-Lecar | 15 | one module each on @3; no engine feature |
| CaV1.2 | 1 | registered on @3; a population waits for the channel's step bound |
| Calcium and HCN: nine more CaV laws, six HCN laws | 15 | the same step |
| Instantaneous Morris-Lecar | 7 | G-2, a law without a gate |
| Calcium-activated K | 1 | G-3, which the cardiac plan's H1 already holds |

D211's programme is recorded as open, after the cleanup, in `docs/CORE_LAWS_ROADMAP.md`. `test_channel_law_kernels.py` tests three HCN laws that would have
had no test, and keeps the kernel rows of three tissue tests that go.

**A condition of D196 is open:** before a batch drops a test that is a live law's only reference check, the check moves beside the law and becomes its
declared test. D196 names Kv1.5's 19 cases. They have not moved, and `kv1p5_mh@1` declares no test (m). What stays checks the kernel against BETSE, run out
of process, and whole tissues against an independent reference (r). One row beside the law is proposed, and the deletion's script refuses to make the branch
until the list says it is there. (An earlier commit of this cleanup had dropped the roadmap's line about it; the line is back.) No other live law module
loses every test that reaches it, but the mass-action kernel's, which is still checked through its operator; one row of it moves as well (m, import graph; r).

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
| `source_decay@1`, `emt_mirna@1`, `passive_pair@1` (G1, G2), source-pair terms, neutral mobile leak, mitochondrial passive (I1 to I3, I11) | Gone; the tests that used them run live worlds. U34, U37, U38, U39 and U47 lose a law record in the viewer's inventory. |

**Nothing in use is lost** in the oldest families (A11), the baths and clusters (A10), mitochondria (C4), water, injury, bath schedules, barriers and
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

265 files with 9,023 IDs test families that are canonical elsewhere, dropped or retired. **16 tests of used capabilities are rewritten, not
deleted:** the store, the four calcium worlds, the assembly cell and cluster, the integrated ensemble, the JUPITER planning, and the cotransport laws, which
are done. Of the 261 IDs that leave files that stay, 187 were rows on worlds that went (107 replace them), 70 are the parity rows, 3 followed the old
registry, and one is a refusal that the calcium work replaced. `removed_rows.tsv` names each, with the 314.

## 6. Records, and what is open

- **Records stay:** 53 protocol and data files, the other results, the design notes and the decisions.
- **Open:** the builders' 15 tests, one law file and three validation scripts; the two rows that move first (section 3); the words of four library pages;
  the rename's tool, table and note; the tier records. The other documents are done: 48 say what left, and the run guides name live worlds, each command
  run once.
- **The deletion is one commit,** made from the list by a script, in place of 9b0debe6. Its dry runs on `legacy-cleanup` f38f6789, c368c9f2 and 34d173d7
  removed 1,529 files (six are gone already), found every path, and broke no import but the retargeted tests', 8 of them now (m); with the optional batch
  1,695, and the same 8. Two edits are in the same commit: one guard's list, and the old exchanger's kernel, which only legacy calls (`plasma_calcium.py`;
  the pump's kernel stays, since `ca_atp_mass_action_positive@1` runs it). On that tree the 15 library pages pass their check (m).
- **On commit 63c181fc:** its message's numbers are wrong. Measured: the drivers load six Python files (and two JSON protocols) where they loaded 24.
- **Thirteen names** in live laws and numerics that only legacy calls, or nothing, are listed for their files' owners, after the core edits.
- **Not run:** no gate and no suite. The full test of the cleanup branch is the test of it.
