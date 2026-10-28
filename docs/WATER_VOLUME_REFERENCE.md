# Water and volume: independent reference and source correspondence

Reference work reviewed on **2026-10-28**. This note owns the reference equations,
source findings and reference-test evidence. [Progress](../PROGRESS.md) owns the
production implementation and CPU/L4 qualification status.

## Declared physical model

The first Cells component is a closed graph of well-mixed, finite compartments.
Neutral solvent crosses explicitly owned interfaces. Water transport changes
compartment volumes and concentrations, while leaving each solute amount
unchanged. Ionic transport may change those amounts through its existing routes.
Areas, capacitances and topology remain fixed. This is a compliant-compartment
approximation, not a resolved shape or fluid-velocity model.

Volumes use pL, amounts fmol, pressure Pa, energy pJ and time seconds. An amount
divided by volume is numerically mM, equivalently mol/m³. Each declared ion and
impermeant osmolyte contributes one ideal osmotic particle. Impermeant particle
counts are explicit; fixed-charge equivalents do not determine them.

For node `i`, with current volume `V`, reference volume `Vref`, nonnegative
modulus `K`, and static pressure offset `P0`:

```text
Pi_i = R*T * (sum_s n_si + n_impermeant_i) / V_i
P_i  = K_i*(V_i/Vref_i - 1) + P0_i
U_i  = 1e-3 * [K_i*(V_i-Vref_i)^2/(2*Vref_i) + P0_i*(V_i-Vref_i)]
Fmix = 1e-3*R*T * sum_i,sum_particles n_i*[ln(n_i/(V_i*1 mM)) - 1]
```

The zero-amount contribution to `Fmix` is its exact zero limit. Concentrations
and volumes are never clipped to logarithm floors. For a directed edge `a→b`:

```text
Delta = (P_a - Pi_a) - (P_b - Pi_b)
Q_ab  = 1e15 * area_m2 * Lp_m_per_Pa_s * availability * Delta   [pL/s]
dV_a/dt -= Q_ab;  dV_b/dt += Q_ab
D_ab  = 1e-3 * Q_ab * Delta                                  [pJ/s]
```

The defining derivative is `d(Fmix+U)/dV_i = 1e-3*(P_i-Pi_i)`.
Consequently, pure-water exchange conserves total volume and satisfies
`d(Fmix+U)/dt = -sum_edges D_ab`, with nonnegative dissipation. Common pressure
offsets do not change exchange in a closed graph. The solvent is treated as
incompressible and solute partial volumes are neglected; this volume ledger is
not a separately resolved count of water molecules.

The water-potential and energy approach follows the thermodynamic structure of
[Mori's multidomain electrodiffusion/osmosis model](https://arxiv.org/abs/1410.8391).
The relationship among entropic, elastic and electrostatic energies is also
developed by [Mori, Liu and Eisenberg](https://arxiv.org/abs/1101.5193).
The present graph and linear pressure law are declared Cells choices; neither
paper's full spatial model or biological parameterization is reproduced here.

## What pinned BETSE actually executes

The inspected checkout is BETSE **1.5.0**, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. The checkout was clean; the five
inspected installed Python files match that checkout byte-for-byte.

| Source | Active behavior and correspondence boundary |
| --- | --- |
| [`pressures.osmotic_P`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/pressures.py#L10) | Sums `R*T*concentration` over ions and enabled molecule/GRN species. The exterior value is a cell-to-ECM lookup or an unweighted membrane-count average. It computes exterior-minus-interior osmotic pressure, a water-velocity quantity, its divergence and a network pressure quantity. |
| Same function, lines 62–90 | The volume change, concentration dilution and membrane/ECM volume reassignment code is commented out. An active conservative changing-volume trajectory cannot be calibrated against this inactive block. |
| [`parameters.py`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/parameters.py#L829) | Osmotic pressure can be enabled; `fluid_flow` and time-dependent deformation are forced off by this loader. Source viscosity, membrane thickness and conductivity choices are recorded as source parameters, not measured calibration data. |
| [`sim.py`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim.py#L1344) | The ordinary loop calls osmotic pressure after molecule/GRN updates and before `update_all_concs` and `update_V`. This order is distinct from the Cells common-stage physical-time model. |
| [`deform.py`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/deform.py#L250) | Displacement is applied to a copied geometry for saved observations. Rebuilding the physical simulation geometry is commented out in that path. This is separate from conservative osmotic volume evolution. |

The native velocity uses the literal coefficient
`(aquaporins/mu_water)*(3e-10)**2/tm` and multiplies it by
`Pi_out - Pi_cell - P_cells`. Its nearby comment and inactive volume-update code
use inconsistent descriptions of the velocity sign. For zero `P_cells`, the
pressure-gradient sign agrees with the Cells **outward** flow convention. The
native subtraction of `P_cells` is not silently reinterpreted as the explicit
Cells intracellular-minus-extracellular hydrostatic pressure law.

The [unmodified native probe](/mnt/workspaces/Cells/water-volume-reference-20261028-01/native-source-probe.json)
retains six prescribed-carrier snapshots, including both exterior mappings,
additional molecule/GRN osmolytes and nonzero `P_cells`. All volume and
concentration arrays remain unchanged. The
[reference comparison](/mnt/workspaces/Cells/water-volume-reference-20261028-01/native-reference-comparison.json)
passes eight instantaneous zero-`P_cells` cell cases with matched constants:
maximum pressure error **1.17e-10 Pa** and volume-flow error **8.89e-16 pL/s**.
These are component/source checks, not native whole-simulation trajectories or
independent biological observations. Native source is not copied into Cells.

## Independent reference interfaces and checks

[`water_volume_reference.py`](../validation/tissue/water_volume_reference.py)
implements an 80-digit Decimal pressure, flow and energy oracle. Its unpadded
case arrays identify initial/reference volumes, solute and impermeant amounts,
moduli, pressure offsets and directed interfaces. `evaluate` optionally accepts
current volumes and solute amounts. `integrate` supplies a DOP853 **water-only**
history with fixed solute amounts. Exact two-compartment elastic relaxation and
a bracketed osmotic-equilibrium solve provide additional references.

[`surface_water_reference.py`](../validation/tissue/surface_water_reference.py)
adds four volume/transfer/dissipation fields to a separate 12-field independent
ionic context. Current volumes enter the ionic concentration calculation at
every stage. Water availability follows its own right-continuous schedule.
The adaptive solver splits at the union of membrane, junction and water events;
it preserves unit-specific tolerances and the complete 16-field state. Its
instantaneous energy proof includes ionic chemical work, capacitor work, ionic
dissipation and the water contribution. Fixed capacitance means no electrical
work arises directly from changing volume in this declared approximation.

Both reference modules avoid production Cells and JAX imports. The
[reference tests](../validation/tissue/test_water_volume_reference.py) passed
**17 cases** in the [frozen CPU run](/mnt/workspaces/Cells/water-volume-reference-20261028-01/checks-03/result.json):
energy-gradient consistency, analytic osmotic equilibrium, swelling/shrinkage,
amount-preserving dilution, exact elastic relaxation, tightened references,
reversed/subdivided interfaces, sealed/disconnected compartments, invalid domains,
separate ionic ownership, independent clocks, zero-water reduction and complete
coupled energy/material accounting. Worker peak RSS was **86 MiB**, on CPU 6;
no GPU was used. The native probe peaked at **100 MiB**.

The [initial wrapper failure](/mnt/workspaces/Cells/water-volume-reference-20261028-01/checks-01/failure.json)
is retained: a missing runner import path stopped it before any tests executed.
The corrected wrapper changed no physical equations or numerical tolerances.

## Active transport with compliant volumes

[`surface_water_kinetic_reference.py`](../validation/tissue/surface_water_kinetic_reference.py)
extends the independent `resolved_tissue@7` shared-channel, maintained-pump and
kinetic-junction equations to `resolved_water@2`. Its separate ionic context
retains 19 fields; the complete context has 23. Current volumes enter passive,
channel and pump concentrations at every stage. `bind`, `initial`, `flatten`,
`unpack`, `evaluate` and `integrate(raw, refinement=1)` match the passive-water
reference interface. DOP853 splits at the union of all five control families;
its maximum step is `1e−5/refinement` s, alongside tighter error tolerances.
The unscaled source-channel catalog requires exactly **298.15 K**; other
temperatures are rejected instead of assuming an unverified temperature law.

For these closed finite compartments, the independent energy proof is

`d(F_mix + U + E_capacitor)/dt + D_passive + D_channel + D_pump + D_water − P_ATP = 0`.

The maintained chemical input is `P_ATP = −1e−3 Σ J_cycle ΔG_ATP`, with the
canonical 1-M standard state:
`ΔG_ATP = ΔG° + RT ln(ADP_mM Pi_mM / (1000 ATP_mM))`.
ATP/ADP/Pi are external maintained support, counted once as chemical work and
excluded from finite osmolyte inventories. The inherited phenomenological gates
have no new energy store. Calcium is an ordinary mobile ion here; this composition
does not include calcium stores/buffers, finite ATP pools or moving geometry.

The [independent tests](../validation/tissue/test_water_kinetic_reference.py)
passed **17 cases** in the
[frozen CPU check](/mnt/workspaces/Cells/water-kinetic-reference-20261028-01/checks-02/result.json),
with [inputs and source hashes](/mnt/workspaces/Cells/water-kinetic-reference-20261028-01/checks-02/inputs.json)
and [saved checks/trajectory evidence](/mnt/workspaces/Cells/water-kinetic-reference-20261028-01/checks-02/evidence).
They cover current-volume coupling, the ATP standard state, independent clocks,
absent/sealed routes, shared membrane owners with a junction and extracellular
face, domain/temperature rejection, the production example's event states, and a complete
50-µs trajectory with tighter-reference and energy/material checks. The worker
used **87 MiB** peak RSS on CPU 6, completing in **4.78 s** without Cells/JAX
imports or GPU use. These are synthetic reference checks, not new native BETSE
volume trajectories, wetlab validation or production GPU qualification.

The [earlier check](/mnt/workspaces/Cells/water-kinetic-reference-20261028-01/checks-01/result.json)
is retained. It preceded the explicit channel-temperature guard and smaller
adaptive step bound; its accepted 310-K example is outside the corrected scope.

## Finite pools with compliant water

[`surface_energy_water_reference.py`](../validation/tissue/surface_energy_water_reference.py)
independently composes finite ATP/ADP/Pi with water for
`resolved_energy_water@1`. The explicit `neutral_ideal_atp_adp_pi@1` declaration
adds live pool particles to osmotic pressure, alongside ions and background
impermeants. Current volume enters ionic, pump and regeneration laws. Pool
metabolites add no ionic charge in this declared approximation; transformed
pH/Mg and solvent assumptions remain. The separate 23-field finite-energy and
19-field ionic contexts are preserved; the complete state has 28 fields.

The additional signed per-cell ledger integrates
`Wvol_dot = −1e−3 RT (ATP+ADP+Pi)/V * V_dot`. The pool check is
`Delta Gpool + Wpump + Dregen − Wregen − Wvol = 0`.
The full balance contains pool free energy once and counts regeneration supply
as external input; pump and volume work are internal transfers. Endpoint dilution
uses current pool amounts, but cannot replace the path-dependent `Wvol` integral
when reactions change their particle count. The water stiffness bound uses
`N_pool < 2 ATP_initial + ADP_initial + Pi_initial`, derived from conserved
adenylate and phosphorus inventories, rather than the initial particle count.

The [independent checks](../validation/tissue/test_energy_water_reference.py)
passed **27 cases** in the
[frozen CPU run](/mnt/workspaces/Cells/energy-water-reference-20261028-01/checks-01/result.json).
[Inputs/source hashes](/mnt/workspaces/Cells/energy-water-reference-20261028-01/checks-01/inputs.json)
and [saved trajectory evidence](/mnt/workspaces/Cells/energy-water-reference-20261028-01/checks-01/evidence/adaptive-history.json)
retain all six control clocks, shared owners, signed work, invalid domains, an
omitted-pool-pressure negative control, all seven coordinator arms, and temporal
refinement. Maximum full-energy and internal-pool residuals on the synthetic
trajectory were **1.46e−12 pJ** and **4.74e−15 pJ**, respectively.
The run used CPU 6, **89 MiB** peak RAM and **81 s**, without Cells/JAX imports or
GPU use. This establishes independent-reference evidence; production execution
and biological calibration retain their separate qualification requirements.
