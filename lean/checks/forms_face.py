"""Compare forms-face fluxes and both stored inventories in a compiled Cells tissue."""

import json

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.laws.routes import logmean_electrodiffusion_forms as forms_law
from cells.models import surface_pump_v3 as tissue
from cells.numerics import surface_transport as surface
from cells.registry.models import get_model
from tests.unit.test_rapid_binding_world import forms_world


EPS = np.finfo(float).eps


def counterflow(count):
    # Exchange two forms at fixed total binder (4 mM). The free activity is
    # consistent with form/base = (free / 12 mM)^count. Only the binder diffuses.
    base = np.array([1.0, 3.0, 1.0])
    form = np.array([3.0, 1.0, 3.0])
    free = 12.0 * (form / base) ** (1.0 / count)
    concentration = np.stack([free, base, form])
    left, right = concentration[:, :-1], concentration[:, 1:]
    faces = surface.FormsFaces(
        active=np.array([True, True]),
        sender=np.array([0, 1]),
        receiver=np.array([1, 2]),
        factor=np.array([[0.0, 0.0], [2e-15, 1e-15], [2e-15, 1e-15]]),
        valence=np.array([[1.0], [-2.0], [-2.0 + count]]),
        stoichiometry=np.array([[0.0, 1.0], [1.0, 0.0], [1.0, count]]),
    )
    rates = surface.forms_face_transport(left, right, np.zeros(2), 298.15, faces, xp=np)
    assert bool(rates.valid)
    flux = rates.flux_fmol_s
    rows, inflow = surface.forms_row_rates(flux, faces, 3, xp=np)
    # At zero voltage each unequal pair here uses the quotient branch of the log mean.
    expected_bound = np.array([4., -2.])  # (D A/L) Δc, in fmol/s.
    expected_ligand = count * expected_bound
    np.testing.assert_allclose(flux, [np.zeros(2), -expected_bound, expected_bound],
                               rtol=16 * EPS, atol=0)
    np.testing.assert_allclose(rows, [np.zeros(2), expected_ligand], rtol=16 * EPS, atol=0)
    np.testing.assert_allclose(inflow, [np.zeros(3), count * np.array([-4., 6., -2.])],
                               rtol=16 * EPS, atol=0)
    np.testing.assert_allclose(rates.current_A, CHARGE_PER_FMOL * expected_ligand,
                               rtol=16 * EPS, atol=0)
    assert np.all(rates.dissipation_pJ_s > 0)

    immobile = faces._replace(factor=np.zeros_like(faces.factor))
    stopped = surface.forms_face_transport(left, right, np.zeros(2), 298.15, immobile, xp=np)
    assert bool(stopped.valid)
    np.testing.assert_array_equal(stopped.flux_fmol_s, np.zeros_like(flux))

    # Dropping the form's ligand still gives two globally conserved rows.
    # The independently predicted receiver gain detects the missing carriage.
    omitted = faces.stoichiometry.copy()
    omitted[2, 1] = 0
    _, wrong = surface.forms_row_rates(flux, faces._replace(stoichiometry=omitted), 3, xp=np)
    np.testing.assert_array_equal(wrong.sum(axis=1), [0., 0.])
    missing = abs(inflow[1, 1] - wrong[1, 1])
    np.testing.assert_allclose(missing, 6 * abs(count), rtol=16 * EPS, atol=0)
    return dict(
        ligand_count=count,
        form_flux_fmol_s=flux.tolist(),
        row_flux_fmol_s=rows.tolist(),
        node_inflow_fmol_s=inflow.tolist(),
        omitted_middle_node_error_fmol_s=float(missing),
    )


def compiled_tissue():
    raw = forms_world(protons=0.5)
    times = [step * raw["execution"]["dt"] for step in range(5)]
    raw["experiment"].update(end_time=times[-1], observation_times=times)
    spec = parse_spec(raw)
    result = run(spec)
    np.testing.assert_array_equal(result.times, times)
    history = result.history
    impl = get_model(spec.model)
    _, layout = impl.initial_values(spec)
    network = (layout.binding_rows, layout.binding_counts, layout.binding_present, 1)
    names = forms_law.movers(spec.model, network, tissue.forms_of_binders(spec.model)).names
    moved = np.asarray(history.forms_face_transferred)[:, :, 0]
    free = moved[:, names.index("H")]
    bare = moved[:, names.index("B_L:B_L")]
    bound = moved[:, names.index("B_L:HB_L")]
    # The fixture declares one H in HB_L. Reconstruct both row transfers by
    # name, independently of the engine's stored stoichiometry and ledger fold.
    expected = np.stack([bare + bound, free + bound], axis=1)
    row_ids = list(spec.model.species_ids)
    rows = [row_ids.index("B_L"), row_ids.index("H")]
    nodes = [node["id"] for node in raw["model"]["extracellular"]]
    face = raw["model"]["faces"][0]
    sender, receiver = (nodes.index(face[end]) for end in ("sender", "receiver"))
    increments = np.asarray(history.extracellular_amount_increment)[:, rows, :]
    sent, received = -increments[:, :, sender], increments[:, :, receiver]
    np.testing.assert_allclose(sent, expected, rtol=64 * EPS, atol=0)
    np.testing.assert_allclose(received, expected, rtol=64 * EPS, atol=0)
    np.testing.assert_array_equal(moved[:, names.index("B_L")], np.zeros(len(times)))
    heat = np.asarray(history.forms_face_dissipated_energy_pJ)[:, 0]
    assert np.all(np.diff(heat) > 0) and bound[-1] > 1000 * abs(free[-1]) > 0
    return dict(
        model=raw["model"]["id"],
        law=face["law"],
        solver=raw["execution"]["solver"],
        times_s=times,
        bare_binder_fmol=float(bare[-1]),
        occupied_binder_fmol=float(bound[-1]),
        free_ligand_fmol=float(free[-1]),
        total_ligand_fmol=float(expected[-1, 1]),
        total_binder_fmol=float(expected[-1, 0]),
        heat_pJ=float(heat[-1]),
        max_sender_error_fmol=float(np.max(np.abs(sent - expected))),
        max_receiver_error_fmol=float(np.max(np.abs(received - expected))),
    )


if __name__ == "__main__":
    print(json.dumps(dict(counterflow=[counterflow(2), counterflow(-1)],
                          tissue=compiled_tissue()), indent=2, allow_nan=False))
