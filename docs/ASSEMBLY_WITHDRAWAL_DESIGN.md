# A timed partial withdrawal of an assembly population's pool (FR-35): design note

**Status: desk work, for the lead's decision with the advisor (21 November 2026).** It sets out the
options, a recommendation, the files, the tests and a price (D142), and decides nothing. It is a
general feature (D144) of `cells.assembly_lineages@2` in population mode. It builds on FR-20's
`cells.pool_replacement@1` (D240, [note](ASSEMBLY_WASHOUT_DESIGN.md)), FR-22's checkpoints and
FR-27's one-mechanism ruling (D246).

**The request** (FEATURE_REQUESTS.md FR-35, 97d3bfda). At a declared time, draw off a fraction f of
the well-mixed pool and add the same volume of a declared buffer. Each molecule leaves
independently, so a species' withdrawn count is Binomial(n, f). The reproducer is `site_wash_spec()`
in `tests/unit/test_assembly_lineages_v2_replacement.py`:
- adding `fraction: 0.5` to its replacement is refused;
- a fresh pool of four X records eight removed and four supplied.

**Engine models it would run:** `cells.assembly_lineages@2` in population mode, with
`cells.shared_pool@1` and the operator of §1.

## 1. The law

| Option | What | For | Against |
| --- | --- | --- | --- |
| L1 | An optional `fraction` on `cells.pool_replacement@1`; absent means today's | The requester's syntax works as typed | @1's registered contract says "draw: none" and books no heat, so both become conditional. Its `pool` key would change unit, from the whole pool's composition in V to the buffer in fV, silently |
| L2 | `cells.pool_replacement@2`, with a fraction | One operator name, two majors | f = 1 must either draw (then @2 is not @1 at 1) or not draw (then it is a special case). The key's unit hazard remains |
| **L3** | A new operator, **`cells.pool_withdrawal@1`**, with the schedule kind `withdrawal`, `fraction` and `buffer`. It shares FR-20's pool step and the population's booking code | @1 stays as registered, bitwise, with no new path. A distinct key, `buffer`, carries the fV unit | Two operators for one mechanism |

**Recommended: L3.**
- **FR-27's wording** called the partial case "an extension of FR-20's operator". D246 rules one
  mechanism with two executions, and L3 keeps that:
  - the withdrawal is the partial execution;
  - at f → 1 its booking is @1's exactly (§4, a stated identity);
  - both declare FR-27's reserved representation key, "the liquid exchange of a compartment", when
    D175's key lands.
- **The requester's syntax:** `fraction` on a replacement is refused, with a message that names the
  withdrawal kind: `{index, kind: withdrawal, times_s, fraction, buffer}`.
- **f = 1 stays @1's.** The withdrawal admits f in (0, 1) only.

## 2. The draw

- **The rule:** each molecule of each finite pool place is withdrawn independently with
  probability f: molecule i of place j leaves when its uniform u_ji < f. So k_j ~ Binomial(n_j, f),
  exactly in distribution.
- **The uniforms** are `streams.uniforms`: (m + 0.5)·2⁻⁵², m a 52-bit integer. So P(u < f) equals f
  to within 2⁻⁵², and exactly for a dyadic f such as 1/2 or 1/4.
- **The address: one block per finite pool place.** The stream is domain 6, `schedule`, with the
  schedule's declared index as its carrier word, like a transfer's. The draw number for wash w and
  place ordinal j (finite pool places in place order, P_f of them) is w·P_f + j. Its block holds
  n_j uniforms, drawn through `streams.block`, so a host draw compiles once per power of two.
  - A block at one draw number is not single draws at consecutive numbers (`uniforms(key, c, n)`
    folds c into the key, then takes n bits). This design uses blocks only.
  - **Why per place:** a species' outcome depends only on its own count and its address. Adding or
    changing another pool species never moves the tracer's withdrawal. (One block per wash would
    shift every later species' offsets.)
  - An empty place draws nothing, but keeps its address, so no later address moves.
  - The schedule's counter is w, the washes done. It advances by one per wash, an empty pool
    included.
- **Against the event stream:** a withdrawal draws only on domain 6, never on the world's event
  stream (domain 5). As at every stop, the event draw that crossed the stop's time is discarded and
  counted. So the world's events around a withdrawal draw the same uniforms as around a replacement
  at that time.
- **The grouped plan:** declared times enter the plan as FR-20's do, under its same-time rule (§6).
- **The checkpoint (FR-22):** the counter w is kept in checkpoint@1's per-schedule counter dict
  (`transfer_counter`, keyed by the schedule's index; indices are unique among schedules), so the
  format is unchanged. A resumed run's withdrawal numbering is a doc key, `withdrawals`, read with
  a default of 0, as FR-20's `replacements` is.
- **The diagnostic record** states every draw: each wash's address per place (index, draw number,
  size) and the realized k_j. The uniforms are recomputed from the address, as a fission block's
  are.

## 3. The buffer's supply

| Option | What | For | Against |
| --- | --- | --- | --- |
| **B1** | `buffer`: one declared integer count per finite pool place, the molecules in the withdrawn volume fV | Deterministic and exact; tracer-free is 0 | A concentration in fV is quantized to integer counts |
| B2 | A declared concentration, with each count drawn as Poisson(c·N_A·fV) on the schedule's stream | Exact grand-canonical counts | More draws and more addresses; nobody has asked for it |
| B3 | FR-20's `pool` composition in V, scaled by f and rounded | Reuses `pool`'s unit | A hidden rounding rule |

**Recommended: B1.** In the fixture, V = 10⁻²² L holds L 30 and S 6.
- **Half wash:** a buffer at the medium's own concentration is L 15, S 3, X 0.
- **Quarter wash:** 30·¼ = 7.5 is not a count, so the user declares 7 or 8. B1 says so and does not
  round.

**The capacity:**
- Each b_j ≤ `molecule_capacity` at parse (FR-20's check).
- The realized pool, n_j − k_j + b_j, passes the fail-closed host guard (`ledger.state_free_energy`).
- Only that guard can fire for some k, and only when b_j > 0. A refusal is a refused run, not a
  sample. An ensemble declares headroom (capacity ≥ the pool's largest count plus b_j), and its
  protocol records any refusal (D246's rule for drawn ensembles).

**c_ext (osmotic worlds):** the buffer's own concentration in fV is at most c_ext, under rule 6, as
FR-20's fresh pool is. The realized pool's solutes are not refused; their drift is reported, as for
every run today. So nothing about c_ext depends on k.

## 4. The energy, exactly

The pool's free energy in this family is the ideal discrete form (`ideal_mixing.py`). A finite pool
place holding c molecules in volume gV has
F(c; gV) = c(μ° − ln X − ln g) + ln c!, with X = N_A·V·c0.
- The engine's tables hold V only. So F(c; gV) = F(c; V) − c·ln g, and no new table is needed.
- Held places are not withdrawn. The excess and lumen terms read no pool count. So the pool's F is
  a sum over places, and everything below holds per place and sums.

**The identity, stated:**

    F(n − k; (1 − f)V) + F(k; fV) − F(n; V) = −ln[C(n, k) f^k (1 − f)^(n−k)] = σ ≥ 0

The μ° and ln X terms cancel, and what is left is the outcome's binomial surprisal. It is exact, per
place and per realization. Its mean over k is the outcome's Shannon entropy. A scratch check over
2,000 random cases of up to four species gives |σ + ln P(k)| ≤ 9·10⁻¹⁴, with every booking below
closing to 10⁻⁹.

**Three bookings that close.** In each, F(after) − F(before) = W − S − H, with S the sink, W the
schedule's work column and H the heat:

| Booking | Sink S | Work W | Heat H | Tracer-free, nothing withdrawn (k = 0) | Tracer-free, everything withdrawn (k = n) |
| --- | --- | --- | --- | --- | --- |
| **A, the volumes** | F(n; V) − F(n − k; (1 − f)V) = F(k; fV) − σ | F(b; fV) | F(n − k; (1 − f)V) + F(b; fV) − F(n − k + b; V) | S = n·ln(1 − f) < 0, H = −n·ln(1 − f) > 0 | S = F(n; V), H = 0 |
| B, the sample's own F | F(k; fV) | F(b; fV) | whatever closes: −σ + H_A | H = 0 | H = n·ln f < 0 |
| C, counts only | F(n; V) − F(n − k; V) | F(n − k + b; V) − F(n − k; V) | 0 | H = 0 | H = 0 |

For n = 8 and f = ½ these are A at k = 0, S = −5.545 and H = +5.545 kT, and B at k = 8,
H = −5.545 kT.

- **A's heat is never negative.** H_A = −ln[C(m, b) f^b (1 − f)^(m−b)], with m = n − k + b: the
  surprisal that b of the m molecules came from the buffer's side. That is D246's constraint for
  FR-27's wash, "a host check holds it non-negative at every event".
  - At f = 1 it is @1's booking: S = F(n; V), W = F(b; V), H = 0.
  - In the large-n limit σ = O(ln n) for a typical outcome, so S → f·F(before). Then A is FR-27's
    continuum booking, term by term.
- **B books a negative heat** when everything leaves.
- **C hides the dilution's real dissipation,** and disagrees with FR-27 in the continuum.

**Recommended: A.**
- The sink takes the F that leaves with the sample, given the outcome.
- The work column takes the buffer's own F.
- The mixing heat goes to the host's heat column (`E_HEAT`, which takes a lysis's release heat
  today).

The record keeps the four terms apart, so B or C can be rebuilt from it: F(k; fV), σ, F(b; fV) and
H. They are computed in the small-ratio form D246 names for FR-27 (`log1p(−f)`).

**The independent reference** for the Lean lane uses closed log-factorial arithmetic, exact ln c!
by summation or `lgamma`. It never reads the engine's table (the capacity finding showed why).
Per place:
- ln P(k | n, f) = ln n! − ln k! − ln (n−k)! + k ln f + (n−k) ln(1 − f);
- σ = −ln P(k | n, f);
- H = −ln P(b | n−k+b, f);
- the closure F(after) − F(before) = W − S − H holds exactly.

The record's terms equal the reference to 10⁻¹².

## 5. The statistical acceptance

**Host draws through the operator's own draw function,** at real run addresses: seeds 0 to 3,999,
the fixture's schedule index, and its tracer place's draw number, vectorised over the 4,000
addresses (about 5 s).
- **Half (f = ½, n = 8):**
  - the mean is in 4 ± 0.1 (4.47 SD of the mean);
  - the variance is in 2 ± 0.2 (4.78 SD of s²);
  - a χ² over the nine outcomes passes at α = 10⁻⁴ (critical 31.8 on 8 df; the smallest expected
    bin is 15.6).
- **Quarter (f = ¼):**
  - the mean is in 2 ± 0.1 (5.2 SD);
  - the variance is in 1.5 ± 0.2.
- **The false-alarm rates** are each band's under 10⁻⁵ (normal approximation) and the χ²'s 10⁻⁴.
  They are a prior over the choice of seeds, fixed once chosen. The test is deterministic: a failure means the draw is wrong, or the
  seeds were among the rare bad choices.
- **The plant the variance band exists for:** one uniform shared by a species, so its molecules
  leave together. At f = ½ that has the same mean, 4, but variance 16. The mean band would pass it;
  the variance band and the χ² catch it. A second plant, f off by 0.05, shifts the mean by 0.4,
  which is 18 SD.

**Engine runs,** two or three: the fixture at f = ½ and f = ¼, one seed each. Each run's recorded
k equals the draw function at its address, bit for bit. In every realization:
- k + (n − k) = 8 exactly;
- the particle's places (four vacant R, two occupied XR) and its key are unchanged at the wash,
  against the world stopped at the last event before it (FR-20's W1 form);
- the record's F terms and heat equal §4's reference, and the books close;
- no stream was refused.

**Restart (FR-22):** reuse FR-20's `test_a_cut_around_each_replacement_resumes_bitwise`,
parametrised over two worlds, the replacement world and a withdrawal world with two times on one
schedule. Cuts fall at k = n and n + 1 around each wash. The plants:
- redo and skip (the applied stops ±1, as now);
- the schedule's counter reset to 0 on resume. This bites only with a cut between the two washes,
  hence two times on one schedule.

## 6. Version-1 refusals

Each is refused at the parse unless stated, with its reason:
- **Not a population** (single-lineage mode), as FR-20.
- **f outside (0, 1).** f = 0 changes nothing. f = 1 is `cells.pool_replacement@1`.
- **`fraction` on a replacement schedule:** the message names the withdrawal kind.
- **The buffer:**
  - one integer count per finite pool place, in fV;
  - each count at most `molecule_capacity`;
  - its concentration at most c_ext in an osmotic world.
- **A held pool species with a membrane or lumen place** (FR-20's Q3): the withdrawal would be
  silently partial for it.
- **The same-time rule, as FR-20's:**
  - a declared time shared with any other stop is refused at the parse;
  - a Poisson shear drawn at its time is refused at the run's start;
  - a lysis at its time is refused at the event.
- **Never withdrawn:** held places, which are reservoirs, and slots. Particles keep their places
  and keys.
- **Labels** (slice 5) are not in version 1. The per-molecule order (place, then molecule) is
  declared, so labels can map onto it later.

**What moves for existing worlds: nothing.**
- A world without a withdrawal writes no new key. The row kind `withdrawal` is listed in run.json's
  legend only when a world declares one. (FR-20 listed `replacement` for every population; no
  registered population run exists, and R4's landed runs are development.)
- No device program changes.
- @1 is untouched.

## 7. Files, tests and price

- **New:** `src/cells/models/assembly_lineages_v2/withdrawal.py`, holding the parse, the draw, the
  booking and the contract, registered as `cells.pool_withdrawal@1`.
- **Changed:**
  - `division.py`: the schedule kind's routing and the same-time rule;
  - `population.py`: the host step, the plan's refusal, the conditional legend and the checkpoint
    doc's numbering;
  - `records.py` (run.json's withdrawals, relations' edges) and `diagnostic.py`;
  - `spec.py`: the buffer's capacity check;
  - `transfer.py`: the shared pool step;
  - `src/cells/registry/model_table.py`: the operator's home;
  - `FORMAT_OL2.md`, and a §0.2 entry in ORIGIN_OF_LIFE_ENGINE_DESIGN.md.
- **Tests, rows in the replacement file (D224):** the refusals; the host statistics (about 5 s);
  two or three engine runs; and the restart world's rows (about 30–60 s, as FR-20's cut test).
- **Price:** 1.5–2 agent-days of building, gates excluded:
  - the operator, 0.5;
  - the host step and its records, 0.5;
  - the tests, 0.5;
  - the docs, 0.25.

## 8. Questions for the lead

1. **The law:** L3, a new operator (recommended), L1 or L2?
2. **The address:** per-place blocks (recommended), or one block per wash?
3. **The buffer:** B1, counts in fV (recommended), or B2, a Poisson draw?
4. **The booking:** A (recommended), B or C?
5. **Capacity conditioning:** keep the fail-closed refusal with declared headroom (recommended), or
   refuse at parse any buffer with b_j > 0 unless headroom is proved?
