"""Explicit manufactured supplied owners for deferred source-conditional checks.

Fixture CODE only during worker preparation. Chief may evaluate it in an
explicitly requested round. Existing supplied macro geometry is reused; no seed,
profile picker, native mesh, native whole initialization or hidden defaults.
"""

import copy
import hashlib
import json
import random

import numpy as np

from cells.processes import betse_ecm_transport as material
from cells.processes import betse_perturbations as perturbations
from validation.betse.betse_normal_ecm_catalog_join_fixtures import fixture as catalog_fixture

CASES = (
    "combined",
    "salt_order",
    "temperature",
    "GJ_override",
    "NaK_shape",
    "membrane_four",
    "ecmJ",
    "periodic",
    "sweep",
    "voltage_same_edge",
    "profile_duplicate",
    "static_K_reset",
    "noise_zero_level",
    "noise_disabled",
    "no_events",
    "no_channel",
    "no_CaATP",
    "rectangular",
    "fast_duplicate",
    "moving_P_noise",
)
COMPONENT_CONTROLS = (
    "static_K_reset",
    "noise_zero_level",
    "noise_disabled",
    "no_events",
    "no_channel",
    "no_CaATP",
)
RAW_CASES = (
    "zero_global_pulse_width",
    "radial_pressure_shape",
    "negative_Dm_source_return",
    "protein_noise_large_limit",
    "GRN_refuses_before_noise",
    "late_negative_temperature",
)
DEPENDENCIES = (
    "missing_owner",
    "changed_geometry_owner",
    "mismatched_environment_targets",
    "missing_M_role",
    "wrong_RNG_version",
    "missing_Gaussian_cache",
    "changed_noise_cache",
    "changed_event_store",
    "competing_control_override",
    "cut_requested",
    "bitmap_unowned",
    "inconsistent_time_callbacks",
    "wrong_scalar_callback",
    "missing_field",
    "wrong_clock",
    "missing_network_cache",
)


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: plain(v) for key, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def document_hash(value):
    return hashlib.sha256(
        json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def finalize_fields(global_options, scheduled, maps, m):
    # Exact source reader field assignments, without invoking its constructor,
    # choosing profiles or consuming a hidden stream. Owners/maps are supplied.
    fields = {}
    for key, suffix in (("K_env", "Kenv"), ("Cl_env", "Clenv"), ("Na_env", "Naenv")):
        row = global_options[key]
        if row != 0:
            for stem, value in zip(("t_on_", "t_off_", "t_change_", "mem_mult_"), row, strict=True):
                fields[stem + suffix] = value
    for key, names in (
        ("T_change", ("tonT", "toffT", "trampT", "multT")),
        ("gj_block", ("tonGJ", "toffGJ", "trampGJ")),
        ("NaKATP_block", ("tonNK", "toffNK", "trampNK")),
    ):
        row = global_options[key]
        if row != 0:
            fields.update(zip(names, row, strict=False))
            if key == "gj_block":
                fields["targets_gj_block"] = list(
                    range(int((min(100, max(1, int(row[3]))) / 100) * m))
                )
    for key, suffix in (
        ("Na_mem", "Namem"),
        ("K_mem", "Kmem"),
        ("Cl_mem", "Clmem"),
        ("Ca_mem", "Camem"),
        ("pressure", "P"),
    ):
        row = scheduled[key]
        if row == 0:
            continue
        domain = "cell_target_inds" if key == "pressure" else "tissue_target_inds"
        target = [i for name in row[4] for i in maps[domain][name]]
        if key == "pressure":
            fields.update(
                dict(zip(("t_onP", "t_offP", "t_changeP", "rate_P"), row[:4], strict=True))
            )
        else:
            for stem, value in zip(
                ("t_on_", "t_off_", "t_change_", "mem_mult_"), row[:4], strict=True
            ):
                fields[stem + suffix] = value
        fields["targets_" + suffix] = target
        fields["apply_" + suffix] = row[4]
        fields["function_" + suffix] = row[5]
    row = scheduled["ecmJ"]
    if row != 0:
        fields.update(dict(zip(("t_on_ecmJ", "t_off_ecmJ", "t_change_ecmJ"), row[:3], strict=True)))
        fields.update(
            apply_ecmJ=row[3],
            mult_ecmJ=row[4],
            targets_ecmJ=[i for name in row[3] for i in maps["env_target_inds"][name]],
        )
    return fields


def rebuild_owner(data):
    owner = data["event_owner"]
    m = len(owner["owners"]["membrane_ids"])
    owner["handler_fields"] = finalize_fields(
        owner["global_options"], owner["scheduled_options"], owner, m
    )


def fixture(case="combined"):
    if case not in CASES:
        raise ValueError("Choose a declared supplied-owner ECM event history")
    data = catalog_fixture(
        case if case in ("rectangular", "fast_duplicate", "no_CaATP") else "mixed_forward"
    )
    field = data["field"]
    definition = field["definition"]
    external = definition["environment_geometry_definition"]
    cd = external["current_definition"]
    cg = cd["geometry"]
    ids = cd["ions"]["ids"]
    n, m, e = len(cg["cell_ids"]), len(cg["owner"]), len(field["initial"]["environment_mol_m3"][0])
    ids.append("M")
    cd["ions"]["valence"].append(-1.0)
    definition["ions"]["moving_ids"].append("M")
    if case == "moving_P_noise":
        definition["ions"]["moving_ids"].append("P")
    for key, row in (
        ("membrane_diffusion_m2_s", [4e-6] * m),
        ("gap_diffusion_m2_s", [4e-5] * m),
        ("environment_diffusion_m2_s", [1e-3] * e),
        ("tight_junction_modulator", [0.6] * e),
    ):
        definition["ions"][key].append(row)
    for key, size, value in (
        ("cell_mol_m3", n, 1e-3),
        ("membrane_mol_m3", m, 1e-3),
        ("environment_mol_m3", e, 1e-3),
        ("membrane_flux_mol_m2_s", m, 2e-7),
        ("junction_flux_mol_m2_s", m, -3e-7),
        ("environment_flux_x_mol_m2_s", e, 1e-6),
        ("environment_flux_y_mol_m2_s", e, -1e-6),
    ):
        field["initial"][key].append([value] * size)
    pi, mi = ids.index("P"), ids.index("M")
    for key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
        rows = field["initial"][key]
        rows[pi] = [a - b for a, b in zip(rows[pi], rows[mi], strict=True)]
    for call in field["steps"]:
        p = call["material"]
        p["boundary_mol_m3"].append(1e-3)
        p["supplied_pump_membrane_flux_mol_m2_s"].append([0.0] * m)
        p["supplied_late_membrane_flux_mol_m2_s"].append([0.0] * m)
    default_dm = dict(Dm_Na=1e-5, Dm_K=1.1e-5, Dm_Cl=1.2e-5, Dm_Ca=1.4e-5, Dm_M=4e-6, Dm_P=1.3e-5)
    base_dm = [[default_dm["Dm_" + name]] * m for name in ids]
    definition["ions"]["membrane_diffusion_m2_s"] = copy.deepcopy(base_dm)
    live_dm = copy.deepcopy(base_dm)
    stream = perturbations.native_stream(12345)
    if case == "static_K_reset":
        # Explicit bounded source-site preparation evidence, not a complete
        # native initializer history. This runs only in a requested test round.
        rng = np.random.RandomState(0)
        before = copy.deepcopy(rng.get_state())
        uniforms = rng.random(m)
        after = copy.deepcopy(rng.get_state())
        live_dm[ids.index("K")] = (
            (0.15 * uniforms + 1) * np.asarray(base_dm[ids.index("K")])
        ).tolist()
        definition["ions"]["membrane_diffusion_m2_s"] = copy.deepcopy(live_dm)
        field["input_recipe"]["supplied_static_K_source_site"] = dict(
            level=0.15,
            uniforms=uniforms.tolist(),
            before=plain(before),
            after=plain(after),
            whole_native_initialization_claim=False,
        )
    external["cache_initial_state"] = dict(
        cell_mol_m3=copy.deepcopy(field["initial"]["cell_mol_m3"]),
        environment_mol_m3=copy.deepcopy(field["initial"]["environment_mol_m3"]),
        free_diffusion_m2_s=[1e-9] * len(ids),
    )
    # Existing geometry binder consumes the explicit already supplied geometry;
    # no mesh/seed or picker is called. Derived maps are returned as owner inputs.
    mb = material.bind(definition)
    g = mb.geometry_binding.geometry
    cells = list(cg["cell_ids"])
    membranes = list(cg["membrane_ids"])
    environment = ["ecm_slot_" + str(j) for j in range(e)]
    maps = dict(
        tissue_target_inds=dict(
            all=list(range(m)), region0=[j for j, a in enumerate(cg["owner"]) if a == 0]
        ),
        cell_target_inds=dict(all=list(range(n)), region0=[0]),
    )
    maps["env_target_inds"] = {
        name: [int(g.membrane_to_grid[j]) for j in indices]
        for name, indices in maps["tissue_target_inds"].items()
    }
    data["catalog"]["tissue_profiles"] = copy.deepcopy(maps["tissue_target_inds"])
    if case == "profile_duplicate":
        data["catalog"]["populations"][0]["apply to"] = ["region0", "region0", "all"]
    if case == "no_channel":
        data["catalog"]["populations"] = None
    dt = field["bootstrap"]["dt_s"]
    on, off, width = 0.5 * dt, 2.0 * dt, 0.7 * dt
    glob = dict.fromkeys(("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block"), 0)
    scheduled = dict.fromkeys(("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ"), 0)
    callbacks = {}
    combined = case in (
        "combined",
        "GJ_override",
        "NaK_shape",
        "rectangular",
        "fast_duplicate",
        "no_channel",
        "no_CaATP",
        "moving_P_noise",
    )
    if combined or case == "salt_order":
        for key, amp in (("K_env", 0.02), ("Cl_env", 0.015), ("Na_env", 0.01)):
            glob[key] = [on, off, width, amp]
    if combined or case == "temperature":
        glob["T_change"] = [on, off, width, 0.01]
    if combined or case == "GJ_override":
        glob["gj_block"] = [on, off, width, 100]
    if combined or case == "NaK_shape":
        glob["NaKATP_block"] = [on, off, width]
    selected = ["region0", "region0", "all"] if case == "profile_duplicate" else ["all"]
    if combined or case in ("membrane_four", "periodic", "sweep", "profile_duplicate"):
        for key, suffix in (
            ("Na_mem", "Namem"),
            ("K_mem", "Kmem"),
            ("Cl_mem", "Clmem"),
            ("Ca_mem", "Camem"),
        ):
            function = (
                "periodic" if case == "periodic" else "f_sweep" if case == "sweep" else "None"
            )
            scheduled[key] = [on, off, width, 0.15, selected, function]
            dynamic = (
                dict(
                    kind="periodic",
                    frequency=2500.0,
                    phase=0.2,
                    provenance="Explicit source phase-wide periodic properties",
                )
                if function == "periodic"
                else dict(
                    kind="sweep",
                    start=500.0,
                    slope=1e7,
                    provenance="Explicit finalized source sweep slope",
                )
                if function == "f_sweep"
                else dict(kind="constant")
            )
            callbacks[suffix] = dict(
                source_function=function,
                source_scalar=1,
                dynamic=dynamic,
                provenance="Explicit supplied finalized native scalar/time callback",
            )
    if combined:
        scheduled["pressure"] = [on, off, width, 1e-6, ["region0"], "None"]
        callbacks["P"] = dict(
            source_function="None",
            source_scalar=1,
            dynamic=dict(kind="constant"),
            provenance="Source scalar-one pressure callback; mechanics excluded",
        )
    if combined or case == "ecmJ":
        scheduled["ecmJ"] = [on, off, width, selected, 0.2]
    voltage = None
    if combined or case == "voltage_same_edge":
        voltage = dict(
            start_time_step=on,
            stop_time_step=off,
            time_step_rate=width,
            peak_voltage=0.003,
            positive_voltage_boundary="R",
            negative_voltage_boundary="R" if case == "voltage_same_edge" else "L",
        )
    configured = {name: field["initial"]["environment_mol_m3"][i][0] for i, name in enumerate(ids)}
    bounds = copy.deepcopy(field["bootstrap"]["boundary_V"])
    entryT = external["parameters"]["configured_temperature_K"]
    gj = [1.0] * m if glob["gj_block"] != 0 else 1.0
    nk = [1.0] * m if glob["NaKATP_block"] != 0 else 1.0
    weights = np.asarray(
        definition["ions"]["environment_diffusion_m2_s"][ids.index("Na")], np.float64
    )
    weights = (weights / weights.max()).reshape(g.shape)
    entry = dict(
        T=entryT,
        c_env_bound=[configured[name] for name in ids],
        gj_block=gj,
        NaKATP_block=nk,
        rho_channel=1.0,
        bound_V=bounds,
        Dm_base=base_dm,
        Dm_scheduled=[[0.0] * m for _ in ids],
        Dm_cells=live_dm,
        D_env_base=copy.deepcopy(definition["ions"]["environment_diffusion_m2_s"]),
        D_env=copy.deepcopy(definition["ions"]["environment_diffusion_m2_s"]),
        D_env_weight_base=weights.tolist(),
        D_env_weight=weights.tolist(),
        D_free=[1e-9] * len(ids),
        P_base=[0.0] * n,
        P_mod=[0.0] * n,
        P_cells=[0.0] * n,
    )
    field["network"]["initial_controls"] = dict(gj_block=[1.0] * m, NaKATP_block=[1.0] * m)
    field["network"]["initial_ion_boundary"] = entry["c_env_bound"].copy()
    if case == "NaK_shape":
        field["network"]["configuration"]["modulators"] = None
    for call in field["steps"]:
        call["scheduled_controls"] = None
        call["boundary_V"] = copy.deepcopy(bounds)
        call["material"].update(
            runtime_temperature_K=entryT,
            boundary_mol_m3=entry["c_env_bound"].copy(),
            junction_block=[1.0] * m,
            channel_multiplier=[1.0] * m,
        )
    owner = dict(
        kind="cells.supplied_finalized_native_tissue_event_owner@1",
        provenance=(
            "Manufactured explicit supplied post-finalization owner on existing "
            "source-conditional macro geometry; no profile picker/mesh/history inference"
        ),
        geometry_declaration_sha256=document_hash(external),
        owners=dict(
            cell_ids=cells,
            membrane_ids=membranes,
            environment_ids=environment,
            membrane_cell_ids=[cells[j] for j in cg["owner"]],
            membrane_environment_ids=[environment[j] for j in g.membrane_to_grid],
            boundary_cell_occurrences=[cells[j] for j in range(n)],
        ),
        handler_fields={},
        tissue_default=default_dm,
        **maps,
        global_options=glob,
        scheduled_options=scheduled,
        configured_environment=configured,
        callbacks=callbacks,
        voltage=voltage,
        event_cut=None,
    )
    if glob["gj_block"] != 0:
        py = random.Random(54321)
        before = py.getstate()
        unused = list(range(m))
        py.shuffle(unused)
        field["input_recipe"]["supplied_GJ_shuffle_site"] = dict(
            before=plain(before),
            after=plain(py.getstate()),
            unused_shuffled_copy=unused,
            actual_target_rule="clamped unshuffled prefix",
            whole_native_initialization_claim=False,
        )
    data.update(
        kind="cells.normal_ecm_event_join_inputs@1",
        case_id=case,
        case_role="component_control"
        if case in COMPONENT_CONTROLS
        else "new_ECM_event_catalog_noise_composition",
        stop_after_calls=3,
        calendar=dict(
            phase="SIM",
            step_count=3,
            dt_s=dt,
            sample_stride=1.0,
            provenance="Supplied complete original normal N3 phase",
        ),
        event_owner=owner,
        entry_event_state=entry,
        noise=dict(
            enabled=0 if case in ("noise_disabled", "static_K_reset") else 1,
            level_mol_m2_s=0.0 if case == "noise_zero_level" else 1e-6,
            provenance=(
                "Explicit original dynamic membrane protein flux amplitude; no Brownian scaling"
            ),
        ),
        prepared_rng=dict(
            kind="cells.supplied_post_event_finalization_numpy_state@1",
            manifest=perturbations.native_stream_manifest(stream),
            provenance=(
                "Explicit synthetic external MT state; prior initializer/callback draw "
                "history is not inferred"
            ),
        ),
        noise_cache=dict(
            present=case == "noise_disabled",
            value=[1e-7 * (j + 1) for j in range(m)] if case == "noise_disabled" else None,
            provenance=(
                "Explicit supplied earlier source cache for disabled carry"
                if case == "noise_disabled"
                else "Explicit supplied source cache absence at this bounded entry"
            ),
        ),
    )
    rebuild_owner(data)
    field["input_recipe"].update(
        supplied_geometry_and_tissue_owner=True,
        native_mesh_or_picker_generated=False,
        M_role_manufactured_explicit=True,
        P_equals_Na_plus_K_plus_2Ca_minus_Cl_minus_M=True,
        SourceDefaultDm_explicit=default_dm,
        noise_level_fixed_before_any_outcome=True,
    )
    field["input_recipe"].pop("P_equals_Na_plus_K_plus_2Ca_minus_Cl", None)
    return plain(data)


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared event/noise raw limit")
    data = fixture("combined")
    owner = data["event_owner"]
    dt = data["calendar"]["dt_s"]
    if case == "zero_global_pulse_width":
        owner["global_options"]["K_env"][2] = 0.0
    elif case == "radial_pressure_shape":
        n = len(owner["owners"]["cell_ids"])
        m = len(owner["owners"]["membrane_ids"])
        owner["scheduled_options"]["pressure"][4:] = [["all"], "gradient_r"]
        owner["callbacks"]["P"] = dict(
            source_function="gradient_r",
            source_scalar=[1.0] * m,
            dynamic=dict(kind="constant"),
            provenance=(
                "Supplied native radial return with slope0/z-offset1; complete membrane axis "
                "versus pressure cell target axis"
            ),
        )
        assert n != m
    elif case == "negative_Dm_source_return":
        owner["scheduled_options"]["Na_mem"][3] = -20.0
    elif case == "protein_noise_large_limit":
        data["noise"]["level_mol_m2_s"] = 1e308
    elif case == "GRN_refuses_before_noise":
        data["field"]["network"]["configuration"]["biomolecules"][0]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e8}
        )
    else:
        owner["global_options"]["T_change"] = [2 * dt, 4 * dt, 0.05 * dt, -3.0]
    data.update(case_id=case, case_role="raw_source_event_control_or_noise_limit")
    rebuild_owner(data)
    return data
