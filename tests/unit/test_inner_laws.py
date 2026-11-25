"""Declared laws and one implementation per structure for resolved_pump_tissue@3 (D172, D176).

docs/INNER_MODEL_V4_DESIGN.md §7.4:
* the law declarations agree with today's tables, and their kernels and openings with today's
  dispatch, bit for bit, on the host and compiled;
* a definition's structure is value-free: equal structures share one cached implementation,
  which registry.get_model returns;
* the implementation's surface is the module's: structure-free names are the module's objects,
  the structure-dependent functions the module's bound once to the structure, plus new names;
* per-law dispatch: an undeclared law traces no kernel (A4's first test); readouts are today's
  bit for bit, the host keeping today's padding values (§7.4 (b)); the batch signature carries
  the structure, and the sizes of a kind's own axes;
* moved_rows lists every in-step mover of the inner model.
"""

import copy
import dataclasses
import functools
import inspect

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes
from cells.laws.channels import potassium_channels, sodium_channels, voltage_gates
from cells.laws.junctions import junction_gate
from cells.laws.pumps import calcium_atpase, kinetic_pump
from cells.models import inner_laws, surface_pump_v3
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_v3_fixtures as fixtures

ARS = "imex_ars222_face_electromigration@1"
SERIES_LAW = spec3.SERIES_GATE_LAW_ID  # FR-30's junction_series_gates@1 (D262).
TODAYS = {law_id: inner_laws.CHANNEL_LAWS[law_id] for law_id in spec3.TODAYS_CHANNEL_LAWS}
GATED = [law for law in TODAYS.values() if law.gated]  # The Kv1 laws': test_kv1_channel_laws.
KV1_CODES = {"kv1p1_mh2@1": 5, "kv1p2_mh@1": 6, "kv1p3_mh@1": 7, "kv1p4_mh@1": 8, "kv1p6_mh@1": 9}
LATER_CODES = {**KV1_CODES, "clleak_always_open@1": 10}  # Registered after today's five.
INNER_PROTOCOL = (
    "MODEL_ID",
    "STATE_AXES",
    "STATE_TYPE",
    "LAYOUT_TYPE",
    "FLOOR_LAYOUT_TYPE",
    "OBSERVATION_FIELDS",
    "BATCH_CAPACITIES",
    "ENERGY_RTOL",
    "EXPLICIT_STEP_BOUND",
    "OBSERVER_ID",
    "OBSERVATION_SAMPLING",
    "STAGE_DOMAIN_ID",
    "DISSIPATION_FIELDS",
    "DEVICE_CHECKS",
    "DEVICE_DIAGNOSTICS",
    "MembraneProcess",
    "initial_values",
    "parameters",
    "physical_amounts",
    "checked_step",
    "imex_step",
    "readouts",
    "field_values",
    "rhs",
    "domain_valid",
    "control_domain_valid",
    "balances",
    "device_balances",
    "channel_magnitudes",
    "check_values",
    "device_checks",
    "check_definition",
    "check_steps",
    "bind_step_checks",
    "batch_signature",
    "working_size",
    "observe_history",
    "summarize",
    "device_check_constants",
    "device_failure_message",
    "rebind",
)


def bits(value):
    value = np.ascontiguousarray(np.atleast_1d(np.asarray(value)))
    return value.view(np.uint8)


def same_bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and np.array_equal(bits(a), bits(b))


def zero_sign_only(a, b):
    """Equal values whose bit patterns differ only at zeros (-0.0 against +0.0)."""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.dtype != np.float64 or b.dtype != np.float64:
        return False
    a = np.ascontiguousarray(np.atleast_1d(a)).ravel()
    b = np.ascontiguousarray(np.atleast_1d(b)).ravel()
    differ = a.view(np.uint64) != b.view(np.uint64)
    return bool(np.all((a[differ] == 0) & (b[differ] == 0)))


# Compiled rates of an undeclared pump: exact zeros where today's compiled padding gives zeros of
# either sign (XLA's kernel at the neutral padding inputs is a tiny value, not +0.0 as NumPy's),
# so these may differ in the sign of a zero only. Integrated, +0.0 + dt (±0.0) is +0.0, so states
# and the host's observations stay bitwise (test_inner_dispatch_steps; check K2).
PUMP_RATE_KEYS = {
    f"derivative.{k}"
    for k in (
        "pump_dissipated_energy_pJ",
        "metabolic_work_pJ",
        "calcium_pump_dissipated_energy_pJ",
        "calcium_metabolic_work_pJ",
    )
}


def compiled_matches(compiled, reference):
    """Every compiled readout bitwise, or (undeclared pumps' rates) equal up to zeros' signs."""
    for key in reference:
        if same_bits(compiled[key], reference[key]):
            continue
        assert key in PUMP_RATE_KEYS and zero_sign_only(compiled[key], reference[key]), key


def voltages():
    """-120..60 mV, with the kernels' removable singularities (sodium_channels)."""
    grid = np.linspace(-0.120, 0.060, 1801)
    return np.concatenate((grid, [-0.025, -0.040, -0.065000123, 0.0]))


def test_channel_declarations_match_todays_tables():
    # Today's five keep their rows; the Kv1 pilot's five follow, registered with codes 5-9, then
    # the always-open chloride leak at 10.
    assert inner_laws.channel_codes() == {**dict(spec3.LAW_CODES), **LATER_CODES}
    assert list(inner_laws.CHANNEL_LAWS) == [*spec3.TODAYS_CHANNEL_LAWS, *LATER_CODES]
    for law_id, law in TODAYS.items():
        assert law.law_id == law_id
        assert len(law.gates) == spec3.GATE_COUNTS[law_id]
        assert law.gated == (law.code < spec3.GATED_CODES)
        assert law.permeant == tuple(
            (s, spec3.SPECIES_VALENCE[s], w) for s, w in spec3.LAW_PERMEABILITIES[law_id]
        )
        assert law.voltage_domain_V == surface_pump_v3.VOLTAGE_DOMAIN_V
        assert (law.kinetics is None) == (law.opening is None) == (not law.gated)
        assert law.reads == () and law.loop_term is None and law.provenance == "parity"
        assert law.represents is law.preserves is law.supports is law.qualified is None
    steps = {law_id: law.rk4_step_s for law_id, law in TODAYS.items()}
    assert steps == {
        spec3.KV1P5_LAW_ID: surface_pump_v3.RK4_POTASSIUM_STEP,
        spec3.KIR2P1_LAW_ID: surface_pump_v3.RK4_POTASSIUM_STEP,
        spec3.NAV1P2_LAW_ID: surface_pump_v3.RK4_SODIUM_STEP,
        spec3.KLEAK_LAW_ID: None,
        spec3.NALEAK_LAW_ID: None,
    }
    assert (surface_pump_v3.RK4_SODIUM_STEP, surface_pump_v3.RK4_POTASSIUM_STEP) == (2.5e-6, 25e-6)


@pytest.mark.parametrize("law", GATED, ids=lambda law: law.law_id)
def test_kernels_and_openings_are_todays_dispatch_bitwise(law):
    """Each gated law's own kernel and opening against today's catalogue dispatch, selected by
    the law's code: NumPy, eager JAX and compiled, bit for bit (probe P2's precondition)."""
    v = voltages()
    codes = np.full(v.shape, law.code)
    rng = np.random.default_rng(law.code)
    gates = rng.uniform(0.0, 1.0, (2, v.size))
    gates[:, :4] = [[0.0, 1.0, 0.5, 1e-300], [1.0, 0.0, 0.5, 1.0]]
    for xp in (np, jnp):
        mine, theirs = law.kinetics(v, xp=xp), sodium_channels.kinetics(v, codes, xp=xp)
        assert all(same_bits(a, b) for a, b in zip(mine, theirs, strict=True))
        assert same_bits(law.opening(gates, xp=xp), sodium_channels.opening(gates, codes, xp=xp))
    compiled = jax.jit(lambda u: law.kinetics(u, xp=jnp))(v)
    reference = jax.jit(lambda u: sodium_channels.kinetics(u, jnp.asarray(codes), xp=jnp))(v)
    assert all(same_bits(a, b) for a, b in zip(compiled, reference, strict=True))
    opened = jax.jit(lambda g: law.opening(g, xp=jnp))(gates)
    expected = jax.jit(lambda g: sodium_channels.opening(g, jnp.asarray(codes), xp=jnp))(gates)
    assert same_bits(opened, expected)


def test_junction_and_pump_declarations():
    junction, series = (inner_laws.JUNCTION_LAWS[k] for k in (junction_gate.LAW_ID, SERIES_LAW))
    assert list(inner_laws.JUNCTION_LAWS) == [junction_gate.LAW_ID, SERIES_LAW]
    assert series.gate_count == 2 and series.gated  # FR-30's series gates (D262).
    assert junction.law_id == junction_gate.LAW_ID and junction.gated and junction.gate_count == 1
    assert junction.kinetics is junction_gate.kinetics and junction.rhs is junction_gate.rhs
    assert junction.domain_valid is junction_gate.domain_valid
    assert junction.max_abs_voltage_V == junction_gate.MAX_ABS_VOLTAGE_V
    nak = inner_laws.PUMP_LAWS[kinetic_pump.LAW_ID]
    assert nak.moves == (("sodium", -3), ("potassium", 2))
    assert nak.kinetics is kinetic_pump.kinetics and nak.domain_valid is kinetic_pump.domain_valid
    ca = inner_laws.PUMP_LAWS[calcium_atpase.LAW_ID]
    assert ca.moves == (("calcium", -1),)
    assert ca.kinetics is calcium_atpase.kinetics
    for law in (nak, ca):
        assert law.fuel_kinds == ("maintained_chemical_reservoirs@1",)


def test_structure_of_definitions():
    release = parse_spec(fixtures.definition("release", solver=ARS))
    assert surface_pump_v3.structure(release.model) == inner_laws.InnerStructure(
        declared_channel_laws=tuple(spec3.LAW_CODES),
        junction_laws=(junction_gate.LAW_ID,),
        pump_laws=(kinetic_pump.LAW_ID, calcium_atpase.LAW_ID),
        fuel_kinds=(inner_laws.MAINTAINED_FUEL_ID,),
        junction_heat_booking=spec3.DEFAULT_JUNCTION_HEAT,
        crossing_junctions=("junction_0",),  # Fix (A): its junction joins floating components.
    )
    bare = parse_spec(fixtures.definition("release", solver=ARS, channels=False))
    assert surface_pump_v3.structure(bare.model).declared_channel_laws == ()
    heredity = parse_spec(water_fixtures.heredity_cell("D", end_time=0.01))
    s = surface_pump_v3.structure(heredity.model)
    assert s.declared_channel_laws == (spec3.KIR2P1_LAW_ID, spec3.NAV1P2_LAW_ID)
    assert s.junction_laws == () and s.pump_laws == (kinetic_pump.LAW_ID,)
    assert s.gate_rows == inner_laws.BASE_GATE_ROWS == 2
    assert [law.law_id for law in s.channel_laws] == list(s.declared_channel_laws)
    hash(s)  # Structure is a cache key.


def test_structure_refuses_unknown_or_unordered_laws():
    base = dict(
        junction_laws=(),
        pump_laws=(),
        fuel_kinds=(),
        junction_heat_booking=spec3.DEFAULT_JUNCTION_HEAT,
    )
    with pytest.raises(ValueError, match="Undeclared"):
        inner_laws.InnerStructure(declared_channel_laws=("tests.channel.unregistered@1",), **base)
    with pytest.raises(ValueError, match="code order"):
        inner_laws.InnerStructure(
            declared_channel_laws=(spec3.NAV1P2_LAW_ID, spec3.KIR2P1_LAW_ID), **base
        )


def scaled_values(raw, factor=0.75):
    """A value twin: every membrane permeability scaled; the structure is unchanged."""
    raw = copy.deepcopy(raw)
    for membrane in raw["model"]["membranes"]:
        p = membrane["permeability_m_per_s"]
        membrane["permeability_m_per_s"] = {k: factor * v for k, v in p.items()}
    return raw


def test_one_cached_implementation_per_structure():
    raw = water_fixtures.heredity_cell("D", end_time=0.01)
    a, b = parse_spec(raw), parse_spec(scaled_values(raw))
    assert a.model != b.model
    impl = get_model(a.model)
    assert isinstance(impl, surface_pump_v3.InnerImplementation)
    assert impl is get_model(b.model) is surface_pump_v3.model_for(a.model)
    assert impl is surface_pump_v3.implementation(surface_pump_v3.structure(a.model))
    assert impl.structure == surface_pump_v3.structure(b.model)
    assert impl.structure_key == (spec3.MODEL_ID, impl.structure)
    other = get_model(parse_spec(fixtures.definition("release", solver=ARS)).model)
    assert other is not impl and other.structure != impl.structure


def bound_to(value, function, structure):
    return (
        isinstance(value, functools.partial)
        and value.func is function
        and value.args == ()
        and value.keywords == {"structure": structure}
    )


def test_implementation_surface_is_the_modules():
    """Every public name of the module: structure-free names are the module's own objects, the
    structure-dependent functions are the module's bound once to the object's structure, and the
    batch signature carries the structure; the adapter's inner protocol is available."""
    spec = parse_spec(water_fixtures.heredity_cell("D", end_time=0.01))
    impl = get_model(spec.model)
    public = [name for name in dir(surface_pump_v3) if not name.startswith("_")]
    bound = set(surface_pump_v3.STRUCTURED_FUNCTIONS)
    for name in public:
        if name == "structure":  # The object's own structure, not the module's function.
            assert impl.structure == surface_pump_v3.structure(spec.model)
        elif name in bound:
            assert bound_to(getattr(impl, name), getattr(surface_pump_v3, name), impl.structure)
            assert getattr(impl, name) is getattr(impl, name)  # Stable: one object per name.
        elif name == "batch_signature":
            assert impl.batch_signature is surface_pump_v3.structured_batch_signature
        else:
            assert getattr(impl, name) is getattr(surface_pump_v3, name), name
    assert impl.domain_valid.with_control is impl.control_domain_valid
    # The adapter re-exports these @3 names (today's de facto inner protocol), and the operators
    # import the last ones directly.
    for name in INNER_PROTOCOL:
        assert hasattr(impl, name), name
    assert "steps" in inspect.signature(impl.check_values).parameters
    assert set(public) <= set(dir(impl))
    with pytest.raises(AttributeError):
        impl.no_such_name  # noqa: B018
    assert impl.declared_channel_laws == impl.structure.declared_channel_laws
    assert dict(impl.law_columns) == {spec3.KIR2P1_LAW_ID: 0, spec3.NAV1P2_LAW_ID: 1}
    assert impl.gate_rows == 2


def test_junction_kinetics_is_todays():
    spec = parse_spec(fixtures.definition("release", solver=ARS))
    impl = get_model(spec.model)
    _, p = impl.initial_values(spec)
    voltage = np.linspace(-0.12, 0.12, p.junction_minimum.size)
    mine = impl.junction_kinetics(voltage, p, xp=np)
    params = junction_gate.Parameters(p.junction_threshold_voltage, p.junction_minimum)
    theirs = junction_gate.kinetics(voltage, params, xp=np)
    assert all(same_bits(a, b) for a, b in zip(mine, theirs, strict=True))


def test_moved_rows():
    heredity = parse_spec(water_fixtures.heredity_cell("D", end_time=0.01)).model
    moved = surface_pump_v3.moved_rows(heredity)
    assert set(moved) == {"Na", "K", "M"}  # P, the fixed anion, is moved by nothing.
    kinds = {s: [(kind, law) for kind, law, _ in movers] for s, movers in moved.items()}
    assert kinds["Na"] == [
        ("membrane", "constant_field@1"),
        ("channel", spec3.NAV1P2_LAW_ID),
        ("pump", kinetic_pump.LAW_ID),
    ]
    assert kinds["K"] == [
        ("membrane", "constant_field@1"),
        ("channel", spec3.KIR2P1_LAW_ID),
        ("pump", kinetic_pump.LAW_ID),
    ]
    assert kinds["M"] == [("membrane", "constant_field@1")]
    release = parse_spec(fixtures.definition("release", solver=ARS)).model
    moved = surface_pump_v3.moved_rows(release)
    assert ("pump", calcium_atpase.LAW_ID) in [(k, law) for k, law, _ in moved["Ca"]]
    channels = {law: ids for kind, law, ids in moved["K"] if kind == "channel"}
    assert set(channels) == {spec3.KV1P5_LAW_ID, spec3.KIR2P1_LAW_ID, spec3.KLEAK_LAW_ID}
    for ids in channels.values():
        assert all(c in {p.id for p in release.channels} for c in ids)


# ------------------------------------------------------------------ per-law dispatch (§7.4 (c))

NAV1P2_LITERAL = "0.065000123"  # Only NaV1.2's kernel carries it (sodium_channels).
KV1P5_LITERAL = "0.0253"  # Kv1.5's inactivation midpoint (voltage_gates).


def without_law(raw, law):
    """raw without the populations of one channel law, and their schedules."""
    raw = copy.deepcopy(raw)
    gone = {c["id"] for c in raw["model"]["channels"] if c["kinetic_law"] == law}
    raw["model"]["channels"] = [c for c in raw["model"]["channels"] if c["id"] not in gone]
    controls = raw["experiment"]["channel_controls"]
    raw["experiment"]["channel_controls"] = [g for g in controls if g["channel_id"] not in gone]
    return raw


def padded(spec, extra=2):
    x = spec.execution
    execution = dataclasses.replace(x, channel_capacity=x.channel_capacity + extra)
    return dataclasses.replace(spec, execution=execution)


def initial(spec, model):
    from cells.execution.schedule import control_values

    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    return state, control, p


def jaxpr_text(model, spec):
    """The checked step's jaxpr at the initial state: tracing only, no compile."""
    state, control, p = jax.tree.map(jnp.asarray, initial(spec, model))
    closed = jax.make_jaxpr(lambda s, dt, c, q: model.checked_step(s, dt, c, q, q.active))(
        state, jnp.asarray(spec.execution.dt), control, p
    )
    return str(closed), len(closed.jaxpr.eqns)


def test_an_undeclared_law_traces_no_kernel():
    """A4's first test: the object's step traces the declared laws' kernels only; the module's
    own (today's catalogue) traces all of them."""
    raw = water_fixtures.heredity_cell("D", end_time=0.01)  # Kir2.1 and NaV1.2.
    for case, nav in ((raw, True), (without_law(raw, spec3.NAV1P2_LAW_ID), False)):
        spec = parse_spec(case)
        impl = get_model(spec.model)
        mine, mine_count = jaxpr_text(impl, spec)
        today, today_count = jaxpr_text(surface_pump_v3, spec)
        assert KV1P5_LITERAL in today and NAV1P2_LITERAL in today
        assert KV1P5_LITERAL not in mine
        assert (NAV1P2_LITERAL in mine) == nav
        assert mine_count < today_count
    assert surface_pump_v3.structure(spec.model).declared_channel_laws == (spec3.KIR2P1_LAW_ID,)


def flat_readouts(values):
    flat = {}
    for key, value in values.field._asdict().items():
        if hasattr(value, "_asdict"):
            flat.update({f"field.{key}.{k}": v for k, v in value._asdict().items()})
        else:
            flat[f"field.{key}"] = value
    flat.update({f"derivative.{k}": v for k, v in values.derivative._asdict().items()})
    for key in ("channel_flux_fmol_s", "channel_targets", "channel_tau_s", "valid"):
        flat[key] = getattr(values, key)
    return {k: np.asarray(v) for k, v in flat.items()}


def without_pumps(raw):
    """raw with no pump on any patch (and no pump schedule)."""
    raw = copy.deepcopy(raw)
    for membrane in raw["model"]["membranes"]:
        membrane["pump"] = None
    raw["experiment"]["pump_controls"] = []
    return raw


KERNELS = {
    "kv1p5": (voltage_gates, "kinetics"),
    "kir2p1": (potassium_channels, "kir2p1_kinetics"),
    "nav1p2": (sodium_channels, "nav1p2_kinetics"),
    "nak_pump": (kinetic_pump, "kinetics"),
    "calcium_pump": (calcium_atpase, "kinetics"),
    "junction_rhs": (junction_gate, "rhs"),
    "junction_domain": (junction_gate, "domain_valid"),
}


# The gated channel laws' declarations, whose kernels a structure's dispatch calls directly: since
# the per-law extraction (CORE_SEAMS §8.2) each declaration holds its own module's kernel, so a
# spy on the older kernel module (KERNELS) sees only today's catalogue dispatch.
DECLARED_KERNELS = {
    spec3.KV1P5_LAW_ID: "kv1p5",
    spec3.KIR2P1_LAW_ID: "kir2p1",
    spec3.NAV1P2_LAW_ID: "nav1p2",
}


def traced_kernels(monkeypatch, model, spec):
    """How often each law's kernel is called while the checked step is traced (no compile):
    through its module, as today's catalogue dispatch calls it, and through its declaration, at
    both places @3's dispatch reads one (InnerStructure.channel_laws and CHANNEL_LAWS)."""
    calls = dict.fromkeys(KERNELS, 0)

    def spy(name, original):
        def wrapped(*args, **kwargs):
            calls[name] += 1
            return original(*args, **kwargs)

        return wrapped

    for name, (module, attribute) in KERNELS.items():
        monkeypatch.setattr(module, attribute, spy(name, getattr(module, attribute)))
    spied = {
        law_id: dataclasses.replace(law, kinetics=spy(DECLARED_KERNELS[law_id], law.kinetics))
        if law_id in DECLARED_KERNELS
        else law
        for law_id, law in inner_laws.CHANNEL_LAWS.items()
    }
    declared = inner_laws.InnerStructure.channel_laws.fget
    monkeypatch.setattr(
        inner_laws.InnerStructure,
        "channel_laws",
        property(lambda self: tuple(spied[law.law_id] for law in declared(self))),
    )
    monkeypatch.setattr(inner_laws, "CHANNEL_LAWS", spied)
    jaxpr_text(model, spec)
    monkeypatch.undo()
    return calls


def test_undeclared_kernels_are_never_traced(monkeypatch):
    """A4's first test, by spies on every kernel: the object's step calls only the declared laws'
    kernels while it is traced, the module's own (today's catalogue) calls every one."""
    heredity = water_fixtures.heredity_cell("D", end_time=0.01)  # Kir2.1, NaV1.2, Na/K pump.
    cases = {
        "heredity_D": (heredity, {"kir2p1", "nav1p2", "nak_pump"}),
        "no_pumps": (without_pumps(heredity), {"kir2p1", "nav1p2"}),
        "no_nav": (without_law(heredity, spec3.NAV1P2_LAW_ID), {"kir2p1", "nak_pump"}),
    }
    for name, (raw, declared) in cases.items():
        spec = parse_spec(raw)
        mine = traced_kernels(monkeypatch, get_model(spec.model), spec)
        assert {k for k, n in mine.items() if n} == declared, (name, mine)
        today = traced_kernels(monkeypatch, surface_pump_v3, spec)
        assert all(today.values()), (name, today)


def test_batch_signature_carries_the_structure():
    raw = water_fixtures.heredity_cell("D", end_time=0.01)
    a, twin = parse_spec(raw), parse_spec(scaled_values(raw))
    other = parse_spec(without_law(raw, spec3.NAV1P2_LAW_ID))
    impl = get_model(a.model)
    assert impl.batch_signature(a.model) == impl.batch_signature(twin.model)
    assert impl.batch_signature(a.model) != impl.batch_signature(other.model)
    assert impl.batch_signature(a.model)[:-1] == surface_pump_v3.batch_signature(a.model)
    # And a kind's own axes, sized (the fourth review's finding 4): one value-free structure with
    # one entity or two on an own axis never shares a batch; a twin in IDs and values does.
    from tests.unit.test_cycle_kind import general
    from tests.unit.test_passive_routes_kind import P, closed_pair, route
    from tests.unit.test_transporter_kind import held_world, population, scoped

    def signature(raw):
        spec = parse_spec(raw)
        return get_model(spec.model).batch_signature(spec.model)

    with scoped():  # The transporter on its population axis.
        x, y = (general(population(id=i, capacity_fmol_s=c)) for i, c in (("t", 0.1), ("u", 0.05)))
        triples = [tuple(map(signature, (held_world(x), held_world(x, y), held_world(y))))]
    s, t = route("leak_S", P), route("leak_T", P / 2)
    triples.append(tuple(signature(closed_pair(routes=r)) for r in ([s], [s, t], [t])))  # Routes.
    for one, two, same_shapes in triples:
        assert one != two and one == same_shapes

    def reads_execution(spec, declaration):  # Planted: a view set that reads past the model.
        assert spec.execution is not None
        return passive_routes.view_sets(spec, declaration)

    with scoped(dataclasses.replace(passive_routes.PASSIVE_ROUTES, view_sets=reads_execution)):
        with pytest.raises(ConfigError, match="view_sets read more than its declaration"):
            signature(closed_pair(routes=[s]))


def test_a_composition_that_closes_slots_keeps_todays_padding_dynamics():
    """K2's amendment 6. Closers (operators with CLOSES) close population slots mid-run, and a
    closed slot keeps its gate update at code 0, the padding code. Where a composition closes
    slots, the compiled kinetics therefore evaluate the code-0 law there too (padding_fill),
    and a closed slot's gate keeps today's dynamics. Worlds without closers trace no code-0
    kernel (A4)."""
    from tests import partition_fixtures

    spec = parse_spec(partition_fixtures.divided())
    structure = surface_pump_v3.structure(spec.model)
    assert structure.padding_fill
    assert spec3.KV1P5_LAW_ID not in structure.declared_channel_laws
    plain = parse_spec(water_fixtures.heredity_cell("D", end_time=0.01))
    assert not surface_pump_v3.structure(plain.model).padding_fill
    voltage = jnp.linspace(-0.09, 0.03, 6)
    codes = jnp.zeros(6, dtype=jnp.int64)  # Every slot at code 0, as closed slots are.

    def kinetics(fill):
        bound = dataclasses.replace(structure, padding_fill=fill)
        return functools.partial(surface_pump_v3.channel_kinetics, xp=jnp, structure=bound)

    assert KV1P5_LITERAL in str(jax.make_jaxpr(kinetics(True))(voltage, codes))
    assert KV1P5_LITERAL not in str(jax.make_jaxpr(kinetics(False))(voltage, codes))
    today = jax.jit(functools.partial(surface_pump_v3.channel_kinetics, xp=jnp))(voltage, codes)
    mine = jax.jit(kinetics(True))(voltage, codes)
    assert all(same_bits(np.asarray(a), np.asarray(b)) for a, b in zip(mine, today, strict=True))
