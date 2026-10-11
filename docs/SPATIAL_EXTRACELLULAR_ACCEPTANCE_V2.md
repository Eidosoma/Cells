# CORE-010 recorded acceptance: resource amendment v2

Prospective plan, 2026-09-11. This supersedes only the wall-budget setting of
the [unchanged v1 protocol](SPATIAL_EXTRACELLULAR_ACCEPTANCE.md) for a **new**
capture. It does not accept, extend, overwrite or resume the stopped v1 session.
All fourteen cases must run again to completion in the new registered session.
Production remains byte-identical at 0.15.0.dev0; stable 0.14.0 is not promoted.

## Reason and bounded resources

The prior one-hour attempt completed ten of fourteen eager trajectories; its
[880-file stopped capture](../reports/core-010-stopped-preservation.json), original
sources, registration, failure and v1 protocol remain immutable. Four eager cases
remain unqualified by that attempt. Passing subsets do not replace their coverage.

The [projection](../reports/core-010-runtime-projection.json) uses the slowest
observed eager cost per accepted step for every case, the original lane schedule
and an additional 900-second allowance for preservation checks, final auditing,
I/O and contention. It estimates 5237.97 seconds (87.3 minutes), not a guaranteed
upper bound or a compiled-throughput/GPU benchmark. The recorded completed eager
manifest hashes bind all measured inputs; missing case costs are extrapolations.

The new [resource definition](../configs/acceptance/spatial_extracellular_resources_v2.json)
sets **7200 seconds and 2 GiB**, with CPU affinity 0–3, the same four single-CPU
eager lanes, the same case order, and one-thread BLAS/OpenMP. Compiled work still
shares those CPUs. A budget stop or child failure fails this new session too;
retain its evidence and stop, with no automatic retry or budget extension.
The separate read-only audit and regression/closeout work are outside the bounded
capture, as in v1, and must be reported separately.

## Unchanged science and execution coverage

Inherit every v1 equation, reference, definition, capacity, event, horizon,
observation, timestep, numerical domain, trajectory/accounting tolerance,
checkpoint, window and cohort requirement. Do not tune parameters, integrate a
new reference, omit expensive cases, reuse v1 trajectories as new results,
change production execution or claim optimization.

The complete new gate therefore requires 57 scalar runs: fourteen each compiled,
eager, refined and fresh-process restarted, plus the nonzero-history future
branch. It also requires four scalar windows and four original plus four
fresh-process resumed cohorts. All complete checkpoints, independent physical
readouts, incoming-control Hermite bounds and earlier-family replays remain
required. Exact replay means matching dtype, shape and bytes, including signed
zero; enforce the existing byte-for-byte requirement explicitly in the shared
comparison, without changing tolerance-based comparisons.

## Registration and closeout

Select a named, validated resource profile; never mutate the imported v1 plan or
accept an arbitrary command-line timeout. Main and fresh-process workers resolve
the same profile from the saved registration. Registration v2 binds its resource
definition; the implementation capsule includes both protocols, the runtime
projection and the [740-file pre-edit baseline](../reports/core-010-retry-workspace-baseline.json).
The v1 profile remains explicit and rejects v2 resource metadata.

Before execution and at independent audit, reauthenticate the stopped v1 evidence.
All 51 production modules, existing scientific fixtures, original v1 plan and
independent physical oracle must remain unchanged. The only planned existing
code edits are resource-profile plumbing in the run driver, artifact auditor
and acceptance closeout, plus strict byte enforcement in the existing exact
comparison. Four existing status documents may be updated; new resources,
tests, protocol and reports are additive.

After capture, a separate read-only full-panel audit and all six regression
source contexts must pass against the captured implementation. Short preflight
tests are not complete-panel acceptance. Record old failed tests/stops honestly.
Successful closeout qualifies this development build only; stable promotion,
biological validation, new physiology, large-mesh solvers and GPU performance
remain separate work.
