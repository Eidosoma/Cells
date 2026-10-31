# Native lifecycle audit and explicit owner handoff

This prefix prepares admission of a **supplied owner boundary** immediately
after ordinary SIM `init_dynamics` and `clear_storage`, before the bootstrap
`update_V`. Its capture may read pinned native objects, but neither that capture
nor an evidence-path label proves that seeding, an initialization trajectory,
serialization, loading or compatibility checks completed. The generated source
map records exact native methods, caller order, owner attributes and AST hashes.

Native seeding runs `make_world`, `init_core`, tissue profiles, `redo_gj`, then
unconditionally `graphLaplacian`. INIT loads `(cells,p_old)`, checks compatible
general/world options and creates fresh core state. SIM loads `(sim,cells,p_old)`
and retains the simulator; it does not call `init_core`. Both reached phases
enter `run_sim_core`, which calls `init_dynamics`, clears storage, calls the
bootstrap voltage update, then constructs the phase clock and selects a solver.

`init_dynamics` rebuilds tissue/diffusion/noise/control/pressure bases and field
initializer caches while preserving primary concentrations. Its random channel
noise draw is unconditional even when the configured multiplier is zero. An
existing GRN is reinitialized, including tissue and channel reader work. This
prefix does not emulate those operations or derive their results from a cold
owner. Runtime `sim.T` and configured `p.T` remain separately captured.

`capture_supplied` copies numeric owners and records presence, absence and
unreadable values explicitly. `capture_native` additionally checks the actual
Simulator, Cells and Parameters class source files against pinned hashes. It
reads existing owners; it does not initialize, unpickle or advance them. Private
channel/transporter/mitochondrial/separate molecule owners are unsupported and
cause admission refusal. Their presence is diagnostic, not complete private
state capture. Upstream evidence links are identifiers, not verified execution
receipts or native geometry certification.

The native Parameters solver, ECM flag, radius and polarizability are YAML
aliases rather than instance fields. Capture reads their four actual getters,
whose descriptor sources are separately pinned; these getters validate/read the
configuration without writing it. Other properties are not evaluated.

`handoff` reauthenticates the existing field or calcium binding and requires
exact matching cell/membrane/ion axes, physical declarations, environment maps,
inverses, current weights, transport coefficients, fixed sigma/ko inputs and
values, bootstrap parameters/boundaries, controls, publications and complete
post-commit GRN cache. Original float arrays remain binary64 and immutable.
Integer scalar native constants can equal their exactly representable declared
floating constants; array shapes and values are not broadcast or repaired.
The existing hot serializer must round-trip the supplied owner without changing
primary material. The adapter then calls existing component `field.reconstruct`
once, returning the existing loop's exact parent type. It never calls a cold
initializer or native dynamics. This is a component bootstrap, not an executed
native `update_V` or an independent scientific comparison.

`handoff_mechanics` can attach the existing field/mechanics composition only
when every held mechanical/display store and the matching additional neighbor,
DEC and graph operator declaration exists. It preserves the original ragged
display owner order. It runs no pressure, deformation, event or display step.
There is no combined calcium/mechanics loop in this prefix. Supplied post-event
pressure drives remain explicit later inputs, without an event scheduler claim.

Several native seams prevent a broader initialization claim:

- The stable initial-mesh panel remains a reviewed failure with **0/9 complete
  meshes**. Separate accepted local primitives and conditional mesh lifecycle
  evidence do not supply missing physical geometry.
- Fresh `init_core` never writes `Egj`; `update_gj` first creates it. Missing
  material stores are retained and refused, without zero-filled stand-ins.
- Osmotic/PP/pressure-gradient stores are not all written during core/dynamics
  initialization. Incomplete mechanics is refused. Native disabled-flow scalar
  zero stores cannot silently become the grid arrays required by the frozen
  field/mechanics composition. Scalar blocker one has a similar schema seam.
- A CaATP rate written during INIT can persist into SIM because dynamics does
  not delete it. The current calcium adapter requires absence at bounded call
  zero, so persisted rate is refused without deletion. Absent-rate calcium
  admission still requires its actual maintained-pool policy and N=3 clock.
- With deformation enabled, `_pickle_phase` replaces saved `phase.cells` with a
  copy of the display cells before serializing, then clears `sim.cellso`.
  A loaded cluster therefore cannot be assumed to retain original seed centres
  with newly consistent physical operators. Matching owners must be supplied;
  the adapter does not refresh or repair geometry.

The prepared check panel verifies complete supplied field, polarized, calcium,
mechanics and warm-owner routing, direct entry into three existing calls,
specific missing/changed-owner refusals, copied immutable buffers and preserved
unreadable stores. The baseline is the unchanged existing component on the same
manufactured declarations. It earns no independent accuracy, initialization or
native trajectory credit. No numerical equations or tolerances are changed;
the original ECM material 39/40 failure and frozen geometry failures stay failed.

Preparation is source/AST reading, literal metadata, code-object compilation,
Ruff, hashing and immutable copying only. Chief owns review, launch/finalization
and any shared progress update. No scientific import, specimen construction,
test collection/execution, active-job polling or shared component edit is part
of preparation.
