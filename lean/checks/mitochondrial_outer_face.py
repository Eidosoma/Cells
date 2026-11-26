"""Exercise the MT-1b capacitor topology and ask the public parser about each outer-face row."""

import json
import math

import jax
import numpy as np
from mitochondrial_cycles import seven_cycle_world

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.numerics.surface_field import CHARGE_ATOL_C
from cells.registry import species_registry
from tests.unit import test_mito_cycle_laws as fixture
from validation.compartment_ph_engine import definitions as fr

OUTER_ROWS = ("K", "H", "Mg", "ADP", "ATP", "AMP", "Pi")


def world(moving, matched=False):
    raw = seven_cycle_world()
    model, experiment = raw["model"], raw["experiment"]
    # Keep the matrix–IMS capacitor. Its only connection to the held bath is a conductive face.
    model["membranes"] = [patch for patch in model["membranes"] if patch["id"] == fr.BOUNDING]
    experiment["membrane_controls"] = [
        c for c in experiment["membrane_controls"] if c["membrane_id"] == fr.BOUNDING
    ]
    model["faces"] = [
        dict(
            id="ims_to_bath",
            sender=fr.LUMEN,
            receiver=fr.BATH,
            area_m2=1e-12,
            length_m=1e-6,
            law="cells.route.logmean_electrodiffusion@1",
            diffusivity_m2_per_s={
                s["id"]: 1e-12 if s["id"] in moving else 0.0 for s in model["species"]
            },
        )
    ]
    if matched:
        outside = {node["id"]: node for node in model["extracellular"]}
        bath, ims = outside[fr.BATH], outside[fr.LUMEN]
        new_k = ims["initial_amount_fmol"]["K"] / ims["volume_pL"] * bath["volume_pL"]
        bath["fixed_charge_equivalent_fmol"] -= new_k - bath["initial_amount_fmol"]["K"]
        bath["initial_amount_fmol"]["K"] = new_k
    dt = raw["execution"]["dt"]
    raw["execution"].update(face_capacity=1, membrane_capacity=1)
    experiment.update(end_time=2 * dt, observation_times=[0, dt, 2 * dt])
    return raw


def potassium_control(matched):
    raw = world(["K"], matched)
    spec, impl, _, layout, control = fixture.start(raw)
    tr = run(spec)
    z = np.asarray(spec.model.valence)
    outside = [v.id for v in spec.model.extracellular]
    ims, bath = outside.index(fr.LUMEN), outside.index(fr.BATH)
    offset = len(spec.model.cells)
    k = list(spec.model.species_ids).index("K")
    basis = layout.field_floating_basis
    assert basis.shape == (3, 1)
    assert basis[0, 0] == basis[offset + ims, 0] != 0 and basis[offset + bath, 0] == 0
    concentration = layout.extracellular_amount_reference[k] / layout.extracellular_volume
    thermal = R * layout.temperature / F
    nernst = thermal * math.log(concentration[bath] / concentration[ims])
    rows = []
    budget = CHARGE_ATOL_C / CHARGE_PER_FMOL
    for i, t in enumerate(tr.times):
        h = tr.history
        state = type(h)(*(v[i] for v in h))
        field = impl.readouts(state, control, layout, xp=np).field
        voltage = field.potential_V[offset + ims] - field.potential_V[offset + bath]
        if i == 0:
            assert abs(voltage - nernst) <= 128 * np.finfo(float).eps * max(thermal, abs(nernst))
        matrix_q = math.fsum(z * state.amount_increment[:, 0])
        ims_q = math.fsum(z * state.extracellular_amount_increment[:, ims])
        net = math.fsum([matrix_q, ims_q])
        outward = math.fsum(z * state.face_transferred[:, 0])
        assert max(abs(net), abs(outward), abs(net + outward)) <= budget
        if i:
            # Dropping the IMS from the same inventory would exceed this bound.
            assert abs(matrix_q) > budget and np.count_nonzero(state.cycle_count[0]) == 7
        rows.append(
            dict(
                t_s=float(t),
                ims_minus_bath_mV=1000 * float(voltage),
                matrix_delta_fmol_eq=matrix_q,
                ims_delta_fmol_eq=ims_q,
                combined_delta_fmol_eq=net,
                outer_transfer_fmol_eq=outward,
            )
        )
    assert tr.final.step_index == 2
    return dict(
        initial_potassium_mM={"ims": float(concentration[ims]), "bath": float(concentration[bath])},
        nernst_mV=1000 * nernst,
        fixed_charge_tolerance_fmol_eq=budget,
        states=rows,
    )


def form_charges():
    spec = parse_spec(world(["K"]))
    z = dict(zip(spec.model.species_ids, spec.model.valence, strict=True))
    rows = {}
    for row in ("ADP", "ATP", "Pi"):
        forms = species_registry.forms_of(spec, row)
        charges = species_registry.form_valences(spec, row)
        # Signed, unequal integral extents give an exact row/ligand accounting control.
        flux = [(-1) ** f * (f + 1) for f in range(len(forms))]
        weighted_forms = sum(q * j for q, j in zip(charges, flux, strict=True))
        ligands = {}
        for (_, counts, _), j in zip(forms, flux, strict=True):
            for ion, count in counts:
                ligands[ion] = ligands.get(ion, 0) + count * j
        weighted_rows = z[row] * sum(flux) + sum(z[ion] * j for ion, j in ligands.items())
        assert weighted_forms == weighted_rows and weighted_rows != z[row] * sum(flux)
        rows[row] = dict(
            forms=[f for f, _, _ in forms],
            signed_extents=flux,
            ligand_receipts=ligands,
            charge=weighted_rows,
        )
    return rows


def admission(moving):
    try:
        parse_spec(world(moving))
    except ConfigError as exc:
        reason = str(exc)
        if "ims_to_bath" not in reason or not any(f"species {s} " in reason for s in moving):
            raise
        return dict(admitted=False, reason=reason)
    return dict(admitted=True)


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    report = dict(
        matched_K=potassium_control(True),
        gradient_K=potassium_control(False),
        form_charges=form_charges(),
        individual_rows={s: admission([s]) for s in OUTER_ROWS},
        all_outer_rows=admission(OUTER_ROWS),
        full_start_state="pending the per-form face and the declared anchor/start world",
    )
    print(json.dumps(report, indent=2, allow_nan=False))
