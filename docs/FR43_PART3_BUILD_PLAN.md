# FR-43 part 3, option B: an integer-population operator in the composite (build plan)

**Status: plan for the lead, docs only, 23 November 2026, from main 2263d11c.** D315 chose B (the
user): a low-count population of integer units in the cell composite, whose events read the
composite's finite pools and whose activity moves material between them, beside the existing
operators. The design is docs/FR43_SHARED_INVENTORIES_DESIGN.md §3.1, §3.3, §3.5, §3.6 and §5
(branch `fr43-design`). This note fixes what is built and asks four choices (§9). Evidence for the
claims below: `/mnt/workspaces/Cells/fr43-part3-20261123/` (`probe/structure_probe.py`,
`out/structure_probe.json`: the intended declarations through `pump_composite.structure_errors`,
no compile).

## 1. The operator: `integer_unit_population@1` (new file `operators/integer_unit_population.py`)

**The physics.** A *site* is an isolated cluster of integer units in one membrane patch, such as a
few channels, transporters or machines. Its units interact only within the site.
- **Unit states** k, each with an integer subunit weight w_k ≥ 1. The counts are n_k (int64).
  FR-43's world has free (w = 1) and active (w = 2), with W = Σ w_k n_k = 2.
- **Channels** j: integer stoichiometry r_jk → p_jk, which conserves W (checked at the definition).
  The propensity is a_j = k_j · Π_k ff(n_k, r_jk) · φ_j, where:
  - ff(n, r) = n!/(n − r)! is the ordered-tuple convention of `cells.stochastic_mass_action@1`, so
    2 free → active at n = 2 gives 2 k_j;
  - φ_j = 1, or c/(1 mM) for one declared read: one species row at the patch's cell or outside
    node. That read is the feedback.
- **Transfer routes** i: a neutral species σ_i crosses the patch between its cell (V_c) and its
  outside node (V_o). The node must be finite.
  - The flux is J_i = G_i (n_c/V_c − n_o/V_o) fmol/s, cell to node, with G_i = Σ_k g_ik n_k and
    g in pL/s per unit. It is passive and linear.
  - The units carry no free energy (declared, as the gene unit's machines). The pools keep @3's
    terms.
- **Rates and conductances** are declared constants, bound as per-world layout data. No schedule
  in version 1.

**State (owned; int64 where marked):**
- counts [site, state] (int64);
- H and E [site];
- the event counter [site] (int64), and per-channel event counts [site, channel] (int64);
- the half-step counter [site] (int64);
- cumulative transfer per route [site, route];
- the booked moves onto @3's rows: cell [species, cell_slot] and node [species,
  extracellular_slot], as ENTITY_WRITES on `amount_increment` and `extracellular_amount_increment`;
- the transfer heat [site] (monotone);
- the division record [site, state] (int64; signed);
- the event trace: time, channel and the route pools at each event [site, trace(, route, 2)], with
  capacity declared. The trace holds the first N events, and the counter says how many occurred.

## 2. The composite's first random streams (new file `numerics/counter_streams.py`)

- **Counter-based Threefry-2x32 with its own written hierarchy:**
  - key(seed) → fold the site's declared index (low word, then high) → fold the domain → fold the
    counter (low, high) → `jax.random.bits` (uint64);
  - u = (m + ½) 2⁻⁵², m the low 52 bits: the open interval (0, 1), the family's uniform map;
  - domains: 1 events (two uniforms per event k: u₁ gives E_k = −ln u₁, u₂ the channel) and
    2 partition (one uniform per unit at a division, counter 0).
- **Where the pieces live:**
  - the seed is declared;
  - keys are bound host side as layout (int64 words);
  - counters are state, so checkpoints carry them and a restart is bitwise.
- **Batches:** each world's own layout gives per-world streams under vmap. Worlds that differ only
  by seed share one compile; the seed is outside `batch_signature`.
- **Records:** the stream's identity (generator, seed, fold order, domains, uniform map) goes in
  the operator's summary.

## 3. The event clock, located inside the half-step

The operator is a split part (`RK4 = "split"`). Its half-step over h advances only its own
variables, with every other row frozen.

**Between events** the counts are constant, so the flow is closed form:
- the two pools relax as u(τ) = u₀ e^{−λτ}, with λ = G (1/V_c + 1/V_o);
- the moved amount is m(τ) = −u₀ expm1(−λτ)/(1/V_c + 1/V_o);
- a read row on the site's own route follows c(τ) = c₀ + δ(1 − e^{−λτ});
- any other read row is constant within the half-step;
- so H(τ) = Σ_j k_j ff_j [c₀τ + δ τ q(λτ)]/(1 mM) in closed form, where q(x) = 1 − (1 − e^{−x})/x
  is summed in series below x = 1.

**Each event:**
- the crossing H = E is found by bisection on the monotone H, 64 halvings, to rounding;
- the pools move to the crossing;
- the channel is the first j with c_j > min(u₂ a₀, nextafter(a₀, 0)), its prefix a serial left
  fold (the exact kernel's rule);
- then H = 0, E = −ln u₁ at counter k + 1, and the rest of the half-step runs at the new counts.

**The loop and the time:**
- `lax.while_loop` runs up to 64 events per half-step. Past the cap the step is refused, never
  truncated.
- The definition refuses dt · a₀,max > 1, with a₀,max taken at the largest counts and the largest
  concentration the read row can reach.
- Event time is (half-step counter) · h + τ: one rounding, no accumulated sum.

**Order, as the design states it.** The half-step is exact. Only the splitting against other
writers of a read or moved row (turnover, exchange, @3's step) is O(dt²). So:
- **Feedback on, the pools moved by the operator alone:** the event times equal the same-draws
  reference to rounding at every dt, and halving shows no order. This is checked first.
- **The two-way world:** the order is shown by halving.
- **Feedback off, constant rates:** the trace is the exact kernel's for the same uniforms
  (t_k = t_{k−1} + E_k/a₀), a pathwise check to rounding.

## 4. Owned state through division: the hook in the composite

**What exists.** The composite's division is `isopotential_partition@1`. It is a retiring event
that takes `lifecycle=` (TAKES_LIFECYCLE). At each division it calls
`lifecycle(state, division_maps(due, p), retirement_masks(due, p), xp=)`. The composite passes that
callable only beside the kinds' lifecycle fields. Owned operator state is not divided: every
cell-side species operator is refused beside the partition (the matrix, 13–25).

**The hook (asked; ~30 lines, based on part 1's head once it lands):**
- `contract.py`:
  - `DIVIDES_OWNED = False`;
  - `divide_owned(self, state, maps, masks, p, *, xp)` → (state, valid);
  - `check_declarations` requires a bool, true only with owned state.
- `pump_composite.py`:
  - `owned_dividers` (static, by the operator list);
  - in `split_step`, `lifecycle = op.RETIRES and (bool(self.kind_lifecycle) or
    bool(self.owned_dividers))`;
  - the callable runs the kinds' part only where the table is non-empty (today's code). Then it
    runs each owned divider in declared order, its validity and-ed;
  - `p` reaches it by closure, only where owned dividers exist;
  - `lifecycle_errors` refuses a retiring operator without TAKES_LIFECYCLE beside an owned divider.
- **D148:** without an owned divider every condition and call is today's, so S5's division worlds
  keep their program text. The proof is the jaxpr-text pair checks, not result identity (§8).

**`independent_segregation`** (the division token, declared per population; D315):
- Each unit of the parent site goes to the first recipient with probability f, independently.
  This is binomial partitioning.
- **f** is the partition's fraction of the site's patch: maps["membrane_slot"], the area fraction
  a_k, one authority. The units live in the membrane, so the area share is their segregation
  probability.
- **The draws:** one uniform per unit from the parent site's partition stream at counter 0, in
  declared unit order (state order, then index within a state); u < f goes to the first.
- **Exactness:** the daughters' counts sum to the parent's exactly, in integers. The parent is
  zeroed. The signed division record closes each site's subunit ledger exactly.
- **The pools** split by the partition's own rule (f dn + δ), to rounding.
- **Clocks:** the parent's clock is retired. Each daughter site keeps H = 0 and its own counter-0
  threshold, which is exact by the strong Markov property at a fixed time.
- **Site maps:** declared parent site → (daughter 1, daughter 2). They are checked host side
  through the contract's generic `patch_maps`: the parent's patch maps onto the daughters'
  patches, in order. They are checked on device against the maps, and refused if they disagree.
- **Births:** a site on a patch born later declares zero units.
- **`exact_fraction` and Protocol G** are the assembly family's. Nothing of theirs is touched.

**Reads beside a closer.**
- `membrane_active` and `extracellular_amount_reference` are current reads at stage split. With
  C1's fallback, worlds without a changer receive no view.
- A closed site (a pending daughter, the retired parent) is selected idle: no rate, no move, the
  clock frozen. That matters because close() pads the cell anchor to 0, so log(0) is never formed.
- Declared anchors are read only at live sites, where they equal close()'s. `amount_reference` is
  not a view field (probe), so no other read is possible.

## 5. Writers, reads and refusals (version 1)

**Co-writers of a transfer row:**
- turnover@1 and exchange@1 are admitted (split parts with exact half-steps, each with its own
  books and ΔG: the 19 November two-writer rule);
- a row the clock reads may be written by any operator or by @3's step.

**Refused at the definition:**
- a charged species;
- a route on a held bath;
- an in-step mover of a transfer row;
- a transfer row that a D152 reaction or the gene unit writes (their one-writer rules; the
  part-2 files are not edited);
- volume providers: water and the lumens, since volumes are fixed reads;
- replacement@1 and @2, and any event that replaces amounts (EVENT_REPLACES);
- any closer that is not a retiring operator taking the lifecycle (insertion@1 and @2 among them);
- a label owner;
- two sites moving one row, or a site reading a row another site moves (they could not be located
  independently; one loop per pool group is the later door);
- dt · a₀,max > 1;
- units on a pending patch;
- a dividing patch without a site map;
- more than 1,024 subunits per site (the low-count scope);
- a second instance of the law.

**Refused at run time:** non-finite values, a pool that would not stay positive, the event cap,
and a division whose daughters disagree with the maps.

**Ledgers:**
- material per species: the paired moves sum to zero;
- @3's species ledger, through ENTITY_WRITES;
- subunits per site, exact in integers.

**Energy:**
- the heat is −ΔF of each move, formed as m ln(c₁′/c₂′) + n₁ φ(−m/n₁) + n₂ φ(m/n₂), with
  φ(x) = x − log1p(x);
- every term is ≥ 0 by construction, so the heat is a monotone heat field;
- the magnitudes are @3's per-row terms.

## 6. Tests, validation and the references

**Tier tests** (`tests/unit/test_integer_unit_population.py`, small worlds built on
`secreted_species_fixtures`: one cell, a finite node, a contact patch, S neutral):
- C3.1–C3.2: S + 2A = 2 on every row and event, and the pools' total conserved;
- C3.3: the closed-form two-state P₀(t) over many sites, at a z set before the run, plus a plant
  with k_a 10% high that must fail. The pathwise exact-kernel check runs to rounding;
- C3.4: the engine's recorded uniforms equal the spec's draws table. The event times are compared
  with the references (once they land);
- C3.5: at an equal split of one active unit, exactly one recipient on every draw and the
  inventories summed, plus the frequencies across seeds against f with a plant at 0.45;
- C3.6: a same-seed restart, cut between events, is bitwise;
- the two-way case: turnover supplies the read row, and the integer state changes the later flux;
- refusals, one parametrized row each;
- the hook's static absence.

Seconds are stated at landing.

**Validation** (`validation/fr43_part3/`): the halving study, the frequency runs and the
comparison with the references.

**References spec** (`validation/fr43_part3/references/spec/part3.json` and README), sent ahead:
- three worlds: two subunits with feedback on alone; four subunits with feedback on (the channel
  rule exercised); and the two-way world with turnover's production in the cell and clearance at
  the node;
- the laws as equations with units, and the unsplit coupled ODE (no dt);
- the stream's written derivation, and the draws as a data table from a standalone generator
  (no engine import);
- the requested outputs, with units.

No engine value is in it.

## 7. Records and registration

The new law requires several registration pieces, and shared files that need the lead's sequencing:
- the run view (layers, sets of its axes, record kinds, units, orientation);
- the summary (stream identity, declarations);
- the library page (`--new operator`, then `--write`);
- the composition-matrix tags and rules (`validation/tissue/composition_matrix.py`) and the
  regenerated block in `docs/PUMP_COMPOSITE.md`;
- tier rows;
- PROGRESS and FR-43's row.

## 8. D148 and gates

**Static absence.** The operator is statically absent unless declared. A world without it traces
nothing of it. The hook's condition depends on the operator list alone.

**Gates**, on clean frozen snapshots:
- `gate.sh` (LANE, ADDITIONS_FROM);
- the FR set;
- `proofs.sh` (the invariance gate and probes2);
- tier rows;
- the guard set and `library_pages.py --check`.

## 9. Choices for the lead

1. **The clock is closed form**, not the note's SSPRK(3,3) stage polynomial.
   - It restricts version 1 to the passive linear transfer and to a read of order 0 or 1.
   - Nonlinear laws (saturable transport, Hill reads) would take the stage polynomial with the
     same bisection, as a later door.
2. **Statistics come from many sites in one world** (for C3.3 and C3.5), and seeds from a batch of
   worlds that differ only by seed. Whether the batch runner takes those in one compile is checked
   first. If it does not, seeds run as separate worlds.
3. **Co-writers in version 1** are turnover and exchange. Two cases follow part 2:
   - beside D152 reactions or the gene unit on one row, which needs their writer rules (part 2's
     files);
   - beside water, which needs current volume reads.

   A row the clock only reads may be anyone's today.
4. **f is the patch's area fraction** (membrane-resident units). The volume fraction would serve
   cytosolic units, a later door.

## 10. Price

The estimate is about 5–6 agent-days, inside the design's 5–8:
- streams 0.5;
- the operator, clock and books 2;
- the hook and segregation 1;
- records and registration 0.5–1;
- tests, the validation drivers and the spec 1–1.5.

Gate wall time and the references come on top.

## 11. As built, and the lead's rulings (23 November 2026)

**The lead's rulings on §9:**
1. The closed-form clock is accepted for version 1: the linear transfer, and a read of order 0 or 1.
2. Many sites in one world, plus a seed batch, are accepted.
3. Turnover and exchange are the co-writers of version 1, **as a stage**. The user chose B so that
   the existing operators share the pools, so part 3 stays open until two things can co-write a
   moved row, after part 2 lands:
   - D152 reactions;
   - the gene unit.
4. f is the patch's area fraction. The equal-probability split is tested where f is exactly ½.

**Departures from this plan:**
- **Sites sharing a pool run in stages, instead of being refused.**
  - After a division both daughter patches face the parent's outside node, so two live sites share
    the node row. Refusing that would have refused every division of a site with a transfer.
  - Sites whose rows meet get different stages, where one of them moves the row and both can be
    live. Rows both only read do not meet, and neither do a parent and its daughters, whose lives
    are disjoint.
  - One stage runs the half-step as the exact flow, so the single-site worlds stay exact at every
    step.
  - With more, a half-step is a palindrome of exact stages (h/2 forward, the last over h, h/2
    back), as exchange's routes are. Coupled sites are therefore split at O(dt²), as with any other
    co-writer.
- **Mask providers are refused, as closers are.** Insertion@1 provides the masks without closing
  them, so the refusal covers any operator that opens or closes slots without dividing them
  through the lifecycle.
- **The pass criteria were fixed before the references returned,** in
  `validation/fr43_part3/REGISTRATION.md`.
  - The W3 study showed that each event's splitting error is C dt² φ(1 − φ), with φ the event's
    phase in its step.
  - So the order is judged by a fit over five halvings, with a phase band, not by pairwise ratios.
