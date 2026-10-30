# B14/B13 perturbation component removal

The two new remap/unit files pass24 short CPU checks. Current source hashes,
dependencies and durable receipt are in
`physiology_perturbation_remap_workqueue.json`. Sampler, stream, step,
checkpoint and shared files remain unchanged. Chief owns paired checkpoint
integration and PROGRESS.md.

`remap_component(state, old_binding, new_binding)` returns frozen
`PerturbationRemapResult(state, archive, diagnostics)`. It validates the complete
accepted source, calls the existing explicit `rebind_stream`, and reuses
`betse_tissue_cut`'s cell-removal ownership/quantity contract. It draws nothing,
never runs an event/loop, and leaves the source untouched. A no-op returns the
original state object with complete empty archive shapes.

Only explicit cell removal plus owner-axis reordering is supported. Every
membrane of a surviving cell must remain, with its old cell/environment owner.
Complete environment and ion sets remain; their coordinate order may change.
Areas, cell volumes, effective environment volumes, numeric precision and
environment mode must match exactly on survivors, including one-ULP changes.
Boundary occurrence changes remain explicit in the new binding, following the
existing stream-rebind semantics. Terminal empty bindings, new wound membranes,
ion/environment deletion, volume conversion/mixing and geometry generation are
unsupported. In particular, a mixed-bath cut that changes effective volume is
refused rather than silently changing inventory at unchanged concentration.

All three protein and three permeability buffers gather by explicit owner IDs.
Permeability gathers both ion and membrane axes. No surviving value, signed
scheduled modifier, control, elapsed component clock, loop count, stream/world
ID, draw counter or native RNG/cache changes. Only the stream layout identity
is rebound. Stable surviving membrane coordinates retain their qualified
behavior; native future samples follow their sequential tape at the new count
and order, without a native subset-invariance claim. No numerical Cells state,
solver/operator or physical topology is automatically remapped here.

`PerturbationRemovalArchive` has fields `cell_ids`, `membrane_ids`,
`environment_ids`, `ion_ids`, `protein`, `diffusion`, `cell_volume_m3`,
`membrane_area_m2`, `environment_effective_volume_m3`, `cell_amount_mol`,
`environment_amount_mol`. IDs and removed buffers use old-owner order; removed
permeability rows keep the old `ion_ids` order. All archived arrays are backed
by immutable bytes. The `.total_amount_mol` property counts only the cell and
environment quantity arrays. Since environment owners remain, their removed
IDs, buffers, measures and amounts have explicit empty axes.

Cell and environment concentration densities use their declared volumes in m3
to form mol quantities through the existing cut contract. Membrane protein is
a view, not another inventory; all permeability buffers are nonmaterial state.
Removed protein is an explicit sink ledger and is not released into exterior
nodes. Diagnostics report previous/retained/removed amounts and the exact
owner-partition residual; they include neither membrane views nor a hidden
quantity rebase. Nonrepresentable quantities or totals refuse. No cut-energy,
whole native-cut or coupled-physiology claim follows.

The24 checks include complete six-buffer removal and reorder, an independent
80-digit Decimal concentration×volume calculation, huge membrane readout values
excluded from removed material, immutable archives, no-op/pure reorder,
nondrawing traps, native cached versus stable survivor continuation, one explicit
postcut component call, one-ULP/dtype/volume/mode changes, unsupported/foreign
owners, mixed-bath effective-volume refusal and invalid/nonrepresentable stock.

Receipt:
`/mnt/workspaces/Cells/physiology-perturbation-remap-tests-20261029-01/result.json`,
SHA256 `3cd36355a4f13f55feb3717852acc90689afc255c2d725c540271c21ffae1dda`.
CPU7/one thread,180s allowance,1GiB child-tree RSS and8GiB host reserve,
no GPU/JIT/persistent cache. Completed in7.06s with258,453,504B peak RSS.
CPUs3/4 and the Chief's frozen trajectory campaign were untouched and unpolled.
