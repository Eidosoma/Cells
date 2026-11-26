<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# ATP synthesis and delivery return four charge equivalents in the declared three-proton model

One ATP synthesis, nucleotide exchange and phosphate import restore the matrix ATP, ADP and phosphate rows and deliver one ATP on P. Their net P-side charge is −4. Potassium–proton exchange swaps one K for one H with zero net charge. At balanced respiratory carriers and zero net charge transfer the seven paths imply five ATP deliveries per oxygen.

## Assumptions

- The registered synthase has three translocated protons per matrix ATP. Nucleotides and phosphate use the declared base forms and all proton rows are explicit.
- The five-per-O₂ identity assumes matched turnovers of synthesis, ATP export and phosphate import, and no additional electrogenic paths. It is an ideal stoichiometric ratio.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.MitochondrialCycles.charge_on_each_side](../CellsProofs/Chemistry/MitochondrialCycles.lean#L62)
- [CellsProofs.Chemistry.MitochondrialCycles.delivery_net](../CellsProofs/Chemistry/MitochondrialCycles.lean#L95)
- [CellsProofs.Chemistry.MitochondrialCycles.delivered_charge](../CellsProofs/Chemistry/MitochondrialCycles.lean#L100)
- [CellsProofs.Chemistry.MitochondrialCycles.potassium_proton_swap](../CellsProofs/Chemistry/MitochondrialCycles.lean#L102)
- [CellsProofs.Chemistry.MitochondrialCycles.charge_balance_iff](../CellsProofs/Chemistry/MitochondrialCycles.lean#L108)

Direct proof subject `cells.cycle.proton_coupled_atp_synthesis_cycle@1`, `cells.cycle.electrogenic_nucleotide_exchange@1`, `cells.cycle.phosphate_proton_symport@1`, `cells.cycle.potassium_proton_exchange@1`

Uses [Restoring both respiratory carriers fixes the turnover ratio and outward charge](mitochondrial-respiratory-balance.md) · [Stall voltages and net charge of the sodium–potassium and calcium pumps](electrogenic-pump-charge.md)

## Numerical comparison

**Checked.** The synthesized ATP, nucleotide exchange, phosphate import and K/H exchange carry −3, −1, 0 and 0 net charge equivalents on P per turn. All seven populations carried nonzero extents in two checked 1 ms steps. The independently calculated combined material postings matched the engine ledger. Global charge error stayed below 1.0 × 10⁻³³ C.

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.rapid_binding@1`

[Complex I](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/nadh_ubiquinone_proton_cycle.py#L20) · [Complex III](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/ubiquinol_cytochrome_c_proton_cycle.py#L35) · [Complex IV](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/cytochrome_c_oxygen_proton_cycle.py#L37) · [ATP synthesis](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/proton_coupled_atp_synthesis_cycle.py#L35) · [Nucleotide exchange](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/electrogenic_nucleotide_exchange.py#L34) · [Phosphate import](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/phosphate_proton_symport.py#L28) · [Potassium–proton exchange](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/laws/cycles/potassium_proton_exchange.py#L16) · [Material ledger by species and side](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/src/cells/kinds/transporter.py#L2128) · [Matrix and lumen fixture](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/tests/unit/test_mito_cycle_laws.py#L63) · [Independent registered component comparisons](https://github.com/Eidosoma/Cells/blob/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007/validation/mitochondria/component_comparison.py#L1) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/checks/mitochondrial_cycles.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/84e3078e3fa0f2a010192e4459abc72eee120b92/lean/PROGRESS.md#mitochondrial-cycle-accounting)

[Tested engine 2ae89b5e2cd1](https://github.com/Eidosoma/Cells/commit/2ae89b5e2cd19fdcd4727eb16a4d33cc20339007) · [Evidence checkpoint 84e3078e3fa0](https://github.com/Eidosoma/Cells/commit/84e3078e3fa0f2a010192e4459abc72eee120b92)

**Engine** `resolved_pump_tissue@3`, `cells.nadh_ubiquinone_proton_cycle@1`, `cells.ubiquinol_cytochrome_c_proton_cycle@1`, `cells.cytochrome_c_oxygen_proton_cycle@1`, `cells.proton_coupled_atp_synthesis_cycle@1`, `cells.electrogenic_nucleotide_exchange@1`, `cells.phosphate_proton_symport@1`, `cells.potassium_proton_exchange@1`, `cells.rapid_binding@1`

[Complex I](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/nadh_ubiquinone_proton_cycle.py#L20) · [Complex III](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/ubiquinol_cytochrome_c_proton_cycle.py#L35) · [Complex IV](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/cytochrome_c_oxygen_proton_cycle.py#L37) · [ATP synthesis](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/proton_coupled_atp_synthesis_cycle.py#L35) · [Nucleotide exchange](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/electrogenic_nucleotide_exchange.py#L34) · [Phosphate import](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/phosphate_proton_symport.py#L28) · [Potassium–proton exchange](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/laws/cycles/potassium_proton_exchange.py#L16) · [Material ledger by species and side](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/src/cells/kinds/transporter.py#L2128) · [Matrix and lumen fixture](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/tests/unit/test_mito_cycle_laws.py#L85) · [Independent stoichiometry by cycle and side](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_cycles.py#L20) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/checks/mitochondrial_cycles.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/0d3f300a5d1c09bf0ad3c557d151879f441425b1/lean/PROGRESS.md#mitochondrial-kinase-supply)

[Tested engine 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1) · [Evidence checkpoint 0d3f300a5d1c](https://github.com/Eidosoma/Cells/commit/0d3f300a5d1c09bf0ad3c557d151879f441425b1)

## Biological evidence

**Open.** Rotor proton count and ATP turnover for synthesis, plus the energetic cost of delivering ATP across the mitochondrial inner membrane.

- [Exactly three protons per ATP is the intrinsic tight-coupling ratio of the mammalian mitochondrial ATP synthases represented by the Cells model.](../WET_LAB_EVIDENCE.md#pair-mammalian-rotor-coupling) · Independent replication unconfirmed

**Unit** c-subunits per rotor, H⁺ per matrix ATP, charge equivalents per delivered ATP

### pinke2020_ovine_rotor@1

ATP synthase purified from sheep heart mitochondria, imaged by cryo-EM. State 1a, deposited EM map EMD-10573 and PDB 6TT7, entities 2 and 10. [Pinke et al. (2020), ovine cryo-EM structure 6TT7](https://doi.org/10.1038/s41594-020-0503-8)

- **Evidence role** descriptive

Subunit counts are structural observations. One H⁺ per c-subunit and three ATP per turn are the tight-coupling interpretation. There is no simultaneous H⁺ and ATP flux measurement.

The ovine assembly has eight c-subunits and three catalytic β-subunits. Its new density corroborates the 8/3 tight-coupling interpretation, with a shared bovine starting model for the rotor. The delivered ATP cost also depends on the export and phosphate paths. [Dataset manifest](../checks/data/paired_wet_lab_measurements.json) · [Comparison verdict](../PROGRESS.md#paired-wet-lab-evidence)

### watt2010_bovine_rotor@1

Structure of the bovine mitochondrial F1–c-ring complex. The bovine c-ring in Fig. 1 and the authors' coupling interpretation. [Watt et al. (2010), Fig. 1 and Discussion](https://doi.org/10.1073/pnas.1011099107)

- **Evidence role** descriptive

The 3.5 Å structure resolves eight c-subunits. The stoichiometric interpretation assumes tight coupling and three ATP per full rotation.

The bovine structure implies 8/3 H⁺ per matrix ATP under tight coupling, and the authors infer 11/3 proton equivalents per delivered ATP. The current Cells model fixes 3 and 4. The structural result identifies a preparation-specific limit of that choice. It does not measure ATP flux under load. [Dataset manifest](../checks/data/mitochondrial_stoichiometry.json) · [Comparison verdict](../PROGRESS.md#mitochondrial-cycle-accounting)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
