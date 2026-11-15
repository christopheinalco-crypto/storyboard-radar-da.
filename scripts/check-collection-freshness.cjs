const { readFileSync } = require('node:fs');

const now = Date.now();
const read = name => JSON.parse(readFileSync('data/' + name + '.json', 'utf8'));
const coverage = read('source-coverage');
const brief = read('editorial-brief');
const inspections = read('project-inspections');
const rss = read('collection_report');
const errors = [];

for (const [label, value] of [
  ['Couverture', coverage.checked_at],
  ['Inspection', inspections.updated_at],
  ['Brief', brief.prepared_at],
  ['RSS', rss.collected_at],
]) {
  const age = now - Date.parse(value);
  if (!Number.isFinite(age) || age < 0 || age > 60 * 60 * 1000) {
    errors.push(label + ' : rapport absent, futur ou vieux de plus d’une heure (' + value + ').');
  }
}
if (!coverage.wave_id || coverage.wave_id !== brief.wave_id ||
    coverage.wave_id !== inspections.wave_id || coverage.checked_at !== brief.coverage_checked_at) {
  errors.push('Couverture, inspection et brief issus de collectes différentes.');
}
if (coverage.target_met !== true || !(rss.rss_sources_parsed > 0)) {
  errors.push('Couverture source sous le seuil ou aucun flux RSS exploitable.');
}
if (brief.research_only !== true || brief.eligible_for_publication_count !== 0) {
  errors.push('Le brief doit contenir uniquement des pistes à vérifier.');
}
if (errors.length) {
  console.error(errors.join('\n'));
  process.exitCode = 1;
} else {
  console.log('Rapports frais et cohérents. Sources ouvertes : ' + coverage.opened_successfully +
    '. RSS exploitables : ' + rss.rss_sources_parsed + '.');
}
