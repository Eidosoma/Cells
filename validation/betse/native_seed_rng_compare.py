"""Exact, stdlib-only comparison of the two saved pre-SEED RNG state wires.

Inputs are decoded saved records, never live generators. Callers must first
authenticate each capture, producer, observation epoch and input/runtime witness.
Matching these records does not establish that authority or reset either stream.
"""

import hashlib

KIND = "cells.saved_initial_rng_state_comparison@1"
STATE_KEYS = {"numpy_random", "python_random", "initial_random_reset_or_replacement"}


def source_plan():
    return dict(
        kind=KIND,
        demo_wire="archive.snapshot",
        reference_wire="independent typed tree/columns",
        complete_MT_words_positions_and_Gaussian_bits=True,
        exact_dtype_layout_and_byte_order=True,
        input_runtime_epoch_and_producer_authentication="required from caller",
        RNG_import_draw_reset_or_owner_construction=False,
        common_starting_authority_established=False,
        scientific_physical_checkpoint_credit=0,
    )


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, keys):
    _require(type(value) is dict and set(value) == set(keys), "Exact saved RNG field roster")


def _integer(value, maximum):
    _require(type(value) is int and 0 <= value <= maximum, "Exact RNG integer extent")
    return value


def _hex(value, size):
    _require(type(value) is str and len(value) == 2 * size, "Complete inline RNG bytes required")
    raw = bytes.fromhex(value)
    _require(raw.hex() == value, "Canonical saved RNG hexadecimal bytes required")
    return value


def _float(value):
    _keys(value, {"float64_bits"})
    return _hex(value["float64_bits"], 8)


def _state(mt, py):
    """Validate the common fixed-size data, without constructing an RNG."""
    _require(
        type(mt) is list and len(mt) == 5 and type(mt[0]) is str and mt[0] == "MT19937",
        "Full NumPy MT state",
    )
    words = mt[1]
    _keys(words, {"dtype", "shape", "strides_bytes", "raw_bytes_hex"})
    _require(
        type(words["dtype"]) is str
        and words["dtype"] in ("<u4", ">u4")
        and type(words["shape"]) is list
        and len(words["shape"]) == 1
        and type(words["shape"][0]) is int
        and words["shape"][0] == 624
        and type(words["strides_bytes"]) is list
        and len(words["strides_bytes"]) == 1
        and type(words["strides_bytes"][0]) is int
        and words["strides_bytes"][0] == 4,
        "Exact native MT uint32/624/contiguous source layout",
    )
    raw = _hex(words["raw_bytes_hex"], 2496)
    _require(any(bytes.fromhex(raw)), "All-zero MT word state is unavailable")
    _integer(mt[2], 624)
    _integer(mt[3], 1)
    _hex(mt[4], 8)
    _require(
        type(py) is list
        and len(py) == 3
        and type(py[0]) is int
        and py[0] == 3
        and type(py[1]) is list
        and len(py[1]) == 625,
        "Complete version-3 Python MT state",
    )
    for value in py[1][:-1]:
        _integer(value, 2**32 - 1)
    _integer(py[1][-1], 624)
    if py[2] is not None:
        _hex(py[2], 8)
    # Own fresh metadata containers. No returned list aliases a supplied wire.
    return dict(
        numpy=[mt[0], {**words, "shape": [624], "strides_bytes": [4]}, mt[2], mt[3], mt[4]],
        python=[3, list(py[1]), py[2]],
    )


def demo_state(value):
    """Normalize a complete archive.snapshot record with all original bits."""
    _keys(value, STATE_KEYS)
    _require(value["initial_random_reset_or_replacement"] is False, "Observation only")
    mt, py = value["numpy_random"], value["python_random"]
    _require(type(mt) is list and len(mt) == 5, "Complete NumPy tuple wire")
    _require(type(py) is list and len(py) == 3, "Complete Python tuple wire")
    array = mt[1]
    _keys(array, {"__ndarray__", "dtype", "shape", "strides", "raw_bytes_hex"})
    _require(array["__ndarray__"] is True, "Actual saved ndarray header")
    return _state(
        [
            mt[0],
            dict(
                dtype=array["dtype"],
                shape=array["shape"],
                strides_bytes=array["strides"],
                raw_bytes_hex=array["raw_bytes_hex"],
            ),
            mt[2],
            mt[3],
            _float(mt[4]),
        ],
        [py[0], py[1], None if py[2] is None else _float(py[2])],
    )


def _primitive(node, kind):
    _keys(node, {"type", "value"})
    types = {"str": str, "int": int, "bool": bool, "NoneType": type(None)}
    _require(node["type"] == kind and type(node["value"]) is types[kind], "Exact typed scalar")
    return node["value"]


def _tuple(node, count):
    _keys(node, {"type", "values"})
    _require(
        node["type"] == "tuple" and type(node["values"]) is list and len(node["values"]) == count,
        "Exact native tuple and complete item count",
    )
    return node["values"]


def _reference_float(node):
    _keys(node, {"type", "bits"})
    _require(node["type"] == "float", "Original Python Gaussian float required")
    return _hex(node["bits"], 8)


def reference_state(value):
    """Normalize the independent producer's fixed-size typed state capture.

    The two producers retain their own wire encoders. This adapter accepts only
    the one inline MT column; it neither expands arbitrary payloads nor searches
    nested epochs. Pass the separately authenticated before_seed_random_states
    capture, not a whole history or a reconstructed owner.
    """
    _keys(value, {"tree", "columns"})
    tree, columns = value["tree"], value["columns"]
    _keys(tree, {"type", "values"})
    _require(
        tree["type"] == "dict" and type(tree["values"]) is list and len(tree["values"]) == 3,
        "Exact independent observed-state mapping",
    )
    fields = {}
    for pair in tree["values"]:
        _require(type(pair) is list and len(pair) == 2, "Exact mapping pair")
        name = _primitive(pair[0], "str")
        _require(name in STATE_KEYS and name not in fields, "Unique declared state field")
        fields[name] = pair[1]
    _require(
        _primitive(fields["initial_random_reset_or_replacement"], "bool") is False,
        "Observation only",
    )
    mt, py = _tuple(fields["numpy_random"], 5), _tuple(fields["python_random"], 3)
    array = mt[1]
    _keys(array, {"type", "layout", "column", "sha256"})
    _require(array["type"] == "array" and type(array["column"]) is str, "Actual MT array node")
    _keys(columns, {array["column"]})
    column, layout = columns[array["column"]], array["layout"]
    _keys(column, {"dtype", "shape", "raw_bytes_hex"})
    _keys(layout, {"dtype", "shape", "strides_bytes", "C_contiguous", "F_contiguous"})
    _require(
        layout["C_contiguous"] is True
        and layout["F_contiguous"] is True
        and type(column["dtype"]) is str
        and type(column["shape"]) is list
        and len(column["shape"]) == 1
        and type(column["shape"][0]) is int
        and column["dtype"] == layout["dtype"]
        and column["shape"] == layout["shape"],
        "Exact MT column and source layout",
    )
    raw = _hex(column["raw_bytes_hex"], 2496)
    _require(
        type(array["sha256"]) is str
        and array["sha256"] == hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
        "Retained MT column digest changed",
    )
    return _state(
        [
            _primitive(mt[0], "str"),
            dict(
                dtype=layout["dtype"],
                shape=layout["shape"],
                strides_bytes=layout["strides_bytes"],
                raw_bytes_hex=raw,
            ),
            _primitive(mt[2], "int"),
            _primitive(mt[3], "int"),
            _reference_float(mt[4]),
        ],
        [
            _primitive(py[0], "int"),
            [_primitive(item, "int") for item in _tuple(py[1], 625)],
            _primitive(py[2], "NoneType")
            if type(py[2]) is dict and py[2].get("type") == "NoneType"
            else _reference_float(py[2]),
        ],
    )


def compare_states(demo_wire, reference_wire):
    """Compare recorded bits only; producer and common-start authority stay external."""
    demo, reference = demo_state(demo_wire), reference_state(reference_wire)
    numpy_equal = demo["numpy"] == reference["numpy"]
    python_equal = demo["python"] == reference["python"]
    return dict(
        kind=KIND,
        numpy_equal=numpy_equal,
        python_equal=python_equal,
        states_equal=numpy_equal and python_equal,
        normalized=dict(demo=demo, reference=reference),
        input_runtime_epoch_and_producer_authenticated=False,
        common_starting_authority_established=False,
        RNG_reset_or_replacement=False,
        scientific_physical_checkpoint_credit=0,
    )
