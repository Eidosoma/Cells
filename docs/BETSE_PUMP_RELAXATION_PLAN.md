# Pump–leak: from a short correspondence test to relaxation and recovery

2026-09-17, D122 / proposed REF-005d. **Design only, not an execution
registration or a longer-duration result.** The prerequisite is the
[independently closed REF-005c pilot](../reports/REF005C_PUMP_PILOT_CLOSEOUT.md).
The [machine-readable proposal](../validation/betse/pump_relaxation_plan/proposal.json)
is deliberately non-runnable. It cannot silently extend a horizon or reuse an
old capture's acceptance stamp.

## Questions we must keep separate

1. Do the numerical implementations converge to the same trajectory over a
   longer interval, with unchanged mechanisms and valid domains?
2. Does that physical model actually approach a stationary ionic/voltage state,
   and respond consistently to a controlled perturbation?
3. Does the selected preparation predict independently measured biology?

The 1 ms pilot answers a bounded part of question 1. It is not resting-state
physiology: the saved primary pump+leak reference ends near **−2.13 mV** from
its near-zero initial voltage. Neither that endpoint nor a flat-looking plot
would establish steady state. The older accepted 10 ms Cells family cases have
different preparations; they do not automatically qualify this matched fixture.

## Staged plan

| Stage | Deliverable | Gate before proceeding |
| --- | --- | --- |
| R0 | Bounded, lossless native recording; explicit Cells window/restart correspondence on the matched fixture | Offline exact decode, live observer neutrality, source-bound overlap, measured memory/artifacts and independent review |
| R1 | Six-control 10 ms numerical extension of the same seven-cell preparation | Independent reference agreement, domains, conservation, energy, trajectory/refinement and complete restart checks |
| R2 | Reference-led longer relaxation, initially considering 0.1 and 1 s separately | Registered steady-state residuals/window, justified solver and timestep, convergence and measured resource caps |
| R3 | Pump-availability suppression/release from a qualified state, alongside an unperturbed branch | Declared input semantics, native dispatch/lifecycle preflight, event alignment, full-state recovery evidence |
| B0 | Original-data readiness for a separate biological benchmark | Methods, uncertainty, bath/preparation, chloride mechanism, input/target separation and held-out perturbation |

Each execution is separately registered, detached, bounded and user-polled.
No stage automatically launches the next. R0 changes recording, not model
physics; R1 changes the tested horizon, not the model. R2/R3 cannot inherit an
unqualified timestep, equilibrium detector, native restart or event bridge.

## Why recording comes first

The completed 1 ms native campaign uses approximately **1.47 GiB** on disk.
Its largest observed result is **143,185,735 bytes (136.55 MiB)**. The native
phase took approximately 426.57 s; the independent review took 337.05 s.

At unchanged steps and legacy recording, a deliberately simple linear workload
projection gives roughly **14.74 GiB total / 1.33 GiB for the largest file** at
10 ms, with about **71 minutes native execution / 56 minutes review**. These are
planning extrapolations, **not measured future performance, strict bounds or
ETAs**. Even this projection exceeds the existing 256 MiB/file and 2 GiB capture
limits. Additional timestep refinement would increase work and storage further.
These costs include native observation/JSON recording and a high-precision
external audit. They are **not Cells kernel benchmarks or GPU speed estimates**.

Splitting a large JSON trace into files bounds individual files, not aggregate
disk use. A compact lossless representation must remove repeated metadata and
use bounded numeric records, or demonstrate another evidence-preserving saving.
Compression ratio, total bytes, Python buffers and whole-process RSS must be
measured independently. The current observer's `steps`/`raw_steps` lists and
BETSE's own histories also need inspection: streaming the final file does not
by itself bound either simulator's live memory.

The proposal carries **no approved runtime or aggregate artifact cap** for the
new run. Register those after measuring the new recording path; do not silently
inherit the old 21-minute or 2 GiB bounds, or treat available disk as permission
to consume it. Reducing scientific checks or increasing timesteps is not a
storage strategy.

## R0: reusable recording contract

Implement a versioned adapter-side record sink, separate from physics and solver
choice. Reuse the existing complete-state and observation contracts where they
fit; do not invent a test-only Cells integration path.

- Store static geometry, species/layout, model settings and source identities
  once. Typed float64 payloads retain signed zero and exact numeric bytes.
- Each dynamic record names run/cell/face ownership, global step index, phase,
  raw native label and physical before/after time. Preserve ordered live calls,
  arguments/returns, applied flux and the three physical update boundaries.
- Flush complete bounded chunks through a non-mutating sink. A **32-step / 8 MiB
  chunk** is a starting engineering target, not an accepted capacity guarantee.
  Release flushed buffers; never accumulate a horizon-length index in memory.
- Use an append-only hashed index and publish the final manifest last. Refuse
  duplicate/missing/reordered steps, corrupt or nonfinite values, torn payloads,
  incomplete call pairs and incompatible schemas. Failure preserves partial
  evidence without publishing a successful run.
- Retain native histories/final arrays and read-only observer lifecycle controls.
  Native pickle files remain hashed, not loaded or assumed restart-compatible.

First qualify the codec **offline against every saved D119 record**, with exact
canonical reconstruction including signed zero and all nested fields. Then
register a live **same-1 ms, same-six-control, same-three-grid, observed/unobserved
36-run** replay against the preserved evidence. The live gate tests hook order,
observer neutrality and resource use, not only serialization. Original frozen
producers and archives remain unchanged; a new format uses a new adapter/schema.

On the Cells side, use the ordinary [windowed execution](WINDOWED_EXECUTION.md)
path and complete checkpoints. Existing kinetic-family window tests are useful
prior evidence, not a substitute for this matched seven-cell fixture. Compare
full/windowed outputs, diagnostic maxima and checkpoint suffixes across several
window sizes, eager/JIT paths and observation policies. No checks may disappear
when observations are sparse. Saving fewer outputs must not reset cumulative
transfers, dissipation, gates or input-clock state.

## R1: explicit 10 ms candidate matrix

Keep all geometry, chemistry, fixed charge, maintained ATP/ADP/Pi, temperature,
boundary controls and physical constants from the closed pilot. In particular,
the shared finite bath remains finite; it is not replaced by an experimental
solution recipe or maintained reservoir to improve agreement.

| Component | Proposed scope |
| --- | --- |
| Native | 6.25 / 3.125 / 1.5625 µs; six controls × three grids × observed/unobserved = 36 runs |
| Cells | Compiled 50 / 25 / 12.5 µs plus eager 50 µs = 24 trajectories |
| Independent reference | Original DOP853 base/tight and Radau settings = 18 new solves |
| Shared observations | Every 0.25 ms from 0 through 10 ms: 41 points, including all old 1 ms observation times |
| Complete Cells restart | 25 µs trajectory, 5 ms checkpoint: six full-state suffixes |
| Candidate work | 67,200 observed / 134,400 total native updates; 9,600 primary Cells updates plus 1,200 restart-suffix updates |

These are **candidate grids**, not a claim that the finest native step remains
adequate at 10 ms. Reference/domain scoping precedes registration. If necessary,
propose a finer ladder explicitly before execution; do not automatically rerun
or loosen a criterion after rejection. Longer accumulated energy error is not
licensed merely because the shorter trajectory passed.

Carry forward the exact D119 trajectory, reference-agreement, mapping,
refinement and accounting criteria. In particular, native finest energy closure
stays **1e-7 pJ**, and the floor-aware 20% successive contraction rule remains.
Keep coarse failures visible. Native material roundoff retains its declared
step-count/inventory allowance; it never becomes a rate or trajectory allowance.
Extend reference call/step/output budgets explicitly if scoping justifies it;
do not infer that the old resource cap covers ten times the work.

The first millisecond is an overlap control for **physical state and transfer
history at matching completed-update times**. Changing the total native horizon
changes BETSE's raw sample labels (`k*T/(N−1)`), even at unchanged `dt`. Do not
demand equality of different raw labels, equate them to elapsed time, or hide
an actual physical-prefix difference behind that labeling distinction. Fixed-
mesh physical prefixes should reproduce; independently adaptive reference
prefixes must meet the registered agreement limits, not a bitwise promise.

Every trajectory records positivity/domain checks, material/charge/energy
balances, solver controls and maxima, not just the final voltage. Native
interval-start work and dissipation retain their definitions. No convex-remainder
subtraction, parameter fitting or source-error mimicry is permitted.

## R2 and R3: steady state and recovery are new scientific gates

Use saved states plus independent RHS/residual evaluation to distinguish fast
electrical adjustment from slow ionic redistribution. A stationary voltage can
coexist with changing Na/K/Cl pools. Require small **net rates for every cell
species and every bath species**, small net membrane current, small voltage
drift and small inventory drift over a fixed observation window, together with
positive domains, conservation and independent refinement.

Register exact dimensional/relative thresholds, reference scales and the window
length **before** claiming relaxation. They are intentionally unresolved until
the longer reference/domain study, not borrowed from experimental uncertainty.
Report both the largest absolute residual and its tolerance ratio; do not hide
an unconverged ion behind a small net charge residual. A pump-driven stationary
state can retain nonzero gross pump/leak fluxes, maintained work and dissipation.
The both-blocked control's trivial stationarity is not biological validation.

A direct stationary solve is a possible cross-check, not a replacement for a
trajectory, its basin of attraction or stability checks. Implicit/stiff,
multirate or reduced methods are later numerical choices requiring conservation,
domain and convergence qualification. Do not switch methods or increase `dt`
merely to reach a longer horizon cheaply. The initial 0.1/1 s suggestions are
separate bounded candidates, never an automatic march to thirty minutes.

For recovery, first propose pump-availability suppression and release from the
same complete qualified state, with an unperturbed branch control. Keep ions,
all transfer/energy histories and maintained-reservoir assumptions intact.
Choose amplitude and schedule prospectively; source SIM dispatch and stored
state semantics need their own preflight. Bath substitution is a distinct
experiment requiring explicit reservoir/material/charge/work accounting, not an
in-place overwrite of finite-bath concentrations. No perturbation is executed
or biologically calibrated by this plan.

## Biology and multiscale architecture

The [original-data benchmark plan](BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) remains a
separate track. Original methods, uncertainty definitions, preparation, chloride
transport and calibration/held-out separation must be resolved before a
biological registration. The existing Costa/Xenopus record is a candidate, not
the model's current bath recipe or an accepted experimental target. No new
literature review or biological tolerance is claimed here.
Data-readiness work can proceed alongside the numerical stages; it need not
wait for every simulator feature or for a long relaxation run.

For Cells, recording policy, integration window, spatial resolution and device
remain independent settings. Keep array kernels pure and perform host I/O at
window boundaries; the native Python observation hook is not a GPU-kernel
architecture. Windowing bounds retained history but does not reduce integration
work or itself implement multirate stepping. Later coarse/fine regions and
inter-organ ports must exchange declared amounts, charge, energy and volume
conservatively, with device and coupling accuracy measured separately.

**Next implementation:** the offline lossless native-record codec and bounded
sink tests, followed by an explicitly registered live observer-parity preflight.
Neither this design nor pilot closeout launches a long simulation, another
audit, optimization campaign, biological fit or GPU job.

## Design verification

**35 design/evidence checks pass in 7.25 s**; see
[the software receipt](../reports/ref-005d-plan-checks-01.xml).
The saved-data [planning record](../runs/ref-005d-planning-2026-09-17/design-01/plan.json)
binds the proposal, exact inherited scientific limits, source identities, matrix
counts and measured-versus-extrapolated resource figures. Its completion digest is
`db57a5c3fb2219e7dd03b885485888d798b2cc63d9473ee639540bdd4a4142cb`.
The status is `pilot_closeout_verified_longer_scope_design_only`: no trajectory,
reference solver, high-precision audit or longer-duration experiment was rerun.
