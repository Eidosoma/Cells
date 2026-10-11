# REF-003e0 expanded SIM bridge

2026-09-12, D077. Prospective capture contract after the user-reviewed D076
closeout. This extends coverage, not physics, tolerances or production code.

## Starting evidence

The [narrow pilot closeout](../runs/ref-003e0-loop-audit-2026-09-12/audit-01/completion.json)
passed 88,956 independent numerical comparisons and 165 focused tests in
32.682 s. It qualifies only the matched-constant, 25 µs, 1 ms, seven-cell
passive/blocked SIM pilot. Its 142 capture files, 11 audit-job files, earlier
accepted/rejected packets and frozen adapter sources stay unchanged.

The [new plan](../validation/betse/expanded_bridge_plan.json) binds that
closeout and the existing refined INIT references. All 352 accepted Cells files
and 51 production modules remain unchanged. No new Cells run is required to
establish this phase/profile/no-op correspondence to the retained INIT panel.

## Coverage and controls

| Axis | Values |
| --- | --- |
| Passive transport | Baseline permeability; completely blocked |
| Constants | Native source F/R; matched Cells F/R |
| Native timestep | 25, 12.5, 6.25 µs |
| SIM profile/event setting | Profiles off; default profile on; default profile with zero-amplitude Na/K/Cl events |
| Observation | Independent observed and unobserved native runs |
| Geometry and duration | Same seven cells / 30 faces, finite bath, 1 ms |

This is **72 fresh native runs**, 36 observed paths / **3360 observed steps**,
36 observer pairs, 24 between-variant comparisons and 1120 enabled-target
zero-amplitude dispatches. The 12 runs overlapping D075 must reproduce that
pilot's physical/numerical records exactly. A variant is not another independent
INIT reference: the panel links to 24 distinct retained INIT mode records.

Every row reuses the unchanged D075 `run_row` and `FullLoopObserver`.
Normal native `run_sim_core` owns dynamics initialization, storage clearing,
pre-loop voltage closure, one FULL loop and SIM serialization. There is no
manual repeat of native setup, fake SIM phase flag or modified model kernel.
The wrapper uses fresh seed/SIM preparation, not a loaded/equilibrated INIT
pickle. Seed/SIM file presence is checked; pickle bytes are neither compared
nor deserialized, and restart is not qualified.

Static metadata expectations come from the unchanged D074 input structure,
with explicit F/R, timestep, sample interval, step count and mapped event times.
These are **derived input expectations, not newly observed preparations**.
The full runner saves each actual core, dynamics, loop-entry state and metadata.
Charge/voltage entry values must match the retained INIT at that row's F/R and
timestep, not a substituted matched-constant preparation. Core concentrations,
geometry, permeability and topology remain exact fixed-input checks.

Capture gates retain exact values, axes, dtypes and byte hashes. They check
all ordinary/final exports against matching INIT, observer noninterference,
profile/no-op noninterference, ownership, fixed controls, event ordering,
complete lifecycle and event/step links. Native raw labels and elapsed time
remain distinct: for N updates the event-time mapping uses N/(N−1). Zero-amplitude
events do not alter physical bytes; later electroflux does include the native
voltage nonce. No approximate gate replaces an exact control.

## Prospective resources

The old pilot measured 26.139 s and about 49.4 MB of retained output. Scale each
pilot row file by its new step count and then by two, including even static
files; add 16 MiB for supervisor/capsule/log overhead. This gives
**1,388,179,444 estimated bytes**, with **42,565,368 estimated bytes** for the
largest individual worker file. This is conservative sizing, not a benchmark.

Step-scaled runtime is 365.943 s; a further 50% allowance rounds to 549 s.
The prospective limits are **600 s for the worker**, **660 s total**,
**2 GiB retained output**, **64 MiB per worker file**, CPUs **0–3** and one
thread per numeric library. Require more than twice the panel allowance in
free disk before registration. The panel byte limit is checked between rows
and at completion, not enforced as a filesystem-wide quota; the worker file
limit uses OS `RLIMIT_FSIZE`. No peak-RAM or GPU speed claim follows.

Process groups are sequential; the checker retains only the current pair and
its group's baseline, not all expanded trajectories in memory. Native durable
partial states and failure traces are preserved. Timeout/error stops the
attempt without retry or deletion. The later independent audit needs its own
prospective resources; the narrow audit's old limits must not be inherited.

## Launch and interpretation

All **125 focused preflight tests pass in 17.67 s**. They exercise actual saved
pilot records, all 36 metadata mappings, synthetic finer-step/F-R extensions,
corruption/coverage gates, resource refusal and timeout/detachment. Synthetic
test fixtures are not native execution evidence. Whole-tree quality and
source/packet preservation are bound by the separate prelaunch receipt.

Register and launch only after that receipt, into a fresh directory:

```bash
.venv/bin/python -B validation/betse/expanded_bridge.py launch runs/ref-003e0-expanded-2026-09-12/capture-01
```

The detached job writes `worker.log`, row snapshots/checks, source/registration
capsules and either `capture.json` or `failure.json`. Launch returns immediately;
status checks are user-requested under [AGENTS.md](../AGENTS.md). No polling,
automatic retry, follow-up audit or regression job is included.

A passing capture means `capture_controls_pass_pending_independent_audit`,
with expanded trajectory qualification still false. The next separately
approved step is an independent saved-data arithmetic/evidence audit and
focused regression using the original criteria. Only after its closeout
should the nonzero held-drive response panel be registered. No biological,
general BETSE-feature, longer-time, organ, restart, GPU or stable-release
qualification is added here.
