# The worlds, the runs, and what the references compute

Read `README.md`'s rules first. `inputs.json` governs the numbers: no number of a world is repeated here.

## 0. Units

Amounts in fmol, volumes in pL, concentrations in mM (fmol/pL), times in s, conductances in pL/s per active unit. A
rate constant is 1/s, or 1/(mM s) where two concentrations are multiplied, or (a read's rate) 1/s at 1 mM: φ = c/(1
mM) (LAWS.md §1). Every declared real is a decimal literal, and both sides use its nearest double. **No start amount
is zero.**

## 1. The worlds

| World | Co-writer beside the population | Read | Judges |
| --- | --- | --- | --- |
| `W5` | The reactions X → S, S + Y → W in the cell | `assemble` reads S in the cell; the transfer moves S | Event times and shared amounts at second order |
| `W5-exact` | The same reactions | none (constant rates) | Event times, exact at every step |
| `W6` | The gene unit making and degrading R | `assemble` reads R in the cell; the transfer moves R | Event times and shared amounts at second order |

- **Copies.** Each world holds 8 independent copies (LAWS.md §0): the same declared numbers, and its own seed for
  each (`seeds[c]`), so 8 paths of one world, not 8 worlds. Nothing couples two copies. In this registration each
  copy is one run's world.
- **Why copies.** A site's event times carry the split error of earlier events, and the order of one path scatters.
  Pooled over the copies, whose paths are independent, the fitted order over five steps is smooth (LAWS.md §5). The
  number was sized by the author before any run, on an emulation of the declared split with made-up numbers (the
  protocol's disclosures); the references size it again for the registered numbers (§5), before the tag.
- **Both declared orders.** Every judged world runs with the co-writer declared first and with the population
  declared first. Each is a family with its own runs.
- **Structure of a copy:** one cell, one finite outside node, one patch between them with one site of 2 subunits.
  Nothing else in the cell or the node moves a row of the world. The engine also holds an inert background and a
  held bath, and the references never see them. The engine side confirms that nothing else writes a row of the
  world.

## 2. The steps and the runs

`inputs.json` lists every registered run (`runs`): name, arm, world, which writer is declared first, copy, step,
role and variant. `judged` runs are compared. `support` runs are restarts. `plant` runs carry a declared change of
the engine's driver. There is no other role.

- **Steps.** `W5` and `W6` run at five steps, each half the last (`rungs_s`). `W5-exact` runs at two (a factor 4
  apart). Each of a judged world's `retry_rung_s` (the next halving) is run only when owed (CRITERIA.md §7).
- **The restarts:** `inputs.json`'s `restart` names the run they resume and the checkpoint's time: one of `W5` (copy
  0, one of the finer rungs) and one of `W6`.
- **The Lie plant:** `W5 reactions-first`, the three finest rungs, every copy, with the second halves of each step
  run in declared order in place of the reverse (the driver's patch; CRITERIA.md §6).
- Every sample time, restart time and horizon is a multiple of the world's coarsest step.

**Placement.** The engine's definition checks, at parse, that the largest propensity times the step is at most 1,
where it bounds the propensity (the declared material of the species read, over its volume, plus what the operators
can produce where that is bounded). Each registered run satisfies it by this arithmetic, from the declared numbers
(`inputs.json`'s `placement`): W5 at its coarsest step, W5-exact, and W6, whose shared row's largest production is
bounded by the gene unit's machines. A world the built engine refuses at the definition for this reason is replaced
by a dated amendment (its rates or its volumes) before the registration tag, never by weakening the check.

## 3. What to compute

For each copy of each world, the exact coupled process (LAWS.md §4), to the accuracy of §4:

1. **Every event** k = 0, 1, … with t_k ≤ T: its time, channel, and the counts after it. From this list the
   published K_c is the number of events with t_k ≤ T − g h₁, g = `inputs.json`'s `guard_steps` and h₁ the world's
   coarsest judged step: the judged set of events. K_c is counted, not chosen.
2. **At every sample time** (`samples_s`): the rows and the books of READOUTS.md §1.
3. **The planted series** of LAWS.md §9, on the same samples and the same event index, in the same layout.
4. **The sizing** of §5, and the checks of §9.

**Invented inputs** (§8) are written first.

## 4. Accuracy, and the classes

- **The reference is the exact process.** Its step-free solution carries `accuracy`, an absolute bound: event times
  10⁻¹¹ × T, every row and book 10⁻¹¹ × its scale (READOUTS.md §2), T the world's `end_s`. It is checked by a
  second, different integration (another method, at least 10 times tighter), and by a closed form where one exists
  (LAWS.md §8's decimal sums for W5-exact, where the accuracy is at most 10⁻¹⁵ T). `W5-exact`'s reference carries
  its events and their accuracy, and no rows: its rows are not compared with the reference (READOUTS.md §3), and its
  identities are judged on the run's own rows.
- **Every (world, series) entry carries its class** (READOUTS.md §3), fixed before any engine run exists, and no
  ruling or run changes it. A class is E, R or S. There is no other.
- **A reference file that departs from its accuracy** is refused by C0, as a fault.

## 5. Sizing, before any run

With the declared split of LAWS.md §5 (your own code, on the registered numbers and draws), for each judged family
and each S readout, at every rung of it and at the retry's:

- **The expected honest statistics.** E_j (CRITERIA.md §3.3) at each rung, the fitted order q over the rungs, the
  step differences, and the expected tolerance τ at the finest rung, all by CRITERIA.md's rules, with the engine's
  series replaced by the emulation's.
- **The plants' sizes** (CRITERIA.md §6): each plant's distance and its margin, and P3's expected order at the rungs
  it is run at.
- **The margins** (CRITERIA.md §6.2): for each plant and, for S plants, each family of its world, the distance, the
  expected tolerance and their ratio, a margin below 10 (1 − 10⁻⁹) being a fault. P4's shift is 10 times the
  family's expected τ.
- **Report every one** under `sizing` (§7). It is used by C0 alone (CRITERIA.md §4.2). It is never a tolerance, a
  scale or a verdict.

**What C0 requires of it** (CRITERIA.md §4.2): every expected q inside [1.6, 2.4] (a tenth inside the window), every
plant margin at least 10, the minimum counts of `inputs.json`'s `minimum_events`, and every E-class plant's distance
non-zero. A world that misses one is changed by a dated amendment before the registration tag, with the reason and
the disclosure that the sizing showed it. A change of a seed is an amendment of the registered inputs.

## 6. Where a run's events, rows and books come from in the engine

The contract is TABLE.md. A row is the engine's amount at the sample. A **book** is the writer's own cumulative
accumulator (never the difference of two rows): xi_1 and xi_2 from the reactions' per-route bookings, moved and the
transfer's own from the population's cumulative account, made and lost from the gene unit's own counters. Each is
signed as READOUTS.md §1 says.

## 7. The reference files

One JSON file per world, `reference_W5.json`, `reference_W5-exact.json`, `reference_W6.json`, with bytes fixed by
the values (sorted keys, fixed separators, no timestamps, floats as JSON numbers of `repr` form):

```json
{"kind": "fr43 part 3 co-writers reference, version 1", "world": "W5", "inputs_sha256": "...",
 "copies": [{"copy": 0, "seed": 0,
   "events": {"K": 0, "K_all": 0, "time_s": [0.0], "channel": ["assemble"], "counts_after": [[0, 1]],
              "accuracy_s": 0.0},
   "samples_s": [0.0],
   "series": {"n_S_c": {"value": [0.0], "accuracy": [0.0]}, "...": {}},
   "checks": [{"name": "...", "residual": 0.0, "bound": 0.0, "passes": true}]}],
 "scales": {"n_S_c": 0.0, "...": 0.0},
 "classes": {"n_S_c": "S", "t_events": "S", "...": "..."},
 "planted": {"P1": {"copies": [{"copy": 0, "events": {}, "series": {}}]}},
 "sizing": {"W5 reactions-first": {"t_events": {"E": [0.0], "used": 0, "q": 0.0, "est": 0.0, "tau": 0.0}},
            "W5 population-first": {}, "mutant": {"W5 reactions-first": {"E": [0.0], "q": 0.0}}},
 "plants": [{"plant": "P1", "family": "W5 reactions-first", "check": "t_events", "distance": 0.0,
             "expected_tolerance": 0.0, "margin": 0.0, "no_margin": false}],
 "draws_check": {"identical": true, "entries": 0},
 "reported": [{"name": "...", "value": 0.0}],
 "provenance": {"revision": "...", "python": "...", "numpy": "...", "scipy": "...", "sha256_of_this_file_excluded": true}}
```

- Numbers shown are placeholders of the right type, not values. Keys the judge does not know are ignored, and a
  missing registered key is a fault (CRITERIA.md C0).
- A copy's `events` list holds the first K_all events. K_all is the number with t_k ≤ T (published for information),
  K is K_c of §3. `channel` is the channel's id, `counts_after` the `[free, active]` counts after the event.
- The `sizing` entry lists, for each family and each S readout, `E` at each rung (in the order of `rungs_s`), the
  number of used rungs, the fitted `q`, `est` and `tau` at the finest, all by CRITERIA.md §3.3, and `mutant` (P3)
  with its three rungs' `E` and its `q`. A `plants` entry names its plant, its family (null for W5-exact's P5 and
  for the record plants) and the check it is measured at.
- Series names are READOUTS.md's. Every copy carries every series of its world (`W5-exact`'s `series` is empty).
  `classes` lists every readout of READOUTS.md §3 and its class for this world, the E entries included.

**The draws.** `draws_check` records the comparison of LAWS.md §6's premise check: `identical` true, and the number
of entries compared. A false one stops the references' tag.

## 8. The invented files

- `reference_invented.json` and `inputs_invented.json`: the same layouts, for worlds of your own invention, in the
  kinds of §1 (one of each: a reactions world with a read, one with constant rates, and a gene world), with 4 copies
  each, your own numbers, seeds, steps, horizon, samples and counts, none of which is a registered number, and a
  full set of runs (judged, restart, Lie plant, refused, stopped).
- They exercise every entry kind of CRITERIA.md: a class S entry that is resolved and one at rounding, a class R sum
  and an event time, the E trace, a retry (a set of runs at one finer step), a plant of each kind, and a fault of
  each row of CRITERIA.md §4. Each number of the rehearsal's honest runs must satisfy the registered rules with the
  margins of CRITERIA.md §10; a seed that the sizing shows to miss them is redrawn before the invented set is used.
- The builder runs exactly `inputs_invented.json`'s runs through the registered exporter (CRITERIA.md §10). The
  invented worlds keep the engine's placement (§2) and a dt·a₀ of at most one quarter.

## 9. The checks before the references' tag

Each is computed in the references' own arithmetic, and its residual and bound are recorded under `checks`. All must
pass:

1. **Draws:** the table regenerated from LAWS.md §6's rule equals `draws.json` bit for bit, for every copy of every
   world.
2. **Closed-form relaxation:** the transfer alone between two pools is LAWS.md §1's λ-relaxation to 10⁻³⁰ relative
   in decimal.
3. **W5-exact:** the events' times equal the decimal sums of LAWS.md §4 to 10⁻¹² s.
4. **Conservation:** in W5 the two sums of LAWS.md §2, in W6 the machines' identity and N + r Σ(chain residues) (in
   words: the reduced sums of the sheet's §4.8), to the accuracy of §4.
5. **A two-method agreement** for every row, book and event (primary and second method) within the claimed accuracy.
6. **The split model's own order** (sizing only): the emulation of §5 is second order. Over the five registered
   rungs and four further halvings, for each judged S readout of each family, the fitted slope of its error against
   the exact process is within [1.8, 2.2].
7. **The minimum counts** of `inputs.json`, and no event of any copy within 10⁻⁹ T of T − g h₁ (K_c must not depend
   on the integration error).
8. **The sizing of §5** is complete and inside the requirements of CRITERIA.md §4.2.
