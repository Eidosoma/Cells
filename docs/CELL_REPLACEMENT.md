# Scheduled cell replacement for the pump-channel family

`resolved_pump_replacement@1` is `resolved_pump_tissue@3` with scheduled carrier
replacement. It is opt-in ([D136](DECISIONS.md)); the default engine is unchanged.
Design, literature and the probe of @3's checks:
`/mnt/workspaces/Cells/cell-replacement-g2-20261111-01/design-note-G2.md`. Status and
runs: [Progress](../PROGRESS.md).

**Implementation (D143).** `resolved_pump_replacement@1` is a thin composition of the
[composite pump-tissue model](PUMP_COMPOSITE.md): `resolved_pump_composite@1` with the
operator `scheduled_cell_replacement@1`. The event map, the formation half-steps and the
ledgers moved unchanged into `src/cells/models/operators/cell_replacement.py`; the model
module re-exports them. The definition format, the step, the checks and the qualified
scope below are unchanged. Before the conversion the composition was bitwise equal to
the earlier implementation on the model's test and qualification worlds (evidence:
`/mnt/workspaces/Cells/composite-s1-20261111-01/`).

Files: `src/cells/core/cell_replacement_spec.py` (definition),
`src/cells/models/cell_replacement.py` (model), the junction law
`src/cells/processes/junction_formation.py`, worlds
`validation/tissue/cell_replacement_fixtures.py`.

## The operation, `scheduled_cell_replacement@1`

An event names a time (an exact multiple of dt inside the horizon), a slot (a cell),
a declared template and a new carrier ID. At the start of the step leaving the event
time:

- **Removal.** The occupant's amounts go to `replacement_removed_fmol` (a waste ledger;
  the contents leave the system: extruded or phagocytosed, not released).
- **Supply.** The template's amounts go to `replacement_supplied_fmol`. The slot takes
  the template's amounts and channel gates, and its route values (the newcomer's own
  parameter draw, if the template declares any).
- **Junctions at the slot** restart the formation law (below). Their gate is set by
  `gate_at_arrival`.
- **Charge and energy.** The held baths' image charge is booked as electrode transfer
  with its work. The net charge supplied goes to `replacement_charge_C`. The change of
  chemical and capacitor free energy, less that work, goes to
  `replacement_free_energy_pJ`.
- **Identity.** The slot's `generation` and `occupant_template` advance; `summarize`
  returns the lineage (carrier, slot, predecessor, successor, birth, death, template).

The row at the event time is the departing carrier's last state; the next row is the
newcomer's first. A refused step returns the state before the event.

**Templates** are declared newcomer states: amounts of every species (fmol) for one
volume and fixed charge background, the gates of each gated channel law, and optional
intensive route values (channel permeability and abundance per law, leak permeability
per species, Na/K and Ca pump capacity per membrane area). The intended template is
the newcomer's isolated steady state, computed by the driver; the engine draws
nothing. A template may only replace a slot's existing routes, by positive values, on
a slot of the same volume and fixed charge background.

## Newcomer kinds (D139)

Each event declares its newcomer kind, and the lineage records it.

- **`isolated_template`.** The newcomer is a declared template: no state is inherited.
- **`donor_copy`, an inheritance route.** It models a newcomer born by a neighbour's
  division.
  - **What is copied.** The newcomer takes the amounts and channel gates that a
    declared donor (a cell sharing a junction with the slot) holds at the event time,
    before any event at that time. Gates are copied by channel law.
  - **Route values.** They are the slot's own, or those of a declared route-only
    template.
  - **Supply.** The supply is the copied amounts. The donor keeps its contents and its
    volume.
  - **Lineage.** The record carries `inheritance_route`, the donor and the donor's
    carrier at the event time.
  - **Admission.** The donor must have the slot's volume and fixed charge background,
    and exactly one population of each gated law the slot has.

**Limit of donor copies.** A real division halves the parent's contents and volume. The
daughters then grow back, and mitotic cells swell and condense along the way
(Zlotek-Zlotkiewicz et al. 2015, J Cell Biol 211:765; Habela and Sontheimer 2007, Cell
Cycle 6:1613). Restoring the donor needs cell growth, which is out of scope, so the
donor is not depleted. The copy models a division-born newcomer's composition, not the
division's mass balance.

## Junction formation, `delayed_first_order_junction_formation@1`

A newcomer's junction channels are new: the departing cell's plaques leave whole as
annular junctions, and new channels form from connexons docking at plaque margins.
Coupling appears after minutes and grows over tens of minutes; connexin half-lives of
1.3–5 h bound de novo formation (sources in the design note and in the law's
docstring). The relative abundance A of each junction at the slot follows

```text
A(age) = 1 - (1 - A0) exp(-max(0, age - lag) / tau)
```

and multiplies the junction's availability; the voltage gate keeps its own law.

| Parameter | Declared | Default (E07 redesign proposal) |
| --- | --- | --- |
| `initial_abundance` A0 | [0, 1] | 0 |
| `lag_s` | ≥ 0 | 600 s (range 2–20 min) |
| `time_constant_s` tau | ≥ 40 s | 1800 s (range 15–60 min; de novo arm 2–7 h) |
| `gate_at_arrival` | `law_open` (law value at Vj = 0) or `law_steady` (steady state at the post-event Vj, one extra field solve) | `law_open` |

Newly formed channels take the junction's current gate state. That is exact only when
formation is much slower than gating (at most about 0.4 s), hence the 40 s floor.
Pre-screen 9's driver rules (a) and (c) are the limit A0 = 1, lag 0 with `law_open` and
`law_steady`. Its "inherit" rule, gate state carried across a replacement, has no
mechanism in the literature and stays excluded (D139).

## Time integration

Each step is: the event map; the exact formation update over dt/2; @3's own
`checked_step` on the occupant view of the layout with junction availability × A,
behind `jax.lax.optimization_barrier`; the exact formation update over dt/2. A is held
at its step-midpoint value inside @3's step.

## Checks

Host and device use @3's own row checks (`surface_pump.checked_rows`,
`surface_pump_checks.row_checks`, `surface_pump.ledger_limits`) with @3's balances plus
the replacement terms: local and total material (+ removed − supplied), global charge
(+ replacement charge) and energy (− booked free energy). Rounding magnitudes add the
replacement terms; without events every bound is @3's exactly. The domain adds the
replacement fields (generation within the schedule, formation state, signed ledgers).

## Equivalence with resolved_pump_tissue@3

Without events, every @3 state field, observation and check diagnostic equals @3's run
bitwise, and every replacement field is zero (`tests/unit/test_cell_replacement.py`).
This is tested on:

- the heredity sheet with IMEX Euler and ARS(2,2,2), compiled and uncompiled, and with
  RK4;
- @3's padded reference world, which has finite outside nodes, faces, Ca pumps, a gauge
  and a mid-run channel release (ARS(2,2,2)).

The 825-node world was not compared.

## Limits

- Inner model `resolved_pump_tissue@3` only; the water model is stage 3.
- A replaced slot needs a held bath (a reservoir node) in its capacitor component, as in
  the heredity sheets. A gauge node alone is refused: the field law holds a floating
  component's net charge, and an event changes it. Finite-ECM worlds come later.
- **RK4 and large charge displacements.** After a whole-content swap, a slot's amount
  increment (against the founder's reference) is about 50 fmol. Each step rounds it by
  eps times that, which moves the slot's charge by about 1e-24 C.
  - IMEX books the electrode charge from the rounded states and telescopes.
  - RK4 integrates it from stage currents, so the plate charge and the electrode sum
    random-walk apart. Diagnosis (`rk4-electrode/` in the design directory): this is
    rounding, not a booking error, and the plate-charge evaluation is exact to 1.5e-33 C.
  - The wrapper gives the electrode ledger a running allowance for the replaced cells'
    charge magnitude at their held nodes (`replaced_charge_magnitude`). It is zero for
    founders, so bounds without events stay @3's exactly.
  - The same effect is latent in @3's RK4 path; it is recorded in PROGRESS, and @3 is
    unchanged.
- In-place swap only: no vacancy, no release of contents, no neighbour uncoupling.
- No stationary-analysis projection (stage 3) and no projective mode.
- **Regression against pre-screen 9 (development).**
  - **R1, rule (a).** Three open-rule turnover runs give identical D sets and stop
    times, with voltages within 1.3e-10 mV.
  - **R1, rule (c).** All eight steady-rule single-newcomer screens give identical
    outcomes and latencies, with voltages within 2.3e-11 mV.
  - **R2.** The rule (a) runs through the row-checked runner with
    `trapezoid_nonnegative@1` show no refusal and identical D sets.
  - The drivers are `validation/tissue/cell_replacement_r1.py`; the evidence is in the
    design directory's `r1/` and `r2/`.
- **Qualified under protocol G2-Q1** (registered with frozen predictions and pinned
  tolerances; judged once from a clean snapshot; 7 of 7 items pass):
  - ledgers on host and device;
  - the event map against an independent operator;
  - trajectories against an independent reduced reference;
  - the reduced chain's end states;
  - observed second order;
  - restart and vmap identity;
  - no-event bitwise equality with @3 on the 825-node world.

  The scope is held-bath heredity worlds, IMEX ARS(2,2,2) at 1 ms, with
  `trapezoid_nonnegative@1`. Evidence is in the design directory's
  `qualification/judged-01/`.
