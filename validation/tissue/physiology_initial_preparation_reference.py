"""Native selection/static sites, independent MT replay and SI coefficient mapping."""

import ast
import hashlib
import os
from decimal import Decimal, localcontext
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.perturbations import betse_perturbations_native as capture
from validation.perturbations import target_selection_native as target_native
from validation.tissue import physiology_permeability_view_reference as physical  # noqa: F401
from validation.tissue.physiology_protein_packet_provider_reference import _mt_uniforms
from validation.topology import random_tissue_profile_preparation_reference as profiles

PINNED = dict(target_native.PINNED) | {
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"
}


@lru_cache(maxsize=1)
def static_site():
    relative = "betse/science/sim.py"
    path = Path(os.environ["CELLS_BETSE_SOURCE"]) / relative
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINNED[relative]:
        raise ValueError("Native static initialization source changed")
    cls = next(
        n for n in ast.parse(data).body if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    method = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "init_dynamics"
    )
    first = next(
        i
        for i, n in enumerate(method.body)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "Dm_cellsA" for t in n.targets)
    )
    last = next(
        i
        for i, n in enumerate(method.body)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.Dm_cells[self.iK]" for t in n.targets)
    )
    statements = method.body[first : last + 1]
    code = compile(
        ast.fix_missing_locations(
            ast.Module(
                body=[capture.wrapper("static_init", "self,cells,p", statements)], type_ignores=[]
            )
        ),
        str(path),
        "exec",
    )
    return code, dict(
        source=relative,
        first_line=statements[0].lineno,
        last_line=statements[-1].end_lineno,
        sha256=PINNED[relative],
    )


def initial_diffusion(request, definition):
    layout = request["preparation"]["geometry"]["layout"]
    thickness = request["preparation"]["geometry"]["thickness_m"]
    model = definition["model"].get("ionic", definition["model"])
    patches = {row["id"]: row for row in model["membranes"]}
    with localcontext() as context:
        context.prec = 80
        return [
            [
                float(
                    Decimal.from_float(float(patches[mid]["permeability_m_per_s"][ion]))
                    * Decimal.from_float(float(thickness[mid]))
                )
                for mid in layout["membrane_ids"]
            ]
            for ion in request["component"]["ion_ids"]
        ]


def evaluate(request, definition):
    selected = profiles.prepare(request["preparation"])
    source = selected["native"]["numpy_state"]
    mids = request["preparation"]["geometry"]["layout"]["membrane_ids"]
    uniforms, successor = _mt_uniforms(source, len(mids))
    before = initial_diffusion(request, definition)
    rng = np.random.RandomState(0)
    rng.set_state((source[0], np.asarray(source[1], np.uint32), source[2], source[3], source[4]))
    code, site = static_site()
    namespace = {"np": capture.NumpyProxy(SimpleNamespace(random=rng.random))}
    exec(code, namespace)
    simulator = SimpleNamespace(
        Dm_cells=np.asarray(before).copy(),
        iK=request["component"]["ion_ids"].index("K"),
        mdl=len(mids),
        cdl=len(request["preparation"]["geometry"]["layout"]["cell_ids"]),
        P_cells=np.zeros(1),
    )
    level = request["component"]["controls"]["static_level"]
    namespace["static_init"](simulator, None, SimpleNamespace(channel_noise_level=level))
    assert simulator.channel_noise_factor.tolist() == uniforms
    assert target_native.numpy_state(rng) == successor
    independent = np.asarray(before).copy()
    potassium = request["component"]["ion_ids"].index("K")
    with localcontext() as context:
        context.prec = 80
        for i, uniform in enumerate(uniforms):
            independent[potassium, i] = float(
                Decimal.from_float(before[potassium][i])
                * (1 + Decimal.from_float(float(level)) * Decimal.from_float(uniform))
            )
    return dict(
        selection=selected,
        base_m2_s=before,
        uniforms=uniforms,
        current_m2_s=simulator.Dm_cells.tolist(),
        scheduled_m2_s=simulator.Dm_scheduled.tolist(),
        independent_current_m2_s=independent.tolist(),
        numpy_successor=successor,
        python_successor=selected["native"]["python_state"],
        static_source_site=site,
        scope=(
            "Native picker/static sites plus independent MT uniform and SI transforms; "
            "no full BETSE initialization"
        ),
    )
