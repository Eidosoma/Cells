# Independent live-recording / saved-window review (D129)

Read-only qualification of the saved D126 native streams and successful D128
output-layout packet. This is a separate reviewer, not another simulation.
The full native/Cells matrix is reviewed once in a detached job.

- Authenticate D119/D120 and D123/D124 prerequisites; D125/D127/D128 software
  receipts and source contexts; all 680 D128 frozen inputs and 516 payloads;
  all 964 native and 24 stopped-continuation files. Both failed attempts stay failed.
- Reuse the already qualified D124 independent CNRS decoder/comparator against
  every original JSON value, not the live producer's stream comparison code.
  Check 36 rows, 18 observer-neutrality pairs, 6,720 updates, 13,404 history samples.
- Independently decode numeric NPY/NPZ with the standard library. Compare saved
  baseline/restart/chunk/checkpoint arrays by dtype, shape and exact bits.
  Check index coverage, overlap ownership, checkpoint clocks, definition/runtime/
  source hashes, all three disk policies, and saved diagnostic reductions.
- Reconstruct expected rolling SHA-256 receipts for the **unsaved** in-memory
  windows/restart windows/zero-length/sparse cases. These are receipt-based
  checks, not direct inspection of unsaved trajectories. Boundary observations
  and the final checkpoint are included in the reconstruction.
- Do not recompute physical residuals. Zero-length diagnostic claims are bounded
  by baseline maxima; they are not independently recalculated. Working-memory
  reservations and native capture memory telemetry are not new measurements.

The import fence excludes Cells, BETSE, NumPy, SciPy, JAX and live/continuation/
layout producer modules. Nothing loads a BETSE pickle or changes production.
No longer-horizon, biological, whole-BETSE bounded-memory or GPU claim follows.

`live_audit_job.py check OUTPUT --tests XML` runs a short, source-bound suite using
saved cases and deliberately corrupted/resealed copies. It has a 60 s deadline.
`live_audit_job.py launch OUTPUT --software SOFTWARE_COMPLETION` authenticates that
receipt and launches the full review detached. It returns only the launch ack.

Full-review safety bounds: CPU affinity 0–3, 900 s, 4 GiB address space, 8 MiB per
new file, 64 MiB new artifacts, 1 GiB disk reserve. The original JSON row is
materialized one at a time; only decoding chunks is bounded by the codec limit.
These are safety caps, not an ETA or a memory-performance claim. No polling,
automatic retry, reference/simulator rerun or follow-up campaign.
