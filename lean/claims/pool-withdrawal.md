<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Partial pool withdrawal conserves counts and fixes their conditional moments

For a well-mixed pool place, the molecules left in the pool plus those withdrawn equal the original count plus the supplied buffer after the wash. For n original molecules sampled independently with probability q, the withdrawn mean is nq, its variance is nq(1−q), and the final pool has mean n(1−q)+buffer with the same variance.

## Assumptions

- Initial and supplied counts are nonnegative integers and their sum fits the place capacity. The count balance holds for every per-molecule assignment.
- The moment calculation averages independent, equiprobable word indices for the molecules. The actual stream uses the midpoints of M = 2^52 bins and withdraws when the midpoint is strictly less than f. PRNG independence is a modeling assumption.
- The effective probability q equals ceil(Mf−1/2)/M for 0 ≤ f ≤ 1. The error is bounded by 2⁻⁵³, including at midpoint ties. For transfer at the measured liquid fraction, the tracer must sample that liquid uniformly.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.PoolWithdrawal.inventory](../CellsProofs/Chemistry/PoolWithdrawal.lean#L11)
- [CellsProofs.Chemistry.PoolWithdrawal.accepted_words](../CellsProofs/Chemistry/PoolWithdrawal.lean#L28)
- [CellsProofs.Chemistry.PoolWithdrawal.probability_error](../CellsProofs/Chemistry/PoolWithdrawal.lean#L41)
- [CellsProofs.Chemistry.PoolWithdrawal.probability_on_grid](../CellsProofs/Chemistry/PoolWithdrawal.lean#L60)
- [CellsProofs.Chemistry.PoolWithdrawal.first_midpoint_stays](../CellsProofs/Chemistry/PoolWithdrawal.lean#L74)
- [CellsProofs.Chemistry.PoolWithdrawal.word_average_eq_trials](../CellsProofs/Chemistry/PoolWithdrawal.lean#L88)
- [CellsProofs.Chemistry.PoolWithdrawal.withdrawn_moments](../CellsProofs/Chemistry/PoolWithdrawal.lean#L107)
- [CellsProofs.Chemistry.PoolWithdrawal.pool_moments](../CellsProofs/Chemistry/PoolWithdrawal.lean#L116)

Direct proof subject `cells.operator.pool_withdrawal@1`

Proof sources [Mathlib natural ceiling and strict comparison, imported in the grid count](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/Floor/Defs.lean#L109-L129) · [Mathlib ceiling bounds, specialized for midpoint probabilities](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/Floor/Semiring.lean#L342) · [Finite Bernoulli count moments reused from lineage fission](../CellsProofs/Chemistry/LineageFission.lean#L90-L119) · [Withdrawal rule and the finite uniform convention](../../docs/ASSEMBLY_WITHDRAWAL_DESIGN.md#L42-L52)

Uses [Size-triggered fission conserves each species under fixed-quota and independent partitions](size-threshold-fission.md)

## Numerical comparison

**Checked.** All finite places balanced in three complete population runs. With eight molecules, 4,000 seeds per fraction gave means 1.993, 3.991 and 2.6405 at one quarter, one half and one third. Sample variances were 1.479, 1.997 and 1.738. Nine controls at or around word cutoffs matched the exact finite-grid law. At f = 2⁻⁵³ the parser admits the wash and every molecule stays.

**Engine** `cells.assembly_lineages@2`

**Operators** `cells.pool_withdrawal@1`

[Withdrawal parse, capacity guard and strict per-molecule sampling](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/models/assembly_lineages_v2/withdrawal.py#L70-L157) · [Host update, event record and material balance](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/models/assembly_lineages_v2/population.py#L785-L825) · [Power-of-two block and real stream addresses](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/models/assembly_lineages_v2/streams.py#L49-L66) · [Midpoint conversion from random words](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/src/cells/models/assembly_lineages/streams.py#L120-L128) · [Acceptance worlds, seed blocks and independent booking reference](https://github.com/Eidosoma/Cells/blob/4532479c017977c67449995684657066225501d5/tests/unit/test_assembly_lineages_v2_replacement.py#L594-L820) · [Cells count and midpoint proofs](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/CellsProofs/Chemistry/PoolWithdrawal.lean) · [Independent Bernoulli moments](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/CellsProofs/Chemistry/LineageFission.lean) · [Original fixed-count bins and calibration of vector axes](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/checks/data/fornell2017_partition.json) · [Vector marker verification shared with lineage fission](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/checks/lineage_fission.py) · [Remaining vector counts and independent aliquot volume measurements](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/checks/data/pool_withdrawal_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/checks/pool_withdrawal.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/26968045502894393d3e0f72ec3675ca84853dbe/lean/PROGRESS.md#fr35-withdrawal)

[Tested engine 4532479c0179](https://github.com/Eidosoma/Cells/commit/4532479c017977c67449995684657066225501d5) · [Evidence checkpoint 269680455028](https://github.com/Eidosoma/Cells/commit/26968045502894393d3e0f72ec3675ca84853dbe)

**Engine** `cells.assembly_lineages@2`, `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.inward_rectifier_linear_driving_force@1`

**Operators** `cells.pool_withdrawal@1`, `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`, `cells.scheduled_species_exchange@1`

[Bilayer area](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/geometry.py#L249) · [Lumen tension and volume](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/lumen.py#L265) · [Deterministic rupture decision](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/kernel.py#L350) · [Bead-equivalent count withdrawal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/assembly_lineages_v2/withdrawal.py#L150) · [Full wash at a bound wall](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/wash_schedule.py#L472) · [Saturable uptake](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/operators/species_exchange.py#L335) · [Potassium reversal](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L55) · [Paired measurements](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_wet_lab_measurements.json) · [Potassium changes in Müller cells](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/paired_calibration_measurements.json) · [Kir4.1 temperature and concentrations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/tada1998_kir41.json) · [POPC molecular areas](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/leaflet_packing.json) · [First independent deflation study](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fujiwara2014_vesicle.json) · [Survival during a tension hold](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/vesicle_rupture_holds.json) · [First bead-count groups](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/fornell2017_partition.json) · [Remaining bead counts and volume observations](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/data/pool_withdrawal_measurements.json) · [Bilayer area harness](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/leaflet_packing.py) · [Vesicle world](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle.py) · [Retained-osmole comparison](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/vesicle_events.py) · [Whole draw and site stocks](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/wall_wash.py) · [Pool event and count reconstruction](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/pool_withdrawal.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/checks/paired_response_endpoints.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9f27f80116ed324e1adbbef7cddb5671d71f12f7/lean/PROGRESS.md#paired-law-replays)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 9f27f80116ed](https://github.com/Eidosoma/Cells/commit/9f27f80116ed324e1adbbef7cddb5671d71f12f7)

## Biological evidence

**Open.** Fraction of passive tracer beads in a sampled or retained daughter at an independently estimated liquid fraction.

- [On average the retained passive bead fraction equals the actual retained liquid fraction.](../WET_LAB_EVIDENCE.md#pair-withdrawal-liquid-fraction) · Independent replication unconfirmed
- [One passive split can leave beads in both the withdrawn and retained liquid.](../WET_LAB_EVIDENCE.md#pair-withdrawal-both-daughters-occupied) · Supported by both studies

Two separate laboratories observed both daughters retaining particles in a passive split. The two quantitative studies share investigators and lack per-event liquid fractions. Independent mean and variance tests remain open.

**Unit** fraction of parent beads

### fornell2017_passive_withdrawal@1

Ten-micrometre polystyrene beads in droplets split into approximately equal thirds. The center is the sampled branch. Passive center daughter, Figure 2c, all 180 vector markers. [Fornell et al. (2017), Fig. 2c](https://doi.org/10.1063/1.4984131)

- **Evidence role** descriptive
- **Observed** 0.4501 fraction of parent beads
- **Predicted** 0.3333 fraction of parent beads

The center volume was nominal. Per-droplet daughter volumes and a sampling criterion for bead-free droplets were unreported.

The nominal geometry underpredicts the mean of the 180 bead fractions by 0.117. At nine parent beads the sample mean was 4.0 versus 3.0 predicted, while the sample variance was 2.18 versus 2.00 beads². Unequal volumes and advection remain possible. [Dataset manifest](../checks/data/pool_withdrawal_measurements.json) · [Measurements](../checks/data/fornell2017_partition.json) · [Comparison verdict](../PROGRESS.md#fr35-withdrawal)

### liu2019_passive_retention@1

A separate droplet chip removes side streams and retains the center. The liquid retention estimate uses the center and input volumes at the same flow. Side-channel withdrawal at 4.5 µL/min, Figure 4b–c, acoustics off. [Liu et al. (2019), Fig. 4b–c](https://doi.org/10.1063/1.5129256)

- **Evidence role** descriptive
- **Observed** 0.282 fraction of parent beads
- **Predicted** 0.2723 fraction of parent beads

The center volume was 12.8 ± 1.1 nL, with the parent about 47 nL from the figure. Volume averages used 50 droplets. Bead retention had SD 0.044 across 20 splits.

Passive bead and volume retention are close in this preparation. Individual volumes paired with bead counts would distinguish independent sampling from geometry-dependent sorting. [Dataset manifest](../checks/data/pool_withdrawal_measurements.json) · [Comparison verdict](../PROGRESS.md#fr35-withdrawal)

### sahore2018_passive_bead_split@1

A magnet-off split in a separate microfluidic droplet device. Fig. 6d, field-off control showing the parent and two separated daughter droplets. [Sahore et al. (2018), Fig. 6d](https://doi.org/10.1039/C8AY01474D)

- **Evidence role** descriptive

No per-split volume calibration, count table or replicated passive occupancy fraction. The adjacent 59% withdrawal estimate was obtained during magnetic retention and is excluded.

Particles occupied both daughters in the illustrated passive split. The published quantitative withdrawal volume belongs to magnetic retention. [Dataset manifest](../checks/data/paired_replay_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-law-replays)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
