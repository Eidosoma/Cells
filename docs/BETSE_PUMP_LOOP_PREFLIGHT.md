# Native BETSE pump–leak preparation

2026-09-16, D115 / REF-005b. The [bounded production-family gate is
closed](../reports/SPEC010_FAMILY_CLOSEOUT.md). Next, establish what the real
BETSE driver does before comparing complete pump–leak trajectories.
This preparation is a validation adapter, not a new production model.

## Why a lifecycle gate

The pinned BETSE 1.5.0 function `science/sim_toolbox.py::pumpNaKATP` returns
inward Na and K flux densities, followed by **outward sodium density**, not ATP
consumption. `science/sim.py::_run_sim_core_loop` then scales the first two
returns by `rho_pump` and masks boundary faces for a closed cluster. Its stored
`rate_NaKATP` does not receive these changes. Actual signed cycles must come
from the applied Na/K transfers, with -3/+2 stoichiometry, before computing
maintained-reservoir chemical work. An upstream label is not a biological law.

The same driver accumulates passive density, then updates concentrations and
voltage. With extracellular space disabled, `update_Co` mixes per-face bath
values: the effective common volume is **number of faces × configured bath
volume**, not the latter alone. The source also has a tiny in-place voltage
nonce in `electroflux`; record its inputs honestly, without copying that
mutation into Cells or hiding it in an observation hook.

## One bounded native preparation

- Unmodified pinned revision `5269a714aa2593ed2a6708c4516289977d8ae1a2`,
  locked native environment, FULL INIT driver and matched declared F/R.
- Existing reproducible **seven-cell / thirty-face** geometry, because the
  native seeder's nominal single-cell setting does not produce one cell.
  This is a comparator fixture; Cells' data-defined one-cell capability stays.
- Eight **25 µs** updates: **0.2 ms elapsed**, not the driver’s raw sample
  label interpreted as an extra or missing step. Native initial chemistry,
  298.15 K, maintained ATP/ADP/Pi and unchanged pump saturation constants.
- Six controls: pump+leak, pump-only, leak-only, all-blocked, half pump density,
  and a closed cluster boundary. Na/K pump density capacity is 1e-7 mol/m²/s;
  passive permeabilities are 1e-9, 2e-9 and 5e-10 m/s for Na/K/Cl when enabled.
  Other transport, networks, junction flux, mechanics and spatial outside are off.
- Each preparation runs **observed and unobserved**: twelve native runs,
  six exact-output pairs and 48 observed steps. The identical declared setup
  hook sets only `rho_pump` and `cluster_open` once after native initialization.
  It does not change concentrations, voltage, integration, methods or clocks.
- Reuse the existing read-only lifecycle observer; extend it with source- and
  instance-scoped copies of direct-loop pump/passive arguments and returns.
  Junction calls must not be mistaken for membrane leak. Preserve full native
  histories, geometry, setup metadata, native restart pickles and boundary records.
- Check actual accumulated density, driver scaling/masking, -3/+2 transfers,
  the diagnostic rate's true meaning, single intracellular/shared-bath updates,
  positive chemistry, chronology and observation neutrality. Densities use
  2e-18 mol/m²/s absolute tolerance, concentrations 2e-12 mM, relative 2e-11.

Successful execution means `native_lifecycle_checks_pass_pending_review`.
It does **not** mean cross-engine trajectory, energy convergence, equilibrium,
biology, spatial pumps or GPU qualification. No Cells trajectory is run here.

## Resources and source preservation

Freeze the reviewed family’s 601 inputs, new adapter/protocol/contract/handoff,
native source/environment identities, geometry and software receipts in a new
capsule. Check again before success. Leave all old captured files, original
launchers and historical identity guards unchanged. No production file edits.

CPU affinity 0–3, one BLAS thread, **240 s native / 300 s total**;
**64 MiB per file / 256 MiB artifacts** (disk limits, not RAM).
Launch detached with durable logs, result/failure receipts and no automatic
retry, polling, subsequent audit or regression.

## After the user requests review

1. Authenticate the packet and independently reconstruct the saved transfers
   and observer pairs. Investigate any mismatch before increasing the horizon.
2. Map its measured cell volumes, face areas, finite bath, actual immobile-ion
   charge and maintained metabolism into `finite_extracellular@2`. Check
   initial states, instantaneous rates and single updates. Aggregate faces
   only where concentrations/voltage and interface laws justify it; preserve
   active-area fractions for boundary masks, without fitting parameters.
3. Register a short matched coupled trajectory panel, with independently
   specified time grids, tolerances, control cases and accounting. Use a
   separate high-accuracy reference and refinement for native stepping and
   Cells RK4. Do not mistake native-step agreement for physical accuracy or
   require two different integrators to have identical histories.
4. Only after that review, extend to relaxation and held-out perturbations,
   then experimental data and spatial/channel/junction composition.

The reusable design remains side-effect-free array laws, explicit owner maps
and complete state/ledgers. A source-contact adapter must not dictate the
production integrator or obstruct later GPU/multiscale execution.
