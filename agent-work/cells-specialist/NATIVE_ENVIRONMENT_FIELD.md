# Native environment reconstruction

This component fills the instantaneous environment part of pinned BETSE 1.5.0
`get_current`, beyond B23 intracellular current and outside Key's material and
voltage chronology. Chief approved this bounded scope and CPU6 checks. Chief
maintains project status in `PROGRESS.md`; this note describes the contract.

The production entry points are `bind`, `evaluate` and `voltage_dependencies` in
`src/cells/processes/betse_environment_field.py`. The binding takes original
centres, membrane midpoints, cell/membrane measures, owner/normals, Cartesian
bounds, grid size and original configured-temperature cache material/constants.
It derives the native truncated grid, unique nearest maps, site area/count/volume
and divergence caches, cell-to-environment corrections, both native Laplacians
and pseudoinverses, and scalar sigma/ko caches. No inverse, map or coefficient is
accepted as a prepared input. Derived buffers are immutable and rebound from
their original declaration before use, rejecting resealed altered dependencies.

Each readout uses a revalidated B23 post-material current prefix and explicit old
vm, boundary voltages and ECM material/full flux/extra readouts, or an explicit
two-dimensional B08 weight. It does not advance those inputs. The B25 dependency
export carries the Dirichlet inverse and original binding provenance, and does
not execute voltage updates. Voronoi generation and barrier initialization are
outside this supplied-geometry boundary.

Native HH means Helmholtz–Hodge. It uses the Dirichlet inverse despite preparing
a Neumann pseudoinverse. Native finite-difference edge signs, separate HH and
Phi_b corner orders, Gaussian constant/reflect modes, repeated-membrane area
mean, noECM last-write mappings, owner-indexed membrane vm and delta-scaled
gradient remain literal. These outputs are source diagnostics: the native
reconstruction can erase a uniform input current, so no continuum projector,
whole-field conservation or physical field-energy parity is claimed.

Nearest ties are explicitly outside this narrower Cells admission. Raw tie
distances and the actual native k=1 choice are retained. Native execution remains
the comparison evidence at those refused ties. Zero screening in ECM and
binary64 current overflow retain actual nonfinite source arrays without partial
commit. High-precision arithmetic is not claimed to reproduce binary64 overflow.

`validation/betse/betse_environment_field_protocol.json` pins seven native files,
states supplied/derived dependencies and fixes budgets before qualification.
Native capture authenticates checkout, installed mirror and frozen bytes, then
executes unchanged original statements/functions with read-only local trace
copies. A pure stdlib Decimal reference derives geometry, Gaussian weights,
finite differences and independent inverse/gauge solutions at 100/160 digits.
Both complete rounded reference buffers are retained, along with actual/native
buffers and original input declarations. Fresh replay denies imports of Cells,
BETSE, JAX and jaxlib. Fixed manufactured metre-scale cases exercise both source
branches; B23 has its existing instantaneous gross budget, never propagated into
field allowances. Geometry/gauge residuals and fixed field/current/voltage
budgets remain separate. No advancing solver, biological geometry, compiled or
GPU claim is made.
