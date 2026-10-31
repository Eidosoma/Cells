# Ordinary ECM pre-step events — owned boundary and source findings

Chief assigned `betse_normal_ecm_event_join`. Static preparation only: never
import/evaluate scientific modules or fixtures, collect tests, launch/poll jobs,
use GPU, edit PROGRESS/shared science or change frozen catalog/field/CaATP laws.
Specialist separately owns `betse_normal_ecm_initialization`; do not edit it.
Catalog01 reporting successor is prepared separately. Chief explicitly requires
final static-review findings before catalog02 freeze. Event implementation must
use that final base rather than propagate any remaining review finding.

Source witness is `betse_normal_ecm_event_join_reachability_01.json`, built from
332 installed-exact Python files, AST/text/hashes only. The native loop resets
membrane/GJ/ECM flux arrays, dispatches SIM fire_events, then pumps, moving ions,
CaATP, GRN/catalog, dynamic protein noise, enabled mechanics, ordinary deferred
commit, full fields/update_V/check_v. Sampling follows and does not gate events
or protein noise. Actual event labels are linspace(0,N*dt,N), while all material
and noise use configured phase dt. Preserve original N3 for bounded prefixes.

TissueHandler.fire_events calls globals, tissue, makeAllChanges. Global order
is K salt, Cl salt, Na salt, runtime T, targeted GJ, scalar NaKATP block. Salt
writes overlap Na/M boundary entries; later source assignments win. Real M-1
is required for K/Na salt branches; current catalog5 roles have no M. Do not
rename P or Cl, invent a native M default or bypass role validation. New prepared
inputs may supply a complete M ion/valence/material/diffusion/boundary/cache row;
otherwise refuse those branches. p.env_concs is the fixed configured reservoir,
separate from live c_env_bound and grid state. T event uses configured p.T,
while sim.T persists when the event is disabled. Enabled events write pulse
baseline even outside their main interval; disabled branches leave prior owners.

Tissue order is Na/K/Cl/Ca scheduled permeabilities, pressure, ecmJ, cut, voltage.
makeAllChanges always sets Dm_cells=Dm_scheduled+Dm_base and P_cells=P_mod+P_base,
even if all events are disabled. Tissue scheduled slots persist between calls.
ECM junction events use fixed D_env_base and D_env_weight_base, writing current
D_env and molecular weights with original indexed/duplicate-last semantics.
They do not redefine initial sigma/ko caches or regenerate geometry/operators.
Voltage writes positive boundary then negative boundary, so identical edges
retain the latter assignment. Untargeted edges persist; later field code reads
actual updated boundary values. Preserve source NaKATP scalar writes rather
than storing fabricated vectors. Explicit broadcasting is allowed only at old
vector consumers, retaining original source shapes in new owned snapshots.

Existing code candidates: physiology_native_calendar (original source labels),
betse_global_controls (T/GJ/NaK/voltage arithmetic), betse_tissue_profiles
(intervention occurrence writes), betse_time_modulation (periodic/sweep laws),
betse_perturbations (local complete MT19937 and source-fast/matrix protein
updates). Reuse only exact source correspondence. Old global control targets
are explicit and cannot claim the source shuffled-selection lifecycle. Old
tissue callback gathering can differ from the literal source, which chooses
a returned full-axis vector by len(pc) and writes it directly without gathering
by target order. For source gradients/single_cell, retain exact callback output
and occurrence shape, including native mismatches/refusals. gradient_y uses
x-offset; radial uses x-offset in both axes. f_sweep may set slope during callback
construction; this is a separate prepared-owner epoch, not a warm event draw.
Bitmap/cut/remesh and other unowned lifecycle branches require prerequisites.

RNG sites must remain distinct. Native init_dynamics copies Dm_base before
always drawing M static-K uniforms (even level0); first SIM makeAllChanges resets
that static perturbation. GJ finalization shuffles a copy through Python random
but selects the unshuffled membrane prefix; even the unused shuffle consumes
its separate stream. single_cell callback construction consumes one NumPy choice,
with supplied ordered boundary occurrences, even duplicates. These preparation
epochs belong to supplied tissue/callback/RNG evidence; do not replay native
initialization or infer a seed history. Warm dynamic noise is guarded by
SIM/dynamic_noise==1/enabled P, consumes exactly one M-uniform vector per call
including t0 and amplitude0, then directly updates P cell/membrane/grid after
GRN and before ordinary commit. Disabled branch consumes none. No sqrt(dt)
scaling or physical Brownian/thermodynamic claim. Local full MT19937 words,
position, Gaussian cache and NumPy version must be owned and immutable; no
ambient global RNG mutation or stable-owner RNG substitution.

Native init_core appends every enabled ion to movingIons, including P; its
exception-for-proteins comment is stale. Explicit prepared moving-ion subsets
are conditional external seams. Do not infer that P is stationary when adding
noise. Test both declared stationary and moving-P cases; retain source ordinary
commit/clipping/shell behavior and separate direct-noise amount books.

New owned live coefficient/control state is necessary: the frozen catalog
material kernel fixes membrane/environment diffusion, but source events change
both before ordinary flux. The catalog context restore also carries molecular
D_env weights from the prior GRN cache. New functional reconstruction must
restore the prior cache then apply the explicitly retained earlier event writes
at the correct source read boundary, without losing or relabelling epochs.
Do not mutate old typed bindings or forge their identities. A new owned material
adapter can add explicit live coefficient inputs and a post-GRN noise callback
while preserving the complete original scalar/math bodies and budgets through
inverse AST/source audits. Capture GRN return before noise, noise return before
commit, and actual post-material cache separately. Pressure writes may be
retained without mechanics credit; mechanics remains Specialist's separate lane.

Potential independent conditionals: actual event-entry owned stores; actual
post-event/pre-material; actual pre-CaATP; pre/post-channel GRN; actual pre-noise
plus archived uniform packet; actual end-field. Independent material reference
must include both source channel and post-GRN noise direct updates. For a full
pre-material noise conditional, any read-only prospective draw must use a cloned
incoming stream without committing it, be labelled prospective, and be proved
identical to the actual post-GRN draw; failed GRN paths must retain unconsumed
actual RNG. Do not use a downstream outcome as an earlier input or conceal RNG
sampling reordering. Primary native replay independently selects and records
original guard/body calls and all stream epochs. Preserve failed parents,
partial source stores, raw native returns and strict port/source distinction.

No scientific execution or qualification has occurred in this event lane.

Exactness caveat for implementation: existing setters/tissue pulses deliberately
use stable logaddexp, while native toolbox.pulse uses literal np.exp. Existing
protein_step uses einsum instead of native update_Co's dot/scatter arithmetic.
Do not assume bit-exact whole-loop outputs merely because local qualified
budgets pass. Prefer original literal pulse/handler/noise arithmetic for primary
source capture and a separately owned port adapter; use qualified calendar/time
laws and local MT sampling where exact operation order corresponds. Existing
stable setter/tissue/protein kernels can supply additional component checks,
with their original budgets, rather than silently replace source operations.
A port noise adapter may replace only the RNG interface call with an explicit
local provider and retain original update_Co, while independent native replay
uses its own RandomState and original AST/proxy. Never monkeypatch shared NumPy
or shared component namespaces. Native post-finalization tissue handler fields
are an explicit supplied owner condition: no new profile picker/mesh creation
or claimed source constructor history. Keep runtime callbacks reconstructed from
explicit prepared periodic/sweep/scalar metadata, with any constructor draws
or source slope initialization already represented by the supplied owner.

Catalog02 is now final and frozen: inputs SHA
`2683f32049555429139bff971fcc443aa30fe021c3bc6f94baff879915b70420`,
receipt SHA `8f9dbe457c40d4143a7617e9c1e79abcbf1efa96123165a277155b56dff1407a`.
Root final review fc24a488...e814 found only reporting-key mismatch; no other
concrete source blocker. All9 science/test/fixture/protocol files,120 protected
pins,94 IDs and1314 planned forms stay identical01. Event implementation resumes.

Owned draft source adapter now exists at
`src/cells/processes/betse_normal_ecm_event_join_source.py`; initial AST emitter
`prepare_betse_normal_ecm_event_join_source.py` is exclusive-output, do not rerun.
It contains literal pulse,4 TissueHandler firer methods, voltage fire and the
original protein-noise guard/body with only the NumPy random call routed through
an explicit p._native_random provider. Port uses existing local-MT sample_native;
independent native must use its own RandomState/original draw, never production.
Prepared temporal callback helper was corrected to the real sweep_program API:
post-finalization explicit slope only, no stop/duration inputs when slope is
already supplied. logs alias is resolved. Main owner validation is still required
before install_owner; event_cut must be explicitly supplied None, never forced.
Error wrappers still need to retain returned source partials on exceptions.

Preferred live-coefficient lowering avoids mutating or forging old typed bindings:
after actual pre-step events, construct a legitimate new material.bind declaration
with only source-written current Dm_cells/D_env replacing those two coefficient
arrays. Lower the actual post-event material values through material.state with
that real binding and original step_index. Record both previous owned parent and
new component input/binding IDs explicitly. All geometry/current/voltage inputs
and geometry identities must remain exact. network.make_context may consume an
explicit RuntimeMaterialInput containing that actual material binding; no old
Binding masquerade. Full field reconstruct can use the fixed event composition
binding (same geometry/initial sigma/ko/free-D caches) and returns a baseline-
bound material State for the next outer step. The event sidecar retains live
coefficients; next step lowers anew. No native full checkpoint migration claim.

Own the actual flux reset outside the material subcall: original loop resets
membrane/GJ and allocates fresh ECM flux arrays, then fire_events. Capture both
pre-reset parent and returned event stores before domain/binding checks. New
owned `_material_step_after_events` can copy the existing CaATP material kernel,
remove only its4 repeated flux-clear statements (the real outer reset already
ran), retain observation markers as source checkpoints, and insert on_noise plus
observation immediately after ecm_grn_dispatch and before deferred ordinary
commit. Inverse AST reintroduces the4 clears and removes the noise hook to
recover the unchanged qualified CaATP material body. This prevents a hidden
second reset/source invocation while retaining all primitive equations/budgets.
Native wrapper executes original reset once, original SIM event guard, ordinary
source, CaATP, catalog/GRN, original noise guard, commit and fields. The local
material/reference boundary begins after actual events, with zero reset flux
buffers; outer snapshots separately prove real pre-step chronology.

After restoring the prior GRN cache into the reconstructed warm context, apply
retained event stores so earlier D_env weight writes survive hydration. Restore
actual scalar/vector GJ/NaK/rho shapes; broadcast only at old force consumers.
The new scalar-aware channel reference must adapt rho indexing while preserving
actual scalar inputs in source snapshots. Source control entries may be scalar;
GRN modulators may later replace them with membrane arrays, which persist into
the next event. Capture post-GRN before noise and post-material after noise plus
commit as distinct epochs. Own nullable protein_noise_flux cache separately from
MT state; disabled branches can carry an older supplied cache without a draw.


# Concrete event bridge implementation decisions (draft, no numerical execution)

Use frozen catalog02 as dependency. New scientific source files currently2:
`betse_normal_ecm_event_join_source.py` (literal handlers/pulse/voltage/noise plus
local RNG/provider/prepared callback plumbing) and
`betse_normal_ecm_event_join_material.py` (step_after_events). The latter has a
stdlib initial generator proving inverse AST exact to CaATP material after
restoring3 reset statements covering4 buffers and removing post-GRN noise hook.
Do not rerun exclusive-output initial emitters. Source helper now adds original
reset_fluxes and original fire_events_guarded wrappers, plus EventSourceRejected
with full mutable partials for event/noise failures. Main is not written yet.
All old catalog02 files remain unchanged. Keep all implementation under newprefix.

Main should have legitimate fixed composition Binding plus sealed EventFieldState.
Bind normal catalog subset through catalog_component.bind (for actual old
geometry/voltage/calcium/catalog declarations), then make a distinct owned new
binding ID including explicit events/entry stores/calendar/MT/noise data. Never
pass the new type to old exact-type initialize/advance, forge an old ID or relabel
old sealed field states. Reuse lower source.cold/restore/dispatch, calcium helper,
network._state, full.reconstruct and original math with actual new owned identity.

At initialization, construct context, configure catalog, install explicit supplied
TissueHandler owner/stores before cold channel reader (named tissue maps must
agree). Source CaATP native policy remains unchanged (ERFalse, fixed defaults,
rate absent). Cold callback archives complete original/cache/owner returns before
strict guards/bootstrap. Full.reconstruct with new owned binding creates new
field state properly; it must not receive relabelled old field objects. Calendar
uses qualified NativePhaseCalendar SIM/N3/dt and must exactly match original
linspace source labels. Entry MT is a complete provided NativeStream manifest
with epoch/provenance, never a guessed native initializer history. Nullable
protein_noise_flux cache is separate, supplied/owned and carried when disabled.

Each advance:
1. Validate owned parent/field/CaATP/clock/event stores/RNG/cache and fixed geometry.
2. Reconstruct context from actual previous material and full channel/GRN cache.
   Install actual event sidecar after restore so live D_env/weights/controls win
   over stale stored coefficient fields. Scalar/vector control shapes survive.
3. Capture actual immutable pre-reset parent; execute literal reset_fluxes once,
   then original SIM guard/fire_events once at actual original label. Capture
   every returned event/store stage before strict domain checks. No per-step
   external T/bath/GJ/rho/boundary overrides: require raw baseline step packets to
   agree with declared entry values and use event-owned persistent values instead.
4. Bind a legitimate runtime material component from unchanged baseline document
   except current event-written membrane/environment diffusion arrays. Validate
   its geometry identity equals the fixed original. Lower actual post-event
   values via material.state(runtime_binding,...,step_index=index). Record full
   previous parent, event result, runtime declaration/binding ID and lowered input.
   This is explicit parameter/input lowering, not native checkpoint migration.
5. Run owned step_after_events(runtime_binding,lowered,forcing,...). It preserves
   all qualified primitive math, guards, frames/ledgers and budgets; real resets
   already occurred. Local component boundary starts post-events with zero flux.
   before_material conditional sees this actual post-event input/runtime document.
6. on_calcium uses unchanged CaATP helper/rate/clock with new owned binding; emit
   full phase before further work. on_network reconstructs current array context
   using actual runtime material binding, restores full prior cache then reapplies
   retained event stores/shape-aware controls/weights, preserving earlier event
   writes. Dispatch actual source time and original pre/post-channel conditionals.
7. on_noise is invoked after ecm_grn_dispatch snapshot and before ordinary commit.
   Existing local-MT sample_native supplies exactly one M-vector when original
   guard permits; native independently uses original NumPy RandomState. Record
   actual pre-noise state/draw/stream, return and failures. Hydrate any supplied
   old noise cache before branch so disabled branch retains it. No flux storage
   addition, sqrt(dt), clipping or hidden stream advancement.
8. Post-material cache is captured after noise and deferred commit, while GRN
   return/pre-noise snapshot remains separate. Sidecar stores reflect GRN control
   rewrites and actual current coefficients/bounds/T/pressure. Full.reconstruct
   uses fixed geometry/initializer caches and new composition ID, updates Vm and
   rebinds returned material State to baseline material binding for next outer
   parent. Preserve runtime material trial/binding provenance in context. Carry
   actual rate, N3 clock/index/accumulated dt, MT and noise-cache fields.

Original helper reset statements: fm.fill(0), fg.fill(0), tuple allocation of
fx_all/fy_all;3 statements/4 effects, not4 statements. Outer native real reset
block is original2 fills plus ECM-if containing2 allocations. Source noise is
a guard/body fragment, called once even disabled but consumes no draw/body writes.

Prepared owner declaration should contain actual handler_fields for enabled
branches, tissue_default6 ion Dm values, explicit cell/membrane/environment target
maps, global_options6 keys, scheduled_options6 keys, configured_environment,
callbacks(supplied source scalar and constant/periodic/explicit-slope sweep),
voltage fields orNone, event_cut explicitlyNone, and geometry/owner identities.
Validate values against source finalizer row semantics and ordered/duplicate
profile expansion; do not regenerate profiles or infer callback spatial shapes.
Temporal callbacks use qualified exact-order helpers; the draft sweep callback
has already been corrected to explicit slope-only real API. Native original
callback factory construction is not inferred from supplied scalar conditions.
Cut/remesh/bitmap/unknown callback lifecycles are explicit prerequisite refusals.

Outer raw event input can extend normal catalog fields with calendar, event_owner,
entry_event_state, noise, prepared_rng, noise_cache. Existing kernel5 roles may
be extended by an explicit M-1 full row for K/Na salt paths; otherwise refuse
those paths. All geometry/material/diffusion/cache/boundary rows are supplied.
For static fixture *code* later executed only by Chief, choose explicit new M
initial1e-3, Dm4e-6/Dgj4e-5/Denv1e-3/freeD1e-9 and neutralize P with real M charge;
these are manufactured declared inputs, never native defaults or chosen outcomes.
Ensure initial cache/GRN boundary vectors include all6 roles. Preserve explicit
moving-ion choice; native actual init_core includes P despite its stale comment.

New scalar-aware independent channel reference must handle actual source rho1
scalar, since old catalog reference assumes an M-vector. Do not change old
reference or falsify source snapshots by broadcasting their metadata. Broadcast
only in equations at the actual scalar/vector consumer seam. Copy existing
pure-stdlib conditionals into own namespace; preserve budgets. For full material
reference, include both catalog direct updates and post-GRN P noise before
ordinary commit. Prospective noise samples, if needed for a pre-material oracle,
must come from a clone of incoming stream, be labelled read-only/uncommitted,
and match actual post-GRN sample; a failed GRN leaves actual stream unconsumed.

Proposed ~20 three-call contextual histories (not finalized): combined, salt
order, runtime T, persistent GJ override, native NaK scalar shape, all4 tissue
membranes, ecmJ, periodic, sweep, same-edge voltage last write, duplicate tissue
targets, noise active, noise level0(draw still), noise disabled(no draw), no events
(makeAllChanges still), no channels, no CaATP, rectangular, fast duplicate, pressure
write retained/no mechanics credit. Add specific raw/dep controls and fixed counts
only after complete design. No source equivalence by imports or biological credit.

## Current implementation and static preparation (2026-10-31)

The draft above is now implemented under the separate event prefix:3 scientific
files, fixture code, independent original-source native owner/capture, independent
Decimal reference, deferred tests, protocol and source map (10 owned files).
No scientific module or fixture has been imported/evaluated; no tests collected,
computations launched or jobs queried. Initial emitters are historical exclusive
source writers; final files contain the subsequently audited manual refinements.
Do not rerun initial emitters over current files.

Chief03 supersedes the earlier catalog02 dependency condition. Chief supplied
`/mnt/workspaces/Cells/ecm-callback-repair-20261031-01/preparation.json` and exact
calcium/catalog callback-only pins. Own `betse_normal_ecm_event_join_dependency_witness_01.json`
independently proves127/129 catalog02 controlled files unchanged; inverse AST of
both incoming-packet callback changes recovers the original full modules. All
old frozen01/02 files, failed evidence, physics and fixed budgets are preserved.
Source03 review remains an explicit freeze prerequisite in the current workqueue;
the event runner refuses preparation until that review is bound. No automatic
rebinding to shared live bytes or scientific rerun is allowed.

The full material reference inserts direct post-GRN protein noise before ordinary
commit using an explicitly uncommitted cloned-stream preview; the actual source
noise draw remains after successful GRN. The separate noise conditional is taken
after the actual draw but before noise arithmetic. Scalar rho is broadcast only
at equation consumers, while actual metadata retains source scalar shape. The
native owner retains the original np.random.random AST through a local proxy,
independent of production sampling. Cache absence, zero-level draws, disabled
no-draw behavior and an explicit earlier supplied noise-cache carry are distinct.
Explicit moving-P and stationary-P conditions are both declared; init_core's
stale protein-exclusion comment does not establish native stationarity.

`betse_normal_ecm_event_join_AST_witness_02.json` proves literal5 firer/voltage
bodies, original pulse/reset/SIM guard, single explicit port random-interface
adaptation, original native noise body, inherited field/CaATP capture/dispatch
functions, and inverse-exact material and reference insertions. No returned
scientific AST is executed. The full native provenance now includes the event
source hashes as well as inherited material hashes.

Deferred matrix:20 three-call histories (6 component controls),6 raw limits and
16 prerequisites =42 unique test IDs;26 native captures;60 normal calls per
implementation;920 fresh100/160-digit conditional forms. This is a planned matrix,
with zero new numerical/trajectory/biological/ER credit. Pressure remains a store
write without mechanics credit. Existing signed_environment39/40 failure and
original class pole failures remain failures.

`betse_normal_ecm_event_join_reporting_metadata_check_02.json` checks the actual
allowlisted test producer's metadata dict and stdlib report-reader on162 tiny
temporary JSON files, including6 raw/16 dependency schemas and missing-event-form
rejection. No science/fixture/reference calculations occur. Earlier01 metadata
check is retained. Static compile/name/Ruff checks cover23 Python files, the
independent closure is14 stdlib modules, the scientific import closure93 modules,
and33 inherited keyword interfaces are checked. Current queue holds10 owned and
131 protected files. The first final static witness records review-pending state;
final freeze must bind the current source hashes and completed Chief review.

During static preparation, an audit initially searched for an inlined Ca helper
instead of the actual `calcium_call` wrapper, and the metadata emitter initially
expected11 instead of10 owned files, then needed tuple/list JSON normalization.
These were tooling expectations, corrected without executing science or changing
source equations. An unqualified shell `python` was unavailable; all subsequent
checks use the explicit venv-cpu interpreter. Draft static failures are not
scientific results and are not relabelled numerical passes.

Final freeze prerequisite resolved: Chief supplied callback source03 review
`/mnt/workspaces/Cells/ecm-callback-repair-20261031-01/root-review-01/REVIEW.json`
SHA256 `d0eb124095d187ee26c5cb52520a8add4a45d74b86dd0da45d2f3e8de974c95c`,
status `clear_for_held_full_roster_runner_preparation`, zero blockers. Current
protocol/queue explicitly bind it and verify both reviewed successor module pins.
Final static witness02 and the immutable event01 packet govern the event handoff;
historical pending flags above describe earlier preparation epochs. Chief has
assigned an independent event review. Cutting/tissue lifecycle work, if admissible
after its source audit, must use a separate prefix and preserve this packet.
