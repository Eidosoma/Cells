# Source layout moves (D188): the scripted moves' design

*Status: proposed, 17 November 2026: D188's step 0, the design note and its probe. Move 1 waits
for main to hold the BLAS pin (D190) and the retire (D189), and for the lead's go. The tools are
drafts: `scripts/source_moves.py` (the map, the rewriter, the verifier) and
`scripts/source_moves_plan.py` (the analyses the maps are built from). The evidence is in
`/mnt/workspaces/Cells/d188-step0-20261116/` (`evidence/`, `maps/`, `tools/`), cited below as `$E`
and `$T`; the plans at main fa19d80c are in `$E/plan-fa19d80c/`.*

## 1. The plan

Each move has three parts:
1. **Refactor commits.** A few small ones, hand-written and semantic-free. Each is checked at
   the AST level and gated. They remove what a pure move cannot carry: dispatch chains, module
   paths computed at run time, couplings, and roots computed from `__file__`.
2. **One move commit.** `source_moves.py apply MAP` makes it and `source_moves.py verify`
   checks it. It holds no hand edits.
3. **The gates (§8),** on each commit.

| | Refactors first | The move commit (draft at main fa19d80c) |
| --- | --- | --- |
| Move 1 | R1 dispatch, R2 computed module paths, R3 seven couplings, R4 file-relative roots (§5, §7.3) | 318 modules into `src/cells/legacy/`, 647 files rewritten |
| Move 2 | the continuity probe's names if a checkpoint must cross it; three more pinned files (§5); the visualizer's tools (their owner) | 109 modules into the target folders, 35 left for the lead to place (§9) |

**The probe** ran the cycle on a scratch tree: a family moved, a coupled kernel extracted and
moved, and a file pinned by path moved. Every check came out identical (§12).

## 2. The move map

One JSON file per move, committed with it in `scripts/moves/`:

```json
{
 "kind": "cells.source_moves.map@1",
 "move": "d188-move-1",
 "modules": [["cells.core.reaction_spec", "cells.legacy.core.reaction_spec"], ...],
 "packages": {"cells.legacy": "\"\"\"...\"\"\"\n", "cells.legacy.core": "", ...},
 "keep": [{"path": "...", "reason": "..."}],
 "reviewed": [{"path": "...", "reason": "..."}]
}
```

- **`modules`** lists old to new dotted names, one entry per module file. A package is its
  `__init__` plus every module in it, and a map that moves a package's `__init__` but not all
  of its modules is refused.
- **`packages`** lists the new packages and their `__init__` text. Every new folder needs one.
- **`keep`** lists the files the rewriter leaves untouched, each with its reason.
- **`reviewed`** lists the files whose computed module paths a person checked against this
  map (§3.3), each with its reason.
- **Basenames are kept.** `validation/tissue/composition_matrix.py:795` and
  `processes/stable_seed_control_volumes.py:99` derive names from them. Where move 2 renames a
  leaf, the rewriter adds `as old_name` at each import.
- **`legacy/` mirrors the sub-packages,** as in `cells.legacy.core.*`, `cells.legacy.models.*`
  and `cells.legacy.processes.*`. A flat folder would collide, for example `models.er_calcium`
  with `processes.er_calcium`.
- **The checks refuse:**
  - a module absent from the tree;
  - an old and a new path that both exist;
  - an unmapped module left in a package the map moves, for example a file that exists only on
    a branch;
  - a new folder without its package file.

## 3. The rewriter

`apply` moves each file, keeping its bytes. It then rewrites every reference to a moved module in
the files in scope. Only files the rewrite changed get ruff's import sorting (`--select I
--fix`). There is no other formatting: 13 src files are not format-clean, and tests anchor on
source text. ruff gets `known-first-party = cells, tests, validation`, because otherwise it
classifies a module by what exists on disk, and a new package does not exist yet when the
rewriter sorts.

### 3.1 What it rewrites

| Kind | Example | How |
| --- | --- | --- |
| `import` and aliases | `import cells.core.x as y` | the name, by AST span |
| `from … import` | `from cells.core.x import a`; `from cells.models import x as m` | the module part; a submodule's import is regrouped by its new parent, and split if its names diverge |
| relative imports | `from . import n` | kept while they mean the same module; made absolute when the file or its target moves (src has none today; validation has 40, none affected) |
| attribute chains | `cells.core.x.parse` after `import cells.core.x` | by AST span |
| dotted paths in strings and comments | `mock.patch("cells.core.x.parse")`, `import_module("cells.core.x")`, `-m cells.x`, `"cells.core.x:parse"`, docstrings | a token rule: longest moved prefix, with any attribute after it kept; nothing followed by `@` |
| file paths in strings and comments | `"src/cells/core/x.py"`, `"core/x.py"` (relative to src/cells, starting with one of its folders, as in `source_hashes()` keys and the continuity test's `EDITS`) | the same token rule |
| programs in strings | a test's subprocess program, such as `from cells.processes import charged_surface_backend` in `test_charged_surface_repository.py` | the string's body is rewritten as Python when it parses and holds no escapes |
| shell, TOML, cfg | `python -m cells.core.x` in `scripts/*.sh` | the dotted and path rules |

**Scope:** tracked `.py`, `.sh`, `.toml`, `.cfg` and `.ini` files under `src/`, `tests/`,
`validation/`, `scripts/` and `examples/`, plus `pyproject.toml`. Its entry point,
`cells = "cells.__main__:main"`, does not move.

### 3.2 What it leaves alone, and why

Counts are from the draft move 1 (`$E/scan-move1-draft.json`).

| Left alone | Why |
| --- | --- |
| Frozen evidence under `/mnt/workspaces` | Never edited (AGENTS.md) |
| JSON anywhere in the checkout: 32 files in `validation/` with 2069 references, and `tests/tier3_record.json` with 8 | Records and registered protocols. They describe the code as it was when they were registered: path-to-hash maps (`protected_sha256`, `owned_sha256`, `source_sha256` and others, in 288 files) and module paths such as `public_parser` in `validation/geometry/*_protocol.json`. No test compares a run's module path with them (grep) |
| `docs/` (11 files), `reports/` (55), `agent-work/` (262), Markdown anywhere | History, and agents' frozen work files. The live docs, ARCHITECTURE.md's "where it lives" column and the module-system design, get one docs-only commit after each move |
| `visualizer/` (5 files) | The visualizer agent's. Its data are extractions at a revision, and its tools read engine paths at a revision (§10) |
| Model, kind and format IDs (`cells.transporter@1`, `cells.visualizer.scene@1`) | Not module paths: the token rule skips names followed by `@` |
| `source_hashes()` keys in run manifests and checkpoints | Written at run time. A checkpoint from before a move carries the old keys, and continuity admission handles that, as the probe showed (§12) |

### 3.3 What it cannot rewrite: computed module paths

A string that run-time code completes to a module path, such as `"cells.core." + stem + "_spec"`
or `f"cells.models.{name}"`, cannot be rewritten.
- **`scan` reports each one as a hazard** when its prefix is the parent package of a moved
  module.
- **`apply` refuses the map** until each hazard's file is refactored or listed under `reviewed`.
- **Today: 17 files** (`$E/computed-module-paths.txt`).
  - 2 in src: `core/active_ecm_polygon_preparation.py` and
    `core/active_polygon_physiology_preparation.py`. Each calls `import_module("cells.core." +
    family)`, and compares `type(spec.model).__module__ + "." + __name__` with a path built the
    same way. A failure there turns into `ActivePreparationRejected`, so a test that expects a
    refusal could still pass.
  - 15 in tests: the joint-water and owned-calcium fixtures, and the dispatch tests.
- **The static import graph cannot see these sites.** R2 rewrites each one to name full modules
  in its table, before move 1.

## 4. The verifier

`verify MAP --base REV --head REV` replays `apply` on the base commit's tracked files in memory.
Then:
- **Identical trees:** the head's tracked files must equal the replay, byte for byte and mode
  for mode, for every path, out of scope included. So every changed line is the rewriter's,
  and nothing else changed.
- **No hash edits:** no SHA-256-like literal may change in a changed file (D187: a hash is
  never updated, by hand or by the tool). A pin's path may change; its hash may not.
- **A second application changes nothing.**
- **Every static `cells.*` import** in the four folders resolves in the result. Collection
  covers only `tests/`.
- **No reference to an old module is left in scope.**

**Planted cases,** in `selftest` rather than in `tests/` (new test files would change the
collected IDs), 28 checks:
- a hand edit, an extra file, a hash edit, an absent module and an unlisted module in a moved
  package are each refused;
- a branch's own new reference is rewritten;
- a relative import is made absolute when its file moves;
- a program in a string is rewritten;
- a kind ID and docs are left alone.

On the real probe, a planted one-line edit was refused (`$E/verify-P3-planted.json`).

**Refactor commits are not the tool's.** They stay small and are checked at the AST level, as the
probe's P2 was (`$E/extraction-P2-check.txt`):
- the moved text is byte-identical;
- every other definition and statement is unchanged;
- only imports change.

Like moves, they pass the gates.

## 5. Code pins

The core owner's finding (16 November): `processes/charged_surface_work.py` pins its dependencies'
content by path, `src/cells/__init__.py` among them. It refuses to run when one changes, and its
pin table enters its binding identity. The inventory is `source_moves_plan.py pins`, output
`$E/plan-fa19d80c/code-pins.json`.

**The inventory.** In src/cells, 14 modules hold 43 live pins on 22 files. All 14 are legacy or
geometry laws, and none is on the active path.

| Pinning module | Pins | Kind |
| --- | --- | --- |
| `processes/charged_surface_work.py` | `cells/__init__.py`, `numerics/__init__.py`, `processes/__init__.py`, `numerics/{membrane_redistribution,fixed_step,extracellular_field}.py`, `processes/electrochemistry.py` | path: root is `parents[3]`; the pin table enters the binding identity |
| `core/conservative_polygon_tissue_preparation.py` | `numerics/surface_transport.py`, `processes/electrochemistry.py` | path: root is `parents[1]`; recorded in its records |
| `processes/stable_seed_partition_advance.py` | `processes/stable_seed_partition_physiology_bridge.py`, `numerics/{fixed_step,surface_transport,extracellular_field}.py`, `core/{state,devices}.py`, `processes/electrochemistry.py` | path: `parents[3]` |
| `processes/stable_seed_partition_physiology_bridge.py` | `processes/stable_seed_explicit_ecm_partition.py`, `numerics/{surface_transport,extracellular_field}.py`, `processes/electrochemistry.py` | path: `parents[3]` |
| `processes/stable_seed_partition_trajectory.py` | `core/resources.py`; it also records its own source hash | path: `parents[3]` |
| `processes/stable_seed_control_volume_environment.py` | `processes/{stable_seed_control_volume_physical_bridge,finite_ecm_polygon_geometry}.py` | path: `parents[1]`; recorded |
| `processes/stable_seed_control_volume_physical_bridge.py` | `core/conservative_polygon_tissue_preparation.py`, `processes/{conservative_polygon_geometry,stable_seed_control_volumes}.py` | path: `parents[1]` |
| `processes/stable_seed_explicit_ecm_partition.py` | three geometry modules | path; recorded |
| 6 geometry modules (`conservative_polygon_geometry`, `finite_ecm_polygon_geometry`, `fixed_polygon_removal`, `stable_mesh_{metric,operator}_reconstruction`, `stable_seed_control_volumes`) | the geometry primitives they import | module: the hash of `module.__file__`, so only its bytes count |

Some pins form chains: a pinning module is itself pinned by another, for example the physical
bridge by the environment. 15 modules compute paths from their own `__file__`.

**How a move treats a pin:**
- **The pinned file moves and its bytes stay.** The rewriter rewrites the pin's path key, as it
  rewrites any path string. The pin stays live and no hash changes. The pin table changes, so
  an identity built from it changes deterministically: charged_surface_work's binding identity
  differs from any recorded before the move.
  - *The probe's P4 shows it:* `_pins()` holds in both trees, the table digest goes from
    `d7618ce1…` to `8933d123…`, and the five tier-1/2 files that reach the law keep every
    outcome, 89 passed and 2 skipped (`$E/p4-check/`).
  - A module pin (`module.__file__`) follows its module: only a byte change breaks it.
- **The pinned file's bytes change** because its imports are rewritten. The pin goes stale and
  the law refuses, which is the pin working as intended. Neither the tool nor anyone updates
  the hash (D187), and the verifier refuses a changed hash literal.
- **The pinning module moves to another depth.** `Path(__file__).parents[k]` then names another
  folder, so its path pins point elsewhere. In charged_surface_work, `parents[3]` would become
  `src/`.

**What the draft move 1 touches:**
- **7 of the 14 pinning modules move,** and 6 of them are rewritten too. All 7 compute their
  root from `__file__`.
- **4 path pins' files move.** Two keep their bytes (`membrane_redistribution.py`,
  `conservative_polygon_tissue_preparation.py`). Two are also rewritten, so they go stale
  (`stable_seed_control_volume_physical_bridge.py`, `stable_seed_partition_physiology_bridge.py`).
- **No module pin is touched.**

**The rule proposed:**
- **R4, before move 1:** make the roots of non-pinned pinning modules independent of depth, for
  example `Path(cells.__file__).resolve().parents[1]`, as `cells.io.source_hashes` does. Here
  that is `charged_surface_work` and `charged_surface_backend_gate` (`parents[4]`). Neither file
  is pinned, so no pin goes stale.
  - With R4, the charged-surface law runs after move 1 with all its pins live: only the
    membrane_redistribution key changes, as P4 shows. `test_charged_surface_repository`, which
    passes today and which the BLAS pin also met, stays green.
- **The stable-seed and conservative-polygon cluster stays as it is,** because its pins form
  chains: R4 would make the outer pins stale.
  - After move 1 these laws refuse at their pin checks.
  - Their gate tests already fail today: 6 tier-1 files with exit code 1
    (`$E/pinned-cluster-tests.json`). On D189's list, 2 are firm (`test_stable_seed_control_volume_{environment,physical_bridge}.py`)
    and 3 are held (`test_stable_seed_partition_{advance,advance_refinement,trajectory}.py`).
    The held list is reviewed again once D188 has cut the couplings.
    The sixth, `test_conservative_polygon_tissue_preparation.py`, is on neither. It has to be
    retired, or shown to keep its counts, before move 1.
  - The frozen evidence stays reproducible from its frozen snapshots.
- **Move 2** touches 3 more path pins: `core/{state,devices,resources}.py` move into
  `execution/`, and `state.py` is rewritten. Those laws are in the same cluster, so the same
  rule applies.

## 6. The registry's legacy entry point

**The dispatch points.** Six modules import every family in order to dispatch on it. For each,
the number of modules it imports that move 1 moves:

| Point | Moved-module imports |
| --- | --- |
| `models/registry.get_model` | 213 |
| `core/specs.parse_spec` and `SimulationSpec._fine_dict` | 92 |
| `core/schedule.control_values` | 61 |
| `cells/__main__` (the `phase`, `geometry`, `profiles`, `cluster`, `coupled` and `excision` subcommands) | 7 |
| `ensemble/families` | 5 |
| `ensemble/cli` | 1 |

**Proposed: one module, `cells/legacy/registration.py`, holding the legacy halves of the chains
verbatim.**
- It exposes `model_for(spec)`, `parse(data)`, `to_dict(sim)`, `control_values(spec, times)`,
  `cli(command)` and `ensemble(model)`. Each returns `None` when no older family matches.
- The core's chains keep their active branches and, where they would refuse today, call
  `_legacy()`. That loads one constant, `LEGACY = "cells.legacy.registration"`, with importlib
  and caches it, the pattern of `kind_registry.BUILTIN_PACKAGE`.
- **A guard test with a planted control:** no module outside `cells/legacy/` imports
  `cells.legacy`, except through that constant (an AST scan).

**Why delegate on a miss rather than a table:**
- It moves code verbatim, so it is the smallest change that can be shown to keep dispatch the
  same.
- Of the registry's 139 `isinstance` entries (9 active), none has a subclass relation across the
  boundary, and none is shadowed. So active-first-then-legacy dispatches every registered class
  as today. This was checked on `get_model`'s chain; R1 checks `_fine_dict` and
  `control_values` the same way.
- `parse_spec` dispatches by model ID, so its order does not matter. The exceptions are the
  projective pre-check and the inline fall-through for `source_decay@1`, `emt_mirna@1`,
  `passive_pair@1` and `reaction_transport@1`, which stay in `specs.py`. Their dataclasses are
  also the shared spec vocabulary that active families reach, and no legacy module is imported
  for them.
- R1's equivalence check: for every registered class and ID, old and new dispatch agree, run in
  one process per tree.

The registration tables of D185 stay the core-seams pass's design.

## 7. Move 1

### 7.1 What moves (draft at fa19d80c: `source_moves_plan.py move1`, `$E/plan-fa19d80c/move1-draft.json`)

**The rule:**
- A module moves when it is an older family's module, is reached only from older families, or
  imports one, and the active path does not reach it.
- Then every module that imports a moved module moves too, except the dispatch points.

**The active path** is a name-level reachability analysis from the entry points with D189's nine
families (`source_moves_plan.py reach`). It follows imported names through each module's top-level definitions,
not whole modules.

**The result: 318 modules.**

| Package | Modules |
| --- | --- |
| core | 134 |
| models | 135 |
| processes | 26 |
| assembly_cluster | 10 |
| assembly_cell | 6 |
| ensemble | 2 (`cluster`, `coupled`) |
| numerics | 1 (`membrane_redistribution`) |
| top-level modules | `excision_io`, `tissue_geometry`, `tissue_phase`, `tissue_profiles` |

**Stays in the core though an older family's:** five modules the active path reaches (§7.2),
which move 2 places, and 15 channel-catalogue modules that `surface_kinetic` reaches.

**The command-line paths change.** The `assembly_cell` and `assembly_cluster` engines are built
on older families, so they move whole, with their CLIs: `python -m cells.assembly_cell` becomes
`-m cells.legacy.assembly_cell`. `cells cluster` and `cells coupled` keep working through the
registration (§6). **For the lead.**

### 7.2 The couplings: the 42, and with D189

Walking the inventory's 42 by name (`$E/couplings-42-walk.txt`):

| Count | Target | Under D189 |
| --- | --- | --- |
| 26 | `models.surface_pump` (13), `core.surface_pump_spec` (5), `core.surface_pump_v2_spec` (5), `models.surface_pump_v2` (3) | Dissolved: the four families D189 keeps active |
| 8 | `models.surface_tissue` | Stays in the core whole (75% of its lines reached; the base of @1–@3); move 2 puts it in `models/` |
| 1 + 1 | `models.surface_kinetic` (90% reached), `core.surface_kinetic_spec` (18%) | Stay in the core; the latter's import of `core.junction_finite_spec` is cut by R3 |
| 2 | `models.kinetic_finite_extracellular` (25% reached) | The reached kernel is extracted to the core, as the probe did, and the rest moves |
| 4 | `check_definition` of `bioelectric_cell`, `multispecies_membrane`, `finite_extracellular`, `physical_ionic_graph` | Not reached at name level: cut by R3 on the spec modules (1–6% reached) |

**A finding for D189's retire check:** that check names the 42, but with D189's ruling the list
that move 1 must cut is different.
- The four kept families bring their own imports: 25 module-level edges into older modules
  (`source_moves_plan.py classes`).
- At name level these reduce to 7 reached modules that import a moved one. These are **R3**:
  `core/{bioelectric,multispecies,physical_ionic_graph,kinetic_finite,surface_kinetic}_spec`,
  `models/kinetic_finite_extracellular` and `processes/cav_channels` (→ `calcium_gates`).
- Each is one small extraction like P2. Its reached part stays, and the part that imports
  legacy moves or is split off.

### 7.3 Pure moves and refactor commits

| Commit | Kind | Content |
| --- | --- | --- |
| R1 | refactor | Creates `cells/legacy/__init__.py` and `cells/legacy/registration.py`, holding the legacy halves of the six dispatch points. It imports the older families at their current paths, and M1's rewriter retargets those imports. Also the delegation and the guard test |
| R2 | refactor | The 17 computed-module-path sites name full modules |
| R3 | refactor | The 7 extractions |
| R4 | refactor | Depth-independent roots of `charged_surface_work` and `charged_surface_backend_gate` (§5) |
| M1 | move | 318 modules; the rewriter changes about 647 files, nearly all import lines (`$E/scan-move1-draft.json`) |

The map is regenerated on the head that holds the pin and the retire, and after R1–R4. The probe
shows that its commits verify.

## 8. Gates per commit

Every refactor and move commit passes:
- `source_moves.py verify` (moves only) and `selftest`;
- **the same collected test IDs:** `pytest --collect-only` over `tests/`, IDs and collection
  errors both (`$T/collect_ids.sh`);
- **crossrev's nine sets identical,** the kinds set included, against the record:
  - with every set's file listing diffed too, since `compare` reads only the record side's
    files (`$T/crossrev.sh`);
  - on two CPUs of one core until the BLAS pin lands, and on any allocation after;
- **G1 at 113 of 113,** each shard on one CPU (`$T/g1-shard.sh`);
- **tiers 1 and 2 with 0 changed.**

Tier 3 runs once on the final tree against `tests/tier3_record.json`, together with G3 and G4
(D194). That record's error lines hold 8 references to modules that move 1 moves, so the tier-3 diff
should read the record through the committed maps (a reading rule; the record is never edited).

**Wall time per commit, with 8 free CPUs:** about 40–50 minutes. That is collection 3, crossrev
4, G1 about 17 on 8 shards, and tiers 1+2 about 20–25.

## 9. Move 2's map (draft: `source_moves_plan.py move2`, `$E/plan-fa19d80c/move2-draft.json`)

109 modules by a rule table, basenames kept:

| Target | From | Count |
| --- | --- | --- |
| `laws/channels/` | `processes/*_channels`, catalogues, `voltage_gates`, `exponential_gates` | 18 |
| `laws/junctions/` | `processes/junction_{gate,formation}`, `coupling/{passive,selective}` | 4 |
| `laws/pumps/` | `processes/{kinetic_pump,calcium_atpase,proton_pump,atp_transporter}`; R3's pump binding joins them | 4 |
| `laws/routes/` | `processes/{passive_permeation,k_anion_symport}` | 2 |
| `laws/reactions/` | `processes/{mass_action,reactions,hill_factors,rapid_proton_buffer,ph_condition,er_calcium,plasma_calcium}` | 7 |
| `laws/transport/` | `processes/{proton_leak,patch_damage}` | 2 |
| `kinds/` | `models/inner_kinds/*` | 6 |
| `operators/` | `models/operators/*` | 22 |
| `models/` | the active model modules: @1–@3, water, replacement, composite and adapter, inner_laws, surface_tissue, surface_kinetic, apical_vertex, reaction_transport | stay |
| `numerics/` | `numerics/*` | stay |
| `execution/` | `core/{runner,windows,vector_windows,batch,batch_windows,projective,devices,phases,grid,state,resources,row_checks,schedule,errors,output_paths}`, `continuity` | 16 |
| `registry/` | `models/registry` (→ `registry/models`, leaf renamed), `core/{kind_registry,species_registry,inventory_species}` | 4 |
| `definitions/` | `core/specs`, the active `core/*_spec` | 18 |
| `records/` | `io`, `window_io`, `batch_io`, `batch_window_io`, `run_view`, `observers` | 6 |

**Left for the lead (35, listed in the map's `draft_notes`):**
- `processes/electrochemistry` (constants used everywhere);
- the geometry and partition kernels, the rectangular-environment kernels, the controls and
  modulations, `vertex_mechanics`, the charged-surface backend;
- `analysis/`, `assays/`, `assembly/`, `assembly_pool/` and `ensemble/`, which D188 does not
  name.

**Move 2 needs three things that move 1 does not:**
- **The continuity probe.** One copy of `validation/continuity/probe.py` runs under both trees.
  - It names its entry points as `cells.core.*` (`ENTRY_POINTS`), so after move 2 it cannot run
    under a pre-move tree.
  - Its P0 digests each static function's name as `__module__.__qualname__` (`static_name`,
    line 208). When move 2 moves a static function's module (`core/vector_windows` into
    `execution/`), P differs and the resume is refused: closed, but a false refusal.
  - Move 1 moves no such module, and the probe's admission held.
  - If a checkpoint must cross move 2, the probe first resolves each entry point under its own
    tree and reads names through the committed maps. **For the lead:** whether any must.
- **Pins.** §5 applies to `core/{state,devices,resources}.py`.
- **`kind_registry.BUILTIN_PACKAGE`** (`"cells.models.inner_kinds"`) is a dotted string, so the
  rewriter covers it.

## 10. Open branches

**The script is idempotent:**
- a module already moved is skipped;
- a branch's own new references to old modules are rewritten;
- a module that exists only on the branch, inside a package the map moves, is refused loudly.

Test file paths never move, but their imports are rewritten (the probe rewrote
`tests/unit/test_compartment_reactions.py`).

**For each branch,** before it merges main, either:
1. merge main into it (git's rename detection carries the branch's edits onto moved files), run
   `apply MAP` on the merge result for the branch's own references, and `verify --base <merge>
   --head <fix>`; or
2. run `apply MAP` on the branch head itself. Identical renames on both sides merge cleanly.

| Branch | What it touches | With the moves |
| --- | --- | --- |
| `core-fixes` (4 commits after a83d8f15) | `core/{kind_registry,species_registry}`, `models/inner_kinds/passive_routes`, `models/operators/{contract,species_reactions}`, `models/surface_pump_v3`, tests | Untouched by move 1; all of it moves in move 2, so it uses the procedure above |
| `visualizer` | only `visualizer/`, no src/tests/validation/scripts changes since a83d8f15 | Its tools read engine files at a revision by hard-coded paths (`extract_laws.py`, `extract_architecture.py`); its owner adapts them (rewrite, or resolve old revisions through the maps); outside the default scope |
| `fr45/transporter/finite-fuel-step2-partial.patch` | `models/inner_kinds/transporter.py` only (base blob `fdefe718`) | Turned into a branch at its base, then handled as a branch; move 1 does not touch it, move 2 moves it to `kinds/` |

## 11. Public imports: no compatibility aliases

Moved modules leave no aliases:
- **D185 owns the stable import surface** for contributed modules, in the core-seams pass.
  Aliases would freeze today's paths as public before that pass decides them.
- **An alias of a legacy module outside `legacy/` breaks move 1's rule.**
- **There is no outside user yet:** stage 1 of the module system has not started.

## 12. The probe (main fa19d80c → scratch head cea0fa6c, never merged)

**The commits:**
- **P1:** compartment_reactions@1 (`core/reaction_spec`, `models/compartment_reactions`) into
  `legacy/`, by the tool. 21 files rewritten, the three dispatch chains included.
- **P2:** the kinetic pump binding kernel (`declared_parameters`, `bind_pumps`, `pump_parameters`,
  `role_inputs`) extracted by hand from `models/kinetic_finite_extracellular.py` into
  `processes/kinetic_pump_binding.py`. The old module re-imports the names, and the four active
  importers retarget.
- **P3:** that kernel into `laws/pumps/`, by the tool.
- **P4:** `numerics/membrane_redistribution.py`, pinned by path, into `legacy/numerics/`, by the
  tool.

| Check | Result | Evidence |
| --- | --- | --- |
| verify P1, P3, P4 | holds; a planted edit refused | `$E/verify-P*-final.json`, `$E/verify-P3-planted.json` |
| P2's extraction | moved text identical; other code identical; only imports changed | `$E/extraction-P2-check.txt` |
| Collected test IDs (P3 against main) | identical: 20792 IDs and the same 13 collection errors | `$E/collect-*.ids`, `.log` |
| crossrev's nine sets (P3), on CPUs 8,24 against `record-a83d8f15` (made on 6,22) | identical in all nine; file listings identical | `$E/crossrev-db8086ea/` |
| G1, six worlds (one per model: @3, composite ×2, water@1, water@2, replacement), one CPU each | identical: 6 of 6, all 688 arrays bitwise | `$E/g1-db8086ea/compare-vs-a83d8f15.json` |
| Continuity resume: checkpoint under main, admitted for P3 by `admit.py`, resumed, compared | proposed (P, B, H, O identical; 31 changed files) and finalised; bitwise at every round; `verify_run` verified | `$E/continuity-db8086ea/` |
| Pinned law (P4) | `_pins()` holds; pin-table digest changes; 5 tier-1/2 files, 89 passed 2 skipped in both | `$E/p4-check/` |
| Tiers 1+2 (P3) | see `$E/tiers-1+2-db8086ea/summary.json` | |

## 13. Estimates

| | Agent-days | Gate wall time |
| --- | --- | --- |
| Move 1: R1 (six dispatch points, equivalence check, guard) | 1–1.5 | |
| Move 1: R2 (17 sites) | 0.5 | |
| Move 1: R3 (7 extractions) | 1 | |
| Move 1: R4, and the pinned cluster's ruling | 0.5 | |
| Move 1: the map regenerated, the scan reviewed, M1 | 0.5 | |
| **Move 1 total** | **3.5–4.5** | about 5 commits × 45 min |
| Move 2: the residue placed with the lead, the probe resolver if needed, pins, M2 | | |
| **Move 2 total** | **2–3** | about 2–3 commits × 45 min |

**Branches** take about 0.25 day each.

## 14. For the lead

1. **CLI paths:** `-m cells.assembly_cell` and `-m cells.assembly_cluster` become
   `-m cells.legacy.*` (§7.1).
2. **The pinned cluster (§5).** Proposed: R4 for the charged-surface law; the stable-seed
   cluster moves as it is and refuses at its pins, with its gate tests retired or shown
   unchanged first. Of its 6 failing tier-1 files, 2 are firm on D189's list, 3 are held, and
   `test_conservative_polygon_tissue_preparation.py` is on neither.
   The alternative is to hold the cluster in place, outside `legacy/`. No hash is updated.
3. **D189's coupling list:** under the ruling it is the 7 R3 sites, not the 42 (§7.2).
4. **Whether any checkpoint must cross move 2** (§9).
5. **Tier 3's error lines** name moved modules: the diff reads the record through the maps.
