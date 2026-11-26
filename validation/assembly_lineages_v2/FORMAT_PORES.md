# The engine's output format for vesicle pores, Phase A (`cells.model.assembly_lineages@2`; FR-31)

This page adds to `FORMAT.md` and `FORMAT_OL2.md` what a world writes when it declares the pore law.
A world that declares neither the pore law nor a hold writes exactly what those pages describe: no
key, row, record or legend entry below appears in it.

The laws are `docs/VESICLE_PORES_LAWS.md`, tagged `pores-laws-sheet-registered-2026-11-22`. The
design is `docs/VESICLE_PORES_DESIGN.md`, with D287 and the lead's rulings of 22 November 2026.
Phase A ruptures a vesicle under a held tension. It has no pore episodes: an open pore ruptures at
once.

## The world: `hazard`

`{law: cells.assembly_hazard.pore_nucleation@1, nu_A, gamma_N, E_A_J_per_mol, eta_298_Pa_s_m}`. Each parameter is
`{value, provenance}`, positive, for one lipid composition:

| Key | Unit | What |
| --- | --- | --- |
| `nu_A` | m⁻²·s⁻¹·(N/m)^(−1/2)·K^(3/2) | the prefactor scale, per membrane area |
| `gamma_N` | N | Γ, the pore's line tension, constant in T |
| `E_A_J_per_mol` | J/mol | E_A, the membrane viscosity's activation energy |
| `eta_298_Pa_s_m` | Pa·s·m | η₂₉₈, the membrane's surface viscosity at 298.15 K |

The law is the first of a new interface, `cells.assembly_hazard@1`: a vesicle's hazard on a clock.
It reads the tension, the area and the world's temperature, draws on the stream domain `pore`, and
its outcome is a lysis. T is the world's `units.temperature_K`.

**Refused at parse:**
- the law without `cells.assembly_geometry.bilayer_geometry@1`: with no geometry, or with FR-21's prescribed shell.
  The vesicle's area is the bilayer's, A = q·W/2.
- any step that changes a membrane place's count (its net change at any membrane place, not the
  membrane's total), so each vesicle's area, and its rate, stay fixed through a hold;
- a membrane or lumen species with no pool place to return to at a rupture;
- a parameter missing, unknown, not `{value, provenance}`, or not positive.

## The experiment: `tension_holds`

`[{index, sigma_N_per_m, start_s, end_s}]`: a tension σ held on every living vesicle over
[start_s, end_s), whatever its counts. It is `cells.operator.tension_hold@1`, an assembly operator with a
work role: an applied protocol, a pipette's, so it lives in the experiment, not in the world id.

**Refused:**
- in the hold itself: a second hold, or an overlapping one (Phase A holds one tension per world);
  keys other than the four; σ not positive; start_s negative; end_s not after start_s;
- against the world, once both are parsed:
  - the pore law without a hold;
  - a hold without the pore law (its only reader in Phase A);
  - a hold with `lumen_volume: osmotic`;
  - σ > σ_β/4, with σ_β = πΓ²/(k_B·T) at the world's Γ and T.

## The clock

- **The rate.** A vesicle of area A has
  k_v = A·ν_A·σ^(1/2)·T^(−3/2)·exp(−E_A/(R·T))·exp(−πΓ²/(σ·k_B·T)), with R = N_A·k_B, both exact
  (SI 2019).
- **The threshold.** Each vesicle draws once, when the run first holds it (a founder, at the run's
  start). u comes from the pore stream, domain 7: @1's derivation, carrier word the vesicle's key,
  counter 0. E = −ln u.
- **The rupture time.** t* = start_s + E/k_v(σ), when t* ≤ end_s; otherwise the vesicle does not
  rupture in the hold. A t* past the horizon is no event of the run.
- **Exact endpoints.** Both comparisons are decided exactly, as rationals of the binary64 values of
  E, k_v (the `rate_per_s` an event records), start_s and the cutoff:
  - t* ≤ end_s as E/k_v ≤ end_s − start_s, and t* ≤ the horizon as E/k_v ≤ horizon − start_s;
  - the t* the host schedules and records stays the float64 value of start_s + E/k_v;
  - from one start (Phase A's one hold), rounding never carries a crossing across a cutoff. It can
    only round it onto the cutoff, and only there does the exact rule decide otherwise than
    t* ≤ cutoff: a t* equal to its cutoff is an event when the exact crossing is at or before it,
    and not when the crossing lies beyond;
  - a vesicle that the hold's end decides this way does not rupture in the hold: its `t_star` is
    null and its `pore_draw_time` inf;
  - the case is the Lean lane's finding of 22 November 2026: a founder ruptured at a hold end that
    its exact crossing passes by 2.4 × 10⁻¹⁷ s.
- **The stop.** t* is a stop of the host:
  - the chemistry draw that crosses it is discarded and counted, as at a schedule stop;
  - a device that ends `inert` before t* is advanced to it;
  - the device kernel is the same program in every world.
- **The end status.** While a vesicle lives, its clock runs. A world whose chemistry is idle ends
  `complete` at the horizon, never `inert`. A population whose vesicles have all ruptured may end
  `inert`.
- **Same-time stops** are refused at the run's start: a t* equal to another vesicle's, or to a
  schedule stop's time (FR-20's rule). The times are compared as recorded, in float64, with exact
  equality:
  - Relations read the recorded times, so two crossings that round to one t* are one time there.
    An exact tie also rounds to one t*, so this refuses it too.
  - Rounding never reverses two crossings from one start, so stops that are not refused run in
    their exact order.
  - D283's same-instant band (4 ulps) is not used. It is for declared times on a fixed step's
    grid, and this clock has no grid.
- **The stream identity** of a pore world adds `domains.pore = 7` and `carriers.pore` to the
  identity its mode would state. Every other run's identity is unchanged.

## A rupture, and its booking

The opening is the forward of an event pair, from closed to a pore at r_c = Γ/σ. Its reverse, the
critical pore's collapse, has rate P = (σ_β·σ)^(1/2)/ζ, with ζ = 4π·η_m(T) and
η_m(T) = η₂₉₈·(T/298.15 K)·exp[(E_A/R)·(1/T − 1/298.15 K)]. Then:
- the hold does w = σ·πr_c² = σ_β/σ (k_BT);
- the vesicle's F rises by ΔF = 2σ_β/σ − ln(A·n_s) (k_BT), with the site density
  n_s = 4π·η₂₉₈·ν_A·exp(−E_A/(R·298.15 K))/(π^(1/2)·Γ·k_B^(−1/2)·298.15 K);
- the opening books `opening_heat_kT` = −ΔF + w = ln(A·n_s) − σ_β/σ, which is ln(k_v/P).

The open pore ruptures at once, through the lysis's release from the open state:
- the membrane's and the lumen's molecules go to their species' pool places;
- a held place's reservoir takes them back, booking w_r = −Σ μ_held × the molecules it takes;
- the closure cost is released;
- it books `release_heat_kT` = −(F(after) − F(open)) + w_r, with F(open) = F(n) + ΔF, F(n)
  including the closure cost.

**The event's total.** Its heat, `opening_heat_kT` + `release_heat_kT`, is
−(F(after) − F(n)) + w + w_r. ΔF cancels, so the books close whatever η₂₉₈ is: η₂₉₈ moves only
how the heat divides between the opening and the release.

## The records (pore worlds only)

- **records.npz** adds `tension_hold_work_kT` [row, hold]: each hold's work, cumulative. The
  ledger's booked work adds its columns' sum, as it does `schedule_work_kT`'s.
- **`row_kind` 9, `pore`.** A row at each rupture's time, holding the released state, after
  which the vesicle's places are empty.
  - In a single lineage the end row follows it, at the same time and state.
  - In a population the slot is free from that row on, its `slot_key` −1.
- **run.json**
  - **`pores`:**
    - `law`, `parameters` (as declared), `units`;
    - `derived`: `temperature_K`, `sigma_beta_N_per_m` and `log_site_density_per_m2`;
    - `events`: each a `{time_s, slot, key, hold, sigma_N_per_m, area_m2, rate_per_s,
      threshold_E, counter, work_kT, opening_heat_kT, cause, release}` record. Its `cause` is
      `pore`, and its `release` is `{returned, release_heat_kT, release_reservoir_work_kT}`:
      `returned` by pool place, with σ the hold's and no σ_max;
    - `causes`: `{pore, threshold}` counts. A σ_max lysis is the `threshold` cause, and Phase A
      has none, since a hold refuses an osmotic lumen.
  - **`tension_hold`:** each hold as `{index, sigma_N_per_m, start_s, end_s, payer}`, with
    `payer` `source:tension_hold/<index>`.
  - **The lifecycle, the bases and `ssa.pore_clock`** state the clock's rule.
- **The diagnostic record:**
  - `fates` adds `discarded_at_pore`, code 3, for the chemistry draw that crosses a pore stop. A
    population's world draws take it in the order of the stops applied.
  - `pore_events` repeats run.json's events.
  - The domain-7 draws are `pore_draw_key`, `pore_draw_counter`, `pore_draw_uniform`,
    `pore_draw_threshold` (E) and `pore_draw_time` (t*, inf when no hold brings H to E), one row
    per vesicle's draw.
  - No step event is marked `event_lysed` for a rupture.
- **relations@2 (a population):**
  - each rupture is a `lysis` event at its life, `by` `cells.assembly_hazard.pore_nucleation@1`, paid by
    `source:tension_hold/<index>`;
  - that source has kind `schedule`, class `energy`, `declared_by` `cells.operator.tension_hold@1` and
    `payer_of` `tension_hold_work_kT`;
  - a single lineage writes no relations, as for a lysis.

## The pair check

run.json's `check.pores` holds the identity ln k_v − ln P + (ΔF − w)/k_BT = 0, taken from three
separate statements of the sheet: the law's rate, its reverse, and the pore's energy (r_c = Γ/σ,
ΔF = 2πr_cΓ − k_BT·ln(A·n_s), w = σ·πr_c²). It is checked in two places, and a run is refused
before its first event if either fails:
- `probe`: the check's own 240 generic states, from seed 20261125. Their parameters, tension,
  temperature (260 to 380 K, away from 298.15 K, where η_m's factors are 1) and area are random.
  The tolerance is 1e-9 in ln.
- `world`: the world's temperature and parameters, at each hold's σ and each vesicle's area.

## Checkpoints of a population (FR-22, rung P)

- **What the checkpoint keeps.** The host's document adds `pores`: each living vesicle's
  `{slot, key, threshold_E, counter, t_star}`, with `t_star` null when no hold brings H to E.
- **A restart** rebuilds each clock from its vesicle's key and counts, and refuses a checkpoint
  whose clocks differ.
- **The applied stops.** A rupture is a host stop, not a committed event, and it stays out of
  `applied_stops`, which counts the schedule's stops.
- **A cut at a rupture's time,** whether the rupture was applied or is pending, is refused, as a cut
  at a lysing event is.
- **Joining two segments.** Each segment's ruptures (`pores.events`) are its own. The threshold
  draws (`pore_draw_*`) are the first segment's, since a vesicle draws when the run first holds it.

## The device clock: a tension from F (OL6 S4, L1)

A pore world with no hold takes its tension from F: `lumen_volume: osmotic` is then required, with
σ_max ≤ σ_β/4 (refused otherwise: "with sigma from F the tension reaches sigma_max"), and steps that
change a membrane place's count are admitted (under a hold they stay refused, with Phase A's words:
T2). Its clock is on the device (`pore_device.py`); Phase A's hold worlds keep the host clock above,
and their records, unchanged.
- **The clock.** Each vesicle draws E as above, a founder at the start and a daughter at its birth
  (H = 0 then). Between events the state holds, so each committed event adds k_v(n)·τ to H, with
  k_v at the state before it (σ from the lumen's exact (N_L, W), A = q·W/2). The candidate opening
  t_c = t + max(0, E − H)/k_v bounds the device's horizon: the chemistry draw that would land past
  it is not committed, and the pore fires at t_c (fate `discarded_at_pore`; a device that halted
  inert is advanced to it). A t_c at a schedule stop's time, or two slots' at one time, is
  refused (FR-20's rule).
- **The booking.** The opening has no hold: w = 0 and ΔF = σ_β/σ − ln(A·n_s) (the sheet's §7, "where
  σ comes from F"), so q_open = ln(A·n_s) − σ_β/σ as under a hold; then the release from the open
  state, so ΔF cancels in the event's total.
- **The records.** No `tension_hold_work_kT` column and no `tension_hold` holds. `pores.events` adds
  `clock_H` (H at t_c) and `delta_F_kT`, with `hold` null, σ the lumen's at t_c and `work_kT` 0;
  `pores.draws` (and the diagnostic's `pore_draw_*`) hold one row per vesicle drawn, founders then
  daughters in birth order, its t* the rupture time or inf. relations@2 names no payer for such a
  rupture (`source` empty). `ssa.pore_clock` states the device's rule.
- **Checkpoints (a population).** The host document adds `pore_clocks`: each living slot's `{slot,
  key, H, threshold_E, rate_per_s, t_c}` as the device left it; a restart takes them as they are,
  and refuses a checkpoint whose living vesicle's key or threshold is not its definition's draw.
