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
// chevron moves stand for nothing: the width and the brightness carry the rate. A lane's
// rate, its way and its colour may change after it is built (a replay steps from record to
// record; the page's theme changes): the streams follow in place, without a new build.
//
// Where lanes crowd (several side by side through one part of a membrane) a chevron is drawn no
// wider than leaves room to the next lane, and a short lane carries fewer (17 November 2026: at a
// thousandfold the chevrons at a crowded place read as a heap of arrow figures).

import * as THREE from "../../three.js";

/** Points along a lane, and sides round the tube. */
const ALONG = 28, ROUND = 6;
/**
 * The ways the way is drawn; `chevrons` is the page's (17 November 2026), the others are kept to be compared:
 * `taper` a trail that widens toward where it flows, `arrow` an arrowhead at the lane's end, and `painted` chevrons
 * drawn in the lane's own stream, which never reach past its width (a fourth, offered on 17 November 2026 for places
 * where several lanes lie side by side).
 */
export const STYLES = ["chevrons", "taper", "arrow", "painted"];
/** Chevrons on a lane at most, and how far apart they run. */
export const CHEVRONS = 3;
/** How many lane lengths a streak runs in a second of watching at true speed: fast, and standing for nothing. */
export const STREAK_PACE = 1.6;
/**
 * A chevron's shape for a size of one: two arms from (-0.9, -0.5) and (0.9, -0.5) to a point at (0, 0.5), each `thick`
 * to either side of its middle, joined by a mitre. Returns the six corners of its outline (left arm's outer end, the outer
 * point, the right arm's outer end, its inner end, the inner point, the left arm's inner end), its width and its length.
 */
export function chevronShape(thick = 0.3) {
  const dx = 0.9, dy = 1, length = Math.hypot(dx, dy), nx = thick / length * dy, ny = thick / length * dx;
  // Where the two arms' outer (and inner) edges meet, on the middle line.
  const tip = (sign) => 0.5 + sign * thick * length / dx;
  const outline = [[-0.9 - nx, -0.5 + ny], [0, tip(1)], [0.9 + nx, -0.5 + ny], [0.9 - nx, -0.5 - ny], [0, tip(-1)], [-0.9 + nx, -0.5 - ny]];
  return { outline, wide: 2 * (0.9 + nx), long: tip(1) - (-0.5 - ny) };
}
/** A chevron's width and its length along its lane, for a size of one. */
export const CHEVRON_WIDE = chevronShape().wide, CHEVRON_LONG = chevronShape().long;
/**
 * How strongly a chevron is drawn over what lies behind it (the user, 17 November 2026: "maybe make them a bit
 * translucent as sometimes they get mixed up with ions"): enough that a bead or an ion behind it shows through, and
 * that it reads as a sign laid over the lane rather than one more thing that moves; and how far its colour is taken
 * toward white, so that it is not an ion's colour either.
 */
export const SEE_THROUGH = 0.7, TINT = 0.15;

const CHEVRON_VERTEX = `
varying vec3 vColour;
void main() {
  // The instance gives the chevron's place, the way its lane runs (its y) and its size; it is turned about that way to face the camera.
  mat4 placed = modelViewMatrix * instanceMatrix;
  vec4 centre = placed * vec4(0.0, 0.0, 0.0, 1.0);
  vec3 run = (placed * vec4(0.0, 1.0, 0.0, 0.0)).xyz;
  float size = length(run);
  vec3 along = run / max(size, 1e-12);
  vec3 eye = projectionMatrix[2][3] == 0.0 ? vec3(0.0, 0.0, 1.0) : normalize(-centre.xyz);
  vec3 across = cross(along, eye);
  float seen = length(across);
  // A lane seen end on: the chevron keeps a width of its own, and its length shrinks as the lane does.
  across = seen > 1e-4 ? across / seen : normalize(cross(along, vec3(0.0, 1.0, 0.001)));
  vec3 point = centre.xyz + (along * position.y + across * position.x) * size;
  gl_Position = projectionMatrix * vec4(point, 1.0);
#ifdef USE_INSTANCING_COLOR
  vColour = instanceColor;
#else
  vColour = vec3(1.0);
#endif
}`;

const CHEVRON_FRAGMENT = `
uniform float uOpacity;
varying vec3 vColour;
void main() {
  gl_FragColor = vec4(vColour, uOpacity);
  #include <colorspace_fragment>
}`;

/** The width of a stream as a share of its fullest, for its rate beside the fullest: the area grows with the rate. */
export function widthOf(share) {
  return 0.25 + 0.75 * Math.sqrt(Math.min(1, Math.max(0, share)));
}

/**
 * How many chevrons a lane carries and how large they are, so that they read as marks of its way
 * and never as a heap: `size` is the chevron's size where room allows; `gap` the distance from the
 * lane's middle stretch to the nearest other lane (none: Infinity); `length` the lane's length.
 * A chevron is no wider than two fifths of the gap on either side, so that two lanes' chevrons
 * side by side keep a fifth of the gap between them (never under a quarter of its size: lanes laid
 * on one another still show their way); a lane carries as many as stand three of their own lengths
 * apart, from one to three (`most`).
 */
export function chevronFit({ length, gap = Infinity, size, most = CHEVRONS }) {
  const fitted = Math.max(size / 4, Math.min(size, (0.8 * gap) / CHEVRON_WIDE));
  const count = Math.max(1, Math.min(most, Math.floor(length / (3 * CHEVRON_LONG * fitted))));
  return { size: fitted, count };
}

/** Points of a lane, from its first end to its last. */
function samples(lane, count) {
  return Array.from({ length: count }, (_, k) => lane.path(k / (count - 1)));
}

/**
 * Each lane's length and the gap from its middle stretch to the nearest other lane, kept on the
 * lane (`length`, `gap`) where it has none: what a packet and a chevron are fitted to.
 */
export function measure(lanes) {
  const points = lanes.map((lane) => samples(lane, 17));
  const boxes = points.map((list) => new THREE.Box3().setFromPoints(list));
  lanes.forEach((lane, k) => {
    if (!(lane.length > 0)) lane.length = points[k].reduce((sum, point, n) => (n ? sum + point.distanceTo(points[k][n - 1]) : 0), 0);
    if (lane.gap !== undefined) return;
    // The nearest lanes first, by their bounds: a lane whose bounds lie farther than the gap found cannot be nearer.
    const middle = points[k].slice(3, 14), box = new THREE.Box3().setFromPoints(middle);
    const others = boxes.map((other, n) => ({ n, apart: n === k ? Infinity : boxApart(box, other) })).filter((item) => item.apart < Infinity).sort((x, y) => x.apart - y.apart);
    let gap = Infinity;
    for (const { n, apart } of others) {
      if (apart >= gap) break;
      for (const here of middle) for (const there of points[n]) gap = Math.min(gap, here.distanceTo(there));
    }
    lane.gap = gap;
  });
  return lanes;
}

/** The least distance between two boxes (nought where they meet). */
function boxApart(a, b) {
  const dx = Math.max(0, a.min.x - b.max.x, b.min.x - a.max.x), dy = Math.max(0, a.min.y - b.max.y, b.min.y - a.max.y), dz = Math.max(0, a.min.z - b.max.z, b.min.z - a.max.z);
  return Math.hypot(dx, dy, dz);
}

const VERTEX = `
attribute vec3 aCentre;
attribute vec3 aSide;
attribute float aS;
attribute float aWidth;
attribute float aReverse;
attribute vec3 aColour;
attribute vec3 aTangent;
attribute float aLength;
uniform float uRadius;
uniform float uTaper;
varying float vU;
varying float vWidth;
varying vec3 vColour;
varying float vAcross;
varying float vLength;
varying float vRadius;
void main() {
  // u runs the way the lane flows: from its first end, or from its last where it is reversed.
  float u = aReverse > 0.5 ? 1.0 - aS : aS;
  vU = u;
  vWidth = aWidth;
  vColour = aColour;
  vLength = aLength;
  // A taper widens a stream toward the end it flows to: the head leads the flow.
  float taper = mix(1.0, 0.2 + 1.0 * u, uTaper);
  vRadius = uRadius * aWidth * taper;
  vec3 position = aCentre + aSide * vRadius;
  // Where this point of the tube's rim lies across the stream as seen (-1 to 1): what a chevron drawn in it is shaped by.
  vec4 middle = modelViewMatrix * vec4(aCentre, 1.0);
  vec3 along = normalize((modelViewMatrix * vec4(aTangent, 0.0)).xyz);
  vec3 seen = normalize(cross(along, normalize(-middle.xyz)));
  vAcross = dot(normalize((modelViewMatrix * vec4(aSide, 0.0)).xyz), seen);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const FRAGMENT = `
uniform float uTime;
uniform float uOpacity;
uniform float uPaint;
uniform float uMove;
varying float vU;
varying float vWidth;
varying vec3 vColour;
varying float vAcross;
varying float vLength;
varying float vRadius;
void main() {
  if (vWidth <= 0.0) discard;
  float ends = smoothstep(0.0, 0.08, vU) * (1.0 - smoothstep(0.9, 1.0, vU));
  if (uPaint > 0.5) {
    // Chevrons drawn in the stream: bands across it whose middle leads and whose sides trail, a ">" the way it flows,
    // about five of its widths apart (two on a short lane), moving with what flows. They never reach past the stream.
    // Only the near side of the tube is drawn, so that the far side's bands do not cross them.
    if (!gl_FrontFacing) discard;
    float spacing = min(5.0 * vRadius, vLength / 2.0);
    float lag = abs(vAcross) * vRadius * 1.8;
    float phase = fract((vU * vLength + lag) / spacing - uMove * vLength / spacing);
    float band = smoothstep(0.0, 0.07, phase) * (1.0 - smoothstep(0.18, 0.26, phase));
    float edge = 1.0 - smoothstep(0.85, 1.0, abs(vAcross));
    gl_FragColor = vec4(vColour * (0.8 + 0.7 * band), (0.16 + 0.84 * band) * edge * ends * uOpacity * (0.45 + 0.55 * vWidth));
    return;
  }
  // Streaks run from the end it flows from (u 0) to the end it flows to (u 1).
  float phase = fract(vU * 5.0 - uTime);
  float streak = smoothstep(0.0, 0.12, phase) * (1.0 - smoothstep(0.3, 0.62, phase));
  float bright = 0.32 + 0.68 * streak;
  gl_FragColor = vec4(vColour * (0.75 + 0.75 * streak), bright * ends * uOpacity * (0.45 + 0.55 * vWidth));
}`;

export class Flow {
  /**
   * lanes  as above; `radius` the fullest stream's radius; `ground` the page's surface, for the chevrons' rims;
   * `style` how the way is drawn (STYLES); `order` where it is drawn among what is see-through; `overlay` that it is
   * drawn over what lies in front of it (a replay's sheet and its close-up draw their signs so), and `groupOrder`
   * the order of the group it is drawn in (a group of its own resets the renderer's group order: see three.js).
   * The streams are built whatever the speed, and shown only where the blend has them (setOpacity): a slow-down
   * taken back brings them without a new build.
   */
  constructor({ lanes, radius, ground, style = "chevrons", order = 60, overlay = false, groupOrder = 0 }) {
    this.lanes = measure(lanes);
    this.radius = radius;
    this.style = STYLES.includes(style) ? style : "chevrons";
    this.overlay = overlay;
    this.time = 0; // lane lengths the streaks have run
    this.travel = 0; // lane lengths the chevrons have moved, of a whole one
    this.moved = 0; // lane lengths the chevrons painted in a stream have moved
    this.most = CHEVRONS; // chevrons on a lane at most
    this.see = SEE_THROUGH; // how strongly a chevron is drawn over what lies behind it
    this.group = new THREE.Group();
    this.group.renderOrder = groupOrder;
    this.group.userData.unpickable = true;
    this.shines = [];
    this.materials = [];
    this.geometries = [];
    this.buildStreams(order);
    if (this.style === "chevrons") this.buildChevrons(ground, order);
  }

  /** The streams of all lanes, as one mesh: a tube along each lane, its streaks worked out in the shader. */
  buildStreams(order) {
    const lanes = this.lanes, per = ALONG * ROUND;
    const centre = new Float32Array(lanes.length * per * 3), side = new Float32Array(lanes.length * per * 3);
    const along = new Float32Array(lanes.length * per), width = new Float32Array(lanes.length * per), reverse = new Float32Array(lanes.length * per), colour = new Float32Array(lanes.length * per * 3);
    const index = [];
    lanes.forEach((lane, k) => {
      for (let i = 0; i < ALONG - 1; i++) {
        for (let j = 0; j < ROUND; j++) {
          const here = k * per + i * ROUND, there = here + ROUND, j2 = (j + 1) % ROUND;
          index.push(here + j, there + j, here + j2, here + j2, there + j, there + j2);
        }
      }
    });
    this.tangents = new THREE.BufferAttribute(new Float32Array(lanes.length * per * 3), 3);
    this.lengths = new THREE.BufferAttribute(new Float32Array(lanes.length * per), 1);
    this.shape(centre, side, along);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("aTangent", this.tangents);
    geometry.setAttribute("aLength", this.lengths);
    this.centres = new THREE.BufferAttribute(centre, 3);
    this.sides = new THREE.BufferAttribute(side, 3);
    geometry.setAttribute("position", this.centres); // three.js wants a position; the shader moves it out to the tube
    geometry.setAttribute("aCentre", this.centres);
    geometry.setAttribute("aSide", this.sides);
    geometry.setAttribute("aS", new THREE.BufferAttribute(along, 1));
    const dynamic = (array, size) => new THREE.BufferAttribute(array, size).setUsage(THREE.DynamicDrawUsage);
    this.widths = dynamic(width, 1);
    this.ways = dynamic(reverse, 1);
    this.colours = dynamic(colour, 3);
    geometry.setAttribute("aWidth", this.widths);
    geometry.setAttribute("aReverse", this.ways);
    geometry.setAttribute("aColour", this.colours);
    geometry.setIndex(index);
    const material = new THREE.ShaderMaterial({
      uniforms: { uTime: { value: 0 }, uOpacity: { value: 1 }, uRadius: { value: this.radius }, uTaper: { value: this.style === "taper" ? 1 : 0 }, uPaint: { value: this.style === "painted" ? 1 : 0 }, uMove: { value: 0 } },
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      transparent: true,
      depthWrite: false,
      depthTest: !this.overlay,
      toneMapped: false,
      side: THREE.DoubleSide,
      forceSinglePass: true, // the tube's near and far sides in one pass: its streaks show through it either way
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
    this.setColours();
  }

  /**
   * Where each lane's tube runs: its middle and the way round it at each point, from the lane's first end to its last.
   * Each point of a lane is asked of its path once; the way along it is taken from the points beside it. A replay's sheet
   * asks for this at every record a height layer raises the cells to, so it is kept to arithmetic.
   */
  shape(centre, side, along) {
    const per = ALONG * ROUND;
    const tangent = new THREE.Vector3(), a = new THREE.Vector3(), b = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), across = new THREE.Vector3(1, 0, 0);
    const cos = Array.from({ length: ROUND }, (_, j) => Math.cos((j / ROUND) * Math.PI * 2)), sin = Array.from({ length: ROUND }, (_, j) => Math.sin((j / ROUND) * Math.PI * 2));
    const tangents = this.tangents.array, lengths = this.lengths.array;
    this.lanes.forEach((lane, k) => {
      const points = Array.from({ length: ALONG }, (_, i) => lane.path(i / (ALONG - 1)));
      lane.samples = points; // kept: the chevrons are placed along them each frame without asking the path again
      for (let i = 0; i < ALONG; i++) {
        // Built from the lane's first end to its last; which way it flows is an attribute of its own (aReverse).
        const point = points[i];
        tangent.subVectors(points[Math.min(ALONG - 1, i + 1)], points[Math.max(0, i - 1)]);
        if (tangent.lengthSq() < 1e-18) tangent.copy(up);
        tangent.normalize();
        a.crossVectors(tangent, Math.abs(tangent.y) > 0.9 ? across : up).normalize();
        b.crossVectors(tangent, a).normalize();
        for (let j = 0; j < ROUND; j++) {
          const at = (k * per + i * ROUND + j) * 3;
          centre[at] = point.x;
          centre[at + 1] = point.y;
          centre[at + 2] = point.z;
          side[at] = a.x * cos[j] + b.x * sin[j];
          side[at + 1] = a.y * cos[j] + b.y * sin[j];
          side[at + 2] = a.z * cos[j] + b.z * sin[j];
          tangents[at] = tangent.x;
          tangents[at + 1] = tangent.y;
          tangents[at + 2] = tangent.z;
          lengths[at / 3] = lane.length;
          if (along) along[at / 3] = i / (ALONG - 1);
        }
      }
    });
  }

  /** The lanes moved (a replay's sheet raised its cells to the record shown): the tubes follow, and each lane's length. */
  reshape() {
    for (const lane of this.lanes) delete lane.length;
    measure(this.lanes.map((lane) => Object.assign(lane, { gap: lane.gap ?? Infinity })));
    if (!this.centres) return;
    this.shape(this.centres.array, this.sides.array, null);
    this.centres.needsUpdate = this.sides.needsUpdate = this.tangents.needsUpdate = this.lengths.needsUpdate = true;
  }

  /** Chevrons along each lane, pointing the way it flows: one instanced mesh, with a rim of the page's ground. */
  buildChevrons(ground, order) {
    // A chevron: one flat mark, its two arms joined at the point by a mitre (no notch, no seam, no piece over another),
    // turned in the vertex shader about its lane to face the camera, so that it reads as one mark from every side.
    const { outline } = chevronShape();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(outline.flatMap(([x, y]) => [x, y, 0]), 3));
    // Two quadrilaterals sharing the edge from the outer point to the inner: the left arm and the right.
    geometry.setIndex([0, 1, 4, 0, 4, 5, 1, 2, 3, 1, 3, 4]);
    const material = new THREE.ShaderMaterial({
      uniforms: { uOpacity: { value: SEE_THROUGH } },
      vertexShader: CHEVRON_VERTEX,
      fragmentShader: CHEVRON_FRAGMENT,
      transparent: true,
      depthWrite: false,
      depthTest: !this.overlay,
      toneMapped: false,
      side: THREE.DoubleSide,
      forceSinglePass: true, // one flat mark: two passes would cost two draw calls for nothing seen
    });
    material.userData.noContact = true;
    material.userData.chevrons = true;
    const count = Math.max(1, this.lanes.length * CHEVRONS);
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.count = 0;
    mesh.frustumCulled = false;
    mesh.renderOrder = order + 2; // after the beads: a bead behind a chevron shows through it
    mesh.raycast = () => {};
    mesh.setColorAt(0, ground);
    this.group.add(mesh);
    this.chevrons = mesh;
    this.geometries.push(geometry);
    this.materials.push(material);
    // Not among what shines: a chevron is a sign laid over the lane, and a glow would make it one more bright bead.
    this.scratch = { matrix: new THREE.Matrix4(), turn: new THREE.Quaternion(), way: new THREE.Vector3(), scale: new THREE.Vector3(), up: new THREE.Vector3(0, 1, 0), point: new THREE.Vector3(), tint: new THREE.Color(), white: new THREE.Color(1, 1, 1) };
  }

  /**
   * Each lane's share of the fullest rate, or its way, changed: the streams' widths and the way their streaks run
   * follow. A lane with no rate is not drawn.
   */
  setShares() {
    if (!this.widths) return;
    const per = ALONG * ROUND, widths = this.widths.array, ways = this.ways.array;
    this.lanes.forEach((lane, k) => {
      widths.fill(lane.perSecond > 0 ? widthOf(lane.share ?? 1) : 0, k * per, (k + 1) * per);
      ways.fill(lane.reverse ? 1 : 0, k * per, (k + 1) * per);
    });
    this.widths.needsUpdate = true;
    this.ways.needsUpdate = true;
  }

  /** The lanes' colours changed (the page's theme): the streams take them in place; the chevrons take them as they are placed. */
  setColours() {
    if (!this.colours) return;
    const per = ALONG * ROUND, array = this.colours.array;
    this.lanes.forEach((lane, k) => {
      for (let at = k * per; at < (k + 1) * per; at++) array.set([lane.colour.r, lane.colour.g, lane.colour.b], at * 3);
    });
    this.colours.needsUpdate = true;
  }

  /** The fullest stream's radius changed (the layers' strength): the streams and the chevrons follow. */
  setRadius(radius) {
    this.radius = radius;
    if (this.streams) this.streams.material.uniforms.uRadius.value = radius;
  }

  /**
   * Run on by a stretch of watching time: the streaks run `pace` lane lengths a second, and the
   * chevrons move along with them (`chevronPace`: lane lengths a second, as the beads do slowed).
   * Where nothing may move, everything stands where it is.
   */
  tick(seconds, still, chevronPace = STREAK_PACE / 4, stream = 1) {
    if (!still) {
      this.time += seconds * STREAK_PACE;
      this.travel = (this.travel + seconds * chevronPace) % 1;
      // Chevrons painted in a stream run as its streaks do at true speed, and with the beads slowed, without a jump between.
      this.moved = (this.moved + seconds * (chevronPace + (STREAK_PACE - chevronPace) * Math.min(1, Math.max(0, stream)))) % 1000;
    }
    if (this.streams) {
      this.streams.material.uniforms.uTime.value = this.time % 1000;
      this.streams.material.uniforms.uMove.value = this.moved;
    }
    this.placeChevrons();
    return !still && this.lanes.some((lane) => lane.perSecond > 0);
  }

  /** Each lane's chevrons, spread evenly along it at the place they have reached, pointing the way it flows, as large as its stream is wide and its room allows. */
  placeChevrons() {
    const mesh = this.chevrons;
    if (!mesh) return;
    const { matrix, turn, way, scale, up, point } = this.scratch;
    let at = 0;
    for (const lane of this.lanes) {
      if (!(lane.perSecond > 0)) continue;
      const { size, count } = chevronFit({ length: lane.length, gap: lane.gap, size: this.radius * 2.6 * widthOf(lane.share ?? 1), most: this.most });
      const samples = lane.samples;
      for (let k = 0; k < count; k++) {
        const share = ((k + 0.5) / count + this.travel) % 1;
        const along = lane.reverse ? 1 - share : share;
        // Between the lane's two points either side, as the tube is drawn; pointing the way it flows along that stretch.
        const at_ = along * (ALONG - 1), i = Math.min(ALONG - 2, Math.floor(at_)), f = at_ - i;
        point.lerpVectors(samples[i], samples[i + 1], f);
        way.subVectors(samples[i + 1], samples[i]);
        if (lane.reverse) way.negate();
        if (way.lengthSq() < 1e-18) way.copy(up);
        turn.setFromUnitVectors(up, way.normalize());
        mesh.setMatrixAt(at, matrix.compose(point, turn, scale.setScalar(size)));
        mesh.setColorAt(at, this.scratch.tint.copy(lane.colour).lerp(this.scratch.white, TINT));
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
      if (material.userData.chevrons) material.uniforms.uOpacity.value = opacity * this.see;
      else if (material.uniforms) material.uniforms.uOpacity.value = stream;
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
