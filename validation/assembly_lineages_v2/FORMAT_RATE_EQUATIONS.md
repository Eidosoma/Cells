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
- The experiment block is the exact run's. `event_limit` and `row_every_events` are stated as not
  applicable in the record; `trace`, `uniforms` and `diagnostic` are refused when true.
- In the first slice (S1), only a single lineage without a geometry runs. Geometry, populations,
  division and schedules come with S2, and the pore clock with S3; each is refused until then.

## run.json (`cells.rate_equations_run@1`)

| Key | Contents |
| --- | --- |
| `world`, `model`, `definition_sha256` | As for exact events: the world's id, `cells.assembly_lineages@2`, and the definition's fingerprint |
| `engine_models` | The world's laws and operators, and `representation: cells.rate_equations@1` |
| `representation` | The declared envelope and integrator; `formulas`; `statuses`; `not_applicable`; and `statistics` (steps accepted and rejected, rtol, atol, end time) |
| `conventions` | The world's tokens, echoed |
| `laws` | Each law as an exact run states it (id, interface, formulas, provenance, test), plus its `limit_formulas` |
| `status` | One of `complete`, `lysed`, `outside_envelope`, `stalled`, `step_limit`, `slots_full` |
| `ledger` | At every row: `free_energy_kT` (F_cont), `residual_kT` (F_cont(n_t) − F_cont(n_0) − (W − Q)), `tolerance_kT`, and `closes` |
| `moieties` | The moiety names, the largest relative drift of Σ_finite m·n − Σ_held m·supplied, its tolerance (1e-12) and `closes` |
| `dissipation` | The smallest per-step margin of −J_r ΔF_r at the accepted states, its tolerance and `holds` |
| `check` | The limit's check: the generic probes' worst gaps, and the world's own |
| `rows` | The row count, their kinds and the world's place names |

## rows.npz

| Array | Shape | Contents |
| --- | --- | --- |
| `row_kind` | [K] | `start`, `observed`, `end` or `outside_envelope` |
| `row_time_s` | [K] | The row's time (s) |
| `counts` | [K, P] | Every place's count, real, in place order (held places 0) |
| `supplied` | [K, P] | Each held place's net supply, real |
| `heat_kT`, `work_kT` | [K] | Q and the reservoir work W, cumulative (k_BT) |
