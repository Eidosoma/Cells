<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Free and engaged polymerases or ribosomes sum to their machine pool

For chains sharing a machine pool, each update preserves free machines plus stage occupancies and the terminal holds that still engage a machine. A chain frees a machine at completion under the returned policy and at detachment under the held policy.

## Assumptions

- The same signed extents update the stages, free machines and cumulative counters in each accepted half-step. Each chain has m ≥ 1 stages and length L = m r. Padded stages are inactive.
- Each chain draws from one declared machine pool. All chains using that pool enter its balance, including chains already in progress.
- Each chain’s policy stays fixed through the update. The same physical detachment extent leaves the terminal hold and frees its machine under the held policy.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Polymerisation.engaged_change](../CellsProofs/Chemistry/Polymerisation.lean#L22)
- [CellsProofs.Chemistry.Polymerisation.pool_step](../CellsProofs/Chemistry/Polymerisation.lean#L39)
- [CellsProofs.Chemistry.TerminalRelease.pool_step](../CellsProofs/Chemistry/TerminalRelease.lean#L21)

Direct proof subject `cells.operator.templated_polymerisation@1`

Proof sources [Mathlib sum_range_succ, used to telescope stage movements](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L498-L505) · [Cells stage layout, cumulative exits and residue ledger](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L1378-L1387) · [Mathlib Finset.sum_add_distrib, imported for sums of machine occupancies](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L267-L269) · [Cells machine and terminal-hold ledgers](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/src/cells/operators/templated_polymerisation.py#L1992-L2012)

## Numerical comparison

**Checked.** Across 183 compiled observations the maximum pool residual was 5.80 × 10⁻¹⁹ fmol. Omitting one competing chain from the two-gene pool produced a 4.88 × 10⁻⁸ fmol discrepancy. On the neutral-label engine, 62 further observations across both terminal machine policies closed within 1.55 × 10⁻²⁰ fmol. Counting the initial hold under the opposite policy misplaced 80 machines in both cases.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Stage layout, active stages and bound residue counts](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L700-L742) · [Half-step changes, cumulative counters and ledgers](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L862-L1004) · [Public windowed simulation](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/execution/windows.py) · [A1 and the competing two-chain world](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/worlds.py#L299-L416) · [Compiled histories and per-chain readouts](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/engine_run.py#L162-L175) · [Stage, pool and product output fields](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/engine_run.py#L267-L289) · [Truncating the original worlds](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/kernel.py#L22-L36) · [Independent copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/sheet_check.py#L90-L97) · [Existing polymerisation regressions](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/unit/test_templated_polymerisation.py#L91-L100) · [Stage and pool proofs](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/CellsProofs/Chemistry/Polymerisation.lean) · [Ribosome occupancy and pulse-label measurements](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/data/polymerisation_pool_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/polymerisation_balances.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/PROGRESS.md#polymerisation-balances)

[Tested engine 6b28ec553680](https://github.com/Eidosoma/Cells/commit/6b28ec55368011de79dce85e6172b5844b77a287) · [Evidence checkpoint d6db91d64f5c](https://github.com/Eidosoma/Cells/commit/d6db91d64f5c90d8e4857873052f4e667eba7469)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`, `cells.neutral_arrival_labels@1`

[Compiled state collection](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L178) · [R1, marking schedules and R1S](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/worlds.py#L520) · [Run horizon and grid](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/kernel.py#L35) · [Compiled window execution](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/execution/windows.py) · [Release extents and their label reports](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/templated_polymerisation.py#L1565) · [Neutral label and pool update](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/species_labels.py#L506) · [Survival and transfer of neutral shares](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/numerics/label_shares.py#L64) · [Composite applies the reporters' half-steps](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/models/pump_composite.py#L1752) · [RNA and hold amounts by label](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L317) · [Physical counters for both fates](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L429) · [Machine and residue ledgers](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/templated_polymerisation.py#L2129) · [Copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/sheet_check.py#L90) · [Exact stage inventory](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/Polymerisation.lean) · [Exact hold and pool inventory](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/TerminalRelease.lean) · [Polymerase retention and secondary transcription counts](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/data/harden2020_polymerase_retention.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/terminal_release.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/PROGRESS.md#fr38-marked-fates)

[Tested engine 947ff262c7fb](https://github.com/Eidosoma/Cells/commit/947ff262c7fba53b53b32a7c44394e84be3fa897) · [Evidence checkpoint 4404a1b3cd88](https://github.com/Eidosoma/Cells/commit/4404a1b3cd889ba7a9a75f18df0cdf479898cd73)

## Biological evidence

**Open.** Machine occupancy with a stated pool boundary, and separately measured RNA departure, polymerase persistence on DNA and new transcription.

**Unit** Fractions of the stated experimental population, seconds for event timing and fmol of machines in Cells

### li2018_ribosome_engagement

At a common growth rate of 0.09 per hour, mRNA-bound E. coli ribosomes accounted for 31 ± 3%, 51 ± 3% and 65 ± 4% of the pool under carbon, nitrogen and phosphorus limitation, respectively. Figure 1e, Table 1 and supplementary Table S1. [Li et al. (2018), Nature Microbiology](https://doi.org/10.1038/s41564-018-0199-2)

- **Evidence role** descriptive

Mean ± SEM across three biological replicates. Free subunits and free assembled ribosomes both enter the unbound pool. Bound particles can include stalled or initiating ribosomes.

The paired occupancy measurements establish condition dependence at matched growth. Both fractions share a denominator. An independent conservation test requires absolute counts and defined pool boundaries. [Dataset manifest](../checks/data/polymerisation_pool_measurements.json) · [Comparison verdict](../PROGRESS.md#polymerisation-balances)

### harden2020_polymerase_retention

Purified E. coli polymerase remained at the DNA spot more than four seconds after sense RNA departure in 87 of 100 selected traces. A separate experiment detected antisense RNA in 78/114 traces with reverse motion and 5/257 without it. Figures 1c–e and 3a,c and accompanying Results. [Harden et al. (2020), Nature Communications 11, 448](https://doi.org/10.1038/s41467-019-14208-9)

- **Evidence role** descriptive

The 100 traces came from two experiments. The four-second threshold reflects frame timing. The secondary transcription counts have separate motion-selected denominators.

These experiments distinguish RNA release, DNA retention and productive reuse. Return to a well-mixed free pool was unobserved. [Dataset manifest](../checks/data/harden2020_polymerase_retention.json) · [Comparison verdict](../PROGRESS.md#fr38-terminal-inventories)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
