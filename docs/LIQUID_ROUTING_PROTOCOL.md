# Liquid routing: the registered comparison for FR-54 and FR-57

**Status: written 25 November 2026 for the lead's tags, before the build** (D341, D352, D362, D364).
Docs and validation only, with no `src/` change. Its author does not write references, build, judge or
check. Branch `fr54-57-protocol`, from main 0e563668. Six placeholders are open (`spec/SPEC.md` §6), to be
filled in one dated commit before the criteria tag, and one number is pending (§10, item 7).

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
| 1 | FR-54, item 1 | Two wells, one step: three backgrounds and an empty well, two volume ratios, at steps declared in advance; the exact heat and the default heat | T1, the transfer against the published scheme (R). T2, against the closed form (B, and the local order L). T3, the exact heat against the free energy its own transfer lost (R). T4, the default heat, the same (R and B once the law arrives, the ladder L until then) |
| 2 | FR-54, items 2 and 3 | Diffusion, a half exchange of one well, diffusion, at three steps under both heats; a run meant to stop | The amounts and the face's heat against the two-well solution (S). The exchange's removed, supplied and refill heat, each against its own row (R) and the reference (S). The rows before it equal the no-exchange twin's (E). Every stop's message (M) |
| 3 | FR-57 | A → B → collector and the reverse, at equal and unequal volumes; a split and merge; a ring; two tracers carried by one flow; labels; a site beside the flow | Every amount, volume, sum, label and the total heat at 1, 8 and 64 steps per residence time (R). The labelled run's physics against its unlabelled twin, and the sites against the world without the router (E) |
| 4 | FR-57 | A collector from zero volume: portions in four orders, and a flow that switches | Each portion's loss, the totals (R). The first portion's loss is +0.0, the restart at the switch (E) |
| 5 | FR-57 | A chain at three steps, with the chamber empty at three traces, and a uniform stream | Each holder's heat against its exact integral, first order (S). The total, exact at every step (R). A uniform stream loses nothing (U) |
| 6 | FR-57, after FR-54 | Flow beside a face, and flow off | The amounts and heats against the exact linear system, second order (S). The flow alone in a species the face does not pass (R). Flow off against the diffusion-only twin (E) |
| 7 | FR-57 | The wash's worlds, re-declared as routed portions | Every saved array and mapped record bit for bit (E) |

**The targets each request named** are all covered: FR-54's three items and its 8 and 2 fmol setup (arms 1
and 2); FR-57's two targets, its "only a flow passes" rows, its free-energy check and its growing collector
(arms 3, 4 and 5). The request's refusals and restarts mid-flow live in tier rows (§8).

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
and `cells.operator.site_occupancy@1`. Arm 7 also runs `cells.operator.scheduled_compartment_wash@1`. The
IDs are the rename candidate's (2dd54f72), checked against its mapping table at the criteria tag.

## 3. The roles

Each is a different agent, and its work goes through the lead.

| Role | Writes | Reads | May not read |
| --- | --- | --- | --- |
| Author (this document's) | This document, the spec folder | – (as the disclosures list) | engine source, tests, run output |
| dt-study agent | The study's edges, the default heat's declared law, the propagator's re-measured bounds, the arm 7 pairs | Engine source; its own runs on today's engine | the spec folder's answers (`references/`), the judge's code |
| References agent | `validation/liquid_routing/references/` | `validation/liquid_routing/spec/` only | this document, the design note, engine source, tests, any run output |
| Builder | The operator; `validation/liquid_routing/worlds.py`, the exporter, `takeover_map.json`, the format sample | The design note, the spec folder, its own code | `references/out/`, the judge's code |
| Judge | Its reader, its synthetic checks, the verdict | This document, the spec folder, the references (from C0 on), the format sample | engine source, tests, the builder's code, the design note |
| Checker | Its own recomputation | The hashed table, the references, the judge's record, and the runs' `definition` against their `inputs` | the judge's code until its own is written |
| Lead | Tags, freezes, launches, hashes, the decision entry | everything | – |

- The builder runs no registered world before the run tag: parse checks, unit rows and invented worlds only.
- The judge's reader is written from this folder alone. The builder's exporter is written from `TABLE.md`
  alone. Neither reads the other's code.
- The checker also confirms that each run's `inputs` is what its `definition` says, that P8's patches were
  on, and that a refused or stopped run is the engine's own.

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

1. **This document and the spec folder** are committed, with placeholders.
2. **The dt study,** on today's engine, fills E1, E2, S1 and L1, re-measures the propagator's bounds, and
   names W7. **The author fills the placeholders** in one dated commit. The criteria tag:
   **`liquid-routing-criteria-2026-11-2x`**. The bands are fixed from here.
3. **The references agent** writes the references, its checks (`SPEC.md` §9) and its plant sizes. If a
   margin is below 10, the author changes the plant first. Tag: **`liquid-routing-references-2026-11-2x`**.
   The build may begin at this tag (it waits for the ID rename).
4. **The builder** builds the operator, then the worlds and the exporter from `TABLE.md`, then the format
   sample and `takeover_map.json`. It checks the sample, and smokes **invented** worlds at every registered
   step and heat, so that a step the engine refuses is found (and changed by a dated commit) before the tag.
5. **The judge's reader** parses `reference_invented.json`, then C0 on the references, then the format
   sample (`TABLE.md` §4), and passes its self-tests (`CRITERIA.md` §6.3). Tag:
   **`liquid-routing-judge-2026-11-2x`.** A registration names a reader that exists (D308).
6. **The registration tag `liquid-routing-registered-2026-11-2x`,** at the head that merges main, the spec,
   the references, the build and the judge, before any registered run. At that head the lead re-runs the
   builder's checks, the judge's tests and C0, regenerates the sample, and makes a trial merge.
7. **Phase 1:** arms 1, 2, 3, 4, 5 and 7, from a clean frozen snapshot of the registration tag
   (`scripts/gates/freeze_snapshot.py --scope full --require-clean`), detached, one thread each, cold (no
   compilation cache), on CPUs the lead allots, on one machine. The exporter's table is hashed before any
   reference value is read. **Arms 1 and 2 are judged first.**
8. **Phase 2:** arm 6, from the same snapshot, **only if FR-54 passes** (Q8). Its table is hashed first too.
9. **The retry,** if any entry is owed one, from the same snapshot, its table hashed the same way.
10. **The checker,** then the record and the decision entry.

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
  - **Flow beside diffusion** lifts the version-1 refusal of a flow at a faced node, under the exact heat.
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

## 9. What it costs

| Work | Agent-days |
| --- | --- |
| The dt study, the edges and the law (already running) | – |
| References: closed forms and integrals in decimal, the checks, the plant sizes, the invented file | 0.75–1 |
| Builder: worlds, exporter, sample and map, smokes on invented worlds | 0.75–1 |
| Judge: reader, C0, sample parse, scoring | 0.75–1 |
| Checker | 0.25–0.5 |
| This folder's later dated commits | 0.25 |
| **Total** | **2.75–3.75** |

The design note's line for the registered protocol is 1.5 to 2 (its §10). The difference is the references'
two quadratures and the six registered networks, the pre-tag format sample, and the checker.

**CPU:** 128 registered runs (arm 1: 55; arm 2: 20; arm 3: 27; arm 4: 8; arm 5: 13; arm 6: 5), about 12 for
arm 7, and at most about 25 for a retry. Each is seconds after a compile of 30 to 45 s: about 2 CPU-hours,
one thread each. The references and their regenerations are minutes.

## 10. Open questions for the lead

1. **FR-57 while arm 6 is not run.** §6 reports it inconclusive as a whole, on three lines. Recommendation:
   keep it, so a pass of flow alone is never read as a pass of the request.
2. **A stop of an honest run fails it** (§7). Recommendation: adopt, stated before any run.
3. **The order window** is [p − ½, 2.5] for each class, the scheme's order 2 plus D271's half, narrower than
   D271's. An out-of-window order is inconclusive, as D271 has it. Recommendation: adopt.
4. **T4 without its law** is judged by the ladder. Recommendation: fill L1 before the criteria tag.
5. **The default-heat starts are the study's starts** (§11). Recommendation: accept, since the study reports
   only edges, the law and its constant.
6. **Arm 7's failing** fails FR-57, as the note's §8.2 reads. Recommendation: accept, and say that it bears on
   the takeover line only.
7. **The propagator's bound** (8 ε an entry) is declared, re-measured, pending. If it moves, `LAWS.md` §9's
   m_n moves by the same number before the tag.

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
  thresholds; the IDs; the edges' list; arm 7's pin).

**Seen and not used:** D362's and D364's desk figures for the default heat's domain (kh at most 0.2 and 0.05)
and the note author's propagator probe (at most 1.0 ε an entry). z_def is a formula of the measured edges.

**The dt study sees the default heat at the registered default-heat starts,** since the edges were asked for
there. It reports edges, the law, its constant and the propagator's bounds, never a heat or a transfer. Its
record is not read by the references, the judge or the checker.

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
  - T4's ladder at 0.2 to 0.62 of its bound at resolved levels, and 0.9 to 15 times it at an unresolved
    one (a background of 0.017 mM).
- **Registered inputs it touched:** the four portion orders of arm 4, whose losses the request states; arm
  2's start, to show that its exact solution holds 8 and 2 fmol at 16 s; and the sign of `F6`'s
  discriminant, to show that the ring has complex rates. No stand-in ran on a registered world.
- **The first pass of the event check** printed orders near 1. Its outputs were off the step grid, not the
  scheme's order; it is kept as `native_run_first_offgrid.out`. SPEC.md §0 therefore requires every
  compared time on the grid.
- **What the dry run changed:** a planted first-order error sits at about 1.0 of a step-halving tolerance
  made from its own rungs, so a plant is scored with the honest run's tolerance, and T4 has a decisive
  ladder. The rounding multipliers come from the operation count in `LAWS.md` §9, not from the margins.

**Not read:** engine source, tests, any run output, any reference file, the judge's code, the builder's code.

**The advisor** was called twice: on the plan, and on this draft (§ the commit message says whether the
second call answered).
