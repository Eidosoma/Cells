# MODEL-005 acceptance: Cells 0.7.0

Date: 2026-09-08 UTC. Outcome: `bitsey_emt_pair@1` is implemented and passes all
14 frozen NUM-004 cases, exact full-state replay and an independently solved
future-control branch. Seven models now run through the shared CPU/JAX engine.
This is bounded nominal source-model engineering, not physical EMT calibration,
full Levin-assay parity, a memory/heredity result, an organ or GPU execution.
See the [run guide](../docs/SOURCE_EMT_PAIR.md) and [progress](../PROGRESS.md).

## Delivered engineering

The model composes separately typed ionic and regulatory state, independently
expressed source membrane/contact laws, the existing pure EMT component and
shared graph scatter. Fixed P/Snail/ST context and initial accounting anchors
are explicit. Complete leak, pump, ionic transfer, local regulation and miRNA
transfer histories survive restart without feeding back into dynamics.
Voltage, algebraic gate scales and binding diagnostics are pure readouts.

A reusable route-axis control definition resolves ionic and miRNA inhibition
independently, alongside per-membrane leak/pump schedules. Existing physical
control shapes and laws are unchanged. Cell, membrane, bath and contact IDs are
distinct from padded storage slots. The shared runner, stepper, observation
machinery and snapshot format need no source-assay branches or test-case names.

Use the frozen maximum RK4 step of 0.01 **nominal source-time units**, exact event
splitting and interval-held cubic observations. Trial states, endpoints, finite
history coefficients and all primary/affine-voltage polynomial extrema are
checked. Invalid trajectories are refused, not clipped. This is a floating-point
domain check, not rigorous interval arithmetic or a general error guarantee.

Source-specific GHK regularization, pump eligibility/activity conventions,
upwind drift, algebraic gate amplitudes and approximate free-miRNA semantics
remain inside the named profile. miRNA drift valence does not confer voltage
charge. No physical regulatory-energy inequality or endogenous cancer-expression
mechanism is inferred. Configuration parsing does not qualify a new parameter
regime or long simulation horizon.

## Tests and frozen-reference acceptance

All **852 tests pass in 300.08 seconds**, with warnings treated as errors: the
previous 783 plus 68 production unit cases and one fresh-process CLI integration
case. The [JUnit record](model-005-tests.xml) has SHA-256
`5d7b1e4a3bd6f5c7b05a5e1297e8ad148fdec042ad7566ae3e97396ee734d8d2`.
Coverage includes strict schemas, resource guards, all frozen paths, independent
routes, base-permeability pump eligibility, zero voltage, asymmetric orientation,
padding/renaming/order, sampling independence, eager/JIT, complete replay at five
boundaries, future branching and invalid stage/cubic-interior refusal.

The [production verifier](../scripts/verify_source_pair_build.py) checks the
unchanged [NUM-004 receipt](../runs/num-004-2026-09-08/qualification-01/verification.json),
its 155 payload hashes and eight-source capsule before comparing with saved
refined Radau arrays. The panel, independent equations and numerical targets
were not changed to fit production. Accepted time grids agree exactly with the
qualified RK4 grids; observations include midpoint and irregular/event samples.

| Check | Measured maximum | Limit |
| --- | ---: | ---: |
| Accepted-state normalized numerical error | 0.002529123 | 1 |
| Observed-state/readout normalized numerical error | 0.027101800 | 1 |
| Independent typed accounting residual | 6.61617e-13 | 2e-9 |

Normalized scores cover primary coordinates, ionic/regulatory histories,
voltages, gate scales and fluxes using the separately typed targets in the
[numerical contract](../docs/SOURCE_EMT_PAIR_NUMERICS.md). The accounting maximum
combines residuals measured in their own coordinate units, not one physical
inventory. These are sampled maxima, not continuous-time error bounds.

The saved five-unit S01 restart reproduces all later state and observation
arrays exactly. The future branch independently inhibits/restores miRNA contact
and cell A pumping while retaining ionic exchange and all prior history. A
fresh independent Radau solve under the changed whole protocol checks all 502
accepted branch states and its two declared observation times. The largest
branch accepted score is 0.000840998. Its definition, native solver states,
comparison arrays and statistics are retained separately.

Across 16 source-pair runs, the verifier checks 142 run payload hashes, 47 complete
snapshots and 12890 independently reconstructed observation readouts. It captures
46 implementation/reference/configuration files, including all 31 production
source files, in an immutable source capsule. The
[acceptance receipt](../runs/model-005-2026-09-08/acceptance-01/verification.json)
has SHA-256 `8f8ef8a3897e26c0ed2b2c49c3b44748f23b3fdb16ff2d64a5aba86f3b8c83b8`;
the [capsule](../runs/model-005-2026-09-08/acceptance-01/implementation_sources.zip)
has SHA-256 `5ffe4c1817f13aa8768de2dbde5e8300617fe607817aae284dfd08c0efce9513`.

## Earlier models and preserved source

All six earlier independent acceptance suites pass in new 0.7.0 directories:
synthetic source/decay (3 runs), passive pair (5), reaction/transport composition
(8), isolated regulation (4), physical cell (20) and physical pair (22).
All **62 trajectories and 2663 arrays** exactly match accepted 0.6.0, including
array inventories, shapes and dtypes. Their existing numerical/reference/replay
checks also pass; this is not merely a comparison of endpoint labels.

The [regression receipt](../runs/model-005-2026-09-08/previous-models-02/verification.json),
SHA-256 `906757f656042ea59ce72fbd6e6c54b4b03c646989fb555547b3bd901671fba3`,
records 500 payload hashes and 157 new snapshots. These fresh runs omit two
optional time-zero snapshots previously saved for synthetic pulse and passive
active; the complete trajectories, six-unit restart and final checkpoints are
unchanged. All 159 accepted historical snapshots were separately verified.

Accepted 0.6.0 was preserved **before production edits** in
[cells-0.6.0-source.tar.gz](cells-0.6.0-source.tar.gz), SHA-256
`ba8b0621186b39b4b745ba2539b1fb363c22d808632a3652f9227baf211c4899`.
Its 28 production files exactly match the prior acceptance identity. Using the
archive in a temporary source tree, all 159 accepted old snapshots load and the
physical-pair Q00 six-to-ten-second replay is exact. Current 0.7.0 correctly
refuses that old source identity. There is no silent checkpoint migration.
The earlier 0.5.0 archive remains unchanged.

The first archive audit incorrectly searched development directories as well as
accepted suites. It encountered a development snapshot whose source differed,
and strict loading correctly refused it. This
[failure](../runs/model-005-2026-09-08/previous-models-01/failure.json) is retained.
The audit's scope was corrected to snapshots listed by the six accepted suites;
no source-identity rule, solver setting, equation or accuracy target was relaxed.

The final read-only [release audit](../runs/model-005-2026-09-08/release-audit.json)
has SHA-256 `924fc049557bb132b63798af6244b3cbf89205fa9e2e2d7008329c1a7aea5367`.
It rechecks **78 new runs, 642 run payload hashes and 204 snapshots**, common
runtime/source identity, all 46 capsule entries, the 2663 unchanged prior arrays
and test receipt. The separately archived 0.6.0 replay is not counted as a new
0.7.0 run.

## Environment and reproduction

Linux x86_64; Python 3.13.5; JAX/JAXlib 0.11.1; NumPy 2.5.3; SciPy 1.18.1;
CPU float64, no RNG. The existing [dependency lock](../requirements-lock.txt)
is unchanged. Editable package metadata was refreshed locally to 0.7.0 without
installing dependencies. All 85 Python files pass lint/format checks; installed
dependency and scoped whitespace checks pass. The pinned BITSEY tree remains
clean at `b2cb370aaecbc8299f259bc4251d5396c81f19a6`; no new upstream or continuing
research-agent experiment was run and no upstream code was vendored.
Documentation checks pass for 37 Markdown files, 70 tables and 549 local link
occurrences, including heading anchors, with no unresolved targets.

Commands below run from Cells with new output paths. The regression driver uses
bounded subprocesses and temporary archived source automatically; it does not
overwrite accepted old runs or substitute current source for old checkpoints.

```bash
taskset -c 0-3 .venv/bin/python -m pytest -q --junitxml=reports/model-005-tests-rerun.xml
taskset -c 0-3 .venv/bin/python scripts/verify_source_pair_build.py --output runs/my-model005-acceptance
taskset -c 0-3 .venv/bin/python scripts/verify_previous_models.py --output runs/my-model005-regressions
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

The frozen NUM-004 artifacts must remain available for acceptance. Its historical
reference-only drivers intentionally check the old 0.6.0 production tree; rerun
that stage with its preserved source at the expected project root, not by
removing the guard. MODEL-005 has a separate verifier for the current source.
Generated arrays, archives and JUnit records are local ignored artifacts; the
tracked reports retain identities and regeneration commands.

CPU affinity was restricted to cores 0–3. Tests and acceptance overlapped on
those cores; elapsed times are diagnostics, not controlled performance results.
No GPU feasibility or differentiability claim follows from forward JAX parity.

## Next bounded work

CORE-004 should exercise independent-world batches: explicit world-local state,
IDs, schedules and histories, no cross-world exchange, scalar parity, complete
restart and bounded allocation/output. PERF-001 should separate compilation,
steady-state work, output and memory costs on representative graphs and pairs.
These measurements inform later GPU and computational-multiscale decisions;
independent worlds are not interacting organs.

CONTACT-003 remains open for longer selected E02 switching protocols. Memory/
relay assays, full-state donor-removal operations and endogenous cancer-expression
strategies need their own pinned mechanisms, preparation and numerical gates.
The original NUM-004 native release-clock failure and passing refinements remain
historical evidence, not a new native capture or an all-assays claim.
