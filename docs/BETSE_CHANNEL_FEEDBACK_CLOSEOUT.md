# REF-004b coupled feedback: independent saved-data closeout

D096, 2026-09-15. The user requested the next independent audit after reviewing
D095's completed capture. This is a new, single-use saved-data audit, not a
simulator rerun or a new integration experiment.

## Evidence and scope

D095 finished in 338.424 seconds. Reference convergence, all required finest-grid
comparisons, refinement, four eager/JIT pairs and four complete restart pairs
passed. Its 5,181,760 native boundary/probe comparisons had zero failures;
2,264 absolute charge snapshots were checked. Fourteen coarse native diagnostic
failures remain: seven active-channel voltage and seven blocked-channel gate
rows at 25 microseconds. Preserve them and their unchanged acceptance policy.

Freeze all 284 capture files, its 112 source inputs, five software XML attempts,
historical handoffs, preceding evidence, and accepted 352 implementation files /
51 production modules. The original receipt remains `capture_pass_pending_audit`.
Completion SHA-256:
`28e985c8f1d49d7953b21382ad6a34b6f2989f23c5407a97118902f8391c8ceb`.

## Independent reconstruction

Replay frozen D095 comparator code with all output redirected into the new audit
or checked against immutable saved output. Never write into the capture. Numerical
identities are rebuilt alongside replay by separate standard-library modules.
These use D094's independently audited mathematical primitives, not D095's
continuous oracle, comparator, definition compiler or either simulator.

Check every reference readout, sampled/endpoint dense polynomial, blocked analytic
control, thermodynamic identity and method/tolerance agreement. Use a direct
polynomial-basis sum independently of the original nested dense evaluation and
log-ratio free-energy algebra independently of the original state-function
subtraction. No reference integrator or numerical Jacobian is rerun. This checks
saved numerical evidence; it is not a rigorous ODE error bound over all real times.

Rebuild every native step identity with a bounded one-step ledger, including
gates, permeability, GHK flux, inventory ownership, current, accumulated transfer
and capacitor voltage. Check absolute charge, observer pairs, full array bytes,
clock mappings, partial records and fresh constitutive probes. Preserve all
native pickles by hash; never unpickle or claim native restart equivalence.

Independently reconstruct Cells definitions from geometry and ionic inventories,
all state/readout identities and inactive padding. Decode numeric NPZ/NPY
checkpoints with the standard library, without NumPy or pickle; check all state,
layout, definition, clock, source and runtime fields against saved trajectories.
Rebuild restart/backend comparisons, common-time cross-engine and reference
comparisons, interval transfers and refinement decisions under the original
budgets, including reference/roundoff-limited classifications.

Compare both measured and expected columns to independent values under unchanged
unit tolerances. Require identical comparison coverage and pass/fail decisions.
Save per-group counts and deterministic identity-stream hashes, plus every
mismatch; do not materialize millions of passing JSON rows in memory. The full
original raw data and frozen audit source make passing identities reproducible.

## Execution and limits

Before launch, bind the new source capsule, passing audit-only software tests,
the original 157-test receipt and all capture/runtime identities. Software checks
use synthetic or bounded saved-data slices; the complete registered audit is a
separate detached execution. No Cells/BETSE/NumPy/JAX/SciPy imports are permitted
in the audit process. No production code or historical input changes.

One detached audit: CPUs 0–3, 900 seconds overall, 256 MiB aggregate artifacts,
128 MiB per file and per decoded record. These artifact limits are not RAM limits.
Retain failure receipts and return without polling, retry or automatic follow-up.
The user requests status.

Only a completed passing audit qualifies this fixed 2 ms four-control numerical
pilot at its registered observations and budgets. It does not qualify biology,
general BETSE parity, long-time/stiff regimes, native restart, GPU, organs,
multiple organs or cross-resolution coupling. Those remain separate tasks.
