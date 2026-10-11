# NUM-005c1 A2: amended reference panel

2026-09-09 / D036. Status: **all 14 amended-policy reference conditions,
independent auditing and all 1362 tests pass**. Production remains 0.10.0.

## Approved policy and preserved evidence

The user approved [A2](../docs/E02_REFERENCE_POLICY_A2.md): adopt the audited
tighter-BDF path with the two original Radau references for reverse miRNA-only,
record its reference-only observers, and run the three remaining controls.
The [machine-readable amendment](../configs/reference/e02_reference_policy_a2.json)
has SHA-256 `4562f67307b8d081bd26e7dd151e5a40ca8a8d966e70cc186de38f9d0e069598`.

Ten original qualified cases keep their original trios/settings. A2's adopted
case uses the pinned A1 four-input comparison and its three passing required
pairs. The original BDF trajectory, failed comparison and diagnostic-only A1
receipt remain unchanged. A2 is an explicit informed acceptance decision, not a
claim that the original failed trial passed.

Register same-state, one-neighbour and isolated controls in that order, each
with base Radau, refined Radau and tighter BDF. Both tighter solvers use 0.1
times base rtol/atol (nominal 1e-11/1e-12). All three pairs must satisfy all eight
unchanged targets; normalized reference disagreement remains at most 0.1 and
accounting residual at most 2e-9. No additional tolerance, retry, phenotype-based
selection, equation change or production change is allowed.

This is an explicitly mixed-setting, accuracy-qualified panel: ten original
trios and four using tighter BDF. It is not a uniform solver-settings comparison,
a rigorous global-error bound or biological confirmation. Reference labels are
not a claim of full-state equilibrium.

## Engineering and registration

A per-case manifest separates selected trajectory paths, method settings,
comparison evidence and observer output. Imported data stays in immutable roots;
no chunk copying, links or global solver overrides. The new bounded three-input
adapter reuses frozen readers, solver, recorder and score definitions. Its
observer arithmetic is extracted unchanged and tested array-for-array against
the original observer. Reader generators close on normal and exceptional exits.

Before scientific execution, **116 targeted tests passed in 41.29 seconds**,
including 25 new A2 checks. They cover exact inputs and settings, ordering,
registration/source tampering, aggregate quotas, linked/unknown artifacts,
worker/observer/comparison stopping without retries, complete short-panel
orchestration and audit, exact observer equivalence, and rehashed grid/state
corruption. A numerically passing nonswitch is accepted. No fixture runs a
1000-unit scientific path. Lint and formatting passed before the source freeze.

The [registration](../runs/num-005c1-a2-2026-09-09/panel-01/registration.json)
has SHA-256 `05aaf162aead58530218956be16fd68574004ecfa7fc2581201c47d28445cdd1`.
The immutable 41-file
[source capsule](../runs/num-005c1-a2-2026-09-09/panel-01/reference_sources.zip)
has SHA-256 `b06e7e51074e203d2ff6b27a23ebd2341a7d76ee92912b53350c2ff6ecda7329`.

One CPU float64 worker at a time, affinity 0–3 and single-thread libraries. The
900-second/path, 3600-second scientific-session, step/RHS and 256 MiB working-array
limits are unchanged. Session time includes adopted observers, comparisons and
closeout. The three prior long-reference roots occupy 582,424,320 bytes, leaving
491,317,504 bytes of the same aggregate 1 GiB cap for the new root. All old failed
and partial attempts count toward this quota.

## Results and audit

The [scientific receipt](../runs/num-005c1-a2-2026-09-09/panel-01/verification.json)
passes: ten imported original cases, the explicitly adopted miRNA-only case and
all three remaining controls have accepted comparisons and reference observers.
Verification SHA-256:
`33b12877213cdd92d203b3fe8d314dd9f1e827345db3a870b77b349389fe71f8`.

| A2 case, M to E | Maximum accepted score | Comparison times | Provenance |
| --- | ---: | ---: | --- |
| miRNA-only | 0.005334691340757373 | 103,243 | Pinned A1 required pairs; four-input grid preserved |
| same-state | 0.0025685891117779845 | 63,082 | Three new paths; every pair required |
| one-neighbour | 0.004834463318602576 | 62,846 | Three new paths; every pair required |
| isolated | 0.0051039177885341975 | 62,906 | Three new paths; every pair required |

All accepted scores stay below 0.1. Across the full 14-case composite panel the
largest accepted score is 0.03386899459217551, in the previously qualified reverse
active condition. The original failed BDF score remains about 0.226 on the A1
four-input grid and is not treated as passing.

Nine new paths reach exactly 1000 units: 92,920 accepted steps, 367 trajectory
chunks and 633,283 solver/Jacobian RHS calls. The longest worker takes
146.09629005397437 seconds; the scientific session takes 1087.2642128000152
seconds, including observers, comparisons and final integrity checks. No path
or session cap is extended. The maximum trajectory working-array estimate is
3,374,976 bytes. These are implementation/resource measurements, not a GPU or
large-tissue performance claim.

New comparisons retain 188,834 times in 739 chunks, and four new observer sets
retain 4028 times in 16 chunks. A2 does not duplicate the adopted A1 comparison.
Each of all 14 cases has 1007 observer times, including 102 in the terminal
window, complete selected reference states and all registered diagnostics.

| Control | E to M recipient | M to E recipient |
| --- | --- | --- |
| active, two target neighbours | M; first sampled target 155 | E; first sampled target 124 |
| blocked | E; no sampled target | M; no sampled target |
| ionic-only | E; no sampled target | M; no sampled target |
| miRNA-only | M; first sampled target 155 | E; first sampled target 124 |
| same-state neighbours | E; no sampled target | M; no sampled target |
| one target neighbour | E; no sampled target | M; no sampled target |
| isolated | E; no sampled target | M; no sampled target |

These are nominal source-time units, not calibrated physical times. The first-hit
brackets are [154,155] and [123,124]; the adopted reverse miRNA-only recipient
passes through sampled X before E. All terminal samples agree with the displayed
endpoint label. There are no unresolved sampled labels or donor label changes.
Nonswitching controls pass numerically: the result was not an acceptance criterion.

This source-model pattern does not establish a biological or voltage-driven
switching mechanism. Prepared E/M ions are equal, and stable regulatory labels
coexist with ionic drift and nonzero passive histories. Complete-state drift/RHS
and native-style goal diagnostics remain in the observer summaries; no full-state
equilibrium, memory-after-removal or native long-driver confirmation is claimed.

The new root retains 1177 files, 133,541,869 bytes including the scientific receipt.
All four long-reference roots total 715,966,189 bytes, below the unchanged
1,073,741,824-byte cap. Original partial and failed attempts remain included.

The [independent audit](num-005c1-a2-audit.json) passes in
395.8095814579865 seconds. It rechecks all 1176 new payloads, the 41-file source
capsule and every pinned prior dependency. All nine new dense trajectories pass
the independent domain/accounting reconstruction; their maximum residual is
3.4106550821695685e-12, below 2e-9. Each of the three new comparison grids is
rebuilt independently, every saved state matches its selected source exactly,
and all primary/history scores are independently reproduced. For all four new
observer sets, source states, labels/allowances, binding caches, coverage,
first-hit/return summaries and drift summaries check out.

Audit SHA-256:
`1502aa19c262306ff44c2443c8a76488312758a0e4d4d978fd60caee41186543`.
The audit reuses the pinned earlier complete-curve/readout audits; it does not
re-integrate old paths. Derived flux/gate/voltage comparison scores and RHS
values remain online-recorded, not independent RHS recomputations. No rigorous
interval proof or global-error certificate is implied by the floating-point
polynomial checks and solver agreement.

The [full regression suite](num-005c1-a2-tests.xml) passes: **1362 tests**,
including 25 new A2 checks, zero failures/errors/skips, with warnings treated as
errors. Runtime is 596.75 seconds (JUnit: 596.687 seconds). Lint, formatting,
dependency, whitespace and documentation-link/table checks also pass. All 39
production source hashes and all earlier closeout/source dependencies remain
unchanged. No original evidence was modified to obtain this result.

```bash
env JAX_PLATFORMS=cpu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python -m pytest -q -W error --junitxml=reports/num-005c1-a2-tests.xml
```

The [scoped closeout](num-005c1-a2-closeout.json) records completion of NUM-005c1
under the explicitly approved A2 policy. The ten original-case qualifications,
original failed campaign and diagnostic-only A1 receipt retain their historical
statuses; the composite panel has fourteen accepted cases. The panel selects
42 complete long-reference paths from 43 retained complete paths, with one
original partial attempt also retained. The six preparation paths are separate.

## Remaining gates

The complete independently audited 14-case A2 panel closes NUM-005c1. It does
not close NUM-005c2, select the long-time production timestep, implement a JAX
source graph or establish full source-assay/biological parity. The next gate is
the [bounded candidate preflight](../docs/E02_CANDIDATE_PREFLIGHT.md), followed by
the registered RK4 study, selected/half-step qualification and candidate-owned
preparation continuations. No candidate, GPU, fluid or continuing-agent
experiment is launched in this slice.
