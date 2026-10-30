# Native image clipping and centroid rebuild preparation

This separate-prefix package is implemented statically, with 31 candidate
checks prepared and unrun. No scientific module was imported, fixture created,
test collected, native body executed or mesh computed during preparation.
Chief owns launch/review and shared status. Initial mesh qualification remains
open after its 19/22 campaign; its failed evidence and tolerances are untouched.

Inputs are an owned complete finite initial source trial and its original owned
image prelude, restricted to the multi-cell, non-SVG caller. This admits a
source continuation, without admitting independently qualified topology or
physical geometry. The source constructor/initial pre_mesh is replayed locally
and checked exactly against the input trial, preserving array layouts and
mutable internal alias relationships before continuation. No caller polygon,
coordinate, image window or mask override is accepted.

The native clipping procedure differs from a general mask intersection:

- The all-vertices branch keeps the cell even if its centre has zero mask
  value. The partial branch requires both a nonzero centre and a mixture of
  zero/nonzero vertex values. Cells with all zero vertices are discarded.
- Partial polygons are clipped to the convex active-pixel hull. Subsequent
  point-cloud searches retain matched old polygon points. The second search
  assigns its matched result to `throw_away_pts` and its unmatched complement
  to `keeper_pts`: hull-matching new vertices are discarded, while unmatched
  new intersections are kept. The strict distance
  predicate is `distance < 1e-15 m`. Duplicate matches remain separate, and
  an empty point cloud yields two empty lists in the original implementation.
- The retained polygons are local intermediates. Their centroids become a new
  seed array, the image is installed, and `pre_mesh` rebuilds the mesh. Its
  alpha stage now tests circumcentres against the image. Final polygons are
  therefore not asserted to be the exact clipped intermediates. An empty seed
  list retains the source `(0,)` array shape and any subsequent failure.

Each emitted centroid has its parent-cell occurrence ID, in source loop order.
The following rebuild carries those derived IDs through exact source deletion
indices. Identity is never recovered through nearest-coordinate matching.
Typed immutable snapshots retain original layouts, object/ragged contents,
every mask query, cell/half-plane/search/intersection locals, emitted polygons,
centroid seeds and raw failure prefixes. A live image-mask instance is replaced
only in serialized caches by an owned grid/curve token; no native object is
exposed. RNG continuation is complete and clipping introduces no random draws.

The attributed private kernel transcribes two new mesh methods and thirteen
geometry/validation/conversion helpers. The native oracle authenticates
eighteen BETSE files, executes the original AST bodies and original linear
interpolator, and records equivalent traces independently. Existing mask/grid
generation is reused as an explicit input law. Its native exception names and
messages have local proxy classes; private metadata/import bindings are
declared in the source map. The initial mesh files and active campaign were
not changed.

Independent diagnostics use Decimal100/160 formulas and exact binary-input
rational predicates. Convex intersection candidates come from all line pairs
and closed half-plane filtering, separately from the native edge-by-edge
algorithm. Source polygons/topology remain inputs. General polygon measures
remain distinct from the native cyclic-quad formulas. Exact side/nonzero
predicate disagreements are retained without changing source predicates or
claiming universal selection correctness.

The existing independent image law covers queries inside the closed image
window. Clipping and rebuild queries can lie outside it; those values receive
native comparison only. No extrapolation or clamping rule is invented, and no
continuous error allowance enters a selection predicate. The proposed
coordinate/area/linear budgets are unchanged. Assertions on new geometry start
at clipping; upstream primitive diagnostics are retained as unqualified inputs,
with no new initial-mesh qualification credit.

The candidate panel has twelve mesh cases (two lattices, three images, centroid
and circumcentre choices), seven isolated manufactured helper witnesses, two raw
helper failures, four resealed-input refusals, two ownership/scope checks and
four reference coefficient-domain checks.
Returned states and rejected trials are saved before expectations, as are native
and primary/refined reference buffers. Unexpected completions in raw cases are
retained. Case outcomes are not yet known and failures will not be relabelled.
The seventh helper witness explicitly checks the keeper/complement assignment
before any source-branch qualification credit. The original 26-check static
receipt and its source/docs are preserved in a read-only predecessor archive;
the successor changes this wording and the witness, with native kernel/math
unchanged. The clipping reference now validates captured float/int coefficients
as exact 0/1 values and converts them to integers before calling the unchanged
qualified Decimal bilinear helper. A mixed float/int witness and three invalid
coefficient refusals cover that boundary; no tolerance or source predicate is
changed.

Chief's initial mesh review reports exact actual/native captures but three
overbudget scalars: square centroid x and hex circumradius/inradius. The merged
B09 case was refused by the physical adapter. That failed campaign remains
frozen. Chief is handling the newly authorized saved-input conditioning
diagnostics; this package does not duplicate them, widen budgets or weaken the
physical adapter. A guarded clipping runner/fresh replay and a numerical launch
have not been prepared or authorized. Scope/fixture review and the upstream
conditioning limitation remain concrete preflight items.

The guarded CPU6 controller and fresh native/reference replays are now prepared
for static preflight. The numerical gate stays false. Frozen inputs include
exact31-check IDs, the21 mesh/helper case IDs, four source-AST-derived reference
domains and all predecessor/failure receipts. Runtime files and raw outcomes
are retained before comparison; root result manifests include nested receipts.
Observed partial/all-discarded branch counts come from actual typed traces on
success or failure. An isolated keeper witness supplies no whole partial-clip
case credit, and declared cases guarantee no branch coverage. Root reports the
saved-input centroid/Heron diagnosis complete; native-exact code stays unchanged,
and any stable path requires separate version/domain qualification.
