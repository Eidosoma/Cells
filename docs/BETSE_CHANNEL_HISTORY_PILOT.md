# REF-004c: paired coupled history pilot

D099, 2026-09-15. The user explicitly requested preparation closeout, paired
references, and a detached coupled run. D098 closes the saved D097 preparation;
its original receipt remains unchanged. This contract registers **one workflow
with a mandatory reference gate before either simulator**. A failed gate stops
the job; it does not trigger new settings, a retry or a larger horizon.

## Fixed physical question

Do the active a/b initial settings, with equal initial voltage, amounts, open
fraction and current, evolve into reliably different coupled responses? Can
both independently evolving engines approach the same continuous references?
Pair a is m=0.2/h=0.6; b is m=0.6/h=0.2. Keep separate zero-permeability a/b
controls: their gates change but their inventories/voltage must not.

Reuse the audited seven-cell / thirty-face geometry, one finite shared bath,
matched F/R, 298.15 K, and the K-only Kv1p5 channel. Na/Cl and auxiliary fixed
charge remain explicit. No background leak, pumps, GJs, other chemistry,
intervention pulses, geometry changes, noise, flow or GPU execution. Gate
settings are explicit data, not a simulated biological preparation history.

Existing production remains unchanged. The native adapter uses the existing
FULL INIT loop, one-time fixture hook, read-only observer and post-hoc fresh
flux probes. The new normative fixture expectation derives only declared m/h
and their product; original observed data are never rewritten or represented
as a capture of the new b setting. No module-global monkeypatch changes a
simulator or its reference. Cells uses its existing checked RK4/full-state
runner, not native post-gates supplied as a trajectory forcing.

## Step 2: reference gate and conditional horizon selection

The candidate horizon is **2 ms**, with common observations at 0, 0.25, 0.5, 1
and 2 ms. D095 qualifies the old constant-control regime and D097 establishes
initial-rate/grid eligibility; neither proves the new paired trajectory. The
candidate is selected only if this actual reference gate passes:

- Twelve fresh independent solves: active/blocked × a/b × base/tight DOP853
  and Radau. Reuse the original registered precision, tolerance, max-step,
  6.25 microsecond sample grid and per-solve resource bounds from
  [D095](../validation/betse/channel_feedback_pilot/protocol.json), now with
  explicit initial gates. Both algorithms use the pinned SciPy 1.18.1 runtime;
  they are not independent libraries. Integration is float64, not 80-digit;
  the independently specified RHS uses 80-digit arithmetic.
- Separately reconstruct saved readouts, dense polynomials and thermodynamic
  balances with D096's audited mathematics. Check blocked analytic m/h
  exponentials with each declared initial setting, complete state axes,
  accepted/sample clocks, positivity and voltage/gate domains. No simulator
  or definition compiler supplies the reference dynamics.
- Require the original method/tolerance agreement budgets at all registered
  samples. Require identical initial non-gate readouts between a and b.
- At 2 ms, require active a/b voltage separation of at least **100 microvolts**
  and open-fraction separation of at least **0.005 in every cell**. These are
  prospective signal gates, not targets used by the dynamics or fitted values.
  Do not substitute the initial derivative witness for integrated evidence.
  Blocked voltage separation is exactly zero.

All reference records and gate receipts are durable. Hash-bind them before
allowing native/Cells workers; verify them again before each worker and at
completion. Reference failure prevents either simulator from launching.
This establishes sampled numerical agreement, not a rigorous ODE error bound
over every real time or a long-time/stiff-regime guarantee.

## Step 3: detached own-state paired comparison

Four conditions × native 25/12.5/6.25 microseconds × observer on/off:
**24 fresh native runs / 4,480 updates / twelve observer pairs**. Four conditions
× Cells JIT 50/25/12.5 microseconds plus eager 50 microseconds: **16 complete
trajectories**, plus **four checkpoint-resumed segments** from 1 ms on the
25 microsecond grid. Preserve **24 complete checkpoints / 1,296 arrays**.

Reuse D095's per-history absolute/relative numerical budgets, conservation
roundoff policy, refinement ratios/floors, and eager/restart criteria unchanged.
Check all full-loop native boundaries, complete Cells histories, fresh versus
interval currents, six-species native charge/inventory accounting, one-owned
cell/bath transfers and nonnegative dissipation. Initial-state checks must use
the actual a/b gates, never the old implicit a default. Replay complete numeric
checkpoint state/layout contents with the existing safe decoder and compare
full resumed histories/observations.

Require each engine's finest grid to meet its continuous reference and the
original own-refinement policy. Retain every coarse diagnostic failure; do not
require the new count to equal the old fourteen or relabel misses as passes.
Reference/roundoff-limited cases are explicitly labelled, not evidence of an
observed RK4 order. Preserve all earlier passive and coupled failures/limits.

Additionally compare signed **a minus b** histories at common observations:
native versus reference and Cells versus reference receive **twice** the
per-trajectory budget, since each contrast subtracts two trajectories. The
cross-engine contrast receives **four times** that base budget. These are
prospective propagated error budgets, not relaxed single-trajectory criteria.
Require identical initial non-gate simulator readouts within each active/blocked
pair. Native energy is not invented from an unavailable native energy export.

## Bounds and execution policy

Bind D098 closeout, all original inputs/evidence, new software checks and the
source capsule before one fresh output directory. All accepted 352 implementation
files / 51 production modules remain unchanged. Sources used for a completed
review or registered run are frozen; corrections require a new version.

CPUs 0–3, **1,200 seconds total**, with worker caps of **240 seconds reference /
360 seconds native / 480 seconds Cells**. Aggregate artifact cap **512 MiB**;
individual/decoded record cap **128 MiB**. Existing 64 MiB trace reservations and
1,024-step limits apply to each Cells definition. Artifact caps are not RAM caps
or performance predictions. The full new panel's runtime is not extrapolated
as a measured speed from prior setup/JIT costs.

The user authorizes the reference-to-simulation gate as part of this job.
Launch detached and return; no assistant polling, retry, GPU work or automatic
post-capture audit/regression. Any capture pass remains
`paired_capture_pass_pending_audit`; independent saved-data closeout is a
separate next step. No biological, channel-family, native-restart, whole-organ
or multiscale-accuracy qualification follows from a raw pass.

This exercises existing multiscale boundaries: locally owned gate history,
conservative transfers, same-stage shared-bath reductions and observations
outside dynamics. Independent worlds are a future batch axis; cells within
one shared bath are not independent jobs. No new production framework is needed.
