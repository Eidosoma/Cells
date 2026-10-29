# Explicit calcium/fuel INIT-to-SIM epochs

Qualification status: the full independent component is pending completion
review. This document records the implemented contract and verified pilot;
it does not claim that the detached full suite has passed.

| Epoch model | Ordinary INIT source | Complete physical parent |
| --- | --- | --- |
| `resolved_calcium_membrane_profile_epoch@1` | `resolved_calcium_membrane_profiles@1` | calcium @6 / ionic @7 |
| `resolved_calcium_energy_membrane_profile_epoch@1` | `resolved_calcium_energy_membrane_profiles@1` | finite-fuel @5 / ionic @12 |

The new spec/runtime pairs are `surface_calcium_profile_epoch` and
`surface_calcium_energy_profile_epoch`. Preparation lives in
`cells.core.owned_calcium_profile_phase_handoff`. Root owns shared public
dispatch, CLI, documentation/status and public tests. The five qualified
scheduled-profile files and every inherited physical equation stay frozen.

## Preparation and exact continuity

The adapter exposes `REQUEST_KIND`, `KIND`, `owner`, `capture_source`, `prepare`,
`replay`, `write_preparation` and `read_preparation`. A request declares all
supported policies, the complete typed INIT source and an explicit ordinary
SIM definition of the same family. It carries a full accepted checkpoint,
including both INIT clocks, event/step position, exact array shapes/precision,
complete original definition, physical layout and all native parameters.

Every original physical array survives byte for byte: 34 parent arrays for
calcium and 38 for finite fuel. The new one-entry phase clock gives 35/39 state
arrays in distinct epoch state/layout types. Chemical free/bound cytosol and
ER stores, channel/junction/calcium gates, every transfer/work/heat ledger and
actual ATP/ADP/Pi increments retain the original accounting origin. Original
inventories, energy-pool anchors, volumes, capacities and static profile/default
preparation are unchanged. Host diagnostics use exact host copies of device
snapshot arrays to avoid mixed NumPy/JAX evaluation.

Only the phase clock starts at zero. Explicit new SIM controls/events and their
clock/cursor are initialized for the new epoch. Native baseline/default
parameters are replayed, the scheduled buffer is logically zero before its
first evaluation, and qualified smooth pulse tails remain. Observations retain
all actual state arrays and expose archived INIT phase time plus total accepted
elapsed time. Ordinary restart retains this epoch; ordinary branch, cuts,
remaps and an implicit phase change are outside the operation.

The finite-fuel epoch supplements fresh-run admission with the unchanged 0.05
gross-turnover limit evaluated at actual carried ATP/ADP/Pi and the explicit SIM
controls. Initial maintained or zero-increment pools cannot supply that check.
The qualified maximum scheduled permeability/chemical bounds, native ramp
ceiling, physical domains and original conservation tolerances also remain.

## Independent evidence and retained arrays

The new reference uses the existing independent full calcium/fuel equations.
It adds carried initial conditions and complete held-control segmentation;
it imports no production equations or integration routine. Dependency capture
includes imported functions and legacy unqualified helpers, explicitly
`validation/betse/contact.py` and its `require` assertion helper.

The full suite is designed to compare both complete INIT phases and four
carried SIM trajectories at every declared observation and control boundary.
Cases cover new/replayed controls, empty events and exact Na closure/reopening.
Each compact NPZ contains both timesteps' complete padded production arrays,
independent/production flats, phase-zero state, observation times, field names
and reference shape metadata. Portable definitions and exact typed source
archives preserve reproducibility. Accounting always uses actual full history,
including transfers from INIT on a route that later closes in SIM.

The declared manufactured fixture uses 100 times the original profile
diffusion coefficients. Its first 31.25 ns transient comparison exceeded the
unchanged state budget by 4.130216 times. The original failed receipt, inputs
and logs remain. A separate bounded reproduction is queued to preserve its
previously unwritten full failed arrays from unchanged physical/integration
functions; it is not a passing scientific case.

The finer finite-fuel SIM pilot passed all 21 observation/control-boundary
samples at 15.625/7.8125 ns. Maximum budget ratios were
0.2365613064 / 0.0145368642; transient background-transfer errors were
4.639213e-13 / 2.850817e-14 fmol. Complete source-state/layout preservation also
passed for both owners. These measured transient reductions are distinct from
the previous accepted scheduled-profile component's endpoint-only comparisons,
which were precision-limited and retained no trajectory NPZ. That older evidence
is unchanged; it supplies no trajectory-order claim for this new feature.

## Pending full-suite review and scope

The 62-check component run was launched detached at 09:33:28 UTC:
`/mnt/workspaces/Cells/owned-calcium-phase-development-20261029-04`.
Its launch receipt and durable launcher log are in the sibling `-04-launch`
directory. Completion/failure and resource artifacts are durable. Each phase
uses CPU7, one numerical thread, <=1 GiB guarded process-tree RSS, >=8 GiB host
reserve and a 480 s cap. The total exceeds ten minutes; no automatic polling,
retry or numerical follow-up is scheduled.

Root separately reported 63 passing public checks, including two eager
execution/restart checks, on the same runtime files. That public evidence does
not substitute for the independent transient component. This worker neither
polls Root's jobs nor reruns those public checks.

The component claims only these two complete owners and the explicit
preparation contract. Compiled coupled trajectories, GPU execution, other
calcium versions/compositions, physiological fitting, native full-solver
parity, cuts/remaps and additional phase operations remain outside its scope.
