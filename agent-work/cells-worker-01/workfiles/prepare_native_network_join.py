# ruff: noqa: E501
"""Prepare a new endogenous-feedback join; leave every frozen prefix unchanged."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")


def main():
    source = (ROOT / "src/cells/processes/betse_normal_calcium_join.py").read_text()

    def change(old, new, count=1):
        nonlocal source
        assert source.count(old) == count, (old, source.count(old))
        source = source.replace(old, new)

    change(
        "from cells.core.errors import NumericalError",
        "from cells.core.errors import NumericalError\nfrom cells.processes import betse_normal_network_join_source as network_source",
    )
    change(
        "betse_normal_rectangular_bath_calcium_join_v1_5_0@1",
        "betse_normal_native_network_feedback_v1_5_0@1",
    )
    change("cells.betse_normal_calcium_join_inputs@1", "cells.betse_normal_network_join_inputs@1")
    change(
        '{"kind", "provenance", "channels", "calcium_handler"}',
        '{"kind", "provenance", "channels", "calcium_handler", "network"}',
    )
    change(
        '    result = Binding(pump_binding, ions.freeze(raw), "")',
        """    network_source.validate(raw["network"], ib,
        pump_binding.gated_binding.voltage_binding.current_binding,
        pump_binding.gated_binding.voltage_binding.kernel.configured_temperature_K)
    result = Binding(pump_binding, ions.freeze(raw), "")""",
    )
    change(
        "    initialization: object\n    identity: str",
        "    initialization: object\n    network_controls: object\n    network_cache: object\n    identity: str",
    )
    change(
        "    calcium_handler: object\n    channel_phases: tuple",
        "    calcium_handler: object\n    network_feedback: object\n    channel_phases: tuple",
    )
    change(
        "def _state(binding, parent, caches, calls, initialization, calcium_rate_cache):",
        "def _state(binding, parent, caches, calls, initialization, calcium_rate_cache, network_controls, network_cache):",
    )
    change(
        '        ions.freeze(initialization),\n        "",',
        '        ions.freeze(initialization),\n        ions.freeze(network_controls),\n        ions.freeze(network_cache),\n        "",',
    )
    change(
        "    return _state(binding, parent, caches, [0] * len(caches), caches, calcium_cache)",
        '    return _state(binding, parent, caches, [0] * len(caches), caches, calcium_cache,\n        network_source.controls(ions.data(binding.definition["network"]["initial_controls"]),len(parent.rate_proxy_mol_m2_s)), None)',
    )
    change(
        "def material_step(binding, parent, forcing, live_pump, live, live_calcium, *, before_calcium=None):",
        "def material_step(binding, parent, forcing, live_pump, live, live_calcium, *, extra_charge_C_m3, extra_current_A_m2, scheduled_controls=None, before_calcium=None, before_network=None):",
    )
    change(
        "    phases = []\n    network = {}", "    phases = []\n    network = {}\n    feedback = {}"
    )
    change(
        "                parent.calcium_rate_proxy_mol_m2_s,\n            ).identity",
        "                parent.calcium_rate_proxy_mol_m2_s,\n                parent.network_controls, parent.network_cache,\n            ).identity",
    )
    change(
        "        ib = binding.pump_binding.gated_binding.material_binding\n        caches, calls",
        """        ib = binding.pump_binding.gated_binding.material_binding
        effective_controls = network_source.controls(
            ions.data(parent.network_controls if scheduled_controls is None else scheduled_controls), len(ib.membrane_ids))
        if not np.array_equal(forcing.junction_block,effective_controls["gj_block"]) or not np.array_equal(live_pump.block,effective_controls["NaKATP_block"]):
            raise ValueError("Effective native forcing must use the owned or explicitly scheduled controls")
        caches, calls""",
    )
    change(
        '            observe("network_clear")',
        """            core, sim, geometry, p, phase = network_source.prepare(
                arrays, ion_ids=ib.ion_ids,
                parameters=dict(runtime_temperature_K=forcing.runtime_temperature_K,
                    R=ib.kernel.R_J_mol_K,F=ib.kernel.F_C_mol,dt_s=forcing.dt_s,
                    valence=ib.kernel.valence,substances_affect_charge=live.substances_affect_charge,
                    incoming_extra_charge=extra_charge_C_m3,incoming_extra_current=extra_current_A_m2),
                definition=binding.definition["network"],incoming_controls=effective_controls,
                incoming_cache=parent.network_cache,phase_kind=live.phase_kind)
            extra = core.extra_J_mem
            writes=[]
            core._observe_control=lambda name,value,actual: writes.append(ions.freeze(dict(
                rule_id=name,target=core.modulators[name].target_label,value=np.array(value,copy=True),
                gj_block=np.array(actual.gj_block,copy=True),NaKATP_block=np.array(actual.NaKATP_block,copy=True))))
            observe("network_clear")""",
    )
    change(
        "            before_network = _values(arrays)",
        "            network_values_before = _values(arrays)",
    )
    change(
        "                    values_before=before_network,",
        "                    values_before=network_values_before,",
    )
    marker = """                # Empty network reaction system still publishes alias-preserving
                # bulk + 0*dt and energy_charge=0, then conditional replacement.
                for i in range(len(cell)):
                    cell[i] = cell[i] + 0.0 * forcing.dt_s
"""
    assert source.count(marker) == 1
    code = """                feedback.update(values_before=ions.data(_values(arrays)),
                    controls_before=effective_controls,cache_before=parent.network_cache,
                    scheduled_control_outputs_supplied=scheduled_controls is not None,
                    definition=binding.definition["network"],runtime_temperature_K=forcing.runtime_temperature_K,
                    F=ib.kernel.F_C_mol,R=ib.kernel.R_J_mol_K,dt_s=forcing.dt_s,
                    incoming_channel_current_A_m2=extra.copy(),phase_kind=live.phase_kind,
                    conditioned_before_model_network=True,executed_chemistry=False,
                    control_writes=writes,source_completed=False)
                if before_network is not None:
                    before_network(ions.freeze(feedback))
                try:
                    core.run_loop_modulators(sim,geometry,p)
                    observe("network_modulators")
                    core.run_loop(phase,0.0)
                    observe("network_chemistry_empty")
                    feedback.update(source_completed=True,empty_chemistry_run_loop_executed=True)
                finally:
                    feedback.update(cache_after=network_source.cache(core),values_after=ions.data(_values(arrays)),
                        controls_after=dict(gj_block=np.array(sim.gj_block,copy=True),NaKATP_block=np.array(sim.NaKATP_block,copy=True)))
                feedback["controls_after"] = network_source.controls(ions.data(feedback["controls_after"]),len(vm))
"""
    source = source.replace(marker, code)
    change(
        '            calcium_phase["rate_after"],\n        )',
        '            calcium_phase["rate_after"],\n            feedback["controls_after"],feedback["cache_after"],\n        )',
    )
    change(
        "            ions.freeze(calcium_phase),\n            tuple(phases),",
        "            ions.freeze(calcium_phase),\n            ions.freeze(feedback),\n            tuple(phases),",
    )
    change(
        "network=ions.freeze(dict(network, calcium_handler=calcium_phase)),",
        "network=ions.freeze(dict(network, calcium_handler=calcium_phase, network_feedback=feedback)),",
    )
    change(
        "    before_calcium=None,\n    boundary_V,",
        "    before_calcium=None,\n    before_network=None,\n    scheduled_controls=None,\n    boundary_V,",
    )
    change(
        "            binding, parent, forcing, live_pump, live, live_calcium, before_calcium=before_calcium",
        "            binding, parent, forcing, live_pump, live, live_calcium, extra_charge_C_m3=extra_charge_C_m3, extra_current_A_m2=extra_current_A_m2, scheduled_controls=scheduled_controls, before_calcium=before_calcium, before_network=before_network",
    )
    change(
        "            material.candidate.calcium_rate_proxy_mol_m2_s,\n        )",
        "            material.candidate.calcium_rate_proxy_mol_m2_s,\n            material.candidate.network_controls,material.candidate.network_cache,\n        )",
    )
    source = source.replace(
        "Rectangular native no-ECM normal join with maintained-pool CaATP.",
        "Rectangular normal join with endogenous native network feedback.",
    )
    with (ROOT / "src/cells/processes/betse_normal_network_join.py").open("x") as stream:
        stream.write(source)


if __name__ == "__main__":
    main()
