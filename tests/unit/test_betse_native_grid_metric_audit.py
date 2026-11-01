"""Stdlib synthetic observations only; no native/numerical library execution."""

import ast
import hashlib
import json
import math
import os
import struct
import unittest
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from pathlib import Path

from cells.processes import betse_native_grid_metric_audit as metric

FLUX = (("N", "flux"), ("S", "flux"), ("E", "flux"), ("W", "flux"))


def bits(value):
    return struct.pack(">d", value).hex()


def observation(*, nx=2, ny=2, xspan=2.0, yspan=2.0, delta=1.0):
    # Explicit synthetic axes, not a replacement native linspace or an input
    # transformation for any saved grid. Fraction supplies a separate fixture
    # construction; the audit receives and retains these final binary64 values.
    x = tuple(float(Fraction.from_float(xspan) * i / nx) for i in range(nx + 1))
    y = tuple(float(Fraction.from_float(yspan) * i / ny) for i in range(ny + 1))
    points = tuple(
        ((x[j] + x[j + 1]) / 2, (y[i] + y[i + 1]) / 2) for i in range(ny) for j in range(nx)
    )
    return metric.GridObservation(
        (ny, nx),
        (0.0, xspan, 0.0, yspan),
        delta,
        points,
        tuple((i, j) for i in range(ny) for j in range(nx)),
        x,
        y,
        "synthetic observation; no retained native input changed",
    )


class GridMetricAuditTests(unittest.TestCase):
    def retain(self, label, report):
        if folder := os.environ.get("CELLS_GRID_METRIC_EVIDENCE"):
            path = Path(folder) / hashlib.sha256(self.id().encode()).hexdigest()[:20]
            path.mkdir(parents=True, exist_ok=True)
            with (path / (label + ".json")).open("x") as stream:
                json.dump(
                    dict(test_id=self.id(), identity=report.identity, report=report.record),
                    stream,
                    sort_keys=True,
                    indent=2,
                    allow_nan=False,
                )
                stream.write("\n")

    def test_uniform_observation_is_data_only_and_inputs_are_unchanged(self):
        raw = observation()
        original = (
            raw.shape,
            raw.bounds_m,
            raw.delta_m,
            raw.coordinates_m,
            raw.map_ij2k,
            raw.vertices_x_m,
            raw.vertices_y_m,
        )
        report = metric.audit(raw, boundaries=FLUX)
        self.assertIs(report.observation, raw)
        self.assertTrue(report.record["uniform_metric_passed"])
        self.assertTrue(report.record["selected_native_observation_checks_passed"])
        self.assertIs(metric.require_uniform_metric(report), report)
        for current, old in zip(
            (
                raw.shape,
                raw.bounds_m,
                raw.delta_m,
                raw.coordinates_m,
                raw.map_ij2k,
                raw.vertices_x_m,
                raw.vertices_y_m,
            ),
            original,
            strict=True,
        ):
            self.assertIs(current, old)
        for key in (
            "source_correspondence_verified",
            "grid_binding_constructed",
            "metric_repair_supplied",
            "native_or_operator_execution",
            "physical_phase_checkpoint_admitted",
        ):
            self.assertFalse(report.record[key])
        self.retain("uniform", report)

    def test_nonintegral_span_preserves_source_geometry_and_refuses_scalar_metric(self):
        raw = observation(yspan=2.5)
        report = metric.audit(raw, boundaries=FLUX)
        record = report.record
        self.assertTrue(record["selected_native_observation_checks_passed"])
        self.assertFalse(record["uniform_metric_passed"])
        self.assertEqual(record["axes"]["y"]["rounded_native_int_count"], 2)
        self.assertEqual(record["axes"]["y"]["effective_spacing_to_delta_ratio"]["display"], "1.25")
        self.assertEqual(record["input"]["delta_binary64_bits"], bits(1.0))
        self.assertEqual(
            record["input"]["coordinates_binary64_bits"],
            [[bits(x), bits(y)] for x, y in raw.coordinates_m],
        )
        with self.assertRaises(metric.UniformMetricRejected) as caught:
            metric.require_uniform_metric(report)
        self.assertIs(caught.exception.audit, report)
        self.assertIs(caught.exception.observation, raw)
        self.retain("source_consistent_metric_refused", report)

    def test_synthetic_625_points_match_reported_aspect_without_rescaling_any_input(self):
        raw = observation(nx=25, ny=25, xspan=25.0, yspan=25.3110668642)
        original = raw.coordinates_m
        report = metric.audit(raw, boundaries=FLUX)
        record = report.record
        self.assertEqual(len(raw.coordinates_m), 625)
        self.assertEqual(record["axes"]["y"]["rounded_native_int_count"], 25)
        self.assertTrue(record["selected_native_observation_checks_passed"])
        self.assertFalse(record["checks"]["spans_per_count_match_scalar_delta"])
        ratio = record["axes"]["y"]["effective_spacing_to_delta_ratio"]
        self.assertAlmostEqual(float(ratio["display"]), 25.3110668642 / 25, places=14)
        self.assertIs(raw.coordinates_m, original)
        self.assertEqual(record["input"]["bounds_binary64_bits"][3], bits(25.3110668642))
        with self.assertRaises(metric.UniformMetricRejected):
            metric.require_uniform_metric(report)
        self.retain("synthetic625_refusal", report)

    def test_counts_truncate_toward_zero_and_reversed_bounds_are_not_sorted(self):
        raw = observation(yspan=-2.5)
        report = metric.audit(raw, boundaries=FLUX)
        self.assertEqual(report.record["axes"]["y"]["rounded_native_int_count"], -2)
        self.assertEqual(raw.bounds_m[2:], (0.0, -2.5))
        self.assertFalse(report.record["checks"]["increasing_bounds"])
        self.retain("reversed_original_bounds", report)

    def test_native_count_mismatch_is_separate_from_uniform_coordinate_gate(self):
        raw = observation()
        raw = replace(raw, shape=(2, 3))
        report = metric.audit(raw, boundaries=FLUX)
        self.assertFalse(report.record["checks"]["native_truncated_counts"])
        self.assertFalse(report.record["checks"]["coordinate_count"])
        self.assertEqual(report.record["input"]["shape"], [2, 3])
        self.retain("incomplete_shape", report)

    def test_coordinate_permutation_refuses_without_reordering_input(self):
        raw = observation()
        points = (raw.coordinates_m[1], raw.coordinates_m[0], *raw.coordinates_m[2:])
        raw = replace(raw, coordinates_m=points)
        report = metric.audit(raw, boundaries=FLUX)
        self.assertFalse(report.record["checks"]["existing_uniform_coordinate_gate"])
        self.assertFalse(report.record["checks"]["centres_match_retained_vertex_midpoints"])
        self.assertIs(raw.coordinates_m, points)
        self.retain("permuted_coordinates", report)

    def test_irregular_vertex_axis_is_distinct_from_regular_anisotropic_spacing(self):
        raw = replace(
            observation(),
            vertices_y_m=(0.0, 0.25, 2.0),
            coordinates_m=((0.5, 0.125), (1.5, 0.125), (0.5, 1.125), (1.5, 1.125)),
        )
        report = metric.audit(raw, boundaries=FLUX)
        self.assertTrue(report.record["checks"]["centres_match_retained_vertex_midpoints"])
        self.assertFalse(report.record["checks"]["observed_axis_steps_match_spans"])
        self.assertFalse(report.record["selected_native_observation_checks_passed"])
        self.assertEqual(raw.vertices_y_m, (0.0, 0.25, 2.0))
        self.retain("irregular_axis", report)

    def test_map_permutation_is_not_hidden_by_good_coordinate_metrics(self):
        raw = observation()
        raw = replace(raw, map_ij2k=(raw.map_ij2k[1], raw.map_ij2k[0], *raw.map_ij2k[2:]))
        report = metric.audit(raw, boundaries=FLUX)
        self.assertTrue(report.record["uniform_metric_passed"])
        self.assertFalse(report.record["selected_native_observation_checks_passed"])
        with self.assertRaises(metric.UniformMetricRejected):
            metric.require_uniform_metric(report)
        self.retain("permuted_map", report)

    def test_nan_payload_and_infinity_are_retained_not_json_normalized(self):
        payload = struct.unpack(">d", bytes.fromhex("7ff8000000004abc"))[0]
        for value in (payload, float("inf"), -float("inf")):
            with self.subTest(bits=bits(value)):
                raw = observation()
                raw = replace(raw, coordinates_m=((value, 0.5), *raw.coordinates_m[1:]))
                report = metric.audit(raw, boundaries=FLUX)
                self.assertFalse(report.record["checks"]["finite"])
                self.assertEqual(
                    report.record["input"]["coordinates_binary64_bits"][0][0], bits(value)
                )
                json.loads(report.record_json)
                self.retain("nonfinite_" + bits(value), report)

    def test_nonfinite_bounds_and_delta_have_no_fabricated_native_count(self):
        for field in ("bounds", "delta"):
            raw = observation()
            raw = (
                replace(raw, bounds_m=(0.0, math.inf, 0.0, 2.0))
                if field == "bounds"
                else replace(raw, delta_m=math.nan)
            )
            report = metric.audit(raw, boundaries=FLUX)
            self.assertFalse(report.record["axes"]["x"]["native_count_available"])
            self.assertFalse(report.record["uniform_metric_passed"])
            self.retain("nonfinite_" + field, report)

    def test_signed_zero_in_original_bounds_and_vertices_remains_distinguishable(self):
        raw = observation()
        raw = replace(raw, bounds_m=(-0.0, 2.0, 0.0, 2.0))
        report = metric.audit(raw, boundaries=FLUX)
        self.assertEqual(report.record["input"]["bounds_binary64_bits"][0], "8000000000000000")
        self.assertEqual(report.record["input"]["vertices_x_binary64_bits"][0], "0000000000000000")
        self.assertFalse(report.record["axes"]["x"]["endpoint_bits_match_bounds"])
        self.assertTrue(report.record["uniform_metric_passed"])
        self.retain("signed_zero", report)

    def test_zero_delta_refuses_without_division_or_replacement(self):
        for value in (0.0, -0.0):
            report = metric.audit(replace(observation(), delta_m=value), boundaries=FLUX)
            self.assertFalse(report.record["axes"]["x"]["native_count_available"])
            self.assertEqual(report.record["input"]["delta_binary64_bits"], bits(value))
            with self.assertRaises(metric.UniformMetricRejected):
                metric.require_uniform_metric(report)
            self.retain("zero_delta_" + bits(value), report)

    def test_empty_partial_coordinates_are_not_filled_in(self):
        raw = replace(observation(), coordinates_m=(), map_ij2k=())
        report = metric.audit(raw, boundaries=FLUX)
        self.assertEqual(report.record["input"]["coordinates_binary64_bits"], [])
        self.assertFalse(report.record["checks"]["coordinate_count"])
        self.assertEqual(report.record["boundary_sites"], [])
        self.retain("empty_partial", report)

    def test_cell_count_one_is_not_promoted_to_uniform_grid_binding(self):
        raw = observation(nx=1, ny=1, xspan=1.0, yspan=1.0)
        report = metric.audit(raw, boundaries=FLUX)
        self.assertFalse(report.record["checks"]["shape_at_least_two"])
        self.assertTrue(report.record["checks"]["native_truncated_counts"])
        with self.assertRaises(metric.UniformMetricRejected):
            metric.require_uniform_metric(report)
        self.retain("one_cell", report)

    def test_staggered_shapes_are_source_description_only(self):
        report = metric.audit(observation(nx=3, ny=2, xspan=3.0), boundaries=FLUX)
        shapes = report.record["source_semantics"]["staggered_shapes"]
        self.assertEqual(shapes, dict(centres=[2, 3], vertices=[3, 4], u=[2, 4], v=[3, 3]))
        self.assertTrue(
            report.record["source_semantics"][
                "staggered_shapes_are_source_description_not_observed_array_certification"
            ]
        )
        self.retain("staggered_description", report)

    def test_mixed_corner_labels_keep_original_asymmetry(self):
        labels = (("N", "flux"), ("S", "value"), ("E", "flux"), ("W", "value"))
        report = metric.audit(observation(), boundaries=labels)
        rows = {row["k"]: row for row in report.record["boundary_sites"]}
        self.assertEqual([rows[k]["source_selected_side"] for k in range(4)], ["S", "E", "N", "E"])
        self.assertEqual(rows[0]["native_label_branch"], "value identity")
        self.assertEqual(rows[0]["other_corner_labels"], {"W": "value"})
        self.assertEqual(rows[3]["other_corner_labels"], {"N": "flux"})
        self.retain("mixed_corners", report)

    def test_boundary_rows_are_centres_at_half_step_not_vertices(self):
        report = metric.audit(observation(nx=3, ny=3, xspan=3.0, yspan=3.0), boundaries=FLUX)
        rows = {row["k"]: row for row in report.record["boundary_sites"]}
        self.assertNotIn(4, rows)
        self.assertEqual(rows[3]["source_selected_side"], "W")
        self.assertEqual(rows[1]["distance_to_geometric_bounds_m"]["S"]["binary64_bits"], bits(0.5))
        self.assertEqual(rows[7]["source_selected_side"], "N")
        self.retain("centre_boundaries", report)

    def test_unknown_boundary_label_is_preserved_with_native_branch_diagnostic(self):
        labels = (("N", "flux"), ("S", "unknown"), ("E", "flux"), ("W", "value"))
        report = metric.audit(observation(nx=3, ny=3, xspan=3.0, yspan=3.0), boundaries=labels)
        self.assertFalse(report.record["checks"]["four_declared_boundary_labels"])
        rows = {row["k"]: row for row in report.record["boundary_sites"]}
        self.assertEqual(rows[0]["native_label_branch"], "value identity")
        self.assertIn("neither branch matched", rows[1]["native_label_branch"])
        self.assertEqual(report.record["input"]["boundaries"][1], ["S", "unknown"])
        self.retain("unknown_label", report)

    def test_missing_and_duplicate_boundary_labels_refuse_without_defaults(self):
        for index, labels in enumerate((FLUX[:3], (*FLUX, FLUX[0]))):
            report = metric.audit(observation(), boundaries=labels)
            self.assertFalse(report.record["checks"]["four_declared_boundary_labels"])
            self.assertEqual(len(report.record["input"]["boundaries"]), len(labels))
            self.retain("boundary_roster_" + str(index), report)

    def test_existing_tolerance_is_explicit_and_not_loosened(self):
        near = metric.audit(observation(yspan=2.0 * (1 + 1e-14)), boundaries=FLUX)
        far = metric.audit(observation(yspan=2.0 * (1 + 4e-14)), boundaries=FLUX)
        self.assertEqual(near.record["uniform_policy"]["rtol"], 2e-14)
        self.assertEqual(near.record["uniform_policy"]["coordinate_epsilon_multiplier"], 64)
        self.assertTrue(near.record["checks"]["spans_per_count_match_scalar_delta"])
        self.assertFalse(far.record["checks"]["spans_per_count_match_scalar_delta"])
        self.retain("near", near)
        self.retain("far", far)

    def test_schema_refusal_retains_original_without_coercion(self):
        class ForbiddenFloat:
            def __float__(self):
                raise AssertionError("Audit must never coerce observations")

        for raw in (
            replace(observation(), delta_m=ForbiddenFloat()),
            replace(observation(), shape=(True, 2)),
            replace(observation(), coordinates_m=[]),
        ):
            with self.assertRaises(metric.MetricInputRejected) as caught:
                metric.audit(raw, boundaries=FLUX)
            self.assertIs(caught.exception.observation, raw)

    def test_metadata_capacity_refusal_retains_observation(self):
        raw = replace(observation(), coordinates_m=((0.0, 0.0),) * (metric.MAX_OBSERVED_POINTS + 1))
        with self.assertRaises(metric.MetricInputRejected) as caught:
            metric.audit(raw, boundaries=FLUX)
        self.assertIs(caught.exception.observation, raw)

    def test_observation_and_report_are_frozen_and_return_fresh_json_views(self):
        raw = observation()
        report = metric.audit(raw, boundaries=FLUX)
        with self.assertRaises(FrozenInstanceError):
            raw.delta_m = 2.0
        edited = report.record
        edited["uniform_metric_passed"] = False
        self.assertTrue(report.record["uniform_metric_passed"])
        self.assertIs(metric.validate(report), report)
        self.retain("original_report", report)

    def test_rehashed_forged_pass_still_refuses_by_recomputing_original_data(self):
        report = metric.audit(observation(yspan=2.5), boundaries=FLUX)
        edited = report.record
        edited["uniform_metric_passed"] = edited["all_observation_checks_passed"] = True
        text = json.dumps(edited, sort_keys=True, separators=(",", ":"), allow_nan=False)
        forged = replace(
            report, record_json=text, identity=hashlib.sha256(text.encode()).hexdigest()
        )
        with self.assertRaises(metric.MetricInputRejected) as caught:
            metric.require_uniform_metric(forged)
        self.assertIs(caught.exception.audit, forged)
        self.retain("actual_refusal", report)

    def test_boundary_input_order_is_retained_not_normalized(self):
        a = metric.audit(observation(), boundaries=FLUX)
        b = metric.audit(a.observation, boundaries=tuple(reversed(FLUX)))
        self.assertNotEqual(a.identity, b.identity)
        self.assertEqual(b.record["input"]["boundaries"], [list(v) for v in reversed(FLUX)])
        self.retain("first_order", a)
        self.retain("other_order", b)

    def test_pinned_original_source_metadata_without_importing_or_executing_it(self):
        if not (folder := os.environ.get("CELLS_GRID_METRIC_NATIVE_ROOT")):
            self.skipTest("Pinned native text is optional for ordinary portable unit controls")
        root = Path(folder)
        for name, expected in metric.SOURCE_PINS:
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected)
        tree = ast.parse((root / metric.SOURCE_PINS[0][0]).read_text())
        cls = next(
            n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FiniteDiffSolver"
        )
        grid = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "cell_grid")
        lap = next(
            n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "makeLaplacian"
        )
        self.assertEqual((grid.lineno, grid.end_lineno), (158, 250))
        self.assertEqual((lap.lineno, lap.end_lineno), (252, 431))
        rendered = ast.unparse(grid)
        self.assertIn("int((self.ymax - self.ymin) / grid_delta)", rendered)
        self.assertIn("np.linspace(ymin, ymax, self.grid_ny + 1)", rendered)
        self.assertIn("A = A / self.delta ** 2", ast.unparse(lap))


if __name__ == "__main__":
    unittest.main()
