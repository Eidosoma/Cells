<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Production and first-order clearance preserve a positive pool and account for gross turnover

At constant rates, the local pool solves dn/dt = P − kn. Production and clearance are separately nonnegative, their difference is the pool change, and subdivision preserves both the endpoint and the cumulative clearance. A balanced pool can have strictly positive production and clearance.

## Assumptions

- The neutral species starts at a positive amount in a well-mixed node of fixed volume. Each schedule interval has nonnegative constant production P and first-order clearance k. Clearance rates for the same pool add. Only cells can have production in this operator.
- The interval identities use exact real arithmetic. The numerical test also follows both gross bookings, the stored float64 amount and the signed chemical work when production and clearance are nearly equal.
- The protein chase uses a signal proportional to the retained pulse-labeled cohort, with zero new labeled input and a constant clearance rate per protein. A second fit fixes the signal background to the measured control. The assay tests the decay curve and leaves the protein’s charge, molar amount and chemical work unmeasured.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.SpeciesTurnover.initial_amount](../CellsProofs/Chemistry/SpeciesTurnover.lean#L28)
- [CellsProofs.Chemistry.SpeciesTurnover.zero_clearance](../CellsProofs/Chemistry/SpeciesTurnover.lean#L31)
- [CellsProofs.Chemistry.SpeciesTurnover.exposure_bounds](../CellsProofs/Chemistry/SpeciesTurnover.lean#L35)
- [CellsProofs.Chemistry.SpeciesTurnover.amount_pos](../CellsProofs/Chemistry/SpeciesTurnover.lean#L46)
- [CellsProofs.Chemistry.SpeciesTurnover.gross_nonneg](../CellsProofs/Chemistry/SpeciesTurnover.lean#L51)
- [CellsProofs.Chemistry.SpeciesTurnover.gross_balance](../CellsProofs/Chemistry/SpeciesTurnover.lean#L57)
- [CellsProofs.Chemistry.SpeciesTurnover.net_change](../CellsProofs/Chemistry/SpeciesTurnover.lean#L63)
- [CellsProofs.Chemistry.SpeciesTurnover.equilibrium_offset](../CellsProofs/Chemistry/SpeciesTurnover.lean#L68)
- [CellsProofs.Chemistry.SpeciesTurnover.amount_derivative](../CellsProofs/Chemistry/SpeciesTurnover.lean#L73)
- [CellsProofs.Chemistry.SpeciesTurnover.steady_turnover](../CellsProofs/Chemistry/SpeciesTurnover.lean#L90)
- [CellsProofs.Chemistry.SpeciesTurnover.compose_stages](../CellsProofs/Chemistry/SpeciesTurnover.lean#L99)
- [CellsProofs.Chemistry.SpeciesTurnover.cohort_survival](../CellsProofs/Chemistry/SpeciesTurnover.lean#L113)
- [CellsProofs.Chemistry.SpeciesTurnover.half_life](../CellsProofs/Chemistry/SpeciesTurnover.lean#L118)

Direct proof subject `cells.scheduled_species_turnover@1`

## Numerical comparison

**Checked.** All 144 scalar cases on each backend and two ordinary four-phase schedules matched the 60-digit reference. Both extreme-rate worlds stored the reference 2 fmol and booked 0.995667 pJ of chemical work. The earlier engine stored 1 fmol and zero work in the larger-rate case. A mixing-chamber check used metered input and exhaust without fitting the outlet measurements. At 120 minutes it predicted 0.387 vol% CO₂ against 0.318 ± 0.034 across four chambers (mean ± SD). [Riveros Lizana et al., Fig. 4](https://doi.org/10.3390/ani13162675)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_species_turnover@1`

[Net change during rapid turnover](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/operators/species_turnover.py#L273) · [Stored amount, production, clearance and work](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/src/cells/operators/species_turnover.py#L278) · [Engine regression at the switch in net calculation](https://github.com/Eidosoma/Cells/blob/dd085e36e9ced2edfed88c7194e970bd335f3ad0/tests/unit/test_species_turnover.py#L450) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/checks/species_turnover.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8f269af4c8b79150020b47a86dd71da848d91714/lean/PROGRESS.md#claim-source-review)

[Tested engine dd085e36e9ce](https://github.com/Eidosoma/Cells/commit/dd085e36e9ced2edfed88c7194e970bd335f3ad0) · [Evidence checkpoint 8f269af4c8b7](https://github.com/Eidosoma/Cells/commit/8f269af4c8b79150020b47a86dd71da848d91714)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.scheduled_species_turnover@1`

[Production and clearance bookings](https://github.com/Eidosoma/Cells/blob/54cb31957d48f488bddefcce7399ca4739dfbcea/src/cells/operators/species_turnover.py#L246) · [Net pool movement and signed work](https://github.com/Eidosoma/Cells/blob/54cb31957d48f488bddefcce7399ca4739dfbcea/src/cells/operators/species_turnover.py#L256) · [Summed cell and outside route rates](https://github.com/Eidosoma/Cells/blob/54cb31957d48f488bddefcce7399ca4739dfbcea/src/cells/operators/species_turnover.py#L279) · [Material and energy ledger integration](https://github.com/Eidosoma/Cells/blob/54cb31957d48f488bddefcce7399ca4739dfbcea/src/cells/operators/species_turnover.py#L568) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/13aaabb568e7f5c47a8571f35e1f4ae4b110595c/lean/checks/species_turnover.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/13aaabb568e7f5c47a8571f35e1f4ae4b110595c/lean/PROGRESS.md#scheduled-species-turnover)

[Tested engine 54cb31957d48](https://github.com/Eidosoma/Cells/commit/54cb31957d48f488bddefcce7399ca4739dfbcea) · [Evidence checkpoint 13aaabb568e7](https://github.com/Eidosoma/Cells/commit/13aaabb568e7f5c47a8571f35e1f4ae4b110595c)

## Biological evidence

**Open.** Mean labeled-protein puncta per neuron after the label is removed. Absolute production and clearance of the total protein pool remain open.

**Unit** puncta per neuron

### dorrbaum2018_protein_chase@1

Primary rat hippocampal neurons after a two-hour pulse. Each protein’s day 0 signal sets its scale, and its day 1 signal sets its decay rate. GM130 and Lamin B1 counts for individual cells, including methionine-only background controls. [Dörrbaum et al. (2018), Figure 2B, source data 1](https://doi.org/10.7554/eLife.34202.008)

- **Evidence role** held out from fitting
- **Fit** Day 0 and day 1 for each protein
- **Evaluation** GM130 days 2 and 3, Lamin B1 days 3 and 7
- **Excluded** Unlabeled production and total protein amount
- **Observed** 11.62 puncta per neuron
- **Predicted** 5.07 puncta per neuron

The displayed Lamin B1 day 7 mean is 11.62 ± 3.22 puncta per neuron (SD across 21 cells). The four late groups have 13–32 cells each. These SDs describe cell scatter. The holdouts are retrospective within one study.

For GM130 the early fit predicted 4.99 and 3.85 against means of 4.00 and 3.31 on days 2 and 3. For Lamin B1 it predicted 16.58 against 18.20 on day 3 and 5.07 against 11.62 on day 7. Including measured background raised the day 7 prediction to 5.97. The assay measures retention of labeled protein. [Dataset manifest](../checks/data/dorrbaum2018_protein_chase.json) · [Comparison verdict](../PROGRESS.md#scheduled-species-turnover)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
