<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Free and engaged polymerases or ribosomes sum to their machine pool

For any finite collection of chains sharing one pool, a stage update preserves free machines plus the sum of all its occupied stages. Only initiation and final release move a machine between the free and engaged pools.

## Assumptions

- The same signed extents update the stages, free machines and cumulative counters in each accepted half-step. Each chain has m ≥ 1 stages and length L = m r. Padded stages are inactive.
- Each chain draws from one declared machine pool. All chains using that pool enter its balance, including chains already in progress.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Polymerisation.engaged_change](../CellsProofs/Chemistry/Polymerisation.lean#L22)
- [CellsProofs.Chemistry.Polymerisation.pool_step](../CellsProofs/Chemistry/Polymerisation.lean#L39)

Direct proof subject `cells.templated_polymerisation@1`

Proof sources [Mathlib sum_range_succ, used to telescope stage movements](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L498-L505) · [Cells stage layout, cumulative exits and residue ledger](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L1378-L1387)

## Numerical comparison

**Checked.** Across 183 compiled rows the maximum pool residual was 5.80 × 10⁻¹⁹ fmol. Omitting one competing chain from the two-gene pool produced a 4.88 × 10⁻⁸ fmol discrepancy.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Stage layout, active stages and bound residue counts](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L700-L742) · [Half-step changes, cumulative counters and ledgers](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L862-L1004) · [Public windowed simulation](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/execution/windows.py) · [A1 and the competing two-chain world](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/worlds.py#L299-L416) · [Compiled histories and per-chain readouts](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/engine_run.py#L162-L175) · [Stage, pool and product output fields](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/engine_run.py#L267-L289) · [Truncating the original worlds](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/kernel.py#L22-L36) · [Independent copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/sheet_check.py#L90-L97) · [Existing polymerisation regressions](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/unit/test_templated_polymerisation.py#L91-L100) · [Stage and pool proofs](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/CellsProofs/Chemistry/Polymerisation.lean) · [Ribosome occupancy and pulse-label measurements](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/data/polymerisation_pool_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/polymerisation_balances.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/PROGRESS.md#polymerisation-balances)

[Tested engine 6b28ec553680](https://github.com/Eidosoma/Cells/commit/6b28ec55368011de79dce85e6172b5844b77a287) · [Evidence checkpoint d6db91d64f5c](https://github.com/Eidosoma/Cells/commit/d6db91d64f5c90d8e4857873052f4e667eba7469)

## Biological evidence

**Open.** Bound and unbound ribosome populations in the same preparation, with a known total and a stated definition of engagement.

**Unit** Fraction of the total ribosome pool in the experiment and fmol of machines in Cells

### li2018_ribosome_engagement

At a common growth rate of 0.09 per hour, mRNA-bound E. coli ribosomes accounted for 31 ± 3%, 51 ± 3% and 65 ± 4% of the pool under carbon, nitrogen and phosphorus limitation, respectively. Figure 1e, Table 1 and supplementary Table S1. [Li et al. (2018), Nature Microbiology](https://doi.org/10.1038/s41564-018-0199-2)

- **Evidence role** descriptive

Mean ± SEM across three biological replicates. Free subunits and free assembled ribosomes both enter the unbound pool. Bound particles can include stalled or initiating ribosomes.

The paired occupancy measurements establish condition dependence at matched growth. Both fractions share a denominator. An independent conservation test requires absolute counts and defined pool boundaries. [Dataset manifest](../checks/data/polymerisation_pool_measurements.json) · [Comparison verdict](../PROGRESS.md#polymerisation-balances)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
