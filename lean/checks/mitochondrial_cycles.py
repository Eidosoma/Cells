"""Compare seven mitochondrial cycle columns with their joint material and charge balance."""

import json

import jax
import numpy as np

from cells.execution.runner import run
from cells.kinds import transporter
from tests.unit import test_mito_cycle_laws as fx

CYCLES = ("c1", "c3", "c4", "f1", "ant", "pic", "khe")
P_CHARGE = np.array([4, 2, 8, -3, -1, 0, 0])


def net_rows(extents, species):
    """Independent N (matrix) and P (intermembrane) changes for arbitrary signed extents."""
    i, iii, iv, synthase, nucleotide, phosphate, potassium = extents
    matrix = dict(
        NADH=-i,
        NAD=i,
        Q=iii - i,
        QH2=i - iii,
        O2=-iv,
        H=-5 * i - 2 * iii - 8 * iv + 2 * synthase + 2 * phosphate - potassium,
        ADP=nucleotide - synthase,
        ATP=synthase - nucleotide,
        Pi=phosphate - synthase,
        K=potassium,
    )
    outer = dict(
        cytc_red=2 * iii - 4 * iv,
        cytc_ox=4 * iv - 2 * iii,
        H=4 * i + 4 * iii + 4 * iv - 3 * synthase - 2 * phosphate + potassium,
        ATP=nucleotide,
        ADP=-nucleotide,
        Pi=-phosphate,
        K=-potassium,
    )
    return np.array([[values.get(s, 0) for s in species] for values in (matrix, outer)])


def checked_world():
    raw = fx.host_p_world()
    dt = raw["execution"]["dt"]
    raw["experiment"].update(end_time=2 * dt, observation_times=[0, dt, 2 * dt])
    spec, _, _, p, _ = fx.start(raw)
    species = list(spec.model.species_ids)
    populations = [row["id"] for row in raw["model"][transporter.MODEL_KEY]]
    slots = [populations.index(name) for name in CYCLES]
    lumen = [o.id for o in spec.model.extracellular].index("lumen_0")
    z = np.asarray(spec.model.valence)
    columns = np.zeros((len(CYCLES), 2, len(species)))
    for i, slot in enumerate(slots):
        for row in np.flatnonzero(p.cycle_row_present[:, slot]):
            side = 0 if p.cycle_row_at_n[row, slot] else 1
            columns[i, side, p.cycle_row_species[row, slot]] += p.cycle_nu[0, row, slot]
        np.testing.assert_array_equal(
            columns[i], net_rows(np.eye(len(CYCLES), dtype=int)[i], species)
        )
    charge = columns @ z
    np.testing.assert_array_equal(charge[:, 1], P_CHARGE)
    np.testing.assert_array_equal(charge[:, 0], -P_CHARGE)

    respiration = np.array([2, 2, 1, 0, 0, 0, 0]) @ charge
    delivery = np.array([0, 0, 0, 1, 1, 1, 0]) @ charge
    np.testing.assert_array_equal(respiration, [-20, 20])
    np.testing.assert_array_equal(delivery, [4, -4])
    np.testing.assert_array_equal(respiration + 5 * delivery, [0, 0])

    result = run(spec)
    assert result.final.step_index == 2
    isolated = [
        species.index(s)
        for s in ("NADH", "NAD", "Q", "QH2", "cytc_red", "cytc_ox", "O2", "ADP", "ATP", "Pi")
    ]
    max_ledger = max_material = 0.0
    for i in range(1, len(result.times)):
        h = result.history
        state = type(h)(*(v[i] for v in h))
        extent = state.cycle_count[0, slots]
        assert np.all(extent != 0)
        reference = net_rows(extent, species)
        ledger = transporter.ledger_terms(state, p, xp=np)
        booked = np.stack((ledger["cell"][:, 0], ledger["outside"][:, lumen]))
        max_ledger = max(max_ledger, float(np.max(np.abs(booked - reference))))
        np.testing.assert_allclose(booked, reference, rtol=3e-13, atol=0)
        physical = np.stack(
            (state.amount_increment[:, 0], state.extracellular_amount_increment[:, lumen])
        )
        max_material = max(
            max_material, float(np.max(np.abs(physical[:, isolated] - reference[:, isolated])))
        )
        np.testing.assert_allclose(
            physical[:, isolated], reference[:, isolated], rtol=3e-13, atol=0
        )
    return dict(
        checked_steps=result.final.step_index,
        populations=CYCLES,
        signed_extents_fmol=extent.tolist(),
        outward_charge_equivalents_per_turn=charge[:, 1].tolist(),
        outer_free_protons_per_turn=columns[:, 1, species.index("H")].tolist(),
        outward_charge_per_oxygen=int(respiration[1]),
        outward_charge_per_ATP_delivery=int(delivery[1]),
        max_material_ledger_discrepancy_fmol=max_ledger,
        max_isolated_species_discrepancy_fmol=max_material,
        global_charge_error_C=float(result.diagnostics["max_global_charge_error_C"]),
    )


if __name__ == "__main__":
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    with fx.mito_scoped():
        print(json.dumps(checked_world(), indent=2, allow_nan=False))
