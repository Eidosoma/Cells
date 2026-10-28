# Conservative cell cutting and topology rebuild contract

The new component removes named cells and remaps explicitly owned state with a
removed-material ledger. Actual BETSE cut/rebuild captures remain separate from
the conservative Cells policy. It is ready for Chief-owned integration; shared
models, dispatch, documentation and root PROGRESS were not changed.

- Law: `conservative_tissue_removal_remap@1`.
- Implementation: `src/cells/processes/betse_tissue_cut.py`.
- Reference, fixtures, captures and protocol: `validation/topology/betse_tissue_cut*`.
- Final component receipt:
  `/mnt/workspaces/Cells/betse-tissue-cut-development-20261028-02/result.json`.
  SHA `e90fed8be76ff2d41b82ac8ad282d38060124f15120908e51acdab4e5a752284`.
- Frozen handoff metadata:
  `/mnt/workspaces/Cells/betse-tissue-cut-handoff-20261028-01/result.json`.

The complete run passes **60 tests: 57 host and three CPU JAX**. Native captures
pass three small-geometry cuts and preserve seven limitation cases. Native,
host and JAX guarded phases take **2.591 / 1.538 / 3.553 s**. Peak process-tree
RSS is **248,418,304 B**, minimum available memory **19,199,733,760 B**, on CPU7
with one BLAS thread, <=1-GiB RSS and >=8-GiB reserve. No GPU, detached job or
persistent compilation cache ran. Attempt 01 is explicitly source preflight;
attempt 02 is the complete component receipt.

## Layout and removal API

`Topology` declares unique stable IDs for cells, membranes, edges and environment
nodes; explicit membrane->cell/environment owners; edge endpoints; and edge
roles. Contact edges have two unique owned membranes, one at each endpoint.
Abstract field edges have membrane indices `[-1,-1]`. Membrane environment `-1`
explicitly means an unbound outside node. Topology validation copies arrays and
makes them read-only.

`plan_cut(topology, removed_cell_ids)` returns an immutable plan containing:

- Original and surviving topologies, preserving survivor order and orientation.
- Old->new maps (`-1` means removed), new->old gather maps and removed indices
  for every domain. Environment node identities remain unchanged.
- Hurt surviving cell IDs and newly exposed surviving membrane IDs, derived
  only from removed **contact** edges.
- Before/after layout identities and the required cache invalidations.

Cell-owned membranes and all incident edges are removed. No cell, membrane,
edge, environmental node, geometry or biological state is created. No-op and
complete removal are defined. No-op retains layout identity and invalidates
nothing. An abstract field edge can survive without any contact or simplex;
it does not imply wound exposure. The native middle cut retains oriented field
edge `C>A`, with no A-C membrane contact.

`owner_csr(after_topology)` builds linear-size cell->membrane and contact-neighbor
maps. Use explicit surviving field-edge endpoints when rebuilding field
operators. `remap_axes(values, plan, [(axis, domain), ...], xp=...)` supports
explicit multi-axis gathers for non-material layout data. Derived operators
must be rebuilt rather than treated as valid by gathering their old entries.

## State and removed quantities

`apply_cut(topology, removed_ids, named_fields)` accepts `OwnedField` declarations
and returns `CutResult`. Each field declares its owner domain/axis and kind:

| Kind | Retained data | Removal accounting |
| --- | --- | --- |
| `state` | Exact surviving values/dtype | Archive removed values; no physical total inferred |
| `quantity` | Exact surviving float64 values | Archive removed quantities and before/surviving/removed totals |
| `density` | Exact values unless a new measure is supplied | Explicit measure and scale convert to quantity; optional new measure preserves amount by rescaling density |

Quantities/densities require declared units and float64. Density also requires
positive finite measures, a positive amount scale and resulting quantity units.
Measures may be owner vectors or broadcast arrays for owned subcompartments.
For example, mM times pL yields fmol with scale 1; mM times m3 requires scale
1e15 for fmol. Explicit `nonnegative=True` rejects negative material inputs.
Signed charges and stored energy/work histories remain signed quantities.

Every `FieldCut` retains removed raw values, removed quantities and owner IDs,
totals and actual balance residuals. Residuals use returned densities and their
new measures. Inputs, measures and totals must be finite/representable, including
empty/no-op cases. No field silently injects removed material into ECM, zeros
survivor state or neutralizes charge. Register each authoritative physical
quantity once; aliases, gates and historical transfer ledgers must not be summed
as additional material inventories.

Global data is declared `domain="global", axis=None, kind="state"`. Equal array
lengths never establish ownership. Multi-owner material must first have one
authoritative entity owner; arbitrary multi-axis gathers do not automatically
define a unique removed-material ledger.

The middle-cut fixture removes **[17.82057854, 44.55144635] fmol** from its two
cell-ion rows; largest reported partition residual is **7.10543e-15 fmol**.
Native ECM volume-map rebuilding with unchanged concentrations changes apparent
environmental material by **[1.22000581, 1.83000871] fmol** in this manufactured
case. Supplying the new measures to the conservative policy preserves both
environmental amounts, with zero residual here and no release into ECM.

## Checkpoint and continuation integration

After a real cut, rebuild geometry maps, field/Poisson operators, owner bindings,
compiled layout/capacity and checkpoint identity. Keep physical time, control
phase, pending events and random-stream identity under explicit ownership; do
not recreate them from compact positional indices. Construct the new complete
model layout and rebind membrane/edge/store/fuel/readout ownership by stable ID.
This component does not operate a model solver or perform that shared wiring.

`checkpoint_manifest(after_topology, result.field_metadata)` records the law,
layout and field-declaration identities, topology, owner axes, shapes, dtypes and
units. `validate_checkpoint_manifest(manifest, topology, expected_field_metadata)`
rejects mismatched layouts and declarations. The composing checkpoint writer
must separately persist/checksum the numeric state, measures, removed ledger,
clocks and parameters. A manifest is not a complete checkpoint file or automatic
migration. Tests cover disk JSON roundtrip, stale layout/unit rejection, and
sequential cuts versus a single combined cut with matching removed totals.

Numerical gather/remapping kernels accept `xp=jax.numpy` after host validation.
Close over a fixed plan and compile for the new shape. A dynamic shape-changing
cut is not executed inside an existing JIT graph. CPU tests cover owned gathers,
multi-axis data, density rescaling, independent batches and complete removal.

Geometry/measure changes can alter chemical/capacitor energies. Removed charge,
volume and stored energy can be archived, but physical cutting/boundary work and
any later reservoir/transport model require explicit caller accounting. No
regeneration, mechanics, cut-energy law, ATP demand or healing process is added.

## Native capture boundaries and retained failures

Pinned revision: `5269a714aa2593ed2a6708c4516289977d8ae1a2`. Captures execute actual
`_cut_cells`, cell polygon/matrix/volume/contact/environment/mask/Poisson methods,
`redo_gj`, DEC cut/maps/core operators and `Simulator.initDenv`. The seed consists
of manufactured adjacent 4/5/6-sided polygons, a small explicit DEC mesh and an
8x8 environment grid. Native Voronoi seeding, biological profiles, mechanics and
whole-tissue simulation are outside the claim. Only the profile-selection hook
is recorded rather than implemented.

Native rebuild traces and data expose diffusion/current resets. The source's
conditional molecular/ER/gap-junction/fast-solver hooks do not imply conservative
state preservation. Seven captured limits are: empty cut, complete removal,
single-survivor geometry, list-middle survivor loss, list-last index failure,
equal-length global-axis deletion and an unknown nested field left unremapped.
Partial mutated native states and exceptions are retained. Native ATP/content
release is commented out.

DEC `cut_mesh` returns **removed** edge indices despite its restructure-index
description. The component provides separate unambiguous keep/remove maps.
Native environment density/volume behaviour and resets remain distinct from
the conservative policy; no whole-tissue parity claim is made.

Reproduction uses the new bounded wrapper with a fresh suffix:

```sh
taskset -c 7 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  agent-work/cells-worker-01/workfiles/check_betse_tissue_cut.py \
  --output /mnt/workspaces/Cells/betse-tissue-cut-development-NEW
```

All component files and evidence are frozen. No follow-up computation,
regression or audit is running. Shared integration remains Chief-owned.
