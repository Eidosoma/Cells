"""Native checkpoint witnesses and a declared synthetic history-capacity probe."""

import resource
import struct
import types


def compare_graph(left, right, *, relocated_roots=None):
    """Compare restored values and mutable aliases, without treating pickle bytes as canonical."""
    import numpy as np

    forwards, backwards, references = {}, {}, []
    facts = dict(objects=0, scalar_values=0, arrays=0, array_bytes=0, aliases=0, relocated_paths=0)

    def check(a, b, path):
        if type(a) is not type(b):
            raise ValueError("Checkpoint type changed: " + path)
        facts["objects"] += 1
        if a is b:
            return
        if isinstance(a, str) and relocated_roots is not None:
            roots = tuple(str(root).rstrip("/") for root in relocated_roots)
            local = tuple(
                value == root or value.startswith(root + "/")
                for value, root in zip((a, b), roots, strict=True)
            )
            if any(local):
                if not all(local) or a[len(roots[0]) :] != b[len(roots[1]) :]:
                    raise ValueError("Checkpoint relocated path changed: " + path)
                facts["relocated_paths"] += 1
                return
        if a is None or isinstance(a, (bool, int, str, bytes, range)):
            if a != b:
                raise ValueError("Checkpoint value changed: " + path)
            facts["scalar_values"] += 1
            return
        if isinstance(a, float):
            if struct.pack("<d", a) != struct.pack("<d", b):
                raise ValueError("Checkpoint float bits changed: " + path)
            facts["scalar_values"] += 1
            return
        if isinstance(a, np.generic):
            if a.dtype != b.dtype or a.tobytes() != b.tobytes():
                raise ValueError("Checkpoint NumPy scalar changed: " + path)
            facts["scalar_values"] += 1
            return
        # Keep identity for containers, arrays and native state-bearing objects.
        if id(a) in forwards or id(b) in backwards:
            if forwards.get(id(a)) != id(b) or backwards.get(id(b)) != id(a):
                raise ValueError("Checkpoint object alias changed: " + path)
            facts["aliases"] += 1
            return
        forwards[id(a)], backwards[id(b)] = id(b), id(a)
        references.append((a, b))
        if isinstance(a, np.ndarray):
            if a.dtype != b.dtype or a.shape != b.shape:
                raise ValueError("Checkpoint array layout changed: " + path)
            if a.dtype.hasobject:
                for i, (x, y) in enumerate(zip(a.flat, b.flat, strict=True)):
                    check(x, y, path + f"/[{i}]")
            elif a.tobytes() != b.tobytes():
                raise ValueError("Checkpoint array bits changed: " + path)
            facts["arrays"] += 1
            facts["array_bytes"] += a.nbytes
        elif isinstance(a, dict):
            if len(a) != len(b):
                raise ValueError("Checkpoint dictionary extent changed: " + path)
            for (ak, av), (bk, bv) in zip(a.items(), b.items(), strict=True):
                check(ak, bk, path + "/key")
                check(av, bv, path + "/" + str(ak))
        elif isinstance(a, (list, tuple)):
            if len(a) != len(b):
                raise ValueError("Checkpoint sequence extent changed: " + path)
            for i, (av, bv) in enumerate(zip(a, b, strict=True)):
                check(av, bv, path + f"/{i}")
        elif isinstance(a, (set, frozenset)):
            if a != b:
                raise ValueError("Checkpoint set changed: " + path)
        elif isinstance(a, types.FunctionType):
            check(a.__code__, b.__code__, path + "/code")
            check(a.__defaults__, b.__defaults__, path + "/defaults")
            check(a.__kwdefaults__, b.__kwdefaults__, path + "/kwdefaults")
            check(a.__closure__, b.__closure__, path + "/closure")
            for name in a.__code__.co_names:
                if (name in a.__globals__) != (name in b.__globals__):
                    raise ValueError("Checkpoint function binding changed: " + path)
                if name in a.__globals__:
                    check(a.__globals__[name], b.__globals__[name], path + "/global/" + name)
        elif isinstance(a, types.CodeType):
            for name in dir(a):
                if name.startswith("co_") and not callable(getattr(a, name)):
                    check(getattr(a, name), getattr(b, name), path + "/" + name)
        elif isinstance(a, types.CellType):
            check(a.cell_contents, b.cell_contents, path + "/cell_contents")
        elif isinstance(a, types.MethodType):
            check(a.__func__, b.__func__, path + "/function")
            check(a.__self__, b.__self__, path + "/self")
        elif hasattr(a, "__dict__"):
            check(vars(a), vars(b), path + "/attributes")
        else:
            # Native extension types such as cKDTree expose their complete
            # serializable state through the stock reduction protocol.
            check(a.__reduce_ex__(4), b.__reduce_ex__(4), path + "/reduction")

    check(left, right, "checkpoint")
    return facts | {"values_and_aliases_exact": True}


def verify_checkpoint(path, destination):
    """Use the ordinary loader and check the complete serialized native object state."""
    from betse.lib.pickle import pickles

    value = pickles.load(str(path))
    pickles.save(value, filename=str(destination))
    restored = pickles.load(str(destination))
    compared = compare_graph(value, restored)
    return dict(
        ordinary_betse_loader=True,
        stock_roundtrip_graph_exact=True,
        comparison=compared,
        objects=len(value),
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    )


def capacity(path, destination, samples):
    """Clone independent history arrays to test storage, never a simulated trajectory.

    All populated native time-history fields are represented. Fresh copies avoid
    accidentally obtaining low memory by aliasing every sample to one array.
    """
    import copy

    import numpy as np
    from betse.lib.pickle import pickles
    from pickle_buffers import inline_arrays

    if type(samples) is not int or not 1 <= samples <= 511999:
        raise ValueError("Synthetic history capacity extent")
    objects = pickles.load(str(path))
    sim = objects[0]
    fields = {}
    for name, values in list(vars(sim).items()):
        if not ((name.endswith("_time") or name == "time") and isinstance(values, list)):
            continue
        if not values:
            fields[name] = dict(samples=0, numeric_bytes=0)
            continue
        template = values[0]
        if isinstance(template, np.ndarray):
            samples_array = [template.copy() for _ in range(samples)]
        else:
            samples_array = [copy.deepcopy(template) for _ in range(samples)]
        setattr(sim, name, samples_array)
        fields[name] = dict(samples=samples, numeric_bytes=samples * np.asarray(template).nbytes)
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    with inline_arrays() as facts:
        pickles.save(objects, filename=str(destination))
    return dict(
        status="synthetic_checkpoint_capacity_written",
        target_steps=samples + 1,
        history_fields=fields,
        peak_rss_before_write_bytes=before,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        checkpoint_storage=facts,
        numerical_trajectory=False,
        actual_512000_step_capture_qualified=False,
    )


def capacity_load(path, template_path, expected):
    """Read the large synthetic checkpoint in a fresh process with the stock loader."""
    import numpy as np
    from betse.lib.pickle import pickles

    objects = pickles.load(str(path))
    loaded_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    original = pickles.load(str(template_path))
    sim, template_sim = objects[0], original[0]
    names = {
        name
        for name, value in vars(sim).items()
        if (name.endswith("_time") or name == "time") and isinstance(value, list)
    }
    if names != set(expected["history_fields"]):
        raise ValueError("Synthetic history field coverage changed")
    fields = {}
    for name in sorted(names):
        values, templates = getattr(sim, name), getattr(template_sim, name)
        count = expected["history_fields"][name]["samples"]
        if len(values) != count or bool(templates) != bool(count):
            raise ValueError("Synthetic history extent changed: " + name)
        identities = set()
        for value in values:
            template = templates[0]
            if type(value) is not type(template):
                raise ValueError("Synthetic history type changed: " + name)
            if isinstance(template, np.ndarray):
                if (
                    value.dtype != template.dtype
                    or value.shape != template.shape
                    or value.tobytes() != template.tobytes()
                ):
                    raise ValueError("Synthetic history array changed: " + name)
                if id(value) in identities:
                    raise ValueError("Synthetic history samples aliased: " + name)
                identities.add(id(value))
            else:
                compare_graph(template, value)
        fields[name] = dict(samples=count, distinct_arrays=len(identities), exact=True)
        # All samples were checked; compare the unchanged non-history state
        # without retaining a second full-sized checkpoint graph.
        setattr(sim, name, templates)
    static = compare_graph(objects, original)
    return dict(
        status="synthetic_checkpoint_capacity_loaded",
        ordinary_betse_loader=True,
        history_fields=fields,
        static_state=static,
        peak_rss_after_load_bytes=loaded_peak,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        numerical_trajectory=False,
        actual_512000_step_capture_qualified=False,
    )
