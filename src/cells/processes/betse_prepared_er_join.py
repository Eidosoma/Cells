"""Explicit prepared ER inputs for the unchanged conditional native update.

This constructor declares a new initial inventory. It does not repair the
literal native constructor, advance time, or rebalance a subsequent state.
Static preparation only; no numerical qualification is implied.
"""

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from decimal import Decimal, localcontext
from types import MappingProxyType, SimpleNamespace

import numpy as np

from cells.processes import betse_endoretic_source as endoretic
from cells.processes import betse_normal_er_join as joined
from cells.processes import betse_normal_ion_join as ions

MODE = "prepared_owned_ER_before_outer_call_channels_primed_v1"
INPUT_KIND = "cells.prepared_owned_ER_recipe@1"


@dataclass(frozen=True, slots=True)
class PreparedPacket:
    mode: str
    binding_identity: str
    source_parent_identity: str
    source_state_identity: str
    recipe: object
    owner_context: object
    initial_temperature_K: float
    cytosol_mM: object
    endoretic_state: endoretic.OwnedState
    requested_voltage_V: object
    ideal_target_voltage_decimal: tuple
    target_charge_density_C_m3: object
    initial_amount_mol: object
    source_initial_amount_mol: object
    identity: str


def _d(value):
    return Decimal.from_float(float(value))


def _require_immutable(value):
    if isinstance(value, np.ndarray):
        if value.flags.writeable or not np.isfinite(value).all():
            raise ValueError("Require immutable finite owned preparation buffers")
    elif is_dataclass(value):
        for field in fields(value):
            _require_immutable(getattr(value, field.name))
    elif isinstance(value, Mapping):
        if not isinstance(value, MappingProxyType):
            raise ValueError("Require immutable preparation mappings")
        for item in value.values():
            _require_immutable(item)
    elif isinstance(value, (list, tuple)):
        if isinstance(value, list):
            raise ValueError("Require immutable preparation sequences")
        for item in value:
            _require_immutable(item)


def _recipe(raw):
    raw = ions.data(raw)
    if (
        type(raw) is not dict
        or set(raw) != {"kind", "mode", "scope", "counterion_id", "target", "provenance"}
        or raw["kind"] != INPUT_KIND
        or raw["mode"] != MODE
        or raw["scope"] not in ("whole_join", "conditional_ER")
        or raw["counterion_id"] not in ("Cl", "P")
        or raw["target"] not in ("neutral", "Ca_thermal_plus", "Ca_thermal_minus")
        or not isinstance(raw["provenance"], str)
        or not raw["provenance"].strip()
    ):
        raise ValueError("Require a complete declared prepared ER recipe")
    if raw["target"] != "neutral" and (
        raw["scope"] != "conditional_ER" or raw["counterion_id"] != "Cl"
    ):
        raise ValueError("Thermal sign probes require an ER-only Cl redistribution")
    return ions.freeze(raw)


def _source_parent(binding, parent):
    if type(binding) is not joined.Binding or type(parent) is not joined.State:
        raise ValueError("Require the typed literal ER source parent")
    _require_immutable(parent)
    if (
        binding.identity != ions.digest(joined.binding_record(binding))
        or joined.bind(binding.pump_binding, ions.data(binding.definition)).identity
        != binding.identity
    ):
        raise ValueError("Changed source binding")
    if (
        parent.binding_identity != binding.identity
        or parent.pump.gated.material.step_index != 0
        or any(parent.channel_calls)
    ):
        raise ValueError("Preparation is only before the first outer call")
    reconstructed = joined.initialize(
        binding,
        parent.pump,
        initial_calcium_rate_proxy_mol_m2_s=parent.calcium_rate_proxy_mol_m2_s,
    )
    if reconstructed.identity != parent.identity:
        raise ValueError("Require the complete unchanged literal constructor return")
    return parent


def parameters(binding, dt_s):
    """The same explicit maintained pools and kinetics used by the old ER join."""
    ib = binding.pump_binding.gated_binding.material_binding
    policy = binding.definition["calcium_handler"]
    return (
        ions.data(policy["maintained"])
        | ions.data(policy["kinetics"])
        | ions.data(policy["endoretic"])
        | dict(
            R=ib.kernel.R_J_mol_K, F=ib.kernel.F_C_mol, tm=ib.kernel.membrane_thickness_m, dt=dt_s
        )
    )


def preparation_inputs(binding, parent, *, recipe, owner_context, initial_temperature_K):
    """Raw conditions for an independent preparer, before any prepared output."""
    _source_parent(binding, parent)
    ib = binding.pump_binding.gated_binding.material_binding
    vb = binding.pump_binding.gated_binding.voltage_binding
    return ions.freeze(
        dict(
            kind="cells.prepared_owned_ER_reference_inputs@1",
            binding_identity=binding.identity,
            source_parent_identity=parent.identity,
            source_state_identity=parent.pump.gated.material.identity,
            ion_ids=ib.ion_ids,
            cell_ids=ib.cell_ids,
            valence=ib.kernel.valence,
            moving_indices=ib.kernel.moving,
            cytosol_mM=parent.pump.gated.material.values.cell_mol_m3,
            cell_volume_m3=ib.kernel.cell_volume_m3,
            cell_area_m2=vb.current_binding.kernel.cell_area_m2,
            capacitance_F_m2=vb.kernel.capacitance_F_m2,
            recipe=_recipe(recipe),
            owner_context=endoretic.context(ions.data(owner_context), len(ib.cell_ids)),
            initial_temperature_K=initial_temperature_K,
            parameters=parameters(binding, 0.0),
            conditioned_before_preparation=True,
        )
    )


def prepare(binding, parent, *, recipe, owner_context, initial_temperature_K):
    """Solve one initial counterion row, then derive and prime all owned fields."""
    before = preparation_inputs(
        binding,
        parent,
        recipe=recipe,
        owner_context=owner_context,
        initial_temperature_K=initial_temperature_K,
    )
    if (
        type(initial_temperature_K) not in (int, float)
        or not math.isfinite(initial_temperature_K)
        or initial_temperature_K <= 0
    ):
        raise ValueError("Require a positive declared initial temperature")
    ib = binding.pump_binding.gated_binding.material_binding
    recipe, owners = before["recipe"], before["owner_context"]
    counter = recipe["counterion_id"]
    if counter not in ib.ion_ids or ib.kernel.valence[ib.ion_ids.index(counter)] != -1:
        raise ValueError("Require an explicit native negative counterion role")
    k = ib.ion_ids.index(counter)
    if counter == "P" and k in ib.kernel.moving:
        raise ValueError("The P allocation control requires the existing stationary anion")
    for row in owners.values():
        if row["contains_IP3"] and np.any(row["IP3_mM"] < 0):
            raise ValueError("Prepared channel inputs require nonnegative IP3")
    cytosol = np.array(before["cytosol_mM"], copy=True)
    fields = {
        key: np.array(value, copy=True) if isinstance(value, np.ndarray) else value
        for key, value in parent.endoretic_state.fields.items()
    }
    cc_er = fields["cc_er"]
    if np.any(cytosol <= 0) or np.any(cc_er <= 0):
        raise ValueError("Preparation requires strictly positive complete inventories")
    targets, ideal_targets, densities = [], [], []
    with localcontext() as ctx:
        ctx.prec = 90
        R, F, T = (
            _d(before["parameters"]["R"]),
            _d(before["parameters"]["F"]),
            _d(initial_temperature_K),
        )
        target = Decimal(0) if recipe["target"] == "neutral" else R * T / (2 * F)
        if recipe["target"] == "Ca_thermal_minus":
            target = -target
        for j in range(len(ib.cell_ids)):
            volume, area = _d(fields["er_vol"][j]), _d(fields["er_sa"][j])
            cm = _d(fields["cm_er"])
            rho = cm * area * target / volume
            other = sum(
                (
                    _d(ib.kernel.valence[i]) * _d(cc_er[i, j])
                    for i in range(len(ib.ion_ids))
                    if i != k
                ),
                Decimal(0),
            )
            solved = (rho / F - other) / _d(ib.kernel.valence[k])
            cc_er[k, j] = float(solved)
            if recipe["target"] != "neutral":
                cytosol[k, j] = float(
                    _d(cytosol[k, j]) + volume / _d(ib.kernel.cell_volume_m3[j]) * rho / F
                )
            targets.append(float(target))
            ideal_targets.append(str(target))
            densities.append(float(rho))
    if (
        not np.isfinite(cc_er).all()
        or not np.isfinite(cytosol).all()
        or np.any(cc_er <= 0)
        or np.any(cytosol <= 0)
    ):
        raise ValueError("Declared counterion equation produced a nonpositive inventory")
    sim = SimpleNamespace(
        cc_er=cc_er,
        cc_cells=cytosol,
        cdl=len(ib.cell_ids),
        iCa=ib.ion_ids.index("Ca"),
        **endoretic._owners(owners),
    )
    er = object.__new__(endoretic._LiteralEndoRetic)
    for key, value in fields.items():
        if key != "cc_er":
            setattr(er, key, value)
    p = SimpleNamespace(**parameters(binding, 0.0))
    er.get_v(sim, p)
    er.channels(sim, SimpleNamespace(), p)
    complete = {
        key: copy.deepcopy(sim.cc_er if key == "cc_er" else getattr(er, key))
        for key in endoretic.FIELDS
    }
    owned = endoretic.state(binding.identity, ib.ion_ids, ib.cell_ids, complete)
    amounts = cytosol * ib.kernel.cell_volume_m3 + owned.fields["cc_er"] * owned.fields["er_vol"]
    initial = (
        before["cytosol_mM"] * ib.kernel.cell_volume_m3
        + parent.endoretic_state.fields["cc_er"] * parent.endoretic_state.fields["er_vol"]
    )
    result = PreparedPacket(
        MODE,
        binding.identity,
        parent.identity,
        parent.pump.gated.material.identity,
        recipe,
        owners,
        float(initial_temperature_K),
        ions.freeze(cytosol),
        owned,
        ions.freeze(np.asarray(targets, np.float64)),
        tuple(ideal_targets),
        ions.freeze(np.asarray(densities, np.float64)),
        ions.freeze(amounts),
        ions.freeze(initial),
        "",
    )
    return replace(result, identity=ions.digest(result))


def validate(binding, parent, packet):
    _require_immutable(packet)
    if type(packet) is not PreparedPacket or packet.identity != ions.digest(
        replace(packet, identity="")
    ):
        raise ValueError("Changed or unsealed prepared ER packet")
    expected = prepare(
        binding,
        parent,
        recipe=packet.recipe,
        owner_context=packet.owner_context,
        initial_temperature_K=packet.initial_temperature_K,
    )
    if packet.identity != expected.identity:
        raise ValueError("Prepared ER packet disagrees with its source parent or recipe")
    return packet


def attach(binding, parent, packet):
    """Reconstruct the real joined State identity; never retain an old identity."""
    validate(binding, parent, packet)
    if packet.recipe["scope"] != "whole_join" or packet.recipe["target"] != "neutral":
        raise ValueError("Nonzero sign probes have only conditional ER ownership")
    if not np.array_equal(packet.cytosol_mM, parent.pump.gated.material.values.cell_mol_m3):
        raise ValueError("Whole-join neutral preparation must preserve the complete parent")
    return joined._state(
        binding,
        parent.pump,
        parent.channel_caches,
        parent.channel_calls,
        parent.initialization,
        parent.calcium_rate_proxy_mol_m2_s,
        packet.endoretic_state,
    )


def conditional_inputs(binding, parent, packet, *, dt_s):
    """A complete ER-only prestate for the separately labelled sign probes."""
    validate(binding, parent, packet)
    if not math.isfinite(dt_s) or dt_s <= 0:
        raise ValueError("Require a positive explicit ER step")
    ib = binding.pump_binding.gated_binding.material_binding
    return ions.freeze(
        dict(
            binding_identity=binding.identity,
            er_state=packet.endoretic_state,
            cytosol_mM=packet.cytosol_mM,
            cell_volume_m3=ib.kernel.cell_volume_m3,
            moving_indices=ib.kernel.moving,
            valence=ib.kernel.valence,
            runtime_temperature_K=packet.initial_temperature_K,
            parameters=parameters(binding, dt_s),
            owner_context=packet.owner_context,
            conditioned_before_model_endoretic=True,
            supplied_prepared_state=True,
            native_constructor_parity=False,
        )
    )
