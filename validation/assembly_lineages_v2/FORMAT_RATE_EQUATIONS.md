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
- Slices S1 and S2 run OL1's laws, the bilayer geometry, the osmotic lumen, lysis, the shared
  pool, shear fission and serial transfer. The pore clock and held tensions come with S3; FR-21's
  shell, FR-20's replacement and FR-35's withdrawal are refused in version 1.

## run.json (`cells.rate_equations_run@1`)

| Key | Contents |
| --- | --- |
| `world`, `model`, `definition_sha256` | As for exact events: the world's id, `cells.assembly_lineages@2`, and the definition's fingerprint |
| `engine_models` | The world's laws and operators, and `representation: cells.rate_equations@1` |
| `representation` | The declared envelope and integrator; `formulas`; `statuses`; `not_applicable`; and `statistics`: steps accepted and rejected, `restarts` (the lumen's kink), `crossings` (located roots), rtol, atol, the end time, `stop_reason` (`envelope` or `floor` for `outside_envelope`) and `schedule_draws` (Poisson gaps on domain 6, as exact) |
| `conventions` | The world's tokens, echoed |
| `laws` | Each law as an exact run states it (id, interface, formulas, provenance, test), plus its `limit_formulas`; a law with no limit kernel (the bilayer geometry) states the representation's rule for it |
| `status` | One of `complete`, `lysed`, `outside_envelope`, `stalled`, `step_limit`, `slots_full` |
| `events` | The vesicle-level events in order: each lysis (time, slot, key, cause, `at_birth`, σ and σ_max, what returned to each pool place, its heat and reservoir work); each fission attempt (time, schedule, k, slot, parent key and counts, outcome; for a split its daughters' keys and counts, the followed daughter or −1 in a population, their slots, the shear work, the sink, and each daughter's lysis at birth); each transfer (time, schedule, its domain-6 draws, kept and removed slots, sink and work) |
| `ledger` | At every row: `free_energy_kT` (F_cont with each living vesicle's closure cost), `residual_kT` (F_cont(n_t) − F_cont(n_0) − (W − Q − S)), `tolerance_kT`, and `closes`; a run whose ledger does not close is refused |
| `moieties` | The moiety names, the largest relative drift of Σ_finite m·n − Σ_held m·supplied plus what left with the sinks (net of a transfer's fresh pool), its tolerance (1e-12) and `closes` |
| `dissipation` | The smallest per-step margin of −J_r ΔF_r at the accepted states, its tolerance and `holds` |
| `check` | The limit's check: the generic verdict (six probes, items 1 to 3 and parity's fitted orders) and the world's own items 1 to 3 |
| `rows` | The row count, their kinds and the world's place names |

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
| `work_kT` | [K] | W summed over payers: the reservoir's (continuous and at releases), the shear's and the transfers' |
| `continuous_heat_kT`, `reservoir_work_kT`, `shear_work_kT`, `transfer_work_kT`, `sink_kT` | [K] | The parts, cumulative |
