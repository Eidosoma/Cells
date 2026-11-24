# The readouts: names, units and definitions

These names are the engine side's `validation/gene_regulation/engine_run.py` export names, and the
names your file uses. The engine side computes the host-side quantities (§2) from its records. You
publish the true values of every quantity.

## 1. The engine's readouts

| Name | Unit | Definition |
| --- | --- | --- |
| `n_N`, `n_M`, `n_Pi`, `n_R`, `n_R_s` | fmol | Each row's amount in the cell |
| `n_X`, `n_A`, `n_ATP`, `n_ADP`, `n_P` | fmol | Arm B's other rows |
| `n_Mx` | fmol | Family C's store row |
| `H_tx_release` | fmol | The hold, H |
| `C_tx_1` … `C_tx_8` | fmol | Transcription's stage complexes |
| `E_tx` | fmol | The engaged polymerases: Σ_j C_tx_j, plus H under `held` |
| `W_tx` | fmol of residues | The residues in transit, r Σ_j (j − 1) C_tx_j |
| `F_pol` | fmol | The free polymerases |
| `int_J_I_tx` | fmol | Cumulative initiations from t = 0 |
| `int_S_tx` | fmol | Cumulative stage exits from t = 0 (§4.7's S) |
| `int_Q_tx` | fmol | Cumulative completions from t = 0, into the hold |
| `int_Q_tx_release_durable`, `int_Q_tx_release_short_lived` | fmol | Cumulative releases into R and into R_s |
| `int_D_R`, `int_D_R_s` | fmol | Each fate's cumulative **net** loss, ∫ k_f n_f (1 − e^(y_f)) dt |
| `H_tx` | pJ | Transcription's heat class (§3.4), with no release term (§9.5) |
| `H_deg_R`, `H_deg_R_s` | pJ | Each fate's degradation heat |
| `H_rel_tx_release_durable`, `H_rel_tx_release_short_lived` | pJ | Each fate's release heat, ∫ Q^f (−ΔG^rel_f) dt |
| `H_store` | pJ | Family C: the store's heat, −∫ dG of its moves |
| `V` | pL | Family D: the cell's volume |
| `H_water` | pJ | Family D: water's heat, ∫ D dt |
| `W_bath` | pJ | Family D: the bath's water work |
| `G_minus_G0` | pJ | G(t) − G(0), LAWS.md §5 |
| `label_R_<c>`, `label_R_s_<c>`, for c in resyn, pool0, pre, win, post | fmol | The five membership classes of each fate row (LAWS.md §1) |
| Arm B's translation and A1 readouts: `F_rib`; `C_tl_j`, `E_tl`, `W_tl`, `int_J_I_tl`, `int_S_tl` and `int_Q_tl`, and the same for `tl_s`; `int_D_P`; `int_J_C`; `H_tl`; `H_deg_P`; `H_rc` | as their kind | The sheet's §6 names for A1 (§4.7, §4.8) |

## 2. The host-side quantities

| Name | Unit | Definition | The reference's value |
| --- | --- | --- | --- |
| `released_present_gross_<fate>` | fmol | `label_<row>_pre + label_<row>_win + label_<row>_post` | the sum of the three classes |
| `route2_<fate>` at each sample time | fmol | The engine's release counter carried by LAWS.md §6's known-rate form at the declared k_f, over the window, read at the sample time | the `win` class at that sample time |
| `excess_over_blank_<fate>` | fmol | The run's `n_<row>` minus its family's blank's `n_<row>`, at the same step | your integration of erratum I, item 4 (SPEC.md §3, item 5) |
| `survival_<fate>` | fmol, fmol and 1 | Route 1's counts: `label_<row>_win` at t2 and at each later sample time, and their ratio | the `win` class at those times, and the ratio |

`<fate>` is `durable` (row R) or `short_lived` (row R_s).

## 3. Scales

**The scale s_y of a quantity** is the magnitude of the terms it is formed from:
- the reference's accuracy requirement is ≤ 10⁻¹¹ s_y, computed on the reference's own solution;
- the judge's rounding term is 8 ε S_h s_y, computed on the engine's own series (CRITERIA.md C2).

| Quantity | s_y |
| --- | --- |
| An amount, occupancy or extent | max over the outputs of \|y\| |
| A label, `released_present_gross` | max over the outputs of its row's amount |
| `excess_over_blank` | max over the outputs of (n_f + n_f^blank) |
| `route2_<fate>` | max over the outputs of the fate's release counter |
| A heat (and in D, `H_water` and `W_bath`) | max over the outputs of Σ_c \|H_c\|, over the run's heat classes (in D, plus \|W_bath\|) |
| `G_minus_G0` | the heat scale, plus max over the outputs of Σ n_r RT (\|μ°_r\| + \|ln(n_r/(V c°))\| + 1), over the rows whose amount moves, plus max over the outputs of RT \|μ°_res\| (W_tx + L H) |
| `V` | max over the outputs of V |
| A survival ratio | 1 |

## 4. Which arm judges what

**Arm A (AF and AN).**
- **Judged:** every quantity of §1 and §2 for the hold worlds.
- **Reported:** `C_tx_1` … `C_tx_8` and `W_tx`, the stage complexes and their weighted sum (D334).
- **Not compared:** each route's own heats and losses (`H_route_*`, `int_D_route_*`), the sums
  `H_total` and `H_routes_sum`, the class totals `n_tx_release_<fate>` (equal to n_R and n_R_s),
  and the hold's labels `label_H_*`.

**Arm B.**
- **Judged:** FR-38's quantities:
  - `H_tx_release`;
  - both releases;
  - `n_R` and `n_R_s`;
  - `int_D_R` and `int_D_R_s`;
  - `H_deg_R`, `H_deg_R_s` and both release heats;
  - the ten labels;
  - `released_present_gross`, `route2` and `survival`.
- **Reported:** every other quantity of §1, which is A1's own:
  - its rows;
  - `F_pol`, `F_rib`, the stage complexes, `E_tx` and `W_tx`;
  - transcription's extents and translation's readouts;
  - `int_D_P` and `int_J_C`;
  - `H_tx`, `H_tl`, `H_deg_P` and `H_rc`;
  - `G_minus_G0`.
- **No blank,** so no `excess_over_blank`.

**Family C.** Arm A's judged set, plus `n_Mx` and `H_store`. `G_minus_G0` includes Mx.

**Family D.** Arm A's judged set, plus `V`, `H_water` and `W_bath`. `G_minus_G0` is family D's
(LAWS.md §5).
