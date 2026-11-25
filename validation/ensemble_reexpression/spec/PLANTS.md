# The plants: mechanisms, homes and what each plant changes

`CRITERIA.md` §4.5 and §6 say how they are scored. Every margin is stated from the legacy side alone, before any run (§8). No band, class or window
moves because of a margin.

## 1. The rule of sizing

- **A plant's distance** at an entry is the largest difference, over the compared times and entities, between a planted legacy run and the honest legacy run of the same world and the same
  captured step. Both are runs of the frozen snapshot. The **honest run is the control,** and the control equals the captured array bit for bit (§8).
- **The band it is sized against** is the entry's β at U_c = 0: 2 U_l + e_round(S_c) + e_round(S_l) + e_close + e_store(S_c), with S_c the candidate's steps at h₃ (and `phi_out`'s own e_close).
- **The margin** is the distance over that band. The rule is **10 at the best entry.** A plant below it is enlarged or replaced by a dated line before the tag, stated, and no number of `CRITERIA.md` changes.
- **The ratio** ρ(y) is the distance over the largest magnitude of the readout in the honest run. `margins.json` holds it. Power reads D(y) = ρ(y) × max |L₃| of the family.
- **Observability.** A mechanism whose plant has no effect above its band in 20 ms is **not observable here**. It is then "not tested" in advance (`CRITERIA.md` §4.5), it is no home of any mechanism, and it is stated with the number.

## 2. Mechanisms and their homes

### Part 1

| Mechanism | Home entries | Consumers that hold it |
| --- | --- | --- |
| Leak permeability | `leak_Na`, `leak_K`, `leak_Cl` | jupiter, cell, base |
| Channel permeability | `channel_K`, and `channel_K_summary` in base | jupiter, cell, base |
| Channel kinetics | `gate_m`, `gate_h` | jupiter, cell, base |
| Na/K pump | `pump` | jupiter, cell, base |
| Junction permeability | `junction_Na`, `junction_K`, `junction_Cl` | jupiter, base, integrated |
| Junction gate | `junction_gate` | jupiter, base, integrated |
| Faces | `face_Na`, `face_K`, `face_Cl` | jupiter, base |
| Electrical closure | `voltage` (its plant is the one that moves it most: `PW-pump` in jupiter and base, `PW-leak` in cell, `PW-junction` in integrated), and `phi_out` in jupiter (`PW-faceK`) | all, except where `phi_out` is absent |

- **Every mechanism must be tested in every consumer that holds it** (`CRITERIA.md` §8), except where §8 here states it is not observable. The judge reads them from `margins.json` (`mechanisms`), with the homes and each plant's ratio.
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
| PW-pump | Both pumps' capacity × 1.01 | `pump` |
| PW-junction | Every species' junction permeability × 1.01 | `junction_x` |
| PW-jgate | The junction gate's threshold voltage × 1.01 | `junction_gate` |
| PW-face | Every species' face diffusivity × 1.01, on every face | `face_x` |
| PW-faceK | K's face diffusivity × 1.01 | `phi_out` |
| PW-pool | Each of the pool's four rates (on, off, close, dissolve) × 1.01, one at a time, on the snapshot's pool run alone | the pool's arrays (class E: a distance that is non-zero, no margin) |

**Run in** `jupiter_baseline` and `jupiter_pump_release` (all but PW-pool), in `base` and `cell` at seed 0 (the plants that the consumer holds; its end state alone is captured), and in
`integrated` (PW-junction, PW-jgate), with its own control.

## 4. The structural plants (ST), Part 1

| Plant | World | Change | Named entries |
| --- | --- | --- | --- |
| ST1 | jupiter_baseline | The pump's ions run backwards: 3 Na in, 2 K out, with the same cycles (patch) | `n_cell_Na`, `n_cell_K`, `voltage` |
| ST2 | jupiter_baseline | The leak flux takes Cl as valence +1 (patch) | `leak_Cl` |
| ST3 | jupiter_baseline | The channel's inactivation gate is left out of its open fraction (patch) | `channel_K` |
| ST4 | jupiter_baseline | The junction's flux takes the voltage difference with the opposite sign (patch) | `junction_Na`, `junction_K`, `junction_Cl` |
| ST5 | jupiter_baseline | Na's and K's face diffusivities exchanged (definition) | `face_Na`, `face_K` |
| ST6 | base, seed 0 | Each pool's availability acts on the other cell's channel (patch) | `channel_K` in world 2 |
| ST7 | cell, seed 0 | The availability is inverted: closed when the assembly has a cycle (patch) | `channel_K` in world 1 |
| ST8 | jupiter_pump_release | The pump is released on one membrane only (definition) | `pump` |
| ST9 | integrated | The junctions' schedule is not applied: open fraction 1 throughout (definition) | `junction_Na`, `junction_K`, `junction_Cl` |
| ST10 | base and cell, seed 0 | The availability is held over each step at its value at the step's start, so an event acts at the next step (patch) | `channel_K` in world 2 (`base`) and in world 1 (`cell`) |

**Two plants replaced before any run, 25 November 2026 (dated line).** ST5 was the faces' drift left out, and ST9 the availability acting on the stored junction gate. The legacy side cannot run the first: its own charge and field checks stop an unbalanced face current. The second needs a patch that
changes the gate's state at a schedule change, and a schedule that is not applied is the same class of error and can be run exactly. Neither was run.

**Three changes, 25 November 2026 (dated line).**
- ST6 and EP2 moved from world 1 to world 2 at seed 0. Worlds 0 and 1 there are not blind (`CRITERIA.md` §8), and the lead said so after ST6's run had been made. World 2 is the first blind world by ID, at that seed, whose two paths differ. ST6's planted run holds all 8 worlds, and its margin at world 1 had been printed before the move.
- ST10 was added: a driver or an engine that lets an event act at the next step instead of at its own time. It was run after this line. (The form with a held availability that an earlier draft registered is gone, `SPEC.md` §3.3, and this is the error it would have made.)
- ST1 and ST4 were refused by legacy's own ledgers at their first attempts, which is what an error of their kind does, and were run again with those ledgers off (§8). Both attempts are in the manifest.

## 5. The engine plants (EP): runs of the candidate, Part 1

| Plant | Run | Change | Named entries |
| --- | --- | --- | --- |
| EP1 | `jupiter_baseline plant channel`, at h₃ | Both channels' maximal permeability × 1.01 | `channel_K` |
| EP2 | `base plant swapped`, seed 0, world 2, at h₃ | Each channel's schedule is the other cell's path | `channel_K` |

A plant's block differs from its honest run's only by its change. Any other difference is a departing echo. **EP2's change is in its channel schedule, which no echo checks** (`SPEC.md` §2.4). So its `switch_list` and its `controls.channel` are class E against the **swapped** paths (the other cell's, same seed and world), and the plant is unscorable if either departs. **Their registered distances** are the legacy side's: EP1's is `PW-channel`'s (its ratio times the largest `channel_K` of the honest control of `jupiter_baseline`), and EP2's is ST6's at world 2 (`margins.json`).

## 6. The judge's plants (JP): altered copies of honest tables

Each is an altered copy of an **honest table of the judge's own, for its self-tests,** and again of the registered tables. The judge's own are made from the reference side's arrays (the captures; in the rehearsal, its `runs/`), each moved by at most one unit in the last place so that the guard does not fire, with an invented heat split; recorded as fabricated. Class E values are not moved, and where the reference side holds no row (in `base` at 5 and 10 ms it holds the voltage and the channel's transfer alone) the row is invented so that the identities close. They cost no run.

**How each is written.** A plant names the run it alters. It alters **rows only**, or the one leaf it names, and everything else of the table (echo, strings, `t`, `steps`, record, source) stays honest. "The path" is the reference path (`SPEC.md` §3.2), and the run's own path is named where it is meant. **A plant that the echo refuses is not a fail plant,** and its "must be" says refused. Where a plant says "in all three rungs" it alters h₁, h₂ and h₃ alike.

| Plant | The run altered, and what | Must be |
| --- | --- | --- |
| JP1 | `jupiter_baseline`, all three rungs: the rows `leak_K` negated | a fail of `leak_K` (S), and of the balances of both cells and of the region they face (R) |
| JP2 | `jupiter_baseline`, all three rungs: the rows `heat_pump` set to zero | a fail of `heat_membrane` (S), and of `energy_identity` |
| JP3 | `jupiter_pump_release`, all three rungs: the rows and potentials replaced by `jupiter_baseline`'s of the same step, the echo and the strings left honest | a fail of `pump` (S), and not refused |
| JP4 | One pool run (`base s1 pool`): one value of one array moved by one unit (an integer by 1, a time by one unit in the last place) | a fail of class E of that array, for that run |
| JP5 | `jupiter_baseline`, h₃: its class S rows replaced by h₂'s class S rows, and `heat_leak`, `heat_pump` and `heat_channel` by h₂'s too, the potentials and the identities' other rows left as they are | both runs refused by the copy guard (a), their readouts judged, for the checker to settle |
| JP6 | `jupiter_baseline`: h₁ refused (kind `harness`, no row), and one `n_cell_K` of h₃ raised by 10⁻⁶ of its largest value | the fail of h₃'s balances stands, and `jupiter` fails |
| JP7 | `jupiter_baseline`, all three rungs: the rows `heat_junction` set to zero | a fail of `heat_junction` (S) and of `energy_identity` |
| JP8 | `base s0 pool`: the last event deleted from the run's own path of world 2, `cell_0` (the availability is 0 before it and after it) | a fail of class E of the run's own path for that run. The exposure is unchanged and passes (R). The schedule entries of the ionic runs, which compare with the reference path, are not touched |
| JP9 | `jupiter_baseline`, h₁: one number of `inputs` moved by 10⁻⁹ of itself | refused, and nothing of the run judged. Not a fail plant |
| JP10 | `integrated`, h₁: an echo with its maps in another order, a 27 for a 27.0, a default omitted, and a schedule with a repeated value | not refused |
| JP11 | `jupiter_baseline`, h₁: `status` `"refused"`, kind `check` | a stop, and a fail (D). The rows it holds are judged |
| JP12 | The support run `jupiter_baseline h=2.5e-05 restart` missing | the consumer at best inconclusive |
| JP13 | `integrated`, h₁ and h₂: the same `record_sha256` | both refused, readouts judged |
| JP14 | `jupiter_baseline`, h₁: one series `leak_K` shifted by 2⁻⁵² of its largest value, the other two rungs honest | the entry's class is by the rule, and no fail is invented |
| JP15 | `base s0 w0`, all three rungs: the rows `channel_K` multiplied by 1.01, every blind family honest | `base` fails, and the record shows that its 30 blind families pass |
| JP16 | `base s0 w0`, h₁, refused (kind `domain`), every blind family honest | `base` inconclusive, and the record shows that its 30 blind families pass |
| JP17 | `base s1 w0`, h₃: one change deleted from `switch_list` alone | a fail of class E of the switch list. The channel schedule's entry passes |
| JP18 | `base s1 w0`, h₃: one character of the `assembly_observable` string changed, and the label kept | refused, and nothing of the run judged. Not a fail plant |
| JP19 | `jupiter_baseline`, all three rungs: one `junction_K` (the last time) raised by 10⁻⁴ of its largest value | a fail of `junction_K` (S), and of the balances of the two cells (R) |
| JP20 | `jupiter_baseline`, all three rungs: the rows `work_pump` multiplied by 1.01 | a fail of `energy_identity`, and of no S entry against a capture |
| JP21 | `jupiter_baseline`, h₂: its class S rows replaced by the captured rows of `jupiter_baseline-h2`, and `heat_leak`, `heat_pump` and `heat_channel` too, by a split of the captured `dissipated_energy_pJ` (the captures hold the sum alone) | refused by the copy guard (b), its readouts judged |
| JP22 | EP1's rows made equal to its honest run's (`jupiter_baseline`, h₃) | EP1 is not caught, and `jupiter` fails |
| JP23 | `integrated`, h₃: an extra string in `declared_strings` | refused, and nothing of the run judged. Not a fail plant |
| JP24 | `jupiter_baseline`, h₃: `steps` one more than end_s/step_s | refused (the reason `off_grid_change`), its readouts judged |

**A judge's plant that the code scores otherwise stops the judge's tag.**

## 7. The structural plants of Part 2

`PART2.md` §7.

## 8. The margins (from the legacy side alone), 25 November 2026

Every run here is a run of the frozen snapshot, with one declared change of a definition or one host-side patch of an imported module, made after the first commit of this branch (5b56f92c, 11:23:02 UTC). The first control began at 11:24:59 UTC. `plants_manifest.json` holds each run's command, patch text, definition, output folder and
sha256, and `margins.json` the numbers below, entry by entry. No band, class or window moved because of one.

**The controls.** An unpatched run of the snapshot equals the captured arrays **bit for bit**, every array, in every world:

| World, captured step | Arrays compared | Runs |
| --- | --- | --- |
| `jupiter_baseline`, 25 µs | 364 | twice (alone, and after the patched runs of its process) |
| `jupiter_pump_release`, 25 µs | 364 | twice |
| `integrated`, 25 µs | 288 | twice |
| `base` seed 0, 12.5 µs | 35 | once |
| `cell` seed 0, 25 µs | 33 | once |

**Where several patch-free runs shared a process,** the batch ended with a second control that equals the captured array too. So nothing of a plant leaked into another run.

**The power plants, per mechanism.** A cell of the table holds the ratio of its home entries' plants (smallest to largest) and the **smallest margin** over them, at U_c = 0. Assembly worlds: the smallest over the eight worlds of seed 0.

| Mechanism | `jupiter_baseline` | `jupiter_pump_release` | `integrated` | `base` | `cell` |
| --- | --- | --- | --- | --- | --- |
| leak permeability | 9.6e-03 to 1.0e-02, 1e+07 | 9.5e-03 to 1.0e-02, 2e+07 |  | 9.4e-03 to 1.0e-02, 1e+07 | 8.4e-03 to 2.8e-02, 1e+07 |
| channel permeability | 1.0e-02, 3e+06 | 1.0e-02, 3e+06 |  | 1.0e-02, 1e+05 | 9.5e-03, 4e+05 |
| channel kinetics | 3.4e-05 to 3.7e-03, 2e+06 | 3.5e-05 to 3.7e-03, 2e+06 |  | 3.4e-05 to 1.2e-02, 2e+06 | 1.8e-05 to 1.2e-02, 1e+06 |
| Na/K pump | 1.0e-02, 4e+08 | 1.0e-02, 3e+08 |  | 1.0e-02, 4e+08 | 1.0e-02, 3e+08 |
| junction permeability | 8.6e-03 to 9.3e-03, 2e+07 | 8.4e-03 to 9.3e-03, 2e+07 | 8.7e-03 to 9.4e-03, 6e+07 | 7.8e-03 to 9.3e-03, 1e+07 |  |
| junction gate | 5.6e-04, 3e+07 | 5.7e-04, 3e+07 | 9.8e-04, 1e+08 | 5.6e-04, 3e+07 |  |
| faces | 9.8e-03 to 9.9e-03, 2e+07 | 9.8e-03 to 9.9e-03, 2e+07 |  | 9.8e-03 to 9.9e-03, 1e+07 |  |
| electrical closure | 3.5e-03 to 9.2e-03, 5e+04 | 2.8e-03 to 9.2e-03, 4e+04 | 2.0e-03, 2e+04 | 3.5e-03, 5e+04 | 3.4e-03, 7e+04 |

- **Every mechanism of every consumer is observable.** The smallest margin of any entry (home or not) is 1.3 × 10³ (`n_out_Cl` of `cell`), against the rule of 10, and the smallest of any home is 2 × 10⁴ (`voltage` of `integrated`). The entries that read an amount carry e_store (`SPEC.md` §6), which makes their margins 10² to 10⁴ times smaller than a band without it, and leaves them above 10³. Otherwise the weakest homes are `channel_K` in `base` and `cell` (the band is set by the gross throughput, and the channel's net amount is small) and the gate h (a ratio of 2 × 10⁻⁵ to 3 × 10⁻⁵, because it moves little in 20 ms), for which `gate_m` is the other home.
- **`voltage`** is a home of the electrical closure, which has no constant of its own. Its plant is the one that moves it most (`PW-pump`, `PW-leak` or `PW-junction`).
- **An assembly's plant (PW-pool).** The snapshot's own pool, run alone, with one rate × 1.01: the four arrays `last_event_time_s`, `pending_time_s`, `dwell_completed_s` and `first_passage_s` change for every rate in both pools of `base`, and for the on, off and close rates in `cell` (the last event's time moves in 37, 37 and 23 of its 64 worlds). In `cell` the dissolve rate moves one array (`pending_time_s`) and no event time. No rate changes an event count in 20 ms. So every rate is observable in class E, which has no margin. The runs and their sha256 are in `plants_manifest.json` (`pool_plants`).

**The structural plants.** All are above 10 times the band by a wide margin, so each is scorable:

| Plant | Named entry: distance, margin |
| --- | --- |
| ST1 pump direction (`jupiter_baseline`) | `n_cell_Na`: 5.9e-03, 3e+08; `n_cell_K`: 4.1e-03, 3e+07; `voltage`: 5.0e-02, 1e+07 |
| ST2 leak valence of Cl (`jupiter_baseline`) | `leak_Cl`: 1.5e-04, 4e+10 |
| ST3 inactivation gate left out (`jupiter_baseline`) | `channel_K`: 1.3e-06, 1e+08 |
| ST4 junction voltage sign (`jupiter_baseline`) | `junction_Na`: 4.7e-06, 8e+09; `junction_K`: 7.9e-05, 9e+09; `junction_Cl`: 4.2e-06, 8e+09 |
| ST5 Na and K face diffusivities exchanged (`jupiter_baseline`) | `face_Na`: 5.3e-02, 5e+08; `face_K`: 2.3e-02, 3e+09 |
| ST8 pump released on one membrane (`jupiter_pump_release`) | `pump`: 2.5e-04, 1e+10 |
| ST9 the schedule is not applied (`integrated`) | `junction_Na`: 2.7e-06, 7e+09; `junction_K`: 2.8e-05, 6e+09; `junction_Cl`: 1.5e-06, 3e+09 |
| ST6 availability on the other cell's channel (`base`, world 2) | `channel_K`: 2.9e-07, 2e+07 |
| ST10 availability held over the step (`base`, world 2) | `channel_K`: 1.4e-09, 1e+05 |
| ST7 availability inverted (`cell`, world 1) | `channel_K`: 6.8e-06, 4e+06 |
| ST10 availability held over the step (`cell`, world 1) | `channel_K`: 2.5e-07, 1e+05 |

- **ST1 and ST4** were refused by legacy's own ledgers at their first attempts ("Finite local/outside/global material, charge or resolved-energy accounting failed" and "Membrane/junction diagnostic dissipation must not decrease"). That is evidence that legacy's own checks see these errors, and it left no planted array. They were run again with those two ledgers off and the domain checks on.
- **ST10, the held factor.** What holding the availability at the start of each step does to legacy's own end state, at the captured h/4 (12.5 µs in `base`, 25 µs in `cell`): `channel_K` at 0.02 s moves by 0.2 % to 2.7 % of itself in the eight worlds of `base` (seed 0) and by 0.0 % to 0.5 % in the first eight of `cell`. It depends on where each event falls in its step, so it has no order. In some worlds it is as large as a 1 % change of a rate constant, or larger. ST10's named entries are far above their bands (a margin of 10⁵), so a driver or an engine that rounds events to its steps is caught. The design authors' own holding study (the protocol's §11) was not read.

**Where a margin is not evidence.** A margin compares legacy with legacy. It says what the band can see of a change of that size, and nothing about a candidate's own step, whose U_c is added to the band (`CRITERIA.md` §4.5).
