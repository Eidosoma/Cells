"""Algebra/codec checks only; manufactured vectors are not trajectory evidence."""

import math
from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np
import pytest

from validation.tissue import cotransport_material_coordinates as coordinates


def context(*, pump=True, routes=True, reordered=False):
    """Minimal plain-data bound context, without any physical RHS or integrator."""
    species = [("Na", 1), ("K", 1), ("Cl", -1), ("Ca", 2)]
    if reordered:
        species.reverse()
    ids = [name for name, _ in species]
    route_rows = (
        [
            dict(
                id="kcc",
                membrane_id="patch",
                law="kcc_reversible_tanh@1",
                roles=dict(potassium="K", chloride="Cl"),
            ),
            dict(
                id="nkcc",
                membrane_id="patch",
                law="nkcc_reversible_tanh@1",
                roles=dict(sodium="Na", potassium="K", chloride="Cl"),
            ),
        ]
        if routes
        else []
    )
    if reordered:
        route_rows.reverse()
    nu = np.zeros((4, len(route_rows)), dtype=np.int64)
    for j, row in enumerate(route_rows):
        for role, name in row["roles"].items():
            nu[ids.index(name), j] = 2 if row["id"] == "nkcc" and role == "chloride" else 1
    model = dict(
        id=coordinates.MODEL_ID,
        temperature_K=298.15,
        species=[dict(id=name, valence=z) for name, z in species],
        cells=[dict(id="cell", initial_charge_C=0.0)],
        extracellular=[dict(id="outside", initial_charge_C=0.0, reservoir=False)],
        membranes=[
            dict(
                id="patch",
                inside="cell",
                outside="outside",
                pump=dict(
                    law="nak_atp_mass_action_positive@1",
                    roles=dict(sodium="Na", potassium="K"),
                    stoichiometry={"Na": -3, "K": 2},
                    metabolism=dict(kind="finite_energy_pool@1", pool_id="fuel"),
                )
                if pump
                else None,
            )
        ],
        channels=[],
        junctions=[],
        faces=[],
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1",
            gauge_reference="outside",
        ),
        energy_pools=[dict(id="fuel", cell_id="cell")],
        regeneration_ports=[dict(pool_id="fuel")],
        cotransporters=route_rows,
    )
    s, r = 4, len(route_rows)
    shapes = dict(
        amount_increment=(s, 1),
        extracellular_amount_increment=(s, 1),
        membrane_transferred=(s, 1),
        junction_transferred=(s, 0),
        face_transferred=(s, 0),
        reservoir_supplied=(s, 1),
        membrane_dissipated_energy_pJ=(1,),
        junction_dissipated_energy_pJ=(0,),
        face_dissipated_energy_pJ=(0,),
        electrode_charge_transferred_C=(1,),
        reservoir_work_pJ=(1,),
        electrode_work_pJ=(1,),
        channel_gate=(2, 0),
        channel_transferred=(s, 0),
        channel_dissipated_energy_pJ=(s, 0),
        junction_gate=(0,),
        pump_cycles=(1,),
        pump_dissipated_energy_pJ=(1,),
        metabolic_work_pJ=(1,),
        energy_amount_increment_fmol=(3, 1),
        regeneration_cycles_fmol=(1,),
        regeneration_dissipated_energy_pJ=(1,),
        regeneration_supplied_work_pJ=(1,),
        volume_increment_pL=(1,),
        extracellular_volume_increment_pL=(1,),
        water_transferred_pL=(1,),
        water_dissipated_energy_pJ=(1,),
        pool_volume_work_pJ=(1,),
        cotransport_cycles_fmol=(r,),
        cotransport_transferred_fmol=(s, r),
        cotransport_dissipated_energy_pJ=(r,),
    )
    return dict(
        raw=dict(model=model),
        shapes=shapes,
        cotransport_nu=nu,
        cotransport_inside=[0] * r,
        cotransport_outside=[1] * r,
        qi=np.array([0.0]),
        qo=np.array([0.0]),
        layout=dict(valence=[[z] for _, z in species], membrane_cell=[0], membrane_outside=[0]),
    )


def reduced(codec, **fields):
    full = np.zeros(codec.full_size)
    for name, value in fields.items():
        full[codec.slices[name]] = np.asarray(value, dtype=float).ravel()
    return full[codec.integrated_indices]


def decimal_inside(codec, full):
    """80-digit real linear identity from the exact input binary64 numbers."""
    with localcontext() as c:
        c.prec = 80
        membrane = full[codec.slices["membrane_transferred"]]
        pump = Decimal.from_float(float(full[codec.slices["pump_cycles"]][0]))
        routes = full[codec.slices["cotransport_cycles_fmol"]]
        return np.asarray(
            [
                float(
                    -Decimal.from_float(float(membrane[i]))
                    + int(codec.pump_stoichiometry[i]) * pump
                    + sum(
                        (
                            int(n) * Decimal.from_float(float(x))
                            for n, x in zip(codec.cotransport_nu[i], routes, strict=True)
                        ),
                        Decimal(0),
                    )
                )
                for i in range(len(codec.species_ids))
            ]
        )


def test_original_field_shape_and_kept_values_roundtrip_without_rebasing_other_histories():
    codec = coordinates.bind(context())
    assert tuple(codec.shapes) == coordinates.FIELD_NAMES
    assert len(codec.shapes) == 31 and codec.full_size == 46 and codec.size == 38
    values = np.arange(codec.size, dtype=float) / 1024
    full = codec.unpack(values)
    np.testing.assert_array_equal(codec.pack(full), values)
    np.testing.assert_array_equal(full[codec.integrated_indices], values)
    for name in (
        "energy_amount_increment_fmol",
        "regeneration_cycles_fmol",
        "pool_volume_work_pJ",
        "volume_increment_pL",
        "extracellular_volume_increment_pL",
        "water_transferred_pL",
        "water_dissipated_energy_pJ",
        "metabolic_work_pJ",
        "cotransport_transferred_fmol",
    ):
        np.testing.assert_array_equal(
            codec.unpack(codec.pack(full))[codec.slices[name]], full[codec.slices[name]]
        )
    with pytest.raises(ValueError):
        codec.integrated_indices[0] = 0


@pytest.mark.parametrize("pump", [False, True])
@pytest.mark.parametrize("routes", [False, True])
def test_zero_history_and_absent_pump_or_routes(pump, routes):
    codec = coordinates.bind(context(pump=pump, routes=routes))
    full = np.zeros(codec.full_size)
    np.testing.assert_array_equal(codec.unpack(codec.pack(full)), full)
    np.testing.assert_array_equal(codec.charge_increment_fmol(codec.pack(full)), np.zeros(2))
    np.testing.assert_array_equal(codec.pack_derivative(full), np.zeros(codec.size))


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("reordered", [False, True])
def test_signed_material_and_charge_identity_with_independent_decimal_arithmetic(
    direction, reordered
):
    codec = coordinates.bind(context(reordered=reordered))
    passive = {"Na": 1 / 32, "K": -1 / 64, "Cl": 1 / 128, "Ca": 1 / 256}
    vector = reduced(
        codec,
        membrane_transferred=[direction * passive[name] for name in codec.species_ids],
        pump_cycles=[direction / 8],
        cotransport_cycles_fmol=[direction * 0.75, -direction * 0.25],
    )
    full = codec.unpack(vector)
    expected = decimal_inside(codec, full)
    np.testing.assert_array_equal(full[codec.slices["amount_increment"]], expected)
    np.testing.assert_array_equal(full[codec.slices["extracellular_amount_increment"]], -expected)
    np.testing.assert_array_equal(codec.pack(full), vector)
    with localcontext() as c:
        c.prec = 80
        charge = -sum(
            (
                int(z) * Decimal.from_float(float(value))
                for z, value in zip(
                    codec.valence, full[codec.slices["membrane_transferred"]], strict=True
                )
            ),
            Decimal(0),
        ) - Decimal.from_float(float(full[codec.slices["pump_cycles"]][0]))
    np.testing.assert_array_equal(
        codec.charge_increment_fmol(vector), [float(charge), -float(charge)]
    )
    np.testing.assert_array_equal(
        codec.charge_increment_C(vector),
        codec.charge_increment_fmol(vector) * coordinates.CHARGE_PER_FMOL,
    )


def test_large_neutral_transfer_does_not_destroy_small_electrogenic_charge():
    codec = coordinates.bind(context())
    vector = reduced(
        codec,
        membrane_transferred=[2.0**-30, -(2.0**-31), 2.0**-32, 2.0**-33],
        pump_cycles=[2.0**-34],
        cotransport_cycles_fmol=[2.0**40, -(2.0**41)],
    )
    full = codec.unpack(vector)
    np.testing.assert_array_equal(
        full[codec.slices["amount_increment"]], decimal_inside(codec, full)
    )
    expected = -(2.0**-31 + 2.0**-34)
    actual = codec.charge_increment_fmol(vector)
    assert actual[0] == expected and actual[1] == -expected
    naive = math.fsum(
        int(z) * float(value)
        for z, value in zip(codec.valence, full[codec.slices["amount_increment"]], strict=True)
    )
    assert naive != expected
    # This is a deliberately enormous algebra probe, not a positive-inventory
    # physical state or evidence of reachability.


def test_pure_neutral_routes_change_bulk_without_changing_electrical_charge():
    codec = coordinates.bind(context(pump=False))
    vector = reduced(codec, cotransport_cycles_fmol=[123.25, -47.5])
    full = codec.unpack(vector)
    assert np.any(full[codec.slices["amount_increment"]] != 0)
    np.testing.assert_array_equal(codec.charge_increment_fmol(vector), [0.0, 0.0])


def test_kept_derivative_matches_linear_map_and_refuses_a_real_source_mismatch():
    codec = coordinates.bind(context())
    vector = reduced(
        codec,
        membrane_transferred=[0.125, -0.25, 0.5, 0.0],
        pump_cycles=[0.125],
        cotransport_cycles_fmol=[1000.0, -400.0],
        regeneration_cycles_fmol=[0.25],
    )
    full = codec.unpack(vector)
    report = codec.derivative_consistency(full)
    assert report["within_roundoff"] and np.all(report["residual_fmol_s"] == 0)
    np.testing.assert_array_equal(codec.pack_derivative(full), vector)
    rounded = full.copy()
    i = codec.slices["amount_increment"].start
    rounded[i] = np.nextafter(rounded[i], np.inf)
    assert codec.derivative_consistency(rounded)["within_roundoff"]
    np.testing.assert_array_equal(codec.pack_derivative(rounded), vector)
    corrupted = full.copy()
    corrupted[i] += 0.01
    assert not codec.derivative_consistency(corrupted)["within_roundoff"]
    with pytest.raises(ValueError, match="Bulk RHS"):
        codec.pack_derivative(corrupted)


def test_zero_rate_consistency_has_no_free_absolute_floor():
    codec = coordinates.bind(context())
    slope = np.zeros(codec.full_size)
    slope[codec.slices["amount_increment"].start] = 1e-30
    report = codec.derivative_consistency(slope)
    assert np.all(report["roundoff_bound_fmol_s"] == 0)
    assert not report["within_roundoff"]


def test_pack_refuses_legacy_inconsistent_bulk_instead_of_projecting_it():
    codec = coordinates.bind(context())
    full = np.zeros(codec.full_size)
    full[codec.slices["amount_increment"].start] = np.nextafter(0.0, 1.0)
    before = full.copy()
    with pytest.raises(ValueError, match="inconsistent"):
        codec.pack(full)
    np.testing.assert_array_equal(full, before)


@pytest.mark.parametrize("method", ["pack", "unpack", "pack_derivative", "charge_increment_fmol"])
@pytest.mark.parametrize("damage", ["shape", "nonfinite", "complex", "boolean"])
def test_state_vector_shape_and_type_refusals(method, damage):
    codec = coordinates.bind(context())
    size = codec.full_size if method in ("pack", "pack_derivative") else codec.size
    vector = np.zeros(size)
    if damage == "shape":
        vector = vector.reshape(1, -1)
    elif damage == "nonfinite":
        vector[0] = np.nan
    elif damage == "complex":
        vector = vector.astype(complex)
    elif damage == "boolean":
        vector = vector.astype(bool)
    with pytest.raises(ValueError, match="finite floating vector"):
        getattr(codec, method)(vector)


def test_absent_pump_history_is_refused_not_erased():
    codec = coordinates.bind(context(pump=False))
    vector = reduced(codec, pump_cycles=[0.125])
    with pytest.raises(ValueError, match="absent Na/K"):
        codec.unpack(vector)
    with pytest.raises(ValueError, match="absent Na/K"):
        codec.charge_increment_fmol(vector)


@pytest.mark.parametrize(
    "change",
    [
        "model",
        "temperature",
        "cell",
        "outside",
        "reservoir",
        "patch_owner",
        "gauge",
        "initial_charge",
        "channels",
        "junctions",
        "faces",
        "pump_stoichiometry",
        "pump_law",
        "pump_pool",
        "pool_owner",
        "port_owner",
        "route_owner",
        "route_law",
        "route_charge",
        "bound_coefficients",
        "bound_route_owner",
        "bound_charge",
        "bound_valence",
        "missing_field",
        "padded_field",
        "field_order",
    ],
)
def test_explicit_scope_and_owner_refusals(change):
    c = deepcopy(context())
    m = c["raw"]["model"]
    if change == "model":
        m["id"] = "resolved_cotransport@1"
    elif change == "temperature":
        m["temperature_K"] = 310.0
    elif change in ("cell", "outside"):
        m["cells" if change == "cell" else "extracellular"].append(dict(id="extra"))
    elif change == "reservoir":
        m["extracellular"][0]["reservoir"] = True
    elif change == "patch_owner":
        m["membranes"][0]["inside"] = "other"
    elif change == "gauge":
        m["closure"]["gauge_reference"] = "other"
    elif change == "initial_charge":
        m["cells"][0]["initial_charge_C"] = 1e-15
    elif change in ("channels", "junctions", "faces"):
        m[change] = [dict(id="unsupported")]
    elif change == "pump_stoichiometry":
        m["membranes"][0]["pump"]["stoichiometry"]["Na"] = -2
    elif change == "pump_law":
        m["membranes"][0]["pump"]["law"] = "other"
    elif change == "pump_pool":
        m["membranes"][0]["pump"]["metabolism"]["pool_id"] = "other"
    elif change == "pool_owner":
        m["energy_pools"][0]["cell_id"] = "other"
    elif change == "port_owner":
        m["regeneration_ports"][0]["pool_id"] = "other"
    elif change == "route_owner":
        m["cotransporters"][0]["membrane_id"] = "other"
    elif change == "route_law":
        m["cotransporters"][0]["law"] = "other"
    elif change == "route_charge":
        m["species"][2]["valence"] = 0
        c["layout"]["valence"][2][0] = 0
    elif change == "bound_coefficients":
        c["cotransport_nu"][0, 0] = 1
    elif change == "bound_route_owner":
        c["cotransport_outside"][0] = 0
    elif change == "bound_charge":
        c["qi"][0] = 1e-15
    elif change == "bound_valence":
        c["layout"]["valence"][0][0] = -1
    elif change == "missing_field":
        c["shapes"].pop("water_transferred_pL")
    elif change == "padded_field":
        c["shapes"]["amount_increment"] = (4, 2)
    elif change == "field_order":
        c["shapes"] = dict(reversed(list(c["shapes"].items())))
    with pytest.raises(ValueError):
        coordinates.bind(c)
