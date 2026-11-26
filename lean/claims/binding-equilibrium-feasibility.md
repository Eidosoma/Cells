<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Which ligand totals admit a positive binding equilibrium?

A finite binding ensemble has exactly one positive equilibrium if and only if every normalized nonnegative weighting of the held ligands leaves strictly positive room above the lowest projected binder inventories. Fixing the unheld activities gives the same criterion on the held rows. Positive held totals guarantee feasibility whenever each binder has a zero-count base form.

## Assumptions

- The model uses ideal activities, finite standard log weights, nonnegative binder totals and a finite nonempty set of chemically present forms per binder. Relative ligand counts are signed integers.
- Free concentrations are exponentials of finite real log concentrations in a common mM frame. Each unheld free concentration is fixed and positive.
- The existence proof uses every nonnegative direction in the unit simplex. The finite vertex claim proves the reduction for one and two ligands and for common lowest forms in any dimension. Engine enumeration and the finite Newton budget receive separate implementation checks.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.BindingFeasibility.equilibrium_has_margin](../CellsProofs/Chemistry/BindingFeasibility.lean#L55)
- [CellsProofs.Chemistry.BindingFeasibility.equilibrium_of_margin](../CellsProofs/Chemistry/BindingFeasibility.lean#L216)
- [CellsProofs.Chemistry.BindingFeasibility.existsUnique_equilibrium_iff](../CellsProofs/Chemistry/BindingFeasibility.lean#L264)
- [CellsProofs.Chemistry.BindingFeasibility.existsUnique_held_equilibrium_iff](../CellsProofs/Chemistry/BindingFeasibility.lean#L306)
- [CellsProofs.Chemistry.BindingFeasibility.positive_totals_admit_equilibrium](../CellsProofs/Chemistry/BindingFeasibility.lean#L324)

Direct proof subject `cells.binding.rapid_binding@1`

Proof sources [Mathlib compactness of the ligand simplex, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Convex/Topology.lean#L74-L79) · [Mathlib extreme value theorem for a continuous potential, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Topology/Order/Compact.lean#L268-L276) · [Mathlib derivative at a local minimum, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/LocalExtr/Basic.lean#L253-L255) · [Cells equilibrium total and uniqueness](../CellsProofs/Chemistry/BindingEquilibrium.lean)

Uses [Prescribed totals admit at most one binding equilibrium](binding-equilibrium-unique.md)

## Numerical comparison

**Failed.** Across the 80 registered states, both CPU backends agreed with independent binder allocations on all 236 nonempty held-coordinate projections and all four C4 challenge cases. At float64 resolution both kernels admitted an exact zero margin and refused a positive margin of 2⁻⁵⁴ mM. NumPy also admitted a negative margin of −2⁻⁵³ mM which compiled JAX CPU refused. The current tissue parser rejects nonpositive H inventories.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Form weights, residual and convex potential](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/src/cells/laws/reactions/rapid_binding.py#L12-L39) · [Numerical margin and verdict](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/src/cells/laws/reactions/rapid_binding.py#L233-L277) · [Finite vertex enumeration](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/src/cells/laws/reactions/rapid_binding.py#L284-L339) · [Tissue host domain for signed totals](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/src/cells/kinds/proton_buffer.py#L83-L88) · [Registered counts and inventories](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/validation/core_seams/references/reference_inputs.json) · [Independent frozen C4 reference margins](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/validation/core_seams/references/designs/core_seams_reference_values.json) · [C4 kernel cases](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/tests/unit/test_rapid_binding_kernel.py#L189-L273) · [Tissue fixtures and release-step scope](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/tests/unit/test_rapid_binding_world.py#L231-L279) · [Exact feasibility proof](https://github.com/Eidosoma/Cells/blob/1d9fe4e10ac7a4a0a9d9e0edf9a3c0e0cb0a914a/lean/CellsProofs/Chemistry/BindingFeasibility.lean) · [Uniqueness of the held inventory solution](https://github.com/Eidosoma/Cells/blob/1d9fe4e10ac7a4a0a9d9e0edf9a3c0e0cb0a914a/lean/CellsProofs/Chemistry/BindingEquilibrium.lean) · [Measured optical saturation and calibration](https://github.com/Eidosoma/Cells/blob/1d9fe4e10ac7a4a0a9d9e0edf9a3c0e0cb0a914a/lean/checks/data/binding_feasibility_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/1d9fe4e10ac7a4a0a9d9e0edf9a3c0e0cb0a914a/lean/checks/binding_feasibility.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/1d9fe4e10ac7a4a0a9d9e0edf9a3c0e0cb0a914a/lean/PROGRESS.md#binding-equilibrium-feasibility)

[Tested engine 0310d9f0cfc7](https://github.com/Eidosoma/Cells/commit/0310d9f0cfc758181c0ef145bb09d513f1ef69ec) · [Evidence checkpoint 1d9fe4e10ac7](https://github.com/Eidosoma/Cells/commit/1d9fe4e10ac7a4a0a9d9e0edf9a3c0e0cb0a914a)

## Biological evidence

**Open.** Saturation of a measured bound-complex signal as metal is added to a known ligand inventory. Testing the strict equilibrium margin would require independent free ligand measurements.

An Fe–Par titration shows optical saturation. The same breakpoint was used to calibrate the ligand stock, and free iron was unmeasured.

**Unit** absorbance at 705 nm

### cortes2017_par_capacity

The authors added Fe(II) to 40 µM Par in 50 mM Na–MOPS and 100 mM NaCl. The two ratios correspond to about 20 and 32 µM added Fe(II). At pH 7.1 the trace reads about 0.39 at Fe:Par ratios of approximately 0.5 and 0.8. [Cortes et al. (2017), supporting Fig. S3b and p. S-4](https://s3-eu-west-1.amazonaws.com/pstorage-acs-6854636/8172722/ic7b00372_si_001.pdf#page=14)

- **Evidence role** descriptive
- **Evaluation** Shape of the bound-complex signal during titration
- **Excluded** An independently measured binding stoichiometry, free iron concentration, or threshold for strictly positive free ligand

Approximate graph readings. The panel reports no endpoint uncertainty, replicate count or measurement temperature.

The optical plateau is consistent with finite ligand capacity. Assigning one Fe per two ligands also set the working ligand concentration, so the endpoint cannot independently establish the stoichiometric boundary. [Dataset manifest](../checks/data/binding_feasibility_measurements.json) · [Comparison verdict](../PROGRESS.md#binding-equilibrium-feasibility)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
