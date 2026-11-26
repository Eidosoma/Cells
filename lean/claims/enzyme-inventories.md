<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Binding and catalysis conserve enzyme and substrate

In E + S ⇌ C and C → E + P, total enzyme is E + C and total substrate is S + C + P. Omitting the returned E loses one enzyme unit per catalytic event while preserving substrate.

## Assumptions

- Each complex carries one enzyme unit and one substrate unit. Each product retains one substrate unit. The site has no external supply or removal.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.Enzyme.enzyme_conserved](../CellsProofs/Chemistry/Enzyme.lean#L33)
- [CellsProofs.Chemistry.Enzyme.substrate_conserved](../CellsProofs/Chemistry/Enzyme.lean#L40)
- [CellsProofs.Chemistry.Enzyme.missing_enzyme_balance](../CellsProofs/Chemistry/Enzyme.lean#L48)

Direct proof subject `cells.operator.local_species_reactions@1`

Proof sources [crnt-lean concentration-rate conservation, imported in the optional check](https://github.com/marpaia/crnt-lean/blob/7386777488a41efd92e6abc2bccf889fb611660e/CRNT/Examples/Enzyme.lean#L64-L82) · [Cells comparison of all directed stoichiometric entries and the fixed-volume conversion](../checks/chemistry/Reuse.lean#L22)

Uses [Balanced reactions preserve a weighted inventory](reaction-inventory.md)

## Numerical comparison

**Checked.** Lean checked both fixture columns and both weight rows. The largest absolute inventory residual in the CPU half-step was about 1.12 × 10⁻²⁰ fmol, below the 6.94 × 10⁻¹⁸ fmol tolerance. The engine refused the missing-enzyme reaction.

**Engine** `resolved_pump_composite@1`

**Operators** `local_species_reactions@1`

[Reaction admission](https://github.com/Eidosoma/Cells/blob/a124c937041353d395732a936a3d2b1001c2b63a/src/cells/operators/species_reactions.py#L431) · [Reaction half-step](https://github.com/Eidosoma/Cells/blob/a124c937041353d395732a936a3d2b1001c2b63a/src/cells/operators/species_reactions.py#L1024) · [Enzyme fixture](https://github.com/Eidosoma/Cells/blob/a124c937041353d395732a936a3d2b1001c2b63a/validation/tissue/species_reactions_fixtures.py#L248) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/9c0b99d30676863d67dd8d30efea6ae490f2bd40/lean/checks/closed_enzyme.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/9c0b99d30676863d67dd8d30efea6ae490f2bd40/lean/PROGRESS.md#19-november-2026--closed-enzyme-reactions)

[Tested engine a124c9370413](https://github.com/Eidosoma/Cells/commit/a124c937041353d395732a936a3d2b1001c2b63a) · [Evidence checkpoint 9c0b99d30676](https://github.com/Eidosoma/Cells/commit/9c0b99d30676863d67dd8d30efea6ae490f2bd40)

## Biological evidence

**Open.** Free enzyme, substrate, bound complex and product amounts in a specified closed enzyme preparation.

NMR resolved ligand states bound to triosephosphate isomerase. Testing both balances requires simultaneous amounts of free enzyme, substrate, bound complex and product during turnover. [Rozovsky and McDermott, Figs. 3–5](https://pmc.ncbi.nlm.nih.gov/articles/PMC1794347/)

**Unit** fmol

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
