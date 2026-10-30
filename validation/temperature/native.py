"""Unchanged isolated BETSE bodies with pinned source sites and temperature reads.

This does not import Cells, run a native simulation, patch equations, infer Q10,
or repair nonfinite native values. Non-numerical logging alone is a stand-in.
"""

import ast
import hashlib
import json
import os
import re
import warnings
from abc import ABCMeta, abstractmethod
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "source_manifest.json").read_text())
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
PARAMETERS = (
    "F",
    "R",
    "q",
    "kb",
    "NAv",
    "deltaGATP",
    "KmNK_Na",
    "KmNK_K",
    "KmNK_ATP",
    "KmCa_Ca",
    "KmCa_ATP",
)
NUMERIC_FIELDS = (
    "m",
    "h",
    "_mInf",
    "_hInf",
    "_mTau",
    "_hTau",
    "P",
    "time_unit",
    "qt",
    "Phi",
    "_mpower",
    "_hpower",
    "vrev",
    "v_corr",
)


def root():
    return Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))


@lru_cache(maxsize=None)
def source(path):
    payload = (root() / path).read_bytes()
    expected = MANIFEST["source_files"].get(path, MANIFEST["temperature_scan_files"].get(path))
    if expected is None or hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("Pinned temperature source changed: " + path)
    return payload.decode(), ast.parse(payload, filename=path)


def site(path, node):
    return dict(
        path=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        sha256=MANIFEST["source_files"].get(path, MANIFEST["temperature_scan_files"].get(path)),
        code=ast.get_source_segment(source(path)[0], node),
    )


def execute(nodes, path, namespace):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), namespace)


class Observed(SimpleNamespace):
    def __getattribute__(self, name):
        if name in ("T", "dt", "F", "R", "q", "kb", "deltaGATP", "cATP", "cADP", "cPi"):
            object.__getattribute__(self, "_reads").append(name)
        return super().__getattribute__(name)


def parameters(profile="literal_native", configured_temperature_K=298.15):
    path = "betse/science/parameters.py"
    tree = source(path)[1]
    selected = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr in PARAMETERS
        ):
            ast.literal_eval(node.value)  # All selected native constants must be literal.
            selected.append(node)
    if {node.targets[0].attr for node in selected} != set(PARAMETERS):
        raise ValueError("Incomplete native constant/affinity parameter capture")
    value = Observed(_reads=[])
    execute(sorted(selected, key=lambda row: row.lineno), path, dict(self=value))
    if profile == "matched_SI":
        value.q, value.kb, value.NAv = 1.602176634e-19, 1.380649e-23, 6.02214076e23
        value.F, value.R = value.NAv * value.q, value.NAv * value.kb
    elif profile != "literal_native":
        raise ValueError("Unknown declared constant profile")
    value.T, value.dt = configured_temperature_K, PROTOCOL["native_step_s"]
    value.cATP, value.cADP, value.cPi = 1.5, 0.1, 0.1
    value.alpha_NaK, value.alpha_Ca, value.serca_max = 1e-7, 2e-8, 3e-8
    return value


@lru_cache(maxsize=None)
def toolbox():
    path = "betse/science/sim_toolbox.py"
    names = {
        "electroflux",
        "pumpNaKATP",
        "pumpCaATP",
        "pumpCaER",
        "no_negs",
        "nernst_planck_flux",
        "nernst_planck_vector",
        "np_flux_special",
        "get_conductivity",
    }
    nodes = [
        node
        for node in source(path)[1].body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if len(nodes) != len(names):
        raise ValueError("Incomplete isolated temperature transport/pump bodies")
    namespace = dict(np=np, BetseSimUnstableException=RuntimeError)
    execute(nodes, path, namespace)
    return namespace


@lru_cache(maxsize=None)
def channel_module(relative):
    base_path = "betse/science/channels/channelsabc.py"
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        logs=SimpleNamespace(log_info=lambda *args, **kwargs: None),
    )
    execute(
        [node for node in source(base_path)[1].body if isinstance(node, ast.ClassDef)],
        base_path,
        namespace,
    )
    path = "betse/science/" + relative
    execute(
        [node for node in source(path)[1].body if isinstance(node, ast.ClassDef)], path, namespace
    )
    return namespace


def snapshot(channel):
    return {
        key: np.asarray(getattr(channel, key)).copy()
        for key in NUMERIC_FIELDS
        if hasattr(channel, key)
    }


def channel_probe(
    relative, name, *, configured_temperature_K, runtime_temperature_K, targeted=False
):
    p = parameters(configured_temperature_K=configured_temperature_K)
    p.sim = Observed(T=runtime_temperature_K, _reads=[])
    channel = channel_module(relative)[name]()
    voltage = np.asarray(PROTOCOL["voltage_V"], dtype=np.float64)
    targets = np.asarray([2, 0]) if targeted else None
    cells = SimpleNamespace(mem_i=np.arange(len(voltage)))
    with warnings.catch_warnings(record=True) as messages:
        warnings.simplefilter("always")
        channel.init(voltage.copy(), cells, p, targets=targets)
        initialized = snapshot(channel)
        count = channel.data_length
        if hasattr(channel, "m"):
            channel.m = np.full(count, PROTOCOL["initial_update_gates"][0])
        if hasattr(channel, "h"):
            channel.h = np.full(count, PROTOCOL["initial_update_gates"][1])
        before = snapshot(channel)
        channel.run(voltage.copy(), p)
        updated = snapshot(channel)
    cls = next(
        node
        for node in source("betse/science/" + relative)[1].body
        if isinstance(node, ast.ClassDef) and node.name == name
    )
    return dict(
        source=site("betse/science/" + relative, cls),
        class_name=name,
        configured_temperature_K=configured_temperature_K,
        runtime_temperature_K=runtime_temperature_K,
        voltage_V=voltage,
        targets=targets,
        selected_voltage_V=voltage if targets is None else voltage[targets],
        initialized=initialized,
        before=before,
        updated=updated,
        parameter_reads=tuple(p._reads),
        runtime_temperature_reads=tuple(p.sim._reads),
        ions=getattr(channel, "ions", []),
        relative_permeability=getattr(channel, "rel_perm", []),
        kinetic_gate=getattr(channel, "kinetic_gate", None),
        warnings=[str(row.message) for row in messages],
    )


def singular_channel_probe(name="Cav2p2", relative="channels/vg_ca.py", voltage_V=0.02):
    channel = channel_module(relative)[name]()
    with warnings.catch_warnings(record=True) as messages:
        warnings.simplefilter("always")
        channel.init(np.asarray([voltage_V]), None, parameters())
        channel._calculate_state(np.asarray([1000 * voltage_V]))
        raw = snapshot(channel)
    return dict(
        class_name=name,
        voltage_V=voltage_V,
        raw=raw,
        finite={key: np.isfinite(value) for key, value in raw.items()},
        warnings=[str(row.message) for row in messages],
        source_repaired=False,
    )


def transport_probe(temperature_K, profile="literal_native", *, configured_temperature_K=298.15):
    p = parameters(profile, configured_temperature_K)
    namespace = toolbox()
    voltage = np.asarray([-0.080, -0.035, 0.0, 0.040])
    outward, inward = np.asarray([145.0, 142.0, 130.0, 120.0]), np.asarray([12.0, 17.0, 22.0, 30.0])
    z = np.asarray([1.0, 1.0, -1.0, 2.0])
    diffusion, thickness = np.full(4, 1e-18), np.full(4, 5e-9)
    flux = namespace["electroflux"](
        outward.copy(),
        inward.copy(),
        diffusion,
        thickness,
        z.copy(),
        voltage.copy(),
        temperature_K,
        p,
    )
    common = dict(
        c=100.0, gcx=1e5, gcy=-5e4, gvx=100.0, gvy=-200.0, ux=1e-6, uy=-2e-6, D=1e-9, z=1.0, mu=1e-8
    )
    planar = namespace["nernst_planck_flux"](**common, T=temperature_K, p=p)
    vector = namespace["nernst_planck_vector"](100.0, 1e5, 100.0, 1e-6, 1e-9, 1.0, temperature_K, p)
    special = namespace["np_flux_special"](
        100.0, 80.0, 1e5, -5e4, 100.0, -200.0, 1e-6, -2e-6, 1e-9, 2e-9, 1.0, temperature_K, p
    )
    conductivity = namespace["get_conductivity"](1e-9, 1.0, 100.0, 1e-6, p)
    return dict(
        temperature_K=temperature_K,
        configured_temperature_K=configured_temperature_K,
        profile=profile,
        constants={key: getattr(p, key) for key in ("F", "R", "q", "kb", "NAv")},
        electroflux=dict(
            cA=outward, cB=inward, D=diffusion, d=thickness, z=z, voltage_V=voltage, result=flux
        ),
        nernst_planck=dict(inputs=common, planar=planar, vector=vector, special=special),
        conductivity=conductivity,
        parameter_reads=tuple(p._reads),
    )


def pump_probe(
    temperature_K,
    profile="literal_native",
    *,
    common_pool_projection=False,
    met_override=False,
    block_fraction=0.7,
):
    p = parameters(profile)
    nak_delta_g0 = p.deltaGATP
    native = toolbox()
    voltage = np.asarray([-0.080, -0.035, 0.0, 0.040])
    met = np.full((3, 4), 99.0) if met_override else None
    na = native["pumpNaKATP"](
        np.full(4, 12.0),
        np.full(4, 145.0),
        np.full(4, 140.0),
        np.full(4, 4.0),
        voltage,
        temperature_K,
        p,
        np.full(4, block_fraction),
        met=met,
    )
    if common_pool_projection:
        p.deltaGATP -= p.R * temperature_K * np.log(1000.0)
    ca = native["pumpCaATP"](
        np.full(4, 2e-4),
        np.full(4, 2.0),
        voltage,
        temperature_K,
        p,
        np.full(4, block_fraction),
        met=met,
    )
    er = native["pumpCaER"](np.full(4, 0.3), np.full(4, 2e-4), voltage, temperature_K, p)
    return dict(
        temperature_K=temperature_K,
        profile=profile,
        common_pool_projection=common_pool_projection,
        met_override=met_override,
        block_fraction=block_fraction,
        voltage_V=voltage,
        nak_delta_g0_J_mol=nak_delta_g0,
        parameters={
            key: getattr(p, key)
            for key in (*PARAMETERS, "cATP", "cADP", "cPi", "alpha_NaK", "alpha_Ca", "serca_max")
        },
        nak=na,
        pmca=ca,
        serca=er,
        parameter_reads=tuple(p._reads),
    )


def legacy_probe(temperature_K, profile="literal_native"):
    path = "betse/science/tissue/channels_o.py"
    node = next(
        row
        for row in source(path)[1].body
        if isinstance(row, ast.FunctionDef) and row.name == "cagPotassium"
    )
    namespace = dict(np=np)
    execute([node], path, namespace)
    voltage = np.asarray(PROTOCOL["voltage_V"])
    calcium = np.asarray([0.0, 2e-6, 2e-5, 2e-4])
    sim = Observed(
        T=temperature_K,
        _reads=[],
        iCa=0,
        iK=0,
        cc_cells=np.asarray([calcium]),
        vm=voltage,
        Dm_cag=np.zeros((1, 4)),
    )
    cells = SimpleNamespace(mem_to_cells=np.arange(4))
    dyna = SimpleNamespace(targets_cagK=np.arange(4), maxDmKcag=1e-18)
    p = parameters(profile)
    namespace["cagPotassium"](dyna, sim, cells, p)
    return dict(
        temperature_K=temperature_K,
        profile=profile,
        voltage_V=voltage,
        calcium_free_numeric_mM=calcium,
        opening=sim.Dm_cag[0] / dyna.maxDmKcag,
        constants=dict(F=p.F, R=p.R),
        runtime_temperature_reads=tuple(sim._reads),
        source=site(path, node),
        runtime_callsite_found=False,
    )


def junction_caller_probe(
    temperature_K, profile="literal_native", *, configured_temperature_K=298.15
):
    path = "betse/science/sim.py"
    cls = next(
        row
        for row in source(path)[1].body
        if isinstance(row, ast.ClassDef) and row.name == "Simulator"
    )
    node = next(
        row for row in cls.body if isinstance(row, ast.FunctionDef) and row.name == "update_gj"
    )
    p = parameters(profile, configured_temperature_K)
    p.v_sensitive_gj = False
    p.gj_surface = 1.0
    sim = Observed(
        T=temperature_K,
        _reads=[],
        vm=np.asarray([-0.060, -0.025]),
        gj_block=np.ones(2),
        cc_at_mem=np.asarray([[12.0, 14.0]]),
        D_gj=np.full((1, 2), 1e-10),
        zs=np.asarray([1.0]),
        mdl=2,
        fluxes_gj=np.zeros((1, 2)),
    )
    cells = SimpleNamespace(
        mem_i=np.asarray([0, 1]),
        nn_i=np.asarray([1, 0]),
        gj_len=np.full(2, 1e-6),
        mem_vects_flat=np.ones((2, 4)),
        gj_default_weights=np.ones(2),
        bflags_mems=np.zeros(2, dtype=bool),
    )
    calls = []

    def observed(*args, **kwargs):
        calls.append(
            dict(temperature_argument_K=float(args[6]), voltage_V=np.asarray(args[5]).copy())
        )
        return toolbox()["electroflux"](*args, **kwargs)

    namespace = dict(np=np, stb=SimpleNamespace(electroflux=observed))
    execute([node], path, namespace)
    namespace["update_gj"](sim, cells, p, 0.0, 0)
    return dict(
        temperature_K=temperature_K,
        configured_temperature_K=configured_temperature_K,
        profile=profile,
        passed_calls=calls,
        flux=sim.fluxes_gj,
        constants=dict(F=p.F, R=p.R),
        parameter_reads=tuple(p._reads),
        runtime_temperature_reads=tuple(sim._reads),
        source=site(path, node),
    )


def reaction_generators(temperature_K, profile="literal_native"):
    path = "betse/science/chemistry/networks.py"
    result = []
    for node in ast.walk(source(path)[1]):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "Keqm" for target in node.targets
        ):
            continue
        text = ast.get_source_segment(source(path)[0], node)
        if not any(
            "self." + name + "[" in text for name in ("reactions", "reactions_mit", "reactions_env")
        ):
            continue
        owner = SimpleNamespace(
            **{
                name: {"r": SimpleNamespace(delta_Go=-12000.0)}
                for name in ("reactions", "reactions_mit", "reactions_env")
            }
        )
        p = parameters(profile)
        sim = Observed(T=temperature_K, _reads=[])
        namespace = dict(self=owner, reaction_name="r", p=p, sim=sim, np=np)
        execute([node], path, namespace)
        expression = namespace["Keqm"]
        value = eval(compile(expression, path + ":" + str(node.lineno), "eval"), namespace)
        result.append(
            dict(
                source=site(path, node),
                expression=expression,
                value=float(value),
                delta_g0_J_mol=-12000.0,
                temperature_K=temperature_K,
                R=p.R,
                runtime_temperature_reads=tuple(sim._reads),
            )
        )
    if len(result) != 3:
        raise ValueError("Require all three native reaction equilibrium generators")
    return result


def inventory():
    rows = []

    class Scan(ast.NodeVisitor):
        def __init__(self, path):
            self.path, self.context = path, []

        def visit_ClassDef(self, node):
            self.context.append(node.name)
            self.generic_visit(node)
            self.context.pop()

        def visit_FunctionDef(self, node):
            self.context.append(node.name)
            self.generic_visit(node)
            self.context.pop()

        def visit_Attribute(self, node):
            if (
                node.attr == "T"
                and isinstance(node.value, ast.Name)
                and node.value.id in ("p", "sim", "self")
            ):
                rows.append(
                    dict(
                        source=site(self.path, node),
                        context=".".join(self.context),
                        kind={
                            "p": "configured_temperature",
                            "sim": "runtime_temperature",
                            "self": "context_self_temperature",
                        }[node.value.id],
                        access=type(node.ctx).__name__,
                    )
                )
            self.generic_visit(node)

        def visit_Constant(self, node):
            if isinstance(node.value, str) and re.search(r"\b(?:sim|p)\.T\b", node.value):
                rows.append(
                    dict(
                        source=site(self.path, node),
                        context=".".join(self.context),
                        kind="generated_expression_or_text",
                        access="literal",
                    )
                )

    for path in MANIFEST["temperature_scan_files"]:
        Scan(path).visit(source(path)[1])
    return rows


def catalog_sources():
    """Full supported bodies retain empirical metadata and commented-out scaling."""
    rows = []
    for relative, names in PROTOCOL["channel_classes"].items():
        path = "betse/science/" + relative
        classes = {
            node.name: node for node in source(path)[1].body if isinstance(node, ast.ClassDef)
        }
        for name in names:
            node = classes[name]
            assignments = []
            for child in ast.walk(node):
                if not isinstance(child, ast.Assign):
                    continue
                for target in child.targets:
                    key = (
                        target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
                    )
                    if key in ("Texpt", "qt", "time_unit", "Phi", "kinetic_gate"):
                        assignments.append(dict(name=key, source=site(path, child)))
            rows.append(dict(class_name=name, source=site(path, node), metadata=assignments))
    return rows
