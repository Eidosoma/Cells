# Pinned wound/TRP source limits

BETSE v1.5.0 commit `5269a714aa2593ed2a6708c4516289977d8ae1a2`:
[raw audit](/mnt/workspaces/Cells/wound-channel-source-limits-20261028-01/capture/audit.json),
[guard](/mnt/workspaces/Cells/wound-channel-source-limits-20261028-01/guard/result.json).

Unchanged `WoundABC.init` calls `_init_state(V)`, but TRP requires `(V,sim,p)`;
unchanged `run` has the same `_calculate_state` mismatch. Both captured calls
raise `TypeError`. The latter leaves its declared W input unchanged at two.
Direct subclass calls, labelled metadata inspection only, confirm powers0/0,
targets/raw taus1 and **no `time_unit` assignment**. Raw tau1 therefore has no
established seconds/milliseconds interpretation for a runnable TRP update.

The source declares W=2 and contains a forward-Euler decrement
`W-W*k*dt`. Its proposed W-dependent conductance and ionic transport are
commented out. Active opening does not implement this wound feedback.
The tissue handler retains an annotation/None member and wound targets;
inspection found no executable TRP use or `wound_close_factor` configuration.

No replacement channel, guessed gate clock or new wound model was created.
The Chief redirected feature work to the runnable Morris–Lecar family.
Audit JSON SHA-256:
`7def0f6cb33a2bc039770872669f17e262ca8d0ec764d3e0b128bc01e8ef4381`.
