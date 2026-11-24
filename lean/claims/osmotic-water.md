<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Water potential sets flow, heat and osmometric equilibrium

Water moves down the hydrostatic-minus-osmotic pressure difference. At frozen solute amounts this potential is the volume derivative of free energy after unit conversion. Dissipated heat is nonnegative. An outward potassium–anion cycle increases the outward water drive by moving two osmoles across the membrane.

## Assumptions

- All volumes and temperature are positive. Osmoles are ideal, elastic pressure is linear in volume, and mobility and stiffness are nonnegative. Each held bath has fixed pressure and concentrations.
- The Heun direction result applies to one finite edge at frozen amounts. Both positive predictor volumes are at least one quarter of their respective start volumes, and the full-step mobility times the sum of the initial pressure slopes is at most 0.05.
- The equilibrium comparisons use positive mobility. The vesicle fit uses a common effective modulus across two small swelling conditions. The ideal red-cell comparison uses aqueous volume and a separate inactive-volume estimate for each preparation.

## Lean proof

**Proved**

- [CellsProofs.Transport.OsmoticWater.declared_potential](../CellsProofs/Transport/OsmoticWater.lean#L23)
- [CellsProofs.Transport.OsmoticWater.energy_has_deriv](../CellsProofs/Transport/OsmoticWater.lean#L35)
- [CellsProofs.Transport.OsmoticWater.endpoint_ledger](../CellsProofs/Transport/OsmoticWater.lean#L46)
- [CellsProofs.Transport.OsmoticWater.potential_has_deriv](../CellsProofs/Transport/OsmoticWater.lean#L56)
- [CellsProofs.Transport.OsmoticWater.potential_change](../CellsProofs/Transport/OsmoticWater.lean#L63)
- [CellsProofs.Transport.OsmoticWater.pressure_step_flow](../CellsProofs/Transport/OsmoticWater.lean#L73)
- [CellsProofs.Transport.OsmoticWater.edge_power](../CellsProofs/Transport/OsmoticWater.lean#L80)
- [CellsProofs.Transport.OsmoticWater.heat_nonneg](../CellsProofs/Transport/OsmoticWater.lean#L87)
- [CellsProofs.Transport.OsmoticWater.heun_transfer](../CellsProofs/Transport/OsmoticWater.lean#L94)
- [CellsProofs.Transport.OsmoticWater.heun_direction](../CellsProofs/Transport/OsmoticWater.lean#L110)
- [CellsProofs.Transport.OsmoticWater.secant_bound](../CellsProofs/Transport/OsmoticWater.lean#L122)
- [CellsProofs.Transport.OsmoticWater.guarded_heun_direction](../CellsProofs/Transport/OsmoticWater.lean#L134)
- [CellsProofs.Transport.OsmoticWater.compliant_bath_stall](../CellsProofs/Transport/OsmoticWater.lean#L150)
- [CellsProofs.Transport.OsmoticWater.ideal_bath_stall](../CellsProofs/Transport/OsmoticWater.lean#L162)
- [CellsProofs.Transport.OsmoticWater.symport_drive_change](../CellsProofs/Transport/OsmoticWater.lean#L176)

Direct proof subject `cells.ideal_osmosis_linear_compliance_water@1`

## Numerical comparison

**Checked.** Five accepted CPU float64 runs tested water alone and water coupled to potassium–anion transport. Halving the step in two coupled worlds reduced the errors in both transfers and both heats by factors of 4.00–4.11 against an independent two-extent calculation. Separate oversized water and cotransport inputs triggered their respective step bounds.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `ideal_osmosis_linear_compliance_water@1`, `k_anion_symport_mass_action@1`

[Water potential, flow and heat](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/numerics/osmotic_water.py#L193) · [Start-of-half-step rate bound](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/osmotic_water.py#L148) · [Heun predictor and corrector](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/osmotic_water.py#L211) · [Finite and held-bath water ledgers](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/osmotic_water.py#L255) · [Independent held-bath trajectory](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/tests/unit/test_surface_pump_water.py#L214) · [Cotransporter step bound](https://github.com/Eidosoma/Cells/blob/93fc8c2cd217dbac9c2f6381d201f5acdb020265/src/cells/operators/k_anion_symport.py#L173) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743/lean/checks/osmotic_water.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743/lean/PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

[Tested engine 93fc8c2cd217](https://github.com/Eidosoma/Cells/commit/93fc8c2cd217dbac9c2f6381d201f5acdb020265) · [Evidence checkpoint ec0c89db3342](https://github.com/Eidosoma/Cells/commit/ec0c89db3342a07a8b4cfc4f48bd598b0bb77743)

## Biological evidence

**Open.** Equilibrium swelling in vesicles and red cells, water flow after pressure steps in a Chara internode, and the water change accompanying net solute movement in trout red cells. A pathway-specific rate for K–anion cotransport during swelling remains open.

- [A hyperosmotic external bath draws water out of protein-free phospholipid vesicles.](../WET_LAB_EVIDENCE.md#pair-hypertonic-water-efflux) · Supported by both studies

**Unit** % swelling, fL cell volume, nL/s inward flow, g water per g dry cell solids

### mathai2008_osmotic_water@1

Protein-free vesicles under a 50% increase in external osmotic pressure, 30 °C. Entrapped dye self-quenching reported volume loss. Fig. 1A, Table I and water-permeability methods. [Mathai et al. (2008), Fig. 1A and Table I](https://doi.org/10.1085/jgp.200709848)

- **Evidence role** descriptive

8–12 traces averaged for a fluorescence curve. The Table I ± convention is unspecified here.

The hyperosmotic bath induced water efflux. DOPC and POPC water permeability were 15.8 ± 0.58 and 13.0 ± 0.44 in units of 10⁻³ cm/s at 30 °C. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### frallicciardi2022_osmotic_water@1

Lipid vesicles under an external osmotic upshift, 20 °C. Only stopped-flow fluorescence data are used. Fig. 1A and experimental panels 3A and 4A. [Frallicciardi et al. (2022), Figs. 1A, 3A and 4A](https://doi.org/10.1038/s41467-022-29272-x)

- **Evidence role** descriptive

Figures report SEM. Methods propagate uncertainty in vesicle size distributions. Individual repeated size determinations do not establish independent preparations.

The hyperosmotic stopped-flow experiment detected shrinkage. DOPC and POPC water permeability were 16.0 ± 1.7 and 12.0 ± 1.4 in units of 10⁻³ cm/s at 20 °C. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### shibly2016_dopc_swelling@1

DOPC vesicles at 25 ± 1 °C contained 98 mM sucrose and were transferred into glucose solutions. Figure 2B and the adjacent results give the equilibrium volume increments after single-vesicle transfers. [Shibly et al., Fig. 2B](https://doi.org/10.1016/j.bpj.2016.09.043)

- **Evidence role** held out from fitting
- **Fit** 96 mM glucose, 14 vesicles
- **Evaluation** 95 mM glucose, 17 vesicles

The reported ±0.1 percentage point has unspecified statistic. The two concentration steps are nominal.

A stiffness fitted to 1.7% swelling predicted 2.57% on the second bath against 2.6 ± 0.1% measured. [Dataset manifest](../checks/data/shibly2016_swelling.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

### kwant1970_red_cell_osmometry@1

Sealed human red-cell ghosts were sized at 37 °C. Temperature for intact-cell sizing is unspecified. Each calibration uses the study's separate estimate of inactive volume. Table II, 126 mOsm/L ghost series, and Table I, Coulter measurements of intact cells. [Kwant and Seeman, Tables I–II](https://doi.org/10.1085/jgp.55.2.208)

- **Evidence role** held out from fitting
- **Fit** Ghosts at 126 mOsm/L, Intact cells at 333 mOsm/L
- **Evaluation** Ghosts at 132, 143, 163, 184 and 211 mOsm/L, Intact cells at 184 mOsm/L

The volume spreads are reported SDs. The calibration volume, inactive volume and bath osmolarity contribute additional uncertainty to predictions.

At 184 mOsm/L the ideal model predicted 111.4 fL for ghosts (109.0 ± 1.0 measured) and 122.6 fL for intact cells (111.5 ± 1.2 measured). [Dataset manifest](../checks/data/kwant1970_osmometry.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

### wendler1982_chara_pressure@1

A Chara corallina internode in artificial pond water at 23 ± 2 °C re-equilibrated between the two pressure steps. Figure 2A gives the first 40 s slopes of two opposite pressure clamps on cell 12. [Wendler and Zimmermann, Fig. 2A](https://doi.org/10.1104/pp.69.5.998)

- **Evidence role** held out from fitting
- **Fit** −0.370 bar pressure step
- **Evaluation** +0.350 bar pressure step

Individual slope uncertainties are unavailable. The second resting turgor was 0.060 bar lower.

One measured pressure step predicted reversed water flow of 4.82 nL/s outward on the second step. The measured flow was 5.3 nL/s outward. [Dataset manifest](../checks/data/wendler1982_pressure.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

### guizouarn2000_trout_water_solutes@1

Rainbow-trout red cells were held at 215 mOsm/kg with ouabain. Each condition measured changes in cellular water, sodium, potassium, chloride and taurine. Figure 1 and Table 1 give the 60-minute water and solute changes after initial hypotonic swelling. [Guizouarn et al., Table 1](https://doi.org/10.1111/j.1469-7793.2000.t01-1-00147.x)

- **Evidence role** descriptive
- **Evaluation** Sodium bath, n = 21, Potassium bath, n = 3
- **Excluded** Choline bath, total osmole change unavailable

The paper reports SEM. The water prediction uses the measured osmole total. Covariance with measured water is unavailable.

Measured osmole changes imply water changes of −0.375 and +0.078 g/g in two baths, against −0.37 and +0.06 measured. Multiple transport pathways contribute. [Dataset manifest](../checks/data/guizouarn2000_water_solutes.json) · [Comparison verdict](../PROGRESS.md#20-november-2026--osmotic-water-and-potassiumanion-transport)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
