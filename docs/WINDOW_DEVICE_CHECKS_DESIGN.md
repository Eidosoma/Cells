# Device row checks for scalar windows, and the vector path's seams (design, 16 November 2026)

**Status: ruled by the lead on 16 November 2026 (below).** The seams are built (step a), on branch
`windows-next-clean` (from c1 = integration-d172 3c10b833). The clean-core measurement (step b,
§1.4) is done, and the lead then approved the device checks (step c) under five conditions. §9
settles the details §4 left open, before the code. The branch now holds main and core-next, and
lands after core-next (§9.1). The measurement probe is
`validation/execution/window_check_probe.py`. Every timing below is development evidence, not a
verdict.

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

### 1.4 The clean-core measurement (step b, 16 November 2026)

Run at 0a4e1d24 (clean) on one clean core, CPU 5. The records are in
`/mnt/workspaces/Cells/windows-next-20261116/probes/`: `small-clean/`, `tissue825/`, `export/`,
`long/` and `long-short/`.

**Per-row costs, in ms.** "Host" is `check_values`; "scan" and "vmap" are the model's
`device_checks` compiled over the same rows.

| World | Step | Host | Device scan | Device vmap | Scan compile, s | Host share |
| --- | --- | --- | --- | --- | --- | --- |
| Eight small worlds (G1 sets) | 0.14–0.88 | 1.9–2.3 | 0.035–0.114 | 0.025–0.079 | 5.2–8.9 | 74–82% where measured |
| The export's world | 0.14 | 1.80 | 0.016 | 0.006 | 4.8 | 90% |
| FR-4's world (kinds; `long/`) | 0.31 | 7.0 | 0.17 | — | — | — |
| The 825-node tissue (S825) | 57.4 | 21.5 | 2.8 | 1.4 | 14.3 | **28%** |

- **The 825-node tissue gains least:** its host share is 28%, so device checks can save it at most
  about a quarter of its wall time.
- **Parity:** host and device gave the same verdict on every sampled row. `replacement_steady`
  is refused by dissipation in both.

**Ratios to the bounds over long runs (`--long`), under the guard band of 1/2.**

| Run | Windows | Largest ratio (ledger, where) | Late ratio (last tenth) | Handed back |
| --- | --- | --- | --- | --- |
| The export's 480,000 steps | 480 | 0.068 (`local`, window 8) | 7.0e-4 | 0 |
| FR-4's world at dt 1 ms, 900,000 steps | 900 | 3.2e-3 (`local`) | 8.7e-5 | 0 |
| RK4 D150 (`rk4_dr2.5_dt0.1`), 5,000 steps | 5 | **0.257** (`total`, first window) | 1.5e-3 | 0 |
| RK4 water (crossrev base), 40 steps | 1 | 5.0e-6 | — | 0 |
| The 825-node tissue, 200 steps | 1 | 9.8e-3 (`global_charge`) | — | 0 |

- **The margin of record is 0.257,** RK4 D150's first window: about 2× below the band.
- **Ratios peak in a run's first windows.** There the rounding allowance, which grows with the
  step count, is smallest. They then fall.
- **Host samples:** the host's `check_values`, sampled every 50th window, refused no sampled
  window. The diagnostics differ at rounding.

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
class WindowPolicy:  # cells.execution.windows
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

### 4.2 The check program (new `cells/execution/row_checks.py`)

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

## 5. Ask 2: the packed planner's seams (`cells.execution.vector_windows`)

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

**The plan as written before the build.** §9.6 maps the lead's five conditions to the evidence actually run, and lists what is dropped. Since the core-next merge, the reference revision for E1 and E2 is d6814d57 (§9.1), not c1.

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
    in mode on. The export's own world runs at its record's window size.
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

## 9. Step (c): the open details, decided before the build (16 November 2026)

The lead approved step (c) after reading §1.4, under five conditions:
- **C1:** outputs are bitwise identical with and without device checks (checks only, no physics);
- **C2:** a host-against-device agreement test;
- **C3:** a planted window over the band is handed back and refused on the host;
- **C4:** crossrev shows programs changing only where a world opts in;
- **C5:** the measured speedups are recorded beside the projections.

### 9.1 Base and dependency

- **The branch holds main b92b4c2b** (merge f3292423) **and core-next 5f4d79ad** (merge d6814d57;
  the lead's Option A).
- **Why core-next:** `margins` is built on core-next's `row_checks(..., ledgers=None)` and on its
  `device_checks` calls (INNER_MODEL_V4_DESIGN §7.4 (p)), which rewrote the lines §4.3 changes.
- **So the branch lands after core-next.** If core-next moves first, it is merged here again; it is
  never rebased.
- **The default path's reference revision is d6814d57,** not c1, since core-next changed @3 and the
  kinds. Crossrev's base set was traced there before any model edit
  (`/mnt/workspaces/Cells/windows-next-20261116/crossrev/before-d6814d57/`).

### 9.2 The switch and its refusals

- **`WindowPolicy.row_checks`** is `"host"` (the default) or `"device"`. As §4.1 says, `to_dict()`
  writes it only for `"device"`.
- **Admission,** in `plan_windows`, via `row_checks.admit` (fail-closed, `ConfigError`):
  - the run must be compiled (`jit: true`);
  - the model must have `device_checks` taking `margins`, `device_check_constants`,
    `DEVICE_CHECKS` and `DEVICE_DIAGNOSTICS`.

  The hook list lives in `row_checks.py`, because `windows.py` importing `vector_windows` would be
  an import cycle.
- **Refused until qualified** (the lead's rulings after §9.7's evidence, D187: no claim without
  teeth):
  - **a GPU backend,** until a GPU measurement of the host-against-device spread exists;
  - **a composition with a live retiring operator** (the division set's partition), whose device
    checks read adjusted rows. Its refusals have no planted test yet. A planted dissipation
    decrease in a dividing world lifts this refusal once it passes.
- **The batch path and the vector path refuse `"device"`:**
  - the batch path checks rows on the host, and vector windows always check them on the device;
  - their records keep today's policy dictionary. That covers `batch_window_io`, cohort snapshots,
    and continuity's `_policy`, which demands exactly `{window_steps, recording}`.
- **Continuity requests** with a device-mode policy are refused by continuity's own `_policy`.
  That is fail-closed, and continuity is unchanged.
- **The CLI's scalar `windowed` commands** gain `--row-checks {host,device}`.

### 9.3 The check program (`cells/execution/row_checks.py`)

- **The form: a `lax.scan`** over the window's full-width device history. This is the form §1.4
  measured, and the projections rest on it.
- **The rows:**
  - row 0 is the window's start, its own predecessor;
  - row k (1 to width) has predecessor k − 1;
  - slots past the real step count are masked;
  - row k's step count is row 0's global step index + k, passed in as a traced input.
- **The outputs:**
  - `first [checks]`: each check's first failing row, or −1;
  - `maxima [diagnostics]`;
  - `ratios [ledgers]`: each ledger's largest |residual| / bound over the window. A zero residual
    gives 0 and a NaN gives +inf, as in the probe, so §1.4's margin stays comparable.
- **The decision.** The device decides a window only when no check failed and every ratio is at most
  `HOST_DECIDES_ABOVE = 0.5`. The test is written so that a NaN ratio goes to the host. A window
  with no steps stays on the host: it has one row.
- **The executable.** There is one per run (per `_WindowExecution`), compiled at the first window.
  Its compile seconds join that window's compile time. Its temporary bytes, from the executable's
  memory analysis, go into the run's resources.
- **The key-set guard.** When the checks are built, the host's `check_values` runs once on the
  start row. If its keys differ from `DEVICE_DIAGNOSTICS` as a set, device mode is refused, so a
  model whose two diagnostic lists drift apart fails closed.
  - The device's diagnostics are then given in the host's key order, so a run's records keep one
    key order in both modes. A composite with an operator's own ledger orders it differently in
    the two lists: the host appends it after the energy and charge ratios.
- **Later, not now:** vmap was 1.3–2.7× faster per row than the scan in §1.4, and a batched
  `lax.map` would bound its memory. That changes the check program, so it needs its own
  agreement evidence.

### 9.4 The runner and the records

- **`_segment`** launches the check program on the device-resident full-width history before slicing
  it, then transfers the history as it does today.
- **`_analyse_checked_segment`,** in device mode only:
  - a host-decided window runs today's `check_values`, raising today's exception class and message;
  - a device-decided window takes the device's maxima.

  As built, `_analyse_segment` keeps its signature and behaviour, because tests wrap it with
  seven fixed arguments. Both functions end in `_accept_segment` (the observers and the final
  checkpoint).
- **The per-window channel.** In device mode `_segment` returns a `CheckedRunResult(RunResult)`,
  following `ProjectiveRunResult`'s pattern. Its one field, `row_checks`, records:
  - who decided the window;
  - why it was handed back, if it was: a device failure, or a ratio above the band;
  - the window's ratios.

  In host mode `_segment` returns today's `RunResult`, so nothing in host mode changes type, key or
  byte. `RunResult` itself cannot gain a defaulted field, because `ProjectiveRunResult` extends it.
- **In device mode only:**
  - each window's timings gain `device_row_check_seconds` and `host_row_check_seconds`;
  - `windows.jsonl` records each window's outcome;
  - `WindowedResult.resources["row_checks"]` holds the mode, the windows, the windows the host
    decided (by reason), and each ledger's largest ratio over the run. That gives every run's
    handback rate (ruling 2).

### 9.5 What "bitwise" covers

- **Bitwise between the modes:** times, histories, observations and checkpoints. The step
  executable is the same one, and the check program only reads the history.
- **Not bitwise:** the diagnostics (ruling 3). So `windows.jsonl`, `summary.json` and the manifest
  differ between modes.
- **So the tests compare arrays, not manifests.**

### 9.6 Evidence for the five conditions

Under D187, each claim is proven once, at its cheapest level.

| Condition | Evidence | Cost |
| --- | --- | --- |
| C1, bitwise | Unit tests, arrays bitwise in both modes. @1 runs at windows of 4 and 7 steps, with a partial last window, and restarts in device mode from a host-mode checkpoint. The water composite (an operator's own ledger) runs at 4 steps; @2 and @3 with a kind run at 5. A retiring composition (the division set's partition) has no unit test: crossrev traces its device checks with margins (C4), and the driver runs two of its worlds in both modes (§9.7). The C5 runs compare their arrays where both modes run | Test files under the 90 s cap |
| C2, agreement | A unit test of the check program with a stub model: rows, predecessors, step counts, masking and the decision. Each device-decided window's diagnostics are compared with the host's `check_values` on the same rows, under the established criteria (2% of the smallest bound; energy at 1e-9 relative; `test_surface_pump_device_checks.py`). Faults planted at a window's first and last rows, and a dissipation decrease across a boundary, must be caught. In the long runs the host is sampled every 50th window, reported | As above |
| C3, the band | A ledger residual is planted over the host's bound, with the device under-reading that ledger by half, so its ratio lies in (1/2, 1]. The window must be handed back and refused with the host's class and message. **Control:** with the band at 1, the same run is accepted. A residual in the band that the host accepts is handed back and the run goes on. It runs on a world with an operator's own ledger, so host- and device-decided windows pass `merge_diagnostics` together. A device failure is refused as in host mode | As above |
| C4, crossrev | The eight sets' jaxprs and bindings at the branch head against d6814d57: identical. Crossrev also gains the `margins=True` device-check trace for every world, the opted-in program (D187 rule 2). An older side lacks it, and `compare` reads only the older side's files | About 1 CPU-hour, detached |
| C5, speed | `run_windowed` in device mode at the records' window size: the export's 8,000, 80,000 and 480,000 steps; FR-4's 20 s pass and its 900,000 steps; the 825-node world. Host mode is re-run on the same cores for the short arms. The long host arms (the export's 480,000 steps, FR-4's 900,000) come from records and projections | About 1 hour on the timed lane |

**Dropped from §6, with the reason:**
- **E5, G1 in mode on** (2.5 CPU-hours). C1's families and C5's long runs cover the bitwise claim.
  - D187 rule 2 instead asks for one device-mode run in the results baseline. A
    `run_windowed_device` path in the run-paths set is proposed to the lead. It is not built here,
    because the baseline's `compare` fails on an array missing from either side, so the next
    baseline save must include it.
- **E6's 12 worlds × 3 partitions:** C1's five families at two partitions, plus C5.
- **E7's full fault list:** under R3 the host decides every flagged window with today's code, and
  each class's detection is already proven per row by the device-check tests. C2 and C3 keep the
  routing cases.
- **E8 over G1's 13,740 rows** (0.7 CPU-hours): per-row parity is proven in three files. C3 covers
  the margin output, and the long runs sample the host. It stays optional.
- **E1, G1 in mode off,** belongs to the results gate at landing, if the lead runs it. Crossrev
  (C4) and the tiers cover the default path here.

### 9.7 The evidence as run (16 November 2026)

Every run below is from the frozen snapshot of c2aec027 (`/mnt/workspaces/Cells/windows-next-20261116/stepc/`).
Each mode ran in its own process.

**C1–C3: the unit tests.** The four new files hold 28 tests, and all pass. A mutation pairing each
row with itself instead of its predecessor fails the boundary case.

**C4: crossrev, the eight sets** (CPUs 11 and 27, `stepc/crossrev/`).
- **c2aec027 against d6814d57: identical.** That is 219 of 219 jaxpr texts and their constants, and
  103 of 103 bindings.
- **Every one of the 73 worlds traces the opted-in program** (`device_checks_margins`).
- **d6814d57 against c1** (informative): identical in seven sets. The division set's three worlds
  differ in their step, right-hand-side and device-check texts and in their bindings. This is
  core-next's item 4, insertion@2's gate at opening, recorded as an intended change before
  core-next landed.

**C5: the measured speedups beside the projections** (`validation/execution/window_row_checks_runs.py`,
`run_windowed`, on the timed lane, CPUs 4 and 5, at the records' window size and recording). The
headline figures compare both modes on the same cores; the records' figures are given beside them.

| Run | Host mode | Device mode | Measured speedup | Projected (§7) |
| --- | --- | --- | --- | --- |
| The export, 8,000 steps | 33.2 s | 23.3 s | 1.4× (compile dominates) | — |
| The export, 80,000 steps | 166.6 s | 34.8 s | 4.8× | — |
| The export, 480,000 steps | about 908 s on these cores (estimate; 3481 s in its record) | 96.3 s | about 9.4× (36× against the record) | 310–370 s, about 10× |
| FR-4's 20 s pass, 20,000 steps | 162.7 s | 44.1 s | 3.7× | 39–43 s, from 176 s |
| FR-4's 900 s, 900,000 steps | about 6,220 s (estimate) | 453.0 s | about 13.7× | about 14× |
| The 825-node tissue, 2,000 steps | 168.5 s (137.9 s without compile) | 161.3 s (116.4 s) | 1.05×; 1.18× without compile | at most about 1.4× (host share 28%) |

- **Bitwise outputs.** Every world run in both modes has the same final-state and observation
  digests.
- **No handbacks.** No device run handed a window back. Largest ratios: the export 0.068 (`local`),
  as in §1.4; FR-4 3.2e-3 (`local`); the 825-node tissue 9.8e-3 (`global_charge`).
- **Where device mode's time goes.** Analysis (checks and observers) fell from 138.6 s to 1.3 s in
  the export's 80,000 steps. The device checks themselves took 6.1 s over the export's 480,000
  steps (12.7 µs per row). Over FR-4's 900,000 steps they took 88.5 s (98 µs per row): 30% of
  its 289.9 s of steps. That is the largest remaining share, and the batched form of §9.3's
  "later" would reduce it.
- **A retiring composition** (the division set's partition, whose device checks read adjusted rows)
  was run in both modes by the driver at windows of 2 steps, from the gate's snapshot 74ebb91b
  (`stepc/speed/division-retiring/`). That covers `division_quartered` (6 steps, three windows) and
  `division_bridge_quarters` (5 steps, a partial last window). Both are bitwise, with no handbacks;
  their largest ratios are 0.004 and 0.003.
  - A refusal in that branch is not exercised. §3.2's disagreement count for its adjusted rows (E8)
    was dropped.
  - The lead's ruling: device mode is refused for such a composition (§9.2) until a planted test
    exists.
- **The 825-node tissue's checks cost 2.3 ms per row on the device,** against 14.1 ms on the host.
  Its step costs about 51 ms, so device checks save it about a sixth of its warm time. Their
  second compile, 14 s, offsets that over 2,000 steps.
- **The records' host arms were slow.** On these clean cores the host check costs 1.73 ms per row
  for the export, against the record's 6.6 ms. The record's host times were taken on a loaded
  machine on 15 November.
  - So a speedup against a record overstates. The same-core figures are the ones to compare.
  - The two "estimate" cells scale the same-core host arm's cost per row: the export's from 80,000
    steps, FR-4's from its 20 s pass (6.58 ms per row).

## 10. Device row checks on a GPU (D330, 24 November 2026)

**The user's decision (D330):** qualify the device row checks on the GPU under the sparse field
solver, on the production path, family by family, starting with the composite and GJ-N1's field
worlds; then run the field's longest points on the L4.

### 10.1 What is admitted

`row_checks.admit` admits a GPU backend only for a model and field solver listed in
`row_checks.GPU_QUALIFIED`, and only when every ledger of the definition's device checks is among
those measured on the GPU (`gpu_refusal`; the lead's ruling, the finer key). Anything else is
refused by name with today's message ("qualified on the CPU only for ..."); a composition with a
live retiring operator stays refused on any backend.
- **Listed:** `resolved_pump_composite@1` under `sparse_capacitive_reduction_gauged_damped_newton@1`,
  for the ledgers of GJ-N1's worlds: local, outside, total, charge, electrode, global_charge,
  energy, reservoir_work, electrode_work and metabolic_work (with the domain and dissipation
  checks).
- **Why per field solver:** the check program differs by field solver. Under the sparse ID the
  capacitor products are its pairwise folds; under version 2 they are a dense product.
- **Not listed:** version 2 and version 3 on any model, and every other model. Their GPU spread is
  unmeasured.
- **Deterministic ops are required** (`row_checks.deterministic_ops`; the lead's ruling, D335). On a
  GPU, XLA adds scatter-adds atomically, in an order that varies between runs, and the composite's
  operators accumulate with them. Block 2 found host and device mode differing in the amounts and the
  operators' ledgers, while the sparse solver's field arrays (no scatter) agreed. So admit refuses GPU
  device mode unless XLA_FLAGS sets `--xla_gpu_deterministic_ops=true`. That check is a tripwire: it
  reads XLA_FLAGS when admit runs and cannot see what XLA itself parsed. The guard is the bitwise
  evidence of G1 and G6 under the flag. In the installed XLA the flag "guarantees run-to-run
  determinism on GPU", and its deterministic mode disables timing-based autotuning.

### 10.2 The criteria

Fixed before any production-path run on the L4 (`/mnt/workspaces/Cells/fr17-sparse-20261123/gpu/
GPU_CRITERIA.txt`, approved by the lead). On GJ-N1's 25 × 25 field at D = 0 (dt 1/8 s) and
D = 1e-13 (dt 1/128 s), with `validation/execution/gpu_row_checks.py`:
- **G1 (C1):** 8 windows of 32 steps per D, host mode then device mode in one process; every array
  identical by bytes.
- **G2 (C2):** for each window the device decides and each ledger, the spread |host ratio − device
  ratio|, both ratios |residual| / bound over the window's rows, the host's from the model's own
  NumPy ledger functions. As amended before any L4 measurement (the lead's ruling): each ledger's
  largest spread on the L4 is at most min(0.4, max(0.1, 1.5 × the CPU's on the same definition)).
  The GPU must be no worse than the CPU-qualified device mode, and the cap of 0.4 keeps every
  decision safe: a window the device accepts at 0.5 lies at most 0.9 of its bound on the host. The
  first declared bound, 0.1, failed on the CPU itself. In the field's first window the bound is still
  the bare atol at steps 0 and 1, and the rounding noise of a 625-cell global sum is a large fraction
  of it: the "total" ledger read 0.281 on the host and 0.088 on the device (a spread of 0.194),
  falling to at most 0.003 from window 2.
- **G3 (C3):** the GPU rows (`CELLS_TEST_GPU=1`) of `test_window_row_checks.py` and
  `test_window_row_checks_composite.py`.
- **G4:** 20,000 steps at D = 1e-13 in device mode: no refusal, G2 on every 50th window, and the
  handback rate reported.
- **G5–G7 (reported):** memory, a second-process repeat, and the production path's ms per step.

**The CPU criterion did not fit these worlds.** The device-check tests' criterion
(`tests/window_row_check_fixtures.agrees`: 2% of the smallest bound, the material floor taken as 2%
of the material atol) fails on GJ-N1's large-amount worlds on the CPU already, under version 2 as
under the sparse ID, in `max_global_balance_error_fmol`. On the line at D = 1e-13 (12 steps), host
and device read 7.4e-20 and 1.1e-19 fmol in its first window, against a floor of 2e-22. These
worlds' bound is dominated by its rounding allowance on large amounts, so the residual is rounding
noise from two summation orders. In units of the bound the spread was 0.022 for "total", against
the band of 0.5. That is a gap in the CPU qualification's criterion, not in the code: G2 is stated
in units of the bound, and the old criterion's results are reported beside it.

### 10.3 The evidence

**Block 1, the host core (12:48–12:54 UTC; `gpu/block1/`).** It asked why the field stepped at
21.2 ms on the L4 on 23 November and at 13.1 ms the next night, with the same driver, world and
field solver (version 2, D = 1e-13, the vector path, the host thread on CPU 6).
- **The program is identical.** The traced programs and their constants are byte-identical between
  the two snapshots (31fde682 and 044f07e6), and so is the device's peak memory.
- **The host core sets the step.** The L4 step on this path is bound by its host thread, which
  launches every kernel and waits on the device (its CPU time equals its wall time). Three arms, one
  process each:
  - snapshot 31fde682, CPU 6's hyperthread sibling (CPU 22) 15% busy: 15.6 ms per step, a 60 s
    compile, 2.0 s of window preparation;
  - snapshot 044f07e6, CPU 22 fully busy with another process: 19.3 ms, 88 s, 3.1 s;
  - snapshot 044f07e6, a busy loop on CPU 22: 20.3 ms, 97 s, 3.3 s.
  - A busy sibling slows the step about 1.3×, and compile and preparation about 1.5×. The 21.2 ms
    run has that profile, and the 13.1 ms run had both CPUs quiet.
  - **So an L4 run's host thread needs a whole physical core,** its sibling idle.
- **The kernels differ between processes.** With metadata and source tables removed, the optimized
  HLO of the window program (2.7 MB) differs in 16–27 lines between any two processes, one snapshot
  or two. Each difference is a reduction that XLA's autotuner emitted either as a Triton kernel or
  with its native emitter (24, 24 and 5 Triton fusions in the three arms). Some are f64 reductions,
  so an unpinned rerun may differ at rounding. The autotune results can be pinned
  (`--xla_gpu_load_autotune_results_from`): registered L4 runs load a fixed file (the lead's ruling).

## Sources

- **Code** at 3c10b833:
  - `src/cells/execution/vector_windows.py`, `windows.py`, `runner.py` (`_window_rollout`, `_segment`,
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
