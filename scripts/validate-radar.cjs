// RADAR DA: read-only integrity check. Does not modify published content.
const fs = require('node:fs');
const read = (path) => JSON.parse(fs.readFileSync(path, 'utf8'));
const errors = [];
const warn = [];
const feed = read('data/feed.json');
const analyses = read('data/analyses.json');
const social = read('data/social-posts.json');
const entries = feed.items;
if (!Array.isArray(entries)) errors.push('feed.items must be an array');
if (!analyses || typeof analyses !== 'object' || Array.isArray(analyses)) errors.push('analyses must be an object');
if (!Array.isArray(social.items)) errors.push('social.items must be an array');
const validHttp = value => typeof value === 'string' && /^https?:\/\//i.test(value);
const seen = new Set();
for (const [i, item] of (Array.isArray(entries) ? entries : []).entries()) {
  if (!validHttp(item.url)) errors.push('feed item ' + i + ': invalid source URL');
  if (item.image && !validHttp(item.image)) errors.push('feed item ' + i + ': invalid image URL');
  if (seen.has(item.url)) errors.push('duplicate feed URL: ' + item.url);
  seen.add(item.url);
  const a = analyses[item.url];
  if (!a) { errors.push('missing analysis: ' + item.url); continue; }
  if (typeof a.intro !== 'string' || !a.intro.trim() ||
      !Array.isArray(a.points) || !a.points.length ||
      !a.points.every(p => Array.isArray(p) && p.length >= 2 && p[1]?.trim()) ||
      typeof a.takeaway !== 'string' || !a.takeaway.trim()) errors.push('incomplete analysis: ' + item.url);
}
for (const [i, item] of (Array.isArray(social.items) ? social.items : []).entries()) {
  if (!item || typeof item !== 'object') errors.push('invalid social item: ' + i);
}
if (!entries?.length) errors.push('empty main feed');
if (!Object.keys(analyses).length) errors.push('empty analyses');
if (!social.items.length) warn.push('social feed empty: publication targets not met');
console.log(JSON.stringify({feed:entries?.length, analyses:Object.keys(analyses).length, social:social.items?.length, errors,warnings:warn}, null, 2));
if (errors.length) process.exitCode = 1;
