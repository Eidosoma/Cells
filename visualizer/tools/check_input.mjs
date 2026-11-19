#!/usr/bin/env node
// Drives the viewer with real pointer input in headless Chrome, through the DevTools
// protocol (Node's built-in WebSocket; no extra dependency). Screenshots set state by
// query parameter and so never touch picking or the camera control; this does.
//
//   node tools/check_input.mjs            (CHECK_ONLY=engine|atlas|species|experiments|cell|zoom runs one part;
//                                          CHECK_RUNS=DIR serves replays from another folder;
//                                          CHECK_SCENE=FILE draws another scene file;
//                                          CHECK_SPECIES=ID runs the cell and zoom parts on that species' cell;
//                                          CHECK_LOOK=plain draws the Cell view with the look as it was, which
//                                          a server that draws in software does much faster: the cell and zoom
//                                          parts test clicks, not the look (tools/check_look.mjs tests that))
//
// Only one browser runs at a time (tools/lib/browser_lock.mjs), so a call may wait its turn.

import { spawn } from "node:child_process";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE } from "./lib/build_page.mjs";

const chromeBinary = process.env.CHROME || "google-chrome";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};

const pageLog = [];
const release = await acquireBrowser();
const server = createServer({ offline: true, runs: process.env.CHECK_RUNS || DEFAULT_RUNS, scene: process.env.CHECK_SCENE || DEFAULT_SCENE, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;

const chrome = spawn(
  chromeBinary,
  // Its profile on disk, removed with the lock: never Chrome's own folder under /tmp.
  ["--headless=new", "--no-sandbox", "--mute-audio", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--remote-debugging-port=0", "--window-size=1280,800", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
const endpoint = await new Promise((resolve, reject) => {
  let text = "";
  chrome.stderr.on("data", (chunk) => {
    text += chunk;
    const match = text.match(/DevTools listening on (ws:\/\/\S+)/);
    if (match) resolve(match[1]);
  });
  setTimeout(() => reject(new Error("Chrome did not report a DevTools address")), 20000);
});

const socket = new WebSocket(endpoint);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});
let nextId = 1;
const waiting = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  const entry = waiting.get(message.id);
  if (!entry) return;
  waiting.delete(message.id);
  if (message.error) entry.reject(new Error(message.error.message));
  else entry.resolve(message.result);
};
const send = (method, params = {}, sessionId) =>
  new Promise((resolve, reject) => {
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params, sessionId }));
  });

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
const page = (method, params) => send(method, params, sessionId);
await page("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false });

const evaluate = async (expression) => {
  const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result.value;
};
const VIEWER = "document.querySelector('cells-viewer')";
const open = async (query) => {
  await page("Page.navigate", { url: `${base}?${query}&still=1` });
  for (let tries = 0; tries < 80; tries++) {
    await sleep(250);
    if (await evaluate(`Boolean(${VIEWER} && ${VIEWER}.current && ${VIEWER}.stage)`).catch(() => false)) break;
  }
  await sleep(900);
};
const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
const click = async (x, y) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await mouse("mousePressed", x, y);
  await mouse("mouseReleased", x, y, { buttons: 0 });
  await sleep(300);
};
const wheel = (x, y, deltaY) => page("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 0, deltaY, button: "none", buttons: 0 });
// Screen position of a world point, given as an expression that yields a Vector3.
const screen = (point) =>
  evaluate(`(() => { const v = ${VIEWER}; const p = ${point}; const out = p.clone(); v.stage.project(p, out); return { x: out.x, y: out.y }; })()`);
const selected = () => evaluate(`${VIEWER}.state.selected`);
const only = process.env.CHECK_ONLY;
const wants = (part) => !only || only === part;
// The points clicked in the cell come from the lens (cell_parts.js), so they follow the layout.
const probe = (name) => `${VIEWER}.current.probes.${name}.clone()`;
const clear = () => evaluate(`${VIEWER}.select(null)`);
// The middle of an element inside the viewer, found by a selector, and a real click there.
const middle = (selector) =>
  evaluate(`(() => { const found = ${VIEWER}.shadowRoot.querySelector(${JSON.stringify(selector)}); if (!found) return null; found.scrollIntoView({ block: "nearest" }); const box = found.getBoundingClientRect(); return { x: box.left + box.width / 2, y: box.top + box.height / 2 }; })()`);
const press = async (selector) => {
  const at = await middle(selector);
  if (!at) throw new Error(`nothing matches ${selector}`);
  await click(at.x, at.y);
  await sleep(250);
};
// The species switch is a dropdown: press its pill, wait for the list, press the species' row.
const pickSpecies = async (id) => {
  const listOpen = () => evaluate(`(() => { const box = ${VIEWER}.shadowRoot.querySelector(".species-list"); return Boolean(box && !box.hidden); })()`);
  if (!(await listOpen())) await press(".species-pick");
  for (let tries = 0; tries < 30 && !(await listOpen()); tries++) await sleep(100);
  await press(`.species-list [data-atlas="${id}"]`);
  for (let tries = 0; tries < 30 && (await listOpen()); tries++) await sleep(100);
  await sleep(150);
};
// The species whose side of the atlas is the inventory's own. The page opens on the species whose
// file says default, which may be another, so the checks of the inventory's side ask for it by name.
const ownAtlas = () => evaluate(`(() => { const atlases = ${VIEWER}.model.raw.proteins.atlases || []; return (atlases.find((atlas) => atlas.reference) || atlases[0])?.id ?? null; })()`);
// What the protein atlas shows of its species: the card, the legend, the rings and the panel.
const speciesState = () =>
  evaluate(`(() => {
    const viewer = ${VIEWER}, root = viewer.shadowRoot, lens = viewer.lenses.get("proteins");
    const text = (selector) => root.querySelector(selector)?.textContent ?? null;
    const panel = root.querySelector("cells-panel");
    return {
      lens: viewer.state.lens,
      atlas: viewer.state.atlas ?? null,
      attribute: viewer.dataset.atlas ?? null,
      // The species the dropdown offers, with the one in view (the switch is one pill and a list since 15 November 2026).
      species: [...root.querySelectorAll(".species-pick")].some((button) => button.offsetParent) && viewer.speciesShown ? viewer.speciesShown.rows.map((row) => ({ id: row.id, label: row.label, pressed: row.id === viewer.speciesShown.active })) : [],
      heading: text(".view-card .card-title"),
      organism: text(".view-card .card-organism"),
      stats: [...root.querySelectorAll(".view-card .stat b")].map((item) => item.textContent).join(" "),
      details: [...root.querySelectorAll(".view-card details summary")].map((item) => item.textContent).join(" | "),
      findings: [...root.querySelectorAll("cells-legend [data-finding]")].map((button) => button.dataset.finding + "=" + button.querySelector(".legend-count").textContent + (button.getAttribute("aria-pressed") === "true" ? "*" : "")).join(", "),
      mapping: [...root.querySelectorAll("cells-legend .legend-body > .legend-item:not(.legend-group)")].map((button) => button.textContent).join(", "),
      units: lens ? lens.nodes.size : null,
      marks: lens ? lens.marks.length : null,
      marksShown: lens ? lens.marks.filter((mark) => mark.mesh.visible).length : null,
      lit: lens ? [...lens.nodes.values()].filter((node) => lens.lit(node.entity)).length : null,
      finding: lens ? lens.finding ?? null : null,
      caveat: text(".caveat"),
      selected: viewer.state.selected,
      panel: panel.hidden ? null : {
        chips: [...panel.querySelectorAll(".chip")].map((chip) => chip.textContent).join(" | "),
        finding: panel.querySelector(".panel-finding")?.textContent ?? null,
        heads: [...panel.querySelectorAll(".panel-list h4")].map((head) => head.textContent).join(" | "),
        lawNote: panel.querySelector(".list-note")?.textContent ?? null,
        tags: [...panel.querySelectorAll(".tag")].map((tag) => tag.textContent).join(" | "),
        hosts: [...new Set([...panel.querySelectorAll(".item-links a")].map((link) => new URL(link.href).hostname))].join(" "),
      },
    };
  })()`);

try {
  // ---------------------------------------------------------------- engine lens
  if (wants("engine")) {
    await open("lens=engine");
    // A block can stand behind a taller neighbour, so ask the page for one whose top is in plain
    // view, then check that a real click there selects it.
    const block = await evaluate(`(() => {
      const viewer = ${VIEWER}, lens = viewer.current;
      const out = lens.nodes.values().next().value.top.clone();
      for (const [id, node] of lens.nodes) {
        if (node.entity.kind !== "component") continue;
        viewer.stage.project(node.top, out);
        const hit = viewer.stage.pick(out.x, out.y + 3, lens.pickRoots);
        if (hit && hit.id === id && out.x > 300 && out.x < 900 && out.y > 90) return { id, x: out.x, y: out.y + 3 };
      }
      return null;
    })()`);
    await click(block.x, block.y);
    check("engine: clicking a block selects it", (await selected()) === block.id, `${block.id} -> ${await selected()}`);
    check("engine: the panel opens", await evaluate(`!${VIEWER}.shadowRoot.querySelector("cells-panel").hidden`));
    await click(40, 400);
    check("engine: clicking empty space clears the selection", (await selected()) === null, String(await selected()));
  }

  // ---------------------------------------------------------------- protein atlas
  if (wants("atlas")) {
    await open("lens=proteins");
    await open(`lens=proteins&atlas=${await ownAtlas()}`);
    // The order decided on 17 November 2026, by the views' ids (Machines, the Laws library and Experiments only where the scene holds them).
    // The titles are the viewer's own list's (src/ui/viewer.js), read from the page: no check holds a title of its own.
    const tabs = await evaluate(`(() => { const v = ${VIEWER}, buttons = [...v.shadowRoot.querySelectorAll(".switch button")]; return { ids: buttons.map((button) => button.dataset.lens), said: buttons.map((button) => button.getAttribute("aria-label")), titles: buttons.map((button) => v.views.find((view) => view.id === button.dataset.lens)?.label) }; })()`);
    const ORDER = ["cell", "machines", "proteins", "engine", "laws", "experiments"];
    check("atlas: the views are in the order decided, the Cell view first, each tab titled from the viewer's list of views", ["cell", "proteins", "engine"].every((id) => tabs.ids.includes(id)) && JSON.stringify(tabs.ids) === JSON.stringify(ORDER.filter((id) => tabs.ids.includes(id))) && tabs.titles.every(Boolean) && JSON.stringify(tabs.said) === JSON.stringify(tabs.titles), JSON.stringify(tabs));
    // A unit whose top is in plain view, with no label lying over the point clicked.
    const unit = await evaluate(`(() => {
      const viewer = ${VIEWER}, lens = viewer.current;
      for (const [id, node] of lens.nodes) {
        const out = node.top.clone();
        viewer.stage.project(node.top, out);
        const x = out.x, y = out.y + 7;
        if (x < 320 || x > 1000 || y < 130 || y > 560) continue;
        const hit = viewer.stage.pick(x, y, lens.pickRoots);
        if (hit && hit.id === id && viewer.shadowRoot.elementFromPoint(x, y) === viewer.canvas) return { id, x, y };
      }
      return null;
    })()`);
    await click(unit.x, unit.y);
    check("atlas: clicking a unit selects it", (await selected()) === unit.id, `${unit.id} -> ${await selected()}`);
    const panel = await evaluate(`(() => {
      const panel = ${VIEWER}.shadowRoot.querySelector("cells-panel");
      return { open: !panel.hidden, chip: panel.querySelector(".chip")?.textContent, hosts: [...new Set([...panel.querySelectorAll(".item-links a")].map((a) => a.hostname))].join(" ") };
    })()`);
    check("atlas: the panel states the mapping and links to the public atlases", panel.open && /Assigned|Candidate|Generic/.test(panel.chip || "") && panel.hosts.includes("proteinatlas.org"), `${panel.chip}; ${panel.hosts}`);

    // The legend's "Generic" leaves only the generic laws lit.
    const generic = await evaluate(`(() => {
      const button = [...${VIEWER}.shadowRoot.querySelectorAll("cells-legend .legend-item")].find((item) => item.querySelector(".legend-label").textContent === "Generic");
      const box = button.getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
    })()`);
    await click(generic.x, generic.y);
    const lit = await evaluate(`(() => { const lens = ${VIEWER}.current; return { isolate: lens.isolate, lit: [...lens.nodes.values()].filter((node) => lens.lit(node.entity)).length, generic: lens.atlas.mappings.find((item) => item.id === "generic").count }; })()`);
    check("atlas: the legend shows the generic laws alone", lit.isolate === "generic" && lit.lit === lit.generic && lit.lit > 0, JSON.stringify(lit));
    await click(generic.x, generic.y);

    // A unit's connection leads to the engine part that holds its law, in the engine view.
    const link = await evaluate(`(() => {
      const button = ${VIEWER}.shadowRoot.querySelector("cells-panel .connection .link-button");
      button.scrollIntoView({ block: "center" });
      const box = button.getBoundingClientRect();
      return { text: button.textContent, x: box.left + Math.min(box.width / 2, 40), y: box.top + box.height / 2 };
    })()`);
    await click(link.x, link.y);
    await sleep(900);
    const there = await evaluate(`(() => {
      const viewer = ${VIEWER}, entity = viewer.model.get(viewer.state.selected);
      const heads = [...viewer.shadowRoot.querySelectorAll("cells-panel .connection h4")].map((item) => item.textContent).join(" | ");
      return { lens: viewer.state.lens, label: entity?.label, heads };
    })()`);
    check("atlas: a unit's connection opens its engine part in the engine view", there.lens === "engine" && there.label === link.text, `${link.text} -> ${there.lens}: ${there.label}`);
    check("atlas: that engine part lists the units it holds the law for", /Holds the law for/.test(there.heads), there.heads);
  }

  // ---------------------------------------------------------------- species atlases
  if (wants("species")) {
    await open("lens=proteins");
    const opens = (await speciesState()).atlas; // the species the page opens on
    await open(`lens=proteins&atlas=${await ownAtlas()}`);
    let s = await speciesState();
    // The species to switch to: one with a unit built from another family, where there is one, so
    // that the checks on such a unit run; otherwise the first that is not shown.
    const rich = await evaluate(`(() => {
      const nodes = [...${VIEWER}.current.nodes.values()];
      const shown = ${JSON.stringify(s.species.filter((item) => !item.pressed).map((item) => item.id))};
      return shown.find((id) => nodes.some((node) => node.entity.species?.[id]?.finding === "different family")) ?? null;
    })()`);
    const other = s.species.find((item) => item.id === rich) || s.species.find((item) => !item.pressed);
    if (!other) {
      check("species: a scene with one atlas shows no switch, and no rings", s.species.length === 0 && s.marks === 0, JSON.stringify(s.species));
    } else {
      const human = s;
      check("species: the inventory's own side has the page's species switch, no rings and no findings", s.species.find((item) => item.pressed)?.id === s.atlas && s.marks === 0 && s.findings === "", JSON.stringify([s.atlas, s.species, s.marks, s.findings]));

      await pickSpecies(other.id);
      s = await speciesState();
      check("species: a click on another species shows its atlas", s.atlas === other.id && s.attribute === other.id && s.heading !== human.heading && s.species.find((item) => item.id === other.id).pressed, JSON.stringify([s.atlas, s.attribute, s.heading]));
      check("species: the card gives the species' own name, counts and sources", Boolean(s.organism) && s.stats !== human.stats && /How it was made/.test(s.details) && /Sources and licences/.test(s.details), JSON.stringify([s.organism, s.stats, s.details]));
      check("species: the units drawn and the legend's mapping counts are the engine's, unchanged", s.units === human.units && s.mapping === human.mapping, `${s.units} units; ${s.mapping}`);
      check("species: the legend lists the species' findings in the contract's words", /^found=\d+, different family=\d+, none found=\d+, nothing to look for=\d+$/.test(s.findings), s.findings);
      const differ = Number(/different family=(\d+)/.exec(s.findings)?.[1]) + Number(/none found=(\d+)/.exec(s.findings)?.[1]);
      check("species: one ring for each unit with another family or nothing found, and no other", s.marks === differ && s.marksShown === s.marks, `${s.marks} rings, ${differ} units`);
      check("species: the page says the laws are the same for every species", /same for every species/.test(s.caveat || ""), s.caveat);

      // A real click on a ring picks its unit.
      const ring = await evaluate(`(() => {
        const viewer = ${VIEWER}, lens = viewer.current;
        for (const mark of lens.marks) {
          mark.mesh.geometry.computeBoundingBox();
          const reach = mark.mesh.geometry.boundingBox.max.x - 0.25;
          for (let angle = 0.05; angle < 6.28; angle += 0.1) {
            const point = mark.mesh.position.clone();
            point.x += Math.cos(angle) * reach;
            point.z += Math.sin(angle) * reach;
            const out = point.clone();
            viewer.stage.project(point, out);
            if (out.x < 320 || out.x > 1000 || out.y < 110 || out.y > 640) continue;
            const hit = viewer.stage.pick(out.x, out.y, lens.pickRoots);
            if (hit && hit.id === mark.node.entity.id && hit.object === mark.mesh && viewer.shadowRoot.elementFromPoint(out.x, out.y) === viewer.canvas) return { id: hit.id, x: out.x, y: out.y };
          }
        }
        return null;
      })()`);
      check("species: a ring can be found under the pointer", Boolean(ring), JSON.stringify(ring));
      if (ring) {
        await click(ring.x, ring.y);
        s = await speciesState();
        check("species: clicking a ring selects its unit", s.selected === ring.id, `${ring.id} -> ${s.selected}`);
        check("species: the panel states the species' finding beside the engine's mapping", Boolean(s.panel) && s.panel.chips.includes(`${other.label}: `) && /Assigned|Candidate|Generic/.test(s.panel.chips) && Boolean(s.panel.finding), JSON.stringify(s.panel));
        check("species: the panel says the laws are the same for every species", s.panel?.lawNote === "The same laws for every species.", String(s.panel?.lawNote));
      }

      // A unit built from another family lists the species' products, each with how it was found.
      const family = await evaluate(`[...${VIEWER}.current.nodes.values()].find((node) => node.entity.species?.[${JSON.stringify(other.id)}]?.finding === "different family")?.entity.id ?? null`);
      if (family) {
        await evaluate(`${VIEWER}.select(${JSON.stringify(family)})`);
        await sleep(300);
        s = await speciesState();
        check("species: a unit of another family lists the species' products with their evidence", Boolean(s.panel) && s.panel.heads.includes(`${other.label} gene products`) && !/Candidate products/.test(s.panel.heads) && /Family signature|Similarity search|Named in a publication|Reviewed entry/.test(s.panel.tags), JSON.stringify([s.panel?.heads, s.panel?.tags.slice(0, 120)]));
        check("species: its links go to the databases", /www\.uniprot\.org|wormbase/.test(s.panel?.hosts || ""), String(s.panel?.hosts));
      }

      // A finding in the legend shows its units alone; a second press shows all again.
      await press('cells-legend [data-finding="none found"]');
      s = await speciesState();
      const none = Number(/none found=(\d+)\*/.exec(s.findings)?.[1] ?? -1);
      check("species: a finding in the legend shows its units alone", s.finding === "none found" && s.lit === none && s.marksShown === none, JSON.stringify([s.finding, s.lit, s.marksShown, s.findings]));
      await press('cells-legend [data-finding="none found"]');
      s = await speciesState();
      check("species: pressing it again shows every unit", s.finding === null && s.lit === s.units && s.marksShown === s.marks, JSON.stringify([s.finding, s.lit, s.marksShown]));

      // The choice is kept across views, and the inventory's atlas comes back as it was.
      await press('.switch [data-lens="engine"]');
      await press('.switch [data-lens="proteins"]');
      s = await speciesState();
      check("species: the species is kept when another view is visited", s.lens === "proteins" && s.atlas === other.id && s.marks > 0, JSON.stringify([s.lens, s.atlas, s.marks]));
      if (family) await evaluate(`${VIEWER}.select(${JSON.stringify(family)})`);
      await pickSpecies(human.atlas);
      s = await speciesState();
      check("species: back on the inventory's atlas, the card, the legend and the picture are as before", s.atlas === human.atlas && s.heading === human.heading && s.stats === human.stats && s.findings === "" && s.marks === 0 && s.lit === s.units && s.mapping === human.mapping, JSON.stringify([s.atlas, s.heading, s.findings, s.marks, s.lit]));
      check("species: the selected unit lists the inventory's candidates again", !family || (Boolean(s.panel) && s.panel.finding === null && /Candidate products/.test(s.panel.heads) && s.panel.lawNote === null), JSON.stringify(s.panel));

      // The address can set the species, also while another view is shown; an unknown one is ignored.
      await open(`lens=cell&atlas=${other.id}`);
      s = await speciesState();
      check("species: atlas= in the address is taken while another view is shown", s.lens === "cell" && s.atlas === other.id, JSON.stringify([s.lens, s.atlas]));
      await open("lens=proteins&atlas=no-such-species");
      s = await speciesState();
      check("species: an unknown species in the address is ignored", s.atlas === opens, JSON.stringify([s.atlas, opens, s.heading]));
    }
  }

  // ---------------------------------------------------------------- experiments (replays)
  if (wants("experiments")) {
    await open("lens=experiments");
    const shown = await evaluate(`${VIEWER}.state.lens`);
    check("experiments: the view is offered when replays have been made", shown === "experiments", `${shown}; make them with npm run adapt:runs`);
    // The tab opens on its landing, a page of cards (18 November 2026); a real press on the card that opens a part (the
    // tumour tissue's, as its experiment's opens.part names it) shows that part, and its networks are a real press away,
    // on its card's own button. (Until then the tab opened on the part itself.)
    let cards = 0;
    for (let tries = 0; tries < 120 && !cards; tries++) {
      await sleep(250);
      cards = await evaluate(`${VIEWER}.state.landing ? ${VIEWER}.shadowRoot.querySelectorAll(".landing-card").length : 0`).catch(() => 0);
    }
    check("experiments: the tab opens on its landing of cards", cards > 0, String(cards));
    // A card the pick finds among all the landing's cards; where its band stands folded (every band but the first does as
    // the landing opens, 19 November 2026), a real press on the band's control shows it first.
    const pressCard = async (pick) => {
      const where = await evaluate(`(() => { const v = ${VIEWER}, lens = v.landingView; const id = lens.landing.bands.flatMap((band) => band.cards.map((card) => card.id)).find((id) => (${pick})(lens.opened(id))); if (!id) return null; if (v.shadowRoot.querySelector('[data-card="' + id + '"]')?.checkVisibility()) return { id }; const band = lens.landing.bands.find((item) => item.cards.some((card) => card.id === id)); const fold = v.shadowRoot.querySelector('[data-band="' + band.id + '"] .landing-fold'); if (!fold) return { id }; fold.scrollIntoView({ block: "center" }); const r = fold.getBoundingClientRect(); return { id, fold: { x: r.left + r.width / 2, y: r.top + r.height / 2 } }; })()`);
      if (!where) return null;
      if (where.fold) {
        await click(where.fold.x, where.fold.y);
        for (let tries = 0; tries < 40 && !(await evaluate(`Boolean(${VIEWER}.shadowRoot.querySelector('[data-card="${where.id}"]')?.checkVisibility())`)); tries++) await sleep(250);
      }
      const at = await evaluate(`(() => { const el = ${VIEWER}.shadowRoot.querySelector('[data-card="${where.id}"] .landing-open'); if (!el || !el.checkVisibility()) return null; el.scrollIntoView({ block: "center" }); const r = el.getBoundingClientRect(); return { id: ${JSON.stringify(where.id)}, folded: Boolean(${JSON.stringify(Boolean(where.fold))}), x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
      if (at) await click(at.x, at.y);
      return at;
    };
    const partCard = await pressCard("(opened) => Boolean(opened?.part)");
    let part = null;
    for (let tries = 0; tries < 120 && partCard && !part; tries++) {
      await sleep(250);
      part = await evaluate(`${VIEWER}.state.part || null`);
    }
    if (shown === "experiments" && part) {
      await evaluate(`Promise.resolve(${VIEWER}.current.ready).then(() => true)`);
      await sleep(600);
      const door = await evaluate(`(() => { const el = ${VIEWER}.shadowRoot.querySelector(".view .tissue-back:not(.tissue-sibling)"); if (!el) return null; el.scrollIntoView({ block: "center" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
      if (door) await click(door.x, door.y);
      let back = false;
      for (let tries = 0; tries < 240 && !back; tries++) {
        await sleep(250);
        back = await evaluate(`Boolean(!${VIEWER}.state.part && ${VIEWER}.current?.run && ${VIEWER}.current.sheet)`).catch(() => false);
      }
      check(`experiments: a real press on a card of the landing (${partCard.id}) shows its part (${part}), and a real press on the part's card's button shows its networks`, Boolean(door) && back, JSON.stringify(door));
    }
    if (shown === "experiments") {
      const spot = (selector) =>
        evaluate(`(() => {
          const element = ${VIEWER}.shadowRoot.querySelector(${JSON.stringify(selector)});
          if (!element) return null;
          element.scrollIntoView({ block: "nearest" });
          const box = element.getBoundingClientRect();
          return { x: box.left + box.width / 2, y: box.top + box.height / 2, left: box.left, width: box.width, text: element.textContent };
        })()`);
      await evaluate(`${VIEWER}.current.ready.then(() => true)`);
      await sleep(800);
      const first = await evaluate(`({ run: ${VIEWER}.current.runId, cells: ${VIEWER}.current.sheet.cells.length, end: ${VIEWER}.current.run.end })`);
      check("experiments: a run is loaded and drawn", first.cells > 0 && first.end > 0, JSON.stringify(first));

      // A cell in plain view, with nothing lying over the point clicked.
      const cell = await evaluate(`(() => {
        const viewer = ${VIEWER}, lens = viewer.current, cells = lens.sheet.cells;
        for (let index = 0; index < cells.length; index++) {
          const out = cells[index].top.clone();
          viewer.stage.project(cells[index].top, out);
          const x = out.x, y = out.y;
          if (x < 330 || x > 980 || y < 140 || y > 600) continue;
          const hit = viewer.stage.pick(x, y, lens.pickRoots);
          if (hit && hit.id === "cell:" + index && viewer.shadowRoot.elementFromPoint(x, y) === viewer.canvas) return { id: "cell:" + index, x, y };
        }
        return null;
      })()`);
      await click(cell.x, cell.y);
      check("experiments: clicking a cell selects it", (await selected()) === cell.id, `${cell.id} -> ${await selected()}`);
      check("experiments: the panel charts that cell's voltage", await evaluate(`Boolean(${VIEWER}.shadowRoot.querySelector("cells-panel cells-trace .trace-plot"))`));
      await clear();

      // The timeline: play moves the playhead, a click on the track jumps to that time.
      const play = await spot("cells-timeline .tl-play");
      const before = await evaluate(`${VIEWER}.current.player.time`);
      await click(play.x, play.y);
      await sleep(2000);
      const during = await evaluate(`({ time: ${VIEWER}.current.player.time, playing: ${VIEWER}.current.player.playing })`);
      await click(play.x, play.y);
      const paused = await evaluate(`${VIEWER}.current.player.playing`);
      check("timeline: play moves the playhead and pause stops it", during.playing && during.time > before && !paused, `${before.toFixed(1)} s -> ${during.time.toFixed(1)} s`);
      const track = await spot("cells-timeline input.tl-range");
      await click(track.left + track.width * 0.8, track.y);
      const sought = await evaluate(`${VIEWER}.current.player.time / ${VIEWER}.current.run.end`);
      check("timeline: a click on the track goes to that time", Math.abs(sought - 0.8) < 0.06, sought.toFixed(3));

      // A phone: the timeline's speed list, the longest a run is offered, stays on the screen and under the bar, each
      // step at least 44 px tall, and a real press takes one. With a cell's panel open the timeline stands on the
      // panel's top edge, and its play button and its list still take a press.
      await page("Emulation.setDeviceMetricsOverride", { width: 400, height: 780, deviceScaleFactor: 1, mobile: false });
      await sleep(1200);
      const speeds = () =>
        evaluate(`(() => {
          const root = ${VIEWER}.shadowRoot, list = root.querySelector(".tl-speeds"), edges = (el) => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round); };
          const bar = root.querySelector(".bar .switch"), panel = root.querySelector("cells-panel");
          return { open: !list.hidden, box: list.hidden ? null : edges(list), steps: [...list.querySelectorAll(".tl-speed-step")].map((step) => Math.round(step.getBoundingClientRect().height)), speed: ${VIEWER}.current.player.speed,
            bar: edges(bar)[3], timeline: edges(root.querySelector("cells-timeline")), panel: panel.hidden ? null : edges(panel), width: innerWidth, height: innerHeight, length: ${VIEWER}.current.run.end - ${VIEWER}.current.run.start };
        })()`);
      const onScreen = (now) => Boolean(now.box) && now.box[0] >= 0 && now.box[2] <= now.width && now.box[1] >= now.bar && now.box[3] <= now.height;
      let speedButton = await spot("cells-timeline .tl-speed");
      await click(speedButton.x, speedButton.y);
      let list = await speeds();
      check(`phone: a real press opens the speed list of a ${Math.round(list.length / 60)}-minute run on the screen, under the bar, each of its ${list.steps.length} steps at least 44 px tall`, list.open && onScreen(list) && list.steps.length >= 5 && list.steps.every((height) => height >= 44), JSON.stringify(list));
      const step = await evaluate(`(() => { const el = [...${VIEWER}.shadowRoot.querySelectorAll('.tl-speed-step[aria-pressed="false"]')][0]; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, speed: Number(el.dataset.speed) }; })()`);
      await click(step.x, step.y);
      list = await speeds();
      check("phone: a real press on a step takes that speed and closes the list", list.speed === step.speed && !list.open, JSON.stringify([step.speed, list.speed, list.open]));
      // A cell chosen through the page (choosing is checked above): its panel is a sheet along the bottom.
      await evaluate(`${VIEWER}.select(${JSON.stringify(cell.id)})`);
      await sleep(900);
      list = await speeds();
      check("phone: with a cell's panel open the timeline stands on the panel's top edge", Boolean(list.panel) && list.timeline[3] <= list.panel[1] && list.timeline[1] >= list.bar, JSON.stringify([list.timeline, list.panel, list.bar]));
      const phonePlay = await spot("cells-timeline .tl-play");
      await click(phonePlay.x, phonePlay.y);
      const phonePlaying = await evaluate(`${VIEWER}.current.player.playing`);
      await click(phonePlay.x, phonePlay.y);
      speedButton = await spot("cells-timeline .tl-speed");
      await click(speedButton.x, speedButton.y);
      list = await speeds();
      check("phone: there a real press still plays the run, and its speed list opens on the screen under the bar", phonePlaying && list.open && onScreen(list), JSON.stringify([phonePlaying, list.box, list.bar]));
      await click(speedButton.x, speedButton.y); // a press on the speed button closes the list again
      await clear();
      await page("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false });
      await sleep(1200);

      // Another run of the same experiment: the card switches, and the recorded class follows the run.
      // A few runs are rows to press; many are a list, which is set as a person choosing would set it.
      const loaded = async (not) => {
        for (let tries = 0; tries < 80; tries++) {
          if (await evaluate(`${VIEWER}.current.run && ${VIEWER}.current.run.id === ${VIEWER}.current.runId && ${VIEWER}.current.runId !== ${JSON.stringify(not)}`)) return;
          await sleep(250);
        }
      };
      const other = await evaluate(`(() => {
        const root = ${VIEWER}.shadowRoot;
        const row = root.querySelector('.run-row[aria-pressed="false"]');
        if (row) { const box = row.getBoundingClientRect(); return { how: "row", x: box.left + box.width / 2, y: box.top + box.height / 2 }; }
        const list = root.querySelector("#cells-run");
        if (!list) return null;
        const next = [...list.options].find((option) => !option.selected && ${VIEWER}.current.catalogue.byId.get(option.value)?.class !== ${VIEWER}.current.catalogue.byId.get(${VIEWER}.current.runId)?.class) || [...list.options].find((option) => !option.selected);
        list.value = next.value;
        list.dispatchEvent(new Event("change"));
        return { how: "list" };
      })()`);
      if (other) {
        if (other.how === "row") await click(other.x, other.y);
        await loaded(first.run);
        const second = await evaluate(`(() => { const lens = ${VIEWER}.current, entry = lens.catalogue.byId.get(lens.runId); return { run: lens.runId, loaded: lens.run?.id, klass: entry.class || null, recorded: lens.run?.view.run.class || null, shown: ${VIEWER}.shadowRoot.querySelector(".run-class .chip")?.textContent || null }; })()`);
        check(`experiments: picking another run (${other.how}) loads it`, second.run !== first.run && second.loaded === second.run, JSON.stringify(second));
        check("experiments: the class shown is the one the run's summary recorded", second.klass === second.recorded && (second.klass === null ? second.shown === null : second.shown?.toLowerCase() === second.klass), JSON.stringify(second));
      }

      // Another experiment, when there is one: the way back to all experiments, then another card, and what it found follows.
      // (Until 18 November 2026 a list in the run's card switched the experiment; the landing is the list now.)
      const left = await evaluate(`({ run: ${VIEWER}.current.runId, experiment: ${VIEWER}.current.catalogue.byId.get(${VIEWER}.current.runId).experiment })`);
      const back = await spot(".exp-back");
      if (back) await click(back.x, back.y);
      await sleep(600);
      const another = await pressCard(`(opened) => Boolean(opened?.run) && !opened.run.startsWith(${JSON.stringify(`${left.experiment}--`)})`);
      check("experiments: another card that opens a run stands on the landing, a real press on its band's control away where its band is folded", Boolean(another), JSON.stringify(another));
      if (another) {
        await loaded(left.run);
        const after = await evaluate(`(() => { const lens = ${VIEWER}.current, entry = lens.catalogue.byId.get(lens.runId), outcome = lens.catalogue.outcomeOf(lens.catalogue.experimentOf(entry)); return { experiment: entry.experiment, loaded: lens.run?.view.run.experiment, facts: [...${VIEWER}.shadowRoot.querySelectorAll(".found-facts .fact")].map((item) => item.textContent).join(" | "), expected: [outcome?.judgedLabel, outcome?.answer ? outcome.label : null].filter(Boolean).join(" | ") }; })()`);
        check("experiments: the way back and another card of the landing switch the experiment", after.experiment !== left.experiment && after.loaded === after.experiment, `${left.experiment} -> ${after.experiment}`);
        check("experiments: what it found is the catalogue's two facts for that experiment", after.facts === after.expected && after.facts.length > 0, after.facts);
      }

      // Run details lead to the engine parts the experiment ran.
      const details = await spot(".run-actions button");
      await click(details.x, details.y);
      const run = await selected();
      const link = await evaluate(`(() => {
        const button = ${VIEWER}.shadowRoot.querySelector("cells-panel .link-button");
        if (!button) return null;
        button.scrollIntoView({ block: "center" });
        const box = button.getBoundingClientRect();
        return { text: button.textContent, x: box.left + Math.min(box.width / 2, 40), y: box.top + box.height / 2 };
      })()`);
      check("experiments: run details open in the panel with links to engine parts", String(run).startsWith("run:") && Boolean(link), `${run}; ${link?.text}`);
      if (link) {
        await click(link.x, link.y);
        await sleep(900);
        const there = await evaluate(`({ lens: ${VIEWER}.state.lens, label: ${VIEWER}.model.get(${VIEWER}.state.selected)?.label })`);
        check("experiments: such a link opens the part in its own view", there.lens !== "experiments" && there.label === link.text, `${link.text} -> ${there.lens}: ${there.label}`);
      }
    }
  }

  // ---------------------------------------------------------------- cell lens
  // The Cell view's look (src/core/look.js) is rich unless CHECK_LOOK names another: "plain", or "full" for every effect held on.
  const cellView = `lens=cell${process.env.CHECK_LOOK ? `&look=${process.env.CHECK_LOOK}` : ""}${process.env.CHECK_SPECIES ? `&species=${process.env.CHECK_SPECIES}` : ""}`;
  // On a busy machine, or with the rich look drawn in software, one frame may take seconds. The
  // cell and zoom parts therefore wait for what they are about to read or click, never for a fixed time.
  const until = async (expression, seconds = 180) => {
    for (let tries = 0; tries < seconds * 4; tries++) {
      if (await evaluate(expression).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  // Two more frames have been drawn (or one, where the view then stands still) and the camera holds still: what is on the screen is what a click meets.
  const settled = async () => {
    await evaluate(`(() => { const stage = ${VIEWER}.stage; if (window.__drawn === undefined) { window.__drawn = 0; stage.afterRender.add(() => { window.__drawn += 1; }); } window.__from = window.__drawn; stage.invalidate(); })()`);
    await until(`window.__drawn >= window.__from + 2 || (window.__drawn > window.__from && !${VIEWER}.stage.running)`);
    let last = null;
    for (let tries = 0, same = 0; tries < 240 && same < 2; tries++) {
      const now = await evaluate(`JSON.stringify([${VIEWER}.stage.camera.position.toArray(), ${VIEWER}.stage.camera.quaternion.toArray()].flat().map((n) => Math.round(n * 1000) / 1000))`);
      same = now === last ? same + 1 : 0;
      last = now;
      await sleep(250);
    }
  };
  // How long a part took, in the look it was drawn with: the rich look costs a server that draws in software several times more a frame.
  const took = (part, from) => console.log(`note  the ${part} part took ${Math.round((Date.now() - from) / 1000)} s, drawn with ${process.env.CHECK_LOOK ? `look=${process.env.CHECK_LOOK}` : "the rich look"}`);
  if (wants("cell")) {
  const cellFrom = Date.now();
  await open(cellView);
  await settled();
  const nucleus = await screen(probe("nucleus"));
  await click(nucleus.x, nucleus.y); // through the gene network's open cage around it
  // A cell without a nucleus has a free chromosome under the cut face of its cytoplasm: a click over it
  // meets the cytoplasm first, and the chromosome is chosen by its name (the label checks below).
  // What is drawn at the nucleus and at its chromatin is the scene's to say: since 16 November 2026 the nucleus is a
  // part of its own and the regulatory circuits sit at the chromatin; a scene made before draws the circuits at the nucleus.
  const atNucleus = await evaluate(`${VIEWER}.current.capabilityByPart.get("nucleus")?.id ?? null`);
  const atChromatin = await evaluate(`(${VIEWER}.current.capabilityByPart.get("chromatin") || ${VIEWER}.current.capabilityByPart.get("nucleus"))?.id ?? null`);
  // The scene of today names both, so that "what the scene draws there" cannot pass on a part that went missing.
  if (await evaluate(`Boolean(${VIEWER}.model.get("cap.nucleus"))`)) check("cell: the scene draws the nucleus at the nucleus and the regulatory circuits at the chromatin", atNucleus === "cap.nucleus" && atChromatin === "cap.circuits", JSON.stringify([atNucleus, atChromatin]));
  if (await evaluate(`Boolean(${VIEWER}.current.species.cell.parts.nucleus ?? true)`)) {
    check(`cell: clicking the nucleus selects what the scene draws there (${atNucleus})`, (await selected()) === atNucleus, String(await selected()));
    await clear();
    if (await evaluate(`Boolean(${VIEWER}.current.probes.chromatin)`)) {
      const inside = await screen(probe("chromatin"));
      await click(inside.x, inside.y);
      check(`cell: clicking into the opened nucleus reaches the chromatin, and what is drawn there (${atChromatin})`, (await selected()) === atChromatin, String(await selected()));
    }
  } else check("cell: a click over the free chromosome meets the cytoplasm that lies over it, or the chromosome", ["cap.reactions", atChromatin].includes(await selected()), String(await selected()));
  await clear();

  // Above the cut the membrane is clipped; a click there must not select it.
  const cut = await screen(probe("cutGel"));
  await click(cut.x, cut.y);
  const inCut = await selected();
  check("cell: a click in the cut-away does not select the membrane", inCut !== "cap.membrane" && inCut !== null, String(inCut));
  await clear();

  // On the uncut side the membrane (or a channel or pump standing on it) is what a click reaches.
  const skin = await screen(probe("uncutSide"));
  await click(skin.x, skin.y);
  const onSkin = await selected();
  check("cell: a click on the uncut side reaches the membrane", ["cap.membrane", "cap.channels", "cap.pumps", "cap.division"].includes(onSkin), String(onSkin));
  await clear();

  // ---------------------------------------------------------------- the view switches
  const press = async (text) => {
    const spot = await evaluate(`(() => {
      const button = [...${VIEWER}.shadowRoot.querySelectorAll(".seg button")].find((item) => item.textContent === "__TEXT__");
      const box = button.getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
    })()`.replace("__TEXT__", text));
    await click(spot.x, spot.y);
  };
  await press("Status");
  check("switch: Colour to Status recolours the cell", (await evaluate(`${VIEWER}.current.colourBy`)) === "status");
  await press("Biology");
  // Every cell is drawn in both size modes (a bacterium too, since 17 November 2026); a card without a Sizes switch is checked for none.
  if (await evaluate(`${VIEWER}.current.modes.length > 1`)) {
  await press("To scale");
  await until(`(() => { const lens = ${VIEWER}.current; return lens.sizeMode === "real" && lens.zones.some((zone) => zone.root.visible && zone.name === "cell" && zone.mode === "real"); })()`, 120);
  await settled();
  const real = await evaluate(`(() => { const lens = ${VIEWER}.current; return { mode: lens.sizeMode, shown: lens.zones.filter((zone) => zone.root.visible).map((zone) => zone.name + ":" + zone.mode).join(" ") }; })()`);
  check("switch: Sizes to To scale shows the to-scale cell and hides the schematic one", real.mode === "real" && real.shown.includes("cell:real") && !real.shown.includes("cell:schematic"), real.shown);
  const nucleusToScale = await screen(probe("nucleus"));
  await click(nucleusToScale.x, nucleusToScale.y);
  // A cell without a nucleus (a bacterium, to scale since 17 November 2026): as in the schematic picture, a click over
  // its free chromosome meets the cytoplasm that lies over it, or the chromosome.
  const toScale = await selected(), free = !(await evaluate(`Boolean(${VIEWER}.current.species.cell.parts.nucleus ?? true)`));
  if (free) check("switch: to scale, a click over the free chromosome meets the cytoplasm that lies over it, or the chromosome", ["cap.reactions", atChromatin].includes(toScale), String(toScale));
  else check("switch: the to-scale nucleus can be clicked", toScale === atNucleus, String(toScale));
  await clear();
  await press("Schematic");
  } else {
    check("switch: a cell drawn in one size mode has no Sizes switch", !(await evaluate(`[...${VIEWER}.shadowRoot.querySelectorAll(".seg button")].some((item) => item.textContent === "To scale")`)));
  }
  // Labels are rebuilt for the mode and shown after the next drawn frame; wait for one.
  for (let tries = 0; tries < 60; tries++) {
    if (await evaluate(`Boolean(${VIEWER}.shadowRoot.querySelector(".label-part:not(.is-off)"))`)) break;
    await sleep(250);
  }
  await settled();

  // ---------------------------------------------------------------- input that starts on a label
  const label = await evaluate(`(() => {
    const shown = [...${VIEWER}.shadowRoot.querySelectorAll(".label-part:not(.is-off)")];
    const el = shown.find((item) => item.dataset.label === "cap.extracellular") || shown[0];
    const box = el.getBoundingClientRect();
    return { id: el.dataset.label, x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
  const before = await evaluate(`({ distance: ${VIEWER}.stage.rig.distance, azimuth: ${VIEWER}.stage.rig.azimuth })`);
  await mouse("mouseMoved", label.x, label.y, { button: "none", buttons: 0 });
  await wheel(label.x, label.y, 200);
  await until(`${VIEWER}.stage.rig.distance > ${before.distance * 1.05}`, 120);
  const afterWheel = await evaluate(`${VIEWER}.stage.rig.distance`);
  check("label: a wheel over a label zooms the camera", afterWheel > before.distance * 1.05, `${before.distance.toFixed(1)} -> ${afterWheel.toFixed(1)}`);

  const spot = await evaluate(`(() => {
    const el = ${VIEWER}.shadowRoot.querySelector('.label-part:not(.is-off)[data-label="${label.id}"]') || ${VIEWER}.shadowRoot.querySelector(".label-part:not(.is-off)");
    const box = el.getBoundingClientRect();
    return { id: el.dataset.label, x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
  await mouse("mouseMoved", spot.x, spot.y, { button: "none", buttons: 0 });
  await mouse("mousePressed", spot.x, spot.y);
  for (let step = 1; step <= 6; step++) await mouse("mouseMoved", spot.x + step * 20, spot.y);
  await mouse("mouseReleased", spot.x + 120, spot.y, { buttons: 0 });
  await until(`Math.abs(${VIEWER}.stage.rig.azimuth - ${before.azimuth}) > 0.2`, 120);
  const afterDrag = await evaluate(`${VIEWER}.stage.rig.azimuth`);
  check("label: a drag that starts on a label turns the camera", Math.abs(afterDrag - before.azimuth) > 0.2, `${before.azimuth.toFixed(2)} -> ${afterDrag.toFixed(2)}`);
  check("label: that drag selects nothing", (await selected()) === null, String(await selected()));

  // The drag leaves the camera gliding; on a busy machine it glides for longer than a fixed
  // wait. With the rich look drawn in software one frame may take seconds, so two reads a
  // moment apart can agree while the camera still moves: wait for drawn frames and a camera
  // that holds still (settled), read the label's place, and click there only once it is the
  // same after the next such wait.
  const place = () => evaluate(`(() => {
    const el = ${VIEWER}.shadowRoot.querySelector(".label-part:not(.is-off)");
    const box = el.getBoundingClientRect();
    return { id: el.dataset.label, x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
  await settled();
  let tap = await place();
  for (let tries = 0; tries < 40; tries++) {
    await settled();
    const next = await place();
    const still = next.id === tap.id && Math.abs(next.x - tap.x) < 0.5 && Math.abs(next.y - tap.y) < 0.5;
    tap = next;
    if (still) break;
  }
  await click(tap.x, tap.y);
  check("label: a plain click on a label selects its part", (await selected()) === tap.id, `${tap.id} -> ${await selected()}`);
  await clear();

  // A thread with a foot (E. coli's flagellum): the foot's panel has a door into the Protein atlas, on the
  // species' own proteins with the foot's set picked out. The foot is a few pixels wide, so it is chosen
  // by its name here; the door is pressed as a visitor presses it.
  const foot = await evaluate(`(() => { const lens = ${VIEWER}.current; const item = (lens.cells?.[lens.sizeMode]?.scenery || []).find((entry) => entry.kind === "base"); return item ? { id: item.id, mark: item.base?.mark ?? null, value: item.base?.value ?? null } : null; })()`);
  if (foot) {
    await evaluate(`${VIEWER}.select(${JSON.stringify(foot.id)})`);
    const door = `${VIEWER}.shadowRoot.querySelector("cells-panel .panel-door button")`;
    await until(`Boolean(${door})`, 60);
    const at = await evaluate(`(() => { const el = ${door}; if (!el) return null; el.scrollIntoView({ block: "nearest" }); const box = el.getBoundingClientRect(); return { x: box.left + box.width / 2, y: box.top + box.height / 2, words: el.textContent }; })()`);
    check("door: the foot of a thread has a panel with a door into the Protein atlas", Boolean(at) && /Protein atlas/.test(at.words), at ? at.words : "no door in the panel");
    if (at) {
      await click(at.x, at.y);
      await until(`${VIEWER}.state.lens === "proteins" && ${VIEWER}.current.mode === "own" && Boolean(${VIEWER}.current.mounted?.mark)`, 180);
      const there = await evaluate(`(() => { const lens = ${VIEWER}.current; return { lens: ${VIEWER}.state.lens, mode: lens.mode ?? null, mark: lens.mounted?.mark ?? null }; })()`);
      check("door: pressing it opens the species' own proteins with the foot's set picked out", there.lens === "proteins" && there.mode === "own" && there.mark?.name === foot.mark && there.mark?.value === String(foot.value), JSON.stringify(there));
      // Back to the Cell view, as the parts that follow expect.
      await evaluate(`${VIEWER}.setLens("cell", true)`);
      await until(`${VIEWER}.state.lens === "cell" && ${VIEWER}.current.active !== false`, 120);
    }
  }
  took("cell", cellFrom);

  }

  // ---------------------------------------------------------------- zoom across scales
  if (wants("zoom")) {
  const zoomFrom = Date.now();
  await open(cellView);
  await settled();
  for (let step = 0; step < 6; step++) {
    await wheel(640, 420, 240);
    await sleep(60);
  }
  await until(`(() => { const lens = ${VIEWER}.current; const fade = (name) => lens.zones.find((zone) => zone.name === name && lens.shows(zone)).fade; return fade("tissue") > 0.9 && fade("cell") < 0.1 && lens.activeStop === "tissue"; })()`, 300);
  await settled();
  const zoomed = await evaluate(`(() => { const lens = ${VIEWER}.current; const fade = (name) => lens.zones.find((zone) => zone.name === name && lens.shows(zone)).fade; return { distance: lens.stage.rig.distance, cell: fade("cell"), tissue: fade("tissue"), stop: lens.activeStop }; })()`);
  check("zoom: wheeling out from the cell fades in the sheet", zoomed.tissue > 0.9 && zoomed.cell < 0.1, JSON.stringify(zoomed));
  check("zoom: the scale rail follows", zoomed.stop === "tissue", zoomed.stop);
  const cellOfSheet = await screen(`${VIEWER}.current.probes.sheetCell.clone()`);
  await click(cellOfSheet.x, cellOfSheet.y);
  check("zoom: at the sheet, a click selects the sheet and not the faded cell", (await selected()) === "cap.sheet", String(await selected()));
  took("zoom", zoomFrom);
  }
} catch (error) {
  check("the run completed", false, error.message);
} finally {
  for (const line of pageLog) console.log(line);
  // Whether the page's own font had arrived by the end: with the stand-in, words run longer and cards stand
  // taller, and a miss is read against that.
  console.log(`note  the page's own font: ${await evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded")) ? "arrived" : "not arrived: the stand-in was shown, whose words run longer"`).catch(() => "not known")}`);
  check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
  socket.close();
  // Stop the browser and wait until it is gone, so that its profile folder can be removed.
  const closed = new Promise((resolve) => chrome.once("close", resolve));
  chrome.kill();
  await Promise.race([closed, sleep(4000)]);
  if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL");
  await Promise.race([closed, sleep(2000)]);
  server.close();
  release();
}
const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
