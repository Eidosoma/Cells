# A scheduled bath composition in the composite (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Qualified, 17 November 2026.** The registered protocol `fr10-dose-schedule-v1`
(`validation/tissue/bath_schedule_protocol.json`, registered at 407ba164) was judged once from a
clean snapshot of that commit: passed, 31 of 31 judged criteria, against the code-blind references
R-faces, R-ion and R-records (`validation/fr10/references`). Its scope is the operator as built
there: neutral formula units, held baths, steps inside the measured region, ARS at 1 ms and RK4 at
0.1 ms.

**Accepted, 14 November 2026 (the lead, with the advisor; D169).** A dose from nothing is a known limit (way (a), extending D150's resolved-start ruling). Version 1 is qualified on steps between resolved levels, and a staircase probe is requested.

**Status: proposed, 14 November 2026; revised the same day after the lead's review with the
advisor.** The departure from the lead's mapping is accepted, since the code confirms it (§2.1).
Net-charged steps are refused. Door S comes early. The onset was probed on the engine as it is
(§3.2). No engine code was added or changed.

D166 logs the request (FR-10, [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md#fr-10--a-dose-schedule-scheduled-bath-composition-in-the-pump-family)).
The decision reads:
- **The feature:** a held bath's composition changes on the dt grid in the composite. The older
  family's explicit ideal-reservoir law, with dose, compensating charge and external work, exists
  and is re-expressed as a composite operator.
- **Its consumers:** the requesting study's doses, E07-v2's osmotic step and FR-4's pH step.
- **Design first (D142),** as a general feature (D144).

**Engine models it runs (AGENTS.md milestone rule):** `resolved_pump_composite@1` over
`resolved_pump_tissue@3`, with one new operator, `scheduled_bath_composition@1`: an event map and a
view. No model, solver, law or shared function changes.

**Basis.**
- **The older law, cited and not copied:** `legacy/models/surface_bath_events.py` (`signal_values`;
  `Adapter.balances`, "Its held electrode supplies the opposite charge") and
  `legacy/core/surface_bath_events_binding.py`, whose policy is
  `explicit_ideal_reservoir_dose_voltage_compensation_work@1`. Its documentation is
  [TISSUE_GEOMETRY.md](TISSUE_GEOMETRY.md#schedule-ideal-reservoir-bath-composition).
- **What is taken:** the accounting only, that is the dose and its work. Its compensating-charge rule
  is cited as the door for a net-charged step, which version 1 refuses (§2.5).
- **What is left:** its logistic phase clock (`phase_clock_rk_stage_native_logistic@1`), its K, Cl and
  Na setter order and its counterion overwrites. These follow the pinned BETSE source
  (TISSUE_GEOMETRY.md), and AGENTS.md keeps BETSE conventions out of the composite.
- **The contract:** [PUMP_COMPOSITE.md](PUMP_COMPOSITE.md) and the [v2 design](PUMP_COMPOSITE_V2_DESIGN.md)
  §1. **Species and their onset rules:** the [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md)
  §7 and §11.4.

**Evidence and log:** `/mnt/workspaces/Cells/closed-compartment-20261114-01/` (HANDOFF.md: the
readers of the bath composition with their files; `probe1/`: the onset probe, its criterion written
before the run). **S** marks our own derivation or reading.

## 0. Summary

**The departure from the lead's mapping, accepted on the code's confirmation.** The mapping books the
dose "as reservoir supply" with the composition change's external work explicit. This note keeps the
dose out of @3's `reservoir_supplied` and makes the work a record, not a work field. The reason is
@3's frame: @3 pins a held bath's increment at zero (§2.1), so the bath's content is in neither its
supply ledger nor its energy ledger. The dose and its work are still booked explicitly, in the
operator's own fields.

1. **The operator.** At declared times on the dt grid, an event map sets a declared held bath's
   composition. The bath's held content is the operator's state. It reaches @3 through the view of
   @3's `extracellular_amount_reference` at that bath (§1).
2. **Neutral steps only.** A step is declared in formula units with integer counts, each neutral in
   integer arithmetic, as D152 checks its moieties. A net-charged step is refused (§1.1, §2.5).
3. **The bookings** (§2):
   - the dose and its free-energy change are records;
   - @3's reservoir-work ledger gains one reconciliation term, the operator's own ledger term, never
     a write into @3's accumulator;
   - the energy ledger needs no term.
4. **Step checks see the schedule's worst composition** through `inner_check_spec` (§2.4).
5. **The walls** (§3.1):
   - D152's reactions list the field in `CONFLICTS_VIEW`: a nominal conflict, since D152 masks held
     baths wherever it reads the field. Insertion@1's second provision is real. Closers pad the field.
   - **Door S, slot-scoped provision, comes early as a general contract feature.** Without it any
     dose world with D152 anywhere is refused, including the requester's natural first world.
     Version 1's workaround is degradation by turnover's clearance.
   - Water@1 reads the declared bath, so with water only isosmotic steps are admitted. E07-v2's
     osmotic step needs door W, which the lead schedules.
6. **The onset blocks acceptance** (§3.2). A dose from nothing is the consumer's main case, and it is
   D150's unresolved switch-on by construction. Probe 1 measured it on the engine as it is:
   - in a species-only world the runner refuses it on the energy ledger, first at row 1;
   - in a mixed world it passes, with an onset-step energy residual of about 2% of that step's
     species flows, unseen (0.16 of that world's bound).
   - Version 1 is qualified between resolved levels, at a step ratio pinned at registration from a
     development measurement, since no arm has yet stepped a bath between two levels. The
     recommendation is D150's known-limit ruling extended to doses, with a staircase probe requested.
   - **Measured since (§7's staircase probe):** the limit is on a step's absolute size, not only on
     its ratio. A 100× stair up to 1e-3 mM passes under ARS, but a 100× step from 1e-3 to 0.1 mM
     does not. In the probe's world, a tenfold step between resolved levels and a staircase of 100×
     stairs from the trace pass under both solvers. A pinned ratio therefore holds only at the levels
     where it was measured.
7. **Effort:** about 1.75 agent-days (range 1.5 to 2.5). Door S adds 0.5 to 1, and door W about 1.

## 1. The operator

### 1.1 Declaration and schedule

```json
{
  "law": "scheduled_bath_composition@1",
  "baths": ["bath_a", "bath_b"],
  "formula_units": {
    "KCl": {"K": 1, "Cl": 1},
    "NaCl": {"Na": 1, "Cl": 1},
    "cargo": {"S": 1}
  }
}
```

- **`baths`:** held baths of @3 (`reservoir: true`), each scheduled by this operator alone.
- **`formula_units`:** each has a name and integer counts over declared species. Counts are
  `int`, at least 1. Each unit's charge Σ_s z_s ν_s is computed in integers from @3's integer
  valences, and must be exactly 0.
  - This is the form of D152's integer moiety check (`species_reactions._moieties` and `_kind`,
    "in integer arithmetic; refused otherwise").
  - A neutral species is its own formula unit.
- **Experiment key `bath_composition_events`:** a list of `{time, baths, formula_units_mM}`.
  - An event sets each of its baths to its declared composition plus Σ_f a_f ν_f, with a_f the
    event's concentration of unit f (mM, signed). The offsets are absolute against the declared
    composition, so successive events never accumulate rounding.
  - So every step is neutral by construction: its charge is Σ_f a_f (Σ_s z_s ν_sf), with every
    inner sum an exact integer zero.
  - Every species must stay positive (D150's trace rule).
  - A time is on the clock's grid (k * dt to within 4 ulps; D283), with 0 < t ≤ the end time, and times increase strictly for
    each bath. The initial composition is the bath's declared one, so an event at time 0 is refused.
- **Per-world control data.** The held content in force at each change time, [species, outside].
  These are never closed-over constants (D150's crossrev rule). The batch signature carries the
  scheduled bath IDs and the formula units.
  - Before a bath's first event, its control is the declared reference amounts themselves, copied,
    never recomputed. A recomputed value could differ by rounding and fire a spurious event at the
    first step, which would break B5's idle promise.
  - Each event's held content is computed once, on the host: the declared amounts plus
    V_b Σ_f a_f ν_f.
- **A ramp** is a declared staircase of steps. There is no logistic law.

### 1.2 State, part and view

| State field | Axes | Role |
| --- | --- | --- |
| `bath_held_amount_fmol` | species, outside | The held content in force: the declared content until the bath's first event. The view provides it |
| `bath_dose_fmol` | species, outside | The cumulative dose: the controller's supply to the reservoir (a record) |
| `bath_dose_free_energy_pJ` | outside | The cumulative free-energy change of the reservoir's content at its declared volume (a record) |
| `bath_reservoir_work_term_pJ` | outside | B, the accumulator of §2.3's reconciliation term |
| `bath_energy_magnitude_pJ` | outside | Magnitudes for the rounding allowance |

- **Part: an event map at the step start.** Where the control's held content differs from the
  state's, it sets the state from the control (the same floats, so nothing re-triggers). It books
  the change Δn = n_new − n_old in the records and updates B. Elsewhere it selects the start state,
  so a step with no event is bitwise idle.
- **View:** `extracellular_amount_reference`, an adapter view field, is the held content at the
  scheduled baths and the declared array elsewhere, selected and never offset by zero.
- **RK4:** the event map runs around @3's RK4 step, as replacement@1's does. Beside a coupled part
  (water), the composite's existing rule refuses event maps.

### 1.3 Who reads the bath composition

| Reader | Reads | With a schedule |
| --- | --- | --- |
| @3's step: transport through `physical_amounts`; the IMEX face weights and the reservoir μ_b (`surface_pump_v3.imex_step`); RK4's `derivative_from_field`; the run-time `membrane_rate` | The view | Sees the scheduled composition. Supply is booked at each epoch's μ_b |
| @3's balances, on the host (`surface_tissue.balances`) and the device (`surface_pump_checks.tissue_balances`) | The declared layout | The chemical term is zero at a held bath. The reservoir-work ledger multiplies cumulative supply by the declared μ_b, so it needs §2.3's term |
| `surface_pump.ledger_magnitudes` | The declared layout | Its reservoir-work magnitude needs §2.3's terms |
| `surface_pump.explicit_rate_bound`, at the definition | The declared layout | Needs the worst case (§2.4) |
| D150's exchange and turnover | Finite nodes only | Neither acts on a held bath, so they compose |
| D152's `local_species_reactions@1` | `CONFLICTS_VIEW` lists the field | Composes since door S (§3.1, updated 17 November 2026); refused, nominally, before it |
| `scheduled_membrane_insertion@1` | It provides the field (onset nodes) | Two providers: refused; door S |
| S5's closers | The adapter pads the field | A provider beside a closer is refused; door S |
| Water@1 (`osmotic_water`) | The declared amounts for the bath's osmotic pressure; the bath's water potential bound at the definition | Sees the declared bath: §3.1 |
| The restricted lumens | The declared bath for their fill and its supply work | Refused; they need insertion anyway |

## 2. Bookings

### 2.1 The frame: @3 pins a held bath's increment at zero

- **The code** (read, not run).
  - `models/surface_tissue.domain_valid`, lines 376–393: the mask of `extracellular_amount_increment`
    is `outside_active & ~reservoir` (line 380), and every value outside its mask must be 0
    (lines 392–393). So a held bath's increment is held at zero at every checked state.
  - `numerics/surface_transport.transport`, lines 323–324: at a held bath the node's rate is zero
    (`finite = where(reservoir, 0, outside)`), and its exchange with the tissue is supply
    (`supply = where(reservoir, -outside, 0)`).
- **So @3's tissue excludes the reservoir's content.** Its free energy is not in @3's chemical term,
  and its supply to the tissue is booked at μ_b.
- **The older family included it.** Its `physical_state` adds the dose to the bath's increment and to
  its supply, and books the dose's chemical and electrical work as reservoir and electrode work.
- **So in the composite:** the controller's action on its reservoir is recorded (§2.2), and @3's
  books need one reconciliation term (§2.3). The energy ledger needs no term: at the event nothing in
  the tissue moves, and afterwards @3 books every supply at the view's μ_b (**S**).

### 2.2 The records: dose and work

At an event that changes a bath's held content by Δn_s:
- **The dose** is Δn_s, supply to the reservoir from the external controller: the older law's dose
  (`signal_values`). It is kept apart from @3's `reservoir_supplied`, which is the reservoir's supply
  to the tissue.
- **Its free-energy change at the declared volume:**

      ΔG_b = 10⁻³ RT Σ_s [Δn_s (ln(a_s/V_b) − 1) + (a_s + Δn_s) log1p(Δn_s/a_s)],

  with a_s the held content before the event. This is the adapter's
  `species_chemical_free_energy_pJ`, as D150's operators book, and the older law's "chemical work"
  of a dose. A neutral step has no electrical part, so this is the composition change's whole
  external work. The summary reports it.
- **Why records, not work fields.**
  - The reservoir's content is outside @3's energy ledger, so a work field would have nothing to
    balance it.
  - ΔG_b scales with the bath's nominal volume. As work it would enter the IMEX flow bound and loosen
    it by an arbitrary amount.
  - So no field ends in `_work_pJ`: the contract makes a field work exactly when it carries that
    suffix.
- **Its own ledgers:** the cumulative dose equals the held content less the declared one; the
  cumulative ΔG_b equals G(held) − G(declared), within rounding.

### 2.3 The reconciliation term in @3's reservoir-work ledger

@3's ledger is W_res − 10⁻³ Σ_s μ_s⁰ S_s, with μ⁰ the declared bath's potential and S the cumulative
supply. @3 books each epoch e's supply at that epoch's μ^e, so the term missing from the ledger is

    K = 10⁻³ Σ_e Σ_s (μ_s^e − μ_s⁰) ΔS_s^e.

The operator keeps it as K = B + 10⁻³ Σ_s (μ_s^now − μ_s⁰) S_s, with B updated at each event:
B ← B + 10⁻³ Σ_s (μ_s^old − μ_s^new) S_s(t_e) (**S**).
- The electrical parts z F φ_b cancel in the differences, so only RT ln(c^e/c⁰) enters.
- **K is the operator's own ledger term.** Its `ledger_terms` add −K to `reservoir_work`, on the host
  and the device, and its magnitude terms add |B| + 10⁻³ Σ_s |μ_s^now − μ_s⁰| S_s. It never writes
  @3's `reservoir_work_pJ`, which @3 alone books.

### 2.4 Step checks

- @3's explicit-rate bound uses the declared concentrations of the patches that face each bath.
- The operator's `inner_check_spec` presents each scheduled bath at its per-species maximum over the
  schedule, as replacement presents its worst case.
- That bounds every epoch, since the bound's slope term grows with max(c) (**S**).
- At run time, @3's `membrane_rate` already reads the view.

### 2.5 Net-charged steps: refused in version 1

- No consumer needs one: a medium change is a combination of neutral salts and neutral solutes.
  Electroneutral substitutions (Na for K, H for Na), salt doses, pH steps with their counterion and
  neutral doses are all admitted.
- **The door,** if a consumer ever needs a net-charged step: the older law's rule. The dose carries
  q = F Σ_s z_s Δn_s, and the held electrode supplies −q ("Its held electrode supplies the opposite
  charge", `Adapter.balances`); their electrical energies φ_b q and −φ_b q cancel. Since a held bath is
  a fixed node of the field, leaving its charge anchor unchanged keeps the field and @3's electrode
  ledger unchanged (**S**). It would be booked in records, as §2.2's are.

## 3. Composition and the onset

### 3.1 Composition

**D150's species: a species dose.** A held bath already serves as a species' far-field source at a
fixed concentration, so a scheduled concentration is a dose, neutral by construction. Exchange and
turnover never act on a held bath, so they compose. Exchange refuses a patch on a held bath, so
uptake into a cell runs from a finite node beside the bath, not from the bath itself.

**Ions.** A substitution, a salt dose, or a pH step on a proton row (FR-4) with its counterion.

**Water: which compositions admit an osmotic step.**
- **Water@1 reads the declared bath.** It computes the bath's osmotic pressure from the declared
  amounts, and books bath water work at a water potential bound at the definition.
- **So with water@1 only isosmotic steps are admitted:** Σ_s c_s at each scheduled bath unchanged,
  to a relative 1e-12. An anisosmotic step is refused at the definition.
- **Door W, the osmotic step** (the lead's to schedule, D144). A water version reads the bath's held
  content from this operator's state, as the lumen reads membrane state's area. It books bath water
  work at each epoch's water potential, with a reconciliation term like §2.3's.
  - E07-v2's osmotic challenge is then [`scheduled_bath_composition@1`, water's new version,
    `scheduled_cell_replacement@2`], with ions as the osmolytes.
  - A neutral species as the osmolyte (sucrose, say) waits for D150's version 1.1, since water and
    the species operators are refused together.

**The walls on the field.**
- **Updated 17 November 2026: door S has landed (D176's round, `docs/SCOPED_COMPOSITION_DESIGN.md`),
  and D152 now composes with this operator in either order.** Checked on main:
  `pump_composite.structure_errors` is empty for the pair in both orders, and the first delivery
  world binds with disjoint slots (`tests/unit/test_door_s.py`). Insertion@1 and the closers stay
  refused, as below. `site_occupancy@1` (FR-3) composes with this operator too since FR-23 (20
  November 2026, D244): its anchor reads are scoped to the finite nodes its populations face, and a
  scheduled composition may not set a site ligand below its trace (`site_occupancy.py`,
  `check_schedule_traces`). The operator's module docstring still calls D152 refused; that text is
  stale and is corrected in a later `src` edit, after move 2 (the lead's ruling). The paragraphs
  below record the analysis as written before door S.
- **D152: refused, but the conflict is nominal** (read, not run). Everywhere D152 reads the field it
  masks held baths: `node_amounts` and `reactions_domain_valid` read finite nodes only
  (`outside_active & ~reservoir`, `species_reactions.py`), and D152 refuses held-bath sites. Its
  `CONFLICTS_VIEW` entry exists for insertion@1, which changes finite onset nodes' anchors. For the
  architecture block's refusal matrix: D152 against this operator is **nominal**.
- **Insertion@1: refused, a real conflict.** It provides the same field at its onset nodes, and the
  composite admits one provider per field.
- **S5's closers: refused.** The adapter pads the field beside a closer.
- **Door S, slot-scoped provision: early, as a general contract feature.** A provider declares the
  slots it provides, and a reader the slots it reads. The composite refuses only an intersection.
  - This operator's view equals the declared array off its baths, so D152 (finite nodes) and
    insertion (onset nodes) would compose. The nominal refusals become admissions, and the real ones
    stay.
  - **It gates the requester's natural first world:** a bath dose, uptake into the cytosol, loading
    into an FR-1 compartment and reactions inside. Without it, version 1 runs that world with
    degradation by turnover's clearance at the compartment node instead of D152's reactions. FR-4's
    pH step with buffering inside a compartment needs it later.
  - It is a host-only change to `contract.py` and `pump_composite.py`, under crossrev.

**Composes:** @3, injection, D150's operators, replacement@1, membrane state, the coupling operator
(D156), and FR-1's compartments, which are finite nodes, never baths.

**Refused:**
- a target that is not a held bath: a finite node cannot be clamped, as the older family also
  refuses;
- a net-charged formula unit (§2.5);
- insertion@1, the closers and the lumens; D152 only before door S (it composes since door S
  landed: see above); `site_occupancy@1` only before FR-23 (it composes since then: see above);
- water@1 with an anisosmotic step;
- the stationary analysis.

### 3.2 The onset: a dose from nothing (probe 1)

**The consumer's main case is D150's unresolved switch-on.** A dose from nothing, with the cargo
absent until the dose, lifts the node beside the dosed bath from the trace by many decades in one
step. D150 measured that a face books such a step's heat a few percent off (its §11.4).

**The probe** (the lead's item 7). It is read-only, on the engine as it is: the clean snapshot of main
at ced45c87, as unit `cells-fr10-probe1` on CPU 2 with a 3G cap, started after
`cells-ccgpu-merge-gate` ended. Its criterion was written before the run (HANDOFF), and its evidence
is in `probe1/`.
- **The dose.** The engine has no bath schedule yet, so the dose is a jump start: the bath held at
  1e-3 mM from t = 0, every cell and finite node at the trace. The neutral species is linear and
  decoupled from the ions, so that is its state at a dose step after a resolved period at the trace.
- **The worlds** have the first delivery world's topology: a held bath, a face to a finite node,
  uptake into the cell, loading into a compartment and clearance there. The species-only world's ions
  are quiescent. The mixed world is D150's heredity chain, its ions moving, with a compartment on
  cell_5 and the dose at bath_5.
- **Each arm** ran through the runner, and row by row through the model's own checked step, 500
  steps.

| Arm | World, trace, solver, dt | The runner | Rows over the energy bound | Largest residual / bound | Onset step: residual / its own flows | Other ledgers, largest / bound |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | species-only, 1e-15 mM, ARS, 1 ms | Refused: "accounting failed: energy" | 13, rows 1 to 13 | 8.4, at row 1 | 2.1% | 0.035 |
| B2 | species-only, 1e-15 mM, ARS, 0.1 ms | Refused, the same | 8, rows 1 to 8 | 2.8 | 1.8% | 0.014 |
| B3 | species-only, 1e-9 mM, ARS, 1 ms | Refused, the same | 13 | 8.2 | 2.1% | 0.032 |
| B4 | species-only, 1e-15 mM, RK4, 0.1 ms | Refused, the same | all 500 | 33 | 12.9% | 0.011 |
| B5 | mixed, 1e-9 mM, ARS, 1 ms | **Passed** | none | 0.16, at row 1 | 0.03% of the world's flows | 0.052 |
| B6 | species-only, resolved, ARS, 1 ms | Passed | none | 3.9e-6 | 1.9e-9 | 0.029 |

No arm's step was refused by the model's own step. `model.check_values` refused exactly the rows over
the bound.

**What it shows.**
- **The criterion's parts (i) to (iii) hold.** Every species-only jump start is refused by the host
  energy ledger, first at row 1. The local, outside, total and reservoir-work ledgers stay within
  their bounds everywhere, so the residual is the face's onset booking. The resolved control passes.
- **Part (iv) fails as written, and what was measured instead is this.** The mixed run passes, but
  the species' whole free-energy change at the end, −0.0105 pJ, is 4.3 times the mixed world's bound
  (0.0024 pJ). So the ions' bound is not blind to the species at this dose. What it does not see is
  the onset's misbooking.
  - That misbooking is the same in both worlds: −7.8e-7 pJ at row 1 in B5 and in B3, with the same
    face and trace.
  - It is 0.16 of the mixed world's bound at row 1, and about 7e-5 of the species' free-energy change
    by 0.5 s.
- **What it does not show: a step between two resolved levels.** B6 was a resolved *start*, not a
  step, and no arm stepped a bath between two levels.
  - So "qualified between resolved levels" rests on a step ratio that no probe has measured. B2's K
    step is tenfold, and B1's species step larger.
  - The admissible ratio, the largest c′/c at an event per species, is pinned at registration from a
    development measurement, as D150's resolved-start rule was. Until then, B1, B2 and B3 assume it.
- **So a dose from nothing is D150's onset limit, unchanged:**
  - transport is exact, by D150 §11.3's probe 4, not re-measured here;
  - the onset step's energy residual is about 2% of that step's flows under ARS, and 13% under
    RK4;
  - a species-only world refuses it, and a mixed world passes it unseen;
  - measured since (§7's staircase probe): the limit bounds a step's absolute size, not only its
    ratio, so a step ratio pinned at registration holds only at the levels where it was measured.

**The ways forward, for the lead's ruling, since this blocks acceptance:**
- **(a) D150's known-limit ruling, extended to doses.** In a mixed world a dose from nothing runs,
  with transport exact and an onset-step energy residual of about 2% of that step's flows. Species-only
  guard worlds dose between resolved levels, at the step ratio pinned at registration. Version 1's
  acceptance then covers those steps, and a dose from nothing carries the known limit in its summary.
- **(b) A resolved dose.** A declared staircase from the trace, admitted only after a probe measures
  it, as D150 §7 requires of ramps. This is the second probe request.
- **(c) A booking change at the source.** @3's IMEX face-heat booking at an onset, as a D148 round or
  a new IMEX ID: beyond this note.
- **The recommendation:** (a) now, as D150 ruled for its own switch-on, with (b)'s probe requested.
  (c) only if a consumer needs the onset's energy itself (**S**).

## 4. Qualification

Numerical, against references written from Appendix A by an agent that never reads the code.
Tolerances are pinned from a dt study at registration.

| Item | Check |
| --- | --- |
| B1. The view reaches @3 | A neutral species stepped between two resolved levels at a bath, at the step ratio pinned at registration, through a face chain: the engine against the matrix exponential with the stepped boundary, second order in dt |
| B2. An ion step | A passive cell with a K leak on a held bath, a KCl-for-NaCl substitution raising K from 5 to 50 mM: the membrane voltage relaxes toward the new zero-current constant-field potential, against an independent ODE (constant-field flux and capacitor). The tenfold step is measured in development first, against the pinned ratio |
| B3. The ledgers across an event | In a species-only world under RK4 (the absolute 2e-8 pJ bound), a step between resolved levels at the pinned ratio: the energy ledger at rounding at every row, before, at and after the event; the reservoir-work ledger closing with §2.3's term. **A control that drops the term must fail**, at the first supply after the event. That the energy ledger stays at rounding across a step is unmeasured until the development run |
| B4. The records | The dose equals V_b Σ_f Δa_f ν_f exactly; ΔG_b against NumPy; the electrode and global-charge ledgers unchanged at every row |
| B5. Idle | With no event, bitwise the composition without the operator (promised); not declared, every crossrev set identical (promised) |
| B6. Restart and vmap | Restart at, before and after an event, bitwise; a vector batch with per-world schedules on the same baths |
| B7. Step checks | A schedule beyond the explicit bound is refused at the definition, and passes at a smaller dt |
| B8. Water@1 | An isosmotic substitution runs with water's ledgers closing; an anisosmotic schedule is refused at the definition |
| B9. Neutrality | A formula unit whose integer charge is not 0 is refused at the parse, and a neutral unit with a large count is admitted: exact, with no floating tolerance |
| B10. The dose from nothing | Under §3.2's way (a): a mixed world dosed from the trace runs, with its known limit reported; a species-only world dosed from the trace is refused by the energy ledger, which the item asserts as the limit's guard |

**The probe request still open:** a staircase from the trace, measured as D150 §7 requires before a
ramp is admitted (§3.2's way (b)).

## 5. Effort and order

| Part | Agent-days |
| --- | --- |
| The operator: parse (formula units, the integer neutrality check), schedule, event map, view, records, ledger and magnitude terms, `inner_check_spec`, refusals, summary, tier-1 tests | 1.0 |
| References (Appendix A) and guards B1 to B9 | 0.75 |
| **Version 1 total** | **1.75 (range 1.5 to 2.5)** |
| Door S, slot-scoped provision (general, early) | 0.5–1.0 |
| Door W, water's new version (for E07-v2's osmotic step; the lead schedules it) | about 1.0 |

**Order.** It touches only a new operator module, disjoint from FR-1's contract addition. Door S
touches `contract.py` and `pump_composite.py`, so it is coordinated with FR-1's addition in one
change set or two consecutive ones.

## 6. Questions for the lead

1. **The onset's way forward** (§3.2), since it blocks acceptance.
2. **Door S's slot declaration:** a static per-field slot mask on the provider and the reader, as
   §3.1 sketches, or a provider-side mask only, with readers keeping their field-level
   `CONFLICTS_VIEW`?
3. **Formula units:** declared on the operator (as here), or on a composite-level species block when
   D150's open question 3 is decided?

## 7. Milestone 1 as built (14 November 2026)

The engine agent built version 1's operator after D169, on the branch, with the lead's approval of
the one shared file it touches (the operator registry). The evidence and log are in
`/mnt/workspaces/Cells/bath-schedule-20261114-01/` (HANDOFF.md).

**What was built.**
- `src/cells/operators/bath_schedule.py`, `scheduled_bath_composition@1`, registered in
  `operators/__init__.py` with one import and one line.
- **The declaration:** `baths` and `formula_units`. Each unit is checked neutral in integer
  arithmetic, with counts that are positive ints.
- **The events,** under the experiment key `bath_composition_events`: `{time, baths,
  formula_units_mM}`, offsets absolute against the declared composition. Before a bath's first
  event, its control is its declared reference amounts themselves.
- **State:** the held content, and the records `bath_dose_fmol`, `bath_dose_free_energy_pJ` and
  `bath_compensation_charge_C`. The last is the older rule's compensating charge, kept as a record:
  zero for a neutral step, which its own ledger checks. Also B, the reconciliation accumulator, and
  the magnitudes.
- **Its own ledgers:** the dose against the held content; the free-energy record against its
  endpoint difference (the per-event terms telescope exactly); and neutrality.
- **K** is its own ledger term on @3's `reservoir_work`, with its magnitude in that ledger's
  rounding allowance.
- **The view** of `extracellular_amount_reference`, and `inner_check_spec` at the per-species
  maxima.
- **Refusals:** each of §1.1's at the definition, and the isosmotic rule beside water@1. The
  composite's own structure check refuses, in either order, insertion@1 (a second provider of the
  field), the closers insertion@2 and the partition (the field is padded beside them), the lumens
  (lumen@1 needs insertion@1, lumen@2 insertion@2) and D152 (nominally), as §3.1 expected. It
  admits injection, membrane state, replacement@1, turnover, exchange and water@1 (all tested in
  `tests/unit/test_bath_schedule.py`). The stationary analysis refuses the composite by its own ID
  check (read, not tested here).
- **Fixtures:** `validation/tissue/bath_schedule_fixtures.py`, the species-only dose leg.

**The gates.** Each ran from a clean snapshot of the branch, in units `cells-fr10-m1-*` on CPU 2
with a 3G cap:
- the operator's commit 2a7e594;
- c36a3fa, the head after the first merge of main (species_regulated_availability@1's landing);
- dae57ff, the tests stage alone, after the second merge of main (the architecture block's first
  items and Track R). It is listed below the table.

| Gate | Result |
| --- | --- |
| The tier-1 smoke, `tests/unit/test_bath_schedule.py` (NumPy) | At c36a3fa's tests stage, 36 passed in 3.8 s by pytest's clock (5 s wall). Every later figure from the tier tool was taken under load. At 2a7e594, 22 passed in 3.5 s; the extra cases are the structure-check and end-time ones |
| B3, `tests/unit/test_bath_schedule_runs.py` (RK4 at 0.1 ms; a step from 1e-3 to 1.5e-3 mM at step 20 of 60) | Passed in 45 s, with every host check on every row. The record (`run-c36a3fa/b3-2/`) follows |
| B5, idleness, `tests/unit/test_bath_schedule_idle.py` | Passed in 40 s: with no event, every inner field is bitwise equal to the composition without the operator |
| Crossrev, the five sets of the baseline of record at 21fb714 | Identical at 2a7e594 and at c36a3fa. Base: 36/36 jaxpr texts, 36/36 constants, 12/12 bindings. Qualification: 78/78, 78/78, 56/56. Injection and volume: 6/6, 6/6, 2/2 each. Division: 27/27, 27/27, 9/9, with its check holding. Main has since renewed the baseline of record at da94f81, with seven sets. Its species and reactions sets have not run on this branch |
| The tier record | Committed from the third measure at c36a3fa, as the lead ruled. All three measures ran on an oversubscribed machine (load 15 to 22 on 8 CPUs), so load pushed every file across a tier boundary: the smoke to tier 2 (24.5 s), and B3 and B5 past the 90 s cap to tier 3. The lead re-measures them at a quiet time (HANDOFF) |

**At dae57ff,** after the second merge of main, the tests stage passed all three files again,
on the loaded machine (load average about 21): the smoke with 36 passed (17.5 s), B3 (193 s) and B5
(126 s). The only commits after it change documentation, which lies outside the snapshot's scope.

**B3's record:**
- **The energy ledger is at rounding on every row.** Its largest residual is 8.5e-22 pJ before the
  event, 8.5e-22 pJ at the first row after it, and 2.0e-20 pJ after that. That is at most 2.6
  ε × the integrated energy flows, and 1.0e-12 of RK4's absolute 2e-8 pJ bound.
- **The reservoir-work ledger closes with the term,** within 9.9e-9 of its bound.
- **Without the term, @3's own reservoir-work ledger fails** from the first row after the event:
  at 2.1e4 × its bound there, and at 4.2e4 to 8.3e5 × afterwards.

**The staircase probe** (the lead's request, §3.2's way (b)). Its criterion was written before the
run, in HANDOFF. Evidence: `run-2a7e594/staircase/` (staircase.json, the probe in `staircase/`).
- **The world:** the species-only dose leg with a face of κ/V = 10/s, so one face time is 0.1 s.
  The ions are quiescent.
- **Part S** doses from nothing: bath, node and cell start at 1e-15 mM. The bath reaches 1e-3 mM by
  a geometric staircase of ratio r, each stair held 0.3 s (3 face times).
- **Part R** takes one step from the resolved profile (1e-3, 0.9e-3 and 0.5e-3 mM), by r.
- **Solvers:** ARS(2,2,2) at 1 ms and RK4 at 0.1 ms.
- **What refuses:** an arm is admissible when the runner passes every host check on every row.
  - Every refusal is the energy ledger. In every refused arm, local, outside, total and
    reservoir-work stay below 0.005 of their bounds.
  - The model's own checked step refused no step.

| Part S: stair ratio r (stairs) | ARS, 1 ms | RK4, 0.1 ms |
| --- | --- | --- |
| 1e12 (1: the dose from nothing in one step) | Refused: 12.4 × the bound, 20 rows from the event | Refused: 376 ×, every row after it |
| 1e6 (2) | Refused at the 2nd stair: 12.3 ×, 20 rows | Refused at the 2nd stair: 81 ×, every row after |
| 1e3 (4) | Refused at the 4th stair: 5.8 ×, 9 rows | Passed |
| **100 (6)** | **Passed** | **Passed** |
| 10 (12) | Passed | Passed |
| 10^0.5 (24) | Passed | Passed |

| Part R: step ratio r, from 1e-3 mM | ARS, 1 ms, 1 s | RK4, 0.1 ms, 0.1 s |
| --- | --- | --- |
| 1.5, 3 | Passed | Passed |
| **10** | **Passed** | **Passed** |
| 100 | Refused: 1.75 × the bound, 2 rows | Passed |
| 1e4 | Refused: 18 ×, 46 rows | Refused: 6.4e4 ×, every row after the event |

- **By the criterion, the admissible dosing protocol from nothing is r = 100.** That is six stairs
  of 100× held for 3 face times each, 1.8 s in all, the last stair reached 1.5 s after the first.
  Every smaller ratio passes too. The one-step dose is refused, as probe 1 found.
- **The admissible step ratio between resolved levels is 10.** That is the ratio that registration
  pins, unless a later measurement narrows it. B3's step (1.5×) lies within it. B2's tenfold K
  step, from 5 to 50 mM, is at other levels, so §4's development measurement still decides it.
- **The limit depends on the step's absolute size, not on its ratio alone.**
  - The staircase's 100× top stair, from 1e-5 to 1e-3 mM, passes under ARS. Part R's 100× step,
    from 1e-3 to 0.1 mM, does not.
  - Every staircase that failed under ARS failed at its top stair, the largest in amount.
  - So both numbers hold for these levels (up to 1e-2 mM), this face and these dt. A world dosed
    at other levels or faces measures its own (**S**).
- **ARS's refusals are transient, RK4's persist.**
  - RK4's energy bound is the absolute 2e-8 pJ, since its relative part is 0. Once a residual
    exceeds it at an event, every later row of the run is over it.
  - ARS's bound has a relative part, 2e-3 of the integrated flows, which grows after the event.
    Its refused rows end within 46 rows.
- **Not built in milestone 1: a refusal at the definition of steps beyond the pinned ratio.** As
  D169 records the limit, the host energy ledger refuses such a step in a species-only world, and a
  mixed world runs it unseen. Milestone 2 builds the refusal (§8).

**Milestone 2's probes** (the lead's ruling: run them first, with their criteria written first).
Criteria and results are in HANDOFF, "FR-10 milestone 2"; the evidence is `m2-probes/run-3d16980/`.
They ran from the clean snapshot of 3d16980, before the rule existed, as unit
`cells-fr10-m2-probes-3d16980` (CPU 2, 2G cap, every arm in its own process; peak 0.90 GB, 911 s).
An arm passes if the runner passes every host check on every row.
- **Probe I, ion steps** (B2's world):
  - One passive cell (1 pL) on a held bath at Na 145, K 5 and Cl 150 mM. Its cytosol is at Na 10,
    K 140 and Cl 20 mM, with a K leak of 5e-10 m/s, and it starts at rest at E_K.
  - At step 10, KCl replaces NaCl by x = 5(r − 1) mM, for r = 1.5, 3 and 10.
  - **All six arms passed, under ARS at 1 ms and RK4 at 0.1 ms.**
  - The K up points: (ratio, level) = (1.5, 7.5), (3, 15) and (10, 50 mM).
  - The Na down points: (1.0175, 145), (1.0741, 145) and (1.45, 145 mM).
  - The r = 3 arm is exactly milestone 1's tested salt step and isosmotic water step, K 5 to 15 mM
    and Na 145 to 135 mM.
- **Probe D, neutral steps down** (part R's world, κ/V = 10/s):
  - From the resolved profile at c0 = 1e-2 and 1e-3 mM, the bath steps down by r = 10 and 100.
  - **All eight arms passed, under both solvers.**
  - The points: (10, 1e-3), (100, 1e-3), (10, 1e-2) and (100, 1e-2 mM).
- A step down by 100 at 1e-2 mM passes ARS, while a step up by 100 to 0.1 mM does not. A step's
  level is the larger of its two concentrations.

## 8. Milestone 2: the step refusal and the species cap (15 November 2026)

**The lead's rulings after milestone 1:**
- a definition-time refusal of oversized dose steps, from the measured region, with ratio and
  absolute size together;
- `check_species_cap`, with a world above 7 species;
- then, on this design point: run both probes first, and write the rule from measured regions only.
  That means no blanket exemption for ions and no symmetric assumption for steps down, and
  milestone 1's tested steps must lie inside what is measured (§7's milestone-2 probes).

### 8.1 The rule: admit only what the measurements dominate

For each scheduled bath and species, every change of the held content from c to c′ is a step. Both
are positive, and they are compared in mM at the bath's volume.
- **The step's terms:**
  - its direction: up if c′ > c, else down;
  - its ratio: r = max(c, c′)/min(c, c′);
  - its level: L = max(c, c′).
- **Its key:** neutral species (valence 0) share one key; each ion is keyed by its species ID. So
  K's measured steps say nothing about Cl, and a step up says nothing about a step down.
- **The step is admitted only if both hold:**
  - a measured passing point (r_p, L_p) of its key and direction dominates it, with r ≤ r_p and
    L ≤ L_p, to a relative 1e-9;
  - the definition lies within the measured conditions: ARS(2,2,2) at dt ≤ 1 ms or RK4 at
    dt ≤ 0.1 ms, and every face touching the bath relaxes its other node, for that species, at
    κ/V ≤ 10/s, with κ = D A / L.
- **Everything else is refused, fail closed.** The message names the bath, the species, the time,
  the direction, r, L, and the measured points that would admit such a step. It points to dosing
  through stairs inside the region.
- **An idle schedule** (no event) has no step, so it is admitted at any solver and dt.

**The measured points** (`bath_schedule.MEASURED_POINTS`; each passed under both solvers, §7):

| Key, direction | Points (ratio, level mM) | From |
| --- | --- | --- |
| neutral, up | (100, 1e-3), (10, 1e-2), (3, 3e-3), (1.5, 1.5e-3) | the staircase probe |
| neutral, down | (10, 1e-3), (100, 1e-3), (10, 1e-2), (100, 1e-2) | probe D |
| K, up | (1.5, 7.5), (3, 15), (10, 50) | probe I |
| Na, down | (1.0175, 145), (1.0741, 145), (1.45, 145) | probe I |

- **Not measured, so refused:**
  - any other ion or direction (Na up, K down, Cl, Ca, protons);
  - faster faces;
  - ARS above 1 ms, RK4 above 0.1 ms, and other solvers.
  Each opens with its own measurement, added to the table.
- **This is a guard, not a model.** The rule claims only that an admitted step lies inside what
  was measured, in worlds of these classes.
  - The host energy ledger remains the run-time check in species-only worlds.
  - A mixed world's bound would not see a violation, which is why the refusal is at the
    definition.
  - The membrane rate beside the bath is not a dimension of the rule. Probe I's world had a K leak
    of 5e-10 m/s, and faster membranes are unmeasured (**S**).
- **The order of the checks in `check_definition`:** the species cap, then (beside water@1) the
  isosmotic rule, then the step rule.

### 8.2 The species cap

`check_definition` calls `species_common.check_species_cap(spec, LAW_ID)`, as every species
operator does (16 species, D165).

### 8.3 Criteria, fixed before the tests ran

**`tests/unit/test_bath_schedule_steps.py`** (NumPy, tier 1):
- **Admitted:**
  - the neutral corners;
  - the staircase's smaller steps;
  - neutral steps down at (100, 1e-2) and (10, 1e-3);
  - K up at (10, 50), (3, 15) and (1.5, 7.5), with their Na steps down;
  - RK4 at 0.1 ms;
  - a slower face.
- **Refused, each with its reason:**
  - 1% past each neutral corner;
  - the staircase's measured failures, (1e3, 1e-3), (100, 0.1) and (1e4, 10);
  - the dose from nothing in one step;
  - a step down past (100, 1e-2);
  - K up past (10, 50);
  - Na up and K down, never measured;
  - a face of 11/s;
  - ARS at 2 ms and RK4 at 0.2 ms.
- **§7's admissible protocol is admitted whole** (six stairs of 100), and so is a washout by 100
  at 1e-3 mM after it.
- **An idle schedule** is admitted at 5 ms.
- **Every measured point** is admitted by its region, and the same point 1% further out is not.
- **The species cap:** 8 species admitted, 17 refused.

**Milestone 1's tests stay as they are:** B3's step, the salt step and the isosmotic step lie
inside the measured regions.

**Crossrev:** no existing set contains the operator, and contract.py and pump_composite.py are
unchanged, so every set stays identical.

**Results** (clean snapshots of the branch, CPU 2, 2G cap):
- **At bd3a295:** `test_bath_schedule_steps.py` 29 passed, and milestone 1's smoke test 36 passed,
  its salt and isosmotic steps included.
- **At 8dde04c:**
  - the composition matrix test passed;
  - B3 and B5 passed;
  - the steps test failed once, on its own edge assertion: an interior point moved 1% out is still
    dominated. It now checks corners only.

## Appendix A. Equations for the independent references

Units are @3's: fmol, pL, mM = fmol/pL, s, m and V. RT = 2.577 pJ/fmol at 310 K, F = 96485.33 C/mol.

**A.1 The bath.** A held bath b has a declared volume V_b, potential φ_b, declared composition c⁰
and a piecewise-constant composition c(t) = c⁰ + Σ_f a_f(t) ν_f, with steps at the declared times.
Its potential is μ_s = RT ln c_s + z_s F φ_b.

**A.2 A face chain with a stepped boundary.** dn_i/dt = Σ_faces κ_f (c_j − c_i) + κ_b (c_b(t) − c_i)
at the node next to the bath, with κ_f = 10¹⁵ D_f A_f / L_f. It is linear, so each epoch is the
matrix exponential with its constant boundary, started from the previous epoch's end.

**A.3 An ion step on a passive cell.**
- The constant-field flux of each species s across the patch, outward positive, is
  J_s = 10¹⁵ P_s A u (c_i − c_o e^{−u}) / (1 − e^{−u}) fmol/s, with c in mM, P_s in m/s, A in m² and
  u = z_s F V / RT, V the cell's potential less the bath's.
- The capacitor gives C dV/dt = −F Σ_s z_s J_s, and the cytosol amounts change by J_s.
- The zero-current constant-field potential at the new composition is the limit (Hille 2001).

**A.4 The records.** At each event, Δn_s = V_b Σ_f Δa_f ν_sf, and ΔG_b is §2.2's expression. The
step's charge F Σ_s z_s Δn_s is zero in exact arithmetic.

**A.5 The reservoir-work ledger.** W_res(t) = 10⁻³ Σ_e Σ_s μ_s^e ΔS_s^e. §2.3's K is
W_res − 10⁻³ Σ_s μ_s⁰ S_s.

## References

- Hille B. *Ion Channels of Excitable Membranes*, 3rd ed. Sinauer, 2001: the constant-field flux and
  the zero-current potential (A.3). A textbook pointer; not fetched here.
- The frozen family's law, cited by path in the basis above. Its scope there was guarded: ideal
  reservoirs only, full bath trajectories out of scope, evidence at ns–µs horizons (FR-10's record).
