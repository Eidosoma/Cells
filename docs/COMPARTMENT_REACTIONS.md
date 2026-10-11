# Closed compartment chemistry

`compartment_reactions@1` adds fixed-volume, compartment-owned reaction networks
to the ordinary Cells CPU/GPU solver. The example
[`calcium_buffer_compartments.json`](../configs/calcium_buffer_compartments.json)
contains two independent cytosols with sequential binding
`Ca + B ⇌ CaB` and `Ca + CaB ⇌ Ca2B`. Its rates, standard potentials, amounts and
volumes are **synthetic verification inputs**, not measurements or a calibrated
calcium model. Current qualification status and artifacts are in
[`PROGRESS.md`](../PROGRESS.md).

This contract and the independent reference address a new scientific risk:
reaction networks can conserve material while violating thermodynamics if their
forward/reverse constants are inconsistent around cycles. Here reverse rates
derive from species standard chemical potentials. The thermodynamic framework
is ideal, isothermal deterministic mass action; see
[Rao and Esposito, Physical Review X 6, 041064 (2016)](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.6.041064).
The model is a closed-system subset, with no reservoirs or chemical work input.

For species amount `n` in fmol, volume `V` in pL and standard concentration `c0`
in mM, activity is `a = n / (V*c0)`. For each local reaction, `nu` is products
minus reactants, `mu0_RT` is the species standard potential divided by `R*T`, and
the supplied forward constant has units `1/s` **at the declared standard
concentration**:

```text
kr = kf * exp(sum(nu * mu0_RT))
jf = V*c0*kf*control*product(a**reactants)   [fmol/s]
jr = V*c0*kr*control*product(a**products)    [fmol/s]
dn/dt = nu * (jf-jr)
affinity_RT = -sum(nu * (mu0_RT + log(a)))
dD/dt = R*T*1e-3*(jf-jr)*affinity_RT        [pJ/s]
```

Forward and reverse rates share a prescribed multiplier in `[0,1]`; it changes
the kinetic barrier, adds no material and leaves the equilibrium unchanged.
Controls are held constant within each integration interval and switches split
the time grid. The implementation uses a stable `expm1` difference near
equilibrium. Standard potentials determine all equilibrium ratios consistently.

Each species declares nonnegative integer counts of conserved moieties plus an
integer charge. Every reaction must conserve every moiety and charge exactly.
Each reaction has one compartment owner; no reaction moves material between
compartments. Initial amounts must be strictly positive, with no clipping or
concentration floor. Finite conserved pools bound concentrations and loss rates;
the largest actual timestep times the conservative loss bound must not exceed
`0.25`. Every RK4 trial and endpoint checks the positive finite domain. An
unstable or inaccurate input is refused instead of silently repaired.

State includes amount increments from the initial state, signed reaction
extents and per-reaction accumulated dissipation. Checks compare amount changes
to stoichiometric extents, local moieties, local charge, and the ideal free-energy
change plus dissipation. Energy is checked per compartment at `1e-9 pJ`; the
qualification also requires independent trajectories and timestep convergence.
Observation cubics use held interval controls, check their whole positive
amount envelope and dissipation bounds, and never change accepted steps.

Species, compartments, moieties and reactions have canonical name ordering.
The ordinary scalar/batch/window APIs and complete state/layout checkpoints
carry this model. Backend choice is explicit (`cpu` or `gpu`), always float64;
GPU requests cannot silently fall back to CPU. The generic artifact format's
legacy `cell_ids` denote compartment storage slots here; named `compartments`
and `active_compartments` in the model summary give their physical meaning.

Qualification reuses the existing detached runner:

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  validation/assembly/qualify_cell.py launch \
  /mnt/workspaces/Cells/chemistry-YYYYMMDD-NN --chemistry
```

The [protocol](../validation/chemistry/protocol.json) registers scope, tolerances
and resource limits. Frozen source/configs, independent SciPy references, CPU
and L4 logs, complete restart results, telemetry and completion/failure artifacts
stay under `/mnt/workspaces`. No throughput job follows automatically.

This is the chemistry foundation for intracellular/calcium work. The separate
[`er_calcium@1` model](ER_CALCIUM.md) adds finite ER exchange, a named BETSE pump
and calcium-only release law; its qualification status is in `PROGRESS.md`.
Plasma-membrane calcium currents and feedback into the spatial ionic/assembly
model still need explicit coupling and separate checks. Local
batch partitioning supports that direction; the shared multi-worker ensemble
adapter and 4–16 GPU scaling are not yet qualified for this new family.
