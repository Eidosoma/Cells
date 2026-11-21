<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A partial wash dilutes free solute and accounts for every sampled molecule

For a finite well of fixed volume V, a wash of fraction f changes free amount n to (1 − f)n + f V c_buffer. Adding sampled material and subtracting supplied material recovers the original total, including bound ligand retained through the event. Repeating k equal washes multiplies the initial excess above the buffer level by (1 − f)ᵏ.

## Assumptions

- The liquid is well mixed. Between the washes used in the repeated-wash formula there is no binding, release, synthesis or transport.
- The Lean positivity result assumes 0 < f ≤ 1 and strictly positive free and buffer amounts. Float64 whole-wash storage also requires sufficient resolution at the host’s amount anchor. Version 1 exchanges ions at their own concentration.

## Lean proof

**Proved**

- [CellsProofs.Tissue.CompartmentWash.inventory](../CellsProofs/Tissue/CompartmentWash.lean#L14)
- [CellsProofs.Tissue.CompartmentWash.positive](../CellsProofs/Tissue/CompartmentWash.lean#L20)
- [CellsProofs.Tissue.CompartmentWash.whole](../CellsProofs/Tissue/CompartmentWash.lean#L24)
- [CellsProofs.Tissue.CompartmentWash.repeated](../CellsProofs/Tissue/CompartmentWash.lean#L27)

Direct proof subject `cells.scheduled_compartment_wash@1`

## Numerical comparison

**Checked.** Four compiled schedules retained all ions and site fields. The maximum material discrepancy was 7.11 × 10⁻¹⁵ fmol. Whole tissue runs resolved a 2⁻⁵⁰ target relative to the initial amount. The 2⁻⁶⁰ target reached the documented float64 refusal.

**Engine** `resolved_pump_tissue@3`

**Operators** `cells.scheduled_compartment_wash@1`, `cells.site_occupancy@1`

[Liquid, sample and supply](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/wash_schedule.py#L301) · [Host event and validity](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/src/cells/operators/wash_schedule.py#L325) · [Finite well with two bound populations](https://github.com/Eidosoma/Cells/blob/d74f519d40b9a9f7488b94b489c6dc4dd865504c/validation/tissue/wash_schedule_fixtures.py) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/checks/compartment_wash.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ceeca19816acd761ab68379d67bb0f7426366a1c/lean/PROGRESS.md#nov21-wash)

[Tested engine d74f519d40b9](https://github.com/Eidosoma/Cells/commit/d74f519d40b9a9f7488b94b489c6dc4dd865504c) · [Evidence checkpoint ceeca19816ac](https://github.com/Eidosoma/Cells/commit/ceeca19816acd761ab68379d67bb0f7426366a1c)

## Biological evidence

**Open.** Free tracer after successive known-fraction washes, together with independently measured ligand retained on the surface.

**Unit** µg/mL

### vloemans2024-dilution

Free fluorescein in PBS, successive 10 µL plugs. For the numerical row, use the measured 1.712 µg/mL starting concentration and three 80% exchanges with blank buffer. Fig. 4A–B, printed mean concentrations [Vloemans et al., Lab on a Chip (2024)](https://doi.org/10.1039/D4LC00195H)

- **Evidence role** descriptive
- **Observed** 0.02 µg/mL
- **Predicted** 0.013696 µg/mL

At least three replicates per point, with one SD drawn graphically. The comparison uses rounded printed means. The study notes wall adsorption and a limited instrument range.

The first two 80% washes measured 0.332 and 0.067 µg/mL against 0.3424 and 0.06848. The third mean was 46% above ideal dilution. The experiments address freely dissolved dye. Instantaneous bound-site retention in a biological well remains open. [Dataset manifest](../checks/data/vloemans2024_dilution.json) · [Comparison verdict](../PROGRESS.md#nov21-wash)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
