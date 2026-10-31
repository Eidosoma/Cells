"""Bounded retained-data algebra only; never import or execute model/references.

NPY decoding uses the standard library, one small saved member at a time. All
comparisons retain the frozen case and budgets. No simulation, flux law, PDE,
reference evaluator, test collector or active-job status reader is called.
"""

import ast
import hashlib
import importlib.abc
import json
import math
import os
import resource
import struct
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

ARCHIVE = Path("/mnt/workspaces/Cells/betse-ecm-failure-capture-20261030-01")
OLD = Path("/mnt/workspaces/Cells/betse-ecm-transport-20261030-02")
FAILED = Path("/mnt/workspaces/Cells/betse-ecm-transport-failed-round-20261030-01.json")
OUT = Path("/mnt/workspaces/Cells/betse-ecm-material-retained-diagnosis-20261031-02")
MAX_MEMBER = 64 * 1024
BLOCKED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "torch", "PIL"}


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Retained-data diagnosis forbids " + fullname)


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Oversize retained JSON")
    return json.loads(path.read_text())


def write(name, value):
    path = OUT / (name + ".json")
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def exact(value):
    return Fraction.from_float(float(value))


def rational(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


class SavedArrays:
    def __init__(self, path):
        self.path = path
        self.archive = zipfile.ZipFile(path)
        infos = self.archive.infolist()
        assert len(infos) <= 2000 and sum(i.file_size for i in infos) <= 4 * 2**20
        assert all(i.file_size <= MAX_MEMBER and i.filename.endswith(".npy") for i in infos)
        self.names = {i.filename.removesuffix(".npy") for i in infos}
        assert len(self.names) == len(infos)

    def get(self, name):
        content = self.archive.read(name + ".npy")
        assert content[:6] == b"\x93NUMPY"
        major, minor = content[6:8]
        assert (major, minor) in ((1, 0), (2, 0), (3, 0))
        width = 2 if major == 1 else 4
        count = int.from_bytes(content[8 : 8 + width], "little")
        header = ast.literal_eval(
            content[8 + width : 8 + width + count].decode("latin1" if major < 3 else "utf8").strip()
        )
        assert (
            set(header) == {"descr", "fortran_order", "shape"} and header["fortran_order"] is False
        )
        shape = header["shape"]
        assert isinstance(shape, tuple) and all(type(n) is int and 0 <= n <= 128 for n in shape)
        codes = {"<f8": "d", "<i8": "q", "<u8": "Q", "|b1": "?"}
        assert header["descr"] in codes, header
        data = content[8 + width + count :]
        size = math.prod(shape)
        fmt = "<" + str(size) + codes[header["descr"]]
        assert len(data) == struct.calcsize(fmt)
        values = struct.unpack(fmt, data)
        assert all(math.isfinite(float(v)) for v in values)
        return dict(shape=shape, dtype=header["descr"], values=values, bytes=data)


def at(array, *indices):
    assert len(indices) == len(array["shape"])
    offset = 0
    for index, size in zip(indices, array["shape"], strict=True):
        assert 0 <= index < size
        offset = offset * size + index
    return array["values"][offset]


def budget(key, wanted):
    leaf = key.rsplit(".", 1)[-1]
    floor = (
        3e-14
        if leaf.endswith("_mol")
        else 1e-40
        if leaf.endswith("_V")
        else 1e-18
        if "flux" in leaf
        else 1e-28
        if "junction_field" in leaf
        else 3e-20
        if "diffusion" in leaf
        else 3e-14
        if leaf in ("alpha", "gap_open")
        else 3e-13
    )
    return floor + 6e-12 * abs(wanted)


def nearest_integer(value):
    lower = value.numerator // value.denominator
    remainder = value - lower
    return lower + int(remainder > Fraction(1, 2) or (remainder == Fraction(1, 2) and lower % 2))


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    assert not any(name.split(".")[0] in BLOCKED for name in sys.modules)
    sys.meta_path.insert(0, Guard())
    assert not OUT.exists()
    OUT.mkdir()
    archive_result = read(ARCHIVE / "result.json")
    comparison = read(ARCHIVE / "comparison.json")
    raw = read(ARCHIVE / "original-case.json")
    data = raw["inputs"]
    definition = data["definition"]
    external = definition["environment_geometry_definition"]
    cg = external["current_definition"]["geometry"]
    ion_ids = external["current_definition"]["ions"]["ids"]
    owner = cg["owner"]
    areas = cg["membrane_area_m2"]
    volumes = external["geometry"]["cell_volume_m3"]
    moving = definition["ions"]["moving_ids"]
    assert not definition["parameters"]["fast_update_ecm"]
    assert not definition["parameters"]["cluster_open"]
    assert len(data["steps"]) == 1 and len(owner) == 9 and len(volumes) == 3
    metadata = raw["actual_metadata"][0]
    inputs_to_pin = [
        "original-case.json",
        "original-case.npz",
        "fresh-reference-r1.json",
        "fresh-reference-r1.npz",
        "fresh-reference-r2.json",
        "fresh-reference-r2.npz",
        "comparison.json",
        "evidence/ecm-transport-raw/signed_environment-references.json",
        "evidence/ecm-transport-raw/signed_environment-references.npz",
        "source/src/cells/processes/betse_ecm_transport.py",
        "source/validation/betse/betse_ecm_transport_reference.py",
        "source/validation/betse/betse_ecm_transport_checks.py",
        "source/validation/betse/betse_environment_field_reference.py",
        "source/tests/unit/test_betse_ecm_transport.py",
        "native/betse/science/sim.py",
        "native/betse/science/sim_toolbox.py",
    ]
    pins = {name: sha(ARCHIVE / name) for name in inputs_to_pin}
    for name, pin in pins.items():
        assert archive_result["artifacts"][name] == pin, name
    assert (
        sha(OLD / "evidence/ecm-transport-raw/signed_environment.npz") == pins["original-case.npz"]
    )
    assert (
        sha(OLD / "evidence/ecm-transport-raw/signed_environment.json")
        == pins["original-case.json"]
    )
    write(
        "inputs",
        dict(
            archive=str(ARCHIVE),
            original_failure_handoff=str(FAILED),
            handoff_sha256=sha(FAILED),
            result_sha256=sha(ARCHIVE / "result.json"),
            archive_sha256=pins,
            original_actual_native_bytes_identical_to_archival=True,
            inputs=data,
            raw_metadata=metadata,
        ),
    )
    actual = SavedArrays(ARCHIVE / "original-case.npz")
    first = SavedArrays(ARCHIVE / "fresh-reference-r1.npz")
    second = SavedArrays(ARCHIVE / "fresh-reference-r2.npz")
    archived_refs = SavedArrays(
        ARCHIVE / "evidence/ecm-transport-raw/signed_environment-references.npz"
    )
    native_keys = sorted(name for name in actual.names if name.startswith("native__"))
    assert len(native_keys) == 381 and len(first.names) == len(second.names) == 396
    bitwise = 0
    for name in native_keys:
        a = actual.get("actual__" + name.removeprefix("native__"))
        b = actual.get(name)
        assert (
            a["shape"] == b["shape"] and a["dtype"] == b["dtype"] and a["values"] == b["values"]
        ), name
        bitwise += a["bytes"] == b["bytes"]
    assert raw["actual_metadata"] == raw["native_metadata"] and raw["native_failure"] is None
    all_fields = []
    failed_fields = []
    worst_resolution = 0.0
    for name in sorted(first.names):
        a = actual.get("actual__" + name.replace(".", "__"))
        r1 = first.get(name)
        r2 = second.get(name)
        ar1 = archived_refs.get("reference__" + name.replace(".", "__"))
        ar2 = archived_refs.get("refined__" + name.replace(".", "__"))
        assert r1["shape"] == r2["shape"] == a["shape"]
        assert r1["values"] == ar1["values"] and r2["values"] == ar2["values"], name
        scores = [
            abs(x - y) / budget(name, y) for x, y in zip(a["values"], r1["values"], strict=True)
        ]
        resolutions = [
            abs(x - y) / budget(name, y) for x, y in zip(r1["values"], r2["values"], strict=True)
        ]
        score = max(scores, default=0.0)
        resolution = max(resolutions, default=0.0)
        worst_resolution = max(worst_resolution, resolution)
        record = dict(
            field=name,
            shape=list(a["shape"]),
            error_over_budget=score,
            reference_resolution_over_budget=resolution,
        )
        all_fields.append(record)
        if score > 1:
            failed_fields.append(record)
    assert (
        len(failed_fields) == 1
        and failed_fields[0]["field"] == "step_0.ledger.membrane_bulk_difference_mol_m3"
    )
    assert (
        failed_fields[0]["error_over_budget"]
        == comparison["failed_fields"][0]["max_error_fraction"]
    )
    write(
        "all-saved-comparisons",
        dict(
            fields=all_fields,
            failed=failed_fields,
            exact_native_numeric_columns=len(native_keys),
            exact_native_bitwise_columns=bitwise,
            reference_resolutions=worst_resolution,
        ),
    )

    def saved(key):
        return actual.get("actual__step_0__" + key.replace(".", "__"))

    cell = saved("candidate.cell_mol_m3")
    mem = saved("candidate.membrane_mol_m3")
    lag = saved("ledger.membrane_bulk_difference_mol_m3")
    rcell = first.get("step_0.candidate.cell_mol_m3")
    rmem = first.get("step_0.candidate.membrane_mol_m3")
    rlag = first.get("step_0.ledger.membrane_bulk_difference_mol_m3")
    fg = saved("candidate.junction_flux_mol_m2_s")
    dt = data["steps"][0]["dt_s"]
    assert all(v == 0 for v in saved("ledger.clipping_added_mol")["values"])
    details = []
    stable_scores = []
    impossible = []
    for ion in moving:
        i = ion_ids.index(ion)
        commit = metadata.index(["membrane_commit", ion])
        gap = metadata.index(["junction_commit", ion])
        clip = metadata.index(["clip_bulk", ion])
        before = saved(f"frame_{commit}.cell_mol_m3")
        after = saved(f"frame_{gap}.cell_mol_m3")
        clipped = saved(f"frame_{clip}.cell_mol_m3")
        for c, name in enumerate(cg["cell_ids"]):
            faces = [j for j, value in enumerate(owner) if value == c]
            face = faces[0]
            aa, bb, delta, wanted = (
                at(mem, i, face),
                at(cell, i, c),
                at(lag, i, face),
                at(rlag, i, face),
            )
            assert at(before, i, c) == aa and at(after, i, c) == at(clipped, i, c) == bb
            assert all(
                at(mem, i, j) == aa and at(lag, i, j) == delta and at(rlag, i, j) == wanted
                for j in faces
            )
            a, b, d, t = map(exact, (aa, bb, delta, wanted))
            assert a - b == d and Fraction(1, 2) <= a / b <= 2
            spacing = exact(math.ulp(aa))
            assert spacing == exact(math.ulp(bb)) and (d / spacing).denominator == 1
            nearest = nearest_integer(t / spacing) * spacing
            lower_bound = abs(nearest - t) - exact(math.ulp(wanted)) / 2
            original_budget = budget("membrane_bulk_difference_mol_m3", wanted)
            irreducible = lower_bound > exact(original_budget)
            if irreducible:
                impossible.append((ion, name))
            requested = (
                exact(dt)
                * sum((exact(at(fg, i, j)) * exact(areas[j]) for j in faces), Fraction(0))
                / exact(volumes[c])
            )
            stable_error = float(abs(requested - t)) / original_budget
            stable_scores.append(stable_error)
            reference_projected = exact(at(rmem, i, face)) - exact(at(rcell, i, c))
            record = dict(
                ion=ion,
                cell_id=name,
                membrane_ids=[cg["membrane_ids"][j] for j in faces],
                indices=dict(ion=i, cell=c, membranes=faces),
                source_frames=dict(membrane_commit=commit, junction_commit=gap, clip_bulk=clip),
                actual_membrane=aa,
                actual_bulk=bb,
                actual_difference=delta,
                reference_membrane_projected=at(rmem, i, face),
                reference_bulk_projected=at(rcell, i, c),
                reference_difference=wanted,
                exact_reference_difference_from_saved_projected_operands=float(reference_projected),
                difference_error=float(d - t),
                fixed_budget=original_budget,
                error_over_budget=float(abs(d - t)) / original_budget,
                operand_spacing=float(spacing),
                difference_to_nearest_lattice=float(abs(nearest - t)),
                nearest_lattice_value=float(nearest),
                actual_is_nearest_possible_stored_difference=d == nearest,
                even_perfect_reference_increment_rounds_to_actual_bulk=float(a - t) == bb,
                target_projection_uncertainty=math.ulp(wanted) / 2,
                irreducible_error_lower_bound_including_target_projection=float(lower_bound),
                original_budget_unattainable_by_any_same_binade_operand_pair=irreducible,
                exact_error_decomposition=dict(
                    actual_operand_deviation_from_projected_reference=float(
                        d - reference_projected
                    ),
                    reference_operand_projection_vs_stored_reference_diagnostic=float(
                        reference_projected - t
                    ),
                    identity_verified=(d - reference_projected) + (reference_projected - t)
                    == d - t,
                ),
                saved_flux_recomposition=dict(
                    method=(
                        "Exact rational dt * sum(saved junction flux * supplied area for actual "
                        "owner) / supplied volume; no flux/rate/model evaluation"
                    ),
                    value=float(requested),
                    exact_ratio=rational(requested),
                    error_over_original_difference_budget=stable_error,
                    quantized_raw_difference_minus_saved_flux_recomposition=float(d - requested),
                    saved_flux_recomposition_minus_reference_difference=float(requested - t),
                ),
                exact_operands=dict(
                    membrane=rational(a),
                    bulk=rational(b),
                    difference=rational(d),
                    target=rational(t),
                ),
            )
            details.append(record)
    write(
        "per-owner-decomposition",
        dict(
            rows=details,
            impossible_same_binade_targets=[dict(ion=i, cell_id=c) for i, c in impossible],
            maximum_saved_flux_recomposition_error_over_unchanged_budget=max(stable_scores),
        ),
    )
    # All conservation statements below are measures of ARCHIVED ledgers and
    # saved fluxes, not a new physical conservation or reference trajectory run.
    ledgers = {
        name: saved("ledger." + name)["values"]
        for name in (
            "boundary_clamp_change_mol",
            "collocated_transport_change_mol",
            "smoothing_change_mol",
            "membrane_transfer_mol",
            "native_environment_exchange_mol",
            "fast_exchange_defect_mol",
            "gap_net_outward_mol",
            "clipping_added_mol",
            "cell_change_mol",
            "environment_change_mol",
            "cell_accounting_residual_mol",
            "environment_accounting_residual_mol",
        )
    }
    balances = []
    partners = definition["junction_geometry"]["partner"]
    lengths = definition["junction_geometry"]["gap_length_m"]
    weights = definition["junction_geometry"]["gap_weights"]
    for ion in moving:
        i = ion_ids.index(ion)
        total_change = exact(ledgers["cell_change_mol"][i]) + exact(
            ledgers["environment_change_mol"][i]
        )
        nongap = sum(
            (
                exact(ledgers[name][i])
                for name in (
                    "boundary_clamp_change_mol",
                    "collocated_transport_change_mol",
                    "smoothing_change_mol",
                    "clipping_added_mol",
                )
            ),
            Fraction(0),
        )
        gap_out = exact(dt) * sum(
            (exact(at(fg, i, j)) * exact(area) for j, area in enumerate(areas)), Fraction(0)
        )
        pairs = []
        for j, k in enumerate(partners):
            if j > k:
                continue
            amount = exact(dt) * (
                exact(at(fg, i, j)) * exact(areas[j])
                + (exact(at(fg, i, k)) * exact(areas[k]) if j != k else 0)
            )
            scaled_sum = exact(at(fg, i, j)) * exact(lengths[j])
            if j != k:
                scaled_sum += exact(at(fg, i, k)) * exact(lengths[k])
            asymmetry_prediction = (
                exact(dt)
                * exact(areas[j])
                * exact(at(fg, i, j))
                * (1 - exact(lengths[j]) / exact(lengths[k]))
                if j != k and areas[j] == areas[k]
                else Fraction(0)
            )
            pairs.append(
                dict(
                    membrane_ids=[cg["membrane_ids"][j], cg["membrane_ids"][k]],
                    areas_m2=[areas[j], areas[k]],
                    saved_outward_fluxes=[at(fg, i, j), at(fg, i, k)],
                    signed_outward_amount_mol=float(amount),
                    directed_path_lengths_m=[lengths[j], lengths[k]],
                    directed_gap_weights=[weights[j], weights[k]],
                    directed_diffusivities_m2_s=[
                        definition["ions"]["gap_diffusion_m2_s"][i][j],
                        definition["ions"]["gap_diffusion_m2_s"][i][k],
                    ],
                    saved_flux_times_length_pair_sum=float(scaled_sum),
                    unequal_path_prediction_from_saved_first_flux_mol=float(asymmetry_prediction),
                    pair_imbalance_minus_unequal_path_prediction_mol=float(
                        amount - asymmetry_prediction
                    ),
                )
            )
        balances.append(
            dict(
                ion=ion,
                actual_saved_ledgers={name: values[i] for name, values in ledgers.items()},
                cell_plus_environment_change_mol=float(total_change),
                nongap_boundary_collocation_smoothing_clipping_mol=float(nongap),
                gap_outward_from_saved_fluxes_mol=float(gap_out),
                net_minus_nongap_plus_gap_mol=float(total_change - nongap + gap_out),
                moving_membrane_exchange_residual_mol=ledgers["native_environment_exchange_mol"][i]
                + ledgers["membrane_transfer_mol"][i],
                directed_gap_pair_imbalances=pairs,
            )
        )
    write(
        "retained-material-accounting",
        dict(
            fast_update_ecm=definition["parameters"]["fast_update_ecm"],
            cluster_open=definition["parameters"]["cluster_open"],
            rows=balances,
            negative_environment_retained=any(
                value < 0 for value in saved("candidate.environment_mol_m3")["values"]
            ),
            physical_material_parity_claimed=False,
        ),
    )
    worst = max(details, key=lambda row: row["error_over_budget"])
    assert (
        worst["ion"] == "Cl"
        and worst["cell_id"] == "cell-1"
        and worst["actual_is_nearest_possible_stored_difference"]
        and worst["original_budget_unattainable_by_any_same_binade_operand_pair"]
    )
    assert all(sha(ARCHIVE / name) == pin for name, pin in pins.items())
    assert not any(name.split(".")[0] in BLOCKED for name in sys.modules)
    result = dict(
        kind="cells.betse_ecm_retained_material_diagnosis@1",
        status="retained_failure_diagnosed_no_source_change",
        utc=datetime.now(timezone.utc).isoformat(),
        source=str(Path(__file__)),
        source_sha256=sha(Path(__file__)),
        saved_actual_native_numeric_matches=len(native_keys),
        saved_actual_native_bitwise_matches=bitwise,
        saved_actual_reference_fields=len(all_fields),
        failed_fields=failed_fields,
        reference_resolution_over_budget=worst_resolution,
        worst_identity=dict(
            ion=worst["ion"], cell=worst["cell_id"], membrane=worst["membrane_ids"][0]
        ),
        worst_error_over_budget=worst["error_over_budget"],
        worst_target_unattainable_on_raw_stored_difference_lattice=True,
        maximum_saved_flux_recomposition_error_over_unchanged_budget=max(stable_scores),
        comparator_math_or_index_or_units_bug_found=False,
        reference_target=(
            "Difference of high-precision carried membrane and bulk states, projected once; "
            "distinct from subtraction of separately rounded stored operands"
        ),
        raw_native_observable=(
            "Exact subtraction of nearly equal binary64 operands after a quantized junction "
            "addition; correct literal source behavior"
        ),
        original_case_and_panel_remain_failed=True,
        new_passing_scientific_cases=0,
        inputs_changed=False,
        budgets_changed=False,
        shared_or_frozen_source_edited=False,
        simulations=False,
        flux_laws_evaluated=False,
        reference_evaluators_run=False,
        tests_collected=False,
        active_jobs_polled=False,
        PROGRESS_edited=False,
        scientific_modules_imported=[],
        resource_bounds=dict(
            address_space_bytes=512 * 2**20, cpu_seconds=60, max_decoded_member_bytes=MAX_MEMBER
        ),
        peak_rss_bytes=int(
            next(
                line.split()[1]
                for line in Path("/proc/self/status").read_text().splitlines()
                if line.startswith("VmHWM:")
            )
        )
        * 1024,
        rusage_history_high_water_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        memory_metric=(
            "peak_rss_bytes is current PID /proc VmHWM; rusage history is retained separately "
            "and is not used as this audit's charged-memory estimate"
        ),
        predecessor_metadata_correction=(
            "01 used process-history ru_maxrss as current audit RSS.02 retains the same saved-data "
            "comparisons and adds current-PID VmHWM plus directed path attribution;01 is preserved"
        ),
        input_sha256=pins,
        artifact_sha256={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
    )
    write("result", result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "saved_actual_native_numeric_matches",
                    "saved_actual_native_bitwise_matches",
                    "saved_actual_reference_fields",
                    "worst_error_over_budget",
                    "worst_target_unattainable_on_raw_stored_difference_lattice",
                    "maximum_saved_flux_recomposition_error_over_unchanged_budget",
                    "peak_rss_bytes",
                )
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        OUT.mkdir(exist_ok=True)
        if not (OUT / "failure.json").exists():
            write(
                "failure",
                dict(
                    type=type(error).__name__,
                    reason=str(error),
                    traceback=traceback.format_exc(),
                    simulations=False,
                    reference_evaluators_run=False,
                ),
            )
        raise
