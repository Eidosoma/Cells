# D106 timed block/release independent audit — handoff

User authorization: “lets go” after the D105 capture status. This task is the
independent saved-data audit only. No simulator or reference integration rerun,
production change, regression campaign, polling or automatic follow-up.

Implementation: `validation/betse/channel_release_audit/`.
Contract: `docs/BETSE_CHANNEL_RELEASE_CLOSEOUT.md` and `plan.json`.
Target: `runs/ref-004d-timed-release-2026-09-16/capture-01`.
Intended fresh output: `runs/ref-004d-timed-release-audit-2026-09-16/audit-01`.

All **116 software checks pass**, with disjoint final coverage:

- `ref-004d-release-audit-checks-04.xml`: 103 tests, 41.99 s.
- `ref-004d-release-audit-checks-05.xml`: 13 tests, 43.13 s.

Coverage includes a complete saved 80-step native block/release case and every
numeric column in its ledger; independent exact mean and original-diagnostic
records; first-step and both-side probes for all eight history/condition cases;
full Cells state/restart/backend ledgers for both histories; every complete
checkpoint byte and event clock; all switch-side RHS ledgers; all trajectory,
no-op, side-contact and 12 contrast groups; refinement reconstruction; corruption
rejection; model-import/write guards; and detached controller success, failure,
deadline and no-polling controls. These software checks are not the full audit.

The two earlier XML receipts and the
[software timeout](REF004D_RELEASE_AUDIT_SOFTWARE_TIMEOUT.md) are retained.
Repository lint, formatting (711 Python files) and whitespace checks pass.
The new capsule has 203 source inputs and 37 historical report bindings; the
final two software XML receipts are separately bound. The 555-file capture,
194 capture source inputs and 352 accepted implementation files / 51 production
modules are preserved.

Final software receipts, source capsule and this handoff are hash-bound by
registration. Launch once with CPUs 0–3, 1,800 s, 128 MiB/file and 256 MiB total
disk artifacts. Actual launch and terminal state must be read from the output
receipts, not inferred from this preparation note. Return without polling.

Preserve all 49 coarse-grid misses. Any completion qualifies only the fixed
seven-cell/two-history/four-condition 2 ms numerical fixture at registered finest
grids and refinement. It does not expand biological or feature-parity claims.
