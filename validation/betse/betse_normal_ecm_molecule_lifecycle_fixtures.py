"""Held phase-aware declarations on the original supplied INIT physical state.

This factory is not evaluated during source preparation. No values are fitted
to numerical outcomes; native source failures remain separate raw specimens.
"""

import copy
import math

from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_transport as transport
from validation.betse import betse_normal_ecm_init_phase_fixtures as initialization
from validation.betse.betse_normal_transporter_join_fixtures import transporter

CASES = (
    "both_enabled",
    "general_only",
    "GRN_only",
    "both_disabled",
    "mixed_INIT_inactive",
    "all_INIT_inactive",
    "default_INIT_active",
    "empty_channels",
    "no_channels",
    "zero_capacity",
    "null_transporters",
    "empty_transporters",
    "ordered_transporters",
    "reverse_transporters",
    "one_INIT_call",
    "zero_INIT_calls",
    "no_INIT_samples",
    "different_SIM_dt",
    "CaATP_disabled_retains_rate",
    "NaK_disabled_resets_on_call",
    "publication_off",
    "pause_resume",
)
RAW_INIT_CASES = (
    "cold_missing_max_rate_0",
    "cold_missing_max_rate_1",
    "first_general_negative",
    "first_GRN_negative",
)
RAW_SIM_CASES = ("warm_missing_max_rate_0", "warm_missing_max_rate_1")
PREFIX_REFUSALS = ("paused_INIT", "capped_INIT", "failed_INIT")
OBSERVER_CASES = ("before_call", "after_call", "warm_before_reinitialize", "headless_sample")
DEPENDENCIES = (
    "foreign_INIT_binding",
    "foreign_world",
    "foreign_ion_axis",
    "wrong_SIM_clock",
    "legacy_flag_false",
    "enabled_ER",
    "enabled_flow",
    "active_osmotic",
    "native_load_claim",
    "missing_rng_provenance",
    "wrong_continuity_stream",
    "foreign_profile_targets",
    "arbitrary_late_flux",
    "changed_owner_flags",
    "latent_null_transporters",
    "changed_publication_policy",
    "changed_transporter_cache",
    "changed_gate_epoch",
    "changed_phase_receipt",
)


def init_calls(case):
    return 0 if case == "zero_INIT_calls" else 1 if case == "one_INIT_call" else 3


def init_fixture(case):
    if case not in (
        *CASES,
        *RAW_INIT_CASES,
        *RAW_SIM_CASES,
        *PREFIX_REFUSALS,
        *OBSERVER_CASES,
        *DEPENDENCIES,
    ):
        raise ValueError("Unknown separately declared molecule lifecycle specimen")
    selected = {
        "mixed_INIT_inactive": "mixed_inactive",
        "all_INIT_inactive": "all_inactive",
        "default_INIT_active": "default_init_active",
        "empty_channels": "empty_channels",
        "no_channels": "no_channels",
        "one_INIT_call": "one_call",
        "zero_INIT_calls": "zero_calls",
        "no_INIT_samples": "no_samples",
        "capped_INIT": "long_calendar_prefix",
    }.get(case, "mechanics_disabled")
    raw = initialization.fixture(selected)
    raw["kind"], raw["case_id"] = lifecycle.init.INPUT_KIND, case
    raw["case_role"] = (
        "Unrun supplied phase owners; no physical initializer or qualification credit"
    )
    raw["setup"]["dynamic_noise"] = dict(enabled=False, level=0.0)
    raw["setup"]["channel_noise_level"] = 0.0
    policy = raw["mechanics_definition"]["policy"]
    policy.update(deformation=False, deform_osmo=False, fluid_flow=False)
    general_enabled = case not in ("GRN_only", "both_disabled")
    grn_enabled = case not in ("general_only", "both_disabled", "first_general_negative")
    raw["flags"].update(molecules_enabled=general_enabled, grn_enabled=grn_enabled)
    policy.update(molecules_enabled=general_enabled, grn_enabled=grn_enabled)
    general = copy.deepcopy(raw["field"]["network"])
    grn = copy.deepcopy(raw["field"]["network"])
    general["owner"] = "molecules"
    rows = [transporter("general_Na_import")]
    if case in (
        "ordered_transporters",
        "reverse_transporters",
        "zero_capacity",
        *RAW_INIT_CASES,
        *RAW_SIM_CASES,
    ):
        rows += [
            transporter("general_Na_export", inward=(), outward=("Na",), reversible=False),
            transporter("general_X_import", ("X",), (1,), reversible=False),
        ]
    if case == "reverse_transporters":
        rows.reverse()
    if case == "zero_capacity":
        for row in rows:
            row["max rate"] = 0.0
    if case == "null_transporters":
        rows = None
    elif case == "empty_transporters":
        rows = []
    fault = "missing_max_rate_" + case[-1] if case.startswith("cold_missing_") else None
    if fault is not None:
        del rows[int(case[-1])]["max rate"]
    general["configuration"]["transporters"] = copy.deepcopy(rows)
    if case in ("first_general_negative", "first_GRN_negative", "failed_INIT"):
        selected_owner = general if case == "first_general_negative" else grn
        selected_owner["configuration"]["biomolecules"][0]["growth and decay"].update(
            {"production rate": 0.0, "decay rate": 1e8}
        )
    if case == "publication_off":
        for net in (general, grn):
            net["cold_publish"] = False
        for row in raw["field"]["steps"]:
            row["publication"] = False
    raw["field"]["network"] = copy.deepcopy(grn)
    external = raw["field"]["definition"]["environment_geometry_definition"]
    cg = external["current_definition"]["geometry"]
    mids, centres = (
        external["geometry"][key] for key in ("membrane_midpoints_m", "cell_centres_m")
    )
    radii = [
        math.sqrt(sum((a - b) ** 2 for a, b in zip(mid, centres[owner], strict=True)))
        for mid, owner in zip(mids, cg["owner"], strict=True)
    ]
    n, m, e = (
        len(raw["field"]["initial"][key][0])
        for key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3")
    )
    child = dict(
        kind=transport.INPUT_KIND,
        case_id=case,
        provenance=(
            "Explicit independent native owner flags on unchanged supplied INIT physical fields"
        ),
        flags=copy.deepcopy(transport.FLAGS),
        configuration={
            "general network": dict(
                copy.deepcopy(general["configuration"]),
                **{
                    "channels": copy.deepcopy(raw["catalog"]["populations"]),
                    "implement network": general_enabled,
                },
            ),
            "gene regulatory network settings": {"gene regulatory network simulated": grn_enabled},
        },
        field=copy.deepcopy(raw["field"]),
        calcium=copy.deepcopy(raw["calcium"]),
        handlers={
            role: dict(network=net, catalog=copy.deepcopy(raw["catalog"]))
            for role, net in (("molecules", general), ("grn", grn))
        },
        shared_initial={
            key: [0.0] * size
            for key, size in (
                ("extra_rho_cells", n),
                ("extra_rho_env", e),
                ("extra_J_mem", m),
                ("extra_Jenv_x", e),
                ("extra_Jenv_y", e),
            )
        },
        transport=dict(
            membrane_volume_m3=[
                0.5 * radius * area
                for radius, area in zip(radii, cg["membrane_area_m2"], strict=True)
            ],
            raw_setup_fault=fault,
        ),
    )
    raw["owners"] = child
    return initialization.events.plain(raw)


def fixture(case, complete):
    raw = copy.deepcopy(lifecycle.ions.data(complete.binding.inputs_raw))
    raw["case_id"] = case
    dt = raw["time_profile"]["init_dt_s"] * (0.5 if case == "different_SIM_dt" else 1.0)
    raw["time_profile"].update(phase="SIM", sim_total_s=3.25 * dt, sim_dt_s=dt, sim_sampling_s=dt)
    raw["flags"].update(phase="SIM", _run_sim=True)
    raw["stop_after_calls"] = 3
    raw["field"]["bootstrap"]["dt_s"] = dt
    raw["mechanics_definition"]["parameters"]["dt_s"] = dt
    for row in raw["field"]["steps"]:
        row["material"]["dt_s"] = dt
    if case == "CaATP_disabled_retains_rate":
        raw["calcium"]["alpha_Ca"] = 0.0
    if case == "NaK_disabled_resets_on_call":
        raw["flags"]["alpha_NaK"] = 0.0
    if case in RAW_SIM_CASES:
        owners = raw["owners"]
        owners["transport"]["raw_setup_fault"] = "missing_max_rate_" + case[-1]
        del owners["handlers"]["molecules"]["network"]["configuration"]["transporters"][
            int(case[-1])
        ]["max rate"]
        del owners["configuration"]["general network"]["transporters"][int(case[-1])]["max rate"]
    raw["owners"]["field"] = copy.deepcopy(raw["field"])
    raw["owners"]["calcium"] = copy.deepcopy(raw["calcium"])
    grid = raw["field"]["definition"]["environment_geometry_definition"]
    profiles = [
        dict(
            name=name,
            cell_indices=list(range(len(grid["current_definition"]["geometry"]["cell_ids"]))),
            membrane_indices=list(indices),
            diffusion_m2_s={
                "Dm_" + name: raw["field"]["definition"]["ions"]["membrane_diffusion_m2_s"][i][0]
                for i, name in enumerate(grid["current_definition"]["ions"]["ids"])
            },
            provenance="Supplied unchanged profile selector outputs, no picker invocation",
        )
        for name, indices in raw["catalog"]["tissue_profiles"].items()
    ]
    streams = complete.binding.setup_receipt
    source_setup = dict(
        kind="cells.supplied_SIM_reinitialization_seams@1",
        provenance="Retained original owner/core diffusion fields on the same supplied world",
        rng_mode="same_process_no_unowned_draws",
        rng_provenance="Actual post-INIT setup process streams; no stream inferred from pickle",
        numpy_rng=copy.deepcopy(lifecycle.ions.data(streams["numpy_rng_after"])),
        python_rng=copy.deepcopy(
            lifecycle.ions.data(streams["event_finalization"]["python_rng_after"])
        ),
        environment_diffusion=dict(
            adherens_multiplier=0.5,
            tight_junction_multiplier=0.4,
            environment_in_cluster_indices=list(
                range(len(grid["cache_initial_state"]["environment_mol_m3"][0]))
            ),
            tight_junction_relative=[1.0] * len(grid["current_definition"]["ions"]["ids"]),
            provenance="Explicit retained init_core/world owner inputs to the native initDenv body",
        ),
        tissue_profiles=profiles,
        cbnd=None,
        static_noise_level=0.0,
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None},
    )
    return initialization.events.plain(
        dict(
            kind=lifecycle.INPUT_KIND,
            case_id=case,
            provenance=(
                "Supplied complete headless INIT handoff; "
                "no native physical initializer or persistence claim"
            ),
            expected_init_binding_identity=complete.binding.identity,
            sim_phase=raw,
            source_setup=source_setup,
            config_equality_receipt=dict(
                general_before=dict(solver="FULL", is_ecm=True),
                general_after=dict(solver="FULL", is_ecm=True),
                world_before=copy.deepcopy(grid["world"]),
                world_after=copy.deepcopy(grid["world"]),
                provenance=(
                    "Supplied seed compatibility subsets with exact unchanged owner/geometry checks"
                ),
            ),
        )
    )
