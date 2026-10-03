const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {effectiveTimeline, applyTimeline, mergeArticleEvents} = require('./chronology');

const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../dataset/bungo_relationships.json'), 'utf8'));
const before = new Map(data.characters.map(person => [person.id, effectiveTimeline(data, person.id)]));
for (const person of data.characters) {
  const rows = before.get(person.id);
  assert.equal(rows[0].start, person.birthYear);
  assert.equal(rows.at(-1).end, person.deathYear);
  rows.slice(1).forEach((row, index) => assert.equal(row.start, rows[index].end));
}

const selected = data.characters[0].id;
const rows = before.get(selected).map(row => ({...row}));
rows[0].location = data.locations.find(place => place.id !== rows[0].location).id;
const changed = {...data, sessions: applyTimeline(data, selected, rows)};
assert.equal(effectiveTimeline(changed, selected)[0].location, rows[0].location);
for (const person of data.characters.filter(item => item.id !== selected)) {
  assert.deepEqual(effectiveTimeline(changed, person.id), before.get(person.id));
}
assert.equal(new Set(changed.sessions.map(session => session.id)).size, changed.sessions.length);

const sample = {
  timeLabels: ['1900','1905','1910'],
  characters: [{id: 0, name: 'A', birthYear: 1900, deathYear: 1910}, {id: 1, name: 'B', birthYear: 1900, deathYear: 1910}],
  locations: [{id: 0, name: 'X'}, {id: 1, name: 'Y'}],
  sessions: [{id: 0, location: 0, members: [0], start: 0, end: 2}, {id: 1, location: 1, members: [1], start: 0, end: 2}]
};
const joined = applyTimeline(sample, 1, [{start: 1900, end: 1910, location: 0, note: ''}]);
assert.equal(joined.length, 1);
assert.deepEqual(joined[0].members.sort(), [0,1]);

const partial = applyTimeline(sample, 1, [
  {start: 1900, end: 1905, location: 0, note: ''},
  {start: 1905, end: 1910, location: 1, note: ''}
]);
assert.deepEqual(effectiveTimeline({...sample, sessions: partial}, 0), effectiveTimeline(sample, 0));
assert.equal(partial.filter(session => session.location === 0).length, 2);
assert.throws(() => applyTimeline(sample, 1, [{start:1900,end:1905,location:0,note:''}]), /出生年から没年/);

const articleData = {...data, locationTree: data.locationTree};
const suehiro = data.characters.find(person => person.name === '末広鉄腸');
const oldRows = effectiveTimeline(articleData, suehiro.id);
const imported = mergeArticleEvents(articleData, suehiro.id, oldRows, [
  {year: 1888.3224, location: 69, confidence: 0.95, source: 'https://example.org/article', evidence: 'サンフランシスコ到着'},
  {year: 1888.37158, location: 59, confidence: 0.95, source: 'https://example.org/article', evidence: 'イギリス到着'}
]);
assert.equal(imported.find(row => row.start <= 1888.3224 && row.end > 1888.3224).location, 69);
assert.equal(imported.find(row => row.start <= 1888.37158 && row.end > 1888.37158).location, 60);
assert.ok(imported.some(row => row.start === 1888.3224));
assert.ok(imported.some(row => row.start === 1888.37158));
assert.ok(imported.some(row => row.note.includes('https://example.org/article')));
console.log('chronology: ok');
