# Native stochastic physiological perturbations

Cells Key Developer, B14 component handoff, 2026-10-29. Seven scientific files
and qualified evidence are frozen. Chief owns active-cut/shared physiology
integration; no shared or earlier frozen files were edited.

Complete receipt:
`/mnt/workspaces/Cells/betse-perturbations-development-20261029-03/result.json`,
SHA256 `71563291ed6c1a9250e0d0759037f78fef2185d9953aa225b5c91bf47ccec579`.
Process `src/cells/processes/betse_perturbations.py`, SHA256
`75fbb75e84d23ab3095230117cd23fef3bf04fecb71e09ba5cb256aea64fbc56`.
Law ID `betse_perturbations_source_v1_5_0@1`.

## Native arithmetic, timing and scope

Authenticated AST bodies/statements/guards execute from pinned installed BETSE
1.5.0 revision `5269a714aa2593ed2a6708c4516289977d8ae1a2`. Ten source/YAML files
match the checkout and are copied externally. A NumPy proxy delegates actual
random calls unchanged while recording arguments, outputs and full before/after
MT19937 states. Phase enumeration labels and unrelated empty event handlers are
normalized support inputs. Actual update_Co/div_env/no_negs, single_cell,
TissueHandler fire_events/makeAllChanges, selected Simulator blocks and disabled
microtubule methods run. Neither production Cells nor JAX is imported in that
child. No full solver, tissue, geometry generation, cut or remap is executed.

Static noise always draws M uniforms U in [0,1), including level=0, then writes
only potassium as `(1+level*U)*Dm_K`. This is positive-biased for positive level,
not zero-mean noise: multiplier mean=1+level/2, variance=level^2/12. Finite signed
levels are retained where the resulting permeability is nonnegative. Missing K
raises upstream after the draw, even at zero level. Permeabilities are m2/s;
uniforms and static levels are dimensionless. Native list/array containers are
both captured.

**Dm_base is copied before static noise.** SIM loop start calls fire_events,
whose finalization overwrites current Dm with base+scheduled. Thus first SIM
finalization removes this static perturbation. INIT does not call that block.
`static_initialize` returns current/base/zero-scheduled `StaticState` without
mutating input; `finalize_scheduled` preserves this exact distinction. Do not
silently make native static heterogeneity persistent through SIM events.

Dynamic protein noise draws fresh M uniforms and passes
`level*(U-0.5)` to actual update_Co as inward-normal flux, in mol/(m2*s).
It runs only when solver=normal, phase=SIM, dynamic_enabled and P enabled.
Source guard is equality to 1; `Controls` requires explicit bool flags. The
fast solver has no dynamic-noise site. Zero dynamic level still consumes a draw
when its guard is active. Boundary closure does not mask this noise branch.
`dynamic_active` supplies the declared sampling guard; callers must skip native
sampling when it returns false.

There is one update per loop invocation, including label t=0. Each update uses
p.dt, not the difference between time labels or sampled output times. No
sqrt(dt) rescaling occurs. At fixed physical duration T=N*dt and fixed level,
cell amount variance is
`T*dt*level^2*sum(owned_membrane_area^2)/12`, rather than a dt-independent Wiener
limit. Irregular time labels with the same number of calls/dt produce the same
captured draws/updates. Changing output sampling does not define a new RNG law.

## Explicit owners and flux accounting

`bind_layout(Layout(...))` copies/freeze stable cell, membrane, environment and
ion axes; explicit membrane owners; positive membrane areas and cell/source
environment volume parameters; ordered boundary-cell occurrences and provenance.
Unique axes are bounded by 4096 IDs; actual component qualification uses small
3-cell/7-membrane layouts plus a 7-cell axis-ambiguity limitation. Dense owner
maps are compiled; this is not a large-layout performance qualification.
Global membrane order is authoritative for native sequential sampling and its
duplicate-scatter semantics. No physical geometry or owner map is inferred.

`ProteinState` fields are cell/membrane/environment concentrations in mol/m3,
with final explicit N/M/E axes and optional leading world axes. Scalar controls
are per leading world (no implicit owner axis). `protein_step` returns new
buffers, inward membrane flux, cell/environment amount changes in mol and the
global balance residual. Inputs are not mutated. Membrane concentration is
rebuilt from updated cells only when noise is active; inactive noise preserves
its prior membrane buffer.

Environment mode must be explicit:

| Mode | Source behavior and acceptance |
| --- | --- |
| matrix | Area-weighted scatter of every membrane flux, divided by the uniform environment volume; cell/environment amount changes cancel. |
| source_fast | Native last duplicate assignment at each environment site, multiplied by that site's summed membrane areas; literal source arithmetic, with conservation checked separately. |
| mixed_bath | Non-ECM source mean mixing, represented by one explicit shared-bath owner. Effective bath volume is M*vol_env, not vol_env. |

The duplicated fast-ECM panel retains a balance defect
**-5.935102132663108e-23 mol** on its first call. `protein_domain_valid` defaults
to conservative acceptance and rejects it. `conservation_required=False` checks
the finite/nonnegative literal result without asserting conservation. Injective
fast mapping is separately qualified. No correction is silently added.

Non-ECM source accepts an initial membrane-length environment vector then
collapses it to a scalar mean; heterogeneous collapse is captured as an
unsupported ownership path. Accepted mixed_bath input uses one shared scalar
site. Actual source mean division introduces the M factor in its effective
volume; dropping that factor gives the wrong amount budget.

Later native update_all_concs/no_negs can clip negative cell concentrations,
without clipping the matching membrane copy or environment. The negative panel
preserves stale/negative membrane values and clipping evidence. Accepted
component domains require finite nonnegative input/output concentrations and
positive dt; no clipping, reservoir creation or hidden balance repair occurs.
Other transport and voltage updates are outside this component.

`boundary_mask` takes an explicit chosen cell-owner index and cell/membrane
domain, then adds the source offset. Native single_cell chooses among repeated
boundary entries, so selection probabilities follow occurrence counts. It
samples once at callback construction, with constant dynamics. Subset pc lengths
can fail after consuming the choice; equal N=M selects membranes first even
when the caller intended cells. Supported binding uses explicit domains. Negative
finite offsets remain literal source values; no [0,1] clipping is added.

## Two distinct RNG laws

`native_stream`, `sample_native`, `native_stream_manifest` and its loader use
`numpy_mt19937_legacy_state_with_gaussian_cache@1`. A local RandomState is set
from all 624 words, position, has_gauss and cached Gaussian value, with exact
recorded NumPy version. Process-global NumPy state remains untouched. The
native capture/replay NumPy version is 2.5.3. Invalid/incomplete/all-zero state,
bad cache flags, version mismatch and stale identities are rejected.

Sampling sites are static_K, protein_flux, boundary_choice and
microtubule_gaussian. The latter records standard-normal draws; source normal
scale transformation consumes the same native RNG/cache, verified against its
actual call. An odd seven-normal draw leaves a cached value; the replay panel
preserves **-0.9117195369572063** through uniform draws and emits exactly that
value next. Uniform, normal and choice calls must remain in source order. Native
owner order, other global RNG consumers, repeated initialization and phase guards
matter; this component does not own every native RNG site. Static zero-level
draws must not be optimized away. Geometry/profile RNG sites remain separate
frozen packages.

`StableCoordinates`, `stable_pairs`/uniforms/normals and `sample_stable` use the
separate law
`threefry2x32_seed_world64_tick64_owner_sha256_site_open52_boxmuller@1`.
CPU JAX Threefry folds seed, a version tag, site, both uint64 world/tick words,
and all eight little-endian SHA256 words of domain+NUL+literal owner ID. Open52
midpoints avoid 0/1; one Box-Muller normal is formed per owner from each pair.
This is not NumPy RandomState or a claim of native sample equivalence.

World reordering/batching and membrane owner reordering/subsetting preserve
identity samples exactly; site tags separate perturbation families. World IDs
7 and 4294967303 and tick 1099511627779 are explicitly distinct in qualification.
High/low words must be supplied as uint32 arrays and JAX x64 is required.
The stable categorical convention sorts unique cell IDs and keeps their native
occurrence multiplicities. Source list order affects native choice replay;
canonical order makes the Cells choice invariant to list permutation while
retaining the same declared categorical weights.

Logical tick is an explicit draw coordinate, not derived from floating time.
Reusing the same seed/world/site/owner/tick intentionally replays the same draw.
Callers must allocate distinct ticks for distinct draws they want independent,
including repeated static initialization; no hidden phase counter advances.
No bit-exact cross-device, cross-version transcendental-normal or full simulator
RNG promise follows. Runtime/library/code pins and packet samples are retained.

`prescribed_draw`/draw manifests bind site, tick, layout identity, exact ordered
owners, numeric values and provenance. Native/stable samplers both produce this
format. Packet hash checks detect stale order/owner/layout; they do not infer a
new geometry or remap a packet after cuts. An explicitly prescribed packet is
not itself statistical evidence of an RNG law.

## Replay and disabled diagnostics

`Replay` contains ProteinState, StaticState, native RNG state or stable root
coordinates, logical next tick and an explicit component clock in seconds.
`replay_record` and `restore_replay` hash/validate controls, complete unbatched
active-component buffers, layout/law/RNG identities and clock. Signed scheduled
modifiers are retained as source numeric buffers. The caller supplies clock
meaning/epoch; the qualified scaffold uses accumulated update duration, distinct
from source loop labels that start at t=0. A changed dt/phase/solver/guard/level
requires an explicitly new control record. This is component replay I/O, not
shared simulator checkpoint migration or ownership of unrelated RNG consumers.

Native replay is exact over seven updates split after three, including buffers
and final RNG state (accumulated update duration **0.014 s**). CPU JAX replay
with the same native sample tape is exact across a split; CPU/JAX RNG engines
are not called equivalent. Stable coordinate snapshots reproduce future samples
exactly, and packet identity prevents reuse under stale owner order.

Microtubule import/configuration/init/update integration is commented out in
the source. Missing parameters/correlation fields and the drag initializer's
NaN path remain captured. No path is activated. `micro_noise_scale` and
`micro_angle_step` require `diagnostic=True` and expose only the literal numeric
noise term/angle increment, with separately prescribed deterministic drift.
Full microtubule kinetics/projection/geometry are not production APIs here.

The source scale mixes vector norm with kB*T, includes length^2 under the square
root, then adds the result to an angle. Its physical dimensions are unresolved;
it must not be interpreted as a validated rotational Brownian law. Draw occurs
only if dilation>0; Gaussian noise is not multiplied by the chemical modulator.
Zero dilation preserves the state without a draw; negative time produces NaNs
upstream and is rejected. Positive drag/length/thermal controls, finite fields
and scale are checked for the isolated diagnostic. Disabled angle/RNG replay
uses explicit packets and prescribed inputs, outside active-state snapshots.

## Qualification and resources

The complete component passes **61 tests: 57 host and four CPU JAX**, no skips,
failures or source drift. It includes **21 native valid cases, 14 retained
limitations**, independent stdlib/80-digit Decimal owner/transform arithmetic,
and authenticated source dispatch/order checks. The expected negative-time
sqrt RuntimeWarning remains in the host log; invalid domain is rejected.

Native moment panels use 32768 uniforms and standard normals; categorical
sampling uses 8192 draws. Means/variances are **0.4969219781/0.0829247910** and
**-0.0032252249/1.0035966849**. Boundary counts **2749/1356/4087** follow weights
1/3,1/6,1/2, maximum absolute standardized count deviation **0.42969**.
Independent analytical moment checks use six-standard-error bounds.

Stable-law 8192-sample uniform mean/variance are
**0.4998722729/0.0824324353**; standard-normal mean/variance
**-0.0075393836/1.0145642539**. Boundary counts **2694/1373/4125**, maximum
absolute standardized deviation **0.85938**, meet the same explicit bounds.
Finite moment/count checks are not proofs of all distributional properties.

Protein panels use 512 independent sample rows at fixed duration **0.006 s**:
three 0.002-s calls versus six 0.001-s calls. Analytic amount variances halve
exactly; observed variances meet the declared six-error bounds. Shared
cell/environment anti-covariance follows the explicit areas/owners and each
sample's amount balance closes. No Brownian rescaling was introduced.

JAX checks batching, world/owner/subset/site isolation, exact replay, per-world
invalid-input isolation and analytical protein/noise Jacobians. No tissue
distribution, energetic/ATP cost, electromechanical closure, stochastic channel
gating, evolving geometry or physiological settling claim follows.

Native/host/JAX guarded times **42.337 / 3.787 / 22.215 s**. Peak sampled tree
RSS **333,107,200 B**; minimum available host memory **17,925,255,168 B**.
CPU7/one thread, no GPU or persistent compilation cache. Native uses existing
BETSE venv; host/JAX use existing CPU venv (NumPy 2.5.3, JAX/JAXlib 0.11.1).
No package was installed/changed. Attempt 01 is source-only preflight; attempt
02 retains lint failures; attempt 03 is the complete pass with 148 hashed
artifacts. No scientific follow-up/audit/regression is queued or active.
