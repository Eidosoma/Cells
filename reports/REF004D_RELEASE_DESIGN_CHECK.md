# REF-004d / D101: suppression/release design checks

2026-09-15. **107 tests pass in 11.88 seconds**, with no failures, errors or skips.
This completes the [input design](../docs/BETSE_CHANNEL_RELEASE_DESIGN.md) and
instantaneous software checks. It does **not** register or run a native input
preflight, a release trajectory, another reference solution or a detached job.

## Engineering result

Existing Cells availability schedules support the proposed block/release without
changing intrinsic channel parameters, m/h, conserved inventories or accumulated
transfers. Keep the general production interfaces; implement any source-specific
input application in the optional adapter.

The native candidate is absolute `maxDm = baseline * availability`, read by the
pinned FULL network channel transport path after the gate update. It is not the
previous passive tissue-event pulse, native inhibitor chemistry or a drug model.
Static source-contract checks are not actual native dispatch evidence.

The candidate block runs from 0.5 to 1 ms in a 2 ms window. Baseline, explicit
no-op, static availability block and suppression/release are each paired across
histories a/b. Native elapsed boundary times, not its inclusive endpoint-labelled
clock, define future application. The whole new response remains unqualified.

## Checked coverage

- All eight configurations preserve physical parameters and initial state; only
  channel availability schedules change. The block does not set intrinsic Pmax
  to zero. Absolute native restoration cannot compound an earlier zero input.
- All **24 candidate Cells grids** pass actual parser/timeline/resource guards.
  Switch-adjacent floats, interval-left inputs, right-continuous switch readouts,
  event positions, unchanged other controls, inactive padding and observation-
  independent grids are checked. No integration step executes.
- **54 actual RHS/readout evaluations**: two saved active histories at 0, 0.5
  and 1 ms, availability 0/0.25/1, on NumPy, eager JAX and compiled JAX. Complete
  nonzero state/ledgers come from D100-audited D099 records, **not** a newly
  simulated release history. CPU float64/runtime identity is enforced.
- Independently reconstructed complete RHS and readouts use D094 80-digit
  mathematics, D097 ownership assembly and unchanged D097 instantaneous error
  budgets. Gates keep evolving at zero availability, all other rates in this
  no-other-flux fixture are exactly zero, and quarter availability scales flux.
  Full state, layout and inputs remain byte-identical during evaluation.
- Negative tests reject altered schedules/scope, bad values, missing or extra
  evidence, changed source composition/order, reset transfer history, frozen
  gates, nonzero blocked transport/outside rates and malformed padding.

The probes explicitly forbid rollout/integration entry points. They execute
neither reference integration nor native transport and provide no new checkpoint
or release-response qualification. Both interpretations matter: source/input
compatibility is established here; actual native input behavior is still open.

## Reproducibility and preservation

[Software XML](ref-004d-release-design-checks-01.xml), SHA-256:
`8f92924bb8327c30d90e9e12e6714529b5f054508e4e5bbc2ed6456c20cdfad5`.
The [source manifest](ref-004d-release-design-source-manifest.json) binds all five
new design inputs, this test receipt and the prior independent completion.
This is a software record, not a new numerical-capture source capsule.

Exact bounded command (use a fresh XML destination on subsequent work):

```bash
env -u XLA_FLAGS -u JAX_DISABLE_JIT PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  taskset -c 0-3 timeout 45s .venv/bin/python -B -m pytest -q -W error \
  validation/betse/channel_release_design/test_release_design.py \
  --junitxml=reports/ref-004d-release-design-checks-01.xml
```

Repository lint, formatting (**661 Python files**) and whitespace checks pass.
Read-only authentication confirms all ten D100 audit files / 152 source inputs,
291 D099 capture files / 143 captured source inputs, unchanged 352 accepted
implementation files / 51 production modules and retained earlier reports.
No original evidence, scientific tolerance or failed coarse result changed.
No full production regression was rerun for these validation-only additions.

## Next gate

Implement and register **actual native input-application/single-update preflight**:
prepared objects, targets, immutable baseline restoration, unchanged full state
at dispatch, gate-first update, fresh versus interval currents, one-owned
cell/bath transfer and elapsed clock mapping. Save actual values and failures.

After that evidence is reviewed, separately register piecewise reference/domain/
convergence/signal checks and the smallest controlled paired response. Do not
infer a release signal from constant-input histories or automatically enlarge
the horizon. Long jobs remain detached and user-polled; nothing further was
launched here. Biological validity, broader BETSE parity and GPUs remain later.
