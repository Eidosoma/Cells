// A machine's shape (schema/MACHINE_SHAPES.md): the surfaces of its shape file, built for a view to draw at the Shape
// level. A shape is the viewer's own surface of a Protein Data Bank entry's coordinates, an illustration: nothing here
// says more of a machine than its file does.
//
// One machine is one mesh: every surface of the file in one buffer, so that a machine costs one draw. Each surface is a
// range of the mesh's triangles, in a table that gives its ids as the catalogue names them (`machine:<kind>:<part>`,
// `machine:<kind>:chain-<id>`) and its kind (protein, nucleic acid, or both). The caller picks a surface by the face a
// ray met (`surfaceAt(faceIndex)`), and recolours one surface, or all, by rewriting the colour of its vertices; nothing
// is rebuilt. Colours are the caller's: a function from a surface (its part, its kind, and the rest of its row) to a
// colour; `shapeColours` is a default from the page's palette.
//
// The mesh is in the frame and the units of the machine's measure: a vertex's integers times the file's `unit_nm` are
// nanometres, and `perNm` turns nanometres into the caller's units. The Machines view draws a measured machine's
// ellipsoids at `centre_nm / UNIT_NM` inside a group it stands on the tray; built with `perNm: 1 / UNIT_NM` and added to
// that same group, a shape sits exactly where its ellipsoids sit.

import * as THREE from "../three.js";
import { loadBeside } from "./protein_shelves.js";
import { pageId } from "./machines_data.js";

export const SHAPE_FORMAT = "cells.visualizer.machine-shape@1";
// A machine's measure kept as a file of its own names its shape file; the ribosomes' measures are their species' files.
const MEASURE_FILE = /^data\/catalogue\/measures\/([a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*)\.json$/;
// The default look: as the page's measured machines (machines.js), a soft, slightly glossy surface.
const LOOK = { roughness: 0.42, metalness: 0.05, envMapIntensity: 1 };

/**
 * Where a machine's shape file is published beside the page: `shapes/<species>.<machine>.json`, with the name of the
 * machine's measure where the catalogue's size names a measure file (`size.from`), else the species' and the kind's.
 */
export function shapePath(species, kind, size = null) {
  const named = MEASURE_FILE.exec(size?.from || "");
  return `shapes/${named ? named[1] : `${species}.${kind}`}.json`;
}

/** What keeps a file from being drawn, in words: an empty list where it can be. */
export function shapeProblems(data) {
  if (!data || typeof data !== "object") return ["it is not a shape file"];
  const problems = [];
  if (data.format !== SHAPE_FORMAT) problems.push(`its format is ${data.format || "not given"}, not ${SHAPE_FORMAT}`);
  if (!(data.unit_nm > 0)) problems.push("it gives no unit");
  if (!Array.isArray(data.meshes) || !data.meshes.length) problems.push("it holds no surface");
  const ids = new Set((data.meshes || []).map((mesh) => mesh.id));
  for (const mesh of [...(data.meshes || []), ...(data.tones || [])]) {
    const count = mesh.vertices?.length / 3;
    if (!Number.isInteger(count) || !Array.isArray(mesh.triangles) || mesh.triangles.length % 3) problems.push(`${mesh.id}: its vertices or triangles are not in threes`);
    else if (mesh.triangles.some((n) => !Number.isInteger(n) || n < 0 || n >= count)) problems.push(`${mesh.id}: a triangle names a vertex it does not have`);
  }
  for (const tone of data.tones || []) if (!ids.has(tone.within)) problems.push(`${tone.id}: the surface it lies within, ${tone.within}, is not in the file`);
  return problems;
}

/**
 * A machine's shape file, read from beside the page (`loadBeside`: the page's own copy where it carries one, else
 * fetched). Resolves to { status, path, data, words }: status "found" with the data; "none" where no shape file is
 * published for the machine (words say so plainly); "failed" where one could not be read or drawn (words say why).
 * A view learns that a machine has no shape only so: a page that carries its shapes inside it (a page for the disk)
 * and not this one has none; else the host answers the fetch with a client error (404, or any 4xx).
 */
export async function loadShape(path, { load = loadBeside, ...options } = {}) {
  const none = { status: "none", path, data: null, words: `No shape is published for this machine (${path}): it is drawn by its ellipsoids only.` };
  const root = "root" in options ? options.root : globalThis.document;
  const carried = root?.querySelectorAll?.('script[type="application/json"][data-file^="shapes/"]');
  if (carried?.length && ![...carried].some((script) => script.dataset?.file === path || script.getAttribute?.("data-file") === path)) return none;
  let data;
  try {
    data = await load(path, options);
  } catch (error) {
    const message = String(error?.message || error);
    if (/ answered 4\d\d$/.test(message)) return none;
    return { status: "failed", path, data: null, words: `The shape file ${path} could not be read (${message}).` };
  }
  const problems = shapeProblems(data);
  if (problems.length) return { status: "failed", path, data: null, words: `The shape file ${path} cannot be drawn: ${problems.join("; ")}.` };
  return { status: "found", path, data, words: null };
}

/**
 * The default colours, from the page's palette (core/theme.js, readPalette): nucleic acid (and a part of both kinds) in
 * the ribosome's token, protein in its part's hue where `hues` gives one (part id -> token), else the protein token;
 * each kind of chain a little lighter than the one before, so that neighbours are told apart.
 */
export function shapeColours(palette = {}, { hues = {} } = {}) {
  const fallback = { bioProtein: "#3f86e0", bioRibosome: "#4c4aa8", bg: "#ffffff" };
  const token = (name) => palette[name] || fallback[name] || fallback.bioProtein;
  return (part, kind, surface = {}) => {
    const hue = kind === "protein" ? hues[part] || "bioProtein" : hues[part] && kind === "nucleoprotein" ? hues[part] : "bioRibosome";
    const colour = new THREE.Color(token(hue));
    return colour.lerp(new THREE.Color(token("bg")), (hues[part] ? 0.3 : 0.45) * (surface.shade || 0));
  };
}

/**
 * Builds a machine's shape as one mesh. `kind` is the catalogue's kind of the machine (its page id `machine:<kind>`);
 * for an item of the catalogue that is not a kind (a unit of the law inventory, `unit.U39`), `id` gives its page id
 * instead, and its surfaces are named `<id>:<part>` and `<id>:chain-<id>`.
 * Options: `perNm` (the caller's units in a nanometre; 1 by default), `colour` (part, kind, surface) -> a colour (a
 * THREE.Color or anything THREE.Color takes; shapeColours({}) by default), `tones` (draw a part of protein and nucleic
 * acid as its two tones instead of one solid, where the file gives them), `material` (the caller's, kept by the caller;
 * else one of this module's, with the vertices' colours).
 * Returns { mesh, surfaces, surfaceAt, recolour, cost, dispose }: `surfaces` is the table of face ranges, one row a
 * surface: { id, part, chain, partId, kind, entity, description, residues, within, shade, first, last, firstVertex,
 * vertexCount } (first and last are triangle numbers, last included; part and chain are page ids or null).
 */
export function buildShape(data, { kind = null, id = null, perNm = 1, colour = null, tones = false, material = null } = {}) {
  const problems = shapeProblems(data);
  if (problems.length) throw new Error(`a shape that cannot be drawn: ${problems.join("; ")}`);
  if (!id && !kind) throw new Error("a shape is built for a machine: give its kind, or its page id");
  const machine = id || pageId(kind);
  const toneOf = new Map();
  if (tones) for (const tone of data.tones || []) toneOf.set(tone.within, [...(toneOf.get(tone.within) || []), tone]);
  const drawn = data.meshes.flatMap((mesh) => toneOf.get(mesh.id) || [mesh]);
  const entities = [...new Set(data.meshes.map((mesh) => mesh.entity).filter(Boolean))];
  const scale = data.unit_nm * perNm;
  const vertexTotal = drawn.reduce((sum, mesh) => sum + mesh.vertices.length / 3, 0);
  const triangleTotal = drawn.reduce((sum, mesh) => sum + mesh.triangles.length / 3, 0);
  const positions = new Float32Array(vertexTotal * 3), normals = new Float32Array(vertexTotal * 3), colours = new Float32Array(vertexTotal * 3).fill(1);
  const index = vertexTotal > 65535 ? new Uint32Array(triangleTotal * 3) : new Uint16Array(triangleTotal * 3);
  const surfaces = [];
  let vertexAt = 0, triangleAt = 0;
  const outside = outsideNormals(drawn);
  for (const mesh of drawn) {
    const count = mesh.vertices.length / 3, faces = mesh.triangles.length / 3;
    for (let i = 0; i < mesh.vertices.length; i++) positions[vertexAt * 3 + i] = mesh.vertices[i] * scale;
    for (let i = 0; i < mesh.triangles.length; i++) index[triangleAt * 3 + i] = mesh.triangles[i] + vertexAt;
    smoothNormals(mesh, normals, vertexAt, outside);
    surfaces.push({
      id: mesh.id,
      part: mesh.part ? `${machine}:${mesh.part}` : null,
      chain: mesh.chain ? `${machine}:${mesh.id}` : null,
      partId: mesh.part || null,
      kind: mesh.kind,
      entity: mesh.entity || null,
      description: mesh.description || null,
      residues: mesh.residues,
      within: mesh.within || null,
      shade: mesh.entity && entities.length > 1 ? entities.indexOf(mesh.entity) / (entities.length - 1) : 0,
      first: triangleAt,
      last: triangleAt + faces - 1,
      firstVertex: vertexAt,
      vertexCount: count,
    });
    vertexAt += count;
    triangleAt += faces;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  geometry.setIndex(new THREE.BufferAttribute(index, 1));
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  const ownMaterial = !material;
  const mesh = new THREE.Mesh(geometry, material || new THREE.MeshStandardMaterial({ ...LOOK, vertexColors: true }));
  mesh.name = `${machine}:shape`;
  mesh.castShadow = mesh.receiveShadow = true;
  mesh.userData.shape = { machine, entry: data.entry, assembly: data.assembly || null, tones: Boolean(tones && toneOf.size) };

  const paint = colour || shapeColours({});
  const scratch = new THREE.Color();
  /** Colours one surface (by its row, its number or its id), or every surface where none is named: `with` a colour, or the caller's function again. */
  const recolour = (which = null, withColour = null) => {
    const rows = which === null ? surfaces : [typeof which === "object" ? which : typeof which === "number" ? surfaces[which] : surfaces.find((row) => row.id === which)].filter(Boolean);
    const attribute = geometry.getAttribute("color");
    for (const row of rows) {
      scratch.set(withColour ?? paint(row.partId, row.kind, row));
      for (let n = row.firstVertex; n < row.firstVertex + row.vertexCount; n++) attribute.setXYZ(n, scratch.r, scratch.g, scratch.b);
      attribute.addUpdateRange?.(row.firstVertex * 3, row.vertexCount * 3);
    }
    attribute.needsUpdate = true;
    return rows.length;
  };
  recolour();

  /** The surface a ray met, from the face it met (a raycast's `faceIndex`): its row of the table, or null. */
  const surfaceAt = (faceIndex) => {
    let lo = 0, hi = surfaces.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1, row = surfaces[mid];
      if (faceIndex < row.first) hi = mid - 1;
      else if (faceIndex > row.last) lo = mid + 1;
      else return row;
    }
    return null;
  };

  let disposed = false;
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    mesh.removeFromParent();
    geometry.dispose();
    if (ownMaterial) mesh.material.dispose();
  };
  return { mesh, surfaces, surfaceAt, recolour, cost: { draws: 1, triangles: triangleTotal, vertices: vertexTotal }, dispose };
}

/** A face's normal, as long as twice its area, from a surface's integer vertices. */
function faceNormal(vertices, a, b, c) {
  const [ax, ay, az] = [vertices[a * 3], vertices[a * 3 + 1], vertices[a * 3 + 2]];
  const [ux, uy, uz] = [vertices[b * 3] - ax, vertices[b * 3 + 1] - ay, vertices[b * 3 + 2] - az];
  const [vx, vy, vz] = [vertices[c * 3] - ax, vertices[c * 3 + 1] - ay, vertices[c * 3 + 2] - az];
  return [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx];
}

const spot = (vertices, n) => `${vertices[n * 3]},${vertices[n * 3 + 1]},${vertices[n * 3 + 2]}`;

/**
 * Where surfaces divide one solid between them (a machine's parts, a part's two tones: those whose file gives `outer`,
 * the number of their first triangles that lie on the machine's outside), the outside's normal at each place a vertex
 * of it stands: the sum of the outside faces round that place, of every such surface drawn. Neighbours share their
 * seam's vertices exactly (the file makes them so), so that a seam is shaded as the one surface it is.
 */
function outsideNormals(drawn) {
  const sums = new Map();
  for (const mesh of drawn) {
    if (mesh.outer === undefined) continue;
    for (let t = 0; t < mesh.outer; t++) {
      const tri = [mesh.triangles[t * 3], mesh.triangles[t * 3 + 1], mesh.triangles[t * 3 + 2]];
      const normal = faceNormal(mesh.vertices, ...tri);
      for (const n of tri) {
        const key = spot(mesh.vertices, n);
        const sum = sums.get(key) || [0, 0, 0];
        for (let k = 0; k < 3; k++) sum[k] += normal[k];
        sums.set(key, sum);
      }
    }
  }
  return sums;
}

/**
 * Smooth normals for one surface, worked out once: each vertex the sum of its faces' normals, weighted by their areas.
 * A vertex on the machine's outside of a surface that divides a solid takes the outside's normal there (outsideNormals);
 * its vertices inside, on a face shared with a neighbour and hidden while the whole is drawn, take their own faces'.
 */
function smoothNormals(mesh, normals, offset, outside) {
  const count = mesh.vertices.length / 3;
  const sums = new Float64Array(count * 3);
  for (let t = 0; t < mesh.triangles.length / 3; t++) {
    const tri = [mesh.triangles[t * 3], mesh.triangles[t * 3 + 1], mesh.triangles[t * 3 + 2]];
    const normal = faceNormal(mesh.vertices, ...tri);
    for (const n of tri) for (let k = 0; k < 3; k++) sums[n * 3 + k] += normal[k];
  }
  for (let n = 0; n < count; n++) {
    const shared = mesh.outer === undefined ? null : outside.get(spot(mesh.vertices, n));
    const [x, y, z] = shared || [sums[n * 3], sums[n * 3 + 1], sums[n * 3 + 2]];
    const length = Math.hypot(x, y, z) || 1;
    normals[(offset + n) * 3] = x / length;
    normals[(offset + n) * 3 + 1] = y / length;
    normals[(offset + n) * 3 + 2] = z / length;
  }
}
