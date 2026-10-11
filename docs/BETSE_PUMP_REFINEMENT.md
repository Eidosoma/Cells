# Native pump–leak timestep refinement

2026-09-16, D119 / REF-005c refinement. **Explicit amended capture, not a pass.**
The [failed-pilot diagnosis](../reports/REF005C_PILOT_FAILURE_DIAGNOSIS.md) supports
finer native steps without changing Cells. The original
[D117 scientific contract](BETSE_MATCHED_PUMP_PILOT.md), failed attempt and
independent diagnosis remain immutable.

## Engineering rule: compare mechanisms, not numerical errors

The user explicitly requires that Cells not reproduce another simulator's
errors. Cells retains its existing checked RK4 integration, conservative model
composition, stage/interpolation safeguards and energy accounting. It is not
changed to match a finite-step BETSE trajectory.

The observed first-order native error is a discretization limitation of this
preparation, not by itself proof of an upstream biological-law or coding bug.
The independent DOP853/Radau reference, physical accounting and timestep
refinement remain separate checks. If the discrepancy does not converge as
expected, retain the rejection and investigate the equations, preparation and
numerics. Do not fit biological parameters, subtract the diagnosed convex energy
remainder, relax tolerances, or adopt source nonce behavior as production biology.

## Exactly what changes

The [machine-readable amendment](../validation/betse/pump_pilot_refinement/protocol.json)
changes only native timesteps, explicit recording/runtime bounds and experiment
identity. It derives the effective comparison contract from the preserved D117
registration; all numerical budgets, physical inputs, reference settings, sample
times, Cells timesteps and restart definitions remain unchanged.

| Item | This attempt |
| --- | --- |
| Native timestep ladder | 6.25 / 3.125 / 1.5625 µs |
| Physical duration and common observations | Original 1 ms and five elapsed-time observations |
| Controls | Original six, including blocking, density scaling and boundary masking |
| New native trajectories | 36: six controls × three steps × observed/unobserved |
| Observed native updates | 6,720; 13,440 updates including unobserved partners |
| Exact overlap | All twelve 6.25 µs result records compared with the original capture |
| Reused production trajectories | All 24 Cells runs, including six complete restart suffixes |
| Reused independent references | All eighteen DOP853 base/tight and Radau solves |
| New Cells/reference solver runs | Zero |

The new controller calls the **unchanged D117 native producer**, which itself
uses the unchanged preparation hook, read-only observer and pinned BETSE driver.
No source monkeypatch, replacement integrator, flux substitution or hidden
change of native model is introduced. As before, actual elapsed updates are
distinct from native raw sample labels.

The reuse phase copies **213 saved files / 19,571,298 bytes** into the new
attempt and checks every byte digest. The copied manifests retain their original
identity and provenance; they are not relabeled as newly executed runs. The
original complete 431-file failed packet remains sealed separately.

## Unchanged science, more useful rejection records

The comparator reuses the original state reconstruction and instantaneous
reference equations, without invoking any solver. It retains the original
finest-grid state/voltage/energy limits, native accumulated-roundoff policy,
energy closure requirement, cross-engine budgets, Cells backend checks and all
36 floor-aware refinement groups.

Numerical comparison misses are counted across the panel and grouped, with up
to **64 first examples** including scope, coordinate, observed/reference values,
error and budget. Per-row records retain reconstructed trajectories, accounting
and reference-error summaries. Thus a first failed energy coordinate no longer
prevents later numerical criteria from being reported. Missing/changed evidence,
invalid domains, conservation assertions, mismatched clocks or non-reproducible
overlap still stop the attempt. Better reporting is not a weaker pass condition.

The comparison software must reproduce **all six original failures** on saved
D117 data before launch. This replay writes only to a fresh temporary directory,
does not integrate either simulator, and leaves the original failed packet alone.
The twelve overlap checks compare canonical JSON digests, including signed zero,
rather than only approximate voltages or Python float equality.

## Resources and execution boundary

Use CPUs **0–3**, one BLAS thread, float64 and the existing separate native
environment. Time limits are **90 s reuse / 900 s native / 180 s comparison /
1,260 s total** (21 minutes). Require at least **3 GiB free disk** before launch.

The hard per-file limit is **256 MiB**; the checked aggregate artifact budget is
**2 GiB**. These are disk-recording limits, not RAM limits. The original 160-step
observed result is approximately 34.2 MiB; a 640-step trace would exceed the
original 64 MiB/file cap. Keep the existing raw recording format and raise these
limits explicitly rather than dropping observations or introducing an unverified
chunked recorder. Aggregate checks run between records/phases; failures retain
partial output. The frozen producer keeps its existing between-row disk guard.

Register and archive **641 source/configuration/contract inputs**, the new
passing software receipt, original registration, diagnosis receipt and complete
reuse manifest. Reauthenticate before/after phases and retain durable stdout,
stderr, partial row records, source capsule and terminal completion/failure.
The terminal failure also attempts to seal all completed payload bytes.

See the [launch handoff](../reports/REF005C_REFINEMENT_HANDOFF.md). Launch once
detached, return immediately, and leave status polling to the user. No automatic
retry, regression, audit or subsequent campaign. Even a producer pass is only
`refined_pump_pilot_pass_pending_independent_review`; independent review waits
for the next instruction. No biological, whole-organ, full BETSE-parity, GPU or
release-promotion claim follows from this short CPU comparison.
