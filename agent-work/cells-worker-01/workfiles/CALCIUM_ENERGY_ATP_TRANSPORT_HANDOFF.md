# Finite-ATP configured transport handoff

Chief-assigned new six-file implementation, qualified 2026-10-30 on CPU7.
Shared parsing/dispatch, public integration tests and repository docs belong to
Chief. All six sources below are now frozen. Current machine-readable status,
failed attempts and the exact resource receipts are in
[the workqueue](calcium_energy_atp_transport_workqueue.json).

## API and physical ownership

- Identity: `resolved_calcium_energy_atp_transport@1`; class
  `SurfaceCalciumEnergyATPTransportModel` subclasses the legacy transport class
  to reuse its existing merged scheduler. Dispatch must select this new class
  before the legacy superclass. Core/model files share the prefix
  `surface_calcium_energy_atp_transport`; reference/fixture files use
  `calcium_energy_atp_transport`.
- Each route retains the native configuration unchanged and declares exactly
  `drive={kind:finite_energy_pool_hydrolysis@1,pool_id,atp_per_cycle:1}`.
  Its pool must belong to that membrane's inside cell. The neutral transformed
  ATP/ADP/Pi rows are views of actual finite owner concentrations at every stage;
  they never add physical inventory or exterior fuel and cannot be membrane cargo.
- Exactly ATP -> ADP + Pi is supported, with coefficient one for each fuel.
  The ionic reactant/product species/coefficient maps must otherwise agree.
  At least one ionic species crosses the membrane. All native Km, regulator,
  density and availability semantics remain the pinned component's contract.
- `network_transport.constants` explicitly declares the Cells F/R values,
  `ionic_standard_state_mM:1` and `fuel_standard_state_mM:1000`.
  Native numeric standard energy must exactly equal the actual owner's 1-M
  hydrolysis delta_g0. None/string-None and mismatched numeric zero refuse;
  numeric zero remains valid when the actual pool also has delta_g0 zero.
- `STATE_TYPE`/`STATE_AXES` contain all 38 parent fields plus these eight:
  `network_cycles_fmol`, `network_transferred_fmol`,
  `network_dissipated_energy_pJ`, `network_fuel_work_pJ`,
  `network_chemical_work_pJ`, `network_electrical_work_pJ`,
  `network_gross_hydrolysis_fmol`, `network_gross_synthesis_fmol`.
  `EXTRA_AXES` declares all eight; only transferred amounts have a species axis.
  The layout has its own exact type and explicit `network_pool_owner`.
  There is no network external-supply field.

## Native correspondence and physical coupling

The pinned source multiplies one literal 1e-3 by each listed concentration raised
to its configured coefficient. Preserved ionic item/coefficient maps cancel
those conversion factors between sides. One ATP -> ADP + Pi leaves exactly
one 1e-3, giving `ADP_mM*Pi_mM/(1000*ATP_mM)`. Consequently the native numeric
reaction energy equals actual 1-M fuel hydrolysis plus ionic concentration work
and outward electric work, without rewriting the source algebra or applying
an extra standard-state bridge. Independent 80-digit source and fuel equations
check that correspondence at every full initial/evolved stage.

Physical heat is `-1e-3 * extent_fmol_s * reaction_energy_J_mol`.
`network_fuel_work_pJ` integrates released pool power:
`-1e-3 * extent_fmol_s * hydrolysis_free_energy_J_mol`. It is an internal transfer diagnostic. Whole-system
energy counts actual fuel free-energy change once, all physical heat once and
only the original declared external supplies. Per-route ionic chemical work +
electric work + heat - released fuel work is checked independently.

Reverse native cycles explicitly synthesize ATP and consume ADP/Pi. Signed
regulation is retained; negative actual heat refuses without clipping. Taking
positive/negative parts is confined to gross-turnover bookkeeping. Combined
shared-owner gross hydrolysis/synthesis includes all existing Na/K, PMCA, ER
and regeneration consumers once. The original 0.05 initial minimum-fuel-pool
step limit and ionic limit remain unchanged, with all merged control events.
An opposed 20000/-20000fmol/s shared-pool unit proves net cancellation cannot
hide turnover. Exhaustion refuses even with transport blocked.

All parent species, chemical ownership, charge, electrode, energy, fuel
material, adenylate, phosphorus and internal-energy ledgers remain enforced;
new route extents extend their explicit accounting rather than replacing their
checks. Original numerical tolerances are retained.

## Evidence

All 75 pytest checks pass: 52 host, 1 CPU JAX eager parity and 22 independent cases.
These include 28 complete 46-field initial/evolved stage comparisons across
active, blocked, empty, reordered, reverse, mixed and fuel-regulated arms with
compact/padded layouts. Fresh actual mixed-arm RHS and DOP853 integration also
pass with both import mechanisms denying Cells/JAX; that is an independence
proof, not an extra counted scientific case.

The three full46-field histories span two original 1.25 us nominal steps and an
actual 0.9375 us route-only boundary. RK4 dt/half-dt is checked against standard
and tightened DOP853 oracles. Fixed state budget is 3e-12 absolute +3e-10 relative
(with 3e-23 C charge budget); potential 3e-13 V; physical rate-energy 1e-10 pJ/s;
endpoint-energy 1e-10 pJ; pool material 2e-12 fmol. No budget was widened.

| Arm | dt error / budget | half-dt error / budget | oracle uncertainty / budget |
| --- | --- | --- | --- |
| reverse | 0.035258699896646005 | 0.0027090825301618235 | 1.196156906028461e-06 |
| active | 0.03517884469798876 | 0.0027041236178174037 | 1.3220653389307616e-06 |
| mixed | 0.03517946024972551 | 0.002705354723408927 | 1.1470820955915049e-06 |

Maximum full-stage rate error/budget: `0.003763341958883924`.
Maximum independent rate-energy residual: `2.1344037648418634e-14 pJ/s`.
Fresh mixed endpoint residual: `-2.3312921688598e-15 pJ`.
Raw definitions, full states/rates, potentials, signed errors, budgets and
short trajectory arrays are under the receipt's `evidence/` directory.

Receipt: `/mnt/workspaces/Cells/calcium-energy-atp-transport-development-20261030-06/result.json`
SHA256: `d15fc77aa5c86756bb6572209ca27d0d3fac51cebe2427428e69ca9fcd5ebaf2`.
Its `inputs.json` preserves all captured source hashes, exact commands,
environment, package versions and the predeclared protocol. All captured
sources remained unchanged. Existing irreversible six hashes are still exact.

All commands used CPU7, one thread, CPU-only JAX, no persistent compilation
cache, 180 s limits, 1 GiB process-tree RSS and 8 GiB host reserve. Phase times were
4.78s isolated reference,10.81s host,39.26s JAX and44.98s independent. Peak RSS
was 642646016 B; minimum available host memory stayed above 21 GB. No long job,
GPU computation, campaign status query or frozen/shared-source edit ran.

Retained failures: preflight 01 missed old test paths in source capture (no
child launched); 02 had a duplicate NPZ potential key after a successful
reference calculation; 03 exposed a 7Na fixture that still hydrolyzed ATP at
actual Vm (corrected to 8Na on both ionic maps); 04/05 caught the focused gross
test deleting its own route event while keeping an off-grid observation.
Corrected that unit to preserve the original schedule and use its accepted
steps. Physical equations and all acceptance budgets remained unchanged.
Exact failed sources, resources, logs/JUnit and corrections are linked from
the same workqueue; no failed evidence was overwritten.

This qualifies synthetic finite-fuel coupling to the pinned native subset,
not a new full native-tissue equivalence, physiological settling, temporal
order, long trajectory or GPU claim. Reuses the previously qualified native
component and independent physical store-energy helper; it does not claim
new actual BETSE ATP-route captures.

## Frozen sources

| Source | SHA256 |
| --- | --- |
| `src/cells/core/surface_calcium_energy_atp_transport_spec.py` | `50aa3bfbde03da1d8d90ad027ba2ddf82a28056662d1e9be7f53cc40270b346d` |
| `src/cells/models/surface_calcium_energy_atp_transport.py` | `75ee86075e849db370b5b8ebb12587f43fe548f5fc539f197267e30bc8fae22c` |
| `validation/tissue/calcium_energy_atp_transport_reference.py` | `f5141c01a2289d0d0f45485d2c6900bfe6ffb21d3bc94867d7d8914db96d570c` |
| `validation/tissue/calcium_energy_atp_transport_fixtures.py` | `a9eadd7377afddee6d874e7d28de14b4c2a84fd6b9328fdf4440b3c29fdd3e29` |
| `tests/unit/test_surface_calcium_energy_atp_transport.py` | `1c60870b773ba616d8ca347af0170bfb6354b5bdb51f8391c25b96f5fcd89bd0` |
| `tests/unit/test_surface_calcium_energy_atp_transport_reference.py` | `96d1e2ae1aa556038a7f2eeb904df1f794a79f11ff9822611fd7abd36b1bf600` |
