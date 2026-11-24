# FR-47's reference spec: the worlds and what the references compute

This folder is for the code-blind references agent of FR-47's qualification
(`docs/FR47_SHELL_EXCHANGE_PROTOCOL.md`; D323).

**Rules for the references:**
- **Code-blind.** Do not read `src/`, `tests/` or any engine module. Read only this folder and the
  protocol document.
- **Value-silent.** This spec states every input, and no result. Compute every result here.
- **Deterministic regeneration.** The writer's output must be bitwise the same under at least two
  other `PYTHONHASHSEED` values (FR-43 part 2's lesson), shown before a head is reported.
- **The writer** (§5) writes the file the judge reads. The judge is first run on a file this writer
  writes on invented inputs, before any engine run (D323; FR-30's lesson).

## 0. Units: every declared count

- **Every count is a number of molecules in one place.** A place is one species in one compartment:
  the pool, the lumen of one shell, or the shell's wall. No count is a concentration, an amount in
  moles or a count per shell.
- **The units of every other quantity:**

  | Quantity | Unit |
  | --- | --- |
  | Volumes | litres (L) in the declarations; the per-molecule rates below use m³ (1 L = 10⁻³ m³) |
  | Area | m² |
  | Permeability | m/s |
  | Times | s |
  | Rates | per second, per molecule or per copy, as stated |
  | Standard potentials and Δ | k_BT (μ°/RT) |
  | Heats and free energies | k_BT |

- **Physical constants:**
  - N_A = 6.02214076 × 10²³ per mol, exact (SI 2019);
  - the standard concentration c0 = 1 mol/L (1000 mM);
  - the temperature is 296.15 K. It enters nothing below: every energy is in k_BT.

## 1. The exact process's rates (the registered laws' formulas, per molecule)

- **The shell's crossing** (`cells.shell_permeation@1`):
  - a pool molecule enters one shell's lumen at κ_in = P_s·A_sh/V_out;
  - a lumen molecule leaves at κ_out = P_s·A_sh·e^Δ/V_in;
  - here V is in m³, and Δ = μ°_lumen − μ°_solution of the tracer.
  - Every molecule moves independently of every other.
- **A gate** (W2 only, `cells.gate_factor@1`): both directions of the crossing are multiplied by
  g(K) = (K·e^a + (N_g − K)·e^b)/N_g.
  - K is the shell's open forms G, and N_g − K its closed forms H.
  - a and b are the forms' declared barrier shifts.
- **The gate's own switching** (W2, `cells.stochastic_mass_action@1`, a one-to-one wall step):
  - each copy G → H at k_GH, and each copy H → G at k_GH·e^(μ°_H − μ°_G);
  - each copy switches independently of every other copy and of the tracer.
- **A withdrawal** (fraction f, a dyadic number, with a tracer-free buffer): each pool molecule is
  removed independently with probability exactly f. Nothing is added. Lumen molecules stay.
  - Its booked mixing heat is −k·ln(1 − f), with k the pool's kept count.
  - Exact events book it to rounding, not to the bit: 2–4 × 10⁻¹⁶ relative, checked on a made-up
    one-slot shell.
- **A replacement** (a full wash, with a tracer-free fresh pool): every pool molecule is removed.
  Nothing is added. Lumen molecules stay.
- **The wall's subunit B** is a constant count: no step moves it.

## 2. The worlds

### W1: two compartments with washes (one shell in a finite pool)

| Input | Value |
| --- | --- |
| Pool volume V_out | 2 × 10⁻¹⁸ L |
| Lumen volume V_in | 2.5 × 10⁻¹⁹ L |
| Shell area A_sh | 1.2 × 10⁻¹⁵ m² |
| Permeability P_s | 1.5 × 10⁻⁷ m/s |
| Tracer potentials | solution 0.0, no lumen potential (Δ = 0) |
| Founder | S@pool 30,000 molecules; S@lumen 0 molecules; B@wall 120 molecules |
| Stops | t = 2.5 s, a withdrawal at f = 1/2; t = 5.0 s, a withdrawal at f = 1/4; t = 7.0 s, a replacement; t = 9.0 s, a withdrawal at f = 1/2 |
| Observation times | 1.25, 2.0, 3.5, 4.5, 6.0, 6.5, 8.0 and 10.5 s, none at a stop |
| Horizon | 11.0 s |

### W1Δ: W1 with a lumen potential

W1 with the tracer's potentials **solution 0.7, lumen 0.7 + ln 2**, so Δ = ln 2. Everything else is
as in W1.

### W2: a switching gate, without washes

| Input | Value |
| --- | --- |
| Volumes, area and P_s | as in W1 |
| Tracer potentials | solution 0.0, Δ = 0 |
| The gate | forms G (open) and H (closed); a = +1.0 for G and b = −1.0 for H; μ°_G = −1.0 and μ°_H = −1.5; k_GH = 4.0 per s per copy |
| Rungs | N_g = 64, 256, 1,024 and 4,096 copies, a separate world each |
| Founder per rung | S@pool 20,000 molecules; S@lumen 0; B@wall 100; G@wall N_g/2; H@wall N_g/2 |
| Observation times | 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0 and 6.0 s |
| Horizon | 6.0 s |

**W2 is not yet sized.** Nothing so far shows that any rung resolves the representation gap at
M = 128. The references' resolution table (§3.3) decides C8's claim, and the lead may resize W2's
inputs after reading that table and before the tag.

## 3. What to compute (every quantity, no values here)

### 3.1 W1 and W1Δ, the exact process

- **Per place (S@pool, S@lumen, B@wall) and per observation time:**
  - the mean, the variance and the fourth central moment of the count;
  - the class: `constant` where the variance is exactly zero (a point mass), else `spread`.
- **Per stop:**
  - the removed count's mean, variance and fourth central moment;
  - for each withdrawal, the mixing heat Q_w = −k·ln(1 − f), with k the pool's kept count: its
    mean, variance and fourth central moment.

### 3.2 W1 and W1Δ, the deterministic representation

- **The mean trajectory:** the rate equations of the counts' means, with each stop's mean map. That
  is n_pool → (1 − f)·n_pool at a withdrawal, and n_pool → 0 at the replacement.
  - The counts at the observation times, the removed amounts and the mixing heats.
- **Per interval between consecutive stops** (and from 0 to the first stop, and from the last to
  the horizon): the continuous heat Q_c = −[F_cont(end) − F_cont(start)] of the mean counts.
  - F_cont(n) = Σ_places n·(μ°_place − ln X_place) + n·ln n − n, with the term 0 at n = 0.
  - X_place = N_A·V_place·c0, V in L and c0 in mol/L.
  - The wall's places enter F_cont as constants and cancel in Q_c.

### 3.3 W2, per rung

- **The exact mean, variance and fourth central moment of S@pool, S@lumen, G@wall and H@wall** at
  the observation times. G and H are each a sum of independent copies, and they test the switching
  directly.
- **B@wall,** which no step moves, is a `constant` pair, as in W1 (AMENDMENT-2026-11-23.md §10).
  - Given the open count K, the tracer's rates are linear in its counts. So the moments
    E[n^j·1{K = k}], j ≤ 4, obey a closed linear system.
- **The class of every pair:** `constant` or `spread`.
- **The mean-field solution, as the deterministic representation's registered limit gives it:**
  - the rate equations of the means, with g evaluated at the mean open count;
  - the gate's switching at k_GH·(N_w + 1)/N_w per G copy and k_GH·e^(μ°_H − μ°_G)·(N_w + 1)/N_w
    per H copy;
  - N_w is the wall's total count, B + G + H = 100 + N_g, a constant.
  - The factor is the limit's membrane factor for a one-to-one wall step, (N − c + 1)/(N − c) with
    c = 0. The exact process's factor cancels to 1 (§1).
  - The factor was checked on a geometry-free, single-lineage world only, because (d) cannot run a
    shell before FR-47's build. That build confirms it in a shell world before the checker runs.
  - So the gap below carries an O(1/N_w) term from this factor, beside the O(1/N_g) term from the
    gate's correlation with the tracer.
- **The representation gap:** the mean-field minus the exact mean, per observable and time.
- **The gap's resolution at M = 128:** the gap over the exact mean's SD/√128, per pair.

### 3.4 The plants' predicted effects, before any run (CRITERIA.md)

For each plant, the quantity its criterion compares, as the plant would change it, from the
reference alone: the planted value, and its distance from the honest value in units of the
criterion's bound.

## 4. What the references never do

- run the engine;
- read an engine output;
- fit anything;
- round a reported value;
- report any value that this spec does not ask for.

## 5. The writer and its file

- **One JSON file per world:** `reference_W1.json`, `reference_W1D.json` and
  `reference_W2_Ng<N_g>.json`.
- **Each file holds:**
  - `"world"`: this spec's inputs, echoed;
  - `"pairs"`: [{observable, time_s, class, mean, var, mu4}, ...], with `value` in place of
    mean, var and mu4 for a `constant`;
  - `"stops"`: [{time_s, kind, f, removed: {class, mean, var, mu4}, mixing_heat: {class, mean,
    var, mu4}}, ...]. A `constant` holds `value` in place of mean, var and mu4. The replacement has
    f 1.0 and `mixing_heat` null, since exact events book no mixing heat there
    (AMENDMENT-2026-11-23.md §10);
  - `"d"`: {pairs: [{observable, time_s, value}], stops: [{time_s, removed, mixing_heat}],
    intervals: [{start_s, end_s, heat}]};
  - for W2, `"gap"`: [{observable, time_s, gap, resolution}];
  - `"plants"`: [{plant, criterion, honest, planted, distance_in_bounds}];
  - `"provenance"`: the references' revision, the writer's version, and the hash seeds of the
    regeneration check.
- **Floats** are written with `repr` (round-trip exact). **Times** are the inputs' floats.
- **The writer's own test** writes a file for invented inputs (other volumes, counts and times). The
  judge must read that file before any engine run.
