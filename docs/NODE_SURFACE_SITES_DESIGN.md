# Binding sites owned by a finite node's own surface (FR-28): design note

**Status: decided (D268, option A, a plain `{"node": N}`, matrix sites covered, @2 refused in
version 1) and built on branch `fr28-node-sites` (development, 21 November 2026).** The note below is
the desk note as decided.

**Earlier status: desk note, proposed, not built.** The operators owner wrote it at the lead's request on
20 November 2026 (FR-28, D245, normal priority). The user wants the options discussed before a new
system is built. Nothing here is coded, and integration would grant no acceptance (D143).

**The request** ([FEATURE_REQUESTS.md](FEATURE_REQUESTS.md) FR-28, from the same outside review as
FR-27): let a binding-site population belong to the surface of a finite outside node, such as a
vessel wall. It faces that node and binds only. Today an owner must be a cell's patch or a contact,
so the review put the wall's sites on an inert stand-in cell that exchanges nothing. The numbers are
unaffected.

**Engine models it concerns:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
`site_occupancy@1` ([SITE_OCCUPANCY_DESIGN.md](SITE_OCCUPANCY_DESIGN.md), "the site note"). FR-28
queues after FR-26 on `site_occupancy.py`. FR-24, FR-27 and FR-26 are gated together as one stack.
Code is cited by function, at that stack's top, which is what FR-28 would build on.

**S** marks our own reading or derivation.

## 0. Summary

| | |
| --- | --- |
| **Before** | A population's owner is `{"patch", "face"}` or `{"contact", "side"}` (`site_occupancy._owner`). The review's vessel wall is a population on an inert stand-in cell's patch. That cell has a volume, ions, a membrane and a voltage, and it takes part in the field solve. It exchanges nothing |
| **Proposed** | A third owner form, `{"node": N}`: sites owned by the finite outside node N itself, facing N, binding only. This is option A, with capacity declared as counts, as for every population (§2, §4) |
| **Why it is small** | No compiled program reads the owner. The layout is built from the facing pool (`bind`, through `facing_node`), so an outward patch population at N and a node-owned population at N give the same layout arrays (**S**). The owner enters host-side checks and records only (§1) |
| **Ledgers** | None new. A node-owned population books exactly as an outward patch population at N does (§5) |
| **Bitwise** | Every existing world, at all three levels. No layout field, program or existing `to_dict` changes |
| **Acceptance** | The review's well with its wall owned by the node, against the same well with the stand-in: the tracer and site fields equal on every row, bit for bit where the compiled site arithmetic is the same; the host checks on every row; the review's analytic equilibria (§8) |
| **Price (S)** | A: about half an agent-day. B (A with a declared area and site density): about one. C (a surface entity on @3's nodes): two to three, with the @3 owner (§10) |
| **Recommended** | A (§10) |

## 1. What exists

- **The owner forms** (`_owner`) are a patch with its face, `outside` or `inside`, or a contact with
  its side, `first` or `second`. `facing_node` gives the free pool a population binds from: the
  patch's outside node, the patch's cell, or the side's cell. A patch population facing a held bath
  is refused at parse: binding from a chemostat, booked as reservoir supply, is a door (site note
  §6.2).
- **The layout does not read the owner** (`bind`). It reads:
  - the facing pool's kind and index;
  - the receiving cell, for internalisation only;
  - the capacity S = α ν N / N_f;
  - the anchors, the rate constants, the ligand's row;
  - the pools and the static route components (`components`, joined through facing nodes).

  This follows the site note's rule that identities live in declarations, never in arrays (§1.6).
- **Where the owner is used, all on the host:**
  - parsing: `_owner`, `parse_population`'s held-bath refusal, and `_internalisation`, which allows
    only an outward patch;
  - `occupancy_to_dict`, and the summary's `site_populations` owner record;
  - `check_slots`, replacement@1's rule as narrowed by FR-26;
  - FR-26's W: `replaced_populations` selects patch owners, and `bind_occupant` indexes every
    population's cell;
  - `check_compartments`, for internalisation only;
  - `population_cell`, R3's locality (FR-24), through `quantity_entities` to @2's site source;
  - `receiving_cell`, for internalisation only.
- **The stand-in in the review's world.** FR-27's `wash_schedule_fixtures.well` declares cells
  `specimen` and `wall_surface` (1 pL each). The wall's sites sit on the patch `wall_face`, facing
  the 1 µL well: capacity 20 fmol, K_d 60 nM, binding ten times faster than the specimen's.
- **What the stand-in costs (S):**
  - a cell that is not there, carrying ions, a volume and a voltage, which the field solve and
    every per-cell ledger include;
  - cell rules applied to a wall: replacement@1 and W could replace it, and @2 would read its
    sites as a cell-local source;
  - a reader of the run sees one more cell than the experiment has.

## 2. The owner kind (all options)

- **The form:** `{"node": N}`, with N a finite outside node. The population faces N. There is no
  face or side key, because a node's own sites face only that node.
- **What it means:** immobile sites owned by the node itself. These may be a vessel wall, a coated
  bottom, or beads or a matrix resting in the node.
  - The law is unchanged: Langmuir binding on finite sites (site note §2.2), with the node well
    mixed, as for an outward patch.
  - The role (wall, matrix, bead) is the driver's; the law names none (D144).
  - The same owner would also serve immobile binders in a node that belong to no cell, such as an
    extracellular matrix. No consumer has asked for that yet.
- **In the declaration types:** `owner_kind` is `"node"`, `owner_id` is N, and `facing` is the
  fixed value `"surface"`, which `to_dict` does not write.
- **It binds only.** Its `internalisation` must be null: it has no inward.
- **The node must be finite.** A held bath is refused, as for an outward patch.
- **Several populations on one node** are admitted, as several on one patch are. They compete for
  the node's free ligand, beside every patch population facing it, and `components` joins them
  through the node.

## 3. Beside the cell owners

- **One entity and one operator.** A node-owned population has the same R, B and S, constants,
  state, multipliers and laws as any other. `site_occupancy@1` still owns every population (the site
  note's option O). The program cannot tell it from an outward patch population at the same node
  (**S**): `bind` builds both from `facing_node`, and neither internalises.
- **It belongs to no cell:** `population_cell` gives none. The consequences:
  - **Replacement@1 and W.** It sits on no slot. `check_slots` never refuses it, and W never resets
    it, so it keeps its bound material across any cell's replacement, as a vessel wall would.
    `bind_occupant` would give it the padding index 0, with `site_replaced` false.
  - **The padding index 0 is also a real cell's index.** It is safe only because W's event selects
    a population by `site_replaced` before it reads the cell index:
    `due = site_replaced & due_slot[site_population_cell]`. §8's aliasing row guards this.
  - **R3 (FR-24).** `quantity_entities` gives it no cell. @2's site source requires the population
    and the element to share a cell (`_site_layout`), so a node-owned population is refused as a
    source, with a message of its own. No @2 target lives at a node, so the door is a node-level
    target, not designed here.
  - **The partition and insertion** are refused beside the operator anyway.
- **The summary's owner record** gains the kind `node` (its id N, facing `surface`). The run view
  has no site layer in version 1.

## 4. The capacity: counts, or an area and a density

This is where the options differ.

- **Counts (option A).** S = α ν N / N_f, as for every population. The site note's "why counts and
  not densities" stands: version 1 reads no area (§1.1).
  - For a wall, N counts adsorption sites, or coating molecules with ν sites each.
  - A driver with an areal density ρ (sites per m²) over an area A sets N = ρA and records both in
    its own inputs. The engine never reads an area.
- **An area and a density (option B).** The owner declares its area, `{"node": N, "area_m2": A}`,
  and the population declares a density of copies, `copies_per_m2` ρ, in place of `copies`, so
  S = α ν ρ A / N_f. Membrane state's channel populations already declare densities per m² in this
  way.
  - There are then two capacity forms in one law. Exactly one is declared per population, and
    anything else is refused.
  - It makes a geometry series declarative, such as one wall density over several well sizes.
  - The area is a constant. No operator admitted beside the site operator changes a node (water
    and the lumens are refused), so nothing would ever change it.
- **A surface entity (option C).** @3's outside nodes declare their surfaces,
  `surfaces: [{id, area_m2}]`, and a population names a surface by id.
  - Geometry would belong to the inner model, where a second consumer could share it: another
    species adsorbing to the same wall, or a later area-scaled exchange.
  - It changes @3's definition, the @3 owner's file. The key would be optional and absent by
    default, so every existing `to_dict` stays the same.

## 5. Ledgers

No new ledger or term. A node-owned population books exactly as an outward patch population at N:
- **Material:** its moiety identity R + B = S, the bound ledger, and @3's outside ledger at N
  through `site_bound_net_fmol` (`material_terms`).
- **Energy:** the site free energy (site note §3.3). Binding is passive, so the component books no
  work, unless an internalising population of a patch facing N joins it, in which case the hybrid
  rules apply as they do today.
- **Where its site-side heat and work are booked, with no cell to own it:**
  - **Heat** is booked per pool, never per owner. The half-step forms each pool's heat
    (`half_step_terms`' `pool_heat`, its node's subsystem) and scatters it by the pool's kind, into
    `site_dissipated_energy_pJ` [cell] or `site_outside_dissipated_energy_pJ` [outside].
  - A node-owned population's pool is (outside, N), so its heat goes to N's entry of the outside
    field. The cell scatter's padding index 0 carries an exact 0 there, through the same masked
    `where` that serves an outward patch population today.
  - **Work and the energy magnitude** go to the population's own entries, `site_work_pJ` and
    `site_energy_magnitude_pJ` [site population].
  - No cell index is read for any of these fields, so nothing is booked at a cell.
  - **W's books** (departed, arrived, the jump) are also per population. A node-owned population's
    entries stay 0, since W never resets it (§3, §8).
- **Charge:** none. Ligands are neutral.
- **The trace rule** (site note §4.3) applies unchanged: the ligand's trace is at most 10⁻⁶ K_d of a
  node-owned population too.

## 6. Composition

Every rule of the operator holds, and the node owner adds none at the law level. The composition
matrix's generated block does not change, since there is no new law. One data-level row is added,
for the @2 refusal (§7).
- **Admitted, as for an outward patch population at N:**
  - @3's faces at N (binding beside transport);
  - D150's turnover and exchange, and D152's reactions at N;
  - the bath schedule, which doses held baths only, so never N (door S);
  - FR-27's wash at N, which leaves bound material in place (the review's case);
  - replacement@1 and W, since the population has no slot;
  - membrane state, injection and the unit producer;
  - the coupling @1 and @2, except @2's site source.
- **Refused, as today for the operator:**
  - by the declarations: water, the symport, replacement@2, insertion@1 and @2, the lumens, the
    partition and the bridge;
  - by their admitted lists: the compartments and trafficking;
  - RK4 and the stationary analysis.

## 7. Refused in version 1

**At the definition,** each with its reason:
- a node that is a held bath: the chemostat door;
- an unknown node, or a cell's ID given as a node, since a cell's sites sit on its patches;
- a face or side key beside the node key, since a node's own sites face only the node;
- an internalisation route, since the population has no inward;
- @2: a node-owned population as a coupling's site source, since it has no cell and no @2 target
  lives at a node. The same holds for a member of a shared set on a node's own surface (FR-45,
  `docs/SITE_OCCUPANCY_DESIGN.md` §14);
- option B only: a population that declares both `copies` and `copies_per_m2`, or neither, and a
  density whose owner declares no area.

**Not refused; stated as limits:**
- **The node is well mixed.** There is no unstirred layer or diffusion-limited adsorption at the
  wall. This is the same approximation as for every population at a node.
- **The capacity is constant.** There is no fouling and no change of area.

## 8. The acceptance test

The criteria are written before any run, as FR-27's were.

1. **NumPy rows** (tier 1, in `test_site_occupancy.py`, about 1 s):
   - **The layout row.** Take the review's well with its wall owned by the node, and the same well
     with the stand-in. Every site layout array is bitwise the same in both: capacity, anchors,
     rates, ligand row, facing kind and node, pools and components.
   - the round trip, the summary's owner record, and no cell from `population_cell`;
   - one row in `REFUSALS` for each refusal of §7, and the @2 row in
     `test_species_regulated_availability.py`.
   - **The aliasing row** (W's event map, as FR-26's event rows are written).
     - **Its world:** cells `cell_0` (index 0, the padding index's real owner) and `cell_1`; an
       outward population on `cell_0`'s patch, covered by W from template T; and a node-owned wall
       population at the finite node that patch faces. replacement@1 replaces `cell_0` at t_e.
     - **At t_e, after the event maps:**
       - `cell_0`'s population is reset to its template, B′ = θ′S within W's 4 ulps;
       - the wall's R and B are bitwise unchanged, and its departed, arrived and jump entries are
         exactly 0;
       - the summed departed booking equals `cell_0`'s population's B before the event, so it
         excludes the wall's sites;
       - the owner's bound ledger closes with W's terms.
     - **Planted:** the wall read as `cell_0`'s (its `site_replaced` set true in the layout, its
       index left at 0). The event then resets the wall and books its B as departed, so the row's
       assertions fail. The test asserts that they do.
2. **A compiled pair:** one row in the review's compiled test file, `test_wash_schedule_runs.py`,
   tier 2, about 20 s for both arms over a short horizon (**S**). Its reason: the request's
   statement that the numbers are unaffected needs the runner.
   - Both arms run through the runner, with every host check passing on every row.
   - **Bitwise is expected** for the well's free tracer and both populations' R, B and bound net, on
     every row (**S**). The site half-step reads only the well's pool and its own state, and the
     stand-in is quiescent.
   - **The two programs differ in shape,** since the stand-in arm has one more cell, so their
     compilations may round differently. The heat at the well, the work and the magnitudes are
     therefore allowed 16 ulps, as FR-24's two programs differed by 8.
   - A difference beyond these is diagnosed before any bound is changed.
   - The four amounts sum to 100 fmol within 10⁻¹² fmol on every row.
   - **Which time each stock is read at** (the Lean lane's request). The rows are the history's
     accepted steps of 10 ms, and the wash is at 0.05 s. The row at 0.05 s holds the stock the wash
     acts on: the wall's 10 fmol and the specimen's 30. The first saved row after it is 0.01 s
     later, at 0.06 s. Its bound stocks are not the event's, since both populations have begun to
     re-equilibrate with the halved free tracer (the wall's relaxation time is about 1.1 s, **S**).
     The sample, booked at the event, is exact on every later row.
3. **The development run** (evidence, not a test): the review's whole sequence, 140 s with FR-27's
   wash at 20 s, with the node-owned wall, against FR-27's development run (its arm W). Its row
   at 20 s is the stock the wash acts on, and its first saved row after the wash is one step,
   10 ms, later.
   - The same comparison holds on every row.
   - At the end, the amounts lie within 2 × 10⁻⁶ fmol of the review's analytic two-site
     equilibrium.
4. **D148:** every registered world is bitwise at all three levels (crossrev and FR's set at the
   gate), and FR-3's judged program is unchanged.

## 9. Files (option A)

- **`src/cells/operators/site_occupancy.py`:**
  - `_owner` gains the node form;
  - `facing_node`, `population_cell` (no cell for a node), `occupancy_to_dict` and
    `_internalisation` (refused for a node);
  - `check_slots`: a node owner is skipped;
  - W's `bind_occupant`: index 0 for a node-owned population;
  - the module docstring.
- **`src/cells/operators/species_regulated_availability.py`:** `_site_layout`'s message for a
  population with no cell. The check already refuses one.
- **`validation/tissue/site_occupancy_fixtures.py`:** `population(..., node=...)`.
- **`validation/tissue/wash_schedule_fixtures.py`:** the well's wall owner, as a stand-in or a node.
- **The tests of §8.**
- **The docs:**
  - the site note: §1.1's owner row, §6.2, §7 and §9;
  - PUMP_COMPOSITE.md's operator row, and the matrix's data-level row;
  - FR-27's note, on the review's wall.
- **Not touched:** @3, the composite, the contract, W's event and every other operator.

## 10. Price (S) and the recommendation

| Option | What it is | Price | For | Against |
| --- | --- | --- | --- | --- |
| 0 | The stand-in, as today | None | Nothing to build | A cell that is not there: ions, a voltage, the field solve, and cell rules applied to a wall. The request asks to remove it |
| **A** | **The node owner, with counts** | **About 0.5 agent-day** | Host-side only; bitwise everywhere; no new ledger; consistent with the site note's counts | A driver converts an areal density into counts |
| B | A, plus a declared area and a site density | About 1 agent-day | Area scaling is declarative | Two capacity forms in one law, and an area nothing else reads |
| C | A surface entity on @3's nodes | About 2–3 agent-days, plus the @3 owner's review | Geometry in the inner model, shareable | A change to @3's definition for one consumer, with no second consumer yet (D136, D144) |

**Recommendation: A.**
- It is what the request needs. The review's wall becomes the well's own, and the numbers stay
  the same.
- It adds no physics, ledger or program, so every existing world stays bitwise.
- B's area is worth its second capacity form only when a consumer brings an areal density and a
  series over geometry.
- C is worth it when a second operator needs a node's surface.
- Either can be added later without changing A's declarations: under B, counts stay the default
  form; under C, `{"node": N}` stays valid beside a named surface.

## 11. Questions for the lead and the user

1. **A, B or C?** A is recommended.
2. **The key.** Is it `{"node": N}`, or a named surface `{"node": N, "surface": "wall"}`? The name
   is a label only under A; it matters under B or C.
3. **The scope of the owner.** Does it also cover immobile sites in a node that belong to no cell,
   such as a matrix? The recommendation is yes: the owner is neutral, and the role is the driver's
   (D144).
4. **@2 reading a node-owned population.** The recommendation is to refuse it in version 1, since no
   @2 target lives at a node.
