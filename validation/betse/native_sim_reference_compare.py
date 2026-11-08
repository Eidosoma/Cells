"""Read-only SIM history reports; completion, observations and parity are separate.

Original terminal evidence is authenticated against its adopted source/review,
runtime, input and full-loop/context graph. The issued reader separately needs
an independently accepted observer pin. Neither reader imports NumPy or model
code or constructs live owners; source comparison grants no numerical parity.
"""

import argparse
import ast
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from types import CodeType, FunctionType, ModuleType

from validation import source_snapshot as snapshot
from validation.betse import native_init_terminal_reference_compare as codec
from validation.betse import native_rng_runtime as rng_runtime
from validation.betse import native_seed_demo_inputs as input_files
from validation.betse import native_seed_demo_report as report
from validation.betse import native_seed_rng_compare as rng_adapter
from validation.betse import native_seed_rng_report as rng_report

KIND = "cells.original_SIM_saved_history_comparison@1"
REF_KIND = "cells.original_SIM_retained_INIT_reference@2"
OBSERVATION_KIND = "cells.original_SIM_iteration_observation@2"
RNG_ADAPTER_SHA256 = "9e8e9539198141e7f76aefc5dba24a52eb9faa3e03f5ae202320bdfafa811a37"
DEMO_REPORT_SHA256 = "9c9f82605a514e69cc3a1622d2cb0f529e09fcb6e13cdea3850dca5677cadf90"
REFERENCE_RNG_AST_SHA256 = "bebf472b9446953873e55d1db1599473c26b099fcb81a310b24630201cc34eb5"
CODEC_SHA256 = "aa65bef81121791d3d738988e1c575c1f976d59c189c8c36e6a1c85946478037"
INPUT_READER_SHA256 = "a5ca1df6c7c56b6bc46eaf39981bdf5a33780e7b79c936dbbd526c4cd5dc0c6d"
RNG_RUNTIME_SHA256 = "6ddb846ef3a20e9ff95fb2e546a39329e8d305b821bfedadf344fce9fe548315"
RNG_REPORT_SHA256 = "d2966c2d1d60486a341e1a04eecc82b40c18a9012bc6b7ea4a491b5577b589b3"
STARTING_REPORT_KIND = "cells.authenticated_starting_rng_saved_report@1"
RNG_MODULES = (
    "numpy",
    "numpy.random",
    "numpy.random.mtrand",
    "numpy.random._mt19937",
    "numpy.random.bit_generator",
    "random",
    "_random",
)
EPOCH = "original_full_SIM_body_end_before_next_FOR_ITER"
MAX_STEPS = 512
GROUPS = ("voltage", "concentrations", "fluxes", "gates", "fields", "clock", "events", "rng")
INITIAL_EPOCH = "pre_SEED_before_world_construction"
LINEAGE = (
    "old_and_current_p_distinct",
    "sim_retained",
    "cells_retained",
    "fresh_SIM_phase",
    "one_shot_INIT_consumed",
)
REF_PRODUCERS = {
    "validation/betse/native_sim_reference.py": (
        "14f6b31277bd7c933526abdd20f76fe41c4ae038304b1ae01c9baa26ec878840"
    ),
    "validation/betse/native_sim_reference_source.py": (
        "0088ba3200ee96f2f344a1027adb4cbf72b8bef5d4f521cab6c4f588098898d1"
    ),
    "validation/betse/native_sim_reference_software.py": (
        "35256de3403b121fb96164452e3148384e3f58401b9f8200aa0f43283ca8bba8"
    ),
    "tests/unit/test_native_sim_reference.py": (
        "306150772b069a55342694265a2282a9d66a2220e5666b048f5547ea265dde6f"
    ),
}
ISSUED_SIM_PRODUCER_KIND = None
COMMON_START_FILE = "validation/betse/native_common_start_rng.py"
COMMON_START_KIND = "cells.explicit_fresh_common_start_rng_program@1"
COMMON_START_REPORT_KIND = "cells.authenticated_common_start_saved_report@1"
COMMON_START_SHA256 = "b52c20c4ede1fc9afbcefd9f22e65626156852cae552a12c14837e65dd1b9eb4"
COMMON_START_REVIEW_SHA256 = "58e4090dfaf544435bd132b703e470d59d49381ade83ea25a7ab0fe3a919d72e"
SIM_REPORT_SHA256 = "9c86d1e85cefb60d8b4031af9693c362e5ba9493fbfa2579d5b5bea28df29964"
SIM_REPORT_REVIEW_SHA256 = "a413fdf49c7eb85fa3d62c848706a9201d246381598eac60a0e08c6ec2f8e76c"
SIM_LAUNCH_SHA256 = "86acc72b17ecc7a85ac4e17eeeb1576dfefe6414936bddd9f864a0e0f5e47fc4"
SIM_OBSERVATION_SHA256 = "98221ffbd440d80eccfa761c60e3ad1b193609634ad26e947e48ba2e6f8d3a28"
require, same = codec.require, codec._same


def source_plan():
    return dict(
        kind=KIND,
        epoch=EPOCH,
        groups=list(GROUPS),
        max_steps=MAX_STEPS,
        read_only_stdlib_and_existing_codecs=True,
        live_owner_or_checkpoint_hydration=False,
        original_and_omitted_flux_modes_separate=True,
        searched_epoch_shift=False,
        exact_raw_bits_dtype_layout=True,
        tolerance=None,
        source_completion_is_not_numerical_or_physical_admission=True,
        mismatched_or_missing_initial_authority_refuses_parity=True,
        pending_producers=[
            "explicit original SIM source and per-execution review adoption",
            "explicit accepted Key completion producer/review on the issued side",
            "independent common pre-SEED starting authority remains unavailable",
        ],
        numerical_physical_or_restart_credit=0,
        issued_SIM_producer_kind=ISSUED_SIM_PRODUCER_KIND,
        initial_rng_wire_adapter=dict(
            module="validation.betse.native_seed_rng_compare",
            sha256=RNG_ADAPTER_SHA256,
            authority_granted=False,
        ),
        starting_rng_saved_readers=dict(
            report_kind=STARTING_REPORT_KIND,
            demo_report_sha256=DEMO_REPORT_SHA256,
            original_reader_sha256=CODEC_SHA256,
            original_producer_normalized_ast_sha256=REFERENCE_RNG_AST_SHA256,
            input_reader_sha256=INPUT_READER_SHA256,
            runtime_provenance_helper=dict(file=rng_runtime.FILE, sha256=RNG_RUNTIME_SHA256),
            complete_input_inventory=True,
            executable_and_rng_runtime_origins=list(RNG_MODULES),
            actual_distinct_constructor_orders_retained=True,
            final_file_and_request_rebinding=True,
            complete_SIM_or_common_start_authority=False,
        ),
        common_start_saved_reader=dict(
            kind=COMMON_START_REPORT_KIND,
            helper=COMMON_START_FILE,
            helper_sha256=COMMON_START_SHA256,
            review_sha256=COMMON_START_REVIEW_SHA256,
            ambient_default_unchanged=True,
            actual_program_return_and_durable_publication=True,
            linked_pre_world_witness_bits=True,
            RNG_or_model_import_or_execution=False,
            numerical_or_physical_credit=0,
        ),
    )


def _empty():
    return dict(
        authenticated=False,
        files_bound=False,
        endpoint_complete=False,
        error=None,
        rows=[],
        reader=_report_api().Reader(),
        failure=None,
        initial_rng=dict(available=False),
    )


def _full_rng(value):
    """Validate complete typed MT observations; no state decoding or reset."""
    require(
        type(value) is dict and set(value) == {"numpy", "python"}, "Both full RNG states required"
    )
    np_state, py_state = value["numpy"], value["python"]
    require(
        np_state.get("kind") == "tuple" and len(np_state["items"]) == 5,
        "Complete NumPy MT state required",
    )
    name, words, position, flag, gauss = np_state["items"]
    require(
        codec._scalar(name, "str") == "MT19937"
        and words.get("kind") == "array"
        and words["layout"]["dtype"] in ("<u4", ">u4")
        and words["layout"]["shape"] == [624]
        and words["bytes"]["size"] == 2496
        and report._hash_identity(words["bytes"]["sha256"])
        and 0 <= codec._scalar(position, "int") <= 624
        and codec._scalar(flag, "int") in (0, 1),
        "Exact NumPy MT words/index/cache flag",
    )
    codec._f64(gauss)
    require(
        py_state.get("kind") == "tuple" and len(py_state["items"]) == 3,
        "Complete Python random state required",
    )
    version, words, cache = py_state["items"]
    require(
        codec._scalar(version, "int") == 3
        and words.get("kind") == "tuple"
        and len(words["items"]) == 625,
        "Full Python MT words required",
    )
    require(
        all(0 <= codec._scalar(word, "int") <= 0xFFFFFFFF for word in words["items"][:624])
        and 0 <= codec._scalar(words["items"][-1], "int") <= 624,
        "Python MT word/index extent",
    )
    if cache.get("kind") != "NoneType":
        codec._f64(cache)
    else:
        require(cache.get("value") is None, "Exact absent Python Gaussian cache")
    return value


def _presence(node, names):
    values = codec._mapping(node)
    require(set(values) == set(names), "Exact native field-presence roster required")
    for value in values.values():
        entry = codec._mapping(value)
        present = codec._scalar(entry["present"], "bool")
        require(
            set(entry) == ({"present", "value"} if present else {"present"}),
            "Native absence cannot be zero-filled or silently omitted",
        )


def _rich_groups(values, time):
    gates = codec._mapping(values["gates"])
    _presence(gates["gap_junction"], ("gjopen", "gj_block", "vgj"))
    _presence(gates["gap_junction_core"], ("alpha", "beta", "gjopen"))
    for name in ("molecules", "grn"):
        network = codec._mapping(gates[name])
        enabled = codec._scalar(network["enabled"], "bool")
        require(
            set(network) == ({"enabled", "channels"} if enabled else {"enabled", "source_branch"}),
            "Actual native enabled/disabled channel branch required",
        )
        if enabled:
            require(network["channels"]["kind"] == "list", "Actual ordered native channel list")
            seen = set()
            for item in network["channels"]["items"]:
                channel = codec._mapping(item)
                require(
                    set(channel) == {"name", "core_type", "fields"}, "Exact native channel record"
                )
                key = codec._scalar(channel["name"], "str")
                require(key not in seen, "No duplicate native channel observation")
                seen.add(key)
                codec._scalar(channel["core_type"], "str")
                codec._mapping(channel["fields"])
    _presence(
        values["electric_fields"],
        ("E_cell_x", "E_cell_y", "E_env_x", "E_env_y", "Emc", "Eme", "v_env", "Phi_b"),
    )
    events = codec._mapping(values["events"])
    require(
        events["calls"]["kind"] == "list" and len(events["calls"]["items"]) <= 512,
        "Bounded ordered actual event calls required",
    )
    codec._mapping(events["global_options"])
    codec._mapping(events["scheduled_options"])
    for name in ("event_cut", "voltage_event"):
        event = codec._mapping(events[name])
        present = codec._scalar(event["present"], "bool")
        require(
            set(event) == ({"present", "fields"} if present else {"present"}),
            "Actual optional native event object state",
        )
        if present:
            codec._mapping(event["fields"])
    for item in events["calls"]["items"]:
        entry = codec._mapping(item)
        require(
            set(entry)
            == {
                "ordinal",
                "module",
                "method",
                "boundary",
                "source_time",
                "is_fired",
                "error_type",
                "cause_type",
            },
            "Exact original event-body boundary",
        )
        require(
            codec._scalar(entry["ordinal"], "int") > 0
            and codec._scalar(entry["boundary"], "str") in ("enter", "return", "unwind")
            and codec._f64(entry["source_time"]) == time,
            "Event observations must retain their actual SIM iteration epoch",
        )
        codec._scalar(entry["module"], "str")
        codec._scalar(entry["method"], "str")
        _presence(
            dict(kind="dict", items=[[dict(kind="str", value="event"), entry["is_fired"]]]),
            ("event",),
        )


def _read_row(reader, pin, ordinal, *, required_observation=False):
    raw, pins = codec._capture(reader, pin)
    values = codec._mapping(codec.wire(raw, pins))
    base = {
        "ordinal",
        "source_time",
        "sampled",
        "configured_dt",
        "fields",
        "numpy_random",
        "python_random",
    }
    rich = base | {"observation_contract", "gates", "electric_fields", "events"}
    require(
        set(values) in (base, rich),
        "Exact SIM iteration wire roster",
    )
    require(
        not required_observation or set(values) == rich,
        "Current original SIM producer must retain all declared observation groups",
    )
    require(
        codec._scalar(values["ordinal"], "int") == ordinal + 1,
        "Actual original one-based SIM ordinal required",
    )
    fields = codec._mapping(values["fields"])
    require(set(fields) <= set(codec.FIELDS), "Undeclared original SIM observation field")
    groups = {}
    for name, roster in (
        ("voltage", ("vm",)),
        ("concentrations", ("cc_cells", "cc_env", "cc_at_mem")),
        ("fluxes", ("fluxes_mem", "fluxes_gj", "fluxes_env_x", "fluxes_env_y")),
    ):
        groups[name] = {key: fields[key] for key in roster} if set(roster) <= set(fields) else None
    time, dt = codec._f64(values["source_time"]), codec._f64(values["configured_dt"])
    sampled = codec._scalar(values["sampled"], "bool")
    groups.update(
        gates=None,
        fields=None,
        events=None,
        clock=dict(source_time_bits=time, dt_bits=dt, sampled=sampled),
        rng=_full_rng(dict(numpy=values["numpy_random"], python=values["python_random"])),
    )
    if set(values) == rich:
        require(
            codec._scalar(values["observation_contract"], "str") == OBSERVATION_KIND,
            "Exact native SIM observation boundary required",
        )
        require(
            set(codec._mapping(values["gates"]))
            == {"gap_junction", "gap_junction_core", "molecules", "grn"},
            "Complete declared native gate observation roster",
        )
        require(
            set(codec._mapping(values["events"]))
            == {"calls", "global_options", "scheduled_options", "event_cut", "voltage_event"},
            "Complete declared event observation roster",
        )
        _rich_groups(values, time)
        groups.update(
            gates=values["gates"], fields=values["electric_fields"], events=values["events"]
        )
    return dict(
        ordinal=ordinal,
        epoch=EPOCH,
        source_time_bits=time,
        dt_bits=dt,
        sampled=sampled,
        groups=groups,
    )


def _rng_api():
    """Authenticate the read-only helper before invoking any of its delegates."""
    path = Path(rng_adapter.__file__)
    raw = path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == RNG_ADAPTER_SHA256,
        "Explicit reviewed starting-RNG helper producer required",
    )
    unit = compile(raw, str(path), "exec", dont_inherit=True)
    codes = {item.co_name: item for item in unit.co_consts if type(item) is CodeType}
    for name, code in codes.items():
        actual = vars(rng_adapter).get(name)
        require(
            type(actual) is FunctionType
            and actual.__globals__ is vars(rng_adapter)
            and actual.__code__ == code
            and actual.__closure__ is None
            and actual.__defaults__ is None
            and actual.__kwdefaults__ is None,
            "Starting-RNG helper callable/code authority changed",
        )
    constants = {}
    for node in ast.parse(raw).body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    require(
        all(
            type(vars(rng_adapter).get(name)) is type(value) and vars(rng_adapter)[name] == value
            for name, value in constants.items()
        ),
        "Starting-RNG helper constant authority changed",
    )
    require(rng_adapter.hashlib is hashlib, "Starting-RNG helper hashing global changed")
    return rng_adapter


def _data(node):
    """Only scalar/container metadata; no numeric owner or array hydration."""
    kind = node.get("kind")
    if kind in ("str", "int", "bool", "NoneType"):
        return codec._scalar(node, kind)
    if kind == "dict":
        return {name: _data(value) for name, value in codec._mapping(node).items()}
    require(kind in ("list", "tuple"), "Declared scalar/container metadata only")
    values = [_data(value) for value in node["items"]]
    return tuple(values) if kind == "tuple" else values


def _reader_function(actual, code, node, namespace):
    def value(expression):
        if (
            isinstance(expression, ast.Subscript)
            and isinstance(expression.value, ast.Attribute)
            and isinstance(expression.value.value, ast.Name)
            and expression.value.value.id == "legacy"
            and expression.value.attr in ("DEMO_KINDS", "LAUNCH_KINDS")
            and isinstance(expression.slice, ast.Constant)
            and type(expression.slice.value) is int
            and expression.slice.value == 6
        ):
            require(namespace.get("legacy") is report, "Immutable legacy default namespace changed")
            return getattr(_report_api(), expression.value.attr)[6]
        if (
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.value.id == "profiles"
            and expression.attr in ("ORIGINAL", "HEADLESS")
        ):
            return {"ORIGINAL": "original", "HEADLESS": "headless"}[expression.attr]
        return ast.literal_eval(expression)

    defaults = tuple(value(item) for item in node.args.defaults) or None
    keywords = {
        arg.arg: value(item)
        for arg, item in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
        if item is not None
    } or None
    require(
        type(actual) is FunctionType
        and actual.__globals__ is namespace
        and actual.__code__ == code
        and actual.__closure__ is None
        and same(actual.__defaults__, defaults)
        and same(actual.__kwdefaults__, keywords),
        "Saved-reader callable/code/default authority changed",
    )


def _report_api():
    """Use the exact reviewed saved-file parser, never a model evaluator."""
    path = Path(report.__file__)
    raw = path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == DEMO_REPORT_SHA256,
        "Explicit reviewed demo@8 saved-file reader required",
    )
    unit = compile(raw, str(path), "exec", dont_inherit=True)
    declared = {
        node.name: node
        for node in ast.parse(raw).body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    for code in (
        item for item in unit.co_consts if type(item) is CodeType and item.co_name in declared
    ):
        actual = vars(report).get(code.co_name)
        if code.co_name == "Reader":
            require(
                type(actual) is type
                and actual.__mro__ == (actual, object)
                and actual.__new__ is object.__new__
                and actual.__getattribute__ is object.__getattribute__
                and not hasattr(actual, "__getattr__"),
                "Demo reader dispatch changed",
            )
            methods = {
                node.name: node
                for node in declared["Reader"].body
                if isinstance(node, ast.FunctionDef)
            }
            for member in (v for v in code.co_consts if type(v) is CodeType):
                _reader_function(
                    vars(actual).get(member.co_name),
                    member,
                    methods[member.co_name],
                    vars(report),
                )
        else:
            _reader_function(actual, code, declared[code.co_name], vars(report))
    require(
        report.hashlib is hashlib and report.snapshot is snapshot,
        "Demo reader hashing/snapshot globals changed",
    )
    return report


def _source_reader(module, expected):
    path = Path(module.__file__)
    raw = path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == expected,
        "Explicit saved-source reader revision required",
    )
    tree = ast.parse(raw)
    declared = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    code = compile(raw, str(path), "exec", dont_inherit=True)
    for item in code.co_consts:
        if type(item) is CodeType and item.co_name in declared:
            _reader_function(
                vars(module).get(item.co_name), item, declared[item.co_name], vars(module)
            )
    imports = {
        alias.asname or alias.name.split(".")[0]
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    for name, actual in (("hashlib", hashlib), ("snapshot", snapshot), ("Path", Path)):
        if name in imports:
            require(
                vars(module).get(name) is actual,
                "Saved-reader hashing/path/snapshot globals changed",
            )
    return module


def _sim_report_api():
    """Authenticate the accepted SIM reader and its reached read-only helpers."""
    require(report._hash_identity(SIM_REPORT_REVIEW_SHA256), "Reviewed SIM reader remains held")
    sim_report = importlib.import_module("validation.betse.native_sim_demo_report")
    sim_launch = importlib.import_module("validation.betse.native_seed_demo_launch")
    sim_observation = importlib.import_module("validation.betse.native_sim_demo_observation")
    for module, name in (
        (sim_report, "native_sim_demo_report"),
        (sim_launch, "native_seed_demo_launch"),
        (sim_observation, "native_sim_demo_observation"),
    ):
        require(
            type(module) is ModuleType
            and sys.modules.get("validation.betse." + name) is module
            and Path(module.__file__).resolve() == Path(__file__).parent / (name + ".py"),
            "Actual loaded SIM metadata producer required",
        )
    api = _source_reader(sim_report, SIM_REPORT_SHA256)
    _source_reader(sim_observation, SIM_OBSERVATION_SHA256)
    require(
        api.legacy is report
        and api.rng_report is rng_report
        and api.launch is sim_launch
        and api.observation is sim_observation
        and sim_launch.sim_observation is sim_observation
        and api.evidence is report.evidence
        and api.Reader is report.Reader
        and api.require is report.require
        and api._hash_identity is report._hash_identity
        and api._iterations is report._iterations
        and api.LEGACY_SHA256 == DEMO_REPORT_SHA256,
        "SIM reader shared namespace/dispatch changed",
    )
    path = Path(sim_launch.__file__)
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SIM_LAUNCH_SHA256, "SIM launch reader changed")
    tree = ast.parse(raw)
    declarations = {
        node.targets[0].id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }

    def integer(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        require(isinstance(node, ast.BinOp), "Closed source policy integer required")
        left, right = integer(node.left), integer(node.right)
        require(0 <= left <= 2**64 and 0 <= right <= 2**64, "Bounded source policy integer")
        if isinstance(node.op, ast.Pow):
            require(right <= 64, "Bounded source policy exponent")
            value = left**right
        else:
            require(isinstance(node.op, ast.Mult), "Exact policy arithmetic required")
            value = left * right
        require(value <= 2**64, "Bounded source policy value")
        return value

    policy = declarations["POLICY"]
    require(
        isinstance(policy, ast.Call)
        and isinstance(policy.func, ast.Name)
        and policy.func.id == "dict"
        and not policy.args
        and all(type(key.arg) is str for key in policy.keywords),
        "Exact pinned source policy declaration required",
    )
    expected_policy = {key.arg: integer(key.value) for key in policy.keywords}
    require(
        type(sim_launch.POLICY) is dict
        and set(sim_launch.POLICY) == set(expected_policy)
        and all(
            type(sim_launch.POLICY[name]) is int and sim_launch.POLICY[name] == value
            for name, value in expected_policy.items()
        ),
        "Pinned SIM resource policy values changed",
    )
    for name in (
        "SIM_GATES",
        "ACQUISITION_SEQUENCE",
        "DIAGNOSTIC_WALL_SECONDS",
        "STACK_INTERVAL_SECONDS",
        "RELEASE",
        "DEMO_RELEASE",
    ):
        expected = ast.literal_eval(declarations[name])
        actual = vars(sim_launch).get(name)
        require(
            type(actual) is type(expected) and same(actual, expected),
            "Pinned SIM release/policy value changed: " + name,
        )
        if type(expected) is tuple:
            require(all(type(value) is str for value in actual), "Exact source policy strings")
    observer_tree = ast.parse(Path(sim_observation.__file__).read_bytes())
    for node in observer_tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("RELEASE", "HISTORY_RELEASE")
        ):
            name, expected = node.targets[0].id, ast.literal_eval(node.value)
            require(
                type(vars(sim_observation).get(name)) is str
                and vars(sim_observation)[name] == expected,
                "Pinned SIM observation release value changed: " + name,
            )
    require(
        sim_launch.ast is ast and sim_launch.snapshot is snapshot and sim_launch.Path is Path,
        "SIM policy reader namespace changed",
    )
    names = {
        "require",
        "source_plan",
        "_wall_seconds",
        "_hash",
        "_environment_map",
        "_producers",
        "_sim_contract",
    }
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    codes = {
        c.co_name: c
        for c in compile(raw, str(path), "exec", dont_inherit=True).co_consts
        if type(c) is CodeType
    }
    for name in names:
        _reader_function(vars(sim_launch).get(name), codes[name], nodes[name], vars(sim_launch))
    require(
        api.LAUNCH_KIND == sim_launch.SIM_KIND == "cells.genuine_seed_demo_detached_launch@13"
        and api.DEMO_KIND
        == sim_launch.SIM_DEMO_KIND
        == "cells.genuine_seed_core_profiles_junctions_demo@9"
        and api.ENDPOINT == sim_launch.SIM_ENDPOINT == "sim_terminal",
        "Exact SIM metadata schemas required",
    )
    return api


def _rng_side():
    return dict(
        authenticated=False,
        available=False,
        reader=None,
        error=None,
        failure=None,
        wire=None,
        witness=None,
        common_starting_authority_established=False,
        numerical_parity_available=False,
    )


def demo_starting_rng(request):
    """Authenticate a genuine legacy or full-SIM saved starting prefix."""
    side = _rng_side()
    try:
        api = _report_api()
        side["reader"] = api.Reader()
        reader = side["reader"]
        require(
            type(request) is dict and set(request) == {"plan", "outcome"},
            "Exact demo starting-RNG saved-file request required",
        )
        outcome = reader.bound(request["outcome"])
        side["failure"] = dict(
            status=outcome.get("status"),
            primary=outcome.get("primary"),
            secondary=outcome.get("secondary"),
            stage=outcome.get("stage"),
        )
        full_sim = outcome.get("kind") == "cells.genuine_seed_core_profiles_junctions_demo@9"
        require(
            full_sim or outcome.get("kind") == "cells.genuine_seed_core_profiles_junctions_demo@8",
            "Starting RNG requires actual demo@8 or SIM demo@9 outcome",
        )
        versioned = (
            _source_reader(rng_report, RNG_REPORT_SHA256)
            if report._hash_identity(RNG_REPORT_SHA256)
            else None
        )
        sim = _sim_report_api() if full_sim else None
        plan, files, _ = (
            sim._plan(reader, Path(request["plan"]["path"]), request["plan"]["sha256"])
            if full_sim
            else (
                api._plan(reader, Path(request["plan"]["path"]), request["plan"]["sha256"])
                if versioned is None
                else versioned.read_plan(
                    reader, Path(request["plan"]["path"]), request["plan"]["sha256"]
                )
            )
        )
        require(
            plan["kind"]
            == (
                "cells.genuine_seed_demo_detached_launch@13"
                if full_sim
                else "cells.genuine_seed_demo_detached_launch@12"
            )
            and plan.get("_demo_kind") == outcome["kind"],
            "Actual launch/outcome schema association",
        )
        demo_root = Path(request["outcome"]["path"]).parent
        failure_path = demo_root / "failure.json"
        if failure_path.exists():
            side["failure"]["retained_failure"] = reader.read(failure_path)
        require(
            Path(request["outcome"]["path"]).name == "outcome.json"
            and demo_root.name == "demo"
            and demo_root.parent.name == "worker",
            "Actual demo outcome/worker path required",
        )
        selected = [
            row
            for row in outcome["captures"]
            if row["label"] in ("before_seed_random_states", "pre_seed_rng_witness")
        ]
        checked = sim._outcome(reader, demo_root, plan, outcome) if full_sim else None
        captures = checked["captures"] if full_sim else api._captures(reader, demo_root, selected)
        observed = (
            checked["initial_rng"]
            if full_sim
            else (
                api._initial_rng_captures(reader, demo_root, plan, outcome, captures)
                if versioned is None
                else versioned.initial_rng_captures(reader, demo_root, plan, outcome, captures)
            )
        )
        require(
            observed is not None and observed.get("observed") is True,
            "Starting observation unavailable; never infer a state from later history",
        )
        parameters = reader.bound(plan["parameter_inputs"])
        program = reader.bound(parameters["program"]["manifest"])
        input_root = Path(parameters["program"]["root"])
        actual = _source_reader(input_files, INPUT_READER_SHA256).inventory(input_root)
        expected = plan["_initial_rng_inputs"]["inventory"]
        allowed = set(expected["directories"])
        for name in program.get("directories", []):
            directory = Path(name)
            require(
                directory.is_relative_to(input_root), "Declared native directory escaped inputs"
            )
            while directory != input_root:
                allowed.add(str(directory.relative_to(input_root)))
                directory = directory.parent
        require(
            actual["files"] == expected["files"]
            and set(expected["directories"]) <= set(actual["directories"]) <= allowed,
            "Complete actual demo input inventory changed",
        )
        resources = (sim if full_sim else api)._resources(
            reader,
            demo_root.parent.parent,
            request["plan"]["path"],
            plan,
            request["plan"]["sha256"],
            None,
        )
        require(resources["sampled_limits_met"] is True, "Starting-RNG guarded resource failure")
        runtime = (
            sim._runtime(reader, demo_root.parent, plan, files)
            if full_sim
            else (
                api._runtime(reader, demo_root.parent, plan, files)
                if versioned is None
                else versioned.runtime_evidence(reader, demo_root.parent, plan, files)
            )
        )
        values = {
            row["label"]: row["initial_rng_wire"]
            for row in captures
            if row["label"] in ("before_seed_random_states", "pre_seed_rng_witness")
        }
        wire = values["before_seed_random_states"]
        witness = values["pre_seed_rng_witness"]
        _rng_api().demo_state(wire)
        side.update(
            authenticated=True,
            available=True,
            wire=wire,
            witness=witness,
            resources=resources,
            runtime=runtime,
            authentication_scope="starting observation only",
            complete_SIM=False,
            input_tree=dict(root=str(input_root), inventory=actual),
            common_context=dict(
                plan=reader.bound(plan["demo_plan"]),
                outcome=outcome,
                output=str(demo_root),
                source=plan["source"],
            ),
        )
    except Exception as error:
        side["error"] = codec._issue(error)
    return side


def _reference_reader():
    _source_reader(codec, CODEC_SHA256)
    checker = FunctionType(
        codec._reference_source.__code__,
        dict(vars(codec), REFERENCE_AST_SHA256=REFERENCE_RNG_AST_SHA256),
    )
    return FunctionType(codec._reference.__code__, dict(vars(codec), _reference_source=checker))


def _runtime_witness(reader, value, actual):
    if type(value) is dict and value.get("kind") == "cells.rng_runtime_provenance@2":
        api = _source_reader(rng_runtime, RNG_RUNTIME_SHA256)
        reader.bind(dict(path=str(Path(api.__file__)), sha256=RNG_RUNTIME_SHA256))
        api.match_inventory(value, actual)
        reader.bind(value["executable"])
        for pin in value["files"].values():
            reader.bind(pin)
        return
    require(
        type(value) is dict
        and set(value) == {"python", "executable", "numpy_version", "files"}
        and type(value["python"]) is str
        and value["python"]
        and type(value["numpy_version"]) is str
        and value["numpy_version"]
        and value["python"] == actual["python"]
        and value["executable"] == actual["executable"]
        and type(value["files"]) is dict
        and set(value["files"]) == set(RNG_MODULES),
        "Exact executable and seven starting-RNG runtime origins required",
    )
    reader.bind(value["executable"])
    for name, pin in value["files"].items():
        reader.bind(pin)
        require(actual["loaded_files"].get(name) == pin, "Starting RNG/runtime origin changed")


def reference_starting_rng(request):
    """Authenticate original-reference captures without importing its producer."""
    side = _rng_side()
    try:
        _report_api()
        parent = _reference_reader()(request)
        side["reader"] = parent["reader"]
        reader = side["reader"]
        # Preserve failed parent records even when the wider verifier refuses.
        worker = reader.bound(request["worker"])
        side["failure"] = dict(
            status=worker.get("status"),
            primary=worker.get("primary"),
            capture_errors=worker.get("capture_errors"),
        )
        require(
            parent.get("authenticated") is True,
            "Original reference source/input/runtime/resource graph unavailable: "
            + str(parent.get("error")),
        )
        plan = parent["plan"]
        captures = worker["captures"]
        labels = ("before_seed_random_states", "pre_seed_rng_witness")
        selected = [row for row in captures if row["label"] in labels]
        require(
            len(selected) == 2
            and [row["label"] for row in selected] == list(labels)
            and all(row["status"] == "saved" for row in selected)
            and captures.index(selected[1]) == captures.index(selected[0]) + 1,
            "Actual consecutive original before-state/witness captures required",
        )
        require(
            worker.get("initial_rng_observation") == selected[1]["files"][0],
            "Original outcome must point at its actual pre-SEED witness",
        )
        state, state_pins = codec._capture(reader, selected[0]["files"][0])
        witness_raw, witness_pins = codec._capture(reader, selected[1]["files"][0])
        witness_nodes = codec._mapping(codec.wire(witness_raw, witness_pins))
        require(
            set(witness_nodes)
            == {
                "kind",
                "epoch",
                "common_binding",
                "state",
                "source",
                "order",
                "observed_states_equalized",
                "common_starting_authority_established",
                "scientific_physical_checkpoint_credit",
            },
            "Exact original witness roster",
        )
        witness = {name: _data(value) for name, value in witness_nodes.items() if name != "state"}
        raw_fields = {key["value"]: value for key, value in witness_raw["tree"]["values"]}
        witness_state = dict(tree=raw_fields["state"], columns=witness_raw["columns"])
        api = _rng_api()
        normalized = api.reference_state(state)
        require(
            normalized == api.reference_state(witness_state),
            "Original witness/state exact bytes differ",
        )
        witness["state"] = witness_state
        require(
            witness["kind"]
            in ("cells.common_initial_rng_observation@1", "cells.common_initial_rng_observation@2")
            and witness["epoch"] == INITIAL_EPOCH
            and witness["observed_states_equalized"] is False
            and witness["common_starting_authority_established"] is False
            and type(witness["scientific_physical_checkpoint_credit"]) is int
            and witness["scientific_physical_checkpoint_credit"] == 0,
            "Original starting witness is observation only",
        )
        common = witness["common_binding"]
        require(
            set(common) == {"input_inventory_sha256", "mode", "profile", "runtime"}
            and common["input_inventory_sha256"] == codec.saved._seal(plan["inputs"]["inventory"])
            and common["mode"] == plan["inputs"]["mode"]
            and common["profile"] == plan["source_plan"]["input_profile"],
            "Original full input/profile/mode binding changed",
        )
        expected_source = dict(
            reference_sha256=plan["execution_source"]["owned_files"][codec.REF_SOURCE],
            snapshot_sha256=plan["execution_source"]["snapshot_sha256"],
            native_inventory_sha256=plan["native_inventory_sha256"],
            original_critical_pins=plan["source_plan"]["critical_source_pins"],
        )
        if witness["kind"] == "cells.common_initial_rng_observation@2":
            require(
                report._hash_identity(RNG_RUNTIME_SHA256), "Reviewed RNG provenance helper held"
            )
            expected_source["files"] = {rng_runtime.FILE: RNG_RUNTIME_SHA256}
            require(
                common["runtime"].get("kind") == "cells.rng_runtime_provenance@2",
                "Original builtin witness/runtime versions differ",
            )
            reader.bind(
                dict(
                    path=str(Path(plan["execution_source"]["root"]) / rng_runtime.FILE),
                    sha256=RNG_RUNTIME_SHA256,
                )
            )
        require(
            witness["source"] == expected_source,
            "Original witness producer/snapshot/source association changed",
        )
        order = witness["order"]
        require(
            set(order)
            == {
                "boundary",
                "stage",
                "parameter_identity",
                "runner_identity",
                "same_parameter",
                "seed_entered",
                "selected_boundaries",
                "native_sites",
            }
            and order["boundary"]
            == "after_original_Parameters.make_and_SimRunner_before_runner.seed"
            and order["stage"] == "original_runner"
            and order["same_parameter"] is True
            and order["seed_entered"] is False
            and all(
                type(order[name]) is int and order[name] > 0
                for name in ("parameter_identity", "runner_identity")
            ),
            "Actual original pre-SEED constructor epoch required",
        )
        require(
            type(order["selected_boundaries"]) is list
            and all(
                type(row) in (list, tuple) and len(row) == 5 for row in order["selected_boundaries"]
            )
            and not any(
                tuple(row[2:4])
                in (("betse.science.simrunner", "seed"), ("betse.science.simrunner", "init"))
                for row in order["selected_boundaries"]
            ),
            "Original pre-SEED work contains later source",
        )
        require(
            same(
                order["selected_boundaries"],
                worker.get("work", [])[: len(order["selected_boundaries"])],
            )
            and order["parameter_identity"] != order["runner_identity"],
            "Original witness must retain the actual earlier work prefix and distinct roots",
        )
        require(
            type(order["native_sites"]) is list
            and all(
                type(row) is dict
                and set(row) == {"site", "counts"}
                and len(row["site"]) == 4
                and len(row["counts"]) == 4
                for row in order["native_sites"]
            ),
            "Original bounded native work roster required",
        )
        final_sites = {tuple(row["site"]): row["counts"] for row in worker.get("work_sites", [])}
        require(
            len(final_sites) == len(worker.get("work_sites", [])),
            "Unique final original native sites",
        )
        for row in order["native_sites"]:
            key = tuple(row["site"])
            counts = row["counts"]
            after = final_sites.get(key)
            require(
                key[3] not in ("SEED", "INIT", "SIM")
                and type(key[2]) is int
                and key[2] > 0
                and all(type(value) is int and value >= 0 for value in counts)
                and counts[1] <= counts[0]
                and counts[2] <= counts[3]
                and after is not None
                and counts[0] <= after[0]
                and counts[1] <= after[1]
                and counts[2] == after[2]
                and counts[3] <= after[3],
                "Original starting native-site counts do not precede final work",
            )
        constructors = {}
        for module, method, stage in (
            ("betse.science.parameters", "load", "original_parameters"),
            ("betse.science.simrunner", "__init__", "original_runner"),
        ):
            matches = [
                row["counts"]
                for row in order["native_sites"]
                if row["site"][0:2] == [module, method] and row["site"][3] == stage
            ]
            require(
                len(matches) == 1 and matches[0][0] == matches[0][1] and matches[0][0] > 0,
                "Actual completed original parameter/runner construction sites required",
            )
            constructors[stage] = matches[0]
        require(
            constructors["original_parameters"][3] < constructors["original_runner"][2],
            "Original parameter construction must precede its runner",
        )
        _runtime_witness(reader, common["runtime"], parent["runtime"])
        actual_inputs = _source_reader(input_files, INPUT_READER_SHA256).inventory(
            Path(plan["inputs"]["root"])
        )
        require(
            actual_inputs == plan["inputs"]["inventory"],
            "Complete original input file/directory inventory changed",
        )
        process_root = Path(request["controller"]["path"]).parent / "process"
        process = reader.read(
            process_root
            / ("failure.json" if (process_root / "failure.json").exists() else "result.json")
        )
        require(
            process["elapsed_seconds"] <= process["limits"]["max_wall_seconds"]
            and process["sampled_peak_process_tree_rss_bytes"]
            <= process["limits"]["max_process_tree_rss_bytes"]
            and process["minimum_available_host_memory_bytes"]
            >= process["limits"]["min_available_host_memory_bytes"]
            and process["samples"] > 0,
            "Original starting-RNG guarded resource failure",
        )
        side.update(
            authenticated=True,
            available=True,
            wire=state,
            witness=witness,
            authentication_scope="starting observation only",
            complete_SIM=False,
            input_tree=dict(root=plan["inputs"]["root"], inventory=actual_inputs),
            common_context=dict(
                plan=plan,
                outcome=worker,
                output=str(Path(request["worker"]["path"]).parent),
                source=plan["execution_source"]["root"],
            ),
        )
    except Exception as error:
        side["error"] = codec._issue(error)
    return side


def compare_starting_rng_saved(demo, reference):
    """Authenticate only the saved starting prefix, never a SIM completion."""
    sides = dict(demo=demo_starting_rng(demo), reference=reference_starting_rng(reference))
    result = dict(
        kind=STARTING_REPORT_KIND,
        status="unavailable",
        observations_match=None,
        common_starting_authority_established=False,
        numerical_parity_available=False,
        physical_checkpoint_credit=0,
        sides={
            name: dict(
                authenticated=side["authenticated"],
                available=side["available"],
                error=side["error"],
                failure=side["failure"],
            )
            for name, side in sides.items()
        },
    )
    if all(side["authenticated"] and side["available"] for side in sides.values()):
        try:
            observed = compare_initial_rng_records(
                sides["demo"]["wire"],
                sides["reference"]["wire"],
                demo_witness=sides["demo"]["witness"],
                reference_witness=sides["reference"]["witness"],
            )
            result.update(
                status="starting_observation_files_authenticated",
                comparison=observed,
                observations_match=observed["states_equal"] and observed["common_binding_equal"],
            )
        except Exception as error:
            result["comparison_error"] = codec._issue(error)
    drift = {}
    result["file_pins"] = {}
    for name, side in sides.items():
        if side["reader"] is None:
            result["file_pins"][name] = []
            continue
        try:
            if side.get("input_tree") is not None:
                retained = side["input_tree"]
                current = _source_reader(input_files, INPUT_READER_SHA256).inventory(
                    Path(retained["root"])
                )
                require(
                    same(current, retained["inventory"]),
                    "Complete input file/directory inventory changed during authentication",
                )
            for path, digest in tuple(side["reader"].pins.items()):
                side["reader"].bind(dict(path=path, sha256=digest))
        except Exception as error:
            drift[name] = codec._issue(error)
        result["file_pins"][name] = [
            dict(path=path, sha256=digest) for path, digest in sorted(side["reader"].pins.items())
        ]
    if drift:
        previous = result
        result = dict(
            kind=previous["kind"],
            status="evidence_changed_during_starting_rng_authentication",
            observations_match=None,
            common_starting_authority_established=False,
            numerical_parity_available=False,
            physical_checkpoint_credit=0,
            errors=drift,
            unverified_forensics=previous,
            file_pins=previous["file_pins"],
            sides={name: dict(authenticated=False, available=False) for name in sides},
        )
    return result


def _common_program_document(value):
    """Independent saved-data parser; import no RNG or live producer."""
    require(type(value) is dict, "Exact saved common-start program required")
    py, np = value.get("python_seed"), value.get("numpy_seed")
    callers, identity = value.get("consumer_sources"), value.get("input_identity")
    require(
        type(py) is int and 0 <= py < 2**256 and type(np) is int and 0 <= np < 2**32,
        "Bounded explicit seed integers required",
    )
    require(
        type(callers) is dict
        and set(callers) == {"cells", "original"}
        and all(report._hash_identity(pin) for pin in callers.values())
        and report._hash_identity(identity),
        "Both callers and actual input identity required",
    )
    expected = dict(
        kind=COMMON_START_KIND,
        epoch="after_parameters_before_world_construction",
        python_seed=py,
        numpy_seed=np,
        python_seed_version=2,
        numpy_api="legacy global RandomState.seed",
        input_identity=identity,
        consumer_sources=callers,
        operations=[
            ["python_before", "python_get", None],
            ["numpy_before", "numpy_get", None],
            ["python_seed", "python_seed", "python_seed"],
            ["python_after", "python_get", None],
            ["numpy_seed", "numpy_seed", "numpy_seed"],
            ["numpy_after", "numpy_get", None],
            ["python_readback", "python_get", None],
            ["numpy_readback", "numpy_get", None],
        ],
        draws=0,
        setstate_or_generator_replacement=False,
    )
    require(same(value, expected), "Exact public common-start program document required")
    return expected


def _common_record(value, role, witness):
    require(
        type(value) is dict
        and set(value)
        == {
            "kind",
            "status",
            "program",
            "program_identity",
            "role",
            "pid",
            "epoch",
            "source",
            "runtime",
            "generator_identities",
            "state",
            "operations",
            "work",
            "states_loaded",
            "generators_replaced",
            "biological_or_phase_admission",
        },
        "Exact completed public common-start receipt required",
    )
    doc = _common_program_document(value["program"])
    identity = hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    require(
        value["kind"] == COMMON_START_KIND
        and value["status"] == "completed"
        and value["role"] == role
        and value["epoch"] == doc["epoch"]
        and value["program_identity"] == identity
        and type(value["pid"]) is int
        and value["pid"] > 0
        and value["states_loaded"] is value["generators_replaced"] is False
        and value["biological_or_phase_admission"] is False
        and value["operations"] == [[row[0], "returned"] for row in doc["operations"]],
        "Actual complete one-shot input program required; ambient observations do not qualify",
    )
    require(
        value["source"]
        == dict(
            helper=COMMON_START_FILE,
            helper_sha256=COMMON_START_SHA256,
            provenance=rng_runtime.FILE,
            provenance_sha256=RNG_RUNTIME_SHA256,
        ),
        "Exact accepted common-start source/provenance required",
    )
    require(
        type(value["generator_identities"]) is dict
        and set(value["generator_identities"]) == {"python", "numpy"}
        and all(type(i) is int and i > 0 for i in value["generator_identities"].values()),
        "Both original generator identities required",
    )
    require(
        type(value["state"]) is dict
        and set(value["state"])
        == {
            kind + "_" + suffix
            for kind in ("python", "numpy")
            for suffix in ("before", "after", "readback")
        },
        "Complete original before/after/readback state data required",
    )
    states = {}
    for suffix in ("before", "after", "readback"):
        states[suffix] = _rng_api().demo_state(
            dict(
                numpy_random=value["state"]["numpy_" + suffix],
                python_random=value["state"]["python_" + suffix],
                initial_random_reset_or_replacement=False,
            )
        )
    require(same(states["after"], states["readback"]), "Program readbacks changed")
    common = witness["common_binding"]
    require(
        doc["input_identity"] == common["input_inventory_sha256"]
        and same(value["runtime"], common["runtime"]),
        "Program and actual pre-world witness input/runtime differ",
    )
    source = witness["source"]
    caller = (
        source["files"]["validation/betse/native_seed_demo.py"]
        if role == "cells"
        else source["reference_sha256"]
    )
    require(doc["consumer_sources"][role] == caller, "Program has a different actual caller")
    work = value["work"]
    require(
        type(work) is dict
        and work.get("program_API_calls") == 8
        and type(work.get("visible_RNG_observer_events")) is int
        and 0 < work["visible_RNG_observer_events"] <= 256
        and work.get("opaque_C_internals_not_independent_cases") is True
        and work.get("inherited_observer_RNG_effects_require_reviewed_caller_contract") is True,
        "Complete bounded RNG API work required; not input/case credit",
    )
    return states["after"]


def _common_saved_side(side, role):
    require(side["authenticated"] and side["available"], "Authenticated starting prefix required")
    require(
        report._hash_identity(COMMON_START_SHA256)
        and report._hash_identity(COMMON_START_REVIEW_SHA256),
        "Accepted common-start producer/review remains held",
    )
    context, reader = side["common_context"], side["reader"]
    source = Path(context["source"])
    source_pin = (
        context["plan"]["snapshot_sha256"]
        if role == "cells"
        else context["plan"]["execution_source"]["snapshot_sha256"]
    )
    manifest = reader.bound(dict(path=str(source / "SNAPSHOT.json"), sha256=source_pin))
    require(
        manifest["files"][COMMON_START_FILE]["sha256"] == COMMON_START_SHA256,
        "Common-start helper is not in the actual producer image",
    )
    reader.bind(dict(path=str(source / COMMON_START_FILE), sha256=COMMON_START_SHA256))
    rows = context["outcome"]["captures"]
    selected = [row for row in rows if row["label"] == "common_start_rng"]
    require(
        len(selected) == 1 and selected[0]["status"] == "saved",
        "Actual saved common-start source return required",
    )
    before = next(
        (i for i, row in enumerate(rows) if row["label"] == "before_seed_random_states"), -1
    )
    require(0 <= rows.index(selected[0]) < before, "Program must precede starting observation")
    root = Path(context["output"])
    if role == "cells":
        row = selected[0]
        snapshot.relative_path(row["path"])
        api = _report_api().evidence
        for pin in api.files(root / row["path"], expected_sha256=row["sha256"]):
            reader.bind(pin)
        value = api.read(root / row["path"], expected_sha256=row["sha256"], expand=False)
    else:
        require(len(selected[0]["files"]) == 1, "Complete inline common-start receipt required")
        raw, pins = codec._capture(reader, selected[0]["files"][0])
        value = _data(codec.wire(raw, pins))
    completion = root / "common-start-rng/COMPLETED.json"
    completed = reader.read(completion)
    require(same(value, completed), "Actual returned record differs from its durable publication")
    declaration = context["plan"].get("common_start")
    require(
        type(declaration) is dict
        and set(declaration) == {"kind", "mode", "program", "program_identity", "provider"}
        and declaration["kind"] == "cells.paired_common_start_preparation@1"
        and declaration["mode"] == side["witness"]["common_binding"]["mode"]
        and same(declaration.get("program"), value["program"])
        and declaration.get("program_identity") == value["program_identity"]
        and declaration.get("provider")
        == dict(
            file=COMMON_START_FILE,
            sha256=COMMON_START_SHA256,
            review_sha256=COMMON_START_REVIEW_SHA256,
        ),
        "Fresh prepared program/provider/input declaration required",
    )
    observed = _common_record(value, role, side["witness"])
    witness_state = (
        _rng_api().demo_state(side["wire"])
        if role == "cells"
        else _rng_api().reference_state(side["wire"])
    )
    require(same(observed, witness_state), "Actual starting witness differs from program readback")
    return value


def compare_common_start_saved(demo, reference):
    """Authenticate explicit input programs; no owner, RNG or numerical admission."""
    sides = dict(cells=demo_starting_rng(demo), original=reference_starting_rng(reference))
    result = dict(
        kind=COMMON_START_REPORT_KIND,
        status="common_start_unavailable",
        common_starting_authority_established=False,
        numerical_parity_available=False,
        complete_SIM=False,
        physical_checkpoint_credit=0,
        errors={},
        file_pins={},
    )
    records = {}
    try:
        for role, side in sides.items():
            records[role] = _common_saved_side(side, role)
        left, right = records["cells"], records["original"]
        left_input = sides["cells"]["witness"]["common_binding"]
        right_input = sides["original"]["witness"]["common_binding"]
        require(
            left_input["mode"] == right_input["mode"]
            and left_input["profile"] == right_input["profile"],
            "Common-start pairing must preserve actual input mode/profile",
        )
        require(
            left["pid"] != right["pid"]
            and same(left["program"], right["program"])
            and same(left["runtime"], right["runtime"]),
            "Distinct processes with the same explicit program/runtime required",
        )
        for kind in ("python", "numpy"):
            require(
                same(left["state"][kind + "_after"], right["state"][kind + "_after"]),
                "Actual common-start bits differ",
            )
        result.update(
            status="common_start_files_authenticated",
            common_starting_authority_established=True,
            program_identity=left["program_identity"],
            scope="exact explicit input program and actual pre-world saved observations only",
        )
    except Exception as error:
        result["errors"]["program"] = codec._issue(error)
    for role, side in sides.items():
        reader = side["reader"]
        if reader is None:
            result["file_pins"][role] = []
            continue
        try:
            retained = side["input_tree"]
            current = _source_reader(input_files, INPUT_READER_SHA256).inventory(
                Path(retained["root"])
            )
            require(
                same(current, retained["inventory"]),
                "Complete input inventory changed during common-start authentication",
            )
            for path, pin in tuple(reader.pins.items()):
                reader.bind(dict(path=path, sha256=pin))
        except Exception as error:
            result.update(
                status="common_start_evidence_changed", common_starting_authority_established=False
            )
            result["errors"][role] = codec._issue(error)
        result["file_pins"][role] = [
            dict(path=path, sha256=pin) for path, pin in sorted(reader.pins.items())
        ]
    result["failed_source_forensics"] = {
        role: dict(error=side["error"], failure=side["failure"]) for role, side in sides.items()
    }
    return result


def _read_lineage(reader, pin):
    raw, pins = codec._capture(reader, pin)
    value = _data(codec.wire(raw, pins))
    require(
        set(value)
        == {
            "kind",
            "epoch",
            "facts",
            "process_local_identities",
            "actual_edges",
            "source_returned",
            "inherited_hooks_restored",
            "observer_coverage_failed",
            "live_owner_or_checkpoint_hydration",
        },
        "Exact original closed-lineage observation",
    )
    require(
        value["kind"] == "cells.original_SIM_closed_lineage_observation@1"
        and value["epoch"] == "after_original_SIM_core_before_pickle_with_restored_hooks"
        and type(value["facts"]) is dict
        and set(value["facts"]) == set(LINEAGE)
        and all(v is True for v in value["facts"].values())
        and value["source_returned"] is True
        and value["inherited_hooks_restored"] is True
        and value["observer_coverage_failed"] is False
        and value["live_owner_or_checkpoint_hydration"] is False,
        "Closed source lineage cannot be inferred from status alone",
    )
    ids = value["process_local_identities"]
    require(
        type(ids) is dict
        and set(ids)
        == {"INIT_phase", "old_parameters", "SIM_phase", "current_parameters", "simulator", "cells"}
        and all(type(v) is int and v > 0 for v in ids.values())
        and len(set(ids.values())) == 6,
        "Distinct actual process-local lineage roots required",
    )
    require(
        value["actual_edges"]
        == [
            ["INIT_phase", "p", "old_parameters"],
            ["INIT_phase", "sim", "simulator"],
            ["INIT_phase", "cells", "cells"],
            ["SIM_phase", "p", "current_parameters"],
            ["SIM_phase", "sim", "simulator"],
            ["SIM_phase", "cells", "cells"],
        ],
        "Actual retained old/current parameter and sim/cells edges changed",
    )
    return value


def complete_input_provenance(inventory):
    """One exact projection, only after the whole actual tree is authenticated."""
    require(
        type(inventory) is dict and set(inventory) == {"files", "directories"},
        "Complete file/directory inventory required for paired provenance",
    )
    directories, files = inventory["directories"], inventory["files"]
    require(
        type(directories) is list
        and type(files) is dict
        and directories == sorted(set(directories)),
        "Exact complete inventory roster",
    )
    for name in (*directories, *files):
        snapshot.relative_path(name)
    for row in files.values():
        require(
            type(row) is dict
            and set(row) == {"size_bytes", "sha256"}
            and type(row["size_bytes"]) is int
            and row["size_bytes"] >= 0
            and report._hash_identity(row["sha256"]),
            "Exact complete input file entry",
        )
    return dict(kind="cells.complete_SIM_input_provenance@1", inventory=inventory)


def compare_initial_rng_records(demo_state, reference_state, *, demo_witness, reference_witness):
    """Observation data only. This cannot certify either source or live ancestry.

    Witness dictionaries are already losslessly read records. Each saved-file
    adapter still has to authenticate producer/runtime/input/order associations
    before any completed-source or numerical comparison can use this report.
    """
    api = _rng_api()
    result = api.compare_states(demo_state, reference_state)
    for witness in (demo_witness, reference_witness):
        require(
            type(witness) is dict
            and witness.get("kind")
            in ("cells.common_initial_rng_observation@1", "cells.common_initial_rng_observation@2")
            and witness.get("epoch") == INITIAL_EPOCH
            and witness.get("observed_states_equalized") is False
            and witness.get("common_starting_authority_established") is False,
            "Actual declared observation-only pre-SEED witness required",
        )
        common = witness.get("common_binding")
        require(
            type(common) is dict
            and set(common) == {"input_inventory_sha256", "mode", "profile", "runtime"}
            and report._hash_identity(common["input_inventory_sha256"])
            and common["mode"] in ("original", "disabled")
            and type(common["profile"]) is str
            and common["profile"]
            and type(common["runtime"]) is dict,
            "Complete initial input/runtime declaration",
        )
        require(
            type(witness.get("source")) is dict
            and witness["source"]
            and type(witness.get("order")) is dict
            and witness["order"].get("same_parameter") is True
            and witness["order"].get("seed_entered") is False,
            "Distinct producer source/order records required",
        )
    require(
        demo_witness["order"].get("boundary")
        == "after_issued_WorldReady_before_geometry_phase_construction"
        and reference_witness["order"].get("boundary")
        == "after_original_Parameters.make_and_SimRunner_before_runner.seed",
        "Preserve the actual distinct constructor epochs; no invented common runner",
    )
    require(
        api.demo_state(demo_witness["state"]) == api.demo_state(demo_state)
        and api.reference_state(reference_witness["state"]) == api.reference_state(reference_state),
        "Each witness must retain its own exact actual saved state",
    )
    result.update(
        epoch=INITIAL_EPOCH,
        common_binding_equal=same(
            demo_witness["common_binding"], reference_witness["common_binding"]
        ),
        retained_source_order=dict(
            demo=dict(source=demo_witness["source"], order=demo_witness["order"]),
            reference=dict(source=reference_witness["source"], order=reference_witness["order"]),
        ),
        numerical_parity_available=False,
        pending=(
            "saved file/producer/runtime/order authentication and "
            "complete issued-SIM source contract"
        ),
    )
    return result


def reference_side(pins):
    side = _empty()
    try:
        require(
            type(pins) is dict and set(pins) == {"prepared", "release", "controller", "worker"},
            "Exact reference saved-path roster required",
        )
        reader = side["reader"]
        worker = reader.bound(pins["worker"])
        side["failure"] = dict(
            primary=worker.get("primary"),
            capture_errors=worker.get("capture_errors"),
            SIM_capture_errors=worker.get("SIM_capture_errors"),
        )
        require(worker.get("kind") == REF_KIND, "Original selected SIM reference schema required")
        plan, release, controller = (
            reader.bound(pins[name]) for name in ("prepared", "release", "controller")
        )
        require(
            plan.get("kind") == REF_KIND and plan.get("held") is True,
            "Exact held SIM preparation required",
        )
        source = Path(plan["execution_source"]["root"])
        manifest = snapshot.verify(
            source, manifest_sha256=plan["execution_source"]["snapshot_sha256"]
        )
        require(
            plan["execution_source"]["owned_files"] == REF_PRODUCERS,
            "Unreviewed SIM producer revision; explicit adoption required",
        )
        # The complete immutable execution image is authority, including its
        # recorded dirty patch. Retain every payload for the final rebind.
        reader.bind(dict(path=str(source / "checkout.patch"), sha256=manifest["patch_sha256"]))
        for name, row in manifest["files"].items():
            reader.bind(dict(path=str(source / snapshot.relative_path(name)), sha256=row["sha256"]))
        for name, expected in REF_PRODUCERS.items():
            require(manifest["files"][name]["sha256"] == expected, "SIM source producer drift")
            reader.bind(dict(path=str(source / name), sha256=expected))
        reader.bind(
            dict(
                path=str(source / "SNAPSHOT.json"),
                sha256=plan["execution_source"]["snapshot_sha256"],
            )
        )
        require(
            release["prepared_sha256"] == pins["prepared"]["sha256"]
            and release.get("kind") == "cells.original_SIM_reference_execution_release@1"
            and release["worker_output"] == str(Path(pins["worker"]["path"]).parent)
            and Path(pins["worker"]["path"]).name == "SIM-reference-result.json",
            "SIM release/worker/source association changed",
        )
        output = Path(release["worker_output"])
        parent_worker = output / "result.json"
        parent_record = reader.read(parent_worker)
        require(
            same(parent_record, worker["INIT_result"]), "Actual same-workflow INIT result changed"
        )
        parent_plan = reader.bound(plan["INIT_prepared"])
        require(
            parent_plan["execution_source"]["root"] == str(source)
            and parent_plan["execution_source"]["snapshot_sha256"]
            == plan["execution_source"]["snapshot_sha256"],
            "Actual same-source INIT preparation required",
        )
        side.update(
            mode=parent_plan["inputs"]["mode"],
            inputs={n: r["sha256"] for n, r in parent_plan["inputs"]["inventory"]["files"].items()},
            configuration_profile=parent_plan["source_plan"]["input_profile"],
            original_sources=parent_plan["native_inventory_sha256"],
            initial_rng=dict(available=False, reason="common_pre_SEED_adapter_review_pending"),
        )
        require(side["mode"] in ("original", "disabled"), "Explicit original/omitted-flux mode")
        for name, row in parent_plan["inputs"]["inventory"]["files"].items():
            reader.bind(
                dict(
                    path=str(Path(parent_plan["inputs"]["root"]) / snapshot.relative_path(name)),
                    sha256=row["sha256"],
                )
            )
        declared = parent_plan["inputs"]["inventory"]
        if set(declared) == {"files", "directories"}:
            actual = _source_reader(input_files, INPUT_READER_SHA256).inventory(
                Path(parent_plan["inputs"]["root"])
            )
            require(same(actual, declared), "Complete original reference input inventory changed")
            side["input_provenance"] = complete_input_provenance(actual)
            side["input_tree"] = dict(root=parent_plan["inputs"]["root"], inventory=actual)
        captures, iterations = worker["SIM_captures"], worker["SIM_iterations"]
        require(
            type(captures) is list
            and len(captures) <= 2048
            and type(iterations) is list
            and len(iterations) <= MAX_STEPS,
            "Bounded SIM captures/iterations required",
        )
        labels = {}
        for row in captures:
            require(
                type(row["label"]) is str and row["label"] not in labels,
                "Unique SIM labels required",
            )
            require(
                row["label"].startswith("SIM.") and row["status"] in ("saved", "capture_failed"),
                "Known original namespaced capture outcome required",
            )
            labels[row["label"]] = row
            if row["status"] == "saved":
                require(
                    type(row["files"]) is list
                    and row["files"]
                    and Path(row["files"][0]["path"]).is_relative_to(
                        output / "SIM-reference/captures"
                    ),
                    "Actual contained primary capture file required",
                )
                actual = codec.evidence.files(
                    row["files"][0]["path"], expected_sha256=row["files"][0]["sha256"]
                )
                require(actual == row["files"], "Complete SIM sidecar roster required")
                for pin in actual:
                    reader.bind(pin)
        for ordinal, pin in enumerate(iterations):
            capture = labels.get(f"SIM.iteration_{ordinal + 1:04d}")
            require(
                capture is not None and capture["status"] == "saved" and pin == capture["files"][0],
                "Actual SIM row/label/cache association changed",
            )
            side["rows"].append(_read_row(reader, pin, ordinal, required_observation=True))
        require(
            {
                label
                for label, row in labels.items()
                if re.fullmatch(r"SIM\.iteration_[0-9]{4}", label) and row["status"] == "saved"
            }
            == {f"SIM.iteration_{i + 1:04d}" for i in range(len(iterations))},
            "Exact saved SIM completed-prefix roster required",
        )
        calendar = labels.get("SIM.original_calendar")
        times = None
        if calendar is not None and calendar["status"] == "saved":
            value, columns = codec._capture(reader, calendar["files"][0])
            times, sampled = codec._reference_calendar(value, columns)
            for index, row in enumerate(side["rows"]):
                require(
                    index < len(times)
                    and row["source_time_bits"] == times[index]
                    and row["sampled"] is (times[index] in sampled),
                    "SIM row differs from the actual complete calendar",
                )
        side["reported_endpoint_complete"] = worker.get("status") == "completed"
        lineage = worker.get("SIM_closed_lineage")
        if lineage is not None:
            capture = labels.get("SIM.closed_lineage")
            require(
                capture is not None
                and capture["status"] == "saved"
                and lineage == capture["files"][0],
                "Actual closed-lineage primary archive association",
            )
            side["lineage_forensics"] = _read_lineage(reader, lineage)
        side["prerequisites"] = [
            "actual complete normal-loop/context/lineage and released source/runtime graph",
            "independent common pre-SEED authority remains unavailable",
        ]
        side.update(
            files_bound=True,
            authenticated=False,
            endpoint_complete=False,
            calendar=times,
            lineage=None if lineage is None else side["lineage_forensics"]["facts"],
            controller=controller,
        )
        if worker.get("status") == "completed":
            try:
                _authenticate_reference_terminal(
                    side, pins, plan, release, controller, worker, parent_plan, manifest
                )
            except Exception as error:
                side["authentication_error"] = codec._issue(error)
                side["error"] = side["authentication_error"]
    except Exception as error:
        side["error"] = codec._issue(error)
    return side


def _canonical_module(root, name, files, *, prefix=""):
    require(
        type(name) is str and all(re.fullmatch(r"[A-Za-z_]\w*", part) for part in name.split(".")),
        "Canonical recorded module name required",
    )
    stem = prefix + name.replace(".", "/")
    relative = stem + "/__init__.py" if stem + "/__init__.py" in files else stem + ".py"
    require(relative in files, "Recorded module absent from its canonical source roster")
    return root / relative, files[relative]["sha256"]


def _reference_read_domains(reader, plan, parent_release, filesystem, runtime, output):
    """Check an explicit new closure; never infer domains from observed imports."""
    closure = plan.get("execution_closure")
    if closure is None:
        return False  # Historical records do not gain this additional proof.
    require(
        type(closure) is dict
        and set(closure)
        == {"kind", "runtime", "worker_output", "read_access", "environment", "expected_calendars"}
        and closure["kind"] == "cells.original_reference_execution_closure@1"
        and closure["worker_output"] == str(output),
        "Exact new reference execution closure required",
    )
    access = closure["read_access"]
    require(
        type(access) is dict
        and set(access) == {"roots", "files"}
        and all(type(access[k]) is list and len(access[k]) <= 1024 for k in access)
        and parent_release["read_access"] == access
        and parent_release["pythonpath"] == closure["environment"]["PYTHONPATH"]
        and filesystem["read_roots"] == access["roots"]
        and filesystem["read_files"] == access["files"],
        "Actual released/final reference read domains changed",
    )
    roots, exact = [Path(p) for p in access["roots"]], set(access["files"])
    require(
        all(p.is_absolute() and str(p) == str(p.resolve()) and p != Path("/") for p in roots)
        and all(Path(p).is_absolute() and str(Path(p).resolve()) == p for p in exact),
        "Canonical bounded explicit reference read domains required",
    )
    declared = closure["runtime"]
    composition = declared["composition"]
    require(
        runtime["executable"] == composition["executable"], "Actual retained reference executable"
    )
    pins = [composition["executable"], composition["venv_configuration"]]
    for name, provider in composition["providers"].items():
        pins.extend(provider["files"])
        if name in runtime["loaded_files"]:
            require(
                runtime["loaded_files"][name] == provider["files"][0],
                "Reference numerical library has a foreign origin: " + name,
            )
    pins.extend(declared["pillow"]["files"])
    pins.extend(declared["startup_files"])
    for pin in pins:
        reader.bind(pin)
    for pin in runtime["loaded_files"].values():
        path = reader.bind(pin)
        require(
            str(path) in exact or any(path == root or path.is_relative_to(root) for root in roots),
            "Actual reference import escaped its released read domains",
        )
    return True


def _paired_calendar_counts(plan, parent_plan, worker, rows):
    closure = plan.get("execution_closure")
    if closure is None:
        return False
    counts = closure["expected_calendars"]
    require(
        parent_plan["source_plan"]["input_profile"] == "headless_core"
        and set(counts) == {"init", "sim"}
        and type(counts["init"]["expected_iterations"]) is int
        and type(counts["sim"]["expected_iterations"]) is int
        and counts["init"]["expected_iterations"] == 500
        and counts["sim"]["expected_iterations"] == 350
        and len(worker["INIT_result"]["iterations"]) == 500
        and len(rows) == 350,
        "Complete paired headless_core 500/350 histories required",
    )
    return True


def _authenticate_reference_terminal(
    side, pins, plan, release, controller, worker, parent_plan, manifest
):
    reader = side["reader"]
    source = Path(plan["execution_source"]["root"])
    output = Path(pins["worker"]["path"]).parent
    expected_names = {
        "source": "SOURCE_REVIEW_SHA256",
        "reference": "REFERENCE_REVIEW_SHA256",
        "execution": "EXECUTION_REVIEW_SHA256",
    }
    constants = {}
    for node in ast.parse((source / "validation/betse/native_sim_reference.py").read_bytes()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in expected_names.values():
                    constants[target.id] = ast.literal_eval(node.value)
    require(
        set(constants) == set(expected_names.values())
        and all(report._hash_identity(v) for v in constants.values()),
        "Original SIM source review/release adoption remains unavailable",
    )
    policy = plan["source_plan"]["resource_policy"]
    require(
        release.get("enabled") is True and release["policy"] == policy,
        "Actual original SIM execution release/policy required",
    )
    contracts = dict(
        source=dict(
            kind="cells.original_SIM_selected_source_review@1",
            original=plan["source_plan"]["original"],
            reference_source=plan["source_plan"]["reference_source"],
            no_numerical_solver_or_flux_repair=True,
        ),
        reference=dict(
            kind="cells.original_SIM_INIT_predecessor_review@1",
            reference_source=plan["source_plan"]["reference_source"],
            internally_created_complete_INIT_only=True,
            external_data_or_owner_arguments=False,
            closed_package_never_rearmed=True,
        ),
        execution=dict(
            kind="cells.original_SIM_execution_policy_review@1",
            policy=policy,
            one_fresh_worker=True,
            max_SIM_iterations=MAX_STEPS,
            complete_calendar_or_refusal=True,
            detached_supervision_required=True,
        ),
    )
    for role, name in expected_names.items():
        require(
            plan["source_plan"]["reviews"][role]
            == constants[name]
            == release["reviews"][role]["sha256"],
            "Actual source-adopted original SIM review pin required",
        )
        require(
            reader.bound(release["reviews"][role]) == contracts[role],
            "Original SIM review contract differs",
        )
    parent_release = reader.bound(release["init_release"])
    require(
        parent_release["prepared_sha256"] == plan["INIT_prepared"]["sha256"]
        and parent_release["worker_output"] == str(output)
        and parent_release["snapshot_sha256"] == plan["execution_source"]["snapshot_sha256"]
        and parent_release["kind"] == "cells.original_INIT_reference_execution_release@1"
        and parent_release["enabled"] is True,
        "Actual same-process original INIT release association",
    )
    require(
        worker["INIT_result"]["status"] == "completed"
        and worker["INIT_result"]["source_returned"] is True
        and worker["INIT_result"]["inherited_hooks_restored"] is True
        and worker["INIT_result"]["observer_coverage_failed"] is False
        and worker["INIT_result"]["filesystem_audit_installed"] is True
        and worker["INIT_parent_consumed"] is True
        and worker["SIM_source_returned"] is True
        and worker["inherited_hooks_restored"] is True
        and worker["SIM_observer_coverage_failed"] is False
        and worker["SIM_finalization_complete"] is True
        and worker.get("primary") is None
        and worker.get("capture_errors") == []
        and worker.get("SIM_capture_errors") == [],
        "Actual complete original INIT/SIM source/coverage flags required",
    )
    require(
        side.get("input_provenance") is not None and side.get("lineage_forensics") is not None,
        "Complete original input/closed-lineage proof required",
    )
    rows = worker["SIM_captures"]
    terminal = next((r for r in rows if r["label"] == "SIM.terminal"), None)
    require(
        terminal is not None
        and terminal["status"] == "saved"
        and worker["SIM_terminal_observation"] == terminal["files"][0],
        "Actual terminal capture association",
    )
    raw, parts = codec._capture(reader, terminal["files"][0])
    value = _data(codec.wire(raw, parts))
    flags = (
        "normal_phase_return",
        "normal_report_return",
        "normal_core_prefix_return",
        "normal_full_loop_return",
        "normal_context_return",
        "normal_selected_caller_return",
        "context_yield",
        "before_native_pickle",
    )
    require(
        value["kind"] == "cells.original_SIM_terminal_observation@1"
        and value["epoch"] == EPOCH
        and all(value.get(name) is True for name in flags)
        and value["native_pickle_entered"] is False
        and value["physical_checkpoint_or_common_starting_authority"] is False
        and type(value["context_entries"]) is int
        and value["context_entries"] == 2,
        "Genuine normal-loop/context/before-pickle terminal witness required",
    )
    require(
        type(value["configured_iterations"]) is int
        and value["configured_iterations"]
        == len(side["rows"])
        == len(side["calendar"])
        == value["completed_iterations"]
        and 1 <= len(side["rows"]) <= MAX_STEPS
        and value["source_time_bits"] == side["calendar"],
        "Complete configured original calendar required",
    )
    require(
        value["selected_source"] == plan["source_plan"]["original"]["terminal_observation"],
        "Original terminal method/source contract changed",
    )
    require(
        value["lineage_identities"] == side["lineage_forensics"]["process_local_identities"],
        "Terminal frames and closed old/current-p/sim/cells lineage differ",
    )
    events = value["events"]
    expected_events = plan["source_plan"]["original"]["terminal_observation"]["required_events"]
    require(
        type(events) is list
        and len(events) == len(expected_events)
        and all(
            type(row) in (list, tuple)
            and len(row) == 3
            and type(row[0]) is int
            and row[0] == i + 1
            and list(row[1:]) == expected_events[i]
            for i, row in enumerate(events)
        ),
        "Actual original terminal call/context/return order required",
    )
    identities = value["actual_frame_identities"]
    require(
        set(identities) == {"phase", "report", "core", "calendar", "loop", "context", "caller"}
        and all(type(v) is int and v > 0 for v in identities.values())
        and len(set(identities.values())) == len(identities),
        "Actual distinct retained source frame observations",
    )
    samples = value["sampled_time_bits"]
    require(
        type(samples) is list
        and len(samples) == len(set(samples))
        and set(samples) <= set(side["calendar"]),
        "Actual original sample membership",
    )
    for row in side["rows"]:
        require(
            row["dt_bits"] == value["dt_bits"]
            and row["sampled"] == (row["source_time_bits"] in samples),
            "Original complete time/dt/sample association",
        )
    process_root = Path(pins["controller"]["path"]).parent / "process"
    process_inputs = reader.read(process_root / "process-inputs.json")
    process = reader.read(
        process_root
        / ("failure.json" if (process_root / "failure.json").exists() else "result.json")
    )
    for flag, expected in (
        ("--prepared", pins["prepared"]["path"]),
        ("--prepared-sha256", pins["prepared"]["sha256"]),
        ("--release", pins["release"]["path"]),
        ("--release-sha256", pins["release"]["sha256"]),
        ("--output", str(output)),
    ):
        command = process_inputs["command"]
        require(
            command.count(flag) == 1 and command[command.index(flag) + 1] == expected,
            "Original SIM guarded command association",
        )
    limits = process["limits"]
    require(
        process_inputs["cwd"] == str(source)
        and process_inputs["limits"] == limits
        and limits["max_wall_seconds"] == policy["wall_seconds"]
        and limits["max_process_tree_rss_bytes"] == policy["max_rss_bytes"]
        and limits["min_available_host_memory_bytes"] == policy["reserve_bytes"]
        and process["status"] == "completed"
        and process["returncode"] == 0
        and process["elapsed_seconds"] <= limits["max_wall_seconds"]
        and process["sampled_peak_process_tree_rss_bytes"] <= limits["max_process_tree_rss_bytes"]
        and process["minimum_available_host_memory_bytes"]
        >= limits["min_available_host_memory_bytes"]
        and process["samples"] > 0
        and controller["status"] == "completed",
        "Original SIM bounded successful terminal required",
    )
    require(
        controller["kind"] == REF_KIND
        and controller["prepared_sha256"] == pins["prepared"]["sha256"]
        and same(controller["process"], process),
        "Actual original supervisor/process association",
    )
    require(
        len(command) == 14
        and command[1:4] == ["-B", "-m", "validation.betse.native_sim_reference"],
        "Exact original SIM worker invocation",
    )
    runtime_executable = command[0]
    binding = reader.read(output / "SIM-reference/source-input-binding.json")
    require(
        binding["execution_source"] == plan["execution_source"]
        and binding["prepared_inputs"] == parent_plan["inputs"],
        "Original SIM final source/input association",
    )
    copied = binding["execution_inputs"]
    require(
        copied["source_root"] == parent_plan["inputs"]["root"]
        and copied["root"] == str(output / "config")
        and copied["inventory"] == parent_plan["inputs"]["inventory"]
        and {r["name"] for r in copied["files"]} == set(parent_plan["inputs"]["inventory"]["files"])
        and len(copied["files"]) == len(parent_plan["inputs"]["inventory"]["files"]),
        "Actual original execution-copy inventory",
    )
    reader.read(output / "execution-inputs.json")
    for row in copied["files"]:
        expected = parent_plan["inputs"]["inventory"]["files"][row["name"]]["sha256"]
        require(
            row["sha256"] == expected
            and row["status"] == "copied"
            and row["source_inode"] != row["execution_inode"],
            "Original execution-copy input changed",
        )
        reader.bind(
            dict(path=str(output / "config" / snapshot.relative_path(row["name"])), sha256=expected)
        )
    runtime = reader.read(output / "SIM-reference/runtime.json")
    reader.bind(runtime["executable"])
    require(
        Path(runtime_executable).is_absolute()
        and str(Path(runtime_executable).resolve(strict=True)) == runtime["executable"]["path"]
        and type(runtime["python"]) is str
        and runtime["python"],
        "Original runtime executable association",
    )
    native_root = Path(parent_plan["native_root"])
    native_roots = [
        ast.literal_eval(node.value.args[0])
        for node in ast.parse(
            (source / "validation/betse/native_init_terminal_reference.py").read_bytes()
        ).body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "NATIVE_ROOT" for t in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "Path"
        and len(node.value.args) == 1
    ]
    require(
        native_roots == [str(native_root)], "Original package root differs from adopted producer"
    )
    native = parent_plan["native_inventory"]
    require(
        hashlib.sha256(
            json.dumps(native, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == parent_plan["native_inventory_sha256"],
        "Original complete package inventory identity",
    )
    require(
        plan["source_plan"]["reference_source"]
        == manifest["files"]["validation/betse/native_init_terminal_reference.py"]["sha256"]
        and parent_plan["source_plan"]["comparator_normalized_AST_sha256"]
        == REFERENCE_RNG_AST_SHA256,
        "Exact selected original INIT producer/source contract",
    )
    for relative, expected in parent_plan["source_plan"]["critical_source_pins"].items():
        require(
            native.get(relative, {}).get("sha256") == expected,
            "Original selected critical package source drift",
        )
    import_policy = parent_plan["source_plan"]["native_import_lifecycle"]
    require(
        import_policy == codec.native_imports.specification(),
        "Exact selected original import policy required",
    )
    import_producer = parent_plan["source_plan"]["native_import_producer"]
    require(
        import_producer
        == dict(
            file=codec.native_imports.FILE,
            sha256=manifest["files"][codec.native_imports.FILE]["sha256"],
        ),
        "Original compiler adapter producer drift",
    )
    compiler_modules = codec.native_imports.validate_record(
        binding["native_import_lifecycle"],
        binding["native_producers"],
        native,
        native_root,
        mode=parent_plan["inputs"]["mode"],
        selections=parent_plan["selections"],
    )
    codec.native_imports.validate_runtime(binding["native_import_lifecycle"], runtime)
    compiler = plan["source_plan"]["original"]["selected_caller_compiler"]
    programs = binding["native_import_lifecycle"]["programs"]
    require(
        set(programs) == {compiler["module"]}, "Exactly one actual selected SIM compiler attempt"
    )
    program = programs[compiler["module"]]
    require(
        program["entry"] == compiler["entry"]
        and program["AST_sha256"] == compiler["AST_sha256"]
        and program["source_sha256"] == compiler["source_sha256"],
        "Selected caller differs from pinned source selection",
    )
    for name, pin in compiler_modules.items():
        require(
            runtime["loaded_files"].get(name) == pin,
            "Actual SIM compiler origin differs from import witness",
        )
        reader.bind(pin)
    required = (
        "validation.betse.native_sim_reference_source",
        "validation.betse.native_init_terminal_reference",
        "betse.science.simrunner",
        "betse.science.sim",
        "betse.science.phase.phasecls",
        "betse.util.type.contexts",
    )
    require(
        set(required) <= set(runtime["loaded_files"])
        and (
            "validation.betse.native_sim_reference" in runtime["loaded_files"]
            or "__main__" in runtime["loaded_files"]
        ),
        "Actual reached original/runtime producer roster",
    )
    for name, pin in runtime["loaded_files"].items():
        path = reader.bind(pin)
        if name == "__main__":
            relative = "validation/betse/native_sim_reference.py"
            require(
                path == source / relative
                and pin["sha256"] == manifest["files"][relative]["sha256"],
                "Guarded -m worker main origin changed",
            )
        if name in ("validation", "cells", "tests") or name.startswith(
            ("validation.", "cells.", "tests.")
        ):
            prefix = "src/" if name == "cells" or name.startswith("cells.") else ""
            expected_path, expected_pin = _canonical_module(
                source, name, manifest["files"], prefix=prefix
            )
            require(
                path == expected_path and pin["sha256"] == expected_pin,
                "Project runtime producer has a foreign/noncanonical origin",
            )
        if path.is_relative_to(source):
            require(
                manifest["files"][str(path.relative_to(source))]["sha256"] == pin["sha256"],
                "Original frozen runtime producer drift",
            )
        if name == "betse" or name.startswith("betse."):
            expected_path, expected_pin = _canonical_module(native_root, name, native)
            require(
                path == expected_path and pin["sha256"] == expected_pin,
                "Original module name/native origin changed",
            )
            relative = str(path.relative_to(native_root))
            observed = binding["native_producers"][name]
            require(
                native[relative]["sha256"] == pin["sha256"] == observed["sha256"]
                and observed["path"] == str(path),
                "Actual original runtime/native-inventory producer mismatch",
            )
    require(
        {name for name in runtime["loaded_files"] if name == "betse" or name.startswith("betse.")}
        == set(binding["native_producers"]),
        "Exact original imported producer roster",
    )
    filesystem = reader.read(output / "SIM-reference/filesystem.json")
    require(
        filesystem["installed"] is True
        and filesystem["failures"] == []
        and filesystem["first_error"] is None,
        "Original final filesystem guard refusal retained",
    )
    require(
        filesystem["write_policy"]["failures"] == []
        and filesystem["write_policy"]["first_error"] is None,
        "Sticky original writer refusal cannot become success",
    )
    side["runtime_read_domains_verified"] = _reference_read_domains(
        reader, plan, parent_release, filesystem, runtime, output
    )
    side["full_paired_calendars_verified"] = _paired_calendar_counts(
        plan, parent_plan, worker, side["rows"]
    )
    require(
        same(reader.read(output / "execution-inputs.json"), copied),
        "Actual saved execution-copy record mismatch",
    )
    for path, digest in tuple(reader.pins.items()):
        reader.bind(dict(path=path, sha256=digest))
    require(
        str(Path(runtime_executable).resolve(strict=True)) == runtime["executable"]["path"],
        "Original worker executable alias changed during authentication",
    )
    side.update(
        authenticated=True,
        endpoint_complete=True,
        terminal_observation=value,
        lineage=side["lineage_forensics"]["facts"],
        runtime=runtime,
        command_executable=dict(path=runtime_executable, resolved=runtime["executable"]["path"]),
        prerequisites=["Common pre-SEED authority is separate and remains unavailable"],
    )


def issued_side(pins, *, accepted_observer_sha256=None):
    # Lazy metadata-only import avoids circular initialization and never imports
    # Key's live implementation while its producer/review gates are held.
    from validation.betse import native_sim_result_observation as observation

    return observation.saved_view(pins, accepted_observer_sha256=accepted_observer_sha256)


def compare_terminal_views(reference, issued):
    """Exact saved observations, independent of common-start or physical claims."""
    result = dict(
        kind="cells.paired_SIM_terminal_observations@1",
        status="unavailable",
        exact_observation_comparison_available=False,
        exact_observations_equal=None,
        verified_source_endpoints_complete=all(
            side.get("endpoint_complete") is True for side in (reference, issued)
        ),
        common_starting_authority_established=False,
        numerical_parity_available=False,
        scientific_physical_checkpoint_credit=0,
        observations=[],
        failures={
            name: side.get("failure")
            for name, side in (("reference", reference), ("issued", issued))
        },
        errors={
            name: side.get("error") for name, side in (("reference", reference), ("issued", issued))
        },
    )
    if not all(
        side.get("files_bound") is True
        and side.get("authenticated") is True
        and side.get("endpoint_complete") is True
        and side.get("error") is None
        for side in (reference, issued)
    ):
        return result
    provenance = {
        name: same(reference.get(name), issued.get(name)) and reference.get(name) is not None
        for name in ("mode", "input_provenance", "configuration_profile", "original_sources")
    }
    result["provenance"] = provenance
    if not all(provenance.values()):
        result["status"] = "incompatible_provenance"
        return result
    require(reference["mode"] in ("original", "disabled"), "Exact operator mode")
    rows = (reference["rows"], issued["rows"])
    if not all(rows):
        return result
    for side in (reference, issued):
        require(
            1 <= len(side["rows"]) <= MAX_STEPS and len(side["rows"]) == len(side["calendar"]),
            "Complete declared saved calendar",
        )
        for index, row in enumerate(side["rows"]):
            require(
                row["ordinal"] == index
                and row["epoch"] == EPOCH
                and row["source_time_bits"] == side["calendar"][index],
                "Absolute SIM epoch/order",
            )
    all_available = all_equal = len(rows[0]) == len(rows[1])
    for index in range(max(map(len, rows))):
        if any(index >= len(items) for items in rows):
            all_available = all_equal = False
            result["observations"].append(dict(ordinal=index, status="missing_completed_iteration"))
            continue
        left, right = rows[0][index], rows[1][index]
        clocks = all(
            same(left[name], right[name]) for name in ("source_time_bits", "dt_bits", "sampled")
        )
        groups = {
            name: dict(
                available=clocks
                and left["groups"][name] is not None
                and right["groups"][name] is not None,
                equal=same(left["groups"][name], right["groups"][name])
                if clocks and left["groups"][name] is not None and right["groups"][name] is not None
                else None,
            )
            for name in GROUPS
        }
        all_available = all_available and all(row["available"] for row in groups.values())
        all_equal = all_equal and all(row["equal"] is True for row in groups.values())
        result["observations"].append(
            dict(
                ordinal=index,
                status="same_clock" if clocks else "different_exact_clock",
                groups=groups,
            )
        )
    result.update(
        status="compared_saved_observations",
        exact_observation_comparison_available=bool(all_available),
        exact_observations_equal=bool(all_equal) if all_available else None,
    )
    return result


def compare_terminal_saved(reference, issued, *, accepted_observer_sha256=None):
    sides = (
        reference_side(reference),
        issued_side(issued, accepted_observer_sha256=accepted_observer_sha256),
    )
    try:
        result = compare_terminal_views(*sides)
    except Exception as error:
        result = compare_terminal_views(_empty(), _empty())
        result["failures"] = {
            name: side.get("failure")
            for name, side in zip(("reference", "issued"), sides, strict=True)
        }
        result["errors"] = {
            name: side.get("error")
            for name, side in zip(("reference", "issued"), sides, strict=True)
        }
        result["errors"]["comparison"] = codec._issue(error)
    result["file_pins"] = {}
    drift = {}
    for name, side in zip(("reference", "issued"), sides, strict=True):
        try:
            if side.get("command_executable") is not None:
                command = side["command_executable"]
                require(
                    str(Path(command["path"]).resolve(strict=True)) == command["resolved"],
                    "Original worker executable alias changed during comparison",
                )
            if side.get("input_tree") is not None:
                tree = side["input_tree"]
                require(
                    same(
                        _source_reader(input_files, INPUT_READER_SHA256).inventory(
                            Path(tree["root"])
                        ),
                        tree["inventory"],
                    ),
                    "Complete saved input tree changed",
                )
            for path, digest in tuple(side["reader"].pins.items()):
                side["reader"].bind(dict(path=path, sha256=digest))
        except Exception as error:
            drift[name] = codec._issue(error)
        result["file_pins"][name] = [
            dict(path=p, sha256=s) for p, s in sorted(side["reader"].pins.items())
        ]
    if drift:
        previous = result
        result = compare_terminal_views(_empty(), _empty())
        result.update(
            status="evidence_changed_during_comparison",
            errors={**previous["errors"], **drift},
            failures=previous["failures"],
            unverified_forensics=previous,
            file_pins=previous["file_pins"],
        )
    return result


def compare_views(reference, issued):
    """Pure typed reports; synthetic views do not create producer authority."""
    result = dict(
        kind=KIND,
        status="unverified_evidence",
        epoch=EPOCH,
        observations=[],
        endpoint_complete=False,
        all_requested_groups_available=False,
        available_observations_equal=None,
        numerical_parity=dict(available=False, equal=None),
        numerical_physical_or_restart_credit=0,
        failures=dict(reference=reference.get("failure"), issued=issued.get("failure")),
        sides={
            name: dict(
                files_bound=side.get("files_bound") is True,
                authenticated=side.get("authenticated") is True,
                retained_completed_rows=len(side.get("rows", [])),
                verified_endpoint_complete=side.get("endpoint_complete") is True,
                reported_endpoint_complete=side.get("reported_endpoint_complete"),
                prerequisites=side.get("prerequisites", []),
            )
            for name, side in (("reference", reference), ("issued", issued))
        },
        restart_prerequisites=[
            "genuine serialized source/resume and RNG ownership",
            "native saved-pickle caller/reconstruction history",
            "independent conservation/domain/physical qualification",
        ],
    )
    if not all(side.get("authenticated") is True for side in (reference, issued)):
        result["errors"] = dict(reference=reference.get("error"), issued=issued.get("error"))
        return result
    provenance = {
        name: same(reference.get(name), issued.get(name)) and reference.get(name) is not None
        for name in ("mode", "inputs", "configuration_profile", "original_sources")
    }
    result["provenance"] = provenance
    if not all(provenance.values()):
        result["status"] = "incompatible_provenance"
        return result
    require(
        reference["mode"] in ("original", "disabled"), "Exact original/omitted-flux mode required"
    )
    for side in (reference, issued):
        rows = side["rows"]
        require(type(rows) is list and len(rows) <= MAX_STEPS, "Complete SIM history capacity")
        for index, row in enumerate(rows):
            require(
                type(row["ordinal"]) is int and row["ordinal"] == index and row["epoch"] == EPOCH,
                "Explicit contiguous SIM epoch only; no shift or INIT relabelling",
            )
            require(
                type(row["sampled"]) is bool
                and all(
                    type(row[name]) is str and re.fullmatch("[0-9a-f]{16}", row[name])
                    for name in ("source_time_bits", "dt_bits")
                ),
                "Exact saved SIM clock/sample bits required",
            )
            require(
                type(row["groups"]) is dict and set(row["groups"]) == set(GROUPS),
                "Exact declared SIM observation group roster",
            )
            require(
                row["groups"]["clock"] is None
                or same(
                    row["groups"]["clock"],
                    {name: row[name] for name in ("source_time_bits", "dt_bits", "sampled")},
                ),
                "Clock group must describe its actual row boundary",
            )
            if row["groups"]["rng"] is not None:
                _full_rng(row["groups"]["rng"])
        calendar = side.get("calendar")
        if calendar is not None:
            require(
                type(calendar) is list
                and 1 <= len(calendar) <= MAX_STEPS
                and all(type(v) is str and re.fullmatch(r"[0-9a-f]{16}", v) for v in calendar)
                and len(rows) <= len(calendar)
                and all(row["source_time_bits"] == calendar[i] for i, row in enumerate(rows)),
                "Actual full calendar/completed-prefix association required",
            )
        if side.get("endpoint_complete") is True:
            require(
                calendar is not None and len(rows) == len(calendar),
                "Completion requires all actual calendar bodies, never empty/partial status",
            )
    a, b = reference["rows"], issued["rows"]
    equal = True
    missing = 0
    compared = 0
    clock_equal = True
    for index in range(max(len(a), len(b))):
        row = dict(ordinal=index, groups={})
        if index >= len(a) or index >= len(b):
            row["status"] = "missing_completed_prefix_observation"
            missing += len(GROUPS)
            clock_equal = False
        else:
            timing = {
                name: same(a[index][name], b[index][name])
                for name in ("source_time_bits", "dt_bits", "sampled")
            }
            row["timing"] = timing
            if not all(timing.values()):
                row["status"] = "different_explicit_SIM_clock"
                equal = False
                clock_equal = False
                missing += len(GROUPS)
            else:
                row["status"] = "compared_saved_SIM_observations"
                for name in GROUPS:
                    left, right = a[index]["groups"][name], b[index]["groups"][name]
                    available = left is not None and right is not None
                    same_value = same(left, right) if available else None
                    row["groups"][name] = dict(available=available, equal=same_value)
                    if available:
                        compared += 1
                        equal = equal and same_value
                    else:
                        missing += 1
        result["observations"].append(row)
    complete = (
        reference.get("endpoint_complete") is True and issued.get("endpoint_complete") is True
    )
    lineages = [side.get("lineage") for side in (reference, issued)]
    lineage_ok = all(
        type(value) is dict
        and set(value) == set(LINEAGE)
        and all(value.get(name) is True for name in LINEAGE)
        for value in lineages
    )
    ra, rb = reference.get("initial_rng", {}), issued.get("initial_rng", {})
    rng_available = all(
        type(value) is dict
        and value.get("available") is True
        and value.get("epoch") == INITIAL_EPOCH
        and type(value.get("common_binding")) is dict
        and value["common_binding"]
        and type(value.get("full_state")) is dict
        and value["full_state"]
        for value in (ra, rb)
    )
    rng_equal = rng_available and all(
        name in ra and name in rb and same(ra[name], rb[name])
        for name in ("epoch", "common_binding", "full_state")
    )
    if rng_available:
        _full_rng(ra["full_state"])
        _full_rng(rb["full_state"])
    result.update(
        status="compared_completed_SIM_endpoints"
        if complete
        else "compared_partial_or_unverified_SIM_completion",
        endpoint_complete=complete,
        available_observations_equal=equal if compared else None,
        compared_group_observations=compared,
        unavailable_group_observations=missing,
        all_requested_groups_available=bool(
            a
            and b
            and missing == 0
            and clock_equal
            and compared == len(a) * len(GROUPS) == len(b) * len(GROUPS)
        ),
        lineage_verified=lineage_ok,
        aligned_clock_equal=clock_equal,
        common_initial_rng=dict(
            available=bool(rng_available), equal=bool(rng_equal) if rng_available else None
        ),
        prerequisites=dict(
            reference=reference.get("prerequisites", []), issued=issued.get("prerequisites", [])
        ),
    )
    ready = bool(complete and lineage_ok and rng_equal and result["all_requested_groups_available"])
    result["numerical_parity"] = dict(
        available=ready,
        equal=equal if ready else None,
        scope="exact declared saved SIM groups/epochs only; no physical/restart qualification",
        reason=None
        if ready
        else "missing_or_mismatched_initial_authority_lineage_completion_or_observations",
    )
    return result


def compare_saved(reference, issued):
    sides = (reference_side(reference), issued_side(issued))
    try:
        result = compare_views(*sides)
    except Exception as error:
        result = compare_views(_empty(), _empty())
        result["errors"]["comparison"] = codec._issue(error)
        result["failures"] = {
            name: side.get("failure")
            for name, side in zip(("reference", "issued"), sides, strict=True)
        }
    result["file_pins"] = {}
    drift = {}
    for name, side in zip(("reference", "issued"), sides, strict=True):
        try:
            for path, digest in tuple(side["reader"].pins.items()):
                side["reader"].bind(dict(path=path, sha256=digest))
        except Exception as error:
            drift[name] = codec._issue(error)
        result["file_pins"][name] = [
            dict(path=path, sha256=digest) for path, digest in sorted(side["reader"].pins.items())
        ]
    if drift:
        previous = result
        result = compare_views(_empty(), _empty())
        result.update(
            status="evidence_changed_during_comparison",
            unverified_forensics=previous,
            file_pins=previous["file_pins"],
            failures=previous["failures"],
            errors=drift,
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--starting-rng", action="store_true")
    parser.add_argument("--common-start", action="store_true")
    args = parser.parse_args()
    if args.starting_rng and args.common_start:
        parser.error("Choose observation-only or explicit common-start comparison")
    starting = args.starting_rng or args.common_start
    reader = (_report_api() if starting else report).Reader()
    pin = dict(path=str(args.request), sha256=args.request_sha256)
    request = reader.bound(pin)
    if starting:
        require(set(request) == {"demo", "reference"}, "Exact starting-RNG saved request")
        function = compare_common_start_saved if args.common_start else compare_starting_rng_saved
        result = function(request["demo"], request["reference"])
    else:
        require(set(request) == {"reference", "issued"}, "Exact saved SIM comparison request")
        result = compare_saved(request["reference"], request["issued"])
    try:
        reader.bind(pin)
    except Exception as error:
        previous = result
        result = (
            dict(
                kind=COMMON_START_REPORT_KIND if args.common_start else STARTING_REPORT_KIND,
                observations_match=None,
                common_starting_authority_established=False,
                numerical_parity_available=False,
                physical_checkpoint_credit=0,
                sides={
                    name: dict(authenticated=False, available=False)
                    for name in ("demo", "reference")
                },
            )
            if starting
            else compare_views(_empty(), _empty())
        )
        result.update(
            status="request_changed_during_comparison",
            unverified_forensics=previous,
            errors=dict(request=codec._issue(error)),
        )
    snapshot.write_json(args.output, result)
    if args.common_start:
        return int(result["status"] != "common_start_files_authenticated")
    return (
        int(result["status"] != "starting_observation_files_authenticated")
        if args.starting_rng
        else int(not result["endpoint_complete"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
