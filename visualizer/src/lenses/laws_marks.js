// The Laws library's own marks: the names written on the room itself (family plaques, shelf
// names, the rows of a frame, the revision the list was read at), and the light that runs
// along a chosen piece's routes. Kept apart from the view so the tests can read them.

import * as THREE from "../three.js";

/** The plank each column stands on: its height and depth, in the scene's units. */
export const PLANK = { h: 0.3, d: 0.5 };
/** The wall's foot rail, from the wall's foot and its glass: the revision is written on its front. */
export const FOOT = { y: 0.05, h: 0.46, z: 0.12, d: 0.62 };
/** The plinth: how far it reaches past the room on each side, where it stands and how thick it is. */
export const PLINTH = { x: 1.5, z: 1.2, y: -0.36, h: 0.34, bevel: 0.06 };

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
/** "2026-11-16" as "16 November 2026". */
export function longDate(iso) {
  const [year, month, day] = String(iso || "").split("-").map(Number);
  return year && month && day ? `${day} ${MONTHS[month - 1]} ${year}` : String(iso || "");
}

/**
 * Every name the room carries, in the scene's units: { text, x, y, z, h, align, tone, kind }.
 * A name written on a plank cannot lose its place to a neighbour's label, as the page's labels
 * did. `h` is the height of the letters' em; `tone` is "strong" or "soft".
 */
export function plaquesOf(library, layout) {
  const out = [];
  const narrow = layout.narrow;
  // A name is written on the front of the plank its column stands on.
  const z = (layout.bars[0]?.z ?? -3) + PLANK.d / 2 + 0.006;
  for (const head of layout.heads) out.push({ text: head.family.short, x: head.x, y: head.y, z, h: 0.26, align: "center", tone: "strong", kind: "family", family: head.family.id });
  // A shelf of several families has a name of its own, on the glass under its planks; a shelf of one is named by its family alone.
  const shelves = new Map();
  for (const head of layout.heads) {
    const key = `${head.shelf}:${head.band}`;
    if (!shelves.has(key)) shelves.set(key, []);
    shelves.get(key).push(head);
  }
  for (const [key, group] of shelves) {
    if (group.length < 2) continue;
    const shelf = library.shelfById.get(key.split(":")[0]);
    out.push({ text: shelf?.label || key, x: (group[0].x + group.at(-1).x) / 2, y: group[0].y - 0.5, z: z - PLANK.d / 2 + 0.02, h: 0.24, align: "center", tone: "soft", kind: "shelf", shelf: shelf?.id });
  }
  for (const frame of layout.frames) {
    if (frame.kind !== "inner model") continue;
    for (const row of frame.rows) {
      out.push({ text: row.label, x: row.x, y: row.y, z: frame.z + 0.1, h: 0.2, align: "left", tone: "soft", kind: "row" });
      // The row's next free registry code, written in its empty socket: a number free, not a piece.
      if (row.next) out.push({ text: `${row.next.code} free`, x: row.next.x, y: row.next.y, z: frame.z + 0.012, h: 0.19, align: "center", tone: "soft", kind: "next" });
    }
  }
  // The revision the list was read at, on the front of the wall's foot rail.
  const stamp = library.stamp.main;
  const read = `Read from the engine's code at main ${stamp.revision} (committed ${longDate(stamp.date)})${narrow ? "" : ". No level is shown that a record does not state."}`;
  out.push({ text: read, x: layout.wall.x, y: layout.wall.y + FOOT.y, z: layout.wall.z + FOOT.z + FOOT.d / 2 + 0.006, h: narrow ? 0.22 : 0.24, align: "center", tone: "soft", kind: "revision" });
  // The older families, on the front face of the plinth their strip stands on.
  if (layout.older.length) {
    out.push({ text: `${layout.older.length} older model families: their laws are tables inside each family`, x: 0, y: PLINTH.y + PLINTH.h / 2, z: layout.bounds.maxZ + PLINTH.z + PLINTH.bevel + 0.01, h: 0.18, align: "center", tone: "soft", kind: "older" });
  }
  return out;
}

/** The plaques as one mesh over one texture: a draw for all of them. Null where no canvas can be made (a test). */
export function plaqueMesh(plaques, palette) {
  if (typeof document === "undefined" || !plaques.length) return null;
  const size = 64, pad = 12, width = 4096;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return null;
  const font = (tone) => `${tone === "strong" ? 650 : 520} ${size}px Inter, "Segoe UI", system-ui, sans-serif`;
  // Pack the texts in rows of the texture; a text too long for a row is drawn smaller, keeping its size in the room.
  let x = 0, y = 0;
  const places = plaques.map((plaque) => {
    context.font = font(plaque.tone);
    const measured = context.measureText(plaque.text).width;
    const fit = Math.min(size, Math.floor((size * (width - pad * 2)) / Math.max(1, measured)));
    const w = Math.ceil((measured * fit) / size) + pad * 2;
    if (x + w > width) { x = 0; y += size + pad * 2; }
    const place = { x, y, w, h: size + pad * 2, fit };
    x += w;
    return place;
  });
  canvas.width = width;
  canvas.height = THREE.MathUtils.ceilPowerOfTwo(y + size + pad * 2);
  context.textBaseline = "middle";
  plaques.forEach((plaque, index) => {
    const place = places[index];
    context.font = font(plaque.tone).replace(`${size}px`, `${place.fit}px`);
    context.fillStyle = plaque.tone === "strong" ? palette.fg || "#12283a" : palette.muted || palette.edge || "#566878";
    context.fillText(plaque.text, place.x + pad, place.y + place.h / 2 + 2);
  });
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  const positions = [], uvs = [], index = [];
  plaques.forEach((plaque, n) => {
    const place = places[n];
    const h = plaque.h * (place.h / place.fit) * 1.05, w = h * (place.w / place.h);
    const left = plaque.align === "left" ? plaque.x : plaque.align === "right" ? plaque.x - w : plaque.x - w / 2;
    const u0 = place.x / canvas.width, u1 = (place.x + place.w) / canvas.width;
    const v0 = 1 - (place.y + place.h) / canvas.height, v1 = 1 - place.y / canvas.height;
    const corners = [[left, plaque.y - h / 2, plaque.z], [left + w, plaque.y - h / 2, plaque.z], [left + w, plaque.y + h / 2, plaque.z], [left, plaque.y + h / 2, plaque.z]];
    const base = positions.length / 3;
    for (const corner of corners) positions.push(...corner);
    uvs.push(u0, v0, u1, v0, u1, v1, u0, v1);
    index.push(base, base + 1, base + 2, base, base + 2, base + 3);
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(index);
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
  material.userData.noContact = true;
  const mesh = new THREE.Mesh(geometry, material);
  mesh.userData.unpickable = true;
  mesh.renderOrder = 3;
  return mesh;
}

/**
 * The routes' light: a tube that glows in the accent, with a brighter head that runs from the
 * chosen piece toward each slot that declares it (uv.x runs along every tube from its piece to
 * its slot). `grown` draws a route only so far; `pulse` is 0 for a steady glow and 1 while the
 * light runs, and eases between. It carries a meaning, so it stays out of filmic light and contact shade.
 */
export function routeMaterial() {
  const material = new THREE.ShaderMaterial({
    uniforms: { colour: { value: new THREE.Color(0x1f6fd0) }, time: { value: 0 }, pulse: { value: 0 }, grown: { value: 1 } },
    vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: [
      "uniform vec3 colour; uniform float time; uniform float pulse; uniform float grown; varying vec2 vUv;",
      "void main() {",
      "  if (vUv.x > grown) discard;",
      "  float d = vUv.x - fract(time);",
      "  float head = d < 0.0 ? exp(d * 7.0) : exp(-d * 55.0);",
      "  float glow = mix(1.0, 0.7 + 0.8 * head, pulse);",
      "  gl_FragColor = vec4(colour * glow, 1.0);",
      "  #include <colorspace_fragment>",
      "}",
    ].join("\n"),
    toneMapped: false,
  });
  material.userData.noContact = true;
  return material;
}

/** Many tubes as one geometry: one draw for every route, each keeping its own uv along it. */
export function mergeTubes(curves, radius, segments = 40) {
  const position = [], normal = [], uv = [], index = [];
  for (const curve of curves) {
    const tube = new THREE.TubeGeometry(curve, segments, radius, 7, false);
    const base = position.length / 3;
    position.push(...tube.attributes.position.array);
    normal.push(...tube.attributes.normal.array);
    uv.push(...tube.attributes.uv.array);
    for (const value of tube.index.array) index.push(base + value);
    tube.dispose();
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normal, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  geometry.setIndex(index);
  return geometry;
}

/**
 * The camera's view that frames a box of the scene, seen from a given side: the box's corners
 * all inside the picture, with a margin, and the box centred (by a few steps of projection).
 */
export function fitView(box, { fov = 34, aspect = 1.6, azimuth = 0.16, polar = 1.42, margin = 0.06 } = {}) {
  const camera = new THREE.PerspectiveCamera(fov, aspect, 0.1, 10000);
  const target = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  let distance = (Math.max(size.x / aspect, size.y) / 2 / Math.tan((fov * Math.PI) / 360)) * 1.3 + size.z;
  const corners = [];
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) corners.push(new THREE.Vector3(x, y, z));
  const point = new THREE.Vector3(), right = new THREE.Vector3(), up = new THREE.Vector3();
  for (let step = 0; step < 6; step++) {
    const sin = Math.sin(polar);
    camera.position.set(target.x + distance * sin * Math.sin(azimuth), target.y + distance * Math.cos(polar), target.z + distance * sin * Math.cos(azimuth));
    camera.lookAt(target);
    camera.updateMatrixWorld();
    camera.updateProjectionMatrix();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const corner of corners) {
      point.copy(corner).project(camera);
      minX = Math.min(minX, point.x); maxX = Math.max(maxX, point.x); minY = Math.min(minY, point.y); maxY = Math.max(maxY, point.y);
    }
    const halfH = distance * Math.tan((fov * Math.PI) / 360), halfW = halfH * aspect;
    right.setFromMatrixColumn(camera.matrixWorld, 0);
    up.setFromMatrixColumn(camera.matrixWorld, 1);
    target.addScaledVector(right, ((minX + maxX) / 2) * halfW).addScaledVector(up, ((minY + maxY) / 2) * halfH);
    distance *= Math.max((maxX - minX) / 2, (maxY - minY) / 2) / (1 - margin);
  }
  return { target, distance, azimuth, polar };
}
