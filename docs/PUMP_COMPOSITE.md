# The composite pump-tissue model and its operators

`resolved_pump_composite@1` runs `resolved_pump_tissue@3`'s own step at a view of its
layout, plus an ordered list of declared operators (D142, D143). Water, cell replacement
and, later, division, growth and mechanics are operators; a new combination is a
definition, not a new model family. Design: [cell-division design note §3](CELL_DIVISION_DESIGN.md#3-composition-the-first-question).
Status and runs: [Progress](../PROGRESS.md).

Files:
- `src/cells/core/pump_composite_spec.py`: the definition and `frozen_definition`;
- `src/cells/models/pump_composite.py`: the composite (one cached implementation per
  inner identity and ordered operator list);
- `src/cells/models/pump_composite_adapter.py`: the @3 entity adapter;
- `src/cells/models/operators/`: the contract and the operators;
- `validation/tissue/composite_guard.py`: the bitwise guards against the frozen models;
- `validation/tissue/composite_crossrev.py` and `composite_dump.py`: the cross-revision
  guards of the thin modules (compiled programs and bindings; saved runs).

**Status: development.** Integration grants no acceptance. A composition is not qualified
by its parts: unqualified combinations run as labelled development runs
(`composition_status` in the summary), and judged status comes only from a registered
protocol for that composition (D143).

## Definition

The model holds `resolved_pump_tissue@3`'s own fields (parsed by @3's parser) plus
`inner_model` and `operators`, an ordered list of operator blocks, each naming its `law`.
The experiment adds each operator's schedule under the operator's own keys:

| Operator law | Block | Experiment key | Frozen model it re-expresses |
| --- | --- | --- | --- |
| `ideal_osmosis_linear_compliance_water@1` | `compartments`, `baths`, `membranes` | `water_controls` | `resolved_pump_water@1` |
| `k_anion_symport_mass_action@1` | `volume_factor`, `roles`, `routes` | `symport_controls` | `resolved_pump_water@2` (with water before it) |
| `scheduled_cell_replacement@1` | `junction_formation`, `templates`, `template_capacity` | `replacement_events` | `resolved_pump_replacement@1` |

The blocks and keys are the frozen models' own, so `frozen_definition(raw)` rewrites a
`resolved_pump_tissue@3`, water@1, water@2 or replacement@1 definition as the equivalent
composition. The run identity (composite ID, inner ID, ordered operator IDs) enters the
batch signature, the summary and the run manifest (`composition`).

## The operator contract

`src/cells/models/operators/contract.py` (design §3.3, with the additions found in S1):

| Item | Declaration |
| --- | --- |
| Owned state | `STATE_AXES` (only this operator writes them); heat and work fields declared, since the energy flows read the `_dissipated_energy_pJ` and `_work_pJ` suffixes by name |
| Entity writes | `ENTITY_WRITES`: inner state fields it changes, each with the owned accumulators that close the inner ledgers; `STATE_RESETS`: intensive kinetic state set at events (gates), which has no ledger |
| View fields | `VIEW_FIELDS`: @3 layout fields it provides from state, one provider each; `CONTROL_FACTORS`: @3 availabilities it multiplies (a product in declared order); `CONFLICTS_VIEW`: fields it reads as declared, which no other operator may provide |
| Parts | event map (`EVENT`), split process (`SPLIT`, with its RK4 mode `coupled` or `split`), in-step membrane process (`PROCESS`, through @3's opt-in hook, at most one per composition). One law may contribute several parts |
| Ledgers | terms added to @3's ledgers and rounding magnitudes, its own ledgers with their bounds |
| Domain and refusal | its domain and control validity (any failure refuses the step, which returns the start state); `REQUIRES` (laws that must precede it) |
| Schedule | its experiment keys, parsed and checked at the definition (event times exact multiples of dt) |

## The step

For IMEX inner steps, `Phi_dt = P1(dt/2) o ... o Pm(dt/2) o I_dt[view] o Pm(dt/2) o ... o P1(dt/2) o E`:
the event maps first, then the split parts' first halves in declared order, @3's own
checked step at the view behind `jax.lax.optimization_barrier` (or @3's IMEX step with the
in-step process, whose applied transfer and heat the operator books), then the second
halves in reverse order. Idle parts select the inner value; branches are static (operator
list and layout shapes). The empty composition is @3's step itself.

For RK4 (reference runs), a composition with a `coupled` split part or an in-step process
integrates the coupled right-hand side unsplit, as water@1 and water@2 do; it refuses
event maps, `split`-mode parts and integer state. Otherwise the events and exact halves
stay around @3's own RK4 step, as replacement@1 does.

The @3 domain is evaluated at the view of the providers whose view follows their split
part (the current volumes), and re-checked at the step end when one exists; event-driven
route views keep @3's zero pattern, as the frozen models assume.

## Checks and observations

Host and device use @3's own row checks with @3's balances on the declared layout plus
the operators' terms in declared order, the operators' own ledgers after @3's, and the
dissipation fields with the operators' heat. Without operators every check is @3's.
Observations are @3's at each row's view (with factored availabilities held at their
effective values), then each operator's columns; an operator may override the energy
columns (water@2 does).

## The entity adapter

The adapter maps operator-provided entity quantities onto @3's layout names and
availabilities onto @3's controls. When an operator provides a capacitance or an activity
mask, it recomputes the derived field arrays (capacitor matrix, scale, solve matrix,
Cholesky factor, fixed and active masks) on the device and selects them only where an
input changed that step. That path covers held-bath topologies only (no floating
components) and is not used by any S1 operator: it is unit-tested against
`surface_field.bind`, not exercised in a run.

## Equivalence with the frozen models (design §3.7)

Bitwise means every compared state field, observation column and `max_` diagnostic equal
under `np.array_equal` (NaN-aware), as the frozen models' own equivalence tests compare;
wherever the guards record bit patterns, they were identical. Every run, its snapshot and
result: `/mnt/workspaces/Cells/composite-s1-20261111-01/README.md`.

- **(a) The empty composition equals `resolved_pump_tissue@3`**
  (`tests/unit/test_pump_composite_identity.py`): heredity cell and seven-cell sheet with
  Euler and ARS(2,2,2), uncompiled, @3's padded reference world, RK4, a vmap batch and
  restart; and the 825-node world (200 steps). Its checked step is @3's own.
- **(b) An idle operator equals the composition without it:** closed water equals the
  empty composition; a symport with no route or every route blocked equals water alone;
  replacement without events equals the empty composition (Euler, ARS(2,2,2), RK4); on
  the 825-node world, closed water and event-free replacement equal @3.
- **(c) Re-expressed water@1, water@2 and replacement@1 equal the frozen models** on their
  test worlds (`test_pump_composite_water.py`, `test_pump_composite_replacement.py`) and
  on their qualification worlds (`validation/tissue/composite_guard.py`, run detached):
  - W1: the six judged trajectories through the judge's windowed path, the P2 stationary
    states (right-hand side, Jacobian and 4-step map at the guesses and the Newton
    solutions) and a 60 s drift from the stationary H state;
  - W2: all eight arms (the same evaluations at every predicted branch, and 1 s
    trajectories);
  - G2-Q1: the nine cases with the device row checks of every row, W37, and Q6's cohorts
    as vmap batches;
  - the 825-node world with closed water and with event-free replacement.

  The dt studies (W1's; G2-Q1's Q5, of which two of eight worlds ran, equal) were not
  repeated. Each world of both studies, traced at 1 ms with dt as an argument, gives
  identical jaxprs for the checked step, right-hand side and device checks; its bound
  inputs (initial state, layout, controls at every change time) have the same shapes and
  dtypes at every step size of the studies and are identical, frozen and thin, at each
  (`composite_crossrev.py`, qualification set). So each step size runs the same program on
  the same inputs. The device checks' constants, which depend on dt, come from @3's own
  function in both.
- **(d) Restart and vmap identity:** restart is bitwise, before, at and after events; vmap
  batches equal the frozen models' batches.

**Thin compositions.** Since the conversion, `frozen_definition` and the thin modules run
one composition, so the guards above would compare the composition with itself. The
comparison with the earlier implementation is across revisions, from the frozen snapshot
against the converted tree:
- `validation/tissue/composite_crossrev.py`: the jaxprs of the checked steps (IMEX and RK4),
  right-hand sides and device checks, traced with dt as an argument, are textually
  identical, and every initial state, layout and control array is identical, on small
  worlds of every structure and on every guarded qualification world (W1, W2, G2-Q1, W37,
  the 825-node world);
- the W2 judge (all eight arms) and W1's stationary phase give identical outputs;
- `validation/tissue/composite_dump.py`: saved runs of short worlds of every structure and
  W2's 1 s trajectories are bit-identical;
- the frozen models' own test files (130 tests) pass unmodified against the thin modules.
