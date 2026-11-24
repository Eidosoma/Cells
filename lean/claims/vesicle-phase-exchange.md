<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Lipid insertion scales with membrane area and diffusion-limited capture scales with radius

At fixed external number density, scaling the area-equivalent radius by s scales area-limited insertion by s² and diffusion-limited capture by s. A join and its reverse share the footprint before insertion. Their rate ratio is the exponential of reservoir work minus free-energy change in thermal units.

## Assumptions

- The same species transfers between the pool and the bilayer. Each comparison holds its kinetic coefficient and external number density fixed.
- The rate-ratio statement applies to an enabled two-way edge with a positive common coefficient, sufficient reactants and a defined discrete membrane counting measure. The endpoint energies include the declared excess terms.
- The spherical diffusion-capture approximation uses the area-equivalent radius. The two encounter conventions describe different limiting mechanisms.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.VesicleExchange.size_scaling](../CellsProofs/Chemistry/VesicleExchange.lean#L23)
- [CellsProofs.Chemistry.VesicleExchange.common_footprint_swap](../CellsProofs/Chemistry/VesicleExchange.lean#L40)
- [CellsProofs.Chemistry.VesicleExchange.transfer_footprint](../CellsProofs/Chemistry/VesicleExchange.lean#L46)
- [CellsProofs.Chemistry.VesicleExchange.pair_balance](../CellsProofs/Chemistry/VesicleExchange.lean#L60)

Direct proof subject `cells.phase_exchange@1`

Proof sources [VeriBiota preservation of a weighted count under an enabled firing, imported in the optional check](https://github.com/OmnisGenomics/VeriBiota/blob/a145b640d7d8009a5a653849c41ef9a1d6b1c176/Biosim/Proofs/Invariants.lean#L113-L121) · [Cells specialization to a one-molecule transfer from a finite pool](../checks/chemistry/Reuse.lean#L63)

Uses [Bilayer area is half the sum of the molecular footprints in its two leaflets](bilayer-footprint.md) · [Finite molecule counts set stochastic encounter rates and paired event heat](assembly-stochastic-encounter.md)

## Numerical comparison

**Checked.** Doubling radius gave 4× area-limited insertion and 2× diffusion-limited capture. Across both transport steps, eight compiled configurations tested finite and held baths and both counting measures. All 40 blocked directions had zero rate. Across 64 active pairs the largest free-energy residual was 1.43 × 10⁻¹⁴ k_BT.

**Engine** `cells.assembly_lineages@2`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Directional activities and geometric factor](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/exchange.py) · [Area or radius on the common footprint](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/src/cells/models/assembly_lineages_v2/kernel.py) · [assembly lineage v2 fixtures](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/assembly_lineage_v2_fixtures.py) · [test assembly lineages v2 geometry](https://github.com/Eidosoma/Cells/blob/329e9e395ac117998657a21eb827192d34314107/tests/unit/test_assembly_lineages_v2_geometry.py) · [vesicle exchange measurements](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/data/vesicle_exchange_measurements.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/checks/vesicle_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/ad1f96418722d25876b38b5a5f38996512d6a32c/lean/PROGRESS.md#ol5-six-replays)

[Tested engine 329e9e395ac1](https://github.com/Eidosoma/Cells/commit/329e9e395ac117998657a21eb827192d34314107) · [Evidence checkpoint ad1f96418722](https://github.com/Eidosoma/Cells/commit/ad1f96418722d25876b38b5a5f38996512d6a32c)

**Engine** `cells.assembly_lineages@2`, `cells.phase_exchange@1`, `cells.membrane_permeation@1`, `cells.bilayer_geometry@1`, `cells.ideal_mixing@1`

[Directional activities and geometric factor](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/exchange.py#L42) · [Area or radius on the common footprint](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/kernel.py#L327) · [Bidirectional engine rates](https://github.com/Eidosoma/Cells/blob/3d3d9641932a52852727df7e4722e15ded245766/src/cells/models/assembly_lineages_v2/kernel.py#L367) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/checks/vesicle_exchange.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/19de00d9a76a27fd064f1e643be28db630d48423/lean/PROGRESS.md#vesicle-phase-exchange)

[Tested engine 3d3d9641932a](https://github.com/Eidosoma/Cells/commit/3d3d9641932a52852727df7e4722e15ded245766) · [Evidence checkpoint 19de00d9a76a](https://github.com/Eidosoma/Cells/commit/19de00d9a76a27fd064f1e643be28db630d48423)

## Biological evidence

**Open.** Lipid molecules inserted per vesicle per second at measured radius and matched free-monomer concentration, composition and temperature.

- [At fixed external lipid supply, the measured whole-vesicle insertion flux can discriminate radius-proportional from area-proportional capture.](../WET_LAB_EVIDENCE.md#pair-vesicle-insertion-size-exponent) · Comparison unresolved

**Unit** molecules/s per vesicle

### jin2021_pazepc_insertion@1

Soluble PAzePC monomers at 0.5–1 µM were supplied to aspirated POPC vesicles under flow. Table 1 gives the PAzePC row. Equation 2 fits the area response. [Jin and Baumgart (2021), Table 1](https://doi.org/10.1039/D1SM00652E)

- **Evidence role** descriptive

Mean ± SEM across 11 vesicles for the fitted PAzePC rates.

The measured association constant was 0.0027 ± 0.0005 µM⁻¹ s⁻¹. Release and movement between leaflets had separate rates. The pooled fractional area kinetics leave molecule flux by radius unresolved. [Dataset manifest](../checks/data/vesicle_exchange_measurements.json) · [Comparison verdict](../PROGRESS.md#vesicle-phase-exchange)

### hentrich2014_oleate_growth@1

Multilamellar oleate vesicles grew under flow with 0.8 mM oleate micelles. Figure 2A plots initial filament elongation against starting vesicle diameter. [Hentrich and Szostak (2014), Fig. 2A](https://doi.org/10.1021/la503933x)

- **Evidence role** descriptive

There is substantial scatter at each diameter. Filament width and free monomer concentration are additional uncertainties in a conversion to molecular flux.

Larger vesicles generally elongated faster. The authors could resolve neither a linear nor a quadratic dependence uniquely from this length readout. [Dataset manifest](../checks/data/vesicle_exchange_measurements.json) · [Comparison verdict](../PROGRESS.md#vesicle-phase-exchange)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
