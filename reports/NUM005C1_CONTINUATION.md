# NUM-005c1: registered continuation and composite reference panel

Started 2026-09-08, stopped 2026-09-09 / D034. Status: **reference disagreement;
panel unqualified/incomplete; artifact audit and all 1314 tests pass**. No RK4 timestep or
production graph is selected. No budget or tolerance was changed after the stop.

## Registered scope

The [continuation guide](../docs/SOURCE_GRAPH_CONTINUATION.md) defines one new
bounded session. The [first session](NUM005C1_LONG_REFERENCE.md), its interrupted
attempt, all payloads and all 25 archived source dependencies stay unchanged.
The new implementation imports only its eight complete, independently audited
reference trios. It rechecks the exact prepared packets, source/runtime identity
and every prior payload before each new worker and at closeout.

The [new registration](../runs/num-005c1-2026-09-08/continuation-01/registration.json)
has SHA-256 `354269b779a029c74106672f45c8932cee6730d13c5862a4da5c5e68da539e63`.
Its 29-file [source capsule](../runs/num-005c1-2026-09-08/continuation-01/reference_sources.zip)
has SHA-256 `440abff5d0bbe9a392d23e5bfdb65ab858a8d7d7e8475e2a7c4cf59a07e47e1b`.
The six remaining M-to-E conditions are blocked, ionic-only, miRNA-only,
same-state, one-neighbour and isolated, each at Radau, BDF and refined Radau.
Order is derived from the original attempt list, not JSON object order.

The original `M_to_E/blocked/radau` attempt is still incomplete and retained.
Its new session-qualified attempt starts at time zero from the exact assay
anchor, not the old partial clock or a private adaptive-solver checkpoint.
Original preparation histories remain in provenance; new assay ledgers start
at zero. All cells evolve freely, without phenotype-dependent numerical branches.

The old root occupies 387,154,280 bytes. The new root therefore receives
686,587,544 bytes of the unchanged aggregate 1,073,741,824-byte artifact quota.
That explicitly derived local allowance covers all new trajectory, comparison
and observation writers. Lossless recording, conservative uncompressed-batch
preflight and the 4 MiB metadata reserve are unchanged. Unknown sibling files,
symlinks and hard links are refused.

One sequential CPU float64 worker uses affinity 0–3 and single-thread libraries.
The 900-second trajectory and 3600-second additional scientific-session limits
are unchanged. Final comparison/readout and integrity work count toward the
session. No automatic retry, budget extension, GPU or native long driver runs.

## Engineering verification

The preparation, long-reference and new continuation tests passed together:
107 tests in 25.29 seconds, with warnings as errors. After tightening closed/live
session checks, all 24 new continuation tests passed again in 13.48 seconds.
These are short fixtures, not additional long scientific trials. Lint and format
checks passed before the registered source freeze.

The tests cover exact remaining order and imports, refusal of altered evidence,
incomplete-path promotion, lower aggregate quota, linked artifacts, exclusive
outputs, exact fresh starts, single-attempt stopping without retries and the
full composite case mapping. Short three-method paths with the derived storage
allowance also pass independent dense domain/accounting checks. The initial
timeout-log fixture caught hashing before its buffered log was flushed; the
new orchestrator flushes before recording that hash. No numerical change was
needed, and no scientific continuation was launched before the tests passed.
Three additional pure saved-sample diagnostic tests pass in 0.08 seconds with
warnings as errors. The diagnostic is explicitly post-hoc, not a new reference
trial or a modification of the prospectively archived sources.

## Results and closeout

The session stopped after 1409.0426863470348 seconds at the unchanged numerical
gate, not its resource cap. Nine new 1000-unit trajectories completed. Blocked
and ionic-only qualified, bringing the cumulative total to ten qualified
conditions. The miRNA-only trio did not qualify: maximum normalized disagreement
0.22626789470158734 exceeds the frozen reference limit of 0.1. Same-state,
one-neighbour and isolated were not started (nine planned attempts). All work
and the [stopping receipt](../runs/num-005c1-2026-09-08/continuation-01/failure.json)
are retained; there is no automatic retry or additional session.
Stopping receipt SHA-256:
`4a432c2f8341b5cd949abf51b776f165cf98951cdd6bf2167168d8853965b194`.

| New condition | Comparison samples | Maximum score (limit 0.1) | Outcome |
| --- | ---: | ---: | --- |
| M_to_E / blocked | 61,946 | 0.0066148662261367955 | Qualified; recipient M at all 102 terminal observations |
| M_to_E / ionic_only | 62,264 | 0.003095486551971143 | Qualified; recipient M at all 102 terminal observations |
| M_to_E / mirna_only | 67,836 | 0.22626789470158734 | Unqualified; no qualified observer outcome |

The two qualified cases each retain all 1007 observers. Their donors stay E and
no label is unresolved. Nonswitching is an allowed result, not a numerical failure.
Together with the prior eight audited cases, ten of 14 conditions now qualify.

The failing quantities are regulatory state (0.22626789470158734) and regulatory
history (0.14831628439082498) in Radau-versus-BDF comparisons. BDF-versus-refined
Radau similarly fails. Radau-versus-refined Radau remains below 0.1 for every
quantity. This localizes the disagreement to comparisons involving BDF; it does
not prove which trajectory is correct or authorize discarding a required method.
No qualified miRNA-only observer/phenotype outcome is published.

The [post-hoc discrepancy diagnostic](num-005c1-disagreement.json) independently
reproduces every stored regulatory state/history maximum for all three method
pairs from the retained comparison chunks. The largest primary discrepancy is
recipient cell 100's `Zeb_mRNA_total` at time 404.4905051573776:

| Quantity | Value |
| --- | ---: |
| Radau value | 6.359167592332305 |
| BDF value | 6.359166389049072 |
| Absolute difference | 1.2032832330532983e-6 |
| Allowed reference difference at BDF value | 5.317958319452454e-7 |

The largest local regulatory-history discrepancy is also recipient Zeb mRNA,
at time 404.0. The Radau/refined-Radau maximum regulatory-state score is only
7.309000677005044e-5. These are source-coordinate values and nominal source
times, not a physical calibration. The failed trio's full 67,836-sample union
grid was additionally audited with the original independent helper. This
read-only localization and grid check took 1.0271282580215484 seconds under an
explicit 60-second limit; no RHS or new integration was evaluated.

The [independent continuation audit](num-005c1-continuation-audit.json) passes in
488.9789850729867 seconds. It rechecks all 1181 new payload hashes, the 29-file
source capsule, all 3218 original payloads and pinned prior subset evidence.
It independently checks all nine new complete dense trajectories, including the
unqualified trio, plus the two qualified comparison grids and observer records.
The largest new independently reconstructed accounting residual is
7.815970093361102e-12, below 2e-9. Its passing audit status explicitly preserves
campaign status `unqualified` and `NUM005c1_complete: false`.

The new trajectories contain 94,525 accepted steps in 372 chunks, with 662,565
solver/Jacobian RHS calls. The largest per-path count is 95,339 and the longest
worker takes 141.89001269597793 seconds. The largest trajectory working-array
estimate is 3,374,976 bytes. All three comparisons retain 192,046 sample times
in 751 chunks, including the failed comparison. The new root occupies
123,955,493 bytes; the two roots together occupy 511,109,773 bytes, below 1 GiB.
The old partial attempt is included and unchanged.

The [full regression suite](num-005c1-continuation-tests.xml) passes: **1314 tests**,
including 24 new continuation tests and three new post-hoc diagnostic tests,
zero failures/errors/skips, with warnings treated as errors. Elapsed time is
571.90 seconds. Lint, formatting, dependency and Markdown link/table checks pass.

```bash
env JAX_PLATFORMS=cpu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python -m pytest -q -W error --junitxml=reports/num-005c1-continuation-tests.xml
```

A passing integrity/domain/accounting audit or software suite cannot overturn a
failed cross-method accuracy gate. NUM-005c1, NUM-005c2, MODEL-006 and ASSAY-002
remain open. Production remains at 0.10.0 with all 39 source hashes unchanged;
old preparation and earlier closeout hashes reverify. The
[scoped closeout receipt](num-005c1-continuation-closeout.json) explicitly separates
passing engineering verification from the unqualified scientific panel.

## Next decision

Do not discard BDF, relax the reference agreement threshold, select RK4 or run
the unstarted controls under a new session automatically. The next proposed
scientific action is a named, separately registered BDF refinement diagnostic
on this unchanged miRNA-only case, preserving this failed evidence and both
Radau references. That requires an explicit amendment before execution; whether
it resolves the discrepancy is not established by the current evidence.

The [candidate preflight note](../docs/E02_CANDIDATE_PREFLIGHT.md) records the
next engineering considerations without launching c2 or changing its protocol.
