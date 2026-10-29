"""Authenticated native electroflux unit cases, without Cells/JAX imports."""

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def independent():
    bad = [name for name in sys.modules if name == "cells" or name.startswith(("cells.", "jax"))]
    assert not bad, bad
    return bad


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    before = independent()
    import numpy as np

    root = Path(__file__).resolve().parents[2]
    protocol = json.loads(
        (root / "validation/topology/tissue_profile_preparation_protocol.json").read_text()
    )
    source = protocol["native_units"]
    path = Path(source["checkout"]) / "betse/science/sim_toolbox.py"
    installed = Path(source["installed_package"]) / "science/sim_toolbox.py"
    assert sha(path) == sha(installed) == source["source_sha256"]["betse/science/sim_toolbox.py"]
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "electroflux")
    assert (
        hashlib.sha256(ast.dump(fn, include_attributes=False).encode()).hexdigest()
        == source["electroflux_ast_sha256"]
    )
    namespace = {"np": np}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), namespace)
    (args.output / "electroflux_source.py").write_text(ast.unparse(fn) + "\n")
    rows = []
    for row in protocol["unit_cases"]:
        data = dict(row)

        def array(key, data=data):
            return np.asarray([data[key]], dtype=np.float64)

        result = namespace["electroflux"](
            array("co_mM"),
            array("ci_mM"),
            array("D_m2_s"),
            array("thickness_m"),
            array("valence"),
            array("voltage_V"),
            data["temperature_K"],
            SimpleNamespace(
                F=source["common_constants"]["F_C_mol"], R=source["common_constants"]["R_J_mol_K"]
            ),
        )
        assert result.shape == (1,) and np.isfinite(result).all()
        rows.append(dict(inputs=data, native_inward_mol_m2_s=float(result[0])))
    report = dict(
        status="passed",
        before_imports=before,
        after_capture_imports=independent(),
        cells_imported=False,
        jax_imported=False,
        source_file=str(path),
        source_sha256=sha(path),
        installed_source_sha256=sha(installed),
        electroflux_ast_sha256=source["electroflux_ast_sha256"],
        common_constants=source["common_constants"],
        rho_channel=1.0,
        cases=rows,
    )
    (args.output / "result.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(status="passed", cases=len(rows), independent=True)))


if __name__ == "__main__":
    main()
