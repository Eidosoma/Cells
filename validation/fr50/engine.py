"""FR-50's engine values for the judge (validation/fr50/judge.py, `--engine
validation.fr50.engine:engine`), both phases, under the judge's contract (its docstring) and its
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

**Phase 2** (fr50-one-way-records-v1 §3), @3's own records (its model key one_way_records), each
world from the registered cases alone:
- World 1 (world_1; E1 and E4): one 1 pL cell on the held bath at V = E_K by its charge anchor,
  its wall patch's own route and a gate-free K population with FR-51's declared block both
  carrying K at the declared values; their records are the patch's K pair and the population's.
- World 2 (world_2; E2 and E3): two 1 pL cells joined by a junction carrying S alone (its gate
  held at 1) and their two 1 pL nodes joined by a face carrying S alone, S at the declared
  concentrations and every potential 0; the junction's S pair and the face's.
- E1 to E4 run compiled at the engine's own step (PHASE_2_STEPS; the cases register none) to the
  last record time, once per world and plant. Each case's rows are its pair's records, net record
  and gap at every accepted step. E4's also hold the population's split and channel_rates' flux at
  each row's own state (channel_split_rows, on the host). World 1's restart is at mid-run.
- E6 on the host (e6_values): World 1's population at the declared voltages and availabilities,
  through clamped_channel_flux.
- E5 (e5): its four refusal rows, each with its control.
- A phase-2 plant runs under validation/fr50/plants.py's planted split, which rebuilds @3's
  implementation so a compiled run traces it.
"""

import contextlib
import copy
import math
from decimal import Decimal
from functools import cache

import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import ONE_WAY_RECORDS_KEY, control_values
from cells.execution.runner import run
from cells.kinds import passive_routes, transporter
from cells.laws.cycles.forms import CycleForm, FluxTerm
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.models import pump_composite, surface_pump_v3
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


# ------------------------------------------------------------------ phase 2: @3's own records
#
# World 1 (E1, E4, and E6's population) and World 2 (E2, E3), each from the registered cases alone
# (the module docstring, phase 2), and E5's refusals. The cases declare no step: each world's is
# the engine's own (PHASE_2_STEPS), a divisor of its record times.

CHANNEL = "k_population"  # World 1's gate-free K population (E4, E6).
BLOCKER = "blocker_B"  # FR-51's constant blocker: no species row (version 1).
CELL_1, NODE_1, CONTACT_1 = "cell_1", "ecs_1", "contact_1"  # World 2's second cell and node.
JUNCTION, FACE = "junction_0", "face_0"  # World 2's junction (E2) and face (E3).
KLEAK = "cells.channel.kleak_always_open@1"
FORMS_LAW = "cells.route.logmean_electrodiffusion_forms@1"
# World 1's patch capacitance per area (F/m^2), the engine's choice: the cases declare none, and at
# V = E_K the records do not depend on it (a typical specific membrane capacitance).
SPECIFIC_CAPACITANCE_F_PER_M2 = 1e-2
# The engine's steps (s), as decimal strings: World 1's records run 0.01 s apart to 0.1 s, World 2's
# 10 s apart to 100 s; World 2's step also meets the junction gate's conservative bound.
PHASE_2_STEPS = {"world_1": "0.0001", "world_2": "0.005"}
# The pairs each case reads, in its world's one_way_records, and its forward direction's word.
PAIRS = {
    "E1": ("membrane", WALL, "K"),
    "E4": ("channel", CHANNEL, "K"),
    "E2": ("junction", JUNCTION, "S"),
    "E3": ("face", FACE, "S"),
}
DIRECTION = {"E1": "outward", "E2": "sender", "E3": "sender", "E4": "outward", "E6": "outward"}


def _block(block):
    """E4's and E6's declared block (cases.json) as @3's channel entry's (FR-51's form), with the
    blocker's ID, which version 1 requires and the case leaves to the engine."""
    blocker, reference = block["blocker"], block["reference"]
    return dict(
        law="cells.channel_block.open_channel_block_weighted_modes@1",
        blocker=dict(
            id=BLOCKER, valence=int(blocker["valence"]), side=blocker["side"],
            concentration_mM=_value(blocker["concentration_mM"]),
        ),
        reference=reference if isinstance(reference, str) else dict(reference),
        modes=[
            {k: _value(v) for k, v in mode.items()} for mode in block["modes"]
        ],
    )  # fmt: skip


def _valences(raw):
    return {s["id"]: s["valence"] for s in raw["model"]["species"]}


def world_1(e1, e4, *, dt, end, records=True, solver=None):
    """World 1 (fr50-one-way-records-v1 §3): one 1 pL cell on the held bath through its wall patch
    of the declared area, at the declared temperature. K is 140 mM in the cell and 5.4 mM in the
    bath (as declared); the patch's own permeability carries K alone (E1's, or 0 without e1), and a
    gate-free K population (cells.channel.kleak_always_open@1) on the same patch carries it with
    FR-51's declared block (E4's). Every other row is impermeant, so V stays at E_K: the cell's
    charge anchor is C E_K, E_K = (R T/(z F)) ln(c_out/c_in) in binary64 from the declared
    concentrations, with its fixed charge closing the anchor (the bath stays electroneutral). Its
    one_way_records: the patch's own K route and the population's K (`records`)."""
    shared = ("T_K", "valence", "A_m2", "c_in_mM", "c_out_mM")
    if e1 is not None and any(e1[key] != e4[key] for key in shared):
        raise ConfigError(f"E1 and E4 share World 1 only where they declare the same {shared}")
    if e1 is not None and _value(e1["availability"]) != 1.0:
        raise ConfigError("World 1's patch is held open (the fixture's): E1's availability is 1")
    raw = _inner(
        fx.world(cells=((CELL, 1.0),), nodes=(), contacts=(), faces=(), dt=dt, end=end,
                 trace_mM=TRACE_mM)
    )  # fmt: skip
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    temperature, z = _value(e4["T_K"]), int(e4["valence"])
    m["temperature_K"] = temperature
    wall = next(p for p in m["membranes"] if p["id"] == WALL)
    wall["area_m2"] = _value(e4["A_m2"])
    wall["capacitance_F"] = SPECIFIC_CAPACITANCE_F_PER_M2 * wall["area_m2"]
    wall["permeability_m_per_s"]["K"] = 0.0 if e1 is None else _value(e1["P_m_per_s"])
    c_in, c_out = _value(e4["c_in_mM"]), _value(e4["c_out_mM"])
    cell = m["cells"][0]
    bath = next(n for n in m["extracellular"] if n["id"] == BATH)
    for node, c in ((cell, c_in), (bath, c_out)):
        node["initial_amount_fmol"]["K"] = c * node["volume_pL"]
    valence = _valences(raw)
    ions = lambda node: math.fsum(valence[s] * a for s, a in node["initial_amount_fmol"].items())  # noqa: E731
    bath["fixed_charge_equivalent_fmol"] = -ions(bath)
    e_k = R * temperature / (z * F) * math.log(c_out / c_in)
    charge = wall["capacitance_F"] * e_k
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - ions(cell)
    m["channels"] = [
        dict(
            id=CHANNEL, membrane_id=WALL, kinetic_law=KLEAK,
            max_permeability_m_per_s=_value(e4["P_m_per_s"]), abundance=_value(e4["abundance"]),
            initial_gate=[],
            permeant_ions=[dict(species_id="K",
                                relative_permeability=_value(e4["relative_permeability"]))],
            block=_block(e4["block"]),
        )
    ]  # fmt: skip
    e["channel_controls"] = [
        dict(channel_id=CHANNEL, schedule=[dict(time=0.0, availability=_value(e4["availability"]))])
    ]
    x["channel_capacity"] = 1
    if _value(e4["open_fraction"]) != 1.0:
        raise ConfigError("World 1's population is gate-free: its open fraction is 1")
    if records:
        m[ONE_WAY_RECORDS_KEY] = [
            dict(entity="membrane", id=WALL, species=["K"]),
            dict(entity="channel", id=CHANNEL, species=["K"]),
        ]
    if solver is not None:
        x["solver"] = solver
    return raw


def world_2(e2, e3, *, dt, end, records=True, inner=True):
    """World 2 (fr50-one-way-records-v1 §3): two 1 pL cells joined by a junction of the declared
    area that carries S alone at the declared permeability, its gate held open at 1 (a minimum open
    fraction of 1), and each cell's contact patch on its own 1 pL finite node, the two nodes joined
    by a face of the declared area and length carrying S alone at the declared diffusivity (the
    secreted-species fixture: quiescent ions, every potential 0). S is at the declared
    concentrations everywhere. Its one_way_records: the junction's S and the face's S. inner False
    keeps the composite fixture's form (no operator), whose step the records then cross."""
    raw = fx.world(
        cells=((CELL, 1.0), (CELL_1, 1.0)), nodes=((NODE, 1.0), (NODE_1, 1.0)),
        contacts=((CONTACT, CELL, NODE), (CONTACT_1, CELL_1, NODE_1)),
        faces=((FACE, NODE, NODE_1, _value(e3["A_m2"]), _value(e3["L_m"])),),
        junctions=((JUNCTION, CELL, CELL_1),), dt=dt, end=end, trace_mM=TRACE_mM,
        concentrations_mM={CELL: _value(e2["c_sender_mM"]), CELL_1: _value(e2["c_receiver_mM"]),
                           NODE: _value(e3["c_sender_mM"]), NODE_1: _value(e3["c_receiver_mM"])},
        diffusivity=_value(e3["D_m2_per_s"]),
    )  # fmt: skip
    raw = _inner(raw) if inner else raw
    m = raw["model"]
    if e2["T_K"] != e3["T_K"]:
        raise ConfigError("E2 and E3 share World 2 only at one temperature")
    m["temperature_K"] = _value(e2["T_K"])
    junction = m["junctions"][0]
    junction["area_m2"] = _value(e2["A_m2"])
    junction["permeability_m_per_s"][fx.SPECIES] = _value(e2["P_m_per_s"])
    if _value(e2["gate"]) != 1.0:
        raise ConfigError("World 2 holds its junction's gate at 1 by a minimum open fraction of 1")
    junction["gate"].update(minimum_open_fraction=1.0, initial_gate=1.0)
    for control in raw["experiment"]["junction_controls"]:
        control["schedule"] = [dict(time=0.0, availability=_value(e2["availability"]))]
    if records:
        m[ONE_WAY_RECORDS_KEY] = [
            dict(entity="junction", id=JUNCTION, species=[fx.SPECIES]),
            dict(entity="face", id=FACE, species=[fx.SPECIES]),
        ]
    return raw


def own_rows(result, dt, pair):
    """A run's rows for one of @3's own record pairs ((entity kind, entity ID, species ID)): n, F,
    B, the pair's net record and its gap at every accepted step, from the run's history (@3 alone
    or the composite form, whose model holds @3's fields)."""
    model = result.spec.model
    pairs = surface_pump_v3.structure(model).one_way_records
    index, (kind, entity, species) = pairs.index(pair), pair
    slots = dict(
        channel=[c.id for c in model.channels], face=[f.id for f in model.faces],
        junction=[j.id for j in model.junctions], membrane=[p.id for p in model.membranes],
    )  # fmt: skip
    s, slot = list(model.species_ids).index(species), slots[kind].index(entity)
    net = surface_pump_v3.ONE_WAY_NETS[kind]
    return _rows(
        result, dt, lambda h: (
            np.asarray(h.one_way_forward_fmol)[:, index],
            np.asarray(h.one_way_backward_fmol)[:, index],
            np.asarray(getattr(h, net))[:, s, slot],
            np.asarray(h.one_way_gap_relative)[:, index],
        ),
    )  # fmt: skip


def channel_split_rows(result, rows=None):
    """E4's extra columns at every accepted row (or the given row indices), on the host: the
    population's K split (outward, inward) and channel_rates' outward K flux at the row's own state,
    controls and membrane voltage (its field's), through clamped_channel_flux."""
    spec = result.spec
    impl = get_model(spec.model)
    _, p = impl.initial_values(spec)
    times = np.asarray(result.times, dtype=np.float64)
    controls = control_values(spec, times)
    k = list(spec.model.species_ids).index("K")
    history = [np.asarray(v) for v in result.history]
    forward, backward, flux = [], [], []
    for i in range(times.size) if rows is None else rows:
        state = impl.STATE_TYPE(*(v[i] for v in history))
        control = impl.Control(*(np.asarray(v)[i] for v in controls))
        voltage = impl.field_values(state, control, p, xp=np).rates.membrane_voltage_V
        j, _, (out, back) = impl.clamped_channel_flux(state, control, p, voltage, xp=np,
                                                      one_way=True)  # fmt: skip
        forward.append(out[k, 0])
        backward.append(back[k, 0])
        flux.append(j[k, 0])
    return dict(split_forward=np.asarray(forward), split_backward=np.asarray(backward),
                channel_flux=np.asarray(flux))  # fmt: skip


@cache
def _phase_2_run(world, dt, end, plant):
    """(spec, result) of World 1 or 2 at dt to end (decimal strings), one run per plant (the
    planted runs compile their own programs: validation/fr50/plants.py)."""
    cases = _cases()
    if world == "world_1":
        raw = world_1(cases["E1"], cases["E4"], dt=float(dt), end=float(end))
    else:
        raw = world_2(cases["E2"], cases["E3"], dt=float(dt), end=float(end))
    spec = parse_spec(raw)
    return spec, run(spec)


@cache
def _phase_2_restart(world, dt, end, at):
    """The run resumed from its checkpoint at `at` (s): (checkpoint, resumed result)."""
    spec, full = _phase_2_run(world, dt, end, None)
    checkpoint = full.checkpoint_at(float(at))
    return checkpoint, run(spec, checkpoint)


def _own_record_case(request):
    kind = request["kind"]
    world = "world_1" if kind in ("E1", "E4") else "world_2"
    dt, end = PHASE_2_STEPS[world], request["record_times_s"][-1]
    _steps(dt, end)  # The horizon is a whole number of steps.
    spec, result = _phase_2_run(world, dt, end, request.get("plant"))
    rows = own_rows(result, dt, PAIRS[kind])
    if kind == "E4":
        rows |= channel_split_rows(result)
    out = dict(direction=DIRECTION[kind], runs={dt: rows})
    if request.get("restart_at_s") is not None:
        checkpoint, resumed = _phase_2_restart(world, dt, end, request["restart_at_s"])
        after_rows = own_rows(resumed, dt, PAIRS[kind])
        after = after_rows["n"] > checkpoint.step_index
        out["restart"] = dict(
            dt_s=dt,
            from_n=int(checkpoint.step_index),
            **{q: v[after] for q, v in after_rows.items()},
            state=_state(resumed),
            uninterrupted_state=_state(result),
        )
    return out


def e6_values(case, evaluations):
    """E6 on the host: World 1's population (its patch's own route closed) at the initial state, at
    each (V, availability) of the request (decimal strings): u, its K split (outward, inward) and
    channel_rates' outward K flux, all through clamped_channel_flux at that patch voltage with the
    population's held availability set."""
    spec = parse_spec(world_1(None, case, dt=1e-4, end=1e-4))
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    k = list(spec.model.species_ids).index("K")
    out = {q: [] for q in ("u", "forward", "backward", "channel_flux")}
    for voltage, availability in evaluations:
        held = control._replace(channel=np.full_like(control.channel, float(Decimal(availability))))
        flux, _, terms, (forward, backward) = impl.clamped_channel_flux(
            state, held, p, float(Decimal(voltage)), xp=np, block=True, one_way=True
        )
        out["u"].append(terms.block.u[0])
        out["forward"].append(forward[k, 0])
        out["backward"].append(backward[k, 0])
        out["channel_flux"].append(flux[k, 0])
    return {q: np.asarray(v, dtype=np.float64) for q, v in out.items()}


def e5(cases):
    """E5's four refusal rows (the judge's REFUSALS["E5"]), each the world with its declaration
    against the same world without it (the control, which must be accepted):
    - charged_face_row: World 2 with a record of K, a charged row, on its face;
    - forms_face: World 2 with its face on the forms law
      (cells.route.logmean_electrodiffusion_forms@1) and a record of S on that face;
    - pump: @3's closed fixture (validation/tissue/surface_pump_v3_fixtures, with Na/K pumps) with
      a record on its first pump;
    - rk4: World 1 with its records under RK4; its control, World 1 without them under RK4, which
      admits a world without kinds (erratum 1)."""
    from validation.tissue import surface_pump_v3_fixtures as closed

    rows = {}
    two = dict(dt=float(PHASE_2_STEPS["world_2"]), end=float(PHASE_2_STEPS["world_2"]))
    asked = world_2(cases["E2"], cases["E3"], **two)
    asked["model"][ONE_WAY_RECORDS_KEY].append(dict(entity="face", id=FACE, species=["K"]))
    control = world_2(cases["E2"], cases["E3"], **two)
    rows["charged_face_row"] = _refusal(_parsed(asked), _parsed(control) is None)
    control = world_2(cases["E2"], cases["E3"], records=False, **two)
    control["model"]["faces"][0]["law"] = FORMS_LAW
    asked = copy.deepcopy(control)
    asked["model"][ONE_WAY_RECORDS_KEY] = [dict(entity="face", id=FACE, species=[fx.SPECIES])]
    rows["forms_face"] = _refusal(_parsed(asked), _parsed(control) is None)
    control = closed.definition("closed")
    pump = control["model"]["membranes"][0]["pump"]["id"]
    asked = copy.deepcopy(control)
    asked["model"][ONE_WAY_RECORDS_KEY] = [dict(entity="pump", id=pump, species=["Na"])]
    rows["pump"] = _refusal(_parsed(asked), _parsed(control) is None)
    one = dict(dt=float(PHASE_2_STEPS["world_1"]), end=float(PHASE_2_STEPS["world_1"]))
    asked = world_1(cases["E1"], cases["E4"], solver="rk4", **one)
    control = world_1(cases["E1"], cases["E4"], solver="rk4", records=False, **one)
    rows["rk4"] = _refusal(_parsed(asked), _parsed(control) is None)
    return dict(refusals=rows)


def engine(request):
    """The judge's engine function (its docstring's contract), both phases."""
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
        if kind in PAIRS:
            return _own_record_case(request)
        if kind == "E6":
            values = e6_values(request["spec"], request["evaluations"])
            return dict(direction=DIRECTION["E6"], **values)
        if kind == "E5":
            return e5(_cases())
    raise NotImplementedError(f"no engine values for case kind {kind!r}")


def _cases():
    """{case kind: the first spec case of that kind} from the registered cases.json (the judge's
    SPEC), for the worlds a request's own case does not hold (World 1's two cases, World 2's two,
    E5's)."""
    import json

    from validation.fr50 import judge

    cases = json.loads(judge.SPEC.read_text())["cases"]
    pick = {}
    for case_id, case in cases.items():
        pick.setdefault(case_id.split("_")[0], case)
    return pick


def _phase_1_cases():
    """K1's and K4's spec cases from the registered cases.json (the judge's SPEC), for K5's worlds,
    which its request does not carry."""
    pick = _cases()
    return pick["K1"], pick["K4"]
