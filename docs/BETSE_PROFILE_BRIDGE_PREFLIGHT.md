# REF-003e0 v2: explicit profile bridge before trajectory work

2026-09-12, D074. **Preparation and event-dispatch checks only.** This version
addresses the [D073 finding](BETSE_SIM_PHASE_BRIDGE.md) without changing its
failed packet, source capsule, rejected launcher or historical report. Actual
execution and test outcomes are recorded in the
[v2 report](../reports/REF003E0_PROFILE_BRIDGE.md).

The six-preparation capture now passes, including 30 direct event dispatches,
with all 87 focused tests passing. Full-loop trajectory work remains separate.

## Explicit configurations

The [versioned input plan](../validation/betse/profile_bridge_plan.json) specifies
six independent native preparations: both passive and fully blocked cases under
each of these configurations.

| Configuration | Tissue profiles | Targeted events | Comparison |
| --- | --- | --- | --- |
| `baseline` | Off, matching REF-003d | Off | SIM initial state versus retained INIT initial state |
| `default_profile` | On; homogeneous `Base` only | Off | Physical setup versus profiles-off SIM |
| `zero_amplitude` | Same default-only profile | Na/K/Cl, multiplier zero | Setup and dispatch copies versus no-event controls |

The only additional configuration change relative to the previous explicit
SIM/event mapping is the declared profile-enabled flag. Extra tissue and cut
profile lists remain empty. The upstream YAML's cutting-event request remains
true, as in the old baseline, but the actual cutting event must remain absent
with an empty cut-profile list. Record configured and effective flags separately;
do not mistake its diagnostic log message for an active cutting process.

Keep all seven cells / 30 membrane faces, geometry, finite bath, auxiliary charge
species, actual diffusion constants, temperature and disabled transport/field/
mechanical/regulatory mechanisms. Use matched constants and a configured 25 µs
SIM step / 1 ms horizon for this preparation test. This is not a newly accepted
timestep or a runtime check of the entire constant/step ladder.

The actual event handler is called at five declared elapsed probe times,
0/0.3/0.5/0.7/1 ms, mapped to native labels by D072's `N/(N-1)` factor. These are
direct preparation probes, not solver-loop iterations; no concentrations are
stepped between them. Only the zero-amplitude rows enable Na/K/Cl interventions.
The no-event rows still exercise native dispatch with those options disabled.

## Adapter and durable partial evidence

[profile_bridge.py](../validation/betse/profile_bridge.py) is separate from the
frozen D073 adapter. It uses native loading, seeding, fresh `SIM` construction and
`init_core`, followed by the ordinary setup operations `init_dynamics`,
`clear_storage` and `update_V`. It never calls `SimRunner.init/sim`, loads an old
trajectory pickle, or enters transport or integration. The frozen preparation
fence and event observer enforce those boundaries without replacing native methods.

Each preparation writes exclusive, successive records:

1. `core.json`: core arrays, geometry and junction topology after fresh `init_core`.
2. `dynamics.json`: the same fields after profile/dynamics initialization.
3. `ready.json`: charge-closed state, starting readouts, phase mapping and observed
   setup-call counts, saved **before** optional profile metadata is accessed.
4. `metadata.json`: configured default and nullable resolved default, target maps,
   phase clock, mechanisms, constants and output paths. Validate before dispatch.
5. `dispatch.json`: read-only before/after copies for every requested dispatch.
6. `final.json`: final setup and metadata; `result.json` links all stages only
   after the row passes.

On failure, retain every completed stage plus explicit worker/controller failure
receipts. Do not overwrite, retry automatically or invent missing observations.
The bounded worker limit is **35 seconds**, CPUs **0–3**, **32 MiB** of artifacts.
The source capsule and plan are written before native preparation begins.

## Gates and limits of the result

The [separate checker](../validation/betse/profile_bridge_check.py) verifies typed
finite array bytes and expected axes, exact retained INIT initial values,
unchanged native diffusion bytes, concentration ownership, all target maps,
disabled mechanisms, zero pressure/scheduled diffusion/flux, setup-call coverage,
and unchanged state across direct no-op dispatches. Four between-configuration
comparisons require identical physical preparation and dispatch evidence.
Configured metadata is deliberately different where a profile/event was enabled.

Synthetic corruption tests are software checks, not native evidence. The saved
native-attempt test separately checks the actual completion or explicit failure;
passing tests cannot turn a failed preparation into a passing native result.
The reference interpreter and all installed native Python files must match the
previous pinned source. Cells production is neither imported nor run.

A preparation pass would not establish native full-loop observer noninterference,
INIT/SIM trajectories, serialization/restart, the complete constants/step ladder,
intervention response, biology or GPU behavior. The next step is a separate
bounded trajectory protocol and worker using fresh phases, with observed/unobserved
partners and exact baseline/profile/no-op correspondence. Size its expanded
coverage and event evidence explicitly; do not reuse this preparation budget as
a trajectory budget. Actual trajectories and follow-up audits remain separate,
user-directed stages; long jobs remain detached and user-polled.
