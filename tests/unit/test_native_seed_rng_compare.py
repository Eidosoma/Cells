"""Complete synthetic saved states only; no random generator or NumPy imports."""

import copy
import hashlib
import os

import pytest

from validation.betse import native_seed_rng_compare as compare
from validation.betse import native_seed_rng_compare_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit native-blocked saved-state software release required")
    with software.blocked(tmp_path):
        yield


def state(*, dtype="<u4", gaussian="0000000000000080", python_cache=None):
    # Deterministic fixture bytes, never a generated RNG state or seeded stream.
    raw = b"".join((i + 1).to_bytes(4, "little" if dtype == "<u4" else "big") for i in range(624))
    return dict(
        numpy_random=[
            "MT19937",
            dict(__ndarray__=True, dtype=dtype, shape=[624], strides=[4], raw_bytes_hex=raw.hex()),
            623,
            1,
            dict(float64_bits=gaussian),
        ],
        python_random=[
            3,
            [i + 7 for i in range(624)] + [624],
            None if python_cache is None else dict(float64_bits=python_cache),
        ],
        initial_random_reset_or_replacement=False,
    )


def wire(value):
    """Explicit original independent tree/column schema, with fixed MT array."""
    columns = {}

    def encode(item):
        if type(item) is dict and item.get("__ndarray__") is True:
            name = "native_000000"
            columns[name] = {
                key: copy.deepcopy(item[key]) for key in ("dtype", "shape", "raw_bytes_hex")
            }
            return dict(
                type="array",
                layout=dict(
                    dtype=item["dtype"],
                    shape=list(item["shape"]),
                    strides_bytes=list(item["strides"]),
                    C_contiguous=True,
                    F_contiguous=True,
                ),
                column=name,
                sha256=hashlib.sha256(bytes.fromhex(item["raw_bytes_hex"])).hexdigest(),
            )
        if type(item) is dict and set(item) == {"float64_bits"}:
            return dict(type="float", bits=item["float64_bits"])
        if type(item) is dict:
            return dict(type="dict", values=[[encode(k), encode(v)] for k, v in item.items()])
        if type(item) is list:
            return dict(type="tuple", values=[encode(v) for v in item])
        return dict(type=type(item).__name__, value=item)

    return dict(tree=encode(value), columns=columns)


@pytest.mark.parametrize("dtype", ("<u4", ">u4"))
@pytest.mark.parametrize(
    "bits", ("0000000000000000", "0000000000000080", "010000000000f87f", "000000000000f07f")
)
@pytest.mark.parametrize("cached", (False, True))
def test_rng_compare_complete_saved_state_preserves_every_bit(dtype, bits, cached):
    left = state(dtype=dtype, gaussian=bits, python_cache=bits if cached else None)
    right = wire(left)
    original = copy.deepcopy((left, right))
    result = compare.compare_states(left, right)
    assert result["states_equal"] is True
    assert result["normalized"]["demo"] == result["normalized"]["reference"]
    assert result["normalized"]["demo"]["numpy"][4] == bits
    assert result["common_starting_authority_established"] is False
    assert result["input_runtime_epoch_and_producer_authenticated"] is False
    assert result["scientific_physical_checkpoint_credit"] == 0
    assert (left, right) == original


@pytest.mark.parametrize(
    "field",
    (
        "numpy_first",
        "numpy_last",
        "numpy_index",
        "numpy_flag",
        "numpy_cache",
        "python_first",
        "python_last",
        "python_index",
        "python_cache",
        "dtype",
    ),
)
def test_rng_compare_distinct_valid_states_never_match(field):
    left, other = state(), state()
    if field.startswith("numpy_") and field in ("numpy_first", "numpy_last"):
        raw = bytearray.fromhex(other["numpy_random"][1]["raw_bytes_hex"])
        raw[0 if field == "numpy_first" else -1] ^= 1
        other["numpy_random"][1]["raw_bytes_hex"] = raw.hex()
    elif field == "numpy_index":
        other["numpy_random"][2] = 624
    elif field == "numpy_flag":
        other["numpy_random"][3] = 0
    elif field == "numpy_cache":
        other["numpy_random"][4]["float64_bits"] = "0000000000000000"
    elif field in ("python_first", "python_last"):
        other["python_random"][1][0 if field == "python_first" else 623] ^= 1
    elif field == "python_index":
        other["python_random"][1][-1] = 623
    elif field == "python_cache":
        other["python_random"][2] = dict(float64_bits="0000000000000000")
    elif field == "dtype":
        other["numpy_random"][1]["dtype"] = ">u4"
    result = compare.compare_states(left, wire(other))
    assert result["states_equal"] is False
    assert result["numpy_equal"] is (not field.startswith("numpy_") and field != "dtype")
    assert result["python_equal"] is (not field.startswith("python_"))
    assert result["common_starting_authority_established"] is False


@pytest.mark.parametrize(
    "case",
    (
        "reset",
        "extra",
        "short_numpy",
        "short_python",
        "word_count",
        "bool_word",
        "wide_word",
        "negative_word",
        "bad_index",
        "bool_index",
        "bool_version",
        "old_version",
        "short_bits",
        "upper_bits",
        "extra_bits",
        "shape",
        "stride",
        "all_zero",
        "dtype",
        "bool_flag",
    ),
)
@pytest.mark.parametrize("format_name", ("demo", "reference"))
def test_rng_compare_rejects_malformed_or_partial_saved_states(case, format_name):
    value = state()
    if case == "reset":
        value["initial_random_reset_or_replacement"] = True
    elif case == "extra":
        value["claimed_authority"] = True
    elif case == "short_numpy":
        value["numpy_random"].pop()
    elif case == "short_python":
        value["python_random"].pop()
    elif case == "word_count":
        value["python_random"][1].pop()
    elif case in ("bool_word", "wide_word", "negative_word"):
        value["python_random"][1][0] = {"bool_word": True, "wide_word": 2**32, "negative_word": -1}[
            case
        ]
    elif case in ("bad_index", "bool_index"):
        value["numpy_random"][2] = 625 if case == "bad_index" else True
    elif case in ("bool_version", "old_version"):
        value["python_random"][0] = True if case == "bool_version" else 2
    elif case in ("short_bits", "upper_bits", "extra_bits"):
        value["numpy_random"][4] = dict(
            float64_bits={
                "short_bits": "00",
                "upper_bits": "ABCDEF0000000000",
                "extra_bits": "00" * 9,
            }[case]
        )
    elif case == "shape":
        value["numpy_random"][1]["shape"] = [623]
    elif case == "stride":
        value["numpy_random"][1]["strides"] = [-4]
    elif case == "all_zero":
        value["numpy_random"][1]["raw_bytes_hex"] = "00" * 2496
    elif case == "dtype":
        value["numpy_random"][1]["dtype"] = "<i4"
    elif case == "bool_flag":
        value["numpy_random"][3] = True
    with pytest.raises(ValueError):
        if format_name == "demo":
            compare.demo_state(value)
        else:
            compare.reference_state(wire(value))


@pytest.mark.parametrize(
    "case",
    (
        "unused_column",
        "digest",
        "duplicate_key",
        "list_for_tuple",
        "false_contiguity",
        "untyped_contiguity",
        "column_dtype",
        "column_shape",
        "external_blob",
        "float_subtype",
        "header_extra",
    ),
)
def test_rng_compare_reference_exact_wire_and_column_binding(case):
    value = wire(state())
    mt = value["tree"]["values"][0][1]["values"]
    if case == "unused_column":
        value["columns"]["extra"] = copy.deepcopy(value["columns"]["native_000000"])
    elif case == "digest":
        mt[1]["sha256"] = "0" * 64
    elif case == "duplicate_key":
        value["tree"]["values"][1][0] = copy.deepcopy(value["tree"]["values"][0][0])
    elif case == "list_for_tuple":
        value["tree"]["values"][0][1]["type"] = "list"
    elif case in ("false_contiguity", "untyped_contiguity"):
        mt[1]["layout"]["C_contiguous"] = False if case == "false_contiguity" else 1
    elif case == "column_dtype":
        value["columns"]["native_000000"]["dtype"] = ">u4"
    elif case == "column_shape":
        value["columns"]["native_000000"]["shape"] = [623]
    elif case == "external_blob":
        value["columns"]["native_000000"]["raw_bytes_hex"] = dict(path="untrusted.bin")
    elif case == "float_subtype":
        mt[4].update(type="numpy_scalar", dtype="<f8")
    elif case == "header_extra":
        mt[1]["layout"]["offset"] = 0
    with pytest.raises(ValueError):
        compare.reference_state(value)


def test_rng_compare_storage_names_and_mapping_order_are_not_state():
    left = state()
    right = wire(left)
    mt = right["tree"]["values"][0][1]["values"]
    right["columns"]["renamed"] = right["columns"].pop(mt[1]["column"])
    mt[1]["column"] = "renamed"
    right["tree"]["values"].reverse()
    assert compare.compare_states(left, right)["states_equal"] is True


def test_rng_compare_output_never_aliases_mutable_source_metadata():
    left = state()
    right = wire(left)
    result = compare.compare_states(left, right)
    before = copy.deepcopy((left, right))
    result["normalized"]["demo"]["numpy"][1]["shape"][0] = 1
    result["normalized"]["demo"]["python"][1][0] = 99
    result["normalized"]["reference"]["numpy"][1]["strides_bytes"][0] = 99
    result["normalized"]["reference"]["python"][1][0] = 99
    assert (left, right) == before


def test_rng_compare_plan_is_data_only_not_stream_or_producer_authority():
    plan = compare.source_plan()
    assert plan["input_runtime_epoch_and_producer_authentication"] == "required from caller"
    assert plan["RNG_import_draw_reset_or_owner_construction"] is False
    assert plan["common_starting_authority_established"] is False
