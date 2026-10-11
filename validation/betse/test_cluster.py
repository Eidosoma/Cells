"""Synthetic comparator checks; not native BETSE evidence."""

import copy
import math

import alignment as a
import cluster_alignment as cluster
import contact as c
import pytest
from cluster_check import check


def synthetic():
    p, b = c.read(cluster.PROTOCOL), c.read(a.PROTOCOL)
    owners = [i for i in range(6) for _ in range(4)] + [6] * 6
    areas = [1e-10 * (1 + (j % 4) / 10) for j in range(30)]
    cell_areas = [
        math.fsum(ar for ar, owner in zip(areas, owners, strict=True) if owner == i)
        for i in range(7)
    ]
    volumes = [5e-16] * 6 + [8e-16]
    g = {
        "cell_count": 7,
        "membrane_count": 30,
        "cell_centres_m": [[i * 1e-5, 0.0] for i in range(7)],
        "cell_volumes_m3": volumes,
        "cell_areas_m2": cell_areas,
        "membrane_owners": owners,
        "membrane_areas_m2": areas,
        "diviterm_m": [v / ar for v, ar in zip(volumes, cell_areas, strict=True)],
        "specific_capacitance_F_per_m2": 0.01,
        "configured_bath_volume_m3": 0.001 * 0.00015**2 * 0.00001,
        "grid_shape": [10, 10],
    }
    g["effective_bath_volume_m3"] = 30 * g["configured_bath_volume_m3"]
    registered = {
        "protocol": p,
        "base_protocol": b,
        "expected_geometry": {key: g[key] for key in cluster.GEOMETRY_FIELDS},
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
        "gj_surface": 0.0,
        "solver": "FULL",
        "temperature_K": 310.15,
    }
    native = {
        "engine": "native_betse_seven_cell_prescribed_updates",
        "geometry": g,
        "settings": settings,
        "warnings": [],
        "profiles": {},
        "trajectory_run": False,
    }
    mapped = cluster.definition(b, p, g)
    local = {
        "engine": "unchanged_cells_finite_extracellular_rhs",
        "definition": mapped,
        "probe_definitions": {
            case["id"]: cluster.probe_definition(mapped, case, p, b, g) for case in p["cases"]
        },
        "results": {},
        "warnings": [],
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "trajectory_run": False,
    }
    vi, vo = [v / 1e-15 for v in volumes], g["effective_bath_volume_m3"] / 1e-15
    zero = [[0.0] * 7 for _ in range(6)]
    for name, constants in b["profiles"].items():

        def snapshot(delta, density=None, constants=constants):
            q = [
                constants["F"]
                * 1e-15
                * math.fsum(z * delta[s][i] for s, z in enumerate(b["expected_valence"]))
                for i in range(7)
            ]
            voltage = [q[i] / (cell_areas[i] * 0.01) for i in range(7)]
            return {
                "inside_mM": [
                    [b["inside_mM"][s] + delta[s][i] / vi[i] for i in range(7)] for s in range(6)
                ],
                "outside_mM": [
                    [b["outside_mM"][s] - math.fsum(delta[s]) / vo] * 30 for s in range(6)
                ],
                "voltage_V": [voltage[owner] for owner in owners],
                "rho_C_per_m3": [q[i] / volumes[i] for i in range(7)],
                "inward_current_A": [0.0] * 30
                if density is None
                else [
                    constants["F"]
                    * ar
                    * math.fsum(z * density[s][j] for s, z in enumerate(b["expected_valence"]))
                    for j, ar in enumerate(areas)
                ],
                "boundary_voltage_V": [0.0] * 100,
            }

        def after(delta, density):
            rates = [
                [
                    math.fsum(
                        density[s][j] * ar
                        for j, (ar, owner) in enumerate(zip(areas, owners, strict=True))
                        if owner == i
                    )
                    / 1e-15
                    for i in range(7)
                ]
                for s in range(6)
            ]
            return [
                [delta[s][i] + rate * b["dt_s"] for i, rate in enumerate(row)]
                for s, row in enumerate(rates)
            ], rates

        saved_cases, local_rows = [], []
        for case in p["cases"]:
            delta = cluster.transfers(case, p) + copy.deepcopy(zero[:3])
            before = snapshot(delta)
            density = [
                [
                    c.oracle(
                        {
                            "inside_mM": before["inside_mM"][s][owner],
                            "outside_mM": before["outside_mM"][s][j],
                            "valence": z,
                            "voltage_V": before["voltage_V"][j],
                            "temperature_K": 310.15,
                            "area_m2": areas[j],
                            "permeability_m_per_s": b["permeability_m_per_s"][s]
                            * case["leak_multiplier"],
                        },
                        constants,
                    )
                    * 1e-15
                    / areas[j]
                    for j, owner in enumerate(owners)
                ]
                for s, z in enumerate(b["expected_valence"])
            ]
            after_delta, rates = after(delta, density)
            saved_cases.append(
                {
                    "id": case["id"],
                    "before": before,
                    "after": snapshot(after_delta, density),
                    "density_mol_per_m2_s": density,
                    "junction_density_mol_per_m2_s": [[0.0] * 30 for _ in range(6)],
                }
            )
            voltage = [before["voltage_V"][owners.index(i)] for i in range(7)]
            local_rows.append(
                {
                    "id": case["id"],
                    "voltage_V": voltage,
                    "increment_voltage_V": voltage,
                    "inside_rate_fmol_per_s": rates[:3],
                    "outside_rate_fmol_per_s": [-math.fsum(row) for row in rates[:3]],
                    "valid_domain": True,
                    "inactive_slots_zero": True,
                }
            )
        footprints = []
        for kind in p["footprints"]:
            density = [a.footprint(kind, areas, b["prescribed_density_mol_per_m2_s"])] + [
                [0.0] * 30 for _ in range(5)
            ]
            delta, _ = after(zero, density)
            footprints.append(
                {
                    "id": kind,
                    "before": snapshot(zero),
                    "after": snapshot(delta, density),
                    "density_mol_per_m2_s": density,
                }
            )
        native["profiles"][name] = {
            "constants": constants,
            "dt_s": b["dt_s"],
            "species": b["expected_species"],
            "valence": b["expected_valence"],
            "initial": snapshot(zero),
            "cases": saved_cases,
            "footprints": footprints,
            "permeability_m_per_s": [[v] * 30 for v in b["permeability_m_per_s"]],
            "clock": {
                "labels_s": [i * 10 * b["dt_s"] / 9 for i in range(10)],
                "sampled_indices": list(range(1, 10)),
            },
        }
        if name == "matched_constants":
            local["results"] = {backend: copy.deepcopy(local_rows) for backend in c.CELLS_BACKENDS}
    return registered, native, local


def test_synthetic_cluster_comparison():
    result = check(*synthetic())
    assert result["status"] == "pass" and result["cell_count"] == 7
    assert all(abs(v) > 1e-6 for v in result["configured_volume_mass_residual_fmol"])


@pytest.mark.parametrize(
    "path,value",
    [
        (("geometry", "cell_count"), 1),
        (("geometry", "effective_bath_volume_m3"), 2.25e-16),
        (("geometry", "diviterm_m", 0), 1.0),
        (("settings", "cell_polarizability"), 1.0),
        (("settings", "alpha_NaK"), 1e-7),
        (("settings", "gj_surface"), 5e-8),
        (("profiles", "matched_constants", "cases", 1, "before", "voltage_V", 29), 0.0),
        (("profiles", "matched_constants", "cases", 0, "after", "outside_mM", 0, 0), 145.0),
        (("profiles", "source_constants", "cases", 0, "junction_density_mol_per_m2_s", 0, 0), 1e-8),
        (("profiles", "source_constants", "cases", 0, "density_mol_per_m2_s", 3, 0), 1e-8),
        (("profiles", "source_constants", "footprints", 0, "density_mol_per_m2_s", 0, 0), 0),
        (("profiles", "source_constants", "clock", "sampled_indices"), list(range(10))),
        (("warnings",), [{"category": "RuntimeWarning", "message": "invalid divide"}]),
    ],
)
def test_rejects_native_corruptions(path, value):
    r, native, local = synthetic()
    target = native
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    try:
        result = check(r, native, local)
    except ValueError:
        return
    assert result["status"] == "failed"


@pytest.mark.parametrize(
    "path,value",
    [
        (("results", "jax_jit", 0, "inside_rate_fmol_per_s", 0, 0), -1),
        (("results", "numpy", 0, "outside_rate_fmol_per_s", 0), 0),
        (("results", "jax_eager", 1, "increment_voltage_V", 6), 0),
        (("results", "numpy", 1, "inactive_slots_zero"), False),
        (("definition", "model", "cells", 1, "cell", "id"), "cell_0"),
        (("probe_definitions", "neutral_initial", "model", "extracellular", "volume_pL"), 1.0),
        (("device",), "gpu"),
        (("jit_disabled",), True),
        (("x64_enabled",), False),
    ],
)
def test_rejects_cells_corruptions(path, value):
    r, native, local = synthetic()
    target = local
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    try:
        result = check(r, native, local)
    except ValueError:
        return
    assert result["status"] == "failed"


def test_preparations_are_new_valid_initial_states_not_invented_histories():
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    _, _, local = synthetic()
    for definition in local["probe_definitions"].values():
        spec = parse_spec(definition)
        assert spec.to_dict() == definition
        state, _ = model.initial_values(spec)
        model.check_values(state, spec)
        assert not any(v.any() for v in state)


def test_duplicate_or_invalid_transfer_owners_rejected():
    p = c.read(cluster.PROTOCOL)
    for values in ([["Na", 7, 0.1]], [["Na", 0, 0.1], ["Na", 0, 0.2]], [["unknown", 0, 0.1]]):
        with pytest.raises(ValueError):
            cluster.transfers({"transfers": values, "leak_multiplier": 1.0}, p)
