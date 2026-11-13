"""Where one IMEX step's time goes, by piece, and the field operators' sparsity (one world).

Companion to scripts/profile_dispatch.py (same inputs and provenance), for the question of
docs/FIELD_SOLVER_INTERFACE_DESIGN.md: how much of a step is the dense node-space linear
algebra (the IMEX operator's assembly and Cholesky, the stage and capacitor triangular
solves, the offset products and LU solves), and how sparse those operators are. Parts:
  pieces    each piece compiled alone (jit, one world, unbatched) at the first
            definition's checkpoint state and timed (median of --repeat calls after a
            warm-up): the checked step; its start-of-step field solve; the IMEX operator's
            build (face weights and face Laplacian) and factorisation (factor_operator:
            assembly and dense Cholesky), and the Cholesky alone; one stage solve (both
            triangular solves and the residual's matrix-vector product); the device row
            checks; and the field solve's parts: one capacitor solve, the offset face
            product, the offset Jacobian product and one offset LU solve. Values of the
            synthetic inputs do not change these kernels' work (no data-dependent control).
            Per-step counts come from the code (numerics/surface_field.solve,
            models/surface_pump_v3.imex_step) and the field solve's Newton iterations.
            --batch N times the same pieces again, each vmapped over N copies of its inputs
            (the batched programs' costs, without a profiler).
  sparsity  host only (NumPy, SciPy): every definition's capacitor matrix, face Laplacian,
            reduced IMEX operator, capacitor solve matrix, incidence matrices and offset
            matrices: size, nonzeros and the Cholesky factor's nonzeros (fill) and
            multiply-adds in natural, reverse Cuthill-McKee and minimum-degree order.
  drift     host only: the free IMEX operator's condition number (plain and Jacobi-scaled)
            at --snapshot and at each of --snapshots, and how far it moves from the
            reference (largest |lambda - 1| of M_ref^-1 M), for iterative and reuse methods.
  trace     a kernel-level profile of --worlds copies of the first definition's state:
            the vmapped checked step and device checks, --repeat traced calls after a
            warm-up (jax.profiler, Perfetto trace kept beside --out), every executed
            instruction's own time (nested events, such as a while loop's body, subtracted)
            by operation class through the compiled module's op_name metadata: dense
            Cholesky, triangular solves, LU, dense products, scatters, gathers, copies and
            the rest; --without-checks traces the step alone (rerunnable unchanged on the
            CPU, the L4 and GH200).
Usage (from a frozen source snapshot):
  JAX_PLATFORMS=cpu PYTHONPATH=src:. python scripts/profile_step.py pieces \\
      --definitions world-1.json --snapshot snapshots/t00008.000 --out pieces.json
"""

import argparse
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from time import perf_counter

os.environ.setdefault("JAX_ENABLE_X64", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402
import profile_dispatch as pd  # noqa: E402  (inputs and provenance; the checkout on the path)

from cells.core.grid import EventGrid  # noqa: E402
from cells.core.schedule import control_values  # noqa: E402
from cells.core.state import initialise  # noqa: E402
from cells.models import surface_tissue as tissue  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from cells.numerics import surface_field as field  # noqa: E402
from cells.numerics import surface_imex as imex  # noqa: E402


def checkpoint(args, index=1):
    """(spec, checkpoint) of definition `index` (1-based) at --snapshot (or its start)."""
    specs, checkpoints = pd.load(args)
    spec = specs[index - 1]
    return spec, checkpoints[index] if checkpoints else initialise(spec)


def step_inputs(spec, start):
    """(dt, control) of the step from the checkpoint, as the window builds them."""
    times = next(EventGrid(spec).windows(start.step_index, 1))
    controls = control_values(spec, times[:-1])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    return np.asarray(float(times[1] - times[0])), control


def timed(function, arguments, repeat):
    """Compile alone, warm up once, then time `repeat` calls until ready (milliseconds)."""
    started = perf_counter()
    compiled = jax.jit(function).lower(*arguments).compile()
    compile_s = perf_counter() - started
    out = compiled(*arguments)
    jax.block_until_ready(out)
    ready = []
    for _ in range(repeat):
        started = perf_counter()
        out = compiled(*arguments)
        jax.block_until_ready(out)
        ready.append(perf_counter() - started)
    return {
        "median_ms": 1e3 * median(ready),
        "min_ms": 1e3 * min(ready),
        "compile_s": compile_s,
        "hlo_counts": pd.hlo_counts(compiled),
    }, out


def concentrations(state, p):
    ci, co = tissue.physical_amounts(state, p)
    return (
        np.where(p.active, ci / p.volume, 1.0),
        np.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )


def piece_timing(args):
    spec, start = checkpoint(args)
    model = get_model(spec.model)
    s, p = start.state, start.layout
    dt, c = step_inputs(spec, start)
    f = tissue.field_layout(p)
    surface = f.surface
    nodes = surface.cell_active.size + surface.outside_active.size
    groups = int(np.asarray(f.offset_free).size)
    stages = int(p.imex_explicit.shape[0])
    rng = np.random.default_rng(0)
    r, rows, calls = args.repeat, {}, []

    def run(name, function, arguments):
        """Time one world's piece; keep it for the batched pass (--batch)."""
        calls.append((name, function, arguments))
        rows[name], out = timed(function, arguments, r)
        return out

    moved, valid = run(
        "step", lambda s, dt, c, p: model.checked_step(s, dt, c, p, p.active), (s, dt, c, p)
    )
    values = run("field_solve", lambda s, c, p: model.field_values(s, c, p), (s, c, p))
    constants = model.device_check_constants(spec)
    steps = np.asarray(start.step_index + 1)
    run(
        "device_checks",
        lambda a, b, p, k, n: model.device_checks(a, b, p, k, n),
        (s, moved, p, constants, steps),
    )
    _, co = concentrations(s, p)

    def build(co, p):
        surface = tissue.field_layout(p).surface
        weight, _ = imex.face_weights(co, surface)
        return imex.face_laplacian(weight, surface)

    laplacian = run("operator_build", build, (co, p))
    coefficient = np.asarray(p.imex_implicit[-1, -1] * dt)
    operator, ok = run(
        "operator_factor",
        lambda a, lap, p: imex.factor_operator(a, lap, p.boundary_V, tissue.field_layout(p)),
        (coefficient, laplacian, p),
    )
    lower = np.asarray(operator.factor)
    run("cholesky_alone", jnp.linalg.cholesky, (lower @ lower.T,))
    charge = rng.standard_normal(nodes) * 1e-15

    def stage(q, op):
        potential, residual = imex.solve_operator(q, op)
        return potential, residual, op.matrix @ potential

    run("stage_solve", stage, (charge, operator))
    run(
        "capacitor_solve",
        lambda q, b, p: field._capacitor_solve(q, b, tissue.field_layout(p), xp=jnp),
        (charge, np.zeros(nodes), p),
    )
    if groups:
        faces = np.asarray(f.face_incidence).shape[1]
        junctions = np.asarray(f.junction_incidence).shape[1]
        conductance = rng.uniform(0.5, 1.5, faces)
        slope = rng.uniform(0.5, 1.5, junctions)
        matrix = run(
            "face_product",
            lambda g, p: (
                (tissue.field_layout(p).face_incidence * g)
                @ tissue.field_layout(p).face_incidence.T
            ),
            (conductance, p),
        )
        jacobian = run(
            "jacobian_product",
            lambda m, g, p: (
                m
                + (tissue.field_layout(p).junction_incidence * g)
                @ tissue.field_layout(p).junction_incidence.T
            ),
            (matrix, slope, p),
        )
        run(
            "offset_lu",
            lambda m, q, p: field._offset_solve(m, q, tissue.field_layout(p), xp=jnp),
            (jacobian, rng.standard_normal(groups), p),
        )
    iterations = int(np.asarray(values.iterations))
    # Per step: one field solve (readouts at the step's start), one operator build and
    # factorisation, a stage solve per stage after the first. Per field solve: a capacitor
    # solve for the base potentials and one for the potential rates, one face product, a
    # Jacobian product per Newton iteration and an offset LU solve for the initial offsets
    # and per iteration (offset solves are skipped without floating components).
    counts = {
        "field_solve": 1,
        "operator_build": 1,
        "operator_factor": 1,
        "stage_solve": stages - 1,
        "capacitor_solve": 2,
        "face_product": 1 if groups else 0,
        "jacobian_product": iterations if groups else 0,
        "offset_lu": 1 + iterations if groups else 0,
    }
    batched = {}
    if args.batch > 1:  # The same pieces vmapped over --batch copies of their inputs.
        for name, function, arguments in calls:
            copies = jax.tree.map(lambda v: jnp.stack([jnp.asarray(v)] * args.batch), arguments)
            batched[name], _ = timed(jax.vmap(function), copies, r)
    out = {
        "world": {
            "model": spec.model,
            "field_solver": spec.execution.field_solver,
            "nodes": nodes,
            "cells": int(surface.cell_active.size),
            "outside_nodes": int(surface.outside_active.size),
            "floating_groups": groups,
            "free_offsets": int(np.asarray(f.offset_free).sum()),
            "faces": int(surface.face_active.size),
            "junctions": int(surface.junction_active.size),
            "membranes": int(surface.membrane_active.size),
            "stages": stages,
            "time": float(start.time),
            "newton_iterations": iterations,
            "step_valid": bool(np.asarray(valid)),
            "factor_valid": bool(np.asarray(ok)),
        },
        "pieces": rows,
        "counts_per_step": counts,
        "summary": summarize(rows, counts),
    }
    if batched:
        out |= {"batch": args.batch, "pieces_batched": batched}
        out["summary_batched"] = summarize(batched, counts)
    return out


def summarize(rows, counts):
    """The step's time by piece (milliseconds per call of each compiled piece)."""
    ms = {k: v["median_ms"] for k, v in rows.items()}
    per_step = {k: counts[k] * ms.get(k, 0.0) for k in counts}
    step = ms["step"]
    rest = step - per_step["field_solve"] - per_step["operator_build"]
    rest -= per_step["operator_factor"] + per_step["stage_solve"]
    inside_solve = sum(per_step[k] for k in ("capacitor_solve", "face_product"))
    inside_solve += per_step["jacobian_product"] + per_step["offset_lu"]
    # The hypothesis's pieces: the operator's factorisation (assembly and Cholesky), the
    # stage triangular solves, the capacitor triangular solves and the offset products and
    # LU solves; "broad" adds the operator's build (face Laplacian by dense scatters).
    named = per_step["operator_factor"] + per_step["stage_solve"] + inside_solve
    return {
        "step_ms": step,
        "device_checks_ms": ms["device_checks"],
        "per_step_ms": per_step,
        "field_solve_rest_ms": per_step["field_solve"] - inside_solve,
        "rest_of_step_ms": rest,
        "hypothesis_ms": named,
        "hypothesis_share_of_step": named / step,
        "hypothesis_share_of_step_and_checks": named / (step + ms["device_checks"]),
        "broad_ms": named + per_step["operator_build"],
        "broad_share_of_step": (named + per_step["operator_build"]) / step,
        "cholesky_share_of_factor": ms["cholesky_alone"] / ms["operator_factor"],
        "falsified": named < 0.5 * step,
    }


def fill(pattern, order):
    """Nonzeros (with the diagonal) and multiply-adds of the Cholesky factor of a symmetric
    pattern in the given order: a diagonally dominant matrix with that pattern is factored
    densely and its nonzeros counted (values do not change the structure)."""
    a = pattern[np.ix_(order, order)].astype(float)
    np.fill_diagonal(a, 0.0)
    a += np.diag(a.sum(axis=1) + 1.0)
    lower = np.linalg.cholesky(a)
    below = (lower != 0).sum(axis=0) - 1
    return {"nonzeros": int((lower != 0).sum()), "multiply_adds": int((below * below).sum())}


def orders(pattern):
    import scipy.sparse as sparse
    from scipy.sparse.csgraph import reverse_cuthill_mckee
    from scipy.sparse.linalg import splu

    csr = sparse.csr_matrix(pattern.astype(float))
    size = pattern.shape[0]
    mmd = splu(
        sparse.csc_matrix(pattern.astype(float) + size * np.eye(size)),
        permc_spec="MMD_AT_PLUS_A",
        options={"SymmetricMode": True},
    ).perm_c
    return {
        "natural": np.arange(size),
        "reverse_cuthill_mckee": np.asarray(reverse_cuthill_mckee(csr, symmetric_mode=True)),
        "minimum_degree": np.argsort(mmd),
    }


def describe(matrix, symmetric=True):
    pattern = np.asarray(matrix) != 0
    rows, cols = pattern.shape
    out = {"shape": [rows, cols], "nonzeros": int(pattern.sum()), "density": float(pattern.mean())}
    if symmetric and rows == cols and rows:
        pattern = pattern | pattern.T | np.eye(rows, dtype=bool)
        out["dense_cholesky_multiply_adds"] = rows**3 // 3
        out["cholesky"] = {k: fill(pattern, o) for k, o in orders(pattern).items()}
    return out


def sparsity(args):
    specs, checkpoints = pd.load(args)
    worlds = {}
    for i, spec in enumerate(specs, start=1):
        start = checkpoints[i] if checkpoints else initialise(spec)
        p = jax.tree.map(np.asarray, start.layout)
        f = tissue.field_layout(p)
        surface = f.surface
        dt, _ = step_inputs(spec, start)
        _, co = concentrations(start.state, p)
        weight, _ = imex.face_weights(co, surface, xp=np)
        laplacian = np.asarray(imex.face_laplacian(weight, surface, xp=np))
        operator, _ = imex.factor_operator(
            p.imex_implicit[-1, -1] * dt, laplacian, p.boundary_V, f, xp=np
        )
        free = np.asarray(operator.free)
        reduced = np.where(free[:, None] & free[None, :], operator.matrix, 0.0)
        reduced = reduced + np.diag((~free).astype(float))
        face, junction = np.asarray(f.face_incidence), np.asarray(f.junction_incidence)
        offsets = {}
        if face.shape[0]:
            product = (np.abs(face) @ np.abs(face).T) != 0
            jacobian = product | ((np.abs(junction) @ np.abs(junction).T) != 0)
            offset_free = np.asarray(f.offset_free)
            jacobian &= offset_free[:, None] & offset_free[None, :]
            jacobian |= np.diag(~offset_free)
            offsets = {"face_product": describe(product), "offset_jacobian": describe(jacobian)}
        worlds[f"{i}: {Path(args.definitions[i - 1]).name}"] = {
            "nodes": int(surface.cell_active.size + surface.outside_active.size),
            "capacitor_matrix": describe(f.capacitor_matrix),
            "capacitor_solve_matrix": describe(f.capacitor_solve_matrix),
            "face_laplacian": describe(laplacian),
            "imex_operator_reduced": describe(reduced),
            "face_incidence": describe(face, symmetric=False),
            "junction_incidence": describe(junction, symmetric=False),
            "floating_basis": describe(f.floating_basis, symmetric=False),
            **offsets,
        }
    return {"worlds": worlds}


def free_operator(spec, start):
    """The IMEX operator C + aL on the free nodes at the checkpoint (host), as factored."""
    p = jax.tree.map(np.asarray, start.layout)
    f = tissue.field_layout(p)
    dt, _ = step_inputs(spec, start)
    _, co = concentrations(start.state, p)
    weight, _ = imex.face_weights(co, f.surface, xp=np)
    laplacian = np.asarray(imex.face_laplacian(weight, f.surface, xp=np))
    operator, _ = imex.factor_operator(
        p.imex_implicit[-1, -1] * dt, laplacian, p.boundary_V, f, xp=np
    )
    free = np.asarray(operator.free)
    return np.asarray(operator.matrix)[np.ix_(free, free)]


def drift(args):
    """Conditioning of the free IMEX operator, and how far it moves between checkpoints.

    For the first definition at --snapshot (the reference) and at each of --snapshots:
    the operator's condition number, plain and after symmetric diagonal (Jacobi) scaling
    (CG's iteration count grows with its square root), and against the reference the
    largest |lambda - 1| of M_ref^-1 M (how good the reference factor is as a
    preconditioner: refinement or CG with it contracts by about this factor per
    iteration) and the relative Frobenius change.
    """
    from scipy.linalg import eigh, eigvalsh

    specs, checkpoints = pd.load(args)
    spec = specs[0]
    reference = free_operator(spec, checkpoints[1] if checkpoints else initialise(spec))

    def condition(m):
        d = 1.0 / np.sqrt(np.diag(m))
        plain, scaled = eigvalsh(m), eigvalsh(m * d[:, None] * d[None, :])
        return {"plain": float(plain[-1] / plain[0]), "jacobi": float(scaled[-1] / scaled[0])}

    out = {
        "reference": {
            "time": float(checkpoints[1].time) if checkpoints else 0.0,
            "free_nodes": int(reference.shape[0]),
            "condition": condition(reference),
        }
    }
    later = {}
    for path in args.snapshots or ():
        start = pd.checkpoints_at(specs[:1], path)[1]
        m = free_operator(spec, start)
        later[Path(path).name] = {
            "time": float(start.time),
            "condition": condition(m),
            "largest_abs_eig_minus_1": float(
                np.max(np.abs(eigh(m, reference, eigvals_only=True) - 1))
            ),
            "relative_frobenius_change": float(
                np.linalg.norm(m - reference) / np.linalg.norm(reference)
            ),
        }
    return {"drift": out | {"later": later}}


def source_map(compiled):
    """HLO instruction name -> (source file, line, op_name, largest output element count)
    from the compiled module."""
    out = {}
    pattern = re.compile(r"^\s*(?:ROOT )?%?([\w.\-]+) = (.*?)metadata=\{(.*)\}")
    pairs = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s}]+)')
    shapes = re.compile(r"[a-z]\w*\[([\d,]*)\]")
    for line in compiled.as_text().splitlines():
        m = pattern.search(line)
        if not m:
            continue
        meta = {k: v.strip('"') for k, v in pairs.findall(m.group(3))}
        head = m.group(2).split(" ", 1)[0] if not m.group(2).startswith("(") else m.group(2)
        head = head[: head.find(")") + 1] if head.startswith("(") else head
        sizes = [int(np.prod([int(d) for d in s.split(",") if d])) for s in shapes.findall(head)]
        out[m.group(1)] = (
            *(meta.get(k, "") for k in ("source_file", "source_line", "op_name")),
            max(sizes, default=0),
        )
    return out


# The operation class of an executed instruction, from its JAX op_name in the compiled
# module's metadata (this jaxlib records no source lines there): first the jitted library
# wrapper it sits in (jnp.linalg.cholesky, jax.scipy.linalg.cho_solve, jnp.linalg.solve), so
# a factorisation's own copies and symmetrisation count with it, then the primitive (the
# path's last component), which names the library call or the fusion's root on every
# backend. The dense node-space linear algebra is dense_cholesky, triangular_solve, lu and
# dense_product (the offset products and the dense matrix-vector products).
WRAPPERS = (
    ("jit(cholesky)", "dense_cholesky"),
    ("jit(_cho_solve)", "triangular_solve"),
    ("jit(solve)", "lu"),
)
PRIMITIVES = (
    ("cholesky", "dense_cholesky"),
    ("triangular_solve", "triangular_solve"),
    ("lu", "lu"),
    ("dot_general", "dense_product"),
    ("scatter", "scatter"),
    ("gather", "gather"),
    ("while", "loop"),
    ("cond", "loop"),
    ("transpose", "copy"),
    ("copy", "copy"),
)


def operation_class(op_name, instruction):
    for wrapper, name in WRAPPERS:
        if wrapper in op_name:
            return name
    primitive = re.sub(r"\[.*$", "", op_name.rsplit("/", 1)[-1]) if op_name else ""
    for key, name in PRIMITIVES:
        if primitive.startswith(key) or instruction.startswith(key):
            return name
    return "elementwise_and_other"


def exclusive_times(events):
    """Each complete event's own time: its duration less that of the events nested in it on
    the same thread (a while loop's event encloses its body's instructions), so nothing is
    counted twice. {id(event): microseconds}."""
    by_thread = defaultdict(list)
    for e in events:
        by_thread[(e.get("pid"), e.get("tid"))].append(e)
    own = {}
    for evs in by_thread.values():
        evs.sort(key=lambda e: (e["ts"], -e.get("dur", 0.0)))
        stack = []
        for e in evs:
            end = e["ts"] + e.get("dur", 0.0)
            while stack and stack[-1][1] <= e["ts"]:
                stack.pop()
            own[id(e)] = e.get("dur", 0.0)
            if stack and end <= stack[-1][1]:
                own[id(stack[-1][0])] -= e.get("dur", 0.0)
            stack.append((e, end))
    return own


def trace_profile(args):
    """Per-instruction own time of --repeat traced calls of the vmapped step (and, unless
    --without-checks, the device checks)."""
    spec, start = checkpoint(args)
    model = get_model(spec.model)
    dt, c = step_inputs(spec, start)
    copies = args.worlds

    def stack(tree):
        return jax.tree.map(lambda v: jnp.stack([jnp.asarray(v)] * copies), tree)

    s, p, cc = stack(start.state), stack(start.layout), stack(c)
    dts = jnp.full((copies,), dt)
    constants = stack(model.device_check_constants(spec))
    steps = jnp.full((copies,), start.step_index + 1)

    def step_and_checks(s, dt, c, p, k, n):
        moved, valid = jax.vmap(lambda s, dt, c, p: model.checked_step(s, dt, c, p, p.active))(
            s, dt, c, p
        )
        if args.without_checks:
            return moved, valid
        checks = jax.vmap(lambda a, b, p, k, n: model.device_checks(a, b, p, k, n))(
            s, moved, p, k, n
        )
        return moved, valid, checks

    arguments = (s, dts, cc, p, constants, steps)
    started = perf_counter()
    compiled = jax.jit(step_and_checks).lower(*arguments).compile()
    compile_s = perf_counter() - started
    sources = source_map(compiled)
    for _ in range(2):
        jax.block_until_ready(compiled(*arguments))
    log_dir = Path(args.out).with_suffix(".trace")
    ready = []
    with jax.profiler.trace(str(log_dir), create_perfetto_trace=True):
        for _ in range(args.repeat):
            started = perf_counter()
            jax.block_until_ready(compiled(*arguments))
            ready.append(perf_counter() - started)
    traces = sorted(log_dir.rglob("*perfetto_trace.json.gz"))
    events = json.loads(gzip.open(traces[-1]).read()) if traces else {"traceEvents": []}
    names = {}
    for e in events.get("traceEvents", []):
        if e.get("ph") == "M" and e.get("name") in ("process_name", "thread_name"):
            names[(e["name"], e.get("pid"), e.get("tid"))] = e.get("args", {}).get("name", "")
    complete = [e for e in events.get("traceEvents", []) if e.get("ph") == "X"]
    own = exclusive_times(complete)
    by_instruction, by_track, by_name = defaultdict(float), defaultdict(float), defaultdict(float)
    for e in complete:
        track = names.get(("process_name", e.get("pid"), None), str(e.get("pid")))
        by_track[track] += own[id(e)]
        by_name[f"{track} | {e.get('name', '')}"] += own[id(e)]
        hlo = e.get("args", {}).get("hlo_op") or e.get("name", "")
        if hlo in sources:
            by_instruction[(track, hlo)] += own[id(e)]
    # Node-space size: an instruction whose largest output holds at least n x n elements per
    # world works on a dense node-space matrix (assembly, scaling, copies, validity checks).
    surface = tissue.field_layout(start.layout).surface
    square = (surface.cell_active.size + surface.outside_active.size) ** 2 * copies
    classes, dense_size, top = defaultdict(float), defaultdict(float), []
    for (track, hlo), us in sorted(by_instruction.items(), key=lambda kv: -kv[1]):
        _, _, op, elements = sources[hlo]
        kind = operation_class(op, hlo)
        classes[(track, kind)] += us
        if elements >= square:
            dense_size[(track, kind)] += us
        if len(top) < 60:
            top.append(
                {
                    "track": track,
                    "instruction": hlo,
                    "us": us,
                    "op_name": op[-160:],
                    "class": kind,
                    "output_elements": elements,
                }
            )
    events_top = sorted(by_name.items(), key=lambda kv: -kv[1])[:60]
    return {
        "worlds": copies,
        "device_checks": not args.without_checks,
        "time": "own (exclusive) microseconds: nested events are subtracted",
        "compile_s": compile_s,
        "hlo_counts": pd.hlo_counts(compiled),
        "ready_ms": [1e3 * x for x in ready],
        "trace": str(traces[-1]) if traces else None,
        "us_per_track": dict(by_track),
        "us_per_class": {f"{t} | {k}": v for (t, k), v in classes.items()},
        "us_per_class_node_square": {f"{t} | {k}": v for (t, k), v in dense_size.items()},
        "top_instructions": top,
        "top_events": [{"event": k, "us": v} for k, v in events_top],
        "attributed_us": sum(by_instruction.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("part", choices=("pieces", "sparsity", "drift", "trace"))
    parser.add_argument("--snapshots", nargs="+", help="further snapshots (drift)")
    parser.add_argument("--definitions", nargs="+", required=True)
    parser.add_argument("--snapshot", default="start", help="a batch snapshot directory, or start")
    parser.add_argument("--backend", help="override each definition's backend (cpu or gpu)")
    parser.add_argument("--field-solver", help="override each definition's field solver")
    parser.add_argument("--repeat", type=int, default=10, help="timed or traced calls")
    parser.add_argument("--worlds", type=int, default=6, help="copies of the state (trace)")
    parser.add_argument("--without-checks", action="store_true", help="trace the step alone")
    parser.add_argument("--batch", type=int, default=1, help="also time the pieces vmapped")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    started = perf_counter()
    parts = dict(pieces=piece_timing, sparsity=sparsity, drift=drift, trace=trace_profile)
    part = parts[args.part]
    result = {
        "kind": "cells.step_profile@1",
        "part": args.part,
        "provenance": pd.provenance(),
        "arguments": vars(args),
        **part(args),
    }
    result["seconds"] = perf_counter() - started
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1, default=str) + "\n")
    print(json.dumps({k: result.get(k) for k in ("summary", "seconds")}, indent=1, default=str))


if __name__ == "__main__":
    main()
