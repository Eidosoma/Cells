# D076 / REF-003e0: independent saved-pilot audit

2026-09-12. The [D075 pilot](BETSE_FULL_LOOP_BRIDGE.md) completed all 12 native
runs / 240 observed steps in **26.139 seconds**, with its predeclared capture
controls passing. Its capture receipt still correctly says pending independent
audit. This separate audit does not change that receipt, rerun either simulator,
or expand the pilot's physical/numerical scope.

## Independence and preserved evidence

The [audit](../validation/betse/full_loop_audit.py) reads saved JSON and source
text only. It imports neither simulator nor NumPy/JAX, refuses those imports
during execution, and never deserializes native pickles. It does not call the
pilot's capture checker. Separate code verifies the records and their links;
the existing, frozen independent arithmetic routines verify physical laws under
the original REF-003d v2 tolerances.

Anchor the pilot's registration, capture receipt, source capsule and launch
receipt separately. Preserve all **142 packet files**, including 138 finalized
payloads and the operational files. Check exact path coverage, regular files,
nonempty payloads, digests, capsule members, source identities, worker metadata,
declared versus observed coverage, chronology, launch identity and byte budgets.
The 58-member original capsule remains unchanged; adding audit tooling does not
make that historical capsule obsolete or require editing its adapters.

The new preservation baseline contains **903 workspace files**. Only the seven
existing status documents may change. All 352 accepted implementation files /
51 production modules, D075's new files/prelaunch receipt, D074's preparation,
the failed D073 attempt and earlier accepted/rejected panels remain frozen.

## Recomputed checks

For all twelve runs, independently link fresh setup and final state to the
accepted preparation, recorded metadata and corresponding retained INIT
numerical record. Compare all typed ordinary/final arrays, observation partners,
profile/no-op controls, final copied state and native seed/SIM-file presence.
File presence is not pickle-content, restart or native-file byte equivalence.

For all six observed trajectories, recompute the existing independent checks:
constant-field ion flux using the 70-digit Decimal expression; concentrations,
charge-derived voltage, charge density and current; per-cell and finite-bath
single-step and accumulated transfers; blocked/inactive paths; ordinary samples,
final arrays and auxiliary output links. This yields **88,956 numerical
comparisons**: 14,826 per observed run, using unchanged registered criteria.

Independently validate all 240 event records, of which 80 have targeted
zero-amplitude settings enabled. Require normal setup/loop coverage, exact
before/after-event equality, fixed inactive controls, native ion order, correct
pre-event flux reset, typed-array bytes and membrane ownership. Link post-flux
copies to the matching legacy trace boundary. Parse the pinned flux source's
`1e-25` voltage nonce and check its six successive floating-point additions;
do not misidentify that source side effect as event-induced physics.

This rechecks the saved 25 µs matched-constant pilot. It is **not a new timestep
refinement or Cells simulation**. Exact correspondence links to the existing
REF-003d v2 evidence; the expanded two-constant-set / three-timestep SIM bridge
still needs separate execution and qualification.

## Verification and detached closeout

The 65 new preflight tests check actual saved metadata/event records, all twelve
row gates, source/physical links, observer/variant controls, corruption with
recalculated digests, missing/linked files, altered capsules, offline imports
and timeout failure handling. They pass in **16.47 seconds**. These are evidence
and adapter tests, not the full numerical audit verdict.

The [job driver](../validation/betse/full_loop_audit_job.py) registers and captures
the 58 frozen pilot sources plus four audit/test files, then runs two detached
stages: the independent numerical audit and **165 focused regression tests**
(the D075 100 plus these 65). It does not run the older full adapter suite or the
4190-test production matrix. A final `completion.json` may qualify the narrow
pilot only if the audit, full focused test coverage, preservation and resource
gates all pass. Any error retains `failure.json`, partial receipts and logs;
there is no automatic retry or expanded simulation.

Limits: CPUs 0–3, single-threaded numerical libraries in the test process,
**90 seconds per stage**, **210 seconds overall**, and **64 MiB retained job
artifacts**. Stage timeouts are enforced on subprocesses; the overall elapsed
and output-size gates are checked between stages and at closeout. The output
limit is not a filesystem quota or a bound on pytest scratch copies. The audit
reads the existing roughly 47 MiB pilot packet; it does not copy it into its
retained output.

Session: `runs/ref-003e0-loop-audit-2026-09-12/audit-01`. Return control immediately
after detached launch under [AGENTS.md](../AGENTS.md); the user requests status.
No automated polling, new simulation, active intervention, biology, GPU or
stable-release promotion follows. After successful closeout and user review,
decide whether to register the expanded bridge.
