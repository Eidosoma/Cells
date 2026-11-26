<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# An equilibrium channel blocker bounds flux sensitivity to voltage and concentration

The weighted fraction of unblocked channels lies between zero and one. Its absolute voltage derivative equals the native slope bound when the modes share a blocker side and charge sign. The product of this fraction and the free current obeys the native stage bound whenever the free current has the declared conductance bound. With the permeant ion’s reversal as reference, the inside and outside concentration bounds include how that ion changes both its free flux and the blocker fraction.

## Assumptions

- Each mode has a positive dissociation constant at zero reference voltage. The blocker concentration is nonnegative. The finite mode weights are nonnegative and have positive total. Cells normalizes by the actual weight sum.
- The voltage derivative holds concentration, temperature, availability and gate state fixed. The reference is membrane voltage or membrane voltage minus a fixed reversal potential. The native declaration assigns a single blocker side and charge sign to all modes.
- Each concentration derivative fixes membrane voltage, blocker dose, gate state, temperature and the opposite endpoint. The permeant ion has nonzero signed valence, both endpoint concentrations are positive and the free flux has a nonnegative permeability scale.
- A measured current ratio represents pore block only to the extent that changes in gating, driving force and the recording protocol are accounted for. Quantitative comparisons require a declared preparation, dose and voltage range.

## Lean proof

**Proved**

- [CellsProofs.Transport.OpenChannelBlock.mode_hasDerivAt](../CellsProofs/Transport/OpenChannelBlock.lean#L31)
- [CellsProofs.Transport.OpenChannelBlock.unblocked_mem_unit](../CellsProofs/Transport/OpenChannelBlock.lean#L55)
- [CellsProofs.Transport.OpenChannelBlock.zero_blocker](../CellsProofs/Transport/OpenChannelBlock.lean#L67)
- [CellsProofs.Transport.OpenChannelBlock.unblocked_hasDerivAt](../CellsProofs/Transport/OpenChannelBlock.lean#L73)
- [CellsProofs.Transport.OpenChannelBlock.abs_deriv_le_slopeBound](../CellsProofs/Transport/OpenChannelBlock.lean#L83)
- [CellsProofs.Transport.OpenChannelBlock.abs_deriv_eq_slopeBound_of_common_sign](../CellsProofs/Transport/OpenChannelBlock.lean#L98)
- [CellsProofs.Transport.OpenChannelBlock.current_slope_bound](../CellsProofs/Transport/OpenChannelBlock.lean#L122)
- [CellsProofs.Transport.BlockMaterialSlope.drive_outside](../CellsProofs/Transport/BlockMaterialSlope.lean#L18)
- [CellsProofs.Transport.BlockMaterialSlope.drive_inside](../CellsProofs/Transport/BlockMaterialSlope.lean#L24)
- [CellsProofs.Transport.BlockMaterialSlope.outside_concentration_bound](../CellsProofs/Transport/BlockMaterialSlope.lean#L59)
- [CellsProofs.Transport.BlockMaterialSlope.inside_concentration_bound](../CellsProofs/Transport/BlockMaterialSlope.lean#L75)

Direct proof subject `cells.channel_block.open_channel_block_weighted_modes@1`

Proof sources [Mathlib real exponential derivative, imported for voltage-dependent dissociation](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/ExpDeriv.lean#L248-L249) · [Mathlib finite sum derivative, imported for the mode mixture](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Add.lean#L188-L192) · [Mathlib finite-sum triangle inequality, specialized to the blocker slope](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/Order/BigOperators/Group/Finset.lean#L234-L239) · [Mathlib product derivative, imported for the full current bound](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Mul.lean#L200-L204) · [Cells single-site occupancy, imported and specialized locally](https://github.com/Eidosoma/Cells/blob/fef8a0d868ac22d0a596f2fd2743ce31d7c12567/lean/CellsProofs/Chemistry/SingleSiteBinding.lean#L17) · [Mathlib real-log derivative, imported for signed reversal sensitivity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Deriv.lean#L47-L49) · [Mathlib chain rule, specialized to the reversal-dependent blocker](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Comp.lean#L237-L241) · [Cells Bernoulli positivity, imported for both free-flux concentration terms](https://github.com/Eidosoma/Cells/blob/dc07534d1f9a2d5c3780837e568726ab91e3707d/lean/CellsProofs/Transport/ProtonLeak.lean#L56-L66)

Uses [One-site binding follows the free ligand concentration](single-site-binding.md) · [Channel opening scales the signed transfer of sodium or potassium](channel-ion-transfer.md)

## Numerical comparison

**Checked.** The compiled CPU float64 clamp passed 6,543 in-range voltage checks across all 18 synthetic blocker cases on f8c6c326. The largest relative errors were 7.77 × 10⁻¹⁵ for the free fraction and 1.13 × 10⁻¹⁴ for the absolute blocker slope against the decimal reference. The largest full-current derivative was 0.989 of its bound or less. A four-mode automatic-differentiation control agreed to 1.90 × 10⁻¹³. All 15 native regression controls passed. On 796f04fa all 6,546 endpoint concentration bounds passed against the separately tagged reference. The smallest bound-to-derivative ratio was 0.9999999999999926 at 10⁻¹² relative tolerance. Both registered faults were detected, including a 192-fold shortfall after omission of the reversal term. A chloride control also passed at 37 voltages.

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `open_channel_block_weighted_modes@1`

[Mode domain and common steepness sign](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/src/cells/definitions/surface_pump_v3_spec.py#L482-L531) · [Native voltage reference, fractions and slope](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/src/cells/laws/channels/open_channel_block.py#L69-L107) · [Native stage values](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/src/cells/models/surface_pump_v3.py#L686-L716) · [Blocked current voltage term](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/src/cells/models/surface_pump_v3.py#L745-L765) · [Compiled clamp over voltage commands](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/validation/fr51/engine.py#L194-L200) · [Synthetic cases and fixed voltage grid](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/validation/fr51/references/spec/cases.json) · [Independent decimal derivatives and mode factors](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/validation/fr51/closed_forms.py#L52-L105) · [Compiled zero-blocker control](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/tests/unit/test_fr51_compiled_ends.py#L26) · [Compiled strong-block control](https://github.com/Eidosoma/Cells/blob/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e/tests/unit/test_fr51_blocked_run.py#L149) · [Weighted blocker bounds](https://github.com/Eidosoma/Cells/blob/fef8a0d868ac22d0a596f2fd2743ce31d7c12567/lean/CellsProofs/Transport/OpenChannelBlock.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/fef8a0d868ac22d0a596f2fd2743ce31d7c12567/lean/checks/weighted_channel_block.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/fef8a0d868ac22d0a596f2fd2743ce31d7c12567/lean/PROGRESS.md#fr51-weighted-block)

[Tested engine f8c6c32665c1](https://github.com/Eidosoma/Cells/commit/f8c6c32665c1ba8c0bcd8b687e4a7f961dc1cc5e) · [Evidence checkpoint fef8a0d868ac](https://github.com/Eidosoma/Cells/commit/fef8a0d868ac22d0a596f2fd2743ce31d7c12567)

**Engine** `resolved_pump_tissue@3`, `resolved_pump_composite@1`, `open_channel_block_weighted_modes@1`

[Signed reversal and weighted blocker](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/src/cells/laws/channels/open_channel_block.py#L69-L107) · [Native stable Bernoulli evaluator](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/src/cells/laws/electrochemistry.py#L17-L24) · [Concentration terms at both membrane endpoints](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/src/cells/models/surface_pump_v3.py#L732-L792) · [Material rate per endpoint volume](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/src/cells/models/surface_pump_v3.py#L795-L824) · [Clamped outward flux and terms](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/src/cells/models/surface_pump_v3.py#L848-L904) · [Compiled case entry point](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/validation/fr51/engine.py#L194-L199) · [Declared synthetic cases](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/validation/fr51/references/spec/cases.json) · [Independent reference result reader](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/validation/fr51/judge.py#L86-L174) · [Registered comparison tolerance](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/validation/fr51/judge.py#L187-L191) · [Registered material-bound check](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/validation/fr51/judge.py#L231-L235) · [Omitted material term and stale reversal controls](https://github.com/Eidosoma/Cells/blob/796f04fad35ce2bc80f256024dc01b44cc9b705b/validation/fr51/plants.py#L174-L197) · [Exact concentration derivatives and bounds](https://github.com/Eidosoma/Cells/blob/dc07534d1f9a2d5c3780837e568726ab91e3707d/lean/CellsProofs/Transport/BlockMaterialSlope.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/dc07534d1f9a2d5c3780837e568726ab91e3707d/lean/checks/block_concentration.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/dc07534d1f9a2d5c3780837e568726ab91e3707d/lean/PROGRESS.md#fr51-concentration-bounds)

[Tested engine 796f04fad35c](https://github.com/Eidosoma/Cells/commit/796f04fad35ce2bc80f256024dc01b44cc9b705b) · [Evidence checkpoint dc07534d1f9a](https://github.com/Eidosoma/Cells/commit/dc07534d1f9a2d5c3780837e568726ab91e3707d)

## Biological evidence

**Open.** Change with voltage in the fraction of sodium current or permeability retained under external acidification. The nodal studies support the direction. The ventricular recordings cover a different voltage range. The exact derivative and transfer of mode parameters remain open.

- [Depolarization relieves extracellular proton block of nodal sodium current.](../WET_LAB_EVIDENCE.md#pair-nodal-sodium-proton-block-relief) · Supported by both studies

**Unit** relative sodium current or permeability at fixed voltage

### woodhull1973-nodal-protons

Voltage-clamped frog nodes of Ranvier. The study estimated sodium permeability from peak current. Fig. 4A and the summary, external pH 7 and 5. [Woodhull (1973), Fig. 4A](https://doi.org/10.1085/jgp.61.6.687)

- **Evidence role** descriptive

The two reductions are rounded examples. No pointwise uncertainty accompanies them in the summary. The +180 mV command is outside the native channel range.

Bath acidification reduced estimated permeability by about 60% at +20 mV and 20% at +180 mV. Block was relieved by stronger depolarization. [Dataset manifest](../checks/data/nodal_proton_block.json) · [Comparison verdict](../PROGRESS.md#fr51-weighted-block)

### mozhayeva1984-nodal-protons

A separate group voltage-clamped nodal membranes at normal external pH and at pH 4.8–4.9. Instantaneous currents addressed open-channel block during acidification. Primary abstract, instantaneous nodal sodium-current measurements. [Mozhayeva, Naumov and Nosyreva (1984)](https://pubmed.ncbi.nlm.nih.gov/6087908/)

- **Evidence role** descriptive

The abstract reports the direction. Pointwise responses, uncertainties and a common voltage interval were unavailable for this comparison.

Proton block decreased as membrane voltage became more positive. A shared numerical slope has yet to be tested. [Dataset manifest](../checks/data/nodal_proton_block.json) · [Comparison verdict](../PROGRESS.md#fr51-weighted-block)

### zhang1991-cardiac-protons

Native guinea-pig ventricular sodium channels, with extracellular pH 5.5 compared with 7.4. This assay measured unitary current amplitude. Fig. 3B and the single-channel amplitude analysis over −70 to −20 mV. [Zhang and Siegelbaum (1991), Fig. 3B](https://doi.org/10.1085/jgp.98.6.1065)

- **Evidence role** descriptive

This tissue, command interval and unitary-current readout differ from the nodal experiments. A zero slope cannot be inferred from an unresolved voltage effect.

Acid reduced unitary amplitude. The study found no significant voltage dependence of that reduction over its tested range, limiting extrapolation of the nodal result. [Dataset manifest](../checks/data/nodal_proton_block.json) · [Comparison verdict](../PROGRESS.md#fr51-weighted-block)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
