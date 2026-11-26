"""Step checks bound to a definition (cells.model.resolved_pump_tissue@1-@3) and clock validation.

core.grid.checked_grid validates a definition's whole declared clock in chunks of
at most 1024 steps. The pump family's step checks read each chunk's largest step
and quantities of the definition alone, so bind_step_checks evaluates those once
per definition (two of its rate bounds build the layout). These tests pin that the
bound checks refuse exactly as the step checks did before (reference_* below are
those functions, unchanged), chunk by chunk in the same order, and that a long
clock builds the layout once, not once per chunk. The charge rule beside a floating node
(docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §8.3) has its definition's rows here, its stage's in
test_kind_rules.py. No JIT and no device.
"""

import copy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import NAV1P2_LAW_ID, projection
from cells.execution import grid as grid_module
from cells.execution.grid import EventGrid, checked_grid, clock_checks
from cells.execution.schedule import control_values
from cells.laws.electrochemistry import F, R
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_pump_v3 as third
from cells.models import surface_tissue as tissue
from cells.numerics import surface_imex as imex
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import species_sum
from cells.operators import species_common as common
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water
from validation.tissue import secreted_species_fixtures as secreted
from validation.tissue import surface_pump_fixtures as fixtures_1
from validation.tissue import surface_pump_v2_fixtures as fixtures_2
from validation.tissue import surface_pump_v3_fixtures as fixtures_3

SOLVERS = (imex.EULER_ID, imex.ARS222_ID, "rk4")
MODULES = {1: first, 2: second, 3: third}
OBSERVATIONS = "Resolved pump observations require accepted integration boundaries"


def reference_1(spec, steps, controls):
    """surface_pump.check_steps before bind_step_checks, verbatim."""
    if spec.execution.solver == "rk4":
        return kinetic.check_steps(spec, steps, controls)
    grid = EventGrid(spec)
    for t in spec.experiment.observation_times:
        try:
            grid.exact_index(t)
        except ConfigError as error:
            raise ConfigError(OBSERVATIONS) from error
    if np.max(steps, initial=0) * first.junction_gate_rate_bound(spec) > first.GATE_STEP_BOUND:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")
    if np.max(steps, initial=0) * first.explicit_rate_bound(spec) > first.EXPLICIT_STEP_BOUND:
        raise ConfigError("IMEX step exceeds the explicit-rate stability bound")


def reference_2(spec, steps, controls):
    """surface_pump_v2.check_steps before bind_step_checks, verbatim."""
    reference_1(spec, steps, controls)
    if spec.execution.solver != "rk4" and (
        np.max(steps, initial=0) * second.calcium_rate_bound(spec) > second.EXPLICIT_STEP_BOUND
    ):
        raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")


def reference_3(spec, steps, controls):
    """surface_pump_v3.check_steps before bind_step_checks, verbatim."""
    step, base = np.max(steps, initial=0), projection(spec)
    if spec.execution.solver == "rk4":
        tissue.check_steps(spec, steps, controls)
        laws = {c.kinetic_law for c in spec.model.channels if c.initial_gate}
        if NAV1P2_LAW_ID in laws and step > third.RK4_SODIUM_STEP + 1e-16:
            raise ConfigError("Resolved NaV1.2 channels require RK4 steps <= 2.5 us")
        if laws and step > third.RK4_POTASSIUM_STEP + 1e-16:
            raise ConfigError("Resolved gated channels require RK4 steps <= 25 us")
    else:
        grid = EventGrid(spec)
        for t in spec.experiment.observation_times:
            try:
                grid.exact_index(t)
            except ConfigError as error:
                raise ConfigError(OBSERVATIONS) from error
        if step * first.explicit_rate_bound(base) > third.EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit-rate stability bound")
        if step * second.calcium_rate_bound(base) > third.EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")
    if step * first.junction_gate_rate_bound(spec) > first.GATE_STEP_BOUND:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")


REFERENCES = {1: reference_1, 2: reference_2, 3: reference_3}


def definition(version, solver, *, end_time=None, early_event=False):
    """The clamped fixture world of each version (@3 with its eight channels)."""
    raw = {1: fixtures_1, 2: fixtures_2, 3: fixtures_3}[version].definition(
        "clamped", solver=solver
    )
    raw = copy.deepcopy(raw)
    e, x = raw["experiment"], raw["execution"]
    if end_time is not None:
        e["end_time"] = end_time
        x["max_steps"] = int(round(end_time / x["dt"])) + 8
    if early_event:  # An event-split step (3e-5 s, then 7e-5 s) in the first chunk.
        schedule = e["membrane_controls"][0]["schedule"]
        schedule.append(dict(schedule[-1], time=3e-5))
    return parse_spec(raw)


def outcome(function, *args):
    """None, or a refusal's type and message and those of its cause."""
    try:
        function(*args)
    except Exception as error:  # Every refusal is compared.
        cause = error.__cause__
        return type(error), str(error), None if cause is None else (type(cause), str(cause))
    return None


def patch_bounds(monkeypatch, explicit, calcium, junction):
    """Declared rate bounds (1/s); the explicit and calcium ones double on a definition
    that still has channels, so a check that read the wrong definition would differ."""

    def scaled(value):
        return lambda spec: value * (2.0 if getattr(spec.execution, "channel_capacity", 0) else 1)

    monkeypatch.setattr(first, "explicit_rate_bound", scaled(explicit))
    monkeypatch.setattr(second, "calcium_rate_bound", scaled(calcium))
    monkeypatch.setattr(first, "junction_gate_rate_bound", lambda spec: junction)


STEPS = (1e-6, 3e-6, 3e-5, 1e-4, 2e-4, 4e-3, 6e-3, 3e-2, 0.2)


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("version", (1, 2, 3))
def test_bound_checks_refuse_as_the_step_checks_did(monkeypatch, version, solver):
    """Every refusal, message and cause, in order, over bounds and step sizes."""
    spec, module, reference = definition(version, solver), MODULES[version], REFERENCES[version]
    controls = control_values(spec, np.zeros(4))
    refusals = set()
    for explicit in (0.0, 150.0, 400.0):
        for calcium in (0.0, 30.0, 300.0):
            for junction in (0.0, 20.0, 60.0):
                patch_bounds(monkeypatch, explicit, calcium, junction)
                bound = module.bind_step_checks(spec)  # Kept across the step sizes.
                for size in STEPS:
                    steps = np.full(4, size)
                    expected = outcome(reference, spec, steps, controls)
                    assert outcome(module.check_steps, spec, steps, controls) == expected
                    assert outcome(bound, steps) == expected
                    refusals.add(None if expected is None else expected[1])
    imex_refusals = {
        1: {"junction step", "explicit-rate"},
        2: {"junction step", "explicit-rate", "calcium pump"},
        3: {"junction step", "explicit-rate", "calcium pump"},
    }[version]
    rk4_refusals = {"0.0001 s", *(("2.5 us",) if version == 3 else ())}  # NaV1.2 present.
    wanted = rk4_refusals if solver == "rk4" else imex_refusals
    for part in wanted:  # Each refusal of the order was reached.
        assert any(r is not None and part in r for r in refusals), part
    assert None in refusals


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("version", (1, 2, 3))
def test_off_grid_observations_refuse_as_before(version, solver):
    spec = definition(version, solver)
    off = replace(spec, experiment=replace(spec.experiment, observation_times=(0.0, 3e-5)))
    steps = np.full(4, spec.execution.dt)
    controls = control_values(off, np.zeros(4))
    expected = outcome(REFERENCES[version], off, steps, controls)
    assert expected is not None and "accepted integration boundaries" in expected[1]
    assert expected[2] is not None  # The grid's own refusal is kept as the cause.
    assert outcome(MODULES[version].check_steps, off, steps, controls) == expected
    assert outcome(MODULES[version].bind_step_checks(off), steps) == expected
    assert outcome(checked_grid, off) == expected


def reference_checked_grid(spec, reference, window_steps):
    for times in EventGrid(spec).windows(0, window_steps):
        reference(spec, np.diff(times), control_values(spec, times[:-1]))


@pytest.mark.parametrize(
    "version, explicit, calcium, junction, refusal",
    [
        # The first chunk's largest step is 7e-5 s, the next chunks' 1e-4 s. Validating
        # the whole clock's largest step at once would refuse with the junction bound
        # (@1, @2) or the explicit bound (@3) instead.
        (1, 2e4, 0.0, 1500.0, "explicit-rate"),
        (2, 2e4, 0.0, 1500.0, "explicit-rate"),
        (2, 0.0, 2e4, 1500.0, "calcium pump"),
        (3, 1.2e4, 2e4, 0.0, "calcium pump"),
        (3, 1.2e4, 0.0, 1500.0, "explicit-rate"),
    ],
)
def test_clock_refusals_are_chunk_by_chunk_in_order(
    monkeypatch, version, explicit, calcium, junction, refusal
):
    spec = definition(version, imex.ARS222_ID, early_event=True)
    patch_bounds(monkeypatch, explicit, calcium, junction)
    expected = outcome(reference_checked_grid, spec, REFERENCES[version], 2)
    assert expected is not None and refusal in expected[1]
    assert outcome(lambda: checked_grid(spec, window_steps=2)) == expected


@pytest.mark.parametrize("solver", SOLVERS)
@pytest.mark.parametrize("version", (1, 2, 3))
def test_valid_clocks_pass_with_the_same_grid(version, solver):
    if version == 3 and solver == "rk4":
        spec = definition(3, solver)  # Gated NaV1.2: RK4 at 1e-4 s is refused.
        expected = outcome(reference_checked_grid, spec, reference_3, 1024)
        assert expected is not None and "2.5 us" in expected[1]
        assert outcome(checked_grid, spec) == expected
        return
    spec = definition(version, solver)
    reference_checked_grid(spec, REFERENCES[version], 1024)
    grid = checked_grid(spec)
    assert list(grid) == list(EventGrid(spec))


def counted(monkeypatch, module, name):
    calls, function = [0], getattr(module, name)

    def wrapper(*args, **kwargs):
        calls[0] += 1
        return function(*args, **kwargs)

    monkeypatch.setattr(module, name, wrapper)
    return calls


@pytest.mark.parametrize(
    "version, solver, builds",
    [(1, imex.ARS222_ID, 1), (2, imex.EULER_ID, 2), (3, imex.ARS222_ID, 2), (1, "rk4", 0)],
)
def test_a_long_clock_builds_each_layout_once(monkeypatch, version, solver, builds):
    """Layout builds (initial_values) per checked_grid do not grow with the clock.

    explicit_rate_bound and calcium_rate_bound each build one layout; before the
    bound checks, every chunk rebuilt them (100 and 200 chunks here). No chunk
    builds a control table either.
    """
    layouts = counted(monkeypatch, tissue, "initial_values")
    tables = counted(monkeypatch, grid_module, "control_values")
    for chunks in (100, 200):
        spec = definition(version, solver, end_time=chunks * 1024 * 1e-4)
        layouts[0] = tables[0] = 0
        grid = checked_grid(spec)
        assert -(-(len(grid) - 1) // 1024) == chunks
        assert (layouts[0], tables[0]) == (builds, 0)
    layouts[0] = 0  # One direct check_steps call (one chunk) builds as many.
    MODULES[version].check_steps(spec, np.full(4, 1e-4), None)
    assert layouts[0] == builds


def test_composites_bind_their_step_checks(monkeypatch):
    """Water @1/@2 and replacement @1 are compositions over @3 (models/pump_composite.py).

    Their check_steps is the composite's: @3's step checks on the definition the
    operators declare (each operator's inner_check_spec, v2 design R5), then each
    operator's own (the water bounds, for instance). The composite binds those to the
    definition (bind_step_checks), so the layouts they read are built once per clock, not
    once per chunk, no chunk builds a control table, and no operator refusal is skipped.
    """
    from cells.models import (
        cell_replacement,
        pump_composite,
        surface_pump_water,
        surface_pump_water_v2,
    )

    for module in (surface_pump_water, surface_pump_water_v2, cell_replacement):
        assert hasattr(module, "bind_step_checks"), module.__name__
    assert hasattr(pump_composite.Composition, "bind_step_checks")
    layouts = counted(monkeypatch, tissue, "initial_values")
    tables = counted(monkeypatch, grid_module, "control_values")
    builds = []
    for chunks in (3, 6):
        spec = parse_spec(water.with_water(water.heredity_cell(end_time=chunks * 1.0)))
        assert get_model(spec.model).module is surface_pump_water  # I2: per structure.
        layouts[0] = tables[0] = 0
        grid = checked_grid(spec)
        assert -(-(len(grid) - 1) // 1024) == chunks and tables[0] == 0
        builds.append(layouts[0])
    assert builds[0] == builds[1] > 0  # Once per clock: 3 or 6 chunks build the same.
    # 100 cm/s: dt x the water relaxation rate far above 0.05, an operator's refusal.
    fast = parse_spec(water.with_water(water.heredity_cell(end_time=0.01), pf_m_s=1.0))
    with pytest.raises(ConfigError, match="Water relaxation"):
        checked_grid(fast)
    with pytest.raises(ConfigError, match="Water relaxation"):
        clock_checks(fast)(np.full(2, 1e-3), np.array([0.0, 1e-3, 2e-3]))


# ------------------------------------------------------------------ the charge rule
# docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §8.3: a patch that faces a floating node (loose) relaxes
# a voltage of its own, so a cell's row divides by its other patches' (held) capacitance alone.

STEP = 1e-3
STORE = 3.3  # A store's capacitance over its cell's wall patch's.


def entity(raw, key, name):
    return next(x for x in raw["model"][key] if x["id"] == name)


def plain(**kwargs):
    """A quiescent secreted-species world as a bare cells.model.resolved_pump_tissue@3 definition."""
    raw = secreted.world(**kwargs)
    raw["model"]["id"] = "cells.model.resolved_pump_tissue@3"
    raw["model"].pop("inner_model")
    raw["model"].pop("operators")
    return raw


def conduct(raw, route, siemens):
    """Give a patch or junction the K permeability whose max-side slope F^2/RT P A c is siemens
    (every node of these worlds holds K at the bath's concentration)."""
    slope = F * F / (R * raw["model"]["temperature_K"])
    c = secreted.BATH_mM["K"]
    route["permeability_m_per_s"]["K"] = siemens / (slope * route["area_m2"] * c)


def pair(*, shared, junction, held=True):
    """Two cells on the bath, each with a contact patch on a floating node, its own or a shared
    one, and a junction j; held False drops cell_1's wall, so each of its patches floats."""
    nodes = ("ecs_0", "ecs_0") if shared else ("ecs_0", "ecs_1")
    raw = plain(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=tuple((n, 1.0) for n in dict.fromkeys(nodes)),
        contacts=tuple((f"contact_{k}", f"cell_{k}", n) for k, n in enumerate(nodes)),
        faces=(),
        junctions=(("j", "cell_0", "cell_1"),) if junction else (),
    )
    if not held:
        m, e = raw["model"], raw["experiment"]
        m["membranes"] = [p for p in m["membranes"] if p["id"] != "wall_cell_1"]
        e["membrane_controls"] = [
            c for c in e["membrane_controls"] if c["membrane_id"] != "wall_cell_1"
        ]
        raw["execution"]["membrane_capacity"] = len(m["membranes"])
    return raw


def charge_world(name, value):
    """The design's worlds A to D, `value` the dt x relaxation rate of their fastest charge mode
    at 1 ms (D's is the rate of its conducting patch, at least the mode's):
    - A: one cell, its wall patch (a K leak) on the bath, a silent store of 3.3 times the wall's
      capacitance;
    - B: two cells joined by a junction that carries K, a silent store each;
    - C: A in a closed world, its wall on a node a face joins to the gauge, and the store declared
      first, so that it is its component's representative;
    - D: one floating node that patches of two cells face, the small one conducting."""
    if name in "AC":
        raw = plain(faces=())
        if name == "C":
            raw = plain(
                nodes=(("ecs_0", 1.0), ("near", 1.0), ("g", 10.0)),
                faces=(("face_0", "near", "g", 1e-10, 1e-5),),
            )
            m = raw["model"]
            m["extracellular"] = [o for o in m["extracellular"] if o["id"] != "bath"]
            raw["execution"]["extracellular_capacity"] = 3
            m["closure"]["gauge_reference"] = "g"
            entity(raw, "membranes", "wall_cell_0")["outside"] = "near"
            for s in ("Na", "K", "Cl"):
                m["faces"][0]["diffusivity_m2_per_s"][s] = 1e-9
        wall = entity(raw, "membranes", "wall_cell_0")
        entity(raw, "membranes", "contact_0")["capacitance_F"] = STORE * wall["capacitance_F"]
        conduct(raw, wall, value * wall["capacitance_F"] / STEP)
        return raw
    raw = pair(shared=name == "D", junction=name == "B")
    if name == "B":
        for k in (0, 1):
            store = entity(raw, "membranes", f"contact_{k}")
            store["capacitance_F"] = STORE * secreted.WALL_C_F
        conduct(raw, raw["model"]["junctions"][0], value * secreted.WALL_C_F / (2 * STEP))
        return raw
    for patch, farads in (("wall_cell_0", 1e-14), ("wall_cell_1", 1e-10), ("contact_0", 1e-12)):
        entity(raw, "membranes", patch)["capacitance_F"] = farads
    small = entity(raw, "membranes", "contact_1")
    small["capacitance_F"] = 1e-13
    conduct(raw, small, value * small["capacitance_F"] / STEP)
    return raw


@pytest.mark.parametrize("name, refused", [("A", 2.2), ("B", 2.2), ("C", 2.2), ("D", 3.0)])
def test_the_rule_beside_a_floating_node_is_the_charge_modes_own(monkeypatch, name, refused):
    """The definition's bound is each world's own relaxation rate, and so is the stage's (B's
    junction has no row there), so the step checks, and the step where its patches conduct, refuse
    it above the bound and admit it below. Planted: no node floats, every patch counted in its
    cell's row, the rule before §8.3 without its node rows, which admits the refused step."""
    step = np.asarray([STEP])
    for value in (refused, 0.9):
        spec = parse_spec(charge_world(name, value))
        assert first.floating_nodes(spec.model) >= {"ecs_0"}
        rate = float(first.explicit_rate_bound(projection(spec)))
        assert STEP * rate == pytest.approx(value, rel=1e-12)
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        stage = 0.0 if name == "B" else value
        for rule in (model.membrane_rate, third.membrane_rate):  # And with no structure (NumPy).
            assert STEP * float(rule(state, control, p, xp=np)) == pytest.approx(stage, rel=1e-12)
        valid = model.imex_step(state, STEP, control, p, xp=np)[1]
        assert bool(valid) == (stage < 1)
        if value < 1:
            third.check_steps(spec, step, None)
            continue
        with pytest.raises(ConfigError, match="explicit-rate stability bound"):
            third.check_steps(spec, step, None)
        with monkeypatch.context() as plant:
            plant.setattr(first, "floating_nodes", lambda model: frozenset())
            third.check_steps(spec, step, None)


def test_a_floating_node_is_one_that_nothing_holds():
    """Not a held bath, not the gauge, and named by no face and no forms face. The definition's
    bound takes the set a caller gives in place of the definition's own: StepChecks gives the one
    that knows the forms faces, which its projection does not hold, so the patch of a node that
    only a forms face names is the cell's (0.27 at 1 ms over both patches, 3 over its own)."""
    node = {n: SimpleNamespace(id=n, reservoir=n == "bath") for n in ("bath", "g", "f", "x", "s")}
    model = SimpleNamespace(
        extracellular=tuple(node.values()),
        faces=(SimpleNamespace(sender="f", receiver="bath"),),
        forms_faces=(SimpleNamespace(sender="bath", receiver="x"),),
        gauge_reference="g",
    )
    assert first.floating_nodes(model) == {"s"}
    raw = plain()  # ecs_0 is joined to the bath by one face.
    raw["model"]["faces"][0]["law"] = "cells.route.logmean_electrodiffusion_forms@1"
    contact = entity(raw, "membranes", "contact_0")
    conduct(raw, contact, 3.0 * contact["capacitance_F"] / STEP)
    spec = parse_spec(raw)
    assert [f.id for f in spec.model.forms_faces] == ["face_0"] and not spec.model.faces
    checks = third.bind_step_checks(spec)
    cell = 3.0 * secreted.CONTACT_C_F / (secreted.CONTACT_C_F + secreted.WALL_C_F)
    assert STEP * float(checks.explicit_rate) == pytest.approx(cell, rel=1e-12)
    with third.forms_return_paths(spec.model):  # The projection alone: its node floats.
        alone = float(first.explicit_rate_bound(checks.base))
    assert STEP * alone == pytest.approx(3.0, rel=1e-12)


def test_a_cell_with_no_held_patch_is_refused_by_name_where_a_junction_charges_it():
    """cell_1's only patch faces the floating node it shares with cell_0, so no capacitance bounds
    what its junction charges: one that carries K is refused, naming the cell and the junction;
    one that carries nothing or the neutral species alone is not, nor K between two held cells."""
    for species, held, refused in (
        ("K", False, True),
        ("S", False, False),
        (None, False, False),
        ("K", True, False),
    ):
        raw = pair(shared=True, junction=True, held=held)
        if species:
            raw["model"]["junctions"][0]["permeability_m_per_s"][species] = 1e-12
        spec = parse_spec(raw)
        assert first.unheld_cells(spec.model) == (set() if held else {"cell_1"})
        if not refused:
            third.check_steps(spec, np.asarray([STEP]), None)
            continue
        with pytest.raises(ConfigError, match="Cell cell_1 has no held patch.*junction j"):
            third.check_steps(spec, np.asarray([STEP]), None)


def test_a_counter_ions_margin_reads_the_capacitance_the_bound_relaxes_it_over():
    """species_common.counter_ion_margin is the bound's own charge term over the row's material
    term, P A / V at the cell: on A's held wall patch, whose bound the store no longer dilutes,
    and on a loose patch, D's, over its own capacitance (a finite node's volume joins there)."""
    for name, patch, volumes in (("A", "wall_cell_0", 1.0), ("D", "contact_1", 2.0)):
        raw = charge_world(name, 0.9)
        route = entity(raw, "membranes", patch)
        permeance = route["permeability_m_per_s"]["K"] * route["area_m2"] / 1e-15  # 1/s per pL.
        margin, where = common.counter_ion_margin(parse_spec(raw), "K")
        assert where == f"membrane {patch}"
        assert margin == pytest.approx((0.9 / STEP) / (volumes * permeance), rel=1e-12)


def reference_explicit_rate_bound(spec):
    """surface_pump.explicit_rate_bound before §8.3's rule, verbatim (its node term, in a world
    with no floating node, is 0)."""
    _, p = kinetic.initial_values(spec)
    z2 = p.valence**2
    volume = np.where(p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf)
    zero = np.zeros((len(z2), p.outside_active.size))
    rows = scatter(p.face_factor, zero, (p.face_sender,), xp=np)
    rows += scatter(p.face_factor, zero, (p.face_receiver,), xp=np)
    face = 2 * np.max(rows / volume, initial=0.0)
    ci = np.where(p.active, p.amount_reference / p.volume, 0.0)
    co = np.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 0.0)
    slope = F * F / (R * p.temperature)
    capacitance = scatter(
        p.membrane_capacitance, np.zeros(p.active.size), (p.membrane_cell,), xp=np
    )
    capacitance = np.where(p.active, capacitance, np.inf)
    gj = (
        slope
        * np.sum(
            z2
            * p.junction_permeability
            * np.maximum(ci[:, p.junction_sender], ci[:, p.junction_receiver]),
            axis=0,
        )
        * np.where(p.junction_active, p.junction_area, 0.0)
    )
    cells = scatter(gj, np.zeros(p.active.size), (p.junction_sender,), xp=np)
    cells += scatter(gj, np.zeros(p.active.size), (p.junction_receiver,), xp=np)
    gm = (
        slope
        * np.sum(
            z2
            * p.membrane_permeability
            * np.maximum(ci[:, p.membrane_cell], co[:, p.membrane_outside]),
            axis=0,
        )
        * np.where(p.membrane_active, p.membrane_area, 0.0)
    )
    membranes = scatter(gm, np.zeros(p.active.size), (p.membrane_cell,), xp=np)
    return max(
        face,
        2 * np.max(cells / capacitance),
        np.max(membranes / capacitance),
        first.neutral_material_rate(p, volume),
    )


def reference_membrane_rate(state, control, p):
    """surface_pump_v3.membrane_rate before §8.3's rule, verbatim, without kinds (NumPy)."""
    ci, co = third.physical_amounts(state, p)
    ci = np.where(p.active, ci / p.volume, 0.0)
    co = np.where(p.outside_active, co / p.extracellular_volume, 0.0)
    slope, n, patch = F * F / (R * p.temperature), p.active.size, p.channel_membranes
    largest = np.maximum(ci[:, p.membrane_cell], co[:, p.membrane_outside])
    passive = (
        species_sum(p.valence**2 * p.membrane_permeability * largest, xp=np) * control.membrane
    )
    open_fraction = np.where(
        p.channel_active,
        p.channel_abundance * third.channel_opening(state.channel_gate, p.channel_laws, xp=np),
        0.0,
    )
    channel = species_sum(
        p.valence**2 * p.channel_permeability * p.channel_relative_permeability * largest[:, patch],
        xp=np,
    ) * (open_fraction * control.channel)
    membrane = np.where(p.membrane_active, passive * p.membrane_area, 0.0)
    membrane += scatter(channel * p.membrane_area[patch], membrane, (patch,), xp=np)
    total = slope * scatter(membrane, np.zeros(n), (p.membrane_cell,), xp=np)
    capacitance = scatter(p.membrane_capacitance, np.zeros(n), (p.membrane_cell,), xp=np)
    return np.max(np.where(p.active, total / np.where(p.active, capacitance, 1.0), 0.0))


@pytest.mark.parametrize("version", (1, 2, 3))
def test_the_rates_of_worlds_with_no_floating_node_are_the_old_rules_bit_for_bit(version):
    """The definition's bound (each version's, every initial condition of its fixture) and @3's
    stage rate at the initial state, with the structure and without, beside the functions as they
    were (reference_*)."""
    fixture = {1: fixtures_1, 2: fixtures_2, 3: fixtures_3}[version]
    for name in ("clamped", "release"):
        spec = parse_spec(fixture.definition(name, solver=imex.ARS222_ID))
        assert not first.floating_nodes(spec.model)
        base = projection(spec) if version == 3 else spec
        bound = float(first.explicit_rate_bound(base))
        assert bound > 0
        assert bound == float(reference_explicit_rate_bound(base))
        if version < 3:
            continue
        model = get_model(spec.model)
        assert model.structure.floating_nodes is False
        state, p = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        expected = float(reference_membrane_rate(state, control, p))
        assert expected > 0
        assert float(model.membrane_rate(state, control, p, xp=np)) == expected
        assert float(third.membrane_rate(state, control, p, xp=np)) == expected
