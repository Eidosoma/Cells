# Cells proof comparisons

## 19 November 2026 · Passive proton leak

For `proton_constant_field_leak@1`, an open route carries free H⁺ inward when the outside concentration exceeds the reversal concentration. With `x = F V/(RT)`, inside-minus-outside voltage and evaluator `B`, Lean gives that concentration as `hIn × B(−x)/B(x)` on both engine branches. The analytic constant-field law reverses at `V = (RT/F) × (ln hOut − ln hIn)` and releases nonnegative instantaneous heat. Those results also apply to the engine’s real-arithmetic formula at zero and for `|x| ≥ 10⁻⁴`. All seven public theorems use the standard Lean axioms. [Proof](CellsProofs/Transport/ProtonLeak.lean) · [Engine flux and heat](../src/cells/laws/transport/proton_leak.py#L28) · [Bernoulli evaluator](../src/cells/laws/electrochemistry.py#L17) · [Goldman’s constant-field model](https://doi.org/10.1085/jgp.27.1.37)

Inside the small-voltage branch the polynomial shifts the reversal ratio. At `x = 0.00009`, an 80-digit calculation found `B(−x)/B(x) − exp(x) ≈ 1.582 × 10⁻³³`, below float64 spacing near 1. Halfway between the thresholds the polynomial gives outward flux with a positive inward electrochemical drive. This limits the engine docstring’s unconditional instantaneous-heat sign claim. [Reversal calculation](checks/proton_leak.py) · [Engine heat contract](../src/cells/laws/transport/proton_leak.py#L35)

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

Five compiled CPU float64 cases exercised both directions, equilibrium, a blocked route and partial opening. With 1 fmol inside 0.5 pL and 2 fmol outside in 2 pL, the solute flowed outward at 50 fmol/s. Following the amount difference would reverse that result. In a separate 20 ms `resolved_pump_tissue@3` run, both final compartment amounts agreed with the independent closed-form solution within the existing relative tolerance. The driver took 9.94 s on four cores and three existing tests passed in 12.21 s. Biological measurements of neutral-solute flux remain open. [Driver](checks/neutral_permeation.py) · [Analytic reference](../validation/passive/passive_reference.py#L66) · [Tissue fixture and tolerance](../tests/unit/test_passive_routes_kind.py#L64)

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

**Reaction inventory.** Eicher et al. measured glucose-6-phosphate and fructose-6-phosphate separately by ³¹P NMR. In their supplementary workbook `supp_data.ods`, the upper block of sheet `PGI` contains five time courses of peak integrals expressed in mM. For dataset 1, summing cells B4 and C4 gives 8.395747 mM at 1.33 min. B30 and C30 give 7.782390 mM at 35.91 min. The measured soluble pool changed by **−0.613357 mM (−7.31%)**. Three of the five courses decreased between their own first and last readings and two increased. Figure 4A reports a nominal starting condition and rounded endpoints with 60° pulses. Figure 5 uses 90° pulses. To interpret the drift, quantify the shared calibration uncertainty and any unobserved pools. To express it as an amount, confirm the volume for each run. Section 3.3 gives 1 mL for the standard assay. [Reaction claim](claims/reaction-inventory.md) · [Eicher et al., Figs. 4–5 and §3.3](https://www.mdpi.com/2218-1989/2/4/818) · [Publisher’s workbook and spectra](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

| Claims | What the published evidence can test |
| --- | --- |
| Junction gradient, reversal, blocking and transfer orientation | Figure 2B of Palacios-Prado and Bukauskas tracks a charged tracer moving between two cells near zero junction voltage. The flux trace is normalized. Figure 1 of Wang and Veenstra shows paired electrical currents. The bovine block and washout traces are **Wang et al. (2010), Fig. 2E–F**. A species-specific rate needs ion or tracer calibration, and a quantitative blocking test needs a residual detection limit. [Tracer](https://pmc.ncbi.nlm.nih.gov/articles/PMC2736430/) · [Paired currents](https://pubmed.ncbi.nlm.nih.gov/9101407/) · [Block study and byline](https://pubmed.ncbi.nlm.nih.gov/20089928/) |
| Extracellular face direction and dissipation | Weber et al. (Fig. 6) measured net current reversal across a claudin pore. Galvez et al. (Fig. 3 and Tables 1–2) measured sodium tracer fluxes in epithelia with active uptake. Passive-face power needs signed net flux, activities and voltage across the same passive path. [Claudin recordings](https://elifesciences.org/articles/09906) · [Sodium flux measurements](https://www.zoology.ubc.ca/~woodcm/Woodblog/wp-content/uploads/2016/07/Galvez-et-al.-2008-In-Vitro-Cell.pdf) |
| Regional transfer and reaction–transport inventories | Kuki et al. (Figs. 3–4) compared myocardial K⁺ depletion and coronary effluent loss in separate preparations. Fausto (Fig. 1) tracked carbon-6 label across tissue, perfusate, bile and CO₂. A closure residual needs amounts on a common boundary and time interval, with sampling and omitted pools accounted for. [Heart potassium](https://doi.org/10.1161/01.RES.67.2.401) · [Liver tracer](https://doi.org/10.1042/bj1290811) |
| Enzyme and substrate inventories | The isomerase NMR study resolves bound ligand states. The chymotrypsin mass spectra resolve an enzyme intermediate. Testing both inventories needs calibrated amounts of free enzyme, substrate, complex and product in the same preparation. [Bound states, Figs. 3–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC1794347/) · [Enzyme intermediate, Figs. 1–3](https://www.derekwilsonlab.ca/userfiles/files/TRMS_Applied_to_Enzymes.pdf) |
| RPTEC C3 voltage | Bonzanni et al. (Fig. 3C) reported 20 cells across three experiments. The ±2 mV in the Cells record is figure-reading uncertainty. Experiment-level uncertainty for the +3.41 mV prediction residual is unresolved. [Primary study](https://doi.org/10.1242/bio.048553) · [Existing comparison](claims/rptec-voltage-c3.md) |

**Single-site binding** was the missing claim. A primary lead is the human myoglobin oxygen-equilibrium study by Rossi-Fanelli and Antonini. Look for observed site occupancy across known free ligand values, record temperature and solution conditions, and identify which observations set the affinity and which test it. For oxygen pressure, report the solubility used to convert to dissolved concentration or compare the dimensionless pressure ratio at the same temperature. A myoglobin comparison would test the one-site curve in that preparation. [Cells binding claim](claims/single-site-binding.md) · [Human myoglobin study](https://pubmed.ncbi.nlm.nih.gov/13584010/)

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
