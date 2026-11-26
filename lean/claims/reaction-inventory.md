<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Balanced reactions preserve a weighted inventory

If each reaction balances an integer-weighted inventory, the combined update preserves that inventory for any signed real reaction extents.

## Assumptions

- The species and reaction sets at the site are finite. Each species change equals its signed stoichiometric coefficients times the extents, summed over reactions.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.inventory_after_reactions](../CellsProofs/Chemistry/Stoichiometry.lean#L27)

Direct proof subject `cells.operator.local_species_reactions@1`

## Numerical comparison

**Checked.** The enzyme example compared four stored species changes with the declared coefficients and two nonzero extents across one CPU half-step.

**Engine** `resolved_pump_composite@1`

**Operators** `local_species_reactions@1`

[Reaction admission](https://github.com/Eidosoma/Cells/blob/a124c937041353d395732a936a3d2b1001c2b63a/src/cells/operators/species_reactions.py#L431) · [Reaction half-step](https://github.com/Eidosoma/Cells/blob/a124c937041353d395732a936a3d2b1001c2b63a/src/cells/operators/species_reactions.py#L1024) · [Enzyme fixture](https://github.com/Eidosoma/Cells/blob/a124c937041353d395732a936a3d2b1001c2b63a/validation/tissue/species_reactions_fixtures.py#L248) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9c0b99d30676863d67dd8d30efea6ae490f2bd40/lean/checks/closed_enzyme.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9c0b99d30676863d67dd8d30efea6ae490f2bd40/lean/PROGRESS.md#19-november-2026--closed-enzyme-reactions)

[Tested engine a124c9370413](https://github.com/Eidosoma/Cells/commit/a124c937041353d395732a936a3d2b1001c2b63a) · [Evidence checkpoint 9c0b99d30676](https://github.com/Eidosoma/Cells/commit/9c0b99d30676863d67dd8d30efea6ae490f2bd40)

## Biological evidence

**Open.** Amount of a specified conserved chemical group across all its species at a closed site.

The measured G6P + F6P pool fell 0.613357 mM (7.31%) in the first of five time courses. The raw acquisition lists 0.950 mL and different timing from the workbook. Volumes, shared calibration and unobserved pools limit the amount balance. [Eicher et al., Fig. 5](https://www.mdpi.com/2218-1989/2/4/818) · [Publisher’s workbook](https://mdpi-res.com/metabolites/metabolites-02-00818/article_deploy/metabolites-02-00818-s001.zip)

**Unit** fmol for the target inventory, mM for the measured soluble pool

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
