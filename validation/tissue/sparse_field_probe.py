"""FR-17 stage 1's probe (docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8.4): the sparse field solver
against version 2 on a world's own field, operation by operation, bit for bit. No step runs.

For each world, built by its generator and parsed under cells.solver.capacitive_reduction_gauged_damped_newton@2,
the field layout is bound twice from the same topology: version 2's (the world's own) and
cells.solver.sparse_capacitive_reduction_gauged_damped_newton@1's (surface_field.bind). Then, on the host (NumPy)
and on the CPU device (jitted, the layout a traced input as in a step):
- capacitor_solve: surface_field._capacitor_solve at the world's initial charges and boundary, and
  at charges C v of random potentials v with random clamp voltages (a nonzero boundary, so the
  subtraction of C @ boundary is exercised);
- operator: surface_imex.factor_operator at the step's coefficient (the tableau's implicit diagonal
  times dt) and the face weights of the world's initial outside concentrations, and solve_operator
  at both charge sets: the potentials, the charge residuals, the validity, and the reduced
  operator's diagonal factor where the reduction is diagonal;
- products: C x and (C + a L) x at random x, the readouts' and residuals' products.
Each comparison reports whether the bytes are identical, whether the values are equal (signed zeros
aside), and the largest difference relative to the largest reference magnitude. Two calibrations
sit beside them: version 2's own host against its device (dense_host_vs_device), and each solve's
charge residual against the engine's acceptance bound (CHARGE_ATOL_C + CHARGE_RTOL x the row's
charge scale; a stage solve is refused above 1), for both IDs on the device.

jaxprs (§8.5 item 1, D147's guard 1 in counts): the checked step, the right-hand side and the
device row checks of each world, traced as composite_crossrev traces them
(validation/tissue/field_floor_guard._traced) under version 2 and under the sparse ID, and every
equation counted by primitive, nested jaxprs included. A count by primitive, not a structural
identity: the report lists the primitives whose counts differ, so it shows whether anything but
the node-space algebra changed.

Usage (PYTHONPATH at the source under test, JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
  python -m validation.tissue.sparse_field_probe OUT.json [WORLD ...]
  python -m validation.tissue.sparse_field_probe jaxprs OUT.json [WORLD ...]
Worlds: gj_field, gj_line, sheet254, W1_P4, G2_W7, S825 (default: all).
"""

import json
import sys
import time

import numpy as np

WORLDS = ("gj_field", "gj_line", "sheet254", "W1_P4", "G2_W7", "S825")


def world(name):
    """A world's definition, by its own generator (the GJ worlds at the line's pinned stage-1
    state, as crossrev's replication set builds them; no step is run)."""
    if name in ("gj_field", "gj_line"):
        from validation.gap_junction_tissue import neither

        shape = name.split("_")[1]
        return neither.coupled_world(1e-13, neither.STAGE1_END_UNITS, shape=shape, end=1.0)
    if name == "sheet254":
        from validation.tissue import cell_replacement_fixtures as rfx

        return rfx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=0.01)
    if name == "S825":
        from validation.tissue import surface_pump_v3_study as study

        return study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    from validation.tissue import composite_crossrev as crossrev

    key = {"W1_P4": "W1_P4@0.001", "G2_W7": "G2_W7_literature@0.001"}[name]
    return crossrev.qualification_worlds()[key]


def compare(reference, candidate):
    a, b = np.asarray(reference), np.asarray(candidate)
    if a.shape != b.shape:
        return dict(identical=False, equal=False, shapes=[list(a.shape), list(b.shape)])
    scale = float(np.max(np.abs(a), initial=0.0))
    difference = float(np.max(np.abs(a - b), initial=0.0)) if a.dtype != bool else float(
        np.any(a != b)
    )
    return dict(
        identical=a.tobytes() == b.tobytes(),
        equal=bool(np.array_equal(a, b)),
        differing=int(np.count_nonzero(a != b)),
        signed_zeros_differing=int(np.count_nonzero((a == 0) & (np.signbit(a) != np.signbit(b)))),
        size=int(a.size),
        max_abs=difference,
        max_rel=difference / scale if scale > 0 else (0.0 if difference == 0 else float("inf")),
    )


def probe(name):
    import jax
    import jax.numpy as jnp

    from cells.definitions.specs import parse_spec
    from cells.models import surface_tissue as tissue
    from cells.numerics import surface_field as field
    from cells.numerics import surface_imex as imex
    from cells.registry.models import get_model

    raw = world(name)
    spec = parse_spec(raw)
    _, p = get_model(spec.model).initial_values(spec)
    dense = tissue.field_layout(p)
    started = time.perf_counter()
    sparse_layout = field.bind(dense.surface, np.asarray(dense.gauge_mask),
                               solver=field.SPARSE_SOLVER_ID)  # fmt: skip
    bind_s = time.perf_counter() - started
    s = dense.surface
    n, o = np.asarray(s.cell_active).size, np.asarray(s.outside_active).size
    rng = np.random.default_rng(20261123)
    clamps = np.asarray(s.reservoir) | np.asarray(dense.gauge_mask)
    initial = np.r_[np.asarray(p.initial_cell_charge_C), np.asarray(p.initial_outside_charge_C)]
    potentials = rng.uniform(-0.1, 0.1, n + o)
    random_charge = np.asarray(dense.capacitor_matrix) @ potentials
    boundary_V = np.where(clamps, rng.uniform(-0.05, 0.05, o), 0.0)
    cases = {
        "initial": (initial, np.r_[np.zeros(n), np.asarray(p.boundary_V)],
                    np.asarray(p.boundary_V)),  # fmt: skip
        "random": (random_charge, np.r_[np.zeros(n), boundary_V], boundary_V),
    }
    solver = spec.execution.solver
    coefficient = float(imex.TABLEAUX[solver].implicit[-1, -1] * spec.execution.dt)
    co = np.where(
        np.asarray(p.outside_active),
        (np.asarray(p.extracellular_amount_reference)) / np.asarray(p.extracellular_volume),
        1.0,
    )
    weight, _ = imex.face_weights(np.where(co > 0, co, 1.0), s, xp=np)
    x = rng.uniform(-1.0, 1.0, n + o)

    def run(layout, xp, charge, boundary, held_V):
        laplacian = imex.operator_laplacian(xp.asarray(weight), layout.surface, layout, xp=xp)
        operator, valid = imex.factor_operator(coefficient, laplacian, xp.asarray(held_V), layout,
                                               xp=xp)  # fmt: skip
        phi, residual = imex.solve_operator(xp.asarray(charge), operator, xp=xp)
        return dict(
            capacitor_solve=field._capacitor_solve(xp.asarray(charge), xp.asarray(boundary), layout,
                                                   xp=xp),  # fmt: skip
            operator_potential=phi,
            operator_residual=residual,
            operator_valid=valid,
            operator_scale=operator.scale,
            capacitor_product=field.capacitor_product(layout, xp.asarray(x), xp=xp),
            operator_product=imex.operator_product(operator, xp.asarray(x), xp=xp),
        )

    out = dict(
        nodes=n + o,
        bind_s=round(bind_s, 3),
        operator_levels=int(np.asarray(sparse_layout.operator_solve_node).shape[0]),
        capacitor_levels=int(np.asarray(sparse_layout.capacitor_solve_node).shape[0]),
        operator_factor_entries=int(np.asarray(sparse_layout.operator_factor_column).size),
        coefficient=coefficient,
        cases={},
    )
    jitted = {}
    for label, (charge, boundary, held_V) in cases.items():
        results = {}
        for side, layout in (("dense", dense), ("sparse", sparse_layout)):
            results[(side, "host")] = run(layout, np, charge, boundary, held_V)
            if side not in jitted:
                jitted[side] = jax.jit(lambda q, c, b, h: run(q, jnp, c, b, h))
            device = jitted[side](jax.tree.map(jnp.asarray, layout), charge, boundary, held_V)
            results[(side, "device")] = jax.tree.map(np.asarray, device)
        entry = {}
        for where in ("host", "device"):
            entry[where] = {
                k: compare(results[("dense", where)][k], results[("sparse", where)][k])
                for k in results[("dense", where)]
            }
        for side in ("sparse", "dense"):
            entry[side + "_host_vs_device"] = {
                k: compare(results[(side, "host")][k], results[(side, "device")][k])
                for k in results[(side, "host")]
            }
        bounds = {}
        for side, layout in (("dense", dense), ("sparse", sparse_layout)):
            r = results[(side, "device")]
            image = np.asarray(field.capacitor_product(layout, r["capacitor_solve"], xp=np))
            solved = ~np.asarray(dense.fixed) & np.asarray(dense.active)
            scale = np.maximum(np.abs(charge), np.abs(image))
            bound = field.CHARGE_ATOL_C + field.CHARGE_RTOL * scale
            capacitor = np.where(solved, np.abs(image - charge) / bound, 0.0)
            stage = np.abs(r["operator_residual"]) / (
                field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.maximum(
                    np.abs(charge), np.abs(r["operator_residual"] + charge))
            )  # fmt: skip
            bounds[side] = dict(capacitor_solve=float(capacitor.max(initial=0.0)),
                                operator_solve=float(stage.max(initial=0.0)))  # fmt: skip
        entry["residual_over_bound"] = bounds
        entry["nonzero_rhs"] = int(np.count_nonzero(charge))
        entry["max_abs_potential"] = float(
            np.max(np.abs(results[("dense", "device")]["capacitor_solve"]), initial=0.0)
        )
        out["cases"][label] = entry
    return out


def jaxprs(names, out_path):
    """Primitive counts of the traced programs under both IDs (module docstring)."""
    import copy

    from cells.numerics import surface_field as field
    from validation.tissue import field_floor_guard as floor

    report = {}
    for name in names:
        raw = world(name)
        counts = {}
        for label, solver in (("dense", field.FACTORED_SOLVER_ID),
                              ("sparse", field.SPARSE_SOLVER_ID)):  # fmt: skip
            declared = copy.deepcopy(raw)
            declared["execution"]["field_solver"] = solver
            traced, _, _ = floor._traced(declared)
            counts[label] = {k: dict(floor.primitive_counts(j)) for k, j in traced.items()}
        entry = {}
        for function in counts["dense"]:
            a, b = counts["dense"][function], counts["sparse"][function]
            changed = {k: [a.get(k, 0), b.get(k, 0)] for k in sorted(set(a) | set(b))
                       if a.get(k, 0) != b.get(k, 0)}  # fmt: skip
            entry[function] = dict(dense_equations=sum(a.values()),
                                   sparse_equations=sum(b.values()), changed=changed)  # fmt: skip
        report[name] = entry
        print(name, json.dumps({f: e["changed"] for f, e in entry.items()}), flush=True)
        with open(out_path, "w") as handle:
            json.dump(report, handle, indent=1)


def main(argv):
    import jax

    jax.config.update("jax_enable_x64", True)
    if argv[0] == "jaxprs":
        return jaxprs(argv[2:] or list(WORLDS), argv[1])
    out_path, names = argv[0], argv[1:] or list(WORLDS)
    report = {}
    for name in names:
        started = time.perf_counter()
        report[name] = probe(name)
        report[name]["seconds"] = round(time.perf_counter() - started, 1)
        summary = {
            label: {where: {k: (v["identical"], v["max_rel"]) for k, v in entry[where].items()}
                    for where in ("host", "device")}
            for label, entry in report[name]["cases"].items()
        }  # fmt: skip
        print(name, json.dumps(summary), flush=True)
        with open(out_path, "w") as handle:
            json.dump(report, handle, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
