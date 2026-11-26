<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Prescribed totals admit at most one binding equilibrium

With fixed binder inventories, ligand totals determine at most one positive free concentration vector. Along any nonconstant joint change of free log concentrations, the projected change in totals is strictly positive. Fixing the unheld free concentrations gives the same uniqueness result for the held ligand equations and for any measured group of binder forms.

## Assumptions

- Each binder has a finite nonempty set of equilibrium forms with fixed standard potentials at one temperature. Integer ligand counts relative to the base may be signed. Zero binder totals are allowed.
- The free concentrations are positive. The equations use ideal concentration activities in a common mM frame. The candidate states have identical binder totals and fixed unheld free concentrations.
- Uniqueness is conditional on existence in exact arithmetic. Admissibility of arbitrary totals, rates of approach to equilibrium and the finite Newton iteration budget require separate checks.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.BindingEquilibrium.total_hasDerivAt_line](../CellsProofs/Chemistry/BindingEquilibrium.lean#L56)
- [CellsProofs.Chemistry.BindingEquilibrium.total_pairing_pos](../CellsProofs/Chemistry/BindingEquilibrium.lean#L73)
- [CellsProofs.Chemistry.BindingEquilibrium.held_equilibrium_unique](../CellsProofs/Chemistry/BindingEquilibrium.lean#L99)
- [CellsProofs.Chemistry.BindingEquilibrium.equilibrium_group_unique](../CellsProofs/Chemistry/BindingEquilibrium.lean#L114)
- [CellsProofs.Chemistry.BindingEquilibrium.positive_free_unique](../CellsProofs/Chemistry/BindingEquilibrium.lean#L124)

Direct proof subject `cells.binding.rapid_binding@1`

Proof sources [Mathlib positivity of the matrix quadratic form, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/LinearAlgebra/Matrix/PosDef.lean#L330-L334) · [Mathlib strict monotonicity from a positive derivative, imported](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/MeanValue.lean#L382-L385) · [Cells finite binding response and its positive definiteness](../CellsProofs/Chemistry/BindingResponse.lean#L147)

Uses [Total ligand increases with its own free concentration](binding-ligand-response.md)

## Numerical comparison

**Checked.** All 423 full pairs had positive projected changes on NumPy and compiled JAX CPU. With selected coordinates fixed, 283 of 284 distinct pairs were distinguishable. One pair near 0.5 mM free Mg gave equal float64 totals on both paths and a positive 80-digit projection. Both backends recovered all 423 independently manufactured target states within 2.99 × 10⁻¹³ in log concentration.

**Engine** `resolved_pump_tissue@3`, `rapid_binding@1`

[Conservation residual and equilibrium solvers](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/src/cells/laws/reactions/rapid_binding.py#L122-L259) · [Single-ligand proton-buffer solver](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/src/cells/laws/reactions/rapid_proton_buffer.py) · [Standard potentials and binder inventories](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/validation/core_seams/references/reference_inputs.json) · [Independent manufactured free concentrations](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/validation/core_seams/references/designs/core_seams_reference_values.json) · [Registered system fixtures and solver tests](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/tests/unit/test_rapid_binding_kernel.py#L80) · [Two-ligand tissue run](https://github.com/Eidosoma/Cells/blob/0310d9f0cfc758181c0ef145bb09d513f1ef69ec/tests/unit/test_rapid_binding_world_two_ligands.py#L31) · [Exact equilibrium theorem](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/CellsProofs/Chemistry/BindingEquilibrium.lean) · [Binding response matrix](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/CellsProofs/Chemistry/BindingResponse.lean) · [Normalized form weights](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/CellsProofs/Chemistry/BindingEnsemble.lean) · [Independent standard-potential partition](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/checks/binding_ensemble.py#L32) · [Measured endpoint conditions](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/checks/data/binding_equilibrium_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/checks/binding_equilibrium.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/fe028eeeafe61014625eef968c487f7fa64b8961/lean/PROGRESS.md#binding-equilibrium-unique)

[Tested engine 0310d9f0cfc7](https://github.com/Eidosoma/Cells/commit/0310d9f0cfc758181c0ef145bb09d513f1ef69ec) · [Evidence checkpoint fe028eeeafe6](https://github.com/Eidosoma/Cells/commit/fe028eeeafe61014625eef968c487f7fa64b8961)

## Biological evidence

**Open.** The concentration of a bound form after two preparations with identical totals approach equilibrium from opposite starting states. Fe–Tar absorbance supplies one such observable.

Opposite iron-loading histories converged to the same Fe–Tar signal within the graph’s resolution. Free metal and the individual protonation states remain unmeasured.

**Unit** µM difference in Fe–Tar complex between preparation histories

### cortes2017_matched_histories

The final solutions had 30.8 µM Fe(II), 72 µM Tar and 220 µM EGTA at pH 7.2. Fe started bound to Tar or to EGTA, giving initial Fe–Tar signals near 31 or 0 µM. Absorbance at 720 nm measured the Fe–Tar complex across its protonation states. The Fe–Tar concentration read from the two late traces is about 22.5 µM in both cases. They approach a common plateau by approximately 15–20 min and stay close through 90 min. [Cortes et al. (2017), supporting Fig. S4a, p. S-15](https://s3-eu-west-1.amazonaws.com/pstorage-acs-6854636/8172722/ic7b00372_si_001.pdf#page=15)

- **Evidence role** held out from fitting
- **Evaluation** Difference between late Fe–Tar plateau readings in the two mixing directions
- **Excluded** Absolute binding affinities and the rate of approach to the plateau
- **Predicted** 0 µM difference in Fe–Tar complex between preparation histories

Each trace is readable to about ±0.5 µM, giving about ±1 µM for their difference. The figure supplies no endpoint sampling uncertainty, replicate count or figure-specific temperature.

The observed difference was indistinguishable from zero at plot resolution. One resolved complex supports the history-independent prediction in this preparation. The complete free ligand vector and Mg–ATP remain open. [Dataset manifest](../checks/data/binding_equilibrium_measurements.json) · [Comparison verdict](../PROGRESS.md#binding-equilibrium-unique)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
