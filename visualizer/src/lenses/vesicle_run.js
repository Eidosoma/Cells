// A cursor over saved records. Chemistry only replays the signed channel's stated place counts.
export function through(times, t) {
  let lo = 0,
    hi = times.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (times[mid] <= t) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export class VesicleRun {
  constructor(file) {
    if (file?.format !== "cells.visualizer.assembly_run@2" || file.time?.unit !== "s" || !file.rows?.length)
      throw new Error("This vesicle replay needs saved rows and a clock in seconds.");
    this.file = file;
    this.pop = file.mode === "population";
    this.channels = new Map(file.channels.map((c) => [c.event_channel, c]));
    this.places = file.places;
    this.membrane = this.places.filter((p) => p.phase === "membrane");
    this.lumen = this.places.filter((p) => p.phase === "lumen");
    this.rows = [];
    let slots = [];
    for (const row of file.rows) {
      slots = slots.slice();
      for (const [slot, state] of row.slots) slots[slot] = state;
      this.rows.push({ ...row, slots });
    }
    this.rowTimes = this.rows.map((r) => r.t);
    this.start = this.rowTimes[0];
    this.end = file.end.time;
    this.events = [
      ...file.shears.map((e) => ({
        ...e,
        label: e.outcome === "split" ? "Shear division" : "Shear · " + e.outcome.replaceAll("_", " "),
      })),
      ...file.releases.map((e) => ({ ...e, label: e.cause === "pore" ? "Pore rupture" : "Threshold lysis" })),
    ].sort((a, b) => a.time - b.time);
    this.eventTimes = this.events.map((e) => e.time);
    this.t = [...new Set([...this.rowTimes, ...file.trace.time, ...this.eventTimes])].sort((a, b) => a - b);
    this.count = this.t.length;
    this.info = { judged_s: null };
    const states = file.rows.flatMap((row) => row.slots.map(([, state]) => state).filter(Boolean));
    this.maxFoot = states.reduce((m, s) => Math.max(m, s.membrane_footprint_quanta), 0);
    this.maxVolume = states.reduce((m, s) => Math.max(m, s.lumen_volume_L || 0), 0);
    // One scale for every sample; diagram areas follow footprint and diagram volumes follow litres.
    this.lumenDisplayScale = this.maxVolume
      ? states.reduce(
          (limit, s) =>
            s.lumen_volume_L > 0
              ? Math.min(
                  limit,
                  (1.81 * Math.sqrt(s.membrane_footprint_quanta / this.maxFoot)) / Math.cbrt(s.lumen_volume_L / this.maxVolume),
                )
              : limit,
          Infinity,
        )
      : 0;
    this.hasTension = states.some((s) => s.tension_N_per_m != null) || file.holds.length > 0;
    this.maxTension = Math.max(
      ...[0, ...file.holds.map((h) => h.sigma_N_per_m), ...file.releases.map((e) => e.tension_N_per_m)],
      states.reduce((m, s) => Math.max(m, s.tension_N_per_m || 0), 0),
    );
    this.founders = this.rows[0].slots.filter(Boolean).length;
    this.ruptures = file.releases.filter((e) => e.cause === "pore");
    this.ruptureTimes = this.ruptures.map((e) => e.time);
  }
  indexAt(t) {
    return Math.max(0, through(this.t, t) - 1);
  }
  isValid(index) {
    return Number.isInteger(index) && index >= 0 && index < this.count;
  }
  eventsBy(t) {
    return through(this.eventTimes, t);
  }
  survivors(t) {
    return this.founders - through(this.ruptureTimes, t);
  }
  at(t, slot = 0, rowIndex = null) {
    const i = rowIndex ?? Math.max(0, through(this.rowTimes, t) - 1);
    const row = this.rows[i],
      sample = row.slots[slot];
    const trace = this.file.trace,
      n = through(trace.time, t);
    const e = rowIndex === null ? this.events[this.eventsBy(t) - 1] || null : null;
    const hold = this.file.holds.find((h) => t >= h.start_s && t < h.end_s);
    const state = {
      row,
      sample,
      slot,
      n,
      event: e,
      hold,
      counts: sample?.counts || [],
      lastChannel: n ? this.channels.get(trace.channel[n - 1]) : null,
    };
    if (sample && n > row.event) {
      state.counts = [...sample.counts];
      for (let j = row.event; j < n; j++) {
        if (this.pop && trace.group[j] !== slot + 1) continue;
        const channel = this.channels.get(trace.channel[j]);
        for (const [p, amount] of channel.reactants)
          if (this.places[p].kind === "finite" && (!this.pop || this.places[p].phase !== "pool")) state.counts[p] -= amount;
        for (const [p, amount] of channel.products)
          if (this.places[p].kind === "finite" && (!this.pop || this.places[p].phase !== "pool")) state.counts[p] += amount;
      }
    }
    return state;
  }
  // Only transfers between two places of the same species are depicted as a moving molecule.
  movements(channel) {
    if (!channel) return [];
    const out = [];
    for (const [from, n] of channel.reactants)
      for (const [to, m] of channel.products) {
        const a = this.places[from],
          b = this.places[to];
        if (a.species === b.species && a.phase !== b.phase) out.push({ from: a, to: b, n: Math.min(n, m) });
      }
    return out;
  }
}
