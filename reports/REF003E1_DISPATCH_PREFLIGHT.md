# REF-003e1: actual nonzero event-dispatch result

2026-09-12, D080. **The bounded native preparation/dispatch preflight passes.**
No transport or time integration ran; no response trajectory is qualified.

## Native result

The [completion](../runs/ref-003e1-dispatch-2026-09-12/preflight-01/completion.json)
reports **four fresh preparations / 160 event dispatches in 24.463 s**. The
four conditions are default-profile baseline, enabled zero amplitude, static
block and suppression/recovery, at matched F/R constants on the 25 µs hold grid.
Each uses the same seven-cell / 30-face finite-bath setup and 40 declared input
times. There are **80 enabled targeted dispatches**, including **40 nonzero**.

All **57,600 scheduled/effective diffusion-value checks** pass with maximum
baseline-scaled control error **2.670623e-15**, below the unchanged **2e-14**
input-control threshold. Actual default/base diffusion, membrane/cell targets,
scalar/dynamic modifiers, function names, multiplier and mapped pulse times
agree with the declared inputs. Only scheduled/effective diffusion changes.
Recorded concentrations, voltage, charge, current, flux storage, geometry,
temperature, pressure and disabled mechanisms preserve their prepared state.
These are control/state checks, not measurements of biological recovery.

Baseline and enabled-zero dispatch records agree exactly. The three normal-
diffusion cases have identical fresh physical preparations; the static-blocked
case matches its retained blocked preparation. Every fresh initial state agrees
with the corresponding qualified D074 preparation and retained INIT values.
No retained initialization pickle was loaded into a native phase.

The native event handler was called, not a transcription of its formula.
Read-only preparation/dispatch hooks prohibited transport and solver entry;
no Cells runtime was imported. There were **no Python warnings**. Direct
dispatch at increasing labels is not a trajectory: state was not advanced
between those labels. Full-loop noninterference still needs observer-off/on
response partners.

## Evidence, tests and resources

The [plan](../validation/betse/dispatch_preflight_plan.json),
[contract](../docs/BETSE_NONZERO_DISPATCH_PREFLIGHT.md), input mapping, checker,
runner and tests were frozen before native execution in the
[prelaunch receipt](ref-003e1-dispatch-prelaunch.json). All **75 focused tests
pass in 8.48 s** in [checks-02](ref-003e1-dispatch-checks-02.xml), with failures,
errors and skipped all zero. All **352 Python files** pass lint/format checks.
No old full suite or production matrix was rerun.

The [earlier 74-test pass](ref-003e1-dispatch-checks-01.xml) in 7.89 s is retained.
Before registration, the prepared-state gate was moved ahead of dispatch and
one interrupted-dispatch persistence test was added. There was no failed
native attempt, post-capture source change, equation change or automatic retry.

The attempt contains **201 files / 200 manifested payloads**, including every
completed event in its own exclusive file and its matching aggregate record,
prepared states, YAML, seed artifacts, results, log and an **80-file source
capsule**. The worker checks all **332 installed native Python files** against
the pinned source. Local inspection verified the complete payload/row manifests,
capsule members/hashes, retained-reference hashes and individual-event/aggregate
equality. This inspection is not a separate trajectory arithmetic audit.

Actual output before the completion receipt is **25,283,869 bytes**. It fits
the prospectively registered 64 MiB panel / 16 MiB worker-file limits, and
runtime fits the 45-second worker / 60-second attempt limits. Execution uses
CPUs 0–3 and single-threaded numeric libraries. The prospective estimates were
33 worker seconds and 46,197,248 bytes; no peak-RAM or GPU measurement is claimed.

Anchors:

- Prelaunch: `8b443dc54529caefd981220839eb415aa43ab2f2827f32417685a1cab41c3843`.
- Native completion: `91cedba21666e3787601a6b466d8feb72ac173a5fa49b9666582d85b542bab3d`.
- Source capsule: `f45a11cf74e50b410ec276b510fab3b9834edb323682fe66e4db0272c445db92`.

The [preservation baseline](ref-003e1-dispatch-preservation.json) covers **942
pre-existing files**, permitting only seven existing status-document edits.
The [handoff receipt](ref-003e1-dispatch-handoff.json) binds final document/test/
source and attempt hashes. All **352 accepted files / 51 production modules**,
the 802-file expanded capture, 11-file expanded audit and older evidence remain
unchanged. Stable stays 0.14.0; accepted development stays 0.15.0.dev0.

## Next step

Implement the control-aware **eight-native / 24-Cells response pilot**, including
observed/unobserved native partners and eager/compiled Cells solver subdivisions
at a fixed hold interval. Register actual inputs, observation sides, original
physical criteria, source hashes and prospective runtime/storage limits before
integration. The new fresh-phase/mapping helpers can supply its preparation;
do not reuse a phase after this preflight has already initialized dynamics and
fired probe events.

No trajectory is launched automatically. Future long capture/audit jobs remain
detached with durable artifacts and user-requested status checks. A passing
dispatch preflight establishes input application at initial physical state,
not a nonzero response, recovery physiology, native/forcing refinement,
restart, GPU behavior, organ function or stable release qualification.
