# E02 A2: amended reference acceptance and remaining controls

D036 / 2026-09-09. The user approved adoption of the amended reference policy,
recording the disputed case's observers, and completing the three remaining
controls. This is a new, explicit decision informed by the already observed
[A1 diagnostic](../reports/NUM005C1_A1_BDF_REFINEMENT.md), not a retrospective
claim that the original failed experiment passed.

## Acceptance policy

The [machine-readable amendment](../configs/reference/e02_reference_policy_a2.json)
leaves equations, prepared anchors, zero assay histories, context, topology,
1000-unit duration, maximum step, checked Jacobian, dense-domain/accounting checks,
all eight error targets, observer semantics and resource caps unchanged.

Ten original qualified cases retain their audited trios and settings. For
`M_to_E/mirna_only`, adopt the two original Radau paths and the audited tighter
BDF path. Reuse the pinned A1 comparison: its four-input union grid includes
every accepted endpoint/midpoint and original observer, and its three required
pairs satisfy the unchanged 0.1 limit. Retain the other three pairs, the original
failed BDF path and the original unqualified receipt as diagnostic evidence.
No new integration or duplicate comparison is needed for this case.

Use the selected three references for its 1007 observer samples, retaining full
states, derived diagnostics, uncertainty-aware labels and 102 terminal samples.
Exclude the rejected original BDF from the accepted-reference uncertainty envelope;
its four-input comparison and rejection remain explicitly linked. A1 itself
continues to be labelled diagnostic-only. Only this A2 decision accepts the case.

Before seeing their results, register `M_to_E/same_state`, `one_neighbor`, then
`isolated`. For each, run Radau at base tolerances, refined Radau at 0.1 times
both tolerances, then BDF at 0.1 times both tolerances. The base values remain
rtol 1e-10 and atol 1e-11; the tighter values are binary64 products, nominally
1e-11 and 1e-12. Maximum step stays 0.1. All three pairs must pass all eight
quantity targets on their full union grid. Failure stops; no retry, alternate
tolerance, case substitution or phenotype-based selection is allowed.

The resulting panel is explicitly mixed-setting, accuracy-qualified evidence:
ten original trios plus four A2 trios using tighter BDF. It is not a uniform
solver-settings study or an estimate of BDF failure frequency. Fourteen cases
with observers and independent audits close NUM-005c1 under A2, not the failed
original campaign, NUM-005c2, a biological validation or production graph support.

## Engineering and budgets

Explicit maps separate immutable trajectory ownership from new comparison and
observer output. No copies, symlinks, global solver-method overrides or mutation
of earlier source capsules. Reuse the pinned solver/recorder, read-only trajectory
reader and numerical score definitions. The new three-input comparison and
observer adapters have explicit reader lifetimes; observer arithmetic is extracted
unchanged from the frozen original and tested bit-exact on short fixtures.

One CPU float64 scientific session, one worker at a time, affinity 0–3,
single-thread libraries. Nine planned paths, 900 seconds/path, 3600 seconds total
including adopted observers, comparisons and closeout, one million accepted
steps and two million RHS calls/path, 256 MiB working-array estimate, 256-step/
sample windows and the original 4 MiB metadata reserve. No GPU, new dependencies,
native long driver, RK4 trial or production change is authorized.

All three previous long-reference roots occupy 582,424,320 bytes. They and the
new output share the original 1 GiB cap, leaving 491,317,504 bytes for the new
root. It lives under `runs/num-005c1-a2-2026-09-09/` to preserve previous closed
parents' strict inventories, not to reset the quota. Unexpected siblings, linked
or special artifacts and changed prior byte totals are refused. Registration
archives the prior 35 sources plus this amendment, guide, panel adapter, runner,
auditor and tests (41 files). Existing outputs cannot be overwritten or resumed.

Before integration, hash-check all pinned closeout/audit receipts, old payloads,
prepared packets, original sources, runtime and production identity. Store an
explicit per-case source/method/comparison/observer manifest. Record each attempt
before launching it; workers require a live session and matching start ledger.
Keep any partial or failed output and stop without extending the session.

## Verification scope

Short tests cover selection/ordering, exact inputs, source and artifact tampering,
aggregate accounting, refusal and stopping, multi-root reader cleanup, and
original/new observer-array equality. No fixture runs a 1000-unit scientific path.

The separate read-only audit has its own unchanged 3600-second cap. Reuse pinned
prior audits; independently check every newly completed dense trajectory, even
in a stopped session. Rebuild each new comparison union grid, match every saved
state to its source and recompute primary/history normalized scores. Check all
new observer states against selected sources, independently reproduce labels,
binding caches, coverage, first-hit/return summaries and drift summaries. Derived
flux/gate/voltage comparison scores and RHS values remain online-recorded, not
independent RHS recomputations. Recheck identities after auditing.

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/complete_graph_reference_panel.py --output runs/num-005c1-a2-2026-09-09/panel-01
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/audit_graph_reference_panel.py runs/num-005c1-a2-2026-09-09/panel-01
```

Test/audit time is separate verification work, never additional integration after
a scientific stop. The fixed-step candidate work and bounded-storage preflight
in [the numerical plan](E02_SWITCHING_NUMERICS.md) remain the next gate.
