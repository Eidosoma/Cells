"""Native-blocked metadata controls for the complete live source dispatcher."""

import os
from contextlib import contextmanager
from types import FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest
from PIL import Image

from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import native_seed_world_geometry_qualification as stage

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(stage.SOFTWARE_RELEASE) != "1":
        pytest.skip("Whole-feature source preparation; blocked controls require release")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(stage), reuse=stage.controls_runner.reuse.reuse))
    # The shared fixture checks its real WPC issuance registry. This diagnostic
    # dispatcher has no owner registry of its own and never invents one.
    namespace = dict(vars(controls), software=adapter, _BLOCKADE_FAILURES=())
    original = controls._blockade.__wrapped__
    function = FunctionType(original.__code__, namespace, original.__name__)
    try:
        with contextmanager(function)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace)


def test_plan_genuine_same_parameter_chain_stops_before_Poisson_and_pins_held():
    plan = stage.source_plan()
    assert plan["stages"] == ("phase", "lattice", "image", "mesh", "lifecycle", "geometry")
    assert plan["parameter_source"] is plan["parameter_review"] is None
    assert all(value is None for value in plan["module_sources"].values())
    assert all(value is None for value in plan["module_reviews"].values())
    assert "make_maskM" in plan["endpoint"] and "before first Poisson" in plan["endpoint"]
    assert plan["actual_live_inputs"] == ("WorldReadyParametersOwner", "CallbackOwner")
    assert plan["actual_release"] is False and plan["invalidated_postcut_owners"] == 11
    assert plan["held_postcut_cases"] == 12
    assert Image.__name__ == "PIL.Image"  # Definitions only; no decoder/image/RNG entry.


@pytest.mark.parametrize("entry", ["evaluate", "acquire", "dependencies"])
def test_unreleased_or_unbound_entry_refuses_before_any_foreign_parent_access(entry, tmp_path):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No fake parent access")

    with pytest.raises(stage.QualificationRejected) as caught:
        if entry == "evaluate":
            stage.evaluate_live(Foreign(), Foreign(), tmp_path / "out", enabled=False)
        elif entry == "acquire":
            stage.acquire_and_evaluate(
                Foreign(),
                tmp_path / "out",
                packet_sha256="x",
                callback_owner=Foreign(),
                enabled=False,
            )
        else:
            stage._dependencies()
    assert caught.value.stage == ("unbound" if entry == "dependencies" else "release")
    assert not (tmp_path / "out").exists()


class Evidence:
    def __init__(self, failure_label=None):
        self.failure_label, self.rows = failure_label, []

    def save(self, label, value):
        self.rows.append((label, value))
        return label != self.failure_label

    def failure(self, error):
        self.rows.append(("failure", error))


def _metadata_chain(fail=None):
    """Private dispatch stand-ins only: no production owner is manufactured."""
    calls, owners = [], []
    primary = ValueError("source sentinel")
    primary.__cause__ = KeyError("same cause")

    class Owner:
        def __init__(self, name):
            self.name, self.retired = name, False
            self.saved = NS(label=name, cache=None)
            self.phase = NS(p=None)
            owners.append(self)

        @property
        def trial(self):
            assert not self.retired, "A consumed parent's numeric validator was reopened"
            calls.append((self.name, "trial"))
            return self.saved

    modules = {}
    for label, alias in (
        ("phase", "world"),
        ("lattice", "prefix"),
        ("image", "image"),
        ("mesh", "mesh"),
        ("lifecycle", "lifecycle"),
        ("geometry", "geometry"),
    ):

        def request(previous, *args, label=label, **kwargs):
            calls.append((label, "request", previous))
            return NS(parent=previous)

        def prepare(value, *, enabled, label=label):
            assert enabled is True
            calls.append((label, "prepare", value.parent))
            if label == fail:
                raise primary
            if isinstance(value.parent, Owner):
                value.parent.retired = True
            return Owner(label)

        module = NS(
            LAW_ID=label,
            MODE="metadata-mode",
            prepare=prepare,
            trial_record=lambda value: dict(label=value.label),
        )
        if label == "phase":
            module.from_world_ready = request
            module._trial_record = module.trial_record
        else:
            setattr(
                module,
                {
                    "lattice": "from_phase",
                    "image": "from_prefix",
                    "mesh": "from_image",
                    "lifecycle": "from_constructor",
                    "geometry": "from_lifecycle",
                }[label],
                request,
            )
        modules[alias] = module
    return modules, calls, owners, primary


@pytest.mark.parametrize(
    "fail", [None, "phase", "lattice", "image", "mesh", "lifecycle", "geometry"]
)
def test_dispatcher_one_real_call_per_stage_retains_exact_success_or_primary_without_hydration(
    fail,
):
    modules, calls, owners, primary = _metadata_chain(fail)
    ready, callbacks = object(), object()
    state, evidence = stage.Execution(world_ready=ready, callback_owner=callbacks), Evidence()
    if fail is None:
        final = stage._execute_chain(state, modules, evidence)
        assert final is owners[-1] is state.result and state.source_completed
        assert all(owner.retired for owner in owners[:-1]) and not final.retired
        assert [row[0] for row in calls if row[1] == "prepare"] == list(stage.STAGES)
        assert [name for name, _ in state.owners] == list(stage.STAGES)
        assert [name for name, _ in state.trials] == list(stage.STAGES)
    else:
        with pytest.raises(ValueError) as caught:
            stage._execute_chain(state, modules, evidence)
        assert caught.value is state.source_error is primary
        assert primary.__cause__.args == ("same cause",)
        assert not state.source_completed and state.result is None
        assert [row[0] for row in calls if row[1] == "prepare"] == list(
            stage.STAGES[: stage.STAGES.index(fail) + 1]
        )
        assert all(
            owner is retained for (_, owner), retained in zip(state.owners, owners, strict=True)
        )
    assert state.world_ready is ready and state.callback_owner is callbacks


@pytest.mark.parametrize("stage_name", list(stage.STAGES))
def test_return_is_retained_before_capture_failure_and_no_next_source_stage(stage_name):
    modules, calls, owners, _ = _metadata_chain()
    state = stage.Execution(world_ready=object(), callback_owner=object())
    evidence = Evidence(stage_name + ".record")
    with pytest.raises(RuntimeError, match="Typed capture refused") as caught:
        stage._execute_chain(state, modules, evidence)
    assert state.source_error is None and state.capture_errors[-1][1] is caught.value
    assert state.last_return is owners[-1] and state.owners[-1][1] is owners[-1]
    assert not state.source_completed
    assert [row[0] for row in calls if row[1] == "prepare"] == list(
        stage.STAGES[: stage.STAGES.index(stage_name) + 1]
    )


def test_lossless_cache_capture_keeps_source_layout_and_all_original_numeric_bits():
    from cells.processes import betse_initial_mesh_preparation_cache as caches

    original = np.array([1.0, -0.0])[::-1]
    cache = caches.snapshot(dict(value=original))
    state, evidence = stage.Execution(), Evidence()
    stage._capture_caches(state, evidence, "trial", cache)
    assert len(evidence.rows) == 1
    payload = evidence.rows[0][1]
    assert payload["descriptor_json"] == cache.descriptor_json
    assert payload["identity"] == cache.identity
    assert payload["columns"]["column_00000"].tobytes() == original.tobytes()
    assert payload["columns"]["column_00000"].view(np.uint64)[0] == 1 << 63
    assert payload["live_owner_or_checkpoint_admission"] is False


def test_live_diagnostic_state_has_no_ordinary_checkpoint_or_plain_hydration_route():
    with pytest.raises(TypeError, match="hydration"):
        stage.Execution().__reduce_ex__(4)


@pytest.mark.parametrize("site", ["failure_forensics", "final_outcome", "both"])
def test_failed_final_capture_retains_original_primary_cause_and_all_raw_state(site, tmp_path):
    primary, cause = ValueError("original source"), KeyError("original cause")
    primary.__cause__ = cause
    state = stage.Execution(source_error=primary, primary=primary, last_return=object())
    attempts = []
    captures = (RuntimeError("forensics"), OSError("outcome"))

    class FailingEvidence(Evidence):
        def failure(self, value):
            attempts.append(("failure", value))
            if site in ("failure_forensics", "both"):
                raise captures[0]

    def write(path, value):
        attempts.append(("outcome", path, value))
        if site in ("final_outcome", "both"):
            raise captures[1]

    seal = FunctionType(
        stage._seal_execution.__code__,
        dict(vars(stage), snapshot=NS(write_json=write)),
    )
    seal(state, FailingEvidence(), tmp_path)
    assert state.source_error is state.primary is primary and primary.__cause__ is cause
    assert [row[0] for row in attempts] == ["failure", "outcome"]
    expected = [
        label for label in ("failure_forensics", "final_outcome") if site == label or site == "both"
    ]
    assert [label for label, _, _ in state.capture_errors] == expected
    assert all(
        error is captures[(label == "final_outcome")] for label, error, _ in state.capture_errors
    )
    assert state.last_return is not None and state.result is None


@pytest.mark.parametrize("mask_value", [0.0, float("nan"), float("inf"), 1.0])
def test_diagnostics_keep_native_mask_bits_and_separate_domain_from_source_equality(mask_value):
    points = np.array([[0.0, 0.0], [1.0, 1.0]])
    mask = np.full((2, 2), mask_value)
    original_bits = mask.tobytes()
    caller = NS(
        cell_i=[0, 1],
        mem_i=np.arange(4),
        ecm_verts_unique=points,
        xypts=points,
        cell_centres=points,
        maskM=mask,
        maskECM=mask,
        voronoi_mask=np.ones((2, 2)),
        cell_vol=np.ones(2),
        mem_vol=np.ones(4),
        ecm_vol=1.0,
        xmin=0.0,
        xmax=1.0,
        ymin=0.0,
        ymax=1.0,
    )
    result = stage.diagnostics(caller)
    assert mask.tobytes() == original_bits and caller.maskM is caller.maskECM is mask
    assert result["domain_gate_passed"] is (mask_value == 1.0)
    assert result["physical_admission"] is result["independent_geometric_accuracy"] is False
    assert result["support"]["maskM"]["finite"] is bool(np.isfinite(mask_value))
    assert result["population"]["cells"] == 2
    assert result["geometry"]["cell_centres"]["inside_native_bounds"] == 2


def test_metadata_dependency_preflight_checks_all_selected_bytes_before_stage_import():
    from types import ModuleType

    calls = []
    parameter = ModuleType("metadata_parameter_only")
    parameter.POLICY = dict(cpu=stage.NATIVE_CPU)

    def template():
        raise AssertionError("No parameter or native source execution")

    for name in ("acquire_world_ready", "prepare", "packet_inputs"):
        setattr(parameter, name, FunctionType(template.__code__, vars(parameter)))

    def path(name, pin):
        calls.append(("hash", name, pin))

    def bound(name, pin):
        calls.append(("import", name, pin))
        assert name == stage.PARAMETER_ENTRY_MODULE
        return parameter

    namespace = dict(
        vars(stage),
        PARAMETER_ENTRY_SOURCE_SHA256="a" * 64,
        PARAMETER_ENTRY_REVIEW_SHA256="b" * 64,
        MODULE_SOURCE_SHA256=dict.fromkeys(stage.MODULES, "c" * 64),
        MODULE_REVIEW_SHA256=dict.fromkeys(stage.MODULES, "d" * 64),
        _producer_path=path,
        _bound_module=bound,
    )
    function = FunctionType(stage._dependencies.__code__, namespace)
    assert function(stages=False) == (parameter, None)
    assert [row[1] for row in calls if row[0] == "hash"] == list(stage.MODULES.values())
    assert [row[1] for row in calls if row[0] == "import"] == [stage.PARAMETER_ENTRY_MODULE]


@pytest.mark.parametrize("cpu", [0, 2, 6])
def test_native_parameter_cpu_contract_is_separate_from_software_and_never_switches(cpu):
    environment = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"),
        "1",
    )
    environment["CUDA_VISIBLE_DEVICES"] = ""
    reads = []

    def path(name):
        assert name == "/proc/meminfo"
        reads.append(name)
        return NS(read_text=lambda: "MemAvailable: 20000000 kB\n")

    namespace = dict(
        vars(stage),
        os=NS(sched_getaffinity=lambda pid: {cpu}, environ=environment),
        resource=NS(RLIMIT_AS=9, getrlimit=lambda limit: (2**30, 2**30)),
        Path=path,
    )
    check = FunctionType(stage._resources.__code__, namespace)
    if cpu == 0:
        assert check() is None and reads == ["/proc/meminfo"]
    else:
        with pytest.raises(stage.QualificationRejected) as caught:
            check()
        assert caught.value.stage == "resources" and reads == []
    plan = stage.source_plan()
    assert plan["native_policy"]["cpu"] == stage.NATIVE_CPU == 0
    assert plan["software_policy"]["cpu"] == 6
