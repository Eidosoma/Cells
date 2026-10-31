# Explicit finite-ECM polygon preparation

The new geometry law `cells_finite_ecm_conforming_polygon_partition@1` describes
one complete, connected planar partition into declared cell and bath polygons,
extruded through a uniform positive height. The finite baths are physical
polygons; their volumes are never supplied as unexplained lumped values or
inferred from cell centroids. The existing active02 and conservative passive02
packets, failed whole-mesh evidence and prior qualification boundaries remain
separate. This source packet inherits no pending polygon acceptance or native
BETSE equivalence.

The [geometry implementation](/home/robert/Cells/src/cells/processes/finite_ecm_polygon_geometry.py)
exposes `from_partition(declaration, law_id=LAW_ID)`, `prepare(request)` and
`validate_binding(request, binding)`. A complete immutable request owns its JSON
declaration and identity; a binding owns the resulting geometry and identity.
Validation reconstructs the geometry, detecting resealed mutations. Geometric
refusals preserve the complete owned request, stage and original exception.

## Bounded geometric and boundary contract

There are 2..32 regions, including 1..16 physical cells and at least one bath;
at most256 distinct vertices, 64 vertices per region and512 directed edges are
supported. Regions must be simple, convex, counterclockwise polygons with exact
conforming shared edges. They must exhaust one declared simple outer ring,
including every collinear boundary subdivision, with no overlap, hole, gap,
unused vertex or disconnected component. Exact rational predicates and local
moments reuse pinned conservative source helpers; the new integer-grid global
Green/ear reference checks this scope independently without a qualification
inheritance claim.

Every cell boundary edge must have a declared bath on its other side. Direct
cell-cell interfaces and cells meeting the external boundary refuse; no finite
cleft is invented. Each cell-bath edge produces exactly one membrane, with its
actual ordered cell/bath owners, direction, area and normal. Membranes are thin
zero-excluded-volume interfaces with an explicit positive constitutive path;
the path does not subtract guessed volume from either compartment.

Each bath-bath shared edge produces exactly one transport face. Its path is the
distance between the exact area centroids of the two bath polygons. This scope
requires that centroid link to be exactly perpendicular to the shared face,
with both centroids on their actual sides and a common normal projection
strictly inside the face. The common projection, individual centroid-to-face
distances and total link length are retained with exact certificates. This
restriction addresses the concrete risk of applying a two-point face law to a
skew or nonlocal stencil. A midpoint distance is never substituted when these
conditions fail. Exact predicates operate on the actual supplied binary64
coordinates; arbitrary rounded rotations need not preserve the admission.

Every exterior directed edge explicitly declares its bath owner and sealed
condition. Both axial caps are also explicitly sealed. Held baths, outer fluxes
and reservoir boundary conditions require a separate extension. The finite
closed system declares one existing bath as an electrical gauge; a gauge fixes
the voltage reference and does not create a material reservoir.

## Physical preparation and deferred independent checks

`cells_finite_ecm_polygon_passive_preparation@1` accepts a complete caller
`resolved_tissue@1` definition containing identified geometric references. It
converts exact region volumes to pL before rounding, preserves shared areas,
computes capacitance from exact area times caller specific capacitance, resolves
membrane diffusivity/path permeability, and supplies each bath face's geometric
area and orthogonal distance. Face diffusivities, all amounts, fixed charges,
charge anchors, temperature, laws, gauge, capacities and controls remain caller
declarations. Numeric geometric overrides and references replacing physical
inventories or controls refuse. The real public passive parser performs the
existing complete initial charge/current admission; its serialization must
preserve every materialized declaration, up to identified owner-row ordering.

The existing solver consumes its unchanged rounded scalar face inputs as
`D * area / length`. Correct rounding of each geometric input is claimed, not
an alteration of that solver arithmetic or its constitutive law. The source
manifest pins the actual parser, model, transport, field and geometry closure.

Deferred cases include one/two-cell partitions, unequal compartment widths,
dyadic diamond coordinates, translation and owner permutations. Every case has
nonzero manufactured cell polarization, nonuniform bath concentrations and
nonzero initial face flux. Bulk bath polygons lacking a membrane connection
exercise independent floating current-continuity components. The state remains
unchanged at time0 and a declared membrane-control boundary; no time step or
trajectory is performed.

Fresh geometry/unit workers deny all scientific and production imports. They
derive exact volumes, faces, normal projection and link distances independently
from integer coordinates, global Green moments and ear dissection, and check
binary64 rounding cells at two Decimal precisions. Fresh field workers allow
NumPy/SciPy and deny Cells, BETSE and JAX. They use the existing independent
scalar transport and full-node charge/current reference, comparing every state
derivative and physical field/rate output, including finite exterior material,
capacitor ownership, current, energy and gauge constraints. Existing field
protocol budgets are pinned unchanged. Internal Newton iterations and normalized
diagnostic coordinates are retained, without a separate cross-solver equality
claim.

Inputs, constructed requests, actual geometry/preparations, initial layouts,
states, controls and complete fields, independent targets and failure records
are saved before assertions. Full payloads are separate from bounded finalizer
metadata. The [protocol](/home/robert/Cells/validation/geometry/finite_ecm_polygon_protocol.json)
and [source/unsupported matrix](/home/robert/Cells/validation/geometry/finite_ecm_polygon_source_map.json)
define the exact deferred units. Only AST inspection, compilation without
execution, Ruff and source hashing/freezing are authorized for this packet.
Root owns `PROGRESS.md`, launch review, finalization and numerical qualification.
