// The colours of the species' own proteins (docs/ATLAS_LOOK.md, decided 16 November 2026), held to the palette
// check as the page's tokens, in both themes: the side of each protein's own membrane, how a side is known, and
// essentiality. Each is told apart from the others for normal sight and under each of the three kinds of
// colour-vision deficiency, from what it stands on, from the law hue, and from every status colour of the map, and
// stands at least 3 : 1 against both page backgrounds. As drawn and lit, tools/check_shelves.mjs "colours" checks
// them again in a real browser.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { KINDS, THRESHOLDS as T, contrast, distance, hue, leastDeficient, over } from "../tools/lib/colour_vision.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const css = readFileSync(path.join(ROOT, "src", "page.css"), "utf8");

/** The tokens of one block of page.css: the light theme's bare :root, or the dark theme's :root[data-theme="dark"]. */
function tokens(theme) {
  const block = theme === "light" ? /:root\s*\{([^}]*)\}/.exec(css)[1] : /:root\[data-theme="dark"\]\s*\{([^}]*)\}/.exec(css)[1];
  return Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map(([, name, value]) => [name, value.toLowerCase()]));
}

/** What a marker stands on, as shelves_view.js composes it: the membrane's face and the inside's glass over the page, the page itself. */
function surfaces(t, theme) {
  const dark = theme === "dark";
  const toward = (colour, target, share) => over(target, colour, share);
  return {
    page: t.bg,
    "membrane face": over(toward(t["bio-membrane"], dark ? "#000000" : "#ffffff", dark ? 0.42 : 0.3), t.bg, dark ? 0.55 : 0.45),
    "inside glass": over(toward(t["bio-membrane"], dark ? "#000000" : "#ffffff", dark ? 0.5 : 0.36), t.bg, dark ? 0.5 : 0.45),
  };
}

const STATUSES = ["st-qualified", "st-landed", "st-designed", "st-failed"];

for (const theme of ["light", "dark"]) {
  const t = tokens(theme);
  const sides = { outside: t["own-outside"], in: t["own-in"], inside: t["own-inside"] };

  test(`${theme}: the three sides are told apart for every kind of sight`, () => {
    assert.ok(Object.values(sides).every(Boolean), "page.css gives the three side colours");
    for (const [a, b] of [["outside", "in"], ["outside", "inside"], ["in", "inside"]]) {
      assert.ok(distance(sides[a], sides[b]) >= T.pairNormal, `${a} / ${b}: ${distance(sides[a], sides[b]).toFixed(1)} for normal sight`);
      assert.ok(leastDeficient(sides[a], sides[b]) >= T.pairDeficient, `${a} / ${b}: ${KINDS.map((kind) => `${kind} ${distance(sides[a], sides[b], kind).toFixed(1)}`).join(", ")}`);
    }
  });

  test(`${theme}: each side stands apart from the hollow grey, from what it stands on and from the law hue`, () => {
    for (const [side, colour] of Object.entries(sides)) {
      assert.ok(distance(colour, t.ghost) >= T.unknownNormal && leastDeficient(colour, t.ghost) >= T.unknownDeficient, `${side} from the grey of "not known"`);
      for (const [what, under] of Object.entries(surfaces(t, theme))) assert.ok(distance(colour, under) >= T.surfaceNormal && leastDeficient(colour, under) >= T.surfaceDeficient, `${side} on ${what} ${under}: ${KINDS.map((kind) => distance(colour, under, kind).toFixed(1)).join(", ")}`);
      assert.ok(distance(colour, t["bio-protein"]) >= T.law, `${side} from the law hue: ${distance(colour, t["bio-protein"]).toFixed(1)}`);
    }
  });

  test(`${theme}: no colour of the atlas can be taken for a status`, () => {
    const all = { ...sides, "basis 1": t["own-basis-1"], "basis 2": t["own-basis-2"], "basis 3": t["own-basis-3"], "mark 1": t["own-mark-1"], "mark 2": t["own-mark-2"], "mark 3": t["own-mark-3"] };
    for (const [name, colour] of Object.entries(all)) {
      for (const status of STATUSES) {
        assert.ok(distance(colour, t[status]) >= T.status, `${name} ${colour} from ${status} ${t[status]}: ${distance(colour, t[status]).toFixed(1)}`);
        if (status === "st-qualified" || status === "st-failed") {
          const gap = Math.abs(((hue(colour).angle - hue(t[status]).angle + 540) % 360) - 180);
          assert.ok(gap >= 22 || hue(colour).chroma < 25, `${name}: ${gap.toFixed(1)} degrees of hue from ${status}`);
        }
      }
    }
  });

  test(`${theme}: every colour of the atlas stands at least 3 : 1 against both page backgrounds`, () => {
    for (const name of ["own-outside", "own-in", "own-inside", "own-basis-1", "own-basis-2", "own-basis-3", "own-mark-1", "own-mark-2", "own-mark-3"]) {
      for (const ground of ["bg", "bg-raised"]) assert.ok(contrast(t[name], t[ground]) >= T.contrast, `${name} on --${ground}: ${contrast(t[name], t[ground]).toFixed(2)}`);
    }
  });

  test(`${theme}: the steps of each ramp are told apart under every deficiency`, () => {
    for (const ramp of ["own-basis", "own-mark"]) {
      for (const [a, b] of [[1, 2], [2, 3], [1, 3]]) assert.ok(leastDeficient(t[`${ramp}-${a}`], t[`${ramp}-${b}`]) >= T.step, `${ramp} ${a} / ${b}`);
      for (let step = 1; step <= 3; step++) assert.ok(leastDeficient(t[`${ramp}-${step}`], t.ghost) >= T.unknownDeficient, `${ramp} ${step} from the grey of "not known"`);
    }
  });
}

test("the dark theme's tokens are the same under the system's setting and under the page's own switch", () => {
  const media = /@media \(prefers-color-scheme: dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{([^}]*)\}/.exec(css)[1];
  const fromMedia = Object.fromEntries([...media.matchAll(/--(own-[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map(([, name, value]) => [name, value.toLowerCase()]));
  const dark = tokens("dark");
  assert.ok(Object.keys(fromMedia).length === 9);
  for (const [name, value] of Object.entries(fromMedia)) assert.equal(dark[name], value, name);
});
