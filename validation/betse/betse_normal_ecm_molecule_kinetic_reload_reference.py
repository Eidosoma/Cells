"""Held independent original-source reload on captured actual retained data.

Neither supplied dictionaries nor an equal cache admit an INIT parent. The new
runtime observer captures the complete supported data graph at the existing
warm boundary, including aliases/layout/profile/configuration. Old conditional
packets alone lack this authority and refuse. No five-path producer is edited.
"""

import ast
import hashlib
import os
import struct
import sys
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_formatter as formatter_owner
from cells.processes import betse_normal_ecm_molecule_kinetic_reload as kinetics
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_formatter as formatter_source
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_reference_native as native
from validation.betse import betse_normal_ecm_molecule_spatial_event_reference as retention
from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

OWNED = (
    "validation/betse/betse_normal_ecm_molecule_kinetic_reload_reference.py",
    "validation/betse/betse_normal_ecm_molecule_kinetic_reload_reference_native.py",
    "tests/unit/test_betse_normal_ecm_molecule_kinetic_reload_reference.py",
)
RELEASES = preparation.RELEASES
require = native.require
FORMATTER_PINS = {
    formatter_owner.__name__: "1834d16378631b56aebc579cd6227fd6905827662eece8da770b76c4b3ae5332",
    formatter_owner.source.__name__: (
        "fd3ef2720b31746665a8fa1eee2cff9a21fd8709ae95ce0b00c0a08296116678"
    ),
    formatter_source.__name__: "830869640fc5c27652b6a3791678890393b7958157eb89394e639bfd82ec21c7",
}
EXECUTABLE_CODE_FIELDS = (
    "co_argcount",
    "co_posonlyargcount",
    "co_kwonlyargcount",
    "co_nlocals",
    "co_stacksize",
    "co_flags",
    "co_code",
    "co_consts",
    "co_names",
    "co_varnames",
    "co_filename",
    "co_name",
    "co_qualname",
    "co_firstlineno",
    "co_linetable",
    "co_exceptiontable",
    "co_freevars",
    "co_cellvars",
)


def executable_constant_key(value, depth=0):
    """Closed typed code constants, including binary64 bits and nested code.

    Python equality merges int/float/complex constants and opposite zero signs.
    This key never invokes arbitrary equality, code bodies or constructors.
    Unsupported constant objects and excessive nesting refuse explicitly.
    """
    require(depth <= 64, "Original formatter executable constant nesting bound")
    kind = type(value)
    if any(kind is allowed for allowed in (type(None), bool, int, str, bytes, type(Ellipsis))):
        return kind, value
    if kind is float:
        return kind, struct.pack("<d", value)
    if kind is complex:
        return kind, struct.pack("<dd", value.real, value.imag)
    if kind is tuple or kind is frozenset:
        keys = (executable_constant_key(item, depth + 1) for item in value)
        return kind, tuple(keys) if kind is tuple else frozenset(keys)
    if kind is CodeType:
        return kind, tuple(
            (name, executable_constant_key(getattr(value, name), depth + 1))
            for name in EXECUTABLE_CODE_FIELDS
        )
    raise ValueError("Unsupported original formatter executable constant category")


def formatter_correspondence(root=native.ROOT):
    """Bind canonical original AST and actual reviewed helper/cache identities.

    Neither matching text nor a copied function/receipt supplies this source
    authority. No formatter or original source body executes during this check.
    """
    for module in (formatter_owner, formatter_owner.source, formatter_source):
        require(
            snapshot.digest(module.__file__) == FORMATTER_PINS[module.__name__],
            "Changed reviewed F1 formatter binding source: " + module.__name__,
        )
    helper = formatter_owner.check_helper()
    methods = formatter_owner.originals()
    for method, expected in zip(methods, formatter_owner._FUNCTION_BUILTINS, strict=True):
        require(
            method.__globals__["tex_val"] is helper
            and method.__builtins__ is expected
            and formatter_owner._builtin_dictionary(method.__globals__) is expected,
            "Foreign formatter consumer helper/cached-builtins association",
        )
    plan = formatter_source.source_plan(Path(root) / "science/chemistry/networks.py")
    require(
        plan["entire_executable_function_AST_equal"] is True
        and plan["live_bindings_installed"] is True,
        "Canonical original/current native formatter correspondence required",
    )
    return dict(
        original=plan["original"],
        adopted=helper.__module__ + "." + helper.__qualname__,
        reviewed_formatter_source_sha256=FORMATTER_PINS.copy(),
        whole_executable_function_AST_equal=True,
        transitive_source_equal=True,
        scope="formatter source/dependencies only; no numerical/reference or parent admission",
        actual_helper_identity_and_cached_builtins_checked=True,
        actual_consumer_cached_builtin_association_checked=True,
        method_association=plan["actual_method_association"],
        source_declarations=plan["source_declarations"],
        evaluated=False,
        affected_fields=(
            "complete cached gad_tex_vars/reaction/transport LaTeX fields; "
            "no exclusion or normalization"
        ),
    )


def check_original_formatter(api, expected, root=native.ROOT):
    """Check a fresh original namespace without calling its formatter.

    expected is the actual function retained immediately after the trusted
    original builder returns, not a deserialized identity or caller receipt.
    """
    helper = formatter_owner.check_helper()
    actual = api.namespace.get("tex_val")
    require(
        actual is expected
        and type(actual) is FunctionType
        and actual.__globals__ is api.namespace
        and actual.__code__.co_filename == native.PREFIX + "tex_val>"
        and actual.__name__ == actual.__qualname__ == "tex_val"
        and actual.__closure__ is None
        and actual.__defaults__ is None
        and actual.__kwdefaults__ is None
        and actual.__annotations__ == {},
        "Foreign/equal-copied original formatter function/namespace",
    )
    require(
        actual.__builtins__ is helper.__builtins__
        and formatter_owner._builtin_dictionary(api.namespace) is actual.__builtins__,
        "Original formatter cached builtins/current namespace mismatch",
    )
    require(
        all(
            (api.namespace[name] if name in api.namespace else actual.__builtins__.get(name))
            is original
            for name, original in formatter_owner._BUILTINS.items()
        ),
        "Original formatter global builtin lookup differs from canonical source",
    )
    # Compilers may emit position-dependent NOP/jump layouts. Compare the
    # original function against its pinned original AST/positions; adopted
    # helper AST correspondence is checked separately, without ignoring ops.
    _, nodes = native.source_plan(root)
    node = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == "tex_val")
    compiled = compile(
        ast.Module(body=[node], type_ignores=[]),
        native.PREFIX + "tex_val>",
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    canonical = next(value for value in compiled.co_consts if type(value) is CodeType)
    code = actual.__code__
    require(
        all(
            getattr(code, n) == getattr(canonical, n)
            for n in (
                "co_code",
                "co_names",
                "co_varnames",
                "co_argcount",
                "co_posonlyargcount",
                "co_kwonlyargcount",
                "co_freevars",
                "co_cellvars",
                "co_flags",
                "co_nlocals",
                "co_stacksize",
                "co_exceptiontable",
            )
        )
        and executable_constant_key(code.co_consts) == executable_constant_key(canonical.co_consts),
        "Original formatter complete executable code differs from canonical source",
    )
    require(
        api.namespace.get("np") is formatter_owner.source.np
        and api.namespace.get("math") is formatter_owner.source.math,
        "Original formatter NumPy/math namespace association differs",
    )
    return dict(
        actual_original_function_cache_and_dependencies_bound=True,
        actual_global_builtin_lookups_bound=tuple(formatter_owner._BUILTINS),
        executable_constants_type_nesting_and_binary64_bits_bound=True,
        evaluated=False,
        pinned_original_executable_code_bound=True,
        adopted_correspondence_uses_AST_without_docstrings_or_positions=True,
    )


def source_plan(root=native.ROOT):
    original, _ = native.source_plan(root)
    adopted = preparation.source_plan(Path(root) / "science/chemistry")
    return dict(
        original=original,
        adopted_method_correspondence=adopted,
        formatter_correspondence=formatter_correspondence(root),
        required_authorities=(
            "actual exhausted INIT binding/run with exact expected identities",
            "current reviewed producer and actual warm runtime roots/profile/alias/layout capture",
        ),
        compiled_or_executed=False,
        scientific_admission=False,
    )


def _nested(function):
    pending, result = [function.__code__], set()
    while pending:
        code = pending.pop()
        result.add(code)
        pending.extend(c for c in code.co_consts if type(c) is CodeType)
    return result


def runtime_roots(ctx):
    """All named roots and every supported instance field, with shared links."""
    return dict(
        sim=ctx.sim,
        cells=ctx.cells,
        p=ctx.p,
        phase=ctx.phase,
        raw=ctx.raw,
        ion_ids=ctx.ion_ids,
        enabled=ctx.enabled,
        definitions={r: ctx.views[r].definition for r in kinetics.ROLES},
        catalogs={r: ctx.views[r].catalog for r in kinetics.ROLES},
    )


def runtime_contracts(ctx):
    """Inspect existing source-backed closures; never invoke a getter/callback."""
    source, qualified = lifecycle.setup.source, lifecycle.catalog
    api = source.science_general()
    types = {value: name for name, value in api.items() if isinstance(value, type)}
    types.update(
        {
            SimpleNamespace: "record",
            lifecycle.setup.FixedPickerOutputs: "record",
            source.MasterOfMolecules: "MasterOfMolecules",
            source.MasterOfGenes: "MasterOfGenes",
            qualified.MasterOfNetworks: "MasterOfNetworks",
        }
    )
    types.update({value: name for name, value in qualified.catalog.CLASSES.items()})
    # No arbitrary function registry is supplied by a caller/archive.
    functions, aliases = {}, {}
    for role in kinetics.ROLES:
        view = ctx.views[role]
        require(
            view.sim is ctx.sim
            and view.cells is ctx.cells
            and view.p is ctx.p
            and view.phase is ctx.phase,
            "Foreign retained view/root association",
        )
    get_ion = ctx.sim.get_ion
    getter_codes = _nested(qualified.base.augment)
    require(
        type(get_ion) is FunctionType
        and get_ion.__code__ in getter_codes
        and get_ion.__globals__ is vars(qualified.base)
        and get_ion.__code__.co_freevars == ("ion_ids",)
        and get_ion.__closure__[0].cell_contents is ctx.ion_ids
        and get_ion.__defaults__ is None
        and get_ion.__kwdefaults__ is None,
        "Missing actual ion-axis lookup callback authority",
    )
    functions[id(get_ion)] = dict(kind="get_ion", ion_ids=ctx.ion_ids)
    observer_codes = _nested(source.install_channel_observer_general) | _nested(
        qualified.install_channel_observer
    )
    for name, value in vars(ctx.p).items():
        if not name.startswith("_") or type(value) is not FunctionType:
            continue
        require(
            name == "_catalog_observe"
            and value.__code__ in observer_codes
            and (value.__globals__ is vars(source) or value.__globals__ is vars(qualified)),
            "Missing source authority for private parameter callback: " + name,
        )
        closure = dict(
            zip(
                value.__code__.co_freevars,
                (c.cell_contents for c in value.__closure__ or ()),
                strict=True,
            )
        )
        require(
            any(closure.get("ctx") is v for v in ctx.views.values()),
            "Foreign observational callback owner",
        )
        functions[id(value)] = dict(
            kind="observer",
            module=value.__module__,
            bytecode_sha256=hashlib.sha256(value.__code__.co_code).hexdigest(),
            scope="explicit non-scientific capture callback; never replayed",
        )
    for role in kinetics.ROLES:
        obj = getattr(ctx.sim, role, None)
        require((obj is not None) is ctx.enabled[role], "Missing/latent warm owner")
        if obj is None:
            continue
        core = obj.core
        allowed_codes = _nested(
            source.restore_general if role == "molecules" else qualified.restore
        )
        for field, attr in (
            ("cell_concs", "cc_cells"),
            ("mem_concs", "cc_at_mem"),
            ("env_concs", "cc_env"),
            ("bound_concs", "c_env_bound"),
        ):
            actual = getattr(core, field)
            require(
                type(actual) is qualified.base.DynamicValueDict,
                "Missing exact retained dynamic alias owner",
            )
            mapping = actual._key_to_dynamic_value
            names = [*ctx.ion_ids, *core.molecules]
            require(list(mapping) == names, "Changed actual dynamic alias axis/order")
            entries = []
            for name in names:
                pair = mapping[name]
                require(
                    type(pair) is qualified.base.DynamicValue,
                    "Missing exact retained dynamic value owner",
                )
                get, put = pair.get_value, pair.set_value
                ionic = name in ctx.ion_ids
                target = ctx.sim if ionic else core.molecules[name]
                storage = (
                    attr
                    if ionic
                    else {
                        "cell_concs": "c_cells",
                        "mem_concs": "cc_at_mem",
                        "env_concs": "c_env",
                        "bound_concs": "c_bound",
                    }[field]
                )
                offset = ctx.ion_ids.index(name) if ionic else None
                expected = (offset if ionic else name, storage)
                for function, arity in ((get, 2), (put, 3)):
                    require(
                        type(function) is FunctionType
                        and function.__code__ in allowed_codes
                        and function.__globals__
                        is vars(source if role == "molecules" else qualified)
                        and function.__code__.co_argcount == arity
                        and function.__kwdefaults__ is None
                        and kinetics.same(function.__defaults__, expected),
                        "Missing actual dynamic getter/setter source association",
                    )
                    closed = dict(
                        zip(
                            function.__code__.co_freevars,
                            (c.cell_contents for c in function.__closure__ or ()),
                            strict=True,
                        )
                    )
                    require(
                        (ionic and closed.get("ctx") is ctx.views[role])
                        or (not ionic and closed.get("net") is core),
                        "Foreign retained dynamic alias backing owner",
                    )
                entries.append((name, target, storage, offset))
            aliases[id(actual)] = ("DynamicValueDict", entries)
    return dict(types=types, aliases=aliases, functions=functions)


class RuntimeCapture:
    """Observe existing warm execution; original source errors stay primary."""

    def __init__(self, binding, completed, api):
        self.binding, self.completed, self.api = binding, completed, api
        self.code = lifecycle.setup.source.initialize_both.__code__
        self.caller = lifecycle.owners.initialize.__code__
        self.original, self.frame, self.ctx = None, None, None
        self.before = self.after = self.reference_roots = None
        self.reference_contracts, self.errors = None, []
        self.entries, self.exits, self.marker = 0, 0, None
        self.restored = self.normal_exit = False
        self.graph_work = []

    def profile(self, frame, event, arg):
        try:
            self.observe(frame, event, arg)
        except BaseException as error:
            self.errors.append(
                dict(
                    stage=event,
                    type=type(error).__name__,
                    message=str(error),
                    partial=getattr(error, "partial", None),
                )
            )
        if self.original is not None:
            self.original(frame, event, arg)

    def observe(self, frame, event, arg):
        if frame.f_code is not self.code:
            return
        if event == "call":
            self.entries += 1
            require(
                self.entries == 1 and frame.f_back.f_code is self.caller,
                "Duplicate or foreign warm boundary caller",
            )
            ctx = frame.f_back.f_locals["ctx"]
            outer = frame.f_back.f_back
            actual = outer.f_locals.get("completed")
            require(
                outer.f_code is lifecycle.setup.reinitialize_owners.__code__
                and outer.f_locals["source_binding"] is self.binding
                and type(actual) is lifecycle.CompleteInit
                and actual.identity == self.completed.identity
                and actual.binding is self.completed.binding
                and actual.parent is self.completed.parent,
                "Warm capture lacks original binding/complete-INIT association",
            )
            require(
                frame.f_locals["phase"] is ctx.phase
                and frame.f_locals["p"] is ctx.p
                and ctx.phase.sim is ctx.sim
                and ctx.phase.cells is ctx.cells
                and ctx.phase.p is ctx.p
                and ctx.phase.kind == "SIM"
                and ctx.p._run_sim is True,
                "Foreign runtime phase/root association",
            )
            self.frame, self.ctx = frame, ctx
            work = dict(operation="capture-and-copy-actual-runtime-roots", status="attempted")
            self.graph_work.append(work)
            graph = native.Graph(api=self.api, **runtime_contracts(ctx))
            self.before, self.reference_roots = graph.capture(runtime_roots(ctx))
            work.update(
                status="returned",
                nodes=len(graph.nodes),
                array_bytes=graph.array_bytes,
                array_headers=len(graph.arrays),
                storage_nodes=graph.storage_nodes,
                array_byte_scope=(
                    "unique retained storage; view headers do not allocate new payloads"
                ),
                dynamic_alias_objects=len(graph.cloned_aliases),
            )
            self.reference_contracts = dict(
                types={cls: name for name, cls in self.api.classes.items()}
                | {SimpleNamespace: "record"},
                aliases=graph.cloned_aliases,
                functions=graph.cloned_functions,
            )
            copied, _ = native.Graph(**self.reference_contracts).capture(self.reference_roots)
            native.compare_graphs(self.before, copied)
            self.graph_work.append(
                dict(
                    operation="verify-exact-reference-clone",
                    status="returned",
                    nodes=len(copied["nodes"]),
                )
            )
        elif event == "return":
            self.exits += 1
            require(frame is self.frame and self.ctx is not None, "Missing matching warm entry")
            work = dict(operation="capture-actual-warm-return-or-unwind-roots", status="attempted")
            self.graph_work.append(work)
            self.after, _ = native.Graph(**runtime_contracts(self.ctx)).capture(
                runtime_roots(self.ctx)
            )
            work.update(status="returned", nodes=len(self.after["nodes"]))

    def stage(self, name, value):
        if name == "kinetic_reload_complete":
            try:
                require(
                    self.marker is None
                    and value["source_binding_identity"] == self.binding.identity
                    and value["source_complete_INIT_identity"] == self.completed.identity
                    and value["capture_complete"] is True
                    and value["normal_exit"] is True,
                    "Foreign or duplicate actual warm completion marker",
                )
            except Exception as error:
                self.errors.append(
                    dict(
                        stage="warm_completion_marker",
                        type=type(error).__name__,
                        message=str(error),
                    )
                )
                raise
            self.marker = value["identity"]

    def __enter__(self):
        self.original = sys.getprofile()
        sys.setprofile(self.profile)
        return self

    def __exit__(self, kind, error, traceback):
        intact = getattr(sys.getprofile(), "__self__", None) is self
        sys.setprofile(self.original)
        self.restored = sys.getprofile() is self.original
        self.normal_exit = kind is None
        if not intact or not self.restored:
            self.errors.append(
                dict(stage="profile_restoration", intact=intact, restored=self.restored)
            )
        return False

    def data(self):
        return dict(
            before=self.before,
            after=self.after,
            capture_errors=self.errors,
            entries=self.entries,
            return_or_unwind_events=self.exits,
            completion_marker=self.marker,
            profile_restored=self.restored,
            outer_normal_exit=self.normal_exit,
            source_binding=self.binding.identity,
            source_complete_INIT=self.completed.identity,
            graph_work=self.graph_work,
        )

    def finish(self):
        require(
            self.normal_exit
            and self.restored
            and not self.errors
            and self.entries == self.exits == 1
            and self.marker is not None
            and self.before is not None
            and self.after is not None,
            "Missing/incomplete actual owner graph/profile/layout authority; no packet hydration",
        )
        return self.data()


class ReferenceCalls(Calls):
    @staticmethod
    def category(module, name):
        if module == "original_betse_kinetic_reload" or module.startswith("pinned_catalog_"):
            return "original_source_boundary"
        return Calls.category(module, name)


def compare_retained(original, candidate, *, association):
    """Compare complete recorded data/aliases/layout/config and source outcome."""
    required = {"binding", "complete_INIT", "INIT_parent", "kinetic_declaration"}
    require(
        type(association) is dict
        and set(association) == required
        and all(type(v) is str and v for v in association.values()),
        "Exact retained comparison association required",
    )
    for leg in (original, candidate):
        require(
            leg["association"] == association
            and leg["capture_complete"] is True
            and leg["capture_errors"] == []
            and leg["status"] in ("source_completed", "source_failed"),
            "Foreign/incomplete retained source leg",
        )
    require(original["status"] == candidate["status"], "Original/candidate source outcome differs")
    native.compare_graphs(original["before"], candidate["before"])
    native.compare_graphs(original["after"], candidate["after"])
    if original["status"] == "source_failed":
        require(
            original["failure"] == candidate["failure"],
            "Original/candidate failure stage/type/message differs",
        )
    return dict(
        status="complete_data_match"
        if original["status"] == "source_completed"
        else "matching_failed_prefix",
        aliases_values_layout_config_equal=True,
        full_native_admission=False,
        independent_biological_cases=0,
        new_tolerance=None,
    )


def actual_comparison(
    directory,
    *,
    changes,
    provenance,
    init_binding=None,
    init_parent=None,
    expected_binding_identity=None,
    expected_parent_identity=None,
    expected_producer=None,
    root=native.ROOT,
):
    """Gated actual preparation/reference; missing genuine authority refuses."""
    require(
        all(os.environ.get(n) == "1" for n in RELEASES),
        "Original kinetic reference remains held behind both releases",
    )
    require(sys.flags.optimize == 0, "Assertion-enabled ownership verification required")
    directory = Path(directory).resolve()
    require(
        not directory.is_relative_to(Path(root).resolve())
        and not directory.is_relative_to(Path(__file__).resolve().parents[2]),
        "Reference output may not mutate original or checkout/snapshot source",
    )
    directory.mkdir(parents=True, exist_ok=False)
    attempts, values, accounting = [], {}, {}
    calls = stream = capture = api = original_formatter = None

    def take(name, operation, **readers):
        if calls is not None:
            calls.stage = name
        return retention._take(
            directory,
            name,
            operation,
            attempts=attempts,
            work="metadata_or_actual_reference_work_never_a_biological_case",
            readers={
                k: lambda reader=reader: lifecycle.ions.data(reader())
                for k, reader in readers.items()
            },
        )

    try:
        take(
            "required-genuine-INIT",
            lambda: preparation.preflight(
                init_binding,
                init_parent,
                expected_binding_identity=expected_binding_identity,
                expected_parent_identity=expected_parent_identity,
            ),
            init_binding=lambda: init_binding,
            init_parent=lambda: init_parent,
            changes=lambda: changes,
        )
        take("bounded-scalar-request", lambda: kinetics.validate_changes(changes))
        require(
            type(provenance) is str and bool(provenance.strip()),
            "Declared reference provenance required",
        )
        require(
            type(expected_producer) is dict and checkpoint.producer_identity() == expected_producer,
            "Missing current reviewed source/runtime producer",
        )
        take("source-plan", lambda: source_plan(root))

        def compile_source():
            nonlocal api, original_formatter
            api = native.compile_original(root)
            original_formatter = api.namespace["tex_val"]
            return dict(
                api.plan, formatter_binding=check_original_formatter(api, original_formatter, root)
            )

        take("original-source-compilation", compile_source)
        stream = (directory / "invocations.jsonl").open("x")
        calls = ReferenceCalls(stream)
        calls.start()
        complete = take(
            "actual-complete-INIT", lambda: run.complete_INIT(init_binding, init_parent)
        )
        raw = take(
            "declared-SIM",
            lambda: preparation.declaration(complete.complete_init, changes, provenance=provenance),
        )
        component = take("source-binding", lambda: lifecycle.bind(raw))
        contract = take(
            "run-declaration",
            lambda: preparation.preparation.fixtures.declaration("zero_INIT_calls", component),
        )
        capture = RuntimeCapture(component, complete.complete_init, api)
        values.update(
            init_binding=init_binding,
            init_parent=init_parent,
            complete=complete,
            raw=raw,
            component=component,
            contract=contract,
        )
        with capture:
            binding, parent = take(
                "actual-retained-transition",
                lambda: run.transition(
                    init_binding,
                    init_parent,
                    component,
                    contract,
                    provenance=provenance,
                    observer=capture.stage,
                ),
                inputs=lambda: values,
                actual_capture=capture.data,
            )
        values.update(binding=binding, parent=parent)
        take("complete-candidate-capture", capture.finish, capture=capture.data)
        roots = capture.reference_roots
        take("retained-formatter-source-binding", lambda: formatter_correspondence(root))
        take(
            "original-formatter-namespace-binding",
            lambda: check_original_formatter(api, original_formatter, root),
        )
        source_calls = []
        values["original_source_calls"] = source_calls
        values["original_log_observations"] = api.logs
        original_before, _ = native.Graph(**capture.reference_contracts).capture(roots)
        native.compare_graphs(capture.before, original_before)
        require(
            roots["phase"].sim is roots["sim"]
            and roots["phase"].p is roots["p"]
            and roots["phase"].cells is roots["cells"],
            "Reference clone lost phase aliases",
        )
        for role in kinetics.ROLES:
            if roots["enabled"][role]:
                source_calls.append(dict(role=role, status="attempted", independent_cases=0))
                take(
                    "original-" + role + "-reinitialize",
                    lambda role=role: getattr(roots["sim"], role).reinitialize(roots["phase"]),
                    before=lambda: original_before,
                    partial=lambda: native.Graph(**capture.reference_contracts).capture(roots)[0],
                )
                source_calls[-1]["status"] = "returned"
        original_after, _ = native.Graph(**capture.reference_contracts).capture(roots)
        take(
            "original-formatter-namespace-after",
            lambda: check_original_formatter(api, original_formatter, root),
        )
        association = dict(
            binding=component.identity,
            complete_INIT=complete.complete_init.identity,
            INIT_parent=init_parent.active.identity,
            kinetic_declaration=lifecycle.ions.digest(kinetics.selection(component.inputs)),
        )
        original = dict(
            association=association,
            status="source_completed",
            capture_complete=True,
            capture_errors=[],
            before=original_before,
            after=original_after,
        )
        candidate = dict(
            association=association,
            status="source_completed",
            capture_complete=True,
            capture_errors=[],
            before=capture.before,
            after=capture.after,
        )
        values.update(original=original, candidate=candidate, original_source_calls=source_calls)
        result = take(
            "complete-retained-data-comparison",
            lambda: compare_retained(original, candidate, association=association),
            original=lambda: original,
            candidate=lambda: candidate,
        )
    except BaseException as error:
        record_failure(
            error,
            stage="original-kinetic-reload-reference",
            readers={
                "available": lambda: values,
                "actual_capture": lambda: None if capture is None else capture.data(),
                "attempts": lambda: attempts,
                "partial": lambda error=error: getattr(error, "partial", None),
                "original_logs": lambda: None if api is None else api.logs,
            },
            retain=lambda p: retention.archives.write_archive(
                directory / "failure", lifecycle.ions.data(p)
            ),
        )
        raise
    finally:
        primary = sys.exception()
        try:
            if calls is not None:
                accounting = calls.stop()
            if stream is not None:
                stream.close()
            snapshot.write_json(
                directory / "attempts.json",
                dict(
                    attempts=attempts,
                    invocations=accounting,
                    independent_biological_cases=0,
                    scope=(
                        "Every actual setup/rebind/verification/reference/helper/clone/nested "
                        "call is work; source compilation is distinct"
                    ),
                ),
            )
        except BaseException as secondary:
            if primary is not None:
                primary.add_note("Reference accounting also failed: " + repr(secondary))
            else:
                raise
    try:
        require(
            accounting.get("profile_intact") and accounting.get("active_invocations") == 0,
            "Incomplete original/candidate invocation accounting",
        )
        snapshot.write_json(
            directory / "result.json",
            dict(
                result,
                source_plan=source_plan(root),
                actual_native_parent_admission=False,
                checkpoint_continuity_admission=False,
                original_source_replay_is_reference_work=True,
            ),
        )
    except BaseException as error:
        record_failure(
            error,
            stage="kinetic-reference-result-publication",
            readers={
                "available": lambda: lifecycle.ions.data(values),
                "attempts": lambda: attempts,
                "accounting": lambda: accounting,
                "result": lambda: result,
            },
            retain=lambda p: retention.archives.write_archive(directory / "publication-failure", p),
        )
        raise
    return result
