# Scheduled regional membranes on complete calcium and finite-fuel owners

This component supports exactly two new models:

| Model | Complete physical parent | State arrays including clock | Fixture populations / laws |
| --- | --- | --- | --- |
| `resolved_calcium_membrane_profiles@1` | `resolved_calcium@6`, ionic @7 | 35 | 22 / 18 |
| `resolved_calcium_energy_membrane_profiles@1` | `resolved_calcium_energy@5`, ionic @12 | 39 | 63 / 56 |

The corresponding spec/runtime modules are
`surface_calcium_profile_interventions` and
`surface_calcium_energy_profile_interventions`. Each spec exports `parse`,
`to_dict`, `owner_spec`, `bindings`, `artifact` and `replay`. The shared native
coefficient capability is `cells.core.owned_calcium_profile_binding`.
Chief owns public parser/serialization/registry/ensemble integration and status.
This worker edited only new owned files and its own work log.

## Physical owner contract

Every original parent state/layout field is retained exactly. Calcium @6 keeps
actual free/bound cytosol and ER inventories, reactions, intrinsic and dedicated
calcium gates, PMCA/NCX, all ionic/chemical transfers, capacitor charge and every
work/heat ledger. Finite-fuel @5 additionally keeps actual ATP/ADP/Pi pools,
regeneration, adenylate/phosphorus and internal pump/pool energy transfers.
All Na/K, PMCA and ER pump parameters use the same current live pools at each
stage. Exact parent layout types preserve channel-catalog and free-calcium
dispatch; no passive or maintained-fuel physical surrogate is introduced.

The source is a full qualified composed preparation `{definition, provenance}`.
Replay must reproduce the entire physical model, including stores, gates, pump
and fuel declarations. The inner `direct_parameter_preparation` supplies only
native geometry, target order, diffusion and explicit SI thickness. It never
supplies physical fields, free concentrations, controls or stage pump parameters.

Only background plasma permeability changes. All complete parent control
families and merged held-input clocks remain. Native family order, target
duplicates/last assignment, default-D multipliers, signed factors and Na/K versus
Cl/Ca ion-flag rules reuse the unchanged qualified compiler/operator. Negative
or nonfinite physical permeability is refused without clipping. INIT disables
scheduled effects while the full owner continues evolving; SIM enables them.
The explicit phase clock advances at RK stages. Ordinary restart retains it;
ordinary branch cannot reset phase. No calcium/fuel INIT-to-SIM operation,
cut/remap or other composed family is admitted here.

## History, observations and timestep admission

The fixed parent rejects past background transfer on a currently closed route.
A temporary readout view therefore masks only that closed-route diagnostic
integral. No actual state is changed. Pinned transitive AST/state-flow evidence
excludes it from amounts, charge, fields, gating, store dynamics and live fuel
staging. Actual history uses the union of possible routes for accounting;
instantaneous physical fields always use current scheduled permeability.

Calcium observations validate actual full history first, collect physical
readouts and restore the actual integral. Finite-fuel observations explicitly
assemble all material, energy and pool diagnostics from untouched actual state.
Their physical calcium collector receives a layout staged from actual current
ATP/ADP/Pi. The initial-prior spec supplies IDs/clocks only. No projected history
enters global or pool balances. Corrupted closed-route history, chemical
ownership, unrecorded pool changes and fuel exhaustion all refuse.

The inherited calcium chemical loss bound omits background GHK transport. A new
conservative outflow term uses maximum scheduled P, actual free-cytosol and
finite-exterior volumes, and the parent's admitted membrane voltage domain.
For either direction its Bernoulli factor is bounded by `1 + |z F V / (R T)|`.
Sum outgoing rates per species/owner and require
`step * (background_loss_bound + parent_chemical_bound) <= 0.25`.
Finite fuel retains its existing conservative changing-fuel chemical bound.
The native ramp-resolution ceiling is also retained. This adds an admission
check; no parent equation, flux, ledger or scientific tolerance changes.

## Qualification and reproducibility

There are 44 distinct passing component checks: 40 host, two complete-owner
CPU JAX eager/abstract-trace checks, and two eager public exact snapshot/resume
checks. Ten panels provide 50 independent complete RHS/field stages. Eight
additional evolved closure/reopening stages bring the total to 58. Across four
evolved clocks for each owner, 980 nonboolean parent readout leaves agree bit
for bit between untouched and diagnostic-view histories. Every observed actual
parent array is exact; material/chemical/fuel corruption cannot hide in the view.

SIM and exact Na closure/reopening receive 4 us full-state trajectories at
31.25 and 15.625 ns against independent segmented DOP853 with every held-control
boundary. Both steps agree within the unchanged state/charge budgets. All four
comparisons are below the precision floor, so no convergence-order claim is
made. Full actual material, chemical ownership, pool, charge and energy checks
retain the parent tolerances. The manifest explicitly includes
`validation/betse/contact.py` and the pump oracle's unqualified `require` helper.

The detached Development07 run completed all checks with unchanged captured
scientific sources. Its raw summary remains **failed**: two public tests were
also selected in host closure phases and skipped by their existing phase guard.
Both then passed in their proper public phases. Finalization reconciles exact
JUnit identities, requiring one genuine pass for each of all 44 unique checks,
exactly those two duplicate skips, zero failures/errors and 44 evidence records.
The original result/failure receipts remain unchanged. A minimal future-runner
fix excludes backend-only cases from every host selection; it is recorded
separately and does not change or rerun scientific tests.

Every phase used CPU7, one numerical thread, <=1 GiB live guarded process-tree
RSS, >=8 GiB host reserve and a 480 s phase cap. Peak RSS was 708,788,224 bytes;
minimum host reserve was 12,020,678,656 bytes. No GPU, install, persistent cache,
long physical trajectory or other-job polling occurred. Component public checks
were already queued before Chief launched independent public checks; no new
public or regression jobs are needed for this handoff.

The frozen handoff exports full portable definitions for both families and all
five cases, plus sealed SIM artifacts. Replay with the corresponding spec
module, or use Chief's public routes. The original shared routing proposal is
historical; Chief has independently wired and checked the live routes. The
isolated test patch applies only to the captured qualified engine workspace.

Native correspondence covers the inherited buffer/pulse/target arithmetic and
explicit D/thickness conversion. CPU JAX claims are eager parity, abstract
tracing and nonzero pulse differentiation. Compiled coupled RHS/trajectories,
GPU execution, physiological fits, slow-gate settling, native full-solver parity,
other calcium versions/compositions and calcium/fuel phase transitions/cuts
remain outside this component's evidence.
