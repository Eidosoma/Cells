<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Single-molecule exchange heat equals the change in assembly log weight

For entry between two nonempty compositions, the logarithm of the entry rate divided by the reverse exit rate at arrival equals the change in the assembly’s log weight. Reversing the event reverses the heat. At extinction the engine assigns the empty state log weight zero, so the last molecule of type i books −ln θᵢ.

## Assumptions

- The uncatalyzed assembly exchanges one molecule at a time with positive activities and rate constants. For N > 0 the composition weight is (N−1)! times the product of θᵢ^(nᵢ)/nᵢ! over all species, where θᵢ = Kᵢρᵢ.
- The empty state has zero entry propensity. Its terminal booking uses the change in log weight. The theorem concerns individual transfers in exact arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ReservoirExchange.join_heat](../CellsProofs/Chemistry/ReservoirExchange.lean#L123)
- [CellsProofs.Chemistry.ReservoirExchange.leave_heat](../CellsProofs/Chemistry/ReservoirExchange.lean#L138)
- [CellsProofs.Chemistry.ReservoirExchange.extinction_heat](../CellsProofs/Chemistry/ReservoirExchange.lean#L146)

Direct proof subject `cells.exchange.reservoir_exchange@1`

Uses [Molecule entry scales with reservoir activity and assembly size, and exit with species count](assembly-reservoir-exit.md)

## Numerical comparison

**Checked.** Across 357 reversible pairs the largest difference from the independent log-weight change was 4.53 × 10⁻¹⁶ kBT. Two seeded lineages exercised three divisions and a terminal exit. Their saved log weight, heat, fission work and discarded free energy agreed with the independent calculation within 1.78 × 10⁻¹⁵ kBT.

**Engine** `cells.assembly_lineages@1`, `cells.reservoir_exchange@1`

**Operators** `cells.size_threshold_fission@1`, `cells.daughter_continuation@1`

[Uncatalyzed entry and exit rates](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/exchange.py#L108) · [Transfer constants and held activities](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/model.py#L47) · [Event booking and the reverse rate](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/kernel.py#L299) · [Log weight and empty-state convention](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/ledger.py#L83) · [Compiled rates by composition](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/validation/assembly_lineages/probes.py#L210) · [Independent scalar event replay](https://github.com/Eidosoma/Cells/blob/6c648d846fa5c92644986fd967dd403757234b26/src/cells/models/assembly_lineages/reference.py#L46) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/713ef3b4bedb2c1f184d46d968262af92f115e3b/lean/checks/reservoir_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/713ef3b4bedb2c1f184d46d968262af92f115e3b/lean/PROGRESS.md#19-november-2026--assembly-reservoir-exchange)

[Tested engine 6c648d846fa5](https://github.com/Eidosoma/Cells/commit/6c648d846fa5c92644986fd967dd403757234b26) · [Evidence checkpoint 713ef3b4bedb](https://github.com/Eidosoma/Cells/commit/713ef3b4bedb2c1f184d46d968262af92f115e3b)

## Biological evidence

**Open.** Single-molecule entry and reverse exit rates at known neighboring compositions, with an independent transfer free-energy difference under the same conditions.

**Unit** kBT

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
