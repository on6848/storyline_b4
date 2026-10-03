(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StoryChronology = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const EPS = 1e-8;
  const same = (a, b) => Math.abs(a - b) < EPS;
  const joinedNotes = (left, right) => [...new Set([left, right].filter(Boolean).flatMap(value => value.split('\n').filter(Boolean)))].join('\n');
  const years = (data, session) => ({
    start: Number(session.startYear ?? data.timeLabels[session.start]),
    end: Number(session.endYear ?? data.timeLabels[session.end])
  });

  function effectiveTimeline(data, personId) {
    const person = data.characters.find(item => item.id === personId);
    if (!person) throw new Error('人物が存在しません。');
    const spans = data.sessions.filter(item => item.members.includes(personId)).map(item => ({...years(data, item), session: item}));
    if (!spans.length) return [{start: person.birthYear, end: person.deathYear, location: data.locations[0]?.id, note: ''}];
    const limits = [...new Set([person.birthYear, person.deathYear, ...spans.flatMap(item => [Math.max(person.birthYear, item.start), Math.min(person.deathYear, item.end)])])]
      .filter(value => value >= person.birthYear && value <= person.deathYear).sort((a, b) => a - b);
    const rows = [];
    for (let i = 0; i < limits.length - 1; i++) {
      const start = limits[i], end = limits[i + 1];
      if (end <= start) continue;
      const active = spans.filter(item => item.start <= start + EPS && item.end >= end - EPS)
        .sort((a, b) => (a.end - a.start) - (b.end - b.start) || b.session.id - a.session.id);
      rows.push({start, end, location: active[0]?.session.location ?? null, note: active[0]?.session.dateNote ?? ''});
    }
    const firstKnown = rows.find(row => row.location !== null)?.location ?? data.locations[0]?.id;
    let previous = firstKnown;
    for (const row of rows) {
      if (row.location === null) row.location = previous;
      else previous = row.location;
    }
    const merged = [];
    for (const row of rows) {
      const last = merged[merged.length - 1];
      if (last && last.location === row.location && last.note === row.note && same(last.end, row.start)) last.end = row.end;
      else merged.push({...row});
    }
    return merged;
  }

  function applyTimeline(data, personId, rows) {
    const person = data.characters.find(item => item.id === personId);
    if (!person) throw new Error('人物が存在しません。');
    const places = new Set(data.locations.map(item => item.id));
    const ordered = rows.map(row => ({start: Number(row.start), end: Number(row.end), location: Number(row.location), note: String(row.note ?? '')}))
      .sort((a, b) => a.start - b.start || a.end - b.end || a.location - b.location);
    if (!ordered.length || !same(ordered[0].start, person.birthYear) || !same(ordered[ordered.length - 1].end, person.deathYear)) throw new Error('年譜は出生年から没年まで必要です。');
    for (let i = 0; i < ordered.length; i++) {
      const row = ordered[i];
      if (!Number.isFinite(row.start) || !Number.isFinite(row.end) || row.start >= row.end || !places.has(row.location)) throw new Error('年譜の期間または場所が不正です。');
      if (i && !same(ordered[i - 1].end, row.start)) throw new Error('年譜の期間に空白または重複があります。');
    }

    const retained = [];
    const recycled = [];
    for (const source of data.sessions) {
      if (!source.members.includes(personId)) {
        retained.push({...source, members: [...source.members]});
      } else if (source.members.length > 1) {
        retained.push({...source, members: source.members.filter(id => id !== personId)});
      } else {
        recycled.push(source);
      }
    }
    let nextId = Math.max(-1, ...data.sessions.map(item => item.id)) + 1;
    const name = id => data.characters.find(item => item.id === id)?.name ?? '';
    for (const row of ordered) {
      const matching = retained.filter(item => {
        const span = years(data, item);
        return item.location === row.location && same(span.start, row.start) && same(span.end, row.end);
      }).sort((a, b) => b.members.length - a.members.length || a.members.map(name).sort().join('|').localeCompare(b.members.map(name).sort().join('|')) || a.id - b.id)[0];
      if (matching) {
        matching.members.push(personId);
        matching.members.sort((a, b) => name(a).localeCompare(name(b)) || a - b);
        if (row.note) matching.dateNote = joinedNotes(matching.dateNote, row.note);
        continue;
      }
      recycled.sort((a, b) => {
        const aSpan = years(data, a), bSpan = years(data, b);
        const aExact = a.location === row.location && same(aSpan.start, row.start) && same(aSpan.end, row.end);
        const bExact = b.location === row.location && same(bSpan.start, row.start) && same(bSpan.end, row.end);
        return Number(bExact) - Number(aExact) || Math.abs(aSpan.start - row.start) - Math.abs(bSpan.start - row.start) || a.id - b.id;
      });
      const reused = recycled.shift();
      const item = {id: reused?.id ?? nextId++, location: row.location, members: [personId], start: 0, end: 1, startYear: row.start, endYear: row.end};
      if (row.note) item.dateNote = row.note;
      retained.push(item);
    }
    return retained.sort((a, b) => {
      const aSpan = years(data, a), bSpan = years(data, b);
      return aSpan.start - bSpan.start || aSpan.end - bSpan.end || a.location - b.location || a.members.map(name).sort().join('|').localeCompare(b.members.map(name).sort().join('|')) || a.id - b.id;
    });
  }

  function isAncestorLocation(data, ancestor, child) {
    const parent = new Map();
    function visit(node) {
      for (const item of node.children || []) { parent.set(item.id, node.id); visit(item); }
    }
    visit(data.locationTree);
    let current = child;
    while (parent.has(current)) {
      current = parent.get(current);
      if (current === ancestor) return true;
    }
    return false;
  }

  function mergeArticleEvents(data, personId, rows, events) {
    const person = data.characters.find(item => item.id === personId);
    if (!person) throw new Error('人物が存在しません。');
    const places = new Set(data.locations.map(item => item.id));
    const updated = rows.map(row => ({...row}));
    const adjustedStarts = new Set();
    const ordered = events.map(event => ({...event, year: Number(event.year), location: Number(event.location)}))
      .sort((a, b) => a.year - b.year || a.location - b.location);
    for (let i = 0; i < ordered.length; i++) {
      const event = ordered[i];
      if (!Number.isFinite(event.year) || !places.has(event.location) || event.year < person.birthYear || event.year >= person.deathYear) throw new Error('記事候補の時刻または場所が不正です。');
      if (i && same(event.year, ordered[i-1].year) && event.location !== ordered[i-1].location) throw new Error('同じ時刻の異なる場所は1件ずつ選んでください。');
      const index = updated.findIndex(row => row.start <= event.year + EPS && event.year < row.end - EPS);
      if (index < 0) throw new Error('記事候補の時刻が年譜に入りません。');
      const row = updated[index];
      const source = event.source ? `${event.source}${event.evidence ? ' | ' + event.evidence : ''}` : event.evidence || '';
      if (row.location === event.location || isAncestorLocation(data, event.location, row.location)) {
        row.note = joinedNotes(row.note, source);
        if (index > 0 && event.confidence >= 0.9 && !adjustedStarts.has(row) && event.year > row.start && event.year - row.start <= 0.02) {
          updated[index-1].end = event.year;
          row.start = event.year;
          adjustedStarts.add(row);
        }
      } else if (same(row.start, event.year)) {
        row.location = event.location;
        row.note = joinedNotes(row.note, source);
      } else {
        const next = {...row, start: event.year, location: event.location, note: source};
        row.end = event.year;
        updated.splice(index+1, 0, next);
      }
    }
    const merged = [];
    for (const row of updated) {
      const last = merged[merged.length - 1];
      if (last && last.location === row.location && same(last.end, row.start)) {
        last.end = row.end;
        last.note = joinedNotes(last.note, row.note);
      } else merged.push(row);
    }
    return merged;
  }

  return {effectiveTimeline, applyTimeline, mergeArticleEvents, isAncestorLocation};
});
