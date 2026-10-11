# E02 bounded diagnostic optimization

D038 / NUM-005c2b, 2026-09-09. The user approved the recommendation following
[D037's checked short profiles](../reports/NUM005C2A_CANDIDATE_ENGINEERING.md).
Implement cached, bounded batched readouts and qualify/profile them against the
frozen scalar evaluator. Keep integration, source equations, scientific error
limits, full short evidence and production unchanged. No long candidate study.

## Numerical boundary

Batch only the observation-sample axis. Each evaluator snapshots one validated
fixed graph/control setting, with immutable numeric arrays and cached geometry,
diffusion factors and gate settings. Check the estimated array budget before
copying a model into the cache. Accept only explicit binary64 arrays with one
to 256 samples and the exact semantic axes. Reject invalid inputs before
evaluating the batch; retain the original primary/electrical domains and all
finite-result checks. No clipping or silent scalar fallback.

Compute the same membrane, regulation, upwind contact, gate and derived-packet
expressions. Preserve graph edge accumulation order, including orientation,
hemichannel swaps, independent ion/miRNA controls and zero-diffusion pump rules.
Use the existing independent regulatory polynomial function on a leading sample
axis. Cache only input-independent data. A changed graph/control setting requires
a new evaluator; caches are not mutable live model views.

Do not substitute this evaluator into the RK4 RHS. The D037 integrator, stage
checks, complete state, global clocks, cubic checks, checkpoint contracts and
sampling remain frozen. The new comparison adapter selects its readout policy
per instance, without modifying frozen modules or global functions. Both
policies use the same bounded grid, samples, score formulas, recording and
readout-fingerprint work.

Integration states, slopes, cubics and sampled states must match the accepted
D037 width-256 arrays exactly. Batched floating-point readouts are compared
against the scalar evaluator using the existing NUM-005a instantaneous budgets:

| Readout | Absolute tolerance | Relative tolerance |
| --- | --- | --- |
| Voltage | 2e-13 | 2e-12 |
| Gate scales | 2e-12 | 2e-12 |
| Membrane/junction flux | 5e-21 | 2e-12 |
| Derived binding cache / packet | 5e-12 | 2e-12 |
| Complete primary RHS readout | 5e-12 | 2e-12 |

All source flux fields share the same instantaneous tolerance. The normalized
readout difference must be at most 1. This does not replace or relax any of
E02's eight candidate/reference targets or its 2e-9 accounting bound. Report
actual bitwise identity separately; passing a tolerance is not a claim of
bitwise identity for arbitrary inputs, batch shapes or runtimes.

## Tests, registration and short profiles

Cover the existing 45 instantaneous graph fixtures, including gradients,
gated/reversed/permuted edges, stars, chains, disconnected components and
independent controls. Add varied batch widths/strides, charge-balanced state
perturbations, state/context/ID mapping, immutable-cache behaviour, preallocation
limits, invalid-value/batch rejection, fingerprint tampering and comparison
failure/cleanup tests. No unit fixture is a 500/1000-unit candidate trial.

Freeze and archive all implementation, test and policy sources before running
the [twelve profiles](../configs/reference/e02_diagnostic_profiles_v1.json).
Reuse D037's six exact cases and reference selections, 0–5.12 nominal units,
step 0.01 and width 256. For each case run the current scalar policy once, then
the cached batched policy once, in separate processes. Do not use old timings
as the only baseline or rerun to obtain a more favourable speed measurement.
One observation per combination is not a statistical benchmark.

Retain the same full states, five slopes, four cubic coefficients, all comparison
samples and observer flags, plus a hash of every batch's complete readout arrays.
Time the complete checked call, including cache creation, comparison, all
recording/receipts and reader cleanup. Also record readout/cache/fingerprint
section times, process-start/input-check time, array estimates and process RSS.
Changing how much evidence is retained is not part of this speed comparison.

Use one CPU float64 worker, affinity 0–3 and four single-thread library variables.
Keep the original 900-second worker, 3600-second session, one-million-step,
256 MiB estimated-array and aggregate 1 GiB limits. All prior preparation,
reference, failed and D037 artifacts count: 783,644,175 bytes leave 290,097,649
for one new root under `runs/num-005c2b-2026-09-09/`. A failure stops without
retry, new tolerance, fallback or automatic resource extension.

## Independent audit and interpretation

Recheck the pinned D037 audit/closeout, every old payload and all source/runtime
identities before reuse. Independently audit new stage/update/cubic algebra,
whole-curve domains/accounting and every comparison grid/sample, using D037's
read-only audit components. Match the ordered numerical fingerprints to D037.

Additionally recompute every recorded input's readouts using the frozen scalar
evaluator. Recompute the selected policy's readouts, match their recorded hashes,
compare the two policies with the registered instantaneous budgets, and recompute
all eight candidate/reference scores. This expands D037's derived-score audit;
it is read-only evaluation of saved states, not a new reference integration.
Neither the optimized nor scalar readout audit is a biological validation.

Report end-to-end speed separately from readout speed and unchanged output size.
Any long-study cost extrapolation remains a planning estimate: reference
transients, sample ratios, directory scanning, compression and late-time numerical
behaviour can change. No result automatically selects a timestep, raises a cap,
authorizes the long study or promotes a production/GPU implementation.

The [compact-evidence design](E02_COMPACT_EVIDENCE_DESIGN.md) is a separate,
unimplemented proposal. Full evidence remains in force for these profiles.

## Reproducible commands

Use the pinned `.venv`; set `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`,
`MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` to `1`, with CPU affinity 0–3.
Both commands use exclusive outputs. The profile command registers sources
and creates one new session; it cannot reopen a closed attempt.

```bash
taskset -c 0-3 .venv/bin/python scripts/profile_graph_diagnostics.py --run --output runs/num-005c2b-2026-09-09/diagnostics-01
taskset -c 0-3 .venv/bin/python scripts/audit_graph_diagnostics.py runs/num-005c2b-2026-09-09/diagnostics-01 --output reports/num-005c2b-audit.json
```
