"""The numbers behind a bead and a glow on a run with a secreted species, from its own 64-bit arrays.

    python3 tools/reference_flow.py RUN_FOLDER RUN_ID TIME > reference.json

Worked out outside the viewer, for `tools/check_layers.mjs flow` (REFERENCE names the file): the saved
totals at the record at TIME and at the one before, the mean rate between them, the busiest lane over the
whole run and the token that follows from it, the largest mean power and the scale's end. Standard
library only (the adapter's own reader of .npz files). The reference for the engine's first development
run at 0.4 s is kept in tools/references/.
"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapt_run as A

folder, run_id, time = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
names = ["observation_times", "observed_face_transferred", "observed_exchange_moved_fmol", "observed_membrane_transferred", "observed_face_dissipated_energy_pJ", "observed_membrane_dissipated_energy_pJ", "observed_pump_dissipated_energy_pJ", "observed_amount", "observed_extracellular_amount"]
data = A.read_npz(folder / "trajectory.npz", names)
config = json.load(open(folder / "resolved_config.json"))
model = config["model"]
species = [item["id"] for item in model["species"]]
row = species.index("S")
t = list(data["observation_times"].values)
count = len(t)
step = min(range(count), key=lambda k: abs(t[k] - time))
assert step >= 1 and abs(t[step] - time) < 1e-9

def at(name, k, *where):
    shape = tuple(data[name].shape)[1:]
    per = 1
    for size in shape:
        per *= size
    offset = 0
    for size, index in zip(shape, where):
        offset = offset * size + index
    return data[name].values[k * per + offset]

cells = [item["id"] for item in model["cells"]]
nodes = [item["id"] for item in model["extracellular"]]
faces = model["faces"]
routes = [route for operator in model["operators"] if operator["law"] == "scheduled_species_exchange@1" for route in operator["routes"]]
membranes = {item["id"]: item for item in model["membranes"]}
lanes = {}
series = {}
for index, face in enumerate(faces):
    series[face["id"]] = ([at("observed_face_transferred", k, row, index) for k in range(count)], face["sender"], face["receiver"])
for index, route in enumerate(routes):
    patch = membranes[route["patch"]]
    series[route["id"]] = ([at("observed_exchange_moved_fmol", k, index) for k in range(count)], patch["inside"], patch["outside"])
busiest = 0.0
for name, (values, first, second) in series.items():
    for k in range(1, count):
        busiest = max(busiest, abs((values[k] - values[k - 1]) / (t[k] - t[k - 1])))
    mean = (values[step] - values[step - 1]) / (t[step] - t[step - 1])
    lanes[name] = {"before": values[step - 1], "now": values[step], "mean": mean, "from": first if mean > 0 else second, "to": second if mean > 0 else first}
raw = busiest * 6.02214076e23 * 1e-15 / 10
if raw > 1:
    power = 10 ** math.floor(math.log10(raw))
    token = round(next(size for size in (1, 2, 5, 10) if size * power >= raw * (1 - 1e-9)) * power)
else:
    token = 1
glow, most = {}, 0.0
for index, face in enumerate(faces):
    values = [at("observed_face_dissipated_energy_pJ", k, index) for k in range(count)]
    for k in range(1, count):
        most = max(most, (values[k] - values[k - 1]) / (t[k] - t[k - 1]))
    glow[face["id"]] = {"before": values[step - 1], "now": values[step], "mean": (values[step] - values[step - 1]) / (t[step] - t[step - 1])}
# The scale's end: the largest power in the unit it is shown in (the largest in which it is at least a tenth), rounded up.
factor = next((f for f in (1, 1e3, 1e6) if most * f >= 0.1), 1e6)
shown = most * factor
power = 10 ** math.floor(math.log10(shown))
full = next(size for size in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10) if size * power >= shown * (1 - 1e-6)) * power / factor
amounts = {cells[0]: at("observed_amount", step, row, 0), **{node: at("observed_extracellular_amount", step, row, index) for index, node in enumerate(nodes)}}
json.dump({"run": run_id, "time": t[step], "interval": [t[step - 1], t[step]], "lanes": lanes, "busiest": busiest, "token": token, "glow": glow, "full": full, "largest_power": most, "amounts": amounts}, sys.stdout, indent=1)
