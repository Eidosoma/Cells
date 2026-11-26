"""Compare exact vertices and held-face minima with cells.binding.rapid_binding@1 and Lean."""

import argparse
import json
from fractions import Fraction
from itertools import combinations, product

import jax
import numpy as np

from binding_feasibility import MARGINS, registry_counts
from cells.laws.reactions import rapid_binding as kernel
from tests.unit import test_rapid_binding_kernel as fixture


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def corners(dimension):
    return {tuple(Fraction(i == j) for j in range(dimension)) for i in range(dimension)}


def reference_vertices(forms, dimension):
    """Normalized directions from exact line crossings or, in three dimensions, plane intersections."""
    axes = corners(dimension)
    if dimension == 1:
        return axes
    differences = {tuple(x - y for x, y in zip(a, b, strict=True))
                   for binder in forms for a, b in combinations(binder, 2)}
    if dimension == 2:
        candidates = {Fraction(dy, dy - dx) for dx, dy in differences if dx != dy}
        return axes | {(t, 1 - t) for t in candidates if 0 <= t <= 1}
    if dimension != 3:
        raise ValueError(f"expected one to three held ligands, received {dimension}")
    vertices = set()
    for (x, y, z), (a, b, c) in combinations(differences | axes, 2):
        normal = (y * c - z * b, z * a - x * c, x * b - y * a)
        scale = sum(normal)
        if scale:
            direction = tuple(Fraction(value, scale) for value in normal)
            if min(direction) >= 0:
                vertices.add(direction)
    return vertices


def exact_margin(direction, forms, totals, binders):
    return dot(direction, totals) - sum(
        amount * min(dot(direction, row) for row in binder)
        for binder, amount in zip(forms, binders, strict=True))


def common_floors(forms):
    result = [tuple(map(min, zip(*binder, strict=True))) for binder in forms]
    if all(row in binder for row, binder in zip(result, forms, strict=True)):
        return result
    return None


def project(forms, held):
    return [[tuple(int(row[j]) for j in held) for row in binder] for binder in forms]


def engine_faces(net, forms):
    """Also check restriction of the production vertex list to the active simplex face."""
    exact, floats = kernel.margin_vertices(net["counts"], net["present"])
    dimension = len(exact[0])
    assert len(set(exact)) == len(exact)
    np.testing.assert_array_equal(floats, net["margin_vertices"])
    np.testing.assert_array_equal(floats, np.array(exact, dtype=float))
    for bits in product((False, True), repeat=dimension):
        held = tuple(j for j, bit in enumerate(bits) if bit)
        if not held:
            continue
        vertices = {tuple(v[j] for j in held) for v in exact
                    if all(value == 0 for j, value in enumerate(v) if not bits[j])}
        projected = project(forms, held)
        assert vertices == reference_vertices(projected, len(held)), (held, vertices)
        yield held, projected, vertices


def registered(name):
    ligands, binders, _, net = fixture.system(name)
    forms = registry_counts(ligands, binders)
    all_rows = list(range(len(ligands)))
    present = [net["counts"][b, mask] for b, mask in enumerate(net["present"])]
    assert project(present, all_rows) == project(forms, all_rows)
    tl, tb = fixture.totals(name, ligands, binders)
    frozen = fixture.VALUES["validity"]["systems"][name]
    stored = fixture.INPUTS["manufactured_states"][name]
    budgets = fixture.margin_bound(tl, tb, net)
    masks = {}
    for held, projected, vertices in engine_faces(net, forms):
        dimension = len(held)
        floors = common_floors(projected)
        bits = np.isin(all_rows, held)
        weights = np.broadcast_to(bits[:, None], tl.shape)
        expected = []
        for batch, (totals, amounts) in enumerate(zip(tl.T, tb.T, strict=True)):
            lig = [Fraction(totals[j]) for j in held]
            binder = list(map(Fraction, amounts))
            best = min(exact_margin(v, projected, lig, binder) for v in vertices)
            if floors is not None:
                floor_by_ligand = zip(*floors, strict=True)
                assert best == min(t - dot(binder, counts)
                                   for t, counts in zip(lig, floor_by_ligand, strict=True))
            if dimension == len(ligands):
                # The frozen rational reference uses binary64 amounts before volume division.
                raw = stored[batch]["totals"]
                reference = Fraction(frozen[batch]["t_star_exact"])
                inventory = [Fraction(raw["ligands_fmol"][l]) for l in ligands]
                stock = [Fraction(raw["binders_fmol"][b]) for b in binders]
                assert min(exact_margin(v, projected, inventory, stock) for v in vertices) == reference
                winner = tuple(map(Fraction, frozen[batch]["lambda_star"]))
                assert winner in vertices and exact_margin(winner, projected, inventory, stock) == reference
            expected.append(float(best))
        args = tl, tb, net["counts"], net["present"], net["margin_vertices"], weights
        errors = {}
        for backend, run in MARGINS.items():
            actual = np.asarray(run(*args))
            delta = np.abs(actual - expected)
            assert np.all(delta <= budgets), (name, held, backend, delta)
            assert np.all(actual > 0) and min(expected) > 0
            errors[backend] = float(delta.max())
        key = ",".join(ligands[j] for j in held)
        masks[key] = {"vertices": [[str(v) for v in row] for row in sorted(vertices)],
                      "common_lowest_forms": floors, "max_absolute_error_mM": errors}
    return {"states": tl.shape[1], "held_faces": masks}


def controls():
    # The duplicate base, parallel profile and absent row exercise the production presence mask.
    pair = np.array([[(0, 0), (2, -1), (0, 0), (9, 9), (-7, 2)]])
    triple = np.array([[(0, 0, 0), (-1, 0, 0), (0, -1, 0), (0, 0, -1)]])
    return [
        ("two_ligand_crossing", pair, np.array([[True, True, True, True, False]]),
         (Fraction(5, 8), Fraction(-3, 8)), (Fraction(1, 3), Fraction(2, 3))),
        ("three_ligand_interior", triple, np.ones((1, 4), dtype=bool),
         (Fraction(-3, 8),) * 3, (Fraction(1, 3),) * 3),
    ]


def challenge(counts, present, totals, winner):
    dimension = len(totals)
    forms = project([b[mask] for b, mask in zip(counts, present, strict=True)], range(dimension))
    assert common_floors(forms) is None
    exact, floats = kernel.margin_vertices(counts, present)
    assert set(exact) == reference_vertices(forms, dimension)
    values = {v: exact_margin(v, forms, totals, [1]) for v in exact}
    assert values[winner] == Fraction(-1, 24)
    without_winner = min(value for v, value in values.items() if v != winner)
    assert without_winner > 0
    assert min(values[v] for v in corners(dimension)) == Fraction(5, 8)
    tl = np.array(totals, dtype=float)[:, None]
    backend_values = {}
    for backend, run in MARGINS.items():
        m = float(np.asarray(run(tl, np.ones((1, 1)), counts, present, floats,
                                 np.ones_like(tl, dtype=bool)))[0])
        assert m < 0 and abs(m - float(values[winner])) <= 8 * np.finfo(float).eps
        backend_values[backend] = m
    return {"minimizer": list(map(str, winner)), "exact_minimum_mM": str(values[winner]),
            "corner_minimum_mM": "5/8", "minimum_with_winner_omitted_mM": str(without_winner),
            "backends_mM": backend_values}


def lean_fixture(label, forms, dimension, vertices):
    """Emit kernel-reduced equalities using the original counts and the engine's rational output."""
    print(f"namespace {label}")
    if dimension == 1:
        (only,), = vertices
        print(f"example : stdSimplex ℝ (Fin 1) = {{fun _ => (({only} : ℚ) : ℝ)}} := by",
              "  simp [stdSimplex_unique]", sep="\n")
    else:
        binders = ["#[" + ", ".join("![" + ", ".join(map(str, row)) + "]" for row in binder) + "]"
                   for binder in forms]
        print(f"private def rows : Array (Array (Fin {dimension} → ℤ)) := #[" + ", ".join(binders) + "]")
        print(f"private def forms (b : Fin rows.size) : Array (Fin {dimension} → ℤ) := rows[b.val]")
        print(f"private def counts (b : Fin rows.size) (i : Fin (forms b).size) : Fin {dimension} → ℤ := (forms b)[i.val]")
        if dimension == 2:
            points = ", ".join(str(v[0]) for v in sorted(vertices))
            print(f"example : twoVertices counts = {{{points}}} := by decide +kernel")
        # This determines whether the proved corner shortcut applies, directly on the form counts.
        floors = common_floors(forms)
        if floors is None:
            print("example : ¬ (∀ b, ∃ i, ∀ k j, counts b i j ≤ counts b k j) := by decide +kernel")
        else:
            rows = ", ".join("![" + ", ".join(map(str, floor)) + "]" for floor in floors)
            print(f"private def floorCounts : Fin rows.size → Fin {dimension} → ℤ := ![{rows}]")
            print("example : ∀ b, ∃ i, ∀ k j, counts b i j = floorCounts b j ∧",
                  "    counts b i j ≤ counts b k j := by decide +kernel", sep="\n")
    print(f"end {label}\n")


def emit_lean():
    print("import CellsProofs.Chemistry.BindingVertices\nopen CellsProofs.Chemistry.BindingVertices\n")
    for name in fixture.INPUTS["systems"]:
        ligands, binders, _, net = fixture.system(name)
        forms = registry_counts(ligands, binders)
        for held, projected, vertices in engine_faces(net, forms):
            lean_fixture(name + "_" + "_".join(ligands[j] for j in held), projected, len(held), vertices)
    for name, counts, present, totals, _ in controls():
        exact, _ = kernel.margin_vertices(counts, present)
        forms = project([b[mask] for b, mask in zip(counts, present, strict=True)], range(len(totals)))
        lean_fixture(name, forms, len(totals), exact)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-lean", action="store_true", help="print exact engine-to-Lean fixture checks")
    if parser.parse_args().emit_lean:
        emit_lean()
    else:
        jax.config.update("jax_enable_x64", True)
        with jax.default_device(jax.devices("cpu")[0]):
            systems = {name: registered(name) for name in fixture.INPUTS["systems"]}
            probes = {name: challenge(*args) for name, *args in controls()}
        print(json.dumps({"registered": systems, "omitted_vertex_controls": probes}, indent=2, allow_nan=False))
