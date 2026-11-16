// The cell's builder as a layout and part modules (src/lenses/cell_layout.js,
// src/lenses/parts/): what tests/cell_build.test.mjs does not already hold. That test holds
// the picture to its numbers; this one holds the seams: that making the layout takes nothing
// from the stream of chance the parts share, and that each module asks the lens only for the
// map's part names it declares, on every path through it, not only on the paths today's
// species take.
//
//   node --test tests/cell_part_modules.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { buildCell } from "../src/lenses/cell_parts.js";
import { makeLayout } from "../src/lenses/cell_layout.js";
import { seeded } from "../src/lenses/parts/geometry.js";
import { CELL_PARTS } from "../src/lenses/parts/index.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FOLDER = path.join(ROOT, "data", "species");
const files = readdirSync(FOLDER).filter((name) => name.endsWith(".json")).map((name) => JSON.parse(readFileSync(path.join(FOLDER, name), "utf8")));
const cellOf = (file, neighbours, has = () => true) => ({ shape: file.levels.find((level) => level.id === "cell").shape, parts: file.cell.parts || {}, has, neighbours, notes: [] });

/** A stand-in for the lens's context that keeps which part names were asked for, into `asked`. */
function context(asked) {
  const standard = () => new THREE.MeshStandardMaterial();
  const part = (name, anchor) => {
    asked.push(name);
    const group = new THREE.Group();
    return { name, anchor: anchor || null, group, material: standard, points: () => new THREE.PointsMaterial(), lineMaterial: () => new THREE.LineBasicMaterial(), proxyMaterial: () => new THREE.MeshBasicMaterial(), add: (...objects) => group.add(...objects) };
  };
  return { part, scale: part, known: () => true, neutral: standard, neutralPoints: () => new THREE.PointsMaterial(), neutralLine: (options = {}) => (options.dashed ? new THREE.LineDashedMaterial() : new THREE.LineBasicMaterial()), illustrate() {}, scenery() {}, sprite() {} };
}

test("making the layout takes nothing from the stream of chance the parts share", () => {
  for (const file of files) {
    for (const mode of ["schematic", "real"]) {
      const layout = makeLayout(mode, cellOf(file, true));
      const fresh = seeded(mode === "real" ? 23 : 7);
      assert.deepEqual([layout.random(), layout.random()], [fresh(), fresh()], `${file.id}, ${mode}: the stream starts where a fresh one does`);
      // What more than one part reads is the layout's, not any one part's.
      for (const claim of ["taken", "pack", "neighbours", "cells", "cagesAt", "machineAt", "coreAt", "coreRadius", "coreReach", "uncutSide", "junction"]) assert.ok(claim in layout, `${file.id}: the layout claims ${claim}`);
    }
  }
});

test("each part module asks only for the map's names it declares, on every path, and the registry holds each once", () => {
  const kinds = CELL_PARTS.map((module) => module.kind);
  assert.equal(new Set(kinds).size, kinds.length, "each kind once");
  const declared = CELL_PARTS.flatMap((module) => module.draws);
  assert.equal(new Set(declared).size, declared.length, "no map name is drawn by two modules");
  for (const file of files) {
    for (const mode of ["schematic", "real"]) {
      for (const neighbours of [true, false]) {
        // Every capability has a place here, so every branch a part has for it is drawn.
        const asked = [];
        const watched = CELL_PARTS.map((module) => ({
          ...module,
          build(env) {
            asked.length = 0;
            const out = module.build(env);
            const strange = asked.filter((name) => !module.draws.includes(name));
            assert.deepEqual(strange, [], `${file.id}, ${mode}, ${neighbours ? "in a layer" : "alone"}: ${module.kind} asked for names it does not declare`);
            return out;
          },
        }));
        const handles = buildCell(context(asked), context(asked), mode, cellOf(file, neighbours), watched);
        assert.ok(handles.probes.uncutSide && handles.shells && Array.isArray(handles.scenery), `${file.id}, ${mode}: the builder hands back its probes, shells and scenery`);
      }
    }
  }
});
