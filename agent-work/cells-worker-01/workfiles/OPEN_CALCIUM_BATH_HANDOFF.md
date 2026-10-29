# Scheduled ideal baths for full calcium/fuel owners

Source is ready for Chief capture and qualification. This handoff explains the
new accounting and counterion ownership needed to assess the scientific claim.
Worker checks were static and raw-metadata only; no model parser, state
constructor, RHS, integrator, pytest collection or numerical job was invoked.
Current source hashes and receipts are in `open_calcium_bath_workqueue.json`.

Six new product modules define `resolved_open_calcium_bath_events@1` and
`resolved_open_calcium_energy_bath_events@1`. They retain all original 34/38
calcium/fuel transport and history fields, adding `reservoir_chemical_work_pJ`
and `phase_clock_s`, for 36/40 fields. The scheduled exterior policy is explicit:
`scheduled_declared_ideal_chemical_and_fixed_voltage_reservoirs@1`.
`schema.owner_spec(spec)` returns the exact corresponding static open owner;
actual reservoir flags, original anchors and fixed background stay unchanged.

The qualified ordinary bath controller supplies the native K → Cl → Na baseline
overwrite laws, explicit Cl guard, stable logistic derivative and transition/8
step ceiling. All full56, PMCA/NCX/Ca-channel/ER and live ATP/ADP/Pi laws are
delegated to the complete open owner using actual current bath concentrations.
The saved clock advances through all RK stages while experiment controls stay
held within each accepted interval.

Parent arrays retain the ordinary bath controller's transport-contribution
semantics. `physical_state` and `physical_*` observations add the prescribed
material dose, opposite electrode charge and program chemical/electrical work.
The nonzero logistic tails at time zero are a sealed, explicit initial
controller operation. No finite amount, source ledger, background or chemical
anchor is reset. Maintenance and programmed rates/work are separately exposed.

The separate chemical-work state integrates actual chemical potential times
the complete maintained supply, including owned plasma routes. The old
constant-potential chemical-work identity is replaced by that integral plus
fixed-voltage supply work. Original full calcium/ER/fuel material, ownership,
capacitor, metabolic, neutral-pool and energy budgets remain. Reversible
program material/charge/work contributions are kept separate until residuals
are formed, preserving small transport errors beside a large imposed dose.
Observers retain every original physical field and use the actual complete
open field and live pools.

Hard ionic-moiety ceilings apply to current physical material, including the
programmed dose, at every stage. Initial admission checks the conservative
all-pulse envelope. All inherited gate, chemical-loss and fuel bounds remain.
Finite fuel also checks initial gross hydrolysis plus synthesis across every
independent pulse-box corner and held control; its 0.05 limit is unchanged.
`energy_model.initial_pool_turnover_bound(spec)` exposes the actual initial
pool amounts, worst corner/control and fractional rate for review.

The accepted four-ion fixtures are untouched. New manufactured five-ion inputs
split existing chloride equally into Cl/M in every ionic and owned chemical
volume, with explicit M valence, moiety, inventories, routes and passive-control
availability. Every fixed background charge is unchanged. These are distinct
physical models. Empty/disabled/INIT reductions compare to their corresponding
static five-ion owner, including separately evolved two-step histories and all
original observations. A separate four-ion Cl-only case needs no M counterion.
Root's static review caught the initially missing M store-control keys; those
are now explicit in every row and asserted by metadata and unit checks.

The independent reference uses ordered 80-digit bath setters and the complete
independent open calcium/fuel equations. Stage argument views change only the
prescribed reservoir inventories; conservation uses the original complete
definition and additive program contributions. Its 33-file dependency closure
is hashed and statically audited, including legacy reference helpers and the
documentation-only test initializer.

There are 91 AST-declared parametrized tests in the two new unit files. They
cover full 36/40-field RHS/field comparisons at all control and bath clocks,
actual 1 ns prefix conservation, external ledger corruption, real M ownership,
strict positivity and ceilings, live-pool rate feedback, observer histories,
replay, native setters and exact static reductions. Prefixes and frozen-history
clock probes provide no full trajectory or biological claim.

The requested turnover boundary case is an unexecuted numerical test, explicitly
separate from the baseline fixtures. It declares a positive low Pi amount in a
cell served by a bath-controlled Na/K pump and a larger K program. It derives
the actual static and pulse-corner fractional rates, then declares a short,
resolved program with the original step quota and resource caps. Both candidate
inputs must pass every inherited static guard; the nearby smaller step must
pass the bath guard and the larger must fail specifically at gross turnover.
No production guard is patched or relaxed. Raw inputs and bound witnesses are
written before checks, so a qualification failure retains the proposed case.
Its feasibility and result require Chief execution; no pass is claimed here.

Static receipt: `host_checks/open_calcium_bath_e452d39b1deae858.json`.
All ten files pass AST/Ruff; 16 raw fixture variants have complete species,
moiety, route and control keys and unchanged background charge. The accepted
14 owned-calcium source files and immutable full8us02 bundle remain unchanged.
Root owns shared routing, public tests, numerical qualification, scheduling and
PROGRESS.md. No active job was polled or changed by this worker.
