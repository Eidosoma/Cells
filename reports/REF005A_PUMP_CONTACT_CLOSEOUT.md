# REF-005a: independent Na/K kinetic contact closeout

2026-09-16, D108. **The registered instantaneous source-contact scope is closed.**
This is not production pump support, a native BETSE whole-cell trajectory or
biological validation.

The original [capture](../runs/ref-005a-pump-contact-2026-09-16/capture-01/completion.json)
passed all 1,240 comparisons in 5.0625 s, with no warnings: 31 states, two constant
profiles and native BETSE / NumPy / eager JAX / compiled JAX. Its
`contact_pass_pending_audit` receipt stays unchanged.

The separately authorized [independent audit](../runs/ref-005a-pump-audit-2026-09-16/audit-01/completion.json)
completed at **2026-09-16 11:46:09 UTC in 0.163 s**. It reconstructs all 1,240
comparison rows using a new 90-digit mass-action/equilibrium expression,
independent of the original thermodynamic oracle. All columns agree; zero
mismatches. All **248 raw density triplets** link to their reported units,
currents and signed cycles, with stoichiometry and dissipation checks.

Largest error / registered numerical budget: **9.6392e-5**. Both numerical
constant profiles remain separate. Near-stall absolute floors, exact blocking,
the native third-return meaning and the unused `met` argument remain explicit.

The auditor imports neither simulator, NumPy/JAX/SciPy nor the original pump
oracle/worker/controller. Import-fence and rehashed-content corruption checks
are included in **17 passing tests / 0.53 s**. The earlier 17-pass / 0.56 s
receipt also remains. The audit is a bounded short saved-data check; neither
simulator nor a reference integrator was rerun. All 15 original capture files,
11 capture sources, software evidence and accepted implementation bytes remain
unchanged. The new audit's own source capsule and test receipt are bound.

Completion SHA-256:
`e968f4a4cbeab64d612029bd61623ec9916d3d720f03903f169c6428dd092ffe`.
Original capture completion SHA-256:
`944d5183323650219cda4eae950e6ffd0fe8e2c2b8d35c2f125cfe727cd9f593`.

Next: [production integration contract and coupled numerical candidate](../docs/KINETIC_PUMP_INTEGRATION.md).
The kinetic pump cannot inherit the synthetic pump's timestep or biological
interpretation. Coupled numerical qualification, actual production integration,
native driver correspondence and experimental evaluation remain distinct gates.
