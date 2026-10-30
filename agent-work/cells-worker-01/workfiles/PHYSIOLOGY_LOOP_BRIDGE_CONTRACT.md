# Proposed atomic physiological-loop bridge

Purpose: prevent event/RK refinement from changing component call frequency or
noise scaling, and make partial failures reproducible before adding a coupled
execution identity. Chief owns paired checkpoint/cursor persistence and public
I/O; worker owns new core/reference/unit files only. Chief approved the limited
Cells identity after this audit; typed cursor signatures below are final.

## Pinned source findings

`physiology_loop_bridge_source_audit.json` verifies all ten source hashes at
BETSE revision `5269a714aa2593ed2a6708c4516289977d8ae1a2`, and records actual
AST order, guards and line references. Normal loop order is SIM event firing
and `base + scheduled` permeability finalization, ion/network work, guarded
protein flux draw/update, then bulk concentration refresh and voltage update.
The guard requires normal SIM, dynamic enabled and protein enabled; enabled
zero amplitude still draws. Fast has no protein draw. INIT skips SIM finalization
and dynamic protein draws. Static initialization is outside the loop and draws
once even at zero amplitude. Disabled microtubule paths stay disabled.

Native loop labels use `linspace(0, N*dt, N)`, while each concentration update
uses full `p.dt`, including the first label zero. Thus native labels, accumulated
component duration and Cells accepted integration times cannot be silently
identified. Native protein noise is a uniform flux multiplied by full `dt`,
with no `sqrt(dt)` normalization.

## Proposed API and clocks

`physiology_tissue_loop.initialise(spec, checkpoint, binding, component, *,
loop_index=0)` returns `TissueLoopCursor`. `cursor_record(cursor)` exports a fresh
JSON record; `restore_cursor(record, spec, checkpoint, binding, component)`
rebuilds it against the complete actual pair. `advance(spec, checkpoint, binding,
component, cursor)` returns frozen `TissueLoopResult(checkpoint, binding,
component, cursor, component_transition, tissue_steps, admission)`.
`result.next_loop_index` aliases `result.cursor.loop_index`.

Cursor kind is `cells.physiology_tissue_loop@1`. It seals complete source/binding,
numeric state/layout bytes, complete component controls/buffers/RNG and current
clock coordinates. Signed `component_call_origin = component.loop_calls -
loop_index` is explicit and preserved on transition. Canonical schema/type
comparison rejects even resealed mismatched associations; hashes detect changes
and do not authenticate authors. Root owns only paired file/container integration.

- Physiological duration is exactly `component.controls.dt_s`. Finer tissue
  `spec.execution.dt` is independent and never substituted into component noise.
- Cells nominal left/right times are `loop_index * physiological_dt` and
  `(loop_index + 1) * physiological_dt`. Both must be exact original `EventGrid`
  points, with the source checkpoint exactly at the left point. Caller supplies
  the explicit nonnegative integer loop index; never infer it from the event
  count or round a quotient. No new grid point or observation is inserted.
- A full nominal interval must lie inside the original source experiment.
  Refuse a partial final loop rather than shorten/rescale the component call.
- Component elapsed time, component loop count and RNG tick remain explicit
  independent coordinates; prior INIT calls or an elapsed-time offset need not
  equal the Cells loop index/time. Admission reports before/after coordinates.
- The source nominal-loop clock is a declared Cells convention, not native
  `linspace` label parity. Numeric clocks/step/event indices remain the exact
  original checkpoint clock. Chief's cursor binds these source/component/numeric
  coordinates to the accepted pair; no mid-loop cursor is accepted in this API.

## One transaction

1. Validate original source checkpoint/grid, binding/component ownership, loop
   index/clock and complete target before any component call.
2. Stage exactly one frozen `physiology_perturbation_step.advance` at the left
   boundary. It preserves its existing order: SIM finalization, guarded protein
   draw/update, full physiological duration/count increment. No static redraw,
   new sampler, seeding, amplitude rescaling or hidden component schedule exists.
3. Hold that proposed component's current P fixed. Repeatedly call frozen
   `physiology_tissue_step.advance` across every original tissue/control grid
   interval through the nominal right endpoint. Source controls may change at
   their original event times; P/component/RNG do not change between substeps.
4. Return only after all local tissue steps pass original acceptance. Publish
   numeric checkpoint + component + incremented cursor only for whole-loop
   success. Intermediate locally valid checkpoints remain uncommitted trials.

`LoopRejected` retains original checkpoint/component/binding, loop clocks,
the component transition or rejection, proposed component/stream/packet when
constructed, a tuple of completed local tissue results, and the actual failed
tissue rejection/raw trial. No input is mutated; no partial accepted pair,
retry, clipping, hidden draw or RNG commit occurs. Chief owns publication failure
artifacts and the accepted pair/cursor association.

## Scope of the composition

Staging the full component transition at the left moves the native protein
update earlier than its source position. Accepted transformations commute only
because the four ordinary tissue RHS families never read component protein,
the component protein update never reads tissue ions, and tissue stepping has
no RNG sites. Permeability finalization remains before ionic work. Native
charged-protein effects on downstream voltage and other source handlers are
outside this identity. Its speculative RNG draw on a failed tissue transaction
also does not claim native failure-prefix parity; the proposed tape is retained.

Existing route-support restrictions, original checkpoints/layout/anchors,
finite-stock guards, conservation and trajectory accuracy budgets remain exact.
Geometry/cuts, whole native physiology, charged-protein coupling, fast equivalent
circuit integration, other RNG sites, GPU execution and automatic schedule
buffer staging are excluded.

## Focused evidence

Plan one bounded CPU7 qualification using captured private sources and existing
runners: exact manual composition on four ordinary families and native/stable
streams; first/evolved loops with finer tissue steps and original control events;
phase/solver guards including enabled zero amplitude; independent component-clock
offsets; bad boundaries and partial-horizon refusals before draws; and component/
later-tissue failures retaining proposed tape and completed trials.

Independent Decimal component transforms use prescribed packets under the
already-qualified RNG law. Complete held-P DOP trajectories carry their own
state continuously across source tissue/event intervals and loop boundaries;
standard/tight uncertainty and all state/potential gates stay unchanged. Finer
tissue grids/event subdivisions must preserve component packets, protein
increments and draw counts at fixed physiological dt. No new distribution,
whole-experiment trajectory or biological-case credit is inferred from exact
composition/restart checks. Limits remain <=480 s per command, 1 GiB process-tree
RSS, >=8 GiB host reserve, one CPU/thread, no GPU or persistent compiler cache.

## Frozen qualification and handoff

All 44 cases pass: 40 contract checks and four complete continuous-reference
trajectory cases (eight initial/evolved nominal loops, 20 common source-grid
endpoints). A fresh process with Cells/JAX imports denied replays all eight
standard/tight loop trajectories with zero state difference from saved evidence.
This adds no biological cases or independent RNG-engine claim. The prescribed
packets use the already-qualified native/stable laws.

Maximum full-state error is 0.0027078472 budget, potential error 0.1020229810,
reference uncertainty 3.64013e-6, and Decimal component error 0.000292164 budget.
Budgets are unchanged. Passive qualification covers 0..200 us with physiological
dt 100 us and tissue dt 50 us; ionic/calcium/fuel cover 0..2.5 us with physiological
dt 1.25 us and tissue dt 0.625 us. The declared 2 ms source experiments/events/caps
remain intact; no whole-experiment or arbitrary-timestep accuracy is claimed.
The earlier separate coarse passive accuracy failures remain untouched.

Receipt: `/mnt/workspaces/Cells/physiology-tissue-loop-tests-20261030-01/result.json`,
SHA256 `39adccc099ae17cd10fabb5ff7b10fa3f388cae16698de4bafa4b034452acbab`.
Phases took 52.66 / 209.83 / 151.96 s, peak RSS 311877632 / 246542336 / 90005504 B;
host reserve remained above 21 GB. All captured sources and three current worker
files stayed exact. Full frozen hashes and all 24 protected dependencies are in
`physiology_tissue_loop_workqueue.json`.

Chief separately reports 80/80 public checkpoint checks (34 new, 46 retained),
179.3 s, pinned to this frozen core:
`/mnt/workspaces/Cells/physiology-tissue-loop-checkpoint-20261030-01/completion-verification.json`.
Those association/restart/publication checks add no trajectory accuracy credit.
No shared-file change, long job, GPU action, follow-up audit/regression or active
campaign query was performed by this worker.
