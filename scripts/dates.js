(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StoryDates = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function parts(value) {
    const year = Math.floor(Number(value));
    const fraction = Number(value) - year;
    if (!Number.isFinite(year)) return {year: '', month: '', day: ''};
    if (Math.abs(fraction) < 0.000005) return {year, month: '', day: ''};
    for (let month = 1; month <= 12; month++) {
      if (Math.abs(fraction - (month - 1) / 12) < 0.00001) return {year, month, day: ''};
    }
    const days = new Date(Date.UTC(year + 1, 0, 1)).getTime() - new Date(Date.UTC(year, 0, 1)).getTime();
    const date = new Date(Date.UTC(year, 0, 1) + Math.round(fraction * days / 86400000) * 86400000);
    return {year, month: date.getUTCMonth() + 1, day: date.getUTCDate()};
  }

  function decimal(yearValue, monthValue = '', dayValue = '') {
    const year = Number(yearValue);
    const month = monthValue === '' ? null : Number(monthValue);
    const day = dayValue === '' ? null : Number(dayValue);
    if (!Number.isInteger(year) || year < 1600 || year > 2099 ||
        (month !== null && (!Number.isInteger(month) || month < 1 || month > 12)) ||
        (day !== null && (month === null || !Number.isInteger(day) || day < 1 || day > 31))) {
      throw new Error('年月日を確認してください。');
    }
    if (month === null) return year;
    if (day === null) return Math.round((year + (month - 1) / 12) * 100000) / 100000;
    const date = new Date(Date.UTC(year, month - 1, day));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() + 1 !== month || date.getUTCDate() !== day) {
      throw new Error('存在しない日付です。');
    }
    const dayOfYear = (date.getTime() - Date.UTC(year, 0, 1)) / 86400000;
    const daysInYear = (Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)) / 86400000;
    return Math.round((year + dayOfYear / daysInYear) * 100000) / 100000;
  }

  function label(value) {
    const date = parts(value);
    return `${date.year}年${date.month === '' ? '--' : String(date.month).padStart(2, '0')}月${date.day === '' ? '--' : String(date.day).padStart(2, '0')}日`;
  }

  return {parts, decimal, label};
});
