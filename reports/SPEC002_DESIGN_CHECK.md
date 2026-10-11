# SPEC-002: selective-contact design evidence

Completed 2026-09-08 UTC. The [physical pair contract](../docs/SELECTIVE_CONTACT_SPEC.md)
and [source map](../docs/SOURCE_COUPLING_MAP.md) are specified and instantaneously
checked. **No physical pair is registered or integrated by this work.** The
runnable package is still Cells 0.5.0, with all 25 production source-file hashes
unchanged from the beginning of this design step.

## Verification

- 709 independent instantaneous checks pass: 106 for pinned native contact
  correspondence, 603 for the new physical equations and limiting cases.
- 36 new tests cover the complete checker, retained fixture identity,
  gate-state/history distinction, independent inhibition, invalid domains and
  deliberately corrupted source meanings.
- Full suite: **483 passed in 114.93 s**, warnings treated as errors. This includes
  the 447 existing tests; [JUnit record](spec-002-tests.xml).
- Lint, formatting (53 Python files), dependency and whitespace checks pass.
  Documentation checks pass for 27 Markdown files, 51 tables and 365 local links.
  The eight captured upstream hashes, two capture-harness hashes, checker/fixture
  receipts, test XML and unchanged existing acceptance receipt were reverified.
- No dependency/version change, GPU job, source patch or continuing-agent
  experiment. No full source or coupled physical trajectory was launched.

The native capture uses BITSEY revision
`b2cb370aaecbc8299f259bc4251d5396c81f19a6` in the already separate reference
environment: Python 3.13.5, NumPy 2.5.3, SciPy 1.18.1, Matplotlib 3.11.1.
One fresh subprocess is bounded to 60 seconds and CPU cores 0-3, with native
math-library threads limited to one. It only calls instantaneous functions,
including one two-cell full-RHS probe with membrane transport disabled.
The clean checkout was verified before and after. `zombie.py` was read/hashed,
not imported; none of the continuing experiment adapters were imported.

## What is established

Native fixtures verify signed upwind drift/diffusion, full-RHS voltage orientation
and scatter, three algebraic gate families at five voltages, conductance amplitude
versus probability, closed/full-block selectivity, and miRNA's primary/proxy and
temporary drift-charge roles. The source's default is valence -1, not the -20
in stale surrounding comments. Its gate adds no evolving memory.

Independent physical checks cover reciprocal constant-field exchange, zero-voltage
and neutral diffusion, Nernst limits, per-species residual and fully impermeant
routes, contact inhibition, a stable gate target, inward boundary slopes and the
fixed-voltage analytic gate solution. A 225-point concentration-ratio/voltage/
gate/control panel verifies passive direction and reciprocal signs.

The pair ledger calculation deliberately uses unequal volumes and capacitances.
It checks per-species internal cancellation, affine/direct charge closure,
capacitance-weighted voltage change, and resolved bath/pump/transport energy.
The energy check explicitly excludes gate conformational energy/current/cost.

For the proposed baseline, initial A -> B flux is
`[-0.0005842358395709245, -0.0015370675141613678, 0.000022402330526346456]`
fmol/s. The gate target is 0.8788782427321509 and its initial slope
3.144391213660754 s⁻¹. The resolved instantaneous energy residual is
2.0194839173657902e-28 J/s. These are equation checks, not time-integrated outcomes.

Two native/physical comparison points intentionally disagree: at normalized
voltage `log(2)` and concentrations 1 and 2, native upwind flux is
-0.3068528194400547 while constant-field flux is zero; at 0.8, the corresponding
values are -0.2 and 0.14722702326712467. The checker requires that distinction
remain visible rather than treating the laws as interchangeable.

### Development correction retained

The first physical ledger check used a fixed 1e-24 C absolute roundoff threshold
and failed at -1.5505597517534537e-24 C after adding/subtracting a small ledger
to/from much larger floating-point amounts. The revised algebra check uses an
operand-scaled bound, `8*epsilon*q_f*sum(abs(nref))`, here
7.52583938907233e-23 C. This is a stated arithmetic bound, not a physical tolerance
fit. The proposed trajectory-accuracy targets were not changed, and no failed
trajectory or test case was removed. The final checker also compares the analytic
gate solution's independently written derivative with its RHS.

## Reproduce and inspect

Ordinary tests and the design checker need only the main environment and retained
numeric fixture; they do not need the network or upstream checkout. Choose new
output names: both capture directories and verification files refuse overwrite.

```bash
taskset -c 0-3 .venv/bin/python scripts/check_selective_contact_contract.py
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
```

To repeat the optional native capture using the existing clean pinned checkout:

```bash
taskset -c 0-3 .reference-venv/bin/python scripts/capture_contact_reference.py upstream/bitsey --output runs/new-contact-source
taskset -c 0-3 .venv/bin/python scripts/check_selective_contact_contract.py --source-reference runs/new-contact-source/reference.json --output runs/new-contact-source/design-check.json
```

The original [native capture](../runs/spec-002-2026-09-08/native-contact/reference.json)
is byte-identical to the retained [numeric fixture](../tests/fixtures/contact_source_probes.json).
[The design receipt](../runs/spec-002-2026-09-08/design-check.json) records the
checker hash, source-fixture hash, runtime, counts and numeric results. Capture
provenance records eight reviewed upstream file hashes and both harness hashes.
Generated runs/logs are ignored local artifacts; the fixture and this report are
retained in the project. Source-code redistribution remains a separate question.

| Artifact | SHA-256 |
| --- | --- |
| Native capture / retained fixture | `714a1cd51d11e4cee00db212ee1bc243ef7776d015d82e38a1c6c0568816fe86` |
| Design receipt | `4297348a948f8a38bd4874133cd26e44d2eb66a18177210d8b8df01cbff1d78e` |
| Capture harness | `6b2655c4570cac76c9ff55c45b940858b523e5f87611aa998d6a4266b74b8bd1` |
| Existing capture provenance helper | `86e5062c4d771ba835260b9b369b19cb59107e1608ba2097601f6a2b51a4ef1e` |
| Independent checker | `fbec1f370d80d2348b45bc2004759bbdaf3bb8bd93bf5e636c8b6a888498d884` |
| Full test XML | `d0c7a7e43ca34b69ccc806f25fc02afbcfe10b565bbe67463b9f04bda81af877` |

The existing MODEL-003 acceptance receipt retains SHA-256
`9d25b98df09dd4e915430bb4811193730ba9d9469fba512f94831169f0ac2f5b`.
Earlier release evidence and all production source hashes are unchanged; no new
source archive or implicit checkpoint migration is necessary for this step.
Archive 0.5.0 before the next actual production edit.

## Next gate and limits

NUM-003 next freezes and integrates the specified 20-case independent panel,
qualifies solver/refinement, positivity, gate bounds, observations and accounting,
and determines a bounded timestep or different numerical method. MODEL-004
follows with production/replay/regression acceptance. Instantaneous checks do
not qualify coupled RK4 or cubic observations; the one-cell 5 ms bound is not
inherited. CONTACT-003 remains in progress until a separately identified
source-compatible model and coupled source trajectories pass.

R005's H3/H4 document check-in is recorded in
[Scientific basis](../docs/SCIENTIFIC_BASIS.md#r005-completed-exploration-findings-and-design-consequences).
Those are source-reported completed results, not Cells reruns. Nothing here
establishes paper-table parity, wet-lab calibration, new PH evidence, organ
function or GPU performance.
