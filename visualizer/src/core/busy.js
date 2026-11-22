// What the page is busy with, for the check tools (tools/lib/page_waits.mjs, `settled`): the reasons that hold, each in
// words, and none when the page is at rest. It reads the state the page already keeps and changes nothing; it costs
// nothing while nobody asks. Whether the page's own fonts have arrived is not among them: a check says it beside the
// page's rest (on the checks' own server a font may not arrive at all) and never waits on it.

/**
 * The reasons `viewer` (the `cells-viewer` element) is not at rest: the scene not yet in; a view loading, a run or a
 * layer's records on their way, a family of the shelves opening; the landing's cards or their details on their way; the camera in
 * flight; a frame owed (asked for and not yet drawn); a view of the page's own still moving (a frame asked for the
 * next by the one before).
 */
export function busyReasons(viewer) {
  const reasons = [];
  if (!viewer?.model) reasons.push("the scene is not yet in");
  const lens = viewer?.current;
  if (lens?.loading) reasons.push("the view is loading");
  if (lens?.pending) reasons.push("a run is on its way");
  if (lens?.fetching?.size) reasons.push("a layer's records are on their way");
  if (lens?.mounted?.opening) reasons.push("a family is opening");
  if (viewer?.panelEvidence?.status === "loading") reasons.push("the unit evidence is loading");
  if (viewer?.landingView?.fetching) reasons.push("the landing's cards are on their way");
  if (viewer?.landingView?.detailsFetching) reasons.push("the cards' details are on their way");
  const stage = viewer?.stage;
  if (stage) {
    if (stage.rig?.flight) reasons.push("the camera is in flight");
    if (stage.needsRender) reasons.push("a frame is owed");
    if (stage.moving) reasons.push("a view is moving");
  }
  return reasons;
}
