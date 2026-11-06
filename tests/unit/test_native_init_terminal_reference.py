"""Native-blocked source/provenance controls, never a reference execution."""

import ast
import copy
import hashlib
import inspect
import json
import os
import struct
import subprocess
import sys
import weakref
from pathlib import Path
from types import FunctionType, SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from validation.betse import native_init_terminal_reference as reference
from validation.betse import native_init_terminal_reference_software as software

if TYPE_CHECKING:
    from validation.betse import (  # noqa: F401 - explicit frozen dynamic-runner controls
        native_sim_reference_compare_software,
        native_sim_reference_software,
    )


@pytest.fixture(autouse=True)
def native_blockade(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit native-blocked reference software release required")
    with software.blocked(tmp_path):
        yield


def _source(relative):
    return (reference.NATIVE_ROOT / relative).read_bytes()


def _observer(tmp_path, state=None, archive=None):
    state = state if state is not None else reference.State()
    archive = archive if archive is not None else SimpleNamespace(save=lambda *args: None)
    seed = reference.FreshSeed(tmp_path / "fresh.betse.gz", tmp_path)
    return reference.Observe(state, reference.NATIVE_ROOT, archive, seed, 10)


def _frame(module="betse.science.sim", name="run_sim_core", locals_=None):
    return SimpleNamespace(
        f_code=SimpleNamespace(
            co_name=name,
            co_firstlineno=1,
            co_filename=str(reference.NATIVE_ROOT / "betse/science/sim.py"),
        ),
        f_globals={"__name__": module},
        f_locals={} if locals_ is None else locals_,
        f_lineno=10,
    )


@pytest.mark.parametrize("profile", ["headless", "headless_core"])
def test_reference_core_profile_is_explicit_without_default_or_body_change(profile):
    plan = reference.source_plan(input_profile=profile)
    assert plan["input_profile"] == profile
    default = reference.source_plan()
    assert default["input_profile"] == "headless"
    assert dict(plan, input_profile="headless") == default
    assert reference.inputs.kind_for_profile(profile) != reference.inputs.KIND


@pytest.mark.parametrize("profile", ["original", "supplied", None])
def test_reference_core_profile_rejects_unavailable_or_undeclared_inputs(profile):
    with pytest.raises((reference.ReferenceRejected, ValueError)):
        reference.source_plan(input_profile=profile)


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_reference_core_profile_authenticates_reviewed_raw_pair_only(tmp_path, mode):
    pair = Path("/mnt/workspaces/Cells/native-basic-core-inputs-20261105-01/paired-inputs-01")
    expected = "f61085dba949e3984e928900f9bb93abc073c077fb3e9da36dd0563a8c2718cc"
    assert reference.snapshot.digest(pair / "inputs.json") == expected
    selected = reference._input_manifest(pair, expected, mode)
    assert selected["profile"] == "headless_core" and selected["mode"] == mode
    assert selected["inventory"]["files"]["sim_config.yaml"]["sha256"] == (
        "c801296a6382de057cde97f383250a7256c9b0be6310ee943e417e289445d193"
    )
    assert reference.snapshot.digest(pair / "inputs.json") == expected
    reference.snapshot.write_json(tmp_path / "selected-raw-inputs.json", selected)


def test_reference_source_plan_gates_and_independence():
    plan = reference.source_plan()
    assert plan["endpoint"] == "original_run_sim_core_before_init_pickle"
    assert plan["workflow"][3:6] == ["SimRunner.seed", "fresh_native_seed_pickle", "SimRunner.init"]
    assert plan["modes"] == ["original", "disabled"]
    assert plan["unchanged_calendar_network_transport_and_numerical_bodies"] is True
    assert plan["source_review_sha256"] is None and plan["bootstrap_review_sha256"] is None
    assert plan["shared_writer_review_sha256"] is None
    assert plan["execution_release_sha256"] is None
    assert plan["actual_source_native_reference_execution_released"] is False
    assert plan["external_seed_phase_parameter_owner_or_cache_inputs"] is False
    assert plan["ordinary_checkpoint_or_restart_admission"] is False
    assert plan["independent_comparison_requires_matching_initial_random_authority"] is True
    assert not {"phase", "parameters", "owner", "seed", "state"} & set(
        inspect.signature(reference.evaluate).parameters
    )


@pytest.mark.parametrize("relative", tuple(reference.CRITICAL))
def test_reference_original_source_pins(relative):
    assert hashlib.sha256(_source(relative)).hexdigest() == reference.CRITICAL[relative]


def test_reference_selected_core_is_exact_prefix():
    relative = "betse/science/sim.py"
    original = ast.parse(_source(relative))
    chosen, changes = reference.selected_tree(relative, _source(relative), "original")
    old = reference._method(original, "Simulator", "run_sim_core")
    new = reference._method(chosen, "Simulator", "run_sim_core")
    assert len(old.body) == len(new.body) + 2
    assert ast.dump(ast.Module(body=old.body[:-2], type_ignores=[])) == ast.dump(
        ast.Module(body=new.body, type_ignores=[])
    )
    assert ast.unparse(old.body[-2]) == "self._pickle_phase(phase)"
    assert ast.unparse(old.body[-1].test) == "exception_instability is not None"
    old.body = copy.deepcopy(new.body)
    assert ast.dump(original) == ast.dump(chosen)
    assert changes[0]["retained_native_instability_checked_by_observer"] is True
    compile(chosen, relative, "exec")  # Compilation only; no source body is executed.


@pytest.mark.parametrize("mode", reference.MODES)
def test_reference_calendar_loop_networks_helpers_unchanged(mode):
    relative = "betse/science/sim.py"
    original = ast.parse(_source(relative))
    chosen, _ = reference.selected_tree(relative, _source(relative), mode)
    for method in ("_plot_loop", "_run_sim_core_loop", "_run_fast_sim_core_loop", "init_dynamics"):
        assert ast.dump(reference._method(original, "Simulator", method)) == ast.dump(
            reference._method(chosen, "Simulator", method)
        )


def test_reference_flux_only_optional_assignment():
    relative = "betse/science/cells.py"
    raw = _source(relative)
    original, unchanged = reference.selected_tree(relative, raw, "original")
    omitted, changes = reference.selected_tree(relative, raw, "disabled")
    assert ast.dump(original) == ast.dump(ast.parse(raw)) and unchanged == []
    original_method = reference._method(original, "Cells", "make_world")
    omitted_method = reference._method(omitted, "Cells", "make_world")
    before = [
        n
        for n in original_method.body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "(_, self.lapENV_P_inv)"
    ][0]
    after = [
        n
        for n in omitted_method.body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "(_, self.lapENV_P_inv)"
    ][0]
    assert ast.unparse(after.value) == "(None, None)"
    assert ast.unparse(before.value) == "self.grid_obj.makeLaplacian(bound=bdic)"
    after.value = before.value
    assert ast.dump(omitted) == ast.dump(original)
    assert changes == [dict(method="Cells.make_world", omitted_flux_call_line=512)]


@pytest.mark.parametrize("mode", ["coarse", None, True, 0, "ORIGINAL"])
def test_reference_unknown_mode_refuses(mode):
    with pytest.raises(reference.ReferenceRejected, match="Exact flux"):
        reference.selected_tree("synthetic.py", b"pass", mode)


def test_reference_changed_original_source_refuses():
    with pytest.raises(reference.ReferenceRejected, match="authority changed"):
        reference.selected_tree("betse/science/sim.py", b"pass", "original")


def test_reference_full_original_inventory_metadata_only():
    result = reference.source_inventory()
    assert all(result[name]["sha256"] == pin for name, pin in reference.CRITICAL.items())
    assert "betse/science/simrunner.py" in result
    assert not any("__pycache__" in name for name in result)
    assert sum(row["size_bytes"] for row in result.values()) <= reference.MAX_SOURCE_BYTES


@pytest.mark.parametrize("defect", ["missing", "changed", "linked"])
def test_reference_inventory_refuses_missing_changed_linked(tmp_path, monkeypatch, defect):
    source = tmp_path / "betse/test.py"
    source.parent.mkdir()
    raw = b"x = 1\n"
    if defect == "changed":
        source.write_bytes(raw + b"# changed\n")
    elif defect == "linked":
        target = tmp_path / "target.py"
        target.write_bytes(raw)
        source.symlink_to(target)
    monkeypatch.setattr(reference, "CRITICAL", {"betse/test.py": hashlib.sha256(raw).hexdigest()})
    with pytest.raises(reference.ReferenceRejected):
        reference.source_inventory(tmp_path)


def test_reference_loader_freshness_and_exact_module_selection(tmp_path):
    files = {"betse/__init__.py": {}, "betse/science/test.py": {}}
    loader = reference.OriginalPackage(tmp_path, files, "original")
    assert loader.find_spec("unrelated") is None
    package = loader.find_spec("betse")
    assert package.submodule_search_locations == [str(tmp_path / "betse")]
    assert loader.find_spec("betse.science.test").origin == str(tmp_path / "betse/science/test.py")
    with pytest.raises(reference.ReferenceRejected, match="Undeclared original"):
        loader.find_spec("betse.science.injected")
    with loader:
        assert sys.meta_path[0] is loader
    assert loader not in sys.meta_path
    with pytest.raises(reference.ReferenceRejected, match="one-shot"):
        loader.__enter__()


def test_reference_loader_preloaded_package_refuses(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "betse", SimpleNamespace())
    loader = reference.OriginalPackage(tmp_path, {}, "original")
    with pytest.raises(reference.ReferenceRejected, match="Fresh process"):
        loader.__enter__()
    assert loader not in sys.meta_path


def test_reference_external_preexisting_seed_refuses(tmp_path):
    path = tmp_path / "old.betse.gz"
    path.write_bytes(b"external bytes, never unpickled")
    with pytest.raises(reference.ReferenceRejected, match="preexisting"):
        reference.FreshSeed(path, tmp_path)


def test_reference_seed_fresh_save_load_and_no_second_load(tmp_path):
    path = tmp_path / "fresh.betse.gz"
    token = reference.FreshSeed(path, tmp_path)
    path.write_bytes(b"fresh synthetic artifact; no pickle execution")
    record = token.saved_return()
    assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    token.before_load(str(path))
    token.check()
    with pytest.raises(reference.ReferenceRejected, match="fresh completed"):
        token.before_load(path)
    assert [row["admitted"] for row in token.attempts] == [True, False]


def test_reference_seed_load_before_save_refuses_and_retains_attempt(tmp_path):
    token = reference.FreshSeed(tmp_path / "fresh.betse.gz", tmp_path)
    with pytest.raises(reference.ReferenceRejected):
        token.before_load(token.path)
    assert token.attempts == [dict(kind="loadWorld", path=str(token.path), admitted=False)]
    assert not token.loaded and not token.saved


@pytest.mark.parametrize("defect", ["bytes", "inode", "path", "link"])
def test_reference_seed_epoch_drift_refuses(tmp_path, defect):
    path = tmp_path / "fresh.betse.gz"
    token = reference.FreshSeed(path, tmp_path)
    path.write_bytes(b"same bits")
    token.saved_return()
    selected = path
    if defect == "bytes":
        path.write_bytes(b"bad bits!")
    elif defect == "inode":
        other = tmp_path / "other"
        other.write_bytes(b"same bits")
        other.replace(path)
    elif defect == "path":
        selected = tmp_path / "other"
        selected.write_bytes(b"same bits")
    else:
        path.rename(tmp_path / "moved")
        path.symlink_to(tmp_path / "moved")
    with pytest.raises(reference.ReferenceRejected):
        token.before_load(selected)
    assert token.attempts[-1]["admitted"] is False and not token.loaded


def test_reference_seed_escape_refuses(tmp_path):
    with pytest.raises(reference.ReferenceRejected, match="escaped"):
        reference.FreshSeed(tmp_path.parent / "escaped", tmp_path)


def test_reference_native_instability_retains_original_identity_and_cause(tmp_path):
    observer = _observer(tmp_path)
    cause, primary = KeyError("source cause"), ValueError("native instability")
    primary.__cause__ = cause
    frame = _frame(locals_={"exception_instability": primary})
    observer._entry(frame)
    observer._return(frame, None)
    assert observer.state.primary is primary and primary.__cause__ is cause
    assert observer.state.source_returned is False
    with pytest.raises(ValueError) as caught:
        reference._stop(observer.state)
    assert caught.value is primary


def test_reference_native_success_return_is_distinct_from_sealing(tmp_path):
    observer = _observer(tmp_path)
    frame = _frame(locals_={"exception_instability": None})
    observer._entry(frame)
    observer._return(frame, None)
    assert observer.state.source_returned is True
    assert observer.state.raw[("betse.science.sim", "run_sim_core", "return")] is None
    assert observer.state.work[-1][-1] == "return"
    assert not observer.state.hooks_restored


def test_reference_primary_and_capture_error_separate(tmp_path):
    state = reference.State(primary=ValueError("primary"))
    capture = RuntimeError("capture")

    def fail():
        raise capture

    assert reference._attempt(state, "return_capture", fail) == (False, None)
    assert state.capture_error is capture
    assert state.secondary == [("return_capture", capture)]
    with pytest.raises(ValueError) as caught:
        reference._stop(state)
    assert caught.value is state.primary


def test_reference_unwind_capture_failure_preserves_source(tmp_path):
    observer = _observer(tmp_path)
    primary, capture = ValueError("original source"), RuntimeError("return observation")
    frame = _frame()
    observer._entry(frame)
    observer.pending[id(frame)] = primary
    observer._return(frame, None)
    reference._secondary(observer.state, "capture", capture)
    with pytest.raises(ValueError) as caught:
        reference._stop(observer.state)
    assert caught.value is primary
    assert observer.state.capture_error is capture
    assert observer.state.raw[("betse.science.sim", "run_sim_core")] == {}


@pytest.mark.parametrize("name", ["_pickle_phase", "sim"])
def test_reference_forbidden_continuation_refuses_before_body(tmp_path, name):
    observer = _observer(tmp_path)
    frame = _frame(
        module="betse.science.simrunner" if name == "sim" else "betse.science.sim", name=name
    )
    with pytest.raises(reference.ReferenceRejected):
        observer._entry(frame)
    assert not observer.admitted and observer.state.work == []


def test_reference_shared_trace_profile_admission_counts_once(tmp_path, monkeypatch):
    observer = _observer(tmp_path)
    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            getprofile=lambda: None,
            gettrace=lambda: None,
            setprofile=lambda value: None,
            settrace=lambda value: None,
        ),
    )
    observer.install()
    frame = _frame()
    observer.trace(frame, "call", None)
    observer.profile(frame, "call", None)
    assert len(observer.state.sites) == 1 and len(observer.state.work) == 1
    assert next(iter(observer.state.sites.values()))[:2] == [1, 0]
    observer.trace(frame, "return", None)
    observer.profile(frame, "return", None)
    assert next(iter(observer.state.sites.values()))[:2] == [1, 1]
    assert observer.admitted == {}


def test_reference_observed_inherits_and_restores_both_hooks(tmp_path):
    observer = _observer(tmp_path)
    before = sys.getprofile(), sys.gettrace()
    with reference.observed(observer):
        assert sys.getprofile() is observer.profile and sys.gettrace() is observer.trace
        assert 2 + 2 == 4
    assert (sys.getprofile(), sys.gettrace()) == before
    assert observer.state.hooks_restored


@pytest.mark.parametrize(
    "failure", ["profile_setup", "trace_setup", "profile_restore", "trace_restore"]
)
def test_reference_independent_observer_cleanup_attempts(tmp_path, monkeypatch, failure):
    observer = _observer(tmp_path)
    old = [object(), object()]
    current, actions = old.copy(), []
    primary = RuntimeError(failure)

    def setter(index):
        def set_(value):
            restoring = value is old[index]
            actions.append((index, "restore" if restoring else "setup"))
            if failure == ("profile" if index == 0 else "trace") + (
                "_restore" if restoring else "_setup"
            ):
                raise primary
            current[index] = value

        return set_

    # Patch this module's sys binding, never the actual outer pytest guard.
    real_sys = reference.sys
    fake = SimpleNamespace(
        setprofile=setter(0),
        settrace=setter(1),
        getprofile=lambda: current[0],
        gettrace=lambda: current[1],
    )
    monkeypatch.setattr(reference, "sys", fake)
    with pytest.raises((RuntimeError, reference.ReferenceRejected)):
        with reference.observed(observer):
            pass
    assert (0, "restore") in actions and (1, "restore") in actions
    if failure.endswith("setup"):
        assert observer.state.primary is primary
    else:
        assert any(error is primary for _, error in observer.state.secondary)
    assert sys is real_sys


def test_reference_final_hook_identity_sample_after_both_restores(tmp_path, monkeypatch):
    observer = _observer(tmp_path)
    old = [object(), object()]
    current, reads = old.copy(), []

    def profile(value):
        current[0] = value

    def trace(value):
        current[1] = value
        if value is old[1]:
            current[0] = object()  # Cross-effect must be noticed after both actions.

    def getter(index):
        reads.append(index)
        return current[index]

    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            setprofile=profile,
            settrace=trace,
            getprofile=lambda: getter(0),
            gettrace=lambda: getter(1),
        ),
    )
    with pytest.raises(reference.ReferenceRejected, match="Observation failed"):
        with reference.observed(observer):
            pass
    assert not observer.state.hooks_restored
    assert observer.state.secondary[-1][0] == "final_observer_identity"


def test_reference_raw_iteration_saved_before_failed_capture(tmp_path, monkeypatch):
    capture = ValueError("archive entry failed")

    def fail(label, value):
        raise capture

    observer = _observer(tmp_path, archive=SimpleNamespace(save=fail))
    monkeypatch.setattr(reference, "random", SimpleNamespace(getstate=lambda: ("python", [3, 4])))
    frame = _frame(
        locals_={
            "t": 0.1,
            "time_steps_sampled": {0.1},
            "self": SimpleNamespace(vm=[-0.07], cc_cells=[[1.0]]),
            "phase": SimpleNamespace(p=SimpleNamespace(dt=0.01)),
        }
    )
    frame.f_globals["np"] = SimpleNamespace(
        random=SimpleNamespace(get_state=lambda: ("MT", [1, 2]))
    )
    with pytest.raises(ValueError) as caught:
        observer._iteration(frame)
    assert caught.value is capture
    assert observer.state.raw["last_iteration"]["fields"]["vm"] == [-0.07]
    assert observer.state.raw["last_iteration"]["source_time"] == 0.1
    assert observer.state.iterations == []


def test_reference_typed_bits_layout_and_alias_evidence():
    import numpy as np

    values = np.array([0x8000000000000000, 0x7FF8000000000001], dtype="<u8").view("<f8")
    view = values[::-1]
    projected = reference.object_evidence(dict(original=values, view=view, again=values))
    assert projected["roots"][0][1] == projected["roots"][2][1]
    view_node = projected["nodes"][projected["roots"][1][1]["reference"]]
    assert view_node["strides_bytes"] == [-8]
    serialized = reference.typed(projected)
    assert any(
        row["raw_bytes_hex"] == view.tobytes().hex() for row in serialized["columns"].values()
    )
    assert projected["complete_object_serialization"] is False
    assert projected["owner_hydration"] is False


def test_reference_release_refusal_has_protected_result(tmp_path, monkeypatch):
    prepared = tmp_path / "prepared.json"
    prepared.write_text(
        json.dumps(dict(kind=reference.KIND, held=True, source_plan=reference.source_plan()))
    )
    from validation.betse import betse_normal_channel_join_runtime as runtime

    monkeypatch.setattr(
        runtime, "inventory", lambda: dict(loaded_files={}, synthetic_metadata=True)
    )
    output = tmp_path / "result"
    result = reference.evaluate(prepared, hashlib.sha256(prepared.read_bytes()).hexdigest(), output)
    assert result["status"] == "failed" and result["source_returned"] is False
    assert result["primary"][0]["type"].endswith("ReferenceRejected")
    assert result["native_producers"] == {} and result["work"] == []
    assert json.loads((output / "result.json").read_text()) == result
    assert reference._RAW_FAILURES[-1].primary.stage == "release"


def test_reference_missing_preparation_preserves_primary_and_metadata_failure(
    tmp_path, monkeypatch
):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    def fail_inventory():
        raise RuntimeError("independent metadata error")

    monkeypatch.setattr(runtime, "inventory", fail_inventory)
    result = reference.evaluate(tmp_path / "missing", "0" * 64, tmp_path / "out")
    assert result["status"] == "failed"
    assert result["primary"][0]["type"] == "builtins.FileNotFoundError"
    assert result["capture_errors"][0]["stage"] == "runtime_inventory"
    assert result["work"] == []


def test_reference_input_forgery_refuses_before_input_tree_read(tmp_path, monkeypatch):
    source = dict(
        directories=[],
        files={
            reference.profiles.MAIN: dict(
                sha256=reference.profiles.ORIGINAL_SHA256,
                size_bytes=reference.profiles.ORIGINAL_BYTES,
            ),
        },
    )
    modes = {mode: dict(config=str(tmp_path / mode / "config")) for mode in reference.MODES}
    value = dict(
        kind=reference.inputs.HEADLESS_KIND,
        held=True,
        source_inventory=source,
        source_tree_sha256=reference.inputs.BUNDLE_SHA256,
        modes=modes,
        source_origin=str(reference.inputs.NATIVE),
        configuration_profile=reference.profiles.HEADLESS,
        input_inventory=reference.profiles.inventory(source, reference.profiles.HEADLESS),
        configuration_changes=reference.profiles.changes(),
        raw_configuration_and_images_unchanged=False,
    )
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(value))
    calls = []
    monkeypatch.setattr(reference.inputs, "inventory", lambda path: calls.append(path))
    with pytest.raises(reference.ReferenceRejected, match="Exact headless demo pair"):
        reference._input_manifest(
            tmp_path, hashlib.sha256(path.read_bytes()).hexdigest(), "original"
        )
    assert calls == []


@pytest.mark.parametrize("event", ["profile_return", "trace_return", "trace_exception"])
def test_reference_inherited_rejection_on_unwind_preserves_primary(tmp_path, monkeypatch, event):
    observer = _observer(tmp_path)
    primary, capture = ValueError("native source"), RuntimeError("inherited observation")
    cause = KeyError("native cause")
    primary.__cause__ = cause

    def inherited_profile(frame, kind, arg):
        if event == "profile_return" and kind == "return":
            raise capture

    def inherited_trace(frame, kind, arg):
        if event == "trace_" + kind:
            raise capture
        return inherited_trace

    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            getprofile=lambda: inherited_profile,
            gettrace=lambda: inherited_trace,
            setprofile=lambda value: None,
            settrace=lambda value: None,
        ),
    )
    observer.install()
    frame = _frame()
    observer.trace(frame, "call", None)
    observer.profile(frame, "call", None)
    observer.trace(frame, "exception", (type(primary), primary, None))
    observer.trace(frame, "return", None)
    observer.profile(frame, "return", None)
    with pytest.raises(ValueError) as caught:
        reference._stop(observer.state)
    assert caught.value is primary and caught.value.__cause__ is cause
    assert observer.state.capture_error is capture
    assert observer.state.raw[("betse.science.sim", "run_sim_core")] == {}
    before = observer.sequence
    with pytest.raises(ValueError) as caught:
        observer._entry(_frame(name="later_method"))
    assert caught.value is primary and observer.sequence == before


@pytest.mark.parametrize("which", ["profile", "trace"])
def test_reference_inherited_entry_rejection_stays_poisoned(tmp_path, monkeypatch, which):
    observer = _observer(tmp_path)
    rejected = RuntimeError("inherited entry guard")

    def prior(frame, event, arg):
        if event == "call":
            raise rejected

    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            getprofile=lambda: prior if which == "profile" else None,
            gettrace=lambda: prior if which == "trace" else None,
            setprofile=lambda value: None,
            settrace=lambda value: None,
        ),
    )
    observer.install()
    with pytest.raises(RuntimeError) as caught:
        getattr(observer, which)(_frame(), "call", None)
    assert caught.value is rejected and observer.state.primary is rejected
    with pytest.raises(RuntimeError) as caught:
        observer._entry(_frame(name="later"))
    assert caught.value is rejected and observer.sequence == 1


def test_reference_failed_forensic_capture_cannot_replace_source(tmp_path):
    primary, capture = ValueError("source primary"), RuntimeError("forensic write")
    parent = [1, 2, 3]
    state = reference.State(primary=primary, raw={"original_partial": parent})

    def failed_save(*args):
        raise capture

    archive = SimpleNamespace(save=failed_save)
    okay, _ = reference._attempt(
        state, "retained_native_partials", reference._retain_native, state, archive
    )
    assert not okay
    assert state.primary is primary and state.capture_error is capture
    assert state.raw["original_partial"] is parent
    with pytest.raises(ValueError) as caught:
        reference._stop(state)
    assert caught.value is primary


@pytest.mark.parametrize("failure", ["record", "write"])
def test_reference_result_sealing_failure_retains_early_primary(tmp_path, monkeypatch, failure):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    capture = RuntimeError("final record or write refusal")
    monkeypatch.setattr(runtime, "inventory", lambda: dict(loaded_files={}))

    def fail(*args):
        raise capture

    if failure == "record":
        monkeypatch.setattr(reference, "_error", fail)
    else:
        original = reference.snapshot.write_json

        def writer(path, value):
            if path.name == "result.json":
                raise capture
            return original(path, value)

        monkeypatch.setattr(reference.snapshot, "write_json", writer)
    with pytest.raises(reference.ReferenceRejected) as caught:
        reference.evaluate(tmp_path / "no_preparation", "0" * 64, tmp_path / "out")
    retained = caught.value.partial
    assert isinstance(retained.primary, FileNotFoundError)
    assert caught.value.__cause__ is retained.primary
    assert retained.capture_error is capture
    assert retained.secondary[-1] == ("result_write", capture)
    assert reference._RAW_FAILURES[-1] is retained


def _release_fixture(tmp_path, monkeypatch):
    callback = SimpleNamespace(
        source_plan=lambda: {"filesystem_conflicts": {"native_HOME_unchanged": True}}
    )
    demo = SimpleNamespace()
    monkeypatch.setattr(reference, "_writer_providers", lambda: (demo, callback))
    plan = dict(native_inventory_sha256="1" * 64, execution_source={"snapshot_sha256": "2" * 64})
    documents = dict(
        source=reference._source_contract(plan),
        bootstrap=reference._bootstrap_contract(callback),
        writer={"kind": "existing_writer_review_checked_by_original_session"},
        execution=reference._execution_contract(),
    )
    names = dict(
        source="SOURCE_REVIEW_SHA256",
        bootstrap="BOOTSTRAP_REVIEW_SHA256",
        writer="WRITER_REVIEW_SHA256",
        execution="EXECUTION_RELEASE_SHA256",
    )
    reviews = {}
    for name, value in documents.items():
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        pin = hashlib.sha256(path.read_bytes()).hexdigest()
        monkeypatch.setattr(reference, names[name], pin)
        reviews[name] = dict(path=str(path), sha256=pin)
    value = dict(
        kind="cells.original_INIT_reference_execution_release@1",
        prepared_sha256="3" * 64,
        snapshot_sha256="2" * 64,
        worker_output=str(tmp_path / "worker"),
        policy=dict(reference.NATIVE_POLICY),
        reviews=reviews,
        rng_policy=dict(exact_parity=False, expected_before_seed=None),
        pythonpath=os.environ.get("PYTHONPATH"),
        read_access=dict(roots=[], files=[]),
        enabled=True,
    )
    monkeypatch.setenv(reference.RELEASE, "1")
    return plan, value, demo, callback


def _save_release(tmp_path, value):
    path = tmp_path / "release.json"
    path.write_text(json.dumps(value))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_completion_release_private_metadata_seam(tmp_path, monkeypatch):
    plan, value, demo, callback = _release_fixture(tmp_path, monkeypatch)
    path, pin = _save_release(tmp_path, value)
    result = reference._release(plan, "3" * 64, path, pin, tmp_path / "worker", True)
    assert result == (value, demo, callback)
    assert reference._ATTEMPT is None  # Metadata verification never issues native objects.


@pytest.mark.parametrize("field", ["prepared", "snapshot", "output", "policy", "review", "enabled"])
def test_reference_completion_release_wrong_binding_refuses(tmp_path, monkeypatch, field):
    plan, value, _, _ = _release_fixture(tmp_path, monkeypatch)
    if field in ("prepared", "snapshot"):
        value[field + "_sha256"] = "9" * 64
    elif field == "output":
        value["worker_output"] = str(tmp_path / "other")
    elif field == "policy":
        value["policy"]["max_rss_bytes"] += 1
    elif field == "review":
        value["reviews"]["source"]["sha256"] = "9" * 64
    else:
        value["enabled"] = False
    path, pin = _save_release(tmp_path, value)
    with pytest.raises(reference.ReferenceRejected):
        reference._release(plan, "3" * 64, path, pin, tmp_path / "worker", True)
    assert reference._ATTEMPT is None


@pytest.mark.parametrize("raw", [b'{"a": 1, "a": 2}', b'{"a": NaN}', b'{"a": Infinity}'])
def test_reference_completion_release_json_refuses_ambiguous_values(tmp_path, raw):
    path = tmp_path / "ambiguous.json"
    path.write_bytes(raw)
    with pytest.raises(reference.ReferenceRejected):
        reference._json_record(path, hashlib.sha256(raw).hexdigest())


def _raw_inputs(tmp_path):
    root = tmp_path / "immutable_config"
    root.mkdir()
    (root / "INITS").mkdir()
    (root / "SIMS").mkdir()
    for name, value in (
        ("sim_config.yaml", b"original relative paths; no YAML evaluation\n"),
        ("image.bin", b"\x00\xff\x80"),
    ):
        path = root / name
        path.write_bytes(value)
        path.chmod(0o444)
    return dict(root=str(root), inventory=reference.inputs.inventory(root))


def test_reference_completion_execution_copy_is_exact_and_independent(tmp_path):
    selected, state = _raw_inputs(tmp_path), reference.State()
    result = reference.execution_copy(selected, tmp_path / "execution", state)
    old, new = Path(selected["root"]), Path(result["root"])
    assert reference.inputs.inventory(new) == selected["inventory"]
    for row in result["files"]:
        assert row["status"] == "copied" and row["source_inode"] != row["execution_inode"]
        assert (new / row["name"]).read_bytes() == (old / row["name"]).read_bytes()
    (new / "INITS/world_1.betse.gz").write_bytes(b"synthetic fresh output; never loaded")
    assert not (old / "INITS/world_1.betse.gz").exists()
    assert reference.inputs.inventory(old) == selected["inventory"]
    assert state.raw["execution_copy"]["rows"] is result["files"]


@pytest.mark.parametrize("defect", ["existing", "same", "changed", "linked"])
def test_reference_completion_copy_refuses_unsafe_inputs(tmp_path, defect):
    selected = _raw_inputs(tmp_path)
    destination = tmp_path / "execution"
    if defect == "existing":
        destination.mkdir()
    elif defect == "same":
        destination = Path(selected["root"])
    elif defect == "changed":
        path = Path(selected["root"]) / "image.bin"
        path.chmod(0o600)
        path.write_bytes(b"changed")
    else:
        destination.symlink_to(Path(selected["root"]), target_is_directory=True)
    with pytest.raises((reference.ReferenceRejected, ValueError)):
        reference.execution_copy(selected, destination, reference.State())


@pytest.mark.parametrize("defect", [None, "cpu", "thread", "memory", "reserve", "cuda"])
def test_reference_completion_resource_contract(tmp_path, monkeypatch, defect):
    env = {
        key: "1"
        for key in (
            "OPENBLAS_NUM_THREADS",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        )
    }
    env["CUDA_VISIBLE_DEVICES"] = ""
    if defect == "thread":
        env["OMP_NUM_THREADS"] = "2"
    elif defect == "cuda":
        env["CUDA_VISIBLE_DEVICES"] = "0"
    monkeypatch.setattr(
        reference,
        "os",
        SimpleNamespace(sched_getaffinity=lambda pid: {3 if defect == "cpu" else 5}, environ=env),
    )
    monkeypatch.setattr(
        reference,
        "resource",
        SimpleNamespace(
            RLIMIT_AS=0,
            getrlimit=lambda key: (2**30 + 1, 2**30 + 1) if defect == "memory" else (2**30, 2**30),
        ),
    )
    monkeypatch.setattr(
        reference, "guard_memory_available", lambda: 1 if defect == "reserve" else 16 * 2**30
    )
    if defect is None:
        reference._resources()
    else:
        with pytest.raises(reference.ReferenceRejected):
            reference._resources()


@pytest.mark.parametrize("matches", [True, False])
def test_reference_completion_rng_is_comparison_only(tmp_path, matches):
    actual = dict(numpy_random=("synthetic_MT", [1, 2, 3]), python_random=(1, [3, 2, 1]))
    expected = copy.deepcopy(actual)
    if not matches:
        expected["numpy_random"][1][0] += 1
    path = tmp_path / "expectation.json"
    path.write_text(
        json.dumps(
            dict(kind="cells.original_INIT_rng_expectation@1", state=reference.typed(expected))
        )
    )
    policy = dict(
        exact_parity=True,
        expected_before_seed=dict(
            path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        ),
    )
    before = copy.deepcopy(actual)
    if matches:
        reference._rng_check(policy, actual)
    else:
        with pytest.raises(reference.ReferenceRejected, match="no reset"):
            reference._rng_check(policy, actual)
    assert actual == before


class _FalseyError(ValueError):
    def __bool__(self):
        return False


@pytest.mark.parametrize(
    "hook,event", [("profile", "return"), ("trace", "return"), ("trace", "exception")]
)
def test_reference_completion_installed_hook_recovery_precedes_metadata(tmp_path, hook, event):
    primary, capture = _FalseyError("source failure"), RuntimeError("inherited observer")
    cause = KeyError("source cause")
    primary.__cause__ = cause

    def body():
        raise primary

    outer_profile, outer_trace = sys.getprofile(), sys.gettrace()
    local, fired, covered = {}, [], []

    def profile(frame, kind, arg):
        if outer_profile is not None:
            outer_profile(frame, kind, arg)
        if hook == "profile" and frame.f_code is body.__code__ and kind == event:
            fired.append(kind)
            sys.setprofile(None)
            sys.settrace(None)
            raise capture

    def trace(frame, kind, arg):
        prior = outer_trace if kind == "call" else local.get(id(frame))
        if prior is not None:
            returned = prior(frame, kind, arg)
            if returned is not None:
                local[id(frame)] = returned
        if kind == "return":
            local.pop(id(frame), None)
        if hook == "trace" and frame.f_code is body.__code__ and kind == event:
            fired.append(kind)
            sys.setprofile(None)
            sys.settrace(None)
            raise capture
        return trace

    observer = _observer(tmp_path)
    observer._native = lambda frame: frame.f_code is body.__code__
    original_return = observer._return

    def checked_return(frame, value):
        if frame.f_code is body.__code__:
            covered.append(
                sys.getprofile() is observer.profile and sys.gettrace() is observer.trace
            )
        return original_return(frame, value)

    observer._return = checked_return
    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        with pytest.raises(_FalseyError) as caught:
            with reference.observed(observer):
                body()
        assert caught.value is primary and primary.__cause__ is cause
        assert observer.state.primary is primary and observer.state.hooks_restored
        assert any(error is capture for _, error in observer.state.secondary)
        assert fired and covered and all(covered)
    finally:
        sys.setprofile(outer_profile)
        sys.settrace(outer_trace)


@pytest.mark.parametrize("hook", ["profile", "trace"])
def test_reference_completion_non_native_wrapper_unwind_preserves_falsey_source(
    tmp_path, monkeypatch, hook
):
    observer = _observer(tmp_path)
    primary, capture = _FalseyError("native"), RuntimeError("wrapper observer")
    primary.__cause__ = KeyError("cause")
    observer.state.native_unwind = primary

    def prior(frame, event, arg):
        if event == "return":
            raise capture
        return prior

    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            getprofile=lambda: prior if hook == "profile" else None,
            gettrace=lambda: prior if hook == "trace" else None,
            setprofile=lambda value: None,
            settrace=lambda value: None,
        ),
    )
    observer.install()
    frame = _frame()
    frame.f_code.co_filename = "/tmp/non-native-wrapper.py"
    observer.local_traces[id(frame)] = prior
    getattr(observer, hook)(frame, "return", None)
    with pytest.raises(_FalseyError) as caught:
        reference._stop(observer.state)
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    assert observer.state.capture_error is capture


def test_reference_completion_cleanup_never_calls_unsafe_secondary_helper(tmp_path, monkeypatch):
    observer = _observer(tmp_path)
    primary, capture, reporter = (
        _FalseyError("source"),
        RuntimeError("restore"),
        RuntimeError("reporter entry"),
    )
    old, current, attempts, reports = [object(), object()], [None, None], [], []

    def unsafe(*args):
        reports.append(args)
        raise reporter

    with pytest.raises(RuntimeError) as caught:
        unsafe(None)  # Non-vacuous failure witness for the helper we must not enter.
    assert caught.value is reporter
    reports.clear()
    monkeypatch.setattr(reference, "_secondary", unsafe)

    def setter(index):
        def set_(value):
            attempts.append((index, value))
            if index == 0 and value is old[0]:
                raise capture
            current[index] = value

        return set_

    current[:] = old
    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            getprofile=lambda: current[0],
            gettrace=lambda: current[1],
            setprofile=setter(0),
            settrace=setter(1),
        ),
    )
    with pytest.raises(_FalseyError) as caught:
        with reference.observed(observer):
            raise primary
    assert caught.value is primary and reports == []
    assert (0, old[0]) in attempts and (1, old[1]) in attempts
    assert observer.state.coverage_failed and not observer.state.hooks_restored
    assert any(error is capture for _, error in observer.state.secondary)


def test_reference_completion_uncovered_forensics_do_not_invoke_callbacks(tmp_path, monkeypatch):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    primary = _FalseyError("original native primary")
    state = reference.State(primary=primary, observer_used=True, hooks_restored=False)
    callbacks = []
    monkeypatch.setattr(runtime, "inventory", lambda: callbacks.append("runtime"))
    monkeypatch.setattr(reference, "_retain_native", lambda *args: callbacks.append("forensics"))
    session = SimpleNamespace(__exit__=lambda *args: callbacks.append("writer"))
    with pytest.raises(_FalseyError) as caught:
        reference._forensic_finish(state, object(), session, True, None, tmp_path)
    assert caught.value is primary and callbacks == []
    assert not (tmp_path / "runtime.json").exists()


@pytest.mark.parametrize("failed", [0, 1])
def test_reference_completion_active_recovery_failure_is_sticky(tmp_path, monkeypatch, failed):
    observer = _observer(tmp_path)
    primary, capture, restoration = (
        _FalseyError("native primary"),
        RuntimeError("callback"),
        RuntimeError("setter"),
    )
    primary.__cause__ = KeyError("native cause")
    current, attempts = [None, None], []

    def setter(index):
        def set_(value):
            attempts.append(index)
            if index == failed:
                raise restoration
            current[index] = value

        return set_

    monkeypatch.setattr(
        reference,
        "sys",
        SimpleNamespace(
            getprofile=lambda: current[0],
            gettrace=lambda: current[1],
            setprofile=setter(0),
            settrace=setter(1),
        ),
    )
    observer.install()
    observer.managed = True
    observer.state.observer_used = True
    observer.state.native_unwind = primary
    with pytest.raises(_FalseyError) as caught:
        observer._capture("inherited_return", capture)
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    assert attempts == [0, 1] and observer.invalid and observer.state.coverage_failed
    assert any(error is capture for _, error in observer.state.secondary)
    assert any(error is restoration for _, error in observer.state.secondary)
    before = observer.sequence
    with pytest.raises(_FalseyError) as caught:
        observer._entry(_frame(name="forbidden_later"))
    assert caught.value is primary and observer.sequence == before


def test_reference_completion_partial_copy_retains_failed_file(tmp_path, monkeypatch):
    selected, state = _raw_inputs(tmp_path), reference.State()
    original = reference.inputs._copy_file
    calls, primary = [], RuntimeError("second copy failed")

    def copier(source, target, expected):
        calls.append(target)
        if len(calls) == 2:
            raise primary
        return original(source, target, expected)

    monkeypatch.setattr(reference.inputs, "_copy_file", copier)
    with pytest.raises(RuntimeError) as caught:
        reference.execution_copy(selected, tmp_path / "execution", state)
    assert caught.value is primary
    rows = state.raw["execution_copy"]["rows"]
    assert [row["status"] for row in rows] == ["copied", "attempted"]
    assert calls[0].exists() and not calls[1].exists()
    assert reference.inputs.inventory(Path(selected["root"])) == selected["inventory"]


def test_reference_completion_declared_runtime_paths_cannot_drift(tmp_path, monkeypatch):
    plan, value, _, _ = _release_fixture(tmp_path, monkeypatch)
    value["pythonpath"] = "/tmp/undeclared-overlay"
    path, pin = _save_release(tmp_path, value)
    with pytest.raises(reference.ReferenceRejected, match="runtime import paths"):
        reference._release(plan, "3" * 64, path, pin, tmp_path / "worker", True)


def test_reference_completion_supervisor_refuses_without_launch(tmp_path, monkeypatch):
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    calls = []
    monkeypatch.setattr(guard, "run_bounded", lambda *args, **kwargs: calls.append(args))
    path = tmp_path / "prepared.json"
    path.write_text(json.dumps(dict(kind=reference.KIND)))
    with pytest.raises(reference.ReferenceRejected) as caught:
        reference.supervise(
            path,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            None,
            None,
            tmp_path / "never-created",
            enabled=True,
        )
    assert caught.value.stage == "release" and calls == []
    assert not (tmp_path / "never-created").exists()


def test_reference_completion_writer_reuse_is_original_readonly_contract():
    path = software.ROOT / "validation/betse/native_seed_demo.py"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == reference.WRITER_PRODUCERS["validation.betse.native_seed_demo"]
    )
    tree = ast.parse(raw)
    session = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_writer_session"
    )
    assert any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "ProcessLogLease"
        for node in ast.walk(session)
    )
    exit_ = reference._method(tree, "ProcessLogLease", "__exit__")
    assert ast.unparse(exit_.body[-1]) == "return False"
    assert not any(
        isinstance(node, ast.Call) and ast.unparse(node.func) in ("os.close", "fcntl.flock")
        for node in ast.walk(exit_)
    )
    source = ast.parse(Path(reference.__file__).read_bytes())
    evaluator = next(
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate"
    )
    assert any(
        isinstance(node, ast.Call) and ast.unparse(node.func) == "demo._writer_session"
        for node in ast.walk(evaluator)
    )


def test_reference_pair_writer_declarations_do_not_adopt_observed_hashes():
    binding = reference.writer_declarations()
    assert binding["observed_hash_is_not_automatic_adoption"] is True
    assert binding["audit"]["component_sha256"] == reference.AUDIT_COMPONENT_SHA256
    for name, row in binding["sources"].items():
        assert row["declared_sha256"] == reference.WRITER_PRODUCERS[name]
        assert row["observed_sha256"] == software.snapshot.digest(Path(row["path"]))
        assert row["declared_source_matches"] is (row["declared_sha256"] == row["observed_sha256"])
    assert binding["all_declared_sources_match"] is all(
        row["declared_source_matches"] for row in binding["sources"].values()
    )


def test_reference_pair_writer_mismatch_refuses_before_either_import(monkeypatch):
    calls = []
    monkeypatch.setattr(
        reference, "WRITER_PRODUCERS", dict.fromkeys(reference.WRITER_PRODUCERS, "0" * 64)
    )
    monkeypatch.setattr(
        reference.importlib, "import_module", lambda *args, **kwargs: calls.append(args)
    )
    with pytest.raises(reference.ReferenceRejected, match="producer adoption unavailable"):
        reference._writer_providers()
    assert calls == []


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("falsey", [False, True])
def test_reference_residual_pending_unwind_never_allows_rejected_entry(tmp_path, hook, falsey):
    primary = (_FalseyError if falsey else ValueError)("original source")
    primary.__cause__ = KeyError("original cause")
    refusal, calls = RuntimeError("entry refused"), []

    def target():
        calls.append("BODY MUST NOT RUN")

    outer_profile, outer_trace = sys.getprofile(), sys.gettrace()
    local = {}

    def profile(frame, event, arg):
        if outer_profile is not None:
            outer_profile(frame, event, arg)
        if hook == "profile" and event == "call" and frame.f_code is target.__code__:
            raise refusal

    def trace(frame, event, arg):
        prior = outer_trace if event == "call" else local.get(id(frame))
        if prior is not None:
            returned = prior(frame, event, arg)
            if returned is not None:
                local[id(frame)] = returned
        if event == "return":
            local.pop(id(frame), None)
        if hook == "trace" and event == "call" and frame.f_code is target.__code__:
            raise refusal
        return trace

    observer = _observer(tmp_path)
    observer.state.native_unwind = primary
    observer._native = lambda frame: False
    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        with pytest.raises(type(primary)) as caught:
            with reference.observed(observer):
                target()
        assert caught.value is primary and caught.value.__cause__ is primary.__cause__
        assert calls == []
        assert any(error is refusal for _, error in observer.state.secondary)
    finally:
        sys.setprofile(outer_profile)
        sys.settrace(outer_trace)


@pytest.mark.parametrize("restored", [True, False])
def test_reference_residual_evaluate_protects_outer_package_cleanup(
    tmp_path, monkeypatch, restored
):
    # Real evaluate control flow with inert package/workflow/lease seams only;
    # no original package, phase, constructor, RNG or source body is invoked.
    selected = dict(_raw_inputs(tmp_path), manifest_sha256="2" * 64, mode="original")
    primary, exit_error, reporter_error = (
        _FalseyError("source primary"),
        RuntimeError("exit entry"),
        RuntimeError("reporter entry"),
    )
    primary.__cause__ = KeyError("source cause")
    required, current, actions, callbacks, loader_list = [object(), object()], [], [], [], []
    current[:] = required
    exiting = [False]

    def setter(index):
        def set_(value):
            actions.append((index, value))
            if exiting[0] and not restored and value is required[index]:
                raise RuntimeError("cannot restore inherited hook")
            current[index] = value

        return set_

    fake_sys = SimpleNamespace(
        setprofile=setter(0),
        settrace=setter(1),
        getprofile=lambda: current[0],
        gettrace=lambda: current[1],
        meta_path=loader_list,
    )
    monkeypatch.setattr(reference, "sys", fake_sys)
    monkeypatch.setattr(reference, "_ATTEMPT", None)

    class Lease:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            callbacks.append("lease_exit")

    lease = Lease()
    demo = SimpleNamespace(ProcessLogLease=Lease, _writer_session=lambda *args: lease)
    authority = dict(
        reviews={"writer": {"path": "unused"}},
        rng_policy=dict(exact_parity=False, expected_before_seed=None),
    )
    monkeypatch.setattr(reference, "_release", lambda *args: (authority, demo, object()))
    monkeypatch.setattr(reference, "_resources", lambda: None)
    monkeypatch.setattr(reference, "_input_manifest", lambda *args: selected)
    inventory = {"metadata_only": {"sha256": "1" * 64}}
    monkeypatch.setattr(reference, "source_inventory", lambda *args: inventory)
    monkeypatch.setattr(reference, "_loop_line", lambda *args: 1)
    audit = SimpleNamespace(installed=True, check=lambda: None)
    monkeypatch.setattr(reference, "_filesystem", lambda *args: audit)

    class Package:
        loaded = {}

        def __enter__(self):
            loader_list.append(self)
            return self

        def __exit__(self, *args):
            exiting[0] = True
            current[:] = [None, None]
            raise exit_error  # Deliberately leaves the loader registered.

        def verify(self):
            raise AssertionError("failed source cannot verify as a success")

    package = Package()
    monkeypatch.setattr(reference, "OriginalPackage", lambda *args: package)

    def flow(*args):
        raise primary

    def unsafe_reporter(*args):
        callbacks.append("unsafe_secondary")
        raise reporter_error

    def forensic(*args):
        assert current[0] is required[0] and current[1] is required[1]
        callbacks.append("covered_forensics")

    monkeypatch.setattr(reference, "_workflow", flow)
    monkeypatch.setattr(reference, "_secondary", unsafe_reporter)
    monkeypatch.setattr(reference, "_forensic_finish", forensic)
    path, output = tmp_path / "plan.json", tmp_path / "result"
    producers = {reference.FILE: reference.snapshot.digest(reference.ROOT / reference.FILE)}
    manifest_pin = reference.snapshot.digest(reference.ROOT / "SNAPSHOT.json")
    value = dict(
        kind=reference.KIND,
        held=True,
        source_plan=reference.source_plan(),
        execution_source=dict(
            root=str(reference.ROOT), snapshot_sha256=manifest_pin, owned_files=producers
        ),
        input_pair="unused",
        inputs=dict(selected),
        native_root=str(tmp_path / "inert-native"),
        native_inventory=inventory,
        native_inventory_sha256=reference._seal(inventory),
    )
    path.write_text(json.dumps(value))
    monkeypatch.setenv("MPLCONFIGDIR", str(output / "mplconfig"))
    if restored:
        result = reference.evaluate(
            path, hashlib.sha256(path.read_bytes()).hexdigest(), output, enabled=True
        )
        state = reference._RAW_FAILURES[-1]
        assert result["status"] == "failed" and callbacks == ["covered_forensics"]
    else:
        with pytest.raises(_FalseyError) as caught:
            reference.evaluate(
                path, hashlib.sha256(path.read_bytes()).hexdigest(), output, enabled=True
            )
        assert caught.value is primary and callbacks == []
        state = primary.reference_partial
        assert not (output / "result.json").exists()
    assert state.primary is primary and state.primary.__cause__ is primary.__cause__
    assert any(error is exit_error for _, error in state.secondary)
    assert package not in loader_list
    assert (0, required[0]) in actions and (1, required[1]) in actions


@pytest.mark.parametrize("mode", ["allowed", "forbidden_write", "forbidden_read"])
def test_reference_residual_real_process_audit_is_sticky_before_effect(tmp_path, mode):
    child = tmp_path / "audit-process"
    child.mkdir()
    script = r"""
import json, os, pathlib, sys
from validation.betse import native_init_terminal_reference as ref
from validation.betse import native_init_terminal_reference_software as controls
root, mode = pathlib.Path(sys.argv[1]), sys.argv[2]
home = root / "native-home"
home.mkdir()
outside = root.parent / "outside-input"
outside.write_bytes(b"external private test bytes")
native_sentinel = []
with controls.blocked(root):
    provider = ref._audit_provider()
    access = dict(roots=[str(root), str(ref.ROOT), sys.prefix, sys.base_prefix], files=[])
    policy = ref.BootstrapAudit(provider, root,
        dict(native_dot_directory=str(home), existing_native_dot_link=None), access)
    policy.install()
    policy.check()
    assert policy.installed and policy.writer.installed
    native_sentinel.append("installed_before_inert_entry")
    allowed = root / "allowed-output"
    allowed.write_bytes(b"allowed")
    if mode == "forbidden_write":
        target = root.parent / "forbidden-output"
        try:
            target.write_bytes(b"MUST NOT BE WRITTEN")
        except BaseException:
            pass
        assert not target.exists()
    elif mode == "forbidden_read":
        try:
            outside.read_bytes()
        except BaseException:
            pass
        else:
            raise AssertionError("forbidden read reached effect")
    failed = False
    try:
        policy.check()
    except BaseException:
        failed = True
    assert failed is (mode != "allowed")
    (root / "audit-result.json").write_text(json.dumps(dict(
        status="failed" if failed else "metadata_completed",
        installed=policy.installed, sentinel=native_sentinel, record=policy.record())))
os.rename(root / "native-blocked.json", root / "separate-audit-child-guard.json")
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(child), mode],
        cwd=software.ROOT,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    (tmp_path / "audit-stdout.log").write_text(result.stdout)
    (tmp_path / "audit-stderr.log").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    value = json.loads((child / "audit-result.json").read_text())
    assert value["installed"] and value["sentinel"] == ["installed_before_inert_entry"]
    assert value["status"] == ("metadata_completed" if mode == "allowed" else "failed")
    guard = json.loads((child / "separate-audit-child-guard.json").read_text())
    assert guard["attempted"] == [] and guard["prior_profile_trace_restored"]


@pytest.mark.parametrize(
    "filename,module,expected",
    [
        (str(reference.NATIVE_ROOT / "betse/science/sim.py"), "synthetic", True),
        ("/tmp/test.py", "betse.science.sim", True),
        ("/tmp/test.py", "numpy.random.synthetic", True),
        ("/tmp/test.py", "cells.processes.synthetic", True),
        ("/tmp/test.py", "unrelated", False),
    ],
)
def test_reference_guard_exact_native_entry_predicate(filename, module, expected):
    frame = SimpleNamespace(
        f_globals={"__name__": module},
        f_code=SimpleNamespace(co_name="metadata", co_filename=filename),
    )
    assert software.forbidden(frame) is expected


def test_reference_capacity_plan_uses_existing_limits_and_pointer_history():
    plan = reference.source_plan()["observation_retention"]
    assert plan["live_iteration_rows"] == 1
    assert plan["static_grid_inverse_in_iteration_fields"] is False
    assert plan["iteration_history"] == "file pins only; captures written synchronously"
    assert plan["preallocation_limits"] == reference.CAPTURE_LIMITS
    assert reference.CAPTURE_LIMITS["column_bytes"] == reference.evidence.payload.MAX_BLOB
    assert reference.CAPTURE_LIMITS["total_column_bytes"] == reference.evidence.payload.MAX_UNIQUE
    assert reference.NATIVE_POLICY["max_rss_bytes"] == 2**30
    assert 625 * 625 * 8 == 3_125_000
    assert 625 * 625 * 8 * 500 == 1_562_500_000  # Counterfactual retained-copy cost.
    assert not {"lapENVinv", "lapENV_P_inv"} & set(reference.ITERATION_FIELDS)


@pytest.mark.parametrize("defect", ["column", "aggregate", "metadata", "atomic", "depth", "cycle"])
def test_reference_capacity_refuses_before_any_wire_clone(tmp_path, monkeypatch, defect):
    import numpy as np

    from validation.betse import betse_initial_mesh_preparation_wire as wire

    if defect == "column":
        value = np.empty(reference.CAPTURE_LIMITS["column_bytes"] + 1, dtype="u1")
    elif defect == "aggregate":
        array = np.empty(2**20, dtype="u1")
        value = [array] * (reference.CAPTURE_LIMITS["total_column_bytes"] // array.nbytes + 1)
    elif defect == "metadata":
        value = ["x" * 65536] * 180
    elif defect == "atomic":
        value = "x" * (reference.CAPTURE_LIMITS["atomic_metadata_upper_bytes"] // 6 + 1)
    elif defect == "depth":
        value = 0
        for _ in range(reference.CAPTURE_LIMITS["depth"] + 1):
            value = (value,)
    else:
        value = []
        value.append(value)
    calls = []

    def forbidden_clone(value):
        calls.append(value)
        raise AssertionError("wire must not run before preallocation refusal")

    monkeypatch.setattr(wire, "capture", forbidden_clone)
    with pytest.raises(reference.ReferenceRejected, match="Observation preflight") as caught:
        reference.typed(value)
    assert calls == []
    assert caught.value.stage == "capture"
    assert caught.value.capture_budget["limits"] == reference.CAPTURE_LIMITS


def test_reference_capacity_counts_each_alias_and_preserves_original_layout():
    import numpy as np

    array = np.array([0x8000000000000000, 0x7FF8000000000001], dtype="<u8").view("<f8")
    view = array[::-1]
    before = array.tobytes()
    budget = reference.capture_budget((array, array, view))
    assert budget["counts"]["columns"] == 3
    assert budget["counts"]["column_bytes"] == 3 * array.nbytes
    assert array.tobytes() == before and view.strides == (-8,)
    wire = reference.typed((array, array, view))
    assert wire["tree"]["values"][2]["layout"]["strides_bytes"] == [-8]
    assert wire["columns"]["native_000002"]["raw_bytes_hex"] == view.tobytes().hex()


def test_reference_capacity_archive_refusal_retains_value_and_primary(tmp_path):
    import numpy as np

    primary, cause = ValueError("original native primary"), KeyError("original cause")
    primary.__cause__ = cause
    state = reference.State(primary=primary)
    archive = reference.Archive(tmp_path / "captures", state)
    value = np.empty(reference.CAPTURE_LIMITS["column_bytes"] + 1, dtype="u1")
    ok, result = reference._attempt(state, "bounded_archive", archive.save, "oversized", value)
    assert ok is False and result is None
    assert state.raw["failed_archive"]["value"] is value
    assert state.captures[0]["status"] == "capture_failed"
    assert state.captures[0]["preallocation_refusal"]["counts"]["column_bytes"] == value.nbytes
    assert isinstance(state.capture_error, reference.ReferenceRejected)
    with pytest.raises(ValueError) as caught:
        reference._stop(state)
    assert caught.value is primary and primary.__cause__ is cause
    assert list((tmp_path / "captures").iterdir()) == []


def test_reference_capacity_full512_writes_files_not_retained_arrays(tmp_path, monkeypatch):
    import numpy as np

    state = reference.State()
    archive = reference.Archive(tmp_path / "captures", state)
    observer = _observer(tmp_path, state=state, archive=archive)
    inverse = np.empty((625, 625))
    sim = SimpleNamespace(lapENVinv=inverse)
    frame = _frame(
        locals_={
            "self": sim,
            "phase": SimpleNamespace(p=SimpleNamespace(dt=0.125)),
            "time_steps_sampled": set(),
        }
    )
    frame.f_globals["np"] = SimpleNamespace(random=SimpleNamespace(get_state=lambda: ("raw-MT",)))
    monkeypatch.setattr(reference, "random", SimpleNamespace(getstate=lambda: ("raw-python",)))
    buffers = []
    for ordinal in range(512):
        current = np.array([float(ordinal), -0.0])
        buffers.append(weakref.ref(current))
        for name in reference.ITERATION_FIELDS:
            setattr(sim, name, current)
        frame.f_locals["t"] = ordinal * 0.125
        observer._iteration(frame)
    assert len(state.iterations) == len(state.captures) == 512
    assert len(state.raw) == 1 and state.raw["last_iteration"]["ordinal"] == 512
    assert sum(ref() is not None for ref in buffers) == 1
    assert sim.lapENVinv is inverse
    assert all(set(row) == {"path", "sha256"} for row in state.iterations)
    assert all(set(row) == {"label", "status", "files"} for row in state.captures)
    for ordinal in (0, 511):
        pin = state.iterations[ordinal]
        saved = reference.evidence.read(pin["path"], expected_sha256=pin["sha256"])
        assert len(saved["columns"]) == len(reference.ITERATION_FIELDS)
        assert all(row["shape"] == [2] for row in saved["columns"].values())
    assert reference.capture_budget(state.raw["last_iteration"])["counts"]["column_bytes"] == 128


def test_reference_capacity_return_locals_overwrite_one_slot(tmp_path):
    class Holder:
        pass

    observer = _observer(tmp_path)
    references = []
    for _ in range(512):
        holder = Holder()
        holder.value = object()
        references.append(weakref.ref(holder))
        frame = _frame(
            module="betse.science.cells", name="cellMatrices", locals_={"temporary": holder}
        )
        observer._entry(frame)
        observer._return(frame, None)
    assert len(observer.state.raw) == 2
    assert observer.admitted == {} and observer.pending == {}
    assert sum(ref() is not None for ref in references) == 1
    assert observer.state.raw[("betse.science.cells", "cellMatrices")]["temporary"] is holder
    assert observer.state.source_returned is False


@pytest.mark.parametrize("defect", ["scalar", "depth"])
def test_reference_capacity_graph_refuses_before_oversized_projection(defect):
    if defect == "scalar":
        value = "x" * (reference.CAPTURE_LIMITS["metadata_upper_bytes"] // 6 + 1)
    else:
        value = 0
        for _ in range(reference.CAPTURE_LIMITS["depth"] + 1):
            value = [value]
    with pytest.raises(reference.ReferenceRejected, match="Observation graph preflight") as caught:
        reference.object_evidence(dict(retained=value))
    assert caught.value.stage == "capture"
    assert caught.value.capture_budget["limits"] == reference.CAPTURE_LIMITS


def test_reference_capacity_graph_preserves_actual_array_and_alias_edges():
    import numpy as np

    array = np.empty((625, 625))
    view = array[::-1]
    result = reference.object_evidence(dict(original=array, again=array, view=view))
    original = result["roots"][0][1]["reference"]
    assert result["roots"][1][1]["reference"] == original
    assert result["nodes"][original]["value"] is array
    view_node = result["nodes"][result["roots"][2][1]["reference"]]
    assert view_node["base"]["reference"] == original
    assert view_node["strides_bytes"] == [-5000, 8]
    assert view_node["value"] is view
    assert result["complete_object_serialization"] is False


@pytest.mark.parametrize("case", ["inline_hex", "wire_depth", "unicode"])
def test_reference_preallocation_encoded_budget_refuses_before_clone(tmp_path, monkeypatch, case):
    import numpy as np

    from validation.betse import betse_initial_mesh_preparation_wire as wire

    if case == "inline_hex":
        value = [np.empty(1024, dtype="u1")] * 8
        monkeypatch.setitem(reference.CAPTURE_LIMITS, "metadata_upper_bytes", 32_000)
    elif case == "wire_depth":
        value = np.empty(1, dtype="u1")
        for _ in range(5):
            value = (value,)
        monkeypatch.setitem(reference.CAPTURE_LIMITS, "depth", 10)
    else:
        value = "\U0001f9ec" * 600
        assert 6 * len(value) + 256 < 6000 < len(json.dumps(value))
        monkeypatch.setitem(reference.CAPTURE_LIMITS, "atomic_metadata_upper_bytes", 6000)
    calls = []
    monkeypatch.setattr(wire, "capture", lambda value: calls.append(value))
    with pytest.raises(reference.ReferenceRejected, match="Observation preflight") as caught:
        reference.typed(value)
    assert calls == []
    counts = caught.value.capture_budget["counts"]
    if case == "inline_hex":
        assert counts["metadata_upper_bytes"] > 32_000
        assert counts["metadata_upper_bytes"] - counts["inline_hex_bytes"] < 32_000
    elif case == "wire_depth":
        assert counts["wire_depth"] > 10


def test_reference_preallocation_graph_unicode_uses_surrogate_bound(monkeypatch):
    monkeypatch.setitem(reference.CAPTURE_LIMITS, "metadata_upper_bytes", 5000)
    value = "\U0001f9ec" * 450
    assert 6 * len(value) + 256 < 5000 < len(json.dumps(value))
    with pytest.raises(reference.ReferenceRejected, match="Observation graph preflight"):
        reference.object_evidence(dict(value=value))


def test_reference_preallocation_normalization_matches_existing_consumer():
    from validation.betse import native_init_terminal_reference_compare as consumer

    raw = Path(reference.__file__).read_bytes()
    expected = reference.comparator_ast_sha256(raw)
    assert (
        expected
        != hashlib.sha256(ast.dump(ast.parse(raw), include_attributes=False).encode()).hexdigest()
    )
    checker = FunctionType(
        consumer._reference_source.__code__, dict(vars(consumer), REFERENCE_AST_SHA256=expected)
    )
    constants, pins = checker(raw)
    assert constants["KIND"] == reference.KIND and set(pins) == reference.REVIEW_PIN_NAMES
    tree = ast.parse(raw)
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            if {t.id for t in node.targets} <= reference.REVIEW_PIN_NAMES:
                node.value = ast.Constant("a" * 64)
    adopted = ast.unparse(tree).encode()
    assert reference.comparator_ast_sha256(adopted) == expected
    assert set(checker(adopted)[1].values()) == {"a" * 64}
    assert reference.source_plan()["comparator_normalized_AST_sha256"] == expected


def _initial_rng_fixture():
    import numpy as np

    p = SimpleNamespace()
    state = reference.State(
        stage="original_runner", raw=dict(parameters=p, runner=SimpleNamespace(_p=p))
    )
    plan = dict(
        execution_source=dict(
            owned_files={
                reference.FILE: reference.snapshot.digest(reference.ROOT / reference.FILE)
            },
            snapshot_sha256=reference.snapshot.digest(reference.ROOT / "SNAPSHOT.json"),
        ),
        inputs=dict(
            mode="original", inventory=dict(files={"sim_config.yaml": dict(sha256="a" * 64)})
        ),
        source_plan=dict(input_profile="headless"),
        native_inventory_sha256="b" * 64,
        rng_policy=dict(exact_parity=False, expected_before_seed=None),
    )
    observed = dict(
        numpy_random=("MT19937", np.array(range(624), dtype="<u4"), 624, 1, -0.0),
        python_random=(3, tuple(range(624)) + (624,), None),
        initial_random_reset_or_replacement=False,
    )
    runtime = dict(
        python="synthetic-version",
        numpy_version="synthetic-version",
        executable=dict(path="/synthetic/python", sha256="c" * 64),
        files={
            name: dict(path="/synthetic/" + name, sha256="d" * 64)
            for name in reference.RNG_RUNTIME_MODULES
        },
    )
    return plan, state, observed, runtime


def _initial_rng_seams(monkeypatch, observed, runtime):
    calls = []

    def read(state):
        calls.append("read_states")
        state.raw["before_seed_random_states"] = observed
        return observed

    monkeypatch.setattr(reference, "_read_initial_rng_states", read)
    monkeypatch.setattr(
        reference, "_initial_rng_runtime", lambda: calls.append("runtime") or runtime
    )
    return calls


@pytest.mark.parametrize("drift", [False, True])
def test_reference_core_profile_initial_witness_keeps_exact_selected_profile(drift):
    plan, state, observed, runtime = _initial_rng_fixture()
    plan["source_plan"]["input_profile"] = "headless_core"
    plan["inputs"]["profile"] = "headless" if drift else "headless_core"
    if drift:
        with pytest.raises(reference.ReferenceRejected, match="input/profile"):
            reference._initial_rng_witness(plan, state, observed, runtime)
    else:
        witness = reference._initial_rng_witness(plan, state, observed, runtime)
        assert witness["common_binding"]["profile"] == "headless_core"
        assert witness["state"] is observed


def _builtin_runtime_fixture(runtime):
    value = copy.deepcopy(runtime)
    value["kind"] = "cells.rng_runtime_provenance@2"
    value["files"].pop("_random")
    value["python"] = ".".join(map(str, sys.version_info[:3]))
    value["interpreter"] = dict(
        implementation="cpython",
        cache_tag=sys.implementation.cache_tag,
        hexversion=sys.hexversion,
        builtin_module_names=["_random"],
    )
    value["builtins"] = {
        "_random": dict(
            kind="cpython_builtin_module",
            name="_random",
            origin="built-in",
            loader="_frozen_importlib.BuiltinImporter",
            has_location=False,
            cached=None,
            submodule_search_locations=None,
            export="_random.Random",
            methods=["seed", "getstate", "setstate", "random", "getrandbits"],
            executable_sha256=value["executable"]["sha256"],
        )
    }
    return value


@pytest.mark.parametrize("drift", [None, "file_and_builtin", "executable", "interpreter"])
def test_reference_builtin_runtime_witness_uses_explicit_versioned_provenance(monkeypatch, drift):
    # Exact shared metadata candidate in this frozen control only; actual
    # producer adoption remains closed in the delivered source.
    candidate = "6ddb846ef3a20e9ff95fb2e546a39329e8d305b821bfedadf344fce9fe548315"
    monkeypatch.setattr(reference, "RNG_RUNTIME_HELPER_SHA256", candidate)
    assert reference.snapshot.digest(reference.ROOT / reference.RNG_RUNTIME_HELPER) == candidate
    plan, state, observed, runtime = _initial_rng_fixture()
    runtime = _builtin_runtime_fixture(runtime)
    if drift == "file_and_builtin":
        runtime["files"]["_random"] = dict(path="/fake.so", sha256="d" * 64)
    elif drift == "executable":
        runtime["builtins"]["_random"]["executable_sha256"] = "0" * 64
    elif drift == "interpreter":
        runtime["interpreter"]["cache_tag"] = "cpython-999"
    if drift is not None:
        with pytest.raises(ValueError):
            reference._initial_rng_witness(plan, state, observed, runtime)
    else:
        witness = reference._initial_rng_witness(plan, state, observed, runtime)
        assert witness["kind"] == reference.RNG_BUILTIN_WITNESS_KIND
        assert (
            witness["state"] is observed
            and "_random" not in witness["common_binding"]["runtime"]["files"]
        )
        assert witness["source"]["files"] == {
            reference.RNG_RUNTIME_HELPER: reference.RNG_RUNTIME_HELPER_SHA256
        }


def test_reference_builtin_missing_helper_refuses_without_invented_file_origin(monkeypatch):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    monkeypatch.setattr(reference, "RNG_RUNTIME_HELPER_SHA256", None)
    monkeypatch.setattr(
        runtime, "inventory", lambda: dict(loaded_files={}, modules_without_files=["_random"])
    )
    with pytest.raises(reference.ReferenceRejected, match="provenance helper unavailable"):
        reference._initial_rng_runtime()


@pytest.mark.parametrize("gaussian", ["none", "negative_zero", "nan_payload"])
def test_reference_initial_rng_full_state_witness_is_saved_without_reset(
    tmp_path, monkeypatch, gaussian
):
    plan, state, observed, runtime = _initial_rng_fixture()
    cache = (
        None
        if gaussian == "none"
        else (
            -0.0
            if gaussian == "negative_zero"
            else struct.unpack("<d", bytes.fromhex("010000000000f87f"))[0]
        )
    )
    observed["python_random"] = (*observed["python_random"][:2], cache)
    before = reference.typed(observed)
    calls = _initial_rng_seams(monkeypatch, observed, runtime)
    archive = reference.Archive(tmp_path / "captures", state)
    witness = reference._capture_initial_rng(plan, state, archive)
    assert calls == ["read_states", "runtime"]
    assert reference.typed(observed) == before
    assert witness["state"] is observed and witness["kind"] == reference.RNG_WITNESS_KIND
    assert witness["epoch"] == reference.RNG_EPOCH
    assert witness["common_binding"]["runtime"] == runtime
    assert (
        witness["source"]["reference_sha256"]
        == plan["execution_source"]["owned_files"][reference.FILE]
    )
    assert witness["order"]["same_parameter"] is True and witness["order"]["seed_entered"] is False
    assert witness["observed_states_equalized"] is False
    assert witness["common_starting_authority_established"] is False
    pin = state.initial_rng_observation
    assert pin is not None and reference.evidence.read(
        pin["path"], expected_sha256=pin["sha256"]
    ) == reference.typed(witness)
    assert [row["label"] for row in state.captures] == [
        "before_seed_random_states",
        "pre_seed_rng_witness",
    ]


@pytest.mark.parametrize(
    "defect",
    [
        "numpy_words",
        "numpy_position",
        "numpy_zero",
        "python_words",
        "python_index",
        "stage",
        "parameter",
        "seed_entered",
        "runtime",
        "source",
    ],
)
def test_reference_initial_rng_incomplete_or_wrong_lineage_refuses(tmp_path, defect):
    plan, state, observed, runtime = _initial_rng_fixture()
    mt, py = observed["numpy_random"], observed["python_random"]
    if defect == "numpy_words":
        observed["numpy_random"] = (mt[0], mt[1][:-1], *mt[2:])
    elif defect == "numpy_position":
        observed["numpy_random"] = (mt[0], mt[1], 625, *mt[3:])
    elif defect == "numpy_zero":
        mt[1][:] = 0
    elif defect == "python_words":
        observed["python_random"] = (py[0], py[1][:-1], py[2])
    elif defect == "python_index":
        observed["python_random"] = (py[0], (*py[1][:-1], 625), py[2])
    elif defect == "stage":
        state.stage = "SEED"
    elif defect == "parameter":
        state.raw["runner"]._p = object()
    elif defect == "seed_entered":
        state.work.append((1, "SEED", "betse.science.simrunner", "seed", "enter"))
    elif defect == "runtime":
        runtime["files"].pop("_random")
    else:
        plan["execution_source"]["owned_files"][reference.FILE] = "0" * 64
    with pytest.raises(reference.ReferenceRejected):
        reference._initial_rng_witness(plan, state, observed, runtime)
    assert state.initial_rng_observation is None and state.captures == []


@pytest.mark.parametrize(
    "defect", ["none", "epoch", "input", "runtime", "numpy_state", "python_state", "legacy"]
)
def test_reference_initial_rng_expectation_binds_epoch_provenance_and_all_state(tmp_path, defect):
    plan, state, observed, runtime = _initial_rng_fixture()
    witness = reference._initial_rng_witness(plan, state, observed, runtime)
    expected = dict(
        kind="cells.original_INIT_rng_expectation@2",
        epoch=reference.RNG_EPOCH,
        common_binding=copy.deepcopy(witness["common_binding"]),
        state=reference.typed(observed),
    )
    if defect == "epoch":
        expected["epoch"] = "later_INIT_identity_roster"
    elif defect == "input":
        expected["common_binding"]["input_inventory_sha256"] = "0" * 64
    elif defect == "runtime":
        expected["common_binding"]["runtime"]["numpy_version"] = "different"
    elif defect in ("numpy_state", "python_state"):
        changed = copy.deepcopy(observed)
        if defect == "numpy_state":
            changed["numpy_random"][1][623] ^= 1
        else:
            changed["python_random"] = (3, (*changed["python_random"][1][:-2], 999, 624), None)
        expected["state"] = reference.typed(changed)
    elif defect == "legacy":
        expected = dict(kind="cells.original_INIT_rng_expectation@1", state=expected["state"])
    path = tmp_path / "expectation.json"
    path.write_text(json.dumps(expected))
    policy = dict(
        exact_parity=True,
        expected_before_seed=dict(path=str(path), sha256=reference.snapshot.digest(path)),
    )
    before = reference.typed(observed)
    if defect == "none":
        reference._rng_check(policy, observed, witness=witness)
    else:
        with pytest.raises(reference.ReferenceRejected):
            reference._rng_check(policy, observed, witness=witness)
    assert reference.typed(observed) == before
    assert witness["common_starting_authority_established"] is False


def test_reference_initial_rng_capture_failure_preserves_source_and_raw(tmp_path, monkeypatch):
    plan, state, observed, runtime = _initial_rng_fixture()
    calls = _initial_rng_seams(monkeypatch, observed, runtime)
    primary, cause, capture = (
        ValueError("native cause"),
        KeyError("original cause"),
        OSError("capture failed"),
    )
    primary.__cause__ = cause

    def save(label, value):
        calls.append(label)
        state.primary = primary
        raise capture

    with pytest.raises(ValueError) as caught:
        reference._capture_initial_rng(plan, state, SimpleNamespace(save=save))
    assert caught.value is primary and primary.__cause__ is cause
    assert state.capture_error is capture and state.initial_rng_observation is None
    assert state.raw["pre_seed_rng_witness"]["state"] is observed
    assert calls == ["read_states", "runtime", "before_seed_random_states"]


def test_reference_initial_rng_partial_getter_keeps_first_state(tmp_path, monkeypatch):
    plan, state, observed, runtime = _initial_rng_fixture()
    capture = OSError("second getter failed")
    calls = []

    def fail():
        calls.append("python")
        raise capture

    reader = FunctionType(
        reference._read_initial_rng_states.__code__,
        dict(
            vars(reference),
            sys=SimpleNamespace(
                modules={
                    "numpy": SimpleNamespace(
                        random=SimpleNamespace(
                            get_state=lambda: calls.append("numpy") or observed["numpy_random"]
                        )
                    )
                }
            ),
            random=SimpleNamespace(getstate=fail),
        ),
    )
    monkeypatch.setattr(reference, "_read_initial_rng_states", reader)
    with pytest.raises(reference.ReferenceRejected) as caught:
        reference._capture_initial_rng(
            plan, state, SimpleNamespace(save=lambda *args: calls.append("save"))
        )
    assert caught.value.__cause__ is capture
    assert state.raw["before_seed_random_states"] == dict(numpy_random=observed["numpy_random"])
    assert calls == ["numpy", "python"] and state.initial_rng_observation is None


def test_reference_initial_rng_getters_and_workflow_have_no_reset_or_draw():
    tree = ast.parse(Path(reference.__file__).read_bytes())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    reader = functions["_read_initial_rng_states"]
    methods = [
        node.func.attr
        for node in ast.walk(reader)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert methods == ["get_state", "getstate"]
    for name in (
        "_read_initial_rng_states",
        "_initial_rng_runtime",
        "_initial_rng_witness",
        "_capture_initial_rng",
        "_rng_check",
    ):
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"seed", "set_state", "setstate", "random", "rand", "randn"}
            for node in ast.walk(functions[name])
        )
    workflow = functions["_workflow"].body
    capture = next(
        i
        for i, node in enumerate(workflow)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_capture_initial_rng"
    )
    assert isinstance(workflow[capture + 1], ast.Assign)
    assert (
        isinstance(workflow[capture + 2], ast.Assign)
        and workflow[capture + 2].value.func.attr == "seed"
    )
    assert (
        reference.source_plan()["common_initial_rng_observation"][
            "automatic_parity_or_starting_authority"
        ]
        is False
    )


@pytest.mark.parametrize("missing", [False, True])
def test_reference_initial_rng_runtime_selects_actual_required_origins(monkeypatch, missing):
    from validation.betse import betse_normal_channel_join_runtime as provider

    _, _, _, runtime = _initial_rng_fixture()
    data = dict(
        python="synthetic-version",
        executable=runtime["executable"],
        loaded_files=dict(runtime["files"], irrelevant=dict(path="/irrelevant", sha256="e" * 64)),
    )
    if missing:
        data["loaded_files"]["numpy.random.mtrand"] = dict(path="/missing", unavailable=True)
    monkeypatch.setattr(provider, "inventory", lambda: data)
    if missing:
        with pytest.raises(reference.ReferenceRejected, match="runtime file identities"):
            reference._initial_rng_runtime()
    else:
        actual = reference._initial_rng_runtime()
        assert actual["files"] == runtime["files"]
        assert "irrelevant" not in actual["files"]


@pytest.fixture(autouse=True)
def common_start_rng_blockade(request, tmp_path, native_blockade):
    if "common_start" not in request.node.name:
        yield
        return
    py = reference.random._inst
    module = sys.modules.get("numpy.random.mtrand")
    ng = None if module is None else vars(module).get("_rand")
    prior, attempts = sys.getprofile(), []

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        receiver = (
            getattr(arg, "__self__", None) if event == "c_call" else frame.f_locals.get("self")
        )
        if (
            event == "call"
            and frame.f_globals.get("__name__") == "random"
            and frame.f_code.co_name in ("seed", "getstate", "setstate", "__init__")
        ) or (event == "c_call" and (receiver is py or ng is not None and receiver is ng)):
            attempts.append((event, frame.f_code.co_qualname))
            raise AssertionError("Actual common-start RNG entry held")

    try:
        sys.setprofile(profile)
        yield
        assert attempts == []
    finally:
        sys.setprofile(prior)
        reference.snapshot.write_json(
            tmp_path / "common-start-RNG-blocked.json", dict(attempted=attempts)
        )


def _common_start_metadata(mode="original"):
    selected = dict(
        mode=mode,
        inventory=dict(
            directories=[],
            files={
                "model.yaml": dict(sha256=("d" if mode == "original" else "e") * 64, size_bytes=1)
            },
        ),
    )
    manifest = dict(
        files={
            name: dict(sha256=pin)
            for name, pin in (
                (reference.FILE, "a" * 64),
                (reference.COMMON_START_FILE, "c" * 64),
                ("validation/betse/native_seed_demo.py", "b" * 64),
            )
        }
    )
    options = dict(python_seed=2437, numpy_seed=5211)
    return options, selected, manifest


@pytest.mark.parametrize(
    "field,value",
    [
        ("python_seed", True),
        ("python_seed", -1),
        ("python_seed", 2**256),
        ("numpy_seed", True),
        ("numpy_seed", -1),
        ("numpy_seed", 2**32),
        ("numpy_seed", 2.0),
        ("state", [1, 2, 3]),
    ],
)
def test_reference_common_start_rejects_implicit_or_state_inputs(field, value):
    options, _, _ = _common_start_metadata()
    options[field] = value
    with pytest.raises(reference.ReferenceRejected):
        reference._common_start_options(options)


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_reference_common_start_declaration_binds_inputs_callers_and_held_provider(mode):
    options, selected, manifest = _common_start_metadata(mode)
    declared = reference.common_start_declaration(options, selected, manifest)
    assert declared["mode"] == mode
    assert declared["program"]["input_identity"] == reference._seal(selected["inventory"])
    assert declared["program"]["consumer_sources"] == dict(cells="b" * 64, original="a" * 64)
    assert declared["provider"]["sha256"] is reference.COMMON_START_SHA256
    assert declared["provider"]["review_sha256"] is reference.COMMON_START_REVIEW_SHA256
    assert declared["program_identity"] == reference._seal(declared["program"])
    ambient = reference.source_plan()
    selected_plan = reference.source_plan(common_start=declared)
    assert "common_start" not in ambient and ambient["HOME_rewrite_or_RNG_initialization"] is False
    assert selected_plan["common_start"] is declared and selected_plan["HOME_rewrite"] is False
    assert selected_plan["actual_source_native_reference_execution_released"] is False
    assert selected_plan["common_start"]["program"]["setstate_or_generator_replacement"] is False
    other = _common_start_metadata("disabled" if mode == "original" else "original")
    assert (
        reference.common_start_declaration(*other)["program_identity"]
        != declared["program_identity"]
    )


@pytest.mark.parametrize("mutation", ["draw_type", "seed_type", "extra", "identity"])
def test_reference_common_start_canonical_declaration_refuses_type_equal_or_resealed_drift(
    mutation,
):
    declared = reference.common_start_declaration(*_common_start_metadata())
    if mutation == "draw_type":
        declared["program"]["draws"] = False
    elif mutation == "seed_type":
        declared["program"]["numpy_seed"] = True
    elif mutation == "extra":
        declared["program"]["state"] = []
    else:
        declared["program_identity"] = "f" * 64
    with pytest.raises(reference.ReferenceRejected):
        reference._common_start_shape(declared)


def test_reference_common_start_unreviewed_producer_refuses_before_import(monkeypatch):
    calls = []
    monkeypatch.setattr(reference, "COMMON_START_SHA256", None)
    monkeypatch.setattr(reference, "COMMON_START_REVIEW_SHA256", None)
    monkeypatch.setattr(reference.importlib, "import_module", lambda name: calls.append(name))
    with pytest.raises(reference.ReferenceRejected, match="remains held"):
        reference._common_start_api()
    assert calls == []


def _common_workflow_metadata(tmp_path, *, selected=True, failure=None, writer_failure=None):
    events, state = [], reference.State()
    options, inputs, manifest = _common_start_metadata()
    declaration = reference.common_start_declaration(options, inputs, manifest)
    p = SimpleNamespace(seed_pickle_filename=str(tmp_path / "world.betse.gz"))
    runner = SimpleNamespace(_p=p)
    seed = SimpleNamespace(path=tmp_path / "world.betse.gz")
    stop = RuntimeError("synthetic stop before actual RNG witness/SEED")
    program = object()

    def initialize(actual_program, actual_state, *, role, output, enabled):
        caller = sys._getframe(1)
        assert caller.f_code is workflow.__code__ and caller.f_locals["state"] is state
        assert caller.f_locals["p"] is p and caller.f_locals["runner"] is runner
        assert actual_program is program and actual_state is state and role == "original"
        assert enabled is True and output == tmp_path / "common-start-rng"
        assert state.stage == "original_runner" and not any(k.endswith("_phase") for k in state.raw)
        events.append("common_start_rng")
        if failure is not None:
            raise failure
        return dict(
            kind=reference.COMMON_START_KIND,
            status="completed",
            role="original",
            program=declaration["program"],
            program_identity=declaration["program_identity"],
        )

    def save(label, value):
        events.append(label + ".save")
        assert state.raw["common_start_rng"] is value
        if writer_failure is not None:
            raise writer_failure
        return None

    def capture(*args):
        events.append("initial_rng")
        raise stop

    def make(_filename):
        events.append("parameters")
        return p

    modules = {
        "betse.appmeta": SimpleNamespace(
            BetseAppMeta=lambda: SimpleNamespace(init_libs=lambda **k: None)
        ),
        "betse.science.parameters": SimpleNamespace(Parameters=SimpleNamespace(make=make)),
        "betse.science.simrunner": SimpleNamespace(SimRunner=lambda actual: runner),
    }
    namespace = dict(
        vars(reference),
        __name__="metadata_common_start_consumer",
        importlib=SimpleNamespace(import_module=lambda name: modules[name]),
        inputs=SimpleNamespace(_program=lambda *args: dict(ordered_path_permission=[])),
        _common_start_request=lambda plan: (SimpleNamespace(initialize=initialize), program),
        _capture_initial_rng=capture,
    )
    workflow = FunctionType(reference._workflow.__code__, namespace)
    plan = dict(
        inputs=dict(inputs, root=str(tmp_path)), source_plan=dict(input_profile="headless_core")
    )
    if selected:
        plan["common_start"] = declaration
    return SimpleNamespace(
        run=lambda: workflow(
            plan, state, SimpleNamespace(folder=tmp_path / "captures", save=save), seed
        ),
        state=state,
        events=events,
        stop=stop,
        p=p,
        runner=runner,
        program=program,
    )


@pytest.mark.parametrize("selected", [False, True])
def test_reference_common_start_actual_direct_call_seam_preserves_ambient_order(tmp_path, selected):
    model = _common_workflow_metadata(tmp_path, selected=selected)
    with pytest.raises(RuntimeError) as caught:
        model.run()
    assert caught.value is model.stop
    assert model.events == (
        ["parameters", "common_start_rng", "common_start_rng.save", "initial_rng"]
        if selected
        else ["parameters", "initial_rng"]
    )
    assert model.state.raw["parameters"] is model.p and model.state.raw["runner"] is model.runner
    assert ("common_start_rng" in model.state.raw) is selected
    assert "seed_phase" not in model.state.raw


@pytest.mark.parametrize("where", ["initialize", "capture"])
def test_reference_common_start_failed_attempt_keeps_primary_partial_and_stops_world(
    tmp_path, where
):
    class FalseError(ValueError):
        def __bool__(self):
            return False

    primary, cause = FalseError("actual synthetic common-start failure"), OSError("original cause")
    primary.__cause__ = cause
    partial = dict(operations=[dict(status="failed")], states=dict(partial=True))
    primary.common_start_attempt = partial
    model = _common_workflow_metadata(
        tmp_path,
        failure=primary if where == "initialize" else None,
        writer_failure=primary if where == "capture" else None,
    )
    with pytest.raises(BaseException) as caught:
        model.run()
    if where == "initialize":
        assert caught.value is primary and model.state.raw["common_start_rng_error"] is primary
        assert model.state.raw["common_start_rng_attempt"] is partial
    else:
        assert caught.value.__cause__ is primary and "common_start_rng" in model.state.raw
        assert model.state.capture_error is primary
    assert primary.__cause__ is cause and "initial_rng" not in model.events
    assert "seed_phase" not in model.state.raw
    assert model.state.raw["common_start_rng_program"] is model.program
    reference.snapshot.write_json(
        tmp_path / "common-start-failure.json",
        dict(
            stage=where,
            primary_identity=id(primary),
            cause_identity=id(cause),
            program_retained=True,
            actual_RNG_or_native_entries=0,
            world_entries=0,
        ),
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "native_init_terminal_reference_software",
        "native_sim_reference_software",
        "native_sim_reference_compare_software",
    ],
)
@pytest.mark.parametrize("cpu", [None, 5, 6])
def test_reference_common_start_runner_CPU_is_explicit_and_preserves_other_caps(
    tmp_path, monkeypatch, module_name, cpu
):
    module = __import__("validation.betse." + module_name, fromlist=[module_name])
    original, calls = dict(module.POLICY), []
    monkeypatch.setattr(module, "POLICY", dict(original))
    monkeypatch.setattr(module, "prepare", lambda *args: calls.append(dict(module.POLICY)))
    monkeypatch.setattr(module.resource, "setrlimit", lambda *args: None)
    arguments = [module_name, "--prepare", str(tmp_path / "not-launched")]
    if cpu is not None:
        arguments += ["--software-cpu", str(cpu)]
    monkeypatch.setattr(sys, "argv", arguments)
    assert module.main() == 0 and calls == [dict(original, cpu=5 if cpu is None else cpu)]
    assert {k: v for k, v in calls[0].items() if k != "cpu"} == {
        k: v for k, v in original.items() if k != "cpu"
    }
