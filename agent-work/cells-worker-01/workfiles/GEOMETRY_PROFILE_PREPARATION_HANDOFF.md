# Qualified initial geometry plus static profiles

Cells Key Developer, 2026-10-29. New module:
`cells.core.geometry_profile_preparation`. No qualified adapter, CLI, shared
dispatch, existing physics, PROGRESS.md or documentation index was changed.

API: `prepare(request)` returns `Preparation(definition, provenance)`;
`derive_geometry(artifact, seed_fills=None)` supplies the qualified direct
profile Geometry view; `replay`, `read_json`, `write_preparation` and
`read_preparation` support complete portable recipes and non-overwriting output.
The request kind is `cells.initial_geometry_profile_request@1`; exact fields are
`kind`, `geometry_preparation`, `seed_fills`, `default`, `profiles`, `ion_enabled`,
`enabled` and `is_ecm`. `geometry_preparation` is the complete paired ordinary
initial geometry definition/provenance artifact. Profile declarations use the
unchanged native Profile/Selector fields, including six-ion Dm order and explicit
selector identities/permutations. The recipe and Python usage are in
`examples/geometry_tissue_profiles/irregular_overlap.request.json` and its README.

The geometry artifact is fully replayed and its typed JSON identities checked.
Source geometry specs are rebound before constructing the direct profile view:

- Layout cell/membrane/exterior axes, per-cell membrane order, membrane owners,
  grid bounds and reciprocal contacts come from the bound geometry.
- Coordinates are the bound polygon centroids, never primal seed positions.
  The independent irregular image control selects `seed-r2-c0` using centroids;
  using primal points incorrectly selects nothing.
- Thickness comes only from explicit physical membrane declarations; native
  generation tm is not a fallback. Junction pair IDs/orientation come from the
  declared physical junctions, with their actual physical neighbor graph.
- Seed fills remain None unless the caller supplies a complete stable-cell ID
  to exact string map. No colors, palettes or cell-ID changes are invented.
  Percent selectors need complete explicit permutations. Index selectors need
  the derived layout identity; derive_geometry does not choose indices/order.

The unchanged direct profile adapter owns selection, duplicate occurrences,
native ALL/percentage alias semantics, ordered D overwrites, insular union and
P=D/thickness. The new module permits only its selected coefficient changes;
typed JSON restoration verifies every other definition property. Full initial
state fields/hash, inventories, volumes, capacitance, physical exterior faces,
control history and execution remain exact. The portable outer request retains
the complete geometry artifact; `profile_preparation` retains the complete direct
profile provenance. Their identities and the derived geometry/layout identities
are cross-linked and regenerated on replay. Inconsistent resealed records are
refused. Strict reading refuses duplicate/nonfinite JSON and changed typed output.

Qualification:
`/mnt/workspaces/Cells/geometry-profile-preparation-development-20261029-02/result.json`.
All **43 host checks** passed, including seven cases and **28 independent full
physical stages** before/after at two control clocks. Cases cover radial/polygon
volume, scaled geometry, overlapping duplicate selections, percentage/ALL order,
exact color strings, centroid-based image picking and disabled profiles.
Independent stdlib polygon/owner maps and frozen stdlib selectors/Decimal unit
conversion supply expected definitions; existing full passive field/flux equations
check potentials, all state derivatives, material and physical energy balance.
Replay/refusals, strict JSON, positional identities, complete source chains and
fresh-process portable serialization are checked. RNG and input data stay exact.

Unchanged budgets: geometry rtol 6e-12 / atol 1e-27 m; P rtol 5e-14 / atol 1e-25
m/s; full RHS rtol 3e-10 / atol 3e-12, charge atol 3e-23 C/s; potential rtol 3e-10 /
atol 3e-13 V; material 3e-14 fmol/s and energy 1e-10 pJ/s. Maximum RHS error uses
0.029805 of its budget. Exact state/inventory/control checks have no tolerance.

Development01 retains a fixture rejection: the frozen native mask requires
noncollinear non-white pixels, so a single pixel is unsupported. The accepted
fixture explicitly declares a 2x2 mask and a separate degenerate-image refusal
is checked. No source law or tolerance changed.

Host guard: 28.19 s (pytest 27.22 s), CPU7, one thread, JIT disabled; peak process
tree RSS 453,574,656 bytes; reserve >=16,492,101,632 bytes. Limits 480 s, 1 GiB RSS,
8 GiB reserve. No GPU, native generation, long job or other-job polling.

The metadata-only finalizer verifies 164 artifacts, 39 captured sources and 43
evidence records, both prior qualified receipts and unchanged public geometry
CLI. Three exact paired request/definition/provenance examples are copied from
passed evidence: overlap, percent-alias and image-centroids. Final receipt:
`/mnt/workspaces/Cells/geometry-profile-preparation-handoff-20261029-01/result.json`.

Static ordinary passive preparation only. No new field/intervention/pressure/ECM
transport law, physical amount/charge remap, cut, moving geometry, checkpoint/
solver continuation, compiled/integrated trajectory or full native simulator
claim. No automatic follow-up or existing component-suite rerun.
