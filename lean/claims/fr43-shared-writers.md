<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Two processes spending and replenishing one finite pool

The change in a shared stock equals the sum of the two writers’ signed bookings over any interval, including a tail after restart. An independently measured reserve with known stoichiometry can distinguish their contributions. A common standard potential assigns a single standard-energy change to the stock.

## Assumptions

- Each writer books exactly its own signed amount change. Both use the same amount units, preserve the cumulative counters at restart and account for every source or sink in this interval. The reserve used to infer one writer’s contribution has no other active route.
- For the two rate probes, the numerator is nonzero at held amounts and controls and volume is positive. The stale-volume energy identity applies to positive amounts in an ideal mixture and compares the same change in amount at two volumes.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.SharedWriter.split_balance](../CellsProofs/Chemistry/SharedWriter.lean#L17)
- [CellsProofs.Chemistry.SharedWriter.window_balance](../CellsProofs/Chemistry/SharedWriter.lean#L22)
- [CellsProofs.Chemistry.SharedWriter.separate_writers](../CellsProofs/Chemistry/SharedWriter.lean#L36)
- [CellsProofs.Chemistry.SharedWriter.shared_standard_energy](../CellsProofs/Chemistry/SharedWriter.lean#L43)
- [CellsProofs.Chemistry.SharedWriter.volume_rate_distinguishes](../CellsProofs/Chemistry/SharedWriter.lean#L47)
- [CellsProofs.Chemistry.SharedWriter.stale_volume_energy](../CellsProofs/Chemistry/SharedWriter.lean#L61)

Direct proof subject `cells.local_species_reactions@1`, `cells.templated_polymerisation@1`

Proof sources [Imported Mathlib telescoping sum specialized to a saved interval](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Basic.lean#L862-L865) · [Imported Mathlib logarithm of a quotient for the ideal-energy correction](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/SpecialFunctions/Log/Basic.lean#L129) · [Cells locally proves the two-writer split and volume specializations](../CellsProofs/Chemistry/SharedWriter.lean)

## Numerical comparison

**Checked.** On the FR-43 part 2B development revision 211a9c17, the fixed-volume network added 0.004997501 fmol and the gene unit spent a net 0.000664664 fmol. The 5 s disk restart reproduced all 78 state fields. Shifting 1% of a writer’s booking to its partner preserved the total and failed the independent reserve check. In a swelling cell both rate probes agreed at 2 and 3 s within 2.54 × 10⁻⁶ relative error. Supplying the initial volume to one writer at a time identified that writer in each control. These checks cover the saved-state rates and accounts. The FR-43 qualification compares the coupled trajectory separately.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.local_species_reactions@1`, `cells.templated_polymerisation@1`, `cells.ideal_osmosis_linear_compliance_water@1`

[Fixed-volume pair and finite reserve](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/validation/tissue/shared_inventory_fixtures.py#L104) · [Both writers in the swelling cell](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/validation/tissue/shared_inventory_fixtures.py#L182) · [Current volumes passed to split operators](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/models/pump_composite.py#L1628) · [Shared standard potential](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/registry/species_registry.py#L679) · [Gene initiation and substrate concentrations](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/operators/templated_polymerisation.py#L2193) · [Reaction step and volume read](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/operators/species_reactions.py#L1767) · [Water volume and work accounts](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/operators/osmotic_water.py) · [Gene-unit fixture with finite stocks](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/validation/gene_regulation/worlds.py#L429) · [Native checkpoint and run entry point](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/execution/runner.py#L362) · [Native saved arrays and snapshots](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/src/cells/records/io.py#L254) · [Native changing-volume energy and tracer controls](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/tests/unit/test_shared_inventory_volume.py) · [Shared-row admission and potential checks](https://github.com/Eidosoma/Cells/blob/211a9c17441ae6c17b00d3d239b5baa05a261d9f/tests/unit/test_shared_inventory_writers.py) · [Balance, volume and energy identities](https://github.com/Eidosoma/Cells/blob/6831a0113ffed609f060d495b205e119235d4768/lean/CellsProofs/Chemistry/SharedWriter.lean) · [Measured UTP and four companion pools](https://github.com/Eidosoma/Cells/blob/6831a0113ffed609f060d495b205e119235d4768/lean/checks/data/fr43_uridine_pool.json) · [Independent UTP reconstruction](https://github.com/Eidosoma/Cells/blob/6831a0113ffed609f060d495b205e119235d4768/lean/checks/shared_uridine_pool.py) · [Pinned proof dependency](https://github.com/Eidosoma/Cells/blob/6831a0113ffed609f060d495b205e119235d4768/lean/lake-manifest.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/6831a0113ffed609f060d495b205e119235d4768/lean/checks/shared_writers.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/6831a0113ffed609f060d495b205e119235d4768/lean/PROGRESS.md#fr43-two-writers)

[Tested engine 211a9c17441a](https://github.com/Eidosoma/Cells/commit/211a9c17441ae6c17b00d3d239b5baa05a261d9f) · [Evidence checkpoint 6831a0113ffe](https://github.com/Eidosoma/Cells/commit/6831a0113ffed609f060d495b205e119235d4768)

## Biological evidence

**Open.** A finite nucleotide pool, its upstream reserve and its consumption product measured together. For a changing-volume amount balance, each concentration also needs a matched volume.

A five-metabolite time course permits reconstruction of the UTP concentration from the other four pools. The experiment resolves net supply and spending. Gross fluxes and the uncertainty of the full residual remain open.

**Unit** mM UTP

### huber2026_shared_UTP

The stock calculation assumes a common volume and that all uridine remains in the five measured pools. It uses upstream depletion and downstream product accumulation. No kinetic parameters were fitted for this readout. Figure 8 validation batch, 40_TO7h mean and SD tables. The archived samples span 0 to 24 h. [Huber et al. (2026), Fig. 8](https://doi.org/10.1016/j.mec.2026.e00287)

- **Evidence role** held out from fitting
- **Evaluation** All nine UTP means from 0.5 to 24 h, with the 7 h measurement reported below
- **Observed** 0.954545 mM UTP
- **Predicted** 0.822089 mM UTP

Reported UTP SD at 7 h is 0.350096 mM. The upstream and product measurements also carry uncertainty. The archive gives no paired covariance for the reconstructed residual.

At 7 h the upstream pools supplied a net 38.101943 mM and product accumulation spent 37.279854 mM. Predicted minus observed UTP ranged from −0.284381 to +0.276418 mM across the nine samples. At 24 h the reconstruction gave 0.697341 mM against 0.525149 mM observed with a UTP SD of 0.021942 mM. This SD covers only the measured UTP channel. [Dataset manifest](../checks/data/fr43_uridine_pool.json) · [Comparison verdict](../PROGRESS.md#fr43-two-writers)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
