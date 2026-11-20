<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Precursor molecules balance across maturation, surface insertion and removal

Routes on the same precursor and cell share first-order consumption. Weighting each route's functional units by its precursor stoichiometry accounts for molecules in transit, on the surface and in the removal ledger. A two-stage maturation pulse and a surface cohort undergoing first-order loss have explicit time courses.

## Assumptions

- Rates are constant over each interval. Each route has a positive number of precursor molecules per functional unit. Unit amounts evolve continuously. The material identity admits any finite number of sequential maturation pools, including direct insertion.
- The pulse starts entirely in the first of two identical stages with no new input or surface removal. The cohort survival comparison tracks labelled surface units with no new labelled insertions.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PopulationUnits.shared_consumption](../CellsProofs/Chemistry/PopulationUnits.lean#L21)
- [CellsProofs.Chemistry.PopulationUnits.pool_balance](../CellsProofs/Chemistry/PopulationUnits.lean#L34)
- [CellsProofs.Chemistry.PopulationUnits.precursor_to_sink](../CellsProofs/Chemistry/PopulationUnits.lean#L45)
- [CellsProofs.Chemistry.PopulationUnits.mixed_stoichiometry](../CellsProofs/Chemistry/PopulationUnits.lean#L60)
- [CellsProofs.Chemistry.PopulationUnits.cohort_survival](../CellsProofs/Chemistry/PopulationUnits.lean#L69)
- [CellsProofs.Chemistry.PopulationUnits.pulse_at_zero](../CellsProofs/Chemistry/PopulationUnits.lean#L80)
- [CellsProofs.Chemistry.PopulationUnits.pulse_derivatives](../CellsProofs/Chemistry/PopulationUnits.lean#L85)
- [CellsProofs.Chemistry.PopulationUnits.positive_arrival](../CellsProofs/Chemistry/PopulationUnits.lean#L109)

Direct proof subject `cells.population_unit_turnover@1`

Uses [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md)

## Numerical comparison

**Checked.** An eight-step checked world used two precursor molecules per direct unit and seven per three-stage unit. All observed precursor, transit, insertion, surface and sink amounts matched the independent matrix exponential within 4.55 × 10⁻¹³ units and 4.24 × 10⁻²² fmol. In a compiled two-stage pulse, 10.82448 of the initial 120 units reached the membrane in 12.5 ms.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.population_unit_turnover@1`, `cells.membrane_entity_state@1`

[Molecules per functional unit](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/population_unit_turnover.py#L185) · [Maturation integrals](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/population_unit_turnover.py#L604) · [Precursor, pools, surface and removal bookings](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/population_unit_turnover.py#L636) · [Independent matrix exponential](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/tests/unit/test_population_unit_turnover.py#L60) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/population_units.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#surface-population-turnover)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

## Biological evidence

**Open.** Survival of a labelled surface-channel cohort and appearance of newly made receptors in the plasma membrane.

**Unit** % of labelled baseline and hours to surface appearance

### strack2011_innervated_cohort@1

Ten innervated mouse hindlimbs were followed with the other leg denervated. Residual receptor-associated label is a proxy for survival. The day-7 normalization favors the slower component. Filled circles in Figure 3D, anchored to day 7. Elapsed times and percent retention were read from the point centers and caps. [Strack et al. (2011), Fig. 3D](https://doi.org/10.1371/journal.pone.0020524)

- **Evidence role** held out from fitting
- **Fit** Anchor and seven elapsed days (100% and approximately 67%)
- **Evaluation** 14 elapsed days, 16 elapsed days, 18 elapsed days

Readings are approximate. The caption specifies SD and the methods specify SEM. Repeated measures share the animals and baseline.

A single rate of 0.05721/day predicted 44.89%, 40.04% and 35.71% retention against 48%, 43% and 42%. The first two predictions fall inside the plotted bars. The last lies below the observed 39–46% bar. [Dataset manifest](../checks/data/surface_population_measurements.json) · [Comparison verdict](../PROGRESS.md#surface-population-turnover)

### devreotes1977_surface_arrival@1

Newly synthesized acetylcholine receptors were followed to the plasma membrane in cultured chick skeletal muscle. Abstract observations over the first 3 and 3.5 hours. [Devreotes et al. (1977), p. 365](https://doi.org/10.1016/0092-8674(77)90023-X)

- **Evidence role** descriptive

The observations describe relative labelling of receptors arriving at the membrane. The report gives no numerical fraction or error for the 3.5-hour observation.

Few labelled receptors reached the surface during the first three hours. By 3.5 hours virtually all receptors entering the membrane carried label. This supports a lag in appearance and leaves the pool count and transit-time distribution open. [Dataset manifest](../checks/data/surface_population_measurements.json) · [Comparison verdict](../PROGRESS.md#surface-population-turnover)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
