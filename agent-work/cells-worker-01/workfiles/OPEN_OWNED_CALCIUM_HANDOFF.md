# Static open-exterior owned calcium and finite fuel

This handoff adds static ideal chemical/voltage reservoirs to the complete56-law
owned calcium and finite-fuel equations. It contains no scheduled bath or epoch
extension. Component numerical qualification is pending with Chief; code and
static checks alone establish no numerical or biological acceptance.

| Model ID | Exact component laws | Saved physical arrays |
| --- | --- | --- |
| `resolved_open_calcium@1` | calcium@11 / ionic@12 | 34 |
| `resolved_open_calcium_energy@1` | calcium_energy@5 / calcium@11 / ionic@12 | 38 |

The original request could not be an ordinary bath wrapper. Existing owned
calcium parsing requires a finite exterior for its conserved-pool bound; its
extra PMCA/NCX/Ca-channel rates also assume finite exterior inventories. Fuel
inherits both restrictions. Chief therefore authorized a separate static open
family and a narrow extraction in the two existing parent spec files.

The private decoders return `_OwnedDeclarations`, not `SimulationSpec`, and
preserve every actual reservoir flag. They retain component/cross-owner, volume,
free-ion, ER, gate, metabolism and schedule validation. Original public parsers
still perform the same closed-exterior checks and complete closed admission.
Mechanically reversing the extraction reproduces both original parse ASTs
exactly, and all other existing helpers/classes are AST-identical. Baselines and
retention evidence are linked by `open_owned_calcium_workqueue.json`.

The new schemas have the original full physical declarations plus three fields:
`exterior_policy`, `ionic_moiety_domain_policy`, and
`ionic_moiety_ceiling_fmol`. Static reservoirs are still declared explicitly by
the real exterior owners' `reservoir` and `boundary_potential_V` fields. No
execution capacity, state owner, reference amount, background charge, chemical
table or geometry is invented or replaced for parsing.

The complete parent computes actual passive, all56 shared channel laws,
junction gates, Na/K, PMCA, NCX, owned calcium channels, ER chemistry/transport
and fuel/regeneration rates. Only the external closure changes. If a held
exterior slot's unmaintained full rate is `r_out`, the added external supply is
`b=-r_out`; the held amount rate becomes zero and total reservoir supply becomes
`S_parent+b`. Finite outside and every intracellular/chemical/gate/pump/fuel
derivative remain actual. Supply is positive into the accounted system.

Electrode current is recomputed from complete corrected ionic charge rates and
the existing capacitor solve. With fixed boundary voltage `phi`, the complete
external powers are `1e-3*sum((RT*log(C)+zF*phi)*S)` and
`1e12*phi*I_electrode` in pJ/s. Chemical power removes the fictitious held-node
accumulation in the finite-exterior component rate. Reservoir material,
electrode charge, reservoir/electrode work and all original histories are saved
normally; no history is reconstructed or reset. Original parent domain,
material, capacitor/global charge, ER ownership and work diagnostics remain.

Maintained-fuel calcium retains the three declared pump-work owners as external
input. Finite fuel uses actual current ATP/ADP/Pi in all three pump families;
pump-work ledgers remain internal transfers, while pool free energy and the
declared regeneration supply complete the balance. The bound-only A/P majorant
never enters a physical readout or RHS. The finite parent's thermodynamic
readout field is `raw.energy`; the initial draft's incorrect `raw.pools` access
was corrected before handoff, as recorded in Chief's targeted review.

Open ionic moiety amounts can change with reservoir supply. Their configured
ceilings are positive finite **fmol domain limits checked at every stage**.
They are not conserved quantities, concentration floors or trajectory clamps.
The measured quantity includes all free/bound cytosolic and ER ions plus every
exterior control-volume inventory. Exceeding a ceiling rejects a stage. True
nonionic chemical moieties and neutral fuel adenylate/phosphorus remain
conserved. ER reaction-loss majorants use those true nonionic totals plus the
declared ionic ceilings. Existing plasma/ER and full catalog kinetic ceilings
remain; chemistry, plasma and passive-background coefficients are summed at
the unchanged0.25 threshold. Finite initial gross fuel turnover retains the
unchanged0.05 limit. Strict transport positivity/voltage/affinity predicates
remain at every stage; no unconditional RK4 positivity theorem is claimed.

With no ideal reservoirs, ceilings must be JSON `null`. The new family delegates
the original admitted parser and step/definition checks and selects the raw
original full field/RHS results exactly, preserving their arithmetic order.
Regression cases compare canonical definitions, complete initial layouts/states,
all full derivative arrays, two separately evolved steps and every original
physical observation. Additional open-domain readouts are compared separately.
Old IDs continue rejecting real reservoir inputs.

The independent reference uses actual reservoir flags, the qualified full-node
and scalar56-law/ER/PMCA/NCX/Ca-channel equations, explicit per-route bath supply,
and independently assembled electrode/work closure. Finite fuel is rebound to
actual current pools. It implements80-digit original molecular/plasma/ER/pool
energy, chemical/ionic ownership, neutral pool/material balances, static work
identities, independent padded-array checks and a scalar loss-bound derivation.
Global ionic budgets use increments directly, avoiding bulk-inventory
subtraction. Full control-stage, corruption, positivity, ceiling, live-fuel and
closed-reduction cases retain the existing numerical tolerances.

Chief owns shared routing, public fixtures/tests, PROGRESS and numerical
qualification. Its ten public checks passed on an isolated snapshot, including
fresh snapshots and actual2ns eager restart. The separate targeted source review
is `/mnt/workspaces/Cells/open-calcium-public-integration-20261029-01/code-review-01/REVIEW.json`;
it records the local readout rename and summary-only drift after that public
snapshot. Those public results do not establish full8us trajectory accuracy,
timestep refinement, compiled CPU/GPU performance, native parity or biology.
The first Root component snapshot passed82 cases and failed only the dependency
audit's overly restrictive handling of `tests/__init__.py`. That initializer
contains documentation only. The corrected audit hashes it, refuses any
executable initializer body, and includes three new production-import refusal
cases. Its failed evidence is retained under `components-06`. Independent
`evaluate` also now rejects nonpositive physical inventories before logarithms;
rate, conservation and bound function ASTs are unchanged. Chief will supersede
that snapshot with a fresh86-case component run; no pass is double-counted.

The worker launched and polled no numerical job and left all frozen/active
ordinary bath, epoch and earlier qualifications untouched.
