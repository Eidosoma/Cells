# Assignment: active transport with water and compliant volumes

2026-10-28. The user explicitly requests continuous parallel coding in this
checkout while long qualifications run detached. The frozen `resolved_water@1`
qualification is active; do not poll it or launch GPU/compiled checks.

## Worker ownership

Implement only these new files plus your existing WORK_LOG.md:

- `src/cells/core/surface_water_kinetic_spec.py`
- `tests/unit/test_surface_water_kinetic_spec.py`
- `configs/resolved_water_kinetic_tissue.json`

The coordinator owns the production model, shared registry/spec/schedule/ensemble
hooks, physical tests/fixtures, protocol, launch and PROGRESS.md. The independent
reference agent owns the new reference module/tests. Do not edit existing water
or kinetic source files. All outputs and caches go under `/mnt/workspaces/Cells`.

## Version and interfaces

Use `MODEL_ID = "resolved_water@2"` and
`SurfaceWaterKineticModel(surface_kinetic_spec.SurfaceCavModel)` with explicit
`water_compartments` and `water_membranes`, using the existing water dataclasses.
The base projection is the broad `resolved_tissue@7` catalog, so we do not need a
new water model version for every existing channel law. This does not establish
new coupled coverage for every law. Maintained Na/K pump energy, intrinsic shared
channel gates and kinetic junction gates remain exactly their existing laws.

Use `Experiment(surface_kinetic_spec.Experiment)` with `water`, and the matching
Change subclass with `water`. Union all membrane, junction, channel, pump and
water boundaries. Control fields in order are membrane, junction, channel, pump,
water. Reuse the existing kinetic Execution (including channel_capacity).

Expose `prior_spec(spec)` removing only water additions to produce an exact
resolved_tissue@7 definition, and `water_spec(spec)` removing channels/pumps and
junction-gate additions to produce resolved_water@1 with the same water owners
and schedules. The latter must also project Execution to the passive type.
Expose strict `parse`/`to_dict` with owned IDs, units, finite closed compartments,
no silent unknown fields, exact owner ordering and round-trip preservation.
Reuse existing water validation where possible by constructing a passive water
projection and parsing it; keep the old source files untouched. At the end,
defer-import `cells.models.surface_water_kinetic` and call `check_definition`.
That module will be implemented by the coordinator in parallel. Report when the
schema is ready so the hook can be checked before a host-only parser run.

## Example and physical scope

Build a small closed finite example by extending the current one-cell / one-
exterior water example. Add Na/K ATPase with explicit maintained ATP/ADP/Pi;
add shared Kv1.5, HCN4 and CaV1.2 populations, so a declared calcium species and
its initial amounts/background charge must be consistent. Reuse the pinned
channel/pump parameter definitions; these are synthetic inputs, not wetlab fits.
Calcium here is an ordinary mobile ion, not an ER/cytosol/buffer model.

Use a 50-us endpoint, dt=1.25e-6, independent off-grid water/pump/channel changes
(e.g. 13.3/23.7/31.1 us), and observations at exact nominal ticks or control
boundaries. Water permeability around 1e-10 m/(Pa s), finite compliant volumes
and explicit neutral osmolytes should produce a small resolvable water response.
Keep model checks strict; do not relax tolerances to make the example pass.

There are 23 complete state fields: the existing 19 shared-channel/pump fields
plus the four water fields. The coordinator's coupled model will use current
volume for every ionic and pump stage, preserve distinct water/ion/pump ledgers,
and include dilution, elastic energy, dissipation and maintained reservoir work.
Geometry/capacitance/topology remain fixed; no finite ATP pool or autonomous
repair. The existing 1.25-us kinetic step ceiling remains, supplemented by the
water block bound.

## Verification and resource coordination

Reuse your bounded host check driver and durable evidence pattern on CPU 7,
BLAS/OMP/MKL1, CPU-only JAX, no persistent compilation cache, <=1 GiB worker RSS
and >=8 GiB host reserve. No trajectories, JIT workers or GPU use until assigned.
Test strict parsing, projections, separate control clocks, absent/closed routes,
reordered species/owners and invalid units/ownership/metabolic inputs. Save source
snapshots and failures. Coordinate when the deferred production hook is ready.
Return concrete selectors and evidence. Then await the next scoped assignment;
we will add execution/replay support once the interface has settled.
