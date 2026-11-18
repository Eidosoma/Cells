// Beads on lanes of a picture in three dimensions: the one renderer of flux, in the Cell view and on
// a replay's sheet and its close-up (schema/QUANTITY_LAYERS.md, rule 3). The arithmetic is the
// bead layer's own (./beads.js): a rate sets how many beads pass a second, never how fast one
// travels; every bead crosses its lane in the same time (longer where the run is slowed, as a
// sign of the slow-down: a lane's `crossing`); where nothing may move the beads stand, as many as
// would be on their way at one moment.
//
// The picture gives the lanes: where each runs is the picture's choice, and the page says
// so. A lane is { key, path, colour, perSecond, reverse }: `path(share)` is a point of the
// lane in the units of the group's parent (a new vector each time), from its first end (0) to
// its last (1), and `reverse` says that the beads travel from the last end to the first. The
// lanes are kept as given (the marks read their beads off them), with what is worked out here
// added: `beads`, `due`, `crossing`, `share`, `length`, `gap`.
//
// The materials stay out of the look (core/look.js): filmic light leaves their colours as
// the legend shows them, they take no part in contact shade, and nothing here can be
// chosen with the pointer. The beads, the streams and the chevrons are what the bloom shines from.
//
// How a lane is drawn follows the speed (17 November 2026, ./beads.js, modeAt): at true speed
// and faster as a stream, as wide and bright as its rate (./flow.js), with no single bead to
// count; slowed a little, as packets that visibly travel; slowed a great deal, as single
// beads crossing slowly. The way it goes is shown by chevrons along the lane (or, to compare,
// by a tapered trail, or by an arrowhead at its end), which stand where nothing may move.
// However short a lane and however busy, no packet overlaps the next (packetOf).

import * as THREE from "../../three.js";
import { advance, standing, headSize, blendAt, CROSSING, MOST } from "./beads.js";
import { Flow } from "./flow.js";

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

/** How much of the room between two beads on a lane the larger of them may take, rim and all: a fifth stays clear. */
export const ROOM = 0.8;

/**
 * How a bead or a packet is drawn on a lane, so that none overlaps the next however short the
 * lane and however busy (17 November 2026): `length` the lane's length, `count` how many are on
 * their way along it at one moment (beads a second times the crossing), `radius` a bead's radius,
 * `stretch` how much longer than a bead a packet is drawn (./beads.js, blendAt). Returns
 * { along, across }: half its length along the lane and its half-width, before its swell (swell)
 * and its rim (RIM). The beads that are on their way together set out evenly, so each has the
 * lane's length over their number to itself: a packet is drawn shorter where that is less than
 * it asks, and where even a round bead would touch the next, the bead is drawn smaller. A packet
 * is never wider than it is long. The number of beads is never touched: the arithmetic of rule 3
 * holds on any lane.
 */
export function packetOf({ length, count, radius, stretch = 1 }) {
  const spacing = count > 0 ? length / Math.ceil(count) : Infinity;
  const room = (ROOM * spacing) / (2 * RIM);
  const along = Math.min(radius * Math.max(1, stretch), room);
  const across = Math.min(radius * (1 + 0.1 * Math.min(1, Math.max(0, stretch - 1))), along);
  return { along, across };
}

/** The fullest stream's radius beside a bead's. */
const FLOW = 0.85;

export class Tokens {
  /**
   * lanes   as above; `radius` a bead's radius; `ground` the colour of the page's surface, for the rims;
   * `order` where the beads are drawn among what is see-through: late, so that glass in front does not hide them;
   * `resolve` how far the run is slowed, in powers of ten (./beads.js, resolveAt, blendAt): 0 draws streams, 3
   * packets, 6 and more single beads, and every value between blends them without a jump (`mode` may name one of
   * the three instead: "stream", "packets", "beads"); `style` how the way is drawn (./flow.js, STYLES);
   * `full` the beads a second of the fullest stream, which a stream's width is measured against.
   */
  constructor({ lanes, radius, ground, order = 60, mode = null, resolve = null, style = "chevrons", full = null, overlay = false, groupOrder = 0 }) {
    this.radius = radius;
    this.ground = ground;
    this.resolve = resolve ?? { stream: 0, packets: 3, beads: 6 }[mode] ?? 6;
    this.blend = blendAt(this.resolve);
    this.style = style;
    this.full = full;
    // The lanes as given, so that a mark reads its beads off its own lanes; each lane's length and its room beside the next (flow.js, measure).
    this.lanes = lanes;
    for (const lane of this.lanes) Object.assign(lane, { crossing: lane.crossing > 0 ? lane.crossing : CROSSING, due: 0, beads: [] });
    for (const lane of this.lanes) lane.share = this.shareOf(lane.perSecond);
    // A lane is as full as it would be had it been watched all along.
    for (const lane of this.lanes) advance(lane, lane.crossing);
    this.group = new THREE.Group();
    this.group.renderOrder = groupOrder; // a group of its own sets the renderer's group order for what is in it
    this.group.userData.unpickable = true;
    const sphere = new THREE.SphereGeometry(1, 16, 12);
    const cone = new THREE.ConeGeometry(1, 2.4, 16); // its tip along +y
    this.geometries = [sphere, cone];
    // `overlay`: drawn over what lies in front, as a replay's sheet and close-up draw their signs, in the order given.
    const core = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, depthTest: !overlay, toneMapped: false });
    const rim = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, depthTest: !overlay, toneMapped: false, side: THREE.BackSide });
    // An arrowhead's own two, so that it shows at true speed, where the beads give way to the stream.
    const headCore = core.clone(), headRim = rim.clone();
    this.materials = [core, rim, headCore, headRim];
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
    this.headRims = make(cone, headRim, ends, order);
    this.heads = make(cone, headCore, ends, order + 1);
    this.meshes = [this.rims, this.cores, this.headRims, this.heads];
    // The stream (at true speed, or as a tapered trail under the beads) and the chevrons: one draw call each.
    // The stream is built whatever the speed: as the slow-down is taken back, it comes back without a new build.
    this.flow = new Flow({ lanes: this.lanes, radius: radius * FLOW, ground, style, order, overlay, groupOrder });
    this.group.add(this.flow.group);
    this.scratch = { matrix: new THREE.Matrix4(), scale: new THREE.Vector3(), turn: new THREE.Quaternion(), tip: new THREE.Vector3(), way: new THREE.Vector3(), up: new THREE.Vector3(0, 1, 0) };
    this.stood = false;
    this.setFade(1);
    this.place(false);
  }

  /** How the lanes are drawn now: "stream", "packets" or "beads", by the blend's larger share (for the words and the tests). */
  get mode() {
    return this.resolve < 1.5 ? "stream" : this.resolve < 4.5 ? "packets" : "beads";
  }

  /**
   * The run is slowed to another point (the Speed slider moves): the blend, the crossing and the fullest stream follow
   * in place, so that nothing jumps: the beads keep where they are, and set out at the new rate from here.
   */
  setResolve(resolve, { crossing = null, full = null } = {}) {
    this.resolve = resolve;
    this.blend = blendAt(resolve);
    if (full !== null) this.full = full;
    for (const lane of this.lanes) {
      if (crossing) lane.crossing = crossing;
      lane.share = this.shareOf(lane.perSecond);
    }
    this.widened = true;
    this.stood = false;
    this.setFade(this.fade);
  }

  /** A lane's rate beside the fullest stream's (0 to 1), for its width; 1 where no fullest is given. */
  shareOf(perSecond) {
    return this.full > 0 ? Math.min(1, Math.max(0, perSecond) / this.full) : 1;
  }

  /** What the bloom shines from: the beads, the streams and the chevrons, and the arrowheads where the way is drawn with them. */
  get shines() {
    return [this.cores, ...(this.style === "arrow" ? [this.heads] : []), ...this.flow.shines];
  }

  /** How many beads, arrowheads, chevrons and streams are drawn now. */
  get drawn() {
    return { beads: this.cores.count, heads: this.heads.count, chevrons: this.flow.chevrons?.count || 0, streams: this.flow.streams?.visible ? this.lanes.filter((lane) => lane.perSecond > 0).length : 0 };
  }

  /** The page's colours changed (its theme): the lanes' own colours are taken in place, the ground for the rims; nothing is built again. */
  setColours(ground, colourOf = (lane) => lane.colour) {
    this.ground = ground;
    for (const lane of this.lanes) lane.colour = colourOf(lane);
    this.flow.setColours();
    this.stood = false;
  }

  /** The lanes moved (their paths give other points now): the streams follow, and each lane's length. */
  reshape() {
    this.flow.reshape();
    this.stood = false;
  }

  /** A bead's radius changed (the layers' strength): the beads, the streams and the chevrons follow in place. */
  setRadius(radius) {
    this.radius = radius;
    this.flow.setRadius(radius * FLOW);
    this.stood = false;
  }

  /** A lane's rate and way, as a run's record gives them for the interval shown. */
  setRate(key, perSecond, reverse) {
    const lane = this.lanes.find((item) => item.key === key);
    if (!lane) return;
    // A lane that turns round starts empty: a bead on its way is not carried back.
    if (reverse !== lane.reverse) lane.beads = [];
    lane.perSecond = perSecond;
    lane.share = this.shareOf(perSecond);
    lane.reverse = reverse;
    this.stood = false;
    this.widened = true; // the streams' widths follow at the next frame
  }

  /**
   * Advance by a stretch of watching time and place every bead. Where nothing may move the
   * beads stand. Returns whether anything moves.
   */
  tick(seconds, still = false) {
    if (this.widened) {
      this.flow.setShares();
      this.widened = false;
    }
    // Chevrons move with what they lead: one lane length a crossing, as the beads go (as fast at true speed).
    const pace = 1 / (this.lanes[0]?.crossing || CROSSING);
    if (still) {
      if (!this.stood) {
        this.place(true);
        this.flow.tick(0, true, pace);
      }
      this.stood = true;
      return false;
    }
    this.stood = false;
    let moving = false;
    // Where beads show, they set out and travel; a stream alone keeps none, and its streaks run on.
    if (this.blend.beads > 0) for (const lane of this.lanes) moving = advance(lane, seconds) || moving;
    else for (const lane of this.lanes) lane.beads = [];
    moving = this.flow.tick(seconds, false, pace, this.blend.stream) || moving;
    this.place(false);
    return moving;
  }

  place(still) {
    const { matrix, scale, turn, tip, way, up } = this.scratch;
    const { radius, ground, rims, cores, heads, headRims } = this;
    // A bead is drawn longer the less it is slowed: a packet slowed a thousand times, round slowed a million times.
    const stretch = this.blend.stretch;
    let at = 0, ends = 0;
    for (const lane of this.lanes) {
      const shares = !(this.blend.beads > 0) ? [] : still ? standing(lane.perSecond, lane.crossing) : lane.beads;
      // As long as the room each has on its lane allows: none overlaps the next (packetOf).
      const drawn = shares.length ? packetOf({ length: lane.length, count: lane.perSecond * lane.crossing, radius, stretch }) : null;
      const packets = drawn && drawn.along > drawn.across * 1.02;
      for (const share of shares) {
        const along = lane.reverse ? 1 - share : share;
        const point = lane.path(along);
        const grown = swell(share);
        if (packets) {
          // A packet: drawn long along its lane, the way it travels.
          way.copy(lane.path(lane.reverse ? Math.max(0, along - 0.02) : Math.min(1, along + 0.02))).sub(point);
          if (way.lengthSq() < 1e-18) way.copy(up);
          turn.setFromUnitVectors(up, way.normalize());
          cores.setMatrixAt(at, matrix.compose(point, turn, scale.set(drawn.across * grown, drawn.along * grown, drawn.across * grown)));
          rims.setMatrixAt(at, matrix.compose(point, turn, scale.set(drawn.across * grown * RIM, drawn.along * grown * RIM, drawn.across * grown * RIM)));
        } else {
          cores.setMatrixAt(at, matrix.compose(point, WHOLE, scale.setScalar(drawn.across * grown)));
          rims.setMatrixAt(at, matrix.compose(point, WHOLE, scale.setScalar(drawn.across * grown * RIM)));
        }
        cores.setColorAt(at, lane.colour);
        rims.setColorAt(at, ground);
        at++;
      }
      // Today's arrowhead at the end of a lane, only where the way is drawn that way.
      if (!(lane.perSecond > 0) || this.style !== "arrow") continue;
      // The arrowhead stands at the end the beads go to, and points on along the lane's last stretch.
      tip.copy(lane.path(lane.reverse ? 0 : 1));
      way.copy(tip).sub(lane.path(lane.reverse ? 0.06 : 0.94));
      if (way.lengthSq() < 1e-18) way.copy(UP);
      turn.setFromUnitVectors(UP, way.normalize());
      const size = radius * HEAD * headSize(lane.perSecond, lane.crossing);
      heads.setMatrixAt(ends, matrix.compose(tip, turn, scale.setScalar(size)));
      headRims.setMatrixAt(ends, matrix.compose(tip, turn, scale.setScalar(size * 1.22)));
      heads.setColorAt(ends, lane.colour);
      headRims.setColorAt(ends, ground);
      ends++;
    }
    // Only what is drawn, or has just gone, is sent to the card again: a stream at true speed sends no bead.
    const was = [cores.count, heads.count];
    cores.count = rims.count = at;
    heads.count = headRims.count = ends;
    for (const [mesh, before] of [[rims, was[0]], [cores, was[0]], [headRims, was[1]], [heads, was[1]]]) {
      if (!mesh.count && !before) continue;
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
  }

  /** How strongly the beads are drawn, with the part of the picture they stand in: 0 hides them. */
  setFade(fade) {
    this.fade = fade;
    const shown = fade > 0.02, clamped = Math.min(1, Math.max(0, fade));
    this.group.visible = shown;
    // The beads and the stream each by their share of the blend; the chevrons whole. A tapered trail stays, faint under beads.
    this.materials[0].opacity = this.materials[1].opacity = clamped * this.blend.beads;
    this.materials[2].opacity = this.materials[3].opacity = clamped;
    // A tapered trail stays, faint under the beads; so does a stream that carries the way painted in it.
    const trail = this.style === "taper" ? Math.max(this.blend.stream, 0.35) : this.style === "painted" ? Math.max(this.blend.stream, 0.5) : this.blend.stream;
    this.flow.setOpacity(clamped, clamped * trail);
    return shown;
  }

  dispose() {
    this.flow.dispose();
    this.group.removeFromParent();
    for (const mesh of this.meshes) mesh.dispose();
    for (const geometry of this.geometries) geometry.dispose();
    for (const material of this.materials) material.dispose();
  }
}
