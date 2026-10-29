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

The prepared tissue uses Cells' existing logmean transport, charge/current field
and energy accounting. Native collocated transport, the separate Bernoulli face
operator, bath events, dynamic barriers and fluid flow require further integration.
Qualification results and remaining work are in [Progress](../PROGRESS.md).
