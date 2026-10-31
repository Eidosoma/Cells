# ruff: noqa: C408
"""NumPy-free phase/run evidence relationships; never evaluates scientific laws."""

import math

if __package__:
    from .betse_normal_ecm_molecule_events_execution_contract import require
else:
    from betse_normal_ecm_molecule_events_execution_contract import require
ROLES = ("molecules", "grn")
PHASE_FIELDS = (
    "binding_identity",
    "network",
    "field",
    "rate_cache",
    "nak_rate",
    "mechanics",
    "stores",
    "clock",
    "history",
    "observations",
    "status",
    "identity",
)
RUN_FIELDS = (
    "binding_identity",
    "entry",
    "entry_receipt",
    "active",
    "history",
    "observations",
    "status",
    "identity",
)
MATERIAL_FIELDS = (
    "cell_mol_m3",
    "membrane_mol_m3",
    "environment_mol_m3",
    "voltage_V",
    "membrane_flux_mol_m2_s",
    "junction_flux_mol_m2_s",
    "environment_flux_x_mol_m2_s",
    "environment_flux_y_mol_m2_s",
    "junction_voltage_V",
    "junction_field_source",
    "junction_field_xy_source",
    "gap_open",
)
FIELD_FIELDS = ("binding_identity", "before", "current", "environment", "voltage", "identity")


def cursor(parent):
    return parent["clock"]["call_index"] if "clock" in parent else cursor(parent["active"])


def array(value):
    return isinstance(value, dict) and value.get("__typed_array__") is True


def numeric_values(archives, value):
    if array(value):
        yield from archives.values(value)
    elif isinstance(value, list):
        for item in value:
            yield from numeric_values(archives, item)
    else:
        require(type(value) in (int, float, bool), "Complete numeric value required")
        yield value


def json_exact(archives, actual, expected):
    """Match a typed actual buffer to the frozen reference's JSON numeric tree."""
    if array(actual):

        def shape(value):
            if not isinstance(value, list):
                return []
            lengths = [shape(v) for v in value]
            require(
                not lengths or all((v == lengths[0] for v in lengths)), "Ragged JSON numeric array"
            )
            return [len(value)] + (lengths[0] if lengths else [])

        require(actual["shape"] == shape(expected), "Typed/reference shape differs")
        pairs = zip(archives.values(actual), numeric_values(archives, expected), strict=True)
        require(
            all(
                (
                    a == b
                    or (
                        isinstance(a, float)
                        and isinstance(b, float)
                        and math.isnan(a)
                        and math.isnan(b)
                    )
                    for a, b in pairs
                )
            ),
            "Exact typed/reference numeric values differ",
        )
    elif isinstance(actual, dict):
        require(
            isinstance(expected, dict) and set(actual) == set(expected),
            "Typed/reference mapping differs",
        )
        for key in actual:
            json_exact(archives, actual[key], expected[key])
    elif isinstance(actual, list):
        require(
            isinstance(expected, list) and len(actual) == len(expected),
            "Typed/reference sequence differs",
        )
        for a, b in zip(actual, expected, strict=True):
            json_exact(archives, a, b)
    else:
        require(actual == expected, "Exact typed/reference scalar differs")


def phase_binding(binding, wrapped=None):
    if "composition" in binding:
        return phase_binding(binding["composition"], wrapped)
    if "calendar" in binding:
        return binding
    require(wrapped is not None and "phase_binding" in wrapped, "Actual SIM phase binding required")
    return wrapped["phase_binding"]


def phase_state(value):
    if "clock" in value:
        return value
    return phase_state(value["active"])


def phase_owner_cache(archives, binding, parent):
    cache = parent["network"]["network_cache"]
    index = cursor(parent)
    kind = binding["calendar"]["phase"]
    require(
        cache["source_phase"] == kind and cache["legacy_run_sim"] is (kind == "SIM"),
        "Actual owner phase/legacy flag differs",
    )
    require(
        cache["shared_absent"] == [] and cache["shared"]["rho_pump"] == 1,
        "Actual shared attribute presence/unit pump required",
    )
    for role in ROLES:
        enabled = cache["enabled"][role]
        saved = cache["handlers"][role]
        require(
            type(enabled) is bool and (saved is not None) is enabled,
            "Disabled/actual owner presence differs",
        )
        if not enabled:
            continue
        require(
            saved["role"] == role and saved["configuration_identity"],
            "Actual stable owner role required",
        )
        own = binding["inputs_raw"]["owners"]["handlers"][role]
        retained = saved["cache"]
        for population in own["catalog"]["populations"] or []:
            name = population["name"]
            active = kind == "SIM" or population.get("init active", True)
            require(
                retained["channel_calls"][name] == (index if active else 0),
                "Actual gate call epoch differs",
            )
            if not active:
                archives.exact(
                    retained["wire"]["channel_fields"][name],
                    retained["initial_channel_fields"][name],
                )
        if role == "molecules":
            configured = own["network"]["configuration"]["transporters"]
            fields = retained["wire"]["transporter_fields"]
            require(
                list(fields) == [row["name"] for row in configured or []],
                "Ordered transporter configuration differs",
            )
            require(
                retained["wire"]["owner_fields"]["transporters"] is (configured is not None),
                "Null/empty transporter flag differs",
            )
            for item in fields.values():
                require(
                    (item["flux"] is not None) is (index > 0),
                    "Actual rebuilt transporter flux epoch differs",
                )
    for key in ("gj_block", "NaKATP_block"):
        archives.exact(parent["network"]["controls"][key], parent["stores"][key])
        archives.exact(cache["shared"][key], parent["stores"][key])


def phase_parent(archives, binding, parent, *, clock_forms=None):
    require(set(parent) == set(PHASE_FIELDS), "Complete phase State schema required")
    cal = binding["calendar"]
    index = cursor(parent)
    count = cal["step_count"]
    limit = binding["call_limit"]
    dt = cal["dt_s"]
    require(
        set(parent["clock"]) == {"call_index", "material_dt_sum_s", "source_times_s"}
        and array(parent["clock"]["source_times_s"])
        and (parent["clock"]["source_times_s"]["dtype"] == "<f8")
        and (parent["clock"]["source_times_s"]["shape"] == [count]),
        "Complete typed original phase clock required",
    )
    require(
        type(index) is int and 0 <= index <= limit <= min(3, count),
        "Phase cursor outside actual bounded source calendar",
    )
    require(
        parent["binding_identity"] == binding["identity"],
        "Actual phase binding association differs",
    )
    require(
        parent["network"]["binding_identity"] == binding["identity"]
        and parent["field"]["binding_identity"] == binding["identity"],
        "Network/field ownership differs",
    )
    require(
        set(parent["network"])
        == {"binding_identity", "material", "network_cache", "controls", "identity"}
        and set(parent["network"]["material"])
        == {"binding_identity", "step_index", "values", "identity"},
        "Complete network/material records required",
    )
    require(
        set(parent["network"]["material"]["values"]) == set(MATERIAL_FIELDS),
        "Every complete ordinary material buffer required",
    )
    require(
        all(
            (
                array(value) and value["dtype"] == "<f8"
                for value in parent["network"]["material"]["values"].values()
            )
        ),
        "Typed float64 material buffers required",
    )
    require(
        set(parent["field"]) == set(FIELD_FIELDS),
        "Complete actual reconstructed field record required",
    )
    require(
        parent["network"]["material"]["step_index"] == parent["mechanics"]["step_index"] == index,
        "Phase material/mechanics cursor differs",
    )
    require(parent["clock"]["material_dt_sum_s"] == index * dt, "Phase accumulated dt differs")
    require(
        parent["mechanics"]["sampled_steps"] == [],
        "Native mechanics/display sampling credit forbidden",
    )
    require(len(parent["history"]) == index, "Complete accepted phase journal required")
    labels = list(numeric_values(archives, parent["clock"]["source_times_s"]))
    require(len(labels) == count, "Original phase label axis changed")
    for j, row in enumerate(parent["history"]):
        require(type(row["sample_eligible"]) is bool, "Typed source sample flag required")
        require(
            row["call_index"] == j
            and row["source_label_s"] == labels[j]
            and (row["dt_s"] == dt)
            and (row["material_dt_sum_s"] == (j + 1) * dt),
            "Phase source label/dt receipt differs",
        )
        require(
            row["source_phase"] == cal["phase"]
            and row["legacy_run_sim"] is (cal["phase"] == "SIM"),
            "Phase receipt selector differs",
        )
        require(
            row["event_fire_calls"] == row["protein_noise_calls"] == 0,
            "Unqualified event/noise expansion",
        )
    samples = [j for j, row in enumerate(parent["history"]) if row["sample_eligible"]]
    require(
        [o["call_index"] for o in parent["observations"]] == samples,
        "Headless source sample selection differs",
    )
    for observation, j in zip(parent["observations"], samples, strict=True):
        require(
            observation["source_label_s"] == labels[j]
            and observation["elapsed_end_s"] == (j + 1) * dt,
            "Headless observation clock differs",
        )
        require(
            observation["native_storage_called"] is observation["display_completed"] is False,
            "Native storage/display credit forbidden",
        )
        require(
            set(observation) >= {"network", "field", "mechanics"},
            "Complete retained observation state required",
        )
        require(
            observation["network"]["material"]["step_index"]
            == observation["mechanics"]["step_index"]
            == j + 1
            and observation["network"]["binding_identity"]
            == observation["field"]["binding_identity"]
            == binding["identity"],
            "Observation source ownership/epoch differs",
        )
    status = "exhausted" if index == count else "capped" if index == limit else "ready"
    require(
        parent["status"] in {status, "paused" if status == "ready" else status},
        "Actual phase status differs from original cursor",
    )
    for key, present in (
        (
            "rate_cache",
            binding["setup_receipt"].get("entry_CaATP_present", False)
            or (index > 0 and binding["calcium"]["alpha_Ca"] > 0),
        ),
        ("nak_rate", binding["setup_receipt"].get("entry_NaK_present", False) or index > 0),
    ):
        value = parent[key]
        require(
            set(value) == {"present", "value"}
            and value["present"] is bool(present)
            and ((value["value"] is not None) is bool(present)),
            "Actual producer cache presence differs",
        )
        if present:
            raw = value["value"]
            membranes = binding["material_binding"]["geometry_binding"]["current_binding"][
                "membrane_ids"
            ]
            require(
                array(raw)
                and raw["dtype"] == "<f8"
                and (raw["shape"] == [len(membranes)])
                and all((math.isfinite(v) for v in archives.values(raw))),
                "Complete finite original producer rate buffer required",
            )
    phase_owner_cache(archives, binding, parent)
    if clock_forms:
        for form in clock_forms:
            expected = dict(form["clock"], call_index=index, material_dt_sum_s=index * dt)
            json_exact(archives, parent["clock"], expected)
            require(
                samples == [j for j in form["sample_indices"] if j < index],
                "Independent sample recurrence differs",
            )
    return parent


def complete_init(archives, value):
    require(
        set(value) == {"binding", "parent", "scope", "identity"},
        "Complete original INIT artifact required",
    )
    binding = value["binding"]
    parent = value["parent"]
    phase_parent(archives, binding, parent)
    require(
        binding["calendar"]["phase"] == "INIT"
        and parent["status"] == "exhausted"
        and (cursor(parent) == binding["calendar"]["step_count"] == binding["call_limit"]),
        "Incomplete INIT artifact cannot cross phases",
    )
    return value


def sim_parent(archives, binding, parent, *, clock_forms=None):
    require(
        set(parent)
        == {"binding_identity", "source_init", "phase_binding", "active", "receipt", "identity"},
        "Complete actual SimPhase required",
    )
    require(parent["binding_identity"] == binding["identity"], "SIM transition binding differs")
    complete_init(archives, parent["source_init"])
    require(
        parent["source_init"]["binding"]["identity"] == binding["expected_init_identity"],
        "Foreign source INIT binding",
    )
    require(parent["phase_binding"]["calendar"]["phase"] == "SIM", "SIM phase selector differs")
    phase_parent(archives, parent["phase_binding"], parent["active"], clock_forms=clock_forms)
    archives.exact(parent["receipt"]["old_INIT_clock"], parent["source_init"]["parent"]["clock"])
    if cursor(parent) == 0:
        for key in ("rate_cache", "nak_rate"):
            archives.exact(parent["active"][key], parent["source_init"]["parent"][key])
    return parent


def completed_run(archives, value):
    require(
        set(value) == {"binding", "run", "complete_init", "identity"},
        "Complete INIT run artifact required",
    )
    run_parent(archives, value["binding"], value["run"])
    require(
        value["run"]["status"] == "exhausted", "Failed/paused/capped outer INIT cannot complete"
    )
    complete_init(archives, value["complete_init"])
    archives.exact(value["run"]["active"], value["complete_init"]["parent"])
    require(
        value["binding"]["composition"]["identity"]
        == value["complete_init"]["binding"]["identity"],
        "Complete INIT run/source binding differs",
    )
    return value


def run_parent(archives, binding, parent, *, clock_forms=None):
    require(set(parent) == set(RUN_FIELDS), "Complete owned RunState schema required")
    require(parent["binding_identity"] == binding["identity"], "Actual owned run binding differs")
    component = binding["composition"]
    entry = parent["entry"]
    active = parent["active"]
    phase = phase_binding(component, active)
    if "source_init" in active:
        sim_parent(archives, component, entry)
        sim_parent(archives, component, active, clock_forms=clock_forms)
    else:
        phase_parent(archives, component, entry)
        phase_parent(archives, component, active, clock_forms=clock_forms)
    require(cursor(entry) == 0, "Outer supplied entry cannot be advanced/rebased")
    receipt = parent["entry_receipt"]
    require(
        set(receipt)
        == {
            "kind",
            "composition_binding_identity",
            "composition_state_identity",
            "source_calendar_identity",
            "source_call",
            "phase",
            "mode",
            "provenance",
            "previous_phase",
            "installed_native_initializer_called",
            "native_load_called",
            "physical_seed_claim",
            "declaration_is_initialization_attestation",
        }
        and receipt["kind"] == "cells.supplied_molecule_phase_entry_declaration@1"
        and (receipt["mode"] == "supplied_molecule54_phase_entry")
        and isinstance(receipt["provenance"], str)
        and receipt["provenance"].strip()
        and all(
            (
                receipt[key] is False
                for key in (
                    "installed_native_initializer_called",
                    "native_load_called",
                    "physical_seed_claim",
                    "declaration_is_initialization_attestation",
                )
            )
        ),
        "Complete supplied-entry scope required without native/physical initialization claims",
    )
    require(
        receipt["composition_binding_identity"] == component["identity"]
        and receipt["composition_state_identity"] == entry["identity"],
        "Supplied entry receipt association differs",
    )
    require(
        receipt["phase"] == phase["calendar"]["phase"]
        and receipt["source_call"] == 0
        and (receipt["source_calendar_identity"] == phase["calendar"]["identity"]),
        "Original entry phase/calendar differs",
    )
    if receipt["previous_phase"] is not None:
        completed_run(archives, receipt["previous_phase"])
        archives.exact(entry["source_init"], receipt["previous_phase"]["complete_init"])
    index = cursor(active)
    history = parent["history"]
    dt = phase["calendar"]["dt_s"]
    require(len(history) == index, "Outer journal/cursor differs")
    previous = entry["identity"]
    samples = []
    labels = list(numeric_values(archives, phase_state(active)["clock"]["source_times_s"]))
    for j, row in enumerate(history):
        require(
            row["call_index"] == j and row["before_identity"] == previous,
            "Outer call chain differs",
        )
        require(
            row["source_label_s"] == labels[j]
            and row["dt_s"] == dt
            and (row["elapsed_start_s"] == j * dt)
            and (row["elapsed_end_s"] == (j + 1) * dt),
            "Outer original label/dt window differs",
        )
        require(type(row["sample_eligible"]) is bool, "Typed source sample eligibility required")
        if row["sample_eligible"]:
            samples.append(j)
        previous = row["after_identity"]
    require(previous == active["identity"], "Outer active identity is not the last accepted call")
    require(
        [o["call_index"] for o in parent["observations"]] == samples,
        "Outer sample ownership differs",
    )
    for observation, j in zip(parent["observations"], samples, strict=True):
        require(
            set(observation)
            == {
                "call_index",
                "source_label_s",
                "elapsed_end_s",
                "state",
                "native_write2storage_called",
                "native_display_completed",
                "mode",
            }
            and observation["mode"] == "headless_observation_at_native_sample_boundary"
            and (type(observation["call_index"]) is int)
            and (observation["source_label_s"] == history[j]["source_label_s"])
            and (observation["elapsed_end_s"] == history[j]["elapsed_end_s"]),
            "Complete original headless observation/clock scope required",
        )
        require(
            observation["state"]["identity"] == history[j]["after_identity"],
            "Observation did not retain reached state",
        )
        require(
            cursor(observation["state"]) == j + 1,
            "Observation state cursor differs from its accepted call",
        )
        require(
            observation["native_write2storage_called"]
            is observation["native_display_completed"]
            is False,
            "Native display/storage credit forbidden",
        )
        if "source_init" in observation["state"]:
            sim_parent(archives, component, observation["state"])
        else:
            phase_parent(archives, component, observation["state"])
    expected = (
        "exhausted"
        if index == phase["calendar"]["step_count"]
        else "capped"
        if phase_state(active)["status"] == "capped"
        else "ready"
    )
    require(
        parent["status"] in {expected, "failed", "paused" if expected == "ready" else expected},
        "Outer run status/cursor differs",
    )
    return parent


def named_negative(archives, case, outcome, native, partial, raw, *, run):
    chain = outcome["available"]["exception_chain"]
    names = ["RunRejected"] if run else []
    names += ["InitRejected", "ECMTransportRejected", "BetseSimUnstableException"]
    require(
        [row["type"] for row in chain] == names, "Original negative-X wrapper/cause chain differs"
    )
    message = "Network concentration of X in cells below zero! Your simulation has become unstable."
    require(
        chain[-1]["message"] == native["failure"]["message"] == message
        and native["failure"]["type"] == "BetseSimUnstableException",
        "Named negative-X native cause differs",
    )
    require(
        native["status"] == "source_refused"
        and native["failure_capture"]
        and (not native["capture_errors"]),
        "Complete actual native refusal required",
    )
    require(
        partial["stage"] == "material_calcium_network_mechanics"
        and partial["reached_stage"] == "network"
        and (partial["call_index"] == 0)
        and (partial["root_cause"]["type"] == "ECMTransportRejected"),
        "Original failed component stage differs",
    )
    buffers = partial["owner_buffers"]
    require(not buffers["capture_errors"], "Incomplete owner partial")
    for key in ("material", "partial_wires"):
        archives.exact(buffers[key], native["partial_buffers"][key])
    archives.exact(buffers["source_order"], native["order"])
    role = "molecules" if "general" in case else "grn"
    target = [r for r in buffers["traces"][role]["mover_frames"] if r["species"] == "X"]
    require(
        target
        and target[-1]["stage"] == "environment_mix"
        and any((v < 0 for v in numeric_values(archives, target[-1]["fields"]["cX_cells"]))),
        "Actual last negative environment-mix witness missing",
    )
    for owner in ROLES:
        for key in ("molecule_frames", "mover_frames", "channel_events", "rhs", "control_writes"):
            archives.exact(buffers["traces"][owner][key], native["traces"][owner][key])
    archives.exact(
        buffers["traces"]["molecules"]["transporter_frames"],
        native["traces"]["molecules"]["transporter_frames"],
    )
    configured = raw["owners"]["handlers"]["molecules"]["network"]["configuration"]["transporters"]
    require(
        [
            (row["stage"], row["name"])
            for row in buffers["traces"]["molecules"]["transporter_frames"]
        ]
        == [
            (stage, row["name"])
            for row in configured
            for stage in ("before", "flux", "current", "reactant_commit", "product_commit", "after")
        ],
        "Original configured transporter failure-prefix order differs",
    )
    ions = raw["field"]["definition"]["environment_geometry_definition"]["current_definition"][
        "ions"
    ]["ids"]
    require(
        [(row["stage"], row["species"]) for row in buffers["traces"][role]["molecule_frames"]]
        == [("molecule_intra", "X"), ("molecule_intra", "Y"), ("rhs_ready", None)]
        + [("chemical_commit", ion) for ion in ions]
        + [("chemical_commit", "X"), ("transport_before", "X")],
        "Original last-negative molecule/ion statement prefix differs",
    )


def call_native(archives, phase, active, detail, native):
    require(
        native["status"] == "source_completed" and (not native["capture_errors"]),
        "Complete native owner call required",
    )
    archives.exact(detail["before_commit"]["values_before"], native["returned"]["material"])
    archives.exact(detail["network"]["shared_after"], native["returned"]["shared"])
    caches = active["network"]["network_cache"]
    for role in ROLES:
        saved = caches["handlers"][role]
        archives.exact(
            None if saved is None else saved["cache"], native["returned"]["handlers"][role]
        )
    archives.exact(detail["network"]["source_order"], native["order"])
    archives.exact(detail["network"]["shared_after"], caches["shared"])
    require(
        detail["receipt"]["call_index"] == cursor(active) - 1,
        "Actual component receipt epoch differs",
    )


def preparation_count(case, category, init_count=3):
    if category == "positive":
        windows = {
            "window_1_then_3": 2,
            "window_2_then_3": 2,
            "window_each_call": 3,
            "empty_prefix_then_all": 2,
        }.get(case, 1)
        return windows + (windows if init_count == 3 else 1)
    if category == "raw":
        return int(case.startswith("warm_"))
    if category == "observer":
        return int(case == "headless_observation")
    if category == "prefix":
        return int(case != "failed_INIT")
    if case == "foreign_previous_phase":
        return 3
    return int(
        case
        in {
            "entry_advanced",
            "changed_journal",
            "rebased_source_label",
            "changed_observation",
            "changed_completed_INIT",
            "stop_before_cursor",
            "terminal_step",
        }
    )
