"""Synthetic membrane callback/owner/continuation controls; actual entry blocked."""

import ast
import copy
import io
import json
import sys
from pathlib import Path
from types import CellType, CodeType, FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import synthetic_owner
from tests.unit.test_betse_normal_ecm_molecule_global_event_checkpoint import stamp, template
from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation
from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

setup = run.composition.lifecycle.setup


@pytest.fixture(autouse=True)
def block_actual_finalizers_callbacks_and_factories(no_actual_execution, request, monkeypatch):
    # Inspect original code objects, but never execute their finalizers or lambdas.
    codes = {
        setup.source._finalize_events_tissue.__code__,
        setup.source._finalize_events_global.__code__,
        run.composition.events.events.prepared_callback.__code__,
    }
    codes.update(setup.constant_callback_code(suffix) for suffix in setup.CONSTANT_SUFFIXES)
    codes.update(
        code
        for code in run.composition.events.events.prepared_callback.__code__.co_consts
        if type(code) is CodeType
    )
    original = sys.getprofile()

    if (
        request.node.originalname
        == "test_membrane_prerequisite_refusal_keeps_failed_parent_cause_partial_and_accounting"
    ):
        # The existing invocation observer must own the single profiler in these
        # failure-only stub controls. Actual producers are still all forbidden.
        def forbidden(*args, **kwargs):
            no_actual_execution.append("actual finalizer/callback/factory")
            raise AssertionError("Actual finalizer/callback execution forbidden")

        monkeypatch.setattr(setup.source, "_finalize_events_tissue", forbidden)
        monkeypatch.setattr(setup.source, "_finalize_events_global", forbidden)
        monkeypatch.setattr(run.composition.events.events, "prepared_callback", forbidden)
        yield
        assert sys.getprofile() is original
        return

    def blocked(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            no_actual_execution.append("actual finalizer/callback/factory")
            raise AssertionError("Actual finalizer/callback execution forbidden")

    sys.setprofile(blocked)
    try:
        yield
    finally:
        sys.setprofile(original)


def sim_template():
    owner = template()["event_owner"]
    return dict(
        provenance="Synthetic unowned setup metadata",
        sim_phase=dict(
            time_profile=dict(
                phase="SIM",
                init_total_s=0.0,
                init_dt_s=1.0,
                init_sampling_s=1.0,
                sim_total_s=3.25,
                sim_dt_s=1.0,
                sim_sampling_s=1.0,
                provenance="Original N3 metadata",
            ),
            setup=dict(
                global_options=owner["global_options"],
                scheduled_options=owner["scheduled_options"],
                maps=dict(
                    tissue_target_inds=dict(all=[0, 1, 2, 3], region0=[2, 0]),
                    cell_target_inds={"all": [0, 1]},
                    env_target_inds={"all": [0, 1]},
                ),
            ),
            unchanged="complete original fixture/config inputs",
        ),
    )


@pytest.mark.parametrize("scenario", membrane.SCENARIOS)
def test_new_declarations_precede_actual_finalization_without_callback_hydration(scenario):
    raw = sim_template()
    original = copy.deepcopy(raw)
    value = membrane.configure_sim(raw, scenario)
    assert raw == original
    assert value["sim_phase"]["unchanged"] == raw["sim_phase"]["unchanged"]
    setup_row = value["sim_phase"]["setup"]
    assert setup_row["maps"] == raw["sim_phase"]["setup"]["maps"]
    assert "callbacks" not in setup_row and "constant_callback_authority" not in setup_row
    assert setup_row["scheduled_options"]["pressure"] == setup_row["scheduled_options"]["ecmJ"] == 0
    selected = [k for k, row in setup_row["scheduled_options"].items() if row != 0]
    assert selected == (
        [scenario.removeprefix("membrane_")]
        if scenario in membrane.CONDITIONS[:4]
        else list(membrane.MEMBRANE_KEYS)
    )
    for key in selected:
        row = setup_row["scheduled_options"][key]
        assert row[:4] == (
            [1.5, 3.0, 0.7, 0.15] if scenario == "membrane_boundaries" else [0.5, 2.0, 0.7, 0.15]
        )
        assert row[5] == "None"
    if scenario != "membrane_mixed_global":
        assert all(v == 0 for v in setup_row["global_options"].values())
    else:
        assert all(v != 0 for v in setup_row["global_options"].values())
    if scenario == "membrane_duplicate_targets":
        assert setup_row["scheduled_options"]["Na_mem"][4] == ["region0", "region0", "all"]
    if scenario == "membrane_empty_targets":
        assert setup_row["scheduled_options"]["Na_mem"][4] == []


def test_missing_profile_is_refused_without_inference():
    raw = sim_template()
    del raw["sim_phase"]["setup"]["maps"]["tissue_target_inds"]["region0"]
    with pytest.raises(ValueError, match="Missing actual supplied profile"):
        membrane.configure_sim(raw, "membrane_duplicate_targets")


@pytest.mark.parametrize("suffix", tuple(membrane.MEMBRANE_KEYS.values()))
def test_literal_constant_callable_identity_is_inspected_without_evaluation(suffix):
    code = setup.constant_callback_code(suffix)
    # This manufactured function is unowned and is never submitted to admission.
    function = FunctionType(code, vars(setup.source))
    synthetic = SimpleNamespace(**{"dyna_" + suffix: function, "scalar_" + suffix: 1})
    authority = setup.constant_callback_record(suffix, synthetic)
    assert authority == setup.constant_callback_record(suffix)
    assert authority["evaluated"] is False and authority["source_scalar"] == 1
    assert authority["source_sha256"] == checkpoint._sha(Path(setup.source.__file__))


@pytest.mark.parametrize("suffix", tuple(membrane.MEMBRANE_KEYS.values()))
def test_restart_record_is_closed_metadata_on_the_retained_typed_owner(tmp_path, suffix):
    binding, _ = synthetic_binding("membrane_combined")
    object.__setattr__(binding.base, "calendar", dict(phase="SIM"))
    authority = binding.base.setup_receipt["event_finalization"]["source_fields"][
        "constant_callback_authority"
    ][suffix]
    assert set(authority) == {
        "kind",
        "suffix",
        "source_module",
        "source_sha256",
        "source_line",
        "bytecode_sha256",
        "source_function",
        "source_scalar",
        "dynamic",
        "evaluated",
    }
    assert all(type(value) in (str, int, bool, dict) for value in authority.values())
    assert authority["dynamic"] == {"kind": "constant"}
    graph = dict(typed_setup_owner=binding.base, same_record=authority)
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(graph)
    encoder.write(tmp_path, tree)
    loaded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    retained = loaded["typed_setup_owner"].setup_receipt["event_finalization"]["source_fields"][
        "constant_callback_authority"
    ][suffix]
    assert type(loaded["typed_setup_owner"]) is run.composition.phase.Binding
    assert retained is loaded["same_record"]
    assert checkpoint.codec.fingerprint(loaded) == checkpoint.codec.fingerprint(graph)
    # Structural transport supplies no actual setup/phase or parent admission.
    assert not isinstance(loaded["typed_setup_owner"], run.RunState)


@pytest.mark.parametrize("kind", ["function", "code", "globals", "module", "closure_cell"])
def test_restart_record_refuses_live_executable_objects(kind):
    function = FunctionType(setup.constant_callback_code("Namem"), vars(setup.source))
    value = {
        "function": function,
        "code": function.__code__,
        "globals": function.__globals__,
        "module": setup.source,
        "closure_cell": CellType(1),
    }[kind]
    with pytest.raises(ValueError, match="Missing ownership/codec for runtime type"):
        checkpoint.codec.Encoder().capture(dict(unowned_executable=value))


@pytest.mark.parametrize("tag", ["function", "code", "closure"])
def test_restart_record_refuses_serialized_execution_nodes_without_running_them(tmp_path, tag):
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(None)
    encoder.write(tmp_path, tree)
    forged = dict(
        kind=checkpoint.codec.KIND,
        root=["ref", 0],
        nodes=[
            dict(
                tag=tag,
                source="raise AssertionError('Serialized execution forbidden')",
            )
        ],
    )
    with pytest.raises(ValueError, match="Unowned checkpoint node"):
        checkpoint.codec.decode(forged, (tmp_path / "arrays.npz").read_bytes())


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "foreign-code",
        "foreign-globals",
        "wrong-suffix",
        "defaults",
        "array",
        "numpy-scalar",
        "float",
        "zero",
    ],
)
def test_missing_or_foreign_actual_callback_is_not_repaired(fault):
    function = FunctionType(setup.constant_callback_code("Namem"), vars(setup.source))
    actual = SimpleNamespace(dyna_Namem=function, scalar_Namem=1)
    if fault == "missing":
        del actual.dyna_Namem
    elif fault == "foreign-code":
        actual.dyna_Namem = lambda t: 1
    elif fault == "foreign-globals":
        actual.dyna_Namem = FunctionType(function.__code__, {})
    elif fault == "wrong-suffix":
        actual.dyna_Namem = FunctionType(setup.constant_callback_code("Kmem"), vars(setup.source))
    elif fault == "defaults":
        actual.dyna_Namem = FunctionType(function.__code__, vars(setup.source), argdefs=(1,))
    else:
        actual.scalar_Namem = {
            "array": np.array(1),
            "numpy-scalar": np.int64(1),
            "float": 1.0,
            "zero": 0,
        }[fault]
    with pytest.raises(ValueError, match="actual finalized scalar-one"):
        setup.constant_callback_record("Namem", actual)


def synthetic_binding(scenario="membrane_combined"):
    binding, state = synthetic_owner()
    configuration = membrane.configure_sim(sim_template(), scenario)["sim_phase"]["setup"]
    owner = template()["event_owner"]
    owner.update(
        global_options=configuration["global_options"],
        scheduled_options=configuration["scheduled_options"],
        tissue_target_inds=configuration["maps"]["tissue_target_inds"],
        voltage=None,
    )
    owner["callbacks"] = {
        suffix: dict(
            source_function="None",
            source_scalar=1,
            dynamic=dict(kind="constant"),
            provenance="Synthetic unowned callback metadata",
        )
        for key, suffix in membrane.MEMBRANE_KEYS.items()
        if owner["scheduled_options"][key] != 0
    }
    owner["handler_fields"] = finalize_fields(
        owner["global_options"], owner["scheduled_options"], owner, 4
    )
    binding.raw["event_owner"] = owner
    authority = {suffix: setup.constant_callback_record(suffix) for suffix in owner["callbacks"]}
    binding.base.setup_receipt["event_finalization"]["source_fields"] = dict(
        owner=copy.deepcopy(owner),
        constant_callback_authority=authority,
        source_phase="SIM",
        legacy_run_sim=True,
        event_fire_calls=0,
    )
    from tests.unit.test_betse_normal_ecm_molecule_event_owner import attach_publication

    attach_publication(binding)
    return binding, state


@pytest.mark.parametrize("scenario", membrane.SCENARIOS)
def test_run_scope_requires_exact_retained_callback_config_and_target_authority(scenario):
    binding, _ = synthetic_binding(scenario)
    run.composition.event_scope(binding)  # Metadata boundary only; actual verify remains blocked.


@pytest.mark.parametrize(
    "fault",
    [
        "missing-owner",
        "missing-authority",
        "foreign-code-pin",
        "boolean-authority",
        "missing-callback",
        "foreign-callback",
        "changed-amplitude",
        "changed-times",
        "sorted-targets",
        "deduplicated-targets",
        "profile-order",
        "array-scalar",
        "float-scalar",
        "periodic",
        "pressure",
        "ecmJ",
        "voltage",
    ],
)
def test_changed_or_unowned_callback_config_targets_and_scope_refuse(fault):
    binding, _ = synthetic_binding("membrane_duplicate_targets")
    owner = binding.raw["event_owner"]
    fields = binding.base.setup_receipt["event_finalization"]["source_fields"]
    if fault == "missing-owner":
        del fields["owner"]
    elif fault == "missing-authority":
        del fields["constant_callback_authority"]
    elif fault == "foreign-code-pin":
        fields["constant_callback_authority"]["Namem"]["source_sha256"] = "0" * 64
    elif fault == "boolean-authority":
        fields["constant_callback_authority"]["Namem"]["evaluated"] = 0
    elif fault == "missing-callback":
        del owner["callbacks"]["Namem"]
    elif fault == "foreign-callback":
        owner["callbacks"]["Namem"]["provenance"] = "Changed callback owner"
    elif fault == "changed-amplitude":
        owner["scheduled_options"]["Na_mem"][3] *= 2
    elif fault == "changed-times":
        owner["scheduled_options"]["Na_mem"][0] += 0.1
    elif fault == "sorted-targets":
        owner["handler_fields"]["targets_Namem"].sort()
    elif fault == "deduplicated-targets":
        owner["handler_fields"]["targets_Namem"] = list(
            dict.fromkeys(owner["handler_fields"]["targets_Namem"])
        )
    elif fault == "profile-order":
        owner["handler_fields"]["apply_Namem"].reverse()
    elif fault in ("array-scalar", "float-scalar"):
        owner["callbacks"]["Namem"]["source_scalar"] = (
            np.array(1) if fault == "array-scalar" else 1.0
        )
    elif fault == "periodic":
        owner["scheduled_options"]["Na_mem"][5] = "periodic"
    elif fault in ("pressure", "ecmJ"):
        owner["scheduled_options"][fault] = [1]
    else:
        owner["voltage"] = {"unowned": 1}
    with pytest.raises(ValueError):
        run.composition.event_scope(binding)


def test_source_return_with_incomplete_owner_stays_refused_without_fixture_hydration():
    binding, _ = synthetic_binding()
    owner = binding.base.setup_receipt["event_finalization"]["source_fields"]["owner"]
    original = copy.deepcopy(owner)
    binding.base.setup_receipt["event_finalization"].pop("owner_publication")
    with pytest.raises(ValueError, match="Missing actual later event-owner publication"):
        membrane.declaration(binding.source_binding, binding.source_entry, "membrane_combined")
    assert owner == original


def source_file():
    return Path(run.composition.events.events.__file__)


def call_anchor(ion_ids=("Na", "K", "Cl", "Ca")):
    binding, _ = synthetic_binding("membrane_duplicate_targets")
    owner = binding.raw["event_owner"]
    return dict(
        scheduled_options=owner["scheduled_options"],
        ion_ids=list(ion_ids),
        labels=[0.0, 1.5, 3.0],
        targets={
            key: owner["handler_fields"]["targets_" + suffix]
            for key, suffix in membrane.MEMBRANE_KEYS.items()
        },
    )


def call_records(anchor):
    source = membrane.source_order(source_file())
    return dict(
        membrane_profile_complete=True,
        membrane_source_binding=source,
        membrane_dispatches=[
            dict(
                label=label,
                exited=True,
                events=[
                    row
                    for key in membrane.active_keys(anchor["scheduled_options"], anchor["ion_ids"])
                    for row in (
                        dict(
                            key=key,
                            operation="callback",
                            returned=True,
                            value=1,
                            parameters=[label],
                            targets=anchor["targets"][key],
                            scalar_type="int",
                            scalar=1,
                            callback_source_sha256=source["sha256"],
                            callback_line=source["constant_callback_line"],
                            callback_runtime_code_matches=True,
                        ),
                        dict(
                            key=key,
                            operation="pulse",
                            returned=True,
                            value=0.02 if label == 3.0 else 0.9,
                            parameters=[label, *anchor["scheduled_options"][key][:3]],
                        ),
                    )
                ],
            )
            for label in anchor["labels"] * 2
        ],
    )


@pytest.mark.parametrize(
    "ion_ids",
    [("Na", "K", "Cl", "Ca"), ("Na", "K", "Ca"), ("Na", "K", "Cl"), ("Na", "K"), ("Cl", "Ca")],
)
def test_literal_ion_presence_guards_and_nonzero_release_tail_are_retained(ion_ids):
    anchor = call_anchor(ion_ids)
    records = call_records(anchor)
    membrane.check_calls(records, anchor)
    keys = [
        r["key"] for r in records["membrane_dispatches"][0]["events"] if r["operation"] == "pulse"
    ]
    assert "Na_mem" in keys and "K_mem" in keys  # Unconditional native branches.
    assert ("Cl_mem" in keys) == ("Cl" in ion_ids)
    assert ("Ca_mem" in keys) == ("Ca" in ion_ids)
    assert records["membrane_dispatches"][2]["events"][1]["value"] == 0.02


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "omit",
        "reverse",
        "callback-order",
        "target-order",
        "deduplicate",
        "array-return",
        "scalar-type",
        "foreign-code",
        "foreign-runtime-code",
        "missing-return",
        "onset",
        "clock",
        "nonfinite",
        "partial",
    ],
)
def test_duplicate_omitted_or_foreign_actual_callback_pulse_records_refuse(fault):
    anchor = call_anchor()
    records = call_records(anchor)
    group = records["membrane_dispatches"][0]
    row = group["events"][0]
    if fault == "duplicate":
        group["events"].append(copy.deepcopy(row))
    elif fault == "omit":
        group["events"].pop()
    elif fault == "reverse":
        group["events"].reverse()
    elif fault == "callback-order":
        group["events"][0], group["events"][1] = group["events"][1], group["events"][0]
    elif fault == "target-order":
        row["targets"] = list(reversed(row["targets"]))
    elif fault == "deduplicate":
        row["targets"] = list(dict.fromkeys(row["targets"]))
    elif fault == "array-return":
        row["value"] = np.array(1)
    elif fault == "scalar-type":
        row["scalar_type"] = "float"
    elif fault == "foreign-code":
        row["callback_source_sha256"] = "0" * 64
    elif fault == "foreign-runtime-code":
        row["callback_runtime_code_matches"] = False
    elif fault == "missing-return":
        row["returned"] = False
    elif fault == "onset":
        group["events"][1]["parameters"][1] += 1
    elif fault == "clock":
        group["label"] = 2
    elif fault == "nonfinite":
        group["events"][1]["value"] = float("nan")
    else:
        records["membrane_profile_complete"] = False
    with pytest.raises(ValueError):
        membrane.check_calls(records, anchor)


def test_literal_membrane_order_and_prepared_constant_source_are_bound(tmp_path):
    binding = membrane.source_order(source_file())
    assert tuple(r["key"] for r in binding["branches"]) == membrane.MEMBRANE_ORDER
    tree = ast.parse(source_file().read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
    fn = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_fire_events_tissue"
    )
    fn.body[3], fn.body[4] = fn.body[4], fn.body[3]
    changed = tmp_path / "changed.py"
    changed.write_text(ast.unparse(tree))
    with pytest.raises(ValueError, match="ordering changed"):
        membrane.source_order(changed)


@pytest.mark.parametrize("foreign", [False, True])
def test_observer_retains_synthetic_callbacks_pulses_and_unwind_without_source_execution(
    tmp_path, foreign
):
    class Base:
        def __init__(self, stream):
            pass

        def observe(self, *args):
            pass

        def stop(self):
            return dict(profile_intact=True)

    observed = membrane.observer(Base, io.StringIO(), source_file(), tmp_path)
    bound = membrane.source_order(source_file())
    namespace = vars(run.composition.events.events)
    code = next(
        code
        for code in namespace["prepared_callback"].__code__.co_consts
        if type(code) is CodeType and code.co_firstlineno == bound["constant_callback_line"]
    )
    function = FunctionType(code, namespace)
    parent = SimpleNamespace(
        f_globals=namespace,
        f_code=SimpleNamespace(co_name="_fire_events_tissue"),
        f_locals=dict(
            t=3.0,
            self=SimpleNamespace(
                targets_Namem=[2, 0, 2, 0, 0, 1, 2, 3], scalar_Namem=1, dyna_Namem=function
            ),
        ),
        f_lineno=bound["branches"][0]["line"],
    )
    callback = SimpleNamespace(
        f_globals=namespace,
        f_code=code,
        f_locals={"t": 3.0},
        f_back=parent,
    )
    pulse = SimpleNamespace(
        f_globals=namespace,
        f_code=SimpleNamespace(co_name="pulse"),
        f_locals=dict(t=3.0, t_on=0.5, t_off=2.0, t_change=0.7),
        f_back=parent,
    )
    observed.observe(parent, "call", None)
    if foreign:
        callback.f_code = code.replace()
        with pytest.raises(ValueError, match="Foreign runtime constant callback identity"):
            observed.observe(callback, "call", None)
        report = observed.stop()
        assert not report["membrane_profile_complete"]
        assert observed.membrane_stream.closed and observed.pulse_stream.closed
        return
    observed.observe(callback, "call", None)
    observed.observe(callback, "return", 1)
    observed.observe(pulse, "call", None)
    observed.observe(pulse, "return", None)
    observed.observe(parent, "return", None)
    report = observed.stop()
    assert report["membrane_profile_complete"]
    rows = report["membrane_dispatches"][0]["events"]
    assert rows[0]["targets"] == [2, 0, 2, 0, 0, 1, 2, 3] and rows[0]["value"] == 1
    assert rows[1]["returned"] is False
    assert observed.membrane_stream.closed and observed.pulse_stream.closed
    evidence = [
        json.loads(line)
        for line in (tmp_path / "membrane-callbacks.jsonl").read_text().splitlines()
    ]
    assert len(evidence) == 4 and evidence[-1]["value"] is None


def test_both_observer_streams_close_when_existing_accounting_fails(tmp_path):
    primary = OSError("Synthetic accounting refusal")

    class Base:
        def __init__(self, stream):
            pass

        def observe(self, *args):
            pass

        def stop(self):
            raise primary

    observed = membrane.observer(Base, io.StringIO(), source_file(), tmp_path)
    with pytest.raises(OSError) as caught:
        observed.stop()
    assert (
        caught.value is primary and observed.membrane_stream.closed and observed.pulse_stream.closed
    )


def store_observations():
    anchor = call_anchor()
    anchor.update(
        membrane_count=4,
        callback_identity="actual-callback-config",
        callback_authority="actual-finalizer-code",
        entry_membrane={key: stamp(key, "array", (4, 4)) for key in membrane.STORES},
    )
    rows = []
    for i in range(3):
        before = {key: stamp(key + "before", "array", (4, 4)) for key in membrane.STORES}
        tissue = {
            key: stamp(key if key == "Dm_base" else key + str(i), "array", (4, 4))
            for key in membrane.STORES
        }
        tissue["Dm_base"] = before["Dm_base"]
        rows.append(
            dict(
                membrane=dict(
                    epochs=dict(
                        before=before,
                        global_=copy.deepcopy(before),
                        tissue=tissue,
                        combined=copy.deepcopy(tissue),
                    ),
                    untouched={
                        ion: dict(before="unselected", after="unselected")
                        for ion in anchor["ion_ids"]
                    },
                    scheduled_rows={
                        ion: stamp(ion + str(i), "array", (4,)) for ion in anchor["ion_ids"]
                    },
                    source_sum_consistent=True,
                )
            )
        )
        rows[-1]["membrane"]["epochs"]["global"] = rows[-1]["membrane"]["epochs"].pop("global_")
    value = dict(
        cursor=3,
        rows=rows,
        scheduled_options=copy.deepcopy(anchor["scheduled_options"]),
        callback_identity=anchor["callback_identity"],
        callback_authority=anchor["callback_authority"],
        post_owner_membrane={key: stamp("post-owner", "array", (4, 4)) for key in membrane.STORES},
    )
    return value, anchor


def test_full_source_epochs_and_post_owner_stores_are_distinct():
    value, anchor = store_observations()
    assert membrane.check_stores(value, anchor) is value
    assert value["post_owner_membrane"] != value["rows"][-1]["membrane"]["epochs"]["combined"]


def test_actual_array_observation_preserves_untargeted_values_and_complete_axes():
    anchor = call_anchor()
    anchor.update(membrane_count=4)
    anchor["targets"] = {key: [2, 0, 2] for key in membrane.MEMBRANE_KEYS}
    base = np.ones((4, 4))
    before = dict(Dm_base=base, Dm_scheduled=np.zeros((4, 4)), Dm_cells=base.copy())
    scheduled = np.zeros((4, 4))
    scheduled[:, [2, 0]] = 0.1  # Manufactured array, never a model source return.
    after = dict(Dm_base=base.copy(), Dm_scheduled=scheduled, Dm_cells=base + scheduled)
    trace = run.ions.freeze(
        dict(before=before, after=after, stages=[dict(state=before), dict(state=after)])
    )

    def array_stamp(value):
        return dict(
            fingerprint=checkpoint.codec.fingerprint(value),
            category="array",
            shape=list(value.shape),
            dtype=value.dtype.str,
        )

    observed = membrane.observe_row(trace, anchor, array_stamp, checkpoint.codec.fingerprint)
    assert all(row["before"] == row["after"] for row in observed["untouched"].values())
    assert observed["source_sum_consistent"]
    assert observed["epochs"]["tissue"]["Dm_scheduled"]["shape"] == [4, 4]
    scheduled[0, 1] = 0.5
    trace = run.ions.freeze(
        dict(before=before, after=after, stages=[dict(state=before), dict(state=after)])
    )
    observed = membrane.observe_row(trace, anchor, array_stamp, checkpoint.codec.fingerprint)
    assert observed["untouched"]["Na"]["before"] != observed["untouched"]["Na"]["after"]
    assert not observed["source_sum_consistent"]


def test_closed_codec_retains_callback_authority_duplicate_targets_full_event_stores_and_aliases(
    tmp_path,
):
    binding, state = synthetic_binding("membrane_duplicate_targets")
    # Remove only the synthetic namespaces, replacing them with plain metadata;
    # this is structural codec transport, never a phase/checkpoint admission.
    object.__setattr__(binding.base, "calendar", dict(phase="SIM"))
    object.__setattr__(state, "clock", dict(call_index=1))
    stores = {key: np.arange(16, dtype=np.float64).reshape(4, 4).copy() for key in membrane.STORES}
    object.__setattr__(state, "stores", stores)
    graph = dict(
        binding=binding,
        state=state,
        same_stores=stores,
        event_trace={"epochs": (1, 2), "failure": {"status": "retained_failed_prefix"}},
        sampling={"calendar": (0.0, 1.5, 3.0), "samples": (1,), "cursor": 1},
        RNG={
            "numpy": "retained actual manifest required",
            "python": "retained actual manifest required",
        },
    )
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(graph)
    encoder.write(tmp_path, tree)
    loaded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert checkpoint.codec.fingerprint(loaded) == checkpoint.codec.fingerprint(graph)
    assert loaded["state"].stores is loaded["same_stores"]
    actual = loaded["binding"].raw["event_owner"]
    assert actual["handler_fields"]["targets_Namem"] == [2, 0, 2, 0, 0, 1, 2, 3]
    assert not isinstance(loaded["state"], run.RunState)


@pytest.mark.parametrize(
    "fault",
    [
        "config",
        "callback",
        "authority",
        "post-owner",
        "missing-store",
        "missing-epoch",
        "shape",
        "dtype",
        "base",
        "global",
        "combination",
        "off-target",
        "missing-ion",
        "no-effect",
    ],
)
def test_lost_changed_or_wrong_epoch_membrane_state_is_refused(fault):
    value, anchor = store_observations()
    observed = value["rows"][0]["membrane"]
    if fault == "config":
        value["scheduled_options"]["Na_mem"][3] += 1
    elif fault in ("callback", "authority"):
        value["callback_identity" if fault == "callback" else "callback_authority"] = "foreign"
    elif fault == "post-owner":
        del value["post_owner_membrane"]["Dm_scheduled"]
    elif fault == "missing-store":
        del observed["epochs"]["tissue"]["Dm_scheduled"]
    elif fault == "missing-epoch":
        del observed["epochs"]["global"]
    elif fault == "shape":
        observed["epochs"]["tissue"]["Dm_cells"]["shape"] = [4]
    elif fault == "dtype":
        observed["epochs"]["tissue"]["Dm_cells"]["dtype"] = "<f4"
    elif fault == "base":
        observed["epochs"]["combined"]["Dm_base"]["fingerprint"] = "changed"
    elif fault == "global":
        observed["epochs"]["global"]["Dm_scheduled"]["fingerprint"] = "changed"
    elif fault == "combination":
        observed["source_sum_consistent"] = False
    elif fault == "off-target":
        observed["untouched"]["Na"]["after"] = "changed"
    elif fault == "missing-ion":
        del observed["scheduled_rows"]["Cl"]
    else:
        for row in value["rows"]:
            row["membrane"]["scheduled_rows"]["Na"]["fingerprint"] = "unchanged"
    with pytest.raises(ValueError):
        membrane.check_stores(value, anchor)


@pytest.mark.parametrize("flag", [None, *validation.RELEASES])
def test_all_new_actual_conditions_stay_behind_both_original_gates(tmp_path, monkeypatch, flag):
    if flag:
        monkeypatch.setenv(flag, "1")
    for scenario in membrane.SCENARIOS:
        with pytest.raises(ValueError, match="both existing Root releases"):
            validation.actual_continuity(tmp_path / scenario, scenario=scenario, cut=1)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "secondary", ["none", "failure-archive", "profile-stop", "attempt-journal"]
)
def test_membrane_prerequisite_refusal_keeps_failed_parent_cause_partial_and_accounting(
    tmp_path, monkeypatch, secondary
):
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
    from validation.betse import betse_normal_ecm_molecule_handoff as handoff
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

    primary = RuntimeError("Synthetic missing finalized callback owner; actual work forbidden")
    cause = ValueError("Original unowned-source prerequisite")
    primary.__cause__ = cause
    primary.partial = {"failed_owner": "retained", "actual_calls": 0}

    def initial(directory, case, attempts):
        attempts.append(
            dict(operation="synthetic INIT stub", status="returned", synthetic_only=True)
        )
        return "unowned synthetic INIT binding", {"failed_or_unqualified_parent": True}

    def transition(directory, binding, parent, attempts, *, scenario, event_owner_inputs):
        assert scenario == "membrane_combined"
        assert parent == {"failed_or_unqualified_parent": True}
        attempts.append(
            dict(
                operation="synthetic callback-owner prerequisite",
                status="refused",
                synthetic_only=True,
            )
        )
        raise primary

    monkeypatch.setattr(preparation, "prepare_INIT", initial)
    monkeypatch.setattr(membrane, "prepare_sim", transition)
    if secondary == "failure-archive":
        archive = preparation.archives.write_archive

        def refuse(path, *args, **kwargs):
            if path.name == "failure":
                raise OSError("Synthetic failure-archive I/O refusal")
            return archive(path, *args, **kwargs)

        monkeypatch.setattr(preparation.archives, "write_archive", refuse)
    elif secondary == "profile-stop":
        stop = Calls.stop

        def refuse(self):
            stop(self)
            raise OSError("Synthetic profile-stop refusal")

        monkeypatch.setattr(Calls, "stop", refuse)
    elif secondary == "attempt-journal":
        write = validation.write_json

        def refuse(path, value):
            if path.name == "attempts.json":
                raise OSError("Synthetic attempt-journal refusal")
            return write(path, value)

        monkeypatch.setattr(validation, "write_json", refuse)
    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")  # Only the fully blocked stubbed failure path.
    output = tmp_path / "synthetic-refusal"
    from tests.unit.test_betse_normal_ecm_molecule_event_owner import explicit_inputs

    with pytest.raises(RuntimeError) as caught:
        validation.actual_continuity(
            output, scenario="membrane_combined", cut=1, event_owner_inputs=explicit_inputs()
        )
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.partial == {"failed_owner": "retained", "actual_calls": 0}
    assert sys.getprofile() is None
    assert not (output / "result.json").exists()
    if secondary != "failure-archive":
        raw = json.loads((output / "failure/data.json").read_text())
        assert handoff._get(raw, "available", "INIT_binding") == "unowned synthetic INIT binding"
        assert handoff._get(raw, "available", "INIT_parent", "failed_or_unqualified_parent") is True
        assert handoff._get(raw, "failure", "message") == str(primary)
        assert str(cause) in handoff._get(raw, "failure", "traceback")
    if secondary != "attempt-journal":
        attempts = json.loads((output / "attempts.json").read_text())["attempts"]
        assert len(attempts) == 3 and attempts[-1]["status"] == "refused"
    if secondary != "none":
        assert any(secondary in note for note in primary.__notes__)
    (tmp_path / "membrane-failure-control.json").write_text(
        json.dumps(
            dict(
                secondary=secondary,
                primary_cause_partial_preserved=True,
                synthetic_only=True,
                actual_calls=0,
                scientific_acceptance=False,
            )
        )
    )
