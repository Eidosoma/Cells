<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A retention estimate needs sampling during the export interval

Two equal positive pulses within an unsampled export interval give different retained amounts under positive first-order loss even when the cumulative export at both endpoints is identical.

## Assumptions

- Constant positive first-order loss, positive pulse amount and the observation after both possible pulse times. The synthetic reader control uses the same cumulative export series up to replacement on both grids.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ProducerReplacement.earlier_pulse_retains_less](../CellsProofs/Chemistry/ProducerReplacement.lean#L101)

Proof sources [Mathlib strict increase of the real exponential, applied to the two pulse times](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Data/Complex/Exponential.lean#L304)

Uses [RNA keeps its producer label through export, cell replacement and return](producer-replacement-rna.md)

## Numerical comparison

**Checked.** On 275b508f all 6 readouts on 3 grids matched their expected verdicts. Adding only post-replacement samples leaves the matching and mismatching outputs at insufficient resolution with a null bound. An interior export sample distinguishes the 1.707738-copy match from the 100-copy mismatch. The earlier frozen comparison records the false acceptance on fd2bb88c.

**Engine**

[Error estimate for known-rate survival](https://github.com/Eidosoma/Cells/blob/275b508f30ae32552bfcf154ca8849765c23672b/validation/gene_regulation/cohort.py#L187) · [Retention verdict by output](https://github.com/Eidosoma/Cells/blob/275b508f30ae32552bfcf154ca8849765c23672b/validation/gene_regulation/replace_restart.py#L237) · [Sparse and finite native controls](https://github.com/Eidosoma/Cells/blob/275b508f30ae32552bfcf154ca8849765c23672b/tests/unit/test_fr38_replace_restart.py#L49) · [Pulse-timing proof](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/CellsProofs/Chemistry/ProducerReplacement.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/checks/producer_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7c9feb549f00f58432dfc0ac3e8567a289c61255/lean/PROGRESS.md#fr38-retention-window-repair)

[Tested engine 275b508f30ae](https://github.com/Eidosoma/Cells/commit/275b508f30ae32552bfcf154ca8849765c23672b) · [Evidence checkpoint 7c9feb549f00](https://github.com/Eidosoma/Cells/commit/7c9feb549f00f58432dfc0ac3e8567a289c61255)

**Engine**

[Error estimate for known-rate survival](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/validation/gene_regulation/cohort.py#L187) · [Retention verdict by output](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/validation/gene_regulation/replace_restart.py#L237) · [Sparse and finite native controls](https://github.com/Eidosoma/Cells/blob/fd2bb88ce444b48344236024a2a18844f59041a4/tests/unit/test_fr38_replace_restart.py#L49) · [Pulse-timing proof](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/CellsProofs/Chemistry/ProducerReplacement.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/checks/producer_replacement.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/d2258d4f81a5a6e4a04277b51df0217e0b044289/lean/PROGRESS.md#fr38-pre-replacement-resolution)

[Tested engine fd2bb88ce444](https://github.com/Eidosoma/Cells/commit/fd2bb88ce444b48344236024a2a18844f59041a4) · [Evidence checkpoint d2258d4f81a5](https://github.com/Eidosoma/Cells/commit/d2258d4f81a5a6e4a04277b51df0217e0b044289)

## Biological evidence

**Open.** Time-resolved export throughout the founder’s lifetime and measured loss in the receiving pool.

**Unit** copy-equivalents at observation

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
