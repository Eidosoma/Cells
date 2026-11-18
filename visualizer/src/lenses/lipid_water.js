// The water the assembly view stands in (src/lenses/lineage.js): a scene at the scale of molecules.
// Everything here is the picture's own and nothing of it is the run's: the water's depth and haze,
// the soft light from above with its moving caustics, the shafts of light and the specks that drift
// in it. No law of Cells computes any of it. It is drawn by shaders alone, with no picture made on
// the card and none downloaded, so a lost context that comes back needs nothing made again: three.js
// sends its programs and buffers again by itself.
//
// One clock moves it: the stage's clock of decoration (core/look.js), which stands still when the
// visitor asks for less motion and while another part of the page holds it. Each frame's place of
// every speck is a function of that clock alone.
//
// What it gives the materials of the view: `wetten(material, water, options)` adds the caustics
// that fall from above, a soft rim of the water's light, the shade deep inside an assembly, and,
// for the tails, a flex that moves with the same clock.

import * as THREE from "../three.js";

/** The water's colours in each theme: its surface light, its middle (the haze far things fade into), its depth, its shafts and specks. */
export const WATER_THEMES = {
  light: { top: "#f4fcfc", mid: "#cfe9ec", deep: "#5f9fb3", shaft: "#ffffff", mote: "#ffffff", rim: "#e4f6f8", caustic: "#fff8e0" },
  dark: { top: "#2f6f90", mid: "#0d2a3c", deep: "#02080f", shaft: "#7cc4e4", mote: "#a9dcf0", rim: "#4aa3c9", caustic: "#c4ecff" },
};
/**
 * The haze: nothing nearer than what the camera looks at is hazed, so the run's molecules keep their
 * colours as the legend shows them; beyond it, things fade into the water by this much a unit.
 */
export const HAZE = { assembly: 0.16, molecules: 0.035, population: 0.05, lineage: 0.03 };
/** The caustics' scale, in cells a unit: small on the molecules, wide on the plate. */
const CAUSTIC_SCALE = { assembly: 3.1, molecules: 0.5, population: 0.5, lineage: 0.45 };
/** Specks drawn in the water, wide and on a phone. */
export const MOTES = { wide: 640, narrow: 220 };
const SHAFTS = 6;

/**
 * The caustics: a bright web of light, as the surface's waves focus the light from above, moving
 * slowly. Two layers of moving cells; the light lies along the edges between cells. Written for
 * this view (a cellular noise, with a hash of sines). `causticsAt(p, t)` is about 0 to 1.
 */
export const CAUSTICS_GLSL = /* glsl */ `
vec2 wetHash(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return fract(sin(p) * 43758.5453);
}
float wetEdges(vec2 p, float t) {
  vec2 cell = floor(p), f = fract(p);
  float near = 8.0, next = 8.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 g = vec2(float(x), float(y));
      vec2 o = wetHash(cell + g);
      o = 0.5 + 0.42 * sin(t * 0.55 + 6.2831 * o);
      vec2 r = g + o - f;
      float d = dot(r, r);
      if (d < near) { next = near; near = d; } else if (d < next) { next = d; }
    }
  }
  return sqrt(next) - sqrt(near);
}
float causticsAt(vec2 p, float t) {
  float a = 1.0 - smoothstep(0.0, 0.16, wetEdges(p, t));
  float b = 1.0 - smoothstep(0.0, 0.13, wetEdges(p * 1.63 + vec2(3.1, 7.7), t * 1.27));
  return clamp(a * a * 0.75 + b * b * 0.5, 0.0, 1.2);
}
`;

const DOME_VERTEX = /* glsl */ `
varying vec3 vDir;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vDir = world.xyz - cameraPosition;
  gl_Position = projectionMatrix * viewMatrix * world;
  gl_Position.z = gl_Position.w * 0.99999;
}`;

const DOME_FRAGMENT = /* glsl */ `
uniform vec3 uTop, uMid, uDeep, uShaft;
uniform float uTime, uShafts;
varying vec3 vDir;
void main() {
  vec3 d = normalize(vDir);
  float y = d.y;
  vec3 colour = mix(uDeep, uMid, smoothstep(-0.85, 0.05, y));
  colour = mix(colour, uTop, smoothstep(0.05, 0.92, y));
  // The window of the sky overhead, as seen from under water.
  colour = mix(colour, uTop * 1.08, smoothstep(0.86, 0.985, y) * 0.8);
  // Shafts of light: bands round the vertical, which meet overhead and fade into the depth.
  float a = atan(d.z, d.x);
  float s = pow(0.5 + 0.5 * sin(a * 7.0 + uTime * 0.045 + 1.3 * sin(a * 3.0 + uTime * 0.02)), 7.0);
  s += 0.6 * pow(0.5 + 0.5 * sin(a * 13.0 - uTime * 0.035 + 1.7), 9.0);
  s += 0.35 * pow(0.5 + 0.5 * sin(a * 23.0 + uTime * 0.06 + 0.4), 12.0);
  float band = smoothstep(-0.45, 0.45, y) * (1.0 - smoothstep(0.7, 0.97, y));
  colour += uShaft * s * band * uShafts;
  gl_FragColor = vec4(colour, 1.0);
  #include <colorspace_fragment>
}`;

const SHAFT_VERTEX = /* glsl */ `
attribute vec2 aShaft;
varying vec2 vUv;
varying float vFlicker;
varying float vNear;
uniform float uTime;
void main() {
  vUv = uv;
  vFlicker = 0.6 + 0.4 * sin(uTime * (0.21 + 0.07 * aShaft.x) + aShaft.y * 6.2831);
  vec4 world = modelMatrix * instanceMatrix * vec4(position, 1.0);
  vNear = clamp(length(world.xyz - cameraPosition) / 4.0, 0.0, 1.0);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const SHAFT_FRAGMENT = /* glsl */ `
uniform vec3 uShaft;
uniform float uStrength;
varying vec2 vUv;
varying float vFlicker;
varying float vNear;
void main() {
  float across = 1.0 - abs(vUv.x * 2.0 - 1.0);
  float profile = across * across * (3.0 - 2.0 * across);
  float fall = smoothstep(0.0, 0.85, vUv.y) * (1.0 - smoothstep(0.92, 1.0, vUv.y));
  float alpha = profile * fall * vFlicker * uStrength * vNear;
  gl_FragColor = vec4(uShaft * alpha, alpha);
  #include <colorspace_fragment>
}`;

const MOTE_VERTEX = /* glsl */ `
attribute vec4 aSeed;
uniform float uTime, uSize, uScale;
uniform vec3 uCentre, uBox;
varying float vAlpha;
void main() {
  // Each speck's place is a function of the clock alone: a slow drift, folded back into a box round the view's middle.
  vec3 drift = vec3(sin(uTime * 0.09 + aSeed.x * 40.0) * 0.6, -uTime * (0.025 + 0.03 * aSeed.w), cos(uTime * 0.07 + aSeed.y * 40.0) * 0.6);
  vec3 p = mod(aSeed.xyz * uBox + drift + uBox * 0.5, uBox) - uBox * 0.5 + uCentre;
  vec4 view = viewMatrix * vec4(p, 1.0);
  float depth = -view.z;
  gl_Position = projectionMatrix * view;
  gl_PointSize = uSize * (0.35 + aSeed.w) * uScale / max(depth, 0.5);
  // Near specks would be blots across the picture, and far ones fade into the haze.
  vAlpha = smoothstep(1.2, 3.5, depth) * (1.0 - smoothstep(14.0, 40.0, depth)) * (0.35 + 0.65 * aSeed.w);
}`;

const MOTE_FRAGMENT = /* glsl */ `
uniform vec3 uMote;
uniform float uAlpha;
varying float vAlpha;
void main() {
  float r = length(gl_PointCoord - 0.5) * 2.0;
  float a = (1.0 - smoothstep(0.15, 1.0, r)) * vAlpha * uAlpha;
  if (a < 0.004) discard;
  gl_FragColor = vec4(uMote * a, a);
  #include <colorspace_fragment>
}`;

/** A small stream of numbers that is the same everywhere. */
function stream(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The water: its dome, its shafts of light, its specks and its haze. One of each, made once. */
export class Water {
  constructor({ narrow = false } = {}) {
    this.group = new THREE.Group();
    this.group.userData.unpickable = true;
    this.uniforms = {
      time: { value: 0 },
      top: { value: new THREE.Color() }, mid: { value: new THREE.Color() }, deep: { value: new THREE.Color() },
      shaft: { value: new THREE.Color() }, mote: { value: new THREE.Color() },
      rim: { value: new THREE.Color() }, caustic: { value: new THREE.Color() },
      shafts: { value: 0.12 }, causticScale: { value: 1.1 }, causticStrength: { value: 0.6 },
      hazeNear: { value: 6 }, hazeDensity: { value: HAZE.assembly },
    };
    const u = this.uniforms;
    // The dome: as far as the haze lets one see, whichever way one looks.
    this.dome = new THREE.Mesh(
      new THREE.SphereGeometry(1, 48, 24),
      new THREE.ShaderMaterial({ uniforms: { uTop: u.top, uMid: u.mid, uDeep: u.deep, uShaft: u.shaft, uTime: u.time, uShafts: u.shafts }, vertexShader: DOME_VERTEX, fragmentShader: DOME_FRAGMENT, side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false, toneMapped: false })
    );
    this.dome.scale.setScalar(400);
    this.dome.renderOrder = -10;
    this.dome.frustumCulled = false;
    this.dome.onBeforeRender = (renderer, scene, camera) => {
      this.dome.position.copy(camera.position);
      this.dome.updateMatrixWorld();
    };
    // Shafts of light from above, in front of the dome: tall soft planes that turn to face the camera.
    const plane = new THREE.PlaneGeometry(1, 1, 1, 1).translate(0, 0.5, 0);
    plane.setAttribute("aShaft", new THREE.InstancedBufferAttribute(new Float32Array(SHAFTS * 2), 2));
    this.shaftUniforms = { uShaft: u.shaft, uTime: u.time, uStrength: { value: 0.16 } };
    this.shafts = new THREE.InstancedMesh(plane, new THREE.ShaderMaterial({ uniforms: this.shaftUniforms, vertexShader: SHAFT_VERTEX, fragmentShader: SHAFT_FRAGMENT, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, side: THREE.DoubleSide, toneMapped: false }), SHAFTS);
    this.shafts.frustumCulled = false;
    this.shafts.renderOrder = 5;
    const random = stream(611);
    this.shaftPlaces = [];
    for (let s = 0; s < SHAFTS; s++) {
      plane.attributes.aShaft.setXY(s, random(), random());
      this.shaftPlaces.push({ x: (random() - 0.5) * 14, z: -2 - random() * 7, width: 0.9 + random() * 1.8, lean: (random() - 0.5) * 0.35 });
    }
    // The specks: a fixed set of seeds, drawn as soft points.
    this.moteCount = MOTES.wide;
    const seeds = new Float32Array(MOTES.wide * 4);
    for (let i = 0; i < seeds.length; i++) seeds[i] = random();
    const motes = new THREE.BufferGeometry();
    motes.setAttribute("position", new THREE.BufferAttribute(new Float32Array(MOTES.wide * 3), 3));
    motes.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 4));
    this.moteUniforms = { uTime: u.time, uMote: u.mote, uSize: { value: 0.05 }, uScale: { value: 900 }, uAlpha: { value: 0.5 }, uCentre: { value: new THREE.Vector3() }, uBox: { value: new THREE.Vector3(26, 16, 26) } };
    this.motes = new THREE.Points(motes, new THREE.ShaderMaterial({ uniforms: this.moteUniforms, vertexShader: MOTE_VERTEX, fragmentShader: MOTE_FRAGMENT, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, toneMapped: false }));
    this.motes.frustumCulled = false;
    this.motes.renderOrder = 6;
    this.group.add(this.dome, this.shafts, this.motes);
    for (const object of [this.dome, this.shafts, this.motes]) {
      object.userData.unpickable = true;
      object.material.userData.noContact = true;
    }
    this.centre = new THREE.Vector3();
    this.setNarrow(narrow);
    this.setTheme(false);
    this.placeShafts();
  }

  /** On a phone: fewer specks. */
  setNarrow(narrow) {
    this.narrow = Boolean(narrow);
    this.moteCount = this.narrow ? MOTES.narrow : MOTES.wide;
    this.motes.geometry.setDrawRange(0, this.moteCount);
  }

  setTheme(dark) {
    this.dark = Boolean(dark);
    const theme = WATER_THEMES[this.dark ? "dark" : "light"];
    for (const key of ["top", "mid", "deep", "shaft", "mote", "rim", "caustic"]) this.uniforms[key].value.set(theme[key]);
    this.uniforms.shafts.value = this.dark ? 0.22 : 0.16;
    this.shaftUniforms.uStrength.value = this.dark ? 0.14 : 0.32;
    this.moteUniforms.uAlpha.value = this.dark ? 0.6 : 0.85;
    this.uniforms.causticStrength.value = this.dark ? 0.7 : 0.55;
  }

  /** How thick the haze is, and how fine the caustics: by the level shown. */
  setLevel(level) {
    this.uniforms.hazeDensity.value = HAZE[level] ?? HAZE.assembly;
    this.uniforms.causticScale.value = CAUSTIC_SCALE[level] ?? CAUSTIC_SCALE.assembly;
  }

  /** Nothing nearer the camera than this is hazed: what it looks at stays as its legend shows it. */
  setHazeNear(distance) {
    this.uniforms.hazeNear.value = Math.max(0, distance);
  }

  /** Where the water's specks and shafts gather: round what the camera looks at. */
  setCentre(point) {
    this.centre.copy(point);
    this.moteUniforms.uCentre.value.copy(point);
    this.placeShafts();
  }

  placeShafts() {
    const dummy = new THREE.Object3D();
    this.shaftPlaces.forEach((place, index) => {
      dummy.position.set(this.centre.x + place.x, this.centre.y - 6, this.centre.z + place.z);
      dummy.rotation.set(0, 0, place.lean);
      dummy.scale.set(place.width, 22, 1);
      dummy.updateMatrix();
      this.shafts.setMatrixAt(index, dummy.matrix);
    });
    this.shafts.instanceMatrix.needsUpdate = true;
  }

  /** The shafts turn to face the camera (about the vertical only). */
  face(camera) {
    if (!camera) return;
    const dummy = this._dummy || (this._dummy = new THREE.Object3D());
    this.shaftPlaces.forEach((place, index) => {
      dummy.position.set(this.centre.x + place.x, this.centre.y - 6, this.centre.z + place.z);
      dummy.rotation.set(0, Math.atan2(camera.position.x - dummy.position.x, camera.position.z - dummy.position.z), place.lean, "YXZ");
      dummy.scale.set(place.width, 22, 1);
      dummy.updateMatrix();
      this.shafts.setMatrixAt(index, dummy.matrix);
    });
    this.shafts.instanceMatrix.needsUpdate = true;
  }

  /** The water's clock, in seconds of decoration. */
  setTime(seconds) {
    this.uniforms.time.value = seconds;
  }

  /** The pixel scale specks are drawn at (they keep their size in the scene). */
  setViewport(height, pixelRatio = 1) {
    this.moteUniforms.uScale.value = Math.max(300, height * pixelRatio);
  }

  attach(scene) {
    if (this.attached) return;
    scene.add(this.group);
    this.attached = scene;
  }

  detach(scene = this.attached) {
    if (!this.attached || !scene) return;
    scene.remove(this.group);
    this.attached = null;
  }

  dispose() {
    for (const object of [this.dome, this.shafts, this.motes]) {
      object.geometry.dispose();
      object.material.dispose();
    }
  }
}

/**
 * Make a lit material wet in the water: caustics from above, a soft rim of the water's light and,
 * where `cores` is given, the shade deep inside an assembly. `flex` bends the geometry with the
 * water's clock along its length (a tail: from 0 at its head, y = 0, to 1 at its tip, y = -1),
 * by each instance's `aFlex` (its phase, and how much it bends). Marks the material wet, so the
 * view leaves it in the haze.
 */
export function wetten(material, water, { caustics = 1, rim = 0.35, rimPower = 2.6, flex = false, cores = null, deep = 0.5, ghost = false } = {}) {
  const u = water.uniforms;
  const own = {
    uWetTime: u.time, uCausticColour: u.caustic, uCausticScale: u.causticScale, uCausticStrength: u.causticStrength, uRimColour: u.rim,
    uCaustics: { value: caustics }, uRim: { value: rim }, uRimPower: { value: rimPower }, uDeep: { value: deep },
    uCores: { value: cores || [0, 1, 2, 3].map(() => new THREE.Vector4(0, 0, 0, 0)) },
    uHazeColour: u.mid, uHazeNear: u.hazeNear, uHazeDensity: u.hazeDensity,
  };
  // The view's own haze stands in for three.js's fog, so that what the camera looks at is never hazed.
  material.fog = false;
  material.userData.wet = true;
  material.userData.noContact = true;
  material.userData.wetUniforms = own;
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, own);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", `#include <common>\nvarying vec3 vWetPos;\nuniform float uWetTime;\n${flex ? "attribute vec2 aFlex;" : ""}${ghost ? "\nattribute float aGhost;\nvarying float vGhost;" : ""}`)
      .replace(
        "#include <begin_vertex>",
        flex
          ? `#include <begin_vertex>
  float wetU = clamp(-position.y, 0.0, 1.0);
  float wetBend = wetU * wetU * aFlex.y;
  transformed.x += wetBend * 0.16 * sin(uWetTime * 1.6 + aFlex.x + wetU * 2.8);
  transformed.z += wetBend * 0.16 * cos(uWetTime * 1.25 + aFlex.x * 1.7 + wetU * 2.2);`
          : "#include <begin_vertex>"
      )
      .replace("#include <begin_vertex>", ghost ? "#include <begin_vertex>\n  vGhost = aGhost;" : "#include <begin_vertex>")
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>
  vec4 wetWorld = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
    wetWorld = instanceMatrix * wetWorld;
  #endif
  vWetPos = (modelMatrix * wetWorld).xyz;`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
varying vec3 vWetPos;
uniform float uWetTime, uCausticScale, uCausticStrength, uCaustics, uRim, uRimPower, uDeep, uHazeNear, uHazeDensity;
uniform vec3 uCausticColour, uRimColour, uHazeColour;
uniform vec4 uCores[4];
${ghost ? "varying float vGhost;" : ""}
${CAUSTICS_GLSL}`
      )

      .replace(
        "#include <opaque_fragment>",
        `{
  vec3 wetN = normalize((vec4(normal, 0.0) * viewMatrix).xyz);
  float wetUp = clamp(wetN.y * 0.65 + 0.35, 0.0, 1.0);
  float wetLight = causticsAt(vWetPos.xz * uCausticScale + vec2(vWetPos.y * 0.21, -vWetPos.y * 0.17), uWetTime);
  // The light the waves focus falls on dark surfaces too: a share of it is added whatever the surface's colour.
  outgoingLight += (diffuseColor.rgb * 0.7 + 0.14) * uCausticColour * wetLight * uCausticStrength * uCaustics * wetUp;
  vec3 wetV = normalize(cameraPosition - vWetPos);
  float wetRim = pow(1.0 - clamp(dot(wetN, wetV), 0.0, 1.0), uRimPower);
  outgoingLight += uRimColour * wetRim * uRim;
  float wetDeep = 0.0;
  for (int c = 0; c < 4; c++) {
    if (uCores[c].w > 0.0) wetDeep = max(wetDeep, 1.0 - clamp(length(vWetPos - uCores[c].xyz) / uCores[c].w, 0.0, 1.0));
  }
  outgoingLight *= 1.0 - uDeep * wetDeep * wetDeep;
  float wetFar = max(0.0, length(vWetPos - cameraPosition) - uHazeNear) * uHazeDensity;
  outgoingLight = mix(outgoingLight, uHazeColour, 1.0 - exp(-wetFar * wetFar));
  ${ghost ? "diffuseColor.a *= 1.0 - vGhost; // a see-through part (the near side of a protocell, so that its inside shows): its own share less opaque" : ""}
}
#include <opaque_fragment>`
      );
  };
  material.customProgramCacheKey = () => `cells-wet-${flex ? 1 : 0}${ghost ? "-ghost" : ""}`;
  return material;
}
