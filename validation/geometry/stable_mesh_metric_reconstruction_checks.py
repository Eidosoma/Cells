"""Independent saved-row metric gates; no production or scientific imports."""

import math
from decimal import Decimal, localcontext
from fractions import Fraction


def _fraction(row):
    return Fraction(int(row["numerator"]), int(row["denominator"]))


def _certificate_shape(metric, expected):
    """Require every owner and scalar slot before following any certificate."""

    def require(condition, label):
        if not condition:
            raise ValueError("Incomplete/extra arithmetic evidence: " + label)

    def sequence(value, size, label):
        require(type(value) is list and len(value) == size, label)

    def keys(value, names, label):
        require(type(value) is dict and set(value) == set(names), label)

    def scalar(value, label, *, signed=False):
        require(type(value) is dict, label)
        kind = value.get("kind")
        if kind == "correctly_rounded_binary_rational":
            names = {"kind", "exact", "arithmetic_event_index"}
            if "store_seam" in value:
                names.add("store_seam")
                require(value["store_seam"] == "correctly_rounded_binary64", label)
        elif kind == "resolved_dyadic_sqrt_interval":
            names = {
                "kind",
                "lower",
                "upper",
                "precision_bits",
                "radicand",
                "arithmetic_event_index",
            }
        else:
            raise ValueError("Incomplete/unknown arithmetic scalar: " + label)
        if signed:
            names.add("sign")
        keys(value, names, label)
        require(type(value["arithmetic_event_index"]) is int, label)

    source, native = expected["native_roles"], metric["native_roles"]
    p, c, e, d, v = (
        len(source["tri_sa"]),
        len(source["vor_sa"]),
        len(source["tri_edge_len"]),
        len(expected["full_dual_metrics"]),
        len(source["tri_sa_o"]),
    )
    require(all(count > 0 for count in (p, c, e, d, v)), "nonempty independent owner axes")
    for key, size in (
        ("tri_sa", p),
        ("tri_cents", p),
        ("vor_sa", c),
        ("vor_cents", c),
        ("tri_edge_len", e),
        ("tri_mids", e),
        ("tri_tang", e),
        ("vor_edge_len", e),
        ("vor_mids", e),
        ("vor_tang", e),
        ("tri_sa_o", v),
    ):
        sequence(source[key], size, "source/" + key)
        sequence(native[key], size, "readout/" + key)
    sequence(metric["full_dual_metrics"], d, "readout/full_dual_metrics")
    for key, size in (
        ("native_stored_dual_over_primal", e),
        ("native_stored_primal_over_dual", e),
        ("coordinate_geometric_length_ratio", e),
        ("native_stored_inverse_dual_area", c),
    ):
        sequence(metric["coefficients"][key], size, "readout/" + key)
    counts = dict(
        primal_polygons=p,
        dual_polygons=c,
        primal_edges=e,
        selected_dual_edges=e,
        full_dual_edges=d,
        dual_vertex_reference_area=v,
        coefficients=e,
        inverse_dual_area=c,
    )
    expected_events = 3 * p + 4 * c + 13 * e + 5 * d + v
    certs = metric["certificates"]
    keys(certs, set(counts) | {"arithmetic_events"}, "complete group inventory")
    for group, count in counts.items():
        sequence(certs[group], count, group + " owner axis")
        for i, row in enumerate(certs[group]):
            label = group + "/" + str(i)
            if group in ("primal_polygons", "dual_polygons"):
                keys(row, {"area", "centroid"}, label)
                scalar(row["area"], label + "/area")
                sequence(row["centroid"], 2, label + "/centroid")
                for axis in (0, 1):
                    scalar(row["centroid"][axis], label + "/centroid/" + str(axis))
            elif group in ("primal_edges", "selected_dual_edges", "full_dual_edges"):
                keys(row, {"length", "midpoint", "tangent"}, label)
                scalar(row["length"], label + "/length")
                for name in ("midpoint", "tangent"):
                    sequence(row[name], 2, label + "/" + name)
                    for axis in (0, 1):
                        scalar(
                            row[name][axis],
                            label + "/" + name + "/" + str(axis),
                            signed=name == "tangent",
                        )
            elif group == "coefficients":
                keys(
                    row,
                    {"native_forward", "native_inverse", "coordinate_geometric", "input_store_hex"},
                    label,
                )
                keys(row["input_store_hex"], {"primal_length", "dual_length"}, label)
                for name in ("native_forward", "native_inverse", "coordinate_geometric"):
                    scalar(row[name], label + "/" + name)
            else:
                scalar(row, label)
    sequence(certs["arithmetic_events"], expected_events, "source-owner scalar event count")
    for i, event in enumerate(certs["arithmetic_events"]):
        label = "arithmetic_events/" + str(i)
        keys(event, {"sequence", "label", "operation", "input_exact", "returned"}, label)
        keys(event["input_exact"], {"numerator", "denominator"}, label + "/input_exact")
        keys(event["returned"], {"value", "binary64_hex", "certificate"}, label + "/returned")
        scalar(event["returned"]["certificate"], label + "/certificate")
    return expected_events, counts


def _certificates(metric, expected):
    try:
        expected_events, counts = _certificate_shape(metric, expected)
    except (KeyError, TypeError, ValueError, IndexError) as error:
        return [
            dict(
                label="complete_source_owner_certificate_contract", passed=False, reason=str(error)
            )
        ]
    rows = [
        dict(
            label="complete_source_owner_certificate_contract",
            passed=True,
            expected_owner_counts=counts,
            expected_scalar_events=expected_events,
        )
    ]
    for event_index, event in enumerate(metric["certificates"]["arithmetic_events"]):
        returned = event.get("returned")
        if returned is None or "failure" in event:
            raise ValueError("A completed candidate has an incomplete arithmetic event")
        value = returned["value"]
        target = _fraction(event["input_exact"])
        certificate = returned["certificate"]
        if certificate["kind"] == "correctly_rounded_binary_rational":
            exact = _fraction(certificate["exact"])
            valid = exact == target and float(exact).hex() == value.hex()
        elif certificate["kind"] == "resolved_dyadic_sqrt_interval":
            lower, upper = _fraction(certificate["lower"]), _fraction(certificate["upper"])
            valid = (
                0 <= lower <= upper
                and lower * lower <= target <= upper * upper
                and float(lower).hex() == float(upper).hex() == value.hex()
                and _fraction(certificate["radicand"]) == target
            )
        else:
            valid = False
        valid = (
            valid
            and returned["binary64_hex"] == value.hex()
            and event["sequence"] == event_index
            and certificate["arithmetic_event_index"] == event_index
        )
        rows.append(
            dict(
                sequence=event["sequence"],
                label=event["label"],
                passed=valid,
                actual_binary64_hex=value.hex(),
            )
        )
    events = metric["certificates"]["arithmetic_events"]
    used = []

    def bound(certificate, value, label, *, signed=False):
        index = certificate.get("arithmetic_event_index")
        valid = type(index) is int and 0 <= index < len(events)
        if valid:
            used.append(index)
            event = events[index]["returned"]
            base = {key: child for key, child in certificate.items() if key != "sign"}
            expected_value = abs(value) if signed else value
            valid = (
                base == event["certificate"]
                and event["value"] == expected_value
                and (not signed or certificate["sign"] == (-1 if value < 0 else 1))
            )
        rows.append(dict(label=label, passed=valid, linked_event=index))

    certs, native = metric["certificates"], metric["native_roles"]
    for group, area, centre in (
        ("primal_polygons", "tri_sa", "tri_cents"),
        ("dual_polygons", "vor_sa", "vor_cents"),
    ):
        for i, certificate in enumerate(certs[group]):
            bound(certificate["area"], native[area][i], group + "/area/" + str(i))
            for axis in (0, 1):
                bound(
                    certificate["centroid"][axis],
                    native[centre][i][axis],
                    group + "/centroid/" + str(i) + "/" + str(axis),
                )
    edge_groups = (
        ("primal_edges", native["tri_edge_len"], native["tri_mids"], native["tri_tang"]),
        ("selected_dual_edges", native["vor_edge_len"], native["vor_mids"], native["vor_tang"]),
        (
            "full_dual_edges",
            [row["length_m"] for row in metric["full_dual_metrics"]],
            [row["midpoint_m"] for row in metric["full_dual_metrics"]],
            [row["tangent_xy"] for row in metric["full_dual_metrics"]],
        ),
    )
    for group, lengths, midpoints, tangents in edge_groups:
        for i, certificate in enumerate(certs[group]):
            bound(certificate["length"], lengths[i], group + "/length/" + str(i))
            for axis in (0, 1):
                bound(
                    certificate["midpoint"][axis],
                    midpoints[i][axis],
                    group + "/midpoint/" + str(i) + "/" + str(axis),
                )
                bound(
                    certificate["tangent"][axis],
                    tangents[i][axis],
                    group + "/tangent/" + str(i) + "/" + str(axis),
                    signed=True,
                )
    for i, certificate in enumerate(certs["dual_vertex_reference_area"]):
        bound(certificate, native["tri_sa_o"][i], "reference_area/" + str(i))
    for i, certificate in enumerate(certs["coefficients"]):
        for leaf, key in (
            ("native_forward", "native_stored_dual_over_primal"),
            ("native_inverse", "native_stored_primal_over_dual"),
            ("coordinate_geometric", "coordinate_geometric_length_ratio"),
        ):
            bound(certificate[leaf], metric["coefficients"][key][i], key + "/" + str(i))
        rows.append(
            dict(
                label="coefficient_input_stores/" + str(i),
                passed=certificate["input_store_hex"]
                == dict(
                    primal_length=native["tri_edge_len"][i].hex(),
                    dual_length=native["vor_edge_len"][i].hex(),
                ),
            )
        )
    for i, certificate in enumerate(certs["inverse_dual_area"]):
        bound(
            certificate,
            metric["coefficients"]["native_stored_inverse_dual_area"][i],
            "inverse_dual_area/" + str(i),
        )
    rows.append(
        dict(
            label="complete_unique_arithmetic_event_coverage",
            passed=sorted(used) == list(range(expected_events)),
        )
    )
    return rows


def compare(metric, primary, refined):
    if (primary["refinement"], refined["refinement"]) != (1, 2):
        raise ValueError("Require both independently executed precision forms")
    rows = []

    def visit(actual, first, second, path):
        if isinstance(first, dict):
            if (
                not isinstance(actual, dict)
                or set(actual) != set(first)
                or set(first) != set(second)
            ):
                raise ValueError("Incomplete/extra metric field set: " + path)
            for key in first:
                visit(actual[key], first[key], second[key], path + "." + key)
            return
        if isinstance(first, list):
            if (
                not isinstance(actual, list)
                or len(actual) != len(first)
                or len(first) != len(second)
            ):
                raise ValueError("Metric owner axis changed: " + path)
            for i, (a, b, c) in enumerate(zip(actual, first, second, strict=True)):
                visit(a, b, c, path + "/" + str(i))
            return
        if first is None or type(first) is int:
            rows.append(
                dict(
                    path=path,
                    kind="exact_owner_or_unavailable_role",
                    passed=actual == first == second,
                )
            )
            return
        if type(actual) is not float or not math.isfinite(actual):
            raise ValueError("Metric readout must retain finite binary64 scalars: " + path)
        truth, other = Decimal(first), Decimal(second)
        value = Decimal.from_float(actual)
        a, b = float(truth), float(other)
        exact_projection = (
            math.isfinite(a)
            and a.hex() == b.hex()
            and (actual.hex() == a.hex() or actual == a == 0.0)
        )
        if truth != 0 and (a == 0 or not math.isfinite(a)):
            exact_projection = False
        resolution = abs(truth - other)
        error = abs(value - truth)
        stored_coefficient = path.startswith("coefficients.native_stored_")
        if stored_coefficient:
            budget = Decimal.from_float(math.ulp(a)) / 2 if math.isfinite(a) else Decimal(0)
            passed = exact_projection and resolution <= Decimal.from_float(math.ulp(a)) * Decimal(
                "0.1"
            )
            policy = "exact independent binary64 store projection; no added numeric floor"
        else:
            area = any(name in path for name in (".tri_sa", ".vor_sa", ".tri_sa_o", ".area_m2"))
            direction = any(
                name in path
                for name in ("tangent_xy", "normal_xy", ".tri_tang", ".vor_tang", "length_ratio")
            )
            floor = Decimal("1e-26" if area else "1e-14" if direction else "1e-27")
            budget = floor + Decimal("6e-12") * abs(truth)
            passed = (
                exact_projection
                and error <= budget
                and error <= 32 * Decimal.from_float(math.ulp(a))
                and resolution <= Decimal("0.1") * budget
            )
            policy = "existing typed geometry floor +6e-12 relative, 32ulp and exact projection"
        rows.append(
            dict(
                path=path,
                actual_binary64_hex=actual.hex(),
                reference_decimal=str(truth),
                refined_reference_decimal=str(other),
                absolute_error_decimal=str(error),
                budget_decimal=str(budget),
                reference_resolution_decimal=str(resolution),
                exact_projection=exact_projection,
                policy=policy,
                passed=bool(passed),
            )
        )

    with localcontext() as context:
        context.prec = max(primary["precision_digits"], refined["precision_digits"]) + 128
        for key in ("native_roles", "full_dual_metrics", "coefficients"):
            visit(metric[key], primary[key], refined[key], key)
    role_check = metric["anchor_roles"] == primary["anchor_roles"] == refined["anchor_roles"]
    certs = _certificates(metric, primary)
    domains = all(
        reference[key]["passed"]
        for reference in (primary, refined)
        for key in ("primal_complex", "dual_complex")
    )
    layout = all(
        row["passed"] for reference in (primary, refined) for row in reference["layout_checks"]
    )
    owners = all(
        value for reference in (primary, refined) for value in reference["strict_seed_owner_checks"]
    )
    orientation = all(
        row["passed"] for reference in (primary, refined) for row in reference["orientation_checks"]
    )
    convexity = all(
        value for reference in (primary, refined) for value in reference["primal_convexity_checks"]
    )
    return dict(
        kind="cells.stable_mesh_metric_independent_comparison@1",
        rows=rows,
        arithmetic_certificates=certs,
        exact_area_owner_roles=role_check,
        independent_complex_geometry=domains,
        independent_source_layout=layout,
        independent_seed_owners=owners,
        independent_orientation=orientation,
        independent_primal_convexity=convexity,
        passed=all(row["passed"] for row in rows)
        and all(row["passed"] for row in certs)
        and role_check
        and domains
        and layout
        and owners
        and orientation
        and convexity,
        physical_geometry_admitted=False,
        native_equivalence=False,
        actual_outgoing_values_used_to_set_budgets=False,
    )
