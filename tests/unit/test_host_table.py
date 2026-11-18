"""The host table (docs/CORE_SEAMS_DESIGN.md §2, §3): seam A's prerequisite, read from the layout.

Each claim at its cheapest level (D187), each with a planted error the check must catch:
- every declared patch and junction is one row, with its kind and its two end nodes, and padded
  slots are inactive rows; a junction with swapped ends, or read as a patch, fails the check;
- each host's voltage by its kind's rule is @3's own membrane and junction voltage, bitwise, on
  the host and on the device; the reversed rule fails;
- the ends the kinds resolve today (transporter.gather, passive_routes._ends) are the table's;
- under a composite the table reads the adapter's view: a patch or junction a closer closes reads
  inactive, and moves and conducts nothing there, while the declared layout reads it active;
- host_scatter puts each entity's values at its host's two end nodes (a reference loop), and a
  transfer from end a to end b conserves; swapped ends fail the reference;
- host_node_conductance is patch_node_conductance on patches, bitwise;
- the host side resolves declared hosts and refuses any other ID;
- the table adds no layout field, and KindRates is the kind contract's object (§8.5, §18).
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import passive_routes, transporter
from cells.models import surface_pump_v3 as v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import partition_fixtures as pf
from tests.unit.test_passive_routes_kind import P, closed_pair, route
from tests.unit.test_transporter_kind import held_world, scoped
from validation.tissue import pump_water_fixtures as water_fixtures

EXTRA = dict(capacity=1, extracellular_capacity=1, membrane_capacity=2, edge_capacity=3)


def padded_sheet():
    """The seven-cell gated sheet (patches and voltage-gated junctions), every capacity padded."""
    raw = water_fixtures.gated_sheet(end_time=0.01)
    for key, more in EXTRA.items():
        raw["execution"][key] += more
    return parse_spec(raw)


def bound(spec, *, kick=0.0):
    """(implementation, state, layout, control) at t = 0; kick shifts the cells' amounts so that
    neighbouring cells differ in potential (the junction voltages are then nonzero)."""
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    if kick:
        shift = kick * np.arange(state.amount_increment.size).reshape(state.amount_increment.shape)
        state = state._replace(amount_increment=state.amount_increment + shift)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return impl, state, p, control


def matches_definition(table, spec):
    """Whether a table states each declared host's kind, ends and activity, and padding inactive."""
    nodes, ids = v3.node_ids(spec), v3.host_ids(spec)
    declared = v3.declared_hosts(spec)
    for row, host_id in enumerate(ids):
        if host_id is None:
            if table.active[row]:
                return False
            continue
        host = declared[host_id]
        if not (
            host.index == row
            and v3.HOST_KINDS[table.kind[row]] == host.kind
            and nodes[table.end_a[row]] == host.end_a
            and nodes[table.end_b[row]] == host.end_b
            and table.active[row]
        ):
            return False
    return len(ids) == len(table.kind) == len(table.end_a) == len(table.end_b)


def test_the_table_lists_each_declared_host_with_its_ends():
    spec = padded_sheet()
    _, _, p, _ = bound(spec)
    table = v3.host_table(p, xp=np)
    m = spec.model
    assert len(m.membranes) == 7 and len(m.junctions) == 12  # Patches and junctions, padded.
    assert matches_definition(table, spec)
    first = len(p.membrane_active)  # The first junction's row.
    end_a, end_b = table.end_a.copy(), table.end_b.copy()  # Plant: its ends swapped.
    end_a[first], end_b[first] = table.end_b[first], table.end_a[first]
    assert not matches_definition(table._replace(end_a=end_a, end_b=end_b), spec)
    as_patch = table._replace(kind=table.kind.copy())  # Plant: a junction read as a patch.
    as_patch.kind[first] = v3.HOST_KINDS.index("patch")
    assert not matches_definition(as_patch, spec)


def test_host_voltages_are_the_models_own_bitwise():
    spec = padded_sheet()
    impl, state, p, control = bound(spec, kick=1e-4)
    w = impl.readouts(state, control, p, xp=np)
    potentials, rates = w.field.potential_V, w.field.rates
    m = len(p.membrane_active)
    voltage = v3.host_voltage(potentials, p, xp=np)
    expected = np.concatenate((rates.membrane_voltage_V, rates.junction_voltage_V))
    assert np.any(rates.junction_voltage_V != 0.0)  # The rule is exercised on both kinds.
    assert np.array_equal(voltage, expected)
    device = jax.jit(lambda v, q: v3.host_voltage(v, q))(
        jnp.asarray(potentials), jax.tree.map(jnp.asarray, p)
    )
    assert np.array_equal(np.asarray(device), expected)
    table = v3.host_table(p, xp=np)
    reversed_rule = np.where(table.active, potentials[table.end_b] - potentials[table.end_a], 0.0)
    assert not np.array_equal(reversed_rule[m:], expected[m:])  # Plant: the rule reversed.


def test_the_ends_the_kinds_resolve_are_the_tables():
    with scoped():  # The transporter's role at each membrane slot's two ends.
        spec = parse_spec(held_world())
        impl, state, p, _ = bound(spec)
        inside, outside, _ = transporter.gather(state, p, xp=np)
        slots = np.arange(len(p.membrane_active))
        a, b = v3.host_ends(v3.node_concentrations(state, p, xp=np), slots, p, xp=np)
        assert np.array_equal(a[p.transporter_role, slots], inside)
        assert np.array_equal(b[p.transporter_role, slots], outside)
    spec = parse_spec(closed_pair(routes=[route("leak_S", P, host=("patch", "contact_0"))]))
    _, state, p, _ = bound(spec)
    c_in, c_out = passive_routes._ends(state, p, np)
    (declared,) = dict(spec.model.kinds)[passive_routes.KIND_ID]
    hosts = np.asarray([v3.host_index(spec, declared.host)])
    a, b = v3.host_ends(v3.node_concentrations(state, p, xp=np), hosts, p, xp=np)
    assert np.array_equal(a, c_in) and np.array_equal(b, c_out)
    assert not np.array_equal(b, c_in)  # Plant: the ends read the other way round differ.


def test_a_host_a_closer_closes_reads_inactive_at_the_view():
    spec = parse_spec(pf.divided(neighbour=True))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    view = model.view(p, state, xp=np)  # Before the division the daughters' slots are closed.
    ids = v3.host_ids(spec)
    closed = [i for i, host in enumerate(ids) if host is not None and "_d" in host]
    assert closed  # The daughters' patches and their contacts.
    declared, at_view = v3.host_table(p, xp=np), v3.host_table(view, xp=np)
    assert declared.active[closed].all()  # Plant: the declared layout would read them open.
    assert not at_view.active[closed].any() and at_view.active[[0, 1]].all()
    potentials = np.linspace(-0.07, 0.02, view.active.size + view.outside_active.size)
    assert np.all(v3.host_voltage(potentials, view, xp=np)[closed] == 0.0)
    hosts = np.asarray(closed)
    ones = np.ones((2, len(closed)))
    cell, outside = v3.host_scatter(-ones, ones, hosts, view, xp=np)
    assert not cell.any() and not outside.any()
    assert not v3.host_node_conductance(np.ones(len(closed)), hosts, view, xp=np).any()


def scatter_reference(at_a, at_b, hosts, spec, p):
    """The node changes of host_scatter, entity by entity (a loop over the declared hosts)."""
    nodes = v3.node_ids(spec)
    declared = {h.index: h for h in v3.declared_hosts(spec).values()}
    out = np.zeros((at_a.shape[0], len(nodes)))
    for k, row in enumerate(hosts):
        host = declared[int(row)]
        out[:, nodes.index(host.end_a)] += at_a[:, k]
        out[:, nodes.index(host.end_b)] += at_b[:, k]
    n = len(p.active)
    return out[:, :n], out[:, n:]


def test_host_scatter_puts_each_entity_at_its_hosts_ends():
    spec = padded_sheet()
    _, _, p, _ = bound(spec)
    m = len(p.membrane_active)
    hosts = np.asarray([0, 3, m, m + 5, 3, m + 11])  # Patches and junctions, a host twice.
    rng = np.random.default_rng(7)
    at_a, at_b = rng.normal(size=(2, len(hosts))), rng.normal(size=(2, len(hosts)))
    cell, outside = v3.host_scatter(at_a, at_b, hosts, p, xp=np)
    want_cell, want_outside = scatter_reference(at_a, at_b, hosts, spec, p)
    rounding = 1e-14  # A node sums at most four O(1) values, in another order than the loop.
    assert np.allclose(cell, want_cell, rtol=0.0, atol=rounding)
    assert np.allclose(outside, want_outside, rtol=0.0, atol=rounding)
    flipped = v3.host_scatter(at_b, at_a, hosts, p, xp=np)  # Plant: the ends swapped.
    assert not np.allclose(flipped[0], want_cell, rtol=0.0, atol=rounding)
    f = rng.normal(size=(2, len(hosts)))  # A transfer from end a to end b conserves.
    cell, outside = v3.host_scatter(-f, f, hosts, p, xp=np)
    assert np.allclose(cell.sum(axis=1) + outside.sum(axis=1), 0.0, atol=1e-14)
    device = jax.jit(lambda a, b, h, q: v3.host_scatter(a, b, h, q))(
        jnp.asarray(at_a), jnp.asarray(at_b), jnp.asarray(hosts), jax.tree.map(jnp.asarray, p)
    )
    host_side = v3.host_scatter(at_a, at_b, hosts, p, xp=np)
    for got, want in zip(device, host_side, strict=True):
        assert np.allclose(np.asarray(got), want, rtol=0.0, atol=rounding)


def test_host_node_conductance_is_patch_node_conductance_on_patches():
    spec = padded_sheet()
    _, _, p, _ = bound(spec)
    m, n = len(p.membrane_active), len(p.active)
    slope = np.linspace(1e-12, 2e-12, m)
    patches = np.arange(m)
    assert np.array_equal(
        v3.host_node_conductance(slope, patches, p, xp=np),
        v3.patch_node_conductance(slope, p, xp=np),
    )
    junction = np.asarray([m])  # Both of a junction's ends are cells.
    nodes = v3.host_node_conductance(np.asarray([3e-12]), junction, p, xp=np)
    ends = [p.junction_sender[0], p.junction_receiver[0]]
    assert np.all(nodes[ends] == 3e-12) and nodes.sum() == 6e-12 and not nodes[n:].any()


def test_the_host_side_resolves_declared_hosts_and_refuses_others():
    spec = padded_sheet()
    m = spec.execution.membrane_capacity
    assert v3.host_index(spec, spec.model.membranes[2].id) == 2
    assert v3.host_index(spec, spec.model.junctions[4].id) == m + 4
    for unknown in ("nowhere", spec.model.cells[0].id, spec.model.extracellular[0].id):
        with pytest.raises(ConfigError, match="not a declared host"):
            v3.host_index(spec, unknown)
    assert v3.host_ids(spec)[len(spec.model.membranes)] is None  # A padded membrane slot.


def test_the_table_adds_no_layout_field_and_kind_rates_is_the_contracts():
    assert not any(name.startswith("host") for name in v3.LAYOUT_TYPE._fields)
    assert v3.KindRates is kind_registry.KindRates  # §18: the class is the kind contract's.
