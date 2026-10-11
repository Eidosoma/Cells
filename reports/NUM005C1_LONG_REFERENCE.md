# NUM-005c1: long E02 implicit reference paths

2026-09-08 / D033. Status: **session capped, panel incomplete**. The runner and
44 new short engineering tests pass. Eight conditions have complete three-method
reference qualification and pass independent post-run auditing. All **1287 tests
pass**, including 44 new checks. NUM-005c1 and NUM-005c remain open. There is no RK4 selection,
production graph or biological validation claim.

## Scope

The [reference guide](../docs/SOURCE_GRAPH_PATHS_REFERENCE.md) describes the
bounded implementation. The [E02-SW1 protocol](../docs/E02_SWITCHING_PROTOCOL.md)
and [numerical plan](../docs/E02_SWITCHING_NUMERICS.md) are unchanged.
The accepted [NUM-005b preparation evidence](NUM005B_PREPARATION.md), full packets,
old numerical sources and production 0.10.0 source hashes are preserved.

The [registered attempt](../runs/num-005c1-2026-09-08/reference-01/registration.json)
plans all 14 exact 1000-unit conditions at Radau, BDF and refined Radau settings.
It archives 25 source files before execution. New assay graphs import exact
qualified primary/context arrays with zero new ledgers; full original preparation
histories remain in provenance. All donors evolve; no desired phenotype controls
the numerical outcome.

Registration SHA-256:
`0d203e30191c4f879e7dc029979d354b1a2194aec5f8f2c8a3fb6e4f62cfcab4`.
The retained 25-file source capsule has SHA-256
`bc535e18dfc1681717a671263f8391db908d4b071845c7ab56fff18e206cd131`.

The new lossless compressed recorder preserves complete accepted states, full
dense coefficients and bit-exact carries, without changing the numerical method.
Uncompressed batch estimates still guard the original 1 GiB artifact cap. One
CPU worker with one numerical library thread uses the original 900-second
trajectory and 3600-second scientific session limits; comparisons and readouts
count toward that session. Resource exhaustion means incomplete, not failure of
the biological hypothesis, and does not authorize automatic continuation.

## Verification and results

Before the long campaign, all 44 new engineering tests and all 39 preparation
regressions passed with warnings treated as errors (83 tests in 12.79 seconds).
They cover exact imports, all 14 initial Jacobian checks, bit-exact old/new paths
at all three implicit settings, short zero/one/two-edge paths, separate dense
accounting audits, compression/quotas, uncertain labels, complete comparison-grid
and observer checks, stopped-worker receipts and no automatic retry.

The [retained stopping receipt](../runs/num-005c1-2026-09-08/reference-01/failure.json)
records **3600.007473581005 seconds**, status `incomplete`, 25 started attempts,
24 complete trajectories and 17 unstarted attempts. The approximately 7.5 ms
wall-clock overrun occurred around timeout/receipt handling; no new budget or
session was started. `M_to_E/blocked/radau` was killed at its remaining session
allowance. Its 27 retained chunks contain 6,912 accepted steps, with last written
boundary **679.1111000000853**; this is not a claim about the exact stopping state
of the solver. Its two other settings and five subsequent conditions were not
run. No automatic retry or budget extension occurred. The stopping receipt SHA-256
is `fdebf3a244e185ad3bc45d32fa9f4e7f322c6a2373fcf358e2b210147cb9bac4`.

The 24 complete trajectories contain **254,210 accepted steps**, 1005 complete
trajectory chunks and 1,760,974 solver/Jacobian RHS calls in total. The longest
complete trajectory took 171.26308751100441 seconds, below the 900-second limit.
RHS limits apply per trajectory; comparison/readout evaluation is additional
work and counts toward the session wall budget.
The maximum measured solver/Jacobian count is 112,629 for one complete path;
including its comparison and observer graph-RHS-equivalent evaluations raises
the largest per-path count to 182,819, still below the 2,000,000 limit. The
largest complete-trajectory working-array estimate is 3,374,976 bytes.

The retained campaign occupies **387,154,280 bytes**, below the 1 GiB cap. Its
3085 NPZ files occupy 385,868,600 bytes; their uncompressed NPY contents total
1,136,480,702 bytes. Lossless compression preserves the arrays without dropping
evidence; the uncompressed content alone would exceed the artifact budget.

Eight complete reference trios were compared at **516,406 union-grid times**.
The largest normalized score was **0.03386899459217551**, below the frozen 0.1
limit. All eight recorded 1007 observer times, including 102 terminal observations
per condition. No observed reference label was unresolved.

| Condition | Comparison times | Maximum score (limit 0.1) | Recipient terminal label | First sampled target time |
| --- | ---: | ---: | --- | ---: |
| E_to_M / active | 67,744 | 0.00229825530 | M | 155 |
| E_to_M / blocked | 62,420 | 0.00645458794 | E | Not observed |
| E_to_M / ionic_only | 62,414 | 0.00750008341 | E | Not observed |
| E_to_M / mirna_only | 67,146 | 0.00207202002 | M | 155 |
| E_to_M / same_state | 61,814 | 0.00554650846 | E | Not observed |
| E_to_M / one_neighbor | 62,810 | 0.00486907807 | E | Not observed |
| E_to_M / isolated | 61,868 | 0.00592165961 | E | Not observed |
| M_to_E / active | 70,190 | 0.03386899459 | E | 124 |

Each listed recipient label holds at every terminal observation. The active
E-to-M and miRNA-only target samples have preceding X-labelled samples at 154;
reverse active has an X-labelled sample at 123. These are sampled brackets, not
exact continuous switching times. In the one-neighbour condition, the E recipient
and M donor retain their respective labels. These are outcomes of the unchanged
source equations and topology, not special branches enforcing an expected result.

The separate [post-run audit](num-005c1-audit.json) passes in
**1202.5730220539845 seconds**, within its independently bounded, read-only
3600-second audit allowance. It checks all 3218 payload hashes, 25 archived/live
source identities, unchanged production, all 24 complete dense trajectories,
all eight union comparison grids and their observer coverage/labels/caches/drift.
Its maximum independently reconstructed residual is **8.142819751810748e-12**,
below 2e-9. The interrupted trajectory receives integrity-only treatment, never
numerical promotion. This audit runs no new reference integration and does not
continue the capped scientific campaign. Audit SHA-256:
`c1e0ec7be902316d50cfc605cf7ebe7f4a031c9ad42f1c0813f44f93c016cfbd`.

For this incomplete campaign, the ordinary auditor CLI checks campaign integrity.
The post-run subset audit additionally calls its `audit_trajectory` helper for
each registered attempt with a complete trajectory receipt, and
`audit_comparison_grid`/`audit_observations` for each entry in the retained
`cross_qualified_cases` list, under one shared 3600-second read-only deadline.
These helpers are in the registered source capsule. Flux comparison scores remain
online-recorded results, not independently recomputed by this artifact audit.
The [full regression suite](num-005c1-tests.xml) passes: **1287 tests**, including
44 new tests, zero failures/errors/skips, with warnings treated as errors.
Elapsed time is **580.39 seconds** (JUnit: 580.376). JUnit SHA-256:
`dc391bfafd559270586af3625bd01685b09a4fa0104fe3b9dd88d23244d5df33`.
Ruff lint/format checks and the main environment dependency check also pass.

```bash
env JAX_PLATFORMS=cpu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python -m pytest -q -W error --junitxml=reports/num-005c1-tests.xml
```

All 39 production source hashes, 421 preparation payloads, 12 NUM-005b closeout
payloads, 17 NUM-005a audit payloads and nine SPEC-004 audit payloads remain
unchanged. The [scoped closeout receipt](num-005c1-closeout.json) links the retained
evidence; it explicitly leaves the full long-reference panel incomplete.

The native-style goal diagnostic is deliberately narrower than full-state
equilibrium. For example, E-to-M active is within about 2.3e-8 of its regulatory
goal packet at the endpoint, yet over the terminal 100 units its Na, K and Cl
coordinates change by approximately -0.00104, +0.23897 and +0.23792 source
concentration units per cell. Its membrane and pump histories continue to grow.
No equilibrium, energy closure or physical EMT calibration follows from the label.

## Remaining work

Interpretation remains specific to this deterministic setup: the qualified E/M
packets have identical ionic concentrations, and all cells have matching fixed
bath/membrane parameters. Route-control outcomes alone are not evidence of a
voltage-driven switching mechanism or of biological confirmation. Ionic drift
and typed exchange histories remain available to inspect that distinction.

NUM-005c remains open. NUM-005c2 must execute all registered RK4 study trials,
qualify every preparation and condition at the selected step and half, and check
all four continuations using each candidate's own prepared state. No production
MODEL-006/VERIFY-011 or ASSAY-002 implementation is included here. There is no
new GPU, fluid, organ or continuing-exploration experiment.

Before c2, estimate the full fine-step RK4 evidence volume and execution cost;
do not assume that c1's compression ratio makes the larger study fit. Keep the
frozen budgets, or stop for an explicit amendment with previous evidence retained.

If this session reaches its cap, the next step is an explicitly registered
continuation, not an automatic repeat of the whole panel. Preserve this root
unchanged. Reuse only complete, hash-checked trajectories whose prepared inputs,
methods, clocks and archived source identities match the original registration.
An interrupted trajectory must be a retained failed/incomplete attempt; starting
it again requires a new attempt identity and starts at time zero, not at a private
adaptive-solver checkpoint. A new session must account for aggregate retained
artifacts, including the earlier session, against the original storage budget.
The current CLI deliberately does not yet implement this continuation workflow.
