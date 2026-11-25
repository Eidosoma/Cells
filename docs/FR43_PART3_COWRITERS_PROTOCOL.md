# FR-43 part 3's co-writers: the registered comparison (protocol)

**Status: written on 25 November 2026, revised after an independent audit of 736f0565 and after its second pass on
36d7f686 (the same day), for the lead's tags. Nothing is built, run or judged.** This document and the spec folder
(`validation/fr43_part3_cowriters/spec/`) are written by the protocol's author, who writes no reference, builds
nothing, judges nothing and checks nothing. Branch `fr43-part3-spec`, from main 5cf41d7c. The design note is
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

- **W5 (reactions), W6 (gene unit).** The event times, the shared row's amounts and the writers' books that the
  coupling touches agree with code-blind references of the exact coupled process to their own step-halving estimate,
  at second order in dt (order p = 2 declared; window [1.5, 2.5], the split scheme's half windows, fitted on the
  engine's own step differences), in both declared orders of the writers. In W6 the gene unit's own effect is judged
  too: its finished chains and stage exits by size, and its monomers, product and machines by ledger (below).
- **W5-exact.** Where no rate reads a row, the event times equal the exact decimal times to rounding at each of two
  steps (W5-exact runs with the same reactions and transfer, in both declared orders).
- **Every row, every writer's book** satisfies its identity to rounding, and starts at its declared value, in every
  run (class R); the event sequence (channels, counts, integer ledger) and a restart are exact (class E). In W6 this
  holds for N, M, Pi, R, the machines and the residues in transit, so that an engine that drops a reversibility
  factor, releases a product late or never, starts from a wrong amount, or neither makes nor consumes the monomer
  fails a judged entry (plants P11 to P15, sized by the references).

**What it does not claim** is in §8 and §9 and, as the list a pass cannot show, in the spec folder (CRITERIA.md
§11). **The spec's tolerances and windows are derived**, from a counted rounding bound or the split's declared
order. No window or tolerance is fitted to any run or to a probe.

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
pooled statistic averages over the phase noise of a single event path (LAWS.md §5). Each copy is one run's world
(§11, ruling 1): the copies of a W6 world do not fit one world's rate bound, and W5's are kept apart for one entry
shape. Every judged world runs with the co-writer declared first and with the population declared first. W5 and W6
run at six steps each, W5-exact at two, plus one restart in each of W5 and W6, plus the Lie plant (§6). All 224
judged runs, 2 support runs and 24 plant runs are listed in `inputs.json`.

## 5. Roles, tags and the order of work

| Role | Who | Writes | Reads |
| --- | --- | --- | --- |
| Protocol author | The author of this document | The spec folder and this document, tagged by the lead. Writes no reference, builds nothing, judges nothing | – |
| References | A code-blind agent | `validation/fr43_part3_cowriters/references/`, the invented set first | The spec folder and the sheet sections LAWS.md §3 names. Nothing else |
| Spec auditor | An agent who wrote none of this text, and builds nothing else | A reader skeleton, a fabricated honest table, its report (§6, step 2), and a second pass on each revision | The spec folder only |
| Builder | The FR-43 part 3 build lane (after the legacy cleanup lands) | `validation/fr43_part3_cowriters/` engine side: the world builders, the exporter (TABLE.md), the Lie patch, the format sample | The spec folder, its own code |
| Judge | A new agent, blind to any engine output and to the engine's development results | The reader and the scorer, `retry_owed.json`, the verdict | The spec folder, the reference files (C0, before any engine run exists), and, once their hashes are recorded, the engine tables and the strings note |
| Checker | An independent agent | Its own recomputation of the verdict | The hashed table, the reference files, the judge's record |
| Lead | The lead | Tags, hashes, the strings note, the record, the decision | Everything |

**The tags, in order** (each by the lead, none by this author):
1. `fr43-part3-cowriters-criteria-2026-11-25`: this document, the spec folder, **after the auditor's second pass on
   the revised head.** It fixes the criteria, bands and plants before any reference exists.
2. The spec auditor reports on every revision before the tag, and its findings change the files themselves (the
   routing registration's practice is an amendment after the tag). After the tag they change the text only by a
   dated amendment.
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
2. **The spec auditor** reads the folder before tag 1 and re-reads every revision before it (it reported on
   736f0565; this head is its second pass). It writes its own reader skeleton and a fabricated honest table for
   every registered run and says what is refused, what passes with nothing judged, and what an honest run would
   fail. After the tag a finding changes the text only by a dated amendment. Its tables and numbers are its own.
3. **The builder** builds only after the legacy cleanup lands and the user releases the hold on builds. It does not
   read the references' values.
4. **The rehearsal** is CRITERIA.md §10's: the whole scoring path on the invented worlds through the registered
   exporter, before the registration tag. It comes before the strings note, so there `operators` is compared with
   the list in the builder's own README. It exercises every class, the faults and the plants. A bound that an honest
   invented run misses is corrected by re-derivation, or is the engine's or the exporter's defect.
5. **The runs:** 250 registered runs plus a retry of 8 at each owed family (§7), each on one copy of its world, from
   a clean frozen snapshot of the registration tag, each run's process cold and one-threaded, on CPUs the lead
   allots, detached. The plants' runs are included.
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

**CPU-hours:** 250 registered runs, each a compile of 30 to 60 s (estimated: the design note's probe worlds took 55
to 74 s, compile and run) and a run of 20 s to 3 minutes (W6 at its finest is 38,400 steps), one thread each. About
4 to 9 CPU-hours in all. The retry, at most 8 runs per owed family, adds up to about 30 minutes. The references:
under one hour. These are estimates, not measurements of the registered runs.

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

The list is in the spec folder, CRITERIA.md §11, as the audit required. Two things beside it, which the list leaves
to the protocol:
- **The claim has no independent form at a step above its ladder**, nor in a fast-transfer or stiff regime (§8):
  W5's is [0.625 ms, 20 ms] and W6's [15.6 ms, 0.5 s].
- **Anything the engine records but the table does not**, and the engine's own ledger checks (recorded, not judged).

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
- **Emulations of the declared split, for sizing** (`/mnt/workspaces/Cells/fr43-part3-spec-20261125/`, host NumPy,
  no engine). **They are close to the registered worlds, in part by coincidence:**
  - *W5's kind:* T = 20 s, the first rung and the sample grid are the registered ones (the design note's probes used
    them, and the emulations ran on them), and the number of rungs was set by the sizing (below). The rates and
    amounts differ by 3 to 26% from the registered (W5-exact's `assemble` rate by 3%), except the W row's trace.
  - *W6's kind, before the audit:* T = 600 s, the rungs, 15 machines, 6 stages, conductance 0.012, a 1.0 pL cell,
    and rates within 0.4 to 18% of the registered values of 736f0565 (which the author found and reported after that
    head). **Those registered values have since been moved off them** (§11): the present W6 differs from each
    emulation by at least 11% in every physical value but two potentials (the monomer's, 0.9% and 3.3% off; the
    residue's, 6% and 7%) and the R rows' trace of 10⁻¹² fmol, which the new-regime emulation shares. The horizon,
    the first rung and the sample grid are the emulations' own (they were set for the sizing and were not moved),
    and the number of rungs, six, was set by the sizing (below).
  - *A new-regime gene-unit chain and a full W6-kind emulation* (the factor 1 − e^x, the saturation, the monomers,
    the pools as the present inputs' kind), with their own numbers, listed in the scratch record; used for the
    third-order totals' resolution and the pooled orders in this regime.
  - What they gave: (i) the number of copies and the pooled statistic: the standard deviation of the fitted order of
    the event times was about 0.16 for 4 copies and 0.06 for 16 pooled (a 4-subunit world), and neighbouring-step
    ratios scattered by 0.15 to 0.35 even at 16. (ii) The registered design (8 copies, 2 subunits): with the errors
    fitted against the exact process (a five-rung fit, the draft's form), in 6 seeds of each declared order of a
    W5-like world the fitted orders of the event times were 1.77 to 2.13 (S_c: 1.91 to 2.06), and in 3 seeds of each
    order of a W6-like world 1.80 to 2.13; the honest error at the finest step over the size tolerance was 0.17 to
    0.46 (W5-like events), 0.21 to 0.42 (S_c) and 0.24 to 0.33 (W6-like events). With the criteria's engine-only fit
    (CRITERIA.md §3.3), a five-rung fit gave 1.75 to 2.47 in 16 runs of the W5-like world (8 seeds of each order)
    and six rungs gave 1.78 to 2.14, which is why the ladder has six rungs; in the W6-like world (before the audit)
    six rungs gave 1.83 to 2.15 in five runs (two gene-first and three population-first). In the present regime, six
    rungs: see below. (iii) The choice of 2 subunits per site over 4: with 4, a channel choice differed from the
    reference's at the coarsest steps in some runs, which would fail the class E trace of an honest run (the note's
    original choice was 2).
  - In the new W6 regime (invented numbers, none of the registered ones): the orders of `n_R_c`, `n_R_o`, `lost`,
    `moved` and the event times over six rungs and the errors over the size tolerance: in 3 seeds of each order
    (24.9 to 31.0 events per copy) the fitted orders over all five step differences were 1.98 to 2.18 for the event
    times, 1.86 to 2.07 for `n_R_c`, 1.87 to 2.07 for `n_R_o` and `moved` and 1.85 to 2.04 for `lost`; the error at
    the finest step over the size tolerance was 0.20 to 0.49 (event times) and 0.16 to 0.39 (rows and books). With
    the counted rounding bounds and the criteria's own fit (the used differences alone), 4 or 5 of the 5 step
    differences were resolved for every judged readout (3 are needed), the third by at least 35 times its threshold,
    and the orders were 1.97 to 2.18 (`n_R_c` 2.05 to 2.18) and the errors over the tolerance 0.20 to 0.48 (2 seeds
    of each order). In the W5 kind, the criteria's own fit (invented numbers, 3 seeds of each order, every judged
    readout, `xi_2` among them): 4 or 5 of 5 resolved, the third by at least 14 times its threshold, orders 1.87 to
    2.16, errors over the tolerance 0.15 to 0.33.
  - The gene unit's chain alone (invented numbers; the registered horizon, sample grid and ladder): the first step
    difference of `made` and of `exits` was half the counted bound's resolution threshold, so none of the five was
    resolved. The differences fall 8-fold per halving and the threshold doubles, so three resolved ones need a first
    difference above 256 times its threshold. W6 therefore judges them by size alone (`at_rounding`). The registered
    chain was not run: the references' sizing checks the name (CRITERIA.md §4.2), and a name that is wrong is a
    fault before the tag.
  - No registered volume, rate, amount, conductance, potential or seed equals the same quantity of an emulation, the
    R rows' trace apart (the horizon, the rungs and the sample grid are shared, as said), and no registered world
    was run on any engine or emulation. The registered W6 values were chosen by hand from the laws (closed forms,
    steady-state estimates and the domain checks, no time stepping).
- **`minimum_events` and the 160 draws per copy** were chosen knowing the emulations' event counts (per copy or
  site: W5 kind, 21 to 33 in the design note's probes, 33 to 38 in the emulations with 2 subunits and 55 with 4; W6
  kind, 71 in the design note's probe, 25 to 38 in the emulations with 2 subunits and 142 to 149 with 4). The minima
  of 736f0565 (W5 12 per copy and 160 in all, W6 10 and 120) are unchanged, and the references' counts are judged at
  C0.
- **A premise check:** `make_draws.py`'s table was compared with the engine's own stream function
  (`cells.numerics.counter_streams`) at all 24 copies × 160 pairs: no differences. The seeds are the registered ones
  and unchanged.
- **The rounding counts.** LAWS.md §7's event-time count was written with the engine's own clock and hazard sum in
  view (the population operator's half-step, the composite's clock), and the row count from its increments. **The
  earlier version of this document said nothing of the engine source appears in the folder; that was wrong for the
  counts.** They are described in words there, and no engine name or code is.
- **Engine source read by the author:** the population operator, the reactions' and the gene unit's laws and
  half-steps, the composite's step, the streams. LAWS.md restates laws the sheet and the operators' pages declare.
- **The exemplars,** read in full or in the parts that matter: FR-38's second registration (its protocol, spec
  folder and amendments 1 to 6), the routing spec (tag `liquid-routing-amendment-5-2026-11-25`) with its five
  amendments, FR-43 part 2's criteria and part 3's registration. No registered result, reference value or judged
  table of any comparison was opened.
- **The audit:** the lead's rulings on the auditor's findings, in words
  (`/mnt/workspaces/Cells/d172-restructure-20261115-01/fr43-spec-audit-rulings.md`, and for the second pass
  `fr43-spec-audit-rulings-2.md` beside it). The auditor's folder and report were not read, as ordered. The advisor
  reviewed the plan and the draft (two rounds, applied); a third round timed out, and the audit followed; a fourth
  round, on the revision after the rulings, was applied.
- **The registered worlds have been run by no engine or emulation.** Their inputs are declared values. Their draws
  were generated by the stated rule (`draws.json`), without running any of the worlds.

## 11. Decisions

The user decided the note's four questions on 25 November 2026: (1) split writers, (2) one judged run over W5, W6
and W5′ (`W5-exact` here) with code-blind references, (3) part 3 closes at this landing, with the population at
changing volume logged as its own request, (4) the declared general rule. The lead ruled L1 to L4 (the note's §7).
The build waits for the legacy cleanup (the user put every other build on hold). D315, D328, D336, D370, D373, D377
and the design note's §5.3 are the basis. A later amendment in this folder governs where it differs.

**The lead's rulings on the first report (25 November 2026):**
1. Eight copies as separate runs: accepted, with the cost stated (§7) and the fallback (one site) not taken. A W5
   copy is its own run for one entry shape; the reason given in the report first (the rate bound) holds for W6 only.
2. Criteria derived, not set from a development run: accepted.
3. W6's placement near its limit: accepted as registered; the build measures it at parse, and a refusal means a
   dated amendment before any run.
4. A judged run that stops on the engine's own check fails (D): accepted.
5. Two subunits and the weak class E: accepted, and stated (CRITERIA.md §11).
6. W6's values that coincided with the emulation's: moved off them, with the placement recomputed. W5's copies stay
   separate runs.

**The lead's rulings on the audit** (V1 to V12, E1 to E9, W, the readings decided) are in this revision; what each
became is in the author's report of the revised head. Three are read so that they can be executed, and the report
says so first: E3 leaves out the gene unit's `made` and `exits`, which are the same in both orders by construction,
and uses two recorded rows in W5-exact, which has no S entry; E1's multiple is of the carrying identity's bound (a
book's own bound is proportional to the book, so every non-zero book would exceed any multiple of it); V10's "after
a retry its score stands as first" is read entry by entry (a plant's entry whose honest entry was inconclusive at
the first pass is scored after the retry if it then passed), since read of the whole plant it would leave every
plant that names the retried entry unscorable, and that arm could never pass.

**Added by the author beyond the rulings' words,** each to keep an honest run from being inconclusive, or a fail
from being hidden: C0 checks the name of an at-rounding entry (fewer than three used differences), the pair's
expected ratio to its threshold and W5-exact's running check, from the references' side; the resumed run's
`events_total` is compared with the uninterrupted run's; a refused run's E and R entries are judged on what it holds
(the two exceptions of §4 of CRITERIA.md apart).

**The lead's rulings on the second pass over 36d7f686** (N1 to N12 and the cosmetics) are in this revision. What was
read or derived:
- **N1.** An entry of a run that is missing or refused by any row is unformed, provenance and a shared record hash
  included. The first ruling on provenance (V6) called such entries formed; "a miss stands" is kept.
- **N2.** Read of the Lie plant's runs and the resumed runs: their echo equals their honest run's apart from
  `variant`. A record plant's edited copy is no run of a table, so it shares no hash with one.
- **N3.** P3 is caught inside [p − 3/2, p − ½]. The upper end is the former boundary, 1.5; the lower end is the same
  half window about p − 1. C0 asks a quarter inside both ends.
- **N5.** Put at the resumed run's check, its row in CRITERIA.md §4 and TABLE.md's definition of `first_index`.
- **N8 to N11 are fixed, N12 is declared** (CRITERIA.md §11). N8 asks the same of W5-exact's two rungs in the
  references' sizing and C0. N9's factor is one half of the references' published book, the midpoint between its
  size and absence; the sizing enters no rule. N10 names P14's four starts in `inputs.json`.
- `inputs.json` gains the half (`fraction_of_reference`) and P14's four checks. No other number, no class and no
  window of an honest entry moved.

**The author's own skeleton was run again on the revised inputs** (25 November 2026, 13:48 UTC; scratch, its own
fabricated tables, no judge): all six families pass honestly; the pairs and W5-exact's two rungs differ; every fault
row, the restart rows, the running check and each of N1 to N10 come out as the text says; each of the eight wrong W6
engines of the author's list fails in both families. The skeleton shares the author's reading.

**Questions to the lead before the criteria tag** are in the author's report to the lead, not here.
