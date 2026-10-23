"""Shared queue adapter with independent-world counts and per-cell assembly outcomes."""

import math

import numpy as np

from cells.assembly_cluster import MODEL_ID, engine
from cells.ensemble.coupled import load_checkpoint, write_checkpoint  # noqa: F401


def run(spec, *, backend="gpu", state=None, callback=None):
    def record(window, current):
        if callback:
            callback(window, current, None)

    return engine.run(spec, backend=backend, state=state, callback=record)


def aggregate(rows):
    from cells.ensemble.cli import add_ionic_observables, wilson

    groups = {}
    for row in rows:
        arm = groups.setdefault(
            row["arm"],
            {
                "model": MODEL_ID,
                "physical_model": row["physical_model"],
                "cell_ids": row["cell_ids"],
                "channel_ids": row["channel_ids"],
                "worlds": 0,
                "committed_events": 0,
                "execute_seconds": 0.0,
                "task_wall_seconds": [],
                "task_seconds_per_world": [],
                "assembly_cells": {},
                "experimental_validation": False,
            },
        )
        if (
            arm["cell_ids"] != row["cell_ids"]
            or arm["channel_ids"] != row["channel_ids"]
            or arm["physical_model"] != row["physical_model"]
        ):
            raise ValueError("Cluster arm changed physical owners")
        if (
            row["physical_model"]
            in (
                "spatial_calcium@4",
                "spatial_calcium@5",
                "resolved_calcium@1",
                "resolved_calcium@2",
                "resolved_calcium@3",
                "resolved_calcium@4",
                "resolved_calcium@5",
                "resolved_calcium@6",
            )
            and "ip3" not in row
        ):
            raise ValueError("Cluster IP3 model requires ligand readouts")
        if row["physical_model"] in (
            "resolved_calcium@1",
            "resolved_calcium@2",
            "resolved_calcium@3",
            "resolved_calcium@4",
            "resolved_calcium@5",
            "resolved_calcium@6",
        ):
            if "calcium" not in row:
                raise ValueError("Resolved cluster requires calcium readouts")
            for key in ("final_voltage_axis", "voltage_owner_ids"):
                if key not in row or arm.setdefault(key, row[key]) != row[key]:
                    raise ValueError("Resolved cluster voltage owners changed or missing")
            if row["final_voltage_axis"] != "membrane_patch" or np.asarray(
                row["final_voltage_V"]
            ).shape != (row["worlds"], len(row["voltage_owner_ids"])):
                raise ValueError("Resolved cluster voltage shape/axis invalid")
        if "ip3" in row:
            ip3 = row["ip3"]
            if ip3["cell_ids"] != row["cell_ids"]:
                raise ValueError("Cluster IP3 owners must match physical cells")
            target = arm.setdefault("ip3", {"law": ip3["law"], "cell_ids": ip3["cell_ids"]})
            if target["law"] != ip3["law"] or target["cell_ids"] != ip3["cell_ids"]:
                raise ValueError("Cluster IP3 law or owners changed")
            for key in ("cytosol_mM", "release_fraction"):
                values = np.asarray(ip3[key])
                if (
                    values.shape != (row["worlds"], len(row["cell_ids"]))
                    or not np.all(np.isfinite(values))
                    or np.any(values < 0)
                    or (key == "release_fraction" and np.any(values > 1))
                ):
                    raise ValueError("Cluster IP3 readouts have invalid owner shape or domain")
                value = np.sum(values, axis=0)
                name = key + "_sum_over_worlds"
                if name in target and np.asarray(target[name]).shape != value.shape:
                    raise ValueError("Cluster IP3 owner shape changed")
                target[name] = (np.asarray(target.get(name, np.zeros_like(value))) + value).tolist()
        if "calcium" in row:
            calcium = row["calcium"]
            target = arm.setdefault("calcium", {"species_ids": calcium["species_ids"]})
            if target["species_ids"] != calcium["species_ids"]:
                raise ValueError("Cluster calcium species changed")
            for key in ("cytosol_amounts_fmol", "er_voltage_V"):
                value = np.sum(np.asarray(calcium[key]), axis=0)
                name = key + "_sum_over_worlds"
                if name in target and np.asarray(target[name]).shape != value.shape:
                    raise ValueError("Cluster calcium owner shape changed")
                target[name] = (np.asarray(target.get(name, np.zeros_like(value))) + value).tolist()
        if "calcium_channels" in row:
            channels = row["calcium_channels"]
            target = arm.setdefault("calcium_channels", {"ids": channels["ids"]})
            if target["ids"] != channels["ids"]:
                raise ValueError("Cluster calcium channel owners changed")
            for key in ("gate", "transferred_fmol", "dissipated_energy_pJ"):
                value = np.sum(np.asarray(channels[key]), axis=0)
                name = key + "_sum_over_worlds"
                if name in target and np.asarray(target[name]).shape != value.shape:
                    raise ValueError("Cluster calcium channel shape changed")
                target[name] = (np.asarray(target.get(name, np.zeros_like(value))) + value).tolist()
        if row["physical_model"] in (
            "resolved_calcium@4",
            "resolved_calcium@5",
            "resolved_calcium@6",
        ):
            for key in (
                "channel_transfer_axes",
                "channel_species_ids",
                "channel_relative_permeability",
            ):
                if key not in row or arm.setdefault(key, row[key]) != row[key]:
                    raise ValueError("Cluster channel species/routes changed or missing")
            species = row["channel_species_ids"]
            shape = (len(species), len(row["channel_ids"]))
            if (
                row["channel_transfer_axes"] != ["world", "species", "channel"]
                or species != row["calcium"]["species_ids"]
                or np.asarray(row["channel_relative_permeability"]).shape != shape
                or np.asarray(row["channel_transferred_fmol"]).shape != (row["worlds"], *shape)
            ):
                raise ValueError("Cluster channel species/transfer axes invalid")
        for key in ("worlds", "committed_events", "execute_seconds"):
            arm[key] += row[key]
        wall = row["wall_end"] - row["wall_start"]
        arm["task_wall_seconds"].append(wall)
        arm["task_seconds_per_world"].append(wall / row["worlds"])
        arrays = ("channel_transferred_fmol", "availability_exposure_s")
        add_ionic_observables(arm, {k: v for k, v in row.items() if k not in arrays})
        for source in arrays:
            destination = source + "_sum_by_owner"
            values = np.asarray(row[source], dtype=float)
            totals = np.array(
                [math.fsum(values[(slice(None), *i)]) for i in np.ndindex(values.shape[1:])]
            ).reshape(values.shape[1:])
            previous = np.asarray(arm.setdefault(destination, np.zeros_like(totals).tolist()))
            if previous.shape != totals.shape:
                raise ValueError("Cluster channel/availability shape changed")
            arm[destination] = (previous + totals).tolist()
        for owner, cell in row["assembly_cells"].items():
            target = arm["assembly_cells"].setdefault(owner, {})
            for key in ("model", "stream_id", "seed"):
                if target.setdefault(key, cell[key]) != cell[key]:
                    raise ValueError("Cluster arm changed cell random stream")
            for key in (
                "worlds",
                "committed_events",
                "final_free_trimers",
                "final_attached_trimers",
                "final_fragment_trimers",
                "initial_total_trimers",
                "material_residual_trimers",
                "ever_full_cages",
                "currently_full_cages",
                "full_cage_dwell_total_s",
            ):
                target[key] = target.get(key, 0) + cell[key]
            for key in ("final_size_histogram", "final_bond_histogram", "dwell_by_size_total_s"):
                previous = target.setdefault(key, [0] * len(cell[key]))
                target[key] = [a + b for a, b in zip(previous, cell[key], strict=True)]
            reactions = target.setdefault(
                "reaction_counts", dict.fromkeys(cell["reaction_counts"], 0)
            )
            for key, value in cell["reaction_counts"].items():
                reactions[key] += value
            target["completion_probability"] = target["ever_full_cages"] / target["worlds"]
            target["completion_probability_wilson_95"] = wilson(
                target["ever_full_cages"], target["worlds"]
            )
    return groups
