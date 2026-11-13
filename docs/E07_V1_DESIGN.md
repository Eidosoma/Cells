# E07-v1 renewal stage: donor copies with an isolated boundary set

**Status: registered by the lead on main (13 November 2026), before any engine run.** The
lead's decisions are in the protocol's `lead_decisions_taken`. The user chose option (c) on 13 November:
donor copies are the main route, and isolated newcomers with fast junction formation form
a boundary set. The design builds on the literature-rule turnover pre-screen
([Progress](../PROGRESS.md); evidence
`/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/`). The parent design is
[HEREDITY_FIRST_EXPERIMENT.md](HEREDITY_FIRST_EXPERIMENT.md).

## 1. What a donor copy may carry (D139)

D139, as written: "'Inherit' is excluded. No junction gate state carries across a
replacement." Donor copies are "a different heredity claim, an inheritance route for the
written state, and its arms are labelled as such." The engine
(`scheduled_cell_replacement@1`, [CELL_REPLACEMENT.md](CELL_REPLACEMENT.md)) implements
this as follows.

| A donor-copy newcomer gets | Not carried |
| --- | --- |
| The donor's amounts of every declared species at the event time, read before any event at that time (the supply ledger books them; the donor keeps its contents) | Junction gate state and junction abundance: every junction at the slot restarts the formation law (A0, lag, tau, gate at arrival). This is the excluded "inherit" |
| The donor's channel gates, matched by channel law | Route values (channel, leak and pump coefficients): the slot's own, unless a route-only template declares them |
| | Volume and fixed-charge background: the parser requires the donor's to equal the slot's |

So the written state can pass only through the copied composition and membrane channel
gates. Coupling to the neighbours is always built anew.

## 2. Donor-copy content: composite v2 §2, decision 4

The decision: [Composite v2](PUMP_COMPOSITE_V2_DESIGN.md) §2 (water plus replacement,
`scheduled_cell_replacement@2`) proposes that newcomers keep the slot's declared
impermeant content. Decision 4 leaves this open until the renewal assay asks. E07-v1 asks
now: does a donor copy get the slot's declared impermeant content, or the donor's?

**Impermeant content in E07-v1's worlds.** The pump family has two kinds.
- **The charged impermeant species P.** It is an amount, so it is among the copied
  amounts.
- **Water's neutral `impermeant_amount_fmol`.** It is a per-cell declaration, not state,
  and is absent at fixed volume.

In the held-bath sheets, every cell, the H template and every copy carry P = 135 mM × V0 =
101.3205 fmol. No route carries P: its membrane and junction permeabilities are 0, NaV1.2
and Kir2.1 carry Na and K only, and the pump moves Na and K. The pre-screen's checkpoints
confirm this:
- P's amount increment is exactly 0 in every cell of every arm;
- every supplied and every removed P is 101.3205 fmol per event.

There are no neutral impermeants.

**Settled for donor copies: the newcomer gets the slot's declared impermeant content.**
- **In E07-v1's worlds it is the same number as the donor's,** so the choice changes no
  trajectory, ledger or readout. `scheduled_cell_replacement@1`'s copy of the donor's P
  is exactly the slot's declared P.
- **For `@2` (later, with §2's code):** a donor whose impermeant content differs from the
  slot's declared content is refused when the definition is checked.
  - It is not mixed. The donor's permeant amounts with the slot's impermeant content
    would be a state that no cell had.
  - A different content needs water-owned impermeant state, which §2 names as a later
    extension.
- **E07-v1's driver checks this equality on every definition before a run.** It is a
  validation check, not an engine change.

**What sets the inherited loading behind the 95-minute censor.** The permeant ions do,
not the impermeant content.
- **D cells load K and the anion M in a fixed volume.** sheet70: K 136 → 146 mM and
  M 7 → 22 mM by 70 min. That is about 2% osmotic excess per 10 min of D residence: 10%
  at 56–58 min, and 15% by extrapolation at about 97 min after the cue.
- **A copy of a D cell carries that loading on.** A D lineage therefore keeps loading
  from the cue, through any number of replacements. In the pre-screen's donor arm at
  central k1, s 1.0, the excess reached 14.4% at 87 min after the cue, and flags came at
  56–58 min.
- **An isolated template resets the loading to 0.**
- **The 95-minute budget therefore bounds the time since the cue, not the number of
  turnovers.** Stage B starts 2 min after the cue (§3), and every arm is judged by 70 min
  after it, the end of the no-turnover control. Loading then stays at or below about 12%
  (sheet70: 11.7–12.1% at 70 min), so no planned run reaches the censor.

**Under water (§2, later).** The loading becomes swelling: the W1 water arms reached
1.03–1.06 V0 by 70 min. What matters for a donor copy then is its volume, which is not
decision 4.
- The donor's volume with the donor's amounts is an exact state copy.
- The slot's declared volume with the donor's amounts starts the newcomer hyperosmotic,
  and it swells back.

§2's code has to choose between these. This note proposes the donor's volume for donor
copies, since a copy is a copy of state, and leaves the decision to §2.

**Dated note (13 November 2026).** §2 is built and landed: `scheduled_cell_replacement@2`,
water plus replacement. A donor copy takes the donor's volume
([composite v2 decision 10](PUMP_COMPOSITE_V2_DESIGN.md)). E07-v1 itself is unchanged: it stays
registered at fixed volume (D151), and any run under water belongs to a later version, on @2.

## 3. Design

**Questions.** The three sets are labelled and kept apart.
- **(a) Inheritance route (the test).** Cells across the sheet are replaced by copies of
  a neighbour, drawn blind to its state: division-born newcomers, D139's donor copy. Does
  bioelectric coupling make the written D state pass more or less faithfully than neutral
  copying? The answer is each run's deviation from the copy-only null (§4) on the same
  schedule and donor draws.
- **(b) Boundary set, threshold-finding.** At the test arms' turnover, how fast must an
  isolated newcomer's junctions form for it to be recruited into the written state?
  - Its tau values, 40 s to 5 min, lie below the literature's 15–60 min.
  - The 40 s point was seen only after the pre-screen's predictions were frozen.
  - So it looks for the formation-time boundary of recruitment and tests no literature
    value.
  - With one seed per tau and s, the boundary it finds, tau*, is a single draw.
- **(c) Controls.**
  - Disc slots with disc donors: they pass B1 by construction under copying, so they
    isolate the electrical loss of D copies.
  - No turnover: sheet70, the same world from the same start, held for 70 min after the
    cue. It bounds every judged record (below).
  - The pre-screen's literature-rule isolated arms: tau 15–60 min, no recruitment in
    317 newcomers. They are evidence and are not rerun.

**World and start.** As in the pre-screen:
- the held-bath 127-cell sheet, with E07 voltage-gated junctions at coupling s and
  homogeneous heredity cells;
- the five discs that held for 70 min without turnover in sheet70: 37 cells at s 1.0,
  0.6 and 0.3, and 19 cells at s 0.6 and 0.3;
- the start is sheet70's state at 120 s, 2 min after the cue, declared as the initial
  state. The rebuilt layout equals sheet70's, and 60 s without events reproduces its
  records to under 1e-14 V (pre-screen `importcheck/`).

**Stage B starts 2 min after the cue.** For these discs, stage A's retention is sheet70
itself. A retention phase before turnover would spend the fixed-volume budget (§2).

**Every arm is judged within the control's window, by 70 min after the cue.**

| Arm group | Judged at | Turnovers | Run length |
| --- | --- | --- | --- |
| (a) fast k1, (b), (c) | the second turnover's completion | 2 | 39 min (ends 41 min after the cue) |
| (a) central k1 | the control's end, 70 min after the cue | 1.7 | 68 min |
| (a) fast k3 | the first turnover's completion, 53 min after the cue | 1 | 68 min (to the control's end; the rest is reported, not judged) |

**Why the central arms are judged at 70 min,** rather than extending the control to
87 min with two new runs:
- sheet70 already covers the window, so no new control is needed;
- no run can reach the osmotic censor by then (loading of about 12% at most), so the plan
  has no censored run to bias E3;
- every founder has been replaced once by the first turnover (42 min after the cue), and
  about 70% of the second turnover is done;
- each central run takes about 26 min less wall time.

The cost: the central arms do not complete a second turnover (§8).

**Engine and numerics.**
- `resolved_pump_replacement@1`: the composite `resolved_pump_composite@1` with
  `scheduled_cell_replacement@1` over `resolved_pump_tissue@3`.
- IMEX ARS(2,2,2), `junction_heat_booking` `trapezoid_nonnegative@1`, fixed volume.
- **Field solver version 2.** D147 applies, but the sheets have no free offsets
  (`offsets.json`: 0 in all five, and `declare(auto)` keeps version 2). The driver still
  builds every definition through `field_solver_choice.declare()`.
- **dt 5 ms.** The pre-screen's check gave 5 ms against 1 ms within 9 µV. G2-Q1's scope
  is 1 ms, so E1 (§6) is a gate before any judged arm, on the worst case: the densest
  events and the fastest formation.

**Replacement, blind to state.**
- **Scope:** every cell of the sheet in (a) and (b), not only the written cells, because
  replacing only the disc is itself a choice by state. In the control, the disc's cells
  only.
- **Order:** oldest first.
  - The founders share one age, so a seeded permutation orders them.
  - Each slot is then replaced every R, with events at (j + 1/2) R / N on the dt grid.
  - N is 127, so whole-sheet events come every 8.0 s at fast k1. That is about three
    times denser than the pre-screen's 27.6 s.
- **Residence:** R = k (lag + tau): 17 min (fast k1), 40 min (central k1), 51 min
  (fast k3). (b) keeps R at 17 min.
- **Donor rule:**
  - (a): a junction neighbour of the slot, drawn uniformly and blind to its state (six
    neighbours inside the sheet, three or four at its edge);
  - control: a uniformly drawn disc neighbour.
- **Seeds:** replicate r draws the permutation from `default_rng([20261113, 0, r])` and
  the donors, one per event in event order, from `default_rng([20261113, 1, r])`.
  Replicate r is therefore the same schedule on every disc and s.
- **Newcomer content:** §1–§2. The driver checks that every donor's P equals the slot's
  declared P.
- **Formation (A0 0, `law_open`):**

  | Arms | Lag | Tau | Basis |
  | --- | --- | --- | --- |
  | (a) fast (k1, k3) and control | 2 min | 15 min | The division-born fast arm (Boassa 2010) |
  | (a) central | 10 min | 30 min | The documented default |
  | (b) | 2 tau / 15 (the fast shape) | 40, 120 and 300 s | Threshold-finding |

**Junction abundance under turnover: k1 is weakly coupled.** A junction restarts
whenever either of its cells is replaced. The formation law's time-averaged abundance A,
from each run's own schedule (`law_junction_abundance` in `null-v3.json`):

| Arm group | A in the first turnover | A after it, to the judged record |
| --- | --- | --- |
| (a) fast k1 | 0.42–0.43 (founder junctions start at 1) | 0.20 |
| (a) central k1 | 0.39 | 0.15 |
| (a) fast k3 | 0.61–0.62 (judged there; about 0.5 later, from the law) | not judged |
| (b) tau 40, 120 and 300 s | 0.92, 0.79, 0.62 | 0.91, 0.76, 0.52 |
| (c) disc-only | 0.42 inside the disc, 0.63 across its edge | 0.20 inside, 0.33 across |

- **At k1, after the first turnover, the junctions carry a fifth or less of their
  declared conductance before the voltage gate.** The nominal s overstates the coupling
  about fivefold. Neutral copying at k1 and s 0.6 would describe nearly uncoupled cells.
- **The pre-screen's erosion grew with k** (engine minus null −0.11, −0.70 and −0.95 at
  k1, k3 and k10), as A grows. So the fast k3 arms at s 0.6 and 1.0 are added.
  - They are judged after one turnover. Two would end 104 min after the cue, beyond the
    control and the fixed-volume budget.
  - k10 is not judged.
- **Every run reports its junction weight** (E6), so each class is read with its
  coupling.

**Stop rules** (as in the pre-screen):
- the planned end;
- one minute after the first of two consecutive 10 s records with no D cell anywhere.
  This is absorbing: copies of H cells and H templates cannot create D;
- the first record with osmotic excess above 15% against the H start in any cell (the
  censor). A censored run is judged at its last valid record (§6);
- a refusal: a step the model refuses, or a failed device check on any row.

**Execution.**
- **Memory:**
  - every unit runs through `scripts/run_detached.sh`, capped at 6G;
  - the arm process ends after writing records, checkpoint and result, and the analysis
    runs as its own process. The pre-screen's in-process analysis peaked at 4.8–5.2 GB;
  - at most two E07 units run at once, and only one while the L4 gap's 8G dispatch test
    is scheduled (the slice cap is 15G).
- **Source:** one clean snapshot of main is taken after the S3 ledger fix (`d020c3b`) has
  landed, with the engine-run driver. E1 and every judged arm run from it.

## 4. The copy-only null

`validation/tissue/e07_v1_turnover.py null` runs without the engine.
- **Each run copies labels along its own schedule and donor draws.** A newcomer takes its
  donor's D/H label at the event time, read before any event at that time (the engine's
  rule), or H when it is isolated.
- **Records are the engine arms' own:** every 10 s, each taken before any event at its
  time. J is the Jaccard of the D set against the disc over the whole sheet.
- **The engine's result is the deviation from it,** paired on the same draws:
  - ΔJ at the judged record;
  - D copies lost to H;
  - H copies and isolated newcomers converted;
  - founders lost.

  Evidence: `/mnt/workspaces/Cells/e07-v1-design-20261113-01/null-v3.json` (2,000 seeds
  per design; every registered seed's paired series, judged-record values and law
  abundance).

**Checked against the pre-screen.** The null was run on each pre-screen arm's own events.
- **Where the engine lost no D carrier and converted no newcomer, the two J series are
  identical record by record.** That covers all 235 records of the donor arms at s 0.3
  (37 and 19 cells) and at 37 cells, s 0.6, and every record of the isolated arms at
  s 0.3.
- **Everywhere else the engine lies below the null.** Engine minus null at the end:

  | Pre-screen donor arm (37 cells, s 1.0) | Engine − null |
  | --- | --- |
  | fast k1 | −0.11 |
  | central k1 | −0.14 |
  | k3 | −0.70 |
  | k10 | −0.95 |

- **D copies did not fall even in H-rich neighbourhoods.** At s 0.3 and 0.6, none of the
  164 D copies was lost (82 at each s), including 12 that arrived with four or five H
  neighbours. At s 1.0, losses came in collective falls, not from a copy's own
  neighbourhood.

**The null at each design's judged record (2,000 seeds):**

| Design | Disc | J at the judged record, median (5–95%) | P(B1) | Max D outside the disc, median |
| --- | --- | --- | --- | --- |
| (a) fast k1 (2nd turnover) | 37 | 0.50 (0.35–0.66) | 0 | 14 |
| | 19 | 0.39 (0.17–0.59) | 0 | 10 |
| (a) central k1 (70 min after the cue) | 37 | 0.54 (0.39–0.68) | not applicable (fewer than two turnovers) | 12 |
| | 19 | 0.43 (0.22–0.63) | not applicable | 8 |
| (a) fast k3 (1st turnover) | 37 | 0.64 (0.52–0.76) | not applicable | 10 |
| | 19 | 0.54 (0.36–0.71) | not applicable | 7 |
| (c) disc slots, disc donors | 37, 19 | 1 | 1 | 0 |
| (b) isolated templates | 37 | 0 | 0 | 0 |
| The pre-screen's design (disc slots, state-blind donors) | 37 | 0.57 (0.35–0.78) | 0.011 | 0 |
| | 19 | 0.42 (0.16–0.74) | 0.005 | 0 |

**What the null means for the design:**
- **Copying alone cannot pass B1 with state-blind donors:** 0 of 2,000 seeds.
- **The expected D count is conserved,** but D drifts and spreads beyond the disc. A
  median of 10–14 D cells lie outside it at some point.
  - This is copying, not physics, so D outside the disc is never a failure (§6).
- **Seed variance is large.** For example, the registered 19-cell seeds end fast k1 at
  J 0.25, 0.65, 0.46 and 0.44. Every engine run is judged against its own paired null.

## 5. Arms, seeds and budget

**Seeds are weighted towards s 1.0,** where an effect is predicted. s 0.3 is predicted to
equal the null exactly, so a single deviation there falsifies it.

| Set | Arms | Seeds | Runs | Model time per run |
| --- | --- | --- | --- | --- |
| (a) fast k1 | 37 cells at s 1.0 | 8 | 8 | 39 min |
| | 37 and 19 cells at s 0.6 | 4 each | 8 | 39 min |
| | 37 and 19 cells at s 0.3 | 2 each | 4 | 39 min |
| (a) central k1 | 37 cells at s 1.0 and 0.6 | 2 each | 4 | 68 min |
| (a) fast k3 | 37 cells at s 1.0 and 0.6 | 3 each | 6 | 68 min |
| (b) tau 40, 120 and 300 s | 37 cells at s 1.0 and 0.6 | 1 | 6 | at most 39 min |
| (c) disc-only | 37 cells at s 1.0 and 0.6 | 1 | 2 | 39 min |

In (a) that is 13 runs at s 1.0, 13 at s 0.6 and 4 at s 0.3.

**Cost on CPU** (one world per process; 7.7 ms per step with two units, 5.8 ms with one):
- a 39-min run takes about 60 min of wall time and a 68-min run about 105 min;
- E1 is three segments at 1 ms and 5 ms, about 3.1 core-hours;
- the out-of-process analyses take about 1 core-hour in all.

| Fits | Set | Core-hours | Wall on two units |
| --- | --- | --- | --- |
| Minimal | (a) fast k1: 4 seeds at s 1.0, 2 per disc at s 0.6, 1 per disc at s 0.3; central 1 each; k3 2 each; (b) at s 0.6 only; (c); E1 | about 29 | about 14.5 h |
| Proposed | the table above, with E1 | about 50 | about 25 h |
| Fuller | the proposed set plus 16 more fast k1 runs (8 at s 1.0, 4 per disc at s 0.6) | about 66 | about 33 h |

Whenever the L4 gap's test forces one unit at a time, the wall time grows accordingly.

## 6. Readouts, analysis rules and the proposed judged items

**The unit of analysis is the run.** Copies within a run are not independent: at s 1.0,
the pre-screen's losses came as collective falls. Every judgment is made on run-level
values, and nothing is pooled per copy.

**Each run is classified at its judged record.** It is compared with its paired null at
the same record. δ = 2 / N_disc: 0.054 for 37 cells and 0.105 for 19 cells.

| Readout | Definition |
| --- | --- |
| ΔJ | J_engine − J_null |
| D-loss fraction | D copies that fell to H before their own replacement, over the D copies arrived |
| Recruitment fraction | H copies converted to D, over the H copies arrived |

| Run class | Rule |
| --- | --- |
| Neutral | \|ΔJ\| ≤ δ, D-loss ≤ 2% and recruitment ≤ 2% |
| Erosion | ΔJ < −δ or D-loss > 5%, and not recruitment |
| Recruitment | ΔJ > +δ or recruitment > 5%, and not erosion |
| Mixed | both the erosion and the recruitment conditions hold |
| Small bias | anything else |

**Each arm group at each s.** An arm group is fast k1, central k1 or fast k3. At a given
s it pools its discs.
- **A class holds** when at least two thirds of the group's runs at that s are in it.
  For a group of two runs, both must be.
- **Otherwise the group is split at that s.** Every run is reported with its class, and
  no class is claimed for that s.

**Censored runs are never dropped.** A run that reaches the censor is judged at its last
valid record: the last 10 s record with osmotic excess at or below 15% in every cell. It
is judged against its paired null at that record, and its truncation is reported. Runs
that keep the most D load the most, so dropping censored runs would bias E3 towards
erosion. (No planned run is expected to reach the censor: §2.)

**Rules carried over from the pre-screen:**

| Pre-screen rule | In E07-v1-B |
| --- | --- |
| "No D outside the disc", with D outside checked against 0 | Dropped. Copying spreads D (null median of 10–14 cells at most). D outside is reported against the paired null. No stop, validity or prediction rule treats it as a failure |
| All-H stop (absorbing) | Kept, over the whole sheet |
| Osmotic censor at 15% | Kept; censored runs are judged at the last valid record and never dropped |
| Collective loss as 5 cells in 10 s (post hoc) | Reported descriptively; no rule uses it |
| B1 as the criterion | Reported beside the null's P(B1); not decisive |
| J over the whole sheet (the union) | Kept; judged against the null |
| Analysis inside the arm process | Moved out of process (memory) |
| Disc-only replacement | Replaced by whole-sheet replacement in (a) and (b); kept only in the control |

**Items:**
- **E1, numerics gate (before any judged arm), on the worst case.** The pre-screen's
  1 ms / 5 ms comparison on E07-v1's own definitions, judged by the same criteria
  (`numerics/criteria.json` of the pre-screen). Three segments:
  - (a) fast k1 at 37 cells, s 1.0, seed 1: the first 600 s, with events every 8.0 s;
  - (b) tau 40 s at 37 cells, at s 1.0 and at s 0.6, seed 1: the first 300 s each.

  If it passes, the arms run at 5 ms. If not, they run at 1 ms with the minimal set.
- **E2, validity.** No refusal and no failed device check in any judged run. Every
  definition passes the driver's checks: P equality, D147's `declare()`, and a layout
  equal to sheet70's. D outside the disc never counts against validity.
- **E3, (a): every run's class, and each arm group's class at each s,** by the rules
  above.
- **E4, control (c).** J = 1 at every record, with no D copy and no founder lost. Any loss
  is reported with its time and neighbourhood.
- **E5, (b) threshold-finding** (reported, with no pass or fail):
  - per tau and s, the isolated newcomers converted, as a fraction of those that arrived
    with five or more D neighbours;
  - ΔJ against the null, whose J is 0 once every founder has been replaced;
  - tau*, the largest ladder tau at which at least one interior newcomer converts. It is
    a single draw.
- **E6, junction weight per run** (reported, qualifying E3–E5). Every junction's abundance
  A and weight A × gate, time-averaged to the judged record and by junction class (D–D,
  D–H, H–H at each record), beside the formation law's A from the schedule. A neutral
  run is read as "neutral at low effective coupling" when its mean weight is well below
  the nominal.
- **B1** (J ≥ 0.8 through two turnovers) is reported for the fast k1, (b) and (c) runs,
  beside the null's P(B1).

## 7. Predictions (written before any E07-v1 engine run)

Item by item, with ranges, in
[`validation/tissue/e07_v1_protocol.json`](../validation/tissue/e07_v1_protocol.json)
(PROPOSED). Their bases are the pre-screen, its opportunity analysis, the stress
segment N2, this null and the law's abundance.

| Item | Prediction |
| --- | --- |
| E1 | Passes (about 10 µV and 3e-6 or less) |
| E3, fast k1, s 0.3 (4 runs) | Neutral in all 4; ΔJ = 0 at every record in at least 3 |
| E3, fast k1, s 0.6 (8 runs) | Neutral holds (at least 6 of 8), at low effective coupling (E6) |
| E3, fast k1, s 1.0 (8 runs) | Erosion holds (at least 6 of 8): ΔJ from −0.35 to −0.05, D-loss 5–25%; the sheet all H in at most 2 |
| E3, central k1 (2 + 2 runs) | Erosion at s 1.0 (both runs); neutral at s 0.6 (both) |
| E3, fast k3, s 1.0 (3 runs) | Erosion in all 3, stronger than at k1: ΔJ after the first turnover from −0.6 to −0.1; the sheet all H by 70 min after the cue in at least 1 |
| E3, fast k3, s 0.6 (3 runs) | Erosion holds (at least 2 of 3): ΔJ from −0.4 to −0.05 |
| E3, recruitment | No H copy converts in any (a) run |
| E4 (control) | J = 1 throughout at s 0.6. At s 1.0, J at least 0.9 after the second turnover, with no collective loss (low confidence) |
| E5, s 0.6 | Recruitment falls with tau: at least 40% of interior newcomers arriving with ≥ 5 D neighbours at 40 s, at least 20% at 120 s, at most 20% at 300 s; tau* at least 120 s (a single draw) |
| E5, s 1.0 | All H within the first turnover at every tau; recruitment, if any, only at 40 s and early |
| E6 | Mean weight after the first turnover: about A on D–D and H–H junctions and about 0.1 A on D–H junctions (gate near its minimum), with A as the law gives (0.20 fast k1, 0.15 central k1; about 0.6 in fast k3's first turnover) |
| Validity | No refusal, no failed device check, no censor; at most about 12.5% excess by 70 min after the cue |
| B1 | Fails in every fast k1 and (b) run; passes in (c) at s 0.6 |

## 8. Limits

- **Coupling under turnover.** k1 is a weakly coupled regime: A is about 0.15–0.20 after
  the first turnover.
  - k3 is judged over one turnover only, and k10 not at all.
  - The central arms are judged at 1.7 turnovers.
- **Fixed volume.** Replacement over water waits for §2's code, which is held until S3's
  fix and first round have landed. Every judged record is within 70 min of the cue.
- **One world family.** Homogeneous held-bath sheets, one formation shape and one
  neighbour rule (uniform). Held baths supply K without limit.
- **Donor copies do not halve the donor** (there is no growth), and turnover is uniform:
  no extrusion by age or stress.
- **One seed in (b),** so tau* is a single draw.
- **Scale.** The 127-cell sheet only; the full tissue needs GH200 or a long-time method.
- **Step.** 5 ms lies outside G2-Q1's 1 ms scope, hence E1 on the worst case.
