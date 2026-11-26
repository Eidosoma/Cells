<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Shear fission partitions the parent among all daughters and books discarded siblings

Assigning each molecule to one daughter preserves per-species inventories and the membrane footprint. If the total footprint cannot cover all daughter minima, every assignment fails. Shear work includes every daughter’s free energy. Following one daughter exports its siblings’ free energy.

## Assumptions

- Counts are nonnegative integers, each molecule has one daughter, and each membrane species has a fixed footprint. The partition is evaluated before any daughter lysis.
- The geometric admission formula assumes a nonnegative area and volume, a positive daughter count and consistent length units. The spherical capacity is computed from the available membrane area.
- Each live daughter pays the same per-vesicle closure cost. The tracer signal comparison assumes a common linear calibration, zero background and no tracer leakage during the split.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesiclePopulation.split_inventory](../CellsProofs/Chemistry/VesiclePopulation.lean#L57)
- [CellsProofs.Chemistry.VesiclePopulation.followed_and_siblings](../CellsProofs/Chemistry/VesiclePopulation.lean#L66)
- [CellsProofs.Chemistry.VesiclePopulation.split_footprint](../CellsProofs/Chemistry/VesiclePopulation.lean#L72)
- [CellsProofs.Chemistry.VesiclePopulation.insufficient_footprint](../CellsProofs/Chemistry/VesiclePopulation.lean#L81)
- [CellsProofs.Chemistry.VesiclePopulation.split_signal](../CellsProofs/Chemistry/VesiclePopulation.lean#L93)
- [CellsProofs.Chemistry.VesiclePopulation.followed_free_energy](../CellsProofs/Chemistry/VesiclePopulation.lean#L99)
- [CellsProofs.Chemistry.VesiclePopulation.closure_work](../CellsProofs/Chemistry/VesiclePopulation.lean#L107)
- [CellsProofs.Chemistry.VesiclePopulation.volume_gate](../CellsProofs/Chemistry/VesiclePopulation.lean#L116)

Direct proof subject `cells.operator.shear_fission@1`

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Membrane area caps the volume that minimizes a vesicle’s osmotic free energy](osmotic-vesicle-volume.md) · [Vesicles withdrawing from a finite shared bath conserve each species across the population](shared-pool-inventory.md)

## Numerical comparison

**Checked.** Five accepted divisions conserved lipid and both solutes. Independent work and sibling-sink errors were at most 7.11 × 10⁻¹⁵ k_BT. Two parents below the combined daughter minimum stayed intact. The population stopped before drawing when its slots filled. Controls checked stress and volume refusals and 48 heterogeneous partitions.

**Engine** `cells.assembly_lineages@2`, `cells.shared_pool@1`, `cells.bilayer_geometry@1`, `cells.osmotic_lumen@1`, `cells.ideal_mixing@1`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`

**Operators** `cells.shear_fission@1`

[Membrane and lumen partition](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/division.py#L226) · [Volume gate and division attempt](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/division.py#L283) · [Acceptance, shear work and sibling sink](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/division.py#L380) · [Follow one daughter](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/runner.py#L257) · [Keep all daughters in the shared pool](https://github.com/Eidosoma/Cells/blob/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce/src/cells/models/assembly_lineages_v2/population.py#L497) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/8b72a3ed05b95e5b4f4f13305b608f17cefbf0a3/lean/checks/vesicle_population.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/8b72a3ed05b95e5b4f4f13305b608f17cefbf0a3/lean/PROGRESS.md#vesicle-shear-fission)

[Tested engine 5011ed3d6bb6](https://github.com/Eidosoma/Cells/commit/5011ed3d6bb64721abc5acfb9f3c834fa12c97ce) · [Evidence checkpoint 8b72a3ed05b9](https://github.com/Eidosoma/Cells/commit/8b72a3ed05b95e5b4f4f13305b608f17cefbf0a3)

## Biological evidence

**Disagrees.** Slope of the two daughters’ summed tracer signal against their parent’s signal in successful divisions.

**Unit** daughter-to-parent signal slope

### deshpande2018_fission_signal@1

DOPC-based giant liposomes divided at a microfluidic Y-junction. Each plotted parent produced two observable daughters. Figure 4a pairs total daughter and parent fluorescence for 78 divisions. The accompanying text describes the geometry and optical corrections. [Deshpande et al. (2018), Fig. 4a](https://doi.org/10.1021/acsnano.7b08411)

- **Evidence role** descriptive
- **Observed** 0.87 daughter-to-parent signal slope
- **Predicted** 1 daughter-to-parent signal slope

The authors report slope 0.87 ± 0.01 (SD) and R² = 0.94. The estimated geometry and optical corrections approximately cancel.

The combined optical signal fell about 13% below perfect recovery. This disagrees with the conservative split under a common linear signal calibration. The escaped dye amount was not independently recovered. [Dataset manifest](../checks/data/vesicle_population_measurements.json) · [Comparison verdict](../PROGRESS.md#vesicle-shear-fission)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
