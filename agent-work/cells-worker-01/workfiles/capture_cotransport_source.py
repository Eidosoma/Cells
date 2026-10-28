"""Bounded-runner child: capture the actual pinned generic BETSE generator.

Only the installed write_transporters AST is executed. Full native simulation,
upstream imports and upstream concentration updates are outside this probe.
The external capture retains exact source files; none are copied into this repo.
"""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.transport.cotransport_reference import betse_generic_density

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads((ROOT / "validation/transport/cotransport_protocol.json").read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    source = PROTOCOL["native_source"]
    checkout = Path(source["checkout"])
    installed = Path(source["installed_package"]).parent
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = dict(status="capturing", revision=revision, files={}, named_law_matches=[])
    write(output / "source-manifest.json", manifest)
    assert revision == source["revision"]
    for relative, expected in source["source_sha256"].items():
        data = (installed / relative).read_bytes()
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, target)
        observed = hashlib.sha256(data).hexdigest()
        manifest["files"][relative] = dict(
            sha256=observed, checkout_match=data == (checkout / relative).read_bytes()
        )
        write(output / "source-manifest.json", manifest)
        assert observed == expected and manifest["files"][relative]["checkout_match"]
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    manifest["version"] = next(
        ast.literal_eval(node.value)
        for node in metadata.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in node.targets)
    )
    assert manifest["version"] == source["version"]
    # The shell review found no named law. Retain the same lexical search receipt.
    search = subprocess.run(
        ["rg", "-n", "-i", r"\bkcc\b|\bnkcc\b", str(installed / "betse")],
        capture_output=True,
        text=True,
        check=False,
    )
    manifest["named_law_search"] = dict(
        argv=search.args, returncode=search.returncode, stdout=search.stdout, stderr=search.stderr
    )
    write(output / "source-manifest.json", manifest)
    assert search.returncode == 1 and not search.stdout
    module = ast.parse((installed / "betse/science/chemistry/networks.py").read_text())
    cls = next(
        n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
    )
    method = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "write_transporters"
    )
    namespace = dict(
        np=np,
        logs=SimpleNamespace(log_info=lambda *_: None),
        tex_val=str,
        BetseSimConfException=ValueError,
    )
    exec(
        compile(
            ast.Module(body=[method], type_ignores=[]),
            str(installed / "betse/science/chemistry/networks.py"),
            "exec",
        ),
        namespace,
    )
    manifest["executed_method"] = dict(
        name=method.name, first_line=method.lineno, last_line=method.end_lineno
    )
    cases = []
    for kind, names, coefficients in (
        ("kcc", ["K", "Cl"], [1, 1]),
        ("nkcc", ["Na", "K", "Cl"], [1, 1, 2]),
    ):
        for direction, ratio in (("forward", 2.0), ("stall", 1.0), ("reverse", 0.5)):
            cases.append((kind, names, coefficients, direction, ratio, 0.0, 1.0))
        cases.append((kind, names, coefficients, "irreversible-reverse-gradient", 0.5, None, 1.0))
        cases.append((kind, names, coefficients, "changed-product-km", 2.0, 0.0, 100.0))
    for kind, names, coefficients, label, ratio, standard, product_km_scale in cases:
        ci = [10.0 + i * 2 for i in range(len(names))]
        co = [value * ratio for value in ci]
        km = [20.0 + i * 3 for i in range(len(names))]
        config = {
            "name": "probe",
            "reaction zone": "cell",
            "reactants": names,
            "reactant multipliers": coefficients,
            "Km reactants": km,
            "products": names,
            "product multipliers": coefficients,
            "Km products": [value * product_km_scale for value in km],
            "transfered out of cell": [],
            "transfered into cell": names,
            "max rate": 1e-5,
            "standard free energy": standard,
            "ignore ECM": False,
            "apply to": "all",
        }
        tr = SimpleNamespace(
            reactants_list=names,
            reactants_coeff=coefficients,
            Km_reactants_list=km,
            products_list=names,
            products_coeff=coefficients,
            Km_products_list=config["Km products"],
            transporter_activators_list=[],
            transporter_activators_Km=[],
            transporter_activators_n=[],
            transporter_inhibitors_list=[],
            transporter_inhibitors_Km=[],
            transporter_inhibitors_n=[],
            reaction_zone="cell",
            transport_out_list=[],
            transport_in_list=names,
            delta_Go=standard,
            vmax=1e-5,
        )
        availability, rho = 0.7, 0.8
        self = SimpleNamespace(
            transporters={"probe": tr},
            get_influencers=lambda *_, opening=availability, **kw: (
                str(opening),
                "",
                kw["tex_list"],
            ),
            mem_concs={name: np.array([value]) for name, value in zip(names, ci, strict=True)},
            env_concs={name: np.array([value]) for name, value in zip(names, co, strict=True)},
        )
        sim = SimpleNamespace(
            vm=np.array([-0.07]),
            T=298.15,
            zs=np.array([1 if name != "Cl" else -1 for name in names]),
            get_ion=names.index,
            rho_pump=rho,
        )
        p = SimpleNamespace(
            ions_dict=dict.fromkeys(names, 1), is_ecm=True, R=8.31446261815324, F=96485.33212331002
        )
        cells = SimpleNamespace(map_mem2ecm=np.array([0]))
        record = dict(
            kind="native-generic-source-probe",
            status="prepared",
            named_configuration=kind,
            case=label,
            config=config,
            inside_mM=ci,
            outside_mM=co,
            availability=availability,
            rho_pump=rho,
            temperature_K=sim.T,
            voltage_V=sim.vm.tolist(),
            geometry_and_updates_executed=False,
        )
        path = output / ("native-generic-" + kind + "-" + label + ".json")
        write(path, record)
        namespace["write_transporters"](self, sim, cells, p)
        record.update(
            expression=tr.transporter_eval_string,
            net_z=int(tr.net_z),
            reactant_tags=tr.react_transport_tag,
            product_tags=tr.prod_transport_tag,
        )
        write(path, record)
        actual = float(
            (
                rho
                * eval(
                    tr.transporter_eval_string,
                    {"np": np},
                    dict(self=self, sim=sim, cells=cells, p=p),
                )
            )[0]
        )
        record.update(status="captured", actual_flux_mol_m2_s=actual)
        write(path, record)
        expected = betse_generic_density(
            ci, co, coefficients, km, tr.vmax, availability, rho, sim.T, standard
        )
        record["expected_flux_mol_m2_s"] = expected
        write(path, record)
        np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-18)
        assert tr.net_z == 0 and tr.react_transport_tag == ["env_concs"] * len(names)
        assert tr.prod_transport_tag == ["mem_concs"] * len(names)
        if standard is None:
            assert actual > 0  # Source-only irreversible semantics; not our physical law.
        else:
            assert np.sign(actual) == np.sign(ratio - 1)
        record["status"] = "passed"
        write(path, record)
    manifest.update(status="passed", cases=len(cases), native_tissue_simulation=False)
    write(output / "source-manifest.json", manifest)
    print(json.dumps(dict(status="passed", native_generic_cases=len(cases), output=str(output))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as exc:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(exc).__name__, message=str(exc)))
        raise
