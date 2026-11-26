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

Direct proof subject `cells.operator.population_unit_turnover@1`

Uses [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md)

## Numerical comparison

**Checked.** An eight-step checked world used two precursor molecules per direct unit and seven per three-stage unit. All observed precursor, transit, insertion, surface and sink amounts matched the independent matrix exponential within 4.55 × 10⁻¹³ units and 4.24 × 10⁻²² fmol. In a compiled two-stage pulse, 10.82448 of the initial 120 units reached the membrane in 12.5 ms. Two declared populations reproduce each of the two published fast/slow receptor fits.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.kleak_always_open@1`

**Operators** `cells.population_unit_turnover@1`, `cells.membrane_entity_state@1`

[Molecules per functional unit](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/population_unit_turnover.py#L185) · [Maturation integrals](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/population_unit_turnover.py#L604) · [Precursor, pools, surface and removal bookings](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/population_unit_turnover.py#L636) · [Independent matrix exponential](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/tests/unit/test_population_unit_turnover.py#L60) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/population_units.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#surface-population-turnover)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `cells.kv1p5_mh@1`, `cells.passive_constant_field_permeation@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.population_unit_turnover@1`, `cells.membrane_entity_state@1`

[Kv1.5 activation and inactivation](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/channels/kv1p5_mh.py#L25) · [Clamped population current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Gate advance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/numerics/exponential_gates.py#L44) · [Constant-field ion flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/constant_field_permeation.py#L59) · [Inward rectifier slope](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Native cohort removal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/population_unit_turnover.py#L958) · [Surface population counts](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/membrane_state.py#L152) · [Two-population fixture](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/validation/fr7/unit_turnover_fixtures.py#L68) · [Paired measurements and protocols](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_replay_measurements.json) · [Kv1.5 dose and rectifier data](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Activation curve and step current](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/trapani2003_kv15_ph.json) · [Published receptor component fits](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/membrane_physiology_pairs.json) · [Red-cell chloride measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/freedman1997_chloride.json) · [Planar-bilayer potassium currents](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pfeffermann2026_potassium.json) · [Prepared clamp and pH rows](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/kv15_ph.py) · [Permeability calibration](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/charged_permeation.py) · [Population declaration and binding](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/population_units.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_law_replays.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Open.** Survival of a labelled surface-channel cohort and appearance of newly made receptors in the plasma membrane.

- [A labelled surface acetylcholine-receptor cohort declines over time at an active, innervated adult mouse neuromuscular junction.](../WET_LAB_EVIDENCE.md#pair-innervated-receptor-cohort-loss) · Supported by both studies
- [All labelled junctional acetylcholine receptors in a normally innervated mouse muscle share one first-order loss rate.](../WET_LAB_EVIDENCE.md#pair-innervated-receptor-single-rate) · Challenged by both studies

Independent labelled cohorts decline over time. Two innervated mouse preparations resolved fast and slow receptor populations. A common loss constant across the entire pool would miss that heterogeneity. The precursor and removal inventories remain open.

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

### bruneau2010_active_achr@1

Active adult mouse sternomastoid synapses. Fewer than 20% of AChRs labelled, muscle fibers expressing rapsyn–GFP. Results, pp. 616–617 and Fig. 3D [Bruneau and Akaaboune (2010), Results and Fig. 3D](https://doi.org/10.1523/JNEUROSCI.4595-09.2010)

- **Evidence role** descriptive

Values and times from Results (SD). The figure caption specifies SEM for the plotted bars. Two follow-ups cannot identify the decay law.

The labelled fraction remaining was 93 ± 5% at 24 h and 75 ± 8% at 72 h. These observations constrain the direction of loss in an active synapse. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### strack2011_achr_two_components@1

Labelled AChR in innervated tibialis anterior. The two-component fit is normalized at day 2. The pre-existing claim's Fig. 3D uses a day-7 anchor in the same study. Table 2, innervated adult mouse muscles, fitted components [Strack et al. (2011), Table 2](https://doi.org/10.1371/journal.pone.0020524)

- **Evidence role** descriptive

Table 2 means and SD for ten muscles. These fitted components and the Fig. 3 observations have common provenance.

In innervated muscles, the authors fitted a 13 ± 2% fast component with half-life 1.1 ± 0.3 days and an 87 ± 2% slow component with half-life 13.1 ± 0.4 days. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### stanley1983_achr_turnover@1

Normally innervated mouse diaphragm neuromuscular junctions. Primary report, Science 222, 67–69, abstract with component estimates [Stanley and Drachman (1983), component estimates](https://doi.org/10.1126/science.6623057)

- **Evidence role** descriptive

Published component estimates. The public abstract gives no pointwise time series, errors or sample counts. The inferred subpopulation fractions are approximate.

The authors reported a fast fraction of approximately 20% with an 18.7 h half-life and a slow component with a 12.4 day half-life. Each component is a fit to a subpopulation. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
