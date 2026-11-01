"""Bounded read-only live YAML graph capture. No decoder or constructors."""

import struct
from collections import OrderedDict
from types import MemberDescriptorType

MAX_NODES = 100000
MAX_BYTES = 16 * 2**20
MAX_DEPTH = 96


class UnsupportedYamlGraph(ValueError):
    pass


def capture(roots, *, yaml_base, runtime_types):
    """Retain storage, identities, scalar bits, slots, comments and aliases.

    runtime_types is the internal exact native/ruamel class registry, not an
    external declaration. Unknown objects refuse rather than become dicts.
    """
    objects, nodes, memo = [], [], {}
    visits = size = 0

    def visit(value, depth=0):
        nonlocal visits, size
        visits += 1
        if depth > MAX_DEPTH or visits > MAX_NODES:
            raise UnsupportedYamlGraph("Bounded YAML graph exhausted")
        kind = type(value)
        if value is None or kind is bool:
            return (kind.__name__, value)
        if kind in (str, bytes, int, float):
            if id(value) in memo:
                return ("ref", memo[id(value)])
            token = len(nodes)
            memo[id(value)] = token
            objects.append(value)
            node = dict(token=token, type=kind.__name__)
            nodes.append(node)
            if kind is float:
                node["float64"] = struct.pack(">d", value).hex()
                return ("ref", token)
            if kind is bytes:
                size += len(value)
                if size > MAX_BYTES:
                    raise UnsupportedYamlGraph("YAML graph byte bound")
                node["bytes"] = value.hex()
                return ("ref", token)
            if kind is str:
                size += len(value.encode("utf-8", "surrogatepass"))
                if size > MAX_BYTES:
                    raise UnsupportedYamlGraph("YAML graph byte bound")
            node["value"] = value
            return ("ref", token)
        if id(value) in memo:
            return ("ref", memo[id(value)])
        if isinstance(value, type) and value in runtime_types:
            objects.append(value)
            return ("class", value.__module__, value.__qualname__)
        if (
            kind not in (dict, list, tuple, set, frozenset, OrderedDict)
            and kind not in runtime_types
        ):
            raise UnsupportedYamlGraph(
                "Unsupported exact YAML graph type: " + kind.__module__ + "." + kind.__qualname__
            )
        token = len(nodes)
        memo[id(value)] = token
        objects.extend((value, kind))
        node = dict(token=token, type=kind.__module__ + "." + kind.__qualname__)
        nodes.append(node)
        if isinstance(value, OrderedDict):
            node["ordered_dict_storage"] = [
                (visit(k, depth + 1), visit(v, depth + 1)) for k, v in OrderedDict.items(value)
            ]
        elif isinstance(value, dict):
            node["dict_storage"] = [
                (visit(k, depth + 1), visit(v, depth + 1)) for k, v in dict.items(value)
            ]
        elif isinstance(value, list):
            node["list_storage"] = [visit(v, depth + 1) for v in list.__iter__(value)]
        elif isinstance(value, tuple):
            node["tuple_storage"] = [visit(v, depth + 1) for v in tuple.__iter__(value)]
        elif isinstance(value, (set, frozenset)):
            iterator = set.__iter__(value) if isinstance(value, set) else frozenset.__iter__(value)
            node["set_storage"] = [visit(v, depth + 1) for v in iterator]
        elif isinstance(value, str):
            node["string_value"] = str.__str__(value)
            size += len(node["string_value"].encode("utf-8", "surrogatepass"))
            if size > MAX_BYTES:
                raise UnsupportedYamlGraph("YAML graph byte bound")
        elif isinstance(value, int):
            node["integer_value"] = int.__int__(value)
        elif isinstance(value, float):
            node["float64_value"] = struct.pack(">d", float.__float__(value)).hex()
        if kind in runtime_types:
            try:
                fields = object.__getattribute__(value, "__dict__")
            except AttributeError:
                fields = None
            if fields is not None:
                node["attributes"] = visit(fields, depth + 1)
            slots = []
            for base in kind.__mro__:
                for name, descriptor in vars(base).items():
                    if type(descriptor) is MemberDescriptorType and name not in (
                        "__dict__",
                        "__weakref__",
                    ):
                        try:
                            item = descriptor.__get__(value, kind)
                        except AttributeError:
                            slots.append((base.__qualname__, name, "absent"))
                            continue
                        slots.append((base.__qualname__, name, visit(item, depth + 1)))
            node["slots"] = slots
            if isinstance(value, yaml_base) and "_conf" not in object.__getattribute__(
                value, "__dict__"
            ):
                raise UnsupportedYamlGraph(
                    "Native YAML object missing retained configuration store"
                )
        return ("ref", token)

    root_edges = [(name, visit(value)) for name, value in roots.items()]
    return tuple(objects), dict(roots=root_edges, nodes=nodes, scalar_bytes=size)
