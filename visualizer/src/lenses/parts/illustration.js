import * as THREE from "../../three.js";
import { makeStudio } from "../../core/environment.js";

/** A sampled sheet, optionally painted at the same positions as its relief. */
export function sheet(rows, columns, at, paint) {
  const vertices = [], colors = [], indices = [];
  const color = new THREE.Color();
  for (let row = 0; row <= rows; row++) {
    for (let col = 0; col <= columns; col++) {
      const t = row / rows, u = col / columns, p = at(t, u);
      vertices.push(p.x, p.y, p.z);
      if (paint) {
        paint(color, t, u, p);
        colors.push(color.r, color.g, color.b);
      }
      if (row === rows || col === columns) continue;
      const a = row * (columns + 1) + col, b = a + columns + 1;
      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setIndex(indices);
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  if (paint) geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  return geometry;
}

export const point = (x, y, z) => new THREE.Vector3(x, y, z);
export const turn = 2 * Math.PI;

/** The soft studio reflections used by the Cell view, with a directional key
 * to give the shallow relief visible depth. */
export function lightSpecimen(lens) {
  const {stage} = lens;
  if (!stage.renderer) return;
  const studio = stage.look?.on("reflections") ? (lens.studio ??= makeStudio(stage.renderer)) : null;
  stage.scene.environment = studio;
  stage.scene.environmentIntensity = stage.palette.dark ? .64 : .72;
  stage.sky.intensity = stage.palette.dark ? .89 : 1.08;
  stage.sun.intensity = stage.palette.dark ? 1.65 : 1.42;
}
