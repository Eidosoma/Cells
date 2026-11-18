# External modules: one assembly path for Cells and independent packages (design)

**Status: PROPOSED, 15 November 2026, for the lead and the advisor; §6 decided on 16 November (D185). Docs only.** Code read at
main 9f60417b, `integration-d172` d732781d and `core-d172` 119ffb74; only main counts as "holds
today". `file`:N cites main unless a branch is named; §7.4–§15.6 and items such as A7, B1, F3
and P2 are INNER_MODEL_V4_DESIGN.md's. D172's round landed on main on 16 November (ab267c39, tag
`d172-landed-2026-11-16`), so what the Round column names now holds on main, except what it marks
reserved. Line numbers cited on `integration-d172` and `core-d172` are as read on 15 November, and
main's line numbers as read at 9f60417b.

**The requirement (the user's, paraphrased).**
- Cells stays MIT, for broad adoption. Independently maintained packages use, extend and compose
  it, and the project extends itself through the same interfaces.
- External components meet the same validation, composition, execution and accounting contracts
  as built-in ones, and Cells coordinates them.
- Delivery is staged by real consumers, along one path: register, resolve, validate, assemble,
  compile, run.

**Engine models** (AGENTS.md):
- **stage 1:** `resolved_pump_tissue@3` with one external channel law, alone and under
  `resolved_pump_composite@1`;
- **stage 2:** an external kind or operator in the composite;
- **stage 3:** the first levels-of-detail pair.

## 1. Status at every level

**Status words:** **holds** (main: code or a landed test); **round** (`integration-d172`,
`core-d172`'s dispatch and compile-key commits, or INNER_MODEL_V4_DESIGN.md §7.4; the Round
column cites `integration-d172`); **planned** (staged here); **not designed**.

| Level | Contract on main | Round | External | Closed point; v1 limit |
| --- | --- | --- | --- | --- |
| Registration | The `get_model` isinstance chain (`registry/models.py`:139–779; "no dynamic plugins", :1); the `parse_spec` chain on ID strings (`definitions/specs.py`:1469); the import-time `OPERATORS` dict (`operators/__init__.py`:29); `INNER_MODEL_IDS`, `INNERS` (`pump_composite_spec.py`:41; `pump_composite.py`:67) | A build-scoped kind registry (seams 1–4 below) | Kinds: holds, since the round. Laws, operators: planned | Module-level tables and chains |
| Definitions, parameters | JSON with exact key sets (`specs.py`:74, :1470); values are data; no organism definition (ARCHITECTURE.md:52) | The species registry (`registry/species_registry.py`) | **Holds** for definitions and builders on built-in IDs | — |
| Laws | Five channel laws in literal tables, all others refused (`surface_pump_v3_spec.py`:53, :113) | Declarations (`inner_laws.py`:132, :171, :183); per-law dispatch; the structure in the compile key | Planned: stage 1 | Module-level tables; codes "next free, never reused" (integration-d172 `inner_laws.py`:6–7); the RK4 bound by law-ID literal (core-d172 `surface_pump_v3.py`:1042); two gates only (:233) |
| Stateful mechanisms | The operator contract (`contract.py`:103–335), checked at registration (:379) | Kinds: fields and optional hooks (§7.4 (k); 20 in the landed `Kind`); door S; `USES_INNER` | Planned: stage 2 | The composite is cached by law-ID strings (`pump_composite.py`:92–102), with one instance per law (:150). Kinds: rules (a)–(c) |
| Composite models | One inner model plus ordered operators (`pump_composite_spec.py`:1–27); FR-1's compartments | The compartment identity map (B2) | Not designed; §3 | Nested compartments "not now" (ARCHITECTURE.md:152) |
| Geometry, connectivity | Topology in the definition; geometry from builders (RUN_VIEW_DESIGN.md §4); vertex mechanics as its own family (`apical_vertex_spec.py`:29) | — | Not designed | Topology changes only through operators |
| Controls, events | `EVENT`, `EXPERIMENT_KEYS`, `CONTROL_FIELDS`, `CONTROL_FACTORS` (`contract.py`:109–124) | Kinds' `control_values` | Planned: stage 2 | Kinds: rule (d) |
| Observations, analysis | `observe`, `READOUT_COLUMNS`, `REPLACES` (`contract.py`:51–58) | `VIEW_LAYERS`, `view_events` (integration-d172 `contract.py`:210–220) | Planned: stage 2. **Holds** on saved outputs | Kinds: rule (b) |
| Resolution, LOD | — | B8's four fields, reserved (`inner_laws.py`:95–99) | Planned: stage 3 | No "represents" key (ARCHITECTURE.md:244–246) |
| Numerics, coupling | A closed integrator tuple (`surface_pump_spec.py`:32); the field solver by layout type; `STEP_ID`, `RK4` (`contract.py`:107, :112); the splitting ID (`pump_composite.py`:66) | Reserved: the implicit slot (§7.4 (g) 4) and the step context (B1) | Not designed; §5 | `get_model` never sees the execution block (§7.4 (a)) |
| Backends | JAX on CPU or GPU, float64 (`execution/devices.py`:22–35) | — | Not designed; §5 | — |

**What the round commits to for modules.** These are the core owner's answers and the lead's
rulings, relayed on 15 November and now in §7.4 (j)–(k). They were ruled before any kind module or
kind registry existed, and they landed with the round on 16 November: the kind registry
(`registry/kind_registry.py`) and three built-in kinds (`models/inner_kinds/`) are on main.

**Seams:**
1. Core imports no kind module. Every kind, built-in or not, registers through one call into a
   registry that parse and build take, defaulting to the built-in one.
2. New kinds and laws take namespaced IDs (`cells.transporter@1`). Bare IDs resolve in `cells`;
   external IDs must be qualified.
3. The canonical kind order is the sorted namespaced ID.
4. A registered but undeclared kind changes nothing: not the classes, the compile key or the
   snapshot layout. A second planted-kind test checks this.

**Version-1 limits on kinds:**
- (a) Ledger terms fold into today's ten ledgers by role.
- (b) State fields are observation columns, after today's; readouts follow today's.
- (c) Material moves land in the shared inventory, and only own accumulators stay apart.
- (d) Controls are availabilities in [0, 1], unless the control-domain hook declares otherwise.

**Closed points outside lookup (main):**

| Point | Where | Blocks | Opened by |
| --- | --- | --- | --- |
| Compile key | `compile_window` keys on functions, rows, tree and shapes (`execution/vector_windows.py`:343–352); core-d172 adds `structure_key` (:354) | No external identity | §2.5 |
| Composition matrix | Pairwise over `OPERATORS` (`composition_matrix.py`:36, :45); untagged refusals fail its test (`test_composition_matrix.py`:27) | Cannot list unseen modules | Admission per composition; a per-registry report (§6) |
| Snapshot and checkpoint identity | `source_hashes()` covers only Cells' `.py` files (`io.py`:30–35), refused on change (:159); exact manifest keys (:135–146); `type(state) is STATE_TYPE` (`execution/runner.py`:80); random state refused (`io.py`:156) | A changed module restores silently; nowhere to record it | §2.5; RNG §5 |
| Freeze tool | Git-listed checkout paths only (`source_snapshot.py`:26, :93, :229); the base snapshot holds `src`, `tests`, `validation`, `pyproject.toml` | Cannot hold an installed module | §6 |
| Tree guards | Scan `src/` or the checkout (`test_engine_betse_boundary.py`:13–21; `test_continuity_bypass.py`:251) | Blind to outside packages | §6 |
| Packaging | `plastic-heredity-cells` builds from `src` (`pyproject.toml`:6–22), but runs use `PYTHONPATH=src` (`scripts/test_tiers.py`:79) | An installed Cells is untested | S9. Debt: `processes/stable_seed_partition_*` import `validation` (`…_trajectory.py`:15–17) |

## 2. Stage 1: explicit registration and one external law

### 2.1 The law

A separately installed package, `cells-example-law`, adds the channel law
`example.boltzmann_mh@1` to an unchanged Cells installation. A world with one population of it
parses, builds, runs, checkpoints and records provenance through the normal path.

**Why a member of an existing kind.** It is a law in the requirement's sense: a kernel and a
declaration, with no state of its own.
- Its gates, transfers and heat use the channel kind's fields, whose accounting is already
  checked.
- A one-law external kind would own fields under rules (a)–(c), which makes it stage 2.

**The law itself.**
- Gates m and h, with Boltzmann targets and constant time constants; opening m·h; permeant K⁺.
  Two gates, as R's dispatch requires (core-d172 `surface_pump_v3.py`:233).
- **What it declares.** It reads the membrane voltage (V) and its own gates, and changes the
  permeant's amounts (fmol, inward-positive) only through the kind's constant-field flux. It
  declares its voltage domain, and a step outside it is refused, as for today's laws.
- **Its declaration** is the round's `ChannelLaw` (integration-d172 `inner_laws.py`:79–99): pure
  JAX kernels, the stage term `constant_field_slope` (v1's only one), `rk4_step_s` and
  `provenance: cited`.
  - **The code.** `code` is a required field (:84), and dispatch reads `law.code` (core-d172
    `surface_pump_v3.py`:237). A module leaves it to Cells: resolution binds it per definition
    (§2.3).
  - **Capabilities.** `cells.channel_law@1` adds optional fields for backends, dtypes and
    integrators. Their defaults describe today's laws, and §2.4 checks them.
- Kinetic constants are structure; permeability, abundance and initial gates are values.

### 2.2 Registration is explicit

```python
from cells import modules
import cells_example_law                       # importing registers nothing
registry = modules.BUILTIN.extended(cells_example_law.MODULE)
spec = parse_spec(data, registry=registry)     # resolution happens here, once
```

On the command line: `cells run --module cells_example_law world.json --output out/`. The flag
repeats, and `resume` and `branch` take it too.

- **Never implicit.** Nothing registers at import, by entry-point discovery, or from a
  definition. Definitions stay data, and no loader imports what a definition or manifest names.
- **Why.** JAX configuration is process-wide (`execution_device` sets x64, `devices.py`:25), so
  an imported package can change an unrelated model's numerics. Discovery would tie runs to
  whatever is installed.
- **Entry points**, as a later opt-in, would only list modules, never register them.

### 2.3 The registry, resolution, IDs and codes

- **`Module(namespace, distribution, interfaces, components)`:** a package's one export, inert at
  import.
- **`Registry`: immutable.**
  - `BUILTIN` registers `cells` through the same `extended` call, from each built-in's own
    package.
  - `extended` returns a new registry or raises (§2.4).
- **`Resolution`:** at parse, the definition's IDs resolve to a frozen map, ID → (declaration,
  module identity), of the components it uses.
  - It rides on the parsed model block, outside `to_dict`, so `resolved_config.json` and the
    fingerprints are unchanged.
  - A re-parse of a spec's own dict reuses that spec's resolution. `write_snapshot` does this
    re-parse (`io.py`:82), and `write_run` calls it for every checkpoint (:243–248).
  - Only raw-data entry points take `registry=` (`parse_spec`, `load_spec`, `load_snapshot`, the
    batch loaders, the CLI). Threading is incremental across 68 `parse_spec` and 74 `get_model`
    call sites, and an unthreaded path refuses external IDs.
  - Registration order never matters. The law adds no sum: its flux joins the kind's per-slot
    arrays, in A7's order.
- **IDs:** `namespace.name@major`. A namespace is `[a-z][a-z0-9_]*`, one per distribution, and
  `cells` is reserved.
- **Interfaces** carry an ID and a major version: `cells.channel_law@1` first, then `cells.kind@1`
  and `cells.operator@1`. Modules declare those they implement, and Cells those it supports. An
  idle optional field keeps the major; a change of meaning takes a new one. Compatibility never
  rests on the static `__version__`.
- **Codes.**
  - `cells` laws keep theirs.
  - An external law's code is 2^15 plus its canonical rank among the structure's external laws, a
    function of the resolved structure alone. The code array is int64 (`surface_pump_v3.py`:178).
  - Dispatch selects on disjoint codes (P2), so order changes no bit.

### 2.4 Errors

Every error is raised at construction and names the module, the component and the remedy.

| Error | When |
| --- | --- |
| Duplicate | A namespace or component ID appears twice |
| Foreign or reserved namespace | A component lies outside its module's namespace, or an external one is `cells.*` |
| Unsupported interface | An unknown ID or major version. The supported ones are listed |
| Malformed declaration | Fails its interface's checks, as `check_declarations` does (`contract.py`:379) |
| Missing component | Unregistered namespace, or absent from its module (`@2` asked, `@1` provided) |
| Missing dependency | A required kind, interface or component is unregistered |
| Incompatible capability | The selected backend, precision, integrator or stage term is undeclared |
| Identity mismatch | A checkpoint's module differs from the registered one |

### 2.5 Invariance and identity

**Unused components change nothing.** The implementation object, its types (by identity), the
compile key, the programs, the bits and the run record all stay the same, because the
resolution, the structure and the record hold only what the definition uses.
- **I1.** Build one world per path (scalar, windowed, vector-window, batch, composite) with
  `BUILTIN`, then with `BUILTIN.extended(example, planted)`. Every path gives:
  - `is`-identical types;
  - crossrev's jaxpr and constants unchanged (`composite_crossrev.py`);
  - bitwise outputs (`results_baseline.compare`);
  - manifests equal except for time stamps.

  On the vector-window path, where `compile_window` lives, the compile key is also equal, with 0 s
  of compile on the second build.
- **I2.** In fresh processes, importing the package registers nothing. A run without it installed
  equals one with it registered but unused.
- **I3.** Permuting the registration order changes nothing.
- **I4.** The round's second planted-kind test, registered from outside `src/cells`.

**The guarantee's scope.** I1–I4 show invariance for the example module, not for every module.
- **Why Cells can't guarantee it:** explicit registration still imports the package, and an
  import can change process-wide JAX settings.
- **What Cells re-asserts:** x64, at every run (`execution_device`, `execution/devices.py`:25). It does
  not re-assert settings such as the default matmul precision or the PRNG implementation.
- **So two things hold:**
  - the build checks a declared set of process-wide settings against Cells' required values, and
    refuses a run whose settings differ, tested with a planted module that changes one at import;
  - the conformance kit (§6) checks invariance per module.

**Fingerprints.** A definition names IDs only, so a world that uses an external law keeps the same
definition fingerprint across module versions. The module stamp therefore also enters the batch
signature and the batch snapshot's definition check, as it enters the compile key and the
manifests.

**Caches.** The registry stamps each external structure entry with its resolved declaration and
module identity; built-in entries stay IDs, so today's keys hold.
- The structure keys `compile_window` (core-d172 `vector_windows.py`:354) and the implementation
  caches (core-d172 `surface_pump_v3.py`:1414; main `pump_composite.py`:92). Registries binding
  one ID to different objects never share an executable.
- JAX's persistent cache (`output_paths.py`:25) keys on the lowered program.

**The record, per module used** (the shape of §6 decision 1's options, which D185 decided as (c);
AGENTS.md's provenance rule is amended to match): namespace, distribution, version and interfaces; the VCS
revision and dirty flag where recorded (PEP 610 `direct_url.json`); and its files' SHA-256,
computed at run time as `source_hashes()` does, with no literals and no per-call layer. It is
written as `modules` into `manifest.json` (absent when none, like `composition`,
`io.py`:293–300) and into the checkpoint manifest.

**Loading** (decision 1, decided by D185) refuses a missing or different module, as it refuses changed Cells source
(`io.py`:159). D153's record can admit a change. Loading imports nothing.

### 2.6 The example package, and what Cells changes

```
cells-example-law/
  pyproject.toml              depends on plastic-heredity-cells; no entry points
  src/cells_example_law/
    __init__.py               MODULE = Module("example", ...); nothing else at import
    law.py                    the ChannelLaw and its two pure JAX kernels
  definitions/, tests/        a one-cell world; the kit on MODULE; kernels vs closed forms
```

**After the landing:**
- **New:** `src/cells/modules/`, with the registry types, the errors and the conformance kit. The
  kit ships only from `src` (`pyproject.toml`:21–22). The core-seams pass built it first, as a
  provisional import surface with no stability promise until a first outside module arrives
  (D195; CORE_SEAMS_DESIGN §8.5).
- **CORE:** the channel table through the registry:
  - `inner_laws`' checks (integration-d172 :227–234);
  - the parser's `LAW_CODES`, `LAW_PERMEABILITIES` and `GATE_COUNTS` (`surface_pump_v3_spec.py`:53,
    :55, :62, :113, :123);
  - the layout's codes (`surface_pump_v3.py`:188);
  - `structure()`;
  - the RK4 bound, read from `rk4_step_s`.
- **INT:** `registry=` threading, the manifests' `modules`, and the CLI flag.

### 2.7 Acceptance

| Test | Pass |
| --- | --- |
| S1 Pipeline | It runs through `cells run --module` and the API, via `io.write_run`; its files name the law and the module |
| S2 Errors | Each row of §2.4, in the kit's negative cases |
| S3 Absent kernel | Its kernel is only in its own world's jaxpr |
| S4 Accounting | Ledgers close at today's tolerances; a planted wrong valence and a reversed flux both fail |
| S5 Reuse | A permeability or abundance change compiles in 0 s, bitwise equal to a fresh compile |
| S6 Restart | It resumes bitwise in a fresh process; an unregistered or changed module is refused |
| S7 Invariance | I1–I4 |
| S8 CPU/GPU | On the L4, vector-window path, by the backend-variant method (inner-model note §5.3) |
| S9 Installation | Wheel installs into a scratch venv on disk leave Cells' `source_hashes()` unchanged. The test unsets `PYTHONPATH` and asserts that `cells.__file__` lies in the venv |
| S10 Early refusal | A GPU run of a CPU-only component, or RK4 without a bound, is refused before compile |

**Gates:** S8 is a recorded L4 run, S9 runs in tier 2, and the rest in tier 1 or 2.

Passing qualifies the interface, not the law's science.

## 3. Stage 2 (outline): a stateful mechanism and a reusable composition, each twice

- **The mechanism** is an external kind (§7.4 (k), rules (a)–(d)) or an external composite
  operator, as its physics needs.
- **Instances.** In a kind, an instance is a row on the kind's axis, with no fields or objects of
  its own. `structure_errors` refuses a repeated operator (`pump_composite.py`:150), so operator
  instance IDs with scoped fields are designed here.
- **A reusable composition** is a host-side template.
  - Before resolution it expands into definition fragments with scoped IDs (`left.lumen`),
    parameters and explicit connections.
  - The identity map keeps scope paths for the run view.
  - Today's admission refuses conflicting owners and cycles, per slot under door S.
- **It depends on** schema A, the seams, door S (two instances changing one field on disjoint
  slots), FR-1's identity map (B2) and the run view's declarations.

## 4. Stage 3 (outline): a reduced and detailed pair

- **The consumer.** ARCHITECTURE's first levels-of-detail case: the fuel case's regeneration
  reaction against a small detailed network (D175, D176), shipped through the module path.
  Nothing is built for the example alone (D144).
- **It needs:**
  - B8's fields, implemented;
  - the "represents" key, compared at admission;
  - a selection per component and per scope;
  - one shared interface, with each representation closing its own ledgers;
  - the envelope and the error budget declared first, with one case outside them failing.
- **Rule (c) binds it:** the detailed intermediates must be inventory rows (D165's cap of 16)
  unless kinds may own pools.
- **Runtime switching** comes later (ARCHITECTURE.md:266–268).

## 5. Numerical, backend and provenance contracts

These are boundaries only. Each is implemented with its first consumer.

| Responsibility | Cells | An extension |
| --- | --- | --- |
| Steps | Accepts or refuses; refusal returns the start state (`contract.py`:45–46) | Reports validity; changes no dt except through declared, checked substeps |
| Stages, clocks | Tableau, stage times, compulsory events, counters (B1) | Rates at the given stage state; reads no clock |
| Events | Times on multiples of dt, in declared order | Declares its times at the definition |
| Domains | Takes their conjunction on host and device; refuses, never repairs | Declares domains and bound terms; never clips |
| Accounting | Books ledgers from applied transfers (§7.5) | Returns applied transfers by row; books only its own accumulators |
| Errors, RNG | Decides acceptance; owns streams, keys and checkpointed state (null today, `io.py`:114) | May supply an error estimate; takes keys, never seeds |
| Checkpoint | Saves declared state; restart is bitwise | Keeps nothing outside declared fields |
| Backend, precision | Device, dtype, placement, compile key | Declares backends, dtypes and determinism; anything else is refused at construction |
| Algebraic coupling | Declared order; implicit slots | Declares a residual; refuses on non-convergence (F3, §15.6) |

**Runs record** the Cells snapshot, the module identities, the structure and methods, the backend,
the reproducibility mode (Q7's flag), the RNG and the qualification scope. Interface, accounting,
accuracy, validity and performance are qualified apart.

## 6. Decisions for the user

**Decided by the user on 16 November 2026 (D185):**
- 1: (c);
- 2: new physics goes into `src/cells` as modules of its structure. (b) was confirmed first and
  revised by the user the same day (D185);
- 3: the conformance kit, where a pass means the kit's checks passed, not that the science is
  qualified;
- 4: (a);
- 5: (b) first.

D185 adds a declarations manifest and a contributor guide with a pull-request template.

Still open: §6.3's question of whether the project lists the modules that pass, and provenance
for in-tree contributed modules (stage 1's design). AGENTS.md's physics rule stands (D185, item
3).

1. **Provenance.** AGENTS.md's provenance (Git revision, dirty diff, frozen snapshot) cannot
   cover an out-of-tree module.
   - (a) The recorded identity (§2.5) counts, which changes that rule.
   - (b) The module's files are frozen beside Cells', so the freeze tool takes a root outside the
     checkout.
   - (c) (a) for development runs, (b) for registered and judged runs.

   Identity is computed at run time either way, with no attestation layer.
2. **D144 with modules.** One-consumer physics could now live in a module. What must still enter
   core?
   - (a) Nothing changes.
   - (b) Modules incubate; physics enters `cells` with a second consumer and its qualification.
   - (c) Core keeps state, accounting, seams and numerics; laws live in modules.

   AGENTS.md's rule on physics in `validation/` must then say whether a module is "the engine".
3. **Qualifying outside modules.** The tier gate and the tree guards cannot reach them.
   - **Proposal:** a conformance kit shipped in Cells. It runs the declaration and error checks,
     I1–I4, ledger closure with planted controls, executable reuse, a fresh-process restart,
     CPU/GPU agreement and the matrix report. It also scans for reference-simulator imports,
     which AGENTS.md keeps out of process, in modules too.
   - It records both identities and each claim, with every property apart.
   - **Open:** whether the project lists the modules that pass, and whether a pass is more than
     the author's claim.
4. **Where the example lives.**
   - (a) A separately installable folder here (say, `examples/modules/cells-example-law/`),
     gated by tier 2 through a wheel install, with a test that it imports only Cells' public
     interface.
   - (b) Its own repository. That proves independence, but needs CI against pinned releases.
5. **A module PR.**
   - (a) Into `cells` as core physics, under D142, D144 and the full tier gate.
   - (b) In-tree under its own namespace, in a contributed-modules area: installable, MIT, with
     an owner, gated by the kit and the tiers.
   - (c) Out of tree, listed by a docs PR with its conformance record.

   These can coexist; which comes first is the user's call.

## 7. The seams this round must leave open

**Confirmed: the core owner's four answers** (§1; §7.4 (j)–(k)), which landed with the round on 16
November. Stage 1 builds on all four, and nothing more is asked of the round:
1. a build-scoped kind lookup;
2. namespaced IDs;
3. a sorted-ID canonical order;
4. a registered but undeclared kind changes nothing.

**Where they limit a module case:**
- **Order 3 sets both field layout and hook evaluation,** so kinds whose stage reads or bookings
  do not commute would compose alphabetically, not physically.
  - Cheap now, costly later: name the two orders apart in the seam code, equal in version 1. A
    later dependency order then moves no fields or snapshot layout. *Met in the round:* the hook
    order is named apart from the field order (`tests/unit/test_kind_rules.py`).
  - Until then, refuse non-commuting hooks on the same rows (a request for §7.4 (k)). *Met in the
    round:* two kinds' stage reads on a shared row are refused at binding, and each booking writes
    only its own kind's fields (`tests/unit/test_kind_rules.py`).
- **Seam 1 covers kinds, not member laws.** Stage 1 opens the channel table after the landing, so
  the round need only avoid hardening:
  - a global code sequence for non-`cells` laws, or `code` as a field a module must supply;
  - behaviour keyed on code values beyond equality and F1's code-0 padding fill;
  - consumers reading `CHANNEL_LAWS` rather than the structure.
- **Caches.** Both `implementation` caches key on structures and ID strings. With `registry=`, a
  registry's resolution must show in the structure entries (§2.5).

**The lead's four scope rules, as version-1 limits:**

| Rule | Blocks for a kind | Cost to lift |
| --- | --- | --- |
| (a) Ledgers fold into today's ten by role | A new conserved quantity (momentum, a count outside the inventory). Operators already declare own ledgers (`contract.py`:42–44), so such a module can be an operator | **Moderate:** `surface_pump.LEDGERS` and `DEVICE_CHECKS` are literals shared with @1 and @2 (`surface_pump.py`:513, :694). Cheap if the seams read ledger lists from the implementation object |
| (b) State observed after today's columns | Private state or solver workspace, then stored in every run | **Cheap:** a flag touching only kind worlds |
| (c) Material in the shared inventory | Pools under one species identity: bound states, membrane-resident species, stage 3's intermediates | **Moderate:** hook 4 (`ledger_terms`) would take kind-held amounts by species identity, which the species registry resolves |
| (d) Controls are availabilities in [0, 1] | Nothing: the control-domain hook declares other domains | **Cheap** |
