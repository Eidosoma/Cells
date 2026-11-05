"""Source/closed-input controls; all actual INIT/draw/factory work is forbidden."""

import ast
import hashlib
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import BuiltinFunctionType, CodeType, FunctionType, MethodType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_init_dynamics_completion as stage
from cells.processes import betse_native_init_molecule_network as molecule
from cells.processes import betse_native_single_cell_poisson_observation as observation
from tests.unit import test_betse_native_init_dynamics_prelude as inherited
from tests.unit import test_betse_native_init_retained_world as retained
from validation.betse import betse_native_init_dynamics_completion_software as runner

synthetic_init_inputs = retained.synthetic_init_inputs


@contextmanager
def monitored_public_model_guard(tmp_path):
    """Keep the exact native blockade independent of inherited event auditing.

    Only a recognised software-only call guard with NO user predecessor may
    move to sys.monitoring. Production observers/audits remain unchanged.
    This avoids taking a whole-state epoch around every call to the test's
    read-only blacklist. The historical cost remains a separate observation;
    this change has not yet established that cost's complete cause.
    """
    before = sys.getprofile(), sys.gettrace()
    choices = (
        inherited._blocked_generator.__code__,
        retained.guards._blockade.__wrapped__.__code__,
        retained.guards.software.child.__code__,
    )
    permitted = tuple(
        code
        for owner in choices
        for code in owner.co_consts
        if type(code) is CodeType and code.co_name in ("profile", "trace")
    )
    guards = tuple(value for value in before if value is not None)
    if not guards or any(
        type(fn) is not FunctionType or not any(fn.__code__ is code for code in permitted)
        for fn in guards
    ):
        raise ValueError("Only the exact frozen software call blockade can be moved")

    def callable_state(fn):
        namespace = fn.__globals__
        declared_builtins = namespace.get("__builtins__")
        resolved_builtins = (
            vars(declared_builtins) if type(declared_builtins) is ModuleType else declared_builtins
        )
        if resolved_builtins is not fn.__builtins__:
            raise ValueError("Actual cached software guard builtins required")
        values = [
            fn,
            fn.__code__,
            namespace,
            fn.__builtins__,
            fn.__defaults__,
            fn.__kwdefaults__,
            fn.__closure__,
            declared_builtins,
        ]
        values.extend(cell.cell_contents for cell in fn.__closure__ or ())
        for key in fn.__code__.co_names:
            if key in namespace:
                values.extend((key, namespace[key]))
            elif key in fn.__builtins__:
                values.extend((key, fn.__builtins__[key]))
        return tuple(values)

    predicate_files = []

    def guard_state(fn, *, verify_path=False):
        if any(
            fn.__code__ is value
            for value in choices[2].co_consts
            if type(value) is CodeType and value.co_name == "profile"
        ):
            # Reused child globals also have software(), a FUNCTION. That is
            # not this exact guard's reached predicate or an authority holder.
            source = None
            predicate = fn.__globals__.get("is_forbidden_frame")
        elif any(
            fn.__code__ is value
            for value in choices[0].co_consts
            if type(value) is CodeType and value.co_name == "trace"
        ):
            source = fn.__globals__.get("runner")
            predicate = getattr(source, "is_forbidden_frame", None)
        elif any(
            fn.__code__ is value
            for value in choices[1].co_consts
            if type(value) is CodeType and value.co_name == "profile"
        ):
            source = fn.__globals__.get("software")
            predicate = getattr(source, "is_forbidden_frame", None)
        else:
            raise ValueError("Exact known software guard layout required")
        module = (
            None if type(predicate) is not FunctionType else sys.modules.get(predicate.__module__)
        )
        canonical = None if module is None else module.__name__
        spec = None
        if canonical == "__main__":
            spec = vars(module).get("__spec__")
            canonical = spec.name if type(spec) is ModuleSpec else None
        filename = None if module is None else vars(module).get("__file__")
        if (
            type(module) is not ModuleType
            or predicate.__globals__ is not vars(module)
            or vars(module).get("is_forbidden_frame") is not predicate
            or type(canonical) is not str
            or not canonical.startswith("validation.betse.betse_native_")
            or type(filename) is not str
        ):
            raise ValueError("Actual frozen native blacklist predicate required")
        if verify_path:
            if Path(filename).resolve() != runner.ROOT / (canonical.replace(".", "/") + ".py"):
                raise ValueError("Actual frozen native blacklist predicate required")
            predicate_files.append(filename)
        return (
            source,
            module,
            module.__name__,
            spec,
            canonical,
            filename,
            runner.ROOT,
            *callable_state(fn),
            *callable_state(predicate),
        )

    pending, bindings = list(guards), []
    while pending:
        fn = pending.pop()
        if any(fn is item[0] for item in bindings):
            continue
        if type(fn) is not FunctionType or not any(fn.__code__ is code for code in permitted):
            raise ValueError("An external profile/trace observer must retain its full epoch audit")
        bindings.append((fn, guard_state(fn, verify_path=True)))
        closure = dict(
            zip(
                fn.__code__.co_freevars,
                (cell.cell_contents for cell in fn.__closure__ or ()),
                strict=True,
            )
        )
        predecessor = closure.get("prior", closure.get("before"))
        if predecessor is None:
            continue
        if type(predecessor) is tuple:
            if len(predecessor) != 2:
                raise ValueError("Exact inherited hook pair required")
            pending.extend(item for item in predecessor if item is not None)
        else:
            pending.append(predecessor)
    # These are exact path-chain identities, not a source-proof cache. Resolve
    # canonical module paths at both boundaries; authenticate every filesystem
    # component and all live guard bindings at each PY_START. Fresh production
    # source-byte/AST checks are neither replaced nor memoized here.
    lstat = os.lstat
    paths = tuple(
        dict.fromkeys(
            str(part)
            for filename in predicate_files
            for part in (*reversed(Path(filename).parents), Path(filename))
        )
    )
    path_bindings = tuple(
        (path, (value.st_dev, value.st_ino, value.st_mode))
        for path in paths
        for value in (lstat(path),)
    )

    def check_paths():
        if os.lstat is not lstat:
            raise AssertionError("Original filesystem identity lookup required")
        for path, original in path_bindings:
            value = lstat(path)
            if (value.st_dev, value.st_ino, value.st_mode) != original:
                raise AssertionError("Frozen software guard path identity changed")

    monitor = sys.monitoring
    initial = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
    free = [i for i, (name, _) in enumerate(initial) if name is None]
    if not free:
        raise ValueError("A free independent software monitoring slot is required")
    tool, name = free[-1], "Cells Key native-blocked public model"
    attempts, errors = [], []
    state = NS(starts=0, calls=0, reserved=False)
    numpy_owner = np.random.mtrand._rand
    standard = sys.modules.get("random")
    std_owner = None if standard is None else vars(standard).get("_inst")

    def start(code, offset):
        state.starts += 1
        frame = sys._getframe(1)
        if frame.f_code is not code:
            raise AssertionError("Actual monitored source-entry frame required")
        check_paths()
        for fn, original in bindings:
            current = guard_state(fn)
            if len(current) != len(original) or any(
                a is not b for a, b in zip(current, original, strict=True)
            ):
                raise AssertionError("Frozen software guard code/closure/global binding changed")
        for guard in guards:
            guard(frame, "call", None)

    def called(code, offset, target, arg0):
        state.calls += 1
        if type(target) in (BuiltinFunctionType, MethodType):
            owner = target.__self__
            if (
                owner is numpy_owner or (std_owner is not None and owner is std_owner)
            ) and target.__name__ not in (
                "get_state",
                "getstate",
            ):
                attempts.append((target.__name__, id(owner)))
                raise AssertionError("Actual global NumPy/stdlib RNG invocation forbidden")

    primary = None
    try:
        monitor.use_tool_id(tool, name)
        state.reserved = True
        monitor.register_callback(tool, monitor.events.PY_START, start)
        monitor.register_callback(tool, monitor.events.CALL, called)
        monitor.set_events(tool, monitor.events.PY_START | monitor.events.CALL)
        sys.settrace(None)
        sys.setprofile(None)
        yield state
    except BaseException as error:
        primary = error
        raise
    finally:
        for setter, value in ((sys.settrace, before[1]), (sys.setprofile, before[0])):
            try:
                setter(value)
            except BaseException as error:
                errors.append(("restore_hook", error))
        if state.reserved:
            for operation, args in (
                (monitor.set_events, (tool, 0)),
                (monitor.register_callback, (tool, monitor.events.PY_START, None)),
                (monitor.register_callback, (tool, monitor.events.CALL, None)),
                (monitor.free_tool_id, (tool,)),
            ):
                try:
                    operation(*args)
                except BaseException as error:
                    errors.append((operation.__name__, error))
        try:
            check_paths()
            for fn, original in bindings:
                current = guard_state(fn, verify_path=True)
                if len(current) != len(original) or any(
                    a is not b for a, b in zip(current, original, strict=True)
                ):
                    raise AssertionError("Frozen software guard final binding changed")
        except BaseException as error:
            errors.append(("final_guard_binding", error))
        final = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
        intact = sys.getprofile() is before[0] and sys.gettrace() is before[1]
        receipt = dict(
            starts=state.starts,
            calls=state.calls,
            attempted_rng=attempts,
            all_monitor_slots_restored=final == initial,
            original_hooks_restored=intact,
            cleanup_errors=[(where, type(error).__name__, str(error)) for where, error in errors],
            conditional_public_issuance_not_native_or_biological_authority=True,
            production_observer_or_ownership_checks_changed=False,
        )
        try:
            runner.snapshot.write_json(tmp_path / "independent-public-model-blockade.json", receipt)
        except BaseException as error:
            errors.append(("receipt", error))
            if primary is not None:
                try:
                    primary.software_monitor_capture_errors = tuple(errors)
                except BaseException:
                    pass
        if (errors or final != initial or not intact or attempts) and primary is None:
            raise AssertionError("Independent software blockade incomplete")


@pytest.fixture
def issued_synthetic_completion(
    synthetic_init_inputs, monkeypatch, tmp_path, native_molecules=False
):
    """All three actual public issuers; synthetic upstream/provider/bodies only.

    No live owner is allocated or inserted by this fixture. Actual production
    constructors issue InitOwner -> PreludeOwner -> DynamicsOwner. Acquisition,
    typed parameter provider, source bodies, tissue provider and stream labels
    are explicit stand-ins; they never establish original native admission.
    """
    h = synthetic_init_inputs
    if type(native_molecules) is not bool:
        raise ValueError("Exact pre-birth synthetic route boolean required")
    initial, prelude = retained.stage, stage.previous
    # The unissued synthetic predecessor supplies the REAL read-only exact-byte
    # checker. The genuine retained routing/ancestor validators are not stubbed.
    initial.previous._ready = lambda: retained.guards.stage
    interface = initial._dynamics_binding(Path(prelude.__file__).read_bytes())[0]
    monkeypatch.setattr(initial, "DYNAMICS_INTERFACE_SHA256", interface)
    h.p.__dict__.update(
        Ca_dyn=False,
        ions_dict={"Na": 1, "K": 1, "Ca": 0},
        molecules_enabled=native_molecules,
        grn_enabled=False,
        deform_osmo=False,
        fluid_flow=False,
        deformation=False,
        solver_type="declared-metadata-FULL",
        channel_noise_level=0.0,
    )
    h.cells.cell_i = np.array([0, 1])
    h.namespace["SolverType"] = NS(FULL=h.p.solver_type)
    h.model_stream = "metadata-before"
    h.channel_buffer = np.array([0.25, 0.75])
    if native_molecules:
        _synthetic_enabled_network(h, monkeypatch)

    def profiles(self, phase):
        self.profile_epoch = 1

    def events(self, phase):
        self.event_epoch = 1

    def clear_storage(self, cells, p):
        self.vm_time = []
        if p.molecules_enabled:
            self.molecules.core.clear_cache()

    # Constructor classes are still UNISSUED/acquired later. No live instance
    # or issued class is changed after any source birth.
    factory = h.factories["TissueHandler"]
    factory.init_profiles, factory.init_events = profiles, events
    h.factories["Simulator"].mdl = 2
    h.factories["Simulator"].clear_storage = clear_storage
    provider = ModuleType("declared_synthetic_tissue_provider")
    provider.record = object()

    def bind(claim, *, original_owner):
        context = stage._active(claim)
        assert context.request.prelude_owner is original_owner
        provider.context = NS(claim=claim, original_owner=original_owner, completion=context)
        provider.session = object()
        return provider.session

    def active(session, *, completion_claim):
        assert session is provider.session and completion_claim is provider.context.claim
        return session

    def context(session, claim=None):
        assert session is provider.session
        assert claim is None or claim is provider.context.claim
        return provider.context

    def registry(value, *, closed=False):
        assert value is provider.context
        assert stage._CLAIMS.get(value.claim) is value.completion
        if closed:
            assert not value.completion.active and value.completion.trial.source_completed

    def wrapper(session, *, completion_claim, original, frame):
        active(session, completion_claim=completion_claim)
        c = provider.context.completion
        assert original is c.init_parent and frame.f_back is c.body_frame
        assert frame.f_locals["actual"] is c.handler

    def dispatch(
        session, *, completion_claim, original, label, delegate, actual, args, kwargs, frame
    ):
        active(session, completion_claim=completion_claim)
        c = provider.context.completion
        assert (
            original is c.init_parent and actual is c.handler and args == (c.phase,) and not kwargs
        )
        assert delegate is getattr(factory, label.split(".")[-1])
        return delegate(actual, *args)

    provider.bind_completion, provider.validate_active = bind, active
    provider._context, provider._registry = context, registry
    provider.validate_closed = lambda session, **kw: provider.record
    provider.source_members = lambda session: (profiles, events)
    provider.state_roots = lambda session: ()
    provider.wrapper_guard, provider.dispatch = wrapper, dispatch
    provider.finish = lambda session, **kw: provider.record
    provider.observe = lambda *args, **kw: None
    provider.validate_rng_call = lambda *args, **kw: pytest.fail("No actual RNG participation")
    provider._source_nodes = lambda: dict(
        metadata=ast.parse("def f(self):\n self.profile_epoch = 1\n self.event_epoch = 1\n").body[0]
    )

    def namespace(context):
        def random(size):
            h.model_stream = "metadata-after"
            return h.channel_buffer

        class Standard:
            def shuffle(self, value):
                pytest.fail("No shuffle in this conditional input")

            def getstate(self):
                return "fixed-stdlib-label"

        def source_body(self, phase):
            phase.dyna.init_profiles(phase)
            self.channel_noise_factor = channel()
            self.rho_pump = 1
            phase.dyna.init_events(phase)

        def actual_molecules(p):
            return molecule.construct(
                context.molecule_session,
                p,
                completion_claim=context.claim,
                source_frame=sys._getframe(1),
            )

        def channel():
            return stage.rng_call(
                context.claim,
                participant=None,
                library="numpy",
                operation="random",
                delegate=random,
                args=(context.sim.mdl,),
                kwargs={},
                source_frame=sys._getframe(1),
            )

        scope = dict(__name__=__name__, __builtins__=__builtins__)
        if native_molecules:
            # Explicit synthetic numerical body, never native correspondence.
            # Preserve the actual participant's literal factory call-site
            # guard; none of its session/registry/parent checks is replaced.
            scope.update(channel=channel, MasterOfMolecules=actual_molecules)
            node = ast.parse(
                "def init_dynamics(self, phase):\n"
                " phase.dyna.init_profiles(phase)\n"
                " self.channel_noise_factor = channel()\n"
                " self.rho_pump = 1\n"
                " self.molecules = MasterOfMolecules(phase.p)\n"
                " self.molecules.read_mol_config(phase)\n"
                " phase.dyna.init_events(phase)\n"
            ).body[0]
            ast.increment_lineno(node, 807)
            for statement, line in zip(node.body, (809, 853, 855, 871, 872, 905), strict=True):
                ast.increment_lineno(statement, line - statement.lineno)
            node.end_lineno = 905
            compiled = compile(ast.Module(body=[node], type_ignores=[]), __file__, "exec")
            code = next(value for value in compiled.co_consts if type(value) is CodeType)
            source_body = FunctionType(code, scope)
        else:
            source_body = FunctionType(source_body.__code__, scope, closure=source_body.__closure__)
        context.methods = {"init_dynamics": source_body}
        context.namespace, context.expected_body = scope, source_body.__code__
        context.source_functions, context.helper_functions = (source_body,), ()
        context.numpy, context.np_rng, context.np_random = np, object(), random
        context.std_rng = Standard()
        context.shuffle, context.std_getstate = context.std_rng.shuffle, context.std_rng.getstate
        context.allowed_codes = frozenset((source_body.__code__,))

    monkeypatch.setattr(stage, "_ready", lambda: provider)
    monkeypatch.setattr(
        stage, "source_plan", lambda: dict(law=stage.LAW_ID, synthetic_not_native=True)
    )
    monkeypatch.setattr(stage, "_namespace", namespace)
    monkeypatch.setattr(
        stage, "_streams", lambda c: (NS(identity=h.model_stream), NS(identity="fixed-standard"))
    )
    monkeypatch.setattr(prelude, "_completion_api", lambda: stage)
    monkeypatch.setenv(stage.RELEASE, "1")
    started = time.monotonic()
    with monitored_public_model_guard(tmp_path):
        h.request = initial.from_seed(h.upstream_owner, law_id=initial.LAW_ID)
        h.owner = initial.prepare(h.request, enabled=True)
        h.context = initial._authority(h.owner)
        # Reuse the existing public-prelude synthetic acquisition seam before
        # that issuer, without requesting an already-issued fixture twice.
        retained.issued_synthetic_dynamics.__wrapped__(h, monkeypatch)
        h.prelude_owner = prelude.prepare(h.dynamics_request, enabled=True)
        h.prelude_context = prelude._authority(h.prelude_owner)
        h.completion_request = (
            stage.from_prelude_native_molecules(h.prelude_owner, law_id=stage.MOLECULE_LAW_ID)
            if native_molecules
            else stage.from_prelude(h.prelude_owner, law_id=stage.LAW_ID)
        )
        h.completion_owner = stage.prepare(h.completion_request, enabled=True)
        h.completion_context = stage._authority(h.completion_owner)
        h.completion_elapsed = time.monotonic() - started
        yield h


def _synthetic_enabled_network(h, monkeypatch):
    """Pre-birth toy bodies; actual MoleculeSession/ancestor/runtime APIs only.

    No original arithmetic/factory runs and no synthetic provider can issue a
    molecular session. The actual bind/observe/finish/validation functions and
    process registries remain installed. The required real retained hooks are
    NOT supplied here: a missing hook remains an honest prerequisite failure.
    """
    if hasattr(h, "owner") or hasattr(h, "context") or hasattr(h, "prelude_owner"):
        raise ValueError("Enabled configuration must precede every public INIT issuer")
    config = dict(
        {"implement network": True, "network plotting": {}},
        biomolecules=[{"name": "X", "initial asymmetry": None}],
        reactions=None,
        transporters=None,
        channels=None,
        modulators=None,
    )
    h.p.network_config = config
    h.p._conf = {"general network": config}
    h.network_config = config
    scope = dict(__name__=__name__, __builtins__=__builtins__, np=np)
    bodies = """
class MasterOfMolecules:
    def __init__(self, p):
        self.parameter_owner = p
        self.transporters = p.network_config["transporters"]
        self.channels = p.network_config["channels"]
        self.modulators = p.network_config["modulators"]
    def read_mol_config(self, phase):
        self.core = MasterOfNetworks(
            phase.sim, phase.cells, phase.p.network_config["biomolecules"], phase.p)
class MasterOfNetworks:
    def __init__(self, sim, cells, config_substances, p):
        self.molecules = {"X": Molecule()}
        self.transporters, self.channels, self.modulators = {}, {}, {}
        self.reactions, self.reactions_env = {}, {}
        self.mit_enabled = False
        self.extra_rho_cells = np.array([0.0, 0.0])
        self.extra_rho_env = np.array([0.0, 0.0])
        self.extra_J_mem = np.array([0.0, 0.0])
        self.extra_Jenv_x = np.array([0.0, 0.0])
        self.extra_Jenv_y = np.array([0.0, 0.0])
    def clear_cache(self):
        for obj in self.molecules.values():
            obj.c_mems_time, obj.c_cells_time, obj.c_env_time = [], [], []
        self.chi_time = []
    def clear_run_loop(self, sim):
        self.extra_rho_cells = np.array([0.0, 0.0])
    def run_loop(self, phase, t):
        for obj in self.molecules.values():
            obj.update_intra(phase.sim, phase.cells, phase.p)
            obj.transport(phase.sim, phase.cells, phase.p)
        self.energy_charge(phase.sim)
        phase.sim.extra_rho_cells = self.extra_rho_cells
    def energy_charge(self, sim):
        self.chi = np.array([0.0, 0.0])
    def write_data(self, sim, cells, p):
        for obj in self.molecules.values():
            obj.c_mems_time.append(obj.cc_at_mem)
            obj.c_cells_time.append(obj.c_cells)
            obj.c_env_time.append(obj.c_env)
        self.chi_time.append(self.chi)
    def report(self, sim, p):
        return None
class Molecule:
    def __init__(self):
        self.c_cells = np.array([1.0, 2.0])
        self.c_env = np.array([3.0, 4.0])
        self.cc_at_mem = self.c_cells
        self.active_pumping = self.ion_channel_gating = False
        self.change_bounds = self.cell_clamp = False
        self.gad_eval_string = "0.0"
    def update_intra(self, sim, cells, p):
        self.cc_at_mem = self.c_cells
    def transport(self, sim, cells, p):
        self.c_cells = self.c_cells + 1.0
class Reaction:
    pass
class Transporter:
    pass
class DynamicValue:
    pass
class DynamicValueDict:
    pass
def set_net_opts(self, net_plot_opts, p):
    return None
"""
    exec(compile(bodies, __file__, "exec"), scope)
    roles = (
        "MasterOfMolecules",
        "MasterOfNetworks",
        "Molecule",
        "Reaction",
        "Transporter",
        "DynamicValue",
        "DynamicValueDict",
    )
    classes = {role: scope[role] for role in roles}
    owner = sys.modules[__name__]
    for role, cls in classes.items():
        monkeypatch.setattr(owner, role, cls, raising=False)

    def acquire(api, completion):
        functions = {
            (role, name): function
            for role, cls in classes.items()
            for name, function in vars(cls).items()
            if type(function) is FunctionType
        }
        functions[("Simulator", "get_ion")] = completion.parent.methods["get_ion"]
        functions[(None, "set_net_opts")] = scope["set_net_opts"]
        exports = tuple((owner, role, cls) for role, cls in classes.items())
        return classes, functions, exports, ()

    monkeypatch.setattr(stage, "_molecule_api", lambda: molecule)
    monkeypatch.setattr(molecule, "_ready", lambda: stage)
    monkeypatch.setattr(molecule, "_actual_functions", acquire)
    h.seams = (
        *h.seams,
        "pre-birth enabled toy configuration and acquired toy numerical bodies; "
        "actual molecular session APIs/registries/material hooks unchanged",
    )


@pytest.fixture
def issued_synthetic_enabled_completion(synthetic_init_inputs, monkeypatch, tmp_path):
    yield from issued_synthetic_completion.__wrapped__(
        synthetic_init_inputs, monkeypatch, tmp_path, native_molecules=True
    )


def test_enabled_prebirth_acquisition_keeps_actual_session_api_and_unchanged_registries(
    synthetic_init_inputs, monkeypatch
):
    h = synthetic_init_inputs
    functions = tuple(
        getattr(molecule, name)
        for name in ("bind_completion", "observe", "finish", "validate_active", "validate_closed")
    )
    registries = molecule._SESSIONS, molecule._CLAIMED, molecule._RUNTIME
    sizes = tuple(len(registry) for registry in registries)
    h.p.molecules_enabled = True
    _synthetic_enabled_network(h, monkeypatch)
    assert (
        tuple(
            getattr(molecule, name)
            for name in (
                "bind_completion",
                "observe",
                "finish",
                "validate_active",
                "validate_closed",
            )
        )
        == functions
    )
    assert tuple(len(registry) for registry in registries) == sizes
    assert h.p.molecules_enabled is True
    assert h.p.network_config is h.network_config is h.p._conf["general network"]
    assert h.network_config["implement network"] is True
    # Source-acquisition observation only; neither these classes nor the
    # tuple below is supplied as a completed network or positive parent.
    classes, members, exports, entries = molecule._actual_functions(
        stage, NS(parent=NS(methods={"get_ion": h.factories["Simulator"].get_ion}))
    )
    assert (
        classes["MasterOfMolecules"]
        is members[("MasterOfMolecules", "read_mol_config")].__globals__["MasterOfMolecules"]
    )
    assert (
        classes["MasterOfNetworks"]
        is members[("MasterOfMolecules", "read_mol_config")].__globals__["MasterOfNetworks"]
    )
    assert not entries and exports
    assert tuple(len(registry) for registry in registries) == sizes


@pytest.mark.parametrize("issued_field", ("owner", "context", "prelude_owner"))
def test_enabled_prebirth_acquisition_refuses_a_late_retrofit(
    synthetic_init_inputs, monkeypatch, issued_field
):
    h = synthetic_init_inputs
    setattr(h, issued_field, object())
    before = dict(vars(h.p))
    with pytest.raises(ValueError, match="precede every public INIT issuer"):
        _synthetic_enabled_network(h, monkeypatch)
    assert tuple(vars(h.p)) == tuple(before)
    assert all(vars(h.p)[name] is value for name, value in before.items())


def test_enabled_prebirth_builder_selects_true_before_issuer_and_compiles_actual_callsite(
    synthetic_init_inputs, monkeypatch, tmp_path
):
    h, entered = synthetic_init_inputs, []
    initial = retained.stage
    primary = RuntimeError("deliberate pre-issuer software stop")

    def stop(owner, *, law_id):
        assert owner is h.upstream_owner and law_id == initial.LAW_ID
        assert h.p.molecules_enabled is True and h.p.grn_enabled is False
        assert h.p.network_config is h.p._conf["general network"]
        assert stage._molecule_api() is molecule
        assert not hasattr(h, "owner") and not hasattr(h, "completion_owner")
        entered.append(owner)
        raise primary

    monkeypatch.setattr(initial, "from_seed", stop)
    generator = issued_synthetic_completion.__wrapped__(
        h, monkeypatch, tmp_path, native_molecules=True
    )
    with pytest.raises(RuntimeError) as caught:
        next(generator)
    assert caught.value is primary and entered == [h.upstream_owner]
    context = NS(sim=NS(mdl=2), claim=object())
    stage._namespace(context)
    assert 871 in {line for _, _, line in context.expected_body.co_lines()}
    assert context.namespace["MasterOfMolecules"].__closure__
    assert not hasattr(h, "completion_owner")


def test_public_issued_completion_chain_uses_actual_issuers_not_allocated_handles(
    issued_synthetic_completion, tmp_path
):
    h = issued_synthetic_completion
    context = h.completion_context
    assert type(h.owner) is retained.stage.InitOwner
    assert type(h.prelude_owner) is stage.previous.PreludeOwner
    assert type(h.completion_owner) is stage.DynamicsOwner
    assert context.phase is h.context.phase and context.sim is h.context.phase.sim
    assert context.p is h.p and context.cells is h.cells
    assert context.trial.source_completed and context.channel_random_attempts == 1
    assert len(context.rng_calls) == 1 and context.rng_calls[0].returned
    assert h.completion_owner.trial is context.trial
    runner.snapshot.write_json(
        tmp_path / "public-issued-completion.json",
        dict(
            public_issuers=("from_seed/prepare", "from_init/prepare", "from_prelude/prepare"),
            elapsed=h.completion_elapsed,
            native_or_biological_parent=False,
            manual_owner_allocation_or_registry_insertion=False,
            declared_seams=(*h.seams, "synthetic tissue provider/bodies and stream labels"),
        ),
    )


def test_monitor_preserves_native_blacklist_before_a_synthetic_body_can_start(tmp_path):
    original = sys.gettrace()
    assert type(original) is FunctionType
    isolated = []

    def cell(value):
        return (lambda: value).__closure__[0]

    closure = tuple(
        cell(isolated) if name == "attempts" else value
        for name, value in zip(original.__code__.co_freevars, original.__closure__, strict=True)
    )
    guard = FunctionType(original.__code__, original.__globals__, closure=closure)
    entered = []

    def forbidden_body():
        entered.append(True)

    labelled = FunctionType(
        forbidden_body.__code__.replace(
            co_filename=str(stage.NATIVE / "betse/science/guard_probe.py")
        ),
        forbidden_body.__globals__,
        closure=forbidden_body.__closure__,
    )
    try:
        sys.settrace(guard)
        with monitored_public_model_guard(tmp_path):
            with pytest.raises(AssertionError, match="entry forbidden"):
                labelled()
        assert isolated and not entered
    finally:
        sys.settrace(original)


def test_monitor_refuses_a_foreign_observer_without_removing_it(tmp_path):
    original = sys.gettrace()

    def foreign(frame, event, arg):
        return None

    try:
        sys.settrace(foreign)
        with pytest.raises(ValueError, match="exact frozen"):
            with monitored_public_model_guard(tmp_path):
                pytest.fail("A foreign observer cannot lose its full epoch audit")
        assert sys.gettrace() is foreign
    finally:
        sys.settrace(original)


@pytest.mark.parametrize("drift", [None, "spec", "path"])
def test_monitor_authenticates_actual_dash_m_runner_instead_of_arbitrary_main(
    tmp_path, monkeypatch, drift
):
    main = sys.modules["__main__"]
    assert type(main.__spec__) is ModuleSpec
    original = sys.getprofile()
    code = next(
        value
        for value in retained.guards.software.child.__code__.co_consts
        if type(value) is CodeType and value.co_name == "profile"
    )
    values = {"attempts": [], "prior": (None, None)}

    def cell(value):
        return (lambda: value).__closure__[0]

    guard = FunctionType(
        code, vars(main), closure=tuple(cell(values[name]) for name in code.co_freevars)
    )
    try:
        sys.setprofile(guard)
        with monkeypatch.context() as patch:
            if drift == "spec":
                patch.setattr(main, "__spec__", ModuleSpec("unrelated_module", loader=None))
            elif drift == "path":
                patch.setattr(main, "__file__", str(tmp_path / "foreign_main.py"))
            if drift is None:
                with monitored_public_model_guard(tmp_path) as state:
                    assert sys.getprofile() is None and state.reserved
                assert sys.getprofile() is guard and not values["attempts"]
            else:
                with pytest.raises(ValueError, match="frozen native blacklist"):
                    with monitored_public_model_guard(tmp_path):
                        pytest.fail("An arbitrary __main__ module cannot be accepted")
                assert sys.getprofile() is guard
    finally:
        sys.setprofile(original)


def _isolated_software_trace():
    original = sys.gettrace()
    assert type(original) is FunctionType
    attempts = []

    def cell(value):
        return (lambda: value).__closure__[0]

    closure = {
        name: cell(
            attempts
            if name == "attempts"
            else (None, None)
            if name == "before"
            else value.cell_contents
        )
        for name, value in zip(original.__code__.co_freevars, original.__closure__, strict=True)
    }
    guard = FunctionType(
        original.__code__,
        dict(original.__globals__),
        closure=tuple(closure[name] for name in original.__code__.co_freevars),
    )
    return original, guard, closure, attempts


def test_monitor_hoists_canonical_resolution_but_still_observes_every_entry(tmp_path, monkeypatch):
    resolutions, original = [], Path.resolve

    def resolving(path, *args, **kwargs):
        resolutions.append(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolving)

    def metadata_leaf():
        return None

    with monitored_public_model_guard(tmp_path) as state:
        before = len(resolutions)
        starts = state.starts
        for _ in range(200):
            metadata_leaf()
        assert state.starts >= starts + 200
        assert len(resolutions) == before
    assert len(resolutions) > before  # Canonical path proof is repeated at exit.


@pytest.mark.parametrize(
    "drift", ("code", "closure", "previous", "predicate", "file", "builtins", "filesystem")
)
def test_monitor_live_drift_refuses_before_probe_with_original_hooks_restored(tmp_path, drift):
    original, guard, closure, attempts = _isolated_software_trace()
    entered = []
    namespace, code = guard.__globals__, guard.__code__
    prior = closure["before"].cell_contents
    old_attempts = closure["attempts"].cell_contents
    source = namespace["runner"]
    predicate = source.is_forbidden_frame
    module = sys.modules[predicate.__module__]
    filename, declared, lstat = module.__file__, namespace["__builtins__"], os.lstat
    foreign_filename = str(tmp_path / "foreign.py")
    copied_predicate = FunctionType(predicate.__code__, predicate.__globals__)

    def probe():
        entered.append(True)

    def foreign(*args, **kwargs):
        pytest.fail("A changed metadata dependency must never execute")

    try:
        sys.settrace(guard)
        with pytest.raises((AssertionError, ValueError)) as caught:
            with monitored_public_model_guard(tmp_path):
                if drift == "code":
                    guard.__code__ = code.replace(co_name="changed_guard")
                elif drift == "closure":
                    closure["attempts"].cell_contents = []
                elif drift == "previous":
                    closure["before"].cell_contents = (foreign, None)
                elif drift == "predicate":
                    namespace["runner"] = NS(is_forbidden_frame=copied_predicate)
                elif drift == "file":
                    module.__file__ = foreign_filename
                elif drift == "builtins":
                    namespace["__builtins__"] = dict(declared)
                else:
                    os.lstat = foreign
                try:
                    probe()
                finally:
                    # C-level assignments restore the checked objects before
                    # any Python cleanup callback can attempt entry.
                    guard.__code__ = code
                    closure["attempts"].cell_contents = old_attempts
                    closure["before"].cell_contents = prior
                    namespace["runner"] = source
                    namespace["__builtins__"] = declared
                    module.__file__ = filename
                    os.lstat = lstat
        expected = {
            "code": "known software guard layout",
            "closure": "guard code/closure/global binding changed",
            "previous": "guard code/closure/global binding changed",
            "predicate": "frozen native blacklist predicate",
            "file": "guard code/closure/global binding changed",
            "builtins": "cached software guard builtins",
            "filesystem": "filesystem identity lookup",
        }
        assert expected[drift] in str(caught.value)
        assert sys.gettrace() is guard and not entered and not attempts
    finally:
        sys.settrace(original)


def test_monitor_cost_refactor_preserves_falsey_primary_and_cause(tmp_path):
    class FalseyError(ValueError):
        def __bool__(self):
            return False

    primary, cause = FalseyError("primary metadata error"), KeyError("original cause")
    primary.__cause__ = cause
    before = sys.getprofile(), sys.gettrace()
    with pytest.raises(FalseyError) as caught:
        with monitored_public_model_guard(tmp_path):
            raise primary
    assert caught.value is primary and primary.__cause__ is cause
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]


def test_monitor_checks_each_filesystem_component_even_when_namespace_is_unchanged(
    tmp_path, monkeypatch
):
    original, entered = os.lstat, []
    model = {"changed": False, "checked": 0}

    def observed_lstat(path):
        value = original(path)
        if model["changed"]:
            model["checked"] += 1
            return NS(st_dev=value.st_dev, st_ino=value.st_ino + 1, st_mode=value.st_mode)
        return value

    def probe():
        entered.append(True)

    # Read-only syscall-result model; no frozen file/path or actual source
    # authority is changed, and every original guard remains installed.
    monkeypatch.setattr(os, "lstat", observed_lstat)
    with pytest.raises(AssertionError, match="path identity changed"):
        with monitored_public_model_guard(tmp_path):
            model["changed"] = True
            try:
                probe()
            finally:
                model["changed"] = False
    assert model["checked"] and not entered


def test_source_metadata_templates_reuse_syntax_but_freshly_read_original_api(monkeypatch):
    initial, api = retained.stage, retained.guards.stage
    initial._source_templates.cache_clear()
    initial._dynamics_template.cache_clear()
    source = Path(stage.previous.__file__).read_bytes()
    reads, original = [], Path.read_bytes

    def reading(path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", reading)
    binder = retained.clone(initial._dynamics_binding, previous=NS(_ready=lambda: api))
    first = binder(source)
    second = binder(bytes(bytearray(source)))
    assert second is first
    assert sum(path == Path(api.__file__) for path in reads) == 2
    assert initial._dynamics_template.cache_info().misses == 1
    assert initial._dynamics_template.cache_info().hits == 1
    assert initial._source_templates.cache_info().misses == 1
    assert initial._source_templates.cache_info().hits == 1
    scope = dict(
        vars(api),
        HELPER_BACK_REFERENCE_SLOTS=initial.DYNAMICS_BACK_REFERENCE_SLOTS,
        HELPER_BINDING_KIND=initial.DYNAMICS_BINDING_KIND,
    )
    assert first == FunctionType(api._helper_binding.__code__, scope)(source)


@pytest.mark.parametrize("drift", ("equal_bytes_subclass", "source_bound"))
def test_source_metadata_input_checks_precede_warm_cache_lookup(drift):
    initial, api = retained.stage, retained.guards.stage
    raw = Path(stage.previous.__file__).read_bytes()
    binder = retained.clone(initial._dynamics_binding, previous=NS(_ready=lambda: api))
    binder(raw)
    before = initial._dynamics_template.cache_info()

    class ForeignBytes(bytes):
        def __hash__(self):
            pytest.fail("A foreign hash dispatch must not enter the source cache")

    value = ForeignBytes(raw) if drift == "equal_bytes_subclass" else b" " * (2**21 + 1)
    with pytest.raises(ValueError, match="Bounded exact source template"):
        binder(value)
    assert initial._dynamics_template.cache_info() == before


@pytest.mark.parametrize(
    "drift",
    (
        "helper_alias",
        "helper_code",
        "defaults",
        "builtins",
        "ast_alias",
        "parser_code",
        "cache_alias",
        "cache_code",
        "file",
    ),
)
def test_source_metadata_drift_cannot_borrow_a_warm_template(monkeypatch, tmp_path, drift):
    initial, api = retained.stage, retained.guards.stage
    raw = Path(stage.previous.__file__).read_bytes()
    binder = retained.clone(initial._dynamics_binding, previous=NS(_ready=lambda: api))
    binder(raw)
    before = initial._dynamics_template.cache_info()

    def foreign(*args, **kwargs):
        pytest.fail("Unproved metadata body must not execute")

    with monkeypatch.context() as patch:
        if drift == "helper_alias":
            patch.setattr(
                api, "_helper_binding", FunctionType(api._helper_binding.__code__, vars(api))
            )
        elif drift == "helper_code":
            patch.setattr(api._helper_binding, "__code__", (lambda *args: None).__code__)
        elif drift == "defaults":
            patch.setattr(api._helper_binding, "__defaults__", ())
        elif drift == "builtins":
            patch.setitem(vars(api), "__builtins__", dict(api._helper_binding.__builtins__))
        elif drift == "ast_alias":
            patch.setattr(api, "ast", ModuleType("ast"))
        elif drift == "parser_code":
            patch.setattr(ast.parse, "__code__", (lambda *args: None).__code__)
        elif drift == "cache_alias":
            patch.setattr(initial, "_dynamics_template", foreign)
        elif drift == "cache_code":
            patch.setattr(
                initial._dynamics_template.__wrapped__, "__code__", (lambda *args: None).__code__
            )
        else:
            patch.setattr(api, "__file__", str(tmp_path / "foreign-source.py"))
        with pytest.raises(ValueError, match="metadata|builtins|template"):
            binder(raw)
    assert initial._dynamics_template.cache_info() == before


@pytest.mark.parametrize("drift", ("none", "source", "code", "namespace", "name", "defaults"))
def test_source_metadata_cache_compares_live_target_functions_each_use(tmp_path, drift):
    initial, api = retained.stage, retained.guards.stage
    path = tmp_path / "read_only_metadata_function.py"
    raw = b"def selected(value=None, *, enabled=False):\n    return value\n"
    path.write_bytes(raw)
    module = ModuleType("read_only_metadata_not_an_owner")
    code = next(
        value for value in compile(raw, str(path), "exec").co_consts if type(value) is CodeType
    )
    function = FunctionType(code, vars(module), "selected", (None,))
    function.__kwdefaults__ = {"enabled": False}
    module.selected = function
    assert initial._metadata_source_interface(
        api, module, path.read_bytes(), path, ("selected",)
    ) == (function,)
    if drift == "none":
        assert initial._metadata_source_interface(
            api, module, path.read_bytes(), path, ("selected",)
        ) == (function,)
    else:
        if drift == "source":
            path.write_bytes(raw.replace(b"return value", b"return None"))
        elif drift == "code":
            function.__code__ = function.__code__.replace(co_name="foreign")
        elif drift == "namespace":
            module.selected = FunctionType(code, dict(vars(module)), "selected", (None,))
        elif drift == "name":
            function.__name__ = "foreign"
        else:
            function.__kwdefaults__["enabled"] = 0  # Equal value, wrong default type.
        with pytest.raises(ValueError, match="source.*code|defaults"):
            initial._metadata_source_interface(api, module, path.read_bytes(), path, ("selected",))


@pytest.mark.parametrize("slot", (None, "PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256", "body"))
def test_source_metadata_keeps_original_dynamics_backreference_controls(slot):
    initial = retained.stage
    raw = Path(stage.previous.__file__).read_bytes()
    binding = retained.clone(
        initial._dynamics_binding, previous=NS(_ready=lambda: retained.guards.stage)
    )
    identity, refs = binding(raw)
    assert refs == (("PARENT_SOURCE_SHA256", None), ("PARENT_REVIEW_SHA256", None))
    changed = raw
    if slot == "body":
        changed += b"\n# distinct exact prelude byte\n"
    elif slot is not None:
        # The old substring also matches COMPLETION_PARENT_REVIEW_SHA256.
        # Match the complete declared line; all other bytes stay exact.
        original = ("\n" + slot + " = None\n").encode()
        assert raw.count(original) == 1
        changed = raw.replace(original, ("\n" + slot + " = '" + "c" * 64 + "'\n").encode(), 1)
    actual, _ = binding(changed)
    assert (identity == actual) is (slot != "body")


@pytest.mark.parametrize("entry", ("api", "claim"))
def test_source_metadata_keeps_original_unbound_entry_refusal(entry, monkeypatch):
    retained.test_dynamics_handoff_unbound_gate_precedes_any_foreign_owner_or_callback(
        entry, monkeypatch
    )


def test_source_metadata_keeps_original_route_proof_and_midproof_alias_refusal(tmp_path):
    retained.test_completion_live_route_is_source_authenticated_before_invocation()
    retained.test_electrical_route_replaced_during_proof_never_invokes_unproved_capture(tmp_path)


def test_public_input_preflight_uses_supported_closed_metadata_not_enum_hydration(
    synthetic_init_inputs,
):
    # Stop before every issuer. This is not an owner or a cached parent.
    h = synthetic_init_inputs
    h.p.solver_type = "declared-metadata-FULL"
    result = h.scope.snapshot(dict(p=vars(h.p), cells=vars(h.cells)))
    assert result.all_finite and result.identity


@pytest.mark.parametrize(
    "change", ["owned", "unowned_sim", "cells", "parameters", "handler", "roster"]
)
def test_storage_projection_keeps_every_unowned_value_and_holder(change, monkeypatch):
    sim = NS(fluxes_mem=np.array([-0.0, 2.0]), vm_time=[1], retained=np.array([3.0]))
    cells, p, handler = NS(cell_i=np.array([0, 1])), NS(_run_sim=False), NS(epoch=1)
    objects = (("sim", sim), ("cells", cells), ("parameters", p), ("handler", handler))
    scope = NS(snapshot=observation.caches.snapshot, graph=observation.callers._graph)
    lease = NS(
        objects=objects,
        holders=tuple(vars(v) for _, v in objects),
        names=tuple(tuple(vars(v)) for _, v in objects),
        fields=[{} for _ in objects],
        allowed=frozenset(("fluxes_mem", "vm_time")),
    )
    context = NS(sim=sim, init_parent=NS(), storage_lease=lease)
    lease.view, lease.tape = (
        NS(objects=objects, fields=lease.fields),
        NS(rng=object(), events=(), draws=(), locals={}),
    )
    monkeypatch.setattr(stage, "_scope", lambda c: scope)
    monkeypatch.setattr(stage.previous.previous, "_projector", lambda c: NS(objects=list(objects)))
    before = stage._storage_values(context)
    if change == "owned":
        sim.fluxes_mem, sim.vm_time = np.array([0.0, 0.0]), []
    elif change == "unowned_sim":
        sim.retained[0] = 9.0
    elif change == "cells":
        cells.cell_i[:] = [1, 0]
    elif change == "parameters":
        p._run_sim = True
    elif change == "handler":
        handler.epoch = 2
    else:
        sim.foreign = 3
    if change == "roster":
        with pytest.raises(ValueError, match="field roster"):
            stage._storage_values(context)
    else:
        assert (stage._storage_values(context).identity == before.identity) is (change == "owned")


def test_storage_source_adoption_refuses_before_any_owner_or_consumer_callback(monkeypatch):
    monkeypatch.setattr(
        stage, "_storage_binding", lambda raw: pytest.fail("No consumer source callback")
    )
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._storage_api()
    assert caught.value.stage == "storage_held"


def test_storage_factored_checker_never_reopens_stale_completed_value_reader():
    tree = ast.parse(Path(stage.__file__).read_bytes())
    node = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_check_init_storage_authority"
    )
    metadata = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_storage_metadata"
    )
    calls = {
        n.func.id
        for part in (node, metadata)
        for n in ast.walk(part)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert not calls.intersection(("_authority", "_closed_epoch", "_check", "_snapshot", "_graph"))
    assert {"_storage_route", "_registry", "_storage_values", "_storage_graph", "_streams"} <= calls
    text = ast.unparse(metadata)
    assert "context.tissue._registry(lease.tissue_context, closed=True)" in text


def _electrical_projection(monkeypatch):
    # Projection-only control: this does not create/register any owner/claim.
    sim = NS(vm=np.array([-0.0, 1.0]), vm_time=[3], retained=np.array([4.0]))
    p, cells, handler = NS(_run_sim=False), NS(cell_i=np.array([0, 1])), NS(epoch=2)
    objects = (("sim", sim), ("parameters", p), ("cells", cells), ("handler", handler))
    lease = NS(
        objects=objects,
        holders=tuple(vars(v) for _, v in objects),
        names=tuple(tuple(vars(v)) for _, v in objects),
        fields=[{} for _ in objects],
        allowed=frozenset(("vm",)),
        storage_allowed=frozenset(("vm_time",)),
    )
    lease.view = NS(objects=objects, fields=lease.fields)
    lease.tape = NS(rng=object(), events=(), draws=(), locals={})
    context = NS(sim=sim, init_parent=NS(), electrical_descendant=lease)
    monkeypatch.setattr(
        stage,
        "_scope",
        lambda c: NS(snapshot=observation.caches.snapshot, graph=observation.callers._graph),
    )
    monkeypatch.setattr(stage.previous.previous, "_projector", lambda c: NS(objects=list(objects)))
    return context, sim, p, cells, handler


@pytest.mark.parametrize(
    "drift", ["owned", "storage", "other_sim", "parameter", "cell", "handler", "new_field"]
)
def test_electrical_projection_factors_only_current_and_historical_owned_fields(drift, monkeypatch):
    context, sim, p, cells, handler = _electrical_projection(monkeypatch)
    before = stage._electrical_values(context)
    if drift == "owned":
        sim.vm = np.array([0.0, 0.0])
    elif drift == "storage":
        sim.vm_time = []
    elif drift == "other_sim":
        sim.retained[0] = 8.0
    elif drift == "parameter":
        p._run_sim = True
    elif drift == "cell":
        cells.cell_i[:] = [1, 0]
    elif drift == "handler":
        handler.epoch += 1
    else:
        sim.foreign = 9
    if drift == "new_field":
        with pytest.raises(ValueError, match="field roster"):
            stage._electrical_values(context)
    else:
        assert (stage._electrical_values(context).identity == before.identity) is (
            drift in ("owned", "storage")
        )


def test_electrical_projection_keeps_unowned_equal_array_aliases_distinct(monkeypatch):
    context, sim, _, _, _ = _electrical_projection(monkeypatch)
    sim.alias = sim.retained
    lease = context.electrical_descendant
    lease.names = tuple(tuple(vars(value)) for _, value in lease.objects)
    before_value, before_graph = stage._electrical_values(context), stage._electrical_graph(context)
    sim.alias = sim.retained.copy()
    after_value, after_graph = stage._electrical_values(context), stage._electrical_graph(context)
    assert before_value.identity == after_value.identity
    assert before_graph[1] != after_graph[1]
    assert len(before_graph[0]) != len(after_graph[0]) or any(
        a is not b for a, b in zip(before_graph[0], after_graph[0], strict=True)
    )


def test_electrical_ancestor_source_gate_refuses_before_foreign_owner_inspection(monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("Held source cannot inspect a supplied owner")

    monkeypatch.setattr(stage, "_storage_binding", lambda *args: pytest.fail("No source callback"))
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._claim_electrical_ancestor(Foreign(), Foreign(), Foreign())
    assert caught.value.stage == "storage_held"


def test_electrical_ancestor_foreign_entry_cannot_use_a_valid_function_name(monkeypatch):
    # Module/name alone grants no source frame permission.
    consumer = NS(_claim_for_electrical=lambda *args: None)
    monkeypatch.setattr(stage, "_storage_api", lambda: consumer)
    monkeypatch.setattr(stage, "_storage_route", lambda *args: pytest.fail("No owner lookup"))
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._claim_electrical_ancestor(None, None, None)
    assert caught.value.stage == "electrical_entry"


def test_current_electrical_ancestry_checker_uses_factored_metadata_not_historical_snapshots():
    tree = ast.parse(Path(stage.__file__).read_bytes())
    selected = {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name in ("_check_electrical_ancestor", "_storage_metadata", "_electrical_route")
    }
    assert len(selected) == 3
    calls = {
        n.func.id
        for part in selected.values()
        for n in ast.walk(part)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert {
        "_electrical_route",
        "_storage_metadata",
        "_electrical_values",
        "_electrical_graph",
    } <= calls
    assert not calls.intersection(("_authority", "_closed_epoch", "_snapshot", "_graph", "_check"))


def test_native_molecule_request_is_an_explicit_typed_opt_in_preserving_ordinary_record():
    plain = stage.Request(object(), "parent", "source", (), "")
    assert plain.native_molecules is False
    assert stage.request_record(plain) == dict(
        law=stage.LAW_ID, parent="parent", source="source", files=()
    )
    selected = stage.Request(plain.prelude_owner, "parent", "source", (), "", native_molecules=True)
    assert stage.request_record(selected) == dict(
        law=stage.MOLECULE_LAW_ID, parent="parent", source="source", files=(), native_molecules=True
    )
    assert stage._digest(stage.request_record(plain)) != stage._digest(
        stage.request_record(selected)
    )


def test_native_molecule_declaration_gate_precedes_any_foreign_owner_inspection():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No held owner may be inspected")

    with pytest.raises(stage.CompletionRejected) as caught:
        stage.from_prelude_native_molecules(Foreign(), law_id=stage.MOLECULE_LAW_ID)
    assert caught.value.stage == "molecule_held"
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.from_prelude_native_molecules(Foreign(), law_id=stage.LAW_ID)
    assert caught.value.stage == "law"


@pytest.fixture
def native_molecule_domain():
    config = {"implement network": True, "biomolecules": [], "channels": None, "modulators": None}
    full = object()
    p = NS(
        _run_sim=False,
        is_ecm=True,
        ions_dict={"Ca": 0},
        Ca_dyn=False,
        molecules_enabled=True,
        grn_enabled=False,
        deform_osmo=False,
        fluid_flow=False,
        deformation=False,
        solver_type=full,
        network_config=config,
        _conf={"general network": config},
    )
    return NS(
        p=p,
        phase=NS(kind=NS(name="INIT")),
        sim=NS(molecules=None),
        original_globals={"SolverType": NS(FULL=full)},
    )


def test_ordinary_domain_keeps_enabled_network_refusal_before_opt_in_provider(
    native_molecule_domain, monkeypatch
):
    monkeypatch.setattr(
        stage, "_molecule_api", lambda: pytest.fail("Ordinary mode never obtains new authority")
    )
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(native_molecule_domain)
    assert caught.value.stage == "unavailable_branch"
    assert "molecules_enabled" in str(caught.value)


def test_explicit_native_domain_preserves_actual_configuration_and_phase_refs(
    native_molecule_domain, monkeypatch
):
    parent = native_molecule_domain
    seen = []

    def configuration(context):
        seen.append(context)
        return molecule._configuration(context)

    monkeypatch.setattr(
        stage, "_molecule_api", lambda: NS(_ready=lambda: None, _configuration=configuration)
    )
    stage._domain(parent, native_molecules=True)
    assert len(seen) == 1
    assert seen[0].p is parent.p and seen[0].phase is parent.phase and seen[0].sim is parent.sim
    assert parent.p.network_config is parent.p._conf["general network"]
    assert parent.p.molecules_enabled is True and parent.sim.molecules is None


@pytest.mark.parametrize(
    "flag", ["calcium", "grn_enabled", "deform_osmo", "fluid_flow", "deformation", "FAST"]
)
def test_native_molecule_opt_in_keeps_other_branch_owners_closed(
    native_molecule_domain, monkeypatch, flag
):
    parent = native_molecule_domain
    monkeypatch.setattr(
        stage, "_molecule_api", lambda: pytest.fail("Other owners remain unavailable")
    )
    if flag == "calcium":
        parent.p.ions_dict["Ca"], parent.p.Ca_dyn = 1, True
    elif flag == "FAST":
        parent.p.solver_type = object()
    else:
        setattr(parent.p, flag, True)
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(parent, native_molecules=True)
    assert caught.value.stage == "unavailable_branch"


@pytest.mark.parametrize("value", [None, 0, 1, "True"])
def test_native_molecule_domain_requires_exact_boolean_before_parent_read(value):
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(None, native_molecules=value)
    assert caught.value.stage == "domain"


def test_native_molecule_transport_retains_literal_body_and_explicit_source_callbacks():
    assert stage._code().co_qualname == "Simulator.init_dynamics"
    nodes = {
        node.name: node
        for node in ast.parse(Path(stage.__file__).read_bytes()).body
        if isinstance(node, ast.FunctionDef)
    }
    calls = ast.unparse(nodes["_namespace"])
    assert (
        "MasterOfMolecules=native_molecules if context.request.native_molecules else unavailable"
        in calls
    )
    assert "source_frame=sys._getframe(1)" in calls
    prepare = ast.unparse(nodes["prepare"])
    assert prepare.index("context.molecule.bind_completion") < prepare.index(
        "with context.account(context)"
    )
    assert "context.molecule_record" in prepare
    assert "molecule.observe(" in ast.unparse(nodes["_observe"])
    assert "context.molecule.graph_roots(" in ast.unparse(nodes["_graph"])
    assert "context.molecule.project_state(" in ast.unparse(nodes["_values"])


def test_default_channel_runtime_additive_interface_keeps_real_definition_exports():
    names = (
        "observes_runtime_frame",
        "runtime_wrapper_guard",
        "runtime_dispatch",
        "_runtime_resolution",
    )
    assert set(names) <= set(stage.MOLECULE_API)
    for name in names:
        function = vars(molecule)[name]
        assert type(function) is FunctionType
        assert function.__globals__ is vars(molecule)
    assert molecule.COMPLETION_SOURCE_SHA256 is None
    assert molecule.COMPLETION_REVIEW_SHA256 is None
    assert molecule.CONTRACT is None


@pytest.mark.parametrize("selected", [False, True])
def test_shared_helper_observation_is_attributed_only_to_actual_molecule_source_leg(selected):
    frame = sys._getframe()
    calls = []
    context = NS(
        pending={},
        primary=None,
        allowed_codes=frozenset((frame.f_code,)),
        frames={},
        tissue_session=None,
        molecule_session=object(),
        molecule_codes=frozenset((frame.f_code,)),
        claim=object(),
        molecule=NS(
            observes_source_frame=lambda *args: selected,
            observe=lambda *args, **kwargs: calls.append(kwargs),
            CaptureStop=RuntimeError,
        ),
        observer_namespace={"_witness": stage.previous._witness},
        last_raw=None,
    )
    stage._observe(context, frame, "return", None)
    assert len(calls) == int(selected)
    assert context.last_raw == (frame, None)


@pytest.mark.parametrize("source_failed", [False, True])
def test_molecule_capture_stop_keeps_original_primary_and_direct_raw_return(source_failed):
    frame, capture = sys._getframe(), OSError("molecule capture")
    primary = RuntimeError("original source") if source_failed else None
    cause = LookupError("original cause")
    if primary is not None:
        primary.__cause__ = cause

    class Stop(Exception):
        pass

    signal = Stop("incomplete source")
    signal.__cause__, signal.partial = capture, object()

    def observe(*args, **kwargs):
        raise signal

    context = NS(
        primary=primary,
        pending={},
        allowed_codes=frozenset((frame.f_code,)),
        frames={},
        tissue_session=None,
        molecule_session=object(),
        molecule_codes=frozenset((frame.f_code,)),
        claim=object(),
        molecule=NS(CaptureStop=Stop, observe=observe, observes_source_frame=lambda *args: True),
        molecule_capture_signal=None,
        observation_error=None,
        capture_error=None,
        capture_errors=(),
        last_capture=None,
        last_raw=None,
        reporting_failure=None,
        observer_namespace={
            "_witness": stage.previous._witness,
            "_record_capture": stage.previous._record_capture,
        },
    )
    if source_failed:
        stage._observe(context, frame, "return", None)
        assert context.primary is primary and context.primary.__cause__ is cause
    else:
        with pytest.raises(Stop) as caught:
            stage._observe(context, frame, "return", None)
        assert caught.value is signal and context.primary is None
    assert context.last_raw == (frame, None)
    assert context.capture_error is capture and context.molecule_capture_signal is signal


def _first_step_projection_model(monkeypatch):
    """Projection data only; no owner/claim is allocated or registered."""
    sim = NS(vm=np.array([1.0]), vm_time=[2], cc_cells=np.array([3.0]), untouched=np.array([4.0]))
    p, cells = NS(_run_sim=False), NS(cell_i=np.array([0, 1]))
    callback, gap = (
        NS(progress=0, identity="retained"),
        NS(alpha=np.array([1.0]), identity="retained"),
    )
    objects = (
        ("sim", sim),
        ("parameters", p),
        ("cells", cells),
        ("callback", callback),
        ("gap", gap),
    )
    permissions = (
        (sim, frozenset(("cc_cells",))),
        (callback, frozenset(("progress",))),
        (gap, frozenset(("alpha",))),
    )
    lease = NS(
        objects=objects,
        holders=tuple(vars(v) for _, v in objects),
        names=tuple(tuple(vars(v)) for _, v in objects),
        fields=[{} for _ in objects],
        full_fields=[{} for _ in objects],
        original=NS(allowed=frozenset(("vm",)), storage_allowed=frozenset(("vm_time",))),
        permissions=permissions,
    )
    lease.view = NS(objects=objects, fields=lease.fields)
    lease.full_view = NS(objects=objects, fields=lease.full_fields)
    lease.tape = NS(rng=None, events=(), draws=(), locals={})
    lease.child = NS(permissions=permissions)
    lease.module = NS(_mutation_contract=lambda c: permissions)
    context = NS(sim=sim, init_parent=NS(), first_step_descendant=lease)
    lease.parent = context
    monkeypatch.setattr(
        stage,
        "_scope",
        lambda c: NS(snapshot=observation.caches.snapshot, graph=observation.callers._graph),
    )
    monkeypatch.setattr(stage.previous.previous, "_projector", lambda c: NS(objects=list(objects)))
    return context, sim, p, cells, callback, gap


@pytest.mark.parametrize(
    "change",
    ["owned_sim", "callback", "gap", "historical", "parameter", "cell", "unowned", "roster"],
)
def test_first_step_projection_keeps_distinct_epoch_permissions(change, monkeypatch):
    context, sim, p, cells, callback, gap = _first_step_projection_model(monkeypatch)
    before = stage._first_step_values(context, stable=True)
    if change == "owned_sim":
        sim.cc_cells[:] = 5.0
    elif change == "callback":
        callback.progress = 1
    elif change == "gap":
        gap.alpha[:] = 2.0
    elif change == "historical":
        sim.vm = np.array([5.0])
        sim.vm_time = []
    elif change == "parameter":
        p._run_sim = True
    elif change == "cell":
        cells.cell_i[:] = [1, 0]
    elif change == "unowned":
        sim.untouched[:] = 9.0
    else:
        sim.foreign = 1
    if change == "roster":
        with pytest.raises(ValueError, match="field roster"):
            stage._first_step_values(context, stable=True)
    else:
        assert (stage._first_step_values(context, stable=True).identity == before.identity) is (
            change in ("owned_sim", "callback", "gap", "historical")
        )


def test_first_step_pre_source_full_proof_does_not_exclude_future_owned_fields(monkeypatch):
    context, sim, *_ = _first_step_projection_model(monkeypatch)
    before = stage._first_step_values(context, stable=False)
    sim.cc_cells[:] = 99.0
    assert stage._first_step_values(context, stable=False).identity != before.identity


def test_first_step_persistent_graph_repeated_reads_preserve_all_reference_identities(monkeypatch):
    context, *_ = _first_step_projection_model(monkeypatch)
    before = stage._first_step_graph(context, stable=True)
    after = stage._first_step_graph(context, stable=True)
    assert before[1] == after[1] and len(before[0]) == len(after[0])
    assert all(a is b for a, b in zip(before[0], after[0], strict=True))


@pytest.mark.parametrize("drift", ["owner", "field", "type", "duplicate", "missing_sim"])
def test_first_step_permission_roster_is_exact_source_and_owner_bound(monkeypatch, drift):
    context, sim, *_ = _first_step_projection_model(monkeypatch)
    lease = context.first_step_descendant
    assert stage._first_step_permissions(lease) is lease.permissions
    rows = list(lease.permissions)
    if drift == "owner":
        rows[0] = (NS(**vars(sim)), rows[0][1])
    elif drift == "field":
        rows[0] = (sim, rows[0][1] | {"untouched"})
    elif drift == "type":
        rows[0] = (sim, set(rows[0][1]))
    elif drift == "duplicate":
        rows[1] = rows[0]
    else:
        rows.pop(0)
    lease.child.permissions = tuple(rows)
    with pytest.raises(ValueError):
        stage._first_step_permissions(lease)


def _runtime_permission_projection_model(monkeypatch, *, continuous=True, closed=False):
    """Actual checker over synthetic metadata; no issuer/registry/owner exists."""
    context, sim, *_ = _first_step_projection_model(monkeypatch)

    class MetadataKey:
        pass

    context.owner = MetadataKey()  # Registry key only; never a DynamicsOwner.
    lease, source = context.first_step_descendant, ModuleType("source_permission_metadata")
    runtime = ModuleType("continuous_permission_metadata") if continuous else source
    core, session, claim = NS(store=[]), object(), object()
    record = object() if closed else None
    base_rows = lease.permissions
    extension = ((sim, frozenset(("molecule_flux",))), (core, frozenset(("store",))))
    complete = (
        (sim, base_rows[0][1] | extension[0][1]),
        *base_rows[1:],
        extension[1],
    )
    context.request = NS(native_molecules=True)
    context.molecule, context.molecule_session = source, session
    lease.objects += (("molecule_core", core),)
    lease.molecule_claim = claim
    child = lease.child
    child.permissions = complete
    child.molecule, child.molecule_claim = source, claim
    child.molecule_permissions, child.molecule_record = extension, record
    calls = []

    def active(actual, *, child):
        calls.append(("active", actual, child))
        return actual

    def final(actual, *, child):
        calls.append(("closed", actual, child))
        return record

    def permissions(actual):
        calls.append(("permissions", actual))
        return extension

    runtime.validate_runtime_active = active
    runtime.validate_runtime = final
    runtime.runtime_permissions = permissions
    if continuous:
        lease.runtime_api = child.short_runtime = runtime
        runtime.session_of = lambda actual, *, child: session
        runtime.session_provider = lambda actual, *, child: source
    monkeypatch.setattr(stage, "_molecule_api", lambda: source)
    monkeypatch.setattr(stage, "_molecule_short_api", lambda: runtime)
    lease.module._mutation_contract = lambda value: complete
    return lease, runtime, calls, extension, complete


@pytest.mark.parametrize(
    "continuous,closed", ((False, False), (False, True), (True, False), (True, True))
)
def test_first_step_runtime_permissions_use_exact_active_or_closed_claim_and_complete_contract(
    monkeypatch, continuous, closed
):
    lease, _, calls, extension, complete = _runtime_permission_projection_model(
        monkeypatch, continuous=continuous, closed=closed
    )
    assert stage._first_step_runtime_permissions(lease) is extension
    assert stage._first_step_permissions(lease) is complete
    assert [row[0] for row in calls] == [
        "closed" if closed else "active",
        "permissions",
        "closed" if closed else "active",
        "permissions",
    ]
    assert all(row[1] is lease.molecule_claim for row in calls)


@pytest.mark.parametrize(
    "drift",
    (
        "foreign_claim",
        "missing_session",
        "foreign_provider",
        "foreign_session",
        "foreign_source",
        "copied_extension",
        "foreign_holder",
        "duplicate_holder",
        "extra_field",
        "missing_extension",
        "missing_extension_both",
        "unowned_holder",
        "disabled_parent",
        "set_fields",
    ),
)
def test_first_step_runtime_permissions_refuse_forged_or_incomplete_merged_rows(monkeypatch, drift):
    lease, runtime, calls, extension, complete = _runtime_permission_projection_model(monkeypatch)
    child, parent = lease.child, lease.parent
    if drift == "foreign_claim":
        child.molecule_claim = object()
    elif drift == "missing_session":
        parent.molecule_session = None
    elif drift == "foreign_provider":
        foreign = ModuleType(runtime.__name__)
        foreign.__dict__.update(vars(runtime))
        lease.runtime_api = child.short_runtime = foreign
    elif drift == "foreign_session":
        runtime.session_of = lambda actual, *, child: object()
    elif drift == "foreign_source":
        child.molecule = ModuleType(parent.molecule.__name__)
    elif drift == "copied_extension":
        # Contents alone agree; only the actual runtime's retained tuple owns it.
        child.molecule_permissions = tuple(list(extension))
    elif drift in (
        "foreign_holder",
        "duplicate_holder",
        "extra_field",
        "missing_extension",
        "set_fields",
    ):
        rows = list(complete)
        if drift == "foreign_holder":
            rows[-1] = (NS(**vars(rows[-1][0])), rows[-1][1])
        elif drift == "duplicate_holder":
            rows.append(rows[-1])
        elif drift == "extra_field":
            rows[-1] = (rows[-1][0], rows[-1][1] | {"unowned"})
        elif drift == "set_fields":
            rows[-1] = (rows[-1][0], set(rows[-1][1]))
        else:
            rows.pop()
        child.permissions = tuple(rows)
    elif drift == "missing_extension_both":
        # Matching actual/public rows alone must not hide omitted canonical work.
        child.permissions = complete[:-1]
        lease.module._mutation_contract = lambda value: complete[:-1]
    elif drift == "unowned_holder":
        lease.objects = lease.objects[:-1]
    else:
        parent.request.native_molecules = False
    with pytest.raises(ValueError):
        stage._first_step_permissions(lease)
    if drift in (
        "foreign_claim",
        "missing_session",
        "foreign_provider",
        "foreign_session",
        "foreign_source",
        "disabled_parent",
    ):
        assert not calls


def test_first_step_runtime_permissions_keep_primary_refusal_before_contract_observation(
    monkeypatch,
):
    lease, runtime, _, _, _ = _runtime_permission_projection_model(monkeypatch)
    primary, cause = ValueError("actual runtime refusal"), KeyError("actual cause")
    primary.__cause__ = cause

    def refused(*args, **kwargs):
        raise primary

    def forbidden(*args):
        pytest.fail("No source contract observation after a runtime refusal")

    runtime.validate_runtime_active = refused
    lease.module._mutation_contract = forbidden
    with pytest.raises(ValueError) as caught:
        stage._first_step_permissions(lease)
    assert caught.value is primary and primary.__cause__ is cause


@pytest.mark.parametrize(
    "drift", ("active_result", "closed_result", "permission_type", "session_provider")
)
def test_first_step_runtime_permissions_reject_foreign_validator_results_and_transport(
    monkeypatch, drift
):
    lease, runtime, _, extension, _ = _runtime_permission_projection_model(
        monkeypatch, closed=drift == "closed_result"
    )
    if drift == "active_result":
        runtime.validate_runtime_active = lambda actual, *, child: object()
    elif drift == "closed_result":
        runtime.validate_runtime = lambda actual, *, child: object()
    elif drift == "permission_type":
        rows = list(extension)
        lease.child.molecule_permissions = rows
        runtime.runtime_permissions = lambda actual: rows
    else:
        runtime.session_provider = lambda actual, *, child: ModuleType(
            lease.parent.molecule.__name__
        )
    with pytest.raises(ValueError):
        stage._first_step_permissions(lease)


def test_first_step_runtime_permissions_ordinary_route_never_reads_molecular_authority(monkeypatch):
    context, *_ = _first_step_projection_model(monkeypatch)

    def forbidden():
        pytest.fail("Unchanged ordinary route cannot require a molecular provider")

    monkeypatch.setattr(stage, "_molecule_api", forbidden)
    monkeypatch.setattr(stage, "_molecule_short_api", forbidden)
    lease = context.first_step_descendant
    assert stage._first_step_runtime_permissions(lease) == ()
    assert stage._first_step_permissions(lease) is lease.permissions


@pytest.mark.parametrize("mode", ("early", "setup", "loop", "admission", "executed", "mutated"))
def test_terminal_ancestor_permission_seal_requires_full_proof_before_any_source_attempt(
    monkeypatch, mode
):
    """Real sealing/checking code; only unissued projection data, no INIT parent."""
    context, sim, *_ = _first_step_projection_model(monkeypatch)
    lease, electrical = context.first_step_descendant, object()
    transition = lease.child
    transition.setup_frame = transition.loop_frame = None
    transition.work = []
    lease.status = "reserved"
    lease.before = stage._first_step_values(context, stable=False)
    lease.before_graph = stage._first_step_graph(context, stable=False)
    lease.module._check_ancestor_metadata = lambda child: electrical
    lease.ancestor_check = lambda *args: context.init_parent
    monkeypatch.setattr(stage, "_storage_metadata", lambda parent: None)
    if mode == "setup":
        transition.setup_frame = object()
    elif mode == "loop":
        transition.loop_frame = object()
    elif mode in ("admission", "executed"):
        transition.work.append(dict(body_started=mode == "executed"))
    elif mode == "mutated":
        sim.cc_cells[0] = 99.0
    if mode != "early":
        with pytest.raises(ValueError):
            stage._check_advance_ancestor(context, object(), electrical, transition, lease)
        assert lease.status == "reserved"
    else:
        assert (
            stage._check_advance_ancestor(context, object(), electrical, transition, lease)
            is context
        )
        assert lease.status == "sealed"
        transition.setup_frame = object()
        transition.work.append(dict(body_started=True))
        sim.cc_cells[0] = 99.0
        assert (
            stage._check_advance_ancestor(context, object(), electrical, transition, lease)
            is context
        )


@pytest.mark.parametrize(
    "operation",
    ("runtime", "completion", "storage", "storage_claim", "electrical", "electrical_claim"),
)
def test_terminal_ancestor_unadopted_source_gates_precede_foreign_owner_access(operation):
    from cells.processes import betse_native_init_electrical as electrical
    from cells.processes import betse_native_init_storage as storage

    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No foreign owner read before terminal source adoption")

    value = Foreign()
    calls = {
        "runtime": lambda: stage._molecule_terminal_api(),
        "completion": lambda: stage._claim_terminal_init_ancestor(value, value, value, value),
        "storage": lambda: storage._terminal_init_key_api(),
        "storage_claim": lambda: storage._claim_terminal_init_ancestor(value, value),
        "electrical": lambda: electrical._terminal_init_api(),
        "electrical_claim": lambda: electrical._claim_for_terminal_init(
            value, expected=value, transition=value, entries=value
        ),
    }
    with pytest.raises(
        (stage.CompletionRejected, storage.StorageRejected, electrical.ElectricalRejected)
    ) as caught:
        calls[operation]()
    assert "held" in caught.value.stage


@pytest.mark.parametrize(
    "mode", ("none", "first", "short", "terminal", "terminal_first", "terminal_short")
)
def test_terminal_ancestor_retained_dispatch_keeps_distinct_exclusive_routes(mode):
    parent = NS(invalid=False, entry_error=None, stage="metadata", request=None, trial=None)
    child, holder = object(), NS()
    if "terminal" in mode:
        holder.terminal_init_transition = child
    if mode in ("first", "terminal_first"):
        holder.first_step_transition = object()
    if mode in ("short", "terminal_short"):
        holder.short_init_transition = object()
    if mode.startswith("terminal_"):
        with pytest.raises(retained.stage.InitRejected):
            retained.stage._advance_child(parent, holder)
        assert parent.invalid
    else:
        value, route = retained.stage._advance_child(parent, holder)
        if mode == "terminal":
            assert value is child and route is retained.stage._terminal_init_runtime
        elif mode == "short":
            assert (
                value is holder.short_init_transition
                and route is retained.stage._short_init_runtime
            )
        else:
            assert value is getattr(holder, "first_step_transition", None)
            assert route is retained.stage._first_step_runtime


@pytest.mark.parametrize("closed", (False, True))
def test_terminal_ancestor_runtime_authentication_never_falls_back_to_short(monkeypatch, closed):
    lease, runtime, _, extension, complete = _runtime_permission_projection_model(
        monkeypatch, closed=closed
    )

    class MetadataKey:
        pass

    parent = lease.parent
    parent.owner = MetadataKey()
    del parent.first_step_descendant
    parent.terminal_init_descendant = lease
    lease.child.terminal_runtime = runtime
    del lease.child.short_runtime
    monkeypatch.setitem(stage._TERMINAL_INIT_DESCENDANTS, parent.owner, lease)
    monkeypatch.setattr(stage, "_molecule_terminal_api", lambda: runtime)

    def forbidden():
        pytest.fail("A terminal claimant cannot use the short-runtime getter")

    monkeypatch.setattr(stage, "_molecule_short_api", forbidden)
    assert stage._advance_lease(parent) is lease
    assert stage._first_step_runtime_permissions(lease) is extension
    assert stage._first_step_permissions(lease) is complete


@pytest.mark.parametrize("missing", (False, True))
def test_terminal_ancestor_registry_and_alias_are_both_required(monkeypatch, missing):
    class MetadataKey:
        pass

    owner, lease = MetadataKey(), object()
    parent = NS(owner=owner, terminal_init_descendant=lease)
    if not missing:
        monkeypatch.setitem(stage._TERMINAL_INIT_DESCENDANTS, owner, lease)
        parent.short_init_descendant = object()
    with pytest.raises(ValueError):
        stage._advance_lease(parent)


@pytest.mark.parametrize("drift", (False, True))
def test_terminal_ancestor_actual_storage_key_source_proof_is_metadata_only(monkeypatch, drift):
    from cells.processes import betse_native_init_storage as storage

    monkeypatch.setattr(storage, "TERMINAL_INIT_ANCESTOR_CLAIM", "_claim_terminal_init_ancestor")
    monkeypatch.setattr(storage, "TERMINAL_INIT_ANCESTOR_CHECK", "_check_terminal_init_ancestor")
    monkeypatch.setattr(storage, "_ready", lambda: None)
    if drift:

        def forbidden(*args):
            pytest.fail("Foreign issuer body must be rejected before execution")

        monkeypatch.setattr(stage._claim_terminal_init_ancestor, "__code__", forbidden.__code__)
        with pytest.raises(ValueError):
            storage._terminal_init_key_api()
    else:
        rows = storage._terminal_init_key_api()
        assert tuple(row[0] for row in rows) == (
            "_claim_terminal_init_ancestor",
            "_check_terminal_init_ancestor",
        )
        assert rows[0][1] is stage._claim_terminal_init_ancestor


def test_first_step_ancestor_source_gate_precedes_foreign_owner_inspection():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("Held source cannot inspect a supplied owner")

    with pytest.raises(stage.CompletionRejected) as caught:
        stage._claim_first_step_ancestor(Foreign(), Foreign(), Foreign(), Foreign())
    assert caught.value.stage == "storage_held"


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    function = inherited._blocked_generator
    generator = FunctionType(
        function.__code__, dict(function.__globals__, stage=stage, runner=runner)
    )(request, tmp_path, monkeypatch)
    before, started, primary = (sys.getprofile(), sys.gettrace()), False, None
    failed = len(stage._FAILED)
    try:
        next(generator)
        started = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        drain = FunctionType(
            inherited.cleanup._drain_guard.__code__,
            dict(
                inherited.cleanup._drain_guard.__globals__,
                _write_failure_diagnostics=inherited._diagnostics,
            ),
        )
        drain(
            generator,
            started,
            tuple(stage._FAILED[failed:]),
            tmp_path,
            required_hooks=before,
            primary=primary,
        )


def test_original_whole_tail_order_and_rng_are_compiled_without_execution(tmp_path):
    plan = stage.source_plan()
    assert plan["extent"] == (809, 1012) and plan["original_tail_statements"] == 35
    assert plan["original_alias_reads"] == (778, 779) and not plan["prefix_replayed"]
    assert plan["full_module_compile_context"] and plan["mandatory_channel_rng_even_if_level_zero"]
    assert not plan["time_vector_solver_storage_updateV_pickle_or_completed_INIT_admission"]
    node = stage._node()
    text = ast.unparse(node)
    assert text.index("phase.dyna.init_profiles(phase)") < text.index("np.random.random(self.mdl)")
    assert text.index("np.random.random(self.mdl)") < text.index("p.channel_noise_level")
    assert text.index("self.cellso = cells") < text.index("phase.dyna.init_events(phase)")
    assert (
        text.index("phase.dyna.init_events(phase)")
        < text.index("self.ko_env")
        < text.index("self.cgj")
    )
    assert text.index("self.cgj") < text.index("self.fast_sim_init")
    assert "RandomState(" not in text and ".seed(" not in text
    assert "smooth_weight_mem" not in text and "self.initDenv" not in text
    code = stage._code()
    assert type(code) is CodeType and code.co_qualname == "Simulator.init_dynamics"
    assert code.co_filename == str(stage.NATIVE / stage.SIM_FILE)
    runner.snapshot.write_json(
        tmp_path / "source-only.json",
        dict(plan=plan, compiled_qualname=code.co_qualname, actual_original_helper_or_rng_calls=0),
    )


@pytest.mark.parametrize("mode", ["default", "integer", "environment"])
def test_source_and_rng_release_refuses_before_source_or_owner_access(monkeypatch, mode):
    monkeypatch.setenv(stage.RELEASE, "0" if mode == "environment" else "1")
    monkeypatch.setattr(
        stage, "_ready", lambda: pytest.fail("No runtime/owner access before release")
    )
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.prepare(None, enabled=1 if mode == "integer" else mode != "default")
    assert caught.value.stage == "release"


def test_parent_and_tissue_adoption_remain_real_missing_prerequisites(monkeypatch):
    monkeypatch.setattr(
        stage.previous, "_authority", lambda value: pytest.fail("No arbitrary parent access")
    )
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.from_prelude(None, law_id=stage.LAW_ID)
    assert caught.value.stage == "unbound"
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.from_prelude(None, law_id="foreign")
    assert caught.value.stage == "law"


@pytest.mark.parametrize("value", [None, {}, NS(), object.__new__(stage.CompletionClaim)])
def test_record_namespace_and_unissued_claim_do_not_authorize_participation(value):
    with pytest.raises(stage.CompletionRejected):
        stage.validate_active(value, original_owner=None)
    with pytest.raises(stage.CompletionRejected):
        stage.failed_context(value)


class Solver(Enum):
    FULL = 1
    FAST = 2


@pytest.fixture
def declaration():
    """Only a domain-check declaration, never an issued phase/PreludeOwner."""
    p = NS(
        _run_sim=False,
        is_ecm=True,
        ions_dict={"Ca": 0},
        Ca_dyn=False,
        molecules_enabled=False,
        grn_enabled=False,
        deform_osmo=False,
        fluid_flow=False,
        deformation=False,
        solver_type=Solver.FULL,
        channel_noise_level=0.0,
    )
    return NS(p=p, phase=NS(kind=NS(name="INIT")), original_globals={"SolverType": Solver})


def test_ordinary_scope_accepts_declaration_without_executing_a_body_or_rng(declaration):
    stage._domain(declaration)
    assert declaration.p.channel_noise_level == 0.0


@pytest.mark.parametrize(
    "field",
    [
        "Ca",
        "molecules_enabled",
        "grn_enabled",
        "deform_osmo",
        "fluid_flow",
        "deformation",
        "FAST",
        "unknown_solver",
    ],
)
def test_actual_requested_unowned_branch_is_not_silently_disabled(declaration, field):
    p = declaration.p
    if field == "Ca":
        p.ions_dict["Ca"], p.Ca_dyn = 1, True
    elif field == "FAST":
        p.solver_type = Solver.FAST
    elif field == "unknown_solver":
        p.solver_type = object()
    else:
        setattr(p, field, True)
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(declaration)
    assert caught.value.stage == "unavailable_branch"
    if field not in ("Ca", "FAST", "unknown_solver"):
        assert getattr(p, field) is True


@pytest.mark.parametrize("field,value", [("_run_sim", True), ("is_ecm", False), ("kind", "SEED")])
def test_actual_phase_and_ecm_boundary_are_not_relabelled(declaration, field, value):
    if field == "kind":
        declaration.phase.kind.name = value
    else:
        setattr(declaration.p, field, value)
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(declaration)
    assert caught.value.stage == "domain"


def test_participation_registry_check_is_distinct_from_recursive_full_audit():
    tree = ast.parse(open(stage.__file__).read())
    funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "_check(" not in ast.unparse(funcs["_active"])
    assert "_registry(context)" in ast.unparse(funcs["_active"])
    assert "context.tissue.validate_active" in ast.unparse(funcs["_check"])
    assert "record" not in ast.unparse(funcs["_active"])
    assert "observe" in stage.TISSUE_API and "validate_rng_call" in stage.TISSUE_API


def test_shared_observer_recipe_keeps_existing_guard_code_and_current_registry():
    context = NS()
    stage._observer_recipe(context)
    namespace = context.observer_namespace
    assert namespace["_ACTIVE"] is stage._ACTIVE
    assert namespace["_guard"].__code__ is stage.previous._guard.__code__
    assert namespace["_recover_hooks"].__code__ is stage.previous._recover_hooks.__code__
    assert namespace["_observe"] is stage._observe and namespace["_epoch"] is stage._epoch
    assert namespace["DynamicsRejected"] is stage.CompletionRejected
    assert namespace is not vars(stage.previous)


@pytest.mark.parametrize(
    "change", ["check", "guard", "inherited", "extra", "drop", "account", "code"]
)
def test_private_observer_namespace_code_and_entry_are_bound_without_calls(monkeypatch, change):
    context = NS()
    stage._observer_recipe(context)
    before = stage._observer_bindings(context)
    stage._same_refs(stage._observer_bindings(context), before)
    namespace = context.observer_namespace
    if change in ("check", "guard", "inherited"):
        namespace["_" + change] = lambda *args: pytest.fail("Foreign checker must not enter")
    elif change == "extra":
        namespace["foreign"] = object()
    elif change == "drop":
        del namespace["_ACTIVE"]
    elif change == "account":
        context.account = lambda *args: pytest.fail("Foreign observer must not enter")
    else:
        function = namespace["_guard"]
        monkeypatch.setattr(function, "__code__", function.__code__.replace(co_name="foreign"))
    with pytest.raises(ValueError):
        stage._same_refs(stage._observer_bindings(context), before)


@pytest.fixture
def rng_model(monkeypatch):
    """Conditional call-record model, not an owned RNG/Prelude/phase authority.

    No random generator is constructed or called. The callback only changes a
    declared metadata stream label and returns a predeclared shaped buffer.
    """
    h = NS(claim=object(), stream="before", result=np.array([0.25, 0.75]), error=None)
    frame = sys._getframe(1)
    context = NS(
        claim=h.claim,
        request=None,
        draw_active=None,
        rng_calls=[],
        channel_random_attempts=0,
        body_frame=frame,
        namespace=frame.f_globals,
        sim=NS(mdl=2),
        cell_i=np.array([0, 1]),
        current_cell_i=NS(identity="cell"),
        primary=None,
        capture_error=None,
        capture_errors=(),
        reporting_failure=None,
        last_capture=None,
        stage="conditional-RNG-record-only",
        invalid=False,
        entry_error=None,
        observer_namespace={"_record_capture": stage.previous._record_capture},
    )

    def delegate(size):
        assert size is context.sim.mdl
        h.stream = "after"
        if h.error is not None:
            raise h.error
        return h.result

    context.np_random = delegate
    h.context = context

    def active(claim):
        assert claim is h.claim
        return context

    monkeypatch.setattr(
        stage,
        "_active",
        active,
    )
    monkeypatch.setattr(stage, "_check", lambda value, **kw: None)
    monkeypatch.setattr(
        stage, "_streams", lambda value: (NS(identity=h.stream), NS(identity="stdlib-unchanged"))
    )
    monkeypatch.setattr(stage, "_cell_snapshot", lambda value: NS(identity="cell"))
    return h


def test_rng_actual_call_record_preserves_argument_return_and_before_after_roots(rng_model):
    h = rng_model
    c = h.context
    frame = sys._getframe()
    c.body_frame, c.namespace = frame, frame.f_globals
    returned = stage.rng_call(
        h.claim,
        participant=None,
        library="numpy",
        operation="random",
        delegate=c.np_random,
        args=(c.sim.mdl,),
        kwargs={},
        source_frame=frame,
    )
    assert returned is h.result and len(c.rng_calls) == 1
    record = c.rng_calls[0]
    assert record.raw_return is h.result and record.returned
    assert record.before[0].identity == "before" and record.after[0].identity == "after"
    assert record.source_frame is frame and c.draw_active is None
    assert stage._rng_record(record)["independent_case"] is False
    with pytest.raises(stage.CompletionRejected, match="Duplicate"):
        stage.rng_call(
            h.claim,
            participant=None,
            library="numpy",
            operation="random",
            delegate=c.np_random,
            args=(c.sim.mdl,),
            kwargs={},
            source_frame=frame,
        )


@pytest.mark.parametrize(
    "mode", ["foreign_delegate", "wrong_shape_argument", "foreign_frame", "active_draw"]
)
def test_rng_record_authority_drift_refuses_before_delegate(rng_model, mode):
    h = rng_model
    c = h.context
    frame = sys._getframe()
    c.body_frame, c.namespace = frame, frame.f_globals
    delegate = c.np_random
    args = (c.sim.mdl,)
    source = frame
    if mode == "foreign_delegate":

        def delegate(size):
            pytest.fail("Foreign delegate entered")
    elif mode == "wrong_shape_argument":
        args = (99,)
    elif mode == "foreign_frame":
        source = rng_model.context.body_frame.f_back
    else:
        c.draw_active = object()
    with pytest.raises(stage.CompletionRejected):
        stage.rng_call(
            h.claim,
            participant=None,
            library="numpy",
            operation="random",
            delegate=delegate,
            args=args,
            kwargs={},
            source_frame=source,
        )
    assert not c.rng_calls and h.stream == "before"


def test_rng_source_failure_retains_partial_stream_advance_and_original_exception(rng_model):
    h = rng_model
    c = h.context
    frame = sys._getframe()
    c.body_frame, c.namespace = frame, frame.f_globals
    h.error = RuntimeError("conditional-original-failure")
    with pytest.raises(RuntimeError) as caught:
        stage.rng_call(
            h.claim,
            participant=None,
            library="numpy",
            operation="random",
            delegate=c.np_random,
            args=(c.sim.mdl,),
            kwargs={},
            source_frame=frame,
        )
    assert caught.value is h.error and c.primary is h.error
    assert c.rng_calls[0].after[0].identity == "after"
    assert not c.rng_calls[0].returned and c.draw_active is None


@dataclass(frozen=True)
class ConditionalWitness:
    source_frame: object
    cell_i_view: object


def test_original_choice_owner_is_admitted_only_through_actual_participant_witness(rng_model):
    h = rng_model
    c = h.context
    frame = sys._getframe()
    participant = object()

    class ConditionalRng:
        def choice(self, values):
            h.stream = "after"
            return h.result

    c.np_rng = ConditionalRng()
    c.tissue_session = participant
    c.tissue = NS(
        RngWitness=ConditionalWitness,
        validate_rng_call=lambda *args, **kw: ConditionalWitness(frame, None),
    )
    result = stage.rng_call(
        h.claim,
        participant=participant,
        library="numpy",
        operation="choice",
        delegate=c.np_rng.choice,
        args=(c.cell_i,),
        kwargs={},
        source_frame=frame,
    )
    assert result is h.result and c.rng_calls[0].operation == "choice"
    assert c.channel_random_attempts == 0


def test_percent_slice_view_mutation_retains_original_array_membership(rng_model):
    h = rng_model
    c = h.context
    frame = sys._getframe()
    participant = object()
    cell_i_copy = c.cell_i[:]

    class ConditionalRng:
        def shuffle(self, values):
            h.stream = "after"
            values[:] = values[::-1]

    c.numpy = np
    c.np_rng = ConditionalRng()
    c.tissue_session = participant
    c.tissue = NS(
        RngWitness=ConditionalWitness,
        validate_rng_call=lambda *args, **kw: ConditionalWitness(frame, cell_i_copy),
    )
    original = c.cell_i
    assert cell_i_copy is not original and cell_i_copy.base is original
    result = stage.rng_call(
        h.claim,
        participant=participant,
        library="numpy",
        operation="shuffle",
        delegate=c.np_rng.shuffle,
        args=(cell_i_copy,),
        kwargs={},
        source_frame=frame,
    )
    assert result is None and c.cell_i is original and c.cell_i.tolist() == [1, 0]
    assert c.rng_calls[0].raw_return is None and c.rng_calls[0].returned


def test_file_inputs_are_issued_typed_records_not_supplied_path_dicts():
    for value in ([], {}, (NS(filename="/mnt/workspaces/Cells/image.png"),)):
        with pytest.raises((stage.CompletionRejected, stage.files.YamlPrefixRejected)):
            stage._file_inputs(value)


def test_capture_reporting_failure_is_secondary_to_direct_retained_error():
    primary = ValueError("observation-primary")
    secondary = OSError("reporting-secondary")

    def refused(*args):
        raise secondary

    context = NS(
        capture_error=None,
        last_capture=None,
        observer_namespace={"_record_capture": refused},
        reporting_failure=None,
    )
    witness = object()
    stage._capture(context, "conditional", primary, witness)
    assert context.capture_error is primary and context.last_capture[2] is witness
    assert context.reporting_failure[0] is secondary


def test_stable_projection_does_not_reintroduce_cell_i_through_duplicate_holder(monkeypatch):
    """Metadata array permutation; no phase/owner or native picker is issued."""
    cells = NS(cell_i=np.array([0, 1]), geometry=np.array([2.0, 3.0]))
    p, handler = NS(_run_sim=False, configuration={"literal": 1}), NS(profile="before")
    sim = NS(rho_pump=0, unowned=np.array([0.1, 0.2]))
    phase = NS(p=p, cells=cells, sim=sim, dyna=handler)
    objects = (
        ("cells", cells),
        ("sim", sim),
        ("handler", handler),
        ("phase", phase),
        ("parameters", p),
    )
    context = NS(
        init_parent=NS(objects=objects),
        parent=NS(gap=None),
        phase=phase,
        p=p,
        cells=cells,
        sim=sim,
        tissue_session=None,
        molecule_session=None,
        request=stage.Request(None, "metadata", "metadata", (), ""),
        original_objects=objects,
        cell_i=cells.cell_i,
    )
    monkeypatch.setattr(
        stage.previous.previous, "_projector", lambda original: NS(objects=list(objects))
    )
    snapshot = observation.caches.snapshot
    before = snapshot(stage._values(context, stable=True))
    full_before = snapshot(stage._values(context))
    cells.cell_i[:] = [1, 0]
    handler.profile = "declared-new-profile"
    sim.rho_pump = 1
    assert snapshot(stage._values(context, stable=True)).identity == before.identity
    assert snapshot(stage._values(context)).identity != full_before.identity
    cells.geometry[0] = 9.0
    assert snapshot(stage._values(context, stable=True)).identity != before.identity


def test_equal_cell_index_replacement_is_refused_before_snapshot_or_rng(monkeypatch):
    original = np.array([0, 1])
    context = NS(cell_i=original, cells=NS(cell_i=original.copy()))
    monkeypatch.setattr(stage, "_scope", lambda value: pytest.fail("No foreign buffer snapshot"))
    with pytest.raises(ValueError, match="cell_i array object replaced"):
        stage._cell_snapshot(context)


@pytest.mark.parametrize("source_failed", [False, True])
def test_tissue_capture_stop_preserves_raw_return_and_separates_native_primary(source_failed):
    frame, capture = sys._getframe(), OSError("tissue observation refused")
    source_primary = RuntimeError("original source failure") if source_failed else None
    cause = LookupError("original source cause")
    if source_primary is not None:
        source_primary.__cause__ = cause

    class Stop(Exception):
        pass

    signal = Stop("incomplete tissue observation")
    signal.__cause__, signal.partial = capture, object()

    def observe(*args, **kwargs):
        raise signal

    context = NS(
        primary=source_primary,
        pending={},
        allowed_codes=frozenset((frame.f_code,)),
        tissue_codes=frozenset((frame.f_code,)),
        tissue_session=object(),
        molecule_session=None,
        claim=object(),
        tissue=NS(CaptureStop=Stop, observe=observe),
        tissue_capture_signal=None,
        observation_error=None,
        capture_error=None,
        capture_errors=(),
        last_capture=None,
        last_raw=None,
        reporting_failure=None,
        frames={},
        observer_namespace={
            "_witness": stage.previous._witness,
            "_record_capture": stage.previous._record_capture,
        },
    )
    if source_failed:
        stage._observe(context, frame, "return", None)
    else:
        with pytest.raises(Stop) as caught:
            stage._observe(context, frame, "return", None)
        assert caught.value is signal
    assert context.primary is source_primary
    assert context.last_raw[0] is frame and context.last_raw[1] is None
    assert context.capture_error is capture and context.observation_error is capture
    assert context.tissue_capture_signal is signal and signal.partial is not None
    if source_failed:
        assert context.primary.__cause__ is cause


def test_source_exception_is_retained_before_pending_ledger_capture_failure():
    frame, primary = sys._getframe(), RuntimeError("original source exception")
    cause, capture = LookupError("cause"), OSError("pending ledger refusal")
    primary.__cause__ = cause

    class Ledger(dict):
        def __setitem__(self, key, value):
            raise capture

    row = dict(frame=frame, globals=frame.f_globals, returned=False)
    context = NS(
        primary=None,
        pending=Ledger(),
        tissue_session=None,
        molecule_session=None,
        frames={id(frame): row},
        capture_error=None,
        capture_errors=(),
        last_capture=None,
        last_source_error=None,
        reporting_failure=None,
        observer_namespace={"_record_capture": stage.previous._record_capture},
    )
    stage._observe(context, frame, "exception", (type(primary), primary, None))
    assert context.last_source_error == (frame, primary)
    assert context.primary is primary and context.primary.__cause__ is cause
    assert context.capture_error is capture and not context.pending


@pytest.mark.parametrize("slot", stage.TISSUE_BACK_REFERENCE_SLOTS)
def test_tissue_interface_uses_existing_exact_bytes_recipe_without_mutual_hash_cycle(
    monkeypatch, slot
):
    from cells.processes import betse_native_init_tissue_dynamics as tissue
    from cells.processes import betse_native_world_phase_construction as binder

    monkeypatch.setattr(stage.previous.previous.previous, "_ready", lambda: binder)
    raw = Path(tissue.__file__).read_bytes()
    joined = b"COMPLETION_SOURCE_SHA256 = COMPLETION_REVIEW_SHA256 = None"
    if joined in raw:
        # Explicit future declaration shape only; the real peer source is NOT
        # changed/adopted, and the current joined declaration refuses binding.
        with pytest.raises(ValueError, match="top-level"):
            stage._tissue_binding(raw)
        raw = raw.replace(
            joined, b"COMPLETION_SOURCE_SHA256 = None\nCOMPLETION_REVIEW_SHA256 = None"
        )
    identity, before = stage._tissue_binding(raw)
    old = slot.encode() + b" = None"
    assert raw.count(old) == 1
    changed = raw.replace(old, slot.encode() + b" = '" + b"0" * 64 + b"'")
    after_identity, after = stage._tissue_binding(changed)
    assert identity == after_identity and dict(before)[slot] is None
    assert dict(after)[slot] == "0" * 64
    assert stage._tissue_binding(raw + b"\n# other-byte drift\n")[0] != identity


@pytest.mark.parametrize("drift", ["source", "review", "order", "missing", "unreviewed"])
def test_tissue_backrefs_require_actual_completion_bytes_and_explicit_review(monkeypatch, drift):
    monkeypatch.setattr(stage.previous, "COMPLETION_REVIEW_SHA256", "1" * 64)
    original = (
        ("COMPLETION_SOURCE_SHA256", hashlib.sha256(Path(stage.__file__).read_bytes()).hexdigest()),
        ("COMPLETION_REVIEW_SHA256", "1" * 64),
    )
    assert stage._check_tissue_backrefs(original) is None
    if drift == "source":
        changed = ((original[0][0], "0" * 64), original[1])
    elif drift == "review":
        changed = (original[0], (original[1][0], "0" * 64))
    elif drift == "order":
        changed = tuple(reversed(original))
    elif drift == "missing":
        changed = original[:1]
    else:
        monkeypatch.setattr(stage.previous, "COMPLETION_REVIEW_SHA256", None)
        changed = (original[0], (original[1][0], None))
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._check_tissue_backrefs(changed)
    assert caught.value.stage == "tissue_source"
