"""@3's channel laws from the law registry (the F owner's Kv1 pilot, D211; CORE_SEAMS §8.3).

A definition may name any channel law the active law registry holds for @3, while today's five
(codes 0-4) stay the full catalogue's. Each claim with a planted error (D187), on a planted law
registered in a test-local registry (`tests.kv_planted@1`: code 5, K only, gates m and h, the
Kv1.5 kernels, an RK4 bound of 2.5 us), as the five Kv1 laws will be:
- the parser's tables are the registry's, and today's five are unchanged by a registered law;
- a population of the registered law binds with its code and runs on the declared structure's
  dispatch, its gates relaxing by the law's own kinetics;
- the full catalogue's domain (structure None) refuses its code, so it never meets that path's
  dispatch, which would run it gate-free;
- an RK4 step above the law's own bound is refused, naming the law; today's two messages stay;
- a replacement template that gates it is refused: the operator's tables hold today's five.
"""

import copy
import dataclasses

import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec_v3
from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import timeline
from cells.models import inner_laws
from cells.models import surface_pump_v3 as v3
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import pump_water_fixtures as water_fixtures

PLANTED = "tests.kv_planted@1"
BOUND_S = 2.5e-6


def planted_law():
    kv1p5 = inner_laws.CHANNEL_LAWS[spec_v3.KV1P5_LAW_ID]
    return dataclasses.replace(kv1p5, law_id=PLANTED, code=5, rk4_step_s=BOUND_S)


def scoped():
    return law_registry.scope(law_registry.BUILTIN.extended(planted_law()))


def with_planted(raw, *, gate=(0.2, 0.9)):
    """raw with a population of the planted law on the first patch, its schedule and capacity."""
    raw = copy.deepcopy(raw)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["channels"].append(
        dict(
            id="kv_planted_0",
            membrane_id=m["membranes"][0]["id"],
            kinetic_law=PLANTED,
            max_permeability_m_per_s=1e-8,
            abundance=1.0,
            initial_gate=list(gate),
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
    )
    e["channel_controls"].append(
        dict(channel_id="kv_planted_0", schedule=[dict(time=0.0, availability=1.0)])
    )
    x["channel_capacity"] = len(m["channels"])
    return raw


def test_the_parsers_tables_are_the_registrys_and_todays_five_stay():
    assert spec_v3.law_codes() == spec_v3.LAW_CODES
    assert spec_v3.law_permeabilities() == spec_v3.LAW_PERMEABILITIES
    assert spec_v3.gate_counts() == spec_v3.GATE_COUNTS
    with scoped():
        assert spec_v3.law_codes() == {**spec_v3.LAW_CODES, PLANTED: 5}
        assert spec_v3.gate_counts()[PLANTED] == 2
        assert spec_v3.law_permeabilities()[PLANTED] == (("K", 1.0),)
    assert len(spec_v3.LAW_CODES) == 5 and PLANTED not in spec_v3.law_codes()


def test_a_registered_law_binds_with_its_code_and_runs_on_the_declared_dispatch():
    raw = with_planted(water_fixtures.heredity_cell("D", end_time=0.004))
    with pytest.raises(ConfigError, match="resolved_pump_tissue@3 law"):
        parse_spec(raw)  # Plant: outside the scope the registry holds no such law.
    with scoped():
        spec = parse_spec(raw)
        impl = get_model(spec.model)
        assert PLANTED in impl.structure.declared_channel_laws
        state, p = impl.initial_values(spec)
        slot = [c.id for c in spec.model.channels].index("kv_planted_0")
        assert p.channel_laws[slot] == 5
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        end, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert valid
        voltage = v3.channel_voltage(
            impl.readouts(state, control, p, xp=np).field.rates.membrane_voltage_V, p, xp=np
        )
        target, _ = planted_law().kinetics(voltage[None, :], xp=np)
        moved = end.channel_gate[:, slot] - state.channel_gate[:, slot]
        toward = target[0][:, slot] - state.channel_gate[:, slot]
        assert np.all(moved * toward > 0)  # Its gates relax toward its law's own targets.
        assert bool(v3.domain_valid(state, p, p.active, xp=np, structure=impl.structure))
        assert not bool(v3.domain_valid(state, p, p.active, xp=np))  # The full catalogue refuses.


def rk4_world(dt):
    """Heredity cell D under RK4 without its NaV1.2 population, with the planted population."""
    raw = water_fixtures.heredity_cell("D", dt=dt, end_time=1e-4, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, 1e-4]
    m, e = raw["model"], raw["experiment"]
    keep = [c for c in m["channels"] if c["kinetic_law"] != spec_v3.NAV1P2_LAW_ID]
    ids = {c["id"] for c in keep}
    m["channels"] = keep
    e["channel_controls"] = [c for c in e["channel_controls"] if c["channel_id"] in ids]
    raw["execution"]["channel_capacity"] = len(keep)
    return with_planted(raw)


def test_an_rk4_step_above_the_laws_own_bound_is_refused():
    with scoped():
        timeline(parse_spec(rk4_world(BOUND_S)))  # Its bound, admitted.
        with pytest.raises(ConfigError, match=rf"\({PLANTED}\) require RK4 steps <= 2.5 us"):
            timeline(parse_spec(rk4_world(2 * BOUND_S)))
    raw = water_fixtures.heredity_cell("D", dt=5e-5, end_time=1e-4, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, 1e-4]
    with pytest.raises(ConfigError, match="Resolved NaV1.2 channels require RK4 steps <= 2.5 us"):
        timeline(parse_spec(raw))  # Today's first message.
    raw = rk4_world(5e-5)
    raw["model"]["channels"].pop()
    raw["experiment"]["channel_controls"].pop()
    raw["execution"]["channel_capacity"] -= 1
    with pytest.raises(ConfigError, match="Resolved gated channels require RK4 steps <= 25 us"):
        timeline(parse_spec(raw))  # Today's second message (Kir2.1 alone at 50 us).


def test_a_replacement_template_that_gates_a_registered_law_is_refused():
    cells = rfx.heredity_sheet(1, 0, dt=1e-3, end_time=0.05)
    template = rfx.template_from_cell(cells, "cell_1", "h")
    template["channel_gates"][PLANTED] = [0.2, 0.9]
    raw = rfx.with_replacement(cells, [template], [(0.01, "cell_0", "h", "n1")])
    with scoped(), pytest.raises(ConfigError, match="tables hold today's five channel laws"):
        parse_spec(raw)
    template["channel_gates"].pop(PLANTED)
    raw = rfx.with_replacement(cells, [template], [(0.01, "cell_0", "h", "n1")])
    with scoped():
        parse_spec(raw)  # Without it the template parses as today.
