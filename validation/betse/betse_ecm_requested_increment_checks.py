"""Pure-stdlib column, byte-identity and requested-operand semantics checks."""

import ast
import math
import struct
import zipfile
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from fractions import Fraction

from validation.betse.betse_ecm_requested_increment_reference import KEY, compare_increment

LEGACY_LEDGERS = (
    "boundary_clamp_change_mol",
    "collocated_transport_change_mol",
    "smoothing_change_mol",
    "membrane_transfer_mol",
    "native_environment_exchange_mol",
    "conservative_environment_exchange_mol",
    "fast_exchange_defect_mol",
    "gap_net_outward_mol",
    "clipping_added_mol",
    "cell_change_mol",
    "environment_change_mol",
    "cell_accounting_residual_mol",
    "environment_accounting_residual_mol",
    "membrane_bulk_difference_mol_m3",
    "source_voltage_nonce_delta_V",
)


def get(value, key):
    return value[key] if isinstance(value, Mapping) else getattr(value, key)


def plain(value):
    if is_dataclass(value):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if hasattr(value, "tolist"):
        return plain(value.tolist())
    if type(value) is float and not math.isfinite(value):
        return dict(nonfinite_binary64_bits_be=struct.pack(">d", value).hex())
    return value


def array_leaves(value, prefix="payload"):
    """Retain every typed array without importing its scientific owner."""
    if hasattr(value, "dtype") and hasattr(value, "shape"):
        return {prefix: value}
    if is_dataclass(value):
        value = {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, (tuple, list)):
        items = enumerate(value)
    else:
        return {}
    result = {}
    for key, item in items:
        result.update(array_leaves(item, prefix + "__" + str(key)))
    return result


def flat(value, prefix=""):
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            result.update(flat(item, prefix + ("." if prefix else "") + key))
        return result
    return {} if value is None else {prefix: value}


def columns(rows, *, ledgers=True):
    result = {}
    for step, row in enumerate(rows):
        prefix = "step_" + str(step) + "."
        for index, frame in enumerate(get(row, "frames")):
            result.update(flat(get(frame, "values"), prefix + "frame_" + str(index)))
        for index, record in enumerate(get(row, "environment_records")):
            record = record if isinstance(record, Mapping) else record._asdict()
            result.update(
                flat(
                    {key: value for key, value in record.items() if key != "ion_id"},
                    prefix + "environment_" + str(index),
                )
            )
        candidate = get(row, "candidate")
        result.update(
            flat(
                candidate if isinstance(candidate, Mapping) else candidate.values,
                prefix + "candidate",
            )
        )
        if ledgers:
            source = row["ledgers"] if isinstance(row, Mapping) else row.diagnostics
            result.update(flat({key: source[key] for key in LEGACY_LEDGERS}, prefix + "ledger"))
    return result


def requested(rows):
    return [
        plain((row["ledgers"] if isinstance(row, Mapping) else row.diagnostics)[KEY])
        for row in rows
    ]


def metadata(rows):
    return [
        [[get(frame, "stage"), get(frame, "ion_id")] for frame in get(row, "frames")]
        for row in rows
    ]


def numeric(value):
    if isinstance(value, Mapping) and set(value) == {"shape", "dtype", "values"}:
        dtype = value["dtype"]
        shape = tuple(value["shape"])
        data = value["values"]
    else:
        dtype = value.dtype.str if hasattr(value, "dtype") else "<f8"
        shape = tuple(value.shape) if hasattr(value, "shape") else None
        data = plain(value)

    def visit(item):
        if type(item) in (tuple, list):
            parsed = [visit(child) for child in item]
            nested = parsed[0][0] if parsed else ()
            if any(row[0] != nested for row in parsed):
                raise ValueError("Ragged retained numeric column")
            return (len(item), *nested), [v for row in parsed for v in row[1]]
        if type(item) not in (int, float) or not math.isfinite(item):
            raise ValueError("Nonfinite or nonnumeric retained column")
        return (), [float(item)]

    inferred, values = visit(data)
    if shape is not None and shape != inferred:
        raise ValueError("Retained column shape mismatch")
    return dict(shape=list(inferred), dtype=dtype, values=data), b"".join(
        struct.pack(">d", v) for v in values
    )


def described(columns):
    return {key: numeric(value)[0] for key, value in columns.items()}


def retained_columns(path, category):
    """Read bounded float64 legacy NPZ columns without a scientific dependency."""
    result = {}
    prefix = category + "__"
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(item.file_size for item in entries) > 100 * 2**20:
            raise ValueError("Unbounded retained ECM archive")
        for item in entries:
            if not item.filename.startswith(prefix):
                continue
            if not item.filename.endswith(".npy") or item.file_size > 2**20:
                raise ValueError("Invalid retained numeric entry")
            with archive.open(item) as stream:
                if stream.read(6) != b"\x93NUMPY":
                    raise ValueError("Require NPY numeric evidence")
                version = stream.read(2)
                if version == b"\x01\x00":
                    width, code, encoding = 2, "<H", "latin1"
                elif version in (b"\x02\x00", b"\x03\x00"):
                    width, code = 4, "<I"
                    encoding = "utf8" if version == b"\x03\x00" else "latin1"
                else:
                    raise ValueError("Unsupported retained NPY version")
                size = struct.unpack(code, stream.read(width))[0]
                if size > 65536:
                    raise ValueError("Unbounded NPY header")
                header = ast.literal_eval(stream.read(size).decode(encoding))
                if set(header) != {"descr", "fortran_order", "shape"}:
                    raise ValueError("Incomplete retained NPY descriptor")
                shape, dtype = header["shape"], header["descr"]
                if (
                    header["fortran_order"]
                    or dtype not in ("<f8", ">f8")
                    or type(shape) is not tuple
                    or any(type(n) is not int or not 0 < n <= 100000 for n in shape)
                ):
                    raise ValueError("Require finite bounded C-order float64 columns")
                count = math.prod(shape)
                if count > 100000:
                    raise ValueError("Unbounded retained column")
                raw = stream.read(count * 8 + 1)
                if len(raw) != count * 8:
                    raise ValueError("Incomplete retained NPY numeric payload")
                values = iter(value[0] for value in struct.iter_unpack(dtype[0] + "d", raw))

                def reshape(dimensions, values=values):
                    return (
                        [reshape(dimensions[1:]) for _ in range(dimensions[0])]
                        if dimensions
                        else next(values)
                    )

                name = item.filename[len(prefix) : -4].replace("__", ".")
                if name in result:
                    raise ValueError("Duplicate retained numeric column")
                result[name] = dict(shape=list(shape), dtype=dtype, values=reshape(shape))
    if not result:
        raise ValueError("Missing retained column category: " + category)
    return result


def exact_columns(actual, expected):
    names = sorted(set(actual) | set(expected))
    rows = []
    for name in names:
        if name not in actual or name not in expected:
            rows.append(
                dict(
                    field=name,
                    present_in_actual=name in actual,
                    present_in_expected=name in expected,
                    exact=False,
                )
            )
            continue
        a, ab = numeric(actual[name])
        b, bb = numeric(expected[name])
        rows.append(
            dict(
                field=name,
                shape=a["shape"],
                expected_shape=b["shape"],
                dtype=a["dtype"],
                expected_dtype=b["dtype"],
                exact=a["shape"] == b["shape"] and a["dtype"] == b["dtype"] and ab == bb,
            )
        )
    return dict(columns=len(names), all_exact=all(row["exact"] for row in rows), fields=rows)


def increment_report(actual, reference, refined):
    if len(actual) != len(reference) or len(reference) != len(refined):
        raise ValueError("Complete requested-increment history lengths disagree")
    rows = []
    for index, (a, b, c) in enumerate(zip(actual, reference, refined, strict=True)):
        rows.append(
            dict(
                step=index,
                actual_to_reference=compare_increment(a, b),
                reference_resolution=compare_increment(b, c),
            )
        )
    return dict(
        steps=rows,
        maximum_error_over_budget=max(
            row["actual_to_reference"]["maximum_error_over_budget"] for row in rows
        ),
        maximum_reference_resolution=max(
            row["reference_resolution"]["maximum_error_over_budget"] for row in rows
        ),
    )


def assert_increment(report):
    assert report["maximum_error_over_budget"] <= 1
    assert report["maximum_reference_resolution"] <= 0.1


def corrupt_requested(inputs, rows, case):
    """Declared wrong observables; no production numerical operation is used."""
    from copy import deepcopy

    result = deepcopy(requested(rows))
    if case == "wrong-sign":
        return [[[-value for value in row] for row in matrix] for matrix in result]
    if case == "wrong-cell-axis":
        for matrix in result:
            for row in matrix:
                row[0], row[1] = row[1], row[0]
        return result
    names = inputs["definition"]["environment_geometry_definition"]["current_definition"]["ions"][
        "ids"
    ]
    moving = inputs["definition"]["ions"]["moving_ids"]
    if case == "stationary-nonzero":
        index = next(i for i, name in enumerate(names) if name not in moving)
        result[0][index][0] = 1e-6
        return result
    if case not in ("clipped-raw-lag", "rounded-state-difference"):
        raise ValueError("Unknown requested-increment corruption")
    owner = inputs["definition"]["environment_geometry_definition"]["current_definition"][
        "geometry"
    ]["owner"]
    for step, row in enumerate(rows):
        for i, name in enumerate(names):
            for cell in range(len(result[step][i])):
                if case == "clipped-raw-lag":
                    ledger = row["ledgers"] if isinstance(row, Mapping) else row.diagnostics
                    result[step][i][cell] = plain(ledger["membrane_bulk_difference_mol_m3"])[i][
                        owner.index(cell)
                    ]
                elif name in moving:
                    frames = get(row, "frames")
                    endpoints = [
                        plain(
                            get(
                                next(
                                    frame
                                    for frame in frames
                                    if get(frame, "stage") == stage and get(frame, "ion_id") == name
                                ),
                                "values",
                            )
                        )["cell_mol_m3"][i][cell]
                        for stage in ("membrane_commit", "junction_commit")
                    ]
                    result[step][i][cell] = endpoints[0] - endpoints[1]
    return result


def semantics(inputs, rows):
    declared = inputs["definition"]
    geometry = declared["environment_geometry_definition"]
    cg = geometry["current_definition"]["geometry"]
    ion_ids = geometry["current_definition"]["ions"]["ids"]
    volumes = geometry["geometry"]["cell_volume_m3"]
    moving = declared["ions"]["moving_ids"]
    owner = cg["owner"]
    areas = cg["membrane_area_m2"]
    previous = inputs["initial"]
    reports = []
    for step, row in enumerate(rows):
        frames = get(row, "frames")
        candidate = get(row, "candidate")
        candidate = plain(candidate if isinstance(candidate, Mapping) else candidate.values)
        diagnostics = row["ledgers"] if isinstance(row, Mapping) else row.diagnostics
        quantity = plain(diagnostics[KEY])
        raw = plain(diagnostics["membrane_bulk_difference_mol_m3"])
        row_reports = []
        local_target = []
        for i, ion in enumerate(ion_ids):
            if ion not in moving:
                local_target.append([0.0] * len(volumes))
                row_reports.append(
                    dict(
                        ion=ion,
                        stationary=True,
                        requested_zero=all(v == 0 for v in quantity[i]),
                        cell_unchanged=candidate["cell_mol_m3"][i] == previous["cell_mol_m3"][i],
                        membrane_unchanged=candidate["membrane_mol_m3"][i]
                        == previous["membrane_mol_m3"][i],
                    )
                )
                continue
            before = plain(
                get(
                    next(
                        f
                        for f in frames
                        if get(f, "stage") == "membrane_commit" and get(f, "ion_id") == ion
                    ),
                    "values",
                )
            )
            after = plain(
                get(
                    next(
                        f
                        for f in frames
                        if get(f, "stage") == "junction_commit" and get(f, "ion_id") == ion
                    ),
                    "values",
                )
            )
            target = []
            cells = []
            for c, volume in enumerate(volumes):
                total = sum(
                    (
                        Fraction.from_float(float(candidate["junction_flux_mol_m2_s"][i][j]))
                        * Fraction.from_float(float(areas[j]))
                        for j, a in enumerate(owner)
                        if a == c
                    ),
                    Fraction(0),
                )
                target.append(
                    float(
                        Fraction.from_float(float(inputs["steps"][step]["dt_s"]))
                        * total
                        / Fraction.from_float(float(volume))
                    )
                )
                a, b = before["cell_mol_m3"][i][c], after["cell_mol_m3"][i][c]
                expected = a - quantity[i][c]
                final = 0.0 if b < 0 else b
                cells.append(
                    dict(
                        cell_id=cg["cell_ids"][c],
                        before_gap=a,
                        requested_outward_increment=quantity[i][c],
                        after_gap=b,
                        final_bulk=candidate["cell_mol_m3"][i][c],
                        exact_requested_operand_reconstructs_gap_update=struct.pack(">d", expected)
                        == struct.pack(">d", b),
                        clipped=b < 0,
                        clip_preserved=struct.pack(">d", final)
                        == struct.pack(">d", candidate["cell_mol_m3"][i][c]),
                    )
                )
            local_target.append(target)
            row_reports.append(dict(ion=ion, stationary=False, cells=cells))
        endpoint = all(
            struct.pack(">d", raw[i][j])
            == struct.pack(
                ">d", candidate["membrane_mol_m3"][i][j] - candidate["cell_mol_m3"][i][c]
            )
            for i in range(len(ion_ids))
            for j, c in enumerate(owner)
        )
        reports.append(
            dict(
                step=step,
                ions=row_reports,
                raw_lag_is_unchanged_stored_endpoint_subtraction=endpoint,
                clipping_added_mol=plain(diagnostics["clipping_added_mol"]),
                conditional_saved_flux_target=local_target,
                conditional_local_comparison=compare_increment(quantity, local_target),
            )
        )
        previous = candidate
    return dict(
        steps=reports,
        meaning=(
            "Requested outward junction operand before rounded bulk addition and clipping; "
            "distinct from the final raw lag"
        ),
        physical_conservation_claim=False,
    )


def assert_semantics(report):
    for step in report["steps"]:
        assert step["raw_lag_is_unchanged_stored_endpoint_subtraction"]
        assert step["conditional_local_comparison"]["maximum_error_over_budget"] <= 1
        for ion in step["ions"]:
            if ion["stationary"]:
                assert ion["requested_zero"] and ion["cell_unchanged"] and ion["membrane_unchanged"]
            else:
                assert all(
                    cell["exact_requested_operand_reconstructs_gap_update"]
                    and cell["clip_preserved"]
                    for cell in ion["cells"]
                )
