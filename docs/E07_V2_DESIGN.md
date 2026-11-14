# E07-v2: write, clear, challenge (proposed note, with E15's version-0 lesions)

**Status: PROPOSED, 14 November 2026, for the lead's review with the advisor.** Nothing here
is registered and nothing has run except the definition-time builds of §7. It follows D151:
E07-v2 adopts the write–clear–challenge rules of the partial-reprogramming review, translated
to Cells, drafted after E07-v1's analysis
([review](PAPER_REVIEW_PARTIAL_REPROGRAMMING.md), rank 1; the
[current plan's coupled-renewal gate](CURRENT_PLAN.md#gate-coupled-renewal)). It also carries
E15's version 0, which is E07-v2's arms plus spatial lesions
([E15 note](EXPERIMENT_PATH_PATTERN_RECOVERY.md) §3), scored as generates, maintains and
restores. E07-v1's registered protocol, frozen scorer and judged items are unchanged (D151).

**What it reuses.** E07-v1's world, driver, copy-only null and analysis rules
([E07-v1 design](E07_V1_DESIGN.md); `validation/tissue/e07_v1_*`). v2 changes which cells
are judged, when judging starts, and adds the challenges and lesions.

## 1. Engine models each arm runs (the AGENTS.md milestone rule)

Every arm runs on the 127-cell held-bath sheet of E07-v1 and sheet70. It uses IMEX ARS(2,2,2),
`junction_heat_booking` `trapezoid_nonnegative@1` and the field solver that D147 declares
through `field_solver_choice.declare()`: `capacitive_reduction_gauged_damped_newton@2` for
these sheets, which have no free offsets.

| Arm | Engine models |
| --- | --- |
| Write and clear, no turnover | `resolved_pump_tissue@3` with sheet70's cue populations: the existing sheet70 run, its records and its 120 s snapshots |
| Turnover, retained mark only | `resolved_pump_replacement@1`, which is `resolved_pump_composite@1` with `scheduled_cell_replacement@1` over @3, junction formation `delayed_first_order_junction_formation@1` |
| Turnover plus second cue | the same, with the cue populations scheduled again after clearance |
| No-turnover control, second cue | `resolved_pump_tissue@3` with the cue populations, from the same sheet70 snapshot |
| Turnover plus injected current | `resolved_pump_composite@1` with `[scheduled_cell_replacement@1, electrode_current_injection@1]` |
| No-turnover control, injected current | `resolved_pump_composite@1` with `[electrode_current_injection@1]` |
| Osmotic step (deferred, §8) | `resolved_pump_composite@1` with `[ideal_osmosis_linear_compliance_water@1, scheduled_cell_replacement@2]`, plus a bath step the pump family lacks |
| E15 v0 block refill | `resolved_pump_replacement@1`: isolated templates at one time over a block |
| E15 v0 state lesions | as the second-cue and injected-current arms, applied to a block |

A combination is not qualified by its parts (D143). Each composition above runs as a labelled
development run until a registered protocol judges it.

## 2. What E07-v1 found that shapes v2

Judged execution: `/mnt/workspaces/Cells/e07-v1-judged-20261113-01/`. Its outputs are
`summary.json`, `scores.json` and `runs/*/seed*/outcome.json`. The scorer is
`validation/tissue/e07_v1_score.py`, frozen at `6b6912b` before any judged outcome.

- **The copy rule carries the mark.** In all 30 (a) runs the engine stayed close to its
  paired copy-only null: ΔJ ran from −0.031 to +0.059 and D-loss from 0 to 9.8%. Of 4,853 H
  copies, 3 converted.
  - The erosion classes at s 1.0 come from D-loss, not from ΔJ. Fast k3 was 3 of 3
    erosion with D-loss 5.7–6.8% and ΔJ from −0.031 to +0.044.
  - So a retention claim in v2 keeps v1's paired null. Turnover's own engine contribution
    is small.
- **At s 1.0 the disc was not maintained even with disc donors, in the one run.** The (c)
  control at s 1.0 lost 14 founders and 6 D copies. J was 0.784 at the judged record
  (minimum 0.649).
  - **The losses came in two collective falls**, of 6 founders at 440 s and 8 at 520 s. Most
    were rim cells with 3–4 D neighbours of 6; the rim D copies followed at 710–1850 s
    (`e4-losses.json`).
  - At s 0.6, J was 1 at every record.
  - This is one run per s. v2's challenges therefore run first at s 0.6, and s 1.0 is a
    boundary case.
- **Naive templates erased the mark within about one turnover at every τ run** (40, 120 and
  300 s; v1 ran no isolated newcomers at the literature brackets). The (b) sheets were all H
  at 940–1050 s (s 0.6) and 550–630 s (s 1.0). The conversions of interior newcomers that
  arrived with five or more D neighbours were:
  - at s 0.6: 9/11, 5/10 and 1/7 at τ 40, 120 and 300 s;
  - at s 1.0: 5/7, 5/9 and 2/8.

  tau* was 300 s at both s, from a single draw.
- **The open question for a block refill.** Whether a small block of naive templates inside
  a surviving mark restores is a hypothesis v1 does not answer. Its whole-sheet refills went
  all H even at τ 40 s, where most interior newcomers with D neighbours converted.
- **Coupling after turnover is the law's.** A after the first turnover was 0.200–0.206 in
  fast k1 and 0.146–0.151 in central k1, and 0.609–0.618 within fast k3's first turnover. It
  equals the law over the same records. Weight / A was 0.102–0.106 on D–H junctions and
  0.95–0.96 on like junctions. A challenge that acts through junctions reports the coupling
  it met.
- **The window holds.** There was no refusal and no censor, and the largest osmotic excess
  was 0.122, in central k1 at s 0.6. E1, the numerics gate, passed at 5 ms on the worst-case
  segments, with |ΔVm| at most 5.7 µV.

## 3. The write–clear–challenge rules in Cells

These are rules (a) to (c) of the review, applied to E07's cue, release and turnover assay.

**(a) Clearance is measured, not fixed.**
- **The cue.** sheet70's cue opens a Na leak population (`cue_<i>`, `NALEAK_LAW_ID`) on
  [0.5, 2.5) s. Each population is 9 times its membrane's own Na leak, ten times in all. It
  drives Na entry and depolarisation.
  - Every sheet70 world carries the 37-cell disc's 37 populations.
  - The 19-cell world cues 19 of them.
- **What v1 did.** v1 started 117.5 s after the cue's end, at sheet70's 120 s snapshot.
- **The proposed criterion.** On the no-turnover control's 10 s records, the clearance time
  t_c is the first record from which every cued cell stays within declared rates:
  - its Na amount and its Vm change no faster than the slow drift the window carries (the
    osmotic loading);
  - they stay so to the end of the window.
- **Tolerances.** They are fixed at registration from the sheet70 records, which already
  exist, before any v2 run, and the choice is disclosed.
- **Start of judging.** Turnover and challenges start at the first sheet70 snapshot (120 s
  grid) at or after t_c. No retention claim is made before t_c.

**(b) Classify by the state at release, not by the schedule.**
- **The reference set.** W is the set of cells in D (Vm above the U state) at the cue's end,
  2.5 s.
- **What uses it.** J, D-loss, founders lost and the challenge classes all use W in place of
  the scheduled disc.
- **Reported beside it.** The set in D at t_c. If either set differs from the disc, that
  difference is a result, not an adjustment.

**(c) Score the mark and the function separately.**
- **The retained mark.** J against the paired copy-only null, D-loss and recruitment, with
  v1's run classes and group rule.
- **The functional challenge.** The response to a post-release challenge, by its own rule
  (§4).
- **First, the plan's own measures.** Continued transmissibility (D copies that keep D and
  pass it on through a second turnover) and physiological cost (osmotic loading, pump work
  and material moved per turnover).
- **No pooling.** The outcomes are never pooled into one score.

## 4. The challenges, in D151's order

Each challenge comes after t_c and registers three things.
- **A no-turnover control.** The same challenge on the same world from the same snapshot,
  without replacement.
- **A fit inside the fixed-volume window.** Every judged record falls within 70 min of the
  cue. v1's osmotic flag (10%) and censor (15%) are kept.
- **A check that it is not the mark again.** The response of a fresh D cell is compared with
  that of a long-held D cell under the same challenge. A fresh D cell is a D copy that
  arrived within a declared time; a long-held one is a founder in W never replaced. Both are
  named per world definition, from the schedule, before the run. If they respond alike, the
  challenge reads the present state (attractor-held), not history.

### 4.1 A second cue

- **What.** sheet70's cue populations, scheduled again after t_c, for 2 s, and for 0.5 s,
  pre-screen 7's short cue.
- **Where.**
  - **The written region.** Readouts are the Vm excursion and the return time, fresh
    against long-held D cells.
  - **A naive region next to W.** Readouts are whether cued H cells are written, against the
    no-turnover control, with their D neighbours counted at the cue. That is
    transmissibility read as a function.
- **The world.** sheet70 declares cue populations only on the 37-cell disc's membranes. In
  the 19-cell disc world, ring 3 is therefore a naive region with populations. In the
  37-cell world, populations outside the disc must be added. Held at zero availability until
  the challenge, they leave the state unchanged, and the layout check then covers the
  extended list.
- **Built** (§7): the second cue after replacement has begun is admitted at every stage.

### 4.2 Injected current

- **What.** `electrode_current_injection@1`, one electrode per challenged cell. The carriers
  are the 3 M KCl fractions with M, the sheet's monovalent anion, in place of Cl:
  {K: 0.4912, M: 0.5088}. That mapping is a declared modelling choice.
- **The step.** A hyperpolarising step into declared D cells, singly and as a block. Its
  size is a declared multiple of the flip threshold, measured first in the no-turnover
  control.
- **Readouts.** Whether the cell flips to H, whether it returns, and its return time; fresh
  against long-held.
- **The control.** The no-turnover control runs the same injection.
- **Built** (§7): replacement with injection is admitted in both operator orders.
- **Not with water.** Injection cannot run over water: main refuses `[water, injection@1]`
  for injection's view conflict on volume.

### 4.3 An osmotic step (deferred)

It needs replacement over water, which has landed but is not qualified on this sheet, and a
bath step that the pump family does not have (§8). It is drafted when both exist.

## 5. E15 version 0: lesions on E07-v2's frame

E15's version 0 adds spatial lesions to v2's arms, inside W or across its boundary. Each is
scored three ways (E15 §2).

| Outcome | Test in version 0 |
| --- | --- |
| Generates | The first cue writes W from the naive sheet: sheet70, classified by (b) |
| Maintains | With no lesion, after t_c, W holds over the window. Without turnover, J stays at 1; with turnover, J tracks the paired null and the arm is classed by v1's rules |
| Restores | After the lesion, J against the pre-lesion pattern returns to a declared agreement by a declared time, holds, and beats a paired null |

**The lesions.**
- **Block refills.** A block is a cell and its six neighbours, inside W or across its
  boundary. All its slots are replaced at one time by naive isolated templates, and the
  formation law governs their coupling.
  - Its paired null is the copy-only null with the block's labels set to H.
  - The parser admits one event per slot and time. A dense block at one time is therefore
    several events, not yet built (§8).
- **State lesions.** Two kinds:
  - a hyperpolarising injection into a block inside W, which erases part of the mark;
  - a cue-kind pulse into a naive block outside W, which writes a spurious patch.

  Their paired null is the same run without the lesion, which is passive relaxation.

**The scores.**
- **Two kinds of return.** Same-instance return is the main score: slot-wise, two-sided
  agreement over all original slots. Same-class return, a disc re-forming elsewhere, is
  reported.
- **Where the rebuilding information is held.**
  - Route values are uniform, so slot-held information is absent.
  - The templates are naive.
  - The driver is withdrawn.
  - The only declared source is the surviving neighbours' state. A return is labelled
    neighbour-held.

**The controls** (E15 §2).
- a sham lesion, with zero current or a refill by the slot's own donor copy;
- the lesion without turnover;
- a declared supplied answer, the cue re-applied to the lesion;
- matched appearance with a different history: a recently written disc against a long-held
  one under the same lesion. It separates history-held from attractor-held recovery.

**What v1 suggests, as a hypothesis.** At τ 40 s most interior newcomers with five or more D
neighbours converted, but the whole sheet still went all H. v1 ran no isolated newcomers at
the literature brackets.
- **The hypothesis.** A small interior refill might restore at fast formation and fail at
  the fast or central bracket.
- **The informative negative result.** A mark that is generated and maintained but not
  restored.

Version 0 has no regulatory network, secreted signal or mechanics. The heredity cell's law
set stands in for "the same network" and is labelled so. E15 §3 asks for 1-D chain screens
before the sheet. This note leaves them out, because v2's frame is v1's sheet; they could
come before the lesion arms if the lead wants them.

## 6. Arms, a sketch for review (not registered)

| Block | s | Turnover | Challenge or lesion | Seeds (the run is the unit) |
| --- | --- | --- | --- | --- |
| Mark only | 0.6, 1.0 | fast k1, donor copies, whole sheet, from t_c | none | 4 at s 0.6, 2 at s 1.0 |
| No-turnover controls | 0.6, 1.0 | none | each challenge and lesion | 1 each (deterministic) |
| Second cue | 0.6 (1.0 boundary) | fast k1 | 2 s and 0.5 s; written region and naive region | 4 |
| Injected current | 0.6 | fast k1 | single cell and block, inside W | 4 |
| E15 v0 refill | 0.6 | fast k1 donor copies elsewhere; the block by naive templates. One formation law per run, so the bracket applies to every junction restart. The fast bracket first, then τ 40 and 120 s as v1's ladder | interior block; boundary block | 2–4 |
| E15 v0 state lesion | 0.6 | fast k1 | injection block inside W; cue block outside W | 2–4 |

**Cost.**
- **Per run.** v1 measured 4.2–7.1 ms per 5 ms step on one core, with two units at once. A
  run from t_c ≈ 120 s to 70 min after the cue is about 816,000 steps, or 57–97 min of wall
  time.
- **The table.** It comes to roughly 70–80 runs, about 100 CPU-hours, or two days on CPUs 2
  and 3. A registration would trim it: the lesions could wait for the challenges' result,
  and s 1.0 could be dropped where s 0.6 already answers.

**Numerics.** The challenges add fast transients (a cue's opening, a current step). Like v1's
E1, v2 needs its own gate: 5 ms against 1 ms on the worst-case challenge segment of each
composition, before any judged arm.

## 7. Definition-time builds of the challenge pairings (done)

- **Check.** `validation/tissue/e07_v2_challenge_builds.py`, branch `1bfe041`, run from a clean
  snapshot.
- **Run.** It ran on CPU 3 after the E07-v1 queue, taking 31 s and 0.31 GB.
- **Evidence.** `/mnt/workspaces/Cells/e07-v2-challenge-builds-20261113-01/builds.json`.
- **Base.** E07-v1's sheet world with the a-donor-fast-k1-d37-s1.0 schedule at development
  seed 101: 291 events, the first at 4.015 s.
- **Challenge.** Each challenge runs on [600, 602) s, after replacement has begun.
- **Stages.** Each build passes parse and `check_definition`, binding, `check_steps` at dt,
  and one checked step traced, not compiled. Nothing was stepped.

| Pairing | Identity | Result |
| --- | --- | --- |
| Second cue (sheet70's 37 cue populations) | `resolved_pump_replacement@1` | admitted at every stage |
| Second cue, composite form | `resolved_pump_composite@1`, `[scheduled_cell_replacement@1]` | admitted at every stage |
| Injection after replacement | `[scheduled_cell_replacement@1, electrode_current_injection@1]` | admitted at every stage |
| Injection before replacement | `[electrode_current_injection@1, scheduled_cell_replacement@1]` | admitted at every stage |

The electrode was in cell 63, the disc's centre, at −20 pA, with carriers {K, M}.

**Why injection is admitted beside replacement.**
- Insertion's refusal of operators that book on the declared layout applies only when
  insertion is in the composition.
- Replacement's view fields are routes (channel, membrane and pump), not field inputs.
- So beside replacement, injection books on the declared layout, which replacement also
  reads as declared.

**What the builds do not show.**
- Step-time behaviour is untested. A half-step that removes more of a carrier than a cell
  holds is refused in the step.
- The write cue before replacement is the same declaration with earlier times and was not
  built separately.
- Not built:
  - a dense block refill;
  - a schedule mixing isolated templates and donor copies;
  - one electrode per block cell;
  - the injection-only control.

## 8. Features it needs that do not exist yet

| Need | For | Status |
| --- | --- | --- |
| A bath composition step in the pump family | 4.3, the osmotic step | None found. A search found bath steps only in the older surface families (`core/surface_bath_events_binding.py` and the `*_bath_events` models) |
| Formation parameters per event or per template | a block at one τ beside donor copies at another | Absent. `with_replacement` declares one `junction_formation` block per definition, and neither templates nor events carry one. §6 uses one law per run |
| Replacement over water qualified on the heredity sheet | 4.3 | `scheduled_cell_replacement@2` over `ideal_osmosis_linear_compliance_water@1` landed on 13 November; G2-Q1 covers @1 on held-bath worlds only |
| Injection over water | an injected current with water | Refused: `[water, injection@1]` |
| A dense block refill inside G2-Q1's scope, and a schedule mixing templates and donor copies | §5 refills | Unverified: both need a definition-time build, then a numerics check |
| Removal with a vacancy, an excision operator for the composite | later E15 versions | Absent (E15 §1.7); not needed for version 0 |
| Readouts (validation side): the clearance criterion, W at release, challenge responses, fresh against long-held labels from the replacement generation, pattern metrics and recovery time | every arm | To write. `src/cells/assays/recovery.py` exists as an observer |

None of these is built for this experiment (D144). The bath step and injection over water
are general composite features, each with its own design note (D142) and gate.

## 9. Questions for the lead and the user

1. **What counts as "function" for a Cells cell** (the review's question 3)? This note takes
   the response to a second cue and a current step, compared between fresh and long-held D
   cells.
2. **Start points.** Should v2 start from sheet70's snapshots at the first 120 s point after
   t_c, or run the write phase in every run?
3. **The 37-cell world.** May it add cue populations outside the disc for the naive-region
   challenge, or should that challenge use the 19-cell world only?
4. **E15 version 0.** Is a refill by naive templates the first damage kind, before any
   vacancy? And is the cue re-applied to the lesion acceptable as a labelled supplied answer?
5. **Order.** Should the lesions run after the challenges, or alongside them in one
   registration?

## 10. What this note does not do

- It registers nothing and runs nothing beyond §7's builds.
- It changes neither E07-v1's protocol and scorer nor D145's holds.
- It does not reproduce the reprogramming paper's pipeline (D138).
- It adds no epigenetic, clock or reprogramming model to `src/cells` (D144).
- It does not count a slot-held prepattern as positional information, a collapse to a
  uniform state as recovery, or a return as evidence that the tissue knows its target
  (E15 §5).
