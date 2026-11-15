// A made-up run in the replay format (schema/RUN_VIEW.md), for developing and testing
// the replay view without any experiment's data. Everything it writes says it is
// synthetic. The shape copies what a real E07-v1 run holds: a hexagonal sheet of 127
// cells, a disc of 37, a record every 10 s plus one at each replacement.

const SQRT3 = Math.sqrt(3);

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
 * records are flagged invalid, to exercise that path).
 */
export function syntheticRun({ rings = 6, disc = 3, end = 2340, interval = 27.5675675, erode = 0.3, seed = 1, arm = "synthetic-example", invalidFrom = null, pitch = 11 } = {}) {
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
  const vm = new Float32Array(steps * cells), generation = new Uint8Array(steps * cells), abundance = new Uint8Array(steps * links);
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
    }
    ends.forEach(([a, b], link) => {
      const age = time - Math.max(born[a], born[b]);
      const formed = age > 1e8 ? 1 : age < 120 ? 0.05 : 0.05 + 0.95 * (1 - Math.exp(-(age - 120) / 900));
      abundance[step * links + link] = Math.round(formed * 255);
    });
  });

  // The payload: every array at an offset that is a multiple of 4.
  const arrays = [
    { id: "t", label: "Time", unit: "s", axes: ["time"], dtype: "float32", data: Float32Array.from(times, (item) => item.time), shape: [steps] },
    { id: "vm", label: "Membrane voltage (synthetic)", unit: "V", set: "cell", layer: "membrane", axes: ["time", "cell"], dtype: "float32", data: vm, shape: [steps, cells] },
    { id: "generation", label: "Generation (synthetic)", unit: "1", set: "cell", layer: "replacement", axes: ["time", "cell"], dtype: "uint8", data: generation, shape: [steps, cells] },
    { id: "junction_abundance", label: "Junction abundance (synthetic)", unit: "1", set: "junction", layer: "replacement", axes: ["time", "junction"], dtype: "uint8", data: abundance, shape: [steps, links], scale: 1 / 255, quantised: true },
    { id: "regular", label: "On the regular record grid", unit: "1", axes: ["time"], dtype: "uint8", data: Uint8Array.from(times, (item) => item.regular), shape: [steps] },
    { id: "valid", label: "Valid record", unit: "1", axes: ["time"], dtype: "uint8", data: Uint8Array.from(times, (item) => (invalidFrom !== null && item.time >= invalidFrom ? 0 : 1)), shape: [steps] },
  ];
  let offset = 0;
  const records = arrays.map(({ data, ...record }) => {
    const bytes = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    let low = Infinity, high = -Infinity;
    for (const stored of data) {
      const actual = stored * (record.scale ?? 1);
      if (Number.isFinite(actual)) {
        low = Math.min(low, actual);
        high = Math.max(high, actual);
      }
    }
    const placed = { ...record, offset, range: [low, high], bytes };
    offset += Math.ceil(bytes.length / 4) * 4;
    return placed;
  });
  const payload = new Uint8Array(offset);
  for (const record of records) payload.set(record.bytes, record.offset);
  for (const record of records) delete record.bytes;
  records.find((record) => record.id === "vm").marks = [{ value: -0.0394, label: "D above, H below (synthetic)" }];

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
  const data = Buffer.from(payload.buffer, payload.byteOffset, payload.byteLength).toString("base64");
  const file = { format: "cells.visualizer.replay@1", view, payload: { encoding: "base64", byte_length: payload.byteLength, data } };
  const entry = { id, experiment: "e07-v1", arm, seed, label: "synthetic example", group: "control", class: "erosion", stop: "planned end", records: steps, end_s: end, file: `runs/${id}.json`, bytes: 0 };
  return { file, entry };
}

/** The catalogue for a list of synthetic runs, with the experiment's entry marked as an example. */
export function syntheticIndex(experiment, entries) {
  return {
    format: "cells.visualizer.replay_index@1",
    experiments: [{ id: "e07-v1", ...experiment, label: `${experiment.label} (synthetic example data)` }],
    runs: entries,
  };
}
