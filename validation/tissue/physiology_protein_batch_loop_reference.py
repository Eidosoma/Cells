"""Independent real RNG tapes, carried full ionic ODEs and decimal ledgers.

No Cells/JAX imports. Both integration tolerances carry their own complete
histories. Stdlib MT19937/Threefry replay supplies real packets rather than
trusting production uniforms. Named-owner component and full-node field/energy
references preserve actual geometry, calendar labels and physical intervals.
"""

from copy import deepcopy
from decimal import Context, Decimal, localcontext

import numpy as np

from validation.tissue import physiology_permeability_schedule_reference as schedules
from validation.tissue import physiology_protein_interval_accounting_reference as accounting
from validation.tissue import physiology_protein_loop_reference as loop
from validation.tissue import physiology_protein_packet_provider_reference as packets
from validation.tissue import physiology_protein_work_view_reference as work


def _plain(component):
    return {
        name: component[name]
        for name in ("protein", "diffusion", "controls", "time_s", "loop_calls")
    } | dict(stream_next_tick=component["stream"]["next_tick"])


def _d(value):
    return Decimal.from_float(float(value))


def _global(
    raw,
    initial_fields,
    fields,
    binding,
    initial,
    current,
    reference_protein,
    first_control,
    last_control,
    valence,
    standard,
    external,
    dissipated,
    clamp,
):
    # Evaluate the state-function difference along a different path: all ionic
    # change with the original protein, then the complete final fixed-ion
    # protein change. This retains all physical ionic stores and their ledgers.
    held = accounting.evaluate(
        raw,
        initial_fields,
        fields,
        binding,
        current["diffusion"]["current_m2_s"],
        reference_protein,
        initial["protein"],
        valence=valence,
        before_control=first_control,
        after_control=last_control,
    )
    shifted = work.evaluate(
        raw,
        fields,
        binding,
        current["diffusion"]["current_m2_s"],
        last_control,
        reference_protein,
        initial["protein"],
        current["protein"],
        valence=valence,
        standard_concentration_mol_m3=standard,
    )
    with localcontext(Context(prec=4096)):
        terms = {key: Decimal(value) for key, value in held["exact_energy_terms"].items()}
        terms["plasma_capacitor_change_pJ"] = _d(held["actual_endpoint_plasma_change_pJ"]) + _d(
            shifted["capacitor_energy_change_pJ"]
        )
        terms.update(
            protein_chemical_change_pJ=_d(shifted["chemical_energy_change_pJ"]),
            protein_external_work_pJ=external,
            protein_dissipated_free_energy_pJ=dissipated,
            protein_clamp_work_pJ=clamp,
        )
        residual = sum(
            (value * (-1 if "work" in name else 1) for name, value in terms.items()), Decimal(0)
        )
        limit = 1e-9 if "chemical_amount_increment" in fields else 2e-8
        return dict(
            exact_energy_terms={name: str(value) for name, value in terms.items()},
            energy_residual_pJ=float(residual),
            physical_energy_limit_pJ=limit,
            energy_valid=bool(abs(residual) <= _d(limit)),
            complete_material_balances=held["balances"],
        )


def integrate(
    raw,
    fields,
    binding,
    source_component,
    charge_reference,
    loops,
    *,
    valence,
    standard_concentration_mol_m3,
    threefry_partitionable,
    padded_outside_capacity,
    refinement=1,
    schedule=None,
):
    if not loops:
        raise ValueError("Require an explicit full-loop history")
    initial, current = deepcopy(source_component), deepcopy(source_component)
    initial_fields, carried = deepcopy(fields), deepcopy(fields)
    external = dissipated = clamp = Decimal(0)
    electrode = [Decimal(0)] * padded_outside_capacity
    endpoints = []
    first_control = loops[0]["intervals"][0]["held_control"]
    for item in loops:
        staged = _plain(current)
        if schedule is not None:
            staged = schedules.stage(schedule, binding, _plain(initial), staged, item["loop_index"])
        source = current | {
            name: staged[name]
            for name in ("protein", "diffusion", "controls", "time_s", "loop_calls")
        }
        owned = packets.provide(binding, source, threefry_partitionable=threefry_partitionable)
        uniforms = None if owned["packet"] is None else owned["packet"]["values"]
        solved = loop.integrate(
            raw,
            carried,
            binding,
            staged,
            charge_reference,
            [dict(prescribed_uniforms=uniforms, intervals=item["intervals"])],
            valence=valence,
            standard_concentration_mol_m3=standard_concentration_mol_m3,
            refinement=refinement,
        )["endpoints"][0]
        previous_protein = source["protein"]
        current = (
            source
            | {
                name: solved["component"][name]
                for name in ("protein", "diffusion", "controls", "time_s", "loop_calls")
            }
            | dict(stream=owned["successor_stream"])
        )
        carried = solved["fields"]
        last_control = item["intervals"][-1]["endpoint_control"]
        first_field = work.fields.evaluate(
            raw,
            carried,
            binding,
            current["diffusion"]["current_m2_s"],
            last_control,
            charge_reference,
            previous_protein,
            valence=valence,
        )
        last_field = work.fields.evaluate(
            raw,
            carried,
            binding,
            current["diffusion"]["current_m2_s"],
            last_control,
            charge_reference,
            current["protein"],
            valence=valence,
        )
        charges = np.asarray(last_field["after"]["electrode_charge_C"]) - np.asarray(
            first_field["after"]["electrode_charge_C"]
        )
        budget = item["budget"]
        with localcontext(Context(prec=4096)):
            external += _d(budget["external_work_pJ"])
            dissipated += _d(budget["dissipated_free_energy_pJ"])
            clamp += _d(solved["work"]["clamp_work_pJ"])
            for i, charge in enumerate(charges):
                electrode[i] += _d(charge)
        global_report = _global(
            raw,
            initial_fields,
            carried,
            binding,
            initial,
            current,
            charge_reference,
            first_control,
            last_control,
            valence,
            standard_concentration_mol_m3,
            external,
            dissipated,
            clamp,
        )
        endpoints.append(
            solved
            | dict(
                component=current,
                packet=owned["packet"],
                successor_stream=owned["successor_stream"],
                global_accounting=global_report,
                ledger=dict(
                    external_work_pJ=str(external),
                    dissipated_free_energy_pJ=str(dissipated),
                    clamp_work_pJ=str(clamp),
                    electrode_charge_C=[str(q) for q in electrode],
                ),
            )
        )
    return dict(
        endpoints=endpoints,
        refinement=refinement,
        independent_RNG_engine=True,
        independently_carried_complete_ionic_states=True,
    )


def report(answer):
    """Portable complete numeric answers without executable solver contexts."""
    return dict(
        refinement=answer["refinement"],
        independent_RNG_engine=answer["independent_RNG_engine"],
        independently_carried_complete_ionic_states=True,
        endpoints=[
            {
                name: item[name]
                for name in (
                    "fields",
                    "state",
                    "component",
                    "potential_V",
                    "work",
                    "evaluations",
                    "packet",
                    "successor_stream",
                    "ledger",
                    "global_accounting",
                )
            }
            for item in answer["endpoints"]
        ],
    )
