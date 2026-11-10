"""Network-channel tooling for parity rung P4 (no BETSE; synthetic extractions).

The emulator's general-network layer (validation/betse/emulator/network.py) against a hand
computation of BETSE's run_loop_channels order, and network_world_adapter's world and
resolved_pump_tissue@3 definition builder. The emulator runs in NumPy here (fast); its JAX
path is the same code, checked against plain BETSE to roundoff in parity-rung2-4-20261109-01.
"""

import copy
import math
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from tests.unit.test_default_world_adapter import AREA, MAMMAL, OWNER, SITE, write_case
from validation.betse import default_world_adapter as adapter
from validation.betse import network_world_adapter as net
from validation.betse.emulator import junction, laws, network
from validation.betse.emulator import spatial as passive

KV, KLEAK = 1e-15, 6e-18  # max Dm, m^2/s
TM = 7.5e-9  # write_case's membrane thickness


def network_config(channels):
    return {
        "implement network": True,
        "biomolecules": [],
        "reactions": None,
        "transporters": None,
        "modulators": None,
        "channels": channels,
    }


CHANNELS = [
    {"name": "Kv", "channel class": "K", "channel type": "Kv1p5", "max Dm": KV,
     "apply to": "all", "init active": True},
    {"name": "K_Leak", "channel class": "K", "channel type": "KLeak", "max Dm": KLEAK,
     "apply to": "all", "init active": False},
]  # fmt: skip


@pytest.fixture(scope="module")
def network_case(tmp_path_factory):
    jax.config.update("jax_enable_x64", True)
    params = {"molecules_enabled": True, "network_config": network_config(CHANNELS)}
    return write_case(tmp_path_factory.mktemp("network") / "betse", ions=MAMMAL, params=params)


def bernoulli(x):
    return np.where(np.abs(x) < 1e-12, 1.0 - x / 2, x / np.expm1(x))


def ghk_inward_fmol_s(ci, co, vm, z, permeability, opening, variant, temperature=310.0):
    x = z * variant.faraday_C_mol * vm / (variant.gas_J_mol_K * temperature)
    return AREA * permeability * opening * 1e15 * (co * bernoulli(x) - ci * bernoulli(-x))


def kv1p5_steady_and_tau(vm):
    """BETSE vg_k.py Kv1p5 in mV and ms, returned in SI."""
    v = 1e3 * vm
    m = 1 / (1 + np.exp((v + 6.0) / -6.4))
    h = 1 / (1 + np.exp((v + 25.3) / 3.5))
    return (m, h), (1e-3 * (-0.1163 * v + 8.33), 1e-3 * (-15.5 * v + 1620.0))


def test_world_maps_only_ion_channel_networks(network_case, tmp_path):
    with pytest.raises(adapter.AdapterError, match="molecules_enabled"):
        adapter.betse_world(network_case)
    world = net.network_world(network_case)
    assert world["network_channels"] == [
        ("Kv", "kv1p5", KV, True),
        ("K_Leak", "kleak", KLEAK, False),
    ]
    assert world["membrane_thickness_m"] == TM
    assert {k for k, v in net.NETWORK_REQUIRED.items() if adapter.REQUIRED_PARAMS[k] != v} == {
        "molecules_enabled"
    }
    for change, message in (
        ({"biomolecules": [{"name": "X"}]}, "biomolecules"),
        ({"channels": [CHANNELS[0] | {"channel type": "Kv3p1"}]}, "only K Kv1p5, K KLeak"),
        ({"channels": [CHANNELS[0] | {"channel type": "Nav1p2"}]}, "only K Kv1p5, K KLeak"),
        (
            {"channels": [CHANNELS[0] | {"channel class": "Na", "channel type": "Nav1p3"}]},
            "only K Kv1p5",
        ),
        ({"channels": [CHANNELS[0] | {"apply to": ["spot"]}]}, "apply to"),
        ({"channels": [CHANNELS[0] | {"channel inhibitors": ["X"]}]}, "unmapped keys"),
        ({"channels": []}, "no channels"),
    ):
        config = network_config(copy.deepcopy(CHANNELS)) | change
        params = {"molecules_enabled": True, "network_config": config}
        case = write_case(
            tmp_path / f"refused-{len(list(tmp_path.iterdir()))}", ions=MAMMAL, params=params
        )
        with pytest.raises(net.NetworkError, match=message):
            net.network_world(case)


@pytest.mark.parametrize("phase, kleak_on", [("init", 0.0), ("sim", 1.0)])
def test_network_step_matches_betse_order_by_hand(network_case, phase, kleak_on):
    """One update: Kv1p5 gates, then Kv flux, then KLeak (inactive in INIT), in order.

    By hand: gates by BETSE's semi-implicit Euler at the step-start Vm; each channel's
    constant-field flux from the bulk cell concentration and the exterior after this
    step's ECM update, applied at once; the membrane and junction transfers (junction.step,
    channel-free) are unchanged and added; the membrane copy includes the channel transfer.
    """
    world = net.network_world(network_case)
    variant = laws.default_world("betse")
    start = adapter.phase_start(world, phase, "betse")
    state, p, _, vm0 = net.network_inputs(world, phase, start, variant)
    assert np.array_equal(np.asarray(p.active), [1.0, kleak_on])
    dt = world["dt_s"][phase]
    control = junction.Control(*(np.ones(AREA.size) for _ in junction.Control._fields))
    new, _, valid = network.step(state, p, dt, control, xp=np, variant=variant)
    assert bool(valid)
    base, _, _ = junction.step(state.junction, p.junction, dt, control, xp=np, variant=variant)

    t, old = p.junction.active.tissue, state.junction.active.tissue
    k = world["species"].index("K")
    _, reset, delta, field = passive.transport(old, t, dt, xp=np, variant=variant)
    vm = np.asarray(field.membrane_voltage_V)
    env = np.asarray(reset + delta).reshape(old.outside_concentration.shape).copy()
    after_ecm, cell = env.copy(), np.asarray(old.cell_concentration).copy()
    steady, tau = kv1p5_steady_and_tau(vm)
    (m0, h0), _ = kv1p5_steady_and_tau(vm0)  # BETSE's channel init at this phase's start
    m = (tau[0] * m0 + dt * steady[0]) / (tau[0] + dt)
    h = (tau[1] * h0 + dt * steady[1]) / (tau[1] + dt)
    voxel = world["site_volume_m3"] * 1e15
    cell_pL = world["cell_volume_m3"] * 1e15
    moved = np.zeros(AREA.size)
    for permeability, opening in ((KV / TM, m * h), (kleak_on * KLEAK / TM, 1.0)):
        flux = ghk_inward_fmol_s(
            cell[k, OWNER], env[k, SITE], vm, 1, permeability, opening, variant
        )
        np.add.at(cell[k], OWNER, dt * flux / cell_pL[OWNER])
        np.add.at(env[k], SITE, -dt * flux / voxel)
        moved += dt * flux
    expect_cell = np.asarray(base.active.tissue.cell_concentration) + cell - old.cell_concentration
    tissue = new.junction.active.tissue
    np.testing.assert_allclose(tissue.cell_concentration, expect_cell, rtol=1e-13)
    np.testing.assert_allclose(
        tissue.outside_concentration,
        np.asarray(base.active.tissue.outside_concentration) + env - after_ecm,
        rtol=1e-13,
    )
    np.testing.assert_allclose(
        tissue.membrane_concentration,
        np.asarray(base.active.tissue.membrane_concentration)
        + (cell - np.asarray(old.cell_concentration))[:, OWNER],
        rtol=1e-13,
    )
    ledger = np.asarray(base.active.tissue.membrane_inward_fmol).copy()
    ledger[k] += moved
    np.testing.assert_allclose(tissue.membrane_inward_fmol, ledger, rtol=1e-12, atol=1e-30)
    np.testing.assert_allclose(new.gates[0], np.stack((m, h)), rtol=1e-13)
    assert np.array_equal(new.gates[1], np.ones((2, AREA.size)))
    residual = passive.accounting(old, tissue, t)
    assert max(float(np.abs(v).max()) for v in residual.values()) < 1e-12


def test_inactive_channels_keep_their_gates_and_move_nothing(network_case):
    world = net.network_world(network_case)
    variant = laws.default_world("betse")
    state, p, _, _ = net.network_inputs(world, "init", adapter.phase_start(world, "init"), variant)
    off = p._replace(active=np.zeros(2))
    control = junction.Control(*(np.ones(AREA.size) for _ in junction.Control._fields))
    new, _, valid = network.step(state, off, 1e-3, control, xp=np, variant=variant)
    base, _, _ = junction.step(state.junction, p.junction, 1e-3, control, xp=np, variant=variant)
    assert bool(valid)
    assert np.array_equal(new.gates, state.gates)
    for a, b in zip(jax.tree.leaves(new.junction), jax.tree.leaves(base), strict=True):
        np.testing.assert_allclose(a, b, rtol=0, atol=0)


def test_resolved_definition_adds_one_population_per_patch_and_channel(network_case):
    from cells.core.specs import parse_spec
    from cells.models import surface_pump_v3
    from cells.models.registry import get_model

    world = net.network_world(network_case, blind=True)
    backend = net.NETWORK_RESOLVED
    assert backend.model_id(world) == "resolved_pump_tissue@3"
    assert set(adapter.EXECUTED) < set(backend.executed)
    raw = backend.definition(world, "init", adapter.phase_start(world, "init"), dt=1e-3)
    model, experiment = raw["model"], raw["experiment"]
    assert model["id"] == "resolved_pump_tissue@3"
    m = len(model["membranes"])
    assert raw["execution"]["channel_capacity"] == len(model["channels"]) == 2 * m
    (m0, h0), _ = kv1p5_steady_and_tau(0.0)
    for c, row in zip(model["channels"], [*model["membranes"]] * 2, strict=True):
        kv = c["id"].startswith("chan-Kv-")
        assert c["membrane_id"] == row["id"]
        assert c["kinetic_law"] == ("kv1p5_mh@1" if kv else "kleak_always_open@1")
        assert c["max_permeability_m_per_s"] == pytest.approx((KV if kv else KLEAK) / TM)
        assert c["abundance"] == 1.0
        assert c["permeant_ions"] == [{"species_id": "K", "relative_permeability": 1.0}]
        if kv:
            np.testing.assert_allclose(c["initial_gate"], [m0, h0], rtol=1e-14)
        else:
            assert c["initial_gate"] == []
    availability = {
        c["channel_id"]: c["schedule"][0]["availability"] for c in experiment["channel_controls"]
    }
    assert {v for k, v in availability.items() if "K_Leak" in k} == {0.0}  # init active False
    assert {v for k, v in availability.items() if "-Kv-" in k} == {1.0}
    spec = parse_spec(raw)
    assert get_model(spec.model) is surface_pump_v3

    # SIM handoff: gates at the steady state of Cells' INIT-end patch voltage.
    state, layout = surface_pump_v3.initial_values(spec)
    checkpoint = SimpleNamespace(state=state, layout=layout, time=0.0)
    start = backend.handoff(raw, checkpoint)
    vm = start["channel_vm_V"]
    assert vm.shape == (m,) and np.all(np.isfinite(vm))
    sim = backend.definition(world, "sim", start, dt=1e-4)
    (ms, hs), _ = kv1p5_steady_and_tau(vm)
    gates = np.array([c["initial_gate"] for c in sim["model"]["channels"][:m]])
    np.testing.assert_allclose(gates, np.stack((ms, hs), axis=1), rtol=1e-12)
    sim_availability = [
        c["schedule"][0]["availability"] for c in sim["experiment"]["channel_controls"]
    ]
    assert set(sim_availability) == {1.0}
    assert math.isclose(sim["execution"]["dt"], 1e-4)


# ............................................. heredity carriers (rung P4b): Na and Kir2.1

NAV, KIR, NALEAK = 2e-15, 7.5e-17, 4e-19  # max Dm, m^2/s
HEREDITY_CHANNELS = [
    {"name": "Nav", "channel class": "Na", "channel type": "Nav1p2", "max Dm": NAV,
     "apply to": "all", "init active": True},
    {"name": "Kir", "channel class": "K", "channel type": "Kir2p1", "max Dm": KIR,
     "apply to": "all", "init active": True},
    {"name": "Na_Leak", "channel class": "Na", "channel type": "NaLeak", "max Dm": NALEAK,
     "apply to": "all", "init active": False},
]  # fmt: skip


@pytest.fixture(scope="module")
def heredity_case(tmp_path_factory):
    jax.config.update("jax_enable_x64", True)
    params = {"molecules_enabled": True, "network_config": network_config(HEREDITY_CHANNELS)}
    return write_case(tmp_path_factory.mktemp("heredity") / "betse", ions=MAMMAL, params=params)


def nav1p2_steady_and_tau(vm):
    """BETSE vg_na.py Nav1p2 as written there (mV, ms), returned in SI."""
    V = 1e3 * np.asarray(vm, dtype=np.float64)
    a = (0.182 * ((V - 10.0) - -35.0)) / (1 - (np.exp(-((V - 10.0) - -35.0) / 9)))
    b = (0.124 * (-(V - 10.0) - 35.0)) / (1 - (np.exp(-(-(V - 10.0) - 35.0) / 9)))
    h_tau = 1 / (
        (0.024 * ((V - 10.0) - -50.0)) / (1 - (np.exp(-((V - 10.0) - -50.0) / 5)))
        + (0.0091 * (-(V - 10.0) - 75.000123)) / (1 - (np.exp(-(-(V - 10) - 75.000123) / 5)))
    )
    steady = (a / (a + b), 1.0 / (1 + np.exp((V - -65.0 - 10.0) / 6.2)))
    return steady, (1e-3 / (a + b), 1e-3 * h_tau)


def kir2p1_steady_and_tau(vm):
    """BETSE vg_k.py Kir2p1 as written there (mV, ms), returned in SI."""
    V = 1e3 * np.asarray(vm, dtype=np.float64)
    steady = (
        1 / (1 + np.exp((V - (-96.48)) / 23.26)),
        1 / (1 + np.exp((V - (-168.28)) / -44.13)),
    )
    tau = (
        3.7 + (-3.37 / (1 + np.exp((V - -32.9) / 27.93))),
        0.85 + (306.3 / (1 + np.exp((V - -118.29) / -27.23))),
    )
    return steady, (1e-3 * tau[0], 1e-3 * tau[1])


def test_heredity_channels_map_to_their_ions_and_laws(heredity_case):
    world = net.network_world(heredity_case)
    assert world["network_channels"] == [
        ("Nav", "nav1p2", NAV, True),
        ("Kir", "kir2p1", KIR, True),
        ("Na_Leak", "naleak", NALEAK, False),
    ]
    assert [net.channel_ion(k) for _, k, _, _ in world["network_channels"]] == ["Na", "K", "Na"]
    _, p, _, _ = net.network_inputs(
        world, "init", adapter.phase_start(world, "init"), laws.default_world("betse")
    )
    assert p.ion == tuple(world["species"].index(i) for i in ("Na", "K", "Na"))
    for vm in (np.linspace(-0.12, 0.06, 19) + 1.234e-4, np.zeros(3)):
        gates = net.steady_gates(["nav1p2", "kir2p1", "naleak"], vm)
        np.testing.assert_allclose(gates[0], nav1p2_steady_and_tau(vm)[0], rtol=1e-13)
        np.testing.assert_allclose(gates[1], kir2p1_steady_and_tau(vm)[0], rtol=1e-13)
        assert np.array_equal(gates[2], np.ones((2, vm.size)))
    assert network.opening("nav1p2", np.array([0.5, 0.25])) == 0.5**3 * 0.25
    assert network.opening("kir2p1", np.array([0.5, 0.25])) == 0.5 * 0.25**2
    assert network.opening("naleak", np.array([0.5, 0.25])) == 1.0


@pytest.mark.parametrize("phase, leak_on", [("init", 0.0), ("sim", 1.0)])
def test_heredity_step_matches_betse_order_by_hand(heredity_case, phase, leak_on):
    """One update: Nav1p2 (m^3 h, Na), Kir2p1 (m h^2, K), then NaLeak (Na; off in INIT).

    Gates by BETSE's semi-implicit Euler at the step-start Vm from BETSE's own mV/ms
    expressions; each channel's flux on the concentrations the previous channel left.
    """
    world = net.network_world(heredity_case)
    variant = laws.default_world("betse")
    start = adapter.phase_start(world, phase, "betse")
    state, p, _, vm0 = net.network_inputs(world, phase, start, variant)
    dt = world["dt_s"][phase]
    control = junction.Control(*(np.ones(AREA.size) for _ in junction.Control._fields))
    new, _, valid = network.step(state, p, dt, control, xp=np, variant=variant)
    assert bool(valid)
    base, _, _ = junction.step(state.junction, p.junction, dt, control, xp=np, variant=variant)

    t, old = p.junction.active.tissue, state.junction.active.tissue
    na, k = world["species"].index("Na"), world["species"].index("K")
    _, reset, delta, field = passive.transport(old, t, dt, xp=np, variant=variant)
    vm = np.asarray(field.membrane_voltage_V)
    env = np.asarray(reset + delta).reshape(old.outside_concentration.shape).copy()
    after_ecm, cell = env.copy(), np.asarray(old.cell_concentration).copy()
    gates = []
    for law in (nav1p2_steady_and_tau, kir2p1_steady_and_tau):
        steady, tau = law(vm)
        (m0, h0), _ = law(vm0)  # BETSE's channel init at this phase's start
        m = (tau[0] * m0 + dt * steady[0]) / (tau[0] + dt)
        h = (tau[1] * h0 + dt * steady[1]) / (tau[1] + dt)
        gates.append(np.stack((m, h)))
    voxel = world["site_volume_m3"] * 1e15
    cell_pL = world["cell_volume_m3"] * 1e15
    moved = np.zeros((len(world["species"]), AREA.size))
    for ion, permeability, opening in (
        (na, NAV / TM, gates[0][0] ** 3 * gates[0][1]),
        (k, KIR / TM, gates[1][0] * gates[1][1] ** 2),
        (na, leak_on * NALEAK / TM, 1.0),
    ):
        flux = ghk_inward_fmol_s(
            cell[ion, OWNER], env[ion, SITE], vm, 1, permeability, opening, variant
        )
        np.add.at(cell[ion], OWNER, dt * flux / cell_pL[OWNER])
        np.add.at(env[ion], SITE, -dt * flux / voxel)
        moved[ion] += dt * flux
    tissue = new.junction.active.tissue
    np.testing.assert_allclose(
        tissue.cell_concentration,
        np.asarray(base.active.tissue.cell_concentration) + cell - old.cell_concentration,
        rtol=1e-13,
    )
    np.testing.assert_allclose(
        tissue.outside_concentration,
        np.asarray(base.active.tissue.outside_concentration) + env - after_ecm,
        rtol=1e-13,
    )
    np.testing.assert_allclose(
        tissue.membrane_inward_fmol,
        np.asarray(base.active.tissue.membrane_inward_fmol) + moved,
        rtol=1e-12,
        atol=1e-30,
    )
    np.testing.assert_allclose(new.gates[0], gates[0], rtol=1e-12)
    np.testing.assert_allclose(new.gates[1], gates[1], rtol=1e-12)
    assert np.array_equal(new.gates[2], np.ones((2, AREA.size)))
    residual = passive.accounting(old, tissue, t)
    assert max(float(np.abs(v).max()) for v in residual.values()) < 1e-12


def test_resolved_definition_maps_heredity_laws_ions_and_gates(heredity_case):
    from cells.core.specs import parse_spec
    from cells.models import surface_pump_v3
    from cells.models.registry import get_model

    world = net.network_world(heredity_case, blind=True)
    start = adapter.phase_start(world, "init")
    raw = net.NETWORK_RESOLVED.definition(world, "init", start, dt=1e-3)
    m = len(raw["model"]["membranes"])
    expect = {
        "Nav": ("nav1p2_m3h_regularized@1", NAV, "Na", nav1p2_steady_and_tau(0.0)[0]),
        "Kir": ("kir2p1_mh2@1", KIR, "K", kir2p1_steady_and_tau(0.0)[0]),
        "Na_Leak": ("naleak_always_open@1", NALEAK, "Na", None),
    }
    assert len(raw["model"]["channels"]) == 3 * m
    for c in raw["model"]["channels"]:
        law, dm, ion, gate = expect[c["id"].split("-")[1]]
        assert c["kinetic_law"] == law
        assert c["max_permeability_m_per_s"] == pytest.approx(dm / TM)
        assert c["permeant_ions"] == [{"species_id": ion, "relative_permeability": 1.0}]
        if gate is None:
            assert c["initial_gate"] == []
        else:
            np.testing.assert_allclose(c["initial_gate"], np.ravel(gate), rtol=1e-13)
    availability = {
        c["channel_id"].split("-")[1]: c["schedule"][0]["availability"]
        for c in raw["experiment"]["channel_controls"]
    }
    assert availability == {"Nav": 1.0, "Kir": 1.0, "Na_Leak": 0.0}
    assert get_model(parse_spec(raw).model) is surface_pump_v3
