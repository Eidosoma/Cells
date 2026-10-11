# REF-004a: isolated channel independently closed

D088, 2026-09-13. **Pass, in the explicitly bounded isolated-channel scope.**
The [actual closeout](../runs/ref-004a-kv1p5-audit-2026-09-13/audit-01/completion.json)
completed in **0.979 seconds**, without importing or rerunning either simulator.
The earlier 11.971-second capture remains unchanged and still records its original
`capture_pass_pending_audit` status; this new receipt establishes closeout.

## Evidence

- All **11,266 frozen comparisons replay exactly**. A separately written
  80-digit Decimal calculation independently reconstructs every comparison,
  expected value, normalized error and verdict, with zero failures.
- The independent calculation uses SI logistic expressions, explicit one-step
  native/RK4 equations and affine-map composition by binary exponentiation.
  It does not call either gate kernel or the original closed-form propagator.
- All 36 measured refinement ratios and 12 roundoff-limited diagnostics match.
  Six additional hidden-history separation checks pass. Both m and h remain
  observable independently of their product.
- Finest-grid maximum absolute gate error versus the continuous solution is
  **0.00740147 for BETSE** and **9.37972e-9 for Cells**, within their preregistered
  bounds. These reflect different numerical methods, not biological accuracy.
- All **102 focused tests pass in 2.58 seconds**: the exact 63 original adapter
  identities plus 39 new actual-packet, corruption, import-fence and reference
  checks. Receipt: [audit checks](ref-004a-audit-checks-01.xml). No failures,
  errors or skips. All 392 Python files pass lint/format checks.
- All 13 capture files, 11 captured source/design inputs, 352 accepted
  implementation files / 51 production modules, and prior D086 evidence remain
  unchanged. All 332 installed BETSE Python files and the reference dependency
  inventory match their recorded identities. No dependency/version changes.

The audit's [registration](../runs/ref-004a-kv1p5-audit-2026-09-13/audit-01/registration.json)
binds inputs, tests, limits and four new audit source/design files. Its
[independent comparison table](../runs/ref-004a-kv1p5-audit-2026-09-13/audit-01/independent-comparisons.json)
retains complete numerical and diagnostic coverage. The
[audit contract](../docs/BETSE_VOLTAGE_GATE_CLOSEOUT.md) remains frozen.

## What is qualified

Six registered prescribed-voltage protocols; one untargeted Kv1.5-style channel;
18 trajectories per engine; 1/0.5/0.25 ms steps; CPU/float64. Kinetics/one-step
probes cover NumPy/eager/JIT, while full Cells gate histories are compiled JAX.
The engineering regime is 298.15 K, without temperature calibration. Initial
native P is explicitly derived from the installed m/h state; subsequent P is
native output. Equilibrium initialization and prescribed non-equilibrium states
remain separate claims.

This is **not** a coupled-cell result, full native tissue-target test, electrode
clamp, physiological calibration, channel-family parity, general waveform
convergence or GPU qualification. Actual intermediate runtime arrays were not
retained; all-stage validity is supported by authenticated source and recorded
worker flags, not reconstructed original substep arrays. Prior passive
input-sampling limitations and all 4173 diagnostic failures remain unchanged.

## Next step, without a new launch

The [coupled-channel plan](../docs/BETSE_COUPLED_CHANNEL_PLAN.md) records the
reviewed native gate-to-transport pathway. Important differences are face-indexed
gate ownership, post-gate channel transport applied directly to concentrations,
and channel flux/current recorded separately from ordinary membrane fluxes.

Next implement a small native configuration/transport preflight at 298.15 K:
network-off, empty-network, zero-permeability channel and active channel controls;
actual target/geometry mapping; matched-state permeability/flux checks; one
conservative update and charge/voltage accounting. Reuse Cells' finite-bath
assembly and shared integrator. No full coupled trajectory, further audit,
production regression or background job was started after this closeout.
