# Small channel–voltage feedback pilot: implementation-ready design

D093, 2026-09-14. Builds on the D092 outline and the separately registered
[full-loop preparation](BETSE_CHANNEL_LOOP_PREPARATION.md). **Not a registered
coupled trajectory experiment or authorization for automatic follow-up.**

## The comparison we want

Can independently evolving native FULL and Cells checked RK4 approach the same
short opening response? Both m and h change permeability; K transfer changes
cell/bath inventories and capacitor voltage; the new voltage changes subsequent
gate rates. Keep the qualified geometry/temperature/constants, four controls and
explicit m=0.2, h=0.6 fixture. No background leak, pumps, GJs or intervention pulses.

Each engine owns its full evolving state and numerical method. The old prescribed
post-native-gate transfer adapter is deliberately not a trajectory driver.

## Independent equations already prepared

`pilot_reference.py` supplies a pure 80-digit Decimal **vector field**, not a new
production model or an integrated reference result. No simulator or older
comparator/compiler is imported. For this K-only regime, use one inward cumulative
transfer q_i in fmol and separate m_i/h_i for each cell:

- Cell K amount = initial K amount + q_i; bath K amount = initial bath amount − Σq_i.
- Cell voltage = actual initial voltage + F·10⁻¹⁵·q_i / C_i.
- Gate derivatives = (voltage-dependent target − current gate) / time constant.
- Permeability = maximum permeability × m_i × h_i; q_i derivative is area-integrated GHK.

Na/Cl and the auxiliary immobile charge remain explicit in the initial state and
conservation checks. q_i is not an extra independently integrated voltage state.
The reduced reference is valid only for this no-other-transfer fixture; it is not
a general replacement for Cells' ten-field state or a native restart object.
Blocked channels keep gate dynamics with zero transport. Channel-free controls
have no gate state. Tests use asymmetric cell states to exercise shared-bath
feedback; they do not assume cells are independent or identical.

The preparation checks the initial vector field against actual production RHS
and checks candidate data definitions. To obtain a **continuous numerical
reference**, a later version must implement/select an independently converged
integrator and register precision, tolerance and refinement requirements before
trajectory capture. Prefer a distinct high-order/adaptive method with an explicit
error budget, plus a tighter-reference repeat; do not call a single numerical
solve “ground truth.” Native discrete-step reconstruction remains a separate check.

## Candidate scope and grid panel

The readiness candidates are 2 ms, with observations at 0, 0.25, 0.5, 1 and 2 ms.
Native candidate steps: 25, 12.5 and 6.25 µs (80/160/320 updates).
Cells candidate steps: 50, 25 and 12.5 µs (40/80/160 updates). These distinct
panels acknowledge native gate-before-transfer versus coupled RK4. The current
Cells step guard is not evidence that any candidate is accurate in this regime.

Four native controls × three grids would be twelve native trajectories; four
Cells controls × three grids × NumPy/eager-JAX/JIT-JAX would be 36 Cells
trajectories. This is a sizing proposal, not an instruction to run that panel now.
Decide whether the initial dynamic pilot needs all three backends at every grid
or compiled trajectories plus bounded backend checks after preparation results
and timings are available. Do not infer GPU throughput from CPU setup/compile time.

For each candidate Cells definition, use the production timeline and conservative
working-storage estimator with max_steps=1024 and a 64 MiB trace reservation.
The registered preparation does not perform even one Cells integration step.
Record eligibility, counts and estimated bytes separately from measured memory,
runtime or accuracy. No extrapolation of a few initial derivatives is a stability
or horizon proof; inspect full-loop preparation signal and domain margins first.

## Gates before registration and capture

1. Independently review the full-loop preparation packet: initialization, explicit
   fixture, observer pairs, raw/elapsed clock mapping and native transfer accounting.
2. Verify the candidate continuous reference, choose its convergence evidence,
   and record a scientific error budget for m/h, voltage, cell/bath amounts and
   interval/cumulative transfers. Keep exact-zero controls separate from toleranced
   active rows. Classify roundoff-limited refinements explicitly.
3. Choose the horizon and engine-specific grids from domain/signal/refinement
   evidence, then freeze the complete panel, observations, tolerances, CPU/disk/
   wall limits and source capsule. Retain rejected candidates; do not tune against
   the resulting trajectories after seeing them.
4. Run the bounded capture detached. Use normal Cells checked RK4, complete
   checkpoints and invariant checks. Compare each engine to its own refined
   solution and to the independent reference, not just to the other engine.
5. Independently audit saved evidence before calling the coupled pilot qualified.
   Suppression/recovery, a second equal-product m/h history pair, additional
   channels, GJs and larger tissues remain separate stages.

Required outputs distinguish pre-gate state, post-gate/pre-transfer state, post-
transfer inventory and completed voltage. Fresh state-dependent current is not
an interval average. Preserve signed inward/outward current conventions and
the integral transfer ledgers. For Cells, verify uninterrupted versus checkpoint-
resumed evolution with every gate and ledger, not only a matching voltage plot.
Native serialization is retained in preparation, but native restart equivalence
needs its own test before it becomes an advertised property of the comparison.

## Why this matters for the multiscale design

No new engine framework or optimization is needed. The exercise checks reusable
interfaces: locally owned gates, explicit membrane owners, one conservative
transfer, stage-consistent bath reduction and observations outside dynamics.
Future GPU batches may contain independent worlds; cells sharing one bath cannot
be treated as independent jobs. Tissue partitioning or gate subcycling must
budget interface error and preserve/approximate slow h history explicitly.
Organ identity and size remain data settings. This benchmark adds neither GPU
execution nor biological/whole-organ qualification.
