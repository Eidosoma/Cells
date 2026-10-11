# SPEC-007: physical ionic graph design checks

2026-09-10, D052. **Complete — design and instantaneous reference only.**
Production remains Cells 0.12.0 with no changed production module.

The [contract](../docs/PHYSICAL_IONIC_GRAPH_SPEC.md) composes local physical
membranes and optional Kv1.5-style channels with a data-defined selective ionic
graph. A single shared maintained bath and fixed diagonal capacitances make
the first electrical and energy closure explicit. This is not a new production
graph, coupled trajectory, timestep selection, organ model or biological result.

## Frozen inputs and result

All **14,116 instantaneous checks pass**, with zero failed checks across eight
synthetic definitions. The [machine-readable result](spec-007-design-check.json)
contains the resolved rates, separate ledgers, source identities and all check
groups. Its SHA-256 is
`f649f5b18eddea1ced4d87bf61a936498dae14898f4e77abb67e990c1ac56ca9`.

The [panel](../configs/reference/physical_ionic_graph_v1.json) and contract were
written before evaluation; their hashes are
`6b6e5431e475e6467428f78d99a1b8756c71cac160498b393aff16d7e17dfc7f` and
`04feb84040e18af82e12ca21894e38051ef7bec9f0da214379856274ff54e91f`, respectively.
Twenty source/evidence files and all 44 production modules are bound by the
receipt. All 204 dependencies of the prior accepted implementation still match.

| Check | Evidence |
| --- | --- |
| Single/disconnected reduction | One mono- and one divalent cell; three heterogeneous disconnected cells; exact local rate reduction when edges are absent or blocked |
| Reciprocal transport | 1,890 direct 70-digit Decimal comparisons, reversed orientation, zero-voltage diffusion, individual Nernst balance and nonnegative passive dissipation |
| Complete graph composition | Mono/divalent pairs and shared-recipient three-cell stars; independent incidence accounting, separate local/edge power and one local membrane evaluation per cell |
| Storage independence | 1,390 cell-order, 3,894 species-order and 307 edge-order comparisons; all compared coordinates exact under these permutations on the scalar reference |
| Existing physical pair | 117 comparisons with the older independent hyperbolic pair reference, with membrane channels absent and the declared unequal cell geometry retained |
| Controls and hidden state | Membrane-channel and junction gates continue evolving when their routes are blocked; recorded transfer is neither cleared nor counted as material |
| Histories | Nonzero manufactured ledgers balance amounts/charge; resetting them is detected; a closed-cycle circulation has distinct edge history but zero net node increment |

The largest normalized arithmetic/accounting error is **0.022219**, below the
passing boundary of 1, in a manufactured nonzero material-ledger check. Its
absolute residual is approximately `2.222e-14` fmol, with a declared `1e-12`
fmol allowance. This is floating-point engineering evidence, not measurement
uncertainty. The `energy_pJ` comparison key is used for pJ/s derivative-coordinate
comparisons in this instantaneous panel; finite-history energy accuracy is not
qualified by it. Global power checks independently use watts.

## What this changes in the design

Each edge supplies one signed species transfer to both endpoints, and owns its
own dissipation and history. A shared recipient contributes its membrane/pump
once, not once per neighbor. Species, cell, membrane, channel and edge identities
remain separate, with sparse endpoint mappings suitable for later array kernels.

The unequal-capacitance pair has a nonzero **unweighted** voltage-rate sum,
approximately `0.010342 V/s`, while its capacitance-weighted charge rate balances.
Expecting the simple voltage sum to remain constant would be a wrong conservation
test. This is an instantaneous witness, not a simulated trajectory or endpoint.

The cycle witness also explains why net cell amounts cannot reconstruct all
past interface transfers. It is an algebraically supplied history, not evidence
that a physical loop generated memory, hysteresis or plastic heredity.

The numerical method is deliberately unresolved: increased coupling strength,
small compartments and high-degree recipients can introduce faster modes.
The one-cell 0.5 ms and previous pair 1 ms limits are not graph guarantees.
Future GPU partitions must exchange solver-stage endpoint state, assign one
edge owner and apply the same transfer on both sides. No device implementation
or cross-device bitwise reproducibility is established by these scalar checks.

## Tests and preservation

All **114 new tests pass** in both the [initial preflight](spec-007-preflight-01.xml)
and [final targeted run](spec-007-targeted-01.xml), each in 1.80 s. These include
strict schemas, duplicate/reversed-edge refusal, invalid real blocked entities,
nonfinite/shape failures, optional mechanisms, valence/ID independence, no input
mutation, no production/integrator calls and refusal to overwrite old receipts.
An unused test import was removed after preflight; no equation, panel input,
scientific tolerance or failed numerical verdict was changed. There were no
failed scientific checks or failed tests in these runs.

All **2997 regression tests pass**, with zero failures, errors or skips:

| Source context | Tests | JUnit time (s) |
| --- | --- | --- |
| Current production 0.12.0 | 1821 | 627.890 |
| Preserved NUM-005 / 0.10.0 | 971 | 158.670 |
| Preserved channel references / 0.11.0 | 205 | 18.968 |

[Regression receipt](spec-007-regression-01/verification.json), SHA-256
`a77e469989378b822ae0189e0a693845cc4cdb7fe3ef2ce2f3f0dc424838a4d0`. Summed test-context time is
805.528 s; this is not a simulation performance measurement. All six XML/log
hashes and JUnit counts are rechecked; both preserved source archives retain
their accepted hashes. No historical source guard or test-context driver changed.

The [previous production saved-output audit](spec-007-core007-audit.json) passes
again: 1580 payloads, 44 production modules, 14 reference cases, 43 scalar outputs,
two scalar windows and four cohorts. It rereads saved evidence, without an ODE
rerun. The new instantaneous calculator also reproduces its saved result exactly,
apart from its timestamp.

Against the [428-file pre-edit baseline](spec-007-workspace-baseline.json),
**417 pre-existing files remain byte-identical** and eleven have documentation-only
updates; none is missing. All production modules, packaging, earlier reference
code, pilot data and prior result files are unchanged, including uncommitted work
already present at the start. The [closeout receipt](spec-007-closeout.json) binds
these checks. Ruff checks/formatting pass for 202 Python files, dependencies are
consistent, and all thirteen affected Markdown files pass local-link/structure checks.

To repeat the bounded reference check with a new receipt:

```bash
taskset -c 4 .venv/bin/python scripts/check_physical_ionic_graph.py --output reports/my-spec007-check.json
taskset -c 4 .venv/bin/python -m pytest tests/unit/test_physical_ionic_graph_reference.py -q
.venv/bin/python scripts/test_cells_build.py --output reports/my-spec007-tests
```

## Next gate

**NUM-008:** freeze short graph trajectories, independent methods/refinement,
control-event and observation rules, complete histories, stage/interior-domain
checks and prospective resource limits. Then **CORE-008** may implement and
accept a new production graph identity using the shared execution engine.
No new organ preset, channel catalog, finite extracellular field, biological
fit, GPU optimization or deferred long source E02 campaign is started here.
