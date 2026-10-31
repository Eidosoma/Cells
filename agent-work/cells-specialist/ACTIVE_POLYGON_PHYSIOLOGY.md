# Active physiology on explicit polygon owners

`cells_polygon_active_physiology_preparation@1` resolves dimensioned geometry
references inside a complete caller definition. The caller selects the actual
model identity and supplies all inventories, fixed charge and charge anchors,
channel populations and gate states, pumps, chemical buffers/reactions, free IP3,
fuel pools and regeneration, reservoir policies, controls, capacities and clocks.
The corresponding public family parser performs its existing physical admission.
The bridge compares the serialized admitted definition with the materialized
caller input, allowing only reordering of identified owner rows. It inserts no
physiology defaults and never substitutes a passive or closed surrogate model.

The [core](/home/robert/Cells/src/cells/core/active_polygon_physiology_preparation.py)
exposes `prepare(geometry_request, binding, request)` and
`validate(geometry_request, binding, request, preparation)`. The returned immutable
preparation contains independent JSON copies of the definition and provenance,
an identity, every conversion input/output/certificate, the actual owner axes and
reservoir flags, and source hashes. Full re-preparation detects resealed changes.
Admission refusals retain the stage, complete request, materialized definition
when available, conversion trace, original exception type and reason.

## Geometry and physical units

The geometry authority is the conservative polygon complex, with directed patch
owners, one contact per reciprocal physical interface, exact binary64-input
volumes and squared edge-area targets. This identity does not inherit the failed
stable whole-mesh preparation's qualification, Voronoi accuracy or native BETSE
equivalence. Initial source and passive packets remain separate and unchanged.

Every supported geometry field requires an identified `$geometry` reference;
numeric overrides and references in physiology, inventory or controls refuse.
Exact rational cubic metres are converted to picolitres once. Area and patch
capacitance are rounded from the exact squared-area target, using each caller's
specific capacitance. A caller diffusivity divided by its explicitly declared
path length gives permeability. Plasma patches use the polygon thickness;
junctions require explicit reciprocal membrane IDs and a positive contact path;
ER paths require explicit internal membrane area and thickness. No centroid
distance, guessed internal membrane area or extracellular spatial-face geometry
is introduced.

For ionic-only families the polygon volume is the ionic cell volume. Calcium
requires an explicit per-cell fraction strictly between zero and one: the
polygon's total volume is partitioned into cytosol and ER before rounding. The
ionic cell and chemical cytosol use the identical exact cytosolic ratio and thus
identical rounded pL value. The caller already supplies matching free-ion amounts
in both representations. Preparation never rescales them. This explicit rule
resolves the concrete risk of counting an ER compartment in addition to the
entire polygon volume.

Each finite-fuel cell declares exactly one owned ATP/ADP/Pi pool. Na/K, PMCA and
ER pumps must consume the pool of their own cytosol; regeneration ports name
actual pool IDs. Open calcium retains every actual bath reservoir flag and the
public parser's explicit exterior policy and global ionic-moiety ceilings.
Binding, partition and source identities cannot substitute for these checks.

## Prepared coverage and limits

The [protocol](/home/robert/Cells/validation/geometry/active_polygon_physiology_protocol.json)
and [source/unsupported matrix](/home/robert/Cells/validation/geometry/active_polygon_physiology_source_map.json)
enumerate the ten initial target identities and their exact public parsers and
actual model types. Other version IDs and water, moving geometry, transport,
profile, intervention, event and epoch compositions refuse. All selected channel
families require their existing explicit 298.15 K identity. Polygon and existing
parser limits both apply; this bridge additionally bounds physical cells at16
and ordinary ionic channel populations at256.

Deferred complete fixtures include nonuniform patch coefficients, initial cell
potentials of -35/-55 mV, nonzero ER voltage, active pump/channel/junction flows,
zero/one/two-state populations where supported, merged geometry, finite fuel
composition sensitivity, mixed/all-held and empty-reservoir open calcium, and
owner-row permutations. Fresh conversion references deny all scientific and
production imports. They use independent integer-grid Green/ear geometry,
integer-ratio unit calculations and exact rounding-cell checks at two Decimal
precisions. Fresh field references permit NumPy/SciPy but deny Cells, BETSE and
JAX; they reuse the established independent scalar laws, complete family
derivative layouts and full-node charge/current roots.

The initial state is never advanced. Read-only probes at time0 and a declared
control boundary use that same initial state, check the manufactured polarization
and compare every derivative field and potential with existing fixed budgets.
Calcium/fuel reference energy identities are retained; basic ionic references
provide full-node residuals and complete derivative comparisons without a new
independent total-energy identity claim. Every input, actual state/layout/control
and field trial, independent target and refusal is saved before assertions.

This packet is static preparation. Numerical execution, test collection, native
comparison and trajectories require Chief's separate reviewed launch. Root owns
`PROGRESS.md`, launch authorization, terminal qualification and failure closeout.
