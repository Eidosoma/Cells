# FR-8's stage 0: criteria and budgets of M1–M5 and the harness (registered before any measurement)

*The FR-8 stage-0 owner, branch `fr8-stage0` from main a15f443a. Written from 20:34 UTC on 18
November 2026 (`date -u`). Nothing named here was built, parsed or run for this measurement
before this file was committed. D217 and D222 approve stage 0 only: measurements M1–M5 and a
small numerical harness (docs/LONG_DURATION_MODE_DESIGN.md §6 and §11). No method is chosen, and
no solver, mode or booking is built. The numbers below are also in
`registration_20261118.json` beside this file, which the drivers read.*

**Engine models it runs** (AGENTS.md): `resolved_pump_tissue@3` (S7a, S7b, S127, T825, H2);
`resolved_pump_tissue@1` (D1); `resolved_pump_composite@1` over `resolved_pump_tissue@3` with
`scheduled_species_turnover@1` and `species_regulated_availability@1` (W0); and the analysis
`stationary_continuation_analysis@1` (M2).

## 0. Rules

- **Declared here, before any comparison runs.** A budget is cumulative from t = 0 and holds at
  every record, never per step (the note's §2 lesson).
- **The parity caps stay as benchmarks** (|dVm| ≤ 20 µV, |dc|/c ≤ 2 × 10⁻⁴, projective's
  `criteria.absolute_caps`). They are reported beside every trajectory comparison and judge
  nothing.
- **No engine tolerance or check is loosened, bypassed or replayed around.** A refusal is a
  result: its check, its message and its time are reported, and it ends that arm.
- **Amendments** are dated additions in §10, written before the run they affect, never edits
  of the text above them.
- **Provenance.** Every run of record starts from a clean snapshot of a committed head of this
  branch (`validation/source_snapshot.freeze` over the tracked files). Its outputs and logs go
  under `/mnt/workspaces/Cells/fr8-stage0-20261118/`, and each record names the snapshot's
  revision.
- **CPUs.**
  - Cost runs go on the timed lane (CPUs 4, 5, 20, 21) under `locks/timed-cores-4-5.lock`, one
    thread per core.
  - Everything else goes on the light CPUs (6, 7, 22, 23) at nice 10.
  - Every job runs through `scripts/run_detached.sh` with a memory cap.

## 1. The worlds

Each is an existing builder's output, called as written. The changes listed are the only ones.

| ID | Builder (under `validation/`) and its call | Model | Used by |
| --- | --- | --- | --- |
| S7a | `tissue/pump_water_fixtures.gated_sheet(dt=1e-3, end_time=1.0)`: seven heredity cells (hexagon of radius 1), the centre in D and the ring in H, each with its held bath, joined by E07-v1's gated junctions at scale 1 (14 field nodes) | @3 | M1, M2 |
| S7b | `tissue/cell_replacement_fixtures.heredity_sheet(radius=1, disc=0, scale=0.6, dt=1e-3, end_time=0.1)`: the same sheet with the pre-screen's ionic background and junctions at scale 0.6. It is the coupling fixtures' base sheet (14 nodes) | @3 | M1, M2 |
| S127 | `heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=0.1)`: 127 cells, D inside ring 3 (254 nodes) | @3 | M1 |
| T825 | `tissue/pump_water_fixtures.scale_world(dt=1e-3, end_time=0.01)`: the W225 world with NaV1.2 and Kir2.1 on every patch (825 nodes) | @3 | M1 |
| D1 | `stationary/worlds.default_world_cell()`: one cell and its held bath with BETSE v1.5.0's default-world coefficients, at the INIT-end composition | @1 | M2 |
| H2 | The harness (§5): `tissue/projective_study.case_cue3` at a 3600 s horizon, with `execution.projective` removed | @3 | M1, harness, M3 |
| W0 | The stage-0 composed world (§1.1) | composite | M1 (operators' conditions), M3, M4, M5 |

### 1.1 W0, the stage-0 composed world

W0 is `regulated_availability_fixtures.dynamic_world`'s composition (milestone 2's moving world,
A8) with stage-0 times. Every piece is that module's own helper:

```text
raw = sheet(end=END, dt=DT, observation_times=OBS)       # S7b with the neutral regulator R at 1e-3 mM
raw = with_coupling(raw, species=["R", "Na"],
    states=[state("s", ["cell_0", "cell_3"], [("hill_activation", "Na", 12.0, 2.0)],
                  on=1/60, off=1/60, initial={"cell_0": 0.2, "cell_3": 0.2}, level=0.5)],
    couplings=[hill_coupling("c_r", "junction", ["junction_0"], "R", "hill_inhibition", 1e-3, 1.0,
                             side="first"),
               coupling("c_s", "junction", ["junction_0"], ("state", "s"), "state_complement",
                        side="both", basal=0.25)],
    switches={"c_r": [(0.0, 1)], "c_s": [(0.0, 1)]},
    writes=WRITES)                                         # per arm: [] or [("s", "cell_3", T, 0.9)]
raw = with_regulator_turnover(raw,
    [("clear_R", "cell_0", "clearance"), ("dose_R", "cell_0", "production")],
    [("clear_R", "cell_0", [(0.0, 1/300)]),
     ("dose_R", "cell_0", DOSE)])                          # per arm: [(0.0, P0)] or [(0.0, P0), (T, 2*P0)]
```

- P0 = (1/300 s⁻¹) × 10⁻³ mM × cell_0's declared volume: the production that holds R at its
  anchor.
- The channel step (M4's A1) is `kir_0`'s schedule in `channel_controls`, from 1.0 to 0.9 at T.
- The junction booking is the inner model's key `junction_heat_booking`. It is omitted for the
  default `explicit_tableau`, and set to `trapezoid_nonnegative@1` in M5's trapezoid arms.
- **The changes from `dynamic_world`:**
  - synthetic minute-scale rates, labelled synthetic as D217's first FR-7 acceptance is: R's
    lifetime is 300 s, and the state's k_on and k_off are 1/60 s⁻¹;
  - R is held at its anchor from t = 0, where `dynamic_world` has no production before its dose;
  - there is no switch interval for c_r, so each arm holds one intervention;
  - the events are per arm.
- **How W0 differs from the note's §5.1 acceptance world.** W0's couplings target `junction_0`,
  not a gate-free channel population. Its state reads Na, not R. This is question Q3.

## 2. The matrix: §11's six headings against each measurement

"n/a" means not applicable, for the reason given. "Rule" means a rule fixed in the section named.

| | Cumulative trajectory error | Intervention response | Threshold timing | Histories | Conservation | Measured cost |
| --- | --- | --- | --- | --- | --- | --- |
| **M1** | n/a: definition-time rates, no trajectory | n/a | n/a | n/a | n/a | host seconds, reported |
| **M2** | n/a: spectra at stationary states | n/a | n/a | n/a | E's conservation residual, reported | reported |
| **Harness (M3's world)** | ΔVm ≤ 2 µV; Δc/c ≤ 2 × 10⁻⁵; Δg ≤ 10⁻⁵ at every row (§5.3) | the same budgets on (1800, 3600] s, and the peak response within relative 10⁻³ (§5.3) | crossings within 0.5 ms; recovery reported to the row (§5.3) | relative 2 × 10⁻⁵ of each accumulator, with floors (§5.3) | every accepted row passes the engine's checks (judged) | rule §5.4: c_e2e, c_window, c_call; repeats within IQR/median 0.10 |
| **M3, operators' share (W0)** | n/a: a cost measurement | n/a | n/a | n/a | the engine's checks on the timed windows | rule §5.4 |
| **M4 (W0)** | n/a: one dt per arm, no second method | peak \|ΔVm\| from the control, reported | settling time per threshold (rule §6) | n/a | every accepted row passes the engine's checks | reported |
| **M5 (W0)** | by-product: each dt against 1 ms, caps reported, not judged | n/a | n/a | counting records compared as count × dt, reported | the energy ratio ρ at every row (rule §7), and every other ledger by the engine's checks | reported |

## 3. M1: @3's explicit bound per world, term by term

**Worlds:** S7a, S7b, S127, T825 and H2, each at its declared dt of 1 ms. For W0, the
operators' conditions are added.

**The terms.** Each is a rate r (s⁻¹) with its own bound B, and the step that term alone admits
is B / r.
- **Today's definition-time checks** (`models/surface_pump_v3.StepChecks`; the first five are
  `surface_pump.explicit_rate_bound`'s terms on @3's channel-free projection):
  - F: face diffusion;
  - J: junction charge relaxation, 2 max_i Σ_j G_j / C_i;
  - M: membrane charge relaxation at the passive patches, max_i Σ_m G_m / C_i;
  - N: neutral species' material relaxation (`neutral_material_rate`);
  - Z: a face-free node's charge relaxation (`face_free_node_rate`);
  - Ca: the calcium pump (`surface_pump_v2.calcium_rate_bound`);
  - K: the declared kinds' bound terms (`StepChecks.kind_rate`);
  - G: the junction gates (`junction_gate_rate_bound`), against `GATE_STEP_BOUND` = 0.125. Every
    other term is against `EXPLICIT_STEP_BOUND` = 1.
- **Today's run-time checks at every explicit stage**, evaluated at the declared initial state
  under the t = 0 controls:
  - Mc: membrane charge relaxation at the channels' actual openings (`membrane_rate`);
  - Kc: the kinds' material rate (`material_rate`). None of these worlds declares a kind.
- **Reported for N2, not in today's bound** (this registration's reading, S):
  - Cm: every species' material relaxation through junction and membrane permeation. It uses
    N's formula applied to all species, 2 max over species and nodes of Σ P A / V: the
    concentration-driven part, which implicit slope conductances would not take over.
- **W0's operators:** the coupling's dt (k_on + k_off) ≤ 1 per state (ruling 5). Turnover is
  exact at any step and has no condition.

**N2's classification** (S; question Q2):
- removed by N2: J, M and Mc;
- removed by N2 in the primary reading: Z (a patch slope conductance relaxing a node, the
  cell–outside coupling N2 makes implicit). The alternative, that it stays, is reported too;
- stays in the primary reading: N, since a neutral species carries no current. The
  alternative, that it is removed, is reported too;
- stays: F, Ca, K, Kc, G, Cm and the operators' conditions.

**Reported per world:**
- each r, dt × r at the world's dt, and B / r;
- dt_today, the smallest B / r over today's terms;
- dt_N2, the smallest B / r over the terms that stay, under each reading;
- the binding term in each case;
- the gains dt_N2 / dt_world, with dt_world 1 ms, and dt_N2 / dt_today.

**Criteria, judged.** M1 is not reported as a measurement if any of these fails.
- **C1.1, reproduction.** max(F, J, M, N, Z) equals `explicit_rate_bound` of the channel-free
  projection exactly, bitwise, per world. Ca, G and K equal their engine functions exactly. N
  and Z are the engine's own functions. F, J and M are recomputed on the bound's own layout from
  its formulas.
- **C1.2, the engine admits what M1 states.** With dt_def the smallest B / r over the
  definition-time terms, the world's `StepChecks` admits a step of 0.999 dt_def. It refuses
  1.001 dt_def with the binding term's own message.
- **C1.3.** Mc comes from the engine's own `membrane_rate`, never re-derived.

**Readings, stated before:**
- **The binding terms,** today and under N2.
- **gain_N2 against §1.1's illustrative step-count cuts of 10× and 100×.** A gain below 10× on a
  seven-cell sheet means N2's stability gain alone does not reach §1.1's first illustration, so
  §7's R1 question stays open. That is reported, not decided.
- **The junction-gate term G** is 1.3 e^(77 × 0.015) + 20 = 24.13 s⁻¹ on E07's junctions
  (threshold 15 mV) by its formula. GATE_STEP_BOUND would then admit at most 5.18 ms on every
  gated sheet, with or without N2. M1 measures it.

## 4. M2: the slow spectrum from E's dense eigenvalues

**Worlds:** D1, S7b and S7a, as @1 and @3 alone. E refuses the composite, so W0 is not analysed.

**Method:** `stationary_continuation_analysis@1`.
- **Slow mode:** formulation "rhs", globalization "auto", from the declared initial state. That
  is the INIT-end composition for D1, and the builders' states for the sheets (centre D, ring
  H). Its full dense spectrum is taken at the converged state (`stability(method="dense",
  count=0)`), with E's error bounds.
- **Fast mode:** at the converged composition, its dense spectrum at its own converged electrical
  state.

**The split, declared.**
- n_f is the fast problem's reduced dimension. The n_f eigenvalues of largest modulus in the
  full spectrum are its fast part, and the rest are its slow spectrum.
- The state is **separated** if both hold:
  - (a) the sorted moduli of the fast part and of the fast mode's spectrum agree pairwise
    within relative 0.1;
  - (b) ε = max |λ_slow| / min |λ_fast part| ≤ 0.1.

**Reported:**
- the spectra, with their rates, error bounds and relaxation times;
- n_f, ε, and separated or not;
- H_R1 = 1 / max |λ_slow|: the step at which an explicit slow integrator meets dt × rate = 1,
  EXPLICIT_STEP_BOUND's convention;
- H_R1 / dt_N2, with M1's dt_N2 for S7a and S7b.

**Outcomes.** Not converged, not consistent (E's step-map consistency), marginal (E's rule) and
not separated are all results.

**Benchmarks:**
- D1's slowest modes, 0.26 s, 189 s and 16,661 s (the qualified stationary analysis);
- the heredity cells' step spectra in the projective protocol's `burst_basis`:
  - H: slow 1/5500 and 1/219 s⁻¹; fast −3.87 ± 0.78i, −140, −1159 and −6804 s⁻¹;
  - D: slow 1/11100 and 1/212 s⁻¹; fast −3.40, −11.2, −430 ± 8.6i and −2891 s⁻¹.

**Reading, stated before.** H_R1 is the step R1's slow integrator would face at that state.
- If H_R1 ≥ 100 dt_N2, a reduction's step exceeds N2's by two orders there. This is reported for
  the choice, not decided.
- Not separated means R1's envelope fails at that state.

## 5. The harness and M3

### 5.1 The world, H2

H2 is `case_cue3`'s world, projective qual-01's F1:
- two independent heredity cells, each with its held bath, started at the saddle composition at
  U − 2 mV and U + 2 mV, with steady gates at those voltages;
- they settle onto H (cell_0) and D (cell_1) within about 2 s, and their compositions relax over
  hundreds to thousands of seconds;
- a 9× Na-leak cue channel on cell_0 (`naleak_always_open@1` at 9 × the Na leak permeability) is
  switched on at 1800 s and off at 1800.3 s.

**The changes from F1, declared:**
- the horizon is 3600 s instead of 1800 s. The builder puts the cue at half the horizon, so it
  stays at the middle, D164's intervention during the slow phase;
- `execution.projective` is removed, as for F1's fine reference;
- the observation times are those of §5.2;
- each arm has its own dt and `max_steps` (ceil(3600 / dt) + 8, as the builder computes it).

**Why this case.**
- It exists: F1 and its fine reference ran in qual-01.
- It has two cells.
- It is still moving after an hour (slow modes near 5500 s and 11100 s, §4's benchmarks).
- It has an intervention at its middle, so every heading binds.
- **Its limit, declared:** the cells are independent, with no junction, so N2's junction terms are
  not exercised on the harness. They are on the sheets in M1, M4 and M5 (question Q5).

### 5.2 The runs

- **Observation times** (seconds, all on the 1 ms grid):
  - every 10 s on [0, 3600];
  - every 1 ms on [1799.990, 1802.000];
  - every 10 ms on (1802, 1830];
  - every 1 s on (1830, 1900].
- **The arms:**
  - R1 at dt 1 ms. It is the run of record, and its cost is M3's;
  - R2 at 0.5 ms;
  - R3 at 0.25 ms, run if R1's measured cost puts R3 under 6 CPU-hours. Otherwise it is reported
    as not run, with the reason.
- **Execution.** `cells.execution.windows.run_windowed` with `window_steps` 2048 and `row_checks`
  "device": the engine's compiled checks of every accepted row, with the host deciding any window
  near a bound. The full state at every observation row is taken through the runner's sink.
- **The reference** z_ref is R3 if it runs, otherwise R2.

### 5.3 Budgets: reference adequacy

Each budget is cumulative from t = 0 and holds at every observation row. It is judged for R1
against z_ref, and for R2 against R3, with the caps reported beside.
- **Trajectory.**
  - |ΔVm| ≤ 2 µV on every patch;
  - |Δc| / c ≤ 2 × 10⁻⁵ for every species in every cell;
  - |Δg| ≤ 10⁻⁵ for every gate.

  These are a tenth of the caps, and a tenth of projective's per-jump gate tolerance of 10⁻⁴.
- **Intervention response.**
  - on the rows in (1800, 3600] s, the same budgets, reported apart;
  - cell_0's peak |Vm − Vm(1800 s)| after the cue, within relative 10⁻³.
- **Threshold timing.**
  - Cell_0's crossings of −50 mV after 1800 s, in either direction: the first, then the next if
    it returns. Each is located by linear interpolation between 1 ms rows, within
    |Δt| ≤ 0.5 ms.
  - The recovery times t_rec(δ): the first row after 1800.3 s from which |Vm − Vm(1800 s)| ≤ δ
    holds through 1830 s, for δ = 1 mV and 0.1 mV. They are reported to the row.
  - No crossing, or no recovery, is a result.
- **Histories.** Every accumulator of the state, at every observation row: membrane and channel
  transfers, pump cycles, reservoir supply, electrode charge, and every dissipated-energy and
  work field. Each holds |Δ| ≤ 2 × 10⁻⁵ × max(|ref|, floor), with these floors:
  - 10⁻¹⁰ fmol for amounts and cycles (the material tolerance);
  - 2 × 10⁻⁸ pJ for energies (`ENERGY_ATOL_PJ`);
  - 3 × 10⁻²⁵ C for charges (`GLOBAL_CHARGE_ATOL_C`).
- **Conservation, judged in every arm.** Every accepted row passes the engine's checks, and any
  refusal ends the arm as its result.
- **The observed order,** reported. p = log2(|z1 − z2| / |z2 − z3|) per class, at the row of
  largest |z1 − z2| and at 3600 s.
  - Inside [1.5, 2.5], around ARS(2,2,2)'s second order, R2's own error is estimated as
    |z2 − z3| / (2^p − 1) and reported.
  - Outside that window, no estimate is made.
- **The consequence, declared.**
  - If R1 meets every adequacy budget against z_ref, R1 is the harness's reference at 1 ms for
    stage 1.
  - Otherwise R2 is, with its own adequacy against R3 reported.
  - If neither meets them, the reference is the finest run, its error unestimated, and that is
    reported.

### 5.4 M3: the cost

- **c_e2e:** R1's total run seconds per step, with preflight and compilation reported apart.
  Also its CPU-hours per simulated hour, and the elapsed time to the trajectory.
- **c_window:** one compiled window of 2048 steps of H2 at 1 ms, timed after a warm-up. It is
  the median of 7 repeats. A measurement is valid if IQR / median ≤ 0.10; otherwise it is
  repeated once and both are reported.
- **c_call:** one jitted checked step (`model.checked_step`), the median of 30 calls after a
  warm-up. That is the method of PUMP_COMPOSITE_V2_DESIGN §3's cost table, whose 1.72 ms on the
  seven-cell sheet is this form's benchmark.
- **The operators' share in W0.**
  - c_window and c_call of W0, with its operators as declared and no event inside the timed
    windows, against the same definition with its operator list emptied (the inner sheet with
    R, as an empty composition);
  - share = 1 − c_empty / c_with, the two programs timed interleaved.
  - **Benchmarks:** 3% (D150's note §4.4); 13–40% (PUMP_COMPOSITE_V2_DESIGN §3); about 1.5 ms of
    6–7 ms (replacement@2, its B.13); and N1's bound of 1.03–1.4× (§1.3).
- **Where.** Every timing runs on one timed-lane CPU under its lock, single-threaded (D190).
- **Readings:**
  - N1's gain bound from the measured share, 1 / (1 − share);
  - the harness's fine hour against §1.1's 1.7 CPU-h per simulated hour of the seven-cell sheet.
- **Counting records.** W0's crossing record counts steps. Wherever it is compared across dt, it
  is compared as count × dt, never bitwise.

## 6. M4: settling after interventions

**World:** W0 at dt 1 ms, with a 180 s horizon, the intervention at t0 = 60 s, and the default
booking.

**The arms,** one intervention each, all else as W0:
- A0, the control: no intervention;
- A1, a channel step: `kir_0`'s availability from 1.0 to 0.9 at t0 (cell_0 is an H cell);
- A2, a dose step: R's production in cell_0 from P0 to 2 P0 at t0;
- A3, a regulatory write: (s, cell_3) set to 0.9 at t0.

**Readouts,** at every accepted row in [t0 − 1 s, t0 + 120 s]: `models/surface_pump_projective.
settling` on the composite model under that row's control. It gives the largest |dVm/dt| over
the active patches, and the largest gate distance |g∞(V) − g| over the junction gates and gated
channel gates. If the composite does not expose readouts that `settling` can read, that is an
engine gap. It is reported, not re-derived, and M4 stops.

**Thresholds,** paired (θ_V in V/s, θ_g as a gate fraction): (10⁻², 10⁻²); (10⁻³, 10⁻³), which
are projective's safety values; (10⁻⁴, 10⁻⁴); and (10⁻⁵, 10⁻⁵).

**The settling time t_s(θ):**
- the first accepted row t ≥ t0 from which both readouts are ≤ θ at every row through t + 10 s;
- "not settled by t0 + 110 s" is a result;
- if A0 exceeds θ at any row in [t0, t0 + 120 s], θ is below the world's background there, and
  t_s at that θ is reported as not attributable.

**The budget rule, declared.** The threshold that holds a handed-back transient within budget is
the largest θ_V with θ_V τ_f ≤ 2 µV, a tenth of the voltage cap. τ_f = 1 / min |λ_fast| comes
from S7b's M2 spectrum. M4 reports t_s at that θ as the fine window's length for that
intervention.

**Also reported:**
- the response: each arm's peak |ΔVm| from A0 at matched rows;
- conservation: every accepted row passes the engine's checks.

## 7. M5: where the energy check binds

**World:** W0 with a 60 s horizon, the dose step at 20 s and the write at 40 s, both exact on
every dt's grid. Observations come every 1 s.

**The arms:** the junction booking, `explicit_tableau` (the default) or
`trapezoid_nonnegative@1`, against dt in {1, 2, 5, 10} ms. That is eight arms.

**The measured quantity:** ρ_k = |R_k| / B_k at every accepted row.
- R_k is `balances(row)["energy"]`.
- B_k is the check's own energy bound at that row: ENERGY_ATOL_PJ + rtol F_k plus the step
  rounding allowance (`surface_pump.ledger_limits`), with rtol 2 × 10⁻³ under ARS(2,2,2).
- Both come from the engine's own functions.

**Refusals.**
- An arm refused at definition time (by the explicit bound, the junction-gate bound or an
  operator's condition) or at run time (by any check) is reported with its check, its message
  and its time. It ends there, and no check is bypassed.
- By the formula of §3, the 10 ms arms are refused at definition time, by the junction-gate
  bound at the latest (dt × 24.13 s⁻¹ > 0.125). Whichever check refuses first is their
  registered result.

**Readings,** per booking:
- ρ_max(dt) over the unrefused arms;
- the order p = log(ρ_max,i / ρ_max,j) / log(dt_i / dt_j), from the two largest unrefused dt;
- the binding step dt*: the smallest dt refused by the energy check. If none is, it is
  dt_i (1 / ρ_max,i)^(1/p) from the largest unrefused dt_i, labelled as an extrapolation;
- the trapezoid's effect, ρ_max(trapezoid) / ρ_max(default) at each dt.

**Benchmarks:** FR-18's second-order error, and its refusals at dt × rate 0.08–0.31, set against
M1's rate for S7b.

**Reading for the choice, stated before.**
- If dt* < dt_N2 (M1, S7b), the energy check holds N2's stability gain below dt_N2 under today's
  bookings (§4.3).
- If dt* ≥ dt_N2, it does not.

**By-products,** reported and not judged:
- each arm's observation rows against the same booking's 1 ms arm, with the caps;
- counting records compared as count × dt;
- the other ledgers at every row, by the engine's checks.

**Overlap with the FR-18 probe** (`core-pass-at3-20261118/fr18-probe/`). Its criterion was read
before this file; its outputs were not.
- The probe replays the replication's worlds, G1's and the judged worlds, each at its own step.
- It runs no dt sweep of a seven-cell composed sheet, and no booking switched on and off.
- M5 uses the probe's results only as a cross-check of its own 1 ms arms, reading G1's and the
  judged worlds' ratios after this registration.
- Nothing of M5 runs before the lead's answer to Q4.

## 8. Planted controls

Each is a tier-1 test in `tests/unit/test_long_duration_*.py`, one plant per claim (D187).

- **M1:**
  - a term perturbed by the factor (1 + 2⁻⁴⁰) must fail C1.1's bitwise reproduction;
  - a step of 1.001 dt_def must be refused.
- **M2:** the split on synthetic reduced Jacobians with known spectra must classify a separated
  case and a non-separated one.
- **The harness:**
  - the budget judge on synthetic rows must fail with one entry at 1.01 × its budget;
  - the crossing locator must find a synthetic trace's known crossing within 10⁻⁹ s;
  - a planted shift of 1 ms must fail the timing budget.
- **M4:**
  - the settling time on a synthetic trace with a known settling row must be found;
  - a re-crossing inside the hold must move t_s.
- **M5:** a synthetic row with |R| = 1.01 B must give ρ > 1.

## 9. Questions for the lead

Each comes with its options and my recommendation. None blocks M1.

- **Q1. "Reference outputs."** §5.2 asks for an independent SciPy Radau/BDF reference by an agent
  that has read neither the engine nor the mode. I have read the engine, so that reference is
  not mine to write.
  - Options: (a) commission a references agent for H2 now; (b) commission it with stage 1's
    protocol; (c) none.
  - Recommendation: (b). Stage 0's reference outputs are the fine engine's at dt, dt/2 and dt/4
    (§5), since a mode is judged against the fine engine (§5.2). @3's own equations were
    qualified separately.
- **Q2. N2's classification of Z and N** (§3).
  - Options: Z removed or stays; N stays or removed.
  - Recommendation: Z removed and N stays, as the primary reading. Both readings are reported
    either way, so the answer only selects the headline.
- **Q3. W0 against §5.1's acceptance world** (§1.1). W0 has junction targets and a state that
  reads Na; §5.1 asks for a gate-free channel target and a state that reads R.
  - Options: (a) W0 as registered; (b) a §5.1-faithful sheet, which adds a gate-free K-leak
    population to the sheet (a new world, whose permeability is a physical choice).
  - Recommendation: (a) for stage 0, which measures numerics. Junction worlds are where FR-18's
    check binds. §5.1's world comes with FR-7's U2 loop at qualification.
- **Q4. M5 and the FR-18 probe** (§7).
  - Options: (a) run M5's eight short arms (about an hour of CPU on the light CPUs), with the
    probe's results as a cross-check only; (b) take the probe's results alone, and leave the dt
    sweep and the booking unmeasured.
  - Recommendation: (a). The probe runs no dt sweep and no booking on or off.
- **Q5. The harness has no junction** (§5.1).
  - Options: (a) as registered; (b) add a second harness world, two heredity cells joined by
    E07's junction (`stationary/worlds.e07_sheet_definition` with two cells). That world is not
    an existing case.
  - Recommendation: (a). The sheets carry the junction terms in M1, M4 and M5.

## 10. Amendments

### Amendment 1, 20:40 UTC on 18 November 2026: the lead's rulings, before any run

The lead answered §9's questions, all as recommended. No criterion, budget or world changes.
- **Q1: (b).** The independent Radau/BDF reference comes with stage 1's protocol. Stage 0's
  references are the fine engine's own runs at dt, dt/2 and dt/4. **Stage 0 makes no
  qualification claim,** and every result says so.
- **Q2.** The headline takes Z as removed by N2 and N as staying. Both readings are reported.
- **Q3: (a).** W0 is used as registered. §5.1's gate-free-target world comes with FR-7's loop at
  qualification.
- **Q4: (a).** M5's eight arms run on the light CPUs at nice 10, through `run_detached.sh`, with
  the FR-18 probe as a cross-check only.
- **Q5: (a).** H2 is kept as registered.
- **The lead also asks** that M1 confirm the junction-gate cap of §3's readings with the term's
  numbers.

### Amendment 2, 21:04 UTC on 18 November 2026: M4's settling readouts on the composite, before M4 runs

- **The gap.** Writing M4's driver showed that `models/surface_pump_projective.settling`, which
  serves @1–@3, cannot read a composite's channel targets. The composite nests the inner
  values under `ionic`, so on a composite `settling` silently omits the channel gates'
  distances and reads only the junction gates. FR-8's fine windows (the note's §4.2) need a
  composite settling readout. This is reported to the lead as an engine gap.
- **What M4 does instead of stopping (§6).** It evaluates `settling` on the composite's inner
  model, at the composite's own effective control and view (`model.inner`, `model.inner_state`,
  `model.control_view`, `model.view`). Those are the same inner readouts that the composite's
  own `readouts` computes, so no physics is re-derived. W0 declares no membrane-process
  operator, so the composite adds no process term to them.
- **The direct composite call** is recorded beside it, to show the gap.
- Nothing else changes.

### Amendment 3, 22:40 UTC on 18 November 2026: two faults in the harness judge, after its first read

An external review, verified by an independent agent at `7d9d9723`, found two faults in
`harness_judge.py`. Both hold.

**What had been run and seen when this was written:**
- R1 (finished 21:09 UTC), R2 (21:25) and R3 (22:37) all ran from snapshot `24e516c7`. Their run
  records were read as they finished, and R1's kept rows were inspected at 21:28 (cell_0's
  voltage around the cue).
- `cells-fr8s0-r3` was stopped at 22:37:40, before its in-chain judge wrote anything. Its
  `judge.log` is empty, and it left no `judge.json`.
- At 22:38 the judge from snapshot `7d9d9723` ran on R1, R2 and R3, in that order and from
  distinct directories. Its whole output was read, **including the orders**: p was 1.30–1.48 per
  class, outside the registered window, so no estimate of either kind was formed. The labelled
  extra of per-span errors was read at 22:39.
- This amendment therefore follows that read. It corrects the judge; it changes no criterion,
  budget or window.

**Fault 1: the judge accepted any list of arms.** Given [R1, R1], it scores zero error and
selects R1 as the reference. `run()` takes the last directory as the reference and labels the
selection with a literal, and `compare()` never checks an arm's identity or step.
- **The correction.** The judge refuses to score unless:
  - arm i is named R1, R2 and R3 in turn, each with its step from `arms_dt_s`;
  - the directories are distinct;
  - the steps strictly decrease;
  - the arms share one snapshot revision and one registration.
- The reference's label comes from its own record.
- A planted control refuses [R1, R1] and [R2, R1].

**Fault 2: §5.3's error estimate was R3's, not R2's.** With z_h = z* + C h^p:
- |z2 − z3| / (2^p − 1) is R3's error;
- R2's error is |z2 − z3| / (1 − 2^−p), which is 2^p times larger.
- **The correction.** Inside the window [1.5, 2.5], the judge reports both, as
  `r2_error_estimate` and `r3_error_estimate`. A planted control checks them on the 16:4:1
  sequence (p = 2). p stays measured per class, as registered.

**The judge of record** is now the corrected judge, re-run on the arms' saved rows; no arm is
re-run. `judge-7d9d9723.json` is kept as superseded evidence and is not reported from. The
adequacy verdicts do not depend on the faults with the arms in their registered order, and the
estimates were not formed. That the re-run confirms both is a claim the re-run tests.
