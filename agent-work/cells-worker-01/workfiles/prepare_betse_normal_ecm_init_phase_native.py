# ruff: noqa: E501
"""Prepare independent INIT orchestration around unchanged source physics capture.

Text substitutions are exclusive and recorded; AST is compiled, never executed.
"""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02/source")


def main():
    source = PARENT / "validation/betse/betse_normal_ecm_event_mechanics_native.py"
    code = source.read_text()
    changes = []

    def swap(old, new, count=1):
        nonlocal code
        assert code.count(old) == count, (old[:120], code.count(old), count)
        code = code.replace(old, new)
        changes.append(dict(old=old, new=new, count=count))

    def section(start, end, new):
        nonlocal code
        a, b = code.index(start), code.index(end, code.index(start))
        swap(code[a:b], new)

    swap(
        "from validation.betse import betse_normal_ecm_event_join_native_events as event_native",
        "from validation.betse import betse_normal_ecm_init_phase_native_setup as setup_native\nfrom validation.betse.betse_normal_ecm_run_lifecycle_native import clock_profile",
    )
    swap(
        "from validation.betse.betse_normal_ecm_event_join_native import capture, run_dispatch",
        "from validation.betse.betse_normal_ecm_event_join_native import capture",
    )
    swap('    declared = composition["event_inputs"]', "    declared = composition")
    swap(
        "    before_rng = copy.deepcopy(np.random.get_state())",
        "    before_rng = copy.deepcopy(np.random.get_state())\n    before_python_rng = setup_native.random.getstate()",
    )
    swap(
        "    sim.T, parameters.dt = (parameters.T, 0.0)",
        '    sim.T, parameters.dt = (parameters.T, composition["time_profile"]["init_dt_s"])',
    )
    swap(
        "    event_owner = event_native.Owner(ctx, declared)",
        "    setup_owner = setup_native.Owner(ctx, declared)",
    )
    swap(
        "            event_stores=event_native.snapshot(sim),\n            noise_stream=event_native.manifest(event_owner.rng),",
        "            setup_pre=copy.deepcopy(setup_owner.pre),",
    )
    section(
        "    cold_event_stores = event_native.snapshot(sim)",
        '    controls = network.clone(definition["initial_controls"])',
        """    setup_pre = copy.deepcopy(setup_owner.pre)
    # Original mechanics entry tools are supplied conditional owners, as in the
    # common source capture; they are initialized once before finalization.
    mechanical_owner = mechanical.Owner(composition, sim, cells, parameters)
    finalized = setup_owner.finalize()
    source_calendar = clock_profile(composition["time_profile"])
    source_times = source_calendar["source_labels_s"].copy()
    ctx.phase.kind = "INIT"
    parameters._run_sim = False
""",
    )
    swap(
        "    mechanical_owner = None\n    with warnings.catch_warnings(record=True) as caught:",
        "    with warnings.catch_warnings(record=True) as caught:",
    )
    swap(
        '            mechanical_owner = mechanical.Owner(composition, sim, cells, parameters)\n            parameters.t_resample = declared["calendar"]["sample_stride"]',
        '            parameters.t_resample = source_calendar["sample_stride"]',
    )
    section(
        "                event_entry = event_result = reset_return = noise_result = None",
        "                runtime_definition = network.clone(raw)",
        """                calcium_count = len(calcium_rows)
                field_phase = "reset"
                parameters.dt = call["material"]["dt_s"]
                before_reset = values()
                source["resets"](sim, cells, parameters, float(source_times[index]))
                reset_return = values()
                field_phase = "nak"
                nak_result = setup_owner.pump(values)
""",
    )
    swap("                preview, preview_after = event_owner.preview(index)\n", "")
    swap(
        "                    initial=values(),\n                    steps=[network.clone(packet)],",
        "                    initial=before_reset,\n                    steps=[network.clone(packet)],",
    )
    section(
        "                    event_stores=event_native.snapshot(sim),",
        "                ctx.trace = network.new_trace()",
        """                    nak_before=network.clone(nak_result["before"]),
                    source_phase="INIT", legacy_run_sim=False,
                )
""",
    )
    swap(
        "                ctx.trace.update(channel_events=[], channel_initializations=[])",
        '                ctx.trace.update(channel_events=[], channel_initializations=[], source_phase="INIT", legacy_run_sim=False)',
    )
    swap(
        '                observe("initial")\n                observe("reset_flux")',
        """                frames.append(dict(stage="initial",ion_id=None,values=before_reset))
                frames.append(dict(stage="reset_flux",ion_id=None,values=reset_return))""",
    )
    section(
        '                sim.fluxes_mem += np.asarray(\n                    packet["supplied_pump_membrane_flux_mol_m2_s"]',
        '                observe("supplied_pump_flux")',
        """                packet["supplied_pump_membrane_flux_mol_m2_s"] = nak_result["applied_flux"].copy()
                material_before["steps"][0]["supplied_pump_membrane_flux_mol_m2_s"] = nak_result["applied_flux"].copy()
""",
    )
    section(
        '                field_phase = "protein_noise"',
        '                field_phase = "steady_mechanics"',
        "",
    )
    swap(
        '                field_phase = "material_network"\n                sim.update_all_concs(cells, parameters)',
        '                observe("INIT_post_network")\n                field_phase = "material_network"\n                sim.update_all_concs(cells, parameters)',
    )
    section(
        "                            before_events=event_entry,",
        "                            material_candidate=material_candidate,",
        """                            nak=copy.deepcopy(nak_result),
                            reset_return=reset_return,
                            phase_stores_after=setup_native.snapshot(sim),
""",
    )
    section(
        "                        before_events=event_entry,",
        "                        material_candidate=material_candidate,",
        """                        nak=copy.deepcopy(setup_owner.nak_history[-1]) if setup_owner.nak_history else None,
                        reset_return=reset_return,
                        phase_stores_after=setup_native.snapshot(sim),
""",
    )
    section(
        "        cold_event_stores=cold_event_stores,",
        "        source_times_s=source_times,",
        """        setup_pre=setup_pre,
        event_finalization=finalized,
        source_calendar=source_calendar,
        nak_history=setup_owner.nak_history,
        event_fire_calls=0,
        dynamic_noise_calls=0,
        source_phase="INIT",
        legacy_run_sim=False,
        Python_RNG_unchanged=before_python_rng == setup_native.random.getstate(),
""",
    )
    swap(
        '        native_source_sha256=pins["source_sha256"]\n        | json.loads(event_native.PROTOCOL.read_text())["native_source"]["source_sha256"],',
        '        native_source_sha256=pins["source_sha256"],',
    )
    swap(
        '"Supplied pump before ion loop; supplied late flux after ion loop; "',
        '"Actual native NaK before ion loop; no arbitrary late flux; ordinary INIT; "',
    )
    swap(
        "Native event/mechanics production import denied: ",
        "Native INIT production import denied: ",
    )
    # Use the independent native dispatch body, changing only the phase/legacy flag.
    native_dispatch = ast.parse(
        (PARENT / "validation/betse/betse_normal_ecm_event_join_native.py").read_text()
    )
    node = copy.deepcopy(
        next(
            n
            for n in native_dispatch.body
            if isinstance(n, ast.FunctionDef) and n.name == "run_dispatch"
        )
    )
    node.body[1].value.value = "INIT"
    node.body.insert(2, ast.parse("ctx.p._run_sim = False").body[0])
    where = code.index("\ndef evaluate(declared):")
    code = (
        code[:where] + "\n" + ast.unparse(ast.fix_missing_locations(node)) + "\n\n" + code[where:]
    )
    # Removed declarations were observational only; no numerical body is edited.
    for old in (
        "    event_rows, noise_rows = ([], [])\n",
        "    event_owner = None\n",
        "    event_entry = event_result = reset_return = noise_result = None\n",
    ):
        code = code.replace(old, "")
    code = code.replace(
        '"""Actual original event/noise state with steady mechanics before one deferred commit.',
        '"""Independent ordinary INIT orchestration with unchanged full source physics.',
    )
    compile(code, "<prepared INIT native capture>", "exec")
    out = ROOT / "validation/betse/betse_normal_ecm_init_phase_native.py"
    with out.open("x") as stream:
        stream.write("# ruff: noqa: F841\n" + code)
    with (
        ROOT
        / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_init_phase_native_generation_01.json"
    ).open("x") as stream:
        json.dump(
            dict(
                kind="cells.init_native_orchestration_generation@1",
                scientific_execution=False,
                parent_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                substitutions=changes,
            ),
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
