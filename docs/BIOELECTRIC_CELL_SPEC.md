# One bioelectric cell: physical and engineering contract

SPEC-001, accepted design baseline 2026-09-08. Model identifier:
`bioelectric_cell@1`, now implemented in Cells 0.5.0 as MODEL-003. NUM-002's
reference source ZIP preserves the original 0.4.0 specification. Independent
instantaneous checks and CPU trajectories precede the separate
[production JAX acceptance](../reports/MODEL003_ACCEPTANCE.md).
See the [implementation guide](BIOELECTRIC_CELL.md) for the resolved schema and
[numerical contract](BIOELECTRIC_NUMERICS.md) for the bounded method candidate
and [reference qualification](../reports/NUM002_REFERENCE.md) for its evidence.
See [review](BETSE_DESIGN_REVIEW.md), [decision D018](DECISIONS.md#d018-bioelectric-interfaces-and-a-one-cell-physical-contract),
and [progress](../PROGRESS.md).

## Purpose and smallest scope

Exercise reusable physical-cell engineering before selective contacts, source
assays, or organs: one well-mixed, fixed-volume cell; one explicit membrane;
three permeant species Na+, K+, Cl-; an immobile negative charge background;
and a maintained external bath. Combine constant-field passive leaks with an
explicitly energized, phenomenological reversible 3Na-out/2K-in pump.

This is a synthetic dimensional reference, not a calibrated Xenopus, mammalian,
BITSEY, BETSE, or Calculion cell. In particular, the pump law below is our limited
engineering choice, not a fitted Na/K-ATPase kinetic mechanism. The
[BETSE and Calculion review](BETSE_DESIGN_REVIEW.md) motivates the boundaries;
it does not supply automatic parameter or trajectory correspondence.

No gap junctions, endogenous channel gates, regulation, calcium, pH, water flow,
metabolic pools, mechanics, growth, fields, current clamp, or voltage clamp enter
this first model. The bath has constant concentrations, temperature, and electric
potential zero. Holding bath chemistry, countercharge, cell volume, and chemical
drive fixed is declared external support. This is an open system, not a claim
that all material and energy in the world have been simulated.

Exactly one active cell and one active membrane are first-fixture limits, not
engine-wide population or species limits. No organ wrapper or shape solver is
needed. Geometry and cell type remain data; changing the model's physics requires
a versioned mechanism, not an arbitrary expression in configuration.

## Units and orientation

Resolve and validate units on the Python host. Hot kernels receive plain arrays
in these units; outputs label them. Names below specify physical meanings;
the [implementation guide](BIOELECTRIC_CELL.md) identifies the runnable fields.

| Quantity | Kernel unit / convention |
| --- | --- |
| Cell amounts `n_s` | fmol |
| Cell volume `v` | pL; fixed and strictly positive |
| Concentrations `c_i,s`, `c_o,s` | mol/m3; numerically equal to mM and to fmol/pL |
| Membrane area `A` | m2; strictly positive; explicit conversion for micrometre-squared input |
| Leak permeability `P_s` | m/s; finite and nonnegative |
| Specific capacitance `C_specific` | F/m2; strictly positive |
| Total membrane capacitance `C = A C_specific` | F |
| Time and temperature | seconds and kelvin; finite, strictly positive temperature |
| Voltage `V_m = phi_inside - phi_outside` | V, not mV |
| Ion valence `z_s` | Na: +1, K: +1, Cl: -1 |
| Transmembrane ion flux `J_s` | fmol/s, positive from bath into cell |
| Pump cycle rate `r` | fmol cycles/s; forward exports 3 Na and imports 2 K |
| Effective ATP hydrolysis free energy `G_ATP` | J/mol cycles under maintained chemical conditions |

Use SI defining constants: `N_A = 6.02214076e23 mol^-1`,
`e = 1.602176634e-19 C`, and `k_B = 1.380649e-23 J/K`;
`F = e N_A`, `R = k_B N_A`. Let `a = 1e-15 mol/fmol`,
`b = 1e-15 m3/pL`, and `q_f = F a` in C/fmol.
Thus `c_i,s = a n_s / (b v)`.

Do not confuse permeability with an aggregate contact coefficient in pL/s or a
membrane diffusion coefficient in m2/s. An adapter must state any area, length,
partition, or time conversion. Source-scaled EMT coordinates and nominal time
have no implicit conversion to this model's physical amounts or seconds.

## State, interfaces, and ownership

| Block | Owned contents | Persistence |
| --- | --- | --- |
| Cell state | `amount[species, cell_capacity]` | Primary dynamic state |
| Membrane accounting | `leak_transferred[species, membrane_capacity]`, `pump_cycles[membrane_capacity]` | Signed integrated flux/cycle ledgers; dynamic but not extra stored matter |
| Cell definition/layout | Stable ID, active mask, volume, initial amount anchor `n_ref`, voltage anchor `V_ref`, fixed charge | Immutable resolved definition; retained in snapshots |
| Membrane definition/layout | Stable ID, independent active mask/capacity, owner-cell slot, facing-bath ID, area, specific capacitance, permeabilities, aggregate pump capacity | Immutable resolved definition; not a cell-contact edge |
| Bath definition | Stable ID, fixed concentrations and potential, temperature, maintained chemical drive | Explicit external conditions; no fictional dynamic bath inventory |
| Experiment controls | Per-ion leak multipliers and an independent pump multiplier | Resolved schedule and current values, retained for replay |
| Derived observations | Concentrations, voltage, currents, fluxes, potentials, exchange balances, signed chemical work | Read-only; not independently evolved |

The first implementation should add only these exercised array blocks. A membrane
mapping is a sparse ownership/endpoint map, not a requirement for dense geometry.
Inactive entries need finite neutral concentrations and nonzero dummy denominators
before masking; a masked NaN or log(0) is still an implementation error.

Physical contact existence, experiment-imposed inhibition, and an endogenous
channel/gap-junction gate are distinct concepts. This model has no endogenous
gate. When a later law adds one, its state, update equation, axis, and checkpoint
semantics must be explicit; neither topology nor the experiment schedule may
silently replace it.

## Charge and voltage closure

Fresh initialization specifies positive ion amounts `n_ref` and `V_ref`. These
fix the immobile background charge once:

```text
Q_fixed = C V_ref - q_f sum_s(z_s n_ref,s)
n_X_equivalent = -Q_fixed / q_f
```

The negative-background model requires `n_X_equivalent >= 0`. It is an effective
fixed charge in monovalent-anion equivalents, not an independently transported
protein species or a complete osmotic model. Choose the initial voltage and
background consistently; do not impose exact bulk electroneutrality as an
additional incompatible constraint.

Amounts are primary. Voltage is derived using the immutable affine anchor:

```text
V_m(n) = V_ref + (q_f / C) sum_s[z_s (n_s - n_ref,s)]
C dV_m/dt = q_f sum_s(z_s dn_s/dt)
```

This equals `(Q_fixed + q_f sum_s(z_s n_s))/C`, but avoids subtracting large
opposing initial charges at every evaluation. Do not separately integrate voltage
and ionic charge without a new explicit constraint formulation. Do not recompute
the background or reset the anchors after preparation, on resume, or when branching.

The bath's countercharge and potential maintenance are external. This lumped
capacitor closure is limited to the declared single membrane and fixed-potential
bath. Finite extracellular charge, multiple facing potentials, field models,
changing area/volume, and external electrode currents require a re-derived charge
closure; they are not enabled by merely adding another array entry.

## Passive membrane mechanism

Assume independent ideal dilute ions, a constant field across the membrane,
well-mixed endpoint concentrations, and fixed temperature. For species `s`,
with experimental multiplier `u_s` in [0, 1]:

```text
x_s = z_s F V_m / (R T)
B(x) = x / (exp(x) - 1), with B(0) = 1
J_leak,s = (A P_s u_s / a) [c_o,s B(x_s) - c_i,s B(-x_s)]
delta_mu_s = R T log(c_i,s / c_o,s) + z_s F V_m
```

`delta_mu_s` is the electrochemical free-energy change for moving one mole
inward. Required independent limits:

- Zero voltage gives `A P_s u_s (c_o,s - c_i,s)/a`.
- The species' Nernst voltage `E_s = R T log(c_o,s/c_i,s)/(z_s F)` gives zero
  flux for that species. Three separate Nernst tests are not simultaneous
  equilibrium of the whole Na/K/Cl cell.
- Setting a route's permeability or multiplier to zero gives exact zero flux.
- Swapping concentrations and reversing voltage reverses the flux.
- Doubling area doubles flux at fixed concentrations and voltage.
- `J_leak,s delta_mu_s <= 0`: passive transport cannot supply free energy.

Use `expm1` plus a near-zero series or an equivalent stable expression. The
scalar design calculator checks the expression through `abs(x) = 50`; this is
not yet a production domain guarantee. JAX branches must be mask-safe at zero
and avoid overflow in evaluated alternatives. Never fix a sign or singularity
problem by clipping the physical flux or flooring a concentration silently.

## Energized pump mechanism

Use stoichiometry `nu = [-3, +2, 0]` in the declared species order. A positive
cycle moves one net positive charge outward. `G_ATP` is the effective maintained
hydrolysis free energy, not a bare standard-state constant or an ATP concentration.
The cell does not evolve ATP, ADP, or phosphate in this approximation.

```text
G_cycle = G_ATP + sum_s(nu_s delta_mu_s)
        = G_ATP + 3 R T log(c_o,Na/c_i,Na)
                + 2 R T log(c_i,K/c_o,K) - F V_m
r = r_max u_pump tanh[-G_cycle / (2 R T)]
J_pump,s = nu_s r
```

`r_max` is a finite nonnegative aggregate cycle capacity in fmol cycles/s for
this membrane; `u_pump` is an independent multiplier in [0, 1]. It is not an
area density. A future density parameterization must convert to aggregate
capacity explicitly.

This reversible phenomenological law supplies a bounded cycle rate with stall
at zero affinity. It reverses for positive `G_cycle` and satisfies
`r G_cycle <= 0`. It does not contain substrate-binding kinetics, calibrated
turnover rates, metabolic regulation, or a general claim about real pump speed.
Changing to such a mechanism requires a separately identified model law.

Signed chemical power delivered by the maintained drive is
`-a G_ATP r` W; forward operation with negative `G_ATP` consumes supplied free
energy, and reversal can return it. Cycle dissipation is `-a r G_cycle >= 0` W.
These describe this pump and its external drive, not the full cost of metabolism
or of maintaining the bath, temperature, and volume.

## Coupled derivative and accounting

Evaluate voltage, concentrations, leaks, and pump from the same numerical stage
state, then accumulate their contributions:

```text
dn_s/dt = J_leak,s + nu_s r
dL_s/dt = J_leak,s
dP/dt = r
I_inward = q_f sum_s[z_s (J_leak,s + nu_s r)]
I_outward = -I_inward
```

`L` is the leak ledger and `P` the signed cycle ledger, both zero at the fresh
origin. In the first one-membrane fixture:

```text
n_s(t) - n_ref,s = L_s(t) + nu_s P(t)
C [V_m(t) - V_ref] = q_f sum_s[z_s (L_s(t) + nu_s P(t))]
chemical_work_supplied(t) = -a G_ATP P(t)
```

For a future supported multi-membrane model, owner-cell accumulation would sum
the relevant membrane contributions. That reuse does not itself establish the
new electrical closure. Signed bath supply is the existing leak-plus-pump ledger,
not a second independently stored amount. Cell ion totals need not be constant:
the bath exchanges ions. Check per-species balance including that exchange, not
a false closed-cell conservation assertion. Likewise, negative signed ledgers
are valid; negative physical amounts are not.

## Controls, preparation, observations, and restart

Define separate named control groups for `leak_multiplier[species, membrane]`
and `pump_multiplier[membrane]`. Host validation resolves names and IDs, rejects
unknown or conflicting entries, and creates a complete deterministic control
vector. Do not extend the existing source-or-contact selector by ignoring one
group. Use the union of control boundaries as exact integration boundaries, with
the new values applying to the following interval. Simultaneous controls need
unambiguous semantics and tests.

First-version controls scale rates only. They cannot change bath composition,
temperature, capacitance, physical topology, or instantaneous cell state. All
such additions would require separately specified events and accounting.

Preparation is an explicit initial run/protocol, with its starting state, controls,
duration, stopping criteria if any, and resulting checkpoint recorded. No hidden
warm-up occurs inside `run`, `resume`, or `branch`. A requested steady-state
preparation must report measured residuals and whether its criteria were met;
an elapsed horizon alone does not establish equilibrium. The initial fixture
below is not prepared or stationary.

Snapshots retain amounts, all ledgers, immutable electrical anchors, complete
membrane/cell/bath definitions and mappings, controls, clock, numerical history,
and provenance. An unchanged restore must reproduce the accepted suffix under
the pinned runtime. A branch changes only permitted future controls/horizon/
observations; it neither clears prior ledgers nor re-equilibrates the cell.

Observers derive voltage and other nonlinear quantities from the declared sampled
primary state, with interpolation semantics labelled. They must not affect
integration, gating, preparation, or future controls. Record continuous voltage,
concentrations, route fluxes, accounting residuals, and chemical work; do not add
an E/M classifier to a model without regulatory state.

## Synthetic starting fixture

All numerical values below are deliberately illustrative engineering parameters.
They are not taken as a matched physiological parameter set from a publication.

| Parameter | Value |
| --- | --- |
| Cell volume | 1 pL |
| Membrane area | 1e-9 m2 = 1000 micrometre2 |
| Specific / total capacitance | 0.01 F/m2 / 1e-11 F = 10 pF |
| Temperature | 298.15 K |
| Initial Na, K, Cl amounts | [12, 140, 10] fmol |
| Bath Na, K, Cl concentrations | [145, 5, 150] mol/m3; electroneutral |
| Initial voltage anchor | -0.065 V |
| Na, K, Cl leak permeabilities | [1e-10, 1e-9, 1e-10] m/s |
| Aggregate pump capacity | 0.02 fmol cycles/s |
| Maintained `G_ATP` | -50000 J/mol cycles |
| Baseline controls | All multipliers 1 |

The implied fixed-anion equivalent is approximately 142.0067368 fmol. All
permeant concentrations are strictly positive; require that throughout the
accepted numerical domain. No epsilon floor or post-step amount clipping is
part of these equations. Fixed volume omits osmotic relaxation explicitly.

## Numerical validation and implementation sequence

NUM-002 selects a bounded candidate: CPU float64 RK4 at at most 0.005 s with
interval-held-control cubic Hermite observations. Its independent implementation
and [numerical contract](BIOELECTRIC_NUMERICS.md) preceded production/JAX acceptance;
no arbitrary-parameter stability or accuracy guarantee is claimed. The existing
linear reaction/transport `h*alpha <= 0.5` bound does not cover these nonlinear
electrical dynamics. The original sequence and fixed physical targets follow;
steps 1–5 are now delivered, and step 6 remains future work.

1. NUM-002: implement a separate NumPy/SciPy trajectory reference without imports
   of Cells' future membrane/pump kernels. Check Radau/BDF agreement and tolerance
   refinement, analytic limits, positive states, signed energy and charge/material
   accounting. Pin the reference implementation and settings before JAX comparison.
2. Establish a bounded panel: the starting fixture over 1 and 10 s; leak-only,
   pump-only, all-routes-off, independent leak/pump block-and-release schedules;
   doubled/halved area or volume and selected permeability/capacity variants.
   Include pump stall/reversal mechanism probes. Use off-grid boundaries such as
   2.03 and 5.07 s, simultaneous changes, and pulses shorter than candidate steps.
3. Select a candidate Cells solver and supported numerical domain from those
   results, checking refinement, internal-stage validity, stiffness, work, and
   failure handling. Predeclare maximum trajectory errors of 1e-6 V for voltage,
   1e-7 fmol for amounts/leak ledgers, and 1e-7 fmol cycles for pump ledgers on
   that panel; demand reference-reference errors at least ten times smaller.
   Require per-species balance residuals <= 1e-10 fmol and charge residual
   expressed as voltage <= 1e-8 V on the panel. Exact algebraic zero/off cases
   are separate checks. NUM-002's independent results are recorded separately;
   production/JAX acceptance against these targets is recorded in MODEL-003.
4. MODEL-003: implement the cell/membrane/bath types, independent control groups,
   and passive ionic mechanism; then add the pump contribution through the same
   composition path. Preserve mask safety, same-stage evaluation, dimensioned
   output, event semantics, snapshots, and strict source/runtime identity.
5. Complete production acceptance: eager/JIT comparisons, independent trajectories,
   solver refinement, invalid-state/step refusal, observation independence, and
   exact checkpoint replay plus independently controlled future branches. Regress
   all four existing models and preserve 0.4.0 source before package changes.
6. Only then add explicitly stateful gates and a two-cell selective contact model,
   with source-coordinate/time mapping and positive/negative source comparisons.
   A pinned BETSE fixture is a separate reference task, not an implied equivalence
   of the synthetic cell. Finite baths/fields and regulatory coupling follow when
   their selected tests require them.

If a candidate timestep fails, refine or change the numerical method; do not
change the physical parameters or relax a tolerance simply to get a pass. If
the model's domain or an acceptance target needs a reasoned revision, record the
failure and version that decision before using the new target. Numerical failure
is not biological death. Production support remains bounded by the ultimately
verified configurations and runtime checks, not by the breadth of the symbols here.

## Evidence delivered with this specification

[check_bioelectric_contract.py](../scripts/check_bioelectric_contract.py) imports
NumPy and standard-library utilities, but no Cells model. It checks unit conversion,
the Bernoulli expression against high-precision Decimal calculations, diffusion
and Nernst limits, orientation, area scaling, pump stoichiometry/off/stall/reversal,
sampled dissipation inequalities, and an algebraic charge/ledger identity.

The [design-check report](../reports/BIOELECTRIC_DESIGN_CHECK.md) and
[JSON receipt](../reports/bioelectric-design-check.json) retain its 74 passing
instantaneous checks, verifier identity, and reproducible numerical values. These
are not 74 new pytest cases, integrated trajectories, source parity, biological
validation, or a fifth runnable Cells model. A frozen-concentration local
relaxation estimate is a diagnostic, not a solver stability bound or a guarantee
of equilibrium. The subsequent [NUM-002 report](../reports/NUM002_REFERENCE.md)
records integrated reference trajectories, numerical refinement, interpolation
checks, and the retained long-time preparation residual. These are distinct
from the original 74 instantaneous checks. MODEL-003's subsequent production
build is documented [separately](BIOELECTRIC_CELL.md). The numbered sequence above
retains the predeclared criteria, not current pending-work status.
