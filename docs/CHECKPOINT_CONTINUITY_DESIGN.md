# Checkpoint continuity (proposed design)

Status: **proposed, 13 November 2026.** The lead and the advisor review it before any code
exists. The user approved the tooling on 13 November: "yes fix checkpoint continuty also"
(PROGRESS). The public validation package is not approved, and this note does not touch
it. The draft decision is D150 (Appendix A). Evidence:
`/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/`.

**Engine models run:** none; this is tooling. The first consumer names its models (§10).

## 1. Summary

- **Refusal stays the default.** `io.load_snapshot` and `batch_io.load_batch_snapshot`,
  called as today, keep every refusal.
- **One explicit, recorded step per resume.** A resume across a change of source or
  runtime needs a **continuity record**, `cells.checkpoint_continuity@1`.
  - The record is written into the new run's folder. It names both sources and both
    runtimes, the evidence, and who admitted the resume.
  - The two loaders accept it through one optional argument. It relaxes only the
    identity comparison it covers.
- **Four cases, kept apart:**

  | Case | Rule | Test |
  | --- | --- | --- |
  | 1. Source changed; programs, bindings and host checks unchanged | Admitted | The continuity probe (§4), on CPU, at trace level, on the checkpoint's own definitions |
  | 2. Programs or bindings changed; physical fields unchanged | Only with a D148 record covering these definitions; the lead admits; never automatic | The probe's chain to the D148 revisions, and D148's guard on these definitions |
  | 3. Definition, layout, solver or model ID changed | Refused, as today | The loaders' existing checks, which no record relaxes |
  | 4. Runtime changed | Its own rule, field by field | Host-side fields: the probe under both runtimes. Compiler and device fields: tolerance, by the backend-variant method with at least three repeats |

- **Unchanged:**
  - registered runs: the W1 hold on its frozen `source-09`, E07-v1 on its one snapshot,
    and judges on clean snapshots;
  - D146 (no aliases) and D147 (a solver switch is a new definition; no migration).
- **The first consumer** is a CPU development run.

## 2. What refuses today, checked against the code (main `f76876d`)

### 2.1 The identity gate is the two loaders, and nothing else

| Site | What it compares | Message |
| --- | --- | --- |
| `io.py` 149–150 | `manifest["source_hashes"]` against `source_hashes()`: the SHA-256 of every `*.py` under the installed `cells` package (489 files) | "Checkpoint model/engine source differs from this installation" |
| `io.py` 152–153 | `manifest["runtime"]` against `runtime_identity(spec.execution.backend)` | "Checkpoint runtime differs; cross-runtime migration is not supported" |
| `io.py` 155–158 | spec fingerprint; state checksum | "...specification checksum mismatch", "...state checksum mismatch" |
| `io.py` 168–169 | state fields equal `STATE_TYPE` fields plus the fields of the definition's layout type | "Invalid checkpoint state fields" |
| `io.py` 175 | `validate_checkpoint` (below) | various |
| `batch_io.py` 113–117 | the same source and runtime comparisons for the cohort (runtime from world 0's backend) | "Batch checkpoint source differs...", "...runtime differs; no implicit migration" |
| `batch_io.py` 118–135 | spec checksum, inventory, identity and order, child paths. Each child goes through `load_snapshot`, so each child's own source and runtime comparison runs too. Then child spec and digest | various |

**`runtime_identity`** (`io.py` 37–60) records:
- `cells_version`;
- `python` (`platform.python_version()`);
- packages: jax, jaxlib, numpy, scipy, ml_dtypes and opt_einsum;
- `platform` and `machine`;
- `numerical_environment`: `XLA_FLAGS` and `JAX_DISABLE_JIT`;
- on GPU, `gpu.device_kind`, `gpu.platform`, `gpu.platform_version`, and every installed
  `nvidia-*` and `jax-cuda*` distribution.

**`runner.validate_checkpoint`** (51–108) checks:
- the clock: finite time, a step index on the grid, time equal to that grid point, and the
  event index;
- the state type: the model's `STATE_TYPE`;
- the layout type: `model.LAYOUT_TYPE` **or** the definition's own layout type,
  `type(initialise(spec).layout)`, which a declared field solver selects;
- the layout length;
- **layout values equal `initialise(spec).layout` under the current source** (93–97);
- state shapes and dtypes;
- `check_values`, then `check_checkpoint` where the model has it;
- at step 0, equality with the declared initial state.

**The execution paths never see identity.**
- Each takes bare `Checkpoint` objects and calls `validate_checkpoint`:
  - `core/runner.run` (317);
  - `core/windows` (96, 131);
  - `core/batch.run_batch` (312);
  - `core/batch_windows` (106);
  - `core/vector_windows` (202, 407);
  - `core/projective` (292).
- None compares source or runtime. **The loaders are the only identity gate**, so they are
  the one place for the rule (§6).

**Engine load sites, all through the loaders, all refusing any change today:**
- `__main__.py` 129 and 161 (batch resume and branch), and 222, 260 and 304 (scalar and
  windowed resume and branch);
- `tissue_phase.py` 156 (an INIT history carried into a new SIM phase);
- `excision_io.py` 142 and 156;
- `processes/stable_seed_partition_trajectory.py` 389;
- `analysis/cli.py` 90 and 105;
- `ensemble/ionic.py` 369, which also compares the device kind itself (364–367).

**Lineage.** `window_io.write_windowed_run` (80) and `batch_window_io.write_windowed_batch`
(41) re-publish the starting checkpoint as `checkpoint_initial` with the *current* identity.
A state resumed from another source would be stamped as native to the new one; §6 keeps the
lineage in the run's provenance instead.

**Out of scope; these keep refusing.** Other checkpoint systems, each with its own identity
rule:
- the stochastic assembly family:
  - `assembly/io.py` 98–109 hashes its own package and `core/output_paths.py` only;
  - `assembly_cell/io.py` hashes all of `src/cells`;
  - `assembly_pool/io.py`;
- the held charged-surface backend (`processes/charged_surface_backend.py`):
  - its identity is a release-manifest digest;
  - its snapshot is an in-memory record (690–716);
  - its `runtime_identity` (156) is its own;
- `validation/betse/physiology/physiology_checkpoint.py`: its `expected_source_hashes`
  *pins* an earlier installation, which is stricter, not looser.

**Driver checks stay.** `heredity_pilot.py` 2252–2254 refuses a resume snapshot whose cohort
fingerprint differs from the driver's rebuilt definitions.

### 2.2 Corrections to the audit

1. **Which source changes refuse.** `source_hashes()` covers `src/cells` only.
   - Docs, tests, validation drivers and scripts never trigger the refusal.
   - Host-only engine code does: `core/phases.py`, the `changes` properties of the
     experiment specs, `analysis/`, and every model module, used or not.
2. **The paths.** Besides runner, batch, batch_windows and vector_windows, `core/windows`
   (scalar windows) and `core/projective` also take checkpoints.
   - Projective is opt-in and failed its qualification.
   - This design refuses continuity for projective definitions.
3. **`validate_checkpoint`'s layout rule.** It accepts `model.LAYOUT_TYPE` or the
   definition's own layout type, not only "the declared model's". Its layout-value equality
   under the current source is the existing guard for case 3.
4. **Batch children carry their own manifests**, with the cohort's identity, and are loaded
   through `load_snapshot`. A relaxation must reach the children (§6).
5. **`cells_version` is a source property** (`cells.__version__`). A change in it is always
   also a source change.
6. **The "about 20 bypasses".**
   - 32 non-test files under `validation/` and `scripts/` name `state.npz`. Most are
     read-only audits.
   - Of the six named:
     - `e07_v1_run.py` resumes from its own `checkpoint.npz`, and starts from sheet70 states
       through `heredity_turnover_literature`;
     - `composite_dump.py` and `inplace_fix_guard.py` read their own dumps, as comparisons;
     - `surface_fixtures.py` reads a fixture `trace.npz` under a digest check;
     - only `field_floor_held.py` and `heredity_turnover_literature.py` read a snapshot's
       `state.npz` directly.
   - Missing from the list:
     - `scripts/profile_dispatch.py`, which rebuilds checkpoints from `world-<i>/state.npz`
       and the manifest clock. The window-timing note relied on this to avoid the runtime
       refusal.
     - `open_calcium_bath_trajectory_production.py`, an INIT-to-SIM handoff from its own
       `last-state.npz`.
   - §7 classifies them all.
7. **The crossrev guard cannot see some constant values** (probes 2 and 4, §4.3).
   - jaxpr text omits the values of closed-over arrays.
   - `composite_crossrev._traced` closes over `device_check_constants`. In the probe's
     worlds that is a scalar (0.002) and a 4-element array (1e-10 each).
     - The scalar appears in the text as a literal.
     - The array is closed over as three constants: two of shape (4, 1) and one of shape
       (4,), whose bytes equal the array's by digest. Their values appear nowhere in the
       text.
   - Crossrev's bindings omit the check constants. A change in the array's values would
     therefore pass crossrev as identical.
   - This bears on D148's fourth criterion. It is an open question (§12).
8. **The resume check in `heredity_pilot.py`** is at 2252–2254.

## 3. The four cases

### 3.0 Order of checks when a record is given

1. **Manifest integrity, unchanged:** field set, checksum, schema, kind and random state.
2. **The record's binding** (§5): the record's kind and digest, and its checkpoint manifest
   digest. Its `from` identity must equal the manifest's identity, and its `to` identity
   the running installation's.
3. **Definition checks (case 3), unchanged:**
   - `parse_spec` under the running source;
   - the fingerprint and the state checksum;
   - the state field set;
   - `validate_checkpoint`, including the layout type and layout values under the running
     source.
4. **No record relaxes step 1 or step 3.** A record replaces only the two identity
   comparisons, and only by the fields it names.

### 3.1 Case 1: the source changed, the programs did not

**Test: the continuity probe (§4).**
- It runs on CPU in two processes:
  - S0, the checkpoint's source tree, shown to reproduce the manifest's `source_hashes`
    exactly;
  - S1, the resuming execution snapshot.
- Its inputs are the checkpoint's own definitions and clocks, and the resuming path and
  window policy.
- The case is admitted if and only if all three parts are identical:
  - **P, programs:**
    - for every probed path, the jaxpr text of the program the path compiles, at the plan's
      own shapes;
    - the dtype, shape and bytes of every constant that jaxpr closes over, at any depth;
    - the path's own lowered StableHLO (`as_text()`). It is deterministic, carries no
      source locations, and carries the constants;
    - the arguments the path passes to `.compile()`. jaxpr text of the bare function
      cannot see a change to the `jax.jit(...)` wrapper or to the compile options;
    - crossrev's step-level texts: checked step or right-hand side, and device checks.
    - The first round's arguments are captured from the path's own entry point, which is
      stopped at `.compile()`.
  - **B, bindings:** every array the path binds, over the whole remaining horizon:
    - the resident inputs: start states, `parameters()`, active masks and check constants;
    - each round's arrays, from the path's own round builder;
    - per definition: the remaining grid, the integration steps, the controls, the
      observation times, and the initial state and layout.
  - **H, host acceptance and observation:**
    - `check_values` (with its step counts), `observe_history` and the windowed
      observation-continuity check are replayed under both sources;
    - they run on every state the S0 run saved up to the checkpoint (its snapshots,
      including this one), and on its saved observation rows where it recorded full
      histories;
    - the outputs must be identical.
- No model program is compiled or executed. Vector windows' small gather of the resident
  inputs does compile.
- **The probe's own runtime.** B and H speak for the resuming run only if the probe ran under
  the resuming runtime's host-side fields: python, numpy, scipy, ml_dtypes, opt_einsum, jax,
  platform and machine.
  - The record keeps the probe's runtime, and the loader checks those fields against `to`.
  - Otherwise the probe is rerun under the resuming runtime (§3.4, host class).

**Scope of the first landing.**
- **CPU definitions only** (`execution.backend: "cpu"`), with `jit: true`.
- **GPU definitions are not yet admitted.** For them, the probe would trace on CPU with
  `execution_device` patched to the CPU device, and cross-lower the captured program for
  `cuda` (probe 2). Device placement enters neither the jaxpr nor the bindings. This is not
  probed.
- **`jit: false` definitions are refused.** They execute eagerly, so there is no compiled
  program to compare.
- **No call site passes a record yet**, neither the CLI nor any other engine call site.
  Only development drivers do, through the API.

**What it decides.**
- Identical programs (jaxpr text, constants, lowered StableHLO and compile arguments) and
  identical bound inputs, under an identical runtime, give an identical compiled program on
  identical inputs.
- On CPU, the resumed run therefore equals S0's own continuation bitwise. CPU execution is
  deterministic, and complete restart is an engine property the tier tests already check.
- On a GPU it is the same program, so the resumed run varies only as S0's continuation
  would.
- Host acceptance and observation are decided on this run's own saved states.

**What it leaves, stated in every record.**
- Host code paths that no saved state reaches, and the driving loop after its first round
  (§4.2), are S1's.
- The consolidated execution path closes the second gap by exposing its rounds as a
  host-only generator that its executor consumes (§6).

**No narrowing.**
- Every file under `src/cells` still counts.
- The record lists the changed files only so that a reviewer can read them. The probe, not
  an argument about which files "feed no rate", decides whether a change reaches the run.
- **The canonical examples:**
  - the phase markers (host-only). Crossrev found the landing round that added them, with
    S3's engine side, identical to the ledger-fix revisions: 36/36, 78/78 and 6/6;
  - the `changes` cache;
  - docstring and comment edits inside traced model code (probe 3b);
  - unrelated models landing.

### 3.2 Case 2: the programs or bindings changed, the physical fields did not (D148)

Admissible only when all of the following hold. **Never automatic.**

1. **A D148 decision exists** for a change C, with before and after execution snapshots
   B and A. Example: D148's first case, `surface_tissue.capacitor_change`.
2. **The probe chains S0 to B and S1 to A.** P and B under S0 equal P and B under B, and
   under S1 they equal those under A, for these definitions and paths. So the only program
   or binding difference between S0 and S1 is C's. This needs four probe processes.
3. **C's D148 guard covered these definitions in the resuming program:** physical fields
   bitwise, and ledger accumulators changed only at rounding level, with every case listed.
   - If the D148 evidence does not include these definitions, the lead runs
     `inplace_fix_guard.py`'s `dump` and `compare` on them under B and A.
   - That run is evidence in the continuity record. It amends no decision.
4. **H is identical** under S0 and S1. A change in host acceptance or observation is never
   admitted, because it would split the run's records at the seam.
5. **The lead admits it**, naming the decision.
   - The record states which ledger accumulators continue across the seam under two
     programs.
   - Their residual diagnostics then mix both programs.

**The chain uses fresh probe outputs.** It compares outputs produced under B and A at
admission time, with P, B and H as in case 1. It does not rely on the stored crossrev
baselines, which hold step-level jaxpr text only and miss closed-over constants (§2.2,
item 7).

### 3.3 Case 3: a definition, layout, solver or model ID changed: refused

No new mechanism is needed. The checks of §3.0 step 3 already refuse:
- **A renamed or removed model ID** fails `parse_spec`. This is D146: "old configs and
  checkpoints are refused".
- **A changed canonical definition** fails the fingerprint check. A schema change that
  alters the canonical form of existing definitions therefore makes their checkpoints
  unresumable, by design.
- **A solver-version switch** is a new definition. `validate_checkpoint` refuses its layout
  (D147: "There is no migration").
- **Changed layout values under S1** fail the layout-value equality.

The record cannot relax any of these, so this design contradicts neither decision.

**Changed semantics behind an unchanged fingerprint** surface as a P or B difference, and
fall to case 2 or are refused.

**The engine's explicit definition changes are unchanged:** excision artifacts
(`excision_io.py`) and phase handoffs (`tissue_phase.py`). They load through the loaders and
keep their own records.

### 3.4 Case 4: the runtime changed

**Rules.**
- The loader requires the record to name exactly the set of runtime fields that differ
  between the manifest and the running installation.
- Each named field carries its class and the test that covered it.
- None is waived by argument.
- **When a host-class test fails:**
  - a P difference treats the change as compiler class, decided by tolerance;
  - a B or H difference refuses. The program would bind different inputs, or record
    different host results, so it is not the same run.

| Field | Class | Test |
| --- | --- | --- |
| `cells_version` | source | Covered by the source admission (cases 1–2) |
| `python`, `packages.numpy`, `scipy`, `ml_dtypes`, `opt_einsum`, `platform` | host | P, B and H under both runtimes (same source), identical. Trace level, CPU |
| `packages.jax` | host (lowering) | As above. P is jax's own lowering input |
| `packages.jaxlib`, `numerical_environment.XLA_FLAGS`, `gpu.packages`, `gpu.platform_version` | compiler | Tolerance (below). First, at trace level: the lowered module for the target platform, identical under both runtimes (cross-lowering for `cuda` works on the CPU host, probe 2) |
| `numerical_environment.JAX_DISABLE_JIT` | execution mode | Refused |
| `machine`, `gpu.device_kind`, `gpu.platform` | device | Host part first: B and H recomputed on the new machine's CPU, identical. Then tolerance |

**Why compiler fields go to tolerance.**
- The executable toy (Appendix B) shows that executable bytes are no usable identity. A
  serialized CPU executable differed between two compiles of one function in one process.
  The optimized HLO carries source file metadata and changes when a line moves.
- So no decided bitwise test exists for a compiler change. A CPU compiler change is
  measured on CPU, where repeats are bitwise and the run-to-run term is zero.

**Tolerance, extending `composite_l4_agreement.py`'s method.**
- **Runs.** From the checkpoint, over a declared horizon:
  - the CPU reference continuation C;
  - n ≥ 3 repeats T₁…Tₙ on the target runtime;
  - for a same-device change, n ≥ 3 repeats O₁…Oₙ on the original runtime.
- **Terms**, for each judged quantity with the protocol's own difference measure d:
  - backend term: max over i of d(C, Tᵢ). For a same-device change, it is the larger of
    that and the cross term, max over i, j of d(Oᵢ, Tⱼ);
  - run-to-run term: max over **all pairs** i < j of d(Tᵢ, Tⱼ), not one pair, because a
    third L4 repeat exceeded one pair's difference by up to 6× on 13 November. For a
    same-device change, it is the larger of that and the same term over the Oᵢ.
- **Tolerance.** The method's rule applies:
  max(registered, up1(3 × (registered/3 + backend + run-to-run))).
- **Stop rule, the method's.** Stop and diagnose, without registering, if a backend term
  (cross term included) or a run-to-run term exceeds the registered sum, or a fixed
  tolerance.
- **Development runs.** A development run without a protocol declares its tolerance before
  measuring.
- **Registration.** The variant is written as PROPOSED and registered by the lead before
  the continued run. The record cites it.
- **The tools.** `composite_l4_agreement terms` takes one pair (`--runs A B`); it needs an
  n-run form. `up1` is restated, not imported from `validation/betse/`, as that tool already
  does.

**Source and runtime changed together.** The source is decided first, on CPU, under one
runtime. The runtime is then decided for S1.

## 4. The continuity probe: crossrev, extended

### 4.1 Can the crossrev tools decide case 1? Not as written

`validation/tissue/composite_crossrev.py` shows the method, but:
1. **Its world sets are hard-coded** (base, qualification, injection), built from
   fixtures. It never reads a snapshot's definitions or clocks, and traces at t = 0.
2. **It needs `checked_step`, `rhs`, `device_checks` and `device_check_constants`.** RK4
   models with `rhs` and `domain_valid` only, and models without device checks, are
   outside it.
3. **It traces step functions, not what the paths compile.**
   - It misses the scan, cond and window wrappers in `core/`, the vmapped cohort window and
     the `lax.map` batch.
   - A change confined to a path's rollout is invisible to it.
4. **Its jaxpr text does not carry constant values, and it does not digest them** (§2.2,
   item 7).
5. **Its bindings are initial state, layout and controls at change times.** They omit:
   - `parameters(spec, layout)`;
   - the check constants;
   - the integration steps and the remaining grid;
   - the per-round arrays: held control tables, slot, index and origin rows;
   - the checkpoint's clock.

**It extends to arbitrary definitions, batch snapshots included,** and probes 1 and 4 did
so (probe 4 through all five paths' own entry points):
- read the definitions and clocks from the snapshot;
- build each path's arguments with the path's own planner and builders;
- trace the path programs and digest the constants;
- add the missing bindings.

### 4.2 The probe

**Where it runs.**
- The probe lives in `validation/continuity/probe.py` in the checkout.
- It runs out of process once per source, with `PYTHONPATH=<tree>/src:<checkout>`, as
  crossrev runs from each revision's snapshot.

**It uses only APIs that S0 already has.** The first real checkpoint predates this work.
- **Declared entry points:**
  - the planners (`plan_windows`, `plan_batch_windows`, `plan_vector_windows`);
  - the builders (`_Round`, `resident_inputs`, `_initial_checkpoints`, `held_controls`,
    and `run_batch`'s and `_run_segment`'s argument assembly);
  - the rollout functions (`_rollout`, `_checked_rollout`, `_discrete_rollout`,
    `_window_rollout`, `_batch_rollout`, `_vector_window`);
  - `timeline`, `integration_steps`, `control_values`, `initialise` and
    `validate_checkpoint`;
  - the model protocol.
- **If a tree lacks one, the probe reports `cannot_decide`, and the resume is refused.**

**Per source process:**
1. **Read without identity.**
   - Everything `load_snapshot` and `load_batch_snapshot` check, except the two identity
     comparisons. These include the manifest and child digests, the fingerprints, the state
     checksum and `validate_checkpoint` under this tree.
   - The process also records this tree's `source_hashes()`. Under S0 it must equal the
     manifest's map, so the record shows that the traced tree is the one that wrote the
     checkpoint.
2. **P0, the entry capture.**
   - The probe calls the path's own entry point: `run`, `iter_windows`, `run_batch`,
     `iter_batch_windows` or `iter_vector_windows`.
   - It replaces the jitted rollout object with a recorder, **under the name the path looks
     it up by**. `batch_windows`, for example, imports `_compiled_batch` by name, so the
     probe patches it there.
   - At `.lower()` the recorder keeps the arguments, the static functions, the jaxpr with
     its constants, and the StableHLO. At `.compile()` it keeps the compile arguments and
     stops.
   - No model program compiles or executes.
3. **P.** The captured program (jaxpr, constants, StableHLO and compile arguments) and
   crossrev's step-level texts per distinct definition.
4. **B.**
   - The captured arguments must equal the first round that the probe's builders produce.
     This shows the tool drives the builders as the path does.
   - The builders are then iterated to the end of the horizon, digesting every array.
   - For the runner path, the remaining-horizon steps and controls are digested in chunks.
5. **H.** Replay on the saved states (§3.1).
6. **Outputs:** the texts, a `summary.json` of digests, timings and peak memory.

**`admit.py`.**
- It runs the probe under S0 and S1, and under B and A for case 2, as detached units.
- It compares the outputs and writes a *proposed* record.
- `admit.py --admitted-by NAME` finalises it, after review.

**`verify_run.py`** checks the resumed run afterwards:
- its manifest's `provenance` names the record;
- its kind and policy are the scope declared at load (§6);
- its window schedule (`windows.jsonl`) matches the rounds the probe iterated.

**The probe reads `state.npz` outside the loaders by design.** It is listed as exempt in
the bypass guard (§7).

**Cost.**
- **Measured** (probe 1: two `resolved_pump_replacement@1` worlds of the seven-cell sheet,
  step 0, CPU 4):
  - 25–37 s per source process, about 0.3–0.4 GB at peak;
  - per path program, 0.5–0.75 MB of jaxpr text and 1.3–1.8 MB of StableHLO.
- **Estimated, not measured:**
  - **Large tissues.** All three crossrev sets, traced at step level only and including the
    825-node worlds, took about 2 minutes at 0.67 GB. Path programs of 825-node worlds
    should therefore take minutes.
  - **Long horizons.** A run of 6,000 rounds adds one host round-builder call per round.
    The probe's three rounds were too short to time.
- Both must be measured on the first large checkpoint against AGENTS.md's 30-minute rule.

### 4.3 This note's probes (trace only, CPU 4, through `run_detached.sh`)

No unit's journal reports an out-of-memory kill (Appendix B).

| Probe | Question | Result |
| --- | --- | --- |
| 1 | Can a batch snapshot's own definitions be traced at cohort level, deterministically? | Yes. Vector window (vmapped, width 8, three rounds), `lax.map` batch, runner and scalar window programs, and per-world step-level texts. Two processes: 12 of 12 texts and 5 of 5 binding sets identical |
| 2 | Does jaxpr text carry constant values? | No. Two functions closing over different 5- and 1,000-element arrays print **identical jaxpr text**; their constants and their StableHLO differ. In the real worlds, the path programs close over no constants (the check constants are arguments), but crossrev-style device-check texts close over three |
| 2 | Other toy questions | No object addresses in jaxpr text (custom_jvp included). StableHLO `as_text()` has no locations. Cross-lowering for `cuda` and `rocm` works on this CPU host. Serialized CPU executables are not a stable identity (§3.4) |
| 3a | Host-only edits (a phase helper, a host attribute on `_Round`) against a program edit (an optimization barrier on `dt` in `pump_composite.checked_step`), on scratch copies | Host edits: `source_hashes()` differs (today's loader refuses), but programs, constants and bindings are **identical**, so case 1 admits. Program edit: every path program's jaxpr and StableHLO differ, with bindings identical, so case 1 refuses |
| 3b | Comment and docstring edits inside traced model code (`checked_step` in `pump_composite.py`, `capacitor_change` in `surface_tissue.py`), which move lines | `source_hashes()` differs, but texts (12/12), constants and bindings (5/5) are **identical**, so case 1 admits. Neither jaxpr text nor StableHLO carries source positions |
| 4 | P0, the entry capture: does driving each path's own entry point, with its jitted rollout replaced by a recorder where the path looks it up, capture the program it compiles? | Yes, on all five paths: `iter_vector_windows`, `iter_batch_windows` (its `_compiled_batch`, imported by name), `run_batch`, `run` and `iter_windows`. 19–25 s per process, 0.43 GB. The captured StableHLO equals the path's direct `.lower()`. Compile arguments are empty. The vector capture **equals the first round rebuilt from the builders**. Repeated, host-edit and program-edit trees as in probe 3a: the program edit changes all five captured programs, with arguments equal |
| 4 | H, host replay on saved states (here the snapshot's step-0 states): does it catch an observer-only change that P and B miss? | Yes. A one-ulp change to every floating observation column except `times`, in the composite's `observe_history`, leaves programs and bindings identical, and changes `observe_history` in both worlds (`check_values` and `summarize` unchanged). Case 1 refuses. A first form, which scaled the first float column, scaled `times` (0 at step 0) and changed nothing. It is kept as evidence of a probe flaw, not of H |

Details are in Appendix B.

## 5. The record

```json
{
  "kind": "cells.checkpoint_continuity@1",
  "checkpoint": {
    "format": "cells_independent_world_checkpoint",
    "path": "/mnt/workspaces/Cells/<run>/snapshots/t00120.000",
    "manifest_sha256": "<the snapshot manifest's own manifest_sha256>",
    "definitions": {"1": "<spec_sha256>", "2": "<spec_sha256>"},
    "clocks": {"1": {"time": 120.0, "step_index": 120000, "event_index": 3}}
  },
  "from": {
    "source_hashes_sha256": "<digest of the manifest's source_hashes map>",
    "tree": "/mnt/workspaces/Cells/<run>/source-07",
    "git_revision": "<from the checkpoint run's inputs>",
    "dirty_diff": "/mnt/workspaces/Cells/<run>/source-07/checkout.patch",
    "tree_reproduces_manifest": true,
    "runtime": {"...": "the manifest's runtime, verbatim"}
  },
  "to": {
    "source_hashes_sha256": "<digest of the resuming tree's source_hashes()>",
    "tree": "/mnt/workspaces/Cells/<new run>/source-01",
    "git_revision": "<from validation/source_snapshot.py>",
    "dirty_diff": "/mnt/workspaces/Cells/<new run>/source-01/checkout.patch",
    "runtime": {"...": "runtime_identity(backend) of the resuming installation"}
  },
  "changed_files": ["core/phases.py", "core/vector_windows.py"],
  "probe": {
    "runtime": {"...": "runtime_identity('cpu') of the probe processes"},
    "host_fields_equal_to_runtime": true
  },
  "source_admission": {"case": "identical_programs"},
  "runtime_admission": {"case": "none", "fields": []},
  "scope": {
    "paths": ["vector_windows", "batch_windows", "lax_map_batch"],
    "policy": {"window_steps": 1000, "recording": "checkpoints"},
    "horizon_rounds": 6000
  },
  "evidence": [
    {"role": "probe S0", "path": ".../continuity/probe-s0/summary.json", "sha256": "..."},
    {"role": "probe S1", "path": ".../continuity/probe-s1/summary.json", "sha256": "..."},
    {"role": "comparison", "path": ".../continuity/compare.json", "sha256": "..."}
  ],
  "residual": [
    "host checks and observers compared on 41 saved states; unreached host paths are S1's",
    "the driving loop after its first round is S1's (section 4.2)"
  ],
  "admitted_by": {"name": "<who>", "role": "lead"},
  "admitted_utc": "<UTC time>",
  "record_sha256": "<cells.core.specs.digest of the record without this field>"
}
```

**Case 2** sets `source_admission`:

```json
{
  "case": "d148",
  "decision": "D148",
  "before": "<B tree>",
  "after": "<A tree>",
  "guard": "<inplace_fix_guard compare file>",
  "ledger_fields_across_seam": ["electrode_charge_transferred_C"]
}
```

**Case 4** lists each differing field, with its class, `from`, `to`, test and evidence, and
for tolerance the registered variant protocol.

**Rules.**
- **Location.** The record lives in the **new** run's folder, never in the snapshot's
  directory, which stays immutable. The new run's inputs name it.
- **Hashes are data.** They live in records and manifests and are computed with the
  existing canonical `digest`. Code holds no literals.
- **One record, one admission.** A record binds exactly one checkpoint manifest, one `from`
  identity and one `to` identity. Another source or runtime needs another record.

## 6. Where the check lives

**Engine (`src/cells`), host-only. No path changes.**
- **`cells/continuity.py` (new).**
  - It parses and verifies the record: kind, digest, required fields per case, and a
    non-empty `admitted_by`.
  - `Admission.require(manifest_fingerprint, manifest_sources, manifest_runtime,
    current_sources, current_runtime)` raises unless the record binds exactly these.
  - `provenance(admission)` returns
    `{"operation": "admitted_resume", "continuity_record": ..., "record_sha256": ...}`.
  - It imports neither JAX nor subprocess, and traces nothing.
- **`io.load_snapshot(directory, *, continuity=None)`.**
  - With `None`, the code path is today's.
  - Otherwise `continuity` is a `continuity.Request(record, path=..., policy=...)`. The
    caller declares the path and window policy it will resume with.
  - The two identity comparisons become `admission.require(...)`. Every other check runs as
    before.
  - The loader refuses if:
    - the record's scope does not cover the declared path and policy;
    - the probe's host-side runtime fields differ from the `to` runtime (§3.1);
    - the definition is a GPU, `jit: false` or projective one (§3.1, first landing).
  - The returned `Snapshot` gains an `admission` field, defaulting to `None`. The manifest
    schema stays 1, because its field set is exact.
- **`batch_io.load_batch_snapshot(directory, *, continuity=None)`.**
  - The record binds the cohort manifest.
  - Each child is loaded against the cohort manifest's recorded identity rather than the
    running installation's. The cohort writer guarantees that they are one identity.
  - The other child checks are unchanged.
- **Writers are unchanged.** They already take `provenance`, and the driver passes
  `provenance(admission)`.
  - `checkpoint_initial` in windowed outputs is re-stamped with S1's identity, as today.
  - The lineage is the run manifest's `provenance` plus the record that the run inputs
    name.
  - A static test (§10) fails a driver that passes `continuity=` without passing the
    provenance.

**Validation (`validation/continuity/`).** `probe.py`, `admit.py` and `verify_run.py`, with
their tests.

**The paths are unchanged.**
- **The checks.** Path and policy are declared at load and refused there if the record does
  not cover them. `verify_run.py` cross-checks the run's manifest afterwards.
- **What remains.** A driver could declare one scope and then call another path. Closing
  that would take four new checks inside the paths, which the consolidation is about to
  replace.
- **The one production path (execution gate) takes this over:**
  - its shared admission checks the declared scope at plan time;
  - it exposes its rounds as a host-only generator that its executor consumes, which
    closes the driving-loop residual of §3.1.

## 7. The bypasses

**One rule.** Every engine execution that starts from saved state does one of two things:
- **(a) Load** through `load_snapshot` or `load_batch_snapshot`. It is refused by default,
  or admitted by a record.
- **(b) Declare itself a start from saved state.** This is a new run of a definition whose
  initial values are imported.
  - The run's inputs record the source snapshot's manifest digest and identity.
  - It claims no continuity with the source run and is judged as its own run.

Reading saved bytes without executing from them is not a migration.

| Class | Tools | Disposition |
| --- | --- | --- |
| Read-only comparison or audit, or a writer of its own output (no execution from the state) | 22 of the 32: `jupiter_check`, `tile_benchmark`, `parallel_cluster`, `profile_cluster`, `spatial_matrix`, `compare_throughput`, `open_calcium_trajectory_compare`, `verify_windows_build` (which uses `load_snapshot`), the two spatial-extracellular audits in `scripts/`, the eleven BETSE-side audits (`*_audit_cells`, `*_context`, `timed_cells_check`, `family_audit`, `matched_windows`, `cells_review`, `diagnose`, `preparation_review`), and `open_calcium_trajectory_production` (writes its own `full-state.npz`) | Exempt: nothing continues |
| Own paired formats with identity checks | the five `validation/betse/physiology/*` IO modules (numeric part through `load_snapshot` and `write_snapshot`) | Exempt: already under the loaders' rule |
| Rebuild and execute outside the loaders | `scripts/profile_dispatch.py` (L4 timing on held states under other XLA flags); `field_floor_held.py` (`--state`, run **under version 3**: a deliberate case-3 diagnostic of version-2 states) | Exempt as diagnostics: no output is a continuation of the run. Each records the snapshot digest and both identities in its output (rule (b)), and the guard test lists them with this reason |
| Import into a new definition | `heredity_turnover_literature.start_state` (sheet70 states into `resolved_pump_replacement@1`), used by E07-v1; its `importcheck` is the empirical import check; `static_cleft_egg_steps.start_state` (R-full's recorded J1 state, a reference record) | Rule (b). The turnover pre-screen and E07-v1 are exempt while their runs last (E07-v1 is running now). New imports record the source digest and identity |
| Driver-owned resume, with no identity | `e07_v1_run.py` and `heredity_turnover_literature.py` (`checkpoint.npz` through the validation-side `Stepper`); `open_calcium_bath_trajectory_production.py` (`last-state.npz` handoff) | Exempt while their runs last, because each resumes inside one execution snapshot. New drivers write Cells snapshots, or record `source_hashes()` and `runtime_identity()` and refuse a resume under another unless given a record |
| Same-process restart and independent references | `betse/fresh_rerun/workers.py` (`restart.npz` written and read in one process); `open_calcium_bath_trajectory_oracle.py` (the independent oracle's own state) | Exempt: no source change can occur, or no Cells engine runs |

**The guard** is a static test modelled on `test_d147_drivers.py`. It fails for any module
under `validation/` or `scripts/` that:
- reads a snapshot's `state.npz`, or constructs `Checkpoint` from loaded arrays, outside
  the loaders, unless the module is listed above with its reason;
- passes `continuity=` and is not on the development allow-list.

`validation/continuity/probe.py` is itself on the exempt list. It reads checkpoints without
the identity comparison so that it can trace them under S0 and S1, keeps every other loader
check, and never continues a run.

The validation-side `Stepper` is a fifth execution path outside `src/cells`. That is noted
for the consolidation (§12).

## 8. The GH200 move

**What differs from the L4:**
- the device: GH200 against L4;
- the machine: aarch64 Grace against x86_64;
- very likely the Python, numpy and jax builds, the CUDA packages and the driver.

Every differing field is named in the record.

**Steps for continuing a run from an L4 checkpoint:**
1. **Source.** Cases 1–2 are decided on CPU, on any host, before any GPU time.
2. **Host side, on the GH200 node's CPU.**
   - P, B and H run under the GH200 runtime and are compared with S1 on x86_64.
   - A difference in B (inputs bound differently) or in H refuses the continuation. The
     run then starts fresh on GH200.
3. **Programs.** The lowered `cuda` module under each runtime is recorded. It can be
   cross-lowered on CPU (probe 2). A difference is expected if the jax versions differ, and
   it moves the decision to step 4; it is not admitted as identical.
4. **Device, by tolerance (§3.4).**
   - Runs: the CPU reference continuation from the checkpoint, at least three GH200
     continuations, and at least three L4 continuations from the same checkpoint for the
     L4's own envelope.
   - The terms are taken over all pairs.
   - The lead registers the variant before the continued run.

**Not moved.** Registered runs are not moved: the W1 hold stays on the L4 with
`source-09`, and E07-v1 stays on its snapshot. The first GH200 continuation is a
development run.

**Fresh runs.** Fresh GH200 runs need no record. Their agreement with CPU is the composition
gate's tolerance method.

**Day one.** Besides rerunning the L4 step-profile harness (D145), step 2 can run on day one
for any development checkpoint.

## 9. AGENTS.md, rule by rule

| Rule | How the design stays inside it |
| --- | --- |
| "Treat those snapshots as immutable" | This refers to execution snapshots. Numerical checkpoints are write-once too. Neither is modified: S0 is read in place on `PYTHONPATH`, and the checkpoint is read, never re-saved. Records and probe outputs go into the new run's folder |
| "make fixes in the checkout and generate a new snapshot for a later run" | An admitted resume *is* a later run, from a new execution snapshot S1 generated from the checkout. Nothing is patched into S0, and no implementation lives under `/mnt/workspaces` |
| "Reuse the existing snapshot and source-binding tools; preserve exact run-source identification" | S1 is frozen by `validation/source_snapshot.py`. S0 is bound to the checkpoint by the manifest's own `source_hashes` map, which the probe recomputes over the S0 tree. The record names both trees, both revisions and both diffs |
| "Run provenance is the Git revision, the dirty diff and the frozen snapshot" | A migrated resume has two sources plus a record. Exact wording proposed below |
| "Do not add per-call or bytecode attestation layers" | The probe runs once per admission, outside the run. The loader's default path is unchanged; with a record, it compares stored identity fields as it does today. Nothing hooks a call. No Python code object or bytecode is inspected. Traced device programs are compared, as the crossrev guard already does (D148, criterion 4) |
| "do not embed SHA-256 hashes of other source files as literals in new code" | None. Hashes live in records and manifests, as data |
| "integration alone grants no scientific acceptance" | The continuity code lands with its guards. An admitted resume serves development runs; judges and registered runs never pass a record (static test) |
| "A milestone that runs none is tooling and needs the user's explicit approval" | Approved on 13 November, verbatim in D150. The first consumer names its engine models |
| "If a check needs more than 30 minutes to reach the code under test, build a faster harness first" | The probe reaches the code under test in seconds to minutes (§4.2). Tolerance runs are separate, registered measurements |
| Running jobs (10 minutes or more detached) | Probes and tolerance repeats run through `scripts/run_detached.sh`, with caps from measured peaks |
| Reference simulators | The tolerance step restates `up1` instead of importing from `validation/betse/`, as `composite_l4_agreement.py` does |
| Lean workflow | One machine-readable record per resume, and one PROGRESS line per admitted resume. No new protocol documents |
| Refusal stays the default (brief) | With `continuity=None`, the loaders run today's code path, with every refusal message unchanged (guard 1). A migration is one explicit `Request` per resume, backed by a record naming both sources, the evidence and who admitted it |
| Registered runs are unchanged (brief) | No registered driver or judge passes a record (static test, guard 6). The W1 hold keeps `source-09`, E07-v1 its snapshot, and judges clean snapshots. The first consumer is a CPU development run |
| One admission rule for all four execution paths (brief) | The rule sits in the two loaders, which every path's checkpoints pass through. The probe traces each path's own program: runner, scalar windows, batch, batch_windows and vector_windows. The consolidated path inherits the loader rule and the declared scope check |

**Proposed wording, for the user to decide.** This design does not need it, but it makes the
two-source provenance explicit. In "Milestones and provenance", replace:

> Run provenance is the Git revision, the dirty diff and the frozen snapshot.

with:

> Run provenance is the Git revision, the dirty diff and the frozen snapshot. A run resumed
> from a checkpoint written under another source or runtime names both, and the continuity
> record that admitted the resume (docs/CHECKPOINT_CONTINUITY_DESIGN.md).

Optional, in "Source code and outputs", after "Treat those snapshots as immutable: make
fixes in the checkout and generate a new snapshot for a later run.":

> Numerical checkpoints are immutable as well: a checkpoint written under one source is
> resumed under another only through a continuity record, never by editing or re-saving it.

## 10. Guard plan for the implementation

1. **Every existing refusal still refuses by default.**
   - One test per refusal site in §2.1, called without a record: source, runtime, the spec
     and state checksums, the field set, and the cohort's inventory, order, child path,
     escape and child identity.
   - The existing tests of these messages stay green.
2. **No record relaxes case 3.** With a valid record, each of these is still refused:
   - a corrupted fingerprint or state;
   - a renamed model ID (the D146 pattern);
   - a version-3 definition with a version-2 checkpoint (the D147 pattern);
   - a changed layout value.
3. **Record binding.** Each of these is refused:
   - a wrong manifest digest;
   - a `from` identity different from the manifest's;
   - a `to` identity different from the installation's;
   - an unnamed or extra differing runtime field;
   - `JAX_DISABLE_JIT`;
   - a tampered `record_sha256`;
   - a missing `admitted_by`;
   - case 2 without its decision, before, after and guard fields;
   - a tolerance case without a registered variant;
   - a declared path or policy outside the record's scope;
   - a probe runtime whose host-side fields differ from `to`;
   - in the first landing, a GPU, `jit: false` or projective definition.
4. **Admitted cases, tested on small worlds, scalar and cohort, on scratch copies as in
   probe 3.**
   - A host-only edit and a comment edit are admitted. The resumed CPU run then equals the
     uninterrupted S0 run **bitwise**, on every path.
   - Each of these is refused, by the probe part named:
     - a program edit (P);
     - a constant-only edit (P constants; a test model closes over an array);
     - a binding-only edit, such as `control_values` arithmetic (B);
     - an observer-only edit (H);
     - a tree that lacks an entry point (`cannot_decide`).
5. **D148 for the implementation itself.** The loaders are shared qualified code, so the
   change must be host-only and shown to be:
   - crossrev base, qualification and injection identical before and after;
   - `inplace_fix_guard` dumps identical, ledgers included;
   - the crossrev baseline renewed at the landing commit;
   - the tier 1 + 2 gate at its baseline.
6. **Static tests.**
   - Bypasses (§7).
   - Registered drivers and judges never pass `continuity=`.
   - A driver that passes `continuity=` also passes `provenance(admission)`.
7. **The first consumer, end to end.**
   - A CPU development run resumes across a real host-only landing, with its record.
   - It is checked by `verify_run.py`, and compared bitwise with an uninterrupted S0
     continuation of the same checkpoint.

## 11. Effort (agent-days; CPU time extra)

| Part | Days |
| --- | --- |
| `continuity.py`, the loader argument for scalar and cohort, tests 1–3, D148 guard runs for the landing | 1.5 |
| `probe.py` (P0, P and B for runner, windows, batch, batch_windows and vector_windows; H), `admit.py`, `verify_run.py`, tests 4 | 3–4 |
| The bypass guard, exemption table, rule (b) records in four tools, a driver-checkpoint helper | 1 |
| The first consumer, end to end on CPU | 0.5–1 |
| **Case 1 usable on CPU** | **6–7.5** |
| Case 2 chain exercised on a real D148 case (when needed) | 1 |
| Runtime: host-side two-environment probe; n-run tolerance terms; GPU cross-lowering compare (at GH200 access) | 2 |
| **Total** | **9–10.5** |

## 12. Open questions for the lead

1. **Path and policy.** Is a scope declared at load (refused there if the record does not
   cover it, and cross-checked by `verify_run.py`) enough until the consolidated path
   checks it at plan time?
2. **The host-analysis residual.** Is replay on the run's saved states enough for
   development runs? Or must runs that want continuity record full histories?
3. **The driving-loop residual** (after round 1). Accept it until the consolidated path's
   host-only round generator closes it? Or build a dry run now? A dry run would replace the
   compiled executable with path-specific stand-in outputs, at about one more day, and
   would be fragile with events and ledger checks.
4. **Who admits.** Proposed:
   - case 1: the lead;
   - case 2: the lead, naming the decision, with the user informed;
   - runtime tolerance: a lead-registered variant.
5. **The crossrev constants gap** (§2.2, item 7). Should crossrev digest constants and bind
   `parameters()` and the check constants now, and renew the baseline? This affects what
   D148's fourth criterion has covered so far.
6. **Bypass exemptions.** Are the running tools exempt until their runs end: E07-v1, the
   turnover pre-screen, `profile_dispatch.py` and `field_floor_held.py`?
7. **Lineage.** Accept re-stamped `checkpoint_initial`, with the lineage carried in the run's
   provenance?
8. **GH200.** Does any run family need a GH200 continuation from L4 checkpoints, or do fresh
   GH200 runs suffice?
9. **Scope.** The assembly family, the held charged-surface backend and projective
   definitions stay out and keep refusing.
10. **The validation-side `Stepper`.** Should the consolidation bring it under the one
    production path?
11. **Not yet probed.** These need probing before the implementation relies on them:
    - **GPU definitions:** the `execution_device` patch, and `cuda` cross-lowering of
      captured path programs. Cross-lowering was shown on a toy only.
    - **Mid-run checkpoints.** Only step 0 was probed. A checkpoint with `start_step > 0`
      exercises the planners' start and the remaining grid.
    - **H on a real run's saved states:** periodic snapshots past step 0, and saved
      observation rows of runs recording full histories.
    - **B over a long horizon:** the cost of iterating the round builder over thousands of
      rounds.
    - **Capture against rebuilt first round on the other paths.** Probe 4 compared them for
      vector windows only. The other four paths were captured, but not compared with a
      rebuilt round.
    - **Large worlds:** the 825-node tissue's path programs (cost estimated in §4.2).
    - **Case 2's four-process chain**, on a real D148 change.
    - **The runtime rules:** the host-side two-environment comparison, and the n-run
      tolerance terms.
    - **`jit: false` definitions** (refused in the first landing).

## Appendix A: draft D150

> ## D150: Checkpoints resume across a source or runtime change only through a recorded admission
>
> 2026-11-13, user approval of the tooling, with the lead's design reviewed by the advisor
> (draft; it lands with the implementation,
> [CHECKPOINT_CONTINUITY_DESIGN.md](CHECKPOINT_CONTINUITY_DESIGN.md)).
> - **The approval.** The user's words were "yes fix checkpoint continuty also". This
>   approves the versioned checkpoint migration that D145 listed as unapproved tooling. The
>   public validation package stays unapproved.
> - **Refusal stays the default.** `load_snapshot` and `load_batch_snapshot` refuse any
>   change of source or runtime unless given a continuity record
>   (`cells.checkpoint_continuity@1`).
>   - A record binds one checkpoint manifest and one pair of identities.
>   - It names both sources and runtimes, the evidence and who admitted the resume.
>   - It lives in the new run's folder, and the run's provenance names it.
> - **Four cases:**
>   1. **Source changed, programs unchanged:** admitted when the continuity probe finds
>      three things identical:
>      - the programs each path compiles: jaxpr, constants, lowered StableHLO and compile
>        arguments;
>      - the bindings over the remaining horizon;
>      - host acceptance and observation on the run's saved states.
>
>      The probe runs on CPU, on the checkpoint's own definitions. No file is exempted by
>      argument. The first landing covers CPU definitions with `jit: true`.
>   2. **Programs or bindings changed, physical fields unchanged:** only with a D148 record
>      covering those definitions, admitted by the lead. Never automatic.
>   3. **Definition, layout, solver or model ID changed:** refused. No record relaxes these
>      checks. D146 and D147 stand: no aliases, no migration.
>   4. **Runtime changed:** every differing field is named and tested.
>      - Host-side fields: decided at trace level on CPU.
>      - Compiler and device fields, including a move from the L4 to GH200: decided by
>        tolerance with the backend-variant method, at least three repeats, and terms taken
>        over all pairs.
> - **Unchanged:** registered runs. The W1 hold stays on `source-09`, E07-v1 on its
>   snapshot, and judges on clean snapshots. The first consumer is a CPU development run.
> - **Bypasses.** Execution from saved state either loads through the loaders or declares
>   itself a new run started from imported state, recorded and judged on its own. A static
>   test lists the exempt tools with their reasons.
> - **Evidence:** `/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/`. The probes
>   show that:
>   - cohort programs traced from a batch snapshot, and captured from all five paths'
>     entry points, repeat identically;
>   - jaxpr text omits constant values, so constants and the lowered StableHLO are
>     compared;
>   - host-only and comment edits leave programs, bindings and host replay identical;
>   - a program edit changes every path's program;
>   - an observer-only edit changes only the host replay.

## Appendix B: probe evidence

All under `/mnt/workspaces/Cells/checkpoint-continuity-20261113-01/probe/` (`HANDOFF.md`
one level up):
- the scripts: `probe_trace.py` (probes 1–3) and `probe_entry.py` (probe 4);
- the runners: `run.sh`, `run_comment.sh`, `run_entry.sh` and `run_entry_observer2.sh`;
- the edits applied to scratch copies of `src/cells` at `f76876d` (the source is unchanged
  at the later branch commits): `host-edit.patch`, `program-edit.patch`,
  `comment-edit.patch`, `observer-edit.patch` and `observer-edit-2.patch`;
- the outputs: `out/`, summarised in `out/probe-summary.json`;
- the toy introspections: `introspect/`;
- the first attempt, which failed on a digest helper and is kept as `out-attempt1/`.

| Comparison | Texts | Programs (jaxpr, constants, StableHLO) | Bindings | Verdict |
| --- | --- | --- | --- | --- |
| Checkout, repeated in a second process | 12/12 identical | all identical | 5/5 identical | identical |
| Host-only edits (`core/phases.py`, `core/vector_windows.py`) | 12/12 identical | all identical | 5/5 identical | identical (today's loader refuses) |
| Program edit (`models/pump_composite.py`) | 10 of 12 differ | every path program's jaxpr and StableHLO differ; constants equal | 5/5 identical | differs |
| Comment and docstring edits in traced code (`models/pump_composite.py`, `models/surface_tissue.py`) | 12/12 identical | all identical | 5/5 identical | identical (today's loader refuses) |

**Probe 4** (`probe_entry.py`, `run_entry.sh`, `run_entry_observer2.sh`; P0 on five paths
and H, compared with `entry-checkout-1`):

| Tree | Captured programs (jaxpr, constants, StableHLO, arguments, compile arguments) | Host replay (`check_values`, `observe_history`, `summarize`) |
| --- | --- | --- |
| Checkout, second process | identical, 5 of 5 paths | identical |
| Host-only edits | identical | identical |
| Program edit | jaxpr and StableHLO differ on all 5 paths; arguments, constants and compile arguments equal | identical |
| Observer edit, first form (scaled `times`, 0 at step 0) | identical | identical: the edit changed nothing (a probe flaw) |
| Observer edit, second form (`observer-edit-2.patch`) | identical | `observe_history` differs in both worlds |

**Constants.**
- Path programs close over 0 constants.
- Crossrev-style device-check texts close over 3, with shapes (4, 1), (4, 1) and (4,). By
  digest, these are the bytes of `device_check_constants`' 4-element array (1e-10 each).
- Those values are absent from the text; its scalar (0.002) appears as a literal.

**Toy (JAX 0.11.1).**
- **Constants.** Different constants give identical jaxpr text, differing constants and
  differing StableHLO, both small (5) and large (1,000).
- **Other checks.**
  - jaxpr text holds no object addresses.
  - Cross-lowering for `cuda` and `rocm` works on CPU.
- **Executables.**
  - A serialized CPU executable compiled twice in one process gave different bytes.
  - Two fresh processes gave equal bytes.
  - The optimized HLO names the source file and changed when the defining line moved.

**Resources.**
- Units `cells-ccont-probe1`, `-probe2`, `-consts`, `-serial`, `-probe3`, `-probe4` and
  `-probe4b`, on CPU 4.
- Each unit's journal reports its memory peak: 0.07–0.35 GB where reported (`-consts`
  reported none).
- No unit's journal reports an out-of-memory kill. The units were collected on exit, so
  their `memory.events` files no longer exist; the statement rests on the journal.
