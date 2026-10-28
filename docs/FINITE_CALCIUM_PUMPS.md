# Finite-pool calcium-pump adapters

The two new laws `finite_atp_pmca_betse_positive@1` and
`finite_atp_er_1ca_betse_positive@1` feed current finite ATP/ADP/Pi concentrations
to the existing positive-domain PMCA and ER kernels. Each signed formal cycle
transfers **one Ca** and hydrolyses **one ATP**. Negative cycles reverse calcium
transfer and synthesize ATP. The ER identity is the existing formal one-Ca
source law; it makes no physiological two-Ca SERCA or proton-transport claim.
NCX has no ATP demand in this adapter.

## Standard-state reconciliation

The finite pool retains its declared 1-M transformed convention, with buffered
pH/Mg/solvent assumptions and no resolved metabolite electrical charge:

```text
g_pool = deltaG0_1M + RT ln(ADP_mM*Pi_mM/(1000*ATP_mM))
```

The unchanged calcium kernels use a numeric-mM quotient. Only the standard
energy argument passed to those kernels changes:

```text
deltaG0_1mM = deltaG0_1M - RT ln(1000)
g_old      = deltaG0_1mM + RT ln(ADP_mM*Pi_mM/ATP_mM) = g_pool
```

The conversion uses **each referenced owner's temperature**. Owner standard
energies, chemical potentials and free energies stay unchanged. The existing
Na/K pump already uses the 1-M convention and receives no conversion. Calling
the old maintained calcium law with explicitly converted standard energy and
the same live concentrations reproduces this adapter's rate and energies.
Existing named laws and maintained configuration meanings stay unchanged.

## Pure interface and signs

`PumpParameters(capacity_fmol_per_s,km_ca_mM,km_atp_mM)` contains kinetics only;
it does not carry a second metabolic reservoir or owner temperature. Pool
parameters and `Routes(owner,active)` reuse `finite_energy`. Amounts are
`[...,3,owner]` in ATP/ADP/Pi order, volume is `[...,owner]` pL, concentrations
are mM, voltage is V and energies are J/mol formal cycles. Route data and
controls use `[...,route]` with independent leading worlds. Shared owners and
empty route lists are supported. Extra world axes are explicit; a single
route with several controls uses `[world,1]`.

`pump_parameters(amount,volume,p,routes,pump)` returns the existing
`er_calcium.PumpParameters` with live owner substrates and converted standard
energy. It is an instantaneous bridge and never updates state.

`pmca_rates` and `er_rates` accept, in order:
`source,destination,voltage,amount,volume,p,routes,pump,availability`.
They call the existing source kernels. Positive PMCA cycles move calcium from
cytosol to outside; PMCA voltage is source minus destination, the usual Vm.
Positive ER cycles move calcium from cytosol to ER; ER voltage is destination
minus source. Their transport free energies are therefore:

```text
PMCA: dmu = RT ln(Ca_destination/Ca_source) - 2 F Vm
ER:   dmu = RT ln(Ca_destination/Ca_source) + 2 F V_ER
E = g_pool + dmu
J = capacity * availability * Ca_source/(KmCa+Ca_source)
    * ATP/(KmATP+ATP) * (1-exp(E/(RT)))
```

The inherited stable log/expm1 implementation avoids cancellation near stall.
The adapter does not add a new kinetic fit. `Rates` contains signed
`cycles_fmol_s`, reaction/hydrolysis/transport energies, nonnegative
`dissipated_power_pJ_s`, signed `pool_chemical_power_pJ_s` and signed
`transport_power_pJ_s`. For a valid route, including reverse operation:

```text
pool_chemical_power = 1e-3 J g_pool
transport_power    = 1e-3 J dmu
heat               = -1e-3 J E >= 0
pool_chemical_power + transport_power + heat = 0
```

The former maintained-reservoir metabolic work is an internal transfer when
the finite pool is present. Adding it again as external supplied energy would
double-count the source. Variable pool volume requires the existing explicit
finite-energy volume derivative; these isolated checks fix volume.

`pool_exchange(cycles,routes,p)` calls the existing finite exchange once with
an explicit empty regeneration axis. It scatters the already computed signed
cycles in route order to `(-J,+J,+J)` for ATP/ADP/Pi. Calcium source/destination
amount rates are `(-J,+J)`. Gross hydrolysis/synthesis are diagnostics, not
additional demand. Adenylate `ATP+ADP` and phosphorus `3ATP+2ADP+Pi` are conserved.

In a complete composition, concatenate PMCA, ER, Na/K and any other declared
ATP-consuming routes before one `finite_energy.exchange_rates` assembly with
the separately declared synthesis ports. Do not add this convenience result
and feed the same cycles to that assembly again. Calcium compartments,
membrane charge/capacitors, osmolytes and checkpoints belong to the composing
model; the adapter supplies no hidden scatter or state mutation for them.

## Strict trial domain

Call `domain_valid(...,kind='pmca'|'er')` before physical use of the unchecked
kernels. Active finite owners require positive finite ATP, ADP, Pi and volume
under the unchanged pool contract. A present but blocked route retains these
requirements. Route Ca and Km values are positive; capacities are nonnegative
and availability is in [0,1]. Numeric booleans, nonfinite values, malformed
owner/route axes, unsafe owner indices and active references to inactive owners
are rejected. The computational bounds are 200--400 K, |V| <= 0.15 V and
|E/(RT)| <= 80, with finite rates and powers. Blocking does not excuse an
out-of-range affinity or malformed physical input.

Inactive owners retain finite_energy's neutral values. Inactive route slots
require safe owner indices, Ca=Km=1 and voltage=capacity=availability=0; bridge
substrates are one and converted standard energy is zero. All returned rates,
energies and powers are zero there. Empty route lists still require valid
owners and reject nonfinite scalar controls. There are no concentration floors,
clipping, ATP resets or zero-substrate continuation. Invalid stages must be
rejected by a later solver.

## Independent evidence and physical clock

The [protocol](../validation/chemistry/finite_calcium_pump_protocol.json)
declares conventions and budgets. The separate
[Decimal reference](../validation/chemistry/finite_calcium_pump_reference.py)
imports no Cells, NumPy or JAX code. Contracts compare old maintained reductions
with the explicit transform, different-temperature owners, mixed PMCA/ER routes
sharing one owner, signed material/energy proofs, stalls, reversal, blockers,
padding, ordering, empty arrays and actual two-by-three independent worlds.

A manufactured finite-fuel path holds equal calcium concentrations and zero
voltage using equal-potential calcium reservoirs. This is a pool experiment,
without a closed calcium-tissue claim. It starts with ATP/ADP/Pi=.8/.2/.2 fmol,
unit pL, 298.15 K and deltaG0_1M=RT ln1000. The capacity is .1 fmol/s,
KmCa=Ca=1 mM and KmATP=.5 mM. ATP depletes toward the positive interior stall
`(3-sqrt5)/2` fmol; it never reaches zero. This manufactured positive standard
energy is selected for a resolvable interior equilibrium, not biological fit.

For recovery, the calcium pump is blocked and the existing finite-energy
regeneration port supplies RT ln16 per cycle at .05 fmol/s. ATP approaches
`(33-sqrt65)/32` fmol. Both phases last twelve **derived local relaxation times**;
state and heat/work quadrature refine at 24/48/96 steps per phase against an
independent 1536-step Decimal rational-equation integration. Conservation uses
retained signed reaction extents, with no state repair. The complete path checks
finite stage pools and the first law including the explicit regeneration supply.
Durations and errors are saved in machine-readable evidence.

Host tests select `tests/unit/test_finite_calcium_pumps.py -k 'not jax'`.
Two separate CPU JAX prototypes select `-k jax`, after coordinator clearance.
The worker's [log](../agent-work/cells-worker-01/WORK_LOG.md) links receipts and
preserved failures. Core/model integration, coupled calcium/ER trajectories,
biological calibration and GPU qualification are separate work.
