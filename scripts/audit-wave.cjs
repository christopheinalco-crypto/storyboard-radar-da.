// RADAR DA — independent publication-count audit (read-only).
// Usage: node scripts/audit-wave.cjs [2026-11-12T12:00:00+01:00]
// Counts actual entries by their timestamps; never counts editorial queue candidates.
const fs = require('node:fs');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const feed = read('data/feed.json');
const social = read('data/social-posts.json');
const targets = { main: 5, linkedin: 3, instagram: 3 };
const now = process.argv[2] ? new Date(process.argv[2]) : new Date();
if (Number.isNaN(now.getTime())) throw Error('Invalid audit date');
const parts = date => Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', hourCycle: 'h23'
}).formatToParts(date).filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
const slots = [6, 12, 16, 20];
const local = parts(now);
const currentHour = Number(local.hour);
const currentSlot = slots.filter(h => h <= currentHour).at(-1);
const today = local.year + '-' + local.month + '-' + local.day;
const inWave = value => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const p = parts(date);
  return p.year + '-' + p.month + '-' + p.day === today
    && currentSlot !== undefined && Number(p.hour) >= currentSlot
    && Number(p.hour) < (slots.find(h => h > currentSlot) || 24)
    && date <= now;
};
const published = { main: [], linkedin: [], instagram: [] };
for (const item of feed.items || []) {
  if (inWave(item.radar_added_at || item.added_at))
    published.main.push({ title: item.title, url: item.url });
}
for (const item of social.items || []) {
  if (!inWave(item.published_at)) continue;
  const u = (item.url || '').toLowerCase();
  const channel = /(^|\.)linkedin\.com\//.test(u.replace(/^https?:\/\//, '')) ? 'linkedin'
    : /(^|\.)instagram\.com\//.test(u.replace(/^https?:\/\//, '')) ? 'instagram' : null;
  if (channel) published[channel].push({ title: item.title, url: item.url });
}
const counts = Object.fromEntries(Object.entries(published).map(([key, list]) => [key, list.length]));
const missing = Object.fromEntries(Object.entries(targets).map(([key, n]) => [key, Math.max(0, n - counts[key])]));
const complete = Object.values(missing).every(n => n === 0);
const report = { audited_at: now.toISOString(), local_day: today, slot_hour: currentSlot,
  timezone: 'Europe/Paris', targets, counts, missing, complete, published,
  note: 'Counts only committed JSON entries with timestamps; does not prove GitHub Pages deployment or image rights.' };
console.log(JSON.stringify(report, null, 2));
if (!complete) process.exitCode = 2;
