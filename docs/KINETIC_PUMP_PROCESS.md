# Named Na/K kinetic process: production boundary and remaining integration

2026-09-16, D111 / SPEC-010. D110 [closed the bounded coupled numerical
prerequisite](../reports/NUM011_COUPLED_CLOSEOUT.md). The new
`src/cells/processes/kinetic_pump.py` implements `nak_atp_mass_action_positive@1`
in the production process layer. **It is not yet a selectable model family.**
The existing synthetic pump and all registered simulation families are unchanged.

## Interface and physics

`Parameters` is an immutable numeric pytree with explicit fields for capacity
in fmol cycles/s, ATP/ADP/Pi and three Km values in mM, and standard hydrolysis
energy in J/mol. Arrays broadcast over `[..., membrane_slot]`; leading world
axes and heterogeneous membranes are ordinary data, not Python loops in the law.
There are no implicit biological parameter defaults.

`kinetics` takes local sodium-inside and potassium-outside concentrations,
the inward Na and K electrochemical potentials, temperature, parameters and
fractional availability. The composing model resolves species roles and supplies
the potentials from the **same solver-stage** chemistry and voltage. Na and K
roles must be distinct monovalent cations; the law's inward stoichiometry is
−3 Na / +2 K per forward cycle.

It returns signed cycle rate, cycle free energy and chemical drive:

```
chemical_drive = deltaG0 + RT log(ADP * Pi / (1000 * ATP))
cycle_energy   = chemical_drive - 3 * mu_Na + 2 * mu_K
saturation     = Na_i³/(KmNa³+Na_i³) * K_o²/(KmK²+K_o²) * ATP/(KmATP+ATP)
cycles         = capacity * availability * saturation * (1 - exp(cycle_energy/RT))
```

The 1000 factor declares the 1 M chemical standard state when inputs are mM.
ATP/ADP/Pi initially remain maintained reservoirs. They are not silently added
to intracellular ion inventories or depleted by an observer.

Capacity is already extensive: the composing model converts a surface density
by `area_m2 * alpha_mol_m2_s * 1e15` exactly once. Apply −3/+2 to cycles once,
accumulate that transfer to the cell and its negative to the bath, and derive
current from the same ionic transfer. Do not add a second voltage/charge update.
Dissipation is `-1e-3 * cycles * cycle_energy` pJ/s; maintained chemical work is
`-1e-3 * cycles * chemical_drive` pJ/s. The process does not own either ledger.

## Numerical contract

Use log saturation and combined exponents to avoid overflowing positive
concentration/Km ratios or prematurely underflowing a representable rate.
`expm1` retains the small affinity difference at stall, without a stall threshold
or clipping. Zero capacity/availability returns an exact zero rate. Forward
and reverse cycles share the same thermodynamic sign convention.

`domain_valid` gives a per-route predicate, not a repaired state. It requires
strictly positive finite substrates/Km, finite nonnegative capacity, availability
in [0,1], finite potentials and drive, and `|cycle_energy/RT| <= 80`. The current
explicit numerical temperature range is 200–400 K; this is **not evidence of
biological calibration across that range**. Individual `|mu_ion/RT| <= 1600`
keeps the rejection arithmetic bounded and encompasses the finite-float64
positive-concentration/log-potential range at the existing voltage bound.

Invalid pools remain invalid when transport is blocked. Neutral values inside
the rejection predicate never enter an accepted physical state. Inactive array
slots must be explicitly prepared with neutral positive inputs and zero capacity
by the future host/layout layer. The solver must additionally check the whole
cell/bath domain, all RHS values and accepted/interpolated state. This process
predicate alone cannot establish any of those conditions or validate species
mapping.

Positive-interior derivatives, including exact zero affinity, are tested.
Parameter gradients at zero-capacity/zero-availability boundaries are not an
accepted API guarantee. CPU eager/JIT and `vmap` checks are not GPU qualification
or a speedup estimate.

## Evidence and preservation

[32 focused process tests](../reports/spec-010-pump-process-checks-02.xml) pass,
covering independent 80-digit scalar arithmetic, forward/reverse transport,
blocking, invalid-domain rejection, neutral padding, broadcasting, JIT/vmap,
stall derivatives, stoichiometric charge and representable tiny saturation.
[Ten gate checks](../reports/spec-010-process-gate-checks-02.xml) include actual
six-state NumPy/eager-JAX/compiled-JAX smoke against saved independent/native
contact values. The [handoff](../reports/SPEC010_PROCESS_HANDOFF.md) records earlier
retained findings and the prospective detached qualification.

The full process contact will reuse all 31 **matched-constant** cases, checking
five readouts against both the saved independent oracle and the saved native
BETSE values on three CPU backends: **930 comparisons**. Original budgets stay
unchanged. This does not rerun native BETSE or qualify a new coupled production
trajectory. Four existing model test files plus the new process tests form a
separate targeted regression of **348 collected tests**—not a full release matrix.

No accepted file is edited: all 352 old implementation files remain unchanged.
Adding this module nevertheless changes the whole-package source inventory
from 51 to 52 modules. Thus the working tree is an **unaccepted development
extension**, not byte-identical to accepted 0.15.0.dev0. Its version string and
stable 0.14.0 release are not promoted. Reproduce old checkpoints with the
preserved accepted source context; never bypass full source-identity checks.

## Next engineering slice

After reviewing the detached process qualification/regression:

1. Add a versioned finite-bath configuration route and typed host parameters;
   validate explicit roles, metabolic support, units and derived finite values.
   Keep old configuration fingerprints, equations and parser behavior intact.
2. Add numeric layout fields and explicit neutral inactive padding. Select the
   pump in the composing model, never in RK4 and never by subtracting another
   pump from its RHS. Reuse material/cycle/dissipation state ownership.
3. Add full-stage and Hermite-interior domain checks, then ordinary run,
   complete restart/branch, homogeneous cohorts/windows and independent energy
   accounting. The six 10 ms candidate cases do not replace this acceptance.
4. Run bounded new-family acceptance and the appropriately routed release
   regression; promotion remains explicit. Then measure native driver ordering,
   area/rho/boundary semantics and longer pump–leak relaxation before biology.

Keep the [broader integration contract](KINETIC_PUMP_INTEGRATION.md), junction
and original-data tracks intact. Detailed BETSE-level realism remains the target.
