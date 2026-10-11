# M1a acceptance: Cells 0.1.0

Verified: 2026-09-08 UTC. Status: complete for the one-cell engineering slice.
M1b source-backed regulation and M1c cell contact remain unimplemented. These
results establish an execution/numerical foundation, not biological memory,
plastic heredity, calibrated cell physiology, or organ function.

## Implemented scope

- Strict, versioned JSON definitions for model, experiment, and execution.
- One active cell with amount, volume, stable identity, and neutral padding.
- Pure source/decay dynamics, generic PyTree RK4, and JAX CPU execution.
- A zero-anchored numerical grid split at exact input events and the final time.
- Separate accepted-state traces and read-only linearly interpolated observations.
- Cumulative input/decay accounting and explicit numerical failure without clipping.
- Complete numeric NPZ/JSON snapshots, checksum/source/runtime checks, and restart.
- Explicit future-input branches with parent provenance and unchanged past state.
- Non-overwriting CLI output, manifests, run summaries, and bounded trace estimates.

## Verification

The final test invocation passed all 88 tests in 9.34 seconds, with warnings
treated as errors. See [JUnit results](m1a-tests.xml). Ruff lint and format checks
passed, and pip reported no broken requirements. The installed package entry
points and fresh-process CLI run/resume/branch paths were exercised.

Tests include analytic constant-input/decay cases, fourth-order refinement,
off-grid and sub-step pulses, exact final-time handling, input events at the
final instant, observation independence, padding, eager/JIT agreement, exact
restart at five boundaries, isolated future branches, invalid units/configuration,
numerical overflow, corrupted/incompatible snapshots, refusal of object-array
unpickling, and refusal to overwrite existing output.

The saved artifacts were additionally checked with an independent closed-form
superposition calculation in [the verifier](../scripts/verify_first_build.py).
This is separate from the stepwise analytic oracle used by the tests.

| Saved example | Executed steps | Final amount (fmol) | Maximum analytic trajectory error (fmol) | Maximum balance error (fmol) |
| --- | --- | --- | --- | --- |
| Pulse, 0 to 12 s | 242 | 0.1666461576788277 | 1.777e-9 | 6.439e-15 |
| Unchanged resume, 6 to 12 s | 120 | 0.1666461576788277 | 8.131e-10 | 6.439e-15 |
| Rechallenge branch, 6 to 12 s | 120 | 1.3032487156980899 | 2.974e-10 | 1.777e-14 |

The declared analytic tolerance is 2e-8 fmol. The unchanged resumed suffix matches
the original accepted time grid and amount/input/decay arrays exactly under this
runtime. The branch begins with the same state and cumulative accounting, then
adds an external 0.5 fmol/s input at six seconds. It does not mutate its parent.
All artifact hashes and checkpoint/branch provenance checks passed.

Local artifacts (generated and excluded from Git):

- [Pulse manifest](../runs/m1a-2026-09-08/pulse/manifest.json).
- [Resumed manifest](../runs/m1a-2026-09-08/resumed/manifest.json).
- [Rechallenge manifest](../runs/m1a-2026-09-08/rechallenged/manifest.json).
- [Verification receipt](../runs/m1a-2026-09-08/verification.json).

The pulse definition SHA-256 is
`8a2e78e5c875caf05db2deda2f657e8de3e3a1dca9d9f106827bd245175ed93c`.
The rechallenge definition SHA-256 is
`9750fdc629ced03c7dc3a954f79407694a8bd681b53bb965a06608534c89d452`.
Full package-source hashes and runtime identity are stored in the manifests.

## Environment and timing scope

Linux x86_64, Python 3.13.5, JAX/jaxlib 0.11.1, NumPy 2.5.3, and float64.
The complete development dependency set is in
[requirements-lock.txt](../requirements-lock.txt). Verification processes were
restricted to CPU IDs 0-3 on this host. No GPU packages or GPU runs were used.

One saved fresh pulse invocation measured approximately 0.131 seconds for
compilation/cache preparation, 0.00101 seconds for synchronised post-compilation
execution, 0.143 seconds for the runner including preparation/analysis, and
0.0267 seconds for artifact payload writes. The last timing excludes publishing
the final manifest; CLI interpreter/import time is outside runner timings.
These are individual observations on a shared host, not throughput estimates,
GPU comparisons, or evidence of organ-scale feasibility. Full bounded traces
are retained in this prototype; the trace-memory estimate is not a hard bound
on whole-process RSS or compiler memory.

## Reproduce

Use the installation steps in [README](../README.md). From the repository root:

```bash
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

For a fresh checkout without these generated example directories:

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/single_cell_pulse.json --output runs/m1a-2026-09-08/pulse --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/m1a-2026-09-08/pulse/snapshots/step-000122 --output runs/m1a-2026-09-08/resumed
taskset -c 0-3 .venv/bin/python -m cells branch runs/m1a-2026-09-08/pulse/snapshots/step-000122 configs/single_cell_rechallenge.json --output runs/m1a-2026-09-08/rechallenged
taskset -c 0-3 .venv/bin/python scripts/verify_first_build.py runs/m1a-2026-09-08
```

On another host, omit taskset or choose CPU IDs available there. Existing example
directories are intentionally not overwritten; use a new root for another run
and pass that root to the verifier. Metadata/timings will differ between fresh
runs. Unchanged replay is exact on the tested host/backend; cross-hardware or
cross-version equivalence is not established. Source-changing edits intentionally
invalidate strict restoration until an explicit migration/version strategy exists.

## Next step

Resolve the pinned Levin-derived model source and its smallest isolated-cell
fixtures, then add it as a separate model in M1b. Preserve this analytic model
as a permanent numerical and replay test. Add physical contact in M1c after the
isolated source-backed model has been checked. No tissue, organ, GPU, or ongoing
research-lane experiment was launched as part of M1a.
