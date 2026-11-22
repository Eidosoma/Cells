<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Label remaining in a closed cell and clearance since the pulse account for the original cohort

After labelling stops, a solved tracer step changes the amount of old label in a region by labelled boundary inflow less local clearance. Across any finite sequence of such steps, label inside the region, label in the rest of the cell and clearance since the pulse sum to the amount present when the pulse ended.

## Assumptions

- The nodes form one closed cell with a fixed region and recorded one-way internal routes. Any new material joins another cohort. Each accepted step solves the tracer’s stated linear equations and books clearance using the same cohort share.
- The balance uses exact real arithmetic. Resolving the time course of mixing and inferring directional fluxes from two-way movement are separate questions.

## Lean proof

**Proved**

- [CellsProofs.Tissue.RegionalTracer.node_balance](../CellsProofs/Tissue/RegionalTracer.lean#L53)
- [CellsProofs.Tissue.RegionalTracer.region_balance](../CellsProofs/Tissue/RegionalTracer.lean#L81)
- [CellsProofs.Tissue.RegionalTracer.pulse_balance](../CellsProofs/Tissue/RegionalTracer.lean#L92)

Proof sources [Cells signed regional transfer theorem, specialized to the tracer’s labelled flux](../CellsProofs/Accounting/Transfer.lean#L35-L51) · [Mathlib finite sum over a region and its complement, imported (Finset.sum_add_sum_compl)](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L147-L150)

Uses [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** The largest whole-cell residual was 5.20 × 10⁻¹⁸ fmol across 501 donor-cohort rows. Across 251 rows starting at the pulse switch it was 2.71 × 10⁻¹⁹ fmol. The pulse account subtracts the 5.327 × 10⁻⁵ fmol already cleared by that switch.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.cell_owned_compartments@1`, `cells.scheduled_species_exchange@1`, `cells.scheduled_species_turnover@1`

[First-order exchange and route counter](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/src/cells/operators/species_exchange.py#L370-L417) · [Turnover and cumulative clearance](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/src/cells/operators/species_turnover.py#L266-L306) · [Two-compartment tissue fixture](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/validation/tissue/secreted_species_fixtures.py#L92) · [Matched transfer and clearance arms](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/validation/compartment_transfer/example.py#L44-L156) · [Regional totals and tracer linear solve](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/validation/regions/readouts.py#L451-L553) · [Pulse labelling schedule and mixed receiver](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/validation/regions/example.py#L49-L73) · [Tracer regression cases](https://github.com/Eidosoma/Cells/blob/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34/tests/unit/test_region_readouts.py#L94) · [Regional tracer proofs](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/CellsProofs/Tissue/RegionalTracer.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/checks/regional_tracer.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/411725a61be219d1769072107e6ed6c4f665a064/lean/PROGRESS.md#fr33-regional-tracer)

[Tested engine d48d40dd1ce0](https://github.com/Eidosoma/Cells/commit/d48d40dd1ce03c1093a1c27e775cd2e8239ccf34) · [Evidence checkpoint 411725a61be2](https://github.com/Eidosoma/Cells/commit/411725a61be219d1769072107e6ed6c4f665a064)

## Biological evidence

**Open.** The same pre-labelled protein inside a defined region, in its full complement, and across the whole neuron over a chase, with clearance and export accounted for.

**Unit** fmol in Cells and relative fluorescence in the imaged synapses

### uchigashima2025_psd95_map

A two-hour pulse/chase distinguished pre-existing and newly made PSD-95 in three mouse cortical pyramidal neurons. Figure 6a–e and Supplementary Figure 9d. [Uchigashima et al. (2025), Nature Communications](https://doi.org/10.1038/s41467-025-65813-w)

- **Evidence role** descriptive

The range 3,239–4,402 counts synaptic regions per neuron. It supplies no uncertainty on an old-label mass balance.

Endpoint maps show where old and new PSD-95 were detected. A longitudinal total including the diffuse pool is still needed to test the closed-cell balance. [Dataset manifest](../checks/data/regional_tracer_measurements.json) · [Comparison verdict](../PROGRESS.md#fr33-evidence)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
