# CORE-010: passive spatial production integration

Status: bounded development acceptance complete in 0.15.0.dev0; stable release remains 0.14.0.

D063 [resource amendment v2](SPATIAL_EXTRACELLULAR_ACCEPTANCE_V2.md) prepares a
fresh complete acceptance capture under a two-hour cap, keeping v1 science and
CPU/artifact settings unchanged. All 106 new resource/byte-replay tests and 228
combined preflight checks pass. The full acceptance-02 capture passed in 73 minutes:
57 scalar runs and 12 streams, all fourteen eager cases complete. The 352 captured
files remain unchanged. The separate full audit, all 4190 six-context regression
tests and [development closeout](../reports/core-010-v2-closeout.json) now pass.
See the [v2 report](../reports/CORE010_ACCEPTANCE_V2.md) and
[completed detached handoff](../reports/CORE010_CLOSEOUT_HANDOFF.md). Stable
promotion and biological/BETSE trajectory validation remain separate.

All 156 development preflight and 3962 six-context regression tests pass.
See the [implementation report](../reports/CORE010_IMPLEMENTATION.md) and
[development closeout](../reports/core-010-implementation-closeout.json) for
scope, retained test failures, exact CLI replay and the remaining release gate.

D062 adds a [prospective recorded-artifact gate](SPATIAL_EXTRACELLULAR_ACCEPTANCE.md)
and [independent audit/corruption tooling](../reports/CORE010_ACCEPTANCE.md), with
122 passing preflight tests and no production edits. The capture stopped at its
one-hour budget with ten of fourteen eager cases complete. All 53 completed scalar
and 12 stream runs independently audit; all 4084 tests pass in the new six-context
regression matrix, with no failures, errors or skips. That stopped v1 attempt
remains unaccepted; the separately registered v2 capture above is now complete.

The physical and numerical contracts remain the frozen SPEC-009 and NUM-010
documents. This slice integrates their passive, closed, fixed-geometry subset
into the shared CPU/float64 JAX engine. It does not extend their biological or
numerical qualification. The accepted 0.14.0 source context is preserved in
`reports/cells-0.14.0-source.tar.gz`; `reports/core-010-preservation.json` binds
the archive and both read-only baseline audits.

## Ownership and execution

`spatial_extracellular@1` has independent padded cell, outside-volume, membrane
and transport-face axes, plus an explicitly ordered species axis. It permits
zero cells for a pure extracellular transport benchmark. Each cell has exactly
one membrane, facing one finite outside volume; several cells may share that
volume. The outside graph is connected, or consists of a single volume without
faces. One explicitly identified outside volume fixes the common voltage gauge.
`face_capacity` counts outside transport slots; the inherited cell-junction
`edge_capacity` is explicitly zero for this passive family.

Six state arrays preserve all five reference coordinate fields: the reference
amount-increment array is split into cell and outside owners; membrane transfer,
face transfer and the two separately owned dissipation histories retain their
meaning. Membrane transfers are positive outward, face transfers sender to
receiver. No charge, inventory or energy projection is permitted.

The field module is a same-stage constraint solver, not a second integrator.
It derives relative outside potentials by current continuity, using positive
logarithmic-mean face conductances. Membrane voltages follow anchored intracellular
ionic charge and the once-owned membrane capacitance. Outside volumes have no
invented bulk capacitor. Component charge compatibility is checked independently.

Geometry/checkpoints contain edge lists, never a persistent dense adjacency or
field matrix. The initial explicit solver identity, `gauged_dense_kirchhoff@1`,
uses a small dense temporary matrix, with its quadratic storage included in the
pre-allocation resource guard. Replacing this solve with a sparse or matrix-free
large-mesh backend requires a separately qualified solver identity. This slice
does not claim large-GPU execution or scaling.

## Acceptance boundary

The inherited actual RK4 step ceiling is 0.000125 seconds for the qualified
panel, with a 0.0000625-second refinement comparison. This is not a universal
mesh-independent stability bound. Existing model families keep their own limits.

Required before release acceptance: strict configuration and ownership tests;
all 14 frozen reference cases with all state fields and field readouts; JIT/eager
comparison; actual stage/native/observed domain and accounting checks; restart,
future-control branches, bounded windows and independent-world cohorts through
the shared engine; immutable evidence and rehashed-corruption audits; preservation
and regression of all older families and historical reference contexts.

Hermite sampling uses the incoming held control for both endpoint slopes.
Complete cubic bounds cover inventories, affine membrane voltage and linear
component charge. Nonlinear field constraints are checked at actual numerical
stages, native states and requested observations, not asserted over every cubic
interior point. Blocked histories must remain exactly unchanged, including
nonzero histories at checkpoint and control boundaries.

Pumps, channels, cross-region cell junctions, switched face barriers, multiple
membrane patches, mechanics, fluid flow, organ physiology and GPU qualification
remain outside this integration. They need their own physical and numerical gates.

## Try the development example

The [one-cell definition](../configs/spatial_extracellular_cell.json) uses the
unchanged synthetic binary-unequal NUM-010 physical inputs and horizon. Its
observation list is shorter for convenient inspection. All geometry, ionic
species and controls are explicit data; production never imports a reference.

```bash
PYTHONPATH=src .venv/bin/python -m cells validate configs/spatial_extracellular_cell.json
PYTHONPATH=src .venv/bin/python -m cells run configs/spatial_extracellular_cell.json --output runs/my-spatial-cell --checkpoint-at 0.15
PYTHONPATH=src .venv/bin/python -m cells resume runs/my-spatial-cell/snapshots/step-001200 --output runs/my-spatial-resume
```

Choose unused output paths. The ordinary CLI also supports bounded windows and
independent-world cohorts. Development checkpoints bind the precise development
sources/runtime; no compatibility with 0.14.0 checkpoints or future edited
development builds is implied. The accepted old sources remain archived.

Use `scripts/test_spatial_extracellular_build.py --output reports/my-test-matrix`
for the current and five historical test contexts. The two original NUM-010
modules still reject modified production and run unchanged under preserved
0.14.0. `scripts/audit_preserved_spatial_extracellular_reference.py` replays the
old reference evidence read-only; its [post-edit result](../reports/core-010-preserved-num010-audit.json)
verifies all 339 payloads and 14 reference restarts with zero ODE calls.
