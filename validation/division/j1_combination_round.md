# J1 combination round on R-full: rationale

**Proposed, 13 November 2026: a draft for the lead to register. Nothing here has been run.** The
user approved a combination round ("Lets go on your suggestions"); the lead's brief set its
contents. The machine-readable file is [`j1_combination_round.json`](j1_combination_round.json);
the decisions it asks for are in its `lead_decisions_requested`.

**Why pair the arms.** The single arms ([rationale](j1_diagnostic_arms.md);
[evidence](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-diagnostic-01/)) each did one
thing:
- A1 (a bath-facing fraction f of new membrane) is the only arm that brings Em at J1 into the
  window, but there Em is still falling at J1 and Rm has no late rise.
- A7a (access scaled with furrow depth) is the only arm with a late Rm rise, but it leaves Em at
  J1 at the record's value, because Rm2 pins the access.

This round runs A1 × A7a. It also pairs A7a with the other two level-shifters, the cation-selective
seal (A8) and the −VM fit (A6c). Without those two pairings, "bath-facing membrane is needed"
would stay untested. The round ends either in frozen candidates plus a C1 registration, or in
parking. There is no third diagnostic round.

## Calibration and what is left as the test

| Unknown | Fixed by | Arms |
| --- | --- | --- |
| P_old | Rm1 852 kΩ (dLB74 Table I) | all |
| Access A/L or κ | Rm2 488 kΩ at J1 (dLB74 Table I) | all |
| Bath-facing fraction f | J1 itself: f is fixed where Em at J1 crosses −20.3 mV, the declared calibration the arm file's last lead decision anticipates | A1 × A7a |
| Depth exponent α | No datum, so a curve: 0, 0.5, 1, 2. α = 0 is the registered access; α = 1 (a uniform resistive slit) is marked before any run | all |
| Seal | Nothing: a fixed rule (access D_Cl = 0) | seal × A7a |
| A6c's P_K,new and P_Na/P_K | The −VM arm's own Em2 and Rm2 (two data, two unknowns), taken as recorded in `a6_final.json` | A6c × A7a |

**What is left as the test:**
- **A1 × A7a.** Rm1, Rm2 and J1 are all used up as calibration. The only test in this round is
  the 0–35 min shape against the criteria below. Its out-of-sample test is C1, held until a
  candidate is frozen.
- **Seal × A7a and A6c × A7a.** Neither calibrates anything on J1, so Em at J1 (−21.9 to
  −18.7 mV) is a test, together with the same shape criteria.
- **Cytosolic Na** is reported and never selected on.

## Pass criteria: p531 only

The criteria are dLB74's description of the series (p531, V), turned into numbers and registered
before any run. Fig. 2 is not used, for three reasons:
- **It is one egg**, with no spread to set a tolerance from. p531 describes the series whose
  Table I means calibrate R-full.
- **Its numbers were read after the single-arm runs.** The approximate reading of the trace was
  registered at `cfe0fa3`, before those runs. Its D-values, however, were first computed after
  them (PROGRESS, 12 November), and no digitisation with an uncertainty exists. Targets set from
  them now would be chosen with those results in view.
- **p531 speaks to exactly the features at issue:** how Em falls and when it reaches its minimum,
  how long the Rm fall lasts, and how large the late changes are.

| Criterion | p531 wording | Registered threshold |
| --- | --- | --- |
| T-J1 (pairings without A1) | Table I: −20.3 ± 0.8 mV | Em at J1 in [−21.9, −18.7] mV |
| T-D2 | "in the next 10 min it becomes about 10 mV more negative" | Em(17) − Em(7) in [−12.5, −7.5] mV (rounds to 10 at 5-mV steps) |
| T-D3 | "during the second half of cleavage it often shows a small decrease" | Em minimum at or after 15 min |
| T-D4 | "(1–3 mV)", "often" | Em(J1) − minimum ≤ 3 mV, with no lower bound |
| T-D5 | "drops drastically from 7 till 17 min" | D5 ≤ 0.66: the fall does not end before 16 min |
| T-R17 | the same, "till 17 min" | at least 93.5% of the fall from the plateau to the lowest Rm is done at 17 min (Rm(17) ≤ 512 kΩ if there is no late rise) |
| T-D7 | "often shows a small increase before second cleavage" | D7 ≤ a quarter of the fall (≤ 121 kΩ with the calibrated Rm2), with no lower bound |

- **How T-D5 and T-R17 read the end time.** "Till 17 min" is read to ±1 min, and "ends" is read
  as 95% complete on an exponential fall from 7 min: time constants of 3.0 to 3.67 min.
- **Fig. 2 is reported beside every point and never judged.** In its own terms it passes every
  shape criterion, with D3 and D7 at their boundaries. Its Em at second cleavage, about −17 mV,
  belongs to one egg and is not compared with T-J1. That check led the drafter to state T-R17
  and T-D7 relative to the fall to the lowest Rm, as p531 describes it, rather than to Rm2.
- **Disclosure.** The drafter knew the single-arm results while converting the wording; the lead
  should review the thresholds with that in mind.
- **By construction, excluded in every arm:** D1 and the flat start, both set by the declared
  onset at 7 min. Also excluded: Em at J1 for A1 × A7a.

**For orientation only, the single arms against these criteria (they are not re-judged).** No
single-arm point passes every shape criterion. The record, A3, A4 and A6 all fail on the Em
fall, the early minimum and the front-loaded Rm fall:
- T-D2: D2 is −3.1 to −5.9 mV.
- T-D3: the minimum comes at 8.0–10.3 min.
- T-D5: D5 is 0.87–0.93.

A1 near its crossing fails T-D2, T-D5 and T-R17. A7a fails T-D3, T-D4 and T-D5 at every α. The
pairings pass only if combining the arms changes these features, so **parking is a likely
outcome**.

## The shared mismatches: no arm proposed

The lead asked for an arm here only if a cited measurement supports one, and none does.
- **The back-loaded schedule is the nearest candidate, but it does not measure normal eggs.** It
  is the registered schedule of 0.04 mm²/min for 10 min, an in-band member. That rate was derived
  by dLB74 from Rm in treated eggs (p536): −VM eggs, with growth lasting 7–10 min, and +VM +CCB
  eggs, with 15–17 min. Normal eggs' insertion is measured only by its total at J1 and its onset.
  BdL73 does say that −VM eggs "show a reduced rate of membrane growth" (p100, found in the text
  extraction), but not relative to what, so nothing here rests on it.
- **No source gives a mechanism for the early Em minimum.** The measured slit widths did not move
  it in A3. BdL73's furrow depths at about 4 and 8 min are already in A7a.
- **K83's growing outward current reflects more new membrane appearing, not a schedule.** It was
  measured with the fertilization envelope removed.

The back-loaded schedule can still be added if the lead wants it: A1 × A7a on that schedule, 4
points, about 60 CPU-min, declared as unsupported for normal eggs.

## Freezing and exit

- **Eligible points:** α = 0 (the registered access) and α = 1 (marked) in each pairing; for A6c,
  the central fit only. Points at α = 0.5 or 2, and A6c's one-at-a-time fits, are sensitivity.
  They are reported and never frozen.
- **A passing eligible point is frozen as computed:** f, κ, P_old, α, the seal or fit, and the
  registered inputs, with the run's snapshot. A C1 registration is then drafted from the arm
  file's `held_check_C1_for_frozen_candidates` and registered with its rule before C1's first
  run. J2 stays held.
- **If no eligible point passes, the question is parked.** R-full with the registered inputs
  stays the reference, and its J1 failure and the shared mismatches are recorded as unexplained.
  C1 and J2 stay held, and resuming needs new measurements or the user's decision.
- **Failures and missing crossings.** A point that fails to integrate is recorded as failed and
  does not pass; it may be rerun once with Radau at rtol 1e-10. An α with no J1 crossing for f
  yields no candidate.

## Rules and compute

- **Scope:** R-full only, with no engine runs. C1 and J2 stay held: no solution B or C run and no
  DFS74 or J2 quantity, tests included. Cytosolic Na is reported beside dL74's 22.4 ± 1.1 mM.
- **No model change is needed.** Every arm uses fields that already exist and are null by
  default (`bath_fraction`, `access_shape`, `new_permeability`, `access_selectivity`). R-full's
  null path therefore stays bit-identical; the existing null-reproduction tests remain the guard.
- **New code comes only after registration:** the f calibration helper and this round's groups,
  beside the diagnostic runner. Two unit tests on synthetic cells go with them: one for the
  helper, and one for the combined path's null reduction. The pairings have never run together,
  so with f = 0 A1 × A7a must reproduce A7a alone, and with α = 0 each pairing must reproduce its
  level-shifter alone.
- **Compute is about 2.1 CPU-hours (up to 3)**, at a peak of about 0.3 GB per process:
  - `j1comb-a1`: the null check and A1 × A7a, about 65 CPU-min, at about 15 CPU-min per
    f-calibrated point.
  - `j1comb-pairs`: seal × A7a and A6c × A7a, 25 points, about 60 CPU-min.
- **Launch:** each unit through `scripts/run_detached.sh NAME 3G --oom-first --wait-headroom 2G
  --cpus …`, from a clean snapshot of the registered commit, into
  `/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-combination-01/`.
