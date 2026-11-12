# Architecture review notes (12 November 2026)

Status: **for review by the user and a second reviewer.** This is a read-only review;
nothing in it has been started.

- **Read:** `src/cells` at `main` `302943e`, plus the composite branch
  (`worktree-agent-a4ece8233841c1c5f`, head `996b7c5`) for the operator contract.
- **Method:** the lead gathered the evidence below with read-only commands, and the
  advisor (a stronger reviewer model) reviewed it. The lead then checked the two points
  the advisor called thin (on-device checks, and the per-step factorisation).
- **Asked for by the user:** the core architecture, the GPU-native angle, and how clean,
  modular and object-oriented the code is.
- **Related:** [Architecture](ARCHITECTURE.md),
  [Parallel execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md), and the
  design note's §3 ([CELL_DIVISION_DESIGN.md](CELL_DIVISION_DESIGN.md)) with D142–D144 in
  [DECISIONS.md](DECISIONS.md).

## Summary

The composite model's rule is the right architecture:
- objects exist only when a model is built;
- the compiled step is pure array code.

That rule covers one model family so far, the pump tissue under `resolved_pump_tissue@3`.
The rest of the engine is an older design: one module per combination of features.

"GPU-native" today means many small independent worlds batched on one device:
- The GPU pays off for ensembles.
- One large interacting world (an organ) is not yet reachable. Each IMEX step does a dense
  factorisation, and there is no code to split one world across devices.

Nothing here should start before the open branches have landed (see PROGRESS).

## 1. Two architectures side by side

**The older design: a module per feature combination.**

| Measure | Value |
| --- | --- |
| `src/cells` | 476 Python files, 122,141 lines |
| `core/` | 167 files, 42,215 lines |
| `models/` | 150 files, 41,563 lines |
| `processes/` | 79 files, 24,408 lines |
| Model modules named `surface_*` | 116 (60 contain `calcium`) |
| Spec modules (`core/*_spec.py`) | 107 |
| Combination suffixes | `_epoch` 22, `_interventions` 17, `_preparation` 14, `_phase_handoff` 11, `_excision` 20, `_binding` 8, `_catalog` 6, `_events` 5 |

- **Example module:**
  `models/surface_calcium_energy_water_repair_profile_barrier_interventions.py` (471
  lines). It wraps three other model modules (`base`, `water_owner`, `membranes`) and a
  scheduling module, and has its own spec module.
- **The model protocol is a module, not a class.** Each model module supplies
  module-level functions:
  - set-up and stepping: `initial_values`, `rhs`, `readouts`;
  - domain checks: `domain_valid`, `control_domain_valid`;
  - numerical checks: `check_definition`, `check_steps`, `check_values`,
    `check_checkpoint`;
  - batching: `batch_signature`, `working_size`.

  State and layout types are NamedTuples built when the module loads.
- **Layering is by module alias.** For example `surface_pump_v3` imports
  `surface_pump as first` and `surface_pump_v2 as second`, and the stack runs
  `surface_tissue` → `surface_kinetic` → `surface_pump` → `_v2` → `_v3`. The W1 cost
  probe's stack trace went through five `initial_values` layers.
- **Dispatch is a chain of type checks.** `models/registry.py` is 773 lines. `get_model`
  (line 139) is an ordered chain of `isinstance` tests with lazy imports, so the order
  carries meaning.
- **Adding a model touches many places.** The composite had to edit `core/specs.py`,
  `models/registry.py`, `core/schedule.py`, `io.py` and `window_io.py`.
- **Caution: this is not dead code.** Many of these modules are probably qualified models
  kept frozen on purpose (BETSE comparison rungs and the qualified pump models).
  - Count model IDs by use before judging; the protein catalogue's census of 778 versioned
    identifiers is a starting point:
    `/mnt/workspaces/Cells/protein-catalogue-20261111-01/law_inventory_v2.json`.
  - Freezing qualified models is a deliberate choice, not a defect.

**The newer design: a composite with operators (D142, D143).**
- `models/operators/contract.py` defines an `Operator` base class:
  - **declarations:** owned state, heat and work fields, entity writes with their
    accumulators, view fields with a single provider, control factors, conflicts,
    requirements and ledgers;
  - **parts:** an event map, split half-steps, and an in-step process;
  - **idle defaults.**
- `models/pump_composite.py` builds one implementation per inner model and ordered list of
  operators, and caches it. The step is
  Φ = P₁(dt/2)…Pₘ(dt/2) ∘ I[view] ∘ Pₘ(dt/2)…P₁(dt/2) ∘ E.
  - An optimisation barrier wraps the inner step.
  - Idle parts are removed statically, and branches depend on structure, never on values.
  - The empty composition is the inner step itself, bitwise.
- **Guards, so far bitwise on CPU:**
  - the empty composition equals `@3`;
  - the water models and replacement, re-expressed as operators, equal the frozen models
    on their test and qualification worlds;
  - 130 of 130 of the frozen models' own tests pass against the thin modules.

## 2. No bound-definition object

Quantities that depend only on the definition are rebuilt through `initial_values(spec)`
at about ten call sites in the pump stack:
- `surface_tissue.py` 417, 523;
- `surface_kinetic.py` 674, 753;
- `surface_pump.py` 394, 625;
- `surface_pump_v2.py` 550, 562, 621;
- `surface_pump_v3.py` 837, 944.

Each rebuild includes the field set-up (`numerics/surface_field.bind`, a dense Cholesky
factorisation on the host).

**Symptom.** Plan validation checks the whole declared clock in chunks of up to 1,024
steps, and recomputed definition-only bounds for every chunk. For the 70-minute,
825-node hold that came to about 4,100 rebuilds, and the W1 cost probe never reached its
first window. The trace is in PROGRESS of 12 November.

**Fix in progress.** A fix on its own branch computes these bounds once per definition.
When it lands, check whether it introduces a real bind-once object, the general remedy,
or a local cache.

## 3. The operator contract: promising, not yet general

- **One inner model.** It wraps `@3` only, through one entity adapter. A second adapter is
  the real test of generality, and it should wait for an experiment that needs it (D144).
- **Size.** The base class has about 30 methods. Building it surfaced nine contract
  additions: RK4 modes, several parts per law, one in-step process, dependency refusals,
  state resets, view evaluation, observation overrides, idle zeros, and energy-field naming.
- **Weak points to settle before division stage S2:**
  1. Heat and work fields are recognised by name suffix (`_dissipated_energy_pJ`,
     `_work_pJ`), not by declaration alone.
  2. Observation columns can be overridden by operator order: water@2 overrides water@1's
     energy columns.
  3. Only one in-step process is allowed at a time. Check this against the division design
     (insertion, cleft and partition together).
- **Entities are field names today.** Stage S2 (membrane areas, capacitances and
  abundances as entity state) is where a typed entity schema should be decided. The
  protein catalogue's `functional_unit` and `catalogue` references attach there.

## 4. The GPU-native angle

**Measured on one NVIDIA L4** (see [MULTISCALE_EXECUTION_ARCHITECTURE.md](MULTISCALE_EXECUTION_ARCHITECTURE.md)):

| Measure | Value |
| --- | --- |
| Cost per world-step, 825-node tissue | 12.5 ms at 1 world; 2.64 ms at 64; 2.28 ms at 256 (execution only); 4.0–4.5 ms end to end with host observers |
| Accounted for in a 154 ms batch step at 64 worlds | 41.5 ms (the dense field factorisation); the rest is unprofiled |
| Compile | 482 s at 64 worlds |
| Repeat runs on one L4 | Not bitwise identical |

**How JAX is used in `src/cells`** (counts of matching lines):

| Construct | Lines |
| --- | --- |
| `jit` | 40 |
| `vmap` | 14 |
| `lax.scan` | 9 |
| `while_loop` | 8 |
| `fori_loop` | 8 |
| `device_put` | 40 |
| `block_until_ready` | 17 |
| Host callbacks (`pure_callback`, `io_callback`, `debug.callback`) | 0 |
| Sharding (`pmap`, `shard_map`, `jax.sharding`) | 0 |
| Rematerialisation | 0 |
| `xp=np` (host numpy) | 930 |
| `xp=jnp` (device JAX) | 656 |

Everything runs in float64. Many functions run on both backends through `xp=`: numpy on
the host for checks and set-up, and JAX on the device for stepping.

**Findings:**

1. **The GPU pays for ensembles.** One world costs 12.5 ms per step; batched it costs
   about 2.3 ms per world. The six-world full-tissue hold sits in the weak regime.
2. **Single-world scaling is limited by a dense solve every step.**
   - `numerics/surface_imex.factor_operator` (lines 101–115) runs a dense Cholesky on
     (C + aL) over the free nodes at every IMEX step. L changes with gated junction
     conductances.
   - The cost grows with the cube of the node count. That is fine at 825 nodes, but rules
     out a single organ-scale world without a sparse or iterative solver.
   - The capacitor solve is factorised once, at set-up (`numerics/surface_field.py` line
     200).
3. **Device checks cover one family.** `device_checks` is defined in 6 of 150 model
   modules:
   - `surface_pump`, `surface_pump_v2`, `surface_pump_v3`;
   - `surface_pump_water`, `surface_pump_water_v2`;
   - `cell_replacement`.

   Other families run through `core/batch.py` (`lax.map`) with checks on the host.
4. **Compile behaviour has no stated rule** for what is a traced input and what is a
   constant built into the program. Evidence:
   - 482 s at 64 worlds;
   - about 8 GB resident for one composite guard compile;
   - compiled programs accumulating past 3 GB across one test file;
   - XLA warned of slow constant folding (over 1 s per instance, for a 4,096-row
     reduction) in the static cleft-egg runs.
5. **Stalls are invisible.** Phase timings are written only when a run ends, so a run that
   stalls before its first window looks the same as a slow compile until it is
   interrupted.
6. **The composite is untested on GPU.** Its guards are bitwise on CPU, and L4 repeat runs
   are not bitwise.
7. **No code splits one world across devices.** Multiple GPUs are used only by spreading
   independent worlds over them (the ensemble plans).
8. **Float64:** the L4's float64 rate is low. Any claim comparing the L4 with GH200
   (JUPITER) on float64 throughput needs a measurement; none has been made.

## 5. Four overlapping execution paths

| Path | File | Lines | What it does |
| --- | --- | --- | --- |
| Single world | `core/runner.py` (with `core/windows.py`) | 500 (+260) | Eager, checked, discrete and windowed rollouts |
| Guarded batch | `core/batch.py` | 458 | Worlds mapped with `lax.map`; rows checked on the host |
| Batch windows | `core/batch_windows.py` | 384 | Windowed cohorts and snapshots |
| Vector windows | `core/vector_windows.py` | 776 | `vmap` over worlds inside `lax.scan`; device checks on every row; only per-window summaries leave the device |

Each path validates plans, checkpoints and observations in its own way.

**Recommendation:** name one production path. Vector windows is the natural candidate
where a model has device checks. Keep the others as declared reference paths.

## What was checked, and what is thin

**Verified by reading code:**
- the registry chain;
- the model-module protocol (one combination module read in full);
- the per-step dense Cholesky in the IMEX step;
- the `device_checks` coverage (grep over `models/`);
- the composite contract and step docstrings.

**Thin:**
- Layering depth rests on one stack trace.
- The registry was read in part.
- Model-ID use has not been counted.
- The L4 batch-step profile is one measurement.
- Float64 across devices is unmeasured.

## Questions for discussion

1. **Migration.** Re-express a legacy family as operators only when it needs a new
   feature? That is the advisor's recommendation. The composite took about one agent-day
   plus guards per family.
2. **README scope.** Should "GPU-native" state today's scope: batched independent worlds
   on one device?
3. **Scale.** What single-world size is needed in the next year? Thousands of cells in one
   interacting tissue or organ would put a sparse or iterative field solver, and splitting
   one world across devices, on the roadmap.
4. **Order of the cleanups** below, once the open branches have landed.

## Candidate follow-ups (not started; each separate and gated)

1. **Declarative model registry.** A table from model ID to its module or implementation
   object, replacing the ordered `isinstance` chain. Behaviour unchanged.
2. **Bound-definition object.** Definition-only quantities (factorisations, rate bounds,
   layouts) computed once and passed explicitly. Assess it after the plan-validation fix
   lands.
3. **One production execution path.** Name it; declare the others as reference paths;
   share plan and checkpoint validation.
4. **Live progress.** Phase markers written as each phase starts and ends (definition,
   plan validation, compile, first window), so stalls show early.
5. **Compile policy.** A written rule for traced inputs and built-in constants, plus a
   measure of compile time and memory for each new model.
6. **GPU measurement.**
   - Profile the whole batch step.
   - Measure how the field solve scales with node count, dense against a sparse or
     iterative solver.
   - Measure float64 throughput on GH200 before any JUPITER budget.
7. **Device checks for other families**, when each family is re-expressed.
8. **Operator contract hardening before S2.** Declared heat and work fields instead of
   suffixes; explicit observation ownership; a decision on several in-step processes; a
   typed entity schema.
