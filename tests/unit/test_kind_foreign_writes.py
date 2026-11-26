"""A kind writes only its own resolved, declared fields (kind_registry.refuse_foreign_writes).

These are the three paths where @3 merges the kinds' outputs, each checked against its own
declared set of the kind bound to its structure entry:
- the initial values: state fields and layout fields (surface_pump_v3.initial_values);
- the rates' derivatives: state fields (surface_pump_v3._kind_rates), on the host step and, once,
  while a compiled run traces;
- the control outputs: control fields (surface_pump_v3_spec.control_values).

Each path refuses two plants, naming the kind and the fields:
- a field outside the kind, the base model's;
- a field that another declaration of the same kind resolves.

A legal kind passes all three. The probe is cells.kind.passive_routes@1 on FR-1's closed pair, with
one state field and one control field of its own per declaration, named by its route count (its
structure entry here). So declarations of one route and of two routes resolve different fields.
"""

import dataclasses
import re

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import passive_routes as pr
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests.unit.test_passive_routes_kind import P, closed_pair, host_step, route

ONE = None  # closed_pair's default: one route, leak_S.
TWO = [route("leak_S", P), route("leak_T", P / 2)]  # Two routes on the same rows.


def probe(tag, plant=None):
    """The probe kind, in a registry of its own (scoped), its structure entry (tag, routes).
    `plant` maps a hook ("initial state", "initial layout", "rates", "control_values") to the
    extra keys it also writes."""
    plant = plant or {}

    def entry(declaration):
        return (tag, len(declaration))

    def fields(entry):
        n = entry[1]
        return kind_registry.KindFields(
            (*pr.STATE_AXES, (f"passive_probe_{n}", ("passive_route",))),
            pr.LAYOUT_FIELDS,
            (f"passive_probe_control_{n}",),
            (),
        )

    def initial(spec, declaration, layout):
        state, own = pr.initial(spec, declaration, layout)
        state = state | {f"passive_probe_{len(declaration)}": np.zeros(len(declaration))}
        return state | plant.get("initial state", {}), own | plant.get("initial layout", {})

    def rates(state, potentials, control, p, *, xp):
        r = pr.rates(state, potentials, control, p, xp=xp)
        n = p.passive_area.shape[0]
        own = r.derivatives | {f"passive_probe_{n}": xp.zeros(n)}
        return r._replace(derivatives=own | plant.get("rates", {}))

    def controls(spec, declaration, times):
        own = {f"passive_probe_control_{len(declaration)}": np.ones((len(times), 1))}
        return own | plant.get("control_values", {})

    kind = dataclasses.replace(
        pr.PASSIVE_ROUTES,
        structure_entry=entry,
        declared_fields=fields,
        initial=initial,
        rates=rates,
        control_values=controls,
    )
    kinds = kind_registry.KindRegistry()
    kinds.register(kind)
    return kind_registry.scope(kinds)


def refusal(hook, fields, role):
    """The refusal's text, as a pattern: the kind, the fields it named and its hook."""
    return re.escape(
        f"Kind {pr.KIND_ID} writes {sorted(fields)} from its {hook}; a kind writes only its own "
        f"declared {role} fields"
    )


@pytest.mark.parametrize("routes", [ONE, TWO], ids=["one route", "two routes"])
def test_a_legal_kind_passes_every_path_with_its_own_fields(routes):
    n = len(routes or [1])
    with probe("legal"):
        raw = closed_pair(routes=routes)
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, _ = model.initial_values(spec)
        assert f"passive_probe_{n}" in type(state)._fields  # Its declaration's own fields.
        assert f"passive_probe_{3 - n}" not in type(state)._fields
        controls = control_values(spec, [0.0])
        assert f"passive_probe_control_{n}" in type(controls)._fields
        assert host_step(raw)[3]  # A valid step: rates, derivatives and booking.


# Each plant: the hook it is made in, the extra keys, and the hook and role the refusal names.
# The plants of "another declaration's" field are made in the one-route declaration, and name the
# two-route declaration's fields.
PLANTS = {
    "initial state, a base field": ("initial state", {"amount_increment": 0.0}, "state"),
    "initial state, another declaration's": ("initial state", {"passive_probe_2": 0.0}, "state"),
    "initial layout, a base field": ("initial layout", {"volume": 0.0}, "layout"),
    "initial layout, another declaration's": ("initial layout", {"passive_probe_2": 0.0}, "layout"),
    "rates, a base field": ("rates", {"amount_increment": 0.0}, "state"),
    "rates, another declaration's": ("rates", {"passive_probe_2": 0.0}, "state"),
    "control_values, a base field": ("control_values", {"channel": 0.0}, "control"),
    "control_values, another declaration's": (
        "control_values",
        {"passive_probe_control_2": 0.0},
        "control",
    ),
}
NAMED = {"initial state": "initial values", "initial layout": "initial values"}
NAMED |= {"rates": "rates", "control_values": "control_values"}


@pytest.mark.parametrize("plant", list(PLANTS))
def test_a_foreign_write_is_refused_at_definition(plant):
    """The definition check evaluates every path (initial_values, control_values, and the rates
    through control_domain_valid's readouts), so a planted write refuses the definition."""
    hook, extra, role = PLANTS[plant]
    with probe(f"definition {plant}", {hook: extra}):
        pattern = "Invalid resolved pump @3 definition: " + refusal(NAMED[hook], extra, role)
        with pytest.raises(ConfigError, match=pattern):
            parse_spec(closed_pair())


def admitted(plant):
    """A definition the legal probe admitted, then built with the planted probe (as a run that
    resumes or windows would build it, past the definition check): (spec, model)."""
    hook, extra, _ = PLANTS[plant]
    with probe(f"admitted {plant}"):
        spec = parse_spec(closed_pair())
    scope = probe(f"planted {plant}", {hook: extra})
    return spec, scope


@pytest.mark.parametrize("plant", list(PLANTS))
def test_each_merge_point_refuses_a_foreign_write_on_its_own(plant):
    hook, extra, role = PLANTS[plant]
    spec, scope = admitted(plant)
    with scope:
        model = get_model(spec.model)
        with pytest.raises(ValueError, match=refusal(NAMED[hook], extra, role)):
            if hook.startswith("initial"):
                model.initial_values(spec)
            elif hook == "control_values":
                control_values(spec, [0.0])
            else:  # The host step's stages.
                state, p = model.initial_values(spec)
                control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
                model.imex_step(state, spec.execution.dt, control, p, xp=np)


def test_a_foreign_derivative_is_refused_while_the_checked_step_traces():
    """The derivatives' check reads keys while tracing: the compiled step (jax.numpy) is refused
    as it traces, before any value exists. crossrev shows it adds no equation."""
    plant = "rates, a base field"
    hook, extra, role = PLANTS[plant]
    spec, scope = admitted(plant)
    with scope:
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        with pytest.raises(ValueError, match=refusal(NAMED[hook], extra, role)):
            jax.eval_shape(model.checked_step, state, spec.execution.dt, control, p, p.active)
