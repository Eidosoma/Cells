# Compact numerical evidence: proposed next contract

Design note associated with D038, 2026-09-09. **Not implemented or adopted for a
scientific run.** [D037](../reports/NUM005C2A_CANDIDATE_ENGINEERING.md) established
bounded numerical windows but showed that full retained evidence still grows
with every timestep. D038 changes diagnostic computation only; it retains full
short-path evidence. A later compact format requires its own approved
registration, tests, resource preflight and explicit audit scope.

## Keep restart state separate from evidence policy

A restart checkpoint must always contain the complete primary and passive
history state, phase anchor/context, original global grid, topology/controls,
stable IDs, source/runtime identity and lineage. Observers, output selection and
compression must not alter it. Phase transitions need their own complete
boundary/preparation provenance; a reference anchor cannot substitute for a
candidate's preparation result.

Retention should be a data-defined output policy, independent of the model or
organ preset. An asynchronous or device-side future implementation must preserve
the same acceptance order: validate a window, publish its complete accepted
checkpoint/evidence, then advance the durable commit cursor. Never mark an
incomplete window committed or silently skip checks under backpressure.

## Candidate policies and what they can prove

| Policy | Retained data | Offline audit capability | Principal cost/limitation |
| --- | --- | --- | --- |
| Full engineering trace | Every accepted state, five slopes, four cubic rows and all comparison states | Reconstruct every curve and check all saved stages/samples | D037 baseline; storage grows with every step/sample |
| Lossless reduced redundancy | Complete initial/checkpoint state, per-step slopes and only non-derivable fields | Rebuild updates/curves in the pinned arithmetic and check reconstruction hashes | Still linear in steps; must prove bit-exact reconstruction, not assume it |
| Checkpoint plus replay certificates | Complete periodic checkpoints, per-window input/output and ordered evidence hashes, online bounds/maxima with witness times, requested observers | Verify integrity immediately; re-execute a pinned window to reconstruct omitted evidence | Hashes alone do not independently verify omitted calculations; replay costs must be budgeted |
| Sparse scientific readouts only | Selected observations and summaries | Inspect only retained observations | Not sufficient by itself for restart or full numerical qualification |

Recommend prototyping lossless redundancy removal first. If it cannot fit the
unchanged aggregate cap, a checkpoint/replay design needs an explicit change to
the evidence/audit policy. Do not describe the latter as equivalent to retaining
and independently auditing every original curve without actually replaying it.

For example, Hermite cubic rows can be regenerated from adjacent accepted states
and endpoint slopes. A format could omit redundant cubic rows while retaining
stage slopes and reconstruction hashes. It must preserve the original update
ordering and source/runtime identity, include off-grid final steps, and handle
restarts/failure tails. Dropping redundant arrays does not change equations; it
does change the reader and recovery/audit contract, which must be tested.

## Aggregate cost and failure semantics

Plan simultaneously for device buffers, host buffers, Python metadata/indexes,
disk artifacts and verifier/replay cost. A fixed numerical window does not imply
constant process RSS: receipt inventories and repeated whole-directory scans
grow with file count. Prefer a bounded streaming manifest and explicit byte
accounting with periodic independent reconciliation, rather than rescanning
the complete output tree on every chunk. This needs crash/partial-write tests.

Use append-only, hash-linked window records with an exclusive final receipt.
Retain partial files and a distinct failed-window receipt after interruption;
do not promote them into complete checkpoints or overwrite prior accepted data.
Failures in one write should not suppress an otherwise possible last-accepted
checkpoint/failing-input record. Declare durability, atomic-publication and
recovery assumptions explicitly; filesystem atomicity is not a substitute for
end-to-end validation.

All old reference and failed artifacts continue to count against the shared
quota. A new directory or policy revision is not a budget reset. Derive raw-layout
bounds first and measure actual lossless output; compression ratios from short
transients are not a promise for a long study. Include the storage cost of
candidate-owned preparations, selected/half-step trials and audit receipts.

## Evidence needed before adoption

Use the exact existing short fixtures to compare a proposed policy with full
evidence: decoded state/clock/curve/sample identity, every acceptance decision,
restart at arbitrary accepted window boundaries, source mismatch and corruption,
missing/reordered chunks, interruption and quota refusal. Audit reconstructed
evidence independently, including worst-error witness reconstruction.

Then measure the complete checked path plus offline audit/replay, not just
writer throughput or RHS speed. Specify any loss of independently inspectable
evidence before selecting a policy. Only after a complete numerical/resource
preflight should a separately registered long candidate study be considered.
No GPU, organ model, new dependency or storage library is selected by this note.
