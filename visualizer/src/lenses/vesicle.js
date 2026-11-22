import * as T from "../three.js";
import { Player } from "../replay/player.js";
import { h, svg } from "../ui/dom.js";
import { registerEntryView } from "../ui/entry_views.js";
import { Water } from "./lipid_water.js";
import { VesicleScene } from "./vesicle_scene.js";
import { VesicleRun } from "./vesicle_run.js";

const levels = [
  ["vesicle", "Vesicle"],
  ["membrane", "Membrane"],
  ["molecule", "Molecule"],
];
const fmt = (n, unit = "") =>
  n == null
    ? "Unrecorded"
    : (Number.isInteger(n) ? n.toLocaleString("en-US") : n.toLocaleString("en-US", { maximumSignificantDigits: 5 })) +
      (unit ? " " + unit : "");
const sci = (n, unit) => (n == null ? "Unrecorded" : (n === 0 ? "0" : n.toExponential(3)) + " " + unit);
function choose(label, options, value, set) {
  return h(
    "label",
    { class: "v-choice" },
    h("span", {}, label),
    h(
      "select",
      { class: "run-select", "aria-label": label, onchange: (e) => set(e.target.value) },
      options.map(([v, t]) => h("option", { value: v, selected: v === value }, t)),
    ),
  );
}
const arrow = (a, b) => a + " → " + b;
function series(run, slot) {
  if (run.pop)
    return {
      title: "Vesicles surviving",
      max: run.founders,
      points: [
        [run.start, run.founders],
        ...run.ruptures.map((e, i) => [e.time, run.founders - i - 1]),
        [run.end, run.survivors(run.end)],
      ],
    };
  const samples = run.rows.flatMap((r) => (r.slots[slot]?.tension_N_per_m == null ? [] : [[r.t, r.slots[slot].tension_N_per_m]]));
  return { title: "Recorded tension", max: run.maxTension, points: samples };
}
function chart(view) {
  const run = view.run,
    s = series(run, view.slot);
  if (!s.points.length) return null;
  const x = (t) => 3 + (194 * (t - run.start)) / (run.end - run.start || 1),
    y = (n) => 43 - (37 * n) / (s.max || 1);
  const d = s.points.map(([t, n], i) => (i ? "H" + x(t) + "V" + y(n) : "M" + x(t) + " " + y(n))).join(" ");
  const cursor = svg("line", { x1: 3, x2: 3, y1: 2, y2: 46, stroke: "currentColor", "stroke-width": 1 });
  view.moveCursor = (t) => {
    cursor.setAttribute("x1", x(t));
    cursor.setAttribute("x2", x(t));
  };
  const pic = svg("svg", { viewBox: "0 0 200 48", role: "img", "aria-label": s.title });
  pic.append(
    svg("line", { x1: 3, x2: 197, y1: 43, y2: 43, stroke: "currentColor", opacity: 0.28 }),
    svg("path", { d, fill: "none", stroke: "#258b89", "stroke-width": 2.2, "stroke-linejoin": "round" }),
  );
  for (const e of run.file.releases)
    if (!run.pop && e.cause === "threshold")
      pic.append(svg("circle", { cx: x(e.time), cy: y(e.tension_N_per_m), r: 3, fill: "#d5763d" }));
  pic.append(cursor);
  return h(
    "figure",
    { class: "v-chart" },
    h("figcaption", {}, s.title + " · " + (s.max ? "0–" : "") + (run.pop ? fmt(s.max) : sci(s.max, "N/m"))),
    pic,
    h("div", {}, h("span", {}, fmt(run.start, "s")), h("span", {}, fmt(run.end, "s"))),
  );
}
function placeList(run, counts, phase) {
  return run.places
    .filter((p) => p.phase === phase)
    .map((p) => p.species + " " + fmt(counts[p.index]))
    .join(" · ");
}
export class VesicleLens {
  constructor(stage, labels, entries, autoplay) {
    this.stage = stage;
    this.labels = labels;
    this.id = "vesicle";
    this.wantsLeftRoom = true;
    this.entries = entries.map((item) => ({ label: item.label, run: new VesicleRun(item.data) }));
    if (!this.entries.length) throw Error("The vesicle view needs a saved development run.");
    this.scene = new VesicleScene();
    this.root = this.scene.root;
    this.water = new Water({ narrow: stage.width < 700 });
    this.water.setLevel("assembly");
    this.water.setTheme(Boolean(stage.palette?.dark));
    this.player = new Player();
    this.level = "vesicle";
    this.layer = "species";
    this.autoplay = autoplay && !stage.reducedMotion;
    this.run = this.entries[0].run;
    this.slot = Math.max(0, this.run.rows[0].slots.findIndex(Boolean));
    this.player.load(this.run);
    this.tickView = () => {
      this.inspectRow = null;
      if (this.active) this.sync();
    };
    this.player.addEventListener("time", this.tickView);
    this.wake = () => this.stage.invalidate?.();
    this.player.addEventListener("state", this.wake);
  }
  activate() {
    this.active = true;
    this.stage.scene.add(this.root);
    this.water.attach(this.stage.scene);
    this.stage.dress?.({ rich: true, filmic: false, contact: false });
    this.stage.rig.limits = { minDistance: 1.1, maxDistance: 30, minPolar: 0.08, maxPolar: Math.PI - 0.08 };
    this.fit();
    this.names();
    this.sync();
    if (this.autoplay) this.player.play();
  }
  deactivate() {
    this.autoplay = this.player.playing;
    this.player.pause();
    this.active = false;
    this.stage.scene.remove(this.root);
    this.water.detach();
    this.labels.clear();
    this.stage.dress?.({ rich: false });
  }
  dispose() {
    this.player.removeEventListener("time", this.tickView);
    this.player.removeEventListener("state", this.wake);
    if (this.active) this.deactivate();
    this.scene.dispose();
    this.water.dispose();
  }
  applyPalette(p) {
    this.water.setTheme(Boolean(p.dark));
    this.stage.invalidate?.();
  }
  fit() {
    const narrow = this.stage.width < 700,
      patch = this.level === "membrane",
      mol = this.level === "molecule";
    this.stage.rig.setView({
      target: new T.Vector3(),
      distance: (mol ? 10.9 : patch ? 9.5 : 9.3) * (narrow ? 1.48 : 1),
      azimuth: mol ? 0.02 : patch ? 0.51 : 0.26,
      polar: mol ? 1.3 : patch ? 1.22 : 1.23,
    });
  }
  levels() {
    return levels.map(([id, label]) => ({ id, label, active: id === this.level }));
  }
  setLevel(id) {
    if (!levels.some(([k]) => k === id)) return;
    this.level = id;
    this.scene.signature = "";
    this.fit();
    this.names();
    this.refresh();
  }
  setRun(id) {
    const next = this.entries.find((e) => e.run.file.id === id)?.run;
    if (!next) return;
    const playing = this.player.playing;
    this.run = next;
    this.slot = Math.max(0, next.rows[0].slots.findIndex(Boolean));
    this.player.load(next);
    this.level = "vesicle";
    this.fit();
    this.names();
    this.refresh();
    if (playing) this.player.play();
  }
  seek(t) {
    this.inspectRow = null;
    this.player.pause();
    this.player.seek(t);
    this.sync();
  }
  refresh() {
    this.onChrome?.();
    this.sync();
  }
  names() {
    this.labels.clear();
    this.tags = {};
    const add = (key, text, x, y, z) => {
      const part =
        { shell: "membrane", outer: "membrane", inner: "membrane", core: "membrane", head: "molecule", tails: "molecule" }[key] || key;
      this.tags[key] = this.labels.add({ id: "vesicle:" + part, text, anchor: new T.Vector3(x, y, z), priority: 600, lift: 4 });
    };
    if (this.level === "molecule") {
      add("head", "Phosphocholine head", -0.3, -0.64, 0.2);
      add("tails", "Hydrocarbon chains", 1.5, 0.28, 0.2);
    } else if (this.level === "membrane") {
      add("outer", "Pool-facing heads", 1.15, 0.68, 0.4);
      add("core", "Hydrocarbon core", -1.35, 0.03, 0.75);
      add("inner", "Lumen-facing heads", 0.75, -0.68, 0.8);
    } else if (!this.run.pop) {
      add("shell", "Membrane", 1.6, 0.45, 0.8);
      add("lumen", "Lumen", 0, -0.2, 1);
      add("daughter", "Other daughter · leaves lineage", 2.0, 0.6, -0.3);
      add("release", "Release", 0, 0.56, 0.35);
    }
  }
  has(id) {
    if (this.run.pop && /^vesicle:slot:\d+$/.test(id)) return Boolean(this.run.rows[0].slots[Number(id.slice(13))]);
    return ["membrane", "lumen", "molecule", "release", "daughter"].some((k) => id === "vesicle:" + k);
  }
  setSelection(id) {
    this.selected = id;
    if (id) this.player.pause();
    if (id?.startsWith("vesicle:slot:") && this.has(id)) {
      this.slot = Number(id.slice(13));
      this.refresh();
    }
  }
  describe(id) {
    if (!this.has(id)) return null;
    const state = this.run.at(this.player.time, this.slot, this.inspectRow),
      sample = state.sample,
      e = state.event;
    const part = id.slice(8),
      title = {
        membrane: "Lipid bilayer",
        lumen: "Aqueous lumen",
        molecule: "POPC molecular reference",
        daughter: "Daughters at shear",
        release: "Molecules returned",
      };
    const entity = {
      id,
      label: title[part],
      eyebrow: "Vesicle replay",
      kind: "part",
      sources: [],
      facts: [["Run time", fmt(this.player.time, "s")]],
    };
    if (part.startsWith("slot:")) {
      const i = Number(part.slice(5)),
        s = this.run.at(this.player.time, i).sample;
      entity.label = "Vesicle in slot " + (i + 1);
      entity.plain = "The same position follows this founder through the held-tension run.";
      entity.facts.push(["Carrier key", this.run.rows[0].slots[i].key], ["State", s ? "Living" : "Ruptured"]);
      if (s) entity.facts.push(["Footprint", fmt(s.membrane_footprint_quanta, "quanta")]);
    }
    if (part === "membrane") {
      entity.plain =
        "The headgroups face water on both surfaces. The tails point into the membrane core. The displayed shell area follows the recorded footprint.";
      entity.facts.push(
        ["Footprint", fmt(sample?.membrane_footprint_quanta, "quanta")],
        ["Membrane counts", placeList(this.run, state.counts, "membrane")],
      );
    }
    if (part === "lumen") {
      entity.plain = "The blue volume follows the recorded lumen volume. Each dot illustrates a sample of the dissolved contents.";
      entity.facts.push(["Volume", sci(sample?.lumen_volume_L, "L")], ["Solute counts", placeList(this.run, state.counts, "lumen")]);
    }
    if (part === "molecule") {
      entity.plain =
        "A named phospholipid from the wwPDB Chemical Component Dictionary. The ideal coordinates illustrate a headgroup and its hydrocarbon chains.";
      entity.facts.push(["Reference", "POPC · LBN"], ["Representation", "Heavy atoms and bonds"]);
    }
    if (part === "daughter") {
      entity.plain = "The marker identifies the daughter that leaves the lineage. Its separate footprint was not recorded.";
      for (const [i, d] of (e?.daughters || []).entries())
        entity.facts.push([
          "Daughter " + (i + 1) + (i === e.followed ? " · continues" : " · leaves"),
          placeList(this.run, d.counts, "membrane") + " · " + placeList(this.run, d.counts, "lumen"),
        ]);
    }
    if (part === "release") {
      entity.plain = e?.cause
        ? "The pool destinations and numbers come from the release event."
        : "No release has occurred at this time.";
      if (e?.cause) entity.facts.push(["Cause", e.cause], ...Object.entries(e.returned).map(([p, n]) => [p, fmt(n)]));
    }
    return entity;
  }
  controls() {
    const run = this.run,
      file = run.file,
      stand = file.development;
    this.metrics = h("div", { class: "v-metrics" });
    this.eventRead = h("p", { class: "v-event" });
    this.recordRead = h("p", { class: "v-record" });
    this.moveCursor = null;
    const selections = [
      choose(
        "Replay",
        this.entries.map((e) => [e.run.file.id, e.label]),
        file.id,
        (v) => this.setRun(v),
      ),
      this.level === "vesicle" && !run.pop && run.hasTension
        ? choose(
            "Colour by",
            [
              ["species", "Membrane species"],
              ["tension", "Recorded tension"],
            ],
            this.layer,
            (v) => {
              this.layer = v;
              this.refresh();
            },
          )
        : null,
      run.pop
        ? choose(
            "Vesicle",
            run.rows[0].slots.flatMap((s, i) => (s ? [[String(i), "Slot " + (i + 1) + " · key " + s.key]] : [])),
            String(this.slot),
            (v) => {
              this.slot = Number(v);
              this.refresh();
            },
          )
        : null,
    ];
    const marks = run.events.map((e, i) => [String(i), fmt(e.time, "s") + " · " + e.label]);
    const navigate = marks.length
      ? choose("Go to event", [["", "Choose an event…"], ...marks], "", (v) => {
          if (v !== "") this.seek(run.events[Number(v)].time);
        })
      : null;
    const burst = file.releases.find((e) => e.cause === "threshold");
    const intact = burst ? run.rows.findLastIndex((r) => r.t === burst.time && r.slots[this.slot]?.membrane_footprint_quanta > 0) : -1;
    const boundary =
      intact < 0
        ? null
        : h(
            "div",
            { class: "v-boundary" },
            h(
              "button",
              {
                type: "button",
                onclick: () => {
                  this.seek(burst.time);
                  this.inspectRow = intact;
                  this.sync();
                },
              },
              "Last intact state",
            ),
            h("button", { type: "button", onclick: () => this.seek(burst.time) }, "Released state"),
          );
    const geometry =
      this.level === "molecule"
        ? "POPC · wwPDB LBN ideal conformer. The run names its membrane species " +
          run.membrane.map((p) => p.species).join(" and ") +
          ". POPC is shown as a separate structural reference. Hydrogens are hidden."
        : this.level === "membrane"
          ? "This structural close-up shows the two water-facing headgroup surfaces and the hydrocarbon tails between them. It remains available after release."
          : null;
    const read = h(
      "details",
      { class: "v-record-details" },
      h("summary", {}, "Read the record"),
      this.recordRead,
      h("p", {}, stand.ol5),
      h("p", {}, stand.judging),
      stand.rupture ? h("p", {}, stand.rupture) : null,
      h("p", {}, stand.picture),
      h(
        "p",
        {},
        "The run supplies no spatial coordinates. Lipid markers and solute dots sample the contents for visibility. Exact counts appear above.",
      ),
      h("p", {}, "These exact-event vesicles hold thousands of molecules. A 100 nm vesicle holds about 2 × 10⁵ amphiphiles."),
      file.holds.length
        ? h("p", {}, "Pores in these runs rupture immediately. Opening and resealing are outside this recorded model.")
        : null,
      h("p", {}, "Engine " + file.source.revision + " · run " + file.id),
    );
    const contents = h(
      "div",
      { class: "v-controls" },
      h("p", { class: "v-standing" }, stand.says),
      selections,
      geometry ? h("p", { class: "v-explain" }, geometry) : null,
      this.metrics,
      chart(this),
      this.eventRead,
      navigate,
      boundary,
      read,
    );
    if (this.active) this.updateReadout(this.run.at(this.player.time, this.slot, this.inspectRow));
    return [contents];
  }
  updateReadout(state) {
    if (!this.metrics) return;
    const run = this.run,
      t = this.player.time,
      s = state.sample,
      e = state.event,
      rows = [];
    if (run.pop) rows.push(["Surviving", run.survivors(t) + " / " + run.founders]);
    rows.push(
      ["Membrane", placeList(run, state.counts, "membrane") || "—"],
      ["Lumen solutes", placeList(run, state.counts, "lumen") || "—"],
      ["Footprint", fmt(s?.membrane_footprint_quanta, "quanta")],
      ["Lumen volume", sci(s?.lumen_volume_L, "L")],
      [state.hold ? "Held tension" : "Tension", sci(state.hold?.sigma_N_per_m ?? s?.tension_N_per_m, "N/m")],
    );
    const read = rows.map((r) => r.join(" ")).join("|");
    if (this.metrics.dataset.values !== read) {
      this.metrics.dataset.values = read;
      this.metrics.replaceChildren(...rows.map(([k, v]) => h("div", {}, h("span", {}, k), h("strong", {}, v))));
    }
    const moves = run.movements(state.lastChannel);
    let what = state.n
      ? "Event " +
        state.n +
        " · " +
        (moves.length
          ? moves.map((m) => m.from.species + " " + arrow(m.from.phase, m.to.phase)).join(", ")
          : state.lastChannel?.step || "")
      : "Founder at the start of the run";
    if (e && (t === e.time || e.cause || t - e.time < 1.4)) {
      if (e.cause) {
        what =
          e.label +
          " at " +
          fmt(e.time, "s") +
          ". Cause " +
          e.cause +
          ". " +
          (e.cause === "threshold"
            ? "Trigger " + sci(e.tension_N_per_m, "N/m") + ", threshold " + sci(e.threshold_N_per_m, "N/m") + ". "
            : "") +
          "Returned " +
          Object.entries(e.returned)
            .map(([name, count]) => fmt(count) + " " + name)
            .join(", ") +
          ".";
      } else if (e.outcome === "split") {
        what =
          e.label +
          " at " +
          fmt(e.time, "s") +
          ". " +
          e.daughters
            .map(
              (d, j) =>
                "Daughter " +
                (j + 1) +
                " (" +
                (j === e.followed ? "continues" : "leaves") +
                ") " +
                [placeList(run, d.counts, "membrane"), placeList(run, d.counts, "lumen")].filter(Boolean).join(", "),
            )
            .join(". ") +
          ". Shear work " +
          fmt(e.shear_work_kT, "kT") +
          ".";
      } else what = e.label + " at " + fmt(e.time, "s") + ". The parent carries on.";
    }
    if (this.inspectRow != null)
      what = "Last intact state at " + fmt(t, "s") + ". The triggering step and release have this same timestamp.";
    this.eventRead.textContent = what;
    this.recordRead.textContent =
      "Geometry sampled at " +
      state.row.t +
      " s. The values hold until the next recorded row. With the time slider focused, the arrow keys step through the saved events.";
    this.moveCursor?.(t);
  }
  sync() {
    const t = this.player.time,
      s = this.run.at(t, this.slot, this.inspectRow);
    this.scene.draw(s, this.run, this.level, this.layer, t, this.slot);
    this.updateReadout(s);
    if (this.tags?.shell) {
      const rad = 2.25 * Math.sqrt((s.sample?.membrane_footprint_quanta || 0) / (this.run.maxFoot || 1));
      this.tags.shell.anchor.set(rad * 0.77, rad * 0.32, rad * 0.41);
      this.tags.shell.hidden = !this.scene.whole.visible;
      this.tags.lumen.hidden = !this.scene.whole.visible || !this.scene.liquid.visible;
      this.tags.daughter.hidden = !this.scene.daughter.visible;
      this.tags.release.hidden = !this.scene.release.visible;
      if (!this.tags.release.hidden) this.labels.setText(this.tags.release, s.event.label);
    }
    this.stage.invalidate?.();
  }
  update(dt, time, real) {
    if (!this.active) return false;
    this.player.tick(real ?? dt);
    this.water.setTime(this.player.time);
    this.water.face(this.stage.camera);
    this.water.setViewport(this.stage.height || 600, this.stage.renderer?.getPixelRatio?.() || 1);
    return this.player.playing;
  }
  chrome() {
    const f = this.run.file;
    const structure = this.level === "molecule";
    let items, note;
    if (structure) {
      items = [
        ["Carbon (C)", "carbon"],
        ["Oxygen (O)", "oxygen"],
        ["Nitrogen (N)", "nitrogen"],
        ["Phosphorus (P)", "phosphorus"],
      ];
      note = "The bonds and heavy-atom coordinates come from the wwPDB POPC ideal conformer.";
    } else if (this.run.pop && this.level === "vesicle") {
      items = [
        ["Living vesicle", "head"],
        ["Selected vesicle or rupture rim", "high"],
      ];
      note = "Each position identifies a slot. A rupture removes one founder from the survival staircase at the event’s recorded time.";
    } else {
      items =
        this.level === "vesicle" && this.layer === "tension"
          ? [["0 N/m", "head"], ...(this.run.maxTension ? [[sci(this.run.maxTension, "N/m"), "high"]] : [])]
          : this.run.membrane.map((p, i) => [p.species + " headgroup", "species-" + (i % 4)]);
      items.push(["Hydrocarbon tails", "tail"], ["Lumen water", "lumen"]);
      note =
        "Shell area follows membrane footprint. The blue volume follows recorded litres. Lipid packing and molecular positions are illustrative.";
    }
    return {
      card: {
        heading: "Vesicle replay",
        organism: "",
        stats: [],
        own: () => this.controls(),
        sources: [
          { name: "Saved development run", licence: f.source.revision },
          {
            name: "POPC ideal coordinates · wwPDB Chemical Component Dictionary",
            url: "https://www.rcsb.org/ligand/LBN",
            licence: "PDB archive · CC0",
          },
        ],
      },
      stamp: f.development.says,
      caveat: f.development.says,
      legend: {
        title: structure ? "POPC atoms" : "Reading the vesicle",
        items: items.map(([label, swatch]) => ({ label, swatch: "ves-" + swatch })),
        note: { text: note },
      },
      timeline: {
        player: this.player,
        stops: true,
        eventWord: "event",
        read: (t) => ({ now: fmt(t, "s"), of: " of " + fmt(this.run.end, "s") }),
      },
    };
  }
}
const styles = `
.v-controls{display:grid;gap:8px}.v-choice{display:grid;gap:3px}.v-choice>span,.v-chart figcaption{font-size:11px;font-weight:650;color:var(--muted)}
.v-controls .run-select{width:100%;min-width:0}.v-metrics{display:grid;gap:4px;font-size:12px;font-variant-numeric:tabular-nums}
.v-boundary{display:flex;gap:5px}.v-boundary button{border:1px solid var(--line);border-radius:6px;background:var(--bg-raised);color:var(--fg);padding:5px;flex:1}
.v-standing{font-size:11px;line-height:1.4;color:var(--muted);margin:0}
.v-metrics>div{display:flex;justify-content:space-between;align-items:baseline;gap:6px}.v-metrics strong{text-align:right}.v-metrics span,.v-explain,.v-record{color:var(--muted)}
.v-chart{margin:1px 0}.v-chart svg{width:100%;height:38px;display:block}.v-chart>div{display:flex;justify-content:space-between;color:var(--muted);font-size:10px}
.v-event,.v-record,.v-explain{margin:0;font-size:12px;line-height:1.4}.v-event{border-left:2px solid #459c90;padding-left:7px}.v-record-details{font-size:12px;overflow-wrap:anywhere}
.view:has(.v-controls){max-height:calc(100% - 148px);overflow:auto}.swatch-ves-head,.swatch-ves-species-0{background:#50c6b3}.swatch-ves-species-1{background:#aa9bd6}.swatch-ves-species-2{background:#e6bd6d}.swatch-ves-species-3{background:#91bbdc}.swatch-ves-high{background:#e88b4c}.swatch-ves-carbon{background:#72a7a4}.swatch-ves-oxygen{background:#ed785f}.swatch-ves-nitrogen{background:#5476d4}.swatch-ves-phosphorus{background:#eeb64f}.swatch-ves-tail{background:#b89670}.swatch-ves-lumen{background:#489fbe}
.frame:has(.v-controls) .caveat{display:none}
@media(max-width:759px){.frame:has(.v-controls) .caveat{display:block;left:50%;top:119px;bottom:auto;margin:0;width:min(330px,calc(100% - 38px));font-size:11px}.frame.view-open:has(.v-controls) .caveat{display:none}.card-folds.view-open .view:has(.v-controls){max-height:min(45%,360px);}.v-controls{gap:6px}.v-boundary button{min-height:42px}}
`;
registerEntryView("vesicle", {
  label: "Vesicle replay",
  short: "Vesicle",
  make: (stage, model, labels, { runs, autoplay }) => new VesicleLens(stage, labels, runs, autoplay),
  styles: { shadow: styles },
});
