# FR-45 addendum: the refusal mapping [B4]

Dated 27 November 2026. Drafted by FR-45's builder for TABLE.md §7 and §14.1 item 1. A reviewer who is not the
builder confirmed it against `src/` [B4, N1], with one correction, made here and in the driver (the exact match
below). The lead hashes it before any registered run.

The driver (`validation/fr45/driver.py`) records `kind`, `raised`, `book` and `name` by this mapping. The judge
(`validation/fr45/judge.py`, `mapped`) applies the same mapping to `raised` and `name` itself, and treats any
departure as a fault (§7, §11.1 item 8).

## The mapping

| The engine raises | `name` | `kind` | `book` |
| --- | --- | --- | --- |
| `cells.execution.errors.NumericalError` whose message is exactly the composite model's `device_failure_message(check)`, for a check of the run's list other than `domain` (the checks addendum) | the check's name | `check` | `moiety ledger` for `site_moiety_entity`; `energy ledger` for `energy`; `dissipation check` for `dissipation`; `host check: <name>` for every other check |
| `NumericalError` whose message is exactly the `domain` check's | `solver domain` | `domain` | null |
| `NumericalError` of any other message, where `cells.operators.site_occupancy.refusal_condition` names the stage condition on the refused step's start state | `stage condition` | `stage` | null |
| `NumericalError` of any other message, where the stage condition is not named | `solver domain` | `domain` | null |
| `cells.definitions.specs.ConfigError`, at parse or at binding, naming `site_occupancy.DOMAIN_REFUSALS` (`initial occupancies over 1 on a set`) | that name | `domain` | null |
| `ConfigError` naming another of `site_occupancy.REFUSALS`, or any other `ConfigError` (its message's first clause) | that name | `definition` | null |
| Anything the engine did not raise: the driver's time limit, or an exception of another module | `driver time limit`, or `driver: <type>` | `harness` | null |

`raised` is the exception's qualified class name. It is null only in a `harness` refusal that no exception ended,
such as the time limit (§7) [B4, E4]. `step` and `time_s` are null exactly at parse.

## The checks' messages

These are the composite's (`cells.models.pump_composite`, `device_failure_message`), as the passes' models give
them:

| Check | Message prefix |
| --- | --- |
| `domain` | `Invalid resolved pump inventory, gates or padding; no repair` |
| `local`, `outside`, `total`, `charge`, `electrode`, `global_charge`, `energy`, `reservoir_work`, `electrode_work`, `metabolic_work` | `Resolved pump accounting failed: <check>` |
| `site_bound_entity`, `site_moiety_entity` | `Site occupancy accounting failed: <check>` |
| `wash_ions` (W2 and W7) | `Compartment wash accounting failed: wash_ions` |
| `dissipation` | `Resolved pump dissipation cannot be negative or decrease` |

## The stage identification [§8.6]

`site_occupancy.refusal_condition(state, control, p, dt)` reads the step's first site half-step on the state it
receives, through `stage_report`. It returns `stage condition` when the stage condition refuses at one of its three
stages, and None otherwise. A `NumericalError` that the driver does not match to a check is a stage refusal only
when this names it, and otherwise a domain failure.

W5's step report (§7) is the same `stage_report` on the start state: its loads, its `h_max_load`, its limit 0.5 and
its verdict.

## Coverage of the plants' patches [N1]

Every check a patch can make the engine refuse is a check of the run's list, so it maps to `check` and the book
above. A patch raises nothing else: no patch raises an exception of its own.

In the dress rehearsal, on invented worlds:
- the P1 patch's run was refused by `dissipation`;
- P5's, on both its runs, by `energy`;
- P6's by `energy`;
- P7's and P8's by `site_moiety_entity`;
- P2, P3, P4 and P9 completed.

The development-only `INVENTED_p7_host.py` raised a host check. The reviewer confirmed that this list covers every
exception and check name a patch can raise [N1].

## The exact match, and the readings ruled at the review (27 November 2026)

- **The exact match.** The engine raises a check's failure as its bare message (`surface_pump`; `pump_composite`'s
  own ledgers and its operators' `LEDGER_MESSAGE + name`). The driver therefore names a failure by the check whose
  message equals the engine's exactly (`driver.py`: `failed_check`, `numerical_refusal`). A prefix match named
  `electrode_work`'s failure `electrode`; the review found it, and a test row plants that failure.
- **`site_bound_entity`.** Its book is `host check: site_bound_entity`. §7's four forms are the three named books
  and `host check: <name>`.
- **The host `domain` check.** Its failure is kind `domain`, name `solver domain`: the reading that cannot make a
  pass easier under P-c. The driver still records it in `checks.domain.failures`, as §4's member rule asks for
  each listed check.
- **Parse refusals by value** map to `definition`. Only `initial occupancies over 1 on a set` maps to `domain`.
- **The stage identification** reads the step's first half-step only. That is conservative: a stage refusal
  beyond the first half-step is not reachable at the registered sizes.
