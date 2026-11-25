# Ligand-gated store release (G-5) and assembly topology as a channel's availability (G-7): design

**Status: proposed, 25 November 2026. Design only: no engine code.** Branch `release-and-assembly-design` from
43b22d40. Main was at 34c56234 when this was written, and no ID had changed. Two parts that can be built
apart. Part I (G-5) is sections 1 to 9. Part II (G-7) is sections 10 to 18. The re-expression map this note
answers is section 14 of `docs/LEGACY_PORT_PLAN.md` at a1db6ab9 ("the map").

**Marks.** (M) I ran it. (R) I read it in code or a document at 43b22d40. (S) my own derivation or arithmetic.
(G) a guess. File references are to `src/cells/` at 43b22d40 unless another place is named. All measured runs
used CPUs 6, 7, 22 and 23, under `nice`, on the CPU build of JAX, with a fresh compile each time. Section 22
lists them.

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
  unchanged. This is the general choice now, because the pool never reads the ionic side. The operator is
  recorded in section 15, with the three cases that would make it worth building.
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

Nothing in this note needs a new family word (section 19). Two new IDs need rows in
`scripts/moves/id-rename-choices.json`, which is not my file.

### 0.2 Questions for the lead

1. **The field solver.** The base cluster written as @3 is refused at its first RK4 step with the default
   field solver (`capacitive_reduction_gauged_damped_newton@2`) at 25, 12.5, 6.25 and 3.125 us (M, section
   13.5). With the declared floor solver (`@3`) every step passes. The map's 14.2 says "RK4 at <= 25 us" and
   does not name a field solver. Does the re-expression stream declare the floor solver for all its @3 worlds?
2. **Stream D's note** must take four things (section 7.1). I ask that you pass them on. I need D's answer on
   the loop term before G-5's builder starts (section 5.5).
3. **The parser** scales a junction control in place (section 21, item 8). It is not mine to fix.
4. **Names:** `species_condition@1` and `hill_product_factor@1` (section 19). Tell the rename's owner.

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
and an impermeant ligand row at -3 with its binding by `local_species_reactions@1` (all M, sections 3 and 14).

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

- **What it is.** `core/ip3_calcium_spec.py:42` (legacy) declares it. `validation/chemistry/ip3_protocol.json`
  calls it a "nominal synthetic engineering choice", not a measurement. No physiological charge is claimed
  here. The paper that measures IP3's protonation (Schmitt and others 1993, J. Chem. Soc. Perkin Trans. 2)
  could not be read: the site refused the request (HTTP 403), and it was not tried again.
- **What it does to the ensemble.** Nothing (M). The full 20 ms run of `configs/ip3_calcium_cluster.json`
  (1,601 rows) at -3, at 0 and at -5 gives all 25 saved state fields bit for bit the same. Only the reported
  background charges differ. IP3 is impermeant everywhere and each node's fixed charge is declared to balance
  the row.
- **What it does in the live engine:**
  1. *The capacitor sum.* `models/surface_tissue.py:376` to 381 says the sums are exact for valence magnitudes
     0, 1, 2, 4 and 8, and that "every world in use has 0, 1 or 2". With a -3 row the host's and the compiled
     sum differ in 24,711 of 200,000 random columns (12%, up to 1.7e4 units in the last place in cancelling
     sums); at 0 or -4 they agree in all (M). It matters only where a held node's or an electrode's ledger is
     asked to close to the last bit, and these worlds have neither (the map, 14.1 finding 4). The note's
     sentence becomes false the day a -3 row lands.
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
  right to fail closed, but its sentence is wrong for this case.

## 4. Options for G-5, and what each loses

| Option | What it is | What it loses |
| --- | --- | --- |
| **A. A new target of `species_regulated_availability`** | Route the store's release as a coupling target | Held through the whole step (the read must be instantaneous and neutral, or be a state), so first order by the operator's own words; an instantaneous read of a charged row, and of any row the inner step moves, is refused; only a product of separable factors, one per coupling; `@2`'s operator targets are five named ones and the store is none; a route's factor on an operator-owned control is refused (`models/pump_composite.py:893`); an @3 channel on a bounding patch is refused anyway |
| **B. A release law inside the store** | Stream D's route carries its own gating parameters | Stage-exact and joint, but it is D's file and D's IDs. It reaches only a store. Other users of the same gating (G-3-like gating of an @3 channel, a luminal sensor) would need their own copy. The law itself is a pure function, so B can call this kind's function if D prefers |
| **C. A separate kind, a source of the door (recommended)** | The pattern of `kinds/ph_condition.py`, the mechanism `docs/INVENTORY_COUPLING_DESIGN.md` section 0.4 names for a stage factor, so no second mechanism | IMEX only (the door is refused under RK4); an opening in [0, 1] only (no flux-form graded release); no loop term today (section 5.5) |
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
- The ensemble's release needs two conditions per cell: `release_calcium` (the two calcium reads) and
  `release_ip3` (one activation read of IP3), named in that order by the release route: `"factors":
  ["release_calcium_0", "release_ip3_0"]`. The door multiplies them in declared order on the route's held
  value.
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
- The product is in one exp of one sum (as legacy's calcium opening, bit for bit). A condition per ligand and
  the door's left fold give legacy's product `held x f_IP3 x f_Ca` to the order of multiplication, which
  commutes for two factors.

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

### 5.5 The loop term

The route moves a row the condition reads, so a gating loop closes. `docs/INNER_MODEL_V4_DESIGN.md` section
7.4 (g) asks that "a law whose flux moves a row its read depends on declares a loop term". The passive route
has none for a factor today (R: the pH condition's route has none either). What it takes (S):

    |dJ/dn| <= |J_open| / n  x  sum over the reads of that row of n_j / 4        per second, n the read row's amount

because f (1 - h) <= 1/4 for each Hill factor and |d ln f / d ln n| <= sum n_j (1 - h_j). In the ensemble
J_open is about 0.02 fmol/s (P A c_store = 1e-7 x 1e-9 x 0.2 mol/m3), the cytosolic Ca is 0.001 fmol and the
two reads have n = 2, so the bound is 20 per second: dt x L is 2.5e-4 at 12.5 us. It is far from binding. A
general feature should still hold it, so the sink's route should add it (section 7.1). If the core prefers,
the source can expose the static read rows (`factor_reads(declaration)`) and the sink bounds the stage with
them.

### 5.6 Refusals by name

Each refusal names the kind, the condition and the thing: an unknown node; an unknown species; a law other
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
  compartment admits it, and a world without one needs nothing. The matrix:

| Beside | Result | Basis |
| --- | --- | --- |
| A compartment (`cell_owned_compartments@1`), a charged route, `local_species_reactions@1` | admitted | M, section 4.1 |
| `cells.passive_routes@1` as sink, @3 channels as sink | admitted | R, M |
| A closure (`rapid_binding@1`, `rapid_proton_buffer@1`) on a read row | reads the free form | R |
| Water, partition, replacement, trafficking, labels, records, membrane state, electrodes, exchange | unaffected: it only reads | S |
| RK4 | refused | M |
| A @3 world with no kinds | not declared, nothing changes | S |

### 5.8 Provenance

The form is Hill's, in its Weiss 1997 presentation (doi:10.1096/fasebj.11.11.9285481, cited from a secondary
index, not read) and in Bezprozvanny, Watras and Ehrlich 1991 for calcium's bell-shaped dependence
(doi:10.1038/351751a0, found, not read). Mak, McBride and Foskett 1998 (doi:10.1073/pnas.95.26.15821, read
through a page tool; its equations were images) reports that IP3 tunes the calcium *inhibition's*
half-saturation: one laboratory, Xenopus oocyte nuclei, so an indication only. A joint law is later work and
would be its own version: `hill_product_factor@1` is separable by its form and does not represent that. The
numbers are legacy's, not measurements (section 2).

## 6. Same equations or a changed model

- **Same equations:** both factors, their parameters, the read of free concentrations, the GHK flux at z = 2,
  the place (at the stage) and the order (release multiplied by the product). The candidate's order is 2, by
  IMEX. So the band of the map's section 8 template can apply, at each consumer's own steps.
- **Changed model, so a criterion of the consumer's own:** a factor held through the step, a factor read
  through a two-state, or a held bath where the world is closed.
- **Two consumers, two statements:** the four `spatial_calcium` worlds need only the calcium condition (`@1`
  to `@3`) or both (`@4`). The four assembly-regulated calcium clusters need G-5's and G-7's parts at once,
  and G-7's schedule multiplies Kv1.5 only (the map, 14.3). Cardiac graded release (the map's D211 and I6
  notes) is another mechanism: it is driven by the L-type current and it is a flux state. Folding
  `ip3_er_release@1` into it would be wrong (section 21, item 7).

## 7. What G-5 needs from others

### 7.1 From stream D (through the lead)

1. **The release is a route of `cells.passive_routes@1`** (`passive_constant_field_permeation@1`, charged, on
   the store's bounding patch, IMEX), with its `factors` key set. The door and the sink exist; a second route
   on the same patch is the leak (M, admitted).
2. **Sign and reading.** The patch's cell is the owner and its outside node is the store, so a positive flux
   is release into the cytosol. Confirm it, since the condition's node is the owner's cell.
3. **The loop term** of section 5.5, in the sink's stage rule, or say that it is left out and why.
4. **A heat booking that stays non-negative** when a factor falls inside a step.
   `docs/HUMAN_CARDIAC_LAWS_DESIGN.md` section 3.8 reads that ARS(2,2,2) can book negative heat when a power
   falls more than 59% in one step. It was read, not run. The ensemble's factor moves far less than that in
   12.5 us.
5. **No closure may own the Ca row** at that node: a charged route refuses a row whose free and total split a
   closure holds (`kinds/passive_routes.py`, the charged law's rule). Buffers are then split reactions, as in
   legacy.
6. **The release as its own route,** apart from the leak, so that a factor does not touch the leak. A release
   schedule is not needed by any captured world; if D wants one, a route's held value may follow a schedule
   (door, section 7.4 (l)).

### 7.2 From the core and the rename

Nothing in `models/surface_pump_v3.py`. If the loop term goes through a source hook, one optional hook of the
kind registry is added (`factor_reads`, static), used by the sink. Otherwise no core change.

## 8. Tests for G-5 (rows, with plants)

All rows go into files that exist (D224). Recorded seconds: `tests/unit/test_fr5_source_kinds.py` 5.64,
`test_fr5_source_kinds_engine.py` 67.28, `test_hill_factors.py` 2.82, `test_passive_routes_kind.py` 75.57
(`tests/test_tiers.json`; 90 s is the cap).

1. `test_hill_factors.py`: the law's product of J factors equals the exp of the sum of the live `log_factor`s
   bit for bit at random points; exact 0 and 1 at zero; NaN below zero. *Plant:* inhibition read as activation
   must fail. No compile beyond one small function.
2. `test_fr5_source_kinds.py`: the declaration's refusals (section 5.6), one row each, and the stateless
   layout. Host only.
3. `test_fr5_source_kinds_engine.py`, one world: the prototype's world (one cell, one store, a gated Ca
   route). Rows: at 100, 50 and 25 us the released amount halves with a ratio of 4 to 2% (*plant:* the factor
   held at the step's start must fail the ratio); with the ligand at 0 the run is bit for bit the run at -3
   (*plant:* reading the bound row must fail); with the condition on the wrong node the result differs
   (*plant*); with K in M instead of mM it differs (*plant*).
4. D148: a definition without the key keeps its structure entry and its program (an equality check on the
   structure, no run).
5. A condition as a source of an @3 channel slot: one row, host only, the routed control equals held x f.
6. A compartment world admits the kind; a source that also declares `bound_rate` is refused there (one parse
   row each).

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
| A coupling whose source is an assembly's quantity | Refused by name: "a coupling's law is one of hill_activation, hill_inhibition, state_fraction, state_complement"; a site's fraction needs the operator that holds it (M) | `operators/species_regulated_availability.py` |
| An operator's events at times off its clock's grid | Refused: an operator's times lie on the step grid | `models/pump_composite.py:2102` to 2105 |
| A conditional availability schedule | None: `channel_controls` is declared data | `definitions/surface_pump_v3_spec.py` |
| The pool inside the ionic step | None. Only legacy's `assembly_regulated_cell@1` and `assembly_regulated_cluster@1` couple them, on legacy models | `legacy/assembly_cell`, `legacy/assembly_cluster` |

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
  k_off 300 and 10 per s. Those are the ensemble's numbers, not measurements. The numbers of Asor and others
  (Nature 2026, doi:10.1038/s41586-026-10948-z) were not read here.
- **Streams.** threefry2x32 of (seed, world, event count); seed = base + stream id, one stream per cell
  (`assembly/kernel.py:83` to 94). For the cluster the two streams are 20260925 and 20260926. Each event is
  drawn from its own counter, so the walk does not depend on how a run is cut.

## 12. The options, with numbers

**How long is a step's hold?** (M, `hold_order`). World: the base cluster, 16 worlds, 20 ms, 2 cells.
Reference: legacy's own event-split RK4 at 12.5 us. Candidates: the same ionic RK4 on a fixed grid, with each
cell's availability held over the step by its value at the step's start, at its middle, or its exact mean over
the step. Worst error at 20 ms over every ionic field, in units of the consumer's criterion (3e-9 |e| + 3e-12,
`validation/assembly/cluster_protocol.json`):

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
- **Event times are the pool's own** and are few: 2 to 14 switches per world in 20 ms (both cells together, 94
  in 16 worlds), against 1,600 steps of 12.5 us.

| Option | What it is | Verdict |
| --- | --- | --- |
| **F1. The composed run by hand** | Run the pool, read its path, write the schedule into the definition yourself | Works today (M) but is hand work: wrong factors or seeds are silent |
| **F2. A "driven world" family** | One command that resolves the paths and runs the ionic world, a definition kind of its own | 2 to 3 days. A new family word, so it goes to the user. Not needed to start |
| **F3. An event-cut composite step** | The composite splits its step at the pool's events | Rejected: the composite's halves (Strang) would be cut mid-step, and the pool never needs it |
| **F4. A small driver (recommended)** | A live module that turns a pool run into `channel_controls`, plus a subcommand | 1 to 1.5 days |
| **F5. An operator hosting the pool** | `cell_assembly_pool@1`, later (section 15) | 4 to 5.5 days, plus a judged comparison |
| **F6. A kind on @3; extending `integer_unit_population@1`; assembly lineages** | Three other homes for the pool | Rejected: a kind cannot own a clock; a unit population counts units and has no graph (no topology); lineages hold no topology |

## 13. The recommended form: the composed run (F4)

### 13.1 Why it is the general choice now

- **The pool never reads the ionic side.** A one-way drive has no loop to hold inside a step, so nothing in it
  needs an operator. It needs the event times to be exact, and the clock already takes them as data.
- **It is exact, and simpler than the operator.** The level is piecewise constant, so its exact value on every
  piece is data. The step's boundaries fall on the switches, so the stepper keeps its own order: 4 on RK4, 2
  on IMEX (S, and section 13.5). No held factor, no new error.
- **No second clock and no copied state.** The pool has one clock, its own, in its own run. The ionic world
  has one clock, `EventGrid`. The only thing that crosses is a list of (time, level) pairs, which is data in a
  definition. Nothing in the ionic world can write the pool back.
- **It stays on the K-only model.** An assembly cell and the base cluster are @3 worlds. An operator would
  force the composite.
- **Reuse.** The driver does not know Kv1.5 or calcium: it knows pools, owners (channel IDs), two levels, and
  an observable's name. Anything that writes a path can drive any schedule.

### 13.2 The definition and the driver

`cells assembly-pool resolve COMPOSED.json --output DIR`. The input is a strict JSON object with exactly the
keys `schema_version`, `ionic` and `pools`. It has no new ID or kind word. `ionic` is an ordinary definition
(`resolved_pump_tissue@3` or `resolved_pump_composite@1`). Each entry of `pools` is:

    {"channels": ["channel_0"],            the channel populations it sets, each set by one pool at most
     "stream": 0,                          added to the pool's seed
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
- **`resolution.json`** holds, for each pool and world: the pool's definition fingerprint, seed and stream,
  the number of events, each switch as (time, level, event count), the exposure (the fsum of level x
  duration), the final pool state and the ionic fingerprint. It is provenance and the one place the path is
  written down.
- The definitions are written as JSON text, with no shared objects (section 21, item 8).

### 13.3 Times

- Event times are the pool's own float64 times, never rounded to steps. The clock splits the step that holds
  one (`execution/grid.py:3` to 6). A time within rounding of a grid point snaps onto it and is recorded
  (`applied_definition`).
- The clock refuses a near miss: an event more than rounding and at most 1e-6 of a step from a grid point
  (`grid.py:55`, `_near_point`). The driver finds it before any run and names the world, pool and event. It
  refuses by default. An explicit option declares it at the grid point and records the shift. The chance is
  about 2e-6 per event (S): 2e-4 for the 94 events of 16 worlds.
- Steps added: one per distinct switch time. Measured (section 13.5): 802 accepted steps against 800 nominal,
  for 2 switches. `execution.max_steps` must cover it, and the driver checks the number.
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

World 0 of the 16 (one switch in each cell, at 0.2354 and 0.7157 ms, so 2 extra steps):

| Stepper and step | cells | outside | voltage |
| --- | --- | --- | --- |
| RK4, 25 us (802 steps) | 2.4e-7 | 9.0e-7 | 2.6e-7 |
| RK4, 12.5 us (1,602) | 2.1e-8 | 5.5e-7 | 0 |
| IMEX, 25 us | 0.948 | 0.450 | 1.34 |
| IMEX, 12.5 us | 0.238 | 0.113 | 0.336 |
| IMEX, 6.25 us | 0.0594 | 0.0282 | 0.0839 |

- **RK4** agrees with legacy at rounding at both steps: the composed run is exact where legacy is, with no
  held factor. The amounts and voltages differ from legacy's by less than 1e-6 of the criterion, a few units
  in the last place.
- **IMEX** is second order (the ratio is 4.0 per halving), so it meets the criterion at 12.5 us and not at 25
  us for this world. The calcium worlds' IMEX has the same order.
- **The composite (M, `composed_composite`).** The same ionic world as `resolved_pump_composite@1` with three
  impermeant rows and `local_species_reactions@1`, IMEX, at 25 and 12.5 us: 802 and 1,602 accepted steps
  against 800 and 1,600, and the Na, K and Cl amounts agree with @3's own IMEX run of the same schedule to
  3e-15 (relative). So the composite takes off-grid changes of an inner channel control beside a split
  operator.
- **The field solver (M, `rk4_domain`, `rk4_domain_floor`, `field_floor`).** With the default solver (`@2`)
  the first RK4 step of this world is refused: at 25 us at stage 3, at 12.5, 6.25 and 3.125 us at stage 2. The
  Newton stops at its rounding floor: the current residual is 0.9 to 2.6e-25 A, which is 0.006 to 0.017 of its
  tolerance, against a target of 0.01. The floor solver accepts the same solve (its extra rule). Every step at
  every stage passes with it. The default solver's refusal is not an instability of RK4.

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
- **GPU:** the pool runs on either backend (`engine.run`). The ionic world keeps @3's GPU path as it is today;
  a composite is refused on a GPU (`vector_windows.py:213` to 230). The driver makes no new claim. The batch
  form of different schedules per world is the existing one (`docs/INDEPENDENT_WORLDS.md`: each world keeps
  its own clock and schedules).

## 14. What the composed run cannot do, with numbers

1. **Feedback.** The pool cannot read the ionic state. Nothing here needs it today; the one thing that would
   is a propensity that depends on voltage, calcium or an amount, which is a new pool law with its own event
   clock (section 15).
2. **Scale.** One extra step per switch of any pool, and one whole control record per switch. At the base
   cluster's rates (about 3 switches per cell in 20 ms, M) a tissue of N cells has about 3 N extra steps
   against 1,600: for 500 cells about 1,500 steps (a factor of 1.9), for 10^4 about 30,000 (a factor of 20).
   Each change record holds every control slot (`execution/schedule.py:150` to 210), so 30,000 records over
   10^4 channels are about 2.4 GB (S). Fine to a few hundred cells. Beyond that the operator, or a step-mean
   schedule (item 3).
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
- **Seed:** seed_p = (seed + stream) mod 2^32, the world ID as data. Two derivations of the live streams
  already exist (`random_pair(seed, world, event count)`, `assembly/kernel.py:83`; the counter streams of
  `integer_unit_population@1`). They must not be mixed; this one uses the first.
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
- **Two streams per world** as legacy: (seed + stream id) and world ID. `integer_unit_population@1`'s streams
  are its own and are unrelated.
- **Platform.** The same CPU gives the same bits; a claim across CPU and GPU is not made here.

## 17. Same equations or a changed model; FR-43 part 3

- **Same equations (the composed run).** The pool's walk is the live code unchanged, and the ionic side's is
  @3 or the composite. A level is applied at the same event times and in the same way as legacy's segments.
  The template of the map's section 8 fits: the candidate's order is 4 on RK4 (K-only) or 2 on IMEX, at its
  own h, h/2 and h/4; the pool arrays are compared bitwise at every h. Trajectories cannot be compared (14.4
  of the map: the assembly jobs hold no trajectory), so endpoints, JSON summaries and pool arrays are the
  judged arrays.
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
once; the ionic rows are host-only except one.

1. The driver's path equals a direct walk of `kernel.step`, bit for bit, for 4 worlds and both cells
   (*plants:* base seed without the stream must fail; `<` in place of `>=` must fail; the level read after the
   event instead of before must fail).
2. The schedule's value at a set of times (before, at, after each switch, at base changes) equals base(t) x
   level(t), and a channel named by two pools is refused (*plants:* the product ignoring the base schedule;
   rounding a switch to the grid).
3. Near miss: a planted event at 1e-9 of a step off a grid point refuses by name; with the option it is
   declared at the point and the shift is recorded.
4. The final pool state and the exposure: equal the pool's own checkpoint, bit for bit.
5. The definitions written are byte-identical for the same input, and parse (*plant:* a shared schedule object
   must be rejected or never occur).
6. One composed world, small (end time 2 ms, one cell): the run ends with nominal + distinct switches steps,
   and its amounts equal the same world run with the schedule written by hand. Under 20 s.

Consumer rows (captures, judged) belong to the re-expression.

# Part III. Both parts

## 19. Words and IDs

No new family word. Every word below is decided (D371, D383). Today's spelling is used in the code; the
renamed spelling is beside it, for the ID move.

| Piece | Today's spelling | Renamed spelling | Family word |
| --- | --- | --- | --- |
| The source kind | `cells.species_condition@1` (key `species_conditions`) | `cells.kind.species_condition@1` | `kind` |
| Its law | `cells.hill_product_factor@1` | `cells.transfer_factor.hill_product_factor@1` | `transfer_factor` (decided for `ph_conditioned_factor@1`) |
| The operator (section 15, only if built) | `cell_assembly_pool@1` | `cells.operator.cell_assembly_pool@1` | `operator` |

- The names need rows in `scripts/moves/id-rename-choices.json` for the two kinds of live ID above (the
  operator's only when it is built). That file is not mine: the lead tells its owner.
- The driver introduces no ID. Its JSON keys (`observable`, `levels`, `stream`, `channels`) are words of an
  input file, not family words. `root_component_has_cycle` is legacy's own law name, reused as an observable's
  name; it is not an ID in the live tree.
- `bookings`, hooks: no new interface word. If the core adds `factor_reads` to the kind registry (section
  5.5), it is a hook, not an ID.

## 20. Price and order

| Item | Agent-days | What is in it |
| --- | --- | --- |
| G-7 driver (F4) | 1 to 1.5 | `schedule.py` and the subcommand 0.4; rows 0.4; the composed example and a check on the two K-only worlds 0.3; library page, run view, review 0.3 |
| G-5 source kind | 1 to 1.75 | law and kind 0.4; rows 0.35; matrix tag, library page, run view 0.25; composite demonstration 0.25; review and landing 0.3 |
| G-5's loop term, if the sink takes it | + 0.25 | with stream D |
| G-7 operator, later | 4 to 5.5 | the rows, matrix, statistics rows, the quantity source of `@2` and a judged comparison |
| Plan's own figures | 2 to 3 and 4 to 6 | `docs/LEGACY_PORT_PLAN.md`; the composed run replaces the second |

- **Order.** (1) G-7's driver: it depends on nothing but live code, and the two K-only worlds are re-expressed
  with it. (2) G-5's source: it depends on no stream, and is tested with the prototype's world (one store
  node, today's kinds). (3) Stream D's store and its route. (4) The calcium worlds and the assembly-regulated
  calcium clusters use both. The driver can serve those four clusters as soon as (3) exists; nothing in it is
  calcium-specific.
- The estimates are mine (S), from the live files of the same shape (ph_condition.py, a door-source kind, is
  250 lines; the pool's run module is 200). They have not been tried.
- **A risk I see:** the IMEX composite's cost is the consumer's, not the driver's. At 20 ms and 12.5 us a
  composite run of two cells took minutes on these crowded CPUs (M, no timing claim).

## 21. Corrections to the plan, the map and the docstrings

Lines are at 43b22d40.

1. **The plan's section 4** cites `species_regulated_availability.py:154`, 548 to 551 and 743 to 745. They
   hold at ce4780d2 and are stale. Now 159, 553 to 557 and 748 to 754.
2. **"Reads species amounts, not topology"** (plan, the same section) is out of date at `@2`, which also reads
   operators' quantities (a site's fraction, a population's rate).
3. **`species_regulated_availability`'s text** "@3's step moves it" is false for an impermeant charged row
   (section 3). The refusal is right; the reason is not.
4. **`surface_tissue.py:376` to 381**: "every world in use has 0, 1 or 2" is false once a -3 row is in a world
   (section 3).
5. **The map's 14.3** says the driver "qualifies on RK4 for the cell and the base". It does, with the declared
   floor field solver (section 13.5). The map names no field solver and says "RK4 at <= 25 us". With the
   default solver the base cluster's first step is refused at every dt tried.
6. **The plan's section 8 three-step order template** fits the composed run and not a held operator factor
   (section 12).
7. **D211 and I6** would fold `ip3_er_release@1` into the cardiac release. It is another mechanism: that
   release relaxes to a target proportional to the L-type current and has flux states
   (`docs/HUMAN_CARDIAC_LAWS_DESIGN.md` section 3.5). Do not fold.
8. **A latent parser hazard (not this note's).** `definitions/surface_pump_spec.py:208` to 217 multiplies each
   junction control's `availability` by the junction's initial gate *in place*, on a deep copy that keeps
   internal aliases. A definition built in Python that shares one schedule object between a junction and other
   controls is parsed with the other controls scaled too (M: membranes and pumps became 0.6 of what was
   declared; a JSON file cannot do this). It silently gave a 10 mV error in one of my probes before I found
   it.
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
| `composed_run4`, `composed_composite`, `rk4_domain`, `rk4_domain_floor` | The composed run, RK4 and IMEX, and the field solver's floor |

Two of my probes were wrong first. `composed_run3` shared one schedule object (item 8 above) and gave a 10 mV
error; it is kept as `composed_run3_ALIASED_invalid.log` and is not cited. The first `composed_run` used the
default field solver and was stopped once its first step was refused.

## 23. What is not claimed

- No agreement with any experiment, and no measured constant. The numbers are the captured definitions'.
- No claim about the receptor, IP3's charge in water, IP3 metabolism, assembly energetics, or the real cage.
- No claim that a composite's calcium run meets any band: only a prototype ran (section 4.1).
- No GPU claim. No claim above a few hundred cells for the composed run. No timing.
- Nothing here is judged. Both parts come back to the user with their price before any build (D383).
