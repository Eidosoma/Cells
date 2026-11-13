# J1 combination round on R-full: rationale

**Proposed, revision 2 (13 November 2026): a draft for the lead to register. Nothing here has been
run.** The user approved a combination round ("Lets go on your suggestions"). The lead's brief set
its contents and the lead's review set this revision; the advisor reviewed both. The
machine-readable file is [`j1_combination_round.json`](j1_combination_round.json); the decisions
still open are in its `lead_decisions_requested`.

**Why pair the arms.** The single arms ([rationale](j1_diagnostic_arms.md);
[evidence](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-diagnostic-01/)) each did one
thing:
- A1 (a bath-facing fraction f of new membrane) is the only arm that brings Em at J1 into the
  window, but there Em is still falling at J1 and Rm has no late rise.
- A7a (access scaled with furrow depth) is the only arm with a late Rm rise, but it moves Em at J1
  by at most 0.04 mV, because Rm2 pins the access.

This round runs A1 × A7a. It also tests whether a level-shifter other than bath-facing membrane
can do A1's job. Seal × A6c is the one such combination whose level at J1 is not already known.
The round ends either in frozen candidates plus a C1 registration, or in parking. There is no
third diagnostic round.

## Calibration and what is left as the test

| Unknown | Fixed by | Arms |
| --- | --- | --- |
| P_old | Rm1 852 kΩ (dLB74 Table I) | all |
| Access A/L or κ | Rm2 488 kΩ at J1 (dLB74 Table I) | all |
| Bath-facing fraction f | J1 itself: f is fixed where Em at J1 crosses −20.3 mV, the declared calibration the arm file's last lead decision anticipates | A1 × A7a |
| Depth exponent α | No datum, so a curve: 0, 0.5, 1, 2 for A1 × A7a, and 0, 1 elsewhere. α = 0 is the registered access; α = 1 (a uniform resistive slit) is marked before any run | all |
| Seal | Nothing: a fixed rule (access D_Cl = 0) | seal × A7a, seal × A6c |
| A6c's P_K,new and P_Na/P_K | The −VM arm's own Em2 and Rm2 (two data, two unknowns): the central fit as recorded in `a6_final.json` | A6c × A7a, seal × A6c |

**What is left as the test:**
- **A1 × A7a.** Rm1, Rm2 and J1 are all used up as calibration. The only test in this round is
  the 0–35 min shape. Its out-of-sample test is C1, held until a candidate is frozen.
- **Seal × A6c.** Its level at J1 is not known, so T-J1 is a real test, together with the shape.
- **Seal × A7a and A6c × A7a.** Their T-J1 results are predicted in the file and expected to fail.
  They are kept for what is not known: the seal's time course, never computed, and A6c's shape
  with the late-rise mechanism.
- **Cytosolic Na** is reported and never selected on.

| Arm | Points | Predicted Em at J1 (written before any run) |
| --- | --- | --- |
| A1 × A7a | α 0, 0.5, 1, 2, f calibrated at each | −20.3 mV by construction (not a test) |
| Seal × A7a | α 0, 1 | −16.53, −16.55 mV: the seal's computed value plus A7a's shift (fails) |
| A6c × A7a | central fit, α 1 | −13.78 mV: A6c's value plus A7a's shift (fails) |
| Seal × A6c | central fit, α 0, 1 | −17.50, −17.51 mV: additive estimate from the single-arm shifts; the interaction is what the run measures |

## Pass criteria

The criteria are dLB74's description of the series (p531, V), turned into numbers and registered
before any run. Fig. 2 (one egg) is not a target, for three reasons:
- **It is one egg**, with no spread to set a tolerance from. p531 describes the series whose
  Table I means calibrate R-full.
- **Its numbers were read after the single-arm runs.** The approximate reading of the trace was
  registered at `cfe0fa3`, before those runs. Its D-values were first computed after them, and no
  digitisation with an uncertainty exists.
- **p531 speaks to exactly the features at issue:** how Em falls and when it reaches its minimum,
  how long the Rm fall lasts, and how large the late changes are.

**Fig. 2 did shape two thresholds.** T-D7 and T-R17 were restated after the drafter checked Fig.
2's egg against their first forms. In the egg's own terms, the first T-D7 would reject it and the
restated form admits it at its boundary. Both forms are registered, and a point can be frozen only
if it passes under both. The drafter knew the single-arm results while writing every threshold.

| Criterion | p531 wording | Threshold |
| --- | --- | --- |
| T-J1 (arms without A1) | Table I: −20.3 ± 0.8 mV | Em at J1 in [−21.9, −18.7] mV |
| T-D2 | "in the next 10 min it becomes about 10 mV more negative" | Em(17) − Em(7) in [−12.5, −7.5] mV (rounds to 10 at 5-mV steps) |
| T-D3 | "during the second half of cleavage it often shows a small decrease" | Em minimum at or after 15 min |
| T-D4 | "(1–3 mV)", "often" | Em(J1) − minimum ≤ 3 mV, with no lower bound |
| T-D5 | "drops drastically from 7 till 17 min" | D5 ≤ 0.66: the fall does not end before 16 min |
| T-R17 | the same, "till 17 min" | first form: Rm(17) ≤ 512 kΩ. Restated: at least 93.5% of the fall from the plateau to the lowest Rm is done at 17 min |
| T-D7 | "often shows a small increase before second cleavage" | first form: D7 ≤ 91 kΩ (a quarter of Rm1 − Rm2). Restated: a quarter of the fall to the lowest Rm (121 kΩ with the calibrated Rm2). No lower bound |

- **T-D3's 15 min is derived, not quoted.** Cleavage runs from the onset of first cleavage (time
  zero) to the onset of second cleavage, J1, declared at 30 min (dLB74 p13). Its second half is
  therefore 15–30 min. The decrease that "often" marks it starts at the minimum, and without it
  Em keeps falling to J1, so either way the minimum is not in the first half.
- **T-D5 and T-R17 read the end time the same way.** "Till 17 min" is read to ±1 min, and "ends"
  as 95% complete on an exponential fall from 7 min: time constants of 3.0 to 3.67 min.
- **Excluded by construction:** D1 and the flat start, set by the declared onset at 7 min, in
  every arm; Em at J1 for A1 × A7a.
- **Fig. 2 is reported beside every point and never judged.**

**For orientation only, the single arms against these criteria (they are not re-judged).** No
single-arm point passes every shape criterion, under either form. The record, A3, A4 and A6 all
fail on three features:
- the Em fall (T-D2): D2 is −3.1 to −5.9 mV;
- the early minimum (T-D3): it comes at 8.0–10.3 min;
- the front-loaded Rm fall (T-D5): D5 is 0.87–0.93.

A1 near its crossing fails T-D2, T-D5 and T-R17. A7a fails T-D3, T-D4 and T-D5 at every α. The
combinations pass only if combining changes these features, so **parking is a likely outcome**.

## The shared mismatches: no arm

The lead asked for an arm here only if a cited measurement supports one, and none does.
- **The back-loaded schedule is left out.** Its 0.04 mm²/min rate was derived by dLB74 from Rm in
  treated eggs (p536): −VM eggs, with growth lasting 7–10 min, and +VM +CCB eggs, with 15–17 min.
  Normal eggs' insertion is measured only by its total at J1 and its onset.
- **No source gives a mechanism for the early Em minimum.** The measured slit widths did not move
  it in A3. BdL73's furrow depths at about 4 and 8 min are already in A7a.

## Freezing and exit

- **Eligible points:** α = 0 and the marked α = 1 in every arm, with A6c through its central fit
  only. A1 × A7a at α 0.5 and 2 are sensitivity points.
- **A point is frozen only if it passes under both forms of T-R17 and T-D7.** It is frozen as
  computed (f, κ, P_old, α, the seal or fit, and the registered inputs), with the run's snapshot.
  A C1 registration is then drafted from the arm file's `held_check_C1_for_frozen_candidates` and
  registered with its rule before C1's first run. J2 stays held.
- **The question is parked in three cases.** If no eligible point passes. If only a sensitivity
  point passes; that point is recorded. Or if the two forms disagree at an eligible point: a false
  park is recoverable, a spent C1 is not. Parked, R-full with the registered inputs stays the
  reference, with its J1 failure and the shared mismatches recorded as unexplained. C1 and J2 stay
  held, and resuming needs new measurements or the user's decision.
- **There is no third round in any case.**
- **Failures:** a point that fails to integrate does not pass; it may be rerun once with Radau.

## Rules and compute

- **Scope:** R-full only, with no engine runs. C1 and J2 stay held: no solution B or C run and no
  DFS74 or J2 quantity, tests included. Cytosolic Na is reported beside dL74's 22.4 ± 1.1 mM.
- **No model change is needed.** Every arm uses fields that already exist and are null by
  default, so R-full's null path stays bit-identical.
- **New code comes only after registration:** the f calibration helper and the groups, beside the
  diagnostic runner. Two unit tests on synthetic cells go with them: one for the helper, and one
  for the combinations' null reduction. With f = 0, A1 × A7a must reproduce A7a alone; with α = 0,
  each arm must reproduce its level-shifters alone.
- **Compute is about 1.3 CPU-hours (up to 2)**, at a peak of about 0.3 GB per process:
  - `j1comb-a1`: the null check and A1 × A7a, about 65 CPU-min.
  - `j1comb-pairs`: the five points of the other arms, about 15 CPU-min.
- **Launch:** each unit through `scripts/run_detached.sh NAME 3G --oom-first --wait-headroom 2G
  --cpus …`, from a clean snapshot of the registered commit, into
  `/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-combination-01/`.
