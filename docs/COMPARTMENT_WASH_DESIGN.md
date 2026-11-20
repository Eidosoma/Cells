# A timed partial wash of a finite compartment (FR-27): design note

**Status: proposed, 20 November 2026, by the operators owner, for the lead and the user.** Desk work
only (D142): options, a recommendation, what stays bitwise, files, tests and a price, before any
code. It describes a general feature (D144). Nothing is built.

**The request** ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md) FR-27; D245, from an outside user's
review): at a declared time, collect a fraction f of a finite compartment's well-mixed liquid into
a recorded sample, refill the same volume with a declared buffer, and leave bound material in
place. The removal, the supply and the free-energy change are booked exactly at the event.

**The requirement from D245:** state the semantics against FR-20's pool replacement
([ASSEMBLY_WASHOUT_DESIGN.md](ASSEMBLY_WASHOUT_DESIGN.md)), so that the two are not two laws for one
mechanism (D175, D210). §2 does so.

**Engine models it would run:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with a new
operator `scheduled_liquid_exchange@1`, beside `site_occupancy@1` and the species operators.

**Code read at 2ae89b5e** (main). FR-20's operator was read on branch `ol-fr20-replacement`.
**S** marks our own reading or derivation.

## 0. Summary

| | |
| --- | --- |
| **Today** | No operator changes a finite node's contents at an event. The bath schedule sets held baths only (`bath_schedule.py:178–182`), and FR-23 keeps finite compartments out (D244). The review applied the wash on the host, between two runs, so each run kept its own books |
| **The mechanism** | One definition, a liquid exchange of a compartment (§2). FR-20's pool replacement is its whole-exchange execution in exact counts. This operator is its deterministic execution, for any fraction |
| **Recommended** | Option A: a new cell-family operator, `scheduled_liquid_exchange@1`, with an event map, exact bookings and the review's world as its acceptance (§3, §4) |
| **Bitwise** | Every existing world, at all three levels: it is a new operator |
| **Price** | Development 2–2.75 agent-days, excluding gates; the options are priced in §9 |

## 1. What exists today

- **Cell family.**
  - The bath schedule (FR-10) sets a held bath's composition. A held bath is a reservoir, and "a
    finite node … cannot be clamped" (`bath_schedule.py:178–182`).
  - FR-23 (D244) admits a held-bath dose beside binding sites. A dose into a finite compartment is
    named as not covered.
  - No other operator changes a finite node's contents at a declared time. The review therefore
    stopped one run, halved the free tracer on the host, recorded the sample and started a second
    run, so the books could not span the wash.
- **Assembly family.** FR-20's `cells.pool_replacement@1` (approved in D240; on its branch):
  - at declared times (> 0), the pool's finite places take a declared composition, in integer
    counts;
  - every assembly is kept as it stands, bound tracer included; held places, c_ext and the pool's
    volume are unchanged;
  - the sink takes F(old pool), the schedule's work column takes F(fresh pool), and the removed and
    supplied counts are recorded. It draws nothing;
  - a pulse is a replacement with tracer-containing solution, not an addition. An addition is a
    separate mechanism, a dose (its Q2).

## 2. One mechanism, two executions

**The definition: a liquid exchange of a compartment.** At a declared time, a fraction f in (0, 1]
of a compartment's well-mixed liquid is drawn off, and the same volume of a declared buffer is
added. The compartment's volume is unchanged.
- **Every dissolved species:** n_s → (1 − f)·n_s + f·V·c_buf,s.
- **The drawn-off liquid is a sample,** f·n_s per species, recorded. The buffer supplied,
  f·V·c_buf,s per species, is recorded too.
- **Everything not dissolved in the liquid is kept as it stands:** bound material on sites,
  assemblies, membranes and their lumens.
- **Held compositions are not touched.** A reservoir is not a compartment; changing one is the bath
  schedule's mechanism.
- **Free energy (S).** For an ideal solution F is homogeneous of degree 1 in (n, V), so the liquid
  before the exchange splits exactly into the part kept and the sample.
  - The sample leaves with F(sample) = f·F(before), booked to a sink.
  - The buffer arrives with F(buffer), booked from its source.
  - Mixing the kept liquid with the buffer dissipates H_mix = F(kept) + F(buffer) − F(after),
    which is never negative.
  - So F(after) − F(before) = F(buffer) − F(sample) − H_mix, and the ledger closes.
  - At f = 1 nothing is kept, so H_mix = 0, and the booking is exactly FR-20's: the sink takes
    F(old pool), and the work column F(fresh pool).

**The two executions:**

| | Assembly family: exact counts | Cell family: deterministic amounts |
| --- | --- | --- |
| f = 1, a whole exchange | FR-20's `cells.pool_replacement@1`, exactly. The fresh pool is the buffer's counts in the pool's volume, and the sample is the whole old pool | This operator, at f = 1 |
| f < 1, a partial exchange | **Binomial thinning:** each molecule of the liquid is drawn off independently with probability f. A draw on the schedule's stream, so an extension of FR-20's operator, later | This operator: the deterministic amounts, the binomial's mean |
| "Tracer-free" | A count can reach 0 | The buffer at the species' trace: amounts stay at or above the trace (D150's rule) |

**Why this is one mechanism, not two (D175, D210).**
- D175 keeps representation and numerical method apart: "Deterministic and stochastic execution
  have explicit semantics", and "Reaction declarations are reused where valid"
  (ARCHITECTURE.md, Levels of detail). The precedent is D152's declaration, which has two
  executions: deterministic on @3's nodes and stochastic in assemblies
  (ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.3).
- Here the definition above, its fields (time, fraction, buffer composition, compartment) and its
  records (sample, supply, the sink's F, the source's F, the mixing heat) are the same in both
  families.
  - The deterministic execution is the large-count limit of the binomial one (**S**). The difference
    is the binomial variance, which is the reduction's declared error budget in D175's sense.
  - Neither execution is a second mechanism.
- **What differs is only execution:**
  - continuous amounts against integer counts;
  - the partial case, a scaling against a draw;
  - the trace floor against a possible zero.
- **The declared key.** D175's "what it represents" key is reserved, not built (ARCHITECTURE.md).
  Both operators would declare the same one, "the liquid exchange of a compartment". With one
  representation per scope, a compartment is exchanged by one operator only.
- **What it is not:**
  - **the bath schedule:** setting a reservoir's composition, booked against the reservoir;
  - **a dose or addition:** material added with nothing removed, FR-20's Q2 (b);
  - **a transfer:** FR-20's serial transfer, which samples the assemblies.

## 3. Options

| Option | What | For | Against |
| --- | --- | --- | --- |
| **A** | A new cell-family operator, `scheduled_liquid_exchange@1`: an event map that executes §2's definition deterministically at finite nodes | One operation with its own books; the shared definition; composes with sites and the species operators | A new operator to register and test |
| B | The bath schedule extended to finite nodes | One fewer operator | A clamp of a reservoir and an exchange with a compartment are different mechanisms with different books. It would mix two meanings under one law (D147) |
| C | A dose into a finite node, with nothing removed | Simple | Another mechanism, FR-20's Q2 (b): it is not a wash, and it moves the volume or ignores it |
| D | Today's host restart between runs | No code | Two sets of books, the sample kept outside the engine, and the sites' state passed through the declared initial occupancy |

**Recommended: A.**

## 4. The design (option A)

**The declaration and the schedule:**
- **The declaration:** the finite nodes it may exchange, each by ID.
- **The experiment key `liquid_exchange_events`:** a list of `{time, node, fraction, buffer_mM}`.
  - The time is on the dt grid, with 0 < t < end, and times increase strictly per node.
  - The fraction lies in (0, 1].
  - `buffer_mM` gives a concentration for each exchanged species.
- **Version 1 exchanges neutral species only.** Ions are left as they are, since the buffer is
  taken to have the compartment's own ion composition. So the exchange is electroneutral by
  construction; neutral formula units for ions are a later option, as in FR-10.
- **A buffer concentration below a species' trace is refused,** since amounts never fall below the
  trace. Its trace is the "tracer-free" buffer.

**The event map,** at the start of the step leaving t, at each node with an event:
- it sets the node's amount increments so that n′ = (1 − f)·n + f·V·c_buf;
- it records the sample, f·n, and the supply, f·V·c_buf, cumulatively and per event;
- it records the free-energy split: the sample's F, the buffer's F and the mixing heat. Each is
  computed with the adapter's own `species_chemical_free_energy_pJ` (`pump_composite_adapter.py:844`),
  as replacement and the bath schedule book theirs;
- every other field is selected, never offset by zero, so a step with no event is idle, bit for bit.

**The books:**
- **Material:** @3's outside ledger at the node gains removed − supplied (D150's sign). The material
  balance with sites is then: free + bound + the cumulative sample − the cumulative supply is
  constant, to rounding.
- **Energy:** the operator's own term closes the composite's energy ledger at the event row.
  - The records carry no heat or work suffix, so they stay out of the IMEX flow bound, as the bath
    schedule's dose records do (BATH_SCHEDULE_DESIGN.md §2.2).
  - Whether the mixing heat should also enter the dissipation check is a question (§10).
- **Charge:** none in version 1.

**Composition:**
- **Composes with:**
  - @3;
  - `site_occupancy@1`: its bound material is kept. The sites read the node's state, which the
    event changes before their half-steps;
  - D150's exchange and turnover, and D152's reactions at the node;
  - the bath schedule, at other, held nodes;
  - the coupling operator, injection and replacement@1.
- **Refused in version 1, each at the definition with its reason:**
  - a held bath, which is the bath schedule's;
  - water: the volumes are declared;
  - a compartment's node (FR-1), a lumen's node and an insertion onset node;
  - **a face at an exchanged node (S).** A wash is a step in the node's concentration, and @3's face
    booking of such a step is FR-10's onset limit, measured only for held baths. It opens after a
    measurement, as FR-10's step rule did.
- **No door S interplay.** The operator writes state, the node's amount increments, through its
  `ENTITY_WRITES`, and provides no view field.

**The records** have the same names and meanings as FR-20's. FR-20's records are a removed and a
supplied count per place, the sink's F and the source's work. The summary lists each event's sample
per species, for a detector's post-processing.

## 5. What stays bitwise

- **Every existing world, at all three levels** (values, programs, structure). It is a new operator.
- **FR-20's operator and the assembly family are untouched.**
- **What changes:** the composition matrix gains this operator's row and column.

## 6. Files and owners

- **The operators owner:**
  - `src/cells/operators/liquid_exchange.py` (new). A new operator module registers with no edit to
    `operators/__init__.py`;
  - `validation/tissue/composition_matrix.py`: tags for its pairs;
  - `docs/PUMP_COMPOSITE.md`: regenerated, with its operator table row;
  - a world builder in `validation/tissue/` for the review's closed well;
  - the tests below.
- **Not touched:** `bath_schedule.py`, and the assembly family's files. FR-20's partial-exchange
  extension is the origin-of-life builder's, if it is ever chosen.

## 7. Tests (D224)

**A new test file for the new operator, `tests/unit/test_liquid_exchange.py`.**

*Tier 1: rows, in NumPy, with no compile:*
- **A refusal table:**
  - a held bath;
  - a fraction outside (0, 1];
  - a charged species;
  - a buffer below the trace;
  - water;
  - a compartment's, a lumen's or an onset node;
  - a face at the node;
  - a time off the grid or outside the horizon.
- **The event map on the review's well,** with 60 fmol free, 30 on the specimen and 10 on the wall,
  and f = 0.5:
  - the free amount becomes 30, and the sample record is 30;
  - every site field is unchanged, bit for bit;
  - the material and energy ledgers close at the event row;
  - f = 1 with a buffer at the trace is a whole exchange.
- **Planted errors:**
  - the sample taken after the exchange, so the material balance misses by f²·n;
  - the mixing heat dropped, so the energy ledger misses by H_mix.

*Tier 2: one compiled world:*
- **The world:** the review's sequence in a single run, the wash at t = 20 s.
- **What it checks:** the runner's host checks pass on every row, and free + specimen + wall +
  sample stays 100 fmol on every row.
- **Its seconds:** about 40–60 s.
- **Its reason:** it is the request's acceptance, one run with one set of books.

The composition-matrix test checks the regenerated block.

## 8. Acceptance, from the request

At the wash, in one run:
1. The compartment's free amounts become (1 − f)·n + f·V·c_buf, and the sample record equals f·n
   per species.
2. Bound material is unchanged, bit for bit.
3. The removal, the supply and the free-energy change are booked at the event: every ledger closes
   on the event row, and the material balance (free, bound, sample and supply) holds on every row.
4. In the review's example, 60, 30 and 10 fmol become 30, 30 and 10, with 30 in the sample, and the
   four sum to 100 throughout.

## 9. Price (S)

| Part | Agent-days |
| --- | --- |
| The operator: parse and refusals, schedule, event map, the free-energy split, ledger and magnitude terms, summary, run-view declarations | 1–1.5 |
| Its composition-matrix tags and the regenerated block | 0.25 |
| Tests: the tier-1 rows and the compiled world | 0.5–0.75 |
| Docs | 0.25 |
| **Development** | **2–2.75** |
| Optional: faces at exchanged nodes, after a measurement in FR-10's way | +1–1.5 |
| Optional: ions, by neutral formula units, with a neutral node | +0.5 |
| Optional: the sample delivered into a receiving node, so its own chemistry can continue | +0.25–0.5 |
| The assembly family's partial exchange, by binomial thinning (an extension of FR-20, the origin-of-life builder's) | +1–1.5 |
| A registered protocol, with code-blind references | +1–1.5 |

Calibration: FR-10's operator, also an event map with exact records, at 1.75 (range 1.5–2.5)
(BATH_SCHEDULE_DESIGN.md §5). FR-20's operator at 1.75–2.5 (ASSEMBLY_WASHOUT_DESIGN.md §8).

## 10. Questions

**For the user:**
1. **The shared definition** (§2): FR-20's pool replacement read as this mechanism's whole-exchange,
   exact-count execution, and this operator as its deterministic execution. Recommended.
2. **"Tracer-free" in the cell family** means the buffer at the species' trace. Accepted?
3. **The mixing heat:** a record with its own ledger term (recommended), or also part of the
   dissipation check?

**For the lead:**
4. Faces at an exchanged node are refused until measured (recommended). Or admit them with a runtime
   level check?
5. Neutral species only in version 1 (recommended)?
6. **The name:** `scheduled_liquid_exchange@1`, after its mechanism (D144); "wash" names one use of
   it.
