# FR-18: criterion X, registered before its run on the full set

*The @3 owner, 18 November 2026, 22:38 UTC (its commit's time), at the lead's direction (FR work under D222).*

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

## Amendment 1: FR-8's worlds, registered before X runs on them

*19 November 2026, 00:59 UTC (its commit's time), at the lead's direction, after the run on the full set. The rule,
both variants and their parameters are unchanged.*

**Why these worlds:**
- FR-8 measured the order falling to 1.25–1.7 through H2's switch.
- Seam D changes the bookings, and M5's trapezoid arms already use `trapezoid_nonnegative@1`.

**The worlds** are built by FR-8's own stage-0 builders, read only, as FR-8 registered them:
`validation/long_duration/worlds.py` and its `registration_20261118.json`, from the snapshot of
FR-8's branch at c5183aba. The two fixture modules those builders call
(`validation/tissue/projective_study.py`, `regulated_availability_fixtures.py`) are byte-identical
in that snapshot and in this run's.
- **H2:** `case_cue3`'s two heredity cells to the registered 3600 s horizon, with the 9× Na-leak cue
  on at 1800 s and off at 1800.3 s. It runs at FR-8's declared dt of 1 ms (arm R1), with FR-8's
  §5.2 observation times. Engine model: `resolved_pump_tissue@3` alone.
- **W0, as M5 builds it:** 60 s, with the dose step at 20 s and the write at 40 s, observed every
  1 s, with the default booking (`explicit_tableau`) at dt 1, 2, 5 and 10 ms. Engine model:
  `resolved_pump_composite@1` with `scheduled_species_turnover@1` and
  `species_regulated_availability@1`.
- **M5's trapezoid arms:** the same W0 arms with the junction booking `trapezoid_nonnegative@1`.

The 10 ms arms are refused at definition time, which is M5's registered result. They are reported
with the check that refuses them.

**The decision, for X2 in each world:**
- every accepted row passes the check;
- every held step passes its own bound;
- the order condition holds, and so does the cap.

This is condition (b) for these worlds. X1 is reported. P1 and P2 are reported but not decided.
Nothing in FR-8's own measurements is judged here.

**Tools:** `recorder_x.py` and `evaluate_x.py` run unchanged, through a world wrapper,
`recorder_fr8.py`, which builds these definitions and is digested beside them. The source is a
clean snapshot of this amendment's commit. The run is
`/mnt/workspaces/Cells/core-pass-at3-20261118/fr18-x/fr8/`, detached on the light CPUs at nice 10
and memory-capped.

**A note on admission, before the run (01:03 UTC, its commit's time).** H2's builder sets `max_trace_bytes` to 2 GB.
`timeline()` estimates a trace for the whole 3600 s horizon at 1 ms (6.9 GB) and refuses the
replay, which never keeps that trace: it keeps per-row values only. FR-8 ran H2 through the
windowed runner instead. So the wrapper raises H2's `max_trace_bytes` to 14 GB. Only that
admission estimate reads it. Nothing else in the rule, the worlds or the tools changes.

**The note, corrected before any world ran (01:05 UTC, its commit's time).** A first launch at 01:04 UTC found W0's
1 ms arms refused by the same admission estimate (2.9 GB against W0's 2 GB). It was stopped before
any other world ran, and its two refusals are kept in `fr8/out-stopped-1/`. The wrapper now applies
one rule to every FR-8 world: a definition whose whole-horizon estimate exceeds its own
`max_trace_bytes` gets twice the estimate. That means 13.8 GB for H2 at 1 ms and 5.9 GB for W0's two
1 ms arms. The 2, 5 and 10 ms arms are unchanged.

*Times corrected to their commits on 19 November, 01:08 UTC. The registration's commit is
570df4fd (22:38:17Z), amendment 1's is e886e928 (00:59:55Z), and the two notes' are 68e8da48
(01:03:34Z) and 344a847e (01:05:36Z). The run of record on FR-8's worlds launched at 01:06:00Z from
a snapshot of 344a847e.*

## Amendment 2: the run-level conditions in a running form, registered before their re-evaluation

*19 November 2026 (its commit's time), at the lead's direction under D224 item 2, before any
re-evaluation and before any engine code. The per-row check, κ, the band, the floor, the counted
and held steps and each held step's own bound are unchanged.*

**Why.** X2 is adopted as an opt-in energy check (D224). An engine checks rows as each window
ends. The order condition (the median of q_k over the counted steps) and X2's held-step cap (at
most max(8, ⌈0.02 |Q|⌉) out-of-band steps) are whole-run quantities, decided here at the run's end,
so a check decided at window ends could give a different verdict.

**The running form.** At each window end, at a row k:
- the order condition holds if no step j ≤ k is counted, or the median of q_j over the counted
  steps j ≤ k lies in [3.5, 4.6];
- X2's cap holds if the out-of-band held steps j ≤ k number at most max(8, ⌈0.02 |Q_k|⌉), with Q_k
  the counted steps j ≤ k.

A run is refused at the first window end where either fails. The registered form is the running
form decided at the last row only. Which steps are held, and so C_k, already depends only on each
step's own q, so the per-row check is the same in both forms.

**The test, on the saved records only, with no new simulation.**
- Both conditions are re-evaluated at every row, the strictest running form, on every evaluated
  world of the full set (`fr18-x/out/`) and of FR-8's worlds (`fr18-x/fr8/out/`). Everything else
  is the registered evaluator's.
- From them come X2's (a), (b) and (c) on the full set, and the decision on FR-8's worlds.
- **If every verdict equals the registered run's,** the running form is adopted. Every row is a
  window end here, so any window partition gives the same verdicts: its window ends are rows, and
  the last row is always one.
- **If any verdict differs,** the conditions stay as registered, decided over the whole run, and
  the engine decides them at the run's end.
- Either way, the report lists each world whose running conditions fail at some row, with that
  row and the condition.

**Tool.** `evaluate_x_running.py`, beside `evaluate_x.py`, which it imports unchanged. Its digest is
recorded before it runs.

### Amendment 2's result: the verdicts differ, so the conditions stay whole-run

*Run on 19 November 2026 from the saved records, with no simulation: `fr18-x/amendment2/`
(`results.json`, `results.txt`, and `tools.sha256` digesting `evaluate_x_running.py` and the
registered `evaluate_x.py` before the run).*

- **The registered verdicts are reproduced.** The test re-derives them from the records with the
  registered evaluator: on the full set, X2's (a), (b) and (c) all hold; on FR-8's seven worlds,
  every world is admitted. The whole-run medians match the registered ones.
- **The running form refuses 47 admitted worlds.**
  - 40 of the full set's 122 worlds and all 7 of FR-8's fail the running order condition at row 1.
    There a single counted step, the run's first, is out of band, at q between 1.79 and 7.47.
  - One of FR-8's worlds, `w0-explicit_tableau-1ms`, also fails the running cap. It holds its ninth
    out-of-band step at row 224, where 224 steps are counted and the cap is 8. Its whole run ends
    with 9 held of 745 counted, against a cap of 15.
- **So (b) on the full set, and FR-8's decision, would change.** By the amendment's own terms the
  running form is not adopted. The order condition and X2's cap stay as registered, decided over
  the whole run, and the engine decides them at the run's end.

## Implementation of X2 as an opt-in energy check (design before code, D142)

*19 November 2026, under D224 as amended (fe365fcb). The rule is X2 as registered, with its
whole-run conditions. Engine code waits for the @3 owner's queued landings; this section fixes the
design first.*

**Selection, in the execution spec** (`definitions/specs.py`, a recorded exception).
- The field is `execution.energy_check = {"check": "step_doubled_energy@1", "integration_error_cap": c}`.
  Without it, a run keeps today's check. `to_dict` omits the default.
- Refused at parse:
  - an unknown check;
  - a missing, non-finite or non-positive cap (there is no default);
  - a solver other than ARS(2,2,2);
  - a model without the step and residual functions the wrapper calls.
- With X2 off nothing in a program or a constant moves: crossrev is identical, and R1's parse row
  differs by the defaulted field's text, as seam D's did.

**1. The step-doubling wrapper, at the model's step function** (`execution/runner.py`, an
exception). It is generic, so composites are covered with their operators, as `recorder_x.py`'s
`_scan` takes them.
- With X2 on, the discrete and window rollouts step with a wrapper around `model.checked_step`.
  Each step is taken whole and as two half steps from the same accepted state, with the step's held
  control.
- On the device, the wrapper evaluates the energy residual of the full step's end and of the half
  steps' end with `model.device_balances(·, p)["energy"]`: `surface_pump_v3`'s and the composite's,
  each with its own adjustments.
- The scan carries R at the last accepted row. Each step emits d_k and d''_k, with d''_k NaN (held
  under rule 1) where the halves are refused or the step is an operator's event step. The runner
  passes the event steps as a mask, found from the schedule's operator-record changes, as the
  probe's `event_steps` does.
- With X2 off, the rollouts receive `model.checked_step` itself: today's programs.

**2. The run-level record, in the checkpoint** (`execution/state.py`'s `Checkpoint` and the
checkpoint IO in `records/io.py`, exceptions).
- `Checkpoint.energy_check` is `None` with X2 off, so today's checkpoints and their files are
  unchanged.
- With X2 on, it carries:
  - R at the checkpoint's row;
  - Σa, Σ|a| and the held steps' Σd;
  - every counted step's q, the whole-run median's input;
  - the out-of-band held count;
  - the running diagnostics.
- k is the checkpoint's `step_index`.
- Each window's final checkpoint carries the record forward. Files store its arrays exactly, so a
  run restarted from a checkpoint continues the same record: two segments give exactly what one
  gives.
- `validate_checkpoint` refuses a record whose presence disagrees with the definition, and one
  whose R is not the checkpoint state's residual.

**3. The per-row check, with host and device parity** (`models/surface_pump_checks.py`, the @3
owner's; `execution/row_checks.py`, an exception).
- At each accepted row k, the step's d_k and d''_k and the record give the counted and held steps,
  q_k, a_k, C_k and floor_k, as the registration defines them. M_k = F_k + T_k + O_k, with T and O
  formed as `recorder_x.py` forms them: a composite's from its inner state and layout, its retiring
  rows adjusted.
- Refused at the row:
  - |C_k| > floor_k + κ Σ|a| (κ = 1/16);
  - a held step with |d_j| above today's bound at its row;
  - the cap, form B: Σ_(j≤k)|a_j| > cap · F_k + floor_k.

  Held steps carry a = 0, so the cap does not see them.
- In an X2 run today's energy bound is not applied. The energy ledger is still evaluated and
  reported, and every other ledger is checked as today.
- The cap, κ and the registration's constants travel in their own constants type, used only with
  X2 on, so `CheckConstants`, crossrev's bindings and `world_key` do not move when it is off.
- The host runs the check on each segment after the model's `check_values`. The device runs the
  same kernel in the window row checks (`row_checks="device"`).
- Both give the same verdicts, and their diagnostics agree within the device checks' existing
  criteria.

**4. The run-end hook** (`runner.run` and `windows.run_windowed`). After the last accepted row the
whole-run conditions are decided from the record:
- the median of the counted q in [3.5, 4.6] (with none counted, the run is at rounding and the
  condition does not apply);
- the out-of-band held count at most max(8, ⌈0.02 |Q|⌉).

A run failing either is refused at its end, naming the condition. The diagnostics report the
largest check ratio, Σ|a|/F at its largest and at the end, the median, and the counted and held
steps.

**Scope and limits.**
- ARS(2,2,2) only. The evidence on FR-8's worlds stops at 5 ms: W0 at 1, 2 and 5 ms, and H2 at 1 ms.
- The cost is two extra half steps and two residual evaluations per step. It is measured once on W0
  at 1 ms, X2 on against off, on the timed lane.
- `validation/` keeps the harness (`recorder_x.py`, `evaluate_x.py`, `recorder_fr8.py`,
  `evaluate_x_running.py`) as the check's independent reference.

**Tests (D224's cost rule).** Rows in existing parametrized files, each world-compiling one with
its seconds stated:
- parse refusals;
- host and device parity in the window row-check tests;
- the restart row, two segments against one, exactly equal;
- one plant row, FR-3's registered plant refused.

The qualification run, once against the saved verdicts, is the boundary set:
- the three refused arms;
- X1's four mixed worlds;
- `W1_P4@0.001` and its protocol twin;
- `division_quartered_values`;
- FR-3's plant;
- cleft_egg.
