"""Software-only lifecycle fixtures and independent coupling checks, not native runs."""

import ast
import copy
import importlib
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("loop_context")
observer_module = importlib.import_module("loop_observer")
check = importlib.import_module("loop_check")
native_module = importlib.import_module("loop_native")
readiness = importlib.import_module("pilot_readiness")
reference = importlib.import_module("pilot_reference")
job = importlib.import_module("loop_job")
c, t = ctx.c, ctx.t
SCIENCE = Path("/synthetic/channel_loop/science")


@pytest.fixture(scope="module")
def registered():
    old = c.read(ctx.audit.CAPTURE / "registration.json")
    return {
        "protocol": c.read(ctx.PROTOCOL),
        "transport_protocol": old["protocol"],
        **{
            key: old[key]
            for key in ("base_protocol", "expected_geometry", "upstream", "cells_runtime")
        },
    }


@pytest.fixture(scope="module")
def prior_native():
    return c.read(ctx.audit.CAPTURE / "betse.json")


def synthetic_phase(network=True, channel=True, fault=None):
    """Fake method bodies carry explicit synthetic filenames; never native evidence."""
    namespace = {"SimpleNamespace": SimpleNamespace}
    exec(
        compile(
            """
class Gate:
    def init(self):
        self.m = 0.7
    def run(self, vm, p):
        self.m += 0.01
""",
            str(SCIENCE / "channels/vg_k.py"),
            "exec",
        ),
        namespace,
    )
    exec(
        compile(
            """
class Network:
    def __init__(self, sim):
        self.channels = {}
        if sim.with_channel:
            gate = Gate()
            gate.init()
            self.channels['K'] = SimpleNamespace(channel_core=gate)
    def clear_run_loop(self, sim):
        pass
    def run_loop_channels(self, phase):
        self.channels['K'].channel_core.run(phase.sim.vm, phase.p)
        if phase.sim.fault == 'double_gate':
            self.channels['K'].channel_core.run(phase.sim.vm, phase.p)
        phase.sim.amount += 0.01
    def run_loop(self, phase, t):
        pass
""",
            str(SCIENCE / "chemistry/networks.py"),
            "exec",
        ),
        namespace,
    )
    exec(
        compile(
            """
class Simulator:
    def init_dynamics(self, phase):
        if self.fault == 'setup_error_before':
            raise RuntimeError('setup failure before construction')
        self.molecules = SimpleNamespace(core=Network(self)) if self.with_network else None
        if self.fault == 'setup_error_after':
            raise RuntimeError('setup failure after construction')
    def clear_storage(self):
        self.stored = []
    def run_sim_core(self, phase):
        if self.fault != 'missing_setup':
            self.init_dynamics(phase)
        if self.fault == 'repeated_setup':
            self.init_dynamics(phase)
        self.clear_storage()
        self.update_V()
        self._run_sim_core_loop(phase, [0.0, 0.0002], {0.0002})
        self.finished = True
    def _run_sim_core_loop(self, phase, time_steps, time_steps_sampled):
        for t in time_steps:
            if self.fault == 'reinitialise':
                self.molecules.core.channels['K'].channel_core.init()
            if self.with_network:
                net = self.molecules.core
                net.clear_run_loop(self)
                if self.with_channel:
                    net.run_loop_channels(phase)
                net.run_loop(phase, t)
            self.update_all_concs()
            if self.fault != 'missing_voltage':
                self.update_V()
            if t in time_steps_sampled:
                self.write2storage(t)
    def update_all_concs(self):
        if self.fault == 'native_error':
            raise RuntimeError('synthetic native error')
    def update_V(self):
        self.vm = self.amount
    def write2storage(self, t):
        self.stored.append((t, self.amount, self.vm))
""",
            str(SCIENCE / "sim.py"),
            "exec",
        ),
        namespace,
    )
    sim = namespace["Simulator"]()
    sim.with_network, sim.with_channel, sim.fault = network, channel, fault
    sim.amount, sim.vm, sim.finished, sim.molecules = 0.0, 0.0, False, None
    return SimpleNamespace(sim=sim, p=SimpleNamespace(dt=0.0001))


def synthetic_copy(sim):
    gate = native_module.channel(sim)
    return {
        "amount": sim.amount,
        "voltage": sim.vm,
        "m": None if gate is None else gate.channel_core.m,
    }


def synthetic_initialise(phase):
    gate = native_module.channel(phase.sim)
    if gate is not None:
        gate.channel_core.m = 0.2


@pytest.mark.parametrize("network,channel", [(False, False), (True, False), (True, True)])
def test_real_profile_dispatch_preserves_synthetic_unobserved_result(network, channel):
    observed, plain = (synthetic_phase(network, channel) for _ in range(2))
    entries = []
    observer = observer_module.ChannelLoopObserver(
        observed, SCIENCE, synthetic_copy, entries.append
    )
    with observer_module.InitialConditionHook(observed, SCIENCE, synthetic_initialise, observer):
        observed.sim.run_sim_core(observed)
    with observer_module.InitialConditionHook(plain, SCIENCE, synthetic_initialise):
        plain.sim.run_sim_core(plain)
    result = observer.result()
    assert synthetic_copy(observed.sim) == synthetic_copy(plain.sim)
    assert observed.sim.stored == plain.sim.stored
    assert result["initial"]["m"] == (0.2 if channel else None)
    assert all(
        step["order"] == check.expected_order({"network": network, "channel": channel})
        for step in result["steps"]
    )
    assert len(entries) == 1 and len(result["steps"]) == 2
    assert result["gate_initializations"] == int(channel)
    assert result["hook_restored"] and sys.getprofile() is None
    saved = copy.deepcopy(result)
    observed.sim.amount = 99
    assert observer.result() == saved


@pytest.mark.parametrize(
    "fault",
    [
        "missing_setup",
        "repeated_setup",
        "reinitialise",
        "double_gate",
        "missing_voltage",
        "native_error",
    ],
)
def test_bad_synthetic_lifecycle_fails_and_restores_hook(fault):
    phase = synthetic_phase(fault=fault)
    observer = observer_module.ChannelLoopObserver(phase, SCIENCE, synthetic_copy, lambda v: None)
    with (
        pytest.raises((ValueError, RuntimeError)),
        observer_module.InitialConditionHook(phase, SCIENCE, synthetic_initialise, observer),
    ):
        phase.sim.run_sim_core(phase)
    assert sys.getprofile() is None and observer.partial()["status"] == "partial_not_qualified"
    with pytest.raises(ValueError):
        observer.result()


def test_existing_profile_is_not_replaced():
    def occupied(*args):
        return None

    phase = synthetic_phase()
    sys.setprofile(occupied)
    try:
        with pytest.raises(ValueError):
            with observer_module.InitialConditionHook(phase, SCIENCE, synthetic_initialise):
                pass
        assert sys.getprofile() is occupied
    finally:
        sys.setprofile(None)


@pytest.mark.parametrize("fault", ["setup_error_before", "setup_error_after"])
def test_failed_native_setup_does_not_apply_initial_condition(fault):
    phase = synthetic_phase(fault=fault)
    applications = []
    observer = observer_module.ChannelLoopObserver(
        phase, SCIENCE, synthetic_copy, lambda value: None
    )
    hook = observer_module.InitialConditionHook(phase, SCIENCE, applications.append, observer)
    with pytest.raises(RuntimeError, match="setup failure"), hook:
        phase.sim.run_sim_core(phase)
    assert not applications and hook.calls == 1 and hook.returns == 0
    assert not observer.calls["run_return"] and sys.getprofile() is None
    with pytest.raises(ValueError):
        observer.result()


def fabricated_row(r, variant, prior):
    """Generate test evidence from the OLD scalar oracle, not the new checker."""
    ref = prior["rows"][variant["id"] + "/prescribed_mh_a"]
    prep = prior["preparations"][variant["id"]]
    p, g = r["protocol"], prep["geometry"]
    n, m, dt = g["cell_count"], g["membrane_count"], p["dt_s"]
    f = r["transport_protocol"]["constants"]["F"]
    initial = {
        "physical": copy.deepcopy(ref["before"]),
        "channel": copy.deepcopy(ref["channel_before"]),
        "network_current": [0.0] * m,
    }
    fixture_before = copy.deepcopy(initial)
    fixture_before["channel"] = copy.deepcopy(ref["initialized_channel"])
    meta = {
        key: copy.deepcopy(ref[key])
        for key in (
            "species",
            "valence",
            "sim_temperature_K",
            "rho_channel",
            "ordinary_diffusivity_m2_per_s",
            "network_inventory",
        )
    }
    meta["channel"] = ref["metadata"]
    row = {
        "id": variant["id"],
        "mode": "observed",
        "geometry": g,
        "settings": prep["settings"],
        "source_constants": prep["source_constants"],
        "core_initial": ref["core_initial"],
        "fixture": {
            "before": fixture_before,
            "after": copy.deepcopy(initial),
            "metadata": meta,
            "declared_gate": p["initial_gate"],
            "applications": 1,
        },
        "smooth_weight_mem": ref["smooth_weight_mem"],
        "smooth_weight_other": ref["smooth_weight_other"],
        "fixture_hook": {"calls": 1, "returns": 1},
        "hook_restored": True,
        "native_pickle": "INITS/init_1.betse.gz",
        "steps": p["steps"],
        "dt_s": dt,
        "phase": "INIT",
    }
    state, steps = copy.deepcopy(initial), []
    labels = [i * p["duration_s"] / (p["steps"] - 1) for i in range(p["steps"])]
    for i in range(p["steps"]):
        step = {
            "index": i,
            "raw_label_s": labels[i],
            "before_elapsed_s": i * dt,
            "after_elapsed_s": (i + 1) * dt,
            "before": copy.deepcopy(state),
            "order": [],
        }

        def save(name, step=step):
            step[name] = copy.deepcopy(state)
            step["order"].append(name)

        density = [0.0] * m
        if variant["network"]:
            state["network_current"] = [0.0] * m
            save("after_clear")
            if variant["channel"]:
                save("before_channel")
                state["channel"]["modulator"] = [1.0] * m
                save("before_gate")
                ch = state["channel"]
                pairs = [
                    t.gate_reference(v, [ch["m"][j], ch["h"][j]], dt)[2]
                    for j, v in enumerate(state["physical"]["voltage_V"])
                ]
                ch.update(
                    {
                        "m": [v[0] for v in pairs],
                        "h": [v[1] for v in pairs],
                        "P": [math.prod(v) for v in pairs],
                        "derived_m_times_h": [math.prod(v) for v in pairs],
                    }
                )
                save("after_gate")
                maximum = ref["metadata"]["maxDm_m2_per_s"] / r["transport_protocol"]["thickness_m"]
                for face, owner in enumerate(g["membrane_owners"]):
                    density[face] = c.oracle(
                        {
                            "valence": 1,
                            "voltage_V": state["physical"]["voltage_V"][face],
                            "temperature_K": 298.15,
                            "area_m2": 1e-15,
                            "permeability_m_per_s": maximum * ch["P"][face],
                            "inside_mM": state["physical"]["inside_mM"][1][owner],
                            "outside_mM": state["physical"]["outside_mM"][1][0],
                        },
                        r["transport_protocol"]["constants"],
                        80,
                    )
                ch["density_mol_per_m2_s"] = density
                ch["DChan_m2_per_s"] = [
                    maximum * v * r["transport_protocol"]["thickness_m"] for v in ch["P"]
                ]
                mol = t.cell_sums(density, g)
                s = state["physical"]
                s["inside_mM"][1] = [
                    v + dt * q / volume
                    for v, q, volume in zip(
                        s["inside_mM"][1], mol, g["cell_volumes_m3"], strict=True
                    )
                ]
                s["outside_mM"][1] = [
                    s["outside_mM"][1][0] - dt * math.fsum(mol) / g["effective_bath_volume_m3"]
                ] * m
                s["at_membrane_mM"][1] = [
                    s["inside_mM"][1][owner] for owner in g["membrane_owners"]
                ]
                state["network_current"] = [-f * v for v in density]
                save("after_channel")
            save("before_network")
            state["physical"]["extra_current_density_A_per_m2"] = state["network_current"].copy()
            save("after_network")
        save("before_ordinary")
        save("after_ordinary")
        s = state["physical"]
        rho = [
            f
            * math.fsum(
                z * s["inside_mM"][j][cell]
                for j, z in enumerate(r["base_protocol"]["expected_valence"])
            )
            for cell in range(n)
        ]
        voltage = [
            q * volume / (area * 0.01)
            for q, volume, area in zip(rho, g["cell_volumes_m3"], g["cell_areas_m2"], strict=True)
        ]
        s["rho_C_per_m3"] = rho
        s["voltage_V"] = [voltage[owner] for owner in g["membrane_owners"]]
        current = [-f * v for v in density]
        average = [
            q / area for q, area in zip(t.cell_sums(current, g), g["cell_areas_m2"], strict=True)
        ]
        smoothed = [
            a * j + b * average[owner]
            for a, b, j, owner in zip(
                row["smooth_weight_mem"],
                row["smooth_weight_other"],
                current,
                g["membrane_owners"],
                strict=True,
            )
        ]
        s.update(
            {
                "Jmem_A_per_m2": current,
                "Jn_A_per_m2": smoothed,
                "I_mem_A": [
                    -j * area for j, area in zip(smoothed, g["membrane_areas_m2"], strict=True)
                ],
            }
        )
        save("after_voltage")
        steps.append(step)
    trace = {
        "status": "complete_observation_not_qualification",
        "hook_restored": True,
        "pending": None,
        "calls": dict.fromkeys(
            (
                "run_sim_core",
                "init_dynamics",
                "clear_storage",
                "initial_update_V",
                "loop",
                "loop_return",
                "run_return",
            ),
            1,
        ),
        "gate_initializations": int(variant["channel"]),
        "initial": initial,
        "steps": steps,
        "labels_s": labels,
        "sampled_indices": list(range(1, p["steps"])),
        "storage": [{"index": i, "raw_label_s": labels[i]} for i in range(1, p["steps"])],
    }
    histories = {"time": ctx.array_record(labels[1:])}
    for name, field in (
        ("cc_time", "inside_mM"),
        ("cc_env_time", "outside_mM"),
        ("vm_time", "voltage_V"),
        ("I_mem_time", "I_mem_A"),
        ("rho_cells_time", "rho_C_per_m3"),
    ):
        histories[name] = ctx.array_record(
            [v["after_voltage"]["physical"][field] for v in steps[1:]]
        )
    row.update(
        {
            "trace": trace,
            "final": copy.deepcopy(state),
            "histories": histories,
            "final_arrays": {k: ctx.array_record(v) for k, v in state["physical"].items()},
        }
    )
    return row


@pytest.fixture(scope="module")
def fabricated(registered, prior_native):
    rows = {}
    for variant in registered["transport_protocol"]["variants"]:
        a = fabricated_row(registered, variant, prior_native)
        b = copy.deepcopy(a)
        b.update({"mode": "unobserved", "trace": None})
        rows[variant["id"] + "/observed"], rows[variant["id"] + "/unobserved"] = a, b
    return {"rows": rows}


def test_complete_fabricated_full_loop_packet(registered, fabricated):
    result = check.evaluate(registered, fabricated)
    assert result["failed_comparisons"] == 0
    assert result["observed_steps"] == 32 and result["observer_pairs_checked"] == 4
    assert result["comparison_count"] > 10000
    assert result["summaries"][-1]["maximum_voltage_change_V"] > 1e-5


@pytest.mark.parametrize(
    "fault",
    [
        "gate_reset",
        "extra_gate",
        "double_transfer",
        "wrong_bath",
        "wrong_voltage",
        "current_sign",
        "leak",
        "junction",
        "auxiliary",
        "missing_step",
        "clock",
        "sampling",
        "initial_P",
        "fixture_changed",
        "order",
        "missing_pair",
        "observer_mutation",
        "wrong_modulator",
        "wrong_gate_product",
    ],
)
def test_corrupted_loop_evidence_rejected(registered, fabricated, fault):
    good = check.evaluate(registered, fabricated)
    assert good["status"] == "pass"
    packet = copy.deepcopy(fabricated)
    row = packet["rows"]["active_channel/observed"]
    step = row["trace"]["steps"][3]
    match fault:
        case "gate_reset":
            step["before"]["channel"]["m"][0] = 0.2
        case "extra_gate":
            step["after_channel"]["channel"]["m"][0] += 0.01
        case "double_transfer":
            step["after_ordinary"]["physical"]["inside_mM"][1][0] += 0.01
        case "wrong_bath":
            step["after_channel"]["physical"]["outside_mM"][1] = [4.1] * 30
        case "wrong_voltage":
            step["after_voltage"]["physical"]["voltage_V"][0] += 0.01
        case "current_sign":
            step["after_network"]["physical"]["extra_current_density_A_per_m2"][0] *= -1
        case "leak":
            step["before"]["physical"]["ordinary_density_mol_per_m2_s"][1][0] = 1e-12
        case "junction":
            step["before"]["physical"]["junction_density_mol_per_m2_s"][1][0] = 1e-12
        case "auxiliary":
            step["after_voltage"]["physical"]["inside_mM"][3][0] += 1
        case "missing_step":
            row["trace"]["steps"].pop()
        case "clock":
            step["after_elapsed_s"] = step["raw_label_s"]
        case "sampling":
            row["trace"]["storage"].pop()
        case "initial_P":
            row["trace"]["initial"]["channel"]["P"] = [0.12] * 30
        case "fixture_changed":
            row["fixture"]["applications"] = 2
        case "order":
            step["order"][1:3] = list(reversed(step["order"][1:3]))
        case "missing_pair":
            del packet["rows"]["empty_network/unobserved"]
        case "observer_mutation":
            row["final_arrays"]["inside_mM"]["bytes_sha256"] = "0" * 64
        case "wrong_modulator":
            step["after_gate"]["channel"]["modulator"] = [2.0] * 30
        case "wrong_gate_product":
            step["after_gate"]["channel"]["derived_m_times_h"][0] = 0.9
    try:
        result = check.evaluate(registered, packet)
    except (ValueError, KeyError):
        return
    assert result["failed_comparisons"] > 0


@pytest.mark.parametrize("variant_index", range(4))
@pytest.mark.parametrize("step_index", range(3))
def test_candidate_definition_existing_parser_and_resource_guard(
    registered, fabricated, variant_index, step_index
):
    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    variant = registered["transport_protocol"]["variants"][variant_index]
    row = fabricated["rows"][variant["id"] + "/observed"]
    dt = registered["protocol"]["pilot_candidate"]["cells_steps_s"][step_index]
    d = readiness.definition(registered, variant, row, dt)
    spec = parse_spec(d)
    state, _ = model.initial_values(spec)
    model.check_values(state, spec)
    mesh = timeline(spec)
    assert len(mesh) - 1 == round(0.002 / dt)
    assert trace_bytes(spec, len(mesh) - 1) < 64 * 1024**2
    assert len(state._fields) == 10
    if variant["channel"]:
        assert np.all(state.gate[:, :7] == np.array([[0.2], [0.6]]))
    assert all(entry["membrane"]["pump"] is None for entry in d["model"]["cells"])


@pytest.mark.parametrize("qscale", [0.0, -1e-5, -1e-4])
@pytest.mark.parametrize("index", range(4))
def test_independent_continuous_coupling_matches_own_state_rhs(
    registered, fabricated, qscale, index
):
    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    variant = registered["transport_protocol"]["variants"][index]
    row = fabricated["rows"][variant["id"] + "/observed"]
    spec = parse_spec(readiness.definition(registered, variant, row, 25e-6))
    state, layout = model.initial_values(spec)
    q = [qscale * (i + 1) if variant["permeability_fraction"] else 0.0 for i in range(7)]
    state.amount_increment[1, :7] = q
    state.channel_transferred[:7] = q
    state.extracellular_amount_increment[1, 0] = -math.fsum(q)
    if variant["channel"]:
        state.gate[0, :7] = [0.2 + i * 0.01 for i in range(7)]
        state.gate[1, :7] = [0.6 - i * 0.01 for i in range(7)]
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
    actual = model.rhs(state, control, layout, layout.active, xp=np)
    expected = reference.rates(
        readiness.parameters(registered, variant, row),
        q,
        state.gate[0, :7].tolist(),
        state.gate[1, :7].tolist(),
    )
    assert actual.amount_increment[1, :7].tolist() == pytest.approx(
        expected["inward_K_fmol_per_s"], abs=2e-10
    )
    assert float(actual.extracellular_amount_increment[1, 0]) == pytest.approx(
        expected["outside_K_fmol_per_s"], abs=2e-10
    )
    assert actual.gate[:, :7] == pytest.approx(np.array(expected["gate_rate_per_s"]), abs=2e-10)
    assert model.cell_voltage(state.amount_increment, layout, xp=np)[:7] == pytest.approx(
        expected["voltage_V"], abs=2e-10
    )
    assert np.all(actual.amount_increment[[0, 2]] == 0)


@pytest.mark.parametrize("value", [True, False, None, "1", float("nan"), float("inf")])
def test_reference_rejects_invalid_numbers(value):
    with pytest.raises(ValueError):
        reference.number(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("outside_volume_pL", 0),
        ("outside_K_fmol", -1),
        ("temperature_K", 310.15),
        ("F", 0),
        ("R", -1),
        ("cm_F_per_m2", 0),
    ],
)
def test_reference_rejects_invalid_physics(registered, fabricated, field, value):
    v = registered["transport_protocol"]["variants"][-1]
    p = readiness.parameters(registered, v, fabricated["rows"]["active_channel/observed"])
    p[field] = value
    with pytest.raises(ValueError):
        reference.rates(p, [0] * 7, [0.2] * 7, [0.6] * 7)


def test_shared_bath_feeds_other_cells_and_hidden_state_matters(registered, fabricated):
    v = registered["transport_protocol"]["variants"][-1]
    p = readiness.parameters(registered, v, fabricated["rows"]["active_channel/observed"])
    base = reference.rates(p, [0] * 7, [0.2] * 7, [0.6] * 7)
    changed = reference.rates(p, [-1e-4] + [0] * 6, [0.2] * 7, [0.6] * 7)
    assert changed["voltage_V"][1:] == base["voltage_V"][1:]
    assert changed["inward_K_fmol_per_s"][1:] != base["inward_K_fmol_per_s"][1:]
    hidden = reference.rates(p, [0] * 7, [0.4] * 7, [0.3] * 7)
    assert hidden["inward_K_fmol_per_s"] == base["inward_K_fmol_per_s"]
    assert hidden["gate_rate_per_s"] != base["gate_rate_per_s"]
    assert base["outside_K_fmol_per_s"] == -math.fsum(base["inward_K_fmol_per_s"])


def test_complete_cells_readiness_worker_without_trajectory(registered, fabricated, tmp_path):
    c.write(tmp_path / "betse.json", fabricated)
    result = readiness.worker(registered, tmp_path)
    assert result["status"] == "readiness_pass" and result["failed_comparisons"] == 0
    assert result["cells_trajectory_runs"] == 0 and len(result["records"]) == 12
    assert len(c.read(tmp_path / "pilot-candidate-definitions.json")) == 12
    assert all(row["integration_executed"] is False for row in result["records"])
    assert any(row["unit"] == "power_pJ_per_s" for row in result["comparisons"])


@pytest.mark.parametrize("index", range(4))
def test_configuration_changes_only_time_grid_and_retains_minimal_network(
    registered, tmp_path, index
):
    # Template keys from the actual frozen YAML structure, loaded by the installed
    # parser in the registered job; this unit test checks the pure transformation.
    import json

    v = registered["transport_protocol"]["variants"][index]
    # Alignment's overrides need every source key; the prior actual YAML was
    # already loaded by native BETSE and its exact source is bound by registration.
    yaml_path = ctx.audit.CAPTURE / "native" / v["id"] / "native.yaml"
    import subprocess

    script = (
        "from ruamel.yaml import YAML; import json,sys; "
        "print(json.dumps(YAML(typ='safe').load(open(sys.argv[1]))))"
    )
    template = json.loads(
        subprocess.check_output(
            [str(c.REFERENCE_PYTHON), "-B", "-c", script, str(yaml_path)], text=True, timeout=8
        )
    )
    old = ctx.old.setup.configuration(
        template, registered["base_protocol"], registered["transport_protocol"], v, tmp_path
    )
    new = ctx.configuration(template, registered, v, tmp_path)
    for block in ("init time settings", "sim time settings"):
        assert new[block]["total time"] == 0.0002
        assert new[block]["time step"] == new[block]["sampling rate"] == 25e-6
        old[block]["total time"] = 0.0002
    assert old == new
    assert new["general network"]["biomolecules"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("steps", 9),
        ("initial_gate", [0.4, 0.3]),
        ("phase", "SIM"),
        ("automatic_retry", True),
        ("cells_trajectory_runs", 1),
    ],
)
def test_unregistered_scope_rejected(registered, field, value):
    p = copy.deepcopy(registered["protocol"])
    p[field] = value
    with pytest.raises(ValueError):
        ctx.validate_protocol(p)


def test_native_initializer_and_observer_have_separate_write_authority():
    source = ast.parse((HERE / "loop_observer.py").read_text())
    observer = next(
        v for v in source.body if isinstance(v, ast.ClassDef) and v.name == "ChannelLoopObserver"
    )
    for node in ast.walk(observer):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert all(
                not ast.unparse(v).startswith(("sim.", "self.phase.", "channel.", "network."))
                for v in targets
            )
    text = (HERE / "loop_native.py").read_text()
    assert text.count("sim.run_sim_core(phase)") == 1
    assert "sim.init_dynamics(phase)" not in text and "._run_sim_core_loop(" not in text


def test_reference_is_model_free_and_readiness_never_integrates():
    source = ast.parse((HERE / "pilot_reference.py").read_text())
    imports = [
        node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
        for node in ast.walk(source)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert set(imports) == {"math", "decimal"}
    source = ast.parse((HERE / "pilot_readiness.py").read_text())
    calls = [ast.unparse(v.func) for v in ast.walk(source) if isinstance(v, ast.Call)]
    assert not any(
        name.endswith(("rk4_step", "rk4_checked_step", "run", "run_sim_core")) for name in calls
    )


def test_prior_closeout_authentication_does_not_rerun_audit():
    value = ctx.prior_closeout()
    assert value["single_transfer_qualified"] and len(value["files_sha256"]) == 9
    assert value["files_sha256"]["completion.json"] == ctx.PRIOR_SHA
    assert len(ctx.sources()) >= 90


def test_failed_execution_is_durable_and_does_not_launch_followup(tmp_path, monkeypatch):
    def fail(_):
        raise ValueError("test authentication failure")

    monkeypatch.setattr(job, "authenticate", fail)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *a: None)
    with pytest.raises(ValueError, match="test authentication failure"):
        job.execute(tmp_path)
    failure = c.read(tmp_path / "failure.json")
    assert not failure["automatic_retry"] and not failure["automatic_followup"]
    assert set(p.name for p in tmp_path.iterdir()) == {"failure.json"}


def test_registration_refuses_existing_output_before_work(tmp_path):
    with pytest.raises(ValueError):
        job.register(tmp_path, tmp_path / "missing.xml")


def test_output_writes_are_exclusive(tmp_path):
    c.write(tmp_path / "result.json", {"status": "old"})
    with pytest.raises(FileExistsError):
        c.write(tmp_path / "result.json", {"status": "rewritten"})


@pytest.mark.parametrize(
    "array", [np.array(0.0), np.array([-0.0, 1.0]), np.ones((2, 3)), np.zeros((0, 3))]
)
def test_independent_array_byte_reconstruction(array):
    ctx.validate_array_record(ctx.array_record(array))


@pytest.mark.parametrize(
    "field,value",
    [
        ("dtype", "<f4"),
        ("shape", [1, 3]),
        ("shape", [True]),
        ("values", [True, 1]),
        ("values", [float("nan"), 1]),
        ("bytes_sha256", "0" * 64),
    ],
)
def test_corrupt_array_record_rejected(field, value):
    record = ctx.array_record(np.array([0.0, 1.0]))
    record[field] = value
    with pytest.raises(ValueError):
        ctx.validate_array_record(record)


def test_registered_limits_and_detachment(registered):
    p = registered["protocol"]
    assert p["resources"]["total_timeout_seconds"] == 240
    assert p["resources"]["max_artifact_bytes"] == 128 * 1024**2
    assert p["cells_trajectory_runs"] == 0
    source = ast.parse((HERE / "loop_job.py").read_text())
    popen = [
        v
        for v in ast.walk(source)
        if isinstance(v, ast.Call) and ast.unparse(v.func) == "subprocess.Popen"
    ]
    assert len(popen) == 1 and any(
        k.arg == "start_new_session" and k.value.value is True for k in popen[0].keywords
    )
