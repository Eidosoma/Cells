# Configurable native BETSE network transport

The new component implements the executable cell-zone transporter generator in
BETSE 1.5.0, with explicit material owners and NumPy/JAX kernels. It is ready for
Chief-owned integration. Existing cotransport, dispatch, schemas, documentation
and root PROGRESS were not changed by this worker.

- Law: `betse_network_transporter_source_v1_5_0@1`.
- Implementation: `src/cells/processes/betse_network_transport.py`.
- Independent oracle: `validation/transport/betse_network_transport_reference.py`.
- Native source/units/domain contract:
  `validation/transport/betse_network_transport_protocol.json`.
- Final component receipt:
  `/mnt/workspaces/Cells/betse-network-transport-development-20261028-04/result.json`.
  SHA-256 `464a4766e8dd2b8bd1f8090328cf4952b563684c122c20e2e8be5f9b35ac7922`.
- Final metadata receipt:
  `/mnt/workspaces/Cells/betse-network-transport-handoff-20261028-01/result.json`.

The final run passes **123 tests: 119 host and four CPU JAX**, with **39 actual
native expression captures** and **three preserved native failure captures**.
Compiled batch/scatter, independent-world rejection, near-stall differentiation
and empty-route kernels pass. Peak sampled process-tree RSS is **347,062,272 B**;
minimum available memory is **21,177,835,520 B**. The native child imports no Cells
or JAX. Every command ran on CPU7 with one BLAS thread, <=1-GiB RSS, >=8-GiB
reserve and a 180-s command limit. No GPU or persistent compilation cache ran.

## Integration API

`bind(configurations, species_ids, species_valence, inside, outside,
compartment_active, *, area_m2, temperature_K=298.15, route_capacity=None)` returns
`Topology, Parameters`. Configuration dictionaries use the native keys, including
the source spelling `transfered into cell` / `transfered out of cell`.

Species and transporter names must be unique; valences are integers in [-8,8],
including neutral species. Every active route has distinct, active inside and
outside owners, nonempty reactant/product lists and positive finite real
coefficients/Km values. The configured reaction must conserve charge. Additional
chemical moiety conservation and authoritative ionic/store/fuel ownership belong
to the composing model. A route can include explicit chemical conversion.

The topology has static `[route]` owners/masks and `[term, route]` substrate and
influencer arrays. `coefficient == 0` and `mode == 0` mark internal term padding.
`Parameters` contains maximum density, area, standard energy, reversible flags
and temperature. Empty route sets and extra route capacity are supported.

```python
valid = domain_valid(c_mM, vm_V, topology, parameters, availability, rho, xp=np)
result = rates(c_mM, vm_V, topology, parameters, availability, rho, xp=np)
n_dot_fmol_s = exchange_rates(result.extent_fmol_s, topology, xp=np)
```

Reject the trial before consuming rates when `valid` is false. Unchecked kernels
do not floor, clamp or repair active concentrations. Concentrations have shape
`[..., species, compartment]`; voltage and controls have shape `[..., route]`.
Temperature is scalar or `[..., 1]`, one temperature per independent world.
All kernels accept `xp=jax.numpy`; `domain_valid` returns one combined predicate
for the supplied arrays. Use `jax.vmap` over worlds for separate rejection flags.

Participating reactants/products stay strictly positive even when blocked.
Other active concentrations, including regulators, may be zero. Inactive
compartments are zero. Padding routes require zero voltage, availability, rho,
area, maximum density and standard energy, with `reversible=False`. Callers
supply these explicit control masks; the default scalar controls suit unpadded
routes. Raw invalid parameters are rejected even for empty route sets.

## Units and ownership

Concentrations/Km are mM (numerically mol/m3). Voltage is V, inside minus outside.
Maximum density and returned flux density are mol/(m2 s). Positive extent follows
the configured reactants to products. Reactants are consumed at their declared
owners and products appear at theirs. A transferred reactant is outside;
a transferred product is outside; other terms are inside.

`extent_fmol_s = flux_density_mol_m2_s * area_m2 / 1e-15`. `exchange_rates`
accumulates each coefficient once, in deterministic declared order, including
shared destinations. It also accepts integrated extents in fmol for endpoint
material accounting. `material_balances` compares endpoint amounts with those
explicit owner ledgers; it does not invent conserved species across reactions.

Native `net_z = sum(exported product nu*z) - sum(imported reactant nu*z)`.
`outward_current_density_A_m2 = F * net_z * flux_density` and the area-integrated
`outward_current_C_s` has the corresponding outward sign. Inside charge rate is
its negative for supported charge-conserving configurations. The component owns
no field solve, voltage state, geometry evolution or concentration stepping.

## Literal native semantics and limits

Pinned revision: `5269a714aa2593ed2a6708c4516289977d8ae1a2`; native
`networks.py` SHA `e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177`.
The external `native-source` directory retains source bytes, line ranges,
generated executable strings, inputs, outputs and failures. The capture executes
the actual `default_zones`, `get_influencers` and `write_transporters` methods.

- Forward loading multiplies reactant Hill saturation factors. Product-side Km
  is validated/retained but absent from the final executable expression.
- Literal Q uses `1e-3 * c**nu` for every list item, with the factor outside the
  power. The log-domain kernel preserves this; it does not substitute a corrected
  1-M standard-state expression.
- `None` / native string `"None"` standard energy selects the irreversible
  branch and removes voltage/Q reversal from the rate. Rho is a nonnegative
  native density multiplier. Availability in [0,1] is an explicit external
  multiplier, applied outside the generated expression in the captures.
- Ordinary activators multiply Hill factors; independent `!` activators add
  Hills, with a native baseline of one when no ordinary activator is present.
  Inhibitors multiply. Direct `&` concentrations form a signed sum. A direct
  inhibitor can make regulation and flux negative; that remains source behavior.
- The native transporter call ignores configured regulator zones and disables
  `*` voltage-sensitive Km requests. Regulator concentrations come from inside.
- Three native non-executable cases are rejected: reversible configurations with
  no transfer term; a direct inhibitor before another inhibitor; and simultaneous
  only-direct activator/only-direct inhibitor groups. Their generated strings and
  SyntaxError/TypeError evidence remain available.

`source_reaction_energy_J_mol` is a source diagnostic, zero for irreversible
routes. It is unsuitable as a physical heat/free-energy ledger: the literal Q
conversion and direct regulation do not establish thermodynamic consistency.
No implicit ATP demand, structural cost, water, osmotic particle term or reservoir
work is added. Explicit ATP species still require caller-owned fuel accounting.
Mitochondrial transport, profile targeting, `ignore ECM`, native geometry/shell
updates and whole-tissue equivalence are outside this component contract.

## Reproduction and retained failures

Run the existing new wrapper with a fresh output suffix:

```sh
taskset -c 7 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  agent-work/cells-worker-01/workfiles/check_betse_network_transport.py \
  --output /mnt/workspaces/Cells/betse-network-transport-development-NEW
```

Attempts 01--03 are preserved: the newly exposed native tuple failure; singleton
temperature handling and incorrectly mixed test units; then NumPy indices
entering compiled scatter. Final 04 fixes those issues. Dimensionless checks now
use their declared roundoff budget; density, energy, material and charge retain
their separate protocol tolerances. No follow-up regression or audit is running.
