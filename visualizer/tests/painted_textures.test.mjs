// Textures painted through a 2D canvas (src/core/painted.js).
//
// When the graphics process is lost, a 2D canvas comes back blank, also one that was asked to stay
// off the card, and three.js sends a texture again from the picture it holds: a texture whose
// picture is a canvas comes back blank (17 November 2026: the Protein atlas's membranes lost their
// beads, the Engine view its shade and its signs). So a painted texture is kept as pixels, through
// the one helper. This holds the rule for every file of the page; what a lost graphics process does
// to each view is held with a real browser by `node tools/check_look.mjs loss`.
//
//   node --test tests/painted_textures.test.mjs

import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const HELPER = "src/core/painted.js";
// The one lens that keeps its canvas: it paints its names again when the context comes back.
const REPAINTS = "src/lenses/laws_marks.js";

async function* scripts(folder) {
  for (const entry of await readdir(folder, { withFileTypes: true })) {
    const full = path.join(folder, entry.name);
    if (entry.isDirectory()) yield* scripts(full);
    else if (entry.name.endsWith(".js")) yield full;
  }
}

test("no file of the page makes a texture from a 2D canvas but the helper and the lens that paints its own again", async () => {
  const canvases = [], textures = [];
  for await (const file of scripts(path.join(ROOT, "src"))) {
    const name = path.relative(ROOT, file).split(path.sep).join("/");
    const text = await readFile(file, "utf8");
    if (/getContext\(\s*["']2d["']/.test(text)) canvases.push(name);
    if (/\bCanvasTexture\b/.test(text.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, ""))) textures.push(name);
  }
  assert.deepEqual(canvases.sort(), [HELPER, REPAINTS].sort(), "a 2D canvas is opened only by the helper, and by the lens that paints its own again");
  assert.deepEqual(textures, [REPAINTS], "a texture is made from a canvas only where the canvas is painted again when the context comes back");
});

test("the helper reads the painted pixels back, and the lens that keeps its canvas paints it again", async () => {
  const helper = await readFile(path.join(ROOT, HELPER), "utf8");
  assert.match(helper, /getImageData\(0, 0, width, height\)/, "the helper keeps the pixels, not the canvas");
  assert.doesNotMatch(helper.replace(/\/\/.*$/gm, ""), /CanvasTexture/, "the helper makes no texture from the canvas itself");
  const lens = await readFile(path.join(ROOT, REPAINTS), "utf8");
  assert.match(lens, /userData\.repaint\s*=/, "the Laws library's names have a way to be painted again");
  assert.match(lens, /addEventListener\?\.\("contextrestored"/, "and are painted again when their canvas comes back");
  const library = await readFile(path.join(ROOT, "src/lenses/laws.js"), "utf8");
  assert.match(library, /webglcontextrestored/, "and when the WebGL context comes back");
});
