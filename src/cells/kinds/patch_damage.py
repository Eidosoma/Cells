"""cells.patch_damage@1: a membrane patch's damage, a source of the routing door (FR-5).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §9 and §16 (the lead's rulings of 16 November 2026) and
INNER_MODEL_V4_DESIGN.md §7.4 (l) and (n); the law is `bounding_patch_damage@1`
(laws/transport/patch_damage.py), injury and resealing as a kind:

    dd/dt = a (1 - d) - b d,   a = k_inj u_inj(t),  b = k_res u_res(t),   d in [0, 1],

with u_inj and u_res piecewise-constant schedules in [0, 1]. d is the damaged fraction of the
patch's area: on a lumped population, a uniform damage of every member (§9). It moves nothing and
books nothing; it reaches routes only as a factor through the routing door (§7.4 (n)).

The declaration (model key `patch_damage`), at most one damage entity per membrane patch:

    [{"id": "damage_0", "patch": "bounding_0", "law": "bounding_patch_damage@1",
      "initial_damage": 0.0, "injury_rate_per_s": 1.0, "resealing_rate_per_s": 0.05}]

and its schedules (experiment key `damage_controls`, optional; the core's gap-6 schedules, §7.4
(l)), each damage entity at most once, an omitted one at 0 throughout:

    [{"damage_id": "damage_0", "injury": [{"time": 0.0, "value": 0.0}, {"time": 60.0, "value": 1.0},
      {"time": 120.0, "value": 0.0}], "resealing": [{"time": 0.0, "value": 0.0},
      {"time": 120.0, "value": 1.0}]}]

parsed into one kind_registry.Schedule with the series "ID.injury" and "ID.resealing" per entity
in declared order. Its breakpoints join the change times, so each is a step boundary and every
step holds the schedules' values at its start. Without the key (the default) both are 0, so d
keeps its start, and the definition keeps its form.

- **Fields,** per membrane slot (zeros off the declared patches): the state d (`patch_damage`); the
  controls u_inj and u_res (`patch_damage_injury`, `patch_damage_resealing`), in [0, 1] by the
  kinds' default rule.
- **rates:** d's derivative only, a(1 - d) - b d at the stage's d (the stage values the routes
  read through the door, second order). No node rate, heat or work; `valid` is the law's domain.
- **book:** d's end value is the law's exact step over the step at the step's held control
  (`book` receives it, §7.4 (l) 5): d_eq + (d_start - d_eq) e^(-(a+b) dt), d_eq = a/(a + b). The
  schedules are constant over each step, so d is exact at every step's end (FR-5's J2: d at
  rounding on every rung pair).
- **domain:** d in [0, 1], zeros off the declared patches.
- **The routing door's source** (§7.4 (n)): `factor_sources(declaration)`, the damage IDs in
  declared order, and `factors(read, p, *, xp)`, d at each one's patch on the stage's state.
- **The lifecycle's declarations** (CORE_SEAMS §4.2, and §18's B1 lift, the lead's rulings of 18
  November 2026): every field's partition role and axes, and the host of its own axis (the damage
  entities, each on its patch). d is a level of its patch, a uniform damage of every member (§9),
  so a split copies it (intensive), as it copies the patch's rate constants and schedules; the
  patch's presence and each entity's patch slot are structural. They are read on the host only, so
  no program changes; a kind beside a closer stays refused until the core gates its rates by its
  host's activity (B1's third step).
- **FR-42's labels** (D303 item 6): `label_refusals` gives none, since it moves no species row, so
  labels are admitted beside it; it has no label_transfers.
"""

from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.laws.transport import patch_damage as law
from cells.modules import (
    AxisHost,
    ConfigError,
    Kind,
    KindView,
    PartitionRole,
    Schedule,
    declared_schedule,
    finite_number,
    parse_series,
    qualified,
    require_fields,
    series_to_dict,
)
from cells.registry.kind_registry import BUILTIN

KIND_ID = "cells.patch_damage@1"
MODEL_KEY = "patch_damage"
SCHEDULE_KEY = "damage_controls"
LAW_ID = qualified(law.LAW_ID)
ENTRY_FIELDS = ("id", "patch", "law", "initial_damage", "injury_rate_per_s", "resealing_rate_per_s")
SCHEDULE_FIELDS = ("damage_id", "injury", "resealing")
SERIES = ("injury", "resealing")  # Each entity's two series, "ID.injury" and "ID.resealing".
STATE_AXES = (("patch_damage", ("membrane_slot",)),)
LAYOUT_FIELDS = (
    "patch_damage_present",  # [membrane] a damage entity on the patch
    "patch_damage_injury_rate_per_s",  # [membrane] k_inj, 0 off the declared patches
    "patch_damage_resealing_rate_per_s",  # [membrane] k_res
    "patch_damage_source_slot",  # [source] each damage entity's patch slot, in declared order
)
CONTROL_FIELDS = ("patch_damage_injury", "patch_damage_resealing")
SOURCE_AXIS = "patch_damage_source"  # The damage entities, in declared order, each on its patch.
# The lifecycle's declarations (the module docstring's last item).
PARTITION_ROLES = MappingProxyType(
    {
        "patch_damage": PartitionRole("intensive"),
        "patch_damage_present": PartitionRole("structural", False),
        "patch_damage_injury_rate_per_s": PartitionRole("intensive"),
        "patch_damage_resealing_rate_per_s": PartitionRole("intensive"),
        "patch_damage_source_slot": PartitionRole("structural", 0),
        "patch_damage_injury": PartitionRole("intensive"),
        "patch_damage_resealing": PartitionRole("intensive"),
    }
)
FIELD_AXES = MappingProxyType(
    {
        "patch_damage_present": ("membrane_slot",),
        "patch_damage_injury_rate_per_s": ("membrane_slot",),
        "patch_damage_resealing_rate_per_s": ("membrane_slot",),
        "patch_damage_source_slot": (SOURCE_AXIS,),
        "patch_damage_injury": ("membrane_slot",),
        "patch_damage_resealing": ("membrane_slot",),
    }
)
AXIS_HOSTS = MappingProxyType({SOURCE_AXIS: AxisHost("patch", "patch_damage_source_slot")})


class Damage(NamedTuple):
    """One declared damage entity."""

    id: str
    patch: str
    initial: float
    injury_rate_per_s: float
    resealing_rate_per_s: float


# ---------------------------------------------------------------------------- definition


def _taken_ids(m):
    nodes = (*m.cells, *m.extracellular, *m.membranes, *m.junctions, *m.faces)
    return {node.id for node in nodes}


def parse(entries, base):
    """The declaration: a tuple of Damage entities, in declared order."""
    m = base.model
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{MODEL_KEY} is a non-empty list of damage entities (omit it for none)")
    patches = {p.id for p in m.membranes}
    taken, ids, used, out = _taken_ids(m), set(), set(), []
    for raw in entries:
        require_fields(raw, set(ENTRY_FIELDS), "a patch damage entity")
        name = raw["id"]
        if not isinstance(name, str) or not name or name in ids or name in taken:
            raise ConfigError(f"patch damage ID {name!r} must be unique among the model's IDs")
        ids.add(name)
        where = f"patch damage {name!r}"
        if not isinstance(raw["law"], str) or not raw["law"] or qualified(raw["law"]) != LAW_ID:
            raise ConfigError(f"{where}: law is {LAW_ID}")
        patch = raw["patch"]
        if patch not in patches:
            raise ConfigError(f"{where}: unknown membrane patch {patch!r}")
        if patch in used:
            raise ConfigError(
                f"{where}: patch {patch} already carries a damage entity (one per patch: d is the "
                "patch's damaged fraction)"
            )
        used.add(patch)
        initial = finite_number(raw["initial_damage"], f"{where}: initial_damage")
        if initial > 1.0:
            raise ConfigError(f"{where}: initial_damage lies in [0, 1]")
        rates = [  # finite_number refuses a negative rate (1/s).
            finite_number(raw[key], f"{where}: {key}")
            for key in ("injury_rate_per_s", "resealing_rate_per_s")
        ]
        out.append(Damage(name, patch, initial, *rates))
    return tuple(out)


def to_dict(declaration):
    return [
        dict(
            id=d.id,
            patch=d.patch,
            law=LAW_ID,
            initial_damage=d.initial,
            injury_rate_per_s=d.injury_rate_per_s,
            resealing_rate_per_s=d.resealing_rate_per_s,
        )
        for d in declaration
    ]


def structure_entry(declaration):
    """Value-free: the law, and the number of sources (the factors' shape)."""
    return (LAW_ID, len(declaration))


def series_name(damage_id, which):
    return f"{damage_id}.{which}"


def default_schedule(declaration):
    """Version 1's constant: no injury and no resealing for every entity."""
    return Schedule(
        tuple((series_name(d.id, which), ((0.0, 0.0),)) for d in declaration for which in SERIES)
    )


def parse_schedule(raw, base, declaration):
    """The entities' schedules from `damage_controls` (module docstring), or the default."""
    if SCHEDULE_KEY not in raw:
        return default_schedule(declaration)
    entries = raw[SCHEDULE_KEY]
    if not isinstance(entries, list) or not entries:
        raise ConfigError(
            f"{SCHEDULE_KEY} is a non-empty list of damage schedules (omit it for none)"
        )
    ids = [d.id for d in declaration]
    given = {}
    for entry in entries:
        require_fields(entry, set(SCHEDULE_FIELDS), f"an entry of {SCHEDULE_KEY}")
        name = entry["damage_id"]
        if name not in ids:
            raise ConfigError(f"{SCHEDULE_KEY}: unknown damage entity {name!r}")
        if name in given:
            raise ConfigError(f"{SCHEDULE_KEY}: damage entity {name!r} is scheduled twice")
        given[name] = {
            which: parse_series(entry[which], f"{SCHEDULE_KEY} {name}.{which}") for which in SERIES
        }
    default = ((0.0, 0.0),)
    return Schedule(
        tuple(
            (series_name(d, which), given.get(d, {}).get(which, default))
            for d in ids
            for which in SERIES
        )
    )


def schedule_to_dict(schedule, declaration):
    """parse_schedule's inverse; {} for the default, so a definition without the key keeps it."""
    if schedule == default_schedule(declaration):
        return {}
    series = dict(schedule.series)
    return {
        SCHEDULE_KEY: [
            dict(
                damage_id=d.id,
                **{which: series_to_dict(series[series_name(d.id, which)]) for which in SERIES},
            )
            for d in declaration
        ]
    }


def initial(spec, declaration, layout):
    """d at its declared start, per membrane slot; the rates and the sources' slots as layout."""
    k = spec.execution.membrane_capacity
    patches = [p.id for p in spec.model.membranes]
    present = np.zeros(k, dtype=bool)
    injury, resealing, start = np.zeros(k), np.zeros(k), np.zeros(k)
    slots = []
    for d in declaration:
        i = patches.index(d.patch)
        present[i], injury[i], resealing[i], start[i] = True, d.injury_rate_per_s, \
            d.resealing_rate_per_s, d.initial
        slots.append(i)
    own = dict(
        patch_damage_present=present,
        patch_damage_injury_rate_per_s=injury,
        patch_damage_resealing_rate_per_s=resealing,
        patch_damage_source_slot=np.asarray(slots, dtype=np.int64),
    )
    return dict(patch_damage=start), own


def control_values(spec, declaration, times):
    """u_inj and u_res per membrane slot at `times` (the change times), from the schedule."""
    schedule = declared_schedule(spec, KIND_ID)
    patches = [p.id for p in spec.model.membranes]
    out = {}
    for which, field in zip(SERIES, CONTROL_FIELDS, strict=True):
        values = np.zeros((len(times), spec.execution.membrane_capacity))
        for d in declaration:
            values[:, patches.index(d.patch)] = schedule.values(series_name(d.id, which), times)
        out[field] = values
    return out


# ---------------------------------------------------------------------------- the step


def rates(state, potentials, control, p, *, xp):
    from cells.modules import KindRates

    d = state.patch_damage
    k_inj, k_res = p.patch_damage_injury_rate_per_s, p.patch_damage_resealing_rate_per_s
    u_inj, u_res = control.patch_damage_injury, control.patch_damage_resealing
    derivative, _, _ = law.rates(d, k_inj, k_res, u_inj, u_res, xp=xp)
    present = p.patch_damage_present
    valid = xp.all(xp.where(present, law.domain_valid(d, k_inj, k_res, u_inj, u_res, xp=xp), True))
    return KindRates(
        cell=xp.zeros_like(state.amount_increment),
        outside=xp.zeros_like(state.extracellular_amount_increment),
        derivatives=dict(patch_damage=xp.where(present, derivative, 0.0)),
        heat_pJ_s=xp.zeros(()),
        work_pJ_s=xp.zeros(()),
        valid=valid,
    )


def book(applied, start, end, control, p, dt, *, xp):
    """d's exact end value at the step's held control (module docstring)."""
    del applied, end
    exact = law.exact_step(
        start.patch_damage,
        p.patch_damage_injury_rate_per_s,
        p.patch_damage_resealing_rate_per_s,
        control.patch_damage_injury,
        control.patch_damage_resealing,
        dt,
        xp=xp,
    )
    d = xp.where(p.patch_damage_present, exact, start.patch_damage)
    return dict(patch_damage=d), xp.all(xp.isfinite(d) & (d >= 0) & (d <= 1))


def domain(state, p, *, xp):
    """d in [0, 1] and finite; zeros off the declared patches."""
    d = state.patch_damage
    valid = xp.all(xp.isfinite(d) & (d >= 0) & (d <= 1))
    return valid & xp.all(xp.where(p.patch_damage_present, True, d == 0))


def label_refusals(declaration, species):
    """FR-42 (D303 item 6): none. Its rates hook moves no species row (it has no moved_rows), so
    no labelled species is moved by it and it reports no transfers."""
    del declaration, species
    return []


# ---------------------------------------------------------------------------- the routing door


def factor_sources(declaration):
    """The routing door's sources this kind exposes: its damage IDs, in declared order."""
    return tuple(d.id for d in declaration)


def factors(read, p, *, xp):
    """Each source's value on the stage's state: d at its patch, in [0, 1]."""
    return read.patch_damage[p.patch_damage_source_slot]


# The run view's declarations (D154): d is a level per membrane slot, the patch's damaged fraction.
VIEW = KindView(
    units=MappingProxyType({"patch_damage": "1"}),
    record_kinds=MappingProxyType({"patch_damage": "level"}),
    record_layers=MappingProxyType({"patch_damage": "membrane"}),
)


PATCH_DAMAGE = BUILTIN.register(
    Kind(
        kind_id=KIND_ID,
        model_key=MODEL_KEY,
        state_axes=STATE_AXES,
        layout_fields=LAYOUT_FIELDS,
        control_fields=CONTROL_FIELDS,
        parse=parse,
        to_dict=to_dict,
        structure_entry=structure_entry,
        initial=initial,
        control_values=control_values,
        rates=rates,
        book=book,
        domain=domain,
        experiment_keys=(SCHEDULE_KEY,),
        parse_schedule=parse_schedule,
        schedule_to_dict=schedule_to_dict,
        factor_sources=factor_sources,
        factors=factors,
        view=VIEW,
        partition_roles=PARTITION_ROLES,
        field_axes=FIELD_AXES,
        axis_hosts=AXIS_HOSTS,
        label_refusals=label_refusals,  # FR-42 (D303 item 6): it moves no row.
    )
)
