// The cell is built exactly as before: a check that holds the cell builder to numbers taken
// from what it draws, so that a change meant to move nothing (the builder's split into part
// modules, steps 1 to 3 of the plan for cell types, docs/CELL_TYPES_DESIGN.md, section 8) can be
// shown to move nothing.
//
// What it holds. Every species of the scene (data/species/*.json, as the extractor carried
// them), in each size mode its cell is drawn in, built as the cell lens builds it
// (src/lenses/cell.js, build): the cell and the studs on its skin (buildCell), the close-up
// of the membrane (buildMolecules), and the sheet where the species has one (buildTissue),
// through stand-ins for the lens's context that keep everything the builders hand over. For
// each part of each cell (each name the builder asks the lens for, and the scenery beside
// them), readable numbers:
//   objects    how many of each kind (meshes, instanced meshes, points, lines, sprites), and
//              how many instances;
//   vertices   how many vertex positions, once each instance has placed its copy;
//   mean       where those positions lie on average, in the cell's own frame;
//   spread     their second moments about the mean (xx, yy, zz, xy, yz, zx), which any
//              moved, resized or turned copy changes;
//   box        the smallest and largest x, y and z;
//   colours    the sums of instance and vertex colours, where a part has them;
//   materials  what each object wears: the kind of material and the options the builder asked
//              for (hue, shade, clip, texture, drift ...), with what it set on it itself, and
//              for each material how many objects and vertices wear it and where they lie on
//              average, so that two materials swapped within one part are told apart;
//   anchors    where its name stands, with the priority a builder gave it, and whether the
//              lens binds it to a capability of the map or draws it as neutral scenery.
// And what the builders hand back beside the picture: the frame, the spots on the outline,
// the shells, the probes the click checks use, the streams, signals and cages that move, the
// close-up's handles, the scenery list and its notes, the "As drawn" words of the structures,
// and the order in which each zone first asks for its parts (the order the lens writes names in).
//
// Numbers are rounded to nine significant figures before they are kept and before they are
// compared, and two numbers are the same when they differ by no more than two units in the
// ninth figure, so that the last bits of a float do not fail the check on another machine.
// A difference names the cell, the part and the numbers that moved.
//
// THE RULE. A commit that refactors never writes new numbers: tests/cell-build/numbers.json
// shows no diff in it. This file's reading code may change with the code it reads (the lens's
// names for what the builders hand back, the scene's shape of a species); byte-identical
// numbers are then the proof that nothing moved. Only a commit that says the picture changes
// writes the numbers again, and its message says which parts changed; their diff then shows
// those parts and nothing else. To write them again, deliberately:
//
//   CELL_BUILD_WRITE=1 node --test tests/cell_build.test.mjs
//
// The numbers come from the scene file (data/architecture/architecture.scene.json) for the
// species, the map's capabilities and what the map leaves out, and from the builders in
// src/lenses (cell_parts.js, cell_structures.js, cell_scenery.js, shapes.js) with the lens's
// own plan of what has a place (cell.js). Not held here: the organ and body outlines
// (outline_parts.js); what the lens does after a build (scaling, colours from the palette,
// labels); and how the lens itself calls the builders, which this file copies from
// CellLens.build by hand (the real-click checks hold that).
//
//   node --test tests/cell_build.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { buildCell, buildMolecules, buildTissue } from "../src/lenses/cell_parts.js";
import { CellLens } from "../src/lenses/cell.js";
import { cellTypeOf } from "../src/scene/entries.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NUMBERS = path.join(ROOT, "tests", "cell-build", "numbers.json");
const FORMAT = "cells.visualizer.cell_build_numbers@1";
const WRITE = process.env.CELL_BUILD_WRITE === "1";
const json = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const scene = json("data/architecture/architecture.scene.json");
const capabilities = scene.entities.filter((entity) => entity.kind === "capability");

// ------------------------------------------------------------ rounding and comparing

/** A number to nine significant figures; what is under 1e-12 is float noise, and 0, as -0 is. */
const round = (value) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return value;
  if (Math.abs(value) < 1e-12) return 0;
  const kept = Number(value.toPrecision(9));
  return kept === 0 ? 0 : kept;
};
/** The same value with every number in it rounded; vectors become [x, y, z], functions are left out. */
function plain(value) {
  if (typeof value === "number") return round(value);
  if (value === null || value === undefined || typeof value === "string" || typeof value === "boolean") return value ?? null;
  if (typeof value === "function") return undefined;
  if (value.isVector3) return [round(value.x), round(value.y), round(value.z)];
  if (value.isVector2) return [round(value.x), round(value.y)];
  if (Array.isArray(value)) return value.map(plain);
  if (value.isObject3D || value.isMaterial || value.isBufferGeometry) return `[${value.type}]`;
  const out = {};
  for (const [key, item] of Object.entries(value)) {
    const kept = plain(item);
    if (kept !== undefined) out[key] = kept;
  }
  return out;
}
/** Two kept numbers are the same within two units of the ninth significant figure. */
const same = (a, b) => a === b || (typeof a === "number" && typeof b === "number" && Math.abs(a - b) <= 2e-8 * Math.max(Math.abs(a), Math.abs(b)) + 1e-12);
/** Where two kept values differ: a list of paths. */
function differences(was, now, at = "") {
  if (same(was, now)) return [];
  if (Array.isArray(was) && Array.isArray(now)) {
    if (was.length !== now.length) return [`${at} (${was.length} items, now ${now.length})`];
    return was.flatMap((item, index) => differences(item, now[index], `${at}[${index}]`));
  }
  if (was && now && typeof was === "object" && typeof now === "object" && !Array.isArray(was) && !Array.isArray(now)) {
    const keys = [...new Set([...Object.keys(was), ...Object.keys(now)])];
    return keys.flatMap((key) => (key in was ? (key in now ? differences(was[key], now[key], at ? `${at}.${key}` : key) : [`${at ? `${at}.` : ""}${key} (gone)`]) : [`${at ? `${at}.` : ""}${key} (new)`]));
  }
  return [`${at || "value"} (${JSON.stringify(was)} → ${JSON.stringify(now)})`];
}

// ------------------------------------------------------------ the stand-ins for the lens

// The properties a builder may set on a material itself, kept where they differ from a fresh one.
const SET_ON_MATERIAL = ["side", "transparent", "opacity", "depthTest", "depthWrite", "colorWrite", "wireframe", "polygonOffset", "polygonOffsetFactor", "polygonOffsetUnits", "alphaTest", "size", "sizeAttenuation", "dashSize", "gapSize", "scale", "visible", "toneMapped", "flatShading", "vertexColors"];

/**
 * What one build hands the lens, kept: for each zone (cell, studs, molecules, tissue) its parts
 * by name, its scenery, and the order in which it asked for parts. `lens` gives what the lens's
 * own context knows: which part names the map has, and which it binds to a capability.
 */
class Keeper {
  constructor(lens) {
    this.lens = lens;
    this.groups = new Map(); // key -> { zone, name, kind, bound, parts: [stand-in part], roots: [Object3D], sprites: [] }
    this.order = {};
    this.tags = new WeakMap(); // material -> "kind(options)"
  }

  group(key, fields) {
    if (!this.groups.has(key)) this.groups.set(key, { ...fields, parts: [], roots: [], sprites: [] });
    return this.groups.get(key);
  }

  tag(material, kind, options = {}) {
    const said = Object.entries(plain(options) || {}).filter(([, value]) => value !== undefined).sort(([a], [b]) => a.localeCompare(b));
    this.tags.set(material, `${kind}(${said.map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : value}`).join(" ")})`);
    return material;
  }

  /** The context the lens hands a builder for one zone (cell.js, CellLens.context). */
  context(zone) {
    const lens = this.lens, keep = this;
    (this.order[zone] ??= []);
    const standIn = (key, name, fields, anchor) => {
      const record = keep.group(key, { zone, name, ...fields });
      if (!keep.order[zone].includes(name)) keep.order[zone].push(name);
      const part = {
        name, anchor: anchor || null, group: new THREE.Group(),
        material: (options = {}) => keep.tag(new THREE.MeshStandardMaterial(), "part", options),
        points: (options = {}) => keep.tag(new THREE.PointsMaterial(), "points", options),
        lineMaterial: (options = {}) => keep.tag(new THREE.LineBasicMaterial(), "line", options),
        proxyMaterial: () => keep.tag(new THREE.MeshBasicMaterial(), "proxy"),
        add: (...objects) => objects.forEach((object) => part.group.add(object)),
      };
      record.parts.push(part);
      record.roots.push(part.group);
      return part;
    };
    return {
      part: (name, anchor) => {
        const entity = lens.capabilityByPart.get(name);
        return standIn(`${zone}:${name}`, name, { kind: "part", bound: Boolean(entity && !lens.absent.has(entity.id)) }, anchor);
      },
      scale: (id, anchor) => standIn(`${zone}:scale:${id}`, `scale:${id}`, { kind: "scale", bound: Boolean(lens.model.get(id)) }, anchor),
      known: (name) => lens.capabilityByPart.has(name),
      neutral: (options = {}) => keep.tag(new THREE.MeshStandardMaterial(), "neutral", options),
      neutralPoints: (options = {}) => keep.tag(new THREE.PointsMaterial(), "neutralPoints", options),
      neutralLine: (options = {}) => keep.tag(options.dashed ? new THREE.LineDashedMaterial() : new THREE.LineBasicMaterial(), "neutralLine", options),
      illustrate: (object, zoneName) => keep.group(`${zoneName || zone}:scenery`, { zone: zoneName || zone, name: "scenery", kind: "scenery" }).roots.push(object),
      scenery: (object, id) => keep.group(`${zone}:chosen:${id}`, { zone, name: id, kind: "chosen" }).roots.push(object),
      sprite: (part, text, position, size) => {
        const owner = [...keep.groups.values()].find((record) => record.parts.includes(part));
        owner?.sprites.push({ text, at: plain(position), size: round(size) });
      },
    };
  }

  /** The numbers of every group, by key, in the order the groups were made. */
  numbers() {
    const out = {};
    for (const [key, record] of this.groups) out[key] = this.digest(record);
    return out;
  }

  digest(record) {
    const objects = {}, materials = {}, flags = new Set();
    let instances = 0, hidden = 0;
    // Moments of every vertex position, shifted by the first one so that a large offset costs no precision.
    let n = 0, K = null, sx = 0, sy = 0, sz = 0, sxx = 0, syy = 0, szz = 0, sxy = 0, syz = 0, szx = 0;
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    const colours = { instance: [0, 0, 0], vertex: [0, 0, 0] };
    let coloured = false;
    const m = new THREE.Matrix4(), whole = new THREE.Matrix4(), c = new THREE.Color();
    for (const root of record.roots) {
      root.updateMatrixWorld(true);
      root.traverse((node) => {
        if (!(node.isMesh || node.isPoints || node.isLine || node.isSprite)) return;
        const kind = node.isInstancedMesh ? "InstancedMesh" : node.type;
        objects[kind] = (objects[kind] || 0) + 1;
        if (!node.visible) hidden++;
        for (const key of Object.keys(node.userData || {})) flags.add(key);
        if (node.renderOrder) flags.add(`renderOrder=${node.renderOrder}`);
        const worn = [];
        for (const material of [node.material].flat()) {
          if (!material) continue;
          const fresh = new material.constructor();
          const set = SET_ON_MATERIAL.filter((key) => key in material && material[key] !== fresh[key]).map((key) => `${key}=${typeof material[key] === "number" ? round(material[key]) : material[key]}`);
          const name = `${this.tags.get(material) || `its own ${material.type}`}${set.length ? ` set ${set.join(" ")}` : ""}`;
          materials[name] ??= { objects: 0, vertices: 0, sum: [0, 0, 0], K: null };
          materials[name].objects++;
          worn.push(materials[name]);
        }
        const placements = [];
        if (node.isInstancedMesh) {
          instances += node.count;
          for (let index = 0; index < node.count; index++) {
            node.getMatrixAt(index, m);
            placements.push(whole.multiplyMatrices(node.matrixWorld, m).clone());
          }
          if (node.instanceColor) {
            coloured = true;
            for (let index = 0; index < node.count; index++) {
              node.getColorAt(index, c);
              colours.instance[0] += c.r;
              colours.instance[1] += c.g;
              colours.instance[2] += c.b;
            }
          }
        } else placements.push(node.matrixWorld);
        const position = node.geometry?.attributes?.position;
        const colour = node.geometry?.attributes?.color;
        if (colour) {
          coloured = true;
          for (let index = 0; index < colour.count; index++) for (let axis = 0; axis < 3; axis++) colours.vertex[axis] += colour.getComponent(index, axis) * placements.length;
        }
        if (!position) return;
        const interleaved = position.isInterleavedBufferAttribute;
        const p = interleaved ? position.data.array : position.array, stride = interleaved ? position.data.stride : position.itemSize, offset = interleaved ? position.offset : 0;
        for (const placement of placements) {
          const e = placement.elements;
          for (let index = 0; index < position.count; index++) {
            const at = index * stride + offset, x0 = p[at], y0 = p[at + 1], z0 = p[at + 2];
            const x = e[0] * x0 + e[4] * y0 + e[8] * z0 + e[12], y = e[1] * x0 + e[5] * y0 + e[9] * z0 + e[13], z = e[2] * x0 + e[6] * y0 + e[10] * z0 + e[14];
            if (K === null) K = [x, y, z];
            const dx = x - K[0], dy = y - K[1], dz = z - K[2];
            for (const wearing of worn) {
              wearing.K ??= [x, y, z];
              wearing.vertices++;
              wearing.sum[0] += x - wearing.K[0];
              wearing.sum[1] += y - wearing.K[1];
              wearing.sum[2] += z - wearing.K[2];
            }
            n++;
            sx += dx; sy += dy; sz += dz;
            sxx += dx * dx; syy += dy * dy; szz += dz * dz; sxy += dx * dy; syz += dy * dz; szx += dz * dx;
            if (x < lo[0]) lo[0] = x;
            if (y < lo[1]) lo[1] = y;
            if (z < lo[2]) lo[2] = z;
            if (x > hi[0]) hi[0] = x;
            if (y > hi[1]) hi[1] = y;
            if (z > hi[2]) hi[2] = z;
          }
        }
      });
    }
    const out = { kind: record.kind };
    if (record.bound !== undefined) out.bound = record.bound;
    out.objects = objects;
    out.instances = instances;
    out.vertices = n;
    if (n) {
      const mx = sx / n, my = sy / n, mz = sz / n;
      out.mean = [K[0] + mx, K[1] + my, K[2] + mz].map(round);
      out.spread = [sxx / n - mx * mx, syy / n - my * my, szz / n - mz * mz, sxy / n - mx * my, syz / n - my * mz, szx / n - mz * mx].map(round);
      out.box = [lo.map(round), hi.map(round)];
    }
    if (coloured) out.colours = { instance: colours.instance.map(round), vertex: colours.vertex.map(round) };
    out.materials = Object.fromEntries(Object.entries(materials).sort(([a], [b]) => a.localeCompare(b)).map(([name, wearing]) => [name, { objects: wearing.objects, vertices: wearing.vertices, ...(wearing.vertices ? { mean: wearing.sum.map((sum, axis) => round(wearing.K[axis] + sum / wearing.vertices)) } : {}) }]));
    if (hidden) out.hidden = hidden;
    if (flags.size) out.flags = [...flags].sort();
    const anchors = record.parts.filter((part) => part.anchor || part.priority !== undefined).map((part) => ({ at: plain(part.anchor), ...(part.priority !== undefined ? { priority: part.priority } : {}) }));
    if (anchors.length) out.anchors = anchors;
    if (record.parts.length > 1) out.asked = record.parts.length;
    if (record.sprites.length) out.sprites = record.sprites;
    return out;
  }
}

// ------------------------------------------------------------ the builds, as the lens makes them

/** The lens as far as its plan needs it, for one species of the scene (cell.js: plan and draws). */
function planned(species) {
  const lens = {
    species, cellType: cellTypeOf(species), sizeMode: "schematic", // its default cell type, as the lens shows it first
    model: { ofKind: (kind) => (kind === "capability" ? capabilities : []), get: (id) => scene.entities.find((item) => item.id === id) || null, raw: scene },
    capabilityByPart: new Map(capabilities.map((entity) => [entity.part, entity])),
    leftOut: new Set((scene.left_out || []).map((item) => item.part).filter(Boolean)),
  };
  CellLens.prototype.plan.call(lens);
  lens.draws = (part) => CellLens.prototype.draws.call(lens, part);
  return lens;
}
const notesOf = (level) => (level?.notes || []).map((item) => (typeof item === "string" ? { text: item } : item));
const samples = (path) => [0, 0.5, 1].map((t) => plain(path(t)));

/** What the cell's builders hand back beside the picture, as numbers and words. */
function handlesOf(handles) {
  const { frame, molecule } = handles;
  return {
    frame: plain({ kind: frame.kind, u: frame.u, cut: frame.cut, top: frame.top, base: frame.base, bevel: frame.bevel, corner: frame.corner, long: frame.long, middle: frame.middle, round: frame.round, outline: frame.outline.length, apothem: frame.outline.apothem, widest: frame.equator.widest }),
    shape: { points: [0, Math.PI / 3, Math.PI / 2, Math.PI, (3 * Math.PI) / 2].map((angle) => plain(handles.shape.point(angle))), depth: round(handles.shape.depth(new THREE.Vector3(0, frame.cut, 0))) },
    spots: plain(handles.spots),
    shells: plain(handles.shells),
    probes: plain(handles.probes),
    streams: (handles.streams || []).map((stream) => plain({ inward: stream.inward, drops: stream.drops.length, reach: stream.reach, at: [0, stream.reach].map((offset) => stream.at(offset)) })),
    signals: { count: (handles.signals || []).length, path: samples(handles.signalPath) },
    cages: (handles.cages || []).map((cage) => plain(cage.position)),
    molecule: plain({ centre: molecule.centre, outward: molecule.outward, pored: molecule.pored, view: molecule.view, fromInside: Boolean(molecule.fromInside), ions: molecule.ions.length, path: samples(molecule.ionPath), pumpAt: molecule.pumpAt || null }),
    reach: round(handles.reach || 0),
    scenery: plain(handles.scenery || []),
    notes: plain(handles.notes || []),
    structures: plain(handles.structures || {}),
  };
}

/** Every build of the scene's species: "<species>/<size mode>" for the cell, "<species>/tissue" for the sheet. */
function buildAll() {
  const builds = {}, broken = {};
  for (const species of scene.species) {
    try {
      buildSpecies(species, builds);
    } catch (error) {
      broken[species.id] = error;
    }
  }
  return { builds, broken };
}

/** One species' builds, added to `builds`. */
function buildSpecies(species, builds) {
  {
    const lens = planned(species);
    // As the lens builds it: the parts of the cell type shown, the species' default (schema/CELL_TYPES.md).
    const cell = { shape: lens.levels.cell.shape, parts: cellTypeOf(species).parts || {}, has: lens.draws, neighbours: Boolean(lens.levels.tissue), notes: notesOf(lens.levels.cell) };
    let first = null;
    for (const mode of lens.modes) {
      const keep = new Keeper(lens);
      const handles = buildCell(keep.context("cell"), keep.context("studs"), mode, cell);
      handles.molecule = buildMolecules(keep.context("molecules"), mode, handles.frame, lens.draws);
      first ??= handles;
      builds[`${species.id}/${mode}`] = { order: keep.order, parts: keep.numbers(), handles: handlesOf(handles) };
    }
    const tissue = lens.levels.tissue;
    if (tissue) {
      const keep = new Keeper(lens);
      const rings = tissue.shape.rings, height = first.frame.top * 2;
      const sheet = buildTissue(keep.context("tissue"), { rings, height, beyond: tissue.shape.beyond ?? [[rings + 2, 0.34], [rings + 4, 0.2], [rings + 5, 0.1]], notes: notesOf(tissue), sides: cell.shape.kind === "prism" ? cell.shape.sides : 6 });
      builds[`${species.id}/tissue`] = { order: keep.order, parts: keep.numbers(), handles: plain({ height, extent: sheet.extent, spread: sheet.spread, notes: sheet.notes }) };
    }
  }
}

// ------------------------------------------------------------ the numbers file

/** The file, laid out so that its diff shows each part on a line of its own. */
function written(builds) {
  const line = (value) => JSON.stringify(value);
  const block = (entries, indent) => entries.map(([key, value]) => `${indent}${line(key)}: ${line(value)}`).join(",\n");
  const parts = Object.entries(builds).map(([key, build]) => [
    `  ${line(key)}: {`,
    `   "order": ${line(build.order)},`,
    `   "parts": {\n${block(Object.entries(build.parts), "    ")}\n   },`,
    `   "handles": {\n${block(Object.entries(build.handles), "    ")}\n   }`,
    "  }",
  ].join("\n"));
  const head = { format: FORMAT, note: "Numbers of what the cell's builders draw, by part, for tests/cell_build.test.mjs. Written only by a commit that says the picture changes, with CELL_BUILD_WRITE=1; never by hand, never by a refactor.", rounding: "nine significant figures; equal within two units of the ninth" };
  return `{\n${Object.entries(head).map(([key, value]) => ` ${line(key)}: ${line(value)}`).join(",\n")},\n "builds": {\n${parts.join(",\n")}\n }\n}\n`;
}

const { builds, broken } = buildAll();
/** How a species' build threw, in a few lines, or null. */
const threw = (key) => {
  const error = broken[key.split("/")[0]];
  return error ? `the builder threw while building ${key.split("/")[0]}: ${String(error.stack || error).split("\n").slice(0, 4).join("\n    ")}` : null;
};

if (WRITE && Object.keys(broken).length) throw new Error(`no numbers written: ${Object.keys(broken).map((id) => threw(id)).join("; ")}`);
if (WRITE) {
  mkdirSync(path.dirname(NUMBERS), { recursive: true });
  writeFileSync(NUMBERS, written(builds));
}
let kept = { builds: {} };
try {
  kept = JSON.parse(readFileSync(NUMBERS, "utf8"));
} catch (error) {
  kept = { missing: `${path.relative(ROOT, NUMBERS)} cannot be read (${error.code || error.name})`, builds: {} };
}

// ------------------------------------------------------------ the checks

test("the numbers file is the check's own, and every species of the repository is built", () => {
  assert.deepEqual(Object.keys(broken), [], Object.keys(broken).map((id) => threw(id)).join("\n"));
  assert.ok(!kept.missing, `${kept.missing}: write the numbers, in a commit that says the picture changes (CELL_BUILD_WRITE=1)`);
  assert.equal(kept.format, FORMAT);
  const files = readdirSync(path.join(ROOT, "data", "species")).filter((name) => name.endsWith(".json")).map((name) => name.replace(/\.json$/, ""));
  const held = Object.keys(json("data/architecture/overlay.json").species_held || {});
  assert.deepEqual(scene.species.map((item) => item.id).sort(), files.filter((id) => !held.includes(id)).sort(), "the scene carries every species file that is not held back (run the extractor if a file was added)");
  for (const species of scene.species) {
    const lens = planned(species);
    for (const mode of lens.modes) assert.ok(builds[`${species.id}/${mode}`], `${species.id} is built in ${mode}`);
  }
  assert.deepEqual(Object.keys(kept.builds).sort(), Object.keys(builds).sort(), "the file holds numbers for exactly the builds made now: a species or a size mode was added or taken away (write the numbers again, in a commit that says so)");
});

for (const key of [...new Set([...Object.keys(builds), ...Object.keys(kept.builds)])]) {
  test(`${key} is built exactly as before`, () => {
    assert.ok(!threw(key), threw(key));
    const was = kept.builds[key], now = builds[key];
    assert.ok(now, `${key} is in the numbers and was not built now: a species or a size mode was taken away`);
    assert.ok(was, `no numbers for ${key}: write them, in a commit that says the picture changes`);
    const problems = [];
    // The order in which each zone first asks for its parts: the order the lens writes their names in.
    for (const line of differences(was.order, now.order)) problems.push(`order of the parts: ${line}`);
    // Each part, on its own, so that the message names the part that moved.
    const names = [...new Set([...Object.keys(was.parts), ...Object.keys(now.parts)])];
    for (const name of names) {
      if (!(name in now.parts)) problems.push(`${name}: no longer drawn`);
      else if (!(name in was.parts)) problems.push(`${name}: drawn now, and not before`);
      else {
        const lines = differences(was.parts[name], now.parts[name]);
        if (lines.length) problems.push(`${name}: ${lines.slice(0, 4).join("; ")}${lines.length > 4 ? `; and ${lines.length - 4} more` : ""}`);
      }
    }
    for (const name of [...new Set([...Object.keys(was.handles), ...Object.keys(now.handles)])]) {
      const lines = differences(was.handles[name], now.handles[name]);
      if (lines.length) problems.push(`handles.${name}: ${lines.slice(0, 4).join("; ")}${lines.length > 4 ? `; and ${lines.length - 4} more` : ""}`);
    }
    assert.ok(!problems.length, `${key} is built differently from its numbers (tests/cell-build/numbers.json):\n  ${problems.join("\n  ")}\nA refactor must move nothing. If the picture is meant to change, write the numbers again (CELL_BUILD_WRITE=1) in a commit that says which parts changed.`);
  });
}
