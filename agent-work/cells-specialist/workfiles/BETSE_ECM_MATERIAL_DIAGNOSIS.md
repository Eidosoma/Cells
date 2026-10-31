# Retained signed-environment failure and proposed increment ledger

The original39/40 panel remains failed. The retained-data audit reproduces the
single failed comparison, verifies all381 actual/native columns **bitwise**, and
checks all396 actual/reference fields. It finds no comparator, branch, owner
index, order or units error. It executes no simulation, flux law or reference
evaluator, imports no scientific package, and changes no shared/frozen source,
input, budget or failure artifact.

The machine evidence is
[diagnosis02](/mnt/workspaces/Cells/betse-ecm-material-retained-diagnosis-20261031-02/result.json),
[per-owner decomposition](/mnt/workspaces/Cells/betse-ecm-material-retained-diagnosis-20261031-02/per-owner-decomposition.json)
and [material accounting](/mnt/workspaces/Cells/betse-ecm-material-retained-diagnosis-20261031-02/retained-material-accounting.json).
The audited source/array hashes are recorded there. The archive remains
`betse-ecm-failure-capture-20261030-01`; its100/160-digit computations are stored
as separate binary64 projections, and the fresh reference buffers match the
archived reference buffers exactly.

## Why the difference cannot meet its current budget

The worst entry is Cl, `mem-3`, owner `cell-1`. Frame25 commits membrane exchange
and copies bulk concentration into the membrane cache. Frame26 adds the small
junction change only to bulk; frame27 performs no clipping in this case. The
membrane cache remains the pre-junction value, exactly as native source specifies.

| Quantity | mol/m3 |
| --- | ---: |
| Saved membrane value |16693.66666080432 |
| Saved final bulk value |16693.6666590814 |
| Their exact stored difference |1.7229212971869856e-6 |
| Independent carried-state difference |1.7229230420530395e-6 |
| Absolute error |1.7448660538927198e-12 |
| Unchanged difference budget |3.000103375382523e-13 |
| Operand spacing |3.637978807091713e-12 |

Both large operands lie in the same binary64 binade, so any difference of two
such stored values is an integer multiple of that spacing. The actual difference
is already the **nearest possible** lattice value to the reference target. Even
allowing half an ULP for the target's archived projection, the irreducible error
is1.7448660537868407e-12, above the budget. Applying the perfect target increment
to the saved pre-junction bulk also rounds to the same final bulk. The final
subtraction itself is exact; the small update lost digits in the earlier bulk
addition. `fsum`, a wider temporary subtraction, or an algebraic reordering of
that subtraction cannot recover those digits from the unchanged buffers.

The saved reference operands subtract to1.7229249351657927e-6, which differs
from the separately projected high-precision difference. Replacing the target
with subtraction of those rounded operands would change the observable and
still produce an error of one full operand ULP against actual. This is not a
valid comparator repair.

Exact rational recomposition of the saved junction fluxes, supplied areas,
dt and cell volumes gives the requested outward concentration increment
1.7229230420530382e-6 at this owner. Its error against the retained target is
1.1782150171509545e-21, or3.92724806357957e-9 of the unchanged budget. This is
saved-data algebra, not a new flux/reference computation or qualification.
The actual native pre-addition `dg` temporary was not archived, so its precise
rounding error is not claimed.

## Separate physical junction imbalance

This case uses the **slow** ECM branch. Moving membrane exchange balances
exactly in its saved ledgers, and clipping is zero. The fast duplicate-assignment
defect is not active. The entire world has imposed boundary/collocated terms;
its total material change alone is therefore not an isolated conservation test.

The three nontrivial junction pairs have equal paired area, diffusivity and
opening weight but unequal supplied path lengths:0.80/0.86,0.84/0.96 and0.88/0.94m.
Native, Cells and the independent reference evaluate each directed face with its
own path. The saved fluxes multiplied by their respective lengths cancel to
roundoff; the unscaled paired material transfers do not. This explains signed
net outward gap amounts of−4.2559533825480874e-10mol Na,
−6.831475982587278e-10mol K and+7.103573827248926e-10mol Cl. The unequal-path
prediction reproduces each paired amount to about1.5e-24mol or better.

That is a real nonconservative operator for this supplied directed geometry,
reproduced by the reference; it is distinct from the failed small-difference
accuracy condition. The existing source-mode flag already declines physical
material/energy parity. Making a physical conservative junction would require a
caller-declared shared conductance, or compatible reciprocal area×D×opening/path,
then one interface transfer applied with opposite signs. Two conflicting
directed paths do not specify which shared conductance to choose. No path,
weight, flux or amount is silently symmetrized in this proposal.

## Narrow, prospective change for Chief's decision

There is no comparator-only repair that makes the original raw-difference gate
true while preserving these native buffers and budgets. The
[unapplied patch](/home/robert/Cells/agent-work/cells-specialist/workfiles/betse_ecm_requested_increment_PROPOSAL.patch)
instead adds the separately named
`junction_requested_outward_increment_mol_m3`, shaped ion×cell. Actual records
`-(dt*dg)` before the bulk addition; independent reference records the same
owned directed-flux sum at its existing precision. Stationary ions remain zero.
This quantity describes the **requested operator increment**, before rounding
the bulk update and before clipping. It does not redefine the measured final
buffer difference.

Static normalization proves the complete original source AST is unchanged after
removing only the new diagnostic allocation/assignments/keyword. The original
updates, statement order, raw lag, checker, inputs and budgets remain intact.
No patch has been applied. The
[candidate tests](/home/robert/Cells/agent-work/cells-specialist/workfiles/betse_ecm_requested_increment_candidate_tests.py)
are compiled only: they require all original396 state/legacy-ledger columns to
remain byte-identical and compare the new increment against both complete
references using the unchanged concentration budget. Root would also require
a fresh source-denied reference worker. The original canonical accuracy test
remains unchanged and open; no xfail or expected-limitation pass is introduced.

The [machine proposal](/home/robert/Cells/agent-work/cells-specialist/workfiles/betse_ecm_material_repair_test_proposal.json)
records the patch bases, hashes, exact tests and scope decisions required before
any separately authorized execution. Audit02 measured25MiB current-PID VmHWM
under a512MiB address-space/60s CPU cap. Audit01 is preserved; its process-history
`ru_maxrss` was incorrectly labeled as current audit RSS, corrected explicitly
in02 without changing any scientific result.
