"""Fresh original-BETSE world and mapping reference; preparation is AST only.

The private compiler, descriptor adapter, wire encoder and numerical libraries
are shared machinery. No Cells production evaluator is imported as an oracle.
Actual execution requires the separate reviewed release/resource gate.
"""

import ast
import copy
import hashlib
import warnings
from pathlib import Path
from types import FunctionType, SimpleNamespace

from validation.betse import native_multi_cell_environment_native as prefix

KIND = "cells.independent_tissue_to_grid@1"
ENDPOINT = "tissue_to_grid_probes"
METHODS = prefix.METHODS
MAPPING_METHODS = ("map_cells_centre_to_grids_centre", "map_cells_centre_to_points")
SOURCE_LINES = dict(
    map_cells_centre_to_grids_centre=[2825, 2854],
    map_cells_centre_to_points=[2883, 3017],
    from_iterable=[95, 148],
    is_sequence=[242, 265],
)
TAIL_LINES = (517, 518, 521, 522, 525, 526)
HELPERS = (
    ("betse/lib/numpy/nparray.py", "from_iterable"),
    ("betse/util/type/iterable/sequences.py", "is_sequence"),
)
PROBE_POLICY = dict(
    kind="cells.mapping_index_probes@1",
    names=["grid_1d", "grid_2d", "points_1d", "points_2d"],
    data="Python float cell-position-plus-one; second row is its negation",
    target="actual caller X,Y arrays",
    interpolation="linear",
    points_factor=1,
    grid_factor="actual caller maskECM via original method",
    inputs=1,
    independent_case_credit=0,
)


def pins_for():
    return dict(prefix.pins_for())


def source_nodes(root):
    """Retain multi construction; extend only original world/mapping bodies."""
    root = Path(root)
    groups, sites = prefix.source_nodes(root)
    groups, sites = copy.deepcopy(groups), copy.deepcopy(sites)
    trees = {}
    for name, digest in pins_for().items():
        path = root / name
        if path.is_symlink() or prefix.shared.digest(path) != digest:
            raise ValueError("Changed original mapping source: " + name)
        trees[name] = ast.parse(path.read_bytes(), filename=str(path))

    def add(file, node):
        nodes = next((nodes for name, nodes in groups if name == file), None)
        if nodes is None:
            nodes = []
            groups.append((file, nodes))
        old = next((n for n in nodes if getattr(n, "name", None) == node.name), None)
        if old is not None:
            if ast.dump(old) != ast.dump(node):
                raise ValueError("Conflicting independently selected helper: " + node.name)
        else:
            nodes.append(copy.deepcopy(node))
        sites[file + ":" + node.name] = dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            ast_sha256=hashlib.sha256(ast.dump(node).encode()).hexdigest(),
        )

    file = prefix.legacy_source.CELLS_FILE
    actual = next(n for n in trees[file].body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    cells = next(
        n
        for f, ns in groups
        if f == file
        for n in ns
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    methods = {n.name: n for n in actual.body if isinstance(n, ast.FunctionDef)}
    cells.body = [
        copy.deepcopy(methods["make_world"]) if n.name == "make_world" else n for n in cells.body
    ]
    cells.body.extend(copy.deepcopy(methods[name]) for name in MAPPING_METHODS)
    for name in ("make_world", *MAPPING_METHODS):
        node = methods[name]
        sites[file + ":Cells." + name] = dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            ast_sha256=hashlib.sha256(ast.dump(node).encode()).hexdigest(),
        )
    stores = [n.lineno for n in methods["make_world"].body if n.lineno in TAIL_LINES]
    if stores != list(TAIL_LINES) or methods["make_world"].body[-1].lineno != 526:
        raise ValueError("Original six-store data tail/order changed")
    file = "betse/science/math/finitediff.py"
    actual = next(
        n for n in trees[file].body if isinstance(n, ast.ClassDef) and n.name == "FiniteDiffSolver"
    )
    grid = next(
        n
        for f, ns in groups
        if f == file
        for n in ns
        if isinstance(n, ast.ClassDef) and n.name == "FiniteDiffSolver"
    )
    grid.body.append(
        copy.deepcopy(
            next(
                n
                for n in actual.body
                if isinstance(n, ast.FunctionDef) and n.name == "makeLaplacian"
            )
        )
    )
    for file, name in HELPERS:
        add(
            file,
            next(n for n in trees[file].body if isinstance(n, ast.FunctionDef) and n.name == name),
        )
    for file, node in (
        (prefix.legacy_source.CELLS_FILE, cells),
        ("betse/science/math/finitediff.py", grid),
    ):
        sites[file + ":" + node.name] = dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            ast_sha256=hashlib.sha256(ast.dump(node).encode()).hexdigest(),
        )
    return groups, sites


def runtime_functions():
    scope = prefix.runtime_functions()
    scope["DIRECT"]["betse.science.cells"].update(
        BetseSequenceException="betse.exceptions:BetseSequenceException",
        nparray="betse.lib.numpy.nparray",
    )
    return scope


def probe_inputs(caller):
    """Declared external data; no state hydration, numerical oracle or mask fix."""
    data = [float(i + 1) for i in range(len(caller.cell_i))]
    two = [data, [-value for value in data]]
    return tuple(
        dict(
            name=name,
            method="grids" if name.startswith("grid_") else "points",
            data=two if name.endswith("2d") else data,
            target_points=None if name.startswith("grid_") else (caller.X, caller.Y),
            interp_method="linear",
            data_factor=1,
        )
        for name in PROBE_POLICY["names"]
    )


def caller_values(obs):
    return prefix.public_snapshot(obs)["caller"]


class Observation(prefix.Observation):
    def __init__(self, capture, record_exception, stream):
        super().__init__(capture, record_exception, stream)
        self.mapping_inputs, self.mapping_results = [], []
        self.mapping_raw_results = []
        self.mapping_before = self.mapping_after = self.mapping_stream_before = None
        self.mapping_stream_after = None
        self.poisson_results, self.poisson_helpers = [], []
        self.prefix_execution = None
        self.mapping_completed = False
        self.mapping_primary = None
        self.mapping_aliases = {}
        self.mapping_warnings = []
        self.environment_aliases = {}
        self.pre_tail_cell_i = None
        self.tail_asarray_returns = []

    def save(self, label):
        super().save(label)
        if label == "make_maskM":
            caller, grid = self.caller, self.grid
            self.pre_tail_cell_i = caller.cell_i
            # These aliases describe the retained pre-tail environment snapshot.
            # The later literal np.asarray store intentionally breaks one alias.
            self.environment_aliases = dict(
                grid_is_actual=caller.grid_obj is grid,
                X_is_grid=caller.X is grid.cents_X,
                Y_is_grid=caller.Y is grid.cents_Y,
                xy_is_grid=caller.xypts is grid.xy_cents,
                map_is_grid=caller.map_ij2k is grid.map_ij2k_cents,
                all_points_cell_i_is_cell_i=caller.all_points_cell_i is caller.cell_i,
                points_tree_is_retained=any(caller.points_tree is t for t in self.trees),
                voronoi_centres_is_xypts=caller.voronoi_centres is caller.xypts,
            )

    def wrap(self, cls, name, **kwargs):
        result = super().wrap(cls, name, **kwargs)
        if cls.__name__ == "FiniteDiffSolver" and name == "cell_grid":
            self.install_poisson(cls)
        if cls.__name__ == "Cells" and name == "__init__":
            self.install_world_tail(cls)
        return result

    def install_world_tail(self, cls):
        original = cls.make_world
        numpy = original.__globals__["np"]

        def asarray(value, *args, **kwargs):
            self.stop()
            if (
                self.tail_asarray_returns
                or type(self.pre_tail_cell_i) is not list
                or value is not self.pre_tail_cell_i
                or self.caller.cell_i is not value
                or self.caller.all_points_cell_i is not value
            ):
                raise ValueError("Original pre-tail cell-index list/alias changed")
            self.work.append(dict(phase="world_data_tail", event="asarray_attempt", is_case=False))
            returned = numpy.asarray(value, *args, **kwargs)
            # Retain the actual return before any observation can reject it.
            self.tail_asarray_returns.append((value, returned))
            self.stop()
            return returned

        # Only make_world's private globals change. Its literal code, delegate
        # and all numerical method globals remain unchanged.
        cls.make_world = prefix.clone(
            original, np=SimpleNamespace(asarray=asarray, ones=numpy.ones)
        )

    def tail_aliases(self):
        rows = self.tail_asarray_returns
        return dict(
            all_points_cell_i_is_original=(
                type(self.pre_tail_cell_i) is list
                and self.caller.all_points_cell_i is self.pre_tail_cell_i
            ),
            cell_i_is_tail_asarray_return=(
                len(rows) == 1
                and rows[0][0] is self.pre_tail_cell_i
                and rows[0][1] is self.caller.cell_i
                and rows[0][1] is not self.pre_tail_cell_i
            ),
        )

    def install_poisson(self, cls):
        original = cls.makeLaplacian
        numpy = original.__globals__["np"]

        def helper(name, delegate, *args, **kwargs):
            self.stop()
            self.work.append(dict(phase=self.stage, event=name + "_attempt", is_case=False))
            value = delegate(*args, **kwargs)
            self.poisson_helpers.append((self.stage, name, value))
            self.snapshot(value, self.stage + "." + name + "_immediate")
            self.stop()
            return value

        method = prefix.clone(
            original,
            np=SimpleNamespace(
                zeros=lambda *a, **k: helper("zeros", numpy.zeros, *a, **k),
                linalg=SimpleNamespace(
                    pinv=lambda *a, **k: helper("pinv", numpy.linalg.pinv, *a, **k)
                ),
            ),
        )

        def solve(actual, *args, **kwargs):
            self.stop()
            if (
                actual is not self.grid
                or self.caller.grid_obj is not actual
                or len(self.poisson_results) >= 2
            ):
                raise ValueError("Original two-solve grid/caller ownership changed")
            self.stage = ("environment_voltage", "environment_current")[len(self.poisson_results)]
            self.work.append(dict(phase=self.stage, event="makeLaplacian_attempt", is_case=False))
            returned = method(actual, *args, **kwargs)
            self.poisson_results.append((self.stage, returned))
            self.stop()
            return returned

        cls.makeLaplacian = solve


def _execute(namespace, declared, configuration, **kwargs):
    """Use fresh original objects, then call original mapping on that caller."""
    obs = kwargs["observation"]
    # evaluate injects the descriptor-bearing parameter constructor here. The
    # genuine legacy delegate must receive it too, rather than its old globals.
    execution = prefix.clone(prefix.legacy._execute, SimpleNamespace=SimpleNamespace)(
        namespace, declared, configuration, **kwargs
    )
    obs.prefix_execution = execution
    if execution["status"] != "source_completed":
        return execution
    caller, grid, mesh, parameter, mask = obs.caller, obs.grid, obs.mesh, obs.parameter, obs.mask
    guards = prefix._guards()
    caught = []
    try:
        with (
            warnings.catch_warnings(record=True) as caught,
            prefix.source_observation(obs, kwargs["native_root"], "mapping_reference"),
        ):
            warnings.simplefilter("always")
            obs.stage = "mapping_before"
            obs.mapping_before = obs.snapshot(caller_values(obs), obs.stage)
            obs.mapping_stream_before = obs.stream()
            for probe in probe_inputs(caller):
                obs.stage = probe["name"]
                obs.mapping_inputs.append(probe)
                obs.work.append(dict(phase=obs.stage, event="mapping_attempt", is_case=False))
                obs.stop()
                if probe["method"] == "grids":
                    value = caller.map_cells_centre_to_grids_centre(
                        probe["data"], interp_method=probe["interp_method"]
                    )
                else:
                    value = caller.map_cells_centre_to_points(
                        probe["data"],
                        probe["target_points"],
                        interp_method=probe["interp_method"],
                        data_factor=probe["data_factor"],
                    )
                obs.mapping_raw_results.append((probe["name"], value))
                obs.stop()
                obs.mapping_results.append((probe["name"], obs.snapshot(value, probe["name"])))
            obs.stage = "mapping_after"
            obs.mapping_after = obs.snapshot(caller_values(obs), obs.stage)
            obs.mapping_stream_after = obs.stream()
            obs.mapping_aliases = dict(
                caller=obs.caller is caller,
                grid=obs.grid is grid and caller.grid_obj is grid,
                mesh=obs.mesh is mesh and caller.mesh is mesh,
                parameter=obs.parameter is parameter,
                mask=obs.mask is mask and mesh.image_mask is mask,
                **obs.tail_aliases(),
            )
            obs.stop()
            obs.mapping_completed = True
    except Exception as error:
        if not isinstance(error, prefix.legacy.CaptureFailure):
            obs.mapping_primary = error
        saved = None
        if obs.mapping_primary is not None:
            try:
                saved = obs.record_exception(error)
            except Exception as capture:
                saved = prefix.legacy._fallback_error(error)
                obs.remember(capture, "mapping_primary_record")
        execution = dict(
            execution,
            status="source_failed",
            source_body_completed=False,
            failed_stage=obs.stage,
            source_error=saved,
        )
    finally:
        try:
            obs.mapping_warnings = prefix._guarded_call(
                lambda: [str(row.message) for row in caught], guards
            )
        except Exception as capture:
            obs.remember(capture, "mapping_warning_capture")
        finally:
            prefix._restore_guards(guards)
    return execution


def _finalize(obs, execution, descriptor_metadata, **kwargs):
    # The nine-method snapshot was retained at make_maskM, before operators/tail.
    environment = prefix._finalize_reference(
        obs,
        obs.prefix_execution or execution,
        descriptor_metadata,
        **kwargs,
        probes=dict(
            cache=lambda: obs.ordinary[-1][1] if obs.ordinary else None,
            stream_after=obs.stream,
            diagnostics=lambda: prefix.diagnostics(obs.caller),
            aliases=lambda: dict(obs.environment_aliases),
        ),
    )
    result = dict(
        kind=KIND,
        stop_after=ENDPOINT,
        status="source_failed",
        source_body_completed=bool(obs.mapping_completed and execution["source_body_completed"]),
        source_error=execution["source_error"],
        capture_error=obs.capture_error,
        capture_errors=obs.capture_errors,
        failed_stage=execution["failed_stage"],
        environment=environment,
        before=obs.mapping_before,
        after=obs.mapping_after,
        results=obs.mapping_results,
        inputs=None,
        stream_before=obs.mapping_stream_before,
        stream_after=obs.mapping_stream_after,
        aliases=obs.mapping_aliases,
        work=obs.work,
        warnings=obs.mapping_warnings,
        original_source_pins=pins_for(),
        source_sites=kwargs["sites"],
        probe_policy=PROBE_POLICY,
        actual_source_prefix_attempts=kwargs["source_attempted"],
        reference_inputs=1,
        prefix_and_mapping_work_are_not_independent_cases=True,
        work_log_layers_nonadditive=True,
        work_log_is_complete_native_operation_count=False,
        shared_machinery=[
            "declared probe-input generator",
            "private compiler and normalized type adapters",
            "NumPy/SciPy/Pillow",
            "typed wire encoder",
        ],
        physical_or_checkpoint_admission=False,
        mapping_return_captures=[],
        mapping_return_capture_gaps=[],
    )
    guards = prefix._guards()
    # Each successful source return is a separate forensic capture attempt,
    # even after an immediate snapshot/observer failed. Do not promote these
    # recovery records into completed mapping results.
    for name, value in obs.mapping_raw_results:
        row = dict(name=name, status="unavailable", value=None, capture_error=None)
        try:
            row["value"] = prefix._guarded_call(lambda value=value: obs.capture(value), guards)
            row["status"] = "saved"
        except Exception as error:
            obs.remember(error, "mapping_return." + name)
            row["capture_error"] = obs.capture_errors[-1]["error"]
            result["mapping_return_capture_gaps"].append(name)
        finally:
            prefix._restore_guards(guards)
        result["mapping_return_captures"].append(row)
    for key, action in (
        (
            "inputs",
            lambda: obs.capture(
                [
                    dict(
                        data=p["data"],
                        target_points=p["target_points"],
                        data_factor=p["data_factor"],
                    )
                    for p in obs.mapping_inputs
                ]
            ),
        ),
        ("poisson_results", lambda: obs.capture(obs.poisson_results)),
        ("poisson_helpers", lambda: obs.capture(obs.poisson_helpers)),
        ("tail_asarray_returns", lambda: obs.capture(obs.tail_asarray_returns)),
    ):
        try:
            result[key] = prefix._guarded_call(action, guards)
        except Exception as error:
            obs.remember(error, "mapping_final_" + key)
        finally:
            prefix._restore_guards(guards)
    result.update(capture_error=obs.capture_error, capture_errors=obs.capture_errors)
    if result["failed_stage"] is None and obs.capture_error is not None:
        result["failed_stage"] = "mapping_final_metadata"
    if (
        result["source_body_completed"]
        and result["source_error"] is None
        and obs.capture_error is None
        and len(obs.mapping_results) == 4
        and all(obs.mapping_aliases.values())
    ):
        result.update(status="source_completed", failed_stage=None)
    return result


def evaluate(raw, configuration, native_root, *, record_exception):
    """No producer imports: execute only the separately compiled original AST."""
    scope = dict(
        vars(prefix),
        source_nodes=source_nodes,
        runtime_functions=runtime_functions,
        Observation=Observation,
        pins_for=pins_for,
        _finalize_reference=_finalize,
        legacy=SimpleNamespace(**dict(vars(prefix.legacy), _execute=_execute)),
    )
    function = FunctionType(
        prefix.evaluate.__code__,
        scope,
        prefix.evaluate.__name__,
        prefix.evaluate.__defaults__,
        prefix.evaluate.__closure__,
    )
    return function(raw, configuration, native_root, record_exception=record_exception)
