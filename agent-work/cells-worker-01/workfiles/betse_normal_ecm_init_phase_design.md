INIT needs a separate phase adapter. This source audit resolves the phase,
entry-cache and random-state differences before implementing ordinary ECM INIT
material execution. It adds no implementation or scientific acceptance.

The pinned native revision is `5269a714aa2593ed2a6708c4516289977d8ae1a2`.
All332 Python files match the installed package. Exact source locations and AST
hashes are in [the boundary evidence](betse_normal_ecm_init_phase_source_boundary_01.json);
[the machine-readable design](betse_normal_ecm_init_phase_design_01.json) records
the proposed interfaces and checks.

| Boundary | Source behavior that the INIT adapter must preserve |
| --- | --- |
| Entry | `SimRunner.init` loads a seed, creates a fresh Simulator and calls `init_core`. SIM instead loads an existing Simulator. Supplied entry is an explicit seam; seed/load/full physical initialization remains unclaimed. |
| Clocks | Use `int(init_total/init_dt)`, INIT dt and sampling settings, original `linspace(0,N*dt,N)` labels and original sampling recurrence. Labels and update dt stay separate. Native count is not forced to3. |
| Legacy phase flag | `_run_sim=False` in INIT. The sweep modulator must retain its source behavior, including an unresolved default slope when its SIM-only calculation is skipped. |
| Setup | Tissue/event finalization still occurs. Static channel-noise setup draws a NumPy vector even when its level is zero; configured global GJ setup can consume Python shuffle state. These are distinct from per-loop noise. |
| Events/noise | Scheduled event execution and dynamic protein-noise updates are SIM-only. Preserve configured flags and exact stores; do not manufacture zero noise returns or run event callbacks. |
| Channels | All configured populations are constructed. An INIT-inactive population then skips warm updates. Its cold private fields and zero warm-call count coexist with active populations' advancing counts. |
| Owners | Fresh GRN construction and later reinitialization are distinct source routes. INIT-to-SIM transition remains outside the first contract because native reinitialization can rebuild channel objects. |
| Defaults | `Ca_dyn`, fluid flow, dynamic deformation and electroosmosis are hard-disabled by the ordinary loader. Temperature, GRN, steady deformation and osmotic flags require explicit configuration. No enabled ER route is introduced. |

The existing cold channel namespace already uses INIT. Its warm dispatch forces
SIM, and the current material wrapper requires every channel count to equal the
material tick. Its mechanics callback also lives inside the protein-noise hook;
INIT must instead place mechanics explicitly after network handling and before
deferred commit. These assumptions need a new-prefix adapter. Existing shared
and frozen SIM helpers stay untouched. Conditional references also need
INIT-aware skipping; a SIM channel oracle cannot establish an inactive
population's result.

The proposed first execution seam is headless INIT on complete supplied source
core/setup owners, entry receipts and caches. Archive actual pre-cold voltage,
constructor inputs, INIT dt, configuration, state/cache absence and RNG states.
Reuse pinned source bodies and unchanged numerical budgets. Respect inherited
kernel caps by explicitly labelling an original-calendar prefix or refusing the
unsupported count; a prefix is not a completed phase.

Each call follows native order: reset fluxes; ordinary pumps and primary movers;
conditional CaATP; the configured molecule block, then the configured GRN block;
optional osmotic/steady mechanics; deferred primary commit; full fields and
voltage check. Each network block clears its loop stores, runs configured
transporters, INIT-active channels and modulators in that order, then runs its
chemistry/movement loop. General molecules can be explicitly disabled for the
initial GRN scope. Flow, dynamic deformation and ER remain closed. Pause/resume
retains the full state and original calendar; phase-entry setup is not repeated
on resume.

Prospective checks must cover zero/one-call clocks, truncation and fractional
sampling; unreachable event/noise callbacks; mixed active/inactive channels;
GRN/CaATP flags; full source/native/fresh Decimal100/160 conditionals; reset/RNG
receipts; window and failure retention; and foreign phase/cache rejection. Those
checks have not run. Native storage, display, pickle, full seed/init/load,
INIT-to-SIM transition and biological/conservation claims remain outside this
first design. Display's existing <=16 field versus >=25 quartic-domain boundary
and native zero-sample pickle limitation remain explicit. INIT also needs its
own reviewed capture profile before selecting evidence tooling.
