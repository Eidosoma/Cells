# B14 atomic perturbation component

The two new files `src/cells/core/physiology_perturbation_step.py` and
`tests/unit/test_physiology_perturbation_step.py` pass29 short CPU cases. Exact
source hashes and the durable receipt are in
`physiology_perturbation_step_workqueue.json`. The sampler and stream-ledger
files remain byte-identical. Chief owns the separate checkpoint extension,
integration tests, shared documentation and PROGRESS.md.

`PhysiologyPerturbationState` has exactly six frozen/slotted fields: `protein`,
`diffusion`, `stream`, `controls`, `time_s`, `loop_calls`. The three protein and
three permeability buffers are independent float64 copies backed by immutable
bytes, including the signed scheduled modifier. The accepted state cannot
alias caller buffers or re-enable NumPy writes.

- `initialise(binding, controls, protein, diffusion_m2_s, stream)` returns a
  component state. It always consumes one `static_K` draw, including INIT,
  fast/disabled/zero-level cases, and saves Dm_base before static noise. Its
  component elapsed time and loop count start at zero.
- `advance(state, binding)` returns
  `PerturbationTransition(state, packet, diagnostics)`. Diagnostics are a
  read-only mapping. The first call has source label0 and applies one full
  controls.dt_s. Every successful call advances elapsed time and loop count,
  including inactive branches. Only enabled draws advance the stream tick.
- `validate_state(state, binding)` returns the exact validated original object
  without drawing, changing counters or mutating buffers. It supports the
  separate checkpoint loader.

A SIM call finalizes current permeability from base+scheduled before the
protein branch, so the first SIM finalization removes the initialization's
static perturbation. INIT does not finalize. The source dynamic guard is reused
exactly: normal SIM with dynamic and protein enabled. An enabled zero level
still draws. Inactive branches preserve every prior protein buffer, including
stale membrane readouts. Downstream bulk refresh and clipping remain separate;
this is a component transition and does not claim full BETSE loop parity.

Inputs, trials and accepted buffers retain the original nonnegative/domain and
conservative-transfer requirements. Signed finite scheduled modifiers are
allowed, but a negative finalized physical permeability refuses before the
protein draw. The frozen protein domain predicate checks positivity and its
original3e-13 relative transfer-conservation bound. A source_fast duplicate
mapping with an actual conservation defect refuses; no arithmetic correction
or blanket ban on conservative nonmatrix mappings is added.

`PerturbationRejected`, a `NumericalError`, retains `.trial`, `.packet`,
`.stream`, `.diagnostics`, `.stage`. If a draw already occurred, `.stream` is
the proposed advanced RNG/cache and `.packet` is its exact draw; the caller's
accepted input remains untouched. The typed `.trial` preserves raw invalid
values and proposed time/count where constructed; it is not an accepted
checkpoint and may intentionally fail validate_state/replay_record. Before a
typed initial trial can be constructed, `.trial` can be None. Pre-draw refusals
have no packet and retain the old RNG. Callers can persist forensic arrays
without promoting them to accepted state. The module does not retry or clip.

Loop count overflow, nonfinite accumulated time or an addition that cannot
advance the floating clock refuses before sampling. The elapsed component
clock counts explicit calls and is independent of a paired deterministic
checkpoint's numerical clock. No RK stage, sqrt(dt) scaling, automatic event
dispatcher/tissue mapping or disabled microtubule path is introduced.

The29 cases cover exact seven-call native composition, stable/native static and
zero-level draws, phase/solver/disabled guards, first-label timing, scheduled
finalization, immutable copies, retained negative and nonconservative trials,
missing-K post-draw timing, conservative source_fast/mixed-bath cases, overflow,
invalid buffers and nondrawing foreign-binding validation. This verifies the
new composition, without a new RNG distribution or whole-physiology claim.

Receipt:
`/mnt/workspaces/Cells/physiology-perturbation-step-tests-20261029-01/result.json`,
SHA256 `d9eee3247cebd6da0ac6da9faccf6e4266d889047a588d55228882a68399081f`.
CPU7/one thread,180s wall allowance,1GiB child-tree RSS,8GiB host reserve,
no GPU/JIT/persistent compilation cache. Completed in3.79s with254,955,520B
sampled peak RSS. No long job, active-job poll or shared/frozen edit ran.
