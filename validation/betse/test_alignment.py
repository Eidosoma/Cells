"""Synthetic checker tests only; these records are not executed BETSE evidence."""

import copy
import math
from pathlib import Path

import alignment as a
import contact as c
import pytest


def synthetic():
    p = c.read(a.PROTOCOL)
    g = {
        "cell_count": 1,
        "membrane_count": 6,
        "cell_volume_m3": 1e-15,
        "cell_area_m2": 6e-10,
        "membrane_areas_m2": [1e-10] * 6,
        "membrane_owners": [0] * 6,
        "diviterm_m": 1e-15 / 6e-10,
        "configured_bath_volume_m3": 2.5e-16,
        "effective_bath_volume_m3": 6 * 2.5e-16,
        "specific_capacitance_F_per_m2": 0.01,
        "capacitance_F": 6e-10 * 0.01,
        "grid_shape": [10, 10],
    }
    settings = {
        "is_ecm": False,
        "cell_polarizability": 0.0,
        "cluster_open": True,
        "alpha_NaK": 0.0,
        "alpha_Ca": 0.0,
        "Ca_dyn": False,
        "molecules_enabled": False,
        "grn_enabled": False,
        "fluid_flow": False,
        "deformation": False,
        "deform_osmo": False,
        "dynamic_noise": False,
        "channel_noise_level": 0.0,
        "v_sensitive_gj": False,
        "solver": "FULL",
        "temperature_K": 310.15,
        "thickness_m": 7.5e-9,
    }
    native = {
        "engine": "native_betse_seed_init_and_prescribed_updates",
        "geometry": g,
        "settings": settings,
        "profiles": {},
        "trajectory_run": False,
    }
    local = {
        "engine": "unchanged_cells_finite_extracellular_rhs",
        "definition": a.cells_definition(p, g),
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "trajectory_run": False,
        "results": {},
    }
    vi, vo = g["cell_volume_m3"] / 1e-15, g["effective_bath_volume_m3"] / 1e-15
    for profile, constants in p["profiles"].items():

        def snapshot(delta, density=None, constants=constants):
            delta = [*delta, *([0.0] * (6 - len(delta)))]
            q = (
                constants["F"]
                * 1e-15
                * math.fsum(z * n for z, n in zip(p["expected_valence"], delta, strict=True))
            )
            current = (
                [0.0] * 6
                if density is None
                else [
                    constants["F"]
                    * g["membrane_areas_m2"][j]
                    * math.fsum(
                        z * row[j] for z, row in zip(p["expected_valence"], density, strict=True)
                    )
                    for j in range(6)
                ]
            )
            return {
                "inside_mM": [v + d / vi for v, d in zip(p["inside_mM"], delta, strict=True)],
                "outside_mM": [
                    [v - d / vo] * 6 for v, d in zip(p["outside_mM"], delta, strict=True)
                ],
                "voltage_V": [q / g["capacitance_F"]] * 6,
                "charge_density_C_per_m3": [q / g["cell_volume_m3"]],
                "inward_current_A": current,
                "boundary_voltage_V": [0.0] * 100,
            }

        probes, local_rows = [], []
        for case in p["transfer_probes"]:
            delta = case["inward_amount_fmol"]
            before = snapshot(delta)
            rates = [
                c.oracle(
                    {
                        "inside_mM": before["inside_mM"][i],
                        "outside_mM": before["outside_mM"][i][0],
                        "valence": z,
                        "voltage_V": before["voltage_V"][0],
                        "temperature_K": 310.15,
                        "area_m2": g["cell_area_m2"],
                        "permeability_m_per_s": p["permeability_m_per_s"][i],
                    },
                    constants,
                )
                for i, z in enumerate(p["expected_valence"])
            ]
            density = [[rate * 1e-15 / g["cell_area_m2"]] * 6 for rate in rates]
            after = snapshot(
                [d + f * p["dt_s"] for d, f in zip([*delta, 0, 0, 0], rates, strict=True)], density
            )
            probes.append(
                {
                    "id": case["id"],
                    "before": before,
                    "after": after,
                    "density_mol_per_m2_s": density,
                }
            )
            local_rows.append(
                {
                    "id": case["id"],
                    "voltage_V": before["voltage_V"][0],
                    "inside_rate_fmol_per_s": rates[:3],
                    "outside_rate_fmol_per_s": [-f for f in rates[:3]],
                }
            )
        footprints = []
        for name in p["footprint_probes"]:
            density = a.footprint(
                name, g["membrane_areas_m2"], p["prescribed_density_mol_per_m2_s"]
            )
            amount = (
                math.fsum(f * ar for f, ar in zip(density, g["membrane_areas_m2"], strict=True))
                * p["dt_s"]
                / 1e-15
            )
            footprints.append(
                {
                    "id": name,
                    "density_mol_per_m2_s": density,
                    "before": snapshot([0, 0, 0]),
                    "after": snapshot([amount, 0, 0], [density] + [[0] * 6] * 5),
                }
            )
        labels = [i * 10 * p["dt_s"] / 9 for i in range(10)]
        native["profiles"][profile] = {
            "constants": constants,
            "dt_s": p["dt_s"],
            "species": p["expected_species"],
            "valence": p["expected_valence"],
            "permeability_m_per_s": [[v] * 6 for v in p["permeability_m_per_s"]],
            "initial": snapshot([0, 0, 0]),
            "probes": probes,
            "footprints": footprints,
            "clock": {
                "native_labels_s": labels,
                "sampled_labels_s": labels[1:],
                "sampled_indices": list(range(1, 10)),
            },
        }
        if profile == "matched_constants":
            local["results"] = {backend: copy.deepcopy(local_rows) for backend in c.CELLS_BACKENDS}
    return {"protocol": p}, native, local


def test_synthetic_checker_passes_and_exposes_bath_normalization():
    result = a.check(*synthetic())
    assert result["status"] == "pass"
    assert result["effective_bath_volume_multiplier"] == 6
    assert all(abs(v) > 1e-7 for v in result["configured_bath_volume_mass_residual_fmol"])
    assert result["trajectory_run"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("geometry", "effective_bath_volume_m3"), 2.5e-16),
        (("geometry", "membrane_owners"), [0, 1, 0, 0, 0, 0]),
        (("geometry", "cell_area_m2"), 6e-9),
        (("geometry", "diviterm_m"), 1),
        (("geometry", "capacitance_F"), 1),
        (("geometry", "cell_volume_m3"), float("nan")),
        (("settings", "cell_polarizability"), 1.0),
        (("settings", "is_ecm"), True),
        (("settings", "alpha_NaK"), 1e-7),
        (("settings", "solver"), "FAST"),
        (("profiles", "matched_constants", "constants", "F"), 96485.0),
        (("profiles", "source_constants", "initial", "inside_mM", 5), 41),
        (("profiles", "source_constants", "initial", "voltage_V", 0), -0.04),
        (("profiles", "source_constants", "probes", 1, "before", "voltage_V", 0), -0.016),
        (("profiles", "source_constants", "probes", 1, "after", "outside_mM", 0, 0), 145),
        (("profiles", "source_constants", "probes", 0, "density_mol_per_m2_s", 3, 0), 1e-8),
        (("profiles", "source_constants", "initial", "boundary_voltage_V", 0), 0.001),
        (("profiles", "source_constants", "footprints", 0, "density_mol_per_m2_s", 0), 0),
        (("profiles", "source_constants", "clock", "sampled_indices"), list(range(10))),
        (("trajectory_run",), True),
    ],
)
def test_rejects_changed_native_records(path, value):
    registration, native, local = synthetic()
    target = native
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    try:
        result = a.check(registration, native, local)
    except ValueError:
        return
    assert result["status"] == "failed"


@pytest.mark.parametrize(
    "path,value",
    [
        (("results", "jax_jit", 0, "inside_rate_fmol_per_s", 0), -1),
        (("results", "jax_eager", 0, "outside_rate_fmol_per_s", 0), 0),
        (("results", "numpy", 1, "voltage_V"), 0),
        (("definition", "model", "extracellular", "volume_pL"), 1),
        (("definition", "model", "cells", 0, "cell", "fixed_charge_equivalent_fmol"), -141),
        (("device",), "gpu"),
        (("x64_enabled",), False),
        (("jit_disabled",), True),
    ],
)
def test_rejects_changed_cells_records(path, value):
    registration, native, local = synthetic()
    target = local
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    try:
        result = a.check(registration, native, local)
    except ValueError:
        return
    assert result["status"] == "failed"


def test_mapping_freezes_charge_explicitly_without_mutating_inputs():
    registration, native, _ = synthetic()
    before = copy.deepcopy((registration, native))
    config = a.cells_definition(registration["protocol"], native["geometry"])
    assert (registration, native) == before
    assert config["model"]["cells"][0]["cell"]["fixed_charge_equivalent_fmol"] == -142
    assert config["model"]["cells"][0]["membrane"]["pump"] is None
    assert config["model"]["cells"][0]["channel"] is None


def test_unknown_yaml_setting_is_not_silently_added():
    with pytest.raises(ValueError, match="Unknown YAML"):
        a.configuration({"a": {}}, {"yaml_overrides": [(["a", "missing"], 1)]})


@pytest.mark.parametrize("asset", ["geo/root/root_cells.svg", "extra_configs/expression_data.yaml"])
def test_source_asset_paths_are_relative_to_generated_configuration(tmp_path, asset):
    base = {"asset": asset, "outputs": "INITS"}
    conf = a.configuration(base, {"yaml_overrides": []}, tmp_path)
    assert not Path(conf["asset"]).is_absolute()
    assert (tmp_path / conf["asset"]).resolve() == c.SOURCE / "betse/data/yaml" / asset
    assert conf["outputs"] == "INITS" and base["asset"] == asset


def test_footprint_balances_unequal_faces():
    areas = [1e-10, 2e-10, 3e-10]
    values = a.footprint("balanced_faces", areas, 1e-7)
    assert math.fsum(v * ar for v, ar in zip(values, areas, strict=True)) == 0
    with pytest.raises(ValueError):
        a.footprint("invented", areas, 1)


@pytest.mark.parametrize("count", [0, 2, 7])
def test_one_cell_guard_rejects_actual_geometry_mismatch(count):
    with pytest.raises(ValueError, match="Requested one cell"):
        a.require_one_cell(
            {
                "requested_single_cell": True,
                "cell_count": count,
                "membrane_count": 6,
                "molecules_enabled": False,
            }
        )


def test_one_cell_guard_requires_disabled_network():
    values = {
        "requested_single_cell": True,
        "cell_count": 1,
        "membrane_count": 6,
        "molecules_enabled": True,
    }
    with pytest.raises(ValueError, match="network"):
        a.require_one_cell(values)
    values["molecules_enabled"] = False
    a.require_one_cell(values)
