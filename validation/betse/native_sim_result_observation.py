"""Read actual completed-SIM observations; never run or reconstruct a model.

The public Key completion surface is the sole live input. Its producer/review
remain explicitly held until adopted. Typed historical caches are read in their
original projection order; live final values never stand in for earlier steps.
"""

import ast
import contextlib
import hashlib
import importlib
import json
import math
import os
import struct
import sys
from pathlib import Path
from threading import RLock
from types import CodeType, FunctionType, SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_sim_reference_compare as comparison

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_sim_result_observation.py"
KEY_MODULE = "cells.processes.betse_native_sim_run"
KEY_FILE = "src/cells/processes/betse_native_sim_run.py"
KEY_SHA256 = KEY_REVIEW = None
HISTORY_MODULE = "cells.processes.betse_native_sim_history_observation"
HISTORY_FILE = "src/cells/processes/betse_native_sim_history_observation.py"
HISTORY_SHA256 = "06aec8e44e02cb3a65ebc076bfc98190ce8d1f035d14ccebd89c3198b11c7d24"
HISTORY_REVIEW = None
_CONTEXT_HELPER = next(
    code
    for code in contextlib.contextmanager.__code__.co_consts
    if type(code) is CodeType and code.co_name == "helper"
)
WRITER_FILE = "validation/betse/native_seed_demo_evidence.py"
WRITER_SHA256 = "e3b5228e3622b6baeaa27fd322008ec61c251f477f406dfe38f26f1f875ab4b6"
PAYLOAD_SHA256 = "697623c528af6c528286424ac0630279125ca7cf84d39cfc98ab1ff3e6d25027"
SNAPSHOT_SHA256 = "54d3002cc636770484b5b7a50f206a229ab68d3472cf95d8909e479b5944dcab"
KIND = "cells.completed_SIM_observation@1"
BINDING_KIND = "cells.completed_SIM_observation_saved_binding@1"
RELEASE = "CELLS_COMPLETED_SIM_OBSERVATION_RELEASED"
MAX_ITERATIONS, MAX_EVENTS = 512, 512
EPOCH = comparison.EPOCH
GJ_FIELDS = ("gjopen", "gj_block", "vgj")
GJ_CORE_FIELDS = ("alpha", "beta", "gjopen")
ELECTRIC_FIELDS = ("E_cell_x", "E_cell_y", "E_env_x", "E_env_y", "Emc", "Eme", "v_env", "Phi_b")
EVENT_ROLES = ("events", "global_events", "tissue_events", "make_changes")
EVENT_METHODS = ("fire_events", "_fire_events_global", "_fire_events_tissue")
KEY_VALIDATORS = (
    "completed_sim",
    "validate_sim",
    "_authority",
    "_bindings",
    "_links",
    "_snapshot",
    "_stable",
    "_metadata",
    "record_document",
    "_digest",
    "_same",
    "_streams",
    "_observation_roster",
    "_field_objects",
)
_LOCK, _ACTIVE, _FAILED = RLock(), [], []


class ObservationRejected(ValueError):
    def __init__(self, message, *, stage, partial=None):
        super().__init__(message)
        self.stage, self.partial = stage, partial


def source_plan():
    return dict(
        kind=KIND,
        public_entry="observe_completed(owner, *, enabled=False, capture)",
        capture_signature="capture(label, typed_wire) -> {path, sha256}",
        capture_input="already typed {tree, columns}; use evidence.write, not archive.snapshot",
        capture_labels=[
            "SIM.iteration_{one_based_ordinal:04d}",
            "SIM.before_state",
            "SIM.ready_state",
            "SIM.final_state",
            "SIM.rng_before",
            "SIM.rng_after",
        ],
        public_Key=dict(
            module=KEY_MODULE,
            source_sha256=KEY_SHA256,
            review=KEY_REVIEW,
            methods=["completed_sim", "validate_sim"],
            required_observation_rosters=["observation_objects", "observation_field_objects"],
            required_rng=(
                "two actual typed Cache snapshots per boundary; never NativeStream JSON inference"
            ),
        ),
        completed_history=dict(
            module=HISTORY_MODULE,
            file=HISTORY_FILE,
            source_sha256=HISTORY_SHA256,
            review=HISTORY_REVIEW,
            factory="observing_completed(owner, *, enabled=False)",
            methods=[
                "completed_sim()",
                "validate_sim(*, row=None, caches=())",
                "call(callback, *args, row=None, caches=(), **kwargs)",
                "record",
            ],
            release_environment="CELLS_NATIVE_SIM_HISTORY_OBSERVATION_RELEASED",
            full_fresh_authority="entry and exit; every actual row/cache/bit remains checked",
            interval_record=(
                "published only after successful closure; diagnostic, never a new owner"
            ),
        ),
        saved_writer=dict(
            file=WRITER_FILE,
            sha256=WRITER_SHA256,
            demo_helper_review="external full source closure in saved binding; no reciprocal pin",
        ),
        paired_compare=(
            "native_sim_reference_compare.compare_terminal_saved(reference, issued, "
            "accepted_observer_sha256=independently_authenticated_Root_plan_observer_pin)"
        ),
        epoch=EPOCH,
        iteration_wire=comparison.OBSERVATION_KIND,
        operator_modes={
            "original_value_and_flux": "original",
            "original_value_only_flux_omitted": "disabled",
        },
        limit=MAX_ITERATIONS,
        fields=list(comparison.codec.FIELDS),
        gap_junction=list(GJ_FIELDS),
        gap_junction_core=list(GJ_CORE_FIELDS),
        electric_fields=list(ELECTRIC_FIELDS),
        channel_state=(
            "original per-step core/channel_core projected dictionaries and actual class names"
        ),
        events="actual retained entry frames plus matching raw returns; no inferred body execution",
        optional_absence="present=False or original disabled branch; never filled with zeros",
        lineage=(
            "same actual sim/cells; distinct old INIT p and current SIM p; "
            "original constructor/INIT trials"
        ),
        calendar=(
            "entire actual configured calendar, exact times/sample membership/dt; no shift/search"
        ),
        starting_rng="external authenticated pre-SEED witness required; SIM-before is not pre-SEED",
        saved_request=["record", "binding"],
        saved_reader=(
            "saved_view(request, *, accepted_observer_sha256=None); exact independent "
            "observer producer from an authenticated Root plan, never the supplied record"
        ),
        saved_binding_kind=BINDING_KIND,
        terminal_association=["status=completed", "observation=record pin", "trial_identity"],
        saved_binding_fields=[
            "kind",
            "execution_source",
            "reviews",
            "runtime",
            "process",
            "terminal",
            "inputs",
            "original_sources",
            "observation_record",
        ],
        actual_source_operator_RNG_or_reference_entry=False,
        live_owner_cache_or_checkpoint_hydration=False,
        numerical_equality_is_saved_observation_only=True,
        common_starting_authority_established=False,
        scientific_physical_checkpoint_credit=0,
    )


def require(value, message):
    if not value:
        raise ValueError(message)


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _node(value):
    if type(value) is float:
        return dict(type="float", bits=struct.pack("<d", value).hex())
    require(value is None or type(value) in (str, int, bool), "Exact typed primitive")
    return dict(type=type(value).__name__, value=value)


def _dict(values):
    return dict(type="dict", values=[[_node(name), value] for name, value in values.items()])


def _mapping(node):
    require(type(node) is dict and node.get("type") == "dict", "Projected dictionary required")
    result = {}
    for key, value in node["values"]:
        require(key.get("type") == "str" and key["value"] not in result, "Unique projected key")
        result[key["value"]] = value
    return result


def _scalar(node, kind):
    types = dict(str=str, int=int, bool=bool, NoneType=type(None))
    require(
        type(node) is dict
        and set(node) == {"type", "value"}
        and node["type"] == kind
        and type(node["value"]) is types[kind],
        "Exact projected scalar",
    )
    return node["value"]


def _float(node):
    require(node["type"] in ("float", "numpy_scalar"), "Actual float64 time/dt bits required")
    if node["type"] == "numpy_scalar":
        require(node["dtype"] in ("<f8", ">f8"), "Native float64 scalar required")
    raw = bytes.fromhex(node["bits"])
    require(len(raw) == 8, "Complete float64 time/dt")
    return struct.unpack(">d" if node.get("dtype", "<f8").startswith(">") else "<d", raw)[0]


def _cache(cache):
    """Lossless read of a validated actual Cache, without decoding any object."""
    raw = cache.descriptor_json
    require(
        type(raw) is str and hashlib.sha256(raw.encode()).hexdigest() == cache.identity,
        "Exact retained cache descriptor required",
    )
    columns = {}
    for column in cache.columns:
        require(column.name not in columns, "Unique retained cache column")
        value = column.values
        columns[column.name] = dict(
            dtype=value.dtype.str,
            shape=list(value.shape),
            raw_bytes_hex=value.tobytes(order="C").hex(),
        )

    def convert(node):
        kind = node["kind"]
        if kind == "numeric_array":
            return dict(
                type="array",
                layout=node["source_layout"],
                column=node["column"],
                sha256=node["sha256"],
            )
        if kind == "object_array":
            return dict(
                type=kind, layout=node["source_layout"], values=[convert(v) for v in node["items"]]
            )
        if kind == "dict":
            return dict(type=kind, values=[[convert(k), convert(v)] for k, v in node["items"]])
        if kind in ("tuple", "list", "set", "frozenset"):
            return dict(type=kind, values=[convert(v) for v in node["items"]])
        return {"type": kind, **{k: v for k, v in node.items() if k != "kind"}}

    value = dict(tree=convert(json.loads(raw)), columns=columns)
    comparison.codec.wire(value, [])
    return value


def _take(node, source, target):
    """Copy only typed evidence; repeated occurrences keep distinct column names."""
    if node["type"] == "array":
        name = f"column_{len(target):06d}"
        target[name] = dict(source[node["column"]])
        return dict(node, column=name)
    if node["type"] == "dict":
        return dict(
            type="dict",
            values=[
                [_take(k, source, target), _take(v, source, target)] for k, v in node["values"]
            ],
        )
    if "values" in node:
        return {**node, "values": [_take(v, source, target) for v in node["values"]]}
    return dict(node)


def _calendar(cache):
    value = _cache(cache)
    tree = value["tree"]
    require(
        tree["type"] == "array"
        and tree["layout"]["dtype"] in ("<f8", ">f8")
        and len(tree["layout"]["shape"]) == 1,
        "Actual float64 calendar",
    )
    raw = bytes.fromhex(value["columns"][tree["column"]]["raw_bytes_hex"])
    times = [
        part[0]
        for part in struct.iter_unpack(">d" if tree["layout"]["dtype"][0] == ">" else "<d", raw)
    ]
    require(
        1 <= len(times) <= MAX_ITERATIONS and all(math.isfinite(t) for t in times),
        "Complete finite bounded calendar",
    )
    return times, value


def _layout(view, cache):
    wire = _cache(cache)
    root = wire["tree"]
    require(
        root["type"] == "tuple" and len(root["values"]) == 2, "Actual full SIM projection shape"
    )
    values = root["values"][0]
    require(values["type"] == "tuple", "Ordered full SIM field roots")
    objects, fields = view["observation_objects"], view["observation_field_objects"]
    require(
        type(objects) is tuple and type(fields) is tuple and len(values["values"]) <= len(fields),
        "Actual ordered root/field roster required",
    )
    selected = []
    for (role, obj), item in zip(fields[: len(values["values"])], values["values"], strict=True):
        require(
            type(role) is str
            and item["type"] == "tuple"
            and len(item["values"]) == 2
            and _scalar(item["values"][0], "str") == role,
            "Original field/projection order",
        )
        require(
            any(role == name and obj is actual for name, actual in objects),
            "Field must be its actual retained projection root",
        )
        selected.append((obj, _mapping(item["values"][1])))

    def fields_for(obj):
        matches = [data for actual, data in selected if actual is obj]
        require(
            bool(matches) and all(comparison.same(matches[0], data) for data in matches),
            "Original historical object fields unavailable or inconsistent",
        )
        return matches[0]

    def resolve(node):
        ref = _mapping(node)
        require(set(ref) == {"owned_reference"}, "Actual projected object reference required")
        index = _scalar(ref["owned_reference"], "int")
        require(0 <= index < len(objects), "Original projection reference out of bounds")
        return objects[index][1]

    return wire["columns"], fields_for, resolve


def _present(data, names, source, target):
    return _dict(
        {
            name: _dict(
                dict(
                    present=_node(name in data),
                    **({"value": _take(data[name], source, target)} if name in data else {}),
                )
            )
            for name in names
        }
    )


def _network(name, sim, parameters, fields, resolve, source, target):
    enabled = _scalar(parameters[name + "_enabled"], "bool")
    if not enabled:
        return _dict(
            dict(
                enabled=_node(False), source_branch=_node("disabled; no channel owner substituted")
            )
        )
    master = fields(resolve(sim[name]))
    core = fields(resolve(master["core"]))
    channels = _mapping(core["channels"])
    observed = []
    for key, reference in channels.items():
        channel = fields(resolve(reference))
        actual = resolve(channel["channel_core"])
        observed.append(
            _dict(
                dict(
                    name=_node(key),
                    core_type=_node(type(actual).__module__ + "." + type(actual).__qualname__),
                    fields=_dict(
                        {key: _take(value, source, target) for key, value in fields(actual).items()}
                    ),
                )
            )
        )
    return _dict(dict(enabled=_node(True), channels=dict(type="list", values=observed)))


def _method_chain(actual, name):
    member = next((vars(cls)[name] for cls in type(actual).__mro__ if name in vars(cls)), None)
    chain = []
    while member is not None:
        require(
            type(member) is FunctionType
            and len(chain) < 16
            and not any(member is old for old in chain),
            "Actual finite event callable chain",
        )
        chain.append(member)
        member = vars(member).get("__wrapped__")
    require(bool(chain), "Actual event method export unavailable")
    return tuple(chain)


def _work_frame(trial, frame):
    matches = [(code, namespace) for actual, code, namespace in trial.work if actual is frame]
    require(
        len(matches) == 1 and matches[0][0] is frame.f_code and matches[0][1] is frame.f_globals,
        "Actual admitted frame/code/global work evidence required",
    )
    returns = [
        i
        for i, (actual, event, _) in enumerate(trial.raw_returns)
        if actual is frame and event == "return"
    ]
    require(
        len(returns) == 1 and not any(actual is frame for actual, _ in trial.exceptions),
        "Actual admitted frame needs its normal retained return",
    )
    return returns[0]


def _outer_event_caller(view, body, name):
    chain = _method_chain(view["handler"], name)
    require(
        body.f_code is chain[-1].__code__ and body.f_globals is chain[-1].__globals__,
        "Actual native event body differs from retained export",
    )
    _work_frame(view["trial"], body)
    caller = body.f_back
    delegate = chain[-1]
    for wrapper in reversed(chain[:-1]):
        require(
            caller is not None
            and caller.f_code is wrapper.__code__
            and caller.f_globals is wrapper.__globals__,
            "Unretained/substituted event wrapper",
        )
        _work_frame(view["trial"], caller)
        require(
            vars(wrapper).get("__wrapped__") is delegate, "Actual wrapper/body delegate changed"
        )
        for key, value in (wrapper.__kwdefaults__ or {}).items():
            require(
                caller.f_locals.get(key) is value, "Actual wrapper hidden keyword delegate changed"
            )
        delegate = wrapper
        caller = caller.f_back
    return caller


def _event_rows(view, row, fields):
    trial = view["trial"]
    require(
        "_is_fired" not in fields(view["handler"]),
        "An event fired-state needs its actual boundary snapshots, not final-state inference",
    )
    require(
        tuple(role for role, _, _ in row.event_calls) == EVENT_ROLES,
        "Original four event calls and order required",
    )
    entries = list(row.event_calls[:3])
    returns = []
    for role, frame, time in entries:
        require(
            frame.f_globals.get("__name__") == "betse.science.tissue.tishandler"
            and frame.f_code.co_name == EVENT_METHODS[EVENT_ROLES.index(role)]
            and struct.pack("!d", time) == struct.pack("!d", row.source_time),
            "Actual original event entry/time required",
        )
        require(
            frame.f_locals.get("self") is view["handler"]
            and frame.f_locals.get("phase") is view["phase"],
            "Actual event handler/phase association required",
        )
        found = [
            (i, arg)
            for i, (actual, event, arg) in enumerate(trial.raw_returns)
            if actual is frame and event == "return"
        ]
        require(
            len(found) == 1 and not any(actual is frame for actual, _ in trial.exceptions),
            "Completed event body requires its actual unique normal return",
        )
        returns.append(found[0][0])
    outer, global_, tissue = entries
    loop = _outer_event_caller(view, outer[1], EVENT_METHODS[0])
    loop_chain = _method_chain(view["sim"], "_run_sim_core_loop")
    require(
        loop is not None
        and loop.f_code is loop_chain[-1].__code__
        and loop.f_globals is loop_chain[-1].__globals__
        and loop.f_locals.get("self") is view["sim"]
        and loop.f_locals.get("phase") is view["phase"],
        "Actual outer SIM loop caller required",
    )
    _work_frame(trial, loop)
    require(
        _outer_event_caller(view, global_[1], EVENT_METHODS[1]) is outer[1]
        and _outer_event_caller(view, tissue[1], EVENT_METHODS[2]) is outer[1]
        and returns[1] < returns[2] < returns[0],
        "Actual native event nesting/return order",
    )
    order = ((0, "enter"), (1, "enter"), (1, "return"), (2, "enter"), (2, "return"), (0, "return"))
    return dict(
        type="list",
        values=[
            _dict(
                dict(
                    ordinal=_node(i + 1),
                    module=_node("betse.science.tissue.tishandler"),
                    method=_node(frame.f_code.co_name),
                    boundary=_node(boundary),
                    source_time=_node(float(row.source_time)),
                    is_fired=_dict(dict(present=_node(False))),
                    error_type=_node(None),
                    cause_type=_node(None),
                )
            )
            for i, (index, boundary) in enumerate(order)
            for _, frame, _ in (entries[index],)
        ],
    )


def _iteration(view, row):
    source, fields, resolve = _layout(view, row.after)
    target = {}
    sim, parameters, handler = (fields(view[name]) for name in ("sim", "current_p", "handler"))
    gap = (
        {} if sim.get("gj_funk", {}).get("type") == "NoneType" else fields(resolve(sim["gj_funk"]))
    )
    gates = _dict(
        dict(
            gap_junction=_present(sim, GJ_FIELDS, source, target),
            gap_junction_core=_present(gap, GJ_CORE_FIELDS, source, target),
            molecules=_network("molecules", sim, parameters, fields, resolve, source, target),
            grn=_network("grn", sim, parameters, fields, resolve, source, target),
        )
    )
    optional = {}
    for label, name in (("event_cut", "event_cut"), ("voltage_event", "_event_voltage")):
        value = handler[name]
        present = value["type"] != "NoneType"
        optional[label] = _dict(
            dict(
                present=_node(present),
                **(
                    {
                        "fields": _dict(
                            {k: _take(v, source, target) for k, v in fields(resolve(value)).items()}
                        )
                    }
                    if present
                    else {}
                ),
            )
        )
    events = _dict(
        dict(
            calls=_event_rows(view, row, fields),
            global_options=_take(parameters["global_options"], source, target),
            scheduled_options=_take(parameters["scheduled_options"], source, target),
            **optional,
        )
    )
    require(
        type(row.rng) is tuple and len(row.rng) == 2, "Both actual per-step RNG caches required"
    )
    numpy, python = (_cache(cache) for cache in row.rng)
    raw = dict(
        tree=_dict(
            dict(
                ordinal=_node(row.ordinal + 1),
                source_time=_node(float(row.source_time)),
                sampled=_node(row.sampled),
                configured_dt=_node(float(view["dt"])),
                fields=_dict(
                    {
                        name: _take(sim[name], source, target)
                        for name in comparison.codec.FIELDS
                        if name in sim
                    }
                ),
                numpy_random=_take(numpy["tree"], numpy["columns"], target),
                python_random=_take(python["tree"], python["columns"], target),
                observation_contract=_node(comparison.OBSERVATION_KIND),
                gates=gates,
                electric_fields=_present(sim, ELECTRIC_FIELDS, source, target),
                events=events,
            )
        ),
        columns=target,
    )
    # Same strict reader as the independently compiled original, no value oracle.
    comparison.codec.wire(raw, [])
    return raw


def _key_functions(module, raw, filename):
    codes = {
        v.co_name: v
        for v in compile(raw, filename, "exec", dont_inherit=True).co_consts
        if type(v) is CodeType
    }
    functions = []
    for name in KEY_VALIDATORS:
        function = vars(module).get(name)
        require(
            type(function) is FunctionType
            and function.__code__ == codes[name]
            and function.__globals__ is vars(module)
            and function.__closure__ is None
            and function.__defaults__ is None
            and function.__kwdefaults__ is None,
            "Actual completion validation callable/code changed",
        )
        functions.append((name, function, function.__code__))
    return tuple(functions)


def _api():
    require(_pin(KEY_SHA256) and type(KEY_REVIEW) is dict, "Reviewed Key completion producer held")
    reader = comparison._report_api().Reader()
    reader.bound(KEY_REVIEW)
    require(
        Path(evidence.__file__).resolve() == ROOT / WRITER_FILE
        and snapshot.digest(ROOT / WRITER_FILE) == WRITER_SHA256,
        "Exact existing typed evidence transport required",
    )
    path = ROOT / KEY_FILE
    require(
        not path.is_symlink() and snapshot.digest(path) == KEY_SHA256,
        "Exact accepted Key completion source required",
    )
    module = importlib.import_module(KEY_MODULE)
    require(
        Path(module.__file__).resolve() == path and type(module.SimRunOwner) is type,
        "Actual Key completion runtime required",
    )
    return module, _key_functions(module, path.read_bytes(), str(path))


def _api_unchanged(api, bindings):
    require(
        snapshot.digest(Path(api.__file__)) == KEY_SHA256,
        "Completion producer changed during observation",
    )
    for name, function, code in bindings:
        require(
            vars(api).get(name) is function
            and function.__code__ is code
            and function.__defaults__ is None
            and function.__kwdefaults__ is None
            and function.__closure__ is None
            and function.__globals__ is vars(api),
            "Completion public surface changed during observation",
        )


def _history_bindings(api, raw, filename):
    declarations = {}
    for node in ast.parse(raw).body:
        if isinstance(node, ast.FunctionDef):
            declarations[node.name] = node
        elif isinstance(node, ast.ClassDef):
            declarations.update(
                {
                    node.name + "." + method.name: method
                    for method in node.body
                    if isinstance(method, ast.FunctionDef)
                }
            )
    unit = compile(raw, filename, "exec", dont_inherit=True)
    pending, codes = [unit], {}
    while pending:
        code = pending.pop()
        codes[code.co_qualname] = code
        pending.extend(v for v in code.co_consts if type(v) is CodeType)
    exported = vars(api)["observing_completed"]
    body = vars(exported).get("__wrapped__")
    require(
        type(exported) is FunctionType
        and exported.__code__ is _CONTEXT_HELPER
        and exported.__globals__ is vars(contextlib)
        and type(body) is FunctionType
        and body.__code__ == codes["observing_completed"]
        and body.__globals__ is vars(api)
        and set(body.__kwdefaults__ or ()) == {"enabled"}
        and body.__kwdefaults__["enabled"] is False
        and len(exported.__closure__ or ()) == 1
        and exported.__closure__[0].cell_contents is body,
        "Actual stdlib contextmanager/original history generator required",
    )
    rows = []
    for name, node in declarations.items():
        code = codes[name]
        parts = name.split(".")
        if len(parts) > 2 or (
            len(parts) == 2
            and parts[0] not in ("HistoryObservationRejected", "CompletedHistoryObservation")
        ):
            continue
        holder = api if len(parts) == 1 else vars(api)[parts[0]]
        actual = vars(holder).get(parts[-1])
        function = actual.fget if type(actual) is property else actual
        if name == "observing_completed":
            function = body
        defaults = tuple(ast.literal_eval(v) for v in node.args.defaults) or None
        keywords = {
            arg.arg: ast.literal_eval(value)
            for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
            if value is not None
        } or None
        require(
            type(function) is FunctionType
            and function.__code__ == code
            and comparison.same(function.__defaults__, defaults)
            and comparison.same(function.__kwdefaults__, keywords)
            and function.__globals__ is vars(api),
            "Original history callable/code required: " + name,
        )
        rows.append((holder, parts[-1], actual, function))
    classes = tuple(
        (cls, cls.__mro__, tuple(vars(cls).items()))
        for cls in (api.CompletedHistoryObservation, api.ObservationRecord)
    )
    require(
        api.ObservationRecord.__getattribute__ is object.__getattribute__
        and "__getattr__" not in vars(api.ObservationRecord),
        "Original sealed history record dispatch required",
    )
    require(
        api.CompletedHistoryObservation.__getattribute__ is object.__getattribute__
        and "__getattr__" not in vars(api.CompletedHistoryObservation),
        "Original history token attribute dispatch required",
    )
    functions = tuple(
        (
            holder,
            name,
            actual,
            function,
            function.__code__,
            function.__globals__,
            function.__defaults__,
            tuple((function.__kwdefaults__ or {}).items()),
            tuple((cell, cell.cell_contents) for cell in function.__closure__ or ()),
        )
        for holder, name, actual, function in rows
    )
    wrapper = (exported, exported.__code__, exported.__globals__, exported.__closure__[0], body)
    globals_ = tuple((name, value) for name, value in vars(api).items() if name != "_PENDING")
    return functions, classes, wrapper, globals_


def _history_api(parent):
    require(
        _pin(HISTORY_SHA256) and type(HISTORY_REVIEW) is dict,
        "Reviewed completed-history producer held",
    )
    comparison._report_api().Reader().bound(HISTORY_REVIEW)
    path = ROOT / HISTORY_FILE
    require(
        not path.is_symlink() and snapshot.digest(path) == HISTORY_SHA256,
        "Exact accepted completed-history source required",
    )
    api = importlib.import_module(HISTORY_MODULE)
    require(
        Path(api.__file__).resolve() == path
        and api.parent is parent
        and api.PARENT_SHA256 == KEY_SHA256
        and api.PARENT_REVIEW_SHA256 == KEY_REVIEW["sha256"],
        "Actual history/complete-SIM predecessor association required",
    )
    return api, _history_bindings(api, path.read_bytes(), str(path))


def _history_unchanged(api, bindings):
    require(
        snapshot.digest(Path(api.__file__)) == HISTORY_SHA256,
        "History producer changed during observation",
    )
    functions, classes, wrapper, globals_ = bindings
    require(
        all(vars(api).get(name) is value for name, value in globals_),
        "History source namespace lookup changed",
    )
    for holder, name, actual, fn, code, namespace, defaults, keywords, closure in functions:
        require(
            vars(holder).get(name) is actual
            and fn.__code__ is code
            and fn.__globals__ is namespace
            and fn.__defaults__ is defaults
            and len(fn.__kwdefaults__ or ()) == len(keywords)
            and all(
                key in (fn.__kwdefaults__ or {}) and fn.__kwdefaults__[key] is value
                for key, value in keywords
            )
            and len(fn.__closure__ or ()) == len(closure)
            and all(
                cell is old and cell.cell_contents is value
                for cell, (old, value) in zip(fn.__closure__ or (), closure, strict=True)
            ),
            "History callable/default/delegate changed: " + name,
        )
    for cls, mro, members in classes:
        require(
            cls.__mro__ is mro
            and len(vars(cls)) == len(members)
            and all(vars(cls).get(name) is value for name, value in members),
            "History token/record dispatch changed",
        )
    exported, code, namespace, cell, body = wrapper
    require(
        api.observing_completed is exported
        and exported.__code__ is code
        and exported.__globals__ is namespace
        and vars(exported).get("__wrapped__") is body
        and exported.__closure__ == (cell,)
        and cell.cell_contents is body,
        "History contextmanager wrapper/delegate changed",
    )


def _history_record(api, actual, view):
    require(
        type(actual) is api.ObservationRecord
        and actual.status == "completed_observation"
        and actual.law == api.LAW_ID
        and actual.trial_identity == view["trial"].identity
        and actual.configured_rows == len(view["iterations"])
        and actual.checked_rows == tuple(range(len(view["iterations"])))
        and actual.full_authority_attempts == actual.full_authority_returns == 2
        and actual.retained_payload_attempts == actual.retained_payload_returns
        and type(actual.native_or_scientific_credit) is int
        and actual.native_or_scientific_credit == 0,
        "Successful complete history interval/exit authority required",
    )
    return {
        name: getattr(actual, name)
        for name in (
            "law",
            "status",
            "trial_identity",
            "configured_rows",
            "checked_rows",
            "work",
            "full_authority_attempts",
            "full_authority_returns",
            "retained_payload_attempts",
            "retained_payload_returns",
            "source_metadata_operations",
            "source_retained_cache_attempts",
            "source_retained_cache_returns",
            "callback_calls",
            "native_or_scientific_credit",
        )
    }


def _surface(owner, api, call):
    require(type(owner) is api.SimRunOwner, "Actual issued Key SimRunOwner required")
    trial = call("validate_sim")
    view = call("completed_sim")
    require(
        type(view) is dict and view["owner"] is owner and view["trial"] is trial,
        "Same actual completed owner/trial required",
    )
    # This is the genuine returned phase's handler reference, not a supplied
    # handler or a reconstructed cache. Key validates this same relationship.
    view = dict(view, handler=view["phase"].dyna)
    require(
        view["phase"].sim is view["sim"]
        and view["phase"].cells is view["cells"]
        and view["phase"].p is view["current_p"]
        and view["old_p"] is not view["current_p"]
        and view["phase"].dyna is view["handler"]
        and view["sim"].dyna is view["handler"]
        and view["phase"].callbacks is view["callback"],
        "Actual SIM/current-p/retained sim+cells+handler lineage changed",
    )
    require(
        trial.assembly_identity == view["constructor"].identity
        and trial.init_identity == view["completed_INIT"].identity
        and all(
            getattr(trial, name) is True
            for name in (
                "report_returned",
                "loop_returned",
                "context_returned",
                "before_native_pickle",
            )
        )
        and view["before_native_pickle"] is True
        and view["native_pickle_or_checkpoint_or_physical_admission"] is False,
        "Complete original report/loop/context before pickle required",
    )
    require(
        type(view["iterations"]) is tuple
        and view["iterations"] is trial.iterations
        and view["calendar"] is trial.calendar
        and view["sampled"] is trial.sampled
        and view["before"] is trial.before
        and view["after"] is trial.after
        and struct.pack("!d", view["dt"]) == struct.pack("!d", trial.dt)
        and view["operator_mode"] == trial.operator_mode
        and type(view["operator_mode"]) is str
        and view["operator_mode"]
        in ("original_value_and_flux", "original_value_only_flux_omitted"),
        "Exact original completion surface",
    )
    require(
        "observation_objects" in view and "observation_field_objects" in view,
        "Actual ordered projection rosters unavailable",
    )
    # Preserve the genuine producer mode separately from the pair's short
    # comparison spelling. Neither the returned public view nor the owner is
    # changed by this projection.
    return dict(
        view,
        source_operator_mode=view["operator_mode"],
        operator_mode={
            "original_value_and_flux": "original",
            "original_value_only_flux_omitted": "disabled",
        }[view["operator_mode"]],
    )


def _verification_atom(value, depth=0):
    require(depth <= 12, "Bounded verification binding graph")
    kind = type(value)
    if value is None or kind in (str, int, bool):
        return (kind.__name__, value)
    if kind is float:
        return ("float", struct.pack("!d", value).hex())
    if kind is FunctionType:
        return (
            "function",
            id(value),
            id(value.__code__),
            id(value.__globals__),
            _verification_atom(value.__defaults__, depth + 1),
            _verification_atom(value.__kwdefaults__, depth + 1),
            tuple(
                (id(cell), _verification_atom(cell.cell_contents, depth + 1))
                for cell in (value.__closure__ or ())
            ),
        )
    if kind is dict:
        return (
            "dict",
            id(value),
            tuple(
                (_verification_atom(k, depth + 1), _verification_atom(v, depth + 1))
                for k, v in value.items()
            ),
        )
    if kind in (tuple, list):
        return (kind.__name__, id(value), tuple(_verification_atom(v, depth + 1) for v in value))
    if kind in (set, frozenset):
        return (
            kind.__name__,
            id(value),
            tuple(sorted(_verification_atom(v, depth + 1) for v in value)),
        )
    return ("object", id(value), id(kind))


def _verification_state():
    modules = []
    for module in (evidence, evidence.payload, snapshot):
        namespace = vars(module)
        modules.append(
            (
                id(module),
                id(namespace),
                tuple(
                    (
                        name,
                        ("retained_failure_list", id(value))
                        if name == "_RAW_FAILURES"
                        else _verification_atom(value),
                    )
                    for name, value in namespace.items()
                    if not name.startswith("__")
                ),
            )
        )
    helpers = [
        hashlib.sha256,
        json.loads,
        json.dumps,
        json.JSONEncoder,
        *[
            getattr(Path, name)
            for name in (
                "open",
                "read_bytes",
                "stat",
                "is_file",
                "is_dir",
                "is_symlink",
                "resolve",
                "absolute",
            )
        ],
        comparison.report.Reader,
        comparison.report.Reader.__new__,
        comparison.report.Reader.__getattribute__,
        *[vars(comparison.report.Reader)[name] for name in ("bind", "read", "bound")],
    ]
    return tuple(modules), tuple(_verification_atom(v) for v in helpers)


def _verification_bindings():
    for module, expected in (
        (evidence, WRITER_SHA256),
        (evidence.payload, PAYLOAD_SHA256),
        (snapshot, SNAPSHOT_SHA256),
    ):
        path = Path(module.__file__)
        raw = path.read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == expected,
            "Accepted verification helper source required",
        )
        names = {n.name for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
        for code in compile(raw, str(path), "exec", dont_inherit=True).co_consts:
            if type(code) is CodeType and code.co_name in names:
                actual = vars(module).get(code.co_name)
                require(
                    type(actual) is FunctionType
                    and actual.__code__ == code
                    and actual.__globals__ is vars(module),
                    "Verification helper executable changed",
                )
    return _verification_state()


def _lineage(view):
    return dict(
        facts={name: True for name in comparison.LINEAGE},
        process_local_identities={
            name: id(view[name])
            for name in ("phase", "sim", "cells", "old_p", "current_p", "handler", "callback")
        },
        actual_edges=[
            ["phase", "sim", "sim"],
            ["phase", "cells", "cells"],
            ["phase", "p", "current_p"],
            ["phase", "dyna", "handler"],
            ["sim", "dyna", "handler"],
        ],
        INIT_trial_identity=view["trial"].init_identity,
        constructor_trial_identity=view["trial"].assembly_identity,
        source="public validate_sim + identical completed_sim actual owner",
        live_owner_or_checkpoint_hydration=False,
    )


def _observe(owner, api, capture, check, *, history_api=None, history_check=None):
    context = SimpleNamespace(
        owner=owner,
        view=None,
        primary=None,
        capture_errors=[],
        rows=[],
        raw_row=None,
        record=None,
        invalid=False,
        entry_error=None,
        calls=[],
        public_returns=[],
        verification=None,
        files=comparison._report_api().Reader(),
        prior=(sys.getprofile(), sys.gettrace()),
        result=None,
        interval=None,
        raw_history_record=None,
    )
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        error = ObservationRejected("Reentrant observation", stage="reentrant", partial=_ACTIVE[-1])
        _ACTIVE[-1].entry_error = error
        raise error
    _ACTIVE.append(context)

    def checked():
        if context.entry_error is not None:
            raise context.entry_error
        require(not context.invalid, "Rejected observation cannot resume")
        require(
            (sys.getprofile(), sys.gettrace()) == context.prior,
            "Both inherited observer hooks required before metadata callbacks",
        )
        if context.verification is not None:
            require(
                _verification_state() == context.verification,
                "Actual transport verification callable/helper bindings changed",
            )
        check()
        if history_check is not None:
            history_check()

    def call(name, **kwargs):
        checked()
        context.calls.append((name, "attempted"))
        actual = (
            getattr(api, name)(owner)
            if context.interval is None
            else getattr(context.interval, name)(**kwargs)
        )
        # Preserve the actual raw result before another fallible observer/check.
        context.public_returns.append((name, actual))
        context.calls.append((name, "returned"))
        checked()
        return actual

    def validate(*, row=None, caches=()):
        actual = call("validate_sim", row=row, caches=caches)
        require(actual is context.view["trial"], "Actual completed source epoch changed")

    def emit(label, raw, *, row=None, caches=()):
        context.raw_observation = raw
        checked()
        expected = evidence._seal(raw)
        try:
            pin = (
                capture(label, raw)
                if context.interval is None
                else context.interval.call(capture, label, raw, row=row, caches=caches)
            )
            context.returned_capture_pin = pin
            require(
                type(pin) is dict and set(pin) == {"path", "sha256"} and _pin(pin["sha256"]),
                "Capture must return exact saved file pin",
            )
            checked()
            require(
                evidence._seal(raw) == expected, "Capture callback changed original observation"
            )
            context.files.bind(pin)
            for part in evidence.files(pin["path"], expected_sha256=pin["sha256"]):
                context.files.bind(part)
            saved = evidence.read(pin["path"], expand=True, expected_sha256=pin["sha256"])
            require(
                evidence._seal(saved) == expected, "Saved capture is not the actual observed wire"
            )
        except BaseException as error:
            context.capture_errors.append((label, error, raw))
            if context.primary is None:
                context.primary = error
            raise
        checked()
        validate(row=row, caches=caches)
        return pin

    def drive():
        view = context.view = _surface(owner, api, call)
        checked()
        times, calendar = _calendar(view["calendar"])
        require(
            len(times) == len(view["iterations"]) == view["current_p"].sim_tsteps,
            "Entire configured actual calendar required",
        )
        sample = _cache(view["sampled"])
        require(sample["tree"]["type"] == "set", "Actual native sample set")
        sampled = {struct.pack("!d", _float(n)).hex() for n in sample["tree"]["values"]}
        require(
            len(sampled) == len(sample["tree"]["values"])
            and sampled <= {struct.pack("!d", t).hex() for t in times},
            "Actual sample axis",
        )
        for index, (row, time) in enumerate(zip(view["iterations"], times, strict=True)):
            context.raw_row = row
            require(
                type(row.ordinal) is int
                and row.ordinal == index
                and type(row.sampled) is bool
                and struct.pack("!d", row.source_time) == struct.pack("!d", time)
                and row.sampled == (struct.pack("!d", time).hex() in sampled),
                "Exact original ordinal/time/sample boundary",
            )
            validate(row=row)
            raw = context.raw_observation = _iteration(view, row)
            pin = emit(f"SIM.iteration_{index + 1:04d}", raw, row=row)
            context.rows.append(dict(ordinal=index, epoch=EPOCH, files=pin))
        captures = {}
        for label, cache in (
            ("before", view["trial"].before),
            ("ready", view["trial"].ready[0]),
            ("final", view["trial"].after[0]),
        ):
            captures[label] = emit("SIM." + label + "_state", _cache(cache), caches=(cache,))
        for label, states in (
            ("rng_before", view["trial"].rng_before),
            ("rng_after", view["trial"].rng_after),
        ):
            require(type(states) is tuple and len(states) == 2, "Both actual full RNG caches")
            columns = {}
            parts = []
            for state in states:
                value = _cache(state)
                parts.append(_take(value["tree"], value["columns"], columns))
            captures[label] = emit(
                "SIM." + label,
                dict(tree=dict(type="tuple", values=parts), columns=columns),
                caches=states,
            )
        record = context.record = dict(
            kind=KIND,
            status="completed_observation",
            epoch=EPOCH,
            operator_mode=view["operator_mode"],
            source_operator_mode=view["source_operator_mode"],
            trial_identity=view["trial"].identity,
            calendar=calendar,
            sampled=sample,
            captures=captures,
            dt_bits=struct.pack("!d", view["dt"]).hex(),
            iterations=context.rows,
            lineage=_lineage(view),
            configured_iterations=len(times),
            work=dict(
                source_calls=len(view["trial"].work),
                iterations=len(times),
                independent_inputs=1,
                validation_calls=context.calls,
            ),
            producer=dict(
                module=KEY_MODULE,
                sha256=KEY_SHA256,
                review=KEY_REVIEW,
                observer=dict(path=FILE, sha256=snapshot.digest(ROOT / FILE)),
            ),
            domain=dict(
                all_retained_step_caches_finite=all(
                    row.after.all_finite for row in view["iterations"]
                ),
                physical_domain_or_conservation_admitted=False,
            ),
            pre_SEED_initial_rng_available=False,
            common_starting_authority_established=False,
            numerical_parity_available=False,
            physical_checkpoint_credit=0,
        )
        # Fallible sealing is inside the observation; nothing usable is returned first.
        validate()
        json.dumps(record, sort_keys=True, allow_nan=False)
        checked()
        for path, digest in tuple(context.files.pins.items()):
            context.files.bind(dict(path=path, sha256=digest))
        context.result = record

    try:
        context.verification = _verification_bindings()
        checked()
        if history_api is None:
            drive()
        else:
            require(history_check is not None, "Authenticated history dispatch check required")
            context.history_manager = history_api.observing_completed(owner, enabled=True)
            with context.history_manager as token:
                context.interval = token
                require(
                    type(token) is history_api.CompletedHistoryObservation,
                    "Actual completed-history observation token required",
                )
                checked()
                drive()
            context.raw_history_record = token.record
            checked()
            context.record["work"]["history_interval"] = _history_record(
                history_api, context.raw_history_record, context.view
            )
            context.record["producer"]["history"] = dict(
                path=HISTORY_FILE, sha256=HISTORY_SHA256, review=HISTORY_REVIEW
            )
            json.dumps(context.record, sort_keys=True, allow_nan=False)
            checked()
    except BaseException as error:
        context.raw_history_failure = error
        if context.entry_error is not None:
            context.primary = context.entry_error
        elif context.primary is None:
            context.primary = (
                error.__cause__
                if history_api is not None
                and type(error) is history_api.HistoryObservationRejected
                and error.__cause__ is not None
                else error
            )
        elif context.primary is not error:
            context.capture_errors.append(("history_exit", error, context.interval))
    finally:
        # A rejected inherited callback can clear its own hook. Recover both
        # independently before another callback or a usable result is returned.
        for setter, getter, prior in (
            (sys.setprofile, sys.getprofile, context.prior[0]),
            (sys.settrace, sys.gettrace, context.prior[1]),
        ):
            try:
                if getter() is not prior:
                    setter(prior)
            except BaseException as error:
                context.capture_errors.append(("hook_restore", error, None))
        final = []
        for getter in (sys.getprofile, sys.gettrace):
            try:
                final.append(getter())
            except BaseException as error:
                final.append(None)
                context.capture_errors.append(("hook_final_identity", error, None))
        if tuple(final) != context.prior:
            context.capture_errors.append(
                ("hook_coverage", ValueError("Inherited hooks not restored"), None)
            )
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.invalid = True
    if context.primary is not None or context.capture_errors or context.invalid:
        _FAILED.append(context)
        primary = (
            context.primary
            if context.primary is not None
            else (
                context.capture_errors[0][1]
                if context.capture_errors
                else ValueError("Observation epoch changed")
            )
        )
        raise ObservationRejected(
            "Completed-SIM observation failed", stage="observation", partial=context
        ) from primary
    return context.result


def observe_completed(owner, *, enabled=False, capture):
    """Observe a genuine completed owner. This never calls an issuer or solver."""
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise ObservationRejected("Completed-SIM observation held", stage="release")
    with _LOCK:
        try:
            api, bindings = _api()
            history, history_bindings = _history_api(api)
        except Exception as error:
            raise ObservationRejected(
                "Accepted completion producer unavailable", stage="producer"
            ) from error
        return _observe(
            owner,
            api,
            capture,
            lambda: _api_unchanged(api, bindings),
            history_api=history,
            history_check=lambda: _history_unchanged(history, history_bindings),
        )


def saved_view(request, *, accepted_observer_sha256=None):
    """Authenticate Root's immutable saved binding; never reconstitute an owner."""
    side = comparison._empty()
    side["error"] = dict(
        type="ProducerPrerequisiteUnavailable", message="Key completion adoption held"
    )
    if not (
        _pin(KEY_SHA256)
        and type(KEY_REVIEW) is dict
        and _pin(HISTORY_SHA256)
        and type(HISTORY_REVIEW) is dict
        and _pin(WRITER_SHA256)
        and _pin(accepted_observer_sha256)
    ):
        return side
    try:
        require(
            _pin(KEY_SHA256) and type(KEY_REVIEW) is dict and _pin(WRITER_SHA256),
            "Reviewed completion/diagnostic producer held",
        )
        require(
            type(request) is dict and set(request) == {"record", "binding"},
            "Exact observation file request",
        )
        reader = side["reader"]
        binding = reader.bound(request["binding"])
        require(
            set(binding) == set(source_plan()["saved_binding_fields"])
            and binding["kind"] == BINDING_KIND
            and binding["observation_record"] == request["record"],
            "Exact saved completion association",
        )
        record = reader.bound(request["record"])
        side["failure"] = record.get("failure")
        execution = binding["execution_source"]
        manifest = snapshot.verify(execution["root"], manifest_sha256=execution["snapshot_sha256"])
        reader.bind(
            dict(
                path=str(Path(execution["root"]) / "SNAPSHOT.json"),
                sha256=execution["snapshot_sha256"],
            )
        )
        reader.bind(
            dict(
                path=str(Path(execution["root"]) / "checkout.patch"),
                sha256=manifest["patch_sha256"],
            )
        )
        for name, row in manifest["files"].items():
            reader.bind(dict(path=str(Path(execution["root"]) / name), sha256=row["sha256"]))
        for name, pin in execution["owned_files"].items():
            require(
                manifest["files"][name]["sha256"] == pin, "Actual immutable completion producer"
            )
        require(
            execution["owned_files"][KEY_FILE] == KEY_SHA256
            and execution["owned_files"][WRITER_FILE] == WRITER_SHA256
            and execution["owned_files"][FILE] == record["producer"]["observer"]["sha256"]
            and execution["owned_files"][FILE] == accepted_observer_sha256
            and record["producer"]["sha256"] == KEY_SHA256
            and record["producer"]["review"] == KEY_REVIEW
            and KEY_REVIEW in binding["reviews"],
            "Explicit accepted completion/observer producer",
        )
        for pin in binding["reviews"]:
            reader.bound(pin)
        inputs = binding["inputs"]
        require(
            set(inputs) == {"root", "inventory", "mode", "profile"}
            and inputs["mode"] == record["operator_mode"],
            "Exact complete input/profile/mode",
        )
        actual_inputs = comparison._source_reader(
            comparison.input_files, comparison.INPUT_READER_SHA256
        ).inventory(Path(inputs["root"]))
        require(
            comparison.same(actual_inputs, inputs["inventory"]), "Complete saved input tree drift"
        )
        runtime = reader.bound(binding["runtime"])
        for pin in runtime["loaded_files"].values():
            path = reader.bind(pin)
            if path.is_relative_to(Path(execution["root"])):
                require(
                    manifest["files"][str(path.relative_to(execution["root"]))]["sha256"]
                    == pin["sha256"],
                    "Loaded completion source drift",
                )
        for name in (KEY_FILE, FILE, WRITER_FILE, HISTORY_FILE):
            module_name = name.removesuffix(".py").replace("/", ".")
            if name.startswith("src/"):
                module_name = module_name.removeprefix("src.")
            require(
                runtime["loaded_files"].get(module_name)
                == dict(
                    path=str(Path(execution["root"]) / name),
                    sha256=manifest["files"][name]["sha256"],
                ),
                "Actual loaded completion producer required",
            )
        require(
            type(runtime["python"]) is str and runtime["python"], "Actual Python runtime required"
        )
        reader.bind(runtime["executable"])
        process = reader.bound(binding["process"])
        limits = process["limits"]
        require(
            process["status"] == "completed"
            and process["returncode"] == 0
            and process["elapsed_seconds"] <= limits["max_wall_seconds"]
            and process["sampled_peak_process_tree_rss_bytes"]
            <= limits["max_process_tree_rss_bytes"]
            and process["minimum_available_host_memory_bytes"]
            >= limits["min_available_host_memory_bytes"]
            and process["samples"] > 0,
            "Actual guarded completed observation required",
        )
        terminal = reader.bound(binding["terminal"])
        require(
            terminal["status"] == "completed"
            and terminal["observation"] == request["record"]
            and terminal["trial_identity"] == record["trial_identity"],
            "Successful actual terminal association required",
        )
        require(
            record["kind"] == KIND
            and record["status"] == "completed_observation"
            and record["epoch"] == EPOCH
            and record["operator_mode"] in ("original", "disabled")
            and record["source_operator_mode"]
            == {
                "original": "original_value_and_flux",
                "disabled": "original_value_only_flux_omitted",
            }[record["operator_mode"]]
            and record["common_starting_authority_established"] is False
            and record["numerical_parity_available"] is False
            and record["physical_checkpoint_credit"] == 0,
            "Exact completed observation record",
        )
        history = record["producer"]["history"]
        require(
            history == dict(path=HISTORY_FILE, sha256=HISTORY_SHA256, review=HISTORY_REVIEW)
            and HISTORY_REVIEW in binding["reviews"]
            and execution["owned_files"][HISTORY_FILE] == HISTORY_SHA256,
            "Explicit accepted completed-history producer/review required",
        )
        closed = record["work"]["history_interval"]
        require(
            closed["law"] == "actual_completed_SIM_read_only_complete_history_interval@1"
            and closed["status"] == "completed_observation"
            and closed["trial_identity"] == record["trial_identity"]
            and closed["configured_rows"] == record["configured_iterations"]
            and closed["checked_rows"] == list(range(record["configured_iterations"]))
            and closed["full_authority_attempts"] == closed["full_authority_returns"] == 2
            and closed["retained_payload_attempts"] == closed["retained_payload_returns"]
            and type(closed["native_or_scientific_credit"]) is int
            and closed["native_or_scientific_credit"] == 0,
            "Complete saved history interval/exit proof required",
        )
        calendar = comparison.codec.wire(record["calendar"], [])
        require(
            calendar["kind"] == "array"
            and calendar["layout"]["dtype"] in ("<f8", ">f8")
            and len(calendar["layout"]["shape"]) == 1,
            "Saved actual calendar",
        )
        values = record["calendar"]["columns"][record["calendar"]["tree"]["column"]]
        order = ">d" if values["dtype"][0] == ">" else "<d"
        times = [
            struct.pack("!d", v[0]).hex()
            for v in struct.iter_unpack(order, bytes.fromhex(values["raw_bytes_hex"]))
        ]
        require(
            all(math.isfinite(struct.unpack("!d", bytes.fromhex(t))[0]) for t in times),
            "Finite actual calendar bits",
        )
        sample = comparison.codec.wire(record["sampled"], [])
        require(sample["kind"] == "set", "Actual saved sample set")
        sampled = [comparison.codec._f64(v) for v in sample["items"]]
        require(
            len(set(sampled)) == len(sampled) and set(sampled) <= set(times),
            "Complete saved sample membership",
        )
        require(
            1 <= len(times) <= MAX_ITERATIONS
            and len(times) == record["configured_iterations"]
            and len(times) == len(record["iterations"]),
            "Complete saved calendar/iteration roster",
        )
        rows = []
        for index, row in enumerate(record["iterations"]):
            require(
                row["ordinal"] == index and row["epoch"] == EPOCH, "Exact saved iteration order"
            )
            value = comparison._read_row(reader, row["files"], index, required_observation=True)
            require(
                value["source_time_bits"] == times[index] and value["dt_bits"] == record["dt_bits"],
                "Saved original calendar/time/dt association",
            )
            require(
                value["sampled"] == (times[index] in sampled),
                "Saved sample flag differs from actual axis",
            )
            rows.append(value)
        require(
            set(record["captures"]) == {"before", "ready", "final", "rng_before", "rng_after"},
            "Original before/ready/final and both RNG boundary captures",
        )
        for label, pin in record["captures"].items():
            raw, pins = comparison.codec._capture(reader, pin)
            node = comparison.codec.wire(raw, pins)
            if label.startswith("rng_"):
                require(node["kind"] == "tuple" and len(node["items"]) == 2, "Both RNG boundaries")
                comparison._full_rng(dict(numpy=node["items"][0], python=node["items"][1]))
        require(
            set(record["lineage"]["facts"]) == set(comparison.LINEAGE)
            and all(v is True for v in record["lineage"]["facts"].values()),
            "Complete actual lineage witness",
        )
        lineage = record["lineage"]
        identities = lineage["process_local_identities"]
        require(
            set(identities)
            == {"phase", "sim", "cells", "old_p", "current_p", "handler", "callback"}
            and all(type(v) is int and v > 0 for v in identities.values())
            and len(set(identities.values())) == len(identities)
            and lineage["actual_edges"]
            == [
                ["phase", "sim", "sim"],
                ["phase", "cells", "cells"],
                ["phase", "p", "current_p"],
                ["phase", "dyna", "handler"],
                ["sim", "dyna", "handler"],
            ]
            and lineage["live_owner_or_checkpoint_hydration"] is False,
            "Exact original distinct-root/edge data witness",
        )
        side.update(
            authenticated=True,
            files_bound=True,
            endpoint_complete=True,
            rows=rows,
            calendar=times,
            mode=record["operator_mode"],
            source_operator_mode=record["source_operator_mode"],
            inputs=binding["inputs"]["inventory"],
            input_provenance=comparison.complete_input_provenance(actual_inputs),
            configuration_profile=binding["inputs"]["profile"],
            original_sources=binding["original_sources"],
            lineage=record["lineage"]["facts"],
            initial_rng=dict(available=False),
            error=None,
            input_tree=dict(root=inputs["root"], inventory=actual_inputs),
            prerequisites=["common authenticated pre-SEED authority still unavailable"],
            observation_record=record,
        )
    except Exception as error:
        side["error"] = comparison.codec._issue(error)
    return side
