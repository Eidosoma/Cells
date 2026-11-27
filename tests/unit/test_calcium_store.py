"""Calcium's channels and its store: the rows of docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md that hold
a world of their own (section 14). On the host, no compile.

- The material term of a channel law (row 4; section 5.3), against central differences of the
  stage's own fluxes, over voltages and openings. The store's side is a finite, face-free node (a
  channel on a compartment's own patch is refused). Two cells share it, each with a calcium
  population; one of them carries a second ion, one is routed through a source, one faces a held
  bath, and a leak without a term counts nowhere. Each ion's mode is at both of its ends and a held
  bath's is left out; the populations add per row and a node takes its largest row; the rate is no
  less than the fastest rate of calcium's own block. Planted, each caught: B(x) and B(-x) exchanged,
  the term at one end only, and the term absent at the store's node. A step above the bound is
  refused, and a law that declares no term adds nothing; a law that names another kernel is refused.
- A block that reads the ion's reversal potential joins its part of the slope, once, at the routed
  availability (planted: the part left out, the block's own term counted beside it). On a law with
  several ions and a material term it is refused by name, since its other ions' fluxes would have no
  such part (admitted: the membrane voltage as the reference, and a law without a term).
- A slot whose own gate reads an ion it moves closes a loop at each of its ions' rows, at both ends
  (section 6.5; planted: the flux of a held gate).

Seconds: about 1 on a busy CPU, parses and NumPy stages. The reason (D224): the rule's rows need a
node that two populations share, a held bath, two ions and a block in one world.
"""

import dataclasses

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import species_condition
from cells.laws.channels import cav1p2_m2h, kleak_always_open, open_channel_block
from cells.laws.reactions import hill_product_factor
from cells.models import surface_pump_v3 as tissue3
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

CALCIUM, TWO_IONS = cav1p2_m2h.LAW_ID, "tests.channel.two_ion_channel@1"
TERM = tissue3.CHANNEL_MATERIAL_TERM
STEP = 1e-3  # The differences' relative step: each flux is linear in its ion's own amounts.
OPENINGS = ((0.9, 0.95), (0.35, 0.6))
VOLTAGES = ((-0.11, -0.06), (-0.02, 0.05), (0.0, 0.0), (0.055, -0.1))  # Each cell's, the node at 0.


def two_ions(**changes):
    """A planted law with the calcium channel's kernels that carries K as well (code 99)."""
    planted = dataclasses.replace(
        cav1p2_m2h.LAW, law_id=TWO_IONS, code=99, permeant=(("Ca", 2, 0.8), ("K", 1, 1.0))
    )
    return dataclasses.replace(planted, **changes)


def with_laws(*laws):
    return law_registry.scope(law_registry.BUILTIN.extended(*laws))


def population(name, patch, law, permeability, **more):
    gates = [] if not law.gates else list(OPENINGS[0])
    ions = [dict(species_id=s, relative_permeability=r) for s, _, r in law.permeant]
    return dict(
        id=name, membrane_id=patch, kinetic_law=law.law_id, abundance=0.5, initial_gate=gates,
        max_permeability_m_per_s=permeability, permeant_ions=ions, **more,
    )  # fmt: skip


def condition(name, species, node, k_mM):
    read = dict(species=species, form="hill_activation", half_saturation_mM=k_mM,
                hill_coefficient=2.0)  # fmt: skip
    return dict(id=name, node=node, law=hill_product_factor.LAW_ID, reads=[read])


def store_side(channels, *, conditions=()):
    """Two cells and the finite, face-free node_0 between them, and the held bath, as a plain @3
    definition: calcium is scarce at both cells and the node (1e-4 and 1e-3 mM)."""
    raw = fx.world(
        cells=(("cell_0", 0.5), ("cell_1", 0.4)), nodes=(("node_0", 0.05),), faces=(),
        contacts=(("contact_0", "cell_0", "node_0"), ("contact_1", "cell_1", "node_0")),
        dt=1e-4, end=1e-3, concentrations_mM=dict(cell_0=2e-3),
    )  # fmt: skip
    inside = dict(cell_0=1e-4, cell_1=1.2e-4, node_0=1e-3, bath=2e-3)
    raw = rfx.with_charged_trace(raw, "Ca", 2, concentrations_mM=inside)
    m, e = raw["model"], raw["experiment"]
    m["id"] = tissue3.MODEL_ID
    m.pop("inner_model")
    m.pop("operators")
    for patch in m["membranes"]:
        patch["capacitance_F"] = 1e-11
        patch["permeability_m_per_s"]["K"] = 1e-9
    m["channels"] = channels
    e["channel_controls"] = [
        dict(channel_id=c["id"], schedule=[dict(time=0.0, availability=0.8)]) for c in channels
    ]
    raw["execution"]["channel_capacity"] = len(channels) + 1
    if conditions:
        m["species_conditions"] = list(conditions)
    return raw


def start(raw):
    """(spec, implementation, state, control, layout) of a definition's start, on the host."""
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    return spec, impl, state, impl.Control(*(v[0] for v in control_values(spec, [0.0]))), p


def scaled(state, p, rows, cells, nodes):
    """The state with the amounts of `rows` scaled by 1 + cells at the cells, 1 + nodes outside."""
    inner, outer = np.array(state.amount_increment), np.array(state.extracellular_amount_increment)
    inner[rows] += cells * p.amount_reference[rows]
    outer[rows] += nodes * p.extracellular_amount_reference[rows]
    return state._replace(amount_increment=inner, extracellular_amount_increment=outer)


def difference_slopes(impl, state, control, p, potentials, rows):
    """([species, channel] |dJ/dn| at each population's cell, the same at its outside node), 1/s, by
    central differences of the stage's own fluxes: every amount of `rows` moved at once, since a
    flux reads its own ion at its own two ends alone."""

    def flux(cells, nodes):
        moved = scaled(state, p, rows, cells, nodes)
        rates, _ = impl.explicit_rates(moved, potentials, control, p, xp=np)
        return np.asarray(rates.channel_transferred)

    cell, node = (f[p.channel_membranes] for f in (p.membrane_cell, p.membrane_outside))
    up = [flux(STEP, 0.0) - flux(-STEP, 0.0), flux(0.0, STEP) - flux(0.0, -STEP)]
    amounts = p.amount_reference[:, cell], p.extracellular_amount_reference[:, node]
    return tuple(np.abs(d) / (2 * STEP * n) for d, n in zip(up, amounts, strict=True))


def expected_nodes(slopes, p, counted):
    """The rule of section 8.2 from the slopes, in NumPy: each mode's own rate at both rows it
    moves, a held bath's part and row left out, summed per row; a node's rate its largest row."""
    to_cell, to_node = slopes
    n = p.active.size
    rows = np.zeros((to_cell.shape[0], n + p.outside_active.size))
    for j in counted:
        patch = p.channel_membranes[j]
        i, k = p.membrane_cell[patch], p.membrane_outside[patch]
        if p.reservoir[k]:
            rows[:, i] += to_cell[:, j]
        else:
            rows[:, i] += to_cell[:, j] + to_node[:, j]
            rows[:, n + k] += to_cell[:, j] + to_node[:, j]
    return rows.max(axis=0)


def fastest(impl, state, control, p, potentials, row):
    """The largest eigenvalue magnitude (1/s) of one species' block, by central differences of the
    stage's derivative: the two cells and the node."""
    n, places = p.active.size, (("cell", 0), ("cell", 1), ("node", 1))

    def derivative(where, sign):
        kind, index = where
        cells, nodes = np.zeros(n), np.zeros(p.outside_active.size)
        (cells if kind == "cell" else nodes)[index] = sign * STEP
        rates, _ = impl.explicit_rates(
            scaled(state, p, row, cells, nodes), potentials, control, p, xp=np
        )
        inner, outer = rates.amount_increment[row], rates.extracellular_amount_increment[row]
        return np.array([inner[0], inner[1], outer[1]])

    amounts = [p.amount_reference[row, 0], p.amount_reference[row, 1]]
    amounts.append(p.extracellular_amount_reference[row, 1])
    block = [
        (derivative(place, 1) - derivative(place, -1)) / (2 * STEP * amount)
        for place, amount in zip(places, amounts, strict=True)
    ]
    return np.abs(np.linalg.eigvals(np.array(block).T)).max()


def test_a_channel_s_material_term_is_its_mode_s_rate_at_both_ends(monkeypatch):
    channels = [
        population("ca_0", "contact_0", cav1p2_m2h.LAW, 3e-7, factors=["gate"]),
        population("ca_1", "contact_1", two_ions(), 4e-7),
        population("wall", "wall_cell_0", cav1p2_m2h.LAW, 1e-9),
        population("leak", "contact_0", kleak_always_open.LAW, 3e-6),  # It declares no term.
    ]
    gate = condition("gate", fx.SPECIES, "cell_0", 3e-3)  # A row that nothing moves: no loop.
    honest = tissue3.material_law.material_slope_per_s
    plants = {
        "B(x) and B(-x) exchanged": lambda v, *a, **k: honest(-v, *a, **k),
        "the term at one end only": lambda *a, **k: (honest(*a, **k)[0], 0.0 * honest(*a, **k)[1]),
    }
    whole = tissue3.channel_material_rates

    def absent(state, read, potentials, control, p, **more):  # Planted: none at the store's node.
        nodes = np.array(whole(state, read, potentials, control, p, **more))
        nodes[p.active.size :] = 0.0
        return nodes

    with with_laws(two_ions()):
        spec, impl, state, control, p = start(store_side(channels, conditions=[gate]))
        species = list(spec.model.species_ids)
        moved, ca = [species.index("Ca"), species.index("K")], species.index("Ca")
        assert impl.structure.loops == () and p.reservoir.tolist() == [True, False]
        assert [c.id for c in spec.model.extracellular] == ["bath", "node_0"]
        n, missed = p.active.size, {**dict.fromkeys(plants, 0), "absent": 0}
        dominant = set()
        for opening in OPENINGS:
            gates = np.where(p.channel_gate_active, np.array(opening)[:, None], 0.0)
            state = state._replace(channel_gate=gates)
            for voltages in VOLTAGES:
                potentials = np.array([*voltages, 0.0, 0.0])
                slopes = difference_slopes(impl, state, control, p, potentials, moved)
                expected = expected_nodes(slopes, p, (0, 1, 2))
                routed, _ = tissue3._route(
                    impl.structure, tissue3._kinds(impl.structure), state, control, p, xp=np
                )
                assert 0.2 < routed.channel[0] / control.channel[0] < 0.8  # The source's factor.
                found = tissue3.channel_material_rates(
                    state, state, potentials, routed, p, xp=np, structure=impl.structure
                )
                assert found == pytest.approx(expected, rel=1e-9, abs=0)
                assert found[n] == 0.0 < found[n + 1]  # The bath's row and the node's.
                modes = (slopes[0] + slopes[1])[moved, 1]  # The second population's two ions.
                dominant.add(int(np.argmax(modes)))
                rate = impl.material_rate(state, control, p, xp=np, potentials=potentials)
                assert rate == pytest.approx(expected.max(), rel=1e-9, abs=0)
                block = fastest(impl, state, control, p, potentials, ca)
                assert rate >= block * (1 - 1e-9)
                for name, planted in plants.items():
                    with monkeypatch.context() as plant:
                        plant.setattr(tissue3.material_law, "material_slope_per_s", planted)
                        wrong = tissue3.channel_material_rates(
                            state, state, potentials, routed, p, xp=np, structure=impl.structure
                        )
                    missed[name] += wrong != pytest.approx(expected, rel=1e-6, abs=0)
                with monkeypatch.context() as plant:
                    plant.setattr(tissue3, "channel_material_rates", absent)
                    wrong = impl.material_rate(state, control, p, xp=np, potentials=potentials)
                missed["absent"] += wrong < block
        assert dominant == {0, 1}  # Each ion is the largest row somewhere.
        # Every plant is caught wherever it shows: the exchange not at 0 V, and the node's own row
        # wherever calcium's block is faster than any cell's row.
        assert missed["B(x) and B(-x) exchanged"] == 6
        assert missed["the term at one end only"] == 8
        assert missed["absent"] >= 4


def test_a_step_above_the_channel_s_material_bound_is_refused():
    """The rule is the step's: at 1.1 times the bound the step is refused and at 0.9 admitted, where
    the charge rule admits both; the same law without its term on K, the ion that needs none, has no
    material rate, and one that names a kernel that @3 does not run is refused by name."""
    channels = [population("ca_0", "contact_0", cav1p2_m2h.LAW, 2e-4)]
    _, impl, state, control, p = start(store_side(channels))
    potentials = impl.readouts(state, control, p, xp=np).field.potential_V
    rate = float(impl.material_rate(state, control, p, xp=np, potentials=potentials))
    charge = float(impl.membrane_rate(state, control, p, xp=np, potentials=potentials))
    assert charge < 0.5 * rate
    for factor, admitted in ((0.9, True), (1.1, False)):
        assert bool(impl.imex_step(state, factor / rate, control, p, xp=np)[1]) is admitted
    blind = impl.material_rate(state, control, p, xp=np, potentials=None)
    assert blind == np.inf  # Without potentials it fails closed.
    for term, words in ((None, None), ("another_kernel", "names the material term another_kernel")):
        law = two_ions(permeant=(("K", 1, 1.0),), material_term=term)
        with with_laws(law):
            raw = store_side([population("k_0", "contact_0", law, 2e-7)])
            if words is not None:
                with pytest.raises(ConfigError, match=words):
                    parse_spec(raw)
                continue
            _, impl, state, control, p = start(raw)
            assert impl.material_rate(state, control, p, xp=np, potentials=potentials) is None


def block_of():
    """An outside block of valence 2 in one mode."""
    return dict(
        law=open_channel_block.LAW_ID,
        blocker=dict(id="blocker", valence=2, side="outside", concentration_mM=2.0),
        modes=[dict(weight=1.0, k0_mM=1.0, electrical_distance=0.8)],
    )


def on_reversal(ion):
    """The population's keys for its block read on ion's reversal (FR-64's voltage_shift), or none
    for the patch voltage, the default."""
    return {} if ion is None else dict(voltage_shift=dict(block=dict(reversal_of=ion)))


def on_ph():
    """The population's keys for its block read on the cell's pH (FR-64's voltage_shift)."""
    ph = dict(side="inside", shift_V_per_ph=-0.1, reference_ph=7.3, ph_window=[6.8, 7.5])
    return dict(voltage_shift=dict(block=dict(ph=ph)))


def proton_slopes(impl, state, control, p, potentials, row):
    """[species, channel] |dJ/dn_H| at each population's cell (1/s), by central differences of the
    stage's own fluxes in the amount of the proton row `row` there (FR-64's block on its pH)."""

    def flux(cells):
        moved = scaled(state, p, [row], cells, 0.0)
        rates, _ = impl.explicit_rates(moved, potentials, control, p, xp=np)
        return np.asarray(rates.channel_transferred)

    cell = p.membrane_cell[p.channel_membranes]
    return np.abs(flux(STEP) - flux(-STEP)) / (2 * STEP * p.amount_reference[row, cell])


@pytest.mark.parametrize("reader", ["the Ca reversal", "the cell's pH"])
def test_a_block_that_reads_a_shift_joins_its_part_once(reader, monkeypatch):
    """A calcium population whose block reads V - E_Ca, at a voltage above E_Ca: the flux is outward
    there, so the direct part of each slope and the part through the reversal have one sign and
    |dJ/dn| is their sum. FR-64: where its block reads the cell's pH instead (an H trace at pH 7.2,
    no kinds), the cell's row also takes the flux's slope in the proton amount there, |dJ_Ca/dn_H|
    (channel_block_terms' proton_slope), which its central difference gives. Each part, planted
    away, lowers the rate."""
    reversal = reader == "the Ca reversal"
    own = population(
        "ca_0", "contact_0", cav1p2_m2h.LAW, 3e-7, block=block_of(), factors=["gate"],
        **(on_reversal("Ca") if reversal else on_ph()),
    )  # fmt: skip
    gate = condition("gate", fx.SPECIES, "cell_0", 3e-3)
    raw = store_side([own], conditions=[gate])
    if not reversal:
        h, out = 10**-7.2 * 1e3, 10**-7.4 * 1e3
        traced = dict(cell_0=h, cell_1=h, node_0=out, bath=out)
        raw = rfx.with_charged_trace(raw, "H", 1, concentrations_mM=traced)
    spec, impl, state, control, p = start(raw)
    ids = list(spec.model.species_ids)
    ca = ids.index("Ca")
    potentials = np.array([0.058, 0.0, 0.0, 0.0])
    to_cell, to_node = difference_slopes(impl, state, control, p, potentials, [ca])
    if not reversal:
        to_cell = to_cell + proton_slopes(impl, state, control, p, potentials, ids.index("H"))
    expected = expected_nodes((to_cell, to_node), p, [0])
    kinds, given = tissue3._kinds(impl.structure), dict(xp=np, structure=impl.structure)
    routed, _ = tissue3._route(impl.structure, kinds, state, control, p, xp=np)
    found = tissue3.channel_material_rates(state, state, potentials, routed, p, **given)
    assert found == pytest.approx(expected, rel=1e-5, abs=0)
    rate = impl.material_rate(state, control, p, xp=np, potentials=potentials)
    assert rate == pytest.approx(expected.max(), rel=1e-5, abs=0)
    with monkeypatch.context() as plant:  # Planted: the part through E or through the pH left out.
        terms = tissue3.channel_block_terms

        def dropped(*args, **kwargs):
            out = terms(*args, **kwargs)
            if reversal:
                return out._replace(inside_through_e=np.zeros(2), outside_through_e=np.zeros(2))
            return out._replace(proton_slope=np.zeros_like(out.proton_slope))

        plant.setattr(tissue3, "channel_block_terms", dropped)
        wrong = impl.material_rate(state, control, p, xp=np, potentials=potentials)
        assert wrong < 0.9 * expected.max()
    with monkeypatch.context() as plant:  # Planted: the block's own term counted beside it.
        plant.setattr(tissue3, "material_term_slots", lambda p, structure, *, xp: xp.zeros(2, bool))
        beside = tissue3.block_material_rates(state, p, potentials, control=routed, **given)
        assert (found + beside)[0] > (1.5 if reversal else 1.2) * expected[0]  # The pH's: 1.24.


MAJORS = (("K", 1, 1.0), ("Na", 1, 0.1))  # Two ions that need no material term.


@pytest.mark.parametrize(
    "law, reversal, refused",
    [
        (two_ions(), "Ca", "Ca"),
        (two_ions(permeant=MAJORS), "K", "K"),
        (two_ions(), None, None),
        (two_ions(permeant=MAJORS, material_term=None), "K", None),
    ],
    ids=("a scarce ion", "two major ions", "the membrane voltage", "a law without a term"),
)
def test_a_reversal_block_on_several_ions_and_a_term_is_refused_by_name(law, reversal, refused):
    """The rule's part through the reversal is the named ion's own flux's, so the law's other ions'
    would have no bound: the definition is refused, with the law, its ions and the block's. The
    reversal is the population's voltage_shift.block since FR-64."""
    with with_laws(law):
        blocked = population(
            "ca_0", "contact_0", law, 3e-7, block=block_of(), **on_reversal(reversal)
        )
        raw = store_side([blocked])
        if refused is None:
            assert parse_spec(raw).model.channels[0].block is not None
            return
        ions = ", ".join(species for species, _, _ in law.permeant)
        match = f"block: {law.law_id} carries {ions} and declares a material term, and the block "
        with pytest.raises(ConfigError, match=match + f"reads the reversal of {refused}: "):
            parse_spec(raw)


@pytest.mark.parametrize("law", (cav1p2_m2h.LAW, two_ions()), ids=("calcium", "two ions"))
def test_a_channel_slot_s_loop_adds_at_every_row_it_moves(law):
    """A population gated by its own cell's calcium: each ion's flux holds the factor, so each ion's
    row closes a loop, at both ends. The expected rate is |J| / f x |df/dn|, df/dn a central
    difference of the source's factor alone; the two ions' law takes its largest row, K's."""
    channels = [population("ca_1", "contact_1", law, 4e-7, factors=["gate"])]
    gate = condition("gate", "Ca", "cell_1", 1.5e-4)
    with with_laws(*([law] if law.law_id == TWO_IONS else [])):
        spec, impl, state, control, p = start(store_side(channels, conditions=[gate]))
        ions, pair = [s for s, *_ in law.permeant], (species_condition.KIND_ID, 0)
        assert impl.structure.loops == tuple(((0, row), pair) for row in range(len(ions)))
        rows, n = [list(spec.model.species_ids).index(s) for s in ions], p.active.size
        assert p.loop_flux_row.tolist() == rows and p.loop_pair_row.tolist() == rows[:1]
        potentials = np.array([0.0, -0.07, 0.0, 0.0])
        rates, _ = impl.explicit_rates(state, potentials, control, p, xp=np)
        flux = np.abs(rates.channel_transferred[rows, 0])
        assert flux.argmax() == len(ions) - 1
        up, down = (
            species_condition.factors(scaled(state, p, rows[0], h, 0.0), p, xp=np)[0]
            for h in (STEP, -STEP)
        )
        factor = species_condition.factors(state, p, xp=np)[0]
        slope = (up - down) / (2 * STEP * p.amount_reference[rows[0], 1])
        expected = np.zeros(n + p.outside_active.size)
        expected[[1, n + 1]] = flux.max() / factor * slope
        kinds = tissue3._kinds(impl.structure)
        routed, _ = tissue3._route(impl.structure, kinds, state, control, p, xp=np)

        def loops(gates):
            return tissue3.loop_material_rates(
                state, state, potentials, gates, p, xp=np, structure=impl.structure, kinds=kinds
            )

        assert loops(routed) == pytest.approx(expected, rel=1e-6, abs=0)
        assert loops(control)[1] > 1.5 * expected[1]  # Planted: the held gate, without the factor.
