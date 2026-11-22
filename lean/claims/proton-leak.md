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

Direct proof subject `cells.proton_constant_field_leak@1`

Proof sources [Cells constant-field definitions](../CellsProofs/Transport/ConstantField.lean) · [Goldman’s constant-field model (1943)](https://doi.org/10.1085/jgp.27.1.37) · [Mathlib positive product, imported for strict outside sensitivity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/GroupWithZero/Unbundled/Basic.lean#L34-L37)

## Numerical comparison

**Checked.** Twelve compiled CPU cases agreed with the 70-digit flux reference within 1.55 × 10⁻²⁰ fmol/s. In a buffered tissue cell, using free H⁺ gave the observed inward rate of 3.31 × 10⁻⁶ fmol/s. Substituting total intracellular proton equivalents reversed the predicted direction. Eight additional composite clamps tracked lumen pH at fixed voltage when bath pH varied independently. MT-1b’s general-binding node currently refuses the leak.

**Engine** `resolved_pump_tissue@3`, `proton_constant_field_leak@1`

[Inward flux and instantaneous heat](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/src/cells/laws/transport/proton_leak.py#L28) · [Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/src/cells/laws/electrochemistry.py#L17) · [Tissue patch rates and endpoints](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/src/cells/kinds/passive_routes.py#L348) · [Independent Decimal flux](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/validation/betse/junction_transport/check.py#L10) · [Independent free-proton closure](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/validation/compartment_ph/ph_reference.py#L167) · [Buffered tissue fixture](https://github.com/Eidosoma/Cells/blob/1dee280f681af373071079c5f9b5921725dc7ed3/tests/unit/test_proton_buffer_kind.py#L258) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/252cb83542e368e5572328d7eb0266ca8bd7417f/lean/checks/proton_leak.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/252cb83542e368e5572328d7eb0266ca8bd7417f/lean/PROGRESS.md#19-november-2026--passive-proton-leak)

[Tested engine 1dee280f681a](https://github.com/Eidosoma/Cells/commit/1dee280f681af373071079c5f9b5921725dc7ed3) · [Evidence checkpoint 252cb83542e3](https://github.com/Eidosoma/Cells/commit/252cb83542e368e5572328d7eb0266ca8bd7417f)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `proton_constant_field_leak@1`

[Three-compartment definition](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/validation/compartment_ph_engine/definitions.py#L117) · [Patch endpoints](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/kinds/passive_routes.py#L585) · [Voltage clamp after the stage read](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/models/pump_composite.py#L1826) · [Free-proton law](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/laws/transport/proton_leak.py#L31) · [Independent Decimal flux](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/validation/betse/junction_transport/check.py#L10) · [General closure admission](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/src/cells/registry/species_registry.py#L1809) · [Seven-cycle fixture](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/tests/unit/test_mito_cycle_laws.py#L85) · [Single outside binding control](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/tests/unit/test_rapid_binding_world.py#L418) · [MT-1b compartment declaration](https://github.com/Eidosoma/Cells/blob/5ef761505f2dbd48c35e36a2caee391e1f7d9394/docs/MITOCHONDRIA_DESIGN.md#L2232) · [Cortese pH ranges](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/data/cortese1992_ims_ph.json) · [Independent flux orientation](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/proton_leak.py) · [Joint mitochondrial control](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/mitochondrial_cycles.py) · [Exact outside dependence](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/CellsProofs/Transport/ProtonLeak.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/checks/ims_proton_leak.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2/lean/PROGRESS.md#mt1b-local-proton-read)

[Tested engine 5ef761505f2d](https://github.com/Eidosoma/Cells/commit/5ef761505f2dbd48c35e36a2caee391e1f7d9394) · [Evidence checkpoint ddd2dbd0dc2b](https://github.com/Eidosoma/Cells/commit/ddd2dbd0dc2b01bc7f2db3715ccef4c229e23ae2)

## Biological evidence

**Open.** Reversal voltage of an open H⁺ path across measured pH gradients at known temperature. Predicting the signed flux magnitude also requires permeability, area and opening.

In Jurkat T cells the proton-current reversal shifted −47 mV per pH unit, versus an ideal −58 mV per pH unit. The fitted slope uncertainty and intracellular pH limit a quantitative verdict. [Schilling et al., Fig. 2E](https://doi.org/10.1113/jphysiol.2002.028878)

**Unit** mV at reversal, fmol/s for signed proton flux

### cortese1992_ims_ph

Soluble FITC-dextran sampled intermembrane-space pH in intact isolated rat liver mitochondria. Abstract, external pH 6.0–8.5. [Cortese et al. (1992)](https://doi.org/10.1016/0005-2728(92)90081-C)

- **Evidence role** descriptive

The authors reported ranges across conditions. The abstract leaves the replicate errors and respiratory state for each reading unspecified.

Relative to the bath, the intermembrane space was 0.4–0.5 pH units more acidic in the condensed configuration and 0–0.2 more acidic in the orthodox configuration. This supports a compartment-specific proton input. The uncoupled gradient and leak rate remain open. [Dataset manifest](../checks/data/cortese1992_ims_ph.json) · [Comparison verdict](../PROGRESS.md#mt1b-local-proton-read)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
