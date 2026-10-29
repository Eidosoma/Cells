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
operator, bath events and fluid flow require further integration.
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
Ordinary restart retains the phase; transferring phases or changing the physical
owner requires a separate supported operation.

The water variants use current compartment volumes for concentrations, fuel
kinetics, calcium stores and osmotic forces, while keeping the original volume
references for energy accounting. The repair variant also carries its actual
damage, injury-transfer and heat histories. Closing an extracellular face keeps
all earlier transfers and heat. Faces keep their declared area and separation;
water exchange changes compartment volumes without moving the mesh.

The public-interface checks use short software probes. Independent stage and
trajectory qualifications are tracked separately in [Progress](../PROGRESS.md),
as are compiled execution and GPU qualification. These variants prescribe the
barrier event; combined membrane-profile/barrier events, phase handoff, cutting
and assembly compositions require separate integration.
