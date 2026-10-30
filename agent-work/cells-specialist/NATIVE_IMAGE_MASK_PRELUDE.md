# Native image mask and make_voronoi prelude

The initial preparation and review repairs were static. Chief authorized the
bounded qualification after reviewing preparation02. Its outcome belongs to
the preparation plan and run artifacts. Shared project status and all ECM work
remain Root-owned. No native mesh computation belongs to this stage.

`betse_image_mask_prelude` captures an actual declared image file into immutable
bytes and a decoded float32 bitmap. Relative names use the configuration
directory; absolute names are retained. Content hashes, lexical and resolved
paths, original mode and Pillow version remain explicit. A later live-file
change cannot replace already owned input. Callers cannot supply pixels or a
world-window override. The window comes from the full lattice state, including
its radius-expanded extrema. The upstream lattice02 result is preserved
separately; this package makes no further lattice or B09 coverage claim.

The original source first creates the mask for every make_voronoi branch,
including single_cell. Pillow converts to F; the code has no explicit alpha
rejection. Every grayscale value unequal to 255 is active, including near-white
254. The binary matrix is flipped vertically before spatial interpolation. Its
coordinates describe pixel centres across the seed bounds. Active pixel IDs
map back to the original file rows. The image convex hull and the binary mask
remain distinct: the hull does not preserve interior holes.

The linear helper builds `RectBivariateSpline(x,y,mask.T,kx=1,ky=1)` and
transposes query results. The fast helper builds an untransposed spline with
native defaults. These are intentionally distinct. Cubic-size failures occur
before hull creation; empty and collinear active pixels fail at the hull. The
paired selection loop preserves zip truncation and the exact `!=0` predicate.
No tiny-value clipping or tolerance is propagated into selected indices.

Only after image construction does the source choose mesh arguments. Single
cell receives the lattice centroid, no seed cloud, noise0.1, six sides and
disabled alpha/merge. The non-SVG lattice branch forwards all seed occurrences,
including duplicate bbox corners, noise0.5, merge/close0.1 and the declared
alpha/centroid controls. HEX maps to `tri`, SQUARE to `rect`. Every native
constructor receives `image_mask=None`. The subsequent lattice
`clip_and_refine(mask)` first calls `pre_mesh()` and only then applies the
image through `clip_to_curve`. This package never prefilters lattice seeds.
It records those calls and forwards the complete post-lattice MT state; it
does not execute a mesh constructor, initial triangulation, alpha/close-point
filter, merge, clipping, refinement or operators. Single-cell generator draws
remain a later authenticated stage.

The isolated native provider authenticates eleven original files and sixteen
captured AST sites, including the native type_check function. Two additional
mesh methods are mapped for static ordering evidence only. Original function and class
method bodies are retained with postponed annotations. The picker nominal base
is replaced with object; import-hook/inheritance validation is outside this
normalized boundary. Existing regular-file path dependencies are supplied
explicitly. A mesh argument recorder stops before any native mesh computation.
Raw source arrays and original layouts are retained, including failed images.

The prepared panel has 28 checks: sixteen image/lattice/single-cell combinations,
four raw image failures and eight ownership/tampering/override/zip checks.
Native comparison includes all spline knots/coefficients and source hull order.
Independent P5-byte decoding, Decimal100/160 grids, monotone-chain image hulls
and manual bilinear queries cover the declared grayscale fixtures inside the
closed source window. Non-PGM decoder conversions, outside-window behavior and
independent fast-cubic interpolation are outside this reference. Fast-cubic
construction is checked against original native arrays only. The proposed
dimensionless linear budget is `2e-14+6e-12*abs(reference)`; coordinates reuse
the B09 budget. Chief must review that bounded scope before qualification.
Both reference buffers, actual values and raw file bytes precede comparisons.
Fresh native/reference replay scripts deny Cells, BETSE and JAX imports.

The second static preparation addresses review gaps without a numerical run.
All sixteen positive cases include swapped off-diagonal interior query pairs.
The asymmetric fixture changes one pixel so that its vertically flipped mask
also remains asymmetric; an independent response check exposes a transposed
linear field. The twenty-eight test IDs and numerical budgets remain unchanged.
Unexpected positive capture/prepare refusals now retain the actual exception
trial as typed numeric columns and separate raw bytes before re-raising.
The original preparation receipt is preserved.

Inputs, resource limits and qualification evidence belong to
`betse_image_mask_prelude_preparation_plan.json`. No full make_world or
biological geometry claim is made.
