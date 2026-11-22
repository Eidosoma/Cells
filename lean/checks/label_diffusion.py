"""FR-33 D1. Compare explicit label rows and a parent on the same Cells face."""

import json
import math

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.numerics import surface_transport
from cells.registry.models import get_model
from validation.regions import example, readouts
from validation.tissue import surface_fixtures


def neutral_trajectory():
    spec = parse_spec(example.two_node_diffusion())
    times, states = readouts.runs(spec)
    _, layout = get_model(spec.model).initial_values(spec)
    series = {}
    for species in ("S", "L", "U"):
        mapping = readouts.world_map(spec, species)
        pair = [mapping["nodes"].index(node) for node in ("left", "right")]
        series[species] = np.array(
            [readouts.node_records(spec, layout, state, mapping)[0][pair] for state in states]
        )
    np.testing.assert_allclose(times, np.linspace(0, 1, 101), rtol=0, atol=1e-13)
    label, complement, parent = (series[key] for key in ("L", "U", "S"))
    for observed, target in ((parent, 1), (label + complement, parent), (label.sum(axis=1), 1)):
        np.testing.assert_allclose(observed, target, rtol=0, atol=1e-12)
    expected_right = 0.5 - 0.4 * np.exp(-2 * example.R_DIFFUSION * np.array(times))
    np.testing.assert_allclose(label[:, 1], expected_right, rtol=0, atol=1e-5)
    return {
        "rows": len(times),
        "final_time_s": times[-1],
        "right_fmol": {s: [float(v[0, 1]), float(v[-1, 1])] for s, v in series.items()},
        "max_family_minus_parent_fmol": float(np.abs(label + complement - parent).max()),
        "max_right_label_closed_form_error_fmol": float(np.abs(label[:, 1] - expected_right).max()),
    }


def face_flux(compiled, valence, voltage, left, right):
    raw = surface_fixtures.definition("equilibrium")
    raw["layout"]["valence"][0][0] = valence
    raw["co"][0] = [left, right, right]
    raw["outside_potential_V"] = [voltage, 0.0, 0.0]
    for key in ("membrane_open", "junction_open"):
        raw[key] = [0.0] * len(raw[key])
    ci, co, _, outside, membrane, junction, layout = surface_fixtures.arrays(raw)
    rates = compiled(ci, co, np.zeros(ci.shape[1]), outside, membrane, junction, layout)
    assert bool(rates.valid) and rates.face_flux_fmol_s.dtype == np.float64
    return float(rates.face_flux_fmol_s[0, 0])


def face_cases():
    compiled = jax.jit(surface_transport.transport)
    scale = surface_fixtures.definition("equilibrium")["layout"]["face_factor"][0][0] / 1e-15
    opposite = ((0.9, 0.1), (0.1, 0.9))
    rows = {}
    for name, valence, voltage, gradients in (
        ("neutral_opposing", 0, 0.010, opposite),
        ("neutral_net", 0, 0.010, ((0.9, 0.2), (0.4, 0.6))),
        ("neutral_near_equality", 0, 0.010, ((1.0001, 1.0), (0.99995, 1.0))),
        ("charged_zero_voltage", 1, 0.0, opposite),
        ("charged_10mV", 1, 0.010, opposite),
    ):
        total = tuple(map(sum, zip(*gradients, strict=True)))
        fluxes = [face_flux(compiled, valence, voltage, *pair) for pair in (*gradients, total)]
        summed, parent = sum(fluxes[:2]), fluxes[2]
        if valence == 0 or voltage == 0:
            # Cancellation near equality is set by the original concentrations.
            atol = 64 * np.finfo(float).eps * scale * max(total)
            for pair, flux in zip((*gradients, total), fluxes, strict=True):
                np.testing.assert_allclose(flux, scale * (pair[0] - pair[1]), rtol=0, atol=atol)
            np.testing.assert_allclose(summed, parent, rtol=0, atol=3 * atol)
        else:
            assert 0 < summed < parent and fluxes[1] < 0 < fluxes[0]
            np.testing.assert_allclose(summed / parent, (8 / 5) / math.log(9), rtol=5e-15)
        rows[name] = {
            "label_pairs_mM": gradients,
            "row_fluxes_fmol_s": fluxes[:2],
            "row_sum_fmol_s": summed,
            "parent_flux_fmol_s": parent,
            "ratio": summed / parent if parent else None,
        }
    return rows


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(json.dumps({"trajectory": neutral_trajectory(), "faces": face_cases()}, indent=2))
