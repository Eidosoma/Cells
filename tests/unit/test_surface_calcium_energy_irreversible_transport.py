"""Literal None-energy rates, owned inventories and explicit physical work."""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core import surface_calcium_energy_irreversible_transport_spec as schema
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_calcium_energy_hcn_extra as parent
from cells.models import surface_calcium_energy_irreversible_transport as model
from cells.processes import betse_network_transport as native
from validation.tissue import calcium_energy_irreversible_transport_fixtures as fixtures


def initial(raw=None):
    spec = schema.parse(fixtures.probe() if raw is None else raw)
    state, layout = model.initial_values(spec)
    table = control_values(spec, [0.0])
    return spec, state, layout, type(table)(*(value[0] for value in table))


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "irreversible-transport"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_initial44_fields_have_physical_work_balance_and_literal_source_zero(arm, padded):
    spec, state, layout, controls = initial(fixtures.probe(arm, padded=padded))
    result = model.readouts(state, controls, layout, xp=np)
    evidence(
        "physical-stage-" + arm + "-" + str(padded),
        dict(
            definition=schema.to_dict(spec),
            valid=bool(result.valid),
            source_diagnostic=result.network.source_reaction_energy_J_mol.tolist(),
            heat_pJ_s=result.network_heat_pJ_s.tolist(),
            chemical_power=result.network_chemical_power_pJ_s.tolist(),
            electrical_power=result.network_electrical_power_pJ_s.tolist(),
            supplied_power=result.network_work_pJ_s.tolist(),
        ),
        {"derivative__" + key: value for key, value in result.derivative._asdict().items()},
    )
    assert result.valid and len(state) == 44 and type(layout) is model.LAYOUT_TYPE
    assert not np.any(layout.network_reversible)
    assert np.all(result.network.source_reaction_energy_J_mol == 0)
    assert np.all(result.network_heat_pJ_s >= 0)
    np.testing.assert_allclose(
        result.network_chemical_power_pJ_s
        + result.network_electrical_power_pJ_s
        + result.network_heat_pJ_s
        - result.network_work_pJ_s,
        0,
        rtol=0,
        atol=1e-10,
    )
    assert abs(float(result.field.energy_balance_pJ_s)) <= 1e-10
    assert model.check_values(state, spec)["max_network_physical_work_error"] == 0.0
    if arm not in ("empty", "blocked"):
        assert np.any(result.network_heat_pJ_s > 0)  # Source diagnostic zero is not heat.
    if arm == "signed-regulation":
        assert result.network.regulation[0] < 0 and result.network.extent_fmol_s[0] < 0
    if arm == "work-extraction":
        assert result.network_work_pJ_s[0] < 0


def test_None_and_string_None_roundtrip_without_reversible_evaluation():
    cases = [initial(fixtures.probe(native_none=value)) for value in (None, "None")]
    for literal, (spec, _, _, _) in zip((None, "None"), cases, strict=True):
        raw = schema.to_dict(spec)
        assert all(
            row["configuration"]["standard free energy"] == literal
            for row in raw["model"]["network_transport"]["routes"]
        )
        assert schema.to_dict(schema.parse(raw)) == raw
    a, b = [model.readouts(state, controls, layout, xp=np) for _, state, layout, controls in cases]
    for actual, expected in zip(a.derivative, b.derivative, strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_declared_external_work_does_not_modify_native_forward_loading_or_direct_ATP():
    _, state, layout, controls = initial()
    larger = layout._replace(
        network_supplied_energy_J_mol=np.where(
            layout.network_active, layout.network_supplied_energy_J_mol + 10000, 0.0
        )
    )
    first, second = (model.readouts(state, controls, p, xp=np) for p in (layout, larger))
    assert first.valid and second.valid
    for name in first.network._fields:
        np.testing.assert_array_equal(getattr(first.network, name), getattr(second.network, name))
    for name in model.base_state(first.derivative)._fields:
        np.testing.assert_array_equal(
            getattr(first.derivative, name), getattr(second.derivative, name)
        )
    np.testing.assert_array_equal(
        first.derivative.energy_amount_increment_fmol,
        second.derivative.energy_amount_increment_fmol,
    )
    assert np.any(second.network_heat_pJ_s != first.network_heat_pJ_s)


def test_actual_transport_chemical_owner_field_work_and_no_inferred_fuel_use():
    _, state, layout, controls = initial()
    off = controls._replace(network_transport=np.zeros_like(controls.network_transport))
    active, blocked = (model.readouts(state, value, layout, xp=np) for value in (controls, off))
    difference = model.STATE_TYPE(
        *(a - b for a, b in zip(active.derivative, blocked.derivative, strict=True))
    )
    np.testing.assert_array_equal(difference.energy_amount_increment_fmol, 0)
    for i in range(layout.er_initial_amount.shape[0]):
        np.testing.assert_allclose(
            difference.chemical_amount_increment[i, :, int(layout.er_cytosol[i])],
            layout.free_ion_selector @ difference.amount_increment[:, i],
            rtol=3e-12,
            atol=3e-13,
        )
    np.testing.assert_allclose(
        difference.amount_increment.sum(axis=-1)
        + difference.extracellular_amount_increment.sum(axis=-1),
        0,
        rtol=0,
        atol=3e-14,
    )
    np.testing.assert_allclose(
        active.field.chemical_energy_rate_pJ_s - blocked.field.chemical_energy_rate_pJ_s,
        np.sum(active.network_chemical_power_pJ_s),
        rtol=0,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        active.field.capacitor_energy_rate_pJ_s - blocked.field.capacitor_energy_rate_pJ_s,
        np.sum(active.network_electrical_power_pJ_s),
        rtol=0,
        atol=1e-10,
    )


@pytest.mark.parametrize("arm", ["empty", "blocked"])
def test_empty_and_blocked_parent_reduction_is_exact(arm):
    spec, state, layout, controls = initial(fixtures.probe(arm, padded=True))
    old, old_layout = parent.initial_values(schema.base_spec(spec))
    a = parent.readouts(old, model.base_control(controls), old_layout, xp=np)
    b = model.readouts(state, controls, layout, xp=np)
    for actual, expected in zip(model.base_state(b.derivative), a.derivative, strict=True):
        np.testing.assert_array_equal(actual, expected)
    for actual, expected in zip(jax.tree.leaves(b.field), jax.tree.leaves(a.field), strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_negative_physical_heat_refuses_unchanged_signed_native_rates_even_when_zero_diagnostic():
    _, state, layout, controls = initial(fixtures.probe("signed-regulation"))
    bad = layout._replace(
        network_supplied_energy_J_mol=np.where(layout.network_active, 60000.0, 0.0)
    )
    result = model.readouts(state, controls, bad, xp=np)
    assert not result.valid and result.network.extent_fmol_s[0] < 0
    assert result.network.regulation[0] < 0 and result.network_heat_pJ_s[0] < 0
    assert result.network.source_reaction_energy_J_mol[0] == 0
    c = model.concentrations(state, bad, xp=np)
    vm = result.field.rates.membrane_voltage_V[bad.network_membrane]
    source = native.rates(
        c,
        vm,
        model.topology(bad),
        model.network_parameters(bad),
        controls.network_transport,
        bad.network_density,
        xp=np,
    )
    np.testing.assert_array_equal(result.network.extent_fmol_s, source.extent_fmol_s)
    assert all(
        np.isnan(value).all() for value in model.rhs(state, controls, bad, bad.active, xp=np)
    )
    blocked = controls._replace(network_transport=np.zeros_like(controls.network_transport))
    assert model.readouts(state, blocked, bad, xp=np).valid  # Zero actual dissipation is allowed.


@pytest.mark.parametrize(
    "fault",
    [
        "reversible",
        "conversion",
        "work_kind",
        "missing_work",
        "nonfinite_work",
        "ignore_exterior",
        "profile",
        "no_transfer",
        "capacity",
        "constants",
        "negative_heat",
    ],
)
def test_invalid_schema_or_initial_physical_dissipation_refuses(fault):
    raw = fixtures.probe()
    block = raw["model"]["network_transport"]
    route = block["routes"][0]
    if fault == "reversible":
        route["configuration"]["standard free energy"] = 0.0
    elif fault == "conversion":
        route["configuration"]["products"] = ["Na", "Cl"]
    elif fault == "work_kind":
        route["drive"]["kind"] = "inferred_ATP"
    elif fault == "missing_work":
        del route["drive"]
    elif fault == "nonfinite_work":
        route["drive"]["supplied_energy_J_per_mol"] = float("inf")
    elif fault == "ignore_exterior":
        route["configuration"]["ignore ECM"] = True
    elif fault == "profile":
        route["configuration"]["apply to"] = ["tissue"]
    elif fault == "no_transfer":
        route["configuration"]["transfered out of cell"] = route["configuration"][
            "transfered into cell"
        ][:]
    elif fault == "capacity":
        raw["execution"]["network_transport_capacity"] = 0
    elif fault == "constants":
        block["constants"]["gas_constant_J_mol_K"] = 8.0
    else:
        route["drive"]["supplied_energy_J_per_mol"] = -1e6
    with pytest.raises(ConfigError):
        schema.parse(raw)


@pytest.mark.parametrize("fault", ["heat", "chemical", "electrical", "padding"])
def test_corrupt_integrated_work_or_padding_refuses(fault):
    spec, state, layout, controls = initial(fixtures.probe(padded=True))
    if fault == "heat":
        state.network_dissipated_energy_pJ[0] = -1e-30
    elif fault == "chemical":
        state.network_chemical_work_pJ[0] = 1e-4
    elif fault == "electrical":
        state.network_electrical_work_pJ[0] = 1e-4
    else:
        state.network_chemical_work_pJ[-1] = 1e-4
    assert not model.control_domain_valid(state, controls, layout, layout.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_readouts_include_separate_physical_work_and_source_diagnostic():
    spec, state, layout, _ = initial()
    history = model.STATE_TYPE(*(value[None] for value in state))
    observed = model.observe_history(np.asarray([0.0]), history, layout, np.asarray([0.0]), spec)
    assert set(vars(observed)) == set(model.OBSERVATION_FIELDS)
    np.testing.assert_array_equal(observed.network_source_reaction_energy_J_mol, 0)
    assert np.any(observed.network_dissipation_pJ_s > 0)
    assert observed.network_chemical_work_pJ.shape == observed.network_electrical_work_pJ.shape
