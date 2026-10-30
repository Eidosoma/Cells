# Native lifecycle after clipping

This separate package continues the exact clipped/rebuilt source state through
the rest of `DECMesh.clip_and_refine`: optional smoothing, optional refinement
and final exterior-derivative operators. The seven new transcriptions preserve
the source formulas, call order, coordinate updates and pseudoinverse defaults.
The original class closure has 26 methods and 20 helper registry entries.
Clipping production code and the earlier native-exact geometry primitives
remain unchanged.

The original `make_voronoi` caller fixes smoothing to `None` and boundary fixing
to `True`. Trials changing either use an explicit manufactured native-API
declaration. Public input remains bounded to 32 source point occurrences and
25 refinement steps, with the caller's false auxiliary flag. A manufactured
topology helper covers direct auxiliary operators without widening that input.

Source details matter here: zero smoothing still rebuilds and solves; a final
rebuild follows refinement even with zero steps; only the convergence branch
stores mesh quality. Rebuilds retain stale operators until the source replaces
them. IDs stay attached to moving slots and follow exact later deletion
indices. The harness records these transitions, raw local matrices, partial
failures, array layouts and the complete RNG state without cleaning the cache.
Replay must reproduce the owned clipping cache, IDs and RNG before continuing.

Independent checks use Decimal 100/160 and exact Fraction assembly on supplied
rounded geometry and topology. Grounded graph incidence uses a gauge-fixed
Laplacian solve; constant matrices use an exact rank formula; bounded full-rank
square matrices use elimination with a conservative rank-gap bound. A source
pin authenticates NumPy's default `rcond=1e-15`. Unsupported or unresolved
rank domains fail their declared checks; the reference does not imitate SVD.
Additional checks cover Moore-Penrose identities, incidence entries, smoothing
coordinates, quality, energy and refinement copies. Existing coordinate,
area and dimensionless budgets remain fixed. Source branch selection is kept
separate from independent arithmetic diagnostics.

The 39 declared checks include 16 complete candidate pipelines, eight algebra
helpers, two raw failures, five control refusals, four resealed-input refusals
and four ancillary checks. Actual and native buffers precede completion and
accuracy assertions. Branch coverage requires saved observed traces; isolated
helpers provide only their declared boundary coverage.

The initial preparation's 19/22 accuracy qualification remains open. This
package neither repairs that failure nor qualifies upstream clipping,
topology, physical cell geometry or a stable arithmetic path. The protocol
records the source boundary and rank argument because either an unnoticed
cache cleanup or a mistaken SVD cutoff would invalidate numerical comparisons.
Only source hashes, AST comparisons, compile-without-execution and Ruff are
permitted during this preparation. Chief coordinates qualification and review.
No scientific imports, fixture generation, pytest collection or numerical work
is performed here.

The guarded package prepares the same 39 exact test IDs in separate processes,
26 native replay cases, 26 reference records and two independent reference
domains. A separate guarded finalizer verifies runtime provenance, counts and
observed coverage. Every unit keeps the established 480-second, 1-GiB summed
RSS and 8-GiB host-reserve limits. Process isolation releases rich traces between
cases; no whole-run collection retains raw actual/native JSON. Native replay
releases the actual record before loading the saved native record. Reference
replay decodes typed payloads one at a time. The controller streams file hashes
and accepts only bounded metadata; full source traces stay in guarded workers.

The controller uses 13 unchanged resource/metadata definitions extracted from
the established runner and sampler. Their source map authenticates exact ASTs.
This avoids importing the original runner's model/CLI dependency graph in the
supervisor. Numerical and finalization paths retain the same live guard,
failure receipts and child cleanup. On a numerical failure, only guarded
partial evidence finalization follows. Observed pipeline coverage remains
separate from manufactured helper and ancillary coverage. Root accepted the
clipping continuation; the earlier 19/22 primitive limitation remains open.
The larger lifecycle run is expected to require a detached launch. Its gate
stays false until Chief schedules qualification.

The prepared outer supervisor additionally bounds the whole process tree to
2 GiB and two hours, including setup and finalization. Individual workers retain
their 1 GiB and 480-second limits. Root starts the supervisor detached and
reviews its durable result when the user requests a status check.
