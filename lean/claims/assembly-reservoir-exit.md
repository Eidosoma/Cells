<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# The assembly’s lipid exit rate scales with its count of that species

In the uncatalyzed `reservoir_exchange@1` law of `cells.assembly_lineages@1`, each molecule of a given type contributes the same exit rate. The instantaneous exit propensity for that type is `leave_rate[i] × counts[i]` per nominal time unit. Applying that count to a bilayer experiment requires identifying the molecules exposed to the reservoir.

## Assumptions

- The reservoir holds the activity of each species fixed. The assembly is well mixed and the base exchange law has no catalytic multiplier.
- For a washout comparison, the measured pool is the accessible tracer. Re-entry, extraction and the conversion of nominal time to seconds affect the comparison.

## Lean proof

**Open**

Proof sources [Assembly exchange law and time convention](../../src/cells/models/assembly_lineages/exchange.py#L1) · [Uncatalyzed entry and exit propensities](../../src/cells/models/assembly_lineages/exchange.py#L108)

## Numerical comparison

**Open.** A comparison of the assembly’s exit propensity with accessible lipid loss under the published washout conditions remains open.

## Biological evidence

**Open.** Decay of accessible tracer during buffer washout and its desorption rate in a separate capture assay.

At 24 °C and 500 µL/min buffer flow, 14:0–6:0 NBD-PC fluorescence in 310 protein-free POPC/POPG vesicles decayed at 0.0108 ± 0.0045 s⁻¹ (mean ± SD). The 49.5 ± 8.5% plateau reflects label retained in the inner leaflet. The rate includes desorption and washout. Separate albumin capture gave about 0.07 s⁻¹ (11 measurements, three preparations). These measurements support first-order loss from the accessible pool. Entry and the Cells time scale remain open. [Veit et al., Fig. 2 and Extended Data Fig. 2](https://doi.org/10.1038/s41594-026-01821-8)

**Unit** s⁻¹

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
