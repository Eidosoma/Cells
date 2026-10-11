# REF-003e0: SIM preparation and the tissue-profile prerequisite

2026-09-12, D073. **Adapter/observer implemented; native preparation preflight
failed. No bridge trajectory is registered, executed or qualified.**

The [D072 design](BETSE_INTERVENTION_PLAN.md) remains frozen historical evidence.
This follow-on records a runtime prerequisite that its control-only probes did
not exercise. See the [attempt report](../reports/REF003E0_PHASE_PREFLIGHT.md).

## What is implemented

- A separate [SIM-from-neutral adapter](../validation/betse/phase_bridge.py),
  using the pinned native configuration loader, seed and fresh `SIM`/`init_core`.
  It does not load the end of the accepted transient as a new initial condition.
- An explicit mapping for SIM timestep, sampling and duration, plus disabled or
  zero-amplitude Na/K/Cl inputs with D072's raw/elapsed clock conversion.
- A new [read-only event observer](../validation/betse/native_event_observer.py).
  One profiling dispatcher routes by source file, object and phase identity.
  It copies pre-/post-dispatch state, diffusion and pressure data, watches native
  membrane-flux calls, and delegates ordinary step/storage observation to the
  unchanged REF-003d observer. It never applies a control or replaces a method.
- A preparation-only mode and entry guards against native integration and
  transport. The CLI has no trajectory command. Prospective state/array checks
  require matching initial conditions, exact no-op copies and finite typed bytes.

The **73 passing focused tests** cover mapping, synthetic step/event ordering,
copy isolation, legacy-observer correspondence, hook restoration, integration
entry guards, the source prerequisite and preservation of the failed attempt.
They do **not** establish full-loop native observer noninterference or a passing
native preparation. Those positive gates remain unexecuted/unqualified.

## What the first native attempt found

The accepted baseline explicitly sets `tissue profile definition / profiles
enabled: false`. The actual native preparation reached the first disabled-event
row's metadata export, which raised `AttributeError` on `dyna.tissue_default`.
That adapter assumption was wrong for the unchanged baseline. No completed
preparation JSON was written; the log, configuration, seed, registration and
source capsule are retained. The zero-amplitude row was not reached.

Pinned [TissueHandler source](../upstream/betse-v1.5.0/betse/science/tissue/tishandler.py)
explains the deeper dependency:

1. `_init_tissues` returns early when profiles are disabled, without constructing
   the default tissue; the profile dictionary is empty.
2. `init_profiles` consequently creates an empty target map.
3. Enabled targeted events resolve their named profiles through that map in
   `_finalize_events_tissue`, then use the tissue-default diffusion when firing.

Thus simply making metadata tolerate a missing field would not enable the
planned targeted event path. The YAML default-profile comment is not sufficient
evidence that this runtime object exists when profiles are disabled.

The current launcher rejects the unamended candidate before creating another
output directory or starting a worker. No automatic retry, default-profile
activation or upstream patch was made. The failed packet remains failed.

## Next version: separate phase, profile and event effects

Before another preparation attempt, specify three explicit configurations for
both passive and fully blocked cases:

| Configuration | Tissue profiles | Targeted events | Purpose |
| --- | --- | --- | --- |
| Baseline SIM | Off, as in retained INIT | Off | Isolate the phase change |
| Default-profile SIM | On; only the homogeneous default, no extra/cut profiles | Off | Isolate profile initialization |
| Zero-amplitude SIM | Same default-only profile | Na/K/Cl enabled, multiplier zero | Isolate event dispatch |

Keep geometry, all ion inventories and auxiliary charges, actual diffusion,
temperature, bath, pump/GJ/field/mechanics/noise settings and constants fixed.
Check the effective cutting/voltage-event flags explicitly; an empty cut-profile
list must not become an active cutting event when enabling tissue profiles.
Retain separate configured defaults and resolved runtime profile/target metadata;
absence is valid for the profiles-off baseline, not an empty successful target set.

Improve partial-state persistence before optional metadata/acceptance checks, so
another setup failure cannot discard the already copied state. Then register a
fresh bounded preparation-only attempt with its own source capsule and resource
limits. Do not overwrite or reinterpret preflight-01. Existing success-check
scaffolding needs actual preparation evidence and corruption tests in that version.

Only after preparation passes should a separate trajectory protocol/worker be
implemented and registered. It must test exact INIT/SIM baseline correspondence,
profile/no-profile correspondence and zero-amplitude/no-event correspondence,
including observed/unobserved partners. Carry forward ordinary/final arrays,
material/charge accounting, source laws and unchanged refinement criteria. Reuse
of old Cells evidence must be labelled as reuse. Response experiments follow
successful bridge closeout, not merely passing observer unit tests.

## Architecture consequence

Keep capability prerequisites explicit and validate them before scheduling an
experiment. A model feature being disabled is different from its data structures
being available but inactive. Record configuration transitions and test each
independently; do not silently enable a dependency inside an observer or adapter.
This will also matter for optional region physics and future multiscale/GPU
execution. No production architecture, equation, dependency or GPU policy changes
in this slice. Long jobs and follow-up audits remain detached and user-polled.
