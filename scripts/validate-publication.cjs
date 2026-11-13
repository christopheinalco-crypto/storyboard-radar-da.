const { execFileSync } = require('node:child_process');
const { isDeepStrictEqual } = require('node:util');

const read = (ref, name) => JSON.parse(execFileSync('git', ['show', ref + ':data/' + name + '.json'], { encoding: 'utf8' }));
const clean = value => typeof value === 'string' && value.trim();
function canonical(value) {
  try {
    const url = new URL(value);
    if (!['https:', 'http:'].includes(url.protocol)) return '';
    for (const key of [...url.searchParams.keys()]) {
      if (/^(utm_|fbclid$|gclid$)/i.test(key)) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    return url.hostname.replace(/^www\./, '') + url.pathname.replace(/\/$/, '') + url.search;
  } catch {
    return '';
  }
}

function validatePublication(base, head) {
  const errors = [];
  const before = read(base, 'feed').items;
  const after = read(head, 'feed').items;
  const archived = read(base, 'published-projects').projects;
  const registry = read(head, 'published-projects').projects;
  const analyses = read(head, 'analyses');
  const historical = new Set([...before, ...archived].map(item => canonical(item.url)));
  const projects = new Set([...before, ...archived].map(item => item.project_id).filter(Boolean));
  const existing = new Set(before.map(item => item.url));
  const added = after.filter(item => !existing.has(item.url));
  if (added.length > 7) errors.push('Plafond de 7 nouvelles fiches dépassé.');
  if (!added.length) return errors;
  for (const file of ['analyses', 'social-posts']) {
    const previous = read(base, file);
    const next = read(head, file);
    if (file === 'analyses' && Object.keys(previous).some(url => !next[url])) errors.push('Analyse historique supprimée.');
    if (file === 'social-posts' && !isDeepStrictEqual(previous, next)) errors.push('Archive sociale modifiée pendant la publication.');
  }
  if (before.some(item => !after.some(next => next.url === item.url)) ||
      archived.some(item => !registry.some(next => isDeepStrictEqual(item, next)))) {
    errors.push('Entrée historique supprimée du flux ou du registre.');
  }
  for (const item of added) {
    const reject = message => errors.push(item.url + ' — ' + message);
    const key = canonical(item.url);
    if (!key || historical.has(key) || !clean(item.project_id) || projects.has(item.project_id)) {
      reject('URL ou identité projet invalide ou déjà publiée.');
    }
    historical.add(key);
    projects.add(item.project_id);
    if (/^(?:instagram|linkedin|facebook|tiktok|twitter|x)\.com\//i.test(key) ||
        /instagram|linkedin|réseaux sociaux/i.test(item.category || '')) reject('Rubrique ou source canonique sociale.');
    if (!registry.some(entry => entry.url === item.url && entry.project_id === item.project_id)) reject('Projet absent du registre.');
    const date = Date.parse(item.published);
    const wave = Date.parse(item.radar_added_at);
    const age = (wave - date) / 86400000;
    if (!Number.isFinite(age) || age < 0 || age > 30 || wave > Date.now()) reject('Date invalide ou hors fenêtre de 30 jours.');
    const review = analyses[item.url];
    const gate = review?.publication_review;
    const scores = ['choice', 'effect', 'lesson', 'evidence', 'freshness'];
    const limits = [5, 5, 4, 3, 3];
    const total = scores.reduce((sum, field) => sum + (gate?.scores?.[field] || 0), 0);
    if (!scores.every((field, i) => Number.isInteger(gate?.scores?.[field]) &&
        gate.scores[field] > 0 && gate.scores[field] <= limits[i]) ||
        total < (item.image ? 14 : 17)) reject('Barème incomplet ou note sous le seuil.');
    if (!['choice', 'effect', 'lesson', 'second_reading'].every(field => clean(gate?.[field]))) reject('Veto éditorial ou seconde lecture non documentés.');
    if (item.image ? !(/^https:\/\//i.test(item.image) && canonical(item.image_source_url) && clean(item.image_credit))
      : Boolean(item.youtube_id || item.slate_id)) reject('Provenance du visuel manquante ou carte sans image non compacte.');
    const visits = Array.isArray(gate?.sources) ? gate.sources : [];
    const urls = new Set(visits.filter(source => canonical(source.url) && clean(source.locator) &&
      Number.isFinite(Date.parse(source.opened_at)) && Date.parse(source.opened_at) <= wave &&
      Date.parse(source.opened_at) >= wave - 30 * 86400000).map(source => canonical(source.url)));
    if (!urls.has(key) || !Array.isArray(review?.points) || !review.points.length ||
        !Array.isArray(review.editorial_review) || review.editorial_review.length !== review.points.length ||
        !review.editorial_review.every(ref => urls.has(canonical(ref.url)) && clean(ref.locator))) {
      reject('Sources ouvertes et repères de relecture incomplets.');
    }
  }
  return errors;
}

module.exports = validatePublication;
if (require.main === module) {
  const errors = validatePublication(process.argv[2], process.argv[3]);
  if (errors.length) {
    console.error(errors.join('\n'));
    process.exitCode = 1;
  }
}
