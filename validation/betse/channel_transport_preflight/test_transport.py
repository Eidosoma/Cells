"""Short software checks. Fabricated native/JAX packets are not captured evidence."""

import ast
import copy
import importlib
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
t = importlib.import_module("transport_protocol")
check = importlib.import_module("transport_check")
job = importlib.import_module("transport_job")
workers = importlib.import_module("transport_workers")
c = t.c


def synthetic_snapshot(ci, co, g, p):
    n, m, f = g["cell_count"], g["membrane_count"], p["constants"]["F"]
    z = [1, 1, -1, 2, -1, -1]
    rho = [f * math.fsum(z[s] * ci[s][i] for s in range(6)) for i in range(n)]
    voltage = [
        q * v / (a * 0.01)
        for q, v, a in zip(rho, g["cell_volumes_m3"], g["cell_areas_m2"], strict=True)
    ]
    return {
        "inside_mM": copy.deepcopy(ci),
        "outside_mM": copy.deepcopy(co),
        "at_membrane_mM": [[row[i] for i in g["membrane_owners"]] for row in ci],
        "voltage_V": [voltage[i] for i in g["membrane_owners"]],
        "rho_C_per_m3": rho,
        "boundary_voltage_V": [0.0] * 100,
        "ordinary_density_mol_per_m2_s": [[0.0] * m for _ in range(6)],
        "junction_density_mol_per_m2_s": [[0.0] * m for _ in range(6)],
        "extra_current_density_A_per_m2": [0.0] * m,
        "Jmem_A_per_m2": [0.0] * m,
        "Jn_A_per_m2": [0.0] * m,
        "I_mem_A": [0.0] * m,
        "extra_rho_cells_C_per_m3": [0.0] * n,
        "extra_rho_env_C_per_m3": [0.0] * m,
    }


def synthetic_native(r):
    p, base, rows, preparations = r["protocol"], r["base_protocol"], {}, {}
    g = copy.deepcopy(r["expected_geometry"])
    g.update(
        {
            "diviterm_m": [
                v / a for v, a in zip(g["cell_volumes_m3"], g["cell_areas_m2"], strict=True)
            ],
            "configured_bath_volume_m3": 0.001 * 0.00015**2 * 0.00001,
            "specific_capacitance_F_per_m2": 0.01,
            "grid_shape": [10, 10],
        }
    )
    g["effective_bath_volume_m3"] = g["membrane_count"] * g["configured_bath_volume_m3"]
    n, m, dt, f = g["cell_count"], g["membrane_count"], p["dt_s"], p["constants"]["F"]
    for variant in p["variants"]:
        settings = {
            "is_ecm": False,
            "cell_polarizability": 0.0,
            "cluster_open": True,
            "alpha_NaK": 0.0,
            "alpha_Ca": 0.0,
            "Ca_dyn": False,
            "molecules_enabled": variant["network"],
            "grn_enabled": False,
            "fluid_flow": False,
            "deformation": False,
            "deform_osmo": False,
            "dynamic_noise": False,
            "channel_noise_level": 0.0,
            "v_sensitive_gj": False,
            "gj_surface": 0.0,
            "substances_affect_charge": True,
            "solver": "FULL",
            "temperature_K": p["temperature_K"],
            "thickness_m": p["thickness_m"],
            "constants": p["constants"],
        }
        preparations[variant["id"]] = {
            "geometry": g,
            "settings": settings,
            "source_constants": {"F": 96485.0, "R": 8.314},
        }
        for fixture in p["states"]:
            ci, co = [[v] * n for v in base["inside_mM"]], [[v] * m for v in base["outside_mM"]]
            before = synthetic_snapshot(ci, co, g, p)
            initialized = b = after = metadata = None
            density = [0.0] * m
            if variant["channel"]:
                equilibrium = [
                    1 / (1 + math.exp(-0.006 / 0.0064)),
                    1 / (1 + math.exp(0.0253 / 0.0035)),
                ]
                initialized = {
                    "m": [equilibrium[0]] * m,
                    "h": [equilibrium[1]] * m,
                    "P": None,
                    "DChan_m2_per_s": None,
                    "derived_m_times_h": [math.prod(equilibrium)] * m,
                    "density_mol_per_m2_s": [0.0] * m,
                    "modulator": 1.0,
                }
                b = copy.deepcopy(initialized)
                pair = equilibrium if fixture["gate"] is None else fixture["gate"]
                b.update(
                    {
                        "m": [pair[0]] * m,
                        "h": [pair[1]] * m,
                        "derived_m_times_h": [math.prod(pair)] * m,
                    }
                )
                post = [t.gate_reference(v, pair, dt)[2] for v in before["voltage_V"]]
                opened = [math.prod(pair) for pair in post]
                maxdm = (
                    p["thickness_m"]
                    * p["max_permeability_m_per_s"]
                    * p["abundance"]
                    * variant["permeability_fraction"]
                )
                for face in range(m):
                    density[face] = c.oracle(
                        {
                            "valence": 1,
                            "voltage_V": before["voltage_V"][face],
                            "temperature_K": p["temperature_K"],
                            "area_m2": 1e-15,
                            "permeability_m_per_s": opened[face] * maxdm / p["thickness_m"],
                            "inside_mM": 140,
                            "outside_mM": 4,
                        },
                        p["constants"],
                        precision=80,
                    )
                after = {
                    "m": [pair[0] for pair in post],
                    "h": [pair[1] for pair in post],
                    "P": opened,
                    "derived_m_times_h": opened,
                    "DChan_m2_per_s": [v * maxdm for v in opened],
                    "density_mol_per_m2_s": density,
                    "modulator": [1.0] * m,
                }
                metadata = {
                    "name": "Kv1p5_contact",
                    "class": "K",
                    "type": "Kv1p5",
                    "targets": list(range(m)),
                    "target_profiles": "all",
                    "init_active": True,
                    "maxDm_m2_per_s": maxdm,
                    "ions": ["K"],
                    "relative_permeability": [1.0],
                    "powers": [1, 1],
                    "time_unit": 1000,
                    "alpha_eval_string": "(1)",
                }
            flux = t.cell_sums(density, g)
            ci[1] = [
                v + dt * rate / volume
                for v, rate, volume in zip(ci[1], flux, g["cell_volumes_m3"], strict=True)
            ]
            co[1] = [4 - math.fsum(flux) * dt / g["effective_bath_volume_m3"]] * m
            final = synthetic_snapshot(ci, co, g, p)
            current = [-v * f for v in density]
            average = [
                v / a for v, a in zip(t.cell_sums(current, g), g["cell_areas_m2"], strict=True)
            ]
            smoothed = [
                0.5 * (j + average[i]) for j, i in zip(current, g["membrane_owners"], strict=True)
            ]
            final.update(
                {
                    "extra_current_density_A_per_m2": current,
                    "Jmem_A_per_m2": current,
                    "Jn_A_per_m2": smoothed,
                    "I_mem_A": [
                        -j * a for j, a in zip(smoothed, g["membrane_areas_m2"], strict=True)
                    ],
                }
            )
            after_channel = synthetic_snapshot(ci, co, g, p)
            after_channel["voltage_V"] = [
                v + (1e-25 if variant["channel"] else 0) for v in before["voltage_V"]
            ]
            after_network = copy.deepcopy(after_channel)
            after_network["extra_current_density_A_per_m2"] = current
            key = f"{variant['id']}/{fixture['id']}"
            rows[key] = {
                "id": key,
                "core_initial": {
                    "inside_mM": before["inside_mM"],
                    "outside_mM": before["outside_mM"],
                    "gate_initialization_voltage_V": [0.0] * m,
                },
                "initialized_channel": initialized,
                "channel_before": b,
                "channel_after": after,
                "before": before,
                "after_channel": after_channel,
                "after_network": after_network,
                "after_ordinary": copy.deepcopy(after_network),
                "after_voltage": final,
                "network_current_density_A_per_m2": current,
                "metadata": metadata,
                "network_inventory": None
                if not variant["network"]
                else {
                    "molecules": [],
                    "reactions": [],
                    "reactions_env": [],
                    "transporters": [],
                    "channels": ["Kv1p5_contact"] if variant["channel"] else [],
                    "modulators": [],
                },
                "dt_s": dt,
                "sim_temperature_K": p["temperature_K"],
                "rho_channel": 1,
                "ordinary_diffusivity_m2_per_s": [[0.0] * m for _ in range(6)],
                "species": base["expected_species"],
                "valence": base["expected_valence"],
                "dtype": "float64",
                "smooth_weight_mem": [0.5] * m,
                "smooth_weight_other": [0.5] * m,
                "call_counts": {
                    "channel_runner": int(variant["channel"]),
                    "empty_chemistry_runner": int(variant["network"]),
                    "ordinary_update": 1,
                    "full_simulator_loop": 0,
                },
            }
    return {"rows": rows, "preparations": preparations}


@pytest.fixture(scope="module")
def registration():
    p = c.read(t.PROTOCOL)
    saved = c.read(c.ROOT / p["geometry_source"])
    return {
        "protocol": p,
        "base_protocol": c.read(t.a.PROTOCOL),
        "expected_geometry": {k: saved[k] for k in t.GEOMETRY_FIELDS},
    }


@pytest.fixture(scope="module")
def native(registration):
    return synthetic_native(registration)


@pytest.fixture(scope="module")
def mapped(registration, native):
    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    p, definitions, results = registration["protocol"], {}, {}
    for variant in p["variants"]:
        g = native["preparations"][variant["id"]]["geometry"]
        for fixture in p["states"]:
            key = f"{variant['id']}/{fixture['id']}"
            row = native["rows"][key]
            definition = t.definition(registration["base_protocol"], p, variant, g, row)
            spec = parse_spec(definition)
            state, layout = model.initial_values(spec)
            model.check_values(state, spec)
            control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
            gates = state.gate.copy()
            if variant["channel"]:
                gates[:, :7] = [
                    t.uniform_faces(row["channel_after"][k], g["membrane_owners"], 7)
                    for k in ("m", "h")
                ]
            values = workers.evaluate_transfer(model, p["dt_s"], state, layout, control, gates, np)
            model.check_values(values[2], spec)
            results[key] = workers.encode_cells(state, gates, values)
            definitions[key] = definition
    # Only NumPy has actually executed here. These copies exercise checker coverage,
    # not JAX runtime agreement. The detached worker must execute all three backends.
    return {"definitions": definitions, "results": {b: copy.deepcopy(results) for b in t.BACKENDS}}


@pytest.fixture(scope="module")
def evaluated(registration, native, mapped):
    return check.evaluate(registration, native, mapped)


def test_complete_synthetic_panel(evaluated):
    assert evaluated["status"] == "pass", [r for r in evaluated["comparisons"] if not r["passed"]][
        :5
    ]
    assert evaluated["comparison_count"] > 10000
    assert evaluated["failed_comparisons"] == 0
    assert evaluated["native_single_updates"] == 12
    assert evaluated["cells_matched_transfers_per_backend"] == 12
    assert not evaluated["independent_audit_complete"]
    assert not evaluated["coupled_trajectory_qualified"]
    assert not evaluated["biology_validated"] and not evaluated["gpu_tested"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("dt_s", 0.001),
        ("temperature_K", 310.15),
        ("cell_count", 1),
        ("membrane_face_count", 7),
        ("upstream_revision", "latest"),
        ("variants", []),
        ("states", []),
        ("abundance", 2),
        ("max_permeability_m_per_s", 1),
        ("substances_affect_charge", False),
        ("tolerances", {"relative": 1}),
        ("resources", {}),
        ("extra", "unregistered"),
    ],
)
def test_protocol_mutations_rejected(registration, field, value):
    p = copy.deepcopy(registration["protocol"])
    p[field] = value
    with pytest.raises(ValueError, match="Protocol differs"):
        t.validate_protocol(p)


@pytest.mark.parametrize(
    "values,owners,n",
    [
        ([1, 2], [0, 0], 1),
        ([1], [0, 0], 1),
        ([1], [1], 1),
        ([float("nan")], [0], 1),
        ([float("inf")], [0], 1),
        ([1], [0], 2),
    ],
)
def test_nonuniform_or_invalid_face_reduction_rejected(values, owners, n):
    with pytest.raises(ValueError):
        t.uniform_faces(values, owners, n)


@pytest.mark.parametrize("values", [[], [1, 2], [float("nan")], [float("inf")]])
def test_invalid_bath_rejected(values):
    with pytest.raises(ValueError):
        t.uniform_bath(values)


@pytest.mark.parametrize("index", range(4))
def test_minimal_network_configuration(registration, tmp_path, index):
    p, base = registration["protocol"], registration["base_protocol"]
    template = {}
    for path, value in base["yaml_overrides"]:
        target = template
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = value
    template["sim time settings"] = {}
    template["general network"]["channels"] = [{"name": "UNWANTED"}]
    original = copy.deepcopy(template)
    variant = p["variants"][index]
    conf = t.configuration(template, base, p, variant, tmp_path)
    assert template == original
    network = conf["general network"]
    assert network["implement network"] == variant["network"]
    assert all(
        network[k] is None for k in ("biomolecules", "reactions", "transporters", "modulators")
    )
    assert "UNWANTED" not in repr(conf) and "max conductivity" not in repr(conf)
    assert bool(network["channels"]) == variant["channel"]
    assert conf["variable settings"]["temperature"] == 298.15
    assert set(
        conf["tissue profile definition"]["tissue"]["default"]["diffusion constants"].values()
    ) == {0}


@pytest.mark.parametrize("index", range(4))
def test_mapping_keeps_actual_immobile_charge_and_no_pump(registration, native, mapped, index):
    variant = registration["protocol"]["variants"][index]
    definition = mapped["definitions"][variant["id"] + "/native_initial"]
    g = native["preparations"][variant["id"]]["geometry"]
    assert len(definition["model"]["cells"]) == 7
    assert definition["model"]["temperature_K"] == 298.15
    assert definition["execution"]["channel_capacity"] == 10
    for i, entry in enumerate(definition["model"]["cells"]):
        assert entry["membrane"]["pump"] is None
        assert set(entry["membrane"]["passive"]["permeability_m_per_s"].values()) == {0}
        assert (entry["channel"] is not None) == variant["channel"]
        vi = g["cell_volumes_m3"][i] / 1e-15
        expected = math.fsum([2 * 0.00002 * vi, -100 * vi, -42.00004 * vi])
        assert entry["cell"]["fixed_charge_equivalent_fmol"] == expected
    assert (
        definition["model"]["extracellular"]["volume_pL"] == g["effective_bath_volume_m3"] / 1e-15
    )


def test_block_evolves_two_gates_but_moves_no_ions(native, mapped, evaluated):
    key = "blocked_channel/prescribed_mh_a"
    row = mapped["results"]["numpy"][key]
    assert row["rhs"]["gate"][0][0] != 0
    assert row["matched_gate"][0][0] != row["initial_state"]["gate"][0][0]
    assert row["after"]["channel_transferred"] == [0] * 10
    assert row["after"]["amount_increment"] == [[0] * 8 for _ in range(3)]
    assert len(evaluated["distinct_hidden_state_controls"]) == 2


@pytest.mark.parametrize(
    "field,index,value",
    [
        ("channel_after/m", 0, 0.9),
        ("channel_after/h", 0, 0.9),
        ("channel_after/P", 0, 0.9),
        ("channel_after/DChan_m2_per_s", 0, 1e-10),
        ("channel_after/density_mol_per_m2_s", 0, 1e-4),
        ("network_current_density_A_per_m2", 0, 1),
        ("after_voltage/voltage_V", 0, -0.01),
        ("after_voltage/Jmem_A_per_m2", 0, 1),
        ("after_voltage/I_mem_A", 0, 1),
    ],
)
def test_native_corruption_rejected(registration, native, field, index, value):
    p, base = registration["protocol"], registration["base_protocol"]
    row = copy.deepcopy(native["rows"]["active_channel/prescribed_mh_a"])
    target = row
    for key in field.split("/"):
        target = target[key]
    target[index] = value
    ledger = check.Ledger(p)
    try:
        check.native_case(
            p,
            base,
            p["variants"][3],
            p["states"][1],
            native["preparations"]["active_channel"],
            row,
            ledger,
        )
    except ValueError:
        return
    assert any(not r["passed"] for r in ledger.rows)


@pytest.mark.parametrize(
    "change",
    [
        "double_transfer",
        "bath_volume",
        "extra_channel",
        "target",
        "initial_P",
        "temperature",
        "pump",
        "ordinary_duplication",
    ],
)
def test_native_structure_or_ownership_rejected(registration, native, change):
    p, base = registration["protocol"], registration["base_protocol"]
    row = copy.deepcopy(native["rows"]["active_channel/prescribed_mh_a"])
    prep = copy.deepcopy(native["preparations"]["active_channel"])
    if change == "double_transfer":
        row["after_ordinary"]["inside_mM"][1][0] -= 0.01
    elif change == "bath_volume":
        prep["geometry"]["effective_bath_volume_m3"] /= 30
    elif change == "extra_channel":
        row["network_inventory"]["channels"].append("KLeak")
    elif change == "target":
        row["metadata"]["targets"].pop()
    elif change == "initial_P":
        row["initialized_channel"]["P"] = [0] * 30
    elif change == "temperature":
        row["sim_temperature_K"] = 310.15
    elif change == "pump":
        prep["settings"]["alpha_NaK"] = 1
    else:
        row["after_ordinary"]["ordinary_density_mol_per_m2_s"][1][0] = 1e-5
    ledger = check.Ledger(p)
    try:
        check.native_contract(
            p, base, p["variants"][3], prep, row, registration["expected_geometry"]
        )
        check.native_case(p, base, p["variants"][3], p["states"][1], prep, row, ledger)
    except ValueError:
        return
    assert any(not r["passed"] for r in ledger.rows)


@pytest.mark.parametrize(
    "change",
    [
        "gate",
        "gate_again",
        "flux",
        "outside",
        "padding",
        "definition",
        "voltage",
        "charge",
        "amount",
        "initial_history",
    ],
)
def test_cells_corruption_rejected(registration, native, mapped, change):
    p, base, key = (
        registration["protocol"],
        registration["base_protocol"],
        "active_channel/prescribed_mh_a",
    )
    row, result = native["rows"][key], copy.deepcopy(mapped["results"]["numpy"][key])
    definition = copy.deepcopy(mapped["definitions"][key])
    if change == "gate":
        result["matched_gate"][0][0] = 0.5
    elif change == "gate_again":
        result["after"]["gate"][0][0] = 0.5
    elif change == "flux":
        result["rhs"]["channel_transferred"][0] = 1
    elif change == "outside":
        result["after"]["extracellular_amount_increment"][1][0] = 0.1
    elif change == "padding":
        result["after"]["channel_transferred"][-1] = 1e-12
    elif change == "definition":
        definition["model"]["temperature_K"] = 310.15
    elif change == "voltage":
        result["after_voltage_V"][0] = 0.03
    elif change == "charge":
        result["countercharge_C"] = 1e-10
    elif change == "initial_history":
        result["initial_state"]["gate"][0][0] = 0.5
    else:
        result["after_inside_amount_fmol"][1][0] = 123
    ledger = check.Ledger(p)
    g = native["preparations"]["active_channel"]["geometry"]
    flux = check.scale(t.cell_sums(row["channel_after"]["density_mol_per_m2_s"], g), 1e15)
    try:
        check.cells_case(
            p, base, p["variants"][3], g, row, definition, result, "numpy", ledger, flux
        )
    except ValueError:
        return
    assert any(not r["passed"] for r in ledger.rows)


@pytest.mark.parametrize("value,shape", [(True, []), (float("nan"), []), ([1], [2]), ([[1]], [1])])
def test_nonfinite_boolean_and_shape_rejected(value, shape):
    with pytest.raises(ValueError):
        check.shape_finite(value, shape, "test")


def test_reference_imports_no_models():
    script = (
        f"import sys; sys.path.insert(0, {str(HERE)!r}); import transport_check, transport_job; "
        "assert not any(n.split('.')[0] in {'cells','betse','numpy','jax','jaxlib'} "
        "for n in sys.modules)"
    )
    subprocess.run([sys.executable, "-B", "-c", script], check=True, timeout=5)


def test_workers_have_no_simulation_driver_or_upstream_patch():
    tree = ast.parse((HERE / "transport_workers.py").read_text())
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {
        "run_sim",
        "run_sim_core",
        "_run_sim_core",
        "_plot_loop",
        "settrace",
        "setprofile",
    }
    assert {
        "seed",
        "init_core",
        "init_dynamics",
        "run_loop_channels",
        "run_loop",
        "update_all_concs",
        "update_V",
        "rhs",
        "channel_readouts",
    } <= calls
    vg = (c.SOURCE / "betse/science/channels/vg_k.py").read_text()
    assert "self._mpower = 1" in vg and "self._hpower = 1" in vg


def test_preservation_and_prerequisite():
    assert job.prior_closeout()["isolated_gate_qualified"]
    preserved = c.authenticate_cells()
    assert len(preserved["implementation_files_sha256"]) == 352
    assert len(list((c.ROOT / "src/cells").rglob("*.py"))) == 51


def test_write_is_exclusive(tmp_path):
    path = tmp_path / "result.json"
    c.write(path, {"preserved": True})
    with pytest.raises(FileExistsError):
        c.write(path, {"preserved": False})
    assert c.read(path) == {"preserved": True}


def test_timeout_handler():
    with pytest.raises(TimeoutError, match="wall-clock"):
        job.alarm(None, None)


def test_registration_refuses_existing_directory(tmp_path):
    with pytest.raises(ValueError, match="fresh run"):
        job.register(tmp_path, tmp_path / "tests.xml")


def test_resources_are_prospective_and_bounded(registration):
    resources = registration["protocol"]["resources"]
    assert resources["total_timeout_seconds"] == 300
    assert resources["max_artifact_bytes"] == 128 * 1024**2
    assert resources["cpu_affinity"] == [0, 1, 2, 3]
    assert len(t.case_ids(registration["protocol"])) == 12


def test_execution_failure_is_durable_without_worker_or_retry(tmp_path):
    # The fresh directory deliberately lacks registration. This child never
    # imports a simulator; its process-local resource limits cannot affect pytest.
    result = subprocess.run(
        [sys.executable, "-B", str(HERE / "transport_job.py"), "execute", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    failure = c.read(tmp_path / "failure.json")
    assert failure["status"] == "failed_not_qualified" and not failure["automatic_retry"]
    assert "registration.json" in failure["traceback"]
    assert not (tmp_path / "completion.json").exists()
    assert not (tmp_path / "betse.log").exists()


@pytest.mark.parametrize("mutation", ["missing_backend", "missing_case", "extra_case"])
def test_missing_coverage_cannot_pass(registration, native, mapped, mutation):
    broken = copy.deepcopy(mapped)
    if mutation == "missing_backend":
        del broken["results"]["jax_jit"]
    elif mutation == "missing_case":
        broken["results"]["jax_eager"].pop("active_channel/native_initial")
    else:
        broken["definitions"]["extra"] = {}
    with pytest.raises(ValueError):
        check.evaluate(registration, native, broken)


def test_units_and_native_single_step_at_nonzero_voltage():
    target, tau, after = t.gate_reference(-0.060, [0.2, 0.6], 25e-6)
    assert target[0] == pytest.approx(1 / (1 + math.exp(54 / 6.4)), rel=1e-14)
    assert target[1] == pytest.approx(1 / (1 + math.exp(-34.7 / 3.5)), rel=1e-14)
    assert tau == pytest.approx([0.015308, 2.55], rel=1e-14)
    assert after[0] == pytest.approx((tau[0] * 0.2 + 25e-6 * target[0]) / (tau[0] + 25e-6))
    assert after[1] == pytest.approx((tau[1] * 0.6 + 25e-6 * target[1]) / (tau[1] + 25e-6))
