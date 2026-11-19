// What the panel and the list say of an assembly view's parts (schema/ASSEMBLY_RUN.md). The shapes
// are the ones every view hands to <cells-panel> and <cells-index>. The list carries the same facts
// as the picture, fission by fission, so that it can stand in where 3D cannot be drawn.
//
// Words that must stand: an example's mark, wherever the run is one; "the picture's choice" for the
// shape, the layout and the map's axes; the run's own H as the run's, and the analysis's marks as
// the analysis's. No statistic of an example is stated.

import { PREFIX, sizeOf, typesHeld, similarity, formWords } from "./assembly_run.js";
import { COMPARE, valueAt } from "./similarity_marks.js";

const fixed = (h) => (h === null || h === undefined ? "not saved" : h.toFixed(3));
const typeName = (lens, i) => lens.set.environments.values().next().value.types[i] || `type ${i}`;

/** The run's mark at fission k, in words: the analysis's, or that none marks it. */
function markWords(run, k) {
  const threshold = run.threshold;
  const mark = run.inherited(k);
  if (mark === null) return "no analysis marks it";
  return `${mark ? "inherited" : "a break"}, by the analysis (${threshold.by}); its threshold ${threshold.value}${threshold.strict ? ", strictly above" : ""}`;
}

function exampleFacts(lens) {
  if (lens.set.example) return [["Invented numbers", `${lens.set.example.says}. Nothing it shows is a finding.`]];
  // A run of the engine: its standing as its file states it, and where that standing is recorded.
  const standing = lens.mainRun.file.development;
  return standing ? [["Standing", `${standing.says}${standing.from ? ` (${standing.from}; ${standing.run_states || "as given to the adapter"})` : ""}`]] : [];
}

/** What a run of the engine names of where it came from, as its record names it. */
function provenanceFacts(run) {
  const from = run.provenance;
  if (!from) return [];
  return [
    ["Revision", `${from.revision}${from.dirty === false ? ", clean" : from.dirty ? ", with changes not committed" : ""}`],
    ["Engine model", from.model],
    ["Laws", from.laws.join(", ")],
    ["Operators", from.operators.join(", ")],
    ["Definition", `sha256 ${from.definition_sha256}`],
    ["Run qualifier", from.qualifier],
    ["World", from.world],
    ["Run folder", `${from.folder} (${from.format})`],
  ];
}

/** What the run states of its law's check and of its ledger: each line its place in the run's record and the run's own text, with no gloss. */
function statedFacts(run) {
  return run.states.map((line) => [line.path, `${line.text}${line.unit ? ` ${line.unit}` : ""}`]);
}

function runFacts(run, lens) {
  // What the entry records of the law's forms in the engine's design (its note "law", with the record it cites).
  const law = lens.entry?.notes?.find((note) => note.id === "law");
  return [
    ["Run", `${run.label}: ${run.law.name}`],
    ...(run.form ? [["Form of the law", formWords(run)]] : []),
    ["Law of catalysis", run.law.says],
    ...(law ? [[law.label, `${law.text}${law.record?.length ? ` (${law.record.map((item) => `${item.path}, ${item.where}`).join("; ")})` : ""}`]] : []),
    ...provenanceFacts(run),
    ...(lens.papers() ? [["Its rules rest on", lens.papers()]] : []),
  ];
}

/** The panel's entity for an id of this view, or null. */
export function describe(lens, id) {
  if (!id || !id.startsWith(PREFIX)) return null;
  const [kind, ...rest] = id.slice(PREFIX.length).split(":");
  const run = lens.mainRun;
  const example = lens.mark ? [{ label: lens.mark }] : [];
  const base = { id, sources: lens.sourcesOf(), chips: example };
  switch (kind) {
    case "assembly": {
      const x = lens.compositionNow(run);
      return {
        ...base,
        label: "One assembly",
        eyebrow: `${lens.set.model.label} · ${run.label}`,
        kind: "assembly",
        plain: `A lipid for each molecule: ${sizeOf(x)} molecules of ${typesHeld(x)} types at the clock's time. It grows one molecule at a time to ${run.raw.rules?.fission_size ?? "its size"}, then splits in two; one daughter carries the lineage on and the other drifts off.`,
        note: `Drawn as lipids in water, ${{ protocell: "in a protocell, a closed shell of two faces with heads to the water outside and inside and the tails between, its faces drawn as soft glassy surfaces and its near side see-through", micelle: "in a micelle, heads to the water and tails in" }[lens.shape] || "in a loose cluster"}: the shape is the picture's choice. The model gives an assembly no shape, no place and no membrane; no law of Cells computes how the lipids move and pack, and the water, the paths in and out, the free molecules' number and every size are the picture's own. A molecule drawn coming in is a join of the run, one going out a leave (at this speed, ${lens.streamWords().replace(/^in, out: /, "")} drawn in flight); a soft halo marks it while it moves. ${lens.helpWords() || ""}`.trim(),
        facts: [...exampleFacts(lens), ...runFacts(run, lens), ["Molecules", String(sizeOf(x))], ["Types held", String(typesHeld(x))], ["Split", run.raw.rules?.split || "as the run states"], ["Carries on", run.raw.rules?.continues || "as the run states"]],
      };
    }
    case "composition": {
      const x = lens.compositionNow(run);
      const lead = lens.leading.map((type) => `${typeName(lens, type)}: ${x[type]}`).join(", ");
      return {
        ...base,
        label: "Its composition",
        eyebrow: "The wheel, the strip and the tape",
        kind: "composition",
        plain: "The list of counts drawn as shares: the wheel round the assembly, the strip beneath it. The types keep their places, t000 onward, so a change of mix is a change of widths.",
        note: "Shares are counts over the size: the view's own division.",
        facts: [...exampleFacts(lens), ["Molecules", String(sizeOf(x))], ["The three leading types", lead], ["The other types", "grey, in two tones that alternate between neighbours; round grey heads in the assembly"]],
      };
    }
    case "type": {
      const type = Number(rest[0]);
      const x = lens.compositionNow(run);
      const slot = lens.leading.indexOf(type);
      return {
        ...base,
        label: typeName(lens, type),
        eyebrow: "A molecule type",
        kind: "type",
        plain: `A molecule type of the environment. It has no chemistry of its own in the model: what it does comes from the table of catalysis. ${lens.leadingWords()}`.trim(),
        note: slot >= 0 ? `One of the three types that lead over the run: it wears a colour and a shape (${["a diamond", "a cube", "a tetrahedron"][slot]}), and in the assembly its lipids have a ${["soft diamond", "soft cube", "soft tetrahedron"][slot]} of a head.` : "Drawn grey, as every type but the three that lead over the run: in the assembly, a round grey head.",
        facts: [["In the assembly now", `${x[type]} of ${sizeOf(x)}`], ["Speeds itself by", `a factor of ${formatFactor(lens.mainEnvironment.catalysis(type, type))} (the table's diagonal)`], ["In the water", `held at ${lens.mainEnvironment.raw.reservoir?.each ?? "the run's"} by the run, as every type is: the free molecules drawn are the picture's number`]],
      };
    }
    case "run": {
      const which = lens.runById(rest[0]);
      if (!which) return null;
      return {
        ...base,
        label: which.label,
        eyebrow: `${lens.set.model.label} · a run`,
        kind: "run",
        plain: `${formWords(which)}. ${which.fissionCount} fissions, ${which.events ? which.events.length.toLocaleString("en-US") : "no saved"} events.`,
        note: which.states.length ? "What the run states of its law's check and of its ledger, line by line as its record writes them (the place in run.json, then its text). The view adds nothing to them and judges neither form." : null,
        facts: [...exampleFacts(lens), ...runFacts(which, lens), ...statedFacts(which)],
      };
    }
    case "fission": {
      const which = lens.runById(rest[0]) || run;
      const k = Number(rest[1]);
      const fission = which.fission(k);
      if (!fission) return null;
      const own = which.similarityAt(k);
      const facts = [
        ...exampleFacts(lens),
        ["Run", which.label],
        ["The parent", `${sizeOf(which.parent(k))} molecules of ${typesHeld(which.parent(k))} types, just before it splits`],
        ["Carries on", `the ${fission.continues} daughter, ${sizeOf(which.carried(k))} molecules`],
        ["H, parent with the daughter carried on", `${fixed(own.carried)}: the run's own`],
        ["H, parent with the other daughter", `${fixed(own.other)}: the run's own`],
        ["Marked", markWords(which, k)],
      ];
      if (fission.totals) facts.push(["Since the lineage began", `${fission.totals.joined} joined, ${fission.totals.left} left, ${fission.totals.discarded} let go with daughters not followed (the run's cumulative totals)`]);
      if (fission.nominal !== undefined) facts.push(["Nominal time", `${fission.nominal}: the model's own units, which carry no calibration`]);
      if (fission.keys) facts.push(["Carrier keys", `the parent ${fission.keys.parent}; the first daughter ${fission.keys.first}, the second ${fission.keys.second} (the run's own keys${which.raw.keys?.spelling ? `, ${which.raw.keys.spelling}` : ""})`]);
      const named = which.composomeAt(k);
      if (named) facts.push(["Composome", `${named.label || named.id}, named by the run's analysis (${which.composomes.method})`]);
      return { ...base, label: `Fission ${k}`, eyebrow: `${which.label} · a fission`, kind: "fission", plain: "The parent at its full size splits in two; one daughter carries the lineage on and the other is let go.", facts };
    }
    case "pair": {
      const which = lens.runById(rest[0]) || run;
      const [a, b] = [Number(rest[1]), Number(rest[2])];
      return {
        ...base,
        label: `Fissions ${a} and ${b}`,
        eyebrow: "A cell of the carpet",
        kind: "carpet",
        plain: "H of two grown assemblies, each just before its fission.",
        note: "Worked out by the view from the saved counts: the run saves H only across each fission.",
        facts: [["H", fixed(similarity(which.parent(a), which.parent(b)))]],
      };
    }
    case "entry": {
      const [, i, j] = rest.map(Number);
      return {
        ...base,
        label: `${typeName(lens, j)} on ${typeName(lens, i)}`,
        eyebrow: "An entry of the table of catalysis",
        kind: "catalysis",
        plain: `How much a molecule of ${typeName(lens, j)} in the assembly speeds the joining and the leaving of ${typeName(lens, i)}.`,
        facts: [["Factor", formatFactor(lens.mainEnvironment.catalysis(i, j))], ["Read as", `${lens.mainEnvironment.raw.catalysis.encoding}, from the run's environment`]],
      };
    }
    case "threshold": {
      const threshold = run.threshold;
      if (!threshold) return null;
      return {
        ...base,
        label: `The analysis's threshold, ${threshold?.value}`,
        eyebrow: "Inheritance",
        kind: "threshold",
        plain: threshold ? threshold.says : "The run states no threshold.",
        note: "Drawn only on the comparison it was made for: the parent with the daughter that carries on. The view reads each fission's mark and decides none.",
        facts: threshold ? [["Compares", threshold.compares], ["By", threshold.by], ["Strict", threshold.strict ? "yes: equality is a break" : "no"]] : [],
      };
    }
    case "composome": {
      const which = lens.runById(rest[0]) || run;
      const named = which.composomes?.names.find((name) => name.id === rest[1]);
      if (!named) return null;
      return { ...base, label: named.label || named.id, eyebrow: "A composome, as the run's analysis names it", kind: "composome", plain: `Named by ${which.composomes.method}.`, facts: [["Fissions", named.fissions.join(", ")]] };
    }
    case "part":
      return partOf(lens, rest[0], base);
    default:
      return null;
  }
}

function formatFactor(log10) {
  const value = 10 ** log10;
  if (value >= 100) return Math.round(value).toLocaleString("en-US");
  if (value >= 1) return value.toPrecision(3);
  return value.toPrecision(2);
}

/** The parts of the view, each with what it is and what is the picture's. */
export const PARTS = [
  { id: "table", label: "The table of catalysis", plain: "A row for each type i and a column for each type j: how much a molecule of type j in the assembly speeds the joining and the leaving of type i, on a logarithmic scale. A column stands on each entry of ten and more. It is the environment, which no assembly writes or inherits.", note: "The table is the run's; its layout as a floor is the picture's." },
  { id: "tape", label: "The tape", plain: "Each fission's parent as a column, types down from t000, a stronger colour for more molecules: long runs of the same mix show as level bands.", note: "After the form of the tapes in the model's own papers; the layout is the picture's choice." },
  { id: "fence", label: "Similarity at each fission", plain: "A post at each fission as tall as H, the run's own similarity of the parent with a daughter. A bead where the analysis marks the fission inherited, a ring where it marks a break.", note: "The analysis's threshold stands as a glass sheet, only on the comparison of the parent with the daughter that carries on." },
  { id: "carpet", label: "The carpet", plain: "H of every two grown assemblies, fission against fission: strong squares along the diagonal are stretches where the mix held; a strong patch away from it is a mix that came back.", note: "Worked out by the view from the saved counts. No threshold is drawn on it." },
  { id: "spine", label: "The lineage", plain: "The daughters that carry on, fission after fission; each fission's other daughter a faded stub, not followed. A ring where the analysis marks a break, a thin segment after it.", note: "The layout is the picture's choice." },
  { id: "map", label: "The map of compositions", plain: "Each grown assembly as a point, joined in order by the lineage's trail. Where the lineage stays, points crowd.", note: "Its axes are the three directions along which the lineage's compositions differ most, worked out by the view: the picture's choice. A crowd is named a composome only where the run's analysis names one." },
  { id: "population", label: "A population", plain: "Many assemblies at once in a fixed number of slots: one splits and another is removed.", note: "Not drawn yet: no run of a population exists, and the view reads none yet." },
];

function partOf(lens, which, base) {
  const part = PARTS.find((item) => item.id === which);
  if (!part) return null;
  const facts = [...exampleFacts(lens)];
  if (which === "fence") facts.push(["Comparing", COMPARE.find((item) => item.id === lens.compare).says]);
  // A run with no analysis (a run of the engine) marks no fission: every post and node wears the same plain cap.
  if ((which === "fence" || which === "spine") && !lens.mainRun.raw.analysis?.inheritance) facts.push(["Marks", "none: no analysis marks this run's fissions, so every cap is the same, and none says inherited or a break"]);
  if (which === "map" && lens.mainRun.composomes === null) facts.push(["Composomes", "none named: the run's analysis names none"]);
  return { ...base, label: part.label, eyebrow: "A part of the view", kind: "part", plain: part.plain, note: part.note, facts };
}

/** The list: the run, the parts, every fission with its H and mark, and the leading types. */
export function sections(lens) {
  const out = [];
  for (const run of lens.shownRuns) {
    out.push({
      label: `${run.label} · ${run.form && run.file.development ? formWords(run) : run.law.name}${lens.set.example ? " · example" : ""}`,
      limit: 12,
      entities: [...(run.states.length ? [{ id: `${PREFIX}run:${run.id}`, label: "What the run states: its law's check, its ledger", swatch: "origin-part", keywords: `run ledger check closure residual ${run.label}` }] : []), ...Array.from({ length: run.fissionCount }, (_, index) => {
        const k = index + 1, own = run.similarityAt(k), mark = run.inherited(k);
        return {
          id: `${PREFIX}fission:${run.id}:${k}`,
          label: `Fission ${k} · H ${own.carried.toFixed(3)}${mark === null ? "" : mark ? " · inherited" : " · a break"}`,
          swatch: mark === false ? "origin-break" : "origin-fission",
          keywords: `fission ${k} ${mark === false ? "break" : mark ? "inherited" : ""} ${run.label}`,
        };
      })],
    });
  }
  out.push({ label: "The view's parts", entities: [{ id: `${PREFIX}assembly`, label: "One assembly", swatch: "origin-part", keywords: "assembly micelle cluster lipids heads tails" }, { id: `${PREFIX}composition`, label: "Its composition", swatch: "origin-part", keywords: "wheel strip shares" }, ...PARTS.map((part) => ({ id: `${PREFIX}part:${part.id}`, label: part.label, swatch: "origin-part", keywords: part.plain }))] });
  out.push({ label: "The leading types", entities: lens.leading.map((type, slot) => ({ id: `${PREFIX}type:${type}`, label: typeName(lens, type), swatch: `origin-type-${slot + 1}`, keywords: "molecule type leading" })) });
  return out;
}

export { valueAt };
