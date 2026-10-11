# REF-003e1 / D084 finer-response handoff

2026-09-13 UTC. Implementation/prelaunch handoff; actual execution is separate.
See the [prospective contract](../docs/BETSE_REFINED_RESPONSE_PANEL.md) and
[plan](../validation/betse/response_panel/refined_response_plan.json).

D083's inspected native preflight passes in 116.002 s: eight preparations,
960 direct dispatches, 345,600 diffusion-value checks, maximum error 2.671e-15
against the unchanged 2e-14 limit, no transport or integration. Its 1042 files
and 98-input capsule remain frozen. D081's 150 rejected comparisons and D082's
independent failure closeout also remain intact.

The new adapter covers only the two finer holds (12.5/6.25 µs), all four
conditions, fresh native observer pairs and separate Cells eager/JIT 1/2/4
subdivisions. Reuse the frozen 25 µs evidence explicitly. New source is under
[response_panel](../validation/betse/response_panel/refined_response_context.py);
neither simulator, its numerical criteria nor previous adapter code changes.

The first software run retains **96 passes / four failures in 60.79 s** in
[checks-01](ref-003e1-refined-response-checks-01.xml). Two failures exposed a
step-count variable collision in the new native checker; one corrected the
surface-count expectation; one corrected the test's fence exception expectation.
No engine or physical threshold changed. All **24 targeted checks pass in
31.84 s** in [checks-02](ref-003e1-refined-response-checks-02.xml), including
exact overlap with the original coarse arithmetic/surfaces and late-grid
corruptions. All **375 Python files** pass lint/format checks.

The complete **114-test** suite is a separately registered detached software
attempt under `runs/ref-003e1-response-refined-preflight-2026-09-13/checks-01`.
Only its actual launch/completion/failure files determine execution state.
Budget: 180-second pytest worker, 300-second total, CPUs 0–3, 16 MiB aggregate
and 8 MiB worker-file caps. It freezes the 106-input capsule, task files and
both earlier test receipts. It does not create response prelaunch or launch
either simulator. Return control without polling; review it on user instruction.

Software receipt and source freeze are separate durable files:

- [Preservation](ref-003e1-refined-response-preservation.json): 990-file baseline,
  150 response / 16 audit / 1042 dispatch files and accepted production.
- Focused check receipts: `ref-003e1-refined-response-checks-*.xml`. They test
  saved records and explicitly synthetic fixtures; they are not new ODE evidence.
- Prelaunch: `ref-003e1-refined-response-prelaunch.json`, created only after the
  full software completion is reviewed and whole-tree quality checks pass. It binds test hashes,
  source hashes, unchanged criteria, documentation, and prospective resources.

New work is 16 native / 48 Cells runs, 960 observed native updates and
13,440 accepted Cells steps. Native/Cells/comparison limits are 300/10,800/300 s;
total limit 11,700 s; CPUs 0–3, float64, 1 GiB artifacts, 64 MiB worker files.
Measured-D081 scaling plus allowances estimates 239/10,004/125 s and
520,964,299 bytes. No peak-RAM or GPU measurement is claimed.

Intended fresh destination:
`runs/ref-003e1-response-refined-2026-09-13/capture-01`.
Only its actual `launch.json` establishes launch; `capture.json` or
`failure.json` establishes completion. Do not infer either from this handoff.
Launch once detached and return without polling. Any later audit/regression
waits for user instruction.

All internal, fixed-input solver and backend gates are required at every hold.
Finest 6.25 µs cross-engine gates are required; coarse/intermediate and
across-hold discrepancies remain visible, separately labelled rejections.
Totals include those failures even when the required-gates summary passes.
Native pulse resampling is not isolated solver refinement. Native convergence,
forcing convergence, overall trajectory qualification, biology and GPU remain
unqualified pending separately scoped evidence and audit.

Next user-authorized sequence after a passing software completion:

1. Authenticate its registration, capsule, all manifested files, 114-test JUnit
   and unchanged production/evidence; do not rerun either simulator.
2. Freeze response prelaunch using that exact `regression.xml` and expected
   test count 114. The context refuses a partial focused suite.
3. Launch only the 16-native / 48-Cells capture detached. Return without polling.
4. Inspect actual capture/failure on a later status request; independent
   numerical audit and regression need their own subsequent scope and budget.
