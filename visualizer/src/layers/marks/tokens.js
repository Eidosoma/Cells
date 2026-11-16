// Beads on lanes of a picture in three dimensions: the mark of flux in the Cell view
// (schema/QUANTITY_LAYERS.md, rule 3, and "Flux in the Cell view"). The arithmetic is the
// bead layer's own (./beads.js): a rate sets how many beads pass a second, never how fast
// one travels; every bead crosses its lane in the same time; an arrowhead ends each lane
// that carries something and points the way its beads go; where nothing may move the beads
// stand, as many as would be on their way at one moment.
//
// The picture gives the lanes: where each runs is the picture's choice, and the page says
// so. A lane is { key, path, colour, perSecond, reverse }: `path(share)` is a point of the
// lane in the units of the group's parent, from its first end (0) to its last (1), and
// `reverse` says that the beads travel from the last end to the first.
//
// The materials stay out of the look (core/look.js): filmic light leaves their colours as
// the legend shows them, they take no part in contact shade, and nothing here can be
// chosen with the pointer. The beads and the arrowheads are what the bloom shines from.

import * as THREE from "../../three.js";
import { advance, standing, headSize, CROSSING, MOST } from "./beads.js";

const UP = new THREE.Vector3(0, 1, 0);
const WHOLE = new THREE.Quaternion();
/** How much larger than a bead its rim is drawn, in the ground's colour, so that a bead reads on any part behind it. */
export const RIM = 1.32;
/** An arrowhead's width beside a bead's, at its full size. */
export const HEAD = 1.25;

/** A bead's size along its lane, as a share of its full size: it comes and goes small. */
export function swell(share) {
  return 0.62 + 0.38 * Math.sin(Math.PI * Math.min(1, Math.max(0, share)));
}

export class Tokens {
  /**
   * lanes   as above; `radius` a bead's radius; `ground` the colour of the page's surface, for the rims;
   * `order` where the beads are drawn among what is see-through: late, so that glass in front does not hide them.
   */
  constructor({ lanes, radius, ground, order = 60 }) {
    this.radius = radius;
    this.ground = ground;
    this.lanes = lanes.map((lane) => ({ ...lane, due: 0, beads: [] }));
    // A lane is as full as it would be had it been watched all along.
    for (const lane of this.lanes) advance(lane, CROSSING);
    this.group = new THREE.Group();
    this.group.userData.unpickable = true;
    const sphere = new THREE.SphereGeometry(1, 16, 12);
    const cone = new THREE.ConeGeometry(1, 2.4, 16); // its tip along +y
    this.geometries = [sphere, cone];
    const core = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, toneMapped: false });
    const rim = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, toneMapped: false, side: THREE.BackSide });
    this.materials = [core, rim];
    for (const material of this.materials) material.userData.noContact = true;
    const make = (geometry, material, count, at) => {
      const mesh = new THREE.InstancedMesh(geometry, material, Math.max(1, count));
      mesh.count = 0;
      mesh.renderOrder = at;
      mesh.frustumCulled = false; // the instances move: their bounds are not kept
      mesh.raycast = () => {}; // a bead never stops a click
      mesh.setColorAt(0, ground);
      this.group.add(mesh);
      return mesh;
    };
    const most = this.lanes.length * MOST, ends = this.lanes.length;
    this.rims = make(sphere, rim, most, order);
    this.cores = make(sphere, core, most, order + 1);
    this.headRims = make(cone, rim, ends, order);
    this.heads = make(cone, core, ends, order + 1);
    this.meshes = [this.rims, this.cores, this.headRims, this.heads];
    this.scratch = { matrix: new THREE.Matrix4(), scale: new THREE.Vector3(), turn: new THREE.Quaternion(), tip: new THREE.Vector3(), way: new THREE.Vector3() };
    this.stood = false;
    this.place(false);
  }

  /** What the bloom shines from. */
  get shines() {
    return [this.cores, this.heads];
  }

  /** How many beads and arrowheads are drawn now. */
  get drawn() {
    return { beads: this.cores.count, heads: this.heads.count };
  }

  /** A lane's rate and way, as a run's record gives them for the interval shown. */
  setRate(key, perSecond, reverse) {
    const lane = this.lanes.find((item) => item.key === key);
    if (!lane) return;
    // A lane that turns round starts empty: a bead on its way is not carried back.
    if (reverse !== lane.reverse) lane.beads = [];
    lane.perSecond = perSecond;
    lane.reverse = reverse;
    this.stood = false;
  }

  /**
   * Advance by a stretch of watching time and place every bead. Where nothing may move the
   * beads stand. Returns whether anything moves.
   */
  tick(seconds, still = false) {
    if (still) {
      if (!this.stood) this.place(true);
      this.stood = true;
      return false;
    }
    this.stood = false;
    let moving = false;
    for (const lane of this.lanes) moving = advance(lane, seconds) || moving;
    this.place(false);
    return moving;
  }

  place(still) {
    const { matrix, scale, turn, tip, way } = this.scratch;
    const { radius, ground, rims, cores, heads, headRims } = this;
    let at = 0, ends = 0;
    for (const lane of this.lanes) {
      const shares = still ? standing(lane.perSecond) : lane.beads;
      for (const share of shares) {
        const point = lane.path(lane.reverse ? 1 - share : share);
        const size = radius * swell(share);
        cores.setMatrixAt(at, matrix.compose(point, WHOLE, scale.setScalar(size)));
        rims.setMatrixAt(at, matrix.compose(point, WHOLE, scale.setScalar(size * RIM)));
        cores.setColorAt(at, lane.colour);
        rims.setColorAt(at, ground);
        at++;
      }
      if (!(lane.perSecond > 0)) continue;
      // The arrowhead stands at the end the beads go to, and points on along the lane's last stretch.
      tip.copy(lane.path(lane.reverse ? 0 : 1));
      way.copy(tip).sub(lane.path(lane.reverse ? 0.06 : 0.94));
      if (way.lengthSq() < 1e-18) way.copy(UP);
      turn.setFromUnitVectors(UP, way.normalize());
      const size = radius * HEAD * headSize(lane.perSecond);
      heads.setMatrixAt(ends, matrix.compose(tip, turn, scale.setScalar(size)));
      headRims.setMatrixAt(ends, matrix.compose(tip, turn, scale.setScalar(size * 1.22)));
      heads.setColorAt(ends, lane.colour);
      headRims.setColorAt(ends, ground);
      ends++;
    }
    cores.count = rims.count = at;
    heads.count = headRims.count = ends;
    for (const mesh of this.meshes) {
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
  }

  /** How strongly the beads are drawn, with the part of the picture they stand in: 0 hides them. */
  setFade(fade) {
    const shown = fade > 0.02;
    this.group.visible = shown;
    for (const material of this.materials) material.opacity = Math.min(1, Math.max(0, fade));
    return shown;
  }

  dispose() {
    this.group.removeFromParent();
    for (const mesh of this.meshes) mesh.dispose();
    for (const geometry of this.geometries) geometry.dispose();
    for (const material of this.materials) material.dispose();
  }
}
