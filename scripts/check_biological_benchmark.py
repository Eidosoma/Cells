"""Offline BIO-001 data-contract checks; no fitting, simulation or biology verdict."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/biology/bonzanni2020_rptec_v1"
ROLES = {"C1": "fit", "C2": "fit", "C3": "evaluation", "C4": "quarantined", "C5": "quarantined"}
FIGURES = {
    "sources/biolopen-9-048553-g2.jpg": (
        "f7a79041283260cf6dd3d040edf9192ded7d6420f0dc70191b2f912fe690f475"
    ),
    "sources/biolopen-9-048553-g3.jpg": (
        "a4a74eb3f135398bed91ee6131ce513c1a2a4a7a0fb8da50627e48d1cd8f3fad"
    ),
}
RECIPE_COLUMNS = (
    "NaCl_mM",
    "KCl_mM",
    "CaCl2_mM",
    "MgCl2_mM",
    "HEPES_mM",
    "glucose_mM",
    "figure2b_Na_mM",
    "figure2b_K_mM",
    "figure2b_Cl_mM",
)
# Explicit source transcription witnesses, not simulator targets.
RECIPES = {
    "C1": (140, 5.4, 1.8, 1, 10, 5.5, 140, 5.4, 151),
    "C2": (110, 35.4, 1.8, 1, 10, 5.5, 110, 35.4, 151),
    "C3": (80, 65.4, 1.8, 1, 10, 5.5, 80, 65.4, 151),
    "C4": (45, 100.4, 1.8, 1, 0, 5.5, 45, 110.4, 151),
    "C5": (10, 135.4, 1.8, 1, 0, 5.5, 10, 145.4, 151),
}
ENDPOINTS = {"C1": (-39, 52, 9), "C2": (-24, 26, 3), "C3": (-18, 20, 3)}
ENDPOINT_COLUMNS = (
    "condition_id",
    "mean_voltage_mV_approx",
    "digitization_bound_mV",
    "published_sem_mV",
    "n_cells",
    "n_experiments",
    "source_panel",
    "extraction",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    parsed = float(value)
    require(math.isfinite(parsed), "Nonfinite data value")
    return parsed


def close(first, second):
    return math.isclose(first, second, rel_tol=0, abs_tol=1e-9)


def read_rows(path, columns):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == list(columns), f"Unexpected CSV schema: {path.name}")
        rows = list(reader)
    require(all(None not in row and None not in row.values() for row in rows), "Malformed CSV row")
    ids = [row["condition_id"] for row in rows]
    require(len(ids) == len(set(ids)), "Duplicate condition")
    return {row["condition_id"]: row for row in rows}


def verify(directory=DATA):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["dataset_id"] == "bonzanni2020_rptec_endpoints@1", "Wrong dataset identity")
    require(manifest["status"] == "provisional_figure_derived_summary", "Data status changed")
    source = manifest["source"]
    require(source["doi"] == "10.1242/bio.048553", "Source DOI changed")
    require(source["license"] == "CC-BY-4.0", "Source attribution/license required")
    figures = source["figures"]
    require(len(figures) == len(FIGURES), "Figure inventory changed")
    require({f["path"]: f["sha256"] for f in figures} == FIGURES, "Source figure identity changed")
    for figure in figures:
        require(figure["modified"] is False, "Source figure must be unmodified")
        content = (directory / figure["path"]).read_bytes()
        require(
            hashlib.sha256(content).hexdigest() == figure["sha256"], "Source figure bytes changed"
        )

    split = manifest["split"]
    for role in ("fit", "evaluation", "quarantined"):
        require(
            split[role] == [key for key, value in ROLES.items() if value == role], "Split changed"
        )
    require(split["blinded"] is False and split["prospective"] is False, "Retrospective data only")
    recording = manifest["recording"]
    require(recording["cell_line"] == "RPTEC/TERT1", "Wrong cell line")
    require(recording["configuration"] == "whole_cell_zero_applied_current", "Boundary changed")
    require(
        recording["sampling_kind"] == "condition_endpoint_not_time_series",
        "Endpoints are not times",
    )
    require(recording["temperature_C"] == 25, "Source temperature changed")
    require(
        close(recording["temperature_K"], recording["temperature_C"] + 273.15), "Temperature units"
    )
    require(recording["minimum_recording_s"] == 30, "Recording duration changed")
    require(recording["liquid_junction_potential_corrected"] is True, "Junction correction changed")
    require(recording["series_resistance_compensated"] is False, "Resistance correction changed")
    require(recording["leak_corrected"] is False, "Leak correction changed")
    require(
        recording["cell_pairing_across_conditions"] == "not_established", "Pairing not established"
    )
    require(recording["intercellular_coupling"] == "not_established", "Isolation not established")
    require(
        recording["intracellular_solution"]["free_intracellular_ion_concentrations"]
        == "not_established_by_recipe",
        "Recipe cannot supply measured free ions",
    )

    uncertainty = manifest["uncertainty"]
    require(uncertainty["source_error_bar_kind"] == "SEM", "Source reports SEM")
    for name in (
        "sem_transcribed",
        "raw_per_cell_data_retained",
        "independent_experiment_data_retained",
        "second_reader_verified",
    ):
        require(uncertainty[name] is False, f"Unestablished uncertainty claim: {name}")
    require(uncertainty["digitization_bound_mV"] == 2, "Reading bound changed")
    require(
        uncertainty["digitization_bound_kind"]
        == "curator_reading_bound_not_statistical_uncertainty",
        "Reading error is not statistical uncertainty",
    )
    claims = manifest["claims"]
    for name in ("production_config", "model_fitted", "simulation_run", "biologically_validated"):
        require(claims[name] is False, f"Unestablished result: {name}")
    require(
        claims["quantitative_biological_acceptance"]
        == "not_assessable_with_current_uncertainty_and_boundary",
        "No biological acceptance yet",
    )

    conditions = read_rows(directory / "conditions.csv", ("condition_id", *RECIPE_COLUMNS, "role"))
    require(list(conditions) == list(ROLES), "Condition inventory/order changed")
    residuals = {}
    for identity, row in conditions.items():
        values = tuple(number(row[c]) for c in RECIPE_COLUMNS)
        require(
            all(close(a, b) for a, b in zip(values, RECIPES[identity], strict=True)),
            "Source recipe changed",
        )
        require(row["role"] == ROLES[identity], "Condition role changed")
        na, k, ca, mg, _, _, reported_na, reported_k, reported_cl = values
        require(close(na + k + 2 * ca + 2 * mg, reported_cl), "Recipe chloride accounting")
        discrepancy = reported_k - k
        require(
            close(discrepancy, 10 if identity in ("C4", "C5") else 0), "Quarantine discrepancy lost"
        )
        residuals[identity] = round(reported_na + reported_k + 2 * ca + 2 * mg - reported_cl, 9)
        if row["role"] != "quarantined":
            require(
                close(reported_na + reported_k - reported_cl, -5.6), "Background-ion charge lost"
            )

    endpoints = read_rows(directory / "voltage_endpoints.csv", ENDPOINT_COLUMNS)
    require(
        list(endpoints) == list(ENDPOINTS), "Endpoint inventory includes missing/quarantined data"
    )
    voltage_V = {}
    for identity, row in endpoints.items():
        mean, cells, experiments = ENDPOINTS[identity]
        require(number(row["mean_voltage_mV_approx"]) == mean, "Approximate endpoint changed")
        require(number(row["digitization_bound_mV"]) == 2, "Endpoint reading bound changed")
        require(
            row["published_sem_mV"] == "", "Unknown SEM must not become zero or an invented value"
        )
        require(
            int(row["n_cells"]) == cells and int(row["n_experiments"]) == experiments,
            "Replication counts changed",
        )
        require(row["source_panel"] == "Figure_3C", "Endpoint locator changed")
        require(row["extraction"] == "manual_visual_nearest_1_mV", "Extraction method changed")
        voltage_V[identity] = mean * 1e-3

    return {
        "dataset_id": manifest["dataset_id"],
        "integrity_status": "pass",
        "source_figures_checked": len(figures),
        "conditions_checked": len(conditions),
        "approximate_endpoints_checked": len(endpoints),
        "fit": split["fit"],
        "evaluation": split["evaluation"],
        "quarantined": split["quarantined"],
        "figure2b_charge_residual_mM_equivalents": residuals,
        "approximate_endpoint_voltage_V": voltage_V,
        "mean_extraction_independently_verified": False,
        "numerical_simulation": "not_run",
        "model_fit": "not_run",
        "biological_acceptance": "not_assessable",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()
    print(json.dumps(verify(args.data), indent=2, allow_nan=False))
