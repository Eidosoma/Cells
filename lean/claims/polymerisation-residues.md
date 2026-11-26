<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Stage exits account for residues in unfinished, terminally held and detached chains

Per chain, residues supplied at stage exits equal the increase in residues in unfinished chains and terminally held RNA plus the residues carried by physical detachments. The update allows nonempty initial stages and holds.

## Assumptions

- The same signed extents update the stages, free machines and cumulative counters in each accepted half-step. Each chain has m ≥ 1 stages and length L = m r. Padded stages are inactive.
- Stage j carries j r residues per occupied complex. Each completion moves L residues into a declared terminal hold. Each physical detachment moves L residues into its product fate. Cumulative detached RNA includes products subsequently degraded.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Polymerisation.transit_change](../CellsProofs/Chemistry/Polymerisation.lean#L29)
- [CellsProofs.Chemistry.Polymerisation.residue_step](../CellsProofs/Chemistry/Polymerisation.lean#L48)
- [CellsProofs.Chemistry.TerminalRelease.hold_step](../CellsProofs/Chemistry/TerminalRelease.lean#L43)
- [CellsProofs.Chemistry.TerminalRelease.fate_sum](../CellsProofs/Chemistry/TerminalRelease.lean#L35)
- [CellsProofs.Chemistry.TerminalRelease.residue_step](../CellsProofs/Chemistry/TerminalRelease.lean#L48)

Direct proof subject `cells.operator.templated_polymerisation@1`

Proof sources [Mathlib sum_range_succ, used to telescope stage movements](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L498-L505) · [Cells stage layout, cumulative exits and residue ledger](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L1378-L1387) · [Mathlib Finset.sum_add_distrib, used to sum complementary fate fractions](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L267-L269) · [Cells per-chain and per-release residue ledgers](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/src/cells/operators/templated_polymerisation.py#L1992-L2012)

## Numerical comparison

**Checked.** The largest residue residual across 183 observations was 3.39 × 10⁻²⁰ fmol. A one-stage chain retained zero residues in transit while releasing 6.55 × 10⁻⁵ fmol alongside an eight-stage chain. In the 62 neutral-label observations the combined stage, hold and detachment balance across both machine policies closed within 1.19 × 10⁻¹⁹ fmol.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Stage layout, active stages and bound residue counts](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L700-L742) · [Half-step changes, cumulative counters and ledgers](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/operators/templated_polymerisation.py#L862-L1004) · [Public windowed simulation](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/src/cells/execution/windows.py) · [A1 and the competing two-chain world](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/worlds.py#L299-L416) · [Compiled histories and per-chain readouts](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/engine_run.py#L162-L175) · [Stage, pool and product output fields](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/engine_run.py#L267-L289) · [Truncating the original worlds](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/kernel.py#L22-L36) · [Independent copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/validation/gene_regulation/sheet_check.py#L90-L97) · [Existing polymerisation regressions](https://github.com/Eidosoma/Cells/blob/6b28ec55368011de79dce85e6172b5844b77a287/tests/unit/test_templated_polymerisation.py#L91-L100) · [Stage and pool proofs](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/CellsProofs/Chemistry/Polymerisation.lean) · [Ribosome occupancy and pulse-label measurements](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/data/polymerisation_pool_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/checks/polymerisation_balances.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d6db91d64f5c90d8e4857873052f4e667eba7469/lean/PROGRESS.md#polymerisation-balances)

[Tested engine 6b28ec553680](https://github.com/Eidosoma/Cells/commit/6b28ec55368011de79dce85e6172b5844b77a287) · [Evidence checkpoint d6db91d64f5c](https://github.com/Eidosoma/Cells/commit/d6db91d64f5c90d8e4857873052f4e667eba7469)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`, `cells.neutral_arrival_labels@1`

[Compiled state collection](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L178) · [R1, marking schedules and R1S](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/worlds.py#L520) · [Run horizon and grid](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/kernel.py#L35) · [Compiled window execution](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/execution/windows.py) · [Release extents and their label reports](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/templated_polymerisation.py#L1565) · [Neutral label and pool update](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/species_labels.py#L506) · [Survival and transfer of neutral shares](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/numerics/label_shares.py#L64) · [Composite applies the reporters' half-steps](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/models/pump_composite.py#L1752) · [RNA and hold amounts by label](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L317) · [Physical counters for both fates](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/engine_run.py#L429) · [Machine and residue ledgers](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/src/cells/operators/templated_polymerisation.py#L2129) · [Copy-to-fmol conversion](https://github.com/Eidosoma/Cells/blob/947ff262c7fba53b53b32a7c44394e84be3fa897/validation/gene_regulation/sheet_check.py#L90) · [Exact stage inventory](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/Polymerisation.lean) · [Exact hold and pool inventory](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/CellsProofs/Chemistry/TerminalRelease.lean) · [Polymerase retention and secondary transcription counts](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/data/harden2020_polymerase_retention.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/checks/terminal_release.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/4404a1b3cd889ba7a9a75f18df0cdf479898cd73/lean/PROGRESS.md#fr38-marked-fates)

[Tested engine 947ff262c7fb](https://github.com/Eidosoma/Cells/commit/947ff262c7fba53b53b32a7c44394e84be3fa897) · [Evidence checkpoint 4404a1b3cd88](https://github.com/Eidosoma/Cells/commit/4404a1b3cd889ba7a9a75f18df0cdf479898cd73)

## Biological evidence

**Open.** Incorporated tracer partitioned between nascent chains and released protein in a matched preparation.

**Unit** Counts per minute per unit of polysome OD₂₆₀ and seconds in the tracer study, fmol of residues in Cells

### stanners1968_nascent_released_label

The radiolabelled valine signals in soluble completed protein and polysome-associated nascent chains crossed at 34, 32, 40 and 32.5 s in four hamster-cell experiments. Figure 4 and Table II, experiments 1–4. [Stanners (1968), Biophysical Journal](https://doi.org/10.1016/S0006-3495(68)86487-2)

- **Evidence role** descriptive

Signals share a polysome optical-density normalization and include a correction for label attached outside nascent chains. The paper’s 23 ± 2 s transit time is a model-derived estimate.

The study resolves the two measured tracer pools. Relating its timing to the simulation requires matching the label pulse, precursor activity and sampling definitions. [Dataset manifest](../checks/data/polymerisation_pool_measurements.json) · [Comparison verdict](../PROGRESS.md#polymerisation-balances)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
