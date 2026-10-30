# Held temperature: owner inventory and supported scope

Chief assigned new `physiology_temperature*` files only. The existing detached
voltage-transition qualification remains untouched and unpolled. Temperature
qualification uses Chief's separately assigned CPU4; CPU5 remains reserved for
the transition job. Static development is separate from numerical qualification.

## Exact families reviewed

| Model ID | Temperature contract | Changed-T scope of this adapter |
| --- | --- | --- |
| `resolved_tissue@1` | Positive prescribed Kelvin temperature in the passive transport/field law | Complete held readouts and full RHS, with original accepted history preserved |
| `resolved_tissue@12` | Shared catalog explicitly requires 298.15 K without temperature scaling | Exact-temperature identity; changed T refused |
| `resolved_calcium@11` | Inherits the same channel contract; ER stores must match ionic T | Exact-temperature identity; changed T refused |
| `resolved_calcium_energy@5` | Inherits channel/store contracts and finite fuel standard-state conversions | Exact-temperature identity; changed T refused |
| `resolved_open_calcium@1` | Same channel/store contract, plus explicit ideal-reservoir closure | Exact-temperature identity; changed T refused |
| `resolved_open_calcium_energy@1` | Same channel/store/fuel contracts, plus explicit reservoir closure | Exact-temperature identity; changed T refused |

`surface_kinetic_spec.parse` explicitly raises “Resolved channels require 298.15 K;
no temperature scaling”. `surface_kinetic_reference._catalog_binding`,
`surface_calcium_energy_reference.bind` and `open_calcium_reference._fuel_components`
retain corresponding restrictions. A temporary layout cannot silently override
this scientific domain. A faithful changed-temperature active model needs an
identified channel/chemical temperature policy and compatible independent
references; arbitrary Q10, Arrhenius or standard-potential extrapolations are not
supplied by the native global setter.

## Temperature dependencies and physical owners

| Mechanism / owner | Actual fields and dependencies | Current interpretation |
| --- | --- | --- |
| Every cell, finite outside owner and ideal reservoir | `layout.temperature`; `surface_transport` computes `RT`, `z F V / RT`, GHK membrane/junction fluxes, logarithmic-mean exterior fluxes and electrochemical affinities | One uniform prescribed Kelvin setpoint; permeability, geometry, capacitance and ionic valence remain declared constants |
| Electrical field / floating capacitor components | `surface_field` uses temperature in exterior conductance and junction-current nonlinear roots; capacitance matrix and fixed charge constraints contain no T factor | Recompute the complete field at the held T; retain original charge and capacitor anchors |
| Chemical reservoirs / electrodes | `mu = RT log(c) + z F phi`; reservoir chemical power, electrode work and dissipations use the recomputed field and fluxes | Instantaneous isothermal source/work rates; no thermal transition inferred |
| Na/K pumps at actual membrane owners | `kinetic_pump.chemical_drive` uses declared `delta_g0_J_mol + RT [log(ADP) + log(Pi) - log(ATP) - log(1000)]`; saturation and affinity use T, with 200–400 K process domain | Maintained concentrations/standard energy and capacity/Km constants are explicit model inputs; no Arrhenius law. `pump_drive` is also a fixed-temperature history cache, not a field to reset in an accepted checkpoint |
| Shared channel populations | Most gate kinetics read voltage and fixed source coefficients without a T argument. Legacy instantaneous calcium-sensitive K reads live free Ca and T explicitly. The common composing schema nevertheless fixes 298.15 K | Do not reinterpret a partial electrochemical T update as a complete temperature-scaled catalog; even disabled/empty channel populations retain their versioned model contract |
| Intrinsic junction gates | Voltage kinetics and fixed threshold/minimum; no T scaling input | Fixed source law; no invented temperature coefficient |
| Owned ER/cytosolic chemistry per actual cell | `er_temperature` contains each store's scalar temperature. `er_standard_mu_RT`, `er_delta_mu_RT`, `er_forward_rate`, volume and standard concentration enter chemistry. Chemical energies/powers scale with RT; equilibrium ratios follow declared dimensionless potentials and kinetic coefficients | Store T must equal ionic T. No reaction enthalpy or activation-energy data are present to select a new physical thermal law |
| ER calcium pumps / release | ER electrochemical terms, maintained ATP drive and dimensionless affinity depend on store T; calcium gate time constants are fixed-source kinetics | 200–400 K ER process domain does not relax the encompassing 298.15-K channel contract |
| Plasma calcium pumps and Na/Ca exchange at membrane owners | `RT log` concentration terms, `F V / RT`, pump chemical drive and exchanger affinity use global T; PMCA parameters include standard potential/concentration conventions | Actual physical owners and standard states stay explicit; unchanged parent history cannot be recomputed under another T |
| Finite ATP/ADP/Pi pool per actual cell | `pool_parameters` supplies live T to transformed chemical potentials, hydrolysis Gibbs energy, mixing free energy, osmotic derivatives and regeneration affinity. `energy_delta_g0_J_mol` is declared in J/mol; inactive owners use neutral 298.15 K | Pool amounts, volume, standard energy and active masks are independent owners, not additional free-ion species |
| Finite-fuel Na/K, PMCA and ER routes | `surface_calcium_energy.stage_layout` projects the same live pool into all pump families; `finite_calcium_pumps.legacy_standard_energy` computes `delta_g0_1M - RT log(1000)` | Both temperature and the 1 M / numeric-mM conversion matter. Updating only outer `temperature` would miss ER temperatures and fixed-temperature admission/history assumptions |
| Open calcium/fuel closure | Actual reservoir chemical potentials, charge supply, external/internal chemical powers and source terms use actual held T | Open variants do not remove the channel restriction; no new thermal coverage follows from chemical openness |

The binding records every actual cell, environment owner, membrane, junction,
outside face, channel population, store-cell owner and finite pool ID, plus
explicit Kelvin units and source identity. The
native T multiplier is dimensionless. It is applied to the original source
temperature through the pinned global setter; disabled calls retain their given
temperature memory. Temperature/voltage/blocker setters remain separate.

## Thermodynamic statement

The accepted parent state/layout, gate values, material and energy histories,
controls, clocks and source specification are checked under their original T.
For passive readouts only a temporary scalar `temperature` changes. All inherited
field/domain, fixed-step, gross-turnover and stage-energy checks remain intact.
No accepted heat input, internal-energy update, entropy production during a
temperature change, heat capacity, thermal transport or anchor reset is defined.

For the passive ideal-mixing isothermal functional with fixed declared standard
state, report the algebraic coefficient shift
`1e-3 * R * (T_new-T_original) * sum(n*(log(n/V)-1))` pJ over actual cells and
finite exterior owners only. Ideal reservoir reference inventories are excluded
from this finite-system diagnostic. This is a change of a prescribed Gibbs
functional, not heat, thermal internal energy or an accepted thermal jump.
Absolute standard chemical potentials and missing caloric state would matter
for a general thermal transition. Active-family identity has zero such shift.

## Planned qualification when CPU5 is released

Use complete passive field/RHS references and 125-digit/pinned native T setters.
Cover initial/evolved source-valid states, closed/open passive worlds, owner
order/padding, nontrivial held controls, all active identities, guarded changed-T
refusals (including empty/blocked populations), invalid/nonpositive native T,
disabled/empty/zero-amplitude programs, source association and parent preservation.
Replay saved reference inputs in a fresh process with Cells/JAX imports denied.
Keep existing rate/charge/field budgets, 5% turnover ceilings and `1e-10 pJ/s`
stage energy limit. No new numerical run or detached-job status check is authorized
by writing this protocol.
