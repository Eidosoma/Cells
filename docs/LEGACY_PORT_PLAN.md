# Legacy port plan: everything Cells uses leaves legacy, in canonical forms

**Status: the route is decided (25 November 2026, D383).** The user chose to re-express, on one branch, with one deletion and one full test
at its end: "Re-express and put everything else on hold and test just once after the re-expression". A CPU re-expression of
the calcium ensemble counts as done; its GPU path is parked.
- **The branch and the order** (`legacy-cleanup`, from 43b22d40, merged by the lead): the live side without legacy; the deletion, one, whole; the
  four features; the re-expressed ensemble; the ID move last. No gate, tier or suite runs until it is coded.
- **So C-1, C-3 and the gates between steps fall away.** §7 is kept as the record of the three routes: its prices, and its ordering, are not the plan now.
  §7.3's live-side items are done or under way on stream B's branch, and §7.5's hand edits are split between B, C and the re-expression's builders.
- **Where the work is now:** §14, the re-expression map; `validation/legacy_port/removal_list.tsv` on branch `legacy-removal-list`,
  with its test IDs; and the user's page, `docs/LEGACY_REMOVAL_PAGE.md`, on this branch.
- **D386 (25 November): the user approved the losses.** The cell-zone transporter stays at the tag; NKCC and the generic symport are ported in
  the cleanup; D211's other ports follow it. The page had set those laws among the lost ones, against D211 and against rows A3 to A6 here.
  §14.7 has the final list and what D211 keeps.
- **Nothing on the cleanup branch needs the old core** while the re-expression is written (my reading, and the lead's). Main, the
  tag `pre-cleanup-2026-11-25` and the captures hold it, and no canonical world reads it. The captures (`science-76a498ae`, and the
  integrated ensemble's world captured at the pre-cleanup tag) are the reference.
- **The measured parts of the plan still stand:** the dry run (§2.1), the coverage table (§3), the gaps (§4, with G-5 and G-7 now read as smaller, §14), and
  the test evidence (§9). What changed since: rows B2 and I8, and §8's examples, were corrected on 25 November, and the removal list
  replaces the counts of §9 and §10.
- **Line citations are at `ce4780d2`,** except that §14 and `kinds/transporter.py`'s lines are at `43b22d40` or `c9da0fdb` as each says,
  and that PROGRESS.md was refreshed on main at `0767867f` (D377), so its lines here hold at `ce4780d2` only. The earlier notes said no other cited
  file had changed up to `c9da0fdb`, without checking; `transporter.py` had.
- **D377 records this plan's figures at `ef344334`.** "15 direct edits, with another 50 fixture files open" is replaced by §7.5; the 58%, the widening and
  the user's choice stand as the record.

**What is decided:**
- **D346 and D348:** port what is used, then delete `src/cells/legacy/` whole, in one deletion with one gate.
  Main is tagged first.
- **D369, the user's direction:** "the legacy work is clearly important cleanup we need to make sure to get
  everything we're actually using out of there in our canonical formats".
  - The end state is canonical: everything used is re-expressed in the engine's laws, models, operators and
    definitions, under the rename's IDs. A relocated legacy island is not an end state.
  - The scope is a test of use (§2), not a list of IDs.
- **D374, the user's decisions:**
  - **The calcium ensemble is kept, and re-expressed in canonical form.** That is the assembly-regulated
    cell and cluster on `spatial_calcium@1`–`@4`, run by the GPU ensemble runner and the JUPITER readiness
    check.
  - **The physiology stack is retired.** The 17 drivers on legacy's five BETSE IDs and the 18 REF-era drivers
    go in the approved deletion batch, with their records kept. The live BETSE parity ladder on
    `resolved_pump_tissue@1`–`@3` stays, and its one legacy import, a re-export of a live helper, becomes a
    direct import.
  - **The route** comes back to the user with prices. That is §7: A, B and C.
  - **The price it quotes is this plan's earlier one:** a rough 16 to 28 agent-days for five features. §4
    corrects it: four features for a CPU re-expression, and G-8 apart, unpriced.
- **The composite's GPU path is closed, not open (D336, D338, D371).** An earlier version of this plan called it
  "D336's open GPU qualification". That was wrong.
  - D336 closed FR-17's GPU qualification of the composite as failed. A new attempt is a fresh registration
    and the user's decision.
  - D338's refusal in the vector windows is for `resolved_pump_composite@1` only. Batched GPU runs of
    `resolved_pump_tissue@1` and `@3`, and the calcium ensemble's legacy ionic families, keep their evidence.
    A re-check of that evidence is logged, not started.
  - FR-53's note asks the GPU question as its Q5, a fresh registration after FR-53 lands. D371 rules that Q5
    waits for FR-53's build, and the user set FR-53 to normal priority. D371 as committed records this as
    the lead's ruling.
  - D372 carries a builder's report, not yet checked, that the plain `runner.run` still admits the composite on
    a GPU. At `ce4780d2` it has no refusal there.
- **D374, the lead's rulings:**
  - no retirement before the rename's move;
  - **inside the deletion batch:** @3's checks against `resolved_tissue@8` stay for now and move to an
    independent validation reference at the end (Q5 (a)); `source_decay@1`, `emt_mirna@1` and
    `passive_pair@1` are deleted, and the conftest's users point at a live world (Q6 (a));
  - **Q5 (a) is widened to `resolved_tissue@1` and `@2`** (the lead's ruling on the review, 24 November). Their
    model code is live and live-subject tests parse both, so they are used (D369's test). In route C the first batch
    moves their dispatch to the live registry, so that a kept legacy hub is not what live code needs;
  - **waiting for the route:** which engine gaps to request, and this plan's three lead rulings;
  - tolerances are derived in each re-expression's registration, never ruled.
- **The lead's rulings on the dry run (25 November):**
  - the eight planning tests and `test_recovery_response_grid.py` are live code with a legacy vehicle (§2);
  - `test_spatial_extracellular_acceptance_resources.py` is kept core, as the JUPITER world's (§7.5 notes what it
    covers);
  - the two refusals in legacy's `to_dict` join C-1's live-side items, with a test (§7.3);
  - the moved entries for `resolved_tissue@1`, `@2` and `@8` match by exact type.
- **D371, on the rename's Q3:** the 18 live pieces that legacy also spells are re-spelled in legacy's files
  too, after a check for pinned legacy config digests. Legacy outlives the rename on every route.
- **BETSE (AGENTS.md, 8 November):** an outside reference only. Nothing in `src/cells` imports, executes,
  re-hosts or copies BETSE code, or carries its conventions or names. Laws BETSE also uses are fine under
  neutral names, with the source cited.
- **New IDs** below are proposals, to be named in the rename note (`docs/ID_HIERARCHY_DESIGN.md`).

**Records:** `/mnt/workspaces/Cells/legacy-port-plan-20261124/`.
- `inventory.json` and `probe4.json`: the import graph, each file's legacy evidence, and each test file's
  class. `probe.json` and `probe2.json` hold superseded figures.
- `probe8.json` and `probe10.json`: route C's kept set, and its first deletion as an edge cut with the corrected
  going tests. They supersede `probe5.json` and `probe7.json`, whose kept sets left out the command lines and whose
  file classes had false positives. `probe6.json` gives the figures by the edits each rests on, and `probe9.json`
  the surviving files that name a deleted ID. `going_why.json` records which rule selected each going test.
- `inventory_records_now.json`: the protein inventory's 81 law records, mapped to today's files.
- `probe-capture-{a,b,c}/`: the capture probes.
- `legacy_defs_with_shared.json`, and `tools/` for the probes' scripts.
- `dry13.json` sorts the dry run's 147 files, and `tools/dry*.py` hold the reads of its records. `dry15_goes.json` lists
  the files that go: 139 in tier 3, and in tiers 1+2 100, which are the 95 that break and five that pass; the four
  physiology tests that pass (§7.5) are not in it.
- The dry run's own records are `/mnt/workspaces/Cells/legacy-dry-run-20261124/` (§2.1).
- The lead's removal analysis of 24 November is `/mnt/workspaces/Cells/legacy-removal-20261124/`.

Paths are repository paths unless they start with `/mnt/`.

## 1. Summary

**Use, measured (§2, §6).** By use, most of D348's eleven IDs are not used. What is:
- **The calcium ensemble,** kept by D374: the assembly-regulated cell and cluster over `spatial_calcium@1`–`@4`,
  with their nested `er_calcium@1`, `spatial_extracellular@2` and `finite_extracellular@2`.
- **`spatial_extracellular@2`,** for the JUPITER readiness check.
- **`resolved_tissue@8`,** @3's reference world, kept for now (Q5 (a)).
- **`resolved_tissue@1` and `@2`,** which earlier versions missed. Live-subject tests parse both (row A12), and
  their model code is live. Q5 (a), as widened, moves their dispatch to the live registry (§7.3).
- **As vehicles of live tests only** (§3, group V): `source_decay@1`, the conftest's world, with five more small
  families in the shared batch fixture; and the worlds behind the ensemble planner's, the refinement clock's and the
  projective mode's tests. Those worlds go, and their users are retargeted (Q6 (a), and the lead's ruling).

No registered protocol in force names a legacy model, and the claimed BETSE parity runs on live models.

**The dry run (§2.1) deleted all of legacy in a scratch copy.** 147 of the 671 tier 1+2 test files then fail, and all
eleven tier-3 files it ran. No live engine module needs legacy to import.
- **105 of the 147 test legacy itself.** 95 of them go at route C's first deletion (2,378 test-seconds, 17%), and ten
  stay with the core.
- **42 do not:** 27 test live code on a legacy world, 12 are the parity ladder's, through two imports, and three fail
  for single reasons.
- **It confirms** the uses in rows A9, A12, E4 and G1, **and corrects** those in A11, C3, G1, G2 and G3. No row
  changes class, but G1's now rests on a live world with a scheduled input, which is not found yet (§12, risk 17).
- **It deleted the whole of legacy,** not route C's pruned tree, and it ran 11 of 222 tier-3 files. §2.2 lists what it
  does not show.

**The coverage table (§3)** has 51 rows by capability and consumer:
- 40 capability rows;
- 11 rows for the protein inventory's law records that still point into legacy (group I).

Each row is classed as canonical, expressible today, needing an engine feature, or dropped, and states how
firmly it was checked. Five rows on the vehicles (group V) stand beside it.

**The calcium ensemble's features (§4), in two parts:**
- **A CPU re-expression needs four:** G-1 calcium-permeant channels on @3, G-4 an ER store, G-5 IP3-gated
  release, and G-7 assembly coupling. With NCX's registration, the rough guess is 13.5 to 22 agent-days.
- **Its GPU runs also need G-8,** the composite on a GPU. That has no price: the last qualification closed as
  failed (D336).
- All are candidate requests, each to be sized by its own design note. None is requested, sized or scheduled.
- The planned human cardiac laws (`docs/HUMAN_CARDIAC_LAWS_DESIGN.md`, H1 and H2) already cover part of G-1
  and G-4, and NCX. D211 folds calcium handling into that lane, so the two lanes' notes are coordinated.
- **Whether G-8 is needed at all depends on the G-4 and G-7 designs.** If the store and the coupling live on
  @3 instead of as composite operators, D338's refusal is not the one that applies. That is an inference, and
  the notes settle it.

**The choice that sets every date, and it is the user's (§13, Q1):** does a CPU re-expression of the ensemble
count as leaving legacy, with its GPU path parked, or does legacy's core wait for the GPU?

**Three routes, with the ensemble kept and the physiology retired (§7).** Lifetimes are counted in agent-days of
work that must finish first. No calendar date is supported for any route, because the features are unrequested,
unsized and unscheduled. The dry run adds about 2 to 3 agent-days to every route, for the live tests' worlds (§7.3).

| | A: relocate, then re-express | B: re-express directly | C: prune legacy in place, then re-express |
|---|---|---|---|
| Agent-days, beyond the features | 20–30 | 15–22 | 16–25 |
| Full gates | 5–7 | 4–5 | 4–5, two of them with tier 3 |
| Lane-hours | about 15–20 | about 12–15 | about 13–18 |
| **If a CPU re-expression counts:** legacy lives | until about 11–16.5 agent-days are done; then a relocated copy lives in live `src` for about 22.5–36 more | whole, until about 28–44 are done | at least 58% of its lines leave after about 6–9; the rest lives for about 23.5–38 more |
| **If legacy's core waits for the GPU:** legacy lives | until A-3, but **the copy is open-ended** in live `src` | **whole, open-ended** | **the core is open-ended**; the rest leaves at C-1 |
| In every gate meanwhile (tiers 1+2, measured) | the copy's own tests: 9 files, 52 test-seconds | every test of legacy itself: 109 files, 2,454 test-seconds (18%), about 7.6 minutes of wall | the core's own tests: 10 files, 56 test-seconds, about 10 s of wall |
| BETSE-rule risk | moderate to high: code built on BETSE-derived conventions enters live `src/cells`, and part of it is barred as it stands (§7.4) | lowest | low: nothing enters live `src`; the BETSE glue goes at C-1 |

**Recommendation: C,** under either answer.
- **The firm figure is at least 58% of legacy's lines** at its first deletion (up to 61%, if the prune left nothing
  of the dispatch hub, which it cannot). It needs no edit to a kept module apart from the hub. Larger figures, up to
  about 85%, are estimates that rest on further edits (§7).
- It is the only route whose standing cost stays small if no date ever comes. Under an open-ended date, A
  leaves a legacy copy in live `src`, and B leaves every legacy test in every gate.
- **It is the user's D346 choice again:** a partial deletion that keeps what the kept consumers use. D346 kept
  BETSE's part and the ensemble's. D374 retired BETSE's, so C keeps the ensemble's core alone.
- **D348's objection is smaller, but it is not 15 edits.** The dry run, and the reading after it, give about 49
  surviving files to change by hand at the first deletion, against D348's 180 files that used both parts; the pruned
  tree's own run fixes the number. All but a few would change on every route, because they drop a deleted world rather
  than split a kept one. The 50 fixture files that were open need none (§7.5).
- **Its weak point is the core's guards (§7.5).** Five of the core's ten test files in tiers 1+2 already fail in the
  record, and three cover an ID that goes. The ensemble's own physics tests are tier 3, three of them without a
  recorded outcome. `spatial_extracellular@2`, the JUPITER world, has no test of its own. So C-0's bitwise windows carry
  the prune's proof. A's copy has the same guards.
- **Its cost:** it reverses D348's "one deletion with one gate". There are two.

**Qualifying a re-expression (§8):** science-length captures at three steps from the pre-rename snapshot,
about 6–8 CPU-hours. Each re-expression's registration derives its own tolerance; never a ruled one.

**The user's questions (§13):**
- Q1, whether a CPU re-expression counts as leaving legacy;
- Q2, the route;
- Q3, whether D348's single deletion yields to two;
- Q4, which of the four features to request;
- Q5, whether to ask for a GPU attempt (G-8), which is separate.

## 2. What "used" means, and how it is measured

**Definition, fixed before counting.** A legacy capability is used when deleting it would take it from at
least one of these consumers:
- **U1, a live engine module:** for example the ensemble runner's kinds (`ensemble/families.py`, `cli.py`,
  `ionic.py`, `worker.py`).
- **U2, a test whose subject is live code** that uses the capability as a vehicle or reference: @3's
  reference world, or the conftest's `spec` fixture.
- **U3, a current document that claims a result resting on it:**
  - PROGRESS's plan and status tables;
  - `CURRENT_PLAN.md`, `SCIENTIFIC_BASIS.md`, `ROADMAP.md` and `EXPERIMENTS.md`;
  - the experiment designs and paper notes;
  - an operational runbook in force.
- **U4, a registered protocol, judge or reference in force** that runs it.

**Not a use:**
- a test whose only subject is a legacy model;
- a driver whose evidence no current document claims;
- a design note, closeout or report that records past work. Its evidence stays under `/mnt/workspaces/Cells`,
  and the pre-deletion tag reproduces it.

A document that points at a legacy module as an existing capability is a claim to correct (group H), not a
use.

**A vehicle is a use of its own kind** (the lead's ruling, 25 November). A live-subject test that runs on a legacy
world does not keep that capability. It obliges the deletion to replace the world with a live one, or to retire the
live code it drives on that code's own merits. Group V (§3) lists them.

**How it was measured:**
- **U4:** the rename probe's frozen set (233 files with registration tags or Freeze and Register commits)
  names no legacy model ID. U4 is empty.
- **U3:** a scan of PROGRESS, the plans, the scientific basis and the paper notes (§6). The claimed BETSE
  parity runs on modern models. The calcium ensemble's qualification is claimed in `docs/GPU_ENSEMBLES.md`,
  and the JUPITER runbook runs `spatial_extracellular@2`. The runbook also runs `test_gpu_execution.py` and
  `test_integrated_ensemble.py` on its nodes (`docs/JUPITER_RUNBOOK.md:167–168`).
- **U1 and U2:** the dry run (§2.1), and static evidence where it did not look (§9).

### 2.1 The dry-run deletion: what it measured

**What ran.** The tool is `validation/legacy_port/dry_delete.py`, on branch `legacy-dry-run` (144e0ef9). The records are
`/mnt/workspaces/Cells/legacy-dry-run-20261124/`: `out-c9da0fdb/` and `out-c9da0fdb-tier3/`, each with `result.json`.
- It copied the snapshot of `c9da0fdb`, deleted **all** of `src/cells/legacy/` with `registry/legacy_entry.py`, and
  turned each `legacy()` call into its miss branch, or into a loud refusal where there is none. That took 14 edits in
  seven live files.
- It ran tiers 1+2 from that tree on lane B, in 34.6 minutes. Each file is judged against the tier record and a
  control run of the same code (FR-50's full run at `0ae23bff`, which differs in two documents).

| Tiers 1+2: 671 files, 13,677 test-seconds | Files | Test-seconds |
|---|---|---|
| Pass | 508 | |
| Fail as in the record and the control, for other reasons | 16 | |
| **Fail with legacy gone** | **147** | **2,995 (22%)** |
| – legacy itself is the subject: the physiology stack (D374) | 30 | 921 |
| – legacy itself is the subject: this plan's kept core | 8 | 50 |
| – legacy itself is the subject: the rest | 67 | 1,463 |
| – live code with a legacy vehicle | 27 | 342 |
| – a live module needing legacy: one validation tool, `validation/betse/emulator/spatial_spec.py` | 4 | 73 |
| – other | 11 | 146 |

- **The classes are by subject,** from the tool's rules and then a review. 123 of the 147 stop at collection, so
  theirs rest on imports and reading, not on a test that ran. §9 sorts all 147 by what each needs, and checks the 67
  against the coverage rows.
- **17 of the 147 already failed or errored** in the record, for reasons of their own, such as missing saved
  references.
- **Tier 3:** the eleven files this plan's rows name were run, and all eleven fail: A12's six, A9's one, E4's one and
  G1's three. In `test_surface_pump.py` two of 42 tests fail for `resolved_tissue@2`; the review says a third fails
  with legacy present too, but its control was stopped before it wrote a record.
- **Configurations:** of 167 JSON files in `configs/` and `examples/`, 131 resolve before and 11 after. Of the 120
  that break, 19 hold kept IDs, so route C's first deletion takes 101.
- **Who imports legacy,** by the tool's sweep: 193 of the 893 test files (74 in tiers 1+2), 25 helper modules under
  `tests/`, 73 `validation/` files and 14 scripts. Five more scripts name it only in strings (§10).
- **Live code:** no live engine module needs legacy to import. The seven edited modules, the model table and
  `cells --version` run without it. What fails inside `src/cells` are misses at the places that resolve a model, and
  one refusal, the ensemble hooks' (`ensemble/families.py:168`).
- **Three things in live code come to light** and are C-1 items (§7.3). The dry run found that two refusals which live
  code needs sit in legacy's `to_dict`. Reading its failures adds two: an unknown ID is refused by its fields, and the
  refinement clock admits one model, which is legacy's.

### 2.2 What it does not show

- **Route C's pruned tree.** It deleted everything. Of its 147, C-1 does not break the core's ten, V5's six, the parity
  ladder's twelve or `test_model_table.py`. C-1 does break some that it passes (below). It proves nothing about the
  hub's prune; C-0's windows and C-1's own gate do that.
- **211 of the 222 tier-3 files.** 152 of them reach legacy by import, the calcium ensemble's own tests among them.
  By this plan's lists, 137 of the 152 test a legacy family that goes, two more are barrier-dispatch tests that go,
  eight are kept core, three are live (`test_batch.py`, and two planning tests like those of V2), and two are the
  emulator's. `test_batch_windows.py` is live too, and has no import evidence.
- **Live code and drivers that only legacy uses.** It left them in place, so tests that stop there pass:
  - `test_specs.py` and `test_run_view.py` use the conftest's or the batch fixture's world, whose spec, parser and
    dictionary are live (`definitions/specs.py`). They need a new world too;
  - `test_continuity_bypass.py` lists retired drivers by path (five of the physiology stack's among them), and refuses
    an entry whose file is gone.
- **Tests that pass without testing.** The result files keep no such list. The dry run's author gave one in its report
  (marked †). The rest were found here, by reading each passing file that reaches legacy and the refusal rows of the
  files that fail in part. The list is not exhaustive:
  - 45 refusal rows are met by the parse miss, because they expect a `ConfigError` with no message: 3 in
    `test_gpu_execution.py` †, 14 in `test_surface_tissue.py` and 28 in `test_surface_kinetic.py`. In the last two they
    are the only tests that pass. Five rows of `test_windows.py` have the same form, and I did not check which error
    met them;
  - six passing files still reach legacy by static evidence †. Four test pure functions or saved inputs of a driver whose
    run path imports legacy: `test_open_calcium_bath_energy_diagnostic.py`, `test_open_calcium_bath_energy_upstream.py`,
    `test_recovery_diagnostic_grid.py` and `test_environment_barrier_composition_transients.py`.
    `test_active_polygon_energy_contract.py` names legacy IDs as keys only. `test_integrated_ensemble_gpu.py` imports
    legacy inside the functions of `test_integrated_ensemble.py`, and all its tests skip;
  - three files ran no test, all skipped here and in the control †: `test_ensemble_gpu.py` (4),
    `test_integrated_ensemble_gpu.py` (4) and `test_voltage_gated_artifact_audit.py` (7).
- **References and drivers that never import legacy** pass whatever their subject is. §7.5's orphan lists find those.
- **The rest of the gate:** the IDs, crossrev and G1 were not run on that tree, nor any script or validation driver.
- **Any other revision.** It ran before the rename, so the tool's anchors must be re-read at the deletion's base.

## 3. The coverage table, by capability and consumer

**Classes:**
- **Canonical:** canonical already;
- **Expressible:** expressible today on canonical pieces;
- **Feature:** needs an engine feature, with its gap in §4;
- **Drop:** dropped, listed with what is lost. Each needs the user's OK under the 17 November rule.

"Uses" names only consumers that count under §2. D374 retired the physiology set, so rows that only it used
have no use left.

**Evidence levels.** A wrong "Canonical" is the silent-loss direction, so each row's basis is stated.
- **Measured by the dry run:** a live-subject test fails when legacy goes, for A9, A10, A12, E2, E4, G1 to G3, and group
  V's rows but for the files marked there.
- **Read here,** at the cited lines: A1, A4–A6, A9, A12 (each test's parse call), B2's refusal, B3–B5, C2, D9, E1–E3, P1, G1, G3, and
  the refusal sites of §4.
- **By registry name or protocol only:** A2, A7, A8, C1, D3, D4, D6 (the registry dump), and D7, D8 (the
  parity protocols' model IDs).
- **From a research read not repeated here:** A3, A10, A11, B1's standard state, B7, C3, C4, D1, D2, D5,
  E4.
- **Group I:** each record's file was mapped here through the move tables. I7's "Canonical" is by name only.

The builder re-reads every row not read here before the deletion, and confirms G1's replacement world. A row found
not canonical moves to Feature or Drop, and the user is told.

### A. The electrical tissue

| # | Capability (legacy home) | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| A1 | Passive resolved tissue: membranes, outside regions, faces, field solver, capacitive closure (`resolved_tissue@1`, live `models/surface_tissue.py`) | @3 is built on its spec (`definitions/surface_tissue_spec.py`). The ID itself: row A12 | Canonical | the code is live; legacy's dispatch of the ID moves to the live registry (row A12) |
| A2 | Gated Na, K and Cl channels registered on @3: Kv1.1–1.6, Kir2.1, Nav1.2, the three leaks | @3 | Canonical | the 11 `channel_law@1` laws |
| A3 | The catalogue's other Na/K/Cl gated laws (Kv2, Kv3, `k_fast`, Nav1.3, Nav1.6 persistent, the `navrat` set) | D211's port programme: "port as is" in `visualizer/data/laws/law_port.json` | Expressible | register one module per law on @3, as the Kv1 extraction did (`laws/channels/kv1_channels.py:7–11`). Their kernels are live in `laws/channels/`, and the deletion leaves them |
| A4 | Calcium-permeant channel laws: 14 CaV laws with `cav1p2_m2h@1`, cation leaks with a Ca share, HCN laws with a Ca share | the calcium ensemble (Cav1.2 in the gated and IP3 clusters); D211's port programme ("port as is" for all 22 CaV and HCN laws) | Feature | G-1 |
| A5 | Instantaneous voltage-gated laws (8 Morris–Lecar) | D211's port programme ("port as is" for the instantaneous Na, CaV and HCN laws) | Feature | G-2 |
| A6 | Calcium-activated K (`cagpotassium_numeric_mM_scale@1`) | D211's port programme ("port as is", U33) | Feature | G-3 |
| A7 | Junction gating | @3 | Canonical | `junction_voltage_relaxation@1`, `junction_series_gates@1` |
| A8 | Na/K pump on maintained reservoirs | @3 | Canonical | `nak_atp_mass_action_positive@1` |
| A9 | @3's reference world: the gated catalogue model `resolved_tissue@8` (live `models/surface_kinetic.py`, with the legacy wrapper `legacy/models/surface_catalog.py`) | `tests/unit/test_surface_pump_v3_gates_equivalence.py` and @3's tests through `validation/tissue/surface_pump_v3_fixtures.py:107–129` (U2); `test_surface_catalog_planning.py` runs on it (V5) | Canonical code, but its dispatch is legacy's | kept for now and moved to an independent validation reference at the end (Q5 (a), D374). Its dispatch moves to the live registry with row A12's |
| A10 | Cell clusters in finite and spatial baths (`finite_extracellular@1`–`@3`, `spatial_extracellular@1`–`@2`) | the JUPITER check (`spatial_extracellular@2`, U3); nested in the calcium ensemble (`spatial_extracellular@2`, `finite_extracellular@2`); `test_gpu_execution.py` and `test_batch_identity.py` run `finite_extracellular@2` (V5), and the JUPITER runbook runs the first (U3); the REF-era drivers are not uses | Expressible | the same physics as @3 worlds (constant-field leaks, Kv1.5, the pump, junctions, faces), not bitwise |
| A11 | The oldest families (`bioelectric_cell@1`, `bioelectric_pair@1`, `multispecies_membrane@1`, `voltage_gated_membrane@1`, `physical_ionic_graph@1`, `emt_mirna_pair@1`, `spatial_extracellular@3`) | vehicles only, which earlier versions gave as none: `bioelectric_cell@1`, `bioelectric_pair@1` and `emt_mirna_pair@1` (V1), `multispecies_membrane@1` (V4); helpers inside the A10 line | Drop | superseded by @3; group H's pointers corrected |
| A12 | Two live tissue models reached only through legacy's dispatch: `resolved_tissue@1` (`models/surface_tissue.py`, `definitions/surface_tissue_spec.py`) and `resolved_tissue@2` (`models/surface_kinetic.py`, `definitions/surface_kinetic_spec.py`) | **@1 (U2):** `test_surface_tissue.py` (parses and runs it) and `test_scalar_tail_reuse.py` (parses it). **@2 (U2):** `test_surface_kinetic.py` (parses it); `test_surface_pump.py:161`, the reference for `resolved_pump_tissue@1`, and `test_vector_windows.py:241`, the ionic simulation that `vmap` refuses, both through `surface_pump_fixtures.reduction`; and `test_rehost_probe.py` through `validation/assays/rehost_probe.py:304–307`, which skips without its saved observation. PROGRESS records that G0 probe (lines 4625–4635) and its plan step 8 cites it (U3). **Both (U1):** `ensemble/ionic.py` admits them as simulations (`:177, 196`). All six test files are tier 3, and all six fail with legacy gone | Canonical | the code is live. C-1 moves the dispatch to the live registry (Q5 (a), widened; §7.3) |

### B. Calcium

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| B1 | Cytosolic calcium with a plasma-membrane pump (`plasma_calcium_pump_positive@1`) | the calcium ensemble | Canonical | `cells.ca_atp_mass_action_positive@1` on @3: the same kernel at a 1 M standard state, Δg0 − RT ln 1000. Not bitwise |
| B2 | NCX, 3 Na : 1 Ca (`ncx_3na_1ca_symmetric_barrier@1`, a live module, unregistered) | the calcium ensemble (plasma, gated, IP3) | Expressible | one cycle law module on the transporter kind's population axis, in its monomial form (§14.3). **Corrected 25 November:** this row said the axis refuses a mode that moves charge. It refuses a mode that creates charge, summed over both ends (`kinds/transporter.py:1336–1339`), which NCX does not |
| B3 | ER store: a closed compartment with a capacitor, a GHK leak, a pump and calcium-gated release (`er_calcium@1` over `compartment_reactions@1`) | the calcium ensemble (all four calcium clusters) | Feature | G-4 |
| B4 | Calcium buffering by mass action, in the cytosol and in the ER | as B3 | Feature (with B3) | `local_species_reactions@1` holds a species that @3 routes only as a covered counter-ion (`operators/species_common.py:16–17`). Inside the ER it waits for G-4 |
| B5 | IP3-gated store release (`ip3_er_release@1`) | the calcium ensemble (IP3 cluster) | Feature | G-5 |
| B6 | Owned calcium in the 56-law tissue, closed or open exterior (`resolved_calcium@11`, `resolved_open_calcium@1`) | none since D374 retired the physiology stack | Drop | composes A4, B1–B5 and D1; the ensemble's re-expression rebuilds those parts |
| B7 | The spatial calcium tissue (`spatial_calcium@5`, `tissue_calcium`) | none; pointed at by `docs/PAPER_REVIEW_CCI_SEQ.md:30` | Drop | its physics is B1–B5 |

### C. Energy

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| C1 | Maintained ATP/ADP/Pi reservoirs | @3 | Canonical | `maintained_chemical_reservoirs@1` |
| C2 | Finite per-cell ATP/ADP/Pi pools, regeneration ports and finite-fuel pumps (`resolved_energy@1`–`@2`, `resolved_calcium_energy@1`–`@5`, `resolved_open_calcium_energy@1`) | none since D374; `docs/CORE_LAWS_ROADMAP.md:73–75` plans its rebuild | Drop now; Feature later | G-6, when a consumer asks |
| C3 | ATP-driven, irreversible, regulated and cotransport variants (`resolved_calcium_energy_atp_transport@1`, `_irreversible_transport@1`, `_regulated@1`–`@2` with `processes/network_control.py` and `network_reactions.py`, `_transport@1`, `resolved_cotransport@1`, `resolved_cotransport_water@1`) | one vehicle, which earlier versions gave as none: `resolved_cotransport_water@1` is the only model the live refinement clock admits (`execution/grid.py:236–239`; V3) | Canonical in part; Drop the legacy forms | `atp_driven_transporter_mass_action_positive@1`, the cotransport cycle laws, `species_regulated_availability@1`. Their finite-fuel forms wait for G-6 |
| C4 | Mitochondria (`resolved_calcium_energy_mitochondria@1`, `mitochondrial_passive`) | none; pointed at by `docs/PAPER_REVIEW_T_CELL_ORGANELLES.md:119–122` | Canonical in a fuller form; Drop the legacy form | the transporter kind's respiratory-chain, ATP-synthase, nucleotide-exchange and adenylate-kinase laws (`docs/MITOCHONDRIA_DESIGN.md`) |

### D. Exterior, volume, membranes, repair

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| D1 | Static ideal chemical and voltage reservoirs with electrode-work ledgers | none since D374 | Expressible | @3's line books `reservoir_supplied`, electrode charge and work (`models/surface_tissue.py:37–43`; `models/surface_pump.py`); the builder confirms every mover's ledger |
| D2 | Hard global ionic-moiety ceilings at every stage | the open families only | Drop | a check in `models/surface_pump_checks.py` if a consumer asks |
| D3 | Water and volume (`resolved_water@1`–`@3`, the `*_water` families) | none | Canonical | `ideal_osmosis_linear_compliance_water@1`; `resolved_pump_water@1`, `@2` |
| D4 | Injury and repair (`resolved_repair@1`–`@4`, `membrane_injury`) | none | Canonical | `cells.patch_damage@1` (FR-5) |
| D5 | Lateral membrane redistribution, mobile channels and pumps (`resolved_redistribution@1`–`@3`, `surface_mobile_*`) | none; an option in `docs/ABUNDANCE_TO_FUNCTION_DESIGN.md:50–53` | Drop (lost: electrophoretic lateral redistribution) | nearest canonical pieces are `membrane_entity_state@1`, trafficking and insertion |
| D6 | Scheduled bath composition, bath events and epochs | none | Canonical | `scheduled_bath_composition@1`, the wash schedule |
| D7 | Extracellular barriers | none | Canonical | the @2/@3 line; parity rung P2 passed on `resolved_pump_tissue@2` |
| D8 | Scheduled membrane profiles and interventions | none | Canonical | P3's scheduled interventions on @3 |
| D9 | Excision (cutting) (`resolved_*_excision`, `processes/tissue_removal.py`) | none of the used rows. `docs/EXPERIMENT_PATH_PATTERN_RECOVERY.md` (row 7) names an excision operator for the composite as new work | Drop the legacy form; Feature later | G-9 |

### E. Assembly and ensembles

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| E1 | Finite-pool stochastic assembly and the capsid graph (`finite_bond_assembly@1`, `capsid_graph@1`) | the ensemble runner (U1) | Canonical (live code) | `assembly_pool/`, `assembly/`; seeded in the model table by the rename (its Q4) |
| E2 | Assembly topology setting channel availability, in one cell and as per-cell pools over a tissue (`assembly_regulated_cell@1`, `assembly_regulated_cluster@1`) | the ensemble runner's kinds (U1); `docs/GPU_ENSEMBLES.md:125–200` (U3); `validation/assembly/qualify_cell.py`; `validation/ensemble/`; `test_jupiter_plan.py` and `test_assembly_cluster_gpu.py` (V5) | Feature | G-7 |
| E3 | GPU ensembles of these worlds (`cells ensemble run`, GPU-only, `ensemble/worker.py:95`) | `docs/GPU_ENSEMBLES.md`; the JUPITER runbook | Feature. Parked if a CPU re-expression counts (§13, Q1) | G-8, unless the ensemble ends on @3 |
| E4 | The ionic wrapper `ionic_worlds@1` (`ensemble/ionic.py`, which admits 98 legacy IDs). Its exercised children are `spatial_extracellular@2` (the JUPITER world) and `finite_extracellular@3` (`configs/junction_finite_cluster.json`, the integrated ensemble's world) | the JUPITER check; `tests/unit/test_integrated_ensemble.py` (6 of 7 fail with legacy gone), which the JUPITER runbook runs; `test_jupiter_plan.py` and `test_ionic_plan_admission.py` (V5); `validation/ensemble/integrated_matrix.py`, `spatial_matrix.py` | Expressible | the adapter exists: `ionic_worlds@1` already admits `resolved_pump_tissue@1`–`@3`, whose GPU path stands (`ensemble/ionic.py:213–215`; D336 refuses only the composite). What is left is the worlds, as row A10 |

### P. BETSE-facing preparation

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| P1 | Tissue-profile selectors and static profiles; mesh binding in BETSE's order; BETSE's grid and bath face conventions; INIT/SIM phase handoff; the `tissue-profiles`, `tissue-geometry`, `tissue-phase` and `excise` command lines | none: D374 retires the physiology set and its helpers. The fourth helper, `emulator/spatial_spec.py`, stays with the parity ladder (row G3) | Drop (and not allowed in `src` in any case, §5) | physics inside it, such as the Bernoulli-fitted face law and cutting, becomes a request if a kept consumer needs it |

### G. Small inline families

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| G1 | `source_decay@1`, the conftest's synthetic world | a vehicle of 20 live-subject test files (V1); earlier versions gave nine | Expressible | retarget to a live world (Q6 (a), D374). `reaction_transport@1`, named before, refuses a scheduled source, so a minimal composite with one, or a split of the worlds, is the builder's to find |
| G2 | `emt_mirna@1`, `passive_pair@1` | vehicles of the shared batch fixture's tests and of `test_cli.py` (V1), which earlier versions missed; their own tests; pointed at by `docs/PAPER_REVIEW_GZMK_AGEING.md:139` | Drop | the vehicles are replaced |
| G3 | The `identifier` check, imported from `legacy/core/multispecies_spec.py`, and the test helper `same`, imported from `test_spatial_calcium.py` | the BETSE-order emulator and 12 tests (§6), the parity ladder's tooling (U3); earlier versions gave ten | Canonical | two changes: `identifier` is the function at `definitions/spec_values.py:23–31`, so its import is retargeted; `same` moves to a helper module |

### V. Vehicles: live tests that run on a legacy world

These are uses of §2's vehicle kind, measured by the dry run unless marked. They are tests, not capabilities, so the
tally below does not count them.

| # | Live code under test | Tests | Legacy worlds | What C-1 does |
|---|---|---|---|---|
| V1 | Batches, windows, records, replay, phases, the command line, specs: the shared worlds of `tests/conftest.py` and `tests/batch_fixtures.py` (rows A11, G1, G2) | 20 files. **Break:** `test_batch_cli.py`, `test_batch_window_cli.py`, `test_window_cli.py`, `test_replay.py`, `test_blas_threads.py`, `test_cli_own_runner.py`, `test_continuity_gpu.py`, `test_continuity_loaders.py`, `test_continuity_tools.py`, `test_fine_windows.py`, `test_numerics.py`, `test_phase_records.py`; in tier 3 `test_cli.py`, `test_windows.py`, `test_scalar_tail_reuse.py`, `test_numerical_refinement.py`. **Pass, on the live half:** `test_specs.py`, `test_run_view.py`. **Tier 3, not run:** `test_batch.py`, `test_batch_windows.py` | `source_decay@1`; and five of the batch fixture's other six models: `emt_mirna@1`, `passive_pair@1`, `bioelectric_cell@1`, `bioelectric_pair@1`, `emt_mirna_pair@1` | New live worlds. Ten of the 20 and the batch fixture drive `source_decay@1`'s scheduled external source, which `reaction_transport@1` refuses (`definitions/specs.py:1129`), so the builder needs a live world with a scheduled input |
| V2 | The ensemble planner (`ensemble/plan.py`) | Seven in tiers 1+2: `test_calcium_activated_catalog_planning.py`, `test_channel_catalog_v2_planning.py`, `test_hcn_extra_catalog_planning.py`, `test_morris_lecar_catalog_planning.py`, `test_morris_lecar_water_repair_planning.py`, `test_surface_calcium_catalog_planning.py`, `test_surface_calcium_energy_planning.py`. Two in tier 3 are of the same kind and were not run: `test_surface_calcium_energy_{mitochondria,transport}_planning.py` | `resolved_tissue@9`–`@12`, `resolved_calcium@7`–`@11`, `resolved_calcium_energy@1`–`@5`, `resolved_water@3`, `resolved_repair@4` | Ionic arms on `resolved_pump_tissue@3`, which `ionic_worlds@1` already admits (`ensemble/ionic.py:215`); assembly arms on a kept calcium cluster. Four of the seven are one file with another fixture module, so one file may carry the assertions and the copies go by the removal list |
| V3 | The refinement clock: `execution.refinement_times` (`execution/grid.py`) | `test_recovery_response_grid.py` (2 of 23 tests), `test_numerical_refinement.py` (tier 3, 20 of 21; the other skips) | `resolved_cotransport_water@1` | It is the clock's only admitted model, and only legacy parses the key (§7.3). Admit a live model, or retire the clock with both tests: for the lead (§13) |
| V4 | The projective mode's refusals (`definitions/projective_spec.py:154–155`) | `test_projective.py` (2 of 25 tests) | `multispecies_membrane@1` (`configs/multispecies_baseline.json`) | Another live model that the mode refuses |
| V5 | The GPU and CPU run path, batch identity, the planners, the ensemble queue | `test_gpu_execution.py`, `test_batch_identity.py`, `test_jupiter_plan.py`, `test_ionic_plan_admission.py`, `test_surface_catalog_planning.py`, `test_assembly_cluster_gpu.py`; tier 3 `test_integrated_ensemble.py` | Kept worlds: `finite_extracellular@2`, `@3`, `assembly_regulated_cell@1`, `assembly_regulated_cluster@1`, `resolved_tissue@8` | Nothing. They are retargeted with their world, at C-2 |

The dry run counts the planning tests as eight. The eighth, `test_surface_catalog_planning.py`, runs on
`resolved_tissue@8`, which C-1 keeps, so it is in V5. V2's worlds belong to rows A3 to A6, B6, C2, D3 and D4, whose uses
are otherwise unchanged.

### H. Documents that point at legacy capabilities: claims to correct

These are not uses. Each pointer is corrected in the deletion's commit, to its row's canonical piece or to
"dropped":
- `docs/PAPER_REVIEW_CCI_SEQ.md:28, 30, 40`: `tissue.py`, `tissue_calcium.py`, the assembly cluster;
- `docs/PAPER_REVIEW_MITOCHONDRIA.md:33`: `surface_calcium.py`;
- `docs/PAPER_REVIEW_T_CELL_ORGANELLES.md:119–122`: the mitochondria family;
- `docs/PAPER_REVIEW_GZMK_AGEING.md:134–139`: `finite_extracellular`, `network_reactions@1`,
  `finite_ecm_polygon_geometry` and `emt_mirna`;
- `docs/ABUNDANCE_TO_FUNCTION_DESIGN.md:50–53` and `docs/CORE_LAWS_ROADMAP.md:73–75`;
- `docs/ARCHITECTURE.md:11–14`, whose opening lists "finite and spatial extracellular inventories",
  "compartment chemistry", "calcium/IP3" and "stochastic assembly with experimental cell coupling" as
  implemented building blocks;
- `docs/BIOELECTRIC_CELL.md:30–31`, `docs/FINITE_ENERGY_POOLS.md:3`, `docs/TISSUE_PHASES.md:301`,
  `docs/TISSUE_RETURN_CURRENT.md` (lines 1327–1391 and 2616–2666 among others) and `docs/TISSUE_GEOMETRY.md:26`;
- `docs/library/DECLARATIONS_FORMAT.md:349`, the manifest's legacy list;
- `docs/WINDOWED_EXECUTION.md:79` and `docs/EXCITABLE_TISSUE_DESIGN.md:473`, on the refinement clock, by what V3 settles.

Design notes that only record past work (`SOURCE_LAYOUT_MOVES_DESIGN.md`, `LAW_DOCUMENTATION_DESIGN.md`) stay
as records.

`network_reactions@1`'s cell, mitochondrial, environment and growth reactions are canonical in part, as
`local_species_reactions@1` and the secreted species. The legacy form is dropped.

### I. The protein inventory's law records that still point into legacy

**The source.** The engine's law inventory is
`/mnt/workspaces/Cells/protein-catalogue-20261111-01/law_inventory_v2.json`
(`cells.protein_catalogue.law_inventory@2`, read at `fec863f`, 12 November; `docs/PROTEIN_CATALOGUE_PLAN.md:60`):
81 law records over 49 units. The viewer's slim copy, `visualizer/data/proteins/inventory.snapshot.json`,
holds the same 81. D211's law-port inventory is `/mnt/workspaces/Cells/law-port-20261117/inventory.json`,
with 54 rows, and the viewer's table `visualizer/data/laws/law_port.json` is made from it. I mapped each record's file through D188's move tables (`scripts/moves/move1-table.json`,
`move2-table.json`) to today's tree.

**The count, corrected on 25 November** (the second reader; recomputed at `9c30104e` with the deletion's own edits). 13 units lose a record:
U34 (`neutral_mobile_leak@1`), U36 (`symmetric_opposing_relaxation@1`), U37 and U38 (the pair's junction flux), U39 (`nak_atp_affinity_tanh@1` and the pair's pump
term), U40 (`plasma_calcium_pump_positive@1`, `finite_atp_pmca_positive@1`), U41 (`er_calcium_pump_positive@1`, `finite_atp_er_1ca_positive@1`), U42
(`ncx_3na_1ca_symmetric_barrier@1`), U43 (`er_calcium_release@1`, `ip3_er_release@1`), U44 (`kcc_reversible_tanh@1`), U45 (`nkcc_reversible_tanh@1`), U46
(`cell_zone_transporter@1`) and U47 (`mitochondrial_passive_continuous_si@1`). This section had said that 11 records point into legacy and that U36's are all live;
the kernels of two that leave, `gate_target` and `reversible_pump`, are dead names.

**The D211 mark** is from the law-port table, `visualizer/data/laws/law_port.json`. The mapping was read here;
it is in `inventory_records_now.json`.

| # | Record (unit) | Legacy file | D211 mark | Uses | Class | Canonical piece, and what the unit keeps |
|---|---|---|---|---|---|---|
| I1 | `neutral_mobile_leak@1` (U34, always-open leaks) | `legacy/core/surface_redistribution_spec.py` | — | none (row D5) | Drop | U34 keeps its six live leak laws |
| I2 | The source pair's junction flux (U37, Cx45/Cx45; U38, Cx40/Cx37) | `legacy/processes/source_electrochemistry.py` | not a port | none. It carries BITSEY's reference conventions, admitted by D149 only through `emt_mirna_pair@1` (`source_electrochemistry.py:1–9`) | Drop | U37 and U38 are left with no law record; the viewer's inventory is updated |
| I3 | The source pair's pump term (U39, Na/K-ATPase) | the same file | — | none | Drop | U39 keeps `nak_atp_mass_action_positive@1`; `nak_atp_affinity_tanh@1` is an ID of legacy's only, and leaves too (corrected 25 November) |
| I4 | `finite_atp_pmca_positive@1` (U40, PMCA) | `legacy/processes/finite_calcium_pumps.py` | — | none (row C2) | Drop, lost until G-6 | U40 keeps `ca_atp_mass_action_positive@1`; `plasma_calcium_pump_positive@1` leaves with the deletion's edits. The canonical pump is `atp_driven_transporter_mass_action_positive@2` |
| I5 | `finite_atp_er_1ca_positive@1` (U41, SERCA family) | the same file | fold into an owner's planned law | none (row C2) | Drop, lost until G-6. D211 folds it into the cardiac lane | U41 keeps no record: `er_calcium_pump_positive@1` leaves with the deletion's edits. The canonical pump is `atp_driven_transporter_mass_action_positive@2` |
| I6 | `ip3_er_release@1` (U43, IP3R-like release) | `legacy/processes/ip3_release.py` | fold into an owner's planned law | the calcium ensemble's IP3 cluster (row B5) | Feature | G-5, coordinated with the cardiac lane's release law (D211) |
| I7 | `kcc_reversible_tanh@1` (U44, KCC) | `legacy/processes/cotransport.py` | — | none | Canonical; Drop the legacy form | `k_anion_symport_mass_action@1` (`laws/routes/k_anion_symport.py`) |
| I8 | `nkcc_reversible_tanh@1` (U45, NKCC) | the same file | port as is | D211's port programme | Expressible | a cycle law on the transporter kind's population axis, which admits any mode that creates no charge (`kinds/transporter.py:1336–1339`; corrected 25 November, see B2). U45 has no other record |
| I9 | `electroneutral_symport_reversible_tanh@1` (U46, a configured transporter) | the same file | port as is | D211's port programme | Expressible | as I8. The law is manufactured, with no outside source (`cotransport.py:1`) |
| I10 | `cell_zone_transporter@1` (U46) | `legacy/processes/cell_zone_transport.py` | port as is | D211's port programme | Feature, or Drop. Not portable "as is": its equations are "those of the BETSE v1.5.0 transporter network", with that network's conventions (`cell_zone_transport.py:1–10`) | a neutral re-expression, the user's call beside D211 |
| I11 | `mitochondrial_passive_continuous_si@1` (U47, inner-membrane permeability) | `legacy/processes/mitochondrial_passive.py` | not a port | none (row C4) | Drop | U47 is left with no law record. The nearest canonical pieces are the transporter kind's mitochondrial laws and the proton-leak routes |

**Tally, 51 rows, after D374, the widening of Q5 (a) and the dry run, which changed uses and no class:**
- **Canonical: 18** (A1, A2, A7, A8, A9, A12, B1, C1, C3, C4, D3, D4, D6, D7, D8, E1, G3, I7). For C3, C4 and I7,
  the legacy forms are dropped.
- **Expressible: 8** (A3, A10, B2, D1, E4, G1, I8, I9). D1 has no use since D374.
- **Feature: 11:**
  - six for the calcium ensemble's CPU re-expression: A4 (G-1), B3 and B4 (G-4), B5 and I6 (G-5), E2 (G-7);
  - one for its GPU runs: E3 (G-8);
  - two for D211's port programme: A5 (G-2) and A6 (G-3). A4 is D211's too;
  - two only if wanted: D9 (G-9) and I10.
- **Drop: 14** (A11, B6, B7, C2, D2, D5, P1, G2, I1, I2, I3, I4, I5, I11). C2, I4 and I5 are lost until
  G-6 is requested.

## 4. Confirmed gaps, at their refusal sites: candidate requests for the user

Each was confirmed by reading the code at main. None is logged as an FR; each is the user's to request.

| Gap | What is refused, and where | Needed by |
|---|---|---|
| **G-1: calcium-permeant channels on @3** | @3's channel valence table is `{"Na": 1, "K": 1, "Cl": -1}` (`definitions/surface_pump_v3_spec.py:169`). Each permeant ion is checked against it, "Channel ion requires its law's species and valence" (`:327–329`). @3 does carry a plasma calcium pump | A4: the calcium ensemble's Cav1.2 |
| **G-2: instantaneous voltage-gated laws** | "a gate-free law gives no kinetics or opening" (`registry/laws.py:422–423`), so a gate-free law is always open | A5: D211's port programme |
| **G-3: channels whose kinetics read a species** | `ChannelLaw.kinetics` takes voltage only, and `reads` is empty for every law (`registry/laws.py:372, 375`) | A6: D211's port programme |
| **G-4: an ER store** | `cell_owned_compartments@1` refuses three things: a Na/K or Ca pump or a channel population on the bounding patch (`operators/compartments.py:359–366`); a constant-field permeability there without declared kinds, and any kind under RK4 (`:368–376`); and an owner whose capacitor component holds no held bath (`:514–519`) | B3, B4: the calcium ensemble |
| **G-5: IP3-gated release** | `species_regulated_availability@1` targets only `("junction", "channel")` (`operators/species_regulated_availability.py:154, 548–551`). It refuses a charged source (`:743–745`), and legacy's IP3 is charged −3 | B5, I6: the calcium ensemble's IP3 cluster |
| **G-6: finite fuel** | @3's Na/K pump requires maintained reservoirs (`definitions/kinetic_pump_spec.py:43–44`), and its two pumps run on the maintained fuel kind (`models/inner_laws.py:9, 60`). The transporter kind refuses `finite_fuel_rows@1` in its version-1 layout (`kinds/transporter.py:251–254, 494–495` at `c9da0fdb`), and its population axis admits it only for the neutral ATP-driven law (`:1164–1182`) | C2, I4, I5: no use since D374; the roadmap's energy rebuild |
| **G-7: assembly coupled to availability** | No operator couples an assembly pool's topology to availability. The registry refuses any other (`registry/operators.py:176–181`); the assembly families exist only as ensemble kinds (`ensemble/families.py:20–26`); the nearest door reads species amounts, not topology (`species_regulated_availability.py:47–49`) | E2: the calcium ensemble |
| **G-8: the composite on a GPU** | `refuse_unqualified_gpu` refuses a GPU backend for `resolved_pump_composite@1` in the vector windows (`execution/vector_windows.py:213–230`, called at `:255`). Device row checks refuse any GPU backend (`execution/row_checks.py:71–74`). FR-17's qualification closed as failed (D336) | E3: the calcium ensemble's GPU runs, if it is re-expressed on the composite |
| **G-9: excision on the composite** | No excision operator exists; `EXPERIMENT_PATH_PATTERN_RECOVERY.md` (row 7) names one as new | D9: no used row today |

**What the calcium ensemble needs:**
- **for a CPU re-expression:** G-1, G-4, G-5 and G-7, plus B2's registration;
- **for its GPU runs, besides:** G-8, unless the store and the coupling are designed onto @3.

**These are candidate requests for the user.** Each is sized by its own design note before it is requested.
Until then the prices are rough guesses:

| Gap | Rough guess, agent-days | Overlap with a planned lane |
|---|---|---|
| G-1 | 2–4 | The cardiac lane plans Ca²⁺ as a channel ion (`docs/HUMAN_CARDIAC_LAWS_DESIGN.md:105`), and an L-type current, `l_type_calcium_cdi@1` (`:171`) |
| G-4 | 5–8 | The cardiac lane plans calcium pools at the cell's potential, with a buffer read and SR uptake and release (its H2, `:783, 862`). That is G-4's branch (ii), with no store voltage, and it is hosted on @3 |
| G-5 | 2–3 | The cardiac lane's release law is graded on the L-type current (`:181`), not IP3. D211 folds `ip3_er_release@1` into an owner's planned law |
| G-7 | 4–6 | none |
| B2 (NCX registration) | 0.5–1 | The cardiac lane plans its own exchanger, `sodium_calcium_exchange_cycle@1`, a four-state cycle after Kang and Hilgemann (`:179`) |
| **For a CPU re-expression, in all** | **13.5–22** | |

**G-8 stands apart, with no price.** The earlier guess of 3 to 6 agent-days was for an attempt, not for a pass.
- **The last attempt failed** (D336). In the first window the device read the total ledger at 0.715 and the host
  at 0.202. The spread, 0.514, is above the amended bound of 0.291 and the cap of 0.4. D335 bars amending the
  criterion after the data.
- **The gain was modest:** with the flag, device mode took 21.8 ms per step, about 1.5 times faster than the
  CPU's 32.0. D326 and D330 had assumed about three times.
- **A new attempt** would follow FR-53's compensated sum, which is normal priority and not built. It is also a
  fresh registration and the user's decision. FR-53's note expects the sum to remove the spread "by construction";
  that is a prediction for a new qualification, not a result.
- **It may not be needed.** If the G-4 and G-7 notes host the store and the coupling on `resolved_pump_tissue@3`
  (the cardiac lane's recommended calcium design is pools on @3), D338's refusal of the composite is not the one
  that applies. @3's own GPU evidence has a re-check logged and not started (D338).

**D211 folds calcium handling and NCX into the cardiac lane's planned laws.** So the ensemble's re-expression
either reuses that lane's laws or registers its own beside them. The G-1 and G-4 notes settle which:
- **reusing them** is a changed model, judged by the ensemble's registered criteria (§8);
- **its own laws in the same seams** keep the same equations, and are judged by a derived band.

## 5. The BETSE rule, family by family

**The rule bars BETSE conventions in `src/cells`.** Laws that BETSE also uses are fine under neutral names,
with the source cited. The rule therefore decides where a relocation may go, and what a re-expression must
neutralise.

| Family | What its code carries | Relocation into `src/cells` |
|---|---|---|
| `resolved_tissue@12` | The two legacy wrappers carry no BETSE convention. The live catalogue does: law-to-BETSE-class maps (`laws/channels/cav_channels.py:13` and others), "native" shifts (`laws/channels/calcium_gates.py:3`, `hcn_channels.py:25`), "pinned" wording | **Allowed.** The catalogue's conventions are existing live code: re-expression neutralises them as the laws are registered, and the rename judges them |
| `resolved_calcium@11` | Claim strings naming BETSE (`legacy/models/surface_calcium.py:937–938`, `er_calcium.py:482–483`). It depends on live laws carrying BETSE's numeric-mM ATP quotient (`laws/reactions/er_calcium.py:1–5`, `plasma_calcium.py:1–5`, `maintained_mM_quotient@1`) | **Allowed after a neutralising commit** for strings and identifiers. The quotient convention is pre-existing live code; re-expression replaces it with a standard-state form, as `ca_atp_mass_action_positive@1` did |
| `resolved_calcium_energy@5` | As `resolved_calcium@11`, plus "native" parameter paths in the finite pumps (`legacy/processes/finite_calcium_pumps.py:80–94, 256`) | **Allowed after neutralising** |
| `resolved_open_calcium@1`, `_energy@1` | The runtime itself is neutral. Its closure pulls in a chain that carries BETSE's conventions: `core/tissue_profile_preparation.py:41–43` records `native_revision` 5269a714, `native_flux` "betse/science/sim_toolbox.py:electroflux and update_Co" and `native_geometry`; `processes/tissue_target_selectors.py:3` ("Selector conventions follow BETSE v1.5.0"); `processes/geometry_operator_binding.py:3, 100` (BETSE's mesh construction, "Preserve native coordinate-wise summation/reciprocal order"); `core/owned_calcium_profile_binding.py:1, 17` ("Native coefficient declarations", `as native`) | **Not allowed for that chain.** The open families use only `background_loss_bound` from it (`legacy/models/open_calcium_admission.py:13, 89`). A relocation must move that one helper neutrally and cut the import. The chain stays out of `src/cells` |
| The physiology set's helpers | `tissue_profiles.py` (INIT/SIM profile recipes), the selectors and mesh binding above, `processes/extracellular_face_transport.py:4–6` ("Grid and bath conventions follow BETSE v1.5.0"), `processes/tissue_removal.py` (reference-code cut behaviour) | **Not allowed,** and moot: D374 retires the set, and its helpers go in the deletion batch |
| `spatial_calcium@1`–`@4`, `assembly_regulated_*` | Laws BETSE also uses (`pumpCaATP`, `Cav1p2`, the IP3 Hill factor), cited; claim strings (`plasma_calcium.py:402` "native PMCA function correspondence", `ip3_calcium.py:154`) | **Allowed after neutralising** strings |

## 6. The BETSE drivers: is their evidence claimed?

**The scan.** I read PROGRESS, README, `docs/CURRENT_PLAN.md`, `SCIENTIFIC_BASIS.md`, `ROADMAP.md`,
`EXPERIMENTS.md`, the experiment designs, the paper notes and the paper reviews.

**The 18 REF-003 to REF-005 drivers, and the junction and spatial-cluster panels,** which run
`finite_extracellular@1`–`@3` and `spatial_extracellular@1`–`@2`:
- They are cited only in their own records: about 40 `docs/BETSE_*` design, preflight and closeout notes
  from September and October (the older decision series), `docs/BETSE_REFERENCE_PLAN.md`, `validation/betse/README.md`
  and `reports/`.
- `docs/BETSE_CAPABILITY_ROADMAP.md:47` cites REF-003a. That is the passive-contact comparison on a live
  law, not one of these drivers.
- PROGRESS names only the seven-cell REF-003c configuration, as one of BETSE's reference cases (line 4801).
- No current plan, the scientific basis or a paper note rests on them.
- **Their evidence is not claimed.** D374 retires them in the deletion batch, with their records kept.

**The 17 physiology drivers and their 58 tests:**
- Their results are claimed nowhere. PROGRESS records only that the stack moved to `validation/betse`
  (Stage B, line 126 and lines 4497–4505).
- `docs/CURRENT_PLAN.md:253–254` notes a dangling reference in it, as maintenance.
- **D374 retires them** in the deletion batch, with their records kept.

**What BETSE parity rests on today.** The parity PROGRESS claims ("Plan: BETSE parity on CPU and L4", steps 3,
3b and 5) uses `validation/betse/protocols/physical_*`, on `resolved_pump_tissue@1`, `@2` and `@3`. Parity
"against saved outputs, out of process" stays possible after the deletion, because the BETSE outputs are
saved under `/mnt/workspaces/Cells`.

**The code around it, traced through the import graph:**
- **The world adapters** (`default_world_adapter.py`, `event_world_adapter.py`, `network_world_adapter.py`)
  reach no legacy module.
- **The BETSE-order emulator reaches legacy once.** `validation/betse/emulator/spatial_spec.py:23` imports
  `identifier` from `cells.legacy.core.multispecies_spec`, which re-exports the live
  `cells.definitions.spec_values.identifier` unchanged (`legacy/core/multispecies_spec.py:9`).
  - Through it reach `emulator/junction_model.py`, `junction_spec.py` and `spatial_model.py`.
  - **Twelve test files of tiers 1+2 fail with legacy gone** (the dry run; earlier versions said ten). Four stop at
    `identifier`: `test_channel_compensation_design.py`, `test_cue_separation_diagnostic.py`,
    `test_local_channel_design.py` and `test_unstimulated_diagnostic.py`.
  - Eight stop before it, at the comparison helper `same` of `test_spatial_calcium.py`, which
    `test_betse_spatial_trajectory.py` imports: that file, `test_betse_charge_precision.py`,
    `test_betse_gate_roundoff.py`, `test_betse_junction_runtime.py`, `test_betse_spatial_active_refinement.py`,
    `test_betse_spatial_junction.py`, `test_betse_spatial_junction_refinement.py` and `test_betse_spatial_runtime.py`.
    At C-1 `test_spatial_calcium.py` stays, so this one bites at C-3 at the latest.
  - Two more, in tier 3, reach the emulator and were not run: `test_betse_spatial_active.py` and
    `test_betse_spatial_refinement.py`.
  - **This is row G3: two changes.** Retargeting `identifier` and moving `same` restored all twelve in a throwaway copy
    (`work/run_helper.out` in the dry run's records): the same passes, failures and skips as the record.
- **The four helpers:**
  - `native_environment_paths.py` is imported only by `tests/unit/test_betse_environment_transport.py`;
  - `native_profile_conventions.py` by the physiology set and `tests/unit/test_betse_tissue_profiles.py`;
  - `native_geometry_operators.py` by nothing;
  - `emulator/spatial_spec.py`, as above.
- **`alignment.py`, `trajectory.py`, `contact.py` and `cluster_alignment.py`** are imported only by
  REF-era modules: the dispatch, expanded, full-loop, held-response, phase, profile and cluster panels.
  No claimed path imports them.

So the claimed ladder rests on no legacy capability except the re-exported `identifier`, which D374 makes a
direct import. The two BETSE tests on the helpers retire with them.

**Bearing on the rename's Q3 (§11):**
- The rename's rewrite list holds 30 `validation/betse` files; about a dozen are in REF-era panel folders.
- Of the 102–106 legacy definitions that spell the shared pieces, 99 are `configs/`, 6 `examples/` and 1
  `validation/betse/junction_coupled/` (`legacy_defs_with_shared.json`).
- D374 rules that nothing retires before the rename's move, so those files are re-spelled with the rest.

## 7. Three routes, priced, with the ensemble kept and the physiology retired

**The record.** The user decided the route on 25 November (status above): one branch, the deletion before the features and the re-expression, and one test at the end. This section
stays as the record of what was priced and why.

### 7.1 First, the user's choice that sets every date (§13, Q1)

**Does a CPU re-expression of the ensemble count as leaving legacy, or does legacy's core wait for the GPU?**

**Answer (a): a CPU re-expression counts.** The ensemble is re-expressed on the CPU, on G-1, G-4, G-5 and G-7.
Legacy's core is deleted when that re-expression passes its registered qualification. The GPU path is parked.
- **What is parked:**
  - `cells ensemble run` for `assembly_cell_ensemble@1` and `assembly_cluster_ensemble@1`. The runner is
    GPU-only (`ensemble/worker.py:95`, `ensemble/cli.py:509–517`), so those kinds would be refused by name, and CPU
    runs would use the ordinary run path;
  - the L4 claims for these families in `docs/GPU_ENSEMBLES.md`, kept as records that the tag reproduces;
  - `test_assembly_cluster_gpu.py` and the assembly half of `test_integrated_ensemble_gpu.py`.
- **What is lost meanwhile:** a capability that works today. The legacy ionic families have GPU evidence (D338),
  so (a) trades a working GPU path for legacy's deletion.
- **What is not parked, conditionally:** the JUPITER readiness check. It would run `spatial_extracellular@2`
  re-expressed on @3 (rows A10, E4). That rests on E4, which this plan has not read here, and on D338 keeping @3's
  batched GPU runs, whose re-check is logged and not started.

**Answer (b): legacy's core waits for the GPU.** The core is deleted only when the re-expressed ensemble passes
on a GPU.
- G-8 closed as failed (D336). FR-53's Q5 waits for FR-53's build (D371). A new attempt is a fresh registration
  and the user's decision.
- **So the date is open-ended.** Nothing schedules it.

**Lifetimes are counted in agent-days of work that must finish first, not in dates.** The four features are
candidate requests: none is requested, sized by a note, scheduled or staffed. Earlier versions said "weeks" for
every route. Nothing supports that, so it is withdrawn.

| Lifetime | A: relocate, then re-express | B: re-express directly | C: prune in place, then re-express |
|---|---|---|---|
| **(a)** legacy | until A-3: 11–16.5 agent-days | whole, until the deletion: 28–44 | at least 58% of its lines leave after 6–9 (C-0, C-1); the core lives for 23.5–38 more |
| **(a)** a copy in live `src` | for a further 22.5–36 (A-4, A-5 and the four features) | none | none |
| **(b)** legacy | until A-3 | **whole, open-ended** | **the core, open-ended**; the rest leaves at C-1 |
| **(b)** a copy in live `src` | **open-ended** | none | none |

### 7.2 What an open-ended date does to each route

- **To A:** the relocated copy becomes the end state in practice. D369 rules a relocated island out as one.
  - It sits in live `src/cells` under new IDs, with 112 modules and 29,223 lines (§7.5), and collects
    dependents.
  - Its BETSE-derived conventions (§5) stay in live code with it.
  - "Legacy is deleted" would be true on paper while its code lives on.
- **To B:** nothing is deleted.
  - Every test of legacy itself stays in every gate. In tiers 1+2 that is 109 files, measured: the 105 of §2.1 and four
    physiology tests that pass without legacy. They take 2,454 of the 13,677 test-seconds (18%), about 7.6 minutes
    of a gate's wall, plus dispatch misses that load the hub. References that never import legacy are not counted.
  - The physiology stack's tests and BETSE glue stay too, since B keeps D348's single deletion.
  - Live changes keep breaking tests that no lane owns.
- **To C:** the core stays in the holding area, with its own tests and a pruned hub. In tiers 1+2 that is ten files and
  56 test-seconds, about 10 s of wall, and in tier 3 seven files (`test_surface_catalog.py` is live once @8's wrapper is
  folded). The live test files on kept worlds (V5) stay under any route. It is the only route whose standing cost
  stays small if no date ever comes, and nothing BETSE-derived enters live `src`.

### 7.3 Common to every route

- **The deletion batch** (D374), with its dry run (§2.1), a tag and a removal list the user approves:
  - the physiology stack and the 18 REF-era drivers with their tests, records kept;
  - Q5 (a), widened by the lead: the dispatch of `resolved_tissue@1`, `@2` and `@8` moves into the live registry,
    and @3's checks keep @8 for now.
    - **What moves:** parse (`legacy/registration.py:1196–1211` and `:1444–1447`), `model_for` (`:794–795`,
      `:806–807`, `:832–833`) and `to_dict` (`:1946–1949`, `:1977–1980`). The hub has no `control_values` entry for
      them. The model table would gain their rows, for the builder to confirm, and
      `ensemble/ionic.py`'s admitted rows for the three stay (`:177, 196, 202`). It is small, an estimated half agent-day inside C-1's range.
    - **The entries match by exact type** (`type(spec) is X`), never `isinstance`: the lead confirmed it.
      `SurfaceKineticModel` derives from `SurfaceTissueModel` (`definitions/surface_kinetic_spec.py:114`), and legacy
      classes that stay in C's core derive from one or the other: `SurfaceCalciumModel`
      (`legacy/core/surface_calcium_spec.py:41`), `SurfaceWaterModel` (`legacy/core/surface_water_spec.py:40`) and
      `SurfaceRedistributionModel` (`legacy/core/surface_redistribution_spec.py:40`). An `isinstance` check before
      the legacy miss would catch them. The general ruling on dispatch still waits (§13);
  - Q6 (a): the three inline families go, with the live half of each (its spec class, parser and dictionary in
    `definitions/specs.py`), and the **20 files of V1** point at live worlds. Earlier versions said nine files.
    - The nine left out nine that break: `test_batch_cli.py`, `test_batch_window_cli.py`, `test_window_cli.py`,
      `test_blas_threads.py`, `test_cli_own_runner.py`, `test_continuity_tools.py`, `test_fine_windows.py`,
      `test_phase_records.py` and, in tier 3, `test_scalar_tail_reuse.py`.
    - They also left out `test_run_view.py`, which passes on the live half, and two tier-3 files that were not run,
      `test_batch.py` and `test_batch_windows.py`.
    - They wrongly held `test_stationary_analysis.py`, which has its own fixture;
  - the other vehicles that go (V2, V3, V4);
  - **two refusals move into live code, with a test** (the lead, 25 November). Legacy's `to_dict` holds the only two
    `raise` statements of the hub, and they protect live models:
    - `legacy/registration.py:2046`, "Multispecies execution settings require their own model identity";
    - `legacy/registration.py:2056`, "Experiment type does not match the declared model".
    - Without them, a surviving model with a wrong experiment type reaches `definitions/specs.py:860–865` and raises an
      `AttributeError` instead of a `ConfigError`. No test covers either.
    - They go into `SimulationSpec._fine_dict`, after the legacy call (`:857–859`), with a row each in
      `tests/unit/test_reaction_transport.py`'s `test_python_api_cannot_drop_or_substitute_controls` (`:129`; D224: rows
      in an existing test). Its present rows match no message, so a parse miss would pass them: the new ones call
      `to_dict` and match it. The first refusal can go with its execution class, at C-3;
  - **an unknown ID is refused by its name** (this plan's addition). After legacy's miss, `parse_spec` checks the
    inline families' fields before it checks the ID (`definitions/specs.py:1052–1060`), so a deleted or unknown ID is
    refused with "model: missing=[…], unknown=[…]". The message behind it lists deleted IDs as available. The ID
    check moves first;
  - **the refinement clock's only model is legacy's** (V3). `execution/grid.py:236–239` refuses any model but
    `resolved_cotransport_water@1`, and only `legacy/core/surface_cotransport_water_spec.py` parses the key. So with
    that model gone, no definition can declare it. Either a live model is admitted, with its own qualification, or the
    clock is retired: its parts of `execution/grid.py`, `execution/batch.py:219, 278`, `execution/vector_windows.py:195`,
    `ensemble/ionic.py:90` and `definitions/specs.py:802–805`, with both tests. Retiring it removes a documented feature
    (`docs/WINDOWED_EXECUTION.md:79`), so it goes on the removal list the user approves (§13);
  - the command line drops `tissue-phase`, `tissue-geometry`, `tissue-profiles` and `excise` (row P1): `__main__.py`
    (`:22–28, 42–43, 50–52, 62–66, 219–220, 236–237`) calls what the hub returns for them, and a pruned hub would return
    None;
  - the parity ladder's two changes (row G3): `identifier` imported directly, and `same` moved out of
    `test_spatial_calcium.py`;
  - `test_continuity_bypass.py`'s list, which names retired drivers;
  - group H's document pointers corrected.
- **The ensemble's CPU re-expression,** on the four features: about 8–12 agent-days, judged against §8's
  science captures by each registration's derived tolerance.
- **The four features and NCX's registration:** 13.5–22 agent-days, rough, priced in §4 and not repeated below.
- **G-8** is apart, unpriced, and only under answer (b) or for the parked path.
- **The science captures,** from the pre-rename snapshot: about 0.3 agent-days and about 1.5 lane-hours.
- **The rename lands first,** with legacy re-spelled (D371), and no retirement comes before its move (D374).

**What the dry run adds to the price:** about 2 to 3 agent-days on every route, a rough estimate.
- V1 is 20 files rather than nine: 1 to 1.5 more.
- V2 to V4 are new: 0.5 to 1.
- The two refusals, the ID check, the guard list and the script list (§10): 0.25 to 0.5.

### 7.4 Routes A and B

**Route A: relocate the used cores as a temporary bitwise copy, then re-express.**

| Step | Content | Agent-days | Gates and lanes |
|---|---|---|---|
| A-0 | Captures: bitwise windows for the cores, and the science set | 0.5 | about 2 lane-hours |
| A-1 | The batch's live-side items (§7.3): the `resolved_tissue@1`, `@2` and `@8` dispatch, with @8's wrapper `legacy/models/surface_catalog.py` folded into live code; the vehicles (V1–V4); the two refusals and the ID check; the parity ladder; the JUPITER and integrated-ensemble worlds onto @3 (rows A10, E4) | 4.5–7 | one full gate |
| A-2 | Relocate the used cores under neutral names, with `scripts/source_moves.py`: one map, its rewriter and verifier, 112 modules (§7.5). A neutralising commit follows (§5). The dispatch stays in the hub until A-3 (§12, risk 1). Proven bitwise | 4–6 | one full gate and the compare, about 2 lane-hours |
| A-3 | The deletion batch: the approved removal list, legacy deleted whole | 2–3 | the dry run again at this base, about 35 minutes; one full gate; tier 3 once (1–2 h); re-measure (about 1 h) |
| A-4 | Re-express the relocated cores as the features land | 8–12 | 2–3 gates; judged runs 2–4 lane-hours |
| A-5 | Retire the relocated copy | 1–2 | one gate |
| **Total** | | **20–30, plus the features** | **5–7 full gates, about 15–20 lane-hours** |

- **Meanwhile in every gate:** the copy's own tests as live tests, nine files in tiers 1+2 (52 test-seconds) and seven
  in tier 3. Five of the nine already fail or error in the record (§7.5).
- **The BETSE-rule risk is moderate to high.** The copy's code depends on BETSE-derived conventions in live laws:
  the numeric-mM ATP quotient, Cav1.2's shift, and claim strings (§5).
  - The 112-module closure also holds `processes/cell_zone_transport.py` and the "native transporter" spec,
    which row I10 says cannot enter live `src` as they stand. So A must also make the cluster's admission edits
    that C treats as optional, or it puts barred code into live `src`.
  - New live code may start to depend on the copy before it is retired.

**Route B: re-express directly; delete legacy when the ensemble is canonical.**

| Step | Content | Agent-days | Gates and lanes |
|---|---|---|---|
| B-0 | The science captures | 0.3 | about 1.5 lane-hours |
| B-1 | As A-1 | 4.5–7 | one full gate |
| B-2 | Re-express the ensemble as the features land | 8–12 | 2–3 gates; judged runs 2–4 lane-hours |
| B-3 | The deletion batch, with legacy deleted whole | 2–3 | as A-3 |
| **Total** | | **15–22, plus the features** | **4–5 full gates, about 12–15 lane-hours** |

- **Meanwhile in every gate:** every test of legacy itself, the physiology stack's included (§7.2).
- **The BETSE-rule risk is the lowest.** Nothing is relocated, and the physiology stack's BETSE glue never moves.

### 7.5 Route C: prune legacy in place to the used cores, delete the rest now, then re-express

**It is the user's D346 choice again.** On 24 November D346 deleted what neither BETSE nor the calcium ensemble
used, and kept the rest until it was ported. D348, later the same afternoon, withdrew that: "no partial deletion",
because 180 files outside legacy used both the kept and the deletable parts. Two things have changed.
- **D374 retired the physiology stack,** so BETSE needs no legacy. What C keeps is the ensemble's core, with
  `spatial_extracellular@2` for JUPITER. The `@1`, `@2` and `@8` paths leave for the live registry at C-1.
- **D348's objection is smaller:** against its 180 files that used both parts, about 49 change by hand at C-1, and most
  of those would change on every route (below).

**The kept core** (`probe8.json`), from these seeds:
- the ensemble's families, with `er_calcium@1`, `spatial_extracellular@2` and `finite_extracellular@2`;
- the `ensemble/cluster.py` and `coupled.py` hooks;
- the two assembly command lines (`assembly_cell.cli` and `assembly_cluster.cli`, with their `__main__`s), which
  run the ensemble on a CPU and which the captures use;
- `resolved_tissue@8`'s wrapper, `legacy/models/surface_catalog.py`. C-1 folds it into live code, so the count below
  is an upper bound;
- every package `__init__` above them.

**The firm figure: C-1 removes at least 58% of legacy's 75,559 lines.**
- 112 of the 321 modules stay (29,223 lines), 208 go, and the hub `registration.py` (2,597 lines) is pruned in
  place. At least 58%, if all of the hub stays; up to 61%, if nothing of it did. C-1 must keep the hub's entries for
  the kept IDs, so 61% is out of reach.
- It is the full static closure, with function-level imports counted, and needs no edit to a kept module apart
  from the hub. It is a static count, so C-1's own dry run proves it.
- 106 of the 112 are on the lead's 24 November keep list. The other six are the two command lines with their
  `__main__`s, `ensemble/cluster.py` and `surface_catalog.py`.

**Estimates beyond that, each resting on further edits to kept modules:**
- **About 62%,** with the cluster's five `resolved_*` branches cut from `assembly_cluster/engine.py` and
  `ensemble/cluster.py` (59–62% by the hub).
  - The review quoted my earlier "63%" as the firm figure. I had labelled it as needing no edit, and that was
    wrong: the probe had already cut those branches, and it left out the command lines.
- **About 85%,** with the cluster's `spec.py` and `engine.py` also admitting only the kept ionic children:
  about 49 modules and 11,500 lines. This is by subtraction, not computed.

**Kept IDs:** the six of the ensemble, `er_calcium@1`, `compartment_reactions@1`, `spatial_extracellular@2`,
`finite_extracellular@2` and `@3`. `resolved_tissue@1`, `@2` and `@8` are not kept in the hub: their dispatch moves
to the live registry at C-1 (§7.3). `finite_extracellular@3` is the integrated ensemble's world
(`configs/junction_finite_cluster.json`). The dry run found no further ID that a live test needs kept: the other
worlds its live tests run on are vehicles (V1 to V4).

**D348's objection, counted again with the dry run.** Earlier versions gave 15 direct edits, with 50 fixture files open.
Both came from import edges and IDs in a file's own text, so neither could see a world reached through a fixture or a
configuration. What changes by hand at C-1:

| What | Files | Basis |
|---|---|---|
| Live `src`: `definitions/specs.py`, `surface_tissue_spec.py`, `surface_kinetic_spec.py`, `ensemble/ionic.py`, `execution/grid.py`, `registry/models.py`, `registry/model_table.py`, `__main__.py` | 8 | read |
| The shared worlds and their users (V1): `tests/conftest.py`, `tests/batch_fixtures.py`, and 18 of the 20 users. `test_continuity_gpu.py` and `test_run_view.py` use only the fixtures | 20 | 16 users break in the dry run; four read |
| Other live tests whose world goes (V2–V4): nine planning tests, `test_projective.py`, `test_recovery_response_grid.py`. `test_numerical_refinement.py` is counted above | 11 | nine break in the dry run; two, in tier 3, read |
| The parity ladder (G3): `emulator/spatial_spec.py`, `test_betse_spatial_trajectory.py`, and the new home of `same` | 3 | the two changes restored all 12 files in a throwaway copy |
| Live tests that mix in a world that goes: `test_surface_catalog.py` (`resolved_tissue@7`), `test_surface_tissue.py` (one test on `legacy/models/tissue.py`), `test_surface_pump_v3_gates_equivalence.py` (@8's wrapper), `test_declarations.py` (two deleted IDs) | 4 | read |
| A helper imported from a test that goes: `test_cav_channels.py` | 1 | breaks in the dry run |
| The guard list and the refusals' rows: `test_continuity_bypass.py`, `test_reaction_transport.py` | 2 | read |
| **In all, about** | **49** | the dry run and reading; the pruned tree's own run fixes it |

- **Most of the 49 are the same on every route.** They drop a world that goes, so A-1 and B-1 hold them too. C's own
  are the hub's prune, and the places it edits twice: `ensemble/ionic.py`, the manifest's legacy list and
  `test_declarations.py`.
- **If the planning copies are consolidated** (V2), one of the nine is edited and the rest join the removal list: about 41.
- **Of the earlier 15,** eight remain. The other import edges belong to files that go with their families (a script, two
  barrier fixtures, the recovery diagnostic and `test_multispecies_build_audit.py`), and two of the four named tests
  already error at collection.
- **The 50 fixture files: none needs a hand edit.**
  - 20 go, or are left with no user. Their tests go (the two barrier-dispatch tests are legacy-subject, now read), or change
    vehicle.
  - 18 are held only by tests that pass with legacy gone, so a deleted ID in their text breaks nothing. 16 of them go
    if three reference tests are removed (below). Two stay with `test_surface_reference.py` and `test_osmotic_water.py`,
    which test arithmetic and a kernel that live tests use.
  - 12 are held by tests that stay. Ten are the chain under `surface_catalog_fixtures.py`, which builds dictionaries and
    parses none of them (read). `validation/assays/rehost_probe.py` uses a kept ID, and
    `scripts/audit_multispecies_build.py` stays with the acceptance test the lead kept.
- **Helpers imported from tests that go.** The dry run counts 39 tests outside the physiology stack that import a helper
  from a legacy-subject test file. By this plan's classes 27 go with their subjects, nine import from a file that
  stays at C-1, and three break: `test_cav_channels.py` and two planning tests, all counted above.
- **Tests that go, at C-1:**
  - **Tiers 1+2: 99 files, 2,398 test-seconds.** 95 break in the dry run and test a family that goes (§9). Four more
    physiology tests pass without legacy and retire with their stack (D374): `test_native_noise.py`,
    `test_physiology_native_calendar.py`, `test_physiology_perturbation_step.py` and `test_physiology_random_streams.py`.
  - **Tier 3: 139 files, by static evidence,** of which the dry run ran none.
  - **Eight more are the removal list's choice** (8.1 test-seconds). Their outcome does not change with legacy gone, and
    they test a legacy family's driver or reference: the four driver tests of §2.2,
    `test_active_polygon_energy_contract.py`, `test_voltage_gated_channel_reference.py` (one recorded failure),
    `test_joint_water_epoch_reference_refinement_contracts.py` and `test_surface_bath_reference_charge.py`.
  - **The earlier 109 and 141 held live tests:** the seven planning tests, `test_numerics.py`, `test_phase_records.py`,
    `test_fine_windows.py`, `test_batch.py`, two tier-3 planning tests and `test_surface_tissue.py`, the last against
    this plan's own row A12. They also held `test_assembly_worker_source.py`, which tests the kept command line, and
    `test_legacy_entry.py`, which guards the hub until C-3. They missed `test_source_pair_cli.py`,
    `test_multispecies_build_audit.py` and `test_spatial_extracellular_example.py`, which the dry run shows, and the
    two barrier-dispatch tests.
  - **14 of the 63 that go by their row test only code that stays in the core's closure** as a passenger, such as
    `processes/finite_energy.py`. The prune does not break them. They go because their capability is canonical or
    dropped, and the removal list says so.
- **At C-3 the rest follows:** the dry run's 14 edits in seven live files (`registry/models.py`, `definitions/specs.py`,
  `execution/schedule.py`, `__main__.py`, `ensemble/families.py`, `ensemble/cli.py`, `registry/declarations.py`),
  `test_model_table.py`, whose plant anchors on the hub's call, `test_legacy_entry.py`, and the gate scripts of §10.

**The guards of the kept core while it lives.** Their recorded state matters, because they and C-0's windows are the
prune's proof:
- **The calcium clusters and the store (tier 3):** `test_spatial_calcium.py` (30 pass) and `test_er_calcium.py` (29).
  `test_plasma_calcium.py`, `test_gated_calcium.py` and `test_ip3_calcium.py` have no outcome in the tier-3 record.
- **The assembly:** `test_assembly_cell.py` (4 pass, one recorded failure) and `test_assembly_cluster.py` (25, two) in tier 3;
  `test_assembly_controls.py` and `test_assembly_worker_source.py` in tier 1; the GPU integration tests, which skip on a
  CPU gate.
- **The chemistry:** `test_compartment_reactions.py` (34 pass, tier 2).
- **Three of the eight that the dry run counts as kept core cover an ID that goes,** so by subject they belong on C-1's
  list: `test_finite_extracellular_production.py` (`finite_extracellular@1`), and the two of `spatial_extracellular@1`
  below. They are counted with the core, as the lead's count has them, and are for the lead to weigh (§13).
- **`finite_extracellular@2`:** none that runs. `test_kinetic_finite_dynamics.py`, `test_kinetic_finite_runner.py` and
  `test_kinetic_finite_schema.py` error at collection in the record, because their saved reference
  (`runs/num-011-kinetic-pump-2026-09-16/`) is not in the tree. `test_finite_extracellular_production.py`, which covers
  `finite_extracellular@1`, errors the same way. Live tests on it do run: `test_gpu_execution.py` and
  `test_batch_identity.py` (V5).
- **`spatial_extracellular@2`:** no test of its own. `test_assembly_cluster.py` runs the cluster on it, and
  `test_tissue.py`, which goes, compares the next version with it.
  - Earlier versions named `test_spatial_extracellular_acceptance_resources.py` and
    `test_spatial_extracellular_context.py` here. They cover CORE-010's acceptance of `spatial_extracellular@1`
    (`docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE.md:1–4`, `tests/spatial_extracellular_fixtures.py:71`), whose code @2 is
    built on. One of the second's three tests fails in the record.
  - The lead ruled the first kept core, as the JUPITER world's, and it is kept here. It runs no world: its 103 tests
    check the acceptance driver's registration, limits and array comparison. So keeping it needs the modules it imports,
    which stay in the closure, and no hub entry for `@1`.
- **The planners and the ensemble:** `test_ionic_plan_admission.py`, `test_jupiter_plan.py`,
  `test_surface_catalog_planning.py` (V5), and `test_integrated_ensemble.py` in tier 3 (7 pass).
- **`resolved_tissue@8`:** `test_surface_catalog.py` (33 pass) and `test_surface_pump_v3_gates_equivalence.py` (9), tier 3.
- **`@1` and `@2`,** whose dispatch leaves the hub at C-1: the six test files of row A12, all tier 3.
- **The hub:** `test_legacy_entry.py` (19 pass, tier 1).

| Step | Content | Agent-days | Gates and lanes |
|---|---|---|---|
| C-0 | Captures: bitwise windows for the kept core (the prune edits must leave its worlds bit for bit), and the science set. They cover `finite_extracellular@2` and `spatial_extracellular@2`, which have no working test of their own | 0.5 | about 2 lane-hours |
| C-1 | **The prune batch:** the approved removal list; 208 of legacy's 321 modules deleted; the hub pruned; the hand edits, about 49; the batch's live-side items (as A-1, without the JUPITER and integrated-ensemble retargets, which wait for C-2). **Among them the dispatch of `resolved_tissue@1`, `@2` and `@8` moves to the live registry, by exact type, so that live code needs no kept hub (§7.3).** Further edits inside the cluster buy the estimates above, and are optional | 5.5–8.5 | the pruned tree's own dry run, about 45 minutes; one full gate; tier 3 once (1–2 h); re-measure (about 1 h) |
| C-2 | Re-express the ensemble and the JUPITER world as the features land (rows A10, E4 included) | 9–14 | 2–3 gates; judged runs 2–4 lane-hours |
| C-3 | Delete the remaining core, the hub and `registry/legacy_entry.py` | 1–2 | one full gate; tier 3 once; re-measure |
| **Total** | | **16–25, plus the features** | **4–5 full gates (two with tier 3), about 13–18 lane-hours** |

- **Meanwhile in every gate:** the core's own tests (§7.2) and the pruned hub's dispatch-miss path. Most of the
  tier 1+2 saving arrives at C-1.
- **The BETSE-rule risk is low.** Nothing enters live `src`, and the physiology stack's BETSE glue (§5) is deleted
  at C-1. The core's own BETSE-derived conventions stay where they are, in the holding area, until C-3.
- **What it reverses:** D348's "no partial deletion" and "one deletion with one gate". There are two deletions,
  the first the larger.
- **Its own risk:** the prune of the hub, whose bitwise proof is C-0's windows, because the core's tests are weak.

### 7.6 The recommendation: Route C, under either answer

| | A | B | C |
|---|---|---|---|
| Agent-days beyond the features | 20–30 | 15–22 | 16–25 |
| Full gates | 5–7 | 4–5 | 4–5 (two with tier 3) |
| Lane-hours | 15–20 | 12–15 | 13–18 |
| Legacy lives, answer (a) | until A-3 (11–16.5 agent-days), then a copy for 22.5–36 | whole, for 28–44 | at least 58% leaves after 6–9; the core for 23.5–38 |
| Legacy lives, answer (b) | until A-3, with the copy open-ended | whole, open-ended | the core open-ended; the rest leaves at C-1 |
| A relocated copy in live `src` | yes | none | none |
| Every gate carries meanwhile, tiers 1+2 | the copy's tests: 52 test-seconds | all tests of legacy itself: 2,454 test-seconds | the core's tests, 56 test-seconds, and a pruned hub |
| BETSE-rule risk | moderate to high | lowest | low |
| Thrown away | the relocated copy | nothing | nothing |

**Why C:**
- It delivers almost all of the deletion's gate saving at its first deletion, as A does: 2,398 of the 2,454
  test-seconds in tiers 1+2.
- It costs no throwaway copy, and nothing BETSE-derived enters live `src`, as B does.
- It does not need an answer to the GPU question to start, and it stays cheap if the answer is (b).
- The lead's removal analysis prepared most of its list, and the dry run now fixes the tier 1+2 part.

**What the dry run does not settle for C:** it deleted everything, so C's prune is still to be proved, by C-0's
windows and C-1's own gate; and its 139 tier-3 files are still static.

**B fits** if the user holds D348's single deletion and answer (a), and accepts every legacy test in every gate
meanwhile. **A fits** only if legacy must be gone before the features, whatever the copy costs; under answer (b) it
leaves that copy in live `src` with no end.

## 8. Qualifying a re-expression: science-length captures and a derived tolerance

**Two kinds of capture, both from a snapshot frozen before the rename's move:**
- **Bitwise windows, Routes A and C.** They prove a move (A) or C's prune edits, not a re-expression: the first scalar window of up
  to 200 steps, through `validation/results_baseline.py save --from`.
- **Science-length runs, both routes.** These qualify a re-expression. Each used capability's consumer
  worlds run at the length their claim used, at three steps, with every recorded array saved.

**The science set (the used capabilities after D374):**

| Worlds | Length | Source |
|---|---|---|
| The four calcium clusters' ionic children | 20 ms at 12.5 µs, 1,600 steps | `configs/{spatial,plasma,gated,ip3}_calcium_cluster.json` |
| The four assembly-regulated calcium clusters | the qualified horizon: 20 ms, 12.5 µs, 16-tick windows (`docs/GPU_ENSEMBLES.md:164–165`), 4 seeds per arm, on the CPU command line | `configs/assembly_regulated_*calcium_cluster.json` |
| The cell family | 20 ms at 100 µs, 200 steps | `configs/assembly_regulated_cell.json` |
| The cluster's base and the JUPITER world | 20 ms at 50 µs | `configs/assembly_regulated_cluster.json`, `configs/spatial_kinetic_cluster.json` (`spatial_extracellular@2`) |

Each runs at h, h/2 and h/4. The capture tool halves dt and doubles `max_steps`; the admission bounds,
such as `spatial_calcium`'s h·loss ≤ 0.25, still hold.

**Two kinds of row, told apart before any run:**
- **Same equations:** the re-expression keeps the model's equations and changes only the code, the
  splitting or the integrator. A numerical band applies.
- **Changed model:** the equations change. Examples are an ER store without its own voltage (the
  pools-at-the-cell's-potential branch of G-4). **Corrected 25 November:** the PMCA at its 1 M standard state (B1) and NCX in
  the monomial form are the same equations, not changed models (§14.2, §14.3). No band applies. These rows are judged by the consumer's own
  registered criterion, such as the calcium ensemble's independent references at 3e-9 (`tests/unit/test_spatial_calcium.py:68–76`),
  or by an independent reference written for the purpose.

**The tolerance for same-equation rows is derived, never tuned or ruled** (D374). Each re-expression's
registration derives it, before any re-expressed run. A template it may adopt, from both methods' own
refinement:
- **Observed order,** computed per array for each method from its own h, h/2 and h/4 runs:
  p̂ = log2(|X_h − X_{h/2}| / |X_{h/2} − X_{h/4}|). The legacy runs come from the snapshot; the candidate's
  runs are part of its qualification.
  - An array is judged by the band only where each method's p̂ is within 0.5 of its declared order: 4 for
    RK4, and the declared order of the candidate's splitting or IMEX scheme.
  - Elsewhere, for example where the differences are already at rounding, it is judged by the consumer's
    registered criterion, and reported so.
- **What is compared:** each method's extrapolated solution, X* = X_{h/4} + (X_{h/4} − X_{h/2})/(2^p − 1),
  at the declared output times.
- **The band:** |X*_legacy − X*_candidate| ≤ 2·(U_legacy + U_candidate) + 64 ulp · max|X|, where
  U = |X_{h/2} − X_{h/4}| / (2^p − 1) is each method's own error estimate.
  - Each method's discretisation error enters, so an IMEX or split candidate at a coarser order is not held
    to RK4's band.
  - The floor is of the size that A7's summation change moved arrays by (`ARCHITECTURE.md`).
- **Conservation ledgers** keep their own absolute bounds, for example 1e-9 pJ on energy. They are properties,
  not comparisons.
- **Stochastic worlds:**
  - The assembly pool's code is live and unchanged, so the same seeds must give the same event sequence,
    compared exactly.
  - If a re-expression changes it, the comparison becomes statistical over a declared seed count, with
    the ensemble's own Wilson-interval checks (`legacy/ensemble/cluster.py`'s `aggregate`, moved).
- **The power check, judged first (D366's lesson):** a planted 1% change in one rate constant must exceed
  the band in at least one judged observable. An observable that misses it is reported as not tested, and
  the qualification counts only tested ones.
- **The re-expression's own step:** it is compared at matching output times. It must pass its own
  step-halving within the same band.

**The command form** is the one verified on 24 November, in shards on a lane:
```
PYTHONPATH=SNAP/src:SNAP JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 CUDA_VISIBLE_DEVICES= JAX_ENABLE_COMPILATION_CACHE=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /mnt/workspaces/Cells/venv-cpu/bin/python -B SNAP/validation/results_baseline.py save OUT/<part> --sets <sets> --from ORIGIN --max-steps <steps>
```
- **The full length** comes from `--max-steps` at or above the world's step count: the first window then
  holds the whole run.
- **The assembly families** run on the CPU command line, one run per config, seed and step. This path was
  not probed:
  ```
  CELLS_OUTPUT_ROOT=OUT JAX_ENABLE_COMPILATION_CACHE=false PYTHONPATH=SNAP/src:SNAP JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 /mnt/workspaces/Cells/venv-cpu/bin/python -B -m cells assembly-cluster run ORIGIN/<config>.json --output OUT/<config>/<seed>/<step> --backend cpu
  ```
  - `assembly-cell run` is the same for `configs/assembly_regulated_cell.json`.
  - It exports `JAX_ENABLE_COMPILATION_CACHE=false` itself, since `configure_caches()` sets a cache folder
    (`execution/output_paths.py:19–31`). The run then checks OUT for cache entries
    (`gate_steps.py jax-entries`).
  - The compare reads `checkpoint/state.npz` and the observation numbers as arrays.
- **The unit:**
  ```
  scripts/run_detached.sh legacy-capture 24G --cpus 0-3,16-19 --oom-first --wait-headroom 26G -- flock /mnt/workspaces/Cells/locks/gate-cores-0-3.lock bash CHECKOUT/validation/legacy_port/capture.sh SNAP ORIGIN OUT
  ```
  Lane B takes `--cpus 8-11,24-27` and its own lock; CPUs 12–15 and 28–31 are never used.
- **Not yet written:** `capture_worlds.py`, which writes `ORIGIN` and the step-halved variants, and
  `capture.sh`. They run from the checkout against the snapshot (`PYTHONPATH=SNAP/src:SNAP`), recording both
  revisions.

**Measured on 24 November** on CPU 4, under the timed lock and a 4 GB scope, cold:

| World | 5 steps | 200 steps | Per step | Compile |
|---|---|---|---|---|
| `spatial_calcium@1` | 22.6 s | 25.1 s | 0.013 s | about 22 s |
| `resolved_tissue@12` | 76.8 s | 87.0 s | 0.052 s | about 76 s |
| `resolved_calcium_energy@5` | 154.9 s | — | — | — |
| `resolved_open_calcium_energy@1` (fixture, JIT off) | 142.7 s | — | — | — |

**Estimated cost of the science set:**
- **Ionic children:** about 43, 64 and 106 s per config at h, h/2 and h/4, so about 15 CPU-minutes for the
  four.
- **Assembly runs:** 6 configs × 4 seeds × 3 steps at an estimated 3–8 minutes each, about 4–8 CPU-hours.
  This is unprobed.
- **The JUPITER world:** about 10 minutes.
- **Total:** about 6–8 CPU-hours, about 1–1.5 hours of one lane in 8 shards.
- **Bitwise windows (Routes A and C):** about 1–1.5 CPU-hours for the core.
- **Placement and timing:** the captures wait for the route. The probes ran on CPU 4 under
  the timed lock and released it between runs.

## 9. Tests: move, stay or go

**Measured, for tiers 1+2:** the dry run's 147 files, sorted by what each needs at C-1 (`dry13.json`).

| Group | Files | Test-seconds | At C-1 |
|---|---|---|---|
| Goes by its coverage row | 63 | 1,441 | on the removal list |
| The physiology stack: 30 files under `tests/betse_physiology/`, and the two tests of its helpers | 32 | 937 | retired (D374), with four more of its tests that pass without legacy (20 test-seconds) |
| Kept core | 8 | 50 | stays until C-3; five of the eight already fail in the record, and three cover an ID that goes (§7.5) |
| Kept by this plan's reading: `test_assembly_worker_source.py` (the kept command line) and `test_legacy_entry.py` (the hub's guard) | 2 | 6 | stays until C-3 |
| Live, on the shared worlds (V1) | 12 | 188 | new live worlds |
| The live planner, on a world that goes (V2) | 7 | 120 | a live world, or the removal list for the copies |
| Live, on another world that goes (V3, V4) | 2 | 13 | a live world, or the clock retired |
| Live, on a kept world (V5) | 6 | 21 | unchanged until C-2 |
| The parity ladder: four through `identifier`, eight through `same` (G3) | 12 | 187 | two changes |
| Single reasons: `test_cav_channels.py`, `test_declarations.py` (both edited at C-1), `test_model_table.py` (at C-3) | 3 | 32 | edited |
| **In all** | **147** | **2,995** | |

**The 63, by row.** Nobody had checked the dry run's "67 the rest" against §3. I mapped each by its docstring and its
legacy imports, not line by line: 63 fall on a row that is dropped or canonical, two are the physiology helpers'
tests, and two stay.
- P1 13, C3 14, D3 6, C2 4, A11 4, D6 3, D7 3, D8 3, B6 with D1 3, D4 2, D9 2, G2 2, D5 1, A10 1, I7–I9 1, I10 1.
- Two of C3's, `test_network_control.py` and `test_network_reactions.py`, test modules the row did not name. Only the
  regulated families import them. The row now names them.
- Eight of the 63 already fail in the record.

**Tier 3, static.** Of the 222 files 11 were run. Of the other 211:
- 139 go with their subjects, by import and name (the two barrier-dispatch files among them were read);
- eight are kept core, with `test_surface_catalog.py` (@8) among them;
- two are the emulator's, and fixed with the parity ladder;
- four are live on a world that goes: `test_batch.py`, the two planning tests of V2, and `test_batch_windows.py`, which
  has no import evidence;
- the other 58 show no reach by import.

**Under §2's definition:**

| Class | What happens | Files (tiers 1+2 / tier 3) |
|---|---|---|
| **Go:** the subject is a legacy model whose capability is canonical or dropped | Deleted in one batch with the deletion, by a removal list (D224) giving each file's capability row and reason. Under Route C they go at C-1 | 99 / 139, the first measured but for four files, the second static. The retired physiology set is 36 / 24 of them (D374) |
| **Move:** physics, conservation and reference tests of the used capabilities (§7.5's guards) | Under C they stay with the kept core until C-2. Under A they move with the relocation. Under B they stay until the deletion. Each is retargeted to the canonical form when its capability is re-expressed, and assertions on legacy structure are dropped | 9 / 7, with the hub's guard beside them |
| **Stay:** live-subject tests on a legacy world (group V), the parity ladder, and @3's reference | The vehicles are replaced at C-1, or at C-2 for V5. A9 and A12 keep `resolved_tissue@8`, `@1` and `@2` (Q5 (a), widened) | 42 / at least 17 |
| **New** | None in the tiers. A re-expression's judged qualification is a recorded run, not a tier test. A test that compiles a world states its seconds and reason (D224). The refusals' rows join an existing test (§7.3) | 0 |

**Static counts that the dry run replaces:** 292 files reach legacy by import, 137 of them in tiers 1+2; 109 and 141 files
go; 28 and 14 reach the kept core. The import reach had taken in the parity ladder's two imports and several live tests
(§7.5).

**Recorded tier-3 failures** stay as recorded in moved files: `test_assembly_cell.py` (1) and
`test_assembly_cluster.py` (2). A fix is a row in the existing file (D224).

## 10. The deletion: content, removal list, gate and saving

**One deletion under A and B; two under C.** C's first, at C-1, is the larger; its second, at C-3, removes the
kept core, the hub and `registry/legacy_entry.py`. Each runs as below.

**Before each:** main is tagged and its snapshot frozen, as the BETSE-native removal was
(`native-betse-frozen-2026-11-08`).

**The commit removes** (under C, the first takes everything outside the kept core, and the second the rest):
- `src/cells/legacy/` and `registry/legacy_entry.py`;
- the `legacy()` call sites: the dry run's 14 edits in seven live files are the list, with the tree importing
  and the command line running after them (`deletion.json`);
- `ensemble/ionic.py`'s rows for capabilities not kept (the rows for `resolved_tissue@1`, `@2` and `@8` stay);
- `registry/declarations.py`'s legacy list and the manifest's `legacy` key. That is coordinated with the
  viewer's agent first, and the format is the rename note's Q6;
- live code that only legacy uses, which the dry run leaves in place: the inline families' live half at C-1, and at C-3
  the spec classes in `definitions/specs.py` that no other live file names (about 35, by name).

**The removal list, by area** (what the dry run's sweep found naming legacy, at C-1 unless marked):
- **Tests:** §9's: 99 files in tiers 1+2 and, by static evidence, 139 in tier 3, with the eight of §7.5 left to choice.
  `tests/unit/test_legacy_entry.py` goes at C-3.
- **`tests/` helpers:** 25 import legacy. They go with their tests, except `spatial_extracellular_fixtures.py`, which
  serves the kept acceptance test.
- **`validation/`, 73 files:** 17 physiology and 18 REF-era drivers and three helpers (D374); 21 that serve dropped rows
  (17 in `validation/tissue/`, two in `topology/`, one each in `execution/` and `geometry/`); 13 of the ensemble's in
  `assembly/` and `ensemble/`, at C-3; and `betse/emulator/spatial_spec.py`, edited.
- **Scripts, 14 that import legacy.** Earlier versions named few of them.
  - **Ten go at C-1,** September and October build drivers of A10 and A11: `audit_finite_extracellular_build.py`,
    `audit_physical_ionic_graph_build.py`, `audit_voltage_gated_build.py`, `verify_bioelectric_build.py`,
    `verify_bioelectric_pair_build.py`, `verify_emt_build.py`, `verify_finite_extracellular_build.py`,
    `verify_physical_ionic_graph_build.py`, `verify_source_pair_build.py` and `verify_voltage_gated_build.py`. Scripts
    that import them follow, such as `verify_world_build.py` and the `preserve_core00*_baseline.py` set, and the
    drivers that run a deleted ID without importing legacy, such as `verify_pair_build.py`.
  - **Four stay until C-3** with the kept acceptance test: `audit_spatial_extracellular_build.py`,
    `spatial_extracellular_production_audit.py`, and, imported by its driver, `verify_multispecies_build.py` and
    `audit_multispecies_build.py`.
- **Five scripts name legacy by string:** `scripts/gates/gate_steps.py:112` (the hub's guard in the always-run set) and
  `scripts/gates/fingerprints.py:72`, edited at C-3; `scripts/legacy_inventory.py`, which
  `scripts/source_moves_plan.py` imports, and `scripts/source_moves.py`'s planted strings, at C-3 with D188's tools.
- **Configurations:** 101 of the 120 that stop resolving, 98 in `configs/` and three in `examples/`; the other 19 at
  C-2 or C-3.
- **Documents:** group H's pointers, the regenerated `docs/library/`, and PROGRESS.

Reports and records stay.

**The gate** is the full one:
- the IDs, with removals declared (`REMOVED_OK_FILE`);
- crossrev (identical: no set reaches legacy);
- tiers 1+2 on the surviving files;
- G1 at 113 of 113 (its worlds name no legacy ID);
- tier 3 once, deliberately, against a refrozen record;
- the tiers re-measured and folded;
- the private-term scan.

The dry run ran the third only, on the whole-legacy tree. The scope map stays stale until the next nightly rebuilds it.

**The saving.** Measured in the gate of 24 November: tiers 1+2 took 2,531 s of about 3,275 locked seconds,
G1 592 s and crossrev 152 s, so 0.186 s of wall per test-second. At `c9da0fdb` tiers 1+2 hold 13,677 test-seconds.

| Stage | Today | After C-1, with the dry run |
|---|---|---|
| Tiers 1+2 | 13,677 test-seconds, about 42 minutes of wall | −2,398 test-seconds (17.5%), about 7.5 minutes, for the 99 files that go. The earlier figure was −2,564 and 8 minutes. If the planning copies go too, up to about −2,500 |
| The upper bound | | −2,995 (22%), about 9.3 minutes: every file that breaks. The earlier bound of −9,554 (70%) is withdrawn: the fixture-reaching tests do not run legacy worlds |
| G1, crossrev | 592 s, 152 s | unchanged |
| Tier 3 | 215 recorded files, 87,166 test-seconds | 139 files go by static evidence, 67,143 recorded test-seconds (77%) |

**When the saving arrives:**
- Route A: at A-3.
- Route C: 2,398 of 2,454 test-seconds at C-1; the rest at C-3.
- Route B: only at the deletion, after the four features and the re-expression.

## 11. The rename's Q3, decided (D371): what it means for each route

**D371 chose (a).** Legacy's files are re-spelled too, after a check for pinned legacy config digests. The
table below stays as the comparison that informed the choice. Route C keeps D371's (a): the rename lands
first, on the whole of legacy, and C-1 then deletes most of what was re-spelled.

The rename note's Q3 concerns the 18 live pieces that legacy also spells: `constant_field`, the Na/K
pump, Kv1.x, Kir2.1, Nav1.2, the leaks, the field solver, `finite_bond_assembly` and the water operator. They
make 2,272 occurrences in 102 legacy definitions and 67 in 33 code files.

| Rename Q3 option | Route A | Route B | Route C |
|---|---|---|---|
| (a) re-spell them in legacy too, 135 files: **chosen (D371)** | Consistent: the relocated cores move already re-spelled. Legacy keeps parsing, and its tests stay green through the rename's gate until A-3 | Consistent, at the cost of re-spelling files that are deleted only at the end. Legacy keeps parsing until then | Consistent. Most re-spelled files go at C-1; the kept core keeps parsing with its new spellings until C-3 |
| (b) keep the 18 bare until legacy is deleted, then a second move | The relocation's neutralising commit re-spells the moved cores. The second move follows A-3. @3's definitions mix spellings until A-3 | @3's definitions mix spellings until B-3 | @3's definitions mix spellings until C-3 |
| (c) delete legacy first, then rename | The rename's 18 pieces wait until A-3 | The rename's 18 pieces wait for the features and the re-expression | They wait until C-3 |
| (d) live files only | Ruled out by the rename note: the parsers both families share would refuse legacy's files | Same | Same |

**In every case:**
- **The captures** come from the pre-rename snapshot and are compared through the committed table. They
  need no re-spelling.
- **No retirement comes before the rename's move** (D374). The REF-era drivers' files, about a dozen of its 30
  `validation/betse` files, are re-spelled with the rest, and go in the deletion batch.

### 11.1 Input for the rename's mapping: three live models whose dispatch sits in legacy

**`resolved_tissue@1`, `@2` and `@8` are live models, not legacy's frozen ones.** Their spec classes, parsers and
model modules are live; only their dispatch is in the hub. The lead's widening of Q5 (a) covers `@1` and `@2`; `@8`
was already covered, and it is the same case.
- **What the rename holds today.** Its candidate at `f8c6c326` lists all twelve `resolved_tissue` majors among
  legacy's frozen models (`legacy_models.json`) and has none of them in `table.tsv`. The note's five live models outside
  the model table (its §1.2) do not include them. Read on 24 November; nothing of the rename's was edited.
- **Proposed IDs, to be named in the rename note:** `cells.model.resolved_tissue@1`, `@2` and `@8`, majors unchanged.

| Old ID | Declared in | Spec class | Parser | Model module | Dispatch today, in `legacy/registration.py` |
|---|---|---|---|---|---|
| `resolved_tissue@1` | `MODEL_ID`, `definitions/surface_tissue_spec.py:22` | `SurfaceTissueModel` (`:74`) | `surface_tissue_spec.parse` | `models/surface_tissue.py` | parse `:1444–1447`, model `:832–833`, dict `:1977–1980` |
| `resolved_tissue@2` | `MODEL_ID`, `definitions/surface_kinetic_spec.py:36` | `SurfaceKineticModel` (`:114`) | `surface_kinetic_spec.parse` | `models/surface_kinetic.py` | parse `:1196–1211`, model `:806–807`, dict `:1946–1949` |
| `resolved_tissue@8` | `CATALOG_MODEL_ID`, `definitions/surface_kinetic_spec.py:42` | `SurfaceCatalogModel` (`:163`) | `surface_kinetic_spec.parse` | `models/surface_kinetic.py`, through legacy's wrapper `legacy/models/surface_catalog.py` | parse `:1196–1211`, model `:794–795`, dict `:1946–1949` |

- **What the rename note has to settle:** mint the three at the rename, or leave them bare with legacy until C-1 moves
  their dispatch and mints them there.
  - If it mints them first, legacy's own places must be re-spelled with the rest (its Q3 (a)): the hub's literals above,
    and the definitions and code that spell them. I have not counted those.
  - Either way `ensemble/ionic.py` (`:177, 196, 202`) and the constants above carry the spellings live code reads.

## 12. Risks

1. **Dispatch between landings (Routes A and C).** Under C it is the pruned hub that keeps the kept core's
   entries until C-3.
   - Unported legacy classes derive from the relocated ones: `TissueCalciumModel` from `IP3CalciumModel`,
     and `TissueModel` from `SpatialJunctionSpec`.
   - `model_for`, `to_dict` and `control_values` are subclass-first isinstance chains, so until A-3 those
     entries stay in the hub, pointing at the moved modules. Only parse entries, which match exact IDs, go
     live.
   - The alternative is exact-type checks. The three `resolved_tissue` entries that move at C-1 use them (§7.3).
2. **A tolerance that cannot test.** Without the power check, a wide band passes anything. The order check
   and the planted change are judged before the comparison.
3. **Features on the critical path.** Under B, four features stand before any deletion, and legacy's tests
   cost gate time and maintenance meanwhile. Under A and C they delay only the re-expression. G-8 stands apart,
   and under answer (b) it has no date (§7.1).
4. **Throwaway work (Route A).** The relocated copy is re-expressed at A-4 and discarded at A-5. Keeping it narrow (only the
   feature-blocked used cores) bounds that.
5. **BETSE conventions leaking into live `src/cells`.** §5 lists them. Route A's copy is the exposure; C and B
   move nothing. The physiology stack's BETSE glue is deleted on every route (D374).
6. **Lost capability.** Each Drop row names what goes. Group H's pointers are corrected, so no document
   claims a capability that is gone.
7. **The rename breaks legacy before the deletion.** It is avoided by the rename's Q3 (a), chosen by D371. Captures from the snapshot are
   unaffected. It also moves the text the dry-run tool's edits anchor on, so the tool is re-read at the deletion's base.
8. **Unprobed paths.**
   - The assembly command lines' capture cost, and the cache setting that `configure_caches()` makes.
   - The tools `capture_worlds.py` and `capture.sh` are not written.
9. **Lane time.** The captures, the pruned tree's dry run, three or four full gates and tier 3 compete with the FR
   queue. FR-43, the user's top priority, keeps the timed cores.
10. **The Lean lane** may cite legacy IDs. It gets the mapping table through the user; `lean/` is not edited.
11. **Route C's partial deletion** reverses D348's single batch. A capability the coverage table missed, and
    which only the deleted part held, would be lost at C-1. The dry run (§2.1) has corrected five rows' uses, and the
    re-read of the rows not read here (§3) comes first. 211 tier-3 files are still unmeasured.
12. **Coordination with the cardiac lane** (§4). If the ensemble and the human cardiac laws each build calcium
    handling, D210's rule of one law per mechanism is at risk. The G-1 and G-4 notes are written together.
13. **An open-ended date** (§7.2). If the user chooses answer (b), or if the features are not requested, the
    remainder lives on. A leaves a legacy copy in live `src` and B leaves every legacy test in every gate; C's
    remainder is the smallest.
14. **Static counts.** The kept set, the edge cut and the tier-3 lists come from import edges and own-text IDs. The dry
    run has corrected mine for tiers 1+2: ten live tests and two of the kept core's were among the files to go, three
    that go were missing, and the count of hand edits was 15 instead of about 49. The tier-3 lists were built the same way,
    and reading has already moved six of their files.
15. **Kernels that D211's port programme needs leave with C-1.** `legacy/processes/cotransport.py` (rows I7, I8 and
    I9) is outside the kept set, and no route step ports it. D211 reads it from the tag instead.
16. **Weak guards (Routes A and C).** The kept core's tests prove less than their number suggests (§7.5): five of ten
    in tiers 1+2 already fail, three cover an ID that goes, three of the calcium tests have no recorded outcome, and two
    kept IDs have no working test of their own. C-0's windows must cover every kept ID, and a planted change must move
    each window (§8).
17. **The retarget of the shared worlds (V1) is the largest live-side item.** Ten of its files drive a scheduled source
    that the named candidate, `reaction_transport@1`, refuses. If no cheap live world offers one, its tests lose what
    they check, or the engine needs a feature first.

## 13. The user's questions

**Answered on 25 November** (D383): Q1 (a CPU re-expression counts), the route (one branch, one deletion, one test at the end), and the four
feature notes (yes, written). The questions below that were not asked again stand as the record.

**Decided by D374, recorded here:**
- the calcium ensemble is kept and re-expressed in canonical form;
- the physiology stack (17 drivers) and the 18 REF-era drivers retire in the deletion batch, with their
  records kept;
- no retirement before the rename's move;
- Q5 and Q6 are (a) each, inside the deletion batch. The lead widened Q5 (a) to `resolved_tissue@1` and `@2` on
  24 November. Q6 (a) covers 20 test files, measured on 25 November, not nine;
- tolerances are derived in each re-expression's registration.

**Q1. What counts as leaving legacy?** This sets every lifetime in §7.1, and it is a choice about capability, not
engineering.
- **(a) A CPU re-expression counts.** The GPU path for these worlds is parked until a GPU qualification passes.
  Legacy's core goes when the CPU re-expression passes its registration.
  - It ends on the four features.
  - It gives up a capability that works today: the legacy ionic families have GPU evidence (D338).
- **(b) Legacy's core waits for the GPU.** The date is open-ended: G-8 closed as failed (D336), FR-53's Q5 waits
  for FR-53's build (D371), and a new attempt is the user's decision.
- **Recommendation: (a), with that loss stated.** A path with no date would hold legacy, or a copy of it, in the
  tree indefinitely. The measured gain from the GPU was about 1.5 times (D336's G7), and the G-4 and G-7 designs
  may open another route (§4). This is the user's call, since it trades a GPU capability for a date.
- **If (b): C is the route.** It is the only one whose standing cost stays small (§7.2).

**Q2. The route.**
- (a) Route A: relocate the used cores as a temporary bitwise copy, delete legacy, then re-express.
- (b) Route B: re-express directly, and delete legacy when the ensemble is canonical.
- (c) Route C: prune legacy in place to the used cores, delete the rest now, and re-express as the features
  land. This means two deletions.
- **Recommendation: (c),** under either answer to Q1.
  - It removes at least 58% of legacy's lines at its first deletion, the firm figure.
  - It throws nothing away, and nothing BETSE-derived enters live `src`.
  - It is D346's choice again, with BETSE's part gone (D374). D348's objection is smaller: about 49 files change by hand
    at C-1, most of them on every route, and the 50 fixture files that were open need none (§7.5).
  - The lead's removal analysis covers most of its list, and the dry run fixes the tier 1+2 part.
- **What the dry run says for this choice (§2.1, §7.6).** It measured what depends on legacy, not any route.
  - It raises the price of all three by about the same 2 to 3 agent-days.
  - It measures what B carries meanwhile: 2,454 test-seconds in every gate, about 7.6 minutes, against 56 for C.
  - It shows that the kept core's tests are weak, so C's and A's bitwise proofs rest on the captures.
  - It does not prove C's prune, and 211 of 222 tier-3 files were not run.

**Q3. If C, whether D348's single deletion yields to two.**
- **Recommendation: yes.** Each deletion has its own dry run, tag, approved removal list and full gate with
  tier 3.

**Q4. Which of the four features to request,** after the route.
- **For the ensemble's CPU re-expression:** G-1, G-4, G-5 and G-7, with NCX's registration. They are candidate
  requests, each sized by its own design note; the G-1 and G-4 notes are written with the cardiac lane (§4).
  The prices are rough until then: 13.5–22 agent-days.
- **D211's port programme also needs three:** G-1 for the CaV and HCN laws, G-2 for the instantaneous laws, and
  G-3 for calcium-activated K.
- **Recommendation:**
  - request the four design notes now, and each build as its note is accepted;
  - G-2 and G-3 follow D211's priority, below GARD and the replication;
  - G-6, G-9 and I10 wait for a consumer.

**Q5. Whether to ask for a GPU attempt (G-8).** It is separate from Q4's four.
- It would be a fresh registration, after FR-53's compensated sum, and the user's decision (D336).
- **No recommendation,** as FR-53's note gives none: the gain with the flag was about 1.5 times. It need not be
  answered for (a) in Q1.

**For the lead, waiting for the route (D374):**
- exact-type dispatch or hub entries between landings (§12, risk 1). The three moved `resolved_tissue` entries
  match by exact type whichever way it goes, as confirmed (§7.3);
- the manifest key;
- a GPU block after the ensemble's re-expression, if Q1 or Q5 calls for one.

**For the lead, new with the dry run's evidence:**
- **the refinement clock (V3):** admit a live model, or retire it with its two tests. Retiring it removes a documented
  feature, so it is the user's, on the removal list. This plan leans to it: PROGRESS, the current plan, the scientific
  basis, the roadmap and the experiments list do not name it, and `execution.fine_windows` gives declared finer steps on
  live models;
- **the planning copies (V2):** one file on live and kept worlds with the copies on the removal list, or nine edited. The
  two in tier 3 are of the same kind as the eight ruled on;
- **`test_spatial_extracellular_acceptance_resources.py`:** it is kept by the ruling, but it covers
  `spatial_extracellular@1`'s acceptance bookkeeping, not the JUPITER world's `@2`, and runs no world (§7.5). Four
  scripts that import legacy, and one helper module, stay for it until C-3. `test_spatial_extracellular_context.py`
  is the same case;
- **the four core tests that error at collection** (§7.5): removed as dead, or kept in case their references are
  restored. One of them, `test_finite_extracellular_production.py`, covers `finite_extracellular@1`, which goes.

## 14. The re-expression map (25 November 2026)

**For whom.** The notes on G-1, G-4 and NCX (D), on G-5 and G-7 (E), and the criteria's author. It says what each used
consumer becomes on today's pieces, what each feature must still supply, and what the captures hold.

- **Basis:** read at `43b22d40`. `src/cells/legacy` there is the captures' `76a498ae` byte for byte (M: the `git diff` is
  empty), so its line numbers hold for both. Legacy paths below start at `src/cells/legacy/`, live ones at `src/cells/`.
- **Marks:** (M) measured on 25 November, (D) my own arithmetic or inference, not run. Everything else is read.
- **Nothing on the branch needs the old core while this is written** (D). Main, the pre-cleanup tag and the captures hold
  it, and no canonical world reads it.

### 14.1 What the reading found

1. **NCX needs no engine feature.** Rows B2 and I8 said that the transporter kind's population axis refuses a mode that
   moves charge. That was wrong, and both are corrected. The check sums valence times count over the rows at both
   ends (`kinds/transporter.py:1336–1339`), so it refuses a mode that creates charge. It gives 0 for 3 Na : 1 Ca, and 0
   for the hosted `electrogenic_nucleotide_exchange@1`, which moves one charge per cycle (M).
2. **The calcium-gated opening of the store blocks all four calcium clusters, not the IP3 one alone.** Legacy's release
   reads cytosolic Ca at every stage (`models/er_calcium.py:178–191`), and the IP3 factor multiplies it
   (`models/ip3_calcium.py:80–91`). They are one mechanism: a factor of cell rows, read at the stage, on one route. One
   owner should take it. I suggest E for the factor source and D for the route it multiplies.
3. **A trace Ca row cannot be buffered while @3's own routes carry it.** `local_species_reactions@1` refuses a species
   with an @3 membrane, junction or channel permeability (`operators/species_common.py:167–200`), except a counter-ion
   with a margin of 100 (`:204`). Cytosolic Ca's margin is about 3.7 on the plasma patch, 10.5 on the store's and
   1.3 on the junction (D). So Ca's leaks and its junction route go to the passive-routes kind, and Cav1.2 as an @3
   channel population would make Ca unbufferable. G-1 therefore owes more than a valence entry (14.3).
4. **The worlds are closed:** one gauge, no held bath. Compartment refusal 6 wants a held bath in the owner's component
   (`operators/compartments.py:513–519`). Here the gauge `local` is in the component and is the solver's
   representative (`numerics/surface_field.py:302`), so a store is a free node. `docs/CLOSED_COMPARTMENT_DESIGN.md`
   §3.5 names this door. Putting in a bath instead would change the model and void the global ion balance.
5. **Four consumers need no new ionic piece:** the JUPITER world, the cluster base, the assembly cell and the
   integrated ensemble's world. They are closed `resolved_pump_tissue@3` worlds, on RK4 at up to 25 µs, or on IMEX.
6. **The calcium worlds keep their equations and change integrator.** Kinds, the reactions operator and routes at a
   compartment all refuse RK4, so a monolithic fourth-order RK4 becomes IMEX with Strang halves, second order. The
   bitwise check set can pin legacy only, never the re-expression.
7. **G-7 is one-way.** The ionic side never reaches the pool. So the pool half is the live
   `finite_bond_assembly@1` and is comparable bitwise, and an assembly world can be written today as a live pool run
   whose availability path is the ionic world's `channel_controls` schedule (14.3).
8. **One used world had no capture, and has one now:** the integrated ensemble's `finite_extracellular@3`
   (`configs/junction_finite_cluster.json`), captured at the pre-cleanup tag as the second set (14.4).

### 14.2 The consumers

All nested worlds have Na, K and Cl; the calcium ones add Ca (z = 2) and the buffer species. "Faces" is
`logmean_electrodiffusion@1`, the same law and the same closure (no net face current into any capacitor component).

| Consumer | Canonical form | Needs | Equations | Integrator |
|---|---|---|---|---|
| JUPITER world: `spatial_extracellular@2`, `configs/spatial_kinetic_cluster.json`, both arms | `resolved_pump_tissue@3`: 2 cells, outside nodes `local` (gauge), `near`, `far`, 3 faces, 1 junction (`junction_voltage_relaxation@1`), the Na/K pump on maintained reservoirs, Kv1.5, constant-field leaks. GPU stands (`ionic_worlds@1` admits @3) | nothing | same | RK4 at ≤ 25 µs (Kv1.5's bound, `laws/channels/kv1p5_mh.py:37`; the check itself runs 25 µs), or IMEX at any of the captured steps |
| The cluster base inside `assembly_regulated_cluster@1` | the same world | G-7 | same | as above |
| `assembly_regulated_cell@1`: one cell, `finite_extracellular@2`, one Kv1.5 channel | @3 with one cell and one finite outside node as the gauge | G-7 | same | as above |
| Integrated ensemble's world: `finite_extracellular@3`, 7 cells, 12 junctions, no pump, leak or channel | @3 with one finite outside node as the gauge; its junction availability schedule is @3's own | nothing; captured at the pre-cleanup tag (14.4) | same | RK4 at its 100 µs: no gated channel, and the junction rate is about 23 per second (D), far inside `GATE_STEP_BOUND` 0.125 |
| `spatial_calcium@1` | `resolved_pump_composite@1` over @3: one store per cell as a `cell_owned_compartments@1` node; Ca's plasma leak, store leak and junction route as `passive_constant_field_permeation@1`; K's store leak as @3's own permeability; buffers in cytosol and store by `local_species_reactions@1`'s passive law, the same kernel | G-4; G-5's Ca factor | same | IMEX, Strang halves |
| `spatial_calcium@2` | the above, with @3's calcium pump on the plasma patch (`ca_atp_mass_action_positive@1`, B1) and NCX | + an NCX law module | same. B1 is a re-parameterisation: ΔG0 = −37,000 + RT ln 1000 = −19,875.97 J/mol at 298.15 K (M) | IMEX |
| `spatial_calcium@3` | + Cav1.2 | + G-1 | same | IMEX |
| `spatial_calcium@4` | + free IP3 (z = −3), its neutral buffer and the bound form (z = −3), one more reaction | + G-5's IP3 factor | same | IMEX |
| The four assembly-regulated calcium clusters | each of the above with two pools per world | G-7 | same | IMEX |
| CPU command lines `assembly-cell`, `assembly-cluster` (`__main__.py:22–28`) | `cells run`, `cells windowed`, `cells batch` on the composite definitions, with G-7's operator or with schedules from the pool | G-7 | | |
| Ensemble kinds `assembly_cell_ensemble@1`, `assembly_cluster_ensemble@1` (`ensemble/families.py:20–26`) | an `EnsembleAdapter` on the new family's row of the model table, which the protocol already allows (`families.py:29–80`). The two kind names are in `TODAY`, which an adapter may not take (`:70`), so one owner must remove them | G-7; parked on the GPU (`worker.py:95`) | | |
| `ionic_ensemble@1` | stays. Its list of admitted simulations (`ensemble/ionic.py:144–264`) shrinks to `resolved_tissue@1`, `@2` and the live pump families | nothing | | |

`assembly_ensemble@1` and `finite_bond_ensemble@1` are live code and stay as they are.

### 14.3 What each feature must supply

#### NCX: a law module, no engine change

- **Legacy:** the kernel is live, `laws/reactions/plasma_calcium.py:34` (`exchange_rates`). Its use is legacy's
  `models/plasma_calcium.py:124–152` (rates, the two selectors), 155–176 (rhs and heat), 179–196 (domain: |x| ≤ 80,
  |V| ≤ 0.15 V), 199–228 (step bound).
- **Equations:** per cycle 3 Na in and 1 Ca out. With u = FV/RT and V inside minus outside,
  D = (1 + (Ni/Kn)³ + (No/Kn)³)(1 + Ci/Kc + Co/Kc), J = k a [(No/Kn)³(Ci/Kc)e^(−u/2) − (Ni/Kn)³(Co/Kc)e^(u/2)]/D in fmol
  cycles/s. Kn 20 mM, Kc 0.001 mM, k 0.002 and 0.0028 fmol/s. Synthetic.
- **Canonical:** J = k a S(1 − e^x) with S the forward term and x = 3 ln(Ni/No) + ln(Co/Ci) + u. The monomial form
  carries S exactly: orders Na@P 3 and Ca@N 1, zeta −1/2, two factors of power 1, `Scaled` constants Kn^−3 and Kc^−1
  (`laws/cycles/forms.py:222, 249`), activities against 1 M. A pure exchange has no standard part, so it needs no
  registry potential (`kinds/transporter.py:1489–1498`). Its cycles are `plasma_exchange_cycles`.
- **Known gap, not a blocker here:** the kind's material term does not bound a charged row that crosses
  (`kinds/transporter.py:2240–2250`). This world's slope is about 4 per second (D).

#### G-1: Cav1.2 on calcium

- **Legacy:** `models/gated_calcium.py:72–86` (rates and flux), 93–113 (rhs), 116–134 (domain −0.120 to 0.060 V, gates in
  [0, 1]), 137–146 and 155–165 (step bounds). The gate kernel is live, `laws/channels/calcium_gates.py:15, 35`.
- **Equations:** m and h per membrane, from (0.2, 0.7); target and tau of V only, with the kernel's own −10 mV shift and
  no temperature term; opening m²h; flux GHK at z = 2 with P = P_max × abundance × availability × opening. P_max 2e-6
  m/s, abundance 0.5 and 0.6, area 3e-10 and 3.6e-10 m². State: two gates, transferred fmol and heat per membrane.
- **Must supply:**
  - (a) Ca in @3's channel valence table (`definitions/surface_pump_v3_spec.py:169`; refusal 327–329);
  - (b) the law as a `ChannelLaw` module, two gates as every gated law has;
  - (c) a per-stage material bound for a trace row through a channel, which @3 lacks (its channel term is the charge
    slope, `models/surface_pump_v3.py:3644–3648`);
  - (d) a way for a channel-carried Ca to be buffered (14.1, finding 3).
- **Another form to weigh (D):** the gates as a factor source of the routing door on a `passive_constant_field_permeation@1`
  Ca route. That law already has the charge and the material term, so (a), (c) and (d) fall away, and the gating becomes a
  kind's state. The choice is D's.
- The live module's text names BETSE and calls the shift native. It needs neutral words when it is registered.

#### G-4: the store

- **Legacy:** `models/er_calcium.py:115–117` (capacitance, fixed charge), 146–149 (voltage), 152–192 (potentials, leak, pump,
  release), 195–210 (rhs and heat), 213–240 (domain), 243–291 (loss bound), 301–307 (steps ≤ 50 µs, h × loss ≤ 0.25),
  310–326 (energy). `models/spatial_calcium.py:91–116` (initial charge), 145–155 (free cytosol), 164–189 (rhs: the ionic
  influx enters the store's cytosol), 192–196 (ownership), 247–290 (energy). Chemistry:
  `models/compartment_reactions.py:114–134`.
- **State:** per store, amounts of 7 species (10 in the IP3 world) in cytosol and store, reaction extents and heat, and
  passive, pump and release ledgers.
- **Equations:** V_ER = V0 + (F/C) Σ z Δn_ER, store minus cytosol, V0 = 0, C 1e-11 and 1.4e-11 F (areas 1e-9 and 1.4e-9 m²
  at 0.01 F/m²). GHK leak per species: P_Ca 1e-8 and P_K 1e-7 m/s, the rest 0. Pump: one Ca in per ATP, J = k × availability × Sat_Ca × Sat_ATP × (1 − e^x),
  x = [ΔG + RT ln(Ca_ER/Ca_cyt) + 2F V_ER]/RT, k 0.003 and 0.0042 fmol/s, K_Ca 0.001 and K_ATP 0.5 mM, 1.5, 0.1 and 0.1 mM ATP, ADP and Pi, ΔG0 −37,000 J/mol as a
  numeric-mM quotient. Release: GHK of Ca with P 1e-7 m/s × the factors (G-5). Volumes 0.05 and 0.07 pL. Buffers: Ca + B =
  CaB (k_f 1000/s, Δμ° −6.9078 RT), Ca + CaB = Ca2B (100/s); B −2, CaB 0, Ca2B +2.
- **What today's pieces give:** the node and its capacitor (V_b = φ_owner − φ_store = −V_ER; the sign flips), the K leak, the
  Ca leak and the release as two routes of `passive_constant_field_permeation@1` on the bounding patch, whose law holds both
  step terms (`laws/routes/constant_field_permeation.py:158–159`), so refusal 4 admits them; buffers by the same kernel
  (`laws/reactions/mass_action.py:6`), each conserving charge.
- **Must supply:**
  - (a) refusal 6 for a component that holds the gauge (14.1, finding 4);
  - (b) the pump on the bounding patch. @3's calcium pump is the same law with V = V_b
    (`laws/reactions/plasma_calcium.py:29` calls `er_calcium.pump_rates` with −V), but refusal 4 refuses it there
    (`operators/compartments.py:358–368`): its slope is in no per-stage term. A Ca-ATPase cycle law on the transporter
    kind, with a `stage_term`, is the other form. No cycle law declares one today except the proton pump;
  - (c) the release route's factor list, whose source is G-5's.
- **Steps (D):** the K leak relaxes the store at about 5,260 per second, so dt × rate is 0.066 at 12.5 µs.

#### G-5: the factors that open a route

- **Legacy:** `laws/reactions/er_calcium.py:53` (live): f_Ca = 1/(1 + (Ka/Ca)^na) × 1/(1 + (Ca/Ki)^ni), Ka 0.001 and Ki 0.02
  mM, na = ni = 2. `processes/ip3_release.py:8–13`: f_IP3 = 1/(1 + (K/[IP3])^n), K 0.00015 mM, n 2, 0 at zero ligand,
  from the free IP3 amount over the cytosol volume (`models/ip3_calcium.py:73–77`). Both multiply the release
  permeability, at the stage.
- **No state, no flux of its own, no ledger.** The log-space expression is `laws/reactions/hill_factors.py`'s;
  the exact zero at zero ligand is legacy's own.
- **Must supply:** a factor source that reads cell rows at the stage, Ca (+2) and IP3 (−3) included. `kinds/ph_condition.py` is
  the pattern: `factor_sources` and `factors(read, p)`. The sink exists: a passive route's `factors` list.
- **What does not serve:** `species_regulated_availability@1` targets junctions and channels only
  (`operators/species_regulated_availability.py:159, 553–556`) and refuses a charged instantaneous source (`:748–753`). A
  held factor or a two-state fraction would change the model.
- **For E to settle:** the capacitor sums are exact on the CPU for valence magnitudes 0, 1, 2, 4 and 8
  (`models/surface_tissue.py:376–381`), and IP3 is −3. No world here has an electrode or a held node, so the electrode ledger
  that note is about is zero (D).

#### G-7: assembly sets a channel's availability

- **Legacy:** `assembly_cell/kernel.py:23–26` (the law), 29–55 (the segment), `assembly_cluster/kernel.py:15–17, 20–81`, and
  `assembly_cluster/controls.py:22–29`. Pool code: live, `assembly_pool/kernel.py:106–172`.
- **Law:** a cell's channel availability is `active_availability` (1) if popcount(bonds) ≥ popcount(occupied), else
  `inactive_availability` (0). It multiplies that cell's channel schedule (`controls.py:29`), so the Kv1.5 channels
  only: the Cav1.2, calcium-pump and release controls are separate (`models/gated_calcium.py:93–95`).
- **Pool:** 20-site graph, ring of 5 occupied at start, 50 free trimers, 5e-15 L, k_on 1e7 per M per s, k_off 300 (cluster) or
  10 (cell) per s, k_close 1000 or 100 per s, dissolve 1 per s. Streams: threefry2x32 of (seed, world, event count), seed =
  base + stream id, one stream per cell (`assembly/kernel.py:83–94`).
- **Clock:** the ionic step is split at the union of every pool's event times and the schedule changes; each segment uses
  the availability before its event (`assembly_cluster/kernel.py:44–60`). The pool never reads the ionic side.
- **Written today, no operator (D):** run the live pool for each cell and world, read its event path, and give the ionic
  world the same path as a `channel_controls` schedule per channel. An off-grid change splits the step there
  (`execution/grid.py:3–6`), the same segmentation. A near-miss is refused (`:55`). It qualifies on RK4 for the cell and the base.
- **As an operator it must keep:** the event times as they fall, not rounded to steps. The contract's operator times must lie
  on the clock's grid (`models/pump_composite.py:2102`), so an event operator needs its own clock or a split, as
  `integer_unit_population@1` does.
- **Check for E:** the path of an operator against the live pool's, bitwise, on the captured seeds.

### 14.4 What the science captures hold

Set `science-76a498ae`, 90 jobs, all ok (M: EXIT 0). Ionic worlds at h, h/2, h/4, run by the windowed runner; a job is
`runs/<world>-<step>/window-NNNN.npz`, 256 steps each, with `times`, `history.*` (one row per accepted step, so 257 in a full
window), `observations.*`, `diagnostics.*`, `final.*`. Array names and shapes were read (M); no value was.

| Captured world | Steps at h, h/2, h/4 | dt at h | Arrays |
|---|---|---|---|
| `{spatial,plasma,gated,ip3}_calcium` | 1600, 3200, 6400 | 12.5 µs | `amount_increment` [4 species, 3 cell slots], `chemical_amount_increment` [2 stores, 7 or 10 species, 3 compartment slots], gates, `calcium_gate` [2, 4] (gated, ip3), junction, faces, the transfer and heat ledgers, `plasma_*` (from plasma on), observation `er_voltage_V`, `plasma_voltage_V`, `cytosol_amount_fmol`, `extracellular_potential_V`, `ip3_*` |
| `jupiter_baseline`, `jupiter_pump_release` | 200, 400, 800 | 100 µs | one window; the same ionic fields and the JUPITER check's observation fields (fluxes, affinities, currents, powers) |
| `cluster_{spatial,plasma,gated,ip3}_calcium` × 4 seeds | 1600, 3200, 6400 ticks | 12.5 µs | 2 worlds; only `checkpoint/state.npz` at the end (`pool_*`, `ionic_*`, `tick`, `segments`, `availability_exposure_s`) and JSON summaries at 0, 2.5, 5, 10, 15 and 20 ms |
| `cluster_base` × 4 seeds | 400, 800, 1600 | 50 µs | 8 worlds; the same, JSON at 0, 5, 10 and 20 ms |
| `cell` × 4 seeds | 200, 400, 800 | 100 µs | 64 worlds; the final checkpoint only, no JSON |

All end at 0.02 s. Ionic observation times are 0, 7.3e-5, 2.5, 5, 7.5, 10, 15 and 20 ms.

**The second set** is `extra-49529e71` (M: EXIT 0, 3 jobs ok at 11:21:34 UTC on 25 November; the tool `be6136e3`, clean). It was
captured at `49529e71`, the pre-cleanup tag, where `src/cells/legacy` equals `76a498ae`'s (M: an empty `git diff`). It holds
`finite_junction_cluster` at 200, 400 and 800 steps of 100, 50 and 25 µs to 0.02 s, one, two and four windows. The arrays (M): `amount_increment`
[3 species, 7 cells], `extracellular_amount_increment` [3, 1], `junction_gate` [12], `junction_transferred` [3, 12],
`junction_dissipated_energy_pJ` [12], the zero-size gate and channel arrays, and the same observation fields as `finite_extracellular@3` gives.
Its observation times are 0, 3.713 ms, 5, 10, 15 and 20 ms, and 3.713 ms is off the 100 µs grid, so @3 refuses it there (14.5). The config's
own schedule opens and closes the junctions (availability 1, 0.5 from 5 ms, 0 from 10 ms, 1 from 15 ms).

**What the calcium arrays compare to:** `amount_increment` is the whole-cell exchange ledger, so it is not the free
cytosol: take the cytosol and the store from `chemical_amount_increment` (compartment slots 0 and 1; slot 2 is padding) or
`cytosol_amount_fmol`. Outside is `extracellular_amount_increment`. `er_voltage_V` is −V_b. Channel and cell slots past the
declared ones are capacity padding.

### 14.5 For the criteria

- **Same equations, so the template of §8 can apply** to every consumer but the kinds' own plumbing: no re-expression above
  is a changed model, if G-4 keeps the closed world, G-5 is per-stage and B1 keeps the standard state. §8's B1 and NCX
  examples are corrected. A changed model would be a held bath, a held-through-the-step factor, or a store at the
  cytosol's potential.
- **The candidate's order is 2** for the calcium worlds and 4 for RK4 worlds. Its own h, h/2 and h/4 are its own steps.
- **RK4 on @3 needs dt ≤ 25 µs with Kv1.5** (RK4 also needs ≤ 100 µs, `models/surface_tissue.py:520–522`). So of the
  captured steps the JUPITER and cell worlds have one (25 µs, h/4), the base two (25 and 12.5 µs). IMEX takes all.
- **Off-grid observations:** @3 refuses an observation off an accepted boundary, on RK4 and on IMEX
  (`surface_tissue.py:525–532`). The 7.3e-5 s sample is a Hermite interpolant in legacy and has no canonical counterpart.
  Compare on grid points, through `history.*`.
- **Observations are spread over the windows:** a full window holds only the requested times inside it.
- **Assembly jobs have no trajectory.** Compare the final ionic state and the JSON summaries, and the pool arrays bitwise at
  every h (the pool clock does not depend on the ionic step). `segments` counts splits and depends on the step.
- **Ledgers:** legacy's `dissipated_energy_pJ` lumps leak, pump and channel per membrane, and the transport heat lumps per
  store. Compare sums. `pump_cycles`, `plasma_*_cycles`, transfers and faces compare one to one.
- **Conservation** (species balance, charge, the energy ledger) is checked by its own bound, not by the band.

### 14.6 What no planned feature re-expresses

1. Bitwise identity with legacy for any of these worlds.
2. The 100 µs and 50 µs RK4 steps of Kv1.5 worlds, and the sample at 7.3e-5 s (14.5).
3. Running the cell and cluster kinds on a GPU: `ionic_worlds@1` does not admit the composite, and the worker is GPU only.
   Their queue on a CPU is `cells batch`, not `cells ensemble run`, unless the runner changes.
4. Legacy's observers: the derived readouts (`er_voltage_V`, `ip3_release_fraction`, and the JUPITER check's fluxes) exist as
   formulas, not as legacy's cubic-interpolant proofs that every step stays in the domain.
5. Old checkpoints of these worlds cannot be resumed. The pre-cleanup tag and the captures keep them.
6. The assembly clusters' trajectories: not captured, so a difference between endpoints has no path to point at.

### 14.7 The final removal list, and what D211 keeps (D386)

**The list** (`validation/legacy_port/removal_list.tsv`, branch `legacy-removal-list`): 1,534 files go, and 165 more with the optional batch, which the user approved on 25 November;
245 files are edited, 9 tests are retargeted, 11 files would retire in a second commit, and 184 files are kept by name; 35 more rows are names: 16 leave files that stay in the
deletion's own commit, four moved first, five are dead after the core edits and ten stay. Every `goes_or_cut` row has a verdict: a reader read 462 files,
and the 35 it asked about are resolved here. A second reader has read the list, the script and the batch (verdict: safe with named corrections, all in).
- **Two commits,** made from the list by `make_deletion.py` (both in `validation/legacy_port/`). The first is the deletion, on one branch that takes the place of 9b0debe6. The second, `--retirements`, removes the
  eleven files whose row says `retires`, after the user's word and the campaign's results (the lead's ruling, 25 November: L67's row is the only one of a reference that Part 2's judge may use beside a miss). Each commit's message names
  the head and the list's revision. `--branch` refuses while a row is open before that commit (none is before the deletion; 16 rows wait for the user before the second), while a row on which the user was asked lacks the approval, and while the list is not committed.
  The JUPITER check's model part gates neither: its rebuild is the user's choice after the cleanup.
  It is prepared, not merged: `legacy-deletion` 3747bb3e is `legacy-cleanup` 61ebb75f and the script's one commit, which removes 1,693 files (six of the 1,699 are gone already) and stops no import but those of the 8 files that would retire, with `lean/` and `visualizer/` read, and the two rehearsals' drivers', which run the frozen snapshot. `legacy-guard-list` 9818e4b8 follows it: three readers of the captures that the campaign's merges added join the bypass guard's read-only group, without which the guard fails on them on the deletion's tree. `legacy-open-retirements` 34e2e8c1 holds the second commit on top of both.
  In the same commit: one guard's exemption list; 302 rows of `tests/test_tiers.json` (114, 46 and 142), which the gate refuses without their files; the exchange kernel and the names that only legacy uses in
  `laws/reactions/plasma_calcium.py`, `laws/reactions/er_calcium.py` (`release_open` among them, by use) and `laws/channels/calcium_gates.py`, with five docstrings; the words of three library pages; and notes on 31 pages.
  `pump_rates`, `PumpParameters`, `chemical_drive` and the two voltage and affinity bounds stay: live laws run them. The second commit: 11 files, one more entry of the guard's list, and 8 tier rows (2 of tier 1, 6 of tier 3), with the prepared rows of six staying files.
- **The fingerprints' definitions** (the tool's own enumeration): 129 in 125 files leave, of 194 in `configs/`, `examples/` and `validation/`; the batch holds none, and the second commit none. `removed_definitions.txt`
  lists them, since the comparison takes exact lists of what one side lacks (306edd69). An earlier count said 127 in 123. The tag has 173, 36165b70 had 177 and the last heads 194: `configs/batch_reaction_transport.json` and its branch brought four, and `validation/ensemble_reexpression/format_sample` 17, whose numbers and strings are placeholders (the tool
  records a refusal at parse for each). The list of additions is the lead's, made again for the final head. 65 are left after the deletion, 44 of them the tag's.
- **D196's safeguard.** `law_reference_checks.tsv` has one row for each of 134 laws and kernels (71 registered laws, 44 of the catalogues, 19 kernels that live models import): its declared
  test (44 of the 71 have one; all 44 are collected after the deletion), the reference rows that check its kernel afterwards, with and without the batch, and those that
  go. An import graph had seen only `mass_action.py`; Kv1.5 and `junction_voltage_relaxation@1` had kept importers and lost their only direct check, and the first table held two standards and missed a fourth, `edge_flux`. All four have a row
  beside the law now (`legacy-kernel-rows`), with planted errors that fail it. `bernoulli` loses its one row of hand values; `test_sodium_catalog.py::test_analytic_singular_limits_and_adjacent_binary_inputs` evaluates it at and near zero (16 arguments exactly zero, 64 below 1e-4) and
  sees a planted value and a planted slope. The table was read again for every file that would retire: two of their kernels are live (`er_calcium`'s `pump_rates` and `chemical_drive`), and both are held through `ca_atp_mass_action_positive@1` and `pump_rates` of the plasma module.
  `pump_rates` itself, off its stall by 1e-13 or its free energy off by 1e-6 J/mol, fails one staying row only, on the BETSE side (`test_betse_emulator_laws.py`; the fresh reader): that claim leaves with that file, and its row says so.
- **14 reference files stay** whose last test goes (the second reader's 13, and `validation/organelles/betse_mitochondria_reference.py`): old native probes and references that stay, and that no test runs at the tag either, import them, or they are BETSE-side references for
  kinetics with no live version, the four of the network among them (the lead: they were on no row when the user said yes to B1).
- **The three live parity files keep their BETSE runs.** They now import `validation/betse/native_hooks.py`, and 19 REF-era modules go
  (the lead's choice (C)). Measured on the tree without what goes, on the light CPUs: 16, 38 and 25 rows pass, each with one skip, and all 64 native
  captures equal the saved ones bit for bit (395 million array scalars).
- **Four parity files could not start their run,** at the tag or before it: three stop in the check of the source they are bound to, which changed on
  11 October 2026, and one is skipped (D131). 70 rows that could only error leave; the 55 that pass stay.
- **The fixed point** (measured at thirteen heads, the last 61ebb75f): on the head tree without what goes, the only remaining files with
  an import that does not resolve are the 8 files that would retire and the two rehearsals' drivers, and the only other mentions of a going path in code are the rename's tool and tables (four pins and four reviewed lines of its choices name seven files of the batch), one guard's exemption list, two
  validation scripts that would go, the words of three parity files and four of the viewer's files. Records name them too: 155 reports, 56 validation protocols and source maps,
  and 53 documents beside `PROGRESS.md`. Run-time imports and path loads were read one by one (75 sites).
- **Test IDs,** by collecting the prepared branches (m): after the deletion 11,140 collect, and 8 files fail to, all of which would retire. Of 21,927, 11,531 no longer collect: 10,956 go with their files, 261 leave files that stay, 138 are of the two files that the pump and symports work rewrote, and 176 are in the 8 files that fail to import; 744 are new (128 of them since abd78068, in the campaign's tests).
  After the second commit, 11,131 collect with no error: 11,545 of the base and 749 new (14 more leave and 5 are new: the parked family's parameter leaves the names of three rows).
  The 17 files that tested used capabilities on worlds that go held 372: 77 are rewritten, 32 use nothing that goes or need one word or number changed (four of them kept after the fresh reader's report: L94, L109, L110 and L112), 70 had left with the pump and symports work, and 193 would retire
  (`open_rows.tsv`, one line per function: its claim, what carries it, the plant that shows it and its outcome, the fresh reader's plants, and what is not carried; the classes are on the page, section 1). 176 of the 193 are in the 8 files that fail to import on the cleanup branch already. For every
  carried line a planted fault is recorded by the row's builder, or made here (`carrier_plants.tsv`, by where each row crashed), and the fresh reader's finer plants are beside them (`carrier_plants_reader.tsv`); what no live row holds is named. Three plants found a live row that missed them, and the rows are strengthened. A row now holds that what is closed carries nothing (a closed patch's flux, a closed junction, a channel of abundance 0), which no staying row held (the fresh reader).
  Nothing in `src/cells` is reached by retiring tests alone, no data file loses its last reader, and
  two of the five calcium references do (`reference_gated_calcium.py`, `reference_ip3_calcium.py`; they stay for the campaign).
- **What waits for the user:** those 193, in seven classes, and the JUPITER check's model part, rebuilt on the re-expressed JUPITER world (D374 lists that check as used; a refusal by name is not a re-expression): about half a day (e), the user's choice after the cleanup.

**D211.** 44 of its 47 "port as is" laws keep their kernel, its reference and a kernel-level test:

| Laws | Surviving test of the kernel |
|---|---|
| Kv2, Kv3, K_fast | `test_potassium_catalog.py` (146 rows) |
| Nav1.3, the rat Navs, Nav1.6 | `test_sodium_catalog.py` (115) |
| CaV1.2 to CaV3.3 | `test_cav_channels.py` (4); CaV1.2, registered on @3 as `cav1p2_m2h@1`, also in `test_kv1_channel_laws.py` (units, shift, powers, both directions and heat) |
| Ca_L2, Ca_L3, Cav_G | `test_calcium_catalog_extra.py` (82) |
| Morris-Lecar | `test_morris_lecar_channels.py` (140) |
| Calcium-activated K | `test_calcium_activated_potassium.py` (103) |
| HCN1, HCN2, HCN4 | `test_channel_law_kernels.py`: the rows moved from `test_surface_hcn.py`; only the stage check of `resolved_tissue@8` would have been left |
| HCN leak and the two cAMP laws | `test_channel_law_kernels.py`: new rows; none would have been left |
| Kv1.1 to Kv1.4, Kv1.6 | `test_kv1_channel_laws.py` (registered on @3) |

The Na/Ca exchanger, the store's pump, NKCC and the generic symport are cycle laws now, each with an independent reference and planted errors in
`test_cycle_kind.py`, and the release's factor is `hill_product_factor@1` (`test_hill_factors.py`); what each still waits for is in
`docs/CORE_LAWS_ROADMAP.md`'s table. Two further pairs of kernel rows moved with them, Kv1.5 with Kir2.1 and Nav1.2, because `validation/betse/emulator/network.py` cites them. Nine planted
errors in the kernels each fail at least one of the ten rows. The four tables of `resolved_tissue@9` to `@12` hold no kernel and no constant
but code ranges and neutral fill values, and nothing that stays imports them, so they go; the rename's choice that reads
one of them (`scripts/moves/id-rename-choices.json:186`) needs the law modules' own tables instead.

## Appendix A. The 11 families of D348: closures, physics, sources and targets

This is kept from the first version of this plan for the builders. Its route is now §7's. That version's
per-family detail still applies to the families Route A relocates: consumers, neutral target homes, bitwise
world sets and the capture commands, including the assembly families' CPU command line. It is in commit
`87d0406b`, `docs/LEGACY_PORT_PLAN.md` §4 and §5 (`git show 87d0406b:docs/LEGACY_PORT_PLAN.md`).

| # | ID (legacy, frozen) | Spec / parse | Model | Import-time closure in legacy |
|---|---|---|---|---|
| F1 | `resolved_tissue@12` | `definitions/surface_kinetic_spec.py` (live) | `legacy/models/surface_hcn_extra.py` → `surface_cav.py` → live `models/surface_kinetic.py` | 2 modules, 73 lines |
| F2 | `resolved_calcium@11` | `legacy/core/surface_calcium_spec.py` | `legacy/models/surface_calcium_hcn_extra.py` → `surface_calcium.py` | 38 modules, 11,123 lines |
| F3 | `resolved_calcium_energy@5` | `legacy/core/surface_calcium_energy_spec.py` | `legacy/models/surface_calcium_energy_hcn_extra.py` → `surface_calcium_energy.py` | 44, 13,438 |
| F4, F5 | `resolved_open_calcium@1`, `_energy@1` | `legacy/core/surface_open_calcium{,_energy}_spec.py` | `legacy/models/surface_open_calcium{,_energy}.py` → `open_calcium_runtime.py` | 58, about 17,980 |
| F6–F9 | `spatial_calcium@1`–`@4` | `legacy/core/{spatial,plasma,gated,ip3}_calcium_spec.py` | `legacy/models/{spatial,plasma,gated,ip3}_calcium.py` | 26–34, 8,157–9,471 |
| F10 | `assembly_regulated_cell@1` | `legacy/assembly_cell/spec.py` | `legacy/assembly_cell/`, `legacy/ensemble/coupled.py` | 12, 3,300 (+91 at function level) |
| F11 | `assembly_regulated_cluster@1` | `legacy/assembly_cluster/spec.py` | `legacy/assembly_cluster/`, `legacy/ensemble/cluster.py` | 83, 21,567 |

**The union** is 107 modules and 27,414 lines. Pruning the cluster's branches for the `resolved_*`
families would leave about 70 modules and 20,000 lines.

**Nested children:**
- `er_calcium@1` is the store of F2, F3 and F6–F9;
- `spatial_extracellular@2` is the ionic child of F6–F9 and of the cluster's base config;
- `finite_extracellular@2` is the ionic child of F10.

**Physics and sources, in short** (file:line references from the two research reads are in the session
records):
- **F1:** the 56-law catalogue on `models/surface_kinetic.py`. @12 adds `hcn_leak_open@1`, `hcn2_camp_m@1` and
  `hcn4_camp_m@1`, codes 53–55. The law forms come from BETSE 1.5.0's channel classes, cited.
- **F2:** ER stores (capacitor, GHK leak, `er_calcium_pump_positive@1`, `er_calcium_release@1`, buffers);
  PMCA, NCX and Cav1.2 per membrane; the IP3 factor; energy to 1e-9 pJ.
  - Sources: BETSE's `pumpCaATP`, `pumpCaER`, `Cav1p2` and `EndoRetic.channels` (`docs/PLASMA_CALCIUM.md`,
    `docs/ER_CALCIUM.md`).
  - NCX is synthetic; Hilgemann and colleagues (1992) support only its reversal.
- **F3:** finite ATP/ADP/Pi pools (`finite_atp_adp_pi_transformed@1`), regeneration
  (`driven_atp_regeneration_tanh@1`), and finite-fuel PMCA and ER pumps. It is synthetic
  (`docs/FINITE_ENERGY_POOLS.md`).
- **F4, F5:** static open reservoirs and moiety ceilings; no new rate law.
- **F6–F9:** F6 adds one ER store per cell and a whole-cell exchange ledger. F7 adds PMCA and NCX, F8 Cav1.2,
  and F9 the IP3 factor a/(1 + a).
- **F10, F11:** `root_component_has_cycle@1`: the channel is available when popcount(bonds) ≥
  popcount(occupied), and the ionic side never feeds back. The cluster has per-cell pools, a union event
  clock and `lax.map` over worlds.
  - The base capsid model is Asor et al., Nature (2026) (`docs/CAPSID_ASSEMBLY.md`). The coupling is a
    stated hypothesis.

**Proposed IDs, to be named in the rename note:** a re-expressed capability takes the canonical family of
its piece, such as `cells.channel.cav1p2_m2h@1`, `cells.cycle.<ncx law>@1`, an ER-store operator in
`cells.operator.`, or an availability-coupling operator. Under Route A, a relocated core keeps its name
under `cells.model.<name>@<major>` until A-5.

**Live laws these families use without a registry entry,** for the rename's table:
- NCX, Cav1.2, the ER pump and release;
- `maintained_mM_quotient@1`;
- `capacitive_components_current_continuity@1`;
- `gauged_dense_kirchhoff@1`;
- 44 catalogue laws.

**Laws defined inside legacy:** `ip3_er_release@1`, `finite_atp_pmca_positive@1`,
`finite_atp_er_1ca_positive@1`, `finite_atp_adp_pi_transformed@1`, `driven_atp_regeneration_tanh@1`,
`finite_energy_pool@1` and `root_component_has_cycle@1`.
