"""Hold post-start UTP out of a five-pool material balance for Huber et al., Fig. 8."""

import json
from math import fsum
from pathlib import Path


def compare():
    source = Path(__file__).with_name("data") / "fr43_uridine_pool.json"
    data = json.loads(source.read_text())
    first, *later = [dict(zip(data["columns"], values, strict=True)) for values in data["rows"]]
    upstream = ("uridine_mM", "UMP_mM", "UDP_mM")
    results = []
    for row in later:
        received = fsum(first[k] - row[k] for k in upstream)
        spent = row["UDP_GalNAc_mM"] - first["UDP_GalNAc_mM"]
        predicted = first["UTP_mM"] + received - spent
        results.append(
            dict(
                time_h=row["time_h"],
                supply_mM=received,
                spending_mM=spent,
                predicted_UTP_mM=predicted,
                observed_UTP_mM=row["UTP_mM"],
                observed_UTP_SD_mM=row["UTP_SD_mM"],
                predicted_minus_observed_mM=predicted - row["UTP_mM"],
            )
        )
    residuals = [row["predicted_minus_observed_mM"] for row in results]
    return dict(rows=results, residual_range_mM=[min(residuals), max(residuals)])


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2, allow_nan=False))
