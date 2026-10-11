# REF-004d / D103 saved-input review: prelaunch handoff

2026-09-15. Source investigation and focused software verification pass before
one detached saved-data review. This is **not its completion receipt**.

## Confirmed cause and bounded correction

D102 completed all native work but rejected an exact-identity assumption at a
zero-flux shared-bath average. The [failure report](REF004D_RELEASE_PREFLIGHT_FAILURE.md)
retains its 52.782 s failure, original status and four anchored receipt hashes.
No captured values, native code or production source has changed.

The [D103 contract](../docs/BETSE_CHANNEL_RELEASE_REVIEW.md) replaces the ordinary
and blocked-channel bath identity assumptions with **exact expected source-order
means**, separately at each native boundary. It does not fit or widen an epsilon.
All original unit-specific physical budgets, independent gate/flux/current/charge
checks, input-state preservation and observer comparisons remain. Material drift
from roundoff is explicitly recorded and checked, not subtracted from the data.

Reconstruct only the pinned positive length-30 float64 reduction. The NumPy
source at the installed revision and its BSD license are included under
`channel_release_review/numpy_source/`; hashes also bind the installed Python
mean implementation and compiled reduction library. No internet or numerical
library is needed during the actual saved-data review.

## Software evidence

All **66 focused tests pass in 10.66 s** (XML suite time 10.647 s), no failures,
errors or skips. The [passing XML](ref-004d-release-review-checks-02.xml) has SHA-256
`7b593a5ba0c6189e27633e99cd75ecb9d5beee3f28425280350b8777a250b5a4`.

Coverage includes:

- Exact agreement with the installed native NumPy binary on **198 vectors**;
  this subprocess evaluates means only, never initializes a BETSE phase.
- Eight actual saved rows spanning both histories, observed/unobserved partners,
  active/no-op/block/release inputs, ordinary rounding and successive blocked
  remixing. Their data remain unchanged under the checker.
- One additional ULP, suppressed averaging, nonuniform bath, altered cell or
  membrane state, duplicate transfer, nonzero inactive flux and input reset are
  rejected. Even an exact source mean must satisfy the original material budget.
- Original first-failure reproduction, full provenance authentication, model
  import exclusion, source-diff restriction, durable failure, duplicate-identity
  rejection and detached launch without waiting or polling.

The [first XML](ref-004d-release-review-checks-01.xml) remains: **63 passes /
two failures in 10.50 s**. The two synthetic corruption increments were smaller
than half an ULP at the large intracellular concentrations, so they did not
change represented data. Correct only the new fixtures to use `nextafter`, and
assert that every corruption actually changes its input. No checker or physical
budget was weakened. Its SHA-256 is
`a8408f5f1081b9e16820f17cf25ad0331849039bf58d3aea1876573185c70162`.

Repository lint, formatting and whitespace checks pass. No original simulator
test suite, phase, reference integrator or long regression was rerun.

Executed final software command (do not overwrite the retained XML):

```bash
env -u XLA_FLAGS -u JAX_DISABLE_JIT PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  taskset -c 0-3 timeout 50s .venv/bin/python -B -m pytest -q --tb=short -W error \
  validation/betse/channel_release_review/test_release_review.py \
  --junitxml=reports/ref-004d-release-review-checks-02.xml
```

## Frozen panel and execution

Read-only authentication confirms all **605 D102 files**, its **165 inputs**,
original 71-test receipt and prior evidence chain. Freeze the saved file hashes
in a new registration; D102 never wrote a successful final manifest. The new
source capsule has **175 inputs** and binds **15 supporting reports/receipts**,
the final review XML, runtime source identities and captured bytes separately.
Do not edit registered sources after launch.

The full review must cover **144 phases / 288 saved updates / 288 input
applications / 72 observer pairs**, including **1,776 zero-flux means**. Keep all
original guard rejections as separate evidence. Full numerical success belongs
to the review's actual receipt, not the sampled software tests or diagnosis.

Launch once from the Cells root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  validation/betse/channel_release_review/review_job.py launch \
  runs/ref-004d-release-review-2026-09-15/review-01 \
  --tests reports/ref-004d-release-review-checks-02.xml
```

One detached saved-data job, CPUs 0–3: **180 seconds total / 64 MiB aggregate /
32 MiB per file**. These are resource ceilings, not runtime predictions or RAM
reservations. There is no simulator worker. NumPy/BETSE/Cells/JAX/SciPy imports
are prohibited during review; native seed pickles are hashed, never loaded.

Return after launch without polling, retry or automatic follow-up. A successful
review records `release_input_preflight_review_closed` separately; the original
capture remains `release_input_preflight_failed_not_qualified`. This closes only
native input/single-update readiness, not a full-loop timed input, 2 ms release
trajectory, biological model, native restart or GPU execution. Piecewise
references and dynamic response are later, separately authorized gates.
