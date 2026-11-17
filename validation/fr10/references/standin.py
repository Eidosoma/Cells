"""Stand-in bundles for dry runs of the harness: an honest engine and planted ones.

``build_standin(out_dir, variant)`` writes every role's bundles in the canonical layout and a
``roles.json``. The honest stand-in steps W1 and W2 with ARS(2,2,2)'s implicit half on the
registered ladder, books the records in float64 and K in the operator's B form. Every row passes
on it. Each planted variant must fail its row:
- ``late``: events take effect one step late (``faces``, ``ion``);
- ``first_order``: implicit Euler (the order rows);
- ``null``: the bath's step never reaches transport (``faces``, ``ion``);
- ``dG_sign``: dG_b booked with the wrong sign (``records``);
- ``K_without_B``: K re-priced at the current potential with no accumulator (``K``, W1);
- ``counterion``: a substitution whose decreasing species is not applied (``records``, W2).

W3's supply is synthetic (the inputs give W3's bath only): zero before the event, then rising
linearly, on a 0.1 ms grid to 6 ms.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import controls, faces, ion, records, schemes
from .bundles import write_bundle
from .common import Constants, constants_from_block, exact, load_inputs

VARIANTS = ("honest", "late", "first_order", "null", "dG_sign", "K_without_B", "counterion")


def _records_arrays(world: dict, const: Constants, species: list, variant: str) -> dict:
    RT = float(const.RT(world["temperature_K"]))
    F = float(const.faraday)
    z = records.valences(world)
    t_ev, dose, dG, q = [], [], [], []
    for _name, bath in world["baths"].items():
        V_b = float(bath["volume_pL"])
        epochs = records.bath_epochs(bath)
        for (_, before), (t_e, after) in zip(epochs, epochs[1:], strict=False):
            after = dict(after)
            if variant == "counterion":
                drops = [s for s in before if after[s] < before[s]]
                for s in drops:
                    after[s] = before[s]
            d = {s: V_b * float(after[s]) - V_b * float(before[s]) for s in species}
            g = records.delta_G_float(before, after, V_b, RT)
            t_ev.append(float(t_e))
            dose.append([d[s] for s in species])
            dG.append(-g if variant == "dG_sign" else g)
            q.append(F * 1e-15 * sum(z[s] * d[s] for s in species))
    return {"event_time_s": np.array(t_ev), "dose_fmol": np.array(dose),
            "dG_b_pJ": np.array(dG), "charge_C": np.array(q)}


def _K_B_form(world: dict, const: Constants, times, supply: np.ndarray, species: list,
              variant: str) -> np.ndarray:
    RT = float(const.RT(world["temperature_K"]))
    bath = next(iter(world["baths"].values()))
    epochs = records.bath_epochs(bath)
    c0 = epochs[0][1]
    dmu = [[RT * float(np.log(float(comp[s] / c0[s]))) for s in species] for _, comp in epochs]
    rows = records.event_rows(times, epochs)
    K = np.empty(len(times))
    B, e = 0.0, 0
    for k in range(len(times)):
        while e + 1 < len(epochs) and rows[e] == k:
            if variant != "K_without_B":
                B += 1e-3 * sum((dmu[e][j] - dmu[e + 1][j]) * supply[k, j]
                                for j in range(len(species)))
            e += 1
        K[k] = B + 1e-3 * sum(dmu[e][j] * supply[k, j] for j in range(len(species)))
    return K


def _epochs_for(variant: str, epochs, dt):
    if variant == "late":
        return controls.shifted_epochs(epochs, "late", dt)
    if variant == "null":
        return controls.shifted_epochs(epochs, "null")
    return epochs


def build_standin(out_dir, variant: str = "honest") -> Path:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs()
    const = constants_from_block(inputs["constants"])
    scheme = "implicit_euler" if variant == "first_order" else "ars_implicit"
    rw = inputs["R_records"]["worlds"]
    species = sorted(rw["W1"]["valence"])
    roles = {"faces": [], "ion": []}

    fw = faces.parse(inputs["R_faces"])
    for dt in inputs["R_faces"]["dt_ladder_s"]:
        amt = schemes.run_faces(fw, dt, scheme, epochs=_epochs_for(variant, fw.epochs, dt))
        n0 = np.array([float(v * c) for v, c in zip(fw.volume, fw.c0, strict=True)])
        supply = np.zeros((fw.times.size, len(species)))
        supply[:, species.index(fw.species)] = np.sum(amt - n0, axis=1)
        arrays = {"time_s": fw.times, "node_amount_fmol": amt, "supply_fmol": supply}
        arrays.update(_records_arrays(rw["W1"], const, species, variant))
        arrays["K_pJ"] = _K_B_form(rw["W1"], const, fw.times, supply, species, variant)
        name = f"W1_dt{dt:g}"
        write_bundle(out / name, {"world": "W1", "solver": scheme, "dt_s": dt,
                                  "nodes": fw.nodes, "species": species}, arrays)
        roles["faces"].append(name)
    roles["records_W1"] = roles["faces"][0]

    iw = ion.parse(inputs["R_ion"], const)
    for dt in inputs["R_ion"]["dt_ladder_s"]:
        run = schemes.run_ion(iw, dt, scheme, epochs=_epochs_for(variant, iw.epochs, dt))
        p = iw.permeant[0]
        cell = np.tile([float(iw.amounts0[s]) for s in species], (iw.times.size, 1))
        cell[:, species.index(p)] = run["amount_fmol"]
        supply = -(cell - cell[0])
        arrays = {"time_s": iw.times, "V_m_V": run["V_m_V"], "cell_amount_fmol": cell,
                  "supply_fmol": supply}
        arrays.update(_records_arrays(rw["W2"], const, species, variant))
        arrays["K_pJ"] = _K_B_form(rw["W2"], const, iw.times, supply, species, variant)
        name = f"W2_dt{dt:g}"
        write_bundle(out / name, {"world": "W2", "solver": scheme, "dt_s": dt,
                                  "species": species}, arrays)
        roles["ion"].append(name)
    roles["records_W2"] = roles["ion"][0]

    t3 = np.array([float(Fraction(k, 10 ** 4)) for k in range(61)])
    t_e = float(exact(rw["W3"]["baths"]["bath"]["events"][0]["time_s"]))
    supply3 = np.zeros((t3.size, len(species)))
    supply3[:, species.index("S")] = np.where(t3 > t_e, 0.05 * (t3 - t_e), 0.0)
    arrays = {"time_s": t3, "supply_fmol": supply3}
    arrays.update(_records_arrays(rw["W3"], const, species, variant))
    arrays["K_pJ"] = _K_B_form(rw["W3"], const, t3, supply3, species, variant)
    write_bundle(out / "W3", {"world": "W3", "solver": "rk4", "dt_s": 1e-4, "species": species},
                 arrays)
    roles["records_W3"] = "W3"
    (out / "roles.json").write_text(json.dumps(roles, indent=1) + "\n")
    return out / "roles.json"
