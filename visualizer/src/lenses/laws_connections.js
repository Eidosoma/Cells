// The atlas groups the library's existing model memberships. A field belongs to the
// declaration that names it; a matching string in another piece never creates an edge.
import { engineId, pageId } from "./laws_data.js";

export const howLabel = { direct: "Direct declaration", inner: "Via inner model", kind: "Via host kind" };
export const relationLabel = {
  direct: "declares",
  inner: "via inner model",
  kind: "via host kind",
  requires: "requires",
  requiredBy: "required by",
  readBy: "read by",
  reads: "reads",
  hosts: "hosts",
  hostedBy: "hosted by",
  writes: "writes",
  ledgers: "ledger",
  provides: "provides",
  owns: "owns",
  conflicts: "cannot combine with",
};
export const familyKey = (id) => pageId("family/" + encodeURIComponent(id));
export const bridgeKey = (model, family) => pageId("bridge/" + encodeURIComponent(model) + "/" + encodeURIComponent(family));
export const fieldKey = (piece, verb, field) => pageId(["field", piece, verb, field].map(encodeURIComponent).join("/"));
export function partsOf(id) {
  try {
    return (engineId(id) || "").split("/").map(decodeURIComponent);
  } catch {
    return [];
  }
}
export function displayName(id) {
  return String(id)
    .replace(/^(?:[a-z][\w]*\.[a-z][\w]*\.|cells\.)/, "")
    .replace(/_/g, " ")
    .replace(/@(\d+)$/, " · v$1");
}
export function modelName(frame) {
  const words = frame.id
    .replace(/^(?:[a-z][\w]*\.[a-z][\w]*\.|cells\.)/, "")
    .replace(/^resolved_pump_/, "")
    .replace(/_/g, " ")
    .replace(/@(\d+)$/, " @$1");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
export class LawConnections {
  constructor(library, scene = null) {
    this.library = library;
    this.bundles = new Map();
    this.members = new Map(library.frames.map((frame) => [frame.id, new Set()]));
    this.incoming = new Map();
    this.readers = new Map();
    this.operatorLinks = new Map();
    // Only use the Engine map's explicit operator edges when it describes this same revision.
    if (scene?.meta?.revision && library.manifest.revision.startsWith(scene.meta.revision)) {
      for (const edge of scene.relations || []) {
        if (!["reads", "writes", "conflicts"].includes(edge.kind) || !edge.from.startsWith("op.") || !edge.to.startsWith("op.")) continue;
        const a = library.piece(edge.from.slice(3)),
          b = library.piece(edge.to.slice(3));
        if (a?.declared?.piece !== "operator" || b?.declared?.piece !== "operator") continue;
        for (const [owner, peer, incoming] of [
          [a, b, false],
          [b, a, true],
        ]) {
          if (!this.operatorLinks.has(owner.id)) this.operatorLinks.set(owner.id, []);
          this.operatorLinks.get(owner.id).push({
            kind: edge.kind,
            peer,
            incoming,
            fields: (edge.label || "")
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          });
        }
      }
    }
    for (const piece of library.pieces) {
      for (const entry of piece.declared_by) {
        const id = bridgeKey(entry.frame, piece.family);
        if (!this.bundles.has(id)) this.bundles.set(id, { id, model: entry.frame, family: piece.family, entries: [] });
        this.bundles.get(id).entries.push({ piece, ...entry });
        this.members.get(entry.frame).add(piece.id);
      }
      for (const read of piece.declared?.reads || []) {
        const target = library.byKey.get(read.name);
        if (!target?.declared) continue;
        if (!this.readers.has(target.id)) this.readers.set(target.id, new Set());
        this.readers.get(target.id).add(piece);
      }
      for (const name of this.requirements(piece)) {
        const target = library.piece(name);
        if (!target) continue;
        if (!this.incoming.has(target.id)) this.incoming.set(target.id, []);
        this.incoming.get(target.id).push(piece);
      }
    }
  }
  requirements(piece) {
    const r = piece.declared?.requires;
    return [...new Set([...(r?.laws || []), ...(r?.kinds || [])])];
  }
  compare(left, right) {
    const a = this.members.get(left),
      b = this.members.get(right);
    const groups = [[], [], []];
    for (const p of this.library.pieces) {
      if (a?.has(p.id)) groups[b?.has(p.id) ? 1 : 0].push(p);
      else if (b?.has(p.id)) groups[2].push(p);
    }
    return groups;
  }
  neighbours(piece) {
    const d = piece.declared,
      out = [];
    for (const { frame, how, via } of piece.declared_by) {
      out.push({ id: pageId(frame), label: modelName(this.library.frame(frame)), verb: how, layer: "models", incoming: true, via });
    }
    for (const name of this.requirements(piece)) {
      const other = this.library.piece(name);
      out.push({ id: other ? pageId(other.id) : null, label: displayName(name), name, verb: "requires", layer: "pieces" });
    }
    for (const p of this.incoming.get(piece.id) || [])
      out.push({ id: pageId(p.id), label: displayName(p.id), verb: "requiredBy", layer: "pieces", incoming: true });
    const host = this.library.byKey.get(d?.host);
    if (host?.declared && host !== piece)
      out.push({id: pageId(host.id), label: displayName(host.id), verb: "hostedBy", layer: "pieces"});
    for (const name of d?.laws || []) {
      const child = this.library.byKey.get(name);
      if (child?.declared) out.push({id: pageId(child.id), label: displayName(child.id), verb: "hosts", layer: "pieces"});
    }
    const field = (verb, name, note) =>
      out.push({ id: fieldKey(piece.id, verb, name), label: name.replace(/_/g, " "), name, note, verb, layer: "fields" });
    const reads = new Map();
    for (const read of d?.reads || []) {
      if (!read.name) continue;
      if (!reads.has(read.name)) reads.set(read.name, new Set());
      reads.get(read.name).add([read.mode, read.stage, read.scoped ? "scoped" : ""].filter(Boolean).join(" · "));
    }
    for (const [name, notes] of reads) {
      const note = [...notes].filter(Boolean).join(", ");
      const target = this.library.byKey.get(name);
      if (target?.declared) out.push({id: pageId(target.id), label: displayName(target.id), verb: "reads", name, note, layer: "pieces"});
      else field("reads", name, note);
    }
    for (const reader of this.readers.get(piece.id) || [])
      out.push({id: pageId(reader.id), label: displayName(reader.id), verb: "readBy", incoming: true, layer: "pieces"});
    for (const [name, entries] of Object.entries(d?.writes || {})) field("writes", name, Array.isArray(entries) ? entries.join(", ") : "");
    for (const name of new Set(d?.ledgers || [])) field("ledgers", name, "");
    for (const name of d?.provides || []) field("provides", name, "");
    for (const [name, axes] of Object.entries(d?.owns || {})) field("owns", name, Array.isArray(axes) ? axes.join(", ") : "");
    const incompatible = new Set();
    for (const edge of this.operatorLinks.get(piece.id) || []) {
      if (edge.kind !== "conflicts" || incompatible.has(edge.peer.id)) continue;
      incompatible.add(edge.peer.id);
      out.push({
        id: pageId(edge.peer.id),
        label: displayName(edge.peer.id),
        verb: "conflicts",
        layer: "pieces",
        note: edge.fields.join(", "),
      });
    }
    return out;
  }
  familyRoutes(family, pieces) {
    const groups = new Map();
    for (const source of pieces) {
      if (source.family !== family) continue;
      for (const edge of this.neighbours(source)) {
        if (edge.layer !== "pieces" || !edge.id) continue;
        const target = this.library.piece(engineId(edge.id));
        if (!target || target.family === family) continue;
        if (!groups.has(target.family)) groups.set(target.family, []);
        groups.get(target.family).push({source, edge});
      }
    }
    return groups;
  }
  describe(id) {
    const [type, key, verb, field] = partsOf(id);
    const family = this.library.familyById.get(key);
    if (type === "family" && family) {
      const pieces = this.library.inFamily.get(key);
      return {
        id,
        label: family.label,
        eyebrow: "Atlas family",
        plain: family.shelf === "design" ? "These pieces are named in design notes." : "Select a piece to trace its declared connections.",
        opens: [pieceList("Pieces", pieces)],
      };
    }
    const bundle = this.bundles.get(id);
    if (bundle) {
      const model = this.library.frame(bundle.model),
        f = this.library.familyById.get(bundle.family);
      return {
        id,
        label: modelName(model) + " ↔ " + f.short,
        eyebrow: "Model and family",
        plain: "Each piece is grouped by how this model declares it.",
        opens: Object.entries(howLabel).map(([how, label]) =>
          pieceList(
            label,
            bundle.entries.filter((e) => e.how === how).map((e) => e.piece),
          ),
        ),
      };
    }
    const piece = this.library.piece(key);
    if (type === "field" && piece) {
      const item = this.neighbours(piece).find((e) => e.verb === verb && e.name === field && e.id === id);
      if (item) {
        const edges = this.operatorLinks.get(piece.id) || [];
        const groups = new Map();
        for (const edge of edges) {
          if (edge.kind === "conflicts" || !edge.fields.includes(field)) continue;
          if (verb !== "owns" && verb !== "provides" && (edge.incoming || edge.kind !== verb)) continue;
          const title = edge.incoming
            ? edge.kind === "writes"
              ? "Written by"
              : "Read by"
            : edge.kind === "writes"
              ? "Writes to state of"
              : "Reads from state of";
          if (!groups.has(title)) groups.set(title, new Map());
          groups.get(title).set(edge.peer.id, edge.peer);
        }
        const opens = [...groups].map(([title, peers]) => pieceList(title + " · Engine map", [...peers.values()]));
        return {
          id,
          label: field,
          eyebrow: verb === "ledgers" ? "Declared ledger" : "Declared field",
          plain: displayName(piece.id) + (verb === "ledgers" ? " lists this ledger." : " " + verb + " this field."),
          facts: item.note
            ? [[{ writes: "Contributions", reads: "Read declaration", owns: "Axes" }[verb] || "Declaration", item.note]]
            : [],
          opens: [...opens, pieceList("Declaration", [piece])],
        };
      }
    }
    return null;
  }
}
export function pieceList(title, pieces) {
  return {
    title,
    count: pieces.length,
    items: pieces.map((p) => ({ id: pageId(p.id), label: p.id, swatch: p.declared ? "laws-declared" : "laws-design" })),
  };
}
