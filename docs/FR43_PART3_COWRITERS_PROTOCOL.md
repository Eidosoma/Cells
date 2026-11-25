# FR-43 part 3's co-writers: the registered comparison (protocol)

**Status: written on 25 November 2026, for the lead's tags. Nothing is built, run or judged.** This document and the
spec folder (`validation/fr43_part3_cowriters/spec/`) are written by the protocol's author, who writes no reference,
builds nothing, judges nothing and checks nothing. Branch `fr43-part3-spec`, from main 5cf41d7c. The design note is
`docs/FR43_PART3_COWRITERS_DESIGN.md` (branch `fr43-part3-cowriters`), whose four questions the user decided on this
day (§11). This is the second registered comparison of FR-43 part 3 (the first:
`validation/fr43_part3/REGISTRATION.md`, judged D319). It is for the open item that D328 named, a moved row
co-written by local reactions or the gene unit.

## 1. Why a registered comparison

D187 rule 6 asks one judged run per claim, and the claim is new. The first comparison's W3 ran the population beside
a writer whose rate does not depend on the population (turnover). The build that this registers (the design note's
§3 and §7) admits the reactions and the gene unit as co-writers of a moved row. Its claim is that beside a writer
whose rate reads the shared row, the event times and the shared amounts of a low-count population converge at second
order in dt to the coupled process, and that where no rate reads the shared row the event times are exact at every
dt. Nothing registered has tested either. The build's own tests (the design note's §5.2) judge the books, ledgers,
restarts and refusals, and cannot see an order.

## 2. The claim

With the engine's two writers as separate split parts in declared order (`integer_unit_population@1` beside
`local_species_reactions@1`, or beside `templated_polymerisation@1`):

- **W5 (reactions), W6 (gene unit).** The event times and the shared row's amounts, and each writer's own book that
  the coupling touches, agree with code-blind references of the exact coupled process to their own step-halving
  estimate, at second order in dt (order p = 2 declared; window [1.5, 2.5], the split scheme's half windows), in
  both declared orders of the writers.
- **W5-exact.** Where no rate reads a row, the event times equal the exact decimal times to rounding at each of two
  steps (W5-exact runs with the same reactions and transfer, in both declared orders).
- **Every row, every writer's book** satisfies its identity to rounding (the books are exact), in every run; the
  event sequence (channels, counts, integer ledger) and a restart are exact (class E).

**What it does not claim** is in §8 and §9 (and in the note's §8). **The spec's tolerances and windows are
derived**, from a counted rounding bound or the split's declared order. No window or tolerance is fitted to any run
or to a probe.

## 3. The engine models it runs

| Model | Where |
| --- | --- |
| `resolved_pump_composite@1` over `resolved_pump_tissue@3` | Every world |
| `integer_unit_population@1` | Every world |
| `local_species_reactions@1` | W5, W5-exact |
| `templated_polymerisation@1` | W6 |

These are today's IDs. The registered IDs, in declared order for each family, are the lead's **strings note** (§5),
which has its own commit and tag after the registration tag. The spec folder names none, so the rename (the note's
§6.1, D345, D346) changes no hashed file of the registration. The builder lists in its README the operators that the
strings note lists.

## 4. The worlds

All inputs are in the spec folder's `inputs.json`. Each world is 8 independent copies (its own seed), so that a
pooled statistic averages over the phase noise of a single event path (LAWS.md §5). Every judged world runs with the
co-writer declared first and with the population declared first. W5 and W6 run at five steps each, W5-exact at two,
plus one restart in each of W5 and W6, plus the Lie plant (§6). All 192 judged runs, 2 support runs and 24 plant
runs are listed in `inputs.json`.

## 5. Roles, tags and the order of work

| Role | Who | Writes | Reads |
| --- | --- | --- | --- |
| Protocol author | The author of this document | The spec folder and this document, tagged by the lead. Writes no reference, builds nothing, judges nothing | – |
| References | A code-blind agent | `validation/fr43_part3_cowriters/references/`, the invented pair first | The spec folder and the sheet sections LAWS.md §3 names. Nothing else |
| Spec auditor | An agent who wrote none of this text, and builds nothing else | A reader skeleton and a fabricated honest table, its report (§6, step 2) | The spec folder only |
| Builder | The FR-43 part 3 build lane (after the legacy cleanup lands) | `validation/fr43_part3_cowriters/` engine side: the world builders, the exporter (TABLE.md), the Lie patch, the format sample | The spec folder, its own code |
| Judge | A new agent, blind to any engine output and to the engine's development results | The reader and the scorer, `retry_owed.json`, the verdict | The spec folder, the reference files (C0, before any engine run exists), and, once their hashes are recorded, the engine tables and the strings note |
| Checker | An independent agent | Its own recomputation of the verdict | The hashed table, the reference files, the judge's record |
| Lead | The lead | Tags, hashes, the strings note, the record, the decision | Everything |

**The tags, in order** (each by the lead, none by this author):
1. `fr43-part3-cowriters-criteria-2026-11-25`: this document, the spec folder, before any reference exists. It fixes
   the criteria, bands and plants.
2. The spec auditor reports. Its findings change the text only by a dated amendment of this folder (the routing
   registration's practice), before the references' tag where they change what the references publish, and always
   before the judge's tag.
3. `fr43-part3-cowriters-references-2026-11-2x`: the references' files, after C0's checks (including the sizing)
   pass.
4. The builder's worlds, exporter, Lie patch and format sample (`fr43-part3-cowriters-build-2026-11-2x`), on the
   built engine (after the legacy cleanup and the co-writer build land), and the sample's hashes in the note.
5. `fr43-part3-cowriters-judge-2026-11-2x`: the judge's reader and scorer, after C0 on the invented pair and the
   format sample.
6. The **rehearsal** on the invented worlds through the registered exporter (§6).
7. **The registration tag** `fr43-part3-cowriters-registered-2026-11-2x`, at the head the runs will be made from:
   the criteria, references, builder, judge, and the runs' frozen snapshot. The **strings note** (the lead's, its
   own commit and tag) follows it, and names the registered operator IDs per family.
8. The runs from the snapshot, then the table. The lead records the table's hashes **before the judge opens any
   table** (C0 has read the references before the runs exist). Then the judge's first pass, `retry_owed.json` and
   its hash, the retry runs if any are owed, and the second pass.
9. The checker, then the record and the lead's decision.

## 6. The order of work, and the rehearsal

1. The references agent starts after tag 1. It may start before the builder exists, since the folder names no engine
   ID.
2. **The spec auditor** starts after tag 1. It writes its own reader skeleton and a fabricated honest table for
   every registered run and says what is refused, what passes with nothing judged, and what an honest run would
   fail. A finding changes the text only by a dated amendment. Its tables and numbers are its own.
3. **The builder** builds only after the legacy cleanup lands and the user releases the hold on builds. It does not
   read the references' values.
4. **The rehearsal** is CRITERIA.md §10's: the whole scoring path on the invented worlds through the registered
   exporter, before the registration tag. It exercises every class, the faults and the plants. A bound that an
   honest invented run misses is corrected by re-derivation, or is the engine's or the exporter's defect.
5. **The runs:** about 218 registered runs plus a retry of 8 at each owed family (§7), each on one copy of its
   world, from a clean frozen snapshot of the registration tag, each run's process cold and one-threaded, on CPUs
   the lead allots, detached. The plants' runs are included.
6. **The table** is built from the runs' records alone, and is hashed by the lead before the judge opens it.
7. **The judge** runs C0, the first pass, and (if owed) the retry pass, in an environment built from a clean
   snapshot of the registration tag, and writes the verdict with the record of CRITERIA.md §8. Then the checker.

## 7. What it costs (an estimate, in agent-days and CPU-hours)

| Work | Who | Agent-days |
| --- | --- | --- |
| This document and the spec folder | Author | done |
| The spec audit | Auditor | 0.5 |
| The references, with the invented pair, the sizing, the planted series, regeneration | References agent | 1.5–2 |
| The worlds, exporter, Lie patch, format sample | Builder | 0.75–1.25 |
| The reader, C0, scoring, rehearsal | Judge | 1 |
| The recomputation | Checker | 0.5 |
| **Total** | | **4.25–5.25** |

**CPU-hours:** about 218 registered runs, each a compile of 30 to 60 s (estimated: the design note's probe worlds
took 55 to 74 s, compile and run) and a run of 20 s to 2 minutes (W6 at its finest is 19,200 steps), one thread
each. About 3 to 6 CPU-hours in all. The retry, at most 8 runs per owed family, adds up to about 30 minutes. The
references: under one hour. These are estimates, not measurements of the registered runs.

## 8. What is left, and what is not claimed

- **Not claimed:** a claim of any other writer (turnover and exchange beside a population were judged in W3 or are
  admitted today), a composite with more than two such writers, an order above second, any energy (the operators'
  own ledgers hold it), a changing volume (§4.3 of the note: FR-65's), a batch or a GPU (D336), a dividing or
  replaced cell with a co-writer, in-step movers, a charged row, more than one site in a patch, units of more than 2
  subunits or sites of more than one unit, a step so large that the split leaves the asymptotic range (λ dt of order
  one, note §2.4), and the trace's recorded pools (first order beside a co-writer by construction).
- **Left to later:** FR-54/57's two steps at a site's node (note §4.1), the region readouts (note §4.2), the
  population at changing volume (the user's question 3, logged as its own request), FR-52's population record, the
  composite on a GPU.

## 9. What a pass cannot show

The comparison tests the laws and the two writers it runs, and only at the sizes above.
- **The channel rule's use of the second draw.** W5 and W6 sites have one non-zero propensity at every state, so u2
  never decides a channel (LAWS.md §1).
- **The random streams' statistics.** The judge tests the draws against the written rule, not their distribution.
- **The finest-step error is the only size test.** A pass says that at the finest step the error is within three
  times the step-halving estimate, and the order is inside its window; not that the error at the coarsest step is
  small. W5-exact is the only exact line.
- **The two declared orders are not told apart by the results** (they are told apart by the echo of the operators).
- **The reach of one spatial size and parameter set:** one volume pair per world, one gain, constants as declared,
  one reaction network of first- and second-order routes, one gene unit with a single chain, one transfer per world.
  A faster transfer, a stiffer network, a step at λ dt of order one, are outside (§8).
- **Discretisation beyond step halving:** the order is fitted on pooled rungs in [1.25 ms, 20 ms] (W5) and [31.25
  ms, 0.5 s] (W6), and says nothing of a coarser step.
- **Anything the engine records but the table does not**, and the engine's own ledger checks (recorded, not judged).
- **Operators the world does not hold:** no turnover, exchange, label owner, water, lumen, wash, division or
  replaced cell in these worlds.
- **A fail that a departing echo hides.** A run whose definition departs from the registered one is refused, not
  judged.
- **The same bugs in two places.** The references and the engine share the law text (LAWS.md), as any pair does; a
  wrong law is found only by the plants and by the checks on the references' files (SPEC.md §9).

## 10. Disclosures: what this registration's author has seen

- **The design note's development probes,** which are the author's own work
  (`/mnt/workspaces/Cells/fr43-part3-cowriters-20261125/`): the compiled worlds (a five-writer world and a gene
  pair, 74 s and 55 s of compile and run on a busy CPU), the operators' half-steps in jitted loops, and a NumPy
  prototype. Their numbers, one site each, not registered: W5-like (S read and moved) 21 to 33 events in 20 s, RMS
  event-time errors 1.7e-6 to 2.5e-5 s at 20 ms and 3.2e-9 to 1.3e-7 s at 1.25 ms; fitted orders 1.85 to 2.19 (the
  gene unit's W6-like 1.94 and 1.95, 71 events); the pooled orders by neighbouring steps scatter (1.7 to 7.8 in
  ratios of successive errors). Constant rates: exact to 3.7e-13 s. Lie order: errors of 4.2e-4 to 5.3e-5 s at 20 to
  2.5 ms, order 1.0 in the prototype. The half-step sequence was measured to leave the rows of the world untouched
  in the tissue's inner step (identity).
- **Sizing emulations for this registration** (`/mnt/workspaces/Cells/fr43-part3-spec-20261125/`, host NumPy, no
  engine): an emulation of the declared split on invented worlds of the W5 and W6 kinds (numbers, seeds and horizons
  of their own, not the registered ones). What they were used for, and what they gave: (i) the number of copies and
  the pooled statistic: the standard deviation of the fitted order of the event times was about 0.16 for 4 copies
  and 0.06 for 16 pooled (a 4-subunit world), and neighbouring-step ratios scattered by 0.15 to 0.35 even at 16.
  (ii) The registered design (8 copies, 2 subunits): in 6 seeds of each declared order of a W5-like world, the
  fitted orders of the event times were 1.77 to 2.13 (S_c: 1.91 to 2.06), and in 3 seeds of each order of a W6-like
  world 1.80 to 2.13. The honest error at the finest step over the size tolerance was 0.17 to 0.46 (W5-like events),
  0.21 to 0.42 (S_c) and 0.24 to 0.33 (W6-like events). (iii) The choice of 2 subunits per site over 4: with 4, a
  channel choice differed from the reference's at the coarsest steps in some runs, which would fail the class E
  trace of an honest run (the note's original choice was 2). No registered number was used, and no registered world
  was run on any engine or emulation.
- **A premise check:** `make_draws.py`'s table was compared with the engine's own stream function
  (`cells.numerics.counter_streams`) at all 24 copies × 160 pairs: no differences.
- **The exemplars,** read in full or in the parts that matter: FR-38's second registration (its protocol, spec
  folder and amendments 1 to 6), the routing spec (tag `liquid-routing-amendment-5-2026-11-25`) with its five
  amendments, FR-43 part 2's criteria and part 3's registration. No registered result, reference value or judged
  table of any comparison was opened.
- **Engine source** (read by the author for the declared laws and the split's order; nothing of it appears in the
  folder): the population operator, the reactions' and the gene unit's laws, the composite's step, the streams.
- **The registered worlds have been run by no engine or emulation.** Their inputs are declared values, some of them
  close in kind to the probe's (same laws, neighbouring numbers). Their draws were generated by the stated rule
  (`draws.json`), without running any of the worlds.
- **The advisor** reviewed the plan before writing (its points are followed) and the finished draft before the
  report.

## 11. Decisions

The user decided the note's four questions on 25 November 2026: (1) split writers, (2) one judged run over W5, W6
and W5′ (`W5-exact` here) with code-blind references, (3) part 3 closes at this landing, with the population at
changing volume logged as its own request, (4) the declared general rule. The lead ruled L1 to L4 (the note's §7).
The build waits for the legacy cleanup (the user put every other build on hold). D315, D328, D336, D370, D373, D377
and the design note's §5.3 are the basis. A later amendment in this folder governs where it differs.

**Questions to the lead before the criteria tag** are in the author's report to the lead, not here.
