// beads: tokens that cross a piece of one membrane through its channel populations and
// its pump, as many a second as the run's saved totals grew between two records. A bead is
// a token of a rate, not an ion: the legend says how many ions one stands for and what time
// the picture keeps (schema/QUANTITY_LAYERS.md, rule 3).
//
//   beads a second on the screen = ions a second / (ions in one bead x how much it is slowed)
//
// The rate sets how many beads pass, never how fast one travels: every bead crosses the
// membrane in the same time, which stands for nothing. The rate is a mean over the interval
// that ends at the record shown (the `rate` rule), so at a run's first record there is none.
//
// It draws on the close-up of a chosen cell's membrane, like the arrows and the marks of
// the charge: a form stands through the piece for each channel population of the membrane
// and one for its pump, and the beads cross in them, in the order the close-up keeps for
// them (`forms`, `beads`). Through a channel population a bead goes out of the cell when the
// population's saved total grew, into it when it fell (the engine's own convention, as the
// record's sign declares it). Through the pump each ion has a lane of its own: the pump's
// cycles between two records times what one cycle moves of that ion, as the pump's
// declaration gives it; a positive number is carried into the cell.
//
// The arithmetic and the stepping of a lane are here for every mark that draws beads
// (./stream.js draws them across the borders of the sheet).

import * as THREE from "../../three.js";
import { rate } from "../derive.js";
import { declared, family, fromFirst, restartsBetween, signedBy } from "../records.js";

export const PER_FMOL = 6.02214076e23 * 1e-15; // ions in a femtomole
export const BUSIEST = 10; // beads a second on the screen for a run's busiest stream
export const SLOWS = [1, 1e3, 1e6]; // the slow-downs offered: true speed, a thousand times, a million times
export const CROSSING = 1.6; // seconds a bead takes to cross: the same for every bead
export const MOST = 18; // beads on one lane at a time
const SIZE = { quiet: 1, bold: 1.35 };

/**
 * How many ions one bead stands for at a slow-down: 1, 2 or 5 times a power of ten, the
 * smallest with which the run's busiest stream passes at most ten beads a second. Never
 * under one ion: slowed enough, a bead is an ion.
 */
export function tokenFor(busiest, slow = 1) {
  const raw = Math.abs(busiest) / (BUSIEST * slow);
  if (!(raw > 1)) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const size = [1, 2, 5, 10].find((step) => step * power >= raw * (1 - 1e-9)) ?? 10;
  return Math.round(size * power);
}

/** How many beads pass in a second on the screen, for a rate in ions a second: its size alone. */
export function beadsASecond(ions, token, slow = 1) {
  return Math.abs(ions) / (token * slow);
}

/** A rate in femtomoles a second as ions a second. */
export const ionsASecond = (fmol) => fmol * PER_FMOL;

/** What time the picture keeps, in the legend's words: true speed, or how much it is slowed and what a second here is in the cell. */
export function timeWords(slow = 1) {
  if (!(slow > 1)) return "True speed: one second here is one second in the cell";
  const seconds = 1 / slow;
  const [value, unit] = seconds >= 1e-3 ? [seconds * 1e3, "millisecond"] : seconds >= 1e-6 ? [seconds * 1e6, "microsecond"] : [seconds * 1e9, "nanosecond"];
  const shown = Number(value.toPrecision(3));
  return `Slowed ${slow.toLocaleString("en-US")} times: one second here is ${shown === 1 ? `one ${unit}` : `${shown.toLocaleString("en-US")} ${unit}s`} in the cell`;
}

/** What one bead stands for, in the legend's words. `what` names the particle: an ion, or a molecule of a species that is none. */
export function tokenWords(token, what = "ion") {
  return token === 1 ? `One bead is one ${what}` : `One bead is ${token.toLocaleString("en-US")} ${what.replace(/( or |$)/g, "s$1")}`;
}

/** What a legend adds to the time a motion layer keeps where nothing may move. */
export const STILL_WORDS = "Shown still here: the beads stand, as many as would be on their way at one moment";

/**
 * The picture's own short statement of a motion layer (rule 3): the token, the time, and the
 * interval the rate is a mean over. Where nothing may move (`still`), it says that too.
 */
export function statementOf({ token, what = "ion", slow = 1, interval, clock, still = false }) {
  const time = `${slow > 1 ? `slowed ${slow.toLocaleString("en-US")} times` : "true speed"}${still ? ", shown still" : ""}`;
  const over = interval ? `mean of ${clock(interval[0])} to ${clock(interval[1])}` : "no rate at the run's first record";
  return `${tokenWords(token, what)} · ${time} · ${over}`;
}

/**
 * The mean rate of one entity's total over the interval that ends at record `step`, in the
 * record's unit a second; null at the first record, where either record is not valid, or
 * where the total restarted on that entity within the interval (a record that says `resets`:
 * no rate is taken across a reset).
 */
export function meanRate(run, record, entity, step) {
  if (!(step >= 1) || !run.isValid(step) || !run.isValid(step - 1)) return null;
  if (restartsBetween(run, record, entity, run.t[step - 1], run.t[step])) return null;
  return rate(record.at(step, entity), record.at(step - 1, entity), run.t[step] - run.t[step - 1]);
}

/** Whether no rate is given for an entity at a record because its total restarted in the interval before it. */
export function restarted(run, record, entity, step) {
  return step >= 1 && restartsBetween(run, record, entity, run.t[step - 1], run.t[step]);
}

/**
 * Where the beads of one lane stand when nothing moves (a still picture, or a visitor who
 * asks for less motion): evenly, as many as would be crossing at any one moment. A stream
 * too thin for one bead to be on its way most of the time shows none: its arrowhead alone
 * says that something crosses, and which way.
 */
export function standing(perSecond) {
  if (!(perSecond > 0)) return [];
  const count = Math.min(MOST, Math.round(perSecond * CROSSING));
  return Array.from({ length: count }, (_, k) => (k + 0.5) / count);
}

/** The words for the arrowhead that ends a lane, for a legend. */
export const HEAD_WORDS = "An arrowhead ends each lane that carries something, and points the way its beads go. A small arrowhead alone: a lane that passes a bead only now and then";

/** How large a lane's arrowhead is drawn, as a share of its full size: full where a bead or more is on its way at one moment, smaller for a thinner stream. */
export function headSize(perSecond) {
  return Math.min(1, Math.max(0.4, Math.sqrt(Math.max(0, perSecond) * CROSSING)));
}

/**
 * Advance one lane by a stretch of watching time: beads set out as many a second as the
 * lane's rate says, each crosses in the same time, and one that has arrived is gone. A lane
 * is { perSecond, due, beads }, `beads` being each bead's share of the way across, the one
 * that set out first standing first. Returns whether anything is on its way or will be.
 *
 * The stretch may be of any length. A bead that set out within it stands where it has got
 * to since the moment it set out, so as many beads pass a second at two frames a second as
 * at sixty, and after a long gap the lane is as full as it would be had it been watched all
 * along. (A stretch longer than a crossing and a half is no different from one of that
 * length: every bead of before has arrived.)
 */
export function advance(lane, seconds) {
  const stretch = Math.min(Math.max(0, seconds), CROSSING * 1.5);
  if (lane.beads.length) lane.beads = lane.beads.map((share) => share + stretch / CROSSING).filter((share) => share < 1);
  if (lane.perSecond > 0) {
    // The clock of setting out runs on from where it stood: a bead sets out each time it passes a whole number.
    const before = lane.due, after = before + lane.perSecond * stretch;
    for (let number_ = Math.floor(before) + 1; number_ <= after; number_++) {
      const since = (after - number_) / lane.perSecond; // seconds since this bead set out
      if (since < CROSSING && lane.beads.length < MOST) lane.beads.push(since / CROSSING);
    }
    lane.due = after - Math.floor(after);
  }
  return lane.perSecond > 0 || lane.beads.length > 0;
}

/**
 * The streams through one membrane: one for each of its channel populations that the run
 * saved a total for, one for each ion its pump moves, and one for each species that crossed
 * the membrane itself. `sources` are the channel populations' totals as declared; `cycles`
 * the pump's saved cycles as declared, or null; `leaks` the totals carried by the membrane's
 * own passive routes, one for each species, as declared. A stream is { kind, name, record,
 * entity, species, per, out }: `per` is what the record's rate is multiplied by (1 for a
 * channel population and for the membrane itself; for a pump, what one cycle moves of the
 * ion) and `out` whether a positive product leaves the cell.
 */
export function streamsOf(run, sources, cycles, membrane, leaks = []) {
  const streams = [];
  for (const source of sources) {
    const set = run.sets.get(source.set), record = run.records.get(source.id);
    if (!record || set?.geometry?.kind !== "on") continue;
    const out = fromFirst(source.sign); // a positive amount leaves the cell where the sign's source is the cell, the inside
    if (out === null) continue;
    set.geometry.index.forEach((on, entity) => {
      if (on !== membrane) return;
      // A total saved for each species names its species; a population's one total is for the one ion it lets through, where it lets one through.
      const through = Array.isArray(set.species?.[entity]) ? set.species[entity] : [];
      streams.push({ kind: "channel", name: set.ids[entity], record, source, entity, species: source.species ?? (through.length === 1 ? through[0] : null), per: 1, out });
    });
  }
  // What one cycle of the membrane's pump moves of each species, as the run's view gives it: a positive count is carried into the cell.
  const moves = run.sets.get("membrane")?.pumps?.[membrane]?.per_cycle;
  const record = cycles ? run.records.get(cycles.id) : null;
  const outwards = fromFirst(cycles?.sign); // false where positive cycles carry their ions into the cell
  if (record && Array.isArray(moves) && outwards !== null) {
    for (const move of moves) {
      if (!move?.count) continue;
      streams.push({ kind: "pump", name: `pump of ${run.sets.get("membrane").ids[membrane]}`, record, source: cycles, entity: membrane, species: move.species, per: move.count, out: outwards });
    }
  }
  // The membrane itself: what its own passive routes carried of each species, where anything ever crossed this one.
  for (const leak of leaks) {
    const series = run.records.get(leak.id), out = fromFirst(leak.sign);
    if (!series || leak.set !== "membrane" || out === null) continue;
    const first = series.at(0, membrane);
    let moves_ = false;
    for (let step = 1; step < run.count && !moves_; step++) moves_ = series.at(step, membrane) !== first;
    if (moves_) streams.push({ kind: "membrane", name: run.sets.get("membrane").ids[membrane], record: series, source: leak, entity: membrane, species: leak.species, per: 1, out });
  }
  return streams;
}

/** The busiest stream through any membrane of the run over any interval, in fmol a second: what the token is sized by. */
export function busiestThrough(run, sources, cycles, leaks = []) {
  const membranes = run.sets.get("membrane")?.ids.length || 0;
  let most = 0;
  for (let membrane = 0; membrane < membranes; membrane++) {
    for (const stream of streamsOf(run, sources, cycles, membrane, leaks)) {
      for (let step = 1; step < run.count; step++) {
        const mean = meanRate(run, stream.record, stream.entity, step);
        if (mean !== null) most = Math.max(most, Math.abs(mean * stream.per));
      }
    }
  }
  return most;
}

export const beads = {
  name: "beads",
  channels: ["motion"],
  lives_on: ["channel population", "pump population", "membrane"],
  surface: "membrane",
  needs_sign: true,

  /** The legend's lines for a layer of beads: what one bead stands for, and what time the picture keeps. */
  keys(busiest, slow = 1, still = false) {
    return [
      { key: "bead", text: `${tokenWords(tokenFor(busiest, slow))}. More beads a second means more ions a second; how fast a bead travels stands for nothing` },
      { key: "time", text: still ? `${timeWords(slow)}. ${STILL_WORDS}` : timeWords(slow) },
    ];
  },

  /**
   * context (see ./index.js): the close-up's surface, the run, the membrane's number,
   * `fed.sources` (the channel populations' totals as declared) and `fed.extras` (by role
   * "pump": the pump's saved cycles), the colours, `memo` (what is worked out once for the
   * run), `slow()` (how much the picture is slowed: 1 is true speed) and `still()` (whether
   * nothing may move).
   */
  create({ surface, run, fed, membrane, colours, strength = "quiet", memo = (key, make) => make(), slow = () => 1, still = () => false }) {
    const { piece, order } = surface;
    const pump = fed.extras.find((entry) => entry.role === "pump");
    const cycles = pump ? declared(run, pump.record) : null;
    // What crossed the membrane itself, beside its channel populations and its pump: one saved total for each species.
    const leak = fed.extras.find((entry) => entry.role === "leak");
    const leaks = !leak ? [] : leak.field ? family(run, leak.field) : [declared(run, leak.record)].filter(Boolean);
    const sources = fed.sources || [];
    const streams = streamsOf(run, sources, cycles, membrane, leaks);
    // One token for the whole run, whichever cell is chosen: sized by the busiest stream through any membrane.
    const busiest = memo("beads-busiest", () => busiestThrough(run, sources, cycles, leaks));
    // The forms: one for each channel population, one for the pump, and the bare membrane where something crossed it;
    // the streams of one form stand side by side in it.
    const forms = [];
    for (const stream of streams) {
      const key = stream.kind === "channel" ? stream.name : stream.kind;
      let form = forms.find((item) => item.key === key);
      if (!form) forms.push((form = { key, kind: stream.kind, name: stream.kind === "pump" ? "pump" : stream.kind === "membrane" ? "membrane itself" : stream.name, streams: [] }));
      form.streams.push(stream);
    }
    const usable = piece.width * 0.8, face = piece.thick / 2, reach = piece.reach * 0.5;
    forms.forEach((form, k) => {
      form.x = forms.length ? ((k + 0.5) / forms.length - 0.5) * usable : 0;
      form.wide = form.kind === "channel" ? 0.16 : 0.34;
      form.streams.forEach((stream, n) => (stream.x = form.x + (form.streams.length > 1 ? (n / (form.streams.length - 1) - 0.5) * (form.wide - 0.14) : 0)));
    });
    for (const stream of streams) Object.assign(stream, { beads: [], due: 0, perSecond: 0, mean: null, up: true });

    // The forms: two walls through the membrane for a channel population, a block for the pump, in the page's ink under the glass.
    const z = 0; // the middle of the piece's depth, behind the plane where the arrows stand
    const group = new THREE.Group();
    group.renderOrder = order.group;
    group.userData.unpickable = true;
    const formMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.5, depthTest: false, depthWrite: false, side: THREE.DoubleSide, toneMapped: false });
    const positions = [], index = [];
    const slab = (x0, x1, y0, y1) => {
      const at = positions.length / 3;
      positions.push(x0, y0, z, x1, y0, z, x1, y1, z, x0, y1, z);
      index.push(at, at + 1, at + 2, at, at + 2, at + 3);
    };
    const tall = face + 0.09;
    for (const form of forms) {
      const half = form.wide / 2, wall = 0.035;
      if (form.kind === "membrane") continue; // the bare membrane has no form: its beads cross the glass itself
      if (form.kind === "pump") {
        // A block with a waist: two walls and a bar across each face.
        slab(form.x - half, form.x - half + wall, -tall, tall);
        slab(form.x + half - wall, form.x + half, -tall, tall);
        slab(form.x - half, form.x + half, tall - wall, tall);
        slab(form.x - half, form.x + half, -tall, -tall + wall);
      } else {
        slab(form.x - half, form.x - half + wall, -tall, tall);
        slab(form.x + half - wall, form.x + half, -tall, tall);
      }
    }
    const formGeometry = new THREE.BufferGeometry();
    formGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positions.length ? positions : [0, 0, 0], 3));
    formGeometry.setIndex(index);
    const formMesh = new THREE.Mesh(formGeometry, formMaterial);
    formMesh.renderOrder = order.forms;
    formMesh.frustumCulled = false;
    formMesh.userData.unpickable = true;
    group.add(formMesh);

    const capacity = Math.max(1, streams.length * MOST);
    const shape = new THREE.SphereGeometry(1, 12, 8);
    // An arrowhead for each stream, pointing up the piece (out of the cell); turned round for a stream that goes in.
    const headShape = new THREE.BufferGeometry();
    headShape.setAttribute("position", new THREE.Float32BufferAttribute([0, 1, 0, -0.85, -0.7, 0, 0.85, -0.7, 0], 3));
    // Drawn with the close-up's other see-through parts, in the order it keeps for them: after the card and the glass.
    const coreMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
    const rimMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
    const make = (material, at, geometry = shape, count = capacity) => {
      const mesh = new THREE.InstancedMesh(geometry, material, count);
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.setColorAt(0, colours.ink);
      mesh.frustumCulled = false;
      mesh.renderOrder = at;
      mesh.userData.unpickable = true;
      mesh.userData.noContact = true;
      mesh.count = 0;
      group.add(mesh);
      return mesh;
    };
    const rims = make(rimMaterial, order.beads), cores = make(coreMaterial, order.beads + 1);
    const headRims = make(rimMaterial, order.beads, headShape, Math.max(1, streams.length)), heads = make(coreMaterial, order.beads + 1, headShape, Math.max(1, streams.length));
    surface.root.add(group);
    // Each form's name, and for a channel population the ion it lets through, under the piece.
    const names = forms.map((form) => {
      const ions = [...new Set(form.streams.map((stream) => stream.species).filter(Boolean))];
      const label = surface.label({ text: `${form.name}${ions.length ? `\n${ions.join(", ")}` : ""}`, at: [form.x, -(face + reach + 0.25), z], kind: "closeup label-closeup-ion", lift: 2 }); // under the arrowhead of a stream that goes in
      label.below(true);
      return label;
    });

    let size = SIZE[strength], tones = colours;
    formMaterial.color.copy(colours.ink);
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
    const turn = new THREE.Quaternion(), inwards = new THREE.Vector3(0, 0, 1);
    const drawBeads = () => {
      let at = 0;
      const radius = 0.05 * size;
      for (const stream of streams) {
        const colour = stream.species ? tones.ion(stream.species) : tones.ink;
        for (const share of stream.beads) {
          if (at >= capacity) break;
          const t = stream.up ? share : 1 - share; // from the inside up to the outside, or back
          position.set(stream.x, (t * 2 - 1) * (face + reach), z);
          const grown = 0.45 + 0.55 * Math.sin(Math.PI * Math.min(1, Math.max(0, share)));
          cores.setMatrixAt(at, matrix.compose(position, quaternion, scale.setScalar(radius * grown)));
          rims.setMatrixAt(at, matrix.compose(position, quaternion, scale.setScalar(radius * grown * 1.45)));
          cores.setColorAt(at, colour);
          rims.setColorAt(at, tones.raised || tones.ground);
          at += 1;
        }
      }
      cores.count = rims.count = at;
      // The arrowheads: one beyond the far end of each stream that carries something.
      let ends = 0;
      for (const stream of streams) {
        if (!(stream.perSecond > 0)) continue;
        const colour = stream.species ? tones.ion(stream.species) : tones.ink;
        position.set(stream.x, (stream.up ? 1 : -1) * (face + reach + 0.1), z);
        turn.setFromAxisAngle(inwards, stream.up ? 0 : Math.PI);
        const grown = headSize(stream.perSecond);
        heads.setMatrixAt(ends, matrix.compose(position, turn, scale.setScalar(radius * 1.5 * grown)));
        headRims.setMatrixAt(ends, matrix.compose(position, turn, scale.setScalar(radius * 2.1 * grown)));
        heads.setColorAt(ends, colour);
        headRims.setColorAt(ends, tones.raised || tones.ground);
        ends += 1;
      }
      heads.count = headRims.count = ends;
      for (const mesh of [cores, rims, heads, headRims]) {
        mesh.instanceMatrix.needsUpdate = true;
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      }
    };
    const token = () => tokenFor(ionsASecond(busiest), slow());
    let shown = { step: 0, valid: false };
    const settle = () => {
      const one = token(), slowed = slow();
      for (const stream of streams) {
        const mean = shown.valid ? meanRate(run, stream.record, stream.entity, shown.step) : null;
        stream.mean = mean === null ? null : mean * stream.per; // fmol a second of this ion, positive as the record's sign says
        stream.perSecond = stream.mean ? beadsASecond(ionsASecond(stream.mean), one, slowed) : 0;
        if (stream.mean) stream.up = stream.mean > 0 === stream.out;
        if (!stream.perSecond) stream.beads = [];
        else if (still()) stream.beads = standing(stream.perSecond);
      }
      drawBeads();
    };

    return {
      streams,
      forms,
      busiest,
      shines: [cores],
      get token() {
        return token();
      },
      /** How many beads and how many arrowheads are drawn now. */
      get drawn() {
        return { beads: cores.count, heads: heads.count };
      },
      update(step, valid) {
        shown = { step, valid };
        settle();
      },
      /** Advance by a frame of `milliseconds`. Returns whether a bead is on its way, so that frames keep coming. */
      tick(milliseconds) {
        if (still()) return false;
        const seconds = milliseconds / 1000;
        let moving = false;
        for (const stream of streams) moving = advance(stream, seconds) || moving;
        drawBeads();
        return moving;
      },
      setSlow() {
        for (const stream of streams) stream.due = 0;
        settle();
      },
      /** The interval the rates shown are means over: [from, to] in the run's seconds, or null at the first record. */
      interval() {
        return shown.step >= 1 ? [run.t[shown.step - 1], run.t[shown.step]] : null;
      },
      /** The numbers behind each stream at the record shown, for the panel. */
      readings() {
        const { step } = shown;
        const one = token(), slowed = slow();
        return streams.map((stream) => ({
          kind: stream.kind,
          name: stream.name,
          record: stream.record.id,
          species: stream.species,
          per: stream.per,
          unit: stream.record.unit,
          before: step >= 1 ? stream.record.at(step - 1, stream.entity) : null,
          now: stream.record.at(step, stream.entity),
          seconds: step >= 1 ? run.t[step] - run.t[step - 1] : null,
          mean: stream.mean,
          reset: restarted(run, stream.record, stream.entity, step),
          particles: stream.mean === null ? null : Math.abs(ionsASecond(stream.mean)),
          beads: stream.mean === null ? null : beadsASecond(ionsASecond(stream.mean), one, slowed),
          way: stream.mean ? (stream.up ? "out of the cell" : "into the cell") : null,
        }));
      },
      /** The legend's lines: the ions with their colours, what one bead stands for, the time, and by whose word a bead goes the way it does. */
      keys() {
        const species = [...new Set(streams.map((stream) => stream.species).filter(Boolean))];
        const lines = [];
        if (species.length) lines.push({ key: "ions", chips: species.map((id) => ({ label: id, colour: tones.ionCss(id) })), text: "Up is out of the cell, down is into it" });
        lines.push(...beads.keys(ionsASecond(busiest), slow(), still()));
        const by = new Map();
        for (const stream of streams) {
          const sign = stream.source.sign, whose = signedBy(sign).trim();
          const said = by.get(whose) || new Set();
          said.add(sign.says);
          by.set(whose, said);
        }
        for (const [whose, said] of by) lines.push({ key: "way", text: `A bead goes the way its total grew: ${[...said].join("; ")}. ${whose.replace(/\.$/, "")}` });
        lines.push({ key: "head", text: HEAD_WORDS });
        if (streams.some((stream) => stream.kind === "pump")) lines.push({ key: "pump", text: "Through the pump: its cycles between two records, times the ions one cycle moves as the pump's declaration gives them" });
        if (streams.some((stream) => stream.kind === "membrane")) lines.push({ key: "leak", text: "Through the membrane itself, with no form: what its own passive routes carried, beside its channel populations and its pump" });
        return lines;
      },
      setStrength(next) {
        size = SIZE[next];
        drawBeads();
      },
      setColours(next) {
        tones = next;
        formMaterial.color.copy(next.ink);
        drawBeads();
      },
      dispose() {
        surface.root.remove(group);
        shape.dispose();
        headShape.dispose();
        formGeometry.dispose();
        for (const material of [formMaterial, coreMaterial, rimMaterial]) material.dispose();
        for (const mesh of [cores, rims, heads, headRims]) mesh.dispose();
        for (const label of names) label.remove();
      },
    };
  },
};
