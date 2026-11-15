"""transporter@1: parse, refusals and hooks, tested alone with stand-ins for the core's calls."""

import jax
import numpy as np
import pytest

from cells.models.inner_kinds import transporter as tk
from cells.processes import atp_transporter as neutral
from cells.processes import proton_pump as proton

jax.config.update("jax_enable_x64", True)
PATCHES = {"bounding_0": ("cell_0", "lumen_0"), "store_0": ("cell_0", "store")}
VALENCE = {"H": 1, "Y": 0, "ATP": 0, "ADP": 0, "Pi": 0, "K": 1}
REGISTRY = {r: {"standard_mu_RT": 0.0} for r in ("ATP", "ADP", "Pi")}


def pump(**over):
    raw = dict(
        id="pump_0",
        patch="bounding_0",
        law=proton.LAW_ID,
        capacity_fmol_s=8.3027e-3,
        stoichiometry=2,
        km_role_mM=1e-4,
        km_atp_mM=0.1,
        role="H",
        fuel=dict(kind="held", node="cell_0", rows=["ATP", "ADP", "Pi"], ph_ref=7.2, ph_band=0.05),
    )
    raw.update(over)
    return raw


def neutral_pump(**over):
    raw = dict(
        id="pump_1",
        patch="store_0",
        law=neutral.LAW_ID,
        capacity_fmol_s=0.1,
        stoichiometry=1,
        km_role_mM=1.0,
        km_atp_mM=0.1,
        role="Y",
        fuel=dict(
            kind="finite", node="cell_0", rows=["ATP", "ADP", "Pi"], ph_ref=None, ph_band=None
        ),
    )
    raw.update(over)
    return raw


def test_parse_round_trips_and_gives_a_value_free_structure_entry():
    ts = tk.parse([pump(), neutral_pump()], PATCHES, VALENCE, REGISTRY)
    assert [tk.to_dict(t) for t in ts] == [pump(), neutral_pump()]
    assert tk.structure_entry(ts) == (
        tk.KIND_ID,
        tuple(sorted([proton.LAW_ID, neutral.LAW_ID])),
        ("finite", "held"),
    )
    assert tk.parse([], PATCHES, VALENCE, REGISTRY) == ()  # undeclared: absent


@pytest.mark.parametrize(
    "over,reason",
    [
        (dict(role="Y"), r"valence \+1"),
        (
            dict(
                fuel=dict(
                    kind="finite",
                    node="cell_0",
                    rows=["ATP", "ADP", "Pi"],
                    ph_ref=7.2,
                    ph_band=0.05,
                )
            ),
            "held fuel",
        ),
        (dict(stoichiometry=5), "integer 1..4"),
        (dict(patch="nowhere"), "unknown patch"),
        (dict(law="other@1"), "law must be"),
    ],
)
def test_proton_pump_refusals(over, reason):
    with pytest.raises(tk.TransporterError, match=reason):
        tk.parse([pump(**over)], PATCHES, VALENCE, REGISTRY)


def test_neutral_refusals_and_the_proton_boundary():
    with pytest.raises(tk.TransporterError, match="valence-0"):
        tk.parse([neutral_pump(role="K")], PATCHES, VALENCE, REGISTRY)
    with pytest.raises(tk.TransporterError, match="dynamic proton row"):
        tk.parse([neutral_pump()], PATCHES, VALENCE, REGISTRY, dynamic_proton_nodes={"cell_0"})
    with pytest.raises(tk.TransporterError, match="registry potential"):
        tk.parse([neutral_pump()], PATCHES, VALENCE, {"ATP": {}, "ADP": {}, "Pi": {}})


def test_moved_rows_are_species_node_pairs_and_held_fuel_is_not_moved():
    ts = tk.parse([pump(), neutral_pump()], PATCHES, VALENCE, REGISTRY)
    pairs = tk.moved_rows(ts)
    assert ("H", "cell_0") in pairs and ("H", "lumen_0") in pairs
    assert ("Y", "store") in pairs and ("ATP", "cell_0") in pairs  # finite fuel moved
    held_only = tk.moved_rows(ts[:1])
    assert all(row != "ATP" for row, _ in held_only)


def test_proton_hook_moves_charge_outward_and_books_heat_and_held_work():
    i = proton.Inputs(1000 * 10**-7.2, 1000 * 10**-5.5, -0.01, 3.0, 0.3, 3.0, 310.0)
    p = proton.Parameters(8.3027e-3, 2.0, 1e-4, 0.1, -30500.0, 7.2, 0.05)
    inward, current, rates = tk.proton_rates(i, p, 1.0, xp=np)
    assert rates.cycles_fmol_s > 0 and inward == pytest.approx(-2 * rates.cycles_fmol_s)
    assert current < 0  # positive charge leaves the inside
    cycles, heat, work = tk.book(rates, True, xp=np)
    assert heat >= 0 and work > heat


def test_neutral_hook_moves_finite_fuel_by_stoichiometry():
    i = neutral.Inputs(10.0, 86.9, 3.27, 0.03, 2.7, -30500.0, 1000.0, 310.0)
    p = neutral.Parameters(0.1, 1.0, 1.0, 0.1)
    inward, fuel, rates = tk.neutral_rates(i, p, 1.0, xp=np)
    assert fuel["ATP"] == pytest.approx(-rates.cycles_fmol_s)
    assert fuel["ADP"] == pytest.approx(rates.cycles_fmol_s)
    assert fuel["Pi"] == pytest.approx(rates.cycles_fmol_s)
    assert tk.book(rates, False, xp=np)[2] == 0.0  # finite fuel: no external work


def test_check_path_hooks_trace_under_jnp():
    import jax.numpy as jnp

    i = proton.Inputs(*(jnp.asarray(v) for v in (6.3e-5, 3.2e-3, -0.01, 3.0, 0.3, 3.0, 310.0)))
    p = proton.Parameters(
        *(jnp.asarray(v) for v in (8.3027e-3, 2.0, 1e-4, 0.1, -30500.0, 7.2, 0.05))
    )
    ok = jax.jit(lambda a, b: tk.domain(proton.LAW_ID, a, b, 1.0, xp=jnp))(i, p)
    assert bool(ok)
    assert tk.control_values([(0.0, 1.0), (5.0, 0.0)], [0.0, 4.9, 5.0, 9.0]) == [1.0, 1.0, 0.0, 0.0]
