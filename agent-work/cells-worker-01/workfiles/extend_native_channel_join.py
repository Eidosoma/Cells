# ruff: noqa: E501
"""Build only new catalog-join files from the frozen late-channel chronology."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def prepare():
    target = ROOT / "src/cells/processes/betse_normal_catalog_join.py"
    if target.exists():
        raise FileExistsError(target)
    source = (ROOT / "src/cells/processes/betse_normal_channel_join.py").read_text()
    tree = ast.parse(source)
    # Retain the already-qualified downstream material/pump/gap/current/voltage
    # bodies in a new file; only the population callback becomes multi-route.
    replacements = {
        "_init_cache": """def _init_cache(row, vm):
    return ions.freeze(catalog.initialize(row["class_name"], vm, row["targets"]))
""",
        "_run_cache": """def _run_cache(row, incoming, vm, dt, modulator):
    return catalog.update(row["class_name"], incoming, vm, dt, modulator)
""",
    }
    lines = source.splitlines(keepends=True)
    for node in sorted(
        [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in replacements],
        key=lambda n: n.lineno,
        reverse=True,
    ):
        lines[node.lineno - 1 : node.end_lineno] = [replacements[node.name]]
    source = "".join(lines)
    source = source.replace(
        "from cells.processes import betse_normal_current as current",
        "from cells.processes import betse_normal_current as current\nfrom cells.processes import betse_channel_catalog_source as catalog",
    )
    source = source.replace(
        "betse_normal_late_channel_join_v1_5_0@1", "betse_normal_late_catalog_join_v1_5_0@1"
    )
    source = source.replace(
        "cells.betse_normal_channel_join_inputs@1", "cells.betse_normal_catalog_join_inputs@1"
    )
    source = source.replace(
        'CLASSES = ("Nav1p6", "Kv1p5", "Kv3p2", "ClLeak")\nROLES = dict(Nav1p6="Na", Kv1p5="K", Kv3p2="K", ClLeak="Cl")',
        "CLASSES = tuple(catalog.CLASSES)\nROUTES = catalog.ROUTES",
    )
    source = source.replace(
        'or set(raw) != {"kind", "provenance", "channels"}',
        'or set(raw) != {"kind", "provenance", "channels", "calcium_handler"}',
    )
    start = source.index('        role = ROLES[row["class_name"]]')
    end = source.index("    result = Binding(", start)
    source = (
        source[:start]
        + """        for role, _ in ROUTES[row["class_name"]]:
            expected = {"Na": 1, "K": 1, "Cl": -1, "Ca": 2}[role]
            if role not in ib.ion_ids or ib.kernel.valence[ib.ion_ids.index(role)] != expected:
                raise ValueError("Missing explicitly supplied native ion role: " + role)
    if "Ca" in ib.ion_ids:
        policy = raw["calcium_handler"]
        if (type(policy) is not dict or set(policy) != {"alpha_Ca", "Ca_dyn", "provenance"}
            or type(policy["alpha_Ca"]) not in (int,float) or policy["alpha_Ca"] != 0
            or type(policy["Ca_dyn"]) is not int or policy["Ca_dyn"] != 0
            or not isinstance(policy["provenance"], str) or not policy["provenance"].strip()):
            raise MissingCoupledState("Ca routes require explicitly disabled CaATP/ER handler; active CaATP and ER are unimplemented dependencies")
    elif raw["calcium_handler"] is not None:
        raise ValueError("A calcium handler policy requires an explicit live Ca ion row")
"""
        + source[end:]
    )
    # Preserve callback position while replacing only the inner population block.
    start = source.index(
        '                for slot, row in enumerate(binding.definition["channels"]):'
    )
    end = source.index("                # Empty network reaction system", start)
    source = (
        source[:start]
        + """                for slot, row in enumerate(binding.definition["channels"]):
                    before = _values(arrays)
                    old_cache = caches[slot]
                    skip = live.phase_kind == "INIT" and not row["init_active"]
                    route_phases = []
                    if not skip:
                        cache = _run_cache(row, old_cache, vm, forcing.dt_s, live.modulators[row["id"]])
                        calls[slot] += 1
                        observe("channel_update")
                        # Native order is class-specific; zero-weight routes still
                        # call get_ion/electroflux/update_Co and consume the nonce.
                        for ion_id, rel_perm in zip(cache["ions"], cache["rel_perm"], strict=True):
                            i = ib.ion_ids.index(ion_id)
                            sampled_bulk = cell[i].copy()
                            sampled_mem = cell[i][ib.kernel.owner].copy()
                            sampled_bath = np.asarray(bath[i]).copy()
                            route_before = _values(arrays)
                            current_before = extra.copy()
                            diffusion = cache["P"] * rel_perm * row["maxDm_m2_s"] * live.modulators[row["id"]]
                            ones = np.ones(len(vm))
                            flux = ions._electroflux(bath[i], sampled_mem, diffusion,
                                ones * ib.kernel.membrane_thickness_m,
                                ib.kernel.valence[i] * ones, vm,
                                forcing.runtime_temperature_K, ib.kernel)
                            cell[i] = cell[i] + (np.dot(ib.kernel.owner_sum, flux * ib.kernel.area_m2)
                                / ib.kernel.cell_volume_m3) * forcing.dt_s
                            membrane[i] = cell[i][ib.kernel.owner]
                            bath[i] = (bath[i] + -flux * (ib.kernel.area_m2 / ib.kernel.bath_volume_m3)
                                * forcing.dt_s).mean()
                            extra += -flux * ib.kernel.F_C_mol * ib.kernel.valence[i]
                            # The native class retains ONLY the last ion route.
                            cache.update(chan_flux=flux, DChan=diffusion)
                            route_phases.append(RoutePhase(ion_id, float(rel_perm),
                                ions.freeze(sampled_bulk), ions.freeze(sampled_mem), ions.freeze(sampled_bath),
                                ions.freeze(diffusion), ions.freeze(flux), ions.freeze(current_before),
                                ions.freeze(extra), route_before, _values(arrays),
                                ions.freeze(cache)))
                            observe("channel_direct", i)
                        caches[slot] = ions.freeze(cache)
                    else:
                        observe("channel_skipped")
                    consumes_clock = not skip and old_cache.get("kinetic_gate", True)
                    phases.append(ChannelPhase(row["id"], row["class_name"], skip,
                        calls[slot], old_cache, caches[slot], before.voltage_V,
                        _values(arrays).voltage_V, tuple(route_phases), before, _values(arrays),
                        forcing.dt_s, forcing.dt_s * old_cache["time_unit"] if consumes_clock else 0.0))
"""
        + source[end:]
    )
    source = source.replace(
        '            observe("network_clear")',
        '            if binding.definition["calcium_handler"] is not None:\n                observe("calcium_handler_disabled")\n            observe("network_clear")',
    )
    # Generic cache contracts have no invented h for ML, and retain literal
    # scalar-vs-vector auxiliary fields for all other classes.
    start = source.index("            expected_keys = set(initial)")
    end = source.index("        ib = binding.pump_binding.gated_binding.material_binding", start)
    source = (
        source[:start]
        + """            expected_keys = set(initial) | (set(catalog.CALCULATED_FIELDS[row["class_name"]]) | {"P"} if calls else set())
            if set(cache) != expected_keys:
                raise ValueError("Missing or unexpected original class state")
            for key in ("m", "h"):
                if key not in initial:
                    if key in cache:
                        raise ValueError("Invented absent native gate")
                    continue
                shape = initial[key].shape if isinstance(initial[key], np.ndarray) else ()
                if np.asarray(cache[key]).shape != shape:
                    raise ValueError("Changed original scalar/target gate shape")
            dynamic = {"m", "h", "P", "DChan", "chan_flux", *catalog.CALCULATED_FIELDS[row["class_name"]]}
            for key in set(initial) - dynamic - {"modulator"}:
                if ions.record(cache[key]) != ions.record(initial[key]):
                    raise ValueError("Changed fixed source class metadata")
            for key in ("chan_flux", "DChan", "P"):
                if key == "P" and not calls or key == "DChan" and not calls:
                    continue
                if not isinstance(cache[key], np.ndarray) or cache[key].shape != (len(parent.pump.rate_proxy_mol_m2_s),):
                    raise ValueError("Changed original membrane cache shape")
"""
        + source[end:]
    )
    # Add explicit unchanged CaATP rate-cache state for the no-op handler path.
    source = source.replace(
        "    channel_calls: tuple\n",
        "    channel_calls: tuple\n    calcium_rate_proxy_mol_m2_s: object\n",
    )
    source = source.replace(
        "def _state(binding, parent, caches, calls, initialization):",
        "def _state(binding, parent, caches, calls, initialization, calcium_rate_cache):",
    )
    source = source.replace(
        'binding.identity, parent, ions.freeze(caches), tuple(calls), ions.freeze(initialization), ""',
        'binding.identity, parent, ions.freeze(caches), tuple(calls), ions.freeze(calcium_rate_cache), ions.freeze(initialization), ""',
    )
    source = source.replace(
        "def initialize(binding, parent):",
        "def initialize(binding, parent, *, initial_calcium_rate_proxy_mol_m2_s):",
    )
    source = source.replace(
        "    caches = []\n",
        '    if binding.definition["calcium_handler"] is None:\n        if initial_calcium_rate_proxy_mol_m2_s is not None:\n            raise ValueError("No calcium rate cache without a live Ca row")\n        calcium_cache = None\n    else:\n        calcium_cache = current._array(initial_calcium_rate_proxy_mol_m2_s, (len(parent.rate_proxy_mol_m2_s),), "explicit unchanged calcium rate cache")\n    caches = []\n',
        1,
    )
    source = source.replace(
        "return _state(binding, parent, caches, [0] * len(caches), caches)",
        "return _state(binding, parent, caches, [0] * len(caches), caches, calcium_cache)",
    )
    source = source.replace(
        "                parent.initialization,\n",
        "                parent.initialization, parent.calcium_rate_proxy_mol_m2_s,\n",
        1,
    )
    source = source.replace(
        "candidate = _state(binding, material.candidate, caches, calls, parent.initialization)",
        "candidate = _state(binding, material.candidate, caches, calls, parent.initialization, parent.calcium_rate_proxy_mol_m2_s)",
    )
    source = source.replace(
        "            parent.initialization,\n        )",
        "            parent.initialization, parent.calcium_rate_proxy_mol_m2_s,\n        )",
    )
    source = source.replace(
        "native_channel_calls=sum(not phase.skipped for phase in material.channel_phases),",
        "native_channel_calls=sum(not phase.skipped for phase in material.channel_phases),\n                native_channel_ion_routes=sum(len(phase.routes) for phase in material.channel_phases),",
    )
    source = source.replace(
        "class ChannelJoinRejected(NumericalError):",
        'class MissingCoupledState(ValueError):\n    """An explicit scientific dependency cannot be silently replaced."""\n\n\nclass ChannelJoinRejected(NumericalError):',
    )
    # Replace the four-class single-route frame type.
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ChannelPhase")
    lines = source.splitlines(keepends=True)
    a = node.decorator_list[0].lineno - 1
    lines[a : node.end_lineno] = [
        """@dataclass(frozen=True, slots=True)
class RoutePhase:
    ion_id: str
    relative_permeability: float
    sampled_bulk_mM: object
    sampled_membrane_mM: object
    sampled_bath_mM: object
    diffusion_m2_s: object
    flux_mol_m2_s: object
    network_current_before_A_m2: object
    network_current_after_A_m2: object
    values_before: ions.Values
    values_after: ions.Values
    cache_after: object


@dataclass(frozen=True, slots=True)
class ChannelPhase:
    channel_id: str
    class_name: str
    skipped: bool
    call_index: int
    cache_before: object
    cache_after: object
    voltage_before_V: object
    voltage_after_V: object
    routes: tuple
    values_before: ions.Values
    values_after: ions.Values
    dt_s: float
    native_dt: float
"""
    ]
    target.write_text("".join(lines))
    # Catalog state-field inventory is emitted literally, never discovered by
    # executing any of the new channel equations during preparation.
    inventory = json.loads(
        (ROOT / "validation/betse/betse_normal_catalog_join_inventory.json").read_text()
    )
    computed = {}
    for name, row in inventory["classes"].items():
        tree = ast.parse((Path(inventory["checkout"]) / row["source"]).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
        fun = next(
            n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_calculate_state"
        )
        computed[name] = tuple(
            sorted(
                {
                    t.attr
                    for n in ast.walk(fun)
                    if isinstance(n, ast.Assign)
                    for t in n.targets
                    if isinstance(t, ast.Attribute) and ast.unparse(t.value) == "self"
                }
            )
        )
    port = ROOT / "src/cells/processes/betse_channel_catalog_source.py"
    port.write_text(port.read_text() + "\n\nCALCULATED_FIELDS = " + repr(computed) + "\n")


if __name__ == "__main__":
    prepare()
