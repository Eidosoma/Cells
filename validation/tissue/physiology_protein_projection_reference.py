"""Independent named-owner Decimal protein stocks/charge and explicit deltas.

No Cells/JAX imports, production slot maps or production geometry arrays are
used in arithmetic. Source pL volumes convert by exact decimal 1e-15. The raw
component vectors are interpreted only through their explicitly declared IDs.
"""

import hashlib
import json
from decimal import Decimal, localcontext

import numpy as np


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _number(value):
    return Decimal.from_float(float(value))


def _owners(raw, binding, protein):
    if binding.get("source_definition_sha256") != _digest(raw) or binding.get(
        "identity"
    ) != _digest({key: value for key, value in binding.items() if key != "identity"}):
        raise ValueError("Independent source/binding declaration mismatch")
    model = raw["model"].get("ionic", raw["model"])
    result = {}
    for domain, rows, field in (
        ("cell", model["cells"], "cell_mol_m3"),
        ("environment", model["extracellular"], "environment_mol_m3"),
    ):
        ids = binding["inputs"][domain + "_ids"]
        values = np.asarray(protein[field])
        if (
            len(set(ids)) != len(ids)
            or set(ids) != {row["id"] for row in rows}
            or values.shape != (len(ids),)
            or not np.isfinite(values).all()
            or np.any(values < 0)
        ):
            raise ValueError("Independent physical protein owner mismatch")
        concentrations = dict(zip(ids, values, strict=True))
        result[domain] = {row["id"]: (concentrations[row["id"]], row["volume_pL"]) for row in rows}
    return result


def project(raw, binding, protein, *, valence, faraday_C_mol):
    owners = _owners(raw, binding, protein)
    with localcontext() as context:
        context.prec = 4096
        z, f = _number(valence), _number(faraday_C_mol)
        result = {}
        total, charge = Decimal(0), Decimal(0)
        for domain, rows in owners.items():
            result[domain] = {}
            for owner, (concentration, volume_pL) in rows.items():
                amount = _number(concentration) * _number(volume_pL) * Decimal("1e-15")
                q = amount * z * f
                result[domain][owner] = dict(
                    amount_mol=float(amount),
                    amount_fmol=float(amount * Decimal("1e15")),
                    charge_C=float(q),
                )
                total += amount
                charge += q
        result.update(total_amount_mol=float(total), total_charge_C=float(charge))
        return result


def delta(raw, binding, before, after, *, valence, faraday_C_mol):
    reference, current = _owners(raw, binding, before), _owners(raw, binding, after)
    with localcontext() as context:
        context.prec = 4096
        z, f = _number(valence), _number(faraday_C_mol)
        result = {}
        total, charge, gross = Decimal(0), Decimal(0), Decimal(0)
        for domain, rows in reference.items():
            result[domain] = {}
            for owner, (concentration, volume_pL) in rows.items():
                change = _number(current[domain][owner][0]) - _number(concentration)
                amount = change * _number(volume_pL) * Decimal("1e-15")
                q = amount * z * f
                result[domain][owner] = dict(
                    amount_delta_mol=float(amount),
                    amount_delta_fmol=float(amount * Decimal("1e15")),
                    charge_delta_C=float(q),
                )
                total += amount
                charge += q
                gross += abs(amount)
        result.update(
            balance_residual_mol=float(total),
            balance_residual_C=float(charge),
            gross_change_mol=float(gross),
        )
        return result
