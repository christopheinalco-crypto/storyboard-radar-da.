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
  // Visual-first policy effective 12 November 2026. Preserve earlier articles for separate repair.
  const addedAt = Date.parse(item.radar_added_at || '');
  const requiresImage = Number.isFinite(addedAt) && addedAt >= Date.parse('2026-11-12T00:00:00+01:00');
  if (requiresImage && (!item.image || !/^https:\/\//i.test(item.image)))
    errors.push('feed item ' + i + ': new article missing verified HTTPS image: ' + item.url);
  if (item.image && !/^https:\/\//i.test(item.image)) errors.push('feed item ' + i + ': invalid HTTPS image URL');
  if (requiresImage && (!item.image_source_url || !validHttp(item.image_source_url)))
    errors.push('feed item ' + i + ': missing image provenance: ' + item.url);
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
  if (!item || typeof item !== 'object') { errors.push('invalid social item: ' + i); continue; }
  const publishedAt = Date.parse(item.published_at || '');
  const requiresImage = Number.isFinite(publishedAt) && publishedAt >= Date.parse('2026-11-12T00:00:00+01:00');
  if (requiresImage && !/^https:\/\//i.test(item.image || ''))
    errors.push('social item ' + i + ': new post missing verified HTTPS image: ' + item.url);
  if (item.image && !/^https:\/\//i.test(item.image)) errors.push('social item ' + i + ': invalid HTTPS image URL');
}
if (!entries?.length) errors.push('empty main feed');
if (!Object.keys(analyses).length) errors.push('empty analyses');
if (!social.items.length) warn.push('social feed empty: publication targets not met');
console.log(JSON.stringify({feed:entries?.length, analyses:Object.keys(analyses).length, social:social.items?.length, errors,warnings:warn}, null, 2));
if (errors.length) process.exitCode = 1;
