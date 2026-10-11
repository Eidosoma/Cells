import json

import pytest

from cells.core.runner import timeline
from cells.core.specs import ConfigError, load_spec, parse_spec


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), True),
        (("schema_version",), 2),
        (("model", "id"), "unknown"),
        (("model", "units", "time"), "ms"),
        (("model", "population", "count"), 2),
        (("model", "population", "count"), True),
        (("model", "population", "cell_id"), -1),
        (("model", "initial_state", "volume"), 0),
        (("model", "initial_state", "amount"), -1),
        (("model", "initial_state", "amount"), float("nan")),
        (("model", "initial_state", "amount"), 10**400),
        (("model", "parameters", "decay_rate"), float("inf")),
        (("model", "parameters", "decay_rate"), "0.4"),
        (("experiment", "end_time"), 0),
        (("experiment", "observation_times"), []),
        (("experiment", "observation_times"), [1.0, 1.0]),
        (("experiment", "observation_times"), [2.0, 1.0]),
        (("experiment", "observation_times"), [13.0]),
        (("experiment", "observation_times"), [False]),
        (("experiment", "source", "kind"), "hidden_input"),
        (("experiment", "source", "schedule"), []),
        (("experiment", "source", "schedule"), [{"time": 1.0, "rate": 1.0}]),
        (("experiment", "source", "schedule"), [{"time": 0.0, "rate": -1.0}]),
        (
            ("experiment", "source", "schedule"),
            [{"time": 0.0, "rate": 0.0}, {"time": 0.0, "rate": 1.0}],
        ),
        (
            ("experiment", "source", "schedule"),
            [{"time": 0.0, "rate": 0.0}, {"time": 13.0, "rate": 1.0}],
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
    node = config_data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(config_data)


def test_round_trip_and_no_alias(spec):
    assert parse_spec(spec.to_dict()) == spec
    data = spec.to_dict()
    data["model"]["initial_state"]["amount"] = 99
    assert spec.model.initial_amount == 0.2
    assert parse_spec(data).fingerprint != spec.fingerprint


@pytest.mark.parametrize("mode", ["missing", "unknown", "wrong_type"])
def test_schema_fields(config_data, mode):
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


@pytest.mark.parametrize("mode", ["nominal_steps", "event_steps", "memory", "stability"])
def test_resource_and_solver_guards(config_data, mode):
    if mode == "nominal_steps":
        config_data["execution"]["max_steps"] = 10
    elif mode == "event_steps":
        config_data["execution"]["max_steps"] = 240
    elif mode == "memory":
        config_data["execution"]["max_trace_bytes"] = 100
    else:
        config_data["model"]["parameters"]["decay_rate"] = 30
    with pytest.raises(ConfigError):
        timeline(parse_spec(config_data))


def test_load_definition(config_data, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data))
    assert load_spec(path) == parse_spec(config_data)
