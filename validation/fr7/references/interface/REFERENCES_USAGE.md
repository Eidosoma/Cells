# Using FR-7's references: R-chain and R-clear (interface only)

**Registered 19 November 2026, before any engine output for FR-7's F3.** The registering commit is
the head of branch `fr7-references`, which the lead tags. The engine builds its worlds from
`inputs.json`, never from the reference values. R-loop, the closed loop's reference, comes later,
after D231's engine probe.

- **R-chain** is the linear chain from template to conductance, with one cell's voltage.
- **R-clear** holds D217's five clearance clauses as registered definitions.

Everything here is synthetic and labelled so (D217).

## Independence

- **Read:**
  - [ABUNDANCE_TO_FUNCTION_DESIGN.md](../../../../docs/ABUNDANCE_TO_FUNCTION_DESIGN.md);
  - D217, D218 and D231;
  - the coupling note's §1.3, §1.4, §9 (the scale of @3's errors at 1 ms) and Appendix A;
  - R-cell's code and usage note (`validation/coupling/`);
  - the core-seams references' layout.
- **Not read:** `src/`, the FR-7 lane's files (`validation/fr7/` outside `references/`, and its
  workspace), any engine test, and any diff of `src/`. No FR-7 engine output existed at
  registration.
- **Imports:** numpy and scipy; R-full's `ghk_flux`, as R-cell does; and
  `validation.coupling.piecewise_ode`. The fast test also runs R-cell itself. Nothing imports
  `cells`, which the fast test checks in a fresh process.

## Files

| Path | What it is |
| --- | --- |
| `interface/inputs.json` | The registered inputs: constants, the step, the clearance criterion, the band rules, the power margin, the cell, six worlds and R-clear's cases. Written by `worlds.py` |
| `interface/rows.json` | Per world: the saved rows, and for every quantity its class, per-row status, value, error bound and band. Also each world's clearance, and checks |
| `interface/plants.json` | Per world and plant: the plant's values and margins on every compared quantity; how each was computed; the calibration; the held factor's two models compared |
| `interface/zero_power.json` | Per world: inapplicable plants, plants not evaluated on a quantity, upstream rows, unaffected quantities, and every compared row where a plant falls under the power margin. Also R-clear's cases without power |
| `interface/clearance.json` | The epsilon computation, the trace level, the operating range, the voltage equivalent, every world's clearance, and R-clear's synthetic cases with their plants |
| `../chain.py` | R-chain: the closed forms, the quadrature, the ODE, the cell and the stepped emulations |
| `../clearance.py` | R-clear: the drive, c*, the inclusion rule, `t_clear`, epsilon and the synthetic trajectories |
| `../worlds.py` | Writes `inputs.json` (`--check` compares) |
| `../design.py` | Writes the four design files in about 2.5 minutes of one CPU (`--check` regenerates and compares) |

**Tests:**
- `tests/unit/test_fr7_references.py`, about 5 s. It checks that the files parse and that the
  inputs equal their generator. It recomputes the bands, the margins, the zero-power list and V's
  rule from the stored values. It checks the power, and regenerates a deterministic subset: the
  template's closed forms in every world, W1's chain, R-clear on every case, and the cell against
  R-cell at a held N. It also checks independence.
- `tests/unit/test_fr7_references_regeneration.py` runs the whole regeneration, about 3 minutes
  under pytest, so it falls in tier 3 by measurement.

## The model

Amounts are in fmol and volumes in pL, so n/V is in mM. Units are counts.

- **The template T**, a neutral cytosolic species under D150's turnover:
  - dn_T/dt = P_T(t) − k_T n_T, with P_T piecewise constant from 0;
  - a dose is n_T(0) > 0, and a production pulse is a segment with P_T > 0;
  - closed form per segment: n_T = n_j e^(−k_T τ) + (P_T/k_T)(1 − e^(−k_T τ)).
- **The factor:** F_T = b + (1 − b) cⁿ/(Kⁿ + cⁿ), with c = n_T/V. It sits on the unit
  producer's rate k_a.
- **The precursor:** dn_P/dt = S_P − k_P n_P − k_a F_T n_P. S_P and k_P are zero in a finite
  pool.
- **The units:**
  - dM₁/dt = c_u k_a F_T n_P − κ M₁;
  - dM_j/dt = κ (M_{j−1} − M_j) for j = 2..m;
  - dN/dt = κ M_m − k_r N;
  - with m = 0, units enter N directly;
  - c_u = N_A 10⁻¹⁵/ν units per fmol;
  - removal acts on all of N, the declared N₀ included. Maturing units are not removed.
- **The account:**
  - W, the precursor consumed into units (fmol);
  - R, the units removed;
  - C_P, the precursor cleared (fmol);
  - the conserved total T = n_P + (Σ M_j + N + R)/c_u + C_P − S_P t;
  - the template's produced and cleared amounts close its own balance.
- **The conductance:** the population's permeability–area product P N/ρ_ref (m³/s). This is the
  view's P a A, with a = N/(A ρ_ref). In `inputs.json`, N = 10⁴ is a = 1 on the 400 µm² patch.
- **The cell** is R-cell's pump-free form:
  - one 2 pL cell, with one 400 µm², 4 pF patch facing a bath held at 0 V;
  - the bath holds Na 145, K 5 and Cl 150 mM; the cytosol starts at 12, 140 and 30 mM;
  - a Na leak of 10⁻¹⁰ m/s is the second permeant route, and Cl is impermeant;
  - the gate-free, K-only population has P = 2 × 10⁻⁹ m/s;
  - constant-field fluxes, 310 K, exact SI constants.
  - The start is the declared initial V, from which the charge is C V₀ and the background follows.
    Every world gives both.

## The worlds

| World | Template | m (κ) | t½ of units | Precursor | Start | Horizon, rows |
| --- | --- | --- | --- | --- | --- | --- |
| `W1_dose_m0_t30` | dose 0.2 fmol (0.1 mM = 10 K) | 0 | 30 s | finite, 10⁻⁴ fmol | N₀ = 10⁴ | 450 s, 49 |
| `W2_dose_m3_t60` | dose | 3 (0.1/s) | 60 s | finite | N₀ = 10⁴ | 600 s, 64 |
| `W3_pulse_m3_t120` | 0.01 fmol/s on [5, 25) s | 3 | 120 s | finite | N₀ = 10⁴ | 900 s, 94 |
| `W4_pulse_m0_t60` | pulse | 0 | 60 s | finite | N₀ = 10⁴ | 600 s, 64 |
| `W5_supplied_dose_m3_t60` | dose | 3 | 60 s | supplied (S_P = 1.0842 × 10⁻⁶ fmol/s) and cleared (t½ 300 s) | the basal steady state: n_P 4 × 10⁻⁴ fmol, M_j 240.886, N 2085.15 | 600 s, 64 |
| `W6_no_template_m3_t60` | none: the control, F_T = b | 3 | 60 s | finite | N₀ = 10⁴ | 600 s, 64 |

Shared by every world:
- the template's half-life is 20 s;
- K = 0.01 mM, n = 2 and b = 0.02;
- ν = 4, so c_u = 1.50553519 × 10⁸ units per fmol;
- k_a = 0.02/s.

**Rows:** 0, 1, 2 and 5 s, then every 10 s to the horizon.

**Horizons:** each world runs at least five unit half-lives beyond its registered clearance row:
6.3, 5.7, 5.2, 5.3, 5.7 and 10 half-lives.

## Reading `rows.json`

The path is `worlds → name → quantities → q`. Each `q` holds:
- `cls`, either `compared` or `information`;
- `unit`;
- `status`, per row;
- `value`, the reference;
- `bound`, the reference's own error bound at that row;
- `band`, for compared classes.

**A compared row passes when |engine − value| ≤ band.**

**Row 0 is information everywhere.** It is the declared start.

**Compared quantities:**
- `n_T_fmol`, `D` (the drive) and `F_T`;
- `n_P_fmol`, `M1_units`…`M3_units`, `N_units`, `PA_m3_s` (the conductance), `W_fmol`,
  `R_units` and `total_fmol`;
- `C_P_fmol`, where k_P > 0 (W5 only);
- `V_V`, on the rows its status marks (below);
- `Na_fmol` and `K_fmol`.

**Information:**
- `c_mM`, `U_s` (the exposure ∫ cⁿ/(Kⁿ + cⁿ) dt) and `Cl_fmol` (constant: impermeant);
- `I_pop_A`, the population's outward current;
- `template_produced_fmol`, `template_cleared_fmol` and `supplied_fmol`;
- `dV_dlnN_V`, the quasi-steady potential's sensitivity to ln N at the row's composition;
- `C_P_fmol` in a finite pool (identically 0);
- `n_T_fmol` and `D` in W6 (identically 0).

### Each row's own error bound

| Quantity | Bound |
| --- | --- |
| Template, factor, drive, exposure | Closed forms: 16 ε \|x\| |
| n_P, M_j, N, W, R, C_P, total | Gauss–Legendre panels of 2.5 s on the closed-form integrands: n_P in closed form in a finite pool (with this package's own closed form for a production segment at n = 2), and the units as the convolution of the consumption flux with the chain's closed-form impulse responses. The bound is the largest difference from three independent computations (panels of 5 s, DOP853 on the chain at rtol 10⁻¹³, the Radau cell's chain at rtol 10⁻¹²), and at least 16 ε \|x\| |
| V and the amounts | The Radau cell at rtol 10⁻¹² (R-cell's layout). The bound is its difference from rtol 10⁻¹⁰, plus 16 ε \|x\| |

Every bound is under 4 × 10⁻⁶ of its band. Each world's `checks` give:
- the closed-form exposure against quadrature (≤ 1.8 × 10⁻¹³ s);
- the material total's spread (≤ 1.3 × 10⁻¹⁵ relative);
- the impermeant follower's spread (≤ 3.3 × 10⁻¹² fmol).

## Bands

**The rule:** band = bound + max(rel × max(|x|, floor × scale), abs). The scale is the largest
|x| over the world's rows. The bands are registered at the declared step dt = 1 ms.

| Class | Quantities | rel | floor | abs |
| --- | --- | --- | --- | --- |
| template | n_T | 10⁻⁹ | 10⁻⁹ | – |
| drive | D | 4 × 10⁻⁹ | 10⁻¹² | – |
| factor | F_T | 10⁻⁹ | 1 | – |
| chain | n_P, N, PA, W, R, C_P | 3 × 10⁻⁷ | 10⁻² | – |
| maturation | M₁…M₃ | 10⁻⁶ | 0.1 | – |
| material total | total | 10⁻⁹ | 1 | – |
| voltage | V | – | – | 1 µV |
| amounts | Na, K | 10⁻⁶ | 1 | – |

**Why these allowances.** A correct engine is second order: D150's turnover is exact, and the routed
factor is evaluated in the producer's half-steps.
- **Three correct treatments, emulated.** Each was emulated exactly at dt = 1 ms in
  `plants.json → calibration_max_band_fraction`:
  - `held_mid`, the factor held at each step's midpoint;
  - `trapezoid`, held at the step's start for the first half-step and at its end for the second;
  - `strang`, the producer's half-steps around an exact maturation-and-removal step.
- **All three reach at most 1.8 × 10⁻² of any band.** The largest is W5's material total, which
  is the stepped emulator's own rounding (1.8 × 10⁻¹¹ relative). On the units, the split chain
  reaches 6 × 10⁻³ (M₂).
- **The plant `factor_held_from_step_start`, a first-order lag, exceeds the bands.** Its margins
  reach 39 on N, 32 on n_P, and about 500 on W at a pulse's onset.
- **The maturation class is wider.** M₂ and M₃ rise as t^(j−1) from an onset, where a split
  scheme's relative error goes as (dt/t)². With the chain's rule, the split chain reached 0.44 of
  the band at t = 1 s.

**The template, factor and drive bands** allow the rounding that an exact turnover accumulates over
up to 9 × 10⁵ steps.

**V's 1 µV:**
- it is a twentieth of rung 1's 20 µV parity cap (D231), and half of stage 0's 2 µV;
- the coupling's A5 world erred by 2.9 × 10⁻⁸ V at 1 ms (coupling note §9.2).

**At a finer dt** the same bands hold, since a second-order error falls as dt². The held factor's
deviation falls as dt, so its margins halve with each halving of dt.

## Plants

**Margin and power.** A plant's margin at a row is |plant − value|/band, and it has power there
when the margin is at least 3 (`inputs.json → power`). Every margin and value is stored.

| Plant | What it does here | How it is computed |
| --- | --- | --- |
| `nu_off_by_one` | c_u from ν + 1 = 5 | The Radau cell with the chain |
| `cu_without_1e-15` | c_u = N_A/ν (per mol, read as per fmol) | The chain alone, by DOP853. Its 10¹⁵-fold units short the cell to E_K, so its V and amount rows are not integrated (`not_evaluated`); its chain rows carry margins of about 10²¹ |
| `maturation_stage_skipped` | m − 1 stages, the same κ (W5's declared M₂ and M₃ merged). A missing stage reads 0 | The Radau cell |
| `removal_on_increment_only` | k_r (N − N₀): the declared units are never removed | The Radau cell |
| `route_on_precursor_clearance` | The factor multiplies the precursor's clearance k_P, and consumption runs at its scheduled maximum k_a | The Radau cell |
| `factor_held_from_step_start` | F_T(t_k) held over each 1 ms step | Chain rows: exact steps. V and amounts: the cell with F read at t − dt/2, which equals the held factor to O(dt²) at step ends. The two models agree on the chain's deviations to 4 × 10⁻⁵ of the deviation |
| `releasing_compartment_left_out` | c* without a releasing compartment | No R-chain world has one (none is admitted in a U2 world today), so it is inapplicable here and shown on R-clear's cases |
| `factor_from_amount` (extra, not in the brief) | The factor reads n_T in fmol as if it were mM: amount sensing, which the coupling note rejects | The Radau cell |

**Compared rows with power** (of 48–93 compared rows; "unaffected" means the plant does not act on
that quantity):

| World (compared rows) | Plant | n_P | N | M₃ | W | R | total | V | K | Largest margin on N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W1 (48) | ν + 1 | unaffected | 48 | · | unaffected | 48 | 48 | 48/48 | 44 | 5.9e+05 |
| W1 (48) | c_u per mol | unaffected | 48 | · | unaffected | 48 | 48 | not run | not run | 3.0e+21 |
| W1 (48) | removal on increment | unaffected | 48 | · | unaffected | 48 | unaffected | 48/48 | 45 | 3.2e+08 |
| W1 (48) | route on clearance | 48 | 48 | · | 48 | 48 | unaffected | 48/48 | 42 | 4.2e+06 |
| W1 (48) | factor from amount | 48 | 48 | · | 48 | 48 | unaffected | 48/48 | 41 | 6.2e+05 |
| W1 (48) | factor held | 42 | 39 | · | 42 | 37 | unaffected | 0/48 | unaffected | 1.9e+01 |
| W2 (63) | ν + 1 | unaffected | 62 | 63 | unaffected | 61 | 63 | 59/59 | 58 | 6.2e+05 |
| W2 (63) | c_u per mol | unaffected | 63 | 63 | unaffected | 63 | 63 | not run | not run | 3.1e+21 |
| W2 (63) | stage skipped | unaffected | 63 | 63 | unaffected | 63 | unaffected | 59/59 | 59 | 4.6e+05 |
| W2 (63) | removal on increment | unaffected | 63 | unaffected | unaffected | 63 | unaffected | 59/59 | 60 | 2.2e+08 |
| W2 (63) | route on clearance | 63 | 61 | 63 | 63 | 61 | unaffected | 59/59 | 55 | 2.0e+06 |
| W2 (63) | factor from amount | 63 | 61 | 63 | 63 | 61 | unaffected | 59/59 | 54 | 7.5e+05 |
| W2 (63) | factor held | 57 | 47 | 9 | 57 | 48 | unaffected | 0/59 | unaffected | 2.3e+01 |
| W3 (93) | ν + 1 | unaffected | 91 | 93 | unaffected | 90 | 93 | 89/89 | 87 | 5.6e+05 |
| W3 (93) | c_u per mol | unaffected | 93 | 93 | unaffected | 93 | 93 | not run | not run | 2.8e+21 |
| W3 (93) | stage skipped | unaffected | 93 | 93 | unaffected | 92 | unaffected | 89/89 | 86 | 4.5e+05 |
| W3 (93) | removal on increment | unaffected | 93 | unaffected | unaffected | 93 | unaffected | 89/89 | 90 | 9.9e+07 |
| W3 (93) | route on clearance | 93 | 93 | 93 | 93 | 92 | unaffected | 89/89 | 88 | 1.4e+06 |
| W3 (93) | factor from amount | 90 | 90 | 90 | 90 | 90 | unaffected | 89/89 | 86 | 5.0e+05 |
| W3 (93) | factor held | 11 | 82 | 16 | 9 | 21 | unaffected | 0/89 | unaffected | 2.2e+01 |
| W4 (63) | ν + 1 | unaffected | 63 | · | unaffected | 63 | 63 | 60/60 | 59 | 6.2e+05 |
| W4 (63) | c_u per mol | unaffected | 63 | · | unaffected | 63 | 63 | not run | not run | 3.1e+21 |
| W4 (63) | removal on increment | unaffected | 63 | · | unaffected | 63 | unaffected | 60/60 | 60 | 2.6e+08 |
| W4 (63) | route on clearance | 63 | 63 | · | 63 | 63 | unaffected | 60/60 | 61 | 2.2e+06 |
| W4 (63) | factor from amount | 60 | 60 | · | 60 | 60 | unaffected | 60/60 | 59 | 8.1e+05 |
| W4 (63) | factor held | 11 | 56 | · | 9 | 16 | unaffected | 0/60 | unaffected | 3.9e+01 |
| W5 (63) | ν + 1 | unaffected | 63 | 63 | unaffected | 62 | 63 | 60/60 | 59 | 6.7e+05 |
| W5 (63) | c_u per mol | unaffected | 63 | 63 | unaffected | 63 | 63 | not run | not run | 3.3e+21 |
| W5 (63) | stage skipped | unaffected | 63 | 63 | unaffected | 63 | unaffected | 60/60 | 60 | 2.5e+06 |
| W5 (63) | removal on increment | unaffected | 63 | unaffected | unaffected | 63 | unaffected | 60/60 | 60 | 4.1e+06 |
| W5 (63) | route on clearance | 63 | 62 | 63 | 63 | 61 | unaffected | 60/60 | 57 | 2.5e+07 |
| W5 (63) | factor from amount | 63 | 62 | 63 | 63 | 61 | unaffected | 60/60 | 56 | 6.8e+05 |
| W5 (63) | factor held | 56 | 38 | 10 | 57 | 53 | unaffected | 0/60 | unaffected | 1.7e+01 |
| W6 (63) | ν + 1 | unaffected | 61 | 63 | unaffected | 60 | 63 | 58/58 | 53 | 6.5e+05 |
| W6 (63) | c_u per mol | unaffected | 63 | 63 | unaffected | 63 | 63 | not run | not run | 3.3e+21 |
| W6 (63) | stage skipped | unaffected | 63 | 63 | unaffected | 62 | unaffected | 58/58 | 54 | 2.6e+04 |
| W6 (63) | removal on increment | unaffected | 63 | unaffected | unaffected | 63 | unaffected | 58/58 | 60 | 7.6e+07 |
| W6 (63) | route on clearance | 63 | 63 | 63 | 63 | 62 | unaffected | 58/58 | 59 | 8.3e+06 |

### The zero-power list (`zero_power.json`)

Per world it gives:
- **`inapplicable`:**
  - the stage skip where m = 0;
  - the two factor plants in W6, which has no template;
  - the compartment plant everywhere.
- **`not_evaluated`:** the c_u plant's V and amount rows.
- **`upstream`:** n_T and D, which no chain plant moves, and F_T, which only `factor_from_amount`
  moves. These rows check D150's turnover and the factor law, both qualified elsewhere, and
  R-clear's input.
- **`unaffected`:** quantities a plant moves by under 0.05 band at every compared row, so it does
  not act on them. Examples:
  - ν and c_u on the precursor's rows;
  - removal on the precursor and the stages;
  - every conserving plant on the material total.
- **`rows_without_power`:** for each plant and quantity it acts on, every compared row it moves by
  under 3 bands, with its margin. These include:
  - the early rows;
  - the held factor's V and amount rows (at most 0.19 band);
  - the held factor's precursor rows after a pulse's clearance. There its lag on the precursor
    cancels, because F returns to b.

### V: compared only where the plants have power

- **A pump-free cell's V depends on N only during the run-down.** Every horizon here lies inside
  that transient:
  - V moves from −65 mV to between +3 and +42 mV as N falls;
  - in W5 it moves from −34 mV down to −77 mV and back to −29 mV, as the template's units come
    and go.
- **The rule.** V is a compared row only where every applicable material plant moves it by at
  least 3 bands. The material plants are ν, the stage skip, removal, the route and amount
  sensing; the c_u plant is not integrated. Other V rows are information.
- **The held factor is left out of the rule.** Its effect on V is sub-µV by design; it is judged
  on the chain's rows and by the order of convergence.
- **Compared V rows:** 48, 59, 89, 60, 60 and 58 of 48, 63, 93, 63, 63 and 63. The rest are the
  first rows.

## R-clear: the clearance clauses

1. **The criterion is declared before any engine output.** These definitions, ε and every world's
   rows are registered here.
2. **The threshold is on the remaining drive:**
   - D = (F_T(c*) − b)/(1 − b) = c*ⁿ/(Kⁿ + c*ⁿ);
   - c* = (cytosolic n_T + Σ over releasing compartments of n_T)/V;
   - `clearance.hill_drive` and `clearance.c_star`.
3. **The fall-back rule** (`clearance.t_clear`):
   - t_clear is the earliest saved row at or after the drive's peak from which D ≤ ε holds at every
     later saved row;
   - the peak is the first row with the largest D;
   - a re-crossing voids an earlier time;
   - if D never exceeds ε, t_clear is the peak row (0 with no template).
4. **Every compartment that can still release template is included.** A compartment counts at row
   t when its declared release rate is positive on some interval starting at or after t
   (`clearance.can_release`).
5. **"Not cleared" (`None`) is the outcome** when no such row exists before the end.

**ε, shown** (`clearance.json → epsilon`, `computation`):
- **With the precursor held at any level,** the units' steady state is N* = c_u k_a F n_P/k_r. A
  constant drive D therefore moves N*, and the conductance, by the relative amount (1 − b) D/b from
  basal.
- **With a supply and a clearance,** N* = c_u S_P k_a F/(k_r (k_P + k_a F)), which moves less.
- **The declared resolution is 10⁻⁴ relative.** So ε ≤ 10⁻⁴ b/(1 − b) = 2.04 × 10⁻⁶, and
  **ε = 2 × 10⁻⁶**:
  - the held-precursor move is 9.8 × 10⁻⁵;
  - W5's move is 8.35 × 10⁻⁵.
- **Information:** at the compared V rows the quasi-steady potential moves by at most 23.8 mV per
  e-fold of N. The resolution is therefore at most 2.4 µV of quasi-steady V (W1, 170 s).

**The trace level and the operating range:**
- D = ε at c = K (ε/(1 − ε))^(1/n) = **1.414 × 10⁻⁵ mM (14.1 nM)**. That is 2.83 × 10⁻⁵ fmol, or
  about 1.7 × 10⁴ molecules, in the 2 pL cell.
- The coupling's declared operating range on the template is **[10⁻⁷, 1] mM**:
  - it includes the trace level and the peaks (≤ 0.1 mM);
  - its low end lies above D150's mean-field floor of 10² molecules per cell (8.3 × 10⁻⁸ mM).
- After clearance the template keeps decaying below the range. F_T is then b to within 10⁻¹⁰.

**The worlds' clearance** (`rows.json → clearance`):

| World | t_clear | D/ε at that row, at the row before | Continuous t_ε |
| --- | --- | --- | --- |
| W1, W2, W5 | 260 s | 0.745, 1.490 | 255.75 s |
| W3, W4 | 280 s | 0.548, 1.097 | 271.33 s |
| W6 | 0 s (no template) | – | – |

An engine's error in D would have to reach 9.7% to move a clearance row. Each world also records:
- the R-clear plants on its own rows;
- `threshold_on_the_factor`, which never clears, since F_T ≥ b > ε.

**R-clear's synthetic cases** (`clearance.json → synthetic_cases`):
- They are exact, by the matrix exponential of the cytosol and its compartments, with rows every
  10 s to 1000 s.
- Each holds the D and c* rows, t_clear and its bracket, and every plant's outcome.
- An asterisk marks power (a different outcome):

| Case | t_clear | compartment left out | sealed counted | first crossing | factor threshold | strict < | end time if not cleared |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RC1_cytosol_dose | 260 | 260 | 260 | 260 | not cleared * | 260 | 260 |
| RC2_releasing_compartment | 680 | 620 * | 680 | 680 | not cleared * | 680 | 680 |
| RC3_recrossing | 630 | 630 | 630 | 250 * | not cleared * | 630 | 630 |
| RC4_not_cleared | not cleared | not cleared | not cleared | not cleared | not cleared | not cleared | 1000 * |
| RC5_compartment_stops_releasing | 460 | 460 | not cleared * | 460 | not cleared * | 460 | 460 |
| RC6_no_template | 0 | 0 | 0 | 0 | not cleared * | 0 | 0 |
| RC7_threshold_equality | 20 | · | · | 20 | not cleared * | 30 * | 20 |

- **RC2:** a compartment releasing at ln 2/50 s⁻¹ (clause 4).
- **RC3:** a second, smaller pulse at 400 s (clause 3).
- **RC4:** a sustained production that keeps D above ε (clause 5).
- **RC5:** a compartment sealed at 300 s, which no longer counts.
- **RC6:** no template.
- **RC7:** a row exactly at ε, which counts as cleared.

## How a comparison reads them

1. **Build each world from `inputs.json`.** Take every input from there: the cell, the population
   (P, relative permeabilities, ρ_ref, N₀ and M₀) and the template (its schedule and k_T). Then:
   - the Hill factor (K, n, b), routed onto the producer's rate;
   - the precursor (n₀, S_P, k_P);
   - the producer (k_a, ν, c_u), the stages (m, κ) and removal k_r on all of N;
   - the start (initial V, amounts, background).
2. **Run at dt = 1 ms** and save at `rows_s`.
3. **Compare every compared row:** |engine − value| ≤ band. Form the material total from the
   engine's rows with the declared c_u. Map the engine's account entries onto W, R and C_P.
4. **The clearance row.** Compute D from the engine's n_T rows by `clearance.hill_drive(n_T/V, K, n)`,
   then `t_clear(rows_s, D, ε)`. The result must equal the registered row.
5. **A refinement study** may use the same bands at dt ≤ 1 ms. The held factor's margins scale as
   dt.

```python
import json
import numpy as np
from validation.fr7.references import clearance

I = "validation/fr7/references/interface/"
inp = json.load(open(I + "inputs.json"))
rows = json.load(open(I + "rows.json"))["worlds"]["W2_dose_m3_t60"]
q = rows["quantities"]["N_units"]
ok = [abs(e - v) <= b for e, v, b, s in
      zip(engine_N, q["value"], q["band"], q["status"]) if s == "compared"]
D = clearance.hill_drive(np.array(engine_nT) / inp["cell"]["volume_pL"], 0.01, 2.0)
t_clear = clearance.t_clear(rows["rows_s"], D, inp["clearance"]["epsilon"])
assert t_clear == rows["clearance"]["t_clear_s"]
```

## Readings of the brief taken here

- **τ_m = 30 s is the mean total maturation delay m/κ,** so κ = 0.1 s⁻¹ at m = 3. κ is declared,
  so the engine uses it whichever reading is meant.
- **"ν off by one" is ν + 1.** ν − 1 moves the units further (4/3 against 4/5).
- **"The route on the precursor's clearance instead of its consumption"** moves the rate route's
  factor onto k_P, and leaves consumption at its scheduled k_a.
- **A skipped stage keeps its declared units.** W5's M₂ and M₃ merge. A missing stage reads 0.
- **F_T at a row is the factor of the row's own template state.** A lag changes only the value the
  producer used.
- **The extra plant `factor_from_amount`** gives the factor's rows power. It is the amount sensing
  the coupling note rejects.
- **ε is rounded down to one significant digit**, so the resolution holds strictly.
- **The power margin is 3**, and "unaffected" means under 0.05 band at every compared row.

## Known limits

- Synthetic throughout: pump-free and feedback-free, with no compartment in R-chain's worlds. R-loop,
  the pump with Na-leak units, waits for D231's probe.
- The references run in float64. Their bounds are at most 4 × 10⁻⁶ of the bands.
- Below about 10² molecules per cell a Hill factor is not meaningful (D150 §1.3). The template
  passes the trace level well above that. It falls under that floor only after clearance, when F_T
  is b to within 10⁻¹⁰.
- The c_u plant's cell is not integrated (above).

## Reproduce

```
PYTHONPATH=. JAX_PLATFORMS=cpu /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.fr7.references.worlds --check
PYTHONPATH=. JAX_PLATFORMS=cpu /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.fr7.references.design --check
```

The design takes about 2.5 minutes on one CPU.
- Within one environment it repeats bit for bit.
- Importing the engine package, as `tests/conftest.py` does, changes the last bits.
- So `--check` compares each row's value, bound and band to 1e-3 of its band (or, for information,
  to 1e-6 of its values' scale), and margins to 1e-3. Statuses, clearance rows and the zero-power
  rows must match exactly.
