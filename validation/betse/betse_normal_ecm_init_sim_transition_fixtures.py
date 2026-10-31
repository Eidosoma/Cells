"""Unevaluated declarations for retained-owner phase transitions.

Existing Nav1p2 SIM declarations retain the inherited oracle-domain limitation.
Concentrations, channel maxima and voltages are not tuned to avoid that limit.
"""

import copy

from cells.processes import betse_normal_ecm_init_sim_transition as transition
from validation.betse import betse_normal_ecm_event_mechanics_fixtures as simulation
from validation.betse import betse_normal_ecm_init_phase_fixtures as initialization

CASES = (
    "ordinary",
    "mixed_INIT_inactive",
    "all_INIT_inactive",
    "default_INIT_active",
    "static_redraw",
    "different_SIM_dt",
    "CaATP_disabled_retains_rate",
    "NaK_disabled_resets_on_call",
    "empty_SIM_channels",
    "no_channels_both_phases",
    "SIM_shuffle",
    "SIM_f_sweep",
    "supplied_new_process_rng",
    "one_INIT_call",
    "zero_INIT_calls",
    "no_INIT_samples",
)
PREFIX_REFUSALS = (
    "paused_INIT",
    "capped_INIT",
    "failed_material_prefix",
    "failed_setup_prefix",
    "latent_None_channels",
)
DEPENDENCIES = (
    "foreign_INIT_binding",
    "foreign_world",
    "foreign_ion_axis",
    "wrong_SIM_clock",
    "legacy_flag_false",
    "enabled_ER",
    "enabled_flow",
    "dynamic_deformation",
    "native_load_claim",
    "missing_rng_provenance",
    "inferred_pickle_rng",
    "wrong_continuity_stream",
    "foreign_profile_targets",
    "arbitrary_supplied_pump",
    "arbitrary_late_flux",
    "changed_Ca_rate_presence",
    "changed_old_clock",
    "changed_phase_receipt",
)
OBSERVER_CASES = ("before_call", "accepted_call", "headless_observation")
KNOWN_ORACLE_LIMIT = dict(
    class_name="Nav1p2",
    domain_V=[-0.120, 0.060],
    catalog05_no_CaATP_observed_V=[0.162, 0.380],
    status="inherited_reference_refusal_not_tolerance_failure",
    Root_owns_prospective_domain_qualification=True,
    fixture_tuning=False,
    oracle_domain_widening=False,
    constant_NaLeak_exception_applies=False,
)


def init_fixture(case):
    selected = {
        "mixed_INIT_inactive": "mixed_inactive",
        "all_INIT_inactive": "all_inactive",
        "default_INIT_active": "default_init_active",
        "no_channels_both_phases": "no_channels",
        "one_INIT_call": "one_call",
        "zero_INIT_calls": "zero_calls",
        "no_INIT_samples": "no_samples",
        "capped_INIT": "long_calendar_prefix",
    }.get(case, "active")
    return initialization.fixture(selected)


def fixture(case, complete):
    if (
        case not in CASES
        and case not in PREFIX_REFUSALS
        and case not in DEPENDENCIES
        and case not in OBSERVER_CASES
    ):
        raise ValueError("Unknown separately declared transition specimen")
    raw = simulation.fixture("GJ_override" if case == "SIM_shuffle" else "no_events")
    packet = raw["event_inputs"]
    # The new feature computes the ordinary pump flux. Old explicit external
    # flux seams are absent from this new declaration; no numeric outcome is used.
    for row in packet["field"]["steps"]:
        for key in ("supplied_pump_membrane_flux_mol_m2_s", "supplied_late_membrane_flux_mol_m2_s"):
            row["material"][key] = [[0.0 for _ in values] for values in row["material"][key]]
    if case == "different_SIM_dt":
        packet["calendar"]["dt_s"] *= 0.5
        packet["field"]["bootstrap"]["dt_s"] *= 0.5
        raw["mechanics_definition"]["parameters"]["dt_s"] *= 0.5
        for row in packet["field"]["steps"]:
            row["material"]["dt_s"] *= 0.5
    if case == "CaATP_disabled_retains_rate":
        packet["calcium"]["alpha_Ca"] = 0.0
    if case == "empty_SIM_channels":
        packet["catalog"]["populations"] = []
    if case in ("no_channels_both_phases", "latent_None_channels"):
        packet["catalog"]["populations"] = None
    dt = packet["calendar"]["dt_s"]
    source = complete.binding
    old_profile = copy.deepcopy(transition.ions.data(source.inputs_raw["time_profile"]))
    old_profile.update(
        phase="SIM",
        sim_total_s=3.25 * dt,
        sim_dt_s=dt,
        sim_sampling_s=dt,
        provenance=(
            "Explicit new native SIM clock, with original INIT association retained separately"
        ),
    )
    if case == "SIM_f_sweep":
        packet["event_owner"]["scheduled_options"]["Na_mem"] = [
            dt,
            3 * dt,
            0.1 * dt,
            0.15,
            ["all"],
            "f_sweep",
        ]
    grid = packet["field"]["definition"]["environment_geometry_definition"]
    cg = grid["current_definition"]["geometry"]
    profiles = []
    for name, indices in packet["catalog"]["tissue_profiles"].items():
        cells = packet["event_owner"]["cell_target_inds"][name]
        profiles.append(
            dict(
                name=name,
                cell_indices=list(cells),
                membrane_indices=list(indices),
                diffusion_m2_s=copy.deepcopy(packet["event_owner"]["tissue_default"]),
                provenance="Explicit ordered outputs of supplied unchanged tissue selectors",
            )
        )
    streams = source.setup_receipt
    numpy_rng = copy.deepcopy(transition.ions.data(streams["numpy_rng_after"]))
    python_rng = copy.deepcopy(
        transition.ions.data(streams["event_finalization"]["python_rng_after"])
    )
    if case == "supplied_new_process_rng":
        numpy_rng = initialization.perturbations.native_stream_manifest(
            initialization.perturbations.native_stream(6789)
        )
    declaration = dict(
        kind=transition.INPUT_KIND,
        case_id=case,
        provenance=(
            "Supplied in-memory completed INIT owners; no native load/pickle or "
            "cold reinitialization attestation"
        ),
        expected_init_binding_identity=source.identity,
        flags=dict(
            transition.FIXED_FLAGS, alpha_NaK=0.0 if case == "NaK_disabled_resets_on_call" else 1e-6
        ),
        time_profile=old_profile,
        sim_composition_template=raw,
        source_setup=dict(
            kind="cells.supplied_SIM_reinitialization_seams@1",
            provenance=(
                "Conditional selector outputs/retained core diffusion fields on identical owners"
            ),
            rng_mode="supplied_SIM_process_stream"
            if case == "supplied_new_process_rng"
            else "same_process_no_unowned_draws",
            rng_provenance=(
                "Explicit process stream supplied at SIM setup; no RNG state inferred from pickle"
            ),
            numpy_rng=numpy_rng,
            python_rng=python_rng,
            environment_diffusion=dict(
                adherens_multiplier=0.5,
                tight_junction_multiplier=0.4,
                environment_in_cluster_indices=list(
                    range(len(grid["cache_initial_state"]["environment_mol_m3"][0]))
                ),
                tight_junction_relative=[1.0] * len(grid["current_definition"]["ions"]["ids"]),
                provenance=(
                    "Explicit supplied retained init_core/world owner inputs for "
                    "the actual initDenv body"
                ),
            ),
            tissue_profiles=profiles,
            cbnd=None,
            static_noise_level=0.15 if case == "static_redraw" else 0.0,
            frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None},
        ),
        config_equality_receipt=dict(
            general_before=dict(solver="FULL", is_ecm=True),
            general_after=dict(solver="FULL", is_ecm=True),
            world_before=copy.deepcopy(grid["world"]),
            world_after=copy.deepcopy(grid["world"]),
            provenance=(
                "Supplied equality subsets plus exact shared owner/geometry checks; "
                "native seed checker not invoked"
            ),
        ),
    )
    assert (
        cg["cell_ids"]
        == source.material_binding.geometry_binding.definition["current_definition"]["geometry"][
            "cell_ids"
        ]
    )
    return initialization.events.plain(declaration)
