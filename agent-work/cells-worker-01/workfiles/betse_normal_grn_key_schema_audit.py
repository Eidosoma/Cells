"""Audit every growth/decay regulator lookup using original AST/string metadata.

No fixture, packet, equation, reference or scientific method is evaluated.
"""

import ast
import hashlib
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/chemistry/networks.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def string(node, values):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return string(node.left, values) + string(node.right, values)
    raise AssertionError(ast.dump(node))


def audit():
    original = ast.parse(PIN.read_text())
    core = next(
        node
        for node in original.body
        if isinstance(node, ast.ClassDef) and node.name == "MasterOfNetworks"
    )
    tissue = next(
        node
        for node in core.body
        if isinstance(node, ast.FunctionDef) and node.name == "tissue_init"
    )
    schema = {}
    for node in ast.walk(tissue):
        if (
            not isinstance(node, ast.Assign)
            or not isinstance(node.value, ast.Call)
            or ast.unparse(node.value.func) != "gad.get"
        ):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "mol"
            ):
                parts = target.attr.split("_")
                if (
                    len(parts) == 3
                    and parts[0] in {"growth", "decay"}
                    and parts[1] in {"activators", "inhibitors"}
                    and parts[2] in {"list", "zone", "Km", "n"}
                ):
                    assert (
                        len(node.value.args) == 2 and ast.literal_eval(node.value.args[1]) is None
                    )
                    schema[target.attr] = dict(
                        key=ast.literal_eval(node.value.args[0]), line=node.lineno, default=None
                    )
    assert len(schema) == 16
    expected = {}
    for phase, prefix in (("growth", ""), ("decay", "decay ")):
        for sign in ("activators", "inhibitors"):
            for field, key in (
                ("list", prefix + sign),
                ("zone", "zone " + prefix + sign),
                ("Km", "Km " + prefix + sign),
                ("n", "n " + prefix + sign),
            ):
                expected[phase + "_" + sign + "_" + field] = key
    assert {field: row["key"] for field, row in schema.items()} == expected
    supported = {value for field, value in expected.items() if not field.endswith("_zone")} | {
        "production rate",
        "decay rate",
        "decay max",
        "scale factor",
        "apply to",
    }
    source = ast.parse((ROOT / "src/cells/processes/betse_normal_grn_source.py").read_text())
    validate = next(
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate"
    )
    allowed = next(
        ast.literal_eval(node.right)
        for node in ast.walk(validate)
        if isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Sub)
        and ast.unparse(node.left) == "set(gad)"
    )
    assert allowed == supported, (allowed - supported, supported - allowed)
    lookups = {}
    for label, path, function in (
        ("validator", "src/cells/processes/betse_normal_grn_source.py", "validate"),
        ("reference", "validation/betse/betse_normal_grn_join_reference.py", "hill"),
    ):
        tree = ast.parse((ROOT / path).read_text())
        method = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function
        )
        expressions = [
            node.slice
            for node in ast.walk(method)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "gad"
            and any(
                isinstance(child, ast.Name) and child.id == "prefix"
                for child in ast.walk(node.slice)
            )
        ]
        assert len(expressions) == 2, (label, len(expressions))
        for phase, prefix in (("growth", ""), ("decay", "decay ")):
            for sign in ("activators", "inhibitors"):
                keys = {string(node, dict(prefix=prefix, sign=sign)) for node in expressions}
                assert keys == {
                    expected[phase + "_" + sign + "_Km"],
                    expected[phase + "_" + sign + "_n"],
                }, (label, phase, sign, keys)
                lookups[label + "/" + phase + "/" + sign] = sorted(keys)
    fixture = ast.parse((ROOT / "validation/betse/betse_normal_grn_join_fixtures.py").read_text())
    fixture_keys = set()
    for node in ast.walk(fixture):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "gad.update":
            assert len(node.args) == 1 and isinstance(node.args[0], ast.Dict)
            fixture_keys |= {ast.literal_eval(key) for key in node.args[0].keys}
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "gad" for target in node.targets
        ):
            for child in ast.walk(node.value):
                if isinstance(child, ast.Dict):
                    fixture_keys |= {ast.literal_eval(key) for key in child.keys}
    assert fixture_keys <= supported, fixture_keys - supported
    for relative in (
        "src/cells/processes/betse_normal_grn_source.py",
        "validation/betse/betse_normal_grn_join_fixtures.py",
        "validation/betse/betse_normal_grn_join_reference.py",
    ):
        text = (ROOT / relative).read_text()
        assert not any(
            typo in text
            for typo in (
                "decay Km activators",
                "decay n activators",
                "decay Km inhibitors",
                "decay n inhibitors",
            )
        ), relative
    return dict(
        kind="cells.native_grn_regulator_key_schema_audit@1",
        native_source=dict(path=str(PIN), sha256=sha(PIN)),
        native_field_lookup_schema=schema,
        all16_regulator_keys_match_original=True,
        allowed_bounded_GAD_keys=sorted(supported),
        fixture_used_GAD_keys=sorted(fixture_keys),
        symbolic_validator_reference_lookup_pairs=lookups,
        zone_scope=(
            "Zone keys omitted and refused in this bounded scope; "
            "original default_zones supplies cell zones"
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_packet_reference_evaluations=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    import json

    result = audit()
    print(
        json.dumps(
            dict(
                native_regulator_keys=len(result["native_field_lookup_schema"]),
                validator_reference_groups=len(result["symbolic_validator_reference_lookup_pairs"]),
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )
