# Ordinary ECM INIT source handoff

This is a source/static implementation on supplied pre-setup tissue, primary,
macro-geometry, initializer-cache and mechanical DEC owners. No numerical
qualification has run. Chief owns review, release, CPU allocation, launches,
shared status and the outstanding component qualifications.

The new `cells.processes.betse_normal_ecm_init_phase` API accepts `bind(inputs)`,
then `binding, state = initialize(declaration)`. A window uses
`state, returns = run_window(binding, state, stop=...)`. The next window resumes
the same parent and original calendar without repeating setup or consuming RNG.

Setup draws native static K noise once, including at level zero; retains base,
scheduled and current Dm separately; constructs fresh GRN/catalog populations;
initializes the supplied mechanics entry; and executes the complete source
global and targeted event finalizers with a local Python shuffle stream. The
source's unused shuffled-copy convention is preserved. Constant and dormant
`f_sweep` callbacks are admitted; `_run_sim=False` preserves an unspecified
slope as None. No callback is fired during INIT.

Warm calls reuse the common material/CaATP/field/steady-mechanics equations.
The private material copy adds only a post-network hook before deferred commit.
The real maintained-pool NaK helper supplies the early pump flux. INIT dispatch
honors each population's `init active` flag, default True. Inactive populations
retain their entire cold private caches and zero counters. Mechanics follows
GRN directly, independently of the unreachable SIM protein-noise path.

The supplied three-row forcing packet is capacity, not a three-call clock.
N0/N1 are represented explicitly; longer native calendars keep all original
labels while the existing material cap permits a prefix of at most three calls.
Source labels and accumulated material dt are separate. Eligibility produces
headless observations; no sampled display or native storage is completed.

Fresh source entry enforces zero Vm and voltage boundaries, configured T, zero
pressure and absent rate caches. Primary concentrations and remaining required
material/gap bookkeeping are explicitly supplied conditional owners. In
particular, a required Egj bookkeeping buffer does not establish that native
init_core produced that attribute before its first GJ update. The existing
conductivity/screening initializer cache is also a supplied conditional seam;
the full init_dynamics conductivity producer is not qualified by this join.

Separate general molecules, GRN-disabled compositions, enabled ER, fluid flow,
electroosmosis, dynamic deformation, physical initialization, seed/load/profile
selection, INIT-to-SIM reinitialization, native storage/pickle and whole native
phase completion remain outside this first scope. Quartic display retains its
at-least25-cell requirement against the field's at-most16-cell domain. Native
zero-sample end-of-phase storage limitations are not hidden by the headless API.

The independent capture reuses unchanged authenticated native scientific bodies
and trace functions, with separately extracted setup/NaK/clock slices and true
INIT dispatch. The independent stdlib reference privately adds only the inactive
guard to the common channel equations. Its material equations remain unchanged;
early pump flux is predicted independently from archived incoming inputs.
Decimal100/160 conditionals use existing budgets and preserve raw forms. No
shared source/reference namespace is patched and no old answer is reused.

The prospective plan has 62 checks:22 positives,5 raw,33 dependency and2 observer
controls;61 accepted calls;986 fresh reference forms;29 native captures. Each
positive retains full native and owned buffers before assertions and exercises
pause/resume on the original calendar. Raw limits name the reached cause and
preserve partial buffers. Observer failures preserve the exact exception and,
after acceptance, the completed candidate. They receive no accuracy credit.

The INIT capture profile is distinct and held for Chief review. Its310689-member
limit is the conservative ZIP_STORED/NPY format-capacity bound under the existing
64MiB archive cap, not a measured case maximum or a promise that every capture
fits. JSON, expanded bytes, headers, dtypes, shape, depth, owner, hash and CRC
guards remain. The catalog profile remains separate.

The frozen driver refuses before creating a run directory while held. A future
released successor requires a requested round and coordinated CPU. It reuses the
existing bounded runner with one CPU/thread,480s science commands,1GiB tree RSS
and8GiB host reserve; typed-evidence checks run separately with the same memory
limits. Chief should launch detached when the expected run takes ten minutes or
more. There are no retries, polling or automatic follow-up jobs.

The preserved signed_environment material failure remains39/40. This source
handoff provides no new physical, global-conservation, energy or ATP-consumption
claim, and inherits zero scientific passes.
