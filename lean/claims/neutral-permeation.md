<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Passive neutral solute follows its concentration gradient

For a neutral solute the inward constant-field flux is the route scale times outside minus inside concentration at any voltage. With a positive scale it is inward exactly when concentration is higher outside. In a closed pair the gradient changes at rate −k times the gradient, where k is the scale times the sum of the reciprocal compartment volumes.

## Assumptions

- Valence is zero. The route scale is area × permeability × opening divided by mol/fmol. Concentrations are in mM and flux is in fmol/s.
- The relaxation identity applies to two well-mixed compartments at fixed positive volumes in pL, with this route as the sole transfer of the solute.

## Lean proof

**Proved**

- [CellsProofs.Transport.Neutral.flux_eq_fick](../CellsProofs/Transport/NeutralPermeation.lean#L14)
- [CellsProofs.Transport.Neutral.inward_iff](../CellsProofs/Transport/NeutralPermeation.lean#L18)
- [CellsProofs.Transport.Neutral.closed_pair_gradient_rate](../CellsProofs/Transport/NeutralPermeation.lean#L23)

Direct proof subject `cells.route.passive_neutral_permeation@1`

Uses [At equal voltage, junction flux follows the concentration gradient](junction-concentration-gradient.md)

## Numerical comparison

**Checked.** Five compiled cases agreed with the independent flux within 7.11 × 10⁻¹⁵ fmol/s. In the closed tissue pair at 20 ms, the largest relative error in final compartment amount was 1.70 × 10⁻⁴ against a 5 × 10⁻⁴ tolerance.

**Engine** `resolved_pump_tissue@3`, `passive_neutral_permeation@1`

[Neutral route](https://github.com/Eidosoma/Cells/blob/f130a109ad8861ce114f0f6fea3ece524465e80f/src/cells/laws/routes/passive_permeation.py#L43) · [Constant-field kernel](https://github.com/Eidosoma/Cells/blob/f130a109ad8861ce114f0f6fea3ece524465e80f/src/cells/laws/electrochemistry.py#L32) · [Inward booking](https://github.com/Eidosoma/Cells/blob/f130a109ad8861ce114f0f6fea3ece524465e80f/src/cells/kinds/passive_routes.py#L355) · [Full-opening rate bound](https://github.com/Eidosoma/Cells/blob/f130a109ad8861ce114f0f6fea3ece524465e80f/src/cells/kinds/passive_routes.py#L553) · [Independent closed-form solution](https://github.com/Eidosoma/Cells/blob/f130a109ad8861ce114f0f6fea3ece524465e80f/validation/passive/passive_reference.py#L66) · [Tissue fixture and tolerance](https://github.com/Eidosoma/Cells/blob/f130a109ad8861ce114f0f6fea3ece524465e80f/tests/unit/test_passive_routes_kind.py#L64) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/b6c7108c22c4c3ea3366672932f3d49ca8b8a3c8/lean/checks/neutral_permeation.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/b6c7108c22c4c3ea3366672932f3d49ca8b8a3c8/lean/PROGRESS.md#19-november-2026--passive-neutral-permeation)

[Tested engine f130a109ad88](https://github.com/Eidosoma/Cells/commit/f130a109ad8861ce114f0f6fea3ece524465e80f) · [Evidence checkpoint b6c7108c22c4](https://github.com/Eidosoma/Cells/commit/b6c7108c22c4c3ea3366672932f3d49ca8b8a3c8)

## Biological evidence

**Open.** Signed passive transfer rate of an identified neutral solute at measured free concentrations on both sides, with compartment volumes or measured flux per area and the corresponding area.

Urea flux was measured over time in liposomes of three lipid compositions. Comparing a Cells rate requires the gradient, area and permeability for the same preparation. [Lande et al., Fig. 3](https://doi.org/10.1085/jgp.106.1.67)

**Unit** fmol/s

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
