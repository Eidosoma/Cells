# CORE-006: multispecies production acceptance

2026-09-09, D048, Cells **0.11.0**. **Pass within the frozen one-cell regime.**
The new `multispecies_membrane@1` family runs through the shared CPU/float64 JAX
engine, with explicit species/valence, pump roles, charge support, diagnostic
histories and complete replay. The seven older families retain their equations,
step limits and exact accepted regression results. This is software/numerical
qualification, not BETSE parity or a new biological result.

The [production guide](../docs/MULTISPECIES_MEMBRANE.md) describes the schema,
state and usage. The [SPEC-005 contract](../docs/MULTISPECIES_MEMBRANE_SPEC.md),
[NUM-006 protocol](../docs/MULTISPECIES_NUMERICS.md) and independent reference
sources remain unchanged. No new implicit reference solve, fit, dependency,
GPU job, optimization campaign or long E02 experiment was run.

## Accepted evidence

Saved session:
[acceptance-02/verification.json](../runs/core-006-2026-09-09/acceptance-02/verification.json).
The [read-only audit](core-006-audit.json) was repeated successfully after the
acceptance command completed; it reconstructs existing refined Radau curves
and independently evaluates readouts without invoking a solver.
The [final release audit](../runs/core-006-2026-09-09/release-audit.json) also
checks all 226 current scalar and 22 cohort snapshots with strict loaders,
authenticates the test receipts and records the final source/workspace identities.

| Check | Result |
| --- | --- |
| Frozen trajectory panel | All 14 Na/K/Cl and synthetic divalent cases pass in both full eager and JIT execution at the preselected 0.01 s maximum actual step |
| Reference error | Maximum observed normalized error 0.0524266426 against a limit of 1; largest voltage discrepancy 5.242664260357577e-8 V (0.00005243 mV) |
| Independent readouts/accounting | 17 instantaneous/accounting/control fields reconstructed independently; material, charge, resolved energy, domain and disabled-route checks pass |
| Eager/JIT agreement | Native and observed canonical arrays agree within 0.001 times the frozen trajectory error budgets; not advertised as bitwise identity |
| Fresh-process scalar restart | All 14 JIT midpoints resume with exact accepted state, observations and layout |
| Future branch | A branch at 0.203 s omits the future pump pulse and agrees with the frozen passive reference; original state and charge/history anchors retained |
| Scalar output inventory | 43 original/restarted/branched runs, 13,164 accepted rows, 230,449 observation rows and 71 snapshots, plus one separately preserved branch-parent snapshot |
| Independent-clock cohorts | Two seven-world cohorts and their two restarts: 28 world instances, 104 per-world windows, 2,808 exact payload-array comparisons; restart changes recording width from 129 to 73 |
| Cohort history and snapshots | 8,882 accepted rows, 155,370 observation rows, 22 complete cohort snapshots containing 154 scalar snapshots; finished worlds remain represented |
| Complete accepted checkpoint inventory | 226 scalar snapshots and 22 enclosing cohort snapshots; enclosing wrappers are not additional scalar states |
| Artifact authentication | 773 payload hashes plus the receipt itself; 60-file implementation capsule includes all 41 production modules and acceptance dependencies |
| Bounded session | 993.226 s before the final read-only audit; 209,703,893 bytes of artifact files, within 1800 s / 512 MiB registered work limits |

The row totals include resumed suffixes; they are not counts of independent
biological experiments. The verification runtime includes compilation, full
eager execution, reference/readout checks, serialization and old regressions.
It is **not** a throughput benchmark or GPU speedup estimate.

## Older models and source preservation

Before editing production, [preserve_core006_baseline.py](../scripts/preserve_core006_baseline.py)
authenticated the accepted 0.10.0 release and archived its 39 production modules
with the original NUM-006 audit environment. The 53-file
[source archive](cells-0.10.0-source.tar.gz) and
[preservation receipt](core-006-preservation.json) remain available.

Under that archived source, all **948 scalar and 99 cohort snapshots** from the
accepted 0.10.0 release load successfully. An archived source-pair continuation
reproduces every original state and observation exactly. Current scalar/cohort
readers refuse those old snapshots instead of silently migrating their identity.

The current production build also passes fresh, authenticated old-model
regressions: **78 scalar trajectories / 3,511 arrays**, **1,777 bounded windows /
30,538 array comparisons**, and **10 batches / 44 worlds / 2,042 arrays** remain
exact. These regressions cover 451,325 accepted scalar rows and 558,729 scalar
observation rows. Old arrays are explicit engineering fixtures, not migrated
production snapshots; no duplicate old trajectories were written.

All existing model assemblies except the dispatch registry, all process laws,
coupling, RK4, observers, scalar/cohort window executors and disk writers are
byte-for-byte unchanged. Seven existing production modules change for version,
typed species/state definitions, control width, resource estimates and batch
compatibility; two modules are added. Of 346 files captured before production edits,
327 remain unchanged. The 19 intentional updates are ten status/design documents,
packaging, seven production modules, and one reference-test fixture's preserved
source context. Existing NUM-006 worktree changes are preserved, not reverted.

## Tests and retained attempts

The complete [test matrix](core-006-tests-02/verification.json) passes:

| Source context | Tests | Failures / errors / skips | Pytest time |
| --- | --- | --- | --- |
| Current production 0.11.0 | 1594 | 0 / 0 / 0 | 555.256 s |
| Preserved reference 0.10.0 | 971 | 0 / 0 / 0 | 156.556 s |
| Total, disjoint test modules | **2565** | **0 / 0 / 0** | **711.812 s** |

The 117 new tests cover definition/domain refusals, independent laws and
trajectories, species permutations/renaming, absent routes with retained charge,
padding, unsampled cubic extrema, resource preflight, controls, exact replay,
branches, batches/windows/cohorts and independently detected rehashed readout
corruption. Historical NUM-005 tests retain their source/packaging, CPU 0–3 and
single-thread environment requirements. The driver uses independent temporary
copies of evidence, without patching historical validators or rerunning the long
campaign. See the [test-context explanation](../docs/MULTISPECIES_MEMBRANE.md#run-resume-and-qualify).

The initially incorrect single-context test call, rejected linked-evidence
workspace and manually interrupted first acceptance session are retained in
[the attempts record](CORE006_ACCEPTANCE_ATTEMPTS.md). They are excluded from
passing totals. No reference equation, fixture, tolerance or numerical guard
was changed to make those attempts pass. Acceptance-02 used unchanged captured
implementation/input bytes from registration to its successful final audit.

Ruff check and format-check pass for all 180 Python files; `git diff --check`
passes. Editable installation reports Cells 0.11.0; `pip check` reports no broken
requirements. The pinned CPU dependencies are unchanged.

## Reproduce and inspect

Use fresh output directories for the commands that create evidence:

```bash
taskset -c 4-7 .venv/bin/python scripts/verify_multispecies_build.py --output runs/my-core006-acceptance
taskset -c 4-7 .venv/bin/python scripts/audit_multispecies_build.py runs/core-006-2026-09-09/acceptance-02
.venv/bin/python scripts/test_cells_build.py --output reports/my-core006-tests
.venv/bin/python scripts/audit_preserved_multispecies_reference.py runs/num-006-2026-09-09/reference-01
```

These commands require the retained reference/old-model evidence and source
archives as well as the pinned local environment; they do not fetch replacements.

| Object | SHA-256 |
| --- | --- |
| Accepted production verification | `2d9352e55e2744f5eb3a41eb51a010d3cac83d3459b928fb495b1a69f39d9ee7` |
| Implementation capsule | `4bf093b89f89d41f9e000cb1917d71ca095ebced4deebf1618feeb2e9f44ed08` |
| Complete test-matrix receipt | `87f5a400b62cf936a4bf6ff658538ef90db8a28398b4c2efaa299c9fef03685c` |
| Preserved 0.10.0 source archive | `24a65b3bd478b76e230670785091b255f51d1427450e15c7b5dabc8a154f6536` |
| Unchanged NUM-006 verification | `331f3dde9ec6093ad1ccd18f27044bc8c30f573c3a596f07642e5c34a2edd41a` |

## Limits and next step

The 0.01 s choice is qualified only for the two frozen assemblies and fourteen
schedules through 10 s. Legal new species/valences, concentrations, geometry,
kinetics or horizons need their own refinement checks. Old physical cell/pair
limits stay 0.005/0.001 s. The divalent fixture is synthetic and unbuffered; it
does not provide a calcium-signaling network. The bath is maintained, not finite.

Proposed next: **SPEC-006**, one state-bearing physical membrane channel with
an independently checked kinetic law and voltage-step/relaxation protocol.
Keep gating, abundance, inhibition and geometry separate. A prescribed-voltage
gate test is not a whole-cell voltage clamp; that would require an explicit
electrode current/charge closure. Connected ionic graphs and finite environments
follow separately. Numeric JAX layouts retain a future device path, but GPU
execution, interacting tissue, multirate/fine-coarse simulation and organ models
remain unimplemented. The closed descriptive pilot and deferred E02 gates are
unchanged.
