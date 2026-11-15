"""Declared laws and one implementation per structure for resolved_pump_tissue@3 (D172, D176).

docs/INNER_MODEL_V4_DESIGN.md §7.4, the first API commit:
* the law declarations agree with today's tables, and their kernels and openings with today's
  dispatch, bit for bit, on the host and compiled;
* a definition's structure is value-free: equal structures share one cached implementation,
  which registry.get_model returns;
* the implementation's surface is the module's: every public name, the same object (programs
  are unchanged in this commit), plus the new names;
* moved_rows lists every in-step mover of the inner model.
"""

import copy
import inspect

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import surface_pump_v3_spec as spec3
from cells.core.specs import parse_spec
from cells.models import inner_laws, surface_pump_v3
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from cells.processes import calcium_atpase, junction_gate, kinetic_pump, sodium_channels
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_v3_fixtures as fixtures

ARS = "imex_ars222_face_electromigration@1"
GATED = [law for law in inner_laws.CHANNEL_LAWS.values() if law.gated]
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
    value = np.atleast_1d(np.asarray(value))
    return value.view(np.uint8)


def same_bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and np.array_equal(bits(a), bits(b))


def voltages():
    """-120..60 mV, with the kernels' removable singularities (sodium_channels)."""
    grid = np.linspace(-0.120, 0.060, 1801)
    return np.concatenate((grid, [-0.025, -0.040, -0.065000123, 0.0]))


def test_channel_declarations_match_todays_tables():
    assert inner_laws.channel_codes() == dict(spec3.LAW_CODES)
    for law_id, law in inner_laws.CHANNEL_LAWS.items():
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
    steps = {law_id: law.rk4_step_s for law_id, law in inner_laws.CHANNEL_LAWS.items()}
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
    (junction,) = inner_laws.JUNCTION_LAWS.values()
    assert junction.law_id == junction_gate.LAW_ID and junction.gated
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
        inner_laws.InnerStructure(declared_channel_laws=("unregistered@1",), **base)
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


def test_implementation_surface_is_the_modules():
    """Every public name of the module, the module's own object (no program changes in this
    commit), beside the object's own structure; the adapter's inner protocol is available."""
    impl = get_model(parse_spec(water_fixtures.heredity_cell("D", end_time=0.01)).model)
    public = [name for name in dir(surface_pump_v3) if not name.startswith("_")]
    for name in public:
        if name == "structure":  # The object's own structure, not the module's function.
            continue
        assert getattr(impl, name) is getattr(surface_pump_v3, name), name
    # The adapter re-exports these @3 names (today's de facto inner protocol), and the operators
    # import the last ones directly.
    for name in INNER_PROTOCOL:
        assert getattr(impl, name) is getattr(surface_pump_v3, name), name
        assert getattr(adapter, name, getattr(impl, name)) is getattr(impl, name), name
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
