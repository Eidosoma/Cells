"""Held actual cold/INIT/warm/SIM owner conditionals; no inherited pass credit."""

import copy
import os
import traceback
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_ecm_grn_join as chemistry
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as fields
from tests.unit import test_betse_normal_ecm_init_phase as initialized
from tests.unit import test_betse_normal_ecm_init_sim_transition as transitioned
from tests.unit import test_betse_normal_ecm_molecule_lifecycle_capture as capture
from tests.unit import test_betse_normal_ecm_molecule_transport as transported
from validation.betse import betse_normal_ecm_init_phase_capture as failures
from validation.betse import betse_normal_ecm_molecule_failure_checks as failure_checks
from validation.betse import betse_normal_ecm_molecule_lifecycle_fixtures as fixtures

phase, owners = lifecycle.init, lifecycle.owners
archive, check, references, isolated = (
    capture.archive,
    capture.check,
    capture.references,
    capture.isolated,
)
exact = fields.exact
MODES = ("nak", "material", "calcium", "mechanics", "commit", "field")


@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get("CELLS_ECM_MOLECULE_LIFECYCLE_RELEASED") != "1":
        pytest.skip("Held source preparation; Chief must explicitly release this lifecycle suite")


def retain_failure(tmp_path, name, error, **values):
    failures.record_failure(
        error,
        stage=name,
        readers=dict(
            supplied_values=lambda: values,
            actual_partial=lambda: getattr(error, "partial", None),
            exception_chain=lambda: failure_checks.exception_chain(error),
            traceback=lambda: traceback.format_exc(),
        ),
        retain=lambda value: archive(tmp_path, name + "-failure-before-reraise", value),
    )


def flags(raw):
    return dict(
        molecules=raw["owners"]["configuration"]["general network"]["implement network"],
        grn=raw["owners"]["configuration"]["gene regulatory network settings"][
            "gene regulatory network simulated"
        ],
    )


def retained(tmp_path, name, operation, **values):
    return failure_checks.retained_call(
        operation,
        stage=name,
        readers={key: lambda value=value: value for key, value in values.items()},
        retain=lambda value: archive(tmp_path, name + "-outcome-before-classification", value),
    )


def sample_contract(binding, parent, clock_forms):
    for form in clock_forms:
        exact(
            ions.data(parent.clock),
            dict(
                form["clock"],
                call_index=parent.cursor,
                material_dt_sum_s=parent.cursor * binding.calendar.dt_s,
            ),
        )
        expected = [j for j in form["sample_indices"] if j < parent.cursor]
        assert [row["call_index"] for row in parent.observations] == expected
    assert len(parent.history) == parent.cursor
    assert all(row["event_fire_calls"] == row["protein_noise_calls"] == 0 for row in parent.history)
    assert all(
        row["native_storage_called"] is row["display_completed"] is False
        for row in parent.observations
    )


def check_handlers(tmp_path, name, point, binding, parent, detail, answers, native, observed):
    cache = parent.network.network_cache
    dispatch = detail["network"]
    assert native["status"] == "source_completed" and not native["capture_errors"]
    exact(observed["commit"]["values_before"], native["returned"]["material"])
    exact(dispatch["shared_after"], native["returned"]["shared"])
    expected_roles = [role for role in owners.ROLES if cache["enabled"][role]]
    assert [
        r["role"] for r in dispatch["source_order"] if r["stage"] == "before_dispatch"
    ] == expected_roles
    for role in owners.ROLES:
        saved = cache["handlers"][role]
        if saved is None:
            assert native["returned"]["handlers"][role] is None
            continue
        exact(ions.data(saved["cache"]), native["returned"]["handlers"][role])
        feedback = dispatch["handlers"][role]
        for mode, comparator in (
            (
                "channels",
                lambda *forms, feedback=feedback: catalog.compare_channels(
                    binding, feedback, *forms
                ),
            ),
            (
                "network",
                lambda *forms, feedback=feedback: chemistry.compare_local(feedback, *forms),
            ),
        ):
            key = role + "-" + mode
            rows = comparator(*answers[key])
            if rows:
                check(tmp_path, name + "-" + key, point / key, rows)
            else:
                assert mode == "channels" and not answers[key][1]["events"]
        key = role + "-transporters"
        if key in answers:
            rows, books = transported.transporter_rows(feedback, *answers[key])
            archive(tmp_path, name + "-transporter-books", books)
            if rows:
                check(tmp_path, name + "-transporters", point / key, rows)
            else:
                assert not answers[key][1]["frames"]
    assert cache["source_phase"] == binding.calendar.phase
    assert cache["legacy_run_sim"] is (binding.calendar.phase == "SIM")


def run_calls(tmp_path, name, binding, parent, *, transition_binding=None, wrapper=None, stop=None):
    folder = capture.root(tmp_path) / name
    folder.mkdir(parents=True, exist_ok=False)
    clock_forms = references(
        folder / "clock",
        dict(
            mode="clock",
            time_profile=binding.inputs_raw["time_profile"],
            source_phase=binding.calendar.phase,
        ),
    )
    target = binding.call_limit if stop is None else stop
    while parent.status == "ready" and parent.cursor < target:
        index = parent.cursor
        point = folder / ("call-" + str(index))
        point.mkdir()
        answers, observed, native = {}, {}, {}

        def before(mode, index=index, observed=observed, answers=answers, point=point):
            def callback(value):
                incoming = dict(
                    ions.data(value),
                    source_phase=binding.calendar.phase,
                    legacy_run_sim=binding.calendar.phase == "SIM",
                )
                archive(tmp_path, name + "-" + str(index) + "-" + mode + "-incoming", incoming)
                observed[mode] = incoming
                answers[mode] = references(point / mode, incoming)

            return callback

        def handler(
            role,
            stage,
            value,
            index=index,
            native=native,
            observed=observed,
            answers=answers,
            point=point,
        ):
            archive(tmp_path, name + "-" + str(index) + "-" + role + "-" + stage, value)
            if role == "all":
                native["call"] = isolated(point / "native", value)
            elif stage in ("channels", "network", "transporters"):
                key = role + "-" + stage
                observed[key] = ions.data(value)
                answers[key] = references(point / key, value)

        previous, digest = parent, ions.digest(parent)
        try:
            callbacks = {"before_" + mode: before(mode) for mode in MODES}
            if transition_binding is None:
                parent, detail = phase.advance(
                    binding, parent, handler_observer=handler, **callbacks
                )
            else:
                wrapper, detail = lifecycle.advance(
                    transition_binding, wrapper, handler_observer=handler, **callbacks
                )
                parent = wrapper.active
            archive(
                tmp_path,
                name + "-" + str(index) + "-accepted-before-comparison",
                dict(parent=parent, detail=detail, wrapper=wrapper),
            )
        except Exception as error:
            retain_failure(
                tmp_path, name + "-" + str(index), error, parent=previous, observed=observed
            )
            raise
        assert ions.digest(previous) == digest and parent.cursor == index + 1
        check_handlers(
            tmp_path,
            name + "-" + str(index),
            point,
            binding,
            parent,
            detail,
            answers,
            native["call"],
            observed,
        )
        trial = detail["material_trial"]
        mechanical_native = dict(candidate=ions.data(detail["mechanics_trial"].candidate.cache))
        rows = (
            ("nak", initialized.nak_rows(detail["nak"], *answers["nak"])),
            ("material", transported.prefix_rows(trial, *answers["material"])),
            ("calcium", catalog.compare_calcium(detail["calcium"], *answers["calcium"])),
            ("commit", transported.commit_rows(trial, *answers["commit"])),
            ("field", fields.compare_field(binding, parent.field, *answers["field"])),
        )
        for mode, values in rows:
            check(tmp_path, name + "-" + str(index) + "-" + mode, point / mode, values)
        # Disabled mechanics has a complete independently evaluated retained cache.
        for form in answers["mechanics"]:
            exact(mechanical_native["candidate"], form["history"][0]["candidate"])
        sample_contract(binding, parent, clock_forms)
    sample_contract(binding, parent, clock_forms)
    return parent, wrapper


def supplied_init(tmp_path, case, *, checked=False, stop=None):
    raw = fixtures.init_fixture(case)
    archive(tmp_path, case + "-INIT-input-before-evaluation", raw)
    declaration = phase.bind(raw)
    seen, answers = {}, {}
    folder = capture.root(tmp_path) / (case + "-cold")
    folder.mkdir(parents=True, exist_ok=False)

    def after_setup(value):
        archive(tmp_path, case + "-static-setup", value)
        seen["setup"] = value
        if checked:
            ids = declaration.base.material_binding.geometry_binding.current_binding.ion_ids
            answers["setup"] = references(
                folder / "setup",
                dict(mode="setup", setup_return=value, ion_ids=list(ids), source_phase="INIT"),
            )

    def handler(role, stage, value):
        archive(tmp_path, case + "-cold-" + role + "-" + stage, value)
        if checked and role == "all":
            seen["native"] = isolated(folder / "native", value)

    def after_cold(value):
        archive(tmp_path, case + "-cold-actual-return", value)
        seen["cold"] = value

    def bootstrap(value):
        archive(tmp_path, case + "-bootstrap-actual-input", value)
        if checked:
            answers["field"] = references(
                folder / "field", dict(ions.data(value), source_phase="INIT")
            )

    try:
        binding, parent = phase.initialize(
            declaration,
            after_setup=after_setup,
            after_cold=after_cold,
            handler_observer=handler,
            before_field=bootstrap,
        )
        archive(
            tmp_path, case + "-INIT-entry-before-comparisons", dict(binding=binding, parent=parent)
        )
        if checked:
            check(
                tmp_path,
                case + "-static-errors",
                folder / "setup",
                initialized.setup_rows(seen["setup"], *answers["setup"]),
            )
            check(
                tmp_path,
                case + "-bootstrap-errors",
                folder / "field",
                fields.compare_field(binding, parent.field, *answers["field"]),
            )
            native = seen["native"]
            assert native["status"] == "source_completed"
            exact(seen["cold"]["material"], native["returned"]["material"])
            assert set(native["returned"]["shared_absent"]) == {"rho_pump", "rho_channel"}
            for role in owners.ROLES:
                saved = seen["cold"]["network_cache"]["handlers"][role]
                if saved is None:
                    assert native["returned"]["handlers"][role] is None
                    continue
                exact(saved["cache"], native["returned"]["handlers"][role])
                incoming = transported.cold_input(raw["owners"], role)
                incoming.update(time_profile=raw["time_profile"], source_phase="INIT")
                forms = references(folder / role, incoming)
                check(
                    tmp_path,
                    case + "-" + role + "-cold-errors",
                    folder / role,
                    chemistry.compare_cold(
                        binding, SimpleNamespace(network_cache=saved["cache"]), *forms
                    ),
                )
        if checked:
            parent, _ = run_calls(tmp_path, case + "-INIT", binding, parent, stop=stop)
        else:
            while parent.status == "ready" and (stop is None or parent.cursor < stop):
                parent, detail = phase.advance(binding, parent)
                archive(
                    tmp_path,
                    case + "-INIT-prefix-" + str(parent.cursor),
                    dict(parent=parent, detail=detail),
                )
        return binding, parent
    except Exception as error:
        retain_failure(tmp_path, case + "-INIT", error, declaration=declaration, reached=seen)
        raise


def prepare(tmp_path, case, *, checked=False):
    binding, parent = supplied_init(tmp_path, case, checked=checked)
    complete = lifecycle.prepare_complete(binding, parent)
    archive(tmp_path, case + "-complete-INIT", complete)
    raw = fixtures.fixture(case, complete)
    archive(tmp_path, case + "-SIM-declaration", raw)
    return complete, raw


def phase_rules_input(raw, completed, reached):
    legacy = lifecycle.setup.legacy_setup_inputs(raw)
    adjusted = dict(reached, before_GRN_reinitialize=reached["before_dual_reinitialize"])
    adjusted["before_GRN_reinitialize"] = dict(
        adjusted["before_GRN_reinitialize"],
        cells_fields={
            key: {"__transition_ndarray__": value["__native_buffer__"]}
            for key, value in adjusted["before_GRN_reinitialize"]["cell_fields"].items()
            if isinstance(value, dict) and "__native_buffer__" in value
        },
    )
    result = transitioned.phase_rules_input(legacy, completed, adjusted)
    result["grid_index_groups"] = {
        key: reached["before_dual_reinitialize"]["cell_fields"][key]["__native_buffer__"]
        for key in ("all_bound_mem_inds", "interior_bound_mem_inds", "ecm_inds_bound_cell")
    }
    result.update(enabled=flags(raw["sim_phase"]), source_phase="SIM")
    return result


@pytest.mark.parametrize("case", fixtures.CASES)
def test_actual_lifecycle(tmp_path, case):
    complete, raw = prepare(tmp_path, case, checked=True)
    original = ions.digest(complete)
    binding = lifecycle.bind(raw)
    seen, boot = {}, []
    folder = capture.root(tmp_path) / (case + "-transition")
    folder.mkdir()

    def observer(stage, value):
        seen[stage] = value
        archive(tmp_path, case + "-warm-" + stage, value)

    def bootstrap(value):
        boot.extend(references(folder / "bootstrap", dict(ions.data(value), source_phase="SIM")))

    try:
        parent = lifecycle.transition(binding, complete, observer=observer, before_field=bootstrap)
        archive(tmp_path, case + "-SIM-entry-before-comparisons", parent)
    except Exception as error:
        retain_failure(tmp_path, case + "-warm", error, complete=complete, reached=seen)
        raise
    native = isolated(folder / "native-reinitialize", seen["before_dual_reinitialize"])
    assert native["status"] == "source_completed"
    reached = seen["dual_owners_reinitialized"]["available"]
    exact(native["returned"]["material"], reached["material"])
    for role in owners.ROLES:
        actual = reached["owners"]["handlers"][role]
        expected = native["returned"]["handlers"][role]
        if actual is None:
            assert expected is None
            continue
        exact(actual["cache"], expected)
        identity = seen["dual_owners_reinitialized"]["owner_identity"][role]
        assert identity["owner_retained"] and identity["core_retained"]
        assert all(identity["molecule_objects_retained"].values())
        assert all(identity["channel_objects_rebuilt"].values())
        assert all(identity["transporter_objects_rebuilt"].values())
        assert all(value is None for value in identity["transporter_fluxes_after"].values())
        assert not identity["read_substances_called"] and not identity["fresh_cold_owner_created"]
    forms = references(folder / "phase-rules", phase_rules_input(raw, complete, seen))
    phase_seen = dict(seen)
    phase_seen["post_static"] = dict(
        seen["post_static"],
        available=dict(
            seen["post_static"]["available"],
            simulator_fields=seen["post_static"]["available"]["simulator_arrays"],
        ),
    )
    check(
        tmp_path,
        case + "-phase-reset-errors",
        folder / "phase-rules",
        transitioned.phase_rows(phase_seen, *forms),
    )
    check(
        tmp_path,
        case + "-SIM-bootstrap-errors",
        folder / "bootstrap",
        fields.compare_field(parent.phase_binding, parent.active.field, *boot),
    )
    assert parent.active.cursor == parent.active.clock.material_dt_sum_s == 0
    exact(ions.data(parent.active.rate_cache), ions.data(complete.parent.rate_cache))
    exact(ions.data(parent.active.nak_rate), ions.data(complete.parent.nak_rate))
    if case == "pause_resume":
        paused = lifecycle.pause(binding, parent)
        parent = lifecycle.resume(binding, paused)
        exact(parent.active.network, paused.active.network)
    active, parent = run_calls(
        tmp_path,
        case + "-SIM",
        parent.phase_binding,
        parent.active,
        transition_binding=binding,
        wrapper=parent,
    )
    assert active.status == "exhausted" and active.cursor == 3
    assert ions.digest(complete) == original and parent.source_init.identity == complete.identity
    if case == "CaATP_disabled_retains_rate":
        exact(ions.data(active.rate_cache), ions.data(complete.parent.rate_cache))
    if case == "NaK_disabled_resets_on_call":
        assert active.nak_rate.present and np.all(active.nak_rate.value == 0)


@pytest.mark.parametrize("case", fixtures.RAW_INIT_CASES)
def test_original_INIT_failure(tmp_path, case):
    raw = fixtures.init_fixture(case)
    archive(tmp_path, case + "-raw-input", raw)
    declaration = phase.bind(raw)
    seen = {}

    def record(role, stage, value):
        if role == "all":
            seen[stage] = value

    with pytest.raises(phase.InitRejected) as caught:
        binding, parent = retained(
            tmp_path,
            case + "-initialize",
            lambda: phase.initialize(declaration, handler_observer=record),
            declaration=declaration,
        )
        while parent.status == "ready":
            parent, _ = retained(
                tmp_path,
                case + "-call-" + str(parent.cursor),
                lambda parent=parent: phase.advance(binding, parent, handler_observer=record),
                parent=parent,
            )
    archive(tmp_path, case + "-original-refusal", dict(partial=caught.value.partial, seen=seen))
    if case.startswith("cold_"):
        native = isolated(capture.root(tmp_path) / (case + "-native"), seen["before_initialize"])
        assert native["status"] == "source_refused" and native["failure"]["type"] == "KeyError"
        assert failure_checks.exception_chain(caught.value)[-1]["type"] == "KeyError"
        exact(
            caught.value.partial["owner_buffers"]["partial_wires"],
            native["partial_buffers"]["partial_wires"],
        )
        exact(
            caught.value.partial["owner_buffers"]["material"], native["partial_buffers"]["material"]
        )
        failed = lifecycle.prepare_failed_prefix(declaration, None, caught.value)
        with pytest.raises(lifecycle.TransitionRejected):
            retained(
                tmp_path,
                case + "-failed-admission",
                lambda: lifecycle.check_complete(failed),
                failed=failed,
            )
    else:
        native = isolated(capture.root(tmp_path) / (case + "-native"), seen["before_dispatch"])
        assert native["status"] == "source_refused" and native["failure_capture"]
        assert parent.cursor == 0
        chain = failure_checks.exception_chain(caught.value)
        assert [row["type"] for row in chain] == [
            "InitRejected",
            "ECMTransportRejected",
            "BetseSimUnstableException",
        ]
        message = (
            "Network concentration of X in cells below zero! Your simulation has become unstable."
        )
        assert chain[-1]["message"] == native["failure"]["message"] == message
        assert caught.value.partial["root_cause"]["type"] == "ECMTransportRejected"
        assert caught.value.partial["stage"] == "material_calcium_network_mechanics"
        assert caught.value.partial["reached_stage"] == "network"
        assert caught.value.partial["call_index"] == 0
        buffers = caught.value.partial["owner_buffers"]
        exact(buffers["material"], native["partial_buffers"]["material"])
        exact(buffers["partial_wires"], native["partial_buffers"]["partial_wires"])
        exact(buffers["source_order"], native["order"])
        role = "molecules" if "general" in case else "grn"
        trace = buffers["traces"][role]
        target = [row for row in trace["mover_frames"] if row["species"] == "X"]
        assert target[-1]["stage"] == "environment_mix"
        assert any(value < 0 for value in target[-1]["fields"]["cX_cells"])
        for owner in owners.ROLES:
            for key in (
                "molecule_frames",
                "mover_frames",
                "channel_events",
                "rhs",
                "control_writes",
            ):
                exact(buffers["traces"][owner][key], native["traces"][owner][key])
        general = buffers["traces"]["molecules"]["transporter_frames"]
        exact(general, native["traces"]["molecules"]["transporter_frames"])
        configured = raw["owners"]["handlers"]["molecules"]["network"]["configuration"][
            "transporters"
        ]
        assert [(row["stage"], row["name"]) for row in general] == [
            (stage, row["name"])
            for row in configured
            for stage in ("before", "flux", "current", "reactant_commit", "product_commit", "after")
        ]
        ion_ids = raw["field"]["definition"]["environment_geometry_definition"][
            "current_definition"
        ]["ions"]["ids"]
        assert [(row["stage"], row["species"]) for row in trace["molecule_frames"]] == (
            [("molecule_intra", "X"), ("molecule_intra", "Y"), ("rhs_ready", None)]
            + [("chemical_commit", ion) for ion in ion_ids]
            + [("chemical_commit", "X"), ("transport_before", "X")]
        )


@pytest.mark.parametrize("case", fixtures.RAW_SIM_CASES)
def test_original_warm_failure(tmp_path, case):
    complete, raw = prepare(tmp_path, case)
    seen = {}
    with pytest.raises(lifecycle.TransitionRejected) as caught:
        retained(
            tmp_path,
            case + "-warm-call",
            lambda: lifecycle.transition(
                lifecycle.bind(raw),
                complete,
                observer=lambda stage, value: seen.update({stage: value}),
            ),
            complete=complete,
            raw=raw,
        )
    archive(tmp_path, case + "-warm-refusal", dict(partial=caught.value.partial, seen=seen))
    native = isolated(capture.root(tmp_path) / (case + "-native"), seen["before_dual_reinitialize"])
    assert native["status"] == "source_refused" and native["failure"]["type"] == "KeyError"
    inner = caught.value.partial["inner_partial"]
    exact(inner["available"]["partial_wires"], native["partial_buffers"]["partial_wires"])
    assert failure_checks.exception_chain(caught.value)[-1]["type"] == "KeyError"
    assert not caught.value.partial["automatic_retry"]


@pytest.mark.parametrize("case", fixtures.PREFIX_REFUSALS)
def test_incomplete_INIT_refusal(tmp_path, case):
    if case == "failed_INIT":
        raw = fixtures.init_fixture(case)
        binding, parent = phase.initialize(phase.bind(raw))
        with pytest.raises(phase.InitRejected) as caught:
            retained(
                tmp_path, case + "-advance", lambda: phase.advance(binding, parent), parent=parent
            )
        failed = lifecycle.prepare_failed_prefix(binding, parent, caught.value)
        archive(tmp_path, case + "-failed-prefix", failed)
        with pytest.raises(lifecycle.TransitionRejected):
            retained(
                tmp_path, case + "-admit", lambda: lifecycle.check_complete(failed), failed=failed
            )
    else:
        binding, parent = supplied_init(tmp_path, case, stop=1 if case == "paused_INIT" else None)
        if case == "paused_INIT":
            parent = phase.pause(binding, parent)
        with pytest.raises(lifecycle.TransitionRejected) as caught:
            retained(
                tmp_path,
                case + "-prepare",
                lambda: lifecycle.prepare_complete(binding, parent),
                parent=parent,
            )
        archive(tmp_path, case + "-prefix-refusal", caught.value.partial)


@pytest.mark.parametrize("case", fixtures.OBSERVER_CASES)
def test_observer_partial_retention(tmp_path, case):
    complete, raw = prepare(tmp_path, case)
    binding = lifecycle.bind(raw)
    seen = {}

    def warm(stage, value):
        seen[stage] = value
        if case == "warm_before_reinitialize" and stage == "before_dual_reinitialize":
            raise RuntimeError("Declared warm observer failure")

    if case == "warm_before_reinitialize":
        with pytest.raises(lifecycle.TransitionRejected) as caught:
            retained(
                tmp_path,
                case + "-warm",
                lambda: lifecycle.transition(binding, complete, observer=warm),
                complete=complete,
            )
    else:
        parent = lifecycle.transition(binding, complete)
        if case == "headless_sample":
            with pytest.raises(phase.InitRejected) as caught:
                retained(
                    tmp_path,
                    case + "-sample",
                    lambda: phase.request_native_sample(parent.phase_binding, parent.active),
                    parent=parent,
                )
        else:

            def observer(stage, value):
                seen[stage] = value
                if stage == case:
                    raise RuntimeError("Declared lifecycle call observer failure")

            with pytest.raises(lifecycle.TransitionRejected) as caught:
                retained(
                    tmp_path,
                    case + "-advance",
                    lambda: lifecycle.advance(binding, parent, observer=observer),
                    parent=parent,
                )
            assert parent.cursor == 0
            if case == "after_call":
                assert seen[case].cursor == 1
    archive(tmp_path, case + "-observer-partial", dict(partial=caught.value.partial, reached=seen))


@pytest.mark.parametrize("case", fixtures.DEPENDENCIES)
def test_lifecycle_dependency_refusal(tmp_path, case):
    complete, raw = prepare(tmp_path, case)
    sim = raw["sim_phase"]
    if case == "foreign_INIT_binding":
        raw["expected_init_binding_identity"] = "foreign"
    elif case in ("foreign_world", "foreign_ion_axis"):
        grid = sim["field"]["definition"]["environment_geometry_definition"]
        if case == "foreign_world":
            grid["world"]["foreign"] = True
        else:
            grid["current_definition"]["ions"]["ids"][0] = "foreign"
    elif case == "wrong_SIM_clock":
        sim["time_profile"]["phase"] = "INIT"
    elif case == "legacy_flag_false":
        sim["flags"]["_run_sim"] = False
    elif case == "enabled_ER":
        sim["flags"]["Ca_dyn"] = True
    elif case == "enabled_flow":
        sim["flags"]["fluid_flow"] = True
    elif case == "active_osmotic":
        sim["mechanics_definition"]["policy"]["deform_osmo"] = True
    elif case == "native_load_claim":
        raw["native_load_or_pickle"] = True
    elif case == "missing_rng_provenance":
        raw["source_setup"]["rng_provenance"] = ""
    elif case == "wrong_continuity_stream":
        raw["source_setup"]["numpy_rng"] = (
            fixtures.initialization.perturbations.native_stream_manifest(
                fixtures.initialization.perturbations.native_stream(6789)
            )
        )
    elif case == "foreign_profile_targets":
        raw["source_setup"]["tissue_profiles"][0]["membrane_indices"] = [999999]
    elif case == "arbitrary_late_flux":
        sim["field"]["steps"][0]["material"]["supplied_late_membrane_flux_mol_m2_s"][0][0] = 1e-12
    elif case == "changed_owner_flags":
        sim["owners"]["configuration"]["general network"]["implement network"] = False
        sim["flags"]["molecules_enabled"] = False
        sim["mechanics_definition"]["policy"]["molecules_enabled"] = False
    elif case == "latent_null_transporters":
        sim["owners"]["handlers"]["molecules"]["network"]["configuration"]["transporters"] = None
        sim["owners"]["configuration"]["general network"]["transporters"] = None
    elif case == "changed_publication_policy":
        sim["owners"]["handlers"]["molecules"]["network"]["cold_publish"] = False
    elif case in ("changed_transporter_cache", "changed_gate_epoch", "changed_phase_receipt"):
        binding = lifecycle.bind(raw)
        parent = lifecycle.transition(binding, complete)
        active = parent.active
        if case == "changed_phase_receipt":
            parent = replace(
                parent, receipt=ions.freeze(dict(ions.data(parent.receipt), old_INIT_clock={}))
            )
        else:
            saved = copy.deepcopy(ions.data(active.network.network_cache))
            general = saved["handlers"]["molecules"]["cache"]
            if case == "changed_gate_epoch":
                general["channel_calls"][next(iter(general["channel_calls"]))] = 99
            else:
                general["wire"]["transporter_fields"] = {}
            net = lifecycle.network._state(
                parent.phase_binding, active.network.material, saved, active.network.controls
            )
            active = phase.state(
                parent.phase_binding,
                net,
                active.field,
                active.rate_cache,
                active.nak_rate,
                active.mechanics,
                active.stores,
                active.clock,
                active.history,
                active.observations,
            )
            parent = lifecycle.phase(
                binding, complete, parent.phase_binding, active, parent.receipt
            )
        with pytest.raises((ValueError, lifecycle.TransitionRejected)) as caught:
            retained(
                tmp_path, case + "-verify", lambda: lifecycle.verify(binding, parent), parent=parent
            )
        archive(tmp_path, case + "-cache-refusal", dict(message=str(caught.value), parent=parent))
        return
    with pytest.raises(
        (ValueError, lifecycle.TransitionRejected, AssertionError, KeyError)
    ) as caught:
        retained(
            tmp_path,
            case + "-transition",
            lambda: lifecycle.transition(lifecycle.bind(raw), complete),
            raw=raw,
            complete=complete,
        )
    archive(
        tmp_path,
        case + "-dependency-refusal",
        dict(message=str(caught.value), partial=getattr(caught.value, "partial", None), inputs=raw),
    )
