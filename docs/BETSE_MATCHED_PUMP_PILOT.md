# Matched Cells–BETSE pump–leak pilot

2026-09-16, D117 / REF-005c. **Registered numerical pilot design, not a result.**
The prerequisites are the [bounded production-family acceptance](../reports/SPEC010_FAMILY_CLOSEOUT.md)
and [independently closed native lifecycle](../reports/REF005B_PUMP_LOOP_CLOSEOUT.md).
The machine-readable contract is
[`pump_matched_pilot/protocol.json`](../validation/betse/pump_matched_pilot/protocol.json).

## Question and scope

Do the unchanged production kinetic finite-bath model and the unmodified pinned
BETSE FULL INIT loop represent the same short pump/passive trajectory, after
explicitly matching preparation, ownership, boundaries and physical time?

Use the supported seven-cell, thirty-membrane-face fixture for **1 ms**. This is
not an organ, equilibrium, resting-potential fit, experimental benchmark or
general BETSE parity claim. No production equation, integrator, biological
parameter or upstream source is changed. Stable 0.14.0 and accepted development
0.15.0.dev0 stay preserved; the working family remains 0.16.0.dev0.

The six controls are pump+leak, pump only, leak only, both blocked, half pump
density, and closed cluster boundary. No channels, junction transport, ECM,
intracellular compartments, dynamic metabolic pools, fluid flow or deformation
are enabled. Only matched physical constants are tested in this pilot.

## Preparation is data, not a new model

Map the audited native initial records into the public `finite_extracellular@2`
schema. Use actual per-cell volume, full membrane area, capacitance and measured
initial voltage. Preserve the tiny native initial charge-cancellation voltage;
do not replace it with an ideal zero or repair concentrations for neutrality.

Na, K and Cl are mobile. The native Ca/P/M species are immobile in this fixture;
carry their measured charge as explicit fixed charge. The outside owner is one
well-mixed **6.75 pL effective bath**, not thirty independently evolving copies
of the configured per-face volume. ATP/ADP/Pi and kinetic constants stay explicit
maintained inputs, with capacity expressed in the production schema as extensive
fmol cycles/s.

For closed boundaries, integrate only unmasked transport area. Scale effective
passive permeability and pump density by the active-area fraction, but retain
**full membrane capacitance**. This whole-cell aggregation requires identical
concentration/voltage on every face belonging to a cell; reject heterogeneity
instead of averaging it silently. Resolved membrane dynamics require a later
model and validation gate.

The first phase checks all **48 saved native interval-start states** on NumPy,
eager JAX and compiled JAX: **144 RHS evaluations**. Compare applied extensive
rates and a prescribed single held-flux transfer, including outside ownership
and voltage. That transfer check is not a claim to run the production RK4
integrator. These are separate preparations, not trajectory state assimilation.

## Registered trajectory matrix

| Component | Per control | Total |
| --- | --- | --- |
| Native FULL INIT | 25 / 12.5 / 6.25 µs, each observed and unobserved | 36 runs / 18 exact pairs |
| Cells ordinary runner | Compiled 50 / 25 / 12.5 µs; eager 50 µs | 24 trajectories |
| Complete checkpoint/restart | 25 µs run, checkpoint at 0.5 ms | Six exact full-state suffixes |
| Independent scalar reference | DOP853 base/tight plus Radau | 18 solves |

Use actual elapsed times **0, 0.25, 0.5, 0.75 and 1 ms** for trajectory/error
comparisons. Native raw sample labels do not equal elapsed completed-update
times; retain both and match the latter. An interval-start flux is not mislabeled
as a recomputed completed-state flux.

The independent scalar equations are reused from the separately qualified
NUM-011 reference, with a new bounded integration/recording wrapper. They import
neither simulator nor JAX. Use float64 adaptive DOP853/Radau, not a claimed
high-precision ODE solver. Save all accepted states and 161 common 6.25 µs samples.
The two DOP853 settings change tolerances and maximum step; Radau provides a
different method. Save individual solves before requiring reference agreement.

## Gates and numerical budgets

The order is held-state mapping → independent reference → native/Cells capture
→ saved-result producer comparisons. A failed gate stops the campaign and keeps
its evidence; there is no automatic retry, tolerance adjustment or follow-up.

The machine-readable protocol specifies every budget. Principal limits:

- Held rates: 2e-10 fmol/s absolute + 2e-11 relative; prescribed concentration
  updates: 2e-12 mM + 2e-11 relative; voltage: 2e-10 V + 2e-11 relative.
- Reference agreement across all saved sample points: 1e-11 fmol, 1e-10 pJ,
  1e-9 V absolute. Reference accepted-state accounting is also checked.
- Finest native trajectory versus reference: 1e-7 fmol, 1e-7 pJ, 5e-6 V
  absolute + 1e-5 relative. Cross-engine absolute limits are twice these values.
- All three compiled Cells grids versus reference: active state coordinates
  use 1e-8 absolute in their own units (fmol or pJ) + 2e-7 relative; voltage
  uses 1e-7 V absolute. Eager/compiled agreement is checked separately.
- Each control/engine/quantity must reduce its maximum reference error by at
  least 20% on both refinements, unless the coarser error is already below its
  registered floor: 5e-11 fmol, 5e-10 pJ or 5e-9 V. Keep every coarse result;
  a floor-limited group is not evidence of measured convergence order.
- Cells accounting: 2e-11 fmol material, 1e-20 C countercharge, 2e-8 pJ energy.
  Native conservation includes a declared update-count/initial-inventory float64
  accumulation allowance; this never enlarges rate or trajectory tolerances.
  Finest native energy closure must be within 1e-7 pJ.

The 59 active comparison coordinates are intracellular/outside amount changes,
passive transfers, signed pump cycles and dissipated energy; voltage is checked
separately. Native dissipation is reconstructed from actual applied rates,
interval-start electrochemical potentials and maintained chemical drive. It is
not inferred from the native sodium-rate diagnostic. Native concentration
increments are measured independently of the cumulative transfer ledger.

Production artifacts retain all ten evolving state fields, padding, full layout,
complete checkpoints and ordinary solver diagnostics. The exact restart test
covers all fields, not just plotted voltage. No custom integration path is added.

## Execution, records and next boundary

One detached campaign on CPUs **0–3**, one BLAS thread, float64. Worker limits:
mapping 120 s, reference 120 s, native 300 s, Cells 420 s; **1,080 s total**.
Artifact limits are **64 MiB per file / 512 MiB total**, disk limits rather
than RAM limits. Each Cells run retains its declared 1,024-step / 64 MiB trace
cap. Native and Cells workers run in their separate locked environments.

Freeze and authenticate original evidence, production inventory, new code,
protocol, contracts and test receipt. Save the source capsule, resolved cases,
all native inputs/outputs/histories, reference accepted states, Cells outputs and
restart artifacts, stage logs and a completion or failure receipt. Operational
launcher/runner logs remain separate from the sealed scientific payload.

The handoff is [REF005C_MATCHED_PUMP_HANDOFF](../reports/REF005C_MATCHED_PUMP_HANDOFF.md).
Return after launch; **no automatic polling, audit, regression or next campaign**.
A producer pass still needs a user-requested independent saved-data review.
If closed, the next pump work is a separately designed relaxation/perturbation
scope linked to original measurements; junction correspondence and spatial
composition remain explicit neighboring projects. GPU and multiscale validation
are not implied by this CPU pilot.
