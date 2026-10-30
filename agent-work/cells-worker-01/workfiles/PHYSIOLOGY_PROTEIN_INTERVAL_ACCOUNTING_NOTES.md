# Held-protein interval accounting

Worker ownership: new core, independent reference and unit files only. Chief owns
charged stepping, cursor, checkpoint/persistence and shared progress. The four
ordinary families are passive, expanded ionic, owned calcium and finite fuel.

`evaluate(spec, before, after, layout, binding, charge_reference, component,
*, protein_species_id, valence, before_control, after_control)` returns immutable
`IntervalAccounting(valid, balances, limits, energy_terms, diagnostics, checks)`.
Invalid admission raises `IntervalAccountingRejected` retaining the report and
both complete numeric endpoints. The same operation supports a single interval
and original-seed-to-current cumulative history at the same held protein/P.

For each physical ideal chemical owner, with fixed original anchor a, original
increments b and e, N=a+b and d=e-b, compute

    DeltaG = 1e-3 R T [d (mu0/RT + log(N/(V c0))) + N h(d/N)]
    h(r) = (1+r) log(1+r) - r.

Amounts are fmol, volume pL, concentration mM, and energies pJ. Decimal input
arithmetic preserves the separate anchor and increments; small-r series preserve
the linear and quadratic terms even below the bulk stock ULP. No bulk free
energies are subtracted. Complete store chemistry replaces intracellular ionic
chemical energy in calcium/fuel; the ionic exchange ledger is not a second
cytosolic inventory. ATP standards use the declared transformed deltaG0 once.

The plasma capacitor interval uses the original charge-only linear solution on
the difference of ionic increments and the actual charged starting voltage:

    DeltaU = 0.5e12 sum C deltaVm (2 Vm_before + deltaVm).

Actual charged endpoint voltage differences and the raw discrepancy from this
ledger-derived increment remain separate diagnostics. Endpoint field/current
closure tolerances are unchanged. ER capacitors use their original store charge
anchor and the same product identity. No energy anchor is reset.

The combined raw energy residual is chemical + plasma/ER capacitor change +
all declared dissipated-history increments - reservoir/electrode work - fixed
metabolic drive work. For finite fuel, add ATP/ADP/Pi chemical change and
regeneration heat, subtract regeneration supply, and count pump work only as
internal pool exchange. Each pool keeps its own internal transfer balance.
Protein chemical energy is constant during this held interval. No cost of the
prior protein redistribution, noise work or holding protocol is inferred.

All original non-overall-energy endpoint checks remain: material, charge,
electrode/global charge, chemical reaction/transfer ledgers, ownership, reservoir
and electrode work, fixed-drive identities, fuel material/invariants, pool
internal energy and regeneration work. Stable cumulative pool changes replace
rounded bulk formulas. Check both endpoints and interval residuals. Keep domain,
padding/support, actual charged field/rate checks and pairwise nondecreasing heat.
Collect raw failures rather than relying on validators that stop at old energy.

Chief authorized bounded CPU7 qualification after the initial coding assignment:
one thread, 480 seconds per phase, 1 GiB process-tree RSS, 8 GiB host reserve,
private captured source under /mnt/workspaces/Cells, no GPU/compiler cache. Any
failed evidence remains; no automatic follow-up campaign is launched.
