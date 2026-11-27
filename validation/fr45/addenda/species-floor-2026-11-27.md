# FR-45 addendum: each species' material-balance floor [W6-1]

Dated 27 November 2026. Drafted by FR-45's builder for TABLE.md §4 and §14.1 (§11.2, W6-1). A reviewer who is not
the builder confirmed it against `src/` [N2], with one correction, made here (the ions). The lead hashes it before
any registered run.

## The one floor the driver passes to the species helper

`validation/fr45/worlds.py` declares every ligand through the engine's species helper,
`cells.registry.inventory_species.add_inventory_species`. Each call passes `floor_fmol=FLOOR_FMOL`, which is
**1e-20 fmol**, for every ligand of every world.

The helper sets that ligand's `execution.material_balance_atol_fmol` to the floor it receives
(`x["material_balance_atol_fmol"][species_id] = floor`). No caller declares a ligand's floor otherwise.

The floor is the caller's argument, positive and at most 1e-10 fmol. It depends on no world's amounts or start:
neither on W1eq's start nor on any declared amount.

The parse-only passes record it in every world's execution block: L1 and L2 (W1, W1p, W2, W4, W5, W6, W7), L1 to
L5 (W3, W3p) and L1 (W7s), each at 1e-20.

## The ions

The ions Na, K and Cl are not required by the host: the bath form parses without them (the reviewer's
ion-free bath). They are in every compartment because SPEC:59-61 and RULINGS-2 §8.1 keep the ions at fixed amounts
there. The helper does not declare them. Their floor is **1e-10 fmol**, declared in the definition's execution block by `worlds.py` as the bath form's
fixtures declare it (`validation/tissue/secreted_species_fixtures.py`: `material_balance_atol_fmol={s: 1e-10 for s,
_ in ION_SPECIES}`). The source check ran this form, its case f. The passes record it in every world: Na, K and Cl
each at 1e-10.

## The reading (ruled 27 November 2026, build rulings item 9)

TABLE §4 says every species' `material_balance_atol_fmol` is "as the engine's species helper sets it ... never
declared otherwise". That sentence applies to the species the helper sets: the ligands, each at 1e-20 fmol.

The host's ions are set by no helper, so they take the bath form's declared value, 1e-10 fmol. No ion moves: every
ion's permeability is 0.0 on every patch, and the wash's exchange is ion-matched. So the ions' floor changes no
verdict.
