# Native tissue profiles and intervention targets

Cells Key Developer component handoff, 2026-10-28. Scientific files and qualified
evidence are frozen. Chief owns shared model/solver/cut/checkpoint integration.

Qualified component:
`/mnt/workspaces/Cells/betse-tissue-profiles-development-20261028-05/result.json`,
SHA256 `d7973ce0c448a57e9e3b56d9013f9c217a9b2307321e95c94c1c9dea0571f50b`.
Process: `src/cells/processes/betse_tissue_profiles.py`, SHA256
`840482d6612a4f0502eac9214acc1d90559345cb757d847f72f4dc8843502be1`.
Law ID: `betse_tissue_profiles_source_v1_5_0@1`.

## Selection and ownership interface

`validate_layout(Layout(...))` returns copied, read-only coordinates and explicit
stable cell, membrane and environment IDs. Every membrane has a cell owner, an
explicit optional environment owner, and an explicit position in its cell's
membrane list. Environment mappings may be noninjective. Empty axes are allowed;
finite nondegenerate bitmap bounds are still required. `layout_identity` hashes
IDs/order, ownership, centres, bounds and optional seed-fill tags. Count equality
never establishes domain equality.

`compile_profiles(layout, default, profiles, ion_enabled=..., is_ecm=...,
enabled=...)` creates an immutable `Binding` with stable-ID target sequences,
pick-time cell IDs, final source cell ordering and read-only numerical kernels.
The ion order is exactly `Na,K,Cl,Ca,M,P`; diffusivities are finite nonnegative
m2/s. Disabling profiles produces no active definitions. The default definition
is always ALL and insular, regardless of its configured selector. It remains a
member of every cell when later profiles overlap it.

Selectors are ALL, exact case-sensitive COLOR, INDICES, PERCENT and IMAGE.
An additional explicit `ids` selector is a Cells interface. INDICES requires a
matching layout identity and an integer cell axis; order and duplicates survive.
Negative, boolean, floating and out-of-range indices are rejected even where
native NumPy permits wrapping or selects inconsistently across domains. COLOR
requires explicit SVG seed tags; it performs no color normalization.

PERCENT requires a complete externally resolved stable-ID permutation for each
picker. Native `cell_i[:]` is a view: shuffling it mutates cell order even for
zero percent. Stored ALL **cell** arrays then alias the final order, while their
already materialized membrane/environment sequences keep pick-time order. The
binding preserves both results without mutating its authoritative layout.
Native selection size is `int((percent/100)*N)`. Production consumes no RNG;
native RNG state/permutations are captured in external evidence. Stream parity
and persisted RNG ownership are caller responsibilities.

IMAGE accepts `Bitmap(grayscale_F)` decoded pixels. `bitmap_data` applies native
float32 quantization, every value unequal to 255 becomes ink, then vertical flip.
`bitmap_values` evaluates the transposed bilinear interpolation at actual nodes
with rectangle clamping; every nonzero interpolated value selects. This is not a
filled convex hull. Native also constructs an unused cubic helper and a hull;
supported masks therefore require finite square 4..1024 grids and at least three
noncollinear ink pixels. Native image decoding does not use alpha as an opacity
mask. File decoding is outside the production kernel; callers retain asset and
decoder provenance. The qualified native captures execute actual Pillow and
SciPy code and retain asset hashes and decoded masks.

`bind_targets(binding, names, domain=...)` concatenates requested profiles in
order with all repeated occurrences. Domains are `cell`, `membrane`,
`environment`. Native omits environment keys for empty/non-ECM selections;
`environment_declared` retains this distinction and environment event binding
rejects absent keys. `gather_owner_field(values,target,domain=...,axis=...)`
requires both the explicit owner domain and numerical axis.

`apply_profile_diffusion(initial[...,6,M], kernel, xp=...)` overwrites only
enabled ions at selected membranes in insertion order; later profiles win.
Membership maps remain overlapping. `insular_membrane_weights` takes an explicit
reciprocal membrane-partner map and original cell adjacency. All insular
region-crossing blockers combine; later profiles do not reconnect earlier cuts.
It returns membrane weights, without rebuilding physical geometry or neighbors.
Host binding must validate reciprocal partners before JAX execution; JAX receives
trusted compiled index arrays. Native neighbor counts remain original counts.

`global_gj_prefix_targets(layout,percent)` preserves the native target bug:
integer percentage is clamped to 1..100 and a prefix of original membrane order
is selected. The source shuffles a copied array and ignores it. Production does
not consume that otherwise irrelevant Python RNG draw.

## Scheduled controls and kernels

`compile_interventions(binding, interventions, event_capacity=...,
target_capacity=...)` supports one intervention per native kind. Family order is
fixed as Na_mem, K_mem, Cl_mem, Ca_mem, pressure, ecmJ. Target-profile order and
duplicate occurrences are retained. Capacity padding is neutral and explicit.
`Intervention` names are unique, clocks/amplitudes are finite, and transition
time is positive. Reversed on/off clocks and signed amplitudes remain valid
native arithmetic. ECM events require ECM and have no spatial callback.

Named callbacks require explicit `Sampled(values,axis=...)`. An `occurrence`
sample is scalar or one value per ordered target occurrence. Alternatively the
axis explicitly names the matching owner domain and values are gathered by ID
indices. Native callback code infers its domain from list length: subsets can
raise an unbound-variable error; full duplicate lists use global coefficient
order; equal cell/membrane counts choose membranes first even for pressure.
Occurrence sampling preserves captured source outputs. Owner sampling is an
explicit Cells choice and must not be called equivalent to those native bugs.
The component captures `gradient_x`; it does not implement arbitrary callbacks.
Dynamic callback factors are explicit numerical inputs, with ECM fixed at one.

`InterventionState` owns nine buffers:

| Buffer | Required final axes / unit |
| --- | --- |
| membrane_base_m2_s, membrane_scheduled_m2_s | [...,6,M], m2/s |
| pressure_base_Pa, pressure_mod_Pa | [...,N], Pa |
| environment_base_m2_s, environment_current_m2_s | [...,6,E], m2/s |
| environment_free_m2_s | [...,6], m2/s |
| environment_weight_base, environment_weight_current | [...,E], native factor |

Environment weights are explicitly flat; flattening/restoring the native 2D grid
is caller-owned. `apply_interventions(time_s,state,kernel,dynamic_factor=1,xp=...)`
supports NumPy and CPU JAX, common leading world axes, scalar time or time with
singleton final axis. Dynamic factors must broadcast to the world/event axes.
The stable logistic difference is the native pulse. Writes process occurrences
in order, so the last duplicate assignment wins. Input buffers are not mutated.

Membrane updates are amplitude*spatial*dynamic*pulse*DEFAULT-profile Dm, written
into the scheduled buffer. Local profile Dm is not used as that multiplier.
Na/K source events ignore ion-enabled guards; Cl/Ca obey them. Pressure writes
the corresponding amplitude product into the modifier. ECM blends selected
diffusivities as `baseD*(1-eff)+eff*freeD`, weights as `baseWeight*(1-eff)+eff`.
No sign clipping is added. Unselected or guarded entries retain previous values.
Results contain updated buffers, base+scheduled membrane totals, base+modifier
pressure totals and per-event pulses. Physical positivity, transport acceptance
and material/energy accounting belong to downstream callers.

`intervention_domain_valid` checks shape/dtype, finiteness, target bounds,
positive transition, neutral padding, ECM dynamic restrictions and finite
outputs. Kernels assume callers perform this check; internal clipped lookup
indices are not an acceptance policy. Batched per-world acceptance can use
`vmap`, as qualified. Raw named-tuple kernels are numerical representations;
trusted manifests/binders establish semantic ownership.

## Remap and checkpoint boundary

`binding_manifest` and `intervention_manifest` hash compiled target order,
layout/profile identity, flags, timing and numerical kernel values. Their
validators reject stale identities, including JSON round trips. These are
identity metadata, not complete checkpoints. Persist raw selector definitions,
bitmap files/decoded provenance, resolved permutations, callback provenance,
dynamic factors, state buffers, clock and RNG independently.

`carry_cell_targets(binding,new_layout,missing='reject'|'drop')` is an explicit
Cells policy: preserve stable cell occurrences, reject or drop removed IDs, and
re-expand with the new declared owner maps. Native post-cut handling instead
reruns profiles, GJ setup and event initialization, which can reselect/resample.
Carry is not native reselection parity. Actual cut execution, new geometry,
solver recompilation and serialized checkpoint migration remain Chief-owned.

## Qualification and preserved limitations

The complete receipt has 81 tests: 77 host and four CPU JAX, no failures/skips,
plus 38 authenticated native valid cases and 19 retained native limitations.
The stdlib reference independently uses ordered owner loops, Fraction bitmap
interpolation on decoded F32 pixels, and 80-digit Decimal pulse/write arithmetic.
Actual upstream AST bodies are authenticated against both checkout and installed
BETSE 1.5.0 revision `5269a714aa2593ed2a6708c4516289977d8ae1a2`.
Path/enum/sequence adapters and recorded `calc_gj_vects` replace setup only;
actual picker, decoder, interpolation and intervention arithmetic runs upstream.
No production Cells/JAX is imported in the native child, and no geometry/cut or
full simulator is executed.

Source limitations include duplicate names, unsupported picker, negative/bool
indices, out-of-range percent/index, missing/white/collinear/nonsquare/small
images, missing SVG tags, absent environment keys, ECM-disabled ecmJ setup,
unknown target profile, ambiguous/subset gradient callbacks, Python None versus
the source string 'None', and zero transition. Captured successes exposing
unsafe source semantics are retained alongside failures. Native broken branches
are rejected rather than silently repaired.

JAX checks compile profile diffusion, bitmap interpolation, GJ weights and
ordered events, cover duplicate batching/padding and isolate invalid worlds.
Four prescribed control samples at 0.1/0.3/0.5/0.9 s restart exactly from carried
buffers. This is control-buffer restart, not solver/checkpoint equivalence.
Pressure time derivative at 0.215 s is 57.70159566416571 Pa/s, central difference
57.701595661541205 Pa/s at 1e-6 s. Qualified tolerances remain those in the JSON
protocol; all selection/order comparisons are exact.

Native/host/JAX guarded wall times are 4.304/5.555/15.406 s. Peak sampled tree
RSS is 310,988,800 B; minimum available host memory is 20,038,062,080 B.
CPU7, one thread, no GPU or persistent compilation cache. Native image checks
use the existing BETSE environment (NumPy 2.5.3, SciPy 1.18.1, Pillow 12.3.0);
host/JAX use the existing CPU environment (NumPy 2.5.3, JAX/JAXlib 0.11.1).
No dependency was installed or changed.

Attempts 01/04 retain lint failures; 02 retains missing-Pillow failure in the CPU
environment; 03 is source-only preflight, not a complete component pass. Attempt
05 qualifies the unchanged complete scientific set. The metadata finalizer
verifies all receipt artifacts and source hashes and records these attempts.
No material, energy, water, ATP or whole-tissue claim follows. No scientific
follow-up/audit/regression is queued; shared/frozen earlier work remains untouched.
