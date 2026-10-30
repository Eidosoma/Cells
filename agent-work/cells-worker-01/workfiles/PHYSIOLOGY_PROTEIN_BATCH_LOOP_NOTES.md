# Complete charged physiological batch loops

Chief requests homogeneous independent worlds on the existing qualified CPU
solver. New physiology_protein_batch_loop files own only cohort orchestration,
the actual-packet bridge, immutable world histories and durable restart/journals.
Existing loop, schedule/calendar, component, field and persistence sources stay
frozen. No device/fused loop, new noise-driving/heat law or changed tolerances.

Each world owns its full spec/binding, ProteinLoopCheckpoint, complete initial/
current component tape, native calendar, physical-grid cursor, decimal work/
electrode ledgers and history lineage. Batch names and native world labels never
seed RNGs. Require one engine/version, spec, physical binding and nominal dt per
cohort, with unique world names and stream/world owners; clocks can differ after
isolated refusals. Reordering/partitioning must preserve each named world.

1. Frozen loop.propose validates the exact parent, stages its original schedule,
   evolves every charged ionic interval on EventGrid with held permeability,
   checks RK/domain/material/charge/energy, and only then draws the original
   post-ion component once. Preserve all raw intervals, failed trials and tapes.
2. Caller supplies each explicit DrivingBudget. Frozen loop.accept performs
   deterministic ionic replay, prescribed-packet/component/field replay, local
   energy admission and origin-to-current conservation with exact decimal work
   and electrode ledgers under the unchanged global tolerance.
3. Encode the actual staged source and already-produced packet/successor into
   the frozen provider numeric contract, without sampling. Use the actual last
   ionic state, exact endpoint control/runtime/charge offsets and original
   before/after field readouts for the complete component commit gate. Strict
   host decoding must equal the candidate loop component bit-for-bit. Both
   admissions must pass before publishing the entire candidate checkpoint.

On any failure return the identical parent world/checkpoint, preserving its
ionic buffers, component/RNG/clocks, schedule, decimal ledgers and lineage.
Keep the raw proposal/rejection, candidate receipt if available and bridge
failure in the attempt journal. Successful neighbors continue independently.
Multi-loop runs retire a failed world for that run; no implicit retry.

Durable per-world restart reuses the frozen complete-loop checkpoint codec.
Manifest-last batch publication stores every world's base/current checkpoint,
ordered accepted history and full numeric attempt archives, including failures.
Restore validates sources/runtime, hashes, complete fields and history chains
without drawing. Explicit history replay is a separate caller action that
recreates real proposals/tapes from saved sources and compares full receipts.

Qualification will cover repeated full loops for all four ordinary families,
both engines, enabled/disabled/zero worlds, real stream continuation, native
calendar labels versus physical intervals, reorder/partition, failure isolation,
stale/cross-world inputs, restart and independent carried full-state references
at the existing two integration tolerances. Preserve Python/JAX/jaxlib/NumPy
versions and measured child affinity. CPU7, one thread,480s/phase,1GiB tree RSS,
>=8GiB reserve. Expected >=10min full qualification launches detached with
durable logs/result/failure and returns control; no automatic status polling.

Detailed bounded plan is in `physiology_protein_batch_loop_workqueue.json`:
79 checks,30 named world histories,84 complete charged-loop endpoints, exact
serial comparisons and60 independent answers at two tolerances plus two failed
provider replays. Heavy cases continue through complete round-boundary restart
in separate processes. Full raw proposal/attempt/serial archives precede test
assertions. Host Controls use the frozen checkpoint codec's scalar value
representation; typed numeric states, actual tapes and cache bits remain exact.
