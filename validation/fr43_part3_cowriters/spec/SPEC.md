# The worlds, the runs, and what the references compute

Read `README.md`'s rules first. `inputs.json` governs the numbers: no number of a world is repeated here.

## 0. Units

Amounts in fmol, volumes in pL, concentrations in mM (fmol/pL), times in s, conductances in pL/s per active unit. A
rate constant is 1/s, or 1/(mM s) where two concentrations are multiplied, or (a read's rate) 1/s at 1 mM: φ = c/(1
mM) (LAWS.md §1). Every declared real is a decimal literal, and both sides use its nearest double. **What starts at
zero, and what does not:** no row's start amount is zero (R starts at a trace of 10⁻¹² fmol). The machines start all
free, every stage complex at exactly 0, and every book at exactly 0 (LAWS.md §3, `inputs.json`'s `machines_start`
and `start`).

## 1. The worlds

| World | Co-writer beside the population | Read | Judges |
| --- | --- | --- | --- |
| `W5` | The reactions X → S, S + Y → W in the cell | `assemble` reads S in the cell; the transfer moves S | Event times, shared amounts and the writers' books at second order |
| `W5-exact` | The same reactions | none (constant rates) | Event times, exact at every step; the books by identity |
| `W6` | The gene unit making and degrading R, drawing N, releasing Pi and returning M | `assemble` reads R in the cell; the transfer moves R | Event times, shared amounts and the gene unit's books at second order; the gene unit's own totals by size; its monomers, its product and its machines by identity |

- **Copies.** Each world holds 8 independent copies (LAWS.md §0): the same declared numbers, and its own seed for
  each (`seeds[c]`), so 8 paths of one world, not 8 worlds. Nothing couples two copies. Each copy is its own run's
  world (the lead's ruling: one entry shape, §11 of the protocol).
- **Why copies.** A site's event times carry the split error of earlier events, and the order of one path scatters.
  Pooled over the copies, whose paths are independent, the fitted order is smooth (LAWS.md §5). Their number was
  sized by the author before any run, on emulations of the split (numbers and seeds of their own, and what coincides
  is in the protocol's §10); the references size it again for the registered numbers (§5), before their tag.
- **Both declared orders.** Every judged world runs with the co-writer declared first and with the population
  declared first. Each is a family with its own runs. W6's `made` and `exits` do not depend on the order.
- **Structure of a copy:** one cell, one finite outside node, one patch between them with one site of 2 subunits.
  Nothing else in the cell or the node moves a row of the world. The engine also holds an inert background and a
  held bath, and the references never see them. The engine side confirms that nothing else writes a row of the
  world.

## 2. The steps and the runs

`inputs.json` lists every registered run (`runs`): name, arm, world, which writer is declared first, copy, step,
role and variant. `judged` runs are compared, `support` runs are the restarts, `plant` runs carry a declared change
of the driver. There is no other role, and no run is meant to be refused or to stop.

- **Steps.** `W5` and `W6` run at n = 6 steps, each half the last (`rungs_s`), `W5-exact` at two (a factor 4 apart).
  Each of a judged world's `retry_rung_s` (the next halving, the finest of the n + 1) is run only when owed
  (CRITERIA.md §7).
- **The restarts:** `inputs.json`'s `restart` names the run they resume and the checkpoint's time: one of `W5`, one
  of `W6`.
- **The Lie plant:** `W5 reactions-first`, the three finest rungs, every copy, with the second halves of each step
  run in declared order in place of the reverse (the driver's patch; CRITERIA.md §6).
- Every sample time, restart time and horizon is a multiple of the world's coarsest step.

**Placement.** The engine's definition checks, at parse, that the largest propensity times the step is at most 1,
where it bounds the propensity (the declared material of the species read, over its volume, plus what the operators
can produce where that is bounded, over the horizon). `inputs.json`'s `placement` gives, for each world, that number
from the declared numbers and what it is based on. **W6** rests on the gene unit's largest production, κ × machines,
and the build adds a check the author has not seen: W6's figure is computed, not measured. **W5:** S is also made
from X without a static bound, so after the build the definition leaves its site unchecked; its figure counts the
declared S alone. A world the built engine refuses at the definition is changed by a dated amendment (its rates or
volumes) before the registration tag, never by weakening the check.

## 3. What to compute

For each copy of each world, the exact coupled process (LAWS.md §4), to the accuracy of §4:

1. **Every event** k = 0, 1, … with t_k ≤ T: its time, channel, and the counts after it. From this list K_c is the
   number of events with t_k ≤ T − g h_1, g = `inputs.json`'s `guard_steps` and h_1 the world's coarsest judged
   step: the judged set of events. K_c is counted, not chosen.
2. **At every sample time** (`samples_s`): the rows and the books of READOUTS.md §1, W5-exact's included.
3. **The planted series** of LAWS.md §9, on the same samples and event indices, in the same layout, for every family
   the plant's `families` names (`both`: every family of its world).
4. **The sizing** of §5, and the checks of §9.

**Invented inputs** (§8) are written first.

## 4. Accuracy, and the classes

- **The reference is the exact process.** Its step-free solution carries `accuracy`, an absolute bound: event times
  10⁻¹¹ T, every row and book 10⁻¹¹ × its scale (READOUTS.md §2). It is checked by a second, different integration
  (another method, at least 10 times tighter), and by a closed form where one exists (LAWS.md §4's decimal sums for
  W5-exact, where the accuracy is at most 10⁻¹⁵ T). T is the world's `end_s`.
- **W5-exact's rows and books are published, and no judgement compares them with the engine's** (they enter the
  run's own identities only).
- **The classes** of the judged entries are READOUTS.md §3's and no others. The reference file lists the judged
  readouts of its world, and nothing else, under `classes`.
- **A reference file that departs from its accuracy** is refused by C0.

## 5. Sizing, before any run

With the declared split of LAWS.md §5 (your own code, on the registered numbers and draws), for each judged family
and each S readout, at every rung and at the retry's:

- **The expected honest statistics.** The n − 1 step differences d_j, the number of used ones, the fitted order q,
  E_n and the expected τ, all by CRITERIA.md §3.3, with the engine's series replaced by the model's. Every S readout
  not named in `at_rounding` must be resolved (at least three used differences) and have q within [p − 0.4, p +
  0.4]; a named one must have fewer than three used differences (its name is checked); and every S readout's E_n
  must be at most its τ. The gene unit's third-order error comes from the model's SSPRK(3,3) (LAWS.md §5).
- **The plants' sizes and margins** (CRITERIA.md §6), per plant, per family and, for P4, per family with its shift:
  the distance, the expected tolerance and their ratio. A margin below 10 (1 − 10⁻⁹) is a fault. P3's expected order
  over its three rungs is at most p − ¾.
- **The pairs** (CRITERIA.md §3.5): for each world and each readout of its `orders_differ`, the pooled root mean
  square of the difference between the model's two declared orders at h_1 (W5-exact's too), over 10 e_round(h_1): at
  least 10, so that an honest pair is seen to differ.
- **The power of W6's co-writer plants** (P11 to P15) is yours to compute, and the only place it can be sized. The
  author states no margin for them: this folder is value-silent.
- **The margins' inputs** (the sizing) are under `sizing` (§7). It is used by C0 alone (CRITERIA.md §4.2). It is
  never a tolerance, a scale or a verdict.

**What C0 requires of it** is in CRITERIA.md §4.2. A world that misses one is changed by a dated amendment before
the registration tag, with the reason and the disclosure that the sizing showed it. A change of a seed is an
amendment of the registered inputs.

## 6. Where a run's events, rows and books come from in the engine

The contract is TABLE.md. A row is the engine's amount at the sample. A **book** is the writer's own cumulative
account (never the difference of two rows). Each is signed as READOUTS.md §1 says.

## 7. The reference files

One JSON file per world, `reference_W5.json`, `reference_W5-exact.json`, `reference_W6.json`, with bytes fixed by
the values (sorted keys, fixed separators, no timestamps, floats as JSON numbers of `repr` form):

```json
{"kind": "fr43 part 3 co-writers reference, version 2", "world": "W5", "inputs_sha256": "...",
 "copies": [{"copy": 0, "seed": 0,
   "events": {"K": 0, "K_all": 0, "time_s": [0.0], "channel": ["assemble"], "counts_after": [[0, 1]],
              "accuracy_s": 0.0},
   "samples_s": [0.0],
   "series": {"n_S_c": {"value": [0.0], "accuracy": [0.0]}, "...": {}},
   "checks": [{"name": "...", "residual": 0.0, "bound": 0.0, "passes": true}]}],
 "scales": {"n_S_c": 0.0, "...": 0.0},
 "classes": {"t_events": "S", "...": "..."},
 "planted": {"P1": {"W5 reactions-first": [{"copy": 0, "events": {}, "series": {}}]},
             "P4": {"W5 reactions-first": {"shift_s": 0.0}}},
 "sizing": {"W5 reactions-first": {"t_events": {"d": [0.0], "used": 0, "q": 0.0, "E": 0.0, "est": 0.0, "tau": 0.0}},
            "mutant": {"W5 reactions-first": {"E": [0.0], "q": 0.0}},
            "pair": {"t_events": {"rms": 0.0, "threshold": 0.0, "ratio": 0.0}}},
 "plants": [{"plant": "P1", "family": "W5 reactions-first", "check": "t_events", "distance": 0.0,
             "expected_tolerance": 0.0, "margin": 0.0, "no_margin": false}],
 "draws_check": {"identical": true, "entries": 0},
 "reported": [{"name": "...", "value": 0.0}],
 "provenance": {"revision": "...", "python": "...", "numpy": "...", "scipy": "...", "sha256_of_this_file_excluded": true}}
```

- Numbers shown are placeholders of the right type, not values. Keys the judge does not know are ignored, and a
  missing registered key is a fault (CRITERIA.md §4.2).
- `classes` holds the judged readouts of the world (READOUTS.md §1's names), and nothing else: those of class S, and
  in W5-exact `t_events` alone, of class R. The E entries, `start`, the identities and the pair are not readouts and
  are not listed. W5-exact's `series` holds its rows and books (published, not judged).
- A copy's `events` list holds the first K_all events. K_all is the number with t_k ≤ T (published for information),
  K is K_c of §3. `channel` is the channel's id, `counts_after` the `[free, active]` counts after the event.
- `planted` is keyed by the plant's `id` in `inputs.json` (`P4-W6`, `P10-W6`, …). For a reference plant of a world
  it holds, per family named in the plant's `families`, a list of copies' events and series; P4 holds the shift of
  each family, and the judge forms its planted times from `shift_s`. A plant whose effect does not depend on the
  declared order may hold one copy list under both families.
- `sizing`: for each family and each S readout, the n − 1 `d` (in the order of `rungs_s`), the number of used
  differences, the fitted `q`, `E` (E_n), `est` and `tau`; `mutant` (P3) with its three rungs' `E` and its `q` (the
  slope of ln E against ln h); and `pair` per readout of `orders_differ` (its threshold is 10 e_round(h_1)).
- A `plants` entry names its plant, its family (null for a record plant) and the check it is measured at.
- `reported` is defined: values this folder asks for that neither C0 nor a verdict reads. It lists K_all per copy,
  the pairwise orders and the coarse-rung errors of the sizing, and the number of draws used per copy, each by name.

**The draws.** `draws_check` records the comparison of LAWS.md §6's premise check: `identical` true, and the number
of entries compared. A false one stops the references' tag.

## 8. The invented files

- `reference_invented.json` and `inputs_invented.json`, and `draws_invented.json` (the same generator's rule on its
  own seeds, a draws table of its own): the same layouts as the registered ones, for worlds of your own invention,
  in the kinds of §1 (a reactions world with a read, one with constant rates, and a gene world), with 4 copies each,
  your own numbers, and a full set of runs (judged, restart, Lie plant, refused, stopped, retry).
- **No number of it equals a registered number of the same kind** (a volume, a rate, an amount, a conductance, a
  seed, a horizon, a rung, a sample time, a count of copies of a template or of machines; a zero, `c0_mM`, and
  structural integers such as the subunits of a unit state are not of a kind). The check is mechanical: a file of
  the registered numbers is compared, and an equality is a fault.
- **Entries at rounding are named** in its `at_rounding` (per world), as the registered set's are, where the sizing
  shows fewer than three used differences. Every other S entry must be resolved, or the seed or the number is
  redrawn before the invented set is used.
- **The retry is reachable:** `inputs_invented.json` lists the retry runs of one family (its `retry_rung_s`, which
  exists), and a copy of the invented table in which that family's coarsest rung is perturbed so that its order
  leaves the window (a judge's rehearsal input) makes the retry owed, so that the retry's scoring path is run.
- The builder runs exactly `inputs_invented.json`'s runs through the registered exporter (CRITERIA.md §10). They
  keep the placement of §2 and a dt·a_0 of at most one quarter.

## 9. The checks before the references' tag

Each is computed in the references' own arithmetic, and its residual and bound are recorded under `checks`. All must
pass:

1. **Draws:** the table regenerated from LAWS.md §6's rule equals `draws.json` bit for bit, for every copy of every
   world.
2. **Closed-form relaxation:** the transfer alone between two pools (LAWS.md §1's equations) equals its exponential
   relaxation to 10⁻³⁰ relative in decimal.
3. **W5-exact:** the events' times equal the decimal sums of LAWS.md §4 to 10⁻¹⁵ T.
4. **Conservation:** the identities of READOUTS.md §4 on your own rows and books, to the accuracy of §4, in every
   world.
5. **The start state** of LAWS.md §3, and `inputs.json`'s `start` and `machines_start`.
6. **A two-method agreement** for every row, book and event within the claimed accuracy.
7. **The sizing's order.** For each judged S readout not named in `at_rounding`, its expected order is resolved and
   within [p − 0.4, p + 0.4]; for a named one, fewer than three differences are used; for every one, `E` is at most
   the expected `tau`.
8. **The minimum counts** of `inputs.json`; no event of any copy within 10⁻⁹ T of T − g h_1 (K_c must not depend on
   the integration error); K_all less than `pairs_per_copy` for every copy; and, in W6, the domain of LAWS.md §3's
   affinities, x ≤ −1 and y ≤ −1, at every time of the run (so that the world is inside the engine's declared
   domain); and, in W5-exact, the running check of CRITERIA.md §3.2 on your own ξ_1, ξ_2 and moved, at every rung's
   S.
9. **The sizing of §5** is complete and inside the requirements of CRITERIA.md §4.2, the plants' margins included.
