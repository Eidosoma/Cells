"""Live finite-fuel ownership, native standards and complete physical ledgers."""

import json
import os
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import surface_calcium_energy_atp_transport_spec as schema
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_calcium_energy as pools
from cells.models import surface_calcium_energy_atp_transport as model
from cells.models import surface_calcium_energy_hcn_extra as parent
from cells.processes import betse_network_transport as native
from validation.tissue import calcium_energy_atp_transport_fixtures as fixtures


def initial(raw=None):
    spec = schema.parse(fixtures.probe() if raw is None else raw)
    state, layout = model.initial_values(spec)
    table = control_values(spec, [0.0])
    return spec, state, layout, type(table)(*(value[0] for value in table))


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "atp-transport"
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
def test_complete46_stage_owned_fuel_heat_and_native_affinity(arm, padded):
    spec, state, layout, controls = initial(fixtures.probe(arm, padded=padded))
    value = model.readouts(state, controls, layout, xp=np)
    evidence(
        "stage-" + arm + "-" + str(padded),
        dict(
            definition=schema.to_dict(spec),
            valid=bool(value.valid),
            source_energy_J_mol=value.network.source_reaction_energy_J_mol,
            physical_energy_J_mol=value.network_reaction_energy_J_mol,
            fuel_hydrolysis_J_mol=value.network_fuel_energy_J_mol,
            released_fuel_power_pJ_s=value.network_fuel_power_pJ_s,
            gross_hydrolysis_fmol_s=value.exchange.gross_hydrolysis_fmol_s,
            gross_synthesis_fmol_s=value.exchange.gross_synthesis_fmol_s,
        ),
        {"derivative__" + key: x for key, x in value.derivative._asdict().items()},
    )
    assert value.valid and len(state) == 46 and type(layout) is model.LAYOUT_TYPE
    assert not hasattr(state, "network_supplied_work_pJ")
    np.testing.assert_array_equal(layout.network_reversible, layout.network_active)
    np.testing.assert_allclose(
        value.network.source_reaction_energy_J_mol,
        value.network_reaction_energy_J_mol,
        rtol=3e-12,
        atol=3e-9,
    )
    np.testing.assert_allclose(
        value.network_chemical_power_pJ_s
        + value.network_electrical_power_pJ_s
        + value.network_heat_pJ_s
        - value.network_fuel_power_pJ_s,
        0,
        atol=1e-10,
        rtol=0,
    )
    assert abs(float(value.field.energy_balance_pJ_s)) <= 1e-10
    assert np.all(value.network_heat_pJ_s >= 0)
    assert model.check_values(state, spec)["max_network_physical_work_error"] == 0
    if arm == "reverse":
        assert value.network.extent_fmol_s[0] < 0 and value.network_fuel_power_pJ_s[0] < 0
        assert value.derivative.network_gross_synthesis_fmol[0] > 0
        assert value.derivative.network_gross_hydrolysis_fmol[0] == 0
    if arm == "mixed":
        assert np.any(value.network.extent_fmol_s > 0) and np.any(value.network.extent_fmol_s < 0)


def test_roundtrip_declares_separate_standards_and_actual_pool_owners():
    spec, state, layout, controls = initial()
    raw = schema.to_dict(spec)
    assert schema.to_dict(schema.parse(raw)) == raw
    assert raw["model"]["network_transport"]["constants"]["fuel_standard_state_mM"] == 1000
    assert raw["model"]["network_transport"]["constants"]["ionic_standard_state_mM"] == 1
    np.testing.assert_array_equal(
        layout.network_pool_owner[layout.network_active],
        layout.network_inside[layout.network_active],
    )
    np.testing.assert_array_equal(layout.network_species_valence[-3:], 0)
    concentrations = model.concentrations(state, layout, xp=np)
    np.testing.assert_array_equal(
        concentrations[-3:, : layout.active.size],
        pools.energy_amounts(state, layout) / layout.volume,
    )
    np.testing.assert_array_equal(concentrations[-3:, layout.active.size :], 0)
    value = model.readouts(state, controls, layout, xp=np)
    for j in range(len(spec.model.network_transporters)):
        owner = layout.network_pool_owner[j]
        np.testing.assert_allclose(
            value.network_fuel_energy_J_mol[j],
            value.energy.hydrolysis_free_energy_J_mol[owner],
            atol=0,
            rtol=0,
        )


def test_live_fuel_changes_native_loading_and_all_consumers_without_hidden_amounts():
    _, state, layout, controls = initial()
    changed = state._replace(
        energy_amount_increment_fmol=np.asarray([[-0.05, -0.08], [0.05, 0.08], [0.05, 0.08]])
    )
    a, b = (model.readouts(s, controls, layout, xp=np) for s in (state, changed))
    assert a.valid and b.valid
    assert np.any(a.network.forward_saturation != b.network.forward_saturation)
    assert np.any(a.network.source_reaction_energy_J_mol != b.network.source_reaction_energy_J_mol)
    assert np.any(a.derivative.pump_cycles != b.derivative.pump_cycles)
    assert np.any(a.derivative.plasma_pump_cycles != b.derivative.plasma_pump_cycles)
    assert np.any(a.derivative.er_pump_transferred != b.derivative.er_pump_transferred)


def test_shared_pool_exchange_preserves_moieties_and_counts_existing_consumers_once():
    _, state, layout, controls = initial(fixtures.probe("mixed"))
    on = model.readouts(state, controls, layout, xp=np)
    off = model.readouts(
        state,
        controls._replace(network_transport=np.zeros_like(controls.network_transport)),
        layout,
        xp=np,
    )
    route = model.route_pool_exchange(on.network.extent_fmol_s, layout, xp=np)
    np.testing.assert_allclose(
        on.derivative.energy_amount_increment_fmol - off.derivative.energy_amount_increment_fmol,
        route.amount_fmol_s,
        rtol=3e-12,
        atol=3e-13,
    )
    for key in route._fields:
        np.testing.assert_allclose(
            getattr(on.exchange, key),
            getattr(off.exchange, key) + getattr(route, key),
            rtol=3e-12,
            atol=3e-13,
        )
    delta = on.derivative.energy_amount_increment_fmol
    np.testing.assert_array_equal(delta[0] + delta[1], 0)
    np.testing.assert_allclose(3 * delta[0] + 2 * delta[1] + delta[2], 0, atol=3e-14, rtol=0)
    np.testing.assert_allclose(
        on.field.chemical_energy_rate_pJ_s - off.field.chemical_energy_rate_pJ_s,
        np.sum(on.network_chemical_power_pJ_s),
        rtol=0,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        on.field.capacitor_energy_rate_pJ_s - off.field.capacitor_energy_rate_pJ_s,
        np.sum(on.network_electrical_power_pJ_s),
        rtol=0,
        atol=1e-10,
    )


@pytest.mark.parametrize("arm", ["empty", "blocked"])
def test_empty_and_blocked_reduce_exactly_to_parent(arm):
    spec, state, layout, controls = initial(fixtures.probe(arm, padded=True))
    old, p = parent.initial_values(schema.base_spec(spec))
    a = parent.readouts(old, model.base_control(controls), p, xp=np)
    b = model.readouts(state, controls, layout, xp=np)
    for actual, expected in zip(model.base_state(b.derivative), a.derivative, strict=True):
        np.testing.assert_array_equal(actual, expected)
    for actual, expected in zip(jax.tree.leaves(b.field), jax.tree.leaves(a.field), strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_numeric_zero_standard_remains_reversible_live_fuel_conversion():
    raw = fixtures.probe()
    for pool in raw["model"]["energy_pools"]:
        pool["delta_g0_J_per_mol"] = 0.0
    for row in raw["model"]["network_transport"]["routes"]:
        row["configuration"]["standard free energy"] = 0.0
    _, state, layout, controls = initial(raw)
    value = model.readouts(state, controls, layout, xp=np)
    assert value.valid and np.any(value.network.source_reaction_energy_J_mol != 0)
    assert np.any(value.network_fuel_power_pJ_s != 0)
    assert np.any(value.network.extent_fmol_s != 0)


def test_opposing_shared_pool_rates_cannot_hide_gross_substrate_turnover():
    raw = fixtures.probe("mixed")
    rows = raw["model"]["network_transport"]["routes"]
    rows[:] = [row for row in rows if row["id"] in ("kcl", "na_atp_synthesis")]
    raw["experiment"]["network_transport_controls"] = [
        group
        for group in raw["experiment"]["network_transport_controls"]
        if group["transporter_id"] in {row["id"] for row in rows}
    ]
    raw["execution"]["network_transport_capacity"] = 2
    _, state, layout, controls = initial(raw)
    rates = model.readouts(state, controls, layout, xp=np).network.extent_fmol_s
    assert rates[0] > 0 and rates[1] < 0
    for row, rate in zip(rows, rates, strict=True):
        row["density_multiplier"] *= 20000 / abs(rate)
    spec, state, layout, controls = initial(raw)
    value = model.readouts(state, controls, layout, xp=np)
    exchange = model.route_pool_exchange(value.network.extent_fmol_s, layout, xp=np)
    np.testing.assert_allclose(exchange.amount_fmol_s, 0, rtol=0, atol=1e-9)
    assert exchange.gross_hydrolysis_fmol_s[0] >= 19999
    assert exchange.gross_synthesis_fmol_s[0] >= 19999
    evidence(
        "opposing-gross",
        dict(
            definition=schema.to_dict(spec),
            signed_route_rates=value.network.extent_fmol_s,
            pool_net=exchange.amount_fmol_s,
            gross_hydrolysis=exchange.gross_hydrolysis_fmol_s,
            gross_synthesis=exchange.gross_synthesis_fmol_s,
            original_minimum_pool_fmol=float(np.min(layout.energy_initial_amount_fmol[:, 0])),
            original_fraction_limit=pools.MAX_INITIAL_POOL_CHANGE_PER_STEP,
        ),
    )
    times = np.asarray(spec.experiment.observation_times)
    with pytest.raises(ConfigError, match="gross ionic/fuel turnover"):
        model.check_steps(spec, np.diff(times), control_values(spec, times[:-1]))


def test_signed_native_regulation_is_retained_and_negative_heat_refuses():
    spec, state, layout, controls = initial()
    t = model.topology(layout)
    # An explicit signed native direct inhibitor; change only influencer tables
    # by binding a declaration, never reverse or clip a computed source rate.
    raw = fixtures.probe()
    for row in raw["model"]["network_transport"]["routes"]:
        row["configuration"].update(
            {"transporter inhibitors": ["ATP&"], "inhibitor Km": [1.0], "inhibitor n": [1.0]}
        )
    with pytest.raises(ConfigError):
        schema.parse(raw)
    rows = [row["configuration"] for row in raw["model"]["network_transport"]["routes"]]
    bound, _ = native.bind(
        rows,
        (*spec.model.species_ids, "ATP", "ADP", "Pi"),
        layout.network_species_valence,
        t.inside,
        t.outside,
        t.compartment_active,
        area_m2=layout.network_area_m2,
        temperature_K=spec.model.temperature_K,
    )
    bad = layout._replace(
        **{
            "network_influencers_" + key: value
            for key, value in bound.influencers._asdict().items()
        }
    )
    value = model.readouts(state, controls, bad, xp=np)
    assert not value.valid and np.all(value.network.regulation < 0)
    assert np.any(value.network_heat_pJ_s < 0)
    assert all(np.isnan(x).all() for x in model.rhs(state, controls, bad, bad.active, xp=np))
    off = controls._replace(network_transport=np.zeros_like(controls.network_transport))
    assert model.readouts(state, off, bad, xp=np).valid


@pytest.mark.parametrize(
    "fault",
    [
        "None",
        "string_None",
        "zero_mismatch",
        "energy_mismatch",
        "stoichiometry",
        "extra_fuel",
        "ionic_conversion",
        "fuel_transfer",
        "foreign_pool",
        "missing_pool",
        "unknown_pool",
        "drive_kind",
        "atp_count",
        "external_work",
        "ignore_exterior",
        "profile",
        "no_transfer",
        "capacity",
        "constants",
        "standards",
        "duplicate_name",
    ],
)
def test_invalid_native_conversion_pool_ownership_or_standards_refuses(fault):
    raw = fixtures.probe()
    block = raw["model"]["network_transport"]
    row, config = block["routes"][0], block["routes"][0]["configuration"]
    if fault in ("None", "string_None", "zero_mismatch", "energy_mismatch"):
        config["standard free energy"] = {
            "None": None,
            "string_None": "None",
            "zero_mismatch": 0.0,
            "energy_mismatch": -30000.0,
        }[fault]
    elif fault == "stoichiometry":
        config["reactant multipliers"][-1] = 2
    elif fault == "extra_fuel":
        config["reactants"].append("Pi")
        config["reactant multipliers"].append(1)
        config["Km reactants"].append(1.0)
    elif fault == "ionic_conversion":
        config["product multipliers"][0] = 2
    elif fault == "fuel_transfer":
        config["transfered into cell"].append("ATP")
    elif fault in ("foreign_pool", "unknown_pool"):
        row["drive"]["pool_id"] = "fuel_cell_1" if fault == "foreign_pool" else "unknown_pool"
    elif fault == "missing_pool":
        del row["drive"]["pool_id"]
    elif fault == "drive_kind":
        row["drive"]["kind"] = "maintained_work_per_cycle@1"
    elif fault == "atp_count":
        row["drive"]["atp_per_cycle"] = 2
    elif fault == "external_work":
        row["drive"]["supplied_energy_J_per_mol"] = 37000
    elif fault == "ignore_exterior":
        config["ignore ECM"] = True
    elif fault == "profile":
        config["apply to"] = ["tissue"]
    elif fault == "no_transfer":
        config["transfered out of cell"] = config["transfered into cell"][:]
    elif fault == "capacity":
        raw["execution"]["network_transport_capacity"] = 0
    elif fault == "constants":
        block["constants"]["gas_constant_J_mol_K"] = 8
    elif fault == "standards":
        block["constants"]["fuel_standard_state_mM"] = 1
    else:
        block["routes"][1]["configuration"]["name"] = config["name"]
    with pytest.raises(ConfigError):
        schema.parse(raw)


@pytest.mark.parametrize("species", [0, 1, 2])
def test_exhaustion_refuses_even_when_all_transport_is_blocked(species):
    _, state, layout, controls = initial(fixtures.probe("blocked"))
    state.energy_amount_increment_fmol[species, 0] = -layout.energy_initial_amount_fmol[species, 0]
    assert not model.control_domain_valid(state, controls, layout, layout.active, xp=np)


@pytest.mark.parametrize("fault", ["heat", "fuel_work", "gross", "padding", "untracked_pool"])
def test_corrupt_work_gross_or_shared_pool_material_ledger_refuses(fault):
    spec, state, _, _ = initial(fixtures.probe(padded=True))
    if fault == "heat":
        state.network_dissipated_energy_pJ[0] = -1e-30
    elif fault == "fuel_work":
        state.network_fuel_work_pJ[0] = 1e-4
    elif fault == "gross":
        state.network_gross_hydrolysis_fmol[0] = 1e-3
    elif fault == "padding":
        state.network_fuel_work_pJ[-1] = 1e-4
    else:
        state.energy_amount_increment_fmol[:, 0] = [-0.001, 0.001, 0.001]
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_observers_expose_finite_fuel_and_both_gross_directions():
    spec, state, layout, _ = initial(fixtures.probe("mixed"))
    history = model.STATE_TYPE(*(x[None] for x in state))
    observed = model.observe_history(np.asarray([0.0]), history, layout, np.asarray([0.0]), spec)
    assert set(vars(observed)) == set(model.OBSERVATION_FIELDS)
    assert np.any(observed.network_gross_hydrolysis_fmol_s > 0)
    assert np.any(observed.network_gross_synthesis_fmol_s > 0)
    assert np.any(observed.network_fuel_power_pJ_s < 0)


def test_numpy_and_cpu_jax46_field_eager_readouts_agree():
    _, state, layout, controls = initial(fixtures.probe(padded=True))
    expected = model.readouts(state, controls, layout, xp=np)
    actual = model.readouts(
        jax.tree.map(jnp.asarray, state),
        jax.tree.map(jnp.asarray, controls),
        jax.tree.map(jnp.asarray, layout),
        xp=jnp,
    )
    assert actual.valid
    for a, b in zip(actual.derivative, expected.derivative, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-12)
    assert abs(float(actual.field.energy_balance_pJ_s)) <= 1e-10
