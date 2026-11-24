# Legacy port plan: everything Cells uses leaves legacy, in canonical forms

**Status: a plan for the morning's review,** reworked after D369 and D374, and corrected after the review
(24 November 2026, night). Nothing in it is built. It was written read-only at main `ce4780d2`.
- **Frozen after the widening below** (24 November), until the dry run reports and the user chooses the route in the
  morning.
- **Line citations are at `ce4780d2`,** with one exception. FR-50's landing (1939563e) moved lines in
  `kinds/transporter.py`, so those are given at main `c9da0fdb`, where the cited refusals still stand.
- By name, no other file cited by line has changed up to `c9da0fdb`. An earlier version of this note said
  that of every cited file, without checking; it was wrong for `transporter.py`.

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
- **`source_decay@1`,** the conftest's world. It is deleted in the batch, and its users are retargeted
  (Q6 (a)).

No registered protocol in force names a legacy model, and the claimed BETSE parity runs on live models.

**The coverage table (§3)** has 51 rows by capability and consumer:
- 40 capability rows;
- 11 rows for the protein inventory's law records that still point into legacy (group I).

Each row is classed as canonical, expressible today, needing an engine feature, or dropped, and states how
firmly it was checked.

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
unsized and unscheduled.

| | A: relocate, then re-express | B: re-express directly | C: prune legacy in place, then re-express |
|---|---|---|---|
| Agent-days, beyond the features | 18–27 | 13–19 | 14–22 |
| Full gates | 5–7 | 4–5 | 4–5, two of them with tier 3 |
| Lane-hours | about 15–20 | about 12–15 | about 13–18 |
| **If a CPU re-expression counts:** legacy lives | until about 9–13.5 agent-days are done; then a relocated copy lives in live `src` for about 22.5–36 more | whole, until about 26–41 are done | at least 58% of its lines leave after about 4–6; the rest lives for about 23.5–38 more |
| **If legacy's core waits for the GPU:** legacy lives | until A-3, but **the copy is open-ended** in live `src` | **whole, open-ended** | **the core is open-ended**; the rest leaves at C-1 |
| In every gate meanwhile (tiers 1+2) | the copy's tests: 28 files, 273 test-seconds | every test that reaches legacy: 137 files, 2,837 test-seconds, about 9 minutes of wall | the core's tests: 28 files, 273 test-seconds, under a minute |
| BETSE-rule risk | moderate to high: code built on BETSE-derived conventions enters live `src/cells`, and part of it is barred as it stands (§7.4) | lowest | low: nothing enters live `src`; the BETSE glue goes at C-1 |

**Recommendation: C,** under either answer.
- **The firm figure is at least 58% of legacy's lines** at its first deletion (up to 61%, if the prune left nothing
  of the dispatch hub, which it cannot). It needs no edit to a kept module apart from the hub. Larger figures, up to
  about 85%, are estimates that rest on further edits (§7).
- It is the only route whose standing cost stays small if no date ever comes. Under an open-ended date, A
  leaves a legacy copy in live `src`, and B leaves every legacy test in every gate.
- **It is the user's D346 choice again:** a partial deletion that keeps what the kept consumers use. D346 kept
  BETSE's part and the ensemble's. D374 retired BETSE's, so C keeps the ensemble's core alone.
- **D348's objection is smaller, but not shown to be 15 edits.** By static evidence there are 15 direct hand
  edits, against its 180 files. Another 50 shared fixture files are held in use by 18 tests that I have not read, so
  their fate is open until C-1's dry run (§7.5).
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

**How it was measured tonight (read-only):**
- **U4:** the rename probe's frozen set (233 files with registration tags or Freeze and Register commits)
  names no legacy model ID. U4 is empty.
- **U3:** a scan of PROGRESS, the plans, the scientific basis and the paper notes (§6). The claimed BETSE
  parity runs on modern models. The calcium ensemble's qualification is claimed in `docs/GPU_ENSEMBLES.md`,
  and the JUPITER runbook runs `spatial_extracellular@2`.
- **U1 and U2:** the static reach and the scope map (§9). Only the dry run below settles U2.

**The dry-run deletion, the definitive measure of U2.** The lead runs it tonight on lane B, after FR-43's gate
(D374). It changes nothing on main. This is its form:
1. `cp -a` the morning's pre-rename snapshot to a scratch tree DRY. Snapshots are immutable, so the dry run
   works on a copy.
2. Run `validation/legacy_port/dry_delete.py DRY`. The script is not yet written. It removes
   `src/cells/legacy/` and `registry/legacy_entry.py`, and replaces every `legacy()` call site with its miss
   branch:
   - `definitions/specs.py:857, 1049`;
   - `registry/models.py:71`;
   - `execution/schedule.py:147`;
   - `__main__.py:220, 237`;
   - `ensemble/families.py`'s `_older` and `ensemble/cli.py:139`.
3. Run tiers 1+2 on lane B, under its lock:
   ```
   scripts/run_detached.sh legacy-dry-tiers 12G --cpus 8-11,24-27 --oom-first -- flock /mnt/workspaces/Cells/locks/gate-cores-8-11.lock /mnt/workspaces/Cells/venv-cpu/bin/python -B DRY/scripts/test_tiers.py run --tiers DRY/tests/test_tiers.json --tier 1 2 --cpus 8,9,10,11,24,25,26,27 --out OUT/tiers12
   ```
   **Cost:** about 42 minutes of the lane. The measured full tiers stage was 2,531 s on 24 November
   (`/mnt/workspaces/Cells/fr51-slot-refusal-20261124/gate-e79cbade/gate.log`). Files that import legacy
   fail at collection, so it is no longer.
4. Tier 3, the same command with `--tier 3`. It is not optional here: all six test files of row A12 are tier 3, so
   tiers 1+2 alone cannot show those uses. The run is estimated at 1–2 hours of a lane. Of its recorded 87,166
   test-seconds, the 204 files that reach legacy mostly fail at collection.
5. Classify every failing file. It is legacy-subject if it imports or names only legacy models; otherwise
   it is a U2 use, reviewed by hand. The list goes to §9's removal list. The passing files' seconds give
   §10's measured saving.

## 3. The coverage table, by capability and consumer

**Classes:**
- **Canonical:** canonical already;
- **Expressible:** expressible today on canonical pieces;
- **Feature:** needs an engine feature, with its gap in §4;
- **Drop:** dropped, listed with what is lost. Each needs the user's OK under the 17 November rule.

"Uses" names only consumers that count under §2. D374 retired the physiology set, so rows that only it used
have no use left.

**Evidence levels.** A wrong "Canonical" is the silent-loss direction, so each row's basis is stated.
- **Read here,** at the cited lines: A1, A4–A6, A9, A12 (each test's parse call), B2's refusal, B3–B5, C2, D9, E1–E3, P1, G1, G3, and
  the refusal sites of §4.
- **By registry name or protocol only:** A2, A7, A8, C1, D3, D4, D6 (the registry dump), and D7, D8 (the
  parity protocols' model IDs).
- **From a research read not repeated here:** A3, A10, A11, B1's standard state, B7, C3, C4, D1, D2, D5,
  E4.
- **Group I:** each record's file was mapped here through the move tables. I7's "Canonical" is by name only.

The builder re-reads every row not read here before the deletion. A row found not canonical moves to
Feature or Drop, and the user is told.

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
| A9 | @3's reference world: the gated catalogue model `resolved_tissue@8` (live `models/surface_kinetic.py`, with the legacy wrapper `legacy/models/surface_catalog.py`) | `tests/unit/test_surface_pump_v3_gates_equivalence.py` and @3's tests through `validation/tissue/surface_pump_v3_fixtures.py:107–129` (U2) | Canonical code, but its dispatch is legacy's | kept for now and moved to an independent validation reference at the end (Q5 (a), D374). Its dispatch moves to the live registry with row A12's |
| A10 | Cell clusters in finite and spatial baths (`finite_extracellular@1`–`@3`, `spatial_extracellular@1`–`@2`) | the JUPITER check (`spatial_extracellular@2`, U3); nested in the calcium ensemble (`spatial_extracellular@2`, `finite_extracellular@2`); the REF-era drivers are not uses | Expressible | the same physics as @3 worlds (constant-field leaks, Kv1.5, the pump, junctions, faces), not bitwise |
| A11 | The oldest families (`bioelectric_cell@1`, `bioelectric_pair@1`, `multispecies_membrane@1`, `voltage_gated_membrane@1`, `physical_ionic_graph@1`, `emt_mirna_pair@1`, `spatial_extracellular@3`) | none; helpers inside the A10 line | Drop | superseded by @3; group H's pointers corrected |
| A12 | Two live tissue models reached only through legacy's dispatch: `resolved_tissue@1` (`models/surface_tissue.py`, `definitions/surface_tissue_spec.py`) and `resolved_tissue@2` (`models/surface_kinetic.py`, `definitions/surface_kinetic_spec.py`) | **@1 (U2):** `test_surface_tissue.py` (parses and runs it) and `test_scalar_tail_reuse.py` (parses it). **@2 (U2):** `test_surface_kinetic.py` (parses it); `test_surface_pump.py:161`, the reference for `resolved_pump_tissue@1`, and `test_vector_windows.py:241`, the ionic simulation that `vmap` refuses, both through `surface_pump_fixtures.reduction`; and `test_rehost_probe.py` through `validation/assays/rehost_probe.py:304–307`, which skips without its saved observation. PROGRESS records that G0 probe (lines 4625–4635) and its plan step 8 cites it (U3). **Both (U1):** `ensemble/ionic.py` admits them as simulations (`:177, 196`). All six test files are tier 3 | Canonical | the code is live. C-1 moves the dispatch to the live registry (Q5 (a), widened; §7.3) |

### B. Calcium

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| B1 | Cytosolic calcium with a plasma-membrane pump (`plasma_calcium_pump_positive@1`) | the calcium ensemble | Canonical | `cells.ca_atp_mass_action_positive@1` on @3: the same kernel at a 1 M standard state, Δg0 − RT ln 1000. Not bitwise |
| B2 | NCX, 3 Na : 1 Ca (`ncx_3na_1ca_symmetric_barrier@1`, a live module, unregistered) | the calcium ensemble (plasma, gated, IP3) | Expressible | a cycle law in the transporter kind's version-1 layout. The population axis refuses a mode that moves charge (`kinds/transporter.py:1336–1339` at `c9da0fdb`). The builder confirms Ca rows |
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
| C3 | ATP-driven, irreversible, regulated and cotransport variants (`resolved_calcium_energy_atp_transport@1`, `_irreversible_transport@1`, `_regulated@1`–`@2`, `_transport@1`, `resolved_cotransport@1`) | none | Canonical in part; Drop the legacy forms | `atp_driven_transporter_mass_action_positive@1`, the cotransport cycle laws, `species_regulated_availability@1`. Their finite-fuel forms wait for G-6 |
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
| E2 | Assembly topology setting channel availability, in one cell and as per-cell pools over a tissue (`assembly_regulated_cell@1`, `assembly_regulated_cluster@1`) | the ensemble runner's kinds (U1); `docs/GPU_ENSEMBLES.md:125–200` (U3); `validation/assembly/qualify_cell.py`; `validation/ensemble/` | Feature | G-7 |
| E3 | GPU ensembles of these worlds (`cells ensemble run`, GPU-only, `ensemble/worker.py:95`) | `docs/GPU_ENSEMBLES.md`; the JUPITER runbook | Feature. Parked if a CPU re-expression counts (§13, Q1) | G-8, unless the ensemble ends on @3 |
| E4 | The ionic wrapper `ionic_worlds@1` (`ensemble/ionic.py`, which admits 98 legacy IDs). Its exercised children are `spatial_extracellular@2` (the JUPITER world) and `finite_extracellular@3` (`configs/junction_finite_cluster.json`, the integrated ensemble's world) | the JUPITER check; `tests/unit/test_integrated_ensemble.py`; `validation/ensemble/integrated_matrix.py`, `spatial_matrix.py` | Expressible | an adapter onto @3 worlds, whose GPU path stands (D336 refuses only the composite). The builder confirms |

### P. BETSE-facing preparation

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| P1 | Tissue-profile selectors and static profiles; mesh binding in BETSE's order; BETSE's grid and bath face conventions; INIT/SIM phase handoff; the `tissue-profiles`, `tissue-geometry`, `tissue-phase` and `excise` command lines | none: D374 retires the physiology set and its helpers. The fourth helper, `emulator/spatial_spec.py`, stays with the parity ladder (row G3) | Drop (and not allowed in `src` in any case, §5) | physics inside it, such as the Bernoulli-fitted face law and cutting, becomes a request if a kept consumer needs it |

### G. Small inline families

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| G1 | `source_decay@1`, the conftest's synthetic world | 9 infrastructure tests (U2): `tests/integration/test_cli.py`, `test_replay.py`; `tests/unit/test_continuity_gpu.py`, `test_continuity_loaders.py`, `test_numerical_refinement.py`, `test_numerics.py`, `test_specs.py`, `test_stationary_analysis.py`, `test_windows.py` | Expressible | retarget to `reaction_transport@1` or a minimal composite (Q6 (a), D374) |
| G2 | `emt_mirna@1`, `passive_pair@1` | their own tests; pointed at by `docs/PAPER_REVIEW_GZMK_AGEING.md:139` | Drop | — |
| G3 | The `identifier` check, imported from `legacy/core/multispecies_spec.py` | the BETSE-order emulator and ten tests (§6), the parity ladder's tooling (U3) | Canonical | the same function, re-exported from `definitions/spec_values.py:23–31`: retarget the import |

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
- `docs/library/DECLARATIONS_FORMAT.md:349`, the manifest's legacy list.

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

**The count.** 11 still point into legacy. On 17 November there were 13, over U34, U36–U41 and U43–U47.
U36's records are all live now, and U38 shares U37's record.

**The D211 mark** is from the law-port table, `visualizer/data/laws/law_port.json`. The mapping was read here;
it is in `inventory_records_now.json`.

| # | Record (unit) | Legacy file | D211 mark | Uses | Class | Canonical piece, and what the unit keeps |
|---|---|---|---|---|---|---|
| I1 | `neutral_mobile_leak@1` (U34, always-open leaks) | `legacy/core/surface_redistribution_spec.py` | — | none (row D5) | Drop | U34 keeps its six live leak laws |
| I2 | The source pair's junction flux (U37, Cx45/Cx45; U38, Cx40/Cx37) | `legacy/processes/source_electrochemistry.py` | not a port | none. It carries BITSEY's reference conventions, admitted by D149 only through `emt_mirna_pair@1` (`source_electrochemistry.py:1–9`) | Drop | U37 and U38 are left with no law record; the viewer's inventory is updated |
| I3 | The source pair's pump term (U39, Na/K-ATPase) | the same file | — | none | Drop | U39 keeps `nak_atp_mass_action_positive@1` and `nak_atp_affinity_tanh@1` |
| I4 | `finite_atp_pmca_positive@1` (U40, PMCA) | `legacy/processes/finite_calcium_pumps.py` | — | none (row C2) | Drop, lost until G-6 | U40 keeps `plasma_calcium_pump_positive@1` and `ca_atp_mass_action_positive@1` |
| I5 | `finite_atp_er_1ca_positive@1` (U41, SERCA family) | the same file | fold into an owner's planned law | none (row C2) | Drop, lost until G-6. D211 folds it into the cardiac lane | U41 keeps `er_calcium_pump_positive@1`, re-expressed with G-4 |
| I6 | `ip3_er_release@1` (U43, IP3R-like release) | `legacy/processes/ip3_release.py` | fold into an owner's planned law | the calcium ensemble's IP3 cluster (row B5) | Feature | G-5, coordinated with the cardiac lane's release law (D211) |
| I7 | `kcc_reversible_tanh@1` (U44, KCC) | `legacy/processes/cotransport.py` | — | none | Canonical; Drop the legacy form | `k_anion_symport_mass_action@1` (`laws/routes/k_anion_symport.py`) |
| I8 | `nkcc_reversible_tanh@1` (U45, NKCC) | the same file | port as is | D211's port programme | Expressible | an electroneutral cycle law on the transporter kind, whose population axis admits charge-neutral modes (`kinds/transporter.py:1336–1339` at `c9da0fdb`). U45 has no other record |
| I9 | `electroneutral_symport_reversible_tanh@1` (U46, a configured transporter) | the same file | port as is | D211's port programme | Expressible | as I8. The law is manufactured, with no outside source (`cotransport.py:1`) |
| I10 | `cell_zone_transporter@1` (U46) | `legacy/processes/cell_zone_transport.py` | port as is | D211's port programme | Feature, or Drop. Not portable "as is": its equations are "those of the BETSE v1.5.0 transporter network", with that network's conventions (`cell_zone_transport.py:1–10`) | a neutral re-expression, the user's call beside D211 |
| I11 | `mitochondrial_passive_continuous_si@1` (U47, inner-membrane permeability) | `legacy/processes/mitochondrial_passive.py` | not a port | none (row C4) | Drop | U47 is left with no law record. The nearest canonical pieces are the transporter kind's mitochondrial laws and the proton-leak routes |

**Tally, 51 rows, after D374 and the widening of Q5 (a):**
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
  - So do ten tests: `test_betse_charge_precision.py`, `test_betse_gate_roundoff.py`,
    `test_betse_junction_runtime.py`, `test_betse_spatial_junction*.py` (2), `test_betse_spatial_runtime.py`,
    `test_channel_compensation_design.py`, `test_cue_separation_diagnostic.py`, `test_local_channel_design.py`
    and `test_unstimulated_diagnostic.py`.
  - This is row G3: a one-line retarget, in validation.
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
| **(a)** legacy | until A-3: 9–13.5 agent-days | whole, until the deletion: 26–41 | at least 58% of its lines leave after 4–6 (C-0, C-1); the core lives for 23.5–38 more |
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
  - Every legacy test stays in every gate: 292 files reach legacy by import, 137 of them in tiers 1+2. That is
    2,837 of the 13,577 test-seconds, about 8.8 minutes of a gate's wall, plus dispatch misses that load the
    hub.
  - The physiology stack's tests and BETSE glue stay too, since B keeps D348's single deletion.
  - Live changes keep breaking tests that no lane owns.
- **To C:** the core stays in the holding area, with its tests and a pruned hub: 42 files, 28 of them in tiers
  1+2, 273 test-seconds, about 0.8 minutes of wall. Nothing else is left. It is the only route whose standing
  cost stays small if no date ever comes, and nothing BETSE-derived enters live `src`.

### 7.3 Common to every route

- **The deletion batch** (D374), with its dry run (§2), a tag and a removal list the user approves:
  - the physiology stack and the 18 REF-era drivers with their tests, records kept;
  - Q5 (a), widened by the lead: the dispatch of `resolved_tissue@1`, `@2` and `@8` moves into the live registry,
    and @3's checks keep @8 for now.
    - **What moves:** parse (`legacy/registration.py:1196–1211` and `:1444–1447`), `model_for` (`:794–795`,
      `:806–807`, `:832–833`) and `to_dict` (`:1946–1949`, `:1977–1980`). The hub has no `control_values` entry for
      them. The model table would gain their rows, for the builder to confirm, and
      `ensemble/ionic.py`'s admitted rows for the three stay (`:177, 196, 202`). It is small, an estimated half agent-day inside C-1's range.
    - **The entries match by exact type** (`type(spec) is X`). `SurfaceKineticModel` derives from
      `SurfaceTissueModel` (`definitions/surface_kinetic_spec.py:114`), and legacy classes that stay in C's core
      derive from one or the other: `SurfaceCalciumModel` (`legacy/core/surface_calcium_spec.py:41`), `SurfaceWaterModel`
      (`legacy/core/surface_water_spec.py:40`) and `SurfaceRedistributionModel`
      (`legacy/core/surface_redistribution_spec.py:40`). An `isinstance` check before the legacy miss would catch
      them. This is a consequence for the lead to confirm: the general ruling on dispatch still waits (§13);
  - Q6 (a): the three inline families go, and the conftest's 9 users point at a live world;
  - the parity ladder's `identifier` import made direct (row G3);
  - group H's document pointers corrected.
- **The ensemble's CPU re-expression,** on the four features: about 8–12 agent-days, judged against §8's
  science captures by each registration's derived tolerance.
- **The four features and NCX's registration:** 13.5–22 agent-days, rough, priced in §4 and not repeated below.
- **G-8** is apart, unpriced, and only under answer (b) or for the parked path.
- **The science captures,** from the pre-rename snapshot: about 0.3 agent-days and about 1.5 lane-hours.
- **The rename lands first,** with legacy re-spelled (D371), and no retirement comes before its move (D374).

### 7.4 Routes A and B

**Route A: relocate the used cores as a temporary bitwise copy, then re-express.**

| Step | Content | Agent-days | Gates and lanes |
|---|---|---|---|
| A-0 | Captures: bitwise windows for the cores, and the science set | 0.5 | about 2 lane-hours |
| A-1 | The batch's live-side items: the `resolved_tissue@1`, `@2` and `@8` dispatch (§7.3), with @8's wrapper `legacy/models/surface_catalog.py` folded into live code; the conftest; the `identifier` import; the JUPITER and integrated-ensemble worlds onto @3 (rows A10, E4) | 2.5–4 | one full gate |
| A-2 | Relocate the used cores under neutral names, with `scripts/source_moves.py`: one map, its rewriter and verifier, 112 modules (§7.5). A neutralising commit follows (§5). The dispatch stays in the hub until A-3 (§12, risk 1). Proven bitwise | 4–6 | one full gate and the compare, about 2 lane-hours |
| A-3 | The deletion batch: the dry run, the approved removal list, legacy deleted whole | 2–3 | dry run about 45 minutes; one full gate; tier 3 once (1–2 h); re-measure (about 1 h) |
| A-4 | Re-express the relocated cores as the features land | 8–12 | 2–3 gates; judged runs 2–4 lane-hours |
| A-5 | Retire the relocated copy | 1–2 | one gate |
| **Total** | | **18–27, plus the features** | **5–7 full gates, about 15–20 lane-hours** |

- **Meanwhile in every gate:** the copy's tests as live tests, 28 files in tiers 1+2 (273 test-seconds) and 14 in
  tier 3, reaching it directly or through helpers.
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
| B-1 | As A-1 | 2.5–4 | one full gate |
| B-2 | Re-express the ensemble as the features land | 8–12 | 2–3 gates; judged runs 2–4 lane-hours |
| B-3 | The deletion batch, with legacy deleted whole | 2–3 | as A-3 |
| **Total** | | **13–19, plus the features** | **4–5 full gates, about 12–15 lane-hours** |

- **Meanwhile in every gate:** every legacy-reaching test, the physiology stack's included (§7.2).
- **The BETSE-rule risk is the lowest.** Nothing is relocated, and the physiology stack's BETSE glue never moves.

### 7.5 Route C: prune legacy in place to the used cores, delete the rest now, then re-express

**It is the user's D346 choice again.** On 24 November D346 deleted what neither BETSE nor the calcium ensemble
used, and kept the rest until it was ported. D348, later the same afternoon, withdrew that: "no partial deletion",
because 180 files outside legacy used both the kept and the deletable parts. Two things have changed.
- **D374 retired the physiology stack,** so BETSE needs no legacy. What C keeps is the ensemble's core, with
  `spatial_extracellular@2` for JUPITER. The `@1`, `@2` and `@8` paths leave for the live registry at C-1.
- **D348's objection is smaller:** its 180 files are down to 15 direct hand edits and 50 fixture files still open,
  below.

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
to the live registry at C-1 (§7.3). The dry run may find more. `finite_extracellular@3` is the integrated
ensemble's world (`configs/junction_finite_cluster.json`).

**D348's objection, recounted** (`probe10.json` to `probe12.json`). A surviving file needs a hand edit if it
imports something that goes, or names a deleted model ID. By static evidence:

| What | Files |
|---|---|
| **Surviving files that import something that goes** | 6: `scripts/verify_source_pair_build.py`, `tests/joint_water_barrier_dispatch_fixtures.py`, `tests/owned_barrier_dispatch_fixtures.py`, `validation/tissue/cotransport_recovery_diagnostic.py`, `tests/unit/test_cav_channels.py`, `tests/unit/test_multispecies_build_audit.py`. The first four likely go with their families |
| **Live `src` files that name a deleted ID** | 5: `definitions/specs.py`, `definitions/surface_kinetic_spec.py`, `definitions/surface_tissue_spec.py`, `ensemble/ionic.py`, `execution/grid.py` |
| **Surviving tests that name a deleted ID** | 4: `test_declarations.py`, `test_finite_extracellular_production.py`, `test_kinetic_finite_schema.py`, `test_surface_catalog.py` |
| **Other surviving files that name a deleted ID** | 147 in `validation/`, fixtures and scripts: 84 orphans (every importer goes, so they go on the removal list), 11 standalone (reference tests of deleted families), and **52 shared**, reached by tests that survive |

- **About the 52 shared:** two are benign. `surface_dynamics_fixtures.py` and `surface_kinetic_fixtures.py` build the
  dictionaries the live pump fixtures start from, and those overwrite the ID before it is parsed. They account for
  293 of the 312 surviving tests that reach the 52.
- **The other 50 hang on 18 tests.** By docstring, ten look legacy-subject (the two barrier dispatch tests, two
  recovery-grid tests, the joint-water epoch contracts, the surface-bath charge reference, the surface reference, the
  multispecies build audit, the source-pair command line, and the catalogue planning), so their fixtures would go
  too. Eight look live-subject or kept core: `test_ionic_plan_admission.py`, `test_surface_catalog.py`,
  `test_numerical_refinement.py`, `test_cav_channels.py`, `test_osmotic_water.py`,
  `test_spatial_extracellular_acceptance_resources.py`, `test_rehost_probe.py` and `test_surface_kinetic.py`. I
  have not read them.
- **So D348's objection has shrunk from 180 files to 15 direct edits, with 50 fixture files open,** not to "about
  15". Reading those 18 tests, and C-1's dry run on the pruned tree, settle it.
- **250 test files go with their subjects:** 109 in tiers 1+2 (2,564 test-seconds) and 141 in tier 3. Their
  subjects were judged by import and name, so the dry run fixes the list.
- **What this replaces.** Two earlier versions gave 15, with a wrong make-up: one classed eight tests of the parity
  ladder as retired by their folder, and 18 live tests as legacy-subject by their names; neither counted the 147.
- **What it cannot see:** a test that parses a deleted ID through a configuration. Tonight's dry run deletes all of
  legacy, so it measures another tree.

**The guards of the kept core while it lives:**
- `test_spatial_calcium.py`, `test_plasma_calcium.py`, `test_gated_calcium.py`, `test_ip3_calcium.py`,
  `test_er_calcium.py`, `test_compartment_reactions.py`, `test_assembly_cell.py`, `test_assembly_cluster.py`,
  `test_assembly_controls.py`, `test_integrated_ensemble.py`, and the two GPU integration tests;
- for `finite_extracellular@2`: `test_kinetic_finite_dynamics.py`, `test_kinetic_finite_runner.py`,
  `test_kinetic_finite_schema.py` and `test_finite_extracellular_production.py`;
- for `spatial_extracellular@2`: `test_spatial_extracellular_acceptance_resources.py` and
  `test_spatial_extracellular_context.py`;
- for the @8 path: `test_surface_catalog.py` and `test_surface_pump_v3_gates_equivalence.py`;
- for `@1` and `@2`, whose dispatch leaves the hub at C-1: the six test files of row A12, all tier 3.

Most are tier 3.

| Step | Content | Agent-days | Gates and lanes |
|---|---|---|---|
| C-0 | Captures: bitwise windows for the kept core (the prune edits must leave its worlds bit for bit), and the science set | 0.5 | about 2 lane-hours |
| C-1 | **The prune batch:** the dry run on the pruned tree; the approved removal list; 208 of legacy's 321 modules deleted; the hub pruned; the hand edits of §7.5; the batch's live-side items (as A-1, without the JUPITER and integrated-ensemble retargets, which wait for C-2). **Among them the dispatch of `resolved_tissue@1`, `@2` and `@8` moves to the live registry, by exact type, so that live code needs no kept hub (§7.3).** Further edits inside the cluster buy the estimates above, and are optional | 3.5–5.5 | dry run about 45 minutes; one full gate; tier 3 once (1–2 h); re-measure (about 1 h) |
| C-2 | Re-express the ensemble and the JUPITER world as the features land (rows A10, E4 included) | 9–14 | 2–3 gates; judged runs 2–4 lane-hours |
| C-3 | Delete the remaining core, the hub and `registry/legacy_entry.py` | 1–2 | one full gate; tier 3 once; re-measure |
| **Total** | | **14–22, plus the features** | **4–5 full gates (two with tier 3), about 13–18 lane-hours** |

- **Meanwhile in every gate:** the core's tests (§7.2) and the pruned hub's dispatch-miss path. Most of the
  tier 1+2 saving arrives at C-1.
- **The BETSE-rule risk is low.** Nothing enters live `src`, and the physiology stack's BETSE glue (§5) is deleted
  at C-1. The core's own BETSE-derived conventions stay where they are, in the holding area, until C-3.
- **What it reverses:** D348's "no partial deletion" and "one deletion with one gate". There are two deletions,
  the first the larger.
- **Its own risk:** the prune of the hub, whose bitwise proof is C-0's windows.

### 7.6 The recommendation: Route C, under either answer

| | A | B | C |
|---|---|---|---|
| Agent-days beyond the features | 18–27 | 13–19 | 14–22 |
| Full gates | 5–7 | 4–5 | 4–5 (two with tier 3) |
| Lane-hours | 15–20 | 12–15 | 13–18 |
| Legacy lives, answer (a) | until A-3 (9–13.5 agent-days), then a copy for 22.5–36 | whole, for 26–41 | at least 58% leaves after 4–6; the core for 23.5–38 |
| Legacy lives, answer (b) | until A-3, with the copy open-ended | whole, open-ended | the core open-ended; the rest leaves at C-1 |
| A relocated copy in live `src` | yes | none | none |
| Every gate carries meanwhile | the copy's tests | all legacy-reaching tests | the core's tests and a pruned hub |
| BETSE-rule risk | moderate | lowest | low |
| Thrown away | the relocated copy | nothing | nothing |

**Why C:**
- It delivers almost all of the deletion's gate saving at its first deletion, as A does.
- It costs no throwaway copy, and nothing BETSE-derived enters live `src`, as B does.
- It does not need an answer to the GPU question to start, and it stays cheap if the answer is (b).
- The lead's removal analysis prepared most of its list.

**B fits** if the user holds D348's single deletion and answer (a), and accepts every legacy test in every gate
meanwhile. **A fits** only if legacy must be gone before the features, whatever the copy costs; under answer (b) it
leaves that copy in live `src` with no end.

## 8. Qualifying a re-expression: science-length captures and a derived tolerance

**Two kinds of capture, both from the pre-rename snapshot frozen in the morning:**
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
  pools-at-the-cell's-potential branch of G-4), the PMCA at another standard state (B1), and NCX written as a
  transporter cycle if its rate form changes. No band applies. These rows are judged by the consumer's own
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

**The command form** is the one verified tonight, in shards on a lane:
```
PYTHONPATH=SNAP/src:SNAP JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 CUDA_VISIBLE_DEVICES= JAX_ENABLE_COMPILATION_CACHE=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /mnt/workspaces/Cells/venv-cpu/bin/python -B SNAP/validation/results_baseline.py save OUT/<part> --sets <sets> --from ORIGIN --max-steps <steps>
```
- **The full length** comes from `--max-steps` at or above the world's step count: the first window then
  holds the whole run.
- **The assembly families** run on the CPU command line, one run per config, seed and step. This path was
  not probed tonight:
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

**Measured tonight** on CPU 4, under the timed lock and a 4 GB scope, cold:

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
- **Placement and timing:** nothing heavy runs tonight; both lanes are held. The probes ran on CPU 4 under
  the timed lock and released it between runs.

## 9. Tests: move, stay or go

The counts are from the static evidence and the scope map (`probe4.json`). The dry run (§2) replaces them.

**Today:**
- 195 of the 891 tier-record files import legacy directly (D346's count): 76 in tiers 1 and 2 (1,530
  test-seconds) and 119 in tier 3.
- 10 more name a legacy ID themselves: 7 and 3.
- 401 reach legacy only through a fixture, shared driver or configuration: 312 (7,847 s) and 89.
  - 27 of the 312 (370 s) are named after a legacy family.
  - The other 285 are mostly live-subject tests whose fixtures also name legacy IDs.
- 35 files have no static evidence and load legacy at runtime only through a dispatch miss.
- **By import, closing over helpers:** 292 files reach legacy, 137 of them in tiers 1+2 (2,837 test-seconds, about
  8.8 minutes of a gate's wall) and 155 in tier 3. Of those, 250 go at the first deletion and 42 stay with the
  kept core (28 in tiers 1+2, 273 test-seconds; 14 in tier 3) (`probe10.json`).

**Under §2's definition:**

| Class | What happens | Files (tiers 1+2 / tier 3), estimated |
|---|---|---|
| **Go:** the subject is a legacy model whose capability is canonical or dropped | Deleted in one batch with the deletion, by a removal list (D224) giving each file's capability row and reason | 109 / 141 by static evidence, after removing 18 live tests that a file-name heuristic had caught (`probe10.json`); the retired physiology set's 34 / 24 are among them (D374). Under Route C they go at C-1 |
| **Move:** physics, conservation and reference tests of the used capabilities: `test_spatial_calcium.py`, `test_plasma_calcium.py`, `test_gated_calcium.py`, `test_ip3_calcium.py`, `test_er_calcium.py`, `test_assembly_cell.py`, `test_assembly_cluster.py`, `test_integrated_ensemble.py`, `test_assembly_controls.py`, the GPU integration tests | Under C they stay with the kept core until C-2. Under A they move with the relocation. Under B they stay until the deletion. Each is retargeted to the canonical form when its capability is re-expressed, and assertions on legacy structure are dropped | 28 / 14 reach the kept core, 6 / 10 of them directly |
| **Stay:** live-subject tests with incidental reach: fixtures naming legacy IDs, dispatch misses, the conftest world, @3's reference | Fixtures are cleaned. A9 and A12 keep `resolved_tissue@8`, `@1` and `@2` (Q5 (a), widened); G1's 9 users point at a live world (Q6 (a)) | not counted statically: the dry run lists them |
| **New** | None in the tiers. A re-expression's judged qualification is a recorded run, not a tier test. A test that compiles a world states its seconds and reason (D224) | 0 |

**Recorded tier-3 failures** stay as recorded in moved files: `test_assembly_cell.py` (1) and
`test_assembly_cluster.py` (2). A fix is a row in the existing file (D224).

## 10. The deletion: content, removal list, gate and saving

**One deletion under A and B; two under C.** C's first, at C-1, is the larger; its second, at C-3, removes the
kept core, the hub and `registry/legacy_entry.py`. Each runs as below.

**Before each:** main is tagged and its snapshot frozen, as the BETSE-native removal was
(`native-betse-frozen-2026-11-08`).

**The commit removes** (under C, the first takes everything outside the kept core, and the second the rest):
- `src/cells/legacy/` and `registry/legacy_entry.py`;
- the `legacy()` call sites of §2;
- `ensemble/ionic.py`'s rows for capabilities not kept (the rows for `resolved_tissue@1`, `@2` and `@8` stay);
- `registry/declarations.py`'s legacy list and the manifest's `legacy` key. That is coordinated with the
  viewer's agent first, and the format is the rename note's Q6.

**Also in the same batch:**
- the removal list's tests and `tests/unit/test_legacy_entry.py`;
- validation drivers and references that serve only dropped rows;
- configs and examples naming deleted IDs (112 configs name a legacy ID);
- group H's document pointers;
- the regenerated `docs/library/`;
- PROGRESS.

Reports and records stay.

**The gate** is the full one:
- the IDs, with removals declared (`REMOVED_OK_FILE`);
- crossrev (identical: no set reaches legacy);
- tiers 1+2 on the surviving files;
- G1 at 113 of 113 (its worlds name no legacy ID);
- tier 3 once, deliberately, against a refrozen record;
- the tiers re-measured and folded;
- the private-term scan.

The scope map stays stale until the next nightly rebuilds it.

**The saving.** Measured in the gate of 24 November: tiers 1+2 took 2,531 s of about 3,275 locked seconds,
G1 592 s and crossrev 152 s.

| Stage | Today | After (estimate, until the dry run measures it) |
|---|---|---|
| Tiers 1+2 | 13,577 test-seconds, 2,531 s of wall (0.186 s of wall per test-second) | −2,564 test-seconds (19%), about 8 minutes of a gate's wall, for the 109 test files that go by static evidence, the retired physiology set's among them. Upper bound −9,554 (70%), about 30 minutes, if the dry run finds that the fixture-reaching tests run legacy worlds |
| G1, crossrev | 592 s, 152 s | unchanged |
| Tier 3 | 215 files, 87,166 test-seconds | 204 files reach legacy; most go |

**When the saving arrives:**
- Route A: at A-3.
- Route C: mostly at C-1; the rest at C-3.
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
   - The alternative is exact-type checks. The three `resolved_tissue` entries that move at C-1 need them (§7.3).
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
   unaffected.
8. **Unprobed paths.**
   - The assembly command lines' capture cost, and the cache setting that `configure_caches()` makes.
   - The tools `capture_worlds.py`, `capture.sh` and `dry_delete.py` are not written.
9. **Lane time.** The captures, the dry run, three or four full gates and tier 3 compete with the FR queue.
   FR-43, the user's top priority, keeps the timed cores.
10. **The Lean lane** may cite legacy IDs. It gets the mapping table through the user; `lean/` is not edited.
11. **Route C's partial deletion** reverses D348's single batch. A capability the coverage table missed, and
    which only the deleted part held, would be lost at C-1. The dry run (§2) and the re-read of the rows not
    read here (§3) come first.
12. **Coordination with the cardiac lane** (§4). If the ensemble and the human cardiac laws each build calcium
    handling, D210's rule of one law per mechanism is at risk. The G-1 and G-4 notes are written together.
13. **An open-ended date** (§7.2). If the user chooses answer (b), or if the features are not requested, the
    remainder lives on. A leaves a legacy copy in live `src` and B leaves every legacy test in every gate; C's
    remainder is the smallest.
14. **Static counts.** The kept set, the edge cut and the going tests come from import edges and own-text IDs.
    Three of my own counts were wrong, and are corrected here: folder names for the retired drivers, file names for
    legacy subjects, and the coverage table's use of `resolved_tissue@1` and `@2`. The dry runs settle the rest.
15. **Kernels that D211's port programme needs leave with C-1.** `legacy/processes/cotransport.py` (rows I7, I8 and
    I9) is outside the kept set, and no route step ports it. D211 reads it from the tag instead.

## 13. The user's questions

**Decided by D374, recorded here:**
- the calcium ensemble is kept and re-expressed in canonical form;
- the physiology stack (17 drivers) and the 18 REF-era drivers retire in the deletion batch, with their
  records kept;
- no retirement before the rename's move;
- Q5 and Q6 are (a) each, inside the deletion batch. The lead widened Q5 (a) to `resolved_tissue@1` and `@2` on
  24 November;
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
  - It is D346's choice again, with BETSE's part gone (D374). D348's objection is smaller, though 50 fixture files
    are still open (§7.5).
  - The lead's removal analysis covers most of its list.

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
  need exact types whichever way it goes (§7.3);
- the manifest key;
- a GPU block after the ensemble's re-expression, if Q1 or Q5 calls for one.

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
