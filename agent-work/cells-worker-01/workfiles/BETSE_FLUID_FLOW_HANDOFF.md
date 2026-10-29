# BETSE fluid flow — standalone source contract

Chief-assigned B11; Cells Key Developer; 2026-10-29. Seven scientific files are
frozen at the successful bounded component receipt. Shared PROGRESS, models,
dispatch, prior components and frozen evidence were not edited. There are no
worker computations or automatic follow-up jobs.

## Qualified files and receipt

- `src/cells/processes/betse_fluid_flow.py`: law
  `betse_fluid_flow_source_v1_5_0@1`, SHA
  `b58a918da7e9e65ba066e1b117c4d4a1cd999c3a90b597d389335f184c01ab41`.
- `validation/flow/betse_fluid_flow_{fixtures,reference,native}.py` and
  `validation/flow/betse_fluid_flow_protocol.json`.
- `tests/unit/test_betse_fluid_flow.py` and own
  `check_betse_fluid_flow.py` runner.
- [Successful receipt](/mnt/workspaces/Cells/betse-fluid-flow-development-20261029-07/result.json),
  SHA `96c8ef38e86096f3713a5c97b2a7697bf2c945e9695bb4bf4f5f408b4d9a34bd`:
  **64 tests: 60 host and four CPU JAX**, zero skips/errors/failures or source
  drift. **169 artifact identities**, 39 machine-readable evidence summaries.
- Native captures: **14 valid source cases, six refinements, 11 limitations**;
  separately two valid GRN current-flow cases and two singular GRN cases.
  Three signed-coefficient limitations are accepted by source arithmetic but
  rejected by the scoped physical coefficient domain; they are not counted as
  additional valid cases.

## API and ownership

`bind_cells(owner_ids, mechanics.Operators, provenance)` freezes exactly one
active, ordered cell axis. IDs are explicit unique strings; matrices are copied
read-only. The existing deformation binder owns neighbor/incidence/DEC/curl
construction. This component does not generate geometry, repair inverses,
reorder owners, reconstruct pressure or infer membrane versus cell axes.

`bind_environment(geometry.GridBinding)` retains explicit C-order site IDs,
`(ny,nx)`, spacing and the qualified geometry identity. It selects the literal
native all-value **voltage** inverse (`lapENVinv`), including native boundary
and pseudoinverse semantics. An all-flux current/pressure inverse is a
different input/law and is rejected here. Geometry, deformation and environment
transport modules and their independent reference helpers were used read-only;
their existing inventories remain authoritative.

`cell_flow(CellForcing, operators, CellParameters, xp=...)` accepts
`electric_field_V_m[...,2,cell]` and signed `charge_density_C_m3[...,cell]`.
Viscosity and gap fraction are scalars or world arrays ending in a singleton
axis. It computes `E*rho*gap_fraction/mu`, then the negative inverse solve, then
the actual inherited cell curl/inverse/curl with `rot_only=True`. The returned
velocity is **m/s**, stream auxiliary is **m2/s**, and the numeric divergence
is **1/s**. The YAML comment explicitly defines gap junction surface as a
dimensionless fraction of cell area. It is not an area in m2.

`environment_flow(EnvironmentForcing, operators, EnvironmentParameters, xp=...)`
accepts electric field `[...,2,ny,nx]`, literal `v_env` potential and supplied
diffusion weight `[...,ny,nx]`, plus viscosity, vacuum permittivity and relative
permittivity on singleton world axes. It returns the source slip expression,
first inverse solve, rotational output, both HH potentials, discarded scalar
gradient and numeric divergence. The source all-value scalar/potential
boundary RHS is zeroed during HH; this is not a no-slip boundary law.

`cell_valid` and `environment_valid` return per-world finite/domain predicates.
Require viscosity >0, gap fraction in [0,1], nonnegative supplied weights,
positive permittivity/spacing and finite fields/operators. Shapes are checked
statically; invalid values are not clipped or repaired. Bare kernels retain
ordinary numeric behavior outside these domains for diagnostics.

`flow(..., fluid_flow=False, environment=None)` is the stateless **host** gate;
disabled calls return `None` with no input validation or writes. Enabling
requires an exact boolean and checked bindings/domains. The ECM argument is an
explicit `(forcing, binding, parameters)` triple. Bare kernels support JIT and
world batching. No mutable simulation object, time step, physical pressure,
water volume or history is part of this API. Enabling the standalone gate does
not enable BETSE itself.

## Source reachability and preserved defects

Pinned BETSE **1.5.0**, revision
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. Twelve installed/checkout source
identities are authenticated and copied externally. Actual `getFlow`,
`HH_Decomp`, cell graph/HH/curl, finite-difference derivatives and grid inverse
bodies execute on explicit manufactured layouts. Five narrowly identified
loader/initialization/caller/consumer/GRN fragments are executed; appended
capture return plumbing is identified. This is not a full native simulation.

The loader unconditionally sets **fluid_flow=False**, **mu_water=0.01 Pa.s**,
and **td_deform=False**, ignoring hypothetical fluid configuration entries.
Manually enabling flow zeros cell, membrane-GJ and ECM output arrays but does
not build the cell graph inverse. That build is behind deformation and the
forced-off dynamic deformation flag. Source capture demonstrates the missing
inverse failure and the partial ECM writes before the later cell failure.

The full loop updates ECM transport **before** `getFlow`, then runs deformation,
concentration updates and voltage recalculation. Voltage is also initialized
before entering the loop, so init-core membrane-sized electric fields are not
the ordinary first-loop field. Flow consumers receive the previous flow at a
transport step, initially zero. The fast loop has no `getFlow` call. ECM ionic
and molecular transport and membrane molecular drift can consume ECM flow;
native GJ ionic transport does not consume the sampled cell velocity here.

No `P_cells`, osmotic `PP` or osmotic-pressure arrays are read by `getFlow`.
Cell HH uses only its rotational branch. ECM HH computes a scalar potential
and its gradient, then `getFlow` discards them. None of these quantities is an
independently solved physical pressure in Pa.

**The ECM source has a dimensional defect.** Its Helmholtz–Smoluchowski
expression already has velocity dimensions **m/s**, then an inverse Laplacian
adds m2. Both first-solve and final ECM output therefore have **m3/s** dimensions;
the HH potentials have **m4/s**, divergence has **m2/s**. These are named native
outputs, not physical volume flow or velocities. They must not silently feed
the earlier transport component's m/s advection input. No conversion or missing
length scale is invented. With unchanged supplied fields/weights, doubling all
lengths quadruples the output and multiplies the HH potential by eight.

The ECM source uses absolute supplied `v_env`, not an explicit interfacial zeta
potential. A +0.02-V offset at fixed E changes the fixture output by
**2.6727605676e-18 native m3/s**. Its tangential boundary field reaches
**4.0511150621e-18 native m3/s**, while normal boundary values are only
**3.9934886748e-33** in this zero-scalar-boundary fixture. Source divergence
reverses boundary derivative signs: boundary divergence reaches
**2.0255575310e-13 native m2/s**, versus **6.3108872418e-30** in the interior.
The discarded scalar auxiliary reaches **5.2761475526e-23 native m4/s**.
Thus neither no-slip nor whole-grid incompressibility is certified. A two-row
grid loses the entire rotational source when all sites are perimeter sites.

Zero viscosity, absent inverses/charge owners, mismatched axes, NaNs and signed
coefficients remain in source evidence. No source failure is suppressed. The
inherited cell HH does not acquire an idempotent projection guarantee.

`grn_current_flow(current_A_m2, concentration_mol_m3, valence, faraday_C_mol)`
is a separate source formula: `-J/(F*mean(c)*mean(z))`, with explicit species
and grid axes and m/s output. Its actual GRN caller sets fluid_flow=True without
calling `getFlow` or supplying cell flow. Mean valence can be zero for ordinary
oppositely charged species; zero mean concentration also gives nonfinite
source output. `grn_valid` rejects these domains without a denominator floor.
The source config readers use two spellings, `recalculate fluid` initially and
`recalculate fluid flow` on reinitialization. Captures record both; no complete
GRN execution, config migration or hidden current conversion is claimed.

## Independent checks and refinement

The reference imports only stdlib and frozen independent reference helpers.
Cell forcing uses 80-digit Decimal arithmetic and existing independent DEC/HH
owner algebra; ECM uses independent grid stencils/pivoted elimination and new
loop-based derivatives/HH arithmetic. Parameter zero/sign/scaling, pressure
independence, explicit axes/ownership and native failures are checked alongside
actual source captures.

Periodic 8/16/32-cell strips give errors **6.4075061364e-10 /
1.6212906332e-10 / 4.0650825802e-11 m/s**, orders **1.98262022 /
1.99578617**, against the source operator's quarter-amplitude continuum limit.
Response relative to force/k² is **0.22470418 / 0.24359940 / 0.24839517 → 0.25**.
This preserves the source's four-membrane averaging; it does not establish a
physical Stokes limit.

ECM 5/9/17 grids use a fixed 1-mm boundary-centre domain and a manufactured
first-solve vector. Both HH first derivatives are discrete, giving the exact
source gain **cos²(theta/2)**. Errors are **0.07322330470 / 0.01903011687 /
0.004803679899 native m3/s**, orders **1.94401846 / 1.98607250**. This numerical
manufactured field is not a physical unit-velocity experiment. For reference
comparison, HH potentials are divided by h and divergence multiplied by h so
all auxiliary comparisons use the established output-field tolerance in the
same units.

CPU JAX covers JIT/batches/world order, per-world invalid coefficients, finite
zero-E/zero-potential/zero-current derivatives and separate GRN denominators.
Seven independent forcing snapshots split after three agree at the stated
tolerance; changing batch shape gives **5.1768996905e-31 m/s** roundoff, so
bitwise equality and dynamic/checkpoint restart are not claimed.

## Execution and evidence retention

CPU7, one BLAS/OMP/MKL/NumExpr thread, CPU-only x64 JAX, no GPU, no persistent
compilation cache, no dependency changes. Native/host/JAX guarded wall times
were **2.030 / 5.072 / 12.651 s**. Peak process-tree RSS **281,755,648 B**;
minimum available host memory **16,883,544,064 B**. Existing venv versions are
recorded in the receipt and authenticated native manifest.

Attempts 01/03 retain lint failures; 02 is source-only preflight; 04 retains the
incorrect initial ECM analytic gain; 05 retains the auxiliary-unit comparison
failure; 06 retains the unsupported bitwise batch assertion; 07 qualifies.
Numerical tolerance constants are unchanged. The analytic expectation,
dimensional comparison and reproducibility claim were corrected explicitly.

`finalize_betse_fluid_flow.py` performs metadata/hash/XML/resource verification
only, copies this contract and itself to a fresh external handoff directory,
and records every development attempt. Scientific execution stops at the
successful receipt. No coupled-tissue, physical pressure/no-slip/Stokes,
physical water-volume, material-remap, energy/ATP or shared checkpoint claim
follows from this component.
