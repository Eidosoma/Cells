# Native network feedback preparation

Chief requested a new network/normal-solver integration prefix. Source auditing
found that a zero-Molecule, nonempty-reaction configuration builds empty
gad_rates with shape(0,), then vstack combines its promoted(1,0) row with(R,N)
reaction rates. The source refuses that dimensional combination for N>0. This
is a planned distinct raw-negative case; no reshaping, fake growth row or supplied
reaction result repairs it. No positive chemistry credit is claimed.

The first defensible component executes endogenous ion-driven GJ/NaK feedback
in one enabled native network core. It owns all ion concentrations through the
joined state, both carried control vectors and complete relevant network caches.
The literal read_modulators/get_influencers expressions and control-write loop
execute. Native clear, empty-chemistry run_loop, energy-charge and publication
bodies also execute. Chemistry is explicitly empty and rejected by the public
binding when configured. The native source methods are preserved with observation
hooks only. Existing standalone modulation binding/domain and NumPy comparisons
are reused; stabilized standalone math does not replace literal primary stepping.

The order remains ordinary pump/ion/GJ/intra work, CaATP, network clear, late
channels, network modulators, empty chemistry, deferred ordinary commit, then
current/voltage. GJ/NaK writes occur after their ordinary use, so the owned values
affect the next call. Optional early scheduled control values and late channel
modulation arrays are explicitly supplied inputs; no native event/function
execution is claimed for them. A read-only pre-network observer supplies only
incoming state to independent references before outgoing feedback computation.

Sampling uses the actual current membrane aliases, including native staleness,
and rectangular bath rows indexed by the same explicit cells.map_mem2ecm used
for voltage geometry. Source-derived controls do not directly add membrane flux
or charge; existing channel current is retained in the network accumulator and
publication replaces or preserves incoming readout fields exactly as configured.
All relevant rate/delta/energy/charge/current caches and their presence persist.
The enabled owner may be molecules or GRN; two-owner execution is excluded.

Actual molecule growth/decay calls update_intra and then unconditionally runs
molecule_mover, even with zero diffusivity. Its complete cell/environment/
membrane concentrations, fluxes, geometry, flags and controls must be owned
before active chemistry integration. Transporters, molecule pumping/gating,
clamps, environmental/mitochondrial reactions, finite fuel, ER/buffers and full
GRN or Simulator lifecycle therefore remain explicit separate dependencies.

Planned checks are ten three-call histories, one no-feedback projection against
the frozen calcium prefix, three dependency controls and one source stack
refusal:15 checks,11 native captures,30 actual pre-network points and60 fresh
Decimal90/140 references. There are zero carried references. Cases cover zero
controls, ordered overwrites, mapped nonuniform bath sampling, GRN owner label,
explicit scheduled override, disabled publication, channel coupling and INIT
channel skip. Native full frames/caches/routes, actual control writes and carry,
current and voltage are primary. Independent control errors use the unchanged
standalone modulation protocol tolerances, with full error/budget/unit arrays.
No upstream transport, whole-trajectory, biological or active-chemistry accuracy
claim follows from these conditional checks. None has run in this preparation.

The runner reuses480s/group,1GiB process-tree RSS,8GiB reserve and one explicitly
coordinated CPU/thread. It checks current owned/protected hashes before and after
computation. Root's authorized surface_calcium.py helper refactor is recorded
as an exact single protected-path change, with its independent review pin. No
hash exemption is introduced. All prior failed/frozen evidence remains intact;
no shared PROGRESS, git staging, commit or detached-job polling occurs.

Chief also identified five concurrent independent recovery-reference edits
(surface dynamics, kinetic, energy, energy_water and cotransport_water).
The queue names these exact unrelated paths for copy-time live consistency;
their frozen bytes remain hashed. None is an owned/protected network dependency
or part of its scientific import/reference closure.

The grn_owner case changes an explicit owner label on the same authenticated
core. It does not select or initialize the native GRN wrapper and provides no
GRN dynamics execution credit. The separately frozen runner02 captures all
post-output setup failures and requires exact unique test and complete report
sets; network01 and all ten scientific files remain untouched.
