# Device row checks for scalar windows, and the vector path's seams (design, 16 November 2026)

**Status: ruled by the lead on 16 November 2026 (below).** The seams are built first, on branch
`windows-next-clean` (from c1 = integration-d172 3c10b833). Device checks wait for the
clean-core measurement. The measurement probe is `validation/execution/window_check_probe.py`.
Every timing below is development evidence, not a verdict.

**The two asks:**
1. Move the host-side row checks of the scalar windowed runner into device windows. The coupling
   operator's matched-arm export (D177) measured these checks at 91% of a long run's wall time.
2. Add the four core seams that the packed GPU planner asked for
   (`docs/PACKED_GPU_EXECUTION_DESIGN.md` on `packed-gpu-planner`, "Seams requested from the
   core"):
   - window arguments;
   - mask-and-continue;
   - a world ID on every refusal;
   - a typed memory refusal.

## The lead's rulings (16 November 2026)

1. **Default off, opt-in** via `WindowPolicy(row_checks="device")`. Changing the default later is
   its own decision, with its own evidence.
2. **R3,** with the `margins` keyword in the five device-check functions. The device screens; any
   failure, or any ledger above half its bound, hands that window to today's host `check_values`.
   **Every evidence run reports the handback rate.**
3. **Diagnostics in device mode** are reported, not judged.
4. **Scope:** the scalar windowed path first. The vector path follows as its own change.
5. **World refusals** keep their exception classes and messages, and carry `exc.refusal`
   (`WorldRefusal`).
6. **`MemoryRefusal(ConfigError)`** is accepted: callers catching `ConfigError` still catch it.
   The class change on the guarded batch path is named in its commit.
7. **Mask-and-continue** is opt-in `refusals="world"`. The refused world's last accepted state is
   at window granularity, stated in the docstring.
8. **Order:**
   - (a) the four seams first, built now with unit tests (pinned to CPUs 18 and 19, nice 10,
     foreground);
   - (b) at the CPU release, the clean-core measurement: the small set again (`SMALL=small-clean`),
     the 825-node world, the export's world, and the late-run ratios. It gates (c);
   - (c) device checks per the evidence plan, after the lead reads (b)'s numbers.

   Everything lands on main after D172's landing, through the normal gates.

**On the export record:** only engine timings are reproduced here (wall, host checks, steps, per-row
and per-step costs). The source is the coupling operator's matched-arm export (D177); no study and
no study-specific parameter is named.

## In brief

- **Where the time goes.** On the scalar windowed path, `check_values` runs on the host for every
  accepted row. The cost is interpreter dispatch on small arrays: about 3–7 ms per row on small
  worlds, nearly independent of their size (the 825-node tissue is pending). The step itself costs
  0.2–1 ms on these worlds. The model's compiled device checks (already used by vector windows)
  test the same row in 0.02–0.12 ms on the CPU.
- **Recommended for ask 1: option C.** The step executable stays untouched. A second compiled
  program runs the model's `device_checks` over the window's rows, which are already on the device,
  and returns one summary per window.
  - States, histories and observations are therefore bitwise by construction, and crossrev's step
    texts do not move.
  - `projective._burst_checks` already uses this pattern.
- **Refusals stay today's (R3).** The device acts as a pass filter:
  - any device failure, or any ledger above half its bound on any row, sends the window to today's
    host `check_values`, which raises what it raises today;
  - only windows that are clean, with margin, are accepted on the device's word.
- **Opt-in.** `WindowPolicy(row_checks="device")`, with `"host"` as the default. With the default,
  no registered result, record or test moves.
- **The seams need no change to the device program.**
  - The window program already masks a failing world for the rest of its window.
  - Masking it in later windows is the round builder's job, as it is for a finished world. So no
    recompile is needed and the world count does not change.
  - The other three seams are additive. They keep the names and lines that the continuity probe and
    its acceptance test pin.
- **Cost.** About 3.5 agent-days and about 10 CPU-hours of evidence.
  - Projected gain: the export's 480,000-step run falls from 3481 s to about 310–370 s, roughly
    10×.
  - FR-4's 20 s rung pass falls from 176 s to about 39–43 s.

## 1. The current check split

### 1.1 Who checks what (code at 3c10b833; INNER_MODEL_V4_DESIGN.md §5.1)

| Path | On the device, every row | On the host, every accepted row | On the host, observed rows |
| --- | --- | --- | --- |
| Scalar windows (`windows.iter_windows` → `runner._segment`, rollout `_window_rollout`) | The step's own refusals: domain at its stages, controls, the stage rule, the field residual | **All of `check_values`** (`runner._analyse_segment`): domain, every ledger with the operators' terms, the operators' own ledgers, dissipation, a retiring composition's actual domains | `observe_history`; `_observation_tail` (`check_values` on the observed rows joined to the previous one) |
| `runner.run`, `batch.run_batch`, `batch_windows.run_batch_windowed` | As above | All of `check_values`, per world | Observers |
| Vector windows | The step's refusals and `device_checks` on every row of every world | None; per-window summaries only | Observers, continuity |
| Projective (`row_checks: device`) | Burst rows: `_burst_checks` | Jumped rows | Observers |

Only the resolved pump family declares device checks: `device_checks` in `surface_pump` (@1),
`surface_pump_v2`, `surface_pump_v3`, and `pump_composite.Composition`. The water families and
replacement@1 alias the composite's. All of them share `surface_pump_checks.row_checks`. The
kinds' check-path hooks trace under `jnp` (§7.4 (k)), so @3's device checks include the declared
kinds, FR-4's stage read and envelope among them.

### 1.2 Measured

**The coupling operator's matched-arm export (D177).** Its three duration runs used the scalar
windowed path on one pinned core. Engine timings only:

| Steps | Compile | Step execution | Host checks (window analysis) | Total |
| --- | --- | --- | --- | --- |
| 8,000 | 67.8 s | 4.1 s | 52.1 s (41%) | 126 s |
| 80,000 | 53.2 s | 40.4 s | 580.2 s (85%) | 680 s |
| 480,000 | 63.1 s | 219.8 s (0.46 ms/step) | **3179.1 s (91%), 6.6 ms/row** | 3481 s |

**FR-4's development rung, 20 s quick pass**
(`d172-restructure-20261115-01/fr45/transporter/HANDOFF-third-owner.md`):
- compile 24 s;
- stepping 5.8 s (0.29 ms per step);
- **host checks 142.8 s, 7.1 ms per accepted row, 81%**;
- total 176 s.

**This note's probe** (`/mnt/workspaces/Cells/windows-next-20261116/probes/small/`; its first
version, whose development revision each `summary.json` records):
- **Setup.** Nine G1 worlds from the tag's saved definitions, the scalar windowed path, windows of
  50 steps.
- **Provisional numbers.** The probe ran at nice 10 on CPUs 18 and 19, which are hyperthread
  siblings of busy tier-3 lanes (load about 60). It was stopped at the coordinator's request
  before its 825-node world and the export's world ran. Both are pending on clean cores.
- **Columns.** The host column is unprofiled. "Device" is `device_checks` compiled over the same
  window's rows, scanned or vmapped. The host share of window wall time is given only where a world
  had warm windows, since a world's single window includes its compile.

| World (model) | Step, ms | Host check, ms/row | Device scan / vmap, ms/row | Check compile, s (scan) | Host share |
| --- | --- | --- | --- | --- | --- |
| coupling_dynamic (composite@1) | 0.71 | 3.30 | 0.120 / 0.071 | 6.9 | — |
| coupling_pair (composite@1) | 0.55 | 3.16 | 0.079 / 0.054 | 5.5 | — |
| W1_P1 (water@1) | 0.22 | 3.36 | 0.044 / 0.023 | 4.5 | 83% |
| W2 red cell 4 (water@2) | 0.23 | 3.52 | 0.052 / 0.032 | 4.7 | 80% |
| G2 C9 donor (replacement@1) | 0.37 | 3.04 | 0.087 / 0.041 | 7.0 | 79% |
| MG0c chain16 (composite@1) | 0.97 | 3.53 | 0.118 / 0.083 | 6.6 | — |
| symport (water@2) | 0.22 | 3.54 | 0.047 / 0.031 | 4.8 | 80% |
| water (water@1) | 0.21 | 3.36 | 0.049 / 0.033 | 4.6 | 84% |
| replacement_steady (replacement@1) | refused | refused | 0.072 / 0.037 | 6.7 | — |

**Inside the host check.** cProfile of one 51-row window, for a water composite and a replacement
world; cProfile inflates the cost to about 5 ms per row.
- Per row, the time goes to:
  - the domain: 29–32%;
  - the inner ledgers, including a dense capacitor solve: 31–34%;
  - magnitudes and bounds: 18–23%;
  - the operators' own ledgers: about 10% for water;
  - the rest is row slicing and dispatch.
- That is about 165–180 NumPy reductions and 470–510 attribute reads per row.
- So the cost scales with rows, not cells. The export's world paid 6.6 ms per row.

**Parity of the same rows (389 rows, nine worlds).**
- **Verdicts.** The device and the host give the same verdict on every row. For
  `replacement_steady`, the device's dissipation check first fails at row 31. The host refuses
  that window with today's message, "Resolved pump dissipation cannot be negative or decrease".
- **Diagnostics.** These are not bitwise:
  - per ledger, 0–100% of rows match exactly;
  - the differences sit at the residuals' own rounding scale: the capacitor charge residual differs
    by 9.6e-29 C, against a host value of 1.3e-29 C;
  - the one diagnostic already expressed in bound units, the global-charge ratio, reaches 1.8e-3,
    and host and device differ by at most 8.9e-5 of the bound.

### 1.3 What the device check costs instead

On the CPU the compiled checks are 27–76× cheaper than the host's per row. They cost 12–23% of a
step.

Their cost is a second compile of 4.5–7 s. Against 3.0–3.5 ms per row saved, it pays back after
about 1,300–2,300 rows: 1.3–2.3 s of model time at dt 1 ms. That is why a default-on mode would
slow every short run and tier test (§4.1).

The GPU cost of the checks is unmeasured, since the GPU is busy.

## 2. Options for ask 1

**The discriminating question:** does the option leave `_compiled_window_rollout`'s executable
untouched?
- If it does, every state, history and observation is bitwise to today's by construction, and the
  evidence only has to cover the checks.
- If it does not, it is a new step program. The repo's own tests show that XLA's algebraic
  rewrites and fused multiply-adds differ between compiled contexts
  (`tests/unit/test_vector_windows_v3_bitwise.py`).

| Option | Step executable | Trade-offs |
| --- | --- | --- |
| **A. Checks fused into the step's scan** (a new `_checked_window_rollout`, as `_vector_window` does per world) | **New program** | One launch per window. But it compiles another step program, and bitwise identity with today is not assured; it would need its own probe. It saves little over C: one launch and a re-read of history already in device memory |
| **B. Route long single-world runs through vector windows** (B = 1; nothing new) | Different (vmapped) | No engine work. But it is not bitwise to the scalar path: the CPU rehearsal measured up to 5.1e-11 in running ledgers and 4.4e-9 in small observed fluxes (PACKED_GPU_EXECUTION_DESIGN.md). Its records are cohort snapshots, not `write_windowed_run`'s. Messages change to the vector form |
| **C. A separate compiled check program over the device-resident window** (recommended) | **Untouched** | Bitwise states by construction. It reuses the models' `device_checks` unchanged, and projective already uses the same pattern (`_burst_checks`). Costs: a second executable, a second compile of about 5 s, and one more launch per window |
| **D. Vectorize the host NumPy checks over rows** | Untouched | It keeps the checks on the host. But it rewrites `checked_rows`, the composite's `check_values` and every operator's own ledgers for a row axis, when compiled versions already exist. Host diagnostics would also move at rounding (a new reduction order), and the cost would still scale with rows |

**Recommendation: C.** It is the only option that is bitwise by construction and reuses code
already qualified on vector windows.

The check program scans the window's rows. The probe found vmap 1.4–2.1× faster on small worlds,
but a scan holds one row's temporaries at a time, which matters for the 825-node tissue at 256-row
windows. The choice between scan and `lax.map` with a batch size will be measured on clean cores.

## 3. Refusals and messages

### 3.1 What refuses in a scalar window today, in this order

1. **A refused step.** `_segment` reads the rollout's `valid` flags first and raises "`<solver>`
   trial/endpoint domain failure on [t0, t1]…". No row check runs.
2. **The row checks** (`check_values` on rows 0..n, where row 0 is the window's start). The host
   raises by class across the whole window, not by first failing row:
   1. a retiring composition first checks the actual domains of every row
      (`Composition._check_actual_domains`);
   2. `surface_pump.checked_rows` then checks each row in turn: its domain, then each inner
      ledger, with the operators' terms, in order;
   3. after all rows, dissipation over the window: any negative value, or any decrease between
      consecutive rows;
   4. finally, each row's operators' own ledgers, in declared order.

   The messages carry no time: `DOMAIN_MESSAGE`, `LEDGER_MESSAGE + name`, `DISSIPATION_MESSAGE`,
   `op.LEDGER_MESSAGE + name`.

So "the first failing row and its bits" does not give the host's message in a mixed window. Take an
operator's own-ledger failure at row 5 and an inner-ledger failure at row 7: the host raises the
inner one. That is also how `vector_windows._failure` can differ from the host when more than one
class fails. Its test covers one class at a time.

### 3.2 Three ways to decide on the device

| | Rule | Messages | Exactness |
| --- | --- | --- | --- |
| **R1** | The device decides; the message comes from the first failure, with the host's class order declared per model | The device-derived text | The decision agrees with the host's except for a residual within rounding of its bound |
| **R2** | **Pass filter**: any device failure sends the window to today's host `check_values` | Today's, from today's code | Exact whenever the device flags. It misses a row the host would fail while the device passes, which needs a residual within rounding of its bound |
| **R3** | R2, plus a **guard band**: a ledger whose device residual exceeds half its bound on any row also sends the window to the host | Today's | Exact unless the host and device evaluations of one residual differ by more than half its bound. Measured so far for one ledger only, global charge, on windows of at most 51 rows: at most 8.9e-5 of the bound |

**Recommendation: R3.**
- The refused window, its exception class and its message are today's, from today's code on the
  same rows. The scalar path already holds the rows on the host for its `RunResult`, so the
  re-check needs no extra transfer.
- A flagged window costs one window of host checks. A refusal ends the run, and a normal run sits
  orders of magnitude below its bounds: the probe's largest global-charge ratio was 1.8e-3. So the
  host re-check runs in practice only at a refusal, or for a run that is near its tolerance.
- The other classes need no margin:
  - **Dissipation** compares state values that are bitwise identical on both sides, through single
    IEEE subtractions, so its decisions are identical where both sides read the stored rows. A
    retiring composition's adjusted rows are computed on each side separately; E8 counts any
    disagreement there.
  - **The row domain** is the same `domain_valid` that the step's own stage refusals evaluate,
    compiled. The host's NumPy evaluation could differ only at a threshold within rounding. E8
    counts any such row.
- R3 needs one model-side change: a `margins` keyword (§4.3). R2 needs none, so it is the fallback
  if the lead prefers no change to model files.
- **R3's speed-up is conditional.** If a ledger sits above half its bound for long stretches, every
  such window goes to the host, and mode on gains nothing there.
  - Running ledgers accumulate rounding with the step count, and RK4 worlds hold the energy ledger
    to an absolute bound. Their ratios late in a long run are unmeasured.
  - R2 keeps the gain regardless; R3 trades it for exactness near a bound. That trade is what
    ruling 2 decides.
  - **So the first clean-core measurement, before any build,** is every ledger's ratio to its bound
    late in the export's 480,000-step run and in FR-4's rung (the probe extended with the
    bounds).

### 3.3 What stays host-only, and why

| Stays on the host | Why |
| --- | --- |
| The verdict and message of any window the device flags (§3.2) | Today's code decides, so refusals stay exactly today's |
| Observers (`observe_history`) on observed rows | They build host records; the cost scales with observed rows |
| Observation continuity (`_observation_tail`: `check_values` on the observed rows joined to the last observed row) | It checks the observation records themselves, across windows, which device rows cannot. Sparse observations keep it cheap |
| `validate_checkpoint` at a start or resume, and `check_checkpoint` | One row, once, with the layout identity |
| Definition and clock admission (`check_definition`, `bind_step_checks` by chunk, `checked_grid`) | Once per clock |
| Models without device hooks (every family outside the resolved pump family) | They have no device form. `row_checks="device"` is refused for them, fail-closed (`require_device_checks`) |
| `jit: false` runs | There is no compiled program; refused, as on vector windows |
| `runner.run`, `run_batch`, `run_batch_windowed`; projective's jumped rows | Out of this round's scope. The batch path refuses `"device"`; `run` takes no policy; projective keeps its own `row_checks` |
| Merging diagnostics across windows (`merge_diagnostics`) | One summary per window |

## 4. Ask 1's API

### 4.1 The switch: opt-in, on the window policy

```python
@dataclass(frozen=True)
class WindowPolicy:  # cells.core.windows
    window_steps: int = 256
    recording: str = "observations"
    row_checks: str = "host"  # "host" | "device"
```

- **The name follows projective's own `row_checks: host | device`.**
- **`to_dict()` writes `row_checks` only when it is `"device"`.** So every existing manifest
  (`write_windowed_run`, `batch_window_io`) keeps its bytes, and old policy dictionaries load
  unchanged.
- **Scope.** `"device"` is the scalar windowed path's switch. Vector windows always check on the
  device, `run_batch_windowed` refuses `"device"`, and `plan_windows` refuses it for `jit: false`
  runs and for models without device hooks.
- **Across a restart the mode may change.** It is an execution choice; the state is the same in
  both modes. The windowed writer records each run's policy, and E6 includes one restart in mode on.
- **Off, auto or on (ruling 1).**
  - **Off by default (recommended):** nothing registered moves. Long runs opt in on one line,
    which is recorded in their manifest.
  - **Auto** (device above about 2,000 planned rows): one definition's diagnostics would then
    depend on its horizon and restart point.
  - **On:** every short run and tier test pays a second compile of about 5 s, and every saved
    diagnostic moves at rounding.
  - Flipping the default later is its own gated change, after mode on has run long and on the GPU.

### 4.2 The check program (new `cells/core/row_checks.py`)

- **Its inputs:**
  - the window's start state, as row 0. Row 0 is its own predecessor, as vector windows re-check a
    window's start;
  - the rollout's device history, rows 1..width;
  - the real step count n, and the global step index of row 0;
  - the parameters, and the model's `device_check_constants`. These are placed on the device once.
- **It scans rows 0..n, masking slots beyond n,** so the last partial window reuses the same
  executable.
- **It returns three small arrays:**
  - `first [checks]`: the first failing row of each check, or -1;
  - `maxima [diagnostics]`: each `DEVICE_DIAGNOSTICS` maximum over rows 0..n;
  - `ratios [ledgers]`: the largest |residual| / bound over rows 0..n.
- **Compiled once per window execution,** in an executable cache keyed like projective's
  `_executable`. Its memory analysis is recorded with the window's resources.
- **`HOST_DECIDES_ABOVE = 0.5`.** The device decides a window only when nothing failed and every
  ratio is at most this value.

### 4.3 The models' one change (R3 only)

`device_checks(previous, row, p, constants, steps, *, margins=False)`.
- With `margins=True` it also returns the per-ledger ratios.
- **Where:** `surface_pump_checks.row_checks`, plus the `device_checks` of `surface_pump`,
  `surface_pump_v2`, `surface_pump_v3` and `Composition`. The water and replacement families alias
  the composite's.
- **The flag is a static Python branch,** so with its default every existing trace is unchanged:
  vector windows, projective, crossrev's device-check texts and the continuity probe's programs.

### 4.4 The runner

- **`_WindowExecution`** gains the compiled checks (`row_checks.DeviceRowChecks`). `_iter_windows`
  builds them when `policy.row_checks == "device"`.
- **`_segment`** keeps its step-refusal check first. It then launches the check program on the
  device-resident `history`, and transfers the history as it does today (`RunResult` still holds
  every row, so `recording="full"`, `checkpoint_at` and sinks are unchanged).
- **`_analyse_segment(..., summary=None)`:**
  - with no summary, or a flagged one, it runs today's `check_values`;
  - otherwise the window's diagnostics are the device's maxima, under the host's key set.
- **Reporting.**
  - Timings gain `device_row_check_seconds` and `host_row_check_seconds`.
  - `WindowedResult.resources` gains the mode and the number of windows the host decided.
  - A field is not added to `RunResult`, because `ProjectiveRunResult` extends it.

### 4.5 Later, not in this round

- Running the next window while the host finishes this one, as vector windows do. After the change
  the remaining host work per window is small.
- A history transferred on demand, for GPU runs that record observations only.
- One check program shared with projective bursts.
- The default flip.

## 5. Ask 2: the packed planner's seams (`cells.core.vector_windows`)

### 5.1 Constraints

- **Additive only.**
  - The continuity probe names `_Round`, `_initial_checkpoints`, `_vector_window`,
    `_compiled_vector_window`, `compile_window` and `resident_inputs` as entry points
    (`validation/continuity/probe.py`). A tree without them answers `cannot_decide`.
  - `tests/integration/test_continuity_acceptance.py` text-matches three lines of
    `vector_windows.py` and counts `_Round(` at exactly two call sites.
  - The seams keep all of these: the first round is built through one private helper, so `_Round(`
    keeps two call sites.
- **`_vector_window`'s program is unchanged by every seam.** Continuity's P part therefore stays
  identical for vector-window checkpoints written before the change.

### 5.2 Window arguments, in place of `packing._lone_arguments`

```python
@dataclass(frozen=True)
class WindowArguments:
    model: object
    args: tuple  # compile_window's arguments, [world, ...]: state, steps, counts, table, index,
                 # slots, first_step, params, active, constants
    rows: int    # stored observation rows (compile_window's rows)
    starts: Mapping[int, Checkpoint]

def window_arguments(plan, checkpoints=None, *, abstract=False) -> WindowArguments: ...
```

- **It returns the cohort's first window as the program receives it.** It is built by the path's
  own constructors: `_initial_checkpoints`, the first round's `_Round`, and `resident_inputs`.
- **`abstract=True`** gives `jax.ShapeDtypeStruct` leaves with the device's sharding and places
  nothing, for keying and probing.
- **A test holds `window_key` of the abstract arguments equal to the key of a real run's launch,**
  shown by the executable being reused at 0 s.
- **With `window_key`** (the planner's one-line swap, recorded on its branch at f31927be), this
  removes the planner's last private calls into the core.

### 5.3 A world ID on every vectorized refusal

- **The record.** Every refusal that concerns one world carries a frozen
  `WorldRefusal(world_id, stage, error, message, step_index, time_interval, checks, checkpoint)`
  as `exc.refusal`.
  - `stage` is one of admission, start, step, check or observation.
  - `checkpoint` is the world's last accepted checkpoint.
  - `WorldCheckError` keeps its fields.
- **Sites:**
  - admission: `checkpoint_batch_limits`' per-world refusals, and `_plan_vector_windows`;
  - start: `_initial_checkpoints`;
  - step and check: `_failure`;
  - observation: the observer and continuity refusal.
- **The exception classes and messages do not change (ruling 5).** `type(exc).__name__` and the
  message text are stored and compared in:
  - the results baseline's refusal records;
  - `packing.Refusal.error`;
  - the packed runner's `REFUSED_BY_OBSERVATION` regex;
  - many validation records.

  Subclasses such as `WorldConfigError` would change all of them. With `exc.refusal`, the planner
  drops the regex.
- **Cohort-level refusals carry none.** Examples: IDs not distinct, an empty list, a batch limit.
  As built, the round builder's own refusals mid-run (held-control segments and observation rows
  that a later window cannot hold) are cohort-level too: they end the run in either mode.

### 5.4 A typed memory refusal

- **`class MemoryRefusal(ConfigError)`,** with `required_bytes`, `limit_bytes` and `stage`
  (`checkpoints`, `estimate` or `compiled`).
- **Where it is raised:** at the four `max_working_bytes` sites that a vector run reaches:
  - checkpoint storage, in `batch.checkpoint_batch_limits` and in `cohort_limits`;
  - the estimate in `_plan_vector_windows`;
  - the compiled window in `launch`.
- **As built,** the guarded batch path's own two estimate sites (`batch.plan_batch`,
  `batch_windows._plan_batch_windows`) raise it too, so every `max_working_bytes` refusal has one
  class.
- **Unchanged:** the messages, and every `except ConfigError` and `match="max_working_bytes"`.
- **The planner** replaces its message match with `except MemoryRefusal`.
- **Padded-step limits stay plain `ConfigError`.** They bound work, not memory, and the planner
  leaves them unbounded.

### 5.5 Mask and continue

```python
iter_vector_windows(spec, policy, checkpoints=None, *, refusals="batch")      # "batch" | "world"
run_vector_windowed(spec, policy, checkpoints=None, *, sink=None, refusals="batch")
```

**What the device already does.**
- `_vector_window` stops a failing world for the rest of its window (`ok & ~failing`). It keeps
  that world's last accepted row, and every other world continues.
- A finished world already rides along with a count of 0. Its slots are computed and discarded,
  and only its start row is re-checked.

So masking a refused world in later rounds needs only the round builder and the host loop. The
executable, the world count and every other world's inputs stay the same.
- **No recompile.** That replaces the resume's B − 1 compile: 70–120 s per 825-node executable on
  the L4, plus 70–100 s under the deterministic flag.
- **No change of batch size.** The development GPU run showed that packing moves small observables
  up to 1.6e-8 on the GPU. A B − 1 executable is a different GPU program, so this also matters for
  the results.

**`refusals="batch"`** is the default, and is today's behaviour: the first failing world's
`WorldCheckError` refuses the batch.

**`refusals="world"`:**
- **Every world that fails in a window is refused alone.**
  - Its `WorldRefusal` carries the same reason that batch mode would raise for it, without the
    batch-outcome suffix "; vectorized batch refused".
  - Its last accepted checkpoint is its checkpoint at the start of the refusing window. This is
    window granularity, as on the scalar path and in the planner's resume.
  - Its rows, observations and diagnostics from that window are dropped. The window is accepted
    for every other world.
- **`_Round` gains a `mask` method** (as built; the design's keyword would have changed a line
  the continuity acceptance test pins). `_Round` builds its inputs once per group of identical
  worlds, so masking is a per-member override after the round is built: a masked member gets
  count 0, no steps, no observation slots, and is not live. Replicas of a refused world
  continue.
- **The observation lag.**
  - A host observation or continuity refusal in window k is found after window k + 1 has been
    launched with that world live.
  - That world's window k + 1 outputs are discarded, and it is masked from window k + 2.
  - A summary from a masked world is ignored.
- **What a caller sees.**
  - `VectorWindow` gains `refusals`, the refusals so far.
  - `WindowedBatchResult` gains `refusals`, empty by default. Its `worlds` hold the completed
    worlds.
  - `checkpoints` stays complete: refused worlds stay at their last accepted checkpoint.
- **At a resume,** the caller passes the refusals so far (`refused=`), so those worlds ride masked
  from the first round with the same world count, rather than running again. A cohort snapshot
  written in world mode records them.
- **The planner** replaces its resume loop with `refusals="world"`.

## 6. The equivalence evidence plan

**What the baseline cannot show by itself.**
- Every G1 world runs one scalar window of at most 200 steps (13,740 rows over 110 worlds). So no
  predecessor row or step offset crosses a window boundary.
- It holds one refusal: `crossrev-base/replacement_steady`, by dissipation.
- E6 and E7 therefore cover window boundaries and every check class.

**Mode off, the default, against c1** (the end game's G1 save, `endgame/c1-3c10b833/g1/merged`):
- **E1, G1 bitwise.** All 113 worlds at this branch's head, from the tag's saved definitions
  (`save --from`, as c1's G1 ran). Every array is bitwise, diagnostics included, and the refusals
  are identical in type name and message. This shows that the default path is unchanged.
- **E2, crossrev on the eight sets.** Identical to c1: no traced model code changes while
  `margins` is off.
- **E3, tiers 1 and 2** at the recorded baseline.
- **E4, continuity.** The probe's P, B and H parts on one vector checkpoint are identical under
  3c10b833 and this branch. `test_continuity_acceptance.py` runs once, deliberately.

**Mode on against mode off, at one revision** (since off ≡ c1, this is also on against c1):
- **E5, G1 in mode on.** The comparison tool gains `--row-checks device`, applied to its scalar
  windowed calls only.
  - Times, histories, observations and final states are bitwise.
  - Refusals are identical in type name and bare message, including `replacement_steady`'s.
  - The diagnostics have the same key set. Their values are **reported, not judged**, as packed
    ruling 2 treats rounding residuals. This is ruling 3; a relative tolerance cannot fit
    residuals that differ by more than their own size.
  - The comparison tool gains a report-only rule for `diagnostics.*`.
- **E6, window partitions.**
  - One world per family and operator set (about 12 worlds) runs at 4-, 7- and 200-step windows
    in mode on. The export's own world runs at 256 steps.
  - At each partition, states and observations must be bitwise to mode off, and refusals
    identical. Across partitions, mode on must show what mode off shows.
  - The number of windows the host decided is reported (expected: none), with the diagnostics' run
    maxima across partitions.
  - One restart in mode on, from a mode-off checkpoint: states and observations bitwise to the
    uninterrupted run.
- **E7, seeded faults in runs, both modes.**
  - **Method:** test doubles of the checked step that corrupt one field at one step, the technique
    of `tests/unit/test_vector_windows.py`.
  - **Faults:**
    - the domain;
    - one ledger of each class: material, charge, energy, work;
    - an operator's own ledger: bath schedule, water and lumen;
    - dissipation, negative and decreasing, including across a window boundary;
    - a retiring composition's actual domain (partition);
    - a refused step;
    - mixed windows, with two fault classes at different rows: own at row 5 and inner at row 7
      must raise the inner one in both modes.
  - **Pass:** the same exception class name and `str()`, the same windows yielded, and the same
    last yielded checkpoint, bitwise.
- **E8, check parity on every saved row.**
  - The probe's parity part, with the `margins` output, over c1's G1 histories. Per row the
    verdicts must agree.
  - Per ledger it reports the largest |host − device| / bound and the largest device ratio,
    against the guard band of 1/2. It also counts domain and dissipation disagreements, including a
    retiring composition's adjusted rows.
  - **The long-run spread:** the export's 480,000-step run in mode on, with every window's ratios
    recorded and host `check_values` sampled every 50th window.
  - **The GPU spread is unmeasured** until a GPU gap; mode on stays CPU-qualified until then.
- **E9, performance.** The export's three duration runs (8,000 to 480,000 steps) and FR-4's 20 s
  pass in mode on, against their recorded times. The 825-node tissue's per-row costs on clean
  cores.

**E10, the seams (unit tests):**
- The abstract `window_arguments` key equals the real one, and the executable is reused.
- The default `refusals="batch"` passes the existing vector tests unchanged.
- **A value-twin refusing world in mode `"world"`:** the packed smoke's world whose pump is 1e5
  times stronger.
  - The continuing worlds must be bitwise equal to the same cohort with a non-refusing twin in its
    place, on the same executable.
  - The refused world's record must equal batch mode's `WorldCheckError` for it in world ID,
    stage, step, interval, checks and reason.
- A planted observation refusal discards the next window's outputs and masks the world after it.
- Every vectorized refusal carries `exc.refusal`; memory refusals are `MemoryRefusal`, with
  unchanged messages.
- The planner's own tests, on its branch, once it switches to the seams.

## 7. Cost

**Engineering:** about 3.5 agent-days.

| Piece | Agent-days |
| --- | --- |
| The policy field and its refusals; `row_checks.py` (scan, summary, cache); `margins` in five functions; the runner; the writer's records | 1.2 |
| The comparison tool's `--row-checks` and report rule; the parity tool over saved histories | 0.3 |
| Tests E7 and E10 (part 1) | 0.6 |
| `window_arguments`; `exc.refusal` at every site; `MemoryRefusal` | 0.5 |
| Mask-and-continue (`_Round`'s override, the loop, the observation lag, the results) and its tests | 0.9 |

**Machine time for the evidence:** about 10 CPU-hours, or 3 hours wall on four cores.

| Item | CPU-hours |
| --- | --- |
| G1 mode off | 2.1 |
| G1 mode on | 2.5 (adds about 5 s of check compile per world) |
| Partitions | 1 |
| Parity over 13,740 rows | 0.7 |
| Crossrev | about 1 |
| Tiers 1 and 2 | about 1 (17 minutes on four cores) |
| Continuity acceptance | 0.5–1 |
| Duration probes in mode on | about 0.5 |

**Projected gains.** These use the records' own splits, with the probe's device cost per row
(0.02–0.12 ms) and a second compile of about 5–10 s. They assume that the host decides no window:
true under R2, and under R3 only while every ledger stays below half its bound (§3.2).
- **The export's 480,000-step run:** 63 s compile, 5–10 s check compile, 220 s steps, 10–58 s device
  checks and about 15 s for the rest: **about 310–370 s against 3481 s**.
- **FR-4's 20 s pass:** 24 s compile, 5–7 s check compile, 5.8 s steps, 0.4–2.4 s device checks
  and 3.4 s for the rest: **about 39–43 s against 176 s.** Compile then dominates. FR-4's world
  declares kinds, whose device cost per row the probe did not measure.
- **The 825-node tissue and the GPU** are pending measurements.

## 8. Rulings asked of the lead

Answered on 16 November 2026: see "The lead's rulings" at the top.

1. **The default:** off with opt-in `row_checks="device"` (recommended), auto, or on.
2. **The refusal rule:**
   - R3, the pass filter with a guard band at 1/2, plus the `margins` keyword in five
     device-check functions (recommended, after the first clean-core measurement of §3.2 shows
     the ledgers stay below half their bounds late in long runs);
   - R2, the pass filter with no model change, which keeps the gain regardless;
   - or R1, the device decides.
3. **Diagnostics in mode on are reported, not judged,** in G1 and in protocol records, with E8's
   bound-unit spread as the evidence. This follows packed ruling 2.
4. **Scope:** the scalar windowed path only. `run`, `run_batch`, `run_batch_windowed` and
   projective are unchanged this round.
5. **World refusals:** classes and messages are kept, with `exc.refusal` (recommended), or
   subclasses that rename stored records.
6. **The memory refusal:** a `ConfigError` subclass `MemoryRefusal`, with messages unchanged. Its
   class name also changes for the guarded batch path, which reaches `checkpoint_batch_limits` too.
7. **Mask-and-continue:**
   - opt-in `refusals="world"`;
   - window granularity for the refused world's last accepted state;
   - its message without the batch suffix.
8. **Order:** part 1 and the seams are independent files apart from `vector_windows.py`, which
   only part 2 touches. They can land separately, part 2 first if the planner's qualification is
   nearer.

## Sources

- **Code** at 3c10b833:
  - `src/cells/core/vector_windows.py`, `windows.py`, `runner.py` (`_window_rollout`, `_segment`,
    `_analyse_segment`), `batch.py`, `batch_windows.py` and `projective.py` (`_burst_checks`);
  - `src/cells/models/surface_pump.py` (`checked_rows`, `ledger_limits`, the messages),
    `surface_pump_checks.py` and `pump_composite.py` (`Composition.check_values`,
    `device_checks`).
- **Docs:**
  - INNER_MODEL_V4_DESIGN.md §5.1, §7.4 (e) and (k);
  - CHECKPOINT_CONTINUITY_DESIGN.md §3.1;
  - PACKED_GPU_EXECUTION_DESIGN.md (`packed-gpu-planner` 69a14cb5), with `packing.py` and
    `packed_runner.py`.
- **Records:**
  - the coupling operator's matched-arm export (D177): its duration runs' engine timings;
  - `/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/transporter/HANDOFF-third-owner.md`;
  - the tag baseline `acceptance/baseline-44227075` (its saved definitions and its refusal record);
  - this note's probe, `/mnt/workspaces/Cells/windows-next-20261116/probes/` (`probe.log`,
    `small/summary.json` and the per-world records).
