# REF-003e0 / D073: first SIM-phase preflight

2026-09-12. **Native preflight failed; 73 focused software/negative-evidence
checks pass. No new trajectory or biological qualification.**

The new adapter and combined event/step observer are described in the
[bridge note](../docs/BETSE_SIM_PHASE_BRIDGE.md). The source-bound
[handoff receipt](ref-003e0-preflight-handoff.json) separates software checks from
the actual native failure.

## Executed attempt

[preflight-01](../runs/ref-003e0-2026-09-12/preflight-01/registration.json) froze
four preparation rows before execution: passive/blocked, matched constants,
25 µs candidate step, disabled/zero-amplitude events. Each proposed five direct
event dispatches at mapped 0/0.3/0.5/0.7/1 ms, without any transport or stepping.
The limit was 25 seconds on CPUs 0–3 and 16 MiB of artifacts. It stopped after
**9.491 seconds**, without retrying or launching a trajectory.

The first disabled-events row reached metadata export after native preparation.
The [native log](../runs/ref-003e0-2026-09-12/preflight-01/worker.log) reports
`AttributeError: 'TissueHandler' object has no attribute 'tissue_default'`.
The adapter incorrectly assumed that a resolved default tissue existed with
profiles disabled. Source inspection confirms the early return and empty target
map; the proposed enabled targeted events also need those structures. Their
runtime execution was **not reached**, so this is a source-supported prerequisite,
not an observed zero-amplitude event failure.

There are **zero completed preparation result files**, no completion/worker-success
receipt and no INIT/SIM trajectory pickle. Six failed-attempt files are retained:
registration, source capsule, worker log, failure receipt, native YAML and seeded
world. The missing intermediate-state receipt is an adapter observability gap to
fix before the next version. No passing preparation equality, event response,
observer noninterference or serialization result is inferred from the partial run.

Failure receipt SHA-256:
`a59ff3debb871735a8376a0a18805a3aadb0ca2d899518cb6520819261a59c95`.
Source capsule SHA-256:
`a55df2422cddacd02de18eb7af57bb4793e98c42575505f11e9f44eddcae0c24`.

## Checks and preservation

The [final focused test receipt](ref-003e0-preflight-checks-04.xml) records 73
passes, no failures/errors/skips. Synthetic fixtures test actual Python profiling
boundaries but are explicitly not BETSE trajectory evidence. Early receipts are
also retained: 68 checks in attempt 01; 68 checks with 24 prospective saved-success
cases deselected in attempt 02; 73 passing checks in attempt 03. Since no successful
native result exists, the current suite checks the actual failed packet and
prerequisite instead; the original prospective success tests remain in its capsule.

Post-attempt changes add a fail-fast profile-prerequisite guard, negative-evidence
tests and this handoff. The unchanged candidate can no longer launch another
worker. No native rerun was performed to make the tests pass; no numerical
tolerance or old evidence was changed. The final handoff binds the captured and
current adapter versions separately. All 352 accepted files / 51 production
modules, both REF-003d packets, their captured sources and the D072 review remain
unchanged. The previous 325-test adapter suite and 4190-test production matrix
were not rerun; the source tree passes lint and formatting checks.

Next: explicitly version the profiles-off → default-profile-on → zero-amplitude
bridge, improve partial-state export, then run a new preparation preflight on user
instruction. Register a trajectory only after that prerequisite passes. Stable
0.14.0, accepted development 0.15.0.dev0, biology and GPU status are unchanged.
