# Initial static native geometry to passive tissue

Cells Key Developer, 2026-10-29. This separate adapter emits ordinary
`resolved_tissue@1`. It reuses the unchanged qualified B09 binder and ordinary
passive model. No existing qualified module, shared dispatch/CLI or PROGRESS.md
was edited. The native generator is not rerun.

API: `cells.core.geometry_tissue_preparation.prepare(request)` returns
`Preparation(definition, provenance)`. Constants are `BRIDGE_ID`, `REQUEST_KIND`
and `KIND`; `replay(provenance)`, `write_preparation(directory, prepared)` and
`read_preparation(directory)` reconstruct the full recipe and refuse changed
output. Writing never overwrites an existing directory. `bind_source(source)`
recomputes the qualified geometry bindings from the complete serialized specs;
a caller-constructed binding cannot bypass this step.

The request has exactly `kind`, `geometry_source`, `physics`, `experiment` and
`execution`. The kind is `cells.initial_static_geometry_tissue_request@1`.
`geometry_source` contains complete `mesh`, `grid`, `geometry` spec dictionaries
and initial `generation` metadata. The latter retains the full native capture,
capture file and semantic identities, the explicit native membrane occurrence
axis, exact pinned native source hashes/runtime, inputs, constructed seed points,
original/retained/removed seed ledger and all three complete RNG states. Specs
must reference this full generation identity. Declared topology, coordinates,
metric/reference-face data, boundary/auxiliary configuration, ordered contacts
and environment owners are checked against the capture before rebinding.
Geometry height, gap, shrink, bounds and boundary labels must match generation.
No physical state exists on an initially removed seed; this is initial geometry
preparation, with no biological amount migration.

Physical declarations are intentionally complete:

- `volume_policy` is explicitly `native_radial` or `polygon`. Cell volume is
  the selected bound m3 measure times 1e15 pL/m3. The irregular example differs
  by over 30%; changing the choice does not rescale any amount or charge.
- `exterior_volume_policy` is `explicit_physical_m3@1`. Every bound environment
  site has a positive caller-declared physical volume and explicit inventory,
  fixed background, charge anchor, reservoir flag and boundary potential. DEC
  areas and native occupied-grid weights never supply physical exterior volume.
- `membrane_area_policy` is `bound_edge_length_times_height@1`. Every patch
  declares its stable ID/inside/outside, positive thickness in m, positive areal
  capacitance in F/m2 and complete nonnegative diffusivity in m2/s. Bound area is
  m2; C=area*areal-C in F and P=D/thickness in m/s. Native generation tm is kept
  as generation metadata; it is never a default for a missing physical thickness.
- `junction_area_policy` is `one_bound_contact_surface@1`. Every actual reciprocal
  contact has exactly one declared junction ID, ordered membrane pair, sender,
  receiver and complete physical P[m/s]. Its area is one contact surface. No GJ
  area fraction, channel count, distance, coefficient or route is inferred.
- Species, temperature, all cell amounts/fixed charge/charge anchors, complete
  physical exterior faces, reservoir/gauge closure, physical provenance, every
  control schedule and execution setting are explicit. Faces are supplied as
  ordinary physical routes; DEC operators do not invent extracellular transport.

Ordinary model parsing validates the entire physical definition, initial charge
compatibility, concentrations and all scheduled initial-field domains. Initial
passive transfer/energy ledgers are exactly empty. Complete source and physical
inputs, both cell measures, geometry manifest, inventory/state/control identities
and the selected policies are retained for replay. Replayed definitions and
provenance must match exactly; inconsistent resealed records are refused.

IDs must satisfy the existing ordinary model format: ASCII letters, digits,
underscore or hyphen. The geometry binder also accepts other strings. The frozen
native single-preset capture uses cell IDs such as `native-seed17:0`; this adapter
explicitly refuses it. It does not rename original seed owners. Supporting that
case requires a separately specified initial naming/provenance contract. The
accepted examples use explicit compatible stable axes from the outset.

Validation receipt:
`/mnt/workspaces/Cells/geometry-tissue-preparation-development-20261029-02/result.json`.
All **56 host checks** passed, including five frozen actual native geometries
under both volume policies, 20 independent full-field/flux stages at two control
clocks, exact inventory/charge preservation, stable-ID permutations, replay,
serialization, 30 missing-physics/owner/capture refusals, native preset ID refusal,
seven resealed tampering cases, input/RNG purity and frozen source provenance.
The stdlib reference computes polygons and owner conversions independently;
existing full-node electrical roots, Decimal GHK, transfer/charge/energy equations
provide physical comparisons. No production projection supplies expected data.

Budgets stay explicit: geometry rtol 6e-12 / atol 1e-30; full RHS rtol 3e-10 /
atol 3e-12 with charge atol 3e-23 C/s; potential rtol 3e-10 / atol 3e-13 V;
material residual atol 3e-14 fmol/s and energy residual 1e-10 pJ/s. Maximum RHS
error used 0.029805 of its budget. Exact owner/state/input checks have no tolerance.

Guarded host time was 30.01 s (27.86 s pytest), CPU7, one thread, JIT disabled,
peak RSS 253,857,792 bytes and minimum available memory 19,676,303,360 bytes.
Limits were 480 s, 1 GiB RSS, 8 GiB reserve. The first attempt preserves the
fixture ID-format failure; the existing ordinary ID restriction was retained.
No numerical tolerance, qualified binder or physical equation was changed.

The metadata-only finalizer verifies 997 artifacts, 451 captured sources, 56
evidence records and the frozen B09 receipt. Three concrete examples include
request.json plus definition.json/provenance.json copied exactly from passed
evidence: irregular-native-radial, irregular-polygon and scaled-polygon. Handoff:
`/mnt/workspaces/Cells/geometry-tissue-preparation-handoff-20261029-01/result.json`.

No cut epoch, physical amount/charge remap, moving geometry, checkpoint/solver
continuation, implicit boundary physics, native generator/full simulator,
integrated/compiled trajectory or GPU claim. No detached-job polling or automatic
follow-up audit/regression. Chief owns public integration.
