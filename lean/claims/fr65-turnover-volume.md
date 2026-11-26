<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Solute amount and water volume determine concentration during swelling

The change in concentration between two samples separates into a net amount change and dilution of the initial pool. Along a differentiable trajectory, the concentration slope depends on gross production minus gross loss and on the rate of volume change.

## Assumptions

- Amount and water volume refer to the same compartment, and each volume is positive. The unit conversion between amount per volume and reported concentration is fixed.
- For the rate identity, the amount and volume are differentiable at the observation time. The amount rate includes all routes of gain and loss for that pool.
- To interpret the two gross rates separately requires another observation, such as a measured release or cohort tracer. Each comparison identifies which material and preparation the experiment followed.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.TurnoverVolume.endpoint_change](../CellsProofs/Chemistry/TurnoverVolume.lean#L11)
- [CellsProofs.Chemistry.TurnoverVolume.concentration_rate](../CellsProofs/Chemistry/TurnoverVolume.lean#L17)

Proof sources [Mathlib quotient derivative, imported and specialized to amount over water volume](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Inv.lean#L143-L146)

Uses [Production and first-order clearance preserve a positive pool and account for gross turnover](scheduled-species-turnover.md) · [Two processes spending and replenishing one finite pool](fr43-shared-writers.md)

## Numerical comparison

**Open.** On main 796f04fa the scheduled turnover operator refuses a changing volume at definition time. The native refusal control passed. A compiled replay of turnover with osmotic water awaits FR-65.

## Biological evidence

**Open.** Amount and cell water in swelling preparations, and independently measured protein breakdown under lower osmolarity.

- [Hypo-osmotic swelling suppresses protein breakdown in rat liver preparations across amino-acid conditions.](../WET_LAB_EVIDENCE.md#pair-liver-swelling-proteolysis) · Different experimental results
- [Swelling changes the gross production and loss rates of the measured intracellular solute.](../WET_LAB_EVIDENCE.md#pair-swelling-solute-gross-turnover) · Comparison unresolved

**Unit** solute amount or released amino acid per g dry cells, water per g dry cells, or fractional change against each experiment’s baseline

### meijer1993-hepatocyte-swelling

Isolated hepatocytes from fasted rats at 37 °C, with and without a physiological amino-acid mixture. Fig. 3E reports ATP amount. Fig. 3F calculates concentration from that amount and Fig. 1 cell water. Table 2 and Fig. 2B report valine production at 70 and 120 mM NaCl. [Meijer et al. (1993), Figs. 1–3 and Table 2](https://doi.org/10.1111/j.1432-1033.1993.tb18053.x)

- **Evidence role** descriptive

Cell water was measured at 45 min. The ATP difference is approximate. Table 2 reports mean ± SEM from 4 and 8 preparations at 70 and 120 mM NaCl.

Without added amino acids ATP amount rose slightly with swelling and calculated ATP concentration fell by up to about 10%. Both 90-minute valine means were 15.5 µmol/g dry cells. Adding amino acids inhibited proteolysis by about 40% versus 15% of the respective controls. [Dataset manifest](../checks/data/liver_swelling_turnover.json) · [Comparison verdict](../PROGRESS.md#fr65-swelling-turnover)

### guizouarn2000_trout_water_solutes@1

Rainbow-trout red cells transferred to 215 mOsm/kg with ouabain. Water and taurine were normalized to dry cell solids. Table 1 gives the net changes from initial swelling to 60 min in the hypotonic bath. Fig. 1 gives the volume relative to the pre-shock value. [Guizouarn et al. (2000), Fig. 1 and Table 1](https://doi.org/10.1111/j.1469-7793.2000.t01-1-00147.x)

- **Evidence role** descriptive

Means ± SEM from 21 experiments in the sodium bath and 3 in the potassium bath. No separate gross taurine production or loss was measured.

During recovery in the sodium bath, cells lost 42.97 ± 1.87 µmol taurine/g and 0.37 ± 0.02 g water/g. In the potassium bath they lost 37.30 ± 0.92 µmol taurine/g while gaining 0.06 ± 0.02 g water/g. This reuses the osmotic-water dataset. [Dataset manifest](../checks/data/guizouarn2000_water_solutes.json) · [Comparison verdict](../PROGRESS.md#fr65-swelling-turnover)

### haussinger1991-perfused-liver-swelling

Perfused livers from fed rats at 37 °C. The perfusate contained 0.1 mM unlabelled leucine. The authors followed leucine released from prelabelled liver proteins. Fig. 1 and Methods, hypotonic perfusion at 185–275 mOsm/L against a 305 mOsm/L control. [Häussinger et al. (1991), Fig. 1](https://pubmed.ncbi.nlm.nih.gov/1645299/)

- **Evidence role** descriptive

Water space and labelled leucine release were measured in separate liver series under matched protocols. Fig. 1 gives SEM with 3–15 experiments per point across conditions and includes some earlier same-group values.

Lowering perfusate osmolarity increased intracellular water and reduced labelled leucine release relative to baseline. The observable is protein breakdown in this preparation. [Dataset manifest](../checks/data/liver_swelling_turnover.json) · [Comparison verdict](../PROGRESS.md#fr65-swelling-turnover)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
