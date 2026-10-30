# One accepted ordinary tissue interval with held component permeability

Worker scope: three new files only. Chief owns the public checkpoint wrapper,
shared dispatch/docs and `PROGRESS.md`. No commit or staging action was taken.

## API and acceptance

`cells.core.physiology_tissue_step.advance(spec, checkpoint, binding, component,
*, end_time_s=None)` returns `TissueStepResult(checkpoint, binding, component,
trial, admission)` after exactly the next original `EventGrid` interval.
The optional requested endpoint must equal that next boundary exactly. Source
schedules select the held RK control packet; a caller cannot supply another
packet. The actual right-continuous endpoint control is checked separately.

Input and accepted output pass original ordinary `validate_checkpoint`.
Original passive zero/nonzero support must match in both directions. The
temporary runtime layout changes only current passive permeability from the
explicit D/thickness mapping. The accepted checkpoint keeps the identical
original layout object and physical anchors; binding and component objects are
also returned unchanged. Component time/loop/RNG state does not advance. There
is no random draw, scheduled-buffer finalization or protein-charge coupling.

`array_rk4_step(state, control, runtime_layout, step_s, *, implementation, xp)`
is the separate array-only trial kernel. Its static implementation must be one
of the four ordinary passive/ionic/calcium/fuel modules. It returns raw states,
derivatives and domain/field/rate/gross status for y0/y2/y3/y4/the proposal. Each
stage checks actual absolute passive membrane transfers per finite free-ion
stock and all-consumer finite-fuel turnover against unchanged 0.05 bounds.
RK trial stages do not receive exact integrated-energy/history checks.

At host acceptance, before/after two-row histories pass original and changed-P
full conservation, energy and monotonic-dissipation checks. A restored JAX
layout receives a temporary NumPy view for the NumPy endpoint guard; output
still retains the identical restored layout. This is the only core correction
after the first qualification attempt; no physical equation changed.

`TissueStepRejected` retains the source checkpoint, binding, component, held
control, runtime layout, proposed endpoint, stage/diagnostics and frozen raw
trial if it was constructed. Rejected values are neither clipped nor committed.
Pure trial validity is not equivalent to host acceptance or an accuracy claim.

## Accuracy scope and preserved failures

Original ordinary budgets remain state `3e-12 + 3e-10*abs(reference)` (charge
fields `3e-23 C` absolute), potential `3e-13 V + 3e-10*abs(reference)`, reference
uncertainty at most 0.1 budget, and original conservation/domain tolerances.

The original passive 100 us source timestep is **unqualified** for endpoint
trajectory potential on both compared intervals, 0..100 us and 100..200 us.
Potential errors are 1.1032134364 and 1.1525784376 budgets. Full-state errors are
0.0210509438 and 0.0200676447 budgets; same-state field closure is within
1.85e-5 budget. The separate field-closure check does not replace trajectory
potential acceptance. Original run01 and diagnostic02 failures remain intact.
The final test marks only its dedicated `EndpointPotentialAccuracyError` as a
strict expected failure after saving all interval metrics and checking other
gates. It adds no positively qualified physical-case credit.

Two internal half steps resolve the original potential discrepancy (0.06824
and 0.07131 budgets) but are numerical evidence, not public accepted checkpoints.
The separate refined recipe declares 50 us source dt **before** binding,
initialization and evolution. It covers the same 0..200 us compared physical
span via four accepted original-source-grid intervals. Standard and tighter
independent DOP853 trajectories carry their own states continuously from the
same initial state across that grid. Geometry, original 2 ms experiment horizon,
absolute schedule events, observation declarations, caps and tolerances are
unchanged. Its maximum state error is 0.0024763819 budget and trajectory
potential error 0.1422473490 budget; reference uncertainty is below 1.36e-7
budget. No claim is made for a complete 2 ms accepted trajectory.

The remaining seven original family/control cases cover initial/evolved
intervals, including an event endpoint followed by an evolved interval.
Unchanged-P checks compare every state field bitwise to established RK4.
Restored-layout checks cover all four families across event/evolved intervals.
Public checkpoint/RNG restart evidence belongs to Chief and is separate from
trajectory accuracy evidence.

## Evidence

Machine-readable ownership, budgets, exact hashes and run references:
`physiology_tissue_step_workqueue.json` in this directory.

- Original host failure: `/mnt/workspaces/Cells/physiology-tissue-step-tests-20261030-01/`.
- Pure NumPy/CPU-JAX eager parity pass:
  `/mnt/workspaces/Cells/physiology-tissue-step-cpu-jax-20261030-01/result.json`.
- Both coarse intervals and preserved test-helper failures:
  `/mnt/workspaces/Cells/physiology-tissue-step-diagnostics-20261030-02/`.
- Final captured-source host and production-import-denied reference run:
  `/mnt/workspaces/Cells/physiology-tissue-step-tests-20261030-03/`.

Host checks passed 29 cases with one strict expected coarse accuracy failure.
The earlier one-case CPU JAX eager check is retained by exact unchanged array
kernel, parity-test and captured-dependency correspondence. It covers the
passive kernel on CPU, not all-family JAX execution or GPU qualification.
The fresh production-import-denied process replayed all 20 actual intervals
with zero difference from saved standard DOP states. Its 14 qualified original
intervals and four accepted source-refinement steps pass all state/potential
gates; the two original coarse intervals retain their accuracy failures.
These replays add no biological cases. Across qualified intervals, maximum
state error is 0.028525 budget and potential error 0.241026 budget. Same-state
field error is at most 3.22e-5 budget across all 20 intervals.

Final receipt:
`/mnt/workspaces/Cells/physiology-tissue-step-tests-20261030-03/result.json`,
SHA256 `4272709fa95382d0ebd41ff26317a960e48bfbf7878179771ced6c999a92489a`.
Host/reference phases took 146.02/49.24 s, with peak RSS 282718208/85409792 B.
The retained CPU JAX phase took 19.12 s with peak RSS 430837760 B.
Thus there are 30 positive worker checks (29 current host plus one earlier
unchanged-kernel CPU JAX check), with one separately retained strict expected
coarse accuracy failure. The three worker sources are frozen; full hashes are
in the workqueue and receipt.

Chief separately reports 46/46 public restart/association checks passing in
51.8 s, including native/stable streams on all four families:
`/mnt/workspaces/Cells/physiology-tissue-step-checkpoint-20261030-02/result.json`.
Those serialization checks add no temporal accuracy credit.

All commands use CPU7,
one thread, CPU-only x64, no persistent compiler cache, <=480s per phase,
<=1GiB process-tree RSS and >=8GiB host reserve. No long job, active campaign
polling, frozen physics/view edit or shared-file edit was performed.
