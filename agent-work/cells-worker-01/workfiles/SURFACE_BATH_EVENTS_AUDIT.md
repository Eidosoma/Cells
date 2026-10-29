# Scheduled ideal-reservoir bath events

Purpose: resolve the concrete mismatch between literal native concentration
setters and Cells' immutable reservoir/charge/work accounting. This is a new
controller physics claim; the independent reference checks that claim separately
from source compatibility. Numerical qualification is pending.

## Native source and admission

The pinned BETSE1.5.0 checkout/revision/source hashes are declared in
`validation/transport/betse_environment_transport_protocol.json`. The static
receipt linked by `surface_bath_events_workqueue.json` authenticates the bath
handler, simulation caller and pulse helper against that existing contract.

- Native ECM assignments execute K, then Cl, then Na. K writes K/M, Cl writes
  Cl/Na, and Na writes Na/M. Every write uses the original baseline; later
  counterion writes replace earlier ones. Overlaps may therefore be charged.
- Only the Cl setter has an ion-enabled guard. The simulation caller fires
  events only in SIM. Logistic tails need not vanish at t=0 or at the horizon.
- Native non-ECM setters replace entire concentration rows without counterions
  and use legacy attributes that can be absent. They are outside this family.
- Cells admits ordered phase-local windows and strictly positive resulting
  concentrations, with a conservative all-pulse positivity bound and each
  active transition resolved by at least8 steps. These are Cells admission
  restrictions, not claims about native validation. Signed amplitudes are kept.

Only declared ideal reservoirs can be targeted. Their volumes and boundary
voltages remain fixed. Each target uses its own original concentration as an
explicit replicated native baseline; uniform targets reproduce the native
single global baseline. There is no generated spatial grid. Real Na/K must
have valence+1 and real Cl/M valence-1 for enabled setters. Disabled Cl needs
neither its ion nor its counterion. No charge-neutralizing overwrite is added.

## Explicit physical controller

Let `N0` be each original reservoir amount and `d(t)=V*(C_program(t)-C0)` the
ordered-setter dose in fmol. The original amount, charge and fixed-background
anchors are never changed in a saved layout. The instantaneous parent field
receives actual current amounts `N0+d` and ionic charge `q0+F*1e-15*z*d` in a
temporary read-only input view. This supplies actual physics to its existing
solver; it is not an accounting rebase.

All original12 passive or19 complete ionic saved arrays retain **transport
contributions**. A saved phase clock determines the separate prescribed dose.
The physical state and observations explicitly add:

| Quantity | Programmed controller contribution |
| --- | --- |
| Extracellular amount increment | `d` |
| Reservoir supplied amount | `d` |
| Electrode charge transferred | `-Q`, with `Q=F*1e-15*sum(z*d)` |
| Reservoir electrochemical work | `G_program + 1e12*phi*Q` |
| Electrode work | `-1e12*phi*Q` |

`G_program` is the fixed-volume ideal-mixture free-energy change from `N0` to
`N0+d`, evaluated with stable logarithms against the original anchor. Its rate
is `1e-3*R*T*sum(log(C_program)*d_dot)` pJ/s. This declares a reversible external
composition controller; it makes no claim that native BETSE reports this work.
The voltage clamp supplies the opposite ionic charge, including charged native
overlaps, without altering the background or finite tissue inventories.

At t=0, the same additive material/charge/work contribution is a recorded
`cells.surface_bath_initial_controller_operation@1` preparation. It is present
in physical readouts and conservation from the initial state onward. No tail
is dropped and no parent transport history is cleared.

Transport uses the exact passive or complete56-law equations and all original
controls. A further saved `reservoir_chemical_work_pJ` integrates
`1e-3*R*T*log(C_program)*maintenance_supply` at every RK stage. It replaces the
invalid fixed-chemical-potential shortcut with the per-reservoir identity
`electrochemical_work = chemical_work + phi*ionic_supply_charge`. All original
material, capacitor, global charge, energy, electrode work, dissipation, gate,
pump and padding checks remain. Inactive schedules have exactly parent RHS
values in every original state field.

The analytic controller contribution avoids numerical drift or resetting of a
prescribed concentration. Its chemical and electrode powers cancel exactly in
the physical energy law. The reported rate residual evaluates the remaining
transport budget, avoiding subtraction of large cancelling prescribed powers;
the individual physical powers are still exposed and independently compared.

## Reviewable surface and limits

IDs are `resolved_passive_bath_events@1` and `resolved_active_bath_events@1`,
with14/21 saved arrays. Their strict schemas declare bath sites, ordered events,
Cl guard, phase and clock/controller/baseline policies. No execution keys are
added. `artifact`/`replay` authenticate the initial operation and complete
definition. `physical_state`, `physical_amounts`, `initial_operation` and
`signal_values` expose the physical interpretation directly. Parent-named saved
history fields report transport contributions; observer `physical_*` histories
report additive totals, ordinary amount/rate/power readouts are physical, and
`maintenance_*` rates identify the parent contribution.

The pure reference uses scalar80-digit ordered setters, existing independent
full-node field/56-law equations, explicit owner loops and80-digit original
mixture/capacitor energy. Unit cases include literal setter parity, all-control
stage comparisons, nonzero1ns transport prefixes, distinct bath baselines,
permuted/padded owners, empty/disabled/INIT reduction, domain refusals and finite
ledger corruptions. These short probes do not qualify full bath trajectories,
slow-gate equilibration, calcium stores, finite fuel, water, non-ECM setters or
an INIT-to-SIM bridge. Root owns shared routing/public fixtures and qualification;
no worker numerical or GPU run is launched.
