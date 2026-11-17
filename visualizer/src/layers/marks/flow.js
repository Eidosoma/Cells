// The flow along lanes in three dimensions, for flux at true speed and for the way it goes
// (schema/QUANTITY_LAYERS.md, rule 3). The user, 17 November 2026: "at full speed, you wont
// see any individual ions" and "a cool visual for the direction though similar to arrows now
// but cooler". So at true speed and faster a lane is drawn as a stream, not as beads: a tube
// along the lane, as wide and as bright as its rate (the busiest stream the fullest), with
// streaks running along it the way it flows. Slowed, the stream gives way to packets and then
// to beads (./tokens.js); the way is shown by chevrons along the lane, which stand where they
// are when nothing may move, so that a still picture and a visitor who asks for less motion
// are told the way too.
//
// Everything here is one draw call each: the streams of all lanes are one mesh, drawn by a
// small shader (the streaks are worked out in it, no texture, no pass of its own), and the
// chevrons of all lanes one instanced mesh. Both are marked to glow with the beads.
//
// A lane is as ./tokens.js has it: { key, path(share), colour, perSecond, reverse }, with
// `share` here its rate beside the fullest (0 to 1). How fast a streak runs and how fast a
// chevron moves stand for nothing: the width and the brightness carry the rate.

import * as THREE from "../../three.js";

/** Points along a lane, and sides round the tube. */
const ALONG = 28, ROUND = 6;
/** The ways the way is drawn; `chevrons` is the page's (17 November 2026), the others are kept to be compared. */
export const STYLES = ["chevrons", "taper", "arrow"];
/** Chevrons on a lane, and how far apart they run. */
export const CHEVRONS = 3;
/** How many lane lengths a streak runs in a second of watching at true speed: fast, and standing for nothing. */
export const STREAK_PACE = 1.6;

/** The width of a stream as a share of its fullest, for its rate beside the fullest: the area grows with the rate. */
export function widthOf(share) {
  return 0.25 + 0.75 * Math.sqrt(Math.min(1, Math.max(0, share)));
}

const VERTEX = `
attribute vec3 aCentre;
attribute vec3 aSide;
attribute float aU;
attribute float aWidth;
attribute vec3 aColour;
uniform float uRadius;
uniform float uTaper;
varying float vU;
varying float vWidth;
varying vec3 vColour;
void main() {
  vU = aU;
  vWidth = aWidth;
  vColour = aColour;
  // A taper widens a stream toward the end it flows to: the head leads the flow.
  float taper = mix(1.0, 0.2 + 1.0 * aU, uTaper);
  vec3 position = aCentre + aSide * uRadius * aWidth * taper;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const FRAGMENT = `
uniform float uTime;
uniform float uOpacity;
varying float vU;
varying float vWidth;
varying vec3 vColour;
void main() {
  if (vWidth <= 0.0) discard;
  // Streaks run from the end it flows from (u 0) to the end it flows to (u 1).
  float phase = fract(vU * 5.0 - uTime);
  float streak = smoothstep(0.0, 0.12, phase) * (1.0 - smoothstep(0.3, 0.62, phase));
  float ends = smoothstep(0.0, 0.08, vU) * (1.0 - smoothstep(0.9, 1.0, vU));
  float bright = 0.32 + 0.68 * streak;
  gl_FragColor = vec4(vColour * (0.75 + 0.75 * streak), bright * ends * uOpacity * (0.45 + 0.55 * vWidth));
}`;

export class Flow {
  /**
   * lanes  as above; `radius` the fullest stream's radius; `ground` the page's surface, for the chevrons' rims;
   * `stream` whether the lanes are drawn as streams (true speed and faster) or carry beads (slowed);
   * `style` how the way is drawn (STYLES); `order` where it is drawn among what is see-through.
   */
  constructor({ lanes, radius, ground, stream = true, style = "chevrons", order = 60 }) {
    this.lanes = lanes;
    this.radius = radius;
    this.stream = stream;
    this.style = STYLES.includes(style) ? style : "chevrons";
    this.time = 0; // lane lengths the streaks have run
    this.phase = 0.5; // where the chevrons stand along their lanes, as a share of their spacing
    this.group = new THREE.Group();
    this.group.userData.unpickable = true;
    this.shines = [];
    this.materials = [];
    this.geometries = [];
    if (stream) this.buildStreams(order);
    if (this.style === "chevrons") this.buildChevrons(ground, order);
  }

  /** The streams of all lanes, as one mesh: a tube along each lane, its streaks worked out in the shader. */
  buildStreams(order) {
    const lanes = this.lanes, per = ALONG * ROUND;
    const centre = new Float32Array(lanes.length * per * 3), side = new Float32Array(lanes.length * per * 3);
    const u = new Float32Array(lanes.length * per), width = new Float32Array(lanes.length * per), colour = new Float32Array(lanes.length * per * 3);
    const index = [];
    const point = new THREE.Vector3(), next = new THREE.Vector3(), tangent = new THREE.Vector3(), a = new THREE.Vector3(), b = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
    lanes.forEach((lane, k) => {
      for (let i = 0; i < ALONG; i++) {
        const share = i / (ALONG - 1);
        // `u` runs the way the lane flows: from its first end, or from its last where it is reversed.
        point.copy(lane.path(lane.reverse ? 1 - share : share));
        next.copy(lane.path(lane.reverse ? 1 - Math.min(1, share + 0.02) : Math.min(1, share + 0.02)));
        tangent.copy(next).sub(point);
        if (tangent.lengthSq() < 1e-18) tangent.copy(lane.path(lane.reverse ? 1 - share : share)).sub(lane.path(lane.reverse ? 1 - Math.max(0, share - 0.02) : Math.max(0, share - 0.02)));
        tangent.normalize();
        a.crossVectors(tangent, Math.abs(tangent.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : up).normalize();
        b.crossVectors(tangent, a).normalize();
        for (let j = 0; j < ROUND; j++) {
          const angle = (j / ROUND) * Math.PI * 2, at = (k * per + i * ROUND + j);
          centre.set([point.x, point.y, point.z], at * 3);
          side.set([a.x * Math.cos(angle) + b.x * Math.sin(angle), a.y * Math.cos(angle) + b.y * Math.sin(angle), a.z * Math.cos(angle) + b.z * Math.sin(angle)], at * 3);
          u[at] = share;
          colour.set([lane.colour.r, lane.colour.g, lane.colour.b], at * 3);
        }
        if (i < ALONG - 1) {
          for (let j = 0; j < ROUND; j++) {
            const here = k * per + i * ROUND, there = here + ROUND, j2 = (j + 1) % ROUND;
            index.push(here + j, there + j, here + j2, here + j2, there + j, there + j2);
          }
        }
      }
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(centre, 3)); // three.js wants a position; the shader moves it out to the tube
    geometry.setAttribute("aCentre", new THREE.BufferAttribute(centre, 3));
    geometry.setAttribute("aSide", new THREE.BufferAttribute(side, 3));
    geometry.setAttribute("aU", new THREE.BufferAttribute(u, 1));
    this.widths = new THREE.BufferAttribute(width, 1);
    this.widths.setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute("aWidth", this.widths);
    geometry.setAttribute("aColour", new THREE.BufferAttribute(colour, 3));
    geometry.setIndex(index);
    const material = new THREE.ShaderMaterial({
      uniforms: { uTime: { value: 0 }, uOpacity: { value: 1 }, uRadius: { value: this.radius }, uTaper: { value: this.style === "taper" ? 1 : 0 } },
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      transparent: true,
      depthWrite: false,
      toneMapped: false,
      side: THREE.DoubleSide,
    });
    material.userData.noContact = true;
    const mesh = new THREE.Mesh(geometry, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = order;
    mesh.raycast = () => {};
    this.group.add(mesh);
    this.streams = mesh;
    this.geometries.push(geometry);
    this.materials.push(material);
    this.shines.push(mesh);
    this.setShares();
  }

  /** Chevrons along each lane, pointing the way it flows: one instanced mesh, with a rim of the page's ground. */
  buildChevrons(ground, order) {
    // A chevron: two arms meeting at a point along +y, drawn in two crossed planes so that it reads from any side.
    const arm = (x0, y0, x1, y1, w) => {
      const dx = x1 - x0, dy = y1 - y0, length = Math.hypot(dx, dy), nx = (-dy / length) * w, ny = (dx / length) * w;
      return [x0 + nx, y0 + ny, x1 + nx, y1 + ny, x1 - nx, y1 - ny, x0 - nx, y0 - ny];
    };
    const flat = [...arm(-0.9, -0.5, 0, 0.5, 0.22), ...arm(0.9, -0.5, 0, 0.5, 0.22)];
    const positions = [], index = [];
    for (const turn of [0, Math.PI / 2]) {
      for (let q = 0; q < flat.length; q += 8) {
        const base = positions.length / 3;
        for (let v = 0; v < 8; v += 2) positions.push(flat[q + v] * Math.cos(turn), flat[q + v + 1], flat[q + v] * Math.sin(turn));
        index.push(base, base + 1, base + 2, base, base + 2, base + 3);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    const core = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
    core.userData.noContact = true;
    const count = Math.max(1, this.lanes.length * CHEVRONS);
    const mesh = new THREE.InstancedMesh(geometry, core, count);
    mesh.count = 0;
    mesh.frustumCulled = false;
    mesh.renderOrder = order + 2;
    mesh.raycast = () => {};
    mesh.setColorAt(0, ground);
    this.group.add(mesh);
    this.chevrons = mesh;
    this.geometries.push(geometry);
    this.materials.push(core);
    this.shines.push(mesh);
    this.scratch = { matrix: new THREE.Matrix4(), turn: new THREE.Quaternion(), point: new THREE.Vector3(), way: new THREE.Vector3(), scale: new THREE.Vector3(), up: new THREE.Vector3(0, 1, 0) };
  }

  /** Each lane's share of the fullest rate changed: the streams' widths follow. A lane with no rate is not drawn. */
  setShares() {
    if (!this.widths) return;
    const per = ALONG * ROUND, array = this.widths.array;
    this.lanes.forEach((lane, k) => array.fill(lane.perSecond > 0 ? widthOf(lane.share ?? 1) : 0, k * per, (k + 1) * per));
    this.widths.needsUpdate = true;
  }

  /**
   * Run on by a stretch of watching time: the streaks run `pace` lane lengths a second, and the
   * chevrons move along with them (`chevronPace`: lane lengths a second, as the beads do slowed).
   * Where nothing may move, everything stands where it is.
   */
  tick(seconds, still, chevronPace = STREAK_PACE / 4) {
    if (!still) {
      this.time += seconds * STREAK_PACE;
      this.phase = (this.phase + seconds * chevronPace * CHEVRONS) % 1;
    }
    if (this.streams) this.streams.material.uniforms.uTime.value = this.time % 1000;
    this.placeChevrons();
    return !still && this.lanes.some((lane) => lane.perSecond > 0);
  }

  /** Each lane's chevrons, spread evenly along it at the phase they have reached, pointing the way it flows, as large as its stream is wide. */
  placeChevrons() {
    const mesh = this.chevrons;
    if (!mesh) return;
    const { matrix, turn, point, way, scale, up } = this.scratch;
    let at = 0;
    for (const lane of this.lanes) {
      if (!(lane.perSecond > 0)) continue;
      const size = this.radius * 2.6 * widthOf(lane.share ?? 1);
      for (let k = 0; k < CHEVRONS; k++) {
        const share = (k + this.phase) / CHEVRONS;
        const along = lane.reverse ? 1 - share : share, ahead = lane.reverse ? Math.max(0, along - 0.03) : Math.min(1, along + 0.03);
        point.copy(lane.path(along));
        way.copy(lane.path(ahead)).sub(point);
        if (way.lengthSq() < 1e-18) way.copy(up);
        turn.setFromUnitVectors(up, way.normalize());
        mesh.setMatrixAt(at, matrix.compose(point, turn, scale.setScalar(size)));
        mesh.setColorAt(at, lane.colour);
        at++;
      }
    }
    mesh.count = at;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }

  /** How strongly the chevrons and the streams are drawn: a stream gone from the blend is not drawn at all. */
  setOpacity(opacity, stream = opacity) {
    for (const material of this.materials) {
      if (material.uniforms) material.uniforms.uOpacity.value = stream;
      else material.opacity = opacity;
    }
    if (this.streams) this.streams.visible = stream > 0.01;
  }

  dispose() {
    this.group.removeFromParent();
    this.chevrons?.dispose();
    for (const geometry of this.geometries) geometry.dispose();
    for (const material of this.materials) material.dispose();
  }
}
