# FR-18: criterion X, registered before its run on the full set

*The @3 owner, 18 November 2026, 22:40 UTC, at the lead's direction (FR work under D222).*

This registers criterion X and its pass criteria before X runs on the FR-18 probe's full world set.
It is development work: no engine code changes the energy check until the lead rules on κ and the
cost policy and puts it to the user. It answers FR-18 (docs/FEATURE_REQUESTS.md): @3's energy check
refuses honest junction worlds at moderate steps, while a small misbooking passes it.

## What led here

- **The probe** (criterion registered at 17:09 UTC, run of record from 17:41 UTC; evidence in
  `/mnt/workspaces/Cells/core-pass-at3-20261118/fr18-probe/`) tested tolerances built from each
  step's own error estimate: E2 (step doubling) and E1 (the trapezoid split), with c = 2.
  - Both admitted FR-18's refused arms and every honest step.
  - Neither caught FR-3's registered plant, so neither was adopted.
- **The floor hides the plant, not the estimate.** At its 1 s row the plant moves the ledger by
  1.6e-11 pJ, while `ENERGY_ATOL_PJ` is 2e-8 pJ. The estimate there is 7.7e-18 pJ.
- **A tolerance built from the estimate admits whatever error the step makes,** so it bounds
  nothing.
- **Today's check refuses FR-18's arms on their first row only.** There the flows are one step's,
  so |R|/F is that step's relative error: 2.2e-2 at dt × rate 0.63. By the end of each run it is
  2e-6 to 9e-6.
- **An exploratory replay** of 16 of the probe's worlds (`fr18-probe/explore/`; development, not a
  verdict) suggested criterion X. Its parameters (κ, the band, the cap and the floor's magnitude)
  were chosen on that replay. This run tests them on all the probe's worlds, those 16 included.

## Engine models it runs

The same as the probe:
- `resolved_pump_tissue@3` alone: the replication's worlds and G1's @3 worlds;
- `resolved_pump_composite@1` over @3 with the judged acceptances' operators
  (`cell_owned_compartments@1`, `species_exchange@1`, `species_turnover@1`, `species_reactions@1`,
  `site_occupancy@1`, `scheduled_bath_composition@1`, `species_regulated_availability@1`), and G1's
  composites and frozen families.

## Why X can work

The energy residual R is constant along any exact trajectory: the ledger closes exactly for the
exact solution. So each step's change in R is that step's own local error, and errors in earlier
steps do not carry into it.
- For ARS(2,2,2) that error scales as dt³, and two half steps from the same state carry a quarter
  of it.
- A misbooking, a booked term wrong by a relative δ, scales as dt per step and appears whole in both
  the full step and the two half steps.

So the step doubling can be used to **subtract** the integration error from the residual, rather
than to allow for it. What remains holds every misbooking at its full size.

## Definitions

Rows are numbered k = 0, ..., n, with row 0 the initial state. Step k takes row k−1 to row k.

- **R_k** is the energy ledger at row k, as the engine's checks evaluate it: the probe's ledger path,
  unchanged. **F_k** is its flows: the sum of the absolute values of every heat and work
  accumulator.
- **d_k = R_k − R_(k−1)** is the full step's change in R. **d''_k** is the change after the same step
  taken as two half steps, from row k−1 with the step's held control.
- **Held steps (H):**
  1. an operator's event step (the probe's amendment 1), or a step whose half steps the step's
     validity refuses;
  2. in X2 only, the out-of-band steps defined below.
- **Counted steps (Q):** steps not held under rule 1, with |d''_k| > 1000 eps M_k.
- **The step ratio** is q_k = d_k / d''_k on counted steps. It is 4 for a clean second-order step.
- **The integration part** is a_k = 4/3 (d_k − d''_k) for a step not held, and 0 for a held step.
- **The magnitude** is M_k = F_k + T_k + O_k, where:
  - T_k is the absolute values, element by element, of the tissue ledger's stored terms, as
    `surface_tissue.balances` forms them: each inventory element's two chemical terms (cytosol and
    outside, with no intracellular override) and each patch's electric term. For a composite these
    are taken from its inner @3 state and layout.
  - O_k is the energy ledger's own magnitude where the model reports one, plus each declared kind's
    |stored_pJ| ledger terms.
- **The floor** is floor_k = `LEDGER_STEP_ROUNDING` × eps × k × M_k, which is 2.5 eps × accepted
  steps × magnitude: the rounding rule the other running ledgers already use. **`ENERGY_ATOL_PJ` is
  dropped** for this check.
- **The corrected residual** is C_k = R_k − Σ_(j≤k) a_j − Σ_(j≤k, j in H) d_j.

## The rule

At every row k ≥ 1:
- **The check:** |C_k| ≤ floor_k + κ Σ_(j≤k) |a_j|.
- **Held steps:** each held step's own change must satisfy |d_j| ≤ `ENERGY_ATOL_PJ` + rtol F_j,
  today's bound at its row.
- **The order condition:** the median of q_k over the counted steps must lie in [3.5, 4.6].
  Otherwise the run is refused, because its error estimate is not trusted. A run with no counted
  step is "at rounding", and the condition does not apply to it.
- **The integration error is reported, not capped.** Per world, report the largest Σ_(j≤k) |a_j| /
  F_k over the rows, and its value at the last row.

Two variants are registered. Each is decided separately.
- **X1: κ = 1/4.** Only rule-1 steps are held.
- **X2: κ = 1/16.** It also holds out-of-band steps: counted steps with q_k outside [3.5, 4.6].
  At most max(8, ⌈0.02 |Q|⌉) steps may be held this way. A run with more is refused.

## Worlds

The probe's set, with its horizons and caps:
- FR-18's seven arms: Figure 5a's network at g = 100 at dt × rate 0.63, 0.31, 0.157 and 0.078, and
  Figure 3's two cells at g = 50 at dt × rate 0.080, 0.040 and 0.020, each to its own horizon;
- G1's 113 worlds, from the acceptance baseline's saved definitions, capped at 200 steps;
- the seven judged acceptance worlds, capped at 2,000 steps;
- fr3-site-occupancy-v1's q1_eps_1e-1, to 1 s plus ten steps.

RK4 worlds are out of scope and listed as excluded, as in the probe.

## Planted controls

These are edits of the honest rows, never fed back into the run, exactly as in the probe. A
planted row is checked as an honest row would be, with its own flows in F and M:
- **P1:** every work accumulator × (1 + 1e-6), from the first row;
- **P2:** the heat accumulators × (1 + 1e-6), and every work accumulator × (1 + 1e-4);
- **FR-3's registered plant:** site_work_pJ[r0] × (1 + 1e-6) at its 1 s row.

## The decision (for each variant)

X works if all three hold:
- **(a)** every accepted row of FR-18's refused arms (Figure 5a at 0.63 and 0.31, Figure 3 at
  0.080) passes the check, and those arms meet the order condition;
- **(b)** every accepted row of every in-scope honest world passes the check, every held step
  passes its own bound, and every world meets the order condition and, in X2, the cap. The honest
  worlds are G1's, the judged worlds, FR-18's other arms, and the plant world's honest rows;
- **(c)** FR-3's registered plant fails the check at its planted row.

Otherwise X does not work, and the report names the failing worlds, rows and ratios. P1 and P2 are
reported, with the first row at which each is caught, but are not part of the decision.

## What is reported

Per world and variant:
- the steps run;
- the largest |C_k| / (floor_k + κ Σ|a_j|) and its row;
- the held steps, with the largest ratio of a held step's change to its bound;
- the median step ratio and the counted steps;
- the integration error;
- for each plant, the first row at which X catches it, beside today's check and E2;
- the cost: two extra half steps per step.

## Known limits

- An event's own booking, and each X2 held step, are checked only by today's bound.
- In X2, a world whose local error changes sign often may hold many steps apart and meet the cap.
- M lacks the stored terms of an operator that reports no magnitude. That makes the floor smaller,
  which is stricter.
- The rows checked are the replay's accepted rows: the engine's own step function, from a clean
  snapshot of this registration's commit.

## Provenance

- **Source:** a clean snapshot of this registration's commit, which is main at its branch point
  plus this file.
- **Tools:** the probe's harness unchanged, plus the registered run's recorder and evaluator. Their
  digests are recorded in the run's `tools.sha256` before the first world runs.
- **Run:** `/mnt/workspaces/Cells/core-pass-at3-20261118/fr18-x/`, one detached unit on the light
  CPUs at nice 10, memory-capped.
