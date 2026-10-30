# B04 None-energy transport with explicit physical work

`resolved_calcium_energy_irreversible_transport@1` is a new model identity.
The existing reversible schema/model and qualified native rate law are
unchanged. The six new scientific files, exact hashes, protocol and receipts
are linked in `calcium_energy_irreversible_transport_workqueue.json`. Chief
owns shared routing, public interfaces/docs and PROGRESS.md.

`SurfaceCalciumEnergyIrreversibleTransportModel` subclasses the configured
transport declaration type. `Control`, `Experiment`, `Execution` reuse that
schema's qualified classes; `base_spec` projects to the original38-field
owned-calcium/finite-fuel parent. The new exact State/Layout tags carry44 state
fields. Six route histories are the existing cycles, transported amount,
dissipated energy and supplied work plus `network_chemical_work_pJ` and
`network_electrical_work_pJ`. In the module, legacy.EXTRA_AXES has the first
four and its own EXTRA_AXES has the new two.

Every route preserves its species/coefficient maps, updates actual free
chemical cytosol and finite exterior, and declares maintained signed external
work per cycle. Configuration `standard free energy` remains literal None or
the native string `"None"`; it is never replaced by a reversible evaluation.
The forward-loading native rate retains its signed regulation. External work
does not alter the native rate or add direct ATP consumption.

For outward stoichiometry nu, actual inside/outside concentrations ci/co and
inside-minus-outside voltage Vm, per-cycle physical transfer terms are
`Gchemical = R*T*sum(nu*log(co/ci))` and
`Gelectric = -F*sum(z*nu)*Vm`, in J/mol. The inherited owned-store schema already
requires the shared1-mM/zero ionic standard state. Rate terms are
`extent_fmol_s * G / 1000`, in pJ/s. Physical heat is
`extent*(W-Gchemical-Gelectric)/1000`; native source reaction-energy diagnostic
zero is retained separately and never used as heat or ATP work.

Signed native regulation/extent are preserved without clamping. Actual physical
heat must be nonnegative; a signed rate that produces negative heat refuses.
Blocked routes have zero actual dissipation but still require the original
positive participating substrates and complete native/parent domains. Saved
physical heat stays nonnegative, and chemical+electrical+heat equals supplied
work within the original work-ledger tolerance. No new substrate floor,
thermodynamic rate reversal, inferred fuel consumption or hidden work source
is introduced. Original Na/K, PMCA, ER, chemical and regeneration owners remain
active with their actual live ATP/ADP/Pi pools.

The independent reference imports no production equations. It uses the frozen
80-digit native scalar rate law and independently derives physical transfer
energies with Decimal. Full store/fuel/capacitor ownership and endpoint energy
are checked separately. A scoped32-file AST audit excludes only the uncalled
production comparison driver `junction_transport.check.check`, while retaining
its independent `decimal_flux` symbol. The original overbroad all-body scan
failure is preserved. A separate fresh process denies Cells/JAX imports through
both import mechanisms for actual binding,44-field RHS and DOP853 integration;
it passes without production imports.

The53 CPU component tests cover36 production and17 independent cases. They
include28 complete44-field initial/evolved stages across padding, reordered,
blocked/empty, downhill, signed-regulation and external-extraction recipes.
Maximum state-rate error/budget is0.00560912; independent rate-energy residual
is1.4211e-14pJ/s, below1e-10. Invalid schema, negative physical heat, corrupted
ledgers/padding and native signed-rate preservation are explicit checks.

Active and signed-regulation histories cover2.5us, two original nominal1.25us
steps with an exact route-only boundary at0.9375us. Against independent
standard/tight DOP853, state error/budget decreases from0.0351417 to0.00270165
and0.0363715 to0.00277247 at half timestep. Oracle uncertainty consumes at most
1.3221e-6 of the accuracy budget. All44 fields, actual control clocks, original
parent budgets and endpoint energy checks remain. These short histories do
not establish settling, observed order, native whole-tissue or GPU equivalence.

The main receipt is
`/mnt/workspaces/Cells/calcium-energy-irreversible-transport-development-20261029-01/result.json`,
SHA256 `c6eb438ac1c56e18e9734ce441dc2d53b17dc0f11d878d37d766298c166b5d5b`.
Fresh actual reference-independence receipt:
`/mnt/workspaces/Cells/calcium-energy-irreversible-reference-independence-20261029-01/result.json`,
SHA256 `924734428193049731bba072b447fe36036b945d9cd9cfddbd93e9da56d89ff5`.
Production/independent phases take14.60/52.33s, peak236,675,072B; the separate
independence check takes7.30s, peak84,553,728B. Each is CPU7/one thread with
180s/1GiB RSS/8GiB reserve, no GPU or persistent cache. No numerical failure or
campaign poll occurred. Chief separately verified four public-interface cases
and their source correspondence; they are linked without recounting them as
component physics cases. The six files are fixed for Chief's cut integration.
