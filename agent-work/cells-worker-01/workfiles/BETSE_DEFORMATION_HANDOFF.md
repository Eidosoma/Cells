# Native deformation and electromechanical displacement contract

The standalone component preserves the reachable steady deformation arithmetic,
source pressure auxiliary, explicitly disabled positive-clock recurrence and
sampled display ownership. Native dimensional/initialization/boundary problems
remain visible. It does not establish physical mechanics or tissue parity.
Shared models, dispatch, root documentation and PROGRESS remain Chief-owned;
all earlier components and evidence were left untouched.

- Law: `betse_deformation_source_v1_5_0@1`.
- Process: `src/cells/processes/betse_deformation.py`.
  SHA `88e61c22a979edbfaa564170a5e615b698092a6356cb1aaa017182e4aba56cb2`.
- Reference, fixtures, native capture and protocol: `validation/mechanics/betse_deformation*`.
- Complete receipt:
  `/mnt/workspaces/Cells/betse-deformation-development-20261028-08/result.json`.
  SHA `f7750f7bf37466d6b18efd7bdd269a944903e03dc2e3bc84e8805b0146484d98`.
- Frozen metadata: `/mnt/workspaces/Cells/betse-deformation-handoff-20261028-01/result.json`.

The run passes **58 tests: 54 host and four CPU JAX**, no skips. Native captures
cover **20 forcing/operator cases, four display cases and ten limitations**.
Native/host/JAX guarded phases take **7.860 / 8.844 / 14.894 s**. Peak process-tree
RSS is **280,268,800 B**, minimum available host memory **19,554,729,984 B**,
on CPU7 with one BLAS thread, <=1-GiB RSS and >=8-GiB reserve. No GPU, detached
job or persistent compilation cache ran.

## Modes, operators and actual formulas

Native parameters unconditionally set `td_deform=False`. The full normal solver
calls osmotic pressure, optional flow, then `getDeformation`, before updating
concentrations/voltage. The fast solver has no corresponding deformation call.
The positive-clock `timeDeform` branch is exercised only as a forced isolated
diagnostic; the component does not enable the source mode or repair its t=0 path.

`bind_operators(...)` takes explicit neighbor pairs, lengths, force/curl
directions, membrane ownership and DEC incidence/inverse/edge/area data. It
reproduces native cell averaging and the factorized Laplacian/inverse. Source
pressure directions (`nn_tx/ty`) and curl directions (`cell_nn_tx/ty`) remain
separate. There is no inferred geometry, orthogonal projector or replacement
Poisson solve. Dense components are bounded to 256 cells, with explicit neutral
padding. Larger/sparse/tissue layouts require separate composition work.

With `B` the neighbor difference divided by length and `A=M_sum_mems/num_mems`,
pressure-gradient matrices are `-A*diag(nn_direction)*B`; curl-gradient matrices
`Gx,Gy` use the cell-neighbor directions and positive sign. Native rotation-only
arithmetic is:

`curl = Gx*Fy-Gy*Fx; AA=Linv*(-curl); rotated=(Gy*AA,-Gx*AA)`.

`HH_cells` ignores `bounds_closed`. Its name/docstring does not establish
idempotence, orthogonality, total-volume conservation or a fixed exterior.
`Parameters.fixed_cluster_boundary` is carried as an explicit native no-op.
No silent zero-displacement boundary correction is added.

The reachable steady branch is:

`gradP=pressure_gradient(P_cells)`;
`raw=Linv*(-gradP/shear)`;
`d=rotation_only(raw) + include_osmotic*pressure_gradient(PP) + E_cell*galvanotropism`.

Electric and osmotic additions occur **after** rotation-only processing. Native
`shear=youngMod/(2*(1+0.49))`; the other Lame parameter is computed but unused.
Prior displacement, current, charge and conductivity do not drive this steady
branch. There is no active displacement clamp or stability bound.

`disabled_time_step(history, forcing, operators, parameters)` implements only
the source positive-clock algebra, using supplied current/previous history:

`F=(gradient(P_cells+optional_PP)+J*rho*galvanotropism/sigma)/shear`;
`k=dt**2*(shear/1000)`;
`gamma=dt**2*damping*shear/(1000*2*radius)`;
`candidate=k*L*d-gamma*(d-d_previous)/dt+(k/shear)*F+2*d-d_previous`;
`new_d=rotation_only(candidate)`.

Both shear divisions and literal density **1000** are retained; configured
density **1050** used in the osmotic helper is a different source parameter.
The disabled routine appends history before branching. At t=0 it fails at
removed `np.float`; no alias is installed. Starting at positive time without a
previous history level fails. Negative time falls through its branch selection
and still rotates current displacement; the supported diagnostic domain instead
requires a positive clock and both levels. No claim of native end-to-end dynamic
initialization is made.

## Units, pressure auxiliary and physical ownership

Cell pressure and ideal osmotic pressure are Pa; concentration totals are mM,
numerically mol/m3. Gradients are 1/m, Laplacian 1/m2 and inverse m2. The steady
elastic pressure term is metres. The steady electric term uses E in V/m and
galvanotropism numerically m2/V. Signed pressures and galvanotropism are retained.

`osmotic_auxiliary(...)` takes explicit total cell/environment solute values and
an environment map/average, surface area and volume. The caller owns which ion,
molecule and GRN rows represent separate physical solutes. Native adds all these
rows without detecting duplicate inventories or applying molecular charge scales.
The formulas are:

`pi_cell/env=R*T*total`; `delta_pi=environment_average*pi_env-pi_cell`;
`u=(delta_pi-P_cells)*(aquaporins/mu_water)*(3e-10**2)/tm`;
`div_u=u*cell_area/cell_volume`; `PP=Linv*(-div_u*rho*dt)`.

The ideal pressures, water velocity and divergence have their ordinary Pa, m/s
and 1/s units. **Native PP is dimensionally unresolved:** its displayed formula
gives kg/m, not Pa; the raw gradient addition in steady displacement is not a
dimensionally consistent elastic-force derivation. Dynamic forcing/damping and
the repeated shear division also do not establish a physical Newton/energy law.
Names such as `displacement_m` track native storage conventions; the mixed
osmotic/dynamic arithmetic does not supply a validated physical displacement
model or energy closure. Keep `PP_native` separate from physical pressure/work.

Native water/concentration/volume updates are commented out. The helper returns
auxiliaries only and never transfers water, changes amounts or updates geometry.
There is no inferred ATP, heat, pressure work, strain energy or conservation law.
Physical geometry, volumes, surface areas, authoritative material/charge/water
inventories and any mechanical energy model remain composing-model-owned.

## Numerical API and acceptance

`Operators` holds six matrices plus an active cell mask. `Forcing` holds cell
pressure, native PP, E/J vectors, charge density and conductivity. Scalar fields
have final cell axes, vectors `[...,2,cell]`, and mechanics parameters scalars or
`[...,1]`. `History` has two equal-shaped displacement arrays; returned previous
state broadcasts with the resulting world shape. Numerical NumPy/JAX kernels
are pure and unchecked; supplied inputs are not mutated.

`steady(...)` returns the total nominal displacement, pressure gradient, raw
elastic/rotated pieces, potential, separate osmotic/electric additions and a
numeric divergence diagnostic. `rotation_only` and `divergence_numeric` expose
the actual supplied matrix operations. `disabled_time_step(...)` returns a new
history and explicit source k/gamma/body/candidate diagnostics.

`domain_valid(...)` checks finite operators/forcing/results, positive shear,
radius and dt, nonnegative native damping and explicit booleans. For time
diagnostics pass `history=` and `time_s=`; conductivity must be positive. Padded
operator rows/columns and cell forcing/history are zero; padded conductivity
can be supplied as neutral 1. `max_displacement_m=` is an optional explicit
caller acceptance limit; no rejected value is clipped and no native bound is
invented. The predicate checks representability, not physical consistency or
modal stability. It returns one boolean for a supplied batch; use `vmap` for
independent world rejection.

`OsmoticGeometry.environment_average` is `[cell,environment]`, with rows summing
exactly to 1 on physical cells and 0 on padding. Surface/volume are positive on
active cells and zero on padding. `osmotic_domain_valid` checks these declarations,
nonnegative totals, positive R/T/viscosity/thickness/density, nonnegative
aquaporin factor/dt and finite outputs. The map is supplied explicitly for either
native ECM sampling or membrane averaging; the component does not infer either
from geometry. No caller should treat a source PP diagnostic as a water ledger.

## Display and reset ownership

Native deformation initialization zeros displacement and creates a deep display
copy. Storage clearing resets histories (and phi), not physical geometry. The
captured tissue-handler deformation-reset fragment recreates the display copy
and tools without itself resetting existing displacement/history. This is a
fragment contract; the full cut/remapping flow remains separately owned.

At sampled write times the source fits quartic `SmoothBivariateSpline` to the
**current copied centres**, evaluates at **original membrane vertices**, adds
displacements to those original vertices, area-weights new centres and appends
display histories. Physical-world rebuild calls are commented out. Normals,
operators, areas, volumes and live physical centres remain unchanged by this
sampled display assignment. Consequently repeated identical displacement data
can produce different displayed vertices because the fitted abscissae changed.

`quartic_display_interpolator(current_display_centres, original_vertices)` builds
only the captured **global degree(4,4) polynomial** regime, for 25..256 full-rank
centres. Native FITPACK `ev` clamps evaluation coordinates to its fitted
rectangular bounds; the helper preserves this interpolation boundary rule.
It does not clamp physical displacement, implement adaptive FITPACK knots or
create tissue geometry. Native captures record ten end knots per axis in this
supported regime. Rebuild the map against current display centres each sample.

`display(d, interpolation, original_vertices, cell_vertex_weights)` returns new
flat vertices/centres; caller owns polygon grouping and histories.
`display_domain_valid` requires finite data/results and normalized nonnegative
owner weights. Physical geometry, operator rebuilds and conserved amounts must
not be replaced by this visualization output. The repeated affine example
changes by **3.692368390342338e-10 m** between samples despite fixed displacement
data; live physical geometry and stored volumes remain unchanged.

## Native evidence, refinement and freeze

Pinned revision is `5269a714aa2593ed2a6708c4516289977d8ae1a2`. Captures authenticate
installed/checkout bytes and execute getDeformation/timeDeform/display,
pressures.osmotic_P, actual check_v, Cells.graphLaplacian/curl/HH/deform_tools,
mechanical parameter assignments and actual initialization/storage/sample/reset
fragments. Inputs are explicit manufactured small graphs/DEC arrays and 25/36
display points; incidence inverses are prepared by exact Fraction elimination.
No native Voronoi seeding or full simulator is executed. The independent oracle
uses only stdlib, 80-digit Decimal owner/matrix loops and partial-pivot normal
equations for display; the native child imports neither Cells nor JAX.

Ten native limitations retain partial state/history, inputs and outcomes:
t=0 np.float failure, missing positive-clock history, negative clock, zero
conductivity, negative dt, missing PP, unbounded displacement, nonfinite steady
output, too few spline points and a collinear fit. The degenerate FITPACK fit
has produced both warnings/bad finite coordinates and a later ValueError on
the same nominal inputs. Both invalid outcomes are retained and accepted only
as limitation evidence; no stable numeric result is promised for that layout.
The supported polynomial-map constructor rejects it. Native check_v checks
NaNs only, and timeDeform calls it only on x; steady has no corresponding check.

On supplied periodic strips of 8/16/32 cells, source gradient errors are
**313.165529 / 80.125195 / 20.147501 per m**, orders **1.96660 / 1.99166**.
Actual rotation gains are **0.213388 / 0.240485 / 0.247598**, tending to **1/4**,
not identity; repeated application squares the gain. This checks native
operator arithmetic and refines its manufactured derivative, not tissue physics.

For supplied compatible solenoidal modal operators and analytic two-level
history, the disabled positive-time recurrence spans **638.719031 us**. At
32/64/128 steps, dt is **19.959970 / 9.979985 / 4.989992 us**, errors
**3.84464e-11 / 9.46354e-12 / 2.34753e-12 m**, orders **2.02240 / 2.01123**.
This is mathematical recurrence convergence, with native initialization still
broken and mode disabled. No whole-tissue settling or energy claim follows.
CPU JAX also demonstrates an exact eight-step primed-history restart over
**8 us**, independent invalid-world rejection, pressure-auxiliary compilation,
display mapping and electric sensitivity. Shared checkpoint schema, time origin,
event phase, previous histories and topology/operator identity remain caller-owned.

All eight attempts remain: 01 lint; 02 missing storage dimension; 03 reference
extrapolation disagreement; 04 lint; 05/06 unexpected degenerate spline outcomes;
07 one exact floating arithmetic grouping assertion; 08 complete qualification.
No valid-case tolerances were loosened. Metadata finalization only verifies
existing hashes/resources and copies this contract; no further scientific
computation, audit or regression is running.

```sh
taskset -c 7 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  agent-work/cells-worker-01/workfiles/check_betse_deformation.py \
  --output /mnt/workspaces/Cells/betse-deformation-development-NEW
```

All seven scientific files and evidence are frozen. Shared integration remains
Chief-owned.
