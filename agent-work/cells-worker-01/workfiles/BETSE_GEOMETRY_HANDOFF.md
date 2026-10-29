# Native geometry and operator binding

Cells Key Developer, B09/B13 handoff, 2026-10-29. Seven scientific files and
qualified evidence are frozen. Chief owns shared models, active-physiology cuts,
solver continuation, evolving geometry and checkpoint integration.

Complete receipt:
`/mnt/workspaces/Cells/betse-geometry-development-20261029-03/result.json`, SHA256
`cbc165a2a899d30136ce3c78224ebec3e9acab9ce11ed08de680a7cd81b6a46f`.
Process `src/cells/processes/betse_geometry.py`, SHA256
`18a082cd09acc817707ba775196666c446b439c5b254a04e36f0b49157b46dff`.
Law ID `betse_geometry_source_v1_5_0@1`.

## Generation, provenance and stable owners

The native child executes actual imported `DECMesh`, `Cells` and
`FiniteDiffSolver` classes from authenticated installed BETSE 1.5.0, revision
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. Eight source modules match the
pinned checkout and are copied into external evidence. Native NumPy/SciPy are
2.5.3/1.18.1. No production Cells or JAX is imported in that child.

Inputs are explicit staggered/irregular point clouds or the actual seeded
`make_single_cell_points` method, with parameters, initial points and complete
NumPy RNG states retained. Generation executes `init_mesh`, then actual
cell indexing/shrink/matrices/patch-volume/contact/neighbor/GJ-vector/ECM/grid/
graph-Laplacian construction. The pinned empty `Cells.__init__` body contains
only `pass`; object allocation bypasses its package-level beartype check because
parameters are normalized explicit attributes, rather than a loaded Parameters
configuration. No mathematical construction or operator method is replaced.
No YAML, SVG/image lattice clipping, full `make_world`, refinement-iteration
algorithm, solver loop or cut is claimed. The spatial panels compare generated
meshes with different explicit spacings.

The source "single cell" point preset constructs a ring plus centre: the
captured downstream geometry has seven owners. The captures do not relabel that
as one biological cell. Native close-point removal may silently delete seeds;
the duplicate panel deletes both explicit coincident owners. Exports retain
original, retained and removed stable IDs. Coordinate equality establishes seed
provenance only within this one captured generation. It is not cross-generation
stable-ID matching or physical state migration. Production consumes no RNG.

`MeshSpec` declares cell/primal-vertex IDs, paired edge IDs, face IDs, dual-vertex
IDs, ordered point arrays, oriented edges and CCW faces/cells. Primal point
coordinates are seed positions. Cell-centroid coordinates are centroids of the
dual polygons; the two coordinate fields generally differ despite sharing cell
owners. Every dual control measure has an explicit reference-face owner.
Original/removed seed IDs must partition retained owners. Names/axes/order are
explicit; no ID, edge pairing, orientation, closest contact or geometry is
inferred by the binder.

`bind_mesh` copies and freezes inputs, checks finite positive measures, unique
coordinates/IDs, face orientation and complete primal boundaries, then computes
incidence, metric and inverse matrices. It allows an explicitly composed
disconnected topology and records one compatibility/gauge component per graph.
That composition is qualified as topology binding, not native Delaunay
generation of disconnected tissue. Configured dense bounds are 256 primal
owners, 1024 dual vertices, 1536 paired edges, 1024 environment sites; actual
native qualification reaches 81 primal owners, 215 edges, 160 dual vertices and
256 environment sites. Larger capacity is not a performance qualification.

## Measures, contacts and environment

`bind_geometry(GeometrySpec(...))` consumes mesh/grid bindings, explicit ordered
per-cell membrane IDs, reciprocal partner IDs, boundary IDs, cell/membrane to
environment owners, height, gap and shrink factor. Positive height/gap and
0<shrink<1 are required. It recomputes shrunk polygons, edges, midpoints,
outward normals, tangents, areas, owner sums and circumference derivatives.
Global membrane order may differ from per-cell CCW order. Contact partners must
be reciprocal, cross distinct cell owners, have equal areas and opposed normals.
Physical membrane contacts and primal field edges are separate declarations.

Native membrane area is edge length*height. Native patch volume is
`0.5*norm(midpoint-cell_centroid)*area`, not perpendicular polygon height.
The kernel exposes `native_patch_volume_m3`, their summed
`native_cell_volume_m3`, and independently calculated
`polygon_cell_volume_m3`. In the irregular centroid panel the maximum relative
difference is **0.3411363810**. The pre-shrink `vor_sa` remains the source DEC
control area, and its initial height-multiplied volume is later replaced by the
native patch sum. These measures must not be silently interchanged.

Native dual edges are associated to primal edges by a nearest-midpoint search.
Centroid duals need not be orthogonal. The `tri_sa_o` measure repeats a reference
primal face's area at each dual vertex, including boundary reflections. Its
explicit reference-face candidates/selection are captured and validated; it is
not a claim that these values partition physical space.

`bind_grid(GridSpec(...))` validates explicit C-order ny,nx, bounds, coordinates,
uniform delta, IDs and all N/S/E/W flux/value labels. Native grid construction
truncates integer dimensions; the nonintegral aspect panel succeeds upstream
with inconsistent coordinate spacing and declared delta. Supported binding
rejects that case. Native nearest environment owner maps are explicit inputs;
ties remain explicitly resolved source choices. Geometric validation accepts
the declared nearest owner, including a tied minimum, without choosing a new ID.

Uniform environment volume is delta^2*height. The separate native weighting is
surface_area_at_site*gap/2 at occupied sites, uniform volume elsewhere. Both
arrays are named explicitly. No claim follows that the latter is an exact
physical extracellular volume or a conservative moving material partition.

## Operators and boundary/gauge choices

All operator calls require explicit domains and policies. Scalar fields use a
final owner axis; membrane vectors use [...,M,2]. Leading world axes broadcast.
`field_valid` checks finite shape/dtype ownership; signed flux/field values are
valid. Compiled frozen bindings establish semantic ownership. Raw numerical
arrays or direct dataclass construction do not establish a trusted binding.

`edge_gradient(...,domain='primal'|'dual')` is D0/edge_length, an edge-directional
derivative. `mesh_divergence` and `mesh_laplacian` take the same domain and
`boundary='closed'|'interior_rows'`. Closed is native btype2:
`-area^-1*D0.T*dual_length*flux`. It has component constants in its nullspace,
area-weighted conservation and the tested negative-adjoint identity. Primal
face incidence satisfies D1*D0=0 exactly.

**Do not assume a complete dual complex.** Native nearest-midpoint edge pairing
can omit edges in a dual polygon's walk. `missing_dual_face_steps` records every
omission, and auxiliary `dual_d1`/interior-row operators preserve source skipped
entries. The irregular centroid panel has one omitted walk step; its
circumcentre counterpart has two. These paths have source correspondence, not
a general dual-chain/conservation or continuum guarantee. Native btype1 sets
boundary output rows to zero; it does not impose a potential boundary value on
the input. Default native world construction requests core operators only.
Dual/interior-row helpers reject that core-only mode rather than inventing
missing auxiliary matrices.

`source_xy_gradient` preserves literal native grad_xy mixing, with explicit
interpolation. Its name does not certify a Cartesian gradient. The edge
directional derivative is the qualified affine/directional operation; no
general centroid-dual continuum Laplacian convergence is claimed.

`source_factorized_inverse` preserves the native product of incidence
pseudoinverses and metric factors. **It is not generally a right inverse of the
assembled Laplacian.** The irregular centroid compatible-source panel has
relative residual **0.3108126850**. The separate Cells `density_poisson` uses the
assembled density operator's pseudoinverse; its panel residual is
**3.8117645620e-15**, mean potential **7.4014868308e-17**. Call
`density_rhs_valid` first: each connected component must have area-weighted
zero-sum source within 2e-12 relative tolerance. Potential gauge is arithmetic
zero mean per component. Global balance alone fails for disconnected owners.
No physical incompatible source is silently accepted/projected.

Environment source stencils use missing-neighbor flux rows, or identity/delta^2
value rows. Corners use SW=South, NW=North, SE=East, NE=East, even when adjacent
labels differ. Value-row RHS must be scaled consistently by the caller.
`environment_poisson(...,convention='native')` uses the actual default-SVD source
matrix and retains its numerical nullspace defects. In this pinned environment,
8x8/16x16 all-flux panels show native inverse residuals
**0.00142130547 / 0.000764451496**, means
**0.0723686218 / -0.00202944875**, despite compatible input. Matrix/diagnostic
captures preserve those failures; no stable gauge is promised for that choice.

`convention='compatible_gauge'` is a separate Cells solve with the explicitly
known constant nullspace removed, or an ordinary inverse of the effective fixed
value-row system. Call `environment_rhs_valid` first. All-flux sources must have
zero arithmetic sum within 2e-12 relative tolerance, and potential mean is zero.
The same panels have residuals **2.6978338325e-15 / 5.3230009756e-15**. This is
an explicit solver convention, not a repair claimed as native parity.

`cell_gradient(...,domain='cell')` uses declared neighbour centroids, returning
the scalar membrane derivative and its source-normal vector. `cell_mean`
requires cell or membrane ownership. `cell_divergence` requires a boundary flag
and `volume_policy='native_radial'|'polygon'`; `circumference_gradient` requires
membrane ownership. `surface_integrals(...,domain='cell'|'environment')` maps
area-weighted signed normal fluxes to owners. Equal/opposite cell/environment
integrals and reciprocal contact cancellation are tested for both volume
choices. These are operator identities, without evolving amounts or asserting
an energy/material model. The separate source membrane-normal helper wrongly
uses Sx for the membrane y component; its failure is retained, and that helper
is not used to claim vector projection parity.

## Integration and checkpoint boundary

`geometry_manifest` carries law/layout identities, stable owner maps, occurrence
order and provenance; `validate_geometry_manifest` rejects stale data, including
JSON round trips. The binding identity includes coordinates, measures, operators,
policies and generation provenance. This is identity metadata, not a serialized
geometry/state/checkpoint format. Persist full specs, generation inputs/RNG,
explicit maps, runtime pins and physical state independently. A new geometry
requires new binding and a separately authorized physical amount/charge remap.

The interface check binds actual captured data to the frozen profile Layout,
cut Topology and deformation operator constructor without changing those files
or running cuts/deformation. For the frozen deformation binder only, the native
-1 m self-boundary length sentinel is explicitly replaced with 1 m on rows whose
potential difference is identically zero. This preserves numerical operators;
it does not assign a physical boundary distance. Actual active-physiology cut
integration remains Chief-owned. Prior cut/deformation/profile receipt and
source hashes are verified and copied by the metadata-only finalizer.

## Qualified evidence and retained failures

The complete component has **66 tests: 62 host and four CPU JAX**, no skips,
source drift or failures, plus **12 actual native geometries, four native grids,
12 retained degeneration/operator limitations**. Independent stdlib reference
loops cover polygons, ordered owners/contacts, incidence, graph/stencil
arithmetic and pivoted gauge elimination. Native-generated topology is explicit
input; the reference does not independently implement Delaunay generation.

Native directional sine differences at maximum edge spacings
13.21449896/6.60724948/3.30362474 um have RMS relative errors
0.02017097869/0.00506780928/0.00126871731, orders **1.99284695/1.99799158**.
All-flux environment cosine-mode errors at 4/8/16 are
0.05035879645/0.01278516923/0.00320863596, orders **1.97777255/1.99443924**.
These are directional-difference and uniform-grid stencil refinement panels,
not full-tissue or general irregular DEC convergence claims.

JAX compiles batched geometry/auxiliary/grid operators, conservative transfers,
invalid-world isolation and compatible solves. Repeated static solves are
exactly equal; this is not trajectory restart. Incidence and area-weighted
transfer derivatives match declared analytical matrices. No physical geometry
differentiation, mechanical energy, cellular amount/charge/water/ATP, settling or
whole-tissue correspondence claim follows.

Native/host/JAX guarded wall times **16.645/6.559/5.565 s**. Peak sampled tree
RSS **252,542,976 B**; minimum available host memory **19,734,528,000 B**.
CPU7, one thread, no GPU or persistent cache. CPU runtime NumPy 2.5.3,
JAX/JAXlib 0.11.1; native runtime is separate existing BETSE environment.

Attempt 20261028-01 retains the typed-constructor setup failure; 20261028-02 is
source-only preflight. 20261029-01 retains lint failure; 20261029-02 retains
centroid-rounding and native-nullspace assertion failures. Centroid arithmetic
was aligned with source; source inverse defects were preserved and separate
explicit gauge solves qualified. Declared native tolerances were not loosened.
20261029-03 is the complete qualified result with 131 artifact hashes. The
finalizer does metadata verification/copying only. No worker computation,
automatic follow-up audit/regression or shared/frozen edit is active.
