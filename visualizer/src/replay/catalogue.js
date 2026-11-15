// The catalogue of replays (scene.replays), read for the interface: which runs there
// are, what the experiment calls things, and the text a run shows before and after its
// file is loaded. Nothing here needs the 3D stage, so the list works without WebGL.
//
// A replay shows what the run recorded. It never computes a verdict of its own: the class
// shown is the one the experiment's summary records, in the experiment's own words.

import { clock, number } from "./format.js";

export const RUN = "run:";
export const CELL = "cell:";

export class Catalogue {
  constructor(replays) {
    this.raw = replays || { experiments: [], runs: [] };
    this.experiments = new Map((this.raw.experiments || []).map((experiment) => [experiment.id, experiment]));
    this.runs = this.raw.runs || [];
    this.byId = new Map(this.runs.map((run) => [run.id, run]));
  }

  experimentOf(run) {
    return this.experiments.get(run?.experiment) || { id: run?.experiment, label: run?.experiment || "Experiment" };
  }

  /** The experiment's own entry for a class id, or a plain stand-in when it has none. */
  classOf(run) {
    if (!run?.class) return null;
    const experiment = this.experimentOf(run);
    return (experiment.classes || []).find((item) => item.id === run.class) || { id: run.class, label: capitalise(run.class), description: "" };
  }

  /**
   * What an experiment found, as the record states it: whether it was judged, and what the
   * answer was. Two facts, shown side by side and never merged; the viewer derives neither.
   * Each fact has a mark (yes, no, mixed or none) that is drawn with words beside it.
   */
  outcomeOf(experiment) {
    const outcome = experiment?.outcome;
    if (!outcome) return null;
    const answer = outcome.judged && ["yes", "no", "mixed"].includes(outcome.answer) ? outcome.answer : null;
    return {
      judged: Boolean(outcome.judged),
      judgedMark: outcome.judged ? "yes" : "none",
      judgedLabel: outcome.judged ? "Judged" : "Not judged",
      status: outcome.status || "",
      answer,
      answerMark: answer || "none",
      label: answer ? outcome.label || "" : "",
      text: outcome.text || "",
      sources: outcome.sources || [],
      spoken: [outcome.judged ? "Judged" : "Not judged", answer ? outcome.label : ""].filter(Boolean).join(". "),
    };
  }

  /** How a run ended: the experiment's plain words for the run's own stop, and any refusal the run records. */
  endOf(run) {
    if (!run) return null;
    const words = this.experimentOf(run).stops?.[run.stop];
    // A refusal is the run's own record; it is put in a sentence, never judged here.
    const record = run.refusal;
    const refusal = !record ? null : typeof record === "string" ? record : [record.failed, record.time_s !== undefined ? `at ${record.time_s} s` : null].filter(Boolean).join(" ") || "recorded by the run";
    return { label: words?.label || (run.stop ? `Stopped: ${run.stop}` : ""), early: Boolean(words?.early), refusal };
  }

  /** A short name for a run in a list: its arm and seed, as the run's plan names them. */
  title(run) {
    return run.seed === null || run.seed === undefined ? run.arm : `${run.arm}, seed ${run.seed}`;
  }

  /** The runs as parts the list and the panel can show, grouped by experiment. */
  sections() {
    const groups = new Map();
    for (const run of this.runs) {
      if (!groups.has(run.experiment)) groups.set(run.experiment, []);
      groups.get(run.experiment).push(this.describe(run.id));
    }
    return [...groups].map(([id, entities]) => ({ label: this.experiments.get(id)?.label || id, entities }));
  }

  entities() {
    return this.runs.map((run) => this.describe(run.id));
  }

  /**
   * A run as the panel shows it. `loaded` is the opened Run, when its file is in: it adds
   * the run's own parameters and readouts and how the replay was made.
   */
  describe(id, loaded = null) {
    const run = this.byId.get(id.startsWith(RUN) ? id.slice(RUN.length) : id);
    if (!run) return null;
    const experiment = this.experimentOf(run);
    const group = experiment.groups?.[run.group];
    const klass = this.classOf(run);
    const chips = [];
    if (klass) chips.push({ label: `Recorded class: ${klass.label}`, title: klass.description });
    if (group) chips.push({ label: group.label, title: group.plain });
    if (run.stop) chips.push({ label: `Stopped at: ${run.stop}`, title: "How the run ended, in the run's own words." });
    const notes = [];
    if (klass?.description) notes.push(`${klass.label}: ${klass.description}`);
    if (experiment.class_note) notes.push(experiment.class_note);
    const facts = [
      ["Arm", run.arm],
      ...(run.seed === null || run.seed === undefined ? [] : [["Seed", String(run.seed)]]),
    ];
    if (run.label) facts.push(["Label", run.label]);
    if (Number.isFinite(run.end_s)) facts.push(["Length of the run", clock(run.end_s)]);
    if (run.records) facts.push(["Saved records", String(run.records)]);
    const sections = [];
    const info = loaded?.info;
    if (info) {
      for (const parameter of info.parameters || []) {
        const named = experiment.parameters?.[parameter.id];
        if (named) facts.push([named.label, value(parameter.value, named.unit)]);
      }
      if (info.engine_models?.length) facts.push(["Engine models", info.engine_models.join("; ")]);
      if (info.revision) facts.push(["Engine revision", info.revision]);
      const readouts = (info.readouts || [])
        .map((readout) => {
          const named = experiment.readouts?.[readout.id];
          if (!named) return null;
          return {
            label: named.label,
            detail: readout.value === null || readout.value === undefined ? "none recorded" : value(readout.value, named.unit),
            tag: readout.supplementary ? "Supplementary" : null,
            tag_title: "The experiment marks this readout as supplementary.",
            lines: named.plain ? [named.plain] : [],
            note: readout.supplementary ? readout.status || "The run marks this readout as supplementary." : null,
          };
        })
        .filter(Boolean);
      if (readouts.length) sections.push({ title: "What the run recorded", items: readouts });
      const records = [...loaded.records.values()]
        .filter((record) => record.set)
        .map((record) => ({
          label: experiment.records?.[record.id]?.label || record.label || record.id,
          detail: [record.unit && record.unit !== "1" ? `saved in ${record.unit}` : null, record.quantised ? "kept coarsely, for drawing only" : null].filter(Boolean).join(" · ") || null,
          lines: [experiment.records?.[record.id]?.plain, record.note].filter(Boolean),
        }));
      if (records.length) sections.push({ title: "Records in this replay", items: records });
    }
    const disclosures = [];
    if (loaded?.derivation.length) disclosures.push({ title: loaded.derived ? "How this replay was derived" : "How this replay was made", lines: loaded.derivation });
    return {
      id: RUN + run.id,
      label: this.title(run),
      eyebrow: experiment.label,
      kind: "run",
      plain: group?.plain || experiment.plain || "",
      note: notes.join(" ") || null,
      chips,
      facts,
      sections,
      disclosures,
      related: experiment.engine_entities?.length ? [{ title: "In the engine", ids: experiment.engine_entities }] : [],
      sources: experiment.sources || [],
      keywords: [run.id, run.arm, run.group, run.class].filter(Boolean).join(" "),
    };
  }
}

/** A plan or outcome value as text: numbers trimmed, the unit after it. */
export function value(raw, unit) {
  let text;
  if (typeof raw === "number") text = Number.isInteger(raw) ? String(raw) : number(raw, Math.abs(raw) >= 100 ? 1 : Math.abs(raw) >= 1 ? 2 : 4).replace(/\.?0+$/, "");
  else if (raw === null || raw === undefined) text = "none recorded";
  else if (typeof raw === "string") text = raw.replace(/_/g, " ");
  else text = JSON.stringify(raw);
  if (!unit || typeof raw !== "number") return text;
  return unit === "s" && raw >= 90 ? `${text} s (${clock(raw)})` : `${text} ${unit}`;
}

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1);
