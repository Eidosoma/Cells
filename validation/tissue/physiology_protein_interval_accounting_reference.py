"""Independent named-owner interval accounting; no Cells or JAX imports.

Chemical changes subtract absolute functionals with 200 guard digits and up to
1600-digit arithmetic, independently of the production increment/series formula.
Plasma increments solve the full physical capacitance matrix with independently
discovered topology. Only original definitions and explicit inputs are read.
"""

from decimal import Context, Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_charge_rhs_reference as rhs
from validation.tissue import surface_field_reference as electrical
from validation.tissue.surface_reference import F, R


def _d(value):
    return Decimal.from_float(float(value))


def ideal_change(anchor, before, after, volume, standard, mu0_rt, temperature):
    arrays = np.broadcast_arrays(anchor, before, after, volume, standard, mu0_rt)
    result = np.empty(arrays[0].shape, dtype=object)
    with localcontext(Context(prec=1600)):
        for index in np.ndindex(result.shape):
            a, b, e, v, c0, mu = (_d(value[index]) for value in arrays)
            if b == e:
                result[index] = Decimal(0)
                continue
            start, end, scale = a + b, a + e, v * c0
            # A quadratic near-equilibrium change can lose twice the stock-to-
            # increment decimal span. Keep another 200 digits beyond that loss.
            # Exact inputs/sums above are formed before selecting log precision.
            lost = max(0, max(abs(start), abs(end)).adjusted() - abs(e - b).adjusted())
            with localcontext(Context(prec=min(1600, 2 * lost + 200))):
                left = start * (mu + (start / scale).ln() - 1)
                right = end * (mu + (end / scale).ln() - 1)
                result[index] = Decimal("0.001") * _d(R) * _d(temperature) * (right - left)
    return result


def _sum(values):
    return sum(np.asarray(values, dtype=object).flat, Decimal(0))


def _difference(before, after):
    return sum(
        (
            _d(e) - _d(b)
            for b, e in zip(np.asarray(before).flat, np.asarray(after).flat, strict=True)
        ),
        Decimal(0),
    )


def _pool(raw, b, e, cells, volumes, temperature):
    pools = {row["cell_id"]: row for row in raw["model"]["energy_pools"]}
    initial = np.asarray(
        [
            [pools[cell]["initial_amount_fmol"][key] for cell in cells]
            for key in ("ATP", "ADP", "Pi")
        ]
    )
    free = ideal_change(
        initial,
        b["energy_amount_increment_fmol"],
        e["energy_amount_increment_fmol"],
        volumes,
        1000.0,
        0.0,
        temperature,
    )
    result = []
    for i, cell in enumerate(cells):
        result.append(
            _sum(free[:, i])
            - Decimal("0.001")
            * _d(pools[cell]["delta_g0_J_per_mol"])
            * (
                _d(e["energy_amount_increment_fmol"][0, i])
                - _d(b["energy_amount_increment_fmol"][0, i])
            )
        )
    return np.asarray(result, dtype=object)


def _pool_balance(raw, b, e, cells, free):
    outer, ion = raw["model"], raw["model"]["ionic"]
    patches = {row["id"]: row for row in ion["membranes"]}
    result = list(free)
    for key, rows, cell_name in (
        ("metabolic_work_pJ", ion["membranes"], lambda row: row["inside"]),
        (
            "plasma_metabolic_work_pJ",
            outer["plasma_transport"]["membranes"],
            lambda row: patches[row["membrane_id"]]["inside"],
        ),
        ("er_metabolic_work_pJ", outer["stores"], lambda row: row["cell_id"]),
    ):
        for i, row in enumerate(rows):
            result[cells.index(cell_name(row))] += _d(e[key][i]) - _d(b[key][i])
    pools = {row["id"]: row["cell_id"] for row in outer["energy_pools"]}
    for i, row in enumerate(outer["regeneration_ports"]):
        result[cells.index(pools[row["pool_id"]])] += (
            _d(e["regeneration_dissipated_energy_pJ"][i])
            - _d(b["regeneration_dissipated_energy_pJ"][i])
            - _d(e["regeneration_supplied_work_pJ"][i])
            + _d(b["regeneration_supplied_work_pJ"][i])
        )
    return np.asarray([float(value) for value in result])


def _material(ion, state, *, has_store):
    cells = [row["id"] for row in ion["cells"]]
    outside = [row["id"] for row in ion["extracellular"]]
    species = [row["id"] for row in ion["species"]]
    patch_ids = [row["id"] for row in ion["membranes"]]
    transfer = np.array(state["membrane_transferred"], copy=True)
    if "channel_transferred" in state:
        for j, channel in enumerate(ion["channels"]):
            transfer[:, patch_ids.index(channel["membrane_id"])] += state["channel_transferred"][
                :, j
            ]
        for j, row in enumerate(ion["membranes"]):
            if pump := row["pump"]:
                transfer[species.index(pump["roles"]["sodium"]), j] += 3 * state["pump_cycles"][j]
                transfer[species.index(pump["roles"]["potassium"]), j] -= (
                    2 * state["pump_cycles"][j]
                )
    if has_store:
        # The complete-store ownership check is separate from this plasma
        # exchange ledger. Do not substitute free cytosol for the latter.
        transfer[species.index("Ca")] += (
            state["plasma_pump_cycles"]
            + state["plasma_exchange_cycles"]
            + state["calcium_channel_transferred"]
        )
        transfer[species.index("Na")] -= 3 * state["plasma_exchange_cycles"]
    local = np.array(state["amount_increment"], copy=True)
    exterior = np.array(state["extracellular_amount_increment"], copy=True)
    for j, row in enumerate(ion["membranes"]):
        local[:, cells.index(row["inside"])] += transfer[:, j]
        exterior[:, outside.index(row["outside"])] -= transfer[:, j]
    for key, rows, values, ids in (
        ("junction_transferred", ion["junctions"], local, cells),
        ("face_transferred", ion["faces"], exterior, outside),
    ):
        for j, row in enumerate(rows):
            values[:, ids.index(row["sender"])] += state[key][:, j]
            values[:, ids.index(row["receiver"])] -= state[key][:, j]
    exterior -= state["reservoir_supplied"]
    total = (
        np.sum(state["amount_increment"], axis=1)
        + np.sum(state["extracellular_amount_increment"], axis=1)
        - np.sum(state["reservoir_supplied"], axis=1)
    )
    return dict(local=local, outside=exterior, total=total)


def evaluate(
    raw,
    before,
    after,
    binding,
    current_diffusion,
    reference_protein,
    current_protein,
    *,
    valence,
    before_control,
    after_control,
):
    """Independent complete-owner energy and plasma/pool material residuals."""
    context, _, phi, proof = rhs.evaluate(
        raw,
        before,
        binding,
        current_diffusion,
        before_control,
        reference_protein,
        current_protein,
        valence=valence,
    )
    _, _, end_phi, end_proof = rhs.evaluate(
        raw,
        after,
        binding,
        current_diffusion,
        after_control,
        reference_protein,
        current_protein,
        valence=valence,
    )
    oracle = rhs.permeability.ORACLES[raw["model"]["id"]]
    b, e = (oracle.unpack(context, oracle.flatten(context, fields)) for fields in (before, after))
    ion = raw["model"].get("ionic", raw["model"])
    cells = [row["id"] for row in ion["cells"]]
    temperature, n = ion["temperature_K"], len(cells)
    with localcontext(Context(prec=4096)):
        chemical = _sum(
            ideal_change(
                context["ao"],
                b["extracellular_amount_increment"],
                e["extracellular_amount_increment"],
                context["vo"],
                1.0,
                0.0,
                temperature,
            )
        )
        er_energy = Decimal(0)
        if "chemical_amount_increment" not in b:
            chemical += _sum(
                ideal_change(
                    context["ai"],
                    b["amount_increment"],
                    e["amount_increment"],
                    context["vi"],
                    1.0,
                    0.0,
                    temperature,
                )
            )
        else:
            for i, store in enumerate(context["stores"]):
                chemical += _sum(
                    ideal_change(
                        store.n0,
                        b["chemical_amount_increment"][i],
                        e["chemical_amount_increment"][i],
                        store.volume,
                        store.c0,
                        store.mu0[:, None],
                        temperature,
                    )
                )
                voltages = []
                for state in (b, e):
                    q = sum(
                        (
                            _d(z) * _d(v)
                            for z, v in zip(
                                store.z,
                                state["chemical_amount_increment"][i, :, store.er],
                                strict=True,
                            )
                        ),
                        Decimal(0),
                    )
                    voltages.append(
                        _d(store.membrane["initial_voltage_V"]) + _d(F * 1e-15) * q / _d(store.cap)
                    )
                er_energy += Decimal("5e11") * _d(store.cap) * (voltages[1] ** 2 - voltages[0] ** 2)
        raw_stage = dict(
            layout=context["layout"],
            gauge_mask=[
                row["id"] == ion["closure"]["gauge_reference"] for row in ion["extracellular"]
            ],
        )
        matrix, active, reservoir, _, floating, _ = electrical.topology(raw_stage)
        pins = ~active | reservoir
        for members in floating:
            pins[members[0]] = True
        free = np.flatnonzero(~pins)
        charges = []
        z = [row["valence"] for row in ion["species"]]
        for key in ("amount_increment", "extracellular_amount_increment"):
            for i in range(b[key].shape[1]):
                charges.append(
                    float(
                        _d(F * 1e-15)
                        * sum(
                            (
                                _d(v) * (_d(e[key][j, i]) - _d(b[key][j, i]))
                                for j, v in enumerate(z)
                            ),
                            Decimal(0),
                        )
                    )
                )
        dphi = np.zeros(len(phi))
        dphi[free] = np.linalg.solve(matrix[np.ix_(free, free)], np.asarray(charges)[free])
        plasma, endpoint_plasma = Decimal(0), Decimal(0)
        for patch in ion["membranes"]:
            i = cells.index(patch["inside"])
            o = n + [row["id"] for row in ion["extracellular"]].index(patch["outside"])
            vb, dv, ve = _d(phi[i] - phi[o]), _d(dphi[i] - dphi[o]), _d(end_phi[i] - end_phi[o])
            plasma += Decimal("5e11") * _d(patch["capacitance_F"]) * ((vb + dv) ** 2 - vb**2)
            endpoint_plasma += Decimal("5e11") * _d(patch["capacitance_F"]) * (ve**2 - vb**2)
        heat = sum(
            (_difference(b[name], e[name]) for name in b if name.endswith("_dissipated_energy_pJ")),
            Decimal(0),
        )
        reservoir_work = _difference(b["reservoir_work_pJ"], e["reservoir_work_pJ"])
        electrode_work = _difference(b["electrode_work_pJ"], e["electrode_work_pJ"])
        pool, supply, metabolic = Decimal(0), Decimal(0), Decimal(0)
        balances = {}
        for label, state in (("before", b), ("after", e)):
            for key, value in _material(
                ion, state, has_store="chemical_amount_increment" in b
            ).items():
                balances[label + "/" + key] = value
        if "energy_amount_increment_fmol" in b:
            free_pool = _pool(raw, b, e, cells, context["vi"], temperature)
            pool = _sum(free_pool)
            balances["interval/pool_energy"] = _pool_balance(raw, b, e, cells, free_pool)
            supply = _difference(
                b["regeneration_supplied_work_pJ"], e["regeneration_supplied_work_pJ"]
            )
        else:
            metabolic = sum(
                (
                    _difference(b[key], e[key])
                    for key in (
                        "metabolic_work_pJ",
                        "plasma_metabolic_work_pJ",
                        "er_metabolic_work_pJ",
                    )
                    if key in b
                ),
                Decimal(0),
            )
        terms = dict(
            chemical_change_pJ=chemical,
            plasma_capacitor_change_pJ=plasma,
            er_capacitor_change_pJ=er_energy,
            fuel_chemical_change_pJ=pool,
            dissipated_energy_pJ=heat,
            reservoir_work_pJ=reservoir_work,
            electrode_work_pJ=electrode_work,
            external_metabolic_work_pJ=metabolic,
            regeneration_supplied_work_pJ=supply,
        )
        residual = (
            chemical
            + plasma
            + er_energy
            + pool
            + heat
            - reservoir_work
            - electrode_work
            - metabolic
            - supply
        )
        balances["interval/energy"] = float(residual)
        return dict(
            energy_terms={key: float(value) for key, value in terms.items()},
            balances=balances,
            exact_energy_terms={key: str(value) for key, value in terms.items()},
            actual_endpoint_plasma_change_pJ=float(endpoint_plasma),
            field_proof=proof,
            endpoint_field_proof=end_proof,
            chemical_arithmetic=(
                "independent absolute-functional subtraction, 200 guard digits, up to1600"
            ),
            coupled_trajectory_accuracy_claim=False,
        )
