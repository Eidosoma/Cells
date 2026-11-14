#!/usr/bin/env node
// Drives the viewer with real pointer input in headless Chrome, through the DevTools
// protocol (Node's built-in WebSocket; no extra dependency). Screenshots set state by
// query parameter and so never touch picking or the camera control; this does.
//
//   node tools/check_input.mjs            (CHECK_ONLY=engine|cell|zoom runs one part)

import { spawn } from "node:child_process";
import { createServer } from "./serve.mjs";

const chromeBinary = process.env.CHROME || "google-chrome";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};

const pageLog = [];
const server = createServer({ offline: true, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;

const chrome = spawn(
  chromeBinary,
  ["--headless=new", "--no-sandbox", "--mute-audio", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--remote-debugging-port=0", "--window-size=1280,800", "about:blank"],
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

  // ---------------------------------------------------------------- cell lens
  if (wants("cell")) {
  await open("lens=cell");
  const nucleus = await screen(probe("nucleus"));
  await click(nucleus.x, nucleus.y); // through the sketched gene-network cage around it
  check("cell: clicking the nucleus selects regulatory circuits", (await selected()) === "cap.circuits", String(await selected()));
  await clear();

  // Inside the cut-away octant the membrane is clipped; a click there must not select it.
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
  await press("To scale");
  const real = await evaluate(`(() => { const lens = ${VIEWER}.current; return { mode: lens.sizeMode, shown: lens.zones.filter((zone) => zone.root.visible).map((zone) => zone.name + ":" + zone.mode).join(" ") }; })()`);
  check("switch: Sizes to To scale shows the to-scale cell and hides the schematic one", real.mode === "real" && real.shown.includes("cell:real") && !real.shown.includes("cell:schematic"), real.shown);
  const nucleusToScale = await screen(probe("nucleus"));
  await click(nucleusToScale.x, nucleusToScale.y);
  check("switch: the to-scale nucleus can be clicked", (await selected()) === "cap.circuits", String(await selected()));
  await clear();
  await press("Schematic");
  // Labels are rebuilt for the mode and shown after the next drawn frame; wait for one.
  for (let tries = 0; tries < 60; tries++) {
    if (await evaluate(`Boolean(${VIEWER}.shadowRoot.querySelector(".label-part:not(.is-off)"))`)) break;
    await sleep(250);
  }

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
  await sleep(300);
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
  await sleep(300);
  const afterDrag = await evaluate(`${VIEWER}.stage.rig.azimuth`);
  check("label: a drag that starts on a label turns the camera", Math.abs(afterDrag - before.azimuth) > 0.2, `${before.azimuth.toFixed(2)} -> ${afterDrag.toFixed(2)}`);
  check("label: that drag selects nothing", (await selected()) === null, String(await selected()));

  const tap = await evaluate(`(() => {
    const el = ${VIEWER}.shadowRoot.querySelector(".label-part:not(.is-off)");
    const box = el.getBoundingClientRect();
    return { id: el.dataset.label, x: box.left + box.width / 2, y: box.top + box.height / 2 };
  })()`);
  await click(tap.x, tap.y);
  check("label: a plain click on a label selects its part", (await selected()) === tap.id, `${tap.id} -> ${await selected()}`);
  await clear();

  }

  // ---------------------------------------------------------------- zoom across scales
  if (wants("zoom")) {
  await open("lens=cell");
  for (let step = 0; step < 6; step++) {
    await wheel(640, 420, 240);
    await sleep(60);
  }
  await sleep(700);
  const zoomed = await evaluate(`(() => { const lens = ${VIEWER}.current; const fade = (name) => lens.zones.find((zone) => zone.name === name && lens.shows(zone)).fade; return { distance: lens.stage.rig.distance, cell: fade("cell"), tissue: fade("tissue"), stop: lens.activeStop }; })()`);
  check("zoom: wheeling out from the cell fades in the sheet", zoomed.tissue > 0.9 && zoomed.cell < 0.1, JSON.stringify(zoomed));
  check("zoom: the scale rail follows", zoomed.stop === "tissue", zoomed.stop);
  const cellOfSheet = await screen(`${VIEWER}.current.probes.sheetCell.clone()`);
  await click(cellOfSheet.x, cellOfSheet.y);
  check("zoom: at the sheet, a click selects the sheet and not the faded cell", (await selected()) === "cap.sheet", String(await selected()));
  }
} catch (error) {
  check("the run completed", false, error.message);
} finally {
  for (const line of pageLog) console.log(line);
  check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
  socket.close();
  chrome.kill();
  server.close();
}
const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
