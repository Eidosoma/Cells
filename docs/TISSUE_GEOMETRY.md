# Prepare passive tissue from native geometry

Use a complete initial geometry recipe to create an ordinary `resolved_tissue@1`
definition. These commands prepare and verify files; they do not run a trajectory.
Run them from the repository with its installed Cells environment, or set
`PYTHONPATH=src` when using a source checkout.

```bash
python -m cells tissue-geometry prepare \
  examples/tissue_geometry/irregular_native_radial.request.json \
  --output /mnt/workspaces/Cells/geometry-prepared

python -m cells tissue-geometry validate /mnt/workspaces/Cells/geometry-prepared

python -m cells tissue-geometry replay \
  /mnt/workspaces/Cells/geometry-prepared/provenance.json \
  --output /mnt/workspaces/Cells/geometry-replayed
```

Choose new output directories each time. Existing directories, files and symlinks
are refused. Successful commands print a JSON summary; invalid inputs return
exit code 2 with an error on stderr. JSON must contain unique object fields and
finite numbers, including nested metadata. `NaN`, infinities and overflowed
literals such as `1e999` are refused.

The same operations are also available through `python -m cells.tissue_geometry`.

Each preparation contains:

- `definition.json`: the complete ordinary passive tissue definition.
- `provenance.json`: the complete request, native capture and source/runtime
  identities, geometry specs, generation inputs/RNG, physical inputs and replay
  identities. Both files can be moved together. Replay needs only the provenance
  file and the Cells environment; the original native capture directory and
  native BETSE installation are not needed.

`validate` strictly reads both files, rebuilds the preparation from its recipe
and checks the complete definition identity, including JSON numeric types.
Editing either file can invalidate it. To
make a different preparation, edit a copy of the request and choose a new output.

The repository example is copied exactly from the qualified component evidence.
It contains an actual irregular native geometry with nine cell owners and 16
exterior sites, plus explicitly manufactured physical inventories, charges,
volumes and transport parameters. Its full capture is embedded for portability.
It is an example of the input contract, rather than a calibrated biological case.

The request has exactly `kind`, `geometry_source`, `physics`, `experiment` and
`execution`. Its kind is `cells.initial_static_geometry_tissue_request@1`.
Keep all source and generation fields when constructing another request. Physical
choices must be supplied explicitly:

- Choose `physics.volume_policy` as `native_radial` or `polygon`. These cell
  volumes differ for irregular shapes. Amounts and charge are not rescaled when
  the policy changes.
- Supply every physical exterior volume in m3. DEC control measures and native
  occupied-grid weights do not supply those volumes.
- Supply membrane thickness in m, areal capacitance in F/m2 and diffusivity in
  m2/s for every species. Bound edge length times declared height gives area;
  capacitance is area times areal capacitance, and permeability is D/thickness.
- Declare every stable cell, exterior, membrane, reciprocal junction and physical
  exterior face, including inventories, fixed charge, charge anchors, coefficients,
  reservoir/gauge choices, control schedules and execution settings.

The frozen geometry adapter validates all these inputs without inferring missing
physics or renaming owners. Ordinary IDs require ASCII letters, digits,
underscores or hyphens; the frozen native single-preset capture's original IDs
contain colons and are refused. Cut epochs, physical state remaps, moving geometry
and solver continuation require separate contracts.

## Apply static tissue profiles

The `tissue-profiles` command also accepts a complete geometry preparation plus
an ordered profile recipe. The [portable example](../examples/geometry_tissue_profiles/README.md)
embeds the geometry's definition and provenance:

```bash
python -m cells tissue-profiles prepare \
  examples/geometry_tissue_profiles/irregular_overlap.request.json \
  --output /mnt/workspaces/Cells/geometry-profiles
python -m cells tissue-profiles validate /mnt/workspaces/Cells/geometry-profiles
python -m cells tissue-profiles replay \
  /mnt/workspaces/Cells/geometry-profiles/provenance.json \
  --output /mnt/workspaces/Cells/geometry-profiles-replayed
```

This request has kind `cells.initial_geometry_profile_request@1` and exactly
`geometry_preparation`, `seed_fills`, `default`, `profiles`, `ion_enabled`,
`enabled` and `is_ecm` alongside `kind`. `geometry_preparation` contains both
complete source artifacts. The resulting passive definition retains its initial
state, inventories, physical geometry and controls. Selected membrane and insular
junction permeabilities change under the existing static-profile rules.

The adapter derives selectors from bound polygon centroids and actual surface
owners, using the explicitly declared physical membrane thickness. Colors and
percentage permutations must be supplied explicitly. Both complete recipes
remain in the output provenance, so a fresh process can reproduce the result
without the original input file. This prepares initial passive tissue; composed
geometry, dynamic interventions and physical remapping require further contracts.

## Apply static extracellular barriers

The same `tissue-profiles` commands accept
`cells.environment_barrier_preparation_request@1`. The
[example request](../examples/extracellular_barriers/request.json) supplies a
manufactured two-cell tissue and a complete 2-by-2 finite exterior:

```bash
python -m cells tissue-profiles prepare \
  examples/extracellular_barriers/request.json \
  --output /mnt/workspaces/Cells/extracellular-barriers
python -m cells tissue-profiles validate /mnt/workspaces/Cells/extracellular-barriers
python -m cells tissue-profiles replay \
  /mnt/workspaces/Cells/extracellular-barriers/provenance.json \
  --output /mnt/workspaces/Cells/extracellular-barriers-replayed
```

This initial preparation applies BETSE's ordered free, adherens and tight-junction
coefficient assignments, followed by explicit ionic modulators. Each tissue face
receives the harmonic mean of its two site diffusivities. Duplicate region
occurrences and sodium normalization remain recorded. A zero endpoint coefficient
blocks that species on the face; there is no added conductivity floor.

Every species and site needs a declared modulator. Stable site/face IDs, species
valences, endpoint ownership, volumes, areas and distances must match the ordinary
`resolved_tissue@1` definition. The first bridge requires a uniform planar grid,
finite exterior owners and a sealed perimeter. Only face diffusivities change;
initial state, inventories, charges, membrane/junction parameters and schedules
remain intact. Full inputs and derived coefficients are retained for exact replay.

For complete channel/calcium/fuel/water owners, use
`cells.composed_environment_barrier_preparation_request@1` with the same fields
and the complete parent under `definition`. This explicit adapter accepts
`resolved_tissue@12`, `resolved_calcium@11`, `resolved_calcium_energy@5`,
`resolved_calcium_energy_water@2` and `resolved_calcium_energy_water_repair@2`.
All five retain the full 56-law catalog. A passive parameter view binds geometry
and coefficients only; the complete parent supplies the field and transport
equations. Both that parameter view and the complete parent must pass their
existing admission checks; a parent that needs active processes to make the
passive view solvable is not admitted by this adapter. Preparation preserves
all initial gates, calcium stores, fuel,
water, damage, accounting references and control schedules. Replay recomputes
the full recipe and rejects modified complete state or coefficients.

For water models, the grid volume must match each **initial** exterior volume;
face areas and distances remain fixed as the model's volumes evolve. This is
not moving-mesh transport. The adapter accepts ordinary initial definitions;
scheduled profiles, inherited epochs, cuts and assembly wrappers require their
own contracts. Manufactured complete-owner inputs are available in
[`environment_barrier_composition_fixtures.py`](../validation/transport/environment_barrier_composition_fixtures.py).

The prepared tissue uses Cells' existing logmean transport, charge/current field
and energy accounting. Native collocated transport, the separate Bernoulli face
operator and fluid flow require further integration. Scheduled ideal-reservoir
bath controls have a separate physical owner and accounting contract below.
Qualification results and remaining work are in [Progress](../PROGRESS.md).

## Schedule extracellular barrier opening

`resolved_extracellular_barriers@1` adds one opening/resealing event to the sealed
passive tissue above. The [complete example](../examples/extracellular_barriers/scheduled.json)
includes its original static preparation and the ordered site IDs to affect:

```bash
python -m cells validate examples/extracellular_barriers/scheduled.json
python -m cells run examples/extracellular_barriers/scheduled.json \
  --output /mnt/workspaces/Cells/scheduled-extracellular-barriers
```

At each integration stage, BETSE's native `ecmJ` logistic pulse blends the selected
site coefficients between their prepared barrier values and free diffusion.
The amplitude lies in `[0, 1]`. Repeated site IDs retain native assignment
semantics: they do not multiply the opening. Fixed ionic modulators apply after
this update, followed by harmonic conversion to physical faces. A zero ionic
modulator therefore remains impermeable throughout the event.

The `SIM` phase applies the pulse; `INIT` holds the prepared barriers fixed.
The physical state carries a phase clock alongside all twelve original material
and energy fields, so ordinary snapshots resume the same event. Closing a
barrier preserves all earlier transfers and dissipated energy. Observation
outputs include site and face diffusivities, the pulse and native sodium weight;
that weight is diagnostic and does not alter physical volumes or inventories.

The event declares `on_s`, `off_s` and positive `change_s`; integration steps must
be at most `change_s / 8`. The on/off times are the native smooth transition
centres, not discontinuous switches. This version accepts one event or `null`,
explicit targets and the six native species names. Its physical model must match
the embedded static preparation; experiment clocks and ordinary held controls
may differ. Phase transfer, cutting and assembly composition need their own
integration.

This is a prescribed diffusivity change using Cells' logmean transport and
existing charge/current closure. There is no added structural barrier energy
store or ATP cost, and it does not reproduce BETSE's entire solver ordering.
Current numerical and execution qualification is recorded in
[Progress](../PROGRESS.md).

The same prescribed coefficient event now has explicit complete-owner variants:

| Scheduled model | Exact physical parent | Saved state fields |
| --- | --- | --- |
| `resolved_active_extracellular_barriers@1` | `resolved_tissue@12` | 20 |
| `resolved_calcium_extracellular_barriers@1` | `resolved_calcium@11` | 35 |
| `resolved_calcium_energy_extracellular_barriers@1` | `resolved_calcium_energy@5` | 39 |
| `resolved_calcium_energy_water_extracellular_barriers@1` | `resolved_calcium_energy_water@2` | 44 |
| `resolved_calcium_energy_water_repair_extracellular_barriers@1` | `resolved_calcium_energy_water_repair@2` | 49 |

Each embeds a complete static barrier preparation from the section above and
adds only `phase_clock_s` to its parent's physical state. The exact parent keeps
its full channel catalog, calcium stores, fuel pools, controls and accounting
references. Site coefficients change at each integration stage; geometry stays
fixed. The same event timing, target and amplitude rules apply. Public parsing,
serialization, snapshots and independent-world admission preserve these owners.
Ordinary restart retains the phase. All five complete owners have an
[explicit INIT-to-SIM preparation](TISSUE_PHASES.md#extracellular-barrier-phases);
current qualification scopes are recorded in [Progress](../PROGRESS.md).
Changing the physical owner requires a separate supported operation.

The water variants use current compartment volumes for concentrations, fuel
kinetics, calcium stores and osmotic forces, while keeping the original volume
references for energy accounting. The repair variant also carries its actual
damage, injury-transfer and heat histories. Closing an extracellular face keeps
all earlier transfers and heat. Faces keep their declared area and separation;
water exchange changes compartment volumes without moving the mesh.

The public-interface checks use short software probes. Independent stage and
trajectory qualifications are tracked separately in [Progress](../PROGRESS.md),
as are compiled execution and GPU qualification. These variants prescribe the
barrier event. The ionic, calcium, finite-fuel, water and repair owners also
support the combined schedules below;
phase handoff for other owner families, cutting and assembly compositions
require separate integration.

## Combining membrane and extracellular events

Five explicit models apply membrane-profile events and one extracellular
opening pulse to a complete physical parent:

| Combined model | Exact parent | Physical/history arrays, plus one shared phase clock |
| --- | --- | --- |
| `resolved_active_profile_barriers@1` | `resolved_tissue@12` | 19 + 1 |
| `resolved_calcium_profile_barriers@1` | `resolved_calcium@11` | 34 + 1 |
| `resolved_calcium_energy_profile_barriers@1` | `resolved_calcium_energy@5` | 38 + 1 |
| `resolved_calcium_energy_water_profile_barriers@1` | `resolved_calcium_energy_water@2` | 43 + 1 |
| `resolved_calcium_energy_water_repair_profile_barriers@1` | `resolved_calcium_energy_water_repair@2` | 48 + 1 |

All retain 63 channel populations, 56 channel laws and their complete controls.
The calcium model carries its chemical species, ER stores and transfer histories;
the finite-fuel model also uses its actual fuel pools and regeneration. Its pumps
keep their finite-fuel ownership. Closing either kind of route preserves earlier
transfers and heat, with the original accounting references.
The water and repair variants retain changing cell/extracellular volumes,
original osmotic references and live fuel concentrations. Repair also retains
damage, injury transport and prescribed repair costs. These states remain
owned by the complete physical parent throughout both coefficient schedules.

Static preparation has an explicit order: membrane profiles first, extracellular
barriers second. A `cells.active_profile_barrier_preparation_request@1` request
contains `order: static_membrane_profiles_then_extracellular_barriers@1`, the
complete `profile_preparation`, and a `barrier_request` whose definition must
exactly match that membrane-prepared definition. The existing `tissue-profiles
prepare`, `validate` and `replay` commands preserve both embedded recipes. Their
summary reports coefficient changes separately for membranes and extracellular
faces. A different owner or reversed preparation order is refused.

The calcium and finite-fuel variants use
`cells.calcium_profile_barrier_preparation_request@1` with the same ordered
fields and CLI commands. Their membrane artifact must be a complete composed
preparation for exactly `resolved_calcium@11` or `resolved_calcium_energy@5`,
each containing the full `resolved_tissue@12` ionic layer. Earlier, smaller
calcium catalogs are not substituted.

Water and repair use `cells.joint_water_profile_barrier_preparation_request@1`
with the same ordered fields and CLI commands. Their complete composed
membrane artifact must belong to exactly `resolved_calcium_energy_water@2`
or `resolved_calcium_energy_water_repair@2`, including the full
`resolved_tissue@12` ionic layer. The public parser, control scheduler, typed
snapshots and ensemble admission preserve these explicit owners. GPU input
admission is separate from GPU execution qualification.

The scheduled model embeds that artifact as `coupled_preparation`, declares
`membrane_interventions` and `barrier_intervention`, and uses the existing
phase, timing and reset policies. INIT holds both schedules inactive; SIM
evaluates both at each integration stage. The timestep must resolve the
transition time divided by eight for both event families. Material, energy,
geometry and gates remain owned by the complete parent model.

These prescribed coefficient changes add no structural barrier energy or ATP
cost. The public interface and independent component checks are recorded in
[Progress](../PROGRESS.md). All five combined models have an
[explicit combined INIT-to-SIM handoff](TISSUE_PHASES.md#combined-membrane-and-extracellular-phases).
Complete trajectories and compiled/GPU execution require their own qualifications.
Assembly compositions need additional integration. Water/repair component,
phase-handoff and public-interface checks have separate evidence entries in
[Progress](../PROGRESS.md).

## Schedule ideal-reservoir bath composition

`resolved_passive_bath_events@1` and `resolved_active_bath_events@1` add
prescribed reservoir concentrations to the exact passive `resolved_tissue@1`
and complete 56-law `resolved_tissue@12` owners. Each retains its full physical
state and control families. The [manufactured definitions](../validation/transport/surface_bath_events_fixtures.py)
declare two reservoirs with distinct initial compositions and fixed voltages.
Scientific and execution qualification is recorded in [Progress](../PROGRESS.md).

The model declares `bath_site_ids`, `bath_events`, `enabled_Cl` and `phase`.
Events contain `kind`, `on_s`, `off_s`, `change_s` and signed `amplitude`.
Supported kinds are `K_env`, `Cl_env` and `Na_env`, in that order. The explicit
policies are `phase_clock_rk_stage_native_logistic@1`,
`each_declared_reservoir_reference_concentration@1` and
`explicit_ideal_reservoir_dose_voltage_compensation_work@1`. INIT holds the
program inactive; SIM evaluates it at every RK stage. Each active transition
requires steps no larger than `change_s / 8`.

The setter order and counterion overwrites follow the pinned BETSE source.
K and Na setters require a real monovalent negative `M` inventory; the Cl
setter writes Na as its counterion. Overlapping events can inject net charge.
Cells therefore records the supplied material, compensating electrode charge
and chemical/electrical work explicitly. These external-controller ledgers are
Cells' physical accounting, not a claim that BETSE reports the same work.
Targets must be declared ideal reservoirs; finite extracellular compartments
cannot be clamped by this feature. Each reservoir uses its own original
concentrations as its baseline, with no change to its fixed background charge.

The saved arrays retain transport contributions, an integrated variable
chemical-work history and the phase clock: 14 arrays for passive tissue and
21 for active tissue. Physical observations add the prescribed dose and work.
Use `physical_*` history readouts when interpreting total supplied material,
electrode charge and work; `maintenance_*` rates expose the underlying
transport contribution. Nonzero logistic tails at time zero are recorded as
an explicit initial controller operation against the original anchors.
No initial tail or existing transport history is discarded.

Ordinary parsing, validation, snapshots and ensemble input admission preserve
the exact bath model. Its schema's `artifact` and `replay` helpers authenticate
the complete definition and initial controller operation. Full trajectories,
compiled/GPU execution and combinations with finite fuel, calcium stores,
water or repair require their own qualification. An
[explicit bath INIT-to-SIM workflow](TISSUE_PHASES.md#ideal-reservoir-bath-phases)
preserves transport histories and records the new initial controller operation;
its qualification is tracked separately. These models
do not implement the native non-ECM whole-row setters.
