# REF-004d: actual native channel input preflight

D102, 2026-09-15. The user approved continuing after the D101
[input design](BETSE_CHANNEL_RELEASE_DESIGN.md). Run actual native preparation,
external availability application and separately checked single updates. Do not
infer a release response from the design or these short probes. Cells production,
the native implementation and all previous evidence remain unchanged.

## Fixed experiment and what time means

Use the D101 four conditions, histories a/b, native 25/12.5/6.25 microsecond
steps and query times 0, 0.5 and 1 ms. These are **input queries**, not elapsed
simulated time in this preflight. The 2 ms candidate still needs a separate
piecewise reference gate before any own-state release trajectory.

For each history/step, seed the same pinned seven-cell/thirty-face geometry.
For every condition/query/observer mode, create a fresh native INIT phase. Keep
one real Kv1p5 channel uniformly targeted, 298.15 K, matched constants and the
same finite shared bath; no passive leak, pump, GJ, new chemistry or SIM event.
Initialization and explicit m/h match D100-authenticated native starting states.
Reseed NumPy from the existing explicit preparation seed before every fresh
phase. Native initialization draws a channel-noise vector even with noise
disabled; observer partners must start with that hidden numeric field identical
as well. Do not exclude it from the non-interference inventory.

1. Execute **one active priming update** using the actual gate/channel,
   empty-network export, ordinary update and charge/voltage functions. This
   creates nonzero channel flux, inventories and hidden-state history.
2. Apply the input prefix up to the selected query to that same primed state,
   with **no integration between applications**. Set only absolute
   `maxDm = immutable_baseline * availability`. In particular, release restores
   the baseline after a previous zero; it does not multiply that zero.
3. Record complete declared ionic/channel state, stored currents and a recursive
   numeric inventory of sim/network/channel/gate/geometry roots before and after
   input. All must remain identical except the excluded `channel.maxDm` input.
   Opaque object metadata is labelled, not pickled or claimed to be serialized.
4. Evaluate fresh native flux on copied state with the new input, without
   advancing gates. The old cached flux remains unchanged at application; it is
   not the new instantaneous current. Preserve and verify the native copied-
   argument record, including the source's `1e-25` voltage/valence additions.
5. Execute **one probe update** and independently check gate-first order,
   effective diffusivity, flux, current export, one-owned cell/bath transfer,
   inactive species, capacitor voltage and no duplicate ordinary transfer.

This gives **six seeds / 144 fresh phases / 288 single updates / 288 input
applications / 72 observer pairs**. Each phase advances only `2 * dt`, not to its
query time. Prefix length is one/two/three according to query. The static-block
fixture still gets the common active priming update; it is not a simulation of
the static-block protocol starting at time zero.

Actual configured Parameters generate the candidate native `linspace` labels;
require exact agreement with the previously captured native full-loop labels.
Map each prospective query by its elapsed step index, never by substituting its
endpoint-labelled native time. No new full-loop input hook is executed here.
Its eventual timing and observer behavior still need dynamic qualification.

## Independent checks and non-interference

Use the existing independently audited 80-digit gate/constant-field equations
and unit-specific single-transfer budgets unchanged. Reconstruct native rational
gate updates separately from a future continuous/RK4 reference. Explicit gates
must keep changing while transport is blocked. Blocked fresh flux and inventory
changes are exactly zero; nonzero stored priming history must survive application.

Read-only source/instance-scoped profiling records gate entry/return and transfer
entry/return. An observer-off partner repeats each complete case on fresh objects;
all state, inputs, numeric guards, fresh readouts and final accounting must match.
Baseline/no-op controls must agree. Never replace an upstream method or treat the
input setter as a read-only observer.

The gate-entry check accounts explicitly for the native network materializing
the unit-modulator vector before calling the gate. Transfer-entry voltage must
equal pre-step voltage plus the native electroflux `1e-25` addition; concentrations
and cached flux are still unchanged there. Neither field is silently omitted
from the observer comparison. Input application itself has no such side effect.

Save before/after states and partial records before assertions. The independent
checker rejects missing cases, duplicate comparisons, state resets, altered
metadata/targets, wrong clocks, invalid restoration and current/transfer errors.
Raw capture pass remains `release_input_preflight_pass_pending_review`.
Separate saved-data review follows user instruction, not automatically.

## Verification, preservation and execution

Short software checks include two explicitly test-only native cases: one block
and one release, with observer partners (**four phases / eight single updates**).
They cannot qualify or substitute for the full 144-phase panel. Keep their
software receipts separate from the registered capture's actual completion.

Before launch, authenticate D101's five design inputs/software manifest, D100's
ten-file independent packet and 152 inputs, D099's 291 files/143 inputs, accepted
352 implementation files/51 production modules and installed native sources.
Bind the new plan/code/document, passing software XML and handoff in a fresh
registration and source capsule. Registered/executed sources become immutable.

One detached CPU 0–3 job, **480 seconds total / 360 seconds native worker /
256 MiB aggregate artifacts / 64 MiB per file**. The compressed reader retains
its existing 128 MiB decoded-record ceiling; artifact caps are not RAM limits.
Persist logs and exclusive completion/failure receipts. Return after launch,
without assistant polling, retries, automatic audits, reference solves, Cells
trajectories, GPU work or release qualification.

After the actual result is reviewed, the following gate is piecewise independent
reference/domain/convergence/signal registration, followed by the smallest
controlled native/Cells release comparison and its separate saved-data audit.
No physiological inhibitor, slow recovery, biological memory, broad BETSE parity,
native restart, organ-scale or GPU claim follows from this preflight.
