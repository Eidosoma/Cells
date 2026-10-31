# Retained mesh failure diagnosis and corrected incidence candidate

This prefix preserves the original failed native reproduction and stable
initial-mesh panel. The latter remains **0/9 complete physical geometries**,
with two separately preserved raw source failures. No original failure is
reclassified. The new saved-data diagnosis reads authenticated JSON/NPZ using
only the standard library, counts integer owner relationships and quotes the
previous independent geometric verdicts. It evaluates no native, candidate,
reference, metric, solver or new mesh-generation routine.

The native `create_mappings` builds a nearest-neighbor tree on directed primal
edge endpoint indices. It queries only `(vi,vj)` and keeps exact zero-distance
matches. The opposite orientation is omitted. Across the nine saved meshes,
216 of 360 face-edge occurrences survive; all 144 missing occurrences are
reverse orientations. The original vertex-to-edge map happens to remain unique
because each original directed edge survives once. Simply accepting reverse
edges and appending endpoints per face would duplicate interior vertex entries.

| Saved case | Omitted reverse incidences | Selected dual pairing mismatches | Missing owner-pair interfaces | Boundary indices outside selected axis |
|---|---:|---:|---:|---:|
| irregular-centroid-aux | 10 | 2 | 0 | 2 |
| irregular-circumcenter-aux | 10 | 2 | 2 | 4 |
| native-single-preset-seed17 | 6 | 0 | 0 | 1 |
| native-single-preset-seed23 | 6 | 0 | 0 | 2 |
| caller-square-zero | 12 | 0 | 0 | 4 |
| caller-square-disordered | 27 | 7 | 2 | 4 |
| caller-hex-disordered | 61 | 5 | 0 | 8 |
| caller-single-square-cache | 6 | 0 | 0 | 1 |
| caller-single-hex-cache | 6 | 0 | 0 | 2 |

Pairing mismatches compare saved selected dual-edge IDs with the actual dual
polygon owners; they are integer observations, not newly computed geometric
errors. Two cases lack interfaces under that lookup. Existing recorded geometry
also identifies overlaps, nonmanifold/shared-direction boundaries and quad
metric defects in the circumcenter and disordered cases. Missing interfaces are
not replaced with a nearby edge. The centroid case has two recorded pairing
errors without recorded polygon-complex defects; a unique owner-pair association
is a justified candidate correction there, pending independent execution.

Native `process_voredges` makes boundary flags on its complete dual-edge set,
then overwrites the edge/metric arrays with a smaller primal-aligned nearest
midpoint selection. It does not remap the flags. All nine saved caches contain
boundary indices beyond the final selected array. This is a stored-axis
inconsistency; the audited mesh source only stores that flag and does not read
it later, so it is not evidence of an observed ordinary-loop crash.

The separate opted-in adapter keeps source seed occurrence IDs, vertex
coordinates, polygon rows and primal edge order. It rebuilds signed face/edge
incidence by undirected endpoint identity and derives unique vertex incidence
directly from edge endpoints. It represents every dual polygon edge on a full
axis, resolves exactly one shared dual interface per primal owner pair, and
records both directions of the full/selected mapping. Selected orientation is
the reverse traversal of primal owner-a's CCW polygon, with geometric
handedness explicitly left for independent checking. Integer primal and full
dual boundary-of-boundary identities are checked. This differs from native
mapping and nearest-midpoint behavior; no native-equivalence claim is made.

The proposed physical owner plan follows native `Cells.cellVerts`: local
membrane `i` is polygon edge `(i-1,i)`, with source polygon order retained.
Internal partner occurrences derive from the shared unscaled dual edge.
Boundary partners remain `None`; no self-partner, no-flux or tissue profile
policy is silently filled. The owner plan is not a scaled physical cell cache.

Every metric, inverse operator and downstream physical/field binding is
invalidated for reuse. The candidate contains integer incidence only: no
pseudoinverse, edge length, tangent, area, centroid, physical volume, grid map or
Poisson solver is newly calculated during preparation. The ordinary native
auxiliary incidence routine already checks both primal edge directions;
its signed operators must be distinguished from the directed-only mapping
defect, and compared prospectively rather than declared numerically failed.

Native physical preparation requires a separate reached chain: `cell_index`,
`cellVerts`, `cellMatrices`, `cell_vols`, membrane processing/neighbors, ECM grid
and environment preparation, boundary inverses, profiles and gap reconstruction,
then the graph operators and simulator initialization. The source map records
each method's actual parameter reads, attribute bindings, body and AST hash.
The mesh's unscaled Voronoi area and final physical cell volume are different
owners: `cell_index` initially uses mesh area times height, while `cell_vols`
overwrites volume by summing membrane pie volumes after cell scaling. The
loader's `scale_cell=0.99` comment says drawing, but reached cell vertices and
membrane measures use it; the comment does not override those operations.
Native membrane vectors also have six columns (midpoint, normal, tangent),
while the bounded manufactured field capture supplies four. Any future adapter
must authenticate the needed columns without rewriting the original owner.

Six cases are prospective topology candidates, not passes. The other three
complete cases have known missing/nonmanifold ownership or geometric defects;
the adapter must refuse unresolved ownership and retain partial evidence. Raw
source failures remain inadmissible. The prepared 32-check panel covers those
cases, missing/changed owners, explicit physical refusal and eight changed-output
controls. Fourteen proposed fresh independent workers use exhaustive incidence
scans and the existing exact integer polygon-complex checker on actual saved
coordinates. They check orientation, both operator chains, axis maps and
physical owner occurrences. No new metric tolerance or independent accuracy
claim is introduced. A passing future topology check would still leave metric,
inverse, physical-cell and initialized-loop validation outstanding.

Tests persist their declaration before loading/binding and retain full incoming
requests, candidates, worker inputs/reports and exception/partial records at
every later stage. The existing immutable original JSON/NPZ and failed review
remain linked and copied into the new freeze. Stable primitive and conditional
mesh-lifecycle evidence are reused as separate evidence, without inheriting
whole-mesh qualification. Chief owns review, launch/finalization and progress;
no scientific imports, fixtures, collection, GPU/job activity, polling, shared
component edits or `PROGRESS.md` changes are part of this preparation.
