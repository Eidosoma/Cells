# The readouts: names, units, definitions, scales and classes

Both sides use these names. The references publish the true values; the engine's table carries the engine's. `<x>`
is the shared row of the world: S in `W5` and `W5-exact`, R in `W6`.

## 1. What is published

| Name | Unit | Definition | Where |
| --- | --- | --- | --- |
| `t_events` | s | The time of every event of the site, in order (index k), with its channel and the counts after it | All |
| `n_S_c`, `n_S_o` | fmol | S in the cell, and in the node | W5, W5-exact |
| `n_X`, `n_Y`, `n_W` | fmol | The cell's X, Y, W | W5, W5-exact |
| `xi_1`, `xi_2` | fmol | The cumulative extents of `make` and `spend`: ∫ J_1, ∫ J_2 from t = 0 | W5, W5-exact |
| `n_R_c`, `n_R_o` | fmol | R in the cell, and in the node | W6 |
| `made`, `lost` | fmol | The cumulative finished chains ∫ J_m, and the cumulative degradation ∫ D, from t = 0 | W6 |
| `moved` | fmol | The transfer's cumulative account of S (or R), from t = 0, positive from the cell to the node | All |

- **Rows and books** are read at `samples_s` (0 included, the initial state). A book is the writer's own
  accumulator: TABLE.md.
- **`t_events`** is judged on the first K_c events of each copy. `K_c` is the reference's (SPEC.md §3).
- **The engine's recorded row at an event** (the pools at the crossing) is recorded and never judged: it is first
  order at a co-writer's step, by construction (the population's own view inside the step).

**Signs.** An amount is positive. `xi_1`, `xi_2`, `made`, `lost` and `moved` (cell to node) are as defined: a
negative `moved` is a net return to the cell.

## 2. Scales, for the rounding bound

Every scale is published by the references (`scales`), from their own solution over the copies and samples of the
world, and the judge reads it there, never from the engine's rows.

| Readout | s (the rounding bound's scale) |
| --- | --- |
| `t_events` | T, the world's `end_s` |
| `n_S_c` | max over copies and samples of \|n_S_c(t)\| + \|n_S_c(0)\| + \|ξ_1(t)\| + \|ξ_2(t)\| + \|moved(t)\| |
| `n_S_o` | max of \|n_S_o(t)\| + \|n_S_o(0)\| + \|moved(t)\| |
| `moved` | max of \|moved(t)\| |
| `xi_2`, `lost` | the book's own maximum |
| `n_R_c` | max of \|n_R_c(t)\| + \|n_R_c(0)\| + \|made(t)\| + \|lost(t)\| + \|moved(t)\| |
| `n_R_o` | max of \|n_R_o(t)\| + \|n_R_o(0)\| + \|moved(t)\| |

## 3. The class of each readout, by world

| Readout | W5 | W5-exact | W6 | Class |
| --- | --- | --- | --- | --- |
| `t_events` (times, judged events) | S | R | S | as listed |
| `channel` and `counts_after` at each judged event | E | E | E | E |
| `integer_ledger`: Σ_k w_k n_k at every sample | E | E | E | E |
| `restart` (the resumed run against the uninterrupted one) | E | – | E | E |
| `n_S_c`, `n_S_o`, `moved`, `xi_2` | S | recorded | – | S |
| `n_R_c`, `n_R_o`, `lost`, `moved` | – | – | S | S |
| The identities of §4, named `identity n_S_c` and so on (per row, at every sample) | R | R | R | R |
| `n_X`, `n_Y`, `n_W`, `xi_1`, `made` | enter §4's identities; else recorded | | | – |

## 4. The identities (class R), on the run's own rows and books

For a sample at t, each residual is the difference of the two sides. Its bound is 16 (S + 1) u s_id with S = t/h
from the registered grid and s_id the sum of the absolute terms in that identity (the rows at t and at t = 0 and the
books at t), from the run's own values.

| World | Identity | Terms |
| --- | --- | --- |
| W5, W5-exact | n_S_c(t) − n_S_c(0) = ξ_1 − ξ_2 − moved | 4 |
| W5, W5-exact | n_S_o(t) − n_S_o(0) = moved | 2 |
| W5, W5-exact | n_X(t) − n_X(0) = −ξ_1 | 2 |
| W5, W5-exact | n_Y(t) − n_Y(0) = −ξ_2,   n_W(t) − n_W(0) = ξ_2 | 2 |
| W6 | n_R_c(t) − n_R_c(0) = made − lost − moved | 4 |
| W6 | n_R_o(t) − n_R_o(0) = moved | 2 |

- **They are judged at every sample, every run, every copy.** They hold at every step, and for a Lie plant too (a
  split in time does not break them).
- **An identity names every holder of its row.** S in W5: cell, node (the rows), and X, W (the chemistry's other
  rows) enter by their own identities. The list is complete: there is no residue in transit for a row that a book
  carries.

## 5. The class S readouts and their entries

| Readout | Entries pooled | Order p |
| --- | --- | --- |
| `t_events` | the copies' judged events (k < K_c, all copies of the family) | 2 |
| `n_S_c`, `n_S_o`, `moved`, `xi_2`; `n_R_c`, `n_R_o`, `lost`, `moved` | the copies' samples (t > 0, all copies) | 2 |

- The pooled statistic is the root mean square over the entries (CRITERIA.md §3.3).
- **An entry is judged only if it is formed by every copy:** the family's runs of all copies at the rung, present
  and not refused.
