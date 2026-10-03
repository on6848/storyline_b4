const assert = require('node:assert/strict');
const dates = require('./dates.js');

assert.deepEqual(dates.parts(1864), {year: 1864, month: '', day: ''});
assert.deepEqual(dates.parts(1875.33333), {year: 1875, month: 5, day: ''});
assert.deepEqual(dates.parts(1888.3224), {year: 1888, month: 4, day: 28});
assert.equal(dates.decimal(1888, 4, 28), 1888.3224);
assert.equal(dates.decimal(1875, 5), 1875.33333);
assert.equal(dates.label(1888.3224), '1888年04月28日');
assert.throws(() => dates.decimal(1900, 2, 29));
console.log('dates: ok');
