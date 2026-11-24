# A timed partial wash of a finite compartment (FR-27): design note

**Status: decided in D246 (20 November 2026) and built on branch `operators-fr27`, in development,
by the operators owner.** Integration grants no acceptance (D143). §2 and §4 to §8 describe the
operator as built. The options (§3) and the price (§9) are kept as the desk note proposed them.

**The request** ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md) FR-27; D245, from an outside user's
review): at a declared time, collect a fraction f of a finite compartment's well-mixed liquid into
a recorded sample, refill the same volume with a declared buffer, and leave bound material in
place. The removal, the supply and the free-energy change are booked exactly at the event.

**The requirement from D245:** state the semantics against FR-20's pool replacement
([ASSEMBLY_WASHOUT_DESIGN.md](ASSEMBLY_WASHOUT_DESIGN.md)), so that the two are not two laws for one
mechanism (D175, D210). §2 does so, and D246 accepted it.

**Engine models it runs:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with the new
operator `scheduled_compartment_wash@1` (`operators/wash_schedule.py`), beside `site_occupancy@1`
and the species operators.

**S** marks our own reading or derivation.

## 0. Summary

| | |
| --- | --- |
| **Before** | No operator changed a finite node's contents at an event. The bath schedule sets held baths only (`bath_schedule.py:178–182`), and FR-23 keeps finite compartments out (D244). The review applied the wash on the host, between two runs, so each run kept its own books |
| **The mechanism** | One definition, a liquid exchange of a compartment (§2). FR-20's pool replacement is its whole-exchange execution in exact counts. This operator is its deterministic execution, at any fraction |
| **Built** | `scheduled_compartment_wash@1`: an event map with the sample, the supply, their free energies and the mixing heat as records, closed in @3's ledgers at the event (§4) |
| **Bitwise** | Every existing world, at all three levels: it is a new operator, and the site operator's change is a definition-time refusal only (§5) |
| **Evidence** | The review's sequence in one run, its books closed on every row, against the review's two-run result (§8) |

## 1. What existed

- **Cell family.**
  - The bath schedule (FR-10) sets a held bath's composition. A held bath is a reservoir, and "a
    finite node … cannot be clamped" (`bath_schedule.py:178–182`).
  - FR-23 (D244) admits a held-bath dose beside binding sites. A dose into a finite compartment was
    named as not covered.
  - No other operator changed a finite node's contents at a declared time. The review therefore
    stopped one run, halved the free tracer on the host, recorded the sample and started a second
    run, so the books could not span the wash.
- **Assembly family.** FR-20's `cells.pool_replacement@1` (approved in D240):
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
- **Free energy (S),** for the continuum F of an ideal solution, which is homogeneous of degree 1
  in (n, V), so the liquid before the exchange splits exactly into the part kept and the sample.
  - The sample leaves with F(sample) = f·F(before), booked to a sink.
  - The buffer arrives with F(buffer), booked from its source.
  - Mixing the kept liquid with the buffer dissipates H_mix = F(kept) + F(buffer) − F(after),
    which is never negative.
  - So F(after) − F(before) = F(buffer) − F(sample) − H_mix, and the ledger closes.
  - At f = 1 nothing is kept, so H_mix = 0, and the booking is exactly FR-20's: the sink takes
    F(old pool), and the work column F(fresh pool).
- **FR-20's builder confirmed the f = 1 booking** against `replacement.py` as built (D246's ruling
  1): `population._replace` books the sink as F(old pool) and the work column, and the transfer
  total, as F(fresh pool), with no mixing term. Slots, lumens and held places are kept, and the
  removed and supplied counts are recorded per finite place.

**The two executions:**

| | Assembly family: exact counts | Cell family: deterministic amounts |
| --- | --- | --- |
| f = 1, a whole exchange | FR-20's `cells.pool_replacement@1`, exactly. The fresh pool is the buffer's counts in the pool's volume, and the sample is the whole old pool | This operator, at f = 1 |
| f < 1, a partial exchange | **Binomial thinning:** each molecule of the liquid is drawn off independently with probability f. A draw on the schedule's stream, so an extension of FR-20's operator, later | This operator: the deterministic amounts, the binomial's mean |
| "Tracer-free" | A count can reach 0 | The buffer at the species' trace; an exact zero is refused (§4.5) |
| The free energy | The counts' discrete F, with ln n!. The split F(sample) = f·F(before) does not hold for a binomial thinning of counts at f < 1, so that extension must book its own split | The continuum F, for which the split above is exact |

**Execution-specific refusals, not part of the shared definition.**
- **The assembly family's** (FR-20): a held pool species that has a membrane or lumen place (its
  Q3, a declared version-1 limit), and, in osmotic worlds, a fresh pool above c_ext.
- **The cell family's** (this operator, §4.6): a face or a membrane that the exchanged species
  crosses at an exchanged node, and charged species other than as the node's own composition.

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
- **What differs is only execution:** continuous amounts against integer counts; the partial case, a
  scaling against a draw; the trace floor against a possible zero; and each family's own refusals
  above.
- **The declared key.** D175's "what it represents" key stays reserved, not built (D246). Both
  operators declare the same one, "the liquid exchange of a compartment", when it exists. With one
  representation per scope, a compartment is then exchanged by one operator only.
- **What it is not:**
  - **the bath schedule:** setting a reservoir's composition, booked against the reservoir;
  - **a dose or addition:** material added with nothing removed, FR-20's Q2 (b);
  - **a transfer:** FR-20's serial transfer, which samples the assemblies.

## 3. Options (as proposed; D246 chose A)

| Option | What | For | Against |
| --- | --- | --- | --- |
| **A** | A new cell-family operator: an event map that executes §2's definition deterministically at finite nodes | One operation with its own books; the shared definition; composes with sites and the species operators | A new operator to register and test |
| B | The bath schedule extended to finite nodes | One fewer operator | A clamp of a reservoir and an exchange with a compartment are different mechanisms with different books. It would mix two meanings under one law (D147) |
| C | A dose into a finite node, with nothing removed | Simple | Another mechanism, FR-20's Q2 (b): it is not a wash, and it moves the volume or ignores it |
| D | Today's host restart between runs | No code | Two sets of books, the sample kept outside the engine, and the sites' state passed through the declared initial occupancy |

## 4. The design, as built

### 4.1 The declaration and the schedule

- **The declaration:** `nodes`, the finite outside nodes it washes, each by ID, and `ions`, which
  version 1 requires to be `same_as_compartment`: the buffer carries the node's own ion composition
  (D246's ruling 2). Ions in neutral formula units are the later option.
- **The experiment key `compartment_wash_events`:** a list of `{time, node, fraction, buffer_mM}`.
  - The time is on the dt grid, with 0 < t < end, and times increase strictly per node.
  - The fraction lies in (0, 1].
  - `buffer_mM` gives a concentration for every neutral species of the world and names no other,
    so no wash is silently partial (ruling 2).

### 4.2 The event map

At the start of the step leaving t, at each node with a wash due (a count of the washes due by now,
against a count of those applied, which is state):
- every species of the node's liquid becomes (1 − f)·n + f·V·c_buf, at constant volume;
- an ion's buffer is the node's own concentration, so its amount is kept, bit for bit;
- the sample f·n and the supply f·V·c_buf are added to the records, ions included at f·n out and the
  same in;
- bound material, which is not liquid, is not read or written;
- with no wash due, the state is the start state, bit for bit.

### 4.3 The records

| Record | What |
| --- | --- |
| `wash_collected_fmol`, `wash_supplied_fmol` | [species, node]: the samples and the buffer supplied, cumulative, every species |
| `wash_sample_free_energy_pJ`, `wash_buffer_free_energy_pJ` | [node]: F(sample) = f·F(n, V) and F(buffer) = F(f·V·c_buf, f·V) of the exchanged (neutral) species, F(n, V) = 10⁻³ RT n (ln(n / V) − 1), @3's chemical term |
| `wash_mixing_heat_pJ` | [node]: H_mix, cumulative |
| `wash_last_mixing_heat_pJ` | [node]: the latest wash's H_mix |
| `wash_last_sample_fmol`, `wash_last_supply_fmol` | [species, node]: the latest wash's sample and supply, level records (FR-44, D327). An ion's supply record is its sample record, one expression. The labelled event's report reads them (§4.7) |
| `wash_energy_magnitude_pJ` | [node]: the energy bookings' absolute terms |
| `wash_applied` | [node], int64: the washes applied |

An ion's sample and supply carry equal free energy, the same liquid at the node's electrochemical
potential, so they are not booked.

**H_mix is computed, not taken as a remainder (D246's ruling 3):**

    H_mix = 10⁻³ RT V Σ_s c′_s [(1 − f) φ(c_s / c′_s) + f φ(c_buf,s / c′_s)],
    c′ = (1 − f) c + f c_buf,  φ(r) = r ln r − r + 1 ≥ 0.

φ is `numerics/ideal_mixing.phi`, the cleft fix's form (`restricted_lumen.mixing` at 28c4e7ff,
not on main when this was built; the lumen keeps its own copy, and one shared function is its
owner's later choice):
- its series for |e| < 10⁻⁴, with e = r − 1 formed without cancellation;
- the e-form (1 + e) log1p(e) − e elsewhere;
- r ln r − r + 1 from the ratio itself where r < 2⁻⁴⁰, where e can round to −1.

Its accuracy (**S**, measured in the tests against 50 digits): a few ulps from the series and the
ratio form; the e-form keeps about eps |ln r| of φ far from 1 and about 2 eps / |e| of it just above
the series' threshold, at most about 4·10⁻¹² relative.

### 4.4 The books and the checks

- **Material:** @3's outside and total ledgers gain collected − supplied at each washed node
  (D150's sign). With sites: free + bound + the cumulative sample − the cumulative supply is
  constant, to rounding.
- **Energy:** @3's energy ledger gains H_mix − (F_buffer − F_sample), against @3's own chemical
  jump at the node. Each term is computed on its own, so the ledger's closure checks the
  decomposition (ruling 3).
  - The records carry no heat or work suffix, so none enters the IMEX flow bound, as the bath
    schedule's dose records do not (BATH_SCHEDULE_DESIGN.md §2.2). Their magnitudes enter the
    energy ledger's rounding allowance.
  - That allowance also holds the stored amounts at the new level: RT (|a| + |n| + f·V·c_buf)
    (|ln c_after| + 1) per exchanged species, with a the node's anchor. The new amount is the anchor
    plus an increment, rounded at about eps times the stored amounts, and that rounding is booked
    at the new level's potential. Without this term, whole washes of a 10 mL well at 1 mM to
    10⁻¹² and 10⁻¹⁴ mM exceeded the energy bound at their own step, by 1.3 and 4.8 times.
- **Its own ledger:** each ion's sample against its supply at each node, zero bit for bit.
- **At every event:** the event refuses the step unless every washed amount stays positive and
  finite, and the event's H_mix is finite and ≥ 0.
- **On every accepted row,** the domain check reads the latest wash's H_mix ≥ 0 per node, so the
  host checks H_mix at every event, not only its cumulative record.

### 4.5 The trace (D246's ruling 4)

- **No buffer concentration is an exact zero, for any species.** @3 keeps every species positive
  at every active node, and at f = 1 a zero would empty the node. A tracer-free buffer is declared
  at the species' trace.
- **A species with a declared trace,** a site ligand, takes a buffer at or above that trace: the
  site operator's own trace rule, which reads the wash's buffers as it reads the bath schedule's
  doses (`site_occupancy.check_schedule_traces`).
- **A species with no declared trace** takes any positive concentration the definition chooses.
- **The amounts' representation** (**S**). A node's amount is @3's anchor plus an increment. So at
  f = 1 a buffer amount below about one ulp of the node's anchor rounds the new amount to zero or
  below, and the event refuses the step. Above that, the new amount carries an absolute error of
  about eps times the anchor. The tests pin both: 1 mM against 2⁻⁶⁰ mM is refused at f = 1 and
  admitted at f = 0.5.

### 4.6 Refused in version 1

At the definition, each with its reason:
- a held bath, which is the bath schedule's;
- **a face at a washed node, until measured** (ruling 5). A wash is a step in the node's
  concentration, and @3's face booking of such a step is FR-10's onset limit, measured for held
  baths only;
- **a neutral species that crosses a washed node's surface by any declared path** (fail closed;
  D263 finding 2). This was first the patch's own permeability alone, the extension of ruling 5
  that the lead accepted. A second review then found the same crossing admitted through a
  registered route, so the paths are now read from the declarations (`surface_crossings`):
  - the inner model's movers, through the core's join (`species_registry.inner_movers`): a
    patch's permeability, channels and pumps on a patch facing the node, a face touching it, and
    every declared kind's moved rows at the node (a kind's passive route, a transporter);
  - species exchange's routes through a patch facing the node, a site population's
    internalisation from it, and the gene unit's exports into the node and its outside
    degradations there (templated_polymerisation@1's amendment T; D327, the fail-open fix,
    each refused by name);
  - an operator's in-step process moving a neutral species at an outside node;
  - every operator law not shown local (`SHOWN_LOCAL`, each with why), with `REFUSED`'s reasons
    for the rest; a law in no list is refused until it is classified.

  Its booking of the step is unmeasured, as a face's, and the wash's books do not see the
  exchange. A site population that only binds stays admitted: its bound material is the site
  operator's, left in place by the wash, the review's case;
- ions declared other than `same_as_compartment`;
- a buffer that misses a neutral species, names another, or holds a concentration ≤ 0 or below a
  site ligand's trace;
- a fraction outside (0, 1], and times off the grid, outside (0, end) or not increasing per node;
- unknown keys and duplicates.

### 4.7 Composition

- **Door S.** It reads its nodes' volumes, anchors and outside mask as declared: fixed reads at its
  event, scoped to its nodes (`SCOPED_READS`, `read_slots`). It writes the nodes' amount
  increments through `ENTITY_WRITES` and provides no view.
- **Refused by the structure check:** water, the lumens and insertion@1 and @2, which change those
  fields on every slot. Each refusal is tagged real in the composition matrix.
- **Refused by the compartments' admitted list:** `cell_owned_compartments@1` fails closed on an
  operator off its list (`compartments.py`), and so does trafficking, which requires it. Admitting
  the wash beside the compartments is the lead's call.
- **Admitted:** @3, `site_occupancy@1`, the bath schedule (its dose at a held bath meets none of the
  wash's slots), D150's turnover and exchange, D152's reactions, the coupling operator (@1 and @2),
  the unit producer, injection, membrane state, replacement@1, the partition and the bridge.
- **A buffer richer than the node** raises the concentration that the sites and D152's reactions
  read at their next half-step. Both check their stage conditions at run time, at every stage, so
  a step outside them is refused, not taken.
- **Labels (FR-44, D327).** Beside `neutral_arrival_labels@1`, in either order:
  - The event takes `labels=` and also returns a `LiquidExchange`: the two level records
    (§4.3) at the labelled rows where a wash is due this step, zero elsewhere. Each is the
    event's own sample and supply. A cumulative record's gain would be inexact, and at f = 1
    after an earlier wash it leaves a kept part that is nonzero or negative.
  - The state and validity are the unlabelled call's, bit for bit.
  - The label owner decides the labels: the sample leaves with the node's shares, and the
    buffer joins the base, whatever window is open (NEUTRAL_LABELS_DESIGN.md §13).
  - The owner is shown local to the wash (`SHOWN_LOCAL`): it moves no amount.
  - The report's axis is the outside nodes, so an exchange of a cell's own liquid cannot be
    expressed in version 1.
- **The run view:** one prescribed layer, each wash an event at its node.
- **The composition matrix** gains its row and column (23 as built; 24 once FR-26's W registers
  before it, §10). The module registers last
  (`wash_schedule.py`), so no law is renumbered.

## 5. What stays bitwise

- **Every existing world, at all three levels** (values, programs, structure). It is a new operator.
- `site_occupancy.check_schedule_traces` also reads the wash's buffers: a host-side refusal at the
  definition, in compositions that declare the wash, which no existing world does.
- **FR-20's operator and the assembly family are untouched.**

## 6. Files

- **New:** `src/cells/operators/wash_schedule.py`; `src/cells/numerics/ideal_mixing.py`;
  `validation/tissue/wash_schedule_fixtures.py` (the review's well and the operator's block);
  `tests/unit/test_wash_schedule.py`; `tests/unit/test_wash_schedule_runs.py`.
- **Changed:** `src/cells/operators/site_occupancy.py` (the trace rule reads the wash's buffers);
  `validation/tissue/composition_matrix.py` (tags, a rule and the compartments rule's text);
  `docs/PUMP_COMPOSITE.md` (regenerated, with its operator-table row).
- **Not touched:** `bath_schedule.py`, `restricted_lumen*.py`, `compartments.py` and the assembly
  family's files.

## 7. Tests (D224)

- **`tests/unit/test_wash_schedule.py`,** in NumPy and a compiled kernel, with no world compiled,
  about 8 s:
  - the refusal table, 18 rows, each with its reason;
  - admitted beside the bath schedule's dose at a held bath and the sites, the read slots, the
    round trip;
  - the wash on the review's well: the sample, the supply and the free-energy split; the sites and
    the ions bit for bit; @3's ledgers at the event; without the wash's energy term the energy
    ledger fails by about 4·10¹⁰ times its bound; a second application idle, bit for bit; a stale
    count refused;
  - f = 1 as FR-20's booking, with @3's energy ledger closed at the event's own step for 1 µL and
    10 mL wells, and the trace limit of §4.5;
  - the host's row check (`check_values`) refusing a negative heat at the latest wash, though the
    cumulative record stays positive;
  - two washes of one node, each with its own fraction and buffer, the records summed;
  - the mixing heat against a 50-digit reference, in four rows (ordinary, the buffer at the trace,
    the node at the trace, the edge below 2⁻⁴⁰), each with a plant that breaks it (the e-form alone,
    the ratio form everywhere);
  - the run view's events.
- **`tests/unit/test_wash_schedule_runs.py`,** one compiled world, about 37 s on one core. Its
  reason: the only path through the compiled event, its controls at the event time and the
  runner's host checks on every row.
- The composition-matrix test checks the regenerated block.

## 8. Acceptance and the development run

**The request's acceptance,** at the wash, in one run:
1. The compartment's free amounts become (1 − f)·n + f·V·c_buf, and the sample record equals f·n
   per species.
2. Bound material is unchanged, bit for bit.
3. The removal, the supply and the free-energy change are booked at the event: every ledger closes
   on the event row, and the material balance (free, bound, sample and supply) holds on every row.
4. In the review's example, 60, 30 and 10 fmol become 30, 30 and 10, with 30 in the sample, and the
   four sum to 100 throughout.

**The development run** (`/mnt/workspaces/Cells/operators-fr27-20261120/`, criteria in
`CRITERION.md`, written first) runs the review's sequence in one run.
- **The run:** steady to 20 s, half the well washed at 20 s with buffer at the trace, then to 140 s.
- **The controls:** the same world with the wash declared and no event, and without the operator.

**The results at 44df5d5c** (`dev-44df5d5c/verdict.json` and its `ADDENDUM.md`). Five criteria
passed, and one clause of criterion 5 failed as written.

| Criterion | Result |
| --- | --- |
| 1. The run, with the runner's host checks on every row | Passed: 14,001 rows, 108 s on one core |
| 2. Rows to 20 s against the world with no wash event | Passed: bit for bit in all 38 shared fields. Against the world without the operator, also bit for bit (information only) |
| 3. The event row | Passed: 60 fmol free at 20 s, a sample of 30 exactly, a supply of 5·10⁻⁷ fmol, and each ion's sample equal to its supply bit for bit, the well's ions never moving |
| 4. The four amounts | Passed: within 2.3·10⁻¹³ fmol of 100 on every row |
| 5. The heat and the energy ledger | H_mix 9.7 ulps from the 50-digit reference, F_sample 1.2 and F_buffer 0.2 ulps: passed. The ledger's residual −2.3·10⁻¹³ pJ against a bound of 1.4·10⁻⁴ pJ: passed. **Failed as written:** without the wash's term the residual is 775 pJ, 5.6·10⁶ times that row's bound, not the 10⁹ times written. The threshold came from the event-only bound (2·10⁻⁸ pJ, no flows; the unit test checks that one, at about 4·10¹⁰). The row's bound adds 2·10⁻³ of the sites' flows over the step |
| 6. Against the review's host-applied run B, and the equilibrium | Passed: within 5.0·10⁻⁷ fmol of B on all 12,000 rows (the buffer's trace, as expected); the final amounts within 1.1·10⁻⁶ fmol of the analytic two-site equilibrium |

**So the wash reproduces the review's two-run result in one run,** with one set of books. The engine
now keeps the sample, the supply and the free-energy split itself, where the host kept them before.

**After the run,** the energy allowance's term for the stored amounts (§4.4) was added. It changes
no state value, only the energy ledger's bound, so the run's amounts and records stand.

**Checked without a criterion** (`/mnt/workspaces/Cells/operators-fr27-20261120/`): the run view
of a washed well is written and passes the reader's check, with one wash layer and the wash as an
event at its node. A well with sites has no view today, since `site_occupancy@1` declares no layers.
And φ equals the cleft fix's `mixing(e, ratio)` bit for bit, in NumPy and compiled.

## 9. Price (as proposed, S)

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
| The assembly family's partial exchange, by binomial thinning, with its own F split (an extension of FR-20, the origin-of-life builder's) | +1–1.5 |
| A registered protocol, with code-blind references | +1–1.5 |

## 10. Decisions and open items

**D246's rulings, as built:**
1. The shared definition, with FR-20's pool replacement as the whole-exchange, exact-count
   execution (§2). FR-20's builder confirmed the f = 1 booking. No shared key is built.
2. Ions are declared, `same_as_compartment`. The sample and supply records list every species (§4.1,
   §4.2).
3. H_mix is computed from the ideal-mixing terms in the cleft fix's form, the ledger's closure is
   checked on its own, and H_mix ≥ 0 is checked at every event, on the device and on every accepted
   row. H_mix is recorded, in the event's books and not in the IMEX flow bound (§4.3, §4.4).
4. "Tracer-free" is the buffer at the species' trace. An exact zero is refused for every species,
   and a species with no declared trace takes any positive concentration (§4.5).
5. Faces at an exchanged node are refused until measured (§4.6).
6. The name: `scheduled_compartment_wash@1`.
7. Branched from FR-23's head, e7a54539, so the composition matrix is edited on top of FR-23's.

**The lead's rulings on the open items (20 November 2026):**
- **The wash beside `cell_owned_compartments@1`** stays refused, as a version-1 limit (§4.7).
- **The refusal of a neutral species crossing a facing membrane** is accepted as built (§4.6). It
  is our extension of ruling 5, and it opens with a measurement, as faces do.
- **The two φ copies stay,** bit for bit the same: `numerics/ideal_mixing.phi` and the cleft fix's
  (§4.3).
- **Untested paths are version-1 limits:** a restart from a checkpoint across a wash, and batched
  windows. Neither was exercised then. FR-44 (D327) tests the restart: a labelled run cut at a
  wash row and one step after, resumed bit for bit, with the wash's redo and skip planted
  (`tests/unit/test_wash_schedule_resume.py`). Batched windows stay untested.
- **Criterion 5's failed clause** (§8) is stated in the landing text.

**Landing:** in a stack with FR-24 and FR-26 (the lead's ruling, 20 November 2026). FR-26's
`site_occupant_replacement@1` registers before this module, so the wash is law 24 of the
composition matrix.
