<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# One-site binding follows the free ligand concentration

At equilibrium the occupied fraction of sites is c / (Kd + c), where c is free ligand concentration and Kd is the dissociation constant. The normalized weights of the two binder forms give the same fraction.

## Assumptions

- One ligand binds one site. Each binder has a free and a singly occupied form, with positive total sites and positive association and dissociation rates. Kd is their off-rate divided by their on-rate.
- Both concentrations are expressed in mM. The rate-balance theorem allows zero free ligand. The log-weight theorem uses positive free ligand and a positive Kd.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.SingleSite.occupancy_from_rates](../CellsProofs/Chemistry/SingleSiteBinding.lean#L19)
- [CellsProofs.Chemistry.SingleSite.occupancy_from_log_weights](../CellsProofs/Chemistry/SingleSiteBinding.lean#L28)

Direct proof subject `cells.rapid_binding@1`

Proof sources [Langmuir kinetic derivation, adapted from Lean 3](https://github.com/ATOMSLab/LeanChemicalTheories/blob/00841fedb86c0af282f515eda7e83a525a42e048/src/adsorption/langmuir_kinetics.lean) · [Bobbin et al., Digital Discovery](https://doi.org/10.1039/D3DD00077J)

## Numerical comparison

**Checked.** Across thirteen manufactured S1 states, the largest absolute occupancy difference from the independent reference was 3.33 × 10⁻¹⁶. Using total ligand in the same formula failed all thirteen. The first state also passed through the tissue’s stage read.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Binding weights](https://github.com/Eidosoma/Cells/blob/9a5bc6b8211847888cbb83c41ad88941bac19213/src/cells/laws/reactions/rapid_binding.py#L87) · [One-step branch](https://github.com/Eidosoma/Cells/blob/9a5bc6b8211847888cbb83c41ad88941bac19213/src/cells/laws/reactions/rapid_binding.py#L217) · [Tissue stage read](https://github.com/Eidosoma/Cells/blob/9a5bc6b8211847888cbb83c41ad88941bac19213/src/cells/kinds/proton_buffer.py#L707) · [Independent S1 design](https://github.com/Eidosoma/Cells/blob/9a5bc6b8211847888cbb83c41ad88941bac19213/validation/core_seams/references/README.md#L101) · [Frozen reference values](https://github.com/Eidosoma/Cells/blob/9a5bc6b8211847888cbb83c41ad88941bac19213/validation/core_seams/references/designs/core_seams_reference_values.json) · [Numerical tolerances](https://github.com/Eidosoma/Cells/blob/9a5bc6b8211847888cbb83c41ad88941bac19213/tests/unit/test_rapid_binding_kernel.py#L127) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/c4b3f5ce8fefbd403fa9fa0344bea14c9be8f55c/lean/checks/single_site_binding.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/c4b3f5ce8fefbd403fa9fa0344bea14c9be8f55c/lean/PROGRESS.md#19-november-2026--single-site-binding-and-face-power-units)

[Tested engine 9a5bc6b82118](https://github.com/Eidosoma/Cells/commit/9a5bc6b8211847888cbb83c41ad88941bac19213) · [Evidence checkpoint c4b3f5ce8fef](https://github.com/Eidosoma/Cells/commit/c4b3f5ce8fefbd403fa9fa0344bea14c9be8f55c)

## Biological evidence

**Open.** Equilibrium bound fraction measured across a free ligand titration for an identified single-site binder at specified temperature and solution conditions.

**Unit** fraction of sites occupied

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
