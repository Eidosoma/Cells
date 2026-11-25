# The readouts: names, units, signs, sources and where they are judged (Part 1)

Both sides use these names. The exporter takes the canonical column. The judge takes the captured column from the captures.

## 1. Orientation

- **Into the cell is positive** for `leak_x`, `channel_x`: amounts that entered the cell through that route, from time 0.
- **Sender to receiver is positive** for `junction_x` and `face_x`. A junction's sender is the captured `from_cell`.
- **A pump cycle is positive** when it moves 3 Na out and 2 K in.
- **A voltage** is the inside's potential less the outside's. A potential is relative to the gauge region, which is at 0 V.
- **An increment** is an amount less the initial amount of the same compartment, in fmol.
- **A heat is a dissipation:** positive, cumulative from time 0, in pJ. **A pump's work** is the work its fuel put in, positive and cumulative.

## 2. The series

`x` is Na, K or Cl. The captured index of a species is its position in the definition's list of species (Na, K, Cl). Slots past the declared entities are padding and are not
read. Entities are matched by their ID. The captured index of a cell, membrane, channel, junction, region or face is its position in the captured definition's list, in **natural order** (`SPEC.md` §4): `junction_2` before `junction_10`, and never a text sort. A pool array's world axis is the world ID, and a cell axis is (`cell_0`, `cell_1`).

| Name | Unit | Entities | Canonical source | Captured source, and its sign relative to the name |
| --- | --- | --- | --- | --- |
| `n_cell_x` | fmol | cells | the cell's `amount_increment` | `amount_increment[x, cell]`, same |
| `n_out_x` | fmol | outside regions | the region's `extracellular_amount_increment` | `extracellular_amount_increment[x, region]`, same |
| `leak_x` | fmol | membranes | **minus** `membrane_transferred`, which is outward | `leak_transferred[x, membrane]`, same (inward) |
| `channel_K` | fmol | channels | **minus** `channel_transferred[K, channel]`, which is outward | `channel_transferred[channel]`, same (inward) |
| `junction_x` | fmol | junctions | `junction_transferred`, sender to receiver | `junction_transferred[x, junction]`, same |
| `face_x` | fmol | faces | `face_transferred`, sender to receiver | `face_transferred[x, face]`, same |
| `pump` | fmol of cycles | membranes | `pump_cycles` | `pump_cycles[membrane]`, same |
| `gate_m`, `gate_h` | 1 | channels | `channel_gate` in the law's gate order m, h | `gate[0, channel]`, `gate[1, channel]` |
| `junction_gate` | 1 | junctions | `junction_gate` | `junction_gate[junction]` |
| `heat_leak` | pJ | membranes | `membrane_dissipated_energy_pJ` | none alone (§5) |
| `heat_pump` | pJ | membranes | `pump_dissipated_energy_pJ` | none alone (§5) |
| `heat_channel` | pJ | channels | `channel_dissipated_energy_pJ`, summed over species | none alone (§5) |
| `heat_junction` | pJ | junctions | `junction_dissipated_energy_pJ` | `junction_dissipated_energy_pJ[junction]` |
| `heat_face` | pJ | faces | `face_dissipated_energy_pJ` | `face_dissipated_energy_pJ[face]` |
| `work_pump` | pJ | membranes | `metabolic_work_pJ` | none |
| `voltage` | V | membranes | the observation's `membrane_voltage_V` | `observations.voltage_V` (`jupiter`, `integrated`), `final_voltage_V` (`cell`, `base`) |
| `phi_out` | V | outside regions but the gauge | the observation's `extracellular_potential_V` | `observations.extracellular_potential_V[region]` (`jupiter` alone) |

**Signs that a wrong reading would swap.** The inner model books its leak and channel transfers outward, legacy books them inward, and the judge reads
`leak_x` and `channel_K` as inward on both sides. So the exporter flips two signs and the judge flips none. A plant tests it (`PLANTS.md`).

**A series absent from a world counts as zero in every sum that names it** (the balances, `heat_membrane`, the energy identity), and is no entry. Per consumer:
- **`cell`** has no junction and no face, so no `junction_*`, `face_*`, `heat_junction`, `heat_face`, `junction_gate`, `phi_out`.
- **`base`** has every series of `jupiter`, but no captured `phi_out`.
- **`integrated`** has no pump, leak or channel, so it has neither their series nor `heat_membrane`. It has no face. Its outside region is touched by no
  route (**`n_out_x` is zero**, class E). Its potentials are at its block's `potential_times_s`.

## 3. What is judged, and over which times

**Every row of this table is an entry.** An entry of a family is one readout, over all its entities and compared times (`SPEC.md` §4).

| Consumer | Class S, over the compared times | Class S at the potential times | Others |
| --- | --- | --- | --- |
| `jupiter` (a family: one arm) | `n_cell_x` (3), `n_out_x` (3), `leak_x` (3), `channel_K`, `junction_x` (3), `face_x` (3), `pump`, `gate_m`, `gate_h`, `junction_gate`, `heat_membrane`, `heat_junction`, `heat_face`. 23 | `voltage`, `phi_out`. 2 | E (restart), R (§5), D. `energy_identity` is class S (§5) |
| `cell` (a family: one seed, one world ID) | `n_cell_x` (3), `n_out_x` (3), `leak_x` (3), `channel_K`, `pump`, `gate_m`, `gate_h`, `heat_membrane`. 14 | `voltage`, at `summary_times_s`. 1 | E on the pool and the schedule (§4), R (§5: exposure and balances), D, `energy_identity` |
| `base` (a family: one seed, one world ID) | the `jupiter` 23 at `end_s`. 23 | `voltage` at `summary_times_s`, and `channel_K` at `summary_times_s` (`channel_K_summary`, whose scale is `channel_K`'s; its row at `end_s` is also in `channel_K`, so one difference there fails both entries). 2 | E on the pool and the schedule, R, D, `energy_identity` |
| `integrated` | `n_cell_x` (3), `junction_x` (3), `junction_gate`, `heat_junction`. 8 | `voltage`. 1 | E: `n_out_x` zero. R, D, `energy_identity` |

- **The counts are per family.** Entries against captures: `jupiter` 25 (2 families, 50), `cell` 15 (32 families, 480), `base` 25 (32 families, 800), `integrated` 9 (1 family, 9). Each family has one `energy_identity`.
- **`energy_identity` has no captured counterpart.** It is the run's own identity (§5).
- **R entries per ionic judged run** (§5): one balance of cells per species (3), one of regions per species (3), one of the closed world per species (3), and one capacitor: ten, over all entities and times. A pool run has one exposure per cell. In all: `jupiter` 60, `cell` 960, `base` 960, `integrated` 30 from the ionic judged runs, and 4 and 8 exposures for `cell` and `base`.
- **E entries:** per pool run and cell, the 19 arrays (19), the run's own path (1) and the seed (1). Per judged ionic run of `cell` or `base`: the switch list, the channel schedule and the pool seeds (one each). Per restart: one per class S readout and potential (25 in `jupiter`), and for a pool restart, per cell, the 19 arrays and the path after the restart (20). `n_out_x` of `integrated` (3 per judged run). In all: `jupiter` 25, `cell` 392, `base` 496, `integrated` 9.
- A consumer whose entries formed are fewer than these, in any class, is at best inconclusive (`CRITERIA.md` §5).

## 4. The assembly pool's arrays (class E)

A pool run (`cell s<k> pool`, `base s<k> pool`) exports, per cell, the 19 final arrays of the live pool, in the world order of the seeds' IDs:

`occupied`, `bonds`, `free`, `fragments`, `time_s`, `last_event_time_s`, `event_count`, `pending_time_s`, `pending_event`, `pending_valid`, `reaction_counts`, `removed`,
`single_returns`, `dissolved`, `dwell_completed_s`, `first_passage_s`, `full_first_s`, `full_dwell_completed_s`, `fault`.

- **Captured:** the checkpoint's `pool_<name>`, which is `[world, ...]` in `cell` and `[world, cell, ...]` in `base`, with the cells in the order (`cell_0`, `cell_1`).
- **All 19 are bit-identical** across h, h/2 and h/4 in every captured job, and equal to what the snapshot's own pool code gives when it
  runs alone. So class E has one reference per seed, and no step.
- **`availability_exposure_s` is not class E.** It differs by a unit in the last place across legacy's own steps. Class R, with its own bound (§5).
- **`segments` and `tick` are not compared.** They count the ionic steps and splits, so they depend on the step.
- **The event path** (`reference_paths.json`) is class E: every committed event of every world, its time as a double and the availability after it.

## 5. What the judge forms from a run's own rows

| Formed | From | Class and tolerance |
| --- | --- | --- |
| `heat_membrane` (per membrane) | `heat_leak` + `heat_pump` + Σ `heat_channel` of that membrane's channels, against the captured `dissipated_energy_pJ[membrane]` | S. **Legacy lumps the three**, so only the sum is compared |
| **Balance of a cell**, at every compared time | `n_cell_x` = Σ over its membranes (`leak_x` + `channel_x` + ν_x `pump`) ± Σ over its junctions, with ν = −3 for Na, +2 for K, 0 for Cl, and a junction's amount minus at its sender, plus at its receiver | R: 8 ε (S + 1) s(`n_cell_x`) + e_store(`n_cell_x`) |
| **Balance of a region** | `n_out_x` = −Σ over the membranes that face it (`leak_x` + `channel_x` + ν_x `pump`) ± Σ over its faces | R: 8 ε (S + 1) s(`n_out_x`) + e_store(`n_out_x`) |
| **Closed world** | Σ over cells `n_cell_x` + Σ over regions `n_out_x` = 0 | R: 8 ε (S + 1) (N_cells s(`n_cell_x`) + N_regions s(`n_out_x`)) + N_cells e_store(`n_cell_x`) + N_regions e_store(`n_out_x`) |
| **Capacitor**, at the potential times | `voltage` − V₀ = (F 10⁻¹⁵/C) Σ_x z_x `n_cell_x` of its cell, with **V₀ the run's own `voltage` at time 0** | R: (8 ε (S + 1) + 4 × 10⁻¹²) s(`voltage`) + e_store(`voltage`) |
| `energy_identity`, at every compared time | below | **S with the exact value 0**, scale s(`energy_identity`), `CRITERIA.md` §4.3 |
| Exposure of a pool | Σ of the intervals of the event path during which the availability is 1, against the captured `availability_exposure_s` of that world and cell at h/4 | R: 2 ε × `end_s` × (2 + the captured job's `segments` of that world) |

**The energy identity** (a closed world, no reservoir):

    E(t) = Σ_compartments Σ_x 10⁻³ R T [ d (ln(n₀/V) − 1) + (n₀ + d) ln(1 + d/n₀) ]          (d the increment, n₀ the initial amount, V the volume)
         + Σ_membranes ½ 10¹² C ΔV (2 V₀ + ΔV),   ΔV = (F 10⁻¹⁵/C) Σ_x z_x n_cell_x,   V₀ the run's own voltage at time 0
         + Σ heats (heat_leak, heat_pump, heat_channel, heat_junction, heat_face)  −  Σ work_pump  =  0

- **The times of the identities** are: `jupiter` and `integrated`, every compared time; `cell` and `base`, `summary_times_s`. A run needs rows of every series that an identity reads at those times, and the run's `voltage` at time 0.
- **e_store** is `SPEC.md` §6's term, 2.5 ε (S + 1) × `amount_refs`, with S the run's own grid's. It is 0 for a series that an entry does not read.
- **It is a property and not a comparison with legacy.** Where an integrator books its heats as integrals, it closes at the integrator's order and not at rounding. That is why it is class S (FR-38's amendment 3), and the balances are class R.
- **The sign of `work_pump`:** the fuel's work enters the world, so it is subtracted from the stored and dissipated energy.
- **Where an identity has zero scale** (a species with no route), the value is exactly zero.
- **Conservation is judged beside the engine's own rule, and not instead of it** (`CRITERIA.md` §4.4). These are Part 1's (the lead's ruling of 25 November, which reverses its earlier one for Part 1). In Part 2 the same formulas are reported and not judged.
- **The formulas, signs and scales were checked on the reference side,** on the captured arrays of every Part 1 world at h/4: every balance is at most 5.3 × 10⁻⁴ of its bound, the capacitor at most 3.1 × 10⁻⁶ of its, and every energy identity at most 1.1 × 10⁻⁶ of its, with U_c = 0 and e_store taken as 0, which is the form legacy's state has (the author's check of 25 November, after the ruling and after the planted numbers had been read). No bound moved because of it.

## 6. Recorded, never judged

- **The table's** `definition`, `checks`, `steps`, `heat_leak`, `heat_pump`, `heat_channel` alone, and any extra series. `heat_leak`, `heat_pump`, `heat_channel` and `work_pump` feed `heat_membrane` and `energy_identity`, so a missing one leaves those entries not formed.
- **Not compared, and why:**
  - legacy's rates, affinities, currents and powers at the observations. The transfers carry their integrals.
  - `segments` and `tick` (§4).
  - the Hermite-interpolated samples off the grid (`SPEC.md` §2.3).

## 7. What in the captures is not a canonical quantity

- **Windows.** A row that two windows share belongs to the earlier one (`SPEC.md` §4).
- **The captured capacities** are padded: slots past the declared entities hold zeros (`SPEC.md` §2.3).
- **`observations.amount_increment` and the rest** repeat the history's rows at the observation times, interpolated where a time is off the grid. The
  judge reads `history.*` for everything but the potentials.
