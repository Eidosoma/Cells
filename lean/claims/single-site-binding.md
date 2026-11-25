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

**Engine** `resolved_pump_tissue@3`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_constant_field_leak@1`, `cells.inward_rectifier_linear_driving_force@1`, `cells.kir2p1_mh2@1`, `cells.rapid_binding@1`

[Tight-coupled proton pump](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/pumps/proton_pump.py#L91) · [Proton flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/transport/proton_leak.py#L31) · [Kir slope conductance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Two binding forms](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/reactions/rapid_binding.py#L340) · [Tissue channel current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/electrochemistry.py#L10) · [Preparation records](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_preparation_controls.json) · [Kir slopes and controls](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_replay_measurements.json) · [Fixed-drive Kir evaluation](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_law_replays.py) · [Native proton roots](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_membrane_physiology.py) · [Tissue clamp specimen](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/clamped_channel_current.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_preparation_controls.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/PROGRESS.md#preparation-evidence-review)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 01edbd968e18](https://github.com/Eidosoma/Cells/commit/01edbd968e182f91c0bd281fe776f5609a78e645)

## Biological evidence

**Open.** Equilibrium bound fraction across a free ligand titration at specified temperature and solution conditions.

- [Purified mammalian myoglobin has an approximately single-site oxygen equilibrium curve when each preparation supplies its own affinity.](../WET_LAB_EVIDENCE.md#pair-myoglobin-oxygen-isotherm) · Supported by both studies

For oxygen binding to human myoglobin at 10 °C, two digitized points set the affinity. The other three gave a root-mean-square error of 0.0422 in fractional occupancy. All five come from one figure with unknown pointwise uncertainty. [Rossi-Fanelli and Antonini, Fig. 2](https://pubmed.ncbi.nlm.nih.gov/13584010/) · [Digitized points](https://bi1.caltech.edu/2017/code/t05_nonlinear_regression.html)

**Unit** fraction of sites occupied

### rossi1958

Purified human myoglobin at pH 7.45 in Tris. Equilibrium oxygen pressure sets free oxygen within this medium. Fig. 2, Table I and the 10 °C figure digitization. [Rossi-Fanelli and Antonini (1958)](https://doi.org/10.1016/0003-9861(58)90094-8)

- **Evidence role** held out from fitting
- **Fit** Digitized points 1 and 4
- **Evaluation** Digitized points 2, 3 and 5 from the same figure

The five readings come from one figure with no pointwise uncertainty. Two were chosen for a retrospective fit.

The original table gives P50 about 0.324 Torr. The two-point fit gives 0.3311 Torr and native binding gives RMSE 0.0422 for the other three points. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### schenkman1997

Equine myoglobin equilibrated against 16 known gas mixtures. The fit corrected for metmyoglobin. Table 1 and the multiwavelength oxygen-equilibrium series. [Schenkman et al. (1997)](https://doi.org/10.1152/jappl.1997.82.1.86)

- **Evidence role** calibration

The 37 °C affinity is a fitted parameter. Independently scored equine point uncertainties are unavailable in this comparison.

The equilibrium curve was described by a single-site isotherm with P50 2.39 Torr at 37 °C and pH 7.0. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
