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
  constructor(file, palette = null) {
    if (file?.format !== "cells.visualizer.assembly_run@2" || file.time?.unit !== "s" || !file.rows?.length)
      throw new Error("This vesicle replay needs saved rows and a clock in seconds.");
    this.file = file;
    this.pop = file.mode === "population";
    this.channels = new Map(file.channels.map((c) => [c.event_channel, c]));
    this.places = file.places;
    this.membrane = this.places.filter((p) => p.phase === "membrane");
    this.lumen = this.places.filter((p) => p.phase === "lumen");
    this.species = [...new Set([...this.membrane, ...this.lumen, ...this.places].map((p) => p.species))];
    this.palette = palette || this.species;
    this.transfers = [];
    this.routes = new Map();
    const trace = file.trace;
    const moves = new Map(file.channels.map((ch) => [ch.event_channel, this.movements(ch)]));
    trace.channel.forEach((code, index) => {
      for (const movement of moves.get(code)) {
        // In a population, group 0 belongs to the shared pool. Vesicle groups start at 1.
        const slot = this.pop ? trace.group[index] - 1 : 0;
        if (slot < 0) continue;
        const { from, to } = movement;
        const key = [slot, from.index, to.index].join("/");
        if (!this.routes.has(key)) this.routes.set(key, { key, slot, from, to, times: [], count: 0 });
        const route = this.routes.get(key);
        route.times.push(trace.time[index]);
        route.count += movement.n;
        this.transfers.push({ ...movement, key, slot, index, time: trace.time[index] });
      }
    });
    this.transferTimes = this.transfers.map((move) => move.time);
    this.exchangedSpecies = [...new Set(this.transfers.map((m) => m.from.species))];
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
  // Flight time and the shear window are display choices. The recorded instants and states never move.
  traffic(t, duration, slot, route, since = -Infinity) {
    const start = through(this.transferTimes, t - duration), end = through(this.transferTimes, t);
    return this.transfers.slice(start, end).filter((m) => m.slot === slot && (!route || route === m.key) && m.time >= since);
  }
  divisionAt(t) {
    if (this.pop) return null;
    const i = through(this.eventTimes, t), last = this.events[i - 1], next = this.events[i];
    if (last?.outcome === "split" && last.daughters.length === 2) {
      const span = Math.min(1.8, ((next?.time ?? Infinity) - last.time) / 2);
      if (span > 0 && t - last.time < span) return { event: last, after: true, part: (t - last.time) / span };
    }
    if (next?.outcome === "split" && next.daughters.length === 2) {
      const span = Math.min(1.25, (next.time - (last?.time ?? this.start)) / 2);
      if (span > 0 && t >= next.time - span) return { event: next, after: false, part: 1 - (next.time - t) / span };
    }
    return null;
  }
  at(t, slot = 0, rowIndex = null) {
    const i = rowIndex ?? Math.max(0, through(this.rowTimes, t) - 1);
    const row = this.rows[i],
      sample = row.slots[slot];
    const trace = this.file.trace,
      n = rowIndex === null ? through(trace.time, t) : row.event;
    const e = rowIndex === null ? this.events[this.eventsBy(t) - 1] || null : null;
    const hold = this.file.holds.find((h) => t >= h.start_s && t < h.end_s);
    let lastIndex = n - 1;
    if (this.pop) while (lastIndex >= 0 && trace.group[lastIndex] !== slot + 1) lastIndex--;
    const state = {
      row,
      sample,
      slot,
      n,
      event: e,
      hold,
      counts: sample?.counts || [],
      lastIndex,
      lastChannel: lastIndex >= 0 ? this.channels.get(trace.channel[lastIndex]) : null,
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
  // A place can appear on both sides as a spectator. Only a conserved species with an
  // unambiguous source and destination is evidence for a trajectory.
  movements(channel) {
    if (!channel) return [];
    const changes = new Map();
    for (const [side, sign] of [[channel.reactants, -1], [channel.products, 1]]) {
      for (const [index, amount] of side) {
        const place = this.places[index];
        if (!changes.has(place.species)) changes.set(place.species, new Map());
        const net = changes.get(place.species);
        net.set(place, (net.get(place) || 0) + sign * amount);
      }
    }
    const out = [];
    for (const net of changes.values()) {
      const sources = [...net].filter(([, n]) => n < 0), sinks = [...net].filter(([, n]) => n > 0);
      if (!sources.length || !sinks.length || (sources.length > 1 && sinks.length > 1)) continue;
      if ([...net.values()].reduce((a, b) => a + b, 0) !== 0) continue;
      for (const [from, lost] of sources)
        for (const [to, gained] of sinks)
          if (from.phase !== to.phase) out.push({ from, to, n: Math.min(-lost, gained) });
    }
    return out;
  }
}
