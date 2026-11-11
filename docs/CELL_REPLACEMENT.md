# Scheduled cell replacement for the pump-channel family

`resolved_pump_replacement@1` is `resolved_pump_tissue@3` with scheduled carrier
replacement. It is opt-in ([D136](DECISIONS.md)); the default engine is unchanged.
Design, literature and the probe of @3's checks:
`/mnt/workspaces/Cells/cell-replacement-g2-20261111-01/design-note-G2.md`. Status and
runs: [Progress](../PROGRESS.md).

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
`law_steady`. Its "inherit" rule has no mechanism in the literature and is not offered.

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

## Limits (stage 1)

- Inner model `resolved_pump_tissue@3` only; the water model is stage 3.
- A replaced slot needs a held bath (a reservoir node) in its capacitor component, as in
  the heredity sheets. A gauge node alone is refused: the field law holds a floating
  component's net charge, and an event changes it. Finite-ECM worlds come later.
- **RK4 with large charge displacements.** RK4 reference runs pass with small charge
  displacements, such as H newcomers in H slots. A D↔H swap displaces about 1e-12 C on
  the slot. @3's RK4 electrode ledger integrates the electrode current, while the check
  recomputes the plate charge. After such a swap that ledger exceeded its relative
  bound (2e-12) by about 4% within 30 steps.
  - The IMEX steps telescope the electrode charge. In one IMEX run (127-cell sheet,
    three D→H swaps, 2800 steps after the events) the electrode residual stayed at
    zero and every ledger at or below 0.2% of its bound
    (`cell_replacement_cost swap`). Hour-scale IMEX runs are not yet measured.
  - The booked image charge gets the family's per-step running allowance.
  - The RK4 case is open for stage 2.
- In-place swap only: no vacancy, no release of contents, no neighbour uncoupling.
- No stationary-analysis projection (stage 3) and no projective mode.
- Not yet qualified: R1 regression against pre-screen 9, independent references and
  the qualification protocol follow (stage 2). R2 waits for the junction-heat option.
