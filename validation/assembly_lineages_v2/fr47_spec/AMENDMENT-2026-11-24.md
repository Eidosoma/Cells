# Amendment 2, 24 November 2026: C8's scope, and five plant readings

This amendment follows the code-blind references (`fr47-references`, 9661297e) and the lead's design
conclusions from them (`docs/FR47_SHELL_EXCHANGE_PROTOCOL.md`; D323).
- It is value-silent: words only, with no result.
- Its engine statements were checked against the engine's code.
- **No band changed.**
- **One criterion's definition changed, C8,** for a design flaw that the references exposed (§1).
  CRITERIA.md carries the change, disclosed here.

## 1. C8: the tracer observables only, and reported, not claimed

- **Reported, not claimed.** At M = 128, no rung of W2 resolves the representation gap. Resizing
  W2 cannot make it resolve within any replica count the protocol can afford.
  - By the protocol's own rule (CRITERIA C8: measured only over three or more resolved rungs), C8's
    slope is therefore **reported from the reference alone, and not claimed**.
  - W2's sizes are kept as registered.
- **The design flaw.** C8 took each rung's gap at its largest |gap| pair over S@pool, S@lumen,
  G@wall and H@wall.
  - The wall forms' gap comes from the limit's switching factor (N_w + 1)/N_w (SPEC.md §3.3). In
    molecules it is of order N_g/N_w, which does not fall with N_g.
  - At the top rung the largest pair is therefore a wall form, and a slope over "largest pairs"
    bends away from −1 by construction.
- **The rule, now in CRITERIA.md.** C8 is restricted to the tracer observables, S@pool and S@lumen.
  - The largest pair per rung is the largest |gap| over those two, with ties going to S@pool, then
    to the earliest time.
  - The slope is reported on ln|gap|, with its resolution table, and nothing in it is claimed as
    measured.
  - C6 and C7 still judge G@wall and H@wall as before.

## 2. The five plant readings

- **P9: the whole term.** "F_cont at a zero place taken as one molecule's" is the place's entire
  Stirling term evaluated at n = 1, that is μ° − ln X − 1.
  - The registered reading is this whole term, the agent's reading.
  - The narrower reading, n·ln n − n alone, is not registered.
- **P4: frozen after the full wash, honest before it.** Confirmed.
  - **After the full wash.** The old factored form gives the entry's flux zero when the pool is
    empty, so both tracer places stay where the wash left them.
  - **Before the full wash.** The plant's only other effect is at the empty lumen at t = 0. The old
    form errs there at the first stage alone, by an amount far below C1's bound. So the planted
    reference is the honest one before the full wash.
- **P8: the heat at the planted kept count, with the declared f.** The planted exact withdrawal
  samples each pool molecule at f².
  - The engine books its mixing heat against the physical, declared f, not the sampler's
    (`cells.pool_withdrawal@1`'s booking).
  - So the planted heat is −k·ln(1 − f), with k the planted kept count. This extends the first
    amendment's statement for P2 to P8.
- **P6: ties go to the earliest.** Confirmed. For every (plant, criterion) entry, a tie in distance
  goes to the earliest time or stop, then to the first observable in the spec's order.
  - So P6's entry names 10.5 s, which ties with the horizon.
- **P3: the replacement-only variant stays out.** Confirmed. That variant's largest-distance entry
  is the registered plant's, so it adds nothing. It is not written to the files.
