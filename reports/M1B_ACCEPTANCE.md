# M1b acceptance: Cells 0.2.0

Date: 2026-09-08 UTC. Outcome: the source-backed isolated regulatory slice is
implemented and numerically verified. The synthetic M1a fixture remains supported.
The full M1 milestone still needs two-cell contact (M1c).

## What works

The same CLI, CPU/JAX runner, RK4 solver, resource bounds, artifact format, and
strict restart machinery now support two explicit models. The regulatory model
owns its three-variable state, scaled units, fixed parameters, algebraic refresh,
validation, and observers. The synthetic model retains amount/input/decay accounting.
Neither is mapped onto misleading state names or a fake common physical volume.

The [reference contract](../docs/EMT_REFERENCE.md) records equations, scope,
provenance, source settings, approximation details, and rerun commands. Tests cover
both models, derivative fixtures, numerical refinement, model-specific schema and
snapshot fields, eager/JIT agreement, padding, read-only observations, branching,
and CLI restoration. All **119 tests passed** with warnings treated as errors in
19.70 seconds; lint, format, and both environment dependency checks also passed.
The test result is [m1b-tests.xml](m1b-tests.xml).

## Quantitative comparison

At fixed Snail 72, both starting states were run to exactly 10000 source-time units,
with RK4 step 0.1: 100000 accepted steps per case, CPU float64. Error below means
the maximum absolute difference across all three primary coordinates and the
accepted trajectory, not merely the final label.

| Check | E-like start | M-like start |
| --- | ---: | ---: |
| JAX versus independent Radau | 9.15655e-8 | 6.25927e-7 |
| BDF versus Radau | 1.36589e-9 | 1.10106e-8 |
| Refinement ratio, step 0.2 to 0.1 | 16.6874 | 16.6809 |
| Refinement ratio, step 0.1 to 0.05 | 16.3460 | 16.3157 |
| Maximum mRNA complex partition residual | 5.32907e-15 | 8.52651e-14 |
| Unchanged replay from 5000 | Exact full suffix | Exact full suffix |
| Native source sampled trajectory versus Radau | 0.00512427 | 0.0234677 |

The independent solvers use rtol=1e-11, atol=1e-12. Before the full acceptance
comparison, tolerances were fixed at 1e-6 for JAX/Radau, 1e-7 for BDF/Radau,
0.1 for the native adaptive-Euler sampled trajectory, and refinement ratios in
(12,20). The source Euler comparison uses a different accuracy contract and
does not define the high-accuracy oracle. All comparisons passed.

All 36 source derivative probes agree within 7.10543e-15; their derived complexes
agree within 2.13163e-14 (each required absolute error below 1e-11). The source's
full isolated simulator and its regulatory gate supplied identical regulatory
slopes at these probes. Native helper outputs were finite and nonnegative at all
saved samples and at the live endpoint. The upstream checkout stayed unmodified.

| Cells final coordinate | E-like start | M-like start |
| --- | ---: | ---: |
| miR200 total | 83.99620026441329 | 8.817966186145386 |
| Zeb mRNA total | 5.951805843082383 | 68.62439028585261 |
| ZEB protein | 0.4100548570488725 | 62.721311537190836 |
| Source-style label | E | M |

The source's last saved samples occurred at 9956.355 and 9960.305; its live
accepted endpoints were 10000.315 and 10000.27. In these settled cases their
primary values coincide, but their times do not. Source endpoint versus Radau
at the source endpoint time differs by at most 2.13163e-14. Cells does not
silently call the source's last sample an exact requested endpoint.

## Artifacts and commands

The [source capture](../runs/m1b-2026-09-08/source-reference/reference.json)
records the pinned revision, six source hashes, unchanged settings, worker limits,
native sample trajectories, accepted state and clocks, and environment. Numerical
fixtures remain tracked even when these ignored run directories are unavailable.

The final [acceptance receipt](../runs/m1b-2026-09-08/acceptance-final/verification.json)
records the verifier/oracle/source hashes, tolerances, errors, and individual
timings. It validates every payload hash and both complete replay suffixes.
Its four run directories are `e`, `e-resumed`, `m`, and `m-resumed`.

```bash
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
.reference-venv/bin/python -m pip check
taskset -c 0-3 .venv/bin/python scripts/verify_emt_build.py runs/m1b-2026-09-08/source-reference/reference.json --output runs/my-emt-acceptance
```

Output directories must be new. Ordinary tests need neither network nor the
optional reference environment. CPU runtime remains Python 3.13.5, JAX/jaxlib
0.11.1, NumPy 2.5.3, SciPy 1.18.1. No GPU was used. Compilation, synchronized
execution, observation, transfer, and output timings are separated in manifests;
these small isolated runs are not a GPU or whole-organ scaling benchmark.

## Previous checkpoints are preserved, not silently migrated

Version 0.1.0 source and supporting definitions/tests/docs were archived before
package edits, after reverifying the three M1a runs:
[cells-0.1.0-source.tar.gz](cells-0.1.0-source.tar.gz), SHA-256
`7539ea7ecc74c07b4092337b797fddb887b5926539e5815f94ceacc5c36533e0`.
The original [M1a report](M1A_ACCEPTANCE.md) and run artifacts are unchanged.
Current Cells correctly refuses those checkpoints because source/runtime identity
changed. Cross-version migration remains unimplemented; rerunning an old config
under 0.2.0 creates a new run, not a migration of its previous numerical snapshot.

To verify old artifacts with their archived source, without replacing this package:

```bash
cells_archive_dir=$(mktemp -d)
tar --extract --gzip --file reports/cells-0.1.0-source.tar.gz --directory "$cells_archive_dir"
PYTHONPATH="$cells_archive_dir/src" taskset -c 0-3 .venv/bin/python "$cells_archive_dir/scripts/verify_first_build.py" runs/m1a-2026-09-08
```

This still requires the old pinned dependency versions and compatible host. The
temporary archive directory is intentionally left available for inspection.

## Limits and next action

This is isolated regulation, not a complete physical cell, bioelectric-contact
replication, tumour model, wet-lab result, memory/PH demonstration, organ, or GPU
benchmark. Source physical-unit correspondence, paper-table provenance, and any
future source-code redistribution rights remain unresolved. Snail is fixed,
complexes use the source's total-miRNA approximation, and labels are observations.

Next: two cells, one explicit contact, and a conservative transport fixture with
active/blocked and unequal-volume controls. Source-selective coupling follows
under its own equations, unit mapping, stiffness checks, and provenance contract.
