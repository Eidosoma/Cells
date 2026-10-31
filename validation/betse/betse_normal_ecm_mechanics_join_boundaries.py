"""Pure source-time extraction from the complete reached native ECM history."""

from copy import deepcopy

FIELD_STAGE = "normal_full_after_handlers_before_deferred_material_voltage"


def pressure(inputs, index):
    drive = inputs["pressure_drives"][index]
    return [float(a) + float(b) for a, b in zip(drive["P_mod_Pa"], drive["P_base_Pa"], strict=True)]


def native_inputs(inputs, captured):
    declaration = inputs["mechanics_definition"]
    geometry = declaration["geometry"]
    primary_ids = inputs["field_inputs"]["definition"]["environment_geometry_definition"][
        "current_definition"
    ]["ions"]["ids"]
    prior = captured.get("bootstrap")
    steps = []
    for index, row in enumerate(captured["history"]):
        network = row.get("network") or {}
        if not network.get("source_completed") or not prior or not prior.get("voltage"):
            break
        current, voltage = prior["current"]["values"], prior["voltage"]["values"]
        actual = network["values_after"]
        molecules = network["cache_after"]["wire"]["molecule_fields"]
        names = list(molecules)
        steps.append(
            dict(
                receipt=dict(
                    stage=FIELD_STAGE,
                    geometry_epoch=declaration["provenance"]["geometry_epoch"],
                    cell_ids=geometry["cell_ids"],
                    environment_ids=geometry["environment_ids"],
                    source_step=index,
                    deferred_material_voltage_commit_done=False,
                ),
                clock_s=inputs["clocks_s"][index],
                dt_s=declaration["parameters"]["dt_s"],
                temperature_K=inputs["field_inputs"]["steps"][index]["material"][
                    "runtime_temperature_K"
                ],
                pressure_Pa=pressure(inputs, index),
                electric_field_V_m=[
                    list(values) for values in zip(*voltage["cell_field_xy_V_m"], strict=True)
                ],
                current_density_A_m2=[
                    list(values) for values in zip(*current["cell_current_xy_A_m2"], strict=True)
                ],
                charge_density_C_m3=deepcopy(current["charge_density_C_m3"]),
                conductivity_S_m=deepcopy(captured["initializer_cache"]["sigma_S_m"]),
                primary_ids=primary_ids,
                primary_cell_mM=deepcopy(actual["cell_mol_m3"]),
                primary_env_mM=deepcopy(actual["environment_mol_m3"]),
                molecule_ids=[],
                molecule_cell_mM=[],
                molecule_env_mM=[],
                grn_ids=names,
                grn_cell_mM=[deepcopy(molecules[name]["c_cells"]) for name in names],
                grn_env_mM=[deepcopy(molecules[name]["c_env"]) for name in names],
                sample=False,
            )
        )
        prior = row.get("field")
    return dict(definition=declaration, initial=inputs["mechanics_initial"], steps=steps)


def assert_identical(actual, expected):
    """Complete boundary input identity includes signed binary64 zeros."""
    import struct

    if isinstance(actual, dict) or isinstance(expected, dict):
        assert (
            isinstance(actual, dict)
            and isinstance(expected, dict)
            and actual.keys() == expected.keys()
        )
        for key in actual:
            assert_identical(actual[key], expected[key])
    elif isinstance(actual, (list, tuple)) or isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected, strict=True):
            assert_identical(a, b)
    elif type(actual) in (int, float) and type(expected) in (int, float):
        assert struct.pack(">d", float(actual)) == struct.pack(">d", float(expected))
    else:
        assert type(actual) is type(expected) and actual == expected
