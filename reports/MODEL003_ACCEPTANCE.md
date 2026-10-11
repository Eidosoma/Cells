# MODEL-003 acceptance: Cells 0.5.0

Date: 2026-09-08 UTC. Outcome: the first physical `bioelectric_cell@1` is
implemented and verified through the shared engine. Five models are runnable.
This is synthetic dimensional engineering, not calibrated Na/K-ATPase kinetics,
BETSE/BITSEY parity, biological heredity, tissue/organ simulation or GPU execution.
M1 remains open for selective source coupling and representative profiling.
See the [run guide](../docs/BIOELECTRIC_CELL.md).

## Delivered engineering

The model composes independently expressed GHK leaks and an energized reversible
reference pump from the same RK stage. Amounts determine voltage through immutable
anchors. Separate cell/membrane capacities, stable owner/bath identities, fixed
charge and clamped conditions are explicit and checkpointed. Leak/pump schedules
are independent groups resolved on their event union. No assay name, desired
phenotype or outcome selects a mechanism or numerical path.

The engine adds a reusable checked-RK4 path and a read-only cubic sampler.
Invalid physical trials are guarded before logarithms; finite derivatives,
positive active amounts, padding and voltage domain are checked at every stage
and endpoint. Failure is refused without publishing clipped/repaired state.
Cubic interpolation uses both endpoint slopes under the interval's held controls,
then validates sampled state. All four previous models retain linear observations.

All **447 tests passed** with warnings treated as errors in **125.51 seconds**:
the previous 346 plus 100 physical-model unit cases and one CLI integration case.
The retained result is [model-003-tests.xml](model-003-tests.xml). Coverage includes
physical limits/signs, mask-safe zero-voltage derivatives, all 18 reference cases,
independent and simultaneous events, a 4 ms pulse, exact disabled routes, padding
and identity renaming, refinement, observation independence, incorrect-slope and
linear-interpolation negative controls, invalid trial/endpoint/sample refusal,
resource/schema failures, complete snapshot corruption checks, and exact replay
at five event/regular boundaries. CLI tests exercise fresh-process run, restore,
branch and failed-run refusal. Ruff lint/format and installed dependency checks pass.
Documentation checks cover 24 Markdown files, 44 tables and 317 local link
occurrences, including heading anchors, with no unresolved targets.

## Independent comparisons and saved artifacts

The [physical acceptance receipt](../runs/model-003-2026-09-08/acceptance/verification.json)
has SHA-256 `9d25b98df09dd4e915430bb4811193730ba9d9469fba512f94831169f0ac2f5b`.
It records 18 physical cases, unchanged resume and an independently controlled
future branch. All short-panel comparisons use the frozen, refined Radau arrays
from NUM-002, not trajectories fitted or regenerated to match production.
Their [reference receipt](../runs/num-002-2026-09-08/qualification/verification.json)
is pinned to `8cf0f7a6d33867f5a1172b6eff949c887bf47bf8c0c93d616477e72d4c27d94d`.
All 39 reference payloads and archived oracle/lock bytes were checked before use.
The additional branch uses the same independent oracle at refined tolerances.

Errors below are maxima across the 18 cases and branch, over accepted states
and requested samples separately. Samples include every endpoint and quarter,
half and three-quarter interval positions in the pinned panel; these are not
rigorous continuous-time supremum bounds.

| Quantity | Maximum accepted-state error | Maximum observed-state error | Predeclared limit |
| --- | ---: | ---: | ---: |
| Ion amount, fmol | 1.37678e-9 | 1.37678e-9 | 1e-7 |
| Leak ledger, fmol | 1.39224e-9 | 1.39224e-9 | 1e-7 |
| Pump ledger, fmol cycles | 7.75870e-11 | 7.75659e-11 | 1e-7 |
| Voltage, V | 1.95771e-8 | 1.95771e-8 | 1e-6 |

Maximum independent material residual is 6.72932e-12 fmol (limit 1e-10);
charge residual expressed as voltage is 6.78519e-11 V (limit 1e-8).
The bounded 0.05 s eager/JIT check differs by at most 1.08421e-19 across the
amount/ledger coordinates. This is not a cross-device reproducibility claim.

The 10 s baseline takes 2000 accepted steps and ends with Na/K/Cl amounts
[11.8197385884, 140.1882763353, 10.0078067338] fmol, voltage -0.06299127284 V,
and 0.1888676839 fmol signed pump cycles. The six-second branch retains all
prior ledgers/anchors, blocks Na leakage until 8 s and the pump until 7 s, then
ends at [11.8124066389, 140.1896034585, 10.0018018869] fmol and -0.06299107447 V.
Neither endpoint is labelled equilibrated or biologically validated.

The final read-only audit verified **40 run manifests, 294 payload hashes and
87 complete snapshots** across physical acceptance and the four regression suites.
All manifests matched the same 25 package-source hashes and pinned runtime.
No runtime dependency was added. The editable package is installed as 0.5.0.
CPU affinity was bounded to cores 0–3; tests and acceptance overlapped on those
cores. Recorded timings are diagnostic, not controlled performance benchmarks.

## Earlier-model regressions

All four prior acceptance suites passed under 0.5.0, in separate new directories:

- [Synthetic source/decay](../runs/model-003-2026-09-08/synthetic-regression/verification.json):
  pulse, exact resume, future rechallenge and analytic accounting.
- [Passive pair](../runs/model-003-2026-09-08/pair-regression/verification.json):
  active, blocked, pulse, release, exact replay, matrix reference and refinement.
- [Isolated regulation](../runs/model-003-2026-09-08/regulatory-regression/verification.json):
  36 source probes, full 10000-unit E/M trajectories, Radau/BDF/refinement and
  exact replay. Maximum JAX/Radau errors remain 9.15655e-8 and 6.25927e-7.
- [Reaction/transport composition](../runs/model-003-2026-09-08/composition-regression/verification.json):
  all eight cases, matrix reference, accounting, refinement and replay.

A separate comparison of all 20 earlier-model saved trajectories found every
accepted-state, observed-state and layout array exactly equal to its 0.4.0 run.
Only release/provenance metadata and diagnostic timings differ.

## Version preservation

Before any production edit, all 0.4.0 run payloads and snapshots were checked
against its 22 source hashes/runtime and the source was preserved in
[cells-0.4.0-source.tar.gz](cells-0.4.0-source.tar.gz), SHA-256
`e5d905bc71cdb50a7e189ae98fffb2f0b027de9e52efac118c6f9a80474469b3`.
Extraction verified every archived package hash. The archived package reproduced
the saved chain checkpoint suffixes exactly. Current 0.5.0 correctly refuses
0.4.0 snapshots as source-mismatched; no compatibility check was weakened.
The three still-earlier source archive checksums remain unchanged.

To inspect an old snapshot with its source and compatible runtime:

```bash
cells_archive_dir=$(mktemp -d)
tar --extract --gzip --file reports/cells-0.4.0-source.tar.gz --directory "$cells_archive_dir"
PYTHONPATH="$cells_archive_dir/src" taskset -c 0-3 .venv/bin/python -m cells resume runs/core-003-2026-09-08/acceptance/chain/checkpoint_final --output runs/my-archived-04-restore
```

The original NUM-002 specification and numerical reference remain in its source
ZIP; current documentation has updated delivery status. The reference receipt,
trajectories and oracle are unchanged. A passing development verification remains
under `runs/model-003-2026-09-08/development-01`, with its pre-hardening source in
`development_sources.zip` (SHA-256
`d9bd5fd459e8da47c5bf75819a48205a27e32f2e21387c9c0c31ff4d09c3b805`).
Final acceptance followed clearer concentration conversion and overflow refusal.
An early test-only decimal/product equality assertion was corrected to compare
the declared capacitance product; no physical parameters or targets were relaxed.

## Reproduction and next scope

```bash
taskset -c 0-3 .venv/bin/python scripts/verify_bioelectric_build.py --output runs/my-physical-acceptance
taskset -c 0-3 .venv/bin/python scripts/verify_composition_build.py --output runs/my-composition-regression
taskset -c 0-3 .venv/bin/python scripts/verify_emt_build.py runs/m1b-2026-09-08/source-reference/reference.json --output runs/my-regulatory-regression
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

The physical verifier defaults to the pinned NUM-002 directory; `--reference`
may point to a verified copy. It refuses existing output paths and altered
reference identity. Ordinary tests reconstruct their independent references
locally and require neither generated runs, network nor an upstream checkout.

Next specify endogenous gates, selective contact/electrical closure and the
source-coordinate/time relationship, with independent positive/negative tests
before implementation. Broader parameter regimes need their own numerical
qualification. Finite baths, fields, regulatory coupling, biological replacement,
independent-world batching, multirate/fine-coarse execution, tissues, organs and
GPU performance remain unimplemented. The one-cell fixture is a reusable
foundation for those tasks, not evidence that they are already solved.
