"""cells.patch_damage@1: a membrane patch's damage, a source of the routing door (FR-5).

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §9 and §16 (the lead's rulings of 16 November 2026); the
law is `bounding_patch_damage@1` (processes/patch_damage.py), the older family's injury and
resealing re-expressed as a kind:

    dd/dt = a (1 - d) - b d,   a = k_inj u_inj(t),  b = k_res u_res(t),   d in [0, 1],

with u_inj and u_res piecewise-constant schedules in [0, 1] whose breakpoints lie on the step grid
(the core's gap-6 schedules join `experiment.changes`). d is the damaged fraction of the patch's
area: on a lumped population, a uniform damage of every member (§9). It moves nothing and books
nothing; it reaches routes only as a factor through the routing door (§16.2), which the core
builds.

The declaration (model key `patch_damage`), at most one damage entity per membrane patch:

    [{"id": "damage_0", "patch": "bounding_0", "law": "bounding_patch_damage@1",
      "initial_damage": 0.0, "injury_rate_per_s": 1.0, "resealing_rate_per_s": 0.05}]

- **Fields,** per membrane slot (zeros off the declared patches): the state d (`patch_damage`) and
  the integrated hazards ∫a dt and ∫b dt (`patch_damage_injury_hazard`,
  `patch_damage_resealing_hazard`, dimensionless, cumulative); the controls u_inj and u_res
  (`patch_damage_injury`, `patch_damage_resealing`), in [0, 1] by the kinds' default rule.
- **rates:** derivatives only. d' = a(1 - d) - b d at the stage's d (the stage values the routes
  read through the door, second order); the hazards' derivatives a and b. No node rate, heat or
  work; `valid` is the law's domain at the stage.
- **book:** d's end value is the exact solution over the step, d_eq + (d_start - d_eq) e^(-(A+B)),
  d_eq = A/(A + B), with A = dt applied(injury hazard) and B = dt applied(resealing hazard): a and
  b are constant within a step, so this is exact, and d is exact at every step's end (FR-5's J2:
  d at rounding on every rung pair). The applied rate, not the difference of the cumulative
  fields, keeps A at one rounding of a dt.
- **domain:** d in [0, 1], the hazards finite and nonnegative, zeros off the declared patches.
- **The routing door's source** (§16.2; the core's seam, its API as the core lands it):
  `factor_sources(declaration)`, the damage IDs in declared order, and `factors(read, p, *, xp)`,
  d at each one's patch on the stage's state.
- **Schedules:** the core's gap-6 format, when it lands (the lead's ruling: one format). Until
  then a damage entity has no schedule, so u_inj = u_res = 0 and d keeps its start.
"""

from typing import NamedTuple

import numpy as np

from cells.core.kind_registry import (
    BUILTIN,
    ConfigError,
    Kind,
    finite_number,
    qualified,
    require_fields,
)
from cells.processes import patch_damage as law

KIND_ID = "cells.patch_damage@1"
MODEL_KEY = "patch_damage"
LAW_ID = qualified(law.LAW_ID)
ENTRY_FIELDS = ("id", "patch", "law", "initial_damage", "injury_rate_per_s", "resealing_rate_per_s")
STATE_AXES = (
    ("patch_damage", ("membrane_slot",)),
    ("patch_damage_injury_hazard", ("membrane_slot",)),
    ("patch_damage_resealing_hazard", ("membrane_slot",)),
)
LAYOUT_FIELDS = (
    "patch_damage_present",  # [membrane] a damage entity on the patch
    "patch_damage_injury_rate_per_s",  # [membrane] k_inj, 0 off the declared patches
    "patch_damage_resealing_rate_per_s",  # [membrane] k_res
    "patch_damage_source_slot",  # [source] each damage entity's patch slot, in declared order
)
CONTROL_FIELDS = ("patch_damage_injury", "patch_damage_resealing")


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


def initial(spec, declaration, layout):
    """d at its declared start and zero hazards, per membrane slot; the rates and the sources'
    slots as layout."""
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
    state = dict(
        patch_damage=start,
        patch_damage_injury_hazard=np.zeros(k),
        patch_damage_resealing_hazard=np.zeros(k),
    )
    own = dict(
        patch_damage_present=present,
        patch_damage_injury_rate_per_s=injury,
        patch_damage_resealing_rate_per_s=resealing,
        patch_damage_source_slot=np.asarray(slots, dtype=np.int64),
    )
    return state, own


def control_values(spec, declaration, times):
    """u_inj and u_res per membrane slot at each step's start. No schedule yet: the core's gap-6
    format sets them when it lands (the lead's ruling, one format); until then both are 0, so d
    keeps its start."""
    k = spec.execution.membrane_capacity
    zeros = np.zeros((len(times), k))
    return dict(patch_damage_injury=zeros, patch_damage_resealing=zeros.copy())


# ---------------------------------------------------------------------------- the step


def hazard_rates(control, p):
    """(a, b) per membrane slot (1/s): k_inj u_inj and k_res u_res, zero off the declared
    patches."""
    a = p.patch_damage_injury_rate_per_s * control.patch_damage_injury
    b = p.patch_damage_resealing_rate_per_s * control.patch_damage_resealing
    return a, b


def rates(state, potentials, control, p, *, xp):
    from cells.models.surface_pump_v3 import KindRates

    d = state.patch_damage
    k_inj, k_res = p.patch_damage_injury_rate_per_s, p.patch_damage_resealing_rate_per_s
    u_inj, u_res = control.patch_damage_injury, control.patch_damage_resealing
    derivative, _, _ = law.rates(d, k_inj, k_res, u_inj, u_res, xp=xp)
    a, b = hazard_rates(control, p)
    present = p.patch_damage_present
    valid = xp.all(xp.where(present, law.domain_valid(d, k_inj, k_res, u_inj, u_res, xp=xp), True))
    return KindRates(
        cell=xp.zeros_like(state.amount_increment),
        outside=xp.zeros_like(state.extracellular_amount_increment),
        derivatives=dict(
            patch_damage=xp.where(present, derivative, 0.0),
            patch_damage_injury_hazard=a,
            patch_damage_resealing_hazard=b,
        ),
        heat_pJ_s=xp.zeros(()),
        work_pJ_s=xp.zeros(()),
        valid=valid,
    )


def exact_damage(start, injury_hazard, resealing_hazard, *, xp):
    """d after a step over which the integrated hazards are A and B (a and b constant within it):
    d_eq + (d - d_eq) e^(-(A+B)), d_eq = A/(A+B), d unchanged where A + B = 0 (the law's exact
    step at unit rates over a unit step)."""
    return law.exact_step(start, injury_hazard, resealing_hazard, 1.0, 1.0, 1.0, xp=xp)


def book(applied, start, end, p, dt, *, xp):
    """d's exact end value from the step's applied hazards (module docstring)."""
    del end
    injury = dt * applied("patch_damage_injury_hazard")
    resealing = dt * applied("patch_damage_resealing_hazard")
    exact = exact_damage(start.patch_damage, injury, resealing, xp=xp)
    d = xp.where(p.patch_damage_present, exact, start.patch_damage)
    return dict(patch_damage=d), xp.all(xp.isfinite(d) & (d >= 0) & (d <= 1))


def domain(state, p, *, xp):
    """d in [0, 1]; the hazards finite and nonnegative; zeros off the declared patches."""
    present = p.patch_damage_present
    d = state.patch_damage
    valid = xp.all(xp.isfinite(d) & (d >= 0) & (d <= 1))
    for name in ("patch_damage", "patch_damage_injury_hazard", "patch_damage_resealing_hazard"):
        value = getattr(state, name)
        valid = valid & xp.all(xp.isfinite(value) & (value >= 0))
        valid = valid & xp.all(xp.where(present, True, value == 0))
    return valid


# ---------------------------------------------------------------------------- the routing door


def factor_sources(declaration):
    """The routing door's sources this kind exposes: its damage IDs, in declared order."""
    return tuple(d.id for d in declaration)


def factors(read, p, *, xp):
    """Each source's value on the stage's state: d at its patch, in [0, 1]."""
    return read.patch_damage[p.patch_damage_source_slot]


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
    )
)
