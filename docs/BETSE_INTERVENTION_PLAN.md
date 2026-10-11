# REF-003e: intervention timing before response comparison

2026-09-12, D072. **Design and control-only checks, not a registered or executed
trajectory panel.** [REF-003d v2](../reports/REF003D_CLOSEOUT.md) remains qualified
only for its 1 ms neutral-prepared seven-cell passive/blocked finite-bath fixture.
The [candidate inputs](../validation/betse/intervention_plan.json) and
[source/control review](../reports/REF003E_INTERVENTION_DESIGN.md) define the next
engineering boundary without changing either simulator.

## What the source review changes

The proposed "block and release" is not a drop-in addition to the qualified run.

| Boundary | Pinned BETSE v1.5.0 | Existing Cells | Consequence |
| --- | --- | --- | --- |
| Phase | Scheduled interventions fire only in `SIM`, before transport; REF-003d used `INIT` | Experiment controls already drive the normal runner | Establish a no-intervention SIM-phase bridge first |
| Event clock | Raw label `k N dt / (N-1)`; state before update is at elapsed `k dt` | Event/control time is elapsed integration time | Declare and test the clock conversion; retain both clocks |
| Permeability intervention | Additive, logistic-shaped pulse relative to tissue-default diffusion | Right-continuous, piecewise-constant leak multipliers | Match the prescribed held input first, not unlike input laws |
| Numerical stages | Native event update once before a full native step | One control held across all RK4 stages of an event-split interval | Refine forcing resolution separately from state integration |
| Boundary readout | Saved final current belongs to the preceding step | Observations use the current/right-side control | Compare matching sides, not just matching timestamp labels |

Source anchors are recorded in the review receipt. The main call sites are
[native FULL loop and clock](../upstream/betse-v1.5.0/betse/science/sim.py),
[native event composition](../upstream/betse-v1.5.0/betse/science/tissue/tishandler.py),
[native pulse](../upstream/betse-v1.5.0/betse/science/math/toolbox.py),
[Cells controls](../src/cells/core/schedule.py),
[event grid](../src/cells/core/grid.py), [runner](../src/cells/core/runner.py),
and [RK4 stages](../src/cells/numerics/fixed_step.py).

## Step 1 — REF-003e0: a SIM-phase bridge, with no physical intervention

Implement a separate adapter/preflight before any new capture. Use the same
seven-cell seed, 30 faces, finite bath, Na/K/Cl, auxiliary fixed charges, constant
profiles and disabled mechanisms. Keep the 1 ms horizon and candidate native
25/12.5/6.25 µs ladder. REF-003d sources, protocols and packets remain immutable.

The proposed bridge is explicitly **SIM from the same neutral preparation**:
construct a normal `SimPhase(kind=SIM, ...)`, initialize that fresh model with
`init_core`, and call its unmodified `run_sim_core`. This route still needs runtime
preflight. It is not the standard `SimRunner.sim()` lifecycle, which loads a prior
initialization pickle. Do not load the end of the earlier transient and label it
the same initial condition, or claim physiological equilibration. A subsequent
standard initialization-to-SIM continuation would be a different experiment.

The bridge must establish:

- Native phase settings select the intended simulation timestep, count, sampling
  and output path; no hidden initialization run or changed geometry occurs.
- All actual starting concentrations, charge-derived voltage, diffusion constants,
  mechanisms, temperature, geometry and effective bath match the registered
  preparation, including after `init_dynamics` reinitializes its structures.
- No-event passive and all-blocked SIM runs correspond to the retained INIT
  trajectories at matching native steps. Reuse of old evidence is labelled as
  reuse, not newly executed Cells runs. Try exact numerical-record correspondence
  first; retain and explain any phase differences before registering acceptance.
- Enabled zero-amplitude Na/K/Cl events are a true no-op relative to disabled
  events. This tests the event pathway separately from biological response.
- Each SIM step fires the event handler once before flux evaluation. The read-only
  observer records pre-/post-event state and effective diffusion, then ordinary
  before-/after-update data. Observed/unobserved partners agree byte-for-byte.
- No-event/blocked checks retain material and charge accounting, positivity,
  instantaneous source-law checks and the original refinement/trajectory limits.
  No pump, gap-junction transport, field, mechanics or regulatory process is added.

Use one read-only profiling dispatcher, routing by exact source file and object
identity. A new observer must include the tissue handler; the frozen observer
only sees simulator-method frames. Do not replace methods, rewrite native time
arrays or use a recording hook to apply the intervention.

Only after preflight should a separate protocol freeze concrete run coverage,
initialization identity, test receipts, CPU/time/storage limits and failure rules.
No bridge capture is registered by this document. A successful bridge must be
inspected and independently closed before a response panel is authorized.

## Step 2 — REF-003e1: corresponding suppression and recovery

The first candidate uses the native supported smooth pulse. In the homogeneous
fixture, the tissue-default diffusion equals the baseline diffusion, so:

```text
q(t) = logistic(10 (t-on) / transition) - logistic(10 (t-off) / transition)
availability(t) = 1 + m q(t)
Dm(t) = Dm_base + m q(t) Dm_default
```

Candidate elapsed-time centres are **0.3 ms and 0.7 ms**, with transition parameter
**0.1 ms** and additive multiplier **m = -1** for all Na/K/Cl routes. Set the
native modulator to the literal string `None`; target all faces and verify the
resolved target set. Do not generalize the multiplier equivalence to heterogeneous
tissue defaults without checking each route. Avoid division by a zero baseline
permeability when reporting blocked/immobile routes.

This is strong suppression and recovery, **not an exact square block**. The pulse
is already slightly active at time zero; its named times are transition centres,
not strict onset/offset boundaries. For this candidate the midpoint availability
is about **4.1223e-9**, not zero. Do not demand exact pre-centre baseline history,
clamp tiny values to zero, set transition time to zero, or reinterpret floating
rounding as a hard biological block. Keep a separate constant-zero control to
test exact zero transport. No physics criterion is relaxed: the intended input
law is explicitly different from a square pulse, and is not yet trajectory-qualified.

### Explicit native clock conversion

For `N = int(duration / dt)`, let `gamma = N / (N-1)`. To prescribe the above pulse
in elapsed update time, multiply all three native YAML time fields—`change start`,
`change finish`, **and** `change rate`—by gamma. Then evaluation at raw native
label `gamma * k * dt` corresponds to the intended value at elapsed `k * dt`.
Keep the original labels, mapped YAML parameters and derived elapsed columns in
the packet. This is an explicit adapter input conversion, not an upstream clock
patch or a claim that unchanged YAML times have the same elapsed meaning.

Changing native resolution changes gamma. Without this mapping, refinement also
changes the timing of the imposed experiment. The control-only review compares
the actual upstream function with independent 70-digit arithmetic at all
40 + 80 + 160 native update-start points. Future full-loop observation must still
confirm that the applied diffusion follows this contract.

### Keep input discretization separate from integration error

BETSE samples the pulse once per native step. First compare that explicitly
piecewise-held experiment in both engines. Generate the complete Cells control
schedule from declared inputs **before integration**, independently check it
against the subsequently observed native diffusion arrays, and retain both.
Do not construct a control schedule from native state/voltage trajectories or
fit an input to achieve output agreement.

At a fixed native input-hold interval `h`, use Cells nominal RK4 steps **h, h/2,
h/4** so integration refinement changes the actual grid while leaving the input
history fixed. Copy event times from the same canonical integer-times-step
construction; avoid near-duplicate floating-point times created by different
arithmetic. The existing event grid deliberately preserves exact event times.

Simply retaining the old Cells 100/50 µs nominal steps would not establish
refinement when both are split at every smaller native control interval: they
can become the same effective grid. Record actual grids and reject duplicate
"refinement" paths. Separately refine native/forcing interval `h`; report input
approximation and native integration error distinctly. Matching a held drive is
not a qualification of continuous-time forcing or RK4's order for a smooth input.

The proposed response controls are no-event baseline, enabled zero-amplitude
no-op, static fully blocked, and the declared suppression/recovery pulse. Keep
native rounded and matched constants separate. Freeze the final matrix and
resource budget only after the phase/control adapter preflights.

### Acceptance requirements to preserve and extend

Inherit the numerical criteria in the
[REF-003d v2 protocol](../validation/betse/trajectory_refinement_protocol.json),
without widening tolerances. Add event/control evidence requirements:

- Effective diffusion matches the prescribed control at every native step and
  every Cells control boundary. No unintended ion, membrane, pump or junction is
  changed. Zero-amplitude events leave trajectories unchanged.
- Inventory, charge-derived voltage and transfer ledgers do not jump merely
  because a permeability control is changed. Derivatives/readouts may jump for a
  held input; distinguish left-side, right-side and interval-integrated quantities.
- Require exact zero flux and unchanged inventories only for an actually zero
  control. For the smooth pulse, evaluate the registered nonzero permeability
  law; no invented flat interval or unconditional flux-sign expectation.
- Compare all cell and bath amount changes, voltage, matching-side rates/currents,
  integrated transfers, positivity and material/charge accounting through both
  transitions and recovery. Use the final state but not a fabricated native final
  RHS. Existing observations must not alter integration or controls.
- Preserve observed/unobserved equality, eager/compiled agreement, independent
  state-integration refinement and forcing refinement. A failed gate stays failed;
  new regimes or resource requirements require a versioned prospective protocol.

These are design requirements, not results. Full event target resolution,
configuration loading, SIM initialization, serialization and trajectory response
remain unexecuted by this source/control review.

## Architecture and later work

Keep an experiment's **input law**, **sampling/hold policy**, **solver step grid**
and **observation side** separate. These distinctions matter for future multirate
regions, compartment interfaces, checkpoint continuation and CPU/GPU execution.
The current numeric control arrays and PyTrees already support the first held-drive
comparison; no new production equation or Python callback in a compiled kernel
is needed for that design.

A future continuous-waveform feature should have a general, data-defined input
law, explicit time evaluation at numerical stages, reference tests and restart
semantics. It must not silently change existing right-continuous schedules or
claim fourth-order smooth forcing from a step-held implementation. A literal
square block in BETSE requires its own supported-input contract; restarting
`run_sim_core` in chunks is not automatically equivalent because it reinitializes
dynamics and storage.

No production code, dependency, release, GPU policy or accepted timestep is
changed here. The previous 325-test adapter suite and 4190-test production matrix
are retained, not rerun. Future long tests/captures run detached with durable
receipts; status checks and follow-up audits await user instruction.
