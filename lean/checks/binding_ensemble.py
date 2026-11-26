"""Check form fractions from cells.binding.rapid_binding@1 against a fixed-activity partition."""

import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import proton_buffer
from cells.laws.reactions import rapid_binding
from cells.registry import species_registry
from tests.unit import test_rapid_binding_kernel as fixture
from tests.unit.test_proton_buffer_kind import host
from tests.unit.test_rapid_binding_world import amounts, reference_cell


compiled = jax.jit(lambda u, tb, beta, n, mask: rapid_binding.speciation(u, tb, beta, n, mask, xp=jnp))


def form_fractions(u, totals, net):
    args = u, totals, net["log_beta"], net["counts"], net["present"]
    for name, evaluate in (("numpy", lambda *xs: rapid_binding.speciation(*xs, xp=np)),
                           ("jax_jit_cpu", compiled)):
        _, forms = evaluate(*args)
        yield name, np.asarray(forms) / totals[:, None]


def partition(binder, free_mM):
    """Multiply activities with signed powers, using the original chemical potentials at c0."""
    with localcontext() as context:
        context.prec = 80
        reg = fixture.REGISTRY
        c0 = Decimal(reg["standard_concentration_mM"])
        forms = reg["binders"][binder]["forms"]
        base = Decimal(forms[0]["mu0_RT"])
        weights = []
        for form in forms:
            weight = (base - Decimal(form["mu0_RT"])).exp()
            for ligand, n in form.get("counts", {}).items():
                standard = Decimal(reg["species"][ligand]["mu0_RT"]).exp()
                weight *= (standard * Decimal(free_mM[ligand]) / c0) ** n
            weights.append(weight)
        total = sum(weights)
        return [float(weight / total) for weight in weights]


def compare_system(name):
    ligands, binders, _, net = fixture.system(name)
    states = fixture.VALUES["systems"][name]["states"]
    free = np.array([[row["x_mM"][ligand] for row in states] for ligand in ligands])
    _, totals = fixture.totals(name, ligands, binders)
    ref = np.zeros((*net["present"].shape, len(states)))
    for b, binder in enumerate(binders):
        for k, row in enumerate(states):
            fractions = partition(binder, row["x_mM"])
            ref[b, :len(fractions), k] = fractions
    mask = np.broadcast_to(net["present"][:, :, None], ref.shape)
    assert np.array_equal(ref > 0, mask)
    metrics = {}
    for backend, fractions in form_fractions(np.log(free), totals, net):
        np.testing.assert_allclose(fractions[mask], ref[mask], atol=0, rtol=2e-13)
        np.testing.assert_array_equal(fractions[~mask], 0.0)
        np.testing.assert_allclose(fractions.sum(axis=1), 1.0, atol=2e-14, rtol=0)
        metrics[backend] = {
            "max_abs_error": float(np.max(np.abs(fractions - ref))),
            "max_abs_log_ratio": float(np.max(np.abs(np.log(fractions[mask] / ref[mask])))),
        }
    return {"states": len(states), "form_fractions": int(mask.sum()),
            "padded_entries": int((~mask).sum()), "errors": metrics}


def grouped_isomers():
    raw, _ = reference_cell("S1", 0)
    binder = next(s for s in raw["model"]["species"] if s["id"] == "buf1")
    ligand = next(s for s in raw["model"]["species"] if s["id"] == "H")
    center_mM = 1e-4
    ratios = np.array([0.25, 1.0, 4.0])
    results = {}
    for label, weights in (("single", [1]), ("two_equal", [1, 1]),
                           ("two_unequal", [1, 3]), ("counted_twice", [1, 1, 1, 1])):
        binder["forms"][0]["standard_mu_RT"] = (
            binder["standard_mu_RT"] + ligand["standard_mu_RT"]
            + math.log(center_mM / raw["model"]["standard_concentration_mM"]) - math.log(sum(weights))
        )
        spec = parse_spec(raw)
        (base, bound), c0 = species_registry.form_log_constants(spec, "buf1")
        forms = (("base", (), base), ("bound", (("H", 1),), bound))
        net = rapid_binding.network(("H",), (("buf1", forms, c0, (("H", 1.0),)),))
        bound = sum(weights) * ratios
        ref = bound / (1 + bound)
        for _, p in form_fractions(np.log(center_mM * ratios[None]), np.ones((1, len(ratios))), net):
            np.testing.assert_allclose(p[0, 1], ref, rtol=2e-14)
        results[label] = float(ref[1])
    binder["forms"].append(dict(binder["forms"][0], id="buf1_other_isomer"))
    try:
        parse_spec(raw)
    except ConfigError as exc:
        if "Isomers are one form" not in str(exc):
            raise
    else:
        raise AssertionError("The registry admitted duplicate form counts")
    return {"center_mM": center_mM, "relative_concentrations": ratios.tolist(),
            "fractions_at_center": results, "duplicate_counts_refused": True}


def tissue_read():
    raw, _ = reference_cell("S3", 0)
    spec = parse_spec(raw)
    _, state, p, _ = host(spec)
    read, ok = proton_buffer.stage_read(state, p, xp=np)
    assert ok
    free = amounts(read, p)[p.binding_rows, 0] / p.volume[0]
    expected = fixture.VALUES["systems"]["S3"]["states"][0]
    ligands, binders, _, _ = fixture.system("S3")
    forms = rapid_binding.forms_from_free(np.log(free[:len(ligands)]), free[len(ligands):],
                                         p.binding_log_beta, p.binding_counts, p.binding_present, xp=np)
    ids = [f["id"] for f in fixture.REGISTRY["binders"][binders[0]]["forms"]]
    reference = np.array([expected["forms_mM"][binders[0]][f] for f in ids])
    floors = expected["floor_residual_1e-13"]
    ratios = np.abs(np.log(forms[0] / reference))
    form_tol = np.array([2 * floors["forms"][f"{binders[0]}|{f}"] for f in ids])
    for i, ligand in enumerate(ligands):
        assert abs(math.log(free[i] / expected["x_mM"][ligand])) <= 2 * floors["x"][ligand]
    assert np.all(ratios <= form_tol)
    return {"model": raw["model"]["id"], "state": "S3/0", "forms": ids,
            "max_abs_log_ratio": float(ratios.max()),
            "max_fraction_of_registered_tolerance": float((ratios / form_tol).max())}


def magnesium_atp():
    data = json.loads((Path(__file__).parent / "data" / "mgatp_binding.json").read_text())
    ward = data["ward1998"]
    kd = data["zhang1997"]["apparent_kd_uM_by_pH"][str(ward["pH"])]["mean"] / 1000
    x = ward["free_mg_uM"] / 1000
    c0 = fixture.C0
    forms = (("apo", (), 0.0), ("MgATP", (("Mg", 1),), math.log(c0 / kd)))
    net = rapid_binding.network(("Mg",), (("ATP", forms, c0, (("Mg", 1.0),)),))
    observed = ward["bound_to_unbound"] / (1 + ward["bound_to_unbound"])
    predictions = {}
    for backend, p in form_fractions(np.array([[math.log(x)]]), np.array([[ward["ATP_mM"]]]), net):
        predictions[backend] = float(p[0, 1, 0])
        np.testing.assert_allclose(p[0, 1, 0], x / (x + kd), rtol=2e-14)
    return {"free_mg_mM": x, "input_apparent_kd_mM": kd, "observed_graph_fraction": observed,
            "predictions": predictions, "predicted_minus_observed": predictions["numpy"] - observed}


def compare():
    systems = {name: compare_system(name) for name in fixture.INPUTS["systems"]}
    return {"systems": systems, "states": sum(s["states"] for s in systems.values()),
            "form_fractions_per_backend": sum(s["form_fractions"] for s in systems.values()),
            "padded_entries_per_backend": sum(s["padded_entries"] for s in systems.values()),
            "grouped_isomers": grouped_isomers(), "tissue": tissue_read(),
            "mgatp_cross_preparation": magnesium_atp()}


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(json.dumps(compare(), indent=2, allow_nan=False))
