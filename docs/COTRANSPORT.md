# Conservative electroneutral cotransport

This standalone component adds manufactured, reversible KCC and NKCC routes.
It is a physical test law, with an assigned route capacity; it is not a fitted
isoform model or a claim of native BETSE KCC/NKCC equivalence. Tissue composition
and trajectory qualification are separate work.

## Physical contract

Both named routes use positive cycles **from outside to inside**. KCC moves one
K+ and one Cl- per cycle. NKCC moves one Na+, one K+ and two Cl- per cycle.
With species coefficients `nu_s`, ideal dilute concentrations `c` in mM, and a
shared isothermal temperature `T` in kelvin, define

```
A = R T sum_s nu_s [log(c_out,s) - log(c_in,s)]       J/mol
deltaG = -A                                        J/mol
J = capacity * availability * tanh[A / (2 R T)]      fmol/s
Qdot = 1e-3 * J * A                                 pJ/s
Gdot_chemical = -Qdot                               pJ/s
```

The positive coefficients describe inward material transfer; the outside loses
the same material. The law IDs are `kcc_reversible_tanh@1` and
`nkcc_reversible_tanh@1`, with the common kernel
`electroneutral_symport_reversible_tanh@1`. At equilibrium the concentration
products on the two sides agree. Reversing the gradient reverses the cycle
rate. `J*A >= 0` gives nonnegative dissipation. Temperature affects the molar
affinity and power; this chosen kinetic response depends on `A/(RT)`.

The thermodynamic concentration-product conditions follow primary KCC
[reversal experiments](https://journals.physiology.org/doi/10.1152/jn.2000.84.1.281)
and NKCC [thermodynamic and kinetic experiments](https://journals.physiology.org/doi/10.1152/jn.01007.2007).
The bounded tanh response is our explicit manufactured choice. For both
stoichiometries `sum_s z_s*nu_s = 0`, so electrical potential cancels from the
cycle affinity and direct transported current. There is no ATP reaction.
Subsequent channel currents can respond to changed ionic concentrations.

The same species uses the same standard chemical potential on both sides;
standard-state factors cancel. The component assumes ideal activities and a
single temperature per independent world. It omits binding states, isoform
regulation, inhibitors, substrate-dependent turnover saturation, solvent drag
and biological parameter calibration.

## Pinned BETSE source correspondence

Inspected BETSE **v1.5.0**, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. The installed readable package
under `/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/betse`
matches the source checkout `/mnt/workspaces/Cells/betse-v1.5.0` for all files
listed below. A case-insensitive search of that package found no named KCC or
NKCC implementation. This is a statement about the inspected revision.

The [generic network builder](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/chemistry/networks.py)
reads user transporter definitions in `read_transporters` (line 924), generates
expressions in `write_transporters` (line 2090), and runs them in
`run_loop_transporters` (line 2985). For a reversible configured route, its
executable expression has the form

```
flux = rho_pump * vmax * alpha
       * product_reactants [(c/Km)^nu / (1 + (c/Km)^nu)]
       * (1 - Q/Keq)
Keq = exp[-(deltaG0 + electrical_transfer_energy)/(R*T)]
```

It uses a molar reaction quotient (concentration factors scaled by `1e-3`),
configuration-driven transferred-side tags, and flux density in mol/(m2*s).
The geometric material update lives outside this expression. For an inward
electroneutral symport with `deltaG0=0`, `Q=product(c_in/c_out)^nu` and
`Keq=1`. Its signed direction agrees with the chemical affinity, while its
kinetic magnitudes and saturation differ from our tanh law. The generated
executable expression does not use the separately constructed product-side
saturation coefficient. `standard free energy: None` chooses the irreversible
branch and is outside the proposed reversible contract.

The [default configuration](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/sim_config.yaml)
leaves custom transporters empty. The
[extra configuration template](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/data/yaml/extra_configs/extra_config_template.yaml)
declares generic reactants/products, multipliers, Km, transfer direction,
maximum flux and standard free energy. Its general comment about positive
outward flux cannot replace the actual configured transferred-side semantics;
the example itself transfers a reactant inward.

| Pinned file | SHA-256 |
| --- | --- |
| `betse/metadata.py` | `6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1` |
| `betse/science/chemistry/networks.py` | `e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177` |
| `betse/data/yaml/sim_config.yaml` | `7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415` |
| `betse/data/yaml/extra_configs/extra_config_template.yaml` | `2dd1322fdab1dff7d7b9b1d90894d27e5f8357bf37b30050c2ae8c10e91492b7` |

Source probes execute the pinned generic expression generator on
manufactured configurations and save its generated expressions, exact inputs,
outputs and source/version hashes. They remain separately labelled from the
manufactured tanh contracts; they do not run a native tissue simulation.

## Array and ownership interface

`Topology` declares species valences, active compartments, inside/outside
compartment indices, a `[species, route]` stoichiometry and active routes.
`named_stoichiometry` binds explicit species IDs and valences to a named law;
species order is arbitrary. Runtime `Parameters` hold capacity in fmol/s and
temperature. Host validators check shapes, finite numeric types, neutral
stoichiometry and safe ownership. The numerical kernels contain no geometry
or integrator.

Concentrations have shape `[..., species, compartment]`. Capacity and
availability broadcast to `[..., route]`. Temperature has a singleton final
axis `[..., 1]`, so it is common to all routes within one world. Leading axes
broadcast as independent worlds; they are never summed together. Every active
compartment requires finite, strictly positive concentrations for every
declared species, including when availability or capacity is zero.

Inactive compartments contain exactly zero concentrations. Inactive routes
have zero stoichiometry, capacity and availability, with safe in-range owner
indices; masked neutral log arguments are used only for padding. Active
substrates are never floored or replaced. Temperature must remain within
200--400 K. Any nonfinite computed rate or power is outside the domain.

`domain_valid` is a compiled-compatible trial predicate; `rates` is an unchecked
pure calculation for valid inputs. `exchange_rates` scatters each signed route
transfer once to its two owners. `material_balances` reconstructs integrated
material from signed cycles and exposes per-species residuals. The composing
model must integrate signed cycle counts, per-species transported amounts and
dissipation exactly once, use its own amount/volume state, reject invalid
integration stages and retain its existing material/energy tolerances.

The general topology validator accepts bounded integer valences (-8 through 8,
excluding zero) and inward coefficients 0, 1 or 2. Every active route must be
nonempty and electrically neutral, with distinct active owners; every index,
including an inactive one, must be safe. The named-role helper additionally
requires the actual Na+/K+/Cl- valences and unique species IDs. An empty route
axis preserves the declared compartments and their concentration domain.

For example, a manufactured KCC route can be evaluated on the host as follows:

```python
import numpy as np
from cells.processes import cotransport as ct

z = np.array([1, -1])
nu = ct.named_stoichiometry(("K", "Cl"), z, ct.KCC_LAW_ID)
topology = ct.validate_topology(ct.Topology(
    z, np.array([True, True]), np.array([0]), np.array([1]),
    nu[:, None], np.array([True]),
))
parameters = ct.validate_parameters(ct.Parameters(0.25, 298.15), topology)
concentrations = np.array([[140.0, 4.0], [10.0, 120.0]])
availability = np.array([1.0])
assert ct.domain_valid(concentrations, topology, parameters, availability, xp=np)
rates = ct.rates(concentrations, topology, parameters, availability, xp=np)
amount_rates = ct.exchange_rates(rates.cycle_fmol_s, topology, xp=np).amount_fmol_s
# This gradient gives negative cycles: KCl moves from compartment 0 to 1.
```

The return fields include signed cycles, affinity, reaction free energy,
per-species route transfer, heat, chemical power and direct charge rate.
`exchange_domain_valid` checks supplied rates or integrated extents before
`exchange_rates` or material replay. Despite the `_s` field names in
`ExchangeRates`, passing cycle integrals in fmol reconstructs amounts in fmol;
the routine is linear and performs no integration. For multiworld arrays,
route parameters must explicitly retain their final route axis and temperature
its singleton axis, for example `capacity[None, :, :]`, `T[:, None, None]` and
`concentration[:, None, :, :]` to produce two broadcast world axes.

## Verification and limits

The [component protocol](../validation/transport/cotransport_protocol.json)
declares dimensional tolerances, source hashes, resource bounds and selectors.
Host contracts use an independent 80-digit Decimal implementation based on
concentration products, not the production log-sum/tanh implementation. A
finite-difference derivative of the closed ideal ionic free energy checks
chemical loss against heat, with a third-derivative and rounding error bound.
Owner permutations, shared sources/sinks, actual multiworld inputs and neutral
material corruption exercise accounting beyond a sum-of-rates identity.

CPU JAX contracts are separately selected after the required resource handoff.
They check eager/JIT/vmap broadcasting, the analytic stall derivative,
automatic-differentiation chemical power, strict compiled rejection and empty
route accumulation. No compiled tissue trajectory or GPU qualification belongs
to this standalone component delivery. Per-run evidence and preserved failures
are linked from the worker's [work log](../agent-work/cells-worker-01/WORK_LOG.md).
