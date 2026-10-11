# REF-004d / D102 native input preflight: prelaunch handoff

2026-09-15. Implementation, focused software checks and read-only authentication
pass before one detached preflight. This is **not its numerical completion**.

## Scope and boundaries

The [contract](../docs/BETSE_CHANNEL_RELEASE_PREFLIGHT.md) and
[plan](../validation/betse/channel_release_preflight/plan.json) retain D101's
four conditions, two m/h histories, three native timesteps and three input query
times. Six geometry seeds produce **144 fresh phases, 288 single updates,
288 input applications and 72 observer pairs** on actual pinned BETSE objects.

Every fresh phase gets one active priming update. Apply the input prefix without
integration between queries, then execute one probe update. Only native
`maxDm = immutable_baseline * availability` is written by the input adapter.
Stored currents, gates, inventories and numeric layout must survive application.
Fresh copied-state flux, gate-first updates, single-owned cell/bath transfer,
current export and capacitor voltage are checked independently.

Each phase advances only `2 * dt`; query times 0, 0.5 and 1 ms are **not** elapsed
simulation times here. Static-block cases also receive the active priming update.
There is no full-loop input hook, 2 ms release response, Cells trajectory,
piecewise reference integration, restart, biological or GPU qualification.
Production code and all previously registered sources/evidence stay unchanged.

## Software evidence and retained development attempts

The final [71-test XML](ref-004d-release-preflight-checks-07.xml) passes in
**14.01 s** (XML suite time 14.004 s), without failures, errors or skips. SHA-256:
`ead6efe9d85734b88d3295e0bba6b2d2d9dcac47887b7c7954cbee8c55761a9c`.

Actual native smoke coverage is explicitly test-only: two cases (one block,
one release), each with observer-on/off partners, giving **four fresh phases /
eight single updates / two observer pairs**. Complete rows pass independent
gate/flux/conservation checks and boundary-artifact linkage. Corruption tests
reject state resets, wrong clocks, altered metadata/inputs, seed mismatches,
fresh-argument changes and incorrect native observer boundaries. Additional
checks cover model-free provenance, detached launch without polling, restoration
of a failing observer and preservation of partial failed-update boundaries.
This small software subset cannot satisfy the full-panel checker.

All earlier XML attempts remain and are hash-bound by registration:

| Attempt | Result | Diagnosis or extension |
| --- | --- | --- |
| [01](ref-004d-release-preflight-checks-01.xml) | 39 passes / 18 common setup errors | New YAML writer needed accepted block-style formatting before native loading. |
| [02](ref-004d-release-preflight-checks-02.xml) | 39 passes / 18 common setup errors | `p.dt` is installed by INIT phase construction; use configured `init_time_step` for the earlier candidate-clock check. |
| [03](ref-004d-release-preflight-checks-03.xml) | 39 passes / 18 common setup errors | Normalize the native float wrapper at the new adapter boundary after authenticating metadata; strict D101 input validation remains unchanged. |
| [04](ref-004d-release-preflight-checks-04.xml) | 39 passes / 18 common setup errors | The full non-interference guard caught different random initialization of unused `channel_noise_factor`; explicitly reseed each fresh case, without excluding the field. |
| [05](ref-004d-release-preflight-checks-05.xml) | 65 passes / 2 failures | Actual smoke cases completed and observer pairs matched; checker expected gate-entry identity before native unit-modulator materialization. Correct exact boundary accounting also includes the source's `1e-25` pre-transfer voltage addition. |
| [06](ref-004d-release-preflight-checks-06.xml) | 69 passes in 13.98 s | Complete numerical, non-interference and artifact-linkage checks pass. |
| [07](ref-004d-release-preflight-checks-07.xml) | 71 passes in 14.01 s | Adds exception-path evidence retention and observer restoration; final launch prerequisite. |

Corrections affect only new, not-yet-registered D102 tooling. No old physics,
criteria, tolerance or capture is rewritten. Repository lint, formatting
(670 Python files) and whitespace checks pass. No long regression was rerun.

Exact final software command, from the Cells root:

```bash
env -u XLA_FLAGS -u JAX_DISABLE_JIT PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  taskset -c 0-3 timeout 50s .venv/bin/python -B -m pytest -q --tb=no -W error \
  validation/betse/channel_release_preflight/test_release_preflight.py \
  --junitxml=reports/ref-004d-release-preflight-checks-07.xml
```

This records the executed command; never overwrite the retained XML on a rerun.

## Provenance, resources and next gate

Read-only authentication checks D100's ten-file packet / 152 source inputs,
D099's 291 capture files / 143 inputs, accepted 352 implementation files /
51 production modules and D101's five design inputs and 107-test receipt.
The D100 completion remains
`e152d806f72f2571b150eb6751c59e1a3fc34ac8accf4bfeaaf4502d30348135`;
the D101 design manifest is pinned to
`c4148a2988251270633f0bbf236e7737f22abd3c9133af82eaa88491633ffd93`.
Native source/package identity is checked again before execution.

The new capsule binds **165 source inputs** (152 prior + five D101 + eight
D102), eleven supporting reports/receipts, explicit preparation data and the
separate passing software receipt. Registered sources become immutable.

One detached job, CPUs 0–3, **480 seconds total / 360 seconds native worker /
256 MiB aggregate artifacts / 64 MiB per file**. These are ceilings, not a runtime
prediction or RAM allocation. The compressed reader retains its 128 MiB decoded
record cap. Logs and completion/failure receipts are durable; failures stop the
job and are not automatically retried.

Launch once:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  validation/betse/channel_release_preflight/release_job.py launch \
  runs/ref-004d-release-preflight-2026-09-15/capture-01 \
  --tests reports/ref-004d-release-preflight-checks-07.xml
```

`launch.json` records process creation, not completion. A successful completion
must still say `release_input_preflight_pass_pending_review`. Return without
polling or launching an audit/reference/trajectory automatically. On subsequent
user instruction, review the actual saved result, then separately gate the
piecewise reference, controlled dynamic response and independent closeout.
