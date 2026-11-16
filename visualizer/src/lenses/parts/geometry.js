// Small pieces of geometry the cell's builders share (cell_parts.js and the part modules in
// this folder): a repeatable stream of chance, copies of one shape, dots, flat fans and bands,
// and places picked at random on a surface. Moved here unchanged from cell_parts.js, so that
// every module draws them the same way.

import * as THREE from "../../three.js";

/** A small repeatable random source, so the cell looks the same on every load. */
export function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A direction at random, evenly over the sphere: two draws from the stream. */
export function unit(random) {
  const z = random() * 2 - 1, angle = random() * Math.PI * 2, r = Math.sqrt(1 - z * z);
  return new THREE.Vector3(r * Math.cos(angle), z, r * Math.sin(angle));
}

export const UP = new THREE.Vector3(0, 1, 0);
export const along = (direction) => new THREE.Quaternion().setFromUnitVectors(UP, direction.clone().normalize());
export const radial = (angle) => new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
export const turnY = (angle) => new THREE.Quaternion().setFromAxisAngle(UP, angle);

/** Many copies of one shape, each at a position, turned by a quaternion or along a direction. */
export function instanced(geometry, material, placements) {
  const mesh = new THREE.InstancedMesh(geometry, material, placements.length);
  const matrix = new THREE.Matrix4(), scale = new THREE.Vector3(), none = new THREE.Quaternion();
  placements.forEach((placement, index) => {
    scale.setScalar(placement.scale ?? 1);
    matrix.compose(placement.position, placement.turn ?? (placement.direction ? along(placement.direction) : none), scale);
    mesh.setMatrixAt(index, matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

/** Dots: how things too small to draw as shapes are shown. */
export function dots(points, material) {
  const geometry = new THREE.BufferGeometry();
  const flat = new Float32Array(points.length * 3);
  points.forEach((point, index) => point.toArray(flat, index * 3));
  geometry.setAttribute("position", new THREE.BufferAttribute(flat, 3));
  return new THREE.Points(geometry, material);
}

/** A flat ring-shaped arc standing as a wall: radius, arc length, thickness and height. */
export function arcWall(radius, start, span, thickness, height) {
  const geometry = new THREE.TorusGeometry(radius, thickness / 2, 8, Math.max(24, Math.round(span * 26)), span);
  geometry.scale(1, 1, height / thickness);
  const mesh = new THREE.Mesh(geometry);
  // Lay the arc flat (its plane becomes horizontal), then turn it to its start angle.
  mesh.quaternion.copy(turnY(-start)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2));
  return mesh;
}

/** A flat shape filling a closed loop of points that lie level, facing up. */
export function fan(points) {
  const centre = points.reduce((sum, point) => sum.add(point), new THREE.Vector3()).multiplyScalar(1 / points.length);
  const geometry = new THREE.BufferGeometry().setFromPoints([centre, ...points]);
  const index = [];
  for (let q = 0; q < points.length; q++) index.push(0, 1 + ((q + 1) % points.length), 1 + q);
  geometry.setIndex(index);
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(points.length + 1).fill([0, 1, 0]).flat(), 3));
  return geometry;
}

/** A flat band between two closed loops of as many points, facing up. */
export function band(inner, outer) {
  const count = inner.length;
  const geometry = new THREE.BufferGeometry().setFromPoints([...inner, ...outer]);
  const index = [];
  for (let q = 0; q < count; q++) {
    const next = (q + 1) % count;
    index.push(q, next, count + q, next, count + next, count + q);
  }
  geometry.setIndex(index);
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(count * 2).fill([0, 1, 0]).flat(), 3));
  return geometry;
}

/** Picks random places on a surface, evenly by area: each a position and the way the surface faces there. */
export function surfaceSampler(geometry) {
  const position = geometry.attributes.position, normal = geometry.attributes.normal, index = geometry.index;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const upTo = [];
  let total = 0;
  for (let start = 0; start < index.count; start += 3) {
    a.fromBufferAttribute(position, index.getX(start));
    b.fromBufferAttribute(position, index.getX(start + 1)).sub(a);
    c.fromBufferAttribute(position, index.getX(start + 2)).sub(a);
    total += b.cross(c).length() / 2;
    upTo.push(total);
  }
  const blend = (attribute, start, u, v) =>
    a.fromBufferAttribute(attribute, index.getX(start)).multiplyScalar(1 - u - v).addScaledVector(b.fromBufferAttribute(attribute, index.getX(start + 1)), u).addScaledVector(c.fromBufferAttribute(attribute, index.getX(start + 2)), v).clone();
  return (random) => {
    const pick = random() * total;
    let low = 0, high = upTo.length - 1;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (upTo[middle] < pick) low = middle + 1;
      else high = middle;
    }
    let u = random(), v = random();
    if (u + v > 1) [u, v] = [1 - u, 1 - v];
    return { position: blend(position, low * 3, u, v), direction: blend(normal, low * 3, u, v).normalize() };
  };
}
