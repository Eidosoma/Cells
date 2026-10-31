"""Prospective supplied INIT cases; this module is not evaluated during preparation."""

import copy
import random

from cells.processes import betse_normal_ecm_init_phase as joined
from cells.processes import betse_normal_ecm_init_phase_setup as setup
from cells.processes import betse_perturbations as perturbations
from validation.betse import betse_normal_ecm_catalog_join_fixtures as catalog
from validation.betse import betse_normal_ecm_event_join_fixtures as events
from validation.betse import betse_normal_ecm_event_mechanics_fixtures as mechanical

CASES = (
    "active",
    "default_init_active",
    "mixed_inactive",
    "all_inactive",
    "inactive_dynamic_gate",
    "static_noise",
    "zero_static_noise",
    "dormant_globals",
    "dormant_sweep",
    "setup_shuffle",
    "empty_channels",
    "no_channels",
    "no_CaATP",
    "no_NaK",
    "mechanics_disabled",
    "osmotic_only",
    "different_init_dt",
    "one_call",
    "zero_calls",
    "long_calendar_prefix",
    "fractional_sampling",
    "no_samples",
)
RAW_CASES = (
    "negative_static_Dm",
    "NaK_nonfinite",
    "CaATP_nonfinite",
    "GRN_negative",
    "mechanics_nonfinite",
)
DEPENDENCIES = (
    "SIM_phase",
    "legacy_run_sim",
    "enabled_ER",
    "enabled_flow",
    "dynamic_deformation",
    "electroosmosis",
    "general_molecules",
    "GRN_off_unqualified",
    "physical_initializer",
    "cut_requested",
    "FAST_solver",
    "missing_setup_receipt",
    "missing_numpy_Gaussian_cache",
    "wrong_numpy_version",
    "wrong_python_version",
    "foreign_tissue_map",
    "wrong_dt",
    "nonzero_supplied_pump",
    "nonzero_late_flux",
    "nonzero_flow",
    "display_enabled",
    "nonprogressing_sampling",
    "foreign_parent",
    "changed_clock",
    "rebound_count",
    "inactive_count_forgery",
    "inactive_cold_gate_forgery",
    "changed_setup_store",
    "changed_rate_presence",
    "changed_previous_field",
    "changed_mechanics_parent",
    "changed_phase_receipt",
    "native_sample_refusal",
)
OBSERVER_CASES = ("before_call", "after_call")


def expected_calls(case):
    if case not in CASES:
        raise ValueError("Unknown prospective INIT case")
    return 0 if case == "zero_calls" else 1 if case == "one_call" else 3


def fixture(case="active"):
    if case not in CASES:
        raise ValueError("Choose a prospective ordinary INIT case")
    supplied = events.fixture("no_events")
    coupled = mechanical.shared(
        supplied, "mechanics_disabled" if case == "mechanics_disabled" else case
    )
    field = copy.deepcopy(supplied["field"])
    n, m, e = (
        len(field["initial"]["cell_mol_m3"][0]),
        len(field["initial"]["voltage_V"]),
        len(field["initial"]["environment_mol_m3"][0]),
    )
    field["initial"]["voltage_V"] = [0.0] * m
    field["bootstrap"]["boundary_V"] = {key: 0.0 for key in field["bootstrap"]["boundary_V"]}
    field["initial"]["junction_voltage_V"] = [0.0] * m
    field["initial"]["junction_field_xy_source"] = [[0.0, 0.0] for _ in range(m)]
    field["initial"]["gap_open"] = list(field["definition"]["junction_geometry"]["gap_weights"])
    owner = field["definition"]["environment_geometry_definition"]["current_definition"][
        "geometry"
    ]["owner"]
    field["initial"]["membrane_mol_m3"] = [
        [row[i] for i in owner] for row in field["initial"]["cell_mol_m3"]
    ]
    for key in (
        "membrane_flux_mol_m2_s",
        "junction_flux_mol_m2_s",
        "environment_flux_x_mol_m2_s",
        "environment_flux_y_mol_m2_s",
    ):
        field["initial"][key] = [[0.0 for _ in row] for row in field["initial"][key]]
    for step in field["steps"]:
        step["boundary_V"] = dict(field["bootstrap"]["boundary_V"])
        for key in ("supplied_pump_membrane_flux_mol_m2_s", "supplied_late_membrane_flux_mol_m2_s"):
            step["material"][key] = [[0.0 for _ in row] for row in step["material"][key]]
    populations = [
        catalog.population(name, j) for j, name in enumerate(("NaLeak", "KLeak", "CaLeak"))
    ]
    if case == "default_init_active":
        for row in populations:
            row.pop("init active")
    elif case in ("mixed_inactive", "all_inactive", "inactive_dynamic_gate"):
        if case == "inactive_dynamic_gate":
            populations = [catalog.population("Nav1p2", 0), catalog.population("HCN2", 1)]
        for j, row in enumerate(populations):
            row["init active"] = False if case != "mixed_inactive" or j == 1 else True
    elif case == "empty_channels":
        populations = []
    elif case == "no_channels":
        populations = None
    declaration_catalog = copy.deepcopy(supplied["catalog"])
    declaration_catalog["populations"] = populations
    dt = field["bootstrap"]["dt_s"] * (0.5 if case == "different_init_dt" else 1.0)
    for step in field["steps"]:
        step["material"]["dt_s"] = dt
    field["bootstrap"]["dt_s"] = dt
    count = (
        0
        if case == "zero_calls"
        else 1
        if case == "one_call"
        else 7
        if case in ("long_calendar_prefix", "fractional_sampling")
        else 3
    )
    stride = 1.5 if case == "fractional_sampling" else 8.0 if case == "no_samples" else 1.0
    glob = {key: 0 for key in setup.GLOBAL_KEYS}
    scheduled = {key: 0 for key in setup.TISSUE_KEYS}
    if case == "dormant_globals":
        glob.update(
            K_env=[0.0, dt, 0.0, 0.1], T_change=[0.0, dt, 0.0, -3.0], NaKATP_block=[0.0, dt, 0.0]
        )
    if case == "setup_shuffle":
        glob["gj_block"] = [0.0, dt, 0.0, 60.0]
    if case == "dormant_sweep":
        scheduled["Na_mem"] = [0.0, dt, 0.0, -20.0, ["all"], "f_sweep"]
    profiles = copy.deepcopy(declaration_catalog["tissue_profiles"])
    profiles.setdefault("all", list(range(m)))
    declaration_catalog["tissue_profiles"] = copy.deepcopy(profiles)
    phase_setup = dict(
        kind="cells.supplied_pre_INIT_setup@1",
        provenance="Manufactured pre-setup INIT tissue/core owners; no seed or load invocation",
        receipts=dict(
            tissue_profiles="Explicit supplied tissue and target-map receipt before static noise",
            init_core=(
                "Conditional init_core values with source zero Vm/pressure "
                "and absent handlers/rates"
            ),
            initializer_cache=(
                "Existing supplied conditional conductivity/screening cache inputs; "
                "whole init_dynamics producer is not qualified"
            ),
        ),
        numpy_rng=perturbations.native_stream_manifest(perturbations.native_stream(12345)),
        python_rng=setup.python_manifest(random.Random(2468)),
        channel_noise_level=0.15 if case == "static_noise" else 0.0,
        global_options=glob,
        scheduled_options=scheduled,
        maps=dict(
            tissue_target_inds=profiles,
            cell_target_inds=dict(all=list(range(n))),
            env_target_inds=dict(all=list(range(e))),
        ),
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None},
        dynamic_noise=dict(enabled=True, level=0.35),
    )
    md, mi = coupled["mechanics_definition"], coupled["mechanics_initial"]
    md["parameters"]["dt_s"] = dt
    if case == "osmotic_only":
        md["policy"]["deformation"] = False
    result = dict(
        kind=joined.INPUT_KIND,
        case_id=case,
        case_role="new supplied INIT conditional; no inherited pass/physical-phase credit",
        field=field,
        calcium=copy.deepcopy(supplied["calcium"]),
        catalog=declaration_catalog,
        flags=dict(joined.FIXED_FLAGS, alpha_NaK=0.0 if case == "no_NaK" else 1e-6),
        time_profile=dict(
            phase="INIT",
            init_total_s=(count + 0.25) * dt,
            init_dt_s=dt,
            init_sampling_s=stride * dt,
            sim_total_s=11.25 * dt,
            sim_dt_s=2.0 * dt,
            sim_sampling_s=4.0 * dt,
            provenance=(
                "Original full INIT count/dt and distinct unused SIM values, fixed before execution"
            ),
        ),
        setup=phase_setup,
        mechanics_definition=md,
        mechanics_initial=mi,
        sample_policy="calendar_eligibility_only_explicit_display_refusal",
        stop_after_calls=expected_calls(case),
    )
    if case == "no_CaATP":
        result["calcium"]["alpha_Ca"] = 0.0
    return events.plain(result)


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Unknown prospective INIT raw refusal")
    result = fixture("active")
    result["case_id"] = case
    result["case_role"] = "raw numerical/refusal evidence; no accuracy credit"
    if case == "negative_static_Dm":
        result["setup"]["channel_noise_level"] = -1e6
    elif case == "NaK_nonfinite":
        result["flags"]["alpha_NaK"] = 1e308
    elif case == "CaATP_nonfinite":
        result["calcium"]["alpha_Ca"] = 1e308
    elif case == "GRN_negative":
        row = result["field"]["network"]["configuration"]["biomolecules"][0]
        row["growth and decay"].update({"production rate": 0.0, "decay rate": 1e8})
    else:
        result["mechanics_definition"]["parameters"]["young_modulus_Pa"] = 1e-320
    return result
