# REF-004b / D093: full-loop preparation and feedback readiness handoff

2026-09-14. Implementation/software handoff, written **before native execution**.
The user requested both full-loop initialization/observer checking and preparation
of the small channel–voltage feedback pilot. Do not treat this document as an
actual native completion or a registered full dynamic comparison.

## Prerequisite now closed

D092's independent audit completed in **3.215071 s** with all 37,068 comparisons
independently rebuilt, zero failures, twelve definition contracts and two
hidden-state controls. Its completion SHA-256 is
`18070f9898bbbd6061867f050ac54d00dbb407b9bd978ced3ebfef136e8b40fb`.
The nine-file audit packet, 54-file original capture, all prior failures, source
capsules and accepted 352 implementation files / 51 production modules are
unchanged. Authenticate prior saved data without rerunning its numerical audit.

## What is implemented

See [native preparation](../docs/BETSE_CHANNEL_LOOP_PREPARATION.md) and
[feedback design](../docs/BETSE_CHANNEL_FEEDBACK_DESIGN.md).

- Eight fresh real-native INIT runs: four controls × observer-on/off. Eight
  25 µs updates each, 200 µs per run, 64 total / 32 observed updates.
- One explicit initial m/h fixture after successful native dynamics initialization,
  identical in both modes. Separate read-only observation, no replaced model
  method or copied native time loop. Failed setup does not apply the fixture.
- Gate-before-transfer/current-export/ordinary-update/voltage boundaries, raw
  versus elapsed clocks, strict blocking, shared-bath conservation and native
  current/charge accounting. Byte hashes independently reconstructed from the
  exported float64 arrays; native sampled histories compared with observer copies.
- Twelve candidate Cells definitions through existing parser, initial-state/RHS,
  timeline and resource checks. Complete ten-field initial state saved. Separate
  80-digit continuous coupled vector field, with no simulator/compiler imports.
  **No Cells trajectory or independently integrated continuous reference yet.**

The future candidate is 2 ms, distinct native 25/12.5/6.25 µs and Cells
50/25/12.5 µs grids. Readiness is not accuracy. Reference integration, dynamic
criteria and full capture/audit still need separate registration. No biology,
general BETSE parity, native restart replay, GPU or multiscale accuracy claim.

## Software evidence

All receipts are retained; none failed:

| Receipt | Result | SHA-256 |
| --- | --- | --- |
| `ref-004b-loop-preparation-checks-01.xml` | 83 passed, 17.63 s | `94dab656b277f5082eafbdc67accd54e592e3414faed52b016c3715adee131cd` |
| `ref-004b-loop-preparation-checks-02.xml` | 95 passed, 18.04 s | `ee6754aa49de1be1ce88bba0a369f08e9b9f64279bd380450423627eda3f2d82` |
| `ref-004b-loop-preparation-checks-03.xml` | **96 passed, 18.70 s** | `6e301363c8979883e3887838c402484b729431e93ce73f710e45c1d944a33710` |

The second suite adds exception-unwinding and independent float64-byte checks;
the third exercises the complete Cells readiness worker using fabricated native
input. Synthetic source-filename lifecycle tests use real Python profile dispatch,
not native BETSE numerical execution. Corruptions cover gate reset/double update,
duplicate transfer, bath ownership, current sign, hidden leak/GJ/auxiliary changes,
clock/sampling, missing partners and observer mutation. Production RHS comparisons
include asymmetric cell states and cross-cell coupling through one finite bath.
Actual native YAML bytes are read through the installed YAML library; actual
native Parameters/network/full-loop execution belongs to the registered capture.

Final focused command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
JAX_PLATFORMS=cpu JAX_ENABLE_X64=true \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
taskset -c 0-3 timeout 55s .venv/bin/python -B -m pytest -q \
  validation/betse/channel_loop_preparation/test_channel_loop.py \
  --junitxml=reports/ref-004b-loop-preparation-checks-03.xml
```

Repository Ruff check, format check and `git diff --check` pass. The format check
includes code/document contexts; its aggregate file count is not a Python-module
count. No full acceptance/regression matrix or prior numerical audit was rerun.

## Detached next execution and limits

Bind **94 source inputs** (83 prior + eleven new), source capsule, original
capture/closeout identity, native checkout/installed dependencies, accepted Cells
runtime and exact numerical environment, and the 96-test XML before launch:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
.venv/bin/python -B validation/betse/channel_loop_preparation/loop_job.py launch \
  runs/ref-004b-loop-preparation-2026-09-14/capture-01 \
  --tests reports/ref-004b-loop-preparation-checks-03.xml
```

Fresh single-use output. CPU 0–3 / float64; 240 s overall, 120 s native worker,
60 s Cells readiness worker; 128 MiB aggregate artifacts, 32 MiB per file. The
aggregate cap is checked between native rows and before completion; it is not
an OS-wide disk quota or measured RAM allocation. Native seed/INIT pickles,
partial exports, full comparisons, stdout/stderr and failure/completion receipts
are durable. Exact worker environment reproduces registered strings/absences.

No automatic polling, retry, saved-data audit or dynamic follow-up. Only actual
launch/completion/failure receipts establish execution state. Success is
`preparation_readiness_pass_pending_audit`, not coupled-trajectory qualification.
Return control after launching; the user requests status and any later step.
