# Explicit-width manufactured cell/bath partition constructor

This source-only constructor supplies a new bounded physical geometry law.
It does not reclassify the earlier full-domain control volumes or claim native
equivalence. All numerical and independent geometric checks remain unrun.

The caller declares a CCW axis-aligned rectangular domain, a tensor grid of
fresh manufactured seed IDs/coordinates, per-column/row cell half-widths, every
outer and intercellular cleft width, every complementary bath-slot ID, extrusion
height and membrane path. Widths have no production defaults. The membrane path
is a separate constitutive length and is not used to infer geometric clefts.
Only layouts with one to four seed columns/rows and at most 32 total regions are
supported; this currently permits at most four cells. Other convex domains,
arbitrary seed clouds, rotations, curved geometry and finite membrane volume
are explicitly unsupported.

Cells are rectangles centred on their unchanged declared seed coordinates.
Positive complementary grid slots become the separately declared bath owners.
Every shared grid line must be exactly representable in binary64; the actual
cell offsets and clefts must exactly equal their declarations. Collapse,
overlap, seed/owner loss and changed widths refuse without tolerance. Input and
returned grid events, raw partition and exact region measure targets precede
their gates; original failures and partial evidence remain available.

The generated conforming partition enters the existing frozen finite-ECM
polygon geometry preparer. Bath rectangles own the whole sealed exterior.
Cells have cell/bath membranes, and all bath/bath centroid links are exactly
orthogonal to shared faces. Geometry, membrane measures, bath volumes, face
distances and owner incidence are rebuilt there, with no cached native map.

Pinned BETSE `Cells.cellVerts` scales vertices about cell centres using
`scale_cell` and separately stores `cell_space` as a gap length. `makeECM` forms
midpoint-based ECM points and nearest-point maps. Those source operations are
inspected and cited in the static source map; this constructor does not assert
that explicit physical offsets reproduce their resulting cells or bath mesh.

The independent worker constructs grid lines cumulatively from domain bounds,
clefts and full cell widths, separately from production's seed-centred offsets.
It then checks the full partition with the frozen independent integer-grid,
Green/ear geometry lane at two precisions. The lane is extracted with unchanged
function ASTs to exclude its field/conversion/scientific dependencies. Strict
field sets, exact two-component vectors, full owner axes, all metric certificate
fields and correctly rounded targets are checked. Complete scalar input/return
links, source seed bits and width targets remain part of the candidate.

Exact cell and bath areas exhaust the domain without overlaps or holes;
extruded volumes balance, owner incidence columns sum to zero, and every region
has constant and affine integrated-flux identities. Binary64 area/volume store
sum defects remain explicit. No trajectory conservation, physical model,
ordinary loop or operator qualification is inherited. Separate caller physical
admission is still required, and old operator/cache gates always refuse.

The future panel has five manufactured cases: one cell, unequal clefts, two
cells, four cells with reordered source owners, and a translated cell. Four
additional test trees batch 23 input refusals and 23 coherent resealed output
controls, check the failed-baseline guard, and keep physical/operator gates
closed. Every tree has one potential actual nested reference worker. Root's
finalizer therefore gives ten scheduled entities and nineteen total entities,
without standalone child replays. Controls require a passing unchanged baseline
in that same worker. Cases add zero biological or native qualification credit.

Root owns independent source review, launch/finalizer preparation and any later
authorized qualification. Preparation is limited to source, AST, Ruff, hashing,
copying and compilation without scientific execution. Prior bridge/environment
packets, failed evidence, existing core files and shared status remain untouched.

The prospective02 evidence repair addresses the two findings in Chief's final
source review (`e4ce212b2be31eae84076b9fd9b3880ffd1927c5b1ea14251f399bdb72f81ab3`).
Every named input refusal declares its exact exception class, bind/prepare phase,
reason, constructor stage and original cause chain. Expected and observed
contracts are saved before comparison. Six metadata contract corruptions cannot
earn credit. The reference saves grid events, each completed axis, each precision
result and later completed mappings immediately, before the next failure point.
Two future metadata fault checks use exact extracted reference function ASTs with
stubbed dependencies; they add no geometry evaluation, case or child and demand
retained precision results with no baseline/control credit.

The source auditor proves inverse AST equality after removing only the reference's
14 partial-retention assignments. It proves unchanged caller mutations and test
source outside the two repaired trees, expectation map and metadata helpers.
Production core, geometry reference lane, fixtures, caller document, five cases,
nine trees, nine potential children, ten scheduled units and nineteen total
entities remain unchanged. Frozen01's 38 files are retained byte-for-byte in
the successor with an explicit preservation map. This is a source-only repair
awaiting Chief's review; it grants no numerical launch or physiology admission.
