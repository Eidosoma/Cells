"""Field-term propagation tooling (validation/betse/field_propagation.py; no BETSE).

The emulator's membrane-input hook (emulator/spatial.MembraneInputs) is neutral when absent
or trivial, changes only what membrane processes see, and the runner turns a Cells layout's
exterior potential into those inputs by the documented formula. Synthetic extractions from
test_default_world_adapter; the emulator runs in NumPy (hook checks) or tiny JAX runs.
"""

import json
import shutil

import jax
import numpy as np
import pytest

from cells.processes.electrochemistry import F, R
from tests.unit.test_betse_network_emulator import CHANNELS, network_config
from tests.unit.test_default_world_adapter import AREA, MAMMAL, OWNER, PROTOCOL, SITE, write_case
from validation.betse import cells_betse_compare as cmp
from validation.betse import default_world_adapter as adapter
from validation.betse import field_propagation as fp
from validation.betse import network_world_adapter as net
from validation.betse.emulator import junction, laws, network
from validation.betse.emulator import spatial as passive


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    jax.config.update("jax_enable_x64", True)
    return write_case(tmp_path_factory.mktemp("propagation") / "betse", ions=MAMMAL)


@pytest.fixture(scope="module")
def network_case(tmp_path_factory):
    jax.config.update("jax_enable_x64", True)
    params = {"molecules_enabled": True, "network_config": network_config(CHANNELS)}
    return write_case(tmp_path_factory.mktemp("netprop") / "betse", ions=MAMMAL, params=params)


def inputs_like(state_tissue, species, scale=1.0, shift=0.0):
    m = AREA.size
    return passive.MembraneInputs(np.full((species, m), scale), np.full(m, shift))


def leaves(tree):
    return [np.asarray(v) for v in jax.tree.leaves(tree)]


def test_trivial_membrane_inputs_are_bitwise_neutral(case, network_case):
    variant = laws.default_world("betse")
    control = junction.Control(*(np.ones(AREA.size) for _ in junction.Control._fields))
    world = adapter.betse_world(case)
    for phase in adapter.PHASES:
        state, p, _ = adapter.emulator_inputs(
            world, phase, adapter.phase_start(world, phase), variant
        )
        trivial = inputs_like(state, len(world["species"]))
        a = junction.step(state, p, world["dt_s"][phase], control, xp=np, variant=variant)
        b = junction.step(
            state, p, world["dt_s"][phase], control, xp=np, variant=variant, membrane_inputs=trivial
        )
        for x, y in zip(leaves(a), leaves(b), strict=True):
            assert np.array_equal(x, y)
    world = net.network_world(network_case)
    state, p, _, _ = net.network_inputs(world, "sim", adapter.phase_start(world, "sim"), variant)
    trivial = inputs_like(state, len(world["species"]))
    a = network.step(state, p, 1e-4, control, xp=np, variant=variant)
    b = network.step(state, p, 1e-4, control, xp=np, variant=variant, membrane_inputs=trivial)
    for x, y in zip(leaves(a), leaves(b), strict=True):
        assert np.array_equal(x, y)


def test_membrane_inputs_change_only_what_membranes_see(case):
    """The leak sees scaled outside concentrations and the shifted voltage; junctions do not."""
    variant = laws.default_world("betse")
    world = adapter.betse_world(case)
    state, p, _ = adapter.emulator_inputs(world, "sim", adapter.phase_start(world, "sim"), variant)
    t, old = p.active.tissue, state.active.tissue
    s = len(world["species"])
    rng = np.random.default_rng(3)
    inputs = passive.MembraneInputs(
        1 + 0.05 * rng.random((s, AREA.size)), 1e-3 * rng.random(AREA.size)
    )
    plain, _, _, field = passive.transport(old, t, 1e-4, xp=np, variant=variant)
    seen, _, _, _ = passive.transport(old, t, 1e-4, xp=np, variant=variant, membrane_inputs=inputs)
    z = world["valence"][:, None]
    expect = laws.ghk_leak(
        np.asarray(old.membrane_concentration),
        np.asarray(old.outside_concentration)[:, SITE] * inputs.outside_scale,
        np.asarray(field.membrane_voltage_V) + inputs.voltage_shift,
        z,
        t.temperature,
        t.membrane_area,
        t.membrane_permeability,
        t.membrane_open,
        variant,
        xp=np,
    )
    np.testing.assert_allclose(seen.membrane_inward_fmol_s, expect, rtol=1e-14, atol=0)
    assert not np.allclose(seen.membrane_inward_fmol_s, plain.membrane_inward_fmol_s)
    assert np.array_equal(seen.junction_outward_fmol_s, plain.junction_outward_fmol_s)
    for name in ("outside_flux_x_mol_m2_s", "outside_flux_y_mol_m2_s"):
        assert np.array_equal(getattr(seen, name), getattr(plain, name))


def fake_cells_layout(world, directory, phi_of_sample):
    """A comparison layout holding only the exterior-potential diagnostic of a Cells run."""
    phases = {}
    for phase in adapter.PHASES:
        times = [(k + 1) * world["dt_s"][phase] for k in range(world["steps"][phase])]
        phi = np.stack([phi_of_sample(phase, k) for k in range(len(times))])
        phases[phase] = {
            "elapsed_after_update_s": times,
            "final_elapsed_s": times[-1],
            "history": {"diag_extracellular_potential_time": phi},
            "final": {"diag_extracellular_potential": phi[-1]},
        }
    cmp.write_layout(
        directory,
        phases,
        protocol_sha256=None,
        betse_geometry_sha256=world["geometry_sha256"],
        provenance={"synthetic": True},
    )
    return directory


def test_field_inputs_follow_the_boltzmann_and_patch_formulas(case, tmp_path):
    world = adapter.betse_world(case)
    o = int(np.prod(world["grid_shape"]))
    rng = np.random.default_rng(5)
    table = {p: rng.normal(0, 1e-4, (world["steps"][p], o)) for p in adapter.PHASES}
    layout = fake_cells_layout(world, tmp_path / "cells", lambda p, k: table[p][k])
    interior = fp.interior_mask(world)
    for phase in adapter.PHASES:
        inputs, stats = fp.field_inputs(world, phase, layout, boltzmann=True, vpatch=True)
        steps = world["steps"][phase]
        assert inputs.outside_scale.shape == (steps, len(world["species"]), AREA.size)
        for u in range(steps):
            # Update u starts at u dt: latest sample at or before it (sample k ends at (k+1) dt).
            phi = table[phase][max(0, u - 1)]
            rel = phi[SITE] - phi[interior].mean()
            z = world["valence"][:, None]
            np.testing.assert_allclose(
                inputs.outside_scale[u], np.exp(-z * F * rel / (R * world["temperature_K"])),
                rtol=1e-14,
            )  # fmt: skip
            mean = np.bincount(OWNER, AREA * phi[SITE]) / np.bincount(OWNER, AREA)
            np.testing.assert_allclose(
                inputs.voltage_shift[u], -(phi[SITE] - mean[OWNER]), rtol=1e-12
            )
        assert stats["first_update_sample"] == 0
    scale_only, _ = fp.field_inputs(world, "sim", layout, boltzmann=True, vpatch=False)
    assert not scale_only.voltage_shift.any()
    shift_only, _ = fp.field_inputs(world, "sim", layout, boltzmann=False, vpatch=True)
    assert np.all(shift_only.outside_scale == 1)
    other = json.loads((layout / cmp.LAYOUT_MANIFEST).read_text())
    other["betse_geometry_sha256"] = "0" * 64
    wrong = tmp_path / "wrong"
    shutil.copytree(layout, wrong)
    (wrong / cmp.LAYOUT_MANIFEST).write_text(json.dumps(other))
    with pytest.raises(adapter.AdapterError, match="different BETSE geometry"):
        fp.field_inputs(world, "sim", wrong, boltzmann=True, vpatch=False)


@pytest.mark.parametrize("runner_name", ["default", "network"])
def test_base_run_is_the_plain_emulator_and_a_zero_field_changes_nothing(
    case, network_case, runner_name, tmp_path
):
    source = case if runner_name == "default" else network_case
    protocol = tmp_path / "protocol.json"
    shutil.copyfile(PROTOCOL, protocol)
    options = dict(constants="betse", device_kind="cpu", sim_start="chained", dt_factor=2)
    if runner_name == "default":
        plain = adapter.run_emulator(source, protocol, tmp_path / "plain", **options)
        world = adapter.betse_world(source)
    else:
        plain = net.run_network_emulator(source, protocol, tmp_path / "plain", **options)
        world = net.network_world(source)
    assert plain["valid"]
    zero = fake_cells_layout(
        world, tmp_path / "cells", lambda p, k: np.zeros(int(np.prod(world["grid_shape"])))
    )
    for mode in ("base", "both"):
        record = fp.run_propagation(
            source,
            protocol,
            zero,
            tmp_path / mode,
            mode=mode,
            runner_name=runner_name,
            constants="betse",
            sim_start="chained",
            dt_factor=2,
        )
        assert record["valid"] and record["mode"] == mode
        for phase in adapter.PHASES:
            for part in ("history", "final"):
                a = np.load(tmp_path / "plain" / f"{phase}_{part}.npz")
                b = np.load(tmp_path / mode / f"{phase}_{part}.npz")
                assert sorted(a.files) == sorted(b.files)
                for name in a.files:
                    assert np.array_equal(a[name], b[name]), (mode, phase, part, name)
    budget = adapter.difference_budget(
        world, [("zero_field", tmp_path / "base", tmp_path / "both")]
    )
    rows = budget["pairs"]["zero_field"]["phases"]
    assert all(o["max"] == 0 for r in rows.values() for o in r["observables"].values())


def test_a_field_moves_the_cells_and_is_read_by_the_tolerance_recipe(case, tmp_path):
    from validation.betse import protocol_tolerances as tol

    world = adapter.betse_world(case)
    protocol = tmp_path / "protocol.json"
    shutil.copyfile(PROTOCOL, protocol)
    o = int(np.prod(world["grid_shape"]))
    ramp = np.linspace(-2e-4, 2e-4, o)
    cells = fake_cells_layout(world, tmp_path / "cells", lambda p, k: ramp)
    for mode in ("base", "boltzmann"):
        fp.run_propagation(case, protocol, cells, tmp_path / mode, mode=mode, sim_start="chained")
    budget = adapter.difference_budget(
        world, [("field", tmp_path / "base", tmp_path / "boltzmann")]
    )
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(cmp.json_safe(budget)))
    ctx = tol.Context(case, tmp_path)
    term = tol.term(ctx, {"budget": str(path), "pairs": ["field"]})
    assert term["sim"]["voltage"] > 0
    assert term["sim"]["cell_concentration"]["K"] > 0


@pytest.mark.parametrize("mode", ["base", "boltzmann", "vpatch", "both"])
def test_sim_gates_start_at_the_patch_voltage_only_with_the_shift(
    network_case, tmp_path, monkeypatch, mode
):
    """Network runner: SIM-start gates at g_inf(Vm + the INIT phase's last shift) in vpatch and
    both; base and boltzmann pass no shift, so their SIM inputs are bitwise the plain ones.

    The emulator phase is stubbed (it returns its start state), so only the phase inputs are
    exercised; the plain runs themselves are checked by the base/zero-field test above.
    """
    world = net.network_world(network_case)
    variant = laws.default_world("betse")
    o = int(np.prod(world["grid_shape"]))
    rng = np.random.default_rng(11)
    table = {p: rng.normal(0, 1e-3, (world["steps"][p], o)) for p in adapter.PHASES}
    cells = fake_cells_layout(world, tmp_path / "cells", lambda p, k: table[p][k])
    protocol = tmp_path / "protocol.json"
    shutil.copyfile(PROTOCOL, protocol)
    seen = []

    def stub(route, state, layout, dt, steps, substeps, drive, variant, device):
        seen.append(state)
        observed = [np.asarray(v) for v in route.observe(state, layout, variant)]
        return {
            "valid": True,
            "accepted_samples": steps,
            "first_rejected_sample": None,
            "wall_s_including_compile": 0.0,
            **dict(
                zip(
                    ("vm", "cell_mM", "env_mM", "v_env", "gate_open"),
                    [np.stack([v] * steps) for v in observed],
                    strict=True,
                )
            ),
            "end": route.end(state),
        }

    monkeypatch.setattr(fp, "driven_phase", stub)
    record = fp.run_propagation(
        network_case, protocol, cells, tmp_path / mode, mode=mode, runner_name="network"
    )
    assert record["sim_gate_shift"] == (mode in ("vpatch", "both"))
    init, sim = seen
    start = adapter.phase_start(world, "sim", "chained", fp.runner("network").end(init))
    plain, _, _, vm = net.network_inputs(world, "sim", start, variant)
    if mode in ("base", "boltzmann"):
        for a, b in zip(leaves(sim), leaves(plain), strict=True):
            assert np.array_equal(a, b)
        assert record["phases"]["sim"]["channel_gate_shift_max_abs_V"] is None
    else:
        shift = fp.field_inputs(world, "init", cells, boltzmann=False, vpatch=True)[0].voltage_shift
        kinds = [k for _, k, _, _ in world["network_channels"]]
        want = net.steady_gates(kinds, vm + shift[-1])
        assert np.array_equal(np.asarray(sim.gates), want)
        assert not np.array_equal(np.asarray(sim.gates), np.asarray(plain.gates))
        for a, b in zip(leaves(sim.junction), leaves(plain.junction), strict=True):
            assert np.array_equal(a, b)
        assert record["phases"]["sim"]["channel_gate_shift_max_abs_V"] == np.abs(shift[-1]).max()
