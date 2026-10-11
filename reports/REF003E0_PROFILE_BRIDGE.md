# REF-003e0 v2 / D074: profile bridge preparation passes

2026-09-12. **Six native preparations and all 30 direct event dispatches pass;
no integration or trajectory qualification.** The
[versioned bridge](../docs/BETSE_PROFILE_BRIDGE_PREFLIGHT.md) resolves the D073
profile prerequisite explicitly. Its first failed attempt remains unchanged.

## Result

The [preparation receipt](../runs/ref-003e0-v2-2026-09-12/preflight-01/completion.json)
records **17.360 seconds**, within the 35-second worker budget on CPUs 0–3.
Artifacts before the completion receipt occupy **4,136,744 bytes**, within the
32 MiB limit. There are 58 payload files plus the completion receipt, a 51-file
adapter/input source capsule, and 332 verified installed native Python files.

Both passive and blocked cases completed all three independently seeded SIM
preparations: profiles off/events off, default profile on/events off, and default
profile on/zero-amplitude Na/K/Cl events. In every case:

- Initial concentrations, charge-derived voltage, charge density, current and
  boundary-voltage values match the retained INIT initial record exactly; native
  diffusion arrays match its accepted constant-diffusion bytes.
- Core state, geometry and junction topology stay unchanged through profile and
  dynamics initialization. All four between-configuration comparisons preserve
  physical preparation and dispatch evidence exactly, including typed array bytes.
- Profiles-off metadata correctly records no resolved default and empty maps.
  Profile-enabled metadata resolves only `Base`, all seven cells / 30 faces, with
  no extra tissue or cut profiles. Zero-amplitude events target all 30 faces for
  each of Na/K/Cl, with the declared mapped times and literal `None` modulator.
- Each of five direct dispatches per preparation preserves every recorded
  before/after state and control byte. Temperature, pressure, diffusion and
  pump/GJ blocking data stay fixed; flux arrays remain zero because no transport
  is executed. Only the two zero-amplitude rows enable the targeted events.
- Setup observation records one seed, two `init_core` calls (seed and fresh SIM),
  one `init_dynamics`, one `clear_storage` and one charge-closure `update_V`.
  Integration-entry guards remain active during preparation/dispatch, and hooks
  are restored. No Cells runtime or native trajectory entry point is called.

There are no Python warnings. The native log retains its expected diagnostic
about an ignored cutting request: upstream YAML still requests cutting, but the
cut-profile list is empty and the effective cutting event is absent. Configured
and effective flags are checked separately, not silently rewritten.

Completion SHA-256:
`e98c0bbef8d871baed90a20ca55ac4c76adb1351b156a1739e6f5d8ace477b8c`.
Registration SHA-256:
`5ea5de7646c22a820c415739de3eabbb2b590784aeccc1708799735e102f80a8`.
Source capsule SHA-256:
`428e66440bb709d408027f23eb8c5ec29a5b3f45a4062488bda181fc993c1d57`.

## Engineering and verification

Each preparation retains `core`, `dynamics`, `ready`, `metadata`, `dispatch` and
`final` JSON records. `ready` is saved before optional metadata access. A failure
injection test verifies that missing metadata cannot discard that physical-state
record; exclusive writes prevent overwrite. Native source and production remain
unmodified, and the old rejected launcher still rejects its unamended candidate.

The [final focused receipt](ref-003e0-v2-checks-02.xml) records **87 passing tests**,
with no failures/errors/skips. The first receipt retains 86 pre-execution checks
with the saved-attempt case deselected. Tests cover the explicit mapping over
both constants profiles and all three candidate step sizes, synthetic state/
metadata corruption, partial persistence, and the actual saved six-preparation
packet. Synthetic checks are not substitutes for native evidence; actual runtime
coverage remains matched constants at the configured 25 µs step only.

The [handoff](ref-003e0-v2-handoff.json) binds the current code to the preparation
capsule and preserves the entire previous D073/D072 evidence chain, both REF-003d
packets, all 352 accepted implementation files / 51 production modules, and all
prior scientific criteria. Only seven existing status documents change. The
source tree passes lint/format checks across 327 Python files. No old full adapter
suite or 4190-test production matrix was rerun, and no native attempt was retried.

## Next boundary

This establishes preparation and zero-amplitude dispatch compatibility, **not**
INIT/SIM trajectory equality, full-loop observer noninterference, serialization,
restart, a suppression/recovery response, biology or GPU performance. No new
trajectory has been registered or launched. Next specify and implement the
bounded full-loop phase/profile/event bridge, retaining exact controls,
observed/unobserved partners and independent trajectory/refinement criteria.
Use fresh phases and a separately justified runtime/storage budget. Long jobs
and subsequent audits remain detached and user-polled.
