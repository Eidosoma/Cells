# E07-v1 renewal stage: donor copies with an isolated boundary set

**Status: PROPOSED (13 November 2026), not registered.** No engine run belongs to this
design until the lead registers its protocol. The user chose option (c) on 13 November:
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
  turnovers.** Stage B starts 2 min after the cue (§3). Two turnovers then end 41 min
  after the cue at fast k1 and 87 min after it at central k1.

**Under water (§2, later).** The loading becomes swelling: the W1 water arms reached
1.03–1.06 V0 by 70 min. What matters for a donor copy then is its volume, which is not
decision 4.
- The donor's volume with the donor's amounts is an exact state copy.
- The slot's declared volume with the donor's amounts starts the newcomer hyperosmotic,
  and it swells back.

§2's code has to choose between these. This note proposes the donor's volume for donor
copies, since a copy is a copy of state, and leaves the decision to §2.

## 3. Design

**Questions.** The three sets are labelled and kept apart.
- **(a) Inheritance route (the test).** Cells across the sheet are replaced by copies of
  a neighbour, drawn blind to its state: division-born newcomers, D139's donor copy. Does
  bioelectric coupling make the written D state pass more or less faithfully than neutral
  copying? The answer is the engine's deviation from the copy-only null (§4) for the same
  schedule and donor draws.
- **(b) Boundary set, threshold-finding.** At the test arms' turnover, how fast must an
  isolated newcomer's junctions form for it to be recruited into the written state?
  - Its tau values, 40 s to 5 min, lie below the literature's 15–60 min.
  - The 40 s point was seen only after the pre-screen's predictions were frozen.
  - So it looks for the formation-time boundary of recruitment and tests no literature
    value.
- **(c) Controls.**
  - Disc slots with disc donors: they pass B1 by construction under copying, so they
    isolate the electrical loss of D copies.
  - No turnover: sheet70, the same world from the same start, held for 70 min.
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

**Engine and numerics.**
- `resolved_pump_replacement@1`: the composite `resolved_pump_composite@1` with
  `scheduled_cell_replacement@1` over `resolved_pump_tissue@3`.
- IMEX ARS(2,2,2), `junction_heat_booking` `trapezoid_nonnegative@1`, fixed volume.
- **Field solver version 2.** D147 applies, but the sheets have no free offsets
  (`offsets.json`: 0 in all five, and `declare(auto)` keeps version 2). The driver still
  builds every definition through `field_solver_choice.declare()`.
- **dt 5 ms.** In the pre-screen's check (segments with events and formation), 5 ms
  matched 1 ms within 9 µV and 2.3e-6 in amounts, with identical D sets. G2-Q1's
  qualified scope is 1 ms, so the protocol puts a numerics gate (E1) before the judged
  arms.

**Replacement, blind to state.**
- **Scope:** every cell of the sheet in (a) and (b), not only the written cells, because
  replacing only the disc is itself a choice by state. In the control, the disc's cells
  only.
- **Order:** oldest first.
  - The founders share one age, so a seeded permutation orders them.
  - Each slot is then replaced every R, with events at (j + 1/2) R / N on the dt grid.
  - N is 127 in (a) and (b), 37 or 19 in the control.
- **Residence:** R = k (lag + tau) with k = 1: 17 min in the fast bracket, 40 min in the
  central one. (b) keeps R at 17 min.
- **Each run** lasts two full turnovers plus 5 min: 39 min (fast) or 85 min (central).
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
  | (a) fast and control | 2 min | 15 min | The division-born fast arm (Boassa 2010) |
  | (a) central | 10 min | 30 min | The documented default |
  | (b) | 2 tau / 15 (the fast shape) | 40, 120 and 300 s | Threshold-finding |

**Stop rules** (as in the pre-screen):
- the planned end;
- one minute after the first of two consecutive 10 s records with no D cell anywhere.
  This is absorbing: copies of H cells and H templates cannot create D;
- the first record with osmotic excess above 15% against the H start in any cell (the
  censor);
- a refusal: a step the model refuses, or a failed device check on any row.

## 4. The copy-only null

`validation/tissue/e07_v1_turnover.py null` runs without the engine.
- **Each run copies labels along its own schedule and donor draws.** A newcomer takes its
  donor's D/H label at the event time, read before any event at that time (the engine's
  rule), or H when it is isolated.
- **Records are the engine arms' own:** every 10 s, each taken before any event at its
  time. J is the Jaccard of the D set against the disc over the whole sheet.
- **The engine's result is the deviation from it,** paired on the same draws:
  - ΔJ(t);
  - D copies lost to H;
  - H copies and isolated newcomers converted;
  - founders lost.

  Evidence: `/mnt/workspaces/Cells/e07-v1-design-20261113-01/null-v2.json` (2,000 seeds
  per design, plus every registered seed's paired series).

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

- **This also confirms the pre-screen's reading:** there, inheritance at s ≤ 0.6 was
  neutral copying.
- **D copies did not fall even in H-rich neighbourhoods.** At s 0.3 and 0.6, none of the
  164 D copies was lost (82 at each s), including 12 that arrived with four or five H
  neighbours. At s 1.0, losses came in collective falls, not from a copy's own
  neighbourhood. At fast k1: 1 of 22 copies with no or one H neighbour, 3 of 15 with two
  or three, 0 of 6 with four.

**The null distributions (2,000 seeds, fast k1; central k1 gives the same J
distributions):**

| Design | Disc | P(B1) | J after the 1st turnover, median (5–95%) | J after the 2nd | D copies per run (with ≥ 4 H neighbours) | H copies with ≥ 5 D neighbours |
| --- | --- | --- | --- | --- | --- | --- |
| (a) whole sheet, state-blind donors | 37 | 0 | 0.64 (0.52–0.76) | 0.50 (0.35–0.66) | 85 (18) | 3 |
| | 19 | 0 | 0.54 (0.36–0.71) | 0.39 (0.17–0.59) | 43 (13) | 1 |
| (c) disc slots, disc donors | 37, 19 | 1 | 1 | 1 | 85, 44 (0) | none |
| (b) whole sheet, isolated templates | 37 | 0 | 0 | 0 | none; 5 templates arrive with ≥ 5 D neighbours | none |
| The pre-screen: disc slots, state-blind donors | 37 | 0.011 | 0.76 (0.60–0.89) | 0.57 (0.35–0.78) | 54 (5) | 1 |
| | 19 | 0.005 | 0.68 (0.47–0.84) | 0.42 (0.16–0.74) | 23 (4) | 0 |

**What the null means for the design:**
- **Copying alone cannot pass B1 with state-blind donors:** 0 of 2,000 seeds on either
  disc.
- **The expected D count is conserved,** at a median of 38 of 37 and 19 of 19 at the end.
  J falls because the D set drifts and spreads beyond the disc (a median of 14 D cells
  outside at most). So J measures spatial fidelity under drift, and inheritance is
  judged by the deviation.
- **Seed variance is large.** One 19-cell seed ends at J 0.25 and another at 0.65. Every
  engine run is therefore paired with its own null.
- **The pre-screen's single donor seeds lie inside these bands,** or at the edge of them
  (19 cells at s 0.3 after one turnover: 0.89).

## 5. Arms, seeds and budget

| Set | Arms | Seeds | Runs | Model time per run |
| --- | --- | --- | --- | --- |
| (a) donor, fast k1 | the five discs | 1–4 | 20 | 39 min |
| (a) donor, central k1 | 37 cells at s 1.0 and 0.6 | 1–2 | 4 | 85 min |
| (b) isolated, tau 40, 120 and 300 s (threshold-finding) | 37 cells at s 1.0 and 0.6 | 1 | 6 | at most 39 min |
| (c) disc slots, disc donors, fast k1 (control) | 37 cells at s 1.0 and 0.6 | 1 | 2 | 39 min |

**Cost on CPU.** The model is one world per process; vmap is slower per world on CPU.
- The pre-screen ran at 7.7 ms per step with two processes.
- A fast run is therefore about 60 min of wall time and a central run about 131 min.
  Runs in (b) stop early once the sheet is all H.
- The whole set is about 37 core-hours: about 18.5 h on two cores.
- Memory: cap each unit at 6G. The pre-screen's longest arms peaked at 4.8–5.2 GB in
  their end-of-run analysis.

| Fits | Set | Core-hours | Wall on two cores |
| --- | --- | --- | --- |
| Minimal | (a) fast with seeds 1–2; (a) central with seed 1; (b) at s 0.6 only; (c) | about 19 | about 10 h |
| Proposed | the table above | about 37 | about 18.5 h |
| Fuller | (a) fast with seeds 1–8; the rest as proposed | about 57 | about 28.5 h |

**Why a few engine seeds suffice.**
- The null gives J's distribution over seeds exactly (2,000 seeds in §4).
- The engine's question is its deviation, which every run samples at each event. A fast
  run of a 37-cell disc has 291 events: about 85 D copies and 205 H copies (null
  medians).
- With four seeds there are about 340 D copies per disc. A D-copy loss fraction of 10%
  then has a standard error of about 1.6%.

## 6. Readouts and the proposed judged items

**Per run:**
- the J series against the disc and its paired null on the same draws,
  ΔJ(t) = J_engine − J_null, at every record and at both turnover completions;
- D inside and outside the disc;
- **event classes:**
  - D copies lost to H before their own replacement (the D-loss fraction);
  - H copies converted to D (the recruitment fraction);
  - isolated newcomers converted, in (b);
  - founders lost before replacement;
  - each class split by D neighbours at arrival, as the null counts them;
- composition and osmotic excess against the H start;
- refusals and device-check failures;
- the opportunity analysis of the pre-screen (`summary` part), for each newcomer.

**Items:**
- **E1, numerics gate (before any judged arm).** The pre-screen's 1 ms / 5 ms comparison,
  repeated on E07-v1's own definitions and judged by the same criteria
  (`numerics/criteria.json` of the pre-screen):
  - (a) fast at 37 cells, s 1.0, seed 1, the first 600 s;
  - (b) tau 40 s at 37 cells, s 0.6, the first 300 s.

  If it passes, the arms run at 5 ms. If not, they run at 1 ms with the minimal set.
- **E2, validity.** No refusal and no failed device check in any judged run. Every
  definition passes the driver's checks: P equality, D147's `declare()`, and a layout
  equal to sheet70's. A censored run is reported as censored.
- **E3, (a) copying fidelity, per coupling s** (pooled over discs and seeds). With
  δ = 2/37 ≈ 0.054 (two cells of the 37-cell disc):

  | Class | Rule |
  | --- | --- |
  | Neutral copying | mean ΔJ after the second turnover within ±δ, D-loss at most 2% and recruitment at most 2% |
  | Electrical erosion | mean ΔJ below −δ, or D-loss above 5% |
  | Electrical recruitment | mean ΔJ above +δ, or recruitment above 5% |
  | Small bias | anything else |

- **E4, control (c).** J = 1 at every record, with no D copy and no founder lost. Any loss
  is reported with its time and neighbourhood.
- **E5, (b) threshold-finding** (reported, with no pass or fail):
  - per tau and s, the isolated newcomers converted, as a fraction of those that arrived
    with five or more D neighbours;
  - ΔJ against the null, whose J is 0 once every founder has been replaced;
  - the boundary tau*, the largest ladder tau at which at least one interior newcomer
    converts.
- **B1** (J ≥ 0.8 through two turnovers) is reported for every run beside the null's
  P(B1). Copying alone cannot pass it in (a) (0 of 2,000 seeds), so it does not decide
  the outcome.

## 7. Predictions (written before any E07-v1 engine run)

Item by item, with ranges, in
[`validation/tissue/e07_v1_protocol.json`](../validation/tissue/e07_v1_protocol.json)
(PROPOSED). Their bases are the pre-screen, its opportunity analysis, the stress
segment N2, and this null.

| Item | Prediction |
| --- | --- |
| E1 | Passes, as in the pre-screen (about 10 µV and 3e-6 or less) |
| E3 at s 0.3 | Neutral copying: ΔJ = 0 at every record in at least 7 of the 8 runs, and no D copy lost or H copy converted |
| E3 at s 0.6 | Neutral copying: mean ΔJ within ±δ; D-loss at most 2%; no recruitment |
| E3 at s 1.0 | Electrical erosion: mean ΔJ after the second turnover from −0.35 to −0.05; D-loss 5–25%; 5–20 founders lost per run; no recruitment; the sheet all H in at most 1 of the 4 fast seeds |
| E3, recruitment | No H copy converts at any s |
| E4 (control) | J = 1 throughout at s 0.6. At s 1.0, J at least 0.9 after the second turnover, with no collective loss (low confidence: newcomers' slowly reformed junctions weaken the disc's interior support of its rim) |
| E5, s 0.6 | Recruitment of interior isolated newcomers falls with tau: at least 40% of those arriving with ≥ 5 D neighbours at 40 s, at least 20% at 120 s, at most 20% at 300 s; tau* at least 120 s, most likely 300 s; J after the 1st turnover 0.15–0.5 at 40 s and 0–0.2 at 300 s |
| E5, s 1.0 | All H within the first turnover at every tau (collective loss, as the pre-screen's s 1.0 isolated arms); recruitment only at 40 s and early, if at all |
| Validity | No refusal and no failed device check. Fast runs reach about 8% excess (no flag). Central runs flag at 55–58 min after the cue and reach 14–15%; the censor may cut the last minutes of some central runs |
| B1 | Fails in every (a) and (b) run; passes in (c) at s 0.6 |

## 8. Limits

- **Fixed volume.** Replacement over water waits for §2's code, which is held until S3's
  fix and first round have landed.
  - The 95-minute budget bounds the time since the cue.
  - Central runs end 87 min after the cue, near the censor (the pre-screen reached
    14.4%).
- **One world family.** Homogeneous held-bath sheets, one formation shape and one
  neighbour rule (uniform). Held baths supply K without limit.
- **Donor copies do not halve the donor** (there is no growth), and turnover is uniform:
  no extrusion by age or stress.
- **Scale.** The 127-cell sheet only; the full tissue needs GH200 or a long-time method.
- **Step.** 5 ms lies outside G2-Q1's 1 ms scope, hence E1.
