# Finite cytosol/ER calcium

`er_calcium@1` couples one fixed-volume cytosol/ER pair to the existing ideal
reaction-network chemistry. The [example](../configs/er_calcium_buffered.json)
has finite free/bound calcium, a two-site buffer in each compartment, potassium
counterflow, an ER capacitor, a calcium pump and calcium-dependent release.
All parameter values are synthetic verification inputs. See
[`PROGRESS.md`](../PROGRESS.md) for qualification status and artifacts.

This contract and the [protocol](../validation/chemistry/er_protocol.json)
address the added scientific risks: transported charge must determine voltage,
the finite inventories must include reaction and transport changes together,
and pump work must close the chemical/electrical energy balance.

Each RK4 trial evaluates all local reactions and membrane routes on the same
current state. Positive signed transport goes from cytosol to ER. Species use
fmol, compartments pL, concentrations mM, areas m², permeability m/s and voltage
`V_ER - V_cytosol` in volts. The capacitor is `C = area * specific_capacitance`.
Voltage is derived from the change in ER mobile charge:

```text
V = V0 + F*1e-15/C * sum(z * delta_n_ER)
mu_ER - mu_cyt = R*T*log(c_ER/c_cyt) + z*F*V
```

Constant immobile background charges reconcile each declared initial inventory
with `+C*V0` in the ER and `-C*V0` in the cytosol. They are recorded in the complete
layout and summary and never change. Passive and release currents use the
existing GHK process. Every transfer increments the ER store and decrements its
cytosol owner by the same amount. Named conserved moieties are checked globally;
local conservation includes the recorded membrane transfer. Local reactions
still conserve charge individually.

The pump law `betse_1_5_er_calcium_pump_positive@1` reproduces the positive-domain
formula in the pinned
[BETSE `pumpCaER`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim_toolbox.py).
Its capacity is total calcium fmol/s (native mol/m²/s times membrane area and
`1e15`). ATP/ADP/Pi are explicitly maintained, with the native numerical **mM**
quotient, equivalent to a 1-mM standard state for the supplied standard energy:

```text
drive = delta_g0 + R*T*log(ADP*Pi/ATP)       [J/mol, numeric mM quotient]
g = drive + (mu_Ca_ER - mu_Ca_cyt)
pump = capacity * availability * Ca_cyt/(KmCa+Ca_cyt)
       * ATP/(KmATP+ATP) * (1-exp(g/(R*T))) [fmol Ca/s]
```

The implementation uses log saturation and `expm1` near reversal. Positive
forward pumping contributes external work `-drive * transferred_fmol * 1e-3`
in pJ; reverse pumping can return work. This specific source law treats one
calcium transfer per formal reaction. It must not be interpreted as a biological
two-calcium SERCA cycle or proton countertransport model; compare the more
detailed [Tran et al. thermodynamic SERCA model (2009)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717298/).
The existing Na/K pump's 1-M convention remains unchanged.

`betse_1_5_er_calcium_release@1` reproduces the calcium-only branch of the pinned
[ER channel function](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/organelles/endo_retic.py):
activation `a/(1+a)` times inhibition `1/(1+h)`, where
`a=(Ca_cyt/K_activation)^n_activation` and
`h=(Ca_cyt/K_inhibition)^n_inhibition`. This instantaneous fraction multiplies
calcium GHK permeability. It introduces no gate state, IP3 dependence or gate
energy. Pump, release, passive and local-reaction controls have independent
explicit multipliers; their union of switch times splits the solver grid.

The state records local reaction extents/dissipation, species-specific passive
transfer, pump and release transfers, and dissipation for the three transport
routes. Summed ideal chemical free-energy change, capacitor energy change,
dissipation and supplied pump work must balance to `1e-9 pJ`. Amounts stay
strictly positive, `|V| <= 0.15 V`, and present-pump affinity stays within `80 RT`.
Every RK4 trial/endpoint is checked. A conservative loss bound uses the combined
conserved pools and the full declared voltage interval; actual step times that
bound must be at most `0.25`, and steps cannot exceed 50 microseconds. Independent
reference/refinement tests remain necessary; these domain checks do not prove
trajectory accuracy. No concentration clipping or repair is applied.

Observation cubics use interval-local controls, check amount/voltage extrema,
conservatively bound pump affinity from those extrema, and check dissipation
bounds. Sampling never affects accepted steps. Scalar, batch/window execution
and complete checkpoints use the ordinary CPU/GPU APIs. One ER pair per world
keeps ownership and voltage unambiguous. The separately identified
[spatial calcium model](SPATIAL_CALCIUM.md) composes these stores with plasma
transport and assembly-controlled channels; multiple ER stores within one cell
remain separate work.

Qualification reuses the established detached runner:

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  validation/assembly/qualify_cell.py launch \
  /mnt/workspaces/Cells/er-YYYYMMDD-NN --chemistry --chemistry-case er
```

The runner freezes source/config/test inputs and authenticated BETSE source
files, then checks the native functions, independent DOP853/Radau trajectories,
refinement, interventions, reduction to closed chemistry, exact replay, CPU/L4
agreement and existing regressions. Function correspondence uses harmonized
physical constants. It is separate from native BETSE initialization and
split-step trajectory parity. No throughput or follow-up job starts automatically.
