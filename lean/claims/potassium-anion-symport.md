<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Potassium–anion cotransport follows the concentration products in a closed pair

The active 1:1 route moves outward when the inside concentration product is larger, stalls at equality and dissipates nonnegative heat. Equal amounts of the two ions move together. With equal fixed volumes, the exact trajectory approaches equilibrium monotonically. An explicit ARS(2,2,2) step can move in the opposite direction if it is too large for the closed pair.

## Assumptions

- Potassium has valence +1 and its partner −1. Concentrations and temperature are positive. The rate scale is capacity times availability times the exponential volume factor. Strict direction and stall require a positive scale.
- The closed-pair trajectory assumes one route, equal fixed finite volumes, constant availability and no other transfers. The explicit stage calculation uses the ARS(2,2,2) order condition. All formal operations are in real arithmetic.

## Lean proof

**Proved**

- [CellsProofs.Transport.PotassiumAnionSymport.fractional_volume_response](../CellsProofs/Transport/PotassiumAnionSymport.lean#L20)
- [CellsProofs.Transport.PotassiumAnionSymport.outward_iff](../CellsProofs/Transport/PotassiumAnionSymport.lean#L31)
- [CellsProofs.Transport.PotassiumAnionSymport.stall_iff](../CellsProofs/Transport/PotassiumAnionSymport.lean#L35)
- [CellsProofs.Transport.PotassiumAnionSymport.normalized_reversal](../CellsProofs/Transport/PotassiumAnionSymport.lean#L41)
- [CellsProofs.Transport.PotassiumAnionSymport.electrochemical_sum](../CellsProofs/Transport/PotassiumAnionSymport.lean#L51)
- [CellsProofs.Transport.PotassiumAnionSymport.heat_nonneg](../CellsProofs/Transport/PotassiumAnionSymport.lean#L60)
- [CellsProofs.Transport.PotassiumAnionSymport.pair_inventories](../CellsProofs/Transport/PotassiumAnionSymport.lean#L73)
- [CellsProofs.Transport.PotassiumAnionSymport.finite_volume_drive](../CellsProofs/Transport/PotassiumAnionSymport.lean#L80)
- [CellsProofs.Transport.PotassiumAnionSymport.equal_volume_drive](../CellsProofs/Transport/PotassiumAnionSymport.lean#L87)
- [CellsProofs.Transport.PotassiumAnionSymport.change_initial](../CellsProofs/Transport/PotassiumAnionSymport.lean#L97)
- [CellsProofs.Transport.PotassiumAnionSymport.change_outward](../CellsProofs/Transport/PotassiumAnionSymport.lean#L100)
- [CellsProofs.Transport.PotassiumAnionSymport.change_solves_rate](../CellsProofs/Transport/PotassiumAnionSymport.lean#L105)
- [CellsProofs.Transport.PotassiumAnionSymport.explicit_step](../CellsProofs/Transport/PotassiumAnionSymport.lean#L116)
- [CellsProofs.Transport.PotassiumAnionSymport.step_points_inward](../CellsProofs/Transport/PotassiumAnionSymport.lean#L123)

Direct proof subject `cells.operator.k_anion_symport_mass_action@1`

## Numerical comparison

**Checked.** After the product-ratio fix, both extreme concentration cases gave finite affinity and heat matching the independent references. At 2⁻⁵¹⁰ mM outside they were 1,836,599.47 J/mol and 4,701.69 pJ/s. All 27 ordinary controls passed. With fixed and moving water, the original 10 ms step was refused and the 32- and 64-step refinements passed. The previous failed cases remain in the earlier checkpoints.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.k_anion_symport_mass_action@1`

[Product ratio and fallback at extreme concentrations](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/laws/routes/k_anion_symport.py#L75) · [Affinity, cycles and dissipation](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/laws/routes/k_anion_symport.py#L123) · [Tissue step admission](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/k_anion_symport.py#L252) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/potassium_anion_symport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#potassium-affinity-repair)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.ideal_osmosis_linear_compliance_water@1`, `cells.k_anion_symport_mass_action@1`

[Coupled water half-step](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/osmotic_water.py#L213) · [Potassium–anion route bound](https://github.com/Eidosoma/Cells/blob/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93/src/cells/operators/k_anion_symport.py#L152) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/checks/osmotic_water.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d906702344fec456f231db786b5771a187998d9/lean/PROGRESS.md#potassium-affinity-repair)

[Tested engine 5fa7a8b88de7](https://github.com/Eidosoma/Cells/commit/5fa7a8b88de7a3cc65ef3b975e7bc3c1a374da93) · [Evidence checkpoint 1d906702344f](https://github.com/Eidosoma/Cells/commit/1d906702344fec456f231db786b5771a187998d9)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `k_anion_symport_mass_action@1`

[Concentration products and chemical affinity](https://github.com/Eidosoma/Cells/blob/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc/src/cells/laws/routes/k_anion_symport.py#L66) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/checks/potassium_anion_symport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b4353f85b18d489a277818bfe43e20c8416b6066/lean/PROGRESS.md#six-numerical-retests)

[Tested engine b9d6452dff1c](https://github.com/Eidosoma/Cells/commit/b9d6452dff1cd0a1d5d3664e0a81b00ce988bfbc) · [Evidence checkpoint b4353f85b18d](https://github.com/Eidosoma/Cells/commit/b4353f85b18d489a277818bfe43e20c8416b6066)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `k_anion_symport_mass_action@1`

[Finite outside and shared-node step bound](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/k_anion_symport.py#L173) · [Step admission](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/k_anion_symport.py#L286) · [Concentration-product affinity](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/laws/routes/k_anion_symport.py#L66) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743/lean/checks/potassium_anion_symport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743/lean/PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

[Tested engine 93fc8c2cd217](https://github.com/Eidosoma/Cells/commit/93fc8c2cd217dbac9c2f6381d201f5acdb020265) · [Evidence checkpoint ec0c89db3342](https://github.com/Eidosoma/Cells/commit/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `ideal_osmosis_linear_compliance_water@1`, `k_anion_symport_mass_action@1`

[Water potential, flow and heat](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/numerics/osmotic_water.py#L193) · [Start-of-half-step rate bound](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/osmotic_water.py#L148) · [Heun predictor and corrector](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/osmotic_water.py#L211) · [Finite and held-bath water ledgers](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/osmotic_water.py#L255) · [Independent held-bath trajectory](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/tests/unit/test_surface_pump_water.py#L214) · [Cotransporter step bound](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/k_anion_symport.py#L173) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743/lean/checks/osmotic_water.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743/lean/PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

[Tested engine 93fc8c2cd217](https://github.com/Eidosoma/Cells/commit/93fc8c2cd217dbac9c2f6381d201f5acdb020265) · [Evidence checkpoint ec0c89db3342](https://github.com/Eidosoma/Cells/commit/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `k_anion_symport_mass_action@1`

[Cycles, affinity and heat](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/laws/routes/k_anion_symport.py#L66) · [Component domain](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/laws/routes/k_anion_symport.py#L89) · [Equal flux in the two ion rows](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L92) · [Route rate used for the step bound](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L152) · [Step admission](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L252) · [Explicit tableau](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/numerics/surface_imex.py#L52) · [Applied transfer and heat](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/models/surface_pump_v3.py#L1436) · [Cycle and heat booking](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L297) · [One-cell validation fixture](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/validation/tissue/pump_water_fixtures.py#L177) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7cc89e34c5f761a9ca801a34ab423e1cc6629746/lean/checks/potassium_anion_symport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7cc89e34c5f761a9ca801a34ab423e1cc6629746/lean/PROGRESS.md#19-november-2026--potassium-and-anion-cotransport)

[Tested engine d6532edeb1bb](https://github.com/Eidosoma/Cells/commit/d6532edeb1bb06127ddf398adb23ab41b2f396c7) · [Evidence checkpoint 7cc89e34c5f7](https://github.com/Eidosoma/Cells/commit/7cc89e34c5f761a9ca801a34ab423e1cc6629746)

## Biological evidence

**Open.** External cation concentration at reversal normalized by internal potassium, plotted against the inside/outside chloride ratio.

- [Changing external potassium can reverse the direction of K–Cl cotransport.](../WET_LAB_EVIDENCE.md#pair-kcl-gradient-reverses-transport) · Supported by both studies
- [Equality of the nominal intracellular and extracellular K–Cl concentration products locates zero flux in swollen sheep erythrocytes across protocols.](../WET_LAB_EVIDENCE.md#pair-kcl-null-across-sheep-protocols) · Independent replication unconfirmed
- [The red-cell K–Cl cotransporter carries approximately one potassium ion per chloride ion.](../WET_LAB_EVIDENCE.md#pair-erythrocyte-kcl-stoichiometry) · Supported by both studies
- [Chloride contributes to the direction of volume-sensitive erythrocyte K–Cl cotransport.](../WET_LAB_EVIDENCE.md#pair-erythrocyte-kcl-combined-gradient) · Supported by both studies

Rabbit red cells gave an outward K:Cl flux ratio of 1.12 ± 0.26 (SD, five preparations), consistent with the model’s 1:1 stoichiometry. The investigators measured rubidium as a potassium tracer and calibrated its relative flux. [Jennings and Adame, Fig. 5](https://pubmed.ncbi.nlm.nih.gov/11502559/)

**Unit** dimensionless normalized reversal slope

### jarolimek1999_dendritic_chloride_reversal@1

Dendrites of cultured rat midbrain neurons. The furosemide-induced shift in GABA-current reversal was measured at two external K⁺ concentrations. Fig. 6B and adjoining low-pipette-anion results. [Jarolimek et al. (1999), Fig. 6B](https://doi.org/10.1523/JNEUROSCI.19-12-04695.1999)

- **Evidence role** descriptive

Values are mean ± SEM. Pipette permeant anion and local free chloride activity are distinct. Transport direction is inferred from the blocker-sensitive voltage shift.

The opposite dendritic voltage responses support a reversal in K–Cl transport direction as external K⁺ rises. No absolute K–Cl flux or independently measured product of activities at zero transport is available. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-transport-and-membrane-measurements)

### delpire1991_sheep_kcl_flux_null@1

Hyposmotically swollen low-K sheep red cells. Net K flux was compared across concentrations and temperatures. Abstract and results on net potassium efflux at equal and reversed concentration products. [Delpire and Lauf (1991), net-flux results](https://doi.org/10.1085/jgp.97.2.173)

- **Evidence role** descriptive

Approximate concentration-product ratio reported by the authors. The exact zero and an uncertainty were not reported for this summary.

Net efflux persisted at equal concentration products and approached zero near twice the internal product. Lauf’s later pH- and volume-clamped study tested this discrepancy with a different protocol. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-transport-and-membrane-measurements)

### jennings2001_rabbit_kcl_flux@1

N-ethylmaleimide-stimulated rabbit erythrocytes. The sulfate bath and anion-exchanger inhibition allowed comparison of K and Cl efflux. Fig. 5 and accompanying K:Cl outward-flux ratio results. [Jennings and Adame (2001), Fig. 5](https://doi.org/10.1152/ajpcell.2001.281.3.C825)

- **Evidence role** descriptive

Mean ± SD over five experiments. The two ionic fluxes define a stoichiometric ratio away from the null.

The independently measured outward K:Cl flux ratio of 1.12 ± 0.26 is compatible with 1:1 coupling in this preparation. Its zero-flux concentration product was not measured. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-transport-and-membrane-measurements)

### lauf1996_sheep_kcc_reversal@1

Low-potassium sheep red cells with pH and volume clamped. The assay compared outward K and inward Rb flux after chloride-minus-nitrate subtraction. Figures 5–7 estimate the reversal point from zero net flux. Figure 8 fits normalized reversal against the chloride ratio. [Lauf and Adragna (1996), Fig. 8](https://doi.org/10.1085/jgp.108.4.341)

- **Evidence role** descriptive
- **Evaluation** Normal and low internal magnesium

Eight points contributed to the normal-magnesium fit and ten to the low-magnesium fit. The paper gives correlations of 0.912 and 0.976. It gives no uncertainty for either slope.

The ideal product rule predicts a slope of 1. The measured slopes were 1.12 at normal magnesium and 1.08 at low magnesium. Rubidium substitutes for external potassium. The volume dependence of net flux remains open. [Dataset manifest](../checks/data/lauf1996_kcc_reversal.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--potassium-and-anion-cotransport)

### brugnara1989_human_kcl

Volume-sensitive transport in human red cells. Permeant substitute anions stabilized membrane potential while anion exchange was inhibited. Net K flux under opposed gradients, pp. C994–C1003. [Brugnara, Van Ha and Tosteson (1989)](https://doi.org/10.1152/ajpcell.1989.256.5.C994)

- **Evidence role** descriptive

The direction is reported directly. A matched sweep of internal and external activities through a measured zero is unavailable here.

An outward chloride gradient drove net K efflux against the K gradient. This constrains the direction under combined ion gradients. [Dataset manifest](../checks/data/paired_preparation_controls.json) · [Comparison verdict](../PROGRESS.md#preparation-evidence-review)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
