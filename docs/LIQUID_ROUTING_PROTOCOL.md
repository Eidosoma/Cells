# Liquid routing: the registered comparison for FR-54 and FR-57

**Status: written 25 November 2026 for the lead's tags, before the build** (D341, D352, D362, D364).
Docs and validation only, with no `src/` change. Its author does not write references, build, judge or
check. Branch `fr54-57-protocol`, from main 0e563668. The dt study of 25 November filled its placements (`spec/SPEC.md`
§6), through the lead's report only (§11). The study agent's later answers are folded in (§11) and none is
pending. **Amendments 1 to 6 of 25 November 2026** (`spec/AMENDMENT-<n>-2026-11-25.md`) govern this document and the
folder where they differ, the latest first.

**What it registers.** This document and `validation/liquid_routing/spec/`: `README.md`, `SPEC.md`,
`LAWS.md`, `READOUTS.md`, `CRITERIA.md`, `TABLE.md` and `inputs.json`. With the code-blind references and
the judge's reader it makes up the registration (§5).

**The protocol is `liquid-routing-v1`.** It carries one verdict per request (the design note's Q9).

## 1. What is judged

Each arm is a set of runs with its own reference. **E** equal bit for bit, **R** within a derived rounding
bound, **B** within a Taylor-remainder bound, **L** local orders, **S** step-halving with an order window,
**M** a stopped run's message, **D** completes. `spec/CRITERIA.md` states every formula.

| Arm | Request | What runs | What is judged, and its class |
| --- | --- | --- | --- |
| 1 | FR-54, item 1 | Two wells, one step: three backgrounds and an empty well, two volume ratios, at steps declared in advance; the exact heat and the default heat | T1, the transfer against the published scheme (R). T2, against the closed form (B, and the local order L). T3, the exact heat against the free energy its own transfer lost (R). T4, the default heat against its declared law (R) and against that free energy (B, and the local order L) |
| 2 | FR-54, items 2 and 3 | Diffusion, a half exchange of one well, diffusion, at three steps under both heats; two runs meant to stop | The amounts and the face's heat against the two-well solution (S). The exchange's removed, supplied and refill heat, each against its own row (R) and the reference (S). The rows before it equal the no-exchange twin's (E). Every stop's message (M) |
| 3 | FR-57 | A → B → collector and the reverse, at equal and unequal volumes; a split and merge; a ring; two tracers carried by one flow; labels; a site beside the flow | Every amount, volume, sum, label and the total heat, at steps from 1/64 to 1 of a residence time (R). The labelled run's physics against its unlabelled twin, and the sites against the world without the router (E). A flow above the operator's throughput bound is refused by name (one expected refusal) |
| 4 | FR-57 | A collector from zero volume: portions in four orders, and a flow that switches | Each portion's loss, the totals (R). The first portion's loss is +0.0, the restart at the switch (E) |
| 5 | FR-57 | A chain at three steps, with the chamber empty at three traces, and a uniform stream | Each holder's heat against its exact integral, first order (S). The total, exact at every step (R). A uniform stream loses nothing (U) |
| 6 | FR-57, after FR-54 | Flow beside a face, and flow off | The amounts and heats against the exact linear system, second order (S). The flow alone in a species the face does not pass (R). Flow off against the diffusion-only twin (E) |
| 7 | FR-57 | The wash's worlds, re-declared as routed portions | Every saved array and mapped record bit for bit (E) |

**The targets each request named** are all covered: FR-54's three items and its 8 and 2 fmol setup (arms 1
and 2); FR-57's two targets, its "only a flow passes" rows, its free-energy check and its growing collector
(arms 3, 4 and 5). The request's refusals and restarts mid-flow live in tier rows (§8).

**Arm 7's worlds** are, by the design note, FR-27's review well, FR-44's twins and FR-37's three draws, with
the pairs of `SPEC.md` §6. Both sides run from the registration tag's snapshot, where the wash still exists. FR-45's W2 and W7 and FR-49's B and C1 are not among them: their judged runs stay on the wash, or
are pinned to a snapshot from before its retirement (D364).

**The claim.** A pass says the engine's passive diffusion between two finite regions, its partial exchange
at a diffusion-connected region, and its prescribed flow of a passive tracer between finite regions into a
growing collector agree, within derived bounds, with independent closed forms, at the registered inputs.

**It does not claim:** anything about a real instrument, dispersion or pressure, ions carried by liquid,
stochastic execution, a default heat booked from an empty well, or a step's heat split as exact. Nothing
here qualifies by integration (D143): only the verdict does.

## 2. The engine models it runs

`cells.model.resolved_pump_composite@1` over `cells.model.resolved_pump_tissue@3`, with the operator
`cells.operator.liquid_routing@1` (new). Arms 1 to 6 use `cells.solver.imex_ars222_face_electromigration@1`
(ARS(2,2,2) only; IMEX Euler stays in tier rows). Arms 1, 2 and 6 add `cells.route.logmean_electrodiffusion@1`
faces, under the default face heat or `cells.heat.exact_free_energy_heat@1`. Arm 3 adds `cells.operator.neutral_arrival_labels@1`
and `cells.operator.site_occupancy@1`. Arm 7 also runs `cells.operator.scheduled_compartment_wash@1`. Arm 2's
exchange is the builder's to execute, by the operator the build provides. The registered strings note holds the exact
operators of every registered run, the declared heat choice of each run of arms 1 to 6, and the IDs in the new form, and
the judge compares with it (amendment 5). The IDs
are the rename candidate's (2dd54f72), read through the rename's committed mapping at the registration tag.

## 3. The roles

Each is a different agent, and its work goes through the lead.

| Role | Writes | Reads | May not read |
| --- | --- | --- | --- |
| Author (this document's) | This document, the spec folder | – (as the disclosures list) | engine source, tests, run output |
| dt-study agent | The study's edges, the default heat's declared law, the propagator's re-measured bounds, the arm 7 pairs | Engine source; its own runs on today's engine | the spec folder's answers (`references/`), the judge's code |
| References agent | `validation/liquid_routing/references/` | `validation/liquid_routing/spec/` only | this document, the design note, engine source, tests, any run output |
| Builder | The operator, and the lift branch; `validation/liquid_routing/worlds.py`, the exporter, `takeover_map.json` (and its rehearsal pair), `takeover_pairs.json` and its script, the format sample | The design note, the spec folder, its own code | `references/out/`, the judge's code |
| Spec auditor (amendment 4) | A reader skeleton, fabricated honest tables, its report | The spec folder only | everything else; its tables are read by no one who references, builds, judges or checks |
| Judge | Its reader, its synthetic checks, `retry_owed.json`, the verdict | This document, the spec folder, the references (from C0 on), the tables, the format samples, `takeover_map.json`, the strings note | engine source, tests, the builder's code, the design note |
| Checker | Its own recomputation | The hashed table, the references, the judge's record, `takeover_map.json`, the record files it recomputes from, and the runs' `definition` against their `inputs` | the judge's code until its own is written |
| Lead | Tags, freezes, launches, hashes, the strings notes, the decision entry | everything | – |

- The builder runs no registered world before the run tag: parse checks, unit rows and invented worlds only.
- The judge's reader is written from this folder alone. The builder's exporter is written from `TABLE.md`
  alone. Neither reads the other's code.
- The checker also confirms that each run's `inputs` is what its `definition` says, that P8's patches were
  on, and that a refused or stopped run is the engine's own. It recomputes the digests of one arm 7 pair from its two
  record files (all six if cheap), confirms every `both_differ`, `wash_only` and `router_only` entry and its reason,
  every entry of `records`, every mark, and the restart's checkpoint from its record.

## 4. Power, before any run (D366)

Every plant's distance is compared with the honest tolerance it must exceed, by `CRITERIA.md` §6.2, from
the references alone. The margin rule is 10. A plant below it is enlarged or replaced in this folder, by a
dated change, before the registration tag and never after a run.

**The plants.** The design note's eighteen, each with its named check:
- **judged in the registered run:** P1 to P5, P7, P8 (twice), P9 to P11 (one variant), P14 to P18, with P19
  added for arm 6, which had no plant. All but P8 are read from honest runs or formed from the closed forms,
  so they cost no run.
- **in tier rows only:** P6 (the heat as a remainder, the 50-digit row), P11's two other variants, P12 (bound
  material, with the judge's own one-ulp self-test) and P13 (the restart plants).

## 5. The order of work and the tags

1. **The dt study** ran on today's engine (25 November) and reported its placements, the default heat's law,
   the propagator's bounds and arm 7's worlds. Its record stays with the lead.
2. **This document and the spec folder,** with the placements (§6 of SPEC.md). The criteria tag:
   **`liquid-routing-criteria-2026-11-2x`**. The bands, counts and classes are fixed from here, with one route to
   correct a bound (`CRITERIA.md` §10).
3. **The references agent** writes the references, its checks (`SPEC.md` §9) and its plant sizes. If a
   margin is below 10, the author changes the plant first. Tag: **`liquid-routing-references-2026-11-2x`**.
   The build may begin at this tag (it waits for the ID rename).
4. **The spec auditor** (amendment 4) reads only the spec folder, and reports what is refused, what passes with
   nothing judged, and what an honest run would fail: before the references' tag if its findings change anything they
   publish, and always before the judge's tag. It re-runs its reader on an amended head before that head is tagged.
5. **The judge's rules** are written from the spec, untagged, before the engine's code exists. That is how D308's
   order (the judge before the build) is met.
6. **The builder** builds the operator and an unlanded **lift branch** for a flow at a faced node, then the worlds and
   the exporter from `TABLE.md`, then the format sample, which includes arm 6's kinds run from that branch, and
   `takeover_map.json`'s layout. It smokes **invented** worlds at every registered step and heat, so that a step the
   engine refuses is found (and changed by a dated commit) before the tag.
7. **The judge's reader** parses `reference_invented.json`, then C0 on the references, then the format sample
   (`TABLE.md` §4) and a meaningless sample of each layout, and passes its self-tests (`CRITERIA.md` §6.3). Tag:
   **`liquid-routing-judge-2026-11-2x`.** A registration names a reader that exists (D308).
8. **The lead's C0 dry run:** the tagged judge's C0 on the tagged references, printing names and pass or fail only,
   so that a fault has a remedy. At judgement it is repeated.
9. **The rehearsal** (`CRITERIA.md` §10): the builder runs the invented worlds of `inputs_invented.json` through the
   registered exporter (labelled development runs; arm 6's from the lift branch, with its revision in the record), with
   one invented arm 7 pair of its own, its map (`takeover_map_rehearsal.json`), its declaration in
   `takeover_pairs.json` and the lead's `registered_strings_rehearsal.json`, and the judge scores the table end to end,
   every class, honest and planted, against `reference_invented.json`. An honest miss is a defect to fix, or a bound to
   correct by §10's route (re-derived, dated, disclosed), before any registered run.
10. **The registration tag `liquid-routing-registered-2026-11-2x`,** at the head that merges main, the spec, the
    references, the build and the judge, before any registered run. At that head the lead re-runs the builder's checks,
    the judge's tests and C0, regenerates the sample, and makes a trial merge. `takeover_map.json`'s content and
    `takeover_pairs.json` (the pairs' wash-side declarations, from the fixtures by a committed script) are filed before it;
    the lead regenerates the pairs from the fixtures, compares, and writes the note's hashes from that.
11. **The strings tag `liquid-routing-strings-2026-11-2x`,** on the next commit, which holds only
    `registered_strings.json`. A file inside the tagged commit cannot hold its own revision. `engine_revision` is the
    registration tag's. Before this tag the lead checks the note by parse against the builder's declared worlds and pairs,
    with no run: one wrong operator ID or heat string would refuse every run of its world. A typo is corrected by a dated
    second note with its own tag, before any table is hashed, and never after. The same is done at phase 2
    (`registered_strings_phase2.json`).
12. **Phase 1:** arms 1, 2, 3, 4, 5 and 7 (nothing of arm 6), from a clean frozen snapshot of the registration tag
    (`scripts/gates/freeze_snapshot.py --scope full --require-clean`), detached, one thread each, cold (no compilation
    cache), on CPUs the lead allots, on one machine. The lead records the tables' hashes; the judge runs C0 on the
    references, then opens the tables. **Arms 1 and 2 are judged first,** with any retry they owe (and arm 5's),
    before FR-54's verdict and before phase 2 is decided. A retry runs only what the judge's `retry_owed.json` names (in
    `table-retry/`, and at phase 2 in `table-arm6-retry/`).
13. **Phase 2: arm 6, only if FR-54 passes** (Q8). The router's first landing refuses a flow at a faced node (a tier
    row asserts it), so arm 6 cannot run from phase 1's snapshot. After FR-54 passes, a small gated landing lifts that
    refusal, and arm 6 runs from that landing's own clean snapshot and tag,
    `liquid-routing-phase2-registered-2026-11-2x`. Its `src` differs from phase 1's only by the lift and its tests, and
    is compared with the rehearsed lift branch's; if a file that arm 6 runs through differs, its rehearsal is repeated
    before the tag (a miss is recorded, no bound is corrected, and the entries that rest on it, named by the lead in a
    dated note before the tag, are recorded and not judged, so arm 6 is at best inconclusive). Nothing of arms 1 to 5 and
    7 is re-run, and phase 1 is never re-scored. The judge is not re-tagged unless its code changes, and then by a dated
    erratum tagged before the runs. Arm 6's retry, if owed, is from that snapshot.
14. **The checker,** then the record and the decision entry.

## 6. The verdicts, and what they decide

`CRITERIA.md` §8 gives the rules.

- **FR-54 reads arms 1 and 2,** on three lines: the first step (arm 1), the exchange (arm 2), and the
  stopped-run report.
  - **A pass lifts one refusal:** a partial exchange at a diffusion-connected finite node, for one neutral
    species crossing by a passive route, under the exact heat, and under the default heat inside its
    measured domain. It also qualifies the two-well diffusion and the stopped-run report.
  - **A pass lifts nothing else:** not ions, not a second crossing species, not a flow at a faced node (arm
    6), and not the default heat from an empty well.
- **FR-57 reads arms 3 to 7 and is reported on three lines:** flow alone (arms 3, 4, 5), takeover (arm 7),
  flow beside diffusion (arm 6).
  - **Flow alone** qualifies `liquid_routing`'s portions and flows for passive neutral tracers in balanced
    networks of the kinds run (a chain, a split and merge, a loop), up to the size run.
  - **Takeover** permits the wash's retirement, under D364's wait for FR-45's W2 and W7 and FR-49's B and C1
    runs (or their pinning). It changes no past verdict.
  - **Flow beside diffusion** qualifies a flow at a faced node, under the exact heat, for the construct the
    phase-2 landing lifts.
  - Arm 6 not run leaves FR-57 inconclusive as a whole, with the other two lines as they stand.
- **An inconclusive verdict is not a fail,** and the retry is the only answer to it (D271). A fail is final
  for this registration. Its diagnosis is non-blind and labelled, by someone other than the author, the
  judge and the checker, and any new run is a new registration.

## 7. One departure from the precedent

FR-38's amendment 6 scores a run that the engine itself stops as refused, at best inconclusive. Here an
honest run that the engine's own energy, material or charge check stops **fails** (`CRITERIA.md` §3.7): the
check's residual above its tolerance is the evidence. A refused definition, domain or harness failure stays
refused. Nothing else differs from amendment 6: a fail is never hidden by a refusal, every entry that can be
formed is judged, and a refused or missing support run only makes its arm inconclusive.

## 8. Not judged here: tier rows

- The kernel rows of the design note's §8.1 (NumPy, on the operator alone), the uniform stream, the f-ladder
  and the 50-digit heat row.
- Every named refusal: an unbalanced node, ions across a link, a flow beside binding, a default-heat
  exchange outside its domain, a flow beside a face before FR-54 passes.
- Restarts across a flow and at a switch beyond arm 4's, the stopped-run row of the vector windows, plants
  P6, P11's two other variants, P12 and P13.
- D148: worlds that declare no router stay bit for bit (the build's gates).

**What the registered comparison cannot show,** in words (amendment 5):
- T1 does not identify ARS(2,2,2) among second-order explicit pairs.
- One full step in place of two half-steps in an exact propagator.
- How a step's heat is split among holders below arm 5's tolerance, and not at all in arms 3 and 6.
- A portion's `resident` and `arriving`.
- A wrong coarse run that a retry drops.
- The size of the numbers in a stop other than P8's.
- A bound species at a linked node: `F7`'s sites stand at a node that no link touches, and a builder's row must
  test a linked one.
- How much and how fast `F7` binds.
- Which step an exact-propagator run took, as far as its values show.
- `transfer_T`, its sign and beyond its sign, and `largest_ion_change_fmol`.
- Any difference below a stated tolerance or τ, arm 2's default heat included.
- That a restart was a restart, and what a digest hashes: the checker's to confirm.

## 9. What it costs

| Work | Agent-days |
| --- | --- |
| The dt study, the edges and the law (already running) | – |
| References: closed forms and integrals in decimal, the checks, the plant sizes, the invented file | 0.75–1 |
| Builder: worlds, exporter, sample and map, smokes on invented worlds | 0.75–1 |
| Judge: reader, C0, sample parse, scoring | 0.75–1 |
| The rehearsal: the invented-world runs (builder), and scoring them (judge) | 0.25–0.5 |
| Checker | 0.25–0.5 |
| This folder's later dated commits | 0.25 |
| **Total** | **3–4.25** |

The design note's line for the registered protocol is 1.5 to 2 (its §10). The difference is the references'
two quadratures and the six registered networks, the pre-tag format sample, the rehearsal, and the checker.

**CPU:** 122 registered runs (arm 1: 47; arm 2: 21; arm 3: 28; arm 4: 8; arm 5: 13; arm 6: 5), 12 for arm 7, and at
most about 25 for a retry (an earlier version of this line said 124, and omitted the retries' rule). Each is seconds after a compile of 30 to 45 s: about 2 CPU-hours,
one thread each. The references and their regenerations are minutes.

## 10. Questions ruled by the lead (25 November 2026)

All seven were ruled as recommended, with the changes noted. The study's answers that items 2 and 7 waited on are
in §11.


1. **FR-57 while arm 6 is not run** is inconclusive as a whole, reported on three lines, so a pass of flow alone
   is never read as a pass of the request. Accepted.
2. **A stop of an honest run fails it** (§7). Adopted, after the study runs every registered default-heat
   (start, step) and the author moves any that stops (§11).
3. **The order window** is [p − ½, 2.5] for each class, the scheme's order 2 plus D271's half, narrower than
   D271's. A resolved order outside it is inconclusive, as D271 has it; an unresolved one is reported, not judged
   (`CRITERIA.md` §3.5). Adopted. Amendment 5's V7 governs since: where exactly one difference is at rounding, an
   entry at most τ is inconclusive and one above τ fails.
4. **The default heat's law** (LAWS.md §2) is declared from the study agent's reading of the engine at main
   0e563668, checked here for its algebra and its Taylor bound only. T4 tests it through the composite. Its class
   R is a scheme check whose pass is expected, since the law was transcribed from the engine; its class B is the
   claim. Kept.
5. **The default-heat starts are the study's starts** (§11). Accepted.
6. **Arm 7's failing** fails FR-57, as the note's §8.2 reads, on the takeover line. Accepted.
7. **The propagator's domain** (throughput ρ at most 1) is the lead's ruling, and the study's definition is in
   `SPEC.md` §1 word for word. Over 657 networks at ρ ≤ 1 the study measured at most 1.36 ε on entries and 1.89 ε
   on column sums, and the first failure sampled is at ρ = 2 (it replaces earlier figures that carried wrong ρ
   labels). The registered worlds stay at 0.625 or below, `F6 h=4.0` must be refused, and `LAWS.md` §9 uses the
   declared 8 ε. A 64-node network is not claimed without a separate qualification. Adopted.

## 11. Disclosures (25 November 2026)

**Read, by the brief:** FR-54 and FR-57; D341, D352, D362 and D364; the design note's §3.2, §5, §8, §9 and
§10 (`f66a4828`); D187, D271, D308, D320, D351, D354, D366 and D370; FR-38's second comparison at
`fr38-v2-amendment-6-2026-11-25` (its protocol and every file of its spec folder); FR-45's protocol, SPEC
and CRITERIA on `fr45-protocol`.

**Read beyond the brief:**
- The design note's header, §0, and its headings; its §4's paragraph heads, cut at about 70 characters,
  which name T1 to T4 and the first word of each tolerance; and §7's first sentence. Not §2, §3.3, the
  "engine's step" or "desk sketch" paragraphs, or §6 to §7's body.
- D143, D148, D246, D278, D280, D282, D316's end, D317's start, D323, D324, D327, D334 in part, D342, D343's
  start, D345 to D349, D365, D367's start, D371 and D377 to D379. FR-27, FR-37, FR-44, FR-55, FR-56 and the
  start of FR-58.
- FR-43 part 2's CRITERIA, at `/mnt/workspaces/Cells/fr43-20261123/part2/references-spec/CRITERIA.md`
  (sha256 093036ca5c83074dbddf7fb0116eaa2b2cc00a1af9ac65c2a252399d42b570b9). It is in no tag. Its window
  [3.6, 4.4] and floor 10⁻⁸ are a form. This folder derives its own windows (`CRITERIA.md` §3.5) and floors
  (the rounding counts). FR-43 part 3's registration at its tag.
- `validation/assembly_lineages_v2/agreement.py` (its head) and the rename design's §2 and the rows that
  hold an ID.
- **The lead's answers** to this author's six questions (the solver and its polynomial R(z); the propagator's
  thresholds; the IDs; the edges' list; arm 7's pin), and **the dt study's report** as the lead relayed it: the
  default heat's booked form with its provenance (main 0e563668, the composite's IMEX step:
  `surface_pump_v3.py` 2768–2788, 2948–2962 and 2985; `surface_imex.py` 47–48, 60–68 and 123–132;
  `extracellular_field.py` 48–62; `surface_transport.py` 351–353), its leading error, the edge table, the
  propagator's measurements, the throughput ruling and arm 7's worlds. The study's folder was not opened.
- **What the report said and how it was used:** the law is declared, and its algebra and Taylor bound were
  derived here and checked on neighbouring inputs (`dry-run/default_law.py`). The study's own agreement figures
  (the law within 2.1 ε, 25 ε at (19, 16)) are not used: the R bound comes from the operation count. Edges
  place cases and set no band. z_def = 1/64 (4.5 times below the smallest completing edge) is a placement, and
  so is this author's estimate for arm 2's start.

**The study agent's later answers,** relayed by the lead on 25 November, all folded in:
- every judged default-heat run completes (16 in arm 1, 9 in arm 2, the exchange emulated by hand), the two expected
  stops stop, and the three recorded runs stop at their first row (`SPEC.md` §6; `CRITERIA.md` §8);
- the throughput definition, taken word for word (`SPEC.md` §1; LAWS §4), and the propagator's basis at ρ ≤ 1;
- the energy residual is cumulative from t = 0 (it spans the missing heat to the stop row), so `P8 flow` compares
  with H_tot at that row (M2);
- the ledgers' units (M1), and that today's messages hold no number, so M1 is a deliverable of the build;
- the registered zero-amount text (`SPEC.md` §0), and what parses (2 × 10⁻¹⁵ and above);
- at an exchange at a faced node under the default heat, the build refuses by name outside χ ≤ 0.25 and kh ≤ 0.2 (the
  lead's ruling on Q7, named constants with their provenance; χ is the lower well's relative change in a step). A
  wash at a faced node is refused today by the wash's face check and by the surface-crossing check behind it; the
  build lifts both by rule. Nothing refuses a flow at a faced node today, since no flow operator exists, so arm 6
  lifts the router's own refusal.

**Seen and not used:** D362's and D364's desk figures for the default heat's domain (kh at most 0.2 and 0.05)
and the note author's propagator probe (at most 1.0 ε an entry). z_def is a formula of the measured edges.

**The dt study saw the default heat at the registered default-heat starts,** since the edges were asked for
there. It reports edges, the law, its constant and the propagator's bounds. Its record is not read by the
references agent, the judge, the checker or this author. It was made on the engine's host-level one-step
routine: the compiled program, the composite, RK4, held baths and kh above 0.4 were not measured, so the
registered run's arm 1 asks for the composite's result and assumes none of it.

**A desk dry run,** on neighbouring inputs only (other volumes, flows and levels), with this author's own
NumPy and decimal code, no engine, on CPU 6, in
`/mnt/workspaces/Cells/fr54-57-protocol-20261125/dry-run/` (scripts, outputs and their sha256).
- **Closed forms** (§1 to §8 of `LAWS.md`) were checked in decimal, 60 digits.
- **Honest stand-ins** (an exact half-step network with ideal portion mixing, the published two-stage
  scheme, and three second-order heat bookings invented for T4) were run through every formula, printing
  statistics and neighbouring-input values:
  - the fraction of the rounding bounds used: at most 0.025 (amounts), 0.010 (labels), 0.007 (one step),
    and 4 × 10⁻⁴ of a looser heat bound (a multiplier of 128);
  - the T2 gap at 0.95 to 0.99 of its remainder, as Taylor's series says;
  - S-class errors at 0.32 to 0.34 of 3 est, orders within 0.05 of p;
  - the T4 ladder rule then planned, at 0.2 to 0.62 of its bound at resolved levels and 0.9 to 15 times it at an
    unresolved one (a background of 0.017 mM). The dt study's law replaced the rule: T4 is judged against its
    declared law and its Taylor bound, which were checked on neighbouring inputs too (err at 0.956 to 1.000 of the
    bound, and P16's planted error 109 to 127 times it at kh = 1/64; `default_law.py`).
- **Registered inputs it touched:** the four portion orders of arm 4, whose losses the request states; arm
  2's start, to show that its exact solution holds 8 and 2 fmol at 16 s; the sign of `F6`'s discriminant, to
  show that the ring has complex rates; and, for placement only, the lower well's change χ at each registered
  default start. No stand-in ran on a registered world, and no reference value was computed on one.
- **The first pass of the event check** printed orders near 1. Its outputs were off the step grid, not the
  scheme's order; it is kept as `native_run_first_offgrid.out`. SPEC.md §0 therefore requires every
  compared time on the grid.
- **What the dry run changed:** a planted first-order error sits at about 1.0 of a step-halving tolerance
  made from its own rungs, so a plant is scored with the honest run's tolerance, and T4 is judged by its law's
  closed bound. The rounding multipliers come from the operation count in `LAWS.md` §9, not from the margins.

**Not read:** engine source, tests, any run output, any reference file, the judge's code, the builder's code.

**Amendments 1 to 6** are in the spec folder, each with its own disclosures. Amendment 5 follows the lead's rulings on
the spec audit, its second rulings after the auditor's re-run, and its answers on that text, the last after the
auditor's third pass. This author did not read the audit, its folder or its numbers; the lead read the references'
README layout section and printed key names, and no value, to answer this author's questions about forms.

**The advisor** answered this author on the plan. It was called three times on the draft, the last after the dt
study's report was written in, and timed out each time. The lead's own advisor review of the protocol and the
criteria (the lead's message of 25 November, 11 items) is answered by the commits after it.
