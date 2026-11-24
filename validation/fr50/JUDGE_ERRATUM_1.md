# FR-50's judge, erratum 1 (24 November 2026): K5's RK4 control

This erratum corrects the judge of `fr50-one-way-records-v1`, tagged `fr50-judge-2026-11-24` at
3cec272b. It is documentation only. `validation/fr50/judge.py` is unchanged: its blob is
`b771040237193c28a796b0947d288a55226c351c` at the tag, and it still is. It was written before any
judged run and before any reference output was read.

## The defect

The judge passes a refusal row (`check_refusals`) only when the engine reports it refused with its
reason, and its control accepted. The judge's docstring defines the control as "the same world
without the declaration, which must be accepted".

For K5's `rk4` row that control is refused by construction:
- in phase 1, `one_way` is declared only on kinds (passive routes and transporters);
- `surface_pump_v3._check_kinds_solver` refuses every declared kind under RK4, whether or not it
  declares `one_way`.

So the world without the declaration, under RK4, can never be accepted, and the row would fail
whatever the engine does.

## The corrected control

For K5's `rk4` row the control is **the same world, with `one_way` declared, under the registered
IMEX solver**. It must be accepted, which shows that RK4 alone is the cause. The engine adapter
reports this as the row's `control_accepted`.

Every other refusal row keeps the docstring's control, "the same world without the declaration":
- **E5's `rk4`** (phase 2): @3's own records under RK4, in a world without kinds, which RK4 admits;
- **K5's `rectifier_route` and `net_flow_transporter_mode`:** their worlds without `one_way` are
  admitted today;
- **K5's `slot_operator`, on the version-1 transporter world:**
  - The passive routes declare no partition roles, so they are refused beside every operator that
    opens, closes or retires slots, with or without `one_way`. A passive-route control could
    never be accepted.
  - The version-1 transporter declares its roles, axes and presence. It is admitted beside
    `isopotential_partition@1` and `scheduled_membrane_insertion@2`
    (`tests/unit/test_kind_lifecycle_roles.py`), so its control can be accepted.

## The refusal message each row expects

The registration's K5 reads: "Each of these, with `one_way` declared, is refused with its reason:
a rectifier route; a net-flow transporter mode; RK4; an operator that retires or closes slots."
E5 reads the same for its four rows.

The reason is the declaration's own, so **every row's message names the declaration**
(`one_way` or `one-way`) and its cause, as `judge.py`'s REFUSALS words already require, case
aside:

| Row | The cause's words (any one) |
| --- | --- |
| K5 `rectifier_route` | "rectif" |
| K5 `net_flow_transporter_mode` | "net-flow", "net flow" or "net_flow" |
| K5 `rk4` | "rk4" |
| K5 `slot_operator` | "retire" or "close" |
| E5 `charged_face_row` | "charged" |
| E5 `forms_face` | "forms" |
| E5 `pump` | "pump" |
| E5 `rk4` | "rk4" |

**For K5's `rk4`, the existing kinds-under-RK4 refusal does not count.** It names RK4 and not the
declaration: "Declared kinds (...) require an IMEX solver: under RK4 none of the kinds' step
guards run (...), so @3 refuses them (fails closed)". The row needs a refusal of its own, naming
`one_way` and RK4. That refusal is checked before the kinds-under-RK4 one, so it is the one
reported. RK4 has no end view of a step, which the records' rule needs, as for FR-42's labels.
