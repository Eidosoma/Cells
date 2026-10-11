# NUM-004: source-compatible coupled qualification

Date: 2026-09-08 UTC. **The bounded independent numerical candidate is qualified;
production implementation is next.** All 14 frozen cases pass RK4 with a maximum
0.01 source nominal-time step and checked cubic observations. Native-source
correspondence qualifies with the explicitly recorded S12 clock refinement;
the original timing failure is retained, not relabeled as a pass.

Cells remains 0.6.0 with all 28 production source hashes unchanged. No dependency,
physical time mapping, production source-compatible model, source-assay parity,
biological validation, organ result or GPU execution is added. The continuing
exploration and its environment were not modified or invoked.

The [numerical contract](../docs/SOURCE_EMT_PAIR_NUMERICS.md) and
[complete model specification](../docs/SOURCE_EMT_PAIR_SPEC.md) define the scope.

This is the historical 0.6.0 reference-stage record. Subsequent production
implementation and its separate checks are recorded in
[MODEL-005 acceptance](MODEL005_ACCEPTANCE.md). The reference drivers' unchanged
0.6.0 source-identity guard is intentional; use that preserved source when
reproducing this stage, not the current production package.

## Independent qualification

- Three study cases at four predeclared RK4 steps: all 12 trials pass.
- All 14 cases at the selected 0.01 step and its half: all 28 trials pass.
- Radau, BDF and refined Radau provide 42 qualification solves; the study has
  nine further solves. Qualification dense-output checks cover 8268 implicit
  polynomial intervals, including admissibility at interior extrema.
- The selected-step qualification has 5903 RK4 intervals and 11887 comparison
  times. Complete state, histories, voltages, scales and fluxes are compared,
  not only regulatory endpoints or E/M labels.
- **783 tests pass in 247.24 s**, with warnings treated as errors. This adds
  24 independent numerical tests, nine recorded-source audit tests and 15
  artifact/protocol tests. [JUnit record](num-004-tests.xml).

Final lint and formatting checks pass for 77 Python files; both environments
pass dependency checks. Documentation checks cover 35 Markdown files, 68 tables
and 507 local links, including heading anchors. The final read-only artifact
check verifies 473 independent/comparison payload hashes, all eight source
capsules, and 56 native phase payloads including the duplicate observer witness.
All 45 successful capture receipts and six retained worker failures are present;
upstream remains clean and all 28 accepted production hashes still match.

All error targets were kept unchanged. The largest selected-step normalized
error is **0.0271018**, where one is the limit. The largest reference disagreement
on that grid is 0.00221408 against a limit of 0.1. Maximum absolute RK4/cubic
errors over the selected-step comparison grid are:

| Quantity | Maximum absolute error | Candidate target, absolute + relative |
| --- | --- | --- |
| Ionic concentration | 3.56550e-11 | 5e-8 + 5e-10 relative |
| Regulatory coordinate | 1.35585e-7 | 5e-6 + 5e-8 relative |
| Ionic history | 3.12864e-11 | 5e-8 + 5e-10 relative |
| Regulatory history | 1.35570e-7 | 5e-6 + 5e-8 relative |
| Cell voltage | 1.56766e-10 V | 5e-7 V |
| Junction scale | 3.07020e-8 | 5e-6 + 5e-8 relative |
| Membrane/junction flux | 1.11050e-13 | 1e-13 + 1e-5 relative |

Ionic and regulatory quantities retain their distinct source-coordinate units;
the maximum flux combines numerical errors across separately typed entries.
Absolute maxima and normalized maxima need not occur at the same sample or
coordinate. These are sampled accuracy measurements, not formal ODE error bounds.

S05's normalized regulatory-history error falls from 0.0271018 at 0.01 to about
0.001705 at 0.005, consistent with fourth-order refinement in this measured
regime. Tiny errors in nearly stationary prepared cases reach roundoff plateaus;
monotone fourth-order ratios are not asserted there. No larger-than-0.01 trial
or longer-horizon guarantee is inferred.

The separate [saved-state auditor](../scripts/audit_source_pair_numerics.py)
imports neither Cells nor the reference RHS. Its [receipt](../runs/num-004-2026-09-08/independent-audit-01.json)
verifies both eight-entry source capsules, 201 payload hashes, 10808 implicit
accepted states, 38152 RK4 accepted states, and 305760 stored comparison-state
rows. All 15 implicit event continuations carry every coordinate exactly.
Independent typed exchange accounting stays below 1.184e-12, versus 2e-9 allowed.
Reversing the edge and swapping hemichannels preserves the full reoriented
history to 6.94e-18; reversing the edge alone changes a primary coordinate by
0.288727. No endpoint fitting or extra gate memory was introduced.

## Native comparison and the retained timing failure

The original cohort contains 42 paths: all 14 cases at three native Euler
refinement levels. Every accepted primary update is checked in the source's
literal multiplication/addition order, together with integer clocks, fixed
context, phase carryover, refreshed versus lagged caches and plotting samples.
All 400452 steps pass these audits. Independent instantaneous RHS witnesses
number 9923, with maximum discrepancy 1.422e-14.

Each native path is compared at every accepted time against refined Radau/BDF
under its realized event schedule, starting from the original prepared or
constructed packet. All 14 original fine runs meet the separate native state
targets and coarse-to-fine contraction checks. Their worst normalized state/
readout score is 0.217101. The two refined reference methods disagree by at most
0.000542639 in production-target-normalized units, versus 0.1 allowed.

Thirteen cases also pass the intended-schedule gate. S12 does not: its original
fine release, requested at 0.137, actually occurs at 0.1439. The delay changes
RNA enough to produce a timing-state score of 1.22326, exceeding one despite
small Euler error at the realized clock. The
[original comparison receipt](../runs/num-004-2026-09-08/native-comparison-01/verification.json)
therefore correctly remains `native_qualification_incomplete`.

After observing that failure, the separate frozen
[extension](../configs/reference/source_emt_pair_event_refinement_v1.json)
predeclared two further S12 refinements, halving and quartering the fine native
time quantum, voltage-change bound and fractional-concentration bound. Both
were executed. Original equations, prepared packets, events, targets and
150000-step limit were unchanged.

| S12 native level | Actual release | Realized-state maximum score | Intended-schedule state maximum score |
| --- | --- | --- | --- |
| Original coarse | 0.51 | 8.50298 | Not an accepted fine witness |
| Original medium | 0.1765 | 0.354938 | Not an accepted fine witness |
| Original fine | 0.1439 | 0.0294185 | 1.22326, fail |
| Additional half-fine | 0.13725 | 0.0141164 | 0.0443327, pass |
| Additional quarter-fine | 0.13755 | 0.00706933 | 0.0975307, pass |

The [extension comparison](../runs/num-004-2026-09-08/native-event-comparison-01/verification.json)
passes every unchanged finest-level gate, including contraction. Its 59775 new
accepted steps and 652 further RHS witnesses bring the distinct native evidence
to **44 paths, 460227 steps and 10575 witnesses**. The original fine S12 is
recompared in the extension but counted only once in these totals. The baseline
13 passing case gates plus the passing S12 extension are the combined numerical
handoff; the baseline itself is not retrospectively a 14-case pass.

Clock error is not monotone on the legacy integer adaptive grid. The quarter-fine
release is slightly later than the half-fine release, although both pass and
realized-state Euler error decreases. Near stationarity, a tiny base time quantum
can still permit a long step: S00-fine ends at 10.45965 for a requested 10. These
are nominal source clocks, not physical seconds. Exact production event splitting
must not be weakened to reproduce such legacy outputs.

Native plotting caches are deliberately retained in their raw lagged form;
pure state-derived comparisons reconstruct endpoint caches. The actual flux
readout difference across a shifted discontinuity is recorded separately from
state-induced error under common controls. No uniform convergence claim across
misaligned discontinuities or equivalence of requested and actual clocks is made.

## Resource limits and preserved attempts

All jobs used CPU affinity 0-3. Independent solves have limits of 200000 RHS
calls, 100000 RK4 steps and 60 seconds per case. Native workers retain a
150000-step limit and maximum total clock of 20 nominal units. Original settings:

| Native level | Minimum time quantum | Voltage-change bound | Fractional concentration bound |
| --- | --- | --- | --- |
| Coarse | 0.005 | 1e-4 V | 1e-3 |
| Medium | 0.0005 | 1e-5 V | 1e-4 |
| Fine | 0.00005 | 1e-6 V | 1e-5 |

The first native cohort completed 39 of 42 captures; S01/S03/S04 fine exceeded
the 60-second recording budget. A lower-overhead read-only source-line recorder
reproduced the completed S00-fine witness byte-for-byte, including its NPZ hash,
but the same three fine runs again exceeded 60 seconds. All six timeouts remain
in `native-01` and `native-02` with logs and source capsules.

An explicitly recorded resource-only increase to 180 seconds allowed those
three captures to finish in `native-03`. No numerical setting or acceptance
target changed. The two event refinements used the same 180-second cap. Native
source was never patched: tracing only observes the source loop. Captures retain
the exact recorder version; comparison capsules retain their baseline or
extension-aware driver. The eight-file independent study/qualification identity
is unchanged throughout.

The reference environment uses Python 3.13.5, NumPy 2.5.3, SciPy 1.18.1 and
Matplotlib 3.11.1. Main tests use the existing CPU lock and JAX 0.11.1.
The pinned BITSEY revision is `b2cb370aaecbc8299f259bc4251d5396c81f19a6`.
No upstream license file was found, and no upstream implementation was vendored.
Some verification jobs overlapped on this host: timings are resource records,
not representative throughput measurements or GPU projections.

## Reproduction and provenance

Use the existing environments and new output directories; no installation is
needed. Independent qualification and unit tests need no upstream checkout.
Native capture additionally needs the clean pinned checkout, optional reference
environment and retained original prepared-state capture named in the panel.

```bash
taskset -c 0-3 .venv/bin/python scripts/verify_source_pair_numerics.py --mode study --output runs/new-source-study
taskset -c 0-3 .venv/bin/python scripts/verify_source_pair_numerics.py --mode qualification --study runs/new-source-study --output runs/new-source-qualification
taskset -c 0-3 .venv/bin/python scripts/audit_source_pair_numerics.py --study runs/new-source-study --qualified runs/new-source-qualification --output runs/new-source-audit.json
taskset -c 0-3 .reference-venv/bin/python scripts/capture_source_pair_trajectories.py upstream/bitsey --output runs/new-source-native --worker-timeout 180 --budget-note 'Recorded capture-only resource allowance; unchanged numerical limits and targets.'
taskset -c 0-3 .venv/bin/python scripts/compare_source_pair_native.py --native runs/new-source-native --qualified runs/new-source-qualification --output runs/new-source-native-comparison
```

The original three-level comparison is expected to retain S12's timing failure
and return exit code 1; it is not sufficient evidence to mark every case passed.
The recorded extension is a separate operation:

```bash
taskset -c 0-3 .reference-venv/bin/python scripts/capture_source_pair_trajectories.py upstream/bitsey --output runs/new-source-event-refinement --native-extension configs/reference/source_emt_pair_event_refinement_v1.json --runs S12-event_finer S12-event_finest --worker-timeout 180 --budget-note 'Recorded native-clock refinement with unchanged acceptance targets.'
taskset -c 0-3 .venv/bin/python scripts/compare_source_pair_native.py --native runs/new-source-native --native runs/new-source-event-refinement --qualified runs/new-source-qualification --native-extension configs/reference/source_emt_pair_event_refinement_v1.json --output runs/new-source-event-comparison
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
```

The extension pins the original failed comparison's hash as decision provenance;
new execution receipts include fresh timings and may have different hashes.
Actual authoritative paths for this session are in [Progress](../PROGRESS.md).
Generated trajectories are ignored local artifacts. No historical run or source
capsule was overwritten or removed.

| Artifact | SHA-256 |
| --- | --- |
| Frozen original panel | `b67efad941db1b4c407aeddcac3836acf4a31653f3a1baa513ece6f5ce2e915d` |
| Supplementary numerical protocol | `226cd48ee1d564411d3ecce929b79dcbc323f92e320e51cdb1415742cd510924` |
| Study receipt | `522db6fd2c849e7709173d9a8396f9195d5855baddd038837bdc2b0b8c9e1854` |
| Qualification receipt | `fa8f7332bccf033f04236c1ff81dc7e838533d00828db63b17847e4613294190` |
| Qualification source capsule | `0e73b31439c2cfaad26bcf17133731a02907493b6b23b4236ac52d52023aae02` |
| Independent saved-state audit | `f7565bc6cd79017d1374cfbdf3ceb015eed7dcf927639ceaf6aa1c963f1d80da` |
| Original native comparison, retained timing failure | `57cb7306cca513ebf8f4ba7ecc821186b633dfe27ab6164204308146e111a53d` |
| Native event-refinement protocol | `390f38f536fd59f53843054755e8a9bacad08f293f48612fda9e4da51b58aaeb` |
| Passing event-refinement comparison | `4c0ef5bbc926c77920830b76ccbf2380f97c61fd88176448bd656b7700c6c042` |
| Final 783-test XML | `fe322e2a4f77effde50f139547182262d1cfd7beb71f4838f3f7d2693b039707` |

## Next implementation gate

MODEL-005 is ready. Preserve accepted 0.6.0 source before production edits;
implement the qualified nominal pair through shared state/mechanism/schedule/
observation interfaces, keeping source-specific quirks local to the model.
Verify full JAX trajectories, diagnostic history, exact replay and independent
future-control branches, capacity and stable identity, domain refusal, and all
six prior models. Preserve the stricter candidate targets instead of adopting
the looser native Euler budget. Selected memory/relay preparation and boundary
operations, endogenous cancer-expression strategies, profiling and GPU work
remain later gates.
