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

Direct proof subject `cells.k_anion_symport_mass_action@1`

## Numerical comparison

**Failed.** All 27 ordinary component cases passed. The closed two-compartment world accepted a 10 ms step and booked 2.141 × 10⁻⁶ fmol inward against an exact 8.669 × 10⁻⁷ fmol outward. The same interval split into 32 or 64 steps gave outward flow. Separately, a component-level extreme concentration ratio produced infinite affinity and heat with finite references.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `k_anion_symport_mass_action@1`

[Cycles, affinity and heat](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/laws/routes/k_anion_symport.py#L66) · [Component domain](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/laws/routes/k_anion_symport.py#L89) · [Equal flux in the two ion rows](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L92) · [Route rate used for the step bound](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L152) · [Step admission](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L252) · [Explicit tableau](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/numerics/surface_imex.py#L52) · [Applied transfer and heat](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/models/surface_pump_v3.py#L1436) · [Cycle and heat booking](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/src/cells/operators/k_anion_symport.py#L297) · [One-cell validation fixture](https://github.com/Eidosoma/Cells/blob/d6532edeb1bb06127ddf398adb23ab41b2f396c7/validation/tissue/pump_water_fixtures.py#L177) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7cc89e34c5f761a9ca801a34ab423e1cc6629746/lean/checks/potassium_anion_symport.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7cc89e34c5f761a9ca801a34ab423e1cc6629746/lean/PROGRESS.md#19-november-2026--potassium-and-anion-cotransport)

[Tested engine d6532edeb1bb](https://github.com/Eidosoma/Cells/commit/d6532edeb1bb06127ddf398adb23ab41b2f396c7) · [Evidence checkpoint 7cc89e34c5f7](https://github.com/Eidosoma/Cells/commit/7cc89e34c5f761a9ca801a34ab423e1cc6629746)

## Biological evidence

**Open.** External cation concentration at reversal normalized by internal potassium, plotted against the inside/outside chloride ratio.

Rabbit red cells gave an outward K:Cl flux ratio of 1.12 ± 0.26 (SD, five preparations), consistent with the model’s 1:1 stoichiometry. The investigators measured rubidium as a potassium tracer and calibrated its relative flux. [Jennings and Adame, Fig. 5](https://pubmed.ncbi.nlm.nih.gov/11502559/)

**Unit** dimensionless normalized reversal slope

### lauf1996_sheep_kcc_reversal@1

Low-potassium sheep red cells with pH and volume clamped. The assay compared outward K and inward Rb flux after chloride-minus-nitrate subtraction. Figures 5–7 estimate the reversal point from zero net flux. Figure 8 fits normalized reversal against the chloride ratio. [Lauf and Adragna (1996), Fig. 8](https://doi.org/10.1085/jgp.108.4.341)

- **Evidence role** descriptive
- **Evaluation** Normal and low internal magnesium

Eight points contributed to the normal-magnesium fit and ten to the low-magnesium fit. The paper gives correlations of 0.912 and 0.976. It gives no uncertainty for either slope.

The ideal product rule predicts a slope of 1. The measured slopes were 1.12 at normal magnesium and 1.08 at low magnesium. Rubidium substitutes for external potassium. The volume dependence of net flux remains open. [Dataset manifest](../checks/data/lauf1996_kcc_reversal.json) · [Comparison verdict](../PROGRESS.md#19-november-2026--potassium-and-anion-cotransport)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
