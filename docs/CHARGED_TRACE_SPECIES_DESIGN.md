# Charged trace species on junctions (FR-15 F2): design note

**Status: proposed, 23 November 2026, by the FR-15 F2 builder, for the lead.** Desk only: no engine
code was written. The code was read at main db54d0f5. What ran: the guard set and
`scripts/library_pages.py --check` on this note's head, and one host-side parse probe (§2). **S**
marks this note's own reading or proposal; everything else is read from the code or the records
cited.

**What is left of F2.** S1 (charged rows in `local_species_reactions@1`, each reaction conserving
charge; ddb52790) and P2 (`passive_constant_field_permeation@1` on the passive-routes kind, on
patches; ce39c904) are on main (the lead's rulings of 19 November, [FEATURE_REQUESTS](FEATURE_REQUESTS.md)
FR-15). What remains is a charged trace row crossing junctions: today nothing admits one. Its
consumer is the gap-junction replication's microRNA (valence −1, made in cells, drifting on
junctions, its charge in the capacitor closure; [GAP_JUNCTION_CANCER_REPLICATION](GAP_JUNCTION_CANCER_REPLICATION.md)
§5 F2, §8 item 2). The Xenopus lane's butyrate is the second consumer of F2 (D228 item 4); §2 shows
which of its needs this build meets.

## 0. Summary

| | |
| --- | --- |
| **What refuses** | `passive_routes.parse` refuses the charged law on any junction (`kinds/passive_routes.py:341`). `species_common.check_impermeant` refuses an operator-written row with an @3 junction permeability (`operators/species_common.py:165`), covered counter-ions apart |
| **Two routes** | **A (recommended):** host the charged law on junctions. **B:** a trace-row door on @3's own junction routes, with a per-stage material bound inside @3 |
| **Charge and energy** | No new term. Node charge sums every row by valence, so the row's charge is in C φ = q as declared. The kind's moves enter each stage's charges. Its heat is J (μ̃_out − μ̃_in), booked by the tableau; the electrical part is @3's capacitor and electrode terms |
| **The one physical gap** | A junction crossing a floating capacitor component: the offset's current balance would miss the kind's current. Refused in version 1 (no consumer has one; FR-15's hosts are held, D276). A2 lifts it |
| **Bitwise** | A junction marker in the kind's structure entry, only where a charged route sits on a junction. Every other world, P2's patch worlds included, keeps its entry, fields and programs |
| **Price (estimates)** | A1 about 2.25–2.75 agent-days with gates; A2 +1–1.5 (the @3 owner's solve); B about 3–4, mostly in @3 |
| **Choices** | C1 A or B; C2 crossing junctions now or later; C3 the junction's material term; C4 in place or a new ID (§10) |

## 1. What refuses a charged species today, and where

- **The passive-routes kind** (`kinds/passive_routes.py`):
  - `parse`, 341–345: `passive_constant_field_permeation@1` "sits on a membrane patch (a junction
    host waits for the @3 owner's ruling …)". The leak (339) and the rectifier (246) are
    patch-only by their own declarations.
  - `check_definition`, 1055: `passive_neutral_permeation@1` carries valence 0 only.
  - The law's declaration lists `("membrane",)` as its hosts
    (`laws/routes/constant_field_permeation.py:143`).
- **`species_common`** (`operators/species_common.py`):
  - `parse_species`, 118–122: neutral rows only, unless `charged=True` (reactions alone pass it).
  - `check_impermeant`, 165–190: any listed row with an @3 membrane, junction or channel route.
    A declared counter-ion is the exception, where @3's explicit-rate bound covers it
    (`check_counter_ion`, 253; `COUNTER_ION_COVERAGE` = 100, line 202).
- **Neutral-only operators,** each through `parse_species`: `scheduled_species_turnover@1`
  (`species_turnover.py:95`, 157), `scheduled_species_exchange@1` (`species_exchange.py:121`, 202),
  `site_occupancy@1`'s ligands (`site_occupancy.py:204`), population unit turnover (204) and
  templated polymerisation (874).
- **Others:**
  - `species_regulated_availability@1` refuses an instantaneous read of a charged species
    (743–750); it reads one through a regulatory state.
  - Wash buffers name neutral species only.
  - The bath schedule admits charged species in neutral formula units.
  - The species registry refuses the charged law on a closure-held row
    (`check_amount_reading_routes`, fail-closed).
  - @3 refuses declared kinds under RK4.
- **Not a refusal, a missing bound:** the transporter kind's `material_term` counts neutral rows
  and K3b's one-end rows, not charged rows that cross (`kinds/transporter.py:2143`). See §6.

## 2. The two consumers' whole paths

| Need | microRNA (z = −1) | butyrate (z = −1) |
| --- | --- | --- |
| Made or consumed | S1 source ∅ → miR⁻ + K⁺, K⁺ a covered counter-ion, with Hill factors as in the EMT world (on main) | S1 (on main) |
| First-order decay | **S:** a closed conversion miR⁻ → D⁻ under the driven `mass_action` law, with D an impermeant product row sharing a declared moiety. The parser admits it (`_kind` returns "closed" for any law, only the passive law demands it, and moieties may be shared; `test_species_reactions_runs.py` runs the neutral S → P with moiety X). Its rate is first order in c_miR, integrated by SSPRK(3,3). The charged version was not run. A sink miR⁻ + K⁺ → ∅ is not first order, since mass action reads every reactant. `scheduled_species_turnover@2` is needed only for exact exponential clearance | as for the microRNA |
| Membrane transport | none | `na_anion_symport_factored@1` on the transporter kind (on main). It has no @3 route, so `check_impermeant` passes |
| Leak permeation | none | P2 on patches (on main). Its `check_counter_ion` margin scales as c V/C. At the comment's scale (1 µM gives 0.4) the line is near 0.25 mM in a pL cell, so a dose below that is a trace row there and keeps P2 |
| Junction drift | **this build** | not needed |
| Its charge in the closure | automatic (§4) | automatic |
| Dose | — | bath schedule, as Na-butyrate (on main) |
| Binding | — | HDAC binding: `site_occupancy@1` refuses a charged ligand. This stays (§6); it belongs to the lane's occupancy-to-state read (G-L8 in its gap register; [GENE_REGULATION_DESIGN](GENE_REGULATION_DESIGN.md)) |
| Material bound when moved | the kind's `material_term` (this build) | missing in the transporter for a trace charged row it moves (§6; the kinds owner) |

**So:** junction hosting serves the microRNA. Butyrate needs no junction. Its remaining F2-side
items lie outside this build: the transporter's material term, and charged ligands in site
occupancy. The microRNA world adds two rows (X and D) under the 16-row cap.

**Run, host side only:** S1 and P2 compose at parse today.
`validation/tissue/species_reactions_fixtures.charge_neutral_source()` (a trace X⁻ made with K⁺ by
`local_species_reactions@1`), given the charged law for X on its patch `contact_0`, is admitted by
`parse_spec` (probe and output in
`/mnt/workspaces/Cells/fr15-f2-junctions-20261123/probes/parse_s1_p2.*`). No step has run with both;
§8's row 3 is the first.

## 3. The options

### A (recommended): host `passive_constant_field_permeation@1` on junctions

What changes, all in `kinds/passive_routes.py` and the law module:
1. **Admission.** `parse` admits a junction host for the charged law. `check_definition` refuses a
   charged route on a junction listed by `surface_pump_v3.crossing_junctions(model)` (4632). Fix
   (A)'s landing (b8e786d4) relied on the blanket junction refusal, so this refusal must land
   in the same change.
2. **Flux.** The law's kernel at V = φ_sender − φ_receiver, inward from the receiver to the sender
   (the kind's convention). Its opening is the junction's gate × availability × the routing door's
   factors, as for the neutral law's junction routes.
3. **Charge step term (S).** A junction route adds 2G at each of its two cells.
   - The Gershgorin row sum of a junction's charge mode is G (1/C_a + 1/C_b) ≤ 2G / min C.
   - That is @3's own junction term, 2 max_i Σ_j G_j / C_i (`surface_pump.explicit_rate_bound`).
   - G once per end, as the patch rule scatters it, would be half of that.
4. **Material step term (S; C3).** At both ends, the two-end sum A P m (B(−x)/V_a + B(x)/V_b)
   (`material_slope_per_s`'s two terms added). At V = 0 it is the neutral law's L.
5. **FR-34's texts that turn false.**
   - `_current` reads "0 on a junction". On a charged junction route, `passive_current_A`
     becomes the route's junction current, positive from sender to receiver (the view's "inside to
     outside"); it is not a share of `membrane_current_A`.
   - `clamped_flux` says a junction route is "voltage-free". There, a charged junction route takes
     its [route] entry as φ_sender − φ_receiver.
   - The view's orientation text changes accordingly.
   - @3's `junction_flux_fmol_s` and `junction_current_A` stay @3's own routes' (§5).
6. **The law.** Its hosts become `("membrane", "junction")`, and its header's junction paragraph
   is replaced.

**Unchanged:**
- The heat: the kind's tableau booking with its RAW_SUM floors. @3's `junction_heat_booking`
  books @3's own routes only.
- The labels (FR-42): the kernel is linear in its ends at fixed voltage.
- The closure rule, and one law per species and route.
- @3 itself.

**Solvers:** IMEX Euler, ARS(2,2,2) and N2. Under N2 the route stays explicit, and its stage term
counts under `explicit_only`. RK4 refuses kinds.

**Against:**
- The kind's route reads the junction's one gate. FR-16's per-species floor (F4: the microRNA's 0,
  the ions' 0.06) must therefore reach a kind route, as a per-route floor read from the gate's open
  state. That is FR-16's design, but A makes it a requirement.
- Junction permeation keeps two representations, as for neutral rows today, held apart by one law
  per species and route.

### B: @3's own routes admit an operator-written charged trace row

- **What changes:**
  - `check_impermeant` admits a charged row on @3's membrane and junction routes; channels stay
    refused.
  - @3 gains a per-stage material refusal for those rows: A P m (B(−x)/V_a + B(x)/V_b) per node at
    the stage's potentials, since the static bound cannot follow the voltage.
  - It is present statically only where such a row is declared (an `InnerStructure` field, a
    recorded exception).
- **For:**
  - Crossing junctions work at once, since @3's junction currents are in the offset balance.
  - FR-16's floors and gating stay in one junction law.
  - @3's junction observations, N2's implicit slopes, junction heat bookings and labels all apply.
- **Against:**
  - It is the core's step and the @3 owner's code.
  - It reverses the 19 November ruling: P2 over P1, and "a charged trace row stays refused
    there".
  - P2's patch law would then duplicate @3's patches for trace rows, which pre-alpha retires
    (churn).

## 4. Charge, the field and the energy ledger

- **The closure.** A node's charge is its background plus F Σ_s z_s n_s over every row
  (`surface_tissue.charge_increment`). The microRNA's −1 therefore enters C φ = q as declared, and
  each component starts neutral (`check_neutral_components`).
- **In the step.**
  - The kind's rates add into the explicit stages' increments, so each stage's (C + a dt L) φ = q
    (`surface_imex.solve_operator`) sees the moved charge.
  - At the step's start, and at fix (A)'s quasi-static states, `field.solve` reads the stored
    charges.
- **S1's writes** conserve charge at every node (Σ ν z = 0). Each node's charge changes only by
  the stored increments' rounding (`COMPONENT_STEP_ROUNDING`), and the z F φ terms cancel, so the
  operator books chemical potentials alone.
- **Energy.**
  - The route's heat is J (μ̃_out − μ̃_in), with μ̃ = RT ln c + z F φ, booked by the tableau and
    joining dissipation by role.
  - Its electrical part, z F (φ_a − φ_b) J, is @3's capacitor term: `readouts`' `capacitor`,
    computed from qdot, which includes the kind's cell rates. At held nodes it is electrode work.
  - The chemical term is @3's own, over every row.
  - Chemical, capacitor and heat sum to zero for the route in exact arithmetic. No ledger term is
    added.
- **Floating components (S, from `numerics/surface_field.py`).**
  - `bind` gives each component without a reservoir one basis column, and `junction_incidence` is
    basis[sender] − basis[receiver]. That is zero within a component and in the rows of held
    components. Only free offsets (no reservoir, no gauge) are solved.
  - A kind's junction current therefore matters only on crossing junctions.
  - There, a current missing from the balance would shift the offsets by about I / G_faces. It
    would also move the component's net charge (the representative's capacitor-ledger row) and
    leave a residual in the energy rate's capacitor term, which drops representative rows.
  - Hence the version-1 refusal.
- **For the replication (S).**
  - A non-trace microRNA's junction transfer is electrically coupled to the junction's ion
    conductance: its counter-ion stays behind, and K⁺ follows through @3's routes.
  - BITSEY drifts it without charge, so this is a real difference.
  - At trace levels its own charge moves voltages by µV.

## 5. The @3 owner's two questions: proposed answers (S, for the owner to confirm)

1. **Must the floating-component residual include a kind's cell-to-cell current?**
   - Yes, exactly where the junction crosses a floating component, and nowhere else (§4's
     incidence argument).
   - Version 1 refuses those junctions.
   - A2 adds a kind hook that the offset Newton calls at trial potentials: each junction's kind
     current and its slope for the Jacobian. They join `evaluate`'s residual and
     `crossing_potential`.
2. **Does KindRates gain a junction_flux?**
   - Not for the ledgers. The moves are in `KindRates.cell`, and `passive_transferred` is the
     kind's own ledger.
   - As an observation it would mirror `membrane_flux`: it would join `total_rates`'
     `junction_flux_fmol_s` and `junction_current_A`, never `junction_transferred`'s derivative.
   - For one meaning it would have to carry the neutral law's junction routes too. That moves
     today's neutral-junction worlds' observations, which is not bitwise.
   - So version 1 keeps @3's junction observations as @3's own routes', and kind routes report
     through their own fields (`passive_transferred`, FR-34's readouts).
   - A flux at the solved potentials is also not what A2 needs: A2 needs a current as a function
     of trial potentials.

## 6. Refusals that stay

- **Net charge from an operator:** every reaction conserves charge, and sources and sinks carry
  their counter-ions.
- **@3's own routes:** an operator-written charged trace row stays refused there (under A);
  counter-ions covered by @3's bound are the exception. Any operator-written row with a channel
  route stays refused.
  **Amended 25 November 2026** ([the calcium note](CALCIUM_STORE_AND_CHANNELS_DESIGN.md) §5.4):
  `local_species_reactions@1` may write a row that a channel carries where the channel's law
  declares its material term. Every other operator, and a law without the term, refuses it still.
- **New in version 1:** the charged law on a junction that crosses a floating component, until A2.
- **The charged law** on a closure-held row, on a neutral row, or beside its host's own
  permeability for its row; the neutral law at valence 0.
- **Neutral-only operators:**
  - turnover@1 and exchange@1 stay neutral. turnover@2 comes when a consumer needs exact
    clearance of a charged row; exchange would be electrogenic transport.
  - `site_occupancy@1`'s charged ligands stay refused: the bound charge would leave the closure
    (G-L8).
  - Regulated availability's instantaneous charged reads go through a state.
- **Unchanged limits:** wash buffers stay neutral; the 16-row cap; kinds under RK4; the material
  term's +inf without potentials.
- **Adjacent, for the kinds owner (not this build).** The transporter's `material_term` skips
  charged crossing rows. A trace charged row that a carrier moves (butyrate on the symporter)
  therefore has no material bound, and the charge rule does not hold it, for `check_counter_ion`'s
  reason. **S:** count a population's charged crossing rows in its material term, as P2's does.
  **Built 25 November 2026, for the laws that declare it** (the calcium note §6.3): a population whose
  law declares `material_term` bounds every row it moves, charged or neutral, by its whole rate. The
  two sodium-anion symporters declare none, so butyrate on the symporter has no material bound
  still.
- **Adjacent, for the lead.** P2's patch material term is each end's own slope, D4's positivity
  form. On a patch facing a finite node of comparable volume, the mode is the two-end sum, up to
  twice that. It is unchanged here unless ruled; P2 is unqualified, and no registered world
  declares the law (§7).

## 7. Bitwise for unchanged worlds (D148 case 2: statically absent unless declared)

- **Host side:** the parse admission and the crossing refusal.
- **The static switch.** The junction terms (2G, the two-end material term, the junction current)
  sit behind a layout field that exists only where a charged route sits on a junction.
  - The kind's structure entry gains a junction marker there alone, as FR-34's `ReadOut` entry did.
  - `declared_fields` adds the field, and only the terms read it.
  - P2's patch worlds, and every world without the charged law, keep their entry, fields and
    programs.
- **No registered world declares the charged law;** nothing under `validation/` or `scripts/`
  names it. Five test files do:
  - `test_passive_routes_kind.py`: its "junction host" refusal row (line 332) asserts today's
    blanket refusal. Its expectation changes by design (§8 row 5). This is the one edit to an
    existing test body, for the lead to sanction.
  - `test_law_registry.py` (the law's step-term names and registration),
    `test_cell_owned_compartments.py` (its held step terms), `test_fr45_proton_laws.py` (its kernel
    at any valence) and `test_neutral_labels_kinds.py` (a patch route): unchanged as read.
  - No test asserts the law's hosts tuple. `registry/model_table.py` lists its module, unchanged.
- **The ID.** The law keeps its ID (C4). Its hosts tuple is read host-side only: the species
  registry's two-ended check (`_route_mover_errors`) admits "junction". No library page lists the
  law.
- **Proof at landing (not run):**
  - crossrev's 11 sets identical;
  - G1's 113 worlds bitwise;
  - FR's landing set bitwise;
  - tiers 1+2 changed 0, apart from the one edited row and the added rows;
  - IDs with no addition or removal;
  - P2's patch test worlds' jaxprs identical at base and head.

## 8. The checks

Rows in `tests/unit/test_passive_routes_kind.py` (D224: rows, not a new file). Its closed pair has
no junction, so the rows build a two-cell world in the gap-junction worlds' form
(`validation/gap_junction_tissue/worlds.py`): two cells facing one held bath, joined by one
junction whose @3 permeability is zero for X.

1. **The junction's closed form (constant-field Nernst–Planck).**
   - Setup: a trace anion X (z = −1) at a held junction voltage of about 50 mV, set by the
     anchors with every ion impermeant, so that the sign plants have power. The junction gate
     is pinned open (minimum open fraction 1, initial gate 1).
   - The relaxation: dn_a/dt = k_b n_b − k_a n_a, with k_a = A P B(−x)/V_a, k_b = A P B(x)/V_b and
     x = z F (φ_a − φ_b)/RT.
   - It must reach that exponential and the Nernst ratio c_a/c_b = e^(−x). Material is
     conserved, and the heat is > 0.
2. **Its charge in the closure.**
   - Setup: the same world at a non-trace amount. Only data differ, so it shares row 1's compile.
     X is the only permeant row.
   - X's own transfer builds the junction voltage. It must relax to the root of
     ln(c_a/c_b) = −z F (φ_a − φ_b)/RT, with φ_a = φ_a0 − z F δ/C_a and φ_b = φ_b0 + z F δ/C_b
     (δ the amount moved). The reference is an independent scalar bisection in NumPy.
   - The result must be neither equal concentrations nor row 1's fixed-voltage ratio. This also
     exercises the 2G term.
   - With no ion route, the energy check reads this route alone. It is the species-only guard that
     GUARD_STATEMENT names: beside ions the shared bound is blind to trace bookings.
3. **The microRNA's shape.**
   - Setup: a composite with `local_species_reactions@1`.
     - A source ∅ → X⁻ + K⁺ in one cell. K⁺ is impermeant on the membranes and moves on the
       junction by @3's own route.
     - A first-order conversion X⁻ → D⁻ in both cells.
     - The kind's junction route carries X.
   - The steady state must match the 2×2 linear closed form at the held potentials. The material,
     node charge and energy ledgers stay within their bounds.
   - K⁺ on the junction shorts the junction voltage, so this row runs at V_j ≈ 0. It tests the
     composition (operator writes beside the kind's junction route, and the ledgers), not drift;
     rows 1 and 2 test drift.
4. **Plants, each failing a row above:**
   - the valence's sign;
   - the junction voltage's orientation;
   - sender and receiver swapped in the flux's ends;
   - the factor 2 dropped: a dt between the halved and the true bound is admitted when planted and
     refused when honest;
   - a closure-blind reference (row 2 with z = 0 in the charge), shown to differ from the engine by
     more than the row's tolerance.
5. **Refusal rows** (the existing parametrized test):
   - the "junction host" row becomes the crossing-junction refusal (§7: the one edited existing
     row);
   - a new row refuses a neutral row on a junction.

**Seconds (estimates, measured and stated at landing).** Rows 1 and 2 share one compile; P2's pair
took about 11 s. Row 3 is one composite compile, about 30–60 s.

**Gate.**
- `gate.sh` (LANE, `PRELOCK_CPU=23`, `ADDITIONS_FROM`) from a clean frozen snapshot: the guard set,
  crossrev, tiers 1+2 and G1.
- FR's landing set.
- Tier rows re-measured with `measure-tier.sh`.
- `scripts/library_pages.py --check`.
- A7's allow-list for any new `entity_sum` call.

## 9. The price (estimates, agent-days)

- **A1** (recommended), about 2.25–2.75 in all:
  - code 0.75–1;
  - tests and plants 0.75–1;
  - gates and tier rows 0.5;
  - review fixes 0.25.
- **A2** (crossing junctions; the @3 owner's solve): +1–1.5. D276 said about +1.
- **B:** about 3–4, mostly in @3, with the @3 owner.
- **Not priced here:** turnover@2, the transporter's charged material term, and FR-16's per-route
  floors.
- **Anchors:** the roadmap's 2–4 days for junction hosting, and D276's +1 day.

## 10. Choices for the lead

- **C1.** A (recommended) or B.
- **C2.** Crossing junctions:
  - refused in version 1 (recommended). No consumer has one; fix (A)'s scan found one crossing
    junction in 323 registered worlds, replacement_padded's, which never conducts, and no kind
    route on any; FR-15's hosts are held;
  - or A2 now.
- **C3.** A junction route's material term:
  - the two-end sum (recommended): the neutral law's form, and its limit at V = 0;
  - or each end's own slope: P2's patch form, which admits twice the neutral law's step on equal
    cells.
- **C4.** The ID:
  - widen @1 in place (recommended): P2's header reserved junction hosting under @1, no world
    declares the law, and S1 and FR-19 are the precedents;
  - or `passive_constant_field_permeation@2`, the user's alternative under D148.
- **C5** (for the replication's owner, not this build): the microRNA's decay as the closed
  conversion, or turnover@2.

## 11. As built (A1, under D310)

- **Where:** `kinds/passive_routes.py` and the law module. @3, the kind contract and
  `species_common.py` are unchanged.
- **Three departures from §3 and §7, each a smaller change:**
  - **No junction marker in the structure entry.** The charged law's own field (`passive_charged`,
    present only where the law is declared) gates every change. D310 changes P2's patch worlds'
    material term anyway, so a marker had nothing left to keep bitwise. Every world without the
    charged law keeps its programs.
  - **`passive_current_A` stays each route's share of `membrane_current_A`:** 0 on a junction
    route, as the view's text says. A junction route's current is e z times its flux. Reporting it
    in that column (§3 item 5) would have changed the view's text for every passive-routes world.
  - **The rows have their own file,** `tests/unit/test_passive_routes_junctions.py`. In the kind
    file they would take it past the tier runner's 90 s measuring cap, into tier 3. The kind file
    keeps only the sanctioned row.
- **A finding, not fixed here.** The charged law books its heat by the tableau. From a trace end
  the tableau samples the log-singular start and books at first order in dt.
  - In a species-only world the energy check refuses it: X at 2 µM against 1e-9 mM leaves 2.0% of
    the route's heat at dt 25 µs and 0.86% at 12.5 µs. From a resolved start (2 and 1 µM) the
    residual is second order: 7.2e-5 and 1.8e-5.
  - The reactions operator has the same limit (its §3.3 (a)). Read, not measured here: the
    operators' GUARD_STATEMENT says the shared energy bound beside ion flows is blind to such
    bookings at µM to nM.
  - Read from the code, not run here: P2's patch routes book the same tableau heat, so the limit
    is theirs too. The test rows start resolved.
  - **For the replication's owner:** the reacting row (§8's check 3) passes with its flows under
    the energy check's 2e-8 pJ floor, so it says nothing about a microRNA at µM entering near-empty
    cells. In a species-only world such a start is refused; in a world with ion flows it books
    heat at first order unseen.
