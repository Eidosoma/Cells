"""Original channel source and ownership controls; native bodies stay blocked."""

import sys
from abc import ABCMeta
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_molecule_channels as stage
from tests.unit import test_betse_native_init_molecule_wrapper_authority as inherited
from validation.betse import betse_native_init_molecule_channels_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    original = inherited.inherited.inherited.inherited._blocked_generator
    guard = FunctionType(
        original.__code__,
        dict(original.__globals__, stage=NS(_ACTIVE=[], _FAILED=[]), runner=runner),
    )
    generator = guard(request, tmp_path, monkeypatch)
    before, entered, primary = (sys.getprofile(), sys.gettrace()), False, None
    try:
        next(generator)
        entered = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        drain = inherited.inherited.inherited.inherited.cleanup._drain_guard
        FunctionType(
            drain.__code__, dict(drain.__globals__, _write_failure_diagnostics=lambda *args: None)
        )(generator, entered, (), tmp_path, required_hooks=before, primary=primary)


@pytest.fixture
def declarations():
    rows = [
        {
            "name": "Nav",
            "channel class": "Na",
            "channel type": "Nav1p3",
            "apply to": "all",
            "init active": False,
            "max Dm": 2e-14,
        },
        {
            "name": "Kv",
            "channel class": "K",
            "channel type": "Kv1p5",
            "apply to": "all",
            "init active": False,
            "max Dm": 1e-15,
        },
        {
            "name": "K_Leak",
            "channel class": "K",
            "channel type": "KLeak",
            "apply to": "all",
            "init active": True,
            "max Dm": 0.6e-17,
            "channel inhibitors": ["X"],
            "inhibitor Km": [0.05],
            "inhibitor n": [2.0],
            "inhibitor zone": ["cell"],
        },
    ]
    return NS(config={"channels": rows})


def test_original_channel_code_compiles_without_evaluating_any_method():
    for role, name in stage.source.SITES:
        code = stage.source.code(role, name)
        assert code.co_name == name and code.co_qualname == role + "." + name
        assert code.co_filename == str(stage.source.NATIVE / stage.source.SITES[(role, name)])
    assert stage.source.node("KLeak", "_init_state").lineno == 691


@pytest.mark.parametrize("drift", ("none", "family_module", "defaults", "base"))
def test_compiled_unexecuted_source_metadata_binds_factory_modules_headers_and_defaults(
    monkeypatch, drift
):
    """Definition-only acquisition seam: no native import, body, owner or claim."""
    modules, classes = {}, {}
    for role, relative in stage.source.CLASSES.items():
        name = relative[:-3].replace("/", ".")
        if name not in modules:
            modules[name] = ModuleType(name)
            vars(modules[name])["__builtins__"] = __builtins__
            monkeypatch.setitem(sys.modules, name, modules[name])
        namespace = vars(modules[name])
        functions = {}
        for method in stage.source.METHODS.get(role, ()):
            defaults, keywords = stage.source.defaults(role, method)
            function = FunctionType(stage.source.code(role, method), namespace, argdefs=defaults)
            function.__kwdefaults__ = keywords
            functions[method] = function
        base_name = stage.CORE_TYPES.get(role)
        if role in ("VgNaABC", "VgKABC"):
            base_name = "ChannelsABC"
        base = object if base_name is None else classes[base_name]
        cls = (type if role == "Channel" else ABCMeta)(
            role, (base,), dict(functions, __module__=name)
        )
        classes[role] = namespace[role] = cls
    network = modules["betse.science.chemistry.networks"]
    network.vgna, network.vgk = (
        modules["betse.science.channels.vg_na"],
        modules["betse.science.channels.vg_k"],
    )
    if drift == "family_module":
        network.vgk = ModuleType(network.vgk.__name__)
    elif drift == "defaults":
        classes["VgKABC"].init.__defaults__ = (0,)
    elif drift == "base":
        wrong = ABCMeta("KLeak", (object,), {"__module__": "betse.science.channels.vg_k"})
        modules[wrong.__module__].KLeak = wrong
    callbacks = NS(
        _source_function=lambda actual, *args: actual,
        simulator=NS(_chain=lambda actual: (actual,)),
    )
    api = NS(
        previous=NS(
            _constant=stage.wrappers.typed._constant,
            previous=NS(caches=NS(previous=NS(callbacks=callbacks))),
        )
    )
    if drift == "none":
        acquired, functions, exports, entries = stage.actual_functions(api, NS())
        assert all(acquired[name] is cls for name, cls in classes.items())
        assert len(functions) == len(stage.source.SITES) and exports and entries
    else:
        with pytest.raises(ValueError):
            stage.actual_functions(api, NS())


def test_original_default_rows_retain_types_order_activity_and_inhibitor(declarations):
    rows = stage.declarations(declarations)
    assert all(a is b for a, b in zip(rows, declarations.config["channels"], strict=True))
    assert [row["init active"] for row in rows] == [False, False, True]
    assert [(row["channel class"], row["channel type"]) for row in rows] == list(stage.SUPPORTED)
    assert rows[2]["channel inhibitors"] == ["X"] and rows[2]["inhibitor Km"] == [0.05]


@pytest.mark.parametrize("value", (None, []))
def test_declared_zero_channel_control_stays_distinct_from_original_default(value):
    assert stage.declarations(NS(config={"channels": value})) == ()


@pytest.mark.parametrize("drift", ("type", "activity", "express", "target"))
def test_unsupported_authority_refuses_without_rewriting_inputs(declarations, drift):
    rows = declarations.config["channels"]
    if drift == "type":
        rows[2]["channel type"] = "unowned"
    elif drift == "activity":
        rows[2]["init active"] = 1
    elif drift == "express":
        rows[2]["apply to"] = "express"
    else:
        rows[2]["apply to"] = [object()]
    before = [dict(row) for row in rows]
    with pytest.raises(ValueError):
        stage.declarations(declarations)
    assert all(
        tuple(row) == tuple(old) and all(row[key] is old[key] for key in old)
        for row, old in zip(rows, before, strict=True)
    )


def test_target_profile_order_and_duplicates_are_preserved(declarations):
    profiles = ["Spot", "Spot", "Other"]
    declarations.config["channels"][2]["apply to"] = profiles
    assert stage.declarations(declarations)[2]["apply to"] is profiles


def test_native_field_roster_keeps_inactive_core_readonly_and_all_history_stores(
    declarations, monkeypatch
):
    context = declarations
    context.channel_records = [
        dict(channel=NS(init_active=row["init active"]), core=NS(), core_type=row["channel type"])
        for row in stage.declarations(context)
    ]
    monkeypatch.setattr(stage, "_owner", lambda value: None)
    storage = stage.permission_rows(context, "storage")
    assert len(storage) == 3 and all(fields == {"D_time", "flux_time"} for _, fields in storage)
    step = stage.permission_rows(context, "first_step")
    assert len(step) == 4
    assert step[-1][0] is context.channel_records[-1]["core"]
    assert {"modulator", "chan_flux", "DChan", "P", "m", "h"} <= step[-1][1]
    assert not any(
        owner is context.channel_records[0]["core"] or owner is context.channel_records[1]["core"]
        for owner, _ in step
    )


@pytest.mark.parametrize("drift", ("none", "inactive", "vm", "p", "parent"))
def test_actual_profiled_channel_frame_preserves_source_parent_and_active_gate(monkeypatch, drift):
    entered = []

    class Core:
        def run(self, vm, p):
            entered.append(self)

    core, p, vm = Core(), object(), object()
    channel = NS(init_active=drift != "inactive")
    record = dict(channel=channel, core=core, init_returned=True)
    context = NS(channel_records=[record], p=p, sim=NS(vm=vm), functions={})
    monkeypatch.setattr(stage, "_owner", lambda value: None)
    before = sys.getprofile()

    def profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event == "call" and frame.f_code is Core.run.__code__:
            stage.runtime_admit(context, ("VgKABC", "run"), frame, NS())

    def intermediary():
        core.run(vm, p)

    def source_loop():
        chan = channel
        assert chan is record["channel"]
        if drift == "parent":
            intermediary()
        else:
            core.run(object() if drift == "vm" else vm, object() if drift == "p" else p)

    context.functions[("MasterOfNetworks", "run_loop_channels")] = source_loop
    try:
        sys.setprofile(profile)
        if drift == "none":
            source_loop()
            assert entered == [core]
        else:
            with pytest.raises(ValueError):
                source_loop()
            assert not entered
    finally:
        sys.setprofile(before)


@pytest.mark.parametrize(
    "drift", ("none", "omit_state", "wrong_targets", "wrong_q", "duplicate", "unwind")
)
def test_profiled_setup_requires_same_config_target_factory_and_complete_returns(
    monkeypatch, declarations, drift
):
    """Toy bodies exercise the actual frame contract, never native constructors."""
    config = declarations.config["channels"][-1]
    declarations.config["channels"] = [config]
    entered, targets = [], object()
    context = declarations

    class Core:
        def init(self, vm, cells, p, targets=None):
            self.targets = targets
            V = vm
            if drift == "unwind":
                raise LookupError("toy core primary")
            if drift != "omit_state":
                self._init_state(V)
            entered.append("init")

        def _init_state(self, V):
            entered.append("state")

    class Channel:
        def init_channel(self, ion_string, type_string, max_val, phase):
            targets = context.targets
            self.channel_core = Core()
            self.channel_core.init(
                phase.sim.vm,
                phase.cells,
                phase.p,
                targets=object() if drift == "wrong_targets" else targets,
            )
            entered.append("channel")

    channel = Channel()
    channel.channel_class, channel.channel_type = config["channel class"], config["channel type"]
    channel.channelMax, channel.channel_profiles_list = config["max Dm"], config["apply to"]
    channel.init_active = config["init active"]
    context.sim, context.cells, context.p = NS(vm=object()), object(), object()
    context.phase = NS(sim=context.sim, cells=context.cells, p=context.p)
    context.core, context.targets = NS(channels={config["name"]: channel}), targets
    context.channel_records, context.frames, context.objects = [], {}, [("Channel", channel)]
    context.classes = dict(Channel=Channel, KLeak=Core)
    context.initial = NS(
        _normal_return=lambda frame: frame.f_code.co_name != "init" or drift != "unwind"
    )

    def source_reader():
        q = 1 if drift == "wrong_q" else 0
        chan_dic, name, self = config, config["name"], context.core
        assert chan_dic is context.config["channels"][0] and self.channels[name] is channel
        assert q in (0, 1)
        channel.init_channel(
            channel.channel_class, channel.channel_type, channel.channelMax, context.phase
        )
        if drift == "duplicate":
            channel.init_channel(
                channel.channel_class, channel.channel_type, channel.channelMax, context.phase
            )

    context.functions = {
        ("MasterOfNetworks", "read_channels"): source_reader,
        ("Channel", "init_channel"): Channel.init_channel,
        ("VgKABC", "init"): Core.init,
        ("KLeak", "_init_state"): Core._init_state,
    }
    roles = {fn.__code__: role for role, fn in context.functions.items()}
    monkeypatch.setattr(stage, "_owner", lambda value: None)
    prior = sys.getprofile()

    def observe(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        role = roles.get(frame.f_code)
        if role is None:
            return
        if event == "call":
            if role[0] != "MasterOfNetworks":
                assert stage.admit_setup(context, role, frame)
            context.frames[id(frame)] = dict(frame=frame)
        elif event == "return":
            stage.returned_setup(context, frame)

    try:
        sys.setprofile(observe)
        if drift in ("wrong_targets", "wrong_q", "duplicate"):
            with pytest.raises(ValueError):
                source_reader()
        elif drift == "unwind":
            with pytest.raises(LookupError, match="toy core primary"):
                source_reader()
        else:
            source_reader()
    finally:
        sys.setprofile(prior)
    if drift == "none":
        stage.finish_setup(context)
        assert entered == ["state", "init", "channel"]
        record = context.channel_records[0]
        assert record["core"] is channel.channel_core
        assert all(
            record[field] for field in ("channel_returned", "init_returned", "state_returned")
        )
    elif drift == "duplicate":
        # The local driver kept the first completed prefix; its enclosing
        # molecular observer owns the sticky failed-attempt disposition.
        assert len(context.channel_records) == 1
        assert entered == ["state", "init", "channel"]
    else:
        with pytest.raises(ValueError):
            stage.finish_setup(context)
        if drift in ("wrong_targets", "wrong_q"):
            assert not entered


@pytest.mark.parametrize("drift", ("none", "foreign_parent", "foreign_voltage", "foreign_p"))
def test_profiled_inner_channel_runtime_requires_exact_inherited_dispatch(monkeypatch, drift):
    entered, p, V = [], object(), object()

    class Core:
        def run(self, V, p):
            if drift == "foreign_parent":
                foreign(self, V)
            else:
                self._calculate_state(object() if drift == "foreign_voltage" else V)
            self._implement_state(V, object() if drift == "foreign_p" else p)

        def _calculate_state(self, V):
            entered.append("calculate")

        def _implement_state(self, V, p):
            entered.append("implement")

    def foreign(self, V):
        self._calculate_state(V)

    core = Core()
    context = NS(
        p=p,
        channel_records=[
            dict(channel=NS(init_active=True), core=core, init_returned=True, core_type="KLeak")
        ],
        frames={},
        functions={("VgKABC", "run"): Core.run},
    )
    monkeypatch.setattr(stage, "_owner", lambda value: None)
    prior = sys.getprofile()
    roles = {
        Core._calculate_state.__code__: ("KLeak", "_calculate_state"),
        Core._implement_state.__code__: ("VgKABC", "_implement_state"),
    }

    def observe(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code is Core.run.__code__:
            context.frames[id(frame)] = dict(frame=frame)
        if event == "call" and frame.f_code in roles:
            stage.runtime_admit(context, roles[frame.f_code], frame, NS())

    try:
        sys.setprofile(observe)
        if drift == "none":
            core.run(V, p)
            assert entered == ["calculate", "implement"]
        else:
            with pytest.raises(ValueError):
                core.run(V, p)
            assert entered == (["calculate"] if drift == "foreign_p" else [])
    finally:
        sys.setprofile(prior)


@pytest.mark.parametrize("drift", ("none", "target_copy", "callee_target", "callee_vm", "callee_V"))
def test_retained_target_and_suspended_voltage_associations_refuse_equal_replacements(
    declarations, drift
):
    """Metadata-only local record probe; no source class or owner is issued."""
    config = declarations.config["channels"][-1]
    targets, vm, voltage = [1, 1, 0], object(), object()
    core = NS(targets=targets)
    channel = NS(
        channel_core=core,
        channel_class=config["channel class"],
        channel_type=config["channel type"],
        init_active=config["init active"],
        channel_profiles_list=config["apply to"],
    )
    init = NS(f_locals=dict(targets=targets, vm=vm))
    state = NS(f_locals=dict(V=voltage))
    record = dict(
        channel=channel,
        core=core,
        config=config,
        core_type="KLeak",
        targets=targets,
        vm=vm,
        initial_voltage=voltage,
        init_frame=init,
        state_frame=state,
        init_returned=True,
    )
    declarations.channel_records = [record]
    declarations.classes = dict(KLeak=type(core))
    declarations.frames = {id(frame): dict(frame=frame, returned=False) for frame in (init, state)}
    stage.validate_associations(declarations)
    if drift == "target_copy":
        core.targets = list(targets)
    elif drift == "callee_target":
        init.f_locals["targets"] = list(targets)
    elif drift == "callee_vm":
        init.f_locals["vm"] = object()
    elif drift == "callee_V":
        state.f_locals["V"] = object()
    if drift == "none":
        stage.validate_associations(declarations)
        assert core.targets is targets and core.targets == [1, 1, 0]
    else:
        with pytest.raises(ValueError):
            stage.validate_associations(declarations)
