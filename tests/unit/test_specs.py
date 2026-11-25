import json

import pytest

from cells.definitions.specs import ConfigError, load_spec, parse_spec
from cells.execution.runner import timeline


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), True),
        (("schema_version",), 2),
        (("model", "id"), "unknown"),
        (("model", "units", "time"), "ms"),
        (("model", "population", "count"), 3),
        (("model", "population", "count"), True),
        (("model", "population", "cell_ids"), [-1, 202]),
        (("model", "initial_state", "volume"), [0, 3]),
        (("model", "initial_state", "amount"), [[-1, 0], [0, 2]]),
        (("model", "initial_state", "amount"), [[float("nan"), 0], [0, 2]]),
        (("model", "initial_state", "amount"), [[10**400, 0], [0, 2]]),
        (("model", "parameters", "reaction", "forward_rate"), [float("inf"), 0.1]),
        (("model", "parameters", "reaction", "forward_rate"), ["0.2", 0.1]),
        (("experiment", "end_time"), 0),
        (("experiment", "observation_times"), []),
        (("experiment", "observation_times"), [1.0, 1.0]),
        (("experiment", "observation_times"), [2.0, 1.0]),
        (("experiment", "observation_times"), [13.0]),
        (("experiment", "observation_times"), [False]),
        (("experiment", "source", "kind"), "hidden_input"),
        (("experiment", "contact", "schedule"), []),
        (("experiment", "contact", "schedule"), [{"time": 1.0, "open_fractions": [1.0]}]),
        (("experiment", "contact", "schedule"), [{"time": 0.0, "open_fractions": [-1.0]}]),
        (
            ("experiment", "contact", "schedule"),
            [{"time": 0.0, "open_fractions": [0.0]}, {"time": 0.0, "open_fractions": [1.0]}],
        ),
        (
            ("experiment", "contact", "schedule"),
            [{"time": 0.0, "open_fractions": [0.0]}, {"time": 13.0, "open_fractions": [1.0]}],
        ),
        (("execution", "backend"), "gpu"),
        (("execution", "precision"), "float32"),
        (("execution", "solver"), "euler"),
        (("execution", "dt"), 0),
        (("execution", "dt"), True),
        (("execution", "capacity"), 0),
        (("execution", "capacity"), 1.5),
        (("execution", "jit"), "true"),
        (("execution", "max_steps"), 0),
        (("execution", "max_trace_bytes"), -1),
    ],
)
def test_invalid_definitions(config_data, path, value):
    parse_spec(config_data)  # The control: one change away, the definition is admitted.
    node = config_data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(config_data)


def test_round_trip_and_no_alias(spec):
    assert parse_spec(spec.to_dict()) == spec
    data = spec.to_dict()
    data["model"]["initial_state"]["amount"][0][0] = 99
    assert spec.model.initial_amounts == ((8, 0), (0, 2))
    assert parse_spec(data).fingerprint != spec.fingerprint


@pytest.mark.parametrize("mode", ["missing", "unknown", "wrong_type"])
def test_schema_fields(config_data, mode):
    parse_spec(config_data)
    if mode == "missing":
        del config_data["execution"]["dt"]
    elif mode == "unknown":
        config_data["execution"]["free_memory"] = True
    else:
        config_data["model"] = []
    with pytest.raises(ConfigError):
        parse_spec(config_data)


@pytest.mark.parametrize("raw", ['{"x": 1, "x": 2}', '{"x": NaN}', "{"])
def test_json_rejects_ambiguous_input(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    with pytest.raises(ConfigError):
        load_spec(path)


@pytest.mark.parametrize(
    "mode,guard",
    [
        ("nominal_steps", "max_steps"),
        ("event_steps", "max_steps"),
        ("memory", "max_trace_bytes"),
        ("stability", "maximum exit rate"),
    ],
)
def test_resource_and_solver_guards(config_data, mode, guard):
    assert len(timeline(parse_spec(config_data))) == 243  # 240 steps, two of them split.
    if mode == "nominal_steps":
        config_data["execution"]["max_steps"] = 10
    elif mode == "event_steps":
        config_data["execution"]["max_steps"] = 240
    elif mode == "memory":
        config_data["execution"]["max_trace_bytes"] = 100
    else:
        config_data["model"]["parameters"]["reaction"]["forward_rate"][0] = 30
    with pytest.raises(ConfigError, match=guard):
        timeline(parse_spec(config_data))


def test_load_definition(config_data, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data))
    assert load_spec(path) == parse_spec(config_data)
