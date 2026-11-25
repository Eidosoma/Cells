# A closed compartment owned by a cell (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Qualified, 18 November 2026.** The registered protocol `fr1-closed-compartment-v1`
(`validation/tissue/compartment_acceptance_protocol.json`, registered at 05a8d193) was judged once
from a clean snapshot of that commit: passed, 44 of 44 judged criteria (C1 to C13 with their
controls), against the code-blind references (`validation/fr1/references`). It is exchange's first
judged acceptance. Its scope is the neutral first version as built there (§3.3): no ion route and
a zero anchor on the compartment, ARS at 1 ms and RK4 at 0.1 ms; V_b's orientation is not shown.

**Accepted, 14 November 2026 (the lead, with the advisor; D169).** The silence claims S1–S5 are pending milestone 1, with their criteria fixed. This protocol is exchange's first judged acceptance.

**Milestone 1 built, 14 November 2026 (§12).** The declaration, the contract's fail-closed marker and the composite's branch for declarations alone are built. S1–S3 hold on every row of every program in a live-owner world, and a planted control breaks them in each program family. S5 is identical in all four pairs, and crossrev is identical in all seven sets. S4 and P2 (on the heredity sheet) are reported. Integration grants no acceptance: C1–C13 and their references come next.

**Refusals 4 and 5, later versions (status 18 November 2026):**
- **On main,** with D172's round (ab267c39): refusal 4 version 1.1 (§3.4.1, FR-4's kinds).
- **On main since fr45-next merged (16 November):**
  - refusal 4 version 1.2 (§3.4.2, FR-5's source kinds);
  - refusal 5 version 1.1 (§3.4.3, the charge anchor where charged routes are admitted).
- **Version 1.3 (§3.4.4, 18 November; CORE_SEAMS §18's option (a)):** refusal 4 checks the kinds
  per move, from each law's declared step terms, in place of version 1.2's lists of kinds.
- **The membrane-state wall's door (§4, 19 November; D217, FR-2):** membrane state composes
  beside a compartment only together with `scheduled_membrane_trafficking@1`, and the declaration
  reads the areas and capacitances as `reference` reads.
- **Refusal 5 version 1.2 (§3.4.5, 19 November; D217, FR-2):** an anchor is also admitted where an
  admitted operator's routes charge the compartment; checked at the definition.

**As drafted (14 November 2026),** for the lead's review with the advisor and revised the same day
after that review: no engine code was added or changed. One read-only probe ran on the engine as
it was, as the lead directed: FR-10's probe 1, which also carried this note's D147 record and its
loading-from-a-trace arms (§9). The other probes are requests (§9).

D157 logs the request (FR-1, [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-1--a-closed-internal-compartment-on-the-shared-inventory)).
The user's words were: "here is a new feature request please log as high prioriity". The decision
reads:
- **The feature:** a cell-owned finite node, with no bath and no faces, bounded by one patch of its
  owning cell, carrying its own volume and inventory rows, with transfer routes to the owner's
  cytosol.
- **The order:** fixed topology first, with retained and cytosolic material kept distinct and
  transfers reconciled on both sides. Dynamic internalisation (FR-2) later.
- **Design first (D142),** as a general feature (D144). The lead's mapping (exchange as a possible
  transfer law, fixed volume first, the electrical treatment as the hard question) is for this note
  to test.

**Engine models it runs (AGENTS.md milestone rule):**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- one new declaration, `cell_owned_compartments@1` (§1.4), which owns no state and runs no part;
- the transfer law is D150's `scheduled_species_exchange@1`, unchanged (§2). Degradation inside a
  compartment is D150's `scheduled_species_turnover@1`, and reactions inside are D152's
  `local_species_reactions@1`, both unchanged (§4).

No model, solver or law changes. The one change to shared code is one widened, host-only admission
in the contract's registration check, which can also serve a part-less site owner for FR-3 (§1.6). It
is an addition, not a change to existing behaviour.

**Basis.**
- The [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) (D150): one inventory, the
  exchange law, identity and the occupant rule, §2.5's occupancy door.
- The [shared-inventory reactions design](SHARED_INVENTORY_REACTIONS_DESIGN.md) (D152) and the
  [coupling design](INVENTORY_COUPLING_DESIGN.md) (D155, D156).
- The contract: [PUMP_COMPOSITE.md](PUMP_COMPOSITE.md), the [v2 design](PUMP_COMPOSITE_V2_DESIGN.md)
  §1 (energy roles) and §3 (the 64-node cap).
- The lifecycle: the [S5 design](CELL_DIVISION_S5_DESIGN.md) §2 and §6, and the S3 lumen's
  accounting ([S3 plan](CELL_DIVISION_S3_PLAN.md) §1; `operators/restricted_lumen.py`).
- The older family's ER capacitor, [ER_CALCIUM.md](ER_CALCIUM.md).

**Evidence and log:** `/mnt/workspaces/Cells/closed-compartment-20261114-01/`:
- HANDOFF.md: the code facts with their files and functions, the citation records, the probe's
  criterion (written before its run) and its results;
- `arithmetic/`: the script and output behind every number marked **S** here;
- `sources/`: the two papers' open-access JATS XML from Europe PMC, from which the quoted sentences
  were extracted by text search;
- `sweep/`: the static sweep of the existing worlds (§3.4);
- `probe1/`: FR-10's probe 1, with this note's arms D1 and D2 and the D147 record (§9);
- `snapshot-main-ced45c8/`: the probe's clean snapshot of main at ced45c87, frozen by
  `validation/source_snapshot.py` from `main-clone/`, a clone of the repository detached at that
  revision (the worktree may not touch the main checkout).

**S** marks our own derivation, arithmetic or interpretation, as in the D150 and D152 notes.

## 0. Summary

1. **The entity is a declared node of @3's layout. It needs no new layout structure** (§1.1).
   - It is a finite outside node that is not a held bath and that no face joins. Exactly one
     membrane patch faces it, and that patch's inside is the owner's cell.
   - Its volume, amounts, fixed charge and charge anchor are @3's own fields of that node. Its
     species are @3's rows at that node: the same species row at another node, never a new row.
   - **The topology already runs.** D150's face-free guard world is such a compartment. It runs
     exchange and turnover under IMEX and RK4, and D152's face-free world runs reactions at that node
     (§1.2).
2. **Ownership is a declaration that carries refusals** (§1.4, §1.5).
   - `cell_owned_compartments@1` names each compartment: its node, its bounding patch, its owner and
     an optional label. It checks that @3's topology implies the ownership.
   - It refuses what would break identity: replacement events on an owner's slot, closers, volume
     providers, field-input providers, and ion routes on the bounding patch.
   - It holds no state and runs no part. The contract refuses such an operator today, so it gains
     one widened, host-only admission, a strict superset of today's rule, which can also serve a
     part-less site owner for FR-3 (§1.6).
3. **The transfer law is D150's exchange, unchanged** (§2).
   - Loading is an export route, and release an import route. Both are driven routes (D174,
     ARCHITECTURE.md's "Transport laws by physical contract"): each books the free-energy change of
     what it moves as signed work, with no heat. An export–import pair can follow a permeation's
     concentration trajectory without being a passive permeation.
   - Every move books the same amount on both sides, so retained and cytosolic material stay
     distinct and reconcile to rounding.
   - **Limits:**
     - the pair is Strang-split, so its equilibrium carries a relative bias, x*/x_eq − 1, of
       −a(a + 2b) dt²/96 (**S**; §2.3);
     - its fall in free energy is booked as signed work, not heat;
     - saturable loading is refused.
   - **Doors:** a passive permeation law, door T1, with an exact two-way relaxation and heat
     (FR-5's neutral leak; D174's target law); and saturable loading.
4. **The electrical treatment: a free node of @3's capacitor network** (§3.1, §3.2).
   - The node's capacitor row gives C_b (φ_comp − φ_cell) = q_comp. So the bounding patch's voltage
     is V_b = φ_cell − φ_comp = −q_comp/C_b exactly (**S**), and the owner's plasma membrane sees
     q_cell + q_comp.
   - This is the parallel-plate organelle capacitor of Grabe & Oster (2001) and Ishida et al.
     (2013). Their impermeant charge B is @3's fixed charge, and their sign is the opposite of @3's
     patch voltage.
   - The node takes part in the capacitor solve, not in the Kirchhoff offset solve.
5. **A neutral first version is electrically silent** (§3.3). The bounding patch carries no ion
   route and the content is electroneutral, so q_comp stays 0 and V_b stays 0. **These claims are
   unrun and pending milestone 1,** with each criterion fixed in §3.3 before any run.
   - *Promised:* the compartment's ion rows never change (bitwise); V_b stays 0 to the field
     solve's rounding; the same world with and without the declaration traces to identical program
     text and constants, since the declaration runs no part.
   - *Reported, not promised:* the rest of the world equals the same world without the node only to
     rounding, because the dense solve gains a row.
6. **The charged door (FR-4, FR-5) is a stability question first** (§3.4, **S**: an unrun code
   reading, which probe P1 would measure).
   - @3 bounds membrane charge relaxation per cell, and relies on implicit face drift to hold
     outside nodes. A compartment has no face.
   - Its own rate, G_b/C_b = P F² c/(RT c_m), does not depend on its size. For Ishida et al.'s
     chloride permeability it is about 4.8 × 10³ s⁻¹. The per-cell bound sees about 7 s⁻¹ for a
     10 pF owner. So an explicit 1 ms step would be unstable, and @3's checks would not refuse it in
     advance.
   - The door is an implicit treatment of the bounding patch (a new IMEX ID), with a bound term as
     its safety net: one D148 round with finding 3's, specified after P1.
   - A sweep of the existing worlds found none exposed on @3's IMEX numerics.
7. **The 64-node cap is untouched in version 1** (§3.6). A compartment provides no field input.
   - Each compartment is one dense field node. It counts against the dense solver's bound always,
     and against 64 once membrane state (FR-3) or insertion (FR-2) composes.
   - **FR-9:** compartments cost nodes, not species rows.
8. **Composition** (§4).
   - *Composes:* @3, injection, D150's exchange and turnover (degradation at the node), D152's
     reactions at the node, the coupling operator, replacement@1 away from owners and away from
     owners as donors, and FR-10's bath schedule.
   - *Composes since 19 November 2026 (D217):* membrane state together with FR-2's
     `scheduled_membrane_trafficking@1`, the membrane-state wall's door.
   - *Refused, each with its door:* water and what requires it, closers, membrane state without
     trafficking (the membrane-state wall, which FR-3's note names too), insertion, the lumens,
     and FR-3's `site_occupancy@1` until its one-line admission.
   - **A wall on the requester's first world:** FR-10's bath schedule and D152's reactions refuse
     each other, through the view field the schedule provides. Version 1's workaround is
     degradation by turnover; the door is FR-10's door S.
9. **Accounting** (§5). There is one material ledger, @3's, at the node. At a fixed volume, @3's
   chemical term at the declared volume is the physical free energy, so no dilution or mixing term
   arises. The lumen's terms arrive with the volume door and FR-2.
10. **Qualification** (§6). It is numerical first, against closed forms written from Appendix A by
    an agent that never reads the code. It is also exchange's first judged acceptance, since D150's
    judged scope was the faces and turnover's clearance. The items cover:
    - loading with retention;
    - two-way exchange with its predicted splitting term;
    - saturable release and degradation;
    - reactions inside, and the three-node uptake path;
    - electrical silence;
    - loading from a trace under RK4.
11. **Two limits, stated, not asked.** A node is a lumped pool, a validity limit: about 99 molecules
    per lysosome at 1 µM is D150's continuum floor (§1.3). Nested compartments are a topology limit
    of @3 (§1.4).
12. **Effort** (§10): about 3.5 agent-days (range 3 to 4.5), plus CPU minutes.

## 1. The entity

### 1.1 A declared node of @3's layout, with no new structure

| FR-1 asks for | @3's layout already has | The declaration checks (§1.4) |
| --- | --- | --- |
| A finite node | An `extracellular` entry with `reservoir: false` | Not a held bath, not the gauge |
| No faces to other nodes | Nothing requires an outside node to have a face (`definitions/surface_tissue_spec.py`) | No face names the node |
| Bounded by one patch of its owner | A `membranes` entry whose `outside` is the node and whose `inside` is the owner | Exactly one patch faces the node, and its inside is the declared owner |
| Its own volume | The node's `volume_pL` | Fixed in version 1 |
| Its own rows of the one inventory | The node's column of `extracellular_amount_increment` [species, outside] over its anchors | The same species rows as the cytosol |
| Transfer routes to the owner's cytosol | D150's exchange routes on the bounding patch (§2) | – |

**What @3 requires of the node.** @3 requires every species to be positive at every active node
(D150 §1.3). So a compartment declares a positive amount of every species: a trace for cargo it does
not yet hold, and a full ion complement. It also declares a fixed charge that makes its charge
anchor F (fixed + Σ z n) zero (§3.3). @3's own definition check holds the anchor to that sum within
1e-20 C (`models/surface_tissue.check_definition`). "Empty" therefore means a trace of cargo plus an
immobile, electroneutral ion complement.

**Why "outside" is the right category (S).** The lumen of the secretory and endocytic organelles is
topologically equivalent to the cell's exterior. A membrane separates it from the cytosol, as the
plasma membrane separates the cytosol from the extracellular space (standard cell biology; for
example Alberts et al., *Molecular Biology of the Cell*, the chapter on intracellular compartments).
So the bounding patch's inside is the cytosol and its outside is the lumen, which is @3's
orientation for every patch.
- The mitochondrial matrix is the exception: it lies inside a double membrane and is topologically
  cytosol-like. A one-patch compartment can still hold it as a species compartment. Its patch
  voltage then has the opposite sign of the usual Δψ_m, a reporting matter for its consumer.

**Why not new layout structure.** A new layout field would be a new @3 identity, and @3 is frozen
and qualified. Nothing about a fixed compartment needs a field that @3 lacks: volume, amounts, fixed
charge, charge anchor, and the patch's area and capacitance are all there.

**Why not a separate inventory operator.** A pool held outside @3's node axis would be D150 §1.1's
rejected "second inventory". Every lifecycle operator would have to learn its fields, water would not
see it as an osmolyte, and it would need its own electrical model. FR-9 noted the budget cost too: a
pool off the node axis needs its own species row. A declared node costs a node and no row.

### 1.2 Already running: the face-free guard worlds

D150's RK4 guard world of the operators' work is this compartment's topology
(`validation/tissue/secreted_species_fixtures.face_free`): "one cell and its finite node joined only
by the contact patch (no face)". The cell's wall patch sits on a held bath, and the node `ecs_0` is
faced by the cell's contact patch alone.
- `tests/unit/test_secreted_species_runs.py` runs secretion into that node and uptake back, and
  every host check passes on every row under IMEX and under RK4.
- `tests/unit/test_secreted_species_guards.py` uses it as the species-only world whose energy flow is
  one law's work alone.
- D152's face-free network world (`validation/tissue/species_reactions_fixtures.face_free_network`)
  runs reactions at that node; its driven example removes P at `ecs_0` under Hill inhibition.

So @3, exchange, turnover and D152's reactions already run on a cell-bounded, face-free node. What
this note adds is what makes that node an owned compartment rather than an anonymous pocket: identity,
the refusals that protect it, and the qualification of the uses FR-1 names.

### 1.3 One node: one organelle or a lumped pool

**The scale (S, from Ishida et al.'s lysosome of 0.68 µm diameter; `arithmetic/`).**
- Its volume is 1.65 × 10⁻⁴ pL, its area 1.45 × 10⁻¹² m², and its capacitance at 1 µF/cm² is
  1.45 × 10⁻¹⁴ F.
- 1 µM of cargo in it is about 99 molecules. That is D150 §1.3's continuum limit of about 10²
  molecules per node.
- Its ions at 100 mM are about 10⁷ molecules. A patch voltage of 100 mV is about 9 × 10³ elementary
  charges, 3 × 10⁻⁴ of its ion content.

**So a compartment node is a well-mixed continuum pool.** It may be:
- *one organelle*, where its contents are far above 10² molecules (its ions always are);
- *a lumped pool of N identical organelles* of one cell, with volume N V, area N A and capacitance
  N C. That is exact for linear neutral transfer and for the capacitor relation of §3.1, as long as
  the organelles share one state (**S**): V = q/C, with q and C both scaled by N.

For µM cargo in vesicles, the lumped pool is the regime of validity. "Particle inside a vesicle"
against "cargo in the cytosol" is then a pool amount against a cytosolic amount. Per-vesicle counts
and stochastic loading are out of scope.

**This is a validity limit of version 1, not a modelling choice.** About 99 molecules per lysosome at
1 µM is D150's continuum floor. A study that needs one vesicle told from another needs a stochastic
treatment, which no version here provides.

A cell may own several compartments, for example a lysosome pool and a secretory-granule pool, each
its own node.

### 1.4 The declaration and its checks

```json
{
  "law": "cell_owned_compartments@1",
  "compartments": [
    {"id": "lys_0", "node": "ecs_lys_0", "patch": "lys_0_membrane", "owner": "cell_0",
     "role": "lumen", "label": "lysosome pool", "reference": null}
  ]
}
```

- `id`: the compartment's own stable ID, a string unique among every ID of the world, its node's
  included (the lead's ruling with D174, built in milestone 1: identity independent of storage).
- `node`: the compartment's @3 outside node, its storage today.
- `patch`: its bounding patch.
- `owner`: the owner's cell id. In version 1 this is the founder carrier, which never changes (§1.5).
- `role`: optional, a short string (1 to 40 characters), "lumen" by default when omitted; the
  identity map and the summary record whether it was declared. **No physics depends on the role in
  version 1:** it is metadata, carried to the map, the summary and later the run view.
- `label`: free text. `reference`: null or an opaque ontology reference, for example a Gene Ontology
  cellular-component term. Both are metadata only: they reach the summary and the run view, never an
  array. S2's guard applies: changing either changes no binding, program or trajectory. Generic laws
  stay generic, so a label never changes a law (the catalogue rule, D150 §1.5).

**Refusals at the definition,** each naming its reason:
1. **The node** is declared, is not a held bath, is not the gauge, and no face names it.
2. **The patch** is the only patch whose outside is the node, and its inside is the declared owner.
3. **One compartment per node.** An owner may own several.
4. **No ion route on the bounding patch (version 1).** Every permeability is zero, and there is no
   Na/K or Ca pump and no channel population on it. The refusal names the charged door (§3.4).
5. **Electroneutral content (version 1).** The node's charge anchor is 0, so V_b = 0. A declared
   resting potential needs charged content, which is FR-4's.
   - **Version 1.1** (the lead's ruling, 16 November 2026; §3.4.3): a nonzero anchor is admitted
     only where refusal 4 already admits charged routes, that is, the world declares kinds and
     steps with an IMEX tableau.
   - **Why:** a world whose admitted routes charge the lumen must be able to resume from its own
     checkpoint. FR-5 starts from FR-4's charged steady state.
   - **Still refused:** the no-kind world (the silent version, §3.3) and RK4.
6. **A held-bath topology (version 1).** The owner's capacitor component holds a held bath, so the
   compartment is a free node of the reduction (§3.5).
7. **The composition** is on the admitted list of §4, which fails closed. Replacement@1 schedules
   no event on an owner's slot, and names no owner as a donor (§1.5). Providers and closers of the
   volumes, the areas, the capacitances and the masks are refused through the declaration's own
   `CONFLICTS_VIEW`, by the composite's existing structure check (§1.6).

**Nested compartments are a topology limit.** A patch joins a cell to an outside node, so a
compartment cannot be bounded by another compartment. Multivesicular bodies and the two mitochondrial
membranes would need patches between two outside nodes, which @3 does not have. No version here
lifts that.

### 1.5 Identity: replacement, division and the lifecycle

**Today, outside nodes are environment.** The compartment's identity rules exist because three
things would otherwise treat it as extracellular space:
- **replacement@1 swaps cell rows only** (`operators/cell_replacement.py`; D150 §5.2's table).
  A newcomer would inherit the previous occupant's compartment content;
- **D152 admits outside routes beside replacement** (its ruling Q6). A reaction at the compartment
  would run on through the owner's replacement;
- **turnover's node clearance is keyed per node, not per carrier** (`species_common`: "outside-node
  routes are environment, not carriers"). A degradation rate would not follow the owner.

**Version 1's rules:**
- **Stable id:** the node id. **Owner:** the founder carrier of the owner's slot, which is the
  owner's carrier for the whole run, because version 1 refuses replacement and division of owners.
- **Rates of routes on the bounding patch** are the owner's: exchange keys cell-side routes by
  carrier (D150 §5.2). **Turnover at the node** is keyed per node. In version 1 the owner never
  changes, so the two keyings agree.
- **Replacement of an owner is refused.** Replacement of any other slot composes.
- **An owner as a donor is refused.** A donor copy takes the donor's cytosolic amounts only, so a
  copy of an owner would arrive without its compartments, and the newcomer would not be a copy.
  - D150's route-signature check would refuse such a copy too, since the owner's extra bounding
    patch changes its multiset of patches (`species_common.ion_route_signature`). But that check runs
    only when a D150 operator is declared, so the compartment's own check carries the rule.
- **Division is refused,** since the partition is a closer.

**The doors** (each needs its own design and qualification):

| Door | What it needs |
| --- | --- |
| R. Replacement of an owner, and an owner as a donor | The event also swaps each of the slot's compartments: the occupant's content leaves as waste, and the template declares the newcomer's (a donor copy copies the donor's into the newcomer's compartments), booked as replacement books the cell's rows. Node-keyed rates at a compartment re-key to the owner's carrier (D150's occupant rule) |
| D. Division of an owner | S5's "slots are storage": each daughter has pending compartment slots, a node and its bounding patch closed until the birth. At the birth the parent's compartment closes, and its content and anchors move to the daughters' as exact fractions (S5 §3.2's anchor rule), with declared fractions per compartment: 0 or 1 for an organelle that goes to one daughter, f for a pool. The adapter's entity hierarchy gains two rules: a closed cell closes its compartments, and a closed compartment closes its bounding patch. Stochastic partitioning of discrete organelles is out of scope |
| C. Creation | FR-2's internalisation opens a pending compartment slot at an event (§7) |
| F. Fusion and fission | A transfer between a compartment and another node across a fusion pore: exocytosis (FR-5) and endosome maturation (§7) |
| X. Retirement | With the owner's retirement, its compartments retire through the entity hierarchy of door D |

**Run view (D154).** The declaration's summary lists each compartment's id, its node's column, its
bounding patch's column, its owner's carrier and its label. A viewer can then draw it inside its
owner, not as extracellular space.

### 1.6 Where the declaration lives: one widened admission in the contract

**What the code admits today** (read, not run).
- `contract.check_declarations` (`operators/contract.py`, lines 336–342) refuses an operator
  with no part unless it has both `ACCEPTS_WRITES` and `VIEW_FIELDS`. Every registered operator
  passes through it at import (`operators/__init__.py`).
- `membrane_entity_state@1` is today's only part-less operator: of the registered operator classes in
  `models/operators/` at main's ced45c87, it alone declares no event, split or process part (a grep).
  Its three owned fields are exactly its three accepted writes, and it provides three view fields.
- So a declaration that owns nothing is refused today. A part-less site owner for FR-3, owning fields
  that later operators write but providing no view, would be refused too (FR-3's lead question 13).
- **The composite itself needs no change.** `Composition.__init__` builds its event, split,
  provider, factor and closer lists from the declarations (`models/pump_composite.py`). An operator
  in none of them contributes only the contract's idle defaults: no ledger term, no column and no
  domain term.

**The recommendation: one widened, host-only admission.**
- **The rule: the existing clause, or a new one.** An operator with no part is admitted when
  *either*:
  - (existing) it has `ACCEPTS_WRITES` and `VIEW_FIELDS`, exactly as today; *or*
  - (new) every field it owns is an accepted write (its `STATE_AXES` lie within its
    `ACCEPTS_WRITES`). One that owns no field at all may not provide views, factors or closures.
- **So it is a strict superset by construction.** Every operator that passes today passes the
  existing clause unchanged. The new clause's restriction on field-less operators cannot touch one
  that passes the existing clause, since an accepted write must be an owned field.
- **What the new clause admits:**
  - this declaration, which owns no field;
  - a part-less site owner for FR-3, **if** every field its owner holds is an accepted write. That
    condition is stated here without reading FR-3's note.
- **What it still refuses:** a part-less operator that owns a field no part and no writer can change,
  unless the existing clause admits it; and a stateless operator that would change the inner layout
  or controls without state.
- **D148 status.** It is an addition, not a change to existing behaviour. It is a check at
  registration, on the host. Every operator registered today is admitted as before, and no program,
  binding or number changes, so D148's four criteria hold trivially. Crossrev of every set stays
  identical, which the landing shows.
- **The declaration also uses `CONFLICTS_VIEW`** (the volumes, the area, the capacitance and the
  masks), so the composite's existing structure check refuses every provider and closer of them.
  The admitted list of §4 covers the rest.

**The alternative: a composite-level `compartments` block** beside `operators` in
`pump_composite_spec`.
- Its absence would leave every definition byte-identical.
- It is cleaner as "an entity, not a law". But it would be the composite's first entity table outside
  the operator list, the run identity would need a rule for it, and its later dynamic versions
  (volume as state, creation) would be operators anyway.

**Why the operator form.**
- Entity owners are operators today: `membrane_entity_state@1` owns populations, insertion owns onset
  nodes, and the partition owns daughters.
- Operators already find each other's declarations through `composite_spec.entries`. The lumen reads
  insertion's, and D150's operators read replacement's.
- The declaration grows into the compartment's entity owner when its volume becomes state (door V).

## 2. The transfer law

### 2.1 The lead's mapping holds: `scheduled_species_exchange@1`, unchanged

| Exchange@1 requires (`operators/species_exchange.py`) | A compartment |
| --- | --- |
| The patch's outside node is finite; a held bath is refused | Yes |
| Neutral species, with zero @3 permeability on every membrane, junction and channel | Yes: D150's inventory species |
| Cell-side rates keyed by the carrier | The owner's |
| The declared volumes and patch area (`CONFLICTS_VIEW`) | Fixed in version 1, with no provider |
| The species cap (7, rising to 16 under D165) | No new rows |

**The direction mapping.** The names are relative to the cell, and the laws are generic.

| Use | Exchange route | Rate | Exact half-step |
| --- | --- | --- | --- |
| Loading, constant | export, `flux` | J (fmol/s) from the cytosol | moved = J h, refused if the pool would not stay positive |
| Loading, constitutive | export, `first_order` | k_e n_cyt | moved = n_cyt (1 − e^{−k_e h}) |
| Release, constitutive (a driven route, booked as work) | import, `first_order` | k_u A c_comp, k_u in m/s | moved = n_comp (1 − e^{−κh}), κ = 10¹⁵ k_u A / V_comp |
| Release, carrier-mediated | import, `saturable` | A V_max c_comp / (K_M + c_comp) | D150's implicit closed form, with its Newton steps and residual check |

### 2.2 Retention, distinguishability and reconciliation

**Reconciliation.** In each exchange stage the cytosol's stored increment gains −moved and the
node's gains +moved: the same float, applied to stored increments, never as n′ − reference
(`species_exchange._stage`). `exchange_moved_fmol` accumulates each route's moves, and the ledger
terms scatter them to @3's local ledger at the owner and its outside ledger at the node, with
opposite signs; the total ledger gains nothing. So, to rounding,

    n_comp(t) − n_comp(0) = Σ over routes on its patch of moved
                            − turnover's clearance at the node
                            + D152's net production at the node,

which is @3's outside ledger at the node, and the cytosol's ledger holds the mirror image. That is
FR-1's "transfers reconcile on both sides".

**Distinguishability.** Retained and cytosolic material are one species row at two nodes. The
compartment's amount changes only through these bookings, so it never mixes with free cargo except
through a declared route.

**Retention.** With loading and no release, the compartment keeps everything it receives (Appendix
A.2). With release, the retained fraction follows the two-node closed form.

### 2.3 Three limits and two doors

1. **A pair can follow Fick's trajectory, but it stays driven, and it is split.**
   - Export at k_e = 10¹⁵ P A / V_cyt and import at k_u = P give the net flux
     J = 10¹⁵ P A (c_cyt − c_comp) fmol/s, the concentration trajectory of Fick's law across the
     patch (**S**). That does not make the pair a passive permeation (D174): each route still books
     its free-energy change as signed work, with no heat (item 2).
   - Exchange runs the pair as the palindrome E(h/2) I(h) E(h/2) (its stage order). With
     x = n_cyt / N, a = k_e and b = κ, the map's fixed point is x* = α(1 − β)/(1 − α²β), with
     α = e^{−ah/2} and β = e^{−bh}, against the equilibrium x_eq = b/(a + b). Then
     x*/x_eq − 1 = −a(a + 2b) h²/24 + O(h³) (**S**; checked numerically to ratio 0.99995–0.999999,
     `arithmetic/split_bias.out`).
   - The composite applies two halves of h = dt/2 per step, and both have that fixed point, so the
     relative bias x*/x_eq − 1 is −a(a + 2b) dt²/96 (**S**). At a = b = 1 s⁻¹ and 1 ms it is 3 × 10⁻⁸: negligible at
     physiological rates, and measured by acceptance C4.
   - Mismatched rates pump against the gradient, with that work booked too.
2. **Exchange is a driven route: a fall in free energy is booked as work, not heat.** Exchange
   books every route's exact ΔG as signed work, never heat (D150 §2.4; D174). The ledger closes,
   but the dissipation check sees no heat from it. A transfer that is physically a passive leak
   therefore needs door T1; exchange does not model it as one. It is a declared limit, as D150's
   laws' metabolic costs are.
3. **Saturable loading is refused.** Exchange refuses a saturable export, so a transporter that
   concentrates cargo into the compartment from the cytosol is not expressible.

**Door T1: a passive permeation law** (for FR-5's neutral leak, and for heat-correct passive
transfer). It is the law D174 expects in D172's round. It must show, in a fixed-volume case: zero
net flux at equal chemical potential, reversal when the driving force reverses, conserved material,
zero external work, and dissipation equal to the free-energy decrease.
- One route, both directions: J = 10¹⁵ P A (c_cyt − c_comp).
- Exact over a half-step as a two-node relaxation: N = n_cyt + n_comp is conserved,
  n_cyt* = N V_cyt / (V_cyt + V_comp), and n_cyt(h) = n_cyt* + (n_cyt − n_cyt*) e^{−λh} with
  λ = 10¹⁵ P A (1/V_cyt + 1/V_comp) (**S**).
- Its heat is H = −ΔG ≥ 0, in a declared heat field, as D152 books its passive routes.
- An open fraction enters through D156's rate route (§4). It would be a law of a new exchange
  version, since exchange@1's schema and qualification stay as they are.

**Door T2: saturable loading.** Exchange's saturable solve, applied to the cell side as source.

### 2.4 What is not the transfer law

- **@3's membrane permeability for a neutral species.** It is refused: @3's explicit-rate bound has
  no material term for neutral species on membranes (D150 §2.6; D152's finding 3 and probe C4; the
  queued D148 round). Exchange avoids that route entirely.
- **A face.** A compartment has none. A face is extracellular diffusion, and it carries ions, so it
  would make the compartment electrically active.

## 3. The electrical treatment

### 3.1 The compartment is a free node of @3's capacitor network

**The field law** (`numerics/surface_field.py`, a code reading).
- `bind` sums each active patch's capacitance between its cell and its outside node into the
  capacitor matrix.
- `solve` solves the capacitor rows at every free node. The Kirchhoff current balance fixes the
  floating offsets through faces and junctions only.
- The IMEX step makes face drift implicit, through the operator (C + a dt L). "Membranes, junctions,
  pumps, gates and face diffusion stay explicit" (`numerics/surface_imex.py`).

**For a compartment node j, owned by cell i, with one patch of capacitance C_b and no face (S):**
- Its capacitor row is C_b (φ_j − φ_i) = q_j. So the bounding patch's voltage, @3's inside minus
  outside, is

      V_b = φ_i − φ_j = −q_j / C_b,

  exactly, at every state. Here q_j = F (fixed_j + Σ_s z_s n_s,j), @3's node charge.
- **Gauss's law.** The owner's row is Σ_k C_k (φ_i − φ_k) + C_b (φ_i − φ_j) = q_i, which with row j
  becomes Σ_k C_k (φ_i − φ_k) = q_i + q_j. So the owner's plasma membrane sees the whole charge it
  encloses, organelle included.
- **Membership of the solves.** The node takes part in the capacitor solve and in the IMEX
  operator's C. It takes no part in the Kirchhoff offset solve or in L, since it has no face. It is
  never a held bath, a gauge or a representative (§3.5).

**The older family's precedent.** `er_calcium@1` derives its ER voltage from the ER's own mobile
charge on its own capacitor, V = V₀ + F × 10⁻¹⁵/C × Σ z Δn_ER, and reconciles its declared
inventories with immobile backgrounds of ±C V₀ ([ER_CALCIUM.md](ER_CALCIUM.md)). That is the same
relation. There it holds for one ER pair per world. Here it comes from @3's field, for any number of
compartments, with no new code.

### 3.2 The literature's organelle capacitor is this relation

Two standard organelle-pH models compute the lumen's potential exactly this way. The sentences,
equations and term definitions below were extracted from their open-access JATS XML (`sources/`).
- **Grabe & Oster (2001), Eq. 3:** "We assume that the net charge localizes to the lumenal leaflet,
  so that we can treat the membrane as a parallel plate capacitor." In their notation,
  Δψ = (F/C₀)(V/A)[Σ ν_i [cations]_i − Σ ν_i [anions]_i + β (pH_C − pH_L) − B], where "C₀ is the
  capacitance per unit area of the membrane (C₀ · A is the total capacitance of the membrane)". Its
  second term is the "Total amount of buffered and free protons in the lumen", and B the "Molar
  concentration of all impermeant charges".
- **Ishida et al. (2013), Eq. 4:** "Our model incorporates a physical model of the membrane
  potential (Rybak et al., 1997), which depends on the net accumulation of charged ions in the lumen
  of the compartment", with ΔΨ = F/(C₀ S) [V (Σ n_i [cation] − Σ n_j [anion] + β (pH_C − pH_L))
  − B V₀]. "B is the luminal concentration of impermeant charges, which are primarily fixed negative
  protein charges trapped in the lumen", and "By convention, the membrane potential is negative
  when there are more negatively charged ions inside the compartment relative to outside."
- Both cite Rybak et al. (1997) for the form; it was not read here.

**How the terms map (S):**

| Their term | @3 at the compartment node |
| --- | --- |
| C₀ A (or C₀ S) | The bounding patch's `capacitance_F`, C_b |
| V Σ z c, the mobile charge | Σ_s z_s n_s, every species row at the node |
| B V₀, the impermeant charge | `fixed_charge_equivalent_fmol`, the node's Donnan background |
| β (pH_C − pH_L) V, the buffer's bound protons | The charge of a protonated buffer species, a row with its valence (FR-4's buffering, D152's charged closed-reaction door) |
| Their ΔΨ, lumen relative to cytosol | −V_b. **@3's patch voltage is cytosol minus lumen**, the opposite sign; the run view names it |
| Ishida et al.'s leaflet surface potentials | Not modelled in @3: a declared limit for FR-4 |

Grabe & Oster also note that, for a given excess concentration, the potential "is proportional to
the ratio of the volume to the surface area". A lumped pool of identical organelles keeps that ratio,
which is why lumping is exact here (§1.3).

### 3.3 The neutral first version is electrically silent

**Conditions** (refusals 4 to 6 of §1.4):
- the bounding patch has zero permeability for every species, no pump and no channel;
- the content is electroneutral: the charge anchor is 0;
- nothing else can charge the node. It has no face. Injection targets cells only
  (`current_injection.py`). Exchange, turnover and reactions move neutral species only.

**The silent version is the world without kinds,** and every condition above still holds there.
Refusal 4 version 1.1 (§3.4.1) admits charged routes on the bounding patch in a world that
declares kinds and steps with an IMEX tableau, and refusal 5 version 1.1 (§3.4.3) admits a
nonzero charge anchor in the same worlds only. A world whose admitted routes charge the lumen
must be able to resume from its own checkpoint. Such a world is no longer silent, and claims
S1–S3 are not made for it. Without kinds, or under RK4, the anchor stays 0 and the claims stand
as written.

**The silence claims are pending milestone 1.** None has been run. Each criterion below is written
before any run, as the coupling note's channel target was, and none is weakened afterwards. Their
basis is the code reading of §3.1 (**S**).

| Claim | Kind | Criterion, fixed now |
| --- | --- | --- |
| S1. The compartment's ion rows never change | Promised, bitwise | At every accepted row, every ion row of the node's `extracellular_amount_increment` equals its initial value bitwise: in scalar, windowed, vector-window and batch runs, and across a restart through a snapshot. The reason: no route with a nonzero coefficient touches them; the constant-field flux at zero permeability is zero; no face or drift reaches the node |
| S2. V_b stays at −q/C_b = 0 | Promised, to @3's charge tolerance | At every accepted row, the node's row holds within @3's own charge tolerance, so \|V_b\| ≤ (CHARGE_ATOL_C + CHARGE_RTOL · max(\|q_comp\|, \|C_b V_b\|)) / C_b, with q_comp = 0 exactly (`surface_field.CHARGE_ATOL_C` = 3e-25 C, `CHARGE_RTOL` = 2e-12). Every accepted solve already enforces this tolerance on the node's row. A tighter bound in ulps of the potentials is not promised: a backward-stable solve can leave a residual on the node's row that scales with the largest capacitance, so for a small C_b, V_b's rounding may lie well above ε \|φ\| |
| S3. No capacitor energy flows through the patch | Promised, to @3's charge tolerance | ½ C_b V_b² ≤ ½ (CHARGE_ATOL_C + CHARGE_RTOL · \|C_b V_b\|)² / C_b at every row (S2's consequence) |
| S4. The rest of the world against the same world without the node and its patch | Reported, not promised | The largest difference of every other field over the run, in ulps of the field. There is no pass rule |
| S5. The declaration is pure identity | Promised, exact | The same world with and without the declaration traces to identical program text and constants: the jaxpr text of the checked step, the right-hand side and the device row checks, with scalar constants as literals; the dtype, shape and SHA-256 of every closed-over array; and the bindings (D148's "what crossrev compares"). The reason: the declaration runs no part |

**Why S4 is reported only.**
- In exact arithmetic the potentials are identical: row j gives φ_j = φ_i, so the owner's row reduces
  to the compartment-free one (**S**).
- But the dense capacitor and IMEX operators gain a row, and their factorisations round
  differently. This is D150's claim-3 situation: reported, with the reduce order program-specific.

**Composes without disturbing it:** injection into the owner moves the owner's potential and the
compartment's together. The compartment's row is unchanged, so V_b stays exact (**S**).

### 3.4 Why ion routes on the bounding patch are refused: the charged door

**An unrun reading.** Everything in this section is arithmetic on a code reading (**S**). Probe P1
(§9), with its criterion written in C4's form, would measure it. The bound term it points to is one
D148 round with finding 3's, not yet specified. None of this blocks version 1, which refuses the ion
routes.

**The code reading (S).**
- @3's definition-time bound (`surface_pump.explicit_rate_bound`) and its run-time stage rule
  (`surface_pump_v3.membrane_rate`) both bound membrane charge relaxation per **cell**:
  max_i Σ_m G_m / C_i, with C_i the cell's total patch capacitance. The bound's docstring says why
  that suffices for plasma membranes: "the outside is held near equipotential by the implicit
  drift".
- A face-free node has no face drift. Its charge relaxes through its patch alone, explicitly, with
  the fast mode's rate about G_b (1/C_b + 1/C_i) ≈ G_b / C_b for C_b ≪ C_i.

**The size of it (S; `arithmetic/`).** With the specific capacitance c_m, G_b/C_b = P F² c/(RT c_m),
independent of the compartment's size. Here c is the larger of the two sides' concentrations, as
@3's slope bound takes it. With Ishida et al.'s Table 1 values (C₀ = 1 µF/cm², 310 K):

| Counterion route | P | c (the larger side) | G_b/C_b | dt × rate at 1 ms |
| --- | --- | --- | --- | --- |
| Cl⁻ | 1.2 × 10⁻⁵ cm/s | 110 mM (lumen) | 4.8 × 10³ s⁻¹ | 4.8 |
| Na⁺ | 9.6 × 10⁻⁷ cm/s | 145 mM (lumen) | 5.0 × 10² s⁻¹ | 0.50 |
| K⁺ | 7.1 × 10⁻⁷ cm/s | 145 mM (cytosol) | 3.7 × 10² s⁻¹ | 0.37 |
| H⁺ | 6 × 10⁻⁵ cm/s | 1 × 10⁻² mM (pH 5) | 2.2 s⁻¹ | 0.002 |

The text extraction drops the superscript minus signs of the table's exponents; they are restored
here, and the table's volume and area agree with a 0.68 µm sphere.
- For the chloride route, @3's per-cell bound sees G_b/(10 pF + C_b) ≈ 6.9 s⁻¹ for a 10 pF owner.
- @3's rule is dt × rate ≤ `EXPLICIT_STEP_BOUND` = 1.0, "half the Euler/RK2 real-axis limit of 2"
  (`models/surface_pump.py`), at the definition and at every IMEX stage.
- So at 1 ms a realistic lysosomal chloride conductance has dt × rate ≈ 4.8: beyond the rule, and
  beyond the explicit part's real-axis stability limit of 2. @3's checks, seeing about 0.007, would
  not refuse it in advance. At best a step fails its domain afterwards. Probe P1 would show which
  happens.

**No existing world on @3's IMEX numerics is exposed** (the lead's sweep; read-only, 14 November;
`sweep/` in the evidence folder).
- **The JSON sweep** (`face_free_sweep.py`, the walk of D152's sweep, static): 99 model blocks in
  configs/, validation/ and tests/, the same at main's ced45c87 and on this branch. Ten finite
  outside nodes that no face names each have an ion route on their facing patch (`gauge_check.out`):
  - **seven are the gauge of a closed one-node world,** a fixed node, so the per-cell bound covers
    the cell against it. Six are older families, RK4 only (resolved_cotransport@1, its water
    version, resolved_energy@1, its water version, resolved_water@1 and @2). One is on @3's IMEX
    numerics: `validation/tissue/pump_water_predictions.json`'s P5, resolved_pump_water@1 under
    ARS(2,2,2), whose node `bath_0` is its gauge;
  - **three are free face-free nodes with a chloride route,** the compartment's own topology:
    resolved_redistribution@1, @2 and @3's configs (node `finite`, beside a held bath). They are an
    older family, RK4 only, with a fixed step limit of 0.1 ms (`surface_tissue.check_steps`), off
    @3's IMEX bound.
- **The candidates the lead named:** the S3 and S5 lumens have access faces (`access` in
  `validation/division/cleft_egg_engine.py`; the clefts' faces in `egg_division_world.py` and
  `tests/partition_fixtures.py`). D150's and D152's face-free worlds have no ion permeability on
  their contact patch.
- So the gap is latent on @3's numerics: it would apply to a future definition with an ion route on
  a free face-free node, which version 1 refuses.

**The door, for FR-4 and FR-5.**
1. **The bound sees face-free nodes.** Its shape, to be specified in that D148 round after P1: a term
   max over free face-free finite nodes of Σ_m G_m / C_node in `explicit_rate_bound` and
   `membrane_rate`, statically gated, so a world with no such node carrying an ion route is
   unchanged.
   - It touches the same two functions as the queued D148 round for neutral species on membranes and
     junctions (finding 3, probe C4), so the two are one round (the lead's ruling).
   - It makes the steps honest, but the chloride route above would then need dt ≤ 1/(4.8 × 10³ s⁻¹),
     about 0.2 ms (**S**).
2. **An implicit treatment.** The bounding patch's electrodiffusion joins the implicit part of the
   IMEX step, as face drift does. That is a new IMEX ID (D147: a change to a solver's iterations is a
   new ID), with its own qualification. FR-5's pores, with permeabilities orders of magnitude above
   these, need it.
- **The recommendation:** (1) as the safety net when any ion route is admitted on a bounding patch,
  and (2) decided by FR-4's design note, which owns the first charged compartment.

**Also on the charged path, re-argued there:**
- `capacitor_change`'s exactness conditions (valences of magnitude 0, 1, 2, 4 or 8) and the
  electrode ledger's telescoping. A compartment is a free node coupled to one cell, so no held node
  gains a coupling (**S**).
- D150 §3's exact-zero argument, rewritten for charged species.

### 3.4.1 Version 1.1: refusal 4 for the admitted kinds (FR-4; the lead's ruling, 16 November 2026)

**Why now.** FR-4's declared world puts its charged routes on the bounding patch: the proton pump
(cells.transporter@1), the proton leak (cells.passive_routes@1) and the K⁺ counterion (@3's
constant-field permeability), with B4's closure (cells.rapid_proton_buffer@1) buffering the lumen.
Door (1) above now exists: B7's definition-time bound holds every free face-free node against its
own patches (`surface_pump.face_free_node_rate`), and, when a world declares kinds, the per-stage
rule does too (`surface_pump_v3.membrane_rate` with `free_outside_nodes`, core-d172 2c780f9f), with
each kind's slope at both ends of its patch (`stage_term` per node). Version 1 still refused every
ion route on a bounding patch, and it saw no kind at all, so a kind's route there passed unchecked:
it failed open.

**The rule (refusal 4, version 1.1).** For each declared compartment's bounding patch:
- **@3's own routes:** a Na/K or Ca pump, or a channel population, stays refused: the per-stage
  rule does not hold its slope at the compartment's node (a pump's slope is in no per-stage term,
  a channel's gating slope neither), and the refusal's message says so. A constant-field
  permeability is admitted **only when the world declares kinds**, because only then does the
  per-stage rule hold the compartment's node; without kinds it stays refused, as in version 1.
- **The kinds a world declares:** the known ones are admitted, each held as follows (wording
  corrected after the core's review, 16 November 2026).
  - **Charged routes, per stage.** cells.transporter@1's proton law and cells.passive_routes@1's
    proton leak put their slopes at both ends of their patch through `stage_term`, so the
    per-stage rule holds the compartment's node against them at every explicit stage. The proton
    law also has a definition-time term (`bound_rate`, its slope bounded at saturation over the
    node's capacitance); the leak has none and is held per stage only.
  - **The passive neutral law, at the definition.** It moves no charge. Its definition-time
    `bound_rate`, dt·L ≤ 1 with L = P·A·(1/V_a + 1/V_b), holds its material relaxation, the
    compartment's own small volume included.
  - **The transporter's neutral law: open.** It has neither term, so nothing bounds its material
    stiffness at a small node: near its static head its flux depends on the compartment's own
    concentration. That is a material question, like finding 3's neutral-species term (the
    inner-model note's §13.6), not the charged door's, and it is recorded here as open. It needs a
    measurement or a bound term before a fast neutral population sits on a bounding patch.
  - cells.rapid_proton_buffer@1 is a stage read and declares no route.
  - **Any other kind is refused** while a compartment is declared: the operator cannot know
    whether its routes cross the bounding patch (D180's external kinds), so it fails closed, as
    §4's admitted list does for operators.
- **Only with an IMEX tableau** (the core's review of version 1.1, 16 November 2026; the lead's
  ruling). Both holds above belong to @3's IMEX step: the per-stage rule runs in `imex_step` only,
  and @3's step checks hold B7's term and the kinds' `bound_rate` for the IMEX solvers only
  (`surface_pump_v3.StepChecks`). An RK4 step (an empty tableau) runs neither and keeps only its
  0.1 ms cap. The review's probe showed the gap: FR-4's declared world under RK4 at 0.1 ms, with
  its K⁺ permeability scaled 10⁴ times (the lumen's row at 2.5 × 10⁵ s⁻¹, dt × rate = 25, far past
  RK4's real-axis limit of about 2.8), was admitted and passed its step checks, while the same
  world under IMEX is refused by the explicit-rate bound. So under RK4 refusal 4 admits **no
  declared kind** beside a compartment, and a permeability stays refused as in version 1: version
  1's refusal stands (fails closed). @3 itself now refuses declared kinds under RK4 for the same
  reason, whether or not a compartment is declared (`surface_pump_v3._check_kinds_solver`; the
  core's review, finding 6), so in a parsed world @3's refusal comes first and refusal 4's RK4
  rule stands behind it until a design for kinds under RK4 lifts both.
- Refusals 1–3 and 5–7 are unchanged. Refusal 5 (no charge anchor) still holds the content
  electroneutral at the start; FR-4's world declares none.

**What it adds.** Identity and refusals only, as before. The operator still owns no state, runs no
part and contributes nothing to any program, so FR-4's declared world (with the operator) must run
bitwise equal to its development world (without it). FR-4's lane checks that on the vector path:
a 20 s pass first, then 900 s.

**Tests.** An admitted kind on the bounding patch is accepted (FR-4's declared world, in the
composite's form). An unknown planted kind is refused. Refusal 4's other cases are unchanged,
including a permeability in a world without kinds. The review's probe is a test: FR-4's declared
world with the stiff K⁺ permeability is refused under RK4 and admitted under IMEX, where the
explicit-rate bound then refuses its step, as before.

### 3.4.2 Version 1.2: the routing door's source kinds (FR-5; the lead's ruling, 16 November 2026)

**Why.** FR-5's declared world adds two kinds beside the compartment: the bounding patch's damage
(cells.patch_damage@1) and the lumen's pH condition (cells.ph_condition@1), the routing door's
sources (the FR-4/FR-5 note's §16). Version 1.1 knows neither, so it refuses that world.

**The rule.** Version 1.2 adds `FACTOR_KINDS`, the source kinds, to the known kinds:
- **What admits them:** they declare no route, move no row and carry no charge. They have no
  `moved_rows`, `stage_term`, `bound_rate`, `held_rows`, stage read, stage check or ledger term.
  The damage's `rates` holds its own state's derivatives only, with zero node rates.
- **How their factors act:** they reach a route only through the door, as its rate multiplier in
  [0, 1], on a known route kind's route. That route's slope at full opening is what the per-stage
  rule and its definition-time term already hold.
- **What stays:** every version 1.1 rule. Any other kind is refused (fails closed), and under RK4
  no declared kind is admitted, the source kinds included.

**Tests.** FR-4's declared world with FR-5's two source kinds is admitted. A world declaring only
the source kinds is refused under RK4 by the operator's own rule. The source kinds' registrations
carry none of the hooks their admission excludes, and the engine runs them beside FR-4's world
with every FR-4 record bitwise unchanged (`tests/unit/test_fr5_source_kinds_engine.py`).

**The summary's scope text** changed with this version, from "version 1.1: ..." to "version
1.2: ...". Frozen operator summaries see that string differ.

### 3.4.3 Refusal 5 version 1.1: the charge anchor where charged routes are admitted (FR-5; the lead's ruling, 16 November 2026)

**Why.** FR-5 starts from FR-4's engine checkpoint at 1800 s, its steady state.
- There the pump has charged the bounding patch. The lumen carries +5.757e-14 C and the cell
  −5.757e-14 C, so V_b = −q/C_b = −7.33 mV, exactly the checkpoint's own V_b.
- FR-5's definition takes each node's charge from the checkpoint as its anchor, with the fixed
  charge following from it. So its declared world is refused by refusal 5, version 1's
  electroneutral content.
- Neutralizing the start would put V_b at 0, which is not the checkpoint the protocol requires.
- **The principle:** a world whose admitted routes charge the lumen must be able to resume from its
  own checkpoint.

**The rule (refusal 5, version 1.1).** A nonzero charge anchor at a compartment's node is admitted
only where refusal 4 already admits charged routes on its bounding patch:
- the world declares kinds;
- @3 steps with an IMEX tableau.

**What stays refused** (fails closed):
- a nonzero anchor in a world without kinds: the silent version, §3.3, whose claims S1–S3 depend
  on it;
- any declared kind under RK4. Version 1's refusal stands there, as refusal 4's RK4 rule does.

**What it does not change.**
- The operator still owns no state, runs no part and contributes nothing to any program. The
  anchor is a host-side check at binding, so no program changes.
- @3's own definition check still holds the anchor to F (fixed + Σ z n) within 1e-20 C
  (`surface_tissue.check_definition`). At a face-free free node V_b = −q/C_b exactly (§3.1), for
  any q.
- Refusals 1–4, 6 and 7 are unchanged.

**The summary's scope text** changes again, beside version 1.2's change above, from "version 1.2:
a zero charge anchor and ..." to the text naming refusal 5 version 1.1. Frozen operator summaries
see that string differ.

**Tests** (`tests/unit/test_cell_owned_compartments.py`):
- FR-5's declared world from a charged start is admitted;
- a world without kinds with a nonzero anchor is still refused;
- under RK4 the operator's own rule still refuses the anchor;
- the planted 1e-17 C control of the silence claims still fails
  (`tests/unit/test_cell_owned_compartments_silence.py`, through its bypass).

**Then the protocol's check:** FR-5's declared world must run bitwise equal to its development
world, as FR-4's did (§3.4.1).

### 3.4.4 Version 1.3: refusal 4 per move (CORE_SEAMS_DESIGN §4.4; the lead's ruling, 18 November 2026)

**Why.** Versions 1.1 and 1.2 admit kinds by ID, so coverage is judged per kind, but it is needed
per law: the transporter has a `stage_term`, yet its neutral law has no term of any kind (§3.4.1's
open item). Every new kind also meant an edit to the lists.

**The rule.** @3's own routes keep version 1.2's rule and its messages: pumps and channel
populations are refused on a bounding patch, a permeability is admitted only where the world
declares kinds, and under RK4 no declared kind is admitted. With an IMEX tableau, each declared
kind is checked per move:
- **Every row a kind moves at the compartment's node,** as its `moved_rows` gives them, needs a step
  term. A move across the bounding patch moves its row there, at the patch's outside end.
  - A charged row needs a charge slope, `stage_term`, which the per-stage rule holds at the node.
  - A neutral row needs a material slope, `material_term`, or a definition-time material bound,
    `material_bound`.
  - A charge bound, `charge_bound`, holds neither: it bounds the declared state only.
- **The term is read by law ID from the law registry.** The law declares it on the law template,
  and the kind that hosts the law must have the hook that supplies it: `stage_term` and
  `material_term` by those names, both bounds through `bound_rate`. So a planted kind that reuses a
  law's ID, as FR-4's K2 does, is admitted only where it keeps the hooks the law names.
- **Fails closed.** A move is refused, naming its law, when the law declares no needed term, when
  its kind lacks the hook, when the move names no law, when the law is unregistered, or when
  another kind hosts it.
- **The kind is read bound to its declaration's structure entry** (the adapter's `bound_kind`), as
  the inner model binds it, never as the static kind, which may differ per entry: a static read
  could admit what the bound kind refuses (the bound-kind sweep, 19 November 2026; planted in the
  test by a bound kind that loses its `stage_term`).
- **A kind with no moved rows** is admitted by its hooks, never its ID:
  - as a stage read, which declares its rows and has no `rates`, `stage_term`, `material_term` or
    `bound_rate` (B4's buffer);
  - or as a source, with none of a mover's hooks (§3.4.2's list, which `material_term` joins: FR-5's
    damage and pH condition).

**What changes.**
- `ROUTE_KINDS`, `READ_KINDS` and `FACTOR_KINDS` go. A new kind or law joins by declaring its
  terms, with no edit here.
- **Newly refused:** the transporter's neutral law at a compartment's node, until it declares D4's
  material term. No world on main has it (CORE_SEAMS_STEP0 §3, redone call by call for this
  version).
- **Newly admitted:** a kind none of whose moves is at a compartment's node, whatever its ID.
- **What it needs** (CORE_SEAMS §18 as amended), on main since seam F's landing (8c2cb523, merged
  at 599b8610): the law template's step terms (`registry/laws.STEP_TERMS`), that is `stage_term`,
  `material_term`, `charge_bound` and `material_bound` on the cycle and route law types, and the
  passive routes' two laws declaring theirs (the leak a `stage_term`, the neutral law a
  `material_bound`). Without them, FR-4's and FR-5's declared worlds would be refused; the premise
  test fails if a declaration goes or the template gains a term refusal 4 does not map.
- **Text.** The summary's scope string changes to version 1.3. No judged record holds it. Frozen
  operator summaries see it differ. The unchanged branches keep version 1.2's messages, since FR-1's
  judged refusal record holds the permeability one.

**Tests** (`tests/unit/test_cell_owned_compartments.py`):
- FR-4's and FR-5's declared worlds are admitted, with their moves at the lumen and their terms;
- planted moves at the node, charged and neutral, each refused case beside its admitted twin;
- a move with no law, an unregistered law, a law another kind hosts, and K2's reuse of a law ID;
- non-movers judged by their hooks;
- the transporter's neutral law, refused on the bounding patch and admitted on the plasma patch;
- the built-in laws' declared terms against their kinds' hooks: the premise.

### 3.4.5 Refusal 5 version 1.2: the anchor where an admitted operator's routes charge the compartment (FR-2; the lead's rulings, 19 November 2026)

**Why.** FR-2's retrieval follows the membrane's charge (R2,
[retrieval design](MEMBRANE_RETRIEVAL_DESIGN.md) §6), so the pool takes the charge of the membrane
it receives. Within one run that charge sits in @3's increments over a zero anchor. A checkpoint
imported as a new definition (D153's rule (b)) carries it as the pool's anchor, which version 1.1
refuses in a world without kinds.

**The rule.** A nonzero anchor is admitted where the world's admitted routes charge the
compartment:
- version 1.1's branch, unchanged: the world declares kinds and steps with an IMEX tableau;
- version 1.2's branch: an operator on the admitted list declares that its routes move charge into
  that compartment, through the contract's host-side hook `charged_compartments(spec,
  declaration)` (compartment IDs; default none), so the declaration never imports the operator.
  `scheduled_membrane_trafficking@1` declares its routes' pools. The branch holds whatever the
  solver: the pool keeps no conductance of its own, so V_b = -q/C_b exactly (§3.1).
- **Fails closed:** an anchor on a compartment that no route enters stays refused, per compartment,
  and so does a hook that names an ID the declaration does not declare.

**Where it is checked: at the definition** (`check_definition`, after refusal 7's admitted list),
since parse sees only the declaration's own block.
- The composite prefixes a definition-check refusal with "Invalid composite definition: ". So a
  re-run of FR-1's R5 world reports that prefix before version 1.1's message. The message is kept
  byte for byte wherever no operator charges a compartment, and FR-1's `classify()` still puts it
  in its judged class (tested). FR-1's frozen judged run (run-05a8d193) and its rehearsals are
  unchanged.
- Refusal 5 now follows refusal 6 in a world with both faults. FR-1's judged worlds each carry one.
- Where an operator charges some compartment but not this one, the message names it.

**Text.** The summary's scope string names version 1.2 in every compartment world, as version 1.3's
did (the lead's ruling (a)). No saved result holds it.

**Tests** (`tests/unit/test_cell_owned_compartments.py`):
- two compartments of one owner, with a route into one, through a stand-in for FR-2's operator
  until its module lands: the anchor admitted on the routed one and refused on the other
  (planted), and a route into an undeclared ID refused;
- the rule at each solver and with kinds, and version 1.1's words where nothing charges;
- FR-1's R5 world through its protocol's own `refusal_pairs()` and `classify()`.

### 3.5 Floating components and the gauge

- **Version 1 requires a held-bath topology** (refusal 6). The owner's capacitor component holds a
  held bath, as every qualification world so far does and as S5 requires of its worlds. In such a
  component no representative is chosen, so the compartment is a free node.
- **With finite extracellular space and floating components** (D147's free offsets), `bind` takes
  the gauge node, or else the component's lowest-index outside node, as its representative. That
  could be the compartment. The physics would be unchanged if the component's net charge were
  exactly zero, but the compartment's row would then carry the component's net-charge residual.
- **The door:** refuse a compartment that would be a representative (`field_fixed` at its node, read
  from the bound layout), with an acceptance item on a floating world. Probe P3.
- **The gauge** is never a compartment: refusal 1.
- **The D147 record** (the lead's item 4; part A of FR-10's probe 1, a host-side definition parse of
  `field_solver_choice.free_field_offsets`, from the clean snapshot of main): **0** for the
  species-only compartment world and **0** for the mixed one. A held-bath topology has no free offset,
  so they keep field solver version 2, as D150's arms and MG0c's did.

### 3.6 The field-input node cap, node cost and the species budget

- **The 64-node cap is untouched in version 1.** It binds only when an operator provides a
  capacitance or a mask (`pump_composite_adapter.FIELD_INPUT_NODE_CAP`, `check_field_inputs`). A
  compartment provides neither.
- **Each compartment is one padded field node.**
  - It always counts against the dense solver's node bound: 256 for version 1 of the field solver,
    2,048 for versions 2 and 3.
  - It counts against 64 once a field-input provider composes. Membrane state (FR-3's site owner)
    and insertion or retrieval (FR-2) are such providers. With one compartment per cell, a 64-node
    world holds about half as many cells (**S**).
- **Cost (S).** The IMEX operator (C + a dt L) is refactorised every step, at O(N³) in the node
  count N. The measured one-core costs are 1.7 ms per step at 14 field nodes, 7.7 ms at 254 and
  76 ms at 825 (v2 §3). A compartment per cell in a 127-cell sheet would take it from about 254 to
  381 nodes. A face-free node with one patch couples only to its owner, so it could be condensed
  exactly out of the dense solve. That would be a new solver ID (D147), when a tissue of compartments
  needs it.
- **FR-9's budget.** Compartments add nodes, never species rows. The requester's species count is
  unaffected by FR-1.

## 4. Composition

| With | Version 1 | Why, and the door |
| --- | --- | --- |
| @3; `electrode_current_injection@1` | Composes | Injection targets cells; V_b stays exact (§3.3) |
| `scheduled_species_exchange@1` | Composes: the transfer law | Its routes on the bounding patch are §2's. Its routes on the plasma membrane carry the uptake path's other leg. It reads the patch areas current (D191; the lead's ruling of 20 November 2026), so it also composes beside membrane state, declared after membrane state and after the unit producer; where no writer changes an area, it reads the declared area bit for bit |
| `scheduled_species_turnover@1` | Composes | Clearance at the node is degradation (a lysosome). Production at a node is refused by turnover; D152's source reactions provide it |
| `local_species_reactions@1` (D152) | Composes | Reactions at the node: the face-free network world's precedent. D152's own refusals hold. Its rule Q6 does not arise, since owners are never replaced |
| `species_regulated_availability@1` (D156) | Composes | Its sources are cell rows and its targets plasma-membrane elements. A channel target on the bounding patch cannot arise, since channels are refused there |
| `species_regulated_availability@2` (B1′) | Composes (20 November 2026) | As @1, and its operator targets' elements are cell-side: it reads a source in its element's cell and refuses an outside-node element |
| `population_unit_turnover@1` (FR-7) | Composes, after membrane state (20 November 2026) | It acts in its populations' cells only and writes membrane state's units, never an area or a capacitance. FR-7's U2 world with a releasing compartment (D217) |
| `templated_polymerisation@1` (FR-49) | Composes, for routes in cells (D327) | Its own check refuses an export into a compartment's node and an outside degradation there (`templated_polymerisation.check_compartments`). An export into a compartment is a later step, with its books at the compartment's node. Qualified by `fr49-compartment-compositions-v1`'s World L (silence at the compartment) |
| `neutral_arrival_labels@1` (FR-49) | Composes, without membrane state (D327) | Refused here beside membrane state (ruling 4), before the membrane-state wall's rule. Labels follow exchange, turnover, D152 and the kinds' routes across a bounding patch, as everywhere. Qualified by World L |
| `scheduled_compartment_wash@1`; `site_occupant_replacement@1` | Refused (the list) | The wash: FR-49's narrowing, a wash of another node, follows FR-44 (D327), and a compartment's node is never washed. `site_occupant_replacement@1` stays off the list (FR-49's ruling 7) |
| `scheduled_cell_replacement@1` | Composes away from owners | Events on an owner's slot are refused (§1.5); door R |
| `scheduled_bath_composition@1` (FR-10) | Composes, but not beside D152 | It acts on held baths only ([its note](BATH_SCHEDULE_DESIGN.md)). D152 lists the field that the bath schedule provides in its `CONFLICTS_VIEW`, so a dose world with reactions anywhere is refused. The conflict is nominal, at the field level only: see below |
| Water, the k-anion symport, replacement@2 | Refused | Volume: door V (§5.3). The symport and replacement@2 require water |
| `membrane_entity_state@1` | Composes only together with FR-2's trafficking or FR-7's unit producer: **the membrane-state wall's door** (19 November 2026, amended 20 November 2026) | Membrane state provides the patches' area and capacitance, so it is a field-input provider (§3.6): the 64-node cap and the held-bath topology apply. The declaration reads the areas and capacitances as `reference` reads (D217): its identity checks take the declared bounding patch as data, so a provider of them is no conflict. Membrane state is admitted only beside `scheduled_membrane_trafficking@1`, which writes areas, capacitances and units, or `population_unit_turnover@1`, which writes units only, and only where every writer of its fields is one of them; alone, or for FR-3's sites, the wall stands |
| `scheduled_membrane_trafficking@1` (FR-2) | Composes, after membrane state and this declaration | Retrieval into a compartment's pool and recycling from it, the charges following the patches ([retrieval design](MEMBRANE_RETRIEVAL_DESIGN.md), D217). It changes a bounding patch's area and capacitance, not its identity: V_b = -q/C_b holds at the current C_b (§3.1). Named on the list before its module lands |
| Insertion@1 and @2 | Refused | Field-input providers; exchange also refuses them, through the masks they provide. FR-2's door (§7) |
| `site_occupancy@1` (FR-3) | Refused: the list fails closed | **Door:** admitted by a host-only, one-line addition when FR-3's operator exists, on two conditions: binding and release only on a bounding patch's outward-facing populations, which face the lumen; and refusal of internalisation from a compartment-facing patch, read from this declaration. **That line is not sufficient alone** if the sites move to membrane state, their owner in FR-3's note: the wall's door admits membrane state only beside trafficking. **FR-49's site pairing** (D327) takes this door after FR-45: outward populations on a bounding patch and populations owned by the compartment's node admitted, inward ones refused, qualified by World B |
| The partition; the bridge | Refused | Closers; door D |
| The restricted lumens | Refused | They require insertion; a compartment is not a lumen's onset node |
| The stationary analysis | Refused | It does not admit the composite (D150 ruling 2) |
| RK4 | As each operator rules | D150 guards it, D152 refuses it; the declaration adds nothing |
| Any operator not listed | Refused | The admitted list fails closed: a new operator may treat outside nodes as environment |

**The requester's natural first world meets a wall.** A bath dose, uptake into the cytosol,
loading into a compartment and reactions inside would combine FR-10's bath schedule with D152. D152
reads `extracellular_amount_reference` as declared, and the bath schedule provides it, so the
composition is refused, although the two act on disjoint nodes.
- **The conflict is nominal** (read, not run). Everywhere D152 reads the field it masks held baths:
  `node_amounts` and `reactions_domain_valid` take finite nodes only (`outside_active & ~reservoir`,
  `species_reactions.py`), and D152 refuses held-bath sites. Its `CONFLICTS_VIEW` entry is there for
  insertion@1, which changes finite onset nodes' anchors: that conflict is real.
- **Version 1's workarounds:** degradation inside by turnover's clearance at the node instead of
  reactions; or a pre-loaded extracellular node instead of a bath dose.
- **The door** is FR-10's door S, slot-scoped provision ([its note](BATH_SCHEDULE_DESIGN.md) §3). It
  gates this world, so its priority comes before FR-4's.

**The coupling operator's doors for compartments (D156; §7's FR-5 row).**
- **A compartment source.** The coupling reads a concentration in the target's own cell. Reading
  the target cell's own compartment keeps that locality, through the ownership relation. A
  compartment's neutral rows are not moved by @3's step: no face, impermeant. So an instantaneous
  factor on them is exact under the held evaluation, as for cell rows (coupling §1.4; **S**). Ion rows
  of a charged compartment enter only through a regulatory state (coupling ruling 1).
- **The rate route** (coupling §2.1) already lists D150's "secretion and uptake rates" as routable
  controls. A factor on the bounding patch's exchange route is FR-5's state-conditioned transfer.

## 5. Accounting

### 5.1 Material in one ledger

- The compartment's amounts are @3's outside rows at its node. @3's per-species local, outside and
  total ledgers cover them, with the species-scale floor (D150 §1.3).
- Every writer books in its own accumulators: exchange's moves with opposite signs at owner and node,
  turnover's clearance at the node, and D152's production and consumption at the node. @3's ledgers
  close with their sum (v2 §1.3, "fluxes add").
- The retained amount of §2.2 is therefore read from @3's own columns at the node. There is no
  second record to keep consistent.

### 5.2 Energy roles at a fixed volume

- **The chemical term.** At a fixed volume, @3's chemical term at the node's declared volume,
  G = RT Σ_s n_s (ln(n_s/V) − 1), is the physical free energy of the compartment's content.
  - Exchange's work is the exact ΔG of both nodes; turnover's is the node's ΔG; D152 books its exact
    ΔG with its owned standard-potential term. The energy ledger closes exactly in exact arithmetic.
  - **No dilution term arises,** because V is fixed, and **no mixing heat,** because no fluid enters.
- **The capacitor.** ½ C_b V_b² stays 0 in version 1 (§3.3).
- **The guards of record (D150's lesson).** The shared IMEX energy bound is blind to species bookings
  at µM–nM. A compartment world whose plasma side has no faces is face-free, so its flows are the
  laws' own. RK4's absolute bound (2e-8 pJ) is then the sensitive guard of every booking, and a
  NumPy ΔG test per law is the exact one (acceptance C10).

### 5.3 What the lumen's accounting brings to the volume door

**Door V: the compartment's volume as state.** It arrives through water across the bounding patch
(osmotic swelling, which FR-5's permeabilisation can involve), through fusion and fission, and
through FR-2's creation. Each piece below exists in the S3 lumen (`restricted_lumen.py`; S3 plan
§1):
- **Volume as state,** provided as the node's `extracellular_volume` through the view, as the lumen
  provides its own.
- **The dilution term** −RT N ln(V/V₀), water's expression, which brings @3's chemical term on the
  declared volume to the physical one.
- **The mixing heat** H = RT Σ_s c′_s [V φ(c_s/c′_s) + dV φ(c_in,s/c′_s)] ≥ 0, with
  φ(y) = y ln y − y + 1: the Jensen gap for fluid of one composition entering a compartment of
  another.
  - For FR-2's enclosure of extracellular fluid and for fusion, the source is a finite node, not a
    held bath. Its loss is then a move booked on both nodes, not a reservoir supply (**S**).
- **D150's and D152's version 1.1** (the `VIEW_READS` fallback and bookings at the view through
  water's endpoint free energy), so that exchange, turnover and reactions read the current volume.

## 6. Qualification

### 6.1 Numerical first

The first acceptance is numerical qualification, as for S5, D150 and D152. The engine is checked
against closed forms and exact discrete solutions in compressed worlds: a cell, its held bath, its
compartment, and an extracellular node where the uptake path needs one. Nothing is compared with
biological data, and no paper's model is reproduced (D138, D151).

**This protocol is also exchange's first judged acceptance.** D150's judged scope was @3's faces and
turnover's first-order clearance. Exchange, turnover's production and the occupant rule entered only
through its test files (D150 §12.2's scope line). So exchange@1 is integrated and guarded but not yet
qualified. FR-1's items C3 to C5 and C8 judge exchange's laws (loading, release, saturable release,
the pair's splitting term and the uptake path's import leg) against references that an agent who
never reads the code writes from Appendix A. The protocol says so in its scope line.

### 6.2 The independent references

- **Written by an agent that never reads the code,** from Appendix A alone, as S5's, D152's and
  D156's are. The engine agent runs them through their usage note.
- **NumPy closed forms and matrix exponentials** of the declared linear systems.
- **The palindrome's step map,** iterated in NumPy, for the splitting term.
- **A dense capacitor solve of its own,** for the electrical relations.
- **A ΔG function of its own,** for the energy tests.

### 6.3 The acceptance items

Tolerances are pinned at registration from a dt study, in G2-Q1's form. One run, from a clean
snapshot.

| Item | Check | Reference |
| --- | --- | --- |
| C1. Identity and refusals | Each refusal of §1.4 fires with its reason; the summary's identity block; a label change moves no binding (S2's guard) | Definitions |
| C2. The declaration is pure identity (pending milestone 1) | §3.3's S5: the same world with and without the declaration traces to identical program text and constants, and identical bindings; every existing crossrev set is identical | Constants-aware crossrev (D148) |
| C3. Loading with retention | Export only, flux and first-order: the engine equals the closed form to rounding (one exact stage); per-route reconciliation to rounding | A.2 |
| C4. Two-way first-order exchange | The engine against the closed form within the registered dt-study tolerance; the splitting term identified as the fixed point's relative displacement, x*/x_eq − 1 = −a(a + 2b) dt²/96 (§2.3); the engine against the iterated step map to rounding. C4's world declares no saturable route, so its stage plan is A.4's | A.3, A.4 |
| C5. Saturable release | The engine against the implicit closed form | A.5 |
| C6. Degradation with loading | Exchange loading plus turnover clearance at the node: the linear two-node system with decay | A.6 |
| C7. Reactions inside | Loading of S plus D152's first-order S → P at the node: a linear three-state system; D152's dt·L rule holds | A.7 |
| C8. The uptake path | An extracellular node to the cytosol (an import on a plasma patch) to the compartment (an export on the bounding patch): a three-node chain against its matrix exponential, every host check passing | A.8 |
| C9. Electrical silence (pending milestone 1) | §3.3's S1 to S4, with their criteria as fixed there before any run: the ion rows bitwise, V_b and the patch energy to rounding, the rest of the world reported | A.9 |
| C10. Energy | A NumPy ΔG test per law at the compartment's volume; the RK4 face-free world within the absolute 2e-8 pJ; the IMEX species-only world | A.10 |
| C11. Loading from a trace | D150's onset error was @3's face heat, and a compartment has no face; exchange books the exact ΔG of each moved amount. FR-10's probe 1 (arms D1 and D2, §9) found a first-order export booked at rounding in one world, on the engine as it is. The judged item covers every loading and release law: a compartment loaded from a trace under RK4 (the absolute bound) and IMEX, every row at rounding | A.2, A.10 |
| C12. Restart and vmap | Restart at, before and after a schedule change, and through a snapshot: bitwise. A vector batch of worlds with different compartment volumes and rates: each world within 1e-12 of its scalar run, bitwise against the reversed batch | – |
| C13. Negative controls | A misbooked move fails the compartment's outside ledger while the cytosol's passes; a misbooked work fails the RK4 world | – |

### 6.4 What is not claimed

- No biological comparison: that waits for a measured trafficking or uptake dataset, registered on
  its own (D151).
- No vesicle counts, no stochastic loading, no charged content, no volume change.
- Integration grants no acceptance; judged status comes only from the registered protocol (D143).

## 7. The links: FR-2 to FR-5

| Request | What it needs from this design | What it adds |
| --- | --- | --- |
| **FR-2, internalisation** | The compartment entity, with door C: a pending compartment slot opened at an event, its content enclosed from the adjacent extracellular node (§5.3's mixing and move bookings), its bounding patch's area and capacitance taken from the plasma membrane | Retrieval's energy source (D158); insertion's reverse direction, with populations moving onto the bounding patch; the 64-node cap, since insertion is a field-input provider (§3.6) |
| **FR-3, site occupancy** | Bound cargo keeps its identity: D150 §2.5's one material ledger spans bound sites on the bounding patch's populations and the free row at the node. Version 1 adds no bound state and closes no door: binding and release would be booked transfers between the two, as exchange's moves are. `site_occupancy@1` is admitted beside a compartment by §4's door, past the membrane-state wall | Sites as population state (`membrane_entity_state@1`), which brings the cap; accessibility as a factor; a part-less site owner can use §1.6's widened admission, if every field it holds is an accepted write |
| **FR-4, compartment pH** | The charged door (§3.4): a proton row and counterions on the bounding patch, the capacitor relation of §3.2 with buffer charge, and the implicit or bounded patch | The acidifying pump and its fuel (the energy-pool door); buffering (D152's charged closed reactions and its stiff-kinetics door); the µM–nM numerics of D150 |
| **FR-5, leak and reseal** | The transfer bookings of §2.2 and door T1's passive law for neutral species; @3's permeability on the bounding patch, with the charged door, for ions; the coupling's compartment source and rate route (§4) | The re-expressed injury law as an operator (D156's open decision); pores' stiffness, which needs §3.4's implicit treatment; exocytic fusion through door F |

## 8. The doors, collected

| Door | Needs | First consumer |
| --- | --- | --- |
| Charged (§3.4) | A face-free-node term in the explicit bound and the membrane rate (one D148 round with finding 3's), then an implicit treatment of the bounding patch (a new IMEX ID) | FR-4 |
| T1, a passive permeation law (§2.3) | A new law with an exact two-way relaxation and a heat field, D174's target in D172's round | FR-5 |
| T2, saturable loading (§2.3) | The saturable solve on the cell side | Granule loading |
| V, volume (§5.3) | D150's and D152's version 1.1, and the lumen's accounting | FR-5's osmotic swelling; FR-2 |
| R, replacement (§1.5) | The swap of an owner's compartments, and the occupant rule for node-keyed rates | Renewal worlds with compartments |
| D, division (§1.5) | Pending compartment slots and the entity hierarchy | Inheritance of organelle pools |
| C, creation (§1.5) | An event opening a pending slot | FR-2 |
| F, fusion and fission (§1.5) | A transfer between a compartment and another node | FR-5's exocytosis |
| Floating topology (§3.5) | The representative refusal, and a floating world's acceptance | Finite-extracellular tissues |
| Coupling source and route (§4) | D156's source-semantics and routing doors | FR-5 |
| S, slot-scoped provision (FR-10's note) | A provider and a reader of one view field declare their slots; only an intersection is refused | The requester's dose, uptake, compartment and reactions world (§4) |
| The membrane-state wall (§4) | Membrane state beside a compartment: a field-input provider, so the 64-node cap and the held-bath topology. Opened for FR-2's trafficking on 19 November 2026, with the areas and capacitances read as references (D217) | FR-2 (opened); FR-3's sites on a bounding patch (waiting) |
| FR-3's `site_occupancy@1` (§4) | A one-line, host-only admission, on its two conditions | FR-3 |
| Condensation (§3.6) | Face-free nodes eliminated from the dense solve: a new solver ID | Tissues with a compartment per cell |

## 9. Probes and records

**What was run** (the lead's review round, 14 November; one unit, `cells-fr10-probe1`, from the
clean snapshot of main at ced45c87, CPU 2, 3G; evidence in `probe1/`):
- **The D147 record** (part A, a host-side definition parse): `free_field_offsets` is 0 for the
  species-only compartment world and for the mixed one (the heredity chain with a compartment on
  cell_5). Both are held-bath topologies, so D147 keeps field solver version 2.
- **P4's question, loading a compartment from a trace** (arms D1 and D2): the face-free world, the
  cytosol pre-loaded at 1e-3 mM, the compartment at a 1e-15 mM trace, an export route only.
  - Both pass the runner and every row. Under ARS at 1 ms (D1), the energy residual is at most
    5.9e-11 of its bound, and the onset step's residual 2.7e-16 of its own flows. Under RK4 at
    0.1 ms (D2), against the absolute 2e-8 pJ, it is at most 3.0e-11 of the bound.
  - So, for a first-order export in this one world, D150's resolved-start rule does not bind on a
    compartment's exchange route: exchange books the exact ΔG of each moved amount, and a compartment
    has no face. The other exchange laws, and other worlds, are C11's to show. The rule still binds
    wherever a face carries a switch-on, as at a dosed bath ([FR-10's note](BATH_SCHEDULE_DESIGN.md)
    §3.2).
  - The unit exited 0 in 499 s, with a peak of 1.73 GB and `memory.events` all zero.
- **The existing-worlds sweep** of §3.4 (static, `sweep/`).

**Still requests** (small and read-only, on the engine as it is, from a clean snapshot):
- **P1, the charged rate gap.** Its criterion, in C4's form, written before any run:
  - *World:* the face-free compartment world, with a chloride permeability on the bounding patch at
    Ishida et al.'s 1.2 × 10⁻⁵ cm/s, luminal chloride 110 mM against cytosolic 10 mM, other ions
    impermeant there, everything else quiescent; dt 1 ms and 0.1 ms, 200 steps each.
  - *Reference:* the exact two-volume relaxation, written independently: the constant-field chloride
    flux across the bounding patch and the two capacitors (the plasma patch to the held bath, the
    bounding patch), V_b = −q_comp/C_b, integrated by Radau at rtol 1e-10.
  - *Measured:* the largest error of V_b and of the compartment's chloride against the reference,
    per record; and which check refuses: the definition-time explicit bound, the run-time membrane
    rate (dt × rate against `EXPLICIT_STEP_BOUND` = 1), @3's domain, or the field solve.
  - *§3.4's reading is confirmed if* neither bound refuses the 1 ms run (both see about 0.007), the
    1 ms run either is refused at run time or departs from the reference by more than 10% of V_b's
    change within 20 steps, and the 0.1 ms run (dt × G_b/C_b = 0.48) follows the reference to its
    dt-study tolerance. Otherwise §3.4 is corrected to what was measured.
- **P2, the reported claim.** A heredity-sheet world with and without a compartment node: the ionic
  fields' largest difference, against rounding. It tests §3.3's S4.
- **P3, a floating component.** A finite-extracellular world (with free offsets) in which the
  compartment has the lowest outside index of its component: which node `bind` chooses as
  representative, and whether the run differs from the reordered world. It tests §3.5.

## 10. Effort and order

| Part | Agent-days |
| --- | --- |
| The contract's widened admission of part-less operators, with its tests and crossrev (§1.6) | 0.5 |
| `cell_owned_compartments@1`: parse, the topology refusals, the admitted list, the replacement refusal, the summary's identity block, tier-1 tests | 1.0 |
| **Independent references, by a second agent that never reads the code** (Appendix A) | 0.75 |
| Guards and worlds: C1 to C13, the protocol's registration, the judged run (detached, CPU minutes) | 1.25 |
| **Version 1 total** | **3.5 (range 3 to 4.5)** |
| Door T1, the passive law | 1.0 |
| The charged door's bound term (one D148 round with finding 3's) | 1.0–1.5, then FR-4's implicit treatment |
| Doors R and D | about 1.5 each, after the occupant mechanism and S5's slot rules |

**Order.**
1. The contract addition.
2. The declaration.
3. The references, in parallel, from Appendix A.
4. The guards and the protocol.

Nothing in flight gates it. It touches `contract.py` and a new operator module only, so it can run
beside D150's, D152's and D156's work on disjoint files. FR-10's operator is disjoint from it too.

## 11. Questions

**Settled in the lead's review with the advisor (14 November):**
- The refusals of §1.4 are accepted, with the D147 record and the membrane-state wall named (§3.5,
  §4).
- The bound term is one D148 round with finding 3's, specified after P1. It does not block version 1
  (§3.4).
- Door S comes early, as a general contract feature (FR-10's note).
- The lumped pool is a validity limit and nesting a topology limit, stated as such (§1.3, §1.4).
  No question goes to the requester or the user.

**For the lead:**
1. **The declaration's home:** the operator form, with §1.6's one widened admission for part-less
   operators (today's clause, or every owned field an accepted write), which can serve FR-3's site
   owner too. Confirm the rule and its D148 status (an addition).
2. **S2's criterion** (§3.3): V_b through @3's own charge tolerance on the node's row, rather than a
   bound in ulps of the potentials. Confirm.
3. **The transfer law:** exchange@1 unchanged for version 1, with its three limits declared, door T1
   deferred to FR-5, and FR-1's protocol as exchange's first judged acceptance (§2, §6.1).
4. **The silence claims' criteria** (§3.3), fixed now for milestone 1. Confirm S1 to S5 and their
   kinds before any run.
5. **Probes P1 to P3** (§9): which to run before the code. P1 sizes FR-4's door. P4's question is
   answered, for a first-order export in one world, by FR-10's probe 1, arms D1 and D2.

## 12. Milestone 1 as built (14 November 2026)

The engine agent built milestone 1 after D169, on its branch, with the lead's rulings of the same
evening, and reworked it after the lead's review of the first hand-back. The evidence and log are in
`/mnt/workspaces/Cells/closed-compartment-m1-20261114-01/` (HANDOFF.md). The D148 record, its stop
rule and every world and control below were written there before their runs, and the silence
criteria of §3.3 were copied there verbatim.

**The contract's admission** (D169's rule, with the lead's option (b)):
- **D169's clause.** A part-less operator is admitted when it has `ACCEPTS_WRITES` and
  `VIEW_FIELDS`, as before, or when it owns fields and every one is an accepted write (FR-3's site
  owner, §1.6).
- **A declaration** carries `contract.Operator.DECLARATION_ONLY`. That clause alone would also have
  admitted the contract test's `Nothing`, an operator with nothing at all, so the marker keeps
  `Nothing` refused.
- **The marker's check fails closed** (`contract.declaration_errors`, the lead's ruling). A marked
  class may define only `DECLARATION_MAY_DEFINE`: `LAW_ID`, `DECLARATION_ONLY`, `CONFLICTS_VIEW`,
  `REQUIRES`, `parse`, `to_dict`, `check_definition`, `initial_values` and `summary`.
  - It refuses every other public name of `Operator` that any class below `Operator` defines,
    whether data or method and even at its default value. That covers the parts, fields, step
    methods, and the schedule and definition-check hooks (`inner_check_spec`, `check_steps`,
    `control_values` and the rest).
  - Every registered operator is admitted as before.
- **`pump_composite.Composition.checked_step`** runs the inner step itself for a composition of
  declarations alone, as it does for the empty composition (option (b) of S5's scope). No existing
  composition contains a declaration, so each takes the branch it took before.

**The declaration:** `operators/compartments.py`, `cell_owned_compartments@1`, registered
with one import and one line.
- Each compartment names its node, its bounding patch and its owner, with a label and a reference
  as metadata.
- §1.4's refusals 1 to 7 fire with their reasons: the node, the patch, one compartment per node, no
  ion route on the bounding patch (`refuse_ion_routes`), a zero charge anchor
  (`refuse_charge_anchor`), a held-bath topology, and §4's admitted list. The list fails closed,
  and keeps replacement@1 away from owners, also as donors.
- `CONFLICTS_VIEW` lists the volumes, the areas, the capacitances and the masks. Through the
  composite's structure check it refuses water and what requires it, membrane state, insertion@1
  and @2, the partition, the bridge and the lumens.
- **Identity is a host-side map, independent of storage** (`compartments.identity_map`; D174's
  "compartment identity is a host-side map"). Each entry holds:
  - the compartment's declared ID;
  - its owner (cell, slot, carrier);
  - its declared role, with whether it was declared;
  - its storage (`outside_node`, the node and its slot);
  - its oriented bounding membrane: the patch and its slot, the inside endpoint the owner cell, the
    outside endpoint the compartment (by its ID), and V_b = φ_owner − φ_compartment;
  - the label and the reference.
- **The ID and the role are declared** (the lead's ruling before landing).
  - The ID is a string, unique among every ID of the world. A collision with the node, a cell, a
    species or another compartment is refused.
  - The role is a short string, "lumen" by default when omitted. The map and the summary
    (`compartments_role_default`) record which.
  - **No physics depends on the role in version 1.** Like the label, the ID, the role and the
    reference change no binding (tested).
  - The summary carries the map. Two compartments in one cell stay distinct (tested).
- **Exchange is a driven route** (D174). §0, §2.1 and §2.3 now say so: it books signed work and no
  heat, and a pair that follows Fick's trajectory is not a passive permeation. The passive law is
  door T1, with D174's five requirements.

**Fixtures:** `validation/tissue/compartment_fixtures.py`.
- **W**, D150's face-free topology with exchange loading S into the compartment. W's ions are
  quiescent, so every potential is 0 and silence cannot fail there; S5's traced pairs use it.
- **W+**, the live-owner world (the lead's ruling):
  - a cytosol at K 140, Na 10 and Cl 20 mM;
  - a K leak of 5e-10 m/s on the owner's wall;
  - an initial owner potential of −0.06 V through its charge anchor.
  K leaves the cell and the owner's potential moves toward E_K, while the compartment must stay
  silent.
- **The planted controls:** (a) a K route of 1e-13 m/s on the bounding patch, and (b) a
  compartment charge anchor of 1e-17 C. Tests reach them by bypassing refusals 4 and 5 through
  monkeypatch, a test-only way.

**The gates.** They ran from clean snapshots on CPU 2 with a 3G cap, every unit launched with
`--oom-first` (and, from 01eb558, `--wait-headroom 2G`). The load averages were 8 to 18 on 8 CPUs,
so the times are loaded; the lead measures tiers on clean CPUs at landing.

| Gate | Result |
| --- | --- |
| The tier-1 smoke, `tests/unit/test_cell_owned_compartments.py` (NumPy) | At 09c83bf, 109 passed in 4.2 s. It covers the admission, the fail-closed marker check name by name, refusals 1 to 7, the identity block, the label's non-binding and the structure check. At 01eb558, 31 of its new cases failed: a data default restated at the same object passed the first, identity-based form of the check. Fixed in 09c83bf |
| S5, `_identity.py` and `_identity_more.py` (tracing, no compile) | **Identical in all four pairs:** W under ARS and under RK4, W with clearance at the node beside exchange, and the declaration alone against no operators at all. At 2dc06ed, before the composite's branch change, the declaration alone differed, as the code reading foresaw |
| S1 to S3 in W+, with a planted control in each program family | **They hold on every row, and every planted control breaks them** (01eb558). In each live check the owner's K row moves and \|φ_owner\| is at least 0.05 V. The programs: the scalar program, with (a) and (b); a restart from a checkpoint in process and through a snapshot, each bitwise, with (a) resumed; RK4 at 0.1 ms; the windowed program; the vector-window program, three live worlds with (a) as a fourth; and the batch program, likewise. All passed again at 09c83bf. Loaded times there: 41, 79, 75, 37, 54 and 37 s |
| The contract's and composite's existing guards | `test_pump_composite_contract.py` 16 passed, its `Nothing` still refused; `test_membrane_state.py` 12 passed. `test_pump_composite_identity.py` 9 passed at c67e2cf: the empty composition still equals @3 bitwise, compiled, uncompiled, batched and restarted |
| D148 criterion 1: crossrev, all seven sets against the baseline of record at da94f81 | **Identical at c67e2cf, at 01eb558 and at 38e8738** (the head's code with the fail-closed check and the identity map; after it, src changed only in the operator's docstring, ee498e5). Base: 36/36 jaxpr texts, 36/36 constants, 12/12 bindings. Qualification: 78/78, 78/78, 56/56. Injection and volume: 6/6, 6/6, 2/2 each. Division: 27/27, 27/27, 9/9, its check holding. Species and reactions: 24/24, 24/24, 8/8 each, their checks holding. |
| D148 criteria 2 and 4 | The lead's landing gate (tier 1+2) and baseline renewal |
| D148 criterion 3 | No ledger accumulator or diagnostic changes: the list of cases is empty |

**Superseded, not deleted:** the five silence program files' passes in W at c67e2cf
(`run-c67e2cf/tests/`), which could not fail, and S4 in W, identical only because nothing moved.

**The reported claims** (no pass rule; `reported/s4_live_p2_sheet.py`, `run-01eb558/reported/`):
- **S4 in W+**, with the export at 0, against the same world without the node, 21 rows:
  - The node is silent and the owner live (\|φ\| up to 0.062 V).
  - Every ionic field of the rest of the world is within 4 ulps of its scale (relative 7e-16).
  - The exception is the energy-balance rate, a near-zero balance that differs at 2.6e-18 pJ/s.
- **P2 on §9's heredity sheet** (`cell_replacement_fixtures.heredity_sheet(1, None)`): comp_0 on
  cell_0, ARS at 1 ms for 0.1 s, 101 rows.
  - comp_0 is silent on every row: S1 bitwise, S2 at 4.6e-6 of its bound, S3 at 2.1e-11. It floats
    with its owner at up to 0.0797 V.
  - The ionic fields differ from the sheet without it by at most 1.0e-12 relative (the electrode
    current), 5.6e-13 (the amount increments) and 4.1e-13 (the membrane fluxes and bath supply).
  - The capacitor residual and the energy balance differ by rounding around zero.
- **P2 first ran on D150's heredity chain**, a deviation from §9 (`run-c67e2cf/reported/`):
  - The chain's amounts are identical.
  - Its largest relative changes are about 1.3e-8 in the electrode current and about 1e-9 in the
    face fluxes and bath supply.
  - Its extracellular potentials, about 3.5e-7 V, differ by 8.8e-17 V. On our reading (**S**), the
    dense solve's rounding, relative to its largest potentials, falls on these small differences
    through the chain's faces.
  - comp_5 was silent there too, on 101 rows, with S2 at 9.3e-6 of its bound.
- Both fit §3.3's expectation (**S**): equal in exact arithmetic, with the solve gaining a row that
  rounds differently.

**Not in milestone 1:**
- the acceptance items C3 to C13 and their independent references (a separate agent, D169);
- probes P1 and P3;
- door S.

**The composition matrix** (`validation/tissue/composition_matrix.py`; docs/PUMP_COMPOSITE.md, row
and column 18). The declaration's twelve refusals all come from its `CONFLICTS_VIEW`.
- **Eleven are real:** water's volumes (door V); membrane state's areas and capacitances (the
  membrane-state wall); the lumens' volumes (not shown nominal); insertion@1's and @2's patch and
  node masks (a bounding patch may be an onset patch, FR-2's door C); and the partition's cell mask
  (door D).
- **One is nominal, insertion@1's `face_active`:** no face names a compartment's node (refusal 1),
  and insertion's face view differs from the declared only at faces naming its onset nodes. The
  slots are disjoint, and the code is cited.
- **Two rules at the definition:** the admitted list, law-level and failing closed, behind the
  declarations' refusals; and replacement@1 kept off owners and donors, data-level.
- The matrix test passes (6 passed), from a snapshot that includes docs/.
- At 38e8738, the head with the matrix, every FR-1 file passed again.
- At 7ffdeb4, with the declared ID and role and refusal 4's pump branch tested, every FR-1 file,
  the matrix test and the contract tests passed (smoke 121 passed).

## Appendix A. Equations for the independent references

Units are @3's: fmol, pL, mM = fmol/pL, s, m. RT = 2.577 pJ/fmol at 310 K, and F = 96485.33 C/mol.
10¹⁵ converts m³ to pL. Write c = cytosol (the owner cell), o = compartment, e = extracellular node,
b = held bath.

**A.1 Nodes.** Each node i has a fixed volume V_i and amount n_i of one neutral species. Its
concentration is c_i = n_i/V_i. A held bath has a fixed c_b.

**A.2 Loading with retention** (export, no release).
- Flux law: n_o(t) = n_o(0) + J t and n_c(t) = n_c(0) − J t, while n_c > 0.
- First-order law: n_o(t) = n_o(0) + n_c(0)(1 − e^{−k_e t}) and n_c(t) = n_c(0) e^{−k_e t}.

**A.3 Two-way first-order exchange.** dn_c/dt = −a n_c + b n_o and dn_o/dt = a n_c − b n_o, with
a = k_e and b = κ = 10¹⁵ k_u A / V_o.
- N = n_c + n_o is conserved, and x = n_c / N relaxes as x(t) = x_eq + (x(0) − x_eq) e^{−(a+b)t},
  with x_eq = b/(a + b).
- With k_e = 10¹⁵ P A / V_c and k_u = P, the equilibrium is c_c = c_o.

**A.4 The palindrome's step map.**
- E(τ): x → x e^{−aτ}. I(τ): x → 1 − (1 − x) e^{−bτ}.
- One half-step of length h is S(h) = E(h/2) I(h) E(h/2). One composite step is S(dt/2) twice.
- The fixed point is x* = α(1 − β)/(1 − α²β), with α = e^{−ah/2} and β = e^{−bh}.
- **The stage plan.** Exchange gives the full h to its last stage. With no saturable route declared
  anywhere in the operator, that stage is the first-order imports, which gives S(h) above (an idle
  flux-export stage changes nothing). With a saturable route anywhere, the imports run as two halves
  around it: the same map in exact arithmetic, a different one at rounding. So the step-map reference
  follows the declared plan.

**A.5 Saturable release.** dn_o/dt = −a c_o/(K_M + c_o), with a = A V_max. Then n_o′ solves
b ln(n_o/n_o′) + (n_o − n_o′) = a t, with b = K_M V_o, and n_c gains what n_o loses.

**A.6 Degradation with loading.** dn_c/dt = −k_e n_c and dn_o/dt = k_e n_c − k n_o: a linear system,
solved by its matrix exponential, with the cleared amount ∫ k n_o dt.

**A.7 A reaction inside.** dn_c/dt = −k_e n_c, dn_S/dt = k_e n_c − k_r n_S and dn_P/dt = k_r n_S at
the compartment, with P's cytosolic row untouched. It is solved by its matrix exponential, and the
moiety S + P is conserved.

**A.8 The uptake path.** dn_e/dt = −κ_u n_e (plus any face to the bath), dn_c/dt = κ_u n_e − k_e n_c
and dn_o/dt = k_e n_c, with κ_u = 10¹⁵ k_u A_plasma / V_e. The declared linear system is solved by
its matrix exponential.

**A.9 The capacitor relations.** For a network of a cell (node i), its held bath (fixed at φ_b) and
its compartment (node j):
- C_pm (φ_i − φ_b) + C_b (φ_i − φ_j) = q_i and C_b (φ_j − φ_i) = q_j.
- So V_b = φ_i − φ_j = −q_j/C_b and V_pm = φ_i − φ_b = (q_i + q_j)/C_pm.
- With q_j = 0 and constant: V_b = 0, and V_pm is that of the cell alone.

**A.10 Free energy.** G = RT Σ_nodes n (ln(n/V) − 1). Each law's work is the ΔG of the nodes it
touches, and turnover's clearance work is the node's ΔG. The energy closes as
ΔG = Σ W_ops + W_bath − H_faces.

## References

- Grabe M, Oster G. Regulation of organelle acidity. *J Gen Physiol* 2001;117(4):329–344.
  [doi:10.1085/jgp.117.4.329](https://doi.org/10.1085/jgp.117.4.329), PMID 11279253, PMC2217256.
  Record by DOI from Europe PMC; the quoted sentence and Eq. 3 were extracted from its open-access
  JATS XML (`sources/PMC2217256.xml`, SHA-256 b385020d…3fe8).
- Ishida Y, Nayak S, Mindell JA, Grabe M. A model of lysosomal pH regulation. *J Gen Physiol*
  2013;141(6):705–720. [doi:10.1085/jgp.201210930](https://doi.org/10.1085/jgp.201210930), PMID
  23712550, PMC3664703. Record by DOI from Europe PMC; the quoted sentences, Eq. 4 and the Table 1
  values were extracted from its open-access JATS XML (`sources/PMC3664703.xml`, SHA-256
  a3f626be…f092).
- Rybak S, Lanni F, Murphy R. Theoretical considerations on the role of membrane potential in the
  regulation of endosomal pH. *Biophys J* (1997). Cited by both papers above for the capacitor form;
  not read here.
- Strang G. On the construction and comparison of difference schemes. *SIAM J Numer Anal*
  1968;5(3):506–517. The splitting whose bias §2.3 computes. Cited from the D156 note's use; not
  fetched here.
- Alberts B, et al. *Molecular Biology of the Cell*, the chapter on intracellular compartments and
  protein sorting: the topology of organelle lumens (§1.1). A textbook pointer; not fetched here.
