import { h, emit } from "../ui/dom.js";
import { engineId, pageId } from "./laws_data.js";
import { bridgeKey, displayName, familyKey, modelName } from "./laws_connections.js";
import { action, control, search } from "./laws_atlas_controls.js";
import { NEIGHBOURS_PER_LAYER } from "./laws_atlas_scene.js";
import { starVerb, sectorLabel } from "./laws_star_scene.js";

const note = text => h("p", { class: "laws-guide" }, text);
const tally = text => h("p", { class: "laws-tally", "aria-live": "polite" }, text);
const modelOptions = (view, except) => view.library.frames.filter(f => f.id !== except).map(f => [f.id, modelName(f)]);
const declaration = (view, id) => action("Read declaration", "declaration", () => view.selectOnPage(id));

function familyGuide(view) {
  if (view.family) {
    const family = view.library.familyById.get(view.family);
    const routes = view.familyRoutes();
    return h("div",{class:"star-family-guide"},
      family.description ? note(family.description) : null,
      routes.size ? action(view.showFamilyRoutes ? "Focus on this family" : "Map connected families · "+routes.size,"family-routes",()=>{
        view.showFamilyRoutes=!view.showFamilyRoutes;
        view.notice({fit:true});
        if (!view.showFamilyRoutes) view.focus(familyKey(family.id));
      }) : null,
      view.showFamilyRoutes ? [...routes].map(([id,rows]) => h("details",{class:"star-route-list"},
        h("summary",{},view.library.familyById.get(id).short+" · "+rows.length),
        rows.map(({source,edge})=>action(displayName(source.id)+" "+starVerb[edge.verb].toLowerCase()+" "+edge.label,
          "route-"+source.id+"-"+edge.verb+"-"+edge.id,()=>view.showRoute(source,edge.verb))))) : null);
  }
  if (view.filter.query || view.primary || view.anatomy || view.filter.box || view.filter.where) return null;
  const pump = view.library.piece("cells.cycle.atp_driven_transporter_mass_action_positive@2");
  const model = view.library.frame("cells.model.assembly_lineages@2");
  return h("details",{class:"star-family-index",open:true},h("summary",{},"Explore the atlas"),
    pump && pump.declared.reads?.some(r=>view.library.byKey.has(r.name)) ?
      action("ATP transport → binding","tour-binding",()=>view.showRoute(pump,"reads")) : null,
    model ? action("Vesicle events & division","tour-vesicle",()=>view.setPrimary(model.id)) : null);
}

export function starControls(view) {
  const library = view.library;
  if (view.mode === "compare") {
    const selected = library.piece(engineId(view.selected));
    return h("div", {class:"laws-navigation"},
      note("Direct marks a piece named by the model. Inner model and Host kind show how a model includes a piece through another declaration."),
      selected ? action("Trace " + displayName(selected.id),"trace",()=>view.tracePiece(selected.id),true) :
        note("Choose a piece in the matrix to trace its connections."));
  }
  if (view.mode === "wiring") {
    const p = library.piece(view.trace), last = view.path.at(-1);
    if (view.terminal) return h("div", {class:"laws-navigation"},
      h("p", {class:"laws-subject"}, last.edge.label),
      note(displayName(p.id) + " · " + starVerb[last.edge.verb].toLowerCase() + " · " + last.edge.label),
      last.edge.note ? note(last.edge.note) : null, declaration(view,last.edge.id));
    const group = view.traceRows.filter(e => e.verb === view.relation);
    const pages = Math.ceil(group.length/NEIGHBOURS_PER_LAYER);
    return h("div", {class:"laws-navigation"},
      h("p", {class:"laws-subject"}, displayName(p.id)),
      note(p.declared ? library.familyById.get(p.family).label : "Named in a design note."),
      group.length ? h("div", {class:"star-destinations"}, view.visibleEdges().map(e =>
        e.id ? h("div", {class:"star-destination"}, action("Follow " + e.label,"follow",() => view.follow(e.id)),
          e.note && e.layer === "pieces" ? h("small",{},e.note) : null) : note(e.label))) : note("This piece has no recorded connections."),
      pages > 1 ? control("Connections page","page",Array.from({length:pages},(_,i)=>[String(i),String(i+1)+" of "+pages]),
        String(view.page), value => { view.page = Number(value); view.notice({fit:true}); }) : null,
      declaration(view,pageId(p.id)));
  }
  const pieces = view.filtered(), source = view.anatomy && view.model.get(view.anatomy);
  const count = view.overviewCount();
  const familyOptions = library.shelves.map(shelf => [sectorLabel[shelf.id] || shelf.label,
    library.families.filter(f => f.shelf === shelf.id).map(f => [f.id,f.label])]);
  const familyMemberships = view.primary && view.family && view.graph.bundles.get(bridgeKey(view.primary,view.family));
  return h("div", {class:"laws-navigation"},
    control("Highlight a model","model",[["","Whole catalogue"],...modelOptions(view)],view.primary || "",id=>view.setPrimary(id)),
    tally(count.pieces + " pieces across " + count.families + " families"),
    control("Explore a family","family",[["","All families"],...familyOptions],view.family || "",id=>view.setMark(id)),
    familyGuide(view),
    view.primary === "cells.model.assembly_lineages@2" && !view.family && !view.filter.query ?
      h("div",{class:"star-family-guide"},["cells.assembly_hazard.pore_nucleation@1","cells.operator.size_threshold_division@1"]
        .filter(id=>view.graph.members.get(view.primary)?.has(id)).map(id=>action(displayName(id),"vesicle-"+id,()=>view.tracePiece(id)))) : null,
    familyMemberships ? action("Inspect family memberships","memberships",()=>view.selectOnPage(familyMemberships.id)) : null,
    search(view,pieces),
    (view.family || source || view.filter.box) && !view.filter.query ?
      control("Trace a piece","piece",[["","Choose a piece…"],...pieces.filter(p=>!view.primary || view.graph.members.get(view.primary)?.has(p.id)).map(p=>[p.id,displayName(p.id)])],"",id=>id && view.tracePiece(id)) : null,
    h("details",{class:"laws-filters",open:Boolean(view.filter.where)}, h("summary",{},"Filter catalogue"),
      control("Catalogue entries","origin",[["all","All entries"],["declared","Declared pieces"],["design","Design notes"]],
        view.filter.where || "all",id=>view.setMode(id))),
    source ? action("Return to "+source.label,"scope",()=>emit(view.stage.canvas,"cells-door",{lens:"cell",select:source.id})) : null);
}

function routeBar(view) {
  const last = view.path.at(-1), origin = view.path[0]?.from || view.trace;
  const stop = (name,i) => h("button",{type:"button",class:"star-stop",dataset:{starStop:String(i)},
    "aria-current":i===view.path.length?"step":null,onclick:()=>view.jumpStop(i)},name);
  const trail = h("nav",{class:"star-breadcrumbs","aria-label":"Flight path"},
    action("Overview","overview",()=>view.overview()), stop(displayName(origin),0),
    view.path.map((s,i)=>[h("span",{class:"star-hop"},starVerb[s.edge.verb].toLowerCase()),stop(s.edge.label,i+1)]));
  const verbs = Object.keys(starVerb).filter(verb=>view.traceRows.some(e=>e.verb===verb));
  const picker = !view.terminal && verbs.length ? control("Relationship","relation",
    verbs.map(verb=>[verb,starVerb[verb]+" · "+view.traceRows.filter(e=>e.verb===verb).length]),
    view.relation,verb=>view.setRelation(verb)) : null;
  return h("div",{class:"star-console star-flight-console"},trail,picker,
    view.terminal ? declaration(view,last.edge.id) : null);
}

const groupNames = ["First only","Shared","Second only"], pageSize = 20;
function matrix(view) {
  const groups = view.graph.compare(view.primary, view.other);
  const rows = view.matrixGroup === -1 ? groups.flat().sort((a,b)=>a.id.localeCompare(b.id)) : groups[view.matrixGroup];
  const pages = Math.max(1, Math.ceil(rows.length/pageSize));
  view.matrixPage = Math.min(pages-1,view.matrixPage);
  const start = view.matrixPage*pageSize;
  const filters = [-1,0,1,2].map(i=>h("button",{type:"button",dataset:{starGroup:String(i)},"aria-pressed":String(view.matrixGroup===i),
    onclick:()=>{view.matrixGroup=i;view.matrixPage=0;view.refreshConsole();}},
    (i===-1?"All":groupNames[i])+" · "+(i===-1?groups.flat().length:groups[i].length)));
  const cell = (p,frame) => {
    const d=p.declared_by.find(entry=>entry.frame===frame);
    const words={direct:"Direct",inner:"Inner model",kind:"Host kind"};
    return h("td",{},d ? h("span",{class:"star-membership "+d.how,title:d.via?displayName(d.via):"Direct declaration"},words[d.how]) :
      h("span",{"aria-label":"No declaration"},"—"));
  };
  const turn = (by) => {view.matrixPage+=by;view.refreshConsole();};
  return h("section",{class:"star-console star-matrix","aria-label":"Model membership matrix"},
    h("header",{},h("h3",{},"Model matrix"),action("Close","close-matrix",()=>view.back())),
    h("div",{class:"star-model-pair"},control("First model","matrix-left",modelOptions(view,view.other),view.primary,id=>view.setPrimary(id)),
      control("Second model","matrix-right",modelOptions(view,view.primary),view.other,id=>view.compareWith(id))),
    h("div",{class:"star-matrix-filters","aria-label":"Pieces to compare"},filters),
    h("div",{class:"star-table-scroll"},h("table",{},h("thead",{},h("tr",{},h("th",{scope:"col"},"Piece"),
      ...[view.primary,view.other].map(id=>h("th",{scope:"col"},modelName(view.library.frame(id)))))),
      h("tbody",{},rows.slice(start,start+pageSize).map(p=>h("tr",{},h("th",{scope:"row"},
        h("button",{type:"button",dataset:{matrixPiece:p.id},onclick:()=>view.tracePiece(p.id)},displayName(p.id))),
        cell(p,view.primary),cell(p,view.other)))))),
    rows.length ? null : note("No pieces in this group."),
    pages>1 ? h("div",{class:"star-pagination"},
      h("button",{type:"button",dataset:{atlasAction:"matrix-prev"},disabled:view.matrixPage===0,onclick:()=>turn(-1)},"Previous"),
      h("span",{"aria-live":"polite"},(view.matrixPage+1)+" / "+pages),
      h("button",{type:"button",dataset:{atlasAction:"matrix-next"},disabled:view.matrixPage===pages-1,onclick:()=>turn(1)},"Next")) : null);
}

export function starConsole(view) {
  if (view.mode==="wiring") return routeBar(view);
  if (view.mode==="compare") return matrix(view);
  const scope = view.family ? view.library.familyById.get(view.family).label :
    view.primary ? modelName(view.library.frame(view.primary)) : "Whole catalogue";
  const example = view.examplePiece();
  return h("div",{class:"star-console star-overview-console"},h("span",{class:"star-scope"},scope),
    example ? action("Fly a connection","example",()=>view.tracePiece(example.id),true) : null,
    view.library.frames.length>1 ? action("Compare models","open-matrix",()=>view.openMatrix()) : null);
}
