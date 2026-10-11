# NUM-005c1 A1: tighter BDF reference diagnostic

2026-09-09 / D035. Status: **registered agreement target, artifact audit and all 1337 tests pass**.
The original qualification count remains ten of 14. This diagnostic does not
reclassify the failed original trio or run the remaining controls.

## Registered scope and engineering

The user approved one tighter BDF reference run after the
[retained miRNA-only disagreement](NUM005C1_CONTINUATION.md). The
[A1 guide](../docs/E02_BDF_REFINEMENT_A1.md) and
[amendment](../configs/reference/e02_bdf_refinement_a1.json) specify one fresh
1000-unit path from the exact original assay anchor. Multiply both BDF tolerances
by 0.1 (nominal rtol 1e-11, atol 1e-12), retaining the original maximum step 0.1,
equations, checked Jacobian, dense-domain/accounting checks and 0.1 reference
agreement threshold. No further tolerance sweep is authorized.

The [registration](../runs/num-005c1-a1-2026-09-09/bdf-tight-01/registration.json)
has SHA-256 `8879e53b387bda2f17ae8d3d7c0725bfed2820f20152d6c4d5f5671b97528fea`.
The 35-file [source capsule](../runs/num-005c1-a1-2026-09-09/bdf-tight-01/reference_sources.zip)
has SHA-256 `4af9023f85809a378b6d448758a9e8734568108580d1d991367a141a6f05a90f`.
The unchanged three prior paths are imported from their original locations,
with pinned completed-curve auditing and complete payload/source checks.

New multi-root comparison plumbing records all four sampled states and all six
pairwise comparisons on the union of every accepted endpoint, midpoint, original
observer time and phase boundary. The required diagnostic pairs are tighter
BDF against each Radau setting, plus the two Radau settings against each other.
Original-BDF comparisons stay visible and are not silently removed from the
old failed evidence. Reader generators close on normal and exceptional exits.

Keep one CPU float64 worker, affinity 0–3, single-thread libraries, the original
900-second trajectory and 3600-second scientific session, working-array and
step/RHS caps. All prior long-reference artifacts count against the aggregate
1 GiB quota: 511,109,773 old bytes leave 562,632,051 bytes for this new root.
No old chunks are copied, linked, overwritten or dropped.

Before the source freeze, all 91 targeted reference tests passed in 27.34
seconds with warnings as errors, including 23 new A1 checks. They cover exact
inputs and the single refinement, source/registration tampering, aggregate
quotas, timeout/failure retention, no retry, explicit imported reader cleanup,
four-input comparison-grid/state/score auditing and bit-exact tighter-BDF
accepted states and dense coefficients against the original numerical recorder.
The fixtures do not execute any 1000-unit scientific path. Lint and formatting
checks passed before the long run.

## Outcome, audit and remaining work

The [single registered trial](../runs/num-005c1-a1-2026-09-09/bdf-tight-01/verification.json)
passes its predefined agreement target. Its maximum required score is
**0.005334691340757373**, below the unchanged 0.1 limit. The original BDF
disagreement remains visible at 0.22626951094532805 on the enlarged grid; no old
result was relabelled as passing. Verification SHA-256:
`1b84b3d3bcb3ca19b64271294a1896b5bde14118cab37326ca8bdf21c7592a38`.

| Required diagnostic pair | Maximum score | Limit |
| --- | ---: | ---: |
| Radau / refined Radau | 0.00009791451918650563 | 0.1 |
| Radau / tighter BDF | 0.005334674482439988 | 0.1 |
| Refined Radau / tighter BDF | 0.005334691340757373 | 0.1 |

| Retained original-BDF diagnostic pair | Maximum score |
| --- | ---: |
| Radau / original BDF | 0.22626951094532805 |
| Original BDF / refined Radau | 0.22626946830184846 |
| Original BDF / tighter BDF | 0.2251706107681209 |

All eight comparison quantities remain recorded for every pair. The maximum
required score comes from regulatory state; tighter BDF's regulatory-history
score is also below 0.1 against both Radau paths. The comparison retains
103,243 union-grid times in 404 chunks, with all four complete sampled states.
The largest online reconstructed accounting residual across these imported/new
samples is 7.815970093361102e-12, below 2e-9. The maximum over the original three
references changes slightly because the new BDF path contributes extra sample
times, not because any original state, threshold or evidence was edited.

The new path reaches exactly 1000 units in 17,704 accepted steps and 70 chunks,
using 188,698 solver/Jacobian RHS calls. Worker time is 230.398458497948 seconds;
the full scientific session takes 425.5550031559542 seconds including comparison
and closeout checks. Both remain below the unchanged caps. Actual binary64
solver rtol is 1.0000000000000001e-11 from multiplication by 0.1, and atol is
1e-12. The trajectory and comparison working-array estimates are 3,374,976 and
13,139,968 bytes respectively, each below 256 MiB. No new integration was
launched after this single trial.

The [independent artifact audit](num-005c1-a1-audit.json) passes in
102.52272595500108 seconds. It verifies all 483 new payload hashes and the
35-file source capsule, with all pinned earlier payloads and source identities
rechecked. It independently checks the new dense trajectory; the maximum
reconstructed residual is 1.4424017535930034e-12, below 2e-9. It rebuilds the
complete four-input union grid, verifies every saved state against its source
trajectory and independently reproduces all four primary/history score groups
for all six method pairs. Derived voltage/flux/cache/gate scores remain
online-recorded results, not independent RHS recomputations by this auditor.

The new root occupies 71,314,547 bytes (484 files including the verification
receipt). All three old/new roots together occupy 582,424,320 bytes, below the
unchanged 1,073,741,824-byte cap; the original partial and failed attempts are
included. No old evidence was copied, modified or omitted from accounting.

The [full regression suite](num-005c1-a1-tests.xml) passes: **1337 tests**,
including 23 new A1 tests, zero failures/errors/skips, with warnings treated as
errors, in 584.77 seconds. Lint, formatting, dependency and documentation link/
table checks also pass. All 39 production source hashes and all earlier
closeout, preparation and registered-source identities remain unchanged.

```bash
env JAX_PLATFORMS=cpu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python -m pytest -q -W error --junitxml=reports/num-005c1-a1-tests.xml
```

The [scoped closeout](num-005c1-a1-closeout.json) records passing engineering,
diagnostic agreement and auditing, without claiming original-panel completion.
A diagnostic pass means the predefined tighter-BDF agreement target is met;
it does not prove the cause of the original BDF error, establish a rigorous error
bound, publish a qualified biological outcome or automatically amend the panel's
reference acceptance policy. The original failed trial remains unqualified.
Production stays at 0.10.0; NUM-005c1, RK4 qualification and later production
graph/assay work remain open.

## Recommended next decision

This result shows that tighter BDF tolerances meet the comparison target for
this unchanged case; no change to cell equations or error thresholds was needed.
It does not identify a BDF implementation defect or prove global error bounds.

The next proposed step is to formalize an amended, accuracy-driven reference
policy, use the audited tighter BDF path for this case with both unchanged
Radau references, and record its reference-only observers. Preserve the failed
original BDF path and its status. Then register completion of the three remaining
controls under explicit settings and aggregate budgets. The policy must depend
on numerical agreement, not a desired phenotype; this single diagnostic does
not itself authorize that continuation or close NUM-005c1.
