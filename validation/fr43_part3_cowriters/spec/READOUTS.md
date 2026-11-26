# The readouts: names, units, definitions, scales, classes and identities

Both sides use these names. The references publish the true values; the engine's table carries the engine's. `<x>`
is the shared row of the world: S in `W5` and `W5-exact`, R in `W6`. The keys differ by world (the table's and the
reference's carry the world's, and no other).

## 1. The readouts

| Name | Unit | Definition | Worlds |
| --- | --- | --- | --- |
| `t_events` | s | The time of every event of the site, in order (index k), with its channel and the counts after it | all |
| `n_S_c`, `n_S_o`; `n_X`, `n_Y`, `n_W` | fmol | S in the cell and in the node; X, Y, W in the cell | W5, W5-exact |
| `xi_1`, `xi_2` | fmol | The cumulative extents of `make` and `spend`: ∫ J_1, ∫ J_2 from t = 0 | W5, W5-exact |
| `n_R_c`, `n_R_o`; `n_N`, `n_M`, `n_Pi` | fmol | R in the cell and in the node; N, M, Pi in the cell | W6 |
| `free`, `engaged` | fmol | Free machines F, and Σ_j C_j, the engaged ones | W6 |
| `transit` | fmol of residues | Residues in transit, r Σ_j (j − 1) C_j | W6 |
| `inits`, `exits`, `made`, `lost` | fmol | Cumulative initiations ∫ J_I, stage exits ∫ Σ_j J_j, finished chains ∫ J_m, molecules of R degraded ∫ D, from t = 0 | W6 |
| `moved` | fmol | The transfer's cumulative account of the shared row, positive from the cell to the node, from t = 0 | all |

- Rows are read at `samples_s` (0 included, the initial state); a book is the writer's own cumulative account
  (TABLE.md), zero at t = 0.
- The engine's recorded row at an event (the pools at the crossing) is recorded and never judged: first order beside
  a co-writer, by construction.

## 2. The rounding bound's scale

Every scale is published by the references (`scales`), from their own solution over the copies and samples of the
world, and the judge reads it there, never from the engine's rows.

| Readout | s (max over copies and samples of …) |
| --- | --- |
| `t_events` | T |
| `n_S_c` | \|n_S_c(t)\| + \|n_S_c(0)\| + \|ξ_1\| + \|ξ_2\| + \|moved\| |
| `n_S_o` | \|n_S_o(t)\| + \|n_S_o(0)\| + \|moved\| |
| `moved`, `xi_2`, `lost`, `made`, `exits` | the book itself |
| `n_R_c` | \|n_R_c(t)\| + \|n_R_c(0)\| + \|made\| + \|lost\| + \|moved\| |
| `n_R_o` | \|n_R_o(t)\| + \|n_R_o(0)\| + \|moved\| |

A row or a book with no line here (`n_X`, `n_Y`, `n_W`, `xi_1`, `n_N`, `n_M`, `n_Pi`, `free`, `engaged`, `transit`,
`inits`) is published and judged by identities alone: its scale, the largest |value| over the copies and samples, is
for its accuracy only (SPEC.md §4). W5-exact's scales are published too, and §3.5 of CRITERIA.md reads those of
`n_S_c` and `moved`. An identity's scale (s_id, §4) is the run's own terms, not a published scale.

## 3. The judged entries, by class and world

| Class | Entry | Scope | W5 | W5-exact | W6 |
| --- | --- | --- | --- | --- | --- |
| E | `trace`: channel and counts after each judged event | every judged run | yes | yes | yes |
| E | `ledger`: Σ_k w_k n_k at every sample and after every event | every judged run | yes | yes | yes |
| E | `restart` (equal to the uninterrupted run) | the resumed run | yes | no | yes |
| R | `t_events` against the exact decimal times | every judged run | no | yes | no |
| R | `start`: rows and books at t = 0 | every judged run | yes | yes | yes |
| R | `identity`, each in §4 | every judged run, every sample | yes | yes | yes |
| S | `t_events` (p = 2) | the family, all copies, all judged events | yes | no | yes |
| S | `n_S_c`, `n_S_o`, `moved`, `xi_2` (p = 2) | the family, all copies, samples t > 0 | yes | no | no |
| S | `n_R_c`, `n_R_o`, `moved`, `lost` (p = 2) | the family, all copies, samples t > 0 | no | no | yes |
| S | `made`, `exits` (p = 3, named in `at_rounding`: size alone) | the family, all copies, samples t > 0 | no | no | yes |
| pair | the two declared orders differ, at the coarsest rung, and W5-exact's two rungs (CRITERIA.md §3.5) | the two families of a world | yes | yes (two recorded rows) | yes |

- **Published and not judged:** `n_X`, `n_Y`, `n_W` and `xi_1` in W5 enter §4's identities only; W5-exact's rows
  (its references publish them) enter them only, and are not compared with the references (but for the running
  check's half, CRITERIA.md §3.2); `n_N`, `n_M`, `n_Pi`, `free`, `engaged`, `transit`, `inits` in W6 likewise.
- `inputs.json`'s `judged` is the list, machine-readable; where it differs from this table, `inputs.json` governs (a
  difference is a fault of this file).

## 4. The identities (R), and the start

A residual is the sum of the identity's terms (`inputs.json`'s `identities`: each a readout, a coefficient, and `t`
or `0` for its row or book at the sample or at t = 0). Its bound is 16 (S + 1) u s_id with S = t/h and s_id = Σ
|coefficient × value|. The identities name every holder of the amount, so that none is missed (a lesson of earlier
registrations).

| World | Identity | The sum that vanishes |
| --- | --- | --- |
| W5 and W5-exact | `S cell` | n_S_c(t) − n_S_c(0) − ξ_1 + ξ_2 + moved |
| | `S node` | n_S_o(t) − n_S_o(0) − moved |
| | `X`, `Y`, `W` | n_X(t) − n_X(0) + ξ_1;  n_Y(t) − n_Y(0) + ξ_2;  n_W(t) − n_W(0) − ξ_2 |
| | `S moiety`, `Y moiety` | n_X + n_S_c + n_S_o + n_W, and n_Y + n_W, against their own t = 0 value |
| W6 | `R cell` | n_R_c(t) − n_R_c(0) − made + lost + moved |
| | `R node` | n_R_o(t) − n_R_o(0) − moved |
| | `N`, `Pi`, `M` | n_N(t) − n_N(0) + r exits;  n_Pi(t) − n_Pi(0) − 2r exits;  n_M(t) − n_M(0) − L lost |
| | `machines` | free + engaged, against its t = 0 value |
| | `engaged` | engaged − inits + made |
| | `transit` | transit − r exits + L made |
| | `nucleoside` | n_N + n_M + L (n_R_c + n_R_o) + transit, against its t = 0 value |

- r = residues / stages, L = residues, as numbers in `inputs.json`.
- A resumed run's identities use the uninterrupted run's t = 0 row and books (it has no t = 0 row of its own), and
  judge its own samples at and after its checkpoint.
- **The start** (class R): at the sample t = 0 each row and book equals its declared value in `inputs.json`'s
  `start`, within 4 u |declared| (exactly zero where the declared value is 0). `free(0)` is `machines_copies` ×
  COPY, and `engaged(0)` and `transit(0)` are 0: the machines start all free and every stage complex at exactly 0
  (LAWS.md §3, `inputs.json`'s `machines_start`). A resumed run has none to judge.

## 5. The class S readouts' entries

| Readout | Entries pooled | Order p |
| --- | --- | --- |
| `t_events` | the copies' judged events (k < K_c) | 2 |
| the rows and books of §3 | the copies' samples with t > 0 | 2, or 3 for `made` and `exits` |

- The pooled statistic is the root mean square over the entries (CRITERIA.md §3.3).
- **`made` and `exits` are exempt by name** (`at_rounding`). They are the gene unit's own books: one operator writes
  them, no rate that moves them reads R, and neither the declared order nor the population reaches them. So their
  error is the third-order error of that operator's half-step alone. It falls 8-fold at each halving while the
  resolution threshold (CRITERIA.md §3.3, ten times the rounding bound) doubles, so three resolved differences need
  a first difference above 256 times its threshold. They are judged by their size alone. **The name is checked:**
  the references' sizing must show fewer than three used differences (C0, CRITERIA.md §4.2); one that shows three is
  a fault before the tag, since the entry is then not at rounding.
- An entry is formed only by every copy's run at every rung of the family (CRITERIA.md §3.0).
