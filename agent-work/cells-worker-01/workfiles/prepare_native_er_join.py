# ruff: noqa: E501
"""Generate a new ER-owned join from the frozen CaATP architecture, statically."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")


def main():
    source = (ROOT / "src/cells/processes/betse_normal_calcium_join.py").read_text()

    def change(old, new, count=1):
        nonlocal source
        assert source.count(old) == count, (old, source.count(old), count)
        source = source.replace(old, new)

    change(
        "from cells.core.errors import NumericalError",
        "from cells.core.errors import NumericalError\nfrom cells.processes import betse_endoretic_source as endoretic",
    )
    change(
        "betse_normal_rectangular_bath_calcium_join_v1_5_0@1",
        "betse_normal_rectangular_bath_endoretic_join_v1_5_0@1",
    )
    change("cells.betse_normal_calcium_join_inputs@1", "cells.betse_normal_er_join_inputs@1")
    change(
        "    initialization: object\n    identity: str",
        "    initialization: object\n    endoretic_state: endoretic.OwnedState\n    identity: str",
    )
    change(
        '    if "Ca" not in ib.ion_ids:\n',
        '    if "Ca" not in ib.ion_ids:\n        raise MissingCoupledState("ER requires an explicit live calcium ion row")\n',
    )
    change(
        '{"Ca_dyn", "maintained", "kinetics", "provenance"}',
        '{"Ca_dyn", "maintained", "kinetics", "provenance", "endoretic"}',
    )
    change('policy["Ca_dyn"] != 0', 'policy["Ca_dyn"] != 1')
    change(
        '"ER/buffer handling requires separate complete owned state; "\n                "Ca_dyn must be explicit0"',
        '"This law requires explicit Ca_dyn1 and complete owned ER state"',
    )
    insertion = """        er_parameters = policy["endoretic"]
        if not isinstance(er_parameters, dict) or set(er_parameters) != set(endoretic.PARAMETERS):
            raise MissingCoupledState("Require all source ER channel and SERCA parameters")
        for name, value in er_parameters.items():
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (name not in ("serca_max", "max_er") and value <= 0):
                raise ValueError("Invalid explicit ER parameter: " + name)
"""
    change(
        '    result = Binding(pump_binding, ions.freeze(raw), "")',
        insertion + '    result = Binding(pump_binding, ions.freeze(raw), "")',
    )
    change(
        "def _state(binding, parent, caches, calls, initialization, calcium_rate_cache):",
        "def _state(binding, parent, caches, calls, initialization, calcium_rate_cache, endoretic_state):",
    )
    change(
        '        ions.freeze(initialization),\n        "",',
        '        ions.freeze(initialization),\n        endoretic_state,\n        "",',
    )
    change(
        "    return _state(binding, parent, caches, [0] * len(caches), caches, calcium_cache)",
        """    ib = binding.pump_binding.gated_binding.material_binding
    vb = binding.pump_binding.gated_binding.voltage_binding
    er_state = endoretic.initialize(binding.identity, ib.ion_ids, ib.cell_ids,
        parent.gated.material.values.cell_mol_m3, ib.kernel.cell_volume_m3,
        vb.current_binding.kernel.cell_area_m2, ib.kernel.valence, vb.kernel.capacitance_F_m2)
    return _state(binding, parent, caches, [0] * len(caches), caches, calcium_cache, er_state)""",
    )
    change(
        "def material_step(binding, parent, forcing, live_pump, live, live_calcium, *, before_calcium=None):",
        "def material_step(binding, parent, forcing, live_pump, live, live_calcium, *, live_er_context, before_calcium=None, before_endoretic=None):",
    )
    change(
        "                parent.calcium_rate_proxy_mol_m2_s,\n            ).identity",
        "                parent.calcium_rate_proxy_mol_m2_s,\n                parent.endoretic_state,\n            ).identity",
    )
    change(
        "                    Ca_dyn=0,\n                    ER_executed=False,",
        "                    Ca_dyn=1,\n                    ER_executed=True,",
    )
    er_call = """                er_parameters = dict(parameters) | dict(policy["endoretic"]) | dict(
                    tm=ib.kernel.membrane_thickness_m, dt=forcing.dt_s)
                er_context = endoretic.context(ions.data(live_er_context), len(ib.cell_ids))
                before_er = ions.freeze(dict(
                    binding_identity=binding.identity, er_state=parent.endoretic_state,
                    cytosol_mM=cell.copy(), membrane_mM=membrane.copy(),
                    cell_volume_m3=ib.kernel.cell_volume_m3, moving_indices=ib.kernel.moving,
                    valence=ib.kernel.valence, runtime_temperature_K=forcing.runtime_temperature_K,
                    parameters=er_parameters, owner_context=er_context,
                    conditioned_before_model_endoretic=True))
                if before_endoretic is not None:
                    before_endoretic(before_er)
                er_trial = endoretic.step(parent.endoretic_state,
                    binding_identity=binding.identity, cytosol_mM=cell,
                    cell_volume_m3=ib.kernel.cell_volume_m3, moving_indices=ib.kernel.moving,
                    valence=ib.kernel.valence, runtime_temperature_K=forcing.runtime_temperature_K,
                    parameters=er_parameters, owner_context=er_context)
                cell[:] = er_trial.cytosol_after_mM
                calcium_phase["endoretic"] = er_trial
                calcium_phase["values_after"] = ions.data(_values(arrays))
                if not er_trial.source_completed or not er_trial.finite:
                    observe("calcium_handler_failure", i)
                    raise ValueError("Raw EndoRetic update refused or returned nonfinite fields")
"""
    change(
        '                observe("calcium_handler", i)',
        er_call + '                observe("calcium_handler", i)',
    )
    change(
        '            calcium_phase["rate_after"],\n        )',
        '            calcium_phase["rate_after"],\n            calcium_phase["endoretic"].candidate,\n        )',
    )
    change(
        "    before_calcium=None,\n    boundary_V,",
        "    before_calcium=None,\n    before_endoretic=None,\n    live_er_context,\n    boundary_V,",
    )
    change(
        "            binding, parent, forcing, live_pump, live, live_calcium, before_calcium=before_calcium",
        "            binding, parent, forcing, live_pump, live, live_calcium, live_er_context=live_er_context, before_calcium=before_calcium, before_endoretic=before_endoretic",
    )
    change(
        "            material.candidate.calcium_rate_proxy_mol_m2_s,\n        )",
        "            material.candidate.calcium_rate_proxy_mol_m2_s,\n            material.candidate.endoretic_state,\n        )",
    )
    source = source.replace(
        "before late channels/deferred commit. ER/buffer state is a separate dependency.",
        "before literal owned EndoRetic and late channels/deferred commit. Explicit binding-buffer chemistry is separate.",
    )
    with (ROOT / "src/cells/processes/betse_normal_er_join.py").open("x") as stream:
        stream.write(source)


if __name__ == "__main__":
    main()
