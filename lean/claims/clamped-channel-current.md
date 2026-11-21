<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A fixed-gate current curve identifies the product of channel abundance and availability

At a declared voltage, the population’s outward electrical current is its outward permeant-ion flux times the signed charge per fmol. With fixed stored gates and known drive, two abundance and availability pairs give the same current at every sampled voltage exactly when their products agree, provided at least one voltage gives a nonzero response at unit abundance and availability.

## Assumptions

- The channel conducts one declared ion. The charge, concentrations, temperature, area and permeability defining its single-population drive are known and shared across the two preparations.
- The readout uses the stored gates. Abundance is proportional to surface count at fixed patch area and reference density. At reversal or with closed gates, a zero signal alone cannot determine the product.

## Lean proof

**Proved**

- [CellsProofs.Transport.IonChannels.clamped_current_from_species](../CellsProofs/Transport/IonChannels.lean#L226)
- [CellsProofs.Transport.IonChannels.clamped_current_factors](../CellsProofs/Transport/IonChannels.lean#L238)
- [CellsProofs.Transport.IonChannels.same_clamped_curve_iff](../CellsProofs/Transport/IonChannels.lean#L249)

Proof sources [Mathlib Finset.sum_eq_single_of_mem, the additive theorem used in the standard build](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L302-L310) · [ATOMS Lab base current, time and amount, imported in the optional units check](https://github.com/ATOMSLab/LeanDimensionalAnalysis/blob/de263eed945693058ef2b8a1fa56c2ec5642ea7a/DimensionalAnalysis/Dimensions.lean#L12-L17) · [Cells specialization for a Faraday conversion times molar flux](../checks/units/FacePower.lean#L31)

Uses [Channel opening scales the signed transfer of sodium or potassium](channel-ion-transfer.md) · [Chloride gradients set leak reversal and inward chloride carries positive outward current](chloride-channel-charge.md) · [An empty surface population has zero abundance and channel flow](empty-surface-flow.md)

## Numerical comparison

**Checked.** On the tissue host, 11 active populations on two patches agreed with the 70-digit reference within 1.30 × 10⁻²⁶ A. Halving abundance or availability halved current exactly. Full block, off-ion fluxes and padding gave zero. The composite replay at −50 mV gave 0.592416 pA with the raw control and 0.296208 pA with its effective 0.5 control. The public composite clamp remains unavailable at this revision.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`, `kv1p1_mh2@1`, `kv1p2_mh@1`, `kv1p3_mh@1`, `kv1p4_mh@1`, `kv1p5_mh@1`, `kv1p6_mh@1`, `kir2p1_mh2@1`, `nav1p2_m3h_regularized@1`, `kleak_always_open@1`, `naleak_always_open@1`, `clleak_always_open@1`

**Operators** `cells.species_regulated_availability@1`

[Tissue clamp](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/models/surface_pump_v3.py#L415) · [Composite control view](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/models/pump_composite.py#L1510) · [Held controls in ordinary observations](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/src/cells/models/pump_composite.py#L2183) · [Composite fixture](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/tissue/regulated_availability_fixtures.py) · [Tissue regression](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/tests/unit/test_surface_pump_v3_populations.py#L165) · [Reference flux](https://github.com/Eidosoma/Cells/blob/68ab12e7f57552fa551b103df1393a1e095cd001/validation/betse/junction_transport/check.py) · [Native channel reference coefficients](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/ion_channels.py) · [Conducting fractions used in the host control](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/data/maverick2022_kv_density.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/checks/clamped_channel_current.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/be54fafbff162065063b215d4ac3e6adaf534e3a/lean/PROGRESS.md#main-review-d264-d266)

[Tested engine 68ab12e7f575](https://github.com/Eidosoma/Cells/commit/68ab12e7f57552fa551b103df1393a1e095cd001) · [Evidence checkpoint be54fafbff16](https://github.com/Eidosoma/Cells/commit/be54fafbff162065063b215d4ac3e6adaf534e3a)

**Engine** `resolved_pump_tissue@3`, `kv1p1_mh2@1`, `kv1p2_mh@1`, `kv1p3_mh@1`, `kv1p4_mh@1`, `kv1p5_mh@1`, `kv1p6_mh@1`, `kir2p1_mh2@1`, `nav1p2_m3h_regularized@1`, `kleak_always_open@1`, `naleak_always_open@1`, `clleak_always_open@1`

[Declared-voltage readout and signed current](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/models/surface_pump_v3.py#L405) · [Per-population gate and abundance in the flux](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/models/surface_pump_v3.py#L370) · [Selective constant-field transfer](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/laws/junctions/selective.py#L19) · [Faraday and fmol conversion](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/src/cells/laws/electrochemistry.py#L10) · [Independent 70-digit constant-field reference](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/validation/betse/junction_transport/check.py#L10) · [Channel opening powers used by the reference](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/lean/checks/ion_channels.py#L24) · [Chloride specimen](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/tests/unit/test_chloride_leak_law.py#L37) · [Routed availability and native-voltage regression](https://github.com/Eidosoma/Cells/blob/1b8017d13755bed2ee9be09375c998e364a4ca62/tests/unit/test_surface_pump_v3_populations.py#L165) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/13302130c8198319ae57b7419f97d60cefd0555d/lean/checks/clamped_channel_current.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/13302130c8198319ae57b7419f97d60cefd0555d/lean/PROGRESS.md#fr34-clamped-current)

[Tested engine 1b8017d13755](https://github.com/Eidosoma/Cells/commit/1b8017d13755bed2ee9be09375c998e364a4ca62) · [Evidence checkpoint 13302130c819](https://github.com/Eidosoma/Cells/commit/13302130c8198319ae57b7419f97d60cefd0555d)

## Biological evidence

**Open.** A matched signed current at a declared voltage with independent measurements of channel abundance, the fraction available to conduct, stored gate state and unitary drive.

**Unit** conducting fraction

### maverick2022_kv_density

Tagged Kv channels in HEK293 cells at room temperature. Channel estimates use gating charge, fluorescence calibration, ionic slope conductance near reversal and current fluctuations. Fig. 8B reports the group means. Fig. 8C, p. 766, orange triangles, gives the density series for Kv1.5. [Maverick and Tamkun (2022), Fig. 8B–C](https://doi.org/10.1016/j.bpj.2022.01.021)

- **Evidence role** descriptive
- **Observed** 0.18 conducting fraction

The two Kv1.5 endpoints are approximate readings of a three-cell moving average near 115 and 425 gating channels/µm². No endpoint uncertainties are given. Group means were 0.96 ± 0.05 for Kv1.4 and 0.26 ± 0.01 for Kv1.5 (SEM).

A conducting fraction held at the low-density value would predict 0.34 at the high-density endpoint, where the figure gives about 0.18. Density changes across cells. The measured fractions constrain an availability model across densities. A matched test of absolute instantaneous current remains open. [Dataset manifest](../checks/data/maverick2022_kv_density.json) · [Comparison verdict](../PROGRESS.md#fr34-clamped-current)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
