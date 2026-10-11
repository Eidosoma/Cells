# SPEC-004: frozen longer switching protocol

2026-09-08. **Design-only acceptance.** [E02-SW1](../docs/E02_SWITCHING_PROTOCOL.md)
and its [independent qualification plan](../docs/E02_SWITCHING_NUMERICS.md)
are specified; no preparation trajectory, prepared packet, long switching result
or new production model is produced. Cells remains **0.10.0**.

## What is now fixed

- Two fresh isolated full-model preparations, 500 nominal units, explicit
  phenotype-margin/domain/numerical criteria and separately reported ionic drift.
- Fourteen deterministic 1000-unit conditions: both switching directions,
  a primary two-neighbour star and six controls per direction. These contain
  36 cell instances and 22 contacts across **independent conditions**, not a
  single communicating 36-cell tissue or biological replicates.
- Full primary/context transfer with preparation provenance; no fabricated
  500-unit packets, three-marker-only resets or substituted old 10000-unit inputs.
- 1007 observations per condition, including 102 in the terminal window;
  phenotype labels, full-state/readout/ledger reporting and explicit unresolved,
  finite-horizon negative, invalid and resource-limited statuses.
- A prospective graph-composition and numerical gate before production. The
  current pair cannot run the primary star; padding or independent batches do
  not add another communicating neighbour.

The selected assay is not an exact historical threshold reproduction: native
preparation disables only miRNA, uses last plotting samples and carries ionic
context between directions. The completed source evidence motivates the design,
not a guarantee of positive outcomes. R006 records the read-only review.

## Checks performed

The standalone [checker](../scripts/check_e02_protocol.py) reads and hashes the
frozen input, verifies the inherited equation panel and native fixture, and
expands a deterministic case inventory. It imports only the Python standard
library, never the simulator, source harness or a numerical solver. The reference
JSON is deliberately not accepted as a production Cells configuration.

All **29 new tests pass**. They check shape/identity/route distinctions, fixed
topology under blocking, one-cell and pair controls, complete-preparation late
binding, no implicit stationarity/removal claims, fresh arrays, exact observation
inventory, freeze mutation refusal and the absence of numerical imports.
The full suite passes **1086 tests in 569.54 seconds**, with warnings promoted
to errors and no failures, errors or skips. The [JUnit receipt](spec-004-tests.xml)
and [design audit](spec-004-audit.json) preserve the result and nine payload
hashes. Ruff lint/format pass across 108 Python files; `pip check` passes and
the CLI reports `Cells 0.10.0`. The documentation check finds no broken local
file links, malformed table columns, missing heading separation or open fences.

The optional workspace audit passes against the accepted 0.10.0 release receipt:
all **39 production Python source hashes are identical**, including numerical,
observer, model and process code. All eight native fixture source hashes match
the separate local checkout, whose HEAD is the pinned revision. Four reviewed
exploration document hashes match the freeze. No upstream or continuing-agent
experiment was launched, stopped, polled or modified. Dependencies, package
version and existing frozen numerical panels were not changed.

## Frozen identities

| Item | SHA-256 |
| --- | --- |
| [E02-SW1 JSON](../configs/reference/e02_switching_protocol_v1.json) | `7e828792a61695e57f78da5ebdb02318ab927b82470f39b63aca9772bf0bece8` |
| Inherited SPEC-003 equation panel | `b67efad941db1b4c407aeddcac3836acf4a31653f3a1baa513ece6f5ce2e915d` |
| Existing native full-RHS fixture | `c71d0ede05060c84e466a7cc9e3a5f4ea7aa4eb2d3c1b77518c415f91a2b5f6b` |
| Accepted 0.10.0 release audit | `94d8ee4500f91fb6fb5506085c515944ad235e7d42318430d11d85e41b74da4e` |
| Reviewed native `zombie.py` | `8a4947327d6a58dba7c2b815610e3daa2615ee68de25d1347bacaee23f981152` |
| Full-suite JUnit receipt | `5b9ee4c4f0e48e0043ba26ea0a9809919e552aa24b68720ac6715b21f00b56ee` |

BITSEY revision: `b2cb370aaecbc8299f259bc4251d5396c81f19a6`. The JSON also
pins all four reviewed pilot/memory documents; the native fixture pins all eight
source files. Hashes identify evidence, not independent validation of the
source-reported outcomes. No upstream implementation is vendored.

## Reproduce the design checks

```bash
taskset -c 0-3 .venv/bin/python scripts/check_e02_protocol.py
taskset -c 0-3 .venv/bin/python scripts/check_e02_protocol.py --audit-workspace
taskset -c 0-3 .venv/bin/python -m pytest tests/unit/test_e02_protocol.py -q -W error
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
```

The first command is a read-only frozen design check. The second deliberately
requires the current workspace to match the reviewed 0.10.0/native/document
baseline; it should refuse after an intentional later source or document change,
not silently update an old acceptance. Neither command runs preparation or
switching. Existing historical acceptance artifacts are retained unchanged.

Next: **NUM-005**, independent fixed-graph composition and preparation/long-time
qualification, with all unsuccessful outcomes and resource limits retained.
MODEL-006/VERIFY-011 and ASSAY-002 follow passing numerical evidence. M1/M1c remain
in progress; memory/relay, cancer-expression, physical calibration, organs and GPU
are still separate future gates.
