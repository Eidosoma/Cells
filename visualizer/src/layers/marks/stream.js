// stream: beads that cross a border of the picture, as many a second as a saved total grew
// between two records. A border is where two tiles meet (../world.js): two cells joined by a
// junction, a cell and the space outside it that its membrane faces, two spaces outside
// joined by a face. Every saved total that lies on such a border gets a lane of its own
// there: what crossed a junction, a face or a membrane for each species, and what an
// exchange route carried.
//
// A bead is a token of a rate, not a particle (schema/QUANTITY_LAYERS.md, rule 3):
//
//   beads a second on the screen = particles a second of the run x the speed / particles in one bead
//
// The speed is the replay's own: what flows keeps its one clock (src/replay/player.js). Paused,
// it stands; played, as much of the run passes for it as for the playhead.
//
// The rate sets how wide a lane's stream is (at true speed and faster) and how many beads pass
// (slowed), never how fast one travels: every bead takes the same time to cross, which stands
// for nothing. The rate is a mean over the interval that ends at
// the record shown (the `rate` rule), so at a run's first record there is none.
//
// A bead goes the way its total grew: from the end the record's declared sign calls the
// source to the other when the mean rate is positive, back when it is negative. A total with
// no declared direction is not drawn.
//
// The lanes are drawn by the one renderer of flux (./tokens.js, ./flow.js), as in the Cell view:
// at true speed and faster each lane is a stream as wide as its rate, with no bead to count;
// slowed, the stream resolves into packets and then single beads; chevrons along each lane
// point its way, and stand with everything else where nothing may move or the replay is paused.
// They are drawn over the sheet, after its other see-through signs (a glow lies under them);
// the lens may mark them to shine (`shines`).

import * as THREE from "../../three.js";
import { tokenFor, beadsASecond, ionsASecond, flowWords, meanRate, restarted, standing, timeKey, paceAt, resolveAt, modeAt, WAY_WORDS } from "./beads.js";
import { Tokens } from "./tokens.js";
import { fromFirst, signedByShort } from "../records.js";

const SIZE = { quiet: 1, bold: 1.35 };

/** Whether an entity's total ever changes in the run: one that never does gets no lane. */
function everMoves(run, record, entity) {
  const first = record.at(0, entity);
  for (let step = 1; step < run.count; step++) if (record.at(step, entity) !== first) return true;
  return false;
}

/**
 * The lanes of a run: one for each entity of each saved total that ever changes.
 * `sources` are the totals as declared (fed.sources); `world` says where each is drawn.
 * Returns { lanes, unplaced, undirected }: a lane is { record, entity, species, name, place,
 * forward }, where `forward` says whether a positive rate goes from the border's side a to
 * its side b; `unplaced` are entities whose two places do not both have a tile; `undirected`
 * the totals whose sign names no end as the source.
 */
export function lanesOf(run, sources, world) {
  const lanes = [], unplaced = [], undirected = [];
  for (const source of sources) {
    const record = run.records.get(source.id);
    const set = run.sets.get(source.set);
    if (!record || !set) continue;
    // The source end is the entity's first end (a link's sender, a membrane's cell: its inside) or the other, as the sign says.
    const first = fromFirst(source.sign);
    if (first === null) {
      undirected.push(source);
      continue;
    }
    for (let entity = 0; entity < set.ids.length; entity++) {
      if (!everMoves(run, record, entity)) continue;
      // A total saved for each species names its species; a route's total is for the species its set gives the route.
      const species = source.species ?? (Array.isArray(set.species) && typeof set.species[entity] === "string" ? set.species[entity] : null);
      const place = world.placeOf(source.set, entity);
      const lane = { record, source, entity, species, name: set.ids[entity], place };
      if (!place?.border) {
        unplaced.push(lane);
        continue;
      }
      lane.forward = (place.first === "a") === first;
      lanes.push(lane);
    }
  }
  return { lanes, unplaced, undirected };
}

/** The largest mean rate of any lane over any interval of the run: its size alone, in the records' unit a second. */
export function busiestOf(run, lanes) {
  let most = 0;
  for (const lane of lanes) {
    for (let step = 1; step < run.count; step++) {
      const mean = meanRate(run, lane.record, lane.entity, step);
      if (mean !== null) most = Math.max(most, Math.abs(mean));
    }
  }
  return most;
}

const smooth = (t) => t * t * (3 - 2 * t);

export const stream = {
  name: "stream",
  channels: ["motion"],
  lives_on: ["junction", "face", "membrane", "route"],
  needs_sign: true,

  /**
   * context (see ./index.js): the sheet with its `world` (the borders between tiles), the
   * run, `fed.sources` (the saved totals as declared), the colours, `speed()` (the replay's
   * speed: seconds of the run each second of watching), `paused()` (whether the replay
   * stands), `still()` (whether nothing may move), `ions` (the species the page knows as
   * ions) and `strength`.
   */
  create({ surface, run, fed, colours, strength = "quiet", speed = () => 1, paused = () => false, still = () => false, ions = new Set() }) {
    const world = surface.world;
    const { lanes, unplaced, undirected } = lanesOf(run, fed.sources || [], world);
    const busiest = busiestOf(run, lanes); // fmol a second
    // What a bead is a token of: ions, where every species that crosses is one the page knows as an ion; molecules otherwise.
    const kinds = new Set(lanes.map((lane) => (lane.species && ions.has(lane.species) ? "ion" : "molecule")));
    const what = kinds.size === 1 ? [...kinds][0] : kinds.size ? "ion or molecule" : "ion";
    // Lanes that share a border stand side by side along it.
    const shared = new Map();
    for (const lane of lanes) {
      const list = shared.get(lane.place.border) || [];
      list.push(lane);
      shared.set(lane.place.border, list);
    }
    for (const [border, list] of shared) list.forEach((lane, k) => (lane.offset = ((k + 0.5) / list.length - 0.5) * 0.66 * border.length));
    let tones = colours;
    const colourOf = (lane) => (lane.species ? tones.ion(lane.species) : tones.ink).clone();
    const heightOf = (tile) => (tile.set === "cell" ? surface.cells[tile.index].height : surface.outside?.level ?? 0);
    /** A point of a lane, a share `t` of its way across its border from side a to side b: a new vector each time. */
    const pathOf = (lane) => (t) => {
      const { border } = lane.place;
      const reach = surface.pitch * 0.62;
      const x = border.mid[0] + border.along[0] * lane.offset + border.across[0] * (t - 0.5) * reach;
      const z = border.mid[1] + border.along[1] * lane.offset + border.across[1] * (t - 0.5) * reach;
      const y = heightOf(border.a) + (heightOf(border.b) - heightOf(border.a)) * smooth(t);
      return new THREE.Vector3(x, y + surface.pitch * 0.07, z);
    };
    lanes.forEach((lane, k) => Object.assign(lane, { key: k, path: pathOf(lane), colour: colourOf(lane), perSecond: 0, reverse: false, mean: null, way: 1 }));

    const radiusAt = (value) => surface.pitch * 0.034 * SIZE[value];
    const token = () => tokenFor(ionsASecond(busiest), speed());
    /** The beads a second of a stream at full width at the speed shown: the run's busiest lane over any interval. */
    const full = () => beadsASecond(ionsASecond(busiest), token(), speed());
    const stands = () => still() || paused();
    // Drawn over the sheet, after its other see-through signs, in the sheet's own order of things.
    const tokens = new Tokens({ lanes, radius: radiusAt(strength), ground: tones.ground, order: 6, resolve: resolveAt(speed()), full: full(), overlay: true });
    surface.root.add(tokens.group);
    let shown = { step: 0, valid: false };
    // The heights the lanes were laid on: a layer on the height channel raises the cells to each record (it is drawn first), and the streams follow.
    const ends = lanes.flatMap((lane) => [lane.place.border.a, lane.place.border.b]);
    let laid = ends.map(heightOf), shaped = 0;
    const settle = () => {
      // The tubes are laid again when the heights change: at once where everything stands, and at most ten times a second
      // while the replay plays (faster than life a record may pass every frame; the beads follow the heights at once).
      const now = ends.map(heightOf), clock = globalThis.performance?.now?.() ?? Date.now();
      if (now.some((height, k) => height !== laid[k]) && (stands() || clock - shaped >= 100)) {
        laid = now;
        shaped = clock;
        tokens.reshape();
      }
      const one = token(), fast = speed(), crossing = paceAt(fast).crossing;
      tokens.setResolve(resolveAt(fast), { crossing, full: full() });
      for (const lane of lanes) {
        lane.mean = shown.valid ? meanRate(run, lane.record, lane.entity, shown.step) : null;
        if (lane.mean) lane.way = (lane.mean > 0) === lane.forward ? 1 : -1;
        tokens.setRate(lane.key, lane.mean ? beadsASecond(ionsASecond(lane.mean), one, fast) : 0, lane.way < 0);
        // With nothing passing, the lane empties; where nothing may move or the replay is paused, the beads stand as many as
        // would be crossing (where beads are drawn at this speed: a stream keeps none).
        if (!lane.perSecond || !(tokens.blend.beads > 0)) lane.beads = [];
        else if (stands()) lane.beads = standing(lane.perSecond, crossing);
      }
      // Placed at once: a paused replay ticks no frame, and its streams, beads and chevrons stand where they are put now.
      tokens.tick(0, stands());
    };

    return {
      lanes,
      unplaced,
      undirected,
      busiest,
      what,
      tokens,
      get shines() {
        return tokens.shines;
      },
      get token() {
        return token();
      },
      /** The ions a second of the run a stream at full width carries: the run's busiest lane over any interval. */
      get widest() {
        return ionsASecond(busiest);
      },
      /** How many beads, chevrons and streams are drawn now (./tokens.js). */
      get drawn() {
        return tokens.drawn;
      },
      update(step, valid) {
        shown = { step, valid };
        settle();
      },
      /** Advance by `milliseconds` of watching at the replay's speed: the run's time the playhead covered, over the speed. Returns whether anything is on its way. */
      tick(milliseconds) {
        if (stands()) return false;
        return tokens.tick(milliseconds / 1000, false);
      },
      /** The replay's clock changed (its speed, or whether it plays): the drawing follows the speed (a stream, packets, beads), a bead stands for another number, and everything stands or sets out. */
      retime() {
        for (const lane of lanes) lane.due = 0;
        settle();
      },
      /** The interval the rates shown are means over: [from, to] in the run's seconds, or null at the first record. */
      interval() {
        return shown.step >= 1 ? [run.t[shown.step - 1], run.t[shown.step]] : null;
      },
      /** The numbers behind each lane at the record shown, for the panel: the two totals, the mean rate, what it is in beads. */
      readings() {
        const { step } = shown;
        const one = token(), fast = speed();
        return lanes.map((lane) => {
          const { border } = lane.place;
          const names = [border.a, border.b].map((tile) => run.sets.get(tile.set).ids[tile.index]);
          const ends = lane.way > 0 ? names : [names[1], names[0]];
          return {
            name: lane.name,
            record: lane.record.id,
            label: lane.source.label,
            species: lane.species,
            unit: lane.record.unit,
            before: step >= 1 ? lane.record.at(step - 1, lane.entity) : null,
            now: lane.record.at(step, lane.entity),
            seconds: step >= 1 ? run.t[step] - run.t[step - 1] : null,
            mean: lane.mean,
            reset: restarted(run, lane.record, lane.entity, step),
            particles: lane.mean === null ? null : Math.abs(ionsASecond(lane.mean)),
            beads: lane.mean === null ? null : beadsASecond(ionsASecond(lane.mean), one, fast),
            ofFull: lane.mean === null ? null : Math.min(1, beadsASecond(ionsASecond(lane.mean), one, fast) / full()),
            from: lane.mean ? ends[0] : null,
            to: lane.mean ? ends[1] : null,
          };
        });
      },
      /** The legend's lines: what the lanes are drawn as at the speed shown, what time the picture keeps, and by whose word a lane goes the way it does. */
      keys() {
        const one = token(), fast = speed(), mode = modeAt(fast);
        const species = [...new Set(lanes.map((lane) => lane.species).filter(Boolean))];
        const many = what === "ion" ? "ions" : what === "molecule" ? "molecules" : "of them";
        const said = flowWords({ speed: fast, token: one, what, widest: ionsASecond(busiest) });
        const lines = [
          ...(species.length ? [{ key: "ions", chips: species.map((id) => ({ colour: tones.ionCss(id), label: id })), text: species.length > 1 ? "Each species that crosses has its own colour" : "The colour of the species that crosses" }] : []),
          { key: "bead", text: mode === "stream" ? `${said}. A stream's width and brightness carry its rate; how fast its streaks run stands for nothing` : `${said}. More of them a second means more ${many} a second; how fast one travels stands for nothing. Where a lane passes less than one now and then, its chevrons alone show` },
          { key: "time", text: timeKey(fast, still(), paused(), what) },
        ];
        // Whose word the direction is: each source says it, and the sources that share a word are named together.
        const by = new Map();
        for (const lane of lanes) {
          const sign = lane.source.sign, whose = signedByShort(sign);
          const said_ = by.get(whose) || new Set();
          said_.add(sign.says);
          by.set(whose, said_);
        }
        for (const [whose, said_] of by) lines.push({ key: "way", text: `A lane flows the way its total grew: ${[...said_].join("; or ")}. ${whose.replace(/\.$/, "")}` });
        // A saved total the layer cannot draw is named, with the reason the run's view gives.
        for (const item of fed.left || []) lines.push({ key: "unplaced", text: `Not drawn: ${(item.record.field ? item.record.label.replace(/: [^:]*$/, "") : item.record.label).toLowerCase()}. ${item.why}` });
        if (lanes.length) lines.push({ key: "head", text: WAY_WORDS });
        if (unplaced.length) lines.push({ key: "unplaced", text: `${unplaced.length} saved total${unplaced.length > 1 ? "s cross borders" : " crosses a border"} this picture does not draw (a cell and a space outside it that has no tile here): no lane for ${unplaced.length > 1 ? "them" : "it"}` });
        return lines;
      },
      setStrength(next) {
        tokens.setRadius(radiusAt(next));
        tokens.tick(0, stands());
      },
      setColours(next) {
        tones = next;
        tokens.setColours(next.ground, colourOf);
        tokens.tick(0, stands());
      },
      dispose() {
        tokens.dispose();
      },
    };
  },
};
