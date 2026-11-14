# A scheduled bath composition in the composite (design)

**Status: proposed, 14 November 2026, for the lead's review with the advisor.** No engine code was
added, changed or run for this note.

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
- **The older law, cited and not copied:** `models/surface_bath_events.py` (`signal_values`;
  `Adapter.balances`, "Its held electrode supplies the opposite charge") and
  `core/surface_bath_events_binding.py`, whose policy is
  `explicit_ideal_reservoir_dose_voltage_compensation_work@1`. Its documentation is
  [TISSUE_GEOMETRY.md](TISSUE_GEOMETRY.md#schedule-ideal-reservoir-bath-composition).
- **What is taken:** the accounting only. That means the dose, its charge with the held electrode
  supplying the opposite charge, and the work.
- **What is left:** its logistic phase clock (`phase_clock_rk_stage_native_logistic@1`), its K, Cl and
  Na setter order and its counterion overwrites. These follow the pinned BETSE source
  (TISSUE_GEOMETRY.md), and AGENTS.md keeps BETSE conventions out of the composite.
- **The contract:** [PUMP_COMPOSITE.md](PUMP_COMPOSITE.md) and the [v2 design](PUMP_COMPOSITE_V2_DESIGN.md)
  §1. **Species and their onset rules:** the [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md)
  §7 and §11.4.

**Evidence and log:** `/mnt/workspaces/Cells/closed-compartment-20261114-01/HANDOFF.md`, which lists
the readers of the bath composition with their files. **S** marks our own derivation or reading.

## 0. Summary

1. **The operator.** At declared times on the dt grid, an event map sets a declared held bath's
   whole composition. The bath's held content is the operator's state. It reaches @3 through the
   view of @3's `extracellular_amount_reference` at that bath (§1).
2. **The bookings are in @3's frame** (§2). @3's tissue excludes a held bath's content, whose
   increment @3 holds at zero. So:
   - the controller's action on its reservoir is recorded: the dose, its free-energy change, and for
     a charged step its charge and the held electrode's compensating charge;
   - @3's reservoir-work ledger gains one reconciliation term;
   - the tissue's energy ledger needs none.
3. **None of the records is a work field.** The reservoir's content is outside @3's energy ledger,
   and its free energy scales with the bath's nominal volume, which as work would loosen the IMEX
   bound (§2.2).
4. **Step checks see the worst composition** of the schedule through `inner_check_spec` (§2.4).
5. **The walls** (§3):
   - D152's reactions read the field as declared, insertion@1 provides it, and closers pad it: each
     is refused. The door is slot-scoped provision.
   - Water@1 reads the declared bath, so with water only isosmotic steps are admitted. E07-v2's
     osmotic step needs a water version that reads the schedule.
6. **Species doses are neutral,** with no compensation. A dose from the trace is D150's unresolved
   onset by construction, and a staircase is a ramp, so version 1 is qualified on steps between
   resolved levels, and the trace-start dose and the staircase are probe requests.
7. **Effort:** about 1.75 agent-days (range 1.5 to 2.5). Door W (water) adds about 1, and door S
   (slot-scoped provision) about 0.5 to 1.

## 1. The operator

### 1.1 Declaration and schedule

```json
{"law": "scheduled_bath_composition@1", "baths": ["bath_a", "bath_b"]}
```

- **`baths`:** held baths of @3 (`reservoir: true`), each scheduled by this operator alone.
- **Experiment key `bath_composition_events`:** a list of `{time, baths, concentrations_mM}`. Each
  event sets the whole composition of its baths, every declared species, each concentration
  positive (D150's trace rule).
  - A time is an exact multiple of dt, with 0 < t ≤ the end time, and times increase strictly for
    each bath.
  - The initial composition is the bath's declared one, so an event at time 0 is refused.
- **Per-world control data.** The held content n_b = c V_b in force at each change time,
  [species, outside], with V_b the bath's declared volume. These are never closed-over constants
  (D150's crossrev rule). The batch signature carries the scheduled bath IDs.
- **A ramp** is a declared staircase of steps. There is no logistic law.

### 1.2 State, part and view

| State field | Axes | Role |
| --- | --- | --- |
| `bath_held_amount_fmol` | species, outside | The held content in force: the declared content until the bath's first event. The view provides it |
| `bath_dose_fmol` | species, outside | The cumulative dose: the controller's supply to the reservoir |
| `bath_dose_free_energy_pJ` | outside | The cumulative free-energy change of the reservoir's content at its declared volume (a record) |
| `bath_dose_charge_C` | outside | F Σ_s z_s × the dose (a record) |
| `bath_compensation_charge_C` | outside | The held electrode's compensating charge, −`bath_dose_charge_C` (a record) |
| `bath_reservoir_work_term_pJ` | outside | B, the reconciliation accumulator of §2.3 |
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
| D152's `local_species_reactions@1` | `CONFLICTS_VIEW` lists the field | Refused; door S |
| `scheduled_membrane_insertion@1` | It provides the field (onset nodes) | Two providers: refused; door S |
| S5's closers | The adapter pads the field | A provider beside a closer is refused; door S |
| Water@1 (`osmotic_water`) | The declared amounts for the bath's osmotic pressure; the bath's water potential bound at the definition | Sees the declared bath: §3 |
| The restricted lumens | The declared bath for their fill and its supply work | Refused; they need insertion anyway |

## 2. Bookings

### 2.1 The frame

- **@3 excludes the reservoir's content from its tissue.** A held bath's increment is held at zero
  (`surface_tissue.domain_valid`). Its free energy is therefore not in @3's chemical term, and its
  supply to the tissue is booked at μ_b.
- **The older family included it.** Its `physical_state` adds the dose to the bath's increment and to
  its supply, and books the dose's chemical and electrical work as reservoir and electrode work.
- **So in the composite:**
  - the controller's action on its reservoir is recorded (§2.2);
  - @3's books need one reconciliation term (§2.3);
  - the tissue's energy ledger needs no term. At the event nothing in the tissue moves, and
    afterwards @3 books every supply at the view's μ_b (**S**).

### 2.2 The records: dose, compensating charge and work

At an event that changes a bath's held content by Δn_s:
- **The dose** is Δn_s, supply to the reservoir from the external controller: the older law's dose
  (`signal_values`). It is kept apart from @3's `reservoir_supplied`, which is the reservoir's supply
  to the tissue.
- **Its free-energy change at the declared volume:**

      ΔG_b = 10⁻³ RT Σ_s [Δn_s (ln(a_s/V_b) − 1) + (a_s + Δn_s) log1p(Δn_s/a_s)],

  with a_s the held content before the event. This is the adapter's
  `species_chemical_free_energy_pJ`, as D150's operators book, and the older law's "chemical work"
  of a dose.
- **A charged step,** where Σ_s z_s Δn_s ≠ 0, keeps the older rule.
  - The dose carries q = F Σ_s z_s Δn_s, and the held electrode supplies −q ("Its held electrode
    supplies the opposite charge", `Adapter.balances`).
  - Their electrical energies, φ_b q and −φ_b q, cancel. So the composition change's external work
    is ΔG_b, and the summary reports it.
  - The bath's charge anchor is not changed. A held bath is a fixed node of the field, so the field
    and @3's electrode ledger are unchanged (**S**).
  - A real medium is electroneutral, so a world should declare the counterion of a dose (KCl, or K
    for Na). The rule covers declared compositions that do not.
- **Why records, not work fields.**
  - The reservoir's content is outside @3's energy ledger, so a work field would have nothing to
    balance it.
  - ΔG_b scales with the bath's nominal volume. As work it would enter the IMEX flow bound and loosen
    it by an arbitrary amount.
  - So no field ends in `_work_pJ`: the contract makes a field work exactly when it carries that
    suffix.
- **Its own ledgers:**
  - the cumulative dose equals the held content less the declared one;
  - the cumulative ΔG_b equals G(held) − G(declared), within rounding;
  - the compensation plus the dose charge is 0.

### 2.3 The reconciliation term in @3's reservoir-work ledger

@3's ledger is W_res − 10⁻³ Σ_s μ_s⁰ S_s, with μ⁰ the declared bath's potential and S the cumulative
supply. @3 books each epoch e's supply at that epoch's μ^e, so the term missing from the ledger is

    K = 10⁻³ Σ_e Σ_s (μ_s^e − μ_s⁰) ΔS_s^e.

The operator keeps it as K = B + 10⁻³ Σ_s (μ_s^now − μ_s⁰) S_s, with B updated at each event:
B ← B + 10⁻³ Σ_s (μ_s^old − μ_s^new) S_s(t_e) (**S**).
- The electrical parts z F φ_b cancel in the differences, so only RT ln(c^e/c⁰) enters.
- Its ledger terms add −K to `reservoir_work`, on the host and the device. Its magnitude terms add
  |B| + 10⁻³ Σ_s |μ_s^now − μ_s⁰| S_s.

### 2.4 Step checks

- @3's explicit-rate bound uses the declared concentrations of the patches that face each bath.
- The operator's `inner_check_spec` presents each scheduled bath at its per-species maximum over the
  schedule, as replacement presents its worst case.
- That bounds every epoch, since the bound's slope term grows with max(c) (**S**).
- At run time, @3's `membrane_rate` already reads the view.

## 3. Composition

**D150's species: a species dose.** A held bath already serves as a species' far-field source at a
fixed concentration, so a scheduled concentration is a dose. It is neutral, with no charge and no
compensation. Exchange and turnover never act on a held bath, so they compose.
- **The onset (a known limit, not resolved here).** A dose from the trace is D150's unresolved
  switch-on by construction.
  - The face next to the bath books its heat a few percent off in the step after the event (D150
    §11.4).
  - The host energy ledger refuses that in a species-only world, and the ions' bound does not see it
    in a mixed world.
- **A staircase is a ramp.** D150 §7 rules ramps inadmissible in guard worlds until a probe measures
  them.
- So version 1 is qualified on steps between two resolved levels (B1). The trace-start dose and the
  staircase are probe requests (§4).

**Ions.** A substitution (Na for K), a dose, or a pH step on a proton row (FR-4) is the same class:
a step between resolved levels.

**Water: which compositions admit an osmotic step.**
- **Water@1 reads the declared bath.** It computes the bath's osmotic pressure from the declared
  amounts, and books bath water work at a water potential bound at the definition.
- **So with water@1 only isosmotic steps are admitted:** Σ_s c_s at each scheduled bath unchanged,
  to a relative 1e-12. An anisosmotic step is refused at the definition.
- **Door W, the osmotic step.** A water version reads the bath's held content from this operator's
  state, as the lumen reads membrane state's area. It books bath water work at each epoch's water
  potential, with a reconciliation term like §2.3's.
  - E07-v2's osmotic challenge is then [`scheduled_bath_composition@1`, water's new version,
    `scheduled_cell_replacement@2`], with ions as the osmolytes.
  - A neutral species as the osmolyte (sucrose, say) waits for D150's version 1.1, since water and
    the species operators are refused together.

**The walls on the field, and door S.**
- D152 reads `extracellular_amount_reference` as declared; insertion@1 provides it; closers pad it.
  Each is refused.
- **Door S, slot-scoped provision.** A provider declares the slots it provides, and a reader the
  slots it reads. The composite refuses only an intersection.
  - This operator's view equals the declared array off its baths. So D152, which reads finite nodes,
    and insertion, which provides onset nodes, would compose.
  - FR-4's pH step with buffering inside a compartment needs this door.
  - It is a host-only change to `contract.py` and `pump_composite.py`, under crossrev.

**Composes:** @3, injection, D150's operators, replacement@1, membrane state, the coupling operator
(D156), and FR-1's compartments, which are finite nodes, never baths.

**Refused:**
- a target that is not a held bath: a finite node cannot be clamped, as the older family also
  refuses;
- D152, insertion@1, the closers and the lumens;
- water@1 with an anisosmotic step;
- the stationary analysis.

## 4. Qualification

Numerical, against references written from Appendix A by an agent that never reads the code.
Tolerances are pinned from a dt study at registration.

| Item | Check |
| --- | --- |
| B1. The view reaches @3 | A neutral species stepped between two resolved levels at a bath, through a face chain: the engine against the matrix exponential with the stepped boundary, second order in dt |
| B2. An ion step | A passive cell with a K leak on a held bath, K stepped from 5 to 50 mM: the membrane voltage relaxes toward the new zero-current constant-field potential, against an independent ODE (constant-field flux and capacitor) |
| B3. The reservoir-work ledger | It closes at every row with §2.3's term. A negative control without the term fails at the first supply after the event |
| B4. The records | The dose equals (c′ − c) V_b exactly; ΔG_b against NumPy; the compensation equals −the dose charge; the electrode and global-charge ledgers unchanged at every row through a charged, K-only step |
| B5. Idle | With no event, bitwise the composition without the operator (promised); not declared, every crossrev set identical (promised) |
| B6. Restart and vmap | Restart at, before and after an event, bitwise; a vector batch with per-world schedules on the same baths |
| B7. Step checks | A schedule beyond the explicit bound is refused at the definition, and passes at a smaller dt |
| B8. Water@1 | An isosmotic substitution runs with water's ledgers closing; an anisosmotic schedule is refused at the definition |

**Probe requests (for the lead; nothing was run):**
- **The trace-start dose:** a species-only world dosed from the trace at a bath. It measures the
  onset booking (expected: D150's refusal) before any study doses from the trace.
- **The staircase:** a geometric staircase from the trace, measured as D150 §7 requires before a ramp
  is admitted.

## 5. Effort and order

| Part | Agent-days |
| --- | --- |
| The operator: parse, schedule, event map, view, records, ledger and magnitude terms, `inner_check_spec`, refusals, summary, tier-1 tests | 1.0 |
| References (Appendix A) and guards B1 to B8 | 0.75 |
| **Version 1 total** | **1.75 (range 1.5 to 2.5)** |
| Door W, water's new version (for E07-v2's osmotic step) | about 1.0 |
| Door S, slot-scoped provision | 0.5–1.0 |

**Order.** It is small and touches only a new operator module, disjoint from FR-1's
`contract.py` addition. It can run as soon as its note is accepted. Door W waits for E07-v2's osmotic
step to be drafted; door S for FR-4.

## 6. Questions

**For the lead:**
1. **Records, not work fields,** for the dose's free energy and the compensating charge (§2.2).
   Confirm.
2. **Charged steps:** admitted under the older rule and reported, with worlds advised to declare the
   counterion. Or refused, since physical media are neutral?
3. **An event at time 0 is refused,** since the bath's declared composition is the initial one.
4. **Door S's priority:** before FR-4, which needs it for a pH step with buffering inside a
   compartment.
5. **The two probe requests** (§4), before or after the code.

**For the user:**
6. **E07-v2's osmotic step needs door W,** a new water version that reads the bath schedule.
   Should it be built when that step is drafted?

## Appendix A. Equations for the independent references

Units are @3's: fmol, pL, mM = fmol/pL, s, m and V. RT = 2.577 pJ/fmol at 310 K, F = 96485.33 C/mol.

**A.1 The bath.** A held bath b has a declared volume V_b, potential φ_b and a piecewise-constant
composition c_b(t), with steps at the declared times. Its potential is
μ_s = RT ln c_b,s + z_s F φ_b.

**A.2 A face chain with a stepped boundary.** dn_i/dt = Σ_faces κ_f (c_j − c_i) + κ_b (c_b(t) − c_i)
at the node next to the bath, with κ_f = 10¹⁵ D_f A_f / L_f. It is linear, so each epoch is the
matrix exponential with its constant boundary, started from the previous epoch's end.

**A.3 An ion step on a passive cell.**
- The constant-field flux of each species s across the patch, outward positive, is
  J_s = 10¹⁵ P_s A u (c_i − c_o e^{−u}) / (1 − e^{−u}) fmol/s, with c in mM, P_s in m/s, A in m² and
  u = z_s F V / RT, V the cell's potential less the bath's.
- The capacitor gives C dV/dt = −F Σ_s z_s J_s, and the cytosol amounts change by J_s.
- The zero-current constant-field potential at the new composition is the limit (Hille 2001).

**A.4 The records.**
- At each event, Δn_s = (c′_s − c_s) V_b, and ΔG_b is §2.2's expression.
- q = F Σ_s z_s Δn_s, and the compensating charge is −q.

**A.5 The reservoir-work ledger.** W_res(t) = 10⁻³ Σ_e Σ_s μ_s^e ΔS_s^e. §2.3's K is
W_res − 10⁻³ Σ_s μ_s⁰ S_s.

## References

- Hille B. *Ion Channels of Excitable Membranes*, 3rd ed. Sinauer, 2001: the constant-field flux and
  the zero-current potential (A.3).
- The frozen family's law, cited by path in the basis above. Its scope there was guarded: ideal
  reservoirs only, full bath trajectories out of scope, evidence at ns–µs horizons (FR-10's record).
