<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Identical donor traces under transfer and degradation have distinct receiver and loss records

Pure one-way transfer and local first-order degradation give the same donor curve for all times when their rate and starting amount agree. For a positive starting amount, rate and elapsed time, either receiver gain or cumulative clearance distinguishes the two mechanisms, and the two differences agree in magnitude.

## Assumptions

- The two controls begin with identical donor and receiver amounts. Each has the same constant first-order rate, zero production, and a single route out of the donor. The transfer receiver retains all arriving label, and degradation books all removed label as loss.
- The comparison uses amounts of the same cohort. A measured fluorescence ratio gives a local signal on a different scale.

## Lean proof

**Proved**

- [CellsProofs.Tissue.RegionalTracer.equal_donor_traces](../CellsProofs/Tissue/RegionalTracer.lean#L128)
- [CellsProofs.Tissue.RegionalTracer.receiver_and_loss_distinguish](../CellsProofs/Tissue/RegionalTracer.lean#L136)

Direct proof subject `cells.operator.scheduled_species_exchange@1`, `cells.operator.scheduled_species_turnover@1`

Proof sources [Cells first-order turnover amount and clearance, specialized at zero production](../CellsProofs/Chemistry/SpeciesTurnover.lean#L19-L26) · [Mathlib strict exponential bound, imported (Real.exp_lt_one_iff)](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Complex/Exponential.lean#L323-L330)

Uses [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md) · [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** The donors agreed exactly at all 11 outputs. At 0.5 s the transfer receiver gained 0.000393469 fmol with zero loss. Local degradation cleared 0.000393469 fmol with zero receiver gain.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.cell_owned_compartments@1`, `cells.scheduled_species_exchange@1`, `cells.scheduled_species_turnover@1`

[First-order exchange and route counter](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/src/cells/operators/species_exchange.py#L370-L417) · [Turnover and cumulative clearance](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/src/cells/operators/species_turnover.py#L266-L306) · [Two-compartment tissue fixture](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/validation/tissue/secreted_species_fixtures.py#L92) · [Matched transfer and clearance arms](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/validation/compartment_transfer/example.py#L44-L156) · [Receiver and loss control](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/tests/unit/test_compartment_transfer_example.py#L14) · [Matched-donor proofs](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/CellsProofs/Tissue/RegionalTracer.lean) · [First-order clearance specialization](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/CellsProofs/Chemistry/SpeciesTurnover.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/checks/regional_tracer.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/PROGRESS.md#fr33-matched-donors)

[Tested engine d48d40dd1ce0](https://github.com/Eidosoma/Cells/commit/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34) · [Evidence checkpoint 411725a61be2](https://github.com/Eidosoma/Cells/commit/411725a61be219d1769072107e6ed6c4f665a064)

## Biological evidence

**Open.** Labelled protein at its source, at receiving synapses and across the cell, sampled over the same period.

- [Regional Bassoon measurements identify how much loss from a labelled source was transfer and how much was degradation.](../WET_LAB_EVIDENCE.md#pair-bassoon-regional-transfer-budget) · Comparison unresolved

**Unit** fmol in Cells and per-spine green/red fluorescence ratio in the experiment

### gray2006_psd95_exchange

After local photoactivation of PSD-95 in mouse neocortex, signal fell in the source spine and rose in two neighboring spines. Figure 4A. [Gray et al. (2006), PLOS Biology](https://doi.org/10.1371/journal.pbio.0040370)

- **Evidence role** descriptive

The figure reports relative fluorescence in selected spines. A recovered mass fraction and a same-cohort whole-neuron total are unavailable from those traces.

The receiver signals document local redistribution. The protein and cause of the 48-hour decline in the Cells study remain unresolved. [Dataset manifest](../checks/data/regional_tracer_measurements.json) · [Comparison verdict](../PROGRESS.md#fr33-evidence)

### tomdieck2015_bassoon

Fixed neuronal cultures labelled throughout. Soma and dendritic signal were compared across time points. Fig. 3b–d, endogenous Bassoon pulse and chase. [tom Dieck et al. (2015)](https://doi.org/10.1038/nmeth.3319)

- **Evidence role** descriptive

The regional mask omits much of the axon. The observations use sampled groups and lack a whole-cell balance.

Somatic Bassoon label decreased while dendrite-associated label increased. Dörrbaum Fig. 2C reuses these data. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### tsuriel2009_bassoon

Neuronal cultures with local photoactivation of tagged Bassoon at boutons. Fig. 5D,F. [Tsuriel et al. (2009)](https://doi.org/10.1523/JNEUROSCI.4777-08.2009)

- **Evidence role** descriptive

The experiment does not measure surviving tagged Bassoon over the entire cell.

Label from a selectively activated region appeared at nearby unilluminated boutons. The regional increase is direct evidence for transfer. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
