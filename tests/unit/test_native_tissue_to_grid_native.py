"""Original AST metadata and synthetic dispatch; real source remains blocked."""

import ast
import copy
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from validation.betse import native_tissue_to_grid_native as n

ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")


def selected(groups, file, name):
    return next(
        node for f, ns in groups if f == file for node in ns if getattr(node, "name", None) == name
    )


def test_source_ast_full_world_mapping_and_helpers_are_independent_original_nodes():
    groups, sites = n.source_nodes(ROOT)
    file = "betse/science/cells.py"
    actual = next(
        node
        for node in ast.parse((ROOT / file).read_text()).body
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    own = selected(groups, file, "Cells")
    for name in ("make_world", *n.MAPPING_METHODS):
        a = next(v for v in own.body if v.name == name)
        b = next(v for v in actual.body if isinstance(v, ast.FunctionDef) and v.name == name)
        assert ast.dump(a) == ast.dump(b)
    body = next(v for v in own.body if v.name == "make_world").body
    assert [v.lineno for v in body[-6:]] == list(n.TAIL_LINES)
    assert ["value", "flux"] == [
        v.value.values[0].value
        for v in body
        if isinstance(v, ast.Assign) and isinstance(v.value, ast.Dict) and v.targets[0].id == "bdic"
    ]
    for file, name in n.HELPERS:
        original = next(
            v
            for v in ast.parse((ROOT / file).read_text()).body
            if isinstance(v, ast.FunctionDef) and v.name == name
        )
        assert ast.dump(selected(groups, file, name)) == ast.dump(original)
    assert file + ":" + name in sites


def test_source_ast_keeps_multi_branch_and_fresh_twenty_stores():
    groups, _ = n.source_nodes(ROOT)
    cells = selected(groups, "betse/science/cells.py", "Cells")
    voronoi = next(v for v in cells.body if v.name == "make_voronoi")
    assert "clip_and_refine" in ast.unparse(voronoi)
    stores = selected(groups, "betse/science/parameters.py", "store_parameters")
    assert [v.lineno for v in stores.body] == list(n.prefix.STORE_LINES)
    assert len(stores.body) == 20


def test_source_ast_original_pin_drift_refuses_before_compilation(monkeypatch):
    original = n.prefix.shared.digest
    monkeypatch.setattr(
        n.prefix.shared,
        "digest",
        lambda p: "0" * 64 if str(p).endswith("cells.py") else original(p),
    )
    with pytest.raises(ValueError, match="source"):
        n.source_nodes(ROOT)


def test_source_ast_private_compilation_never_changes_shared_runtime():
    before = copy.deepcopy(n.prefix.legacy_runtime.DIRECT)
    groups, _ = n.source_nodes(ROOT)
    scope = n.runtime_functions()
    codes, _, metadata = scope["compile_groups"](groups, native_root=ROOT)
    assert "betse.science.math.finitediff" in codes
    assert metadata["constructors_methods_rng_decode_or_operators_executed"] is False
    assert n.prefix.legacy_runtime.DIRECT == before
    assert scope["DIRECT"]["betse.science.cells"]["nparray"] == "betse.lib.numpy.nparray"


@pytest.mark.parametrize("count", [0, 1, 4])
def test_probe_policy_retains_targets_and_both_original_input_ranks(count):
    x, y = object(), object()
    rows = n.probe_inputs(NS(cell_i=list(range(count)), X=x, Y=y))
    assert [r["name"] for r in rows] == n.PROBE_POLICY["names"]
    assert rows[0]["data"] == [float(i + 1) for i in range(count)]
    assert rows[1]["data"] == [rows[0]["data"], [-v for v in rows[0]["data"]]]
    assert rows[0]["target_points"] is rows[1]["target_points"] is None
    for row in rows[2:]:
        assert row["target_points"][0] is x and row["target_points"][1] is y
    assert all(row["interp_method"] == "linear" for row in rows)


def harness(monkeypatch, *, failure=None, capture_failure=None):
    import numpy as np

    calls = []
    primary, cause = ValueError("original mapping primary"), RuntimeError("original cause")

    class Caller:
        cell_i = [0, 1]
        X, Y = (1, 2), (3, 4)

        def map_cells_centre_to_grids_centre(self, data, **kw):
            calls.append("grids")
            if failure == "mapping":
                raise primary from cause
            return data

        def map_cells_centre_to_points(self, data, targets, **kw):
            calls.append("points")
            return data

    caller = Caller()
    obs = n.Observation(
        copy.deepcopy, lambda e: dict(type=type(e).__name__, message=str(e)), lambda: dict(epoch=0)
    )
    obs.caller = caller
    obs.grid = caller.grid_obj = object()
    obs.mask = object()
    obs.mesh = caller.mesh = NS(image_mask=obs.mask)
    obs.parameter = object()
    caller.all_points_cell_i = caller.cell_i
    obs.pre_tail_cell_i = caller.cell_i
    obs.pre_tail_cell_i_values = tuple(caller.cell_i)
    obs.tail_array_type = np.ndarray
    caller.cell_i = np.asarray(caller.cell_i)
    obs.tail_asarray_returns = [(obs.pre_tail_cell_i, caller.cell_i)]
    obs.tail_array_state = obs.array_state(caller.cell_i)
    monkeypatch.setattr(n, "caller_values", lambda obs: dict(unchanged="source bytes"))
    monkeypatch.setattr(n.prefix, "source_observation", lambda *a, **k: nullcontext())
    base = dict(
        status="source_failed" if failure == "prefix" else "source_completed",
        source_body_completed=failure != "prefix",
        failed_stage="prefix" if failure == "prefix" else None,
        source_error=dict(type="prefix") if failure == "prefix" else None,
        warnings=[],
    )
    monkeypatch.setattr(n.prefix.legacy, "_execute", lambda *a, **k: copy.deepcopy(base))
    if capture_failure:
        original = obs.capture

        def capture(value):
            if calls:
                raise OSError("capture failed after actual synthetic return")
            return original(value)

        obs.capture = capture
    return NS(obs=obs, calls=calls, primary=primary, cause=cause)


def test_dispatch_after_one_fresh_prefix_retains_actual_caller(monkeypatch):
    h = harness(monkeypatch)
    result = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    assert result["status"] == "source_completed" and h.obs.mapping_completed
    assert h.calls == ["grids", "grids", "points", "points"]
    assert len(h.obs.mapping_results) == 4 and all(h.obs.mapping_aliases.values())
    assert len([r for r in h.obs.work if r["event"] == "mapping_attempt"]) == 4


def test_prefix_failure_never_enters_mapping_and_keeps_original_result(monkeypatch):
    h = harness(monkeypatch, failure="prefix")
    result = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    assert result["source_error"] == dict(type="prefix") and not h.calls
    assert h.obs.mapping_before is None and h.obs.prefix_execution is result


def test_mapping_unwind_preserves_primary_cause_and_stops_later_probes(monkeypatch):
    h = harness(monkeypatch, failure="mapping")
    result = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    assert result["status"] == "source_failed" and h.obs.mapping_primary is h.primary
    assert h.primary.__cause__ is h.cause and h.calls == ["grids"]
    assert not h.obs.mapping_results


def test_capture_after_return_is_separate_and_stops_later_probes(monkeypatch):
    h = harness(monkeypatch, capture_failure=True)
    result = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    assert result["status"] == "source_failed" and result["source_error"] is None
    assert h.obs.capture_error is not None and h.calls == ["grids"]
    assert not h.obs.mapping_completed


def test_distinct_zero_scaled_inverse_roots_and_third_solve_refusal():
    class Matrix:
        def __truediv__(self, other):
            return Matrix()

    fake = NS(zeros=lambda shape: Matrix(), linalg=NS(pinv=lambda value: Matrix()))
    space = dict(np=fake)
    exec(
        compile(
            "def makeLaplacian(self,**kw):\n"
            "    Z=np.zeros((2,2))\n"
            "    A=Z/2\n"
            "    return A,np.linalg.pinv(A)\n",
            "<synthetic-grid>",
            "exec",
        ),
        space,
    )
    grid_type = type("SyntheticGrid", (), dict(makeLaplacian=space["makeLaplacian"]))
    obs = n.Observation(
        lambda v: dict(retained_type=type(v).__name__), lambda e: dict(message=str(e)), lambda: None
    )
    obs.grid = grid_type()
    obs.caller = NS(grid_obj=obs.grid)
    obs.install_poisson(grid_type)
    for kind in ("value", "flux"):
        obs.grid.makeLaplacian(bound={k: kind for k in ("N", "S", "E", "W")})
    roots = [v for _, pair in obs.poisson_results for v in pair] + [
        v for _, name, v in obs.poisson_helpers if name == "zeros"
    ]
    assert len({id(v) for v in roots}) == 6
    assert len(obs.poisson_helpers) == 4
    with pytest.raises(ValueError, match="two-solve"):
        obs.grid.makeLaplacian(bound={})
    assert len(obs.poisson_results) == 2


@pytest.mark.parametrize("drop_injection", [False, True])
def test_descriptor_factory_reaches_genuine_second_delegate_and_phase_stays_ordinary(
    monkeypatch, drop_injection
):
    h = harness(monkeypatch)
    configuration = {"grid": 25}
    seen = []

    class Parameter:
        def __init__(self, **kw):
            self.__dict__.update(kw)

        @property
        def grid_size(self):
            return self._conf["grid"]

    def containers(**kw):
        result = Parameter(**kw) if "_conf" in kw else NS(**kw)
        seen.append(result)
        return result

    # Reproduce evaluate's two namespace layers, without executing a constructor
    # or descriptor from BETSE. A stub returning a prepared result hides R1.
    scope = dict(SimpleNamespace=NS)
    exec(
        "def delegate(namespace, declared, configuration, **kwargs):\n"
        "    p = SimpleNamespace(_conf=configuration)\n"
        "    phase = SimpleNamespace(p=p)\n"
        "    assert p.grid_size == 25\n"
        "    kwargs['observation'].parameter = phase.p\n"
        "    return dict(status='source_completed', source_body_completed=True, "
        "failed_stage=None, source_error=None, warnings=[])\n",
        scope,
    )
    monkeypatch.setattr(n.prefix.legacy, "_execute", scope["delegate"])
    execute = n.prefix.clone(n._execute, SimpleNamespace=containers)
    if drop_injection:
        monkeypatch.setattr(n.prefix, "clone", lambda function, **kw: function)
        with pytest.raises(AttributeError, match="grid_size"):
            execute({}, {}, configuration, observation=h.obs, native_root=ROOT)
        assert seen == [] and h.calls == []
        assert scope["delegate"].__globals__["SimpleNamespace"] is NS
        return
    result = execute({}, {}, configuration, observation=h.obs, native_root=ROOT)
    assert result["status"] == "source_completed"
    assert type(seen[0]) is Parameter and seen[0]._conf is configuration
    assert type(seen[1]) is NS and seen[1].p is seen[0] is h.obs.parameter
    assert scope["delegate"].__globals__["SimpleNamespace"] is NS


def tail_harness(monkeypatch):
    import numpy as np

    old = [0, 1]
    delegated = []

    def asarray(value):
        delegated.append(value)
        h.returned = np.asarray(value)
        return h.returned

    numpy = NS(asarray=asarray, ones=np.ones, ndarray=np.ndarray)
    scope = dict(np=numpy)
    exec(
        "def make_world(self, phase):\n"
        "    self.cell_i = np.asarray(self.cell_i)\n"
        "    self.gj_default_weights = np.ones(len(self.mem_i))\n",
        scope,
    )
    cls = type("Cells", (), dict(make_world=scope["make_world"]))
    caller = cls()
    caller.cell_i = caller.all_points_cell_i = old
    caller.mem_i = [0, 1]
    caller.X, caller.Y, caller.xypts, caller.map_ij2k = (object() for _ in range(4))
    caller.voronoi_centres = caller.xypts
    caller.points_tree = object()
    grid = caller.grid_obj = NS(
        cents_X=caller.X,
        cents_Y=caller.Y,
        xy_cents=caller.xypts,
        map_ij2k_cents=caller.map_ij2k,
    )
    obs = n.Observation(
        copy.deepcopy, lambda e: dict(type=type(e).__name__, message=str(e)), lambda: None
    )
    obs.caller, obs.grid, obs.trees = caller, grid, [caller.points_tree]
    monkeypatch.setattr(
        n.prefix.Observation, "save", lambda self, label: self.ordinary.append((label, "cache"))
    )
    obs.save("make_maskM")
    obs.install_world_tail(cls)
    h = NS(
        obs=obs,
        caller=caller,
        old=old,
        returned=None,
        delegated=delegated,
        original=scope["make_world"],
        numpy=numpy,
    )
    return h


def test_original_tail_alias_transition_keeps_old_list_and_actual_delegate_return(monkeypatch):
    h = tail_harness(monkeypatch)
    h.caller.make_world(None)
    assert h.delegated == [h.old] and h.delegated[0] is h.old
    assert h.caller.all_points_cell_i is h.old
    assert h.caller.cell_i is h.returned and h.returned is not h.old
    assert type(h.returned) is h.numpy.ndarray and h.returned.tolist() == h.old
    assert h.caller.all_points_cell_i is not h.caller.cell_i
    assert h.obs.tail_asarray_returns[0][0] is h.old
    assert h.obs.tail_asarray_returns[0][1] is h.returned
    assert all(h.obs.tail_aliases().values()) and all(h.obs.environment_aliases.values())
    assert h.caller.make_world.__code__ is h.original.__code__
    assert h.original.__globals__["np"] is h.numpy
    with pytest.raises(ValueError, match="pre-tail"):
        h.caller.make_world(None)
    assert len(h.delegated) == 1


@pytest.mark.parametrize(
    "changed",
    ["input", "alias", "missing", "return", "original_values", "returned_values", "post_alias"],
)
def test_tail_witness_rejects_equal_replacements_and_missing_conversion(monkeypatch, changed):
    h = tail_harness(monkeypatch)
    if changed in {"input", "alias", "original_values"}:
        if changed == "original_values":
            h.old[0] = 99
        else:
            setattr(h.caller, "cell_i" if changed == "input" else "all_points_cell_i", list(h.old))
        with pytest.raises(ValueError, match="pre-tail"):
            h.caller.make_world(None)
        assert not h.delegated
    elif changed == "missing":
        assert h.obs.tail_aliases()["cell_i_is_tail_asarray_return"] is False
    else:
        h.caller.make_world(None)
        if changed == "return":
            h.caller.cell_i = h.returned.copy()
            assert h.obs.array_state(h.caller.cell_i) == h.obs.array_state(h.returned)
            assert h.caller.cell_i is not h.returned
        elif changed == "returned_values":
            h.returned[0] = 99
        else:
            h.caller.all_points_cell_i = list(h.old)
            assert h.caller.all_points_cell_i == h.old and h.caller.all_points_cell_i is not h.old
        assert not all(h.obs.tail_aliases().values())


@pytest.mark.parametrize("bad", ["tuple", "same_list", "float_array", "values", "rank"])
def test_tail_ndarray_type_value_transition_refuses_bad_delegate_returns(monkeypatch, bad):
    import numpy as np

    h = tail_harness(monkeypatch)
    values = {
        "tuple": tuple(h.old),
        "same_list": h.old,
        "float_array": np.asarray(h.old, dtype=float),
        "values": np.asarray([99, 1]),
        "rank": np.asarray([h.old]),
    }
    h.numpy.asarray = lambda value: values[bad]
    h.caller.make_world(None)
    assert h.obs.tail_asarray_returns[0][1] is values[bad]
    assert not all(h.obs.tail_aliases().values())


@pytest.mark.parametrize("bad", ["retarget_list", "retarget_array", "mutate_return"])
def test_tail_transition_drift_stops_before_first_mapping_delegate(monkeypatch, bad):
    h = harness(monkeypatch)
    if bad == "retarget_list":
        h.obs.caller.all_points_cell_i = list(h.obs.pre_tail_cell_i)
    elif bad == "retarget_array":
        h.obs.caller.cell_i = h.obs.caller.cell_i.copy()
    else:
        h.obs.caller.cell_i[0] = 99
    result = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    assert result["status"] == "source_failed" and h.calls == []
    assert h.obs.mapping_before is None and not h.obs.mapping_completed


@pytest.mark.parametrize("replacement", [False, 0.0], ids=["bool", "float"])
@pytest.mark.parametrize("boundary", ["before_tail", "before_mapping"])
def test_tail_equal_valued_scalar_type_change_refuses(monkeypatch, replacement, boundary):
    if boundary == "before_tail":
        h = tail_harness(monkeypatch)
        old_type = type(h.old[0])
        h.old[0] = replacement
        assert tuple(h.old) == h.obs.pre_tail_cell_i_values
        assert type(h.old[0]) is not old_type
        with pytest.raises(ValueError, match="pre-tail"):
            h.caller.make_world(None)
        assert h.delegated == [] and h.obs.tail_asarray_returns == []
    else:
        h = harness(monkeypatch)
        before = h.obs.array_state(h.obs.caller.cell_i)
        h.obs.pre_tail_cell_i[0] = replacement
        assert tuple(h.obs.pre_tail_cell_i) == h.obs.pre_tail_cell_i_values
        assert h.obs.array_state(h.obs.caller.cell_i) == before
        assert h.obs.tail_aliases()["all_points_cell_i_is_original"] is False
        execution = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
        assert execution["status"] == "source_failed" and h.calls == []
        assert h.obs.mapping_before is None and not h.obs.mapping_completed


@pytest.mark.parametrize("secondary", [False, True])
@pytest.mark.parametrize("boundary", ["returned_state", "mapping_witness"])
def test_tail_array_observation_failure_is_capture_and_retains_return(
    monkeypatch, boundary, secondary
):
    error = OSError("tail state observation")
    error.__cause__ = cause = LookupError("original observation cause")
    if boundary == "returned_state":
        h = tail_harness(monkeypatch)
        obs = h.obs
    else:
        h = harness(monkeypatch)
        obs = h.obs
    obs.record_exception = n.prefix.legacy._fallback_error

    def failed_state(value):
        raise error

    obs.array_state = failed_state
    if boundary == "returned_state":
        with pytest.raises(n.prefix.legacy.CaptureFailure) as caught:
            h.caller.make_world(None)
        assert caught.value.__context__ is error and error.__cause__ is cause
        assert h.caller.cell_i is h.old and h.caller.all_points_cell_i is h.old
        assert h.obs.tail_asarray_returns[0][1] is h.returned
        execution = dict(source_body_completed=False, source_error=None, failed_stage="world_tail")
    else:
        execution = n._execute({}, {}, {}, observation=obs, native_root=ROOT)
        assert execution["source_error"] is None and h.calls == []
        assert not obs.mapping_completed
    assert obs.capture_errors[0]["stage"] == "tail_asarray_state"
    assert [row["type"] for row in obs.capture_error["chain"]] == ["OSError", "LookupError"]
    actual = obs.tail_asarray_returns[0][1]
    original_capture = obs.capture

    def capture(value):
        if secondary and value is obs.tail_asarray_returns:
            raise OSError("secondary tail return archive")
        return original_capture(value)

    obs.capture = capture
    result = finalize_stub(monkeypatch, obs, execution)
    assert result["source_error"] is None and result["status"] == "source_failed"
    assert obs.tail_asarray_returns[0][1] is actual
    if secondary:
        assert "tail_asarray_returns" not in result
        assert result["capture_errors"][-1]["stage"] == "mapping_final_tail_asarray_returns"
    else:
        saved = result["tail_asarray_returns"][0][1]
        assert type(saved) is type(actual) and saved.tobytes() == actual.tobytes()


def finalize_stub(monkeypatch, obs, execution):
    monkeypatch.setattr(
        n.prefix,
        "_finalize_reference",
        lambda *args, probes, **kwargs: dict(aliases=probes["aliases"]()),
    )
    return n._finalize(obs, execution, {}, sites={}, image_sha256="0" * 64, source_attempted=True)


def test_environment_alias_is_historical_not_recomputed_after_tail(monkeypatch):
    h = tail_harness(monkeypatch)
    h.caller.make_world(None)
    execution = dict(source_body_completed=False, source_error=None, failed_stage="held")
    result = finalize_stub(monkeypatch, h.obs, execution)
    assert result["environment"]["aliases"]["all_points_cell_i_is_cell_i"] is True
    assert h.caller.all_points_cell_i is not h.caller.cell_i
    rows = result["tail_asarray_returns"]
    assert len(rows) == 1 and rows[0][0] == h.old
    assert type(rows[0][1]) is h.numpy.ndarray
    assert h.obs.array_state(rows[0][1]) == h.obs.array_state(h.returned)
    assert h.obs.tail_asarray_returns[0][1] is h.returned


@pytest.mark.parametrize("where", ["stop", "snapshot"])
def test_actual_return_retained_before_observer_failure_and_recaptured(monkeypatch, where):
    h = harness(monkeypatch, capture_failure=where == "snapshot")
    error = OSError("post-return observer failure")
    if where == "stop":
        original = h.obs.stop

        def stop():
            if h.obs.mapping_raw_results and h.obs.capture_error is None:
                h.obs.remember(error, "post_return_stop")
            original()

        h.obs.stop = stop
    execution = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    assert execution["status"] == "source_failed" and execution["source_error"] is None
    assert h.calls == ["grids"] and not h.obs.mapping_results
    name, returned = h.obs.mapping_raw_results[0]
    assert name == "grid_1d" and returned is h.obs.mapping_inputs[0]["data"]
    captured = []

    def capture(value):
        captured.append(value)
        return copy.deepcopy(value)

    h.obs.capture = capture
    result = finalize_stub(monkeypatch, h.obs, execution)
    assert any(value is returned for value in captured)
    assert result["mapping_return_captures"][0] == dict(
        name=name,
        status="saved",
        value=returned,
        capture_error=None,
    )
    assert not result["mapping_return_capture_gaps"]
    assert result["status"] == "source_failed" and result["capture_error"] is not None
    assert result["source_error"] is None and result["results"] == []


def test_failed_forensic_return_capture_does_not_hide_other_returns_or_primary(monkeypatch):
    h = harness(monkeypatch)
    first, second = object(), object()
    h.obs.mapping_raw_results = [("grid_1d", first), ("grid_2d", second)]
    primary = ValueError("original source")
    cause = RuntimeError("source cause")
    primary.__cause__ = cause
    h.obs.mapping_primary = primary
    seen = []

    def capture(value):
        seen.append(value)
        if value is first:
            raise OSError("first forensic capture failed")
        return "second-return" if value is second else copy.deepcopy(value)

    h.obs.capture = capture
    execution = dict(
        source_body_completed=False, failed_stage="points_1d", source_error=dict(type="ValueError")
    )
    result = finalize_stub(monkeypatch, h.obs, execution)
    rows = result["mapping_return_captures"]
    assert [r["status"] for r in rows] == ["unavailable", "saved"]
    assert rows[0]["value"] is None and rows[0]["capture_error"]["type"] == "OSError"
    assert rows[1]["value"] == "second-return" and result["mapping_return_capture_gaps"] == [
        "grid_1d"
    ]
    assert seen[0] is first and seen[1] is second
    assert h.obs.mapping_primary is primary and primary.__cause__ is cause
    assert (
        result["source_error"] is execution["source_error"] and result["status"] == "source_failed"
    )


@pytest.mark.parametrize("where", ["stop", "snapshot", "registration"])
@pytest.mark.parametrize("forensic_fails", [False, True])
def test_direct_return_array_survives_observation_failure_with_independent_forensics(
    monkeypatch, tmp_path, where, forensic_fails
):
    import numpy as np

    h = harness(monkeypatch, capture_failure=where == "snapshot")

    def direct(actual, data, **kwargs):
        h.calls.append("grids")
        return np.asarray(data)

    monkeypatch.setattr(type(h.obs.caller), "map_cells_centre_to_grids_centre", direct)
    initial = OSError("post-return " + where)
    if where == "stop":
        stop = h.obs.stop

        def failed_stop():
            if h.obs.last_probe_result is not None and h.obs.capture_error is None:
                h.obs.remember(initial, "direct_return_stop")
            stop()

        h.obs.stop = failed_stop
    elif where == "registration":

        class FailedRegistration(list):
            def append(self, value):
                raise initial

        h.obs.mapping_raw_results = FailedRegistration()
    execution = n._execute({}, {}, {}, observation=h.obs, native_root=ROOT)
    name, returned = h.obs.last_probe_result
    assert type(returned) is np.ndarray and name == "grid_1d"
    assert returned.tolist() == h.obs.mapping_inputs[0]["data"]
    assert execution["status"] == "source_failed" and execution["source_error"] is None
    assert h.calls == ["grids"] and h.obs.mapping_results == []
    if where == "registration":
        assert h.obs.mapping_raw_results == []
    else:
        assert h.obs.mapping_raw_results[0] is h.obs.last_probe_result
    attempted = []
    secondary = OSError("independent forensic capture")

    def capture(value):
        attempted.append(value)
        if value is returned and forensic_fails:
            raise secondary
        return copy.deepcopy(value)

    h.obs.capture = capture
    result = finalize_stub(monkeypatch, h.obs, execution)
    assert attempted[0] is returned
    row = result["mapping_return_captures"][0]
    assert row["name"] == name
    if forensic_fails:
        assert row["status"] == "unavailable" and row["capture_error"]["type"] == "OSError"
        assert result["mapping_return_capture_gaps"] == [name]
    else:
        assert row["status"] == "saved" and type(row["value"]) is np.ndarray
        assert h.obs.array_state(row["value"]) == h.obs.array_state(returned)
        assert result["mapping_return_capture_gaps"] == []
    assert result["status"] == "source_failed" and result["source_error"] is None
    assert result["results"] == [] and h.obs.mapping_completed is False
    (tmp_path / "direct-return-evidence.json").write_text(
        json.dumps(
            dict(
                boundary=where,
                forensic_failed=forensic_fails,
                name=name,
                raw_dtype=returned.dtype.str,
                raw_shape=returned.shape,
                raw_strides=returned.strides,
                raw_bytes_hex=returned.tobytes().hex(),
                last_result_is_actual_return=True,
                no_later_probe=h.calls == ["grids"],
                source_error=result["source_error"],
                capture_error=result["capture_error"],
                forensic_status=row["status"],
                forensic_error=row["capture_error"],
                completed_results=result["results"],
            ),
            sort_keys=True,
            indent=2,
        )
    )
