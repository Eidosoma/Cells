# The deterministic representation's records (`cells.rate_equations@1`)

OL6 (D304); the design is docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md (tag
`ol6-design-note-2026-11-22`). A definition chooses this representation with
`execution.representation`; the world, its id and its laws are the same as for exact events.

## The definition

```json
"execution": {
  "backend": "cpu", "precision": "float64", "mode": "single_lineage",
  "stream": {"seed": 1, "environment": 0, "lineage": 0, "branch": 0},
  "representation": {
    "id": "cells.rate_equations@1",
    "envelope": {"min_count": 1000, "provenance": "..."},
    "integrator": {"id": "rosenbrock_rodas4_dense@1", "rtol": 1e-8, "atol_count": 1e-3,
                   "step_limit": 1000000}
  }
}
```

- `molecule_capacity`, `chunk_events` and `unroll` do not apply, and are refused.
- `mode` is `single_lineage` or `population` (a world with a `cells.shared_pool@1` block of at most
  64 slots), as the world's population block says.
- The experiment block is the exact run's. `event_limit` and `row_every_events` are stated as not
  applicable in the record; `trace`, `uniforms` and `diagnostic` are refused when true.
- Slices S1 to S3 run OL1's laws, the bilayer geometry, the osmotic lumen, lysis, the shared
  pool, shear fission, serial transfer, the pore law's clock (`cells.pore_nucleation@1`) and held
  tensions (`cells.tension_hold@1`). FR-21's shell, FR-20's replacement and FR-35's withdrawal are
  refused in version 1.
- **The pore law's tension** is a hold's (the experiment's `tension_holds`, with tension_hold's
  cross-checks as for exact events) or, with no hold, the osmotic lumen's (σ from F, which needs
  σ_max ≤ σ_β/4). Under a hold, a step that changes a membrane place's count is refused (T2); with
  σ from F such steps are admitted, which exact events refuse until the clock moves onto the
  device (OL6 S4).
- **The clock's bound** (D309, which replaced the absolute 1e-10 of the note's §3.5). Each
  accepted step's embedded estimate U^H of a vesicle's clock error is at most 1e-10 + 2e-3 |ΔH|,
  ΔH that step's own increment of the vesicle's clock H, or the run is refused. The absolute part
  governs the steps before the clock is live (ΔH near 0). By the estimate, the relative part
  bounds a crossing time's relative error by about 2e-3 while the clock's rate rises (D309; S3
  measured the estimate overstating the actual error about 200-fold). H is out of step
  selection, so a world whose rate is very sensitive to its state (σ from F near the lumen's
  kink) still needs tight tolerances: rtol 1e-12 with atol_count 1e-9 in the slice's own test
  world and in Protocol D's vesicle worlds.

## run.json (`cells.rate_equations_run@1`)

| Key | Contents |
| --- | --- |
| `world`, `model`, `definition_sha256` | As for exact events: the world's id, `cells.assembly_lineages@2`, and the definition's fingerprint |
| `engine_models` | The world's laws and operators, and `representation: cells.rate_equations@1` |
| `representation` | The declared envelope and integrator; `formulas`; `statuses`; `not_applicable`; and `statistics`: steps accepted and rejected, `restarts` (the lumen's kink), `crossings` (located roots), rtol, atol, the end time, `stop_reason` (`envelope` or `floor` for `outside_envelope`) and `schedule_draws` (Poisson gaps on domain 6, as exact) |
| `conventions` | The world's tokens, echoed |
| `laws` | Each law as an exact run states it (id, interface, formulas, provenance, test), plus its `limit_formulas`; a law with no limit kernel (the bilayer geometry) states the representation's rule for it |
| `status` | One of `complete`, `lysed`, `outside_envelope`, `stalled`, `step_limit`, `slots_full` |
| `events` | The vesicle-level events in order: each lysis (time, slot, key, cause, `at_birth`, σ and σ_max, what returned to each pool place, its heat and reservoir work; a pore's rupture, cause `pore`, also records the hold or null, σ, the area, k_v, `threshold_E`, `counter` 0, `clock_H` at the located crossing, `work_kT` (the hold's, 0 with σ from F), `opening_heat_kT` and `delta_F_kT`, and books its release from the open state); each fission attempt (time, schedule, k, slot, parent key and counts, outcome; for a split its daughters' keys and counts, the followed daughter or −1 in a population, their slots, the shear work, the sink, and each daughter's lysis at birth); each transfer (time, schedule, its domain-6 draws, kept and removed slots, sink and work) |
| `ledger` | At every row: `free_energy_kT` (F_cont with each living vesicle's closure cost), `residual_kT` (F_cont(n_t) − F_cont(n_0) − (W − Q − S)), `tolerance_kT`, and `closes`; a run whose ledger does not close is refused |
| `moieties` | The moiety names, the largest relative drift of Σ_finite m·n − Σ_held m·supplied plus what left with the sinks (net of a transfer's fresh pool), its tolerance (1e-12) and `closes` |
| `dissipation` | The smallest per-step margin of −J_r ΔF_r at the accepted states, its tolerance and `holds` |
| `check` | The limit's check: the generic verdict (six probes, items 1 to 3 and parity's fitted orders) and the world's own items 1 to 3 |
| `rows` | The row count, their kinds and the world's place names |
| `pores` | Pore worlds only: the exact run's block (pore_clock.block: the law, its parameters, units and derived constants, the ruptures and the lyses counted by cause), with `reads` stating this representation's event fields |
| `tension_hold` | Worlds with a hold only: each hold with its interval and payer, as for exact events |

In `representation.statistics`, a pore world adds `pores`: each threshold draw (key, counter, u, E,
the time drawn: a founder at 0, a daughter at its birth), the largest embedded estimate of the
clock's error (`largest_clock_error`), the largest fraction of its bound used
(`largest_clock_error_fraction`, |U^H|/(1e-10 + 2e-3 |ΔH|), at most 1 in a run that was not
refused), and the bound's two parts (`clock_error_bound`, 1e-10, and `clock_error_relative`,
2e-3). The world's own check adds `pore`: the traced rate against the law's
host form at the founders' areas and tensions.

## rows.npz

| Array | Shape | Contents |
| --- | --- | --- |
| `row_kind` | [K] | `start`, `observed`, `end`, `outside_envelope`, `lysis`, `shear`, `transfer` or `slots_full` |
| `row_time_s` | [K] | The row's time (s) |
| `counts` | [K, P] | Single lineage: every place's count, real, in place order (held places 0) |
| `pool_counts`, `slot_counts` | [K, P], [K, S, P] | Population: the pool's places, and each slot's vesicle places (0 elsewhere and in an empty slot) |
| `alive`, `keys` | [K, S] | Each slot's living vesicle and its carrier key (−1 when empty); S = 1 in a single lineage |
| `supplied` | [K, P] | Each held place's net supply, real |
| `heat_kT` | [K] | Q, cumulative: the continuous heat plus the events' (k_BT) |
| `work_kT` | [K] | W summed over payers: the reservoir's (continuous and at releases), the shear's, the transfers' and the holds' |
| `continuous_heat_kT`, `reservoir_work_kT`, `shear_work_kT`, `transfer_work_kT`, `sink_kT` | [K] | The parts, cumulative |
| `pore_clock_H` | [K, S] | Pore worlds only: each slot's clock H (0 in an empty slot, and after its vesicle's rupture) |
| `tension_hold_work_kT` | [K, holds] | Worlds with a hold only: each hold's work, cumulative (paid by `source:tension_hold/<index>`); `work_kT` includes it |
