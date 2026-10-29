# Scheduled calcium/finite-fuel membrane boundary

Purpose: resolve the Chief's explicit @6 boundary-design request before adding
scheduled background membranes to coupled physical owners. A passive or ionic
projection cannot serve as the complete calcium/fuel field, state or accounting.

The first concrete calcium owner is `resolved_calcium@6`
(`SurfaceCalciumCavModel`, exact `surface_calcium.CAV_LAYOUT_TYPE`). Its nested
ionic identity is `resolved_tissue@7`. It retains all actual channel/junction
gates, dedicated calcium gates, PMCA/NCX, free/bound cytosol and ER chemistry,
reaction/ER/plasma transfers, capacitor charges and every work/heat ledger.

The finite-fuel target is specifically `resolved_calcium_energy@5`
(`SurfaceCalciumEnergyHCNExtraModel`, exact energy HCN_EXTRA layout). Its nested
ionic identity is `resolved_tissue@12`. It retains the complete 56-law owner and
actual cellular ATP/ADP/Pi, regeneration, all three pump families and every
pool/material/energy ledger. These are two explicit supported parent contracts;
other calcium versions, water, transport, mitochondria, regulation, cuts and
phase handoffs receive no blanket admission.

## Verified source distinctions

- `spatial_calcium.cytosol_amount` gathers actual free chemical amounts from
  each owned store. It does not reconstruct free calcium from total ionic
  reference amounts or transfer integrals.
- `spatial_calcium.ownership_residual` compares chemical moiety increments with
  the actual total ionic increment. Plasma charge remains the whole-cell ionic
  increment; ER charge and free/bound chemistry have separate owners.
- `surface_calcium.readouts` passes that live free-cytosol view into the exact
  kinetic layout, then adds dedicated calcium/PMCA/NCX and ER reaction/transport
  derivatives. Store inflow follows the actual current external ionic RHS.
- `surface_calcium_energy.stage_layout` derives all Na/K, PMCA and ER pump
  parameters from the same current energy-pool amounts at every RK stage.
  `initial_prior_spec` is for initial layout/serialization only; it cannot
  supply stage fuel.
- Finite-fuel balances remove constant maintained-drive identities. The three
  pump work ledgers become internal energy transfers. Actual pool free energy,
  regeneration work/heat, adenylate and phosphorus must remain in global checks.

The current source has no `resolved_calcium_energy@6`; the requested @6 entry
point is the explicit calcium @6 owner. No new parent identity or constitutive
law is invented to fill that naming gap.

## Coefficient capability

Use the qualified `tissue_profile_composition_preparation` artifact in full.
It replays the complete source, owns inventory/state identities and carries
`direct_parameter_preparation` for native geometry/target/D-thickness binding.
That inner record supplies native coefficients only. It never supplies coupled
fields, controls, free concentrations, pump parameters or physical state.

Only background plasma membrane P changes. Store/ER permeability, volumes,
capacities, gates, initial inventories, fuel declarations and all source control
histories remain the complete parent's data. Native timing/default-Dm/target
rules retain their already qualified scope; no full native-loop claim follows.

## History and observation risk

The fixed-parent membrane history guard also sits below these coupled owners.
The active component's closed-route diagnostic view is eligible only after a
new transitive call-graph proof through calcium chemistry and live pool staging.
All actual chemical, ionic, gate, fuel and other ledger fields must remain
unchanged. Actual full state and union route support drive every accounting
check; current P drives every physical readout.

Calcium observation collects physical readouts and named actual state, so the
single temporary diagnostic field can be restored after observation, with full
actual conservation checked first. Finite-fuel observation additionally calls
`balances`. Its diagnostics must be assembled from untouched actual state; do
not route projected history through material or pool-energy diagnostics. An
owner-specific observation adapter must use actual balances and actual pools.

Parent chemical/ionic loss bounds must see the maximum possible background P,
not just its static baseline. Native global support supplies a conservative
all-time upper coefficient for timestep/domain checks only. It must never
replace instantaneous physical coefficients.

Implementation review found the inherited calcium loss bound does not include
background membrane GHK outflow. The new check therefore supplements that
unchanged chemical/pump bound explicitly: each outgoing background coefficient
is at most `area * P_upper / 1e-15 * (1 + |z| F V_max / (R T))`. Sum it per
species and actual finite owner, divide by the same owner volumes used in the
physical free-cytosol/exterior equations, and take the maximum fractional rate.
`V_max` is the complete calcium owner's admitted membrane voltage domain.
Require `step * (background_bound + parent_chemical_bound) <= 0.25`; finite-fuel
uses its existing conservative live-fuel parent projection for the chemical
term. The giant-permeability refusal initially exposed this gap; its failed
evidence remains frozen. This strengthens admission without changing a flux,
physical history, scientific tolerance or any parent file.

## Required evidence before admission

Keep the parent equations and all frozen passive/epoch/active/shared files
unchanged. New spec/runtime/reference/tests must preserve the exact parent
types and every named field. Qualify @6 first, then the explicit finite-fuel
owner with its live stage-pool contract. Independent complete coupled RHS,
potentials, chemical/free/bound ownership, ATP/ADP/Pi and full ledger comparisons
must cover pulse phases, closure/reopening and real control clocks. Include
adequate short refinement, actual-history corruption, wrong owners, exhaustion,
unchanged inactive scheduling, exact artifacts/checkpoints and no implicit phase
transition. CPU7, <=1 GiB RSS, >=8 GiB reserve, no GPU or long trajectories.

The dependency manifest must explicitly include `validation/betse/contact.py`:
the pump oracle imports its `require` assertion helper through an unqualified
module path, which a package-prefixed AST dependency walk can otherwise miss.
