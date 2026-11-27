# FR-45 addendum: the ledgers and host checks [B3, S-b]

Dated 27 November 2026. Drafted by FR-45's builder for TABLE.md §4 and §14.1 item 2. A reviewer who is not the
builder confirmed it against `src/` [N2], with one correction to the list's source, made here. The lead hashes it
before any registered run.

The judge reads the list by world from `checks-list-2026-11-27.json` (`--checks-list`). A completed honest run
fails C10 if its `checks` lacks a check listed for its world, or records a failure (§4) [B3; §8.3].

## The list, by world

Every world (W1, W1eq, W1p, W2, W3, W3p, W4, W5, W6, W7, W7s) evaluates these fourteen checks:
- `domain`;
- `local`, `outside`, `total`;
- `charge`, `electrode`, `global_charge`;
- `energy`, `reservoir_work`, `electrode_work`, `metabolic_work`;
- `site_bound_entity`, `site_moiety_entity`;
- `dissipation`.

W2 and W7 also evaluate `wash_ions`. A plant run evaluates its world's list.

The list is the engine's own: the composite model's `DEVICE_CHECKS`, as each parse-only pass records it from the
world it parsed (`driver.py parse`, at bc201ec8). It comes from `cells.models.pump_composite`, where
`self.DEVICE_CHECKS = ("domain", *self.LEDGERS, "dissipation")` and `LEDGERS` is the inner model's followed by each
declared operator's. The JSON keeps the engine's order, so W2's and W7's lists end `…, site_moiety_entity,
wash_ions, dissipation`. C10 reads each list as a set. A run's `checks` takes the same list, from its own model.

## Where each comes from, and where `definition` records it

| Checks | Brought by | `definition` records |
| --- | --- | --- |
| `domain`, `dissipation` | the inner model, `cells.model.resolved_pump_tissue@3` (`cells.models.surface_pump`: `DEVICE_CHECKS`); `dissipation` reads every operator's monotone heat fields (`DISSIPATION_FIELDS`) | `model.inner_model` and `model.operators` |
| `local`, `outside`, `total` | the inner model's material ledgers | `model.inner_model`; their bounds from `execution.material_balance_atol_fmol` (each species') |
| `charge`, `electrode`, `global_charge` | the inner model's charge ledgers | `model.inner_model` |
| `energy`, `reservoir_work`, `electrode_work`, `metabolic_work` | the inner model's energy ledgers; the site operator books its free energy into `energy` | `model.inner_model`; the energy tolerance from `execution.solver` (`surface_pump.ENERGY_RTOL`) |
| `site_bound_entity`, `site_moiety_entity` | `cells.operator.site_occupancy@1` (`LEDGERS`) | `model.operators[law=cells.operator.site_occupancy@1]` |
| `wash_ions` | `cells.operator.scheduled_compartment_wash@1` (`LEDGERS`), its `ions` `same_as_compartment` | `model.operators[law=cells.operator.scheduled_compartment_wash@1]` |

The definition holds no separate list of checks and no check's mode. Every check on this path raises, and has no
other mode [§8.3]. No `energy_check` is selected: X2 is waived for FR-45 (D412).

## Cadence: each step

The driver runs `iter_windows` with `WindowPolicy(1, "full")`: one step a window, every row recorded, and
`row_checks` at its default `"host"`. On that path every accepted row is checked by the model's `check_values`
(`cells.execution.windows`: `WindowPolicy`'s note, and `_observation_tail`). So every check above is evaluated at
each step, against the row before it, and not only at the saved rows.

A failure raises `NumericalError` with the check's message (the refusal mapping). The driver records it in
`checks[<name>].failures` as `{"step", "message"}`, with `step` the steps completed, and refuses the run [E3].
