# The plants: mechanisms, homes and what each plant changes

`CRITERIA.md` §4.5 and §6 say how they are scored. Every margin is stated from the legacy side alone, before any run (§8). No band, class or window
moves because of a margin.

## 1. The rule of sizing

- **A plant's distance** at an entry is the largest difference, over the compared times and entities, between a planted legacy run and the honest legacy run of the same world and the same
  captured step. Both are runs of the frozen snapshot. The **honest run is the control,** and the control equals the captured array bit for bit (§8).
- **The band it is sized against** is the entry's β at U_c = 0: 2 U_l + e_round(S_c) + e_round(S_l) + e_close, with S_c the candidate's steps at h₃.
- **The margin** is the distance over that band. The rule is **10 at the best entry.** A plant below it is enlarged or replaced by a dated line before the tag, stated, and no number of `CRITERIA.md` changes.
- **The ratio** ρ(y) is the distance over the largest magnitude of the readout in the honest run. `margins.json` holds it. Power reads D(y) = ρ(y) × max |L₃| of the family.
- **Observability.** A mechanism whose plant has no effect above its band in 20 ms is **not observable here**. It is then an entry "not tested" in advance (`CRITERIA.md` §4.5), and no mechanism is made a home for it. It is stated with the number.

## 2. Mechanisms and their homes

### Part 1

| Mechanism | Home entries | Consumers that hold it |
| --- | --- | --- |
| Leak permeability | `leak_Na`, `leak_K`, `leak_Cl` | jupiter, cell, base |
| Channel permeability | `channel_K` | jupiter, cell, base |
| Channel kinetics | `gate_m`, `gate_h` | jupiter, cell, base |
| Na/K pump | `pump` | jupiter, cell, base |
| Junction permeability | `junction_Na`, `junction_K`, `junction_Cl` | jupiter, base, integrated |
| Junction gate | `junction_gate` | jupiter, base, integrated |
| Faces | `face_Na`, `face_K`, `face_Cl` | jupiter, base |
| Electrical closure | `voltage`, and `phi_out` in jupiter | all, except where `phi_out` is absent |

- **Every mechanism must be tested in every consumer that holds it** (`CRITERIA.md` §8), except where §8 here states it is not observable.
- **The other entries** (`n_cell_x`, `n_out_x`, the heats) take the ratio of the plant that moves them most. They are not homes.
- **The assembly mechanisms** are class E and have their own plants (§4).

### Part 2

`PART2.md` §7.

## 3. The power plants (PW): one constant × 1.01

Each is a legacy run of the captured definition with that one change, on the legacy side. Where the constant is in code, the change is a host-side patch of the snapshot's module in the driver, never in the tree.

| Plant | Change | Homes |
| --- | --- | --- |
| PW-leak | Every species' leak permeability of both membranes × 1.01 | `leak_x` |
| PW-channel | Both channels' maximal permeability × 1.01 | `channel_K` |
| PW-kinetics | Both gates' time constants × 1.01 (patch) | `gate_m`, `gate_h` |
| PW-pump | Both pumps' capacity × 1.01 | `pump`, and the largest effect on `voltage` |
| PW-junction | Every species' junction permeability × 1.01 | `junction_x` |
| PW-jgate | The junction gate's threshold voltage × 1.01 | `junction_gate` |
| PW-face | Every species' face diffusivity × 1.01, on every face | `face_x` |
| PW-faceK | K's face diffusivity × 1.01 | `phi_out` |
| PW-pool | The pool's off-rate × 1.01 | the pool's arrays (class E: a distance that is non-zero, no margin) |

**Run in** `jupiter_baseline` and `jupiter_pump_release` (all but PW-pool), in `base` and `cell` at seed 0 (the plants that the consumer holds; its end state alone is captured), and in
`integrated` (PW-junction, PW-jgate), where it is marked as not tied to a capture until one exists.

## 4. The structural plants (ST), Part 1

| Plant | World | Change | Named entries |
| --- | --- | --- | --- |
| ST1 | jupiter_baseline | The pump's ions run backwards: 3 Na in, 2 K out, with the same cycles (patch) | `n_cell_Na`, `n_cell_K`, `voltage` |
| ST2 | jupiter_baseline | The leak flux takes Cl as valence +1 (patch) | `leak_Cl` |
| ST3 | jupiter_baseline | The channel's inactivation gate is left out of its open fraction (patch) | `channel_K` |
| ST4 | jupiter_baseline | The junction's flux takes the voltage difference with the opposite sign (patch) | `junction_Na`, `junction_K`, `junction_Cl` |
| ST5 | jupiter_baseline | The faces' drift is left out: no outside potential (patch) | `face_Na`, `face_K`, `face_Cl` |
| ST6 | base, seed 0 | Each pool's availability acts on the other cell's channel (patch) | `channel_K` in world 1 |
| ST7 | cell, seed 0 | The availability is inverted: closed when the assembly has a cycle (patch) | `channel_K` in world 1 |
| ST8 | jupiter_pump_release | The pump is released on one membrane only (definition) | `pump` |
| ST9 | integrated | The availability multiplies the stored junction gate rather than the flux (patch) | `junction_K` |

## 5. The engine plants (EP): runs of the candidate, Part 1

| Plant | Run | Change | Named entries |
| --- | --- | --- | --- |
| EP1 | `jupiter_baseline plant channel`, at h₃ | Both channels' maximal permeability × 1.01 | `channel_K` |
| EP2 | `base plant swapped`, seed 0, world 1, at h₃ | Each channel's schedule is the other cell's path | `channel_K` |

A plant's block differs from its honest run's only by its change. Any other difference is a departing echo.

## 6. The judge's plants (JP): altered copies of honest tables

Formed by the judge from the honest tables, before the judge's tag and again on the registered tables. They cost no run.

| Plant | Alteration | Must be |
| --- | --- | --- |
| JP1 | `leak_K` with the opposite sign | a fail of `leak_K` (S) |
| JP2 | `heat_membrane` formed without `heat_pump` | a fail of `heat_membrane` (S) |
| JP3 | `jupiter_baseline` read as `jupiter_pump_release` | a fail of `pump` |
| JP4 | One value of one pool array moved by one unit (an integer by 1, a time by one unit in the last place) | a fail of class E |
| JP5 | h₃'s rows copied from h₂'s | both runs refused (the copy guard), and the readouts judged |
| JP6 | One run of a family refused, and an E entry of another run altered to fail | the fail stands |
| JP7 | `heat_junction` set to zero | a fail of `heat_junction` (S), and a reported energy residual |
| JP8 | One event deleted from a path | a fail of class E, and of the schedule |
| JP9 | An echo with one number off by 10⁻⁹ | refused, and nothing of the run judged |
| JP10 | An echo with its maps in another order, a 4 for a 4.0, and a schedule with a repeated value | not refused |
| JP11 | A judged run's `status` a `check` refusal | a stop, and a fail |
| JP12 | A support run missing | the consumer at best inconclusive |
| JP13 | A `record_sha256` shared by two runs | both refused, readouts judged |
| JP14 | One S series of h₁ shifted by the size of a rounding, and the other two honest | the entry's class is by the rule, and no fail is invented |

**A judge's plant that the code scores otherwise stops the judge's tag.**

## 7. The structural plants of Part 2

`PART2.md` §7.

## 8. The margins (from the legacy side alone)

**The control.** Filled by the author after the bands were committed, and before the Part 1 tag: each world's unpatched control run of the snapshot, and its comparison with the capture, array by array. The numbers are in `margins.json`, the runs in `plants_manifest.json`.

**Margins:** to be filled, with the date of the runs. `margins.json` holds, per plant, world and entry, the distance, the band at U_c = 0, the margin and the ratio. `plants_manifest.json` holds each run's command, patch text, output folder and sha256. Part 2's are `margins_part2.json` and `plants_manifest_part2.json`.
