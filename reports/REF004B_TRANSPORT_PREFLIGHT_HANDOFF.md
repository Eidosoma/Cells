# REF-004b / D089 transport preflight handoff

2026-09-14. **Software preflight complete; actual native/Cells capture is separate.**
Implements only the setup and single-transfer stage in
[D088's frozen design](../docs/BETSE_COUPLED_CHANNEL_PLAN.md), under the new
[D089 contract](../docs/BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md).

## Completed before numerical capture

- All **76 focused software tests pass in 2.03 s**, no failures/errors/skips:
  `reports/ref-004b-transport-checks-03.xml`, SHA-256
  `974087833dfd4a8e6d0d14b445f156ae75899973807a04d9dd78058b29ebea29`.
  Earlier 71-pass / 76-pass XML receipts remain intact. Tests use fabricated
  native records and actual NumPy Cells kernels; synthetic copies labelled for
  backend coverage do not count as executed native/JAX evidence.
- Tests reject wrong temperature, missing targets/backends/cases, nonuniform
  faces/bath, lost hidden state, second gate advancement, wrong units/signs,
  double ion transfer, padding corruption and countercharge errors. A short
  deliberately unregistered subprocess checks durable failure without an engine
  import, retry or completion claim.
- Repository lint and format checks pass. No full regression was requested or
  automatically launched. All **352 accepted files / 51 production modules**
  still authenticate; no production equations, integrators, dependencies or
  release versions were changed.
- The previous isolated audit and original thirteen capture files, including
  their registered sources, still authenticate. Concurrent repository commits
  did not change those accepted identities; unrelated research work is untouched.
- A **63-input source capsule** and **393-file earlier source baseline** are
  prepared for registration, alongside the accepted source and prior evidence
  anchors. The old flat BETSE validation source inventory does not grow.

Protocol SHA-256:
`6354ced23893880cf0c619234bc03553660c113e8644aeb12bdf9b81ee6a6ce3`.
Registration binds exact protocol, sources, fixed geometry, software receipt and
installed/native identities before numerical execution.

## One bounded attempt

Run directory: `runs/ref-004b-transport-2026-09-14/capture-01`.
Actual `launch.json`, `completion.json` or `failure.json` establish its state;
this handoff is not an execution receipt.

Four native configurations: network off, empty network, blocked Kv1p5 and active
Kv1p5. Three fresh states each: native-initial, `(0.2,0.6)` and `(0.4,0.3)` m/h.
Twelve single-update cases include six channel-runner calls. Cells evaluates
twelve matched post-gate states and prescribed conservative transfers on each
of NumPy, eager JAX and compiled JAX.

Native and Cells use 298.15 K, matched constants, seven cells / thirty faces,
one explicitly finite bath, a 25 microsecond prescribed transfer, zero background
leak/pumps/junction transport and no auxiliary chemistry. The native current
export flag is explicit. The mapper preserves actual fixed-ion charge and
requires within-cell gate/voltage uniformity. Native gate-before-transport
ordering is kept visible; the Cells adapter transfer is **not an RK4 step**.

CPUs 0–3, float64, single-thread libraries. Maximum 120 seconds per worker,
300 seconds overall, 128 MiB aggregate artifacts and 32 MiB per file. These file
limits are not RAM limits. Keep configs, geometry, partial case snapshots, logs,
source capsule and numerical rejections. No automatic retry, polling or audit.

## What remains open

A pass is `capture_pass_pending_audit`. Inspect the actual result on the user's
next status request, then obtain a separate instruction for saved-data closeout.
Only after that gate should a short coupled trajectory and timestep refinements
be registered. This stage does not validate biology, physiological channel
density, a voltage range, full-loop numerical parity, passive input-sampling
convergence, organ-scale execution or GPUs.
