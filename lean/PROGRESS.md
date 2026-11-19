# Cells proof comparisons

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
