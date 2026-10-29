"""Authenticated native reader, generators, growth fields and matrix captures.

Small explicit input arrays; no production Cells/JAX imports or native run_loop.
Spatial modulator callbacks return supplied samples and are recorded as hooks.
"""

import argparse
import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.chemistry.betse_network_reactions_fixtures import cases, limitations
from validation.chemistry.betse_network_reactions_reference import evaluate

PROTOCOL = Path(__file__).with_name("betse_network_reactions_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def write(path, data):
    path.write_text(json.dumps(serial(data), indent=2, allow_nan=False) + "\n")


def executable(method):
    result = copy.deepcopy(method)
    result.decorator_list = []
    result.returns = None
    for arg in (*result.args.posonlyargs, *result.args.args, *result.args.kwonlyargs):
        arg.annotation = None
    return result


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(PROTOCOL.read_text())
    source = protocol["native_source"]
    checkout, installed = Path(source["checkout"]), Path(source["installed_package"]).parent
    manifest = dict(
        status="capturing",
        files={},
        executed_methods={},
        native_run_loop=False,
        modulator_hook="Return explicit per-cell samples; no spatial function equivalence claim",
    )
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest["revision"] = revision
    for relative, expected in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        path = output / "upstream" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, path)
        manifest["files"][relative] = dict(
            sha256=hashlib.sha256(content).hexdigest(),
            checkout_match=content == (checkout / relative).read_bytes(),
        )
        write(output / "source-manifest.json", manifest)
        assert (
            manifest["files"][relative]["sha256"] == expected
            and manifest["files"][relative]["checkout_match"]
        )
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    manifest["version"] = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert manifest["version"] == source["version"]
    parameters = ast.parse((installed / "betse/science/parameters.py").read_text())
    native_r = next(
        ast.literal_eval(n.value)
        for n in ast.walk(parameters)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "R" for t in n.targets)
    )
    assert native_r == 8.314
    manifest["native_default_R_J_mol_K"] = native_r
    module = ast.parse((installed / "betse/science/chemistry/networks.py").read_text())
    classes = {n.name: n for n in module.body if isinstance(n, ast.ClassDef)}
    network = classes["MasterOfNetworks"]
    methods = [
        n
        for n in network.body
        if isinstance(n, ast.FunctionDef) and n.name in source["executed_methods"]
    ]
    assert {n.name for n in methods} == set(source["executed_methods"])
    by_name = {n.name: n for n in network.body if isinstance(n, ast.FunctionDef)}
    time_assign = next(
        n
        for n in ast.walk(by_name["read_substances"])
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "use_time_dilation" for t in n.targets)
    )
    time_branch = next(
        n
        for n in ast.walk(by_name["read_substances"])
        if isinstance(n, ast.If) and ast.unparse(n.test) == "mol.use_time_dilation"
    )
    gad_assign = next(
        n
        for n in ast.walk(by_name["tissue_init"])
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "gad" for t in n.targets)
    )
    gad_branch = next(
        n
        for n in ast.walk(by_name["tissue_init"])
        if isinstance(n, ast.If) and ast.unparse(n.test) == "gad != 'None' and gad is not None"
    )
    reader = ast.parse(
        "def read_growth_fields(self, mol, mol_dic, phase, cells, sim, p):\n    pass\n"
    ).body[0]
    reader.body = copy.deepcopy([time_assign, time_branch, gad_assign, gad_branch])
    method_bodies = [*methods, reader]
    reaction_constructor = next(
        n
        for n in classes["Reaction"].body
        if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    init_growth = next(
        n
        for n in classes["Molecule"].body
        if isinstance(n, ast.FunctionDef) and n.name == "init_growth"
    )
    compiled = ast.Module(
        body=[
            ast.ClassDef(
                name="CapturedNetwork",
                bases=[],
                keywords=[],
                body=[executable(n) for n in method_bodies],
                decorator_list=[],
            ),
            ast.ClassDef(
                name="Reaction",
                bases=[],
                keywords=[],
                body=[executable(reaction_constructor)],
                decorator_list=[],
            ),
            ast.ClassDef(
                name="CapturedMolecule",
                bases=[ast.Name(id="SimpleNamespace", ctx=ast.Load())],
                keywords=[],
                body=[executable(init_growth)],
                decorator_list=[],
            ),
        ],
        type_ignores=[],
    )
    for method in (*methods, reaction_constructor, init_growth):
        manifest["executed_methods"][
            method.name if method is not reaction_constructor else "Reaction.__init__"
        ] = dict(first_line=method.lineno, last_line=method.end_lineno)
    manifest["growth_reader_fragments"] = [
        dict(first_line=n.lineno, last_line=n.end_lineno)
        for n in (time_assign, time_branch, gad_assign, gad_branch)
    ]
    hook_state, warnings = {}, []
    namespace = dict(
        np=np,
        OrderedDict=OrderedDict,
        SimpleNamespace=SimpleNamespace,
        logs=SimpleNamespace(
            log_info=lambda *_: None, log_warning=lambda *args: warnings.append(args)
        ),
        tex_val=str,
        BetseSimConfException=ValueError,
        mods=SimpleNamespace(sampled=lambda *_: (hook_state["modulation"], None)),
    )
    exec(
        compile(
            ast.fix_missing_locations(compiled),
            str(installed / "betse/science/chemistry/networks.py"),
            "exec",
        ),
        namespace,
    )
    records = []
    for raw, limitation in [(r, False) for r in cases()] + [(r, True) for r in limitations()]:
        path = output / (raw["name"] + ".json")
        record = dict(
            status="prepared",
            input=raw,
            limitation=limitation,
            native_run_loop=False,
            source_profile_targets={},
            modulator_hook_values={},
            stage="prepare",
        )
        write(path, record)
        native = namespace["CapturedNetwork"]()
        native.mit_enabled = raw.get("mit_enabled", True)
        native.time_dila = raw["time_dilation"]
        ids, zones = raw["species_ids"], raw["compartment_zones"]
        positions = {
            zone: [i for i, name in enumerate(zones) if name == zone]
            for zone in ("cell", "mit", "env")
        }
        for zone in positions:
            setattr(
                native,
                zone + "_concs",
                {
                    s: np.asarray(raw["concentration_mM"][i], float)[positions[zone]]
                    for i, s in enumerate(ids)
                },
            )
        sim = SimpleNamespace(
            cdl=len(positions["cell"]),
            edl=len(positions["env"]),
            mdl=len(positions["cell"]),
            T=raw["temperature_K"],
        )
        cells = SimpleNamespace(
            cell_i=np.arange(sim.cdl),
            mem_i=np.arange(sim.mdl),
            map_cell2ecm=np.array(
                [positions["env"].index(raw["cell_to_environment"][i]) for i in positions["cell"]]
            ),
        )
        p = SimpleNamespace(R=raw["gas_constant_J_mol_K"])
        phase = SimpleNamespace(
            cells=cells,
            sim=sim,
            p=p,
            dyna=SimpleNamespace(cell_target_inds={}, tissue_target_inds={}),
        )
        native.molecules = OrderedDict()
        warnings.clear()
        try:
            record["stage"] = "read_reactions"
            native.read_reactions(raw["reactions"], sim, cells, p)
            record["reader_zones"] = {
                zone: {
                    name: obj.reaction_zone
                    for name, obj in getattr(
                        native, "reactions" + ("_" + zone if zone != "cell" else ""), {}
                    ).items()
                }
                for zone in ("cell", "mit", "env")
            }
            record["reader_free_energies"] = {
                zone: {
                    name: obj.delta_Go
                    for name, obj in getattr(
                        native, "reactions" + ("_" + zone if zone != "cell" else ""), {}
                    ).items()
                }
                for zone in ("cell", "mit", "env")
            }
            write(path, record)
            for mol_dic in raw["growth"]:
                name = mol_dic["name"]
                mol = namespace["CapturedMolecule"](
                    name=name,
                    c_cells=native.cell_concs[name],
                    growth_targets_cell=cells.cell_i,
                    growth_targets_mem=cells.mem_i,
                )
                native.molecules[name] = mol
                target = np.asarray(raw["growth_targets"].get(name, [True] * sim.cdl), bool)
                gad = mol_dic.get("growth and decay")
                if isinstance(gad, dict) and isinstance(gad["apply to"], list):
                    for profile in gad["apply to"]:
                        phase.dyna.cell_target_inds[profile] = np.flatnonzero(target)
                        phase.dyna.tissue_target_inds[profile] = np.flatnonzero(target)
                hook_state["modulation"] = np.asarray(
                    raw["growth_modulation"].get(name, [1.0] * sim.cdl)
                )
                record["stage"] = "read_growth_fields"
                native.read_growth_fields(mol, mol_dic, phase, cells, sim, p)
                record["source_profile_targets"][name] = mol.growth_targets_cell
                record["modulator_hook_values"][name] = getattr(
                    mol, "growth_mod_function_cells", None
                )
            record["stage"] = "write_generators"
            native.write_growth_and_decay()
            native.write_reactions()
            if native.mit_enabled:
                native.write_reactions_mit()
            native.write_reactions_env()
            record["expressions"] = dict(
                growth={
                    name: dict(
                        rate=mol.gad_eval_string,
                        growth_aux=mol.gad_eval_string_growth,
                        decay_aux=mol.gad_eval_string_decay,
                    )
                    for name, mol in native.molecules.items()
                },
                reactions={
                    zone: {
                        name: obj.reaction_eval_string
                        for name, obj in getattr(
                            native, "reactions" + ("_" + zone if zone != "cell" else ""), {}
                        ).items()
                    }
                    for zone in ("cell", "mit", "env")
                },
            )
            write(path, record)
            record["stage"] = "matrix_builders"
            native.create_reaction_matrix()
            if native.mit_enabled:
                native.create_reaction_matrix_mit()
            native.create_reaction_matrix_env()
            matrices = {"cell": native.reaction_matrix, "env": native.reaction_matrix_env}
            if native.mit_enabled:
                matrices["mit"] = native.reaction_matrix_mit
            record["matrices"] = matrices
            write(path, record)
            context = dict(self=native, sim=sim, cells=cells, p=p)
            record["stage"] = "evaluate_expressions"

            def ev(expression, context=context):
                with np.errstate(all="ignore"):
                    return np.asarray(eval(expression, {"np": np}, context), float)

            rows, gad_rates = [], []
            for name, mol in native.molecules.items():
                unmasked = ev(mol.gad_eval_string)
                masked = np.zeros(sim.cdl)
                masked[mol.growth_targets_cell] = unmasked[mol.growth_targets_cell]
                gad_rates.append(masked)
                ga, da = ev(mol.gad_eval_string_growth), ev(mol.gad_eval_string_decay)
                for local, owner in enumerate(positions["cell"]):
                    rows.append(
                        dict(
                            name=name,
                            kind="growth",
                            owner=owner,
                            concentration_rate_mM_s=masked[local],
                            growth_optimization_alpha=ga[local],
                            decay_optimization_mM_s=da[local],
                        )
                    )
            delta = np.zeros((len(ids), len(zones)))
            for zone in ("cell", "mit", "env"):
                if zone == "mit" and not native.mit_enabled:
                    continue
                objs = getattr(native, "reactions" + ("_" + zone if zone != "cell" else ""))
                local_rates = list(gad_rates) if zone == "cell" else []
                for name, obj in objs.items():
                    value = ev(obj.reaction_eval_string)
                    local_rates.append(value)
                    for local, owner in enumerate(positions[zone]):
                        rows.append(
                            dict(
                                name=name,
                                kind=zone,
                                owner=owner,
                                concentration_rate_mM_s=value[local],
                            )
                        )
                local_rates = np.asarray(local_rates).reshape((-1, len(positions[zone])))
                delta[:, positions[zone]] = matrices[zone] @ local_rates
            amount = delta * np.asarray(raw["volume_m3"]) / 1e-15
            record.update(
                routes=rows,
                concentration_delta_mM_s=delta,
                amount_fmol_s=amount,
                warnings=list(warnings),
                status="captured_limitation" if limitation else "passed",
            )
            if not limitation:
                oracle = evaluate(raw)
                record["independent_reference"] = oracle
                assert len(rows) == len(oracle["routes"])
                for actual, expected in zip(rows, oracle["routes"], strict=True):
                    assert (actual["name"], actual["kind"], actual["owner"]) == (
                        expected["name"],
                        expected["kind"],
                        expected["owner"],
                    )
                    for key in (
                        "concentration_rate_mM_s",
                        "growth_optimization_alpha",
                        "decay_optimization_mM_s",
                    ):
                        if key in actual:
                            np.testing.assert_allclose(
                                actual[key], expected[key], rtol=5e-12, atol=2e-14
                            )
                np.testing.assert_allclose(amount, oracle["amount_fmol_s"], rtol=5e-12, atol=2e-12)
                for zone, actual in matrices.items():
                    np.testing.assert_array_equal(
                        actual, np.asarray(oracle["matrices"][zone]).reshape(actual.shape)
                    )
            else:
                assert not raw.get("expected_failure")
        except (
            TypeError,
            SyntaxError,
            ValueError,
            UnboundLocalError,
            KeyError,
            IndexError,
            AttributeError,
        ) as error:
            record.update(
                status="captured_failure",
                failure_type=type(error).__name__,
                message=str(error),
                warnings=list(warnings),
            )
            write(path, record)
            assert limitation and raw.get("expected_failure"), record
        write(path, record)
        records.append(dict(name=raw["name"], status=record["status"], path=str(path)))
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
    manifest.update(
        status="passed",
        records=records,
        component_cases=len(cases()),
        limitations=len(limitations()),
        production_cells_imported=False,
        jax_imported=False,
    )
    write(output / "source-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps({k: result[k] for k in ("status", "component_cases", "limitations")}))
