// stream: beads that cross a border of the picture, as many a second as a saved total grew
// between two records. A border is where two tiles meet (../world.js): two cells joined by a
// junction, a cell and the space outside it that its membrane faces, two spaces outside
// joined by a face. Every saved total that lies on such a border gets a lane of its own
// there: what crossed a junction, a face or a membrane for each species, and what an
// exchange route carried.
//
// A bead is a token of a rate, not a particle (schema/QUANTITY_LAYERS.md, rule 3):
//
//   beads a second on the screen = particles a second / (particles in one bead x how much it is slowed)
//
// The rate sets how many beads pass, never how fast one travels: every bead takes the same
// time to cross, which stands for nothing. The rate is a mean over the interval that ends at
// the record shown (the `rate` rule), so at a run's first record there is none.
//
// A bead goes the way its total grew: from the end the record's declared sign calls the
// source to the other when the mean rate is positive, back when it is negative. A total with
// no declared direction is not drawn.
//
// Beads are plain discs of colour with a rim of the page's ground, so they read on a tile of
// any colour without any finishing pass; the lens may mark them to shine (`shines`). An
// arrowhead beyond the far end of each lane that carries something points the way its beads
// go, so that a still picture, and a visitor who asks for less motion, are told the way too.

import * as THREE from "../../three.js";
import { tokenFor, beadsASecond, ionsASecond, timeWords, tokenWords, meanRate, restarted, standing, advance, headSize, MOST, HEAD_WORDS, STILL_WORDS } from "./beads.js";
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
   * run, `fed.sources` (the saved totals as declared), the colours, `slow()` (how much the
   * picture is slowed: 1 is true speed), `still()` (whether nothing may move), `ions` (the
   * species the page knows as ions) and `strength`.
   */
  create({ surface, run, fed, colours, strength = "quiet", slow = () => 1, still = () => false, ions = new Set() }) {
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
    for (const lane of lanes) Object.assign(lane, { beads: [], due: 0, perSecond: 0, mean: null, way: 1 });

    let size = SIZE[strength];
    const capacity = Math.max(1, lanes.length * MOST);
    const shape = new THREE.SphereGeometry(1, 12, 8);
    // An arrowhead lying flat, pointing along +x; turned for each lane to the way its beads go.
    const headShape = new THREE.BufferGeometry();
    headShape.setAttribute("position", new THREE.Float32BufferAttribute([1, 0, 0, -0.7, 0, 0.85, -0.7, 0, -0.85], 3));
    // Unlit and out of the scene's look: a bead's colour is exactly its species' colour. Drawn with the sheet's
    // other see-through signs, after them (a glow lies under the beads that cross it).
    const coreMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
    const rimMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
    const make = (material, order, geometry = shape, count = capacity) => {
      const mesh = new THREE.InstancedMesh(geometry, material, count);
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.setColorAt(0, colours.ink);
      mesh.frustumCulled = false;
      mesh.renderOrder = order;
      mesh.userData.unpickable = true;
      mesh.userData.noContact = true;
      mesh.count = 0;
      return mesh;
    };
    const rims = make(rimMaterial, 6), cores = make(coreMaterial, 7);
    const headRims = make(rimMaterial, 6, headShape, Math.max(1, lanes.length)), heads = make(coreMaterial, 7, headShape, Math.max(1, lanes.length));
    const group = new THREE.Group();
    group.userData.unpickable = true;
    group.add(rims, cores, headRims, heads);
    surface.root.add(group);
    let tones = colours;
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
    const turn = new THREE.Quaternion(), upwards = new THREE.Vector3(0, 1, 0);
    const heightOf = (tile) => (tile.set === "cell" ? surface.cells[tile.index].height : surface.outside?.level ?? 0);
    /** Where a bead stands, a share `u` of its way across its lane's border. */
    const place = (lane, u, out) => {
      const { border } = lane.place;
      const t = lane.way > 0 ? u : 1 - u; // from side a to side b, or back
      const reach = surface.pitch * 0.62;
      const x = border.mid[0] + border.along[0] * lane.offset + border.across[0] * (t - 0.5) * reach;
      const z = border.mid[1] + border.along[1] * lane.offset + border.across[1] * (t - 0.5) * reach;
      const y = heightOf(border.a) + (heightOf(border.b) - heightOf(border.a)) * smooth(t);
      return out.set(x, y + surface.pitch * 0.07, z);
    };
    const drawBeads = () => {
      let at = 0;
      const radius = surface.pitch * 0.034 * size;
      for (const lane of lanes) {
        const colour = lane.species ? tones.ion(lane.species) : tones.ink;
        for (const u of lane.beads) {
          if (at >= capacity) break;
          place(lane, u, position);
          // A bead grows in as it sets out and shrinks away as it arrives.
          const grown = 0.45 + 0.55 * Math.sin(Math.PI * Math.min(1, Math.max(0, u)));
          cores.setMatrixAt(at, matrix.compose(position, quaternion, scale.setScalar(radius * grown)));
          rims.setMatrixAt(at, matrix.compose(position, quaternion, scale.setScalar(radius * grown * 1.5)));
          cores.setColorAt(at, colour);
          rims.setColorAt(at, tones.ground);
          at += 1;
        }
      }
      cores.count = rims.count = at;
      // The arrowheads: one a little beyond the far end of each lane that carries something, pointing the way its beads go.
      let ends = 0;
      for (const lane of lanes) {
        if (!(lane.perSecond > 0)) continue;
        const { border } = lane.place;
        place(lane, 1, position);
        position.x += border.across[0] * lane.way * surface.pitch * 0.075;
        position.z += border.across[1] * lane.way * surface.pitch * 0.075;
        turn.setFromAxisAngle(upwards, -Math.atan2(border.across[1] * lane.way, border.across[0] * lane.way));
        const grown = headSize(lane.perSecond);
        heads.setMatrixAt(ends, matrix.compose(position, turn, scale.setScalar(radius * 1.5 * grown)));
        headRims.setMatrixAt(ends, matrix.compose(position, turn, scale.setScalar(radius * 2.1 * grown)));
        heads.setColorAt(ends, lane.species ? tones.ion(lane.species) : tones.ink);
        headRims.setColorAt(ends, tones.ground);
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
      for (const lane of lanes) {
        lane.mean = shown.valid ? meanRate(run, lane.record, lane.entity, shown.step) : null;
        lane.perSecond = lane.mean ? beadsASecond(ionsASecond(lane.mean), one, slowed) : 0;
        if (lane.mean) lane.way = (lane.mean > 0) === lane.forward ? 1 : -1;
        // With nothing passing, the lane empties; where nothing may move, the beads stand as many as would be crossing.
        if (!lane.perSecond) lane.beads = [];
        else if (still()) lane.beads = standing(lane.perSecond);
      }
      drawBeads();
    };

    return {
      lanes,
      unplaced,
      undirected,
      busiest,
      what,
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
        for (const lane of lanes) moving = advance(lane, seconds) || moving;
        drawBeads();
        return moving;
      },
      /** The slow-down changed: a bead stands for another number, and as many pass as before for the busiest lane. */
      setSlow() {
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
        const one = token(), slowed = slow();
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
            beads: lane.mean === null ? null : beadsASecond(ionsASecond(lane.mean), one, slowed),
            from: lane.mean ? ends[0] : null,
            to: lane.mean ? ends[1] : null,
          };
        });
      },
      /** The legend's lines: what one bead stands for, what time the picture keeps, and by whose word a bead goes the way it does. */
      keys() {
        const one = token();
        const species = [...new Set(lanes.map((lane) => lane.species).filter(Boolean))];
        const lines = [
          ...(species.length ? [{ key: "ions", chips: species.map((id) => ({ colour: tones.ionCss(id), label: id })), text: species.length > 1 ? "Each species that crosses has its own colour" : "The colour of the species that crosses" }] : []),
          { key: "bead", text: `${tokenWords(one, what)}. More beads a second means more ${what === "ion" ? "ions" : what === "molecule" ? "molecules" : "of them"} a second; how fast a bead travels stands for nothing` },
          { key: "time", text: still() ? `${timeWords(slow())}. ${STILL_WORDS}` : timeWords(slow()) },
        ];
        // Whose word the direction is: each source says it, and the sources that share a word are named together.
        const by = new Map();
        for (const lane of lanes) {
          const sign = lane.source.sign, whose = signedByShort(sign);
          const said = by.get(whose) || new Set();
          said.add(sign.says);
          by.set(whose, said);
        }
        for (const [whose, said] of by) lines.push({ key: "way", text: `A bead goes the way its total grew: ${[...said].join("; or ")}. ${whose.replace(/\.$/, "")}` });
        // A saved total the layer cannot draw is named, with the reason the run's view gives.
        for (const item of fed.left || []) lines.push({ key: "unplaced", text: `Not drawn: ${(item.record.field ? item.record.label.replace(/: [^:]*$/, "") : item.record.label).toLowerCase()}. ${item.why}` });
        if (lanes.length) lines.push({ key: "head", text: HEAD_WORDS });
        if (unplaced.length) lines.push({ key: "unplaced", text: `${unplaced.length} saved total${unplaced.length > 1 ? "s cross borders" : " crosses a border"} this picture does not draw (a cell and a space outside it that has no tile here): no beads for ${unplaced.length > 1 ? "them" : "it"}` });
        return lines;
      },
      setStrength(next) {
        size = SIZE[next];
        drawBeads();
      },
      setColours(next) {
        tones = next;
        drawBeads();
      },
      dispose() {
        surface.root.remove(group);
        shape.dispose();
        headShape.dispose();
        coreMaterial.dispose();
        rimMaterial.dispose();
        for (const mesh of [cores, rims, heads, headRims]) mesh.dispose();
      },
    };
  },
};
