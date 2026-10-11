# M1c-a acceptance: Cells 0.3.0

Date: 2026-09-08 UTC. Outcome: two cells exchange a synthetic quantity through
one explicit passive contact. Active, blocked, release, pulse, and restart checks
pass. This completes the conservative transport prerequisite; M1c-b selective
bioelectric coupling and representative workload profiling remain before M1
closeout. It is not a biological heredity or organ result.

## What works

The third registered model, `passive_pair@1`, uses the existing CPU/JAX runner,
RK4 solver, observers, resource limits, and artifact/restart machinery. A separate
coupling module computes edge flux and reciprocal amount contributions. State and
validation now distinguish cell and edge capacities, stable IDs, physical contacts,
prescribed opening, and signed transfer ledgers. The other two models retain
their original equations and meanings. See the [contact contract](../docs/PASSIVE_CONTACT.md).

All **189 tests passed**, with warnings treated as errors, in 29.51 seconds.
The [test report](m1c-a-tests.xml) includes 69 new pair/kernel unit cases and one
fresh-process pair CLI scenario alongside the original 119 tests. Coverage includes
unequal/equal volumes, reversed transport and edge orientation, slot permutation,
zero permeability, blocked/partial opening, neutral padding, shared endpoints,
off-grid and sub-step controls, final-time events, finite-value guards, invalid
definitions, observer independence, eager/JIT agreement, exact replay at five
boundaries, branch isolation, and checkpoint integrity. Lint, format, and installed
dependency checks pass. No new runtime dependency was needed.

## Quantitative acceptance

The shipped pair starts with [8, 0] fmol in [1, 3] pL and permeability 0.4 pL/s.
Fresh runs end at 12 seconds with nominal RK4 step 0.05 seconds. Active/blocked
runs take 240 steps; the off-grid pulse adds two boundaries for 242 steps.
The equilibrium is [2, 6] fmol at equal concentrations of 2 fmol/pL.

The saved-run verifier uses an independent two-by-two SciPy matrix exponential,
not the JAX coupling code or the scalar closed-form oracle used in unit tests.
Tolerances were set before the recorded acceptance: 3e-8 fmol maximum absolute
reference error, 1e-12 fmol amount/transfer-accounting error, and refinement ratios
between 14 and 20 for steps 0.4, 0.2, and 0.1 seconds over a two-second case.

| Saved run | Final amounts, fmol | Maximum amount error versus matrix reference, fmol | Maximum total-amount error, fmol |
| --- | --- | ---: | ---: |
| Active | [2.0099693439, 5.9900306561] | 9.50969e-9 | 4.44089e-15 |
| Blocked | [8, 0] | 0 | 0 |
| Resumed from 6 s | [2.0099693439, 5.9900306561] | 3.37213e-9 | 4.44089e-15 |
| Released at 6 s | [2.2445732272, 5.7554267728] | 3.37213e-9 | 1.77636e-15 |
| Pulse, 2.03-5.07 s | [3.1858100681, 4.8141899319] | 9.41134e-9 | 1.77636e-15 |

The resumed/released comparisons cover their saved 6-12 s suffixes, explaining
their smaller maximum errors. Per-cell changes match signed edge transfer within
4.44089e-15 fmol across all five runs. The blocked run retains the same physical
contact as the active run and is exactly unchanged. Closing the contact at six
seconds freezes every later amount and transfer entry. Unchanged replay is exact
for the entire accepted suffix, not only its endpoint.

Step-refinement errors are 4.54351e-5, 2.60068e-6, and 1.55577e-7 fmol. Ratios
17.4705 and 16.7163 support fourth-order convergence on this panel.

## Saved artifacts and reproduction

The [verification receipt](../runs/m1c-a-2026-09-08/verification.json) records
runtime/source/verifier hashes, five manifest hashes, error limits, results, and
separate preparation, compilation/cache, synchronized execution, observation,
host transfer, and artifact-write timings. All payload hashes and final snapshots
were checked. Generated `runs/` directories are ignored local artifacts; the
configurations, tests, verifier, and this report are retained in the repository.

To produce a new set, run from Cells with the pinned CPU environment:

```bash
taskset -c 0-3 .venv/bin/python -m cells run configs/pair_exchange_active.json --output runs/my-pair/active --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells run configs/pair_exchange_blocked.json --output runs/my-pair/blocked
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-pair/active/snapshots/step-000120 --output runs/my-pair/resumed
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-pair/active/snapshots/step-000120 configs/pair_exchange_release.json --output runs/my-pair/released
taskset -c 0-3 .venv/bin/python -m cells run configs/pair_exchange_pulse.json --output runs/my-pair/pulse --checkpoint-at 2.03 --checkpoint-at 5.07 --checkpoint-at 6
taskset -c 0-3 .venv/bin/python scripts/verify_pair_build.py runs/my-pair --output runs/my-pair/verification.json
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

Choose new output paths; no overwrite or migration is implied. CPU affinity is
bounded to four permitted cores on this host; adapt it to another host's affinity.
The active pair took about 0.294 seconds for compilation/cache and 0.00135 seconds
for synchronized execution. These tiny-run timings are not a throughput benchmark,
an independent-world scaling study, or evidence of GPU speedup. No GPU was used.

## Previous-model regression and preserved versions

Both earlier acceptance workflows were rerun in fresh directories under 0.3.0:

- [Synthetic regression](../runs/m1c-a-2026-09-08/synthetic-regression/verification.json):
  pulse, exact resume, and rechallenge pass; maximum analytic error 1.77697e-9 fmol.
- [Regulatory regression](../runs/m1c-a-2026-09-08/regulatory-regression/verification.json):
  36 source probes, full 10000-unit E/M trajectories, Radau/BDF comparisons,
  refinement, and exact restarts pass. Maximum JAX/Radau errors remain
  9.15655e-8 and 6.25927e-7, matching the historical M1b result.

The regulatory check reused the existing pinned native source capture; it did
not launch new upstream experiments or change the continuing exploration.
Regeneration commands remain in the [M1a](M1A_ACCEPTANCE.md) and
[M1b](M1B_ACCEPTANCE.md) reports; choose new paths under the installed version.

Before package edits, verified 0.2.0 source and its supporting definitions, tests,
scripts, documents, and historical reports were archived:
[cells-0.2.0-source.tar.gz](cells-0.2.0-source.tar.gz), SHA-256
`1696a7a03564b5667918818647a5050750f165372b2ae2783bc270859c383a5f`.
Afterward, all four old M1b runs were rechecked with this archive: source/runtime
identity, all payload hashes, and final snapshot loading pass. Current 0.3.0
correctly refuses their snapshots with a source-mismatch error.

To inspect old snapshots without replacing this installation:

```bash
cells_archive_dir=$(mktemp -d)
tar --extract --gzip --file reports/cells-0.2.0-source.tar.gz --directory "$cells_archive_dir"
PYTHONPATH="$cells_archive_dir/src" taskset -c 0-3 .venv/bin/python -c 'from cells.io import load_snapshot; print(load_snapshot("runs/m1b-2026-09-08/acceptance-final/e/checkpoint_final").checkpoint.time)'
```

This requires the original compatible runtime/dependencies. The extracted
directory is left available for inspection. The 0.1.0 archive and original
M1a/M1b reports and artifacts remain intact. Cross-version snapshot migration is
not implemented; rerunning an old configuration produces a new-version run.

## Next step and limits

Specify and validate source-selective bioelectric coupling separately, starting
with pinned equations, ions/voltage, dimensional correspondence, primary/derived
state, controls, and a trusted stiff-capable CPU reference. Do not silently attach
this seconds-based passive law to source-scaled EMT coordinates. Representative
batch profiling is still pending before M1 closeout.

This release is a deterministic engineering contact fixture. It does not validate
source switching, tumour dynamics, biological memory, heredity, organ physiology,
multirate/coarse-grained computation, arbitrary graph execution, or GPU performance.
Upstream redistribution terms, physical-time calibration, and paper-table provenance
retain their existing open status.
