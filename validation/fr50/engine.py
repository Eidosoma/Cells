"""FR-50's engine values for the judge (validation/fr50/judge.py, `--engine
validation.fr50.engine:engine`), phase 1, under the judge's contract (its docstring) and its
erratum 1 (validation/fr50/JUDGE_ERRATUM_1.md).

**Each case's world** is built from the request's spec case (the registered cases.json's entry)
alone, each value read from its decimal string:
- K1 and K2: a cell and a finite node (the declared volumes) joined by one contact patch of the
  declared area, nothing else crossing (secreted_species_fixtures.world: quiescent ions, zero ion
  permeability, no face). One neutral passive route (cells.route.passive_neutral_permeation@1, `one_way: true`)
  carries S at the declared permeability and opening, S at the declared concentrations;
- K3: the same two nodes and patch, with a charged row Q of the declared valence at the declared
  concentrations (impermeant otherwise, its charge compensated in each node's fixed charge), on
  one constant-field route (cells.route.passive_constant_field_permeation@1, `one_way: true`);
- K4 and K4h: a cell on the held bath through its wall patch, with the neutral ATP-driven
  transporter (cells.cycle.atp_driven_transporter_mass_action_positive@1, version 1's form, `one_way: true`)
  on the patch: role Y at the declared inside and outside concentrations, held fuel ATP, ADP and Pi
  at the cell with the declared standard potentials mu°/RT and standard concentration c0.
Every world is at the declared temperature and runs @3 alone (its inner definition).

**Where each value comes from:**
- K1, K2 and K4 run compiled (cells.execution.runner.run) at each requested step to the last record
  time. Their rows are every accepted step's: n, and the records F and B, the net record and
  one_way_gap_relative of the case's route or patch, from the run's history.
- K2's restart: the run at the requested step, checkpointed at the requested time and resumed
  (run(spec, checkpoint)). Its rows after the checkpoint, and both runs' whole final states.
- K3 and K4h: the kind's own one_way_fluxes hook (bound in the active kind registry, so a plant
  applies) on the host, at the world's initial state: K3 at each requested voltage (the cell's
  potential, the node's 0), K4h at zero potentials.
- K5: each refusal's world, parsed (a definition-time refusal), with its control (erratum 1):
  - rectifier_route: K1's world with an inward rectifier on K that asks for one_way; the control is
    the same rectifier without the key;
  - net_flow_transporter_mode: K4's world with a population of a net-flow exchanger law (a fixture
    of this module, NET_FLOW_FIXTURE, never shipped) that asks for one_way; the control is the
    same population without the key;
  - rk4: K1's world under RK4; its control is the same world under its registered IMEX solver;
  - slot_operator: K4's world as a composite beside cells.operator.isopotential_partition@1, judged by the
    composite's slot-changer and lifecycle checks, as tests/unit/test_kind_lifecycle_roles.py
    judges a kind's admission beside a closer; the control is the population without the key.
- A request with a plant runs under validation/fr50/plants.py's planted kind registry.

Phase 2's kinds are not built here yet; they are judged at phase 2's landing.
"""

import contextlib
from decimal import Decimal

import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.kinds import passive_routes, transporter
from cells.laws.cycles.forms import CycleForm, FluxTerm
from cells.models import pump_composite
from cells.operators import OPERATORS
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.kind_registry import LabelView
from cells.registry.models import get_model
from validation.fr50 import plants
from validation.tissue import secreted_species_fixtures as fx

CELL, NODE, BATH = "cell_0", "ecs_0", "bath"
CONTACT, WALL = "contact_0", f"wall_{CELL}"
ROUTE = "route_0"  # The case's route, the only one.
POPULATION = "transporter_0"
SLOT_OPERATOR = "cells.operator.isopotential_partition@1"
RETIRES = "opens, closes or retires slots"  # The composite's words for a slot changer's refusals.
TRACE_mM = 1e-9
# A test-only net-flow exchanger (never shipped): K's row from N to P against Y's from P to N, one
# mode; K5's net-flow row declares it only to be refused, and its control parses it.
NET_FLOW_FIXTURE = law_registry.CycleLaw(
    "fr50test.cycle.net_flow_exchange@1",
    (),
    (),
    None,
    None,
    cycle=CycleForm(
        kinetics="net_flow",
        roles=(("X", 1), ("Y", 0)),
        rows=(("X", "N"), ("X", "P"), ("Y", "N"), ("Y", "P")),
        modes=(("exchange", (-1, 1, 1, -1)),),
        flux_terms=((FluxTerm(1.0, (-1, 1, 1, -1), 0.0),),),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only net-flow law for FR-50's K5 refusal row, never shipped",
)


def _value(text):
    """A spec value (a decimal string) as the float nearest it."""
    return float(Decimal(text))


def _inner(raw):
    """The composite fixture's inner @3 definition, its operators dropped (no operator is run)."""
    m = raw["model"]
    if "inner_model" in m:
        m["id"] = m.pop("inner_model")
    m.pop("operators", None)
    return raw


def _set_patch(raw, patch_id, *, area=None, availability=None):
    m = raw["model"]
    for patch in m["membranes"]:
        if patch["id"] == patch_id and area is not None:
            patch["area_m2"] = area
    if availability is not None:
        for control in raw["experiment"]["membrane_controls"]:
            if control["membrane_id"] == patch_id:
                control["schedule"] = [dict(time=0.0, availability=availability)]


def _add_charged(raw, sid, valence, concentrations):
    """raw with a charged row sid (impermeant) at {node: mM}, its charge compensated in each node's
    fixed charge, so the field starts where it did."""
    m = raw["model"]
    m["species"].append(dict(id=sid, valence=valence))
    for node in (*m["cells"], *m["extracellular"]):
        amount = node["volume_pL"] * concentrations.get(node["id"], TRACE_mM)
        node["initial_amount_fmol"][sid] = amount
        node["fixed_charge_equivalent_fmol"] -= valence * amount
    for patch in m["membranes"]:
        patch["permeability_m_per_s"][sid] = 0.0
    raw["execution"]["material_balance_atol_fmol"][sid] = 1e-15
    return raw


def route_world(case, *, dt, end, one_way=True):
    """K1's or K2's world (module docstring) from its spec case; dt and end in s."""
    c_cell = case.get("c_cell_mM", case.get("c_cell_mM_at_0"))
    c_node = case.get("c_node_mM", case.get("c_node_mM_at_0"))
    raw = fx.world(
        cells=((CELL, _value(case["V_cell_pL"])),),
        nodes=((NODE, _value(case["V_node_pL"])),),
        contacts=((CONTACT, CELL, NODE),),
        faces=(),
        dt=dt,
        end=end,
        concentrations_mM={CELL: _value(c_cell), NODE: _value(c_node)},
        trace_mM=TRACE_mM,
    )
    raw = _inner(raw)
    raw["model"]["temperature_K"] = _value(case["T_K"])
    _set_patch(raw, CONTACT, area=_value(case["A_m2"]), availability=_value(case["opening"]))
    route = dict(id=ROUTE, patch=CONTACT, law=passive_routes.LAW_ID, species=fx.SPECIES,
                 permeability_m_per_s=_value(case["P_m_per_s"]))  # fmt: skip
    if one_way:
        route[passive_routes.ONE_WAY_KEY] = True
    raw["model"][passive_routes.MODEL_KEY] = [route]
    return raw


def routes_world(k1_case, k2_case, *, dt, end):
    """K1 and K2 in one world with two species (the registration's §5, for the tests): K1's world
    with S on route_0 (K1's values) and S2 on route_1 (K2's permeability and concentrations). The
    two cases declare the same volumes, area, opening and temperature, which the world takes from
    K1's (refused where they differ)."""
    shared = ("T_K", "A_m2", "opening", "V_cell_pL", "V_node_pL")
    if any(k1_case[key] != k2_case[key] for key in shared):
        raise ConfigError(f"K1 and K2 share one world only where they declare the same {shared}")
    raw = route_world(k1_case, dt=dt, end=end)
    raw = add_inventory_species(
        raw, "S2", trace_mM=TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={
            CELL: _value(k2_case["c_cell_mM_at_0"]), NODE: _value(k2_case["c_node_mM_at_0"])
        },
    )  # fmt: skip
    raw["model"][passive_routes.MODEL_KEY].append(
        dict(id="route_1", patch=CONTACT, law=passive_routes.LAW_ID, species="S2",
             permeability_m_per_s=_value(k2_case["P_m_per_s"]), one_way=True)
    )  # fmt: skip
    return raw


def route_rows(result, dt, route, species):
    """A run's rows for one route of a routes world: n, F, B, net and gap at every accepted step."""
    s = list(result.spec.model.species_ids).index(species)
    return _rows(
        result, dt, lambda h: (
            np.asarray(h.passive_inward_fmol)[:, route],
            np.asarray(h.passive_outward_fmol)[:, route],
            np.asarray(h.passive_transferred)[:, s, route],
            np.asarray(h.passive_one_way_gap_relative)[:, route],
        ),
    )  # fmt: skip


def charged_world(case):
    """K3's host world (module docstring) from its spec case."""
    raw = fx.world(
        cells=((CELL, 1.0),), nodes=((NODE, 1.0),), contacts=((CONTACT, CELL, NODE),), faces=(),
        trace_mM=TRACE_mM,
    )  # fmt: skip
    raw = _add_charged(
        _inner(raw), "Q", int(case["valence"]),
        {CELL: _value(case["c_in_mM"]), NODE: _value(case["c_out_mM"])},
    )  # fmt: skip
    raw["model"]["temperature_K"] = _value(case["T_K"])
    _set_patch(raw, CONTACT, area=_value(case["A_m2"]), availability=_value(case["opening"]))
    raw["model"][passive_routes.MODEL_KEY] = [
        dict(id=ROUTE, patch=CONTACT, law=passive_routes.CHARGED_LAW_ID, species="Q",
             permeability_m_per_s=_value(case["P_m_per_s"]), one_way=True)
    ]  # fmt: skip
    return raw


def transporter_world(case, *, dt=1e-3, end=1e-3, one_way=True, population=None, inner=True):
    """K4's or K4h's world (module docstring) from its spec case; inner False keeps the composite
    fixture's form (no operator), for K5's slot row."""
    if _value(case["availability"]) != 1.0:
        raise ConfigError("version 1's layout holds each patch's availability at 1")
    raw = fx.world(
        cells=((CELL, 1.0),), nodes=(), contacts=(), faces=(), dt=dt, end=end, trace_mM=TRACE_mM
    )
    concentrations = {"Y": {CELL: case["c_in_mM"], BATH: case["c_out_mM"]}}
    for row, value in case["fuel_mM"].items():
        concentrations[row] = {CELL: value}
    for row, at in concentrations.items():
        raw = add_inventory_species(
            raw, row, trace_mM=TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM={node: _value(v) for node, v in at.items()},
        )  # fmt: skip
    raw = _inner(raw) if inner else raw
    m = raw["model"]
    m["temperature_K"] = _value(case["T_K"])
    m["standard_concentration_mM"] = _value(case["c0_mM"])
    for entry in m["species"]:
        if entry["id"] in case["mu0_over_RT"]:
            entry["standard_mu_RT"] = _value(case["mu0_over_RT"][entry["id"]])
    entry = population or dict(
        id=POPULATION, patch=WALL, law=transporter.NEUTRAL_LAW,
        capacity_fmol_s=_value(case["capacity_fmol_cycles_per_s"]),
        stoichiometry=int(case["stoichiometry"]), km_role_mM=_value(case["K_mM"]),
        km_atp_mM=_value(case["K_ATP_mM"]), role="Y",
        fuel=dict(kind=transporter.HELD, node=CELL, rows=["ATP", "ADP", "Pi"], ph_ref=None,
                  ph_band=None),
    )  # fmt: skip
    if one_way:
        entry = dict(entry, **{transporter.ONE_WAY_KEY: True})
    m[transporter.MODEL_KEY] = [entry]
    return raw


def _steps(dt, end):
    steps = Decimal(end) / Decimal(dt)
    if steps % 1:
        raise ConfigError(f"{end} s is not a whole number of steps {dt} s")
    return int(steps)


def _rows(result, dt, field):
    """n (the steps so far) and the case's record arrays at every accepted step of a run, from its
    history; field(history) gives (F, B, net, gap). The steps are consecutive at the fixed dt."""
    times = np.asarray(result.times, dtype=np.float64)
    n = np.rint(times / float(dt)).astype(np.int64)
    if np.any(np.diff(n) != 1) or not np.allclose(times, n * float(dt), rtol=0, atol=1e-9):
        raise AssertionError(f"the run's accepted times are not consecutive steps of {dt} s")
    F, B, net, gap = (np.asarray(x, dtype=np.float64) for x in field(result.history))
    return dict(n=n, F=F, B=B, net=net, gap=gap)


def _route_fields(spec):
    s = list(spec.model.species_ids).index(fx.SPECIES)
    return lambda h: (
        np.asarray(h.passive_inward_fmol)[:, 0],
        np.asarray(h.passive_outward_fmol)[:, 0],
        np.asarray(h.passive_transferred)[:, s, 0],
        np.asarray(h.passive_one_way_gap_relative)[:, 0],
    )


def _transporter_fields(spec):
    j = [p.id for p in spec.model.membranes].index(WALL)
    return lambda h: (
        np.asarray(h.transporter_forward_fmol)[:, j],
        np.asarray(h.transporter_backward_fmol)[:, j],
        np.asarray(h.transporter_cycles)[:, j],
        np.asarray(h.transporter_one_way_gap_relative)[:, j],
    )


def transporter_rows(result, dt):
    """A transporter world's run's rows (the wall patch's population): n, F, B, net and gap at
    every accepted step, from its history (the inner or the composite form)."""
    return _rows(result, dt, _transporter_fields(result.spec))


def _state(result):
    state = result.final.state
    return {name: np.asarray(getattr(state, name)) for name in type(state)._fields}


def _record_case(request):
    kind = request["kind"]
    case, end = request["spec"], request["record_times_s"][-1]
    out = dict(direction="forward" if kind == "K4" else "inward", runs={})
    results = {}
    for dt in request["dt_s"]:
        _steps(dt, end)  # The horizon is a whole number of steps.
        if kind == "K4":
            spec = parse_spec(transporter_world(case, dt=float(dt), end=float(end)))
            fields = _transporter_fields(spec)
        else:
            spec = parse_spec(route_world(case, dt=float(dt), end=float(end)))
            fields = _route_fields(spec)
        result = run(spec)
        results[dt] = (spec, result, fields)
        out["runs"][dt] = _rows(result, dt, fields)
    if request.get("restart_at_s") is not None:
        dt = request["restart_dt_s"] or request["dt_s"][0]
        spec, full, fields = results[dt]
        checkpoint = full.checkpoint_at(float(request["restart_at_s"]))
        resumed = run(spec, checkpoint)
        rows = _rows(resumed, dt, fields)
        after = rows["n"] > checkpoint.step_index
        out["restart"] = dict(
            dt_s=dt,
            from_n=int(checkpoint.step_index),
            **{q: v[after] for q, v in rows.items()},
            state=_state(resumed),
            uninterrupted_state=_state(full),
        )
    return out


def _host(raw):
    """(spec, state, p, control, the bound kind and its declaration) of a world on the host."""
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    ((_, kind, declaration),) = kind_registry.declared_kinds(spec.model.kinds)
    return spec, state, p, control, kind, declaration


def _k3(request):
    spec, state, p, control, kind, _ = _host(charged_world(request["spec"]))
    forward, backward = [], []
    for voltage in request["voltages_V"]:
        potentials = np.zeros(p.active.size + p.outside_active.size)
        potentials[[c.id for c in spec.model.cells].index(CELL)] = float(Decimal(voltage))
        view = LabelView(state, state, potentials, control)
        inward, outward = kind.one_way_fluxes(view, p, xp=np)["passive_transferred"]
        forward.append(inward[0])
        backward.append(outward[0])
    return dict(direction="inward", forward=np.asarray(forward), backward=np.asarray(backward))


def _k4h(request):
    spec, state, p, control, kind, _ = _host(transporter_world(request["spec"]))
    potentials = np.zeros(p.active.size + p.outside_active.size)
    view = LabelView(state, state, potentials, control)
    plus, minus = kind.one_way_fluxes(view, p, xp=np)["transporter_cycles"]
    j = [patch.id for patch in spec.model.membranes].index(WALL)
    return dict(direction="forward", J_plus=np.float64(plus[j]), J_minus=np.float64(minus[j]))


def _parsed(raw, laws=None):
    """None where the definition parses, else its refusal's message."""
    scope = law_registry.scope(laws) if laws is not None else contextlib.nullcontext()
    try:
        with scope:
            parse_spec(raw)
    except ConfigError as error:
        return str(error)
    return None


def _beside_slot_operator(raw):
    """The composite's slot-changer and lifecycle refusals of K4's world (the composite fixture's
    form) beside SLOT_OPERATOR, as tests/unit/test_kind_lifecycle_roles.py reads them."""
    inner = get_model(parse_spec(raw).model).inner
    operators = (OPERATORS[SLOT_OPERATOR],)
    errors = [e for e in pump_composite.structure_errors(inner, operators) if RETIRES in e]
    return errors + pump_composite.lifecycle_errors(inner, operators)


def _refusal(message, control):
    return dict(refused=message is not None, message=message or "", control_accepted=control)


def k5(k1_case, k4_case):
    """K5's four refusal rows (module docstring), from K1's and K4's spec cases."""
    rows = {}
    rectifier = dict(
        id="rectifier_K", patch=CONTACT, law=passive_routes.RECTIFIER_LAW_ID, species="K",
        g_ref_S_per_m2=1.0, k_ref_mM=5.0, v_half_V=0.01, slope_V=0.01,
    )  # fmt: skip
    asked = route_world(k1_case, dt=0.1, end=0.1)
    asked["model"][passive_routes.MODEL_KEY].append(dict(rectifier, one_way=True))
    control = route_world(k1_case, dt=0.1, end=0.1)
    control["model"][passive_routes.MODEL_KEY].append(rectifier)
    rows["rectifier_route"] = _refusal(_parsed(asked), _parsed(control) is None)
    laws = law_registry.BUILTIN.extended(NET_FLOW_FIXTURE)
    exchanger = dict(
        id="exchanger_0", host=WALL, law=NET_FLOW_FIXTURE.law_id, orientation={"N": "a"},
        capacity_fmol_s=0.05, roles={"X": "K", "Y": "Y"}, parameters={}, held_rows=[],
    )  # fmt: skip
    asked = transporter_world(k4_case, one_way=False, population=dict(exchanger, one_way=True))
    control = transporter_world(k4_case, one_way=False, population=exchanger)
    rows["net_flow_transporter_mode"] = _refusal(
        _parsed(asked, laws), _parsed(control, laws) is None
    )
    asked = route_world(k1_case, dt=0.1, end=0.1)
    control = route_world(k1_case, dt=0.1, end=0.1)  # Erratum 1: one_way, under the IMEX solver.
    asked["execution"]["solver"] = "rk4"
    rows["rk4"] = _refusal(_parsed(asked), _parsed(control) is None)
    asked = _beside_slot_operator(transporter_world(k4_case, inner=False))
    control = _beside_slot_operator(transporter_world(k4_case, one_way=False, inner=False))
    found = [e for e in asked if "one_way" in e]
    rows["slot_operator"] = _refusal(found[0] if found else None, not control)
    return dict(refusals=rows)


def engine(request):
    """The judge's engine function (its docstring's contract), phase 1."""
    kind = request["kind"]
    with plants.planted(request.get("plant")):
        if kind in ("K1", "K2", "K4"):
            return _record_case(request)
        if kind == "K3":
            return _k3(request)
        if kind == "K4h":
            return _k4h(request)
        if kind == "K5":
            return k5(*_phase_1_cases())
    raise NotImplementedError(f"FR-50's phase 2 ({kind}) is built after phase 1 lands")


def _phase_1_cases():
    """K1's and K4's spec cases from the registered cases.json (the judge's SPEC), for K5's worlds,
    which its request does not carry."""
    import json

    from validation.fr50 import judge

    cases = json.loads(judge.SPEC.read_text())["cases"]
    pick = {}
    for case_id, case in cases.items():
        for kind in ("K1", "K4"):
            if case_id.split("_")[0] == kind and kind not in pick:
                pick[kind] = case
    return pick["K1"], pick["K4"]
