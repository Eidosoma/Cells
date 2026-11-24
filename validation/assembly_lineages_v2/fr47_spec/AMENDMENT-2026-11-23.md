# Amendment of 23 November 2026: the references agent's questions answered

This amendment answers the references agent's questions on the spec at c6d7667e
(`docs/FR47_SHELL_EXCHANGE_PROTOCOL.md`; D323).
- It is value-silent: words only, with no result.
- Its statements about the engine were checked against the engine's code and against probes on
  made-up worlds, never on a protocol world.
- Questions 1 and 11 (location and provenance) were answered by the lead.
- **What changed in the spec:**
  - **One error, fixed:** CRITERIA's P4 named a stop that W1 does not have (question 2).
  - **Statements added, with no band changed:** CRITERIA states the two z formulas, the scales,
    the plants' units and C8's tie rule. SPEC adds B@wall to W2's pairs and states the stops'
    classes in the schema.

## 2. P4's withdrawal after the full wash (an error, fixed in CRITERIA)

- **W1 is as intended**, and P4 is corrected. P4's criterion C4 is judged at the **9.0 s
  withdrawal**, the first stop after the full wash at 7.0 s.
- **How the error arose.** The design note's earlier W1 had its post-wash withdrawal at 7.5 s. When
  W1's inputs were re-chosen, the stops moved, but P4's text did not.

## 3. P3, "(d)'s wash applied to the lumen too"

- **Your default is the registered plant.** At every stop, (d) applies the stop's map to the lumen
  as well as to the pool:
  - at a withdrawal, the lumen's count times (1 − f);
  - at the replacement, the lumen's count set to 0.
- **The planted (d) books the lumen's loss as removed,** with the pool's, at that stop.
- **A replacement-only variant** may be sized as information. It is not registered.

## 4. P2, keeping (1 − f)²

- **Your default is the plant.** At each withdrawal, the planted (d) keeps k = (1 − f)²·n of the
  pool.
  - It books (1 − (1 − f)²)·n as removed.
  - It books −k·ln(1 − f) as the mixing heat: the physical f in the formula, with the planted k.

## 5. P5, the gate factor on one direction

- **The planted direction is the entry, pool → lumen**, the entry step's forward direction as it is
  declared.
  - Only κ_in is multiplied by g(K).
  - κ_out, the exit, is left ungated.

## 6. s_y for the stop and interval quantities

Each quantity's scale is the largest |reference value| of that quantity over the world:
- **removed counts (C1 for (d), C4):** over the world's stops, the replacement included;
- **mixing heats (C4):** over its withdrawals, since the replacement books none;
- **interval heats (C9):** over its intervals.

## 7. The plants' "criterion's bound"

- **The statistical criteria:**
  - **The unit.** For C2 (P7) and C4 (P8, exact events), a plant's distance is
    |planted − honest| / (6·SD_ref/√128).
  - **Why 6.** A plant is caught when its criterion fails, and the fail band is 6.
  - **Which SD.** SD_ref is the honest reference's SD at that quantity, since the judge compares the
    planted replicas against the honest reference.
- **C5 for P6:** the derived bound with the step guard's cap, A = 10⁴; eps = 2⁻⁵²; P_t = 2 (S@pool
  and S@lumen); T = 30,000 (W1's founder); and S = 4 stops.
- **Each (plant, criterion) entry** reports its compared quantity with the largest distance in
  bounds, and names it (observable and time, stop, or interval).

## 8. C8's "largest pair"

- **The largest pair** is the pair with the largest |gap| over S@pool, S@lumen, G@wall and H@wall at
  the observation times.
- **Ties.** Without washes, S@pool + S@lumen is constant, so their gaps are opposite and their SDs
  equal. A tie goes to the first in that order (S@pool, S@lumen, G@wall, H@wall), then to the
  earliest time.
- **Resolution** = |gap| / (SD/√128), with SD the exact SD at that pair.
- **The slope** is fitted on ln|gap| against ln N_g.

## 9. The two z formulas, now stated in CRITERIA

With M = 128 replicas, ȳ their mean, and s² their unbiased variance (divisor M − 1):
- **the mean's** z = (ȳ − m)/√(σ²/M);
- **the spread's** z = (s² − σ²)/√((μ₄ − σ⁴(M − 3)/(M − 1))/M);
- m, σ² and μ₄ are the reference's mean, variance and fourth central moment.

## 10. The schema

- **Each stop's quantities carry a class.** `removed` and `mixing_heat` each carry `class`
  (`constant` or `spread`), as pairs do. A `constant` one holds `value`, and a `spread` one holds
  mean, var and mu4.
- **The replacement** is written with f 1.0 and `mixing_heat` null. Exact events book no mixing heat
  there, only the old pool's free energy to the sink and the fresh pool's as work.
- **W2's pairs include B@wall**, a constant as in W1: no step moves it. §3.3 had omitted it, and
  SPEC now lists it.
