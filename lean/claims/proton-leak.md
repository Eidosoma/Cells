<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Voltage and free proton concentrations set the leak reversal

For an open route, inward flux is positive exactly when hOut exceeds hIn × B(−x)/B(x), using the engine’s selected Bernoulli factor at x = FV/(RT). The analytic law reverses at V = (RT/F) × (ln hOut − ln hIn) and releases nonnegative instantaneous heat. The engine’s real-arithmetic evaluator gives the analytic flux at x = 0 and for |x| ≥ 10⁻⁴. At other x the polynomial has its own reversal ratio. At fixed voltage and opening, the change in inward flux is scale × B(x) times the change in free outside concentration.

## Assumptions

- Positive free H⁺ concentrations on both sides in mM, positive absolute temperature and proton valence +1. Voltage is inside minus outside, with positive flux inward.
- Area × permeability × opening is positive for directional claims and may be zero for the heat inequality. The proof interprets both evaluator branches in real arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Transport.ProtonLeak.series_flux](../CellsProofs/Transport/ProtonLeak.lean#L69)
- [CellsProofs.Transport.ProtonLeak.series_inward_iff](../CellsProofs/Transport/ProtonLeak.lean#L76)
- [CellsProofs.Transport.ProtonLeak.series_eq_analytic](../CellsProofs/Transport/ProtonLeak.lean#L83)
- [CellsProofs.Transport.ProtonLeak.analytic_inward_iff](../CellsProofs/Transport/ProtonLeak.lean#L101)
- [CellsProofs.Transport.ProtonLeak.analytic_equilibrium_iff](../CellsProofs/Transport/ProtonLeak.lean#L107)
- [CellsProofs.Transport.ProtonLeak.reversal_voltage_iff](../CellsProofs/Transport/ProtonLeak.lean#L112)
- [CellsProofs.Transport.ProtonLeak.analytic_heat_nonneg](../CellsProofs/Transport/ProtonLeak.lean#L122)
- [CellsProofs.Transport.ProtonLeak.outside_change](../CellsProofs/Transport/ProtonLeak.lean#L138)
- [CellsProofs.Transport.ProtonLeak.strictMono_outside](../CellsProofs/Transport/ProtonLeak.lean#L145)

Direct proof subject `cells.route.proton_constant_field_leak@1`

Proof sources [Cells constant-field definitions](../CellsProofs/Transport/ConstantField.lean) · [Goldman’s constant-field model (1943)](https://doi.org/10.1085/jgp.27.1.37) · [Mathlib positive product, imported for strict outside sensitivity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/GroupWithZero/Unbundled/Basic.lean#L34-L37)

## Numerical comparison

**Checked.** Twelve compiled CPU cases agreed with the 70-digit flux reference within 1.55 × 10⁻²⁰ fmol/s. In a buffered tissue cell, using free H⁺ gave the observed inward rate of 3.31 × 10⁻⁶ fmol/s. Substituting total intracellular proton equivalents reversed the predicted direction. Eight additional composite clamps tracked lumen pH at fixed voltage when bath pH varied independently. Version 1 refused the general-binding node. [Version 2](buffered-proton-reversal.md) exercises that endpoint. Six compiled roots agreed with the Nernst values at nominal pipette and bath pH to within 10⁻¹⁰ mV. At microglial pipette/bath pH 5.5/7.8 the model gave −135.15 mV at 23 °C against an approximate −86 mV measured.

**Engine** `resolved_pump_tissue@3`, `proton_constant_field_leak@1`

[Inward flux and instantaneous heat](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/src/cells/laws/transport/proton_leak.py#L28) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/src/cells/laws/electrochemistry.py#L17) · [Tissue patch rates and endpoints](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/src/cells/kinds/passive_routes.py#L348) · [Independent Decimal flux](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/validation/betse/junction_transport/check.py#L10) · [Independent free-proton closure](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/validation/compartment_ph/ph_reference.py#L167) · [Buffered tissue fixture](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/tests/unit/test_proton_buffer_kind.py#L258) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/252cb83542e368e5572328d7eb0266ca8bd7417f/lean/checks/proton_leak.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/252cb83542e368e5572328d7eb0266ca8bd7417f/lean/PROGRESS.md#19-november-2026--passive-proton-leak)

[Tested engine 1dee280f681a](https://github.com/Eidosoma/Cells/commit/1dee280f681af373071079c5f9b5921725dc7ed3) · [Evidence checkpoint 252cb83542e3](https://github.com/Eidosoma/Cells/commit/252cb83542e368e5572328d7eb0266ca8bd7417f)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `proton_constant_field_leak@1`

[Three-compartment definition](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/validation/compartment_ph_engine/definitions.py#L117) · [Patch endpoints](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/kinds/passive_routes.py#L585) · [Voltage clamp after the stage read](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/models/pump_composite.py#L1826) · [Free-proton law](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/laws/transport/proton_leak.py#L31) · [Independent Decimal flux](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/validation/betse/junction_transport/check.py#L10) · [General closure admission](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/registry/species_registry.py#L1809) · [Seven-cycle fixture](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/tests/unit/test_mito_cycle_laws.py#L85) · [Single outside binding control](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/tests/unit/test_rapid_binding_world.py#L418) · [MT-1b compartment declaration](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/docs/MITOCHONDRIA_DESIGN.md#L2232) · [Cortese pH ranges](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/data/cortese1992_ims_ph.json) · [Independent flux orientation](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/proton_leak.py) · [Joint mitochondrial control](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/mitochondrial_cycles.py) · [Exact outside dependence](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/CellsProofs/Transport/ProtonLeak.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/ims_proton_leak.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/PROGRESS.md#mt1b-local-proton-read)

[Tested engine 5ef761505f2d](https://github.com/Eidosoma/Cells/commit/5ef761505f2dbd48c35e36a2caee391e1f7d9394) · [Evidence checkpoint ddd2dbd0dc2b](https://github.com/Eidosoma/Cells/commit/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2)

**Engine** `cells.passive_constant_field_permeation@1`, `cells.proton_constant_field_leak@1`

[Three-ion constant-field flux](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/routes/constant_field_permeation.py#L59) · [Open-route proton flux](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/transport/proton_leak.py#L31) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/electrochemistry.py#L10) · [Flux evaluation](https://github.com/Eidosoma/Cells/blob/0455ce787fd8c36ec2eb51389e4f5a5a5012f253/src/cells/laws/electrochemistry.py#L32) · [1949 squid permeability ratios](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/checks/data/hodgkin_katz1949_rest.json) · [1979 substitutions and measured proton reversals](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/checks/data/membrane_physiology_pairs.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/checks/paired_membrane_physiology.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/34e1f9dfc1628af1f81e66cf8166d5c6f4207407/lean/PROGRESS.md#paired-membrane-physiology)

[Tested engine 0455ce787fd8](https://github.com/Eidosoma/Cells/commit/0455ce787fd8c36ec2eb51389e4f5a5a5012f253) · [Evidence checkpoint 34e1f9dfc162](https://github.com/Eidosoma/Cells/commit/34e1f9dfc1628af1f81e66cf8166d5c6f4207407)

**Engine** `resolved_pump_tissue@3`, `cells.proton_atp_mass_action_positive@1`, `cells.proton_constant_field_leak@1`, `cells.inward_rectifier_linear_driving_force@1`, `cells.kir2p1_mh2@1`, `cells.rapid_binding@1`

[Tight-coupled proton pump](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/pumps/proton_pump.py#L91) · [Proton flux](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/transport/proton_leak.py#L31) · [Kir slope conductance](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L127) · [Two binding forms](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/reactions/rapid_binding.py#L340) · [Tissue channel current](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/models/surface_pump_v3.py#L621) · [Thermodynamic constants](https://github.com/Eidosoma/Cells/blob/153449799f4d301a34f2be58172becc4dc562806/src/cells/laws/electrochemistry.py#L10) · [Preparation records](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_preparation_controls.json) · [Kir slopes and controls](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/data/paired_replay_measurements.json) · [Fixed-drive Kir evaluation](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_law_replays.py) · [Native proton roots](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_membrane_physiology.py) · [Tissue clamp specimen](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/clamped_channel_current.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/checks/paired_preparation_controls.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/01edbd968e182f91c0bd281fe776f5609a78e645/lean/PROGRESS.md#preparation-evidence-review)

[Tested engine 153449799f4d](https://github.com/Eidosoma/Cells/commit/153449799f4d301a34f2be58172becc4dc562806) · [Evidence checkpoint 01edbd968e18](https://github.com/Eidosoma/Cells/commit/01edbd968e182f91c0bd281fe776f5609a78e645)

## Biological evidence

**Open.** Reversal voltage of an open H⁺ path across measured pH gradients at known temperature. Predicting the signed flux magnitude also requires permeability, area and opening.

- [An increased bath-minus-intracellular pH difference moves the open proton-current reversal to more negative intracellular voltages.](../WET_LAB_EVIDENCE.md#pair-proton-gradient-tail-reversal) · Supported by both studies
- [In brown-fat and skeletal-muscle mitochondrial inner membranes, a one-unit bath-minus-matrix pH difference produces a proton-current reversal near −59 mV at 24 °C.](../WET_LAB_EVIDENCE.md#pair-mitoplast-proton-reversal-independence) · Independent replication unconfirmed
- [A one-unit increase in bath minus pipette pH shifts plasma-membrane proton-current reversal negatively, by roughly 50–60 mV in these buffered whole-cell preparations.](../WET_LAB_EVIDENCE.md#pair-plasma-proton-reversal-slope) · Supported by both studies

In Jurkat T cells the proton-current reversal shifted −47 mV per pH unit, versus an ideal −58 mV per pH unit. The fitted slope uncertainty and intracellular pH limit a quantitative verdict. Independent macrophage and microglia tail currents also show the sign of the pH response, with the largest departures when nominal pipette and bath pH are furthest apart. Two inner-membrane measurements share a laboratory. [Schilling et al., Fig. 2E](https://doi.org/10.1113/jphysiol.2002.028878) Sasaki’s independent expression study also reported tail reversal near proton equilibrium. A three-lab comparison with measured pH at both membrane faces remains open. [Sasaki et al.](https://doi.org/10.1126/science.1122352)

**Unit** mV at reversal, fmol/s for signed proton flux

### cortese1992_ims_ph

Soluble FITC-dextran sampled intermembrane-space pH in intact isolated rat liver mitochondria. Abstract, external pH 6.0–8.5. [Cortese et al. (1992)](https://doi.org/10.1016/0005-2728(92)90081-C)

- **Evidence role** descriptive

The authors reported ranges across conditions. The abstract leaves the replicate errors and respiratory state for each reading unspecified.

Relative to the bath, the intermembrane space was 0.4–0.5 pH units more acidic in the condensed configuration and 0–0.2 more acidic in the orthodox configuration. This supports a compartment-specific proton input. The uncoupled gradient and leak rate remain open. [Dataset manifest](../checks/data/cortese1992_ims_ph.json) · [Comparison verdict](../PROGRESS.md#mt1b-local-proton-read)

### kapus1993_macrophage_proton@1

Native mouse peritoneal macrophages, whole-cell proton tail currents at approximately 22 °C. Voltage is cell interior relative to bath. Table II, symmetric Cs-aspartate rows, and Fig. 8 on pH changes during prolonged depolarization [Kapus et al. (1993), Table II and Fig. 8](https://doi.org/10.1085/jgp.102.4.729)

- **Evidence role** descriptive

Table II reports means ± SEM. Estimated residual junction offsets below 6 mV were uncorrected. The intracellular dye indicated good initial dialysis and a rise in pH of up to 0.8 during a 9 s pulse in a separate experiment.

At bath pH 7.5 and pipette pH 6.0 or 6.8 the observed reversals were −69.17 ± 9.25 and −38.07 ± 3.60 mV. The nominal Cells roots at 22 °C were −87.85 and −40.99 mV. The independently observed intracellular alkalinization can shift an experimental reversal. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### morihata2000_microglia_proton@1

Native rat microglia, pipette pH 5.5, bath pH stepped across four solutions. Temperature 22–24 °C. Voltage is cell interior relative to bath. Figure 2B–C, reversal from proton current tails [Morihata et al. (2000), Fig. 2B–C](https://doi.org/10.1523/JNEUROSCI.20-19-07220.2000)

- **Evidence role** descriptive

Means and SEMs read approximately from the figure. The 45 mV/pH slope over the first three baths is printed in the text. Liquid junction potential was corrected before sealing. Intracellular pH at tail measurement was unmeasured.

The reported shift was about −45 mV per unit increase in bath pH from 6.3 to 7.3. At bath pH 7.8 the crossing was approximately −86 mV against the nominal −135.15 mV at 23 °C. These values constrain the direction of proton transport under voltage clamp. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### fedorenko2012_ucp1_reversal@1

Mouse brown-adipose mitoplasts with UCP1-associated current. Figure 6E used bath oleic acid and 15 mM pipette α-cyclodextrin to impose asymmetric fatty-acid availability. Voltage is matrix relative to bath. Figure 1F, reversal across gradients, and Fig. 6E, an example with two bath pH values [Fedorenko, Lishko and Kirichok (2012), Figs. 1F and 6E](https://doi.org/10.1016/j.cell.2012.09.010)

- **Evidence role** descriptive

Approximate crossings in Fig. 6E lack individual voltage error estimates. The manuscript Results and Fig. 6E caption disagree on the bath oleic-acid unit, so its concentration is excluded from the comparison. The separate multi-gradient comparison in Fig. 1F used 3–10 recordings per condition and a 24 °C Nernst reference. This study and the 2019 skeletal-muscle study share the Kirichok laboratory.

At fixed matrix pH 7, raising bath pH from 7 to 8 moved the example reversal from approximately 0 to −60 mV. The asymmetric ligand conditions limit transfer of current magnitude. [Dataset manifest](../checks/data/membrane_physiology_pairs.json) · [Comparison verdict](../PROGRESS.md#paired-membrane-physiology)

### bertholet-2019-proton-reversal

Fatty-acid-activated proton current in mouse skeletal muscle mitoplasts. Three matrix/bath pH pairs, 13 individual voltages. The group means are −62.23, −91.13 and +28.82 mV. Extended Data Figure 3d and its source workbook. [Bertholet et al. (2019), Nature 571, 515–520](https://doi.org/10.1038/s41586-019-1400-3)

- **Evidence role** descriptive

Calculated sample SEMs are 1.92, 1.82 and 6.70 mV (n = 6, 3 and 4). The workbook gives individual readings and sample SD. Group intervals use the 95% Student t interval for independent observations. The figure specifies 24 °C for the Nernst reference.

The unfitted Cells roots were −58.96, −88.44 and +29.48 mV. Each lies within its group interval. This retrospective check concerns reversal of the observed proton current. It supplies no absolute permeability calibration. [Dataset manifest](../checks/data/bertholet2019_proton_reversal.json) · [Comparison verdict](../PROGRESS.md#mt1b-buffered-reversal)

### cherny1995_alveolar

Native rat alveolar epithelial proton current, whole-cell tails at 20 °C. Fig. 2. [Cherny, Markin and DeCoursey (1995)](https://doi.org/10.1085/jgp.105.6.861)

- **Evidence role** descriptive

Twelve pH combinations, 2–18 observations per point. SDs describe points. The slope has no reported interval.

The fitted reversal slope was −52.4 mV per unit of bath minus pipette pH. Local proton activity during the tails was unmeasured. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

### ramsey2006_hv1

Human Hv1 in HEK cells, whole-cell tails at pipette pH 6.5 and 22–24 °C. Figs. 1e–f. [Ramsey et al. (2006)](https://doi.org/10.1038/nature04700)

- **Evidence role** descriptive

Group means ± SEM with 10, 14 and 5 recordings. Local membrane pH was unmeasured.

Measured roots were +53.3, +0.9 and −56.5 mV at bath pH 5.5, 6.5 and 7.5. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
