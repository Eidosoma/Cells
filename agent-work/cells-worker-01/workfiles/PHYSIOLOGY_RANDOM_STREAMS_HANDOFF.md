# B14 physiological stream ownership

The new `src/cells/core/physiology_random_streams.py` and its unit tests pass
50 short CPU checks. The machine-readable source hashes, receipt and resource
record are in `physiology_random_streams_workqueue.json`. The qualified
`src/cells/processes/betse_perturbations.py` remains byte-identical. Chief owns
the separate complete-snapshot wrapper and PROGRESS.md.

`PhysiologyRandomStream` has five frozen, slotted fields: `stream_id`,
`world_id`, `next_tick`, `layout_identity`, `rng`. The RNG is exactly the existing
`NativeStream` or `StableCoordinates`. The public functions are:

- `new_stream(binding, rng, *, stream_id, world_id, next_tick=0)`
- `draw(stream, binding, *, site, enabled=True) -> (packet_or_None, next_stream)`
- `stream_record(stream)`
- `restore_stream(record, binding)`
- `rebind_stream(stream, old_binding, new_binding)`

One global uint64 next tick advances once for each enabled call, across all
four qualified sites. Disabled calls return `(None, original_stream)` without
sampling or touching the native Gaussian cache. Effect amplitude is outside
this API: a caller must still draw when a source-enabled call has zero physical
effect. Site guards, phase timing, source-disabled microtubule status, solver
integration and physical state changes remain caller-owned. At UINT64_MAX an
enabled request refuses before sampling because its increment cannot be
represented; a disabled request and record round trip remain valid there.

The record has exactly `kind`, `law_id`, `stream_id`, `world_id`, `next_tick`,
`layout_identity`, `rng`, `identity`. Kind is
`cells.physiology_random_stream@1`. Identity is the canonical sorted compact
JSON SHA256 of every other field. The native nested RNG uses the existing
complete MT19937 manifest, including all624 words, position, Gaussian cache,
NumPy version and native identity. The stable nested RNG has `rng_id`, `seed`,
`world_id`; its world must match the stream's explicit world. Restore checks
the exact field sets, law, hashes, counters, RNG internals and binding identity.
These hashes detect changes; they do not authenticate authorship.

`stream_id` labels ownership and does not salt either existing RNG law. Native
world IDs also label ownership: the caller supplies independently initialized
native states when it needs independent worlds. Cloning the same native state
under two labels deliberately replays the same tape. Stable sampling retains
the already-qualified seed/world64/tick64/site/owner-token law unchanged.

Draw and restore reject stale/foreign layouts. Explicit rebind permits only
surviving cell, membrane, environment and ion IDs and preserves each surviving
membrane's old cell/environment owner. It retains the exact RNG/cache, world,
stream ID and next tick, changing only layout identity. Geometry validation and
physical state remapping belong to the cut/checkpoint owner. Boundary weights
or ordering may change explicitly with the new valid binding. Native sequential
draws can then change because their order/count changed; there is no native
subset-invariance claim. Stable surviving membrane coordinates retain their
qualified subset behavior; a changed boundary categorical law is explicit.

The50 checks include exact five-site-call native tape correspondence across a
shared high uint64 counter, cached-Gaussian JSON restart, unchanged process-global
NumPy RNG, zero-level static permeability with an enabled draw, disabled-site
sampler traps, full-width stable world/tick/site separation, stable survivors,
native rebind correspondence, immutable records, overflow boundaries and
rehashed invalid/foreign owner/world/cache/version records. They add no new RNG
distribution or coupled physiological claim. Original backend/version limits
of the qualified samplers continue to apply.

Completed evidence:
`/mnt/workspaces/Cells/physiology-random-streams-tests-20261029-01/result.json`,
SHA256 `76584cc859a113caf84a1f33ffb298d93944a2a64d0aaa8f0a415ff194454675`.
The bounded check used CPU7/one thread, no GPU/JIT/persistent compilation cache,
180s wall allowance,1GiB child-tree RSS and8GiB host reserve. It completed in
4.53s with257,376,256B sampled peak RSS. No long run or active-job polling ran.
