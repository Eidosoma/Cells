# Cells proof comparisons

## 20 November 2026 · Osmotic water and potassium–anion transport

**The earlier wrong-direction step is now refused.** On engine revision `93fc8c2cd217dbac9c2f6381d201f5acdb020265`, the original 10 ms fixed-volume reproducer gave a potassium–anion step bound of 3.761 against the limit of 1. The same step with water enabled was also refused by the cotransporter. The earlier bound was 0.221. The 32- and 64-step controls completed in both worlds. The separate component check still produced infinite affinity and heat at the extreme 2⁻⁵¹⁰ mM input, with finite 60-digit reference values. [Original comparison](#19-november-2026--potassium-and-anion-cotransport) · [Current finite-outside bound and its scope](../src/cells/operators/k_anion_symport.py#L173) · [Fixed-volume reproducer](checks/potassium_anion_symport.py)

**Water proofs.** At fixed solute amounts, differentiating the mixing and elastic free energy in pJ with respect to volume in pL gives the water potential in Pa divided by 1,000. Its pressure slope is K/Vref + RT N/V². The outward flow dissipates nonnegative heat, and for a held bath the remaining energy rate equals its supplied-water work. For one finite membrane, the Lean proof gives the exact Heun transfer using the pressure changes between the starting and predictor volumes. If the initial volume at each end is at most four times its positive predictor volume, the engine's 0.05 relaxation bound preserves the initial flow direction over that half-step. The default 0.5–2 Vref window satisfies this condition. The proof also gives the osmometric equilibrium and the effect of one outward 1:1 cotransport cycle on the two osmotic pressures. These 15 theorems use the standard Lean axioms. [Proofs](CellsProofs/Transport/OsmoticWater.lean) · [Water step](../src/cells/operators/osmotic_water.py#L211) · [Endpoint ledgers](../src/cells/operators/osmotic_water.py#L255)

**Changing-volume comparison.** The CPU float64 runner for `resolved_pump_composite@1` used its `resolved_pump_tissue@3` inner model, one finite cell, one finite outside compartment, and the water and K–anion operators. An independent ODE advances two signed transfers. Each outward cycle removes two cell osmoles and adds two outside. Water changes both concentrations and the carrier's activation. DOP853 and Radau agreed to 5 × 10⁻¹⁰ relative plus 5 × 10⁻¹⁵ absolute for the two transfers and two heats. Halving the engine step reduced the errors in all four quantities by factors of 4.00–4.11. [Driver and inputs](checks/osmotic_water.py) · [Water rate](../src/cells/operators/osmotic_water.py#L148) · [Carrier rate](../src/cells/laws/routes/k_anion_symport.py#L66)

| Case | Steps and elapsed time | Engine / reference outward water (pL) | Engine / reference outward K–anion cycles (fmol) |
| --- | --- | ---: | ---: |
| Ordinary pair | 32 over 200 ms | −0.006454647 / −0.006454635 | 0.7260321 / 0.7260354 |
| Near carrier stall | 64 over 10 ms | 0.0002123253952 / 0.0002123253953 | 0.00007233328 / 0.00007235229 |
| Water alone | 32 over 200 ms | −0.006870671 / −0.006870672 | 0 / 0 |

All five accepted runs preserved the two ion inventories and charge to the reported global precision. The largest global water residual was 2.17 × 10⁻¹⁹ pL. A separate water-only input gave dt × water rate = 0.0870 and was refused against the 0.05 limit. The coupled check took 32 s on four CPU cores. The 56 water tests, 10 cotransport tests and 82 repository guard tests passed. Before and after test discovery recorded identical sets of 20,555 test IDs and the same five collection errors from unavailable archived run inputs. [Water component tests](../tests/unit/test_osmotic_water.py) · [Held-bath osmometer and ledger tests](../tests/unit/test_surface_pump_water.py#L199)

**Biological measurements from Search.** These are retrospective comparisons. Each row below uses its own calibration. The two equilibrium studies probe the water potential, while a pressure clamp probes the initial flow. [Reproduce the comparisons](checks/osmometry.py)

| Preparation and calibration | Measurement held out from calibration | Cells prediction |
| --- | --- | --- |
| DOPC vesicles, 25 ± 1 °C. The 1.7% swelling at 96 mM external glucose sets an effective K of 52.8 kPa. | 2.6 ± 0.1% swelling at 95 mM (17 vesicles) | 2.568%. Zero stiffness gives 3.158%. The paper leaves the statistic for ±0.1 unspecified. [Shibly et al., Fig. 2B](https://doi.org/10.1016/j.bpj.2016.09.043) · [Inputs](checks/data/shibly2016_swelling.json) |
| Resealed human red-cell ghosts, 37 °C. The 126 mOsm/L measurement and 1.5 fL inactive volume set 20.223 fmol of trapped osmoles. | 109.0 ± 1.0 fL at 184 mOsm/L and 95.2 ± 0.9 fL at 211 mOsm/L (SD) | 111.41 and 97.34 fL. The ideal law overpredicted each of the five held-out means by 0.70–2.41 fL. [Kwant and Seeman, Table II](https://doi.org/10.1085/jgp.55.2.208) · [Inputs](checks/data/kwant1970_osmometry.json) |
| Intact human red cells, 33 fL inactive volume and a separate 333 mOsm/L calibration. | 111.5 ± 1.2 fL at 184 mOsm/L (SD) | 122.58 fL. The zero-stiffness ideal-water model overpredicted swelling here by 11.08 fL. [Kwant and Seeman, Table I](https://doi.org/10.1085/jgp.55.2.208) |
| One *Chara* internode, 23 ± 2 °C. A −0.370 bar step and +5.1 nL/s inward flow set the conductance. | −5.3 nL/s inward after a +0.350 bar step | −4.82 nL/s. The second baseline was 0.060 bar lower. The individual slope uncertainties are unavailable. [Wendler and Zimmermann, Fig. 2A](https://doi.org/10.1104/pp.69.5.998) · [Inputs](checks/data/wendler1982_pressure.json) |

The vesicle fit applies to small strains over this concentration interval. The intact-cell volume discrepancy leaves room for mechanics, nonideal solutes and uncertainty in inactive volume.

**Paired water and solute measurements.** Search also identified trout red cells with measured water, K, Cl, Na and taurine content from the initial swelling to 60 min in a 215 mOsm/kg bath. Dividing the reported change in total osmoles by the bath osmolality reproduces the authors' conditional ideal-water calculation. The sodium bath gives −0.375 g water per g dry cell solids, against −0.37 ± 0.02 measured (21 experiments, SEM). Replacing external sodium with potassium gives +0.078 against +0.06 ± 0.02 (three experiments). The printed sodium-bath species means sum to −81.07 µmol/g and the table's reported total is −80.69 µmol/g. Either gives −0.38 g/g to the paper's precision. The ion and taurine measurements constrain the total osmolyte change. Isolating K–anion cotransporter kinetics requires a pathway-specific measurement. [Guizouarn et al., Fig. 1 and Table 1](https://doi.org/10.1111/j.1469-7793.2000.t01-1-00147.x) · [Measured inputs](checks/data/guizouarn2000_water_solutes.json) · [Calculation](checks/osmometry.py)

For a time-course comparison, a separate trout study measured water, K, Na and Cl at matched times through 90 min. It inferred taurine from the osmotic balance. Its ion and water traces can therefore test the timing of a future model fit, while the earlier study supplies an independently assayed taurine endpoint. [Maxime, Fig. 1 and Table 1](https://doi.org/10.33594/000000440)

## 19 November 2026 · Potassium and anion cotransport

**Engine finding for the operators owner.** The `k_anion_symport_mass_action@1` step-size check can admit a step that transports both ions in the wrong direction. The normal CPU float64 runner for `resolved_pump_composite@1` completed a 10 ms step with 2.141 × 10⁻⁶ fmol **inward**. The exact trajectory gives 0.867 × 10⁻⁶ fmol **outward**. The reported global material and charge errors were both zero. [Reproducer](checks/potassium_anion_symport.py) · [Operator step check](../src/cells/operators/k_anion_symport.py#L252) · [Proof](CellsProofs/Transport/PotassiumAnionSymport.lean)

The fixture has one cell and one finite outside compartment, each 1 pL, with water and other membrane transfers disabled. One cycle moves one K⁺ and one monovalent anion. The inside concentrations were 4 and 4 mM. The outside concentrations were 128 and 0.125 − 2⁻²⁰ mM. The capacity was 2.5 fmol/(s mM²), availability was one, and the cell was at its set volume. These inputs test the integration near equilibrium. [World definition](checks/potassium_anion_symport.py#L65)

For equal fixed volumes, let D be the initial inside product minus the outside product, S the sum of **all four** starting concentrations, V the common volume and k the active rate scale. The outward extent is V(D/S)(1 − exp(−λt)), with λ = kS/V. The engine bounds the rate using the inside concentration sum and the largest allowed volume factor. In this example it obtained h × bound = 0.221, below the limit of 1, while hλ = 3.403. On this linear problem the explicit ARS(2,2,2) stages give hJ₀(1 − hλ/2), which reverses sign when hλ exceeds 2. The correction belongs in the step-size bound for finite outside compartments. The proof also gives the dependence on each volume when the two volumes differ. [Rate used in the bound](../src/cells/operators/k_anion_symport.py#L152) · [Tableau](../src/cells/numerics/surface_imex.py#L52) · [Applied transfer and heat](../src/cells/models/surface_pump_v3.py#L1436)

| Steps over the same 10 ms | Booked outward transfer (fmol) | Exact outward transfer (fmol) |
| ---: | ---: | ---: |
| 1 | −2.1409988 × 10⁻⁶ | +8.6691746 × 10⁻⁷ |
| 32 | +8.6670944 × 10⁻⁷ | +8.6691746 × 10⁻⁷ |
| 64 | +8.6686762 × 10⁻⁷ | +8.6691746 × 10⁻⁷ |

The 32- and 64-step runs converged with an error reduction of 4.17. An ordinary 20-step world agreed with the independent tableau calculation, and 27 component cases agreed with the 60-digit rate, affinity, activation and heat calculations. A separate **component-only** check found overflow in the concentration-product quotient. With 16 mM for both inside ions and 2⁻⁵¹⁰ mM for both outside ions, both products are normal float64 numbers. The domain check accepts them, but the kernel returns infinite affinity and heat. The reference gives 1.83660 × 10⁶ J/mol and 4701.69 pJ/s. The scale of this second case is far outside physiological concentrations. [Range check](checks/potassium_anion_symport.py#L44) · [Kernel](../src/cells/laws/routes/k_anion_symport.py#L79)

**Biological measurements.** Search checked the original erythrocyte studies. In rabbit red cells the measured outward K:Cl flux ratio was 1.12 ± 0.26 (SD, five preparations), consistent with the 1:1 booking. In sheep red cells with pH and volume clamped, normalized reversal versus chloride ratio had fitted slopes of 1.12 and 1.08 at normal and low internal magnesium. Cells predicts 1. The study used Rb for inward flux and reported no uncertainty for the slopes. Earlier swollen sheep cells gave apparent reversal near 24 mM external Rb at 37 °C, against about 12 mM from equal products. That assay used chloride medium without a chloride-minus-nitrate subtraction, leaving the contribution of other K fluxes unresolved. Human red-cell swelling measurements used one-way K influx and leave the instantaneous exponential law for net flux open. [Jennings and Adame, Fig. 5](https://pubmed.ncbi.nlm.nih.gov/11502559/) · [Lauf and Adragna, Fig. 8](https://pmc.ncbi.nlm.nih.gov/articles/PMC2229324/) · [Reversal data](checks/data/lauf1996_kcc_reversal.json) · [Delpire and Lauf, Fig. 4](https://pmc.ncbi.nlm.nih.gov/articles/PMC2216477/) · [Kaji, Fig. 1 and Table I](https://pmc.ncbi.nlm.nih.gov/articles/PMC2228857/)

```json
{
  "engine_revision": "d6532edeb1bb06127ddf398adb23ab41b2f396c7",
  "model": "resolved_pump_composite@1", "operator": "k_anion_symport_mass_action@1",
  "backend": "cpu", "dtype": "float64", "component_cases": 27,
  "near_stall_steps": [1, 32, 64], "duration_s": 0.01,
  "reference_outward_fmol": 8.669174564376788e-7,
  "booked_outward_fmol": [-2.140998803980456e-6, 8.667094436883358e-7, 8.668676212784617e-7],
  "full_exit": 1, "controls_only_exit": 0
}
```

## 19 November 2026 · Law and evidence review

We rebuilt all 22 Cells Lean modules from source into an empty output directory using the pinned Lean 4.19.0 compiler and compiled Mathlib dependencies. All 153 distinct theorems named in the register resolved in their declared modules. Lean reported only `propext`, `Classical.choice` and `Quot.sound` as transitive axioms. The optional `grn-lean` Hill proofs and ATOMS Lab dimensional check also compiled. The live inventory contains 30 laws and 24 operators. Direct claims cover all 30 laws and three operators. Each claim gives the property and assumptions that were proved. [Claim register](claims.json) · [Registry coverage](COVERAGE.md) · [Theorem check](scripts/CheckClaims.lean)

The 20 registered engine comparisons ran on CPU float64 with `resolved_pump_tissue@3`, `resolved_pump_composite@1` and both versions of `cells.assembly_lineages` (1 and 2). Sixteen passed. All four recorded failures reproduced, with the following outcomes.

| Comparison | Result on this engine revision |
| --- | --- |
| [Membrane insertion](checks/membrane_insertion.py) | Both versions rejected a valid step with expected heat 0.0516031 pJ. Substituting the one-patch heat alone still failed. Substituting both heat and image charge completed the step. |
| [GARD catalysis](checks/gard_catalysis.py) | Two extreme catalyst ratios broke forward/reverse agreement. The ledger refused both steps. |
| [Transition-state catalysis](checks/assembly_kinetics.py) | The two correct rates were 2.06115 s⁻¹. Both computed rates were zero, and the world reported inert with zero events. |
| [Inward rectification](checks/inward_rectifier.py) | An equivalent conductance normalization produced a finite reference current of 0.552053 pA. The engine refused it at initialization. |

The separate BIO-002 reference calculation reproduced the +3.41 mV held-out C3 error and its not-assessable biological verdict. All 170 comparison links resolved to files and, where specified, lines or headings at their recorded revisions. [BIO-002 reference](../reports/BIO002_CONDITIONED_VOLTAGE.md) · [Comparison drivers and pinned records](claims.json)

Search independently checked all six measurement files in `checks/data/`, the priority channel comparisons and the PGI worksheet, and spot-checked the pump and RPTEC results. The evidence corrections below preserve the existing biological verdicts.

- Coady used sodium steps of 96 to 48 and 48 to 24 mM, each paired with a substrate change from 1 to 0.5 mM. The revised driver gives an isolated shift ratio of 2 for each pair. The whole-oocyte means were 2.2 ± 0.2 for lactate and 2.3 ± 0.3 for propionate. In the separate Gopal series, observed charge exceeded the prediction for all four human points by about 65–85 pmol. [Coady, Fig. 4](https://pmc.ncbi.nlm.nih.gov/articles/PMC1965447/) · [Gopal, Fig. 9A](https://ars.els-cdn.com/content/image/1-s2.0-S0021925819709016-gr9.jpg) · [Revised comparison](checks/sodium_anion_symport.py#L105)
- The Shaw fits reproduced across 23 distinct printed compositions. The Parker crystal onset lies 20.4 percentage points above Shaw’s highest composition. Parker gives 23 °C for equilibration before fluorescence measurements. The temperature for the microscopy endpoint is unspecified. [Shaw, Table S1](https://ars.els-cdn.com/content/image/1-s2.0-S0006349523001017-mmc1.pdf) · [Parker, Methods and Fig. 3](https://www.phys.ttu.edu/~huang24/Amanda.pdf)
- The Kir4.1 inward-conductance fit and matched-drive currents come from the same patch series. The Shon two- and three-partner classes were withheld from our one-partner fit within one experiment. The PGI worksheet reports soluble-pool concentrations in mM, while the proof concerns amounts. [Kir4.1 comparison](claims/inward-rectifier.md) · [Confined-binding comparison](claims/assembly-stochastic-encounter.md) · [PGI worksheet audit](claims/incoming/pgi-evidence.md)

```json
{
  "engine_revision": "e01fa24bb315b641bb17b43fdd82d9a5086039c4",
  "registered_engine_drivers": 20, "passed": 16,
  "failed": ["membrane-insertion", "gard-catalysis", "assembly-kinetics", "inward-rectifier"],
  "reference_drivers_passed": 1, "registered_theorems": 153,
  "smct1_sodium_pairs_mM": [[96, 48], [48, 24]],
  "smct1_isolated_shift_ratios": [1.9999999999999956, 1.999999999999998]
}
```

## 19 November 2026 · Inward rectification and sodium-anion symport

Both comparisons run `resolved_pump_tissue@3`. The inward rectifier reverses at the monovalent Nernst potential. With driving voltage u = V − E and positive conductance, the current has the sign of u and releases heat Iu ≥ 0. The host bounds the **magnitude** of the current’s voltage derivative when choosing a step. Lean derives that derivative and proves the host’s voltage-free bound for every voltage. Writing w = (u − V½)/s, the logistic fraction q satisfies |w| q(1 − q) ≤ ¼. This yields the bound G(5/4 + |V½|/(4s)), where G includes area and opening. [Rectifier proofs](CellsProofs/Transport/InwardRectifier.lean) · [Engine current and stage bound](../src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L75)

**Engine finding for the lead.** A change of reference concentration can make a valid potassium route fail the initial domain check. Multiplying its reference conductance by b and its reference concentration by b² preserves the entire current–voltage curve. The same tissue patch had 140 mM potassium inside and 5 mM outside in all three cases below. At 0 mV, the 60-digit calculation gave the same outward current, **0.5520533 pA**, each time. The last declaration uses extreme, finite reference coefficients. The engine forms 5/Kref before taking its square root, so that intermediate overflows. With these inputs, taking the two square roots before division gives the finite effective conductance. [Proof of reference invariance](CellsProofs/Transport/InwardRectifier.lean) · [Reproducer](checks/inward_rectifier.py#L79) · [Engine evaluation](../src/cells/laws/routes/inward_rectifier_linear_driving_force.py#L71) · [Initial domain check](../src/cells/models/surface_pump_v3.py#L1558)

| Reference conductance (S/m²) | Reference K (mM) | Compiled 1 ms tissue run |
| ---: | ---: | --- |
| 1 | 4 | Outward transfer 5.682053 × 10⁻⁶ fmol, heat 4.728381 × 10⁻⁵ pJ |
| 2⁻⁸ | 4 × 2⁻¹⁶ | Same transfer and heat, bit for bit |
| 2⁻⁵¹² | 2⁻¹⁰²² | Refused during definition validation |

The compiled CPU law agreed with a 60-digit reference for current, inward flux, heat and the slope magnitude over 360 ordinary states. The reference obtained the derivative with dual numbers. The largest error divided by the respective unrectified physical scale was 6.47 × 10⁻¹⁶ or less. The voltage-free bound covered all 360 states, including 64 with negative differential conductance. [Comparison and scales](checks/inward_rectifier.py#L20) · [Independent derivative arithmetic](../validation/core_seams/references/exact.py#L88)

**Kir4.1 measurements.** For cloned rat Kir4.1 channels in HEK293T cells at about 25 °C, lowering external potassium from 153 to 15 mM shifted reversal by approximately −60 mV. Cells predicted −59.67 mV. The authors fitted a 0.51 concentration exponent to the *inward slope conductance*. To test current at the *same driving voltage*, we read each reversal from Fig. 4C, moved 60 mV below it, and interpolated the current in Fig. 4B(b). Only the 153 mM current set the scale. At fixed drive, every choice of the same logistic parameters and availability predicts the square-root ratio. Cells underestimated the inward current magnitude at all four lower concentrations. The figure gives means of three patches with no numerical uncertainties for these points. [Tada et al., Fig. 4B–D](https://www.jstage.jst.go.jp/article/jjphysiol/48/1/48_1_71/_pdf/-char/ja#page=6) · [Figure readings and assumptions](checks/data/tada1998_kir41.json)

| External K (mM) | Current read from figure (pA) | Cells at V − E = −60 mV (pA) |
| ---: | ---: | ---: |
| 15 | −0.59 | −0.385 |
| 21 | −0.80 | −0.456 |
| 35 | −1.04 | −0.588 |
| 63 | −1.16 | −0.789 |
| 153 | −1.23 | −1.230 (calibration) |

**Sodium–anion symport.** Each forward cycle carries n sodium ions and one monovalent anion from P to N. This moves n − 1 positive charges and n + 1 particles. With n = 1 the rate is independent of voltage. With n > 1 an enabled carrier imports below its unique stall voltage and exports above it. Capacity and the two source-side Hill factors set the rate scale. The proof reuses the factored transporter rate and gives a direct experimental observable. Halving external sodium shifts the carrier’s stall voltage n times as far as halving the substrate at fixed internal concentrations. A common nonzero conductance weighting cancels from the ratio. [Symport proofs](CellsProofs/Transport/SodiumAnionSymport.lean) · [Cycle declaration](../src/cells/laws/cycles/na_anion_symport_factored.py#L42) · [Host rate evaluation](../src/cells/kinds/transporter.py#L1407)

The host comparison covered all four admitted sodium counts, both orientations, three availabilities and five voltages. Against independent 60-digit calculations, all 120 stages agreed on free energy, saturation, one-way and net rates, and heat. Twelve active cases were at their predicted stall. The maximum error was 0.220 of one estimated roundoff floor, with an acceptance limit of 64 floors. A compiled two-step run transported 8.621772 × 10⁻⁵ fmol lactate, equal to its cycle total, with zero reported global charge error. [Host comparison](checks/sodium_anion_symport.py) · [Rate tolerance](../validation/core_seams/references/design.py#L39)

**SMCT1 measurements.** The Cells declaration cites Coady et al. for n = 2 in human SMCT1. In that study the measured net charge per lactate was 1.04 ± 0.07, compared with 1 from the host’s transported rows. Independent volume/current measurements gave 3.1 ± 0.1 osmolytes per charge, compared with 3. The ratios of zero-current shifts after sodium and substrate halving were 2.2 ± 0.2 for lactate and 2.3 ± 0.3 for propionate (means ± SE, 11 and 7 oocytes). The model predicted 2. Its **isolated** voltage shifts at 24 °C were −35.50 and −17.75 mV. The measured whole-oocyte shifts also depend on other conductances, including an anion leak. The absolute stall, Hill constants and turnover rates remain open experimentally. [Coady et al., Figs. 1, 2 and 4–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC1965447/) · [Observables and protocol](checks/data/coady2007_smct1.json) · [Computed shifts](checks/sodium_anion_symport.py#L105)

Gopal et al. provide a separate laboratory’s charge and lactate measurements. For the four human SMCT1 points in Fig. 9A, uptake was approximately 225, 285, 300 and 370 pmol. With n = 2 those numbers also give the predicted pmol of net positive charge. The measured charges were about 290, 360, 385 and 450 pmol. These retrospective figure readings are rounded to 5 pmol. Individual errors are unavailable. [Gopal et al., Fig. 9A](https://ars.els-cdn.com/content/image/1-s2.0-S0021925819709016-gr9.jpg) · [Paired readings](checks/data/gopal2004_lactate.json)

```json
{
  "engine_revision": "ced58d2a1edc59e25d8f6e62bd79cc51b2f5d984",
  "model": "resolved_pump_tissue@3", "backend": "cpu", "dtype": "float64",
  "rectifier": {"states": 360, "negative_slopes": 64, "max_scaled_error": 6.462348535570529e-16,
    "scale_exponents": [0, -8, -512], "admitted": [true, true, false],
    "reference_current_A": 5.52053308618338e-13},
  "symport": {"states": 120, "active_stalls": 12, "max_error_in_roundoff_floors": 0.21907374518353304,
    "isolated_shift_mV": [-35.49801595309584, -17.749007976547958],
    "cycles_fmol": 8.621772032950217e-05, "global_charge_error_C": 0}
}
```

All 22 public theorems compiled with only `propext`, `Classical.choice` and `Quot.sound`. The full rectifier comparison reproduced the refusal in 21.97 s and returned status 1. Its controls passed in 33.58 s. The symport comparison passed in 18.66 s. Each used two CPU cores. The nine existing tests for these two laws and the 82 repository guards passed. [Rectifier host tests](../tests/unit/test_inward_rectifier_route.py) · [Symport host tests](../tests/unit/test_na_anion_symport_factored.py)

The live registry now has direct proofs and recorded numerical comparisons for all 30 laws. The rectifier comparison is recorded as failed. Full test discovery returned the same 20,308 IDs and the same five missing-fixture errors before and after the proof checkpoint. All five documentation-generator tests passed. [Coverage register](COVERAGE.md) · [Proof and evidence checkpoint](https://github.com/Eidosoma/Cells/commit/40dfe4de2a04559196bddef7e32c01cffc056e7b)

## 19 November 2026 · Stochastic encounters and transition-state catalysis

In `cells.assembly_lineages@2`, drawing two copies of one molecule with count n gives n(n − 1) ordered choices. For a general reaction the finite-place draws are falling factorials. Lean proves that their log, including the membrane normalization and dilute concentration scales, equals the change of ideal energy less the reactants’ standard potentials. On regular, finite two-way edges, log(forward rate / reverse rate) is the initial free energy minus the final free energy plus held-reservoir work. The proof also covers the cancelled membrane denominator for full consumption under the offset-one measure. If a membrane participant survives on both sides at the singular boundary, the numerator is positive and the denominator is zero. [Lean proofs](CellsProofs/Chemistry/AssemblyKinetics.lean) · [Encounter law](../src/cells/models/assembly_lineages_v2/mass_action.py#L74) · [Mathlib factorial identity](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Nat/Factorial/Basic.lean#L368)

For catalysis, the common state is the componentwise minimum of the two endpoint counts. A nonempty common membrane has a factor equal to its count-weighted mean of exp(ΔΔG‡), which is strictly positive even for inhibition. An empty common membrane has factor 1. On a positive two-way edge the original rate ratio survives exactly when both directions receive the same multiplier. The same equilibrium weights then satisfy detailed balance. These results allow shared reactants and products. [Factor and rate-ratio proofs](CellsProofs/Chemistry/AssemblyKinetics.lean#L96) · [Engine factor](../src/cells/models/assembly_lineages_v2/transition_state.py#L130)

**Engine finding for the lead.** A valid two-molecule world stops as `inert` with both directions of an enabled reaction at zero. A ⇌ B has equal standard potentials, a base rate of 10⁹ s⁻¹, and one stationary C molecule. A and B have contact energies +20 kBT, C has −20 kBT, all within the declared range. In either direction C is the only common molecule. The exact rate is therefore 10⁹ exp(−20) = **2.0611536224 s⁻¹**. C contributes −1 + exp(−20) to the cached sum. Adding this to the large moving-molecule contribution rounds away exp(−20). Subtracting that moving term gives −1 on the common state, and adding 1 gives zero. The world passes its own balance probe (107 pairs, maximum residual 1.07 × 10⁻¹⁴ kBT). A zero forward rate is skipped by that probe. The 60 s compiled run records zero events and a passing ledger. [Two-state input and clock check](checks/assembly_kinetics.py#L90) · [Cached subtraction](../src/cells/models/assembly_lineages_v2/transition_state.py#L130) · [Balance probe](../src/cells/models/assembly_lineages_v2/balance.py#L87) · [Inert status](../src/cells/models/assembly_lineages_v2/kernel.py#L459)

Absorbing the exact constant factor into the rate gives the identical two-state process on the reachable compositions. This control fires four alternating events, reaching the chosen event limit, with its first at **0.3459699807 s** on the same random draw. Moderate contacts of ±2 kBT also pass. At zero contact energy for the movers, retaining C at −20 kBT restores four events but the rate is still low by 2.00 × 10⁻⁸ relative. The remaining subtraction is in 1 + expm1(−20). A numerical reference for the operator owner is to form the positive weighted mean directly on the remaining integer counts, with weight 1 for unspecified species. [Exact common-state mean](CellsProofs/Chemistry/AssemblyKinetics.lean#L112) · [Reference-rate tolerance](../validation/ool/references/detailed_balance.py#L191)

The ordinary comparison used the 592 registered OL1 states and two additional states with a single remaining inhibitor. Catalysed and bare rates matched the independent reference for both measures, including the zero and singular patterns. Across 1,925 two-way edges, the forward and reverse multipliers agreed with the reference common-state factor within 6.11 × 10⁻¹⁶ in log units. The six-state boundary world checked both orientations of a last leave and a two-copy leave under three token combinations. With extinction enabled those three rates were 0.125, 0.25 and 1 s⁻¹. The kept rule suppressed all three. The full driver exits with status 1 on the two clock discrepancies. [CPU driver](checks/assembly_kinetics.py) · [Independent rates](../validation/ool/references/laws.py#L222) · [Boundary world](../validation/ool/references/designs/ol1_boundary.world.json)

**Biological measurements.** Shon and Cohen measured the probability that one labelled molecule binds a partner in a sealed chamber containing exactly one, two or three partners. We read the experimental bars in Fig. 4f for the 250 nm radius and used the one-partner measurement to set the equilibrium odds. Cells’ pool reaction R + G ⇌ D predicted the other two probabilities from their counts. The Lean result eliminates the unknown chamber volume from this comparison. [Shon and Cohen, Fig. 4f and Table 1](https://cohenweb.rc.fas.harvard.edu/Publications/Shon_Cohen_Dimples_JACS.pdf) · [Measurements and uncertainties](checks/data/shon2012_confined_binding.json) · [Engine comparison](checks/confined_binding.py)

| Available partners | Observed bound probability (figure reading) | From one-partner odds | From bulk Kd, geometry volume | From bulk Kd, loading volume |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.48 | 0.48 (calibration) | 0.432 | 0.269 |
| 2 | 0.64 | 0.649 | 0.603 | 0.424 |
| 3 | 0.67 | 0.735 | 0.695 | 0.525 |

For the last two columns we used the independently measured bulk Kd of 57 ± 12 nM. A cylinder with the reported radius and the midpoint of the measured depth range gives 38.29 aL. A separate loading experiment implies 79.07 aL from its mean occupancy at the nominal bath concentration. The assay’s effective volume remains uncertain. The comparison uses the measured association constant to set the time unit. It cancels from the equilibrium predictions. Numerical uncertainties for the individual bars are unavailable. These are two distinct reactants. Live-cell measurements of receptor homodimer kinetics report a 91 ± 16 ms lifetime, with surface densities in place of fixed small integer counts. The repeated-reactant count law remains open experimentally. [Shon and Cohen, Figs. 2c and 4f](https://doi.org/10.1021/ja3062425) · [Kasai et al., Figs. 4–6](https://doi.org/10.1083/jcb.201009128)

For the catalyst claim, Leventis and Silvius measured cholesterol exchange between vesicles at 37 °C. The relaxation half-time fell from 195 ± 13 minutes to about 3.4 minutes with 1 mM β-cyclodextrin, approximately a 57-fold speedup. A separate equilibrium series at 0.5 mM gave a partition coefficient of 0.91 ± 0.06 for the same lipid pair. Matched forward and reverse rates with and without the catalyst remain open. These data concern a soluble transfer catalyst. The engine evaluates contact fractions on the membrane. [Leventis and Silvius, Figs. 1–2 and Table 1](https://doi.org/10.1016/S0006-3495(01)75873-0)

```json
{
  "engine_revision": "e584c79bfe74ef14085479e7d55b8a3975970656",
  "model": "cells.assembly_lineages@2", "backend": "cpu", "dtype": "float64", "seed": 1,
  "laws": ["cells.stochastic_mass_action@1", "cells.transition_state_factor@1"],
  "states_per_measure": 594, "reversible_edges": [963, 962], "singular_rates": [0, 2],
  "factor_range": [0.5, 2.5], "max_log_factor_error": 6.106226635438361e-16,
  "opposed_contacts": {"expected_rate_per_s": 2.061153622438558, "rates_per_s": [0, 0],
    "horizon_s": 60, "events": 0, "status": "inert", "ledger_holds": true},
  "same_draw_control": {"first_event_s": 0.3459699806783901, "events": 4},
  "neutral_movers_relative_rate_error": 2.0033979697409166e-8,
  "measured_bound_probabilities_approx": [0.48, 0.64, 0.67],
  "held_out_bound_probabilities": [0.648648648648649, 0.7346938775510207]
}
```

The 18 public theorems compiled with only `propext`, `Classical.choice` and `Quot.sound`. The full comparison took 31.21 s on two CPU cores, the controls-only comparison passed in 33.06 s, and the confined-binding comparison took 2.31 s. The nine existing assembly kernel tests and the 82 repository guards passed. [Existing kernel tests](../tests/unit/test_assembly_lineages_v2_kernel.py) · [Confined-binding driver](checks/confined_binding.py)

Test discovery returned the same 20,308 test IDs and the same five missing-fixture errors before and after the proof checkpoint. The live registry resolved both new claims, and all five documentation-generator tests passed. [Proof and evidence checkpoint](https://github.com/Eidosoma/Cells/commit/cb4194144bdccd3c4ce4fc24c28979d91a3943a8)

## 19 November 2026 · Ideal and regular assembly mixing

For the two mixing laws in `cells.assembly_lineages@2`, adding one molecule of species A costs an ideal mixing energy whose exponential, relative to the membrane standard state, is (a + 1)/(N + 1 − c). Here a is the count of A, N is the total membrane count, and c is 0 or 1 for the two registered measures. The formula holds for N ≥ c. Lean also checks the empty membrane, the first molecule’s energy and the cost of transferring one molecule from a finite dilute pool. At positive N the two membrane free energies differ by ln N. Event admission at extinction follows the world's boundary rule. [Lean derivation](CellsProofs/Chemistry/AssemblyMixing.lean) · [Ideal energy and increment](../src/cells/models/assembly_lineages_v2/ideal_mixing.py#L64)

For regular mixing, symmetry of the interaction matrix makes the engine’s incremental update equal to recomputing the quadratic energy from all counts. In a binary membrane with b molecules of B and one unlike-pair energy χ, the excess cost of adding A is χb²/[N(N + 1)]. Its bulk chemical potential is χ(b/N)². For χ = 1 and equal amounts of A and B, the engine gave 0.214286 kBT at N = 6 and 0.245902 at N = 60, approaching 0.25. The default proof reuses matrix and derivative results from the pinned Mathlib. All twelve named theorems checked with only `propext`, `Classical.choice` and `Quot.sound`. [Regular energy and update](../src/cells/models/assembly_lineages_v2/regular_mixing.py#L95) · [Mathlib matrix identities](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Matrix/Mul.lean#L662)

The CPU comparison used the seven-step OL1 probe world, with its declared interactions and again with only ideal mixing. For each measure and variant, the host kernel and ledger were compared with the exact-factorial reference on the same 592 compositions. The check includes zero and singular rate patterns, reversible edge heats and closed cycles. On four compiled 80-event trajectories the independent reference replayed the counts and rebooked heat and reservoir work at every saved row. The largest state-energy error was 2.14 × 10⁻¹⁴ kBT. [CPU comparison](checks/assembly_mixing.py) · [World](../validation/ool/references/designs/ol1_wa.world.json) · [Reference and edge tolerances](../validation/ool/references/detailed_balance.py#L155) · [Trajectory tolerance](../validation/ool/references/ledger.py#L85)

**Biological evidence.** Shaw et al. measured equilibrium cholesterol activity in protein-free DOPC vesicles across 5.4–45.6 mol% cholesterol. Unit activity refers to crystalline cholesterol. For cholesterol mole fraction x we fitted A = s x for ideal mixing and A = s x exp[χ(1 − x)²] for regular mixing. Each model fitted its own reference-state scale s. We used all 25 readings, fitting ln(A/x) with each of the 23 distinct composition values printed in Table S1 held out in turn. Readings with the same printed value stayed together. The table gives activity errors on these withheld readings. The parameter estimates use all rows. [Shaw et al., Fig. 2A](https://pmc.ncbi.nlm.nih.gov/articles/PMC10111267/) · [Table S1, printed p. 13](https://ars.els-cdn.com/content/image/1-s2.0-S0006349523001017-mmc1.pdf) · [Transcribed numbers and reference state](checks/data/shaw2023_dopc.json) · [Fit and engine comparison](checks/cholesterol_activity.py)

| Model | Scale s | χ (kBT) | Held-out activity RMSE | Predicted activity at 45.6 mol% |
| --- | ---: | ---: | ---: | ---: |
| Ideal | 1.695 | 0 | 0.0953 | 0.791 |
| Regular | 1.117 | 0.753 | 0.0782 | 0.677 |

At 45.6 ± 1.5 mol% the observed activity was 0.45 ± 0.02. Adding the interaction term reduced average error, and both curves overpredicted this endpoint. Reweighting the fits using both reported 68% half-widths gave errors of 0.0997 and 0.0772, respectively, and shifted χ to 1.017 kBT. This sensitivity calculation assumes zero covariance. The two coordinates come from the same fit, activity shares a calibration across samples, and the reported intervals describe the extracted values. These within-study predictions leave the value of χ and its transfer to other preparations open. The experimental observable is bulk activity. At each measured composition we also evaluated the engine’s insertion energy at a chosen N = 1,000, which represents every tabulated percentage exactly. For the primary fits its activity differed from the bulk prediction by at most 0.0021. Molecular event rates and finite vesicle counts were unmeasured. [Experimental method and confidence intervals](https://pmc.ncbi.nlm.nih.gov/articles/PMC10111267/) · [Calibration, Fig. S7](https://ars.els-cdn.com/content/image/1-s2.0-S0006349523001017-mmc1.pdf)

**Independent saturation check.** Parker et al. located the onset of cholesterol crystals at a DOPC membrane mole fraction of 0.66 ± 0.02 across three sample series. We extrapolated the two Shaw fits to this endpoint with the fitted scales fixed. At x = 0.66 the ideal curve gives 1.119 and the regular curve 0.804. Over x = 0.64–0.68 the predictions span 1.085–1.153 and 0.788–0.820. If the two preparations equilibrated with the same solid phase, activity at onset is 1. The ideal curve is closer at saturation, although regular mixing fitted the lower compositions better. Parker identified the solid as monohydrate. Shaw’s reference crystal polymorph is unspecified, as is the confidence level of Parker’s reported ±0.02. Independent activity measurements in the 35–50 mol% range remain open. [Parker et al., Fig. 3](https://doi.org/10.1016/S0006-3495(04)74221-6) · [Endpoint and preparation](checks/data/parker2004_dopc_saturation.json)

```json
{
  "engine_revision": "1e77a8876cc28e23e9ffed443e62c465b6f8fe3c",
  "model": "cells.assembly_lineages@2", "backend": "cpu", "dtype": "float64", "seed": 1,
  "laws": ["cells.ideal_mixing@1", "cells.regular_mixing@1"],
  "states_per_variant": 592, "variants": 4, "reversible_edge_comparisons": 3842,
  "cycle_comparisons": 1930, "trajectory_events": 320, "saved_rows": 48,
  "max_state_energy_error_kT": 2.1316282072803006e-14, "state_atol_kT": 1e-10,
  "max_edge_error_kT": 1.9984014443252818e-14, "max_independent_closure_kT": 1.4210854715202004e-14,
  "activity_rows": 25, "composition_folds": 23, "activity_rmse_ideal": 0.09532314049809815,
  "activity_rmse_regular": 0.07819454423476385, "regular_chi_kT": 0.7526736601694367,
  "max_abs_finite_N1000_minus_bulk_activity": [0.0015963759088614832, 0.0020792557562164526],
  "external_crystal_onset_mole_fraction": 0.66,
  "extrapolated_activity_at_onset": {"ideal": 1.118971866, "regular": 0.804292464}
}
```

The complete comparison, including both datasets, took 41.73 s on two CPU cores. The nine existing kernel tests passed in 69.71 s, the six ledger tests in 36.29 s and the 82 repository guards in 89.68 s. [Model kernel tests](../tests/unit/test_assembly_lineages_v2_kernel.py) · [Ledger tests](../tests/unit/test_assembly_lineages_v2_ledger.py)

Full test discovery before and after the proof checkpoint returned identical lists of 20,308 test IDs. Both collections reported the same five missing-fixture errors in the finite extracellular, kinetic finite and physical ionic graph modules. The claim generator’s five tests, its live-registry check and the Lean declaration check passed. [Proof checkpoint](https://github.com/Eidosoma/Cells/commit/2c18459cbac3a33f58551194340afe2b2c565b5a)

## 19 November 2026 · GARD catalysis on reversible transfers

The two GARD comparison laws in `cells.assembly_lineages@1` multiply the base reservoir-exchange rates. For a transfer of species i from composition n to n + eᵢ, the pair-consistent form evaluates both multipliers on n. Lean proves that the multiplier cancels and the heat equals the change in the base log weight Φ on every nonempty reversible edge. The single-event form instead adds ln bᵢ(n) − ln bᵢ(n + eᵢ) to that heat. When the last molecule leaves, the pair-consistent exit factor is 1 and the single-event factor is 1 + βᵢᵢ. [Lean proofs](CellsProofs/Chemistry/GardCatalysis.lean) · [Registered factors](../src/cells/models/assembly_lineages/gard.py#L137) · [Base exchange heat](claims/assembly-exchange-heat.md)

**Float64 refusal for the engine lead.** Start with one molecule of type B. When A enters, B is the only catalyst on both sides of the reversible edge. If β_AA = 2⁵⁴ and β_AB = 1, the exact multiplier is 2 in both directions and the exact heat is zero. On CPU, forming the row sum at (1, 1) rounds 2⁵⁴ + 1 to 2⁵⁴. Subtracting β_AA then gives a reverse multiplier of 1. The engine books **ln 2 kBT** and refuses the first event at its passive ledger check. A smaller case also crosses the rounding bound. Keeping the same random draw and reducing the diagonal, or setting β_AB to zero, gives the expected zero heat. Computing the reverse sum on the counts with the departing molecule removed gives a reference that avoids the subtraction. [One-event reproducer](checks/gard_catalysis.py#L107) · [Reverse multiplier](../src/cells/models/assembly_lineages/gard.py#L143) · [Ledger refusal](../src/cells/models/assembly_lineages/runner.py#L894)

| β_AA | β_AB | Exact multiplier | CPU reverse multiplier | CPU heat (kBT) | Outcome after one event |
| ---: | ---: | ---: | ---: | ---: | --- |
| 2 | 1 | 2 | 2 | 0 | Reached stop |
| 2⁵⁴ | 0 | 1 | 1 | 0 | Reached stop |
| 2²¹ | 2⁻³² | 1 + 2⁻³² | 1 | 2.3283064363 × 10⁻¹⁰ | Refused, bound 10⁻¹⁰ |
| 2⁵⁴ | 1 | 2 | 1 | 0.6931471806 | Refused, bound 10⁻¹⁰ |

**Rank-one condition at the tested revision.** The single-event exception in the design and law description used rank one of β. The sufficient condition proved here is rank one of the matrix formed by adding one to **every entry** of β. If 1 + βᵢⱼ = uᵢvⱼ with positive factors, the extra heat is a difference of state values and cancels around any closed path of nonempty compositions. The corrected log weight is Φ(n) − ln(Σⱼ vⱼ nⱼ / N). For a direct counterexample to the wording, set β_AA = 1 and all other entries to zero. This β has rank one. At counts (1, 1), the product of the four rates around +A, +B, −A, −B divided by the reverse product is **81/80**, which excludes detailed balance on that square. The exact finite-reservoir reference already uses the entrywise shift. The CPU comparison below uses the registered held reservoir. [Exact square](CellsProofs/Chemistry/GardCatalysis.lean#L117) · [Design §2.5](../docs/GARD_DESIGN.md#25-the-independent-check-and-its-scope-16-november-2026) · [Finite-reservoir reference](../validation/gard/references/closed_world.py#L202)

For each of three matrices and both laws, the CPU driver checked 45 compositions through size eight, 70 reversible edges and 27 four-step cycles against an independent exact-rational reference. The largest edge error on that grid was 5.00 × 10⁻¹⁶ kBT. On the shifted rank-one example the single-event log weight correction agreed within 4.45 × 10⁻¹⁶ kBT, even though the difference from the base heat reached 0.4055 kBT. Each law also ran a two-fission lineage and agreed with scalar replay on all 14 event choices and times. The full driver took 13.15 s on two CPU cores and exited with status 1 on the two refusals. Its controls-only run passed. All 17 existing assembly kernel, balance and ledger tests and the 82 repository guards passed. [CPU comparison and inputs](checks/gard_catalysis.py) · [Exact reference propensities](../validation/gard/references/kernels.py#L279) · [Exact cycle reference](../validation/gard/references/detailed_balance.py#L132)

```json
{
  "engine_revision": "f7767ad79edf2f972b78999e64b40f0c294bcf88",
  "model": "cells.assembly_lineages@1", "backend": "cpu", "dtype": "float64", "seed": 1,
  "laws": ["cells.gard_catalysis_pair_consistent@1", "cells.gard_catalysis_single_event@1"],
  "matrices": [[[1,0],[0,0]], [[0,1],[1,3]], [[2,5],[0.5,1]]],
  "edge_comparisons": 420, "square_comparisons": 162,
  "single_event_square_at_1_1": ["81/80", "1", "99/98"],
  "max_ordinary_edge_error_kT": 4.996003610813204e-16, "edge_atol_kT": 1e-9,
  "pair_lineage_max_residual_kT": 4.440892098500626e-15,
  "driven_lineage_reported_max_residual_kT": 0.25071844353711015,
  "one_event_exact_heat_kT": 0, "refused_heat_kT": [2.3283064362676457e-10, 0.6931471805599453]
}
```

Full test discovery at the tested engine revision and the proof checkpoint returned the same 20,300 test IDs. Both collections reported the same five missing-fixture errors in the finite extracellular, kinetic finite and physical ionic graph tests.

**Biological measurements.** Sampaio, Moreno and Vaz compared the same fluorescent lysophospholipid (NBD-lysoMPE) in protein-free vesicles at 308 K. From pure POPC to 1:1 POPC/cholesterol, the insertion constant fell from (3.4 ± 0.3) × 10¹⁰ to (1.7 ± 0.1) × 10¹⁰ M⁻¹ s⁻¹ per molar vesicles. The corresponding exit estimates were 25 ± 2 and 27 ± 2 s⁻¹. Independent equilibrium titrations gave association constants of 1.3 × 10⁹ and 6.1 × 10⁸ M⁻¹. The kinetic fit used the measured equilibrium constant and assumed slow lipid exchange between leaflets. Changing a shared rate multiplier at fixed affinity cannot account for that composition change. Testing GARD’s specific multiplier or a four-transfer cycle would require event rates at known neighboring molecular counts. [Sampaio et al., Figs. 1–3 and Table 1](https://doi.org/10.1529/biophysj.104.054007)

**Lead decision, 19 November.** The lead accepted the two false refusals at extreme coefficient ratios. The builder plans to recompute the lost catalyst sum after its current test run, preserving existing results bit for bit. If that changes recorded results, the proposed alternative is a new law version. The design correction for the entrywise rank-one condition landed at `0b564f2d`. At `1e77a887`, the numerical repair and matching code wording were still pending. [Corrected design](https://github.com/Eidosoma/Cells/blob/0b564f2d99f70995c741456d7f55a515d049dd4d/docs/GARD_DESIGN.md#L320) · [Law at the reviewed revision](https://github.com/Eidosoma/Cells/blob/1e77a8876cc28e23e9ffed443e62c465b6f8fe3c/src/cells/models/assembly_lineages/gard.py#L143)

## 19 November 2026 · Assembly reservoir exchange

In `cells.assembly_lineages@1`, the uncatalyzed `cells.reservoir_exchange@1` law admits one molecule at a time. For species *i*, write θᵢ = Kᵢρᵢ, where Kᵢ is its transfer constant and ρᵢ is its held activity. In an assembly of size N, the entry rate is kᵢθᵢN and the exit rate is kᵢnᵢ. Lean proves entry is linear in activity and size, each additional molecule raises that species’ exit rate by kᵢ, and a nonempty state with all net rates zero requires Σθᵢ = 1. Time is nominal. [Engine rates](../src/cells/models/assembly_lineages/exchange.py#L108) · [Parameter binding](../src/cells/models/assembly_lineages/model.py#L47) · [Lean proofs](CellsProofs/Chemistry/ReservoirExchange.lean)

For a join between nonempty states, the forward rate at departure and the reverse rate at arrival determine the booked heat. Lean proves that the log of their ratio equals the change in the engine’s full log weight, including the `(N−1)!` factor. The reverse leave books its negative. The final leave into the empty state has no reverse join. With log weight zero at extinction its booking is −ln θᵢ. [Event implementation](../src/cells/models/assembly_lineages/kernel.py#L299) · [State function](../src/cells/models/assembly_lineages/ledger.py#L83)

The CPU driver checked every three-species composition through size eight against exact rational propensities. For each reversible join with both states on that grid, an independent calculation used integer factorials, rational state weights and a 65-digit logarithm. Doubling one species’ held activity doubled its entry at every state and preserved all exit rates. A second check replayed the same random draws through the host reference. One lineage underwent three fissions over 40 exchange events, and another ended with its founder’s only molecule leaving. Species inventories, event choices, times, fission partitions and the saved heat, work and discarded free energy matched the references. The driver took 5.61 s on two CPU cores. Eleven assembly kernel, balance and ledger tests and the 82 always-run guards passed. [Driver and worlds](checks/reservoir_exchange.py) · [Compiled rate probe](../validation/assembly_lineages/probes.py#L210) · [Scalar event replay](../src/cells/models/assembly_lineages/reference.py#L46)

```json
{
  "engine_revision": "6c648d846fa5c92644986fd967dd403757234b26",
  "model": "cells.assembly_lineages@1", "law": "cells.reservoir_exchange@1",
  "backend": "cpu", "dtype": "float64", "seed": 1, "rate_factor": null,
  "states": 165, "reversible_pairs": 357,
  "max_rate_error_per_nominal_time": 1.7763568394002505e-15, "rate_rtol": 8.881784197001252e-16,
  "max_heat_error_kT": 4.527628272299467e-16, "edge_atol_kT": 1e-9,
  "growth": {"events": 40, "fissions": 3, "saved_rows": 8, "final_heat_kT": 12.71204244621217},
  "extinction": {"events": 1, "fissions": 0, "saved_rows": 2, "final_heat_kT": 10.257445766024022},
  "max_booking_error_kT": 1.7763568394002505e-15, "booking_atol_kT": 1e-10
}
```

**Finding for the engine lead.** The exchange docstring describes relaxation to xᵢ = θᵢ. The design also describes a composition proportional to θᵢ. These statements need different conditions. Zero net rates require the θᵢ to sum to one. For a growing assembly with a common leave constant k, the fraction changes at k(θᵢ − xᵢΣθⱼ), so its stationary proportion is θᵢ/Σθⱼ. Cells also accepts unequal leave constants. With counts (1, 1), θ = (1, 1) and leave constants (1, 2), the compiled net count rates are (1, 2). The first fraction starts at ½ and its mean-field derivative is **−¼ per nominal time unit**. Changing both leave constants to one gives derivative zero in the same state. The registered rates produce the expected values in both cases. The documentation can distinguish zero net exchange from constant proportions during growth. [Exchange docstring](../src/cells/models/assembly_lineages/exchange.py#L11) · [Design §2.1](../docs/GARD_DESIGN.md#21-the-rate-law-mean-field) · [Exact counterexample](CellsProofs/Chemistry/ReservoirExchange.lean#L79)

**Biological measurements.** In 310 protein-free POPC/POPG vesicles, accessible 14:0–6:0 NBD-PC washed out at 0.0108 ± 0.0045 s⁻¹ (24 °C, 500 µL/min flow, mean ± SD). The retained fraction was 49.5 ± 8.5%. Separate albumin capture gave about 0.07 s⁻¹ across 11 measurements in three preparations. A flow sink and two leaflets affect the washout observable. Cells requires positive held activity and counts a single well-mixed assembly. [Veit et al., Fig. 2 and Extended Data Fig. 2](https://doi.org/10.1038/s41594-026-01821-8)

Estronca et al. added 100 nm POPC/cholesterol vesicles to dehydroergosterol pre-equilibrated with albumin. The measured transfer rate increased with vesicle concentration at 25 °C. At 35 °C the fitted insertion constant was (6.4 ± 0.6) × 10⁷ M⁻¹ s⁻¹ (SD, per molar vesicles). Adding equal-sized vesicles changes total available membrane. The experiment leaves the effects of free monomer activity and individual vesicle size unresolved. The fluorescence fit assumes rapid albumin equilibration and sterol exchange between leaflets. Calibration of the Cells clock and a measurement of the event free-energy difference both remain open. [Estronca et al., Fig. 2, Eq. 6 and Table 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC2098731/)

## 19 November 2026 · Chloride leak

The newly registered `clleak_always_open@1` adds a monovalent anion to the channel populations of `resolved_pump_tissue@3`. Lean proves that outward Cl⁻ movement gives negative outward current. For positive permeability, availability and concentrations, the reversal voltage on the regular branch is `(RT/F) × (ln inside − ln outside)`. The identity also holds at zero voltage. The finite near-zero polynomial keeps its own Bernoulli ratio. The proof reuses the existing constant-field reversal theorem with the concentrations exchanged. [Channel and reversal proofs](CellsProofs/Transport/IonChannels.lean) · [Registered chloride declaration](../src/cells/laws/channels/clleak_always_open.py#L20) · [Current in the tissue host](../src/cells/models/surface_pump_v3.py#L872)

Two one-cell runs started at −21.52 mV with 62.56 mM internal Cl⁻. With 147 mM in the held bath, chloride moved into the cell and the initial electrode current was **+0.573 pA**. With 70 mM outside, chloride left the cell and the current was **−5.733 pA**. The independent calculation integrated signed material transfer with a 70-digit constant-field rate and updated the capacitor voltage at each evaluation. The driver checked the cell and reservoir inventories, signed electrode charge, voltage, all other ions and a padding slot. It took 13.95 s on four CPU cores. [Two tissue worlds and comparison](checks/chloride_channel.py) · [Independent scalar flux](../validation/betse/junction_transport/check.py#L10)

```json
{
  "engine_revision": "d4f1eaf723ee1bdd1e54d9be086cb81d67356bfa",
  "model": "resolved_pump_tissue@3", "law": "clleak_always_open@1", "backend": "cpu", "dtype": "float64",
  "solver": "imex_ars222_face_electromigration@1", "independent_solver": "DOP853",
  "dt_s": 0.000030517578125, "end_s": 0.00048828125, "temperature_K": 310.0,
  "bath_mM": [147, 70], "initial_voltage_V": -0.02151770525721294,
  "initial_outward_flux_fmol_s": [-0.005942329617988368, 0.05942329617988358],
  "initial_electrode_current_A": [5.733476467777896e-13, -5.733476467777887e-12],
  "final_outward_transfer_fmol": [-2.8824350858087033e-6, 2.88820012833921e-5],
  "max_transfer_error_fmol": 1.5791679555264733e-12, "material_atol_fmol": 1e-10,
  "max_electrode_current_error_A": 2.875735404806082e-21, "current_rtol": 2e-6,
  "paper_conditions": {"outside_mM": [145, 15], "temperature_K": 310.15, "model_reversal_shift_mV": 60.63433164318693}
}
```

At 37 °C in rabbit collecting-tubule principal cells, lowering nominal pipette chloride from 145 to 15 mM shifted the single-channel reversal about **+45 mV**. For those concentrations the Cells chloride-only pathway gives **+60.6 mV** at fixed intracellular chloride. The cell-attached voltage is relative to rest, and the paper gives no uncertainty on the shift. The result supports the direction of the response. Absolute permeability and intrinsic opening remain open. [Ling et al., Fig. 1B](https://doi.org/10.1172/JCI117037) · [Preparation and selectivity](claims/incoming/channel-gating-evidence.md#chloride-leak)

The ten-channel Na⁺/K⁺ comparison reproduced the errors below on the checkout containing the new chloride law. Across the two checkpoints, all ten targeted engine tests and the 82 always-run guards passed. Test collection at the chloride revision gained exactly the three new chloride cases and retained all 20,206 previous test IDs. Five existing missing-fixture collection errors persisted. [Chloride engine tests](../tests/unit/test_chloride_leak_law.py) · [Na⁺/K⁺ comparison](checks/ion_channels.py)

## 19 November 2026 · Ten ion-channel laws

For the eight voltage-dependent channel laws in `resolved_pump_tissue@3`, Lean proves that both gate targets lie in [0, 1] and both time constants are positive over the declared −120 to +60 mV domain. The exponential stage keeps the opening in [0, 1] for any nonnegative duration and any pair of admissible endpoint voltages. The proof covers the polynomial branch at small steps and the regularized NaV1.2 rates. The two gate-free leak laws have intrinsic opening one. On the permeant ion, opening times external availability scales the signed constant-field flux. The channel debits the cell and credits its exterior by that same flux. All other species receive zero. These theorems use the Cells constant-field and transfer proofs and Mathlib’s exponential inequalities. The 14 new theorems use only the standard Lean axioms. [Stage proof](CellsProofs/Transport/ChannelStep.lean) · [Channel laws and booking](CellsProofs/Transport/IonChannels.lean) · [Tissue stage](../src/cells/models/surface_pump_v3.py#L1257)

The CPU driver checks each law’s declared ion and opening powers against Lean and the compiled tissue dispatcher. For the five Kv1 laws with coefficient tables it also checks the Lean targets and time constants against the engine’s table entries symbolically. Scalar references in mV and ms cover all eight gated laws at 25 voltages, including NaV1.2’s removable singularities. In 72 additional stage cases the driver checked every combination of gate and endpoint targets at zero or one, including the floats immediately below and above the series switch. [Driver and synthetic world](checks/ion_channels.py) · [Kv1 reference](../validation/tissue/kv1_reference.py) · [Kir2.1 reference](../validation/tissue/kir_reference.py) · [NaV1.2 reference](../validation/tissue/sodium_reference.py)

One cell with a held bath carried all ten channels on one membrane. An external block lasted 0.24414 ms. All eight gate pairs moved during the block while every transfer stayed zero. After release the potassium routes carried outward flux and both sodium routes carried inward flux. Each channel’s flux and cumulative transfer, the cell and reservoir inventories, and the membrane voltage were checked against a separate adaptive integration of the capacitor and material balances with Decimal rates. Every off-ion and padding transfer was zero. The test used the ARS(2,2,2) integrator in float64. The driver took 29.62 s on four CPU cores. [Outward flux in the host](../src/cells/models/surface_pump_v3.py#L358) · [Independent constant-field calculation](../validation/betse/junction_transport/check.py#L10)

```json
{
  "engine_revision": "ec46f7a4e940b86c6fc110230b2bd851081dee50",
  "model": "resolved_pump_tissue@3", "backend": "cpu", "dtype": "float64",
  "solver": "imex_ars222_face_electromigration@1", "independent_solver": "DOP853",
  "dt_s": 0.0000019073486328125, "release_s": 0.000244140625, "end_s": 0.0009765625,
  "voltages": 25, "gate_pairs": 6, "stage_cases": 72, "max_stage_error": 2.220446049250313e-16,
  "max_target_error": 2.220446049250313e-16, "max_tau_error_s": 1.7763568394002505e-15,
  "max_opening_error": 2.7755575615628914e-17, "max_tissue_gate_error": 4.3100384372607436e-11,
  "max_flux_error_over_channel_peak": 3.8995113287681594e-10, "max_transfer_error_fmol": 2.3651329705171267e-13,
  "final_voltage_V": -0.039793205071044134, "gate_atol": 2e-6, "flux_atol_over_channel_peak": 2e-6, "material_atol_fmol": 1e-10
}
```

**Biological comparison.** Rat Kv1.1 whole-cell currents in CHO cells at 25 °C had a fitted decay time of 313 ± 82 ms (SD) at −20 mV. Under an assumed equilibrated −80 mV hold the same fit on the Cells current gave about 8.0 s, beyond the 1.5 s pulse. The model retained 88.3% of its peak current at pulse end. For adult human NaV1.2 at room temperature, the model current's 10–90% rise was 0.296 ms versus 0.38 ± 0.05 ms measured (SEM). Its inactivation midpoint was −54.9 mV versus −63.53 ± 0.79 mV. These are descriptive whole-current comparisons for the specified preparations. The evidence note also records the limitations for the other isoforms and the generic leak laws. [Search agent’s evidence and protocols](claims/incoming/channel-gating-evidence.md) · [Reproduce both model traces](checks/channel_clamp_evidence.py) · [Ranjan et al., Fig. 2C](https://doi.org/10.3389/fncel.2019.00358) · [Begemann et al., Table 2](https://doi.org/10.1186/s10020-019-0073-6)

For rat Kv1.4 a 3.2 s depolarization from −80 to 0 mV left **less than 2%** of peak oocyte patch current. Cells retained **0.57%**. Four published voltage-dependence parameters coincide with the engine’s, which limits the independence of this comparison. In a separate 30 °C HEK293 preparation, a +40 mV pulse elicited two fitted decay components. The Cells law has a single inactivation gate and retained 21.0% of its peak at 200 ms under that pulse. [Stühmer et al., Table I and Fig. 6](https://doi.org/10.1002/j.1460-2075.1989.tb08483.x) · [Roeper et al., Fig. 1](https://doi.org/10.1523/JNEUROSCI.17-10-03379.1997) · [Pulse calculations and definitions](checks/channel_clamp_evidence.py)

## 19 November 2026 · Hill activation and inhibition

The optional `grn-lean` check recompiled the original scalar monotonicity proofs and both Cells specializations on Lean 4.19.0. The axiom reports contain only `propext`, `Classical.choice` and `Quot.sound`. On the engine's 6 × 5 × 9 grid of half-saturations, exponents and concentrations, the compiled CPU factors were compared with the upstream formula evaluated at 65-digit precision using the exact binary inputs. All three engine Hill tests also passed, including the reaction-rate comparison in `resolved_pump_composite@1`. [Proof and upstream pin](checks/hill/check.sh) · [Numerical driver](checks/hill/compare.py) · [Reaction operator comparison](../tests/unit/test_hill_factors.py) · [Chemistry library assessment](ENGINE_LAW_VERIFICATION.md#chemistry-libraries-tested-against-cells)

```json
{
  "engine_revision": "6d74998581eab13d45327bc4801b463d0fb7a6f7",
  "grn_revision": "070ba8da6a09bdc4b0550396c61611668768bc0b",
  "backend": "cpu", "dtype": "float64", "cases": 540, "atol": 8.881784197001252e-16,
  "max_abs_error": {"hill_activation": 4.440892098500626e-16, "hill_inhibition": 4.718447854656915e-16}
}
```

## 19 November 2026 · Voltage-gated junction conductance

At a fixed junction voltage the law has one equilibrium conductance and one relaxation time. Lean proves that increasing voltage magnitude lowers the equilibrium when the residual fraction is below one. Starting anywhere in the allowed interval preserves its bounds. Reversing voltage polarity preserves the clamped trajectory, and splitting a constant-voltage interval preserves its final conductance. For three equally spaced samples of the deviation from equilibrium, the middle sample squared equals the product of its neighbors. Two exponential decays with positive amplitudes and distinct rates give a strict inequality instead. [Proof](CellsProofs/Transport/JunctionGate.lean) · [Rate equation and clamp update](../src/cells/laws/junctions/junction_voltage_relaxation.py#L41)

The compiled clamp update matched the reference at 45 voltage–time combinations. In a separate 62.5 ms run of `resolved_pump_tissue@3`, three cell pairs carried only a neutral tracer so their voltage differences stayed fixed at −80, 0 and +80 mV. External availability was zero for 31.25 ms. Tracer flux remained zero during the block while the intrinsic gates moved from 0.9 to **0.528734, 0.908373 and 0.528734**. On release the flux immediately reflected those three values. Both cell inventories and the junction transfers matched the integrated neutral-tracer solution. The reference evaluates the two voltage rates with 65-digit decimal arithmetic. The driver took 23.99 s on four CPU cores. Nineteen existing rate, clamp and host tests passed. [Driver and input world](checks/junction_gate.py) · [Scalar reference](../validation/betse/junction_gate/reference.py#L9) · [Clamp protocol](../validation/betse/junction_gate/protocol.json) · [Transport availability](../src/cells/models/surface_pump_v3.py#L733) · [Intrinsic gate derivative](../src/cells/models/surface_pump_v3.py#L779)

In seven wild-type Cx43 cell pairs, voltage-clamp fits gave residual normalized conductances of **0.35 ± 0.01** on the positive branch and **0.33 ± 0.01** on the negative branch (SEM). At −100 mV the same preparation showed a fast **70 ± 5 ms** decay and a slow **931 ± 54 ms** decay. The Cells reference parameters give **one 50.001 ms** time constant at that voltage. The two measured components limit the model's use for the full Cx43 trace. The voltage series leaves exact transient polarity symmetry and the external availability factor open. [Evidence note and normalization](claims/incoming/junction-gate-evidence.md) · [Sahu and Bera, Table 2 and Figure S2](https://pmc.ncbi.nlm.nih.gov/articles/PMC3607587/)

```json
{
  "engine_revision": "6d74998581eab13d45327bc4801b463d0fb7a6f7",
  "model": "resolved_pump_tissue@3", "law": "junction_voltage_relaxation@1",
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1", "jaxlib": "0.11.1",
  "threshold_V": 0.015, "residual_fraction": 0.1, "initial_gate": 0.9,
  "clamp_samples": 45, "max_clamp_error": 1.1102230246251565e-16,
  "max_three_sample_residual": 5.551115123125783e-17, "tau_at_minus_100_mV_ms": 50.000551675513144,
  "solver": "rk4", "dt_s": 0.00006103515625, "release_s": 0.03125, "duration_s": 0.0625,
  "junction_voltages_V": [-0.08, 0, 0.08], "gate_at_release": [0.5287339724666028, 0.908373067432633, 0.5287339724666028],
  "release_flux_fmol_s": [0.10574679449332056, 0.18167461348652658, 0.10574679449332056],
  "final_transfer_fmol": [0.002614271383999489, 0.0056791335747008315, 0.002614271383999489],
  "max_tissue_gate_error": 5.9396931817445875e-15, "max_transfer_error_fmol": 8.673617379884035e-18,
  "gate_atol": 5e-12, "flux_atol_fmol_s": 3e-12, "material_atol_fmol": 1e-10
}
```

## 19 November 2026 · Sodium-potassium and calcium pump charge

A forward Na⁺/K⁺-ATPase cycle exports three Na⁺ and imports two K⁺. The Cells plasma-membrane calcium pump exports one Ca²⁺ per forward cycle. Their outward charge flux in elementary-charge equivalents is therefore `J_NaK + 2 J_Ca`. Lean connects that count to the voltage term in the free energy of both pumps and proves each pump’s stall voltage and forward direction. Each pump runs forward above its own stall voltage when voltage is measured inside relative to outside. The seven theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ElectrogenicPumps.lean) · [Na⁺/K⁺ rate](../src/cells/laws/pumps/nak_atp_mass_action_positive.py#L63) · [Calcium rate](../src/cells/laws/pumps/ca_atp_mass_action_positive.py#L88) · [Ion flux and electrode current](../src/cells/models/surface_pump_v3.py#L783)

We initialized five independent cells in `resolved_pump_tissue@3` at each predicted stall, at the midpoint and 10 mV beyond each end of the interval. Each cell had its own held bath, the same maintained fuel concentrations and only the two pumps carrying current. Two independent 80-digit scalar calculations supplied the initial reference rates. The compiled tissue rates and energies matched at all five voltages, with stalls at **−99.365 mV for Na⁺/K⁺** and **−104.104 mV for Ca²⁺**. At the midpoint, we chose the calcium capacity so the two initial currents would cancel. Each contributed about 0.349 pA in opposite directions. The compiled electrode current was 2.04 × 10⁻²⁶ A. The 1 ms run accounted for Na⁺, K⁺ and Ca²⁺ in both the cells and the reservoirs and booked positive heat for each midpoint pump. The cancellation is an initial condition. The driver took 29.32 s on four CPU cores. Nine existing pump and declaration tests passed. [Driver and inputs](checks/electrogenic_pumps.py) · [Na⁺/K⁺ reference](../validation/betse/pump_contact/pump_reference.py#L83) · [Calcium reference](../validation/chemistry/finite_calcium_pump_reference.py#L19) · [Calcium tolerances](../validation/chemistry/finite_calcium_pump_protocol.json)

The experimental comparisons constrain the ion counts. Squid axon measurements pair sodium flux with electrical current, while red-cell ghosts pair sodium loss with ATP hydrolysis. In purified pig-brain calcium pumps, the measured Ca²⁺ and ATP rates give 1.02 Ca²⁺ per ATP. Including the measured inward H⁺ flux gives about +1.4 net charges per ATP in that preparation. The Cells law books +2 because calcium is its only transported ion. Applying its current to this preparation would require accounting for the protons. Experimental validation of the two calculated stall voltages remains open. [Measurements, conditions and uncertainties](claims/incoming/pump-charge-evidence.md) · [Squid axons, Table I](https://doi.org/10.1085/jgp.93.5.903) · [Red-cell ghosts](https://doi.org/10.1113/jphysiol.1967.sp008297) · [Calcium and proton flux, Table I](https://doi.org/10.1074/jbc.273.29.18230)

```json
{
  "engine_revision": "a06ee308a8348a5392e4645ccc368ccf8a086604",
  "model": "resolved_pump_tissue@3",
  "laws": ["nak_atp_mass_action_positive@1", "ca_atp_mass_action_positive@1"],
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1", "jaxlib": "0.11.1",
  "solver": "rk4", "dt_s": 0.00005, "duration_s": 0.001, "temperature_K": 298.15,
  "concentrations_mM": {"inside": {"Na": 12, "K": 140, "Ca": 0.0001}, "bath": {"Na": 145, "K": 5, "Ca": 2}, "maintained": {"ATP": 1.5, "ADP": 1, "Pi": 5}},
  "delta_g0_1M_J_mol": -30500, "nak_capacity_fmol_s": 0.1, "calcium_capacity_fmol_s": 0.1574830840232326,
  "initial_voltages_V": [-0.11410448475867015, -0.10410448475867015, -0.10173467077150977, -0.09936485678434939, -0.0893648567843494],
  "nak_stall_V": -0.09936485678434939, "calcium_stall_V": -0.10410448475867015,
  "max_cycle_error_fmol_s": 3.5041414214731503e-16, "max_current_error_A": 3.7966297646476856e-26,
  "midpoint_cycles_fmol_s": [-0.00361764979679795, 0.001808824898399081],
  "midpoint_electrode_current_A": 2.0419795228050456e-26,
  "midpoint_heat_pJ": [8.268047906450134e-7, 7.244105791341412e-7],
  "cycle_atol_fmol_s": 2e-12, "current_atol_A": 2e-22, "integrated_inventory_atol_fmol": 1e-15
}
```

## 19 November 2026 · ATP-driven transport

An enabled ATP cycle runs forward when its total free-energy change is negative, reverses when it is positive, and stalls at zero. Positive flux moves cargo from N to P and consumes ATP on side N. Lean proves these statements for the two branches of the engine’s rate formula and proves nonnegative heat in either direction. For a proton pump moving `n` protons per ATP, the stall voltage is `V_N − V_P = (RT/F) ln(a_P/a_N) + ΔG_fuel/(nF)`. For a neutral cargo, voltage drops out of the rate at fixed activities and capacity. All eight theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ATPCycle.lean) · [Proton cycle](../src/cells/laws/pumps/proton_pump.py#L223) · [Neutral cycle](../src/cells/laws/pumps/atp_transporter.py#L135) · [Shared rate formula](../src/cells/laws/cycles/forms.py#L893)

The compiled `resolved_pump_tissue@3` transporter matched the independent reference values at 92 states. Each of the four panels had 18 forward cases, four reverse cases and one nominal stall within the reference roundoff band. Heat was nonnegative at all 92 states. Disabling availability or setting capacity to zero gave exactly zero cycles, heat and work in all eight controls. At fixed chemistry, shifting the proton pump’s voltage by −10 or +10 mV about stall gave **−0.023228** and **+0.010986 fmol/s** respectively. The same offsets left all three flowing neutral controls unchanged. The driver took 4.52 s on four CPU cores. Six existing tests passed in 49.20 s, including two 4 ms tissue trajectories checking the material, charge and energy accounts. [Compiled comparison](checks/atp_cycle.py) · [Reference inputs](../validation/core_seams/references/reference_inputs.json) · [Frozen values](../validation/core_seams/references/designs/core_seams_reference_values.json) · [Reference tolerances](../tests/unit/test_cycle_kind_references.py#L296) · [Neutral run](../tests/unit/test_transporter_kind.py#L197) · [Proton run](../tests/unit/test_transporter_kind.py#L329)

```json
{
  "engine_revision": "a6f4c7d9b8e84cbd7c23264215510ba93fb8e3d3",
  "model": "resolved_pump_tissue@3", "kind": "cells.transporter@1",
  "laws": ["proton_atp_mass_action_positive@1", "atp_driven_transporter_mass_action_positive@1"],
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1",
  "states_by_panel": {"v1_proton_n2": 23, "v1_neutral_n1": 23, "v1_neutral_n2": 23, "ff_neutral_n1": 23},
  "forward": 72, "reverse": 16, "within_stall_band": 4, "off_controls": 8,
  "max_abs_error": {"dG_RT": 6.466044960882567e-15, "cycles_fmol_s": 7.494005416219807e-16,
                    "heat_pJ_s": 3.9968028886505635e-15, "work_pJ_s": 3.907985046680551e-14},
  "max_error_in_reference_floors": 0.441238400426874, "allowed_floors": 16
}
```

**Biological comparison.** Kettner et al. measured ATP-dependent current in isolated yeast vacuoles. At cytosolic pH 8.5 and vacuolar pH 5.0, Table 2 gives a mean reversal of **−17.5 ± 5 mV** (standard error, six trials). Using the paper’s estimated hydrolysis voltage and proton gradient, the proved stall relation gives `−587.5/2 + 207.2 = −86.55 mV` for two tightly coupled protons per ATP. The paper tabulates −86.5 mV, **69.0 mV below the observed mean**. Both use cytosol-minus-vacuole voltage. This comparison uses the authors’ fuel estimate and assumed coupling. They attribute the shifted current reversal to a parallel proton shunt. The neutral case has a separate experimental lead. Van Herwaarden et al. measured ATP-dependent riboflavin uptake into inside-out vesicles in Fig. 3E. A test of voltage independence needs matched gradients and multiple imposed voltages. [Kettner et al., Table 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC1303676/) · [Van Herwaarden et al., Fig. 3E](https://pmc.ncbi.nlm.nih.gov/articles/PMC1800714/)

## 19 November 2026 · Membrane insertion heat

Both versions of `scheduled_membrane_insertion` add uncharged membrane at fixed free-node charges and held bath potentials. They call `fixed_charge_change` and require every booked patch heat to be finite and at least zero. Lean shows that the exact field equations give the network heat in pJ as `(10¹²/2) Σ [C(ΔV)² + ΔC(V + ΔV)²]`. Here `V` is the old patch voltage and `ΔV` its change. Each term is nonnegative for nonnegative capacitances and additions. In one patch against a held bath, the heat is `(10¹²/2) C V² ΔC/(C + ΔC)` and the bath’s image charge change is exactly zero. All seven public theorems use the standard Lean axioms. [Proof](CellsProofs/Tissue/MembraneInsertion.lean) · [Shared field calculation](../src/cells/models/pump_composite_adapter.py#L959) · [Version 1 guard](../src/cells/operators/membrane_insertion.py#L424) · [Version 2 guard](../src/cells/operators/membrane_insertion_v2.py#L244)

**Engine finding, confirmed by the Cells lead.** Both operators refuse a 1 ms step on an admitted one-patch input with `ΔC/C = 1.7 × 10¹⁶` per initial half-step. The compiled CPU half-step computes **−0.043037 pJ**. An 80-digit calculation at the same initial charge gives **+0.051603 pJ**. The first energy term alone is about 8.77 × 10¹⁴ pJ, with float64 spacing of 0.125 pJ. The implementation adds a nearly equal correction of opposite sign. This stress input doubles the area on the first half-step using an extreme inserted specific capacitance of 8.5 × 10¹⁴ F/m². All 12 ordinary control half-steps passed at the existing relative tolerance of 10⁻⁹, and both 1 ms control runs completed. Four existing tests also passed, including two clamps and a finite cleft. [Reproducer](checks/membrane_insertion.py) · [One-patch fixture and tolerance](../tests/unit/test_membrane_insertion.py#L145) · [Two-version comparison](../tests/unit/test_membrane_insertion_v2.py#L203)

The same field solve gives **+0.051603 pJ** with the sum of squares. Substituting that heat alone in a separate diagnostic run exposed an electrode accounting failure. The unmodified field calculation gives **−3.638 × 10⁻¹² C** of bath image charge for this single patch. With the sum-of-squares heat and the known single-patch image charge of zero substituted, both runs completed. Multi-patch worlds can have real image charge at individual baths. The single-patch control isolates the two calculations involved in this refusal. [Image charge and heat](../src/cells/models/pump_composite_adapter.py#L985) · [Diagnostic controls](checks/membrane_insertion.py)

The lead assigned the robustness fix to the operators owner. The proposed change uses sum-of-squares heat and a cancellation-free image charge exact for one patch. A bitwise comparison of recorded worlds determines whether it lands with the declared numerical freeze batch. The failed comparison above records the original engine behavior. [Existing heat calculation for charge-following transfer](../src/cells/models/pump_composite_adapter.py#L1095)

```json
{
  "engine_revision": "06e25525a39f3a2995bd5aa26a7e38bd67b211c3",
  "model": "resolved_pump_composite@1", "inner": "resolved_pump_tissue@3",
  "operators": ["scheduled_membrane_insertion@1", "scheduled_membrane_insertion@2"],
  "backend": "cpu", "dtype": "float64", "jax": "0.11.1", "jaxlib": "0.11.1",
  "half_step_s": 0.0005, "end_s": 0.001,
  "control_ratios": [0, 0.000001, 0.5, 1, 5, 1000], "control_cases_passed": 12,
  "max_control_relative_heat_error": 1.857494947841975e-14, "heat_rtol": 1e-9,
  "stress_ratio": 1.7e16, "stress_specific_capacitance_F_per_m2": 8.5e14,
  "initial_capacitance_F": 1.6306360828084532e-11, "initial_charge_C": -1.2972730823853619e-12,
  "computed_heat_pJ": -0.04303697682917118, "reference_heat_pJ": 0.05160309734417014,
  "sum_of_squares_pJ": 0.05160309734417019,
  "computed_image_C": -3.637978807091713e-12, "reference_image_C": 0,
  "stress_runs": {"original": "both refused the first step", "heat_only": "both failed electrode accounting",
                  "heat_and_single_patch_image": "both completed"}
}
```

## 19 November 2026 · Passive proton leak

For `proton_constant_field_leak@1`, an open route carries free H⁺ inward when the outside concentration exceeds the reversal concentration. With `x = F V/(RT)`, inside-minus-outside voltage and evaluator `B`, Lean gives that concentration as `hIn × B(−x)/B(x)` on both engine branches. The analytic constant-field law reverses at `V = (RT/F) × (ln hOut − ln hIn)` and releases nonnegative instantaneous heat. Those results also apply to the engine’s real-arithmetic formula at zero and for `|x| ≥ 10⁻⁴`. All seven public theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ProtonLeak.lean) · [Engine flux and heat](../src/cells/laws/transport/proton_leak.py#L28) · [Bernoulli evaluator](../src/cells/laws/electrochemistry.py#L17) · [Goldman’s constant-field model](https://doi.org/10.1085/jgp.27.1.37)

Inside the small-voltage branch the polynomial shifts the reversal ratio. At `x = 0.00009`, an 80-digit calculation found `B(−x)/B(x) − exp(x) ≈ 1.582 × 10⁻³³`, below float64 spacing near 1. Halfway between the thresholds the polynomial gives outward flux with a positive inward electrochemical drive. This limits the engine docstring’s unconditional instantaneous-heat sign claim. [Reversal calculation](checks/proton_leak.py) · [Engine heat contract](../src/cells/laws/transport/proton_leak.py#L35)

**Lead decision.** A numerical tolerance is sufficient. The instantaneous proton heat feeds the step booking. The charged leak uses the solver’s tableau, and the 16 ε negative-share floor applies to routes eligible for exact booking. The lead will clarify the heat docstring. Exact nonnegativity applies to the analytic law, with the polynomial and float64 covered to numerical tolerance. [Route selection](../src/cells/kinds/passive_routes.py#L246) · [Step booking](../src/cells/kinds/passive_routes.py#L500) · [Exact-share floor](../src/cells/kinds/passive_routes.py#L458)

Twelve compiled CPU float64 cases covered opposing drives, the Nernst crossing, blocking, partial opening and both sides of the two branch boundaries. The flux reference uses 70-digit Decimal arithmetic. In a 4 ms `resolved_pump_tissue@3` run, the buffered cell initially took up **3.310 × 10⁻⁶ fmol/s**. Using total intracellular proton equivalents in the reference gave **−3.183 fmol/s**. Two four-core runs took 13–16 s, and three existing law and tissue tests passed. [Driver](checks/proton_leak.py) · [Flux reference](../validation/betse/junction_transport/check.py#L10) · [Independent buffer closure](../validation/compartment_ph/ph_reference.py#L167) · [Tissue fixture](../tests/unit/test_proton_buffer_kind.py#L258)

```json
{
  "engine_revision": "1dee280f681af373071079c5f9b5921725dc7ed3",
  "model": "resolved_pump_tissue@3", "law": "proton_constant_field_leak@1",
  "backend": "cpu", "dtype": "float64", "component_cases": 12,
  "max_flux_error_fmol_s": 1.543812817544248e-20, "flux_atol_fmol_s": 4.7124e-17,
  "max_heat_error_pJ_s": 2.0328790734103208e-19, "heat_atol_pJ_s": 1.214613282895345e-16,
  "opposed_flux_fmol_s": -1.9698929665489864e-5, "nernst_residual_fmol_s": 4.3159515760814405e-21,
  "small_voltage_x": 0.00009, "outside_inside_ratio_shift": 1.581812000278e-33,
  "end_s": 0.004, "initial_voltage_V": -0.02151770525721294,
  "free_inside_mM": 6.309573444801929e-5, "total_inside_mM": 25.000063095734447,
  "free_outside_mM": 3.981071705534969e-5,
  "initial_inward_fmol_s": 3.3097843238305726e-6, "reference_inward_fmol_s": 3.309784324017176e-6,
  "using_total_inward_fmol_s": -3.183387556995154, "booked_heat_pJ": 1.1771717405987001e-8
}
```

**Biological evidence.** Schilling et al. measured reversal of an activated proton current in Jurkat T cells at 20–23 °C. Figure 2E gives a fitted slope of **−47 mV per unit of outside-minus-inside pH** across six gradients, alongside an ideal Nernst slope of **−58 mV per pH unit**. The observed shift has the predicted direction and is 11 mV per pH unit shallower. The figure reports group means and standard errors. Uncertainty in the fitted slope and the relation between pipette pH and intracellular pH matter for a quantitative comparison. The current amplitude also depends on channel opening. Biological validation of the Cells leak remains open. [Schilling et al., Fig. 2E and Methods](https://doi.org/10.1113/jphysiol.2002.028878)

## 19 November 2026 · Passive neutral permeation

For `passive_neutral_permeation@1`, the zero-valence specialization of the existing constant-field theorem gives inward flux `J = scale × (cOut − cIn)` at any voltage. In a closed pair of fixed positive volumes, the outside-minus-inside concentration difference changes at rate `−k × (cOut − cIn)`, with `k = scale × (1/vIn + 1/vOut)`. The three Lean theorems use the standard axioms `propext`, `Classical.choice` and `Quot.sound`. [Neutral proof](CellsProofs/Transport/NeutralPermeation.lean) · [Engine law](../src/cells/laws/routes/passive_permeation.py#L43) · [Tissue rate bound at full opening](../src/cells/kinds/passive_routes.py#L553)

Five compiled CPU float64 cases exercised both directions, equilibrium, a blocked route and partial opening. With 1 fmol inside 0.5 pL and 2 fmol outside in 2 pL, the solute flowed outward at 50 fmol/s. Following the amount difference would reverse that result. In a separate 20 ms `resolved_pump_tissue@3` run, both final compartment amounts agreed with the independent closed-form solution within the existing relative tolerance. The driver took 9.94 s on four cores and three existing tests passed in 12.21 s. Figure 3 of Lande et al. supplies urea-flux time courses for three liposome compositions. A quantitative comparison needs the gradients, area and permeability of a matched preparation. [Lande et al., Fig. 3](https://doi.org/10.1085/jgp.106.1.67) [Driver](checks/neutral_permeation.py) · [Analytic reference](../validation/passive/passive_reference.py#L66) · [Tissue fixture and tolerance](../tests/unit/test_passive_routes_kind.py#L64)

```json
{
  "engine_revision": "f130a109ad8861ce114f0f6fea3ece524465e80f",
  "model": "resolved_pump_tissue@3", "law": "passive_neutral_permeation@1",
  "backend": "cpu", "dtype": "float64", "component_cases": 5,
  "max_flux_error_fmol_s": 7.105427357601002e-15,
  "unequal_volume_inward_flux_fmol_s": -49.999999999999986,
  "end_s": 0.02, "reference_rate_per_s": 99.99999999999999,
  "inward_transfer_fmol": -0.0002160443856244789, "reference_transfer_fmol": -0.00021616617919084682,
  "max_final_amount_error_fmol": 1.2179356636795365e-7,
  "max_final_amount_relative_error": 0.0001700632756849268, "final_amount_rtol": 5e-4
}
```

## 19 November 2026 · Biological evidence review

The first literature handoff covered 11 of the 12 claims registered at review time. The reaction time courses below give a direct comparison of two measured pools. At this checkpoint, 11 biological claims were open and the retrospective RPTEC comparison was not assessable. [Claim index](README.md#proof-index) · [RPTEC closeout](../reports/BIO003_PILOT_CLOSEOUT.md)

**Reaction inventory.** Eicher et al. measured glucose-6-phosphate and fructose-6-phosphate separately by ³¹P NMR. In their supplementary workbook `supp_data.ods`, the upper block of sheet `PGI` contains five time courses of peak integrals expressed in mM. For dataset 1, summing cells B4 and C4 gives 8.395747 mM at 1.33 min. B30 and C30 give 7.782390 mM at 35.91 min. The measured soluble pool changed by **−0.613357 mM (−7.31%)**. Three of the five courses decreased between their own first and last readings and two increased. Figure 4A reports a nominal starting condition and rounded endpoints with 60° pulses. Figure 5 uses 90° pulses. To interpret the drift, quantify the shared calibration uncertainty and any unobserved pools. Only the first listed acquisition has raw data in the supplement. Its metadata give 0.950 mL and 1.40 min per acquisition. The standard assay gives 1.00 mL and the workbook uses 1.33 min. Per-course volumes and timing remain unresolved. [Reaction claim](claims/reaction-inventory.md) · [Eicher et al., Figs. 4–5 and §3.3](https://www.mdpi.com/2218-1989/2/4/818) · [Publisher’s workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

| Claims | What the published evidence can test |
| --- | --- |
| Junction gradient, reversal, blocking and transfer orientation | Figure 2B of Palacios-Prado and Bukauskas tracks a charged tracer moving between two cells near zero junction voltage. The flux trace is normalized. Zonta et al. estimated **226 ± 75 calcein molecules/s per open Cx26 channel** at a 125 μM gradient. Only the donor was voltage-clamped during that transfer interval. Figure 1 of Wang and Veenstra shows paired electrical currents. The bovine block and washout traces are **Wang et al. (2010), Fig. 2E–F**. A species-specific rate needs ion or tracer calibration, and a quantitative blocking test needs a residual detection limit. [Tracer](https://pmc.ncbi.nlm.nih.gov/articles/PMC2736430/) · [Calibrated calcein flux, Fig. 1A–C](https://doi.org/10.1186/1478-811X-11-15) · [Paired currents](https://pubmed.ncbi.nlm.nih.gov/9101407/) · [Block study and byline](https://pubmed.ncbi.nlm.nih.gov/20089928/) |
| Extracellular face direction and dissipation | Weber et al. (Fig. 6) measured net current reversal across a claudin pore. Galvez et al. (Fig. 3 and Tables 1–2) measured sodium tracer fluxes in epithelia with active uptake. Passive-face power needs signed net flux, activities and voltage across the same passive path. [Claudin recordings](https://elifesciences.org/articles/09906) · [Sodium flux measurements](https://www.zoology.ubc.ca/~woodcm/Woodblog/wp-content/uploads/2016/07/Galvez-et-al.-2008-In-Vitro-Cell.pdf) |
| Regional transfer and reaction–transport inventories | Kuki et al. (Figs. 3–4) compared myocardial K⁺ depletion and coronary effluent loss in separate preparations. Fausto (Fig. 1) tracked carbon-6 label across tissue, perfusate, bile and CO₂. A closure residual needs amounts on a common boundary and time interval, with sampling and omitted pools accounted for. [Heart potassium](https://doi.org/10.1161/01.RES.67.2.401) · [Liver tracer](https://doi.org/10.1042/bj1290811) |
| Enzyme and substrate inventories | The isomerase NMR study resolves bound ligand states. The chymotrypsin mass spectra resolve an enzyme intermediate. Testing both inventories needs calibrated amounts of free enzyme, substrate, complex and product in the same preparation. [Bound states, Figs. 3–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC1794347/) · [Enzyme intermediate, Figs. 1–3](https://www.derekwilsonlab.ca/userfiles/files/TRMS_Applied_to_Enzymes.pdf) |
| RPTEC C3 voltage | Bonzanni et al. (Fig. 3C) reported 20 cells across three experiments. The ±2 mV in the Cells record is figure-reading uncertainty. Experiment-level uncertainty for the +3.41 mV prediction residual is unresolved. [Primary study](https://doi.org/10.1242/bio.048553) · [Existing comparison](claims/rptec-voltage-c3.md) |

**Single-site binding** was the missing claim. A primary lead is the human myoglobin oxygen-equilibrium study by Rossi-Fanelli and Antonini. Look for observed site occupancy across known free ligand values, record temperature and solution conditions, and identify which observations set the affinity and which test it. For oxygen pressure, report the solubility used to convert to dissolved concentration or compare the dimensionless pressure ratio at the same temperature. A myoglobin comparison would test the one-site curve in that preparation. [Cells binding claim](claims/single-site-binding.md) · [Human myoglobin study](https://pubmed.ncbi.nlm.nih.gov/13584010/)

**Research follow-up.** I reproduced the proposed within-figure comparison for human myoglobin at 10 °C. Of the first five published digitized points, fitting the first and fourth gave a half-saturation pressure of 0.3311 Torr. The other three had a root-mean-square occupancy residual of 0.0422. This retrospective split shares a preparation and a figure, with unknown pointwise uncertainty. The PGI workbook gave first-to-last changes in measured G6P + F6P of −0.613357, −1.534898, +0.099302, +0.391083 and −0.207509 mM for datasets 1–5 respectively. Both biological assessments remain open. [Myoglobin experiment](https://pubmed.ncbi.nlm.nih.gov/13584010/) · [Caltech’s Fig. 2 digitization](https://bi1.caltech.edu/2017/code/t05_nonlinear_regression.html) · [PGI workbook](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

## 19 November 2026 · Single-site binding and face-power units

For `rapid_binding@1`, Lean derives the bound fraction from equal forward and reverse rates and recovers the same fraction from the two form weights used by Cells. The local proof specializes the Langmuir argument to a free ligand concentration and a dissociation constant, both in mM. The comparison ran the compiled law on all thirteen manufactured S1 states and the stage read on the first state in `resolved_pump_tissue@3`. Reference tolerances are twice the recorded floor on the log of each concentration. A common binder total cancels when taking the ratio of two bound fractions. The driver took 5.79 s on four CPU cores. Three existing kernel and tissue checks passed in 6.59 s. Experimental binding data remain open. [Binding proof](CellsProofs/Chemistry/SingleSiteBinding.lean) · [Upstream theorem](https://github.com/ATOMSLab/LeanChemicalTheories/blob/00841fedb86c0af282f515eda7e83a525a42e048/src/adsorption/langmuir_kinetics.lean) · [Driver](checks/single_site_binding.py) · [Independent reference design](../validation/core_seams/references/README.md#L101) · [Tolerance calculation](../tests/unit/test_rapid_binding_kernel.py#L127)

```json
{
  "engine_revision": "9a5bc6b8211847888cbb83c41ad88941bac19213",
  "model": "resolved_pump_tissue@3", "law": "rapid_binding@1",
  "backend": "cpu", "dtype": "float64", "reference": "S1", "states": 13,
  "kd_mM": 9.999999999999994e-5, "fraction_range": [0.038286503882254776, 0.999000999000999],
  "max_fraction_error_vs_reference": 3.3306690738754696e-16,
  "max_fraction_error_vs_formula": 1.1102230246251565e-16,
  "total_ligand_control_failures": 13, "tissue_state_0_fraction": 0.5812579461704979
}
```

For `logmean_electrodiffusion@1`, the default proof checks the exact scale from fmol/s × J/mol to pJ/s. An optional import checks the physical dimensions using ATOMS Lab's amount, time and energy. A first build of upstream revision `de263eed` on Lean 4.19 failed on the newer Mathlib matrix-rank module name. Changing that one import in the build copy let both upstream modules compile. Omitting the molar denominator in a negative control left an uncancelled amount dimension and Lean rejected the equation. The dimension proof uses `propext` and `Quot.sound`. The two binding theorems and scalar conversion also use `Classical.choice`. With compiled Mathlib available, the optional check took 10.09 s including the first source download. Warm default builds measured 4.01 s before the additions and 3.75 s afterward on this checkout. [Units check](checks/units/FacePower.lean) · [Reproduction script](checks/units/check.sh) · [Engine multiplier](../src/cells/numerics/surface_transport.py#L312) · [Pinned package](https://github.com/ATOMSLab/LeanDimensionalAnalysis/tree/de263eed945693058ef2b8a1fa56c2ec5642ea7a) · [SI prefixes](https://www.bipm.org/en/measurement-units/si-prefixes)

## 19 November 2026 · Extracellular face electrodiffusion

Eight Lean theorems check the two log-ratio branches, positivity and symmetry of the implemented mean (including its small-gradient polynomial), flux reversal, equilibrium, direction and instantaneous dissipation per species and per face. They use the standard axioms `propext`, `Classical.choice` and `Quot.sound`. The force is sender minus receiver electrochemical potential. The direction equivalence requires a positive face coefficient. [Face proofs](CellsProofs/Transport/LogMeanFace.lean) · [Mean](../src/cells/numerics/extracellular_field.py#L48) · [Flux and power](../src/cells/numerics/surface_transport.py#L292)

The development comparison ran eleven CPU float64 cases and one closed `resolved_pump_tissue@3` world with `logmean_electrodiffusion@1`. For each active species and face at each observation time, the independent scalar mean and the declared geometry gave a reference flux. The driver took 17.46 s on four cores. Sixteen existing surface and scalar-reference tests passed in 8.91 s. [Inputs and JSON results driver](checks/logmean_face.py) · [Independent reference](../validation/tissue/surface_reference.py#L13) · [Tolerances](../validation/tissue/surface_protocol.json#L27)

At zero voltage, concentrations of 100.00000000000001 and 100 mM gave a positive reference flux and zero computed flux. The engine subtracts the two rounded logs in its driving force. The difference falls within the protocol's absolute flux tolerance. At a resolved gradient, deliberately reversing the flux and both endpoint bookings conserved total material but produced negative power and failed the direction check. These are development checks under supplied or simulated endpoint conditions. Biological face-flux measurements remain open.

```json
{
  "engine_revision": "c9549dfc553ce2e9cce5d05160c24b1879e3077b",
  "backend": "cpu", "dtype": "float64", "component_cases": 11,
  "flux_atol_fmol_s": 3e-12, "physical_rtol": 3e-10,
  "opposed_flux_fmol_s": -0.0004999999999999968,
  "reversed_flux_fmol_s": 0.0004999999999999968,
  "balanced_flux_fmol_s": 3.361730104660899e-18,
  "adjacent_float64": {"flux_fmol_s": 0, "reference_fmol_s": 1.4210854715202002e-18},
  "reversed_flux_control": {"total_rate_fmol_s": 0, "power_pJ_s": -4.522364735283246e-5},
  "tissue": {
    "model": "resolved_pump_tissue@3", "law": "logmean_electrodiffusion@1",
    "solver": "imex_ars222_face_electromigration@1", "samples_species_faces": [3, 4, 5],
    "max_flux_error_fmol_s": 1.496198998029996e-17, "max_abs_transferred_fmol": 9.758954574665261e-6
  }
}
```

## 19 November 2026 · Regional reaction and transport balance

Lean checked the regional balance for a reaction–transport–reaction step and its whole-graph corollary. The proof uses the earlier chemistry theorem separately on each reaction half-step. The transfer theorem cancels every internal edge. Only the reactions inside the chosen region need to balance its inventory. Both results use the standard Lean axioms `propext`, `Classical.choice` and `Quot.sound`. [Regional proof](CellsProofs/Tissue/ReactionTransport.lean) · [Engine split order](../src/cells/models/pump_composite.py#L1308)

The development comparison ran one 50 ms step of `resolved_pump_composite@1` with `local_species_reactions@1` and the `resolved_pump_tissue@3` face solver. Four of the twelve finite extracellular compartments formed the region. A and B interconverted there, while one boundary face brought material in and the other carried it out. Both the individual species balances and the A + B inventory passed. Reversing the larger boundary face in the recorded transfers failed the regional check and passed the whole-chain check. The driver took 17.99 s on four CPU cores. The existing 200-step passive-chain test against the independent reference passed in 19.76 s. [Inputs and driver](checks/regional_balance.py) · [Closed pair](../validation/morphogenesis/mg0c_turing.py#L180) · [Reference test](../tests/unit/test_species_reactions_composition.py#L84) · [Tolerance rule](../tests/unit/test_species_reactions_composition.py#L321)

```json
{
  "engine_revision": "030bd02a5f4bb74d15ef8bde4fdf1db03f69b801",
  "backend": "cpu", "dtype": "float64", "step_s": 0.05,
  "region": ["node_2", "node_3", "node_4", "node_5"],
  "region_balance": {
    "inventory_change_fmol": 1.2526038874940276e-6,
    "boundary_inflow_fmol": 1.2526038874941343e-6,
    "crossing_faces_fmol": {"face_1": 3.5748138477117313e-6, "face_5": -2.322209960217597e-6},
    "reaction_extent_fmol": 1.7563691429785305e-5,
    "max_species_residual_fmol": 9.147955830346444e-20,
    "residual_fmol": -1.0672615135404184e-19, "tolerance_fmol": 5.578917767468619e-17
  },
  "whole_chain": {"residual_fmol": -1.6263032587282567e-19, "tolerance_fmol": 1.7053025658242405e-16},
  "reversed_face": {
    "id": "face_1", "region_residual_fmol": 7.149627695423356e-6,
    "whole_chain_residual_fmol": -1.6263032587282567e-19
  }
}
```

## 19 November 2026 · Closed enzyme reactions

Lean 4.19.0 checked the general conservation theorem, the two enzyme-fixture inventories and the missing-enzyme counterexample. All four use only the standard Lean axioms `propext`, `Classical.choice` and `Quot.sound`. Four additional equalities matched the fixture’s integer columns and weights to the Lean definitions. Replacing the catalytic products with P alone made the column equality fail in Lean. [General theorem](CellsProofs/Chemistry/Stoichiometry.lean) · [Fixture proofs](CellsProofs/Chemistry/Enzyme.lean) · [Declaration](../validation/tissue/species_reactions_fixtures.py#L248)

The development comparison ran one JIT-compiled half-step of `local_species_reactions@1` on `resolved_pump_composite@1` from `enzyme_recipe(1e-12)`. At `cell_0`, X counts substrate (S + C + P) and Y counts enzyme (E + C). The driver took 11.51 s on four CPU cores, including Lean’s declaration check. The two existing tests for stored amounts and refusal of an unbalanced reaction passed in 3.05 s. [Driver and JSON output format](checks/closed_enzyme.py) · [Amount and inventory tolerances](../tests/unit/test_species_reactions_halfstep.py#L275) · [Refusal case](../tests/unit/test_species_reactions_refusals.py#L119)

```json
{
  "engine_revision": "a124c937041353d395732a936a3d2b1001c2b63a",
  "backend": "cpu",
  "dtype": "float64",
  "half_step_s": 0.0125,
  "extent_fmol": {"binding": 1.2338087167211897e-6, "catalysis": 7.711641577505311e-9},
  "max_species_residual_fmol": 1.122318655111948e-20,
  "inventory_residual_fmol": {"X": -1.1206642938868419e-20, "Y": 6.776263578034403e-21},
  "inventory_tolerance_fmol": 6.938893903907228e-18,
  "missing_enzyme": {"inventory_change_per_catalytic_event": {"X": 0, "Y": -1}, "engine_admission": "refused"}
}
```

The conservation theorem applies to any signed reaction extents in exact arithmetic. The CPU result measures the implementation on this fixture. Reaction-rate accuracy and tissue-level composition are separate claims.

## 19 November 2026 · Junction transport

Eight Lean theorems cover the constant-field flux and finite-graph transfer accounting. The development comparison used engine revision `109a7355ed85`, CPU float64 and four CPU cores. The driver took 18.79 s, including the integrated `resolved_pump_tissue@3` world. The 11 component tests passed in 9.46 s. The largest per-cell rate difference from the reference was 1.36 × 10⁻²⁰ fmol/s against a tolerance of 3 × 10⁻¹⁴ fmol/s. Swapping the owners gave a 2.40 × 10⁻⁴ fmol/s discrepancy. The tissue’s potassium transfer reached 2.18 × 10⁻⁶ fmol and its maximum global material residual was 3.25 × 10⁻¹⁹ fmol. The pilot source was checkpointed in `627c376c`. [Comparison](checks/constant_field.py) · [Flux proof](CellsProofs/Transport/ConstantField.lean) · [Accounting proof](CellsProofs/Accounting/Transfer.lean)
