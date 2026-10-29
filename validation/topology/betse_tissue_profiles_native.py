"""Authenticated profile pickers, image loading, target maps and event writes."""

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import json
import random
import shutil
import subprocess
import sys
from abc import ABCMeta
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
from scipy.interpolate import RectBivariateSpline
from scipy.spatial import ConvexHull

from validation.topology.betse_tissue_profiles_fixtures import IONS, cases, limitations
from validation.topology.betse_tissue_profiles_reference import events as reference_events
from validation.topology.betse_tissue_profiles_reference import profiles as reference_profiles

PROTOCOL = Path(__file__).with_name("betse_tissue_profiles_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def write(path, value):
    path.write_text(json.dumps(serial(value), indent=2, allow_nan=False) + "\n")


def executable(node):
    result = copy.deepcopy(node)
    if isinstance(result, ast.FunctionDef):
        result.decorator_list, result.returns = [], None
        for arg in (*result.args.posonlyargs, *result.args.args, *result.args.kwonlyargs):
            arg.annotation = None
    return result


def rng_state():
    state = np.random.get_state()
    return dict(
        generator=state[0],
        keys=state[1].copy(),
        position=state[2],
        has_gauss=state[3],
        cached_gauss=state[4],
    )


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    contract = json.loads(PROTOCOL.read_text())
    source = contract["native_source"]
    checkout, installed = Path(source["checkout"]), Path(source["installed_package"]).parent
    manifest = dict(
        status="capturing",
        files={},
        executed_bodies={},
        full_simulator=False,
        versions={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "Pillow")},
        support_hooks=source["support_hooks"],
    )
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest["revision"] = revision
    trees = {}
    for relative, expected in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        dest = output / "upstream" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, dest)
        manifest["files"][relative] = dict(
            sha256=hashlib.sha256(content).hexdigest(),
            checkout_match=content == (checkout / relative).read_bytes(),
        )
        write(output / "source-manifest.json", manifest)
        assert (
            manifest["files"][relative]["sha256"] == expected
            and manifest["files"][relative]["checkout_match"]
        )
        trees[relative] = ast.parse(content.decode())
    metadata = trees["betse/metadata.py"]
    manifest["version"] = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert manifest["version"] == source["version"]

    def die_file(filename):
        if not Path(filename).is_file():
            raise FileNotFoundError(filename)

    namespace = dict(
        np=np,
        array=np.array,
        copy=copy,
        ABCMeta=ABCMeta,
        Enum=Enum,
        OrderedDict=OrderedDict,
        RectBivariateSpline=RectBivariateSpline,
        ConvexHull=ConvexHull,
        shuffle=random.shuffle,
        BetseSimConfException=ValueError,
        BetseSimTissueException=ValueError,
        BetseImageException=ValueError,
        BetseMathInterpolationException=ValueError,
        files=SimpleNamespace(die_unless_file=die_file),
        pathnames=SimpleNamespace(
            is_relative=lambda value: not Path(value).is_absolute(),
            join=lambda a, b: str(Path(a) / b),
            get_basename=lambda value: Path(value).name,
        ),
        sequences=SimpleNamespace(
            is_sequence=lambda value: isinstance(value, (list, tuple, np.ndarray))
        ),
        logs=SimpleNamespace(log_info=lambda *_: None, log_debug=lambda *_: None),
    )
    picker_enum = Enum("CellsPickerType", ("ALL", "COLOR", "IMAGE", "INDICES", "PERCENT"))
    namespace["CellsPickerType"] = picker_enum
    bodies = []
    for relative, class_names in (
        (
            "betse/science/tissue/picker/tispickcls.py",
            (
                "TissuePickerABC",
                "TissuePickerAll",
                "TissuePickerColor",
                "TissuePickerIndices",
                "TissuePickerPercent",
            ),
        ),
        (
            "betse/science/tissue/picker/tispickimage.py",
            ("TissuePickerImageMask", "TissuePickerImage"),
        ),
        ("betse/science/tissue/tisprofile.py", ("CellsProfileABC", "TissueProfile")),
    ):
        for cls in [
            n for n in trees[relative].body if isinstance(n, ast.ClassDef) and n.name in class_names
        ]:
            node = copy.deepcopy(cls)
            node.decorator_list = []
            node.body = [
                executable(n) if isinstance(n, ast.FunctionDef) else copy.deepcopy(n)
                for n in cls.body
            ]
            bodies.append(node)
            manifest["executed_bodies"][cls.name] = dict(
                source=relative, first_line=cls.lineno, last_line=cls.end_lineno
            )
    handler_cls = next(
        n
        for n in trees["betse/science/tissue/tishandler.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    selected = [
        n
        for n in handler_cls.body
        if isinstance(n, ast.FunctionDef) and n.name in source["handler_methods"]
    ]
    assert {n.name for n in selected} == set(source["handler_methods"])
    bodies.append(
        ast.ClassDef(
            name="CapturedHandler",
            bases=[],
            keywords=[],
            body=[executable(n) for n in selected],
            decorator_list=[],
        )
    )
    for n in selected:
        manifest["executed_bodies"]["TissueHandler." + n.name] = dict(
            source="betse/science/tissue/tishandler.py", first_line=n.lineno, last_line=n.end_lineno
        )
    cells_cls = next(
        n
        for n in trees["betse/science/cells.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    redo = next(n for n in cells_cls.body if isinstance(n, ast.FunctionDef) and n.name == "redo_gj")
    bodies.append(
        ast.ClassDef(
            name="CapturedCells", bases=[], keywords=[], body=[executable(redo)], decorator_list=[]
        )
    )
    manifest["executed_bodies"]["Cells.redo_gj"] = dict(
        source="betse/science/cells.py", first_line=redo.lineno, last_line=redo.end_lineno
    )
    for relative, names in (
        ("betse/science/math/toolbox.py", ("flatten", "pulse")),
        ("betse/science/math/modulate.py", ("gradient_x",)),
        ("betse/util/math/mathinterp.py", ("interp2d_linear",)),
        ("betse/lib/numpy/nparray.py", ("from_iterable", "to_signed")),
        ("betse/lib/pil/pilnumpy.py", ("load_image",)),
    ):
        for node in trees[relative].body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                bodies.append(executable(node))
                manifest["executed_bodies"][node.name] = dict(
                    source=relative, first_line=node.lineno, last_line=node.end_lineno
                )
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DTYPE_UNSIGNED_TO_SIGNED" for t in node.targets
            ):
                bodies.append(copy.deepcopy(node))
    mode = next(
        n
        for n in trees["betse/lib/pil/pilnumpy.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "ImageModeType"
    )
    bodies.insert(0, copy.deepcopy(mode))
    namespace["Image"] = Image
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=bodies, type_ignores=[])),
            "authenticated-native-tissue-profiles",
            "exec",
        ),
        namespace,
    )
    namespace["nparray"] = SimpleNamespace(
        from_iterable=namespace["from_iterable"], to_signed=namespace["to_signed"]
    )
    namespace["pilnumpy"] = SimpleNamespace(load_image=namespace["load_image"])
    namespace["toolbox"] = namespace["tb"] = SimpleNamespace(
        flatten=namespace["flatten"], pulse=namespace["pulse"]
    )
    namespace["mod"] = SimpleNamespace(gradient_x=namespace["gradient_x"])
    namespace["ImageModeType"] = namespace["ImageModeType"]
    pick_steps, image_masks, picker_names = [], {}, {}
    original_pick = namespace["TissuePickerABC"].pick_cells_and_mems

    def pick(self, cells, p):
        name = picker_names[id(self)]
        row = dict(
            name=name,
            class_name=type(self).__name__,
            cell_i_before=cells.cell_i.copy(),
            rng_before=rng_state(),
        )
        pick_steps.append(row)
        output = original_pick(self, cells, p)
        row.update(
            cells_at_pick=copy.deepcopy(output[0]),
            membranes_at_pick=output[1].copy(),
            cell_i_after=cells.cell_i.copy(),
            rng_after=rng_state(),
            membrane_dtype=str(output[1].dtype),
        )
        return output

    namespace["TissuePickerABC"].pick_cells_and_mems = pick
    original_mask = namespace["TissuePickerImage"].get_image_mask

    def image_mask(self, cells):
        mask = original_mask(self, cells)
        name = picker_names[id(self)]
        image_masks[name] = dict(
            clipping_matrix=mask.clipping_matrix.copy(),
            decoded_F_pixels=namespace["load_image"](
                self.filename, mode=namespace["ImageModeType"].GRAYSCALE_FLOAT
            ),
            linear_values=[
                float(np.asarray(mask.clipping_function(x, y)).reshape(-1)[0])
                for x, y in cells.cell_centres
            ],
            unused_fast_values=mask.clipping_function_fast.ev(
                cells.cell_centres[:, 0], cells.cell_centres[:, 1]
            ),
        )
        return mask

    namespace["TissuePickerImage"].get_image_mask = image_mask
    records = []
    for raw, limitation in [(r, False) for r in cases()] + [(r, True) for r in limitations()]:
        path = output / (raw["name"] + ".json")
        record = dict(
            status="prepared",
            input=raw,
            limitation=limitation,
            stage="prepare",
            full_simulator=False,
        )
        write(path, record)
        pick_steps.clear()
        image_masks.clear()
        picker_names.clear()
        np.random.seed(raw["seed"])
        random.seed(raw["seed"])
        layout = raw["layout"]
        n, m, _e = (
            len(layout["cell_ids"]),
            len(layout["membrane_ids"]),
            len(layout["environment_ids"]),
        )
        asset_dir = output / "assets" / raw["name"]
        asset_dir.mkdir(parents=True)

        def normalized(row, asset_dir=asset_dir):
            fields = dict(
                name=row["name"],
                picker_type=getattr(picker_enum, row["picker"].upper(), row["picker"]),
                picker_cells_color=row["color"],
                picker_cells_index=row["indices"],
                picker_cells_percent=row["percent"],
                is_gj_insular=row["insular"],
            )
            image_path = asset_dir / (row["name"] + (".png" if row["rgba"] else ".tiff"))
            if row["picker"] == "image" and not row.get("missing_image"):
                gray = np.asarray(row["bitmap"], np.float32)
                if row["rgba"]:
                    data = np.zeros(gray.shape + (4,), np.uint8)
                    data[..., :3] = np.asarray(gray, np.uint8)[..., None]
                    Image.fromarray(data).save(image_path)
                else:
                    Image.fromarray(gray).save(image_path)
            fields["picker_image_filename"] = str(image_path)
            fields.update(
                {
                    "Dm_" + ion: value
                    for ion, value in zip(IONS, row["diffusivity_m2_s"], strict=True)
                }
            )
            return SimpleNamespace(**fields)

        p = SimpleNamespace(
            is_tissue_profiles=raw["enabled"],
            tissue_default=normalized(raw["default"]),
            tissue_profiles=[normalized(row) for row in raw["profiles"]],
            conf_dirname=str(asset_dir),
            is_ecm=raw["is_ecm"],
            ions_dict=dict(zip(IONS, (int(v) for v in raw["ion_enabled"]), strict=True)),
            scheduled_options=dict.fromkeys(
                ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ"), 0
            ),
            global_options=dict.fromkeys(
                ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block"), 0
            ),
            gradient_x_properties={
                key.replace("_", "-"): value for key, value in raw["gradient_x"].items()
            },
            event_cut_time=0.0,
        )
        for row in raw["events"]:
            common = [row["on_s"], row["off_s"], row["change_s"]]
            p.scheduled_options[row["kind"]] = common + (
                [row["profiles"], row["amplitude"]]
                if row["kind"] == "ecmJ"
                else [row["amplitude"], row["profiles"], row["function"]]
            )
        if "global_gj_percent" in raw:
            p.global_options["gj_block"] = [0.2, 0.8, 0.12, raw["global_gj_percent"]]
        cells = namespace["CapturedCells"]()
        cells.cell_i, cells.mem_i = np.arange(n), np.arange(m)
        cells.cell_to_mems = np.empty(n, object)
        for i, group in enumerate(layout["cell_membranes"]):
            cells.cell_to_mems[i] = np.asarray(group, int)
        cells.mem_to_cells, cells.map_mem2ecm = (
            np.asarray(layout["membrane_cell"], int),
            np.asarray(layout["membrane_environment"], int),
        )
        cells.cell_centres, cells.mem_mids_flat = (
            np.asarray(layout["cell_centres_m"], float),
            np.asarray(layout["membrane_midpoints_m"], float),
        )
        cells.xmin, cells.xmax, cells.ymin, cells.ymax = layout["bounds_m"]
        cells.seed_fills, cells.nn_i = (
            layout["seed_fills"],
            np.asarray(layout["partner_membrane"], int),
        )
        cells.cell_nn = np.empty(n, object)
        for i, row in enumerate(layout["cell_neighbors"]):
            cells.cell_nn[i] = np.asarray(row, int)
        geometry_calls = []
        cells.calc_gj_vects = lambda _p, geometry_calls=geometry_calls: geometry_calls.append(
            "calc_gj_vects recorded, no geometry rebuilt"
        )
        cells.X = np.zeros(raw["environment_shape"])
        sim = SimpleNamespace(
            Dm_cells=np.asarray(raw["initial_membrane_m2_s"], float),
            Dm_scheduled=np.asarray(raw["initial_scheduled_m2_s"], float),
            P_base=np.asarray(raw["pressure_base_Pa"], float),
            P_mod=np.asarray(raw["pressure_mod_Pa"], float),
            D_env_base=np.asarray(raw["environment_base_m2_s"], float),
            D_env=np.asarray(raw["environment_current_m2_s"], float),
            D_free=np.asarray(raw["environment_free_m2_s"], float),
            D_env_weight_base=np.asarray(raw["environment_weight_base"], float).reshape(
                raw["environment_shape"]
            ),
            D_env_weight=np.asarray(raw["environment_weight_current"], float).reshape(
                raw["environment_shape"]
            ),
            gj_block=np.asarray([0.3 + 0.02 * i for i in range(m)]),
        )
        for i, ion in enumerate(IONS):
            setattr(sim, "i" + ion, i)
        handler = namespace["CapturedHandler"]()
        handler.event_cut, handler._event_voltage = None, None
        phase = SimpleNamespace(cells=cells, sim=sim, p=p, dyna=handler)
        try:
            record["stage"] = "_init_tissues"
            handler._init_tissues(p)
            picker_names.update(
                {
                    id(profile.picker): name
                    for name, profile in handler.tissue_name_to_profile.items()
                }
            )
            record["stage"] = "init_profiles"
            handler.init_profiles(phase)
            targets = {
                name: dict(
                    cells=handler.cell_target_inds[name],
                    membranes=handler.tissue_target_inds[name],
                    environments=handler.env_target_inds.get(name, []),
                    environment_declared=name in handler.env_target_inds,
                )
                for name in handler.tissue_name_to_profile
            }
            permutations = {
                row["name"]: row["cell_i_after"]
                for row in pick_steps
                if row["class_name"] == "TissuePickerPercent"
            }
            record.update(
                targets=copy.deepcopy(targets),
                pick_steps=copy.deepcopy(pick_steps),
                image_masks=copy.deepcopy(image_masks),
                resolved_permutations=copy.deepcopy(permutations),
                final_cell_order=cells.cell_i.copy(),
                diffusion_m2_s=sim.Dm_cells.copy(),
            )
            write(path, record)
            record["stage"] = "redo_gj"
            cells.redo_gj(phase)
            record.update(
                gj_weights=cells.gj_default_weights.copy(),
                original_neighbor_counts=cells.num_nn.copy(),
                connected_neighbors=copy.deepcopy(cells.cell_nn_connected),
                geometry_hooks=geometry_calls,
            )
            sim.Dm_base = sim.Dm_cells.copy()
            record["stage"] = "init_events"
            python_rng_before = random.getstate()
            handler.init_events(phase)
            record["python_rng_consumed_global_GJ"] = random.getstate() != python_rng_before
            if hasattr(handler, "targets_gj_block"):
                record["global_gj_targets"] = handler.targets_gj_block
            declarations = {}
            suffixes = {
                "Na_mem": "Namem",
                "K_mem": "Kmem",
                "Cl_mem": "Clmem",
                "Ca_mem": "Camem",
                "pressure": "P",
                "ecmJ": "ecmJ",
            }
            for row in raw["events"]:
                suffix = suffixes[row["kind"]]
                declarations[row["name"]] = dict(
                    kind=row["kind"],
                    targets=getattr(handler, "targets_" + suffix, None),
                    scalar=getattr(handler, "scalar_" + suffix, 1),
                )
            record["event_declarations"] = declarations
            record["event_records"] = []
            write(path, record)
            for time in raw["times_s"]:
                record["stage"] = "fire_events"
                with np.errstate(all="ignore"):
                    handler.fire_events(phase, time)
                record["event_records"].append(
                    dict(
                        time_s=time,
                        membrane_scheduled_m2_s=sim.Dm_scheduled.copy(),
                        membrane_total_m2_s=sim.Dm_cells.copy(),
                        pressure_mod_Pa=sim.P_mod.copy(),
                        pressure_total_Pa=sim.P_cells.copy(),
                        environment_current_m2_s=sim.D_env.copy(),
                        environment_weight_current=sim.D_env_weight.ravel().copy(),
                        gj_block=sim.gj_block.copy(),
                    )
                )
            record["status"] = "captured_limitation" if limitation else "passed"
            write(path, record)
            if limitation:
                assert not raw["expected_failure"], raw["name"]
            else:
                expected = reference_profiles(raw, permutations)
                event_expected = reference_events(raw, expected)
                record["independent_profiles"] = expected
                record["independent_events"] = event_expected
                for name, data in expected["targets"].items():
                    for field in ("cells", "membranes", "environments"):
                        np.testing.assert_array_equal(targets[name][field], data[field])
                    assert targets[name]["environment_declared"] == data["environment_declared"]
                np.testing.assert_array_equal(cells.cell_i, expected["final_cell_order"])
                np.testing.assert_array_equal(record["diffusion_m2_s"], expected["diffusion_m2_s"])
                np.testing.assert_array_equal(cells.gj_default_weights, expected["gj_weights"])
                for actual, oracle in zip(
                    record["event_records"], event_expected["records"], strict=True
                ):
                    for field in (
                        "membrane_scheduled_m2_s",
                        "membrane_total_m2_s",
                        "pressure_mod_Pa",
                        "pressure_total_Pa",
                        "environment_current_m2_s",
                        "environment_weight_current",
                    ):
                        atol = (
                            1e-30
                            if field.startswith("membrane")
                            else 3e-13
                            if field.startswith("pressure")
                            else 1e-21
                            if field == "environment_current_m2_s"
                            else 3e-14
                        )
                        np.testing.assert_allclose(
                            actual[field], oracle[field], rtol=5e-12, atol=atol
                        )
        except Exception as error:
            if isinstance(error, AssertionError):
                raise
            record.update(
                status="captured_failure",
                failure_type=type(error).__name__,
                message=str(error),
                partial_Dm=sim.Dm_cells,
                partial_cell_i=cells.cell_i,
                partial_targets=getattr(handler, "cell_target_inds", None),
                pick_steps=copy.deepcopy(pick_steps),
            )
            write(path, record)
            assert limitation and raw["expected_failure"], raw["name"]
        record["assets"] = {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in asset_dir.glob("*")
            if p.is_file()
        }
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
        geometry_or_cut_executed=False,
        production_random_stream_claim=False,
    )
    write(output / "source-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps({key: result[key] for key in ("status", "component_cases", "limitations")}))
