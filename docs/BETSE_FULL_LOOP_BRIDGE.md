# REF-003e0 / D075: narrow full-loop bridge pilot

2026-09-12. Prospective execution contract following the
[passing D074 preparation](../reports/REF003E0_PROFILE_BRIDGE.md). This is a
**12-run integration pilot, not the expanded bridge or a nonzero intervention**.
Its [machine plan](../validation/betse/full_loop_bridge_plan.json),
[prelaunch checks](../reports/ref-003e0-loop-prelaunch.json) and
[handoff](../reports/REF003E0_FULL_LOOP_PILOT.md) are separate from every earlier
protocol and result. Production equations and acceptance criteria remain frozen.

## Question and coverage

Does the unchanged passive/blocked seven-cell finite-bath trajectory survive
moving from INIT to fresh SIM, enabling the default profile, and enabling
zero-amplitude targeted events, without our observer changing the outputs?

| Input axis | Pilot coverage |
| --- | --- |
| Case | Passive and fully blocked membranes |
| Configuration | Profiles off/events off; default profile on/events off; default profile on/zero-amplitude Na/K/Cl events |
| Observation | A freshly seeded observed and unobserved run for each configuration |
| Physical/numerical inputs | Matched constants, native 25 µs update step, 1 ms elapsed horizon, seven cells / 30 faces |

This gives six independent observed runs and six independent observer-off
partners. Each observed run has 40 integration steps and event dispatches:
**240 observed dispatches**, of which **80 enable the zero-amplitude Na/K/Cl
event settings**. The other 160 calls still execute the SIM dispatch path with
those settings disabled. Do not report all 240 as enabled targeted events.

The first pilot deliberately keeps D074's exact input coverage. Both constant
sets and the 25/12.5/6.25 µs ladder remain the subsequent expanded bridge, which
would contain 72 native runs / 3360 observed steps. A pass here does not qualify
that expansion. Broader coverage needs its own registration and resource budget.

No new Cells runs occur: the accepted REF-003d v2 packet, its eight Cells records
and independent material/charge/source-law/refinement closeout remain unchanged.
The pilot compares each SIM numerical record to the corresponding retained INIT
record at the same constants, timestep, case and observation mode. This provides
a narrow exact link to existing evidence, not a fresh cross-simulator refinement
campaign or new biological validation.

## Native lifecycle and observation

Use D074's frozen configuration mapping and fresh-phase helper: seed with the
registered seed, construct a fresh SIM phase, and call its native `init_core`.
Then call normal `run_sim_core` once. That method owns `init_dynamics`,
`clear_storage`, initial charge closure, the FULL loop and native SIM saving.
Do not reuse a phase already prepared/probed by the preparation-only adapter,
load an initialization pickle, replace a native method, or apply controls in
an observation callback.

The new lifecycle observer extends the frozen event observer using the same
single `sys.setprofile` dispatcher. It verifies the exact native file and object,
one normal setup sequence, one full loop and return, and one dispatch before all
six native ion-flux calls before each concentration/voltage update. Existing
profiling hooks are refused; normal/error exits restore the hook. The
observer-off partner has no profiling hook during setup or integration.

Record raw native labels, update-clock columns and storage indices separately.
For 40 steps, raw label k is `k * 40 * dt / 39`, while pre/post-update elapsed
times are `k * dt` and `(k + 1) * dt`. Event input times retain the declared
40/39 conversion; the native clock is not rewritten. Ordinary storage contains
indices 1–39, with index 0 retained through the observed trace.

## Prospective gates

- Fresh core, dynamics, loop-entry state, geometry, topology and setup metadata
  must reproduce the corresponding accepted D074 preparation exactly.
- Each SIM run must match its retained INIT numerical record exactly, excluding
  the YAML digest (phase/configuration/output paths differ). Compare all nine
  ordinary and ten final typed arrays, complete legacy trace values when
  observed, constants, mechanisms, ion table, geometry and numerical metadata.
  Typed array shape, dtype, values and byte digest all matter; old list-only
  trace data support exact values, not an invented typed-byte guarantee.
- The six observed/unobserved pairs must match physical setup, ordinary/final
  numerical arrays, final state, metadata and topology. Both alternative
  configurations must independently match the profiles-off baseline's physical
  evidence and complete observed trajectory, giving four variant comparisons.
- Each event must preserve its complete copied before/after state and control
  records exactly. Effective diffusion stays at its case-specific baseline;
  scheduled diffusion, pressures and disabled junction transport stay zero.
  Resolved targets, configured versus effective cutting/voltage flags, pumps,
  temperature, finite bath and all disabled mechanisms remain checked.
- Compare matching boundaries. The pinned FULL loop resets flux arrays before
  dispatch, then `sim_toolbox.electroflux` adds its `1e-25` nonce to its voltage
  argument in place. The post-flux copy therefore links to the legacy
  before-concentration-update trace, not to an incorrectly unchanged entire
  post-event state. Native prior-step current semantics are also retained.
- Final metadata must report a seed pickle and SIM pickle present, and no INIT
  pickle. Metadata may differ from preparation only in the SIM-presence flag.
  Normal completion and file presence are checked, **not pickle byte equality,
  deserialization or restart qualification**.

The capture worker performs these predeclared exact-control checks. It does not
rerun or weaken independent numerical criteria. Successful capture is named
`capture_controls_pass_pending_independent_audit`, with `trajectory_qualified`
false. The separate saved-data audit is a subsequent user-requested step.

## Resources and failure evidence

Use CPUs 0–3 and single-threaded numerical libraries, a **120-second native
worker timeout**, **150 seconds overall**, **256 MiB panel artifacts**, and a
**32 MiB per-worker-file OS limit**. Panel storage is checked between rows and
at completion with 1 MiB terminal headroom; it is not a filesystem-wide quota.
The overall elapsed gate is checked by the detached supervisor around its
timeout-bounded worker and receipt work, not a separate OS watchdog on every
supervisor instruction.

The prospective storage estimate is **142,920,656 bytes (136.30 MiB)**: maximum
retained preparation-state JSON size, three copies per observed step with a
factor-two allowance for evolved values/indentation, retained native-record
sizes, 4 MiB per run for native outputs/metadata/logs, and 8 MiB additional
headroom. This is a sizing allowance, not a measured new runtime. D074's six
preparations took 17.360 s; twelve native loops plus copying/serialization
justify a separate larger worker budget. No scalability or GPU speed claim.

Every run saves its start/input/core evidence. Observed runs save dynamics and
loop-entry physical state before optional loop metadata. After integration,
final physical state is saved before final metadata. Catchable errors preserve
a failure receipt and partial observer copies where available; a hard worker
timeout can only preserve already-written stages, prior completed rows and logs.
Exclusive writes reject replacement of old evidence. Any failure stops the
pilot without retry, retuning or automatic expanded runs.

The launcher snapshots all adapter/input sources before spawning the detached
supervisor. The native worker verifies its installed Python sources against the
pinned BETSE checkout, imports no Cells runtime, and exports durable row checks,
logs and a terminal capture/failure manifest. Run location:
`runs/ref-003e0-loop-2026-09-12/pilot-01`.

Follow [the workspace policy](../AGENTS.md): return control after detached
launch; no assistant polling, automatic saved-data audit or regression campaign.
On the next user instruction, inspect status first. If capture passes, audit
the saved packet independently before deciding on the expanded bridge and then
the separately held-drive nonzero suppression/recovery comparison.
