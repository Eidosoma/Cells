# Cells proof comparisons

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
