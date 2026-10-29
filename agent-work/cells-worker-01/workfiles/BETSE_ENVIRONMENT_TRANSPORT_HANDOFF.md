# Native environment transport, barriers and explicit conservative faces

Cells Key Developer B08 handoff, 2026-10-29. Seven scientific files and qualified
evidence are frozen. Chief owns coupled fields, active cuts, calcium/ER and
shared physiology integration. No shared or earlier frozen file was edited.

Qualified receipt:
`/mnt/workspaces/Cells/betse-environment-transport-development-20261029-04/result.json`,
SHA256 `c0df59be8d95908a0202dec9e0703d04eee4473fdfa5d6053e3522882379c6ae`.
Process `src/cells/processes/betse_environment_transport.py`, SHA256
`7cf5b793964f9b34dccd85b04982a3c2f2e92f3b043b8e04a30a647409afe42c`.

The two laws are deliberately distinct:

- `betse_environment_transport_source_v1_5_0@1`: literal native collocated
  arithmetic, including its source defects and stage accounting.
- `bernoulli_fitted_environment_faces@1`: separate conservative face flux,
  external-bath ledger and monotone forward-Euler acceptance domain.

## Source coverage and what actually runs

Native child executes authenticated AST methods/statements from BETSE 1.5.0,
revision `5269a714aa2593ed2a6708c4516289977d8ae1a2`. Eight source/configuration
files match installed package and checkout and are copied into evidence.
Actual Simulator initDenv/update_ecm, FD gradient/diff/divergence/integrator,
Nernst-Planck flux, gaussian_filter, bath event initialization/firing and pulse
run. Full molecule_mover runs with Dm=Dgj=0, ignoreGJ=True and normalized explicit
owner inputs, isolating its extracellular branch; actual update_Co/div_env zero
exchange still executes. Wound coefficient statements execute on explicit
targets, without running selection, cutting or geometry reconstruction.

Recording wrappers delegate unchanged helper arithmetic and retain arguments,
outputs, warnings and failures. Neither production Cells nor JAX is imported in
the child. There is no full native solver, tissue, active membrane/GJ transport,
geometry generation or cut. Supplied cell/membrane/field objects are normalized
component inputs; YAML/whole-world parameter construction is not claimed.

Constants are explicit inputs: pinned q=1.602e-19 C, kb=1.3806e-23 J/K and
F=96485 C/mol are retained rather than silently replaced by modern SI-derived
values. Diffusion is m2/s, field V/m, velocity m/s, concentration mol/m3,
membrane/face flux mol/(m2*s), volume m3, amount mol, charge C and dt seconds.
Species valence is explicitly dimensionless. Extra molecule mobility is
m2/(V*s). Temperature and constants must be positive in accepted domains.

## Ownership, coefficients and modifiers

`bind_grid(GridSpec(...))` requires explicit unique stable site/species/face IDs,
valences, ny/nx, C-order site coordinates, positive uniform spacing and height,
oriented internal owner pairs and boundary owners/sides. Every nearest internal
contact and physical perimeter face must be declared once. A corner has two
boundary faces. Face orientation/order may change explicitly; physical updates
are invariant within tolerance, while binding identity changes.

Binding recomputes face normals/distances, areas=delta*height, site
volumes=delta^2*height and half-cell boundary distance=delta/2. Inputs/compiled
arrays are copied/read-only. Limits are 1024 sites and 32 species; qualification
reaches 32x32 native grids and 16x16 conservative refinement, not a maximum-size
performance guarantee. Fields use explicit [...,2,site] axes; concentration and
diffusion use [...,species,site]. `owner_to_grid`/`grid_to_owner` make spatial
conversion explicit. Same counts do not establish interchangeable domains.

`init_barriers` consumes explicit `Regions` occurrence lists and nonnegative
free diffusion/relative TJ/adherens/tight factors. It first fills free D,
overwrites cluster sites with freeD*adherens, then overwrites the concatenated
three boundary sets with freeD*tight*relativeTJ. Tight values take precedence at
overlaps. Duplicate target occurrences remain in metadata. Sodium is required
for the source common weight `D_Na/max(D_Na)`, not division by free sodium D.
Amplifying factors >1 therefore change normalization of other regions too.
Absent sodium and zero normalization are rejected, with raw native failures/
NaNs retained. No epsilon/floor or coefficient clipping is added.

Ion transport multiplies its absolute D_env species map by the prescribed
species TJ_modulator. Generic molecules instead use their own Do times the
sodium-normalized common weight and a molecule-specific Ftj at TJ targets;
they do not use the ion TJ_modulator. `molecule_diffusivity` preserves this
distinction. Native advanced assignment applies Ftj once at repeated target
locations, rather than compounding it for every occurrence. `ignore_TJ` bypasses
both common weighting and Ftj.

The non-ECM initialization path has a species-only free-D vector and a sigma=1
Gaussian-reflected common barrier map, with no ionic grid transport. It is
exposed separately through `legacy_non_ecm_weight`. `reflect_gaussian` matches
pinned sigma=1/2, truncate=4, reflect behavior; constant dielectric Chi capture
is diagnostic, without a new electrostatic field model.

`wound_barriers` sets explicit selected D entries to freeD*woundFactor*relativeTJ
and common weights to woundFactor. It neither renormalizes the map nor changes
TJ target lists/modulators/base snapshots. It returns arrays; callers own
current-versus-base coefficient state and any actual cut/geometry changes.

Zero diffusion blocks diffusive/thermal-drift transfer in the conservative law.
Advection and the separate molecule mobility term are independent source
mechanisms and can still carry material when D=0. A diffusion barrier is not a
claim of an impermeable fluid/mobility interface.

## Literal source stencil and its limits

`source_step` copies input and clamps perimeter **site** concentrations to the
species bath values before transport. It evaluates source positive one-sided
boundary/central interior gradients and literal Nernst-Planck flux:
`-D*grad(c) + (D*z*q/(kb*T)+mu)*E*c + velocity*c`.
Source flow is included only under the explicit flow flag. Ionic update has
mu=0; the generic molecule path supplies mu and time dilation.

Source divergence uses a different diff helper whose boundary derivatives have
the opposite sign. The composed central gradient/divergence has a two-site
interior stencil. Its checkerboard interior is unchanged in a retained panel.
The zero-bath impulse panel injects **9.53674316406468e-21 mol per species**
during the collocated step, despite zero initial perimeter amount/first face
exchange. These are preserved defects, not evidence of conservative transport.

The output is not clamped back to bath after Euler transport. Optional neighbor
smoothing when sharpness<1 preserves that current perimeter but can change
total amount. `SourceResult` separates clamp, collocated and smoothing amount
changes. Their arithmetic sum matches the actual update; **the collocated or
smoothing change is not an inferred physical bath flux**. Do not invent a
reservoir compensation and call it source conservation.

`source_domain_valid` checks finite shapes/controls, positive thermal/dt,
nonnegative diffusion/concentrations/output and sharpness in [0,1]. It is a
literal numerical-domain predicate, not conservative physical acceptance.
The conservative law has a separate predicate. Native ionic update can leave
negative concentrations; molecule_mover instead raises on negatives. The
explicit no_negs clipping diagnostic changes amounts and is not called by
update_ecm. Clipping/floors are not used for accepted transport.

The molecule all-zero path can skip transport when bath<=1e-15 and returns
different flux shapes; small-bath suppression is retained as a limitation.
Malformed native field shapes can fail after perimeter writes; standalone
functions use an immutable explicit owner interface rather than reproducing
unsafe alias mutation. Missing TJ modulator, degenerate grid, zero temperature,
negative coefficients and unstable Euler paths remain captured.

## Bath setter order and external charge

`compile_baths`/`apply_baths` preserve K_env then Cl_env then Na_env family order,
source pulses and baselines. K writes K and counterion M; Cl writes Cl and Na
under its enabled-ion guard; Na writes Na and M. Later assignments overwrite
earlier salt contributions. K/Na are unguarded and require the appropriate
declared owners. Positive transition is required; signed finite amplitudes and
reversed pulse clocks remain literal where output domains permit them.

Overlapping events need not remain charge neutral: the retained panel ends at
[Na,K,Cl,M]=[19.6,4.2,14,12.6] mol/m3, with bath charge-density change
**-270158 C/m3**. `bath_domain_valid(require_neutral_pair=True)` rejects that
claim; the ordinary setter predicate and charge ledger preserve the literal
external values. No local electroneutrality or Poisson correction is invented.

For non-ECM events, full concentration vectors are assigned from legacy
conc_env_k/cl/na attributes, without counterion writes or scalar boundary
updates. The successful normalized legacy case and absent-attribute failure
are separate. Production requires explicit baseline arguments; it does not fix
or claim full native parameter-loader compatibility.

## Conservative face operator and acceptance

`face_step` takes explicit concentrations/diffusion, prescribed electric/velocity
fields, Thermal, dt, boolean boundary-face open masks and per-species/per-port
bath concentrations. Internal D is the harmonic mean. Electric and flow fields
are averaged to internal faces and projected on the declared orientation;
boundary ports use the adjacent site field and outward normal.

For each face, w=(D*z*q/(kb*T)+mu)*E_normal+u_normal, Pe=w*length/D and
`J=D/length*[cL*B(-Pe)-cR*B(Pe)]`, B(x)=x/expm1(x). The shared frozen Bernoulli
primitive supplies the removable zero-Pe limit. At exactly D=0 the separate
upwind advection/mobility limit is used. This is a distinct discretization,
without a native flux/stencil equivalence claim.

Each internal amount transfer is applied with opposite signs to its two owners.
Open boundary ports link to explicitly prescribed reservoirs at half-cell
distance. Closed ports have zero flux; no site clamp is used. Positive outward
boundary flux increases the external bath ledger. `FaceResult` returns
concentrations, amounts, per-site deltas, internal/boundary fluxes, signed
per-face bath amount changes, species balance and global charge residuals.
The bath is an explicit infinite-reservoir ledger, not an evolved finite bath.

`face_domain_valid` requires finite nonnegative concentrations/D/bath, positive
thermal constants/dt, |Pe|<=500, nonnegative result and outgoing-rate Euler
Courant<=1, plus species balance within 3e-13 relative tolerance. No timestep
adaptation, clipping, positivity floor, hidden mixing or rejected-trial commit
is implemented. Callers own trial acceptance and any timestep control. Field
and bath work, thermodynamics and current/Poisson closure are outside scope.

Fixed W/E face baths retain a linear steady profile; a compatible constant-field
Boltzmann exponential balances to maximum flux **4.336808689942018e-19
mol/(m2*s)**. Open-bath panel residuals are [-3.0092655381e-36,0] mol and
charge residual -2.9034898544e-31 C. These are component arithmetic limits,
not physical tissue/energetic closure.

## Qualification, refinement and integration boundary

Complete pass: **75 tests, 71 host/four CPU JAX**, no skips, failures or source
drift. Actual native capture includes **23 valid cases, 19 limitations and three
native interior-refinement grids**. Independent stdlib stencil/region/Gaussian/
pulse loops and 80-digit Decimal face flux/owner budgets import no production,
NumPy or JAX. Closed/open species and global charge ledgers, barriers, drift,
advection, zero-D mobility, positivity and domain failures are checked.

Native interior relative stencil errors at 8/16/32 are
**0.1894305309 / 0.05035879645 / 0.01278516923**, orders
**1.91135316 / 1.97777255**. Three boundary layers are excluded; this does not
qualify source boundary convergence or resolve its checkerboard defect.
Conservative sealed cosine-mode errors at 4/8/16 are
**0.05035879645 / 0.01278516923 / 0.00320863596**, orders
**1.97777255 / 1.99443924**.

Forward-Euler temporal errors over **0.00059740483196 s** at 8/16/32 updates are
**1.9998241150e-4 / 9.9211820413e-5 / 4.9413658783e-5 mol/m3**, orders
**1.01128920 / 1.00560214**. Maximum Courant decreases
**0.32842678 / 0.16421339 / 0.08210669**. These are prescribed constant-D mode
checks; no general heterogeneous-field/tissue recovery claim follows.

CPU JAX covers literal source/coefficient/bath paths, conservative batching,
invalid-world isolation, zero-field/zero-D derivative limits, and exact eight
component updates split after three (**8 us**). The Jacobian is nonnegative and
its columns sum to one in the sealed diffusion panel. This is fixed-operator
component restart, not shared checkpoint continuation.

The optional frozen geometry interface checks identical explicit grid owner
coordinates/volumes without editing that component, rebuilding a world or
remapping physical amounts. `grid_manifest` validates geometry/site/species/
face/measure identity, including JSON round trips. Current diffusion/modulators,
barrier bases, bath controls/ledgers, fields and evolving state must be persisted
separately; this manifest is not a full checkpoint format. Coefficient/flux
operators do not perform cutting or authoritative geometry updates.

Native/host/JAX guarded times **4.039 / 3.787 / 20.217 s**. Peak tree RSS
**325,390,336 B**; minimum available host memory **19,727,589,376 B**.
CPU7/one thread, no GPU/persistent cache or package changes. Native NumPy/SciPy
2.5.3/1.18.1; CPU NumPy 2.5.3, JAX/JAXlib 0.11.1. Attempts 01/03 preserve lint
failures; 02 is source-only preflight; 04 is the complete qualified pass with
164 artifact hashes. No follow-up scientific audit/regression is queued or
running; shared and previous frozen evidence remain untouched.
