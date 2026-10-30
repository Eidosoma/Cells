"""Independent reference coordinate checks, not biological recovery evidence."""

from copy import deepcopy

import numpy as np
import pytest

from validation.tissue import cotransport_material_coordinates as material
from validation.tissue import surface_cotransport_water_reference as ref
from validation.tissue import surface_cotransport_water_response as response
from validation.tissue import surface_dynamics_reference as dynamics
from validation.tissue.test_cotransport_water_reference import evidence


def prefix(end=2e-5):
    raw = response.definition("supply_recovery")
    raw["experiment"].update(end_time=end, observation_times=[0.0, 0.21 * end, 0.5 * end, end])
    for kind in ref.CONTROL_KINDS:
        for group in raw["experiment"][kind + "_controls"]:
            group["schedule"] = [row for row in group["schedule"] if row["time"] <= end]
    return raw


def test_charge_coordinates_reach_the_field_root_without_rebasing_anchors(monkeypatch):
    raw = prefix()
    for owner, charge in zip(
        (raw["model"]["cells"][0], raw["model"]["extracellular"][0]),
        (1e-14, -1e-14),
        strict=True,
    ):
        owner["initial_charge_C"] = charge
        owner["fixed_charge_equivalent_fmol"] += charge / (1e-15 * ref.F)
    c = ref.bind(raw)
    codec = material.bind(c)
    fields = ref.unpack(c, ref.initial(c))
    fields["membrane_transferred"][0, 0] = 1e-4
    fields["pump_cycles"][0] = 1e-5
    fields["cotransport_cycles_fmol"][:] = [0.2, 0.7]
    reduced = ref.flatten(c, fields)[codec.integrated_indices]
    full = codec.unpack(reduced)
    charge = codec.charge_increment_fmol(reduced)
    anchors = (c["qi"].copy(), c["qo"].copy())
    staged = dynamics.stage(c, full, 0, charge_equivalent_increment_fmol=charge)
    np.testing.assert_array_equal(staged["cell_charge_C"], c["qi"] + 1e-15 * ref.F * charge[:1])
    np.testing.assert_array_equal(staged["outside_charge_C"], c["qo"] + 1e-15 * ref.F * charge[1:])
    reached = []
    original_stage = dynamics.stage

    def record_stage(*args, charge_equivalent_increment_fmol=None, **kwargs):
        reached.append(charge_equivalent_increment_fmol)
        return original_stage(
            *args, charge_equivalent_increment_fmol=charge_equivalent_increment_fmol, **kwargs
        )

    monkeypatch.setattr(dynamics, "stage", record_stage)
    slope, phi, proof = ref.evaluate(c, full, 0, charge_equivalent_increment_fmol=charge)
    assert len(reached) == 1 and reached[0] is charge
    wanted = (anchors[0][0] + 1e-15 * ref.F * charge[0]) / c["layout"]["membrane_capacitance"][0]
    np.testing.assert_allclose(phi, [wanted, 0.0], rtol=2e-12, atol=2e-14)
    np.testing.assert_array_equal(c["qi"], anchors[0])
    np.testing.assert_array_equal(c["qo"], anchors[1])
    assert codec.derivative_consistency(slope)["within_roundoff"]
    evidence(
        "material-charge-field-root",
        dict(inputs=c["raw"], charge_fmol=charge.tolist(), potential_V=phi.tolist(), proof=proof),
    )


@pytest.mark.parametrize("bad", [[0.0], [0.0, np.nan], [0.0, np.inf], [True, False], ["0", "0"]])
def test_charge_coordinate_domain_is_checked_before_the_field_solve(bad):
    c = ref.bind(prefix())
    with pytest.raises(ValueError, match="finite real value per node"):
        ref.evaluate(c, ref.initial(c), 0, charge_equivalent_increment_fmol=bad)


@pytest.mark.parametrize("coordinates", ["global", "local_delta"])
def test_transport_coordinate_history_has_analytic_material_and_event_values(
    monkeypatch, coordinates
):
    """An imposed linear RHS exercises reduction and dense/event observations."""
    raw = prefix()
    cut, end = 1e-5, raw["experiment"]["end_time"]
    for kind in ref.CONTROL_KINDS:
        for group in raw["experiment"][kind + "_controls"]:
            group["schedule"] = [
                dict(time=0.0, availability=0.25),
                dict(time=cut, availability=0.75),
            ]
    c = ref.bind(raw)
    species = [row["id"] for row in raw["model"]["species"]]
    sodium, potassium, chloride = (species.index(name) for name in ("Na", "K", "Cl"))
    route_rates = np.asarray([2.0, 0.5])
    passive = np.zeros(len(species))
    passive[sodium] = 1e-3
    pump = 0.01
    inside = -passive.copy()
    inside[sodium] += -3 * pump + route_rates[1]
    inside[potassium] += 2 * pump + route_rates.sum()
    inside[chloride] += route_rates[0] + 2 * route_rates[1]
    times_seen = []

    def analytic(context, state, held, *, charge_equivalent_increment_fmol):
        times_seen.append(held)
        level = 0.25 if held < cut else 0.75
        slopes = {key: np.zeros(shape) for key, shape in context["shapes"].items()}
        slopes["amount_increment"][:, 0] = inside * level
        slopes["extracellular_amount_increment"][:, 0] = -inside * level
        slopes["membrane_transferred"][:, 0] = passive * level
        slopes["pump_cycles"][0] = pump * level
        slopes["cotransport_cycles_fmol"][:] = route_rates * level
        slopes["cotransport_transferred_fmol"][:] = context["cotransport_nu"] * route_rates * level
        slopes["energy_amount_increment_fmol"][:, 0] = np.asarray([-pump, pump, pump]) * level
        slopes["volume_increment_pL"][0] = -0.1 * level
        slopes["extracellular_volume_increment_pL"][0] = 0.1 * level
        slopes["water_transferred_pL"][0] = 0.1 * level
        slopes["membrane_dissipated_energy_pJ"][0] = 0.3 * level
        fields = ref.unpack(context, state)
        expected_charge = -(fields["membrane_transferred"][sodium, 0] + fields["pump_cycles"][0])
        np.testing.assert_array_equal(
            charge_equivalent_increment_fmol, [expected_charge, -expected_charge]
        )
        return ref.flatten(context, slopes), np.asarray([held, -held]), {}

    monkeypatch.setattr(ref, "evaluate", analytic)
    result = ref.integrate(
        raw,
        max_step_s=end / 3,
        segment_coordinates=coordinates,
        material_coordinates="transport_ledgers",
    )
    fields = ref.unpack(c, result["state"])
    times = np.asarray(result["times"])
    integral = 0.25 * np.minimum(times, cut) + 0.75 * np.maximum(times - cut, 0)
    np.testing.assert_allclose(
        fields["amount_increment"][:, :, 0], integral[:, None] * inside, rtol=2e-14, atol=2e-20
    )
    np.testing.assert_array_equal(
        fields["extracellular_amount_increment"], -fields["amount_increment"]
    )
    np.testing.assert_allclose(fields["pump_cycles"][:, 0], pump * integral, rtol=2e-14, atol=2e-20)
    np.testing.assert_allclose(
        fields["cotransport_cycles_fmol"], integral[:, None] * route_rates, rtol=2e-14, atol=2e-20
    )
    np.testing.assert_allclose(
        fields["energy_amount_increment_fmol"][:, :, 0],
        integral[:, None] * [-pump, pump, pump],
        rtol=2e-14,
        atol=2e-20,
    )
    np.testing.assert_allclose(
        fields["membrane_dissipated_energy_pJ"][:, 0], 0.3 * integral, rtol=2e-14, atol=2e-20
    )
    np.testing.assert_array_equal(result["potential_V"][:, 0], times)
    assert result["event_times"] == [0.0, cut, end]
    assert result["derived_fields"] == list(material.BULK_FIELDS)
    assert result["integrated_scalar_count"] == result["complete_scalar_count"] - 2 * len(species)
    offset = 0
    for segment in result["segments"]:
        assert set(times_seen[offset : offset + segment["evaluations"]]) == {segment["left_s"]}
        offset += segment["evaluations"]
    assert times_seen[offset:] == result["times"]
    evidence(
        "material-analytic-history-" + coordinates,
        dict(inputs=raw, state=result["state"].tolist(), segments=result["segments"]),
    )


def test_coordinate_derivative_disagreement_is_retained_without_retry(monkeypatch):
    raw = prefix()
    calls = []

    def inconsistent(context, state, held, **kwargs):
        calls.append(held)
        fields = {key: np.zeros(shape) for key, shape in context["shapes"].items()}
        fields["amount_increment"][0, 0] = 1.0
        return ref.flatten(context, fields), np.zeros(2), {}

    monkeypatch.setattr(ref, "evaluate", inconsistent)
    with pytest.raises(ref.ReferenceIntegrationError, match="Bulk RHS disagrees") as raised:
        ref.integrate(
            raw,
            max_step_s=1e-5,
            segment_coordinates="local_delta",
            material_coordinates="transport_ledgers",
        )
    failure = raised.value.diagnostics
    assert calls == [0.0]
    assert failure["automatic_retry"] is False
    assert failure["completed_segments"] == []
    assert failure["state"] == failure["initial_state"]
    assert len(failure["attempted_solver_state"]) == failure["integrated_scalar_count"]
    assert failure["attempted_full_derivative"][0] == 1.0
    diagnostic = failure["material_derivative_consistency"]
    assert diagnostic["within_roundoff"] is False
    assert np.max(diagnostic["residual_fmol_s"]) == 1.0
    assert np.max(diagnostic["roundoff_bound_fmol_s"]) == 0.0
    evidence("material-derivative-refusal", failure)


def test_short_physical_prefix_preserves_all_fields_and_refines_without_projection():
    """20 microseconds of original physics; no claim about the later recovery."""
    raw = prefix()
    before = deepcopy(raw)
    answers = []
    for coordinates, refinement in (
        ("full", 2),
        ("transport_ledgers", 1),
        ("transport_ledgers", 2),
    ):
        result = ref.integrate(
            raw,
            max_step_s=2.5e-6,
            refinement=refinement,
            segment_coordinates="local_delta",
            material_coordinates=coordinates,
        )
        answers.append(result)
        evidence(
            f"material-physical-prefix-{coordinates}-{refinement}",
            dict(inputs=raw, scope="numerical support only")
            | {
                key: value.tolist() if isinstance(value, np.ndarray) else value
                for key, value in result.items()
            },
        )
    assert raw == before
    c = ref.bind(raw)
    codec = material.bind(c)
    absolute = ref.flatten(
        c,
        {
            name: np.full(shape, 3e-28 if name.endswith("_C") else 3e-14)
            for name, shape in c["shapes"].items()
        },
    )
    for answer in answers[1:]:
        difference = np.abs(answer["state"] - answers[0]["state"])
        budget = absolute + 3e-11 * np.abs(answers[0]["state"])
        assert np.max(difference / budget) <= 1
        np.testing.assert_allclose(
            answer["potential_V"], answers[0]["potential_V"], rtol=2e-10, atol=2e-12
        )
        values = ref.unpack(c, answer["state"])
        np.testing.assert_array_equal(
            values["amount_increment"], -values["extracellular_amount_increment"]
        )
        proofs = []
        for time, state in zip(answer["times"], answer["state"], strict=True):
            charge = codec.charge_increment_fmol(codec.pack(state))
            _, _, proof = ref.evaluate(c, state, time, charge_equivalent_increment_fmol=charge)
            assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-8
            assert abs(proof["water_energy_balance_pJ_s"]) < 3e-8
            assert np.max(np.abs(proof["pool_internal_transfer_balance_pJ_s"])) < 3e-10
            assert abs(proof["water_volume_rate_balance_pL_s"]) < 3e-12
            assert np.max(np.abs(proof["adenylate_rate_fmol_s"])) < 3e-12
            assert np.max(np.abs(proof["phosphorus_rate_fmol_s"])) < 3e-12
            proofs.append(proof)
        evidence(f"material-physical-prefix-proofs-{answer['refinement']}", dict(proofs=proofs))
    np.testing.assert_allclose(answers[1]["state"], answers[2]["state"], rtol=3e-11, atol=3e-14)
