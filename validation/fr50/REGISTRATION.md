# FR-50: the registered protocol `fr50-one-way-records-v1` and its pass criteria

This note fixes the pass criteria for FR-50, opt-in one-way cumulative records per route. It was
written on 23 November 2026, before any code-blind reference exists and before any engine code. The
design is `/mnt/workspaces/Cells/fr49-51-design-20261123/DESIGN.md` §2, with rulings 1–8 as D327
approved them and the reviewers' details. The lead tags this note and the references' spec
(`references/spec/`) before the engine build (D327).

**The engine.**
- **Phase 1:** `cells.passive_routes@1` (`passive_neutral_permeation@1`,
  `passive_constant_field_permeation@1`) and `cells.transporter@1`
  (`atp_driven_transporter_mass_action_positive@1`), within `resolved_pump_tissue@3`'s step.
- **Phase 2:** `resolved_pump_tissue@3`'s membrane routes, junction routes, uncharged faces and
  channel populations, the last with FR-51's block.
- `resolved_pump_composite@1` where a world needs it.

Phase 1 is judged at its landing; phase 2 is judged at its own, after FR-51 (D327).

**Bounds fixed before any reference value was seen.** Each bound below was fixed before this writer
saw any value from the registered references. What informed them is listed in §6.

**The inconclusive rule.** A criterion is inconclusive, not a pass, where the reference reports a
cross-check difference above its declared accuracy.

## 1. Definitions (D327: the gap measured before any correction)

For a recorded pair (a route and, where it carries several, a species) over one step:
- **The uncorrected amounts** F_t and B_t (fmol, or fmol of cycles). They are the trapezoid of the
  step's two ends' one-way fluxes, or under the Euler IMEX its one stage's weight times the start's.
  They come from the same kernels as FR-42's labels.
- **Δ** is the booked net: the net record's change over the step.
- **The gap:** g = Δ − (F_t − B_t).
- **The records:** F ← F + F_t + max(g, 0), and B ← B + B_t + max(−g, 0).
- **The relative gap of the step,** defined whatever the amounts:
  - r = |g| / max(F_t + B_t, |g|) where F_t + B_t + |g| > 0;
  - r = 0 where all three are 0;
  - r lies in [0, 1], and r = 1 flags a booked net with no one-way flow.
- **`one_way_gap_relative`** is the running maximum of r over the run's steps, per pair. It is a
  state field, so restarts carry it.
- **Closure,** on every row: |F − B − (net − net₀)| ≤ 2.5 ε n (F + B + |net| + |net₀|), where n is
  the steps so far and net₀ the net record at the start.
- **The error of a record** q at the engine's step h, over the record times t_i:
  e_q(h) = max_i |q_engine,h(t_i) − q_ref(t_i)| / max_i |q_ref(t_i)|.

**The channel split** (D327) is built from `channel_rates`' own factors:
- forward is g c_in B(−x), and backward is g c_out B(x);
- g carries the population's A P r a, its opening, its routed availability and FR-51's u, exactly
  as `channel_rates` forms them;
- so forward − backward is `channel_rates`' outward flux, at rounding, at every state. This is
  **the kernel closure**.

## 2. Phase 1: the kinds

### K1. A neutral route at zero net (steady)

**The world:** a cell and a finite node, each 1 pL, joined by a patch of area 1e-10 m². A
`passive_neutral_permeation@1` route of P = 1e-9 m/s carries S at 1e-3 mM at both ends. It runs at
dt = 0.1 s to 100 s.

**The criteria:**
1. **K1-1, absolute:** at each record time, |F_e − F_r| ≤ 1e-11 F_r and |B_e − B_r| ≤ 1e-11 B_r.
2. **K1-2, the gap:** `one_way_gap_relative` ≤ 1e-12 on every row.
3. **K1-3:** closure on every row.

**Plants, each of which must fail:**
- (a) the backward kernel halved. Closure holds, and the corrected records come back exactly
  (§6), so it fails only K1-2, with r = 1/3;
- (b) both kernels halved. The gap stays 0, so it fails only K1-1.

### K2. A neutral route relaxing (the order)

**The world:** K1's, with P = 1e-7 m/s and S at 1e-3 mM in the cell and 1e-6 mM in the node. It runs
at dt = 0.1 s and 0.05 s to 200 s, four relaxation times.

**The criteria:**
1. **K2-1, absolute, the order:** for q in {F, B}, with e_q of §1:
   - 3.6 ≤ e_q(0.1 s)/e_q(0.05 s) ≤ 4.4;
   - where e_q(0.1 s) < 1e-8, the ratio is not judged, and q passes if e_q(0.05 s) < 1e-8.
2. **K2-2, the gap's order:**
   - `one_way_gap_relative` at the horizon is at most 1e-5 at 0.05 s;
   - where it is at least 1e-12 at 0.1 s, its ratio between the two steps lies in [3.0, 5.0].
3. **K2-3:** closure on every row.
4. **K2-4:** a restart from a checkpoint at 100 s is bit for bit the uninterrupted run, the records
   and the gap included.

### K3. The charged kernel (host only)

**The evaluation:** `passive_constant_field_permeation@1`'s one-way kernel, at the declared state
and the four declared voltages.

**The criterion:** each direction satisfies |J_e − J_r| ≤ 1e-12 J_r, and so does the ratio
inward/outward.

**Plant:** B(x) and B(−x) exchanged. It must fail at every nonzero declared voltage: it inverts
Ussing's factor e^(−x).

### K4. A transporter at equilibrium (absolute; D327)

**The world:** a cell on a held bath, with the neutral ATP-driven transporter on its patch, held
fuel, and the declared role concentrations. ΔG_cyc = 0 there. It runs at dt = 0.1 s to 100 s.

**The criteria:**
1. **K4-1, absolute:** at each record time, |F_e − F_r| ≤ 1e-11 F_r and |B_e − B_r| ≤ 1e-11 B_r, in
   fmol of cycles.
2. **K4-2:** |net| ≤ 1e-12 F on every row, and `one_way_gap_relative` ≤ 1e-12.
3. **K4-3:** closure on every row.
4. **K4h, host:** at the off-equilibrium state, J₋/J₊ = e^(ΔG_cyc/RT) within 1e-12, and J₊ is
   absolute within 1e-12.

**Plants, each of which must fail:**
- (a) J₊ without the saturation S: K4-1;
- (b) J₋ = J₊ e^(−ΔG/RT). It is indistinguishable at equilibrium, so it must fail K4h.

### K5. Refused at the definition (rows)

Each of these, with `one_way` declared, is refused with its reason:
- a rectifier route;
- a net-flow transporter mode;
- RK4;
- an operator that retires or closes slots.

## 3. Phase 2: @3's routes

### E1–E4. Steady pairs (absolute)

**World 1:** one cell on a held bath, at V = E_K, set by its charge anchor. Its K crosses the patch
both by the patch's own permeability (E1) and by a gate-free K channel population with FR-51's block
(E4). Every other ion is impermeant, so V stays at E_K.

**World 2:** two cells joined by a junction (E2), and two finite nodes joined by a face (E3). A
neutral S sits at equal concentrations and potentials everywhere.

**The criteria, per pair:**
1. **Absolute:** at each record time, |F_e − F_r| ≤ 1e-11 F_r and |B_e − B_r| ≤ 1e-11 B_r.
2. **The gap:** `one_way_gap_relative` ≤ 1e-12 on every row.
3. **Closure** on every row.
4. **For E4, the kernel closure** (§1) at every observed row: the split's difference equals
   `channel_rates`' flux within 4 ulps of (forward + backward).

**D327's planted fault:** FR-51's block left out of both directions of E4's split.
- At zero net current it doubles both records, since u = 1/2.
- The net, the ratio, the gap and the kernel closure all still pass, since V = E_K.
- **It must fail E4's absolute criterion,** by a factor of 2.

**Restart:** World 1, from a checkpoint at mid-run, is bit for bit the uninterrupted run.

### E6. The channel split off reversal (host only)

**The evaluation:** the blocked population at the five declared voltages and the two availabilities.
- Each direction is within 1e-12 of the reference's absolute value, u included.
- The kernel closure holds within 4 ulps.
- The ratio inward/outward equals (c_o/c_i) e^(−x) within 1e-12.

**Plants, each of which must fail:**
- (a) the split's own opening, with the routed availability left out. At availability 0.5 it misses
  the absolute values and the kernel closure by a factor of 2;
- (b) the block left out of the split. It misses the absolute values and the kernel closure;
- (c) B(x) and B(−x) exchanged.

### E5. Refused at the definition (rows)

Each of these, with a record declared, is refused with its reason:
- a face row of a charged species;
- a forms face;
- a pump;
- RK4.

## 4. D148: unchanged worlds stay bitwise

- **The static predicates:**
  - without `one_way` on any route, the kinds keep today's fields;
  - with `InnerStructure.one_way_records == ()`, @3 keeps today's types.

  Crossrev is identical for every set.
- **The label path's three copies of the step rule move onto the shared helper.** The labelled
  worlds' transfers are then bit for bit today's (`tests/unit/test_neutral_labels_transport.py`'s
  rows), and their crossrev is identical. If either moves, the migration is dropped (DESIGN.md
  §2.6).

## 5. The tests (D224)

- **Host, no compile:** K3, K4h, E6, K5 and E5 are rows in `test_passive_routes_kind.py`,
  `test_transporter_kind.py` and `test_surface_pump_v3_populations.py` (tier 2), with their plants
  beside them. About 5 s.
- **Compiled:**
  - phase 1: K1 and K2 in one world with two species (zero net and relaxing), at two steps; its
    restart; and K4. About 120–180 s;
  - phase 2: Worlds 1 and 2, and World 1's restart. About 100–150 s.
- Each states its seconds and reason at landing.

## 6. Evidence that informed the bounds

The evidence is in `/mnt/workspaces/Cells/fr50-registration-20261123/probe/values.py` and its log.
It is a development aid on the declared values, not the reference and not an engine run:
- **K1's records** are 1e-5 fmol at 100 s.
- **K2's relaxation time** is 50 s, and dt k = 0.002 at 0.1 s.
- **K4 at equilibrium:** ΔG_cyc/RT is 0.0 in binary64, and J₊ = J₋ = 4.5454545455e-4 fmol of
  cycles per s.
- **E4:** u = 1/2 exactly, and the plant doubles each direction, to 0.1828 fmol/s.
- **The step rule's blind spot:**
  - a one-sided halving gives r = 1/3, and the corrected records come back to (1.000, 1.000);
  - a common-mode halving gives r = 0.

  These are the same facts as the design note's probe A.

**The bands.**
- The absolute band of 1e-11 allows a record's rounding over 1,000 steps, about 2e-13, 50 times
  over.
- The gap band of 1e-12 allows a steady pair's per-step rounding, a few times 1e-16, 1,000 times
  over.
- Every plant misses by at least 1/3 relative, or by a factor of 2.

**A limit to state.** The records follow the declared laws' independence assumption, which is
Ussing's flux ratio. Multi-ion pores depart from it, so the records are the model's one-way fluxes.
They do not predict isotope fluxes through such pores. No study is cited here, so this is not a
claim about any.
