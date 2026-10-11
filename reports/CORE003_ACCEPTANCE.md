# CORE-003 acceptance: Cells 0.4.0

Date: 2026-09-08 UTC. Outcome: the engineering composition gate is implemented
and verified. A fourth model combines local reversible conversion with
species-specific transport on data-defined fixed graphs. Source-selective
bioelectricity and representative workload profiling remain pending; M1/M1c
are not complete. See the [model contract](../docs/REACTION_TRANSPORT.md).

## Engineering evidence

The shared runner integrates both processes from the same RK stage state. The
local reaction law is a separate pure module; the existing passive gather/scatter
coupler now preserves leading species/batch axes. Generic observation interpolation
supports arbitrary trailing field axes, and the scheduler supports independent
contact-opening columns resolved by stable contact IDs. No assay ID, desired E/M
label, or source outcome selects execution behaviour.

All **270 tests passed** with warnings treated as errors in 51.76 seconds:
the previous 189 plus 80 composition unit cases and one new CLI integration case.
The retained result is [core-003-tests.xml](core-003-tests.xml). Coverage includes
one, two, three, and five cells; zero edges; reaction-only, transport-only, combined,
blocked and one-way conversion limits; shared/parallel endpoints; cell/species/edge
permutations and renaming; independent contacts; inactive storage; stage derivatives;
noncommuting event order; refinement; sub-step controls; final-time events; empty
observations; eager/JIT agreement; exact restart at five boundaries; independent
branches; metadata, domain, capacity and ledger failures. Lint, format, and installed
dependency checks also passed.

The final read-only artifact audit rechecked 20 run manifests against the current
22 package-source hashes and runtime, verified 126 payload hashes, and loaded all
33 recorded snapshots. All four acceptance receipts passed, their recorded
verifier/reference identities matched, and all three historical source-archive
checksums remained intact. Documentation checks covered 17 Markdown documents
and 200 local link occurrences, including heading anchors.

## Saved examples and quantitative results

The [acceptance receipt](../runs/core-003-2026-09-08/acceptance/verification.json)
records eight saved runs, every payload hash, source/runtime/verifier/oracle
identities, fixed tolerances, independent comparisons, replay, and timings.
The oracle builds its own full linear generator, including signed conversion
and edge ledgers. It imports no production process, coupling, or schedule code.

The three-cell chain starts with species amounts [8,0,1] and [0,2,0] fmol in
volumes [1,3,2] pL: 11 fmol total. It has heterogeneous per-cell forward/reverse
rates and two species-selective contacts with independently prescribed openings.
Fresh cases end at 12 s. Nominal RK4 step is 0.05 s; chain/pair/control runs have
242 steps including 2.03 and 5.07 s events; the isolated cell has 240 steps.

| Run | Maximum amount error versus matrix reference, fmol | Maximum global amount-balance error, fmol |
| --- | ---: | ---: |
| Single reactive cell | 4.84029e-10 | 7.10543e-15 |
| Two-cell reaction/transport | 3.52451e-8 | 3.55271e-15 |
| Three-cell chain | 3.58704e-8 | 1.06581e-14 |
| All contacts blocked | 4.78539e-10 | 7.10543e-15 |
| Connected pair plus isolated third cell | 3.52451e-8 | 7.10543e-15 |
| Transport only | 1.05949e-8 | 1.06581e-14 |
| Unchanged resume, 6-12 s | 1.19133e-8 | 1.06581e-14 |
| Contact release, 6-12 s | 1.19133e-8 | 7.10543e-15 |

Maximum transfer-ledger error is 2.52211e-8 fmol and conversion-ledger error
1.35209e-8 fmol across these runs; all fit the fixed 4e-8 fmol reference limit.
Independent per-species/cell accounting residuals are at most 7.99361e-15 fmol,
below the 1e-12 fmol acceptance threshold. Error maxima are over each saved
trajectory, so suffix-run maxima need not equal full-run maxima.

The chain ends with species totals 3.2764107969 and 7.7235892031 fmol. Total A+B
remains 11 fmol; reactions need not preserve either species separately.
With reactions disabled, both initial species totals, 9 and 2 fmol, are preserved.
Blocking contacts preserves physical topology and produces exactly zero transfer.
Closing them at six seconds freezes all later contact ledgers, while local amounts
and conversion ledgers keep evolving. Unchanged restart matches every field and
time in the entire accepted suffix exactly.

Independent transient refinement at steps 0.4, 0.2 and 0.1 s gives maximum
state/ledger errors 1.80756e-4, 1.00638e-5 and 5.91577e-7 fmol. Ratios 17.9610
and 17.0118 lie within the predeclared 14-20 range for fourth-order convergence.

Three development variants exposed the distinction between stability and accuracy:
equal volumes, parallel edges, and the heterogeneous five-cell graph exceeded the
4e-8 target at the demo step 0.05, with amount errors approximately 8.53e-8,
6.80e-8 and 6.47e-8. Their tests now refine to 0.025, require fourth-order improvement,
and meet the original tolerance without changing model parameters or loosening
the error limit. The supported step bound is not a universal accuracy guarantee.

## Reproduction

From Cells, using its pinned CPU environment and a new output directory:

```bash
taskset -c 0-3 .venv/bin/python scripts/verify_composition_build.py --output runs/my-composition-acceptance
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

The script generates `single`, `pair`, `chain`, `blocked`, `disconnected`,
`transport_only`, `resumed`, and `released`, then audits saved payloads and writes
a new verification receipt. It refuses an existing destination. Configurations,
test oracles, and verifiers are retained; generated `runs/` are ignored local data.
Ordinary tests require no network or upstream checkout. No new runtime dependency
was added; the editable package is installed as 0.4.0.

CPU affinity was bounded to cores 0-3 on this host. Manifests distinguish compilation
or cache lookup, synchronized execution, observation, host transfer, and artifact
writing. Acceptance and the test suite overlapped in wall time on the same bounded
cores, so these timings are diagnostic, not a controlled performance comparison.
No GPU was used and no scaling claim is made.

## Regression and version preservation

All three earlier-model acceptance suites passed under 0.4.0. These 12 fresh
regression runs are separate from historical artifacts:

- [Synthetic source/decay](../runs/core-003-2026-09-08/synthetic-regression/verification.json):
  pulse, exact resume, and changed future input.
- [Passive pair](../runs/core-003-2026-09-08/pair-regression/verification.json):
  all five original transport/control/replay examples and matrix/refinement checks.
- [Isolated regulation](../runs/core-003-2026-09-08/regulatory-regression/verification.json):
  all 36 source probes, two full 10000-unit trajectories, Radau/BDF comparisons,
  refinement, and exact restarts. E/M maximum JAX/Radau errors remain
  9.15655e-8 and 6.25927e-7, respectively.

The prior source was verified and archived before package edits:
[cells-0.3.0-source.tar.gz](cells-0.3.0-source.tar.gz), SHA-256
`296e49081fa628303aedf0a2d19fed54518eeae2dbfe23cc35e267c1e19f89d3`.
The archived package still verifies the old five pair runs, including complete
snapshots, payloads, numerical references, and replay. Current 0.4.0 refuses an
old 0.3.0 snapshot with a source-mismatch error; compatibility was not weakened.

```bash
cells_archive_dir=$(mktemp -d)
tar --extract --gzip --file reports/cells-0.3.0-source.tar.gz --directory "$cells_archive_dir"
PYTHONPATH="$cells_archive_dir/src" taskset -c 0-3 .venv/bin/python "$cells_archive_dir/scripts/verify_pair_build.py" runs/m1c-a-2026-09-08
```

This requires the original compatible runtime/dependencies. The extracted directory
is left available for inspection. Older archives, reports, and run artifacts are
unchanged. Cross-version migration is not implemented.

## What remains

Specify source bioelectric primary state, coordinate/clock mapping, membrane and
selective-contact mechanisms, numerical domain, and independent reference checks
before the next implementation. Use the shared engineering boundaries for those
mechanisms and explicit experiment operations for later switching/relay assays.

This release does not provide arbitrary process discovery, arbitrary reaction
networks, ionic dynamics, the source's communicating regulatory cells, biological
replacement events, whole-world batching, multirate/coarse-scale execution, organs,
or GPU execution. Source unit correspondence and reuse limitations remain open.
