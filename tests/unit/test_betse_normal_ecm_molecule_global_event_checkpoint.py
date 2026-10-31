"""Global checkpoint configuration/order controls; real event/model calls blocked."""

import ast
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import synthetic_owner
from validation.betse import betse_normal_ecm_molecule_global_event_checkpoint as global_events


def template():
    return dict(
        case_id="combined",
        provenance="Existing combined fixture metadata",
        event_owner=dict(
            global_options=dict(
                K_env=[0.5, 2.0, 0.7, 0.02],
                Cl_env=[0.5, 2.0, 0.7, 0.015],
                Na_env=[0.5, 2.0, 0.7, 0.01],
                T_change=[0.5, 2.0, 0.7, 0.01],
                gj_block=[0.5, 2.0, 0.7, 100],
                NaKATP_block=[0.5, 2.0, 0.7],
            ),
            scheduled_options=dict(Na_mem=[1], K_mem=[1], Cl_mem=0, Ca_mem=0, pressure=[1], ecmJ=0),
            callbacks={"P": {"source_function": "None"}},
            voltage={"peak_voltage": 1},
            owners={"membrane_ids": ["m0", "m1", "m2", "m3"]},
            configured_environment={"K": 4, "Cl": 5, "Na": 6, "M": 7},
            tissue_default={"kept": True},
            tissue_target_inds={"all": [0, 1, 2, 3]},
            cell_target_inds={"all": [0, 1]},
            env_target_inds={"all": [0, 1]},
            handler_fields={"old": "not a runtime store"},
        ),
    )


@pytest.mark.parametrize("scenario", global_events.SCENARIOS)
def test_explicit_global_configuration_reuses_original_parameters_and_owners(scenario):
    raw = template()
    before = copy.deepcopy(raw)
    declared = global_events.program(raw, scenario, [0.0, 1.5, 3.0])
    assert raw == before
    a, b = raw["event_owner"], declared["event_owner"]
    for key in (
        "owners",
        "configured_environment",
        "tissue_default",
        "tissue_target_inds",
        "cell_target_inds",
        "env_target_inds",
    ):
        assert a[key] == b[key]
    assert all(value == 0 for value in b["scheduled_options"].values())
    assert b["callbacks"] == {} and b["voltage"] is None
    for key in global_events.GLOBAL_ORDER:
        if key not in global_events.CONFIGURATIONS[scenario]:
            assert b["global_options"][key] == 0
            continue
        original = a["global_options"][key]
        row = b["global_options"][key]
        assert row[2] == original[2]
        if scenario == "global_boundaries":
            assert row[:2] == [1.5, 3.0]
        else:
            assert row[:2] == original[:2]
        if scenario == "global_salts_signed_reversal":
            assert row[3] == -original[3]
        elif len(row) == 4:
            assert row[3] == original[3]
    if scenario == "global_salts_reversed_declaration":
        assert tuple(b["global_options"]) == tuple(reversed(global_events.GLOBAL_ORDER))
    if b["global_options"]["gj_block"] != 0:
        assert b["handler_fields"]["targets_gj_block"] == [0, 1, 2, 3]


@pytest.mark.parametrize("key", global_events.GLOBAL_ORDER)
def test_typed_run_scope_admits_each_existing_global_mechanism(key):
    binding, _ = synthetic_owner()
    binding.raw["event_owner"]["global_options"] = dict.fromkeys(global_events.GLOBAL_ORDER, 0)
    binding.raw["event_owner"]["global_options"][key] = template()["event_owner"]["global_options"][
        key
    ]
    run.composition.event_scope(binding)


@pytest.mark.parametrize(
    "mechanism", ["pressure", "membrane", "ecmJ", "callback", "voltage", "unknown-global"]
)
def test_non_global_noise_or_native_scope_is_not_opened(mechanism):
    binding, _ = synthetic_owner()
    owner = binding.raw["event_owner"]
    if mechanism == "pressure":
        owner["scheduled_options"]["pressure"] = [1]
    elif mechanism == "membrane":
        owner["scheduled_options"]["Na_mem"] = [1]
    elif mechanism == "ecmJ":
        owner["scheduled_options"]["ecmJ"] = [1]
    elif mechanism == "callback":
        owner["callbacks"]["Na"] = {"function": "unowned"}
    elif mechanism == "voltage":
        owner["voltage"] = {"peak": 1}
    else:
        owner["global_options"]["unowned"] = 0
    with pytest.raises(ValueError, match="deterministic global|finalized constant"):
        run.composition.event_scope(binding)


def stamp(name, category="scalar", shape=()):
    return dict(
        fingerprint=name,
        category=category,
        shape=list(shape),
        dtype="<f8" if category != "scalar" else None,
    )


def stores_observation(scenario="global_combined"):
    declared = global_events.program(template(), scenario, [0.0, 1.5, 3.0])
    options = declared["event_owner"]["global_options"]
    entry = {
        key: stamp("entry-" + key, "array", (4,))
        if key in ("gj_block", "NaKATP_block")
        else stamp("T" if key == "T" else "bath", "array", (6,))
        if key == "c_env_bound"
        else stamp("T")
        for key in global_events.STORES
    }
    rows = []
    for i in range(3):
        after = {
            key: stamp(key + str(i), "array", (4,))
            if key == "gj_block"
            else stamp(key + str(i), "array", (6,))
            if key == "c_env_bound"
            else stamp(key + str(i), "numpy_scalar")
            if key == "NaKATP_block"
            else stamp("T" + str(i) if options["T_change"] != 0 else "T")
            for key in global_events.STORES
        }
        before = copy.deepcopy(entry)
        if options["T_change"] == 0:
            before["T"] = stamp("T")
        rows.append(
            dict(global_before=before, global_after=after, events_after=copy.deepcopy(after))
        )
    value = dict(
        cursor=3,
        rows=rows,
        global_options=copy.deepcopy(options),
        post_owner_controls={
            key: stamp("post-owner-" + key) for key in ("gj_block", "NaKATP_block")
        },
        transport=dict.fromkeys(
            (
                "material",
                "rate",
                "NaK_rate",
                "field",
                "runtime_binding",
                "runtime_definition",
                "owner_caches",
                "all_stores",
            ),
            "full-state",
        ),
    )
    anchor = dict(global_options=options, entry_global=entry)
    return value, anchor


def test_global_and_post_owner_epochs_are_retained_separately():
    value, anchor = stores_observation()
    assert global_events.check_stores(value, anchor) is value
    assert (
        value["rows"][-1]["global_after"]["NaKATP_block"]
        != value["post_owner_controls"]["NaKATP_block"]
    )
    assert value["rows"][-1]["global_after"]["gj_block"] != value["post_owner_controls"]["gj_block"]


@pytest.mark.parametrize(
    "fault",
    [
        "NaK-vector",
        "GJ-axis",
        "missing-epoch",
        "missing-rate",
        "missing-post-owner",
        "changed-config",
        "no-salt-effect",
        "no-pump-effect",
        "unconfigured-T",
        "NaK-entry-scalar",
    ],
)
def test_missing_store_rate_or_source_shape_cannot_be_hidden(fault):
    value, anchor = stores_observation(
        "global_salts" if fault == "unconfigured-T" else "global_combined"
    )
    if fault == "NaK-vector":
        value["rows"][0]["global_after"]["NaKATP_block"] = stamp("wrong", "array", (4,))
    elif fault == "GJ-axis":
        value["rows"][0]["global_after"]["gj_block"]["shape"] = [2]
    elif fault == "missing-epoch":
        value["rows"][0]["events_after"].pop("c_env_bound")
    elif fault == "missing-rate":
        value["transport"].pop("rate")
    elif fault == "missing-post-owner":
        value["post_owner_controls"].pop("NaKATP_block")
    elif fault == "changed-config":
        value["global_options"]["Na_env"][3] = -1
    elif fault == "unconfigured-T":
        value["rows"][0]["global_after"]["T"] = stamp("changed")
    elif fault == "NaK-entry-scalar":
        anchor["entry_global"]["NaKATP_block"] = stamp("wrong-entry")
    else:
        field = "c_env_bound" if fault == "no-salt-effect" else "NaKATP_block"
        for row in value["rows"]:
            row["global_after"][field]["fingerprint"] = "unchanged"
    with pytest.raises(ValueError):
        global_events.check_stores(value, anchor)


def source_file():
    return Path(run.composition.events.events.__file__)


def test_literal_source_branch_order_is_bound_without_running_a_law(tmp_path):
    binding = global_events.source_order(source_file())
    assert tuple(row["key"] for row in binding["branches"]) == global_events.GLOBAL_ORDER
    tree = ast.parse(source_file().read_bytes())
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TissueHandler"
    )
    fn = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "_fire_events_global"
    )
    indices = [i for i, node in enumerate(fn.body) if isinstance(node, ast.If)]
    a, b = indices[:2]
    fn.body[a], fn.body[b] = fn.body[b], fn.body[a]
    changed = tmp_path / "changed-source.py"
    changed.write_text(ast.unparse(tree))
    with pytest.raises(ValueError, match="ordering changed"):
        global_events.source_order(changed)


def pulse_records(options):
    return dict(
        global_profile_complete=True,
        global_dispatches=[
            dict(
                label=label,
                exited=True,
                pulses=[
                    dict(
                        key=key,
                        parameters=[label, *options[key][:3]],
                        returned=True,
                        value=0.01 if label == 0 else 0.9 if label == 1.5 else 0.02,
                    )
                    for key in global_events.GLOBAL_ORDER
                    if options[key] != 0
                ],
            )
            for label in [0.0, 1.5, 3.0] * 2
        ],
    )


@pytest.mark.parametrize(
    "fault", [None, "reverse", "duplicate", "omit", "onset", "release-tail", "unwind", "clock"]
)
def test_real_source_order_contract_rejects_wrong_or_missing_observations(fault):
    options = global_events.program(template(), "global_salts", [0.0, 1.5, 3.0])["event_owner"][
        "global_options"
    ]
    report = pulse_records(options)
    group = report["global_dispatches"][0]
    if fault == "reverse":
        group["pulses"].reverse()
    elif fault == "duplicate":
        group["pulses"].append(copy.deepcopy(group["pulses"][0]))
    elif fault == "omit":
        group["pulses"].pop()
    elif fault == "onset":
        group["pulses"][0]["parameters"][1] = 1
    elif fault == "release-tail":
        group["pulses"][0]["value"] = float("nan")
    elif fault == "unwind":
        group["pulses"][0]["returned"] = False
    elif fault == "clock":
        group["label"] = 5
    if fault is None:
        global_events.check_pulses(report, options, [0.0, 1.5, 3.0])
        assert (
            report["global_dispatches"][2]["pulses"][0]["value"] == 0.02
        )  # Never truncate a tail.
    else:
        with pytest.raises(ValueError):
            global_events.check_pulses(report, options, [0.0, 1.5, 3.0])


def test_observer_reads_synthetic_frames_and_retains_partial_unwind(tmp_path):
    class Base:
        def __init__(self, stream):
            self.stream = stream

        def observe(self, *args):
            pass

        def stop(self):
            return dict(profile_intact=True)

    observed = global_events.observer(Base, io.StringIO(), source_file(), tmp_path)
    bound = global_events.source_order(source_file())
    namespace = {"__name__": "cells.processes.betse_normal_ecm_event_join_source"}
    parent = SimpleNamespace(
        f_globals=namespace,
        f_code=SimpleNamespace(co_name="_fire_events_global"),
        f_locals={"t": 3.0},
        f_lineno=bound["branches"][0]["line"],
    )
    child = SimpleNamespace(
        f_globals=namespace,
        f_code=SimpleNamespace(co_name="pulse"),
        f_back=parent,
        f_locals=dict(t=3.0, t_on=0.5, t_off=2.0, t_change=0.7),
    )
    observed.observe(parent, "call", None)
    observed.observe(child, "call", None)
    observed.observe(child, "return", None)  # An unwind is not a successful scalar return.
    observed.observe(parent, "return", None)
    report = observed.stop()
    assert report["global_profile_complete"]
    assert report["global_dispatches"][0]["pulses"][0]["returned"] is False
    rows = [json.loads(row) for row in (tmp_path / "global-pulses.jsonl").read_text().splitlines()]
    assert len(rows) == 2 and rows[0]["event"] == "entry" and rows[1]["value"] is None


def test_global_journal_closes_when_base_accounting_fails(tmp_path):
    primary = OSError("synthetic base accounting refusal")

    class Base:
        def __init__(self, stream):
            self.stream = stream

        def observe(self, *args):
            pass

        def stop(self):
            raise primary

    observed = global_events.observer(Base, io.StringIO(), source_file(), tmp_path)
    with pytest.raises(OSError, match="synthetic base accounting refusal") as caught:
        observed.stop()
    assert caught.value is primary and observed.pulse_stream.closed
