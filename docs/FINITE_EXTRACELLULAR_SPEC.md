# One finite extracellular compartment

SPEC-008 / D055, 2026-09-10. **Design and instantaneous reference only.**
Accepted [CORE-008](../reports/CORE008_ACCEPTANCE.md), Cells 0.13.0, stays unchanged.
This is not a production family, time integration, timestep selection or biology
result. Current status lives in [Progress](../PROGRESS.md).

## Smallest useful boundary

N >= 1 fixed-volume well-mixed cells face one fixed-volume, well-mixed,
equipotential extracellular compartment. Each cell has one membrane capacitor,
the existing passive species permeation and optional synthetic Na/K pump, and
zero or one existing Kv1.5-style channel. Fixed selective cell-cell junctions
are optional. All share temperature and the declared species table. Geometry,
temperature and externally supplied pump drive are constant.

The outside now owns **actual species amounts**, not just concentrations or an
exchange ledger. There is no maintained reservoir, electrode, external material
source, extracellular capacitance to ground, or hidden neutralizing ion.
The ionic system is closed; externally driven pumps and isothermal dissipation
mean it is not a thermally isolated system or a complete metabolic model.

This is an intentionally reduced model. Charge-capacitor constraints and a
potential gauge are used in [Sætra and Mori's electrodiffusive network model](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012114).
Free-energy consistency is a central principle in
[Mori, Liu and Eisenberg's electrodiffusion/osmosis formulation](https://doi.org/10.1016/j.physd.2011.08.010).
Our single equipotential outside, fixed geometry and omitted fluid/field physics
are design choices, not a replication of either paper. This is only a bounded
step toward the spatial extracellular capabilities of
[BETSE](https://pmc.ncbi.nlm.nih.gov/articles/PMC4933718/), not parity with it.

## Input and ownership

Reference identity: `cells.finite_extracellular_reference@1`. The JSON root has
exactly `schema`, `species`, `temperature_K`, `extracellular`, `cells`, `junctions`.
Species records and local cell/membrane/channel/junction records retain
[SPEC-007's fields](PHYSICAL_IONIC_GRAPH_SPEC.md). There is no `bath` record.
Every membrane's `outside` binds the sole extracellular ID. The outside has
exactly `id`, `volume_pL`, `initial_amount_fmol` for every species and signed
`fixed_charge_equivalent_fmol`. It has no independent voltage anchor.

All IDs, roles, valences, kinetics, maps, duplicate/reversed-edge rules and
positive/finite domains are explicit as in SPEC-007. Fixed charge has no transport
route and does not assert a chemical identity or osmolarity. The resolver never
derives fixed charge to repair inputs, renormalizes concentrations, resets gates,
or silently turns a maintained bath into a finite one. The frozen panel reuses
old cell definitions but supplies each new outside inventory/charge explicitly.

Keep separate species, intracellular compartment, extracellular compartment,
membrane, channel and junction axes. This first topology has one membrane per
cell and one shared outside, but those counts are not a universal architecture
identity. The scalar reference uses immutable cell-/edge-major tuples; a later
production adapter must explicitly map them to numeric array axes.

Retain all nine [graph state fields](PHYSICAL_IONIC_GRAPH_SPEC.md#state-and-ownership)
and add `extracellular_amount[species]`. Transfers L, P, H and T remain separate
signed histories, not extra material. The outside has no second copy of L/P/H,
no cell-cell T contribution and no duplicate membrane dissipation. Checkpoints
must retain outside amounts and initial inventory/charge anchors even when an
observer does not request them. No checkpoint format changes in this slice.

## Floating capacitor-star closure

Let a = 1e-15 mol/fmol, q_f = a F, C_i = area_i * specific_capacitance_i,
n_si be intracellular amounts, n_so outside amounts, and X_i/X_o fixed-charge
equivalents in fmol. Concentrations in mM are n/volume_pL. The outside potential
phi_o = 0 is a **gauge choice**, not an imposed electrode clamp.

```text
Q_i = q_f [X_i + sum_s z_s n_si] = C_i (phi_i - phi_o)
Q_o = q_f [X_o + sum_s z_s n_so] = -sum_i C_i (phi_i - phi_o)
sum_i Q_i + Q_o = 0
V_i = Vref_i + (q_f/C_i) sum_s z_s (n_si - nref_si)
deltaV_edge = V_from - V_to
```

Initial cell anchors must satisfy the existing 1e-10 V consistency tolerance.
The explicit outside charge plus the initial capacitor charges must be zero
within 1e-20 C, as must the independently summed initial total charge. Retain
the reported rounding residuals. At a supplied state, the increment constraint
`q_f sum_s z_s (n_so-nref_so) + sum_i C_i (V_i-Vref_i) = 0` has the same
1e-20 C tolerance. No charge projection or counterion replacement is allowed.
Gauging every phi by the same constant changes no voltage, flux or energy.

The lumped net charges stand for opposing membrane-associated charge; this is
not a resolved space-charge or Debye-layer model. Do not additionally impose
exact zero total charge in each individual compartment: that would erase the
capacitor charge and contradict nonzero membrane voltages. No separate outside
capacitor energy may be added: each physical membrane capacitor is counted once.
Multiple external potentials, membranes per cell, electrodes or moving geometry
will require a new electrical closure, not a renamed version of this one.

## Same-stage exchange and feedback

Evaluate the unchanged GHK, synthetic pump and channel laws using **current**
inside and outside concentrations. Use the unchanged oriented junction law
between intracellular endpoints. For membrane inward flux Mdot_si and oriented
edge flux J_se, with incidence B_ie = -1 at source and +1 at destination:

```text
Mdot_si = Ldot_si + nu_si Pdot_i + sum_bound_channels Hdot_k
dn_si/dt = Mdot_si + sum_e B_ie J_se
dn_so/dt = -sum_i Mdot_si
dT_se/dt = J_se
dc_so/dt = (dn_so/dt) / volume_outside
```

Compute each membrane and edge once from the same complete state. Cell-cell
exchange never enters the outside inventory. Even without junctions, cells
sharing a finite outside are **not independent worlds**: changes to outside
chemistry can affect every membrane. Closing one membrane does not freeze the
outside; closing every membrane does. Inhibited membrane/junction gates keep
relaxing, and earlier transfer histories remain untouched.

Checks on supplied nonzero histories require, for every species:

```text
n_si - nref_si = L_si + nu_si P_i + sum_bound H_k + sum_e B_ie T_se
n_so - nref_so = -sum_i [L_si + nu_si P_i + sum_bound H_k]
(n_so-nref_so) + sum_i (n_si-nref_si) = 0
```

Material residuals and countercharge are separate checks: balanced but wrongly
reallocated neutral salt can satisfy charge while violating material history.
Circulating edge history can still be invisible to node amounts.

## Closed ionic free energy

At fixed volumes and temperature, choose c_star = 1 mM merely to make logarithms
dimensionless. For all inside compartments and the one outside:

```text
E = a RT sum_{compartment,s} n_s [log(c_s/c_star)-1] + sum_i C_i V_i^2/2
mu_si = RT log(c_si/c_so) + z_s F V_i
P_supplied = -a sum_i drive_i Pdot_i
dE/dt = P_supplied - sum_i Dm_dot_i - sum_e De_dot_e
(E-E_initial) + sum_i Dm_i + sum_e De_e + a sum_i drive_i P_i = 0
```

Energy in this display is J; retained dissipation state is pJ and converts by
1e-12. Gate conformational energy, gating charge, finite ATP pools, thermal,
osmotic and mechanical work remain omitted. Passive and synthetic pump-cycle
dissipation have the existing nonnegative sign convention. With no external
pump drive the resolved free energy is nonincreasing, not generally constant.
Fixed background charges add no changing chemical term at fixed geometry.

The old maintained-bath grand potential cannot be reused with c_so(t) substituted
into its denominator: differentiating that expression introduces additional
terms and omits the outside's chemical energy. Compare the **full finite-system
energy derivative** to independently summed interface dissipation and pump work.
Compute finite energy differences using anchored log1p expressions where useful;
do not subtract two enormous absolute reservoir energies unnecessarily.

## Reductions, limits and numerical gate

At identical initial concentrations, the finite model's intracellular/gate/
history derivatives match the maintained-bath graph. Its outside derivative is
the sum of membrane exchanges, not zero. For a fixed algebraically prescribed
transfer, enlarging outside volume while preserving initial concentrations
reduces concentration change exactly as 1/volume; resulting instantaneous local
rates approach the maintained-bath rates. This is a bounded arithmetic limit
check, **not** a uniform long-time convergence theorem or trajectory result.

All real inside/outside amounts stay strictly positive. Validate finite derived
concentrations, rates and energies; all gates lie in [0,1], every declared
species retains membrane/edge abs(z F deltaV / RT) <= 50 even when blocked,
and present Kv1.5 channels retain their voltage/temperature domain. No clipping,
amount floor, concentration refill or gate reset is allowed.

No timestep is inherited from CORE-008. A small shared outside adds feedback
and potentially faster depletion/stiff modes. **NUM-009** must separately freeze
short coupled trajectories, independent reference/refinement methods, events,
all ten state fields, outside depletion and charge constraints, whole-cubic
interior checks and prospective resources before **CORE-009** implementation.
Reference scalar constructors do not define padded production shapes yet.

For future GPUs, the common outside introduces a shared reduction: gather its
current solver-stage state, evaluate owned membrane transfers, sum once into
the outside update, and apply equal/opposite transfers to inside owners.
Independent vmap worlds each own a separate outside. Partitioned cells in one
world must not evolve private replicas of the same outside. Later spatial
compartments can distribute this ownership, but require explicit conservative
interfaces, mixing-resolution validation and a field/electrical closure. No
dense cell-cell matrix, GPU runtime or universal plugin framework is needed now.

## Frozen reference checks

The [panel](../configs/reference/finite_extracellular_v1.json) declares nine
synthetic cases, including one-cell volume variants, mono/divalent cells,
disconnected cells, a pair and shared-outside stars. Outside fixed charges are
declared once, not fitted or repaired during resolution. Its tolerances and
probes precede execution. The [checker](../scripts/check_finite_extracellular.py)
uses independent Decimal interface/energy calculations, maintained-bath
reductions, conservation and nonzero ledger/countercharge witnesses, storage
permutations and blocked-route separation. No production RHS or ODE solver is
an oracle. [Results](../reports/SPEC008_DESIGN_CHECK.md) retain failures and scope.

No extracellular mesh/PDE, water flow, swelling, barrier, organ preset, new
channel catalog, biological calibration, GPU optimization or deferred E02
campaign is started here.
