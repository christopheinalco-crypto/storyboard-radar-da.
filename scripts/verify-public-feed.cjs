const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { readFileSync, mkdirSync, writeFileSync } = require('node:fs');
const { isDeepStrictEqual } = require('node:util');
const { chromium } = require('playwright');

const feed = JSON.parse(readFileSync('data/feed.json', 'utf8')).items;
const base = process.argv[2];
const head = process.argv[3];
const previous = base ? JSON.parse(execFileSync('git', [
  'show', base + ':data/feed.json',
], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })).items : feed;
const byUrl = new Map(previous.map(item => [item.url, item]));
const analyses = JSON.parse(readFileSync('data/analyses.json', 'utf8'));
const previousAnalyses = base ? JSON.parse(execFileSync('git', [
  'show', base + ':data/analyses.json',
], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })) : analyses;
const changed = feed.filter(item => !isDeepStrictEqual(byUrl.get(item.url), item) ||
  !isDeepStrictEqual(previousAnalyses[item.url], analyses[item.url]));
// Un commit du vérificateur seul peut laisser changed vide : tester alors
// les quatre fiches les plus récentes pour prouver le rendu réel du flux.
const cardsToVerify = changed.length ? changed : feed.slice(0, Math.min(4, feed.length));
// Vérifier aussi un vrai chargement d'image quand la vague présente uniquement des vidéos ou des titres.
if (!cardsToVerify.some(item => item.image)) {
  const illustrated = feed.find(item => item.image);
  if (illustrated) cardsToVerify.push(illustrated);
}
const publicSite = 'https://christopheinalco-crypto.github.io/storyboard-radar-da./';

async function main() {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' });
    const response = await page.goto(publicSite + '?verify=' + Date.now());
    assert(response?.ok(), 'Le site public ne répond pas');
    for (const name of ['feed', 'analyses', 'published-projects']) {
      const url = new URL('data/' + name + '.json?verify=' + Date.now(), publicSite);
      const publicData = await page.request.get(url.href);
      assert(publicData.ok(), 'JSON public indisponible : ' + name);
      assert.deepEqual(await publicData.json(), JSON.parse(readFileSync('data/' + name + '.json', 'utf8')),
        'Version publique différente pour ' + name);
    }
    await page.locator('#feed article').first().waitFor();
    const cards = page.locator('#feed article');
    const rendered = await cards.locator('a.source-action').evaluateAll(links => links.map(link => link.href));
    assert.deepEqual(rendered, feed.map(item => new URL(item.url).href), 'Flux public différent du flux attendu');
    const first = cards.first();
    await first.getByRole('button', { name: /Décryptage DA/ }).click();
    await first.getByRole('button', { name: /Conserver l’idée/ }).click();
    assert.equal(await cards.count(), feed.length, 'Le Carnet masque une fiche du flux');
    assert.equal(await first.locator('a.source-action').evaluate(link => link.href), rendered[0]);
    mkdirSync('public-feed-evidence', { recursive: true });
    for (const [index, item] of cardsToVerify.entries()) {
      const card = cards.nth(feed.indexOf(item));
      const image = card.locator('.visual img');
      if (item.image) {
        assert.equal(await image.count(), 1, 'Image attendue mais absente');
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(async img => {
          await img.decode();
          if (!img.naturalWidth) throw new Error('Visuel non chargé');
        });
        assert.equal(await image.getAttribute('src'), item.image, 'Visuel public différent du visuel validé');
      } else if (/^[A-Za-z0-9_-]{11}$/.test(item.youtube_id || '')) {
        const video = card.locator('iframe.project-video');
        assert.equal(await video.count(), 1, 'Vidéo officielle absente');
        assert((await video.getAttribute('src')).includes('youtube-nocookie.com/embed/' + item.youtube_id),
          'Vidéo du projet incorrecte');
      } else if (/^\d+$/.test(item.slate_id || '')) {
        const video = card.locator('iframe.project-video');
        assert.equal(await video.count(), 1, 'Vidéo Slate absente');
      } else {
        assert.equal(await image.count(), 0, 'Carte titre seul : image inattendue');
        assert(await card.locator('a.source-action').isVisible(), 'Carte titre seul : lien source invisible');
      }
      const study = card.locator('.inline-study');
      if (!(await study.isVisible()))
        await card.getByRole('button', { name: /Décryptage DA/ }).click();
      assert(await study.isVisible(), 'Décryptage invisible');
      if (/\^\^[^^]+\^\^/.test(JSON.stringify(analyses[item.url]))) {
        assert(await study.locator('mark.da-inline-highlight').first().isVisible(), 'Surlignage du décryptage invisible');
      }
      await card.screenshot({ path: 'public-feed-evidence/fiche-' + (index + 1) + '.png' });
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: 'public-feed-evidence/flux.png' });
    const newCards = feed.filter(item => !byUrl.has(item.url));
    writeFileSync('public-feed-evidence/verification.json', JSON.stringify({
      checked_at: new Date().toISOString(),
      site: publicSite,
      head: head || null,
      base: base || null,
      feed_count: rendered.length,
      verified_new_projects: newCards.map(({ project_id, url }) => ({ project_id, url })),
      verified_cards: cardsToVerify.map(({ project_id, url }) => ({ project_id, url })),
    }, null, 2) + '\n');
    console.log(`${rendered.length} fiches dans le flux public, ${cardsToVerify.length} cartes contrôlées (image, vidéo ou titre seul).`);
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
