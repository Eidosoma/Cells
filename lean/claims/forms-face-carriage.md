<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A moving binder carries its ligands across a face

Each binder form contributes one binder and its signed ligand stoichiometry to every transfer. The stored rows conserve their inventories across the endpoints and recover the movers’ charge. Ligand can cross even at zero net binder flux.

## Assumptions

- Each face credits and debits the same signed transfer. The inventory statement sums the face contributions on a finite closed network. Any reservoir, reaction or membrane contribution to an observed node needs its own accounting.
- Counts are integers relative to the reference form. For the zero-net-binder case, the two forms have swapped positive endpoint concentrations, the same positive diffusivity and zero voltage difference. The ligand carried by the occupied form moves in addition to any independent free-ligand flux.

## Lean proof

**Proved**

- [CellsProofs.Transport.FormsFace.binder_and_ligand](../CellsProofs/Transport/FormsFace.lean#L23)
- [CellsProofs.Transport.FormsFace.charge_from_rows](../CellsProofs/Transport/FormsFace.lean#L33)
- [CellsProofs.Transport.FormsFace.row_conservation](../CellsProofs/Transport/FormsFace.lean#L42)
- [CellsProofs.Transport.FormsFace.ligand_moves_at_zero_binder_flux](../CellsProofs/Transport/FormsFace.lean#L51)

Direct proof subject `cells.route.logmean_electrodiffusion_forms@1`

Proof sources [Imported Mathlib sum over an optional mover, specialized to free ligand plus forms](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Fintype/BigOperators.lean#L97) · [Imported Mathlib interchange of finite sums, specialized to total charge](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Group/Finset/Sigma.lean#L116)

Uses [Extracellular face flux follows the electrochemical potential drop](extracellular-face-direction.md) · [Only boundary transfers change a region’s inventory during transport](transfer-inventory.md)

## Numerical comparison

**Checked.** Across four compiled CPU tissue steps, both nodes matched the independently reconstructed binder and H⁺ transfers within 6.94 × 10⁻¹⁸ fmol. Two kernel controls moved ligand at zero net binder flux. Omitting a signed ligand count preserved global totals but missed the shared node by 12 or 6 fmol/s.

**Engine** `resolved_pump_tissue@3`, `logmean_electrodiffusion_forms@1`, `rapid_binding@1`

[Form stoichiometry, valence and diffusivity](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/laws/routes/logmean_electrodiffusion_forms.py#L141) · [Logarithmic mean](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/numerics/extracellular_field.py#L48) · [Form flux, row projection and node booking](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/numerics/surface_transport.py#L107) · [IMEX form weights and electric drift](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/numerics/surface_imex.py#L142) · [Face current in the field solve](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/numerics/surface_field.py#L475) · [Cumulative row transfers and tissue ledgers](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/models/surface_pump_v3.py#L3695) · [Binding weights for each chemical form](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/laws/reactions/rapid_binding.py#L100) · [Stage concentrations from rapid binding](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/kinds/proton_buffer.py#L387) · [Physical units](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/laws/electrochemistry.py) · [Two-lumen fixture and native controls](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/tests/unit/test_rapid_binding_world.py#L685) · [Compartment definition](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/validation/compartment_ph_engine/definitions.py) · [Compartment inputs](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/validation/compartment_ph_engine/parameters.py) · [Compiled runner](https://github.com/Eidosoma/Cells/blob/7ece26559d7b459928d6a7a7b819fb613b51a984/src/cells/execution/runner.py#L393) · [Form projections and zero-net-binder theorem](https://github.com/Eidosoma/Cells/blob/3fcba9e4820397d2e0dff718972e9f1c7fded34d/lean/CellsProofs/Transport/FormsFace.lean) · [Log-mean face law in real arithmetic](https://github.com/Eidosoma/Cells/blob/3fcba9e4820397d2e0dff718972e9f1c7fded34d/lean/CellsProofs/Transport/LogMeanFace.lean) · [Transfers on a finite graph](https://github.com/Eidosoma/Cells/blob/3fcba9e4820397d2e0dff718972e9f1c7fded34d/lean/CellsProofs/Accounting/Transfer.lean) · [Acid arrival and oxygen flux measurements](https://github.com/Eidosoma/Cells/blob/3fcba9e4820397d2e0dff718972e9f1c7fded34d/lean/checks/data/mobile_buffer_transport.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/3fcba9e4820397d2e0dff718972e9f1c7fded34d/lean/checks/forms_face.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/3fcba9e4820397d2e0dff718972e9f1c7fded34d/lean/PROGRESS.md#forms-face-carriage)

[Tested engine 7ece26559d7b](https://github.com/Eidosoma/Cells/commit/7ece26559d7b459928d6a7a7b819fb613b51a984) · [Evidence checkpoint 3fcba9e48203](https://github.com/Eidosoma/Cells/commit/3fcba9e4820397d2e0dff718972e9f1c7fded34d)

## Biological evidence

**Open.** Simultaneous transfers of free ligand, individual binder forms and total binder between compartments with measured geometry and endpoint concentrations.

Carbonic buffer shortened acid arrival between regions of a rabbit heart cell. Mobile myoglobin increased initial oxygen flux in a polymer film. Both support facilitated transport. Passage of each binding form across the same interface remains unmeasured.

**Unit** fmol per stored row in Cells, s for acid arrival and kg O₂ m⁻² h⁻¹ for oxygen flux

### spitzer2002_acid_arrival

Isolated rabbit ventricular myocytes at 36 °C. The readout was a 20 nM rise in free intracellular H⁺ at sites about 40 µm apart. Figures 1–2 and the Results on diffusion delay. [Spitzer et al. (2002)](https://doi.org/10.1113/jphysiol.2001.013268)

- **Evidence role** descriptive

Arrival delay was 25.1 ± 5.1 s in HEPES (10 cells), 5.93 ± 2.96 s with carbonic buffer (7 cells) and 15.53 ± 2.65 s with carbonic anhydrase inhibited (8 cells). Errors are SEM across separate groups.

Buffer chemistry and its kinetics affected acid transport. Predicting these times requires spatial geometry and reaction rates. The effective diffusion coefficients were inferred from the same delays. [Dataset manifest](../checks/data/mobile_buffer_transport.json) · [Comparison verdict](../PROGRESS.md#forms-face-carriage)

### figueiredo2014_oxygen_flux

Dissolved oxygen crossed a polymer film with or without horse myoglobin at 25 °C. Figures 6–7. [Figueiredo et al. (2014)](https://doi.org/10.1590/0104-6632.20140313s00002307)

- **Evidence role** descriptive

The carrier-free film gave 3 × 10⁻⁷ kg m⁻² h⁻¹. Initial flux with uncrosslinked myoglobin was about threefold higher. Tests were in triplicate and the authors reported deviation below 10% without specifying its definition.

Myoglobin later leached out. Crosslinking also impaired oxygen unloading, so the controls leave the effect of mobility alone unresolved. [Dataset manifest](../checks/data/mobile_buffer_transport.json) · [Comparison verdict](../PROGRESS.md#forms-face-carriage)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
