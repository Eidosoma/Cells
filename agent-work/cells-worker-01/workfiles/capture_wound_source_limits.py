"""Compact raw wound init/run audit; no replacement channel or guessed clock."""

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
from abc import ABCMeta, abstractmethod
from pathlib import Path
from types import SimpleNamespace

import numpy as np

CHECKOUT = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
FILES = {
    "betse/science/channels/wound_channel.py":
        "a6a545e4e814e7e378d069f9ace425895b9a78c4bb44554a9513dd184e573035",
    "betse/science/channels/channelsabc.py":
        "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4",
    "betse/science/tissue/tishandler.py":
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54",
}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(
        ["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == REVISION
    for relative, expected in FILES.items():
        data = (INSTALLED / relative).read_bytes()
        assert data == (CHECKOUT / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(INSTALLED / relative, target)
    shutil.copyfile(__file__, output / "audit-source.py")
    namespace = dict(np=np, ABCMeta=ABCMeta, abstractmethod=abstractmethod,
                     logs=SimpleNamespace(log_info=lambda *_: None))
    for relative, names in (
        ("betse/science/channels/channelsabc.py", {"ChannelsABC"}),
        ("betse/science/channels/wound_channel.py", {"WoundABC", "TRP"}),
    ):
        module = ast.parse((INSTALLED / relative).read_text())
        nodes = [n for n in module.body if isinstance(n, ast.ClassDef) and n.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(INSTALLED / relative),
                     "exec"), namespace)
    vm = np.array([-.080, -.040, 0., .060])
    cells = SimpleNamespace(mem_i=np.arange(4))
    sim = SimpleNamespace(mdl=4)
    p = SimpleNamespace(dt=.001, wound_close_factor=.2)
    failures = []
    for phase in ("init", "run"):
        obj = namespace["TRP"]()
        if phase == "run":
            # Declared logical input context only; original methods stay unchanged.
            obj.targets = np.arange(4)
            obj.W_factor, obj.W_decay = 2., p.wound_close_factor
        try:
            obj.init(vm, cells, p) if phase == "init" else obj.run(vm, p)
        except TypeError as exc:
            record = dict(status="captured-native-failure", phase=phase,
                          exception=dict(type=type(exc).__name__, message=str(exc)),
                          voltage_V=vm.tolist(), dt_s=p.dt,
                          wound_factor_present=hasattr(obj, "W_factor"),
                          wound_factor=getattr(obj, "W_factor", None),
                          time_unit_present=hasattr(obj, "time_unit"))
            write(output / ("native-" + phase + "-failure.json"), record)
            failures.append(record)
        else:
            raise AssertionError("Expected unchanged source signature failure")
    obj = namespace["TRP"]()
    obj._init_state(vm * 1000, sim, p)
    obj._calculate_state(vm * 1000, sim, p)
    assert not hasattr(obj, "time_unit")
    assert (obj._mpower, obj._hpower) == (0, 0)
    result = dict(status="source-limits-confirmed", revision=revision, source_sha256=FILES,
                  audit_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  affinity=sorted(os.sched_getaffinity(0)), raw_failures=failures,
                  direct_subclass_metadata_only=dict(powers=[0, 0], targets=[1, 1],
                      raw_taus=[1, 1], time_unit_defined=False),
                  active_factor_step="W_factor-W_factor*W_decay*p.dt (forward Euler)",
                  factor_feedback_and_ionic_transport="commented out",
                  whole_native_success=False, replacement_component_created=False)
    write(output / "audit.json", result)
    print(json.dumps(dict(status=result["status"], raw_failures=len(failures))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    capture(parser.parse_args().output)
