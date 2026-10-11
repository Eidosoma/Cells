# MODEL-004 acceptance: Cells 0.6.0

Date: 2026-09-08 UTC. Outcome: `bioelectric_pair@1` is implemented and verified
against the frozen independent physical-pair reference. Six production models
are runnable. This is synthetic dimensional engineering, not calibrated biology,
source-assay parity, a heredity result, tissue/organ simulation or GPU execution.
See the [run guide](../docs/BIOELECTRIC_PAIR.md). M1 remains open for source-compatible
coupling, independent-world execution and representative profiling.

## Delivered engineering

Two cells reuse the one-cell membrane laws and conservative graph scatter from
the same RK stage. Separate cell/membrane/edge capacities, stable identities,
one maintained bath and diagonal capacitance closure are explicit. Amounts own
charge. The endogenous junction gate, signed transfer history and diagnostic
dissipation integrals are checkpointed; none is a second ionic inventory.
Gate conformational energy, gating current and control costs are excluded.

Independent leak/pump/contact groups resolve to a control PyTree with separately
sized membrane and edge arrays. The common checked engine handles it without
assay-specific branches. A blocked contact retains its identity and its gate
continues evolving. One flux is scattered with opposite signs at its endpoints.

Use CPU float64 RK4 with maximum nominal step 1 ms, as qualified by NUM-003,
not the older one-cell 5 ms bound. Every stage and endpoint is checked. Cubic
observations hold the same interval control at both endpoint slopes, return
stored endpoints exactly, and check all amount/gate/affine-voltage interior
extrema even without interior samples. Invalid state, slopes or coefficients
are refused without clipping or result publication. This floating-domain check
is not an interval-arithmetic accuracy proof.

All **670 tests passed** with warnings treated as errors in **270.23 seconds**:
the previous 542 plus 127 physical-pair unit cases and one CLI integration case.
The retained result is [model-004-tests.xml](model-004-tests.xml), SHA-256
`d7594d90fbd516b15b6cba521161c607cdf3336c453f1b909c62eb9d1ad3233f`.
Coverage includes all 20 independent full trajectories, equations/limits/signs,
padding/identity/control order, sub-step events, exact five-boundary replay,
future branching, all layout fields and state checksums, gate-only analytics,
unequal-capacitance conservation, eager/JIT and refinement, numerical-failure
refusal, and incorrect linear/post-event-slope/interior-overshoot negative controls.
CLI checks run, resume and branch in fresh processes. Lint, formatting, installed
dependencies and whitespace checks pass; no runtime dependency was added.
Documentation checks cover 31 Markdown files, 59 tables and 436 local link
occurrences (including heading anchors), with no unresolved targets. All 64
Python files pass Ruff formatting checks.

## Frozen-reference comparisons and artifacts

The [acceptance receipt](../runs/model-004-2026-09-08/acceptance/verification.json)
has SHA-256 `344467bf3b49c5955ba9791d5bb582caa1d07dc315c174f40ac1abd1297cdabc`.
The [NUM-003 receipt](../runs/num-003-2026-09-08/qualification/verification.json)
remains pinned to `7c69c33f76dc6658b10b2cd874d9787ef03f1ae817050827c04d9c3596c1df2a`.
Before use, the verifier checked its 203 payload hashes, eight-source capsule,
38669 native accepted states, 81 implicit segments and 21 exact event continuations.
The frozen panel, oracle equations and targets were not changed for production.

The 20 cases compare directly with saved refined Radau arrays, not references
regenerated to fit JAX. A separate six-second future branch compares with the
same independent oracle at refined tolerances; its definition, solver statistics,
native increments and comparison arrays are saved. Across 22 pair runs the audit
checks all 109027 accepted and 420041 observed states. Instantaneous independent
readout comparisons use an explicitly bounded total of 5409 samples (at most
257 per run), not every RHS trial.

| Quantity | Maximum accepted error | Maximum observed error | Unchanged limit |
| --- | ---: | ---: | ---: |
| Ion amount, fmol | 6.48015e-12 | 6.48015e-12 | 1e-7 |
| Leak ledger, fmol | 1.78166e-12 | 2.92360e-12 | 1e-7 |
| Pump history, fmol cycles | 2.12327e-13 | 2.12327e-13 | 1e-7 |
| Contact transfer ledger, fmol | 4.73343e-12 | 4.73343e-12 | 1e-7 |
| Gate fraction | 1.14882e-8 | 1.14882e-8 | 1e-7 |
| Derived voltage, V | 8.35366e-11 | 8.35366e-11 | 1e-6 |
| Diagnostic dissipation, pJ | 3.00142e-11 | 4.29831e-11 | 1e-6 |

Errors include all panel endpoints and quarter/half/three-quarter interval samples,
plus the branch's accepted/requested times. They are sampled maxima, not rigorous
continuous-time error bounds. Largest independent accounting residuals are
1.76911e-12 fmol material, 1.47135e-11 V charge-as-voltage and 5.51102e-11 pJ
resolved energy, against 1e-8, 1e-8 and 1e-6 respectively. The bounded fast-gate
10 ms eager/JIT run differs by at most 1.73472e-18 across state coordinates.

The ten-second baseline takes 10000 steps and ends at voltages
[-0.0627671281992, -0.0615802613798] V and gate 0.964422680211. Its junction
transfer is [-0.00639897208803, 0.00164074117790, -0.000834270961354] fmol.
The independently controlled branch retains all prior history, includes a 0.7 ms
block, takes 4003 further steps and ends with transfer
[-0.00858665621845, -0.00978290028128, -0.000385654162206] fmol.
Neither endpoint is called equilibrated or biologically validated.

The final [release audit](../runs/model-004-2026-09-08/release-audit.json), SHA-256
`2ca3f5fa87de7bcd256364c17396bec3fe97e735ff00bf1649984e237c47b23f`, verifies
**62 run manifests, 504 payload hashes and 159 complete snapshots** across pair
acceptance and five regression suites. All match the same 28 package-source
hashes and pinned runtime. The editable package is installed as 0.6.0.
CPU affinity was bounded to cores 0–3. Tests and acceptance overlapped there;
timings are diagnostics, not controlled or representative performance benchmarks.

## Earlier-model regressions

All five prior acceptance suites pass under 0.6.0 in new directories:

- [Synthetic source/decay](../runs/model-004-2026-09-08/synthetic-regression/verification.json):
  analytic pulse, exact resume and future rechallenge.
- [Passive pair](../runs/model-004-2026-09-08/pair-regression/verification.json):
  active/blocked, pulse/release, matrix reference, refinement and replay.
- [Reaction/transport](../runs/model-004-2026-09-08/composition-regression/verification.json):
  eight examples, independent matrix/accounting/refinement and complete replay.
- [Isolated regulation](../runs/model-004-2026-09-08/regulatory-regression/verification.json):
  36 native probes, full 10000-unit E/M trajectories, Radau/BDF/refinement and replay.
- [Physical one-cell](../runs/model-004-2026-09-08/physical-cell-regression/verification.json):
  all 18 frozen NUM-002 cases, complete restart and independently controlled branch.

A separate comparison found **all 40 previous-model trajectories exactly equal
to 0.5.0 across all 1189 stored arrays**, including observations and immutable
layouts. No older model's equations, numerical bounds or observation policy were
changed. Provenance/version metadata and diagnostic timings differ.

## Version preservation

Before production edits, all 25 source hashes matched NUM-003's recorded 0.5.0
identity. Its 40 runs, 294 payload hashes and 87 snapshots were checked. Source,
tests, scripts, configurations, documentation and dependency declarations were
preserved in [cells-0.5.0-source.tar.gz](cells-0.5.0-source.tar.gz), SHA-256
`6bfd584592a23899409505419149ebbdd66532a985f32821b844f5caf6f1cd3a`.
Extraction verified every package hash and reproduced the saved six-second
baseline checkpoint suffix exactly. Current 0.6.0 correctly refuses 0.5.0
snapshots as source-mismatched; no compatibility check was weakened. All four
earlier source archive checksums remain unchanged.

To restore with the archived source and compatible pinned runtime:

```bash
cells_archive_dir=$(mktemp -d)
tar --extract --gzip --file reports/cells-0.5.0-source.tar.gz --directory "$cells_archive_dir"
PYTHONPATH="$cells_archive_dir/src" taskset -c 0-3 .venv/bin/python -m cells resume runs/model-003-2026-09-08/acceptance/baseline_10s/snapshots/step-001200 --output runs/my-archived-05-replay
```

The accepted implementation has a separate 41-file
[source capsule](../runs/model-004-2026-09-08/acceptance/implementation_sources.zip),
SHA-256 `50719603d444598c776f0f823ac8650b754543cc108670a548bac6b1f4b008cd`.
Its sources are identical to retained passing `development-02`. The incomplete
`development-01` retains its earlier 40-file capsule, SHA-256
`f294cd79dbdf9450f79404ade92d8d4256b0bd437fc78022fb819dd059f7c8a2`.
That first artifact audit stopped on an overly strict exact current-reduction
assertion: independent summation differed by at most 5.05e-29 A. Unit-test
orientation/padding comparisons similarly exposed roughly 1e-21 pJ reduction
roundoff. These cross-calculation checks now use explicit tight tolerances;
same-layout restart remains bitwise exact. A test overflow input was corrected
to actually overflow. Nonfinite cubic coefficients/slopes were additionally
hardened against unsampled interior failure. No reference or physical accuracy
target was relaxed and no failed development directory was overwritten.

## Reproduction and next scope

```bash
taskset -c 0-3 .venv/bin/python scripts/verify_bioelectric_pair_build.py --output runs/my-physical-pair-acceptance
taskset -c 0-3 .venv/bin/python scripts/verify_bioelectric_build.py --output runs/my-physical-cell-regression
taskset -c 0-3 .venv/bin/python scripts/verify_composition_build.py --output runs/my-composition-regression
taskset -c 0-3 .venv/bin/python scripts/verify_emt_build.py runs/m1b-2026-09-08/source-reference/reference.json --output runs/my-regulatory-regression
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

The pair verifier defaults to the pinned NUM-003 directory; `--reference` may
identify a verified copy. It refuses an existing output or changed oracle/panel.
Ordinary tests construct independent references locally and need no generated
runs, network or upstream checkout. The synthetic/passive verification scripts
are read-only auditors: first generate their example run sets, then pass the run
root positionally and an optional new JSON receipt with `--output`. Their earlier
acceptance reports retain those CLI reproduction sequences.

Next pin a complete source-compatible model and a small active/blocked coupled
trajectory panel. Preserve its algebraic gate, upwind transport and nominal-unit
contract; do not silently substitute the physical pair. Preparation criteria,
physical EMT mapping, representative graph/world profiling, multirate/fine-coarse
methods, tissue/organ presets and GPU execution remain separate work. This turn
did not inspect or run the continuing research agent's experiments.
