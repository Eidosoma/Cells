#!/usr/bin/env python3
"""Code-blind references for the "neither" threshold of the gap-junction cancer replication.

Inputs, and the only inputs: the preprint (J. Grodstein, J. Mathews and M. Levin, bioRxiv
10.64898/2026.09.02.748840 v1, CC-BY 4.0) and the registered specification ``spec/neither.json``
read from the tag ``TAG``. numpy and scipy only; nothing here imports the engine or any other
module of this folder's parent package.

Subcommands (run from anywhere, pinned to one light CPU, e.g. ``taskset -c 6``):

    python -I neither_reference.py stage1 --run-dir DIR             # stage 1, once -> DIR/stage1.json
    python -I neither_reference.py search --geometry line --run-dir DIR
    python -I neither_reference.py search --geometry field --run-dir DIR
    python -I neither_reference.py interface --run-dir DIR [--check]  # -> interface/neither.json
    python -I neither_reference.py time --geometry field --d 1e-13    # cost of one point, nothing written

Each search writes DIR/<geometry>-points.jsonl as points finish and DIR/<geometry>.json at the end.
README.md in this folder holds the model, the integrator and the checks.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import scipy
import scipy.sparse as sp
from scipy.integrate import BDF, DOP853, Radau

TAG = "gj-neither-registered-2026-11-23"
SPEC_FORMAT = "gap_junction_tissue.neither_spec@1"
FORMAT = "gap_junction_tissue.neither_references@1"
SPEC_REL = "validation/gap_junction_tissue/references/spec/neither.json"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INTERFACE = HERE / "interface" / "neither.json"

NOMINAL = {"rtol": 1e-9, "atol": 1e-12}  # stage 2, BDF
TIGHTER_FACTOR = 10
STAGE1 = {"rtol": 1e-13, "atol": 1e-16}  # stage 1, DOP853
STAGE1_CROSS = {"rtol": 1e-12, "atol": 1e-15}  # stage 1 cross-check, Radau
STOP_FACTOR = Fraction(1001, 1000)  # hi <= (1 + 0.001) lo, tested exactly
N_SIDE = 25
N_TUMOR = 6

# The registered texts these references implement; the generator stops if any changes.
EQUATIONS = [
    "du/dt = g_u H(z; K_u, n_u, lambda_u) - k_u u + (junction terms, u only)",
    "dm/dt = g_m H(z; K_m, n_m, lambda_m) - k_m m",
    "dz/dt = g_z m sum_{i=0..6} C(6, i) l_i X^i / (1 + X)^6 - k_z z, X = u / x0",
    "H(z; K, n, lambda) = (1 + lambda (z/K)^n) / (1 + (z/K)^n)",
    "junction (a, b): its flux G (u_a - u_b) leaves a and enters b;"
    " G / V = D A_cell / (L_GJ V_cell) = 3 D / (r L_GJ)",
]
CONSTANT_KEYS = [
    "g_u", "K_u", "n_u", "lambda_u", "k_u", "g_m", "K_m", "n_m", "lambda_m", "k_m",
    "g_z", "x0", "l", "k_z", "radius_m", "junction_length_m", "g_over_v_per_d",
]
STAGES = {
    "uncoupled_s": 500.0,
    "coupled_s": 20000.0,
    "rule": "stage 1: one tumor cell and one healthy cell, no junctions, 500 s from the seeds, once;"
    " every tumor cell of stage 2 starts at stage 1's tumor end state, every healthy cell at its healthy"
    " one; stage 2 runs 20,000 s coupled, its clock from 0",
}
CRITERION = {
    "cell": "u > m + 2 at the end of stage 2, in every cell",
    "rows": "for every row, max m - min m <= 2; a row is the cells with one z (the last lattice index)",
}
GEOMETRY = {
    "line": {
        "lattice": "1 x 1 x 25: cells c0..c24 along z",
        "tumor": "z < 6 (c0..c5)",
        "junctions": "c_k - c_(k+1), k = 0..23",
        "rows": "each cell is its own row, so the spread condition is empty",
        "neighbours": 2,
    },
    "field": {
        "lattice": "1 x 25 x 25: cell c{y}_{z}, y and z in 0..24",
        "tumor": "y < 6 and z < 6 (a 6 x 6 block at the corner)",
        "junctions": "one per pair one lattice step apart (c{y}_{z} - c{y}_{z+1} and c{y}_{z} - c{y+1}_{z}),"
        " 1,200 in all; no diagonals",
        "rows": "row z holds c0_z .. c24_z",
        "neighbours": 4,
    },
}
EXPECTED_COUNTS = {"line": (25, 24, 6), "field": (625, 1200, 36)}  # cells, junctions, tumor cells
SEARCH_BRACKET = [0.0, 1e-13]
INTERFACE_KEYS = ["format", "registration", "model", "stage1", "geometries"]


# --------------------------------------------------------------------------- spec


def read_spec_text(spec_file: str | None) -> str:
    if spec_file is not None:
        return Path(spec_file).read_text()
    out = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{TAG}:{SPEC_REL}"], check=True, capture_output=True, text=True
    )
    return out.stdout


def validate_spec(spec: dict) -> None:
    def need(ok: bool, what: str) -> None:
        if not ok:
            raise ValueError(f"spec differs from the registered text these references implement: {what}")

    need(spec.get("format") == SPEC_FORMAT, "format")
    model = spec["model"]
    need(model["equations"] == EQUATIONS, "model.equations")
    need(list(model["constants"]) == CONSTANT_KEYS, "model.constants keys")
    need(len(model["constants"]["l"]) == 7, "model.constants.l")
    need({k: model["stages"][k] for k in STAGES} == STAGES, "model.stages")
    need({k: model["criterion"][k] for k in CRITERION} == CRITERION, "model.criterion")
    for name in ("tumor", "healthy"):
        need(set(model["seeds"][name]) == {"u", "m", "z"}, f"model.seeds.{name}")
    for name, text in GEOMETRY.items():
        need({k: spec["geometry"][name][k] for k in text} == text, f"geometry.{name}")
    need(spec["search"]["bracket"] == SEARCH_BRACKET, "search.bracket")
    need("hi <= (1 + 0.001) lo" in spec["search"]["stop"], "search.stop")
    need("ten-fold tighter integration tolerance" in spec["search"]["tighter"], "search.tighter")
    need(spec["interface"]["format"] == FORMAT, "interface.format")
    need(list(spec["interface"]["keys"]) == INTERFACE_KEYS, "interface.keys")
    c = model["constants"]
    geometric = 3.0 / (c["radius_m"] * c["junction_length_m"])
    need(abs(geometric - c["g_over_v_per_d"]) <= 1e-12 * c["g_over_v_per_d"], "g_over_v_per_d = 3 / (r L_GJ)")


# --------------------------------------------------------------------------- model


def _horner(coef: np.ndarray, x):
    acc = coef[-1] + 0.0 * x
    for a in coef[-2::-1]:
        acc = acc * x + a
    return acc


class Model:
    """One cell's miR200 (u), Zeb mRNA (m) and ZEB (z) rates, as model.equations writes them."""

    def __init__(self, constants: dict):
        c = constants
        self.gu, self.Ku, self.nu, self.lu, self.ku = c["g_u"], c["K_u"], c["n_u"], c["lambda_u"], c["k_u"]
        self.gm, self.Km, self.nm, self.lm, self.km = c["g_m"], c["K_m"], c["n_m"], c["lambda_m"], c["k_m"]
        self.gz, self.x0, self.kz = c["g_z"], c["x0"], c["k_z"]
        self.coef = np.array([math.comb(6, i) * c["l"][i] for i in range(7)], dtype=float)  # P(X) = sum coef_i X^i
        self.dcoef = np.array([i * self.coef[i] for i in range(1, 7)], dtype=float)
        self.g_over_v_per_d = c["g_over_v_per_d"]

    @staticmethod
    def hill(z, K, n, lam):
        r = (z / K) ** n
        return (1.0 + lam * r) / (1.0 + r)

    @staticmethod
    def hill_dz(z, K, n, lam):
        r = (z / K) ** n
        return (lam - 1.0) * n * (z / K) ** (n - 1.0) / K / (1.0 + r) ** 2

    def binding(self, u):
        x = u / self.x0
        return _horner(self.coef, x) / (1.0 + x) ** 6

    def binding_du(self, u):
        x = u / self.x0
        p, dp = _horner(self.coef, x), _horner(self.dcoef, x)
        return (dp * (1.0 + x) - 6.0 * p) / (1.0 + x) ** 7 / self.x0

    def rates(self, u, m, z):
        du = self.gu * self.hill(z, self.Ku, self.nu, self.lu) - self.ku * u
        dm = self.gm * self.hill(z, self.Km, self.nm, self.lm) - self.km * m
        dz = self.gz * m * self.binding(u) - self.kz * z
        return du, dm, dz

    def cell_jacobian(self, y):
        u, m, z = y
        return np.array(
            [
                [-self.ku, 0.0, self.gu * self.hill_dz(z, self.Ku, self.nu, self.lu)],
                [0.0, -self.km, self.gm * self.hill_dz(z, self.Km, self.nm, self.lm)],
                [self.gz * m * self.binding_du(u), self.gz * self.binding(u), -self.kz],
            ]
        )


class Network:
    """A geometry of geometry.<name>: cells, tumor mask, junctions and rows."""

    def __init__(self, name: str):
        self.name = name
        if name == "line":
            self.ids = [f"c{k}" for k in range(N_SIDE)]
            self.tumor = np.array([k < N_TUMOR for k in range(N_SIDE)])
            pairs = [(k, k + 1) for k in range(N_SIDE - 1)]
            self.rows = [np.array([k]) for k in range(N_SIDE)]  # each cell is its own row
            self.grid = None
        elif name == "field":
            index = lambda y, z: y * N_SIDE + z  # noqa: E731
            self.ids = [f"c{y}_{z}" for y in range(N_SIDE) for z in range(N_SIDE)]
            self.tumor = np.array([y < N_TUMOR and z < N_TUMOR for y in range(N_SIDE) for z in range(N_SIDE)])
            pairs = [(index(y, z), index(y, z + 1)) for y in range(N_SIDE) for z in range(N_SIDE - 1)]
            pairs += [(index(y, z), index(y + 1, z)) for y in range(N_SIDE - 1) for z in range(N_SIDE)]
            self.rows = [np.array([index(y, z) for y in range(N_SIDE)]) for z in range(N_SIDE)]  # row z
            self.grid = (N_SIDE, N_SIDE)  # [y, z]
        else:
            raise ValueError(name)
        self.n = len(self.ids)
        self.a = np.array([p[0] for p in pairs])
        self.b = np.array([p[1] for p in pairs])
        self.degree = np.bincount(np.concatenate([self.a, self.b]), minlength=self.n).astype(float)
        lap = sp.coo_matrix(
            (
                np.concatenate([self.degree, -np.ones(len(pairs)), -np.ones(len(pairs))]),
                (
                    np.concatenate([np.arange(self.n), self.a, self.b]),
                    np.concatenate([np.arange(self.n), self.b, self.a]),
                ),
            ),
            shape=(self.n, self.n),
        )
        self.laplacian = lap.tocsr()
        cells, junctions, tumor_cells = EXPECTED_COUNTS[name]
        if (self.n, len(pairs), int(self.tumor.sum())) != (cells, junctions, tumor_cells):
            raise AssertionError(f"{name}: cells, junctions or tumor count differ from the spec")
        if self.degree.max() != GEOMETRY[name]["neighbours"] or self.degree.min() < 1:
            raise AssertionError(f"{name}: neighbour count differs from the spec")
        if len({tuple(sorted(p)) for p in pairs}) != len(pairs):
            raise AssertionError(f"{name}: duplicate junction")
        if sorted(np.concatenate(self.rows).tolist()) != list(range(self.n)):
            raise AssertionError(f"{name}: rows do not partition the cells")


class Coupled:
    """Stage 2: every cell's rates plus the junction flux of u, G/V = g_over_v_per_d x D.

    The state interleaves cells: y = [u_0, m_0, z_0, u_1, m_1, z_1, ...].
    """

    def __init__(self, model: Model, net: Network, d: float):
        self.model, self.net, self.d = model, net, d
        self.gv = model.g_over_v_per_d * d
        n = net.n
        iu = 3 * np.arange(n)
        im, iz = iu + 1, iu + 2
        self.rows = np.concatenate([iu, iu, im, im, iz, iz, iz, 3 * net.a, 3 * net.b])
        self.cols = np.concatenate([iu, iz, im, iz, im, iu, iz, 3 * net.b, 3 * net.a])
        self.size = 3 * n
        self.nfev = 0

    def rhs(self, t, y):
        self.nfev += 1
        u, m, z = y[0::3], y[1::3], y[2::3]
        du, dm, dz = self.model.rates(u, m, z)
        if self.gv:
            du = du - self.gv * (self.net.laplacian @ u)
        out = np.empty_like(y)
        out[0::3], out[1::3], out[2::3] = du, dm, dz
        return out

    def jac(self, t, y):
        md = self.model
        u, m, z = y[0::3], y[1::3], y[2::3]
        n = self.net.n
        ones = np.ones(n)
        coupling = np.full(len(self.net.a), self.gv)
        vals = np.concatenate(
            [
                -md.ku - self.gv * self.net.degree,
                md.gu * md.hill_dz(z, md.Ku, md.nu, md.lu),
                -md.km * ones,
                md.gm * md.hill_dz(z, md.Km, md.nm, md.lm),
                md.gz * md.binding(u),
                md.gz * m * md.binding_du(u),
                -md.kz * ones,
                coupling,
                coupling,
            ]
        )
        return sp.csc_matrix((vals, (self.rows, self.cols)), shape=(self.size, self.size))


def check_jacobian(system: Coupled, y: np.ndarray) -> float:
    """Largest relative gap between the analytic Jacobian and central differences."""
    exact = system.jac(0.0, y).toarray()
    numeric = np.empty_like(exact)
    for k in range(y.size):
        h = 1e-6 * max(1.0, abs(y[k]))
        yp, ym = y.copy(), y.copy()
        yp[k] += h
        ym[k] -= h
        numeric[:, k] = (system.rhs(0.0, yp) - system.rhs(0.0, ym)) / (2 * h)
    return float(np.abs(exact - numeric).max() / max(1.0, np.abs(exact).max()))


# --------------------------------------------------------------------------- integration


def integrate(solver_cls, fun, y0, t_end, jac=None, **tol):
    """Step a scipy solver to t_end keeping only the final state; returns (y, stats)."""
    kwargs = dict(tol)
    if jac is not None:
        kwargs["jac"] = jac
    solver = solver_cls(fun, 0.0, np.array(y0, dtype=float), t_end, **kwargs)
    steps = 0
    while solver.status == "running":
        message = solver.step()
        steps += 1
        if solver.status == "failed":
            raise RuntimeError(f"{solver_cls.__name__} failed at t = {solver.t}: {message}")
    if solver.t != t_end:
        raise RuntimeError("integration did not end at t_end")
    stats = {"steps": steps, "nfev": solver.nfev, "njev": getattr(solver, "njev", 0), "nlu": getattr(solver, "nlu", 0)}
    return np.array(solver.y), stats


def stage1(model: Model, seeds: dict, t_end: float) -> dict:
    """Stage 1, once: one tumor and one healthy cell, uncoupled, from the seeds."""

    def fun(t, y):
        return np.array(model.rates(*y))

    def jac(t, y):
        return model.cell_jacobian(y)

    out = {}
    for name in ("tumor", "healthy"):
        y0 = [seeds[name][k] for k in ("u", "m", "z")]
        y, stats = integrate(DOP853, fun, y0, t_end, **STAGE1)
        cross, _ = integrate(Radau, fun, y0, t_end, jac=jac, **STAGE1_CROSS)
        out[name] = {
            "state": dict(zip(("u", "m", "z"), map(float, y))),
            "radau_rel_gap": float(np.max(np.abs(cross - y) / np.abs(y))),
            "max_abs_rate_end": float(np.abs(fun(t_end, y)).max()),
            "steps": stats["steps"],
        }
    return out


def start_state(net: Network, stage1_states: dict) -> np.ndarray:
    tumor = [stage1_states["tumor"][k] for k in ("u", "m", "z")]
    healthy = [stage1_states["healthy"][k] for k in ("u", "m", "z")]
    return np.concatenate([tumor if is_tumor else healthy for is_tumor in net.tumor]).astype(float)


def assess(net: Network, y: np.ndarray) -> dict:
    """The criterion at the end of stage 2 (model.criterion)."""
    u, m = y[0::3], y[1::3]
    margin = u - m - 2.0
    epithelial = int(np.count_nonzero(margin > 0.0))
    spread = max(float(m[row].max() - m[row].min()) for row in net.rows)
    normalized = bool(epithelial == net.n and spread <= 2.0)
    return {
        "normalized": normalized,
        "epithelial_cells": epithelial,
        "min_margin": float(margin.min()),
        "max_row_spread": spread,
    }


def run_point(model: Model, net: Network, start: np.ndarray, d: float, t_end: float, method: str, rtol: float, atol: float) -> dict:
    system = Coupled(model, net, d)
    began = time.perf_counter()
    if method == "BDF":
        y, stats = integrate(BDF, system.rhs, start, t_end, jac=system.jac, rtol=rtol, atol=atol)
    elif method == "DOP853":
        y, stats = integrate(DOP853, system.rhs, start, t_end, rtol=rtol, atol=atol)
    else:
        raise ValueError(method)
    seconds = time.perf_counter() - began
    record = {"d": d, **assess(net, y)}
    if record["normalized"] != (record["min_margin"] > 0.0 and record["max_row_spread"] <= 2.0):
        raise AssertionError("outcome does not follow from the recorded numbers")
    diag = {
        "method": method,
        "rtol": rtol,
        "atol": atol,
        "max_abs_rate_end": float(np.abs(system.rhs(t_end, y)).max()),
        "min_state": float(y.min()),
        "seconds": round(seconds, 3),
        **stats,
    }
    if net.grid is not None:  # the field is symmetric under y <-> z; rows stay rows of one z
        state = y.reshape(net.grid + (3,))
        diag["symmetry_rel"] = float(np.abs(state - state.transpose(1, 0, 2)).max() / np.abs(state).max())
        if diag["symmetry_rel"] > 1e-6:
            raise AssertionError(f"field end state not symmetric under y <-> z ({diag['symmetry_rel']:.2e})")
    return {"point": record, "diag": diag}


# --------------------------------------------------------------------------- provenance and files


def provenance() -> dict:
    def git(*args):
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()

    return {
        "head": git("rev-parse", "HEAD"),
        "dirty": git("status", "--porcelain", "--", str(HERE.relative_to(REPO))),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "spec": f"git show {TAG}:{SPEC_REL}",
    }


def load_inputs(spec_file: str | None):
    spec = json.loads(read_spec_text(spec_file))
    validate_spec(spec)
    return spec, Model(spec["model"]["constants"])


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1) + "\n")
    tmp.replace(path)


# --------------------------------------------------------------------------- commands


def cmd_stage1(args) -> int:
    spec, model = load_inputs(args.spec)
    run_dir = Path(args.run_dir)
    result = stage1(model, spec["model"]["seeds"], spec["model"]["stages"]["uncoupled_s"])
    write_json(run_dir / "stage1.json", {"provenance": provenance(), "stage1": result, "tolerance": STAGE1, "cross": STAGE1_CROSS})
    print(json.dumps(result, indent=1))
    return 0


def cmd_time(args) -> int:
    spec, model = load_inputs(args.spec)
    net = Network(args.geometry)
    states = {k: v["state"] for k, v in stage1(model, spec["model"]["seeds"], spec["model"]["stages"]["uncoupled_s"]).items()}
    start = start_state(net, states)
    gap = check_jacobian(Coupled(model, net, args.d), start * (1.0 + 0.01 * np.sin(np.arange(start.size))))
    print(f"jacobian check: {gap:.2e}")
    result = run_point(model, net, start, args.d, spec["model"]["stages"]["coupled_s"], args.method, args.rtol, args.atol)
    print(json.dumps(result))
    return 0


def cmd_search(args) -> int:
    spec, model = load_inputs(args.spec)
    net = Network(args.geometry)
    run_dir = Path(args.run_dir)
    stage1_file = json.loads((run_dir / "stage1.json").read_text())
    states = {k: v["state"] for k, v in stage1_file["stage1"].items()}
    start = start_state(net, states)
    t_end = spec["model"]["stages"]["coupled_s"]
    jac_gap = max(
        check_jacobian(Coupled(model, net, d), start * (1.0 + 0.01 * np.sin(np.arange(start.size))))
        for d in (0.0, SEARCH_BRACKET[1])
    )
    if jac_gap > 1e-6:
        raise AssertionError(f"analytic Jacobian differs from central differences ({jac_gap:.2e})")
    log = run_dir / f"{args.geometry}-points.jsonl"
    log.unlink(missing_ok=True)
    prov = provenance()
    points, diags = [], []

    def evaluate(d: float, phase: str, method: str = "BDF", factor: int = 1) -> dict:
        res = run_point(model, net, start, d, t_end, method, NOMINAL["rtol"] / factor, NOMINAL["atol"] / factor)
        with log.open("a") as fh:
            fh.write(json.dumps({"phase": phase, **res["point"], **res["diag"]}) + "\n")
        print(f"{args.geometry} {phase} d={d!r} {res['point']} {res['diag']}", flush=True)
        if phase == "search":
            points.append(res["point"])
            diags.append(res["diag"])
        return res

    lo_d, hi_d = SEARCH_BRACKET
    if evaluate(lo_d, "search")["point"]["normalized"]:
        raise RuntimeError("D = 0 normalizes; stop and report")
    if not evaluate(hi_d, "search")["point"]["normalized"]:
        raise RuntimeError("D = 1e-13 does not normalize; stop and report")
    while not Fraction(hi_d) <= STOP_FACTOR * Fraction(lo_d):
        mid = (lo_d + hi_d) / 2.0
        if not lo_d < mid < hi_d:
            raise ArithmeticError("bracket cannot be split in binary64")
        if evaluate(mid, "search")["point"]["normalized"]:
            hi_d = mid
        else:
            lo_d = mid
    tighter = {d: evaluate(d, "tighter", factor=TIGHTER_FACTOR) for d in (lo_d, hi_d)}
    explicit = {d: evaluate(d, "explicit", method="DOP853") for d in (lo_d, hi_d)}
    ordered = sorted(points, key=lambda p: p["d"])
    outcomes = [p["normalized"] for p in ordered]
    if outcomes != sorted(outcomes):
        raise AssertionError("points are not monotone in d")
    summary = {
        "provenance": prov,
        "geometry": args.geometry,
        "bracket": [lo_d, hi_d],
        "points": ordered,
        "tighter": {
            "factor": TIGHTER_FACTOR,
            "lo_normalized": tighter[lo_d]["point"]["normalized"],
            "hi_normalized": tighter[hi_d]["point"]["normalized"],
        },
        "explicit": {
            "lo_normalized": explicit[lo_d]["point"]["normalized"],
            "hi_normalized": explicit[hi_d]["point"]["normalized"],
        },
        "end_diagnostics": {
            "nominal": {repr(d): next(dg for p, dg in zip(points, diags) if p["d"] == d) for d in (lo_d, hi_d)},
            "tighter": {repr(d): tighter[d] for d in (lo_d, hi_d)},
            "explicit": {repr(d): explicit[d] for d in (lo_d, hi_d)},
        },
        "max_abs_rate_end_search": max(dg["max_abs_rate_end"] for dg in diags),
        "seconds_total": round(sum(dg["seconds"] for dg in diags), 1),
        "jacobian_check": jac_gap,
    }
    write_json(run_dir / f"{args.geometry}.json", summary)
    return 0


def geometry_method(summary: dict, stage1_file: dict) -> str:
    ends = summary["end_diagnostics"]  # nominal: diagnostics; tighter and explicit: {point, diag}
    lo_d, hi_d = summary["bracket"]
    sides = (("lo", lo_d), ("hi", hi_d))
    point = {p["d"]: p for p in summary["points"]}
    rate = {
        side: max(
            ends["nominal"][repr(d)]["max_abs_rate_end"],
            *(ends[group][repr(d)]["diag"]["max_abs_rate_end"] for group in ("tighter", "explicit")),
        )
        for side, d in sides
    }
    nominal_margin = {side: point[d]["min_margin"] for side, d in sides}
    margin_gap = {
        side: max(
            abs(ends[group][repr(d)]["point"]["min_margin"] - point[d]["min_margin"]) for group in ("tighter", "explicit")
        )
        for side, d in sides
    }
    radau_gap = max(v["radau_rel_gap"] for v in stage1_file["stage1"].values())
    moving = [side for side in ("lo", "hi") if rate[side] > 1e-6]
    text = (
        f"stage 2 integrated by scipy {scipy.__version__} BDF (variable-order backward differentiation) with the"
        f" analytic sparse Jacobian (checked against central differences), rtol {NOMINAL['rtol']:g}, atol"
        f" {NOMINAL['atol']:g}, over the full 20,000 s from stage 1's end states; stage 1 once by DOP853 at rtol"
        f" {STAGE1['rtol']:g}, atol {STAGE1['atol']:g} (Radau at rtol {STAGE1_CROSS['rtol']:g} agrees to"
        f" {radau_gap:.0e} relative); G/V = g_over_v_per_d x D on u only; outcome at t = 20,000 s: u > m + 2 in"
        " every cell and max m - min m <= 2 in every row; search: both ends of [0, 1e-13] first, then arithmetic"
        f" bisection until hi <= 1.001 lo, tested in exact rationals ({len(summary['points'])} points); tighter:"
        f" both final ends rerun at rtol {NOMINAL['rtol'] / TIGHTER_FACTOR:g}, atol"
        f" {NOMINAL['atol'] / TIGHTER_FACTOR:g}; independent check: both final ends rerun with explicit DOP853 at"
        f" rtol {NOMINAL['rtol']:g}, atol {NOMINAL['atol']:g}, which keeps both outcomes; at lo and hi the"
        f" least margin u - m - 2 is {nominal_margin['lo']:.6g} and {nominal_margin['hi']:.6g}, and the tighter"
        f" and explicit reruns move it by at most {margin_gap['lo']:.0e} and {margin_gap['hi']:.0e}; largest"
        f" |dy/dt| at t = 20,000 s: {rate['lo']:.1e} per s at lo, {rate['hi']:.1e} per s at hi"
    )
    if moving:
        text += (
            f" (at {' and '.join(moving)} the end state is still changing at t = 20,000 s; its outcome is the"
            " state at that time, as the criterion defines)"
        )
    if summary["geometry"] == "field":
        text += "; every end state is symmetric under y <-> z to within 1e-6 relative"
    text += f"; run at {summary['provenance']['head'][:12]}"
    return text


def build_interface(spec: dict, run_dir: Path) -> dict:
    stage1_file = json.loads((run_dir / "stage1.json").read_text())
    geometries = {}
    for name in ("line", "field"):
        path = run_dir / f"{name}.json"
        if not path.exists():
            continue  # absent: not computed, then not assessable
        summary = json.loads(path.read_text())
        lo_d, hi_d = summary["bracket"]
        if not (Fraction(hi_d) <= STOP_FACTOR * Fraction(lo_d)):
            raise AssertionError(f"{name}: bracket misses the stopping rule")
        if not (summary["tighter"]["hi_normalized"] and not summary["tighter"]["lo_normalized"]):
            raise AssertionError(f"{name}: tighter tolerance changed an outcome")
        if not (summary["explicit"]["hi_normalized"] and not summary["explicit"]["lo_normalized"]):
            raise AssertionError(f"{name}: the explicit DOP853 check changed an outcome")
        geometries[name] = {
            "bracket": [lo_d, hi_d],
            "points": summary["points"],
            "tighter": summary["tighter"],
            "method": geometry_method(summary, stage1_file),
        }
    seeds = spec["model"]["seeds"]
    return {
        "format": FORMAT,
        "registration": TAG,
        "model": {
            "constants": spec["model"]["constants"],
            "seeds": {name: dict(seeds[name]) for name in ("tumor", "healthy")},
        },
        "stage1": {name: stage1_file["stage1"][name]["state"] for name in ("tumor", "healthy")},
        "geometries": geometries,
    }


def cmd_interface(args) -> int:
    spec, _ = load_inputs(args.spec)
    text = json.dumps(build_interface(spec, Path(args.run_dir)), indent=1) + "\n"
    out = Path(args.out)
    if args.check:
        if not out.exists() or out.read_text() != text:
            print(f"MISMATCH: {out} differs from the run's results", file=sys.stderr)
            return 1
        print(f"ok: {out} matches the run's results")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", help="read the spec from this file instead of git show TAG:...")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("stage1")
    p.add_argument("--run-dir", required=True)
    p = sub.add_parser("search")
    p.add_argument("--geometry", choices=("line", "field"), required=True)
    p.add_argument("--run-dir", required=True)
    p = sub.add_parser("time")
    p.add_argument("--geometry", choices=("line", "field"), required=True)
    p.add_argument("--d", type=float, required=True)
    p.add_argument("--method", choices=("BDF", "DOP853"), default="BDF")
    p.add_argument("--rtol", type=float, default=NOMINAL["rtol"])
    p.add_argument("--atol", type=float, default=NOMINAL["atol"])
    p = sub.add_parser("interface")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--out", default=str(INTERFACE))
    p.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return {"stage1": cmd_stage1, "time": cmd_time, "search": cmd_search, "interface": cmd_interface}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
