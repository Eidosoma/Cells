// The scene file, indexed for the viewer. Read-only: lenses and panels ask it questions.

export const SCENE_FORMAT = "cells.visualizer.scene@1";

export class SceneModel {
  constructor(scene) {
    const problems = validate(scene);
    if (problems.length) throw new Error(`Scene file is not valid: ${problems.slice(0, 3).join("; ")}`);
    this.raw = scene;
    this.meta = scene.meta || {};
    this.entities = scene.entities;
    this.relations = scene.relations;
    this.byId = new Map(scene.entities.map((entity) => [entity.id, entity]));
    this.statuses = new Map(scene.statuses.map((status) => [status.id, status]));
    this.kinds = new Map(scene.relation_kinds.map((kind) => [kind.id, kind]));
    this.groups = scene.groups;
    this.outgoing = new Map();
    this.incoming = new Map();
    for (const relation of scene.relations) {
      push(this.outgoing, relation.from, relation);
      push(this.incoming, relation.to, relation);
    }
  }

  get(id) {
    return this.byId.get(id);
  }

  inGroup(groupId) {
    return this.entities.filter((entity) => entity.group === groupId);
  }

  ofKind(kind) {
    return this.entities.filter((entity) => entity.kind === kind);
  }

  /** Every relation touching this part, as {relation, other, outward}. */
  links(id) {
    const out = (this.outgoing.get(id) || []).map((relation) => ({ relation, other: relation.to, outward: true }));
    const back = (this.incoming.get(id) || []).map((relation) => ({ relation, other: relation.from, outward: false }));
    return [...out, ...back];
  }

  neighbours(id) {
    return new Set(this.links(id).map((link) => link.other));
  }

  isBuilt(entity) {
    const status = this.statuses.get(entity.status);
    return status ? status.built : true;
  }

  sourceUrl(source) {
    return this.meta.source_base_url ? this.meta.source_base_url + source.path : null;
  }
}

function push(map, key, value) {
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(value);
}

/** Structural checks shared by the viewer and the build tools. Returns a list of problems. */
export function validate(scene) {
  const problems = [];
  if (!scene || typeof scene !== "object") return ["not an object"];
  if (scene.format !== SCENE_FORMAT) problems.push(`format is ${scene.format}, expected ${SCENE_FORMAT}`);
  for (const key of ["statuses", "relation_kinds", "groups", "entities", "relations"]) {
    if (!Array.isArray(scene[key])) problems.push(`${key} is missing`);
  }
  if (problems.length) return problems;
  const statuses = new Set(scene.statuses.map((status) => status.id));
  const kinds = new Set(scene.relation_kinds.map((kind) => kind.id));
  const groups = new Set(scene.groups.map((group) => group.id));
  const ids = new Set();
  for (const entity of scene.entities) {
    if (!entity.id || !entity.label) problems.push(`a part lacks an id or label`);
    if (ids.has(entity.id)) problems.push(`duplicate id ${entity.id}`);
    ids.add(entity.id);
    if (entity.status && !statuses.has(entity.status)) problems.push(`${entity.id}: unknown status ${entity.status}`);
    if (entity.group !== "biology" && !groups.has(entity.group)) problems.push(`${entity.id}: unknown group ${entity.group}`);
  }
  for (const relation of scene.relations) {
    if (!ids.has(relation.from) || !ids.has(relation.to)) problems.push(`relation ${relation.from} -> ${relation.to}: unknown part`);
    if (!kinds.has(relation.kind)) problems.push(`relation ${relation.from} -> ${relation.to}: unknown kind ${relation.kind}`);
  }
  return problems;
}
