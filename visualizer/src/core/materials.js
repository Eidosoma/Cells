// How a status looks. The same rules serve every lens:
//   built parts are solid, parts not built are ghosts, a failed part carries a cross,
//   and colour repeats what the form already says (see the legend).

import * as THREE from "../three.js";
import { statusToken } from "./theme.js";
import { paintedTexture } from "./painted.js";

export const STATUS_ORDER = ["qualified", "landed", "established", "failed", "designed", "planned", "external", null];

/** How each status is drawn: fill opacity, and the style of its outline. */
export const STATUS_FORM = {
  qualified: { fill: 1, outline: null },
  landed: { fill: 1, outline: null },
  established: { fill: 1, outline: null },
  failed: { fill: 1, outline: null, cross: true },
  designed: { fill: 0.3, outline: "solid" },
  planned: { fill: 0.07, outline: "dashed" },
  external: { fill: 1, outline: null },
  unstated: { fill: 1, outline: null },
};

export const formOf = (status) => STATUS_FORM[status || "unstated"];

/**
 * The materials for every status, in three strengths: normal, dimmed (when another
 * part is in focus) and outline. Colours are filled in by applyPalette.
 */
export class StatusMaterials {
  constructor() {
    this.sets = new Map();
    for (const status of Object.keys(STATUS_FORM)) {
      const form = STATUS_FORM[status];
      const solid = form.fill === 1;
      const fill = new THREE.MeshStandardMaterial({
        roughness: 0.68,
        metalness: 0,
        transparent: !solid,
        opacity: form.fill,
        depthWrite: solid,
      });
      const dim = new THREE.MeshStandardMaterial({
        roughness: 0.9,
        metalness: 0,
        transparent: true,
        opacity: solid ? 0.22 : form.fill * 0.5,
        depthWrite: false,
      });
      const line =
        form.outline === "dashed"
          ? new THREE.LineDashedMaterial({ dashSize: 0.34, gapSize: 0.22, transparent: true, opacity: 0.95 })
          : new THREE.LineBasicMaterial({ transparent: true, opacity: 0.95 });
      const lineDim = line.clone();
      lineDim.opacity = 0.22;
      this.sets.set(status, { fill, dim, line, lineDim });
    }
  }

  get(status) {
    return this.sets.get(status || "unstated");
  }

  applyPalette(palette) {
    for (const [status, set] of this.sets) {
      const colour = palette[statusToken(status === "unstated" ? null : status)];
      const outline = status === "planned" ? palette.ghost : colour;
      set.fill.color.set(colour);
      set.dim.color.set(colour);
      set.line.color.set(outline);
      set.lineDim.color.set(outline);
    }
  }

  dispose() {
    for (const set of this.sets.values()) for (const material of Object.values(set)) material.dispose();
  }
}

/** A slab with rounded corners: w along x, d along z, height 1 along y (scale it). */
export function roundedSlab(w, d, radius, bevel = 0.07) {
  const shape = new THREE.Shape();
  const x = -w / 2, z = -d / 2, r = Math.min(radius, w / 2, d / 2);
  shape.moveTo(x + r, z);
  shape.lineTo(x + w - r, z);
  shape.quadraticCurveTo(x + w, z, x + w, z + r);
  shape.lineTo(x + w, z + d - r);
  shape.quadraticCurveTo(x + w, z + d, x + w - r, z + d);
  shape.lineTo(x + r, z + d);
  shape.quadraticCurveTo(x, z + d, x, z + d - r);
  shape.lineTo(x, z + r);
  shape.quadraticCurveTo(x, z, x + r, z);
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: 1 - 2 * bevel,
    bevelEnabled: bevel > 0,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelSegments: 2,
    curveSegments: 6,
  });
  // Extrusion runs along +z; stand it up so height is +y, base at y = 0.
  geometry.rotateX(-Math.PI / 2);
  geometry.translate(0, bevel, 0);
  return geometry;
}

/** A smooth path between two points: an arc within a level, an S-curve between levels. */
export function linkCurve(from, to) {
  const rise = to.y - from.y;
  const span = Math.hypot(to.x - from.x, to.z - from.z);
  if (Math.abs(rise) < 0.5) {
    const lift = 1.1 + span * 0.16;
    const mid = from.clone().add(to).multiplyScalar(0.5);
    mid.y += lift * 2;
    return new THREE.QuadraticBezierCurve3(from, mid, to);
  }
  const pull = Math.abs(rise) * 0.45;
  const direction = Math.sign(rise);
  return new THREE.CubicBezierCurve3(
    from,
    new THREE.Vector3(from.x, from.y + direction * pull, from.z),
    new THREE.Vector3(to.x, to.y - direction * pull, to.z),
    to
  );
}

/** A small text sprite for marks drawn in the scene itself (charges, gate numbers). */
export function glyphSprite(text, colour, size = 1) {
  const texture = paintedTexture(96, 96, (context) => {
    context.font = "600 68px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = colour;
    context.fillText(text, 48, 52);
  });
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }));
  sprite.scale.setScalar(size);
  return sprite;
}

/**
 * Gives a standard material a soft rim: a little extra light where the surface turns
 * away from the viewer, and optionally more opacity there (glass). The uniform objects
 * exist from the start, so colours can be set before the shader is compiled.
 */
export function soften(material, { rim = 0.3, power = 2.4, alphaRim = 0 } = {}) {
  const uniforms = {
    uRimColor: { value: new THREE.Color(1, 1, 1) },
    uRimStrength: { value: rim },
    uRimPower: { value: power },
    uAlphaRim: { value: alphaRim },
  };
  material.userData.rim = uniforms;
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform vec3 uRimColor;\nuniform float uRimStrength;\nuniform float uRimPower;\nuniform float uAlphaRim;")
      .replace(
        "#include <opaque_fragment>",
        [
          "float rimTerm = pow(1.0 - clamp(abs(dot(normalize(vViewPosition), normal)), 0.0, 1.0), uRimPower);",
          "outgoingLight += uRimColor * rimTerm * uRimStrength;",
          "diffuseColor.a = clamp(diffuseColor.a + uAlphaRim * rimTerm, 0.0, 1.0);",
          "#include <opaque_fragment>",
        ].join("\n")
      );
  };
  material.customProgramCacheKey = () => "cells-soft-rim";
  return material;
}

// ------------------------------------------------------------------ the look at rest
// Three of the seven effects of the resting look are added to a material here
// (core/look.js; the user's choice of 15 November 2026): soft translucency, surface texture
// and membrane shimmer. A fourth, crowd drift, is `jostle` below. Each is switched by a
// number shared by every material (0 or 1), so one assignment turns it on or off for the
// whole scene, and with all at 0 a material is drawn exactly as `soften` draws it.
//
// Where the techniques come from: the translucency is the cheap one of Barré-Brisebois and
// Bouchard (GDC 2011: light let through where the eye looks toward a light, with the thin
// edge standing in for a thickness map); the relief is Mikkelsen's bump mapping of an
// unparametrised surface, as three.js's own bump map does it (MIT); the noise is plain
// value noise. Nothing is copied from a source that forbids it.

/** The numbers every enriched material shares. One set belongs to a stage. */
export function lookNumbers() {
  return { time: { value: 0 }, translucency: { value: 0 }, texture: { value: 0 }, shimmer: { value: 0 }, drift: { value: 0 } };
}

// The kinds of surface texture: each is detail that no data stands behind (scenery).
export const TEXTURES = ["grain", "folds", "pores"];

const LOOK_COMMON = /* glsl */ `
varying vec3 vLookPos;
uniform vec3 uRimColor;
uniform float uRimStrength;
uniform float uRimPower;
uniform float uAlphaRim;
uniform float uLookTime;
uniform float uLookTranslucency;
uniform float uLookTexture;
uniform float uLookShimmer;
uniform float uLookThin;
uniform float uLookUnit;
uniform vec3 uLookAxis;
float lookHash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float lookNoise(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(lookHash(i), lookHash(i + vec3(1.0, 0.0, 0.0)), f.x), mix(lookHash(i + vec3(0.0, 1.0, 0.0)), lookHash(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
             mix(mix(lookHash(i + vec3(0.0, 0.0, 1.0)), lookHash(i + vec3(1.0, 0.0, 1.0)), f.x), mix(lookHash(i + vec3(0.0, 1.0, 1.0)), lookHash(i + vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);
}
// How much of the part one pixel covers, in the part's own units; set once for each pixel.
float lookFoot = 0.0;
// A detail of this size fades away before a pixel grows as large as it is, so that a
// texture seen from afar, or on a surface turned edge-on, never breaks up into speckle.
float lookFade(float size) { return 1.0 - smoothstep(0.25 * size, 0.6 * size, lookFoot); }
#if LOOK_TEXTURE == 1
// Grain: the sheets of the endoplasmic reticulum, a little uneven.
#define LOOK_LEVEL (0.024 * (0.5 * lookFade(0.3) + 0.25 * lookFade(0.13)))
float lookHeight(vec3 p) { return 0.024 * (lookFade(0.3) * lookNoise(p * 3.2) + 0.5 * lookFade(0.13) * lookNoise(p * 7.5)); }
#elif LOOK_TEXTURE == 2
// Folds: low ridges across the long way of a mitochondrion, a little uneven.
#define LOOK_LEVEL 0.0
float lookHeight(vec3 p) { return 0.032 * lookFade(0.7) * sin(dot(p, uLookAxis) * 8.5 + 1.7 * lookNoise(p * 1.6)) + 0.006 * lookFade(0.11) * (lookNoise(p * 9.0) - 0.5); }
#elif LOOK_TEXTURE == 3
// Pores: shallow pits scattered over the nucleus.
#define LOOK_LEVEL 0.0
float lookHeight(vec3 p) {
  vec3 q = p * 2.9, i = floor(q), f = fract(q);
  float near = 1.0;
  for (int x = 0; x <= 1; x++) for (int y = 0; y <= 1; y++) for (int z = 0; z <= 1; z++) {
    vec3 corner = vec3(float(x), float(y), float(z));
    vec3 pit = corner + 0.36 * (vec3(lookHash(i + corner), lookHash(i + corner + 13.1), lookHash(i + corner + 31.7)) - 0.5);
    near = min(near, distance(f, pit));
  }
  return -0.028 * lookFade(0.2) * smoothstep(0.3, 0.06, near);
}
#else
#define LOOK_LEVEL 0.0
float lookHeight(vec3 p) { return 0.0; }
#endif
#ifdef LOOK_SHIMMER
// A sheet that flickers in place: each point of a lattice rises and falls at its own slow
// pace, so nothing travels across the membrane as a wave would.
float lookFlick(vec3 p, float t) {
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  #define LOOK_BEAT(o) sin(t * (0.5 + 0.9 * lookHash(i + o + 5.3)) + 6.2832 * lookHash(i + o))
  return mix(mix(mix(LOOK_BEAT(vec3(0.0, 0.0, 0.0)), LOOK_BEAT(vec3(1.0, 0.0, 0.0)), f.x), mix(LOOK_BEAT(vec3(0.0, 1.0, 0.0)), LOOK_BEAT(vec3(1.0, 1.0, 0.0)), f.x), f.y),
             mix(mix(LOOK_BEAT(vec3(0.0, 0.0, 1.0)), LOOK_BEAT(vec3(1.0, 0.0, 1.0)), f.x), mix(LOOK_BEAT(vec3(0.0, 1.0, 1.0)), LOOK_BEAT(vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);
}
#endif
// How far the surface stands out at a place, in the part's own units.
float lookRelief(vec3 p) {
  float height = 0.0;
  #if LOOK_TEXTURE > 0
  height += uLookTexture * lookHeight(p);
  #endif
  #ifdef LOOK_SHIMMER
  height += uLookShimmer * 0.045 * lookFade(1.25) * lookFlick(p * 0.8, uLookTime);
  #endif
  return height;
}
`;

const LOOK_TINT = /* glsl */ `
lookFoot = length(fwidth(vLookPos));
#if LOOK_TEXTURE > 0
if (uLookTexture > 0.0) {
  // A little darker in the hollows and lighter on the rises, so the relief reads without any light on it.
  diffuseColor.rgb *= 1.0 + uLookTexture * 2.0 * (lookHeight(vLookPos) - LOOK_LEVEL);
}
#endif
`;

const LOOK_RELIEF = /* glsl */ `
{
  float lookOn = 0.0;
  #if LOOK_TEXTURE > 0
  lookOn += uLookTexture;
  #endif
  #ifdef LOOK_SHIMMER
  lookOn += uLookShimmer;
  #endif
  if (lookOn > 0.0) {
    // The surface's slope from the change of its relief across one pixel each way.
    float lookHere = lookRelief(vLookPos);
    vec2 lookRise = vec2(lookRelief(vLookPos + dFdx(vLookPos)) - lookHere, lookRelief(vLookPos + dFdy(vLookPos)) - lookHere) * uLookUnit;
    vec3 lookAcross = dFdx(-vViewPosition), lookDown = dFdy(-vViewPosition);
    vec3 lookR1 = cross(lookDown, normal), lookR2 = cross(normal, lookAcross);
    float lookDet = dot(lookAcross, lookR1) * faceDirection;
    if (abs(lookDet) > 0.0) normal = normalize(abs(lookDet) * normal - sign(lookDet) * (lookRise.x * lookR1 + lookRise.y * lookR2));
  }
}
`;

const LOOK_LIGHT = /* glsl */ `
vec3 lookEye = normalize(vViewPosition);
float rimTerm = pow(1.0 - clamp(abs(dot(lookEye, normal)), 0.0, 1.0), uRimPower);
outgoingLight += uRimColor * rimTerm * uRimStrength;
diffuseColor.a = clamp(diffuseColor.a + uAlphaRim * rimTerm, 0.0, 1.0);
#ifdef LOOK_THIN
if (uLookTranslucency > 0.0) {
  // Light let through: most where the eye looks toward a light through the part, and a
  // little at every thin edge. It takes the part's own colour, as light through soft matter does.
  float lookThrough = 0.0;
  #if NUM_DIR_LIGHTS > 0
  for (int lookLight = 0; lookLight < NUM_DIR_LIGHTS; lookLight++) {
    vec3 lookBent = normalize(directionalLights[lookLight].direction + normal * 0.4);
    lookThrough += pow(clamp(dot(lookEye, -lookBent), 0.0, 1.0), 2.5) * dot(directionalLights[lookLight].color, vec3(0.3333));
  }
  #endif
  outgoingLight += uLookTranslucency * uLookThin * diffuseColor.rgb * (0.42 * lookThrough + 0.2 * rimTerm);
}
#endif
`;

/**
 * As `soften`, with what the resting look adds. `numbers` is the stage's shared set
 * (lookNumbers). `thin` is how much light the part lets through (0 for none); `texture`
 * one of TEXTURES, with `axis` the long way of the part for "folds", in its own frame;
 * `shimmer` for a membrane; `unit` how large one of the part's units is in the scene.
 */
export function enrich(material, numbers, { rim = 0.3, power = 2.4, alphaRim = 0, thin = 0, texture = null, axis = null, shimmer = false, unit = 1 } = {}) {
  const kind = TEXTURES.indexOf(texture) + 1;
  const uniforms = {
    uRimColor: { value: new THREE.Color(1, 1, 1) },
    uRimStrength: { value: rim },
    uRimPower: { value: power },
    uAlphaRim: { value: alphaRim },
    uLookThin: { value: thin },
    uLookUnit: { value: unit },
    uLookAxis: { value: axis ? axis.clone().normalize() : new THREE.Vector3(0, 1, 0) },
    uLookTime: numbers.time,
    uLookTranslucency: numbers.translucency,
    uLookTexture: numbers.texture,
    uLookShimmer: numbers.shimmer,
  };
  material.userData.rim = uniforms;
  material.userData.look = { thin, texture: kind ? texture : null, shimmer: Boolean(shimmer) };
  const defines = `#define LOOK_TEXTURE ${kind}\n${thin > 0 ? "#define LOOK_THIN\n" : ""}${shimmer ? "#define LOOK_SHIMMER\n" : ""}`;
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader.replace("#include <common>", "#include <common>\nvarying vec3 vLookPos;").replace("#include <begin_vertex>", "#include <begin_vertex>\nvLookPos = position;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\n${defines}${LOOK_COMMON}`)
      .replace("#include <color_fragment>", `#include <color_fragment>\n${LOOK_TINT}`)
      .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>\n${LOOK_RELIEF}`)
      .replace("#include <opaque_fragment>", `${LOOK_LIGHT}\n#include <opaque_fragment>`);
  };
  material.customProgramCacheKey = () => `cells-look-${kind}${thin > 0 ? 1 : 0}${shimmer ? 1 : 0}`;
  return material;
}

// Two sines of unlike pace on each axis, set off by the place itself: bounded, and with a mean of nothing.
const LOOK_JOSTLE = /* glsl */ `
uniform float uLookTime;
uniform float uLookDrift;
uniform float uLookReach;
vec3 lookJostle(vec3 seed, float t) {
  return vec3(sin(t * 0.9 + seed.x * 50.0) + sin(t * 1.7 + seed.y * 31.0), sin(t * 1.1 + seed.y * 47.0) + sin(t * 1.9 + seed.z * 29.0), sin(t * 0.8 + seed.z * 43.0) + sin(t * 1.6 + seed.x * 37.0));
}
`;
// A copy of an instanced shape is set off by where the copy stands; a point by where it is.
const LOOK_JOSTLED = /* glsl */ `
#ifdef USE_INSTANCING
vec3 lookSeed = instanceMatrix[3].xyz;
#else
vec3 lookSeed = position;
#endif
if (uLookDrift > 0.0) transformed += uLookDrift * uLookReach * lookJostle(lookSeed, uLookTime);
`;

/**
 * Crowd drift: each point, or each copy of an instanced shape, jostles about its own place,
 * slowly and at random. Two sines of unlike pace on each axis, set off by the place itself:
 * the mean of the motion is nothing, so the crowd goes nowhere (decoration never moves
 * with a direction). `reach` is how far, in the object's own units. Works on a points
 * material and on a mesh material alike.
 */
export function jostle(material, numbers, { reach = 0.08 } = {}) {
  const uniforms = { uLookTime: numbers.time, uLookDrift: numbers.drift, uLookReach: { value: reach } };
  // A material that already has a hook of its own (a soft rim) keeps it: this one runs after it.
  const own = (name) => (Object.prototype.hasOwnProperty.call(material, name) ? material[name] : null);
  const before = own("onBeforeCompile"), key = own("customProgramCacheKey")?.call(material) ?? "";
  material.userData.jostle = uniforms;
  material.userData.noContact = true; // what drifts is drawn a little off its place: it takes no part in contact shade
  material.onBeforeCompile = (shader, renderer) => {
    before?.call(material, shader, renderer);
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>\n${LOOK_JOSTLE}`
      )
      .replace("#include <begin_vertex>", `#include <begin_vertex>\n${LOOK_JOSTLED}`);
  };
  material.customProgramCacheKey = () => `${key}|cells-jostle`;
  return material;
}
