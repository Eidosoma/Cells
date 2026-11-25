# The legacy cleanup: what goes, and what you approve

25 November 2026. Five minutes to read. Basis of each number: **(m)** measured, **(r)** read in the code, **(e)** estimated.
The list behind this page is `validation/legacy_port/removal_list.tsv` on branch `legacy-removal-list`: one row per file, with its
owner, reason and basis.

**In one sentence.** All of `src/cells/legacy` goes in one deletion, with everything that only served it. What you use comes back in
the engine's own forms. The old code, its runs and its captures stay at the tag `pre-cleanup-2026-11-25` and in
`/mnt/workspaces/Cells/legacy-captures-20261125`.

## 1. Counts, by area

| Area | Goes | Lines | Basis |
|---|---|---|---|
| `src/cells/legacy`, and its entry | 322 files | 75,581 | (m) |
| Tests | 266 of 894 files | 93,983 | (m); which ones, by the dry run and by reading |
| Test helpers | 36 files | 3,694 | (m), import graph |
| Validation drivers and references | 259 files, and **206 more not yet decided** (56,818 lines) | 72,112 | (m), import graph and names; a reader is deciding the 206 |
| Scripts | 28, and two that B deleted | 8,678 | (m) |
| Configurations | 116 of 157 | JSON | (m) |
| Examples | all 15 (ten inputs, five guides) | JSON | (m) |
| Test IDs | **9,117 of 21,927, a floor** | | (m), the gate's own collection; IDs lost inside edited or retargeted files are not counted |
| Written or rewritten by an owner | 159 files edited, 15 tests retargeted | | (r) |

It saves 2,580 of 13,784 test-seconds in tiers 1 and 2 (m), about 8 minutes of wall per full gate (e: 0.186 s of wall per test-second,
measured 24 November). 142 of 222 tier-3 files go (m). The gate's fingerprints lose 127 definitions in 123 files, of 274 (m); G1's 113
worlds are unaffected (r).

## 2. What comes back

| You use | It becomes | Needs |
|---|---|---|
| The JUPITER world, the cluster base, the assembly cell, the integrated ensemble's world | closed `resolved_pump_tissue@3` worlds, same equations | the assembly coupling only |
| The four calcium clusters | a composite over @3, one store per cell | four features |
| The assembly command lines and ensemble kinds | CPU batch runs; the GPU path is **parked** | the assembly coupling |

How the features look now (r; no new prices):
- **The plasma calcium pump and the Na/Ca exchanger need no engine feature.** The pump is @3's own at another standard state; the exchanger
  is one law module.
- **Smaller than the plan priced:** the calcium-gated opening, the assembly coupling, and the store.
- **Not smaller:** calcium through a channel. The engine refuses a buffered trace ion that a channel carries.

## 3. What is lost, and what replaces it

| Row | In one sentence |
|---|---|
| Oldest families (A11) | Nothing in use is lost; @3 does the same physics. |
| Baths and clusters (A10) | Nothing in use is lost; the JUPITER and ensemble worlds become @3 worlds. |
| Na, K and Cl channel catalogue (A3) | Nothing in use is lost; Kv1.1 to Kv1.6, Kir2.1, Nav1.2 and the leaks are @3's laws, and the other kernels stay. |
| Calcium and cation channels (A4) | The families go and their kernels stay; one can run once the calcium feature lands. |
| Instantaneous and calcium-activated channels (A5, A6) | The families go and nothing replaces them (candidate requests G-2, G-3). |
| Owned calcium in the tissue, closed or open (B6, B7) | The models go, their parts are rebuilt by the ensemble, and nothing else used them. |
| Finite ATP, ADP and phosphate pools, and the finite-fuel pumps (C2, I4, I5) | What legacy has goes, so the capability is not in the engine after the cleanup but is not lost for good; row fuel for the Na/K pump is a candidate request you may make, and none is made yet. |
| ATP-driven, regulated and cotransport energy models (C3) | Canonical in part; the finite-fuel forms wait for a request. |
| Mitochondria (C4) | Canonical, in a fuller form on the transporter kind. |
| Water, injury, bath schedules, barriers, membrane profiles (D3, D4, D6 to D8) | Canonical: `resolved_pump_water@1` and `@2`, `cells.patch_damage@1`, `scheduled_bath_composition@1`, and @3's schedules. |
| Hard ceilings on an ion's total (D2) | Lost; a check on the @3 line can be asked for. |
| Lateral redistribution and mobile proteins (D5) | Lost; the nearest pieces are `membrane_entity_state@1` and trafficking. |
| Cutting cells out (D9) | Lost until you ask for an operator. |
| BETSE-facing preparation (P1) | Gone; it may not live in the engine anyway. |
| Cotransport kernels (I7 to I9) | KCC is canonical (`k_anion_symport_mass_action@1`); the two that D211 marked to port stay only in the tag. |
| Cell-zone transporter, source-pair terms, neutral mobile leak, mitochondrial passive, older finite pumps (I1 to I5, I10, I11) | Gone; U34, U37, U38, U39 and U47 lose a law record in the viewer's inventory. |
| Physiology stack and REF-era BETSE drivers (D374) | You retired them; records stay. |
| `source_decay@1`, `emt_mirna@1`, `passive_pair@1` (G1, G2) | Gone; the tests that used them move to live worlds. |

## 4. Commands, examples, scripts, the clock, the GPU

| What | In one sentence |
|---|---|
| `tissue-phase`, `tissue-geometry`, `tissue-profiles`, `excise` | Removed. |
| `assembly-cell`, `assembly-cluster`, and their two ensemble kinds | Refused by name, saying they are parked and where they are re-expressed. |
| Ten example inputs and five guides | Removed; they serve those commands. `examples/active_tissue_phase/continued.request.json` is already refused on main (the lead's reading, not rechecked). |
| `scripts/legacy_inventory.py`, `scripts/source_moves_plan.py` | Deleted by stream B: records of old moves. |
| 28 build and audit scripts of September and October | Removed with the builds they checked. |
| The refinement clock | Removed with its two tests; no remaining model uses it. |
| GPU ensembles of assembly clusters | Parked; the GPU coverage of `test_gpu_execution`, `test_batch_identity` and two GPU integration files moves to @3 if that is cheap, and is lost until the GPU path returns if it is not. |

## 5. Tests

266 files with 9,117 IDs test families that are canonical elsewhere, dropped or retired. **15 tests of used capabilities are rewritten, not
deleted:** the store, the four calcium worlds, the assembly cell and cluster, the integrated ensemble and the JUPITER planning. One more
goes that was first kept for the JUPITER world, `test_spatial_extracellular_acceptance_resources.py`: it checks only the old
acceptance records.

## 6. Records, and what is open

- **Records stay:** 22 protocol files that only going files read, the other protocols and results, the design notes and the decisions.
- **Pending:** the 206 validation files, each being read (goes, cut the import, record, or ask). 21 folders are half and half until then,
  the largest `validation/tissue`, `validation/betse`, `topology`, `ensemble`, `transport`, `assembly` and `temperature`. The counts will
  move a little.
- **Not run:** nothing was run after the deletion; the gate on the cleanup branch is the test of it.
- **You are asked to approve** this list, in the order on the cleanup branch, and to say if a row above is wrong.
