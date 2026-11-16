// A made-up run in the replay format (schema/RUN_VIEW.md), for developing and testing
// the replay view without any experiment's data. Everything it writes says it is
// synthetic. The shape copies what a real E07-v1 run holds: a hexagonal sheet of 127
// cells, a disc of 37, a record every 10 s plus one at each replacement.

const SQRT3 = Math.sqrt(3);
const MADE_UP = "none: synthetic example data";

/** Axial coordinates of a hexagon of cells, `rings` cells out from the centre. */
function hexagon(rings) {
  const cells = [];
  for (let q = -rings; q <= rings; q++) {
    for (let r = Math.max(-rings, -q - rings); r <= Math.min(rings, -q + rings); r++) cells.push([q, r]);
  }
  return cells;
}

const distance = ([q, r]) => (Math.abs(q) + Math.abs(r) + Math.abs(q + r)) / 2;

// A small repeatable random source, so the same run comes out every time.
function random(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let x = state;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Build a run. Returns { file, entry }: the run file as an object and its catalogue entry.
 * Options: rings (6 gives 127 cells), disc (3 gives 37), end, interval, erode (the share of
 * replaced disc cells that fall to the resting voltage), invalidFrom (a time after which
 * records are flagged invalid, to exercise that path), gate (false: the run saved no
 * junction gate), surroundings (false: its files do not say that the cells' surroundings
 * share one potential) and membrane (true: the run says which membrane lies on which cell,
 * saved each ion's concentration in each cell, and states the constants of its definition,
 * as a judged run's view does; "unsigned": the same, with no word on which way the voltage
 * is positive; "unstated": the same, with no constants and the reason). `parts` holds the
 * files of the records that come in a file of their own, by part id
 * (schema/QUANTITY_LAYERS.md, rule 10).
 */
export function syntheticRun({ rings = 6, disc = 3, end = 2340, interval = 27.5675675, erode = 0.3, seed = 1, arm = "synthetic-example", invalidFrom = null, pitch = 11, gate = true, surroundings = true, membrane = false } = {}) {
  const rand = random(seed);
  const axial = hexagon(rings);
  const key = ([q, r]) => `${q},${r}`;
  const where = new Map(axial.map((cell, index) => [key(cell), index]));

  // Polygons with shared corners: each corner is the centre of three cells.
  const corners = new Map(), vertices = [], faces = [];
  const size = pitch / SQRT3; // centre to corner
  const centre = ([q, r]) => [pitch * (q + r / 2), pitch * (SQRT3 / 2) * r];
  for (const cell of axial) {
    const [x, y] = centre(cell);
    const face = [];
    for (let k = 0; k < 6; k++) {
      const angle = (Math.PI / 180) * (60 * k - 30);
      const vx = x + size * Math.cos(angle), vy = y + size * Math.sin(angle);
      const name = `${Math.round(vx * 1000)},${Math.round(vy * 1000)}`;
      if (!corners.has(name)) {
        corners.set(name, vertices.length);
        vertices.push([Number(vx.toFixed(4)), Number(vy.toFixed(4))]);
      }
      face.push(corners.get(name));
    }
    faces.push(face);
  }
  const ends = [];
  axial.forEach(([q, r], index) => {
    for (const [dq, dr] of [[1, 0], [0, 1], [-1, 1]]) {
      const other = where.get(key([q + dq, r + dr]));
      if (other !== undefined) ends.push([index, other]);
    }
  });
  const cells = axial.length, links = ends.length;
  const inDisc = axial.map((cell) => distance(cell) <= disc);
  const discCells = axial.map((_, index) => index).filter((index) => inDisc[index]);

  // The disc's cells are replaced in a shuffled order, again and again, by a copy of a disc neighbour.
  const order = [...discCells];
  for (let index = order.length - 1; index > 0; index--) {
    const swap = Math.floor(rand() * (index + 1));
    [order[index], order[swap]] = [order[swap], order[index]];
  }
  const neighbours = axial.map(() => []);
  for (const [a, b] of ends) {
    neighbours[a].push(b);
    neighbours[b].push(a);
  }
  const events = [];
  for (let n = 0, time = interval / 2; time < end; n++, time += interval) {
    const slot = order[n % order.length];
    const donors = neighbours[slot].filter((index) => inDisc[index]);
    events.push({ time: Number(time.toFixed(3)), slot, donor: donors[Math.floor(rand() * donors.length)], label: `n${n}`, falls: rand() < erode });
  }

  const times = [];
  for (let time = 0; time <= end + 1e-9; time += 10) times.push({ time, regular: 1 });
  for (const event of events) times.push({ time: event.time, regular: 0 });
  times.sort((a, b) => a.time - b.time);
  const steps = times.length;

  const D = -0.022, H = -0.075;
  const vm = new Float32Array(steps * cells), generation = new Uint8Array(steps * cells), abundance = new Uint8Array(steps * links), gates = new Uint8Array(steps * links);
  // Each ion's concentration in each cell follows the cell's voltage between two made-up compositions (mM).
  const IONS = [{ id: "Na", valence: 1, H: 5.9, D: 10.4, bath: 145 }, { id: "K", valence: 1, H: 136.2, D: 137.9, bath: 5 }, { id: "M", valence: -1, H: 7.1, D: 13.0, bath: 140 }, { id: "P", valence: -1, bath: 10 }];
  const saved = IONS.filter((ion) => ion.H !== undefined);
  const conc = saved.map(() => new Float32Array(steps * cells));
  const state = inDisc.map((yes) => (yes ? D : H)); // the voltage each cell is heading for
  const level = [...state], born = axial.map(() => -1e9), count = axial.map(() => 0);
  let next = 0;
  times.forEach(({ time }, step) => {
    while (next < events.length && events[next].time <= time) {
      const event = events[next++];
      count[event.slot] += 1;
      born[event.slot] = event.time;
      state[event.slot] = event.falls ? H : state[event.donor];
      level[event.slot] = state[event.donor]; // a copy arrives at its donor's voltage, then may drift
    }
    for (let index = 0; index < cells; index++) {
      level[index] += (state[index] - level[index]) * 0.18;
      vm[step * cells + index] = level[index] + (rand() - 0.5) * 0.0012;
      generation[step * cells + index] = count[index];
      const share = (level[index] - H) / (D - H);
      saved.forEach((ion, row) => (conc[row][step * cells + index] = ion.H + (ion.D - ion.H) * share));
    }
    ends.forEach(([a, b], link) => {
      const age = time - Math.max(born[a], born[b]);
      const formed = age > 1e8 ? 1 : age < 120 ? 0.05 : 0.05 + 0.95 * (1 - Math.exp(-(age - 120) / 900));
      abundance[step * links + link] = Math.round(formed * 255);
      // A junction between two cells far apart in voltage has its gate mostly shut.
      gates[step * links + link] = Math.round((Math.abs(level[a] - level[b]) > 0.015 ? 0.12 : 0.96) * 255);
    });
  });

  // The payload: every array at an offset that is a multiple of 4.
  const arrays = [
    { id: "t", label: "Time", unit: "s", axes: ["time"], dtype: "float32", data: Float32Array.from(times, (item) => item.time), shape: [steps] },
    { id: "vm", label: "Membrane voltage (synthetic)", unit: "V", set: "cell", layer: "membrane", axes: ["time", "cell"], dtype: "float32", data: vm, shape: [steps, cells], kind: "level", owner: MADE_UP },
    { id: "generation", label: "Generation (synthetic)", unit: "1", set: "cell", layer: "replacement", axes: ["time", "cell"], dtype: "uint8", data: generation, shape: [steps, cells], kind: "level", owner: MADE_UP },
    { id: "junction_abundance", label: "Junction abundance (synthetic)", unit: "1", set: "junction", layer: "replacement", axes: ["time", "junction"], dtype: "uint8", data: abundance, shape: [steps, links], scale: 1 / 255, quantised: true },
    { id: "regular", label: "On the regular record grid", unit: "1", axes: ["time"], dtype: "uint8", data: Uint8Array.from(times, (item) => item.regular), shape: [steps] },
    { id: "valid", label: "Valid record", unit: "1", axes: ["time"], dtype: "uint8", data: Uint8Array.from(times, (item) => (invalidFrom !== null && item.time >= invalidFrom ? 0 : 1)), shape: [steps] },
  ];
  // Lay arrays end to end, each at a multiple of four bytes: { records, payload }.
  const pack = (list) => {
    let offset = 0;
    const placed = list.map(({ data, ...record }) => {
      const bytes = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
      let low = Infinity, high = -Infinity;
      for (const stored of data) {
        const actual = stored * (record.scale ?? 1);
        if (Number.isFinite(actual)) {
          low = Math.min(low, actual);
          high = Math.max(high, actual);
        }
      }
      const entry = { ...record, offset, range: [low, high], bytes };
      offset += Math.ceil(bytes.length / 4) * 4;
      return entry;
    });
    const bytes = new Uint8Array(offset);
    for (const record of placed) bytes.set(record.bytes, record.offset);
    for (const record of placed) delete record.bytes;
    return { records: placed, payload: bytes };
  };
  const { records, payload } = pack(arrays);
  // Each junction's gate comes in a file of its own, as a real run's does.
  const gatePart = gate
    ? pack([{ id: "junction_gate", label: "Junction gate (synthetic)", unit: "1", set: "junction", layer: "junctions", axes: ["time", "junction"], dtype: "uint8", data: gates, shape: [steps, links], scale: 1 / 255, quantised: true, kind: "level", owner: MADE_UP, part: "junction-gate" }])
    : null;
  if (gatePart) records.push(...gatePart.records);
  records.find((record) => record.id === "vm").marks = [{ value: -0.0394, label: "D above, H below (synthetic)" }];
  // What the layers on a membrane need: the voltage declared over the membranes with its sign, and each ion's concentration in a file of its own.
  const ionParts = [];
  if (membrane) {
    const voltage = records.find((record) => record.id === "vm");
    if (membrane !== "unsigned") voltage.sign = { says: "a positive voltage means the cell's inside is positive against its outside", high: "inside", by: "made up with the rest of this synthetic example" };
    records.splice(records.indexOf(voltage) + 1, 0, { ...voltage, id: "membrane_voltage_V", set: "membrane", axes: ["time", "membrane"], same_as: "vm", marks: undefined });
    saved.forEach((ion, row) => {
      const part = `concentration-${ion.id.toLowerCase()}`;
      const packed = pack([{ id: `concentration_mM.${ion.id}`, label: `${ion.id} in the cell (synthetic)`, unit: "mM", set: "cell", layer: "ions", axes: ["time", "cell"], dtype: "float32", data: conc[row], shape: [steps, cells], kind: "level", owner: MADE_UP, field: "concentration_mM", species: ion.id, part }]);
      records.push(...packed.records);
      ionParts.push({ id: part, label: `The concentration of ${ion.id} in each cell (synthetic)`, payload: packed.payload });
    });
  }

  const id = `e07-v1--${arm}--seed${seed}`;
  const judged = Math.min(end, 2020);
  const view = {
    format: "cells.run_view@1",
    derived: true,
    derivation: [
      "Synthetic example: every value in this file is made up by visualizer/tests/helpers/synthetic_replay.mjs. It is no experiment's result.",
      "Cell positions: a regular hexagonal sheet drawn by the generator.",
    ],
    run: {
      id,
      experiment: "e07-v1",
      arm,
      seed,
      label: "synthetic example",
      group: "control",
      engine_models: ["none: synthetic example data"],
      revision: null,
      end_s: end,
      stop: "planned end",
      class: "erosion",
      judged_s: judged,
      parameters: [
        { id: "size", value: discCells.length },
        { id: "s", value: 1.0 },
        { id: "kind", value: "donor" },
        { id: "scope", value: "disc" },
        { id: "rule", value: "disc_neighbour" },
        { id: "formation.lag_s", value: 120 },
        { id: "formation.time_constant_s", value: 900 },
        { id: "residence_s", value: 1020 },
        { id: "interval_s", value: interval },
        { id: "judged_at", value: "second turnover" },
        { id: "dt", value: 0.005 },
      ],
      readouts: [
        { id: "judged_s", value: judged, supplementary: false },
        { id: "J_engine", value: 0.78, supplementary: false },
        { id: "J_null", value: 1.0, supplementary: false },
        { id: "delta_J", value: -0.22, supplementary: false },
        { id: "delta", value: 2 / discCells.length, supplementary: false },
        { id: "D_loss_fraction", value: 0.09, supplementary: false },
        { id: "founders_lost", value: 14, supplementary: false },
        { id: "delta_J_over_records.mean", value: -0.14, supplementary: true, status: "supplementary: not judged (synthetic example)" },
      ],
    },
    time: { unit: "s", record: "t" },
    space: { unit: "um", dimensions: 2 },
    layers: [
      { id: "membrane", label: "Membrane voltage and ions", representation: "simulated" },
      { id: "replacement", label: "Cell replacement", representation: "prescribed" },
      ...(gate ? [{ id: "junctions", label: "Junction gating", representation: "modelled" }] : []),
    ],
    sets: [
      { id: "cell", scale: "cell", ids: axial.map((_, index) => `cell_${index}`), geometry: { kind: "polygons", vertices, faces } },
      { id: "junction", scale: "cell", ids: ends.map((_, index) => `junction_${index}`), geometry: { kind: "links", between: "cell", ends } },
    ],
    regions: [{ id: "disc", label: "The disc", set: "cell", indices: discCells }],
    records,
    events: events.map((event) => ({
      time: event.time,
      kind: "replacement",
      layer: "replacement",
      at: { set: "cell", index: event.slot },
      from: { set: "cell", index: event.donor },
      label: event.label,
    })),
  };
  const base64 = (bytes) => Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength).toString("base64");
  const parts = {};
  const entry = { id, experiment: "e07-v1", arm, seed, label: "synthetic example", group: "control", class: "erosion", stop: "planned end", records: steps, end_s: end, file: `runs/${id}.json`, bytes: 0 };
  if (gatePart) {
    view.parts = [{ id: "junction-gate", label: "Each junction's gate (synthetic)", file: `runs/${id}.junction-gate.json`, byte_length: gatePart.payload.byteLength }];
    parts["junction-gate"] = { format: "cells.visualizer.replay_part@1", run: id, part: "junction-gate", payload: { encoding: "base64", byte_length: gatePart.payload.byteLength, data: base64(gatePart.payload) } };
    entry.parts = [{ id: "junction-gate", file: view.parts[0].file, bytes: 0 }];
  }
  if (membrane) {
    const each = (value) => Array.from({ length: cells }, () => value);
    view.layers.push({ id: "ions", label: "Ion concentrations", representation: "simulated" });
    view.sets.push(
      { id: "species", ids: IONS.map((ion) => ion.id) },
      { id: "outside", holds: "outside node", scale: "cell", ids: axial.map((_, index) => `bath_${index}`) },
      { id: "membrane", scale: "cell", ids: axial.map((_, index) => `membrane_${index}`), geometry: { kind: "on", set: "cell", index: axial.map((_, index) => index) }, outside: { set: "outside", index: axial.map((_, index) => index) } }
    );
    const says = "Synthetic example: made up, and taken to be held constant.";
    const constants = [
      { id: "temperature", label: "Temperature", unit: "K", axes: [], values: 310, from: "definition.json", says },
      { id: "valence", label: "Valence", unit: "1", axes: ["species"], values: IONS.map((ion) => ion.valence), from: "definition.json", says },
      { id: "volume", label: "Cell volume", unit: "pL", set: "cell", axes: ["cell"], values: each(0.75), from: "definition.json", says },
      { id: "membrane_capacitance", label: "Membrane capacitance", unit: "F", set: "membrane", axes: ["membrane"], values: each(1.6e-11), from: "definition.json", says },
      { id: "membrane_area", label: "Membrane area", unit: "m2", set: "membrane", axes: ["membrane"], values: each(3.2e-10), from: "definition.json", says },
      { id: "extracellular_concentration_mM", label: "Concentration outside", unit: "mM", set: "outside", axes: ["species", "outside"], values: IONS.map((ion) => each(ion.bath)), from: "definition.json", says },
    ];
    if (membrane === "unstated") view.unstated = constants.map((constant) => ({ id: constant.id, why: "Not stated as a constant: the run's model (synthetic) is not one whose operators the viewer knows." }));
    else view.constants = constants;
    view.parts = [...(view.parts || []), ...ionParts.map((part) => ({ id: part.id, label: part.label, file: `runs/${id}.${part.id}.json`, byte_length: part.payload.byteLength }))];
    entry.parts = [...(entry.parts || []), ...ionParts.map((part) => ({ id: part.id, file: `runs/${id}.${part.id}.json`, bytes: 0 }))];
    for (const part of ionParts) parts[part.id] = { format: "cells.visualizer.replay_part@1", run: id, part: part.id, payload: { encoding: "base64", byte_length: part.payload.byteLength, data: base64(part.payload) } };
  }
  if (surroundings) view.surroundings = { shared: true, potential_V: 0, says: "Synthetic example: every cell's surroundings are taken to be a held bath at 0 V." };
  const file = { format: "cells.visualizer.replay@1", view, payload: { encoding: "base64", byte_length: payload.byteLength, data: base64(payload) } };
  return { file, entry, parts };
}

/** The catalogue for a list of synthetic runs, with the experiment's entry marked as an example. */
export function syntheticIndex(experiment, entries) {
  return {
    format: "cells.visualizer.replay_index@1",
    experiments: [{ id: "e07-v1", ...experiment, label: `${experiment.label} (synthetic example data)` }],
    runs: entries,
  };
}
