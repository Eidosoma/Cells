"""Check cells.binding.rapid_binding@1 feasibility against independent binder inventories."""

import json
from fractions import Fraction
from functools import partial
from itertools import product

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import linprog

from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.reactions import rapid_binding as kernel
from tests.unit import test_rapid_binding_kernel as fixture
from tests.unit.test_rapid_binding_world import reference_cell


MARGINS = {
    "numpy": partial(kernel.joint_margin, xp=np),
    "jax_jit_cpu": jax.jit(partial(kernel.joint_margin, xp=jnp)),
}
SOLVERS = {
    "numpy": partial(kernel.free_ligands, xp=np),
    "jax_jit_cpu": jax.jit(partial(kernel.free_ligands, xp=jnp)),
}


def registry_counts(ligands, binders):
    return [np.array([[form.get("counts", {}).get(ligand, 0) for ligand in ligands]
                      for form in fixture.REGISTRY["binders"][b]["forms"]]) for b in binders]


def primal_margin(forms, held, target, binders):
    """Maximize a common free remainder t over nonnegative form amounts, in mM."""
    # One column per present form, followed by the unrestricted common remainder.
    rows = np.concatenate(forms)[:, held].T
    owner = np.repeat(np.arange(len(forms)), [len(b) for b in forms])
    inventory = (owner == np.arange(len(forms))[:, None]).astype(float)
    answer = linprog(
        np.r_[np.zeros(len(owner)), -1.0],
        A_ub=np.column_stack((rows, np.ones(len(rows)))), b_ub=target[held],
        A_eq=np.column_stack((inventory, np.zeros(len(forms)))), b_eq=binders,
        bounds=[(0, None)] * len(owner) + [(None, None)], method="highs",
    )
    assert answer.success, answer.message
    return float(answer.x[-1])


def compare_margins(net, tl, tb, held, references):
    args = tl, tb, net["counts"], net["present"], net["margin_vertices"], held
    bounds = fixture.margin_bound(tl, tb, net)
    errors = {}
    for name, run in MARGINS.items():
        margin = np.asarray(run(*args))
        if references is None:
            assert np.all(np.isposinf(margin)), name
            continue
        discrepancy = np.abs(margin - references)
        assert np.all(discrepancy <= bounds), (name, margin, references, bounds)
        resolved = np.abs(references) > bounds
        np.testing.assert_array_equal(margin[resolved] > 0, references[resolved] > 0)
        errors[name] = float(np.max(discrepancy))
    return errors


def registered(name):
    ligands, binders, volume, net = fixture.system(name)
    tl, tb = fixture.totals(name, ligands, binders)
    forms = registry_counts(ligands, binders)
    frozen = np.array([float(Fraction(row["t_star_exact"]) / Fraction(volume))
                       for row in fixture.VALUES["validity"]["systems"][name]])
    result = {}
    for bits in product((False, True), repeat=len(ligands)):
        pick = np.array(bits)
        held = np.broadcast_to(pick[:, None], tl.shape)
        ref = None
        if any(bits):
            ref = np.array([primal_margin(forms, pick, t, b) for t, b in zip(tl.T, tb.T, strict=True)])
            if all(bits):
                assert np.all(np.abs(ref - frozen) <= fixture.margin_bound(tl, tb, net))
                assert np.all(frozen > 0)
        result["".join(str(int(bit)) for bit in bits)] = compare_margins(net, tl, tb, held, ref)
    return {"states": tl.shape[1], "max_absolute_error_mM_by_held_mask": result}


def solver_verdicts(net, tl, tb, held, comp_l, comp_b, *, compare_residual_only=False):
    args = tl, tb, net["log_beta"], net["counts"], net["present"], held, comp_l, comp_b
    results = {}
    with np.errstate(all="ignore"):
        for name, solve in SOLVERS.items():
            u, ok = solve(*args, vertices=net["margin_vertices"])
            results[name] = {"valid": bool(ok[0])}
            if compare_residual_only:
                _, residual_ok = solve(*args)
                results[name]["residual_only_valid"] = bool(residual_ok[0])
                value = float(np.asarray(u)[0, 0])
                results[name]["log_free_H"] = value if np.isfinite(value) else None
    return results


def planted(name, state):
    ligands, volume, net, tl, tb, held, cl, cb = fixture.planted_system(state)
    forms = registry_counts(ligands, fixture.INPUTS["systems"][state["system"]]["binders"])
    primal = primal_margin(forms, held[:, 0], tl[:, 0], tb[:, 0])
    frozen = fixture.VALUES["validity"]["planted"][name]
    exact = Fraction(frozen["t_star_exact"]) / Fraction(volume)
    assert abs(primal - float(exact)) <= fixture.margin_bound(tl, tb, net)[0]
    errors = compare_margins(net, tl, tb, held, np.array([primal]))
    verdicts = solver_verdicts(net, tl, tb, held, cl, cb)
    assert all(result["valid"] == (exact > 0) for result in verdicts.values())
    return {"exact_margin_mM": str(exact), "primal_margin_mM": primal, "verdicts": verdicts,
            "absolute_error_mM": errors}


def release_network(size):
    """Independent copies of the registered base/H-release pair, with unique form identifiers."""
    source = fixture.binder_spec("rel1", ("H",))
    binders = []
    for index in range(size):
        binder_id = f"rel_{index}"
        forms = tuple((f"{binder_id}_{form_id}", counts, beta) for form_id, counts, beta in source[1])
        binders.append((binder_id, forms, *source[2:]))
    return kernel.network(("H",), tuple(binders))


def release_boundary():
    """At least one positive free solution exists exactly when total H + sum(T_B) is positive."""
    cases = [
        ("feasible_control", -1.0, (0.5, 0.6, 0.6)),
        ("infeasible_control", -2.0, (0.5, 0.6, 0.6)),
        ("exact_boundary", -1.7, (0.5, 0.6, 0.6)),
        ("representable_interior", -0.8999999999999999, (0.3, 0.3, 0.3)),
        ("below_floor", -3.8000000000000003, (0.3, 0.3, 1.0, 1.1, 1.1)),
    ]
    result, failures = {}, []
    for case, total, amounts in cases:
        net = release_network(len(amounts))
        held, cl, cb = fixture.masks(net, 1)
        tl = np.array([[total]])
        tb = np.array(amounts)[:, None]
        exact = Fraction.from_float(total) + sum(map(Fraction.from_float, amounts))
        verdicts = solver_verdicts(net, tl, tb, held, cl, cb, compare_residual_only=True)
        args = tl, tb, net["counts"], net["present"], net["margin_vertices"], held
        for name, run in MARGINS.items():
            margin = float(np.asarray(run(*args))[0])
            verdict = verdicts[name]
            verdict["margin_mM"] = margin
            if (margin > 0) != (exact > 0) or verdict["valid"] != (exact > 0):
                failures.append({"case": case, "backend": name, "expected_valid": exact > 0,
                                 "margin_positive": margin > 0, "valid": verdict["valid"]})
        result[case] = {"total_H_mM": total, "binder_totals_mM": amounts,
                        "exact_margin_of_stored_inputs_mM": str(exact), "backends": verdicts}
    return result, failures


def host_domain():
    """Exercise the current tissue parser on positive, zero and negative initial H inventories."""
    raw, _ = reference_cell("S7", 1)
    parse_spec(raw)
    verdicts = {"registered_positive_control": "admitted"}
    node = raw["model"]["cells"][0]
    for target in (0.0, -1.7):
        # Keep the fixed charge balanced while changing the H inventory.
        amount = target * node["volume_pL"]
        node["fixed_charge_equivalent_fmol"] -= amount - node["initial_amount_fmol"]["H"]
        node["initial_amount_fmol"]["H"] = amount
        try:
            parse_spec(raw)
        except ConfigError as exc:
            verdicts[str(target)] = str(exc)
        else:
            verdicts[str(target)] = "admitted"
    return verdicts


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        systems = {name: registered(name) for name in fixture.INPUTS["systems"]}
        plants = {name: planted(name, state) for name, state in fixture.INPUTS["validity"]["planted"].items()}
        edges, failures = release_boundary()
    print(json.dumps({"registered": systems, "planted": plants, "release_boundary": edges,
                      "tissue_initial_H_mM": host_domain(), "classification_failures": failures}, indent=2, allow_nan=False))
    raise SystemExit(int(bool(failures)))
