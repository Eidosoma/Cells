# Legacy port plan: the families BETSE's comparisons and the calcium ensemble use, then legacy's deletion

**Status: a plan for review, 24 November 2026, night.** Nothing in it is built, run as a gate, or decided
beyond D345, D346 and D348. It was written read-only against main at `ce4780d2`.

**Decisions it carries out:**
- **D346, amended by D348:** port the 11 legacy families that the BETSE comparisons and the calcium
  ensemble use, then delete `src/cells/legacy/` whole, in one deletion with one gate.
- **D348's correction:** `kinetic_pump_binding.py` does not import legacy.
- **The rename comes first (D345, D346).** Every live ID becomes `cells.<family>.<name>@major`. Legacy's IDs
  stay bare and frozen until the deletion. A ported family's ID is minted once, under the rename's
  families. Every ID below is a proposal, **to be named in the rename note** (branch `rename-design`).
- **BETSE's role (AGENTS.md):** BETSE is an outside reference only. Nothing named BETSE goes into `src/`.
  Parity checks stay possible later, against saved outputs, out of process.

**Records:**
- The lead's dependency analysis: `/mnt/workspaces/Cells/legacy-removal-20261124/`.
- This plan's read-only probes and inventories: `/mnt/workspaces/Cells/legacy-port-plan-20261124/`.
  - `inventory.json`: per family, its seeds, import-time closure and direct consumers, and every test file's
    class.
  - `probe.json`, `probe2.json`, `probe3.json` and `probe4.json`: the import graph, the runtime reach from
    the scope map, the closures and the test classification. Their scripts are in `tools/`.
  - `probe-capture-a/` and `probe-capture-b/`: the capture probes of §5.

Paths below are repository paths unless they start with `/mnt/`.

## 1. Summary

**The 11 decided families sit on more legacy than their IDs show.** Their import-time closure is 107 of
legacy's 321 modules and about 27,400 of its 75,600 lines. With function-level imports it is 122 modules
and 33,600 lines.
- They nest three more legacy families inside their definitions:
  - `er_calcium@1` is the store in seven of them;
  - `spatial_extracellular@2` is the ionic child of `spatial_calcium@1`–`@4` and of the cluster's base
    configuration;
  - `finite_extracellular@2` is the ionic child of `assembly_regulated_cell@1`.
- **18 of the 39 legacy-importing BETSE drivers use none of the five BETSE IDs.** They run
  `finite_extracellular@1`–`@3` and `spatial_extracellular@1`–`@2`: the REF-003 to REF-005 comparisons
  and the junction and spatial-cluster panels.
  - The lead's closure kept their modules, through its import seeds.
  - Its count of five IDs came from ID strings, though. These drivers import the models by module, and
    those families' IDs are defined in `definitions/specs.py`, outside legacy.
  - This is question Q1.

**What "port" means here (§2).** Bit for bit is attainable only by a faithful relocation: the code moves
out of `legacy/` under neutral names, its dispatch joins the live registries, and its ID is minted. That is
D188's scripted move, run for the kept families, with its import rewriter and verifier. A re-expression on
the modular core (`resolved_pump_tissue@3`, the composite, operators and kinds) cannot be bitwise. Its
blockers today include @3's {Na, K, Cl} valence table, finite fuel, and no ER compartment or
assembly-coupling law. This plan relocates first and proves the relocation bitwise. Re-expression is
question Q2.

**The proof is cheap and reuses G1's tool.** `validation/results_baseline.py save --from` captured legacy
worlds unchanged in tonight's probe on CPU 4, for a 5-step first window, cold:

| World | Seconds | Arrays |
|---|---|---|
| `resolved_tissue@12` | 76.8 | 79 |
| `spatial_calcium@1` | 22.6 | 53 |
| `resolved_calcium_energy@5` | 154.9 | 140 |
| `resolved_open_calcium_energy@1`, from a fixture, JIT off | 142.7 | 144 |

The assembly families capture through their own CPU command line (§5.2, C4).
- **The full capture is estimated at 2.5–4 CPU-hours,** about 25–40 minutes on one lane.
- **It is not for tonight:** both lanes are held and the load is about 17.
- **It runs from the pre-rename tag's frozen snapshot** (§5, §13).

**The deletion is more than the folder (§8).**
- The legacy hub also dispatches live code: `resolved_tissue@1`–`@12`, whose model is
  `cells.models.surface_kinetic`. The modern @3's tests use `resolved_tissue@8` as a reference world.
- It serves `source_decay@1`, `emt_mirna@1` and `passive_pair@1`. These parse in `definitions/specs.py`
  but run on legacy models. `source_decay@1` is the shared conftest's default world.

**Tests (§7).** 195 of the 891 tier-record test files import legacy directly; that is D346's count. 10 more
name a legacy ID themselves. 401 reach legacy only through a fixture, shared driver or configuration.
- At runtime, 388 of the scope map's 662 files load legacy, and 354 of those load the hub. Most of those
  loads are dispatch misses, not uses.
- The definitive list is a scratch dry-run deletion with a tiers run (§7.4). Its command is given; it has not
  been run.

**Gate time (§9).** G1's 113 worlds and crossrev's sets name no legacy ID, so the deletion does not shorten
them.
- **Tiers 1+2:** the files certain or likely to go hold about 2,100 of 13,577 test-seconds, about 15%, or
  about 4 minutes of a lane's wall. The upper bound is 9,554 test-seconds (70%).
- **Tier 3** shrinks most: 204 of its 215 recorded files, 85,147 of 87,166 test-seconds, reach legacy.
- The measured figure comes from the dry run.

**Cost (§10).**
- The relocation: about 8–11 agent-days, plus about 10–12 lane-hours of gates and captures. Tier 3's
  deliberate run is the largest part.
- A full re-expression: a further 15–25 agent-days, judged at tolerances, not bitwise.

**The user's questions (§12):**
- Q1, scope beyond the 11;
- Q2, relocation then re-expression;
- Q3, which BETSE drivers stay runnable;
- Q4, the `resolved_tissue` majors kept;
- Q5, the three inline families and the conftest world.

## 2. What a port is here, and what "bit for bit" covers

**Relocation (R), the proving step.**
- Each kept module moves out of `legacy/` into a neutral home, by a move map and D188's tool,
  `scripts/source_moves.py`: one map, one import rewriter, one verifier. Its maps are kept beside move 1's
  and move 2's in `scripts/moves/`.
- **The verifier** checks that every changed file equals the rewriter applied to its old content.
- **Dispatch:** each kept family's entries in `legacy/registration.py` (parse, `model_for`, `to_dict`,
  `control_values`, the command line and the ensemble hook) move into the live dispatch points
  (`definitions/specs.py`, `registry/models.py`, `execution/schedule.py`, `__main__.py`,
  `ensemble/families.py`) and the model table.
- **IDs:** its ID is minted under the rename's families. The legacy ID is then refused at parse, with a
  message naming the new one, as the rename's table does. There are no aliases (D345); superseded
  mechanisms retire when the replacement lands.
- **Pruning** is separate and behaviour-preserving: branches no kept family reaches are cut, for example the
  cluster's mobile-channel, mobile-pump, mitochondria, network-transport and finite-energy branches,
  which serve only the `resolved_*` derived families.
- **Why it can be bitwise:** the kernels, their evaluation order and the compiled programs' inputs are
  unchanged. D188's moves were gated on G1 at 113 of 113, bitwise.

**Re-expression (E), a later step per family.**
- The family becomes a declared structure of @3 or of the composite: registered channel, cycle, route and
  reaction laws, operators and kinds.
- **It cannot be bitwise.** `docs/ARCHITECTURE.md` records A7's summation order moving ledger and
  diagnostic arrays at rounding. The registered PMCA (`cells.ca_atp_mass_action_positive@1`) already uses
  another standard state (Δg0 − RT ln 1000).
- **Today's blockers:**
  - @3's valence table is {Na, K, Cl}, which refuses every calcium-permeant law;
  - gate-free laws give no opening under @3's template, which excludes 8 instantaneous Morris–Lecar laws;
  - the channel-law seam reads voltage only;
  - finite fuel is a target, not a case (`ARCHITECTURE.md`, material identity and fuel);
  - there is no ER store or assembly-coupling law.
- So E is judged at a declared tolerance against R's bitwise-proven outputs. That is Q2.

**Bit for bit covers numeric arrays only.**
- **Scalar families:** every array `results_baseline.py save` writes per world: times, `history.*`,
  `observations.*`, `diagnostics.*`, and the final checkpoint's state, time and step.
- **Assembly families:** every array of `checkpoint/state.npz` (`pool_*`, `ionic_*`, `tick`, `segments`,
  `availability_exposure_s`, `fault`) and the numbers in `observations/tick-*.json` and `result.json`.
  They are compared as loaded arrays, not as file digests.
- **A refusal is an output.** Its type must match, and its message must match after the ID mapping.
  `results_baseline.compare` needs one validation-only option for that: an ID-mapping file applied to
  refusal messages.
- **Not compared:**
  - model, law, observer and domain ID strings, which go through the mapping table;
  - source paths and SHA-256 values of source files, which drivers record, for example `trajectory.py`'s
    `source_sha256`;
  - runtime identity;
  - timestamps and wall times.
- **The environment must match:** the same `venv-cpu` (jaxlib, XLA flags), CPU only, float64,
  single-thread BLAS, cold compilation cache and one CPU per shard. `results_baseline`'s manifest records
  it, and a mismatch voids the comparison rather than failing it.

## 3. Scope

### 3.1 The 11 decided families

| # | ID (legacy, frozen) | Spec / parse | Model | Import-time closure in legacy | Notes |
|---|---|---|---|---|---|
| F1 | `resolved_tissue@12` | `definitions/surface_kinetic_spec.py` (live) | `legacy/models/surface_hcn_extra.py` → `surface_cav.py` → live `models/surface_kinetic.py` | 2 modules, 73 lines | The model and the 56-law catalogue are live |
| F2 | `resolved_calcium@11` | `legacy/core/surface_calcium_spec.py` | `legacy/models/surface_calcium_hcn_extra.py` → `surface_calcium.py` | 38 modules, 11,123 lines | Children: ionic F1, `er_calcium@1` stores |
| F3 | `resolved_calcium_energy@5` | `legacy/core/surface_calcium_energy_spec.py` | `legacy/models/surface_calcium_energy_hcn_extra.py` → `surface_calcium_energy.py` | 44 modules, 13,438 lines | Parse rewrites @5 to F2 before decoding (spec:367–378) |
| F4 | `resolved_open_calcium@1` | `legacy/core/surface_open_calcium_spec.py` | `legacy/models/surface_open_calcium.py` → `open_calcium_runtime.py` | 58 modules, 17,979 lines | An adapter over F2 |
| F5 | `resolved_open_calcium_energy@1` | `legacy/core/surface_open_calcium_energy_spec.py` | `legacy/models/surface_open_calcium_energy.py` | 58 modules, 17,986 lines | The same adapter over F3 |
| F6 | `spatial_calcium@1` | `legacy/core/spatial_calcium_spec.py` | `legacy/models/spatial_calcium.py` | 26 modules, 8,157 lines | Subclasses `spatial_extracellular@2`; `er_calcium@1` stores |
| F7 | `spatial_calcium@2` | `legacy/core/plasma_calcium_spec.py` | `legacy/models/plasma_calcium.py` | 28 modules, 8,771 lines | Over F6 |
| F8 | `spatial_calcium@3` | `legacy/core/gated_calcium_spec.py` | `legacy/models/gated_calcium.py` | 30 modules, 9,204 lines | Over F7 |
| F9 | `spatial_calcium@4` | `legacy/core/ip3_calcium_spec.py` | `legacy/models/ip3_calcium.py` | 34 modules, 9,471 lines | Over F8 |
| F10 | `assembly_regulated_cell@1` | `legacy/assembly_cell/spec.py` | `legacy/assembly_cell/`, `legacy/ensemble/coupled.py` | 12 modules, 3,300 lines (+91 at function level) | Ionic child `finite_extracellular@2`; pool `finite_bond_assembly@1` (live, `assembly_pool/`) |
| F11 | `assembly_regulated_cluster@1` | `legacy/assembly_cluster/spec.py` | `legacy/assembly_cluster/`, `legacy/ensemble/cluster.py` | 83 modules, 21,567 lines | Ionic child `spatial_extracellular@2` or F6–F9 |

The union of the 11 import-time closures is 107 modules and 27,414 lines.
- **Pruning** the cluster's five branches for the `resolved_*` families is estimated to remove about 37
  modules and 7,800 lines. The specs and models of mobile channels, mobile pumps, repair, redistribution,
  water and mitochondria go with them.
- **That leaves about 70 modules and 20,000 lines.** The builder's first step computes the exact figure.
- **Two modules outside the closure are reached only lazily, through the hub's ensemble hook:**
  `legacy/ensemble/cluster.py` and `coupled.py` (461 lines). F10 and F11 need them.

### 3.2 Layers the 11 need underneath: nested in definitions or inherited in code

| ID or layer | Why it is needed | Where it lives |
|---|---|---|
| `er_calcium@1` | The `stores` child of F2, F3 and F6–F9 (for example `configs/resolved_hcn_extra_calcium.json` and `configs/spatial_calcium_cluster.json`) | `legacy/core/er_spec.py`, `legacy/models/er_calcium.py`, over `compartment_reactions@1` (`legacy/core/reaction_spec.py`, `legacy/models/compartment_reactions.py`) |
| `spatial_extracellular@2` | The ionic child of F6–F9 and of `configs/assembly_regulated_cluster.json`; F6's spec class subclasses it | `legacy/core/spatial_junction_spec.py`, `legacy/models/spatial_junction.py`, over `finite_extracellular@3`, `@1` and `spatial_extracellular@1` |
| `finite_extracellular@2` | The ionic child of F10 (`configs/assembly_regulated_cell.json`) | `legacy/core/kinetic_finite_spec.py`, `legacy/models/kinetic_finite_extracellular.py`, `kinetic_finite_bounds.py` |
| `resolved_tissue@12` (F1) | The ionic child of F2 and F3 | as F1 |
| `resolved_calcium@1`–`@10` and `resolved_calcium_energy@1`–`@4` bases | F2's and F3's models inherit their code from `surface_calcium.py`, `surface_calcium_catalog.py`, `surface_calcium_cav.py` and `surface_energy_spec.py`, not their IDs | legacy models and specs, in the closure |
| older families' helpers | `bioelectric_spec`, `multispecies_spec` and `multispecies_membrane`, `voltage_gated_spec` and `voltage_gated_membrane`, `physical_ionic_graph_spec` and its model: imported by the extracellular line, as helpers only | legacy, in the closure |

The spec classes of `finite_extracellular@1`–`@3` and `spatial_extracellular@1`–`@2` are already live
(`definitions/specs.py:294–402`). Only their parse modules and models are legacy.

### 3.3 IDs consumers use beyond the 11

| ID | Consumers | Note |
|---|---|---|
| `finite_extracellular@1` | 13 BETSE drivers (§4.8) | Not one of the five; Q1 and Q3 |
| `finite_extracellular@2` | 3 BETSE drivers; F10's child | Q1 and Q3 |
| `finite_extracellular@3` | `validation/betse/junction_coupled/test_coupled.py`, `spatial_cluster/test_spatial.py` | Q1 and Q3 |
| `spatial_extracellular@1`, `@2` | `validation/betse/spatial_cluster/test_spatial.py`; `@2` is F6's and F11's child | Q1 and Q3 |
| `compartment_reactions@1` | 3 BETSE physiology drivers (`physiology_protein_loop.py`, `physiology_protein_interval_accounting.py`, `physiology_protein_interval_arrays.py`) | Under `er_calcium@1` anyway |
| `resolved_tissue@1`–`@11` | Live code, legacy dispatch. 14–49 files each name them; @3's reference worlds use `@8` (`validation/tissue/surface_pump_v3_fixtures.py:107–129`, for example `tests/unit/test_surface_pump_v3_gates_equivalence.py`); the BETSE physiology references name `@1` | Q4 |
| `source_decay@1`, `emt_mirna@1`, `passive_pair@1` | The shared conftest (`configs/single_cell_pulse.json`, 10 test files), their own tests | Q5 |
| Legacy process helpers, not model IDs | `tissue_profiles.py` (static profiles), `processes/tissue_removal.py`, `processes/extracellular_face_transport.py`, `processes/tissue_target_selectors.py`, `processes/geometry_operator_binding.py`, `core/tissue_profile{,_composition}_preparation.py`, `multispecies_spec.identifier` | Used directly by BETSE drivers. The target selectors, geometry binding and the two profile preparations are in F4's closure, and `multispecies_spec` is in every family's; `tissue_profiles.py` (263 lines), `tissue_removal.py` (520) and `extracellular_face_transport.py` (751) are outside every closure |

**`ensemble/ionic.py` admits 98 legacy IDs** as ionic children. Tests and drivers exercise
`spatial_extracellular@2` and F6–F9 under F11, and `finite_extracellular@2` under F10. The rest go with
the deletion: the cluster's spec (`legacy/assembly_cluster/spec.py:139–175`) admits 33 legacy types, and
the ported cluster admits only the exercised ones.

## 4. The families

Each entry gives:
- the legacy source and its closure (§3.1);
- the physics, with its sources as the code and docs cite them;
- the consumers, grouped (the full lists are in `inventory.json`);
- the target home, with neutral names, and the proposed ID;
- the bitwise check, whose world list and commands are in §5.

The proposed ID form is **`cells.model.<legacy name>@<legacy major>`**: the family prefix only, with
names and majors kept. It keeps lineage readable and makes the capture's mapping trivial. Descriptive new
names at major 1 are the alternative, for the rename note to choose.

### 4.1 F1 `resolved_tissue@12`: the 56-law gated tissue

- **Physics.** `models/surface_kinetic.py` over `resolved_tissue@1`:
  - channel gates, with transfer and heat per species;
  - a junction gate;
  - the Na/K pump `nak_atp_mass_action_positive@1` on maintained reservoirs, with `pump_cycles`, pump heat
    and `metabolic_work_pJ`;
  - the energy ledger: channel and pump heat, less work;
  - RK4 step ceilings of 1.25, 2.5 and 25 µs.
- **@12 over @11** adds `hcn_leak_open@1`, `hcn2_camp_m@1` and `hcn4_camp_m@1` (codes 53–55,
  `laws/channels/hcn_extra_channels.py`).
- **Sources.** The law forms come from BETSE 1.5.0's channel classes (Pietak and Curry, 2025, as
  `laws/channels/kv1p1_mh2.py` cites them), for example `vg_funny.py` at 5269a714
  (`docs/TISSUE_RETURN_CURRENT.md`). Primary papers are cited second-hand only.
- **What the legacy wrappers add.** `legacy/models/surface_hcn_extra.py` (32 lines) and `surface_cav.py`
  (41 lines) add the MODEL_ID, OBSERVER_ID `resolved_hcn_extra_accepted_grid@1`, STAGE_DOMAIN_ID
  `positive_resolved_hcn_extra_actual_controls@1`, the layout type, the channel axes and `working_size`.
  The layout type alone selects the 56-law catalogue.
- **Consumers.** 55 files name the ID or import its modules:
  - src: `ensemble/ionic.py`;
  - BETSE: 7, in the physiology set;
  - tests: 9;
  - other validation: 37, the derived families' references, which go.
- **Target.** No relocation of the model. The wrappers' constants become a per-major table in
  `models/surface_kinetic.py`. The `resolved_tissue` dispatch moves into the live dispatch points
  (`registration.py:778–807, 1196–1211, 1444–1447, 1946–1949`). Which majors keep IDs is Q4.
- **ID:** `cells.model.resolved_tissue@12`, to be named in the rename note.
- **Bitwise check.** Set `F1`: `configs/resolved_hcn_extra_ionic.json`,
  `configs/resolved_active_excision_source.json`, and
  `validation/tissue/hcn_extra_catalog_fixtures.definition("ionic", arm)` for its six arms. If Q4 keeps
  them, add the `@8` reference world `surface_pump_v3_fixtures.reference()` and one `@1` world.
- **Cost:** about 8 worlds at about 80–120 s each, roughly 15 CPU-minutes. This is extrapolated from the
  probe's 76.8 s.

### 4.2 F2 `resolved_calcium@11`: 56-law tissue with owned calcium and ER

- **Physics:**
  - one `er_calcium@1` store per cell, 1–16 per world, sharing cytosol volume and free ions with the ionic
    child;
  - per membrane, PMCA `plasma_calcium_pump_positive@1`, NCX `ncx_3na_1ca_symmetric_barrier@1` and one
    Cav1.2 population `cav1p2_m2h@1`;
  - the IP3 factor `ip3_er_release@1` on ER release;
  - the energy ledger to 1e-9 pJ, the chemical ledger, ownership and three work identities;
  - a finite exterior only.
- **The ER store (`er_calcium@1`, §3.2):**
  - an ER capacitor, V = V0 + F·1e-15/C·Σ z Δn;
  - a GHK leak per species;
  - the pump `er_calcium_pump_positive@1` with the `maintained_mM_quotient@1` convention;
  - the calcium-gated release `er_calcium_release@1`;
  - buffers by `ideal_detailed_balance_mass_action@1`.
- **Sources:**
  - BETSE 1.5.0's `pumpCaATP`, `pumpCaER`, `Cav1p2` (`vg_ca.py`) and `EndoRetic.channels`
    (`docs/PLASMA_CALCIUM.md`, `docs/ER_CALCIUM.md`);
  - NCX is a synthetic symmetric-barrier law; Hilgemann and colleagues (1992) support only its 3:1
    electrogenic reversal (`PLASMA_CALCIUM.md`);
  - Tran et al. (2009) are cited as a contrast only.
- **Consumers.** 36 files:
  - BETSE: 11 (physiology);
  - tests: 8, among them `tests/unit/test_hcn_extra_catalog.py` (tier 3, 459 s, 106 passed) and
    `test_surface_calcium_catalog.py`;
  - other validation: 16;
  - src: `ensemble/ionic.py`.
- **Target:** `models/calcium/` (`surface.py`, `surface_catalog.py`, `surface_cav.py`, `hcn_catalog.py`)
  and `definitions/calcium/surface_spec.py`. The legacy-only IP3 law
  (`legacy/processes/ip3_release.py`) moves to `laws/reactions/ip3_release.py`.
- **ID:** `cells.model.resolved_calcium@11`. Its store's ID is `cells.model.er_calcium@1`.
- **Bitwise check.** Set `F2`: `configs/resolved_hcn_extra_calcium.json`,
  `configs/resolved_calcium_excision_source.json` and `hcn_extra_catalog_fixtures.definition("calcium",
  arm)` for the six arms.
- **Cost:** about 8 worlds at about 150 s, roughly 20 CPU-minutes.

### 4.3 F3 `resolved_calcium_energy@5`: with finite cellular ATP/ADP/Pi

- **Physics.** Per-cell finite ATP/ADP/Pi pools:
  - pool law `finite_atp_adp_pi_transformed@1`;
  - regeneration ports `driven_atp_regeneration_tanh@1`;
  - the Na/K pump on `finite_energy_pool@1`;
  - `finite_atp_pmca_positive@1` and `finite_atp_er_1ca_positive@1`, one Ca and one ATP per cycle, with
    ΔG0 shifted by −RT ln 1000 (`legacy/processes/finite_calcium_pumps.py`).
- **Ledgers:** pool free energy, material, adenylate, phosphorus, per-cell pool energy and regeneration
  work.
- **Sources:** none external. It is a synthetic port, "rather than a mitochondrial or experimental fit"
  (`docs/FINITE_ENERGY_POOLS.md`); the conversions are in `docs/FINITE_CALCIUM_PUMPS.md`.
- **Consumers.** 49 files:
  - BETSE: 12;
  - tests: 13, five of them tier 1 (for example `test_surface_calcium_energy_water.py`, which goes);
  - other validation: 23.
- **Target:** `models/calcium/energy.py`, `energy_hcn_catalog.py` and `definitions/calcium/energy_spec.py`.
  The pool and pump laws move from `legacy/processes/finite_energy.py` and `finite_calcium_pumps.py` to
  `laws/pumps/` and `laws/reactions/`.
- **ID:** `cells.model.resolved_calcium_energy@5`. The four law IDs go to the cycle, reaction and
  free-energy families, for the rename note.
- **Bitwise check.** Set `F3`: `configs/resolved_hcn_extra_energy.json` and
  `hcn_extra_catalog_fixtures.definition("energy", arm)` for the six arms.
- **Cost:** measured at 154.9 s for 5 steps; about 7 worlds, roughly 20 CPU-minutes.

### 4.4 F4 and F5 `resolved_open_calcium@1`, `resolved_open_calcium_energy@1`: static open exterior

- **Physics.** No new rate law or state over F2 and F3. They add:
  - the policies `static_declared_ideal_chemical_and_voltage_reservoirs@1` and
    `hard_global_ionic_moiety_ceilings_fmol_every_stage@1`;
  - the closure `complete_owned_calcium_static_reservoir_material_electrode_work@1`;
  - ceilings checked at every stage;
  - a loss bound and steps of at most 1.25 µs (`legacy/models/open_calcium_{runtime,reservoirs,admission}.py`).
- **Sources:** none; synthetic (`TISSUE_RETURN_CURRENT.md`).
- **The closure also pulls in** the profile and geometry helpers, nine modules of about 4,200 lines:
  `owned_calcium_profile_binding`, `surface_profile_interventions` (spec and model),
  `geometry_{profile,tissue}_preparation`, `tissue_profile{,_composition}_preparation`,
  `tissue_target_selectors` and `geometry_operator_binding`.
- **Consumers.** 26 and 27 files:
  - BETSE: 8 and 9 (physiology: `physiology_boundary_voltage.py`, `physiology_temperature.py`,
    `physiology_boundary_voltage_view.py`, `physiology_temperature_view.py` and the open arrays);
  - tests: `tests/unit/test_open_calcium.py` (tier 2), `test_open_calcium_bath_events.py` (tier 3), and
    three fixtures under `tests/`;
  - other validation: 12.
- **Target:**
  - `models/calcium/open.py`, `open_energy.py`, `open_runtime.py`, `open_reservoirs.py`, `open_admission.py`;
  - the profile helpers go to `definitions/profiles/`;
  - `tissue_target_selectors` and `geometry_operator_binding` go to `numerics/`.
- **IDs:** `cells.model.resolved_open_calcium@1` and `cells.model.resolved_open_calcium_energy@1`.
- **Bitwise check.** Set `F45`: `validation/tissue/open_calcium_fixtures.definition(family, case)` for the
  five cases of each family, plus `depleted=True` for energy, 11 worlds.
- **Cost.** The fixtures run with JIT off. A 5-step window measured 142.7 s, and eager cost grows with
  steps, so these worlds capture 16 steps: estimated 40–90 CPU-minutes, the largest item.

### 4.5 F6–F9 `spatial_calcium@1`–`@4`: the calcium ensemble's ionic families

- **Physics:**
  - **F6:** one ER store per cell (1–16 per world). `amount_increment` becomes a whole-cell exchange
    ledger, so ER exchange and binding cannot charge the plasma capacitor. Ownership residual and charge
    checks; energy balance to 1e-9 pJ; steps of at most 50 µs with h·loss at most 0.25. No new law
    (`docs/SPATIAL_CALCIUM.md`).
  - **F7:** per-membrane PMCA and NCX, with `plasma_pump_cycles`, `plasma_exchange_cycles` and
    `plasma_dissipated_energy_pJ`, and schedules.
  - **F8:** one Cav1.2 per membrane (`cav1p2_m2h@1`, 298.15 K only), with GHK flux at z = 2 and
    P = max·abundance·availability·m²h.
  - **F9:** per-cell binding to free IP3 multiplies ER release by a/(1 + a) at every stage; no new state.
- **Sources:**
  - F7 to F9 as F2: BETSE 1.5.0's `pumpCaATP`, `Cav1p2` and the IP3 Hill factor; NCX synthetic;
  - F6 has none ("no biological or native trajectory calibration", `legacy/models/spatial_calcium.py:544–547`).
- **Consumers:**
  - tests: `test_spatial_calcium.py` (tier 3, 475 s), `test_plasma_calcium.py`, `test_gated_calcium.py`,
    `test_ip3_calcium.py` and `test_tissue_calcium.py` (tier 3);
  - ensemble validation: `validation/ensemble/cluster_matrix.py` and `parallel_cluster.py`, which requires
    `@4`;
  - frozen evidence: `/mnt/workspaces/Cells/{spatial,plasma,gated,ip3}-calcium-2026*`.
- **Evidence registrations record pre-D188 source paths,** so their source gates already refuse today's
  tree. Re-running old evidence is not a path the port needs.
- **Target:** `models/calcium/spatial.py`, `plasma.py`, `gated.py`, `ip3.py` and
  `definitions/calcium/{spatial,plasma,gated,ip3}_spec.py`. NCX and Cav1.2 stay in their live law modules.
- **IDs:** `cells.model.spatial_calcium@1`–`@4`.
- **Bitwise check.** Set `F69`: `configs/{spatial,plasma,gated,ip3}_calcium_cluster.json`, 200 steps each.
- **Cost:** measured 22.6 s for `@1`; roughly 3–5 CPU-minutes for the four.

### 4.6 F10 `assembly_regulated_cell@1`: one assembly-gated channel in a finite ionic cell

- **Physics:**
  - coupling law `root_component_has_cycle@1`: the channel is available when popcount(bonds) ≥
    popcount(occupied);
  - the assembly topology sets availability over each segment, and ionic state never feeds back;
  - RK4 split at events on a fixed grid;
  - state `CoupledState(pool, ionic, tick, segments, availability_exposure_s, fault)`;
  - one cell, one channel and constant controls.
- **Sources:** the base capsid model is Asor et al., Nature (2026) (`docs/CAPSID_ASSEMBLY.md`). The
  coupling is a stated hypothesis.
- **Consumers:**
  - src: `ensemble/cli.py`, `families.py` (`TODAY`, `_older(...)`) and `worker.py`;
  - tests: `test_assembly_cell.py` (tier 3, 561 s; its recorded outcome has 1 failure), and
    `test_assembly_worker_source.py` and `test_integrated_ensemble.py`;
  - validation: `validation/assembly/cluster_partition_replay.py` and `qualify_cell.py` (its default case),
    and five under `validation/ensemble/` (`parallel_cluster.py`, `rounding_cluster.py`, `step_cluster.py`,
    `test_gpu_screen.py`, `test_rounding_cluster.py`).
- **Target:** `models/assembly_regulation/` (`cell_spec`, `cell_kernel`, `cell_engine`, `cell_io`,
  `ensemble_coupled`). The coupling law goes to `laws/assembly/root_component_has_cycle.py`, and the
  ensemble's adapter enters the model table.
- **IDs:** `cells.model.assembly_regulated_cell@1`; the coupling law's family is for the rename note.
- **Bitwise check.** Set `E10`:
  `cells assembly-cell run configs/assembly_regulated_cell.json --backend cpu --until T` (§5.2, C4).
- **Cost:** estimated at 3–8 CPU-minutes, from the tier-3 file's 561 s for six tests.

### 4.7 F11 `assembly_regulated_cluster@1`: per-cell assembly pools over an ionic tissue

- **Physics:**
  - pools are owned per cell, with seeds (base + stream) mod 2³²;
  - the clock is the union of all cells' events and control changes;
  - per-owner modulation;
  - `lax.map` over worlds keeps the bits fixed (`legacy/assembly_cluster/kernel.py:101–127`);
  - it adds `aggregate`: per-cell and per-model checks with Wilson intervals.
- **Sources:** none external.
- **Consumers.** 56 files:
  - src: `ensemble/cli.py`, `families.py`;
  - 13 ensemble validation files: `validation/assembly/qualify_cell.py` and `cluster_partition_replay.py`;
    `validation/ensemble/cluster_matrix.py`, `parallel_cluster.py`, `parallel_kernel.py`,
    `rounding_cluster.py` and `step_cluster.py`; and `test_energy_steps.py`, `test_gpu_screen.py`,
    `test_larger_screen.py`, `test_parallel_cluster.py`, `test_rounding_cluster.py` and
    `test_step_cluster.py`. `profile_cluster.py` and `tile_benchmark.py` reach it through these;
  - tests: `test_assembly_cluster.py` (tier 3, 179 s, recorded with 2 failures), `test_assembly_controls.py`
    (tier 1), `tests/integration/test_assembly_cluster_gpu.py`, and about 30 derived-family tests that go.
- **Target:** `models/assembly_regulation/` (`cluster_spec`, `cluster_kernel`, `cluster_engine`,
  `cluster_controls`, `ensemble_cluster`). The `resolved_*` branches are pruned.
- **ID:** `cells.model.assembly_regulated_cluster@1`.
- **Bitwise check.** Set `E11`: `cells assembly-cluster run CONFIG --backend cpu --until T` for
  `configs/assembly_regulated_cluster.json` and the four `configs/assembly_regulated_*calcium_cluster.json`.
- **Cost:** estimated at 15–25 CPU-minutes.

### 4.8 The BETSE drivers (39 import legacy), by group

| Group | Files | Legacy used | Bearing on the port |
|---|---|---|---|
| Physiology (17) | `validation/betse/physiology/` (`core/`: boundary voltage, initial preparation, perturbation remap, protein interval accounting, protein loop, temperature, tissue binding, random profile preparation; `models/`: active-temperature arrays and open arrays, boundary-voltage, permeability and temperature views; `numerics/`: protein electrical and interval arrays; `physiology_initial_preparation_io.py`, `random_tissue_profiles.py`) | F1–F5 spec classes and models; the `surface_calcium` and `surface_calcium_energy` bases; `compartment_reactions`; `kinetic_finite_extracellular.pump_parameters`; `tissue_profiles`, `tissue_target_selectors`, `tissue_removal`, the profile preparations | Retargeted by the move map, if they stay runnable (Q3); 58 tests in `tests/betse_physiology/` follow them |
| REF-003 to REF-005 comparisons, and the junction and spatial-cluster panels (18) | `alignment.py`, `cluster_alignment.py`, `trajectory.py`, `test_trajectory.py`, `test_cluster.py`, `channel_feedback_pilot/`, `channel_history_preflight/`, `channel_loop_preparation/` (2), `channel_release_design/`, `channel_release_pilot/`, `channel_transport_preflight/` (2): `finite_extracellular@1`. `pump_matched_pilot/` (2), `junction_trajectory/test_trajectory.py`: `@2`. `junction_coupled/test_coupled.py`: `@3`. `spatial_cluster/test_spatial.py`: `spatial_extracellular@1`, `@2`, `finite_extracellular@3` | None of the five IDs | They need Q1 option (b), or they retire with their saved outputs (Q3). BETSE runs in its own process: `trajectory.py`'s Cells worker, for example, refuses if BETSE was imported |
| Helpers (4) | `native_environment_paths.py` (face transport), `native_geometry_operators.py` (geometry binding), `native_profile_conventions.py` (target selectors), `emulator/spatial_spec.py` (`identifier`) | Legacy process code imported into `validation/` | Under AGENTS.md, physics the engine lacks must not live in `validation/`. They follow whatever src home their helper gets, or retire with the drivers they serve |

`validation/betse/physiology/core/physiology_active_temperature_compilation.py` names the IDs without
importing legacy, so it is a 40th consumer.

## 5. Captures: what is saved from legacy before any change, and how

### 5.1 When and from what

- **The captures run from the frozen snapshot of the pre-rename tag,** D346's step 2, "tag main". The
  rename rewrites live law IDs that legacy definitions name: `kv1p5_mh@1`, `constant_field@1`,
  `cav1p2_m2h@1`, `er_calcium_pump_positive@1` and the rest. Legacy specs also import law-ID constants
  from live modules (`calcium_gates.LAW_ID`, `plasma_calcium.PUMP_LAW` and `EXCHANGER_LAW`).
- **A snapshot is immutable,** so the captures can run any time after the tag, when a lane is free, and
  need not precede the rename's landing.
- **Recommended:** a second capture of the same worlds on the renamed main before the first port landing.
  It shows bitwise that the rename moved no legacy number, and its definitions carry the new law IDs that
  the port's comparison feeds back. It costs the same lane time.

### 5.2 Steps and commands

- **C0: freeze the tag's snapshot.** From a clean worktree at the tag (TAG below), in about a minute:
  ```
  python scripts/gates/freeze_snapshot.py <worktree-at-TAG> /mnt/workspaces/Cells/legacy-port-20261125/snapshot --scope full --require-clean
  ```
- **C1: write the world definitions.** A small validation tool, `validation/legacy_port/capture_worlds.py`,
  lands before the tag as a validation-only change. It writes `ORIGIN/<set>/<world>.json` (`{"name",
  "definition"}`) from §4's configs and fixture builders, freezing the definitions as G1's `--from` does.
  - It imports fixtures that the deletion will remove, so it runs on the snapshot.
  - No compile; under a minute:
  ```
  cd SNAP && PYTHONPATH=SNAP/src:SNAP JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 /mnt/workspaces/Cells/venv-cpu/bin/python -B validation/legacy_port/capture_worlds.py ORIGIN
  ```
  - If it misses the tag, it runs from the checkout with `PYTHONPATH=SNAP/src:SNAP`, and the run records
    both revisions.
- **C2: capture the scalar families (F1–F9 and the run paths) on one lane.** The capture logic is in a
  script file, never an inline `bash -c` (systemd expands `${...}`).
  - `validation/legacy_port/capture.sh` shards the sets over the lane's eight CPUs, one CPU per shard
    (`taskset`), as `gate.sh` shards G1.
  - Each shard runs:
    ```
    PYTHONPATH=SNAP/src:SNAP JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /mnt/workspaces/Cells/venv-cpu/bin/python -B SNAP/validation/results_baseline.py save OUT/part-K --sets <sets> --from ORIGIN --max-steps 200
    ```
    The eager F4 and F5 worlds use `--max-steps 16`.
  - The parts are then merged with `scripts/gates/gate_steps.py g1-merge`.
  - On lane A:
    ```
    scripts/run_detached.sh legacy-capture 24G --cpus 0-3,16-19 --oom-first --wait-headroom 26G -- flock /mnt/workspaces/Cells/locks/gate-cores-0-3.lock bash SNAP/validation/legacy_port/capture.sh SNAP ORIGIN /mnt/workspaces/Cells/legacy-port-20261125/capture-tag
    ```
  - Lane B is the same with `--cpus 8-11,24-27` and `/mnt/workspaces/Cells/locks/gate-cores-8-11.lock`.
    Never CPUs 12–15 or 28–31.
  - `run_detached.sh` disables JAX's compilation cache in the unit (D321), so the capture is cold.
  - The probes stayed within their 4 GB scope caps; their peaks were not measured. 3 GB per shard is
    assumed, and the first shard's journal peak checks it.
- **C3: the run paths.** One world per scalar family goes through every run path that
  `results_baseline.run_paths` exercises. A refused path is captured as a refusal, which must match after
  the port. This is set `paths` in the same unit.
- **C4: the assembly families on the CPU.** `cells ensemble run` is GPU-only (`ensemble/worker.py:95`), so
  the capture uses each family's own command line:
  ```
  CELLS_OUTPUT_ROOT=OUT PYTHONPATH=SNAP/src:SNAP JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 /mnt/workspaces/Cells/venv-cpu/bin/python -B -m cells assembly-cell run SNAP/configs/assembly_regulated_cell.json --output OUT/E10/cell --backend cpu --until T
  CELLS_OUTPUT_ROOT=OUT ... -m cells assembly-cluster run SNAP/configs/<config>.json --output OUT/E11/<name> --backend cpu --until T
  ```
  - The cluster runs on the base config and the four calcium configs.
  - The outputs are `checkpoint/state.npz`, `observations/tick-*.json`, `result.json` and
    `completion.json` (which holds digests).
  - **T** is the horizon at which one run takes at most about 5 minutes on one CPU. The tool times one run
    first and records T.
  - These lines join `capture.sh` as a ninth queue on the same lane.
- **C5: the compare, after each port landing.**
  ```
  python SNAP2/validation/results_baseline.py compare CAPTURE PORTED --output compare.json
  ```
  - This is bitwise by default, with the ID-mapping option of §2. PORTED is saved by the same command as
    C2, from the ported head's snapshot SNAP2, `--from` the mapped definitions.
  - `validation/legacy_port/compare_assembly.py` compares the assembly arrays and numbers, excluding
    provenance fields.

### 5.3 Cost and placement

| Item | Worlds | One-CPU estimate | Basis |
|---|---|---|---|
| F1 | ~8 | ~15 min | 76.8 s measured for one 5-step window |
| F2 | ~8 | ~20 min | extrapolated from F3 |
| F3 | ~7 | ~20 min | 154.9 s measured |
| F4, F5 | 11 | 40–90 min | 142.7 s measured, eager; 16 steps |
| F6–F9 | 4 | 3–5 min | 22.6 s measured for `@1` |
| Run paths | ~9 | ~25 min | G1's run-paths set, scaled |
| F10, F11 | 6 | 20–35 min | tier-3 seconds of their test files |
| **Total** | **~53** | **2.5–4 CPU-hours** | **one lane, 8 shards: about 25–40 min wall, bounded by the slowest eager shard** |

- **Placement:** lane A or B under its lock, like a gate.
- **Tonight:** nothing heavy runs. Both lanes are held by gates and the load is about 17. C0 and C1 are
  light, but C1's tool must land first. The probes above ran on CPU 4 under the timed lock, each under a
  4 GB scope cap.
- **GPU.** The ensemble's GPU tests compare the GPU with a same-run CPU at 3e-10 relative, not bitwise. The
  L4 has a recorded bitwise failure across the compilation cache, and D336 refuses the composite on a GPU.
  - So the CPU capture is the proof. After F11's landing, the GPU tests (`test_assembly_cluster_gpu.py`,
    `test_integrated_ensemble_gpu.py`, and the `CELLS_*_TEST_BACKEND=gpu` cases) run once at their own
    criteria, in an announced GPU block (`gpu.reserved`).
  - No GPU capture is planned.

## 6. Order of ports and dependencies

| Step | Content | Depends on | Lands with |
|---|---|---|---|
| S0 | `validation/legacy_port/` capture tools; tag; C0–C4 | — | before the tag: a no-src landing (D223) |
| S1 | F1: the `resolved_tissue` dispatch into the live registries, and the wrappers folded | the rename | L1 |
| S2 | The nested layers: `compartment_reactions@1`, `er_calcium@1`, the extracellular line (`finite_extracellular@1`–`@3`, `spatial_extracellular@1`–`@2` as modules, with their IDs per Q1) and the old families' helpers | the rename | L1 |
| S3 | F6–F9 | S2 | L1 |
| S4 | F2, then F3 | S1, S2, S3 (`surface_calcium.py` imports spatial, plasma, gated and IP3 helpers) | L2 |
| S5 | F4 and F5, with the profile and geometry helpers | S4 | L2 |
| S6 | F10 and F11, with the ensemble adapters: `families.py` (`TODAY` entries, `_older`), `cli.py`, `worker.py`, `ionic.py` pruned to kept children | S2, S3 | L2 |
| S7 | Consumers: the BETSE drivers kept (Q3), the ensemble validation, the moved tests, configs and examples, all retargeted by the move map | S1–S6, in the same landing as the families they use | L1, L2 |
| S8 | The deletion (§8) | L1 and L2 on main | L3 |

- **Three full gates, not six.** Each landing changes src/, so it runs the full gate (D223): tiers 1+2,
  crossrev, G1 and the IDs, plus C5 for its families. Batching the six moves into two landings saves three
  gates; each landing's move map and verifier keep it mechanical.
- **Two builders can work in parallel on disjoint files:**
  - builder 1 takes S2, S3 and S6, the ensemble line;
  - builder 2 takes S1, then S4 and S5 once S3 has landed in L1, the BETSE line.
- **Branches in flight** that touch legacy rebase onto each landing's move map by the same script, as D188
  required.

## 7. Tests: move, stay or go

### 7.1 What the numbers count

Each class below is defined per tier-record file (891 files, `inventory.json`):
- **Imports legacy directly** (195 files; D346's count): 76 in tiers 1 and 2 (1,530 test-seconds) and 119
  in tier 3.
- **Names a legacy model ID itself** (10): 7 in tiers 1 and 2 (177 s) and 3 in tier 3.
- **Reaches legacy only through a fixture, shared driver or configuration** (401): 312 in tiers 1 and 2
  (7,847 s) and 89 in tier 3.
  - 27 of the 312 (370 s) are named after a legacy family and likely go.
  - The other 285 (7,477 s) are mostly modern-subject tests whose fixtures also name legacy IDs: bath
    schedule, compartments, the command line, replay, windows and the BETSE physiology set.
- **No static evidence** (285), but 35 of them (1,239 s) load legacy at runtime through a dispatch miss.
  - For example, `parse_spec` calls `legacy().parse` before the inline families, and `model_for` imports
    spec modules in order until one matches.
  - These must pass unchanged after the deletion.
- **Runtime (the scope map, 24 November, tiers 1 and 2):** 388 of 662 files load at least one legacy module,
  and 354 load the hub. That counts loads, not uses.

### 7.2 The classes and what happens to each

| Class | What happens | Files (tiers 1+2 / tier 3) |
|---|---|---|
| **Go**: the subject is a legacy family not ported (derived families: excision, barriers, profiles, bath events, water, repair, mitochondria, transport, the older bioelectric, multispecies, graph and EMT families) | Deleted in one batch with the deletion, by a removal list (D224) giving each file's family and the reason | about 95 / 115 (estimate; the dry run fixes it) |
| **Go, replaced**: tests of the 11 families that check legacy structure (planning, dispatch, the hub) | Deleted. C5's recorded bitwise comparison is the proof, and the moved physics tests keep coverage | a few; listed by the builders |
| **Move**: physics, conservation and reference tests of the 11 families and their nested layers (for example `test_hcn_extra_catalog.py`, `test_spatial_calcium.py`, `test_plasma_calcium.py`, `test_gated_calcium.py`, `test_ip3_calcium.py`, `test_er_calcium.py`, `test_assembly_cell.py`, `test_assembly_cluster.py`, `test_integrated_ensemble.py`, `test_open_calcium.py`, the GPU integration tests, and `tests/betse_physiology/` if Q3 keeps the physiology set) | Retargeted by the move map, with the same assertions. Paths do not move (D188) | about 40 / 45 under Q3 (a), of which `tests/betse_physiology/` is 34 / 24 (941 tier 1+2 seconds) |
| **Stay**: modern-subject tests with incidental legacy reach (fixtures naming legacy IDs, dispatch misses, the conftest world) | Their fixtures are cleaned. References to `resolved_tissue@8`/`@1` are kept or retargeted (Q4); the 10 conftest users are retargeted (Q5) | about 290 / 55 |
| **New** | None in the tiers. The bitwise proof is a recorded one-time comparison, like G1's baseline. Any new test that compiles a world states its seconds and reason (D224) | 0 |

### 7.3 Pre-existing failures

- **The tier-3 record holds failures in the moved files:** `test_assembly_cell.py` (1),
  `test_assembly_cluster.py` (2), `test_surface_calcium_energy.py` (1), and `test_surface_calcium.py`, which
  times out at 1,800 s.
- A moved file must match its recorded outcome, not improve on it silently. A fix goes in the existing file
  as a row (D224).

### 7.4 The definitive classifier: a scratch dry-run deletion

This runs once L2 is on main, and its output is the deletion's removal list.
1. Freeze a snapshot of the head with `freeze_snapshot.py --scope full`.
2. In the snapshot only, `validation/legacy_port/dry_delete.py`:
   - removes `src/cells/legacy/` and `registry/legacy_entry.py`;
   - replaces every `legacy()` call site with its miss branch: the six of §8 and the ensemble's.
3. Run, on a lane:
   ```
   scripts/run_detached.sh legacy-dry-tiers 12G --cpus 8-11,24-27 --oom-first -- flock /mnt/workspaces/Cells/locks/gate-cores-8-11.lock /mnt/workspaces/Cells/venv-cpu/bin/python -B DRY/scripts/test_tiers.py run --tiers DRY/tests/test_tiers.json --tier 1 2 --cpus 8,9,10,11,24,25,26,27 --out OUT
   ```
   About 30 minutes of lane B. Tier 3 runs deliberately afterwards.
4. Every failing or erroring file goes on the removal list, with its reason, or on the fix list.
5. The passing files' summed seconds, against the base run, are the measured saving of §9.

## 8. The deletion: its content, removal list and gate

**Before it:**
- main is tagged (D346), as the BETSE-native removal was (`native-betse-frozen-2026-11-08`);
- the tag's snapshot is frozen.

**The commit removes:**
- `src/cells/legacy/` (321 files, or what the moves left);
- `registry/legacy_entry.py`;
- the six `legacy()` call sites of the dispatch points: `definitions/specs.py:857, 1049`,
  `registry/models.py:71`, `execution/schedule.py:147`, `__main__.py:220, 237`, and `LEGACY_COMMANDS`;
- the ensemble's: `ensemble/families.py`'s `_older` hooks and `ensemble/cli.py:139`; and
  `ensemble/ionic.py`'s rows for families not kept;
- `registry/declarations.py`'s legacy list, `legacy_entries` and the manifest's `legacy` key.

**The manifest change needs coordinating.** The `legacy` key is a top key of `cells.declarations@2`, and the
viewer reads the manifest. Either the schema goes to `@3` or the key stays empty. That is the lead's ruling,
with the viewer's agent told first.

**Tests, validation and data go with it:**
- the removal list's tests (§7);
- `tests/unit/test_legacy_entry.py`;
- the tier record's rows, re-measured as below;
- the tier-3 record's rows, refrozen;
- validation drivers and references that reach only deleted families. About 600 validation files have
  legacy evidence; the dry run and an import check list them exactly. Their frozen evidence stays under
  `/mnt/workspaces/Cells` untouched, and the tag keeps them reproducible.
- configs, examples and reports naming deleted IDs. 112 configs name legacy IDs. Reports are recorded
  evidence and stay.

**Laws and numerics left without a user** are listed by an import check after the deletion. Candidates:
- `laws/channels/`'s catalogue modules, if Q2's re-expression replaces them;
- `numerics/surface_field.py` and `tissue_field.py`, if only legacy used them.

They are kept or deleted in the same batch.

**Docs:**
- `docs/library/` regenerated (`scripts/library_pages.py`), with its page tests;
- `PROGRESS.md`;
- `ARCHITECTURE.md`'s legacy mentions;
- this note, marked done.

**The gate** is the full one, since src/ changes, on a free lane:
- **IDs**, with the removed IDs declared (`REMOVED_OK_FILE`: the 127 dispatch IDs, the 2 assembly IDs and
  the 3 inline ones, less those Q4 and Q5 keep).
- **Crossrev** head against base: identical, since no set reaches legacy.
- **Tiers 1+2** on the surviving files, against the recorded baseline.
- **G1** at 113 of 113, bitwise; its worlds name no legacy ID.
- **Tier 3** once, deliberately, on the final tree against the refrozen record, as D188 did.
- **Tiers re-measured** on the surviving files (`test_tiers.py measure`, on cores no other job is pinned
  to), then folded.
- **The scope map** is stale until the next nightly rebuilds it, so no-src selection is refused until then
  (`scope.py`). That is expected, not a failure.
- **The private-term scan** on the staged diff.

## 9. What the deletion saves in gate time

| Stage | Today | After (estimate) | Basis |
|---|---|---|---|
| Tiers 1+2 | 669 files, 13,577 test-seconds (tier 1 2,615; tier 2 10,962) | −1,700 to −2,100 s (13–15%), about 4 min of a lane's wall at 8 workers; about −2,700 to −3,000 s if Q3 (c) also retires the physiology tests; upper bound −9,554 s (70%) if the dry run finds the fixture-reaching tests run legacy worlds | §7.1 |
| The hub's import | Up to 354 processes import the hub's 97 module-level legacy modules on a dispatch miss | Gone | Measured by the dry run's file seconds |
| G1 (113 worlds) and crossrev | Unchanged | Unchanged | No legacy world |
| IDs check and manifest | 132 legacy entries | Gone | Small |
| Tier 3 (deliberate) | 215 recorded files, 87,166 test-seconds | 204 files (85,147 s) reach legacy. Most go; the moved ones stay | §7.1 |
| No-src selection (D229) | Many files are reached by any change near legacy | Fewer reachers per change | Measured on the first nightly after |

**The honest reading.**
- The routine gate gains a few minutes of the hour D346 gives it, because G1 and crossrev dominate and are
  untouched.
- The large saving is tier 3's deliberate runs, about 24 test-hours today, and a narrower suite for every
  later selection.
- D189 measured a 2.1-minute saving per tier 1+2 gate for its retire list; this one is larger, and the dry
  run measures it.

## 10. Cost in agent-days

| Work | Agent-days | Gates and lanes |
|---|---|---|
| S0: capture tools, C0–C4 | 0.5 | one lane for about 40 min; optionally again after the rename |
| S1–S3 (L1): F1, the nested layers, F6–F9; move map, rewriter run, verifier, dispatch and IDs, consumers | 2–3 | one full gate (about 1 h) and C5 |
| S4–S6 (L2): F2–F5, F10–F11, the ensemble adapters, consumers | 3–4 | one full gate, C5, and the GPU block (about 1 h) |
| S7 extra: BETSE drivers per Q3, test retargets, the conftest per Q5 | 1–1.5 | inside L1 and L2 |
| S8 (L3): the dry run, removal list, deletion, re-measure, tier 3 | 1.5–2 | dry run about 30 min; full gate; tier 3 once (about 2–3 h of a lane); re-measure (about 1 h) |
| **R total** | **about 8–11** | **about 10–12 lane-hours** |
| E, per family, if Q2 asks for it | F1 3–5; F2/F3/F6–F9 laws and compartments 5–8; F3's fuel blocked on the finite-fuel case; F4/F5 1–2; F10/F11 3–5: **15–25** | tolerance judging per family |

**The reference is D188.** It sized move 1, which made today's 321-file legacy, at 3.5–4.5 agent-days, and
both moves at about 6 hours of gates. This port moves about a third of those lines but also re-plumbs
dispatch, IDs and consumers.

## 11. Risks

- **The scope grows past the 11.** The nested layers and the drivers' extra families (§3.2, §3.3). Q1
  bounds it.
- **Bitwise fails for reasons that are not the port:**
  - a different jaxlib or XLA flags;
  - BLAS threads;
  - a warm cache;
  - shard CPU count;
  - padding columns at inactive channel slots (K1).
  The capture records the environment, and C5 runs in the same one. A port difference stops the landing:
  nothing is accepted at a tolerance without the user (Q2).
- **Order dependence on IDs or module names.** In the families' closure the only sorts found are
  reactions by their own definition IDs (`legacy/core/reaction_spec.py:144`) and membranes by cell index,
  not law IDs. Law codes are unchanged. Still, C5 is the check, not this reading.
- **The rename breaks legacy before the port.** The rename's gate runs the tiers, which include about 600
  legacy-reaching files, so the rename must keep legacy parsing (§13). The captures are taken from the tag
  either way.
- **Lost coverage of live features.** @3's reference worlds (`resolved_tissue@8`), the conftest's
  `source_decay@1`, and fixtures shared with modern tests (§7.2). Q4 and Q5 decide them; the dry run
  shows what is left.
- **Frozen drivers.** Several BETSE and ensemble drivers pin source paths or hashes
  (`trajectory.py`'s `source_sha256`, the ensemble registrations' pre-D188 paths). They cannot re-run
  their own registrations after the move. They stay as records, reproducible from the tag, and only
  drivers Q3 keeps are retargeted.
- **BETSE wording.**
  - Moved docstrings may keep citing BETSE as a law's source (AGENTS.md: "cite the source").
  - Identifiers carrying BETSE conventions are renamed neutral in the move, for example "native" in
    `native_geometry_passive_tissue@1` and `phase_clock_rk_stage_native_logistic@1`, and the
    `tissue_target_selectors as native` alias.
  - Existing live modules already carry some, such as `NATIVE_CALCIUM_SCALE` and
    `cagpotassium_numeric_mM_scale@1`. They are the rename's to judge, not this port's.
- **Concurrency.** Other agents' branches touching legacy, and the visualizer's reading of the manifest.
  Each landing publishes its move map; the viewer's agent is told before L3.
- **Lane time.** Captures, three full gates, the dry run and tier 3 compete with the FR queue for the two
  lanes.
- **The Lean lane** may cite legacy IDs. It gets the port's IDs in the rename's mapping table, through the
  user (D346). `lean/` is not edited.

## 12. The user's questions

**Q1. Which legacy IDs survive as IDs, beyond the 11?**
- (a) The 11 only. The nested layers (`er_calcium@1`, `spatial_extracellular@2`, `finite_extracellular@2`)
  keep IDs only as definition children; standalone worlds of them are refused. The 18 REF-003 to REF-005
  drivers retire with their saved outputs.
- (b) Also keep `finite_extracellular@1`–`@3`, `spatial_extracellular@1`–`@2` and `compartment_reactions@1`
  as standalone IDs. Their code is in the 11's closure already. This costs:
  - six more capture sets, about 20 CPU-minutes;
  - four more catalogue IDs (`finite_extracellular@1` and `@3`, `spatial_extracellular@1`,
    `compartment_reactions@1`), plus standalone admission for the two nested ones;
  - about 1 agent-day of consumers.
- (c) Keep every legacy model the closure carries.
- **Recommendation: (a).** It matches D348's 11 and the catalogue-size priority. The REF-era comparisons are
  closed out, with saved outputs, and BETSE parity later works from those outputs and the ported families.

**Q2. What "ported to the modern models" requires.**
- (a) Relocate under neutral names, proven bitwise. Re-express a family on @3 or the composite later, when
  an experiment needs it (D136, D144), judged at a declared tolerance against the relocation.
- (b) Re-express now, judged at tolerances from the start: 15–25 agent-days more, with no bitwise proof.
- (c) Relocate only, and never re-express.
- **Recommendation: (a).** It is the only path the brief's bitwise proof fits. E's blockers (calcium in
  @3, finite fuel, an ER store) are engine features in their own right.

**Q3. Which BETSE drivers stay runnable after the deletion?**
- (a) The 17 physiology drivers and their 58 tests, on the ported F1–F5. The 18 REF-era drivers and the
  4 helpers retire, with their records kept and the tag reproducing them.
- (b) All 39, which needs Q1 (b).
- (c) None stay runnable. BETSE parity is redone later from saved outputs, with new drivers on the ported
  families.
- **Recommendation: (a).** The physiology set is what uses the five IDs. Its tests already run in tiers 1
  and 2, and parity against saved outputs stays possible.

**Q4. The `resolved_tissue` majors.** `@1`–`@12` are live code, only dispatched by legacy.
- (a) Keep `@12` plus the majors kept consumers use: `@8`, the reference for @3's tests, and `@1`, which the
  physiology references name.
- (b) Keep all twelve: no code cost, but nine more IDs.
- (c) Keep `@12` only, retarget @3's reference checks to another reference, and lose their cross-check.
- **Recommendation: (a).**

**Q5. `source_decay@1`, `emt_mirna@1` and `passive_pair@1`.** They parse live, but their models are in
legacy. `source_decay@1` is the shared conftest's world, used by 10 test files:
- nine infrastructure tests: `tests/integration/test_cli.py` and `test_replay.py`, and
  `tests/unit/test_continuity_gpu.py`, `test_continuity_loaders.py`, `test_numerical_refinement.py`,
  `test_numerics.py`, `test_specs.py`, `test_stationary_analysis.py` and `test_windows.py`;
- and `test_passive_pair.py`.
- (a) Delete all three. Retarget the 10 conftest users to a small live world, `reaction_transport@1`
  or a minimal composite, and drop their own tests.
- (b) Relocate `source_decay@1` (82 lines) as a minimal synthetic test world. Delete the other two.
- (c) Keep all three, relocated.
- **Recommendation: (a)**, by the pre-alpha rule. The tests keep their subjects, and only their vehicle
  changes. Choose (b) if the user prefers a dedicated minimal world.

**For the lead, not the user:**
- the manifest key (§8);
- the GPU block after L2 (§5.3);
- whether to recapture after the rename (§5.1);
- the capture's `--max-steps` (200 here, as G1);
- refusal-message mapping in `compare` (§2).

## 13. Dependencies for the rename note

- **Legacy must keep parsing through the rename.** It names live law IDs in code (`calcium_gates.LAW_ID`,
  `plasma_calcium.PUMP_LAW` and `EXCHANGER_LAW`, `er_calcium.PUMP_LAW`, `METABOLISM_ID`) and in the
  configs and fixtures legacy tests read (`kv1p5_mh@1`, `constant_field@1`, `logmean_electrodiffusion@1`,
  `junction_voltage_relaxation@1`, `nak_atp_mass_action_positive@1`, `cav1p2_m2h@1`, …).
  - Either the rename's script rewrites those references and data too, or legacy's tests fail the rename's
    gate.
  - Legacy's own model IDs stay bare (D346).
- **The port's IDs enter the same old-to-new table** in its second batch:
  - model IDs (§4);
  - legacy-defined law IDs: `ip3_er_release@1`, `finite_atp_pmca_positive@1`, `finite_atp_er_1ca_positive@1`,
    `finite_atp_adp_pi_transformed@1`, `driven_atp_regeneration_tanh@1`, `finite_energy_pool@1`,
    `root_component_has_cycle@1`.
- **Unregistered live laws the families use** are the rename's to name: the 45 catalogue laws not
  registered on @3, NCX, Cav1.2, the ER pump and release, `maintained_mM_quotient@1`,
  `capacitive_components_current_continuity@1` and `gauged_dense_kirchhoff@1`.
- **The closed family list has no word** for the observer, stage-domain, closure and policy IDs these
  families carry: about 60 strings such as `resolved_hcn_extra_accepted_grid@1` and
  `static_declared_ideal_chemical_and_voltage_reservoirs@1`. The note decides whether they are catalogue
  IDs or plain labels.
- **The captures need the pre-rename tag's snapshot** (§5.1). The tag of D346's step 2 serves.
