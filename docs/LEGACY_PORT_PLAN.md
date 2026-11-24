# Legacy port plan: everything Cells uses leaves legacy, in canonical forms

**Status: a plan for the morning's review, reworked after D369** (24 November 2026, night). Nothing in it is
built or decided. It was written read-only:
- the tree is main at `ce4780d2`;
- D369 is at `618cf31c`, which changes none of the files cited here by line.

**What is decided:**
- **D346 and D348:** port the legacy families that are used, then delete `src/cells/legacy/` whole, in one
  deletion with one gate. Main is tagged first.
- **D369, the user's direction:** "the legacy work is clearly important cleanup we need to make sure to get
  everything we're actually using out of there in our canonical formats".
  - **The end state is canonical.** Everything used is re-expressed in the engine's laws, models,
    operators and definitions, under the rename's IDs. A relocated legacy island is not an end state.
  - **The scope is a test of use, not a list of IDs.** This is the user's rule of 17 November: legacy goes
    in one batch after a check that covers every capability.
  - **Not settled:** whether a bitwise relocation comes first, as an interim step. §7 prices both routes.
- **BETSE (AGENTS.md, 8 November):** an outside reference only. Nothing in `src/cells` imports, executes,
  re-hosts or copies BETSE code, or carries its conventions or names. Laws BETSE also uses are fine under
  neutral names, with the source cited.
- **The rename comes first (D345, D346).** Every live ID becomes `cells.<family>.<name>@major`; legacy's
  stay bare and frozen until the deletion. Every new ID below is a proposal, to be named in the rename note
  (`docs/ID_HIERARCHY_DESIGN.md` on branch `rename-design`).

**Records:** `/mnt/workspaces/Cells/legacy-port-plan-20261124/`.
- `inventory.json`, `probe4.json`: the import graph, each file's legacy evidence, and each test file's
  class. `probe.json` and `probe2.json` hold superseded figures, among them 1,445 consumers counted through
  the dispatch string.
- `probe-capture-{a,b,c}/`: tonight's capture probes.
- `legacy_defs_with_shared.json`: the legacy definitions that spell the rename's 18 shared pieces.
- `tools/`: the probes' scripts.
- The lead's earlier analysis is in `/mnt/workspaces/Cells/legacy-removal-20261124/`.

Paths are repository paths unless they start with `/mnt/`.

## 1. Summary

**"Used" is fixed before counting (§2).** A capability is used when a consumer that is not a legacy-subject
test needs it, in one of four ways:
- a live engine module needs it;
- a live feature's test uses it as a vehicle or reference;
- a current document claims a result that rests on it;
- a registered protocol in force runs it.

A test whose only subject is a legacy model is not a use, and neither is a historical record.

**Tonight's checks of use:**
- **No registered protocol in force names a legacy model.** None of the rename probe's 233 frozen files
  does.
- **No current document claims a result from the 39 legacy-importing BETSE drivers.** The claimed parity
  ladder's own code reaches legacy only through one re-exported helper (§6, row G3).
  - The BETSE parity that PROGRESS claims (the default world, rungs D and F, P2 to P4b, CPU and L4) runs on
    `resolved_pump_tissue@1` to `@3` (`validation/betse/protocols/physical_*`).
  - The 18 REF-003 to REF-005 drivers are cited only by their own September and October design and closeout
    notes and reports.
  - The 17 physiology drivers' results are claimed nowhere. PROGRESS records only that their stack moved
    to `validation/betse` (Stage B).
- **Used today, beyond legacy's own tests:**
  - the calcium ensemble: the assembly-regulated cell and cluster over `spatial_calcium@1`–`@4`. Its users
    are the live ensemble runner's kinds (`ensemble/families.py:20–26`) and `docs/GPU_ENSEMBLES.md`'s
    qualified preparations;
  - `spatial_extracellular@2`, which the JUPITER readiness check runs (`validation/ensemble/jupiter_check.py:47,
    367`; `docs/JUPITER_RUNBOOK.md`);
  - `resolved_tissue@8`, @3's reference world in its gates-equivalence tests;
  - `source_decay@1`, the shared conftest's world for 9 infrastructure tests.
- **Documents that point at legacy capabilities** (paper reviews, two design notes) are claims to correct,
  not uses (§3, group H).

**The coverage table (§3)** has 39 capability rows:
- 16 canonical already;
- 5 expressible today;
- 9 that need an engine feature: five for the calcium ensemble, one if Q2 keeps the physiology set, and
  three only if wanted;
- 6 dropped, each listed with what is lost;
- 3 that follow Q2 or another row.

**Nine gaps are confirmed at their refusal sites (§4).** They are candidate requests for the user, not FRs:
- calcium-permeant channels on @3;
- instantaneous gate-free laws;
- channels that read a species;
- an ER store;
- IP3-gated store release;
- finite fuel;
- assembly-to-availability coupling;
- the composite on a GPU;
- excision.

The calcium ensemble alone needs five of them: G-1, G-4, G-5, G-7 and G-8.

**The BETSE rule bars part of a relocation (§5).**
- The profile, mesh and face chain that `resolved_open_calcium@1`'s closure pulls in carries BETSE's
  conventions: BETSE's source revision and functions recorded as fields, its selector conventions, its mesh
  summation order, its grid and bath conventions. It cannot enter `src/cells`.
- The open families need only one helper from it (`open_calcium_admission.py:13, 89`).
- The physiology set's helpers are BETSE glue throughout.

**The two routes (§7):**
- **Route A:** relocate the used, feature-blocked cores bitwise as an interim, delete legacy early, then
  re-express as the features land.
  - About 16–24 agent-days, plus the features.
  - Legacy goes in about 1–1.5 weeks.
- **Route B:** re-express first, then delete.
  - About 13–20 agent-days, plus the same features.
  - The deletion waits for all five features, and legacy's tests stay in every gate until then.

**Qualifying a re-expression (§8)** needs science-length captures at three steps (h, h/2, h/4), with the
tolerance derived from legacy's own step-halving and fixed before any re-expressed run, plus a power check.
- Tonight's probes give the per-step costs: 0.013 s per step for `spatial_calcium@1` and 0.052 s for
  `resolved_tissue@12`, after compiles of 22–155 s.
- The used set's science captures are estimated at 6–8 CPU-hours, about 1–1.5 hours of one lane, from
  the pre-rename snapshot. The five-step bitwise captures are only for Route A.

**The rename's Q3 (§11):** option (a), re-spell legacy's uses of the 18 shared pieces, works under either
route.
- Retiring the 18 REF-era drivers before the move takes about a dozen of the rename's 30 `validation/betse`
  rewrite files out.
- Captures from the pre-rename snapshot need no re-spelling: they are compared through the table.

**The user's questions (§13):**
- Q1, the sequence;
- Q2, the physiology stack;
- Q3, the REF-era drivers;
- Q4, the calcium ensemble's place;
- Q5, @3's reference world;
- Q6, the three inline families;
- Q7, which gaps to request.

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

**The dry-run deletion, the definitive measure of U2.** It is not run tonight, because the lanes are full.
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
4. Tier 3, the same command with `--tier 3`: estimated at 1–2 hours of a lane. Of its recorded 87,166
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

"Uses" names only consumers that count under §2. Rows whose only consumers are the physiology set depend
on Q2.

**Evidence levels.** A wrong "Canonical" is the silent-loss direction, so each row's basis is stated.
- **Read here,** at the cited lines: A1, A4–A6, A9, B2's refusal, B3–B5, C2, D9, E1–E3, P1, G1, G3, and
  the refusal sites of §4.
- **By registry name or protocol only:** A2, A7, A8, C1, D3, D4, D6 (the registry dump), and D7, D8 (the
  parity protocols' model IDs).
- **From a research read not repeated here:** A3, A10, A11, B1's standard state, B7, C3, C4, D1, D2, D5,
  E4.

The builder re-reads every row not read here before the deletion. A row found not canonical moves to
Feature or Drop, and the user is told.

### A. The electrical tissue

| # | Capability (legacy home) | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| A1 | Passive resolved tissue: membranes, outside regions, faces, field solver, capacitive closure (`resolved_tissue@1`, live `models/surface_tissue.py`) | @3 is built on its spec (`definitions/surface_tissue_spec.py`) | Canonical | @3; only legacy's dispatch of the ID goes |
| A2 | Gated Na, K and Cl channels registered on @3: Kv1.1–1.6, Kir2.1, Nav1.2, the three leaks | @3 | Canonical | the 11 `channel_law@1` laws |
| A3 | The catalogue's other Na/K/Cl gated laws (Kv2, Kv3, `k_fast`, Nav1.3, Nav1.6 persistent, the `navrat` set) | physiology set only (Q2) | Expressible, or Drop | register one module per law on @3, as the Kv1 extraction did (`laws/channels/kv1_channels.py:7–11`) |
| A4 | Calcium-permeant channel laws: 14 CaV laws with `cav1p2_m2h@1`, cation leaks with a Ca share, HCN laws with a Ca share | the calcium ensemble (Cav1.2 in the gated and IP3 clusters); physiology (Q2) | Feature | G-1 |
| A5 | Instantaneous voltage-gated laws (8 Morris–Lecar) | none beyond legacy tests; physiology if it uses them | Feature, or Drop | G-2 |
| A6 | Calcium-activated K (`cagpotassium_numeric_mM_scale@1`) | none beyond legacy tests | Feature, or Drop | G-3 |
| A7 | Junction gating | @3 | Canonical | `junction_voltage_relaxation@1`, `junction_series_gates@1` |
| A8 | Na/K pump on maintained reservoirs | @3 | Canonical | `nak_atp_mass_action_positive@1` |
| A9 | @3's reference world: the gated catalogue model `resolved_tissue@8` (live `models/surface_kinetic.py`) | `tests/unit/test_surface_pump_v3_gates_equivalence.py` and @3's tests through `validation/tissue/surface_pump_v3_fixtures.py:107–129` (U2) | Canonical code, but its dispatch is legacy's | Q5 |
| A10 | Cell clusters in finite and spatial baths (`finite_extracellular@1`–`@3`, `spatial_extracellular@1`–`@2`) | the JUPITER check (`spatial_extracellular@2`, U3); nested in the calcium ensemble (`spatial_extracellular@2`, `finite_extracellular@2`); the REF-era drivers are not uses | Expressible | the same physics as @3 worlds (constant-field leaks, Kv1.5, the pump, junctions, faces), not bitwise |
| A11 | The oldest families (`bioelectric_cell@1`, `bioelectric_pair@1`, `multispecies_membrane@1`, `voltage_gated_membrane@1`, `physical_ionic_graph@1`, `emt_mirna_pair@1`, `spatial_extracellular@3`) | none; helpers inside the A10 line | Drop | superseded by @3; group H's pointers corrected |

### B. Calcium

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| B1 | Cytosolic calcium with a plasma-membrane pump (`plasma_calcium_pump_positive@1`) | the calcium ensemble; physiology | Canonical | `cells.ca_atp_mass_action_positive@1` on @3: the same kernel at a 1 M standard state, Δg0 − RT ln 1000. Not bitwise |
| B2 | NCX, 3 Na : 1 Ca (`ncx_3na_1ca_symmetric_barrier@1`, a live module, unregistered) | the calcium ensemble (plasma, gated, IP3); physiology | Expressible | a cycle law in the transporter kind's version-1 layout. The population axis refuses a mode that moves charge (`kinds/transporter.py:1250–1253`). The builder confirms Ca rows |
| B3 | ER store: a closed compartment with a capacitor, a GHK leak, a pump and calcium-gated release (`er_calcium@1` over `compartment_reactions@1`) | the calcium ensemble (all four calcium clusters); physiology | Feature | G-4 |
| B4 | Calcium buffering by mass action, in the cytosol and in the ER | as B3 | Feature (with B3) | `local_species_reactions@1` holds a species that @3 routes only as a covered counter-ion (`operators/species_common.py:16–17`). Inside the ER it waits for G-4 |
| B5 | IP3-gated store release (`ip3_er_release@1`) | the calcium ensemble (IP3 cluster); physiology | Feature | G-5 |
| B6 | Owned calcium in the 56-law tissue, closed or open exterior (`resolved_calcium@11`, `resolved_open_calcium@1`) | physiology only (Q2) | Feature, or Drop | composes A4, B1–B5 and D1 |
| B7 | The spatial calcium tissue (`spatial_calcium@5`, `tissue_calcium`) | none; pointed at by `docs/PAPER_REVIEW_CCI_SEQ.md:30` | Drop | its physics is B1–B5 |

### C. Energy

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| C1 | Maintained ATP/ADP/Pi reservoirs | @3 | Canonical | `maintained_chemical_reservoirs@1` |
| C2 | Finite per-cell ATP/ADP/Pi pools, regeneration ports and finite-fuel pumps (`resolved_energy@1`–`@2`, `resolved_calcium_energy@1`–`@5`, `resolved_open_calcium_energy@1`) | physiology only (Q2); `docs/CORE_LAWS_ROADMAP.md:73–75` plans its rebuild | Feature | G-6 |
| C3 | ATP-driven, irreversible, regulated and cotransport variants (`resolved_calcium_energy_atp_transport@1`, `_irreversible_transport@1`, `_regulated@1`–`@2`, `_transport@1`, `resolved_cotransport@1`) | none | Canonical in part; Drop the legacy forms | `atp_driven_transporter_mass_action_positive@1`, the cotransport cycle laws, `species_regulated_availability@1`. Their finite-fuel forms wait for G-6 |
| C4 | Mitochondria (`resolved_calcium_energy_mitochondria@1`, `mitochondrial_passive`) | none; pointed at by `docs/PAPER_REVIEW_T_CELL_ORGANELLES.md:119–122` | Canonical in a fuller form; Drop the legacy form | the transporter kind's respiratory-chain, ATP-synthase, nucleotide-exchange and adenylate-kinase laws (`docs/MITOCHONDRIA_DESIGN.md`) |

### D. Exterior, volume, membranes, repair

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| D1 | Static ideal chemical and voltage reservoirs with electrode-work ledgers | physiology (Q2) | Expressible | @3's line books `reservoir_supplied`, electrode charge and work (`models/surface_tissue.py:37–43`; `models/surface_pump.py`); the builder confirms every mover's ledger |
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
| E1 | Finite-pool stochastic assembly and the capsid graph (`finite_bond_assembly@1`, `capsid_graph@1`) | the ensemble runner (U1) | Canonical (live code) | `assembly_pool/`, `assembly/`; seeded in the model table by the rename's Q4 |
| E2 | Assembly topology setting channel availability, in one cell and as per-cell pools over a tissue (`assembly_regulated_cell@1`, `assembly_regulated_cluster@1`) | the ensemble runner's kinds (U1); `docs/GPU_ENSEMBLES.md:125–200` (U3); `validation/assembly/qualify_cell.py`; `validation/ensemble/` | Feature | G-7 |
| E3 | GPU ensembles of these worlds (`cells ensemble run`, GPU-only, `ensemble/worker.py:95`) | `docs/GPU_ENSEMBLES.md`; the JUPITER runbook | Feature, after re-expression on the composite | G-8 |
| E4 | The ionic wrapper `ionic_worlds@1` (`ensemble/ionic.py`, which admits 98 legacy IDs) | the JUPITER check; `tests/unit/test_integrated_ensemble.py`; `validation/ensemble/integrated_matrix.py`, `spatial_matrix.py` | Expressible | an adapter onto @3 worlds, whose GPU path stands (D336 refuses only the composite). The builder confirms |

### P. BETSE-facing preparation

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| P1 | Tissue-profile selectors and static profiles; mesh binding in BETSE's order; BETSE's grid and bath face conventions; INIT/SIM phase handoff; the `tissue-profiles`, `tissue-geometry`, `tissue-phase` and `excise` command lines | physiology set (Q2); the 4 helper modules | Not allowed in `src` (§5): Drop, or BETSE glue in `validation/betse/` if Q2 keeps the set | physics inside it, such as the Bernoulli-fitted face law and cutting, becomes a request if a kept consumer needs it |

### G. Small inline families

| # | Capability | Uses | Class | Canonical piece or gap |
|---|---|---|---|---|
| G1 | `source_decay@1`, the conftest's synthetic world | 9 infrastructure tests (U2): `tests/integration/test_cli.py`, `test_replay.py`; `tests/unit/test_continuity_gpu.py`, `test_continuity_loaders.py`, `test_numerical_refinement.py`, `test_numerics.py`, `test_specs.py`, `test_stationary_analysis.py`, `test_windows.py` | Expressible | retarget to `reaction_transport@1` or a minimal composite (Q6) |
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

**Tally, 39 rows:**
- **Canonical: 16** (A1, A2, A7, A8, A9, B1, C1, C3, C4, D3, D4, D6, D7, D8, E1, G3). For C3 and C4, the
  legacy forms are dropped.
- **Expressible: 5** (A10, B2, D1, E4, G1).
- **Feature: 9:**
  - five the calcium ensemble needs: A4, B3, B5, E2, E3;
  - C2, if Q2 keeps the physiology set;
  - A5, A6 and D9, only if wanted.
- **Drop: 6** (A11, B7, D2, D5, P1, G2).
- **Following another answer: 3.** A3 and B6 follow Q2, and B4 waits with B3.

## 4. Confirmed gaps, at their refusal sites: candidate requests for the user

Each was confirmed by reading the code at main. None is logged as an FR; each is the user's to request.

| Gap | What is refused, and where | Needed by |
|---|---|---|
| **G-1: calcium-permeant channels on @3** | @3's channel valence table is `{"Na": 1, "K": 1, "Cl": -1}` (`definitions/surface_pump_v3_spec.py:169`). Each permeant ion is checked against it, "Channel ion requires its law's species and valence" (`:327–329`). @3 does carry a plasma calcium pump | A4: the calcium ensemble's Cav1.2; physiology |
| **G-2: instantaneous voltage-gated laws** | "a gate-free law gives no kinetics or opening" (`registry/laws.py:422–423`), so a gate-free law is always open | A5 |
| **G-3: channels whose kinetics read a species** | `ChannelLaw.kinetics` takes voltage only, and `reads` is empty for every law (`registry/laws.py:372, 375`) | A6 |
| **G-4: an ER store** | `cell_owned_compartments@1` refuses three things: a Na/K or Ca pump or a channel population on the bounding patch (`operators/compartments.py:359–366`); a constant-field permeability there without declared kinds, and any kind under RK4 (`:368–376`); and an owner whose capacitor component holds no held bath (`:514–519`) | B3, B4: the calcium ensemble; physiology |
| **G-5: IP3-gated release** | `species_regulated_availability@1` targets only `("junction", "channel")` (`operators/species_regulated_availability.py:154, 548–551`). It refuses a charged source (`:743–745`), and legacy's IP3 is charged −3 | B5: the calcium ensemble's IP3 cluster; physiology |
| **G-6: finite fuel** | @3's Na/K pump requires maintained reservoirs (`definitions/kinetic_pump_spec.py:43–44`), and its two pumps run on the maintained fuel kind (`models/inner_laws.py:9, 60`). The transporter kind refuses `finite_fuel_rows@1` in its version-1 layout (`kinds/transporter.py:234–237, 443–444`), and its population axis admits it only for the neutral ATP-driven law (`:1088–1104`) | C2: physiology; the roadmap's energy rebuild |
| **G-7: assembly coupled to availability** | No operator couples an assembly pool's topology to availability. The registry refuses any other (`registry/operators.py:176–181`); the assembly families exist only as ensemble kinds (`ensemble/families.py:20–26`); the nearest door reads species amounts, not topology (`species_regulated_availability.py:47–49`) | E2: the calcium ensemble |
| **G-8: the composite on a GPU** | `refuse_unqualified_gpu` refuses a GPU backend for `resolved_pump_composite@1` (`execution/vector_windows.py:213–230`, D330, D336) | E3: the calcium ensemble's GPU runs, once it is re-expressed on the composite |
| **G-9: excision on the composite** | No excision operator exists; `EXPERIMENT_PATH_PATTERN_RECOVERY.md` (row 7) names one as new | D9: no used row today |

**What the calcium ensemble needs:** G-1, G-4, G-5, G-7 and G-8, plus B2's registration.
- If Q2 keeps the physiology set, G-6 joins them, and G-2 and G-3 too if its worlds use those laws.
- The dry run and a read of the physiology protocols settle which laws they use.

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
| The physiology set's helpers | `tissue_profiles.py` (INIT/SIM profile recipes), the selectors and mesh binding above, `processes/extracellular_face_transport.py:4–6` ("Grid and bath conventions follow BETSE v1.5.0"), `processes/tissue_removal.py` (reference-code cut behaviour) | **Not allowed.** If Q2 keeps the set, the BETSE glue goes to `validation/betse/`, and any physics in it that the engine lacks becomes a request. `validation/` must not hold engine physics (AGENTS.md) |
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
- **Their evidence is not claimed.** They retire with their records (Q3).

**The 17 physiology drivers and their 58 tests:**
- Their results are claimed nowhere. PROGRESS records only that the stack moved to `validation/betse`
  (Stage B, line 126 and lines 4497–4505).
- `docs/CURRENT_PLAN.md:253–254` notes a dangling reference in it, as maintenance.
- **Their use is the user's call (Q2).**

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

So the claimed ladder rests on no legacy capability except the re-exported `identifier`. The two BETSE
tests on the helpers retire with the helpers (Q2, Q3).

**Bearing on the rename's Q3 (§11):**
- The rename's rewrite list holds 30 `validation/betse` files; about a dozen are in REF-era panel folders.
- Of the 102–106 legacy definitions that spell the shared pieces, 99 are `configs/`, 6 `examples/` and 1
  `validation/betse/junction_coupled/` (`legacy_defs_with_shared.json`).
- Retiring the REF-era drivers before the rename's move takes their files out of it.

## 7. Two routes, priced

Both routes end in the same state: every used capability canonical, legacy deleted whole, the rename's IDs
throughout. The tables count the used set as Q2 (retire the physiology set) and Q4 (keep the calcium
ensemble) recommend. The gaps of §4 are the user's requests and are priced separately:
These prices are rough guesses, not estimates from a design:
- G-1: 2–4 agent-days;
- G-4: 5–8;
- G-5: 2–3;
- G-7: 4–6;
- G-8: 3–6;
- B2's registration: 0.5–1.

That makes 16–28 agent-days for the calcium ensemble's features.

### Route A: relocate the blocked cores bitwise as an interim, delete legacy early, then re-express

| Step | Content | Agent-days | Lanes |
|---|---|---|---|
| A-0 | Captures from the pre-rename snapshot: bitwise windows for the relocated cores, and the science-length set of §8 | 0.5 | about 2 h of one lane |
| A-1 | Re-express at once what is expressible today: the JUPITER check onto @3 (A10, E4), the conftest world (G1), `resolved_tissue@8`'s dispatch per Q5 | 2.5–4 | one gate |
| A-2 | Relocate the used cores that wait on features: `spatial_calcium@1`–`@4`, `er_calcium@1` with `compartment_reactions@1`, `spatial_extracellular@2` and `finite_extracellular@2` with their helpers, and the two assembly families with the ensemble adapters. `scripts/source_moves.py` does the move: one map, its rewriter and verifier. A neutralising commit follows (§5); the dispatch stays in the hub until A-3 (§12, risk 1). Proven bitwise (§8) | 4–6 | one full gate, plus the compare |
| A-3 | The coverage table's Drop rows, approved by the user; the dry run; the removal list; the deletion | 2–3 | dry run about 45 min; full gate; tier 3 once (1–2 h); re-measure (about 1 h) |
| A-4 | Re-express the relocated cores as G-1, G-4, G-5, G-7, G-8 and B2 land, each judged against §8's science captures | 6–9 | judged runs, about 2–4 lane-hours |
| A-5 | Retire the relocated island | 1–2 | one gate |
| **Total** | | **16–24, plus 16–28 of features** | |

- **Legacy goes** in about 1–1.5 weeks, independent of the features.
- **The relocated island** lives under neutral names and new IDs until A-4. D369 rules it out only as an end
  state.
- **Risks:** the island's code is thrown away at A-4, and an interim under new IDs can attract new
  dependents. §12 has the rest.

### Route B: re-express directly, delete when the last used capability is canonical

| Step | Content | Agent-days | Lanes |
|---|---|---|---|
| B-0 | The science-length captures of §8 | 0.3 | about 1.5 h of one lane |
| B-1 | As A-1 | 2.5–4 | one gate |
| B-2 | The features G-1, G-4, G-5, G-7, G-8 and B2's registration | (priced above) | per request |
| B-3 | Re-express the calcium ensemble and its nested layers on them, each judged against B-0 | 8–12 | judged runs, 2–4 lane-hours |
| B-4 | As A-3: the drops, the dry run, the removal list, the deletion | 2–3 | as A-3 |
| **Total** | | **13–20, plus 16–28 of features** | |

- **The deletion waits for all five features.** At the features' pace that is weeks.
- **Until then legacy stays in every gate:** its tests cost about 2,100–9,500 of the 13,577 tier 1+2
  test-seconds per gate (§10), and live changes can break legacy tests that nobody now owns.
- **No code is thrown away.**

### If Q2 keeps the physiology set

Both routes add:
- re-expressing `resolved_tissue@12` as @3 channel laws (rows A3 and A4) and its 56-law worlds: 3–5 agent-days;
- rows B6 and C2, with C2's finite fuel (G-6 at 4–6, plus 3–5): 7–11;
- moving the BETSE glue into `validation/betse`: 2–3;
- G-2 and G-3 if its worlds use them: 3–5.

That is about 15–24 agent-days more. Route A would also relocate the cores of `resolved_tissue@12`,
`resolved_calcium@11` and `resolved_calcium_energy@5` (3–4 agent-days), but not the glue (§5).

## 8. Qualifying a re-expression: science-length captures and a derived tolerance

**Two kinds of capture, both from the pre-rename snapshot frozen in the morning:**
- **Bitwise windows, Route A only.** They prove a move, not a re-expression: the first scalar window of up
  to 200 steps, through `validation/results_baseline.py save --from`.
- **Science-length runs, both routes.** These qualify a re-expression. Each used capability's consumer
  worlds run at the length their claim used, at three steps, with every recorded array saved.

**The science set (used capabilities, under Q2 and Q4 as recommended):**

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

**The tolerance for same-equation rows is derived, never tuned.** It is fixed in the protocol before any
re-expressed run, from both methods' own refinement:
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
- **If Q2 keeps the physiology set:** about 3–5 CPU-hours more, for its tests' worlds. Its eager (JIT off)
  fixtures capture with JIT on, with legacy's JIT-on runs as the reference.
- **Bitwise windows (Route A):** about 1–1.5 CPU-hours for the relocated cores.
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

**Under §2's definition:**

| Class | What happens | Files (tiers 1+2 / tier 3), estimated |
|---|---|---|
| **Go:** the subject is a legacy model whose capability is canonical or dropped | Deleted in one batch with the deletion, by a removal list (D224) giving each file's capability row and reason | about 130 / 150 under Q2 (retire), counting the physiology set's 34 / 24 |
| **Move:** physics, conservation and reference tests of the used capabilities: `test_spatial_calcium.py`, `test_plasma_calcium.py`, `test_gated_calcium.py`, `test_ip3_calcium.py`, `test_er_calcium.py`, `test_assembly_cell.py`, `test_assembly_cluster.py`, `test_integrated_ensemble.py`, `test_assembly_controls.py`, the GPU integration tests | Retargeted to the canonical form when its capability is re-expressed, or moved with the relocation in Route A. Assertions on legacy structure are dropped | about 5 / 10 |
| **Stay:** live-subject tests with incidental reach: fixtures naming legacy IDs, dispatch misses, the conftest world, @3's reference | Fixtures are cleaned; G1 and A9 are retargeted per Q5 and Q6 | about 290 / 55 |
| **New** | None in the tiers. A re-expression's judged qualification is a recorded run, not a tier test. A test that compiles a world states its seconds and reason (D224) | 0 |

**Recorded tier-3 failures** stay as recorded in moved files: `test_assembly_cell.py` (1) and
`test_assembly_cluster.py` (2). A fix is a row in the existing file (D224).

## 10. The deletion: content, removal list, gate and saving

**Before it:** main is tagged and its snapshot frozen, as the BETSE-native removal was
(`native-betse-frozen-2026-11-08`).

**The commit removes:**
- `src/cells/legacy/` and `registry/legacy_entry.py`;
- the `legacy()` call sites of §2;
- `ensemble/ionic.py`'s rows for capabilities not kept;
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
| Tiers 1+2 | 13,577 test-seconds, 2,531 s of wall (0.186 s of wall per test-second) | Point estimate −2,100 to −3,000 test-seconds (the higher figure with the physiology set retired), about 6.5–9.5 min per gate. Upper bound −9,554 (70%), about 30 min |
| G1, crossrev | 592 s, 152 s | unchanged |
| Tier 3 | 215 files, 87,166 test-seconds | 204 files reach legacy; most go |

Under Route B, the saving arrives only at the deletion, after the features.

## 11. The rename's Q3 under each route

The rename note's Q3 concerns the 18 live pieces that legacy also spells: `constant_field`, the Na/K
pump, Kv1.x, Kir2.1, Nav1.2, the leaks, the field solver, `finite_bond_assembly` and the water operator. They
make 2,272 occurrences in 102 legacy definitions and 67 in 33 code files.

| Rename Q3 option | Route A | Route B |
|---|---|---|
| (a) re-spell them in legacy too, 135 files | Consistent: the relocated cores move already re-spelled. Legacy keeps parsing, and its tests stay green through the rename's gate until the deletion about 1–1.5 weeks later | Consistent, at the cost of re-spelling files that are deleted weeks later. Legacy keeps parsing until then |
| (b) keep the 18 bare until legacy is deleted, then a second move | The relocation's neutralising commit re-spells the moved cores. The second move follows A-3. @3's definitions mix spellings for about 1–1.5 weeks | @3's definitions mix spellings for weeks, until B-4 |
| (c) delete legacy first, then rename | The rename's 18 pieces wait about 1–1.5 weeks | The rename's 18 pieces wait for the features: weeks |
| (d) live files only | Ruled out by the rename note: the parsers both families share would refuse legacy's files | Same |

**In every case:**
- **The captures** come from the pre-rename snapshot and are compared through the committed table. They
  need no re-spelling.
- **Retiring files shrinks the rewrite set.** Retiring the REF-era drivers (Q3), and the physiology set if Q2
  retires it, before the rename's move takes their files out of the rewrite set. For the REF-era drivers
  that is about a dozen of its 30 `validation/betse` files.
- **Recommended: (a)** under either route. It keeps one spelling in live code and costs a mechanical rewrite
  of files that the deletion removes later.

## 12. Risks

1. **Dispatch between landings (Route A).**
   - Unported legacy classes derive from the relocated ones: `TissueCalciumModel` from `IP3CalciumModel`,
     and `TissueModel` from `SpatialJunctionSpec`.
   - `model_for`, `to_dict` and `control_values` are subclass-first isinstance chains, so until A-3 those
     entries stay in the hub, pointing at the moved modules. Only parse entries, which match exact IDs, go
     live.
   - The alternative is exact-type checks.
2. **A tolerance that cannot test.** Without the power check, a wide band passes anything. The order check
   and the planted change are judged before the comparison.
3. **Features on the critical path (Route B).** Five features stand before the deletion, and legacy's tests
   cost gate time and maintenance meanwhile.
4. **Throwaway work (Route A).** The relocated island is discarded at A-4. Keeping it narrow (only the
   feature-blocked used cores) bounds that.
5. **BETSE conventions leaking into `src/cells`.** §5 lists them. The rule's boundary test runs in every
   gate, and the BETSE glue stays in `validation/betse`.
6. **Lost capability.** Each Drop row names what goes. Group H's pointers are corrected, so no document
   claims a capability that is gone.
7. **The rename breaks legacy before the deletion.** It is avoided by Q3 (a). Captures from the snapshot are
   unaffected.
8. **Unprobed paths.**
   - The assembly command lines' capture cost, and the cache setting that `configure_caches()` makes.
   - The tools `capture_worlds.py`, `capture.sh` and `dry_delete.py` are not written.
9. **Lane time.** The captures, the dry run, three or four full gates and tier 3 compete with the FR queue.
   FR-43, the user's top priority, keeps the timed cores.
10. **The Lean lane** may cite legacy IDs. It gets the mapping table through the user; `lean/` is not edited.

## 13. The user's questions

**Q1. The sequence.**
- (a) Route A: re-express what is expressible now, relocate only the feature-blocked used cores bitwise,
  delete legacy in about 1–1.5 weeks, then re-express the cores as the features land.
- (b) Route B: re-express directly, and delete when the last used capability is canonical.
- **Recommendation: (a).** The calcium ensemble's re-expression waits on five engine features, and B keeps
  about 600 legacy-reaching test files in every gate until they land. The interim island is narrow and
  proven bitwise, and D369 rules it out only as an end state.

**Q2. The BETSE physiology stack** (17 drivers, 58 tests, in `validation/betse/physiology`).
- (a) Retire it with its records. BETSE parity is redone later on canonical models, against saved
  outputs.
- (b) Keep it runnable. Its capabilities become uses (rows A3, A4, B6, C2 and D1, and A5 and A6 if needed), its
  BETSE glue moves into `validation/betse`, and it adds about 15–24 agent-days and G-6.
- **Recommendation: (a).** No current document claims its results, and the BETSE parity that PROGRESS
  claims already runs on `resolved_pump_tissue@1`–`@3`.

**Q3. The 18 REF-003 to REF-005 drivers, and the junction and spatial-cluster panels.**
- (a) Retire them with their records, before the rename's move.
- (b) Retire them at the deletion.
- (c) Keep them, which needs A10's families as standalone IDs.
- **Recommendation: (a).** Their evidence is not claimed (§6), and retiring them early shrinks the rename's
  rewrite set.

**Q4. The calcium ensemble's place.** D348 named it. The coverage check finds its uses in the live ensemble
runner's kinds and `docs/GPU_ENSEMBLES.md`'s qualified preparations. No current experiment plan runs it.
- (a) Keep it in scope. Its re-expression needs G-1, G-4, G-5, G-7 and G-8.
- (b) Retire it with its records, leaving the ensemble runner its live kinds (`capsid_graph@1`,
  `finite_bond_assembly@1`) and the ionic wrapper on @3 (E4).
- **Recommendation: the user's call.** If (a), Route A. If (b), legacy can be deleted after steps A-1 and A-3 alone,
  with no engine feature, in about 5–7 agent-days.

**Q5. @3's reference world, `resolved_tissue@8`.**
- (a) Keep the live catalogue model as a reference-only family, with its dispatch moved into the live
  registries.
- (b) Point @3's equivalence tests at an independent validation-side reference instead. Candidates:
  `validation/tissue/surface_kinetic_reference.py`, or NumPy forms of the laws.
- (c) Drop the cross-check.
- **Recommendation: (a) for the interim and (b) as the end state.** Its value is its independence.

**Q6. `source_decay@1`, `emt_mirna@1` and `passive_pair@1`.**
- (a) Delete all three. Retarget the conftest's 9 infrastructure users to `reaction_transport@1` or a
  minimal composite.
- (b) Re-express `source_decay@1` as a minimal canonical test world.
- **Recommendation: (a).**

**Q7. Which gaps to request** (§4): the calcium ensemble's five if Q4 (a); G-6 too if Q2 (b); G-2, G-3
and G-9 only when a consumer asks. **Recommendation:** follow Q2 and Q4.

**For the lead, not the user:**
- exact-type dispatch or hub entries in Route A (§12, risk 1);
- the manifest key;
- a GPU block after the ensemble's re-expression;
- the band's factor 2 and its rounding floor, to be fixed in the capture's record before any run.

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
