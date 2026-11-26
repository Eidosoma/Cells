<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Pair-consistent catalysis preserves the heat of a reversible transfer

A molecule entering an assembly sees the same catalytic multiplier as its reverse exit when the moving molecule is excluded from both catalyst counts. The log ratio of the two rates then equals the base exchange log-weight change. A singleton’s exit has multiplier one.

## Assumptions

- The species set is finite. The counts are nonnegative integers and the catalytic matrix β has nonnegative entries. The assembly exchanges one molecule at a time, with positive rate and transfer constants and fixed positive reservoir activities.
- The reversible transfer connects two nonempty compositions. The singleton’s exit into the empty state is a separate boundary case. Lean evaluates the sums in exact arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.GardCatalysis.weighted_addOne](../CellsProofs/Chemistry/GardCatalysis.lean#L25)
- [CellsProofs.Chemistry.GardCatalysis.factor_pos](../CellsProofs/Chemistry/GardCatalysis.lean#L31)
- [CellsProofs.Chemistry.GardCatalysis.pair_reverse_factor](../CellsProofs/Chemistry/GardCatalysis.lean#L39)
- [CellsProofs.Chemistry.GardCatalysis.singleton_factors](../CellsProofs/Chemistry/GardCatalysis.lean#L48)
- [CellsProofs.Chemistry.GardCatalysis.pair_heat](../CellsProofs/Chemistry/GardCatalysis.lean#L64)

Direct proof subject `cells.rate_factor.gard_catalysis_pair_consistent@1`

Uses [Single-molecule exchange heat equals the change in assembly log weight](assembly-exchange-heat.md)

## Numerical comparison

**Failed.** The 210 ordinary transfer pairs agreed with the base heat within 5.00 × 10⁻¹⁶ kBT. Two admitted one-event runs with a large diagonal coefficient lost the remaining catalyst in the reverse sum. The passive ledger refused both, booking 2.33 × 10⁻¹⁰ and 0.693147 kBT where the exact heat is zero. Both one-event controls passed. The failure is recorded for version 1. An in-place change altered registered results and was reverted. The lead assigned the accurate reverse calculation to version 2. [Version decision](../../docs/DECISIONS.md#L8017) · [Branch replay](../PROGRESS.md#remaining-numerical-findings)

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@1`, `cells.gard_catalysis_single_event@1`

**Operators** `cells.size_threshold_fission@1`, `cells.daughter_continuation@1`

[Reverse pair factor](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/models/assembly_lineages/gard.py#L143) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/gard_catalysis.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#six-numerical-retests)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`, `cells.gard_catalysis_pair_consistent@1`, `cells.gard_catalysis_single_event@1`

**Operators** `cells.size_threshold_fission@1`, `cells.daughter_continuation@1`

[Single-event factor](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/gard.py#L137) · [Pair-consistent reverse and terminal factors](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/gard.py#L143) · [Event heat using reverse rates at arrival](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/kernel.py#L299) · [Passive ledger refusal](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/src/cells/models/assembly_lineages/runner.py#L894) · [Compiled rate probe](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/assembly_lineages/probes.py#L210) · [Independent rational propensities](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/gard/references/kernels.py#L279) · [Rate products around a square](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/gard/references/detailed_balance.py#L132) · [Rank-one condition in the finite-reservoir reference](https://github.com/Eidosoma/Cells/blob/f7767ad79edf2f972b78999e64b40f0c294bcf88/validation/gard/references/closed_world.py#L202) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/f382628833be3f23b53cd95ac0a52ec15a76e6ca/lean/checks/gard_catalysis.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/f382628833be3f23b53cd95ac0a52ec15a76e6ca/lean/PROGRESS.md#19-november-2026--gard-catalysis-on-reversible-transfers)

[Tested engine f7767ad79edf](https://github.com/Eidosoma/Cells/commit/f7767ad79edf2f972b78999e64b40f0c294bcf88) · [Evidence checkpoint f382628833be](https://github.com/Eidosoma/Cells/commit/f382628833be3f23b53cd95ac0a52ec15a76e6ca)

## Biological evidence

**Open.** Entry, reverse exit and independent affinity for the same lipid as the surrounding membrane composition changes.

For the same lipid tracer at 308 K, changing pure POPC vesicles to 1:1 POPC/cholesterol halved the fitted entry constant. Exit estimates were 25 ± 2 and 27 ± 2 s⁻¹. Independent titrations gave association constants of 1.3 × 10⁹ and 6.1 × 10⁸ M⁻¹. A shared catalytic multiplier at fixed affinity cannot explain the change. The fit used the equilibrium measurement, and molecular neighbor counts remain unknown. [Sampaio et al., Table 1](https://doi.org/10.1529/biophysj.104.054007)

**Unit** M⁻¹ s⁻¹ per molar vesicles for entry, s⁻¹ for exit

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
