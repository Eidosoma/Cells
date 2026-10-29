# Apply static profiles to prepared geometry

`irregular_overlap.request.json` embeds a qualified initial passive geometry
artifact and explicit ordered profile declarations. With Cells available:

```bash
python -m cells tissue-profiles prepare \
  examples/geometry_tissue_profiles/irregular_overlap.request.json \
  --output /mnt/workspaces/Cells/geometry-profiles
python -m cells tissue-profiles validate /mnt/workspaces/Cells/geometry-profiles
python -m cells tissue-profiles replay \
  /mnt/workspaces/Cells/geometry-profiles/provenance.json \
  --output /mnt/workspaces/Cells/geometry-profiles-replayed
```

Choose new output directories. These commands prepare inputs without running
a simulation. Both complete provenance chains are retained, and replay needs
only `provenance.json`. The Python API is also available:

```python
from cells.core import geometry_profile_preparation as bridge

request = bridge.read_json("examples/geometry_tissue_profiles/irregular_overlap.request.json")
prepared = bridge.prepare(request)
bridge.write_preparation("/mnt/workspaces/Cells/geometry-profiles-api", prepared)
verified = bridge.read_preparation("/mnt/workspaces/Cells/geometry-profiles-api")
assert verified == prepared
```

Replay from the saved recipe:

```python
recipe = bridge.read_json("/mnt/workspaces/Cells/geometry-profiles-api/provenance.json")
replayed = bridge.replay(recipe)
```

The adapter derives the profile layout from bound polygon centroids and actual
surface owners, thickness from explicit physical membrane inputs, and contacts
from the declared reciprocal junctions. It does not use primal seed positions
as cell centroids or infer colors, permutations, owners or physical inputs.
`seed_fills` is either None or a complete stable-cell ID to exact string mapping.
Percentage selectors need an explicit full permutation. For positional selectors,
obtain the required identity from the derived layout:

```python
from cells.processes.betse_tissue_profiles import layout_identity

view = bridge.derive_geometry(request["geometry_preparation"], seed_fills=request["seed_fills"])
identity = layout_identity(view.layout)
```

Use that identity in the explicit index selector declaration. Static preparation
changes selected membrane permeability and insular junction permeability only;
inventories, initial state, volumes, capacitance, physical exterior faces,
controls and other properties remain exact. These files prepare an ordinary
passive model; they do not execute a trajectory, move geometry or remap state.
