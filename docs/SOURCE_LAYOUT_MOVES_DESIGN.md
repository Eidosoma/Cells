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
| Move 1 | R1 dispatch, R2 computed module paths, R3 seven couplings, R4 file-relative roots (§5, §7.3) | 318 modules into `src/cells/legacy/`, 649 files rewritten |
| Move 2 | the continuity probe's names if a checkpoint must cross it; three more pinned files (§5); the visualizer's tools (their owner) | 109 modules into the target folders, 35 left for the lead to place (§9) |

**The probe** ran the cycle on a scratch tree: a family moved, a coupled kernel extracted and
moved, a file pinned by path moved, and a pinning law moved after R4. Every check came out
identical: test IDs, crossrev's nine sets, G1 on six worlds, a continuity resume, and tiers 1+2
with 0 changed (§13).

## 2. The move map

One JSON file per move, committed with it in `scripts/moves/`:

```json
{
 "kind": "cells.source_moves.map@1",
 "move": "d188-move-1",
 "modules": [["cells.core.reaction_spec", "cells.legacy.core.reaction_spec"], ...],
 "packages": {"cells.legacy": "\"\"\"...\"\"\"\n", "cells.legacy.core": "", ...},
 "keep": [{"path": "...", "reason": "..."}],
 "reviewed": [{"path": "...", "reason": "..."}],
 "refactors": [{"kind": "split", "commit": "...", "old": "src/cells/....py", "new": "src/cells/....py", "names": [...]}]
}
```

- **`modules`** lists old to new dotted names, one entry per module file. A package is its
  `__init__` plus every module in it, and a map that moves a package's `__init__` but not all
  of its modules is refused.
- **`packages`** lists the new packages and their `__init__` text. Every new folder needs one.
- **`keep`** lists the files the rewriter leaves untouched, each with its reason.
- **`reviewed`** lists the files whose computed module paths a person checked against this
  map (§3.3), each with its reason.
- **`refactors`** declares the splits and merges that the move depends on. Each was made by its
  own hand-written commit, named here (for example the probe's P2), never by the move commit.
  The rewriter does not read this field.
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

**The path table, for tools that read src/cells by place** (the visualizer's map tooling).
- `source_moves.py table MAP` writes one JSON row per file: `old` and `new` path,
  `old_module` and `new_module`, `kind` and `to_legacy`.
  - `kind` is `move`, `created` (a new package file) or the `kind` of a declared refactor
    (`split`, `merge`).
  - `to_legacy` marks every file that goes into `legacy/`.
- Moves are pure and keep basenames. A split appears only as a declared refactor with its commit.
- Each move commits its table beside its map. The drafts are
  `$E/path-table-move1-draft-fa19d80c.json` (318 moves, 8 package files) and
  `$E/path-table-move2-draft-fa19d80c.json`. An example refactor row is in
  `$E/path-table-probe-kernel-example.json`.

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

Counts are from the draft move 1 (`$E/scan-move1-draft.json`). It was run on this branch at
910ebce0, which is main fa19d80c plus this note and the two tools. The tools are outside the
rewriter's scope, and the note is a doc, so the counts are main's.

| Left alone | Why |
| --- | --- |
| Frozen evidence under `/mnt/workspaces` | Never edited (AGENTS.md) |
| JSON anywhere in the checkout: 32 files in `validation/` with 2069 references, and `tests/tier3_record.json` with 8 | Records and registered protocols. They describe the code as it was when they were registered: path-to-hash maps (`protected_sha256`, `owned_sha256`, `source_sha256` and others, in 288 files) and module paths such as `public_parser` in `validation/geometry/*_protocol.json`. No test compares a run's module path with them (grep) |
| `docs/` (12 files, this note included), `reports/` (55), `agent-work/` (262), Markdown anywhere | History, and agents' frozen work files. The live docs, ARCHITECTURE.md's "where it lives" column and the module-system design, get one docs-only commit after each move |
| `visualizer/` (5 files) | The visualizer agent's. Its data are extractions at a revision, and its tools read engine paths at a revision (§10) |
| Model, kind and format IDs (`cells.transporter@1`, `cells.visualizer.scene@1`) | Not module paths: the token rule skips names followed by `@` |
| `source_hashes()` keys in run manifests and checkpoints | Written at run time. A checkpoint from before a move carries the old keys, and continuity admission handles that, as the probe showed (§13) |

**Audits that read one relative path in two trees** fit neither rule. 20 validation files hold 30
path strings of moved files, mostly the stable-seed audits, references and workers in
`validation/geometry/`, and seven BETSE audits and jobs. They read the same relative path under
a frozen bundle and under the live tree, as in
`stable_seed_partition_physiology_bridge_audit.py:429`.
- **Rewritten,** the frozen read breaks.
- **Kept,** the live read breaks. A file-level `keep` would also skip the file's imports.
- **Proposed:** these audit frozen evidence of the pinned cluster, so they are retired with its
  tests (D187), or translated by hand before the move: the live path through the maps, the
  frozen path as recorded. **For the lead** (§15).

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
collected IDs), 29 checks:
- a hand edit, an extra file, a hash edit, an absent module and an unlisted module in a moved
  package are each refused;
- a branch's own new reference is rewritten;
- a relative import is made absolute when its file moves;
- a program in a string is rewritten;
- a kind ID and docs are left alone;
- the path table marks a move to `legacy/` and the package files created.

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

**The inventory.** In src/cells, 14 modules hold 43 live pins on 22 files.
- All 14 are legacy or geometry laws, and the active path reaches none of them (`reach.json`).
- The same modules also hold 19 stale path-keyed pins, in 5 modules, on files that have changed
  since (`core/{runner,schedule,windows,specs}.py`, `numerics/surface_field.py`,
  `models/surface_tissue.py` and others). Those laws already refuse when they reach them.
- 29 further hex literals digest manifests, reviews and evidence, not source files.

| Pinning module | Pins | Kind |
| --- | --- | --- |
| `processes/charged_surface_work.py` | `cells/__init__.py`, `numerics/__init__.py`, `processes/__init__.py`, `numerics/{membrane_redistribution,fixed_step,extracellular_field}.py`, `processes/electrochemistry.py` | path: root is `parents[3]`; the pin table enters the binding identity |
| `core/conservative_polygon_tissue_preparation.py` | `numerics/surface_transport.py`, `processes/electrochemistry.py` | path: root is `parents[1]`; recorded in its records |
| `processes/stable_seed_partition_advance.py` | `processes/stable_seed_partition_physiology_bridge.py`, `numerics/{fixed_step,surface_transport,extracellular_field}.py`, `core/{state,devices}.py`, `processes/electrochemistry.py` | path: `parents[3]` |
| `processes/stable_seed_partition_physiology_bridge.py` | `processes/stable_seed_explicit_ecm_partition.py`, `numerics/{surface_transport,extracellular_field}.py`, `processes/electrochemistry.py` | path: `parents[3]` |
| `processes/stable_seed_partition_trajectory.py` | `core/resources.py`; it also records its own source hash | path: `parents[3]` |
| `processes/stable_seed_control_volume_environment.py` | `processes/{stable_seed_control_volume_physical_bridge,finite_ecm_polygon_geometry}.py` | path: `parents[1]`; recorded |
| `processes/stable_seed_control_volume_physical_bridge.py` | `core/conservative_polygon_tissue_preparation.py`, `processes/{conservative_polygon_geometry,stable_seed_control_volumes}.py` | path: `parents[1]` |
| `processes/stable_seed_explicit_ecm_partition.py` and 6 geometry modules (`conservative_polygon_geometry`, `finite_ecm_polygon_geometry`, `fixed_polygon_removal`, `stable_mesh_{metric,operator}_reconstruction`, `stable_seed_control_volumes`) | the geometry modules they import | module: the hash of `module.__file__`, so only its bytes count; the first records its pins |

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
- **R4, before move 1:** `charged_surface_work` takes its root from the package
  (`Path(cells.__file__).resolve().parents[2]`, as `cells.io.source_hashes` does) instead of
  `parents[3]`.
  - It is the only pinning module that needs this. Nothing pins its own bytes (src inventory
    and data-file pins both).
  - `charged_surface_backend_gate`'s `parents[4]` names the root of a released frozen snapshot
    (`<root>/source/src/cells/processes/…`, checked against a hard-coded path). It refuses in any
    live tree, before and after the move, so it is left alone. Its release layout belongs to
    that held component's own release.
  - *The probe's P5 shows it:* R4 by hand (P5a, the same folder at today's layout), then the
    tool moves the law and its three backend modules into `legacy/processes/` (P5b).
    - `_pins()` holds from the new depth.
    - The five tier-1/2 files keep every outcome, 89 passed and 2 skipped,
      `test_charged_surface_repository` included. That is the test the BLAS pin also met.
    - **The negative control:** the same move without R4 makes the law fail at
      `src/src/cells/__init__.py` (`FileNotFoundError`; `$E/p5-without-r4/`).
- **The stable-seed and conservative-polygon cluster stays as it is,** because its pins form
  chains: R4 would make the outer pins stale.
  - After move 1 these laws refuse at their pin checks.
  - Their gate tests already fail today, before any pin check: they lack a frozen-evidence
    root, or index variables are unset. `test_conservative_polygon_tissue_preparation.py` is
    the exception: it already refuses at a stale pin (`core/surface_tissue_spec.py`). So the
    move changes no outcome the gates see.
  - 6 tier-1 files fail, with exit code 1 (`$E/pinned-cluster-tests.json`). On D189's list:
    - 2 are firm: `test_stable_seed_control_volume_{environment,physical_bridge}.py`;
    - 3 are held: `test_stable_seed_partition_{advance,advance_refinement,trajectory}.py`. The
      held list is reviewed again once D188 has cut the couplings;
    - the sixth, `test_conservative_polygon_tissue_preparation.py`, is on neither. It has to be
      retired, or shown to keep its counts, before move 1.
  - The frozen evidence stays reproducible from its frozen snapshots.
- **Move 2** touches 3 more path pins: `core/{state,devices,resources}.py` move into
  `execution/`, and `state.py` is rewritten. Those laws are in the same cluster, so the same
  rule applies.

**Data-file pins:**
- 8878 hex literals in the checkout's JSON and Python files outside src (outside `agent-work/`
  and `visualizer/`) equal a current src file's hash.
- The draft move 1 breaks 5125 of them, in 116 files. Nearly all are records and protocols
  under `reports/` and `validation/`, which are left alone (§3.2). Evidence:
  `$T/pins.py`, `$E/json-pins-move1-draft.json`.
- Which tests read them live is measured by the tier gate on each commit, not predicted. A
  static search for their readers is too coarse, because file names such as `result.json`
  are generic. The probe's tiers are in §13.

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

### 7.1 What moves (draft at fa19d80c: `source_moves_plan.py move1`)

**The rule:**
- A module moves when it is an older family's module, is reached only from older families, or
  imports one, and the active path does not reach it.
- Then every module that imports a moved module moves too, except the dispatch points.

**The active path** is a name-level reachability analysis from the entry points with D189's nine
families (`source_moves_plan.py reach`). It follows imported names through each module's
top-level definitions, not whole modules.

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
| M1 | move | 318 modules; the rewriter changes 649 files with 2661 edits: 2598 import statements, 54 strings, 7 programs in strings, 2 comments (`$E/scan-move1-draft.json`) |

The map is regenerated on the head that holds the pin and the retire, and after R1–R4.
- **At main b844f920** (the pin and D189's retire; `$E/plan-b844f920/`):
  - the module set is identical: 318 modules;
  - the scan rewrites 630 files with 2597 edits (225 test files, against 242 before the
    retire) and lists 135 hazards in 114 files;
  - the pin inventory is unchanged;
  - `core/blas_threads.py` joins `execution/` in move 2's draft.
- **The BLAS pin landed on main at df9c5063** (`core/blas_threads.py`, `core/__init__.py` and the
  run entry points; `cells/__init__.py` unchanged). No module it touches moves in move 1.
- **Gates after the pin** compare crossrev with `record-cda5dc82`, on any CPU count, which is
  still recorded.

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

**Counts can hide a changed failure** in a file that is already red, for example a pin
assertion that becomes a missing file. Each commit also diffs the normalized failure lines of
its red files. On the probe, the 8 red files that read pins on moved files kept their failure
lines (`$E/red-files-failure-lines.txt`).

Tier 3 runs once on the final tree against `tests/tier3_record.json`, together with G3 and G4
(D194). That record's error lines hold 8 references to modules that move 1 moves, so the tier-3
diff should read the record through the committed maps (a reading rule; the record is never
edited).

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

## 11. Identifiers, the registries' new homes, and what keys on a path

**No identifier changes.** Law, kind, operator and model IDs, such as `resolved_pump_tissue@3`,
`cells.transporter@1` or `passive_neutral_permeation@1`, are names, not paths. The moves change
none:
- the rewriter skips a name followed by `@`;
- `apply` edits no definition body, so no ID constant changes;
- crossrev's program texts carry function names only, never module paths, and the probe's were
  identical.

**The new homes.**

| What | Today | After move 1 | After move 2 (draft) |
| --- | --- | --- | --- |
| The operator registry (`OPERATORS`) | `models/operators/__init__.py` | unchanged | `operators/__init__.py` |
| Operators | `models/operators/*.py` | unchanged | `operators/*.py` |
| Active model modules (@1–@3, composite and adapter, water, replacement, apical_vertex, reaction_transport, surface_tissue, surface_kinetic, inner_laws, checks, projective) | `models/*.py` | unchanged | `models/*.py` (unchanged) |
| Older families' model modules | `models/*.py` | `legacy/models/*.py` | unchanged |
| The model registry (`get_model`) | `models/registry.py` | unchanged (refactored by R1) | `registry/models.py` (leaf renamed; the one rename in the draft) |
| Older families' registrations | inside the dispatch chains | `legacy/registration.py` (R1) | unchanged |
| Kinds | `models/inner_kinds/*.py` | unchanged | `kinds/*.py` |
| The kind, species and inventory registries | `core/{kind_registry,species_registry,inventory_species}.py` | unchanged | `registry/*.py` |

**What keys on a module path, and how it stays stable:**

| Keyed on a path | Kept stable by |
| --- | --- |
| Registry dispatch (imports, lazy ones included) | the rewriter; after R1, one constant for the legacy entry point |
| `kind_registry.BUILTIN_PACKAGE` (`"cells.models.inner_kinds"`) | the rewriter (a dotted string) |
| Computed module paths (`"cells.core." + name`), and the `__module__` comparisons in the two active preparations | R2, before the move: full module names in their tables (§3.3) |
| `__module__.rsplit(".", 1)[1]` (`composition_matrix.py:795`, `stable_seed_control_volumes.py:99`) | basenames are kept |
| Code pins keyed by path (§5) | the rewriter rewrites the path and never the hash. Pin tables, and the identities built on them, change deterministically; byte changes make pins stale, and they are never re-hashed |
| Code pins on a module object (`module.__file__`) | follow the module; unchanged unless its bytes change |
| `source_hashes()` keys in run manifests and checkpoints | continuity admission (§13) |
| The continuity probe's `static_name` (`__module__.__qualname__`) | unchanged by move 1; move 2 needs the map-aware resolver (§9) |
| Records written by code (`parser=`, `actual_model_type=`, `type(x).__module__`) | new records name the new paths, and frozen records keep theirs. No test compares the two (grep) |

## 12. Public imports: no compatibility aliases

Moved modules leave no aliases:
- **D185 owns the stable import surface** for contributed modules, in the core-seams pass.
  Aliases would freeze today's paths as public before that pass decides them.
- **An alias of a legacy module outside `legacy/` breaks move 1's rule.**
- **There is no outside user yet:** stage 1 of the module system has not started.

## 13. The probe (main fa19d80c → scratch head d4fa8719, never merged)

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
- **P5a:** R4 by hand on `charged_surface_work`.
- **P5b:** the pinning law `charged_surface_work` and its three backend modules into
  `legacy/processes/`, by the tool.

The active-path checks (crossrev, G1, continuity) ran on P3. P4 and P5 change only older-family
code, which those checks' worlds do not load.

| Check | Result | Evidence |
| --- | --- | --- |
| verify P1, P3, P4 (the tool as committed at 910ebce0, whose selftest had 28 checks), P5b (the head's tool) | holds: 0 problems each; a planted edit refused | `$E/verify-P*-final.json`, `$E/verify-P5b.json`, `$E/verify-P3-planted.json`, `$E/selftest-final.json` |
| P2's extraction | moved text identical; other code identical; only imports changed | `$E/extraction-P2-check.txt` |
| Collected test IDs (P3, P4 and P5b, each against main) | identical: 20792 IDs and the same 13 collection errors | `$E/collect-*.ids`, `.log` |
| crossrev's nine sets (P3), on CPUs 8,24 against `record-a83d8f15` (made on 6,22) | identical in all nine; file listings identical | `$E/crossrev-db8086ea/` |
| G1, six worlds (one per model: @3, composite ×2, water@1, water@2, replacement), one CPU each | identical: 6 of 6, all 688 arrays bitwise | `$E/g1-db8086ea/compare-vs-a83d8f15.json` |
| Continuity resume: checkpoint under main, admitted for P3 by `admit.py`, resumed, compared | proposed (P, B, H, O identical; 31 changed files) and finalised; bitwise at every round; `verify_run` verified | `$E/continuity-db8086ea/` |
| Pinned file moved (P4) | `_pins()` holds; pin-table digest changes; 5 tier-1/2 files, 89 passed 2 skipped in both | `$E/p4-check/` |
| Pinning law moved after R4 (P5b against P4) | `_pins()` holds from `legacy/processes/`; 5 tier-1/2 files keep every outcome. Without R4: `FileNotFoundError` at `src/src/cells/__init__.py` | `$E/p5-check/`, `$E/p5-without-r4/` |
| Tiers 1+2 (P3), 6 CPUs | 518 files, 0 changed against `tests/test_tiers.json`. One count increase, `test_cell_owned_compartments.py` at 148 passed against 140, the same as at a83d8f15. The 8 red files that read pins on moved files keep their failure lines | `$E/tiers-1+2-db8086ea/summary.json`, `$E/red-files-failure-lines.txt` |
| Tiers 1+2 (P4), 6 CPUs | 518 files, 0 changed, the same one count increase; the 8 red files keep their failure lines | `$E/tiers-1+2-cea0fa6c/summary.json`, `$E/red-files-failure-lines.txt` |

## 14. Estimates

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

## 15. For the lead

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
6. **`ensemble/{cluster,coupled}`** (the adapters for the two assembly engines) move to
   `legacy/ensemble/`. `ensemble/families` and `ensemble/cli` stay, as dispatch points (§6).
7. **Registered protocol JSON and other records stay unedited** (§3.2): the default, to
   confirm.
8. **The audits that read one path in two trees** (§3.2): retire with the cluster's tests, or
   translate by hand.

## 16. Move 1's dry run (17 November, at main df2b910b)

*Scratch, never merged: `/mnt/workspaces/Cells/d188-dryrun-20261117/` (`$R`), the moved tree in
`tree/`.*

**What ran:**
- R4 by hand (91fb70a5), as in the probe's P5a.
- The draft map regenerated at df2b910b: the same 318 modules as at fa19d80c and b844f920. The
  tool applied it (10e83979), rewriting 630 files with 2597 edits.
- R1–R3 were not applied. Every hazard file was listed under `reviewed` with its category
  (below), so the 17 R2 sites stand unrefactored and their failures are the known ones.

| Check | Result | Evidence |
| --- | --- | --- |
| Collected test IDs | 18482 against main's 18482, with the same 5 collection errors. **2 IDs differ, only by the mapped path in a parametrization:** `test_open_calcium_regression.py::test_mechanically_reversing_private_extraction_retains_the_complete_closed_parser_AST[src/cells/core/surface_calcium{,_energy}_spec.py-…]` now names `src/cells/legacy/core/…` | `$R/evidence/collect-*.ids` |
| crossrev's nine sets against `record-cda5dc82`, 1 CPU (8) | identical in all nine; file listings identical | `$R/evidence/crossrev-10e83979/` |
| Tiers 1+2 against the record, 6 CPUs | 479 files; 4 changed (§16.1); no count increase | `$R/evidence/tiers-1+2-10e83979/summary.json` |
| `verify` of the move commit (91fb70a5 → 10e83979) | holds: 318 moved, 630 rewritten, 0 problems | `$R/evidence/verify-move1-dryrun.json` |

**The ID gate needs a reading rule.** An ID that differs only by a path the map renames is the
move's own change. The proposal is to compare IDs through the map, as with tier 3's error lines.
The alternative is a stable `ids=` in that test, made by a refactor before the move. **For the
lead.**

### 16.1 The red list

These are every test green on main (df2b910b) and not green in the dry run. Each file was run on
both trees, one CPU per process (`$R/evidence/red-list/`).

| Tests | Cause | Class |
| --- | --- | --- |
| `test_surface_calcium_energy_regulated_dispatch.py`: all 7 | `ModuleNotFoundError` on `cells.models.surface_calcium_energy_*` and `cells.core.surface_calcium_energy_regulated{,_v2}_spec`, from `import_module("cells.models." + module)` | R2, known |
| `test_surface_profile_interventions_dispatch.py`: 4 of 14 (`test_profile_registration_preserves_existing_physical_families`, 4 cases) | `ModuleNotFoundError` on `cells.models.surface_calcium_energy_{hcn_extra,transport,mitochondria,water}` | R2, known |
| `test_surface_active_profile_interventions_dispatch.py`: 5 of 16 (`test_active_profile_registration_preserves_parent_and_composed_dispatch`, 5 cases) | `ModuleNotFoundError` on `cells.models.surface_hcn_extra` and `cells.models.surface_calcium_energy_*` | R2, known |
| **`test_open_calcium_regression.py`: 2 of 44** (`test_mechanically_reversing_private_extraction_retains_the_complete_closed_parser_AST`, both cases) | **An AST-hash pin** (below) | **new** |

**The AST-hash pin.**
- The test rebuilds a parser from `_decode_components` and `parse`'s body, and hashes its
  `ast.dump`.
- `parse` holds a function-level import that the move rewrites (`from cells.models.surface_calcium
  import check_definition` becomes `cells.legacy.models…`; likewise `surface_calcium_energy`). So
  the hash moves: `55e7d3dd…` → `76a77824…`, and `ab7840fc…` → `741915a4…`.
- No move can keep it without a hash change (D187), so it is not an R2 case. It is also one of
  the two renamed IDs.
- **For the lead:**
  - retire the two cases: they pin a reversed extraction of older families' parsers, and the
    frozen evidence keeps them; or
  - change the test before move 1 to hash the parser without its import statements, with its
    reason. That is a test change, not a hash-only update.

**Less the known R2 sites, the tier-1/2 red list is these 2 tests.**

**R2's other test sites are tier 3,** passing in `tests/tier3_record.json`:
`test_active_ecm_polygon_preparation.py`, `test_active_polygon_physiology_preparation.py`,
`test_owned_barrier_interventions.py`, `test_owned_calcium_profile_barriers.py` and
`test_owned_calcium_profile_interventions_dispatch.py`. `test_assembly_cluster.py` already fails
there. The five joint-water fixtures serve tier-3 and integration files. All are expected to fail
on the same cause until R2, and the tier-3 run on the final tree checks them.

**The 38 files that are red on main too** were run on both trees. Their 1648 tests keep their
outcomes one by one, so no failure hides behind an unchanged count
(`$R/evidence/red-files-compare.txt`).

### 16.2 The scan's 135 hazards, by category

| Category | Hazards | Files | Can it reach a moved module? |
| --- | --- | --- | --- |
| A: a computed module path: `import_module("cells.core." + name)`, the `__module__` comparison and the recorded `parser=` path | 30 | 15 (2 src, 13 tests) | yes: R2 |
| B: a computed `-m` path of a CLI worker: `assembly_cell/cli.py:239` builds `"cells." + cli_name`, and `tests/unit/test_assembly_cluster.py:632` asserts it | 2 | 2 | yes: R2. New since step 0, which matched only package prefixes |
| C: a namespace check of the top package: `startswith("cells.")`, `== "cells"`, `removeprefix("cells.")` (the BETSE natives, validation references, `legacy_inventory.py`) | 82 | 78 | no: a moved module stays under `cells.` |
| D: prose ending in `cells.` in a docstring or string, or an embedded program that checks the namespace | 19 | 18 | no |
| E: an f-string labelling a BETSE object's attribute (`f"cells.{name}"`, `validation/betse/betse_reference_extract.py`) | 2 | 1 | no |

- **R2's list at df2b910b is 17 files:** A's 15 and B's 2. Step 0's 17 at fa19d80c included two
  files that D189's retire removed: `test_joint_water_profile_barriers.py` and
  `test_betse_ecm_material_callback.py`.
- **In the real map,** C, D and E files go under `reviewed` with their category, and A and B are
  refactored first.
- Listing: `$R/evidence/hazards-by-category.json`.

### 16.3 The pin intersection

§5's 22 live pinned files carry 43 pins, each a (law, file) pair.
- **R1's six dispatch files:** none is pinned.
- **R3's seven extraction sites:** none is pinned.
- **M1 and move 2** touch 26 of the 43 pins. All are path pins of the 7 path-pinning laws;
  M1 moves all 7 of them. No module pin is touched.
- Move 2 was scanned on the moved tree (`$R/evidence/scan-move2-after-move1.json`). Its draft
  moves 110 modules and rewrites 1160 files.

| Pinning law | Its touched pins, and whether the pinned file's bytes change | Green test today behind it |
| --- | --- | --- |
| `processes/charged_surface_work` | 7 pins. M1 moves `numerics/membrane_redistribution.py` with its bytes kept; the other 6 files are untouched by M1 and by move 2's draft. The law moves (R4 keeps its root) | `test_charged_surface_repository.py` |
| `core/conservative_polygon_tissue_preparation` | `numerics/surface_transport.py`: rewritten by move 2 | none (its test is red today) |
| `processes/stable_seed_control_volume_environment` | `processes/stable_seed_control_volume_physical_bridge.py`: moved and rewritten by M1 | none (D189 retired its tests) |
| `processes/stable_seed_control_volume_physical_bridge` | `core/conservative_polygon_tissue_preparation.py`: moved by M1 with its bytes kept, rewritten by move 2 | none (retired) |
| `processes/stable_seed_partition_advance` | `processes/stable_seed_partition_physiology_bridge.py`: moved and rewritten by M1. `core/{state,devices}.py`: moved and rewritten by move 2. `numerics/surface_transport.py`: rewritten by move 2 | none (red today) |
| `processes/stable_seed_partition_physiology_bridge` | `numerics/surface_transport.py`: rewritten by move 2 | none (red today) |
| `processes/stable_seed_partition_trajectory` | `core/resources.py`: moved and rewritten by move 2 | none (red today) |

- **The only green test behind a touched pin** is `test_charged_surface_repository.py`. It
  holds with R4 (P5).
- **Move 2 must keep that law's six other pinned files byte for byte:**
  `processes/electrochemistry.py` stays where it is, and
  `numerics/{fixed_step,extracellular_field}.py` and the three package files are not rewritten.
  Otherwise the test turns red, because no hash is updated.
- Evidence: `$R/evidence/pin-intersection.json`.

### 16.4 charged_surface_work's binding identity

- **No compared record holds it.** Crossrev's record (`record-cda5dc82`) and G1's saves have no
  charged-surface world: no file names the law ID `held_charged_surface_prescribed_field_work@1`.
  No registered protocol in the checkout names it either; the only JSON mention is the
  visualizer's laws listing.
- **Frozen development evidence from 30–31 October holds bindings made with the old pin table**
  (`/mnt/workspaces/Cells/betse-charged-surface-work-*-20261031-*`).
- **Any later comparison with those is a D148 case:** an in-place change to shared code, here
  the pin table's path key. It is not "identical".

### 16.5 Family membership

These are all older families' modules:
- `models/surface_tissue`: resolved_tissue@1's model;
- `models/surface_kinetic`: the model of resolved_tissue@2–@12;
- `core/surface_kinetic_spec`: that family's definitions;
- `core/surface_tissue_spec`: resolved_tissue@1's definitions;
- `models/kinetic_finite_extracellular`: finite_extracellular@2's model.
- **They stay in the core** because the four families D189 kept are built on them: reached
  75%, 90%, 18%, 100% and 25% at name level. This is D189's "shared code of the four".
- **Their families' registrations move** to `legacy/registration.py` with R1.
- **Their modules stay,** so those older families keep running on core modules. This is allowed:
  the rule is only that nothing outside `legacy/` imports from it.

### 16.6 Found by the dry run, for the real map

- **R2 has 17 files** (§16.2), two of them new since step 0 (category B).
- **Two test IDs carry a mapped path** (§16, ID gate) and need a reading rule, or a stable
  `ids=`.
- **One AST-hash pin** (`test_open_calcium_regression.py`, 2 cases) needs a ruling before move 1.

- **Packages split.** `assembly_cell/__init__.py` and `assembly_cluster/{__init__,controls}.py`
  stay where they are while their other modules move. `controls` is imported only by moved
  modules and two tests. The planner should also move a module whose only src importers are
  moved modules, and a package's `__init__` with its last module.
- **A stale comment.** `core/__init__.py` names `processes/charged_surface_work` in a comment
  without `.py`, which the path rule does not match. A docs-level fix after the move.

## 17. The lead's rulings (17 November 2026, with the advisor)

On §15's eight items, after the dry run (§16):
1. **CLI paths: accepted.** `-m cells.assembly_cell` and `-m cells.assembly_cluster` become
   `-m cells.legacy.*`, with no aliases (§12). The rewriter does not touch `docs/` or the
   README, so user-facing commands and import paths there are updated in a separate docs commit
   with move 1.
2. **The pinned cluster: the proposal of §5 is accepted.** R4 applies to `charged_surface_work`;
   the stable-seed and conservative-polygon cluster moves as it is and refuses at its pins.
   - No test that is green today turns red through a pin (§16.3).
   - `test_conservative_polygon_tissue_preparation.py` stays a recorded red, and goes to the
     user's next retire batch.
   - **For move 2:** `charged_surface_work`'s six other pinned files keep their bytes:
     `processes/electrochemistry.py`, `numerics/fixed_step.py`, `numerics/extracellular_field.py`
     and the three package files.
3. **The coupling list is R3's 7 sites, not the 42: accepted, as an amendment to D189.**
   - The older families' shared modules stay in the core (`models/`), because the four families
     D189 keeps are built on them: `surface_tissue` and `surface_tissue_spec` (resolved_tissue@1),
     `surface_kinetic` and `surface_kinetic_spec` (resolved_tissue@2–@12), and the reached kernel
     of `kinetic_finite_extracellular` (finite_extracellular@2).
   - Their registrations move to `legacy/registration.py` in R1.
4. **Checkpoints across move 2: put to the user.** The default is none, with older checkpoints
   restoring on the tag of the tree before the moves. This blocks move 2, not move 1.
5. **The tier-3 diff reads `tier3_record.json` through the maps: accepted.** It is needed before
   the final tier-3 run.
6. **`ensemble/{cluster,coupled}` move to `legacy/ensemble/`: accepted.**
7. **Registered protocol JSON and other records stay unedited: confirmed.**
8. **The 20 audits that read one path in two trees.** None is run by a green test or an active
   protocol: the dry run's tiers show no red beyond §16.1. They are left untouched, listed here
   as broken by move 1 for the live-tree read, and go to the user's next retire batch (D187).

**From the dry run:**
- **The AST-hash test** (`test_open_calcium_regression.py`, two cases). It compares the parser's
  AST through the map: moved module names are translated back to their old names before the
  hash. No hash literal changes (D187). This is a test change before move 1, with R2. If it
  cannot be done cleanly, the two cases go to the user as a retire item.
- **The collected-ID gate compares IDs through the map,** so a parametrization that names a moved
  path is the same test.
- **The planner takes a reverse closure,** and a package's `__init__` moves with its last module
  (§16.6).

## 18. R1–R4 landed; the deviations accepted (17 November 2026)

R1 landed at d61d4618 and R2–R4 at the merge of d188-r2r4 8c41d7ec. The evidence is in
`/mnt/workspaces/Cells/d188-r1-20261117/` and `/mnt/workspaces/Cells/d188-r2r4-20261117/`.

**Deviations, accepted by the lead:**
- **R1:**
  - control_values crosses the active and legacy line, so its chain runs in three parts. First
    matches are unchanged.
  - Active worlds still load the legacy registration through misses. This is accepted until the
    core-seams registration tables.
  - Two type-only annotations naming legacy types are dropped.
- **R3:**
  - An eighth extraction, `voltage_gated_spec`'s `fraction`.
  - No extraction for `cav_channels`.
  - **The planner's keep rule:** a non-family module that a reached core module imports stays
    in the core. That keeps `calcium_gates`, `kinetic_finite_bounds` and the new
    `rate_junction_spec`, beyond D189's amended list.
  - Dispatch points count as couplings.
- **`output_bound`** goes through a legacy hook (`_CELL.working_size`), not a lift.
- **Move 1's map holds 334 modules,** not 318. calcium_gates stays (−1). R3's six old modules (+6),
  R2's two unreached preparations (+2), the reverse closure (+7) and two package `__init__`s (+2)
  move.

**Before move 1** (its owner):
- **R5:** the detached assembly worker takes its root from the package.
  - Today `assembly_cell/cli.py`:219 copies `Path(__file__).parents[1]`, and `io.py`:44 roots
    `source_identity` there.
  - After the move both would name `src/cells/legacy`, so the worker would launch from a copy
    holding only `legacy/`. No green test sees this.
  - R5 adds a test with a planted case.
- **The map,** committed in `scripts/moves/` in the commit before the move, since the AST test and
  `verify` need it.
- **A docs commit** with the move, for the user-facing commands and import paths (§17 item 1).
- **M1's gates:**
  - collected IDs through the map;
  - crossrev;
  - G1 at 113 of 113;
  - tiers 1+2 with 0 changed;
  - the red files unchanged;
  - a continuity resume across the move.

  G1 and continuity were not run on the dry run's moved tree.
- **Before tier 3's final run:** the tier-3 diff through the maps must also translate moved files
  inside absolute paths (§17 item 5).
- **Lint:** the move adds 12 line-length findings. They are fixed in a separate commit, never in
  the move commit.

## 19. Move 1 landed (17 November 2026)

Merge 7bb8bf23 (d188-m1 9b20034a), tagged `d188-move1-landed-2026-11-17`. The tree before it is
tagged `pre-d188-move1-2026-11-17` (097f802e). Every gate of §18 held; the evidence is in
`/mnt/workspaces/Cells/d188-m1-20261117/gate-9b20034a/`.

**The lead's rulings on what the move found:**
- **Docs.** Code paths of moved modules are rewritten in living and dated notes by the move's own
  text rules: paths only, with the text otherwise unchanged. This note keeps the old paths it
  documents, and `docs/history/` is untouched.
- **`cells tissue-geometry --help`** now shows `usage: cells.legacy.tissue_geometry`, because the
  rewriter followed its `prog=` string. This is accepted, since the module is legacy.
- **One registered protocol's data pin went stale** through R5:
  `validation/topology/joint_water_profile_phase_handoff_protocol.json`. 94 of its 263 digests
  were already stale, and no test reads it. It stays unedited, under §17 item 7.
- **For move 2's map:** `assembly/cli.py`, `assembly_pool/cli.py` and `ensemble/cli.py` still copy
  file-relative roots. Any map that moves one of them needs R5's treatment first.
- **Move 2 is next.** It waits for the user's answer on checkpoints (§17 item 4). Its 36 unplaced
  modules are placed against `docs/CORE_SEAMS_DESIGN.md` §8.2, so files move once, and
  `charged_surface_work`'s six pinned files keep their bytes.

## 20. `processes/` dissolved, option (R) (17 November 2026, D198)

The user chose (R): retire the pinning legacy laws and their tests, and move what the engine uses.
- **Superseded:** §17 item 2, and §18's and §19's rulings on keeping the six files' bytes. Step
  0's extraction exclusion rule (`docs/CORE_SEAMS_STEP0.md` §2) holds only until the retire batch
  lands.
- **The batch comes first.** The tree is tagged, and the exact list is taken from the dissolved
  trial tree. A file an active entry point reaches moves; an unreached file retires.
- **Move 2's map** is then regenerated without byte-keeping constraints.
- **R6 is re-measured.** If `src/cells/__init__.py` is free, the BLAS pin returns to one home
  (D190's first wording), on 2 CPUs, with a planted control.
- **Handoff:** move 2's owner finishes through M2's landing. A fresh owner then takes tier 3, G3
  and G4 on the final tree.

## 21. Move 2 made (18 November 2026, on d188-m2-prep at main bb69abd4)

*Landed on 18 November 2026 (merge d5d56d1b, tag `d188-move2-landed-2026-11-18`). Evidence: `/mnt/workspaces/Cells/d188-m2-move-20261118/`.*

**The map** (`scripts/moves/move2.json`, with its path table):
- **117 modules move.** 108 come from the planner's rule table (§9); the 9 it leaves unplaced are
  placed in the map's `placement`, each with its reason.
- **Ten packages are created,** each with its text: `definitions/`, `execution/`, `laws/` with six
  of its groups, and `records/`. `laws/junctions/` is `coupling/`'s package file, moved.
- **`processes/` (D198) and `core/` (R6′, the BLAS pin's one home in `cells/__init__.py`)
  dissolve.** Their package files go, by the map's `dissolve`.
- **`laws/mechanics/` is a seventh law group** beyond D188's six, approved by the lead on 17
  November. It holds `vertex_mechanics` (MG1's law), and later tissue mechanics.
- **The other placements:**
  - `electrochemistry` goes to `laws/`;
  - `calcium_gates` to `laws/channels/`;
  - `patch_electrodiffusion` to `laws/routes/`;
  - `legacy_entry` to `registry/`;
  - `spec_values` and `vertex_preparation` to `definitions/`;
  - `source_layout` to `records/`.
- **Hazards:** every one of the scan's 128, in 111 files, is reviewed. The set is the one dry run
  4 read.

**The move commit** is `apply` alone: 1270 files rewritten. `verify` holds with 0 problems.
- **A second `apply` changes nothing.** It needed one tool fix after the move: a reviewed hazard
  file that the map moves keeps its review at its new path. Two had moved.
- **The declaration** follows in its own commit: `cells.records.source_layout.MOVES` names the two
  dissolved folders and the restore tag `pre-d188-move2-2026-11-18`.

**Outside the rewriter's scope:**
- **`visualizer/tools/make_engine_view_fixture.sh`.** Its six imports and one path check get a
  follow-up commit with the same old-to-new list, which CellsViz applies to the visualizer
  branch's copy.
- **The docs.** Commit by the rules of §19: 56 files, the library pages among them, whose
  generated blocks name the moved files.

**The two tier-3 pin tests** (`test_joint_water_profile_interventions`,
`test_owned_calcium_profile_interventions`) fail first at a different pin than the tier-3 record
says:
- the record has `src/cells/core/er_spec.py`;
- the tree has `src/cells/__init__.py`, both before the move and after it, because R6′ edited that
  file;
- after the move, 103 of 181 and 90 of 152 of their pinned paths are missing, against 67 and 54.

No hash is updated (D187).

**Open branches:**
- **core-fixes and packed-gpu-planner carry over by §10's procedure,** each starting from the
  branch merged with main:
  - the tier record re-folded with `tiers --base`;
  - the branch's tests run on the merged head;
  - then the map applied and `verify` run.
- **packed-gpu-planner's own modules.** It adds `core/packed_runner.py` and `core/packing.py`,
  which exist only on the branch. The committed map refuses the branch for them, as §10 intends,
  so its owner applies the map extended by those two modules (to `execution/`).
- **windows-next and fr45-transporter** are superseded on main, and are pruned after the move.

**What the gate found after M2, fixed in follow-up commits (the move commit stays the tool's
output):**
- **Recorded text.** The dotted-name rule rewrote strings that saved data repeats and code
  compares:
  - a preparation recipe's provenance (`cells_flux`), which R1's 274-definition harness caught
    as 8 refused definitions;
  - the FR-4/5 protocols' execution-path ruling;
  - the registered MG0c protocol's engine lines.
  The registered JSON was never touched, because JSON is outside the scope. The code strings are
  back to their pre-move bytes, each marked with a comment holding `source-moves: keep`. That is
  a per-line keep, which the tool honours in apply, in `verify`'s old-reference scan and in a
  second application. It is for an identifier that is never resolved as a module. A live
  reference keeps its rewrite: an import, a dispatch name, a package to scan, a source path to
  hash or read, a message.
- **Paths the text rules cannot see,** each fixed by hand:
  - components joined at run time (`root / "core" / "x.py"`, `MODELS / "operators"`);
  - a folder prefix completed by concatenation (`"src/cells/models/operators/" + name`);
  - a moved module's bare file name inside a message.
- **Move 1's map on a merged head (base = head).** The carry-over proofs ran this check, and it
  was refused twice:
  - first, because D198's retire batch (330aeb55) removed 20 of move 1's 334 modules, which are
    in neither place. The proofs now cut those 20 from the map they check;
  - then, because the import check did not resolve namespace packages. Before the move,
    `cells/records/` held only `relations.py`. The import check now resolves a folder of modules
    without a package file, as Python does.
