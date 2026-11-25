# Ligand-gated store release (G-5) and assembly topology as a channel's availability (G-7): design

**Status: proposed, 25 November 2026. Design only: no engine code.** Branch `release-and-assembly-design` from
43b22d40. Main was at 34c56234 when the first version was written; it is at 1887337a (D385) now, and no ID has
changed. **Second reader:** 25 November 2026, with the lead's rulings on its table (`second-reader/REVIEW.md`
and `LEAD-RULINGS.md` of the lead's working folder); the rulings that concern this note (3, 7, 9 to 16) are
executed below. Two parts that can be built apart. Part I (G-5) is sections 1 to 9. Part II (G-7) is sections
10 to 18. The re-expression map this note answers is section 14 of `docs/LEGACY_PORT_PLAN.md` at a1db6ab9
("the map").

**Marks.** (M) I ran it. (R) I read it in code or a document at 43b22d40. (S) my own derivation or arithmetic.
(G) a guess. File references are to `src/cells/` at 43b22d40 unless another place is named. On
`legacy-cleanup` (149f9df9) 54 files of `src/cells` differ, among them `execution/grid.py`,
`execution/schedule.py`, `models/surface_tissue.py` and `models/surface_pump_v3.py`, so a builder re-reads the
lines; section 20.1 gives the edit sites there. (M2) the second reader measured it. All measured runs used
CPUs 6, 7, 22 and 23, under `nice`, on the CPU build of JAX, with a fresh compile each time. Section 22 lists
them.

**Engine models this note runs** (the milestone rule): `resolved_pump_tissue@3` (@3),
`resolved_pump_composite@1` over it, and `finite_bond_assembly@1`. Two parts of legacy were run read-only, as
references.

## 0. In short

- **G-5.** Today no species can set a store route's release. I recommend one new *source kind* of the routing
  door, `species_condition@1`. It has no state, books nothing, and gives one number in [0, 1] per declared
  condition: a product of Hill factors of concentrations at one node, evaluated at every stage. Stream D's
  release route names it in its `factors` list. Two conditions reproduce the ensemble: one for calcium
  (activation and inhibition) and one for IP3. A prototype of the kind ran on the live engine beside a
  compartment, unmodified (M).
- **G-7.** Today an assembly cannot set an availability. I recommend **no operator now**. A small driver runs
  the live pool and writes its switch times into the ionic world's `channel_controls`, as ordinary data. The
  ionic world is then an ordinary definition: `run`, `windowed`, `batch`, `resume` and `branch` work
  unchanged. The second reader ran legacy's own RK4 split only at the switches against legacy's split at every
  pool event: the pool's end state is bit for bit the live pool's, and the ionic difference is below 1e-5 of
  the criterion (M2). This is the general choice now, because the pool never reads the ionic side. The
  operator is recorded in section 15, with the three cases that would make it worth building.
- **Order and price.** G-7's driver first (1 to 1.5 agent-days): it needs no store and gives two of the six
  assembly worlds, the K-only ones. G-5's source next (1 to 1.75): it can be built and tested before stream
  D's route exists. The plan priced the two at 2 to 3 and 4 to 6 days.

### 0.1 Questions for the user

1. **G-7: the driver or an operator?** (a) The driver now, and the operator only when section 15's need
   appears. *Recommended.* 1 to 1.5 days. (b) The operator now: 4 to 5.5 days, plus a judged comparison. It
   moves the two K-only consumers from @3 onto the composite, which has no GPU, and keeps a held factor whose
   order can only be shown by a fit. (c) Both, driver first.
2. **G-5: a separate kind, or part of the store?** (a) A source kind that any route or @3 channel can name.
   *Recommended.* 1 to 1.75 days. (b) A release law inside stream D's store: about the same work, but in D's
   file, with the IDs and refusals of a store law, and it serves only a store.
3. **The driver's observable** (the lead's question A5). Legacy's rule for it was a versioned law,
   `root_component_has_cycle@1`: physics with no citation, stated as a hypothesis (section 11). (a) A plain
   selector word in the driver's input, no ID and no page. *Recommended.* 0 days more. (b) A registered law
   with an ID and a library page, under a new family word, for example `assembly_observable`, with one row in
   the choices file: 0.25 day, and the word is yours to give. In either case the composed file's fingerprint,
   the pools' seeds and the switch list are recorded in the run's inputs (section 13.2).

Otherwise nothing in this note needs a new family word (section 19). The two IDs of G-5 need rows in
`scripts/moves/id-rename-choices.json`, which is not my file.

### 0.2 Questions for the lead

1. **What retires** (section 5.10): `ph_condition@1`, either in G-5's landing (then + 0.75 day, and FR-5's
   worlds judged again in it) or after it (my recommendation); the coupling's instantaneous Hill on channels
   at that operator's next version; the two reserved `loop_term` fields, removed with their reasons. The dates
   are yours.
2. **A neighbour of the second reader's row 2** (R, section 5.10): a proton row that a cycle law moves at both
   ends has no material bound of its own in either layout of the transporter (version 1 has no material term;
   on the population axis the term covers neutral rows and charged rows changed at one end). Only its charge
   slope is bounded, and the kernel the proton pump declares for this, `loop_rates_per_s`, is called by one
   unit test only. It is not known to bind anywhere.
3. **IDs:** `species_condition@1` and `hill_product_factor@1` need rows in
   `scripts/moves/id-rename-choices.json`; tell the rename's owner.
4. **If a ruling cannot be executed** I say what I would do instead in section 20.2.

### 0.3 Words used here

A *source* is a kind that gives factors; a *sink* is a place whose control a factor multiplies. The *door* is
@3's routing door (docs/INNER_MODEL_V4_DESIGN.md section 7.4 (n)). A *condition* is one declared factor. A
*path* is a list of (time, value) points. *The ensemble* is the calcium ensemble of the map, 14.2. *RK4* and
*IMEX* are @3's two steppers; IMEX is `imex_ars222_face_electromigration@1` here. All amounts are in fmol,
volumes in pL, concentrations in mM (1 fmol per pL is 1 mM), times in s, voltages in V, energies in pJ.

# Part I. G-5: release gated by calcium and IP3

## 1. What is refused today, and where

| Wanted | Today | Where |
| --- | --- | --- |
| A species gates a store route's release | No source kind reads a declared species by a Hill law. The only sources are `cells.ph_condition@1` (the free proton) and `cells.patch_damage@1` (R: the only `factor_sources` in the tree) | `kinds/ph_condition.py:190`, `kinds/patch_damage.py:336` |
| The release as an @3 channel population on the store's patch | Refused by name: a pump or channel on a bounding patch | `operators/compartments.py:358` to 368 |
| The release gated by `species_regulated_availability@1` or `@2` | Refused by name: the target must be a junction or a channel; at `@2`, one of five operators' controls, none a store's (M) | `operators/species_regulated_availability.py:159`, 553 to 557 |
| An instantaneous read of a charged species | Refused by name: "reads the charged species instantaneously; @3's step moves it" (M for a -3 row at both versions; R: any nonzero valence) | 748 to 754 |
| A read through a two-state (regulatory state) | Admitted for a charged input (M), but the state is a model of its own: first-order memory in place of an instantaneous gate | 410 |
| A source named by a route that no kind exposes | Refused by name: "names unknown factor sources" (M) | `models/surface_pump_v3.py:1253` |
| Any declared kind under RK4 | Refused by name (M) | `models/surface_pump_v3.py:3412` |

What works today: a passive route's `factors` list (`kinds/passive_routes.py:529`), a charged constant-field
Ca route on a compartment's bounding patch, two such routes of Ca on one patch (a leak and a gated release),
and an impermeant ligand row at -3 with its binding by `local_species_reactions@1` (all M, sections 3 and
4.1).

## 2. The physics and the ensemble's numbers

Legacy's release, held here because legacy leaves the tree (R): `laws/reactions/er_calcium.py:53` and
`legacy/processes/ip3_release.py:8` to 13, with the concentration read of `legacy/models/ip3_calcium.py:73` to
91.

    f_Ca  = 1 / (1 + (Ka / c)^na)  x  1 / (1 + (c / Ki)^ni)            c = free Ca in the cytosol (mM)
    f_IP3 = 1 / (1 + (K / l)^n)                                        l = free IP3 in the cytosol (mM); 0 at l = 0
    J     = availability x f_IP3 x f_Ca x P A x GHK(z = 2, V_b)        fmol/s, store to cytosol

- Each factor is dimensionless and in [0, 1]; the two bind no calcium and no IP3 (a factor is a reading, not a
  consumption). J uses the store's and the cytosol's free amounts over their volumes.
- **Numbers** (R, `configs/ip3_calcium_cluster.json`): Ka 0.001 mM, Ki 0.02 mM, na = ni = 2; K 0.00015 mM, n =
  2; P 1e-7 m/s; areas 1e-9 and 1.4e-9 m2; store volumes 0.05 and 0.07 pL. Cytosol 0.5 and 0.7 pL. Free IP3
  5e-5 and 9.1e-5 fmol (1e-4 and 1.3e-4 mM), its neutral buffer 5e-4 and 7e-4, the bound form 1e-4 and 1.4e-4,
  binding rate 2e4 per s with the bound form's standard potential -9.2103 RT. All IP3 permeabilities are zero.
  Every schedule in the four captured calcium worlds is constant at 1, the release schedule included.
- **Where IP3 comes from.** Nothing makes or removes it in the ensemble. IP3 metabolism and the receptor's own
  binding (and so the depletion of IP3 by it) are not represented. The ligand is a conserved, impermeant row.
- **The opening is an instantaneous function of the read concentrations.** No gate state, no latency, no
  receptor inactivation.

## 3. IP3's charge (-3), as it is

- **What it is.** A species valence in the definitions (`configs/ip3_calcium_cluster.json`, the stores'
  species lists), not in legacy's code, whose parser checks only the species' name and moiety
  (`legacy/core/ip3_calcium_spec.py:61` to 82). `validation/chemistry/ip3_protocol.json:63` calls it "a
  nominal synthetic engineering choice, not a pH-dependent protonation model". No physiological charge is
  claimed here. The paper that measures IP3's protonation (Schmitt and others 1993, J. Chem. Soc. Perkin
  Trans. 2) could not be read: the site refused the request (HTTP 403), and it was not tried again.
- **What it does to the ensemble.** Nothing (M). The full 20 ms run of `configs/ip3_calcium_cluster.json`
  (1,601 rows) at -3, at 0 and at -5 gives all 25 saved state fields bit for bit the same. Only the reported
  background charges differ. IP3 is impermeant everywhere and each node's fixed charge is declared to balance
  the row.
- **What it does in the live engine:**
  1. *The capacitor sum.* `models/surface_tissue.py:376` to 381 says the sums are exact for valence magnitudes
     0, 1, 2, 4 and 8, and that every world in use has 0, +-1 or +-2. With a -3 row the host's and the
     compiled sum differ in 24,711 of 200,000 random columns (12%, up to 1.7e4 units in the last place in
     cancelling sums); at 0 or -4 they agree in all (M). It matters only where a held node's or an electrode's
     ledger is asked to close to the last bit, and these worlds have neither (the map, 14.1 finding 4). The
     note's sentence becomes false the day a -3 row lands.
  2. *Reactions.* `local_species_reactions@1` admits L + L_buffer to L_bound at -3, 0 and -3 and refuses a
     bound form at 0 (the net charge changes by 3) (M).
  3. *Sources and sinks* of a charged row need counter-ions (R, the same refusal).
  4. *The coupling's charged refusal* (section 1) does not stand in G-5's way, because G-5 does not use that
     operator.
- **Recommendation.** Keep -3 as data in the re-expressed ensemble: it is the captured definition, it is
  inert, and the worlds are closed. In a new world whose nodes are held, prefer a regulator valence in {0, 1,
  2, 4, 8} (S); there is no charge measurement that asks for 3, and these keep the sums exact.
- **A correction of the refusal's reason.** `species_regulated_availability`'s text says "@3's step moves it".
  For an impermeant charged row nothing in the step moves it: `species_registry.moved_in_step` lists no mover
  for the -3 row (M), and `check_unmoved_sources` (`:1583`) already asks the exact question. The refusal is
  right to fail closed, but its sentence is wrong for this case (corrected on `legacy-cleanup`, b677738c: it
  now says that an instantaneous source must be a neutral row).

## 4. Options for G-5, and what each loses

| Option | What it is | What it loses |
| --- | --- | --- |
| **A. A new target of `species_regulated_availability`** | Route the store's release as a coupling target | Held through the whole step (the read must be instantaneous and neutral, or be a state), so first order by the operator's own words; an instantaneous read of a charged row, and of any row the inner step moves, is refused; only a product of separable factors, one per coupling; `@2`'s operator targets are five named ones and the store is none; an operator's factor on a kind's control is refused (`models/pump_composite.py:893`), so a coupling cannot multiply a passive route's slot; an @3 channel on a bounding patch is refused anyway |
| **B. A release law inside the store** | Stream D's route carries its own gating parameters | Stage-exact and joint, but it is D's file and D's IDs. It reaches only a store. Other users of the same gating (G-3-like gating of an @3 channel, a luminal sensor) would need their own copy. The law itself is a pure function, so B can call this kind's function if D prefers |
| **C. A separate kind, a source of the door (recommended)** | The pattern of `kinds/ph_condition.py`, the mechanism `docs/INVENTORY_COUPLING_DESIGN.md` section 0.4 names for a stage factor, so no second mechanism | IMEX only (the door is refused under RK4); an opening in [0, 1] only (no flux-form graded release); the feedback bound is stream D's, with two hooks (section 5.5) |
| **D. A split operator with a look-ahead** | A gating operator with its own clock | A second clock and a held factor; not needed by a one-way reading |

**C is recommended.** The read has to be at the stage (a held factor is a changed model, the map 14.5) and the
door is the engine's one way to do that. It is general: the same kind serves @3's own channel slots through
B1's door. The other options are kept above so that the choice can be checked.

### 4.1 What a prototype showed (M, scratch only, live engine unmodified)

A source kind that reads two species at a cell's node ran inside `resolved_pump_composite@1` over @3, beside
`cell_owned_compartments@1` and `local_species_reactions@1` (one cell, one closed store, one gated Ca route,
20 ms). At 100, 50 and 25 us every host check passed. Ca released was 7.77628408390546e-5,
7.776285410453842e-5 and 7.77628574175738e-5 fmol: the halving ratio is 4.004, second order. The route's heat
never fell. The factor moved 0.2437 to 0.1982 to 0.1610 over the run. With the ligand at 0 the run at 50 us
was bit for bit the one at -3. Without the ligand's factor 3.077e-4 fmol was released, ungated 3.666e-4 (both
50 us).

### 4.2 The law is the live Hill law

The legacy IP3 expression equals `laws/reactions/hill_factors.py:41` `factor` bit for bit, 20,003 of 20,003
values on the host and compiled, and legacy's release opening equals exp(ln activation + ln inhibition) of it,
20,000 of 20,000 (M). At zero ligand: activation is exactly 0 and inhibition exactly 1, on host and compiled;
below zero both are NaN (M). So no new arithmetic is needed, only the declared form and its place.

## 5. The recommended design: `species_condition@1`

### 5.1 Declaration

Model key `species_conditions`, a list, each:

    {"id": "release_calcium_0", "node": "cell_0", "law": "hill_product_factor@1",
     "reads": [{"species": "Ca", "form": "hill_activation", "half_saturation_mM": 0.001, "hill_coefficient": 2.0},
               {"species": "Ca", "form": "hill_inhibition", "half_saturation_mM": 0.02, "hill_coefficient": 2.0}]}

- One condition is one factor: the product of its reads at one node. A node is any cell or outside node, a
  store's node included (a luminal reading), by its ID. `reads` is non-empty. A condition may read several
  species.
- The ensemble's release needs two conditions per cell: `release_ip3` (one activation read of IP3) and
  `release_calcium` (the two calcium reads), named in that order by the release route: `"factors":
  ["release_ip3_0", "release_calcium_0"]`, the order legacy multiplies in. The door multiplies them in
  declared order on the route's held value.
- The same condition can be named by many routes and channels. It is a declaration, not a route.

### 5.2 Law, units, signs, zero

For condition c at node v with reads j = 1 to J, species s_j, K_j (mM, > 0) and n_j (> 0):

    x_j   = N(s_j, v) / V(v)                       concentration (mM) on the stage's read
    z_j   = n_j (ln x_j - ln K_j)
    ln h  = -ln(1 + e^(-z))   for activation,  -ln(1 + e^(z))   for inhibition
    ln f  = sum over j of ln h_j                    a serial left fold, in declared order
    f     = e^(ln f)                                dimensionless, in [0, 1], multiplying a route's or channel's opening

- A higher activation reading opens, a higher inhibition reading closes. f multiplies the opening of a sink
  that has its own sign convention. For a store's route, that is stream D's (positive into the cytosol,
  section 7.1).
- Exact zero and one at zero ligand come from the law (ln 0 = -infinity). @3 keeps every row above zero at
  every node (`models/surface_tissue.py:414`, the domain), so no run reaches it; it is a property of the law,
  and a row tests it there. A negative or NaN reading gives NaN, and the door refuses the step.
- A condition's product is in one exp of one sum (as legacy's calcium opening, bit for bit). A condition per
  ligand and the door's left fold give legacy's `held x f_IP3 x f_Ca`, in its order, so at a held value of 1
  they give legacy's number bit for bit (S, from the two measured equalities of section 4.2).

### 5.3 Where and when it is evaluated

At every stage, by @3's own `_route` (`models/surface_pump_v3.py:1185`), after the stage read and before any
kind's rates, and at observed rows for its readout. The read state is the stage's (the free form where a
closure owns the row, as `ph_condition` reads free protons). There is no operator, no clock, no held state, no
control view. So the order is the stepper's, second on IMEX, measured above. Host and compiled use the same
function. It has no platform branch.

### 5.4 State, ledgers, heat and work

None. A factor is not a flux: it owns no amount, charge or energy row, has no work or heat role and no ledger.
The route it multiplies books everything, by its own kind, as today:
- **Amount:** the release moves n fmol from the store's node to the owner's, recorded once by the route
  (`passive_transferred`).
- **Charge:** the route's own, 2 per Ca, carried by its flux into the membrane current and by its slope in the
  stage rule (`stage_term`). Its kind books it.
- **Energy:** the route's heat, from its kernel's dissipation rate, is non-negative at a fixed factor. A
  gate's opening and closing costs no energy here (legacy's convention, and the door's for damage and pH).
  That is a modelling choice, stated once.
- **The closing is the route's:** nothing in this note adds to or takes from any global sum, so every closing
  that stands today stands.

### 5.5 The feedback hooks (the adopted form)

The bound on the feedback a factor brings is stream D's and is built (L3). The lead adopted this note's form
of the source hooks (ruling 9 on the second reader's table), with four additions, and ruled where the term is
added (3) and what it does not bound (7). The three sides are stated here so that both builders write against
one text. The stage rule is `material_rate` (`models/surface_pump_v3.py:3701`).

**The source's hooks,** optional fields of `registry/kind_registry.py`'s `Kind` (default None). A kind that
has one must have both, and binding refuses one alone by name.

    factor_rows(declaration) -> ( ( (species ID, node ID), ... ), ... )

- Host only, once, at binding. One tuple of pairs per source, in the order of `factor_sources(declaration)`. A
  pair is a (species ID, node ID) whose amount that source's factor reads. Each pair once per source, in order
  of first appearance.
- Names only: no index, array, model or unit.
- For the recommended kind: per condition, the distinct species of its reads, each with the condition's node.
  The ensemble's two conditions give ((("IP3", "cell_0"),), (("Ca", "cell_0"),)).

      factor_log_slopes(read, p, *, xp) -> array [P]        d ln f / d ln n, dimensionless, signed

- P is the number of pairs, flattened: sources in `factor_sources` order, then that source's pairs. n (fmol)
  is the amount of that row at that node on the stage's read, and the arguments are `factors`'.
- For the recommended kind, for the pair (condition c, species s): sum over the reads j of c with species s of
  sign_j n_j (1 - h_j), with sign +1 for activation and -1 for inhibition and h_j as in section 5.2; (1 - h_j)
  is 1 / (1 + e^(z_j)) for an activation and 1 / (1 + e^(-z_j)) for an inhibition. Finite, 0 for a padded
  read, in [-sum n_j, sum n_j]. The sum is signed within one condition and one species. The core takes the
  magnitude.

**The sink's hooks** are stream D's, stated so that the two texts agree:

    routed_rows(declaration) -> ( ( (species ID, node ID a, node ID b), ... ), ... )
    routed_flux(read, potentials, control, p, *, xp) -> array [M]      fmol/s

- `routed_rows`: one tuple of moved rows per routed slot, in `routed_controls` order. A passive route moves
  one row; a channel population one per permeant ion.
- `routed_flux` is evaluated **at the routed control** (the door's result), never the held one. M is the
  number of (slot, row) pairs, flattened: **one J per slot and row**. Only |J| is used. @3 is the sink of its
  own channel slots and has the same two in the core.

**The static pairing.** At binding the core makes `InnerStructure.loops = ((m, p), ...)` from the names: m is
a (slot, row) of a routed slot and p a pair of one of that slot's sources, where the pair's (species, node) is
an end of a row the same slot moves, and the node is not a held bath (a held amount does not move, so it
closes no loop). Every row of the slot pairs with every such p. These are positions: they enter the structure
and are value-free. The indices of the padded arrays **cannot** enter it, because `structure(model)` is built
from the model alone and knows no capacities (`models/surface_pump_v3.py:5041`). They are **layout fields**,
present only where `loops` is not empty, as FR-51's are (`BLOCK_LAYOUT_FIELDS`, `:189`): `loop_pair_row`,
`loop_pair_node` [P], `loop_flux_row`, `loop_flux_end_a`, `loop_flux_end_b` [M].

**The rule,** in `material_rate`, after its stage read and the door's `_route`, at every place that rule runs
today (the step's first explicit stage, `:2830`, and each later one, `:2941`):

    rate(m, p)  =  (|J_m| x |slope_p|) / max(n_p, tiny)          1/s, J in fmol/s, n in fmol, tiny the smallest normal float64
    rows[species_m, a_m] and rows[species_m, b_m]  +=  sum over the pairs p of m of rate(m, p)
    nodes  +=  max over species of rows

- **The factor is inside the product.** J is routed, so it contains f; the product is formed before the
  division, so f is inside df/dn, and the part of dJ/dn that goes through this factor is |J| |slope| / n. At a
  zero amount f and J are 0 and the quotient is 0 / tiny = 0, finite; without the floor on n, or with the
  division first, it is NaN (0 / 0 or 0 x infinity; M2, `feedback_zero`). It is finite there but not a bound
  at exactly zero: the direct slope is 0 at coefficient 2, 264 per second at coefficient 1, and unbounded
  below 1 (M2). On @3 no row reaches zero (`models/surface_tissue.py:414`), so it is unreachable today. It is
  covered anyway, and a row holds it.
- **The held control is not used.** At an amount of 1e-9 fmol the held flux times slope over n is 4e7 per
  second and would refuse every step; the routed one is 7e-3 (M2, the same probe).
- **Both ends, per moved row** (ruling 3). The route's flux changes both of its rows, and every other row of
  the slot (a channel with several ions) depends on the factor too, so each (slot, row) adds its term at both
  of its nodes. A held bath's row is dropped by `material_rate` already.
- **D148.** Where `loops` is empty nothing changes.

**What the source costs at a stage (S, no timing).** With C conditions and R reads in all, `factors` takes R
logarithms, R `logaddexp`, R - C additions and C exponentials. `factor_log_slopes` adds R evaluations of (1 -
h), R multiplications and a sum per pair; P divisions are the core's. No linear solve, no node-sized array.
The ensemble has 2 conditions and 3 reads per cell. In one compiled stage the two hooks share their logarithms
(XLA's common-subexpression step, S). It is small against the field solve and the passive routes' kernels, and
it is evaluated at the two explicit stages of ARS(2,2,2).

**Size in the ensemble (S).** The bound is stream D's, 6 per second there (its figure, and d ln f / d ln c =
0.38 is 0.4 - 0.02 from my formula). My own cap is 20 per second, since the sum of n_j / 4 over the reads is
1. It binds nothing at 12.5 us (dt x L 7.5e-5 to 2.5e-4).

**Limits, to be stated in both notes:**
- Loops through two routes (one moves X and gates on Y, another moves Y and gates on X) are not bounded.
- **Loops through a source that has no hooks are not bounded, today `ph_condition` and `patch_damage`**
  (ruling 7). They are used (FR-4, FR-5), so they are not refused, and their docstrings say so
  (`kinds/ph_condition.py:1` to 31, `kinds/patch_damage.py:1` to 51). The hooks for them are a follow-up for
  the lead to log, not built here.
- A Hill coefficient below 1 has no finite d f / d n as n goes to 0: the stage rule then refuses at a trace
  amount (at coefficient 0.5 and 1e-160 fmol the direct slope is 1e80 per second, M2). It is admitted, and the
  refusal is right.
- Where a closure owns the read row, the stage read's n is the free amount while the route moves the total,
  and the closure's own slope is not in the hook. No captured world has one on a row a gated route moves. If a
  later world needs it, the closure's owner supplies that slope, as the proton pump's loop kernel does
  (`laws/pumps/proton_pump.py:153`).

### 5.6 Refusals by name

Each refusal names the kind, the condition and the thing: an unknown node;  an unknown species; a law other
than `hill_product_factor@1`; a form other than `hill_activation` or `hill_inhibition`; an empty `reads`; a
half-saturation or coefficient that is not finite and positive; a condition ID that is not unique among the
model's IDs; a factor source exposed by two kinds (the door, today); an unknown source in a sink's list (the
door, today); RK4 (the kind rule, today). A bath node or a held row is admitted: its factor is constant (M). A
row held by a closure is read at its free form. A factor outside [0, 1] or not finite refuses the step (the
door, today).

### 5.7 Restart, branch, D148, GPU, composition

- **Restart and branch.** No state. Its layout fields are constants and are saved and compared with the rest
  of the layout.
- **D148.** A definition without `species_conditions` holds no kind, no layout field, no route entry and no
  program change. The structure entry is value-free (the number of reads of each condition), so two worlds of
  the same shape share programs.
- **GPU.** The kind has no platform code. Its worlds are composites, whose GPU is refused
  (`execution/vector_windows.py:213` to 230), so no GPU claim is made.
- **Composition:** it is a *source* by refusal 4's rule (`operators/compartments.py:125` to 133: none of
  `stage_term`, `material_term`, `bound_rate`, `held_rows`, `stage_read`, `stage_check`, `ledger_terms`), so a
  compartment admits it, and a world without one needs nothing. The two hooks of section 5.5 are not on that
  list, so a source that has them is still admitted. The matrix:

| Beside | Result | Basis |
| --- | --- | --- |
| A compartment (`cell_owned_compartments@1`), a charged route, `local_species_reactions@1` | admitted | M, section 4.1 |
| `cells.passive_routes@1` and @3's channels as sinks; a plain @3 world | admitted | R; M, `at3_kind` |
| **Water** (`ideal_osmosis_linear_compliance_water@1`, with or without `k_anion_symport_mass_action@1`) | admitted; the factor reads the current volume: in a world whose cell volume fell 1.6% the observed factor rose from 0.4861 to 0.4941, as N / V at the current volume gives | M, `compose_probe`, `water_volume` |
| **Labels** (`neutral_arrival_labels@1`) | admitted: K labelled, and Ca labelled and moved by the gated route, in the prototype's world; a gated route's one-way flows use the routed control at both ends of the step (R) | M (parse), `labels_probe`; not run |
| **Wash** (`scheduled_compartment_wash@1`) | admitted: the wash refuses a kind's *route* that moves a neutral species across the washed node's surface (`operators/wash_schedule.py:77`), and the source is no route | M (parse), `compose_probe` |
| A closure (`rapid_binding@1`, `rapid_proton_buffer@1`) on a read row | admitted; reads the free form | R |
| A held bath's row (or `scheduled_bath_composition@1`) | admitted; a constant, or piecewise constant, read | M (a held bath) |
| `scheduled_cell_replacement@1`, `@2`, `scheduled_membrane_trafficking@1` | refused by name, beside any declared kind (they build today's fixed inner fields) | R, `models/pump_composite.py:864` to 869 |
| A closer or a retiring operator (`isopotential_partition@1`, `scheduled_membrane_insertion@2`) | refused by name until the kind declares partition roles, as `ph_condition` is today | R; M, `lifecycle` |
| RK4 | refused by name | M |

### 5.8 Provenance

The form is Hill's, in its Weiss 1997 presentation (doi:10.1096/fasebj.11.11.9285481, cited from a secondary
index, not read) and in Bezprozvanny, Watras and Ehrlich 1991 for calcium's bell-shaped dependence
(doi:10.1038/351751a0, found, not read). Mak, McBride and Foskett 1998 (doi:10.1073/pnas.95.26.15821, read
through a page tool; its equations were images) reports that IP3 tunes the calcium *inhibition's*
half-saturation: one laboratory, Xenopus oocyte nuclei, so an indication only. A joint law is later work and
would be its own version: `hill_product_factor@1` is separable by its form and does not represent that. The
numbers are legacy's, not measurements (section 2).

### 5.9 Layout, readout, axis and view

- **Layout fields** (padded to the largest number of reads, R; C conditions). The structure entry is (the law
  ID, and per condition its number of reads and of pairs): no value, so two worlds of one shape share
  programs.

| Field | Shape | What |
| --- | --- | --- |
| `species_condition_node` | [C] int64 | the node: cells, then outside nodes, as the passive routes index them |
| `species_condition_row` | [C, R] int64 | the species row a read takes (0 in padding) |
| `species_condition_form` | [C, R] int64 | 1 activation, 2 inhibition, 0 padding (the codes of `hill_factors`) |
| `species_condition_half_saturation_mM` | [C, R] | K (1 in padding) |
| `species_condition_coefficient` | [C, R] | n (1 in padding) |
| `species_condition_pair` | [C, R] int64 | the flattened pair of the read, for the slopes' sum |

- **State and control fields:** none. **Readout column:** `species_condition_factor`, [condition], f on the
  observed row's read; unit 1.
- **Axis:** `species_condition`, the kind's own, one entry per condition, no slot. **Partition roles:** none
  in version 1, so a closer refuses the kind (section 5.7).
- **View** (`KindView`, D154): units {"species_condition_factor": "1"}, observation axis
  ("species_condition",), record kind "level", record layer "membrane" (as `ph_condition`). Its set: the IDs;
  role "node: the node whose concentrations set the condition"; kind "factor"; the law; `at` the node; and
  `reads`, each with its species, form, K and n. The legacy readout `ip3_release_fraction` is the IP3
  condition's column, and `ip3_cytosol_mM` is a formula of the amounts (the map, 14.6).
- **Definition round trip:** `to_dict` writes the declared entries with the law's full ID, as `ph_condition`
  does.

### 5.10 What retires, and when

One source of factors where the shapes agree, else two with the reason (ruling 13; D210; pre-alpha, no
backwards compatibility).

| Old | New | Do the shapes agree? | When |
| --- | --- | --- | --- |
| `ph_condition@1` and its law `ph_conditioned_factor@1` (a source) | `species_condition@1` with one `hill_activation` read of the proton row, K = 10^(3 - pH50) mM, n = the slope | Yes as a function: on 20,000 random points the two differ by at most 2.3e-15 absolute, 5,222 are bit for bit equal. The pH law's tanh form loses relative accuracy at a small factor (up to 3e-11 relative where f > 1e-6) (M, `ph_same`) | The user's standing direction is to retire a superseded mechanism when its replacement lands. (i) In G-5's landing: + 0.75 day, FR-5's worlds re-expressed and judged again in it; its results move by rounding. (ii) After it, my recommendation: FR-5's judged records cover the build they judged, so G-5's landing stays bit for bit for them; from that landing no new definition uses `ph_condition`, its docstring names its successor, and it retires when FR-5's worlds are judged again (0.75 day, G). The lead picks |
| The instantaneous Hill of `species_regulated_availability@1` and `@2` on a **channel** population (a neutral species in the channel's own cell) | a condition named in that channel's `factors` | Yes, where the row is one the inner step does not move, the coupling is always on, basal is 0, the world is IMEX and the target is a channel: the factor is the same number at every stage, so the product is bit for bit the coupling's (S; a host row holds the two factors equal, section 8) | Frozen at G-5's landing: no new instantaneous species-to-channel use there. It retires at the coupling's next version, when its judged worlds (A5, the later A5 acceptance) are judged on the door |
| The rest of that operator | none | **No, so two.** The coupling also targets junctions and other operators' rates; its factor is held and works under RK4; it has basal, switches and an identity rule; its sources include two-state, population and site quantities. The door has channel and route sinks only, is IMEX only, and has no basal or switch | stays |
| `patch_damage@1` | none | No: it has a state and schedules | stays |
| `ChannelLaw.loop_term` (`registry/laws.py:377`) | none | No law declares it and nothing reads it. A channel population's loop is bounded through `routed_flux` (section 5.5) | removed, with that reason |
| `CycleLaw.loop_term` (`:446`) | none | No code evaluates it. Only the proton pump declares it (`laws/pumps/proton_pump.py:137`, 265). A cycle law's own loop is the transporter's material term, which takes it from the law's `d_j_d_ln_c` and the closure's derivative (`kinds/transporter.py:2225` to 2264), not from a declared kernel | removed, with that reason: the field, its check (`:482`) and the two lines of `proton_pump.py`. `loop_rates_per_s` stays as a tested function (`tests/unit/test_fr45_proton_laws.py:407`), documented as not evaluated by the engine |

The removal loses a name, not a bound: what the transporter bounds today, and what it does not (section 0.2,
question 2), is unchanged by it.

## 6. Same equations or a changed model

- **Same equations:** both factors, their parameters, the read of free concentrations, the GHK flux at z = 2,
  the place (at the stage) and the order (release multiplied by the product). The candidate's order is 2, by
  IMEX. So the band of the map's section 8 template can apply, at each consumer's own steps.
- **Changed model, so a criterion of the consumer's own:** a factor held through the step, a factor read
  through a two-state, or a held bath where the world is closed.
- **Two consumers, two statements:** the four `spatial_calcium` worlds need only the calcium condition (`@1`
  to `@3`) or both (`@4`). The four assembly-regulated calcium clusters need G-5's and G-7's parts at once,
  and G-7's schedule multiplies Kv1.5 only (the map, 14.3). Cardiac graded release (D211 and the plan's row
  I6) is another mechanism: it is driven by the L-type current and it is a flux state. Folding
  `ip3_er_release@1` into it would be wrong (section 21, item 7).

## 7. What G-5 needs from others

### 7.1 From stream D (through the lead)

D's note (`docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md` at c5006ff6) answers most of what this part needs (R,
its sections 5.1, 6.5 to 6.7):
1. The release is one more `passive_constant_field_permeation@1` route of Ca on the store's bounding patch,
   with a `factors` list, apart from the leak. The door and the sink exist; a second Ca route on that patch is
   admitted (M).
2. The sign: J is fmol/s into the cytosol. The condition's node is the owner's cell.
3. The calcium row is the free one, buffers are split reactions, and no closure owns it: a charged route
   refuses a row whose free and total a closure holds (`kinds/passive_routes.py`, the charged law's rule).
4. The factor must be in [0, 1], finite, at each explicit stage, on the stage's read. Section 5.3 and the
   door's check (`models/surface_pump_v3.py:1198`) do that.
5. The route books heat only, by the tableau, and D says these routes stay far from a reversal; a release that
   crosses its own reversal could be refused (its L9, and section 3.8 of the cardiac note, read and not run).
6. The bound on the feedback a factor brings is D's, with the hooks of section 5.5. D's `routed_rows` and
   `routed_flux` are D's. The hook's form is settled: the lead adopted this note's (d ln f / d ln n, signed,
   dimensionless) with four additions (ruling 9), and D's text is to follow it. Nothing is open between us.
7. **Before any store world,** the corrected charge rule (the second reader's row 1: a cell's slopes divided
   by the plasma patches' capacitance alone) is its own commit. It is not this note's, and a store world
   should not be built before it.

The lead's ruling on channels also concerns G-7: a calcium channel is a population on @3 whose law declares
its ions' valences, so G-7's factor acts on channel populations through `channel_controls` and needs no change
for it (section 13.1).

### 7.2 From the core and the rename

Two optional hooks of the kind registry (`factor_rows`, `factor_log_slopes`), the loop fields of the structure
and the layout, and their call in `material_rate`: that edit is D's step 6, in the core's files. Otherwise
nothing in the core changes.

## 8. Tests for G-5 (rows, with plants)

Rows go into files that exist, except the engine rows, which are a new feature and get one file that states
its seconds (D224). Recorded seconds today: `tests/unit/test_fr5_source_kinds.py` 5.64,
`test_fr5_source_kinds_engine.py` 67.28, `test_hill_factors.py` 2.82, `test_passive_routes_kind.py` 75.57
(`tests/test_tiers.json`; the cap is 90 s, and the two engine files have no room for more worlds). Seconds
below are guesses (G) until measured.

1. `test_hill_factors.py`: the law's product of J factors equals the exp of the sum of the live `log_factor`s
   bit for bit at random points; exact 0 and 1 at zero; NaN below zero. *Plant:* inhibition read as activation
   must fail. About 1 s.
2. `test_fr5_source_kinds.py`: the declaration's refusals (section 5.6), one row each, and the stateless
   layout, the readout column, the axis and the view's entries (section 5.9). Host only, under 1 s.
3. Same file: the hooks. `factor_rows` returns the declared pairs once each, in order, names only;
   `factor_log_slopes` equals a central finite difference of ln f in ln n over random states, and at a very
   small and a very large amount, and is 0 in padding. A zero amount gives a finite rate when the product is
   formed first. *Plants:* the sign of an inhibition dropped; the derivative taken in n; a pair listed twice;
   the division before the product (NaN); the held control in place of the routed one. About 1 s.
4. A new `tests/unit/test_species_condition_kind.py` (about 45 s, mostly one compile): one @3 world under IMEX
   (one cell, one outside node, one charged Ca route of `passive_constant_field_permeation@1` on a plain
   patch, gated by the condition; 1 ms; 50, 25 and 12.5 us), so the kind is tested with no compartment and no
   composite (M, `at3_kind`: the prototype kind parses and runs in such a world). Rows: the moved amount
   halves with a ratio of 4 within 5% (*plant:* the factor held at the step's start must fail the ratio); an
   impermeant ligand at valence 0 gives the run at -3 bit for bit (*plant that tests valence:* a reading
   scaled by |z|, so a factor that uses the row's charge, must fail it); the condition on the wrong node
   differs (*plant*); K in M for mM differs (*plant*); reading the bound row for the free one differs
   (*plant*).
5. In the same file, one composite row: the prototype's world (section 4.1), 10 steps, admitted beside a
   compartment, with the heat never falling. About 25 s.
6. D148: a definition without the key keeps its structure entry and its program (an equality check on the
   structure, no run). Host only.
7. A condition as a source of an @3 channel slot: host only, the routed control equals held x f.
8. A compartment world admits the kind; a source that also declares `bound_rate` is refused there (one parse
   row each).
9. The coupling's factor at basal 0 and the condition's, for one neutral species at random points and both
   forms, are the same number bit for bit (host only, about 1 s), which holds section 5.10's agreement of
   shapes.

D's rows 11 and 12 (the feedback bound against a finite difference of the stage's derivative) use the two
hooks. The two-cell closed row (two cells, near and far, two free offsets, the floor solver by
`field_solver_choice.declare()`, a junction Ca route and two stores, compiled, tier 2) is stream D's (ruling
14); this kind is in it, with the plants 'cell_0's condition reads cell_1's node' and 'K and n exchanged'.
The consumer's own row (the ensemble's release against captures) belongs to the re-expression, not here.

## 9. What G-5 does not claim

No receptor, no IP3 production or removal, no receptor binding of IP3, no inactivation or adaptation, no
wet-lab agreement; no claim that the Hill parameters are measured; no claim about a GPU. Nothing here
qualifies D's route, its heat booking or its step bound.

# Part II. G-7: assembly topology as a channel's availability

## 10. What is refused today, and where

| Wanted | Today | Where |
| --- | --- | --- |
| An operator that hosts a pool | Refused by name: "Each operator names a registered law" (M) | the operator registry, `registry/operators.py:176` to 181 |
| A coupling whose source is an assembly's quantity | Refused by name: "a coupling's law is one of hill_activation, hill_inhibition, state_fraction, state_complement"; a site's fraction needs the operator that holds it (M) | `operators/species_regulated_availability.py:721` |
| An operator's events at times off its clock's grid | Refused: an operator's times lie on the step grid | `models/pump_composite.py:2102` to 2105 |
| A conditional availability schedule | None: `channel_controls` is declared data | `definitions/surface_pump_v3_spec.py:636` and 809 to 811 |
| The pool inside the ionic step | None. Only legacy's `assembly_regulated_cell@1` and `assembly_regulated_cluster@1` couple them, on legacy models | `legacy/assembly_cell/kernel.py:29`, `legacy/assembly_cluster/kernel.py:20` |

**What works today:** a `channel_controls` schedule whose changes are at any times (M, section 13), and the
live pool as a run of its own.

## 11. The law and its numbers

Legacy's coupling, held here (R): `legacy/assembly_cell/kernel.py:23` to 26 and 29 to 55,
`legacy/assembly_cluster/kernel.py:15` to 17 and 44 to 60, `legacy/assembly_cluster/controls.py:22` to 29,
with the law's own name `root_component_has_cycle@1` in the config.

    cyclic(pool)  = popcount(bonds) >= popcount(occupied)          (E - V + 1 >= 1 on the connected root component)
    level(pool)   = active_availability if cyclic else inactive_availability      (the ensemble: 1 and 0)
    g(t)          = base(t) x level(t)        multiplies the channel populations of the pool's owner cell

- *The cycle count.* The assembly a pool tracks stays connected to its root (a state invariant, R), so E - V +
  1 is its number of independent rings, and "at least one ring" is popcount(bonds) >= popcount(occupied).
- *What it multiplies.* Kv1.5's channel slots (`control.channel`) of that cell only. Legacy's `modulate` also
  scales a mobile-channel control where the owner table has one; no used world does. Cav1.2, the pumps and the
  release have separate controls (`legacy/models/gated_calcium.py:93` to 95).
- *The events drive it, not the step.* A cell's pool is one event-driven walk: an event at t_k changes the
  pool, so the level is right-continuous at t_k. The segment before t_k has the old level (R). A pool never
  reads the ionic state, so nothing in the ionic world changes a propensity.
- **The pool (`finite_bond_assembly@1`, live).** The 20-site graph of the engineered cage
  (`dodecahedron_g10_2@1`), initial nodes 10, 12, 14, 16, 18 (a ring of five), root 10, 50 free subunits,
  5e-15 L, k_on 1e7 per M per s, dissolve 1 per s; k_close 1000 per s in the cluster and 100 in the cell;
  k_off 300 and 10 per s. Those are the ensemble's numbers, not measurements. The assembly model's source
  (Asor and others, Nature 2026, as docs/CAPSID_ASSEMBLY.md cites it) was not read here.
- **Seeds.** The kernel draws threefry2x32 of (seed, world, event count) (`assembly/kernel.py:83` to 94). Each
  pool's definition carries its own effective seed. Legacy's parser only checks that `seed - stream_id` is the
  same for all pools of a world (`legacy/assembly_cluster/spec.py:188` to 214), and the kernel gets each
  pool's `seed` unchanged (`engine.py:312`): 20260925 for cell_0 (stream 0) and 20260926 for cell_1 (stream 1)
  in the cluster's definition. Each event is drawn from its own counter, so the walk does not depend on how a
  run is cut.
- **Provenance.** The law is a hypothesis stated in `validation/assembly/cluster_protocol.json` ("The presence
  of a cycle in the retained assembly controls its owner's channel availability"), with no literature source
  and no feedback. The pool's own provenance is the assembly's (docs/CAPSID_ASSEMBLY.md).

## 12. The options, with numbers

**How long is a step's hold?** (M, `hold_order`). World: the base cluster, 16 worlds, 20 ms, 2 cells.
Reference: legacy's own event-split RK4 at 12.5 us. Candidates: legacy's own ionic RK4 on a fixed grid (not
the composite), with each cell's availability held over the step by its value at the step's start, at its
middle, or its exact mean over the step. Worst error at 20 ms over every ionic field, in units of the
consumer's criterion (3e-9 |e| + 3e-12, `validation/assembly/cluster_protocol.json`):

| Step (us) | 100 | 50 | 25 | 12.5 | 6.25 | 3.125 | order by a fit over six steps (RMS of the 16 worlds) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| start of step | 19,766 | 5,255 | 3,281 | 2,233 | 1,035 | 612 | 0.95 |
| middle of step | 10,811 | 6,426 | 2,785 | 1,332 | 641 | 324 | 1.00 |
| exact mean over the step | 23.1 | 7.23 | 1.64 | 0.557 | 0.0955 | 0.0301 | 2.01 |

- A value held at the start or the middle never meets the criterion at any of these steps. The mean meets it
  at 12.5 us and below. The mean needs the next event's time: a look-ahead inside the step, or the whole path
  in advance.
- **Order can only be shown by a fit.** Switches fall at random phases inside a step, so the three-step order
  of the map's section 8 (h, h/2, h/4) scatters: a world's local order ranges from -1.1 to 4.4 for the mean
  and from -4.4 to 6.9 for the middle, and a world's fit over the six steps is 1.6 to 2.4 for the mean (median
  2.1) and 0.55 to 1.6 for the middle. FR-43 part 3 reached the same conclusion
  (`docs/FR43_PART3_BUILD_PLAN.md` section 11: event error C dt2 phi (1 - phi), order by a fit).
- **Switch times are the pool's own** and are few: 2 to 14 switches per world in 20 ms (both cells together,
  94 in 16 worlds), against 1,600 steps of 12.5 us.

| Option | What it is | Verdict |
| --- | --- | --- |
| **F1. The composed run by hand** | Run the pool, read its path, write the schedule into the definition yourself | Works today (M) but is hand work: wrong factors or seeds are silent |
| **F2. A "driven world" family** | One command that resolves the paths and runs the ionic world, a definition kind of its own | 2 to 3 days. A new family word, so it goes to the user. Not needed to start |
| **F3. An event-cut composite step** | The composite splits its step at the pool's events as it runs | Rejected: the clock is built before the run, from declared times. An event found during the run cannot become a step boundary. F4 gives the same times as data |
| **F4. A small driver (recommended)** | A live module that turns a pool run into `channel_controls`, plus a subcommand | 1 to 1.5 days |
| **F5. An operator hosting the pool** | `cell_assembly_pool@1`, later (section 15) | 4 to 5.5 days, plus a judged comparison |
| **F6. A kind on @3; extending `integer_unit_population@1`; assembly lineages** | Three other homes for the pool | Rejected: a kind cannot own a clock; a unit population counts units and has no graph (no topology); lineages hold no topology |

## 13. The recommended form: the composed run (F4)

### 13.1 Why it is the general choice now

- **The pool never reads the ionic side.** A one-way drive has no loop to hold inside a step, so nothing in it
  needs an operator. It needs the switch times to be exact, and the clock already takes them as data.
- **It is exact, and simpler than the operator.** The level is piecewise constant, so its exact value on every
  piece is data. The step's boundaries fall on the switches, so the stepper keeps its own order: 4 on RK4, 2
  on IMEX (S, and section 13.5). No held factor, no new error.
- **No second clock and no copied state.** The pool has one clock, its own, in its own run. The ionic world
  has one clock, `EventGrid`. The only thing that crosses is a list of (time, level) pairs, which is data in a
  definition. Nothing in the ionic world can write the pool back.
- **It stays on the K-only model.** An assembly cell and the base cluster are @3 worlds. An operator would
  force the composite.
- **It acts on channel populations.** It writes `channel_controls`, so it drives any law on an @3 channel
  population: Kv1.5 here, and a calcium channel population when stream D's form (a population whose law
  declares its ions) lands.
- **Reuse.** The driver does not know Kv1.5 or calcium: it knows pools, owners (channel IDs), two levels, and
  an observable's name. Anything that writes a path can drive any schedule.

### 13.2 The definition and the driver

`cells assembly-pool resolve COMPOSED.json --output DIR` (and `run`, which resolves and runs the worlds). The
input is a strict JSON object with exactly the keys `schema_version`, `ionic` and `pools`. It has no new ID or
kind word. `ionic` is an ordinary definition (`resolved_pump_tissue@3` or `resolved_pump_composite@1`). Each
entry of `pools` is:

    {"channels": ["channel_0"],            the channel populations it sets, each set by one pool at most
     "observable": "root_component_has_cycle",   a name from a short table; one for now
     "levels": {"false": 0.0, "true": 1.0},      in [0, 1]
     "pool": {...}}                        an ordinary finite_bond_assembly@1 definition, with `worlds` W

Outputs, in DIR: `pools/` (the pool runs, ordinary `finite_bond_assembly@1` output with `recording:
"events"`), `resolution.json`, and one ordinary definition per world (or `batch.json`, an `independent_worlds`
batch, one world per pool world). The ionic definition is untouched except its `channel_controls`.

- Module: `src/cells/assembly_pool/schedule.py` (names: `SwitchPath`, `ChannelDrive`; pure functions over
  arrays). It calls `assembly_pool.engine.run` and the live `kernel.step` unchanged.
- The path is walked in one place: for each committed event it evaluates the observable and keeps the points
  where the level changes. The first point is at time 0.
- The base schedule of a channel is multiplied: for every base change and every switch the new value is
  base(t) x level(t), both right-continuous.
- **The definitions' `channel_controls` are the source of what runs.** A run reads nothing else.
  **`resolution.json`** is generated beside them as provenance: for each pool and world, the pool's definition
  fingerprint and its seed, the number of events, each switch as (time, level, event count), the exposure (the
  fsum of level x duration), the final pool state and the ionic fingerprint. No run reads it, and a check row
  holds it equal to the definitions' schedules.
- **The run's inputs.** The ionic definition's fingerprint holds the schedule's numbers and nothing else: not
  the pool, its seed or the rule. So `resolve` also writes `inputs.json`: the composed file's SHA-256, each
  pool's definition fingerprint and seed, the observable (its law's ID if A5 is (b)), and the switch list of
  each world. The existing record is the writers' `provenance` argument (`records/io.py:259` and 363,
  `records/batch_io.py:239`, `records/window_io.py:227`, `records/batch_window_io.py:189`), which the run
  drivers under `validation/` already fill (R). So `inputs.json` goes into `provenance["composed"]`: the
  driver's own `run` subcommand passes it when it runs the worlds through the existing runners, and the
  re-expression's run drivers do the same. No edit to `__main__.py` or `records/`. A run started by `cells
  run` on a written definition is an ordinary run of that definition, and its manifest holds no composed
  inputs, so registered runs go through the driver or a run driver.
- The definitions are written as JSON text, with no shared objects (section 21, item 8).

### 13.3 Switch times

Legacy splits its step at every pool *event*; the driver splits at the *switches* of the level, a subset. The
second reader compared them on legacy's own RK4 for the base cluster (M2, `split_equivalence`, 4 worlds, the
same seeds): against legacy's split at every event, the split at the switches alone differs by 2.9e-6 to
9.3e-6 of the criterion at 50 us and by 1e-7 to 1.8e-7 at 12.5 us, and the split at every event by 4e-8 to
7e-8. Both are far below the criterion. The pools' end states, uncut, are bit for bit legacy's in all four
worlds and both cells (M2).

- Switch times are the pool's own float64 times, never rounded to steps. The clock splits the step that holds
  one (`execution/grid.py:3` to 6). A time within rounding of a grid point snaps onto it and is recorded
  (`applied_definition`).
- The clock refuses a near miss: a time more than rounding and at most 1e-6 of a step from a grid point
  (`grid.py:55`, `_near_point`). The driver finds it before any run and names the world, pool and switch. It
  refuses by default. An explicit option declares it at the grid point and records the shift. The chance is
  about 2e-6 per switch (S). The second reader found none (M2, `pool_paths`, 4 captured seeds, the base
  cluster, the cell and the four calcium clusters, at every captured step and its half and quarter): no near
  miss, no snap, no tie between pools, and the smallest gap between two switches of one world is 2.3e-6 s
  (base) and 4.4e-5 s (calcium clusters).
- Steps added: one per distinct switch time. Measured (section 13.5): 802 accepted steps against 800 nominal,
  for 2 switches. `execution.max_steps` must cover it, and the driver checks the number.
- **Seeds:** each pool's definition carries its effective seed, as legacy's does (section 11), and the driver
  refuses two pools of one world with the same seed. There is no stream key.
- Extending the run: the path is prefix-stable (the pool's events do not depend on where it is cut, M, section
  16), so a longer horizon leaves the past schedule unchanged and a saved world resumes or branches by the
  ordinary rule (a branch cannot rewrite changes before its checkpoint).

### 13.4 Ledgers, heat and work

- **Pool side:** the pool's own integer ledger closes in its own run (`material_residual_trimers`), with no
  charge and no energy.
- **Ionic side:** an availability is a control. It owns no amount, charge or energy row, exactly as a
  channel's declared schedule today. Every ionic closing is the one that stands.
- **Between them:** nothing is exchanged. The pool's free energy is not represented, so the energy of forming
  a ring is not in the ionic ledger and cannot be. If it should be, that is a new law with an explicit term,
  and it is not assumed here.

### 13.5 What I measured for it

The base cluster's ionic half as `resolved_pump_tissue@3` (two cells, near and far outside nodes, three faces,
one gated junction, the Na/K pump on maintained reservoirs, Kv1.5, constant-field leaks), driven by the live
pool's switching path in `channel_controls`, against legacy's event-split RK4 at 12.5 us (M, `composed_run4`;
the same seeds and streams; 20 ms). Worst error at 20 ms, in units of the consumer's criterion (3e-9 |e| +
3e-12). The declared field solver is the floor one (`capacitive_reduction_gauged_damped_newton@3`), see below.

Two worlds of the 16 (M): world 0 with one switch in each cell (2 extra steps), and world 1 with nine and one
(10 extra steps):

| Stepper and step | World 0: cells, outside, voltage | World 1: cells, outside, voltage |
| --- | --- | --- |
| RK4, 25 us (802 and 810 steps) | 2.4e-7, 9.0e-7, 2.6e-7 | 3.0e-7, 9.2e-7, 4.7e-7 |
| RK4, 12.5 us (1,602 and 1,610) | 2.1e-8, 5.5e-7, 0 | 3.7e-8, 2.7e-7, 0 |
| IMEX, 25 us | 0.948, 0.450, 1.34 | 0.921, 0.449, 1.31 |
| IMEX, 12.5 us | 0.238, 0.113, 0.336 | 0.231, 0.112, 0.328 |
| IMEX, 6.25 us | 0.0594, 0.0282, 0.0839 | 0.0579, 0.0282, 0.0822 |

- **RK4** agrees with legacy to under 1e-6 of the criterion at both steps in both worlds, a few units in the
  last place. Two worlds only, and one ionic set; I did not run the other fourteen, so this is not a claim for
  all of them.
- **IMEX** is second order (the ratio is 4.0 per halving in both worlds), so it meets the criterion at 12.5 us
  and not at 25 us here. RK4's own order cannot be seen in these numbers, since it agrees at rounding.
- **The composite (M, `composed_composite`).** The same ionic world as `resolved_pump_composite@1` with three
  impermeant rows and `local_species_reactions@1`, IMEX, at 25 and 12.5 us: 802 and 1,602 accepted steps
  against 800 and 1,600, and the Na, K and Cl amounts agree with @3's own IMEX run of the same schedule to
  3e-15 (relative). So the composite takes off-grid changes of an inner channel control beside a split
  operator.
- **The field solver is already ruled** (D147, D156): a definition of the resolved pump family with a free
  field offset declares `capacitive_reduction_gauged_damped_newton@3`, and one with none keeps `@2`. A
  composite follows its inner model (D156). The near and far nodes give the JUPITER, base and calcium worlds
  two free offsets; the assembly cell and the integrated ensemble's world have none and keep version 2 (M2,
  `free_offsets`). Run drivers and builders under `validation/` declare it with
  `validation/tissue/field_solver_choice.declare(raw)` (the `auto` rule); the composed worlds' builders and
  tests use it. The driver in `src/cells` does not choose a solver: it takes the ionic definition as declared.
  The sparse ID `sparse_capacitive_reduction_gauged_damped_newton@1` has no floor, so `auto` refuses it for a
  free-offset world. The first version of this note missed the rule. What I measured agrees with it: with `@2`
  the base cluster's first RK4 step is refused, at 25 us at stage 3 and at 12.5, 6.25 and 3.125 us at stage 2,
  because the Newton stops at its rounding floor (the current residual is 0.9 to 2.6e-25 A, which is 0.006 to
  0.017 of its tolerance, against a target of 0.01), and `@3` accepts the same solves at every stage (M,
  `rk4_domain`, `rk4_domain_floor`, `field_floor`). It is not an instability of RK4.
- **The floor guard rerun.** D148's record says that the floor guard of D147 compares primitive counts, not
  constants, and asks to rerun it with constants before version 3 serves a run of record
  (`docs/DECISIONS.md:4910` to 4912). No record of that rerun was found (M2, R). It is a step before the
  registered campaign (ruling 10), and not this build's.
- **Batched paths.** `ionic_worlds@1` admits the floor solver on both backends and mappings (M2,
  `floor_admission`, planners only). Two free-offset @3 worlds with different off-grid channel schedules,
  IMEX, run by `lax_map` equal their own runs bit for bit and by `vmap` to 5.1e-14 (M2, `floor_vmap`).

### 13.6 What must be refused, by name

In the driver, before any run: an unknown key; an ionic model other than @3 or the composite; a channel ID not
in the definition, or set by two pools; an observable not in the table; levels that are not in [0, 1] or not
finite; a pool without `recording: "events"`; a pool horizon different from the ionic `end_time` (or a longer
one that was not asked for); a world count that differs between pools; a near miss (13.3); a `max_steps` too
small; a replacement, partition or trafficking operator on an owner's cell (the path belongs to the channel
slot and would outlive the cell); a pool that faults, naming its world and event cap. In the ionic world,
today's refusals.

### 13.7 Restart, D148, CPU and GPU

- Restart, branch, resume, windowed and batch: ordinary (the world is an ordinary definition). Replaying the
  pool reproduces its path bit for bit (M, section 16). The definitions also carry the path, so a run does not
  need the pool code.
- **D148:** the driver adds no engine code to an ionic world. A world without it is today's, byte for byte.
- **Composition.** It writes only `channel_controls`, so it composes with anything that admits an off-grid
  change of that control: @3 alone, a composite with reactions, and a batch (all M, above). Beside operators
  whose event times must be on the grid the schedule's changes may still be off it
  (`models/pump_composite.py:2102` to 2105 covers only operators' times, R). Beside a coupling that also sets
  a channel's availability, the two multiply (its factor is applied to the held control, R, not run).
  `scheduled_cell_replacement` and the like on an owner's cell: the driver refuses (13.6).
- **GPU:** the pool runs on either backend (`engine.run`). The ionic world keeps @3's GPU path as it is today
  (the floor solver is admitted there by the planners, not run); a composite is refused on a GPU
  (`vector_windows.py:213` to 230). The driver makes no new claim. The batch form of different schedules per
  world is the existing one (`docs/INDEPENDENT_WORLDS.md`: each world keeps its own clock and schedules). Two
  base-cluster worlds with different schedules in one `independent_worlds` batch (1 ms, RK4 at 25 us, the
  first with two off-grid switches, the second with one on the grid) gave histories bit for bit equal to the
  scalar runs, 42 and 40 steps (M, `batch_worlds`).

## 14. What the composed run cannot do, with numbers

1. **Feedback.** The pool cannot read the ionic state. Nothing here needs it today; the one thing that would
   is a propensity that depends on voltage, calcium or an amount, which is a new pool law with its own event
   clock (section 15).
2. **Scale.** One extra step per switch of any pool, and one whole control record per switch. Switches per 20
   ms (M2, `pool_paths`, 4 seeds): 32 to 48 in 8 base-cluster worlds, 65 to 90 in 64 cell worlds, 4 to 16 in 2
   calcium worlds; that is about 3 per base-cluster cell (M). A tissue of N cells then has about 3 N extra
   steps against 1,600: for 500 cells about 1,500 steps (a factor of 1.9), for 10^4 about 30,000 (a factor of
   20). Each change record holds every control slot (`execution/schedule.py:150` to 210), so 30,000 records
   over 10^4 channels are about 2.4 GB (S). Fine to a few hundred cells. Beyond that the operator, or a
   step-mean schedule (item 3).
3. **A step-mean schedule without an operator** is possible for large tissues and is not built here: the
   driver writes, at grid points only, the exact mean of the level over each step. It adds no step, needs at
   most two change records per switch, and at 12.5 us meets the ensemble's criterion (0.56 units, section 12).
   It is second order, not exact.
4. **No pool state in the checkpoint.** A definition of an ionic world is a definition of the pool's *path*. A
   reader who wants the pool's state takes it from `resolution.json` and the pool's own checkpoint.

## 15. The operator, recorded as a later option

Build it when a pool must read the ionic side, when a tissue has more than about a thousand cells, or when
FR-43 part 3's unit population should drive a channel. Not before.

- **Identity:** `cell_assembly_pool@1` (renamed spelling `cells.operator.cell_assembly_pool@1`), a split
  operator of the composite, half before and half after the inner step, for one pool per declared owner (cells
  of a tissue on one axis).
- **Kernel:** `assembly_pool/kernel.step` unchanged, so the same seeds give the same event sequence. Its
  `when` is compared to the half-step's end, and an event later in the step waits for its own part.
- **State:** occupied and bonds as the kernel's own unsigned integers, cast at the boundary (every built-in
  integer field of the composite is int64, so the state stores int64 and casts); free subunits; event count;
  the time as a Neumaier pair; a fault code. A fault refuses the step. An EVENT_CAP of 64 per half-step
  refuses by name when it is met.
- **Seed:** the pool's own effective seed (uint32) and the world ID as data. Two derivations of the live
  streams already exist (`random_pair(seed, world, event count)`, `assembly/kernel.py:83`; the counter streams
  of `integer_unit_population@1`). They must not be mixed; this one uses the first.
- **Output:** `QUANTITIES` `cyclic_fraction` per owner, so `species_regulated_availability@2` needs one source
  code more for its existing `coupling_site_*` arrays (no layout change) and a factor b + (1 - b) x fraction.
  `integer_unit_population@1` would be the second owner of the same quantity role (FR-43 part 3's counts), and
  that is the general reason to build it.
- **Hold:** the factor is held over the step. The mean needs a look-ahead (second order, section 12); the
  mid-step value is first order. The order check must be a fit (section 12). The composed run needs neither.
- **What it costs:** the composite (so a GPU is refused, and the K-only worlds leave @3); one held factor; a
  judged comparison with the composed run; 4 to 5.5 agent-days. It also needs FR-43 part 3's hazard clock if
  the pool is to read a changing state: changing a propensity invalidates a pre-sampled event
  (`docs/CAPSID_ASSEMBLY.md:278` to 279), so the clock must be a hazard clock, not a list of drawn times.
- **Refusals recorded:** closers and replacement on a pool's cell; the coupling's volume conflicts;
  `cell_owned_compartments@1`'s admitted list (`operators/compartments.py:154`) does not hold it; an event
  operator's schedule times must lie on the step grid (`models/pump_composite.py:2102` to 2105), so a pool's
  off-grid events must be handled inside the operator's own half-steps, not declared as event times.
- **What it gives in return:** one definition and one checkpoint for the whole world; a step count that does
  not grow with the number of switches; a place for a pool that reads the ionic side.

## 16. Determinism and seeds

- **Cut-independence (M).** The pool's events are bit for bit the same uncut, at 50 us ticks, at 6.25 us
  half-steps with a Neumaier clock, and at 12.5 us half-steps with a random cut: 16 worlds, both cells of the
  base cluster, 2 to 15 events per pool in 20 ms.
- **The same seeds give the same sequence** because the kernel is called, not copied. The check for the
  driver: its path equals a direct walk of `kernel.step`, and its pool end state equals the captured `pool_*`
  arrays bit for bit on the four captured seeds, at every h (the pool does not depend on the ionic step, so
  the same arrays at h, h/2 and h/4).
- **One seed per pool and one world ID** as legacy (section 11). `integer_unit_population@1`'s streams are its
  own and are unrelated.
- **Platform.** The same CPU gives the same bits; a claim across CPU and GPU is not made here.

## 17. Same equations or a changed model; FR-43 part 3

- **Same equations (the composed run).** The pool's walk is the live code unchanged, and the ionic side's is
  @3 or the composite. A level changes at the switch times, where legacy's segments end; legacy also ends a
  segment at every other pool event, and the difference is far below the criterion on RK4 (section 13.3, M2).
  The pool's end state is bit for bit legacy's. The plan's section 8 template applies with its own rounding
  fallback. The RK4 candidate (K-only) agrees with legacy at rounding at 25 and 12.5 us (section 13.5), so its
  observed order is noise, and the template's fallback, the consumer's registered criterion, is what judges
  it. The IMEX candidate shows order 2 at its own h, h/2 and h/4 (M, section 13.5). The pool arrays are
  compared bitwise at every h. Trajectories cannot be compared (14.4 of the map: the assembly jobs hold no
  trajectory), so endpoints, JSON summaries and pool arrays are the judged arrays.
- **What the composed run does not reproduce** and a criterion should not ask for: bitwise identity with
  legacy's ionic state (its field solver differs), `segments` (a count of its own splits), and the exposure's
  summation (legacy accumulates it in segments; the path gives it exactly. The step-mean rule's exposure
  agreed with it to 3e-16 s, M).
- **Changed model:** a held factor (the operator) is one; it needs the consumer's own criterion and a fitted
  order, not the three-step band.
- **FR-43 part 3's integer-unit population** composes beside a composed run, as data beside an operator:
  independent owners, independent streams, no shared state. Its compensated clock takes off-grid steps
  (`integer_unit_population.py:811`). Its counts are not an availability today: it has no `QUANTITIES`, and
  giving it one is the operator's work (section 15). One thing to note: an off-grid split breaks the count
  times dt conversion of `species_regulated_availability`'s crossing record (R), so a composite with both
  should declare its level through `channel_controls`.

## 18. Tests for G-7 (rows, with plants)

Rows go into `tests/unit/test_assembly_pool.py` (27.9 s, 90 s cap), which already compiles the pool's program
once; the ionic rows are host only, so no new compile (D224).

1. The driver's path equals a direct walk of `kernel.step`, bit for bit, for 4 worlds and both cells
   (*plants:* a pool given the other pool's seed must fail; `<` in place of `>=` must fail; the level read
   before the event instead of after must fail).
2. The schedule's value at a set of times (before, at, after each switch, at base changes) equals base(t) x
   level(t), and a channel named by two pools is refused (*plants:* the product ignoring the base schedule;
   rounding a switch to the grid).
3. Near miss: a planted switch at 1e-9 of a step off a grid point refuses by name; with the option it is
   declared at the point and the shift is recorded.
4. The final pool state and the exposure: equal the pool's own checkpoint, bit for bit.
5. The definitions written are byte-identical for the same input, and parse; `inputs.json` holds the composed
   file's SHA-256, the seeds and the switch list, and changes when any of them changes (*plants:* a schedule
   object shared between controls must not occur; the seed left out of the inputs).
6. The written world parses, its `EventGrid` has nominal + distinct switches steps, and its `channel_controls`
   equal the schedule written by hand; host only. No world is compiled: an off-grid change of a channel
   control is existing behaviour (section 13.5). The two-cell closed row is stream D's (ruling 14).

Consumer rows (captures, judged) belong to the re-expression.

# Part III. Both parts

## 19. Words and IDs

No new family word, as recommended (question 3 of section 0.1 could add one). Every word below is decided
(D371, D383). Today's spelling is used in the code; the renamed spelling is beside it, for the ID move.

| Piece | Today's spelling | Renamed spelling | Family word |
| --- | --- | --- | --- |
| The source kind | `cells.species_condition@1` (key `species_conditions`) | `cells.kind.species_condition@1` | `kind` |
| Its law | `cells.hill_product_factor@1` | `cells.transfer_factor.hill_product_factor@1` | `transfer_factor` (decided for `ph_conditioned_factor@1`) |
| The operator (section 15, only if built) | `cell_assembly_pool@1` | `cells.operator.cell_assembly_pool@1` | `operator` |

- The two live IDs above (the operator's only when it is built) need rows in
  `scripts/moves/id-rename-choices.json`, which is not my file: the lead tells its owner.
- The driver introduces no versioned ID as recommended (question A5, question 3 of section 0.1). Its JSON keys
  (`observable`, `levels`, `channels`) are words of an input file. `root_component_has_cycle` was legacy's law
  ID `root_component_has_cycle@1` and is reused as a plain observable's name; whether it should carry a
  version is the user's.
- Hooks: `factor_rows` and `factor_log_slopes` (section 5.5) are kind-registry hooks, not IDs, and no new
  interface word.

## 20. Price and order

| Item | Agent-days | What is in it |
| --- | --- | --- |
| G-7 driver (F4) | 1 to 1.5 | `schedule.py` and the two subcommands (the run inputs in them) 0.4; rows 0.4; the composed example and a check on the two K-only worlds 0.3; library page, run view, review 0.3 |
| G-5 source kind | 1 to 1.75 | law and kind 0.4; rows 0.35; matrix tag, library page, run view 0.25; composite demonstration 0.25; review and landing 0.3 |
| The two hooks of section 5.5 | 0.15, inside G-5's range | the bound itself is stream D's (0.75, its note; the second reader reads 1 to 1.5) |
| Law record and page, if A5 is (b) | + 0.25 | |
| `ph_condition`'s retirement (section 5.10) | 0.75, later | FR-5's worlds re-expressed and judged again |
| G-7 operator, later | 4 to 5.5 | the rows, matrix, statistics rows, the quantity source of `@2` and a judged comparison |
| Plan's own figures | 2 to 3 and 4 to 6 | `docs/LEGACY_PORT_PLAN.md`; the composed run replaces the second |

- **Not in it:** the two legacy command lines (`assembly-cell`, `assembly-cluster`), which leave with legacy
  (the map, 14.2); the judged re-expression; the retirement of `ph_condition`. **The two ensemble kinds
  (`assembly_cell_ensemble@1`, `assembly_cluster_ensemble@1`) lack a home** (ruling 15): the driver creates no
  family row, so no `EnsembleAdapter`, for them, and D384 refuses them by name. A batch of composed worlds is
  an `independent_worlds` batch (section 13.7), not an ensemble kind. Should they come back, the map's 14.2
  gives the row.
- **The second reader's order,** which the lead accepts: its rows 1, 8 and 9 settled first; G-7's driver,
  independent; stream D's steps 1, 3 and 4; this note's source with the final hooks; D's steps 2 and 6 as one
  edit of `material_rate`; D's steps 5 and 7.
- **Order.** (1) G-7's driver: it depends on nothing but live code, and the two K-only worlds are re-expressed
  with it. (2) G-5's source: it depends on no stream, and is tested with the prototype's world (one store
  node, today's kinds). (3) Stream D's store and its route. (4) The calcium worlds and the assembly-regulated
  calcium clusters use both. The driver can serve those four clusters as soon as (3) exists; nothing in it is
  calcium-specific.
- The estimates are mine (S), from the live files of the same shape (`ph_condition.py`, a door-source kind,
  and the pool's `engine.py` are about 250 lines each). They have not been tried.
- **A risk I see:** the IMEX composite's cost is the consumer's, not the driver's. At 20 ms and 12.5 us a
  composite run of two cells took minutes on these crowded CPUs (M, no timing claim).

### 20.1 Edits to the live engine

Lines at 43b22d40; on `legacy-cleanup` at 149f9df9 the same except where a second number is given. The bound
of section 5.5 is stream D's; its edits are named so that the two notes meet.

| Build | File and line | Edit |
| --- | --- | --- |
| G-5 | new `kinds/species_condition.py` | the kind (about 260 lines) |
| G-5 | new `laws/reactions/hill_product_factor.py` | the law: ln f, f and the slopes (about 70 lines) |
| G-5 | `kinds/__init__.py:1` to 29 | one docstring line, one import |
| G-5 | `registry/kind_registry.py:251` to 258, 457 to 460, and `declaration_errors` (about 959) | two optional fields; a kind with one of the two is refused; docstring |
| G-5 | `kinds/ph_condition.py:1` to 31, `kinds/patch_damage.py:1` to 51 | docstrings: the limit of section 5.5; for `ph_condition`, its successor |
| G-5 | `docs/library/` and its generator's output, `validation/tissue/composition_matrix.py`, `scripts/moves/id-rename-choices.json` (the last two not mine) | pages, matrix tags, the two ID rows |
| G-5 | `registry/model_table.py` | none: the kind registers through the `cells.kinds` package, a home already, and the law has no Law record (as `ph_conditioned_factor@1`) |
| G-5's hooks, in D's step 6 | `models/inner_laws.py:284` (283) | `loops: tuple = ()` |
| | `models/surface_pump_v3.py:189`, 331, 1215 (1214), 3701 (3700), 5041 (5040), 5442 (5441) (`kind_types`) | the loop layout fields (FR-51's pattern), their fill, the pairing, the rule, the structure field, the layout type |
| | `kinds/passive_routes.py:529` | `routed_rows`, `routed_flux` (and @3's own in `surface_pump_v3`) |
| `loop_term` removal (section 5.10), with D's steps 2 and 5 | `registry/laws.py:377`, 446, 482; `laws/pumps/proton_pump.py:137`, 265; `docs/INNER_MODEL_V4_DESIGN.md:558`, 841; `docs/library/DECLARATIONS_FORMAT.md:210`, 224; `tests/unit/test_inner_laws.py:152`, `tests/unit/test_law_registry.py:222` | the two reserved fields, the check, the two declaring lines, and what documents and tests them |
| G-7 | new `assembly_pool/schedule.py` | the driver (about 150 lines) |
| G-7 | `assembly_pool/cli.py:132` | the `resolve` and `run` subcommands |
| G-7, only if A5 is (b) | a law module, a library page, one row of the choices file | the observable's law |

My own builds edit nothing in `models/pump_composite.py`, `models/pump_composite_adapter.py`, `operators/`,
`execution/`, `numerics/` or `definitions/`. D's step 6 may need the composite's adapter to carry the loop
layout fields, as FR-51's are (D's to check).

### 20.2 If a ruling cannot be executed

No ruling that concerns this note is impossible as worded. Two depend on stream D's builder:
- **Ruling 9, layout indices:** if the core layout fields cannot be added in D's step, each side keeps its
  own: the source kind its pair rows and nodes in its own layout (two more fields) and a hook
  `factor_amounts(read, p) -> [P]`, the sink its ends in its own layout (it has them) and a hook for them.
  Nothing enters the structure but positions. 0.1 day more here, 0.25 less in the core.
- **Ruling 3, per moved row:** if a sink cannot enumerate its rows' fluxes, it gives one J per slot and the
  core adds it to every row of the slot (conservative). A multi-ion slot without `routed_rows` is refused by
  name rather than bounded wrongly.

The judged-record questions (FR-5's and the coupling's) are the lead's dates, not impossibilities (section
5.10).

## 21. Corrections to the plan, the map and the docstrings

Lines are at 43b22d40. Items 3, 4, 8 and 9 are corrected on `legacy-cleanup` (b677738c, merged as D386).

1. **The plan's section 4** cites `species_regulated_availability.py:154`, 548 to 551 and 743 to 745. They
   hold at ce4780d2 and are stale. Now 159, 553 to 557 and 748 to 754.
2. **"Reads species amounts, not topology"** (plan, the same section) is out of date at `@2`, which also reads
   operators' quantities (a site's fraction, a population's rate).
3. **`species_regulated_availability`'s text** "@3's step moves it" is false for an impermeant charged row
   (section 3). The refusal is right; the reason is not.
4. **`surface_tissue.py:376` to 381**: "every world in use has 0, +-1 or +-2" is false once a -3 row is in a
   world (section 3).
5. **The map** (`docs/LEGACY_PORT_PLAN.md` at a1db6ab9): line 1379 says the JUPITER world runs at "RK4 at <=
   25 us", 1487 says an off-grid schedule "qualifies on RK4 for the cell and the base", and 1521 says RK4 on
   @3 needs dt <= 25 us with Kv1.5. None names the field solver, which D147 and D156 rule (section 13.5). With
   version 2 the base cluster's first RK4 step is refused at every dt tried (25 to 3.125 us, M). The first
   version of this note asked instead of citing the rule.
6. **The plan's section 8 three-step order template** (`docs/LEGACY_PORT_PLAN.md` at a1db6ab9, lines 962 to
   979) fits the composed run where the differences are above rounding, and not a held operator factor
   (sections 12 and 17).
7. **D211 and the plan's row I6** would fold `ip3_er_release@1` into the cardiac release. It is another
   mechanism: that release relaxes to a target proportional to the L-type current and has flux states
   (`docs/HUMAN_CARDIAC_LAWS_DESIGN.md` section 3.5). Do not fold.
8. **A latent parser hazard, fixed on `legacy-cleanup` (D386)** with one row
   (`tests/unit/test_surface_pump.py`). `definitions/surface_pump_spec.py:207` to 215 multiplies each junction
   control's `availability` by the junction's initial gate *in place*, on a deep copy that keeps internal
   aliases. A definition built in Python that shares one schedule object between a junction and other controls
   is parsed with the other controls scaled too (M: membranes and pumps became 0.6 of what was declared; a
   JSON file cannot do this). The kinetic parser had the same scaling
   (`definitions/surface_kinetic_spec.py:286`). It silently gave a 10 mV error in one of my probes before I
   found it.
9. **`registry/kind_registry.py`'s docstring** says built-in kinds are in `models/inner_kinds/`; they are in
   `kinds/`.
10. **`legacy/processes/ip3_release.py:1`** names BETSE, but its arithmetic is the live Hill activation bit
    for bit (section 4.2).

## 22. Evidence, and what was run

Worktree at 43b22d40, with no source edits. `PYTHONPATH` the worktree's `src` and root, JAX on the CPU in x64,
compilation cache disabled, CPUs 6, 7, 22, 23 under `nice`; detached units for anything over a minute. Scripts
and records: `/mnt/workspaces/Cells/release-and-assembly-design-20261125/` (`probe/`, `out/`, `README.txt`).
The machine was busy, so no time below is a performance claim.

| Record | What it shows |
| --- | --- |
| `hill_same`, `zero_ligand` | The live Hill law is legacy's, bit for bit; exact 0 and 1 at zero ligand; NaN below zero |
| `ip3_charge`, `ip3_charge_check` | IP3 at -3, 0 and -5 are the same run bit for bit (legacy, 1,601 rows, 25 fields) |
| `capacitor_sum` | Host against compiled charge sum with a -3 row |
| `pool_cuts` | The pool's events do not depend on the cuts |
| `hold_order` | Holding rules against an event-split run, 16 worlds, six steps |
| `parse_ip3`, `parse_assembly`, `two_routes`, `moved` | What is refused and admitted today, with the messages |
| `source_kind` | The prototype source kind, live engine |
| `composed_run4`, `composed_composite` | The composed run, RK4 and IMEX, as @3 and inside a composite |
| `rk4_domain`, `rk4_domain_floor`, `field_floor` | Why the default field solver refuses the first RK4 step |
| `batch_worlds`, `at3_kind`, `lifecycle` | Two composed worlds in one batch; the prototype kind in a plain @3 world; what a closer meets in a kind without partition roles |
| `compose_probe`, `labels_probe`, `water_volume` | The kind beside water, wash and labels (parse); the factor under moving water volumes (a run) |
| `ph_same` | `ph_condition`'s law against the Hill law |

**The second reader's records** (`/mnt/workspaces/Cells/second-read-calcium-notes-20261125/probe/`), cited as
(M2): `pool_paths`, `split_equivalence`, `feedback_zero`, `free_offsets`, `floor_admission`, `floor_vmap`.

Two of my probes were wrong first. `composed_run3` shared one schedule object (item 8 above) and gave a 10 mV
error; it is kept as `composed_run3_ALIASED_invalid.log` and is not cited. The first `composed_run` used the
default field solver and was stopped once its first step was refused.

## 23. What is not claimed

- No agreement with any experiment, and no measured constant. The numbers are the captured definitions'.
- No claim about the receptor, IP3's charge in water, IP3 metabolism, assembly energetics, or the real cage.
- No claim that a composite's calcium run meets any band: only a prototype ran (section 4.1).
- No GPU claim. No claim above a few hundred cells for the composed run. No timing.
- The hooks and the run-inputs option are specified, not built. The second reader's M2 results are its own.
- Nothing here is judged. Both parts come back to the user with their price before any build (D383).
