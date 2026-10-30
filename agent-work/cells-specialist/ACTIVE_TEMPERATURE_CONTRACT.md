# Explicit held active-temperature contract

Chief assigned `physiology_active_temperature*` files, independent references
and tests after the pinned-source investigation. Existing model IDs, parsers,
temperature guards, ordinary readouts, accepted states and histories remain
unchanged. Shared documents and initialization belong to Chief. The CPU5
voltage-transition job remains untouched and unpolled.

The separately named opt-in is
`active_uniform_isothermal_fixed_empirical_kinetics@1`, carried by
`cells.physiology_active_temperature_binding@1` and
`cells.physiology_active_temperature_view@1`. Its only input identities are
`resolved_tissue@12`, `resolved_calcium@11`, `resolved_calcium_energy@5`,
`resolved_open_calcium@1` and `resolved_open_calcium_energy@1`. Their ordinary
source declarations/checkpoints must still be valid at 298.15 K. Every actual
cell, environment, membrane, junction, face, population, store and finite pool
is associated explicitly by ID. The policy is mandatory and its complete
record is reconstructed; resealing another standard-state choice does not
change the admitted contract.

The Kelvin setter has a distinct memory type and is evaluated with the pinned
native-program semantics. Held temperatures use the existing 200–400 K process
domain plus all field, gate, positivity, affinity, loss and turnover checks.
This numeric domain is not biological calibration. Native configured/runtime
split semantics remain labelled separate evidence: the new contract uniformly
uses the held temperature in all ionic/field/junction/reservoir/ER/pool terms.
SI constants are inherited from the coherent physical kernels, not substituted
with rounded native constants. Empirical gate curves, time units, Phi, forward
reaction coefficients, diffusion/permeability, pump capacity/Km, geometry and
capacitance are fixed. Live voltage/calcium feedback and legacy instantaneous
calcium-K temperature dependence remain part of the complete derivatives.

Native-source review also established that `get_conductivity` includes `1/d`:
with the declared SI inputs its output is **S/m²**, despite the native S/m
docstring. The previously measured relative `q/kb` versus `F/R` mismatch remains
valid. The frozen native investigation is preserved; this units correction
belongs to its interpretation and future work, not a numerical source repair.

ER reference standard coefficients are fixed in J/mol by
`mu0 = R*298.15*standard_mu_RT_ref`. The held dimensionless coefficients are
`standard_mu_RT = (298.15/T)*standard_mu_RT_ref`; reaction differences follow the
same stoichiometry. Detailed balance changes with these coefficients while the
forward rates remain fixed. This is a declared isothermal numerical family;
reaction enthalpies, activation energies, Q10 and heat capacities are absent.

Standard conventions stay explicit. Maintained Na/K has a declared 1 M J/mol
standard; maintained PMCA/ER inputs declare their numeric-mM J/mol standard and
retain that declared J/mol coefficient. A finite shared pool instead declares
its 1 M J/mol standard, so each stage projects its live ATP/ADP/Pi and applies
`deltaG0_legacy(T) = deltaG0_pool - R*T*ln(1000)` to both PMCA and ER. These are
different input conventions, not permission to share one unconverted numeric
standard between native pump families. Na/K cached drives and finite pump
projections are checked at the held temperature rather than silently retaining
298.15 K cached values.

The complete input checkpoint is checked under its original specification and
anchors first. A private coefficient projection supplies the same validators'
held loss/gate bounds; it is never returned as a parsed ordinary specification
or accepted checkpoint. Only temperature, Na/K drive cache, ER temperature and
dimensionless standard/reaction differences, and finite calcium bridge caches
may differ in the runtime layout. Any geometry, initial inventory, fixed-charge,
capacitor/reference or kinetic-parameter change is refused. Original layout,
source declaration, gate/material/energy histories, controls and clocks remain
byte-identical; outputs are immutable.

Every admitted view has complete finite rates, converged fields, nonnegative
dissipation within the existing roundoff tolerance, stage energy residual at
most `1e-10 pJ/s`, unchanged nominal/gate/loss bounds, and passive/finite-pool
gross turnover at most 5% for the explicit supplied rate-view step. The step
labels a rate admissibility check and is never executed under the held T.
Thermal jumps, heat, thermal internal energy/entropy, accepted changed-T
checkpoints and history resealing are not defined by this contract.

The independent oracle validates original definitions with unchanged binders,
then constructs explicit new-policy contexts from actual owner declarations.
It does not import Cells/JAX or patch ordinary reference globals/guards. It
reuses scalar/full-node independent ionic, channel, calcium, chemical and pool
laws; the finite-fuel assembly is copied from the qualified open reference with
only its changed-T context constructor replaced. Open closure always retains
actual reservoirs and hard ionic-moiety ceilings. A fresh import-denied replay
reconstructs the complete saved rate and potential columns.

Qualification freezes all inputs and exact sources on CPU4 with one thread,
1 GiB process-tree RSS, at least 8 GiB host reserve and 480 s per phase. All56
laws appear in all five families; closed/open, reordered/padded, initial and
original-T evolved states are compared at 273.15 and 310.15 K. Identity,
disabled/empty/zero native programs, enabled setter outputs, original guards,
refusals, policy tampering, fixed-J detailed balance and cached drives are
included. Rate budgets remain `3e-12 + 3e-10*abs(rate)` (charge rates use
`3e-23 C/s`); potentials use `3e-13 + 3e-10*abs(phi)` V. Every field of each
ordinary complete RHS is compared. No follow-up regression or unrelated job
poll is scheduled by this qualification.

The completed physical field comparison additionally saves/replays route
voltages, all total fluxes, electrochemical affinities, route currents and
dissipations, node/membrane/electrode charges, electrode and reservoir currents,
membrane voltage rates, capacitor energy and chemical/electrical/dissipative
powers. Iteration counts and normalized solver diagnostics retain their actual
convergence checks rather than an artificial cross-solver equality requirement.
