# Cell division: design note (D141, D142)

Status: **draft for review by the lead and the advisor, before any engine code**
(11 November 2026). Merged to main on 11 November 2026, before any engine or
reference model had produced an Em for J1, so the choices declared here are on
record first. It covers stages 1b (parameter table), 2 (scale smoke test) and the
design of engine piece 1 in the [cell-division plan](CELL_DIVISION_PLAN.md). Nothing here
is built or qualified. Evidence: `/mnt/workspaces/Cells/cell-division-20261111-01/`
(`verification/` for the tables and paper notes, `scale-smoke-01/` for the smoke test).

Paper abbreviations: **dLB74** de Laat & Bluemink 1974, J Cell Biol 60:529; **BdL73**
Bluemink & de Laat 1973, J Cell Biol 59:89; **K83** Kline, Robinson & Nuccitelli 1983,
J Cell Biol 97:1753; **DFS74** DiCaprio, French & Sanders 1974, Biophys J 14:387; **dL74**
de Laat, Buwalda & Habets 1974, Exp Cell Res 89:1. Marks: **V** read in the full text,
**S** our arithmetic or interpretation, **F** read off a figure.

## 0. Summary

- **Composition first.** Division needs replacement-like events, volume state, evolving
  membrane geometry, a new compartment and topology changes at once. A wrapper around
  `resolved_pump_tissue@3` for it would be the third combination wrapper, which D142 rules
  out. Proposal: **one composite pump-tissue model** that runs `resolved_pump_tissue@3`'s
  own step at a *view* of its layout, plus **operators** with a declared contract (owned
  state, ledgered writes to shared entity state, the inner layout fields they provide,
  step kind, ledgers, refusals). Water, replacement and division become operators; new
  combinations become definitions, not model families (§3).
- **Entities own state; operators write it only through ledgers** (§2). Membrane surfaces
  are split into domains (old and new membrane), and each domain holds **populations of
  identified functional units** (an assembled channel, pump, transporter or connexin
  channel) whose abundance is state. Each has a stable unit ID and an opaque reference to
  the planned [protein catalogue](PROTEIN_CATALOGUE_PLAN.md) (the identity hook the lead
  asked for). "Functional unit" avoids a clash with ion species.
- **Division is a process** (§4): about 7 min of furrowing without new membrane, then
  insertion of new, K-selective membrane at the measured rate into a **restricted cleft
  compartment**, then an **isopotential partition** event at a declared time, into fresh
  daughter slots, then bridge closure. An instant split stays a declared test limit only.
- **Charge and energy laws** (§5). Insertion conserves the free-node charges; the clamps
  supply image charge with its work; the capacitor free energy falls by
  H = ½ ∫ (ΔV)² dC ≥ 0, booked as heat. The partition keeps every potential continuous;
  a symmetric partition changes no energy at all.
- **Frog membrane** (§6): a nearly nonselective old membrane and a K-selective new
  membrane are existing constant-field leak laws; no pump. Missing: abundance as state,
  insertion, and the cleft.
- **Validation** (§8): first judged observable **J1**, dLB74 Table I, normal eggs at onset
  of second cleavage: Em −20.3 ± 0.8 mV (SE, n = 20) predicted, with Rm 488 ± 28 kΩ from
  the same eggs calibrating the cleft access. A bath-equivalent cleft predicts −37 to
  −44 mV, so the test can fail. **J2** is DFS74 Table I (2 and 4 cells) after the
  partition exists.
- **Stage 2 smoke test: accepted** on `@3` and on `resolved_pump_water@1` (§1.2), with every
  ledger at most 1% of its bound. It found one magnitude problem, at the definition check:
  a fixed 1e-20 C bound below the float64 resolution of an egg's fixed background.

**Decisions for the user** (decided 11 November 2026, D143: decision 1 as "re-express everything now"; decisions 2–4 taken as the lead's stated defaults)
1. Adopt the composite model with operators as the D142 answer, and let water@1 and
   replacement@1 be re-expressed through it under bitwise guards (§3.6). The alternative,
   keeping them frozen and composing only new IDs, duplicates their laws.
2. Make J1 (one compartment; needs no partition) the first judged run, ahead of J2.
3. Accept the first slice's stated limits: well-mixed cytosol, held bath, prescribed
   timing, no fitted junction, uniform old membrane, cytosol on the measured activity basis.
4. Whether unqualified operator combinations may run as labelled development runs, with
   judged status only from registered protocols (recommended).

**Open questions for the review:** new-membrane capacitance (not measured); when the
partition happens (bridge closure is not measured); the cleft access's selectivity (§7);
the cleft-node stiffness at 1 ms (§5.4); one old-membrane calibration per dataset (dLB74
against DFS74 batches); and, for later triggered divisions, re-anchoring at the event
against D057 (§5.2).

## 1. What stages 1b and 2 established

### 1.1 Parameter table v2

`verification/xenopus_parameters.csv` now holds the full-text values of the three J Cell
Biol papers: 11 rows corrected in place, 28 appended, every row with a source and a mark.
The stage-1 table is kept as `xenopus_parameters.v1.csv`. Appendix A lists the changes.
Two corrections matter for the design:
- the folded area is **1.7 × the measured geometric 5.11 ± 0.09 mm²** (contour +30%;
  dLB74 p534, BdL73 p93), not 1.64 × a smooth sphere;
- the old membrane's 74 kΩ·cm² is **852 kΩ × 8.69 mm²** (43.5 kΩ·cm² on the geometric
  area), and the new membrane is **1.82 and 1.36 kΩ·cm²** (mean 1.59), from resistances
  and areas measured in different eggs and media.

The J Cell Biol notes' "TEA no effect" (K83) was not found in K83's PDF text layer, so it
is not carried over. Those notes were checked against the PDF, so it needs a second look.

### 1.2 Scale smoke test (accepted)

One egg-sized cell at rest, through `core/runner.run` (host checks on every accepted row)
and `surface_pump_v3.device_checks` on every row. Driver
`validation/tissue/egg_scale_smoke.py` (commit `c29435f`), run from a clean snapshot on
CPU 3. Evidence: `scale-smoke-01/` (`command.txt`, `results/*.json`).

- **World:** `resolved_pump_tissue@3`, IMEX ARS(2,2,2) at 1 ms for 60 s (60,001 rows), no
  pump, no channel populations. Water volume 0.782 µL (dL74 Table 2). Cytosol on the
  activity basis: Na 19.4, K 51.4, Cl 53.1 mM (dL74 Table 4). Steinberg's NaCl and KCl on
  the same basis (coefficient a_K/c_K = 0.545/0.67, dL74 p11). Old membrane P_Na = P_K,
  P_Cl = 0, with P set so that Rin = 852 kΩ at rest. Capacitance 0.62 µF/cm² on 5.11 mm².
  295.15 K.
- **Scale:** volume 1.04 × 10⁶ times the heredity cell's, largest amount 4.2 × 10⁷ fmol,
  capacitance 1,900 times, τ = 27 ms. That is six orders of magnitude, not nine.
- **Rest:** Vm −9.945 mV (dL74: −9.8 mV for P_Na/P_K = 1). The engine's fluxes equal an
  independent constant-field calculation to eight digits (221.0968 fmol/s of Na in, K out).
  Over 60 s Vm moves by 3.9e-13 V and Na rises by 13,264 fmol (+0.017 mM).
- **Ledgers, worst residual over its checked bound on any row:**

  | Ledger | @3 | water@1 |
  | --- | --- | --- |
  | Material (local, outside, total), water | exactly 0 | exactly 0 |
  | Capacitor charge | 2.5e-15 | 1.2e-8 |
  | Electrode charge | 1.0e-11 | 3.5e-5 |
  | Global charge | 1.8e-14 | 2.3e-11 |
  | Energy | 4.0e-12 | 8.3e-12 |
  | Reservoir work / bath water work | 4.8e-3 / – | 9.6e-3 / 3.8e-3 |

  The field's charge residual stays at or below 5.2e-26 C. No device row fails. In the
  water arm the egg swells slowly: the activity-basis cytosol is 124 mOsm against a 96 mOsm
  bath, so Vm moves by 1.6 µV in 60 s.
- **Refusal found:** the heredity fixtures' construction (anchor C·Vm, background
  anchor/F − Σ z n) is refused by `surface_tissue.check_definition`: the anchor and the
  inventory differ by 1.2e-20 C against an absolute bound of 1e-20 C. One float64 step of
  the egg's 1.38 × 10⁷ fmol background is 1.8e-19 C, so whether such a definition passes
  is luck. Computing the anchor from the rounded inventory (a 3e-13 V offset) passes. Engine
  follow-up: scale that bound with Σ|z F n|, as the running ledgers already do.
- **Cost:** compile 16 s, execution 4.2 s (0.07 ms per step), host checks 151 s
  (2.5 ms per row). Runs of 10⁶ steps or more must use the device checks of the
  vector-window runner.

Not tested yet: whole-content increments after a partition (§5.4), and runs of hours.

### 1.3 What the design must represent: Xenopus first cleavage

| Time after furrow onset | Event | Source |
| --- | --- | --- |
| 0–7 min | Groove 100 µm deep at about 4 min, furrow 150 µm at about 8 min. The extra surface comes from smoothing the folded egg surface. Em and Rm are unchanged | BdL73 p96 (V); dLB74 p531, p538 (V) |
| 4–8 min | New, smooth, unpigmented membrane appears (absent at 3–4 min, present at 7–8 min). Em and Rm start changing at 6–8 min | BdL73 (V); dLB74 p531 (V) |
| 7–17 min | Rm falls steeply; Em becomes about 10 mV more negative. New membrane grows at about 0.04 mm²/min (in the treatment arms); about 0.06 mm²/min in normal eggs (S) | dLB74 p531, p536 (V) |
| Late in the cycle | Em depolarises by 1–3 mV as the blastomeres become apposed more closely | dLB74 p531 (V) |
| About 30 min | Onset of second cleavage. Normal eggs: Em −20.3 ± 0.8 mV (SE, 20), Rm 488 ± 28 kΩ (17). New membrane 1.39 ± 0.29 mm² (SD, 11; probably both faces, S; other eggs, in 1/10 Steinberg); cytoplasmic bridge 0.26 ± 0.18 mm²; coupling V2/V1 above 0.95 throughout first cleavage | dLB74 Table I, p538 (V); BdL73 Table II (p96) and p95 (V); single-egg traces (F) |
| About 35 min | First cleavage complete; the second has already begun | DFS74 p395, citing Bluemink 1971 (V, secondary) |
| Second cycle | DFS74's 2-cell values, sampled after the second furrow began: Em −15.5 ± 1.6 mV (SD, 9), Rm per cell 1.05 MΩ, Rj 0.286 MΩ, coupling ratio 0.772 | DFS74 Table I (V) |

Three facts shape the design: the new membrane is a different membrane (low resistance,
K-selective, Ba²⁺-sensitive: dLB74, K83); it lines a narrow cleft rather than facing the
bath (only about 0.14 mm² of it acts as bath-exposed: dLB74 p535); and the two halves
stay one electrical compartment until the bridge closes.

## 2. Entities and owned state

This follows the ownership table of the
[multiscale architecture page](MULTISCALE_EXECUTION_ARCHITECTURE.md#state-ownership-and-geometry).
"State" means it evolves in the run; "declared" means it is fixed in the definition.

| Entity | Owns | Written by | Must not be conflated with |
| --- | --- | --- | --- |
| Species | Identity, valence (declared) | – | – |
| **Compartment** (cytosol, cleft lumen, finite outside node, held bath) | Amounts (anchored increments), volume, fixed-charge background (state, constant except at events); its kind | Transport inside the inner step; partition; replacement; water; cleft growth | A cell, a lineage record, a bath's clamp |
| **Cell** | Carrier ID, slot, one cytosolic compartment, its membrane patches; later a cycle state | Partition and replacement (identity); a trigger law later | Its compartment (a dividing cell keeps one cytosol until partition) and its slot |
| **Membrane patch** | Endpoints (a cytosol and one outside compartment), domain, area A and capacitance C (state) | Insertion; partition; mechanics later | Contact adjacency, cell volume |
| **Membrane domain** | Type (old, new), specific capacitance, passive leak per area, the composition of membrane it receives on insertion (declared) | – | A patch: a domain may span several patches, and a patch is one domain's piece facing one outside compartment |
| **Population** | Molecular species ID and catalogue reference (declared), kinetic law and unit parameters (declared), abundance N and gate state (state) | Insertion; partition; replacement templates; later trafficking and gene regulation | Availability, which is an experiment control (blockers, schedules) |
| **Contact** (cell to cell) | Endpoints, kind (cytoplasmic bridge, channel contact), geometry (bridge aperture), its connexin-channel populations | Bridge closure; junction formation (G2); gating inside the inner step | The trans-cleft path, which is two patches and a compartment |
| **Outside transport edge** (face) | Endpoints, area over length, diffusivities | Declared in the first slice | A membrane |
| **Tissue topology** | Slot capacities (declared), activity masks (state), capacitor components | Partition and insertion onset (activation) | Identity and lineage |
| **Lineage** | Records: carrier, kind (founder, newcomer, daughter), parents, slot, birth, death, inheritance route | Event operators only | Slots, which are storage |

**Populations and the identity hook (the lead's constraint).** A membrane domain holds
populations of identified functional units: channels, pumps, transporters and connexin
channels. Each population declares:
- `functional_unit`: a stable ID and a `catalogue` reference, either null or
  `{"catalogue": <id>, "entry": <key>}`. The reference is opaque to the engine: physics
  comes only from the kinetic law and its parameters. The curated catalogue (gene-product
  accessions, assembly stoichiometry) is designed separately; the two are reconciled at
  review.
- Its kinetic law and unit parameters (for example permeability per unit abundance).
- State: abundance N and its gates. Today's `channel_abundance` is then N divided by the
  patch area times a reference density, presented to the inner model as layout (§3.3).

Two populations of the same functional unit in different domains share the unit ID.
For the frog membrane no gene product is established in the sources read, so every
population is unassigned (catalogue null).

**Slots.** Every array is padded to declared capacities: the cell slots, patches,
populations, contacts, outside nodes and faces the run will need. Shapes never change in a
run. Each daughter takes a fresh slot, declared inactive until its event, with its anchors
at its expected content; the parent's slot is retired at the partition (the rule and its
reason are in §5.2). One round of division from one cell therefore needs 3 cell slots, and
1 → 2 → 4 cells needs 7. Each cleft node is likewise declared inactive until insertion
begins.

**Interfaces between scales.**
- Molecule to membrane: a patch's conductance for a law is the sum over its populations
  of abundance times unit permeability; the patch area turns abundance into density.
- Membrane to cell: patches join a cytosol to outside compartments in the capacitor graph;
  capacitance follows the patch area and its domain's specific capacitance.
- Cell to tissue: cytosols, clefts and baths are the field's nodes; contacts and faces are
  its conductive edges. A topology event changes masks, which reach the field reduction
  through the view (§3.8).
- Tissue to lineage: only event operators write lineage, with stable carrier IDs that
  later stochastic laws can key their streams on.

## 3. Composition (the first question)

### 3.1 The problem

Both existing extensions wrap `resolved_pump_tissue@3` the same way:
- they extend its state with fields they own;
- they give @3's `checked_step` a **view** of its layout: current volumes (water), or each
  slot's template routes and junction availability × formation abundance (replacement);
- they split the step around @3's step behind `jax.lax.optimization_barrier`: W ∘ I ∘ W
  for water, F ∘ I ∘ F ∘ E for replacement (composition order: the event map E acts first, as in `cell_replacement.checked_step`);
- they add their terms to @3's own check functions.

Each wraps @3 alone: replacement wraps the fixed-volume model, and replacement over water
is unbuilt. Division needs replacement-like events, volume state, changing areas and
capacitances, a new compartment and topology changes. Building it as another wrapper
makes water + replacement + division a fourth model and mechanics a fifth. `src/cells/core`
still shows where that leads (for example
`surface_calcium_energy_water_repair_profile_barrier_interventions_spec.py`).

### 3.2 Proposal: one composite model and operators

- **One registered model** (working name `resolved_pump_composite@1`): an inner model
  (`resolved_pump_tissue@3`) plus an ordered list of operators, each with its own law ID,
  version and parameters.
- A run's identity is the composite ID, the inner ID and the ordered operator IDs. All of
  them enter the batch signature and the manifest.
- New combinations are definitions, not files. The registry stays explicit: one model ID,
  and one ID per operator law.
- A combination is not qualified by its parts. Each judged combination has its own
  protocol, and integration grants no acceptance (AGENTS.md).
- The composite is generic over inner models. An inner model qualifies when it exposes the
  family protocol @3 already has (state and layout types, `checked_step`, balances,
  magnitudes, `ledger_limits`, domain, observation) and has an entity adapter (§3.3).
  @3 is the first; another family joins by writing its adapter, not a wrapper.
- The object structure lives in specs and operator objects at build time. Each operator
  compiles to pure JAX functions over arrays, so the hot loop is unchanged in kind.

### 3.3 The operator contract

| Item | Meaning |
| --- | --- |
| Owned state | Fields only it writes (for example formation lag, bridge aperture) |
| Entity writes | Shared entity fields it changes, each through its own accumulator, so the entity ledger closes: Δx = Σ over writers of their booked contributions |
| View fields | Inner-layout fields it provides from state. Each field has exactly one provider; availability multipliers combine as a declared product. The composite refuses a definition with two providers of one field |
| Kind | **Event map** (at the start of the step leaving an event time); **split process** (half-steps around the inner step, on its own variables); **in-step membrane process** (through @3's existing opt-in membrane-process hook, as `resolved_pump_water@2`'s symport) |
| Ledgers | Terms added to the inner ledgers, its own ledgers, and the magnitudes for their rounding bounds |
| Domain and refusal | Its validity conditions. Any failure refuses the whole step, which returns the start state |
| Schedule | Event times (exact multiples of dt) and rate schedules, checked at the definition |

**The entity adapter.** The view fields for @3 are its layout names: `volume`,
`extracellular_volume`, `membrane_area`, `membrane_capacitance`, `initial_cell_charge_C`
(the charge anchors), `channel_abundance`, the route values replacement already provides,
the activity masks, and the field arrays derived from capacitances and masks
(`field_capacitor_matrix`, `_scale`, `_solve_matrix`, `_factor`, `field_fixed`,
`field_active`). One adapter module maps entity quantities onto these names and recomputes
the derived field arrays on the device when a capacitance or a mask changed in that step.
It never changes @3's code.

### 3.4 The step

```text
Phi_dt = P1(dt/2) o ... o Pm(dt/2) o I_dt[view] o Pm(dt/2) o ... o P1(dt/2) o E
```

- E: the event maps due at the step start, in the declared order. Two events on one slot
  at one time are refused.
- P: the split processes; I: @3's own `checked_step` at the view, behind the barrier.
- Water's W ∘ I ∘ W and replacement's F ∘ I ∘ F ∘ E are instances.
- The symmetric order is second order when each piece is, and it keeps an exact
  stationary state a fixed point when the pieces act on disjoint variables (the water
  model's argument).
- Geometry is frozen inside I, as the volumes are in water@1.

### 3.5 Checks

- Host and device use @3's own `checked_rows`, `row_checks` and `ledger_limits`, with
  @3's balances plus the operators' terms, as both wrappers do now.
- Without operators, every bound is @3's exactly.
- Energy is booked as the water model does it: @3's ledger on the declared layout, plus
  explicit operator terms (dilution, elastic, capacitor-energy correction, insertion heat,
  event free energies).

### 3.6 What changes in the existing models

- **`resolved_pump_tissue@3`:** no change to its physics or its code. The adapter (§3.3)
  is new code beside it.
- **`resolved_pump_water@1` and `@2`, `resolved_pump_replacement@1`:** they stay
  registered, qualified and unchanged as models. Their laws become operators:
  - water: the Heun half-step and the water ledgers;
  - replacement: the event map, the formation law and their ledgers;
  - symport: an in-step process.
- **Acceptance of the composite:** re-expressed through it, each of those three models
  is **bitwise equal** to the frozen model on its own test and qualification worlds. Only
  then may the old modules become thin compositions, which gives one implementation per
  law (decision 1). If the guard fails, they stay frozen and the composite carries new IDs.
- **Cross-operator meaning is declared at the entity, not inside a wrapper.** For example,
  replacement over water: the template declares the newcomer's volume, and the event books
  a volume removal and supply in the compartment's volume ledger.

### 3.7 Bitwise equality when off

Mechanisms:
- idle maps select the inner value, never add a computed zero;
- one barrier around the inner step;
- branches are static (by shape and the declared operator list), never by value;
- derived field arrays are selected from the bound ones unless something changed in that
  step.

Tests, on CPU:
1. the empty composition equals @3;
2. each idle operator equals the composition without it;
3. re-expressed water@1, @2 and replacement@1 equal the frozen models;
4. every division operator idle equals @3 on the 825-node world.

GPU runs keep bounded agreement only: repeat L4 runs were not bitwise in one observation.

### 3.8 Padded slots, topology changes, the field solve and vmap

- **Activation** flips masks in state at the event. The view passes them to @3's activity
  arrays and to the field's `fixed` and `active` masks. A slot can only be switched on if
  its anchors were declared for it (§5.2): a padded slot's zero reference amounts are not
  valid in @3's chemical-energy term.
- **Event maps** are gathers and scatters with static index arrays from the schedule.
- **vmap:** worlds batch when capacities and the operator list match. Event times,
  fractions and rates are per-world data.
- **Field topology.** @3 binds its capacitor components on the host, once.
  - First slice: every cell keeps a patch on a held bath (true for Xenopus to about
    16 cells), so every capacitor component contains a reservoir.
  - Activating a cell, patch or cleft node then changes masks, not components. The
    floating basis stays empty, and recomputing the capacitor reduction and its Cholesky
    factor on the device is enough. For at most a few dozen nodes this costs little per
    step.
  - Worlds with floating components (finite ECM without baths) would need topology
    epochs: host-bound field topologies stacked per epoch and selected by a control. They
    are refused for now, as G2 refuses them.
- **Triggers.** State-triggered divisions later use the same masks and event maps.

### 3.9 Later operators on the same contract

- **Growth:** material synthesis from a declared supply, volume through water with
  synthesised osmolytes, and area through the insertion operator with a growth-coupled
  rate.
- **Trigger:** a Cdk1 oscillator or a size law (state-driven events).
- **Mechanics** (`apical_vertex_mechanics@1`): it owns shape state and provides areas,
  volumes and contact geometry through the same view fields. A stretch changes
  capacitance at fixed charge, and the energy then goes to the mechanics ledger as work
  (§5.1).
- **Gene regulation and trafficking:** they write population abundances through the same
  ledgers. This closes the architecture page's gap "membrane abundance as state".

## 4. Operations and interfaces for division

### 4.1 Division as a process

1. **Smoothing (0 to about 7 min).** No operator acts: the real membrane area, the
   populations and the electrical state are those of the uncleaved egg (dLB74). The
   geometry of the groove is not modelled; nothing in the electrical data needs it.
2. **Insertion (about 7 min to partition).** At onset, the parent's cleft-facing patch
   (new-membrane domain) and the cleft compartment are activated with a small declared
   area. New membrane then grows at the declared rate; the cleft lumen grows with it.
3. **Partition (an event).** The parent becomes two daughters at a declared time (or a
   declared bridge aperture), because bridge closure was not measured. The step's explicit
   bound only refuses (§5.4): if the declared aperture is too wide for the step, the step
   is refused and needs a smaller dt. The event never moves with dt.
4. **Bridge closure.** The aperture shrinks to zero. Coupling then runs through the
   trans-cleft path (§7).
5. **Next division.** The same operators run on each daughter, each with its own furrow
   cleft joined to the first at the centre (geometry declared in the J2 protocol).

### 4.2 The four operators (working names)

**`furrow_membrane_insertion@1`** (split process on a patch; activation at onset)
- Law: dA/dt = r(t); dC/dt = c_new r(t); dN_k/dt = r(t) ρ_k for each population of the
  domain.
- Applied in half-steps at fixed free-node charges (§5.1).
- Ledgers: area inserted, abundance inserted, image-charge electrode transfer and its work,
  insertion heat H ≥ 0.
- Parameters: r about 0.04–0.06 mm²/min from about 7 min (dLB74 p536, S); total 1.39 mm²
  at onset of second cleavage (BdL73). c_new is not measured: 0.62 µF/cm², DFS74's
  whole-cell value on a smooth basis, as the default, with arms 0.4 and 1.0. ρ_k from the
  new membrane's 1.36–1.82 kΩ·cm² and selectivity (§6).
- Supply: membrane comes from internal stores (BdL73: ER cisternae open into the furrow;
  dense inclusions as possible precursor pools), booked from a declared unlimited reserve
  (a stated limit). Vesicle contents are not modelled.
- Refuses: negative area, a rate outside its schedule, retrieval (dA < 0).

**`restricted_cleft_lumen@1`** (split process on an outside compartment)
- Law: the lumen volume is V_c = w × (face area). The added volume fills with bath fluid
  at bath composition through the access face, booked as reservoir supply with its work.
- Access: one face to the bath, with free-solution diffusivities and one geometric factor
  A/L calibrated on Rm (§7).
- Parameters: w 1.5–2.5 µm (BdL73 TEM, F; fixation shrinkage unknown, arm 0.5 µm);
  diffusivities from standard tables (to be cited at build).
- Fixed lumen volume is the simpler arm.

**`isopotential_partition@1`** (event)
- Declares: time, parent slot, two fresh daughter slots (inactive until then, anchors
  declared at their expected content, §5.2), volume fraction f, area fraction a_k per
  patch, two new carrier IDs, the bridge contact and its initial aperture. The parent's
  slot is retired.
- Map: §5.2. Lineage: the parent's carrier ends; two daughters begin, with inheritance
  route "division".
- Ledgers: partition transfers of amount, volume, area and abundance between slots (they
  sum to zero); partition free energy; electrode transfer, checked to be zero.
- Refuses: an active daughter slot, a second event on either slot at that time, or a
  bridge conductance above the explicit bound (§5.4).

**`cytoplasmic_bridge_closure@1`** (split process on a contact)
- Law: the aperture a(t) shrinks linearly (or exponentially) from a_0 over a declared
  closure time.
- Electrical: an aperture in a thin wall has access conductance 2aσ. As the junction's
  constant-field law it becomes permeability × area = 2a D_s for each species, with
  cytoplasmic diffusivities (to be sourced).
- This is not G2's formation law: coupling falls here, where in G2 it rises.

**An instant split** (partition with no insertion phase) stays available as a declared
limit for tests. It is not the default.

## 5. Charge and energy laws

### 5.1 Growing capacitance (insertion)

Notation:
- free nodes f: cytosols, cleft lumens, finite outside nodes;
- clamped nodes b: held baths at potentials φ_b;
- the capacitor matrix K(C) = Σ_k C_k e_k e_kᵀ, with e_k the patch's cell-minus-outside
  incidence; node charges q = Kφ.

**Law.** An insertion step C → C' = C + ΔC (ΔC ≥ 0) conserves the free-node charges q_f
and keeps the clamp potentials. The inserted membrane arrives uncharged: fusion adds no net
charge to the cytosol or to the outside fluid. The redistribution current flows on the
patch's RC time (milliseconds), far faster than insertion (minutes).

**Consequences.**
- **Potentials:** φ_f' = K'_ff⁻¹ (q_f − K'_fb φ_b).
- **Image charge:** each clamp supplies Δq_b = q_b' − q_b, booked as electrode transfer
  with work W = Σ φ_b Δq_b, exactly as replacement books its image charge.
- **Second law:** the capacitor free energy G = ½ q_fᵀ φ_f − ½ q_bᵀ φ_b equals
  max over φ_f of [q_fᵀ φ_f − ½ φᵀ K φ]. By the envelope theorem,
  ∂G/∂C_k = −½ (Δφ_k)² ≤ 0 at fixed q_f and φ_b. So H = G(C) − G(C') ≥ 0 for any
  insertion, and it is booked as **insertion heat**, a new nonnegative dissipation field.
- **Energy:** the capacitor energy then obeys ΔU = W − H, which closes the energy ledger.
- **What the voltage does:** a one-patch cell's |Vm| falls by the factor C/(C + ΔC) and
  recovers on τ = RC, with H = ½ q² ΔC / (C (C + ΔC)). For the egg, ΔC/C is about 2e-7 per
  1 ms step, so the jumps are nanovolts. The law matters for the ledgers, not for the
  trajectory.
- **Retrieval** (ΔC < 0, endocytosis) would need supplied work −H ≥ 0 from a declared
  source. It is refused in the first slice.
- **The same term, a different owner.** In a mechanical stretch (later), −ΔG is electrical
  work done on the mechanics (Maxwell stress), booked in the mechanics ledger rather than
  as heat. The operator decides the booking; the law is the same. This meets the
  architecture page's requirement that geometry changes account for capacitive work.

### 5.2 The partition

Parent P (amounts n, volume V, background X, patches k with charge q_k = C_k ΔV_k) becomes
daughters D1 and D2: volume fractions f and 1 − f, and patch k split into area fractions
a_k and 1 − a_k.

1. **Potentials are continuous.** The cytosol was one conductor, and the bridge closes
   slowly compared with τ = 25 ms, so both daughters start at the parent's potential.
   Outside potentials and outside node charges are unchanged, so no electrode charge
   moves.
2. **Charges follow the patches:** q_D1 = Σ_k a_k q_k.
3. **Amounts and background follow the volume:** n_D1 = f n + δ, X_D1 = f X. Here δ
   carries the mismatch δq = Σ_k (a_k − f) q_k, divided among declared carrier species in
   proportion to their cytosolic transference numbers (δ_s = t_s δq / (z_s F)). For a
   symmetric division (a_k = f = ½), δ = 0 exactly.
4. **Volume, reference volume and populations** split by their fractions. Gates are
   intensive, so both daughters' populations take the parent's gate state. Charge anchors
   are presented to @3 through the view.
5. **Conservation and energy:**
   - material and charge are exact;
   - capacitor energy is unchanged (same patch voltages, split capacitances);
   - elastic energy is unchanged when the reference volume splits with the volume;
   - chemical free energy changes only by the unmixing term in δ (≥ 0, about RT δ²/n),
     booked as **partition work** supplied by the unmodelled contractile machinery.

   A symmetric partition changes no energy at all.
6. **Anchors for slots that switch on.**
   - Padded slots hold reference amounts 0, volume 1 and charge anchor 0, and padded
     patches an initial voltage 0 (`surface_tissue.initial_values`). @3's chemical-energy
     term takes log(a/V) and log1p(δ/a) on the reference, masked only by activity, so a
     padded slot cannot simply be switched on.
   - **Rule for prescribed divisions:** both daughters take fresh slots, declared inactive,
     whose anchors are their expected content: reference amounts, volume and charge anchor
     f (or 1 − f) times the parent's declared ones. Their patches are declared inactive,
     and the event sets their split areas (patch area is state). The parent's slot is
     retired at the event.
   - Anchors stay immutable (D057). Active slots keep small increments (f times the
     parent's increment, plus δ). The whole-content transfer, about 4 × 10⁷ fmol per
     species for an egg, is booked once, on the retired slot, which no longer evolves.
   - The composite owns the capacitor-energy term (§5.3), so a patch's declared initial
     voltage does not matter.
   - Triggered divisions (later) cannot declare their anchors in advance. Setting anchors at
     the event is re-anchoring, a decision against D057; until it is taken, triggered
     divisions are refused.

### 5.3 Where each term is booked

| Term | Booked in | Owner |
| --- | --- | --- |
| Ionic transport, channels, faces, junctions, bridge | @3's route ledgers and dissipation | Inner step |
| Insertion: area, abundance, membrane supply | Insertion ledgers (supply from the declared reserve) | Insertion |
| Insertion: image charge, its work, heat H | Electrode ledger and work; insertion dissipation field | Insertion |
| Cleft growth: bath fluid drawn in | Reservoir supply and reservoir work; the compartment's volume ledger | Cleft lumen |
| Partition: transfers between slots | Partition ledgers, summing to zero; @3's local and total material get the terms | Partition |
| Partition: unmixing free energy | Partition work | Partition |
| Volume changes | Dilution and elastic terms (the water model's) | Water or partition |
| Capacitance change in @3's electric term | Correction ½ Σ (C_t − C_0) V_t², so the total is the true ½ Σ C_t V_t² − ½ Σ C_0 V_0² | Composite |
| Lineage | Lineage records | Event operators |

### 5.4 Numerics and scale

- **Split.** Geometry is frozen over the inner step and advanced in half-steps (§3.4).
  The capacitor reduction and its factor are recomputed on the device once per step
  that changed them.
- **Cleft stiffness, the main numerical risk.**
  - The new membrane's own time constant r_m c_m is 1.59 kΩ·cm² × 0.62–1 µF/cm² ≈
    1.0–1.6 ms.
  - The cleft node is tied to its cell by the new membrane (about 8.7 µS for 1.39 mm²)
    much more than to the bath by the access (about 1 µS). Its potential relaxes at about
    600–1,000 s⁻¹, so dt × rate ≈ 0.6–1.0 at 1 ms (S).
  - The family's explicit bound would not see this. It sums conductances over the cell's
    total capacitance (≈ 0.25 at 1 ms for the egg) and assumes outside nodes are held near
    equipotential by implicit drift, which a restricted cleft is not.
  - First numerical task: a step study of the cleft egg at 1, 0.5 and 0.25 ms against
    RK4. Outcomes: 0.5 ms, or an implicit membrane–cleft term as a new solver version.
- **Bridge stiffness.** A bridge of conductance G_b is an explicit junction term:
  dt × 2 G_b / C ≤ 1 gives R_b ≥ about 100 kΩ for a daughter of about 20 nF at 1 ms, an
  aperture of at most about 10 µm (for a cytoplasmic resistivity of about 2 Ω·m, to be
  sourced). This is a refusal condition only: a declared partition with a wider aperture
  refuses the step at 1 ms and needs a smaller dt. The 0.26 mm² bridge at onset of second
  cleavage (radius 0.29 mm, about 3.5 kΩ) is far wider, so the egg is rightly one
  compartment then.
- **Scale.**
  - With fresh daughter slots (§5.2), active slots keep small increments; the retired
    parent slot carries the whole content but no longer evolves. Without that rule, G2's
    RK4 electrode-ledger drift after 50 fmol swaps would be about 10⁶ times larger at egg
    scale. What remains is the rounding of the event map itself, a one-step transfer of
    about 4 × 10⁷ fmol, which needs an event magnitude allowance as G2's has.
  - The definition-check bound (§1.2) must be scale-aware before egg worlds are routine.
  - The material atol of 1e-10 fmol held over 60 s, but not yet with large increments over
    30 min.
- **Cost.** A 1 → 2 → 4 run is about 4 × 10⁶ steps at 1 ms: minutes per world on CPU with
  device checks, and impractical with host checks on every row (§1.2).

## 6. The frog membrane in the engine

| Domain | Biology | Engine representation | Source |
| --- | --- | --- | --- |
| Old (egg) membrane | 74 kΩ·cm² on the folded area; P_Na/P_K about 1; Cl⁻ substitution has no effect | Constant-field leak with P_Na = P_K and P_Cl = 0 (the smoke test reproduces −9.9 mV and 852 kΩ). As populations: Na and K leak laws (`naleak_always_open@1`, `kleak_always_open@1`), so that insertion and partition act on abundances | dL74; dLB74 Table I (V) |
| New (furrow) membrane | 1.36–1.82 kΩ·cm²; mainly K⁺; outward current reversed by 1 mM Ba²⁺; five-fold lower particle density | A K leak population plus a small Na leak, at P_Na/P_K ≈ 0.02–0.05. That ratio comes from the exposed arms' branch EMFs, −91 and −74 mV (S). Ba²⁺ is an availability schedule on the K population: a qualitative check against K83's reversal | dLB74 p535 (V); K83 Table II (V) |
| Pump | None detected at first cleavage: ouabain and ethacrynic acid without effect; pump current below 0.01 µA/cm² | `pump: null`, the route the smoke test used | dL74 p13; K83 p1760 (V) |

**Missing in the engine:**
- abundance as state, insertion, and the cleft (§4);
- a sourced voltage dependence for the new K conductance. Ba²⁺ sensitivity hints at an
  inward rectifier but does not establish one, so the default is an ungated leak. The
  existing Kir2.1 law is mammalian and serves only as a sensitivity arm;
- bound ions: dL74 reports about 60% of Na and 30% of K bound. The cytosol is declared on
  the measured activity basis, which is what the membranes see; a buffered pool is a later
  model;
- a peri-furrow old-membrane domain. K83's inward current is 4–30 times larger next to the
  new membrane, so the uniform old membrane cannot reproduce K83's spatial pattern (a
  stated limit);
- Ca²⁺ and Cl⁻ currents at the old membrane (K83): not needed for Em in the first slice.

## 7. The cleft

**A restricted compartment.** The cleft lumen is a finite outside node:
- the parent's new-membrane patch faces it, and after partition both daughters' patches
  do;
- one face joins it to the bath, with free-solution diffusivities and a single geometric
  factor A/L, so its electrical and diffusive exchange are consistent (Nernst–Einstein);
- A/L is calibrated on Rm of normal eggs at onset of second cleavage (488 kΩ);
- its volume is set separately, from TEM (gap w × face area).

**Why restricted, and why the restriction is not the open slab.**
- The Rm drop from 852 to 488 kΩ in normal eggs shows the new membrane does reach the
  bath, so the cleft is not sealed before partition. Yet only about 0.14 of 1.39 mm²
  acts as exposed (dLB74 p535).
- With all new membrane in the cleft (114 kΩ at 1.59 kΩ·cm²), the access must be about
  1 MΩ in series (S).
- An open slab of the fixed gap would give ρ/(8πw) ≈ 30 kΩ (w = 2 µm, ρ ≈ 1.6 Ω·m for
  about 60 mM NaCl; S, to be sourced). That is about 30 times too little.
- So the restriction sits at the rim, where the blastomere margins are apposed (dLB74:
  "the small drop in Em coincides with the moment at which the blastomeres become apposed
  more closely"), or the gap in vivo is narrower than in fixed tissue. Keeping volume
  (TEM) and access (Rm) as separate parameters covers both.

**Rm is defined operationally.** dLB74 measured it with 3 × 10⁻⁸ A pulses of 1.2 s
every 10 s, alternating in polarity (dLB74 p530), giving excursions of 15–25 mV on a
−10 to −20 mV membrane. Constant-field membranes rectify, strongly so for a K-selective
membrane facing low K⁺. Rm is therefore the simulated response to that same pulse
protocol, in the reference and in the engine. The linear-circuit numbers in this note,
including the −37 to −44 mV limit, are estimates only. **Engine gap:** the pump-tissue
family has no current-injection control, so the pulse protocol needs one, reported
before S3.

**How it predicts Em.** K⁺ leaving through the new membrane accumulates in the lumen and
lowers that membrane's driving force. The limits:
- fast exchange (a bath-equivalent lumen): the parallel-branch value, −37 to −44 mV;
- slow exchange (lumen K at equilibrium with the cytosol): Em tends to the old membrane's
  −10 mV.

The measured −20.3 mV lies between them. A normal egg's apparent branch EMF of −35 mV
would correspond to roughly 12 mM K⁺ in an otherwise bath-like lumen (S). Where the model
lands is set by A/L (from Rm), by w (from TEM) and by the access selectivity, not by Em,
so J1 can fail on either side. The selectivity is a declared assumption: free-solution
diffusivity ratios (Nernst–Einstein) by default. A rim seal about 30 times tighter than
the open slab need not have them, and that ratio sets K⁺ accumulation against electrical
conductance, which is what J1 judges. A cation-selective seal is the sensitivity arm.

The lumen's K⁺ exchange time V_c / (D_K A/L) is about 8 min (S), comparable with
insertion. The lumen is therefore not quasi-steady, and w must be pre-registered as a
band.

**The sealed reading and the shared parameter.** After partition, the trans-cleft path
(face, lumen, face) is the main route between blastomeres. Specialised junctions are
absent (Sanders & Zalik 1972, cited by dLB74), and DFS74 saw only point contacts.
- Sealed (A/L = 0): Rj = 2 r_new / A_face, so the membrane rule *is* the junction rule:
  they share r_new and A_face.
- Restricted: Rj follows from the T-network, R1 + R2 + R1 R2 / R_acc ≈ 0.4–0.5 MΩ for
  0.7 mm² faces, against DFS74's 0.286 ± 0.071 MΩ (S).

Either way Rj and the coupling ratio at 2 cells are tied to calibrated parameters. They
are reported as checks, not judged, and no gap-junction conductance is fitted. The same
compartment entity later serves the sealed blastocoel: its composition (Gillespie 1983)
and its potential (Slack & Warner 1973) are in the parameter table.

## 8. Validation

### 8.1 Judged observables

- **J1, first.** dLB74 Table I, normal eggs at onset of second cleavage.
  - Prediction: Em −20.3 ± 0.8 mV (SE, n = 20).
  - Calibration from the same eggs: Rm 488 ± 28 kΩ (n = 17) fixes A/L.
  - The egg is still one compartment then (bridge open, V2/V1 > 0.95), so J1 tests
    insertion and the cleft without the partition.
  - It fails if the cleft behaves like the bath (−37 to −44 mV), if the new membrane were
    identical to the old (about −10 mV), or if the cleft were sealed (Rm would stay near
    852 kΩ).
  - **Prediction of record.** Before any model produces an Em, the protocol fixes:
    - default values for the gap width, the access selectivity, the new-membrane
      capacitance and selectivity, and the insertion rate;
    - the declared ranges around them;
    - a maximum prediction band width.

    The first Em under the defaults, from the independent reference (R-full), is the
    prediction of record, whatever it is. If the ranges give a band wider than the
    maximum, J1 is reported, not judged.
- **J2.** DFS74 Table I blastomere Em at 2 cells (−15.5 ± 1.6 mV, SD, n = 9) and 4 cells
  (−16.0 ± 2.4 mV, n = 10).
  - Sampled at DFS74's phases: 2 cells after the second furrow began, 4 cells after the
    third.
  - The same laws are applied to each division, with no refit. The old membrane is set
    from DFS74's own 1-cell Em (Fig. 2, about −6 mV, F), a different batch from dLB74's
    −9.7 mV.
  - Needs the partition and the second furrow.
- **Reported, not judged:**
  - the time-course shape (its 6–8 min onset is tied to the declared insertion onset);
  - Rm per cell at 2 and 4 cells (1.05 and 1.80 MΩ);
  - Rj and the coupling ratio (tied, §7);
  - the −VM and +CCB arms (used for calibration);
  - K83's currents, which need an extracellular field around the egg (out of scope).

### 8.2 What calibrates and what is predicted

| Quantity | Set from | Source |
| --- | --- | --- |
| Old-membrane permeability (P_Na = P_K) | Rm 852 kΩ at onset of first cleavage; Em −9.7 mV checks the selectivity | dLB74 Table I |
| New-membrane specific conductance | 1.36–1.82 kΩ·cm² | dLB74 p535 (vitelline membrane removed; +CCB) |
| New-membrane selectivity | Branch EMFs −91 and −74 mV | dLB74 Table I, the same two arms (S) |
| New-membrane area and rate | 1.39 mm²; about 0.04–0.06 mm²/min from about 7 min | BdL73 Table II; dLB74 p536 |
| New-membrane capacitance | Declared 0.62 µF/cm², arms 0.4–1.0 (not measured) | DFS74 whole-cell value |
| Lumen volume | w 1.5–2.5 µm × face area | BdL73 micrographs (F) |
| Cleft access A/L | Rm 488 kΩ, normal eggs, onset of second cleavage | dLB74 Table I |
| Cleft access selectivity | Declared: free-solution diffusivity ratios; arm: a cation-selective seal | Assumption |
| Cytosol and medium | Activities | dL74 Tables 2, 4 |
| **Predicted:** Em of normal eggs at onset of second cleavage (J1); DFS74 2- and 4-cell Em (J2) | | |

### 8.3 Why it is not circular

1. Each input comes from another measurement:
   - the uncleaved egg (old membrane);
   - eggs whose new membrane is exposed (new membrane);
   - electron microscopy of other eggs (area, timing, gap);
   - ion-selective electrodes (activities).
2. A/L is fitted to one number, Rm, and Em is a different observable. With the
   bath-equivalent lumen the calibration already fixes Em at −37 to −44 mV, which
   disagrees with the data. The lumen's composition shift then follows from the same
   geometry under the declared access selectivity (§7), with no parameter fitted to Em;
   that selectivity is an assumption with its own arm, not a measurement.
3. J2 uses another laboratory's eggs, with the laws carried over unchanged.

### 8.4 Independent references for the division operation

- **R-ops (numpy):** insertion and partition maps written from §5's equations, not from
  the engine. They give potentials, charges, image charge, H, transfers and free energies
  on random states, as G2's R-ops did.
- **R-full (numpy/scipy):** an ODE of the one-cell egg with its cleft, and of the pair
  after partition. It uses constant-field membranes, a two-point Nernst–Planck access and
  the insertion schedule, written independently. It is compared on trajectories and on
  J1's state, as W1's and G2's references were.
- **Analytic limits:** the bath-equivalent lumen (parallel branches); the sealed lumen;
  one-patch insertion, V' = VC/(C + ΔC) with the H formula; a symmetric partition giving
  bitwise-identical daughters.

### 8.5 Engine checks

- Bitwise equality when off (§3.7).
- Every ledger, on host and device, at egg scale.
- Restart mid-insertion and across the partition, bitwise on CPU.
- vmap cohorts of 2 and 8 worlds within 1e-12 relative.
- Observed second order with ARS(2,2,2), once the stiffness study passes.
- Partition rounding at egg scale (whole-content increments, IMEX and RK4).

## 9. Build stages, costs and risks

| Stage | Content | Rough effort |
| --- | --- | --- |
| S0 (done) | Parameter table v2; scale smoke test | – |
| S0b (next, before the composer) | (1) R-full, the numpy/scipy reference of the cleft egg, and J1's prediction band from it under the declared defaults; (2) if a static cleft egg can be written as a plain `@3` definition (a new-membrane patch facing a finite outside node with one face to the bath), the step study at 1, 0.5 and 0.25 ms. An implicit membrane–cleft term would change the inner solver, so this is learned before S1; (3) Rm as the simulated pulse response, and the current-injection gap; (4) the smoke test extended to J1's 35-min horizon | 2–3 days |
| S1 composer | Operator contract, composite model, @3 adapter. Re-express water@1, @2 and replacement@1 bitwise now (D143); a model whose guard fails stays frozen. Tier gate | 2–3 agent-days |
| S2 membrane state | Areas, capacitances and abundances as entity state; insertion with the §5.1 law; capacitor factor on the device. Analytic and bitwise tests | 2 days |
| S3 cleft egg | Lumen operator and access face; the step study (stiffness); development calibration of A/L; R-full | 3 days, plus CPU hours |
| S4 J1 | Protocol registered before the run (tolerances: step term, reference term, w and c_new bands); judged run from a clean snapshot | 2 days |
| S5 partition | Partition, bridge closure, lineage and R-ops; 1 → 2 → 4 cells; J2 protocol and judged run | 3–4 days |
| Later | Trigger (Cdk1, then size), growth, C. elegans (PAR cortex), mechanics coupling | – |

Compute is small: at most 16 cells, about 4 × 10⁶ steps per run. Calibrating A/L takes
about 10–20 runs of 30 min of model time each.

**Risks:**
1. **Refactoring qualified models (S1).** Guarded by bitwise tests against the frozen
   models; the fallback is to leave them frozen.
2. **Cleft stiffness at 1 ms (§5.4).** The step study comes first; then 0.5 ms or an
   implicit membrane–cleft term.
3. **Egg-scale rounding:** the definition bound (found), whole-content increments after
   partition, and fixed floors over hour-long runs.
4. **Data:**
   - areas and resistances come from different eggs and media (1/10 against full
     Steinberg);
   - the gap is read off a figure, with unknown shrinkage;
   - new-membrane capacitance and bridge closure were not measured;
   - DFS74's sampling phase must be matched;
   - the 1-cell Em differs by batch;
   - within-cycle time courses are single traces.
5. **Model validity:**
   - a well-mixed cytosol in a 1.3 mm egg: K⁺ diffuses across 0.6 mm in about 6 min, so
     chemical gradients near the furrow are possible, although the cytoplasm is
     isopotential (dLB74's two electrodes agreed);
   - a uniform old membrane;
   - a held bath;
   - no vitelline-membrane mechanics;
   - a prescribed lumen volume with no water flow, although solute build-up in the lumen is
     what J1 judges.
6. **J1's power.** If the bands on w, c_new and the access selectivity make the prediction
   band wide, J1 is weak. Publish the band in the protocol, before the run.

## Appendix A. Parameter table v2

Files in `verification/`:
- `xenopus_parameters.v1.csv`: the stage-1 table, 76 rows, unchanged (sha256 `7d5928…f06a5`);
- `xenopus_parameters.csv`: v2, 104 rows (sha256 `b4b953…0a12`);
- `xenopus_parameters_v2_edit.py`: reads v1 and writes v2.

Each corrected row quotes its v1 value, source and mark in its note. Printed page numbers
were checked page by page against the PDFs, and agree with the J Cell Biol notes (for
example R_new and the 0.14 mm² on dLB74 p535, the smoothing passage on p538).

**Corrected in place (11 rows):**
- the folded egg area (basis 1.7 × the measured 5.11 mm²);
- the first-cleavage Em: dLB74 Table I, three arms, mean ± SE (n);
- the old-membrane resistance with its basis;
- the new-membrane resistance: 1.82 and 1.36 kΩ·cm², mean 1.59, with its inputs and the
  different-eggs and different-media caveats;
- the onset of the Em and Rm change, and the new-membrane appearance (full text; growth
  rate now obtained);
- the insertion-mechanism note (the total area is now obtained);
- conductances present (K83 full text; the TEA line dropped);
- the DFS74 specific-resistance note (area basis);
- the two abstract-level Em ranges (now pointing to Table I).

**Appended (28 rows):**
- geometric egg area, three arms;
- Rm at onset of first cleavage;
- Em and Rm at onset of second cleavage;
- the Em and Rm time course;
- coupling above 0.95 and isopotentiality during first cleavage;
- the bath-exposed new membrane (1148 ± 104 kΩ; 0.14 mm²);
- BdL73 Table II, four arms (1.39 ± 0.29 mm² normal);
- the 0.26 mm² bridge;
- the growth rate of about 0.04 mm²/min;
- the branch EMFs (S);
- new-membrane capacitance (not obtained);
- furrow depths;
- the gap of about 1.5–2.5 µm (F);
- the absence of specialised junctions;
- K83's medium and temperature, its seven Table I currents, Table II, the pump bound, and
  its time course and spatial pattern;
- the first-to-second cleavage interval of about 30 min (F).

**Flagged in the rows:**
- K83's tangent-plane current gives n = 15 in Table I but n = 9 in the text;
- "a factor of about 1/3 per 100 µm" and "< 0.01 µA/cm²" are read from an imperfect text
  layer;
- K83's DOI follows the J Cell Biol volume.issue.page pattern and was not checked online.
