"""Fresh real issuer chain with declared pre-birth toy bodies; no native credit."""

import ast
import contextlib
import os
import sys
import time
from types import CodeType, FunctionType

import pytest

from cells.processes import betse_native_init_terminal as stage
from cells.processes import betse_native_init_terminal_molecules as participant
from tests.unit import test_betse_native_init_dynamics_completion as completion_model
from tests.unit import test_betse_native_init_short_history as history
from validation.betse import betse_native_init_terminal_issued_software as software

_RAW_CAPTURE_FAILURES = []


def _retain_secondary(path, primary, secondary):
    """A failed diagnostic writer must never replace the active source error."""
    _RAW_CAPTURE_FAILURES.append((path, primary, secondary))
    try:
        software.snapshot.write_json(
            path,
            dict(
                primary=software.compact_error(primary),
                secondary=software.compact_error(secondary),
                complete=False,
            ),
        )
    except BaseException as writer:
        _RAW_CAPTURE_FAILURES.append((path, primary, writer))


def _failed_context(h, current):
    if current is not None:
        return current
    # The request and consumption edge must be the actual issuer's, including
    # a failure before the generator could yield its Completion owner.
    for api, field in (
        (completion_model.stage, "completion_request"),
        (completion_model.stage.previous, "dynamics_request"),
        (history.guard_model.stage, "request"),
    ):
        request = vars(h).get(field)
        if type(request) is api.Request and request in api._REQUESTS:
            partial = api._CONSUMED.get(request)
            if partial is not None and partial.request is request:
                return partial
    return None


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit frozen software release required")
    if (
        request.node.name in software.ISSUED_CASES
        and os.environ.get(software.ISSUED_RELEASE) != "1"
    ):
        pytest.skip("Exact released issued-terminal envelope required")
    namespace = dict(vars(history.guard_model), software=software, _RAW_GUARDS=[])
    fn = FunctionType(history.guard_model.blocked.__wrapped__.__code__, namespace)
    with contextlib.contextmanager(fn)(request, tmp_path, monkeypatch):
        yield


TOY_CLOCK_AND_CALLER = """
def _plot_loop(self, phase):
    return calendar, sampled, noop_context()
def setup(self, phase):
    time_steps, time_steps_sampled, solver_context = self._plot_loop(phase)
    exception_instability = None
    phase.callbacks.progress_ranged(progress_max=len(time_steps_sampled))
    with solver_context:
        self._run_sim_core_loop(phase, time_steps, time_steps_sampled, None)
"""


@contextlib.contextmanager
def declared_noop_context():
    """Declared toy solver scope; stdlib context machinery is real and retained."""
    yield


def _toy_functions(text, namespace):
    """Compile only declared toy bodies with this file's actual producer path."""
    code = compile(ast.parse(text), __file__, "exec", dont_inherit=True)
    return {
        value.co_name: FunctionType(value, namespace)
        for value in code.co_consts
        if type(value) is CodeType
    }


def _terminal_inputs(monkeypatch, tmp_path, *, retained_flux, failed):
    """Compose the same real acquisition before any public issuer runs."""
    old_ready = history.runtime_provider._ready
    h = history._issued_history_inputs(
        monkeypatch, tmp_path, retained_flux=retained_flux, failed=failed
    )
    # H's fixture configures its own provider. It is not this route's provider;
    # restore it before any issuer, rather than changing an already-issued owner.
    monkeypatch.setattr(history.runtime_provider, "_ready", old_ready)
    closure = dict(
        zip(
            history.stage._engine.__code__.co_freevars,
            (cell.cell_contents for cell in history.stage._engine.__closure__),
            strict=True,
        )
    )
    namespace_builder = closure["namespace_builder"]
    namespace, tree = h.first_step_namespace, h.first_step_tree
    replacement = ast.parse(TOY_CLOCK_AND_CALLER)
    selected = {node.name: node for node in replacement.body}
    tree.body[:] = [selected.get(getattr(node, "name", None), node) for node in tree.body]
    functions = _toy_functions(ast.unparse(ast.fix_missing_locations(tree)), namespace)
    namespace.update(
        {
            name: functions[name]
            for name in ("setup", "_plot_loop", "_run_sim_core_loop", "update_V", "write2storage")
        }
    )
    # Compile a single consistent source tree so callback bytecode positions
    # and the actual source acquisition tree describe the same declaration.
    normalized = ast.parse(ast.unparse(tree))
    tree.body[:] = normalized.body
    factory = h.factories["Simulator"]
    for name in ("_plot_loop", "_run_sim_core_loop", "update_V", "write2storage"):
        setattr(factory, name, namespace[name])
    factory.run_sim_core = namespace["setup"]
    actual_engine = stage._engine

    def terminal_namespace(context):
        namespace_builder(context)
        stage._bind_loop_span(context)
        context.noop_type = contextlib._GeneratorContextManager
        context.noop_methods = (context.noop_type.__enter__, context.noop_type.__exit__)
        context.noop_generator = declared_noop_context.__wrapped__
        context.external["noop_context"] = declared_noop_context
        wrapper = context.runtime["_helper"](context, "noop_context")
        context.wrappers["noop_context"] = wrapper
        private = dict(namespace, noop_context=wrapper)
        original = context.methods["_plot_loop"]
        context.methods["_plot_loop"] = FunctionType(
            original.__code__,
            private,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        context.namespaces += ((private, tuple(private.items())),)
        entries = (
            (declared_noop_context, "noop_context"),
            (declared_noop_context.__wrapped__, "noop_context_generator"),
            (context.noop_methods[0], "solver_context_enter"),
            (context.noop_methods[1], "solver_context_exit"),
        )
        for function, name in entries:
            context.allowed_codes |= frozenset((function.__code__,))
            context.body_names[function.__code__] = name
        context.permissions = stage._mutation_contract(context)

    def engine(context):
        values = actual_engine(context)
        values["_namespace"] = terminal_namespace
        values["_domain"] = lambda child: (
            None
        )  # Only predeclared toy bodies, never native FULL admission.
        return values

    electrical, storage = stage.base.previous, stage.base.previous.storage
    for name, value in dict(
        TERMINAL_INIT_ANCESTOR_CLAIM="_claim_terminal_init_ancestor",
        TERMINAL_INIT_ANCESTOR_CHECK="_check_terminal_init_ancestor",
    ).items():
        monkeypatch.setattr(storage, name, value)
    functions = (electrical._claim_for_terminal_init, electrical._check_terminal_init_authority)
    parent = stage.base._ParentBinding(
        electrical, *functions, tuple(electrical._parent_atoms(fn) for fn in functions)
    )

    def ready():
        stage._parent(parent)
        return parent

    def binding():
        names = (
            "prepare",
            "_ready",
            "_claim_wrapper",
            "_dispatch",
            "_check_ancestor_metadata",
            "_mutation_contract",
            "_configured_count",
            "_terminal_runtime_status",
        )
        return electrical._StepBinding(
            stage,
            tuple(
                (name, vars(stage)[name], storage._electrical_atoms(vars(stage)[name]))
                for name in names
            ),
        )

    monkeypatch.setattr(stage, "_engine", engine)
    monkeypatch.setattr(stage, "_ready", ready)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(declared_synthetic_terminal_only=True))
    for name, value in dict(
        PARENT_CLAIM="_claim_for_terminal_init",
        PARENT_CHECK="_check_terminal_init_authority",
        RUNTIME_BEGIN="begin_iteration",
        RUNTIME_END="finish_iteration",
        RUNTIME_CONTRACT=participant.LAW_ID,
        RUNTIME_SOURCE_SHA256=software.snapshot.digest(stage.Path(participant.__file__)),
    ).items():
        monkeypatch.setattr(stage, name, value)
    monkeypatch.setattr(electrical, "_terminal_init_api", binding)
    monkeypatch.setattr(completion_model.stage, "_molecule_terminal_api", lambda: participant)
    monkeypatch.setattr(participant, "_ready", lambda: stage)
    monkeypatch.setenv(stage.RELEASE, "1")
    stage._parent(stage._ready())
    electrical._check_step_binding(electrical._terminal_init_api())
    h.inherited_fixture_declarations = h.seams
    h.seams = (
        "complete declared five-label calendar, actual normal loop/caller/context returns",
        "same fresh public INIT/Completion/Storage/Electrical ancestry; no H owner reused",
        "declared pre-birth toy context/caller, not original BETSE solver/native authority",
        "retained operator presence is a toy ownership input, not native operator admission",
    )
    return h


def _run_issued_terminal(monkeypatch, tmp_path, *, retained_flux, failed):
    h = _terminal_inputs(monkeypatch, tmp_path, retained_flux=retained_flux, failed=failed)
    generator = completion_model.issued_synthetic_completion.__wrapped__(
        h, monkeypatch, tmp_path, native_molecules=True
    )
    primary = current = expected = None
    outcomes = []
    started = time.monotonic()
    try:
        h = next(generator)
        original = h.completion_context
        prior = h.completion_owner
        for label, api, declaration in (
            ("storage", stage.base.previous.storage, "from_dynamics"),
            ("electrical", stage.base.previous, "from_storage"),
            ("terminal", stage, "from_electrical"),
        ):
            kwargs = dict(law_id=api.LAW_ID)
            if api is stage:
                kwargs["maximum"] = 512
            request = getattr(api, declaration)(prior, **kwargs)
            try:
                prior = api.prepare(request, enabled=True)
            except BaseException as error:
                current = api._CONSUMED.get(request)
                if api is not stage or not failed:
                    raise
                assert isinstance(error, stage.InitTerminalRejected)
                assert (
                    error.__cause__ is h.synthetic_error
                    and h.synthetic_error.__cause__ is h.synthetic_cause
                )
                assert (
                    current.invalid
                    and current.timeline.completed == 1
                    and current.timeline.current[0] == 1
                )
                assert current.trial is None and not hasattr(current, "owner")
                expected = h.synthetic_error
                with pytest.raises(stage.InitTerminalRejected, match="attempted"):
                    stage.prepare(request, enabled=True)
                history.interpreter_model._chain_checkpoint(
                    tmp_path, "terminal-mid-failure", current, error=error
                )
                outcomes.append(dict(stage=label, status="expected_failed", completed=1))
                break
            current = api._authority(prior)
            assert all(
                getattr(current, name) is getattr(original, name)
                for name in ("phase", "sim", "cells", "p", "handler")
            )
            history.interpreter_model._chain_checkpoint(tmp_path, label, current)
            outcomes.append(dict(stage=label, status="completed", trial=current.trial.identity))
        if not failed:
            assert type(prior) is stage.InitTerminalOwner
            assert (
                current.timeline.completed == h.p.init_tsteps == 5
                and current.timeline.current is None
            )
            assert (
                len(current.trial.iterations) == 5
                and current.time_steps is h.calendar
                and current.sampled is h.sampled
            )
            assert (
                not current.selected_stopped and current.loop_returned and current.context_returned
            )
            status = stage._terminal_runtime_status(current)
            assert status is current.terminal_status and status.before_native_pickle is True
            assert (
                participant.validate_runtime(current.molecule_claim, child=current)
                is current.molecule_record
            )
        software.snapshot.write_json(
            tmp_path / "issued-terminal-outcome.json",
            dict(
                status="completed_control",
                failed=failed,
                retained_flux=retained_flux,
                outcomes=outcomes,
                seams=h.seams,
                inherited_fixture_declarations=h.inherited_fixture_declarations,
                inherited_H_or_first_step_iterations_are_not_executed=True,
                elapsed_seconds=time.monotonic() - started,
                configured_count=5,
                maximum=512,
                distinct_inputs=1,
                work_and_prefixes_are_not_independent_cases=True,
                native_or_scientific_credit=0,
            ),
        )
    except BaseException as error:
        primary = error
        current = _failed_context(h, current)
        if current is not None:
            try:
                history.interpreter_model._chain_checkpoint(
                    tmp_path, "terminal-control-failure", current, error=error
                )
            except BaseException as capture:
                _retain_secondary(tmp_path / "capture-failure.json", error, capture)
        raise
    finally:
        try:
            generator.close()
        except BaseException as cleanup:
            _retain_secondary(
                tmp_path / "cleanup-secondary.json",
                primary if primary is not None else expected,
                cleanup,
            )
            if primary is None:
                raise


def test_terminal_issued_value_only(monkeypatch, tmp_path):
    _run_issued_terminal(monkeypatch, tmp_path, retained_flux=False, failed=False)


def test_terminal_issued_retained_flux(monkeypatch, tmp_path):
    _run_issued_terminal(monkeypatch, tmp_path, retained_flux=True, failed=False)


def test_terminal_issued_mid_failure_value_only(monkeypatch, tmp_path):
    _run_issued_terminal(monkeypatch, tmp_path, retained_flux=False, failed=True)


def test_terminal_issued_mid_failure_retained_flux(monkeypatch, tmp_path):
    _run_issued_terminal(monkeypatch, tmp_path, retained_flux=True, failed=True)


@pytest.mark.parametrize(
    "select,seconds",
    (
        (software.ISSUED_CASES[1], 1800),
        ("metadata", 1800),
        (" or ".join(software.ISSUED_CASES[:2]), 480),
        ("metadata", 0),
    ),
)
def test_terminal_issued_policy_refuses_unreleased_case_or_budget(select, seconds):
    with pytest.raises(ValueError):
        software._policy(select, seconds)


def test_terminal_issued_no_supplied_owner_or_missing_real_issuer_permission():
    with pytest.raises(stage.InitTerminalRejected):
        stage._authority({})
    with pytest.raises(TypeError):
        stage.InitTerminalOwner()
    assert not software._issued_driver(sys._getframe())


def test_terminal_issued_clock_declaration_has_full_context_and_native_order_without_evaluation():
    tree = ast.parse(TOY_CLOCK_AND_CALLER)
    nodes = {node.name: node for node in tree.body}
    assert ast.unparse(nodes["setup"].body[1]) == "exception_instability = None"
    assert isinstance(nodes["setup"].body[-1], ast.With)
    assert "noop_context()" in ast.unparse(nodes["_plot_loop"])
    assert not any(isinstance(node, ast.Raise) for node in ast.walk(tree))
    assert participant.MAX_ITERATIONS == stage.MAX_ITERATIONS == 512
    assert history.runtime_provider.MAX_ITERATIONS == history.stage.MAX_ITERATIONS == 64


@pytest.mark.parametrize(
    "retained_flux,failed", ((False, False), (True, False), (False, True), (True, True))
)
def test_terminal_issued_prebirth_declaration_keeps_real_issuers_and_both_runtime_caps(
    monkeypatch, tmp_path, retained_flux, failed
):
    modules = (
        history.guard_model.stage,
        completion_model.stage.previous,
        completion_model.stage,
        stage.base.previous.storage,
        stage.base.previous,
        stage,
    )
    original = [
        (module, module.prepare, module._REQUESTS, len(module._REQUESTS)) for module in modules
    ]
    prior_ready = history.runtime_provider._ready
    h = _terminal_inputs(monkeypatch, tmp_path, retained_flux=retained_flux, failed=failed)
    assert not hasattr(h, "owner") and not hasattr(h, "completion_owner")
    assert all(
        module.prepare is function and module._REQUESTS is requests and len(requests) == count
        for module, function, requests, count in original
    )
    assert history.runtime_provider._ready is prior_ready
    assert h.p.init_tsteps == len(h.calendar) == 5
    assert h.first_step_namespace["calendar"] is h.calendar
    assert h.first_step_namespace["sampled"] is h.sampled
    assert (h.cells.lapENV_P_inv is h.cells.environment) is retained_flux
    assert (h.cells.lapENV_P_inv is None) is (not retained_flux)
    assert h.upstream.phase.callbacks is h.callback
    assert h.factories["Simulator"].run_sim_core is h.first_step_namespace["setup"]
    assert h.first_step_namespace["setup"].__code__.co_filename == __file__
    assert participant.MAX_ITERATIONS == 512 and history.runtime_provider.MAX_ITERATIONS == 64
    software.snapshot.write_json(
        tmp_path / "prebirth-terminal-declaration.json",
        dict(
            configured_count=5,
            retained_flux=retained_flux,
            declared_mid_failure=failed,
            new_issued_requests=0,
            actual_native_operator_RNG_or_scientific_credit=0,
            seams=h.seams,
            inherited_fixture_declarations=h.inherited_fixture_declarations,
        ),
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("cpu", 6),
        ("cpu", True),
        ("threads", 2),
        ("wall_seconds", 1800),
        ("software_bytes", 2**31),
        ("reserve_bytes", 0),
        ("selection", "other"),
        ("software_release_requested", 1),
        ("terminal_issued_synthetic", False),
    ),
)
def test_terminal_issued_resource_and_exact_selection_refuse_before_owner_entry(field, value):
    inputs = dict(
        cpu=7,
        threads=1,
        metadata_bytes=512 * 2**20,
        software_bytes=2**30,
        reserve_bytes=8 * 2**30,
        wall_seconds=480,
        software_release_requested=True,
        selection="metadata",
        terminal_issued_synthetic=True,
        software_integration_envelope=None,
    )
    software._prepared(inputs, "metadata", 480)
    inputs[field] = value
    with pytest.raises(ValueError):
        software._prepared(inputs, "metadata", 480)


@pytest.mark.parametrize(
    "module",
    (
        "cells.processes.betse_native_init_terminal",
        "cells.processes.betse_native_init_electrical",
        "cells.processes.betse_native_init_storage",
    ),
)
def test_terminal_issued_guard_never_accepts_a_supplied_frame_receipt(module):
    from types import SimpleNamespace

    supplied = SimpleNamespace(
        f_globals={"__name__": module}, f_code=SimpleNamespace(co_name="_run")
    )
    assert not software._issued_driver(supplied)
    assert software.is_forbidden_frame(supplied)


@pytest.mark.parametrize("status", range(6))
def test_terminal_issued_exit_status_preserves_inherited_pytest_failure(status):
    assert software._exit_status(status) == status


def test_terminal_issued_selector_is_literal_and_never_groups_released_owner_cases():
    from types import SimpleNamespace

    cheap = SimpleNamespace(name="test_policy", originalname="test_policy")
    issued = [SimpleNamespace(name=name, originalname=name) for name in software.ISSUED_CASES]
    items = [cheap, *issued]
    yes, no = software._select_items(items, "policy")
    assert yes == [cheap] and no == issued
    for name, exact in zip(software.ISSUED_CASES, issued, strict=True):
        yes, no = software._select_items(items, name)
        assert yes == [exact] and len(no) == 4
    with pytest.raises(ValueError, match="exactly one released item"):
        software._select_items(items, "test_terminal_issued")


def test_terminal_issued_secondary_writer_cannot_replace_original_cause(monkeypatch, tmp_path):
    primary, cause, capture, writer = (
        ValueError(name) for name in ("source", "cause", "copy", "I/O")
    )
    primary.__cause__ = cause
    observed = []

    def refused(path, value):
        observed.append((path, value))
        raise writer

    before = len(_RAW_CAPTURE_FAILURES)
    with monkeypatch.context() as patch:
        patch.setattr(software.snapshot, "write_json", refused)
        with pytest.raises(ValueError) as caught:
            try:
                raise primary from cause
            except BaseException:
                _retain_secondary(tmp_path / "failed-capture.json", primary, capture)
                raise
    assert caught.value is primary and caught.value.__cause__ is cause
    assert len(observed) == 1 and observed[0][1]["complete"] is False
    assert _RAW_CAPTURE_FAILURES[before:][0][1:] == (primary, capture)
    assert _RAW_CAPTURE_FAILURES[before:][1][1:] == (primary, writer)


def _preflight_inputs(select, seconds):
    """Real frozen source pins, with no owner/fixture/release receipt supplied."""
    manifest_path = software.ROOT / "SNAPSHOT.json"
    manifest = software.snapshot.verify(
        software.ROOT, manifest_sha256=software.snapshot.digest(manifest_path)
    )
    return dict(
        cpu=7,
        threads=1,
        metadata_bytes=512 * 2**20,
        software_bytes=2**30,
        reserve_bytes=8 * 2**30,
        wall_seconds=seconds,
        software_release_requested=True,
        selection=select,
        terminal_issued_synthetic=True,
        snapshot_sha256=software.snapshot.digest(manifest_path),
        owned_files={name: manifest["files"][name]["sha256"] for name in software.OWNED},
        software_integration_envelope=software._integration_envelope(select, seconds),
    )


@pytest.mark.parametrize("seconds", (480, 1800))
def test_terminal_issued_real_inherited_child_preflight_reaches_worker_before_owner(
    tmp_path, seconds
):
    """Execute the unchanged inherited child/producer preflight, not a stub.

    Stop at the actual final worker's call event before collection or owner
    setup. JSON reads, manifest verification, producer checks, imports and
    definition evidence all use their real implementations and frozen bytes.
    """
    select = software.ISSUED_CASES[0] if seconds == 1800 else "metadata_preflight"
    inputs = _preflight_inputs(select, seconds)
    software._prepared(inputs, select, seconds)
    output = tmp_path / "real-child-preflight"
    output.mkdir()
    software.snapshot.write_json(output / "inputs.json", inputs)
    original = software.prior.reused.inherited.inherited.inherited
    worker = original.reuse.base.reuse.child
    inherited_profile, inherited_trace = sys.getprofile(), sys.gettrace()
    reached, owner_entries = [], []

    class BeforeCollection(BaseException):
        pass

    stop = BeforeCollection("real inherited preflight complete; collection stays held")

    def profile(frame, event, arg):
        if inherited_profile is not None:
            inherited_profile(frame, event, arg)
        if event != "call":
            return
        if (
            frame.f_globals.get("__name__", "").startswith("cells.processes.")
            and frame.f_code.co_name == "prepare"
        ):
            owner_entries.append(frame)
            raise AssertionError("No public owner setup in preflight")
        if frame.f_code is worker.__code__:
            reached.append(frame)
            raise stop

    try:
        sys.setprofile(profile)
        with pytest.raises(BeforeCollection) as caught:
            software._inherited_child(output, select)
        assert caught.value is stop
    finally:
        sys.setprofile(inherited_profile)
    assert sys.getprofile() is inherited_profile and sys.gettrace() is inherited_trace
    assert len(reached) == 1 and owner_entries == []
    frame = reached[0]
    assert frame.f_back.f_code is original.reuse.child.__code__
    assert frame.f_globals["ROOT"] is software.ROOT
    assert frame.f_globals["TEST"] == software.TEST
    assert frame.f_globals["SOFTWARE_RELEASE"] == software.SOFTWARE_RELEASE
    assert frame.f_globals["is_forbidden_frame"] is software.is_forbidden_frame
    assert frame.f_locals["output"] is output and frame.f_locals["select"] is select
    assert (output / "INIT-definition-imports.json").is_file()
    assert (output / "definition-imports.json").is_file()
    assert not (output / "reports").exists() and not (output / "pytest").exists()
    software.snapshot.write_json(
        output / "preflight-observation.json",
        dict(
            actual_unmodified_inherited_child_code=True,
            actual_frozen_source_checks_and_definition_evidence=True,
            seconds=seconds,
            stopped_at_original_worker_before_body=True,
            collection_or_owner_entries=0,
            actual_native_operator_RNG_or_scientific_credit=0,
        ),
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("single_named_pilot", None),
        ("single_named_pilot", "other"),
        ("native_bodies_operators_RNG_reference_and_science_held", None),
        ("native_bodies_operators_RNG_reference_and_science_held", 1),
    ),
)
def test_terminal_issued_real_inherited_child_refuses_malformed_long_preparation(
    tmp_path, field, value
):
    select = software.ISSUED_CASES[0]
    inputs = _preflight_inputs(select, 1800)
    software._prepared(inputs, select, 1800)
    inputs["software_integration_envelope"][field] = value
    with pytest.raises(ValueError, match="Exact terminal issued envelope"):
        software._prepared(inputs, select, 1800)
    output = tmp_path / "refused-real-preflight"
    output.mkdir()
    software.snapshot.write_json(output / "inputs.json", inputs)
    with pytest.raises(ValueError, match="Explicit blocked integration preparation required"):
        software._inherited_child(output, select)
    assert list(output.iterdir()) == [output / "inputs.json"]


def test_terminal_issued_real_inherited_child_refuses_the_failed_packet_vocabulary(tmp_path):
    select = software.ISSUED_CASES[0]
    inputs = _preflight_inputs(select, 1800)
    software._prepared(inputs, select, 1800)
    inputs["software_integration_envelope"] = dict(
        seconds=1800,
        single_case=select,
        detached=True,
        automatic_retry=False,
        source_native_operator_RNG_reference_and_science_held=True,
    )
    with pytest.raises(ValueError, match="Exact terminal issued envelope"):
        software._prepared(inputs, select, 1800)
    output = tmp_path / "refused-old-envelope"
    output.mkdir()
    software.snapshot.write_json(output / "inputs.json", inputs)
    with pytest.raises(ValueError, match="Explicit blocked integration preparation required"):
        software._inherited_child(output, select)
    assert list(output.iterdir()) == [output / "inputs.json"]


def test_terminal_issued_preparation_and_launch_share_the_exact_inherited_seam():
    tree = ast.parse(software.Path(software.__file__).read_bytes())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    prepare_calls = [
        call
        for call in ast.walk(functions["prepare"])
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_integration_envelope"
    ]
    child_calls = [
        call
        for call in ast.walk(functions["child"])
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_inherited_child"
    ]
    assert len(prepare_calls) == len(child_calls) == 1
    assert ast.unparse(prepare_calls[0]) == "_integration_envelope(select, seconds)"
    assert ast.unparse(child_calls[0]) == "_inherited_child(output, select)"


def test_terminal_issued_compact_report_configuration_is_live(pytestconfig):
    assert pytestconfig.option.tbstyle == "short"
    assert pytestconfig.option.showlocals is False
    assert pytestconfig.option.fulltrace is False


def test_terminal_issued_compact_report_namespace_seals_canonical_span_before_other_helpers():
    tree = ast.parse(stage.Path(__file__).read_bytes())
    factory = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_terminal_inputs"
    )
    namespace = next(
        node
        for node in factory.body
        if isinstance(node, ast.FunctionDef) and node.name == "terminal_namespace"
    )
    assert ast.unparse(namespace.body[0]) == "namespace_builder(context)"
    assert ast.unparse(namespace.body[1]) == "stage._bind_loop_span(context)"
    assert not any(
        isinstance(node, ast.Assign) and "loop_span" in ast.unparse(node)
        for node in ast.walk(namespace)
    )


@pytest.mark.parametrize("writer_failure", (False, True))
def test_terminal_issued_compact_report_retains_primary_without_rendering_owner_graph(
    tmp_path, monkeypatch, writer_failure
):
    from types import SimpleNamespace

    class DoNotRender:
        def __repr__(self):
            raise AssertionError("Owner/local graph representation is not failure evidence")

    primary, cause = ValueError("declared diagnostic", DoNotRender()), OSError("source cause")
    primary.__cause__ = cause
    state = SimpleNamespace(
        primary=None, primary_stage=None, evidence_attempts=(), evidence_errors=()
    )
    reporter = software.Reports(tmp_path, state, "metadata", [])
    item = SimpleNamespace(nodeid="declared compact reporter metadata")
    call = SimpleNamespace(when="call", excinfo=SimpleNamespace(value=primary))
    writer = OSError("declared report I/O failure")

    def refused(*args, **kwargs):
        raise writer

    with monkeypatch.context() as patch:
        if writer_failure:
            patch.setattr(software.snapshot, "write_json", refused)
        reporter.pytest_runtest_makereport(item, call)
    assert state.primary is primary and state.primary.__cause__ is cause
    assert state.primary_stage == "pytest_call" and len(state.evidence_attempts) == 1
    if writer_failure:
        assert state.evidence_errors == (("compact_case_failure", writer, primary),)
    else:
        import json

        paths = list((tmp_path / "compact-failures").glob("*.json"))
        assert len(paths) == 1
        row = json.loads(paths[0].read_text())
        assert row["raw_primary_retained_in_state"] is True
        assert row["full_failed_owner_serialization_claimed"] is False
        assert row["primary"][0]["args"][1]["opaque_type"].endswith("DoNotRender")
        assert state.evidence_errors == ()


def test_terminal_issued_reporter_refusal_probe():
    """Explicit expected-failure diagnostic, never an issued-owner case."""
    if os.environ.get(software.REPORTER_PROBE_RELEASE) != "1":
        pytest.skip("Separate exact compact reporter probe release required")

    class DoNotRender:
        def __repr__(self):
            raise AssertionError("Compact traceback must not render retained local graphs")

    retained_local_graph = DoNotRender()
    assert retained_local_graph is not None
    primary, cause = ValueError("declared compact reporter refusal"), OSError("declared cause")
    raise primary from cause
