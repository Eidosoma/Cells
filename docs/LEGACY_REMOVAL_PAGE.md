# The legacy cleanup: what goes, and what you approved

25 November 2026. Six minutes to read. Basis of each number: **(m)** measured, **(r)** read in the code, **(e)** estimated.
The list behind this page is `validation/legacy_port/removal_list.tsv` on branch `legacy-removal-list`: one row per file, with its
owner, reason, basis and state.

**In one sentence.** All of `src/cells/legacy` goes in one deletion, with everything that only served it. What you use comes back in
the engine's own forms. The old code, its runs and its captures stay at the tag `pre-cleanup-2026-11-25` and in
`/mnt/workspaces/Cells/legacy-captures-20261125`.

**Status.** You approved the losses on 25 November (D386): yes to the table in section 3, the cell-zone transporter left at the tag,
NKCC and the generic symport ported in the cleanup, and D211's other ports as the next step after it. **The counts below are the final
ones. The deletion (9b0debe6) is merged only after you have seen them.**

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
| Test IDs | **9,283 of 21,927**: 9,023 in files that go, 260 rows in files that stay | | (m), collection of the final tree |
| Test IDs that come back | 314, in 10 files their builders are rewriting | | (m); those 10 files do not import until then |
| Written or rewritten by an owner | 190 files edited (63 of them documents), 16 tests retargeted | | (r); 178 of the 190 edits are done |
| **Optional, your yes or no:** the old families' own references and the last REF-era folders | 166 files: 40 helpers, 37 tests, 69 scripts, 20 REF-era files | 49,279 | (m); 1,933 more test IDs, 192 more test-seconds in tiers 1 and 2 |

On the tree without all of this, **12,488 tests collect and only the 10 files above fail to** (m). Apart from the 16 retargeted tests, no
remaining file imports or loads anything that goes, by any way of importing (m); the rename's tool and one guard still name some of it. The
deletion saves 2,574 of 13,784 test-seconds in tiers 1 and 2 (m), about 8 minutes of wall per full
gate (e: 0.186 s of wall per test-second, measured 24 November). 142 of 222 tier-3 files go (m). The gate's fingerprints lose 127
definitions in 123 files, of 274 (m); G1's 113 worlds are unaffected (r).
**Measured where:** files and lines at 49529e71, the tag's commit; seconds in the tier record; IDs, imports and the dry run at `legacy-cleanup` c368c9f2;
the parity runs at 63c181fc, on a tree without 1,472 of the files (the other 63 are outside their import chain).

**The optional batch** imports nothing that goes, so the deletion does not need it. It is what the oldest families were checked with: independent
references, trajectories, audits and their tests (the EMT pair and graph, the bioelectric cell and pair, the multispecies, voltage-gated, ionic-graph,
finite and spatial extracellular families), and the REF-era pump and gate contacts. Nothing that stays uses it (m, import graph); the
re-expression's criteria and design notes do not name it, and no kept law's reference is in it. Kept out because something does use them:
`tests/reference_er_calcium.py` and its four sisters, `spatial_cluster/reference.py`, `pump_contact/pump_reference.py` and
`voltage_gate_audit/gate_independent.py`. Its frozen panels (JSON) stay as records either way. **The lead recommends that it goes.**

## 2. What comes back

| You use | It becomes | Needs |
|---|---|---|
| The JUPITER world, the cluster base, the assembly cell, the integrated ensemble's world | closed `resolved_pump_tissue@3` worlds, same equations | the assembly coupling only, being built |
| The four calcium clusters | a composite over @3, one store per cell | four features |
| The assembly command lines and ensemble kinds | CPU batch runs; the GPU path is **parked** | the assembly coupling |
| NKCC and the generic symport | law modules on the transporter kind | a check of their tanh form against the cycle forms |

The plasma calcium pump and the Na/Ca exchanger need no engine feature: the pump is @3's own at another standard state, and the exchanger is one
law module, now built. Calcium through a channel is not smaller than priced: the engine refuses a buffered trace ion that a channel carries.

## 3. What is lost, what stays, and what waits

**The laws stay (D211).** The channel laws keep their kernels in live `laws/`, with their references and a test of each kernel. Only the
old tissue that hosted them goes.

| Group | Laws | Waits for |
|---|---|---|
| Kv1.1 to Kv1.4, Kv1.6 | 5 | nothing: registered on @3 |
| Voltage-only Na and K: Kv2, Kv3, K_fast, Nav1.3, the rat Navs, Nav1.6, three dynamic Morris-Lecar | 15 | one module each on @3; no engine feature |
| Calcium and HCN: ten CaV laws, six HCN laws | 16 | calcium through channels, being built |
| Instantaneous Morris-Lecar | 7 | G-2, a law without a gate |
| Calcium-activated K | 1 | G-3, which the cardiac plan's H1 already holds |

D211's programme is recorded as open, continuing after the cleanup, in `docs/CORE_LAWS_ROADMAP.md`. Three of the HCN laws would have had no test of
their kernel; `test_channel_law_kernels.py` gives them one, and keeps the kernel rows of three tissue tests that go.

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

**Nothing in use is lost** in the oldest families (A11), the baths and clusters (A10), mitochondria (C4), water, injury, bath schedules,
barriers and membrane profiles (D3, D4, D6 to D8): @3's line does the same physics. The owned-calcium tissues (B6, B7) go and the ensemble
rebuilds their parts. **The three parity files whose live BETSE run works keep it** (16, 38 and 25 rows pass on the tree without what goes,
and the 64 native captures equal the saved ones bit for bit (m)): they now take what they need from one module instead of 19 old ones.

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
deleted:** the store, the four calcium worlds, the assembly cell and cluster, the integrated ensemble, the JUPITER planning, and the
cotransport laws. 260 more IDs leave files that stay: 187 were rows on worlds that went (107 new or renamed ones replace them), 70 are the
parity rows above, and 3 followed the old registry (2 new).

## 6. Records, and what is open

- **Records stay:** 53 protocol and data files, the other results, the design notes and the decisions.
- **Open:** the builders' 16 tests, three files of laws and three validation scripts; the rename's tool, table and design note; the tier records; and one
  guard whose list changes in the deletion's own commit. The documents are done (`legacy-cleanup-docs`): 48 carry a note of what left, and the run
  guides name live worlds, each command run once.
- **The deletion is one commit,** made by a script from the list, on one branch that takes the place of 9b0debe6. Its dry run on `legacy-cleanup`
  f38f6789 and on c368c9f2 removed 1,529 files, found every path, left nothing under `src/cells/legacy`, and broke no import but the 10 tests' (m).
- **On commit 63c181fc:** its message says that the drivers load eight files where they loaded 24. Measured: six Python files (eight with two JSON
  protocols) where they loaded 24 Python files.
- **Four names in live laws and numerics** that nothing calls any more are listed for their files' owners, after the core edits.
- **Not run:** no gate and no suite. The full test of the cleanup branch is the test of it.
