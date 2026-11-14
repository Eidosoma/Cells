// How a status looks. The same rules serve every lens:
//   built parts are solid, parts not built are ghosts, a failed part carries a cross,
//   and colour repeats what the form already says (see the legend).

import * as THREE from "../three.js";
import { statusToken } from "./theme.js";

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
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 96;
  const context = canvas.getContext("2d");
  context.font = "600 68px system-ui, sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillStyle = colour;
  context.fillText(text, 48, 52);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }));
  sprite.scale.setScalar(size);
  return sprite;
}
