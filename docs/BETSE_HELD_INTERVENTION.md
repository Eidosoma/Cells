# REF-003e1: prescribed suppression and recovery

2026-09-12, D079. This is a control-design/compiler slice, not a registered
trajectory. It extends the frozen [D072 input-law design](BETSE_INTERVENTION_PLAN.md)
after the expanded no-op SIM bridge passed its independently executed
[joint closeout](../runs/ref-003e0-expanded-audit-2026-09-12/audit-01/completion.json):
1,232,616 comparisons and 433 tests in 167.679 s. Its scope remains 1 ms,
seven cells / 30 native membrane faces, two F/R profiles and three timesteps,
with zero-amplitude events only. Historical capture/prelaunch receipts stay frozen.

## First response panel

Keep the same finite shared bath, neutral preparation, geometry, concentrations,
passive Na/K/Cl transport, disabled pumps/channels/junctions and CPU/float64.
Use fresh SIM preparation, not an equilibrated state or a loaded INIT pickle.
Enable only the default tissue profile, with all 30 faces targeted where events
are enabled. Homogeneous targets correspond to all seven Cells membranes.

| Condition | Native configuration | Cells effective control |
| --- | --- | --- |
| Baseline | Default profile enabled, no scheduled event | Availability 1 |
| Zero amplitude | Same preparation, enabled Na/K/Cl events with multiplier 0 | Availability 1 |
| Static blocked | No scheduled event; base/default mobile diffusion zero | Availability 0 throughout |
| Suppression/recovery | Normal base diffusion; enabled Na/K/Cl pulse with multiplier −1 | Prescribed availability `1 − q(t)` held per interval |

The proposed first capture is **8 native runs and 24 Cells runs** at matched
F/R constants and a 25 µs hold interval over 1 ms. Four native conditions each
have observer-off/on partners: 160 observed steps. Cells runs each condition
with eager/compiled JAX and solver steps h, h/2, h/4. No new solver family,
mechanism or production dependency is needed.

Retained default-profile passive/blocked and zero-amplitude passive records
provide exact native numerical overlap targets. New schedules and output grids
are not byte-identical to old Cells definitions; do not demand whole-record
equality. Compare common physical samples or appropriate rate/transfer records.

This is a **pilot**, not native-timestep convergence evidence. Before a capture,
separately preflight the actual nonzero event handler, prepare control-aware
capture/checking code, and register exact definitions, observations, tolerances,
source hashes and prospective resource bounds. There is no executable capture
launcher in D079 and its control-probe limits do not authorize a simulation.

## Input law, composition and numerical scale

Retain the D072 pulse: logistic difference with centres 0.3 and 0.7 ms and
transition parameter 0.1 ms. The gain is `10 / transition`, not `1 / transition`.
Availability is positive even at maximum suppression (about 4.1223e-9), has
nonzero tails at the start/end, and is not an exact square block. “Recovery”
here means restored permeability, not return of voltage, concentrations or a
biological state to their original values. The finite bath retains history.

The native handler assigns `Dm_scheduled = multiplier * q * Dm_default`, then
forms `Dm_effective = Dm_scheduled + Dm_base`. Cells multiplies passive
permeability by its availability. Their mathematical correspondence requires
the homogeneous fixture's `Dm_default == Dm_base` and `Dm = P * thickness`.
Do not assume this mapping for heterogeneous profiles, multiple interventions,
different tissue defaults or future spatial modulation.

Compile Cells controls from declared inputs using independent 70-digit decimal
arithmetic before any trajectory. Do not extract or fit controls from native
state, event histories, or measured response. The control probe calls the
actual pinned BETSE pulse and then evaluates its source-order additive
arithmetic. That is **not** an event-handler or target-selection execution.
The later preflight must check actual `Dm_base`, `Dm_scheduled`, `Dm_cells`,
target indices, scalar/modulator values, and all disabled controls.

Addition near cancellation and multiplication need not give bitwise identical
floating-point values. Gate their absolute diffusion difference divided by
the **positive unsuppressed diffusion baseline**, at the existing dimensionless
2e-14 control tolerance. Never divide by the tiny suppressed residual, and
require exact zero for the immobile species and the permanently blocked case.
This control-unit criterion does not relax any physical trajectory tolerance.

## Four separate clocks/contracts

1. **Input law:** the continuous mathematical pulse specifies values only.
2. **Hold policy:** sample at `t_k = k*h`, then hold `u_k` on `[t_k, t_(k+1))`.
   Native raw labels come from `linspace(0, N*h, N)`. Scale all three YAML
   pulse-time parameters by `N/(N−1)`; do not patch the native clock. Save both
   raw labels and elapsed update times.
3. **Solver grid:** Cells subdivides each held interval into 1, 2 or 4 steps.
   Generate boundaries as integer products of the same binary64 h, not by
   cumulative addition or independently rounded decimal timestamps. The actual
   production EventGrid must contain exactly N, 2N or 4N intervals, with no
   microscopic extra steps. All RK4 stages of a step retain its interval's
   control, including the stage at its right endpoint.
4. **Observation side:** state, rate and accumulated transfer have distinct
   meanings at a boundary. Label them explicitly; do not infer them from time
   labels alone.

| Recorded quantity | Boundary interpretation |
| --- | --- |
| Amounts, voltage, accumulated ledgers | Continuous across the control dispatch itself; record/check pre/post dispatch |
| Fresh instantaneous rate at `t_k` | Right-side control `u_k` on the state at `t_k`; previous interval's endpoint stage used `u_(k−1)` |
| Native stored membrane flux/current | Flux actually used for the preceding update, with its saved evaluation state/control; not a fresh RHS on the resulting endpoint state |
| Interval transfer | Match signed ledger differences over the same interval and include the shared bath |

Generate N control records at `0, h, …, (N−1)h`, **no new event at T**. The
last held control persists through the terminal readout. The native last raw
label is T but its last input represents elapsed T−h. Evaluating a fresh pulse
at T in Cells would silently introduce a different final-rate contract.
Even with this endpoint convention, native stored final current must not be
compared directly with a fresh Cells endpoint RHS: the evaluation states differ.

The existing production parser, numeric control arrays and EventGrid can
express this contract. The control-only probe checks all four conditions at
25/12.5/6.25 µs and all three subdivisions, including `nextafter` on the left
of every interior control boundary, exact boundaries and the terminal value.
It checks all active membranes and zeroed padding/pump/channel/junction fields.
It does not execute eager/JIT integration or qualify GPU behavior.

## Response gates and later expansion

Keep the original [trajectory criteria](../validation/betse/trajectory_refinement_protocol.json)
and their independent arithmetic basis. A control-aware checker must use each
interval's declared **and observed** effective diffusion; the frozen constant-
permeability checker and no-op observer assertions cannot be applied unchanged.
Do not edit those accepted checkers into accepting a new experiment.

Before accepting a response, require:

- Actual targets/controls agree with the prescribed law and source composition;
  only intended mobile permeabilities change at event dispatch. State and
  accumulated transfers do not jump. Preserve native flux-call nonce semantics.
- Observer-on/off results agree; zero-amplitude and no-event controls agree;
  static blocking gives exactly zero transport. Pulse transport need not be zero.
- Every saved flux/current/state/transfer link passes independent, control-aware
  arithmetic; all amounts stay valid, and cell-plus-bath inventory and charge
  budgets close with their unchanged unit-specific tolerances.
- Eager/compiled Cells paths agree, and Cells refinement at **fixed h** passes
  the original criteria. Compare matched state increments and ledgers, not only
  large absolute inventories or visually similar voltage curves.
- Separately expand h to 12.5 and 6.25 µs with solver-refinement partners. Native
  refinement changes both its integration and held input. Report that combined
  change separately from fixed-input Cells solver refinement; use fine Cells
  results across h to assess sensitivity to the hold policy. Do not call this
  isolated native-solver error or assume fourth-order accuracy for sampled forcing.
- Later restore the separate source-constant profile and independently audit
  the saved panel. A one-h pilot alone does not close the full REF-003e1 gate.

No continuous stage-evaluated forcing, active physiology, biological recovery,
longer horizon, restart, tissue/organ or GPU qualification follows from this slice.
No acceptance threshold is fitted to observed pulse trajectories.

## Engineering consequence and next step

Keep this input compiler in the optional reference adapter. General simulator
interfaces remain model state + numeric controls + solver schedule + explicit
observations/accounting. This separation also suits future batched GPU work:
precompute host-side schedules and transfer bounded numeric arrays, with no
BETSE callbacks or per-step Python dependency inside compiled kernels. It is
an architectural compatibility argument, not a speed or memory measurement.

The next bounded step is **actual nonzero SIM preparation/dispatch preflight**:
check source-order composition and unchanged physical state at selected pulse
times using a fresh native phase. Then implement/register the 8+24 response
pilot with a control-aware observer/checker and resources based on measured
preflight costs. Any long capture or follow-up audit runs detached with durable
failure/result artifacts under [AGENTS.md](../AGENTS.md); return for user polling,
with no automatic expansion, retry or follow-up audit.

See the [data-defined plan](../validation/betse/held_intervention_plan.json),
[compiler/probes](../validation/betse/held_intervention.py), and
[control-design report](../reports/REF003E1_CONTROL_DESIGN.md).
