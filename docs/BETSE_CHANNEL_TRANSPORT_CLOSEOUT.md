# REF-004b: independent channel single-transfer closeout

D092, 2026-09-14. Implements a saved-data audit of
[D091's runtime-corrected capture](BETSE_CHANNEL_RUNTIME_FIX.md). The user
reviewed its **21.272-second pass / 37,068 comparisons**, then requested this
next step. The raw capture remains `capture_pass_pending_audit`; only a separate
successful audit completion closes this narrowly defined comparison.

## Two numerical checks, separately implemented

1. Replay the frozen comparator exactly from the saved registration, native
   records and Cells records. Require complete dictionary equality with its
   original 37,068-row comparison, including failures, units, identities and
   hidden-state diagnostics. This checks reproduction, not independence.
2. Reconstruct all 37,068 numerical comparisons from raw fields with independent
   80-digit Decimal arithmetic. The independent module imports no simulator,
   original comparator, original protocol helper or original mathematical oracle.
   It uses exponential-odds gate targets, a dimensionless implicit-Euler native
   update, and the direct exp(VF/RT) GHK expression, with the zero-voltage limit.
   Independently sum face areas/fluxes by owner, derive six-species inventory
   conservation, finite-bath updates, current signs, capacitive charge/voltage,
   native current smoothing and Cells material/current/transfer ledgers.

Use the original absolute-plus-relative-to-expected tolerance definition. Check
both captured actual values and stored expectations against the reconstruction;
require exact identity/unit coverage, with no omitted or duplicate comparison.
High-precision reductions need not be bitwise equal to float64 cancellation.
Retain any numerical failures in the new audit output, never relax criteria.

Independently check data-definition units, membrane endpoints, cell/bath volumes,
species amounts, immobile charge, initial voltage and per-cell hidden gates.
Preserve native's absent initial P, distinguish prescribed m/h pairs from actual
histories, and check that equal initial products evolve differently. The
original exact configuration, inactive-padding and no-double-transfer guards
are also replayed. The energy check covers the captured prescribed ledger
increment; it does not newly qualify channel energetics or a long trajectory.

## Evidence and implementation boundary

Pin original completion, registration and comparison digests, then authenticate
every capture file and source-capsule byte. Reconcile the separate native
geometry/preparation/before/after files with aggregate output and reconcile the
separate Cells definitions with those actually consumed. Never unpickle native
world archives: hash them only. Check runtime/packages, loaded native source
bytes, CPU/precision/JIT regime, warnings, elapsed clocks and file accounting.
Keep both earlier failed attempts and their correction evidence unchanged.

The actual audit runs in a fresh process with Cells, BETSE, NumPy, JAX and SciPy
imports forbidden. No simulator or older audit is rerun. The focused software
suite includes the unchanged 152 prior tests plus new arithmetic, corruption,
coverage and import-fence checks. Their synthetic-model / startup / native
parameter-loader checks are software tests, separate from the fenced audit.

Register the passing software XML, exact capture inventory and source capsule
before detached execution. Limits: CPU 0–3, **120 seconds**, **64 MiB aggregate
artifacts / 32 MiB per file**. These are output quotas, not RAM limits. Retain
failure receipts/logs; return without polling, automatic retry or follow-up.

## Qualification, if the independent audit passes

Only four native preparations, twelve native single updates, and twelve matched
prescribed Cells transfers per NumPy/eager-JAX/JIT-JAX backend: seven cells,
thirty faces, one shared finite bath, 298.15 K, matched constants, 25 microseconds,
and the frozen network-off/empty/blocked/active fixtures. Cells' production
integrator did not run in this contact: this is not a full coupled trajectory,
physiological validation, broad BETSE parity, arbitrary tissue size or GPU proof.

The [next dynamic-pilot outline](BETSE_CHANNEL_DYNAMIC_PILOT.md) is conditional
design only. It launches no simulation and is not an approved numerical protocol.
