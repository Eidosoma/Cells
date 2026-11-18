// A run's cells as the Experiments view draws them: each cell a flat prism of its polygon, its corners pulled a little
// towards its middle so that cells read as separate tiles, its side walls shaded by a fixed drawn light; and between
// two cells the run joins by a junction, a seam. One mesh holds every prism, unlit, so that a cell's colour is exactly
// the legend's (src/layers/marks/tint.js paints it, walls and all). The replay of one run (src/lenses/replay.js) and
// the tissue line (src/lenses/tissue_line.js) both draw their cells with it: one way of drawing a run's cells.

import * as THREE from "../three.js";

export const INSET = 0.055; // each cell is drawn a little small, so cells read as separate tiles
export const LIGHT = new THREE.Vector2(-0.55, 0.83).normalize(); // where the side walls' shading comes from

/**
 * The prisms and seams of a run's cells (its cell set's polygons), centred on the middle of their extent.
 * `pick(cellNumber)` names what a press on a cell picks. Returns { cells, geometry, mesh, seams, pitch, low, high,
 * extent, point, centre }: `cells` as the marks read them ({ face, ring, inset, centre, radius, height, top, start,
 * walls, shade }), `seams` null or { quads, geometry, mesh, record }, `point(vertex)` a vertex in the sheet's plane.
 */
export function buildCells(run, { pick = null } = {}) {
  const { vertices, faces } = run.sets.get("cell").geometry;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of vertices) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const point = (index) => [vertices[index][0] - cx, vertices[index][1] - cy];
  const extent = Math.max(maxX - minX, maxY - minY) / 2;

  // Each cell: its corners pulled a little towards its middle.
  let area = 0, corners = 0;
  const cells = faces.map((face) => {
    const ring = face.map(point);
    let mx = 0, my = 0, twice = 0;
    ring.forEach(([x, y], k) => {
      const [nx, ny] = ring[(k + 1) % ring.length];
      mx += x;
      my += y;
      twice += x * ny - nx * y;
    });
    mx /= ring.length;
    my /= ring.length;
    area += Math.abs(twice) / 2;
    corners += ring.length;
    const inset = ring.map(([x, y]) => [mx + (x - mx) * (1 - INSET), my + (y - my) * (1 - INSET)]);
    return { face, ring, inset, centre: [mx, my], radius: Math.sqrt(Math.abs(twice) / 2 / Math.PI), height: 0, top: new THREE.Vector3(mx, 0, my) };
  });
  const pitch = Math.sqrt(area / cells.length); // about one cell across

  // One mesh for all the prisms. Per cell: a top fan (centre + corners), then four vertices per side wall.
  const total = corners * 5 + cells.length;
  const positions = new Float32Array(total * 3), colours = new Float32Array(total * 3), index = [];
  const faceCell = [];
  let at = 0;
  for (const [number_, cell] of cells.entries()) {
    const n = cell.inset.length;
    cell.start = at;
    positions.set([cell.centre[0], 0, cell.centre[1]], at * 3);
    cell.inset.forEach(([x, y], k) => positions.set([x, 0, y], (at + 1 + k) * 3));
    for (let k = 0; k < n; k++) {
      index.push(at, at + 1 + ((k + 1) % n), at + 1 + k);
      faceCell.push(number_);
    }
    at += n + 1;
    cell.walls = at;
    cell.shade = [];
    for (let k = 0; k < n; k++) {
      const [ax, ay] = cell.inset[k], [bx, by] = cell.inset[(k + 1) % n];
      // top a, top b, bottom b, bottom a
      positions.set([ax, 0, ay, bx, 0, by, bx, 0, by, ax, 0, ay], at * 3);
      index.push(at, at + 1, at + 2, at, at + 2, at + 3);
      faceCell.push(number_, number_);
      // The wall's outward direction decides how dark it is: a fixed, drawn light.
      const out = new THREE.Vector2((ax + bx) / 2 - cell.centre[0], (ay + by) / 2 - cell.centre[1]).normalize();
      cell.shade.push(0.6 + 0.26 * Math.max(0, out.dot(LIGHT)));
      at += 4;
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  geometry.setIndex(index);
  geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), extent * 1.5 + 0.78 * pitch);
  // Unlit, so a cell's colour is exactly the legend's; the walls carry their own shading.
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
  mesh.frustumCulled = false;
  if (pick) mesh.userData.pick = (hit) => pick(faceCell[hit.faceIndex]);

  // Seams: the strip between two joined cells, darker the further their junctions have formed.
  const junctions = run.sets.get("junction");
  const abundance = run.records.get("junction_abundance");
  let seams = null;
  if (junctions?.geometry?.kind === "links" && junctions.geometry.between === "cell") {
    const quads = [];
    // The strip between two cells that do not touch: from one rim to the other along the line joining their middles, a third of a cell wide.
    const between = (one, other) => {
      let dx = other.centre[0] - one.centre[0], dy = other.centre[1] - one.centre[1];
      const apart = Math.hypot(dx, dy) || 1;
      dx /= apart;
      dy /= apart;
      const half = Math.min(one.radius, other.radius) * 0.3, nx = -dy * half, ny = dx * half;
      const a = [one.centre[0] + dx * one.radius, one.centre[1] + dy * one.radius], b = [other.centre[0] - dx * other.radius, other.centre[1] - dy * other.radius];
      return [[a[0] + nx, a[1] + ny], [a[0] - nx, a[1] - ny], [b[0] - nx, b[1] - ny], [b[0] + nx, b[1] + ny]];
    };
    junctions.geometry.ends.forEach(([a, b], link) => {
      const shared = cells[a].face.filter((vertex) => cells[b].face.includes(vertex));
      // Cells placed where the run's view prescribes them need not touch: the strip runs between their rims, on the line joining them.
      if (shared.length !== 2 && run.prescribed) return quads.push({ a, b, link, points: between(cells[a], cells[b]) });
      if (shared.length !== 2) return; // not neighbours in the drawing: nothing to draw between them
      const corner = (cell, vertex) => cell.inset[cell.face.indexOf(vertex)];
      quads.push({ a, b, link, points: [corner(cells[a], shared[0]), corner(cells[a], shared[1]), corner(cells[b], shared[1]), corner(cells[b], shared[0])] });
    });
    if (quads.length) {
      const seamPositions = new Float32Array(quads.length * 12), seamColours = new Float32Array(quads.length * 16), seamIndex = [];
      quads.forEach((quad, k) => {
        quad.points.forEach(([x, y], corner) => seamPositions.set([x, 0, y], (k * 4 + corner) * 3));
        seamIndex.push(k * 4, k * 4 + 1, k * 4 + 2, k * 4, k * 4 + 2, k * 4 + 3);
      });
      const seamGeometry = new THREE.BufferGeometry();
      seamGeometry.setAttribute("position", new THREE.BufferAttribute(seamPositions, 3));
      seamGeometry.setAttribute("color", new THREE.BufferAttribute(seamColours, 4));
      seamGeometry.setIndex(seamIndex);
      const seamMesh = new THREE.Mesh(seamGeometry, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
      seamMesh.frustumCulled = false;
      seamMesh.userData.unpickable = true;
      seamMesh.renderOrder = 2;
      seams = { quads, geometry: seamGeometry, mesh: seamMesh, record: abundance || null };
    }
  }
  return { cells, geometry, mesh, seams, pitch, low: 0.2 * pitch, high: 0.78 * pitch, extent, point, centre: [cx, cy] };
}
