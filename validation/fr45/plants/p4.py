"""P4 (C7): the free-site load taken per population, not summed over the set, in the compiled step and the host report
alike (CRITERIA:124). Seams: site_occupancy.stage_loads, and the host report's L_R entries (step_report), which then
name each population's load, as the format sample's INVENTED-W5-P4 shows."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P4"
CHANGE = "stage_loads: L_R per population, not summed over its set, in the step and the host report"


def apply():
    honest_loads, honest_report = so.stage_loads, so.step_report

    def planted(n, member_free, c, vol, mb, p, *, xp):
        load_n, _, load_b = honest_loads(n, member_free, c, vol, mb, p, xp=xp)
        return load_n, mb * p.site_on_rate * c, load_b

    def planted_report(spec, declaration, state, control, p, dt):
        report = honest_report(spec, declaration, state, control, p, dt)
        h, _, load_r, _ = so.first_stage_loads(state, control, p, dt)  # Per population, by `planted`.
        per_population = [dict(kind="L_R", id=x.site_set or x.id, sums=[x.id], per_s=float(load_r[k]))
                          for k, x in enumerate(declaration.populations)]  # fmt: skip
        loads = [x for x in report["loads"] if x["kind"] == "L_n"] + per_population + [
            x for x in report["loads"] if x["kind"] == "L_B"]  # fmt: skip
        worst = max(loads, key=lambda x: x["per_s"])
        h_max = h * worst["per_s"]
        return {**report, "loads": loads, "max_load": dict(worst), "h_max_load": h_max,
                "first_stage_verdict": "admitted" if h_max <= so.THETA else "refused"}  # fmt: skip

    so.stage_loads = planted
    so.step_report = planted_report
