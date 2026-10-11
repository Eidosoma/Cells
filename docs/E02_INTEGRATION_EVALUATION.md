# E02 integration-side evaluation prototype

D041 / NUM-005c2e. Short CPU float64 engineering only. The fixed-control
reference equations, RK4 update, stage/domain/accounting and whole-cubic
checks stay unchanged. No production, long-step, resource-cap or biological
acceptance change follows from this prototype.

## Boundary and identity

[PreparedModel](../tests/reference_graph_evaluation.py) is a read-only snapshot
of a validated graph, context, controls and parameter panel. Numerical arrays
are bytes-backed and immutable, nested parameter mappings are read-only, and
the serializable case accessor returns a detached value. Changed graph,
context, parameters or controls require a new instance. Dynamic state and
history remain explicit arguments; there is no last-state cache.

Two explicit policies share this interface: `scalar_frozen` calls the original
graph equations; `scalar_cached` hoists diffusion/length, diffusion/thickness,
pump eligibility, bath values and the Snail-only regulatory factors.
Multiplications retain their original order; contacts retain their original
edge accumulation order. All decomposed outputs and their finite checks remain,
including the derived packet. Complete derivative assembly includes primary,
leak, pump-cycle, ionic-contact, local-regulatory and miRNA-contact coordinates.

The evaluator has an explicit revision, policy and case/panel digest inside
the registered numerical source/runtime identity. Matching finite probes does
not authorize cross-evaluator restarts. Same-policy restarts may change window
width or lossless recording policy, using the D040 dependency-aware API.
All prior numerical sources and artifacts remain immutable.

The adapter delegates to the frozen D039 checked runner through D040 recording:
no stage, voltage/exponent, blocked-history, accounting or whole-curve guard is
removed or cached. Fresh RHS output must still be finite and complete.
The adapter additionally requires a finite float64 vector and a boolean
absolute/increment mode, and refuses per-call control overrides.

## Qualification and measurements

The [registered plan](../configs/reference/e02_evaluation_profiles_v1.json)
uses all 45 frozen graph fixtures, eight nonuniform primary perturbations and
both absolute/increment coordinate modes. Finite history perturbations test
instantaneous history independence, not the validity of those inputs as
accounting-consistent trajectory stages. All complete derivatives and all
12 decomposed fields must match byte for byte. This is a finite test set,
not a proof for every admissible state or another runtime.

Twelve profiles cover the same six D040 cases, each with frozen and cached
evaluation: duration 5.12, maximum step 0.01, 512 steps, windows of 256.
Both retain D039 `rk4_basis` trajectories, D040 `trajectory_backed`
comparisons and D038 `batched_cached` observations. Full logical evidence,
dependency checking and checkpoint publication remain unchanged.

[The profiler](../scripts/profile_graph_evaluation.py) records complete checked
time (including preparation, checks and publication), RHS-only call timing,
section timings, actual evidence bytes and process high-water RSS.
Separate 256-call cProfile microprofiles identify initial-state RHS costs;
they are instrumented diagnostics, excluded from checked trajectory timings
but included in whole-worker/session time and retained storage. No microprofile
timing is presented as a full-path speedup. One ordered pair per case is not
a statistical benchmark.

[The independent auditor](../scripts/audit_graph_evaluation.py) reuses the
frozen independent trajectory/sample reconstruction and scalar readout audits.
It additionally reconstructs every RK4 stage input from saved data and
recomputes every complete stage/endpoint slope with the original graph
evaluator, requiring exact bytes. Cached evaluation and writer interpolation
are not used for this slope check. This extra verification cost is reported.
RHS evaluation here checks slopes; it does not replace or reconstruct recorded
evidence. Curve extrema remain floating-point polynomial checks, not
interval-certified bounds on the true ODE solution.

## Resources and limits

One numerical job at a time: CPU affinity 0–3, float64, four numerical-library
thread counts of one. Original caps remain 900 seconds per worker,
3600 seconds per session/audit, one million steps, 256 MiB estimated arrays,
and 1 GiB across all retained research roots. D040 and all earlier roots use
831,126,114 bytes, leaving 242,615,710 before this slice.

The evaluator estimate is `8 * (512*N + 256*E + 128)` additional bytes.
It is checked before snapshot allocation, and added to the unchanged D040
aggregate recording/readout estimate before output creation. The scalar
baseline uses the same conservative allowance. This is an array estimate,
not a hard RSS bound. Numerical windows are bounded; filesystem inventories,
dependency/index validation and quota scans still grow with retained records.

Source registration precedes numerical profiles. Sources are archived and
hashed, outputs are exclusive, failed/partial evidence is retained, and a
failure stops the session without automatic retry or refinement. New sources
are frozen once registered. Reproducible receipts and the final report are
separate from mutable project progress documents.

This remains a short evaluation experiment. Remaining trajectory storage,
whole-curve and offline audit costs require separate engineering decisions.
No long-study launch, compact long-policy adoption, tolerance change, GPU
migration or production graph implementation is authorized by a short pass.
