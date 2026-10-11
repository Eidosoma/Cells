# NUM-005a: independent fixed-graph composition acceptance

2026-09-08. **Instantaneous reference gate complete; long-time qualification
is not complete.** The [new reference](../docs/SOURCE_EMT_GRAPH_REFERENCE.md)
supports one-cell, pair and larger fixed graphs independently of production.
Cells remains **0.10.0**; no production model, numerical method, dependency or
prepared E02 packet is added. The frozen E02-SW1 protocol and existing pair
reference inputs/equations are unchanged.

## Evidence

The [acceptance receipt](../runs/num-005a-2026-09-08/acceptance-01/verification.json)
passes **18,499 scalar/structural checks** across 45 native derivative inputs
and 17 pair-oracle settings. These are arithmetic and interface checks, not
independent scientific replicates or trajectories. The panel spans 1–5 cells,
including zero-edge graphs and disconnected components. All **118 new tests
pass**. The full suite passes **1204 tests in 560.96 seconds**, with warnings
promoted to errors and no failures, errors or skips. The
[JUnit receipt](num-005a-tests.xml) and [final audit](num-005a-audit.json) retain
that result and 17 payload hashes. The 18-file accepted source capsule and
11-file failed-attempt archive were verified; all 39 production files and the
nine SPEC-004 payloads remain unchanged. Ruff lint/format pass across 113 Python
files, both environments pass dependency checks, and local Markdown checks pass.

| Native quantity | Largest absolute difference |
| --- | ---: |
| Complete evolving RHS | 3.552713678800501e-15 |
| Local regulatory RHS | 3.552713678800501e-15 |
| Junction flux | 4.235164736271502e-22 |
| Membrane leak flux | 3.308722450212111e-24 |
| Pump flux | 2.6469779601696886e-23 |
| Voltage, voltage difference, gate scales, refreshed packet | 0 in this capture |

Differences retain their respective source-coordinate/flux units; they are not
one physical error metric. The registered instantaneous tolerances are unchanged
from the pair comparison. These values do not qualify 500/1000-unit trajectories,
continuous interpolation, equilibrium or a biological switching result.

The graph reference reuses independently written local/constitutive equations,
evaluates cell-local terms once, and adds only edge transfer through an explicit
loop. A separate incidence assembly and individual-cell comparisons check
composition. Tests cover shared-recipient accumulation without degree rescaling,
cell/edge permutations, hemichannel reversal, independent controls, disconnected
components, typed passive ledgers, source approximations, domain refusal and
corrupt/incomplete evidence. All 30 one-edge reference coordinates preserve the
old pair ordering; the old 14-case numerical evidence is not repinned or rerun.

The native worker uses pinned reusable modules, never the cancer driver,
continuing-exploration harness or Cells. It checks full primary/context
preservation, cache refresh, repeatable derivatives, zero nonprimary native
slopes, excluded regulatory charge and restored temporary parameter arrays.
The 14 E02 construction-seed conditions and two preparation seeds are labelled
explicitly: **none is a prepared 500-unit state**.

## Retained first capture failure

[native-01](../runs/num-005a-2026-09-08/native-01/failure.json) is incomplete.
The native RHS returned, but the additional diagnostic collector used
`local[gate.out_ion]` where a tuple of three row indices requires
`local[gate.out_ion, :]`. NumPy interpreted the former as three array dimensions
and refused it. The registered inputs, native log, failure and an 11-file source
archive remain; no failed result is counted as a passing witness.

Only that adapter index changed before
[native-02](../runs/num-005a-2026-09-08/native-02/reference.json). The expanded
input hash, native source, reference equations and tolerances did not change.
The corrected capture passes all 45 conditions. Native invalid-escape syntax
warnings remain in the log; upstream was not patched. This was an
instrumentation error, not a numerical/biological failure or a production fix.

## Provenance and preservation

BITSEY remains pinned to `b2cb370aaecbc8299f259bc4251d5396c81f19a6`, with eight
source hashes matching the existing fixture and a clean checkout before/after
capture. The worker ran under the separate reference environment, on CPU affinity
0–3 with one numerical-library thread and a 60-second timeout. The receipt records
actual Python/package versions; there is no native integration-time benchmark.
This capture used Python 3.13.5, NumPy 2.5.3, SciPy 1.18.1 and Matplotlib 3.11.1.
No continuing-agent job, GPU job or new external source campaign was run.

| Artifact | SHA-256 |
| --- | --- |
| Frozen graph probe definition | `f9f5ebbdb6e0ac499224d7d7be63d0d620612642900d987540abc3b0c10b0ad5` |
| Identical expanded inputs for both native attempts | `b0eb57b517ca97de0702cb25ca0def705ea06a172da06bb811a363cdae63ed43` |
| Passing retained native fixture | `4ca9a9834f826aa8cbb72fe462d986bdfc1b4dcd46f2a49798bd9dfdbff83fef` |
| Acceptance receipt | `ec33714cdd560b8d95d6703c8021cc464bae1a36a71db831e21e6a55e19855e9` |
| 18-file independent acceptance capsule | `cfd056d91c7290f82f2d55ab06b4024c3ec2da37788fc4fc3ad95b989f94804b` |
| First native failure receipt | `7c30479298e9c4c65a65245e08661f9675c5802d9540da9601a8e290dd7494b7` |
| First attempt's 11-file source archive | `9588b786525b794d8fc2358df5516406945e54bf746312c426eb9af89da42217` |
| Full-suite JUnit receipt | `56cbde965492ae159f54c8769da6db264e3a8a06e2e4ca76e290eb41628e5ce3` |

The acceptance capsule preserves independent reference/build/checker/test files,
the two reference fixtures, definitions and dependency pins. It contains no
upstream implementation. Production source preservation is checked against the
accepted 0.10.0 release audit; no version/source migration is appropriate for this
reference-only work. Historical SPEC-004's nine payload hashes remain intact,
including its frozen protocol/numerical documents and earlier test receipt.

Next: **NUM-005b**, bounded independent preparation integration and qualification;
then long trajectories/candidate selection (NUM-005c). NUM-005, M1 and M1c remain
in progress, with production graph and assay claims behind their later gates.
