# The readouts: names, units, scales and classes

Both sides use these names. The references publish the true values. `<x>` is a species (T, U or L),
`<i>` a holder.

## 1. The compared series

| Name | Unit | Definition | Class |
| --- | --- | --- | --- |
| `n_<x>_<i>` | fmol | The amount of x in a node, a well or the collector | R, or S (§3) |
| `V_K` | pL | The collector's volume | R |
| `supplied_<x>` | fmol | x delivered by the inlets, from t = 0 | R |
| `H_<i>` | pJ | The router's cumulative mixing heat at holder i (nodes and K) | arm 5: S. Elsewhere recorded, and their sum compared |
| `H_tot` | pJ | Σ_i `H_<i>`, formed by the judge | R; arm 6 with `H_face`: S and R (§3) |
| `H_face` | pJ | The face's cumulative heat | arm 1: R (T3, T4) and B (T4); arm 2 and 6: S, and an identity (R) |
| `label_T_tag_<i>`, `label_T_plain_<i>` | fmol | T by label | R |
| `n_L_S`, `free_sites_S`, `bound_L_S` | fmol | `F7`'s site node | E |
| `events[]` (arm 2) | fmol, pJ | `before`, `sample`, `supplied`, `heat` of each exchange | R, S |
| `events[]` (arm 4) | fmol, pL, pJ | `volume`, `amount`, `loss`, `resident`, `arriving` of each portion | R, E |

**Recorded, never judged:** `transfer_T` (the face's own cumulative transfer), each `H_<i>` outside arm
5, a portion's `resident` and `arriving`, `largest_ion_change_fmol` (a run's one number), and everything
under `definition` and `checks`.

## 2. Scales and the error a comparison allows

| Quantity | Scale s |
| --- | --- |
| An amount or label | N_x: the species' total in the world to that time, start plus supplied |
| `V_K` | the collector's volume at the end of the run |
| A heat, or an event's heat | s_F (LAWS.md §9) |
| An event's `before`, `sample`, `supplied`; a portion's `amount` | N_x |

The rounding term is e_round = m (S + 1) u s, with m from LAWS.md §9 for the arm, S = t/h (from the
registered grid, never from the table) and u = 2⁻⁵³. The reference's own error is its `accuracy`.

## 3. The class of each compared series, by arm

| Arm | R | S | Other |
| --- | --- | --- | --- |
| 1 | `n_T_1`, `n_T_2` against the scheme (T1); `H_face` exact (T3); `H_face` default against its law (T4); the sum n_1 + n_2 | – | B: the transfer (T2), the default heat (T4). L: the orders of T2 and T4 |
| 2 | the sums; the exchange's numbers and the first step after it, from the run's own rows; `H_face` exact, from the run's own rows; `supplied` | `n_T_1`, `n_T_2`, `H_face` (both heats), `before`, `sample`, `heat` (p = 2) | E: to the exchange, the `N-none` twin, and `before` |
| 3 | every `n`, `V_K`, `supplied`, label and their sums, `H_tot` | – | E: twins; N: every `H_<i>` never falls |
| 4 | every `n`, `V_K`, `supplied`, `H_K`, each portion's `amount`, `volume` and `loss` | – | E: the first portion's loss, +0.0; the restart |
| 5 | every `n`, `V_K`, `H_tot` at every step, `H5` included | `H_A`, `H_B`, `H_K` (p = 1), `H1` to `H4` | U: `H5`; N |
| 6 | `n_U_*`, `V_K`, sums, the energy identity on the run's own rows | `n_T_*`, and `H_tot` with `H_face` against the reference (p = 2) | E: `J0` against its twin |
| 7 | – | – | E: digests |

The classes are:
- **E, equal:** bit for bit, the sign of zero included.
- **R, rounded:** within e_round plus the reference's accuracy. Never an order window.
- **B, remainder:** within a Taylor remainder bound plus e_round.
- **S, stepped:** compared by step-halving, with an order window. Never held to rounding.
- **L, local orders:** the one-step orders of T2 and T4 at halved steps (§3.4 of CRITERIA.md).
- **U, uniform:** at most the bound of CRITERIA.md §3.6. **N:** never falls. **M:** a stopped run's
  message. **D:** completes.
