# Ordinary steady mechanics at the shared-field boundary

The new `betse_mechanics_join` prefix composes the existing deformation and
disabled flow gates without editing their implementations. Its conditional
native scope is the FULL loop after ion transport, special handlers, networks
and noise, before deferred concentration commit and voltage reconstruction.
The caller supplies the fields, primary/molecule/GRN concentration rows, exact
cell/environment IDs, phase `dt`, source clock, seeded DEC layout and measures.
The wrapper does not execute those upstream mechanisms or infer their state.

Native order is `osmotic_P`, guarded `getFlow`, guarded steady deformation,
`update_all_concs`, `update_V`, `check_v`, then sampled `write2storage`. The
ordinary parameter loader forces `fluid_flow=False`, `td_deform=False` and
`mu_water=0.01 Pa*s`. Deformation and osmotic controls remain actual user
flags. The public API refuses enabled flow, dynamic deformation and FAST.
It never invents a flow-result input to steady deformation: the source has
none. The two existing components share field/owner/operator prerequisites.

There is an important correction to the earlier initialization-only source
description. `Simulator.init_dynamics` does not build the inverse when its
dynamic-deformation guard is false. That fragment and its old missing-inverse
evidence remain unchanged. It is incomplete as a claim about an ordinary
seeded lifecycle: `SimRunner.seed` unconditionally calls `graphLaplacian` after
`redo_gj` and before saving the seeded cluster. Initialization and simulation
load that cache. The cut path also rebuilds the graph. This packet records
both facts and requires a declared seed or post-cut graph origin. It executes
neither native seeding nor cutting; the explicit layout and DEC prerequisites
remain caller owned. A geometry epoch change requires a new binding/state.

The only `p.fluid_flow=True` assignment is inside
`MasterOfGenes.run_core_sim`, the isolated sim-grn runner, under
`self.recalc_fluid`. Reading or reinitializing a network in the ordinary FULL
solver does not execute that assignment. Its initial fluid formula is
`-J_env / (F * mean(c_env) * mean(z))`; it is distinct from `getFlow` and can
divide by zero mean valence. A normal call with an externally enabled flag
would be a separate conditional policy scope, not ordinary loader reachability.
This packet neither enables nor qualifies it. Existing flow component source
correspondence stays intact; its extracellular `m3/s` output is not silently
connected to a transport port expecting `m/s`.

When osmotic pressure is enabled, the wrapper adds exactly the declared primary
and enabled paired molecule/GRN rows before calling the existing osmotic
auxiliary. It preserves native signed pressures and the unresolved dimensions
of `PP`. It changes no water amount, cell volume, ionic inventory, energy or
live geometry. The native bulk pressure gradients are stored before the final
electric displacement read, including a later missing-field failure. Every
returned/failed trial and all numeric arrays are retained before comparisons.
The source accepts some nonfinite steady output; the wrapper rejects it after
saving its full raw trial. That stronger finite guard remains explicit.

Sampling is a separate conditional boundary with a caller-supplied receipt
after deferred material commit, voltage reconstruction and its guard. Those
operations are not executed or certified here. The existing interpolation map
is rebuilt from the current persistent display centres for each sample;
displacements are added to the original membrane vertices. The next sample
uses the updated display centres. The live physical geometry, graph inverse,
areas and volumes stay unchanged because `implement_deform_timestep` has no
active `deformWorld` call. Only the existing global quartic interpolation
regime is supported; native knot records must confirm that regime. Adaptive
FITPACK remains refused and unqualified. Source fixed-boundary behavior and
the non-projector nature of its HH rotation are preserved.

The prospective02 packet declares fourteen complete contexts, sixteen refusal
cases, five independent corruption cases, immutable/resealed owner checks and
a source protocol check. Fresh workers deny production imports. Independent
workers also deny all scientific packages and recompute complete owner/DEC,
pressure, HH and conditional display outputs at100/160 Decimal digits, saving
full raw trees and separate projections before comparison. The independent
display fit uses pivoted scalar normal equations. Native workers execute
authenticated unchanged pressure/deformation/graph/curl/HH/display bodies on
the supplied declarations and retain complete source locals, objects, dtype
inventories, numeric NPZ arrays, spline knots/coefficient data, failures and
private RNG witnesses. Object-array values retain their original dtype and
shape in sidecars without introducing pickle data.

Independent static review of01 identified two imported-owner gaps, recorded in
`/mnt/workspaces/Cells/betse-mechanics-join-preflight-20261031-01/REVIEW.json`
(SHA256 `42ed395a5ab7593d0dad585f765602982a34ecaea5a6918143aadb67e5f99795`).
Frozen01 remains unchanged and held. Version02 requires the exact no-ECM
membrane-sized environment axis and identity membrane map; its independent
reference derives the original owner average directly instead of consuming a
prepared averaging matrix. Permuted-map and wrong-size controls must refuse.
The native adapter now restores imported display vertices by declared membrane
owners while keeping original `mem_verts` as sample coordinates. A noncanonical
imported-centre/vertex case checks both initial retention and later refitting.

All budgets are inherited unchanged from the deformation contract: relative
`8e-12`, displacement floor `3e-20 m`, display floor `3e-17 m`, operator floor
`2e-14`, pressure/gradient floor `3e-9` in their named units and auxiliary floor
`3e-14`. Reference resolution must use at most0.1 of those budgets. Disabled
flow and other held buffers must retain exact binary64 bytes. No carried-error
allowance or tolerance widening is introduced. Incorrect phase `dt` is refused;
the independent corruption panel also tests a million-fold `PP` time-factor
substitution, which is resolvable under the unchanged auxiliary floor.

Preparation is static: source/AST auditing, code-object compilation, Ruff,
hashing and immutable copying. It imports no scientific module, constructs no
fixture, collects or executes no test, starts no simulation/reference and edits
no central `PROGRESS.md`. Existing components, old packets, failed evidence and
active jobs remain untouched. Chief owns preflight, execution authorization,
the launcher and finalizer. The new declared-unit file belongs only to this
packet; no previous scientific qualification is inherited.
