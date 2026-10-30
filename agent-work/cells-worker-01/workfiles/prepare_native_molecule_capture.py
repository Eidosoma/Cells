"""Extend only the separate native capture boundary and observation fields."""

# ruff: noqa: E501 -- captured source templates are formatted in their outputs.

from pathlib import Path

base = Path("validation/betse")
for suffix in ("native_helpers", "native"):
    text = (base / ("betse_normal_network_join_" + suffix + ".py")).read_text()
    text = text.replace("betse_normal_network_join", "betse_normal_molecule_join")
    if suffix == "native_helpers":
        needle = """        source["stb"],
    )"""
        assert text.count(needle) == 1
        text = text.replace(
            needle,
            """        source["stb"],
        ion_ids=definition["ion_ids"],
        dynamic_value=ns["DynamicValue"],
        dynamic_dict=ns["DynamicValueDict"],
    )""",
            1,
        )
        needle = """            values_before=material_native.values(actual),
            controls_before=dict("""
        assert text.count(needle) == 1
        text = text.replace(
            needle,
            """            values_before=material_native.values(actual),
            molecule_states_before=network_native.snapshot(net.molecules),
            controls_before=dict(""",
            1,
        )
        text = text.replace(
            'observe("network_chemistry_empty", None, actual)',
            'observe("network_molecule_chemistry", None, actual)',
        )
        text = text.replace(
            "empty_chemistry_run_loop_executed=True", "configured_chemistry_run_loop_completed=True"
        )
        text = text.replace(
            "chemical_rhs_evaluated=bool(net.reactions) and net.reaction_rates is not None,",
            'chemical_rhs_evaluated=any(row["stage"] == "rhs_ready" for row in feedback["molecule_frames"]),',
        )
        needle = """                chemical_commit_completed=bool(net.reactions) and feedback["source_completed"],"""
        assert text.count(needle) == 1
        text = text.replace(
            needle,
            """                chemical_commit_completed=feedback["source_completed"],
                executed_chemistry=any(row["stage"] == "rhs_ready" for row in feedback["molecule_frames"])
                    and (bool(definition["network"]["reactions"]) or any(row["growth"]["enabled"] for row in definition["network"]["molecules"])),
                molecular_transports_completed=sum(row["stage"] == "transport_after" for row in feedback["molecule_frames"]),
                molecule_states_after=network_native.snapshot(net.molecules),""",
            1,
        )
    else:
        needle = """    network_cache = None"""
        assert text.count(needle) == 1
        text = text.replace(
            needle,
            """    network_cache = channel_helpers.network_native.initial_cache(inputs["channel_definition"]["network"])""",
            1,
        )
        text = text.replace(
            "source_parameters=vars(parameters),",
            'source_parameters={key:value for key,value in vars(parameters).items() if key != "_mover_observe"},',
            1,
        )
    output = base / ("betse_normal_molecule_join_" + suffix + ".py")
    with output.open("x") as stream:
        stream.write(text)
print("Created separate two-file native capture; no source/numeric execution")
