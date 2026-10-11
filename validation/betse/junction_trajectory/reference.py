"""Independent continuous transport/charge/energy equations; no Cells imports."""

import numpy as np
from scipy.integrate import solve_ivp


def maximum(value):
    return float(np.max(np.abs(value), initial=0))


def bind(prepared, row, trace, protocol):
    g = prepared["geometry"]
    owners, partners = (np.asarray(g[k], dtype=int) for k in ("mem_to_cells", "nn_i"))
    pairs = np.asarray(g["canonical_face_pairs"], dtype=int)
    a, b = pairs.T
    np.testing.assert_array_equal(partners[partners], np.arange(len(owners)))
    np.testing.assert_array_equal(partners[a], b)
    np.testing.assert_array_equal(
        np.sort(pairs.ravel()), np.flatnonzero(partners != np.arange(len(owners)))
    )
    area, volume = (np.asarray(g[k]) for k in ("mem_sa", "cell_vol"))
    np.testing.assert_allclose(
        area[a], area[b], rtol=protocol["tolerances"]["partner_area_rtol"], atol=0
    )
    np.testing.assert_allclose(
        row["diviterm_m"], volume / np.asarray(g["cell_sa"]), rtol=5e-14, atol=0
    )
    ids = [prepared["species"][s] for s in protocol["species"]]
    immobile = [i for i in range(len(prepared["native_valences"])) if i not in ids]
    z = np.asarray(prepared["native_valences"])
    cc, co = trace["initial_cc_cells"], trace["initial_cc_env"]
    cap = np.asarray(g["cell_sa"]) * row["specific_capacitance_F_m2"]
    voltage = trace["initial_vm_ave"]
    np.testing.assert_allclose(trace["initial_vm"], voltage[owners], rtol=0, atol=2e-12)
    np.testing.assert_allclose(
        voltage,
        row["fixture"]["target_voltage_V"],
        rtol=0,
        atol=protocol["tolerances"]["initial_voltage_V"],
    )
    chosen = {tuple(p) for p in row["fixture"]["selected_face_pairs"]}
    topology = row["case"]["topology"]
    selected = pairs if topology == "all" else pairs[:1] if topology == "single" else []
    if chosen != {tuple(p) for p in selected}:
        raise ValueError("Native junction selection differs from registered topology")
    np.testing.assert_array_equal(cc, row["fixture"]["after_setup"]["cc_cells"])
    np.testing.assert_array_equal(co, np.broadcast_to(co[:, :1], co.shape))
    opening = np.asarray([float(tuple(p) in chosen) for p in pairs])
    incidence = np.zeros((len(volume), len(pairs)))
    incidence[owners[a], np.arange(len(pairs))] = -1
    incidence[owners[b], np.arange(len(pairs))] = 1
    return {
        "species": protocol["species"],
        "valence": z[ids],
        "indices": np.asarray(ids),
        "immobile": np.asarray(immobile),
        "owners": owners,
        "partners": partners,
        "faces": pairs,
        "senders": owners[a],
        "receivers": owners[b],
        "volume_pL": volume * 1e15,
        "area_m2": np.asarray(g["cell_sa"]),
        "face_area_m2": area,
        "edge_area_m2": area[a],
        "incidence": incidence,
        "capacitance_F": cap,
        "specific_capacitance_F_m2": row["specific_capacitance_F_m2"],
        "initial_voltage_V": voltage,
        "initial_amount_fmol": cc[ids] * volume * 1e15,
        "fixed_inside_charge_fmol": (z[immobile] @ cc[immobile]) * volume * 1e15,
        "outside_volume_pL": row["effective_bath_volume_pL"],
        "outside_concentration_mM": co[ids, 0],
        "fixed_outside_charge_fmol": float(z[immobile] @ co[immobile, 0])
        * row["effective_bath_volume_pL"],
        "permeability_m_s": np.asarray(prepared["native_D_gj_m2_s"])[ids][:, a]
        * protocol["gj_surface_fraction"]
        / g["gj_len"],
        "opening": opening * np.asarray(g["gj_default_weights"])[a],
        "temperature_K": prepared["temperature_K"],
        **prepared["constants"],
    }


def voltage(c, delta):
    return c["initial_voltage_V"] + c["F"] * 1e-15 / c["capacitance_F"] * np.sum(
        c["valence"][:, None] * delta, axis=-2
    )


def edge_rates(c, concentration, potential):
    """Bernoulli form independent of Cells' positive/negative split formula."""
    ca, cb = concentration[..., c["senders"]], concentration[..., c["receivers"]]
    dv = potential[..., c["senders"]] - potential[..., c["receivers"]]
    x = c["valence"][:, None] * c["F"] * dv[..., None, :] / (c["R"] * c["temperature_K"])
    small = np.abs(x) < 1e-5
    safe = np.where(small, 1.0, x)
    bernoulli = np.where(small, 1 - x / 2 + x**2 / 12 - x**4 / 720, safe / np.expm1(safe))
    flux = (
        c["edge_area_m2"]
        * c["permeability_m_s"]
        * c["opening"]
        * 1e15
        * ((bernoulli + x) * ca - bernoulli * cb)
    )
    mu = (
        c["R"] * c["temperature_K"] * np.log(cb / ca)
        - c["valence"][:, None] * c["F"] * dv[..., None, :]
    )
    power = -1e-3 * np.sum(flux * mu, axis=-2)
    return flux, power


def unpack(c, y):
    n, e = c["initial_amount_fmol"].size, c["permeability_m_s"].size
    return (
        y[..., :n].reshape((*y.shape[:-1], *c["initial_amount_fmol"].shape)),
        y[..., n : n + e].reshape((*y.shape[:-1], *c["permeability_m_s"].shape)),
        y[..., n + e :],
    )


def rhs(c, y):
    delta, _, _ = unpack(c, y)
    concentration = (c["initial_amount_fmol"] + delta) / c["volume_pL"]
    if not np.isfinite(y).all() or np.min(concentration) <= 0:
        raise ValueError("Independent junction reference outside positive finite domain")
    flux, power = edge_rates(c, concentration, voltage(c, delta))
    return np.concatenate(((flux @ c["incidence"].T).ravel(), flux.ravel(), power))


def integrate(c, protocol, method):
    n = c["initial_amount_fmol"].size + c["permeability_m_s"].size + len(c["opening"])
    settings = protocol["reference"]
    result = solve_ivp(
        lambda t, y: rhs(c, y),
        (0, protocol["duration_s"]),
        np.zeros(n),
        method=method,
        rtol=settings["rtol"],
        atol=settings["atol"],
        max_step=settings["max_step_s"],
        dense_output=True,
    )
    if not result.success or not np.isfinite(result.y).all():
        raise ValueError("Independent junction integration failed: " + result.message)
    return result


def energy_balance(c, delta, dissipated):
    n0 = c["initial_amount_fmol"]
    chemical = (
        1e-3
        * c["R"]
        * c["temperature_K"]
        * np.sum(
            delta * (np.log(n0 / c["volume_pL"]) - 1) + (n0 + delta) * np.log1p(delta / n0),
            axis=(-2, -1),
        )
    )
    dv = voltage(c, delta) - c["initial_voltage_V"]
    electric = 0.5e12 * np.sum(c["capacitance_F"] * dv * (2 * c["initial_voltage_V"] + dv), axis=-1)
    return chemical + electric + np.sum(dissipated, axis=-1)


def accounting(c, delta, transfer, dissipated):
    values = {
        "material_fmol": maximum(np.sum(delta, axis=-1)),
        "local_transfer_fmol": maximum(delta - transfer @ c["incidence"].T),
        "energy_pJ": maximum(energy_balance(c, delta, dissipated)),
        "minimum_concentration_mM": float(
            np.min((c["initial_amount_fmol"] + delta) / c["volume_pL"])
        ),
        "minimum_dissipation_increment_pJ": float(np.min(np.diff(dissipated, axis=0), initial=0)),
    }
    if not np.isfinite(list(values.values())).all() or values["minimum_concentration_mM"] <= 0:
        raise ValueError("Invalid junction accounting/domain")
    return values


def difference(c, actual, expected):
    da, ta, ea = unpack(c, actual)
    db, tb, eb = unpack(c, expected)
    return {
        "voltage_V": maximum(voltage(c, da) - voltage(c, db)),
        "amount_fmol": maximum(da - db),
        "transfer_fmol": maximum(ta - tb),
        "energy_pJ": maximum(ea - eb),
    }
