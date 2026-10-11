# REF-004b / D096 independent coupled-pilot audit handoff

2026-09-15. Audit implementation and software checks are complete. This handoff
predates the single detached audit; it is not a claim of numerical closeout.
See the [audit contract](../docs/BETSE_CHANNEL_FEEDBACK_CLOSEOUT.md).

## User-reviewed pilot evidence

D095 completed in **338.424 seconds**, without warnings. Independent reference
convergence, all required finest-grid comparisons, eight refinement groups,
twelve observer pairs, four complete restart pairs and four eager/JIT pairs pass.
All **5,181,760 native boundary/probe identities** pass, with **2,264 absolute
charge snapshots**. Both simulators evolved their own complete states.

Fourteen coarse native diagnostic failures remain: seven active-channel voltage
rows and seven blocked-channel gate rows at 25 microseconds. They are not erased,
relabeled as required passes or used to change a tolerance. Refinement reduces
errors and the registered finest grids meet every required criterion.

| Pilot anchor | SHA-256 |
| --- | --- |
| Completion | `28e985c8f1d49d7953b21382ad6a34b6f2989f23c5407a97118902f8391c8ceb` |
| Registration | `1a479c2589d65a52146c3167f82952a8c83bd4ca359a6e42c931aac6183a065a` |
| Capture comparison | `f5fb3f35abf1e7ff9cb2051e3584d3c9261d6d2f415549e75bb7dcd0ecaaeca5` |
| Reference gate | `22b40cb33492ea1adea6d0f77712bdaec4b4dab0c34c2e49425a3b88d8c1fefd` |
| Trajectory comparison | `94968a184397b647af5a99160478c3ba53136359f171aed621a1395f55e28ffa` |

Preserve all **284 capture files** (280 manifest payloads, three operational
files and completion), **112 capture source inputs**, previous evidence and
accepted **352 implementation files / 51 production modules**. Preserve the
original `capture_pass_pending_audit` receipt. Authentication also binds all
five pilot software XML attempts and four historical handoffs.

## What the audit implements

- Frozen reference/native/Cells comparison replay with guarded output sinks.
  Write opens into the capture are forbidden; replayed summaries must equal
  saved summaries and all fourteen diagnostic rows must replay unchanged.
- Separate independent reconstruction of both columns and the unit of every
  numerical identity. Reuse D094's independently audited math primitives, not
  D095's oracle or either production model. Compare status as well as values.
- One-step native identity maps, full float64 bytes, observer pairs, lifecycle/
  elapsed clocks, partial records, current/transfer ownership and direct charge.
  Fresh native probes remain separate from the gate-first interval current.
- Independent dense polynomial basis evaluation, reference coordinate/domain
  checks, analytic controls, log-ratio thermodynamics and solver-agreement floors.
  No ODE integrator, numerical Jacobian or simulator is rerun.
- Complete Cells state/readout and definition reconstruction, inactive padding,
  all 24 checkpoints, four restart and four backend pairs. A standard-library
  numeric-only NPZ/NPY reader checks all 54 state/layout arrays in each checkpoint,
  including identity, owner, clock, source and runtime bindings. No NumPy or
  pickle loading is used; native restart files are authenticated by hash only.
- Independent common-time/interval-transfer pairing and all refinement decisions,
  including the existing reference/roundoff floors. No measured convergence order
  is claimed for floor-limited Cells differences.

Retain per-group counts, maxima and deterministic hashes of the complete
identity streams, plus every mismatch. Passing identities remain reproducible
from the full immutable raw data and frozen audit source. Millions of passing
JSON rows are not simultaneously materialized in memory.

## Software verification

All **122 audit-only tests pass in 11.18 seconds**, with no failures/errors/skips.
The suite uses bounded saved-data slices and synthetic corruption cases, not a
complete numerical closeout. It checks all four controls, each reference method,
reference-identity routing, direct dense algebra, eight-step native reconstruction,
fresh-probe mapping, complete checkpoint kinds, malformed numeric archives,
state/owner corruption, refinement decisions, streaming coverage, write guards,
source authentication and fresh-process import rejection.

The original **157 pilot tests remain hash-bound**, not rerun: audit tests do not
launch even a synthetic Cells/BETSE trajectory or reference integration. This
keeps the saved-data closeout separate from simulator execution. Repository
lint, formatting (622 files) and whitespace checks pass.

| Audit software receipt | Result | SHA-256 |
| --- | --- | --- |
| `ref-004b-feedback-audit-checks-01.xml` | 104 pass / 10.92 s | `1e93c4e5247b1ebf652d873c36199bfbc30df3cce68053f8050beaf1718cd509` |
| `ref-004b-feedback-audit-checks-02.xml` | 122 pass / 11.19 s | `5a418a915e96d6415f8cbbf6df663e9cd3da419c605c969589ecee1e095e19a1` |
| `ref-004b-feedback-audit-checks-03.xml` | 122 pass / 11.18 s | `bc763ceb2954a460dcef04a9c326a182f023325292def805e34932e3cfcf60a7` |

## Single-use detached audit

Register **122 source inputs**: 112 frozen pilot inputs, nine new audit/plan/test
files and one contract. Bind the passing audit XML, original software/handoffs,
all pilot hashes, prior evidence and installed runtime/source identities before
launching once at `runs/ref-004b-feedback-audit-2026-09-15/audit-01`.

```sh
.venv/bin/python -B validation/betse/channel_feedback_audit/feedback_audit_job.py launch \
  runs/ref-004b-feedback-audit-2026-09-15/audit-01 \
  --tests reports/ref-004b-feedback-audit-checks-03.xml
```

CPUs 0–3, **900 seconds overall**, **256 MiB aggregate artifacts**, **128 MiB per
file and decoded record**. These are artifact limits, not RAM ceilings. Complete
numeric checkpoints have an additional one-million-element per-array guard.
The process forbids Cells, BETSE, NumPy, JAX/JAXlib and SciPy imports.

Durable stdout/stderr, replay diagnostics and completion/failure receipts remain
in the new audit directory. Detach and return without polling, interruption,
retry or automatic follow-up. The user requests status; mutable
[progress](../PROGRESS.md) records the launch receipt.

Only an actual `coupled_feedback_pilot_audit_closed` receipt qualifies this fixed
2 ms four-control numerical pilot at registered observations and budgets. No
biological validation, general BETSE parity, long-time/stiff-regime accuracy,
native restart, GPU, organ, multiorgan or cross-resolution qualification follows.
