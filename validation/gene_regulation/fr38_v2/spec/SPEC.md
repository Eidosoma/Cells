# FR-38's second comparison: the worlds, and what the references compute

Read `README.md`'s rules first. Every value below is an input; no result appears in this folder.

## 0. Units: every declared count

| Declared quantity | Unit |
| --- | --- |
| A pool's machines (`pools[].machines`); a chain's gene copies (`template.copies`); the hold's start (`release.initial_copies`); the fate rows' starts, where this folder gives them in copies | **copies**: molecules in one cell. 1 copy = COPY_FMOL fmol, with COPY_FMOL = 10¹⁵/N_A, the double `1.6605390671738468e-09` |
| A species row's initial amount (`initial_amount_fmol`) | fmol |
| A concentration in this folder's tables | mM. In a 1 pL cell, 1 mM is 1 fmol |
| A volume (`volume_pL`) | pL |
| The release's mean dwell τ (`dwell_s`); every time | s. The release's exit rate is 1/τ |
| The durable fraction p | dimensionless, in [0, 1] |
| Initiation k_I | mM⁻¹ s⁻¹ |
| A degradation's k_f; the D152 passive forward rate | s⁻¹ (the D152 rate at its own c0 of 1 mM) |
| A standard potential `standard_mu_RT` | μ°/RT at the model's standard concentration c° = 1000 mM (1 M). The D152 network's own potentials are at its c0 = 1 mM |
| Hydraulic permeability L_p | m Pa⁻¹ s⁻¹; area m²; pressure Pa |
| A label's initial share | a fraction |

**Constants.**
- N_A = 6.02214076 × 10²³ mol⁻¹ and k_B = 1.380649 × 10⁻²³ J K⁻¹, both exact (SI 2019).
- R = N_A k_B as their double product.
- T = 310.15 K, so RT = R T. Energies are in pJ, with 1 kJ/mol × 1 fmol = 1 pJ.

**Declared reals.**
- Each is a decimal literal, or a stated expression such as 1/9000.
- Both sides use the nearest double. The engine receives exactly that double, so you may carry its
  exact decimal expansion.

**One unit on output.** Every amount is in fmol, every energy in pJ, every time in s and every
volume in pL. Copies never appear in your output.

## 1. The hold worlds: families AF, AN, C and D

### 1.1 Common to all four

**The cell and its bath.**
- One cell, `cell_0`, of 1.0 pL, with the background ions K (+1) and Y (−1) at 140 mM each.
- A held bath, `bath_0`: a reservoir of 1.0 pL, with K and Y at 140 mM.
- One patch, `patch_0`, between them: area 10⁻¹⁰ m², and every permeability 0, so no solute
  crosses. Nothing is charged or moved electrically: every row below is neutral.
- **Arms A and C:** the cell's volume is fixed. **Arm D** adds water (§1.6).

**The neutral rows,** in the cell at t = 0, and at 10⁻¹⁵ mM everywhere else:

| Row | Initial in the cell | μ°/RT at 1 M |
| --- | --- | --- |
| N (the NTP lump) | 2.0 mM | 24.8672029410015 |
| M (the NMP lump) | AF: 0.05 mM. AN, C, D: 4.0 × 10⁻³ mM | 0.0 |
| Pi | 5.0 mM | 0.0 |
| R (the durable fate) | 20 copies | 1200 × μ°_res |
| R_s (the short-lived fate) | 15 copies | 1200 × μ°_res |

- **The residue potential.** μ°_res = 8.599269797012601 in AF (the sheet's numeric test instance).
  In AN, C and D it is −10.368889, a declared synthetic value outside §3.3's range.
- **So the fate rows' potentials** are the decimal literals 10319.123756415122 (AF) and
  −12442.6668 (AN, C and D). Each is 1200 μ°_res in exact decimal. Use these literals' nearest
  doubles, not a floating-point product: 1200 × −10.368889 in doubles is −12442.666799999999.
- **The moieties** (§1.4, restricted to these rows):
  - phosphorus: N 3, M 1, Pi 1, R 1200, R_s 1200;
  - nucleoside: N 1, M 1, R 1200, R_s 1200.

**The gene unit** (`templated_polymerisation@1`, §1–§4 with §9).
- **The pool.** Pool `pol` in `cell_0`, 10⁴ machines (copies).
- **The chain.** Chain `tx`:
  - its template is one gene copy, and its product is R;
  - L = 1200 residues, 8 stages and speed v = 50 nt/s;
  - each stage exit draws N (one per residue) and releases Pi (two per residue), as §2 states;
  - N's saturation constant is 0.02 mM.
- **Initiation.** k_I = 3.0 × 10³ mM⁻¹ s⁻¹, constant. In the blank it is 0.
- **The release** `tx_release` (§9.1–§9.4):
  - τ = 2400 s;
  - the machine is `returned` or `held`, as each run states;
  - fates: durable R, short-lived R_s;
  - one class, marked at release;
  - H(0) = 160 copies. In the blank it is 0.
- **The durable fraction p,** by run:
  - p = 0, constant;
  - p = 1, constant;
  - p_sched: 0.7 on [0, 2700 s), and 0.25 from 2700 s on. This is a schedule (§9.4, source 2),
    piecewise constant, the value in force at the start of each step.
- **The degradations,** each returning L monomers of M (§4.4, §9.2):
  - `deg_R` on R at k_d = 1/9000 s⁻¹ (the double `0.00011111111111111112`);
  - `deg_R_s` on R_s at k_s = 1/1350 s⁻¹ (the double `0.0007407407407407407`).
- **No other route.** There is no recharging, no translation and no regulator.

**The labels** (FR-42's label owner, `neutral_arrival_labels@1`).
- R and R_s each carry five labels: `resyn` (the base), `pool0`, `pre`, `win` and `post`.
- **Initial shares** in the cell: `pool0` 1.0.
- **The species' own label in force** is `resyn` from t = 0 throughout. Re-synthesis enters there.
- **Transcription's own source schedule** (release-marking): `pre` from 0, `win` from 1800 s and
  `post` from 5400 s.
- **So the window is W = [1800, 5400) s.** A release joins the label in force at the start of its
  step.

**The time grid.**
- The horizon is 14,400 s.
- Outputs every 30 s, at t_i = 30 i s, i = 0, …, 480.
- The cohort's sample times are t2 = 5400 s, 9000 s and 12600 s.

**The matched blank.** The same world with H(0) = 0 and k_I = 0: nothing completes and nothing is
released (erratum I, item 5). Every other input is equal, the pools and both losses included. It
is physically the same for either machine option. Publish it once per family, as run `blank`.

### 1.2 The families

| Family | Potentials and M | Runs you compute |
| --- | --- | --- |
| AF | μ°_res 8.599269797012601; M 0.05 mM | p = 0, p = 1 and p_sched, each with `returned` and `held`; the blank |
| AN | μ°_res −10.368889; M 4.0 × 10⁻³ mM | p = 0 and p = 1 with `returned`; p_sched with `returned` and `held`; the blank |
| C | AN's, plus the monomer store (§1.5) | p_sched with `returned`; the blank, with the store |
| D | AN's, in a swelling cell (§1.6) | p_sched with `returned`; the blank, swelling |

A labelled run and its unlabelled twin are one physical solution (the labels change no physics,
FR-42). Compute it once. The twins and the restart are the engine's own checks, not yours.

### 1.3 Run names

Use `"<p> <machine>"`, with p one of `p=0`, `p=1` or `p_sched` and machine one of `returned` or
`held`, and `"blank"` for the blank. For example, `"p_sched held"`.

### 1.4 What is not in these worlds

There are no translation, recharging, regulator, export or replacement routes, and no other label
than the five.

### 1.5 Family C: the monomer store (FR-43 part 2A)

- **The row.** Mx, neutral and impermeant, at 1.0 × 10⁻⁶ mM in the cell at t = 0 (10⁻¹⁵ mM
  elsewhere).
  - Its μ°/RT at 1 M is 0.0.
  - It carries M's moieties: phosphorus 1, nucleoside 1.
- **The network.** `local_species_reactions@1` at its own c0 = 1 mM, with species M and Mx, each at
  μ°/RT = −6.907755278982137 at that c0 (the registry's 0.0 converted, ln(1/1000)). One reaction:
  - `store_M`, M ⇌ Mx, in `cell_0`;
  - law `ideal_detailed_balance_mass_action@1`, forward 1/3000 s⁻¹ (the double
    `0.0003333333333333333`) at c0;
  - multiplier 1 from t = 0.
- **The composition.** The network and the gene unit both write M, as split parts in the
  composite's declared order (FR-43 part 2A). The coupled system is the ODE of LAWS.md. Compute the
  exact coupled solution; the split is the engine's error, not yours.

### 1.6 Family D: the swelling cell (FR-43 part 2B)

- **Water.** `ideal_osmosis_linear_compliance_water@1` on `cell_0` (LAWS.md §4):
  - the reference volume is 1.0 pL, the minimum 0.5 pL and the maximum 3.0 pL;
  - no impermeant amount, bulk modulus 0 Pa and pressure offset 0 Pa.
- **The bath.** `bath_0`, held, at hydrostatic pressure 0 Pa. Its K and Y, and its traces, are at
  0.4 of the amounts in §1.1, so K and Y are 56 mM each.
- **The patch's water.** L_p = 2.8029294930351318e-14 m Pa⁻¹ s⁻¹, with availability 1 from t = 0.
- **Every rate and booking reads the current volume** (LAWS.md §4): the gene unit's, and the
  water's osmotic pressure.

## 2. Arm B: A1 with the release (family B)

- **The world.** A1 as the sheet's §5.1 declares it, at the numeric test instance.
  - Read §5.1's table, "The initial state", "The schedule" and "The horizon". Skip its closed
    forms and its measured bound.
  - The rows are X, N, M, A, ATP, ADP, Pi, R and P, plus R_s at R's trace (c_R).
  - Every machine is free at t = 0.
- **Potentials,** μ°/RT at 1 M: ATP 12.409206388416035, ADP 0.0, Pi 0.0, N 24.8672029410015,
  M 0.0, A 0.0, R and R_s 10319.123756415122, P 2336.405378810971. X carries none: it enters
  only through its turnover and the factor (§4.6).
- **Transcription declares the release** (§9.9's addendum):
  - τ = 1500 s, p = 0.55 constant, H(0) = 0;
  - fates: durable R, short-lived R_s;
  - the machine `returned` or `held`.
- **The fates' losses:**
  - `deg_R` at k_d = 1/8000 s⁻¹ (the double `0.000125`), replacing A1's k_R;
  - `deg_R_s`, with `deg_R`'s form and standard free energy, at k_s = 1/1100 s⁻¹ (the double
    `0.0009090909090909091`).
- **Translation.** Two chains, `tl` templated by R and `tl_s` templated by R_s, each with A1's
  translation inputs. Both share the ribosome pool and make P.
- **Everything else is A1's:**
  - recharging;
  - protein degradation;
  - the regulator X's production until t_off and its clearance;
  - the factor on transcription's initiation (§4.6: Hill activation, with A1's K_X, n_X and b_X).
- **The labels.** As §1.1's, on R and R_s, with transcription's schedule giving `pre` from 0,
  `win` from 2400 s and `post` from 6000 s. So W = [2400, 6000) s.
  - Initial shares: `pool0` 1.0, which here is the trace.
- **The time grid.** Horizon 21,600 s. Outputs every 60 s, at t_i = 60 i s, i = 0, …, 360.
  Sample times 6000, 9600 and 13200 s.
- **Runs:** `"p=0.55 returned"` and `"p=0.55 held"`. There is no blank.

## 3. What to compute

For every run of every family, compute every quantity READOUTS.md lists for it, at every output
time of its grid. This includes the stage complexes and the other quantities READOUTS.md marks as
reported. In particular:

1. **The physical state and books:**
   - every row;
   - the hold;
   - the stage complexes, the engaged machines, the free machines and the residues in transit;
   - the cumulative extents: initiations, stage exits, completions, the releases into each fate
     and each fate's net loss;
   - every heat class;
   - G − G(0) (LAWS.md §5);
   - in C, the store's row and heat; in D, the volume, water's heat and the bath's water work.
2. **The five membership classes** per fate row (LAWS.md §1): `resyn`, `pool0`, `pre`, `win` and
   `post`. Compute them by integrating their laws alongside the physical state. Never take one as
   a difference of others.
3. **`released_present_gross`,** the sum of the `pre`, `win` and `post` classes.
4. **The window's cohort at each sample time** (it is the `win` class there), and the survival
   readout:
   - the counts at t2 = 5400 s (B: 6000 s) and at each later sample;
   - each later count over the count at t2.
5. **`excess_over_blank`** for each run and fate: its row minus the family's blank row. Integrate
   the run and its blank together, as one system, so that their common part cancels exactly
   (erratum I, item 4).
6. **`cohort_net`,** the net tracker of erratum I, item 6. It is used only to size plants; the
   comparison never pairs it with an engine readout.
7. **Your own checks:**
   - the classes' sum against the row;
   - §9.7's identities: the hold, per producer, each fate row and the machines;
   - §4.8's moieties;
   - G's identity, G − G(0) + Σ heats = 0 (in D, with water's terms, LAWS.md §4).

   Report each check's largest residual.
8. **In every family,** compute the `pool0` class's closed form, P(0) e^(−k_f t), in decimal
   arithmetic of at least 50 digits, as a check on your integration. It holds whatever the monomer
   pool, the volume or re-synthesis does. Report its largest difference from your integrated
   class.

**How to integrate.**
- **The full ODE** of each world: every state of item 1, with the classes, the trackers and the
  counters.
- **Deviation form.** Each state is a deviation from its initial value, so a large row's small
  change keeps its digits. G − G(0) is formed the same way.
- **Restarts.** Restart the solve at every output time and at every switch: t1, t2, p_sched's
  2700 s, and in B, t_off. No output is interpolated.
- **Two methods.**
  - The primary is any method you state.
  - A second, of a different kind, is the check: for example an explicit Runge–Kutta pair at tight
    tolerance and an implicit one.
  - Report the largest difference between them, per quantity.
- **Accuracy.**
  - Every published non-constant value carries `accuracy`, its absolute error bound. Take it from
    the difference between your primary solve and one at tolerances 100 times tighter, and from the
    second method, times a safety factor of at least 2, which you state.
  - **The requirement** for every quantity READOUTS.md marks as judged: accuracy ≤ 10⁻¹¹ × the
    quantity's scale (READOUTS.md §3).
  - Where float64 cannot reach it, use extended precision (for example mpmath) for that world.
  - The judge refuses a file in which a judged value's accuracy exceeds its requirement.
  - Reported quantities carry their accuracy, with no requirement.

## 4. The classes, from your model's structure

Each (run, quantity, time) entry carries a class, fixed by your model before any engine run exists
(`agreement.py`'s rule at zero uncertainty, D323).

**`constant`, value `+0.0` exactly**, where your model is exactly zero by its structure:
- **At an idle fate** (p = 0: R is idle; p = 1: R_s is idle), at every output: the releases into
  it, its release heat, and its `pre`, `win` and `post` classes (erratum I, item 7).
- **In the blank, at every output:**
  - the hold, both releases and both release heats;
  - the completions, the initiations and the stage exits;
  - every stage complex, the engaged machines and the residues in transit;
  - transcription's heat;
  - every row's `pre`, `win` and `post` classes.
- **In every run:**
  - the `win` class at every t ≤ t1;
  - the `post` class at every t ≤ t2;
  - the `pre` class at t = 0.

**`stepped`** for every other entry, with `value`, `accuracy` and `scale`.

**Never `spread`.** Every world is deterministic.

A nonzero or non-structural value is never `constant`, however small. In particular, the excess
over the blank at an idle fate is `stepped`.

## 5. What the references never do

- run the engine;
- read an engine output;
- fit anything;
- round a reported value;
- report a value this folder does not ask for.

## 6. The plants' predicted effects, before any run

For each plant of CRITERIA.md, compute its effect from your model alone. That is the quantity the
plant's criterion compares, as the plant would change it.

| Plant | What you compute |
| --- | --- |
| P1 | In AF and AN, every run with releases into a fate: the net tracker `cohort_net` against the `win` class, at every output after t1 |
| P1′ | In AN, at each sample time: the window's members by the host's net-rate form on your own counters, against the `win` class. Use LAWS.md §6's form, with the per-interval rate taken from the net loss over each output interval. Report it in units of route 2's bound, three times LAWS.md §6's grid error, on your own counters |
| P1″ | In AN and at every idle fate: `excess_over_blank` against `released_present_gross` |
| P2 | AF's `p=1 returned` with p = 1 − 2⁻³⁰ in place of 1: the idle short-lived fate's releases, release heat and `pre`, `win` and `post` classes |
| P3a, P3b | AN's `p_sched returned` with transcription's schedule switching to `win` at 1800.5 s in place of 1800 s (P3a), or back to `post` at 5400.5 s in place of 5400 s (P3b). The judged step is 0.5 s, so this is one step late: the changed `win` class |
| P4 | AN's `p_sched returned` and B's `p=0.55 returned`, with the window marked at completion: the hold's members that completed in W, released into each fate and not yet lost. That is the completion-marked class, against the `win` class |
| P5 | AF's `p_sched returned` with k_s × (1 + 10⁻⁴): R_s, its net loss, its five classes and its release heat |
| P6 | AF's `p_sched returned`: G − G(0) without the hold's standard term (LAWS.md §5), against G − G(0) |
| P7 | AF's `p_sched`: the `held` run's free and engaged machines, against the `returned` run's |
| P8 | C's `p_sched returned` with the store's forward rate × 1.01: M, Mx, the excess over the blank, the `resyn` class, and every other class. You predict the latter unchanged; report their largest change |
| P9 | D's `p_sched returned` with the gene unit reading the declared volume V₀ = 1.0 pL in place of the current one, for every concentration it reads and every booking, while water still reads the current volume: the fate rows, their five classes, the release heats and G − G(0) |

For each entry, report:
- the honest value and the planted value at the quantity's largest distance;
- that distance relative to the quantity's scale;
- for P1′, the distance in units of route 2's bound.

## 7. The writer and its file

**One JSON file per family:** `reference_AF.json`, `reference_AN.json`, `reference_B.json`,
`reference_C.json` and `reference_D.json`.

**Its layout** (abbreviated; `"..."` stands for values or entries of the same form):

```json
{
 "kind": "cells.fr38_v2.reference@1",
 "family": "AN",
 "inputs": {"H0_copies": 160, "tau_s": 2400.0, "k_I_per_mM_s": 3000.0,
            "k_d_per_s": 0.00011111111111111112, "k_s_per_s": 0.0007407407407407407,
            "p_sched": [[0.0, 0.7], [2700.0, 0.25]], "window_s": [1800.0, 5400.0],
            "...": "every input of SPEC.md for this family, echoed with its unit in its name"},
 "units": {"amount": "fmol", "energy": "pJ", "time": "s", "volume": "pL",
           "copy_fmol": 1.6605390671738468e-09},
 "times_s": [0.0, 30.0, 60.0, "..."],
 "samples_s": [5400.0, 9000.0, 12600.0],
 "runs": {
  "p_sched returned": {
   "series": {
    "n_R": {"class": ["stepped", "..."], "value": [0.0, "..."],
            "accuracy": [0.0, "..."], "scale": 0.0},
    "label_R_win": {"class": ["constant", "...", "stepped", "..."], "value": [0.0, "..."],
                    "accuracy": [null, "...", 0.0, "..."], "scale": 0.0},
    "...": "every READOUTS.md quantity of this arm"
   },
   "survival": [{"fate": "durable", "t2_s": 5400.0, "ts_s": 9000.0, "alive_t2": 0.0,
                 "alive_ts": 0.0, "ratio": 0.0, "accuracy": [0.0, 0.0, 0.0]}],
   "excess_over_blank": {"durable": {"class": ["..."], "value": ["..."], "accuracy": ["..."],
                                     "scale": 0.0}},
   "not_compared": {"cohort_net_durable": ["..."], "cohort_net_short_lived": ["..."]},
   "checks": {"membership_sum_largest_relative": 0.0, "hold_identity_largest_fmol": 0.0,
              "G_identity_largest_pJ": 0.0, "...": "..."}
  },
  "blank": {"...": "..."}
 },
 "plants": [{"plant": "P1", "run": "p_sched returned", "quantity": "label_R_win",
             "time_s": 9000.0, "honest": 0.0, "planted": 0.0, "relative_distance": 0.0}],
 "method": {"primary": "...", "second": "...", "tolerances": "...", "safety_factor": 2.0,
            "largest_difference_between_methods": {"...": "..."}, "run_time_s": "..."},
 "provenance": {"revision": "...", "dirty_paths": [], "writer_version": "...",
                "hash_seeds_checked": [0, 1, 4242], "python": "...", "numpy": "...",
                "scipy": "...", "mpmath": "...", "sha256_of_this_file_excluded": true}
}
```

The sample's inputs are SPEC.md's. Every other number in it is a placeholder, 0.0, of the right
type, not a value.

**Rules for the file:**
- Each series has one entry per output time, in order.
- `class`, `value` and `accuracy` are parallel lists. A `constant` entry's accuracy is null.
- `scale` is per series (READOUTS.md §3).
- **Floats** are written with `repr`, which round-trips exactly. Times are the inputs' doubles.
- Keys are sorted, with fixed separators, so the bytes depend only on the values.

## 8. The invented-input file

- Your writer's own test writes `reference_invented.json`, in the same layout, for a family of your
  own invention:
  - other τ, H(0), pools, k_I, k_d, k_s, p schedule, window, sample times and horizon;
  - a grid of at most 61 outputs.
- It must exercise:
  - one idle fate, so that `constant` entries appear;
  - a blank, and `excess_over_blank`;
  - every series of arm A;
  - one plant entry of each kind.
- It is committed with your references. The judge's reader must parse it, its first read, before
  any engine run (D323).
