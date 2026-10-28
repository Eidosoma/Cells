"""Capture actual pinned native generator/regulation expressions, independently.

Only three authenticated AST methods execute. Source captures include native
configuration failures; native simulation, geometry and updates do not execute.
"""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.transport.betse_network_transport_fixtures import (
    SPECIES,
    VALENCE,
    cases,
    source_failures,
)
from validation.transport.betse_network_transport_reference import evaluate

PROTOCOL = Path(__file__).with_name("betse_network_transport_protocol.json")


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    contract = json.loads(PROTOCOL.read_text())
    source = contract["native_source"]
    checkout = Path(source["checkout"])
    installed = Path(source["installed_package"]).parent
    manifest = dict(status="capturing", files={}, executed_methods={}, native_simulation=False)
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest["revision"] = revision
    assert revision == source["revision"]
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    manifest["version"] = next(
        ast.literal_eval(node.value)
        for node in metadata.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
    )
    assert manifest["version"] == source["version"]
    for relative, expected in source["source_sha256"].items():
        data = (installed / relative).read_bytes()
        copied = output / "upstream" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, copied)
        observed = hashlib.sha256(data).hexdigest()
        manifest["files"][relative] = dict(
            sha256=observed, checkout_match=data == (checkout / relative).read_bytes()
        )
        write(output / "source-manifest.json", manifest)
        assert observed == expected and manifest["files"][relative]["checkout_match"]
    module = ast.parse((installed / "betse/science/chemistry/networks.py").read_text())
    cls = next(
        n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
    )
    methods = [
        n
        for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name in source["executed_methods"]
    ]
    assert {n.name for n in methods} == set(source["executed_methods"])
    for method in methods:
        manifest["executed_methods"][method.name] = dict(
            first_line=method.lineno, last_line=method.end_lineno
        )
    native_class = ast.ClassDef(
        name="CapturedNetwork", bases=[], keywords=[], body=methods, decorator_list=[]
    )
    native_module = ast.fix_missing_locations(ast.Module(body=[native_class], type_ignores=[]))
    namespace = dict(
        np=np,
        logs=SimpleNamespace(log_info=lambda *_: None),
        tex_val=str,
        BetseSimConfException=ValueError,
    )
    exec(
        compile(native_module, str(installed / "betse/science/chemistry/networks.py"), "exec"),
        namespace,
    )
    records = []
    prepared = [(row["name"], row, False) for row in cases()]
    prototype = cases()[0]
    prepared.extend(
        (name, dict(prototype, config=config), True) for name, config in source_failures().items()
    )
    for name, row, expected_failure in prepared:
        config = row["config"]
        tr = SimpleNamespace(
            reactants_list=config["reactants"],
            reactants_coeff=config["reactant multipliers"],
            Km_reactants_list=config["Km reactants"],
            products_list=config["products"],
            products_coeff=config["product multipliers"],
            Km_products_list=config["Km products"],
            reaction_zone=config["reaction zone"],
            transport_out_list=config["transfered out of cell"],
            transport_in_list=config["transfered into cell"],
            delta_Go=config["standard free energy"],
            vmax=config["max rate"],
            transporter_activators_list=config.get("transporter activators"),
            transporter_activators_Km=config.get("activator Km"),
            transporter_activators_n=config.get("activator n"),
            transporter_activators_zone=config.get("activator zone"),
            transporter_inhibitors_list=config.get("transporter inhibitors"),
            transporter_inhibitors_Km=config.get("inhibitor Km"),
            transporter_inhibitors_n=config.get("inhibitor n"),
            transporter_inhibitors_zone=config.get("inhibitor zone"),
        )
        if tr.delta_Go == "None":
            tr.delta_Go = None
        native = namespace["CapturedNetwork"]()
        native.transporters = {"probe": tr}
        native.mem_concs = {s: np.array([v]) for s, v in row["inside_mM"].items()}
        native.env_concs = {s: np.array([v]) for s, v in row["outside_mM"].items()}
        native.molecules = {s: SimpleNamespace(z=z) for s, z in zip(SPECIES, VALENCE, strict=True)}
        ions = ["Na", "K", "Cl", "Ca"]
        sim = SimpleNamespace(
            vm=np.array([row["voltage_V"]]),
            T=row["temperature_K"],
            zs=np.array(VALENCE[:4]),
            get_ion=ions.index,
            rho_pump=row["rho"],
            cdl=1,
            mdl=1,
            edl=1,
        )
        p = SimpleNamespace(
            ions_dict=dict.fromkeys(ions, 1), is_ecm=True, R=8.31446261815324, F=96485.33212331002
        )
        cells = SimpleNamespace(map_mem2ecm=np.array([0]))
        path = output / (name + ".json")
        record = dict(
            status="prepared",
            input=row,
            expected_native_failure=expected_failure,
            native_geometry_or_updates_executed=False,
            availability_is_external_multiplier=True,
        )
        write(path, record)
        native.write_transporters(sim, cells, p)
        record.update(
            expression=tr.transporter_eval_string,
            native_net_z=float(tr.net_z),
            reactant_tags=tr.react_transport_tag,
            product_tags=tr.prod_transport_tag,
        )
        write(path, record)
        try:
            value = eval(
                tr.transporter_eval_string, {"np": np}, dict(self=native, sim=sim, cells=cells, p=p)
            )
        except (SyntaxError, TypeError) as error:
            record.update(
                status="expected_native_failure",
                failure_type=type(error).__name__,
                message=str(error),
            )
            write(path, record)
            assert expected_failure
            records.append(dict(name=name, status=record["status"], path=str(path)))
            continue
        assert not expected_failure
        actual = float(np.asarray(value).reshape(-1)[0] * sim.rho_pump * row["availability"])
        expected = evaluate(
            config,
            row["inside_mM"],
            row["outside_mM"],
            dict(zip(SPECIES, VALENCE, strict=True)),
            **{
                key: row[key]
                for key in ("voltage_V", "temperature_K", "area_m2", "availability", "rho")
            },
        )
        record.update(
            status="captured",
            actual_flux_mol_m2_s=actual,
            reference=expected,
            actual_current_density_A_m2=float(tr.net_z * p.F * actual),
        )
        write(path, record)
        np.testing.assert_allclose(
            actual, expected["flux_density_mol_m2_s"], rtol=5e-12, atol=1e-18
        )
        np.testing.assert_allclose(tr.net_z, expected["native_net_z"], rtol=0, atol=3e-13)
        np.testing.assert_allclose(
            record["actual_current_density_A_m2"],
            expected["outward_current_density_A_m2"],
            rtol=5e-12,
            atol=1e-13,
        )
        record["status"] = "passed"
        write(path, record)
        records.append(dict(name=name, status="passed", path=str(path)))
    assert not any(
        name == "cells" or name.startswith("cells.") or name == "jax" or name.startswith("jax.")
        for name in sys.modules
    )
    manifest["no_production_or_jax_imports"] = True
    manifest.update(
        status="passed",
        cases=records,
        successful_cases=sum(r["status"] == "passed" for r in records),
        expected_native_failures=sum(r["status"] == "expected_native_failure" for r in records),
    )
    write(output / "source-manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="passed",
                cases=manifest["successful_cases"],
                expected_failures=manifest["expected_native_failures"],
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as error:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
