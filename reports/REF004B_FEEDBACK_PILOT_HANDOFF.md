# REF-004b / D095 reference-gated feedback pilot handoff

2026-09-15. Implementation and focused software checks are complete. This
handoff predates the single detached scientific capture; launch and result
receipts establish its actual execution state. See the
[registered design](../docs/BETSE_CHANNEL_FEEDBACK_PILOT.md).

## Both requested stages, one gated capture

The user requested independent continuous-reference convergence and the small
evolving Cells/BETSE comparison. D094 preparation/readiness is independently
closed: 74,092 comparisons, zero failures, 5.541 seconds. Completion SHA-256:
`8ec513d8171ebf3a6670ae270f66fed1821ff4caf66670076c3e4bc03ef5c391`.

Authenticate its nine-file audit, D093's 74-file preparation, all earlier
evidence and 101 existing source inputs. Accepted 352 implementation files /
51 production modules remain unchanged. No release, package installation or
GPU work is included.

1. Integrate the independently checked continuous vector field with base/tight
   DOP853 and a distinct Radau check: three solves per control, twelve total.
   Preserve accepted states and dense polynomials; replay saved polynomials,
   analytic controls, thermodynamics and convergence before launching either
   simulator. The RHS uses 80-digit arithmetic; integration remains float64.
   These are distinct algorithms within SciPy, not independent libraries.
2. Only on a passing reference gate, run the registered 2 ms four-control panel:
   twelve native observer-on/off pairs (24 runs / 4,480 updates), twelve compiled
   and four eager production JAX trajectories, and four complete checkpoint
   reload/resume segments. Each engine evolves its own state. Check strict
   accounting/readouts, finest-grid errors, both refinement halvings,
   cross-engine agreement, backend agreement and complete restart histories.

The panel keeps seven cells / thirty faces, one finite shared bath, Kv1p5,
fixed geometry and constant controls. No ordinary leak, pumps, GJs, extra
chemistry, mechanics, flow or noise. It is an engineering regime, not a
physiological resting state. All definitions, grids and criteria are fixed
before scientific capture; no post-result adjustment or automatic retry.

Native traces and byte records are retained as lossless bounded gzip JSON.
Fresh native current is a post-hoc constitutive probe on copies of completed
states, never the previous interval's current or an extra integration step.
Check its permeability/GHK law independently. Check absolute native charge,
final channel-array links and each Cells readout against its own accepted
state. Preserve every numerical rejection; reconstruct passing identities
from the complete records and frozen checker. Native restart is not claimed.

## Software evidence and retained attempts

Final focused run: **157 tests pass in 50.23 s**, no failures/errors/skips:
96 original preparation tests and 61 new checks. These cover synthetic
coupled references, saved-data gate success/corruption, failure-gated worker
launch, dense output, analytic controls, domain/resource guards, compression,
refinement, full production state, eager/JIT agreement and complete restart.
The production fixture explicitly declares a different -35 mV / 100 microsecond
initial state and matching bath countercharge; it is not the scientific pilot.
The native probe test calls only the constitutive function on copied data.

Repository lint, formatting (612 files) and whitespace checks pass. Runtime
preflight verifies reference Python 3.13.5, NumPy 2.5.3, SciPy 1.18.1 and installed
IVP source hashes. Earlier receipts remain intact:

- Attempt 01: 138 passes, one failure, seven setup errors, 29.88 s. The synthetic
  voltage fixture omitted matching bath countercharge; the production guard
  correctly refused it. The probe test also mistook normal BETSE initialization
  banners for failure. Corrected the fixture and output assertion, not production.
- Attempt 02: 147 passes, 47.03 s, before the final boundary/gate checks were added.
- Attempt 03: 154 passes, three failures, 50.65 s. New corruption tests reached
  the byte-integrity guard before their intended constitutive check. Tests now
  check both malformed bytes and well-formed but numerically false exports.
- Attempt 04: 156 passes, one failure, 50.34 s. A new probe-corruption fixture
  violated face-owner uniformity before its intended numerical check. Preserve
  uniformity in that synthetic corruption to isolate the constitutive rejection.
- Attempt 05: final 157-test pass. No equations, production guards, pilot inputs
  or scientific error budgets were changed to address these fixture failures.

| Software XML | SHA-256 |
| --- | --- |
| `ref-004b-feedback-pilot-checks-01.xml` | `7244fd666b05518df44e4b306f9cec4cec82b1447d283ed07e1ed977fd827239` |
| `ref-004b-feedback-pilot-checks-02.xml` | `944dda2e5e9f50955827fd08e76464cf1ae19faf38acf6ed818d740a5d14080b` |
| `ref-004b-feedback-pilot-checks-03.xml` | `2eda8b4682ee18dd92d16b9992d2ed0c191c1da67322f003d7e33efc01b25bf0` |
| `ref-004b-feedback-pilot-checks-04.xml` | `f8b8672a6042b0f9e672fa7c10d12d448b60637f052ec729a42f1fda3c12646b` |
| `ref-004b-feedback-pilot-checks-05.xml` | `6006370438c009495b7ccde5f460f64926cb341899cf1996481eed2237d65143` |

## Single-use launch and hand-back

Bind **112 source inputs** (101 previous + ten new adapter/protocol/test files +
one contract), passing XML, prior packets, definitions and runtime identities.
Freeze them before this fresh destination is used:
`runs/ref-004b-feedback-pilot-2026-09-15/capture-01`.

```sh
.venv/bin/python -B validation/betse/channel_feedback_pilot/feedback_job.py launch \
  runs/ref-004b-feedback-pilot-2026-09-15/capture-01 \
  --tests reports/ref-004b-feedback-pilot-checks-05.xml
```

One detached process, CPUs 0–3, 900-second overall cap; reference/native/Cells
worker caps 180 / 240 / 360 seconds. Artifact limits: 512 MiB aggregate,
128 MiB per file and per decompressed record. These are not RAM ceilings.
Durable stage logs, complete scientific records and completion/failure receipts
stay in the run directory. Partial native observation survives native failures.

Return control without polling or interrupting computation. The user requests
status. No retry, independent audit or follow-up regression is automatically
launched. The mutable [progress page](../PROGRESS.md) records the launch receipt;
this handoff does not assert completion.

A successful capture remains `capture_pass_pending_audit`; a later independent
saved-data closeout is required for coupled qualification. No biological
validation, general BETSE parity, long-time/stiff-regime accuracy, GPU, organ,
multiorgan or cross-resolution qualification follows from this pilot.
