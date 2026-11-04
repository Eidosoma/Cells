"""Actual original default channel objects attached to a molecular session.

Only pinned native class/method references and observed live source ancestry
are transported. This module contains no channel/flux/gating equations.
"""

import hashlib
import sys
from abc import ABCMeta
from types import ModuleType

from cells.processes import betse_native_init_molecule_channels_source as source
from cells.processes import betse_native_init_molecule_wrapper_authority as wrappers

NETWORK_MODULE = "cells.processes.betse_native_init_molecule_network"
SUPPORTED = source.DEFAULT_TYPES
CORE_TYPES = dict(Nav1p3="VgNaABC", Kv1p5="VgKABC", KLeak="VgKABC")


def source_plan():
    return dict(
        original=source.plan(),
        supported=SUPPORTED,
        original_configuration_rewritten_or_native_constructor_released=False,
        inactive_INIT_channels_constructed_but_not_run=True,
        actual_KLeak_and_ionic_membrane_store_ownership_required=True,
    )


def declarations(context):
    """Inspect the retained actual rows; neither fill defaults nor edit inputs."""
    rows = context.config.get("channels")
    if rows is None:
        return ()
    if type(rows) is not list:
        raise ValueError("Actual original channel declaration list required")
    for row in rows:
        if type(row) is not dict or (row["channel class"], row["channel type"]) not in SUPPORTED:
            raise ValueError("Only original Nav1p3/Kv1p5/KLeak channel families are owned")
        if type(row["name"]) is not str:
            raise ValueError("This channel domain requires literal original string names")
        if type(row.get("init active", True)) is not bool:
            raise ValueError("Exact original INIT channel activity boolean required")
        profiles = row["apply to"]
        if profiles == "express":
            raise ValueError("Expression-file channel target authority remains unavailable")
        if profiles not in (None, "all") and (
            type(profiles) is not list or any(type(name) is not str for name in profiles)
        ):
            raise ValueError("Original all/profile target declarations required")
    return tuple(rows)


def actual_functions(api, completion):
    """Acquire original exports only; never call any factory or native method."""
    classes, functions, exports, entries = {}, {}, [], []
    callbacks = api.previous.previous.caches.previous.callbacks
    for relative, pin in source.PINS.items():
        path = source.NATIVE / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Original channel source changed")
    for role, relative in source.CLASSES.items():
        module = sys.modules.get(relative[:-3].replace("/", "."))
        if type(module) is not ModuleType:
            raise ValueError("Actual native channel module must already be imported")
        cls = vars(module).get(role)
        expected_meta = type if role == "Channel" else ABCMeta
        if (
            type(cls) is not expected_meta
            or cls.__module__ != module.__name__
            or cls.__name__ != role
        ):
            raise ValueError("Actual original channel class export required: " + role)
        classes[role] = cls
        exports.append((module, role, cls))
    if (
        classes["ChannelsABC"].__bases__ != (object,)
        or classes["VgNaABC"].__bases__ != (classes["ChannelsABC"],)
        or classes["VgKABC"].__bases__ != (classes["ChannelsABC"],)
        or any(classes[name].__bases__ != (classes[base],) for name, base in CORE_TYPES.items())
    ):
        raise ValueError("Exact original channel base-class dispatch required")
    constructor_globals = vars(sys.modules["betse.science.chemistry.networks"])
    for alias, name in (("vgna", "Nav1p3"), ("vgk", "Kv1p5")):
        module = sys.modules[classes[name].__module__]
        if constructor_globals.get(alias) is not module:
            raise ValueError("Actual original channel family module lookup required: " + alias)
    for (role, name), relative in source.SITES.items():
        actual = vars(classes[role])[name]
        original = callbacks._source_function(actual, relative, name, role)
        if api.previous._constant(original.__code__) != api.previous._constant(
            source.code(role, name)
        ):
            raise ValueError("Exact original channel method body required")
        positional, keywords = source.defaults(role, name)
        if api.previous._constant(original.__defaults__) != api.previous._constant(
            positional
        ) or api.previous._constant(original.__kwdefaults__) != api.previous._constant(keywords):
            raise ValueError("Exact original channel method defaults required")
        if actual is not original:
            wrappers.validate(actual, original, owner=classes[role], attribute=name)
        functions[(role, name)] = original
        entries.extend(callbacks.simulator._chain(actual))
    return classes, functions, tuple(exports), tuple(entries)


def _owner(context):
    module = sys.modules.get(NETWORK_MODULE)
    if (
        type(module) is not ModuleType
        or module._SESSIONS.get(context.session) is not context
        or module._CLAIMED.get(context.claim) is not context
        or context.api._CLAIMS.get(context.claim) is not context.completion
    ):
        raise ValueError("Actual issued original molecular session required")
    return module


def _parent(context, frame, key):
    function = context.functions[key]
    parent = frame.f_back
    row = context.frames.get(id(parent))
    if (
        row is None
        or row["frame"] is not parent
        or parent.f_code is not function.__code__
        or parent.f_globals is not function.__globals__
    ):
        raise ValueError("Actual original channel source-call parent required")
    return parent


def admit_setup(context, role, frame):
    """Called from the molecular observer before the original channel body."""
    _owner(context)
    name, method = role
    actual = frame.f_locals.get("self")
    if name == "Channel" and method == "init_channel":
        parent = _parent(context, frame, ("MasterOfNetworks", "read_channels"))
        config = parent.f_locals.get("chan_dic")
        if not any(row is config for row in declarations(context)):
            raise ValueError("Channel constructor detached from original configuration row")
        if (
            type(actual) is not context.classes["Channel"]
            or not any(name == "Channel" and owner is actual for name, owner in context.objects)
            or parent.f_locals.get("self") is not context.core
            or type(parent.f_locals.get("q")) is not int
            or parent.f_locals["q"] != len(context.channel_records)
            or context.config["channels"][parent.f_locals["q"]] is not config
            or context.core.channels[parent.f_locals["name"]] is not actual
            or frame.f_locals.get("phase") is not context.phase
            or frame.f_locals.get("ion_string") is not actual.channel_class
            or frame.f_locals.get("type_string") is not actual.channel_type
            or frame.f_locals.get("max_val") is not actual.channelMax
        ):
            raise ValueError("Actual channel/configuration/phase argument association changed")
        record = dict(
            channel=actual,
            config=config,
            frame=frame,
            core=None,
            init_frame=None,
            state_frame=None,
            state_returned=False,
            init_returned=False,
            channel_returned=False,
            core_type=actual.channel_type,
            targets=None,
            vm=None,
            initial_voltage=None,
        )
        if any(row["channel"] is actual for row in context.channel_records):
            raise ValueError("Channel initialization already attempted")
        context.channel_records.append(record)
        return True
    if name in ("VgNaABC", "VgKABC") and method == "init":
        parent = _parent(context, frame, ("Channel", "init_channel"))
        record = next((row for row in context.channel_records if row["frame"] is parent), None)
        if record is None or record["core"] is not None:
            raise ValueError("Actual once-only channel-core birth required")
        channel = record["channel"]
        if (
            type(actual) is not context.classes[record["core_type"]]
            or channel.channel_core is not actual
            or any(owner is actual for _, owner in context.objects)
            or frame.f_locals.get("vm") is not context.sim.vm
            or frame.f_locals.get("cells") is not context.cells
            or frame.f_locals.get("p") is not context.p
            or frame.f_locals.get("targets") is not parent.f_locals.get("targets")
        ):
            raise ValueError("Original core factory/voltage/target owner association changed")
        record["core"], record["init_frame"] = actual, frame
        record["targets"], record["vm"] = frame.f_locals["targets"], frame.f_locals["vm"]
        context.objects.append(("channel_core_" + record["core_type"], actual))
        return True
    if name in CORE_TYPES and method == "_init_state":
        record = next((row for row in context.channel_records if row["core"] is actual), None)
        if record is None or record["state_frame"] is not None:
            raise ValueError("Original fresh channel state initialization required")
        parent = _parent(context, frame, (CORE_TYPES[name], "init"))
        if parent is not record["init_frame"] or frame.f_locals.get("V") is not parent.f_locals.get(
            "V"
        ):
            raise ValueError("Original targeted initial voltage object required")
        record["state_frame"] = frame
        record["initial_voltage"] = frame.f_locals["V"]
        return True
    return False


def returned_setup(context, frame):
    for record in context.channel_records:
        for frame_field, returned in (
            ("init_frame", "init_returned"),
            ("state_frame", "state_returned"),
            ("frame", "channel_returned"),
        ):
            if record[frame_field] is frame:
                record[returned] = context.initial._normal_return(frame)


def finish_setup(context):
    """No missing/omitted factory can be promoted by a completed reader."""
    declared = declarations(context)
    records = context.channel_records
    if len(records) != len(declared):
        raise ValueError("Complete original ordered channel construction required")
    expected = {}
    for config, record in zip(declared, records, strict=True):
        if (
            record["config"] is not config
            or not all(
                record[field] for field in ("channel_returned", "init_returned", "state_returned")
            )
            or record["core"] is None
        ):
            raise ValueError("Original channel/core/state setup did not complete")
        expected[config["name"]] = record["channel"]
    actual = context.core.channels
    if tuple(actual) != tuple(expected) or any(
        actual[key] is not value for key, value in expected.items()
    ):
        raise ValueError("Original final channel dictionary/order/duplicate-name result changed")
    validate_associations(context)


def validate_associations(context):
    for record in context.channel_records:
        channel, core, config = record["channel"], record["core"], record["config"]
        if (
            not any(row is config for row in declarations(context))
            or channel.channel_class != config["channel class"]
            or channel.channel_type != config["channel type"]
            or channel.init_active is not config.get("init active", True)
            or channel.channel_profiles_list is not config["apply to"]
        ):
            raise ValueError(
                "Original channel declaration/phase-activity/target association changed"
            )
        if core is not None and (
            channel.channel_core is not core
            or type(core) is not context.classes[record["core_type"]]
        ):
            raise ValueError("Original native channel/core association changed")
        for source_field, argument, expected in (
            ("init_frame", "targets", record["targets"]),
            ("init_frame", "vm", record["vm"]),
            ("state_frame", "V", record["initial_voltage"]),
        ):
            frame = record[source_field]
            observed = context.frames.get(id(frame))
            if frame is not None and observed is not None and not observed.get("returned", False):
                if observed["frame"] is not frame or frame.f_locals.get(argument) is not expected:
                    raise ValueError(
                        "Actual suspended channel source argument changed: " + argument
                    )
        if record["init_returned"] and core.targets is not record["targets"]:
            raise ValueError("Original target ndarray/duplicate/order owner was replaced")


def runtime_admit(context, role, frame, runtime):
    """Authenticate reached inherited/core methods and the exact active INIT gate."""
    _owner(context)
    if role[0] not in (*CORE_TYPES, "ChannelsABC", "VgNaABC", "VgKABC"):
        return False
    actual = frame.f_locals.get("self")
    record = next((row for row in context.channel_records if row["core"] is actual), None)
    if record is None or not record["init_returned"] or record["channel"].init_active is not True:
        raise ValueError("Only the actual initialized active INIT channel may run")
    method = role[1]
    if method == "run":
        parent = frame.f_back
        runner = context.functions[("MasterOfNetworks", "run_loop_channels")]
        if (
            parent.f_code is not runner.__code__
            or parent.f_locals.get("chan") is not record["channel"]
        ):
            raise ValueError("Original selected channel-loop call required")
        if (
            frame.f_locals.get("vm") is not context.sim.vm
            or frame.f_locals.get("p") is not context.p
        ):
            raise ValueError("Original runtime voltage/parameter owner required")
    elif method in ("_calculate_state", "_implement_state", "update_mh"):
        expected = (
            (CORE_TYPES[record["core_type"]], "_implement_state")
            if method == "update_mh"
            else (CORE_TYPES[record["core_type"]], "run")
        )
        parent = _parent(context, frame, expected)
        if parent.f_locals.get("self") is not actual:
            raise ValueError("Original inherited channel receiver required")
        if "V" in frame.f_locals and frame.f_locals["V"] is not parent.f_locals.get("V"):
            raise ValueError("Original targeted runtime voltage object required")
        if "p" in frame.f_locals and frame.f_locals["p"] is not context.p:
            raise ValueError("Original channel parameter owner required")
    else:
        raise ValueError("Channel setup cannot be replayed as runtime")
    return True


def permission_rows(context, kind):
    _owner(context)
    if kind not in ("storage", "first_step"):
        raise ValueError("Exact channel descendant epoch required")
    history = frozenset(("D_time", "flux_time"))
    rows = []
    for record in context.channel_records:
        rows.append((record["channel"], history))
        if kind == "first_step" and record["channel"].init_active is True:
            name = record["core_type"]
            base = CORE_TYPES[name]
            fields = set()
            for role, method in (
                (base, "run"),
                (base, "_implement_state"),
                (name, "_calculate_state"),
                ("ChannelsABC", "update_mh"),
            ):
                fields.update(source.effects(source.node(role, method), "self"))
            fields.update(source.effects(network_node("run_loop_channels"), "chan.channel_core"))
            rows.append((record["core"], frozenset(fields)))
    return tuple(rows)


def network_node(method):
    return source.network.node("MasterOfNetworks", method)
