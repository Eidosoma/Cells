# Finite ATP, ADP and phosphate pools

`cells.processes.finite_energy` implements a standalone finite-energy component
for the declared transformed law `finite_atp_adp_pi_transformed@1`. It supplies
current metabolic concentrations to the existing Na/K process without changing
that process or its maintained-reservoir configurations. Model, schema,
checkpoint and tissue integration require their own work and qualification.

The immediate purpose is to replace an inexhaustible chemical input with owned
material and finite free energy, while preserving the existing pump's 1-M
standard state. The [mitochondria review](PAPER_REVIEW_MITOCHONDRIA.md) explains
this prerequisite. The supply port below is synthetic; its rates and energy
input are declared parameters rather than a mitochondrial or experimental fit.

## Units, ownership and API

Amounts have axes `[..., 3, owner]`, with fixed species order `ATP, ADP, Pi`.
Leading axes may represent independent worlds. Volume and owner parameters
broadcast to `[..., owner]`; route data broadcast to `[..., route]`. Static
integer owner indices and boolean masks are explicit one-dimensional arrays.

| Quantity | Units or responsibility |
| --- | --- |
| Amount, signed cycle extent | fmol |
| Current physical volume | pL |
| Concentration `amount / volume` | mM, numerically mol/m³ |
| Temperature | K; declared numeric domain 200–400 K |
| Standard energy, chemical potential, supplied energy per cycle | J/mol |
| Free energy, supplied work, dissipated heat | pJ |
| Rates and powers | fmol/s and pJ/s |
| `Parameters(temperature_K, delta_g0_J_mol, active)` | Pool thermodynamic context |
| `Routes(owner, active)` | Once-owned pump or regeneration routes |
| `RegenerationParameters(capacity_fmol_s, supplied_energy_J_mol)` | Explicit reversible supply port |

`validate_parameters` and `validate_routes` check host declarations.
`domain_valid` checks physical state; `exchange_domain_valid` checks signed
cycle arrays and their padding. `thermodynamics` returns concentrations,
chemical potentials, hydrolysis energy, finite free energy, osmolyte count and
the separate partial derivative with respect to volume.

`pump_parameters` gathers the current pool concentrations and standard energy
into a new `kinetic_pump.Parameters`. Capacity and Km remain those of the
provided template. The caller supplies Na/K potentials, temperature and
availability from the same integration stage. Existing pump parameters are
immutable inputs; the bridge does not change them or call pump kinetics.

Temperature is a separate argument of `kinetic_pump.kinetics`, rather than a
field of its `Parameters`. With validated pool parameters, gather it as
`temperature = np.take(p.temperature_K, routes.owner, axis=-1)` and use
`np.where(routes.active, temperature, 298.15)` for inactive padding. This preserves
leading world axes. Use the same gathered temperature for ionic chemical
potentials and kinetics. A composing model may instead enforce equality to its
global temperature; it must not mix a heterogeneous pool drive with an unrelated
global temperature.

`exchange_rates` consumes the pump's already-computed signed cycle rates and
the regeneration port's signed synthesis rates. It returns amount derivatives,
signed owner totals and gross directional hydrolysis/synthesis rates. Composing
models retain the existing pump cycle integrals, new regeneration extents, and
the regeneration work/heat integrals. They may additionally retain the gross
directional integrals. Applying the same pump transfer through two ownership
paths is an error; `material_balances` checks amounts against those route
extents and the independent adenylate/phosphorus identities.

Repeated destinations use the established `ordered_scatter` routine, preserving
declared route order. Leading worlds remain independent. Route permutation is
not a guarantee of identical floating-point reduction. Empty route arrays and
explicitly inactive owners are supported.

## Material and finite chemical energy

Positive pump cycles implement `ATP -> ADP + Pi`, with coefficients
`(-1, +1, +1)`. Negative cycles implement the reverse. For signed pump demand
`D` and signed ATP synthesis `S` accumulated to one owner:

```text
d(ATP, ADP, Pi)/dt = (-1, +1, +1) * (D - S)
adenylate          = ATP + ADP
phosphorus         = 3*ATP + 2*ADP + Pi
```

Both identities are conserved. Regeneration imports energy through the port;
it does not import ATP or reset a pool. Gross directional rates retain opposing
flows that would disappear from a net extent.

The explicit standard concentration is `c0 = 1000 mM`. In the chosen energy
gauge, `mu0_ATP = -delta_g0` and `mu0_ADP = mu0_Pi = 0`. At fixed owner
temperature and declared standard potential:

```text
mu_i = mu0_i + R*T*log(c_i/c0)
g    = delta_g0 + R*T*log(ADP*Pi/(1000*ATP))
G    = 1e-3 * sum_i n_i * (mu0_i + R*T*(log(c_i/c0) - 1))
```

Thus `mu_ADP + mu_Pi - mu_ATP = g`. For fixed volume, pump consumption changes
the pool free energy at `1e-3 * D * g` pJ/s. `chemical_power_pJ_s` computes the
general species contribution `1e-3 * sum(mu_i * dn_i/dt)` per owner.

For changing volume, the separate partial derivative is
`dG/dV = -1e-3 * R*T*sum(n_i)/V` pJ/pL. A later water composition must include
this term and the explicit `ATP+ADP+Pi` osmolyte count exactly once. The component
does not insert either into existing ionic or impermeant totals.

## Reversible supplied-energy port

The declared law `driven_atp_regeneration_tanh@1` uses a finite nonnegative
capacity `C`, availability `a` in `[0,1]`, and supplied energy `w >= 0` J/mol:

```text
J                    = C*a*tanh((g+w)/(2*R*T))
reaction_energy      = -g-w
supplied_power       = 1e-3 * J*w
dissipated_power     = 1e-3 * J*(g+w)
pool_chemical_power  = -1e-3 * J*g
```

Positive `J` synthesizes ATP. Negative `J` hydrolyses ATP and exports signed
work. Dissipation is nonnegative in both directions, and
`pool_chemical_power + dissipated_power - supplied_power = 0` at fixed volume.
Zero supplied energy remains a reversible dissipative route; availability zero
closes the route exactly. The numeric domain requires `abs((-g-w)/(R*T)) <= 80`
and finite outputs. An overflowing power is rejected even if its nominal
capacity parameter is finite.

For a later closed ion/pool composition, the first-law balance becomes:

```text
dG_ions/dt + dG_pools/dt + pump_heat + regeneration_heat - supplied_power = 0
```

The former maintained-reservoir chemical work must be replaced by the finite
pool contribution. Counting both would introduce a second energy source.

## Domain and scientific limits

Every active owner requires finite, strictly positive ATP, ADP, Pi and volume.
Exhaustion rejects the trial, including with all routes off. There are no log
floors, pool clipping, ATP resets or zero-substrate continuation law. Physical
inputs are never repaired by a domain predicate. Neutral arithmetic in rejection
predicates and inactive padding does not change accepted state.

Inactive owners use zero amounts, unit volume, 298.15 K and zero standard
potential. Inactive routes require zero cycles; inactive regeneration routes
also require zero capacity, supplied energy and availability. Present but
blocked routes retain their real pool-domain requirements. Pure kernels expect
validated inputs; a composing solver must reject invalid stages and outputs.

This is a transformed biochemical-potential model with buffered pH, magnesium
and solvent activity. H/O/Mg species, explicit protons, water stoichiometry,
binding equilibria and electrical metabolite charge are not resolved.
Temperature and standard potential are fixed per owner; time-varying thermal or
buffer support would require additional work/heat terms. A future integration
must assign cell/compartment ownership, osmolyte and charge bookkeeping, and
decide which buffers support the transformed species.

The existing calcium laws use a historical numeric-mM quotient. They cannot
silently share this 1-M energy accounting. Existing named laws, source histories
and accepted configuration meanings are preserved. No respiration, oxygen-use,
mitochondrial inheritance or whole-cell biological claim follows from this port.

## Reproducible checks and remaining work

The [protocol](../validation/chemistry/finite_energy_protocol.json) declares the
equations, units, numerical budgets and resource limits before execution.
The [independent reference](../validation/chemistry/finite_energy_reference.py)
uses 80-digit Decimal arithmetic without importing Cells, NumPy or JAX.
Tests compare thermodynamics, signed regeneration, material ledgers, shared
owners, current-volume pump inputs and closed first-law identities. Source-off
and recovery-direction examples are instantaneous contracts. Analytic constant
signed-demand paths require no numerical trajectory integration.

NumPy/reference tests select `tests/unit/test_finite_energy.py -k 'not jax'`.
Separate CPU JAX prototypes select `-k jax` for eager/JIT/vmap and energy
gradients. Actual checks and retained failures are linked in the worker's
[work log](../agent-work/cells-worker-01/WORK_LOG.md); this guide is not a second
run-status record. L4 qualification and whole-model integration remain separate.

A useful next independent work item is a bounded demand/supply-interruption
trajectory harness with a separately integrated scalar reference, complete
replay and step refinement. It can qualify energetic exhaustion/recovery
experiments before touching existing tissue-model ownership or checkpoints.

## Resolved active tissue with finite cellular pools

The new `resolved_energy@1` family composes the finite component with the
`resolved_tissue@7` shared channel catalog and actual Na/K pumping. Geometry,
capacitance and compartment volumes remain fixed; outside owners are finite
and closed. Qualification status belongs in `PROGRESS.md` rather than this
contract. The implementation and initial host checks are not a biological fit.

Every cell declares exactly one `energy_pools` entry. Its `cell_id` owns the
volume, and the ionic model owns the temperature (298.15 K for the existing
unscaled channel laws). Pool amounts and standard energy are explicit:

```json
{
  "id": "energy_0",
  "cell_id": "cell_0",
  "law": "finite_atp_adp_pi_transformed@1",
  "initial_amount_fmol": {"ATP": 0.003, "ADP": 0.0002, "Pi": 0.0002},
  "delta_g0_J_per_mol": -37000.0
}
```

Na/K pumps refer to their inside cell's pool through
`"metabolism": {"kind": "finite_energy_pool@1", "pool_id": "energy_0"}`.
They do not retain unused maintained ATP/ADP/Pi fields. Several pump patches may
share that owner; their already-computed signed cycle rates accumulate once.
Each stage supplies current finite concentrations to the unchanged kinetic law
before assembling conservative ion and pool derivatives.

`regeneration_ports` declare `id`, `pool_id`, the named tanh law,
`capacity_fmol_per_s` and `supplied_energy_J_per_mol`. Their independently
identified `regeneration_controls` use the standard time/availability schedules.
The accepted grid unions membrane, junction, channel, pump and regeneration
boundaries. Empty port lists are explicit; `regeneration_capacity` controls
padding, independently of cell, membrane and channel capacities.

The [example](../configs/resolved_energy_tissue.json) has a 50-us horizon and
1.25-us nominal step, three shared Kv1.5/HCN4/CaV1.2 populations, independent
off-grid supply/pump/channel interruptions and a small finite fuel supply.
Its 200-fmol/s pump capacity and small metabolic amounts are manufactured to
make finite-fuel effects resolvable over this interval. They are not calibrated
physiological rates. A second fixture uses two pump patches sharing one pool.
Calcium is an ordinary transported ion here, without ER/buffer composition.

Complete state contains the 19 active ionic fields plus:

| Field | Axes and meaning |
| --- | --- |
| `energy_amount_increment_fmol` | ATP/ADP/Pi × cell slots |
| `regeneration_cycles_fmol` | Signed synthesis extent per port |
| `regeneration_dissipated_energy_pJ` | Nonnegative accumulated port heat |
| `regeneration_supplied_work_pJ` | Signed accumulated external supply |

All 23 fields, numerical layout and control clocks belong in complete
checkpoints. `initial_ionic_spec` reconstructs initial maintained concentrations
only for parser/layout reuse and an initial-rate comparison. It is not the
evolving finite-energy definition, and serialization preserves finite references.

The existing `metabolic_work_pJ` field records an **internal** pump/pool transfer
integral using current chemical drive. Its fixed-initial-drive-times-cycles
identity is invalid for changing fuel. The combined balance uses finite pool
free-energy change, ionic/capacitor energy, transport/pump/regeneration heat and
signed regeneration supply. The internal diagnostic is not an external source.
An additional per-cell pool balance checks finite free energy against that
integrated internal transfer and port heat/work. Material ledgers separately
check ATP/ADP/Pi, adenylate and phosphorus. Port supply retains the exact
constant-work-per-cycle identity for its declared fixed supplied energy.

The existing 1.25-us channel ceiling is retained. An additional initial gross
turnover check limits the nominal step to five percent of the smallest initial
pool per active control setting. This is an initial guard, not a global
positivity or accuracy theorem. Every trial must still satisfy the strict pool
domain, and coupled timestep/reference qualification remains necessary.

The [independent tissue reference](../validation/tissue/surface_energy_reference.py)
reconstructs its own initial ionic representation from raw declarations. It
uses full-node field roots, independent Decimal channel/pump laws and the
separate 80-digit metabolic oracle. Its segmented adaptive integration is
available for coordinated trajectory/refinement checks. Worker tests cover
host/schema and instantaneous 23-field stages; execution/replay and full CPU/L4
qualification are coordinated separately.

This composition does not implicitly add metabolites to ionic charges or water
osmolyte totals. Buffered pH/Mg/solvent assumptions remain explicit. Combining
these pools with changing-volume water dynamics requires a later once-owned
osmotic and transformed-energy contract. No mitochondrial respiration,
proton/Mg speciation, assembly ATP cost or autonomous metabolic regulation is
inferred from the finite-energy family.
