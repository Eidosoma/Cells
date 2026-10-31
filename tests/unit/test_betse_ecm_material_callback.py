"""Software contracts for the real material-observer prelude, without a solver run."""

import ast
import copy
import importlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


def observer_block(component_path):
    """Execute the production declaration/validation/callback block in isolation."""
    tree = ast.parse(Path(component_path).read_text())
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "advance"
    )
    start = next(
        i
        for i, node in enumerate(function.body)
        if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "row"
    )
    end = next(
        i
        for i, node in enumerate(function.body)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "before_material is not None"
    )
    return compile(
        ast.Module(body=copy.deepcopy(function.body[start : end + 1]), type_ignores=[]),
        str(component_path),
        "exec",
    )


def minimal_binding(component, packet, controls, scheduled, initial=None):
    """Only array-axis metadata consumed by Drive validation, no physical fixture."""
    s, m = np.asarray(packet["supplied_pump_membrane_flux_mol_m2_s"]).shape
    grid = np.asarray(packet["electric_x_source"]).shape
    axes = SimpleNamespace(ion_ids=tuple(range(s)), membrane_ids=tuple(range(m)))
    geometry = SimpleNamespace(current_binding=axes, geometry=SimpleNamespace(shape=grid))
    drive_binding = SimpleNamespace(
        geometry_binding=geometry, kernel=SimpleNamespace(cluster_open=True)
    )
    declaration = copy.deepcopy(packet)
    # Stale declaration fields must be replaced by the actual previous field.
    declaration["electric_x_source"] = np.full(grid, -999.0).tolist()
    declaration["electric_y_source"] = np.full(grid, 999.0).tolist()
    binding = SimpleNamespace(
        inputs=dict(
            definition={"role": "software-axis-stub"},
            steps=[dict(material=declaration, scheduled_controls=copy.deepcopy(scheduled))],
        ),
        material_binding=drive_binding,
        calcium={"role": "calcium"},
        catalog={"role": "catalog"},
    )
    values = SimpleNamespace(_asdict=lambda: {} if initial is None else initial)
    parent = SimpleNamespace(
        network=SimpleNamespace(
            controls=copy.deepcopy(controls),
            material=SimpleNamespace(values=values),
            network_cache={},
        ),
        clock={"role": "clock"},
    )
    fields = SimpleNamespace(
        environment=SimpleNamespace(
            values=SimpleNamespace(
                electric_x_source=np.asarray(packet["electric_x_source"], np.float64).copy(),
                electric_y_source=np.asarray(packet["electric_y_source"], np.float64).copy(),
            )
        )
    )
    return dict(
        vars(component),
        binding=binding,
        parent=parent,
        fields=fields,
        rate={"present": False, "value": None},
        index=0,
    )


@pytest.mark.parametrize("family", ["calcium", "catalog"])
@pytest.mark.parametrize("scheduled", [False, True])
@pytest.mark.parametrize("array_declaration", [False, True])
def test_incoming_packet_types_values_selection_and_mutation_isolation(
    family, scheduled, array_declaration
):
    component = importlib.import_module("cells.processes.betse_normal_ecm_" + family + "_join")
    packet = dict(
        dt_s=1e-6,
        runtime_temperature_K=300.0,
        junction_block=[0.1, 0.2],
        channel_multiplier=[0.7, 0.8],
        supplied_pump_membrane_flux_mol_m2_s=[[1e-12, 2e-12]],
        supplied_late_membrane_flux_mol_m2_s=[[3e-12, 4e-12]],
        electric_x_source=[[0.125, 0.25], [0.5, 1.0]],
        electric_y_source=[[0.25, 0.5], [1.0, 2.0]],
        velocity_x_m_s=[[0.0, 0.0], [0.0, 0.0]],
        velocity_y_m_s=[[0.0, 0.0], [0.0, 0.0]],
        boundary_mol_m3=[150.0],
    )
    if array_declaration:
        packet = {
            k: np.asarray(v, np.float64) if isinstance(v, list) else v for k, v in packet.items()
        }
    held, scheduled_controls = {"gj_block": [0.3, 0.4]}, {"gj_block": [0.5, 0.6]}
    namespace = minimal_binding(component, packet, held, scheduled_controls if scheduled else None)
    observed = []
    namespace["before_material"] = observed.append
    exec(observer_block(component.__file__), namespace)
    assert len(observed) == 1
    incoming, forcing = observed[0]["steps"][0], namespace["forcing"]
    assert set(incoming) == set(forcing._fields)
    assert incoming["junction_block"] == (scheduled_controls if scheduled else held)["gj_block"]
    assert type(incoming["channel_multiplier"]) is (np.ndarray if array_declaration else list)
    assert type(incoming["supplied_pump_membrane_flux_mol_m2_s"]) is (
        np.ndarray if array_declaration else list
    )
    for name in ("electric_x_source", "electric_y_source"):
        assert isinstance(incoming[name], np.ndarray) and incoming[name].dtype == np.float64
        np.testing.assert_array_equal(incoming[name], packet[name])
    for name, actual in forcing._asdict().items():
        expected = (
            (scheduled_controls if scheduled else held)["gj_block"]
            if name == "junction_block"
            else packet[name]
        )
        np.testing.assert_array_equal(actual, expected)
        if isinstance(actual, np.ndarray):
            assert actual.dtype == np.float64 and not actual.flags.writeable
    prior = copy.deepcopy(namespace["binding"].inputs)
    incoming["channel_multiplier"][0] = -1.0
    incoming["junction_block"][0] = -1.0
    incoming["electric_x_source"][0, 0] = -1.0
    assert forcing.channel_multiplier[0] == 0.7
    assert forcing.junction_block[0] == (0.5 if scheduled else 0.3)
    assert namespace["fields"].environment.values.electric_x_source[0, 0] == 0.125
    np.testing.assert_array_equal(
        namespace["binding"].inputs["steps"][0]["material"]["channel_multiplier"],
        prior["steps"][0]["material"]["channel_multiplier"],
    )


@pytest.mark.parametrize("family", ["calcium", "catalog"])
def test_drive_refusal_precedes_callback(family):
    component = importlib.import_module("cells.processes.betse_normal_ecm_" + family + "_join")
    packet = dict(
        dt_s=1e-6,
        runtime_temperature_K=300.0,
        junction_block=[0.1],
        channel_multiplier=[0.7, 0.8],
        supplied_pump_membrane_flux_mol_m2_s=[[0.0]],
        supplied_late_membrane_flux_mol_m2_s=[[0.0]],
        electric_x_source=[[0.0]],
        electric_y_source=[[0.0]],
        velocity_x_m_s=[[0.0]],
        velocity_y_m_s=[[0.0]],
        boundary_mol_m3=[1.0],
    )
    namespace = minimal_binding(component, packet, {"gj_block": [0.3]}, None)
    observed = []
    namespace["before_material"] = observed.append
    with pytest.raises(ValueError):
        exec(observer_block(component.__file__), namespace)
    assert observed == []
