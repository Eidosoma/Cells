# NUM-005b: independent preparation qualification

2026-09-08. **The two independent 500-unit preparations pass numerical and
preparation qualification.** Cells production remains **0.10.0**. This supplies
full, hash-pinned reference anchors for NUM-005c; it does not qualify connected
1000-unit trajectories, choose a production RK4 step, implement the production
graph, or establish biological switching or equilibrium.

The [bounded reference guide](../docs/SOURCE_PREPARATION_REFERENCE.md) describes
the implementation and limits. The frozen SPEC-004 protocol, inputs and numerical
budgets, NUM-005a equations/native witnesses, existing pair reference and all
39 production source files remain unchanged. No new dependency, native long-time
campaign, continuing-agent experiment, fluid solver or GPU execution was added.

## Registered execution and independent audit

The [registration](../runs/num-005b-2026-09-08/preparation-01/registration.json)
precedes all six trajectories and archives 20 source/config/test/runtime files.
Each fresh E/M seed was independently evolved by Radau, BDF and refined Radau
to exactly 500 nominal units. All six attempts passed at their original settings;
there was no scientific retry, parameter/tolerance amendment or duration extension.

The [qualification](../runs/num-005b-2026-09-08/preparation-01/qualification.json)
and [campaign receipt](../runs/num-005b-2026-09-08/preparation-01/verification.json)
retain 32,372 accepted steps in 129 bounded trajectory chunks and 190,163
trajectory RHS calls including Jacobian construction/checking. The full campaign
took 245.17 seconds; individual trajectories took 23.53–35.37 seconds. CPU affinity
was 0–3, with one worker and one numerical-library thread. Python 3.13.5,
NumPy 2.5.3 and SciPy 1.18.1 match the recorded runtime.

Comparisons cover 32,596 E and 33,144 M times, merging all three accepted grids,
their midpoints and fixed observations. All three method pairs are checked at
every merged time. The 65,740 total comparison times occupy 258 bounded chunks;
these are numerical checks, not independent biological replicates. Full primary
state, ionic/regulatory histories, voltage, membrane fluxes and binding caches
are checked; no-edge junction/scale arrays are correctly empty, not evidence of
a connected-path pass.

| Check | E | M | Required |
| --- | ---: | ---: | ---: |
| Worst normalized reference disagreement | 0.003919634 | 0.003393756 | <= 0.1 |
| Minimum signed phenotype margin after allowance, 400–500 | 78.044380 | 59.806410 | >= 10 |
| Integer observations in qualification window | 101 | 101 | 101 |

The disagreement is normalized by the original candidate error budgets; reference
agreement must occupy at most one tenth of those budgets. The E worst score is
ionic history; the M worst score is regulatory history. The largest independently
audited reconstruction residual is `4.8405723873656825e-14`, below `2e-9`.
Every dense primary/electrical/residual polynomial and accepted state passes the
domain/accounting checks. Minimum regulatory concentration is zero, without
clipping. The maximum absolute voltage across these paths is approximately
0.031183 V, below 0.2 V; no claim of rigorous interval certification is made.

The separate [artifact audit](num-005b-audit.json) verifies all 421 payload hashes,
20 archived/live sources, exact chunk clocks/carries, complete endpoint identity,
ledger reconstruction, full-interval domain bounds, preparation margins and
independently reconstructed observation/endpoint binding caches. Its code imports
neither the simulator nor the reference RHS. Prepared packet identity refers to
the completed qualification receipt, not merely a successful solver endpoint.

The working-array estimate per integration is 876,928 bytes. The retained campaign
directory is approximately 44.3 MiB, below the 1 GiB artifact budget. These are
array/output measurements, not total process-RSS or GPU-performance claims.

## Full reference anchors and remaining drift

The [prepared packets](../runs/num-005b-2026-09-08/preparation-01/prepared-packets.json)
retain complete refined endpoints, original anchors, fixed context, all typed
histories, derived packets, phase clocks and parent hashes. Values below are
rounded for reading; subsequent work must use the full stored arrays.

| Primary coordinate | E at 500 | M at 500 |
| --- | ---: | ---: |
| Na | 6.128524509 | 6.128524509 |
| K | 129.621865345 | 129.621865345 |
| Cl | 55.755147836 | 55.755147836 |
| u, source miR200 total | 83.996200265 | 8.817966183 |
| m, source Zeb mRNA total | 5.951805843 | 68.624390286 |
| z, source ZEB protein | 0.410054857 | 62.721311560 |

Fixed context is `P=80`, `Snail=72`, `ST=0`; endpoint voltage is approximately
-0.015302463 V. The regulatory anchor separations after numerical allowances are
75.178219, 62.672571 and 62.311244, each above the required 1.

**Stable sampled phenotype is not full-state equilibrium.** From 400 to 500,
both preparations still change by approximately Na -0.132789, K +0.372426 and
Cl +0.239495 in their source concentration coordinates; voltage changes by
+0.000455553 V. Regulatory drift is much smaller, and all nonzero endpoint RHS
values and peak-to-peak ranges remain in the receipt. No equilibration-root
substitution or silent extension beyond 500 was used.

Future assay worlds copy these exact prepared primary/context arrays with new
zero assay ledgers and explicit preparation provenance. The original preparation
histories remain retained; importing a prepared state is not an ordinary restart.
The reference runner's complete boundary snapshots do not claim serialization of
private adaptive-solver caches or exact Radau/BDF restart.

## Engineering verification and handoff

All **39 new infrastructure tests pass**, including short all-method smoke
comparisons, independent Jacobian/boundary stencils, full-interval refusals,
corrupt/incomplete artifacts, strict new-output handling, bounded memory/output
policies and refusal to publish packets after failed criteria/reference agreement.
The one-unit smoke case is labelled engineering-only and contributes no scientific
preparation evidence. The full suite passes **1243 tests in 568.21 seconds**, with
warnings promoted to errors and no failures, errors or skips. The
[JUnit receipt](num-005b-tests.xml) and [closeout](num-005b-closeout.json) retain
that result and the final artifact identities. Ruff lint/format pass across
117 Python files and both environments pass dependency checks. All nine SPEC-004
and 17 NUM-005a payload hashes remain unchanged; local Markdown checks pass.

Next is **NUM-005c**: the 14 frozen 1000-unit conditions, registered RK4 study,
selected/half-step verification, and candidate-owned preparation-to-contact
continuations. No connected condition has been run or classified here. NUM-005,
M1 and M1c remain in progress; MODEL-006/VERIFY-011 and ASSAY-002 remain behind
the full numerical gate.

## Retained identities

| Artifact | SHA-256 |
| --- | --- |
| Registration | `a9909f649a68bb57cd076f4ff81389ed7b8cc432a91e10dc841c4857a611d8db` |
| 20-file source capsule | `ebd2d97680c2603d58dbc25ed1143e10acdc777614655d3de445a9ed3025fab2` |
| Qualification receipt | `f4fa3adc83ae550c21354c9de6da1e556c07076cc65921c54b805159a780b641` |
| Prepared packets | `a7eee3207205b799717523c14c0d4436d8935d4766f3b976474856ab90458e6b` |
| Campaign verification | `cf2570b6a8720bdb864113a2075d748d883a78a7a69783acab91d060c2360d63` |
| Independent artifact audit | `799afa9652c99bc73dff72218971d4968519b521432c37f5846b2683ac0138df` |
| Full-suite JUnit receipt | `f4bb5cacebcb967f875eebe10545d578134312569d22022b83b177080d71a9d4` |
