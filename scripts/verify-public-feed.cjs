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
    mkdirSync('public-feed-evidence', { recursive: true });
    for (const [index, item] of changed.entries()) {
      const card = cards.nth(feed.indexOf(item));
      const image = card.locator('.visual img');
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(async img => {
        await img.decode();
        if (!img.naturalWidth) throw new Error('Visuel non chargé');
      });
      assert.equal(await image.getAttribute('src'), item.image, 'Visuel public différent du visuel validé');
      await card.getByRole('button', { name: /Décryptage DA/ }).click();
      assert(await card.locator('.inline-study').isVisible(), 'Décryptage invisible');
      await card.screenshot({ path: 'public-feed-evidence/fiche-' + (index + 1) + '.png' });
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: 'public-feed-evidence/flux.png' });
    console.log(`${rendered.length} fiches dans le flux public, ${changed.length} visuels contrôlés.`);
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
