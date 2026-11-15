const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { readFileSync, mkdirSync } = require('node:fs');
const { chromium } = require('playwright');

const feed = JSON.parse(readFileSync('data/feed.json', 'utf8')).items;
const base = process.argv[2];
const previous = base ? JSON.parse(execFileSync('git', [
  'show', base + ':data/feed.json',
], { encoding: 'utf8' })).items : feed;
const byUrl = new Map(previous.map(item => [item.url, item]));
const changed = feed.filter(item => byUrl.get(item.url)?.image !== item.image || !byUrl.has(item.url));
// Un commit du vérificateur seul peut laisser changed vide : tester alors
// les quatre fiches les plus récentes pour prouver le rendu réel du flux.
const cardsToVerify = changed.length ? changed : feed.slice(0, Math.min(4, feed.length));
const publicSite = 'https://christopheinalco-crypto.github.io/storyboard-radar-da./';

async function main() {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' });
    const response = await page.goto(publicSite + '?verify=' + Date.now());
    assert(response?.ok(), 'Le site public ne répond pas');
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
      await card.getByRole('button', { name: /Décryptage DA/ }).click();
      assert(await card.locator('.inline-study').isVisible(), 'Décryptage invisible');
      await card.screenshot({ path: 'public-feed-evidence/fiche-' + (index + 1) + '.png' });
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: 'public-feed-evidence/flux.png' });
    console.log(`${rendered.length} fiches dans le flux public, ${cardsToVerify.length} cartes nouvelles ou modifiées contrôlées (image, vidéo ou titre seul).`);
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
