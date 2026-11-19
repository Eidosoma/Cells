// A frame drawn into a WebGL context that the browser has just taken away can fail inside three.js: it reads a
// program's log, which is then null, and throws. That is no fault of the page, and it must not stop the page's frames:
// the context comes back, and the restore asks for the picture again (core/stage.js, onRestored). A failure with the
// context in hand is a fault, and is thrown on as before. Kept apart from the stage so that it is tested without one.

/**
 * Draw one frame. Returns true where it was drawn, false where drawing failed because the context is lost (`lost()`
 * says so at that moment); any other failure is thrown on.
 */
export function drawGuarded(draw, lost) {
  try {
    draw();
    return true;
  } catch (error) {
    let gone = false;
    try {
      gone = Boolean(lost());
    } catch {
      gone = false;
    }
    if (!gone) throw error;
    return false;
  }
}
