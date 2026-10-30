"""Execute pinned BETSE pulse/targeted-buffer AST on explicit supplied owners.

This is source arithmetic evidence, not native geometry/configuration, event
selection, a whole simulation or equality of native/Cells loop calendars.
"""

import ast
import copy
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.perturbations import physiology_calendar_native as calendars
from validation.perturbations import spatial_modulation_native as spatial
from validation.perturbations import time_modulation_native as modulators

PINNED = {
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
}


@lru_cache(maxsize=1)
def capture():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    trees = {}
    for name, digest in PINNED.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Pinned native source changed: " + name)
        trees[name] = ast.parse(data)
    pulse = copy.deepcopy(
        next(
            n
            for n in trees["betse/science/math/toolbox.py"].body
            if isinstance(n, ast.FunctionDef) and n.name == "pulse"
        )
    )
    cls = next(
        n
        for n in trees["betse/science/tissue/tishandler.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    method = methods["_fire_events_tissue"]
    expected = [
        "p.scheduled_options['Na_mem'] != 0",
        "p.scheduled_options['K_mem'] != 0",
        "p.scheduled_options['Cl_mem'] != 0 and p.ions_dict['Cl'] != 0",
        "p.scheduled_options['Ca_mem'] != 0 and p.ions_dict['Ca'] != 0",
    ]
    assert [ast.unparse(n.test) for n in method.body[4:8]] == expected
    wrapper = ast.parse("def targeted(self,phase,t):\n    pass\n").body[0]
    wrapper.body = copy.deepcopy(method.body[1:8])
    finalize = copy.deepcopy(methods["makeAllChanges"])
    finalize.decorator_list = []
    finalize.returns = None
    namespace = {"np": np}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[pulse, wrapper, finalize], type_ignores=[])),
            "<pinned BETSE permeability schedule>",
            "exec",
        ),
        namespace,
    )
    namespace["tb"] = SimpleNamespace(pulse=namespace["pulse"])
    return namespace


def evaluate(plan, binding, initial, current, loop_index):
    """Pinned membrane block at an explicit nominal or source-calendar label."""
    source = capture()
    time_s = loop_index * plan["physiological_dt_s"]
    source_hashes = dict(PINNED)
    if "native_calendar" in plan:
        calendar = calendars.evaluate(plan["native_calendar"], solver="normal")
        time_s = calendar["event_label_s"][loop_index]
        source_hashes.update(calendar["native_source_sha256"])
    axes = binding["inputs"]
    ions, membranes = axes["ion_ids"], axes["membrane_ids"]
    modifier = np.array(initial["diffusion"]["scheduled_m2_s"], dtype=float, copy=True)
    for row in plan["changes"]:
        if row["loop_index"] <= loop_index:
            modifier = np.array(row["scheduled_m2_s"], dtype=float, copy=True)
    sim = SimpleNamespace(
        Dm_cells=np.array(current["diffusion"]["current_m2_s"], copy=True),
        Dm_base=np.array(initial["diffusion"]["base_m2_s"], copy=True),
        Dm_scheduled=modifier,
        P_mod=np.asarray(0.0),
        P_base=np.asarray(0.0),
    )
    handler = SimpleNamespace(tissue_default=SimpleNamespace())
    p = SimpleNamespace(
        scheduled_options={ion + "_mem": 0 for ion in ("Na", "K", "Cl", "Ca")},
        ions_dict={ion: int(ion in ions) for ion in ("Cl", "Ca")},
    )
    seen = set()
    for row in plan["pulses"]:
        ion = row["ion_id"]
        if ion not in ("Na", "K", "Cl", "Ca") or ion in seen:
            raise ValueError("Native comparison requires at most one pulse per supported ion")
        seen.add(ion)
        p.scheduled_options[ion + "_mem"] = 1
        setattr(sim, "i" + ion, ions.index(ion))
        suffix = ion + "mem"

        def dynamic(t, v=row["dynamic_scale"]):
            return v

        factors = np.asarray(row["spatial_scalar"])
        if "spatial_modulator" in row:
            spatial_values = spatial.evaluate(row["spatial_modulator"])
            factors = spatial_values["factor"]
            assert spatial_values["dynamic"] == [1, 1, 1]
            source_hashes.update(spatial.PINNED)
        if "time_modulator" in row:
            scalar, function, _ = modulators.prepare(row["time_modulator"])
            assert scalar == 1

            def dynamic(t, v=row["dynamic_scale"], f=function):
                return v * f(t)

            source_hashes.update(modulators.PINNED)
        for name, value in dict(
            scalar_=factors,
            dyna_=dynamic,
            t_on_=row["on_s"],
            t_off_=row["off_s"],
            t_change_=row["change_s"],
            mem_mult_=row["multiplier"],
            targets_=[membranes.index(name) for name in row["membrane_ids"]],
        ).items():
            setattr(handler, name + suffix, value)
        setattr(handler.tissue_default, "Dm_" + ion, row["default_diffusion_m2_s"])
    if current["controls"]["phase"] == "SIM":
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            source["targeted"](
                handler,
                SimpleNamespace(sim=sim, p=p, cells=None),
                time_s,
            )
            source["makeAllChanges"](handler, sim)
    else:
        sim.Dm_scheduled = np.array(current["diffusion"]["scheduled_m2_s"], copy=True)
    return dict(
        current_m2_s=sim.Dm_cells,
        base_m2_s=sim.Dm_base,
        scheduled_m2_s=sim.Dm_scheduled,
        native_source_sha256=source_hashes,
    )
