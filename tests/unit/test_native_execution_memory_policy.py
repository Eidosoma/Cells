"""Execute the real resource/CLI definitions with inert launch delegates.

No model module, numerical library, owner or simulation is imported. The
inherited hard-limit model reproduces Linux's refusal to raise a hard limit.
"""

import argparse
import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
GIB = 2**30
METADATA = 512 * 2**20
MODULES = (
    "native_seed_demo",
    "native_seed_demo_launch",
    "native_seed_world_callback_prelude",
    "native_seed_world_geometry_qualification",
    "native_init_terminal_reference",
    "native_sim_reference",
)


class Rejected(ValueError):
    def __init__(self, message, *, stage=None):
        super().__init__(message)
        self.stage = stage


def require(value, message, *_args):
    if not value:
        raise Rejected(message)


def definitions(name, names, **overrides):
    path = ROOT / "validation/betse" / (name + ".py")
    tree = ast.parse(path.read_bytes())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)
        or isinstance(node, ast.FunctionDef)
        and node.name in names
    ]
    ns = dict(
        __doc__="Resource controls",
        argparse=argparse,
        json=json,
        Path=Path,
        require=require,
        _require=require,
        DemoRejected=Rejected,
        PreludeRejected=Rejected,
        QualificationRejected=Rejected,
        **overrides,
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


def policies(name):
    ns = definitions(name, {"POLICY", "NATIVE_CPU", "NATIVE_POLICY"})
    return ns.get("NATIVE_POLICY", ns.get("POLICY"))


@pytest.mark.parametrize("name", MODULES[:-1])
def test_native_memory_policy_separates_resident_and_virtual_budget(name):
    policy = policies(name)
    assert policy["max_rss_bytes"] == 4 * GIB
    assert policy["max_address_space_bytes"] == 8 * GIB
    assert policy["reserve_bytes"] == 8 * GIB
    assert policy["threads"] == 1
    assert policy["cpu"] == (5 if name == "native_init_terminal_reference" else 0)
    assert policy["wall_seconds"] == (480 if "world_" in name else 7200)
    if name == "native_seed_world_geometry_qualification":
        assert definitions(name, {"POLICY"})["POLICY"]["software_bytes"] == GIB


@pytest.mark.parametrize(
    "name", [n for n in MODULES if n not in ("native_seed_demo_launch", "native_sim_reference")]
)
@pytest.mark.parametrize("defect", [None, "address_space", "cpu", "thread", "cuda"])
def test_native_memory_resource_checks_admit_new_budget_and_keep_other_limits(name, defect):
    policy = policies(name)
    env = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"),
        "1",
    )
    env["CUDA_VISIBLE_DEVICES"] = "0" if defect == "cuda" else ""
    if defect == "thread":
        env["OMP_NUM_THREADS"] = "2"
    limit = 8 * GIB + (1 if defect == "address_space" else 0)
    ns = definitions(
        name,
        {"POLICY", "NATIVE_POLICY", "NATIVE_CPU", "_resources"},
        resource=NS(RLIMIT_AS=9, getrlimit=lambda _: (limit, limit)),
        os=NS(environ=env, sched_getaffinity=lambda _: {99 if defect == "cpu" else policy["cpu"]}),
        guard_memory_available=lambda: 16 * GIB,
    )
    # Only the real /proc memory availability read is substituted.
    ns["Path"] = lambda _: NS(read_text=lambda: "MemAvailable: 16777216 kB\n")
    if defect is None:
        ns["_resources"]()
    else:
        with pytest.raises(Rejected):
            ns["_resources"]()


@pytest.mark.parametrize("limit", [GIB, 4 * GIB, 8 * GIB, 8 * GIB + 1])
def test_native_memory_worker_requires_exact_declared_virtual_cap(limit):
    calls = []
    ns = definitions(
        "native_seed_demo_launch",
        {"POLICY", "_worker_environment"},
        THREADS=(),
        environment=lambda *_: {},
        os=NS(environ={}),
        resource=NS(RLIMIT_AS=9, getrlimit=lambda _: (limit, limit)),
        resources=NS(memory_available=lambda: 16 * GIB),
        _parameter=lambda: NS(_runtime_entry=lambda r: calls.append(r)),
    )
    ns["environment"] = lambda *_: dict.fromkeys(
        (
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
            "PYTHONOPTIMIZE",
            "PYTHONPYCACHEPREFIX",
            "PYTHONPATH",
            "CUDA_VISIBLE_DEVICES",
            "JAX_PLATFORMS",
            "MPLCONFIGDIR",
            "XDG_CACHE_HOME",
            "TMPDIR",
            "TEMP",
            "TMP",
        )
    )
    # Use an actual nonexistent path; no runtime directory is created.
    ns["Path"] = Path
    plan = dict(source="/does-not-exist-memory-policy-control", release_environment={}, runtime="r")
    if limit == 8 * GIB:
        ns["_worker_environment"](plan, Path("/unused/worker"))
        assert calls == ["r"]
    else:
        with pytest.raises(Rejected, match="address-space"):
            ns["_worker_environment"](plan, Path("/unused/worker"))
        assert calls == []


class InheritedLimits:
    RLIMIT_AS = 9

    def __init__(self):
        self.limits = (2**60, 2**60)
        self.events = []

    def setrlimit(self, kind, limits):
        assert kind == self.RLIMIT_AS and 0 < limits[0] <= limits[1]
        if limits[1] > self.limits[1]:
            raise ValueError("not allowed to raise maximum limit")
        self.limits = limits
        self.events.append(limits)


@pytest.mark.parametrize(
    "name", ["native_seed_demo_launch", "native_sim_reference", "native_init_terminal_reference"]
)
def test_native_memory_cli_parent_hard_limit_allows_worker_budget(name, monkeypatch):
    limits, delegated = InheritedLimits(), []
    ns = definitions(
        name,
        {"POLICY", "NATIVE_POLICY", "main"},
        resource=limits,
        initial=NS(
            NATIVE_POLICY=policies("native_init_terminal_reference"), MODES=("original", "disabled")
        ),
        MODES=("original", "disabled"),
        RELEASE="unused_control_release",
        os=NS(environ={}),
    )

    def delegate(*args, **kwargs):
        delegated.append(limits.limits)
        return dict(status="completed")

    for operation in ("launch", "controller", "worker", "supervise", "evaluate"):
        ns[operation] = delegate
    if name == "native_seed_demo_launch":
        commands = [
            ["--launch", "/plan", "--output", "/out"],
            ["--controller", "/plan", "--output", "/out"],
            ["--worker", "/plan", "--output", "/out"],
        ]
    elif name == "native_sim_reference":
        commands = [
            ["--controller", "/out", "--prepared", "/plan", "--prepared-sha256", "hash"],
            ["--prepared", "/plan", "--prepared-sha256", "hash", "--output", "/out"],
        ]
    else:
        commands = [
            ["--controller", "/plan", "--prepared-sha256", "hash", "--output", "/out"],
            ["--worker", "/plan", "--prepared-sha256", "hash", "--output", "/out"],
        ]
    for command in commands:
        monkeypatch.setattr("sys.argv", ["memory-control", *command])
        assert ns["main"]() == 0
    expected = [(METADATA, 8 * GIB)] * (len(commands) - 1) + [(8 * GIB, 8 * GIB)]
    assert limits.events == delegated == expected
