"""The split-and-merge kernel: membrane moved between patches, the charges following the patches.

pump_composite_adapter.charge_following_transfer (docs/MEMBRANE_RETRIEVAL_DESIGN.md §2.2, R2;
docs/CORE_SEAMS_DESIGN.md §4.6's merge; D217: B1's first slice, FR-2's retrieval and recycling and
door F's first kernel). Host-side, in NumPy, against an independent dense capacitor solve written
here from the patches (no adapter field arrays), each check beside a planted error it catches:
* the closed forms: into a free face-free node j bounded by one patch b, from a patch k of b's
  cell, only phi_j moves, V_b' = (C_b V_b + dc V_k)/(C_b + dc), and the heat is C_b dc (V_b -
  V_k)^2 / (2 (C_b + dc)). Planted: R1, the membrane leaving uncharged (insertion's rule run
  backwards), moves the cell's potential too;
* the energy ledger: the heat equals the clamps' and reservoirs' work less the capacitor energy's
  change, against the dense reference, for retrieval from a held bath and from a free node, for
  recycling into a held bath's patch (the potentials re-solved in general) and for two transfers
  at once. Planted: the merge heat without its C_b / (C_b + dc) factor;
* charge: each piece is neutral and its four plate-charge moves cancel exactly, a same-cell
  transfer leaves the cell's charge bitwise, and where each node meets one transfer the network's
  free charge change equals the reservoirs' supply exactly; at a held bath that loses a piece the
  clamp's transfer and the reservoir's supply cancel. Planted: a piece whose outside plate takes
  its own rounding;
* the carriers: check_carriers refuses a neutral carrier and transference numbers that do not sum
  to 1, and the carriers' amounts carry the moved charge;
* a piece at its target's voltage (two patches of one cell on one node) dissipates exactly nothing;
  one a node apart does. The kernel under jax.jit matches NumPy.
"""

from fractions import Fraction

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.models import pump_composite_adapter as adapter
from cells.registry.models import get_model
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx


def layout(raw):
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    return spec, adapter.inner_state(state), adapter.inner_layout(p)


def patch(spec, name):
    return [m.id for m in spec.model.membranes].index(name)


def node(spec, name):
    nodes = [c.id for c in spec.model.cells] + [c.id for c in spec.model.extracellular]
    return nodes.index(name)


def charged(q, **charges):
    """q with node charges (C) set by node slot, cells then outside nodes."""
    n = q.active.size
    cells, outside = np.array(q.initial_cell_charge_C), np.array(q.initial_outside_charge_C)
    for slot, value in charges.items():
        k = int(slot[1:])
        (cells if k < n else outside)[k if k < n else k - n] = value
    return q._replace(initial_cell_charge_C=cells, initial_outside_charge_C=outside)


# ------------------------------------------------------------------ the independent reference


def dense(q, capacitance, charge):
    """(K, phi, held): the capacitor network from its patches, written here, its free potentials
    solved from the free charges with the held and inactive nodes at their potentials."""
    n, o = q.active.size, q.outside_active.size
    matrix = np.zeros((n + o, n + o))
    for m, c in enumerate(capacitance):
        if q.membrane_active[m]:
            e = np.zeros(n + o)
            e[q.membrane_cell[m]], e[n + q.membrane_outside[m]] = 1.0, -1.0
            matrix += c * np.outer(e, e)
    held = np.concatenate((~np.asarray(q.active), np.asarray(q.reservoir) | ~q.outside_active))
    phi = np.concatenate((np.zeros(n), np.asarray(q.boundary_V)))
    free = ~held
    rhs = charge[free] - matrix[np.ix_(free, held)] @ phi[held]
    phi[free] = np.linalg.solve(matrix[np.ix_(free, free)], rhs)
    return matrix, phi, held


def reference(q, state, source, target, dc):
    """R2 from first principles: each piece takes both plate charges at its source's voltage; the
    potentials re-solved; the heat from the energy ledger, W - (U' - U)."""
    n = q.active.size
    charge = np.concatenate((q.initial_cell_charge_C, q.initial_outside_charge_C))
    charge = charge + CHARGE_PER_FMOL * np.concatenate(
        (
            np.sum(q.valence * state.amount_increment, axis=0),
            np.sum(q.valence * state.extracellular_amount_increment, axis=0),
        )
    )
    c0 = np.asarray(q.membrane_capacitance, dtype=float)
    matrix, phi, held = dense(q, c0, charge)
    cells, outside = np.asarray(q.membrane_cell), n + np.asarray(q.membrane_outside)
    v = np.where(q.membrane_active, phi[cells] - phi[outside], 0.0)
    plate = dc * v[source]
    c1 = c0.copy()
    np.add.at(c1, source, -dc)
    np.add.at(c1, target, dc)
    moved = np.zeros(phi.size)
    np.add.at(moved, cells[target], plate)
    np.add.at(moved, cells[source], -plate)
    np.add.at(moved, outside[target], -plate)
    np.add.at(moved, outside[source], plate)
    matrix1, phi1, _ = dense(q, c1, charge + np.where(held, 0.0, moved))
    v1 = np.where(q.membrane_active, phi1[cells] - phi1[outside], 0.0)
    electrode = np.where(held, matrix1 @ phi1 - matrix @ phi, 0.0)
    supplied = np.where(held, -moved, 0.0)
    work = np.sum(phi * (electrode + supplied))
    energy = 0.5 * np.sum(c1 * v1**2) - 0.5 * np.sum(c0 * v**2)
    return dict(
        phi=phi, phi1=phi1, v=v, v1=v1, electrode=electrode[n:], heat=1e12 * (work - energy)
    )


def transfer(q, state, source, target, dc):
    return adapter.charge_following_transfer(
        state, q, np.asarray(source), np.asarray(target), np.asarray(dc, dtype=float), q, xp=np
    )


# ------------------------------------------------------------------ the worlds


@pytest.fixture(scope="module")
def held_bath():
    """FR-1's silence world W: the owner cell_0 on a held bath through its wall, charged here to
    -60 mV, and the neutral compartment ecs_0 bounded by contact_0 (V_b = 0). Retrieval: wall ->
    contact_0."""
    spec, state, q = layout(cfx.loaded_compartment(end=0.004))
    wall = patch(spec, "wall_cell_0")
    q = charged(q, n0=-0.06 * float(q.membrane_capacitance[wall]))
    return spec, state, q, wall, patch(spec, "contact_0")


@pytest.fixture(scope="module")
def free_node():
    """cell_0 with a wall to the bath, contact_0 to the finite node ecs_0 and contact_1 to the
    face-free node ecs_1; charges set so that every patch voltage differs. Retrieval: contact_0 ->
    contact_1, from a free node."""
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0), ("ecs_1", 0.5)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_0", "ecs_1")),
        faces=(),
        end=0.004,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    spec, state, q = layout(raw)
    q = charged(q, n0=-4e-13, n2=1.5e-13, n3=-0.5e-13)
    return spec, state, q, patch(spec, "contact_0"), patch(spec, "contact_1")


def closed_form(q, state, k, b, dc):
    """V_b' and the heat of a retrieval k -> b into a free face-free node bounded by b alone."""
    r = reference(q, state, [k], [b], np.array([dc]))
    vk, vb, cb = r["v"][k], r["v"][b], float(q.membrane_capacitance[b])
    return (cb * vb + dc * vk) / (cb + dc), 1e12 * cb * dc * (vb - vk) ** 2 / (2 * (cb + dc))


# ------------------------------------------------------------------ the closed forms


@pytest.mark.parametrize("world", ["held_bath", "free_node"])
def test_only_the_compartments_potential_moves_into_its_closed_form(world, request):
    spec, state, q, k, b = request.getfixturevalue(world)
    dc = 0.1 * float(q.membrane_capacitance[k])
    out = transfer(q, state, [k], [b], [dc])
    r = reference(q, state, [k], [b], np.array([dc]))
    j = q.active.size + int(q.membrane_outside[b])
    moved = np.abs(r["phi1"] - r["phi"]) > 1e-15
    assert moved.tolist() == [i == j for i in range(moved.size)]
    vb, heat = closed_form(q, state, k, b, dc)
    assert out.after_V[b] == pytest.approx(vb, rel=1e-12)
    assert out.heat_pJ == pytest.approx(heat, rel=1e-9) and out.heat_pJ > 0
    assert out.after_V[k] == pytest.approx(out.before_V[k], rel=1e-12)  # The source keeps V_k.
    # Planted: R1, the retrieved membrane leaving uncharged (fixed free charges), moves more than
    # phi_j: the owner's potential where k faces the held bath, the source's node where it is free.
    c1 = np.array(q.membrane_capacitance, dtype=float)
    c1[k] -= dc
    c1[b] += dc
    _, phi_r1, _ = dense(
        q, c1, np.concatenate((q.initial_cell_charge_C, q.initial_outside_charge_C))
    )
    moved_r1 = np.abs(phi_r1 - r["phi"]) > 1e-15
    assert moved_r1.tolist() != [i == j for i in range(moved_r1.size)]


def test_a_piece_at_its_targets_voltage_dissipates_exactly_nothing():
    """Two patches of one cell facing one node share a voltage exactly, so moving membrane between
    them dissipates exactly nothing and moves no potential; the planted twin, a node apart, does."""
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0), ("ecs_1", 0.5)),
        contacts=(
            ("contact_0", "cell_0", "ecs_0"),
            ("contact_1", "cell_0", "ecs_0"),
            ("contact_2", "cell_0", "ecs_1"),
        ),
        faces=(),
        end=0.004,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    spec, state, q = layout(raw)
    q = charged(q, n0=-4e-13, n2=1.5e-13)
    k, b, apart = (patch(spec, f"contact_{i}") for i in range(3))
    dc = 0.1 * float(q.membrane_capacitance[k])
    out = transfer(q, state, [k], [b], [dc])
    assert out.before_V[k] == out.before_V[b] and out.before_V[k] != 0.0
    assert out.heat_pJ == 0.0 and not np.any(out.charge_C) and not np.any(out.supplied_C)
    assert out.before_V[apart] != out.before_V[k]
    assert transfer(q, state, [k], [apart], [dc]).heat_pJ > 0.0


# ------------------------------------------------------------------ the energy ledger


def two_cells():
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 0.5)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(),
        end=0.004,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    spec, state, q = layout(raw)
    return spec, state, charged(q, n0=-3e-13, n1=-5e-13, n3=0.7e-13, n4=-0.2e-13)


def cases():
    yield "retrieval from a held bath", "held_bath", None
    yield "retrieval from a free node", "free_node", None
    yield "recycling into a held bath's patch", "held_bath", "reverse"
    yield "two transfers at once", "two_cells", None
    yield "a transfer between two cells", "two_cells", "across"


@pytest.mark.parametrize("name, world, direction", list(cases()), ids=[c[0] for c in cases()])
def test_the_heat_closes_the_energy_ledger_against_the_dense_reference(
    name, world, direction, request
):
    if world == "two_cells" and direction == "across":  # The inside plate moves between cells.
        spec, state, q = two_cells()
        source, target = [patch(spec, "contact_0")], [patch(spec, "contact_1")]
    elif world == "two_cells":
        spec, state, q = two_cells()
        source = [patch(spec, "wall_cell_0"), patch(spec, "contact_1")]
        target = [patch(spec, "contact_0"), patch(spec, "wall_cell_1")]
    else:
        spec, state, q, k, b = request.getfixturevalue(world)
        source, target = ([b], [k]) if direction == "reverse" else ([k], [b])
    dc = np.array([0.1 * float(q.membrane_capacitance[s]) for s in source])
    out = transfer(q, state, source, target, dc)
    r = reference(q, state, source, target, dc)
    scale = 1e12 * 0.5 * np.sum(np.asarray(q.membrane_capacitance) * r["v"] ** 2)
    assert out.heat_pJ == pytest.approx(r["heat"], rel=1e-9, abs=1e-12 * scale)
    assert out.heat_pJ >= 0
    np.testing.assert_allclose(out.after_V, r["v1"], rtol=1e-11, atol=1e-15)
    np.testing.assert_allclose(out.electrode_C, r["electrode"], rtol=1e-9, atol=1e-24)
    # Planted: the merge loss without its C_b / (C_b + dc) factor breaks the ledger.
    naive = 0.5e12 * np.sum(dc * (out.before_V[source] - out.before_V[target]) ** 2)
    assert abs(naive - r["heat"]) > 1e-6 * abs(r["heat"])


# ------------------------------------------------------------------ charge


@pytest.mark.parametrize("world", ["held_bath", "free_node"])
def neutral(charge_C, supplied_C, q, k, b, plate):
    """Whether the transfer k -> b of one cell moved a neutral piece, exactly: the shared cell's
    charge unchanged bitwise, the target's outside node (or its reservoir) given -plate and the
    source's +plate, the same rounded number."""
    n = q.active.size
    u, w = int(q.membrane_outside[k]), int(q.membrane_outside[b])

    def given(node):  # The charge the piece's move gives node (a free one, or a held one's supply).
        return charge_C[n + node] if not q.reservoir[node] else -supplied_C[node]

    return (
        charge_C[int(q.membrane_cell[k])] == 0.0
        and Fraction(float(given(w))) == -Fraction(float(plate))
        and Fraction(float(given(u))) == Fraction(float(plate))
    )


@pytest.mark.parametrize("world", ["held_bath", "free_node"])
def test_charge_is_conserved_exactly(world, request):
    spec, state, q, k, b = request.getfixturevalue(world)
    n = q.active.size
    dc = 0.1 * float(q.membrane_capacitance[k])
    out = transfer(q, state, [k], [b], [dc])
    plate = out.plate_C[0]
    assert plate == dc * out.before_V[k] and plate != 0.0
    assert neutral(out.charge_C, out.supplied_C, q, k, b, plate)
    # Each node meets one transfer here, so the free charge change equals the supply exactly.
    free = sum(Fraction(float(x)) for x in out.charge_C)
    assert free == sum(Fraction(float(x)) for x in out.supplied_C)
    if bool(q.reservoir[int(q.membrane_outside[k])]):  # The held bath loses the piece: the clamp's
        o = int(q.membrane_outside[k])  # transfer and the reservoir's supply cancel.
        assert out.electrode_C[o] + out.supplied_C[o] == pytest.approx(0.0, abs=1e-12 * abs(plate))
    # Planted: a piece whose outside plate takes the target's voltage, -dc V_b, is not neutral.
    wrong_charge, wrong_supply = np.array(out.charge_C), np.array(out.supplied_C)
    outside = -dc * float(out.before_V[b])
    w = int(q.membrane_outside[b])
    if q.reservoir[w]:
        wrong_supply[w] = -outside
    else:
        wrong_charge[n + w] = outside
    assert not neutral(wrong_charge, wrong_supply, q, k, b, plate)


def test_a_view_that_returns_to_the_declared_capacitances_refreshes_from_them(held_bath):
    """The incoming view need not be the declared layout: FR-2 passes membrane state's view. A
    retrieval from the declared layout, then the same capacitance recycled from the view it gave,
    lands every capacitance back on the declared one bitwise; the second transfer's potentials must
    then be the declared layout's field, not the first view's (refresh_field keeps its first
    argument's arrays where nothing differs from the bound layout)."""
    spec, state, q, k, b = held_bath
    ck, cb = float(q.membrane_capacitance[k]), float(q.membrane_capacitance[b])
    dc = next(  # A capacitance whose round trip returns both patches bitwise.
        x for x in (ck * 2.0**-n for n in range(2, 20)) if (ck - x) + x == ck and (cb + x) - x == cb
    )
    first = transfer(q, state, [k], [b], [dc])
    moved = first.view._replace(  # The first view with the charges it moved, as FR-2 books them.
        initial_cell_charge_C=first.view.initial_cell_charge_C + first.charge_C[: q.active.size],
        initial_outside_charge_C=first.view.initial_outside_charge_C
        + first.charge_C[q.active.size :],
    )
    second = adapter.charge_following_transfer(
        state, moved, np.asarray([b]), np.asarray([k]), np.asarray([dc]), q, xp=np
    )
    assert (
        np.asarray(second.view.membrane_capacitance).tobytes()
        == np.asarray(q.membrane_capacitance).tobytes()
    )
    r = reference(moved, state, [b], [k], np.array([dc]))
    np.testing.assert_allclose(second.after_V, r["v1"], rtol=1e-11, atol=1e-15)
    np.testing.assert_allclose(second.electrode_C, r["electrode"], rtol=1e-9, atol=1e-24)
    assert second.heat_pJ == pytest.approx(r["heat"], rel=1e-9, abs=1e-15)
    for name in adapter.DERIVED_FIELD_ARRAYS:
        if hasattr(q, name):
            assert (
                np.asarray(getattr(second.view, name)).tobytes()
                == np.asarray(getattr(q, name)).tobytes()
            ), name


def test_the_kernel_under_jit_matches_numpy(free_node):
    import jax
    import jax.numpy as jnp

    jax.config.update("jax_enable_x64", True)
    spec, state, q, k, b = free_node
    dc = 0.1 * float(q.membrane_capacitance[k])
    host = transfer(q, state, [k], [b], [dc])
    jq, jstate = jax.tree.map(jnp.asarray, (q, state))

    @jax.jit
    def device(state, q):
        return adapter.charge_following_transfer(
            state, q, jnp.asarray([k]), jnp.asarray([b]), jnp.asarray([dc]), q, xp=jnp
        )

    out = device(jstate, jq)
    for name in ("charge_C", "supplied_C", "after_V", "electrode_C"):
        np.testing.assert_allclose(
            np.asarray(getattr(out, name)), getattr(host, name), rtol=1e-12, atol=1e-27
        )
    assert float(out.heat_pJ) == pytest.approx(float(host.heat_pJ), rel=1e-10)


# ------------------------------------------------------------------ the carriers


def test_the_carriers_are_checked_and_carry_the_moved_charge(held_bath):
    spec, state, q, k, b = held_bath
    valence = (
        [s.valence for s in spec.model.species]
        if hasattr(spec.model, "species")
        else list(spec.model.valence)
    )
    rows = {s: i for i, s in enumerate(spec.model.species_ids)}
    adapter.check_carriers((rows["K"], rows["Cl"]), (0.6, 0.4), valence, "test")
    with pytest.raises(ConfigError, match="row 3 is neutral"):
        adapter.check_carriers((rows["K"], rows["S"]), (0.5, 0.5), valence, "test")
    with pytest.raises(ConfigError, match="sum to 1"):
        adapter.check_carriers((rows["K"], rows["Cl"]), (0.6, 0.5), valence, "test")
    with pytest.raises(ConfigError, match="distinct species rows"):
        adapter.check_carriers((rows["K"], rows["K"]), (0.5, 0.5), valence, "test")
    out = transfer(q, state, [k], [b], [0.1 * float(q.membrane_capacitance[k])])
    scale = adapter.carrier_scale((rows["K"], rows["Cl"]), (0.6, 0.4), valence, len(rows))
    amounts = adapter.carrier_amounts(out.charge_C, scale, xp=np)
    carried = CHARGE_PER_FMOL * np.sum(np.asarray(valence)[:, None] * amounts, axis=0)
    np.testing.assert_allclose(carried, out.charge_C, rtol=1e-14, atol=1e-30)
    assert not amounts[rows["S"]].any() and not amounts[rows["Na"]].any()
