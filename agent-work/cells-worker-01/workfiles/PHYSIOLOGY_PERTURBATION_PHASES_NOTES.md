# Explicit pre-ion preparation and post-ion component finish

Chief owns numeric charge routing, loop/cursor/publication composition and later
coupled acceptance. Worker owns only the new component phase core, independent
reference, tests and workfiles. All previously qualified modules stay unchanged.

## API

`physiology_perturbation_phases.prepare(state, binding)` returns immutable
`PerturbationPreparation` with `source_state`, `held_state`, complete source/
held/binding identities, its own sealed identity and diagnostics. Binding is the
existing `betse_perturbations.Binding`, not a new tissue binding. The held state's
diffusion D has units m2/s; existing explicit thickness/owner mapping converts it
to tissue P. No protein/stream/controls/time/count value advances in preparation.
No static initialization or random draw occurs. Only SIM current permeability
is finalized as base+scheduled; INIT retains static current permeability.
Clock/count arithmetic is preflighted without advancing the source.

`finish(state, binding, preparation)` receives the original accepted source,
not its held proposal. It rebuilds preparation nondrawing, checks complete
buffers/controls/clocks/RNG/cache and binding against the original source,
then invokes frozen `physiology_perturbation_step.advance` exactly once. It
returns that established `PerturbationTransition` type with state/packet plus
preparation-association diagnostics. Held diffusion must remain identical.
Pure finalization/domain calculations may be recomputed for validation; they
are not additional events, draws or physical updates.

`PerturbationPhaseRejected` retains `source_state`, `binding`, `preparation`,
raw `held_state`/`trial`, `packet`, proposed `stream`, original
`component_rejection`, any complete `transition`, diagnostics and stage. Neither
phase publishes an accepted pair or mutates its input. Root owns numeric trials
between phases and their atomic rejection/publication.

## Source association and timing

Complete source seals reuse qualified component replay and stream records,
including native MT words/position/Gaussian cache, logical tick/ownership,
all protein/diffusion buffers, controls, elapsed time and loop count. A held
proposal or a source modified after preparation refuses before a finish draw.
Resealing an alternative held proposal does not bypass rebuilding the actual
finalization. Content-identical source clones can replay; hashes detect changes,
not authorship. No persistent mutable one-shot token is introduced. Calling
finish again on the same uncommitted source replays the same proposal. Calling
it on the accepted advanced source with a stale preparation is refused.

Native pinned order is SIM finalization, ionic work, then guarded protein noise.
The existing audit is `physiology_loop_bridge_source_audit.json`. Splitting
the component call lets the caller place ionic work between these operations.
The dynamic guard, zero-amplitude draw, full physiological dt/no sqrt(dt),
inactive-call time/count increment and static initialization behavior remain
the original qualified component laws. No event/RK draw rate is introduced.
Component source labels and elapsed clock are not silently matched to native
linspace labels or numeric accepted time.

## Boundaries left to later coupling

- The held state is an uncommitted component proposal, not a portable pending
  checkpoint or permission to publish a mid-loop pair. A persisted partial
  cursor/transaction needs Root's explicit association/format policy.
- Ion evolution, charge/work routing, field acceptance, feedback ordering and
  accepted conservation ledgers are absent here. Reference tests use an ion
  interval marker, not a new numerical trajectory or native full-loop claim.
- Other RNG sites between phases require an explicitly ordered ownership/tape
  protocol; changing the accepted source stream breaks this preparation's seal.
- Source fast/bath quirks and domain refusals remain in the frozen component
  transition. No correction, clipping, new geometry or new RNG law is added.
- If post-ion protein/field acceptance fails, the complete joint transaction
  must retain numeric proposals and the proposed component tape without commit.
  This component module does not claim native failure-prefix parity.

Qualification uses private sources, CPU7/one thread, <=480 s, <=1 GiB process-tree
RSS and >=8 GiB host reserve. Inputs/results/source hashes and run status are
recorded in `physiology_perturbation_phases_workqueue.json`.

## Frozen qualification

All 35 cases pass. They cover exact one-transition composition under native
cached MT/stable laws, six guards including enabled zero level, three successive
calls per profile, immutable/nondrawing preparation, complete source changes,
resealed false holds, clock/permeability preparation failures and post-draw/
overflow finish rejections with preserved original trial/tape. Replayed proposals
match; stale preparations refuse before another component call.

A fresh process with Cells/JAX imports denied replays all 36 actual component
calls in 72 prepare/finish forms across 12 independently carried sequences.
Saved reference data replay exactly; maximum error is 0.000439693 of unchanged
protein/diffusion comparison budgets. Prescribed packets use the already
qualified RNG laws; no independent RNG-engine/distribution claim is added.
The ion marker is an ordering test, not numerical ion/coupled trajectory evidence.

Receipt: `/mnt/workspaces/Cells/physiology-perturbation-phases-tests-20261030-01/result.json`,
SHA256 `1aef291755bac4381bb86019097d358525980816ee04e4eefa52cdd5feb97ee2`.
Unit/reference phases took 8.30/0.52 s; peak RSS 303939584/33062912 B and host
reserve stayed above 21 GB. All three new sources are frozen; 40 protected
sources and captured inputs stayed exact. Full hashes/limits, cached-source
stream records, packets, raw holds and rejected proposals are in the workqueue
and receipt. No old/shared source, GPU action, long run or active campaign query
was changed/launched/performed in this worker lane.
